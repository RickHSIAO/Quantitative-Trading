"""
Full Stage 3 test pack for TASK-014BD
src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review.py

Stage 3 is the comprehensive BD test pack: core run / Group A / Group B /
Group C / Group D safety, --allow flag behaviour, CLI subprocess
integration, write_report on-disk JSON+Markdown inspection, identity
wording grep, and untouched-file regression. The narrower Stage 1
suite (`*_stage1.py`) remains a focused smaller proof; this file is the
primary BD regression pack.

Every fail-closed test asserts:
  * result.status == STATUS_FAIL_CLOSED
  * the specific gate name is in result.blocked_gates
  * real_execution_allowed / send_allowed stay False
  * no_orders_sent stays True
  * g20_lifted stays False
  * no_position_modified stays True

TASK-014BD is a STRICT manual-authorization-review-readiness-review-only
module: it never opens a socket, never reads secrets, never calls any
endpoint, never modifies any position, never lifts G20, and never
authorizes any real execution. The tests below prove that contract holds
end-to-end. BD consumes TASK-014BC (manual-authorization-review-dry-run)
as the direct upstream. BB/BA/AZ/AY/AX/AW/AV/AU/AT/AS/AR/AQ artifacts
appear ONLY as BC-proven chained proof and are never consumed directly
by BD.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from src.demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review import (
    ADAPTER_CONTRACT_VERSION,
    ADAPTER_NAME,
    AUTHORIZATION_RESULT_DOCUMENTED_ONLY,
    BD_DEFAULT_OUTPUT_DIR,
    CONCLUSION_READY_NOT_EXECUTABLE,
    GATE_BC_ADAPTER_EXECUTION_INCLUDED_TRUE,
    GATE_BC_ADAPTER_IMPLEMENTATION_INCLUDED_TRUE,
    GATE_BC_ARTIFACT_MISSING,
    GATE_BC_AUTHORIZATION_RESULT_MISMATCH,
    GATE_BC_CONCLUSION_MISMATCH,
    GATE_BC_FAILED_STAGE_NON_EMPTY,
    GATE_BC_G20_LIFTED_TRUE,
    GATE_BC_MISSING_BB_CHAINED_PROOF,
    GATE_BC_MISSING_BB_PROVEN_CHAINED_PROOF,
    GATE_BC_MODE_FAIL_CLOSED,
    GATE_BC_MODE_MISMATCH,
    GATE_BC_NEXT_REQUIRED_TASK_MISMATCH,
    GATE_BC_NO_POSITION_MODIFIED_FALSE,
    GATE_BC_NO_SECRETS_LOADED_FALSE,
    GATE_BC_ORDER_ENDPOINT_CALLED_TRUE,
    GATE_BC_REAL_EXECUTION_ALLOWED_TRUE,
    GATE_BC_RESPONSE_STATUS_MISMATCH,
    GATE_BC_SCOPE_SUMMARY_HAS_BC_CONSUMES_AV,
    GATE_BC_SCOPE_SUMMARY_HAS_BC_CONSUMES_AW,
    GATE_BC_SCOPE_SUMMARY_HAS_BC_CONSUMES_AX,
    GATE_BC_SCOPE_SUMMARY_HAS_BC_CONSUMES_AY,
    GATE_BC_SCOPE_SUMMARY_HAS_BC_CONSUMES_AZ,
    GATE_BC_SCOPE_SUMMARY_HAS_BC_CONSUMES_BA,
    GATE_BC_SCOPE_SUMMARY_HAS_ITDOCUMENTS_TYPO,
    GATE_BC_SEND_ALLOWED_TRUE,
    GATE_BC_STATUS_FAIL_CLOSED,
    GATE_BC_STATUS_UNACCEPTABLE,
    GATE_BC_STOP_ENDPOINT_CALLED_TRUE,
    IDENTITY_CHECKLIST,
    IDENTITY_STRICT,
    MODE_CHECKLIST,
    MODE_FAIL_CLOSED,
    NEXT_REQUIRED_TASK,
    RESPONSE_STATUS_NOT_SENT,
    SCOPE_SUMMARY_LITERAL,
    STATUS_BC_READY,
    STATUS_FAIL_CLOSED,
    STATUS_READY,
    STATUS_READY_BUT_EXECUTION_DISABLED,
    STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED,
    TinyGuardedEntryRealExecutionAdapterDisabledImplementationScaffoldManualAuthorizationGateFinalPreExecutionReviewManualAuthorizationReviewReadinessReviewResult as BDResult,
    _HARD_FAIL_GATES,
    _load_bc_dry_run_artifact,
    run_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review as run,
    write_report,
)

ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = ROOT / (
    "src/demo_tiny_guarded_entry_real_execution_adapter_disabled_"
    "implementation_scaffold_manual_authorization_gate_final_pre_"
    "execution_review_manual_authorization_review_readiness_review.py"
)
PREVIEW_PATH = ROOT / (
    "scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_"
    "disabled_implementation_scaffold_manual_authorization_gate_final_"
    "pre_execution_review_manual_authorization_review_readiness_review.py"
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_VALID_BC_SCOPE_SUMMARY = (
    "TASK-014BC consumes TASK-014BB DISABLED IMPLEMENTATION SCAFFOLD "
    "MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW MANUAL "
    "AUTHORIZATION REVIEW output at runtime plus BB-proven chained "
    "proof, including BA final pre-execution review, AZ readiness "
    "review, AY dry-run, AX manual authorization gate design, AW final "
    "pre-execution review, AV readiness review, AU dry-run, AT design, "
    "AS static skeleton dry-run, AR static skeleton design, and AQ "
    "implementation design."
)

_VALID_BB_SCOPE_SUMMARY = (
    "TASK-014BB consumes TASK-014BA DISABLED IMPLEMENTATION SCAFFOLD "
    "MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW output at "
    "runtime plus BA-proven chained proof, including AZ readiness "
    "review, AY dry-run, AX manual authorization gate design, AW final "
    "pre-execution review, AV readiness review, AU dry-run, AT design, "
    "AS static skeleton dry-run, AR static skeleton design, and AQ "
    "implementation design."
)


def _valid_bc_artifact() -> dict[str, Any]:
    """Construct a fresh, fully populated synthetic BC artifact dict."""
    return {
        # ---- BC top-level ----
        "status": STATUS_BC_READY,
        "mode": (
            "disabled_implementation_scaffold_manual_authorization_gate_"
            "final_pre_execution_review_manual_authorization_review_"
            "dry_run_checklist"
        ),
        "selected_symbol": "SOLUSDT",
        "adapter_name": "GuardedTinyEntryRealExecutionAdapter",
        "adapter_contract_version": (
            "disabled_implementation_scaffold_manual_authorization_gate_"
            "final_pre_execution_review_manual_authorization_review_"
            "dry_run_v1"
        ),
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_conclusion": (
            "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_"
            "FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_"
            "DRY_RUN_READY_NOT_EXECUTABLE"
        ),
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_authorization_result": (
            "DOCUMENTED_ONLY_NOT_AUTHORIZED"
        ),
        "response_status": (
            "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_"
            "FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_"
            "DRY_RUN_NOT_SENT"
        ),
        "next_required_task": (
            "TASK-014BD_guarded_entry_real_execution_adapter_disabled_"
            "implementation_scaffold_manual_authorization_gate_final_pre_"
            "execution_review_manual_authorization_review_readiness_review"
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
        "scope_summary": _VALID_BC_SCOPE_SUMMARY,
        # ---- BC->BB chained proof (BB-side fields BC emits) ----
        "consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_contract_version": (
            "disabled_implementation_scaffold_manual_authorization_gate_"
            "final_pre_execution_review_manual_authorization_review_v1"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_status": (
            "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_"
            "IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_"
            "PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_READY"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_next_required_task": (
            "TASK-014BC_guarded_entry_real_execution_adapter_disabled_"
            "implementation_scaffold_manual_authorization_gate_final_pre_"
            "execution_review_manual_authorization_review_dry_run"
        ),
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_scope_summary": _VALID_BB_SCOPE_SUMMARY,
    }


@pytest.fixture
def valid_bc_artifact() -> dict[str, Any]:
    return _valid_bc_artifact()


@pytest.fixture
def bc_artifact_factory():
    """Return a factory `make(**overrides)` returning a valid BC artifact."""
    def _make(**overrides: Any) -> dict[str, Any]:
        d = _valid_bc_artifact()
        d.update(overrides)
        return d
    return _make


@pytest.fixture
def bd_output_dir(tmp_path: Path) -> Path:
    p = tmp_path / "bd_out"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Helper assertions
# ---------------------------------------------------------------------------

def _assert_fail_closed_invariants(
    result: BDResult, expected_gate: str
) -> None:
    """Assert FAIL_CLOSED semantics + the safety invariants."""
    assert result.status == STATUS_FAIL_CLOSED, (
        f"Expected FAIL_CLOSED but got {result.status!r}; "
        f"blocked_gates={result.blocked_gates}"
    )
    assert result.mode == MODE_FAIL_CLOSED
    assert expected_gate in result.blocked_gates, (
        f"Expected gate {expected_gate!r} in blocked_gates "
        f"but got {result.blocked_gates}"
    )
    assert result.failed_stage != ""
    # Safety invariants -- ALL must hold under FAIL_CLOSED.
    assert result.real_execution_allowed is False
    assert result.send_allowed is False
    assert result.no_orders_sent is True
    assert result.no_position_modified is True
    assert result.g20_lifted is False
    assert result.order_endpoint_called is False
    assert result.stop_endpoint_called is False
    assert result.no_secrets_loaded is True
    assert result.secret_value_observed is False
    assert result.g20_policy_still_in_place is True
    assert result.executable_adapter_included is False


# ===========================================================================
# Group BD00 -- Happy path
# ===========================================================================

class TestBD00CoreRun:

    def test_happy_path_with_valid_synthetic_bc_artifact_returns_READY(
        self, valid_bc_artifact: dict[str, Any]
    ) -> None:
        result = run(bc_artifact=valid_bc_artifact)
        assert result.status == STATUS_READY, (
            f"got {result.status!r}; blocked={result.blocked_gates}"
        )
        assert result.mode == MODE_CHECKLIST
        assert result.blocked_gates == []
        assert result.failed_stage == ""
        # Safety invariants must hold even on READY.
        assert result.real_execution_allowed is False
        assert result.send_allowed is False
        assert result.no_orders_sent is True
        assert result.no_position_modified is True
        assert result.g20_lifted is False
        assert result.g20_policy_still_in_place is True
        assert result.no_live_endpoint is True
        assert result.no_secrets_loaded is True

    def test_happy_path_populates_bc_upstream_fields(
        self, valid_bc_artifact: dict[str, Any]
    ) -> None:
        result = run(bc_artifact=valid_bc_artifact)
        assert (
            result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_status
            == valid_bc_artifact["status"]
        )
        assert (
            result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_scope_summary
            == _VALID_BC_SCOPE_SUMMARY
        )

    def test_happy_path_populates_bc_to_bb_chained_proof_fields(
        self, valid_bc_artifact: dict[str, Any]
    ) -> None:
        result = run(bc_artifact=valid_bc_artifact)
        assert (
            result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_consumed_contract_version
            == valid_bc_artifact["consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_contract_version"]
        )
        assert (
            result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_scope_summary
            == _VALID_BB_SCOPE_SUMMARY
        )

    def test_hard_fail_gates_frozenset_size_is_37(self) -> None:
        # FIX1: BD hardens one extra Group B phrase ("TASK-014BC consumes
        # TASK-014AV") into the enforced set, lifting BD's hard-fail gate
        # count from BC's baseline of 36 to 37.
        assert isinstance(_HARD_FAIL_GATES, frozenset)
        assert len(_HARD_FAIL_GATES) == 37

    def test_happy_path_scope_summary_mentions_bools_set_True(
        self, valid_bc_artifact: dict[str, Any]
    ) -> None:
        result = run(bc_artifact=valid_bc_artifact)
        assert result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_scope_summary_mentions_bb_direct_upstream is True
        assert result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_scope_summary_mentions_bb_proven_chained_proof is True


# ===========================================================================
# Group BD01 -- Group A: BC artifact / field gates
# ===========================================================================

class TestBD01BCUpstreamGates:

    def test_missing_bc_artifact_fails_closed_with_GATE_BC_ARTIFACT_MISSING(
        self, tmp_path: Path
    ) -> None:
        # No artifact / no path.
        result = run()
        _assert_fail_closed_invariants(result, GATE_BC_ARTIFACT_MISSING)
        # Explicit but non-existent path.
        result2 = run(bc_artifact_path=tmp_path / "nope.json")
        _assert_fail_closed_invariants(result2, GATE_BC_ARTIFACT_MISSING)

    def test_bc_status_unacceptable_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory(status="SOME_OTHER_STATUS")
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_STATUS_UNACCEPTABLE)

    def test_bc_mode_mismatch_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory(mode="some_other_mode")
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_MODE_MISMATCH)

    def test_bc_conclusion_mismatch_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory()
        a["disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_conclusion"] = "WRONG_CONCLUSION"
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_CONCLUSION_MISMATCH)

    def test_bc_response_status_mismatch_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory(response_status="WRONG_RESPONSE_STATUS")
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_RESPONSE_STATUS_MISMATCH)

    def test_bc_authorization_result_mismatch_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory()
        a["disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_authorization_result"] = "WRONG"
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_AUTHORIZATION_RESULT_MISMATCH)

    def test_bc_next_required_task_mismatch_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory(next_required_task="TASK-014ZZ_some_other_task")
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_NEXT_REQUIRED_TASK_MISMATCH)

    def test_bc_real_execution_allowed_True_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory(real_execution_allowed=True)
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_REAL_EXECUTION_ALLOWED_TRUE)

    def test_bc_send_allowed_True_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory(send_allowed=True)
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_SEND_ALLOWED_TRUE)

    def test_bc_adapter_implementation_included_True_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory(adapter_implementation_included=True)
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_ADAPTER_IMPLEMENTATION_INCLUDED_TRUE)

    def test_bc_adapter_execution_included_True_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory(adapter_execution_included=True)
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_ADAPTER_EXECUTION_INCLUDED_TRUE)

    def test_bc_order_endpoint_called_True_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory(order_endpoint_called=True)
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_ORDER_ENDPOINT_CALLED_TRUE)

    def test_bc_stop_endpoint_called_True_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory(stop_endpoint_called=True)
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_STOP_ENDPOINT_CALLED_TRUE)

    def test_bc_no_position_modified_False_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory(no_position_modified=False)
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_NO_POSITION_MODIFIED_FALSE)

    def test_bc_no_secrets_loaded_False_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory(no_secrets_loaded=False)
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_NO_SECRETS_LOADED_FALSE)

    def test_bc_g20_lifted_True_fails_closed(self, bc_artifact_factory) -> None:
        a = bc_artifact_factory(g20_lifted=True)
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_G20_LIFTED_TRUE)

    def test_bc_missing_bb_chained_proof_fails_closed(self, bc_artifact_factory) -> None:
        # Empty out the BB contract version + BB status (BC->BB chained
        # proof envelope) --> GATE_BC_MISSING_BB_CHAINED_PROOF.
        a = bc_artifact_factory()
        a["consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_contract_version"] = ""
        a["upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_status"] = ""
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BC_MISSING_BB_CHAINED_PROOF)

    def test_bc_missing_bb_proven_chained_proof_fails_closed(self, bc_artifact_factory) -> None:
        # BC scope_summary lacks "BB-proven chained proof" -> the
        # proven-chained-proof Group A gate fires.
        a = bc_artifact_factory(
            scope_summary=(
                "TASK-014BC consumes TASK-014BB but without the magic "
                "phrase about chained proof."
            )
        )
        result = run(bc_artifact=a)
        _assert_fail_closed_invariants(
            result, GATE_BC_MISSING_BB_PROVEN_CHAINED_PROOF
        )


# ===========================================================================
# Group BD02 -- Group B: BC scope_summary content gates (forbidden phrases)
# ===========================================================================

class TestBD02BCScopeSummaryGates:

    def test_bc_scope_summary_contains_bc_consumes_ba_fails_closed(self, valid_bc_artifact) -> None:
        bad = dict(valid_bc_artifact) | {
            "scope_summary": _VALID_BC_SCOPE_SUMMARY + " TASK-014BC consumes TASK-014BA"
        }
        result = run(bc_artifact=bad)
        _assert_fail_closed_invariants(
            result, GATE_BC_SCOPE_SUMMARY_HAS_BC_CONSUMES_BA
        )

    def test_bc_scope_summary_contains_bc_consumes_az_fails_closed(self, valid_bc_artifact) -> None:
        bad = dict(valid_bc_artifact) | {
            "scope_summary": _VALID_BC_SCOPE_SUMMARY + " TASK-014BC consumes TASK-014AZ"
        }
        result = run(bc_artifact=bad)
        _assert_fail_closed_invariants(
            result, GATE_BC_SCOPE_SUMMARY_HAS_BC_CONSUMES_AZ
        )

    def test_bc_scope_summary_contains_bc_consumes_ay_fails_closed(self, valid_bc_artifact) -> None:
        bad = dict(valid_bc_artifact) | {
            "scope_summary": _VALID_BC_SCOPE_SUMMARY + " TASK-014BC consumes TASK-014AY"
        }
        result = run(bc_artifact=bad)
        _assert_fail_closed_invariants(
            result, GATE_BC_SCOPE_SUMMARY_HAS_BC_CONSUMES_AY
        )

    def test_bc_scope_summary_contains_bc_consumes_ax_fails_closed(self, valid_bc_artifact) -> None:
        bad = dict(valid_bc_artifact) | {
            "scope_summary": _VALID_BC_SCOPE_SUMMARY + " TASK-014BC consumes TASK-014AX"
        }
        result = run(bc_artifact=bad)
        _assert_fail_closed_invariants(
            result, GATE_BC_SCOPE_SUMMARY_HAS_BC_CONSUMES_AX
        )

    def test_bc_scope_summary_contains_bc_consumes_aw_fails_closed(self, valid_bc_artifact) -> None:
        bad = dict(valid_bc_artifact) | {
            "scope_summary": _VALID_BC_SCOPE_SUMMARY + " TASK-014BC consumes TASK-014AW"
        }
        result = run(bc_artifact=bad)
        _assert_fail_closed_invariants(
            result, GATE_BC_SCOPE_SUMMARY_HAS_BC_CONSUMES_AW
        )

    def test_bc_scope_summary_contains_bc_consumes_av_fails_closed(self, valid_bc_artifact) -> None:
        # FIX1: BD hardens AV as a Group B forbidden direct-consumption
        # phrase (count: 36 -> 37).  BC's scope_summary references AV
        # only as BB-proven chained proof; any direct "BC consumes AV"
        # wording from upstream invalidates that chain and must fail
        # closed.
        bad = dict(valid_bc_artifact) | {
            "scope_summary": _VALID_BC_SCOPE_SUMMARY + " TASK-014BC consumes TASK-014AV"
        }
        result = run(bc_artifact=bad)
        _assert_fail_closed_invariants(
            result, GATE_BC_SCOPE_SUMMARY_HAS_BC_CONSUMES_AV
        )

    def test_bc_scope_summary_contains_Itdocuments_fails_closed(self, valid_bc_artifact) -> None:
        bad = dict(valid_bc_artifact) | {
            "scope_summary": _VALID_BC_SCOPE_SUMMARY + " Itdocuments the BB review."
        }
        result = run(bc_artifact=bad)
        _assert_fail_closed_invariants(
            result, GATE_BC_SCOPE_SUMMARY_HAS_ITDOCUMENTS_TYPO
        )


# ===========================================================================
# Group BD03 -- Group C: BC failure passthrough
# ===========================================================================

class TestBD03BCFailurePassthrough:

    def test_bc_status_FAIL_CLOSED_fails_closed(self, valid_bc_artifact) -> None:
        bad = dict(valid_bc_artifact) | {"status": STATUS_FAIL_CLOSED}
        result = run(bc_artifact=bad)
        _assert_fail_closed_invariants(result, GATE_BC_STATUS_FAIL_CLOSED)

    def test_bc_mode_fail_closed_fails_closed(self, valid_bc_artifact) -> None:
        bad = dict(valid_bc_artifact) | {"mode": MODE_FAIL_CLOSED}
        result = run(bc_artifact=bad)
        _assert_fail_closed_invariants(result, GATE_BC_MODE_FAIL_CLOSED)

    def test_bc_failed_stage_non_empty_fails_closed(self, valid_bc_artifact) -> None:
        bad = dict(valid_bc_artifact) | {"failed_stage": "stage_X_some_failure"}
        result = run(bc_artifact=bad)
        _assert_fail_closed_invariants(result, GATE_BC_FAILED_STAGE_NON_EMPTY)


# ===========================================================================
# Group BD04 -- Group D: BD own-source self-introspection invariants
# ===========================================================================

class TestBD04GroupDSafetyGates:
    """Static greps over BD's own source -- these must pass for clean BD."""

    @classmethod
    def setup_class(cls) -> None:
        cls.source = SRC_PATH.read_text(encoding="utf-8")
        cls.lines = cls.source.splitlines()
        cls.preview_source = PREVIEW_PATH.read_text(encoding="utf-8")
        cls.preview_lines = cls.preview_source.splitlines()

    def _active_import_lines(self, lines) -> list[str]:
        out: list[str] = []
        for ln in lines:
            s = ln.lstrip()
            if s.startswith("#"):
                continue
            if s.startswith("import ") or s.startswith("from "):
                out.append(s)
        return out

    def test_bd_src_module_does_not_import_socket(self) -> None:
        for ln in self._active_import_lines(self.lines):
            assert not ln.startswith("import socket"), ln
            assert not ln.startswith("from socket"), ln

    def test_bd_src_module_does_not_import_requests(self) -> None:
        for ln in self._active_import_lines(self.lines):
            assert not ln.startswith("import requests"), ln
            assert not ln.startswith("from requests"), ln

    def test_bd_src_module_does_not_import_urllib_or_httpx_or_websockets_or_aiohttp(self) -> None:
        forbidden_prefixes = (
            "import urllib", "from urllib",
            "import httpx", "from httpx",
            "import websockets", "from websockets",
            "import aiohttp", "from aiohttp",
            "import http.client", "from http.client",
        )
        for ln in self._active_import_lines(self.lines):
            for prefix in forbidden_prefixes:
                assert not ln.startswith(prefix), (
                    f"BD src must not have active import {ln!r}"
                )

    def test_bd_preview_module_does_not_import_socket_requests_urllib_etc(self) -> None:
        forbidden_prefixes = (
            "import socket", "from socket",
            "import requests", "from requests",
            "import urllib", "from urllib",
            "import httpx", "from httpx",
            "import websockets", "from websockets",
            "import aiohttp", "from aiohttp",
            "import http.client", "from http.client",
            "import hmac", "from hmac",
            "import dotenv", "from dotenv",
            "import pybit", "from pybit",
        )
        for ln in self._active_import_lines(self.preview_lines):
            for prefix in forbidden_prefixes:
                assert not ln.startswith(prefix), (
                    f"BD preview must not have active import {ln!r}"
                )

    def test_bd_src_module_does_not_reference_secrets_dotenv_hmac_or_signing(self) -> None:
        bad_call_phrases = (
            "os.environ[", "os.environ.get(",
            "os.getenv(",
            "load_dotenv(",
            "hmac.new(",
            "hashlib.sha256(",
        )
        for ln in self.lines:
            stripped = ln.lstrip()
            if stripped.startswith("#"):
                continue
            for phrase in bad_call_phrases:
                assert phrase not in ln, (
                    f"BD src must not have call site {phrase!r}: {ln!r}"
                )

    def test_bd_src_module_does_not_reference_main_or_src_risk_or_bybitexecutor(self) -> None:
        for ln in self._active_import_lines(self.lines):
            assert not ln.startswith("from main"), ln
            assert not ln.startswith("import main"), ln
            assert not ln.startswith("from src.risk"), ln
            assert not ln.startswith("import src.risk"), ln
            assert "BybitExecutor" not in ln, ln
            assert not ln.startswith("from pybit"), ln
            assert not ln.startswith("import pybit"), ln

    def test_bd_preview_module_does_not_reference_main_or_src_risk_or_bybitexecutor(self) -> None:
        for ln in self._active_import_lines(self.preview_lines):
            assert not ln.startswith("from main"), ln
            assert not ln.startswith("import main"), ln
            assert not ln.startswith("from src.risk"), ln
            assert not ln.startswith("import src.risk"), ln
            assert "BybitExecutor" not in ln, ln

    def test_bd_src_module_has_no_send_place_order_execute_method_defs(self) -> None:
        active_def = re.compile(
            r"^\s*(?:async\s+)?def\s+(send|place_order|execute)\s*\("
        )
        for ln in self.lines:
            stripped = ln.lstrip()
            if stripped.startswith("#"):
                continue
            assert not active_def.match(ln), (
                f"BD src must not define send/place_order/execute method: {ln!r}"
            )

    def test_bd_src_module_does_not_lift_g20(self) -> None:
        bad_phrases = (
            "g20_lifted = True",
            "lift_g20(", "lift_G20(", "disable_g20(", "bypass_g20(",
        )
        for ln in self.lines:
            stripped = ln.lstrip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith('"') or stripped.startswith("'"):
                continue  # docstring / string literal
            for phrase in bad_phrases:
                assert phrase not in ln, (
                    f"BD src must not lift G20: {ln!r}"
                )

    def test_bd_src_module_does_not_modify_positions(self) -> None:
        bad_call_phrases = (
            "modify_position(", "close_position(", "set_leverage(",
            "cancel_order(", "amend_order(", "place_order(",
            "create_order(", "trading_stop(",
        )
        for ln in self.lines:
            stripped = ln.lstrip()
            if stripped.startswith("#"):
                continue
            for phrase in bad_call_phrases:
                assert phrase not in ln, (
                    f"BD src must not call position mutator {phrase!r}: {ln!r}"
                )

    def test_bd_runtime_self_source_gates_do_not_trigger(
        self, valid_bc_artifact: dict[str, Any]
    ) -> None:
        """A clean happy-path run must NOT have any Group D gate."""
        result = run(bc_artifact=valid_bc_artifact)
        group_d_gates = {
            "bd_approval_phrase_treated_as_authorization",
            "bd_live_endpoint_reference_beyond_denylist",
            "bd_network_primitive_or_import",
            "bd_secret_loader_or_hmac_or_signing",
            "bd_sender_or_main_or_risk_or_bybitexecutor_coupling",
            "bd_active_send_place_order_execute_behavior",
            "bd_real_order_or_stop_endpoint_call",
            "bd_g20_lift",
            "bd_position_modification",
        }
        for g in group_d_gates:
            assert g not in result.blocked_gates, (
                f"Group D gate triggered unexpectedly on clean run: {g}"
            )


