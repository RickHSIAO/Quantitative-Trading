"""
tests/demo_trading/test_demo_tiny_lifecycle_runner_dry_run.py
TASK-014AC: Tiny Lifecycle Runner Implementation / Dry-run Only tests
(AC1 - AC61+).

Covers dry_run_checklist / dry_run_runner_approval_dry_run /
real_runner_execution_guard / fail_closed paths; all 8 stages; 73 gate
constants; 18-state runner state machine; 8-step dry-run trace; three
dry-run request envelopes (entry / stop / cleanup) with
preview_only=True / send_allowed=False / real_payload=False /
endpoint_called=False / no signature / no private headers; readonly
verification simulation labelled artifact-only; 11-slot
DRY_RUN_NOT_SENT audit; failure path simulation (FAIL_CLOSED or
MANUAL_REVIEW_REQUIRED with no auto retry / cleanup /
emergency_close); status precedence; observability sanitisation;
source-scan safety (no urlopen / no forbidden imports / no signing /
no os.environ); report artifacts; forbidden-flag absence; the
invariant that TASK-014L sender G20 (protected_entry_policy_missing)
still blocks --execute-new-entry and is NOT lifted here; and the
12-artifact preflight contract (10 baseline + 014AA lifecycle summary +
014AB runner design).
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

from src.demo_tiny_lifecycle_runner_dry_run import (
    ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES,
    ACCEPTABLE_RUNNER_DESIGN_STATUSES,
    ALL_STAGES,
    BASE_URL_DEMO_REF,
    CLEANUP_TOKEN_PATTERN,
    DEFAULT_SELECTED_SYMBOL,
    DRY_RUN_STEPS,
    DemoTinyLifecycleRunnerDryRun,
    ENTRY_TOKEN_PATTERN,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_PROOF_STRENGTH,
    FORBIDDEN_LOG_FIELDS,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_CLEANUP_ENVELOPE_PREVIEW_ONLY,
    GATE_CLEANUP_ENVELOPE_SEND_NOT_ALLOWED,
    GATE_CLEANUP_FAILURE_FAIL_CLOSED,
    GATE_CONTRACT_MISSING,
    GATE_DISCORD_SANITIZED_ONLY,
    GATE_DRY_RUN_RUNNER_TRUE,
    GATE_EIGHT_STEP_TRACE_COMPLETE,
    GATE_ELEVEN_AUDIT_SLOTS_PRESENT,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_ENVELOPE_PREVIEW_ONLY,
    GATE_ENTRY_ENVELOPE_SEND_NOT_ALLOWED,
    GATE_ENTRY_FAILURE_FAIL_CLOSED,
    GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW,
    GATE_G20_NOT_LIFTED,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_LIFECYCLE_SUMMARY_MISSING,
    GATE_NO_AUTO_ADVANCE_TRACE,
    GATE_NO_AUTO_CLEANUP,
    GATE_NO_AUTO_EMERGENCY_CLOSE,
    GATE_NO_AUTO_RETRY,
    GATE_NO_ENDPOINT_INVOKED,
    GATE_NO_G20_LIFT,
    GATE_NO_LIVE_ENDPOINT,
    GATE_NO_PARALLEL_EXECUTION_TRACE,
    GATE_NO_POSITION_MODIFIED,
    GATE_NO_POSITION_MODIFIED_SCOPE,
    GATE_NO_PRIVATE_HEADERS,
    GATE_NO_REAL_ORDER_ENDPOINT,
    GATE_NO_REAL_STOP_ENDPOINT,
    GATE_NO_RETRY_LOOP_TRACE,
    GATE_NO_SECRETS_EMITTED,
    GATE_NO_SECRETS_IN_AUDIT,
    GATE_NO_SECRETS_LOADED,
    GATE_NO_SENDER_ADAPTER,
    GATE_NO_SIGNATURE,
    GATE_NO_SKIP_STEP_TRACE,
    GATE_NOOP_PLAN_MISSING,
    GATE_NOTION_SANITIZED_ONLY,
    GATE_PARTIAL_FILL_FAIL_CLOSED,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_POST_CLEANUP_VERIFICATION_SIMULATED,
    GATE_POST_ENTRY_VERIFICATION_SIMULATED,
    GATE_POST_STOP_VERIFICATION_SIMULATED,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_PROTECTION_MISSING,
    GATE_READONLY_SMOKE_MISSING,
    GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
    GATE_REAL_EXECUTION_NOT_ALLOWED,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED,
    GATE_REAL_RUNNER_EXECUTION_NOT_IMPL,
    GATE_REAL_RUNNER_NOT_IMPLEMENTED,
    GATE_RECONCILIATION_MISSING,
    GATE_REQUIRED_STATES_OBSERVED,
    GATE_RESPONSE_FROM_EXCHANGE_FALSE,
    GATE_RESPONSES_SANITIZED,
    GATE_RUNNER_DESIGN_MISSING,
    GATE_RUNNER_DESIGN_STATUS_UNACCEPTABLE,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_STOP_ENVELOPE_PREVIEW_ONLY,
    GATE_STOP_ENVELOPE_SEND_NOT_ALLOWED,
    GATE_STOP_FAILURE_FAIL_CLOSED,
    GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
    GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
    GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING,
    GATE_TRACE_STEP_ENDPOINT_NOT_CALLED,
    GATE_TRACE_STEP_POSITION_NOT_MODIFIED,
    GATE_TRACE_STEP_TOKEN_NOT_VALIDATED,
    GATE_UNEXPECTED_POSITION_MANUAL_REVIEW,
    GATE_VERIFICATION_SOURCE_ARTIFACT_ONLY,
    MODE_DRY_RUN_CHECKLIST,
    MODE_DRY_RUN_RUNNER_APPROVAL_DRY_RUN,
    MODE_FAIL_CLOSED,
    MODE_REAL_RUNNER_EXECUTION_GUARD,
    ORDER_CREATE_PATH_REF,
    REQUIRED_AUDIT_ARTIFACTS,
    RUNNER_STATES,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_DRY_RUN_SCOPE,
    STAGE_2_STATE_MACHINE_TRACE,
    STAGE_3_DRY_RUN_PAYLOAD_MATERIALIZATION,
    STAGE_4_READONLY_VERIFICATION_SIMULATION,
    STAGE_5_AUDIT_ARTIFACT_GENERATION,
    STAGE_6_FAILURE_PATH_SIMULATION,
    STAGE_7_FINAL_DRY_RUN_VERDICT,
    STATUS_DRY_RUN_READY,
    STATUS_DRY_RUN_READY_EXEC_DISABLED,
    STATUS_FAIL_CLOSED,
    STATUS_REAL_RUNNER_NOT_IMPL,
    STOP_ATTACH_TOKEN_PATTERN,
    TRADING_STOP_PATH_REF,
    TinyLifecycleRunnerDryRunResult,
)


_MODULE_PATH = ROOT / "src" / "demo_tiny_lifecycle_runner_dry_run.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_tiny_lifecycle_runner_dry_run.py"
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


def _valid_runner_design() -> dict:
    return {
        "timestamp_utc":                  "2026-06-10T11:59:58Z",
        "mode":                           "design_checklist",
        "selected_symbol":                "SOLUSDT",
        "status":                         "TINY_LIFECYCLE_RUNNER_DESIGN_READY",
        "real_execution_allowed":              False,
        "real_runner_implemented":             False,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
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


def _gate() -> DemoTinyLifecycleRunnerDryRun:
    return DemoTinyLifecycleRunnerDryRun()


_UNSET = object()


def _run(
    *,
    readonly=_UNSET, recon=_UNSET, protection=_UNSET, contract=_UNSET,
    noop_plan=_UNSET, lifecycle=_UNSET, real_permission_gate=_UNSET,
    tiny_entry_permission_gate=_UNSET,
    tiny_stop_attach_permission_gate=_UNSET,
    tiny_cleanup_permission_gate=_UNSET,
    lifecycle_summary=_UNSET,
    runner_design=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    allow_dry_run_runner_approval=False,
    allow_real_runner_execution=False,
    _now=_TEST_NOW,
) -> TinyLifecycleRunnerDryRunResult:
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
        runner_design=_valid_runner_design()                           if runner_design        is _UNSET else runner_design,
        symbol=symbol,
        allow_dry_run_runner_approval=allow_dry_run_runner_approval,
        allow_real_runner_execution=allow_real_runner_execution,
        _now=_now,
    )


# ===========================================================================
# AC1: valid dry-run checklist => DRY_RUN_READY
# ===========================================================================

class TestAC1DryRunChecklistReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_DRY_RUN_READY
        assert r.mode == MODE_DRY_RUN_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.real_execution_allowed is False
        assert r.real_runner_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.dry_run_trace_complete is True
        assert r.next_required_task == (
            "TASK-014AD_tiny_lifecycle_real_execution_guarded_runner_design_review"
        )


# ===========================================================================
# AC2: --allow-dry-run-runner-approval => DRY_RUN_READY_BUT_EXECUTION_DISABLED
# ===========================================================================

class TestAC2DryRunRunnerApprovalDryRun:
    def test_promotes_status(self):
        r = _run(allow_dry_run_runner_approval=True)
        assert r.status == STATUS_DRY_RUN_READY_EXEC_DISABLED
        assert r.mode == MODE_DRY_RUN_RUNNER_APPROVAL_DRY_RUN
        assert r.dry_run_runner_approval_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_runner_implemented is False
        assert r.current_task_real_execution_allowed is False


# ===========================================================================
# AC3: --allow-real-runner-execution => REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED
# ===========================================================================

class TestAC3RealRunnerExecutionGuard:
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
# AC4 - AC15: missing upstream artifacts (12) => FAIL_CLOSED
# ===========================================================================

class TestAC4MissingReadonly:
    def test_none(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestAC5MissingReconciliation:
    def test_none(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestAC6MissingProtection:
    def test_none(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestAC7MissingContract:
    def test_none(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestAC8MissingNoopPlan:
    def test_none(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestAC9MissingLifecycle:
    def test_none(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestAC10MissingRealPermissionGate:
    def test_none(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAC11MissingTinyEntryPermissionGate:
    def test_none(self):
        r = _run(tiny_entry_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAC12MissingTinyStopAttachPermissionGate:
    def test_none(self):
        r = _run(tiny_stop_attach_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAC13MissingTinyCleanupPermissionGate:
    def test_none(self):
        r = _run(tiny_cleanup_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAC14MissingLifecycleSummary:
    def test_none(self):
        r = _run(lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAC15MissingRunnerDesign:
    def test_none(self):
        r = _run(runner_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DESIGN_MISSING in r.blocked_gates


# ===========================================================================
# AC16: selected_symbol collides with an existing position => FAIL_CLOSED
# ===========================================================================

class TestAC16SymbolCollision:
    @pytest.mark.parametrize("sym", list(EXISTING_POSITION_SYMBOLS))
    def test_collision_blocks(self, sym):
        r = _run(symbol=sym)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_COLLIDES_EXISTING in r.blocked_gates


# ===========================================================================
# AC17 - AC20: proof envelope mismatches => FAIL_CLOSED
# ===========================================================================

class TestAC17EndpointFamilyMismatch:
    def test_mainnet(self):
        ro = _valid_readonly(); ro["endpoint_family"] = "bybit_mainnet"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestAC18AccountModeMismatch:
    def test_live(self):
        ro = _valid_readonly(); ro["account_mode"] = "live"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestAC19ProofStrengthMismatch:
    def test_weak(self):
        ro = _valid_readonly(); ro["proof_strength"] = "WEAK"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROOF_STRENGTH_NOT_STRONG in r.blocked_gates


class TestAC20PositionDetailsSourceMismatch:
    def test_synthetic(self):
        rec = _valid_reconciliation()
        rec["mode"] = "synthetic"
        rec["position_details_source"] = "synthetic"
        r = _run(recon=rec)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY in r.blocked_gates


# ===========================================================================
# AC21: runner_design status unacceptable => FAIL_CLOSED
# ===========================================================================

class TestAC21RunnerDesignStatusUnacceptable:
    def test_fail_closed(self):
        rd = _valid_runner_design(); rd["status"] = "FAIL_CLOSED"
        r = _run(runner_design=rd)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DESIGN_STATUS_UNACCEPTABLE in r.blocked_gates

    @pytest.mark.parametrize("status", sorted(ACCEPTABLE_RUNNER_DESIGN_STATUSES))
    def test_acceptable_statuses_pass(self, status):
        rd = _valid_runner_design(); rd["status"] = status
        r = _run(runner_design=rd)
        assert r.status == STATUS_DRY_RUN_READY


# ===========================================================================
# AC22 - AC24: envelope contract violations => FAIL_CLOSED
# ===========================================================================

class TestAC22EntryEnvelopePreviewOnly:
    def test_preview_false(self):
        gate = _valid_tiny_entry_permission_gate()
        gate["entry_payload_preview"] = {
            **_valid_entry_payload_preview(), "preview_only": False,
        }
        ls = _valid_lifecycle_summary()
        ls["entry_payload_preview"] = {
            **_valid_entry_payload_preview(), "preview_only": False,
        }
        r = _run(tiny_entry_permission_gate=gate, lifecycle_summary=ls)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_ENVELOPE_PREVIEW_ONLY in r.blocked_gates


class TestAC23StopEnvelopePreviewOnly:
    def test_preview_false(self):
        gate = _valid_tiny_stop_attach_permission_gate()
        gate["stop_payload_preview"] = {
            **_valid_stop_payload_preview(), "preview_only": False,
        }
        ls = _valid_lifecycle_summary()
        ls["stop_payload_preview"] = {
            **_valid_stop_payload_preview(), "preview_only": False,
        }
        r = _run(tiny_stop_attach_permission_gate=gate, lifecycle_summary=ls)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_STOP_ENVELOPE_PREVIEW_ONLY in r.blocked_gates


class TestAC24CleanupEnvelopePreviewOnly:
    def test_preview_false(self):
        gate = _valid_tiny_cleanup_permission_gate()
        gate["cleanup_payload_preview"] = {
            **_valid_cleanup_payload_preview(), "preview_only": False,
        }
        ls = _valid_lifecycle_summary()
        ls["cleanup_payload_preview"] = {
            **_valid_cleanup_payload_preview(), "preview_only": False,
        }
        r = _run(tiny_cleanup_permission_gate=gate, lifecycle_summary=ls)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CLEANUP_ENVELOPE_PREVIEW_ONLY in r.blocked_gates


# ===========================================================================
# AC25: missing symbol => FAIL_CLOSED
# ===========================================================================

class TestAC25MissingSymbol:
    def test_empty_symbol(self):
        r = _run(symbol="")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_MISSING in r.blocked_gates


# ===========================================================================
# AC26: 8 stages built
# ===========================================================================

class TestAC26EightStages:
    def test_eight(self):
        r = _run()
        assert set(r.stages.keys()) == set(ALL_STAGES)
        assert r.stage_order == list(ALL_STAGES)
        assert len(ALL_STAGES) == 8


# ===========================================================================
# AC27: 18-state runner state machine
# ===========================================================================

class TestAC27RunnerStateMachine:
    def test_eighteen_states(self):
        r = _run()
        assert len(r.runner_states) == 18
        assert len(RUNNER_STATES) == 18
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


# ===========================================================================
# AC28: 8-step dry-run trace
# ===========================================================================

class TestAC28EightStepDryRunTrace:
    def test_eight_steps(self):
        r = _run()
        assert len(r.state_machine_trace) == 8
        assert len(DRY_RUN_STEPS) == 8
        names = [s["step_name"] for s in r.state_machine_trace]
        assert names == list(DRY_RUN_STEPS)

    def test_step_index_zero_through_seven(self):
        r = _run()
        assert [s["step_index"] for s in r.state_machine_trace] == list(range(8))

    def test_trace_block_fields(self):
        r = _run()
        env = r.stages[STAGE_2_STATE_MACHINE_TRACE]
        sm = env["state_machine_trace"]
        assert sm["eight_step_trace_complete"] is True
        assert sm["required_states_observed"] is True
        assert sm["no_auto_advance"] is True
        assert sm["no_parallel_execution"] is True
        assert sm["no_skip_step"] is True
        assert sm["no_retry_loop"] is True
        assert sm["every_step_endpoint_not_called"] is True
        assert sm["every_step_position_not_modified"] is True
        assert sm["every_step_token_not_validated"] is True


# ===========================================================================
# AC29: per-step safety invariants
# ===========================================================================

class TestAC29PerStepSafetyInvariants:
    def test_every_step_safe(self):
        r = _run()
        for s in r.state_machine_trace:
            assert s["endpoint_called"] is False
            assert s["position_modified"] is False
            assert s["auto_advanced"] is False
            assert s["token_validated"] is False
            assert s["parallel"] is False
            assert s["skipped"] is False
            assert s["retry"] is False

    def test_artifact_slot_present(self):
        r = _run()
        slots = {s["artifact_slot"] for s in r.state_machine_trace}
        for needed in (
            "pre_snapshot", "entry_request_envelope", "post_entry_readonly",
            "stop_request_envelope", "post_stop_readonly",
            "cleanup_request_envelope", "post_cleanup_readonly",
            "final_audit",
        ):
            assert needed in slots

    def test_always_on_trace_gates(self):
        r = _run()
        for g in (
            GATE_EIGHT_STEP_TRACE_COMPLETE,
            GATE_REQUIRED_STATES_OBSERVED,
            GATE_NO_AUTO_ADVANCE_TRACE,
            GATE_NO_PARALLEL_EXECUTION_TRACE,
            GATE_NO_SKIP_STEP_TRACE,
            GATE_NO_RETRY_LOOP_TRACE,
            GATE_TRACE_STEP_ENDPOINT_NOT_CALLED,
            GATE_TRACE_STEP_POSITION_NOT_MODIFIED,
            GATE_TRACE_STEP_TOKEN_NOT_VALIDATED,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# AC30: stage_1 dry-run scope
# ===========================================================================

class TestAC30DryRunScope:
    def test_scope_fields(self):
        r = _run()
        env = r.stages[STAGE_1_DRY_RUN_SCOPE]
        s = env["dry_run_scope"]
        assert s["dry_run_runner"]                  is True
        assert s["real_runner_implemented"]         is False
        assert s["real_execution_allowed"]          is False
        assert s["order_endpoint_called"]           is False
        assert s["stop_endpoint_called"]            is False
        assert s["no_endpoint_invoked_in_this_task"] is True
        assert s["no_position_modified"]            is True
        assert s["no_secrets_loaded"]               is True
        assert s["g20_policy_still_in_place"]       is True
        assert s["g20_lifted"]                      is False
        assert s["next_required_task"] == (
            "TASK-014AD_tiny_lifecycle_real_execution_guarded_runner_design_review"
        )

    def test_always_on_scope_gates(self):
        r = _run()
        for g in (
            GATE_DRY_RUN_RUNNER_TRUE,
            GATE_REAL_RUNNER_NOT_IMPLEMENTED,
            GATE_REAL_EXECUTION_NOT_ALLOWED,
            GATE_NO_ENDPOINT_INVOKED,
            GATE_NO_POSITION_MODIFIED_SCOPE,
            GATE_NO_SECRETS_LOADED,
            GATE_NO_G20_LIFT,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# AC31: stage_3 dry-run payload materialization
# ===========================================================================

class TestAC31DryRunPayloadMaterialization:
    def test_envelopes_safe(self):
        r = _run()
        env = r.stages[STAGE_3_DRY_RUN_PAYLOAD_MATERIALIZATION]
        d = env["dry_run_request_envelopes"]
        for which in ("entry_request_envelope", "stop_request_envelope",
                      "cleanup_request_envelope"):
            e = d[which]
            assert e["preview_only"]      is True
            assert e["endpoint_called"]   is False
            assert e["send_allowed"]      is False
            assert e["real_payload"]      is False
            assert e["signature_present"] is False
            assert e["private_headers"]   == []
        assert d["no_signature"]       is True
        assert d["no_private_headers"] is True
        assert d["no_sender_adapter"]  is True

    def test_entry_envelope_path_ref(self):
        r = _run()
        e = r.dry_run_request_envelopes["entry_request_envelope"]
        assert e["endpoint_path_ref"] == ORDER_CREATE_PATH_REF

    def test_stop_envelope_path_ref(self):
        r = _run()
        e = r.dry_run_request_envelopes["stop_request_envelope"]
        assert e["endpoint_path_ref"] == TRADING_STOP_PATH_REF

    def test_cleanup_envelope_path_ref(self):
        r = _run()
        e = r.dry_run_request_envelopes["cleanup_request_envelope"]
        assert e["endpoint_path_ref"] == ORDER_CREATE_PATH_REF

    def test_always_on_payload_gates(self):
        r = _run()
        for g in (
            GATE_NO_SIGNATURE,
            GATE_NO_PRIVATE_HEADERS,
            GATE_NO_SENDER_ADAPTER,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# AC32: stage_4 readonly verification simulation
# ===========================================================================

class TestAC32ReadonlyVerificationSimulation:
    def test_simulated_flags(self):
        r = _run()
        env = r.stages[STAGE_4_READONLY_VERIFICATION_SIMULATION]
        sim = env["readonly_verification_simulation"]
        assert sim["verification_is_simulated"] is True
        assert sim["real_readonly_after_execution_not_performed"] is True
        for slot in ("post_entry_readonly_simulated",
                     "post_stop_attach_readonly_simulated",
                     "post_cleanup_readonly_simulated"):
            assert sim[slot]["source"] == "artifact_only"

    def test_always_on_simulation_gates(self):
        r = _run()
        for g in (
            GATE_POST_ENTRY_VERIFICATION_SIMULATED,
            GATE_POST_STOP_VERIFICATION_SIMULATED,
            GATE_POST_CLEANUP_VERIFICATION_SIMULATED,
            GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED,
            GATE_VERIFICATION_SOURCE_ARTIFACT_ONLY,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# AC33: stage_5 audit artifact generation (11 slots, DRY_RUN_NOT_SENT)
# ===========================================================================

class TestAC33AuditArtifactGeneration:
    def test_eleven_slots(self):
        r = _run()
        env = r.stages[STAGE_5_AUDIT_ARTIFACT_GENERATION]
        a = env["audit_artifacts"]
        assert a["eleven_audit_slots_present"] is True
        assert a["required_audit_artifacts"] == list(REQUIRED_AUDIT_ARTIFACTS)
        assert len(a["required_audit_artifacts"]) == 11
        assert len(a["audit_artifacts"]) == 11
        for slot, slot_data in a["audit_artifacts"].items():
            assert slot_data["status"] == "DRY_RUN_NOT_SENT"
            assert slot_data["endpoint_called"] is False
            assert slot_data["response_from_exchange"] is False
            assert slot_data["sanitized"] is True
            assert slot_data["discord_sanitized_only"] is True
            assert slot_data["notion_sanitized_only"] is True
        assert a["responses_sanitized"] is True
        assert a["response_from_exchange"] is False
        assert a["no_secrets_in_audit"] is True
        assert a["discord_sanitized_summary_only"] is True
        assert a["notion_sanitized_summary_only"] is True
        for f in FORBIDDEN_LOG_FIELDS:
            assert f in a["forbidden_log_fields"]

    def test_always_on_audit_gates(self):
        r = _run()
        for g in (
            GATE_ELEVEN_AUDIT_SLOTS_PRESENT,
            GATE_RESPONSES_SANITIZED,
            GATE_RESPONSE_FROM_EXCHANGE_FALSE,
            GATE_NO_SECRETS_IN_AUDIT,
            GATE_DISCORD_SANITIZED_ONLY,
            GATE_NOTION_SANITIZED_ONLY,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# AC34: stage_6 failure path simulation
# ===========================================================================

class TestAC34FailurePathSimulation:
    def test_matrix_fields(self):
        r = _run()
        env = r.stages[STAGE_6_FAILURE_PATH_SIMULATION]
        m = env["failure_path_simulation"]
        for fail_closed_key in (
            "entry_rejected", "stop_attach_rejected", "cleanup_rejected",
            "readonly_unavailable_between_steps", "entry_or_cleanup_partial_fill",
        ):
            assert m[fail_closed_key]["resolution"] == "FAIL_CLOSED"
            assert m[fail_closed_key]["no_auto_retry"] is True
            assert m[fail_closed_key]["no_auto_cleanup"] is True
            assert m[fail_closed_key]["no_auto_emergency_close"] is True
            assert m[fail_closed_key]["no_next_step"] is True
            assert m[fail_closed_key]["manual_review_required"] is False
        for review_key in ("existing_stop_mismatch", "unexpected_position_appears"):
            assert m[review_key]["resolution"] == "MANUAL_REVIEW_REQUIRED"
            assert m[review_key]["manual_review_required"] is True
            assert m[review_key]["no_auto_retry"] is True
            assert m[review_key]["no_auto_cleanup"] is True
            assert m[review_key]["no_auto_emergency_close"] is True

    def test_always_on_failure_gates(self):
        r = _run()
        for g in (
            GATE_ENTRY_FAILURE_FAIL_CLOSED,
            GATE_STOP_FAILURE_FAIL_CLOSED,
            GATE_CLEANUP_FAILURE_FAIL_CLOSED,
            GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
            GATE_PARTIAL_FILL_FAIL_CLOSED,
            GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW,
            GATE_UNEXPECTED_POSITION_MANUAL_REVIEW,
            GATE_NO_AUTO_RETRY,
            GATE_NO_AUTO_CLEANUP,
            GATE_NO_AUTO_EMERGENCY_CLOSE,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# AC35: stage_7 final dry-run verdict
# ===========================================================================

class TestAC35FinalDryRunVerdict:
    def test_default_flags(self):
        r = _run()
        env = r.stages[STAGE_7_FINAL_DRY_RUN_VERDICT]
        v = env["final_dry_run_verdict"]
        assert v["dry_run_runner_approval_allowed"]     is False
        assert v["real_runner_execution_requested"]     is False
        assert v["dry_run_trace_complete"]              is True
        assert v["real_execution_allowed"]              is False
        assert v["real_runner_implemented"]             is False
        assert v["current_task_real_execution_allowed"] is False
        assert v["g20_policy_still_in_place"]           is True
        assert v["g20_lifted"]                          is False
        assert v["no_real_order_endpoint"]              is True
        assert v["no_real_stop_endpoint"]               is True
        assert v["no_position_modified"]                is True
        assert v["no_live_endpoint"]                    is True
        assert v["no_secrets_loaded"]                   is True
        assert v["no_secrets_emitted"]                  is True
        assert v["order_endpoint_called"]               is False
        assert v["stop_endpoint_called"]                is False
        assert v["status"] == STATUS_DRY_RUN_READY
        assert v["mode"]   == MODE_DRY_RUN_CHECKLIST

    def test_guard_does_not_flip_real_execution(self):
        r = _run(allow_real_runner_execution=True)
        env = r.stages[STAGE_7_FINAL_DRY_RUN_VERDICT]
        v = env["final_dry_run_verdict"]
        assert v["real_execution_allowed"] is False
        assert v["real_runner_execution_requested"] is True
        assert v["status"] == STATUS_REAL_RUNNER_NOT_IMPL
        assert v["mode"]   == MODE_REAL_RUNNER_EXECUTION_GUARD


# ===========================================================================
# AC36: G20 not lifted
# ===========================================================================

class TestAC36G20NotLifted:
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
# AC37: socket-disabled import smoke
# ===========================================================================

class TestAC37SocketDisabledImport:
    def test_module_safe_under_socket_disabled(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"]       = str(ROOT)
        cp = subprocess.run(
            [sys.executable, "-c",
             "import socket; socket.socket = None; "
             "import src.demo_tiny_lifecycle_runner_dry_run as m; "
             "print('OK', m.STATUS_DRY_RUN_READY)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=60,
        )
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout


# ===========================================================================
# AC38: dataclass roundtrip with deep-copy
# ===========================================================================

class TestAC38DataclassRoundTrip:
    def test_to_dict_roundtrip(self):
        r = _run(allow_dry_run_runner_approval=True)
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
            ("no_secrets_loaded",                   True),
            ("secret_value_observed",               False),
            ("g20_policy_still_in_place",           True),
            ("g20_lifted",                          False),
            ("current_task_real_execution_allowed", False),
            ("real_runner_implemented",             False),
            ("real_execution_allowed",              False),
            ("dry_run_runner_approval_allowed",     True),
            ("dry_run_trace_complete",              True),
        ):
            assert d[key] is expected, f"{key} should be {expected}"
        assert d["status"] == STATUS_DRY_RUN_READY_EXEC_DISABLED
        # Deep-copy: mutating returned dict must not affect source.
        d["stages"][STAGE_2_STATE_MACHINE_TRACE]["mutated"] = True
        assert "mutated" not in r.stages[STAGE_2_STATE_MACHINE_TRACE]
        d["state_machine_trace"][0]["mutated"] = True
        assert "mutated" not in r.state_machine_trace[0]
        d["dry_run_request_envelopes"]["entry_request_envelope"]["mutated"] = True
        assert "mutated" not in r.dry_run_request_envelopes["entry_request_envelope"]
        d["audit_artifacts"]["pre_snapshot"]["mutated"] = True
        assert "mutated" not in r.audit_artifacts["pre_snapshot"]


# ===========================================================================
# AC39: path refs
# ===========================================================================

class TestAC39PathRefs:
    def test_path_refs(self):
        r = _run()
        assert r.order_create_path_ref == ORDER_CREATE_PATH_REF
        assert r.trading_stop_path_ref == TRADING_STOP_PATH_REF
        assert r.base_url_ref          == BASE_URL_DEMO_REF


# ===========================================================================
# AC40: safety invariants on dataclass
# ===========================================================================

class TestAC40SafetyInvariants:
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
        assert r.no_secrets_loaded is True
        assert r.secret_value_observed is False
        assert r.existing_positions_touched == []

    def test_dry_run_approval(self):
        r = _run(allow_dry_run_runner_approval=True)
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
# AC41: gate count >= 73
# ===========================================================================

class TestAC41GateCount:
    def test_at_least_73(self):
        import src.demo_tiny_lifecycle_runner_dry_run as m
        gate_names = [
            n for n in dir(m)
            if n.startswith("GATE_") and isinstance(getattr(m, n), str)
        ]
        assert len(gate_names) >= 73, (
            f"Expected >= 73 GATE_ constants, got {len(gate_names)}: "
            f"{sorted(gate_names)}"
        )


# ===========================================================================
# AC42: always-on gates surface in every checklist
# ===========================================================================

class TestAC42AlwaysOnGates:
    def test_always_on_present(self):
        r = _run()
        unique = set(r.blocked_gates)
        for g in (
            # dry-run scope
            GATE_DRY_RUN_RUNNER_TRUE,
            GATE_REAL_RUNNER_NOT_IMPLEMENTED,
            GATE_REAL_EXECUTION_NOT_ALLOWED,
            GATE_NO_ENDPOINT_INVOKED,
            GATE_NO_POSITION_MODIFIED_SCOPE,
            GATE_NO_SECRETS_LOADED,
            GATE_NO_G20_LIFT,
            # trace
            GATE_EIGHT_STEP_TRACE_COMPLETE,
            GATE_REQUIRED_STATES_OBSERVED,
            GATE_NO_AUTO_ADVANCE_TRACE,
            GATE_NO_PARALLEL_EXECUTION_TRACE,
            GATE_NO_SKIP_STEP_TRACE,
            GATE_NO_RETRY_LOOP_TRACE,
            GATE_TRACE_STEP_ENDPOINT_NOT_CALLED,
            GATE_TRACE_STEP_POSITION_NOT_MODIFIED,
            GATE_TRACE_STEP_TOKEN_NOT_VALIDATED,
            # payload (signature / private headers / sender adapter always-on)
            GATE_NO_SIGNATURE,
            GATE_NO_PRIVATE_HEADERS,
            GATE_NO_SENDER_ADAPTER,
            # readonly simulation
            GATE_POST_ENTRY_VERIFICATION_SIMULATED,
            GATE_POST_STOP_VERIFICATION_SIMULATED,
            GATE_POST_CLEANUP_VERIFICATION_SIMULATED,
            GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED,
            GATE_VERIFICATION_SOURCE_ARTIFACT_ONLY,
            # audit
            GATE_ELEVEN_AUDIT_SLOTS_PRESENT,
            GATE_RESPONSES_SANITIZED,
            GATE_RESPONSE_FROM_EXCHANGE_FALSE,
            GATE_NO_SECRETS_IN_AUDIT,
            GATE_DISCORD_SANITIZED_ONLY,
            GATE_NOTION_SANITIZED_ONLY,
            # failure simulation
            GATE_ENTRY_FAILURE_FAIL_CLOSED,
            GATE_STOP_FAILURE_FAIL_CLOSED,
            GATE_CLEANUP_FAILURE_FAIL_CLOSED,
            GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
            GATE_PARTIAL_FILL_FAIL_CLOSED,
            GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW,
            GATE_UNEXPECTED_POSITION_MANUAL_REVIEW,
            GATE_NO_AUTO_RETRY,
            GATE_NO_AUTO_CLEANUP,
            GATE_NO_AUTO_EMERGENCY_CLOSE,
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
# AC43: no forbidden imports
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
    "src.demo_tiny_lifecycle_runner_design",
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


class TestAC43NoForbiddenImports:
    def test_module(self):
        imp = _collect_imports(_MODULE_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in module"

    def test_cli(self):
        imp = _collect_imports(_SCRIPT_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in CLI"


# ===========================================================================
# AC44: no sender reuse
# ===========================================================================

class TestAC44NoSenderReuse:
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

    def test_no_runner_design_module_reuse(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTinyLifecycleRunnerDesign" not in code

    def test_no_summary_module_reuse(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTinyLifecycleRealExecutionSummary" not in code


# ===========================================================================
# AC45: no network/env/signing tokens
# ===========================================================================

class TestAC45NoNetworkTokens:
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
# AC46: forbidden flags do not exist anywhere
# ===========================================================================

class TestAC46NoForbiddenFlags:
    @pytest.mark.parametrize("flag", [
        "--execute-real-lifecycle",
        "--execute-real-entry",
        "--execute-real-stop",
        "--execute-real-cleanup",
        "--execute-real-runner",
        "--send-order",
        "--place-order",
    ])
    def test_flag_absent_in_module(self, flag):
        code = _read_code_only(_MODULE_PATH)
        assert flag not in code

    @pytest.mark.parametrize("flag", [
        "--execute-real-lifecycle",
        "--execute-real-entry",
        "--execute-real-stop",
        "--execute-real-cleanup",
        "--execute-real-runner",
        "--send-order",
        "--place-order",
    ])
    def test_flag_absent_in_cli(self, flag):
        code = _read_code_only(_SCRIPT_PATH)
        assert flag not in code

    def test_flag_token_absent_in_module(self):
        code = _read_code_only(_MODULE_PATH)
        for ident in ("execute_real_lifecycle", "execute_real_entry",
                      "execute_real_stop", "execute_real_cleanup",
                      "execute_real_runner", "send_order", "place_order"):
            assert ident not in code

    def test_flag_token_absent_in_cli(self):
        code = _read_code_only(_SCRIPT_PATH)
        for ident in ("execute_real_lifecycle", "execute_real_entry",
                      "execute_real_stop", "execute_real_cleanup",
                      "execute_real_runner", "send_order", "place_order"):
            assert ident not in code


# ===========================================================================
# AC47: token patterns surfaced + 3 distinct
# ===========================================================================

class TestAC47TokenPatterns:
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
# AC48: stage_0 artifact preflight reports all 12 upstream artifacts present
# ===========================================================================

class TestAC48Stage0PreflightAllPresent:
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
        assert env["runner_design_present"]                    is True
        assert env["current_task_real_execution_allowed"]      is False


# ===========================================================================
# AC49: report artifacts written (dry-run checklist)
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
        des_d  = base / "design";      des_d.mkdir()
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
        (des_d  / "latest_tiny_lifecycle_runner_design.json").write_text(json.dumps(_valid_runner_design()), encoding="utf-8")
        return ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, sp_d, cp_d, sum_d, des_d, out_d


class TestAC49ReportChecklist(_ReportSetupMixin):
    def test_writes_report(self):
        from scripts.preview_demo_tiny_lifecycle_runner_dry_run import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d,
             rp_d, ep_d, sp_d, cp_d, sum_d, des_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_dry_run_runner_approval=False,
                allow_real_runner_execution=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d, tiny_cleanup_dir=cp_d,
                lifecycle_summary_dir=sum_d,
                runner_design_dir=des_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            files = sorted(p.name for p in out_d.iterdir())
            assert "latest_tiny_lifecycle_runner_dry_run.json" in files
            assert "latest_tiny_lifecycle_runner_dry_run.md"   in files
            data = json.loads(
                (out_d / "latest_tiny_lifecycle_runner_dry_run.json").read_text(encoding="utf-8")
            )
            assert data["status"] == STATUS_DRY_RUN_READY
            assert data["real_execution_allowed"] is False
            assert data["real_runner_implemented"] is False
            assert data["order_endpoint_called"] is False
            assert data["stop_endpoint_called"] is False
            assert data["no_position_modified"] is True
            assert len(data["runner_states"]) == 18
            assert len(data["required_audit_artifacts"]) == 11
            assert len(data["state_machine_trace"]) == 8


# ===========================================================================
# AC50: no secrets in report
# ===========================================================================

class TestAC50NoSecretsInReport(_ReportSetupMixin):
    def test_no_secrets(self):
        from scripts.preview_demo_tiny_lifecycle_runner_dry_run import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d,
             rp_d, ep_d, sp_d, cp_d, sum_d, des_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_dry_run_runner_approval=False,
                allow_real_runner_execution=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d, tiny_cleanup_dir=cp_d,
                lifecycle_summary_dir=sum_d,
                runner_design_dir=des_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            md = (out_d / "latest_tiny_lifecycle_runner_dry_run.md").read_text(encoding="utf-8")
            for forbidden in ("API_KEY", "API_SECRET", "BYBIT_API", "X-BAPI-SIGN"):
                assert forbidden not in md
            data = json.loads(
                (out_d / "latest_tiny_lifecycle_runner_dry_run.json").read_text(encoding="utf-8")
            )
            assert data["secret_value_observed"] is False


# ===========================================================================
# AC51: CLI valid run exits 0 + missing artifact exits 1
# ===========================================================================

class TestAC51CLIExitCodes(_ReportSetupMixin):
    def test_subprocess_exits_0(self):
        from scripts.preview_demo_tiny_lifecycle_runner_dry_run import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d,
             rp_d, ep_d, sp_d, cp_d, sum_d, des_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_dry_run_runner_approval=False,
                allow_real_runner_execution=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d, tiny_cleanup_dir=cp_d,
                lifecycle_summary_dir=sum_d,
                runner_design_dir=des_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0

    def test_subprocess_missing_exits_1(self):
        from scripts.preview_demo_tiny_lifecycle_runner_dry_run import run_execute
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for sub in ("readonly", "recon", "protection", "contract", "noop",
                        "lifecycle", "real_perm", "entry_perm", "stop_perm",
                        "cleanup_perm", "summary", "design"):
                (base / sub).mkdir()
            rc = run_execute(
                symbol="SOLUSDT",
                allow_dry_run_runner_approval=False,
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
                runner_design_dir=base / "design",
                output_dir=base / "out", _now=_TEST_NOW,
            )
            assert rc == 1


# ===========================================================================
# AC52: next_required_task points at TASK-014AD
# ===========================================================================

class TestAC52NextTaskIs014AD:
    def test_next_required_task(self):
        r = _run()
        assert r.next_required_task == (
            "TASK-014AD_tiny_lifecycle_real_execution_guarded_runner_design_review"
        )


# ===========================================================================
# AC53: upstream lifecycle summary status echoed
# ===========================================================================

class TestAC53UpstreamSummaryStatusEchoed:
    def test_echoed(self):
        r = _run()
        assert r.upstream_lifecycle_summary_status == (
            "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY"
        )


# ===========================================================================
# AC54: upstream runner design status echoed
# ===========================================================================

class TestAC54UpstreamRunnerDesignStatusEchoed:
    def test_echoed(self):
        r = _run()
        assert r.upstream_runner_design_status == (
            "TINY_LIFECYCLE_RUNNER_DESIGN_READY"
        )


# ===========================================================================
# AC55: status promotion vs. fail-closed precedence
# ===========================================================================

class TestAC55StatusPrecedence:
    def test_hard_fail_beats_approval(self):
        # Even with --allow-dry-run-runner-approval, a missing upstream
        # artifact must downgrade to FAIL_CLOSED.
        r = _run(readonly=None, allow_dry_run_runner_approval=True)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED

    def test_hard_fail_beats_execution_guard(self):
        # Even with --allow-real-runner-execution, a hard-fail upstream
        # must downgrade to FAIL_CLOSED (not promote to NOT_IMPL).
        r = _run(runner_design=None, allow_real_runner_execution=True)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED


# ===========================================================================
# AC56: dry-run scope flags
# ===========================================================================

class TestAC56DryRunScopeFlags:
    def test_dry_run_runner_true(self):
        r = _run()
        assert r.dry_run_scope["dry_run_runner"] is True
        assert r.dry_run_scope["real_runner_implemented"] is False
        assert r.dry_run_scope["no_endpoint_invoked_in_this_task"] is True
        assert r.dry_run_scope["g20_policy_still_in_place"] is True
        assert r.dry_run_scope["g20_lifted"] is False


# ===========================================================================
# AC57: ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES whitelist contains 3 statuses
# ===========================================================================

class TestAC57AcceptableSummaryWhitelist:
    def test_three_statuses(self):
        assert len(ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES) == 3
        assert "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY" in ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES

    def test_runner_design_three_statuses(self):
        assert len(ACCEPTABLE_RUNNER_DESIGN_STATUSES) == 3
        assert "TINY_LIFECYCLE_RUNNER_DESIGN_READY" in ACCEPTABLE_RUNNER_DESIGN_STATUSES


# ===========================================================================
# AC58: runner_design_status_acceptable list sorted
# ===========================================================================

class TestAC58RunnerDesignStatusAcceptableSurfaced:
    def test_sorted_list_surfaced(self):
        r = _run()
        env = r.stages[STAGE_0_ARTIFACT_PREFLIGHT]
        assert env["runner_design_status_acceptable"] == sorted(
            ACCEPTABLE_RUNNER_DESIGN_STATUSES
        )


# ===========================================================================
# AC59: no signature / no private headers in any envelope
# ===========================================================================

class TestAC59NoSignatureInEnvelopes:
    def test_no_signature(self):
        r = _run()
        for which in ("entry_request_envelope", "stop_request_envelope",
                      "cleanup_request_envelope"):
            e = r.dry_run_request_envelopes[which]
            assert e["signature_present"] is False
            assert e["private_headers"] == []
            # Headers preview only contains content-type, never auth
            assert "X-BAPI-API-KEY" not in e["headers_preview"]
            assert "X-BAPI-SIGN"    not in e["headers_preview"]
            assert "Authorization"  not in e["headers_preview"]


# ===========================================================================
# AC60: existing positions never touched even with all flags set
# ===========================================================================

class TestAC60ExistingPositionsNotTouched:
    def test_default(self):
        r = _run()
        assert r.existing_positions_touched == []
        assert set(r.existing_position_symbols) == set(EXISTING_POSITION_SYMBOLS)

    def test_with_dry_run_approval(self):
        r = _run(allow_dry_run_runner_approval=True)
        assert r.existing_positions_touched == []

    def test_with_real_execution_guard(self):
        r = _run(allow_real_runner_execution=True)
        assert r.existing_positions_touched == []


# ===========================================================================
# AC61: blocked_gates deduplicated
# ===========================================================================

class TestAC61BlockedGatesDeduped:
    def test_no_duplicates(self):
        r = _run()
        assert len(r.blocked_gates) == len(set(r.blocked_gates))
