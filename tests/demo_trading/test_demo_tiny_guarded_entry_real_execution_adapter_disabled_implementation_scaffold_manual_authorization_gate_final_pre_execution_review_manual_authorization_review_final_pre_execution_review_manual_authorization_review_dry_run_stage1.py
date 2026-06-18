"""
Stage 1 focused-core tests for TASK-014BG

src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run.py

These tests prove that the BG src is internally coherent: identity
constants, the 37 hard-fail gate constants (BG mirrors BF's 37-gate
hardening by enforcing a dedicated forbidden-direct-consumption guard
for "TASK-014BF consumes TASK-014AV" at the BF-scope level), the result
dataclass default safety invariants, the chain-closure booleans, the BF
artifact loader, and the run-function gate evaluation logic.  The full
test pack (CLI subprocess tests, on-disk JSON/MD inspection, identity-
wording grep tests, all the BF-content-grep negative-proof tests) is
Stage 3 and is intentionally NOT included here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run import (
    ADAPTER_CONTRACT_VERSION,
    ADAPTER_NAME,
    AUTHORIZATION_RESULT_DOCUMENTED_ONLY,
    CONCLUSION_READY_NOT_EXECUTABLE,
    GATE_BF_ARTIFACT_MISSING,
    GATE_BF_MISSING_BE_CHAINED_PROOF,
    GATE_BF_MODE_MISMATCH,
    GATE_BF_NEXT_REQUIRED_TASK_MISMATCH,
    GATE_BF_REAL_EXECUTION_ALLOWED_TRUE,
    GATE_BF_SCOPE_SUMMARY_HAS_BF_CONSUMES_AV,
    GATE_BF_SCOPE_SUMMARY_HAS_BF_CONSUMES_BB,
    GATE_BF_SEND_ALLOWED_TRUE,
    GATE_BF_STATUS_FAIL_CLOSED,
    IDENTITY_CHECKLIST,
    IDENTITY_STRICT,
    MODE_CHECKLIST,
    MODE_FAIL_CLOSED,
    NEXT_REQUIRED_TASK,
    RESPONSE_STATUS_NOT_SENT,
    SCOPE_SUMMARY_LITERAL,
    STATUS_BF_READY,
    STATUS_FAIL_CLOSED,
    STATUS_READY,
    STATUS_READY_BUT_EXECUTION_DISABLED,
    STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED,
    TinyGuardedEntryRealExecutionAdapterDisabledImplementationScaffoldManualAuthorizationGateFinalPreExecutionReviewManualAuthorizationReviewFinalPreExecutionReviewManualAuthorizationReviewDryRunResult as BGResult,
    _GATE_TO_STAGE,
    _HARD_FAIL_GATES,
    _load_bf_manual_authorization_review_artifact,
    run_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run as run,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _valid_bf_artifact() -> dict[str, Any]:
    """
    A synthetic BF artifact dict that mirrors the TASK-014BF emitted JSON
    contract closely enough to satisfy every Group A / Group B / Group C
    gate (i.e. so that no hard-fail gate triggers on BG).
    """
    bf_scope_summary = (
        "TASK-014BF consumes TASK-014BE DISABLED IMPLEMENTATION SCAFFOLD "
        "MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW MANUAL "
        "AUTHORIZATION REVIEW FINAL PRE-EXECUTION REVIEW output at "
        "runtime plus BE-proven chained proof, including BD readiness "
        "review, BC dry-run, BB manual authorization review, BA final "
        "pre-execution review, AZ readiness review, AY dry-run, AX "
        "manual authorization gate design, AW final pre-execution "
        "review, AV readiness review, AU dry-run, AT design, AS static "
        "skeleton dry-run, AR static skeleton design, and AQ "
        "implementation design."
    )
    be_scope_summary = (
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
    return {
        # BF top-level
        "status": STATUS_BF_READY,
        "mode": (
            "disabled_implementation_scaffold_manual_authorization_gate_"
            "final_pre_execution_review_manual_authorization_review_"
            "final_pre_execution_review_manual_authorization_review_"
            "checklist"
        ),
        "selected_symbol": "SOLUSDT",
        "adapter_name": "GuardedTinyEntryRealExecutionAdapter",
        "adapter_contract_version": (
            "disabled_implementation_scaffold_manual_authorization_gate_"
            "final_pre_execution_review_manual_authorization_review_"
            "final_pre_execution_review_manual_authorization_review_v1"
        ),
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_conclusion": (
            "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_"
            "FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_"
            "FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_"
            "READY_NOT_EXECUTABLE"
        ),
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_authorization_result": (
            "DOCUMENTED_ONLY_NOT_AUTHORIZED"
        ),
        "response_status": (
            "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_"
            "FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_"
            "FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_NOT_"
            "SENT"
        ),
        "next_required_task": (
            "TASK-014BG_guarded_entry_real_execution_adapter_disabled_"
            "implementation_scaffold_manual_authorization_gate_final_pre_"
            "execution_review_manual_authorization_review_final_pre_"
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
        "scope_summary": bf_scope_summary,
        # BF->BE chained proof (BE-side fields BF emits)
        "consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_contract_version": (
            "disabled_implementation_scaffold_manual_authorization_gate_"
            "final_pre_execution_review_manual_authorization_review_"
            "final_pre_execution_review_v1"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_status": (
            "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_"
            "IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_"
            "PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_FINAL_"
            "PRE_EXECUTION_REVIEW_READY"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_next_required_task": (
            "TASK-014BF_guarded_entry_real_execution_adapter_disabled_"
            "implementation_scaffold_manual_authorization_gate_final_pre_"
            "execution_review_manual_authorization_review_final_pre_"
            "execution_review_manual_authorization_review"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary": be_scope_summary,
    }


@pytest.fixture
def valid_bf_artifact() -> dict[str, Any]:
    return _valid_bf_artifact()


# ---------------------------------------------------------------------------
# Stage 1 core tests
# ---------------------------------------------------------------------------

def test_identity_checklist_and_strict_literal_exact_match() -> None:
    assert IDENTITY_CHECKLIST == (
        "DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL "
        "PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW FINAL "
        "PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW DRY-RUN "
        "CHECKLIST"
    )
    expected_strict = (
        "STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-"
        "GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-"
        "FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-DRY-RUN-"
        "ONLY"
    )
    assert IDENTITY_STRICT == expected_strict
    # The BG identity must NOT collapse to any earlier phase identity.
    assert "READINESS-REVIEW-ONLY" not in IDENTITY_STRICT
    assert "DESIGN-ONLY" not in IDENTITY_STRICT
    # BG must not collapse to BF's identity (BF ends with
    # "MANUAL-AUTHORIZATION-REVIEW-ONLY"; BG ends with "DRY-RUN-ONLY").
    bf_identity = (
        "STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-"
        "GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-"
        "FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-ONLY"
    )
    assert IDENTITY_STRICT != bf_identity
    assert IDENTITY_STRICT.endswith("DRY-RUN-ONLY")


def test_scope_summary_literal_exact_match() -> None:
    expected = (
        "TASK-014BG consumes TASK-014BF DISABLED IMPLEMENTATION SCAFFOLD "
        "MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW MANUAL "
        "AUTHORIZATION REVIEW FINAL PRE-EXECUTION REVIEW MANUAL "
        "AUTHORIZATION REVIEW output at runtime plus BF-proven chained "
        "proof, including BE final pre-execution review, BD readiness "
        "review, BC dry-run, BB manual authorization review, BA final "
        "pre-execution review, AZ readiness review, AY dry-run, AX "
        "manual authorization gate design, AW final pre-execution "
        "review, AV readiness review, AU dry-run, AT design, AS static "
        "skeleton dry-run, AR static skeleton design, and AQ "
        "implementation design."
    )
    assert SCOPE_SUMMARY_LITERAL == expected
    # Direct upstream is BF; BE/BD/BC/BB/BA/AZ/AY/AX/AW/AV must NOT be
    # present as direct-consumption phrases on BG's own scope_summary.
    for forbidden in (
        "TASK-014BG consumes TASK-014BE",
        "TASK-014BG consumes TASK-014BD",
        "TASK-014BG consumes TASK-014BC",
        "TASK-014BG consumes TASK-014BB",
        "TASK-014BG consumes TASK-014BA",
        "TASK-014BG consumes TASK-014AZ",
        "TASK-014BG consumes TASK-014AY",
        "TASK-014BG consumes TASK-014AX",
        "TASK-014BG consumes TASK-014AW",
        "TASK-014BG consumes TASK-014AV",
    ):
        assert forbidden not in SCOPE_SUMMARY_LITERAL


def test_next_required_task_points_to_demo_only_tiny_execution_adapter_path() -> None:
    """BG closes the disabled review chain.  Its next_required_task must
    point to the demo-only tiny execution adapter implementation path,
    NOT to another readiness_review / final_pre_execution_review /
    manual_authorization_review chain suffix."""
    expected = (
        "TASK-014BH_demo_only_tiny_execution_adapter_implementation_path"
    )
    assert NEXT_REQUIRED_TASK == expected
    # Must NOT spawn another review-chain suffix.
    for forbidden in (
        "_readiness_review",
        "_final_pre_execution_review",
        "_manual_authorization_review",
        "_dry_run",
    ):
        assert forbidden not in NEXT_REQUIRED_TASK, (
            f"next_required_task must NOT contain {forbidden!r} -- "
            f"BG is the chain-closing dry-run."
        )


def test_status_and_conclusion_constants_are_distinct() -> None:
    assert STATUS_READY != CONCLUSION_READY_NOT_EXECUTABLE
    assert STATUS_READY != STATUS_READY_BUT_EXECUTION_DISABLED
    assert STATUS_READY != STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
    assert STATUS_READY != STATUS_FAIL_CLOSED
    # BG status must end with the BG-specific DRY_RUN suffix, not the BF
    # MANUAL_AUTHORIZATION_REVIEW suffix.
    assert STATUS_READY.endswith("MANUAL_AUTHORIZATION_REVIEW_DRY_RUN_READY")
    assert CONCLUSION_READY_NOT_EXECUTABLE.endswith(
        "MANUAL_AUTHORIZATION_REVIEW_DRY_RUN_READY_NOT_EXECUTABLE"
    )


def test_hard_fail_gates_frozenset_contains_exactly_37() -> None:
    # BG mirrors BF's 37-gate hardening: A=18 + B=7 + C=3 + D=9.
    # The dedicated GATE_BF_SCOPE_SUMMARY_HAS_BF_CONSUMES_AV is enforced
    # at the BF-scope level, mirroring BF's
    # GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AV.
    assert isinstance(_HARD_FAIL_GATES, frozenset)
    assert len(_HARD_FAIL_GATES) == 37


def test_gate_to_stage_covers_every_hard_fail_gate() -> None:
    for gate in _HARD_FAIL_GATES:
        assert gate in _GATE_TO_STAGE, f"Gate {gate!r} missing from _GATE_TO_STAGE"


def test_av_guard_constant_name_and_value() -> None:
    # Mirrors BF's GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AV pattern:
    # BG inspects BF's scope_summary, so the AV-guard is named for BF.
    assert GATE_BF_SCOPE_SUMMARY_HAS_BF_CONSUMES_AV == "bf_scope_summary_has_bf_consumes_av"
    assert GATE_BF_SCOPE_SUMMARY_HAS_BF_CONSUMES_AV in _HARD_FAIL_GATES


def test_run_with_valid_synthetic_bf_artifact_returns_READY(valid_bf_artifact: dict[str, Any]) -> None:
    result = run(bf_artifact=valid_bf_artifact)
    assert result.status == STATUS_READY, (
        f"Expected STATUS_READY but got {result.status!r}; "
        f"blocked_gates={result.blocked_gates}"
    )
    assert result.mode == MODE_CHECKLIST
    assert result.blocked_gates == []
    assert result.failed_stage == ""


def test_default_dataclass_safety_invariants_hold() -> None:
    """A freshly-instantiated BG result must hold every safety invariant."""
    r = BGResult()
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
    assert r.manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_only is True
    assert r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_only is True
    # Authorization-grants invariants (every grants_execution must be False)
    assert r.manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_grants_execution is False
    assert r.manual_authorization_review_final_pre_execution_review_manual_authorization_review_grants_execution is False
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
    assert r.manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_accepts_runtime_approval is False
    assert r.manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_translates_text_to_execution is False
    # Identity / verdict
    assert r.adapter_name == ADAPTER_NAME
    assert r.adapter_contract_version == ADAPTER_CONTRACT_VERSION
    assert r.response_status == RESPONSE_STATUS_NOT_SENT
    assert r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_conclusion == CONCLUSION_READY_NOT_EXECUTABLE
    assert r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_authorization_result == AUTHORIZATION_RESULT_DOCUMENTED_ONLY
    assert r.next_required_task == NEXT_REQUIRED_TASK
    assert r.existing_positions_touched == []
    # Chain-closure invariants (BG-specific)
    assert r.closes_disabled_review_chain is True
    assert r.prepares_demo_only_tiny_execution_adapter_implementation_path is True
    assert r.spawns_additional_review_chain_suffix is False


def test_missing_bf_artifact_triggers_GATE_BF_ARTIFACT_MISSING_and_FAIL_CLOSED(tmp_path: Path) -> None:
    # No artifact provided at all -> the run-function still sets
    # artifact=None and triggers the gate.
    result = run()
    assert GATE_BF_ARTIFACT_MISSING in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED
    assert result.mode == MODE_FAIL_CLOSED
    assert result.failed_stage != ""

    # Also: explicit path that doesn't exist.
    missing = tmp_path / "nope.json"
    result2 = run(bf_artifact_path=missing)
    assert GATE_BF_ARTIFACT_MISSING in result2.blocked_gates
    assert result2.status == STATUS_FAIL_CLOSED


def test_bf_status_FAIL_CLOSED_triggers_passthrough_FAIL_CLOSED(valid_bf_artifact: dict[str, Any]) -> None:
    bad = dict(valid_bf_artifact) | {
        "status": STATUS_FAIL_CLOSED,
        "mode": MODE_FAIL_CLOSED,
        "failed_stage": "stage_X_synthetic_failure",
    }
    result = run(bf_artifact=bad)
    assert GATE_BF_STATUS_FAIL_CLOSED in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED
    assert result.mode == MODE_FAIL_CLOSED


def test_bf_mode_mismatch_triggers_FAIL_CLOSED(valid_bf_artifact: dict[str, Any]) -> None:
    bad = dict(valid_bf_artifact) | {"mode": "some_random_unaccepted_mode"}
    result = run(bf_artifact=bad)
    assert GATE_BF_MODE_MISMATCH in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_bf_next_required_task_mismatch_triggers_FAIL_CLOSED(valid_bf_artifact: dict[str, Any]) -> None:
    bad = dict(valid_bf_artifact) | {"next_required_task": "TASK-014WRONG"}
    result = run(bf_artifact=bad)
    assert GATE_BF_NEXT_REQUIRED_TASK_MISMATCH in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_bf_real_execution_allowed_True_triggers_FAIL_CLOSED(valid_bf_artifact: dict[str, Any]) -> None:
    bad = dict(valid_bf_artifact) | {"real_execution_allowed": True}
    result = run(bf_artifact=bad)
    assert GATE_BF_REAL_EXECUTION_ALLOWED_TRUE in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_bf_send_allowed_True_triggers_FAIL_CLOSED(valid_bf_artifact: dict[str, Any]) -> None:
    bad = dict(valid_bf_artifact) | {"send_allowed": True}
    result = run(bf_artifact=bad)
    assert GATE_BF_SEND_ALLOWED_TRUE in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_bf_scope_summary_missing_TASK_014BF_consumes_TASK_014BE_triggers_FAIL_CLOSED(valid_bf_artifact: dict[str, Any]) -> None:
    """Per TASK-014BG lock-in 2: a BF artifact whose scope_summary does
    not contain 'TASK-014BF consumes TASK-014BE' must fail closed.  The
    enforcement gate is GATE_BF_MISSING_BE_CHAINED_PROOF."""
    # Build a scope_summary that lacks the direct-upstream phrase but
    # still contains the "BE-proven chained proof" marker (so we
    # isolate the missing-direct-upstream condition).
    bad_summary = (
        "TASK-014BF consumes some other upstream output at runtime plus "
        "BE-proven chained proof, including BD readiness review, BC "
        "dry-run, BB manual authorization review, BA final pre-execution "
        "review, AZ readiness review."
    )
    bad = dict(valid_bf_artifact) | {"scope_summary": bad_summary}
    result = run(bf_artifact=bad)
    assert GATE_BF_MISSING_BE_CHAINED_PROOF in result.blocked_gates, (
        f"Expected GATE_BF_MISSING_BE_CHAINED_PROOF to fire; "
        f"blocked_gates={result.blocked_gates}"
    )
    assert result.status == STATUS_FAIL_CLOSED


def test_bf_scope_summary_contains_TASK_014BF_consumes_TASK_014BB_triggers_FAIL_CLOSED(valid_bf_artifact: dict[str, Any]) -> None:
    bad_summary = (
        valid_bf_artifact["scope_summary"]
        + " TASK-014BF consumes TASK-014BB directly"
    )
    bad = dict(valid_bf_artifact) | {"scope_summary": bad_summary}
    result = run(bf_artifact=bad)
    assert GATE_BF_SCOPE_SUMMARY_HAS_BF_CONSUMES_BB in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_bf_scope_summary_contains_TASK_014BF_consumes_TASK_014AV_triggers_FAIL_CLOSED(valid_bf_artifact: dict[str, Any]) -> None:
    """AV-guard test (mandatory).  Mirrors BF's AV-hardening at the next
    chain level: BG must fail closed when BF's scope_summary contains
    the forbidden direct-consumption phrase 'TASK-014BF consumes
    TASK-014AV'."""
    bad_summary = (
        valid_bf_artifact["scope_summary"]
        + " TASK-014BF consumes TASK-014AV directly"
    )
    bad = dict(valid_bf_artifact) | {"scope_summary": bad_summary}
    result = run(bf_artifact=bad)
    assert GATE_BF_SCOPE_SUMMARY_HAS_BF_CONSUMES_AV in result.blocked_gates
    assert result.status == STATUS_FAIL_CLOSED