# ===========================================================================
# Group BD05 -- --allow flag behaviour
# ===========================================================================

class TestBD05AllowFlags:

    def test_allow_readiness_review_flag_returns_READY_BUT_EXECUTION_DISABLED_and_no_execution(
        self, valid_bc_artifact: dict[str, Any]
    ) -> None:
        result = run(
            bc_artifact=valid_bc_artifact,
            allow_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review=True,
        )
        assert result.status == STATUS_READY_BUT_EXECUTION_DISABLED
        # No execution-side flag may have flipped.
        assert result.real_execution_allowed is False
        assert result.send_allowed is False
        assert result.no_orders_sent is True
        assert result.no_position_modified is True
        assert result.g20_lifted is False
        assert result.executable_adapter_included is False
        assert result.adapter_implementation_included is False
        assert result.adapter_execution_included is False
        assert result.send_method_included is False
        assert result.place_order_method_included is False
        assert result.execute_method_included is False
        assert result.manual_authorization_review_readiness_review_grants_execution is False
        assert result.order_endpoint_called is False
        assert result.stop_endpoint_called is False

    def test_allow_real_entry_execution_returns_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED_and_no_execution(
        self, valid_bc_artifact: dict[str, Any]
    ) -> None:
        result = run(
            bc_artifact=valid_bc_artifact,
            allow_real_entry_execution=True,
        )
        assert result.status == STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
        assert result.real_execution_allowed is False
        assert result.send_allowed is False
        assert result.no_orders_sent is True
        assert result.no_position_modified is True
        assert result.g20_lifted is False
        assert result.real_entry_implemented is False
        # Even though we asked for real entry, no socket, no endpoint, no order.
        assert result.order_endpoint_called is False
        assert result.stop_endpoint_called is False


