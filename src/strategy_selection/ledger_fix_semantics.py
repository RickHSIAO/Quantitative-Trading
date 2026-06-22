"""TASK-014BZ_FIX -- fixed-capital additive ledger semantics + duplicate
canonicalization.

The authoritative Paper Portfolio ledger is additive on FIXED initial capital, not
compounding against prior-day NAV. TASK-014BZ validated the wrong relation
(``nav_t ≈ nav_(t-1) * (1 + daily_pnl_pct)``), producing false
``NAV_CONTINUITY_FAILURE`` results. The correct relations are:

    nav_t            ≈ nav_(t-1) + daily_pnl_usd                       (additive NAV)
    daily_pnl_pct    ≈ daily_pnl_usd / paper_equity_init * 100         (fixed-capital %)
    cumulative_pnl_pct ≈ (nav_t / paper_equity_init - 1) * 100         (cumulative %)

This module validates those three relations and canonicalizes duplicate dates
WITHOUT mutating the raw append-only ledger. The real 20260605 duplicate resolves
to the second row (CANONICAL_RERUN_FINAL) because only it continues additively into
20260606 (10445.8930 + 151.5218 = 10597.4148).
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
SUPERSEDED_RERUN = "SUPERSEDED_RERUN"
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
    superseded_rerun_count: int
    ambiguous_duplicate_conflict_count: int
    canonical_row_fingerprints: list[dict[str, str]] = field(default_factory=list)
    superseded_row_fingerprints: list[dict[str, str]] = field(default_factory=list)


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


def canonicalize_ledger(raw_rows: Sequence[pp.PerformanceRow], paper_equity_init: float) -> CanonicalizationResult:
    """Resolve duplicate dates into a single canonical unique-date chain without
    mutating the raw ledger. Identical duplicates are safely deduplicated; differing
    duplicates are resolved by additive continuity into the next canonical row
    (SUPERSEDED_RERUN); otherwise the date fails closed (AMBIGUOUS_DUPLICATE_CONFLICT;
    never first-wins/last-wins)."""
    init = float(paper_equity_init)
    by_date: "OrderedDict[str, list[pp.PerformanceRow]]" = OrderedDict()
    for r in raw_rows:
        by_date.setdefault(r.date, []).append(r)
    dates_sorted = sorted(by_date)

    canonical: list[pp.PerformanceRow] = []
    records: list[dict[str, Any]] = []
    canon_fps: list[dict[str, str]] = []
    superseded_fps: list[dict[str, str]] = []
    identical = superseded = ambiguous = 0
    duplicate_dates = [d for d in dates_sorted if len(by_date[d]) > 1]

    for i, d in enumerate(dates_sorted):
        cands = by_date[d]
        if len(cands) == 1:
            canonical.append(cands[0])
            continue

        # Duplicate date.
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
        continuous = [c for c in cands if _continues_into(c, next_rows, init)]
        method = "next_date_additive_continuity"
        if not continuous and not next_rows:
            continuous = [c for c in cands if _continues_from(c, prev_canon, init)]
            method = "prior_date_additive_continuity"

        if len(continuous) == 1:
            superseded += 1
            chosen = continuous[0]
            others = [c for c in cands if c is not chosen]
            canonical.append(chosen)
            records.append({
                "date": pp._iso(d), "classification": SUPERSEDED_RERUN,
                "raw_row_count": len(cands), "resolution_method": method,
                "reason": "exactly one candidate continues additively into the next canonical row "
                          "and passes its own fixed-capital + cumulative checks (CANONICAL_RERUN_FINAL)",
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
            ambiguous += 1
            records.append({
                "date": pp._iso(d), "classification": AMBIGUOUS_DUPLICATE_CONFLICT,
                "raw_row_count": len(cands), "continuous_candidate_count": len(continuous),
                "reason": "no candidate (or multiple candidates) continues the additive chain; "
                          "FAIL CLOSED (no first-wins / last-wins)",
                "row_identities": [row_fingerprint(c) for c in cands],
            })

    status = CANONICALIZATION_AMBIGUOUS if ambiguous else CANONICALIZATION_VALID
    return CanonicalizationResult(
        status=status, canonical_rows=canonical, resolution_records=records,
        raw_row_count=len(raw_rows), canonical_row_count=len(canonical),
        duplicate_date_count=len(duplicate_dates), identical_duplicate_count=identical,
        superseded_rerun_count=superseded, ambiguous_duplicate_conflict_count=ambiguous,
        canonical_row_fingerprints=canon_fps, superseded_row_fingerprints=superseded_fps)


def build_duplicate_resolution_report(canon: CanonicalizationResult) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "raw_performance_row_count": canon.raw_row_count,
        "canonical_performance_row_count": canon.canonical_row_count,
        "duplicate_date_count": canon.duplicate_date_count,
        "identical_duplicate_count": canon.identical_duplicate_count,
        "superseded_rerun_count": canon.superseded_rerun_count,
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
    "NAV_ABS_TOL_USD", "PCT_ABS_TOL", "SUPERSEDED_RERUN", "TASK_ID",
    "build_duplicate_resolution_report", "canonicalize_ledger", "compounding_continuity_holds",
    "row_fingerprint", "validate_ledger_semantics",
]
