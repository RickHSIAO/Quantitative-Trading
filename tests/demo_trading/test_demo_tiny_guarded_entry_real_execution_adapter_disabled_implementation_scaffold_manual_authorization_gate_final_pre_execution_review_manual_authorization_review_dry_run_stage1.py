"""
Stage 1 focused-core tests for TASK-014BC

src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run.py

These tests prove that the BC src is internally coherent: identity
constants, the 36 hard-fail gate constants, the result dataclass
default safety invariants, the BB artifact loader, and the run-function
gate evaluation logic.  The full 40+ test pack (CLI subprocess tests,
on-disk JSON/MD inspection, identity-wording grep tests, all the
BB-content-grep negative-proof tests) is Stage 3 and is intentionally
NOT included here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run import (
    ADAPTER_CONTRACT_VERSION,
    ADAPTER_NAME,
    AUTHORIZATION_RESULT_DOCUMENTED_ONLY,
    CONCLUSION_READY_NOT_EXECUTABLE,
    GATE_BB_ARTIFACT_MISSING,
    GATE_BB_NEXT_REQUIRED_TASK_MISMATCH,
    GATE_BB_REAL_EXECUTION_ALLOWED_TRUE,
    GATE_BB_SCOPE_SUMMARY_HAS_BB_CONSUMES_AZ,
    GATE_BB_STATUS_FAIL_CLOSED,
    IDENTITY_CHECKLIST,
    IDENTITY_STRICT,
    MODE_CHECKLIST,
    MODE_FAIL_CLOSED,
    NEXT_REQUIRED_TASK,
    RESPONSE_STATUS_NOT_SENT,
    SCOPE_SUMMARY_LITERAL,
    STATUS_BB_READY,
    STATUS_FAIL_CLOSED,
    STATUS_READY,
    STATUS_READY_BUT_EXECUTION_DISABLED,
    STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED,
    TinyGuardedEntryRealExecutionAdapterDisabledImplementationScaffoldManualAuthorizationGateFinalPreExecutionReviewManualAuthorizationReviewDryRunResult as BCResult,
    _HARD_FAIL_GATES,
    _load_bb_manual_authorization_review_artifact,
    run_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run as run,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _valid_bb_artifact() -> dict[str, Any]:
    """
    A synthetic BB artifact dict that mirrors the TASK-014BB emitted
    JSON contract closely enough to satisfy every Group A / Group B /
    Group C gate (i.e. so that no hard-fail gate triggers).
    """
    bb_scope_summary = (
        "TASK-014BB consumes TASK-014BA DISABLED IMPLEMENTATION SCAFFOLD "
        "MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW output at "
        "runtime plus BA-proven chained proof, including AZ readiness "
        "review, AY dry-run, AX manual authorization gate design, AW final "
        "pre-execution review, AV readiness review, AU dry-run, AT design, "
        "AS static skeleton dry-run, AR static skeleton design, and AQ "
        "implementation design."
    )
    ba_scope_summary = (
        "TASK-014BA consumes TASK-014AZ DISABLED IMPLEMENTATION SCAFFOLD "
        "MANUAL AUTHORIZATION GATE READINESS REVIEW output at runtime plus "
        "AZ-proven chained proof, including AY dry-run, AX manual "
        "authorization gate design, AW final pre-execution review, AV "
        "readiness review, AU dry-run, AT design, AS static skeleton "
        "dry-run, AR static skeleton design, and AQ implementation design."
    )
    return {
        # BB top-level
        "status": STATUS_BB_READY,
        "mode": (
            "disabled_implementation_scaffold_manual_authorization_gate_"
            "final_pre_execution_review_manual_authorization_review_checklist"
        ),
        "selected_symbol": "SOLUSDT",
        "adapter_name": "GuardedTinyEntryRealExecutionAdapter",
        "adapter_contract_version": (
            "disabled_implementation_scaffold_manual_authorization_gate_"
            "final_pre_execution_review_manual_authorization_review_v1"
        ),
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_conclusion": (
            "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_"
            "FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_READY_"
            "NOT_EXECUTABLE"
        ),
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_authorization_result": (
            "DOCUMENTED_ONLY_NOT_AUTHORIZED"
        ),
        "response_status": (
            "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_"
            "FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_NOT_SENT"
        ),
        "next_required_task": (
            "TASK-014BC_guarded_entry_real_execution_adapter_disabled_"
            "implementation_scaffold_manual_authorization_gate_final_pre_"
            "execution_review_manual_authorization_review_dry_run"
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
        "scope_summary": bb_scope_summary,
        # BB->BA chained proof (BA-side fields BB emits)
        "consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_contract_version": (
            "disabled_implementation_scaffold_manual_authorization_gate_"
            "final_pre_execution_review_v1"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_status": (
            "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_"
            "IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_"
            "PRE_EXECUTION_REVIEW_READY"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_next_required_task": (
            "TASK-014BB_guarded_entry_real_execution_adapter_disabled_"
            "implementation_scaffold_manual_authorization_gate_final_pre_"
            "execution_review_manual_authorization_review"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary": ba_scope_summary,
    }


@pytest.fixture
def valid_bb_artifact() -> dict[str, Any]:
    return _valid_bb_artifact()


# ---------------------------------------------------------------------------
# Stage 1 core tests
# ---------------------------------------------------------------------------

def test_run_with_valid_synthetic_bb_artifact_returns_READY(valid_bb_artifact: dict[str, Any]) -> None:
    result = run(bb_artifact=valid_bb_artifact)
    assert result.status == STATUS_READY, (
        f"Expected STATUS_READY but got {result.status!r}; "
        f"blocked_gates={result.blocked_gates}"
    )
    assert result.mode == MODE_CHECKLIST
    assert result.blocked_gates == []
    assert result.failed_stage == ""


def test_default_dataclass_safety_invariants_hold() -> None:
    """A freshly-instantiated BC result must hold every safety invariant."""
    r = BCResult()
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
    assert r.manual_authorization_review_dry_run_only is True
    assert r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_only is True
    # Authorization-grants invariants
    assert r.manual_authorization_review_dry_run_grants_execution is False
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
    assert r.manual_authorization_review_dry_run_accepts_runtime_approval is False
    assert r.manual_authorization_review_dry_run_translates_text_to_execution is False
    # Identity / verdict
    assert r.adapter_name == ADAPTER_NAME
    assert r.adapter_contract_version == ADAPTER_CONTRACT_VERSION
    assert r.response_status == RESPONSE_STATUS_NOT_SENT
    assert r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_conclusion == CONCLUSION_READY_NOT_EXECUTABLE
    assert r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_authorization_result == AUTHORIZATION_RESULT_DOCUMENTED_ONLY
    assert r.next_required_task == NEXT_REQUIRED_TASK
    assert r.existing_positions_touched == []


def test_identity_strict_literal_exact_match() -> None:
    expected_strict = (
        "STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-"
        "GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-"
        "DRY-RUN-ONLY"
    )
    assert IDENTITY_STRICT == expected_strict
    assert IDENTITY_CHECKLIST == (
        "DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL "
        "PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW DRY-RUN "
        "CHECKLIST"
    )


def test_scope_summary_literal_exact_match() -> None:
    expected = (
        "TASK-014BC consumes TASK-014BB DISABLED IMPLEMENTATION SCAFFOLD "
        "MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW MANUAL "
        "AUTHORIZATION REVIEW output at runtime plus BB-proven chained "
        "proof, including BA final pre-execution review, AZ readiness "
        "review, AY dry-run, AX manual authorization gate design, AW final "
        "pre-execution review, AV readiness review, AU dry-run, AT design, "
        "AS static skeleton dry-run, AR static skeleton design, and AQ "
        "implementation design."
    )
    assert SCOPE_SUMMARY_LITERAL == expected


def test_hard_fail_gates_frozenset_contains_exactly_36() -> None:
    assert isinstance(_HARD_FAIL_GATES, frozenset)
    assert len(_HARD_FAIL_GATES) == 36


def test_missing_bb_artifact_triggers_GATE_BB_ARTIFACT_MISSING_and_FAIL_CLOSED(tmp_path: Path) -> None:
    # No artifact provided at all -> the run-function still sets
    # artifact=None and triggers the gate.
    result = run()
    assert GATE_BB_ARTIFACT_MISSING in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED
    assert result.mode == MODE_FAIL_CLOSED
    assert result.failed_stage != ""

    # Also: explicit path that doesn't exist.
    missing = tmp_path / "nope.json"
    result2 = run(bb_artifact_path=missing)
    assert GATE_BB_ARTIFACT_MISSING in result2.blocked_gates
    assert result2.status == STATUS_FAIL_CLOSED


def test_bb_status_FAIL_CLOSED_triggers_passthrough_FAIL_CLOSED(valid_bb_artifact: dict[str, Any]) -> None:
    bad = dict(valid_bb_artifact) | {
        "status": STATUS_FAIL_CLOSED,
        "mode": MODE_FAIL_CLOSED,
        "failed_stage": "stage_X_synthetic_failure",
    }
    result = run(bb_artifact=bad)
    assert GATE_BB_STATUS_FAIL_CLOSED in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED
    assert result.mode == MODE_FAIL_CLOSED


def test_bb_scope_summary_contains_bb_consumes_az_triggers_FAIL_CLOSED(valid_bb_artifact: dict[str, Any]) -> None:
    bad_summary = (
        valid_bb_artifact["scope_summary"]
        + " TASK-014BB consumes TASK-014AZ directly"
    )
    bad = dict(valid_bb_artifact) | {"scope_summary": bad_summary}
    result = run(bb_artifact=bad)
    assert GATE_BB_SCOPE_SUMMARY_HAS_BB_CONSUMES_AZ in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_bb_real_execution_allowed_True_triggers_FAIL_CLOSED(valid_bb_artifact: dict[str, Any]) -> None:
    bad = dict(valid_bb_artifact) | {"real_execution_allowed": True}
    result = run(bb_artifact=bad)
    assert GATE_BB_REAL_EXECUTION_ALLOWED_TRUE in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_bb_next_required_task_wrong_value_triggers_FAIL_CLOSED(valid_bb_artifact: dict[str, Any]) -> None:
    bad = dict(valid_bb_artifact) | {"next_required_task": "TASK-014WRONG"}
    result = run(bb_artifact=bad)
    assert GATE_BB_NEXT_REQUIRED_TASK_MISMATCH in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_allow_flag_returns_READY_BUT_EXECUTION_DISABLED_with_no_execution(valid_bb_artifact: dict[str, Any]) -> None:
    result = run(
        bb_artifact=valid_bb_artifact,
        allow_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run=True,
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
    assert result.manual_authorization_review_dry_run_grants_execution is False


def test_allow_real_entry_execution_flag_returns_NOT_IMPLEMENTED(valid_bb_artifact: dict[str, Any]) -> None:
    result = run(
        bb_artifact=valid_bb_artifact,
        allow_real_entry_execution=True,
    )
    assert result.status == STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
    # Invariants still hold.
    assert result.real_execution_allowed is False
    assert result.send_allowed is False
    assert result.no_orders_sent is True
    assert result.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_conclusion == CONCLUSION_READY_NOT_EXECUTABLE


def test_to_dict_round_trip_completeness(valid_bb_artifact: dict[str, Any]) -> None:
    result = run(bb_artifact=valid_bb_artifact)
    d = result.to_dict()
    # Spot-check required keys are present.
    for key in (
        "status", "mode", "selected_symbol", "adapter_name",
        "adapter_contract_version", "response_status", "next_required_task",
        "failed_stage", "blocked_gates", "scope_summary",
        "identity_checklist", "identity_strict",
        "manual_authorization_review_dry_run_only",
        "executable_adapter_included",
        "real_execution_allowed", "send_allowed", "no_orders_sent",
        "no_position_modified", "g20_lifted",
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_conclusion",
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_authorization_result",
        # BB upstream
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_scope_summary",
        # BB->BA chained proof
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_scope_summary_mentions_ba_direct_upstream",
    ):
        assert key in d, f"Missing key in to_dict() output: {key!r}"

    # Every dataclass field must appear in dict.
    from dataclasses import fields as _fields
    for f in _fields(BCResult):
        assert f.name in d, f"Field {f.name!r} missing from to_dict()"

    # to_dict must be JSON-serializable.
    json.dumps(d)


def test_next_required_task_constant_equals_documented_fallback_BD_string() -> None:
    expected = (
        "TASK-014BD_guarded_entry_real_execution_adapter_disabled_"
        "implementation_scaffold_manual_authorization_gate_final_pre_"
        "execution_review_manual_authorization_review_readiness_review"
    )
    assert NEXT_REQUIRED_TASK == expected


def test_bb_chained_proof_exposure_in_result(valid_bb_artifact: dict[str, Any]) -> None:
    """BC must expose BB's BA next_required_task and BA scope_summary via
    its upstream_* fields (chained proof through BB)."""
    result = run(bb_artifact=valid_bb_artifact)
    expected_ba_next = (
        "TASK-014BB_guarded_entry_real_execution_adapter_disabled_"
        "implementation_scaffold_manual_authorization_gate_final_pre_"
        "execution_review_manual_authorization_review"
    )
    assert result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_next_required_task == expected_ba_next
    ba_scope = result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary
    assert "TASK-014BA consumes TASK-014AZ" in ba_scope


def test_load_bb_artifact_roundtrip(tmp_path: Path, valid_bb_artifact: dict[str, Any]) -> None:
    """The loader returns the same dict when given a valid JSON file."""
    f = tmp_path / "bb.json"
    f.write_text(json.dumps(valid_bb_artifact), encoding="utf-8")
    loaded = _load_bb_manual_authorization_review_artifact(f)
    assert loaded is not None
    assert loaded["status"] == valid_bb_artifact["status"]
    # Missing file
    missing = tmp_path / "nope.json"
    assert _load_bb_manual_authorization_review_artifact(missing) is None
    # Invalid JSON
    bad = tmp_path / "bad.json"
    bad.write_text("not json {", encoding="utf-8")
    assert _load_bb_manual_authorization_review_artifact(bad) is None
