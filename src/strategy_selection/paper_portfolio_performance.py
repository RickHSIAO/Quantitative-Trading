"""TASK-014BZ -- authoritative Paper Portfolio performance source + lineage.

TASK-014BY interpreted the wrong artifact family as strategy returns. The Forward
dry-run snapshots ``outputs/forward_record/prev3y_crypto/<date>_pnl.json`` carry
operational metadata only (``clock_started=false``, ``day_number=0``,
``daily_pnl_pct=0``, ``paper_execution_status=FORBIDDEN``) and are NOT a
performance ledger. The authoritative strategy performance is the Paper Portfolio
ledger:

  * ``outputs/forward_record/paper_portfolio/daily_pnl.csv``  (per-day NAV / PnL)
  * ``outputs/forward_record/paper_portfolio/state.json``     (NAV / peak / positions)

This module is READ-ONLY. It never falls back silently to the zero-valued dry-run
JSON: when the authoritative ledger is missing or invalid it fails closed with an
explicit data-quality status. It derives the FIRST 30 valid, unique, ordered
performance rows as the official validation window (it does NOT hardcode the end
date) and reports any later rows separately as a POST_VALIDATION_EXTENSION.

Reuses the canonical metrics in ``src.metrics.performance`` for Sharpe / Sortino /
max-drawdown; never fabricates unavailable trade-level / cost data.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import pathlib
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

TASK_ID = "TASK-014BZ"

# --- Data-quality / lineage statuses ---------------------------------------
VALID_AUTHORITATIVE_PERFORMANCE = "VALID_AUTHORITATIVE_PERFORMANCE"
INVALID_DRY_RUN_PLACEHOLDER = "INVALID_DRY_RUN_PLACEHOLDER"
PERFORMANCE_SOURCE_MISSING = "PERFORMANCE_SOURCE_MISSING"
PERFORMANCE_SOURCE_CONFLICT = "PERFORMANCE_SOURCE_CONFLICT"
NAV_CONTINUITY_FAILURE = "NAV_CONTINUITY_FAILURE"
DUPLICATE_PERFORMANCE_DATE = "DUPLICATE_PERFORMANCE_DATE"
INSUFFICIENT_VALID_PERFORMANCE_DAYS = "INSUFFICIENT_VALID_PERFORMANCE_DAYS"

OFFICIAL_VALIDATION_DAYS = 30
PAPER_EQUITY_INIT_DEFAULT = 10_000.0

# Documented NAV-continuity tolerance. Each row's recorded NAV must agree with the
# NAV implied by the prior NAV and the recorded daily PnL pct, AND with the NAV
# implied by paper_equity_init and the recorded cumulative pct, within this
# RELATIVE tolerance. It is a data-integrity guard, NOT a tuned strategy value.
NAV_CONTINUITY_REL_TOLERANCE = 1e-4

# Headerless ``daily_pnl.csv`` column order (Paper Portfolio ledger). Derived from
# the paired ``<date>_paper_pnl.json`` schema written alongside the ledger.
DAILY_PNL_COLUMNS = (
    "date", "nav_usd", "daily_pnl_usd", "daily_pnl_pct", "cumulative_pnl_pct",
    "max_dd_pct", "n_open", "n_entered", "n_exited", "n_skipped",
    "gross_exposure_ratio", "net_exposure_ratio", "guard_status",
)

_GUARD_PASS = "PASS"


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _finite(value: Any) -> bool:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f)


def _iso(compact: str) -> str:
    return f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}" if len(compact) == 8 else compact


# ---------------------------------------------------------------------------
# Performance row model
# ---------------------------------------------------------------------------


@dataclass
class PerformanceRow:
    date: str                      # compact YYYYMMDD
    nav_usd: float
    daily_pnl_usd: float
    daily_pnl_pct: float           # percent units, as recorded
    cumulative_pnl_pct: float      # percent units, as recorded
    max_dd_pct: float
    n_open: int
    n_entered: int
    n_exited: int
    guard_status: str
    gross_exposure_ratio: float = 0.0
    net_exposure_ratio: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def daily_return_decimal(self) -> float:
        return self.daily_pnl_pct / 100.0

    @property
    def cumulative_return_decimal(self) -> float:
        return self.cumulative_pnl_pct / 100.0


def _parse_row(values: Sequence[str]) -> tuple[PerformanceRow | None, str]:
    """Parse one headerless ``daily_pnl.csv`` record. Returns (row, status) where
    status is VALID_AUTHORITATIVE_PERFORMANCE or a specific rejection reason."""
    if len(values) < len(DAILY_PNL_COLUMNS):
        return None, f"MALFORMED_ROW:expected>={len(DAILY_PNL_COLUMNS)}_got_{len(values)}"
    rec = dict(zip(DAILY_PNL_COLUMNS, values))

    date = str(rec["date"]).strip()
    if len(date) != 8 or not date.isdigit():
        return None, f"MALFORMED_DATE:{date!r}"

    # Every numeric field that feeds performance must be finite.
    for fld in ("nav_usd", "daily_pnl_usd", "daily_pnl_pct", "cumulative_pnl_pct"):
        if not _finite(rec[fld]):
            return None, f"NON_FINITE:{fld}={rec[fld]!r}"
    if float(rec["nav_usd"]) <= 0.0:
        return None, f"NON_POSITIVE_NAV:{rec['nav_usd']!r}"

    guard = str(rec["guard_status"]).strip()
    if guard != _GUARD_PASS:
        return None, f"GUARD_NOT_PASS:{guard!r}"

    def _int(x: Any) -> int:
        try:
            return int(float(x))
        except (TypeError, ValueError):
            return 0

    row = PerformanceRow(
        date=date,
        nav_usd=float(rec["nav_usd"]),
        daily_pnl_usd=float(rec["daily_pnl_usd"]),
        daily_pnl_pct=float(rec["daily_pnl_pct"]),
        cumulative_pnl_pct=float(rec["cumulative_pnl_pct"]),
        max_dd_pct=float(rec["max_dd_pct"]) if _finite(rec["max_dd_pct"]) else 0.0,
        n_open=_int(rec["n_open"]), n_entered=_int(rec["n_entered"]),
        n_exited=_int(rec["n_exited"]), guard_status=guard,
        gross_exposure_ratio=float(rec["gross_exposure_ratio"]) if _finite(rec["gross_exposure_ratio"]) else 0.0,
        net_exposure_ratio=float(rec["net_exposure_ratio"]) if _finite(rec["net_exposure_ratio"]) else 0.0,
        raw=rec,
    )
    return row, VALID_AUTHORITATIVE_PERFORMANCE


# ---------------------------------------------------------------------------
# Dry-run snapshot detection (never read as returns)
# ---------------------------------------------------------------------------


def is_dry_run_placeholder(snapshot: Mapping[str, Any]) -> bool:
    """A Forward dry-run snapshot is an operational placeholder (NOT performance)
    when the strategy clock has not started / day_number is 0 / paper execution is
    forbidden. Such records must never be interpreted as strategy returns."""
    clock_started = bool(snapshot.get("clock_started", False))
    day_number = snapshot.get("day_number", 0)
    forbidden = str(snapshot.get("paper_execution_status", "")).upper() == "FORBIDDEN"
    try:
        day0 = int(day_number) == 0
    except (TypeError, ValueError):
        day0 = False
    # Placeholder when the clock has not started AND the day is 0 (operational
    # snapshot), or when paper execution is explicitly forbidden for that file.
    return (not clock_started and day0) or (forbidden and not clock_started)


def scan_dry_run_snapshots(snapshot_dir: str | pathlib.Path) -> dict[str, Any]:
    """Scan ``prev3y_crypto/<date>_pnl.json`` operational snapshots. Returns
    snapshot counts and a clear placeholder verdict. These files are operational
    metadata ONLY and are deliberately NOT used as a performance source."""
    d = pathlib.Path(snapshot_dir)
    files = sorted(d.glob("*_pnl.json")) if d.exists() else []
    day_dist: dict[str, int] = {}
    clock_started_count = 0
    placeholder_count = 0
    zero_pnl_count = 0
    for p in files:
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        dn = str(obj.get("day_number", "missing"))
        day_dist[dn] = day_dist.get(dn, 0) + 1
        if bool(obj.get("clock_started", False)):
            clock_started_count += 1
        if is_dry_run_placeholder(obj):
            placeholder_count += 1
        if float(obj.get("daily_pnl_pct", 0.0) or 0.0) == 0.0:
            zero_pnl_count += 1
    return {
        "snapshot_file_count": len(files),
        "snapshot_clock_started_count": clock_started_count,
        "snapshot_day_number_distribution": dict(sorted(day_dist.items())),
        "snapshot_zero_daily_pnl_count": zero_pnl_count,
        "dry_run_placeholder_count": placeholder_count,
        "dry_run_placeholder_detected": placeholder_count > 0,
        "note": "Forward dry-run <date>_pnl.json are operational metadata ONLY and are NEVER "
                "interpreted as strategy returns when clock_started=false / day_number=0 / "
                "paper_execution_status=FORBIDDEN.",
    }


# ---------------------------------------------------------------------------
# Authoritative ledger loader
# ---------------------------------------------------------------------------


@dataclass
class AuthoritativePerformance:
    status: str                                  # overall data_lineage_status
    paper_dir: str
    performance_source: str
    performance_source_fingerprint: str
    state_fingerprint: str
    paper_equity_init: float
    all_rows: list[PerformanceRow]               # validated, ordered, deduped
    rejected: list[dict[str, Any]]               # rejected raw rows + reasons
    nav_continuity_failures: list[dict[str, Any]]
    duplicate_dates: list[str]
    state: dict[str, Any]
    state_conflicts: list[str]
    warnings: list[str] = field(default_factory=list)

    @property
    def valid_row_count(self) -> int:
        return len(self.all_rows)


def load_authoritative_performance(
    paper_dir: str | pathlib.Path,
    *,
    paper_equity_init: float | None = None,
) -> AuthoritativePerformance:
    """Load the authoritative Paper Portfolio performance ledger (read-only).

    Fails closed with an explicit status when the ledger is missing or unreadable;
    never substitutes the zero-valued dry-run snapshot JSON. Validates each row,
    rejects duplicates, and flags NAV-continuity breaks. Cross-checks against
    ``state.json`` (last_processed_date / NAV) and reports any conflict.
    """
    d = pathlib.Path(paper_dir)
    csv_path = d / "daily_pnl.csv"
    state_path = d / "state.json"

    state: dict[str, Any] = {}
    state_fp = ""
    if state_path.exists():
        try:
            raw = state_path.read_bytes()
            state_fp = _sha256_bytes(raw)
            state = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            state = {"_error": str(exc)}

    init = (float(paper_equity_init) if paper_equity_init is not None
            else float(state.get("paper_equity_init", PAPER_EQUITY_INIT_DEFAULT) or PAPER_EQUITY_INIT_DEFAULT))
    if not (_finite(init) and init > 0):
        init = PAPER_EQUITY_INIT_DEFAULT

    if not csv_path.exists():
        return AuthoritativePerformance(
            status=PERFORMANCE_SOURCE_MISSING,
            paper_dir=str(d).replace("\\", "/"),
            performance_source="paper_portfolio/daily_pnl.csv",
            performance_source_fingerprint="", state_fingerprint=state_fp,
            paper_equity_init=init, all_rows=[], rejected=[], nav_continuity_failures=[],
            duplicate_dates=[], state=state, state_conflicts=[],
            warnings=["authoritative daily_pnl.csv missing; FAIL CLOSED (no dry-run fallback)"])

    try:
        raw_bytes = csv_path.read_bytes()
    except OSError as exc:
        return AuthoritativePerformance(
            status=PERFORMANCE_SOURCE_MISSING,
            paper_dir=str(d).replace("\\", "/"),
            performance_source="paper_portfolio/daily_pnl.csv",
            performance_source_fingerprint="", state_fingerprint=state_fp,
            paper_equity_init=init, all_rows=[], rejected=[], nav_continuity_failures=[],
            duplicate_dates=[], state=state, state_conflicts=[],
            warnings=[f"daily_pnl.csv unreadable: {exc}; FAIL CLOSED"])

    source_fp = _sha256_bytes(raw_bytes)
    text = raw_bytes.decode("utf-8", errors="replace")

    # Tolerate an optional header line (first field non-numeric date).
    reader = csv.reader(text.splitlines())
    parsed: list[PerformanceRow] = []
    rejected: list[dict[str, Any]] = []
    for values in reader:
        if not values or all(not str(v).strip() for v in values):
            continue
        first = str(values[0]).strip()
        if first.lower() in ("date", "day") or not first[:1].isdigit():
            # header row
            continue
        row, st = _parse_row(values)
        if row is None:
            rejected.append({"raw": list(values), "reason": st})
        else:
            parsed.append(row)

    # Order by date and reject duplicates (keep first occurrence).
    parsed.sort(key=lambda r: r.date)
    seen: set[str] = set()
    ordered: list[PerformanceRow] = []
    duplicate_dates: list[str] = []
    for r in parsed:
        if r.date in seen:
            duplicate_dates.append(r.date)
            rejected.append({"raw": r.raw, "reason": f"{DUPLICATE_PERFORMANCE_DATE}:{r.date}"})
            continue
        seen.add(r.date)
        ordered.append(r)

    # NAV-continuity validation (documented relative tolerance).
    continuity_failures: list[dict[str, Any]] = []
    prev_nav: float | None = None
    for r in ordered:
        implied_cum = init * (1.0 + r.cumulative_return_decimal)
        cum_ok = _rel_close(r.nav_usd, implied_cum, NAV_CONTINUITY_REL_TOLERANCE)
        daily_ok = True
        if prev_nav is not None:
            implied_daily = prev_nav * (1.0 + r.daily_return_decimal)
            daily_ok = _rel_close(r.nav_usd, implied_daily, NAV_CONTINUITY_REL_TOLERANCE)
        if not (cum_ok and daily_ok):
            continuity_failures.append({
                "date": r.date, "nav_usd": r.nav_usd,
                "implied_from_cumulative": implied_cum,
                "implied_from_prior_daily": (prev_nav * (1.0 + r.daily_return_decimal)
                                             if prev_nav is not None else None),
                "cumulative_ok": cum_ok, "daily_ok": daily_ok,
            })
        prev_nav = r.nav_usd

    # State cross-check (does not reduce valid rows; reported as conflict only).
    state_conflicts = _state_conflicts(ordered, state, init)

    status = _overall_status(ordered, duplicate_dates, continuity_failures, state_conflicts)

    return AuthoritativePerformance(
        status=status,
        paper_dir=str(d).replace("\\", "/"),
        performance_source="paper_portfolio/daily_pnl.csv",
        performance_source_fingerprint=source_fp, state_fingerprint=state_fp,
        paper_equity_init=init, all_rows=ordered, rejected=rejected,
        nav_continuity_failures=continuity_failures, duplicate_dates=duplicate_dates,
        state=state, state_conflicts=state_conflicts)


def _rel_close(a: float, b: float, rel: float) -> bool:
    if b == 0.0:
        return abs(a) <= rel
    return abs(a - b) / abs(b) <= rel


def _state_conflicts(rows: Sequence[PerformanceRow], state: Mapping[str, Any], init: float) -> list[str]:
    conflicts: list[str] = []
    if not rows or not state or "_error" in state:
        return conflicts
    last = rows[-1]
    lpd = str(state.get("last_processed_date", "")).strip()
    if lpd and lpd != last.date:
        conflicts.append(f"last_processed_date_mismatch:state={lpd}:ledger_last={last.date}")
    nav = state.get("nav_usd")
    if _finite(nav) and not _rel_close(float(nav), last.nav_usd, NAV_CONTINUITY_REL_TOLERANCE):
        conflicts.append(f"state_nav_mismatch:state={nav}:ledger_last={last.nav_usd}")
    return conflicts


def _overall_status(rows, duplicate_dates, continuity_failures, state_conflicts) -> str:
    if state_conflicts:
        return PERFORMANCE_SOURCE_CONFLICT
    if continuity_failures:
        return NAV_CONTINUITY_FAILURE
    if duplicate_dates:
        return DUPLICATE_PERFORMANCE_DATE
    if len(rows) < OFFICIAL_VALIDATION_DAYS:
        return INSUFFICIENT_VALID_PERFORMANCE_DAYS
    return VALID_AUTHORITATIVE_PERFORMANCE


# ---------------------------------------------------------------------------
# Official 30-day window + post-validation extension
# ---------------------------------------------------------------------------


@dataclass
class ValidationWindow:
    official_rows: list[PerformanceRow]
    extension_rows: list[PerformanceRow]
    official_day_count: int
    sufficient: bool

    @property
    def official_start(self) -> str | None:
        return self.official_rows[0].date if self.official_rows else None

    @property
    def official_end(self) -> str | None:
        return self.official_rows[-1].date if self.official_rows else None

    @property
    def extension_start(self) -> str | None:
        return self.extension_rows[0].date if self.extension_rows else None

    @property
    def extension_end(self) -> str | None:
        return self.extension_rows[-1].date if self.extension_rows else None


def derive_validation_window(
    perf: AuthoritativePerformance, *, official_days: int = OFFICIAL_VALIDATION_DAYS,
) -> ValidationWindow:
    """Select the FIRST ``official_days`` valid, unique, ordered performance rows as
    the official validation window. Rows after the window are the
    POST_VALIDATION_EXTENSION. The end date is DERIVED, never hardcoded."""
    rows = perf.all_rows
    official = rows[:official_days]
    extension = rows[official_days:]
    return ValidationWindow(
        official_rows=official, extension_rows=extension,
        official_day_count=len(official), sufficient=len(official) >= official_days)


# ---------------------------------------------------------------------------
# Metrics over a set of rows (reuse canonical metrics for risk ratios)
# ---------------------------------------------------------------------------


def compute_window_metrics(rows: Sequence[PerformanceRow], *, paper_equity_init: float) -> dict[str, Any]:
    """Compute performance metrics over ``rows``. Cumulative return / NAV come from
    the recorded ledger; Sharpe / Sortino / max-drawdown reuse the canonical
    metrics module on the recorded daily-return series."""
    if not rows:
        return {
            "row_count": 0, "cumulative_return_decimal": None, "end_nav_usd": None,
            "max_drawdown_decimal": None, "sharpe": None, "sortino": None,
            "daily_win_rate": None, "longest_winning_streak": 0, "longest_losing_streak": 0,
            "best_day": None, "worst_day": None,
            "note": "no rows in window",
        }

    daily = [r.daily_return_decimal for r in rows]
    navs = [r.nav_usd for r in rows]

    # Equity-curve max drawdown from authoritative NAV (most direct).
    peak = -math.inf
    max_dd = 0.0
    for nav in navs:
        peak = max(peak, nav)
        if peak > 0:
            dd = nav / peak - 1.0
            max_dd = min(max_dd, dd)

    # Win rate / streaks / best-worst from recorded daily returns.
    wins = sum(1 for x in daily if x > 0)
    win_rate = wins / len(daily)
    longest_win = _longest_streak(daily, positive=True)
    longest_loss = _longest_streak(daily, positive=False)
    best_idx = max(range(len(daily)), key=lambda i: daily[i])
    worst_idx = min(range(len(daily)), key=lambda i: daily[i])

    sharpe, sortino = _canonical_risk_ratios(rows)

    return {
        "row_count": len(rows),
        "cumulative_return_decimal": rows[-1].cumulative_return_decimal,
        "end_nav_usd": rows[-1].nav_usd,
        "start_nav_usd": rows[0].nav_usd,
        "max_drawdown_decimal": max_dd,
        "sharpe": sharpe,
        "sortino": sortino,
        "daily_win_rate": win_rate,
        "winning_day_count": wins,
        "losing_day_count": sum(1 for x in daily if x < 0),
        "flat_day_count": sum(1 for x in daily if x == 0),
        "longest_winning_streak": longest_win,
        "longest_losing_streak": longest_loss,
        "best_day": {"date": _iso(rows[best_idx].date), "return_decimal": daily[best_idx]},
        "worst_day": {"date": _iso(rows[worst_idx].date), "return_decimal": daily[worst_idx]},
        "canonical_metric_source": "src/metrics/performance.py::compute_stats",
    }


def _longest_streak(values: Sequence[float], *, positive: bool) -> int:
    best = cur = 0
    for x in values:
        hit = x > 0 if positive else x < 0
        cur = cur + 1 if hit else 0
        best = max(best, cur)
    return best


def _canonical_risk_ratios(rows: Sequence[PerformanceRow]) -> tuple[float | None, float | None]:
    try:
        import pandas as pd
        from src.metrics import performance as perf
    except Exception:  # noqa: BLE001
        return None, None
    df = pd.DataFrame([{
        "date": _iso(r.date), "portfolio_return": r.daily_return_decimal,
        "benchmark_return": 0.0,
        "gross_exposure": r.gross_exposure_ratio or 1.0,
        "net_exposure": r.net_exposure_ratio,
        "turnover": 0.0, "n_longs": r.n_entered, "n_shorts": 0,
    } for r in rows])
    try:
        stats = perf.compute_stats(df)
    except Exception:  # noqa: BLE001
        return None, None
    return float(stats.get("sharpe_full", 0.0)), float(stats.get("sortino_full", 0.0))


__all__ = [
    "AuthoritativePerformance", "DAILY_PNL_COLUMNS", "DUPLICATE_PERFORMANCE_DATE",
    "INSUFFICIENT_VALID_PERFORMANCE_DAYS", "INVALID_DRY_RUN_PLACEHOLDER",
    "NAV_CONTINUITY_FAILURE", "NAV_CONTINUITY_REL_TOLERANCE", "OFFICIAL_VALIDATION_DAYS",
    "PERFORMANCE_SOURCE_CONFLICT", "PERFORMANCE_SOURCE_MISSING", "PerformanceRow",
    "TASK_ID", "VALID_AUTHORITATIVE_PERFORMANCE", "ValidationWindow",
    "compute_window_metrics", "derive_validation_window", "is_dry_run_placeholder",
    "load_authoritative_performance", "scan_dry_run_snapshots",
]
