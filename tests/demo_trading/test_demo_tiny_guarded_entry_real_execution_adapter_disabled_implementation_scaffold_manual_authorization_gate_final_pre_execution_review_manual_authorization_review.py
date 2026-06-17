"""
Full Stage 3 test pack for TASK-014BB
src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.py

Stage 3 is the comprehensive BB test pack: core run / Group A / Group B /
Group C / Group D safety, --allow flag behaviour, CLI subprocess
integration, write_report on-disk JSON+Markdown inspection, identity
wording grep, and untouched-file regression. The narrower Stage 1
suite (`*_stage1.py`) remains a focused smaller proof; this file is the
primary BB regression pack.

Every fail-closed test asserts:
  * result.status == STATUS_FAIL_CLOSED
  * the specific gate name is in result.blocked_gates
  * real_execution_allowed / send_allowed stay False
  * no_orders_sent stays True
  * g20_lifted stays False
  * no_position_modified stays True

TASK-014BB is a STRICT manual-authorization-review-only module: it never
opens a socket, never reads secrets, never calls any endpoint, never
modifies any position, never lifts G20, and never authorizes any real
execution.  The tests below prove that contract holds end-to-end.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from src.demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review import (
    ADAPTER_CONTRACT_VERSION,
    ADAPTER_NAME,
    AUTHORIZATION_RESULT_DOCUMENTED,
    BB_DEFAULT_OUTPUT_DIR,
    CONCLUSION_READY_NOT_EXECUTABLE,
    GATE_BA_ADAPTER_EXECUTION_INCLUDED_TRUE,
    GATE_BA_ADAPTER_IMPLEMENTATION_INCLUDED_TRUE,
    GATE_BA_ARTIFACT_MISSING,
    GATE_BA_AUTHORIZATION_RESULT_MISMATCH,
    GATE_BA_AZ_CHAINED_PROOF_MISSING,
    GATE_BA_AZ_DIRECT_PROOF_MISSING,
    GATE_BA_CONCLUSION_MISMATCH,
    GATE_BA_FAILED_STAGE_NON_EMPTY,
    GATE_BA_G20_LIFTED_TRUE,
    GATE_BA_MODE_FAIL_CLOSED,
    GATE_BA_MODE_MISMATCH,
    GATE_BA_NEXT_REQUIRED_TASK_MISMATCH,
    GATE_BA_NO_POSITION_MODIFIED_FALSE,
    GATE_BA_NO_SECRETS_LOADED_FALSE,
    GATE_BA_ORDER_ENDPOINT_CALLED_TRUE,
    GATE_BA_REAL_EXECUTION_ALLOWED_TRUE,
    GATE_BA_RESPONSE_STATUS_MISMATCH,
    GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AV,
    GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AW,
    GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AX,
    GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AY,
    GATE_BA_SCOPE_SUMMARY_CONTAINS_ITDOCUMENTS_TYPO,
    GATE_BA_SCOPE_SUMMARY_MISSING_AZ_DIRECT,
    GATE_BA_SEND_ALLOWED_TRUE,
    GATE_BA_STATUS_FAIL_CLOSED,
    GATE_BA_STATUS_UNACCEPTABLE,
    GATE_BA_STOP_ENDPOINT_CALLED_TRUE,
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
    STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED,
    TinyGuardedEntryRealExecutionAdapterDisabledImplementationScaffoldManualAuthorizationGateFinalPreExecutionReviewManualAuthorizationReviewResult as BBResult,
    _HARD_FAIL_GATES,
    _load_ba_final_pre_execution_review_artifact,
    run_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review as run,
    write_report,
)

ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = ROOT / (
    "src/demo_tiny_guarded_entry_real_execution_adapter_disabled_"
    "implementation_scaffold_manual_authorization_gate_final_pre_"
    "execution_review_manual_authorization_review.py"
)
PREVIEW_PATH = ROOT / (
    "scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_"
    "disabled_implementation_scaffold_manual_authorization_gate_final_"
    "pre_execution_review_manual_authorization_review.py"
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_VALID_BA_SCOPE_SUMMARY = (
    "TASK-014BA consumes TASK-014AZ DISABLED IMPLEMENTATION "
    "SCAFFOLD MANUAL AUTHORIZATION GATE READINESS REVIEW output "
    "at runtime plus AZ-proven chained proof, including AY "
    "dry-run, AX manual authorization gate design, AW final "
    "pre-execution review, AV readiness review, AU dry-run, AT "
    "design, AS static skeleton dry-run, AR static skeleton "
    "design, and AQ implementation design."
)


def _valid_ba_artifact() -> dict[str, Any]:
    """Construct a fresh, fully populated synthetic BA artifact dict."""
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
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope": {
            "scope_summary": _VALID_BA_SCOPE_SUMMARY,
        },
        "implementation_design_scope": {
            "scope_summary": _VALID_BA_SCOPE_SUMMARY,
        },
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
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run_status": (
            "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_"
            "IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DRY_RUN_READY"
        ),
    }


@pytest.fixture
def valid_ba_artifact() -> dict[str, Any]:
    return _valid_ba_artifact()


@pytest.fixture
def ba_artifact_factory():
    """
    Return a factory `make(**overrides)` that builds a valid BA artifact
    with the given top-level overrides applied.
    """
    def _make(**overrides: Any) -> dict[str, Any]:
        d = _valid_ba_artifact()
        d.update(overrides)
        return d
    return _make


@pytest.fixture
def bb_output_dir(tmp_path: Path) -> Path:
    p = tmp_path / "bb_out"
    p.mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture
def bb_artifact_path(tmp_path: Path, valid_ba_artifact: dict[str, Any]) -> Path:
    p = tmp_path / "ba_artifact.json"
    p.write_text(json.dumps(valid_ba_artifact), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Helper assertions
# ---------------------------------------------------------------------------

def _assert_fail_closed_invariants(
    result: BBResult, expected_gate: str
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
# Group BB00 -- Happy path
# ===========================================================================

class TestBB00CoreRun:

    def test_happy_path_with_valid_synthetic_ba_artifact_returns_READY(
        self, valid_ba_artifact: dict[str, Any]
    ) -> None:
        result = run(ba_artifact=valid_ba_artifact)
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

    def test_happy_path_populates_ba_upstream_fields(
        self, valid_ba_artifact: dict[str, Any]
    ) -> None:
        result = run(ba_artifact=valid_ba_artifact)
        assert (
            result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_status
            == valid_ba_artifact["status"]
        )
        assert (
            result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary
            == _VALID_BA_SCOPE_SUMMARY
        )

    def test_happy_path_populates_az_chained_proof_fields(
        self, valid_ba_artifact: dict[str, Any]
    ) -> None:
        result = run(ba_artifact=valid_ba_artifact)
        assert (
            result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_consumed_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_contract_version
            == valid_ba_artifact["consumed_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_contract_version"]
        )
        assert (
            result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run_status
            == valid_ba_artifact["upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run_status"]
        )

    def test_hard_fail_gates_frozenset_size_is_36(self) -> None:
        assert isinstance(_HARD_FAIL_GATES, frozenset)
        assert len(_HARD_FAIL_GATES) == 36


# ===========================================================================
# Group BB01 -- Group A: BA artifact / field gates
# ===========================================================================

class TestBB01BAUpstreamGates:

    def test_missing_ba_artifact_fails_closed_with_GATE_BA_ARTIFACT_MISSING(
        self, tmp_path: Path
    ) -> None:
        # No artifact / no path.
        result = run()
        _assert_fail_closed_invariants(result, GATE_BA_ARTIFACT_MISSING)
        # Explicit but non-existent path.
        result2 = run(ba_artifact_path=tmp_path / "nope.json")
        _assert_fail_closed_invariants(result2, GATE_BA_ARTIFACT_MISSING)

    def test_ba_status_unacceptable_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory(status="SOME_OTHER_STATUS")
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_STATUS_UNACCEPTABLE)

    def test_ba_mode_mismatch_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory(mode="some_other_mode")
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_MODE_MISMATCH)

    def test_ba_conclusion_mismatch_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory()
        a["disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_conclusion"] = "WRONG_CONCLUSION"
        a.pop("implementation_design_conclusion", None)
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_CONCLUSION_MISMATCH)

    def test_ba_response_status_mismatch_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory(response_status="WRONG_RESPONSE_STATUS")
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_RESPONSE_STATUS_MISMATCH)

    def test_ba_authorization_result_mismatch_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory()
        a["disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_authorization_result"] = "WRONG"
        a.pop("implementation_design_authorization_result", None)
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_AUTHORIZATION_RESULT_MISMATCH)

    def test_ba_next_required_task_mismatch_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory(next_required_task="TASK-014BZ_some_other_task")
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_NEXT_REQUIRED_TASK_MISMATCH)

    def test_ba_real_execution_allowed_True_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory(real_execution_allowed=True)
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_REAL_EXECUTION_ALLOWED_TRUE)

    def test_ba_send_allowed_True_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory(send_allowed=True)
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_SEND_ALLOWED_TRUE)

    def test_ba_adapter_implementation_included_True_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory(adapter_implementation_included=True)
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_ADAPTER_IMPLEMENTATION_INCLUDED_TRUE)

    def test_ba_adapter_execution_included_True_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory(adapter_execution_included=True)
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_ADAPTER_EXECUTION_INCLUDED_TRUE)

    def test_ba_order_endpoint_called_True_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory(order_endpoint_called=True)
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_ORDER_ENDPOINT_CALLED_TRUE)

    def test_ba_stop_endpoint_called_True_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory(stop_endpoint_called=True)
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_STOP_ENDPOINT_CALLED_TRUE)

    def test_ba_no_position_modified_False_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory(no_position_modified=False)
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_NO_POSITION_MODIFIED_FALSE)

    def test_ba_no_secrets_loaded_False_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory(no_secrets_loaded=False)
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_NO_SECRETS_LOADED_FALSE)

    def test_ba_g20_lifted_True_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory(g20_lifted=True)
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_G20_LIFTED_TRUE)

    def test_ba_az_direct_proof_missing_fails_closed(self, ba_artifact_factory) -> None:
        # Empty out BA's AZ readiness review contract version --> AZ
        # direct proof missing.
        a = ba_artifact_factory()
        a["consumed_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_contract_version"] = ""
        a["upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_status"] = ""
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_AZ_DIRECT_PROOF_MISSING)

    def test_ba_az_chained_proof_missing_fails_closed(self, ba_artifact_factory) -> None:
        a = ba_artifact_factory()
        a["upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run_status"] = ""
        result = run(ba_artifact=a)
        _assert_fail_closed_invariants(result, GATE_BA_AZ_CHAINED_PROOF_MISSING)


# ===========================================================================
# Group BB02 -- Group B: BA scope_summary content gates
# ===========================================================================

class TestBB02BAScopeSummaryGates:

    def _mutate_scope(self, artifact: dict[str, Any], new_summary: str) -> None:
        artifact[
            "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope"
        ]["scope_summary"] = new_summary
        artifact["implementation_design_scope"]["scope_summary"] = new_summary

    def test_ba_scope_summary_missing_az_direct_fails_closed(self, valid_ba_artifact) -> None:
        self._mutate_scope(
            valid_ba_artifact,
            "summary without the required direct upstream phrase",
        )
        result = run(ba_artifact=valid_ba_artifact)
        _assert_fail_closed_invariants(
            result, GATE_BA_SCOPE_SUMMARY_MISSING_AZ_DIRECT
        )

    def test_ba_scope_summary_contains_ba_consumes_ay_fails_closed(self, valid_ba_artifact) -> None:
        self._mutate_scope(
            valid_ba_artifact,
            _VALID_BA_SCOPE_SUMMARY + " TASK-014BA consumes TASK-014AY",
        )
        result = run(ba_artifact=valid_ba_artifact)
        _assert_fail_closed_invariants(
            result, GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AY
        )

    def test_ba_scope_summary_contains_ba_consumes_ax_fails_closed(self, valid_ba_artifact) -> None:
        self._mutate_scope(
            valid_ba_artifact,
            _VALID_BA_SCOPE_SUMMARY + " TASK-014BA consumes TASK-014AX",
        )
        result = run(ba_artifact=valid_ba_artifact)
        _assert_fail_closed_invariants(
            result, GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AX
        )

    def test_ba_scope_summary_contains_ba_consumes_aw_fails_closed(self, valid_ba_artifact) -> None:
        self._mutate_scope(
            valid_ba_artifact,
            _VALID_BA_SCOPE_SUMMARY + " TASK-014BA consumes TASK-014AW",
        )
        result = run(ba_artifact=valid_ba_artifact)
        _assert_fail_closed_invariants(
            result, GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AW
        )

    def test_ba_scope_summary_contains_ba_consumes_av_fails_closed(self, valid_ba_artifact) -> None:
        self._mutate_scope(
            valid_ba_artifact,
            _VALID_BA_SCOPE_SUMMARY + " TASK-014BA consumes TASK-014AV",
        )
        result = run(ba_artifact=valid_ba_artifact)
        _assert_fail_closed_invariants(
            result, GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AV
        )

    def test_ba_scope_summary_contains_Itdocuments_fails_closed(self, valid_ba_artifact) -> None:
        self._mutate_scope(
            valid_ba_artifact,
            _VALID_BA_SCOPE_SUMMARY + " Itdocuments the AZ readiness review.",
        )
        result = run(ba_artifact=valid_ba_artifact)
        _assert_fail_closed_invariants(
            result, GATE_BA_SCOPE_SUMMARY_CONTAINS_ITDOCUMENTS_TYPO
        )


# ===========================================================================
# Group BB03 -- Group C: BA failure passthrough
# ===========================================================================

class TestBB03BAFailurePassthrough:

    def test_ba_status_FAIL_CLOSED_fails_closed(self, valid_ba_artifact) -> None:
        valid_ba_artifact["status"] = STATUS_FAIL_CLOSED
        result = run(ba_artifact=valid_ba_artifact)
        _assert_fail_closed_invariants(result, GATE_BA_STATUS_FAIL_CLOSED)

    def test_ba_mode_fail_closed_fails_closed(self, valid_ba_artifact) -> None:
        valid_ba_artifact["mode"] = MODE_FAIL_CLOSED
        result = run(ba_artifact=valid_ba_artifact)
        _assert_fail_closed_invariants(result, GATE_BA_MODE_FAIL_CLOSED)

    def test_ba_failed_stage_non_empty_fails_closed(self, valid_ba_artifact) -> None:
        valid_ba_artifact["failed_stage"] = "stage_5_some_failure"
        result = run(ba_artifact=valid_ba_artifact)
        _assert_fail_closed_invariants(result, GATE_BA_FAILED_STAGE_NON_EMPTY)


# ===========================================================================
# Group BB04 -- Group D: BB own-source self-introspection invariants
# ===========================================================================

class TestBB04GroupDSafetyGates:
    """Static greps over BB's own source -- these must pass for clean BB."""

    @classmethod
    def setup_class(cls) -> None:
        cls.source = SRC_PATH.read_text(encoding="utf-8")
        # Strip out the pattern-definition denylist tuples / single-quoted
        # literals that legitimately mention the forbidden substrings.
        # For the active-import / coupling tests we only want to find
        # ACTIVE constructs (i.e. lines starting with the import statement).
        cls.lines = cls.source.splitlines()

    def _active_import_lines(self) -> list[str]:
        out: list[str] = []
        for ln in self.lines:
            s = ln.lstrip()
            if s.startswith("#"):
                continue
            if s.startswith("import ") or s.startswith("from "):
                out.append(s)
        return out

    def test_bb_module_does_not_import_socket(self) -> None:
        for ln in self._active_import_lines():
            assert not ln.startswith("import socket"), ln
            assert not ln.startswith("from socket"), ln

    def test_bb_module_does_not_import_requests(self) -> None:
        for ln in self._active_import_lines():
            assert not ln.startswith("import requests"), ln
            assert not ln.startswith("from requests"), ln

    def test_bb_module_does_not_import_urllib_or_httpx_or_websockets_or_aiohttp(self) -> None:
        forbidden_prefixes = (
            "import urllib", "from urllib",
            "import httpx", "from httpx",
            "import websockets", "from websockets",
            "import aiohttp", "from aiohttp",
            "import http.client", "from http.client",
        )
        for ln in self._active_import_lines():
            for prefix in forbidden_prefixes:
                assert not ln.startswith(prefix), (
                    f"BB must not have active import {ln!r}"
                )

    def test_bb_module_does_not_reference_secrets_dotenv_hmac_or_signing(self) -> None:
        # Inspect non-comment, non-string code lines.  We allow these
        # tokens to appear inside string-literal denylist definitions
        # (those occur as part of `_SECRET_SIGNING_PATTERNS = (...)`)
        # but never as active call sites.
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
                    f"BB must not have call site {phrase!r}: {ln!r}"
                )

    def test_bb_module_does_not_reference_main_or_src_risk_or_bybitexecutor(self) -> None:
        for ln in self._active_import_lines():
            assert not ln.startswith("from main"), ln
            assert not ln.startswith("import main"), ln
            assert not ln.startswith("from src.risk"), ln
            assert not ln.startswith("import src.risk"), ln
            assert "BybitExecutor" not in ln, ln
            assert not ln.startswith("from pybit"), ln
            assert not ln.startswith("import pybit"), ln

    def test_bb_module_has_no_send_place_order_execute_method_defs(self) -> None:
        import re
        active_def = re.compile(
            r"^\s*(?:async\s+)?def\s+(send|place_order|execute)\s*\("
        )
        for ln in self.lines:
            stripped = ln.lstrip()
            if stripped.startswith("#"):
                continue
            assert not active_def.match(ln), (
                f"BB must not define send/place_order/execute method: {ln!r}"
            )

    def test_bb_module_does_not_lift_g20(self) -> None:
        # Active assignments of g20_lifted to True must not appear.
        # The src does have `result.g20_lifted = False` (re-assertion);
        # that's fine.
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
                    f"BB must not lift G20: {ln!r}"
                )

    def test_bb_module_does_not_modify_positions(self) -> None:
        # No active calls to position-mutation primitives.
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
                    f"BB must not call position mutator {phrase!r}: {ln!r}"
                )

    def test_bb_runtime_self_source_gates_do_not_trigger(
        self, valid_ba_artifact: dict[str, Any]
    ) -> None:
        """A clean happy-path run must NOT have any Group D gate."""
        result = run(ba_artifact=valid_ba_artifact)
        group_d_gates = {
            "bb_approval_input_treated_as_authorization",
            "bb_live_endpoint_reference_beyond_denylist",
            "bb_network_primitive_or_import",
            "bb_secret_loader_or_hmac_or_signing",
            "bb_sender_or_main_or_risk_or_bybitexecutor_coupling",
            "bb_active_send_place_order_execute_behavior",
            "bb_real_order_or_stop_endpoint_call",
            "bb_g20_lift",
            "bb_position_modification",
        }
        for g in group_d_gates:
            assert g not in result.blocked_gates, (
                f"Group D gate triggered unexpectedly on clean run: {g}"
            )


