"""
tests/demo_trading/test_demo_tiny_guarded_stop_attach_dry_run_adapter.py
TASK-014AF: Guarded Stop-attach-only Dry-run Adapter tests (AF1 - AF65).

Covers stop_adapter_checklist / stop_dry_run_approval /
real_stop_execution_guard / fail_closed paths; all 9 stages; 111 gate
constants; 13-artifact preflight contract (10 baseline + AA lifecycle
summary + AB runner design + AC runner dry-run + AD guarded design
review + AE guarded entry adapter --- minus the entry / cleanup
permission gates, since this adapter is stop-attach-only); AD
readiness_conclusion == DESIGN_REVIEW_READY_NOT_EXECUTABLE required;
AE adapter status acceptable required; stop-attach precondition
contract (SOLUSDT post-entry / long / qty 0.1 / entry ref 64.4 /
stopLoss 61.18 / tpslMode Full / slTriggerBy MarkPrice / positionIdx 0
/ category linear); manual token contract
(CONFIRM_DEMO_TINY_STOP_ATTACH_*) never validated; preview-only
request envelope with no signature / no private headers / trading-stop
path ref / demo base url; pre/post readonly verification plan; failure
policy (FAIL_CLOSED / MANUAL_REVIEW_REQUIRED); status precedence;
source-scan safety (no urlopen / no forbidden imports / no signing /
no os.environ / no AE module reuse); report artifacts; forbidden-flag
absence (--execute-real-* / --send-order / --place-order /
--real-run); the invariant that TASK-014L sender G20
(protected_entry_policy_missing) still blocks --execute-new-entry and
is NOT lifted here; next_required_task points at TASK-014AG.
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

from src.demo_tiny_guarded_stop_attach_dry_run_adapter import (
    ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES,
    ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES,
    ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES,
    ACCEPTABLE_RUNNER_DESIGN_STATUSES,
    ACCEPTABLE_RUNNER_DRY_RUN_STATUSES,
    ALL_STAGES,
    BASE_URL_DEMO_REF,
    BASE_URL_LIVE_REF,
    DEFAULT_SELECTED_SYMBOL,
    DEMO_ENDPOINT_ALLOWLIST,
    DRY_RUN_NOT_SENT_MARKER,
    DemoTinyGuardedStopAttachDryRunAdapter,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_ENTRY_REFERENCE_PRICE,
    EXPECTED_EXISTING_POSITION_COUNT,
    EXPECTED_INSTRUMENT_CATEGORY,
    EXPECTED_MAX_NOTIONAL_USDT,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_POSITION_IDX,
    EXPECTED_POST_ENTRY_QTY,
    EXPECTED_POST_ENTRY_SIDE,
    EXPECTED_POST_ENTRY_SYMBOL,
    EXPECTED_PROOF_STRENGTH,
    EXPECTED_SL_TRIGGER_BY,
    EXPECTED_STOP_LOSS,
    EXPECTED_TICK_SIZE,
    EXPECTED_TPSL_MODE,
    FORBIDDEN_LOG_FIELDS,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_AUDIT_ARTIFACTS_PRESENT,
    GATE_AUDIT_NO_SECRETS,
    GATE_AUDIT_RESPONSE_DRY_RUN_NOT_SENT,
    GATE_AUDIT_RESPONSE_FROM_EXCHANGE_FALSE,
    GATE_AUDIT_SANITIZED,
    GATE_CLEANUP_NOT_INCLUDED,
    GATE_CONFIRMATION_FLAGS_NOT_VALIDATED,
    GATE_CONTRACT_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_NOT_INCLUDED,
    GATE_ENVELOPE_BASE_URL_DEMO_ONLY,
    GATE_ENVELOPE_ENDPOINT_NOT_CALLED,
    GATE_ENVELOPE_NO_PRIVATE_HEADERS,
    GATE_ENVELOPE_NO_SIGNATURE,
    GATE_ENVELOPE_NOT_REAL_PAYLOAD,
    GATE_ENVELOPE_PREVIEW_ONLY,
    GATE_ENVELOPE_SEND_NOT_ALLOWED,
    GATE_ENVELOPE_SL_TRIGGER_BY_MARK_PRICE,
    GATE_ENVELOPE_STOP_LOSS_VALUE,
    GATE_ENVELOPE_TPSL_MODE_FULL,
    GATE_ENVELOPE_TRADING_STOP_PATH,
    GATE_EXISTING_POSITIONS_UNCHANGED_REQUIRED,
    GATE_EXPECTED_COUNT_FLAG_DOCUMENTED,
    GATE_EXPECTED_ENTRY_QTY_FLAG_DOCUMENTED,
    GATE_EXPECTED_ENTRY_SYMBOL_FLAG_DOCUMENTED,
    GATE_EXPECTED_STOP_LOSS_FLAG_DOCUMENTED,
    GATE_EXPECTED_SYMBOLS_FLAG_DOCUMENTED,
    GATE_FULL_LIFECYCLE_NOT_INCLUDED,
    GATE_G20_NOT_LIFTED,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_GUARDED_DESIGN_REVIEW_MISSING,
    GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE,
    GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE,
    GATE_GUARDED_ENTRY_ADAPTER_MISSING,
    GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE,
    GATE_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_ONLY,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_LIFECYCLE_SUMMARY_MISSING,
    GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED,
    GATE_MAX_NOTIONAL_FLAG_DOCUMENTED,
    GATE_NO_AUTO_CLEANUP,
    GATE_NO_AUTO_EMERGENCY_CLOSE,
    GATE_NO_AUTO_ENTRY,
    GATE_NO_AUTO_NEXT_STEP,
    GATE_NO_AUTO_RETRY,
    GATE_NO_ENDPOINT_INVOKED,
    GATE_NO_G20_LIFT,
    GATE_NO_LIVE_ENDPOINT,
    GATE_NO_POSITION_MODIFIED,
    GATE_NO_POSITION_MODIFIED_SCOPE,
    GATE_NO_REAL_ORDER_ENDPOINT,
    GATE_NO_REAL_STOP_ENDPOINT,
    GATE_NO_SECRETS_EMITTED,
    GATE_NO_SECRETS_LOADED,
    GATE_NO_SENDER_ADAPTER,
    GATE_NOOP_PLAN_MISSING,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_POST_STOP_EXPECTED_STOP_LOSS,
    GATE_POST_STOP_EXPECTED_TRIGGER_BY,
    GATE_POST_STOP_READONLY_REQUIRED,
    GATE_PRE_STOP_EXPECTED_QTY,
    GATE_PRE_STOP_EXPECTED_SIDE_LONG,
    GATE_PRE_STOP_EXPECTED_SYMBOL,
    GATE_PRE_STOP_READONLY_REQUIRED,
    GATE_PRE_STOP_SELECTED_SYMBOL_PRESENT,
    GATE_PRECONDITION_ACCOUNT_MODE_DEMO,
    GATE_PRECONDITION_CATEGORY_LINEAR,
    GATE_PRECONDITION_ENDPOINT_FAMILY_BYBIT_DEMO,
    GATE_PRECONDITION_ENTRY_REFERENCE_VALID,
    GATE_PRECONDITION_EXPECTED_ENTRY_SYMBOL,
    GATE_PRECONDITION_EXPECTED_PROTECTED_LIST,
    GATE_PRECONDITION_POSITION_IDX_ZERO,
    GATE_PRECONDITION_PROOF_STRENGTH_STRONG,
    GATE_PRECONDITION_QTY_TINY,
    GATE_PRECONDITION_SELECTED_SYMBOL_PRESENT,
    GATE_PRECONDITION_SIDE_LONG,
    GATE_PRECONDITION_SL_TRIGGER_BY_MARK_PRICE,
    GATE_PRECONDITION_STOP_LOSS_BELOW_ENTRY,
    GATE_PRECONDITION_STOP_LOSS_TICK_ALIGNED,
    GATE_PRECONDITION_STOP_LOSS_VALUE,
    GATE_PRECONDITION_SYMBOL_MATCHES,
    GATE_PRECONDITION_TPSL_MODE_FULL,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW,
    GATE_PROTECTION_MISSING,
    GATE_READONLY_SMOKE_MISSING,
    GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
    GATE_REAL_EXECUTION_NOT_ALLOWED,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED,
    GATE_REAL_STOP_ATTACH_EXECUTION_NOT_IMPL,
    GATE_REAL_STOP_ATTACH_NOT_IMPLEMENTED,
    GATE_RECONCILIATION_MISSING,
    GATE_REQUEST_REJECTED_FAIL_CLOSED,
    GATE_RUNNER_DESIGN_MISSING,
    GATE_RUNNER_DRY_RUN_MISSING,
    GATE_SECOND_CONFIRMATION_DOCUMENTED,
    GATE_SECRET_EMISSION_FAIL_CLOSED,
    GATE_SELECTED_SYMBOL_ABSENT_FAIL_CLOSED,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
    GATE_SELECTED_SYMBOL_QTY_MISMATCH_FAIL_CLOSED,
    GATE_SELECTED_SYMBOL_SIDE_MISMATCH_FAIL_CLOSED,
    GATE_STOP_ATTACH_ONLY,
    GATE_STOP_ENVELOPE_PRESENT,
    GATE_STOP_LOSS_INVALID_FAIL_CLOSED,
    GATE_STOP_TOKEN_PATTERN_PRESENT,
    GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING,
    GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
    GATE_TOKEN_NOT_VALIDATED,
    GATE_VERIFICATION_PLAN_ONLY,
    MODE_FAIL_CLOSED,
    MODE_REAL_STOP_EXECUTION_GUARD,
    MODE_STOP_ADAPTER_CHECKLIST,
    MODE_STOP_DRY_RUN_APPROVAL,
    ORDER_CREATE_PATH_REF,
    READINESS_CONCLUSION_NOT_EXECUTABLE,
    REQUIRED_CONFIRMATION_FLAGS,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_STOP_ADAPTER_SCOPE,
    STAGE_2_STOP_PRECONDITION_CONTRACT,
    STAGE_3_MANUAL_CONFIRMATION_DRY_RUN_CONTRACT,
    STAGE_4_STOP_REQUEST_ENVELOPE_DRY_RUN,
    STAGE_5_STOP_READONLY_VERIFICATION_PLAN,
    STAGE_6_STOP_FAILURE_POLICY,
    STAGE_7_AUDIT_ARTIFACT_GENERATION,
    STAGE_8_FINAL_STOP_ADAPTER_VERDICT,
    STATUS_ADAPTER_READY,
    STATUS_ADAPTER_READY_EXEC_DISABLED,
    STATUS_FAIL_CLOSED,
    STATUS_REAL_STOP_NOT_IMPL,
    STOP_TOKEN_PATTERN,
    TRADING_STOP_PATH_REF,
    TinyGuardedStopAttachDryRunAdapterResult,
)


_MODULE_PATH = ROOT / "src" / "demo_tiny_guarded_stop_attach_dry_run_adapter.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_tiny_guarded_stop_attach_dry_run_adapter.py"
_TEST_NOW    = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _valid_readonly() -> dict:
    return {
        "timestamp_utc":          "2026-06-11T10:00:00Z",
        "endpoint_family":        EXPECTED_ENDPOINT_FAMILY,
        "account_mode":           EXPECTED_ACCOUNT_MODE,
        "proof_strength":         EXPECTED_PROOF_STRENGTH,
        "demo_runtime_verified":  True,
        "equity_usd":             500.0,
        "available_balance_usd":  400.0,
    }


def _valid_reconciliation() -> dict:
    return {
        "timestamp_utc":           "2026-06-11T10:05:00Z",
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
        "timestamp_utc":          "2026-06-11T11:00:00Z",
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
        "timestamp_utc":      "2026-06-11T11:30:00Z",
        "mode":               "preview",
        "selected_symbol":    "SOLUSDT",
        "path":               TRADING_STOP_PATH_REF,
        "method":             "POST",
        "real_probe_allowed": False,
        "status":             "TRADING_STOP_CONTRACT_PREVIEW_OK",
    }


def _valid_noop_plan() -> dict:
    return {
        "timestamp_utc":     "2026-06-11T11:45:00Z",
        "mode":              "plan",
        "selected_symbol":   "SOLUSDT",
        "recommended_path":  "real_tiny_position_with_stop_lifecycle",
        "status":            "NOOP_PROBE_PLAN_READY",
    }


def _valid_lifecycle() -> dict:
    return {
        "timestamp_utc":             "2026-06-11T11:55:00Z",
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
        "timestamp_utc":             "2026-06-11T11:58:00Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "REAL_PERMISSION_CHECKLIST_READY",
        "real_execution_allowed":              False,
        "real_tiny_position_implemented":      False,
        "current_task_real_execution_allowed": False,
    }


def _valid_tiny_stop_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-11T11:59:00Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "TINY_STOP_ATTACH_PERMISSION_CHECKLIST_READY",
        "stop_loss":                 61.18,
        "real_execution_allowed":              False,
        "current_task_real_execution_allowed": False,
    }


def _valid_lifecycle_summary() -> dict:
    return {
        "timestamp_utc":                  "2026-06-11T11:59:55Z",
        "mode":                           "checklist",
        "selected_symbol":                "SOLUSDT",
        "status":                         "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY",
        "expected_entry_reference_price": 64.87,
        "real_execution_allowed":              False,
        "real_lifecycle_runner_implemented":   False,
        "current_task_real_execution_allowed": False,
    }


def _valid_runner_design() -> dict:
    return {
        "timestamp_utc":                  "2026-06-11T11:59:58Z",
        "mode":                           "design_checklist",
        "selected_symbol":                "SOLUSDT",
        "status":                         "TINY_LIFECYCLE_RUNNER_DESIGN_READY",
        "real_execution_allowed":              False,
        "real_runner_implemented":             False,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _valid_runner_dry_run() -> dict:
    return {
        "timestamp_utc":                  "2026-06-11T11:59:59Z",
        "mode":                           "dry_run_checklist",
        "selected_symbol":                "SOLUSDT",
        "status":                         "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY",
        "real_execution_allowed":              False,
        "real_runner_implemented":             False,
        "current_task_real_execution_allowed": False,
        "dry_run_trace_complete":              True,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _valid_guarded_design_review() -> dict:
    return {
        "timestamp_utc":             "2026-06-11T11:59:59.5Z",
        "mode":                      "design_review_checklist",
        "selected_symbol":           "SOLUSDT",
        "status":                    "TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY",
        "readiness_conclusion":      READINESS_CONCLUSION_NOT_EXECUTABLE,
        "real_execution_allowed":              False,
        "real_runner_implemented":             False,
        "guarded_runner_implemented":          False,
        "guarded_runner_design_review":        True,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _valid_guarded_entry_adapter() -> dict:
    return {
        "timestamp_utc":             "2026-06-11T11:59:59.8Z",
        "mode":                      "entry_adapter_checklist",
        "selected_symbol":           "SOLUSDT",
        "status":                    "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY",
        "readiness_conclusion":      READINESS_CONCLUSION_NOT_EXECUTABLE,
        "real_execution_allowed":              False,
        "real_entry_implemented":              False,
        "guarded_entry_dry_run_adapter":       True,
        "entry_only":                          True,
        "stop_attach_included":                False,
        "cleanup_included":                    False,
        "full_lifecycle_included":             False,
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


def _adapter() -> DemoTinyGuardedStopAttachDryRunAdapter:
    return DemoTinyGuardedStopAttachDryRunAdapter()


_UNSET = object()


def _run(
    *,
    readonly=_UNSET, recon=_UNSET, protection=_UNSET, contract=_UNSET,
    noop_plan=_UNSET, lifecycle=_UNSET, real_permission_gate=_UNSET,
    tiny_stop_attach_permission_gate=_UNSET,
    lifecycle_summary=_UNSET,
    runner_design=_UNSET,
    runner_dry_run=_UNSET,
    guarded_design_review=_UNSET,
    guarded_entry_adapter=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    allow_stop_dry_run_approval=False,
    allow_real_stop_execution=False,
    _now=_TEST_NOW,
) -> TinyGuardedStopAttachDryRunAdapterResult:
    return _adapter().run_checklist(
        readonly_smoke=_valid_readonly()                                         if readonly                       is _UNSET else readonly,
        reconciliation=_valid_reconciliation()                                   if recon                          is _UNSET else recon,
        protection=_valid_protection()                                           if protection                     is _UNSET else protection,
        contract=_valid_contract()                                               if contract                       is _UNSET else contract,
        noop_plan=_valid_noop_plan()                                             if noop_plan                      is _UNSET else noop_plan,
        lifecycle_mock=_valid_lifecycle()                                        if lifecycle                      is _UNSET else lifecycle,
        real_permission_gate=_valid_real_permission_gate()                       if real_permission_gate           is _UNSET else real_permission_gate,
        tiny_stop_attach_permission_gate=_valid_tiny_stop_permission_gate()      if tiny_stop_attach_permission_gate is _UNSET else tiny_stop_attach_permission_gate,
        lifecycle_summary=_valid_lifecycle_summary()                             if lifecycle_summary              is _UNSET else lifecycle_summary,
        runner_design=_valid_runner_design()                                     if runner_design                  is _UNSET else runner_design,
        runner_dry_run=_valid_runner_dry_run()                                   if runner_dry_run                 is _UNSET else runner_dry_run,
        guarded_design_review=_valid_guarded_design_review()                     if guarded_design_review          is _UNSET else guarded_design_review,
        guarded_entry_adapter=_valid_guarded_entry_adapter()                     if guarded_entry_adapter          is _UNSET else guarded_entry_adapter,
        symbol=symbol,
        allow_stop_dry_run_approval=allow_stop_dry_run_approval,
        allow_real_stop_execution=allow_real_stop_execution,
        _now=_now,
    )


# ===========================================================================
# AF1: valid checklist => TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY
# ===========================================================================

class TestAF1AdapterReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_ADAPTER_READY
        assert r.mode == MODE_STOP_ADAPTER_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.real_execution_allowed is False
        assert r.real_stop_attach_implemented is False
        assert r.guarded_stop_attach_dry_run_adapter is True
        assert r.stop_attach_only is True
        assert r.entry_included is False
        assert r.cleanup_included is False
        assert r.full_lifecycle_included is False
        assert r.current_task_real_execution_allowed is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.next_required_task == "TASK-014AG_guarded_cleanup_only_dry_run_adapter"


# ===========================================================================
# AF2: --allow-stop-dry-run-approval => READY_BUT_EXECUTION_DISABLED
# ===========================================================================

class TestAF2StopDryRunApproval:
    def test_approval(self):
        r = _run(allow_stop_dry_run_approval=True)
        assert r.status == STATUS_ADAPTER_READY_EXEC_DISABLED
        assert r.mode == MODE_STOP_DRY_RUN_APPROVAL
        assert r.stop_dry_run_approval_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_stop_attach_implemented is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE


# ===========================================================================
# AF3: --allow-real-stop-execution => REAL_STOP_ATTACH_EXECUTION_NOT_IMPLEMENTED
# ===========================================================================

class TestAF3RealStopExecutionGuard:
    def test_guard(self):
        r = _run(allow_real_stop_execution=True)
        assert r.status == STATUS_REAL_STOP_NOT_IMPL
        assert r.mode == MODE_REAL_STOP_EXECUTION_GUARD
        assert r.real_stop_execution_requested is True
        assert r.real_execution_allowed is False
        assert r.real_stop_attach_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.no_position_modified is True


# ===========================================================================
# AF4-AF16: 13 missing upstream artifacts each => FAIL_CLOSED
# ===========================================================================

class TestAF4MissingReadonly:
    def test_fail_closed(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert r.failed_stage == STAGE_0_ARTIFACT_PREFLIGHT
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestAF5MissingReconciliation:
    def test_fail_closed(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestAF6MissingProtection:
    def test_fail_closed(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestAF7MissingContract:
    def test_fail_closed(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestAF8MissingNoopPlan:
    def test_fail_closed(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestAF9MissingLifecycle:
    def test_fail_closed(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestAF10MissingRealPermissionGate:
    def test_fail_closed(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAF11MissingTinyStopAttachPermissionGate:
    def test_fail_closed(self):
        r = _run(tiny_stop_attach_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAF12MissingLifecycleSummary:
    def test_fail_closed(self):
        r = _run(lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAF13MissingRunnerDesign:
    def test_fail_closed(self):
        r = _run(runner_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DESIGN_MISSING in r.blocked_gates


class TestAF14MissingRunnerDryRun:
    def test_fail_closed(self):
        r = _run(runner_dry_run=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DRY_RUN_MISSING in r.blocked_gates


class TestAF15MissingGuardedDesignReview:
    def test_fail_closed(self):
        r = _run(guarded_design_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_MISSING in r.blocked_gates


class TestAF16MissingGuardedEntryAdapter:
    def test_fail_closed(self):
        r = _run(guarded_entry_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_ENTRY_ADAPTER_MISSING in r.blocked_gates


# ===========================================================================
# AF17: selected symbol must equal SOLUSDT; any existing demo position
#       symbol triggers GATE_SELECTED_SYMBOL_NOT_SOLUSDT (also caught as
#       hard-fail) => FAIL_CLOSED
# ===========================================================================

class TestAF17SymbolNotSolusdt:
    @pytest.mark.parametrize("sym", list(EXISTING_POSITION_SYMBOLS))
    def test_fail_closed(self, sym):
        r = _run(symbol=sym)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert r.failed_stage == STAGE_0_ARTIFACT_PREFLIGHT
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in r.blocked_gates

    def test_fail_closed_other_symbol(self):
        r = _run(symbol="BTCUSDT")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in r.blocked_gates


# ===========================================================================
# AF18-AF21: upstream invariant mismatches
# ===========================================================================

class TestAF18EndpointFamilyMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["endpoint_family"] = "bybit_live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestAF19AccountModeMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["account_mode"] = "live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestAF20ProofStrengthMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["proof_strength"] = "WEAK"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROOF_STRENGTH_NOT_STRONG in r.blocked_gates


class TestAF21PositionDetailsSourceMismatch:
    def test_fail_closed(self):
        bad = _valid_reconciliation()
        bad["position_details_source"] = "mock"
        bad["mode"] = "mock"
        r = _run(recon=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY in r.blocked_gates


# ===========================================================================
# AF22: guarded_design_review status unacceptable => fail closed
# ===========================================================================

class TestAF22GuardedDesignReviewStatusUnacceptable:
    def test_fail_closed(self):
        bad = _valid_guarded_design_review()
        bad["status"] = "SOMETHING_ELSE"
        r = _run(guarded_design_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE in r.blocked_gates


# ===========================================================================
# AF23: guarded_design_review readiness conclusion executable => fail closed
# ===========================================================================

class TestAF23GuardedDesignReviewReadinessExecutable:
    def test_fail_closed(self):
        bad = _valid_guarded_design_review()
        bad["readiness_conclusion"] = "READY_TO_EXECUTE"
        r = _run(guarded_design_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE in r.blocked_gates


# ===========================================================================
# AF24: guarded_entry_adapter status unacceptable => fail closed
# ===========================================================================

class TestAF24GuardedEntryAdapterStatusUnacceptable:
    def test_fail_closed(self):
        bad = _valid_guarded_entry_adapter()
        bad["status"] = "SOMETHING_ELSE"
        r = _run(guarded_entry_adapter=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE in r.blocked_gates


# ===========================================================================
# AF25: missing --symbol
# ===========================================================================

class TestAF25MissingSymbol:
    def test_fail_closed(self):
        r = _run(symbol="")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_MISSING in r.blocked_gates


# ===========================================================================
# AF26: 9 stages present
# ===========================================================================

class TestAF269Stages:
    def test_stage_count(self):
        r = _run()
        assert len(r.stages) == 9
        assert r.stage_order == list(ALL_STAGES)
        for stage_id in ALL_STAGES:
            assert stage_id in r.stages
            assert r.stages[stage_id]["stage"] == stage_id


# ===========================================================================
# AF27: stop adapter scope content
# ===========================================================================

class TestAF27StopAdapterScope:
    def test_scope_flags(self):
        r = _run()
        s = r.stop_adapter_scope
        assert s["guarded_stop_attach_dry_run_adapter"] is True
        assert s["stop_attach_only"] is True
        assert s["entry_included"] is False
        assert s["cleanup_included"] is False
        assert s["full_lifecycle_included"] is False
        assert s["real_stop_attach_implemented"] is False
        assert s["real_execution_allowed"] is False
        assert s["order_endpoint_called"] is False
        assert s["stop_endpoint_called"] is False
        assert s["no_endpoint_invoked_in_this_task"] is True
        assert s["no_position_modified"] is True
        assert s["no_secrets_loaded"] is True
        assert s["g20_policy_still_in_place"] is True
        assert s["g20_lifted"] is False
        assert s["next_required_task"] == "TASK-014AG_guarded_cleanup_only_dry_run_adapter"


# ===========================================================================
# AF28: stop precondition contract
# ===========================================================================

class TestAF28StopPreconditionContract:
    def test_payload_invariants(self):
        r = _run()
        c = r.stop_precondition_contract
        assert c["selected_symbol"] == "SOLUSDT"
        assert c["expected_entry_symbol"] == EXPECTED_POST_ENTRY_SYMBOL == "SOLUSDT"
        assert c["expected_position_side"] == EXPECTED_POST_ENTRY_SIDE == "long"
        assert c["expected_qty"] == EXPECTED_POST_ENTRY_QTY == 0.1
        assert c["expected_entry_reference_price"] == EXPECTED_ENTRY_REFERENCE_PRICE == 64.4
        assert c["stopLoss"] == EXPECTED_STOP_LOSS == 61.18
        assert c["stop_loss_below_entry_reference"] is True
        assert c["tick_size"] == EXPECTED_TICK_SIZE == 0.01
        assert c["stop_loss_tick_aligned"] is True
        assert c["tpslMode"] == EXPECTED_TPSL_MODE == "Full"
        assert c["slTriggerBy"] == EXPECTED_SL_TRIGGER_BY == "MarkPrice"
        assert c["positionIdx"] == EXPECTED_POSITION_IDX == 0
        assert c["category"] == EXPECTED_INSTRUMENT_CATEGORY == "linear"
        assert c["selected_symbol_present_before_stop"] is True
        assert c["max_notional_usdt"] == EXPECTED_MAX_NOTIONAL_USDT == 10.0
        assert c["expected_existing_position_count"] == EXPECTED_EXISTING_POSITION_COUNT == 5
        assert c["expected_existing_symbols"] == list(EXISTING_POSITION_SYMBOLS)
        assert c["proof_strength"] == EXPECTED_PROOF_STRENGTH
        assert c["account_mode"] == EXPECTED_ACCOUNT_MODE
        assert c["endpoint_family"] == EXPECTED_ENDPOINT_FAMILY

    def test_gates_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_PRECONDITION_SYMBOL_MATCHES,
                  GATE_PRECONDITION_EXPECTED_ENTRY_SYMBOL,
                  GATE_PRECONDITION_SIDE_LONG,
                  GATE_PRECONDITION_QTY_TINY,
                  GATE_PRECONDITION_ENTRY_REFERENCE_VALID,
                  GATE_PRECONDITION_STOP_LOSS_VALUE,
                  GATE_PRECONDITION_STOP_LOSS_BELOW_ENTRY,
                  GATE_PRECONDITION_STOP_LOSS_TICK_ALIGNED,
                  GATE_PRECONDITION_TPSL_MODE_FULL,
                  GATE_PRECONDITION_SL_TRIGGER_BY_MARK_PRICE,
                  GATE_PRECONDITION_POSITION_IDX_ZERO,
                  GATE_PRECONDITION_CATEGORY_LINEAR,
                  GATE_PRECONDITION_SELECTED_SYMBOL_PRESENT,
                  GATE_PRECONDITION_EXPECTED_PROTECTED_LIST,
                  GATE_PRECONDITION_PROOF_STRENGTH_STRONG,
                  GATE_PRECONDITION_ACCOUNT_MODE_DEMO,
                  GATE_PRECONDITION_ENDPOINT_FAMILY_BYBIT_DEMO):
            assert g in blocked


# ===========================================================================
# AF29: manual confirmation dry-run contract
# ===========================================================================

class TestAF29ManualConfirmationContract:
    def test_token_pattern(self):
        r = _run()
        m = r.manual_confirmation_dry_run_contract
        assert m["stop_token_pattern"] == STOP_TOKEN_PATTERN
        assert m["token_validated"] is False
        assert m["token_format_not_authorization"] is True
        assert m["tokens_not_validated_in_this_task"] is True
        assert m["confirmation_flags_validated"] is False

    def test_required_flags(self):
        r = _run()
        m = r.manual_confirmation_dry_run_contract
        assert m["required_confirmation_flags"] == list(REQUIRED_CONFIRMATION_FLAGS)
        assert m["confirmation_flags_documented"] is True
        assert m["second_confirmation_required"] is True
        assert m["max_notional_cap_required"] is True
        assert m["expected_existing_position_count"] == 5
        assert m["expected_existing_symbols"] == list(EXISTING_POSITION_SYMBOLS)
        assert m["expected_existing_symbols_required"] is True
        assert m["expected_entry_symbol_required"] is True
        assert m["expected_entry_qty_required"] is True
        assert m["expected_stop_loss_required"] is True

    def test_gates_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_STOP_TOKEN_PATTERN_PRESENT, GATE_TOKEN_NOT_VALIDATED,
                  GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
                  GATE_SECOND_CONFIRMATION_DOCUMENTED,
                  GATE_MAX_NOTIONAL_FLAG_DOCUMENTED,
                  GATE_EXPECTED_COUNT_FLAG_DOCUMENTED,
                  GATE_EXPECTED_SYMBOLS_FLAG_DOCUMENTED,
                  GATE_EXPECTED_ENTRY_SYMBOL_FLAG_DOCUMENTED,
                  GATE_EXPECTED_ENTRY_QTY_FLAG_DOCUMENTED,
                  GATE_EXPECTED_STOP_LOSS_FLAG_DOCUMENTED,
                  GATE_CONFIRMATION_FLAGS_NOT_VALIDATED):
            assert g in blocked


# ===========================================================================
# AF30: stop request envelope - preview only, no signature, no headers
# ===========================================================================

class TestAF30StopRequestEnvelope:
    def test_envelope_safety_flags(self):
        r = _run()
        e = r.stop_request_envelope
        assert e["preview_only"] is True
        assert e["send_allowed"] is False
        assert e["endpoint_called"] is False
        assert e["real_payload"] is False
        assert e["signature_present"] is False
        assert e["private_headers"] == []
        assert e["no_sender_adapter"] is True

    def test_envelope_payload(self):
        r = _run()
        e = r.stop_request_envelope
        assert e["endpoint_path_ref"] == TRADING_STOP_PATH_REF
        assert e["base_url_ref"] == BASE_URL_DEMO_REF
        assert e["demo_endpoint_allowlist"] == [BASE_URL_DEMO_REF]
        assert e["live_endpoint_denylist"] == [BASE_URL_LIVE_REF]
        assert e["category"] == "linear"
        assert e["symbol"] == "SOLUSDT"
        assert e["stopLoss"] == EXPECTED_STOP_LOSS
        assert e["tpslMode"] == EXPECTED_TPSL_MODE
        assert e["slTriggerBy"] == EXPECTED_SL_TRIGGER_BY
        assert e["positionIdx"] == EXPECTED_POSITION_IDX

    def test_gates_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_STOP_ENVELOPE_PRESENT, GATE_ENVELOPE_PREVIEW_ONLY,
                  GATE_ENVELOPE_SEND_NOT_ALLOWED,
                  GATE_ENVELOPE_ENDPOINT_NOT_CALLED,
                  GATE_ENVELOPE_NOT_REAL_PAYLOAD,
                  GATE_ENVELOPE_NO_SIGNATURE,
                  GATE_ENVELOPE_NO_PRIVATE_HEADERS,
                  GATE_ENVELOPE_TRADING_STOP_PATH,
                  GATE_ENVELOPE_BASE_URL_DEMO_ONLY,
                  GATE_ENVELOPE_STOP_LOSS_VALUE,
                  GATE_ENVELOPE_TPSL_MODE_FULL,
                  GATE_ENVELOPE_SL_TRIGGER_BY_MARK_PRICE,
                  GATE_NO_SENDER_ADAPTER):
            assert g in blocked


# ===========================================================================
# AF31: readonly verification plan
# ===========================================================================

class TestAF31ReadonlyVerificationPlan:
    def test_pre_post_required(self):
        r = _run()
        p = r.stop_readonly_verification_plan
        assert p["pre_stop_readonly_required"] is True
        assert p["post_stop_readonly_required"] is True
        assert p["pre_stop_selected_symbol_present"] is True
        assert p["pre_stop_expected_symbol"] == "SOLUSDT"
        assert p["pre_stop_expected_qty"] == EXPECTED_POST_ENTRY_QTY
        assert p["pre_stop_expected_side"] == EXPECTED_POST_ENTRY_SIDE == "long"
        assert p["post_stop_expected_stop_loss"] == EXPECTED_STOP_LOSS
        assert p["post_stop_expected_trigger_by"] == EXPECTED_SL_TRIGGER_BY
        assert p["existing_positions_unchanged_required"] is True
        assert p["verification_plan_only"] is True
        assert p["real_readonly_after_execution_not_performed"] is True

    def test_gates_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_PRE_STOP_READONLY_REQUIRED,
                  GATE_POST_STOP_READONLY_REQUIRED,
                  GATE_PRE_STOP_SELECTED_SYMBOL_PRESENT,
                  GATE_PRE_STOP_EXPECTED_SYMBOL,
                  GATE_PRE_STOP_EXPECTED_QTY,
                  GATE_PRE_STOP_EXPECTED_SIDE_LONG,
                  GATE_POST_STOP_EXPECTED_STOP_LOSS,
                  GATE_POST_STOP_EXPECTED_TRIGGER_BY,
                  GATE_EXISTING_POSITIONS_UNCHANGED_REQUIRED,
                  GATE_VERIFICATION_PLAN_ONLY,
                  GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED):
            assert g in blocked


# ===========================================================================
# AF32: failure policy
# ===========================================================================

class TestAF32FailurePolicy:
    def test_fail_closed_paths(self):
        r = _run()
        f = r.stop_failure_policy
        assert f["request_rejected"] == "FAIL_CLOSED"
        assert f["selected_symbol_absent"] == "FAIL_CLOSED"
        assert f["selected_symbol_side_mismatch"] == "FAIL_CLOSED"
        assert f["selected_symbol_qty_mismatch"] == "FAIL_CLOSED"
        assert f["stop_loss_invalid"] == "FAIL_CLOSED"
        assert f["existing_protected_mismatch"] == "MANUAL_REVIEW_REQUIRED"
        assert f["readonly_unavailable"] == "FAIL_CLOSED"
        assert f["live_endpoint_detected"] == "FAIL_CLOSED"
        assert f["secret_emission_detected"] == "FAIL_CLOSED"

    def test_no_automatic(self):
        r = _run()
        f = r.stop_failure_policy
        assert f["no_auto_retry"] is True
        assert f["no_auto_cleanup"] is True
        assert f["no_auto_emergency_close"] is True
        assert f["no_auto_entry"] is True
        assert f["no_auto_next_step"] is True
        assert f["manual_intervention_only"] is True

    def test_gates_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_REQUEST_REJECTED_FAIL_CLOSED,
                  GATE_SELECTED_SYMBOL_ABSENT_FAIL_CLOSED,
                  GATE_SELECTED_SYMBOL_SIDE_MISMATCH_FAIL_CLOSED,
                  GATE_SELECTED_SYMBOL_QTY_MISMATCH_FAIL_CLOSED,
                  GATE_STOP_LOSS_INVALID_FAIL_CLOSED,
                  GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW,
                  GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
                  GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED,
                  GATE_SECRET_EMISSION_FAIL_CLOSED,
                  GATE_NO_AUTO_RETRY, GATE_NO_AUTO_CLEANUP,
                  GATE_NO_AUTO_EMERGENCY_CLOSE,
                  GATE_NO_AUTO_ENTRY,
                  GATE_NO_AUTO_NEXT_STEP):
            assert g in blocked


# ===========================================================================
# AF33: audit artifacts (dry-run not sent, sanitized, no secrets)
# ===========================================================================

class TestAF33AuditArtifacts:
    def test_audit_flags(self):
        r = _run()
        a = r.audit_artifacts
        assert a["response_status"] == DRY_RUN_NOT_SENT_MARKER == "DRY_RUN_NOT_SENT"
        assert a["response_from_exchange"] is False
        assert a["sanitized"] is True
        assert a["no_secrets"] is True
        assert a["forbidden_log_fields"] == list(FORBIDDEN_LOG_FIELDS)

    def test_audit_sub_artifacts_present(self):
        r = _run()
        a = r.audit_artifacts
        assert "precondition_contract" in a
        assert "manual_confirmation_contract" in a
        assert "stop_request_envelope" in a
        assert "readonly_verification_plan" in a
        assert "failure_policy" in a
        assert "final_stop_adapter_verdict" in a

    def test_gates_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_AUDIT_ARTIFACTS_PRESENT,
                  GATE_AUDIT_RESPONSE_DRY_RUN_NOT_SENT,
                  GATE_AUDIT_RESPONSE_FROM_EXCHANGE_FALSE,
                  GATE_AUDIT_SANITIZED, GATE_AUDIT_NO_SECRETS):
            assert g in blocked


# ===========================================================================
# AF34: final stop adapter verdict
# ===========================================================================

class TestAF34FinalStopAdapterVerdict:
    def test_default(self):
        r = _run()
        v = r.final_stop_adapter_verdict
        assert v["stop_dry_run_approval_allowed"] is False
        assert v["real_stop_execution_requested"] is False
        assert v["real_execution_allowed"] is False
        assert v["real_stop_attach_implemented"] is False
        assert v["guarded_stop_attach_dry_run_adapter"] is True
        assert v["stop_attach_only"] is True
        assert v["entry_included"] is False
        assert v["cleanup_included"] is False
        assert v["full_lifecycle_included"] is False
        assert v["current_task_real_execution_allowed"] is False
        assert v["readiness_conclusion"] == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert v["g20_policy_still_in_place"] is True
        assert v["g20_lifted"] is False
        assert v["no_real_order_endpoint"] is True
        assert v["no_real_stop_endpoint"] is True
        assert v["no_position_modified"] is True
        assert v["no_live_endpoint"] is True
        assert v["no_secrets_loaded"] is True
        assert v["no_secrets_emitted"] is True
        assert v["order_endpoint_called"] is False
        assert v["stop_endpoint_called"] is False
        assert v["status"] == STATUS_ADAPTER_READY
        assert v["mode"] == MODE_STOP_ADAPTER_CHECKLIST
        assert v["next_required_task"] == "TASK-014AG_guarded_cleanup_only_dry_run_adapter"

    def test_approval(self):
        r = _run(allow_stop_dry_run_approval=True)
        v = r.final_stop_adapter_verdict
        assert v["status"] == STATUS_ADAPTER_READY_EXEC_DISABLED
        assert v["mode"] == MODE_STOP_DRY_RUN_APPROVAL

    def test_guard(self):
        r = _run(allow_real_stop_execution=True)
        v = r.final_stop_adapter_verdict
        assert v["status"] == STATUS_REAL_STOP_NOT_IMPL
        assert v["mode"] == MODE_REAL_STOP_EXECUTION_GUARD
        assert v["real_stop_execution_requested"] is True
        assert v["real_execution_allowed"] is False


# ===========================================================================
# AF35: g20 still in place (not lifted)
# ===========================================================================

class TestAF35G20NotLifted:
    def test_g20_invariants(self):
        for kw in ({}, {"allow_stop_dry_run_approval": True},
                   {"allow_real_stop_execution": True}):
            r = _run(**kw)
            assert r.g20_policy_still_in_place is True
            assert r.g20_lifted is False
            assert GATE_G20_NOT_LIFTED in r.blocked_gates
            assert GATE_G20_POLICY_STILL_IN_PLACE in r.blocked_gates
            assert GATE_NO_G20_LIFT in r.blocked_gates


# ===========================================================================
# AF36: socket-disabled import smoke
# ===========================================================================

class TestAF36SocketDisabledImport:
    def test_module_safe_under_socket_disabled(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"]       = str(ROOT)
        cp = subprocess.run(
            [sys.executable, "-c",
             "import socket; socket.socket = None; "
             "import src.demo_tiny_guarded_stop_attach_dry_run_adapter as m; "
             "print('OK', m.STATUS_ADAPTER_READY)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=60,
        )
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout


# ===========================================================================
# AF37: dataclass roundtrip with deep-copy
# ===========================================================================

class TestAF37DataclassRoundTrip:
    def test_to_dict_roundtrip(self):
        r = _run(allow_stop_dry_run_approval=True)
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
            ("real_stop_attach_implemented",        False),
            ("guarded_stop_attach_dry_run_adapter", True),
            ("stop_attach_only",                    True),
            ("entry_included",                      False),
            ("cleanup_included",                    False),
            ("full_lifecycle_included",             False),
            ("real_execution_allowed",              False),
            ("stop_dry_run_approval_allowed",       True),
        ):
            assert d[key] is expected, f"{key} should be {expected}"
        assert d["status"] == STATUS_ADAPTER_READY_EXEC_DISABLED
        assert d["readiness_conclusion"] == READINESS_CONCLUSION_NOT_EXECUTABLE
        # Deep-copy: mutating returned dict must not affect source.
        d["stages"][STAGE_2_STOP_PRECONDITION_CONTRACT]["mutated"] = True
        assert "mutated" not in r.stages[STAGE_2_STOP_PRECONDITION_CONTRACT]
        d["stop_adapter_scope"]["mutated"] = True
        assert "mutated" not in r.stop_adapter_scope
        d["stop_precondition_contract"]["mutated"] = True
        assert "mutated" not in r.stop_precondition_contract
        d["stop_request_envelope"]["mutated"] = True
        assert "mutated" not in r.stop_request_envelope


# ===========================================================================
# AF38: path refs
# ===========================================================================

class TestAF38PathRefs:
    def test_path_refs(self):
        r = _run()
        assert r.order_create_path_ref == ORDER_CREATE_PATH_REF
        assert r.trading_stop_path_ref == TRADING_STOP_PATH_REF
        assert r.base_url_ref          == BASE_URL_DEMO_REF
        assert r.base_url_ref != BASE_URL_LIVE_REF


# ===========================================================================
# AF39: safety invariants on dataclass (default / approval / guard)
# ===========================================================================

class TestAF39SafetyInvariants:
    def test_default(self):
        r = _run()
        assert r.send_allowed is False
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

    def test_approval(self):
        r = _run(allow_stop_dry_run_approval=True)
        assert r.send_allowed is False
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_secrets_loaded is True

    def test_guard(self):
        r = _run(allow_real_stop_execution=True)
        assert r.send_allowed is False
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.real_execution_allowed is False
        assert r.real_stop_attach_implemented is False


# ===========================================================================
# AF40: gate count >= 111
# ===========================================================================

class TestAF40GateCount:
    def test_at_least_111(self):
        import src.demo_tiny_guarded_stop_attach_dry_run_adapter as m
        gate_names = [
            n for n in dir(m)
            if n.startswith("GATE_") and isinstance(getattr(m, n), str)
        ]
        assert len(gate_names) >= 111, (
            f"Expected >= 111 GATE_ constants, got {len(gate_names)}: "
            f"{sorted(gate_names)}"
        )


# ===========================================================================
# AF41: always-on gates surface in every checklist
# ===========================================================================

class TestAF41AlwaysOnGates:
    def test_always_on_present(self):
        r = _run()
        unique = set(r.blocked_gates)
        for g in (
            # scope
            GATE_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_ONLY, GATE_STOP_ATTACH_ONLY,
            GATE_ENTRY_NOT_INCLUDED, GATE_CLEANUP_NOT_INCLUDED,
            GATE_FULL_LIFECYCLE_NOT_INCLUDED,
            GATE_REAL_STOP_ATTACH_NOT_IMPLEMENTED,
            GATE_REAL_EXECUTION_NOT_ALLOWED,
            GATE_NO_ENDPOINT_INVOKED, GATE_NO_POSITION_MODIFIED_SCOPE,
            GATE_NO_SECRETS_LOADED, GATE_NO_G20_LIFT,
            # precondition
            GATE_PRECONDITION_SYMBOL_MATCHES,
            GATE_PRECONDITION_EXPECTED_ENTRY_SYMBOL,
            GATE_PRECONDITION_SIDE_LONG,
            GATE_PRECONDITION_QTY_TINY,
            GATE_PRECONDITION_ENTRY_REFERENCE_VALID,
            GATE_PRECONDITION_STOP_LOSS_VALUE,
            GATE_PRECONDITION_STOP_LOSS_BELOW_ENTRY,
            GATE_PRECONDITION_STOP_LOSS_TICK_ALIGNED,
            GATE_PRECONDITION_TPSL_MODE_FULL,
            GATE_PRECONDITION_SL_TRIGGER_BY_MARK_PRICE,
            GATE_PRECONDITION_POSITION_IDX_ZERO,
            GATE_PRECONDITION_CATEGORY_LINEAR,
            GATE_PRECONDITION_SELECTED_SYMBOL_PRESENT,
            GATE_PRECONDITION_EXPECTED_PROTECTED_LIST,
            GATE_PRECONDITION_PROOF_STRENGTH_STRONG,
            GATE_PRECONDITION_ACCOUNT_MODE_DEMO,
            GATE_PRECONDITION_ENDPOINT_FAMILY_BYBIT_DEMO,
            # manual confirmation
            GATE_STOP_TOKEN_PATTERN_PRESENT, GATE_TOKEN_NOT_VALIDATED,
            GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
            GATE_SECOND_CONFIRMATION_DOCUMENTED,
            GATE_MAX_NOTIONAL_FLAG_DOCUMENTED,
            GATE_EXPECTED_COUNT_FLAG_DOCUMENTED,
            GATE_EXPECTED_SYMBOLS_FLAG_DOCUMENTED,
            GATE_EXPECTED_ENTRY_SYMBOL_FLAG_DOCUMENTED,
            GATE_EXPECTED_ENTRY_QTY_FLAG_DOCUMENTED,
            GATE_EXPECTED_STOP_LOSS_FLAG_DOCUMENTED,
            GATE_CONFIRMATION_FLAGS_NOT_VALIDATED,
            # envelope
            GATE_STOP_ENVELOPE_PRESENT, GATE_ENVELOPE_PREVIEW_ONLY,
            GATE_ENVELOPE_SEND_NOT_ALLOWED,
            GATE_ENVELOPE_ENDPOINT_NOT_CALLED,
            GATE_ENVELOPE_NOT_REAL_PAYLOAD,
            GATE_ENVELOPE_NO_SIGNATURE,
            GATE_ENVELOPE_NO_PRIVATE_HEADERS,
            GATE_ENVELOPE_TRADING_STOP_PATH,
            GATE_ENVELOPE_BASE_URL_DEMO_ONLY,
            GATE_ENVELOPE_STOP_LOSS_VALUE,
            GATE_ENVELOPE_TPSL_MODE_FULL,
            GATE_ENVELOPE_SL_TRIGGER_BY_MARK_PRICE,
            GATE_NO_SENDER_ADAPTER,
            # readonly plan
            GATE_PRE_STOP_READONLY_REQUIRED,
            GATE_POST_STOP_READONLY_REQUIRED,
            GATE_PRE_STOP_SELECTED_SYMBOL_PRESENT,
            GATE_PRE_STOP_EXPECTED_SYMBOL,
            GATE_PRE_STOP_EXPECTED_QTY,
            GATE_PRE_STOP_EXPECTED_SIDE_LONG,
            GATE_POST_STOP_EXPECTED_STOP_LOSS,
            GATE_POST_STOP_EXPECTED_TRIGGER_BY,
            GATE_EXISTING_POSITIONS_UNCHANGED_REQUIRED,
            GATE_VERIFICATION_PLAN_ONLY,
            GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED,
            # failure policy
            GATE_REQUEST_REJECTED_FAIL_CLOSED,
            GATE_SELECTED_SYMBOL_ABSENT_FAIL_CLOSED,
            GATE_SELECTED_SYMBOL_SIDE_MISMATCH_FAIL_CLOSED,
            GATE_SELECTED_SYMBOL_QTY_MISMATCH_FAIL_CLOSED,
            GATE_STOP_LOSS_INVALID_FAIL_CLOSED,
            GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW,
            GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
            GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED,
            GATE_SECRET_EMISSION_FAIL_CLOSED,
            GATE_NO_AUTO_RETRY, GATE_NO_AUTO_CLEANUP,
            GATE_NO_AUTO_EMERGENCY_CLOSE,
            GATE_NO_AUTO_ENTRY,
            GATE_NO_AUTO_NEXT_STEP,
            # audit
            GATE_AUDIT_ARTIFACTS_PRESENT,
            GATE_AUDIT_RESPONSE_DRY_RUN_NOT_SENT,
            GATE_AUDIT_RESPONSE_FROM_EXCHANGE_FALSE,
            GATE_AUDIT_SANITIZED, GATE_AUDIT_NO_SECRETS,
            # execution guard
            GATE_REAL_STOP_ATTACH_EXECUTION_NOT_IMPL,
            GATE_NO_REAL_ORDER_ENDPOINT, GATE_NO_REAL_STOP_ENDPOINT,
            GATE_NO_POSITION_MODIFIED, GATE_G20_NOT_LIFTED,
            GATE_G20_POLICY_STILL_IN_PLACE, GATE_NO_LIVE_ENDPOINT,
            GATE_NO_SECRETS_EMITTED,
        ):
            assert g in unique, f"always-on gate missing: {g}"


# ===========================================================================
# AF42: no forbidden imports
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
    "src.demo_tiny_lifecycle_runner_dry_run",
    "src.demo_tiny_lifecycle_guarded_runner_design_review",
    "src.demo_tiny_guarded_entry_dry_run_adapter",
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


class TestAF42NoForbiddenImports:
    def test_module(self):
        imp = _collect_imports(_MODULE_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in module"

    def test_cli(self):
        imp = _collect_imports(_SCRIPT_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in CLI"


# ===========================================================================
# AF43: no sender / AE module reuse
# ===========================================================================

class TestAF43NoSenderOrAEReuse:
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

    def test_no_ae_module_reuse(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTinyGuardedEntryDryRunAdapter" not in code

    def test_no_ad_module_reuse(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTinyLifecycleGuardedRunnerDesignReview" not in code

    def test_no_runner_dry_run_module_reuse(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTinyLifecycleRunnerDryRun" not in code


# ===========================================================================
# AF44: no network tokens in code
# ===========================================================================

class TestAF44NoNetworkTokens:
    def test_no_net_tokens(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            for tok in ("urllib", "urlopen", "httpx",
                        "requests.", "http.client", "socket.",
                        "session.post", "session.get"):
                assert tok not in code, (
                    f"Network token {tok!r} present in {path.name}"
                )


# ===========================================================================
# AF45: no env/signing in module
# ===========================================================================

class TestAF45NoEnvOrSigning:
    def test_module(self):
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
# AF46: forbidden flags absent
# ===========================================================================

class TestAF46NoForbiddenFlags:
    @pytest.mark.parametrize("flag", [
        "--execute-real-lifecycle",
        "--execute-real-entry",
        "--execute-real-stop",
        "--execute-real-stop-attach",
        "--execute-real-cleanup",
        "--execute-real-runner",
        "--send-order",
        "--place-order",
        "--real-run",
    ])
    def test_flag_absent_in_module(self, flag):
        code = _read_code_only(_MODULE_PATH)
        assert flag not in code

    @pytest.mark.parametrize("flag", [
        "--execute-real-lifecycle",
        "--execute-real-entry",
        "--execute-real-stop",
        "--execute-real-stop-attach",
        "--execute-real-cleanup",
        "--execute-real-runner",
        "--send-order",
        "--place-order",
        "--real-run",
    ])
    def test_flag_absent_in_cli(self, flag):
        code = _read_code_only(_SCRIPT_PATH)
        assert flag not in code

    def test_flag_token_absent_in_module(self):
        code = _read_code_only(_MODULE_PATH)
        for ident in ("execute_real_lifecycle", "execute_real_entry",
                      "execute_real_stop", "execute_real_stop_attach",
                      "execute_real_cleanup",
                      "execute_real_runner", "send_order", "place_order"):
            assert ident not in code

    def test_flag_token_absent_in_cli(self):
        code = _read_code_only(_SCRIPT_PATH)
        for ident in ("execute_real_lifecycle", "execute_real_entry",
                      "execute_real_stop", "execute_real_stop_attach",
                      "execute_real_cleanup",
                      "execute_real_runner", "send_order", "place_order"):
            assert ident not in code


# ===========================================================================
# AF47: stop token pattern structure
# ===========================================================================

class TestAF47StopTokenPattern:
    def test_token_structure(self):
        assert STOP_TOKEN_PATTERN.startswith("CONFIRM_DEMO_TINY_STOP_ATTACH_")
        assert "YYYYMMDD" in STOP_TOKEN_PATTERN
        assert "SYMBOL" in STOP_TOKEN_PATTERN

    def test_token_surfaced(self):
        r = _run()
        assert r.stop_token_pattern == STOP_TOKEN_PATTERN


# ===========================================================================
# AF48: stage_0 artifact preflight reports all 13 upstream artifacts present
# ===========================================================================

class TestAF48Stage0PreflightAllPresent:
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
        assert env["tiny_stop_attach_permission_gate_present"] is True
        assert env["lifecycle_summary_present"]                is True
        assert env["runner_design_present"]                    is True
        assert env["runner_dry_run_present"]                   is True
        assert env["guarded_design_review_present"]            is True
        assert env["guarded_entry_adapter_present"]            is True
        assert env["current_task_real_execution_allowed"]      is False

    def test_guarded_design_review_acceptable_list_surfaced(self):
        r = _run()
        env = r.stages[STAGE_0_ARTIFACT_PREFLIGHT]
        assert env["guarded_design_review_status_acceptable"] == sorted(
            ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES
        )
        assert env["guarded_design_review_readiness_expected"] == (
            READINESS_CONCLUSION_NOT_EXECUTABLE
        )

    def test_guarded_entry_adapter_acceptable_list_surfaced(self):
        r = _run()
        env = r.stages[STAGE_0_ARTIFACT_PREFLIGHT]
        assert env["guarded_entry_adapter_status_acceptable"] == sorted(
            ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES
        )


# ===========================================================================
# AF49-AF51: CLI / report helpers + tests
# ===========================================================================

class _ReportSetupMixin:
    def _setup(self, base: Path):
        ro_d   = base / "readonly";     ro_d.mkdir()
        rec_d  = base / "recon";        rec_d.mkdir()
        prot_d = base / "protection";   prot_d.mkdir()
        con_d  = base / "contract";     con_d.mkdir()
        noop_d = base / "noop";         noop_d.mkdir()
        lc_d   = base / "lifecycle";    lc_d.mkdir()
        rp_d   = base / "real_perm";    rp_d.mkdir()
        sp_d   = base / "stop_perm";    sp_d.mkdir()
        sum_d  = base / "summary";      sum_d.mkdir()
        des_d  = base / "design";       des_d.mkdir()
        dry_d  = base / "dry_run";      dry_d.mkdir()
        grv_d  = base / "guarded_rev";  grv_d.mkdir()
        gea_d  = base / "entry_adapter"; gea_d.mkdir()
        out_d  = base / "out"
        (ro_d   / "latest_smoke.json").write_text(json.dumps(_valid_readonly()), encoding="utf-8")
        (rec_d  / "latest_reconciliation.json").write_text(json.dumps(_valid_reconciliation()), encoding="utf-8")
        (prot_d / "latest_new_entry_protection.json").write_text(json.dumps(_valid_protection()), encoding="utf-8")
        (con_d  / "latest_trading_stop_contract.json").write_text(json.dumps(_valid_contract()), encoding="utf-8")
        (noop_d / "latest_trading_stop_noop_probe_plan.json").write_text(json.dumps(_valid_noop_plan()), encoding="utf-8")
        (lc_d   / "latest_tiny_position_lifecycle_mock.json").write_text(json.dumps(_valid_lifecycle()), encoding="utf-8")
        (rp_d   / "latest_tiny_position_real_permission_gate.json").write_text(json.dumps(_valid_real_permission_gate()), encoding="utf-8")
        (sp_d   / "latest_tiny_stop_attach_permission_gate.json").write_text(json.dumps(_valid_tiny_stop_permission_gate()), encoding="utf-8")
        (sum_d  / "latest_tiny_lifecycle_real_execution_summary.json").write_text(json.dumps(_valid_lifecycle_summary()), encoding="utf-8")
        (des_d  / "latest_tiny_lifecycle_runner_design.json").write_text(json.dumps(_valid_runner_design()), encoding="utf-8")
        (dry_d  / "latest_tiny_lifecycle_runner_dry_run.json").write_text(json.dumps(_valid_runner_dry_run()), encoding="utf-8")
        (grv_d  / "latest_tiny_lifecycle_guarded_runner_design_review.json").write_text(json.dumps(_valid_guarded_design_review()), encoding="utf-8")
        (gea_d  / "latest_tiny_guarded_entry_dry_run_adapter.json").write_text(json.dumps(_valid_guarded_entry_adapter()), encoding="utf-8")
        return (ro_d, rec_d, prot_d, con_d, noop_d, lc_d,
                rp_d, sp_d, sum_d, des_d, dry_d, grv_d, gea_d, out_d)


class TestAF49ReportChecklist(_ReportSetupMixin):
    def test_writes_report(self):
        from scripts.preview_demo_tiny_guarded_stop_attach_dry_run_adapter import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, sp_d,
             sum_d, des_d, dry_d, grv_d, gea_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_stop_dry_run_approval=False,
                allow_real_stop_execution=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_stop_dir=sp_d,
                lifecycle_summary_dir=sum_d,
                runner_design_dir=des_d,
                runner_dry_run_dir=dry_d,
                guarded_design_review_dir=grv_d,
                guarded_entry_adapter_dir=gea_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            files = sorted(p.name for p in out_d.iterdir())
            assert "latest_tiny_guarded_stop_attach_dry_run_adapter.json" in files
            assert "latest_tiny_guarded_stop_attach_dry_run_adapter.md"   in files
            data = json.loads(
                (out_d / "latest_tiny_guarded_stop_attach_dry_run_adapter.json").read_text(encoding="utf-8")
            )
            assert data["status"] == STATUS_ADAPTER_READY
            assert data["real_execution_allowed"] is False
            assert data["real_stop_attach_implemented"] is False
            assert data["guarded_stop_attach_dry_run_adapter"] is True
            assert data["stop_attach_only"] is True
            assert data["entry_included"] is False
            assert data["cleanup_included"] is False
            assert data["order_endpoint_called"] is False
            assert data["stop_endpoint_called"] is False
            assert data["no_position_modified"] is True
            assert data["readiness_conclusion"] == READINESS_CONCLUSION_NOT_EXECUTABLE
            assert data["required_confirmation_flags"] == list(REQUIRED_CONFIRMATION_FLAGS)
            assert data["next_required_task"] == (
                "TASK-014AG_guarded_cleanup_only_dry_run_adapter"
            )


class TestAF50NoSecretsInReport(_ReportSetupMixin):
    def test_no_secrets(self):
        from scripts.preview_demo_tiny_guarded_stop_attach_dry_run_adapter import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, sp_d,
             sum_d, des_d, dry_d, grv_d, gea_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_stop_dry_run_approval=False,
                allow_real_stop_execution=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_stop_dir=sp_d,
                lifecycle_summary_dir=sum_d,
                runner_design_dir=des_d,
                runner_dry_run_dir=dry_d,
                guarded_design_review_dir=grv_d,
                guarded_entry_adapter_dir=gea_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            md = (out_d / "latest_tiny_guarded_stop_attach_dry_run_adapter.md").read_text(encoding="utf-8")
            for forbidden in ("API_KEY", "API_SECRET", "BYBIT_API", "X-BAPI-SIGN"):
                assert forbidden not in md
            data = json.loads(
                (out_d / "latest_tiny_guarded_stop_attach_dry_run_adapter.json").read_text(encoding="utf-8")
            )
            assert data["secret_value_observed"] is False
            assert data["no_secrets_loaded"] is True


class TestAF51CLIExitCodes(_ReportSetupMixin):
    def test_run_execute_exits_0(self):
        from scripts.preview_demo_tiny_guarded_stop_attach_dry_run_adapter import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, sp_d,
             sum_d, des_d, dry_d, grv_d, gea_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_stop_dry_run_approval=False,
                allow_real_stop_execution=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_stop_dir=sp_d,
                lifecycle_summary_dir=sum_d,
                runner_design_dir=des_d,
                runner_dry_run_dir=dry_d,
                guarded_design_review_dir=grv_d,
                guarded_entry_adapter_dir=gea_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0

    def test_run_execute_missing_exits_1(self):
        from scripts.preview_demo_tiny_guarded_stop_attach_dry_run_adapter import run_execute
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for sub in ("readonly", "recon", "protection", "contract", "noop",
                        "lifecycle", "real_perm", "stop_perm",
                        "summary", "design", "dry_run", "guarded_rev", "entry_adapter"):
                (base / sub).mkdir()
            rc = run_execute(
                symbol="SOLUSDT",
                allow_stop_dry_run_approval=False,
                allow_real_stop_execution=False,
                write_report=False,
                readonly_dir=base / "readonly",
                reconciliation_dir=base / "recon",
                protection_dir=base / "protection",
                contract_dir=base / "contract",
                noop_plan_dir=base / "noop",
                lifecycle_dir=base / "lifecycle",
                real_permission_dir=base / "real_perm",
                tiny_stop_dir=base / "stop_perm",
                lifecycle_summary_dir=base / "summary",
                runner_design_dir=base / "design",
                runner_dry_run_dir=base / "dry_run",
                guarded_design_review_dir=base / "guarded_rev",
                guarded_entry_adapter_dir=base / "entry_adapter",
                output_dir=base / "out", _now=_TEST_NOW,
            )
            assert rc == 1


# ===========================================================================
# AF52: next_required_task points at TASK-014AG
# ===========================================================================

class TestAF52NextTaskIs014AG:
    def test_next_required_task(self):
        r = _run()
        assert r.next_required_task == "TASK-014AG_guarded_cleanup_only_dry_run_adapter"

    def test_next_required_task_under_approval(self):
        r = _run(allow_stop_dry_run_approval=True)
        assert r.next_required_task == "TASK-014AG_guarded_cleanup_only_dry_run_adapter"

    def test_next_required_task_under_guard(self):
        r = _run(allow_real_stop_execution=True)
        assert r.next_required_task == "TASK-014AG_guarded_cleanup_only_dry_run_adapter"


# ===========================================================================
# AF53: upstream status echoes
# ===========================================================================

class TestAF53UpstreamStatusEchoes:
    def test_summary_echo(self):
        r = _run()
        assert r.upstream_lifecycle_summary_status == "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY"

    def test_runner_design_echo(self):
        r = _run()
        assert r.upstream_runner_design_status == "TINY_LIFECYCLE_RUNNER_DESIGN_READY"

    def test_runner_dry_run_echo(self):
        r = _run()
        assert r.upstream_runner_dry_run_status == "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY"

    def test_guarded_design_review_status_echo(self):
        r = _run()
        assert r.upstream_guarded_design_review_status == (
            "TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY"
        )

    def test_guarded_design_review_readiness_echo(self):
        r = _run()
        assert r.upstream_guarded_design_review_readiness_conclusion == (
            READINESS_CONCLUSION_NOT_EXECUTABLE
        )

    def test_guarded_entry_adapter_status_echo(self):
        r = _run()
        assert r.upstream_guarded_entry_adapter_status == (
            "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY"
        )


# ===========================================================================
# AF54: status precedence (hard-fail beats approval/guard; guard beats approval)
# ===========================================================================

class TestAF54StatusPrecedence:
    def test_hard_fail_beats_approval(self):
        r = _run(readonly=None, allow_stop_dry_run_approval=True)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED

    def test_hard_fail_beats_execution_guard(self):
        r = _run(guarded_entry_adapter=None, allow_real_stop_execution=True)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED

    def test_guard_beats_approval(self):
        r = _run(allow_stop_dry_run_approval=True,
                 allow_real_stop_execution=True)
        assert r.status == STATUS_REAL_STOP_NOT_IMPL
        assert r.mode == MODE_REAL_STOP_EXECUTION_GUARD


# ===========================================================================
# AF55: acceptable status whitelists
# ===========================================================================

class TestAF55AcceptableWhitelists:
    def test_summary_three(self):
        assert len(ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES) == 3

    def test_runner_design_three(self):
        assert len(ACCEPTABLE_RUNNER_DESIGN_STATUSES) == 3

    def test_runner_dry_run_three(self):
        assert len(ACCEPTABLE_RUNNER_DRY_RUN_STATUSES) == 3

    def test_guarded_design_review_three(self):
        assert len(ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES) == 3
        assert "TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY" in (
            ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES
        )

    def test_guarded_entry_adapter_three(self):
        assert len(ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES) == 3
        assert "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY" in (
            ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES
        )


# ===========================================================================
# AF56: existing 5 positions never touched even with all flags set
# ===========================================================================

class TestAF56ExistingPositionsNotTouched:
    def test_default(self):
        r = _run()
        assert r.existing_positions_touched == []
        assert set(r.existing_position_symbols) == set(EXISTING_POSITION_SYMBOLS)

    def test_with_approval(self):
        r = _run(allow_stop_dry_run_approval=True)
        assert r.existing_positions_touched == []

    def test_with_real_execution_guard(self):
        r = _run(allow_real_stop_execution=True)
        assert r.existing_positions_touched == []


# ===========================================================================
# AF57: blocked_gates deduplicated
# ===========================================================================

class TestAF57BlockedGatesDeduped:
    def test_no_duplicates(self):
        r = _run()
        assert len(r.blocked_gates) == len(set(r.blocked_gates))


# ===========================================================================
# AF58: 7 required confirmation flags (exact values)
# ===========================================================================

class TestAF58RequiredConfirmationFlags:
    def test_seven_flags(self):
        assert len(REQUIRED_CONFIRMATION_FLAGS) == 7

    def test_specific_flags(self):
        assert "--i-understand-this-is-demo-real-execution" in REQUIRED_CONFIRMATION_FLAGS
        assert any("--max-notional-usdt" in f for f in REQUIRED_CONFIRMATION_FLAGS)
        assert any("--expected-existing-position-count" in f for f in REQUIRED_CONFIRMATION_FLAGS)
        assert any("--expected-existing-symbols" in f for f in REQUIRED_CONFIRMATION_FLAGS)
        assert any("--expected-entry-symbol" in f for f in REQUIRED_CONFIRMATION_FLAGS)
        assert any("--expected-entry-qty" in f for f in REQUIRED_CONFIRMATION_FLAGS)
        assert any("--expected-stop-loss" in f for f in REQUIRED_CONFIRMATION_FLAGS)

    def test_max_notional_value(self):
        assert "--max-notional-usdt 10" in REQUIRED_CONFIRMATION_FLAGS

    def test_expected_position_count(self):
        assert "--expected-existing-position-count 5" in REQUIRED_CONFIRMATION_FLAGS

    def test_expected_entry_symbol(self):
        assert "--expected-entry-symbol SOLUSDT" in REQUIRED_CONFIRMATION_FLAGS

    def test_expected_entry_qty(self):
        assert "--expected-entry-qty 0.1" in REQUIRED_CONFIRMATION_FLAGS

    def test_expected_stop_loss(self):
        assert "--expected-stop-loss 61.18" in REQUIRED_CONFIRMATION_FLAGS


# ===========================================================================
# AF59: demo endpoint allowlist + live denylist
# ===========================================================================

class TestAF59EndpointAllowlistDenylist:
    def test_constants(self):
        assert DEMO_ENDPOINT_ALLOWLIST == ("https://api-demo.bybit.com",)
        assert BASE_URL_DEMO_REF == "https://api-demo.bybit.com"
        assert BASE_URL_LIVE_REF == "https://api.bybit.com"

    def test_envelope_surfaced(self):
        r = _run()
        e = r.stop_request_envelope
        assert "https://api-demo.bybit.com" in e["demo_endpoint_allowlist"]
        assert "https://api.bybit.com" in e["live_endpoint_denylist"]


# ===========================================================================
# AF60: real_execution_allowed always False regardless of any flag combo
# ===========================================================================

class TestAF60RealExecutionAllowedAlwaysFalse:
    @pytest.mark.parametrize("approval,guard", [
        (False, False), (True, False), (False, True), (True, True),
    ])
    def test_always_false(self, approval, guard):
        r = _run(allow_stop_dry_run_approval=approval,
                 allow_real_stop_execution=guard)
        assert r.real_execution_allowed is False
        assert r.real_stop_attach_implemented is False
        assert r.current_task_real_execution_allowed is False


# ===========================================================================
# AF61: hard-fail set has at least 21 gates
# ===========================================================================

class TestAF61HardFailGatesCount:
    def test_at_least_twenty_one(self):
        from src.demo_tiny_guarded_stop_attach_dry_run_adapter import (
            _HARD_FAIL_GATES,
        )
        assert len(_HARD_FAIL_GATES) >= 21


# ===========================================================================
# AF62: stage_order == ALL_STAGES (9 stages in order)
# ===========================================================================

class TestAF62StageOrder:
    def test_order(self):
        r = _run()
        assert r.stage_order == [
            STAGE_0_ARTIFACT_PREFLIGHT, STAGE_1_STOP_ADAPTER_SCOPE,
            STAGE_2_STOP_PRECONDITION_CONTRACT,
            STAGE_3_MANUAL_CONFIRMATION_DRY_RUN_CONTRACT,
            STAGE_4_STOP_REQUEST_ENVELOPE_DRY_RUN,
            STAGE_5_STOP_READONLY_VERIFICATION_PLAN,
            STAGE_6_STOP_FAILURE_POLICY,
            STAGE_7_AUDIT_ARTIFACT_GENERATION,
            STAGE_8_FINAL_STOP_ADAPTER_VERDICT,
        ]
        assert len(r.stage_order) == 9


# ===========================================================================
# AF63: 13-artifact preflight contract - all 13 must be present
# ===========================================================================

class TestAF6313ArtifactPreflightContract:
    @pytest.mark.parametrize("kw", [
        {"readonly": None}, {"recon": None}, {"protection": None},
        {"contract": None}, {"noop_plan": None}, {"lifecycle": None},
        {"real_permission_gate": None},
        {"tiny_stop_attach_permission_gate": None},
        {"lifecycle_summary": None}, {"runner_design": None},
        {"runner_dry_run": None},
        {"guarded_design_review": None},
        {"guarded_entry_adapter": None},
    ])
    def test_each_missing_fails_closed(self, kw):
        r = _run(**kw)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert r.failed_stage == STAGE_0_ARTIFACT_PREFLIGHT


# ===========================================================================
# AF64: stage_8 final stop adapter verdict mirrors result.status / mode
# ===========================================================================

class TestAF64Stage8MirrorsResult:
    def test_status_match(self):
        r = _run()
        v = r.stages[STAGE_8_FINAL_STOP_ADAPTER_VERDICT]["final_stop_adapter_verdict"]
        assert v["status"] == r.status
        assert v["mode"] == r.mode

    def test_status_match_approval(self):
        r = _run(allow_stop_dry_run_approval=True)
        v = r.stages[STAGE_8_FINAL_STOP_ADAPTER_VERDICT]["final_stop_adapter_verdict"]
        assert v["status"] == r.status
        assert v["mode"] == r.mode

    def test_status_match_guard(self):
        r = _run(allow_real_stop_execution=True)
        v = r.stages[STAGE_8_FINAL_STOP_ADAPTER_VERDICT]["final_stop_adapter_verdict"]
        assert v["status"] == r.status
        assert v["mode"] == r.mode


# ===========================================================================
# AF65: live URL never surfaces in envelope allowlist;
#       readiness_conclusion never READY_TO_EXECUTE;
#       alternate guarded review and entry adapter statuses accepted.
# ===========================================================================

class TestAF65ReadinessAndAllowlistInvariants:
    def test_live_url_demo_only(self):
        r = _run()
        e = r.stop_request_envelope
        assert BASE_URL_LIVE_REF not in e["demo_endpoint_allowlist"]
        assert BASE_URL_LIVE_REF in e["live_endpoint_denylist"]

    def test_readiness_default(self):
        r = _run()
        assert r.readiness_conclusion == "DESIGN_REVIEW_READY_NOT_EXECUTABLE"
        assert r.readiness_conclusion != "READY_TO_EXECUTE"

    def test_readiness_with_approval(self):
        r = _run(allow_stop_dry_run_approval=True)
        assert r.readiness_conclusion == "DESIGN_REVIEW_READY_NOT_EXECUTABLE"

    def test_readiness_with_real_guard(self):
        r = _run(allow_real_stop_execution=True)
        assert r.readiness_conclusion == "DESIGN_REVIEW_READY_NOT_EXECUTABLE"

    def test_readiness_constant_never_executable(self):
        assert READINESS_CONCLUSION_NOT_EXECUTABLE == (
            "DESIGN_REVIEW_READY_NOT_EXECUTABLE"
        )
        assert "READY_TO_EXECUTE" not in READINESS_CONCLUSION_NOT_EXECUTABLE

    def test_guarded_review_execution_disabled_status_accepted(self):
        rev = _valid_guarded_design_review()
        rev["status"] = "TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY_BUT_EXECUTION_DISABLED"
        r = _run(guarded_design_review=rev)
        assert r.status == STATUS_ADAPTER_READY

    def test_guarded_entry_adapter_execution_disabled_status_accepted(self):
        ada = _valid_guarded_entry_adapter()
        ada["status"] = "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED"
        r = _run(guarded_entry_adapter=ada)
        assert r.status == STATUS_ADAPTER_READY

    def test_guarded_entry_adapter_not_impl_status_accepted(self):
        ada = _valid_guarded_entry_adapter()
        ada["status"] = "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED"
        r = _run(guarded_entry_adapter=ada)
        assert r.status == STATUS_ADAPTER_READY
