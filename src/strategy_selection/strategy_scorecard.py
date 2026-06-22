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


EXPECTED_FORWARD_DAYS = 30

# Truthful baseline status when the local snapshot is incomplete (only the
# stable IDENTITY is frozen; the full-30 evidence has not been finalized).
FROZEN_BASELINE_IDENTITY_PENDING = "FROZEN_BASELINE_IDENTITY_PENDING_FULL30_ARTIFACT_FINALIZATION"


def build_v1_baseline_manifest(
    *,
    code_commit: str,
    pilot_id: str,
    diagnostics: Mapping[str, Any],
    policy_fingerprint: str = "",
) -> dict[str, Any]:
    """Build the versioned V1 baseline manifest. Separates the STABLE baseline
    identity (whose fingerprint is environment-independent) from the
    environment-specific local evidence snapshot. Read-only; never mutates the
    Pilot state. The local artifact set is NEVER claimed to be the completed
    30-day evidence unless the present-date coverage actually reaches 30."""
    integrity = diagnostics.get("data_integrity", {})
    present = int(integrity.get("present_date_count", 0))
    expected = int(integrity.get("expected_date_count", EXPECTED_FORWARD_DAYS) or EXPECTED_FORWARD_DAYS)
    full = present >= expected and present > 0

    baseline_identity = {
        "baseline_name": "V1",
        "strategy_id": diag.EXPECTED_STRATEGY_NAME,
        "source_run_key": diag.PRIMARY_RUN_KEY,
        "code_commit": code_commit,
        "pilot_id": pilot_id,
        "policy_configuration_fingerprint": policy_fingerprint,
        "expected_30d_validation_identity": {
            "run_key": diag.PRIMARY_RUN_KEY, "strategy_id": diag.EXPECTED_STRATEGY_NAME,
            "expected_date_count": EXPECTED_FORWARD_DAYS,
        },
        "exclusions": list(EXCLUSIONS),
    }
    local_evidence_snapshot = {
        "local_snapshot_status": diag.PARTIAL if not full else diag.PRESENT,
        "present_date_count": present,
        "expected_date_count": expected,
        "covered_dates": integrity.get("covered_dates", []),
        "artifact_fingerprints": dict(integrity.get("source_fingerprints", {})),
        "authoritative": bool(full),
        "note": ("local snapshot is INCOMPLETE and NON-AUTHORITATIVE; it is NOT the completed 30-day "
                 "evidence. Generate the authoritative full-30 manifest under the VPS runtime output "
                 "root." if not full else "full 30-day coverage present."),
    }
    manifest = {
        "task_id": TASK_ID,
        "baseline_identity": baseline_identity,
        "local_evidence_snapshot": local_evidence_snapshot,
        "status": FROZEN_ACTIVE_BASELINE if full else FROZEN_BASELINE_IDENTITY_PENDING,
        "notes": "Active V1 strategy logic is FROZEN and UNCHANGED; this manifest only identifies and "
                 "fingerprints the baseline IDENTITY. The running Pilot state was not mutated. The "
                 "identity fingerprint is environment-independent; local evidence is recorded separately.",
    }
    manifest["manifest_fingerprint"] = manifest_fingerprint(manifest)
    return manifest


def manifest_fingerprint(manifest: Mapping[str, Any]) -> str:
    """Fingerprint over the STABLE baseline identity only (environment-independent;
    excludes the local evidence snapshot and the fingerprint field itself)."""
    payload = manifest.get("baseline_identity", {})
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


