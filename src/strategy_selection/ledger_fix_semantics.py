"""TASK-014BZ_FIX / FIX2 -- fixed-capital additive ledger semantics + duplicate
canonicalization.

The authoritative Paper Portfolio ledger is additive on FIXED initial capital, not
compounding against prior-day NAV. The correct relations are:

    nav_t            ≈ nav_(t-1) + daily_pnl_usd                       (additive NAV)
    daily_pnl_pct    ≈ daily_pnl_usd / paper_equity_init * 100         (fixed-capital %)
    cumulative_pnl_pct ≈ (nav_t / paper_equity_init - 1) * 100         (cumulative %)

Duplicate-date canonicalization (FIX2): same-date rows can form an INCREMENTAL
RERUN CHAIN where each row's delta contributes to the canonical daily result.
The real 20260605 duplicate is two incremental deltas:

    10480.2968 - 61.0413 = 10419.2555  (row 1)
    10419.2555 + 26.6375 = 10445.8930  (row 2)

Canonical aggregated daily_pnl_usd = -61.0413 + 26.6375 = -34.4038 (NOT +26.6375).
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Sequence

from src.strategy_selection import paper_portfolio_performance as pp

TASK_ID = "TASK-014BZ_FIX"

# --- Additive fixed-capital semantic statuses ------------------------------
ADDITIVE_NAV_VALID = "ADDITIVE_NAV_VALID"
DAILY_PCT_FIXED_CAPITAL_VALID = "DAILY_PCT_FIXED_CAPITAL_VALID"
CUMULATIVE_PCT_VALID = "CUMULATIVE_PCT_VALID"
LEDGER_SEMANTICS_VALID = "LEDGER_SEMANTICS_VALID"
ADDITIVE_NAV_FAILURE = "ADDITIVE_NAV_FAILURE"
DAILY_PCT_FAILURE = "DAILY_PCT_FAILURE"
CUMULATIVE_PCT_FAILURE = "CUMULATIVE_PCT_FAILURE"

# --- Duplicate-date classification -----------------------------------------
IDENTICAL_DUPLICATE = "IDENTICAL_DUPLICATE"
SAME_DATE_INCREMENTAL_RERUN_CHAIN = "SAME_DATE_INCREMENTAL_RERUN_CHAIN"
TRUE_REPLACEMENT_RERUN = "TRUE_REPLACEMENT_RERUN"
SUPERSEDED_RERUN = "SUPERSEDED_RERUN"  # back-compat alias
AMBIGUOUS_DUPLICATE_CONFLICT = "AMBIGUOUS_DUPLICATE_CONFLICT"
CANONICALIZATION_VALID = "CANONICALIZATION_VALID"
CANONICALIZATION_AMBIGUOUS = "CANONICALIZATION_AMBIGUOUS"

# Documented ABSOLUTE tolerances for the ledger's decimal rounding (NAV/PnL are
# recorded to 4 decimals; percentages to ~6 decimals). These are integrity guards,
# NOT tuned strategy parameters.
NAV_ABS_TOL_USD = 1e-2
PCT_ABS_TOL = 1e-4

# Ledger decimal precision used for normalization / fingerprints.
_NAV_DP = 4
_PCT_DP = 6


def _norm(value: float, dp: int) -> float:
    return round(float(value), dp)


def row_fingerprint(row: pp.PerformanceRow) -> str:
    payload = "|".join([
        row.date,
        f"{_norm(row.nav_usd, _NAV_DP):.4f}",
        f"{_norm(row.daily_pnl_usd, _NAV_DP):.4f}",
        f"{_norm(row.daily_pnl_pct, _PCT_DP):.6f}",
        f"{_norm(row.cumulative_pnl_pct, _PCT_DP):.6f}",
    ])
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalized_tuple(row: pp.PerformanceRow) -> tuple:
    return (row.date, _norm(row.nav_usd, _NAV_DP), _norm(row.daily_pnl_usd, _NAV_DP),
            _norm(row.daily_pnl_pct, _PCT_DP), _norm(row.cumulative_pnl_pct, _PCT_DP))


# ---------------------------------------------------------------------------
# Per-row fixed-capital checks
# ---------------------------------------------------------------------------


def _daily_pct_ok(row: pp.PerformanceRow, init: float, tol: float = PCT_ABS_TOL) -> bool:
    implied = row.daily_pnl_usd / init * 100.0
    return abs(row.daily_pnl_pct - implied) <= tol


def _cumulative_pct_ok(row: pp.PerformanceRow, init: float, tol: float = PCT_ABS_TOL) -> bool:
    implied = (row.nav_usd / init - 1.0) * 100.0
    return abs(row.cumulative_pnl_pct - implied) <= tol


def compounding_continuity_holds(rows: Sequence[pp.PerformanceRow], *, tol: float = NAV_ABS_TOL_USD) -> bool:
    """True iff the (WRONG, prior-NAV compounding) relation nav_t ≈ nav_(t-1) *
    (1 + daily_pnl_pct/100) holds for all rows. For this additive ledger it does
    NOT hold; exposed so tests can prove the compounding formula is rejected."""
    prev = None
    for r in rows:
        if prev is not None:
            implied = prev * (1.0 + r.daily_pnl_pct / 100.0)
            if abs(r.nav_usd - implied) > tol:
                return False
        prev = r.nav_usd
    return True


# ---------------------------------------------------------------------------
# Additive fixed-capital ledger semantic validation
# ---------------------------------------------------------------------------


def validate_ledger_semantics(
    rows: Sequence[pp.PerformanceRow], paper_equity_init: float, *,
    nav_tol: float = NAV_ABS_TOL_USD, pct_tol: float = PCT_ABS_TOL,
) -> dict[str, Any]:
    """Validate the three canonical additive fixed-capital relations on an ordered
    canonical (unique-date) row chain. ``daily_pnl_pct`` is NEVER interpreted as a
    compounded return against prior-day NAV."""
    init = float(paper_equity_init)
    per_row: list[dict[str, Any]] = []
    additive_all = daily_all = cum_all = True
    failures = 0
    prev_nav: float | None = None
    for r in rows:
        base = init if prev_nav is None else prev_nav
        implied_nav = base + r.daily_pnl_usd
        a_ok = abs(r.nav_usd - implied_nav) <= nav_tol
        d_ok = _daily_pct_ok(r, init, pct_tol)
        c_ok = _cumulative_pct_ok(r, init, pct_tol)
        if not (a_ok and d_ok and c_ok):
            failures += 1
        additive_all &= a_ok
        daily_all &= d_ok
        cum_all &= c_ok
        per_row.append({
            "date": pp._iso(r.date),
            "additive_nav": ADDITIVE_NAV_VALID if a_ok else ADDITIVE_NAV_FAILURE,
            "daily_pct": DAILY_PCT_FIXED_CAPITAL_VALID if d_ok else DAILY_PCT_FAILURE,
            "cumulative_pct": CUMULATIVE_PCT_VALID if c_ok else CUMULATIVE_PCT_FAILURE,
            "implied_nav": round(implied_nav, _NAV_DP),
            "implied_daily_pct": round(r.daily_pnl_usd / init * 100.0, _PCT_DP),
            "implied_cumulative_pct": round((r.nav_usd / init - 1.0) * 100.0, _PCT_DP),
        })
        prev_nav = r.nav_usd

    overall_valid = additive_all and daily_all and cum_all
    statuses: list[str] = []
    if additive_all:
        statuses.append(ADDITIVE_NAV_VALID)
    else:
        statuses.append(ADDITIVE_NAV_FAILURE)
    if daily_all:
        statuses.append(DAILY_PCT_FIXED_CAPITAL_VALID)
    else:
        statuses.append(DAILY_PCT_FAILURE)
    if cum_all:
        statuses.append(CUMULATIVE_PCT_VALID)
    else:
        statuses.append(CUMULATIVE_PCT_FAILURE)
    return {
        "task_id": TASK_ID,
        "semantics_model": "ADDITIVE_FIXED_CAPITAL",
        "paper_equity_init": init,
        "row_count": len(rows),
        "consistency_failure_count": failures,
        "additive_nav_status": ADDITIVE_NAV_VALID if additive_all else ADDITIVE_NAV_FAILURE,
        "daily_pct_status": DAILY_PCT_FIXED_CAPITAL_VALID if daily_all else DAILY_PCT_FAILURE,
        "cumulative_pct_status": CUMULATIVE_PCT_VALID if cum_all else CUMULATIVE_PCT_FAILURE,
        "statuses": statuses,
        "overall_status": LEDGER_SEMANTICS_VALID if overall_valid else "LEDGER_SEMANTICS_FAILURE",
        "tolerances": {"nav_abs_usd": nav_tol, "pct_abs": pct_tol},
        "note": "Additive on fixed initial capital: nav_t = nav_(t-1) + daily_pnl_usd; "
                "daily_pnl_pct = daily_pnl_usd / paper_equity_init * 100; "
                "cumulative_pnl_pct = (nav_t / paper_equity_init - 1) * 100. "
                "daily_pnl_pct is NOT a compounded prior-day-NAV return.",
        "per_row": per_row,
    }


# ---------------------------------------------------------------------------
# Duplicate-date canonicalization (raw ledger preserved)
# ---------------------------------------------------------------------------


@dataclass
class CanonicalizationResult:
    status: str
    canonical_rows: list[pp.PerformanceRow]
    resolution_records: list[dict[str, Any]]
    raw_row_count: int
    canonical_row_count: int
    duplicate_date_count: int
    identical_duplicate_count: int
    same_date_incremental_rerun_chain_count: int
    true_replacement_rerun_count: int
    ambiguous_duplicate_conflict_count: int
    canonical_row_fingerprints: list[dict[str, str]] = field(default_factory=list)
    superseded_row_fingerprints: list[dict[str, str]] = field(default_factory=list)

    @property
    def superseded_rerun_count(self) -> int:
        return self.true_replacement_rerun_count


def _continues_into(c: pp.PerformanceRow, next_rows, init: float) -> bool:
    """A candidate continues the chain if it passes its own fixed-capital + cumulative
    checks AND some next-date row satisfies c.nav + next.daily_pnl_usd ≈ next.nav."""
    if not (_daily_pct_ok(c, init) and _cumulative_pct_ok(c, init)):
        return False
    for nr in next_rows:
        if abs((c.nav_usd + nr.daily_pnl_usd) - nr.nav_usd) <= NAV_ABS_TOL_USD:
            return True
    return False


def _continues_from(c: pp.PerformanceRow, prev_canon: pp.PerformanceRow | None, init: float) -> bool:
    if prev_canon is None:
        return False
    if not (_daily_pct_ok(c, init) and _cumulative_pct_ok(c, init)):
        return False
    return abs((prev_canon.nav_usd + c.daily_pnl_usd) - c.nav_usd) <= NAV_ABS_TOL_USD


def _try_incremental_chain(
    cands: list[pp.PerformanceRow], prev_nav: float | None, next_rows: list[pp.PerformanceRow],
    init: float, tol: float = NAV_ABS_TOL_USD,
) -> pp.PerformanceRow | None:
    """Test if the raw same-date rows (in file order) form an ordered intra-date
    additive chain:
    1. first row starts from prev canonical NAV;
    2. each subsequent row NAV = prior same-date row NAV + its daily_pnl_usd;
    3. final row connects to at least one next-date row;
    4. every row's cumulative_pnl_pct matches its own NAV against fixed initial capital.

    If valid, returns a synthetic canonical row with aggregated daily PnL."""
    if prev_nav is None or len(cands) < 2:
        return None
    running = prev_nav
    for r in cands:
        implied = running + r.daily_pnl_usd
        if abs(r.nav_usd - implied) > tol:
            return None
        if not _cumulative_pct_ok(r, init):
            return None
        running = r.nav_usd
    final = cands[-1]
    if next_rows:
        if not any(abs((final.nav_usd + nr.daily_pnl_usd) - nr.nav_usd) <= tol for nr in next_rows):
            return None
    summed_pnl = sum(r.daily_pnl_usd for r in cands)
    agg_pct = round(summed_pnl / init * 100.0, 6)
    return pp.PerformanceRow(
        date=final.date, nav_usd=final.nav_usd, daily_pnl_usd=round(summed_pnl, 4),
        daily_pnl_pct=agg_pct, cumulative_pnl_pct=final.cumulative_pnl_pct,
        max_dd_pct=final.max_dd_pct, n_open=final.n_open, n_entered=final.n_entered,
        n_exited=final.n_exited, guard_status=final.guard_status)


def canonicalize_ledger(raw_rows: Sequence[pp.PerformanceRow], paper_equity_init: float) -> CanonicalizationResult:
    """Resolve duplicate dates into a single canonical unique-date chain without
    mutating the raw ledger.

    Priority order for differing same-date rows:
    1. SAME_DATE_INCREMENTAL_RERUN_CHAIN — raw rows form an ordered intra-date
       additive chain; construct a synthetic canonical row with aggregated daily PnL.
    2. TRUE_REPLACEMENT_RERUN — exactly one full-day candidate independently connects
       to both prior and next canonical rows.
    3. AMBIGUOUS_DUPLICATE_CONFLICT — fail closed (no first-wins / last-wins).
    """
    init = float(paper_equity_init)
    by_date: "OrderedDict[str, list[pp.PerformanceRow]]" = OrderedDict()
    for r in raw_rows:
        by_date.setdefault(r.date, []).append(r)
    dates_sorted = sorted(by_date)

    canonical: list[pp.PerformanceRow] = []
    records: list[dict[str, Any]] = []
    canon_fps: list[dict[str, str]] = []
    superseded_fps: list[dict[str, str]] = []
    identical = incremental = replacement = ambiguous = 0
    duplicate_dates = [d for d in dates_sorted if len(by_date[d]) > 1]

    for i, d in enumerate(dates_sorted):
        cands = by_date[d]
        if len(cands) == 1:
            canonical.append(cands[0])
            continue

        # --- Identical duplicate (safe dedupe) ---
        if len({_normalized_tuple(c) for c in cands}) == 1:
            identical += 1
            chosen = cands[0]
            canonical.append(chosen)
            records.append({
                "date": pp._iso(d), "classification": IDENTICAL_DUPLICATE,
                "raw_row_count": len(cands),
                "reason": "all normalized financial fields identical; safely deduplicated",
                "row_identities": [row_fingerprint(c) for c in cands],
                "canonical_fingerprint": row_fingerprint(chosen),
            })
            canon_fps.append({"date": pp._iso(d), "fingerprint": row_fingerprint(chosen)})
            continue

        next_rows = by_date[dates_sorted[i + 1]] if i + 1 < len(dates_sorted) else []
        prev_canon = canonical[-1] if canonical else None
        prev_nav = prev_canon.nav_usd if prev_canon else (init if not canonical else None)

        # --- Priority 1: same-date incremental rerun chain ---
        agg = _try_incremental_chain(cands, prev_nav, next_rows, init)
        if agg is not None:
            incremental += 1
            canonical.append(agg)
            prior_d = dates_sorted[i - 1] if i > 0 else None
            next_d = dates_sorted[i + 1] if i + 1 < len(dates_sorted) else None
            records.append({
                "date": pp._iso(d), "classification": SAME_DATE_INCREMENTAL_RERUN_CHAIN,
                "contributing_raw_row_count": len(cands),
                "contributing_raw_row_fingerprints": [row_fingerprint(c) for c in cands],
                "canonical_row_fingerprint": row_fingerprint(agg),
                "canonical_daily_pnl_usd": agg.daily_pnl_usd,
                "canonical_daily_pnl_pct": agg.daily_pnl_pct,
                "canonical_nav_usd": agg.nav_usd,
                "canonical_cumulative_pnl_pct": agg.cumulative_pnl_pct,
                "prior_date": pp._iso(prior_d) if prior_d else None,
                "next_date": pp._iso(next_d) if next_d else None,
                "prior_continuity_pass": True,
                "intra_date_chain_pass": True,
                "next_date_continuity_pass": bool(next_rows),
                "reason": "raw rows form an ordered intra-date additive chain; canonical daily PnL "
                          "is the SUM of all same-date deltas (not any single row's daily_pnl_usd)",
            })
            canon_fps.append({"date": pp._iso(d), "fingerprint": row_fingerprint(agg)})
            continue

        # --- Priority 2: true full-day replacement rerun ---
        continuous = [c for c in cands if _continues_into(c, next_rows, init)
                      and (prev_canon is None or _continues_from(c, prev_canon, init))]
        method = "both_prior_and_next_continuity"
        if not continuous:
            continuous = [c for c in cands if _continues_into(c, next_rows, init)]
            method = "next_date_additive_continuity"
        if not continuous and not next_rows:
            continuous = [c for c in cands if _continues_from(c, prev_canon, init)]
            method = "prior_date_additive_continuity"

        if len(continuous) == 1:
            replacement += 1
            chosen = continuous[0]
            others = [c for c in cands if c is not chosen]
            canonical.append(chosen)
            records.append({
                "date": pp._iso(d), "classification": TRUE_REPLACEMENT_RERUN,
                "raw_row_count": len(cands), "resolution_method": method,
                "reason": "exactly one full-day replacement candidate connects independently to "
                          "both prior and next canonical rows",
                "canonical_row": {"date": pp._iso(d), "nav_usd": chosen.nav_usd,
                                  "daily_pnl_usd": chosen.daily_pnl_usd,
                                  "cumulative_pnl_pct": chosen.cumulative_pnl_pct},
                "superseded_rows": [{"date": pp._iso(d), "nav_usd": o.nav_usd,
                                     "daily_pnl_usd": o.daily_pnl_usd,
                                     "cumulative_pnl_pct": o.cumulative_pnl_pct} for o in others],
                "canonical_fingerprint": row_fingerprint(chosen),
                "superseded_fingerprints": [row_fingerprint(o) for o in others],
            })
            canon_fps.append({"date": pp._iso(d), "fingerprint": row_fingerprint(chosen)})
            for o in others:
                superseded_fps.append({"date": pp._iso(d), "fingerprint": row_fingerprint(o)})
        else:
            # --- Priority 3: fail closed ---
            ambiguous += 1
            records.append({
                "date": pp._iso(d), "classification": AMBIGUOUS_DUPLICATE_CONFLICT,
                "raw_row_count": len(cands), "continuous_candidate_count": len(continuous),
                "reason": "neither an incremental chain nor a unique full-day replacement can be "
                          "proven; FAIL CLOSED (no first-wins / last-wins)",
                "row_identities": [row_fingerprint(c) for c in cands],
            })

    status = CANONICALIZATION_AMBIGUOUS if ambiguous else CANONICALIZATION_VALID
    return CanonicalizationResult(
        status=status, canonical_rows=canonical, resolution_records=records,
        raw_row_count=len(raw_rows), canonical_row_count=len(canonical),
        duplicate_date_count=len(duplicate_dates), identical_duplicate_count=identical,
        same_date_incremental_rerun_chain_count=incremental,
        true_replacement_rerun_count=replacement,
        ambiguous_duplicate_conflict_count=ambiguous,
        canonical_row_fingerprints=canon_fps, superseded_row_fingerprints=superseded_fps)


def build_duplicate_resolution_report(canon: CanonicalizationResult) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "raw_performance_row_count": canon.raw_row_count,
        "canonical_performance_row_count": canon.canonical_row_count,
        "duplicate_date_count": canon.duplicate_date_count,
        "identical_duplicate_count": canon.identical_duplicate_count,
        "same_date_incremental_rerun_chain_count": canon.same_date_incremental_rerun_chain_count,
        "true_replacement_rerun_count": canon.true_replacement_rerun_count,
        "ambiguous_duplicate_conflict_count": canon.ambiguous_duplicate_conflict_count,
        "canonicalization_status": canon.status,
        "duplicate_resolution_records": canon.resolution_records,
        "canonical_row_fingerprints": canon.canonical_row_fingerprints,
        "superseded_row_fingerprints": canon.superseded_row_fingerprints,
    }


__all__ = [
    "ADDITIVE_NAV_FAILURE", "ADDITIVE_NAV_VALID", "AMBIGUOUS_DUPLICATE_CONFLICT",
    "CANONICALIZATION_AMBIGUOUS", "CANONICALIZATION_VALID", "CUMULATIVE_PCT_FAILURE",
    "CUMULATIVE_PCT_VALID", "CanonicalizationResult", "DAILY_PCT_FAILURE",
    "DAILY_PCT_FIXED_CAPITAL_VALID", "IDENTICAL_DUPLICATE", "LEDGER_SEMANTICS_VALID",
    "NAV_ABS_TOL_USD", "PCT_ABS_TOL", "SAME_DATE_INCREMENTAL_RERUN_CHAIN",
    "SUPERSEDED_RERUN", "TASK_ID", "TRUE_REPLACEMENT_RERUN",
    "build_duplicate_resolution_report", "canonicalize_ledger", "compounding_continuity_holds",
    "row_fingerprint", "validate_ledger_semantics",
]
