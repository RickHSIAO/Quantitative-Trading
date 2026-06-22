"""TASK-014BZ -- corrected strategy diagnostics over the AUTHORITATIVE Paper
Portfolio performance.

Supersedes the TASK-014BY zero-return verdict (which scored the Forward dry-run
snapshot JSON instead of the Paper Portfolio ledger). This module:

  * builds the source-lineage record (snapshot counts vs authoritative rows vs the
    official 30-day count are SEPARATE fields; "37/30" is never a coverage label);
  * scores ONLY the official 30 valid Paper Portfolio days; a positive official
    cumulative return can never fail the positive-net-expectancy gate;
  * keeps Primary/Shadow NON-comparable unless the Shadow has its own independent
    authoritative daily performance series;
  * invalidates the dry-run-based challengers and only emits evidence-backed
    challengers from corrected metrics + available contribution evidence;
  * classifies the observed static long/short hold with daily mark-to-market
    WITHOUT calling it a defect (absent a documented rebalancing intent).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.strategy_selection import paper_portfolio_performance as pp

TASK_ID = "TASK-014BZ"
SUPERSEDED_TASK = "TASK-014BY"
SUPERSEDED_LABEL = "REJECT_INSUFFICIENT_EDGE"

# Corrected scorecard labels (reuse the TASK-014BY vocabulary where it still applies).
KEEP_BASELINE = "KEEP_BASELINE"
CHALLENGER_CANDIDATE = "CHALLENGER_CANDIDATE"
NEEDS_MORE_DATA = "NEEDS_MORE_DATA"
REJECT_EXCESSIVE_DRAWDOWN = "REJECT_EXCESSIVE_DRAWDOWN"
REJECT_DATA_INCOMPLETE = "REJECT_DATA_INCOMPLETE"

GATE_PASS = "PASS"
GATE_FAIL = "FAIL"
GATE_INSUFFICIENT = "INSUFFICIENT"

# REVIEW thresholds (NOT optimized strategy parameters).
CORRECTED_REVIEW_THRESHOLDS = {
    "max_drawdown_decimal": 0.20,      # review threshold (20%)
    "min_official_days": pp.OFFICIAL_VALIDATION_DAYS,
    "label_note": "REVIEW thresholds for the corrected scorecard; not optimized strategy parameters and "
                  "never tuned against the 30-day sample.",
}

# Static-hold behavior classification.
STATIC_HOLD = "STATIC_LONG_SHORT_HOLD_WITH_DAILY_MARK_TO_MARKET"

MAX_CHALLENGERS = 2


# ---------------------------------------------------------------------------
# Source lineage
# ---------------------------------------------------------------------------


def build_source_lineage(
    perf: pp.AuthoritativePerformance,
    window: pp.ValidationWindow,
    snapshot_scan: Mapping[str, Any],
    official_metrics: Mapping[str, Any],
    extension_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble the required output fields with snapshot / authoritative / official
    counts kept strictly SEPARATE."""
    return {
        "task_id": TASK_ID,
        "supersedes": SUPERSEDED_TASK,
        # Snapshot (operational metadata only) -------------------------------
        "snapshot_file_count": snapshot_scan.get("snapshot_file_count", 0),
        "snapshot_clock_started_count": snapshot_scan.get("snapshot_clock_started_count", 0),
        "snapshot_day_number_distribution": snapshot_scan.get("snapshot_day_number_distribution", {}),
        "dry_run_placeholder_detected": snapshot_scan.get("dry_run_placeholder_detected", False),
        # Authoritative performance ------------------------------------------
        "performance_source": perf.performance_source,
        "performance_source_fingerprint": perf.performance_source_fingerprint,
        "state_fingerprint": perf.state_fingerprint,
        "authoritative_performance_row_count": perf.valid_row_count + len(perf.duplicate_dates),
        "valid_performance_row_count": perf.valid_row_count,
        "rejected_row_count": len(perf.rejected),
        # Official window (DERIVED, never hardcoded) -------------------------
        "official_validation_start": window.official_start,
        "official_validation_end": window.official_end,
        "official_validation_day_count": window.official_day_count,
        # Post-validation extension ------------------------------------------
        "post_validation_extension_count": len(window.extension_rows),
        "post_validation_extension_start": window.extension_start,
        "post_validation_extension_end": window.extension_end,
        # Headline metrics ----------------------------------------------------
        "official_30d_cumulative_return": official_metrics.get("cumulative_return_decimal"),
        "extension_latest_cumulative_return": extension_metrics.get("cumulative_return_decimal"),
        "official_30d_nav": official_metrics.get("end_nav_usd"),
        "extension_latest_nav": extension_metrics.get("end_nav_usd"),
        "official_30d_max_drawdown": official_metrics.get("max_drawdown_decimal"),
        "official_30d_sharpe": official_metrics.get("sharpe"),
        "official_30d_sortino": official_metrics.get("sortino"),
        "daily_win_rate": official_metrics.get("daily_win_rate"),
        "longest_winning_streak": official_metrics.get("longest_winning_streak"),
        "longest_losing_streak": official_metrics.get("longest_losing_streak"),
        "best_day": official_metrics.get("best_day"),
        "worst_day": official_metrics.get("worst_day"),
        # Lineage verdict -----------------------------------------------------
        "data_lineage_status": perf.status,
        "data_lineage_note": (
            "Authoritative source = paper_portfolio/daily_pnl.csv (+ state.json). The Forward dry-run "
            "<date>_pnl.json snapshots are operational metadata only and were NOT used as returns. "
            "snapshot_file_count, authoritative_performance_row_count and official_validation_day_count "
            "are SEPARATE fields; the prior '37/30' coverage label is invalid."),
        "nav_continuity_failures": perf.nav_continuity_failures,
        "duplicate_dates": [pp._iso(d) for d in perf.duplicate_dates],
        "state_conflicts": perf.state_conflicts,
    }