# ===========================================================================
# Group BB05 -- --allow flag behaviour
# ===========================================================================

class TestBB05AllowFlags:

    def test_allow_manual_authorization_review_flag_returns_READY_BUT_EXECUTION_DISABLED_and_no_execution(
        self, valid_ba_artifact: dict[str, Any]
    ) -> None:
        result = run(
            ba_artifact=valid_ba_artifact,
            allow_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review=True,
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
        assert result.manual_authorization_review_grants_execution is False

    def test_allow_real_entry_execution_returns_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED_and_no_execution(
        self, valid_ba_artifact: dict[str, Any]
    ) -> None:
        result = run(
            ba_artifact=valid_ba_artifact,
            allow_real_entry_execution=True,
        )
        assert result.status == STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
        assert result.real_execution_allowed is False
        assert result.send_allowed is False
        assert result.no_orders_sent is True
        assert result.no_position_modified is True
        assert result.g20_lifted is False
        assert result.real_entry_implemented is False


# ===========================================================================
# Group BB06 -- CLI subprocess integration
# ===========================================================================

class TestBB06CLIIntegration:

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
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
        assert "DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW" in text

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
            "--from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review",
            "--ba-artifact-path",
            "--symbol",
            "--expected-commit-hash",
            "--allow-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review",
            "--allow-real-entry-execution",
            "--write-report",
            "--output-dir",
        )
        for flag in required:
            assert flag in text, f"CLI --help missing flag {flag!r}"

    def test_cli_valid_subprocess_with_synthetic_ba_artifact_exits_0(
        self, tmp_path: Path, valid_ba_artifact: dict[str, Any]
    ) -> None:
        ba_path = tmp_path / "ba.json"
        ba_path.write_text(json.dumps(valid_ba_artifact), encoding="utf-8")
        out_dir = tmp_path / "bb_out"
        proc = self._run_cli(
            "--ba-artifact-path", str(ba_path),
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

    def test_cli_missing_ba_artifact_exits_1(self, tmp_path: Path) -> None:
        missing_path = tmp_path / "does_not_exist.json"
        proc = self._run_cli(
            "--ba-artifact-path", str(missing_path),
            "--symbol", "SOLUSDT",
        )
        assert proc.returncode == 1, (
            f"Expected exit 1 but got {proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
        assert STATUS_FAIL_CLOSED in proc.stdout


# ===========================================================================
# Group BB07 -- write_report on-disk JSON + Markdown
# ===========================================================================

class TestBB07WriteReport:

    def _written(
        self, valid_ba_artifact: dict[str, Any], bb_output_dir: Path
    ) -> dict[str, Path]:
        result = run(ba_artifact=valid_ba_artifact)
        return write_report(result, bb_output_dir)

    def test_write_report_creates_latest_json(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        assert paths["json_path"].exists()
        assert paths["json_path"].name.startswith("latest_")
        assert paths["json_path"].suffix == ".json"

    def test_write_report_creates_latest_md(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        assert paths["md_path"].exists()
        assert paths["md_path"].name.startswith("latest_")
        assert paths["md_path"].suffix == ".md"

    def test_write_report_creates_timestamped_json(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        assert paths["timestamped_json_path"].exists()
        assert "Z." in paths["timestamped_json_path"].name or paths["timestamped_json_path"].name.endswith("Z.json")
        assert paths["timestamped_json_path"].suffix == ".json"
        assert paths["timestamped_json_path"].name != paths["json_path"].name

    def test_write_report_creates_timestamped_md(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        assert paths["timestamped_md_path"].exists()
        assert paths["timestamped_md_path"].suffix == ".md"
        assert paths["timestamped_md_path"].name != paths["md_path"].name

    # ----- Field-presence tests for JSON / Markdown -----

    _BA_UPSTREAM_KEYS = (
        "consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_contract_version",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_mode",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_conclusion",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_authorization_result",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_response_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_real_execution_allowed",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_send_allowed",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_adapter_implementation_included",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_adapter_execution_included",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_order_endpoint_called",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_stop_endpoint_called",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_no_position_modified",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_no_secrets_loaded",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_g20_lifted",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_next_required_task",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary",
    )

    _CHAINED_PROOF_KEYS = (
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_consumed_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_contract_version",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_response_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_next_required_task",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_mentions_az_direct_upstream",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_ay",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_ax",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_aw",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_av",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_itdocuments_typo",
    )

    def test_generated_json_contains_all_17_ba_upstream_fields(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        data = json.loads(paths["json_path"].read_text(encoding="utf-8"))
        assert len(self._BA_UPSTREAM_KEYS) == 17
        for k in self._BA_UPSTREAM_KEYS:
            assert k in data, f"JSON missing BA-upstream key {k!r}"

    def test_generated_markdown_contains_all_17_ba_upstream_fields(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        md = paths["md_path"].read_text(encoding="utf-8")
        for k in self._BA_UPSTREAM_KEYS:
            assert k in md, f"Markdown missing BA-upstream key {k!r}"

    def test_generated_json_contains_all_11_ba_to_az_chained_proof_fields(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        data = json.loads(paths["json_path"].read_text(encoding="utf-8"))
        assert len(self._CHAINED_PROOF_KEYS) == 11
        for k in self._CHAINED_PROOF_KEYS:
            assert k in data, f"JSON missing chained-proof key {k!r}"

    def test_generated_markdown_contains_all_11_ba_to_az_chained_proof_fields(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        md = paths["md_path"].read_text(encoding="utf-8")
        for k in self._CHAINED_PROOF_KEYS:
            assert k in md, f"Markdown missing chained-proof key {k!r}"

    def test_generated_json_scope_summary_contains_bb_consumes_ba_and_ba_proven_chained_proof(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        data = json.loads(paths["json_path"].read_text(encoding="utf-8"))
        scope = data["scope_summary"]
        assert "TASK-014BB consumes TASK-014BA" in scope
        assert "BA-proven chained proof" in scope

    def test_generated_markdown_scope_summary_contains_bb_consumes_ba_and_ba_proven_chained_proof(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        md = paths["md_path"].read_text(encoding="utf-8")
        assert "TASK-014BB consumes TASK-014BA" in md
        assert "BA-proven chained proof" in md

    def test_generated_json_does_not_say_bb_consumes_az_directly(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        data = json.loads(paths["json_path"].read_text(encoding="utf-8"))
        assert "TASK-014BB consumes TASK-014AZ" not in data["scope_summary"]

    def test_generated_json_does_not_say_bb_consumes_ay_directly(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        data = json.loads(paths["json_path"].read_text(encoding="utf-8"))
        assert "TASK-014BB consumes TASK-014AY" not in data["scope_summary"]

    def test_generated_json_does_not_say_bb_consumes_ax_directly(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        data = json.loads(paths["json_path"].read_text(encoding="utf-8"))
        assert "TASK-014BB consumes TASK-014AX" not in data["scope_summary"]

    def test_generated_json_does_not_say_bb_consumes_aw_directly(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        data = json.loads(paths["json_path"].read_text(encoding="utf-8"))
        assert "TASK-014BB consumes TASK-014AW" not in data["scope_summary"]

    def test_generated_json_does_not_say_bb_consumes_av_directly(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        data = json.loads(paths["json_path"].read_text(encoding="utf-8"))
        assert "TASK-014BB consumes TASK-014AV" not in data["scope_summary"]

    def test_generated_markdown_does_not_say_bb_consumes_az_directly(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        md = paths["md_path"].read_text(encoding="utf-8")
        # Allow the chained-proof reference "AZ readiness review" but
        # forbid the literal "TASK-014BB consumes TASK-014AZ" phrasing.
        assert "TASK-014BB consumes TASK-014AZ" not in md

    def test_generated_markdown_does_not_say_bb_consumes_ay_directly(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        md = paths["md_path"].read_text(encoding="utf-8")
        assert "TASK-014BB consumes TASK-014AY" not in md

    def test_generated_markdown_does_not_say_bb_consumes_ax_directly(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        md = paths["md_path"].read_text(encoding="utf-8")
        assert "TASK-014BB consumes TASK-014AX" not in md

    def test_generated_markdown_does_not_say_bb_consumes_aw_directly(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        md = paths["md_path"].read_text(encoding="utf-8")
        assert "TASK-014BB consumes TASK-014AW" not in md

    def test_generated_markdown_does_not_say_bb_consumes_av_directly(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        md = paths["md_path"].read_text(encoding="utf-8")
        assert "TASK-014BB consumes TASK-014AV" not in md

    def test_generated_report_header_says_bb_consumes_task_014ba_final_pre_execution_review_output(
        self, valid_ba_artifact, bb_output_dir
    ) -> None:
        paths = self._written(valid_ba_artifact, bb_output_dir)
        md = paths["md_path"].read_text(encoding="utf-8")
        assert "TASK-014BB consumes TASK-014BA" in md
        assert "final pre-execution review output" in md


# ===========================================================================
# Group BB08 -- Identity wording
# ===========================================================================

class TestBB08IdentityWording:

    def test_identity_says_final_pre_execution_review_manual_authorization_review_only(self) -> None:
        assert "MANUAL-AUTHORIZATION-REVIEW-ONLY" in IDENTITY_STRICT
        assert "FINAL-PRE-EXECUTION-REVIEW" in IDENTITY_STRICT

    def test_identity_does_not_say_only_final_pre_execution_review_only(self) -> None:
        # IDENTITY_STRICT must not stop at FINAL-PRE-EXECUTION-REVIEW-ONLY;
        # it must continue into MANUAL-AUTHORIZATION-REVIEW-ONLY.
        assert not IDENTITY_STRICT.endswith("FINAL-PRE-EXECUTION-REVIEW-ONLY")

    def test_identity_does_not_say_readiness_review_only(self) -> None:
        assert "READINESS-REVIEW-ONLY" not in IDENTITY_STRICT

    def test_identity_does_not_say_dry_run_only(self) -> None:
        assert "DRY-RUN-ONLY" not in IDENTITY_STRICT

    def test_identity_does_not_say_design_only(self) -> None:
        assert "DESIGN-ONLY" not in IDENTITY_STRICT

    def test_scope_summary_literal_starts_with_bb_consumes_ba(self) -> None:
        assert SCOPE_SUMMARY_LITERAL.startswith(
            "TASK-014BB consumes TASK-014BA"
        )

    def test_next_required_task_targets_TASK_014BC_dry_run(self) -> None:
        assert "TASK-014BC" in NEXT_REQUIRED_TASK
        assert NEXT_REQUIRED_TASK.endswith("_dry_run")

    def test_adapter_identity_constants(self) -> None:
        assert ADAPTER_NAME == "GuardedTinyEntryRealExecutionAdapter"
        assert "manual_authorization_review_v1" in ADAPTER_CONTRACT_VERSION


# ===========================================================================
# Group BB09 -- Untouched files regression
# ===========================================================================

class TestBB09UntouchedFiles:

    def test_main_py_untouched_no_bb_references(self) -> None:
        main_py = ROOT / "main.py"
        if not main_py.exists():
            pytest.skip("main.py not present")
        text = main_py.read_text(encoding="utf-8", errors="replace")
        forbidden = (
            "manual_authorization_review",
            "TASK-014BB",
            "demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review",
        )
        for token in forbidden:
            assert token not in text, (
                f"main.py unexpectedly references BB token {token!r}"
            )

    def test_src_risk_py_untouched_no_bb_references(self) -> None:
        risk_py = ROOT / "src" / "risk.py"
        if not risk_py.exists():
            pytest.skip("src/risk.py not present")
        text = risk_py.read_text(encoding="utf-8", errors="replace")
        forbidden = (
            "manual_authorization_review",
            "TASK-014BB",
            "demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review",
        )
        for token in forbidden:
            assert token not in text, (
                f"src/risk.py unexpectedly references BB token {token!r}"
            )

    def test_bybitexecutor_untouched_no_bb_references(self) -> None:
        # Search for any module containing "BybitExecutor" definition.
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
            forbidden = (
                "manual_authorization_review",
                "TASK-014BB",
                "demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review",
            )
            for token in forbidden:
                assert token not in t, (
                    f"{path} unexpectedly references BB token {token!r}"
                )


# ===========================================================================
# Group BB10 -- BA loader round-trip + serialization
# ===========================================================================

class TestBB10BALoader:

    def test_load_ba_artifact_roundtrip(
        self, tmp_path: Path, valid_ba_artifact: dict[str, Any]
    ) -> None:
        f = tmp_path / "ba.json"
        f.write_text(json.dumps(valid_ba_artifact), encoding="utf-8")
        loaded = _load_ba_final_pre_execution_review_artifact(f)
        assert loaded is not None
        assert loaded["status"] == valid_ba_artifact["status"]

    def test_load_ba_artifact_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert _load_ba_final_pre_execution_review_artifact(tmp_path / "nope.json") is None

    def test_load_ba_artifact_invalid_json_returns_none(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text("not json {", encoding="utf-8")
        assert _load_ba_final_pre_execution_review_artifact(f) is None

    def test_to_dict_round_trips_via_json(
        self, valid_ba_artifact: dict[str, Any]
    ) -> None:
        result = run(ba_artifact=valid_ba_artifact)
        d = result.to_dict()
        text = json.dumps(d)
        parsed = json.loads(text)
        assert parsed["status"] == result.status
        assert parsed["scope_summary"] == result.scope_summary
        assert parsed["next_required_task"] == result.next_required_task

    def test_bb_default_output_dir_targets_review_subdir(self) -> None:
        s = str(BB_DEFAULT_OUTPUT_DIR).replace("\\", "/")
        assert s.endswith(
            "tiny_guarded_entry_real_execution_adapter_disabled_"
            "implementation_scaffold_manual_authorization_gate_final_"
            "pre_execution_review_manual_authorization_review"
        )
