"""
tests/demo_trading/test_demo_tiny_lifecycle_runner_design.py
TASK-014AB: Tiny Lifecycle Real Execution Runner Design tests
(AB1 - AB48+).

Covers design_checklist / runner_design_approval_dry_run /
real_runner_execution_guard / fail_closed paths; all 8 stages;
68 gate constants split across 8 categories; 18-state runner state
machine; 11-slot per-step audit artifact contract; 3 distinct manual
approval tokens (entry / stop_attach / cleanup); payload contract
(preview_only / qty parity / reduceOnly / stopLoss>0 / stopLoss<entry
ref / no real-payload conversion); abort & fail-closed policy;
observability sanitisation; source-scan safety (no urlopen / no
forbidden imports / no signing / no os.environ); report artifacts;
forbidden-flag absence; and the invariant that TASK-014L sender G20
(protected_entry_policy_missing) still blocks --execute-new-entry and
is NOT lifted here.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import tokenize
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_tiny_lifecycle_runner_design import (
    ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES,
    ALL_STAGES,
    BASE_URL_DEMO_REF,
    CLEANUP_TOKEN_PATTERN,
    DEFAULT_SELECTED_SYMBOL,
    DemoTinyLifecycleRunnerDesign,
    ENTRY_TOKEN_PATTERN,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_PROOF_STRENGTH,
    FORBIDDEN_LOG_FIELDS,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_ARTIFACT_PER_STEP_REQUIRED,
    GATE_CLEANUP_FAIL_CLOSED,
    GATE_CLEANUP_PAYLOAD_PREVIEW_ONLY,
    GATE_CLEANUP_REDUCE_ONLY_TRUE,
    GATE_CLEANUP_TOKEN_PATTERN_PRESENT,
    GATE_CONTRACT_MISSING,
    GATE_DESIGN_ONLY_TRUE,
    GATE_DISCORD_SANITIZED_ONLY,
    GATE_EACH_STEP_SEPARATE_MANUAL_APPROVAL,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_FAIL_CLOSED,
    GATE_ENTRY_PAYLOAD_PREVIEW_ONLY,
    GATE_ENTRY_QTY_EQUALS_CLEANUP_QTY,
    GATE_ENTRY_TOKEN_PATTERN_PRESENT,
    GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW,
    GATE_G20_NOT_LIFTED,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_LIFECYCLE_SUMMARY_MISSING,
    GATE_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE,
    GATE_NEXT_TASK_IS_DRY_RUN_IMPL,
    GATE_NO_AUTO_ADVANCE,
    GATE_NO_AUTO_CLEANUP,
    GATE_NO_AUTO_EMERGENCY_CLOSE,
    GATE_NO_ENDPOINT_INVOKED,
    GATE_NO_G20_LIFT,
    GATE_NO_LIVE_ENDPOINT,
    GATE_NO_PARALLEL_EXECUTION,
    GATE_NO_POSITION_MODIFIED,
    GATE_NO_PREVIEW_TO_REAL_CONVERSION,
    GATE_NO_REAL_ORDER_ENDPOINT,
    GATE_NO_REAL_STOP_ENDPOINT,
    GATE_NO_RETRY_LOOP_FAILURE_POLICY,
    GATE_NO_RETRY_LOOP_STATE_MACHINE,
    GATE_NO_SECRETS_EMITTED,
    GATE_NO_SECRETS_IN_LOGS,
    GATE_NO_SKIP_STEP,
    GATE_NOOP_PLAN_MISSING,
    GATE_NOTION_SANITIZED_ONLY,
    GATE_PARTIAL_FILL_FAIL_CLOSED,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_PROTECTION_MISSING,
    GATE_READONLY_BETWEEN_REAL_STEPS_REQUIRED,
    GATE_READONLY_SMOKE_MISSING,
    GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
    GATE_REAL_EXECUTION_NOT_ALLOWED,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_REAL_RUNNER_EXECUTION_NOT_IMPL,
    GATE_REAL_RUNNER_NOT_IMPLEMENTED,
    GATE_RECONCILIATION_MISSING,
    GATE_REQUIRED_STATES_PRESENT,
    GATE_SANITIZED_RESPONSE_REQUIRED,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_STOP_FAIL_CLOSED,
    GATE_STOP_LOSS_LESS_THAN_ENTRY_REF,
    GATE_STOP_LOSS_POSITIVE,
    GATE_STOP_PAYLOAD_PREVIEW_ONLY,
    GATE_STOP_TOKEN_PATTERN_PRESENT,
    GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
    GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
    GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING,
    GATE_TOKEN_FORMAT_IS_NOT_AUTHORIZATION,
    GATE_TOKENS_DISTINCT,
    GATE_TOKENS_NOT_VALIDATED_IN_THIS_TASK,
    GATE_UNEXPECTED_POSITION_MANUAL_REVIEW,
    MODE_DESIGN_CHECKLIST,
    MODE_FAIL_CLOSED,
    MODE_REAL_RUNNER_EXECUTION_GUARD,
    MODE_RUNNER_DESIGN_APPROVAL_DRY_RUN,
    ORDER_CREATE_PATH_REF,
    POST_REAL_READONLY_STATES,
    REAL_SUBMIT_STATES,
    REQUIRED_AUDIT_ARTIFACTS,
    RUNNER_STATES,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_RUNNER_DESIGN_SCOPE,
    STAGE_2_STATE_MACHINE_DESIGN,
    STAGE_3_MANUAL_APPROVAL_CONTRACT,
    STAGE_4_EXECUTION_PAYLOAD_CONTRACT,
    STAGE_5_ABORT_AND_FAIL_CLOSED_POLICY,
    STAGE_6_OBSERVABILITY_AND_AUDIT_DESIGN,
    STAGE_7_FINAL_DESIGN_VERDICT,
    STATUS_DESIGN_READY,
    STATUS_DESIGN_READY_EXEC_DISABLED,
    STATUS_FAIL_CLOSED,
    STATUS_REAL_RUNNER_NOT_IMPL,
    STOP_ATTACH_TOKEN_PATTERN,
    TRADING_STOP_PATH_REF,
    TinyLifecycleRunnerDesignResult,
)


_MODULE_PATH = ROOT / "src" / "demo_tiny_lifecycle_runner_design.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_tiny_lifecycle_runner_design.py"
_TEST_NOW    = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _valid_readonly() -> dict:
    return {
        "timestamp_utc":          "2026-06-10T10:00:00Z",
        "endpoint_family":        EXPECTED_ENDPOINT_FAMILY,
        "account_mode":           EXPECTED_ACCOUNT_MODE,
        "proof_strength":         EXPECTED_PROOF_STRENGTH,
        "demo_runtime_verified":  True,
        "equity_usd":             500.0,
        "available_balance_usd":  400.0,
    }


def _valid_reconciliation() -> dict:
    return {
        "timestamp_utc":           "2026-06-10T10:05:00Z",
        "mode":                    EXPECTED_POSITION_DETAILS_SOURCE,
        "position_details_source": EXPECTED_POSITION_DETAILS_SOURCE,
        "open_positions_count":    5,
        "positions": [
            {"symbol": "ENAUSDT",   "side": "short", "quantity": 100.0, "entry_price": 0.5, "stop_price": 0.0},
            {"symbol": "TIAUSDT",   "side": "short", "quantity": 50.0,  "entry_price": 2.0, "stop_price": 0.0},
            {"symbol": "AIXBTUSDT", "side": "short", "quantity": 200.0, "entry_price": 0.3, "stop_price": 0.0},
            {"symbol": "POLYXUSDT", "side": "short", "quantity": 300.0, "entry_price": 0.2, "stop_price": 0.0},
            {"symbol": "EDUUSDT",   "side": "short", "quantity": 400.0, "entry_price": 0.4, "stop_price": 0.0},
        ],
    }


def _valid_protection() -> dict:
    return {
        "timestamp_utc":          "2026-06-10T11:00:00Z",
        "selected_symbol":        "SOLUSDT",
        "selected_side":          "long",
        "selected_qty":           12.2,
        "entry_reference_price":  64.87,
        "stop_price":             61.63,
        "protected_entry_status": "PREVIEW_ONLY",
        "preview_only":           True,
    }


def _valid_contract() -> dict:
    return {
        "timestamp_utc":      "2026-06-10T11:30:00Z",
        "mode":               "preview",
        "selected_symbol":    "SOLUSDT",
        "path":               TRADING_STOP_PATH_REF,
        "method":             "POST",
        "real_probe_allowed": False,
        "status":             "TRADING_STOP_CONTRACT_PREVIEW_OK",
    }


def _valid_noop_plan() -> dict:
    return {
        "timestamp_utc":     "2026-06-10T11:45:00Z",
        "mode":              "plan",
        "selected_symbol":   "SOLUSDT",
        "recommended_path":  "real_tiny_position_with_stop_lifecycle",
        "status":            "NOOP_PROBE_PLAN_READY",
    }


def _valid_lifecycle() -> dict:
    return {
        "timestamp_utc":             "2026-06-10T11:55:00Z",
        "mode":                      "mock_lifecycle",
        "selected_symbol":           "SOLUSDT",
        "side":                      "long",
        "tiny_qty":                  0.1,
        "tiny_notional":             6.487,
        "entry_reference_price":     64.87,
        "stop_price":                61.63,
        "status":                    "MOCK_TINY_LIFECYCLE_SUCCESS",
        "failed_phase":              "",
        "dangling_tiny_position":    False,
        "existing_positions_touched": [],
    }


def _valid_real_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-10T11:58:00Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "REAL_PERMISSION_CHECKLIST_READY",
        "real_execution_allowed":              False,
        "real_tiny_position_implemented":      False,
        "current_task_real_execution_allowed": False,
        "real_tiny_position_requested":        False,
    }


def _valid_entry_payload_preview() -> dict:
    return {
        "preview_only":      True,
        "category":          "linear",
        "symbol":            "SOLUSDT",
        "side":              "Buy",
        "orderType":         "Market",
        "qty":               0.1,
        "positionIdx":       0,
        "orderLinkId":       "DRYRUN-TINY-ENTRY-SOLUSDT-20260610",
        "endpoint_path_ref": ORDER_CREATE_PATH_REF,
        "endpoint_called":   False,
    }


def _valid_tiny_entry_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-10T11:59:00Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "TINY_ENTRY_PERMISSION_CHECKLIST_READY",
        "rounded_tiny_qty":          0.1,
        "entry_payload_preview":     _valid_entry_payload_preview(),
        "real_execution_allowed":              False,
        "real_tiny_entry_implemented":         False,
        "current_task_real_execution_allowed": False,
        "real_tiny_entry_requested":           False,
    }


def _valid_stop_payload_preview() -> dict:
    return {
        "preview_only":      True,
        "category":          "linear",
        "symbol":            "SOLUSDT",
        "stopLoss":          61.63,
        "tpslMode":          "Full",
        "slTriggerBy":       "MarkPrice",
        "positionIdx":       0,
        "endpoint_path_ref": TRADING_STOP_PATH_REF,
        "endpoint_called":   False,
    }


def _valid_tiny_stop_attach_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-10T11:59:30Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "TINY_STOP_ATTACH_PERMISSION_CHECKLIST_READY",
        "stop_price":                61.63,
        "stop_payload_preview":      _valid_stop_payload_preview(),
        "real_execution_allowed":              False,
        "real_stop_attach_implemented":        False,
        "current_task_real_execution_allowed": False,
        "real_stop_attach_requested":          False,
    }


def _valid_cleanup_payload_preview() -> dict:
    return {
        "preview_only":      True,
        "category":          "linear",
        "symbol":            "SOLUSDT",
        "side":              "Sell",
        "orderType":         "Market",
        "qty":               0.1,
        "reduceOnly":        True,
        "closeOnTrigger":    False,
        "positionIdx":       0,
        "orderLinkId":       "DRYRUN-TINY-CLEANUP-SOLUSDT-20260610",
        "endpoint_path_ref": ORDER_CREATE_PATH_REF,
        "endpoint_called":   False,
    }


def _valid_tiny_cleanup_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-10T11:59:45Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "TINY_CLEANUP_PERMISSION_CHECKLIST_READY",
        "expected_tiny_qty":         0.1,
        "cleanup_side":              "Sell",
        "cleanup_payload_preview":   _valid_cleanup_payload_preview(),
        "real_execution_allowed":              False,
        "real_cleanup_implemented":            False,
        "current_task_real_execution_allowed": False,
        "real_cleanup_requested":              False,
    }


def _valid_lifecycle_summary() -> dict:
    return {
        "timestamp_utc":                  "2026-06-10T11:59:55Z",
        "mode":                           "checklist",
        "selected_symbol":                "SOLUSDT",
        "status":                         "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY",
        "expected_entry_reference_price": 64.87,
        "entry_payload_preview":          _valid_entry_payload_preview(),
        "stop_payload_preview":           _valid_stop_payload_preview(),
        "cleanup_payload_preview":        _valid_cleanup_payload_preview(),
        "real_execution_allowed":              False,
        "real_lifecycle_runner_implemented":   False,
        "current_task_real_execution_allowed": False,
    }


def _read_code_only(path: Path) -> str:
    tokens: list[str] = []
    with open(path, "rb") as fh:
        for tok in tokenize.tokenize(fh.readline):
            if tok.type in (
                tokenize.STRING, tokenize.COMMENT,
                tokenize.ENCODING, tokenize.NEWLINE, tokenize.NL,
                tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER,
            ):
                continue
            tokens.append(tok.string)
    return " ".join(tokens)


def _gate() -> DemoTinyLifecycleRunnerDesign:
    return DemoTinyLifecycleRunnerDesign()


_UNSET = object()


def _run(
    *,
    readonly=_UNSET, recon=_UNSET, protection=_UNSET, contract=_UNSET,
    noop_plan=_UNSET, lifecycle=_UNSET, real_permission_gate=_UNSET,
    tiny_entry_permission_gate=_UNSET,
    tiny_stop_attach_permission_gate=_UNSET,
    tiny_cleanup_permission_gate=_UNSET,
    lifecycle_summary=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    allow_runner_design_approval=False,
    allow_real_runner_execution=False,
    _now=_TEST_NOW,
) -> TinyLifecycleRunnerDesignResult:
    return _gate().run_checklist(
        readonly_smoke=_valid_readonly()                               if readonly             is _UNSET else readonly,
        reconciliation=_valid_reconciliation()                         if recon                is _UNSET else recon,
        protection=_valid_protection()                                 if protection           is _UNSET else protection,
        contract=_valid_contract()                                     if contract             is _UNSET else contract,
        noop_plan=_valid_noop_plan()                                   if noop_plan            is _UNSET else noop_plan,
        lifecycle_mock=_valid_lifecycle()                              if lifecycle            is _UNSET else lifecycle,
        real_permission_gate=_valid_real_permission_gate()             if real_permission_gate is _UNSET else real_permission_gate,
        tiny_entry_permission_gate=_valid_tiny_entry_permission_gate() if tiny_entry_permission_gate is _UNSET else tiny_entry_permission_gate,
        tiny_stop_attach_permission_gate=_valid_tiny_stop_attach_permission_gate() if tiny_stop_attach_permission_gate is _UNSET else tiny_stop_attach_permission_gate,
        tiny_cleanup_permission_gate=_valid_tiny_cleanup_permission_gate() if tiny_cleanup_permission_gate is _UNSET else tiny_cleanup_permission_gate,
        lifecycle_summary=_valid_lifecycle_summary()                   if lifecycle_summary    is _UNSET else lifecycle_summary,
        symbol=symbol,
        allow_runner_design_approval=allow_runner_design_approval,
        allow_real_runner_execution=allow_real_runner_execution,
        _now=_now,
    )


# ===========================================================================
# AB1: valid design checklist => DESIGN_READY
# ===========================================================================

class TestAB1DesignChecklistReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_DESIGN_READY
        assert r.mode == MODE_DESIGN_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.real_execution_allowed is False
        assert r.real_runner_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.next_required_task == (
            "TASK-014AC_tiny_lifecycle_runner_implementation_dry_run_only"
        )


# ===========================================================================
# AB2: --allow-runner-design-approval => DESIGN_READY_BUT_EXECUTION_DISABLED
# ===========================================================================

class TestAB2RunnerDesignApprovalDryRun:
    def test_promotes_status(self):
        r = _run(allow_runner_design_approval=True)
        assert r.status == STATUS_DESIGN_READY_EXEC_DISABLED
        assert r.mode == MODE_RUNNER_DESIGN_APPROVAL_DRY_RUN
        assert r.runner_design_approval_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_runner_implemented is False
        assert r.current_task_real_execution_allowed is False


# ===========================================================================
# AB3: --allow-real-runner-execution => REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED
# ===========================================================================

class TestAB3RealRunnerExecutionGuard:
    def test_guard_returns_not_impl(self):
        r = _run(allow_real_runner_execution=True)
        assert r.status == STATUS_REAL_RUNNER_NOT_IMPL
        assert r.mode == MODE_REAL_RUNNER_EXECUTION_GUARD
        assert r.real_execution_allowed is False
        assert r.real_runner_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.real_runner_execution_requested is True
        assert GATE_REAL_RUNNER_EXECUTION_NOT_IMPL in r.blocked_gates


# ===========================================================================
# AB4 - AB14: missing upstream artifacts => FAIL_CLOSED  (11 artifacts)
# ===========================================================================

class TestAB4MissingReadonly:
    def test_none(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestAB5MissingReconciliation:
    def test_none(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestAB6MissingProtection:
    def test_none(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestAB7MissingContract:
    def test_none(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestAB8MissingNoopPlan:
    def test_none(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestAB9MissingLifecycle:
    def test_none(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestAB10MissingRealPermissionGate:
    def test_none(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAB11MissingTinyEntryPermissionGate:
    def test_none(self):
        r = _run(tiny_entry_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAB12MissingTinyStopAttachPermissionGate:
    def test_none(self):
        r = _run(tiny_stop_attach_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAB13MissingTinyCleanupPermissionGate:
    def test_none(self):
        r = _run(tiny_cleanup_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAB14MissingLifecycleSummary:
    def test_none(self):
        r = _run(lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


# ===========================================================================
# AB15: selected_symbol collides with an existing position => FAIL_CLOSED
# ===========================================================================

class TestAB15SymbolCollision:
    @pytest.mark.parametrize("sym", list(EXISTING_POSITION_SYMBOLS))
    def test_collision_blocks(self, sym):
        r = _run(symbol=sym)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_COLLIDES_EXISTING in r.blocked_gates


# ===========================================================================
# AB16 - AB19: proof envelope mismatches => FAIL_CLOSED
# ===========================================================================

class TestAB16EndpointFamilyMismatch:
    def test_mainnet(self):
        ro = _valid_readonly(); ro["endpoint_family"] = "bybit_mainnet"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestAB17AccountModeMismatch:
    def test_live(self):
        ro = _valid_readonly(); ro["account_mode"] = "live"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestAB18ProofStrengthMismatch:
    def test_weak(self):
        ro = _valid_readonly(); ro["proof_strength"] = "WEAK"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROOF_STRENGTH_NOT_STRONG in r.blocked_gates


class TestAB19PositionDetailsSourceMismatch:
    def test_synthetic(self):
        rec = _valid_reconciliation()
        rec["mode"] = "synthetic"
        rec["position_details_source"] = "synthetic"
        r = _run(recon=rec)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY in r.blocked_gates


# ===========================================================================
# AB20: lifecycle summary status unacceptable => FAIL_CLOSED
# ===========================================================================

class TestAB20LifecycleSummaryStatusUnacceptable:
    def test_fail_closed(self):
        ls = _valid_lifecycle_summary(); ls["status"] = "FAIL_CLOSED"
        r = _run(lifecycle_summary=ls)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE in r.blocked_gates

    @pytest.mark.parametrize("status", sorted(ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES))
    def test_acceptable_statuses_pass(self, status):
        ls = _valid_lifecycle_summary(); ls["status"] = status
        r = _run(lifecycle_summary=ls)
        assert r.status == STATUS_DESIGN_READY


# ===========================================================================
# AB21 - AB27: payload contract violations => FAIL_CLOSED
# ===========================================================================

class TestAB21EntryPreviewOnly:
    def test_preview_false(self):
        ls = _valid_lifecycle_summary()
        ls["entry_payload_preview"] = {**_valid_entry_payload_preview(), "preview_only": False}
        r = _run(lifecycle_summary=ls)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_PAYLOAD_PREVIEW_ONLY in r.blocked_gates


class TestAB22StopPreviewOnly:
    def test_preview_false(self):
        ls = _valid_lifecycle_summary()
        ls["stop_payload_preview"] = {**_valid_stop_payload_preview(), "preview_only": False}
        r = _run(lifecycle_summary=ls)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_STOP_PAYLOAD_PREVIEW_ONLY in r.blocked_gates


class TestAB23CleanupPreviewOnly:
    def test_preview_false(self):
        ls = _valid_lifecycle_summary()
        ls["cleanup_payload_preview"] = {**_valid_cleanup_payload_preview(), "preview_only": False}
        r = _run(lifecycle_summary=ls)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CLEANUP_PAYLOAD_PREVIEW_ONLY in r.blocked_gates


class TestAB24EntryQtyEqualsCleanupQty:
    def test_qty_mismatch(self):
        ls = _valid_lifecycle_summary()
        ls["cleanup_payload_preview"] = {**_valid_cleanup_payload_preview(), "qty": 0.2}
        r = _run(lifecycle_summary=ls)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_QTY_EQUALS_CLEANUP_QTY in r.blocked_gates


class TestAB25CleanupReduceOnly:
    def test_reduce_only_false(self):
        ls = _valid_lifecycle_summary()
        ls["cleanup_payload_preview"] = {**_valid_cleanup_payload_preview(), "reduceOnly": False}
        r = _run(lifecycle_summary=ls)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CLEANUP_REDUCE_ONLY_TRUE in r.blocked_gates


class TestAB26StopLossPositive:
    def test_zero(self):
        ls = _valid_lifecycle_summary()
        ls["stop_payload_preview"] = {**_valid_stop_payload_preview(), "stopLoss": 0.0}
        r = _run(lifecycle_summary=ls)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_STOP_LOSS_POSITIVE in r.blocked_gates


class TestAB27StopLossLessThanEntryRef:
    def test_stop_above_entry(self):
        ls = _valid_lifecycle_summary()
        ls["stop_payload_preview"] = {**_valid_stop_payload_preview(), "stopLoss": 999.0}
        r = _run(lifecycle_summary=ls)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_STOP_LOSS_LESS_THAN_ENTRY_REF in r.blocked_gates


# ===========================================================================
# AB28: missing symbol => FAIL_CLOSED
# ===========================================================================

class TestAB28MissingSymbol:
    def test_empty_symbol(self):
        r = _run(symbol="")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_MISSING in r.blocked_gates


# ===========================================================================
# AB29: 8 stages built
# ===========================================================================

class TestAB29EightStages:
    def test_eight(self):
        r = _run()
        assert set(r.stages.keys()) == set(ALL_STAGES)
        assert r.stage_order == list(ALL_STAGES)
        assert len(ALL_STAGES) == 8


# ===========================================================================
# AB30: 18-state runner state machine + readonly-after-real invariant
# ===========================================================================

class TestAB30RunnerStateMachine:
    def test_eighteen_states(self):
        r = _run()
        assert len(r.runner_states) == 18
        assert len(RUNNER_STATES) == 18
        # Critical states must be present.
        for s in (
            "INIT",
            "PRE_READONLY_SNAPSHOT_REQUIRED",
            "ENTRY_TOKEN_REQUIRED",
            "ENTRY_READY",
            "ENTRY_SUBMITTED",
            "POST_ENTRY_READONLY_REQUIRED",
            "STOP_TOKEN_REQUIRED",
            "STOP_READY",
            "STOP_SUBMITTED",
            "POST_STOP_READONLY_REQUIRED",
            "CLEANUP_TOKEN_REQUIRED",
            "CLEANUP_READY",
            "CLEANUP_SUBMITTED",
            "POST_CLEANUP_READONLY_REQUIRED",
            "FINAL_AUDIT_REQUIRED",
            "COMPLETE",
            "FAIL_CLOSED",
            "MANUAL_REVIEW_REQUIRED",
        ):
            assert s in r.runner_states

    def test_readonly_after_each_real_step(self):
        r = _run()
        env = r.stages[STAGE_2_STATE_MACHINE_DESIGN]
        sm = env["state_machine_design"]
        assert sm["readonly_between_real_steps_required"] is True
        assert sm["no_auto_advance"] is True
        assert sm["no_parallel_execution"] is True
        assert sm["no_skip_step"] is True
        assert sm["no_retry_loop"] is True
        mapping = sm["readonly_after_real"]
        assert mapping["ENTRY_SUBMITTED"]   == "POST_ENTRY_READONLY_REQUIRED"
        assert mapping["STOP_SUBMITTED"]    == "POST_STOP_READONLY_REQUIRED"
        assert mapping["CLEANUP_SUBMITTED"] == "POST_CLEANUP_READONLY_REQUIRED"
        assert set(sm["real_submit_states"]) == set(REAL_SUBMIT_STATES)
        assert set(sm["post_real_readonly_states"]) == set(POST_REAL_READONLY_STATES)

    def test_always_on_state_machine_gates(self):
        r = _run()
        for g in (
            GATE_REQUIRED_STATES_PRESENT,
            GATE_READONLY_BETWEEN_REAL_STEPS_REQUIRED,
            GATE_NO_AUTO_ADVANCE,
            GATE_NO_PARALLEL_EXECUTION,
            GATE_NO_SKIP_STEP,
            GATE_NO_RETRY_LOOP_STATE_MACHINE,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# AB31: stage_3 manual approval contract (3 distinct tokens)
# ===========================================================================

class TestAB31ManualApprovalContract:
    def test_three_distinct_tokens(self):
        r = _run()
        env = r.stages[STAGE_3_MANUAL_APPROVAL_CONTRACT]
        m = env["manual_approval_contract"]
        assert m["entry_token_pattern"]       == ENTRY_TOKEN_PATTERN
        assert m["stop_attach_token_pattern"] == STOP_ATTACH_TOKEN_PATTERN
        assert m["cleanup_token_pattern"]     == CLEANUP_TOKEN_PATTERN
        assert len({
            ENTRY_TOKEN_PATTERN,
            STOP_ATTACH_TOKEN_PATTERN,
            CLEANUP_TOKEN_PATTERN,
        }) == 3
        assert m["tokens_distinct_per_step"] is True
        assert m["tokens_validated_in_this_task"] is False
        assert m["each_real_step_requires_separate_manual_approval"] is True
        assert m["token_format_alone_is_not_authorization"] is True

    def test_always_on_manual_approval_gates(self):
        r = _run()
        for g in (
            GATE_ENTRY_TOKEN_PATTERN_PRESENT,
            GATE_STOP_TOKEN_PATTERN_PRESENT,
            GATE_CLEANUP_TOKEN_PATTERN_PRESENT,
            GATE_TOKENS_DISTINCT,
            GATE_TOKENS_NOT_VALIDATED_IN_THIS_TASK,
            GATE_EACH_STEP_SEPARATE_MANUAL_APPROVAL,
            GATE_TOKEN_FORMAT_IS_NOT_AUTHORIZATION,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# AB32: stage_4 execution payload contract
# ===========================================================================

class TestAB32ExecutionPayloadContract:
    def test_payload_pulled(self):
        r = _run()
        env = r.stages[STAGE_4_EXECUTION_PAYLOAD_CONTRACT]
        c = env["execution_payload_contract"]
        assert c["entry_preview_only"] is True
        assert c["stop_preview_only"] is True
        assert c["cleanup_preview_only"] is True
        assert c["entry_qty_equals_cleanup_qty"] is True
        assert c["cleanup_reduce_only"] is True
        assert c["stop_loss_positive"] is True
        assert c["stop_loss_less_than_entry_ref"] is True
        assert c["no_preview_to_real_conversion"] is True
        assert c["entry_qty"] == pytest.approx(0.1)
        assert c["cleanup_qty"] == pytest.approx(0.1)
        assert c["stop_loss"] == pytest.approx(61.63)
        assert c["expected_entry_reference_price"] == pytest.approx(64.87)

    def test_no_preview_to_real_conversion_always_on(self):
        r = _run()
        assert GATE_NO_PREVIEW_TO_REAL_CONVERSION in r.blocked_gates


# ===========================================================================
# AB33: stage_5 abort and fail-closed policy
# ===========================================================================

class TestAB33AbortAndFailClosedPolicy:
    def test_matrix_fields(self):
        r = _run()
        env = r.stages[STAGE_5_ABORT_AND_FAIL_CLOSED_POLICY]
        m = env["abort_and_fail_closed_policy"]
        assert m["entry_rejected"]                     == "fail_closed"
        assert m["stop_attach_rejected"]               == "fail_closed"
        assert m["cleanup_rejected"]                   == "fail_closed"
        assert m["readonly_unavailable_between_steps"] == "fail_closed"
        assert m["entry_or_cleanup_partial_fill"]      == "fail_closed"
        assert m["existing_stop_mismatch"]             == "manual_review"
        assert m["unexpected_position_appears"]        == "manual_review"
        assert m["no_automatic_emergency_close"]       is True
        assert m["no_automatic_cleanup"]               is True
        assert m["no_retry_loop_after_failure"]        is True
        assert m["emergency_close_preview_only"]       is True
        assert set(m["expected_existing_position_symbols"]) == set(EXISTING_POSITION_SYMBOLS)

    def test_always_on_failure_policy_gates(self):
        r = _run()
        for g in (
            GATE_ENTRY_FAIL_CLOSED,
            GATE_STOP_FAIL_CLOSED,
            GATE_CLEANUP_FAIL_CLOSED,
            GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
            GATE_PARTIAL_FILL_FAIL_CLOSED,
            GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW,
            GATE_UNEXPECTED_POSITION_MANUAL_REVIEW,
            GATE_NO_AUTO_EMERGENCY_CLOSE,
            GATE_NO_AUTO_CLEANUP,
            GATE_NO_RETRY_LOOP_FAILURE_POLICY,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# AB34: stage_6 observability and audit design (11 required artifacts)
# ===========================================================================

class TestAB34ObservabilityAndAuditDesign:
    def test_eleven_required_artifacts(self):
        r = _run()
        env = r.stages[STAGE_6_OBSERVABILITY_AND_AUDIT_DESIGN]
        o = env["observability_and_audit_design"]
        assert len(o["required_audit_artifacts"]) == 11
        assert o["required_audit_artifacts"] == list(REQUIRED_AUDIT_ARTIFACTS)
        assert o["artifact_per_step_required"] is True
        assert o["sanitized_response_required"] is True
        assert o["no_secrets_in_logs"] is True
        assert o["discord_sanitized_summary_only"] is True
        assert o["notion_sanitized_summary_only"] is True
        # Forbidden log fields documented.
        for f in FORBIDDEN_LOG_FIELDS:
            assert f in o["forbidden_log_fields"]

    def test_always_on_observability_gates(self):
        r = _run()
        for g in (
            GATE_ARTIFACT_PER_STEP_REQUIRED,
            GATE_SANITIZED_RESPONSE_REQUIRED,
            GATE_NO_SECRETS_IN_LOGS,
            GATE_DISCORD_SANITIZED_ONLY,
            GATE_NOTION_SANITIZED_ONLY,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# AB35: stage_7 final design verdict (all guard flags False)
# ===========================================================================

class TestAB35FinalDesignVerdict:
    def test_default_flags(self):
        r = _run()
        env = r.stages[STAGE_7_FINAL_DESIGN_VERDICT]
        v = env["final_design_verdict"]
        assert v["real_execution_allowed"]              is False
        assert v["real_runner_implemented"]             is False
        assert v["current_task_real_execution_allowed"] is False
        assert v["g20_policy_still_in_place"]           is True
        assert v["g20_lifted"]                          is False
        assert v["no_real_order_endpoint"]              is True
        assert v["no_real_stop_endpoint"]               is True
        assert v["no_position_modified"]                is True
        assert v["no_live_endpoint"]                    is True
        assert v["no_secrets_emitted"]                  is True
        assert v["status"] == STATUS_DESIGN_READY

    def test_guard_does_not_flip_real_execution(self):
        r = _run(allow_real_runner_execution=True)
        env = r.stages[STAGE_7_FINAL_DESIGN_VERDICT]
        v = env["final_design_verdict"]
        assert v["real_execution_allowed"] is False
        assert v["real_runner_execution_requested"] is True
        assert v["status"] == STATUS_REAL_RUNNER_NOT_IMPL


# ===========================================================================
# AB36: stage_1 runner design scope
# ===========================================================================

class TestAB36RunnerDesignScope:
    def test_scope_fields(self):
        r = _run()
        env = r.stages[STAGE_1_RUNNER_DESIGN_SCOPE]
        s = env["runner_design_scope"]
        assert s["design_only"]                      is True
        assert s["real_runner_implemented"]          is False
        assert s["real_execution_allowed"]           is False
        assert s["no_endpoint_invoked_in_this_task"] is True
        assert s["g20_policy_still_in_place"]        is True
        assert s["g20_lifted"]                       is False
        assert s["next_required_task"] == (
            "TASK-014AC_tiny_lifecycle_runner_implementation_dry_run_only"
        )

    def test_always_on_design_scope_gates(self):
        r = _run()
        for g in (
            GATE_DESIGN_ONLY_TRUE,
            GATE_REAL_RUNNER_NOT_IMPLEMENTED,
            GATE_REAL_EXECUTION_NOT_ALLOWED,
            GATE_NO_ENDPOINT_INVOKED,
            GATE_NO_G20_LIFT,
            GATE_NEXT_TASK_IS_DRY_RUN_IMPL,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# AB37: G20 not lifted
# ===========================================================================

class TestAB37G20NotLifted:
    def test_g20_unchanged_constant(self):
        from src.demo_new_entry_protection import G20_BLOCKED_GATE_NAME
        assert G20_BLOCKED_GATE_NAME == "protected_entry_policy_missing"

    def test_module_does_not_reference_g20(self):
        code = _read_code_only(_MODULE_PATH)
        assert "protected_entry_policy_missing" not in code
        assert "G20_BLOCKED_GATE_NAME"          not in code

    def test_result_records_g20_in_place(self):
        r = _run()
        assert r.g20_policy_still_in_place is True
        assert r.g20_lifted is False
        assert GATE_G20_POLICY_STILL_IN_PLACE in r.blocked_gates
        assert GATE_G20_NOT_LIFTED in r.blocked_gates


# ===========================================================================
# AB38: socket-disabled import smoke
# ===========================================================================

class TestAB38SocketDisabledImport:
    def test_module_safe_under_socket_disabled(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"]       = str(ROOT)
        cp = subprocess.run(
            [sys.executable, "-c",
             "import socket; socket.socket = None; "
             "import src.demo_tiny_lifecycle_runner_design as m; "
             "print('OK', m.STATUS_DESIGN_READY)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=60,
        )
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout


# ===========================================================================
# AB39: dataclass roundtrip with deep-copy
# ===========================================================================

class TestAB39DataclassRoundTrip:
    def test_to_dict_roundtrip(self):
        r = _run(allow_runner_design_approval=True)
        d = r.to_dict()
        for key, expected in (
            ("order_endpoint_called",               False),
            ("stop_endpoint_called",                False),
            ("no_position_modified",                True),
            ("no_live_endpoint",                    True),
            ("no_orders_sent",                      True),
            ("no_batch_order",                      True),
            ("no_close_only_path",                  True),
            ("emergency_close_invoked",             False),
            ("leverage_mutated",                    False),
            ("transfer_invoked",                    False),
            ("secret_value_observed",               False),
            ("g20_policy_still_in_place",           True),
            ("g20_lifted",                          False),
            ("current_task_real_execution_allowed", False),
            ("real_runner_implemented",             False),
            ("real_execution_allowed",              False),
            ("runner_design_approval_allowed",      True),
        ):
            assert d[key] is expected, f"{key} should be {expected}"
        assert d["status"] == STATUS_DESIGN_READY_EXEC_DISABLED
        # Deep-copy: mutating returned dict must not affect source.
        d["stages"][STAGE_3_MANUAL_APPROVAL_CONTRACT]["mutated"] = True
        assert "mutated" not in r.stages[STAGE_3_MANUAL_APPROVAL_CONTRACT]
        d["entry_payload_preview"]["mutated"] = True
        assert "mutated" not in r.entry_payload_preview
        d["stop_payload_preview"]["mutated"] = True
        assert "mutated" not in r.stop_payload_preview
        d["cleanup_payload_preview"]["mutated"] = True
        assert "mutated" not in r.cleanup_payload_preview


# ===========================================================================
# AB40: path refs
# ===========================================================================

class TestAB40PathRefs:
    def test_path_refs(self):
        r = _run()
        assert r.order_create_path_ref == ORDER_CREATE_PATH_REF
        assert r.trading_stop_path_ref == TRADING_STOP_PATH_REF
        assert r.base_url_ref          == BASE_URL_DEMO_REF


# ===========================================================================
# AB41: safety invariants
# ===========================================================================

class TestAB41SafetyInvariants:
    def test_default(self):
        r = _run()
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.no_orders_sent is True
        assert r.no_batch_order is True
        assert r.no_close_only_path is True
        assert r.emergency_close_invoked is False
        assert r.leverage_mutated is False
        assert r.transfer_invoked is False
        assert r.secret_value_observed is False
        assert r.existing_positions_touched == []

    def test_dry_run(self):
        r = _run(allow_runner_design_approval=True)
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True

    def test_guard(self):
        r = _run(allow_real_runner_execution=True)
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.real_execution_allowed is False


# ===========================================================================
# AB42: gate count == 68 (21 + 6 + 6 + 7 + 8 + 10 + 5 + 5)
# ===========================================================================

class TestAB42GateCount:
    def test_at_least_68(self):
        import src.demo_tiny_lifecycle_runner_design as m
        gate_names = [
            n for n in dir(m)
            if n.startswith("GATE_") and isinstance(getattr(m, n), str)
        ]
        assert len(gate_names) >= 68, (
            f"Expected >= 68 GATE_ constants, got {len(gate_names)}: "
            f"{sorted(gate_names)}"
        )


# ===========================================================================
# AB43: always-on gates surface in every checklist
# ===========================================================================

class TestAB43AlwaysOnGates:
    def test_always_on_present(self):
        r = _run()
        unique = set(r.blocked_gates)
        for g in (
            # design scope
            GATE_DESIGN_ONLY_TRUE,
            GATE_REAL_RUNNER_NOT_IMPLEMENTED,
            GATE_REAL_EXECUTION_NOT_ALLOWED,
            GATE_NO_ENDPOINT_INVOKED,
            GATE_NO_G20_LIFT,
            GATE_NEXT_TASK_IS_DRY_RUN_IMPL,
            # state machine
            GATE_REQUIRED_STATES_PRESENT,
            GATE_READONLY_BETWEEN_REAL_STEPS_REQUIRED,
            GATE_NO_AUTO_ADVANCE,
            GATE_NO_PARALLEL_EXECUTION,
            GATE_NO_SKIP_STEP,
            GATE_NO_RETRY_LOOP_STATE_MACHINE,
            # manual approval
            GATE_ENTRY_TOKEN_PATTERN_PRESENT,
            GATE_STOP_TOKEN_PATTERN_PRESENT,
            GATE_CLEANUP_TOKEN_PATTERN_PRESENT,
            GATE_TOKENS_DISTINCT,
            GATE_TOKENS_NOT_VALIDATED_IN_THIS_TASK,
            GATE_EACH_STEP_SEPARATE_MANUAL_APPROVAL,
            GATE_TOKEN_FORMAT_IS_NOT_AUTHORIZATION,
            # payload contract (no-conversion is always-on)
            GATE_NO_PREVIEW_TO_REAL_CONVERSION,
            # failure policy
            GATE_ENTRY_FAIL_CLOSED,
            GATE_STOP_FAIL_CLOSED,
            GATE_CLEANUP_FAIL_CLOSED,
            GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
            GATE_PARTIAL_FILL_FAIL_CLOSED,
            GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW,
            GATE_UNEXPECTED_POSITION_MANUAL_REVIEW,
            GATE_NO_AUTO_EMERGENCY_CLOSE,
            GATE_NO_AUTO_CLEANUP,
            GATE_NO_RETRY_LOOP_FAILURE_POLICY,
            # observability
            GATE_ARTIFACT_PER_STEP_REQUIRED,
            GATE_SANITIZED_RESPONSE_REQUIRED,
            GATE_NO_SECRETS_IN_LOGS,
            GATE_DISCORD_SANITIZED_ONLY,
            GATE_NOTION_SANITIZED_ONLY,
            # execution guard
            GATE_REAL_RUNNER_EXECUTION_NOT_IMPL,
            GATE_NO_REAL_ORDER_ENDPOINT,
            GATE_NO_REAL_STOP_ENDPOINT,
            GATE_NO_POSITION_MODIFIED,
            GATE_G20_NOT_LIFTED,
            GATE_G20_POLICY_STILL_IN_PLACE,
            GATE_NO_LIVE_ENDPOINT,
            GATE_NO_SECRETS_EMITTED,
        ):
            assert g in unique, f"always-on gate missing: {g}"


# ===========================================================================
# AB44: no forbidden imports
# ===========================================================================

_FORBIDDEN_IMPORTS = (
    "urllib", "requests", "httpx", "socket", "http.client", "http",
    "pybit",
    "main",
    "src.risk",
    "src.bybit_executor",
    "BybitExecutor",
    "src.demo_new_entry_sender",
    "src.demo_close_only_sender",
    "src.demo_emergency_close_sender",
    "src.demo_protected_new_entry_orchestrator",
    "src.demo_trading_stop_contract_probe",
    "src.demo_trading_stop_noop_probe_plan",
    "src.demo_tiny_position_lifecycle_mock",
    "src.demo_tiny_position_real_permission_gate",
    "src.demo_tiny_entry_permission_gate",
    "src.demo_tiny_stop_attach_permission_gate",
    "src.demo_tiny_cleanup_permission_gate",
    "src.demo_tiny_lifecycle_real_execution_summary",
)


def _collect_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.add(node.module)
    return out


class TestAB44NoForbiddenImports:
    def test_module(self):
        imp = _collect_imports(_MODULE_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in module"

    def test_cli(self):
        imp = _collect_imports(_SCRIPT_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in CLI"


# ===========================================================================
# AB45: no sender reuse
# ===========================================================================

class TestAB45NoSenderReuse:
    def test_no_close_only(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoCloseOnlySender"     not in code
            assert "demo_close_only_sender"  not in code

    def test_no_emergency_close(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoEmergencyCloseSender"    not in code
            assert "demo_emergency_close_sender" not in code

    def test_no_new_entry_sender(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoNewEntrySender"    not in code
            assert "demo_new_entry_sender" not in code

    def test_no_summary_module_reuse(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTinyLifecycleRealExecutionSummary" not in code


# ===========================================================================
# AB46: no network/env/signing tokens
# ===========================================================================

class TestAB46NoNetworkTokens:
    def test_no_net_tokens(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            for tok in ("urllib", "urlopen", "httpx",
                        "requests.", "http.client", "socket.",
                        "session.post", "session.get"):
                assert tok not in code, (
                    f"Network token {tok!r} present in {path.name}"
                )

    def test_no_env_or_signing(self):
        code = _read_code_only(_MODULE_PATH)
        assert "os.environ" not in code
        assert "getenv"     not in code
        assert "dotenv"     not in code
        assert "hmac"       not in code.lower()
        assert "hashlib"    not in code.lower()
        assert "BYBIT_API"  not in code
        assert "API_KEY"    not in code
        assert "API_SECRET" not in code


# ===========================================================================
# AB47: forbidden flags do not exist anywhere
# ===========================================================================

class TestAB47NoForbiddenFlags:
    @pytest.mark.parametrize("flag", [
        "--execute-real-lifecycle",
        "--execute-real-entry",
        "--execute-real-stop",
        "--execute-real-cleanup",
    ])
    def test_flag_absent_in_module(self, flag):
        code = _read_code_only(_MODULE_PATH)
        assert flag not in code

    @pytest.mark.parametrize("flag", [
        "--execute-real-lifecycle",
        "--execute-real-entry",
        "--execute-real-stop",
        "--execute-real-cleanup",
    ])
    def test_flag_absent_in_cli(self, flag):
        code = _read_code_only(_SCRIPT_PATH)
        assert flag not in code

    def test_flag_token_absent_in_module(self):
        code = _read_code_only(_MODULE_PATH)
        for ident in ("execute_real_lifecycle", "execute_real_entry",
                      "execute_real_stop", "execute_real_cleanup"):
            assert ident not in code

    def test_flag_token_absent_in_cli(self):
        code = _read_code_only(_SCRIPT_PATH)
        for ident in ("execute_real_lifecycle", "execute_real_entry",
                      "execute_real_stop", "execute_real_cleanup"):
            assert ident not in code


# ===========================================================================
# AB48: token patterns surfaced + 3 distinct
# ===========================================================================

class TestAB48TokenPatterns:
    def test_three_patterns(self):
        r = _run()
        assert r.entry_token_pattern       == ENTRY_TOKEN_PATTERN
        assert r.stop_attach_token_pattern == STOP_ATTACH_TOKEN_PATTERN
        assert r.cleanup_token_pattern     == CLEANUP_TOKEN_PATTERN
        assert len({
            r.entry_token_pattern,
            r.stop_attach_token_pattern,
            r.cleanup_token_pattern,
        }) == 3


# ===========================================================================
# AB49: stage_0 artifact preflight reports all 11 upstream artifacts present
# ===========================================================================

class TestAB49Stage0PreflightAllPresent:
    def test_all_present(self):
        r = _run()
        env = r.stages[STAGE_0_ARTIFACT_PREFLIGHT]
        assert env["readonly_smoke_present"]                   is True
        assert env["reconciliation_present"]                   is True
        assert env["protection_present"]                       is True
        assert env["contract_present"]                         is True
        assert env["noop_plan_present"]                        is True
        assert env["lifecycle_mock_present"]                   is True
        assert env["real_permission_gate_present"]             is True
        assert env["tiny_entry_permission_gate_present"]       is True
        assert env["tiny_stop_attach_permission_gate_present"] is True
        assert env["tiny_cleanup_permission_gate_present"]     is True
        assert env["lifecycle_summary_present"]                is True
        assert env["current_task_real_execution_allowed"]      is False


# ===========================================================================
# AB50: report artifacts written (design checklist)
# ===========================================================================

class _ReportSetupMixin:
    def _setup(self, base: Path):
        ro_d   = base / "readonly";    ro_d.mkdir()
        rec_d  = base / "recon";       rec_d.mkdir()
        prot_d = base / "protection";  prot_d.mkdir()
        con_d  = base / "contract";    con_d.mkdir()
        noop_d = base / "noop";        noop_d.mkdir()
        lc_d   = base / "lifecycle";   lc_d.mkdir()
        rp_d   = base / "real_perm";   rp_d.mkdir()
        ep_d   = base / "entry_perm";  ep_d.mkdir()
        sp_d   = base / "stop_perm";   sp_d.mkdir()
        cp_d   = base / "cleanup_perm"; cp_d.mkdir()
        sum_d  = base / "summary";     sum_d.mkdir()
        out_d  = base / "out"
        (ro_d   / "latest_smoke.json").write_text(json.dumps(_valid_readonly()), encoding="utf-8")
        (rec_d  / "latest_reconciliation.json").write_text(json.dumps(_valid_reconciliation()), encoding="utf-8")
        (prot_d / "latest_new_entry_protection.json").write_text(json.dumps(_valid_protection()), encoding="utf-8")
        (con_d  / "latest_trading_stop_contract.json").write_text(json.dumps(_valid_contract()), encoding="utf-8")
        (noop_d / "latest_trading_stop_noop_probe_plan.json").write_text(json.dumps(_valid_noop_plan()), encoding="utf-8")
        (lc_d   / "latest_tiny_position_lifecycle_mock.json").write_text(json.dumps(_valid_lifecycle()), encoding="utf-8")
        (rp_d   / "latest_tiny_position_real_permission_gate.json").write_text(json.dumps(_valid_real_permission_gate()), encoding="utf-8")
        (ep_d   / "latest_tiny_entry_permission_gate.json").write_text(json.dumps(_valid_tiny_entry_permission_gate()), encoding="utf-8")
        (sp_d   / "latest_tiny_stop_attach_permission_gate.json").write_text(json.dumps(_valid_tiny_stop_attach_permission_gate()), encoding="utf-8")
        (cp_d   / "latest_tiny_cleanup_permission_gate.json").write_text(json.dumps(_valid_tiny_cleanup_permission_gate()), encoding="utf-8")
        (sum_d  / "latest_tiny_lifecycle_real_execution_summary.json").write_text(json.dumps(_valid_lifecycle_summary()), encoding="utf-8")
        return ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, sp_d, cp_d, sum_d, out_d


class TestAB50ReportChecklist(_ReportSetupMixin):
    def test_writes_report(self):
        from scripts.preview_demo_tiny_lifecycle_runner_design import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d,
             rp_d, ep_d, sp_d, cp_d, sum_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_runner_design_approval=False,
                allow_real_runner_execution=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d, tiny_cleanup_dir=cp_d,
                lifecycle_summary_dir=sum_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            files = sorted(p.name for p in out_d.iterdir())
            assert "latest_tiny_lifecycle_runner_design.json" in files
            assert "latest_tiny_lifecycle_runner_design.md"   in files
            data = json.loads(
                (out_d / "latest_tiny_lifecycle_runner_design.json").read_text(encoding="utf-8")
            )
            assert data["status"] == STATUS_DESIGN_READY
            assert data["real_execution_allowed"] is False
            assert data["real_runner_implemented"] is False
            assert data["order_endpoint_called"] is False
            assert data["stop_endpoint_called"] is False
            assert data["no_position_modified"] is True
            assert data["expected_entry_reference_price"] == pytest.approx(64.87)
            assert len(data["runner_states"]) == 18
            assert len(data["required_audit_artifacts"]) == 11


# ===========================================================================
# AB51: no secrets in report
# ===========================================================================

class TestAB51NoSecretsInReport(_ReportSetupMixin):
    def test_no_secrets(self):
        from scripts.preview_demo_tiny_lifecycle_runner_design import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d,
             rp_d, ep_d, sp_d, cp_d, sum_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_runner_design_approval=False,
                allow_real_runner_execution=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d, tiny_cleanup_dir=cp_d,
                lifecycle_summary_dir=sum_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            md = (out_d / "latest_tiny_lifecycle_runner_design.md").read_text(encoding="utf-8")
            for forbidden in ("API_KEY", "API_SECRET", "BYBIT_API", "X-BAPI-SIGN"):
                assert forbidden not in md
            data = json.loads(
                (out_d / "latest_tiny_lifecycle_runner_design.json").read_text(encoding="utf-8")
            )
            assert data["secret_value_observed"] is False


# ===========================================================================
# AB52: CLI valid run exits 0 + missing artifact exits 1
# ===========================================================================

class TestAB52CLIExitCodes(_ReportSetupMixin):
    def test_subprocess_exits_0(self):
        from scripts.preview_demo_tiny_lifecycle_runner_design import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d,
             rp_d, ep_d, sp_d, cp_d, sum_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_runner_design_approval=False,
                allow_real_runner_execution=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d, tiny_cleanup_dir=cp_d,
                lifecycle_summary_dir=sum_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0

    def test_subprocess_missing_exits_1(self):
        from scripts.preview_demo_tiny_lifecycle_runner_design import run_execute
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for sub in ("readonly", "recon", "protection", "contract", "noop",
                        "lifecycle", "real_perm", "entry_perm", "stop_perm",
                        "cleanup_perm", "summary"):
                (base / sub).mkdir()
            rc = run_execute(
                symbol="SOLUSDT",
                allow_runner_design_approval=False,
                allow_real_runner_execution=False,
                write_report=False,
                readonly_dir=base / "readonly",
                reconciliation_dir=base / "recon",
                protection_dir=base / "protection",
                contract_dir=base / "contract",
                noop_plan_dir=base / "noop",
                lifecycle_dir=base / "lifecycle",
                real_permission_dir=base / "real_perm",
                tiny_entry_dir=base / "entry_perm",
                tiny_stop_attach_dir=base / "stop_perm",
                tiny_cleanup_dir=base / "cleanup_perm",
                lifecycle_summary_dir=base / "summary",
                output_dir=base / "out", _now=_TEST_NOW,
            )
            assert rc == 1


# ===========================================================================
# AB53: next_required_task points at TASK-014AC
# ===========================================================================

class TestAB53NextTaskIs014AC:
    def test_next_required_task(self):
        r = _run()
        assert r.next_required_task == (
            "TASK-014AC_tiny_lifecycle_runner_implementation_dry_run_only"
        )


# ===========================================================================
# AB54: upstream lifecycle summary status echoed
# ===========================================================================

class TestAB54UpstreamSummaryStatusEchoed:
    def test_echoed(self):
        r = _run()
        assert r.upstream_lifecycle_summary_status == (
            "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY"
        )


# ===========================================================================
# AB55: status promotion vs. fail-closed precedence
# ===========================================================================

class TestAB55StatusPrecedence:
    def test_hard_fail_beats_approval(self):
        # Even with --allow-runner-design-approval, a missing upstream
        # artifact must downgrade to FAIL_CLOSED.
        r = _run(readonly=None, allow_runner_design_approval=True)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED

    def test_hard_fail_beats_execution_guard(self):
        # Even with --allow-real-runner-execution, a hard-fail upstream
        # must downgrade to FAIL_CLOSED (not promote to NOT_IMPL).
        r = _run(lifecycle_summary=None, allow_real_runner_execution=True)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