# ===========================================================================
# Group BD06 -- CLI subprocess integration
# ===========================================================================

class TestBD06CLIIntegration:

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env["COLUMNS"] = "400"
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run(
            [sys.executable, str(PREVIEW_PATH), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            env=env,
            timeout=120,
        )

    def test_cli_help_mentions_full_phase_name(self) -> None:
        proc = self._run_cli("--help")
        assert proc.returncode == 0, proc.stderr
        text = proc.stdout
        assert "DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW READINESS REVIEW" in text

    def test_cli_help_says_bc_is_dry_run_and_bd_is_readiness_review(self) -> None:
        proc = self._run_cli("--help")
        assert proc.returncode == 0
        text = proc.stdout
        # The exact disambiguation wording from the parser description.
        assert "BC is the dry-run; BD is the readiness review" in text

    def test_cli_help_does_not_describe_bd_as_dry_run(self) -> None:
        proc = self._run_cli("--help")
        assert proc.returncode == 0
        text = proc.stdout
        forbidden_descriptions = (
            "TASK-014BD dry run",
            "TASK-014BD dry-run",
            "BD dry-run review",
            "BD manual authorization review dry-run",
            "BD is the dry-run",
            "BD is a dry-run",
        )
        for phrase in forbidden_descriptions:
            assert phrase not in text, (
                f"CLI --help describes BD as dry-run via {phrase!r}"
            )

    def test_cli_help_does_not_describe_bc_as_readiness_review(self) -> None:
        proc = self._run_cli("--help")
        assert proc.returncode == 0
        text = proc.stdout
        forbidden_descriptions = (
            "TASK-014BC readiness review",
            "TASK-014BC readiness-review",
            "BC readiness review output",
            "BC is the readiness review",
            "BC is a readiness review",
        )
        for phrase in forbidden_descriptions:
            assert phrase not in text, (
                f"CLI --help describes BC as readiness review via {phrase!r}"
            )

    def test_cli_help_does_not_imply_real_execution(self) -> None:
        proc = self._run_cli("--help")
        assert proc.returncode == 0
        text = proc.stdout
        forbidden = (
            "--execute-real",
            "--send-order",
            "--place-order",
            "--real-run",
            "--confirm-token",
            "--auto-commit",
            "--git-commit",
            "--auto-push",
            "--git-push",
        )
        for token in forbidden:
            assert token not in text, (
                f"CLI help unexpectedly exposes {token!r}"
            )

    def test_cli_help_lists_all_required_flags(self) -> None:
        proc = self._run_cli("--help")
        assert proc.returncode == 0
        text = proc.stdout
        required = (
            "--from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review-dry-run",
            "--bc-artifact-path",
            "--symbol",
            "--expected-commit-hash",
            "--allow-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review-readiness-review",
            "--allow-real-entry-execution",
            "--write-report",
            "--output-dir",
        )
        for flag in required:
            assert flag in text, f"CLI --help missing flag {flag!r}"

    def test_cli_valid_subprocess_with_synthetic_bc_artifact_exits_0(
        self, tmp_path: Path, valid_bc_artifact: dict[str, Any]
    ) -> None:
        bc_path = tmp_path / "bc.json"
        bc_path.write_text(json.dumps(valid_bc_artifact), encoding="utf-8")
        out_dir = tmp_path / "bd_out"
        proc = self._run_cli(
            "--bc-artifact-path", str(bc_path),
            "--symbol", "SOLUSDT",
            "--write-report",
            "--output-dir", str(out_dir),
        )
        assert proc.returncode == 0, (
            f"CLI failed: returncode={proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
        assert STATUS_READY in proc.stdout
        # Report files should exist.
        assert any(out_dir.glob("latest_*.json"))
        assert any(out_dir.glob("latest_*.md"))

    def test_cli_missing_bc_artifact_exits_1(self, tmp_path: Path) -> None:
        missing_path = tmp_path / "does_not_exist.json"
        proc = self._run_cli(
            "--bc-artifact-path", str(missing_path),
            "--symbol", "SOLUSDT",
        )
        assert proc.returncode == 1, (
            f"Expected exit 1 but got {proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
        assert STATUS_FAIL_CLOSED in proc.stdout

    def test_cli_expected_commit_hash_is_record_only_not_authorization(
        self, tmp_path: Path, valid_bc_artifact: dict[str, Any]
    ) -> None:
        """--expected-commit-hash MUST appear in stdout but MUST NOT promote
        the run to real execution."""
        bc_path = tmp_path / "bc.json"
        bc_path.write_text(json.dumps(valid_bc_artifact), encoding="utf-8")
        proc = self._run_cli(
            "--bc-artifact-path", str(bc_path),
            "--symbol", "SOLUSDT",
            "--expected-commit-hash", "abc1234recordedonly",
        )
        assert proc.returncode == 0
        assert "abc1234recordedonly" in proc.stdout
        # Even with an "expected commit hash", real_execution_allowed
        # is False and STATUS_READY (NOT a real-execution status).
        assert STATUS_READY in proc.stdout
        assert "real_execution_allowed                     : False" in proc.stdout


# ===========================================================================
# Group BD07 -- write_report on-disk JSON + Markdown
# ===========================================================================

class TestBD07WriteReport:

    def _written(
        self, valid_bc_artifact: dict[str, Any], bd_output_dir: Path
    ) -> dict[str, Path]:
        result = run(bc_artifact=valid_bc_artifact)
        return write_report(result, bd_output_dir)

    def test_write_report_creates_four_files(
        self, valid_bc_artifact, bd_output_dir
    ) -> None:
        paths = self._written(valid_bc_artifact, bd_output_dir)
        assert set(paths.keys()) == {
            "latest_json", "latest_md", "timestamped_json", "timestamped_md"
        }
        for key, p in paths.items():
            assert p.exists(), f"{key} path {p} does not exist"

    def test_write_report_creates_latest_json(
        self, valid_bc_artifact, bd_output_dir
    ) -> None:
        paths = self._written(valid_bc_artifact, bd_output_dir)
        assert paths["latest_json"].exists()
        assert paths["latest_json"].name.startswith("latest_")
        assert paths["latest_json"].suffix == ".json"

    def test_write_report_creates_latest_md(
        self, valid_bc_artifact, bd_output_dir
    ) -> None:
        paths = self._written(valid_bc_artifact, bd_output_dir)
        assert paths["latest_md"].exists()
        assert paths["latest_md"].name.startswith("latest_")
        assert paths["latest_md"].suffix == ".md"

    def test_write_report_creates_timestamped_json(
        self, valid_bc_artifact, bd_output_dir
    ) -> None:
        paths = self._written(valid_bc_artifact, bd_output_dir)
        assert paths["timestamped_json"].exists()
        assert paths["timestamped_json"].suffix == ".json"
        assert paths["timestamped_json"].name != paths["latest_json"].name
        # Must end with a Z marker on the timestamp.
        assert "Z" in paths["timestamped_json"].name

    def test_write_report_creates_timestamped_md(
        self, valid_bc_artifact, bd_output_dir
    ) -> None:
        paths = self._written(valid_bc_artifact, bd_output_dir)
        assert paths["timestamped_md"].exists()
        assert paths["timestamped_md"].suffix == ".md"
        assert paths["timestamped_md"].name != paths["latest_md"].name

    # ----- Field-presence tests for JSON / Markdown -----

    _BC_UPSTREAM_KEYS = (
        "consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_contract_version",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_mode",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_conclusion",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_authorization_result",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_response_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_real_execution_allowed",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_send_allowed",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_adapter_implementation_included",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_adapter_execution_included",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_order_endpoint_called",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_stop_endpoint_called",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_no_position_modified",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_no_secrets_loaded",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_g20_lifted",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_next_required_task",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_scope_summary",
    )

    _CHAINED_PROOF_KEYS = (
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_consumed_contract_version",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_next_required_task",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_scope_summary",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_scope_summary_mentions_bb_direct_upstream",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_scope_summary_mentions_bb_proven_chained_proof",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_scope_summary_has_no_bc_consumes_ba",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_scope_summary_has_no_bc_consumes_az",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_scope_summary_has_no_bc_consumes_ay",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_scope_summary_has_no_bc_consumes_ax",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_scope_summary_has_no_itdocuments_typo",
    )

    def test_generated_json_contains_all_17_bc_upstream_fields(
        self, valid_bc_artifact, bd_output_dir
    ) -> None:
        paths = self._written(valid_bc_artifact, bd_output_dir)
        data = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
        assert len(self._BC_UPSTREAM_KEYS) == 17
        for k in self._BC_UPSTREAM_KEYS:
            assert k in data, f"JSON missing BC-upstream key {k!r}"

    def test_generated_markdown_contains_all_17_bc_upstream_field_labels(
        self, valid_bc_artifact, bd_output_dir
    ) -> None:
        paths = self._written(valid_bc_artifact, bd_output_dir)
        md = paths["latest_md"].read_text(encoding="utf-8")
        for k in self._BC_UPSTREAM_KEYS:
            assert k in md, f"Markdown missing BC-upstream key {k!r}"

    def test_generated_json_contains_all_11_bc_to_bb_chained_proof_fields(
        self, valid_bc_artifact, bd_output_dir
    ) -> None:
        paths = self._written(valid_bc_artifact, bd_output_dir)
        data = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
        assert len(self._CHAINED_PROOF_KEYS) == 11
        for k in self._CHAINED_PROOF_KEYS:
            assert k in data, f"JSON missing chained-proof key {k!r}"

    def test_generated_markdown_contains_bc_to_bb_chained_proof_labels(
        self, valid_bc_artifact, bd_output_dir
    ) -> None:
        paths = self._written(valid_bc_artifact, bd_output_dir)
        md = paths["latest_md"].read_text(encoding="utf-8")
        assert "BC-proven chained proof" in md
        for k in self._CHAINED_PROOF_KEYS:
            assert k in md, f"Markdown missing chained-proof key {k!r}"

    def test_generated_json_scope_summary_contains_bd_consumes_bc_and_bc_proven_chained_proof(
        self, valid_bc_artifact, bd_output_dir
    ) -> None:
        paths = self._written(valid_bc_artifact, bd_output_dir)
        data = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
        scope = data["scope_summary"]
        assert "TASK-014BD consumes TASK-014BC" in scope
        assert "BC-proven chained proof" in scope

    def test_generated_markdown_scope_summary_contains_bd_consumes_bc_and_bc_proven_chained_proof(
        self, valid_bc_artifact, bd_output_dir
    ) -> None:
        paths = self._written(valid_bc_artifact, bd_output_dir)
        md = paths["latest_md"].read_text(encoding="utf-8")
        assert "TASK-014BD consumes TASK-014BC" in md
        assert "BC-proven chained proof" in md

    # ---- Negative grep tests: JSON ----

    @pytest.mark.parametrize("forbidden", [
        "TASK-014BD consumes TASK-014BB",
        "TASK-014BD consumes TASK-014BA",
        "TASK-014BD consumes TASK-014AZ",
        "TASK-014BD consumes TASK-014AY",
        "TASK-014BD consumes TASK-014AX",
        "TASK-014BD consumes TASK-014AW",
        "TASK-014BD consumes TASK-014AV",
        "TASK-014BD consumes TASK-014AU",
        "TASK-014BD consumes TASK-014AT",
        "TASK-014BD consumes TASK-014AS",
        "TASK-014BD consumes TASK-014AR",
        "TASK-014BD consumes TASK-014AQ",
    ])
    def test_generated_json_scope_summary_does_not_say_bd_consumes_other(
        self, valid_bc_artifact, bd_output_dir, forbidden
    ) -> None:
        paths = self._written(valid_bc_artifact, bd_output_dir)
        data = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
        assert forbidden not in data["scope_summary"], (
            f"BD scope_summary in JSON contains forbidden phrase {forbidden!r}"
        )

    # ---- Negative grep tests: Markdown ----

    @pytest.mark.parametrize("forbidden", [
        "TASK-014BD consumes TASK-014BB",
        "TASK-014BD consumes TASK-014BA",
        "TASK-014BD consumes TASK-014AZ",
        "TASK-014BD consumes TASK-014AY",
        "TASK-014BD consumes TASK-014AX",
        "TASK-014BD consumes TASK-014AW",
        "TASK-014BD consumes TASK-014AV",
        "TASK-014BD consumes TASK-014AU",
        "TASK-014BD consumes TASK-014AT",
        "TASK-014BD consumes TASK-014AS",
        "TASK-014BD consumes TASK-014AR",
        "TASK-014BD consumes TASK-014AQ",
    ])
    def test_generated_markdown_does_not_say_bd_consumes_other(
        self, valid_bc_artifact, bd_output_dir, forbidden
    ) -> None:
        paths = self._written(valid_bc_artifact, bd_output_dir)
        md = paths["latest_md"].read_text(encoding="utf-8")
        assert forbidden not in md, (
            f"BD report Markdown contains forbidden phrase {forbidden!r}"
        )

    def test_generated_report_header_says_bd_consumes_task_014bc_dry_run_output(
        self, valid_bc_artifact, bd_output_dir
    ) -> None:
        paths = self._written(valid_bc_artifact, bd_output_dir)
        md = paths["latest_md"].read_text(encoding="utf-8")
        expected = (
            "TASK-014BD consumes TASK-014BC disabled implementation "
            "scaffold manual authorization gate final pre-execution "
            "review manual authorization review dry-run output."
        )
        assert expected in md, (
            f"Expected exact header line {expected!r} in markdown report"
        )

    def test_generated_report_does_not_describe_bd_as_dry_run(
        self, valid_bc_artifact, bd_output_dir
    ) -> None:
        """BD is the readiness review; BC is the dry-run.  The BD report
        must NEVER describe BD as a dry-run."""
        paths = self._written(valid_bc_artifact, bd_output_dir)
        md = paths["latest_md"].read_text(encoding="utf-8")
        forbidden_descriptions = (
            "TASK-014BD dry run",
            "TASK-014BD dry-run",
            "BD dry-run review",
            "BD readiness review dry run",
        )
        for phrase in forbidden_descriptions:
            assert phrase not in md, (
                f"BD report describes BD as dry-run via {phrase!r}"
            )

    def test_generated_report_correctly_describes_bc_as_dry_run(
        self, valid_bc_artifact, bd_output_dir
    ) -> None:
        """BC is the dry-run; the BD header explicitly references BC's
        dry-run output."""
        paths = self._written(valid_bc_artifact, bd_output_dir)
        md = paths["latest_md"].read_text(encoding="utf-8")
        assert (
            "TASK-014BC disabled implementation scaffold manual "
            "authorization gate final pre-execution review manual "
            "authorization review dry-run output"
        ) in md


# ===========================================================================
# Group BD08 -- Identity wording
# ===========================================================================

class TestBD08IdentityWording:

    def test_identity_checklist_contains_readiness_review_checklist_wording(self) -> None:
        assert (
            "DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE "
            "FINAL PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW "
            "READINESS REVIEW CHECKLIST"
        ) == IDENTITY_CHECKLIST

    def test_identity_strict_contains_readiness_review_only_suffix(self) -> None:
        assert (
            "STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-"
            "GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-"
            "READINESS-REVIEW-ONLY"
        ) == IDENTITY_STRICT

    def test_identity_strict_is_not_just_manual_authorization_review_only(self) -> None:
        # Must NOT degrade to BB-style "MANUAL-AUTHORIZATION-REVIEW-ONLY"
        # without the READINESS-REVIEW suffix.
        assert IDENTITY_STRICT != (
            "STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-"
            "GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-ONLY"
        )
        assert not IDENTITY_STRICT.endswith(
            "MANUAL-AUTHORIZATION-REVIEW-ONLY"
        )

    def test_identity_strict_does_not_say_dry_run_only(self) -> None:
        assert not IDENTITY_STRICT.endswith("DRY-RUN-ONLY")

    def test_identity_strict_does_not_say_final_pre_execution_review_only(self) -> None:
        assert not IDENTITY_STRICT.endswith("FINAL-PRE-EXECUTION-REVIEW-ONLY")

    def test_identity_strict_does_not_say_design_only(self) -> None:
        assert not IDENTITY_STRICT.endswith("DESIGN-ONLY")

    def test_scope_summary_literal_starts_with_bd_consumes_bc(self) -> None:
        assert SCOPE_SUMMARY_LITERAL.startswith(
            "TASK-014BD consumes TASK-014BC"
        )

    def test_scope_summary_literal_contains_bc_proven_chained_proof(self) -> None:
        assert "BC-proven chained proof" in SCOPE_SUMMARY_LITERAL

    def test_next_required_task_targets_TASK_014BE_final_pre_execution_review(self) -> None:
        assert "TASK-014BE" in NEXT_REQUIRED_TASK
        assert NEXT_REQUIRED_TASK.endswith("_final_pre_execution_review")

    def test_adapter_identity_constants(self) -> None:
        assert ADAPTER_NAME == "GuardedTinyEntryRealExecutionAdapter"
        assert "manual_authorization_review_readiness_review_v1" in ADAPTER_CONTRACT_VERSION


# ===========================================================================
# Group BD09 -- Untouched files regression
# ===========================================================================

class TestBD09UntouchedFiles:

    _FORBIDDEN_BD_TOKENS = (
        "manual_authorization_review_readiness_review",
        "TASK-014BD",
        "demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review",
    )

    def test_main_py_untouched_no_bd_references(self) -> None:
        main_py = ROOT / "main.py"
        if not main_py.exists():
            pytest.skip("main.py not present")
        text = main_py.read_text(encoding="utf-8", errors="replace")
        for token in self._FORBIDDEN_BD_TOKENS:
            assert token not in text, (
                f"main.py unexpectedly references BD token {token!r}"
            )

    def test_src_risk_py_untouched_no_bd_references(self) -> None:
        risk_py = ROOT / "src" / "risk.py"
        if not risk_py.exists():
            pytest.skip("src/risk.py not present")
        text = risk_py.read_text(encoding="utf-8", errors="replace")
        for token in self._FORBIDDEN_BD_TOKENS:
            assert token not in text, (
                f"src/risk.py unexpectedly references BD token {token!r}"
            )

    def test_bybitexecutor_untouched_no_bd_references(self) -> None:
        candidates: list[Path] = []
        for p in (ROOT / "src").rglob("*.py"):
            try:
                t = p.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            if "class BybitExecutor" in t or "BybitExecutor =" in t:
                candidates.append(p)
        if not candidates:
            pytest.skip("BybitExecutor source not present")
        for path in candidates:
            t = path.read_text(encoding="utf-8", errors="replace")
            for token in self._FORBIDDEN_BD_TOKENS:
                assert token not in t, (
                    f"{path} unexpectedly references BD token {token!r}"
                )


# ===========================================================================
# Group BD10 -- BC loader round-trip + serialization
# ===========================================================================

class TestBD10BCLoader:

    def test_load_bc_artifact_roundtrip(
        self, tmp_path: Path, valid_bc_artifact: dict[str, Any]
    ) -> None:
        f = tmp_path / "bc.json"
        f.write_text(json.dumps(valid_bc_artifact), encoding="utf-8")
        loaded = _load_bc_dry_run_artifact(f)
        assert loaded is not None
        assert loaded["status"] == valid_bc_artifact["status"]

    def test_load_bc_artifact_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert _load_bc_dry_run_artifact(tmp_path / "nope.json") is None

    def test_load_bc_artifact_invalid_json_returns_none(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text("not json {", encoding="utf-8")
        assert _load_bc_dry_run_artifact(f) is None

    def test_to_dict_round_trips_via_json(
        self, valid_bc_artifact: dict[str, Any]
    ) -> None:
        result = run(bc_artifact=valid_bc_artifact)
        d = result.to_dict()
        text = json.dumps(d)
        parsed = json.loads(text)
        assert parsed["status"] == result.status
        assert parsed["scope_summary"] == result.scope_summary
        assert parsed["next_required_task"] == result.next_required_task

    def test_bd_default_output_dir_targets_readiness_review_subdir(self) -> None:
        s = str(BD_DEFAULT_OUTPUT_DIR).replace("\\", "/")
        assert s.endswith(
            "tiny_guarded_entry_real_execution_adapter_disabled_"
            "implementation_scaffold_manual_authorization_gate_final_"
            "pre_execution_review_manual_authorization_review_"
            "readiness_review"
        )


# ===========================================================================
# Group BD11 -- BC-bypass-as-authorization negative proof
# ===========================================================================

class TestBD11NoAuthorizationViaInputs:
    """Even if the caller tries to claim authorization via input text or
    promotional flags, BD must NEVER set real_execution_allowed True."""

    def test_allow_readiness_review_does_not_grant_execution_anywhere(
        self, valid_bc_artifact: dict[str, Any]
    ) -> None:
        result = run(
            bc_artifact=valid_bc_artifact,
            allow_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review=True,
        )
        assert result.manual_authorization_review_readiness_review_grants_execution is False
        assert result.manual_authorization_review_dry_run_grants_execution is False
        assert result.manual_authorization_review_grants_execution is False
        assert result.manual_authorization_gate_final_pre_execution_review_grants_execution is False
        assert result.manual_authorization_gate_readiness_review_grants_execution is False
        assert result.manual_authorization_gate_dry_run_grants_execution is False
        assert result.manual_authorization_gate_design_grants_execution is False
        assert result.final_pre_execution_review_grants_execution is False
        assert result.readiness_review_grants_execution is False
        assert result.dry_run_grants_execution is False
        assert result.adapter_grants_execution is False
        assert result.approval_phrase_grants_execution is False
        assert result.approval_token_grants_execution is False
        assert result.approval_inputs_grant_execution is False
        assert result.token_to_authorization_mapping is False
        assert result.phrase_to_authorization_mapping is False
        assert result.manual_authorization_review_readiness_review_accepts_runtime_approval is False
        assert result.manual_authorization_review_readiness_review_translates_text_to_execution is False