# ---------------------------------------------------------------------------
# Corrected scorecard (scores ONLY the official 30 valid days)
# ---------------------------------------------------------------------------


def _gate(name: str, status: str, detail: str) -> dict[str, str]:
    return {"gate": name, "status": status, "detail": detail}


def score_official_window(
    perf: pp.AuthoritativePerformance,
    window: pp.ValidationWindow,
    official_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Deterministic corrected scorecard. Fails closed to NEEDS_MORE_DATA when the
    authoritative window is not yet 30 valid days. A positive official cumulative
    return PASSES the positive-net-expectancy gate (it can never fail it)."""
    gates: list[dict[str, str]] = []

    lineage_ok = perf.status == pp.VALID_AUTHORITATIVE_PERFORMANCE
    window_ok = window.sufficient

    # Authoritative-source gate (drives REJECT_DATA_INCOMPLETE vs NEEDS_MORE_DATA).
    if perf.status in (pp.PERFORMANCE_SOURCE_MISSING, pp.PERFORMANCE_SOURCE_CONFLICT):
        gates.append(_gate("authoritative_source", GATE_FAIL, f"lineage={perf.status}"))
    elif perf.status in (pp.NAV_CONTINUITY_FAILURE, pp.DUPLICATE_PERFORMANCE_DATE):
        gates.append(_gate("authoritative_source", GATE_FAIL, f"integrity={perf.status}"))
    elif not window_ok:
        gates.append(_gate("authoritative_source", GATE_INSUFFICIENT,
                           f"{window.official_day_count} of {pp.OFFICIAL_VALIDATION_DAYS} valid days"))
    else:
        gates.append(_gate("authoritative_source", GATE_PASS,
                           f"{window.official_day_count} valid authoritative days"))

    cum = official_metrics.get("cumulative_return_decimal")
    # Positive-net-expectancy gate: scored on observed official cumulative return.
    if not window_ok or cum is None:
        gates.append(_gate("positive_net_expectancy", GATE_INSUFFICIENT,
                           "official 30-day window not yet complete"))
    else:
        gates.append(_gate("positive_net_expectancy",
                           GATE_PASS if cum > 0.0 else GATE_FAIL,
                           f"official_cumulative_return={cum}"))

    # Drawdown gate (review threshold).
    dd = official_metrics.get("max_drawdown_decimal")
    if not window_ok or dd is None:
        gates.append(_gate("acceptable_drawdown", GATE_INSUFFICIENT, "drawdown sample insufficient"))
    else:
        gates.append(_gate("acceptable_drawdown",
                           GATE_PASS if abs(dd) <= CORRECTED_REVIEW_THRESHOLDS["max_drawdown_decimal"]
                           else GATE_FAIL, f"official_max_dd={dd}"))

    # Risk-adjusted observation (reported, not a hard gate when single-strategy).
    sharpe = official_metrics.get("sharpe")
    gates.append(_gate("risk_adjusted_observation",
                       GATE_PASS if (sharpe is not None and window_ok) else GATE_INSUFFICIENT,
                       f"official_sharpe={sharpe}"))

    # Dimensions that remain UNAVAILABLE from the ledger (never fabricated).
    gates.append(_gate("trade_level_profit_factor", GATE_INSUFFICIENT,
                       "PF/expectancy UNAVAILABLE (ledger has no per-trade win/loss records)"))
    gates.append(_gate("cost_funding_slippage_robustness", GATE_INSUFFICIENT,
                       "cost/funding/slippage robustness UNAVAILABLE (needs Demo fills)"))
    gates.append(_gate("oos_comparison", GATE_INSUFFICIENT,
                       "like-for-like OOS comparison UNAVAILABLE (no compatible OOS series supplied)"))
    gates.append(_gate("regime_robustness", GATE_INSUFFICIENT,
                       "no canonical regime definition; regime robustness UNAVAILABLE"))

    label = _resolve_label(gates, lineage_ok=lineage_ok, window_ok=window_ok, perf=perf)
    return {
        "task_id": TASK_ID, "strategy_id": "prev3y_crypto_combined_paper_safe_variant",
        "supersedes": {"task": SUPERSEDED_TASK, "invalid_label": SUPERSEDED_LABEL,
                       "reason": "prior label scored zero-valued dry-run snapshots, not the "
                                 "authoritative Paper Portfolio ledger"},
        "scored_window": {"official_day_count": window.official_day_count,
                          "official_start": window.official_start,
                          "official_end": window.official_end},
        "gates": gates, "label": label,
        "review_thresholds": CORRECTED_REVIEW_THRESHOLDS,
        "observed_return": official_metrics.get("cumulative_return_decimal"),
        "risk_adjusted": {"sharpe": official_metrics.get("sharpe"),
                          "sortino": official_metrics.get("sortino"),
                          "max_drawdown": official_metrics.get("max_drawdown_decimal")},
        "explicitly_missing": [
            "trade_level_profit_factor", "cost_funding_slippage_evidence",
            "oos_comparison", "regime_definition",
        ],
        "ranks_by_return_only": False,
        "label_rationale": _label_rationale(label),
    }


def _resolve_label(gates, *, lineage_ok, window_ok, perf) -> str:
    by_name = {g["gate"]: g["status"] for g in gates}
    if by_name.get("authoritative_source") == GATE_FAIL:
        if perf.status in (pp.PERFORMANCE_SOURCE_MISSING,):
            return NEEDS_MORE_DATA
        return REJECT_DATA_INCOMPLETE
    if not window_ok or not lineage_ok:
        return NEEDS_MORE_DATA
    if by_name.get("acceptable_drawdown") == GATE_FAIL:
        return REJECT_EXCESSIVE_DRAWDOWN
    # Positive official return + acceptable drawdown + full authoritative window.
    if by_name.get("positive_net_expectancy") == GATE_PASS:
        return KEEP_BASELINE
    return CHALLENGER_CANDIDATE


def _label_rationale(label: str) -> str:
    return {
        NEEDS_MORE_DATA: "Authoritative Paper Portfolio window not yet 30 valid days in this runtime; "
                         "the active V1 baseline remains frozen and running. No fallback to dry-run JSON.",
        REJECT_DATA_INCOMPLETE: "authoritative performance source missing/conflicting/integrity-failed.",
        KEEP_BASELINE: "official 30-day authoritative window shows positive cumulative return within the "
                       "drawdown review threshold; keep V1 (trade-level PF / cost / OOS still pending).",
        CHALLENGER_CANDIDATE: "official window complete but headline gate not strongly positive.",
        REJECT_EXCESSIVE_DRAWDOWN: "official 30-day max drawdown exceeds the review threshold.",
    }.get(label, "")


# ---------------------------------------------------------------------------
# Primary vs Shadow comparability (authoritative performance required)
# ---------------------------------------------------------------------------


def assess_primary_shadow_comparability(
    primary: pp.AuthoritativePerformance,
    shadow: pp.AuthoritativePerformance | None,
) -> dict[str, Any]:
    """Primary and Shadow are comparable ONLY when BOTH have an independent
    authoritative daily performance series of the same length/methodology. Forward
    snapshot availability alone is insufficient."""
    primary_ok = primary.status == pp.VALID_AUTHORITATIVE_PERFORMANCE
    if shadow is None:
        return {
            "task_id": TASK_ID, "primary_shadow_comparable": False,
            "reason": "MISSING_SHADOW_AUTHORITATIVE_PERFORMANCE: no independent Shadow Paper Portfolio "
                      "daily performance series exists; snapshot availability alone is insufficient.",
            "primary_has_authoritative_performance": primary_ok,
            "shadow_has_authoritative_performance": False,
        }
    shadow_ok = shadow.status == pp.VALID_AUTHORITATIVE_PERFORMANCE
    same_length = primary.valid_row_count == shadow.valid_row_count and primary.valid_row_count > 0
    comparable = primary_ok and shadow_ok and same_length
    return {
        "task_id": TASK_ID, "primary_shadow_comparable": comparable,
        "reason": ("comparable: both have independent authoritative series of equal length"
                   if comparable else
                   "NOT_COMPARABLE: shadow lacks an equal-length authoritative performance series"),
        "primary_has_authoritative_performance": primary_ok,
        "shadow_has_authoritative_performance": shadow_ok,
        "primary_valid_rows": primary.valid_row_count,
        "shadow_valid_rows": shadow.valid_row_count,
    }


# ---------------------------------------------------------------------------
# Static-hold behavior classification
# ---------------------------------------------------------------------------


def classify_hold_behavior(
    window: pp.ValidationWindow, *, rebalancing_documented: bool = False,
) -> dict[str, Any]:
    """Classify the observed entry/exit cadence. The current evidence (entries on
    the first day, no later entries/exits, unchanged targets, daily mark-to-market)
    is reported as a static hold and is NOT automatically a defect."""
    rows = window.official_rows or window.extension_rows
    entered_first = rows[0].n_entered if rows else 0
    later_entries = sum(r.n_entered for r in rows[1:]) if len(rows) > 1 else 0
    later_exits = sum(r.n_exited for r in rows[1:]) if len(rows) > 1 else 0
    nav_changed = len({round(r.nav_usd, 6) for r in rows}) > 1 if rows else False
    static = entered_first > 0 and later_entries == 0 and later_exits == 0

    warning = None
    if static and rebalancing_documented:
        warning = ("STRATEGY_DOC_EXPECTS_REBALANCING: repository strategy documentation states daily "
                   "re-ranking/rebalancing was intended, but the ledger shows a static hold.")

    return {
        "task_id": TASK_ID,
        "behavior": STATIC_HOLD if static else "ACTIVE_REBALANCING_OBSERVED",
        "first_day_entries": entered_first,
        "later_entries": later_entries,
        "later_exits": later_exits,
        "daily_mark_to_market_observed": nav_changed,
        "is_defect": False,
        "warning": warning,
        "note": "Static long/short hold with daily mark-to-market is reported as an observation, NOT a "
                "defect. A warning is added only if strategy docs state daily rebalancing was intended.",
    }


# ---------------------------------------------------------------------------
# Corrected challengers
# ---------------------------------------------------------------------------


def correct_challengers(
    perf: pp.AuthoritativePerformance,
    window: pp.ValidationWindow,
    official_metrics: Mapping[str, Any],
    *,
    contribution_available: bool = False,
    capabilities: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Invalidate the prior dry-run-derived challengers. Emit AT MOST two
    evidence-backed challengers ONLY from corrected authoritative metrics +
    available contribution evidence. Until then, prior H1/H2 are retained only as
    future_research_candidates and are NOT labelled EVIDENCE_BACKED."""
    caps = dict(capabilities or {})
    window_ok = window.sufficient and perf.status == pp.VALID_AUTHORITATIVE_PERFORMANCE

    invalidated = [
        {"id": "H1_replace_equal_weight_with_canonical_risk_sizing",
         "prior_status": "EVIDENCE_BACKED", "corrected_status": "INVALIDATED_FROM_DRY_RUN_ANALYSIS",
         "reason": "prior backing came from the zero-return dry-run analysis; 30 snapshot files existing "
                   "is not performance evidence"},
        {"id": "H2_enable_existing_canonical_overlay_gate",
         "prior_status": "EVIDENCE_BACKED", "corrected_status": "INVALIDATED_FROM_DRY_RUN_ANALYSIS",
         "reason": "prior backing came from the zero-return dry-run analysis"},
    ]

    future_research: list[dict[str, Any]] = [
        {"id": "FRC_equal_weight_vs_risk_sizing",
         "structural_observation": "Paper Portfolio holds ~equal target weights across 50 names.",
         "candidate_single_change": "OFFLINE/SHADOW only: compare equal-weight vs the existing canonical "
                                    "risk sizer (src/demo_portfolio_risk).",
         "requires": "corrected authoritative per-symbol contribution evidence before selection",
         "dimension": "strategy_native_sizing", "status": "FUTURE_RESEARCH_CANDIDATE"},
        {"id": "FRC_overlay_or_regime_gate",
         "structural_observation": "No overlay/regime filter currently constrains entries.",
         "candidate_single_change": "OFFLINE/SHADOW only: evaluate the existing canonical overlay/regime "
                                    "gate as an entry filter.",
         "requires": "corrected authoritative drawdown/regime evidence before selection",
         "dimension": "entry_overlay_filter", "status": "FUTURE_RESEARCH_CANDIDATE"},
    ]

    contribution_note = (
        "Per-symbol / per-trade contribution is UNAVAILABLE from the ledger; therefore NO causal claim "
        "(e.g. 'equal-weight caused poor/strong performance') is made." if not contribution_available
        else "per-symbol contribution available; causal hypotheses may reference it.")

    hypotheses: list[dict[str, Any]] = []
    if window_ok and contribution_available:
        # Only here may evidence-backed challengers be emitted (still NOT promoted).
        if caps.get("volatility_adjusted_sizing"):
            hypotheses.append({
                "id": "H1c_risk_sizing_from_authoritative_contribution",
                "status": "EVIDENCE_BACKED", "evidence_strength": "AUTHORITATIVE_30D",
                "proposed_single_change": "OFFLINE/SHADOW: replace equal-weight with the existing canonical "
                                          "risk sizer (src/demo_portfolio_risk).",
                "changes": {"strategy_native_sizing": True},
                "promotion_status": "NONE_PROMOTED",
            })

    return {
        "task_id": TASK_ID, "max_allowed": MAX_CHALLENGERS,
        "emitted_count": len(hypotheses), "hypotheses": hypotheses[:MAX_CHALLENGERS],
        "invalidated_prior_challengers": invalidated,
        "future_research_candidates": future_research,
        "contribution_available": contribution_available,
        "contribution_note": contribution_note,
        "evidence_strength": "AUTHORITATIVE_30D" if window_ok else "INSUFFICIENT_AUTHORITATIVE_EVIDENCE",
        "promotion_status": "NONE_PROMOTED",
        "note": "Prior challengers from the zero-return dry-run analysis are invalidated. No challenger is "
                "labelled EVIDENCE_BACKED merely because 30 snapshot files exist; challengers require "
                "corrected authoritative metrics + contribution evidence and are never promoted here.",
    }


__all__ = [
    "CHALLENGER_CANDIDATE", "CORRECTED_REVIEW_THRESHOLDS", "GATE_FAIL", "GATE_INSUFFICIENT",
    "GATE_PASS", "KEEP_BASELINE", "MAX_CHALLENGERS", "NEEDS_MORE_DATA", "REJECT_DATA_INCOMPLETE",
    "REJECT_EXCESSIVE_DRAWDOWN", "STATIC_HOLD", "SUPERSEDED_LABEL", "SUPERSEDED_TASK", "TASK_ID",
    "assess_primary_shadow_comparability", "build_source_lineage", "classify_hold_behavior",
    "correct_challengers", "score_official_window",
]