def evidence_is_sufficient_for_challenger_selection(diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    """A Challenger hypothesis may be SELECTED only after the full dataset passes
    expected-date coverage, artifact consistency, the minimum-sample gate, and
    comparable primary/shadow evidence."""
    integrity = diagnostics.get("data_integrity", {})
    primary_shadow = diagnostics.get("primary_shadow", {})
    present = int(integrity.get("present_date_count", 0))
    expected = int(integrity.get("expected_date_count", EXPECTED_FORWARD_DAYS) or EXPECTED_FORWARD_DAYS)
    coverage_ok = present >= expected and present > 0
    sample_ok = bool(integrity.get("sample_sufficient", {}).get("return_metrics"))
    consistency_ok = (not integrity.get("stale_summary", False)
                      and integrity.get("strategy_id_matches_expected", True)
                      and not integrity.get("duplicate_dates"))
    comparable = primary_shadow.get("ranking_status") == "RANKED"
    sufficient = coverage_ok and sample_ok and consistency_ok and comparable
    return {
        "sufficient": sufficient, "coverage_ok": coverage_ok, "min_sample_ok": sample_ok,
        "artifact_consistency_ok": consistency_ok, "comparable_primary_shadow": comparable,
        "present_date_count": present, "expected_date_count": expected,
    }


def generate_challenger_hypotheses(
    diagnostics: Mapping[str, Any], capabilities: Mapping[str, Any],
) -> dict[str, Any]:
    """Emit AT MOST two single-change, evidence-based Challenger hypotheses ONLY
    when the full dataset passes the evidence gate. When evidence is insufficient
    (e.g. the local 2/30 day-0 snapshot) emit ZERO challengers and record purely
    structural observations under ``future_research_candidates`` -- they are NOT
    presented as selected hypotheses. Kelly sizing / overlay gates are never
    preselected without full evidence, and an overlay gate is never labelled a
    regime hypothesis unless a canonical regime definition exists."""
    gate = evidence_is_sufficient_for_challenger_selection(diagnostics)
    contribution = diagnostics.get("contribution", {})
    by_symbol = contribution.get("by_symbol_structural_exposure", [])
    equal_weight_observed = bool(by_symbol) and len({round(abs(r["weight"]), 4) for r in by_symbol}) <= 2

    # Structural observations (deferred research; never selected without full evidence).
    future_research_candidates: list[dict[str, Any]] = []
    if equal_weight_observed and capabilities.get("volatility_adjusted_sizing"):
        future_research_candidates.append({
            "id": "FRC_equal_weight_vs_risk_sizing",
            "structural_observation": "Forward portfolio uses uniform ~equal target weights "
                                      "(structural; from paper_portfolio weights).",
            "candidate_single_change": "OFFLINE/SHADOW only: compare equal-weight vs the existing "
                                       "canonical risk sizer (src/demo_portfolio_risk).",
            "requires": "full 30-day VPS dataset + comparable primary/shadow evidence before selection",
            "dimension": "strategy_native_sizing",
        })
    overlay_only = capabilities.get("overlay_gate_machinery") and not capabilities.get("canonical_regime_gate")
    if capabilities.get("overlay_gate_machinery") or capabilities.get("canonical_regime_gate"):
        future_research_candidates.append({
            "id": "FRC_overlay_gate" if overlay_only else "FRC_regime_gate",
            "structural_observation": "Forward overlay gate always passes (no active warning/stop "
                                      "gates); no overlay/regime filtering currently constrains entries.",
            "candidate_single_change": ("OFFLINE/SHADOW only: evaluate the existing canonical OVERLAY "
                                        "gate as an entry filter." if overlay_only else
                                        "OFFLINE/SHADOW only: evaluate the existing canonical REGIME gate."),
            "label_note": ("labelled OVERLAY gate, NOT a regime hypothesis -- no canonical regime "
                           "definition exists in the repository." if overlay_only else
                           "canonical regime definition present."),
            "requires": "full 30-day VPS dataset + sufficient per-bucket sample before selection",
            "dimension": "regime_filter" if not overlay_only else "entry_overlay_filter",
        })

    if not gate["sufficient"]:
        return {
            "task_id": TASK_ID, "max_allowed": MAX_CHALLENGERS, "emitted_count": 0,
            "hypotheses": [],
            "evidence_gate": gate,
            "evidence_strength": "INSUFFICIENT_SAMPLE_NO_SELECTION",
            "future_research_candidates": future_research_candidates,
            "capabilities_considered": dict(sorted(capabilities.items())),
            "promotion_status": "NONE_PROMOTED",
            "note": "Evidence insufficient for Challenger selection (local snapshot is incomplete / "
                    "day-0 / not comparable). Zero challengers emitted; structural observations are "
                    "recorded as future_research_candidates only, NOT as selected hypotheses. "
                    "Challengers may be selected only after the full 30-day VPS analysis passes the gate.",
        }

    # --- Full evidence available: emit <=2 evidence-backed single-change hypotheses ---
    catalog: list[dict[str, Any]] = []
    if equal_weight_observed and capabilities.get("volatility_adjusted_sizing"):
        catalog.append({
            "id": "H1_replace_equal_weight_with_canonical_risk_sizing",
            "observed_problem": "Equal-weight target sizing ignores per-symbol volatility/risk.",
            "supporting_metrics_artifacts": ["paper_portfolio/state.json weights",
                                             "pnl.json long_weight_sum/short_weight_sum",
                                             "overall_metrics canonical Sharpe/Calmar/max_dd"],
            "proposed_single_change": "OFFLINE/SHADOW: replace equal-weight target sizing with the "
                                      "EXISTING canonical risk sizer (src/demo_portfolio_risk).",
            "economic_mechanism": "Risk-parity-style sizing reduces over-allocation to volatile names.",
            "expected_benefit": "Higher risk-adjusted return / lower drawdown.",
            "expected_downside": "Possible lower raw return; added complexity.",
            "overfitting_risk": "LOW-MEDIUM (reuses an existing sizer; no new fitted parameters).",
            "exact_offline_tests_required": ["replay determinism with sizer swapped",
                                             "cost-stress vs equal-weight", "concentration cap check"],
            "promotion_criteria": "Full 30-day + 7-day Demo: higher Sharpe/Calmar, drawdown <= baseline, "
                                  "no concentration increase.",
            "rejection_criteria": "Worse risk-adjusted return / higher drawdown / higher concentration.",
            "changes": {"entry": False, "exit": False, "regime_filter": False, "universe": False,
                        "strategy_native_sizing": True, "cost_execution_handling": False},
            "evidence_strength": "FULL_SAMPLE", "status": "EVIDENCE_BACKED",
        })
    if overlay_only or capabilities.get("canonical_regime_gate"):
        is_regime = bool(capabilities.get("canonical_regime_gate"))
        catalog.append({
            "id": "H2_enable_existing_canonical_regime_gate" if is_regime
                  else "H2_enable_existing_canonical_overlay_gate",
            "observed_problem": "No overlay/regime filtering currently constrains entries.",
            "supporting_metrics_artifacts": ["forward_summary.json gate_status",
                                             "validation_30d.csv gate columns", "overlay_check.json"],
            "proposed_single_change": ("OFFLINE/SHADOW: enable the EXISTING canonical "
                                       + ("REGIME" if is_regime else "OVERLAY")
                                       + " gate as an entry filter."),
            "economic_mechanism": "Suppress entries in adverse conditions to reduce drawdown.",
            "expected_benefit": "Lower drawdown / steadier equity.",
            "expected_downside": "Fewer trades; possible missed upside.",
            "overfitting_risk": "MEDIUM (reuse existing thresholds; do not tune new ones).",
            "exact_offline_tests_required": ["gated vs ungated replay on identical artifacts",
                                             "per-bucket min-sample check", "missing-gate-input fail-closed"],
            "promotion_criteria": "Full 30-day: lower max drawdown, >= comparable expectancy, sufficient "
                                  "per-bucket sample.",
            "rejection_criteria": "No drawdown improvement / insufficient bucket sample / new tuned thresholds.",
            "changes": {"entry": True, "exit": False, "regime_filter": is_regime, "universe": False,
                        "strategy_native_sizing": False, "cost_execution_handling": False,
                        "entry_overlay_filter": not is_regime},
            "label_note": ("canonical regime definition present" if is_regime
                           else "labelled OVERLAY gate, NOT a regime hypothesis (no canonical regime def)"),
            "evidence_strength": "FULL_SAMPLE", "status": "EVIDENCE_BACKED",
        })

    hypotheses = catalog[:MAX_CHALLENGERS]
    return {
        "task_id": TASK_ID, "max_allowed": MAX_CHALLENGERS, "emitted_count": len(hypotheses),
        "hypotheses": hypotheses, "evidence_gate": gate, "evidence_strength": "FULL_SAMPLE",
        "future_research_candidates": [], "capabilities_considered": dict(sorted(capabilities.items())),
        "promotion_status": "NONE_PROMOTED",
        "note": "Challenger work is offline/shadow-only and NOT promoted by this task.",
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
    "CHALLENGER_CANDIDATE", "EXCLUSIONS", "EXPECTED_FORWARD_DAYS", "FROZEN_ACTIVE_BASELINE",
    "FROZEN_BASELINE_IDENTITY_PENDING", "GATE_FAIL", "GATE_INSUFFICIENT",
    "GATE_PASS", "KEEP_BASELINE", "MAX_CHALLENGERS", "NEEDS_MORE_DATA", "REJECT_COST_FRAGILE",
    "REJECT_CONCENTRATED_RESULT", "REJECT_DATA_INCOMPLETE", "REJECT_EXCESSIVE_DRAWDOWN",
    "REJECT_INSUFFICIENT_EDGE", "SCORECARD_REVIEW_THRESHOLDS", "TASK_ID",
    "build_demo_comparison_scaffold", "build_v1_baseline_manifest", "discover_capabilities",
    "evidence_is_sufficient_for_challenger_selection", "generate_challenger_hypotheses",
    "manifest_fingerprint", "read_completed_successful_days", "score_strategy",
]
