"""
Stage 1 focused-core tests for TASK-014BB

src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.py

These tests prove that the BB src is internally coherent: identity
constants, the 36 hard-fail gate constants, the result dataclass
default safety invariants, the BA artifact loader, and the run-function
gate evaluation logic.  The full 40+ test pack (CLI subprocess tests,
on-disk JSON/MD inspection, identity-wording grep tests, all the
BA-content-grep negative-proof tests) is Stage 3 and is intentionally
NOT included here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review import (
    ADAPTER_CONTRACT_VERSION,
    ADAPTER_NAME,
    AUTHORIZATION_RESULT_DOCUMENTED,
    CONCLUSION_READY_NOT_EXECUTABLE,
    GATE_BA_ARTIFACT_MISSING,
    GATE_BA_REAL_EXECUTION_ALLOWED_TRUE,
    GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AY,
    GATE_BA_SCOPE_SUMMARY_MISSING_AZ_DIRECT,
    GATE_BA_STATUS_FAIL_CLOSED,
    IDENTITY_CHECKLIST,
    IDENTITY_STRICT,
    MODE_CHECKLIST,
    MODE_FAIL_CLOSED,
    NEXT_REQUIRED_TASK,
    RESPONSE_STATUS_NOT_SENT,
    SCOPE_SUMMARY_LITERAL,
    STATUS_FAIL_CLOSED,
    STATUS_READY,
    STATUS_READY_BUT_EXECUTION_DISABLED,
    TinyGuardedEntryRealExecutionAdapterDisabledImplementationScaffoldManualAuthorizationGateFinalPreExecutionReviewManualAuthorizationReviewResult as BBResult,
    _HARD_FAIL_GATES,
    _load_ba_final_pre_execution_review_artifact,
    run_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review as run,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_ba_artifact() -> dict[str, Any]:
    """
    A synthetic BA artifact dict that mirrors the TASK-014BA emitted
    JSON contract closely enough to satisfy every Group A / Group B /
    Group C gate (i.e. so that no hard-fail gate triggers).
    """
    scope_summary = (
        "TASK-014BA consumes TASK-014AZ DISABLED IMPLEMENTATION "
        "SCAFFOLD MANUAL AUTHORIZATION GATE READINESS REVIEW output "
        "at runtime plus AZ-proven chained proof, including AY "
        "dry-run, AX manual authorization gate design, AW final "
        "pre-execution review, AV readiness review, AU dry-run, AT "
        "design, AS static skeleton dry-run, AR static skeleton "
        "design, and AQ implementation design."
    )
    return {
        "status": (
            "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_"
            "IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_"
            "PRE_EXECUTION_REVIEW_READY"
        ),
        "mode": (
            "disabled_implementation_scaffold_manual_authorization_"
            "gate_final_pre_execution_review_checklist"
        ),
        "selected_symbol": "SOLUSDT",
        "adapter_name": "GuardedTinyEntryRealExecutionAdapter",
        "adapter_contract_version": (
            "disabled_implementation_scaffold_manual_authorization_"
            "gate_final_pre_execution_review_v1"
        ),
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_conclusion": (
            "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_"
            "GATE_FINAL_PRE_EXECUTION_REVIEW_READY_NOT_EXECUTABLE"
        ),
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_authorization_result": (
            "DOCUMENTED_ONLY_NOT_AUTHORIZED"
        ),
        "response_status": (
            "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_"
            "GATE_FINAL_PRE_EXECUTION_REVIEW_NOT_SENT"
        ),
        "next_required_task": (
            "TASK-014BB_guarded_entry_real_execution_adapter_"
            "disabled_implementation_scaffold_manual_authorization_"
            "gate_final_pre_execution_review_manual_authorization_review"
        ),
        "failed_stage": "",
        "blocked_gates": [],
        "real_execution_allowed": False,
        "send_allowed": False,
        "adapter_implementation_included": False,
        "adapter_execution_included": False,
        "order_endpoint_called": False,
        "stop_endpoint_called": False,
        "no_position_modified": True,
        "no_secrets_loaded": True,
        "g20_lifted": False,
        # BA's stage_1 scope dict
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope": {
            "scope_summary": scope_summary,
        },
        "implementation_design_scope": {
            "scope_summary": scope_summary,
        },
        # AZ chained proof BA itself emits
        "consumed_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_contract_version": (
            "disabled_implementation_scaffold_manual_authorization_"
            "gate_readiness_review_v1"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_status": (
            "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_"
            "IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_"
            "READINESS_REVIEW_READY"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_response_status": (
            "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_"
            "GATE_READINESS_REVIEW_NOT_SENT"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_next_required_task": (
            "TASK-014BA_guarded_entry_real_execution_adapter_"
            "disabled_implementation_scaffold_manual_authorization_"
            "gate_final_pre_execution_review"
        ),
        # AY status carried through AZ chain
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run_status": (
            "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_"
            "IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DRY_RUN_READY"
        ),
    }


# ---------------------------------------------------------------------------
# Stage 1 core tests
# ---------------------------------------------------------------------------

def test_run_with_valid_synthetic_ba_artifact_returns_READY(valid_ba_artifact: dict[str, Any]) -> None:
    result = run(ba_artifact=valid_ba_artifact)
    assert result.status == STATUS_READY, (
        f"Expected STATUS_READY but got {result.status!r}; "
        f"blocked_gates={result.blocked_gates}"
    )
    assert result.mode == MODE_CHECKLIST
    assert result.blocked_gates == []
    assert result.failed_stage == ""


def test_default_dataclass_safety_invariants_hold() -> None:
    """A freshly-instantiated BB result must hold every safety invariant."""
    r = BBResult()
    # Live-action invariants
    assert r.real_execution_allowed is False
    assert r.current_task_real_execution_allowed is False
    assert r.send_allowed is False
    assert r.order_endpoint_called is False
    assert r.stop_endpoint_called is False
    assert r.no_orders_sent is True
    assert r.no_position_modified is True
    assert r.no_live_endpoint is True
    assert r.no_secrets_loaded is True
    assert r.secret_value_observed is False
    assert r.g20_policy_still_in_place is True
    assert r.g20_lifted is False
    # Adapter-surface invariants
    assert r.executable_adapter_included is False
    assert r.adapter_implementation_included is False
    assert r.adapter_execution_included is False
    assert r.send_method_included is False
    assert r.place_order_method_included is False
    assert r.execute_method_included is False
    assert r.real_entry_implemented is False
    assert r.manual_authorization_review_only is True
    assert r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_only is True
    # Authorization-grants invariants
    assert r.manual_authorization_review_grants_execution is False
    assert r.manual_authorization_gate_final_pre_execution_review_grants_execution is False
    assert r.readiness_review_grants_execution is False
    assert r.dry_run_grants_execution is False
    assert r.adapter_grants_execution is False
    # Approval-input invariants
    assert r.approval_phrase_grants_execution is False
    assert r.approval_token_grants_execution is False
    assert r.approval_inputs_grant_execution is False
    assert r.token_to_authorization_mapping is False
    assert r.phrase_to_authorization_mapping is False
    assert r.manual_authorization_review_accepts_runtime_approval is False
    assert r.manual_authorization_review_translates_text_to_execution is False
    # Identity / verdict
    assert r.adapter_name == ADAPTER_NAME
    assert r.adapter_contract_version == ADAPTER_CONTRACT_VERSION
    assert r.response_status == RESPONSE_STATUS_NOT_SENT
    assert r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_conclusion == CONCLUSION_READY_NOT_EXECUTABLE
    assert r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_authorization_result == AUTHORIZATION_RESULT_DOCUMENTED
    assert r.next_required_task == NEXT_REQUIRED_TASK
    assert r.existing_positions_touched == []


def test_identity_strict_literal_exact_match() -> None:
    expected = (
        "STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-"
        "GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-"
        "ONLY"
    )
    assert IDENTITY_STRICT == expected
    # Also verify the checklist literal.
    assert IDENTITY_CHECKLIST == (
        "DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE "
        "FINAL PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW "
        "CHECKLIST"
    )


def test_scope_summary_literal_exact_match() -> None:
    expected = (
        "TASK-014BB consumes TASK-014BA DISABLED IMPLEMENTATION SCAFFOLD "
        "MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW output at "
        "runtime plus BA-proven chained proof, including AZ readiness "
        "review, AY dry-run, AX manual authorization gate design, AW final "
        "pre-execution review, AV readiness review, AU dry-run, AT design, "
        "AS static skeleton dry-run, AR static skeleton design, and AQ "
        "implementation design."
    )
    assert SCOPE_SUMMARY_LITERAL == expected


def test_hard_fail_gates_frozenset_contains_all_36() -> None:
    assert isinstance(_HARD_FAIL_GATES, frozenset)
    assert len(_HARD_FAIL_GATES) == 36


def test_missing_ba_artifact_triggers_GATE_BA_ARTIFACT_MISSING_and_FAIL_CLOSED(tmp_path: Path) -> None:
    # No artifact provided at all -> loader is never called, but the
    # run-function still sets artifact=None and triggers the gate.
    result = run()
    assert GATE_BA_ARTIFACT_MISSING in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED
    assert result.mode == MODE_FAIL_CLOSED
    assert result.failed_stage != ""

    # Also: explicit path that doesn't exist.
    missing = tmp_path / "nope.json"
    result2 = run(ba_artifact_path=missing)
    assert GATE_BA_ARTIFACT_MISSING in result2.blocked_gates
    assert result2.status == STATUS_FAIL_CLOSED


def test_ba_status_FAIL_CLOSED_triggers_passthrough_FAIL_CLOSED(valid_ba_artifact: dict[str, Any]) -> None:
    valid_ba_artifact["status"] = STATUS_FAIL_CLOSED
    valid_ba_artifact["mode"] = MODE_FAIL_CLOSED
    valid_ba_artifact["failed_stage"] = "stage_X_synthetic_failure"
    result = run(ba_artifact=valid_ba_artifact)
    assert GATE_BA_STATUS_FAIL_CLOSED in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED
    assert result.mode == MODE_FAIL_CLOSED


def test_ba_scope_summary_contains_ba_consumes_ay_triggers_FAIL_CLOSED(valid_ba_artifact: dict[str, Any]) -> None:
    # Inject a forbidden "TASK-014BA consumes TASK-014AY" phrase into BA's
    # scope_summary.  This must trigger Group B gate 20.
    bad_summary = valid_ba_artifact["disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope"]["scope_summary"]
    bad_summary += " TASK-014BA consumes TASK-014AY"
    valid_ba_artifact["disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope"]["scope_summary"] = bad_summary
    valid_ba_artifact["implementation_design_scope"]["scope_summary"] = bad_summary
    result = run(ba_artifact=valid_ba_artifact)
    assert GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AY in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_ba_scope_summary_missing_az_direct_triggers_FAIL_CLOSED(valid_ba_artifact: dict[str, Any]) -> None:
    valid_ba_artifact["disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope"]["scope_summary"] = (
        "some unrelated summary text without the required direct-upstream phrase"
    )
    valid_ba_artifact["implementation_design_scope"]["scope_summary"] = (
        "some unrelated summary text without the required direct-upstream phrase"
    )
    result = run(ba_artifact=valid_ba_artifact)
    assert GATE_BA_SCOPE_SUMMARY_MISSING_AZ_DIRECT in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_ba_real_execution_allowed_True_triggers_FAIL_CLOSED(valid_ba_artifact: dict[str, Any]) -> None:
    valid_ba_artifact["real_execution_allowed"] = True
    result = run(ba_artifact=valid_ba_artifact)
    assert GATE_BA_REAL_EXECUTION_ALLOWED_TRUE in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_allow_flag_returns_READY_BUT_EXECUTION_DISABLED_with_no_execution(valid_ba_artifact: dict[str, Any]) -> None:
    result = run(
        ba_artifact=valid_ba_artifact,
        allow_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review=True,
    )
    assert result.status == STATUS_READY_BUT_EXECUTION_DISABLED
    # No execution-side flag may have flipped.
    assert result.real_execution_allowed is False
    assert result.send_allowed is False
    assert result.no_orders_sent is True
    assert result.order_endpoint_called is False
    assert result.stop_endpoint_called is False
    assert result.no_position_modified is True
    assert result.g20_lifted is False
    assert result.executable_adapter_included is False
    assert result.adapter_implementation_included is False
    assert result.adapter_execution_included is False
    assert result.send_method_included is False
    assert result.place_order_method_included is False
    assert result.execute_method_included is False
    assert result.manual_authorization_review_grants_execution is False


def test_to_dict_exposes_all_result_fields(valid_ba_artifact: dict[str, Any]) -> None:
    result = run(ba_artifact=valid_ba_artifact)
    d = result.to_dict()
    # Spot-check required keys are present.
    for key in (
        "status", "mode", "selected_symbol", "adapter_name",
        "adapter_contract_version", "response_status", "next_required_task",
        "failed_stage", "blocked_gates", "scope_summary",
        "identity_checklist", "identity_strict",
        "manual_authorization_review_only",
        "executable_adapter_included",
        "real_execution_allowed", "send_allowed", "no_orders_sent",
        "no_position_modified", "g20_lifted",
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_conclusion",
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_authorization_result",
        # BA upstream
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary",
        # AZ chained proof
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_mentions_az_direct_upstream",
    ):
        assert key in d, f"Missing key in to_dict() output: {key!r}"
    # to_dict must be JSON-serializable.
    json.dumps(d)


def test_load_ba_artifact_roundtrip(tmp_path: Path, valid_ba_artifact: dict[str, Any]) -> None:
    """The loader returns the same dict when given a valid JSON file."""
    f = tmp_path / "ba.json"
    f.write_text(json.dumps(valid_ba_artifact), encoding="utf-8")
    loaded = _load_ba_final_pre_execution_review_artifact(f)
    assert loaded is not None
    assert loaded["status"] == valid_ba_artifact["status"]
    # Missing file
    missing = tmp_path / "nope.json"
    assert _load_ba_final_pre_execution_review_artifact(missing) is None
    # Invalid JSON
    bad = tmp_path / "bad.json"
    bad.write_text("not json {", encoding="utf-8")
    assert _load_ba_final_pre_execution_review_artifact(bad) is None