def test_allow_flag_returns_READY_BUT_EXECUTION_DISABLED_with_no_execution(valid_bf_artifact: dict[str, Any]) -> None:
    result = run(
        bf_artifact=valid_bf_artifact,
        allow_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run=True,
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
    assert result.manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_grants_execution is False
    # Chain-closure invariants still hold.
    assert result.closes_disabled_review_chain is True
    assert result.prepares_demo_only_tiny_execution_adapter_implementation_path is True
    assert result.spawns_additional_review_chain_suffix is False


def test_allow_real_entry_execution_flag_returns_NOT_IMPLEMENTED(valid_bf_artifact: dict[str, Any]) -> None:
    result = run(
        bf_artifact=valid_bf_artifact,
        allow_real_entry_execution=True,
    )
    assert result.status == STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
    # Invariants still hold.
    assert result.real_execution_allowed is False
    assert result.send_allowed is False
    assert result.no_orders_sent is True
    assert result.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_conclusion == CONCLUSION_READY_NOT_EXECUTABLE


def test_to_dict_round_trip_completeness(valid_bf_artifact: dict[str, Any]) -> None:
    result = run(bf_artifact=valid_bf_artifact)
    d = result.to_dict()
    # Spot-check required keys are present.
    for key in (
        "status", "mode", "selected_symbol", "adapter_name",
        "adapter_contract_version", "response_status", "next_required_task",
        "failed_stage", "blocked_gates", "scope_summary",
        "identity_checklist", "identity_strict",
        "manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_only",
        "executable_adapter_included",
        "real_execution_allowed", "send_allowed", "no_orders_sent",
        "no_position_modified", "g20_lifted",
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_conclusion",
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_authorization_result",
        # BF upstream
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_scope_summary",
        # BF->BE chained proof (BG uses short prefix bf_chained_be_*)
        "bf_chained_be_status",
        "bf_chained_be_next_required_task",
        "bf_chained_be_scope_summary",
        "bf_scope_summary_mentions_be_direct_upstream",
        "bf_scope_summary_mentions_be_proven_chained_proof",
        # Chain-closure booleans
        "closes_disabled_review_chain",
        "prepares_demo_only_tiny_execution_adapter_implementation_path",
        "spawns_additional_review_chain_suffix",
    ):
        assert key in d, f"Missing key in to_dict() output: {key!r}"

    # Every dataclass field must appear in dict.
    from dataclasses import fields as _fields
    for f in _fields(BGResult):
        assert f.name in d, f"Field {f.name!r} missing from to_dict()"

    # to_dict must be JSON-serializable.
    json.dumps(d)


def test_bf_chained_proof_exposure_in_result(valid_bf_artifact: dict[str, Any]) -> None:
    """BG must expose BF's BE next_required_task and BE scope_summary via
    its bf_chained_be_* fields (chained proof through BF)."""
    result = run(bf_artifact=valid_bf_artifact)
    expected_be_next = (
        "TASK-014BF_guarded_entry_real_execution_adapter_disabled_"
        "implementation_scaffold_manual_authorization_gate_final_pre_"
        "execution_review_manual_authorization_review_final_pre_"
        "execution_review_manual_authorization_review"
    )
    assert result.bf_chained_be_next_required_task == expected_be_next
    assert "TASK-014BE consumes TASK-014BD" in result.bf_chained_be_scope_summary
    # Group B booleans on BF scope_summary
    assert result.bf_scope_summary_mentions_be_direct_upstream is True
    assert result.bf_scope_summary_mentions_be_proven_chained_proof is True


def test_load_bf_artifact_roundtrip(tmp_path: Path, valid_bf_artifact: dict[str, Any]) -> None:
    """The loader returns the same dict when given a valid JSON file."""
    f = tmp_path / "bf.json"
    f.write_text(json.dumps(valid_bf_artifact), encoding="utf-8")
    loaded = _load_bf_manual_authorization_review_artifact(f)
    assert loaded is not None
    assert loaded["status"] == valid_bf_artifact["status"]
    # Missing file
    missing = tmp_path / "nope.json"
    assert _load_bf_manual_authorization_review_artifact(missing) is None
    # Invalid JSON
    bad = tmp_path / "bad.json"
    bad.write_text("not json {", encoding="utf-8")
    assert _load_bf_manual_authorization_review_artifact(bad) is None
