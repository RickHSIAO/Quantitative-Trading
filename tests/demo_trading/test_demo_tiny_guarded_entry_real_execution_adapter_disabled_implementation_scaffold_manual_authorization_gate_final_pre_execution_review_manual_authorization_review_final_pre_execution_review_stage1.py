"""
Stage 1 focused-core tests for TASK-014BE

src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review.py

These tests prove that the BE src is internally coherent: identity
constants, the 37 hard-fail gate constants (BE mirrors BD-FIX1's
37-gate hardening by enforcing a dedicated forbidden-direct-consumption
guard for "TASK-014BD consumes TASK-014AV" at the BD-scope level), the
result dataclass default safety invariants, the BD artifact loader, and
the run-function gate evaluation logic.  The full test pack (CLI
subprocess tests, on-disk JSON/MD inspection, identity-wording grep
tests, all the BD-content-grep negative-proof tests) is Stage 3 and is
intentionally NOT included here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review import (
    ADAPTER_CONTRACT_VERSION,
    ADAPTER_NAME,
    AUTHORIZATION_RESULT_DOCUMENTED_ONLY,
    CONCLUSION_READY_NOT_EXECUTABLE,
    GATE_BD_ARTIFACT_MISSING,
    GATE_BD_MISSING_BC_CHAINED_PROOF,
    GATE_BD_MODE_MISMATCH,
    GATE_BD_NEXT_REQUIRED_TASK_MISMATCH,
    GATE_BD_REAL_EXECUTION_ALLOWED_TRUE,
    GATE_BD_SCOPE_SUMMARY_HAS_BD_CONSUMES_AV,
    GATE_BD_SCOPE_SUMMARY_HAS_BD_CONSUMES_BB,
    GATE_BD_SEND_ALLOWED_TRUE,
    GATE_BD_STATUS_FAIL_CLOSED,
    IDENTITY_CHECKLIST,
    IDENTITY_STRICT,
    MODE_CHECKLIST,
    MODE_FAIL_CLOSED,
    NEXT_REQUIRED_TASK,
    RESPONSE_STATUS_NOT_SENT,
    SCOPE_SUMMARY_LITERAL,
    STATUS_BD_READY,
    STATUS_FAIL_CLOSED,
    STATUS_READY,
    STATUS_READY_BUT_EXECUTION_DISABLED,
    STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED,
    TinyGuardedEntryRealExecutionAdapterDisabledImplementationScaffoldManualAuthorizationGateFinalPreExecutionReviewManualAuthorizationReviewFinalPreExecutionReviewResult as BEResult,
    _GATE_TO_STAGE,
    _HARD_FAIL_GATES,
    _load_bd_readiness_review_artifact,
    run_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review as run,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _valid_bd_artifact() -> dict[str, Any]:
    """
    A synthetic BD artifact dict that mirrors the TASK-014BD-FIX1 emitted
    JSON contract closely enough to satisfy every Group A / Group B /
    Group C gate (i.e. so that no hard-fail gate triggers).
    """
    bd_scope_summary = (
        "TASK-014BD consumes TASK-014BC DISABLED IMPLEMENTATION SCAFFOLD "
        "MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW MANUAL "
        "AUTHORIZATION REVIEW DRY-RUN output at runtime plus BC-proven "
        "chained proof, including BB manual authorization review, BA "
        "final pre-execution review, AZ readiness review, AY dry-run, "
        "AX manual authorization gate design, AW final pre-execution "
        "review, AV readiness review, AU dry-run, AT design, AS static "
        "skeleton dry-run, AR static skeleton design, and AQ "
        "implementation design."
    )
    bc_scope_summary = (
        "TASK-014BC consumes TASK-014BB DISABLED IMPLEMENTATION SCAFFOLD "
        "MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW MANUAL "
        "AUTHORIZATION REVIEW output at runtime plus BB-proven chained "
        "proof, including BA final pre-execution review, AZ readiness "
        "review, AY dry-run, AX manual authorization gate design, AW "
        "final pre-execution review, AV readiness review, AU dry-run, "
        "AT design, AS static skeleton dry-run, AR static skeleton "
        "design, and AQ implementation design."
    )
    return {
        # BD top-level
        "status": STATUS_BD_READY,
        "mode": (
            "disabled_implementation_scaffold_manual_authorization_gate_"
            "final_pre_execution_review_manual_authorization_review_"
            "readiness_review_checklist"
        ),
        "selected_symbol": "SOLUSDT",
        "adapter_name": "GuardedTinyEntryRealExecutionAdapter",
        "adapter_contract_version": (
            "disabled_implementation_scaffold_manual_authorization_gate_"
            "final_pre_execution_review_manual_authorization_review_"
            "readiness_review_v1"
        ),
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_conclusion": (
            "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_"
            "FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_"
            "READINESS_REVIEW_READY_NOT_EXECUTABLE"
        ),
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_authorization_result": (
            "DOCUMENTED_ONLY_NOT_AUTHORIZED"
        ),
        "response_status": (
            "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_"
            "FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_"
            "READINESS_REVIEW_NOT_SENT"
        ),
        "next_required_task": (
            "TASK-014BE_guarded_entry_real_execution_adapter_disabled_"
            "implementation_scaffold_manual_authorization_gate_final_pre_"
            "execution_review_manual_authorization_review_final_pre_"
            "execution_review"
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
        "scope_summary": bd_scope_summary,
        # BD->BC chained proof (BC-side fields BD emits)
        "consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_contract_version": (
            "disabled_implementation_scaffold_manual_authorization_gate_"
            "final_pre_execution_review_manual_authorization_review_"
            "dry_run_v1"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_status": (
            "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_"
            "IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_"
            "PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_DRY_RUN_READY"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_next_required_task": (
            "TASK-014BD_guarded_entry_real_execution_adapter_disabled_"
            "implementation_scaffold_manual_authorization_gate_final_pre_"
            "execution_review_manual_authorization_review_readiness_review"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_scope_summary": bc_scope_summary,
    }


@pytest.fixture
def valid_bd_artifact() -> dict[str, Any]:
    return _valid_bd_artifact()


# ---------------------------------------------------------------------------
# Stage 1 core tests
# ---------------------------------------------------------------------------

def test_identity_checklist_and_strict_literal_exact_match() -> None:
    assert IDENTITY_CHECKLIST == (
        "DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL "
        "PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW FINAL "
        "PRE-EXECUTION REVIEW CHECKLIST"
    )
    expected_strict = (
        "STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-"
        "GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-"
        "FINAL-PRE-EXECUTION-REVIEW-ONLY"
    )
    assert IDENTITY_STRICT == expected_strict
    # The BE identity must NOT collapse to any earlier phase identity.
    assert "READINESS-REVIEW-ONLY" not in IDENTITY_STRICT
    assert "DRY-RUN-ONLY" not in IDENTITY_STRICT
    assert "MANUAL-AUTHORIZATION-REVIEW-ONLY" not in IDENTITY_STRICT
    assert "DESIGN-ONLY" not in IDENTITY_STRICT


def test_scope_summary_literal_exact_match() -> None:
    expected = (
        "TASK-014BE consumes TASK-014BD DISABLED IMPLEMENTATION SCAFFOLD "
        "MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW MANUAL "
        "AUTHORIZATION REVIEW READINESS REVIEW output at runtime plus "
        "BD-proven chained proof, including BC dry-run, BB manual "
        "authorization review, BA final pre-execution review, AZ "
        "readiness review, AY dry-run, AX manual authorization gate "
        "design, AW final pre-execution review, AV readiness review, "
        "AU dry-run, AT design, AS static skeleton dry-run, AR static "
        "skeleton design, and AQ implementation design."
    )
    assert SCOPE_SUMMARY_LITERAL == expected


def test_next_required_task_constant_equals_documented_fallback_BF_string() -> None:
    expected = (
        "TASK-014BF_guarded_entry_real_execution_adapter_disabled_"
        "implementation_scaffold_manual_authorization_gate_final_pre_"
        "execution_review_manual_authorization_review_final_pre_"
        "execution_review_manual_authorization_review"
    )
    assert NEXT_REQUIRED_TASK == expected


def test_status_and_conclusion_constants_are_distinct() -> None:
    assert STATUS_READY != CONCLUSION_READY_NOT_EXECUTABLE
    assert STATUS_READY != STATUS_READY_BUT_EXECUTION_DISABLED
    assert STATUS_READY != STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
    assert STATUS_READY != STATUS_FAIL_CLOSED
    assert CONCLUSION_READY_NOT_EXECUTABLE.endswith(
        "FINAL_PRE_EXECUTION_REVIEW_READY_NOT_EXECUTABLE"
    )


def test_hard_fail_gates_frozenset_contains_exactly_37() -> None:
    # BE mirrors BD-FIX1's 37-gate hardening: A=18 + B=7 + C=3 + D=9.
    # The dedicated GATE_BD_SCOPE_SUMMARY_HAS_BD_CONSUMES_AV is enforced
    # at the BD-scope level, mirroring BD-FIX1's
    # GATE_BC_SCOPE_SUMMARY_HAS_BC_CONSUMES_AV.
    assert isinstance(_HARD_FAIL_GATES, frozenset)
    assert len(_HARD_FAIL_GATES) == 37


def test_gate_to_stage_covers_every_hard_fail_gate() -> None:
    for gate in _HARD_FAIL_GATES:
        assert gate in _GATE_TO_STAGE, f"Gate {gate!r} missing from _GATE_TO_STAGE"


def test_av_guard_constant_name_and_value() -> None:
    # Mirrors BD-FIX1's GATE_BC_SCOPE_SUMMARY_HAS_BC_CONSUMES_AV pattern:
    # BE inspects BD's scope_summary, so the AV-guard is named for BD.
    assert GATE_BD_SCOPE_SUMMARY_HAS_BD_CONSUMES_AV == "bd_scope_summary_has_bd_consumes_av"
    assert GATE_BD_SCOPE_SUMMARY_HAS_BD_CONSUMES_AV in _HARD_FAIL_GATES


def test_run_with_valid_synthetic_bd_artifact_returns_READY(valid_bd_artifact: dict[str, Any]) -> None:
    result = run(bd_artifact=valid_bd_artifact)
    assert result.status == STATUS_READY, (
        f"Expected STATUS_READY but got {result.status!r}; "
        f"blocked_gates={result.blocked_gates}"
    )
    assert result.mode == MODE_CHECKLIST
    assert result.blocked_gates == []
    assert result.failed_stage == ""


def test_default_dataclass_safety_invariants_hold() -> None:
    """A freshly-instantiated BE result must hold every safety invariant."""
    r = BEResult()
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
    assert r.manual_authorization_review_final_pre_execution_review_only is True
    assert r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_only is True
    # Authorization-grants invariants (every grants_execution must be False)
    assert r.manual_authorization_review_final_pre_execution_review_grants_execution is False
    assert r.manual_authorization_review_readiness_review_grants_execution is False
    assert r.manual_authorization_review_dry_run_grants_execution is False
    assert r.manual_authorization_review_grants_execution is False
    assert r.manual_authorization_gate_final_pre_execution_review_grants_execution is False
    assert r.manual_authorization_gate_readiness_review_grants_execution is False
    assert r.manual_authorization_gate_dry_run_grants_execution is False
    assert r.manual_authorization_gate_design_grants_execution is False
    assert r.final_pre_execution_review_grants_execution is False
    assert r.readiness_review_grants_execution is False
    assert r.dry_run_grants_execution is False
    assert r.adapter_grants_execution is False
    # Approval-input invariants
    assert r.approval_phrase_validated is False
    assert r.approval_token_validated is False
    assert r.approval_inputs_validated is False
    assert r.approval_phrase_grants_execution is False
    assert r.approval_token_grants_execution is False
    assert r.approval_inputs_grant_execution is False
    assert r.token_to_authorization_mapping is False
    assert r.phrase_to_authorization_mapping is False
    assert r.manual_authorization_review_final_pre_execution_review_accepts_runtime_approval is False
    assert r.manual_authorization_review_final_pre_execution_review_translates_text_to_execution is False
    # Identity / verdict
    assert r.adapter_name == ADAPTER_NAME
    assert r.adapter_contract_version == ADAPTER_CONTRACT_VERSION
    assert r.response_status == RESPONSE_STATUS_NOT_SENT
    assert r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_conclusion == CONCLUSION_READY_NOT_EXECUTABLE
    assert r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_authorization_result == AUTHORIZATION_RESULT_DOCUMENTED_ONLY
    assert r.next_required_task == NEXT_REQUIRED_TASK
    assert r.existing_positions_touched == []


def test_missing_bd_artifact_triggers_GATE_BD_ARTIFACT_MISSING_and_FAIL_CLOSED(tmp_path: Path) -> None:
    # No artifact provided at all -> the run-function still sets
    # artifact=None and triggers the gate.
    result = run()
    assert GATE_BD_ARTIFACT_MISSING in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED
    assert result.mode == MODE_FAIL_CLOSED
    assert result.failed_stage != ""

    # Also: explicit path that doesn't exist.
    missing = tmp_path / "nope.json"
    result2 = run(bd_artifact_path=missing)
    assert GATE_BD_ARTIFACT_MISSING in result2.blocked_gates
    assert result2.status == STATUS_FAIL_CLOSED


def test_bd_status_FAIL_CLOSED_triggers_passthrough_FAIL_CLOSED(valid_bd_artifact: dict[str, Any]) -> None:
    bad = dict(valid_bd_artifact) | {
        "status": STATUS_FAIL_CLOSED,
        "mode": MODE_FAIL_CLOSED,
        "failed_stage": "stage_X_synthetic_failure",
    }
    result = run(bd_artifact=bad)
    assert GATE_BD_STATUS_FAIL_CLOSED in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED
    assert result.mode == MODE_FAIL_CLOSED


def test_bd_mode_mismatch_triggers_FAIL_CLOSED(valid_bd_artifact: dict[str, Any]) -> None:
    bad = dict(valid_bd_artifact) | {"mode": "some_random_unaccepted_mode"}
    result = run(bd_artifact=bad)
    assert GATE_BD_MODE_MISMATCH in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_bd_next_required_task_mismatch_triggers_FAIL_CLOSED(valid_bd_artifact: dict[str, Any]) -> None:
    bad = dict(valid_bd_artifact) | {"next_required_task": "TASK-014WRONG"}
    result = run(bd_artifact=bad)
    assert GATE_BD_NEXT_REQUIRED_TASK_MISMATCH in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_bd_real_execution_allowed_True_triggers_FAIL_CLOSED(valid_bd_artifact: dict[str, Any]) -> None:
    bad = dict(valid_bd_artifact) | {"real_execution_allowed": True}
    result = run(bd_artifact=bad)
    assert GATE_BD_REAL_EXECUTION_ALLOWED_TRUE in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_bd_send_allowed_True_triggers_FAIL_CLOSED(valid_bd_artifact: dict[str, Any]) -> None:
    bad = dict(valid_bd_artifact) | {"send_allowed": True}
    result = run(bd_artifact=bad)
    assert GATE_BD_SEND_ALLOWED_TRUE in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_bd_scope_summary_missing_TASK_014BD_consumes_TASK_014BC_triggers_FAIL_CLOSED(valid_bd_artifact: dict[str, Any]) -> None:
    """Per TASK-014BE lock-in 2: a BD artifact whose scope_summary does
    not contain 'TASK-014BD consumes TASK-014BC' must fail closed.  The
    enforcement gate is GATE_BD_MISSING_BC_CHAINED_PROOF."""
    # Build a scope_summary that lacks the direct-upstream phrase but
    # still contains the "BC-proven chained proof" marker (so we
    # isolate the missing-direct-upstream condition).
    bad_summary = (
        "TASK-014BD consumes some other upstream output at runtime plus "
        "BC-proven chained proof, including BB manual authorization "
        "review, BA final pre-execution review, AZ readiness review."
    )
    bad = dict(valid_bd_artifact) | {"scope_summary": bad_summary}
    result = run(bd_artifact=bad)
    assert GATE_BD_MISSING_BC_CHAINED_PROOF in result.blocked_gates, (
        f"Expected GATE_BD_MISSING_BC_CHAINED_PROOF to fire; "
        f"blocked_gates={result.blocked_gates}"
    )
    assert result.status == STATUS_FAIL_CLOSED


def test_bd_scope_summary_contains_TASK_014BD_consumes_TASK_014BB_triggers_FAIL_CLOSED(valid_bd_artifact: dict[str, Any]) -> None:
    bad_summary = (
        valid_bd_artifact["scope_summary"]
        + " TASK-014BD consumes TASK-014BB directly"
    )
    bad = dict(valid_bd_artifact) | {"scope_summary": bad_summary}
    result = run(bd_artifact=bad)
    assert GATE_BD_SCOPE_SUMMARY_HAS_BD_CONSUMES_BB in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_bd_scope_summary_contains_TASK_014BD_consumes_TASK_014AV_triggers_FAIL_CLOSED(valid_bd_artifact: dict[str, Any]) -> None:
    """AV-guard test (mandatory).  Mirrors BD-FIX1's AV-hardening at
    the next chain level: BE must fail closed when BD's scope_summary
    contains the forbidden direct-consumption phrase 'TASK-014BD
    consumes TASK-014AV'."""
    bad_summary = (
        valid_bd_artifact["scope_summary"]
        + " TASK-014BD consumes TASK-014AV directly"
    )
    bad = dict(valid_bd_artifact) | {"scope_summary": bad_summary}
    result = run(bd_artifact=bad)
    assert GATE_BD_SCOPE_SUMMARY_HAS_BD_CONSUMES_AV in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_allow_flag_returns_READY_BUT_EXECUTION_DISABLED_with_no_execution(valid_bd_artifact: dict[str, Any]) -> None:
    result = run(
        bd_artifact=valid_bd_artifact,
        allow_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review=True,
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
    assert result.manual_authorization_review_final_pre_execution_review_grants_execution is False


def test_allow_real_entry_execution_flag_returns_NOT_IMPLEMENTED(valid_bd_artifact: dict[str, Any]) -> None:
    result = run(
        bd_artifact=valid_bd_artifact,
        allow_real_entry_execution=True,
    )
    assert result.status == STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
    # Invariants still hold.
    assert result.real_execution_allowed is False
    assert result.send_allowed is False
    assert result.no_orders_sent is True
    assert result.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_conclusion == CONCLUSION_READY_NOT_EXECUTABLE


def test_to_dict_round_trip_completeness(valid_bd_artifact: dict[str, Any]) -> None:
    result = run(bd_artifact=valid_bd_artifact)
    d = result.to_dict()
    # Spot-check required keys are present.
    for key in (
        "status", "mode", "selected_symbol", "adapter_name",
        "adapter_contract_version", "response_status", "next_required_task",
        "failed_stage", "blocked_gates", "scope_summary",
        "identity_checklist", "identity_strict",
        "manual_authorization_review_final_pre_execution_review_only",
        "executable_adapter_included",
        "real_execution_allowed", "send_allowed", "no_orders_sent",
        "no_position_modified", "g20_lifted",
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_conclusion",
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_authorization_result",
        # BD upstream
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_scope_summary",
        # BD->BC chained proof
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_scope_summary_mentions_bc_direct_upstream",
    ):
        assert key in d, f"Missing key in to_dict() output: {key!r}"

    # Every dataclass field must appear in dict.
    from dataclasses import fields as _fields
    for f in _fields(BEResult):
        assert f.name in d, f"Field {f.name!r} missing from to_dict()"

    # to_dict must be JSON-serializable.
    json.dumps(d)


def test_bd_chained_proof_exposure_in_result(valid_bd_artifact: dict[str, Any]) -> None:
    """BE must expose BD's BC next_required_task and BC scope_summary via
    its upstream_* fields (chained proof through BD)."""
    result = run(bd_artifact=valid_bd_artifact)
    expected_bc_next = (
        "TASK-014BD_guarded_entry_real_execution_adapter_disabled_"
        "implementation_scaffold_manual_authorization_gate_final_pre_"
        "execution_review_manual_authorization_review_readiness_review"
    )
    assert result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_next_required_task == expected_bc_next
    bc_scope = result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_scope_summary
    assert "TASK-014BC consumes TASK-014BB" in bc_scope


def test_load_bd_artifact_roundtrip(tmp_path: Path, valid_bd_artifact: dict[str, Any]) -> None:
    """The loader returns the same dict when given a valid JSON file."""
    f = tmp_path / "bd.json"
    f.write_text(json.dumps(valid_bd_artifact), encoding="utf-8")
    loaded = _load_bd_readiness_review_artifact(f)
    assert loaded is not None
    assert loaded["status"] == valid_bd_artifact["status"]
    # Missing file
    missing = tmp_path / "nope.json"
    assert _load_bd_readiness_review_artifact(missing) is None
    # Invalid JSON
    bad = tmp_path / "bad.json"
    bad.write_text("not json {", encoding="utf-8")
    assert _load_bd_readiness_review_artifact(bad) is None
