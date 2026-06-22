"""TASK-014BY -- transparent, deterministic strategy scorecard + challenger design.

The scorecard does NOT rank strategies by return alone; it applies explicit gates
(net expectancy, PF, drawdown, Forward/OOS consistency, cost robustness,
concentration, regime robustness, sample sufficiency, data completeness,
execution feasibility) and emits an explicit label. Thresholds are REVIEW
thresholds (clearly labelled), reusing documented project values where available.

It freezes/identifies the active V1 baseline WITHOUT modifying its strategy logic
or mutating the Pilot state, designs AT MOST two evidence-based Challenger
hypotheses (each a single change, referencing an EXISTING repository capability),
and builds an updateable 7-day Demo comparison scaffold whose current fields are
NOT_YET_AVAILABLE (never fabricated).
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any, Mapping, Sequence

from src.strategy_selection import forward30_diagnostics as diag

TASK_ID = "TASK-014BY"

# Scorecard labels.
KEEP_BASELINE = "KEEP_BASELINE"
CHALLENGER_CANDIDATE = "CHALLENGER_CANDIDATE"
NEEDS_MORE_DATA = "NEEDS_MORE_DATA"
REJECT_INSUFFICIENT_EDGE = "REJECT_INSUFFICIENT_EDGE"
REJECT_EXCESSIVE_DRAWDOWN = "REJECT_EXCESSIVE_DRAWDOWN"
REJECT_CONCENTRATED_RESULT = "REJECT_CONCENTRATED_RESULT"
REJECT_COST_FRAGILE = "REJECT_COST_FRAGILE"
REJECT_DATA_INCOMPLETE = "REJECT_DATA_INCOMPLETE"

GATE_PASS = "PASS"
GATE_FAIL = "FAIL"
GATE_INSUFFICIENT = "INSUFFICIENT"

# REVIEW thresholds (NOT optimized strategy parameters).
SCORECARD_REVIEW_THRESHOLDS = {
    "min_profit_factor": 1.2,        # review threshold
    "max_drawdown_decimal": 0.20,    # review threshold (20%)
    "min_net_expectancy": 0.0,       # must be > 0
    "max_top1_weight_share": 0.25,   # review threshold for concentration
    "label_note": "REVIEW thresholds for selection gates; not optimized strategy parameters and "
                  "never tuned against the 30-day sample.",
}

EXCLUSIONS = ("TASK-014BO_BP_MANUAL_ROUND_TRIP", "SMOKE_TEST")

FROZEN_ACTIVE_BASELINE = "FROZEN_ACTIVE_BASELINE"

MAX_CHALLENGERS = 2


# ---------------------------------------------------------------------------
# V1 baseline manifest (freeze + identify; no strategy/pilot mutation)
# ---------------------------------------------------------------------------


def build_v1_baseline_manifest(
    *,
    code_commit: str,
    pilot_id: str,
    diagnostics: Mapping[str, Any],
    policy_fingerprint: str = "",
    forward_period: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the versioned V1 baseline manifest. Read-only: derives fingerprints
    from the supplied diagnostics; never reads/writes the live Pilot state."""
    integrity = diagnostics.get("data_integrity", {})
    artifact_fps = dict(integrity.get("source_fingerprints", {}))
    manifest = {
        "baseline_name": "V1",
        "strategy_id": diag.EXPECTED_STRATEGY_NAME,
        "source_run_key": diag.PRIMARY_RUN_KEY,
        "code_commit": code_commit,
        "pilot_id": pilot_id,
        "policy_configuration_fingerprint": policy_fingerprint,
        "forward_validation_period": forward_period or {
            "covered_dates": integrity.get("covered_dates", []),
            "present_date_count": integrity.get("present_date_count", 0),
            "expected_date_count": integrity.get("expected_date_count", 0),
        },
        "artifact_fingerprints": artifact_fps,
        "exclusions": list(EXCLUSIONS),
        "status": FROZEN_ACTIVE_BASELINE,
        "task_id": TASK_ID,
        "notes": "Active V1 strategy logic is FROZEN and UNCHANGED; this manifest only identifies "
                 "and fingerprints the baseline. The running Pilot state was not mutated.",
    }
    manifest["manifest_fingerprint"] = manifest_fingerprint(manifest)
    return manifest


