"""TASK-014BZ_FIX -- holding-period vs fresh-daily-risk metrics + corrected scorecard.

Keeps two scopes strictly separate:
  * Holding-period: the +6.077668% 30-calendar-day cumulative return and end NAV
    (10607.7668) remain reportable; drawdown is reported only as
    OBSERVED_MARK_DRAWDOWN with a stale-path warning.
  * Fresh one-day risk: Sharpe/Sortino/streaks/win-rate/best-worst use ONLY
    FRESH_DAILY_MARK days; below the minimum fresh count they are
    INSUFFICIENT_FRESH_DAILY_OBSERVATIONS (never published as official).

The corrected scorecard never returns REJECT_DATA_INCOMPLETE once the additive
ledger validates; a positive holding-period return yields KEEP_BASELINE_PROVISIONAL.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from src.strategy_selection import paper_portfolio_performance as pp
from src.strategy_selection import price_freshness as pf
from src.strategy_selection import ledger_fix_semantics as lfs

TASK_ID = "TASK-014BZ_FIX"

# Corrected overall labels.
KEEP_BASELINE_PROVISIONAL = "KEEP_BASELINE_PROVISIONAL"
NEEDS_MORE_DATA = "NEEDS_MORE_DATA"
REJECT_EXCESSIVE_DRAWDOWN = "REJECT_EXCESSIVE_DRAWDOWN"

GATE_PASS = "PASS"
GATE_FAIL = "FAIL"
GATE_INSUFFICIENT = "INSUFFICIENT"
GATE_PASS_WITH_WARNING = "PASS_WITH_WARNING"

OBSERVED_MARK_DRAWDOWN = "OBSERVED_MARK_DRAWDOWN"

CORRECTED_REVIEW_THRESHOLDS = {
    "max_drawdown_decimal": 0.20,
    "min_fresh_daily_observations": pf.MIN_FRESH_DAILY_OBSERVATIONS,
    "label_note": "REVIEW thresholds; not optimized strategy parameters and never tuned against the sample.",
}

SUPERSEDED = [
    {"task": "TASK-014BY", "invalid_label": "REJECT_INSUFFICIENT_EDGE",
     "reason": "scored zero-valued Forward dry-run snapshot JSON"},
    {"task": "TASK-014BZ", "invalid_label": "REJECT_DATA_INCOMPLETE",
     "reason": "false-positive from the wrong prior-NAV compounding continuity check"},
]


# ---------------------------------------------------------------------------
# Holding-period scope (all official calendar days)
# ---------------------------------------------------------------------------


def compute_holding_period_metrics(
    official_rows: Sequence[pp.PerformanceRow], *, paper_equity_init: float,
) -> dict[str, Any]:
    if not official_rows:
        return {"calendar_days": 0, "cumulative_return_decimal": None, "end_nav_usd": None,
                "observed_mark_drawdown_decimal": None, "drawdown_status": OBSERVED_MARK_DRAWDOWN,
                "note": "no official rows"}
    last = official_rows[-1]
    peak = -math.inf
    max_dd = 0.0
    for r in official_rows:
        peak = max(peak, r.nav_usd)
        if peak > 0:
            max_dd = min(max_dd, r.nav_usd / peak - 1.0)
    return {
        "scope": "CALENDAR_HOLDING_PERIOD",
        "calendar_days": len(official_rows),
        "start_date": pp._iso(official_rows[0].date),
        "end_date": pp._iso(last.date),
        "cumulative_return_decimal": last.cumulative_pnl_pct / 100.0,
        "end_nav_usd": last.nav_usd,
        "start_nav_usd": official_rows[0].nav_usd,
        "observed_mark_drawdown_decimal": max_dd,
        "drawdown_status": OBSERVED_MARK_DRAWDOWN,
        "drawdown_warning": "OBSERVED_MARK_DRAWDOWN over the recorded daily marks; the intra-period path "
                            "across stale-cache intervals is UNKNOWN, so this is a mark-to-market drawdown, "
                            "not a verified worst intra-period drawdown.",
        "note": "Holding-period cumulative return and end NAV remain valid as a 30-calendar-day result.",
    }


# ---------------------------------------------------------------------------
# Fresh one-day risk scope (FRESH_DAILY_MARK only)
# ---------------------------------------------------------------------------


def compute_fresh_daily_risk(
    official_rows: Sequence[pp.PerformanceRow], freshness: Mapping[str, Any], *,
    paper_equity_init: float, min_fresh: int = pf.MIN_FRESH_DAILY_OBSERVATIONS,
) -> dict[str, Any]:
    init = float(paper_equity_init)
    fresh_dates = set(freshness.get("fresh_daily_dates", []))
    fresh_rows = [r for r in official_rows if r.date in fresh_dates]
    count = len(fresh_rows)
    base = {
        "scope": "FRESH_ONE_DAY_RISK",
        "fresh_daily_observation_count": count,
        "min_fresh_daily_observations": min_fresh,
        "excluded_scopes": [pf.ENTRY_PRICE_ANCHOR, pf.STALE_CACHE_NO_PRICE_CHANGE,
                            pf.FRESH_MULTI_DAY_CATCHUP_MARK],
        "note": "Daily risk metrics use ONLY FRESH_DAILY_MARK days; stale zeros and the multi-day "
                "catch-up mark are excluded.",
    }
    if count < min_fresh:
        base.update({
            "status": pf.INSUFFICIENT_FRESH_DAILY_OBSERVATIONS,
            "sharpe": None, "sortino": None, "daily_win_rate": None,
            "longest_winning_streak": None, "longest_losing_streak": None,
            "best_day": None, "worst_day": None,
            "warning": "Below the documented minimum fresh daily observation threshold; daily Sharpe/"
                       "Sortino are NOT published as official (would otherwise be computed from stale "
                       "zeros plus the multi-day catch-up mark).",
        })
        return base

    # Fixed-capital daily returns over fresh marks only.
    daily = [r.daily_pnl_usd / init for r in fresh_rows]
    wins = sum(1 for x in daily if x > 0)
    best_i = max(range(len(daily)), key=lambda i: daily[i])
    worst_i = min(range(len(daily)), key=lambda i: daily[i])
    sharpe, sortino = _risk_ratios(daily)
    base.update({
        "status": "FRESH_DAILY_METRICS_AVAILABLE",
        "sharpe": sharpe, "sortino": sortino,
        "daily_win_rate": wins / count,
        "longest_winning_streak": _streak(daily, positive=True),
        "longest_losing_streak": _streak(daily, positive=False),
        "best_day": {"date": pp._iso(fresh_rows[best_i].date), "return_decimal": daily[best_i]},
        "worst_day": {"date": pp._iso(fresh_rows[worst_i].date), "return_decimal": daily[worst_i]},
    })
    return base


def _streak(values: Sequence[float], *, positive: bool) -> int:
    best = cur = 0
    for x in values:
        hit = x > 0 if positive else x < 0
        cur = cur + 1 if hit else 0
        best = max(best, cur)
    return best


def _risk_ratios(daily: Sequence[float], annualization: float = 365.25) -> tuple[float | None, float | None]:
    if len(daily) < 2:
        return None, None
    n = len(daily)
    mean = sum(daily) / n
    var = sum((x - mean) ** 2 for x in daily) / (n - 1)
    std = math.sqrt(var)
    sharpe = (mean / std * math.sqrt(annualization)) if std > 0 else 0.0
    downs = [x for x in daily if x < 0]
    if downs:
        dvar = sum(x * x for x in downs) / len(downs)
        dstd = math.sqrt(dvar)
        sortino = (mean / dstd * math.sqrt(annualization)) if dstd > 0 else 0.0
    else:
        sortino = 0.0
    return sharpe, sortino


# ---------------------------------------------------------------------------
# Extension scope
# ---------------------------------------------------------------------------


def compute_extension_metrics(
    extension_rows: Sequence[pp.PerformanceRow], *, official_end_nav: float | None,
    freshness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not extension_rows:
        return {"extension_count": 0, "extension_latest_cumulative_return_from_initial": None,
                "extension_period_return": None, "fresh_daily_observation_count": 0, "robust": False}
    last = extension_rows[-1]
    fresh_dates = set((freshness or {}).get("fresh_daily_dates", []))
    fresh_in_ext = sum(1 for r in extension_rows if r.date in fresh_dates)
    period_ret = (last.nav_usd / official_end_nav - 1.0) if official_end_nav else None
    return {
        "extension_start": pp._iso(extension_rows[0].date),
        "extension_end": pp._iso(last.date),
        "extension_count": len(extension_rows),
        "extension_latest_cumulative_return_from_initial": last.cumulative_pnl_pct / 100.0,
        "extension_latest_nav": last.nav_usd,
        "extension_period_return": period_ret,
        "extension_period_return_reference_nav": official_end_nav,
        "fresh_daily_observation_count": fresh_in_ext,
        "robust": False,
        "note": "Extension is reported separately; a six-day Sharpe/Sortino is NOT presented as robust.",
    }


# ---------------------------------------------------------------------------
# Corrected scorecard
# ---------------------------------------------------------------------------


def _gate(name: str, status: str, detail: str) -> dict[str, str]:
    return {"gate": name, "status": status, "detail": detail}


def score_corrected(
    *, semantics: Mapping[str, Any], canonicalization_status: str,
    holding: Mapping[str, Any], fresh_risk: Mapping[str, Any], official_sufficient: bool,
) -> dict[str, Any]:
    """Corrected scorecard. Never REJECT_DATA_INCOMPLETE once the additive ledger
    validates; positive holding-period return -> KEEP_BASELINE_PROVISIONAL."""
    gates: list[dict[str, str]] = []

    semantics_valid = semantics.get("overall_status") == lfs.LEDGER_SEMANTICS_VALID
    canon_ok = canonicalization_status == lfs.CANONICALIZATION_VALID
    source_ok = semantics_valid and canon_ok and official_sufficient

    gates.append(_gate("authoritative_source",
                       GATE_PASS if source_ok else GATE_INSUFFICIENT,
                       f"semantics={semantics.get('overall_status')}, canon={canonicalization_status}, "
                       f"official_sufficient={official_sufficient}"))

    cum = holding.get("cumulative_return_decimal")
    if not official_sufficient or cum is None:
        gates.append(_gate("positive_holding_period_return", GATE_INSUFFICIENT,
                           "official holding-period window not yet complete"))
    else:
        gates.append(_gate("positive_holding_period_return",
                           GATE_PASS if cum > 0.0 else GATE_FAIL,
                           f"holding_period_cumulative_return={cum}"))

    dd = holding.get("observed_mark_drawdown_decimal")
    if dd is None:
        gates.append(_gate("observed_drawdown", GATE_INSUFFICIENT, "drawdown sample insufficient"))
    elif abs(dd) <= CORRECTED_REVIEW_THRESHOLDS["max_drawdown_decimal"]:
        gates.append(_gate("observed_drawdown", GATE_PASS_WITH_WARNING,
                           f"{OBSERVED_MARK_DRAWDOWN}={dd}; stale-interval intra-period path unknown"))
    else:
        gates.append(_gate("observed_drawdown", GATE_FAIL, f"{OBSERVED_MARK_DRAWDOWN}={dd} exceeds threshold"))

    gates.append(_gate("daily_risk_metrics",
                       fresh_risk.get("status", pf.INSUFFICIENT_FRESH_DAILY_OBSERVATIONS),
                       f"fresh_daily_observation_count={fresh_risk.get('fresh_daily_observation_count')}"))

    gates.append(_gate("trade_level_profit_factor", GATE_INSUFFICIENT,
                       "PF/expectancy UNAVAILABLE (no per-trade win/loss records)"))
    gates.append(_gate("cost_funding_slippage_robustness", GATE_INSUFFICIENT,
                       "cost/funding/slippage UNAVAILABLE (needs Demo fills)"))
    gates.append(_gate("oos_comparison", GATE_INSUFFICIENT, "no compatible OOS series supplied"))
    gates.append(_gate("regime_robustness", GATE_INSUFFICIENT, "no canonical regime definition"))

    label = _resolve_label(gates, source_ok=source_ok)
    return {
        "task_id": TASK_ID, "strategy_id": "prev3y_crypto_combined_paper_safe_variant",
        "supersedes": SUPERSEDED,
        "gates": gates, "label": label,
        "label_rationale": _label_rationale(label),
        "review_thresholds": CORRECTED_REVIEW_THRESHOLDS,
        "holding_period_return": holding.get("cumulative_return_decimal"),
        "holding_period_end_nav": holding.get("end_nav_usd"),
        "daily_risk_status": fresh_risk.get("status"),
        "explicitly_missing": ["trade_level_profit_factor", "cost_funding_slippage_evidence",
                               "oos_comparison", "regime_definition"],
        "never_reject_data_incomplete_after_additive_valid": True,
        "ranks_by_return_only": False,
    }


def _resolve_label(gates, *, source_ok: bool) -> str:
    by = {g["gate"]: g["status"] for g in gates}
    if not source_ok:
        # Authoritative source not yet complete in this runtime -> NEEDS_MORE_DATA
        # (never REJECT_DATA_INCOMPLETE once additive semantics are the model).
        return NEEDS_MORE_DATA
    if by.get("observed_drawdown") == GATE_FAIL:
        return REJECT_EXCESSIVE_DRAWDOWN
    if by.get("positive_holding_period_return") == GATE_PASS:
        return KEEP_BASELINE_PROVISIONAL
    return NEEDS_MORE_DATA


def _label_rationale(label: str) -> str:
    return {
        KEEP_BASELINE_PROVISIONAL: "Additive ledger validates and the 30-calendar-day holding-period "
                                   "return is positive (+6.077668%); kept PROVISIONALLY because daily risk "
                                   "metrics rest on only 19 fresh one-day observations and trade-level PF / "
                                   "cost / OOS / regime evidence is still pending.",
        NEEDS_MORE_DATA: "Authoritative additive window not yet complete in this runtime; active V1 baseline "
                         "remains frozen and running. Never REJECT_DATA_INCOMPLETE after additive validation.",
        REJECT_EXCESSIVE_DRAWDOWN: "observed mark drawdown exceeds the review threshold.",
    }.get(label, "")


__all__ = [
    "CORRECTED_REVIEW_THRESHOLDS", "GATE_FAIL", "GATE_INSUFFICIENT", "GATE_PASS",
    "GATE_PASS_WITH_WARNING", "KEEP_BASELINE_PROVISIONAL", "NEEDS_MORE_DATA",
    "OBSERVED_MARK_DRAWDOWN", "REJECT_EXCESSIVE_DRAWDOWN", "SUPERSEDED", "TASK_ID",
    "compute_extension_metrics", "compute_fresh_daily_risk", "compute_holding_period_metrics",
    "score_corrected",
]