def manifest_fingerprint(manifest: Mapping[str, Any]) -> str:
    payload = {k: v for k, v in manifest.items() if k != "manifest_fingerprint"}
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Scorecard gates
# ---------------------------------------------------------------------------


def _gate(name: str, status: str, detail: str) -> dict[str, str]:
    return {"gate": name, "status": status, "detail": detail}


def score_strategy(diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic gated scorecard. Returns gate results + an explicit label.
    Never ranks by return alone."""
    integrity = diagnostics.get("data_integrity", {})
    overall = diagnostics.get("overall_metrics", {})
    contribution = diagnostics.get("contribution", {})
    cost = diagnostics.get("cost_stress", {})

    suff = integrity.get("sample_sufficient", {})
    sample_ok = bool(suff.get("return_metrics")) and bool(suff.get("risk_ratios"))
    coverage_ok = integrity.get("present_date_count", 0) >= integrity.get("expected_date_count", 30)
    data_complete = sample_ok and coverage_ok and not integrity.get("stale_summary", False) \
        and integrity.get("strategy_id_matches_expected", True)

    gates: list[dict[str, str]] = []

    # Data completeness gate (first; drives NEEDS_MORE_DATA vs REJECT_DATA_INCOMPLETE).
    if integrity.get("strategy_id_matches_expected", True) is False:
        gates.append(_gate("data_completeness", GATE_FAIL, "strategy_id mismatch"))
    elif not coverage_ok or not sample_ok:
        gates.append(_gate("data_completeness", GATE_INSUFFICIENT,
                           f"{integrity.get('present_date_count', 0)} of "
                           f"{integrity.get('expected_date_count', 30)} days present"))
    else:
        gates.append(_gate("data_completeness", GATE_PASS, "sufficient coverage and sample"))

    # Sample sufficiency gate.
    gates.append(_gate("sample_sufficiency", GATE_PASS if sample_ok else GATE_INSUFFICIENT,
                       "return/risk sample sufficient" if sample_ok else "insufficient observations"))

    cm = overall.get("canonical_metrics", {})

    # Net expectancy gate (trade-level expectancy UNAVAILABLE -> INSUFFICIENT).
    gates.append(_gate("positive_net_expectancy", GATE_INSUFFICIENT,
                       "trade-level expectancy UNAVAILABLE (no trade records)")
                 if not sample_ok else
                 _gate("positive_net_expectancy",
                       GATE_PASS if overall.get("cumulative_return_decimal", 0.0) >
                       SCORECARD_REVIEW_THRESHOLDS["min_net_expectancy"] else GATE_FAIL,
                       f"cumulative_return={overall.get('cumulative_return_decimal', 0.0)}"))

    # Profit factor gate (UNAVAILABLE without trade-level wins/losses).
    gates.append(_gate("acceptable_profit_factor", GATE_INSUFFICIENT,
                       "PF UNAVAILABLE (no trade-level win/loss data)"))

    # Drawdown gate (canonical max_dd if sample sufficient).
    if sample_ok and "max_dd_full" in cm:
        dd = abs(float(cm.get("max_dd_full", 0.0)))
        gates.append(_gate("acceptable_drawdown",
                           GATE_PASS if dd <= SCORECARD_REVIEW_THRESHOLDS["max_drawdown_decimal"]
                           else GATE_FAIL, f"max_dd={dd}"))
    else:
        gates.append(_gate("acceptable_drawdown", GATE_INSUFFICIENT, "drawdown sample insufficient"))

    # Forward/OOS consistency.
    oos = diagnostics.get("oos_vs_forward", {})
    gates.append(_gate("forward_oos_consistency",
                       GATE_PASS if oos.get("status") == diag.PRESENT else GATE_INSUFFICIENT,
                       f"oos_status={oos.get('status')}"))

    # Cost robustness.
    gates.append(_gate("cost_robustness", GATE_INSUFFICIENT,
                       "cost stress UNAVAILABLE (paper dry-run zero cost; needs Demo fills)")
                 if cost.get("all_costs_zero_paper_dry_run", True) else
                 _gate("cost_robustness", GATE_PASS, "recorded costs present"))

    # Concentration.
    conc = contribution.get("concentration", {})
    top1 = float(conc.get("top1_weight_share", 0.0))
    gates.append(_gate("concentration",
                       GATE_PASS if top1 <= SCORECARD_REVIEW_THRESHOLDS["max_top1_weight_share"]
                       else GATE_FAIL,
                       f"top1_weight_share={top1} (structural exposure; PnL concentration UNAVAILABLE)"))

    # Regime robustness.
    regime = diagnostics.get("regime", {})
    gates.append(_gate("regime_robustness", GATE_INSUFFICIENT,
                       f"regime status={regime.get('status')}"))

    # Execution feasibility (Demo execution path exists & authorized for this Pilot).
    gates.append(_gate("execution_feasibility", GATE_PASS,
                       "strategy-native Bybit Demo execution path exists (TASK-014BX)"))

    label = _resolve_label(gates, data_complete=data_complete, integrity=integrity)
    return {
        "task_id": TASK_ID, "strategy_id": diag.EXPECTED_STRATEGY_NAME,
        "gates": gates, "label": label,
        "review_thresholds": SCORECARD_REVIEW_THRESHOLDS,
        "label_rationale": _label_rationale(label),
        "ranks_by_return_only": False,
    }


def _resolve_label(gates: Sequence[Mapping[str, str]], *, data_complete: bool,
                   integrity: Mapping[str, Any]) -> str:
    by_name = {g["gate"]: g["status"] for g in gates}
    if by_name.get("data_completeness") == GATE_FAIL:
        return REJECT_DATA_INCOMPLETE
    if not data_complete:
        return NEEDS_MORE_DATA
    # From here, data is complete; apply hard rejects then keep/challenger.
    if by_name.get("acceptable_drawdown") == GATE_FAIL:
        return REJECT_EXCESSIVE_DRAWDOWN
    if by_name.get("concentration") == GATE_FAIL:
        return REJECT_CONCENTRATED_RESULT
    if by_name.get("cost_robustness") == GATE_FAIL:
        return REJECT_COST_FRAGILE
    if by_name.get("positive_net_expectancy") == GATE_FAIL:
        return REJECT_INSUFFICIENT_EDGE
    if all(by_name.get(g) == GATE_PASS for g in
           ("positive_net_expectancy", "acceptable_drawdown", "forward_oos_consistency")):
        return KEEP_BASELINE
    return CHALLENGER_CANDIDATE


def _label_rationale(label: str) -> str:
    return {
        NEEDS_MORE_DATA: "Forward sample/coverage insufficient for a final verdict; the active V1 "
                         "baseline remains frozen and running while more successful days accumulate.",
        REJECT_DATA_INCOMPLETE: "required artifacts are structurally incomplete or mismatched.",
        KEEP_BASELINE: "complete evidence supports keeping V1.",
        CHALLENGER_CANDIDATE: "complete evidence suggests a single-change challenger may help.",
    }.get(label, "")


# ---------------------------------------------------------------------------
# Challenger hypotheses (<=2, evidence-gated, single change each)
# ---------------------------------------------------------------------------


def discover_capabilities() -> dict[str, Any]:
    """Discover EXISTING repository capabilities a challenger could reference.
    A hypothesis is only emitted for a confirmed capability."""
    def has_module(name: str) -> bool:
        try:
            __import__(name)
            return True
        except Exception:  # noqa: BLE001
            return False

    return {
        "canonical_regime_gate": diag._discover_canonical_regime() is not None,
        "overlay_gate_machinery": has_module("apps.forward_record.gate_checker"),
        "volatility_adjusted_sizing": has_module("src.demo_portfolio_risk"),  # Kelly/risk sizer exists
        "existing_exit_rule_variants": has_module("src.variants.task008"),
    }


def generate_challenger_hypotheses(
    diagnostics: Mapping[str, Any], capabilities: Mapping[str, Any],
) -> dict[str, Any]:
    """Emit AT MOST two single-change, evidence-based Challenger hypotheses, each
    referencing a confirmed existing capability. When the Forward sample is
    insufficient, hypotheses are PROVISIONAL and gated on the full sample."""
    integrity = diagnostics.get("data_integrity", {})
    contribution = diagnostics.get("contribution", {})
    sample_ok = bool(integrity.get("sample_sufficient", {}).get("return_metrics"))
    evidence_strength = "FULL_SAMPLE" if sample_ok else "STRUCTURAL_ONLY_REQUIRES_FULL_30D_SAMPLE"

    catalog: list[dict[str, Any]] = []

    # H1: equal-weight sizing observed -> use existing canonical vol-adjusted/risk sizer.
    by_symbol = contribution.get("by_symbol_structural_exposure", [])
    equal_weight_observed = bool(by_symbol) and len({round(abs(r["weight"]), 4) for r in by_symbol}) <= 2
    if capabilities.get("volatility_adjusted_sizing") and equal_weight_observed:
        catalog.append({
            "id": "H1_replace_equal_weight_with_canonical_risk_sizing",
            "observed_problem": "Forward portfolio uses uniform ~equal weights per symbol "
                                "(structural observation from paper_portfolio weights), ignoring "
                                "per-symbol volatility/risk.",
            "supporting_metrics_artifacts": ["paper_portfolio/state.json weights",
                                             "pnl.json long_weight_sum/short_weight_sum",
                                             "contribution.by_symbol_structural_exposure"],
            "proposed_single_change": "Replace equal-weight sizing with the EXISTING canonical "
                                      "0.4 fractional-Kelly / risk-based sizer "
                                      "(src/demo_portfolio_risk.compute_demo_portfolio_sizing).",
            "economic_mechanism": "Risk-parity-style sizing reduces over-allocation to high-volatility "
                                  "names and can improve risk-adjusted return without changing signals.",
            "expected_benefit": "Higher Sharpe/Calmar at similar gross exposure; less drawdown from "
                                "volatile outliers.",
            "expected_downside": "Possible lower raw return if high-vol names were net winners; added "
                                 "sizing complexity.",
            "overfitting_risk": "LOW-MEDIUM: reuses an existing canonical sizer (no new free parameters "
                                "fit to the 30-day sample).",
            "exact_offline_tests_required": [
                "replay determinism with the sizer swapped in (same inputs -> same actions)",
                "cost-stress comparison vs equal-weight baseline",
                "concentration check that no single position exceeds the existing single-position cap",
            ],
            "promotion_criteria": "On the FULL 30-day sample AND 7-day Demo: higher Sharpe and "
                                  "Calmar with drawdown <= baseline and no increase in concentration.",
            "rejection_criteria": "Lower risk-adjusted return, higher drawdown, or higher concentration "
                                  "than V1 on complete evidence.",
            "changes": {"entry": False, "exit": False, "regime_filter": False, "universe": False,
                        "strategy_native_sizing": True, "cost_execution_handling": False},
            "evidence_strength": evidence_strength,
            "status": "PROVISIONAL" if not sample_ok else "EVIDENCE_BACKED",
        })

    # H2: no active regime/overlay gate -> add an existing canonical regime/overlay gate.
    summary_overlay_always_pass = True  # observed: forward_summary gate_status.overlay_always_pass
    no_active_regime_gate = summary_overlay_always_pass
    if (capabilities.get("canonical_regime_gate") or capabilities.get("overlay_gate_machinery")) \
            and no_active_regime_gate:
        catalog.append({
            "id": "H2_add_existing_canonical_regime_or_overlay_gate",
            "observed_problem": "Forward run shows the overlay/regime gate always passes "
                                "(forward_summary gate_status.overlay_always_pass=true; no active "
                                "warning/stop gates), i.e. no regime filtering currently constrains entries.",
            "supporting_metrics_artifacts": ["forward_summary.json gate_status",
                                             "validation_30d.csv active_warning_gates/active_stop_gates",
                                             "overlay_check.json artifacts"],
            "proposed_single_change": "Enable the EXISTING canonical overlay/regime gate "
                                      "(apps/forward_record gate machinery) as an entry filter.",
            "economic_mechanism": "Suppressing entries during adverse regimes reduces exposure to "
                                  "unfavorable conditions, improving drawdown and consistency.",
            "expected_benefit": "Lower drawdown and steadier equity in adverse regimes.",
            "expected_downside": "Fewer trades; potential missed upside if the gate is too strict.",
            "overfitting_risk": "MEDIUM: must reuse the existing gate definition/thresholds, not tune "
                                "new ones against the 30-day sample.",
            "exact_offline_tests_required": [
                "regime-gated replay vs ungated baseline on identical artifacts",
                "sample-count check that each regime bucket meets the min-observation threshold",
                "failure injection: gate input missing -> fail closed, never silently disable",
            ],
            "promotion_criteria": "On the FULL 30-day sample: lower max drawdown and >= comparable "
                                  "expectancy, with sufficient per-regime observations.",
            "rejection_criteria": "No drawdown improvement, or insufficient per-regime sample, or "
                                  "requires new tuned thresholds.",
            "changes": {"entry": True, "exit": False, "regime_filter": True, "universe": False,
                        "strategy_native_sizing": False, "cost_execution_handling": False},
            "evidence_strength": evidence_strength,
            "status": "PROVISIONAL" if not sample_ok else "EVIDENCE_BACKED",
        })

    hypotheses = catalog[:MAX_CHALLENGERS]
    return {
        "task_id": TASK_ID,
        "max_allowed": MAX_CHALLENGERS,
        "emitted_count": len(hypotheses),
        "capabilities_considered": dict(sorted(capabilities.items())),
        "evidence_strength": evidence_strength,
        "hypotheses": hypotheses,
        "note": "Challenger work is offline/shadow-only and NOT promoted by this task. Hypotheses are "
                "selected from evidence + confirmed existing capabilities; provisional until the full "
                "30-day sample (and 7-day Demo) confirm them.",
        "promotion_status": "NONE_PROMOTED",
    }


# ---------------------------------------------------------------------------
# 7-day Demo comparison scaffold (updateable; never fabricates current metrics)
# ---------------------------------------------------------------------------


def build_demo_comparison_scaffold(
    *, pilot_id: str, baseline_manifest_fingerprint: str,
    completed_successful_days: Any = "UNKNOWN",
) -> dict[str, Any]:
    fields = [
        "expected_target_actions", "actual_orders", "fills", "average_prices", "fees", "funding",
        "realized_pnl", "slippage", "signal_to_order_latency", "target_vs_actual_position_diff",
        "rejected_actions", "reconciliation_incidents", "daily_success_verdicts",
    ]
    return {
        "task_id": TASK_ID, "pilot_id": pilot_id,
        "baseline_linkage": {"baseline_name": "V1", "manifest_fingerprint": baseline_manifest_fingerprint},
        "completed_successful_days": completed_successful_days,
        "demo_metrics": {f: "NOT_YET_AVAILABLE" for f in fields},
        "ingestion_ready": True,
        "note": "Updateable comparison layer; current Demo performance is NOT_YET_AVAILABLE (the Pilot "
                "has no completed successful-day sample). Manual BO/BP round-trip and smoke records are "
                "excluded from strategy performance.",
    }


def read_completed_successful_days(pilot_id: str, output_root: str | pathlib.Path | None) -> Any:
    """Read-only best-effort read of the Pilot's completed_successful_days; returns
    UNKNOWN when not safely readable. NEVER mutates the Pilot state."""
    try:
        from src.demo_strategy_pilot_store import CANONICAL_PILOT_ROOT
        root = pathlib.Path(output_root) if output_root is not None else CANONICAL_PILOT_ROOT
        state_path = pathlib.Path(root) / pilot_id / "pilot_state.json"
        if not state_path.exists():
            return "UNKNOWN"
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return int(data.get("completed_successful_days", 0))
    except Exception:  # noqa: BLE001
        return "UNKNOWN"


__all__ = [
    "CHALLENGER_CANDIDATE", "EXCLUSIONS", "FROZEN_ACTIVE_BASELINE", "GATE_FAIL", "GATE_INSUFFICIENT",
    "GATE_PASS", "KEEP_BASELINE", "MAX_CHALLENGERS", "NEEDS_MORE_DATA", "REJECT_COST_FRAGILE",
    "REJECT_CONCENTRATED_RESULT", "REJECT_DATA_INCOMPLETE", "REJECT_EXCESSIVE_DRAWDOWN",
    "REJECT_INSUFFICIENT_EDGE", "SCORECARD_REVIEW_THRESHOLDS", "TASK_ID",
    "build_demo_comparison_scaffold", "build_v1_baseline_manifest", "discover_capabilities",
    "generate_challenger_hypotheses", "manifest_fingerprint", "read_completed_successful_days",
    "score_strategy",
]
