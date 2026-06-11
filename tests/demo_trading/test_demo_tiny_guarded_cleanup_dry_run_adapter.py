"""
tests/demo_trading/test_demo_tiny_guarded_cleanup_dry_run_adapter.py
TASK-014AG: Guarded Cleanup-only Dry-run Adapter tests (AG1 - AG68).

Covers cleanup_adapter_checklist / cleanup_dry_run_approval /
real_cleanup_execution_guard / fail_closed paths; all 9 stages; 117 gate
constants; 14-artifact preflight contract (10 baseline + AA lifecycle
summary + AB runner design + AC runner dry-run + AD guarded design
review + AE guarded entry adapter + AF guarded stop-attach adapter ---
minus the entry / stop permission gates plus the cleanup permission
gate, since this adapter is cleanup-only); AD readiness_conclusion ==
DESIGN_REVIEW_READY_NOT_EXECUTABLE required; AE adapter status
acceptable required; AF adapter status acceptable required; cleanup
precondition contract (SOLUSDT post-entry / long / qty 0.1 / cleanup
side Sell / reduceOnly True / closeOnTrigger False / orderType Market
/ positionIdx 0 / category linear); manual token contract
(CONFIRM_DEMO_TINY_CLEANUP_*) never validated; preview-only request
envelope with no signature / no private headers / order-create path
ref / demo base url; pre/post readonly verification plan; failure
policy (FAIL_CLOSED / MANUAL_REVIEW_REQUIRED); status precedence;
source-scan safety (no urlopen / no forbidden imports / no signing /
no os.environ / no AE/AF module reuse); report artifacts;
forbidden-flag absence (--execute-real-* / --send-order /
--place-order / --real-run); the invariant that TASK-014L sender G20
(protected_entry_policy_missing) still blocks --execute-new-entry and
is NOT lifted here; next_required_task points at TASK-014AH.
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

from src.demo_tiny_guarded_cleanup_dry_run_adapter import (
    ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES,
    ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES,
    ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES,
    ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES,
    ACCEPTABLE_RUNNER_DESIGN_STATUSES,
    ACCEPTABLE_RUNNER_DRY_RUN_STATUSES,
    ALL_STAGES,
    BASE_URL_DEMO_REF,
    BASE_URL_LIVE_REF,
    CLEANUP_TOKEN_PATTERN,
    DEFAULT_SELECTED_SYMBOL,
    DEMO_ENDPOINT_ALLOWLIST,
    DRYRUN_ORDER_LINK_ID_PREFIX,
    DRY_RUN_NOT_SENT_MARKER,
    DemoTinyGuardedCleanupDryRunAdapter,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_CLEANUP_ORDER_TYPE,
    EXPECTED_CLEANUP_SIDE,
    EXPECTED_CLOSE_ON_TRIGGER,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_EXISTING_POSITION_COUNT,
    EXPECTED_INSTRUMENT_CATEGORY,
    EXPECTED_MAX_NOTIONAL_USDT,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_POSITION_IDX,
    EXPECTED_PRE_CLEANUP_QTY,
    EXPECTED_PRE_CLEANUP_SIDE,
    EXPECTED_PRE_CLEANUP_SYMBOL,
    EXPECTED_PROOF_STRENGTH,
    EXPECTED_REDUCE_ONLY,
    FORBIDDEN_LOG_FIELDS,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_AUDIT_ARTIFACTS_PRESENT,
    GATE_AUDIT_NO_SECRETS,
    GATE_AUDIT_RESPONSE_DRY_RUN_NOT_SENT,
    GATE_AUDIT_RESPONSE_FROM_EXCHANGE_FALSE,
    GATE_AUDIT_SANITIZED,
    GATE_CLEANUP_ENVELOPE_PRESENT,
    GATE_CLEANUP_ONLY,
    GATE_CLEANUP_SIDE_INVALID_FAIL_CLOSED,
    GATE_CLEANUP_TOKEN_PATTERN_PRESENT,
    GATE_CONFIRMATION_FLAGS_NOT_VALIDATED,
    GATE_CONTRACT_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_NOT_INCLUDED,
    GATE_ENVELOPE_BASE_URL_DEMO_ONLY,
    GATE_ENVELOPE_CLOSE_ON_TRIGGER_FALSE,
    GATE_ENVELOPE_ENDPOINT_NOT_CALLED,
    GATE_ENVELOPE_NO_PRIVATE_HEADERS,
    GATE_ENVELOPE_NO_SIGNATURE,
    GATE_ENVELOPE_NOT_REAL_PAYLOAD,
    GATE_ENVELOPE_ORDER_CREATE_PATH,
    GATE_ENVELOPE_ORDER_TYPE_MARKET,
    GATE_ENVELOPE_PREVIEW_ONLY,
    GATE_ENVELOPE_QTY_TINY,
    GATE_ENVELOPE_REDUCE_ONLY_TRUE,
    GATE_ENVELOPE_SEND_NOT_ALLOWED,
    GATE_ENVELOPE_SIDE_SELL,
    GATE_EXISTING_POSITIONS_UNCHANGED_REQUIRED,
    GATE_EXPECTED_CLEANUP_QTY_FLAG_DOCUMENTED,
    GATE_EXPECTED_CLEANUP_SIDE_FLAG_DOCUMENTED,
    GATE_EXPECTED_CLEANUP_SYMBOL_FLAG_DOCUMENTED,
    GATE_EXPECTED_COUNT_FLAG_DOCUMENTED,
    GATE_EXPECTED_REDUCE_ONLY_FLAG_DOCUMENTED,
    GATE_EXPECTED_SYMBOLS_FLAG_DOCUMENTED,
    GATE_FULL_LIFECYCLE_NOT_INCLUDED,
    GATE_G20_NOT_LIFTED,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_GUARDED_CLEANUP_DRY_RUN_ADAPTER_ONLY,
    GATE_GUARDED_DESIGN_REVIEW_MISSING,
    GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE,
    GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE,
    GATE_GUARDED_ENTRY_ADAPTER_MISSING,
    GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE,
    GATE_GUARDED_STOP_ADAPTER_MISSING,
    GATE_GUARDED_STOP_ADAPTER_STATUS_UNACCEPTABLE,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_LIFECYCLE_SUMMARY_MISSING,
    GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED,
    GATE_MAX_NOTIONAL_FLAG_DOCUMENTED,
    GATE_NO_AUTO_EMERGENCY_CLOSE,
    GATE_NO_AUTO_ENTRY,
    GATE_NO_AUTO_NEXT_STEP,
    GATE_NO_AUTO_RETRY,
    GATE_NO_AUTO_SECOND_CLEANUP,
    GATE_NO_AUTO_STOP_ATTACH,
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
    GATE_PARTIAL_CLEANUP_FAIL_CLOSED,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_POST_CLEANUP_READONLY_REQUIRED,
    GATE_POST_CLEANUP_SELECTED_SYMBOL_ABSENT,
    GATE_PRE_CLEANUP_EXPECTED_QTY,
    GATE_PRE_CLEANUP_EXPECTED_SIDE_LONG,
    GATE_PRE_CLEANUP_EXPECTED_SYMBOL,
    GATE_PRE_CLEANUP_READONLY_REQUIRED,
    GATE_PRE_CLEANUP_SELECTED_SYMBOL_PRESENT,
    GATE_PRECONDITION_ACCOUNT_MODE_DEMO,
    GATE_PRECONDITION_CATEGORY_LINEAR,
    GATE_PRECONDITION_CLEANUP_SIDE_SELL,
    GATE_PRECONDITION_CLOSE_ON_TRIGGER_FALSE,
    GATE_PRECONDITION_ENDPOINT_FAMILY_BYBIT_DEMO,
    GATE_PRECONDITION_EXPECTED_CLEANUP_SYMBOL,
    GATE_PRECONDITION_EXPECTED_PROTECTED_LIST,
    GATE_PRECONDITION_MAX_NOTIONAL_CAP,
    GATE_PRECONDITION_ORDER_TYPE_MARKET,
    GATE_PRECONDITION_POSITION_IDX_ZERO,
    GATE_PRECONDITION_PROOF_STRENGTH_STRONG,
    GATE_PRECONDITION_QTY_TINY,
    GATE_PRECONDITION_REDUCE_ONLY_TRUE,
    GATE_PRECONDITION_SELECTED_SYMBOL_PRESENT,
    GATE_PRECONDITION_SIDE_LONG,
    GATE_PRECONDITION_SYMBOL_MATCHES,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW,
    GATE_PROTECTION_MISSING,
    GATE_READONLY_SMOKE_MISSING,
    GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
    GATE_REAL_CLEANUP_EXECUTION_NOT_IMPL,
    GATE_REAL_CLEANUP_NOT_IMPLEMENTED,
    GATE_REAL_EXECUTION_NOT_ALLOWED,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED,
    GATE_RECONCILIATION_MISSING,
    GATE_REDUCE_ONLY_INVALID_FAIL_CLOSED,
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
    GATE_STOP_ATTACH_NOT_INCLUDED,
    GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
    GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
    GATE_TOKEN_NOT_VALIDATED,
    GATE_VERIFICATION_PLAN_ONLY,
    MODE_CLEANUP_ADAPTER_CHECKLIST,
    MODE_CLEANUP_DRY_RUN_APPROVAL,
    MODE_FAIL_CLOSED,
    MODE_REAL_CLEANUP_EXECUTION_GUARD,
    ORDER_CREATE_PATH_REF,
    READINESS_CONCLUSION_NOT_EXECUTABLE,
    REQUIRED_CONFIRMATION_FLAGS,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_CLEANUP_ADAPTER_SCOPE,
    STAGE_2_CLEANUP_PRECONDITION_CONTRACT,
    STAGE_3_MANUAL_CONFIRMATION_DRY_RUN_CONTRACT,
    STAGE_4_CLEANUP_REQUEST_ENVELOPE_DRY_RUN,
    STAGE_5_CLEANUP_READONLY_VERIFICATION_PLAN,
    STAGE_6_CLEANUP_FAILURE_POLICY,
    STAGE_7_AUDIT_ARTIFACT_GENERATION,
    STAGE_8_FINAL_CLEANUP_ADAPTER_VERDICT,
    STATUS_ADAPTER_READY,
    STATUS_ADAPTER_READY_EXEC_DISABLED,
    STATUS_FAIL_CLOSED,
    STATUS_REAL_CLEANUP_NOT_IMPL,
    TRADING_STOP_PATH_REF,
    TinyGuardedCleanupDryRunAdapterResult,
)


_MODULE_PATH = ROOT / "src" / "demo_tiny_guarded_cleanup_dry_run_adapter.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_tiny_guarded_cleanup_dry_run_adapter.py"
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


def _valid_tiny_cleanup_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-11T11:59:00Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "TINY_CLEANUP_PERMISSION_CHECKLIST_READY",
        "cleanup_side":              "Sell",
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
        "timestamp_utc":             "2026-06-11T11:59:59.7Z",
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


def _valid_guarded_stop_adapter() -> dict:
    return {
        "timestamp_utc":             "2026-06-11T11:59:59.9Z",
        "mode":                      "stop_adapter_checklist",
        "selected_symbol":           "SOLUSDT",
        "status":                    "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY",
        "readiness_conclusion":      READINESS_CONCLUSION_NOT_EXECUTABLE,
        "real_execution_allowed":              False,
        "real_stop_attach_implemented":        False,
        "guarded_stop_attach_dry_run_adapter": True,
        "stop_attach_only":                    True,
        "entry_included":                      False,
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


def _adapter() -> DemoTinyGuardedCleanupDryRunAdapter:
    return DemoTinyGuardedCleanupDryRunAdapter()


_UNSET = object()


def _run(
    *,
    readonly=_UNSET, recon=_UNSET, protection=_UNSET, contract=_UNSET,
    noop_plan=_UNSET, lifecycle=_UNSET, real_permission_gate=_UNSET,
    tiny_cleanup_permission_gate=_UNSET,
    lifecycle_summary=_UNSET,
    runner_design=_UNSET,
    runner_dry_run=_UNSET,
    guarded_design_review=_UNSET,
    guarded_entry_adapter=_UNSET,
    guarded_stop_adapter=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    allow_cleanup_dry_run_approval=False,
    allow_real_cleanup_execution=False,
    _now=_TEST_NOW,
) -> TinyGuardedCleanupDryRunAdapterResult:
    return _adapter().run_checklist(
        readonly_smoke=_valid_readonly()                                         if readonly                       is _UNSET else readonly,
        reconciliation=_valid_reconciliation()                                   if recon                          is _UNSET else recon,
        protection=_valid_protection()                                           if protection                     is _UNSET else protection,
        contract=_valid_contract()                                               if contract                       is _UNSET else contract,
        noop_plan=_valid_noop_plan()                                             if noop_plan                      is _UNSET else noop_plan,
        lifecycle_mock=_valid_lifecycle()                                        if lifecycle                      is _UNSET else lifecycle,
        real_permission_gate=_valid_real_permission_gate()                       if real_permission_gate           is _UNSET else real_permission_gate,
        tiny_cleanup_permission_gate=_valid_tiny_cleanup_permission_gate()       if tiny_cleanup_permission_gate   is _UNSET else tiny_cleanup_permission_gate,
        lifecycle_summary=_valid_lifecycle_summary()                             if lifecycle_summary              is _UNSET else lifecycle_summary,
        runner_design=_valid_runner_design()                                     if runner_design                  is _UNSET else runner_design,
        runner_dry_run=_valid_runner_dry_run()                                   if runner_dry_run                 is _UNSET else runner_dry_run,
        guarded_design_review=_valid_guarded_design_review()                     if guarded_design_review          is _UNSET else guarded_design_review,
        guarded_entry_adapter=_valid_guarded_entry_adapter()                     if guarded_entry_adapter          is _UNSET else guarded_entry_adapter,
        guarded_stop_adapter=_valid_guarded_stop_adapter()                       if guarded_stop_adapter           is _UNSET else guarded_stop_adapter,
        symbol=symbol,
        allow_cleanup_dry_run_approval=allow_cleanup_dry_run_approval,
        allow_real_cleanup_execution=allow_real_cleanup_execution,
        _now=_now,
    )


# ===========================================================================
# AG1: valid checklist => TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY
# ===========================================================================

class TestAG1AdapterReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_ADAPTER_READY
        assert r.mode == MODE_CLEANUP_ADAPTER_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.real_execution_allowed is False
        assert r.real_cleanup_implemented is False
        assert r.guarded_cleanup_dry_run_adapter is True
        assert r.cleanup_only is True
        assert r.entry_included is False
        assert r.stop_attach_included is False
        assert r.full_lifecycle_included is False
        assert r.current_task_real_execution_allowed is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.next_required_task == "TASK-014AH_guarded_tiny_lifecycle_dry_run_summary"


# ===========================================================================
# AG2: --allow-cleanup-dry-run-approval => READY_BUT_EXECUTION_DISABLED
# ===========================================================================

class TestAG2CleanupDryRunApproval:
    def test_approval(self):
        r = _run(allow_cleanup_dry_run_approval=True)
        assert r.status == STATUS_ADAPTER_READY_EXEC_DISABLED
        assert r.mode == MODE_CLEANUP_DRY_RUN_APPROVAL
        assert r.cleanup_dry_run_approval_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_cleanup_implemented is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE


# ===========================================================================
# AG3: --allow-real-cleanup-execution => REAL_CLEANUP_EXECUTION_NOT_IMPLEMENTED
# ===========================================================================

class TestAG3RealCleanupExecutionGuard:
    def test_guard(self):
        r = _run(allow_real_cleanup_execution=True)
        assert r.status == STATUS_REAL_CLEANUP_NOT_IMPL
        assert r.mode == MODE_REAL_CLEANUP_EXECUTION_GUARD
        assert r.real_cleanup_execution_requested is True
        assert r.real_execution_allowed is False
        assert r.real_cleanup_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.no_position_modified is True


# ===========================================================================
# AG4-AG17: 14 missing upstream artifacts each => FAIL_CLOSED
# ===========================================================================

class TestAG4MissingReadonly:
    def test_fail_closed(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert r.failed_stage == STAGE_0_ARTIFACT_PREFLIGHT
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestAG5MissingReconciliation:
    def test_fail_closed(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestAG6MissingProtection:
    def test_fail_closed(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestAG7MissingContract:
    def test_fail_closed(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestAG8MissingNoopPlan:
    def test_fail_closed(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestAG9MissingLifecycle:
    def test_fail_closed(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestAG10MissingRealPermissionGate:
    def test_fail_closed(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAG11MissingTinyCleanupPermissionGate:
    def test_fail_closed(self):
        r = _run(tiny_cleanup_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAG12MissingLifecycleSummary:
    def test_fail_closed(self):
        r = _run(lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAG13MissingRunnerDesign:
    def test_fail_closed(self):
        r = _run(runner_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DESIGN_MISSING in r.blocked_gates


class TestAG14MissingRunnerDryRun:
    def test_fail_closed(self):
        r = _run(runner_dry_run=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DRY_RUN_MISSING in r.blocked_gates


class TestAG15MissingGuardedDesignReview:
    def test_fail_closed(self):
        r = _run(guarded_design_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_MISSING in r.blocked_gates


class TestAG16MissingGuardedEntryAdapter:
    def test_fail_closed(self):
        r = _run(guarded_entry_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_ENTRY_ADAPTER_MISSING in r.blocked_gates


class TestAG17MissingGuardedStopAdapter:
    def test_fail_closed(self):
        r = _run(guarded_stop_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_STOP_ADAPTER_MISSING in r.blocked_gates


# ===========================================================================
# AG18: selected symbol must equal SOLUSDT
# ===========================================================================

class TestAG18SymbolNotSolusdt:
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
# AG19-AG22: upstream invariant mismatches
# ===========================================================================

class TestAG19EndpointFamilyMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["endpoint_family"] = "bybit_live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestAG20AccountModeMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["account_mode"] = "live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestAG21ProofStrengthMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["proof_strength"] = "WEAK"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROOF_STRENGTH_NOT_STRONG in r.blocked_gates


class TestAG22PositionDetailsSourceMismatch:
    def test_fail_closed(self):
        bad = _valid_reconciliation()
        bad["position_details_source"] = "mock"
        bad["mode"] = "mock"
        r = _run(recon=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY in r.blocked_gates


# ===========================================================================
# AG23: guarded_design_review status unacceptable => fail closed
# ===========================================================================

class TestAG23GuardedDesignReviewStatusUnacceptable:
    def test_fail_closed(self):
        bad = _valid_guarded_design_review()
        bad["status"] = "SOMETHING_ELSE"
        r = _run(guarded_design_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE in r.blocked_gates


# ===========================================================================
# AG24: guarded_design_review readiness conclusion executable => fail closed
# ===========================================================================

class TestAG24GuardedDesignReviewReadinessExecutable:
    def test_fail_closed(self):
        bad = _valid_guarded_design_review()
        bad["readiness_conclusion"] = "READY_TO_EXECUTE"
        r = _run(guarded_design_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE in r.blocked_gates


# ===========================================================================
# AG25: guarded_entry_adapter status unacceptable => fail closed
# ===========================================================================

class TestAG25GuardedEntryAdapterStatusUnacceptable:
    def test_fail_closed(self):
        bad = _valid_guarded_entry_adapter()
        bad["status"] = "SOMETHING_ELSE"
        r = _run(guarded_entry_adapter=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE in r.blocked_gates


# ===========================================================================
# AG26: guarded_stop_adapter status unacceptable => fail closed
# ===========================================================================

class TestAG26GuardedStopAdapterStatusUnacceptable:
    def test_fail_closed(self):
        bad = _valid_guarded_stop_adapter()
        bad["status"] = "SOMETHING_ELSE"
        r = _run(guarded_stop_adapter=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_STOP_ADAPTER_STATUS_UNACCEPTABLE in r.blocked_gates


# ===========================================================================
# AG27: missing --symbol
# ===========================================================================

class TestAG27MissingSymbol:
    def test_fail_closed(self):
        r = _run(symbol="")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_MISSING in r.blocked_gates


# ===========================================================================
# AG28: 9 stages present
# ===========================================================================

class TestAG28NineStages:
    def test_stage_count(self):
        r = _run()
        assert len(r.stages) == 9
        assert r.stage_order == list(ALL_STAGES)
        for stage_id in ALL_STAGES:
            assert stage_id in r.stages
            assert r.stages[stage_id]["stage"] == stage_id


# ===========================================================================
# AG29: cleanup adapter scope content
# ===========================================================================

class TestAG29CleanupAdapterScope:
    def test_scope_flags(self):
        r = _run()
        s = r.cleanup_adapter_scope
        assert s["guarded_cleanup_dry_run_adapter"] is True
        assert s["cleanup_only"] is True
        assert s["entry_included"] is False
        assert s["stop_attach_included"] is False
        assert s["full_lifecycle_included"] is False
        assert s["real_cleanup_implemented"] is False
        assert s["real_execution_allowed"] is False
        assert s["order_endpoint_called"] is False
        assert s["stop_endpoint_called"] is False
        assert s["no_endpoint_invoked_in_this_task"] is True
        assert s["no_position_modified"] is True
        assert s["no_secrets_loaded"] is True
        assert s["g20_policy_still_in_place"] is True
        assert s["g20_lifted"] is False
        assert s["next_required_task"] == "TASK-014AH_guarded_tiny_lifecycle_dry_run_summary"


# ===========================================================================
# AG30: cleanup precondition contract
# ===========================================================================

class TestAG30CleanupPreconditionContract:
    def test_payload_invariants(self):
        r = _run()
        c = r.cleanup_precondition_contract
        assert c["selected_symbol"] == "SOLUSDT"
        assert c["expected_cleanup_symbol"] == EXPECTED_PRE_CLEANUP_SYMBOL == "SOLUSDT"
        assert c["expected_pre_cleanup_side"] == EXPECTED_PRE_CLEANUP_SIDE == "long"
        assert c["expected_pre_cleanup_qty"] == EXPECTED_PRE_CLEANUP_QTY == 0.1
        assert c["cleanup_side"] == EXPECTED_CLEANUP_SIDE == "Sell"
        assert c["orderType"] == EXPECTED_CLEANUP_ORDER_TYPE == "Market"
        assert c["reduceOnly"] == EXPECTED_REDUCE_ONLY is True
        assert c["closeOnTrigger"] == EXPECTED_CLOSE_ON_TRIGGER is False
        assert c["positionIdx"] == EXPECTED_POSITION_IDX == 0
        assert c["category"] == EXPECTED_INSTRUMENT_CATEGORY == "linear"
        assert c["selected_symbol_present_before_cleanup"] is True
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
                  GATE_PRECONDITION_EXPECTED_CLEANUP_SYMBOL,
                  GATE_PRECONDITION_SIDE_LONG,
                  GATE_PRECONDITION_QTY_TINY,
                  GATE_PRECONDITION_CLEANUP_SIDE_SELL,
                  GATE_PRECONDITION_REDUCE_ONLY_TRUE,
                  GATE_PRECONDITION_CLOSE_ON_TRIGGER_FALSE,
                  GATE_PRECONDITION_POSITION_IDX_ZERO,
                  GATE_PRECONDITION_ORDER_TYPE_MARKET,
                  GATE_PRECONDITION_CATEGORY_LINEAR,
                  GATE_PRECONDITION_MAX_NOTIONAL_CAP,
                  GATE_PRECONDITION_SELECTED_SYMBOL_PRESENT,
                  GATE_PRECONDITION_EXPECTED_PROTECTED_LIST,
                  GATE_PRECONDITION_PROOF_STRENGTH_STRONG,
                  GATE_PRECONDITION_ACCOUNT_MODE_DEMO,
                  GATE_PRECONDITION_ENDPOINT_FAMILY_BYBIT_DEMO):
            assert g in blocked


# ===========================================================================
# AG31: manual confirmation dry-run contract
# ===========================================================================

class TestAG31ManualConfirmationContract:
    def test_token_pattern(self):
        r = _run()
        m = r.manual_confirmation_dry_run_contract
        assert m["cleanup_token_pattern"] == CLEANUP_TOKEN_PATTERN
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
        assert m["expected_cleanup_symbol_required"] is True
        assert m["expected_cleanup_qty_required"] is True
        assert m["expected_cleanup_side_required"] is True
        assert m["expected_reduce_only_required"] is True

    def test_gates_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_CLEANUP_TOKEN_PATTERN_PRESENT, GATE_TOKEN_NOT_VALIDATED,
                  GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
                  GATE_SECOND_CONFIRMATION_DOCUMENTED,
                  GATE_MAX_NOTIONAL_FLAG_DOCUMENTED,
                  GATE_EXPECTED_COUNT_FLAG_DOCUMENTED,
                  GATE_EXPECTED_SYMBOLS_FLAG_DOCUMENTED,
                  GATE_EXPECTED_CLEANUP_SYMBOL_FLAG_DOCUMENTED,
                  GATE_EXPECTED_CLEANUP_QTY_FLAG_DOCUMENTED,
                  GATE_EXPECTED_CLEANUP_SIDE_FLAG_DOCUMENTED,
                  GATE_EXPECTED_REDUCE_ONLY_FLAG_DOCUMENTED,
                  GATE_CONFIRMATION_FLAGS_NOT_VALIDATED):
            assert g in blocked


# ===========================================================================
# AG32: cleanup request envelope - preview only, no signature, no headers
# ===========================================================================

class TestAG32CleanupRequestEnvelope:
    def test_envelope_safety_flags(self):
        r = _run()
        e = r.cleanup_request_envelope
        assert e["preview_only"] is True
        assert e["send_allowed"] is False
        assert e["endpoint_called"] is False
        assert e["real_payload"] is False
        assert e["signature_present"] is False
        assert e["private_headers"] == []
        assert e["no_sender_adapter"] is True

    def test_envelope_payload(self):
        r = _run()
        e = r.cleanup_request_envelope
        assert e["endpoint_path_ref"] == ORDER_CREATE_PATH_REF
        assert e["base_url_ref"] == BASE_URL_DEMO_REF
        assert e["demo_endpoint_allowlist"] == [BASE_URL_DEMO_REF]
        assert e["live_endpoint_denylist"] == [BASE_URL_LIVE_REF]
        assert e["category"] == "linear"
        assert e["symbol"] == "SOLUSDT"
        assert e["side"] == EXPECTED_CLEANUP_SIDE == "Sell"
        assert e["orderType"] == EXPECTED_CLEANUP_ORDER_TYPE == "Market"
        assert e["qty"] == EXPECTED_PRE_CLEANUP_QTY == 0.1
        assert e["reduceOnly"] is True
        assert e["closeOnTrigger"] is False
        assert e["positionIdx"] == 0
        assert e["orderLinkId_prefix"] == DRYRUN_ORDER_LINK_ID_PREFIX
        assert e["orderLinkId_example"].startswith(DRYRUN_ORDER_LINK_ID_PREFIX)

    def test_gates_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_CLEANUP_ENVELOPE_PRESENT, GATE_ENVELOPE_PREVIEW_ONLY,
                  GATE_ENVELOPE_SEND_NOT_ALLOWED,
                  GATE_ENVELOPE_ENDPOINT_NOT_CALLED,
                  GATE_ENVELOPE_NOT_REAL_PAYLOAD,
                  GATE_ENVELOPE_NO_SIGNATURE,
                  GATE_ENVELOPE_NO_PRIVATE_HEADERS,
                  GATE_ENVELOPE_ORDER_CREATE_PATH,
                  GATE_ENVELOPE_BASE_URL_DEMO_ONLY,
                  GATE_ENVELOPE_SIDE_SELL,
                  GATE_ENVELOPE_QTY_TINY,
                  GATE_ENVELOPE_REDUCE_ONLY_TRUE,
                  GATE_ENVELOPE_CLOSE_ON_TRIGGER_FALSE,
                  GATE_ENVELOPE_ORDER_TYPE_MARKET,
                  GATE_NO_SENDER_ADAPTER):
            assert g in blocked


# ===========================================================================
# AG33: readonly verification plan
# ===========================================================================

class TestAG33ReadonlyVerificationPlan:
    def test_pre_post_required(self):
        r = _run()
        p = r.cleanup_readonly_verification_plan
        assert p["pre_cleanup_readonly_required"] is True
        assert p["post_cleanup_readonly_required"] is True
        assert p["pre_cleanup_selected_symbol_present"] is True
        assert p["pre_cleanup_expected_symbol"] == "SOLUSDT"
        assert p["pre_cleanup_expected_qty"] == EXPECTED_PRE_CLEANUP_QTY
        assert p["pre_cleanup_expected_side"] == EXPECTED_PRE_CLEANUP_SIDE == "long"
        assert p["post_cleanup_selected_symbol_absent_or_zero"] is True
        assert p["existing_positions_unchanged_required"] is True
        assert p["verification_plan_only"] is True
        assert p["real_readonly_after_execution_not_performed"] is True

    def test_gates_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_PRE_CLEANUP_READONLY_REQUIRED,
                  GATE_POST_CLEANUP_READONLY_REQUIRED,
                  GATE_PRE_CLEANUP_SELECTED_SYMBOL_PRESENT,
                  GATE_PRE_CLEANUP_EXPECTED_SYMBOL,
                  GATE_PRE_CLEANUP_EXPECTED_QTY,
                  GATE_PRE_CLEANUP_EXPECTED_SIDE_LONG,
                  GATE_POST_CLEANUP_SELECTED_SYMBOL_ABSENT,
                  GATE_EXISTING_POSITIONS_UNCHANGED_REQUIRED,
                  GATE_VERIFICATION_PLAN_ONLY,
                  GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED):
            assert g in blocked


# ===========================================================================
# AG34: failure policy
# ===========================================================================

class TestAG34FailurePolicy:
    def test_fail_closed_paths(self):
        r = _run()
        f = r.cleanup_failure_policy
        assert f["request_rejected"] == "FAIL_CLOSED"
        assert f["selected_symbol_absent"] == "FAIL_CLOSED"
        assert f["selected_symbol_side_mismatch"] == "FAIL_CLOSED"
        assert f["selected_symbol_qty_mismatch"] == "FAIL_CLOSED"
        assert f["cleanup_side_invalid"] == "FAIL_CLOSED"
        assert f["reduce_only_invalid"] == "FAIL_CLOSED"
        assert f["partial_cleanup"] == "FAIL_CLOSED"
        assert f["existing_protected_mismatch"] == "MANUAL_REVIEW_REQUIRED"
        assert f["readonly_unavailable"] == "FAIL_CLOSED"
        assert f["live_endpoint_detected"] == "FAIL_CLOSED"
        assert f["secret_emission_detected"] == "FAIL_CLOSED"

    def test_no_automatic(self):
        r = _run()
        f = r.cleanup_failure_policy
        assert f["no_auto_retry"] is True
        assert f["no_auto_second_cleanup"] is True
        assert f["no_auto_emergency_close"] is True
        assert f["no_auto_entry"] is True
        assert f["no_auto_stop_attach"] is True
        assert f["no_auto_next_step"] is True
        assert f["manual_intervention_only"] is True

    def test_gates_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_REQUEST_REJECTED_FAIL_CLOSED,
                  GATE_SELECTED_SYMBOL_ABSENT_FAIL_CLOSED,
                  GATE_SELECTED_SYMBOL_SIDE_MISMATCH_FAIL_CLOSED,
                  GATE_SELECTED_SYMBOL_QTY_MISMATCH_FAIL_CLOSED,
                  GATE_CLEANUP_SIDE_INVALID_FAIL_CLOSED,
                  GATE_REDUCE_ONLY_INVALID_FAIL_CLOSED,
                  GATE_PARTIAL_CLEANUP_FAIL_CLOSED,
                  GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW,
                  GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
                  GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED,
                  GATE_SECRET_EMISSION_FAIL_CLOSED,
                  GATE_NO_AUTO_RETRY, GATE_NO_AUTO_SECOND_CLEANUP,
                  GATE_NO_AUTO_EMERGENCY_CLOSE,
                  GATE_NO_AUTO_ENTRY,
                  GATE_NO_AUTO_STOP_ATTACH,
                  GATE_NO_AUTO_NEXT_STEP):
            assert g in blocked


# ===========================================================================
# AG35: audit artifacts (dry-run not sent, sanitized, no secrets)
# ===========================================================================

class TestAG35AuditArtifacts:
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
        assert "cleanup_request_envelope" in a
        assert "readonly_verification_plan" in a
        assert "failure_policy" in a
        assert "final_cleanup_adapter_verdict" in a

    def test_gates_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_AUDIT_ARTIFACTS_PRESENT,
                  GATE_AUDIT_RESPONSE_DRY_RUN_NOT_SENT,
                  GATE_AUDIT_RESPONSE_FROM_EXCHANGE_FALSE,
                  GATE_AUDIT_SANITIZED, GATE_AUDIT_NO_SECRETS):
            assert g in blocked


# ===========================================================================
# AG36: final cleanup adapter verdict
# ===========================================================================

class TestAG36FinalCleanupAdapterVerdict:
    def test_default(self):
        r = _run()
        v = r.final_cleanup_adapter_verdict
        assert v["cleanup_dry_run_approval_allowed"] is False
        assert v["real_cleanup_execution_requested"] is False
        assert v["real_execution_allowed"] is False
        assert v["real_cleanup_implemented"] is False
        assert v["guarded_cleanup_dry_run_adapter"] is True
        assert v["cleanup_only"] is True
        assert v["entry_included"] is False
        assert v["stop_attach_included"] is False
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
        assert v["mode"] == MODE_CLEANUP_ADAPTER_CHECKLIST
        assert v["next_required_task"] == "TASK-014AH_guarded_tiny_lifecycle_dry_run_summary"

    def test_approval(self):
        r = _run(allow_cleanup_dry_run_approval=True)
        v = r.final_cleanup_adapter_verdict
        assert v["status"] == STATUS_ADAPTER_READY_EXEC_DISABLED
        assert v["mode"] == MODE_CLEANUP_DRY_RUN_APPROVAL

    def test_guard(self):
        r = _run(allow_real_cleanup_execution=True)
        v = r.final_cleanup_adapter_verdict
        assert v["status"] == STATUS_REAL_CLEANUP_NOT_IMPL
        assert v["mode"] == MODE_REAL_CLEANUP_EXECUTION_GUARD
        assert v["real_cleanup_execution_requested"] is True
        assert v["real_execution_allowed"] is False


# ===========================================================================
# AG37: g20 still in place (not lifted)
# ===========================================================================

class TestAG37G20NotLifted:
    def test_g20_invariants(self):
        for kw in ({}, {"allow_cleanup_dry_run_approval": True},
                   {"allow_real_cleanup_execution": True}):
            r = _run(**kw)
            assert r.g20_policy_still_in_place is True
            assert r.g20_lifted is False
            assert GATE_G20_NOT_LIFTED in r.blocked_gates
            assert GATE_G20_POLICY_STILL_IN_PLACE in r.blocked_gates
            assert GATE_NO_G20_LIFT in r.blocked_gates


# ===========================================================================
# AG38: socket-disabled import smoke
# ===========================================================================

class TestAG38SocketDisabledImport:
    def test_module_safe_under_socket_disabled(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"]       = str(ROOT)
        cp = subprocess.run(
            [sys.executable, "-c",
             "import socket; socket.socket = None; "
             "import src.demo_tiny_guarded_cleanup_dry_run_adapter as m; "
             "print('OK', m.STATUS_ADAPTER_READY)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=60,
        )
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout


# ===========================================================================
# AG39: dataclass roundtrip with deep-copy
# ===========================================================================

class TestAG39DataclassRoundTrip:
    def test_to_dict_roundtrip(self):
        r = _run(allow_cleanup_dry_run_approval=True)
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
            ("real_cleanup_implemented",            False),
            ("guarded_cleanup_dry_run_adapter",     True),
            ("cleanup_only",                        True),
            ("entry_included",                      False),
            ("stop_attach_included",                False),
            ("full_lifecycle_included",             False),
            ("real_execution_allowed",              False),
            ("cleanup_dry_run_approval_allowed",    True),
        ):
            assert d[key] is expected, f"{key} should be {expected}"
        assert d["status"] == STATUS_ADAPTER_READY_EXEC_DISABLED
        assert d["readiness_conclusion"] == READINESS_CONCLUSION_NOT_EXECUTABLE
        # Deep-copy: mutating returned dict must not affect source.
        d["stages"][STAGE_2_CLEANUP_PRECONDITION_CONTRACT]["mutated"] = True
        assert "mutated" not in r.stages[STAGE_2_CLEANUP_PRECONDITION_CONTRACT]
        d["cleanup_adapter_scope"]["mutated"] = True
        assert "mutated" not in r.cleanup_adapter_scope
        d["cleanup_precondition_contract"]["mutated"] = True
        assert "mutated" not in r.cleanup_precondition_contract
        d["cleanup_request_envelope"]["mutated"] = True
        assert "mutated" not in r.cleanup_request_envelope


# ===========================================================================
# AG40: path refs
# ===========================================================================

class TestAG40PathRefs:
    def test_path_refs(self):
        r = _run()
        assert r.order_create_path_ref == ORDER_CREATE_PATH_REF
        assert r.trading_stop_path_ref == TRADING_STOP_PATH_REF
        assert r.base_url_ref          == BASE_URL_DEMO_REF
        assert r.base_url_ref != BASE_URL_LIVE_REF


# ===========================================================================
# AG41: safety invariants on dataclass (default / approval / guard)
# ===========================================================================

class TestAG41SafetyInvariants:
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
        r = _run(allow_cleanup_dry_run_approval=True)
        assert r.send_allowed is False
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_secrets_loaded is True

    def test_guard(self):
        r = _run(allow_real_cleanup_execution=True)
        assert r.send_allowed is False
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.real_execution_allowed is False
        assert r.real_cleanup_implemented is False


# ===========================================================================
# AG42: gate count >= 117
# ===========================================================================

class TestAG42GateCount:
    def test_at_least_117(self):
        import src.demo_tiny_guarded_cleanup_dry_run_adapter as m
        gate_names = [
            n for n in dir(m)
            if n.startswith("GATE_") and isinstance(getattr(m, n), str)
        ]
        assert len(gate_names) >= 117, (
            f"Expected >= 117 GATE_ constants, got {len(gate_names)}: "
            f"{sorted(gate_names)}"
        )


# ===========================================================================
# AG43: always-on gates surface in every checklist
# ===========================================================================

class TestAG43AlwaysOnGates:
    def test_always_on_present(self):
        r = _run()
        unique = set(r.blocked_gates)
        for g in (
            # scope
            GATE_GUARDED_CLEANUP_DRY_RUN_ADAPTER_ONLY, GATE_CLEANUP_ONLY,
            GATE_ENTRY_NOT_INCLUDED, GATE_STOP_ATTACH_NOT_INCLUDED,
            GATE_FULL_LIFECYCLE_NOT_INCLUDED,
            GATE_REAL_CLEANUP_NOT_IMPLEMENTED,
            GATE_REAL_EXECUTION_NOT_ALLOWED,
            GATE_NO_ENDPOINT_INVOKED, GATE_NO_POSITION_MODIFIED_SCOPE,
            GATE_NO_SECRETS_LOADED, GATE_NO_G20_LIFT,
            # precondition
            GATE_PRECONDITION_SYMBOL_MATCHES,
            GATE_PRECONDITION_EXPECTED_CLEANUP_SYMBOL,
            GATE_PRECONDITION_SIDE_LONG,
            GATE_PRECONDITION_QTY_TINY,
            GATE_PRECONDITION_CLEANUP_SIDE_SELL,
            GATE_PRECONDITION_REDUCE_ONLY_TRUE,
            GATE_PRECONDITION_CLOSE_ON_TRIGGER_FALSE,
            GATE_PRECONDITION_POSITION_IDX_ZERO,
            GATE_PRECONDITION_ORDER_TYPE_MARKET,
            GATE_PRECONDITION_CATEGORY_LINEAR,
            GATE_PRECONDITION_MAX_NOTIONAL_CAP,
            GATE_PRECONDITION_SELECTED_SYMBOL_PRESENT,
            GATE_PRECONDITION_EXPECTED_PROTECTED_LIST,
            GATE_PRECONDITION_PROOF_STRENGTH_STRONG,
            GATE_PRECONDITION_ACCOUNT_MODE_DEMO,
            GATE_PRECONDITION_ENDPOINT_FAMILY_BYBIT_DEMO,
            # manual confirmation
            GATE_CLEANUP_TOKEN_PATTERN_PRESENT, GATE_TOKEN_NOT_VALIDATED,
            GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
            GATE_SECOND_CONFIRMATION_DOCUMENTED,
            GATE_MAX_NOTIONAL_FLAG_DOCUMENTED,
            GATE_EXPECTED_COUNT_FLAG_DOCUMENTED,
            GATE_EXPECTED_SYMBOLS_FLAG_DOCUMENTED,
            GATE_EXPECTED_CLEANUP_SYMBOL_FLAG_DOCUMENTED,
            GATE_EXPECTED_CLEANUP_QTY_FLAG_DOCUMENTED,
            GATE_EXPECTED_CLEANUP_SIDE_FLAG_DOCUMENTED,
            GATE_EXPECTED_REDUCE_ONLY_FLAG_DOCUMENTED,
            GATE_CONFIRMATION_FLAGS_NOT_VALIDATED,
            # envelope
            GATE_CLEANUP_ENVELOPE_PRESENT, GATE_ENVELOPE_PREVIEW_ONLY,
            GATE_ENVELOPE_SEND_NOT_ALLOWED,
            GATE_ENVELOPE_ENDPOINT_NOT_CALLED,
            GATE_ENVELOPE_NOT_REAL_PAYLOAD,
            GATE_ENVELOPE_NO_SIGNATURE,
            GATE_ENVELOPE_NO_PRIVATE_HEADERS,
            GATE_ENVELOPE_ORDER_CREATE_PATH,
            GATE_ENVELOPE_BASE_URL_DEMO_ONLY,
            GATE_ENVELOPE_SIDE_SELL,
            GATE_ENVELOPE_QTY_TINY,
            GATE_ENVELOPE_REDUCE_ONLY_TRUE,
            GATE_ENVELOPE_CLOSE_ON_TRIGGER_FALSE,
            GATE_ENVELOPE_ORDER_TYPE_MARKET,
            GATE_NO_SENDER_ADAPTER,
            # readonly plan
            GATE_PRE_CLEANUP_READONLY_REQUIRED,
            GATE_POST_CLEANUP_READONLY_REQUIRED,
            GATE_PRE_CLEANUP_SELECTED_SYMBOL_PRESENT,
            GATE_PRE_CLEANUP_EXPECTED_SYMBOL,
            GATE_PRE_CLEANUP_EXPECTED_QTY,
            GATE_PRE_CLEANUP_EXPECTED_SIDE_LONG,
            GATE_POST_CLEANUP_SELECTED_SYMBOL_ABSENT,
            GATE_EXISTING_POSITIONS_UNCHANGED_REQUIRED,
            GATE_VERIFICATION_PLAN_ONLY,
            GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED,
            # failure policy
            GATE_REQUEST_REJECTED_FAIL_CLOSED,
            GATE_SELECTED_SYMBOL_ABSENT_FAIL_CLOSED,
            GATE_SELECTED_SYMBOL_SIDE_MISMATCH_FAIL_CLOSED,
            GATE_SELECTED_SYMBOL_QTY_MISMATCH_FAIL_CLOSED,
            GATE_CLEANUP_SIDE_INVALID_FAIL_CLOSED,
            GATE_REDUCE_ONLY_INVALID_FAIL_CLOSED,
            GATE_PARTIAL_CLEANUP_FAIL_CLOSED,
            GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW,
            GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
            GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED,
            GATE_SECRET_EMISSION_FAIL_CLOSED,
            GATE_NO_AUTO_RETRY, GATE_NO_AUTO_SECOND_CLEANUP,
            GATE_NO_AUTO_EMERGENCY_CLOSE,
            GATE_NO_AUTO_ENTRY,
            GATE_NO_AUTO_STOP_ATTACH,
            GATE_NO_AUTO_NEXT_STEP,
            # audit
            GATE_AUDIT_ARTIFACTS_PRESENT,
            GATE_AUDIT_RESPONSE_DRY_RUN_NOT_SENT,
            GATE_AUDIT_RESPONSE_FROM_EXCHANGE_FALSE,
            GATE_AUDIT_SANITIZED, GATE_AUDIT_NO_SECRETS,
            # execution guard
            GATE_REAL_CLEANUP_EXECUTION_NOT_IMPL,
            GATE_NO_REAL_ORDER_ENDPOINT, GATE_NO_REAL_STOP_ENDPOINT,
            GATE_NO_POSITION_MODIFIED, GATE_G20_NOT_LIFTED,
            GATE_G20_POLICY_STILL_IN_PLACE, GATE_NO_LIVE_ENDPOINT,
            GATE_NO_SECRETS_EMITTED,
        ):
            assert g in unique, f"always-on gate missing: {g}"


# ===========================================================================
# AG44: no forbidden imports
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
    "src.demo_close_only_cleanup",
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
    "src.demo_tiny_guarded_stop_attach_dry_run_adapter",
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


class TestAG44NoForbiddenImports:
    def test_module(self):
        imp = _collect_imports(_MODULE_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in module"

    def test_cli(self):
        imp = _collect_imports(_SCRIPT_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in CLI"


# ===========================================================================
# AG45: no sender / AE / AF module reuse
# ===========================================================================

class TestAG45NoSenderOrAEAFReuse:
    def test_no_close_only(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoCloseOnlySender"     not in code
            assert "demo_close_only_sender"  not in code
            assert "DemoCloseOnlyCleanup"    not in code
            assert "demo_close_only_cleanup" not in code

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

    def test_no_af_module_reuse(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTinyGuardedStopAttachDryRunAdapter" not in code

    def test_no_ad_module_reuse(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTinyLifecycleGuardedRunnerDesignReview" not in code

    def test_no_runner_dry_run_module_reuse(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTinyLifecycleRunnerDryRun" not in code


# ===========================================================================
# AG46: no network tokens in code
# ===========================================================================

class TestAG46NoNetworkTokens:
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
# AG47: no env/signing in module
# ===========================================================================

class TestAG47NoEnvOrSigning:
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
# AG48: forbidden flags absent
# ===========================================================================

class TestAG48NoForbiddenFlags:
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
# AG49: cleanup token pattern structure
# ===========================================================================

class TestAG49CleanupTokenPattern:
    def test_token_structure(self):
        assert CLEANUP_TOKEN_PATTERN.startswith("CONFIRM_DEMO_TINY_CLEANUP_")
        assert "YYYYMMDD" in CLEANUP_TOKEN_PATTERN
        assert "SYMBOL" in CLEANUP_TOKEN_PATTERN

    def test_token_surfaced(self):
        r = _run()
        assert r.cleanup_token_pattern == CLEANUP_TOKEN_PATTERN


# ===========================================================================
# AG50: stage_0 artifact preflight reports all 14 upstream artifacts present
# ===========================================================================

class TestAG50Stage0PreflightAllPresent:
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
        assert env["tiny_cleanup_permission_gate_present"]     is True
        assert env["lifecycle_summary_present"]                is True
        assert env["runner_design_present"]                    is True
        assert env["runner_dry_run_present"]                   is True
        assert env["guarded_design_review_present"]            is True
        assert env["guarded_entry_adapter_present"]            is True
        assert env["guarded_stop_adapter_present"]             is True
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

    def test_guarded_stop_adapter_acceptable_list_surfaced(self):
        r = _run()
        env = r.stages[STAGE_0_ARTIFACT_PREFLIGHT]
        assert env["guarded_stop_adapter_status_acceptable"] == sorted(
            ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES
        )


# ===========================================================================
# AG51-AG53: CLI / report helpers + tests
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
        cp_d   = base / "cleanup_perm"; cp_d.mkdir()
        sum_d  = base / "summary";      sum_d.mkdir()
        des_d  = base / "design";       des_d.mkdir()
        dry_d  = base / "dry_run";      dry_d.mkdir()
        grv_d  = base / "guarded_rev";  grv_d.mkdir()
        gea_d  = base / "entry_adapter"; gea_d.mkdir()
        gsa_d  = base / "stop_adapter"; gsa_d.mkdir()
        out_d  = base / "out"
        (ro_d   / "latest_smoke.json").write_text(json.dumps(_valid_readonly()), encoding="utf-8")
        (rec_d  / "latest_reconciliation.json").write_text(json.dumps(_valid_reconciliation()), encoding="utf-8")
        (prot_d / "latest_new_entry_protection.json").write_text(json.dumps(_valid_protection()), encoding="utf-8")
        (con_d  / "latest_trading_stop_contract.json").write_text(json.dumps(_valid_contract()), encoding="utf-8")
        (noop_d / "latest_trading_stop_noop_probe_plan.json").write_text(json.dumps(_valid_noop_plan()), encoding="utf-8")
        (lc_d   / "latest_tiny_position_lifecycle_mock.json").write_text(json.dumps(_valid_lifecycle()), encoding="utf-8")
        (rp_d   / "latest_tiny_position_real_permission_gate.json").write_text(json.dumps(_valid_real_permission_gate()), encoding="utf-8")
        (cp_d   / "latest_tiny_cleanup_permission_gate.json").write_text(json.dumps(_valid_tiny_cleanup_permission_gate()), encoding="utf-8")
        (sum_d  / "latest_tiny_lifecycle_real_execution_summary.json").write_text(json.dumps(_valid_lifecycle_summary()), encoding="utf-8")
        (des_d  / "latest_tiny_lifecycle_runner_design.json").write_text(json.dumps(_valid_runner_design()), encoding="utf-8")
        (dry_d  / "latest_tiny_lifecycle_runner_dry_run.json").write_text(json.dumps(_valid_runner_dry_run()), encoding="utf-8")
        (grv_d  / "latest_tiny_lifecycle_guarded_runner_design_review.json").write_text(json.dumps(_valid_guarded_design_review()), encoding="utf-8")
        (gea_d  / "latest_tiny_guarded_entry_dry_run_adapter.json").write_text(json.dumps(_valid_guarded_entry_adapter()), encoding="utf-8")
        (gsa_d  / "latest_tiny_guarded_stop_attach_dry_run_adapter.json").write_text(json.dumps(_valid_guarded_stop_adapter()), encoding="utf-8")
        return (ro_d, rec_d, prot_d, con_d, noop_d, lc_d,
                rp_d, cp_d, sum_d, des_d, dry_d, grv_d, gea_d, gsa_d, out_d)


class TestAG51ReportChecklist(_ReportSetupMixin):
    def test_writes_report(self):
        from scripts.preview_demo_tiny_guarded_cleanup_dry_run_adapter import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, cp_d,
             sum_d, des_d, dry_d, grv_d, gea_d, gsa_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_cleanup_dry_run_approval=False,
                allow_real_cleanup_execution=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_cleanup_dir=cp_d,
                lifecycle_summary_dir=sum_d,
                runner_design_dir=des_d,
                runner_dry_run_dir=dry_d,
                guarded_design_review_dir=grv_d,
                guarded_entry_adapter_dir=gea_d,
                guarded_stop_adapter_dir=gsa_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            files = sorted(p.name for p in out_d.iterdir())
            assert "latest_tiny_guarded_cleanup_dry_run_adapter.json" in files
            assert "latest_tiny_guarded_cleanup_dry_run_adapter.md"   in files
            data = json.loads(
                (out_d / "latest_tiny_guarded_cleanup_dry_run_adapter.json").read_text(encoding="utf-8")
            )
            assert data["status"] == STATUS_ADAPTER_READY
            assert data["real_execution_allowed"] is False
            assert data["real_cleanup_implemented"] is False
            assert data["guarded_cleanup_dry_run_adapter"] is True
            assert data["cleanup_only"] is True
            assert data["entry_included"] is False
            assert data["stop_attach_included"] is False
            assert data["order_endpoint_called"] is False
            assert data["stop_endpoint_called"] is False
            assert data["no_position_modified"] is True
            assert data["readiness_conclusion"] == READINESS_CONCLUSION_NOT_EXECUTABLE
            assert data["required_confirmation_flags"] == list(REQUIRED_CONFIRMATION_FLAGS)
            assert data["next_required_task"] == (
                "TASK-014AH_guarded_tiny_lifecycle_dry_run_summary"
            )


class TestAG52NoSecretsInReport(_ReportSetupMixin):
    def test_no_secrets(self):
        from scripts.preview_demo_tiny_guarded_cleanup_dry_run_adapter import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, cp_d,
             sum_d, des_d, dry_d, grv_d, gea_d, gsa_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_cleanup_dry_run_approval=False,
                allow_real_cleanup_execution=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_cleanup_dir=cp_d,
                lifecycle_summary_dir=sum_d,
                runner_design_dir=des_d,
                runner_dry_run_dir=dry_d,
                guarded_design_review_dir=grv_d,
                guarded_entry_adapter_dir=gea_d,
                guarded_stop_adapter_dir=gsa_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            md = (out_d / "latest_tiny_guarded_cleanup_dry_run_adapter.md").read_text(encoding="utf-8")
            for forbidden in ("API_KEY", "API_SECRET", "BYBIT_API", "X-BAPI-SIGN"):
                assert forbidden not in md
            data = json.loads(
                (out_d / "latest_tiny_guarded_cleanup_dry_run_adapter.json").read_text(encoding="utf-8")
            )
            assert data["secret_value_observed"] is False
            assert data["no_secrets_loaded"] is True


class TestAG53CLIExitCodes(_ReportSetupMixin):
    def test_run_execute_exits_0(self):
        from scripts.preview_demo_tiny_guarded_cleanup_dry_run_adapter import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, cp_d,
             sum_d, des_d, dry_d, grv_d, gea_d, gsa_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_cleanup_dry_run_approval=False,
                allow_real_cleanup_execution=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_cleanup_dir=cp_d,
                lifecycle_summary_dir=sum_d,
                runner_design_dir=des_d,
                runner_dry_run_dir=dry_d,
                guarded_design_review_dir=grv_d,
                guarded_entry_adapter_dir=gea_d,
                guarded_stop_adapter_dir=gsa_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0

    def test_run_execute_missing_exits_1(self):
        from scripts.preview_demo_tiny_guarded_cleanup_dry_run_adapter import run_execute
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for sub in ("readonly", "recon", "protection", "contract", "noop",
                        "lifecycle", "real_perm", "cleanup_perm",
                        "summary", "design", "dry_run", "guarded_rev",
                        "entry_adapter", "stop_adapter"):
                (base / sub).mkdir()
            rc = run_execute(
                symbol="SOLUSDT",
                allow_cleanup_dry_run_approval=False,
                allow_real_cleanup_execution=False,
                write_report=False,
                readonly_dir=base / "readonly",
                reconciliation_dir=base / "recon",
                protection_dir=base / "protection",
                contract_dir=base / "contract",
                noop_plan_dir=base / "noop",
                lifecycle_dir=base / "lifecycle",
                real_permission_dir=base / "real_perm",
                tiny_cleanup_dir=base / "cleanup_perm",
                lifecycle_summary_dir=base / "summary",
                runner_design_dir=base / "design",
                runner_dry_run_dir=base / "dry_run",
                guarded_design_review_dir=base / "guarded_rev",
                guarded_entry_adapter_dir=base / "entry_adapter",
                guarded_stop_adapter_dir=base / "stop_adapter",
                output_dir=base / "out", _now=_TEST_NOW,
            )
            assert rc == 1


# ===========================================================================
# AG54: next_required_task points at TASK-014AH
# ===========================================================================

class TestAG54NextTaskIs014AH:
    def test_next_required_task(self):
        r = _run()
        assert r.next_required_task == "TASK-014AH_guarded_tiny_lifecycle_dry_run_summary"

    def test_next_required_task_under_approval(self):
        r = _run(allow_cleanup_dry_run_approval=True)
        assert r.next_required_task == "TASK-014AH_guarded_tiny_lifecycle_dry_run_summary"

    def test_next_required_task_under_guard(self):
        r = _run(allow_real_cleanup_execution=True)
        assert r.next_required_task == "TASK-014AH_guarded_tiny_lifecycle_dry_run_summary"


# ===========================================================================
# AG55: upstream status echoes
# ===========================================================================

class TestAG55UpstreamStatusEchoes:
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

    def test_guarded_stop_adapter_status_echo(self):
        r = _run()
        assert r.upstream_guarded_stop_adapter_status == (
            "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY"
        )


# ===========================================================================
# AG56: status precedence (hard-fail beats approval/guard; guard beats approval)
# ===========================================================================

class TestAG56StatusPrecedence:
    def test_hard_fail_beats_approval(self):
        r = _run(readonly=None, allow_cleanup_dry_run_approval=True)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED

    def test_hard_fail_beats_execution_guard(self):
        r = _run(guarded_stop_adapter=None, allow_real_cleanup_execution=True)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED

    def test_guard_beats_approval(self):
        r = _run(allow_cleanup_dry_run_approval=True,
                 allow_real_cleanup_execution=True)
        assert r.status == STATUS_REAL_CLEANUP_NOT_IMPL
        assert r.mode == MODE_REAL_CLEANUP_EXECUTION_GUARD


# ===========================================================================
# AG57: acceptable status whitelists
# ===========================================================================

class TestAG57AcceptableWhitelists:
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

    def test_guarded_stop_adapter_three(self):
        assert len(ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES) == 3
        assert "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY" in (
            ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES
        )


# ===========================================================================
# AG58: existing 5 positions never touched even with all flags set
# ===========================================================================

class TestAG58ExistingPositionsNotTouched:
    def test_default(self):
        r = _run()
        assert r.existing_positions_touched == []
        assert set(r.existing_position_symbols) == set(EXISTING_POSITION_SYMBOLS)

    def test_with_approval(self):
        r = _run(allow_cleanup_dry_run_approval=True)
        assert r.existing_positions_touched == []

    def test_with_real_execution_guard(self):
        r = _run(allow_real_cleanup_execution=True)
        assert r.existing_positions_touched == []


# ===========================================================================
# AG59: blocked_gates deduplicated
# ===========================================================================

class TestAG59BlockedGatesDeduped:
    def test_no_duplicates(self):
        r = _run()
        assert len(r.blocked_gates) == len(set(r.blocked_gates))


# ===========================================================================
# AG60: 8 required confirmation flags (exact values)
# ===========================================================================

class TestAG60RequiredConfirmationFlags:
    def test_eight_flags(self):
        assert len(REQUIRED_CONFIRMATION_FLAGS) == 8

    def test_specific_flags(self):
        assert "--i-understand-this-is-demo-real-execution" in REQUIRED_CONFIRMATION_FLAGS
        assert any("--max-notional-usdt" in f for f in REQUIRED_CONFIRMATION_FLAGS)
        assert any("--expected-existing-position-count" in f for f in REQUIRED_CONFIRMATION_FLAGS)
        assert any("--expected-existing-symbols" in f for f in REQUIRED_CONFIRMATION_FLAGS)
        assert any("--expected-cleanup-symbol" in f for f in REQUIRED_CONFIRMATION_FLAGS)
        assert any("--expected-cleanup-qty" in f for f in REQUIRED_CONFIRMATION_FLAGS)
        assert any("--expected-cleanup-side" in f for f in REQUIRED_CONFIRMATION_FLAGS)
        assert any("--expected-reduce-only" in f for f in REQUIRED_CONFIRMATION_FLAGS)

    def test_max_notional_value(self):
        assert "--max-notional-usdt 10" in REQUIRED_CONFIRMATION_FLAGS

    def test_expected_position_count(self):
        assert "--expected-existing-position-count 5" in REQUIRED_CONFIRMATION_FLAGS

    def test_expected_cleanup_symbol(self):
        assert "--expected-cleanup-symbol SOLUSDT" in REQUIRED_CONFIRMATION_FLAGS

    def test_expected_cleanup_qty(self):
        assert "--expected-cleanup-qty 0.1" in REQUIRED_CONFIRMATION_FLAGS

    def test_expected_cleanup_side(self):
        assert "--expected-cleanup-side Sell" in REQUIRED_CONFIRMATION_FLAGS

    def test_expected_reduce_only(self):
        assert "--expected-reduce-only true" in REQUIRED_CONFIRMATION_FLAGS


# ===========================================================================
# AG61: demo endpoint allowlist + live denylist
# ===========================================================================

class TestAG61EndpointAllowlistDenylist:
    def test_constants(self):
        assert DEMO_ENDPOINT_ALLOWLIST == ("https://api-demo.bybit.com",)
        assert BASE_URL_DEMO_REF == "https://api-demo.bybit.com"
        assert BASE_URL_LIVE_REF == "https://api.bybit.com"

    def test_envelope_surfaced(self):
        r = _run()
        e = r.cleanup_request_envelope
        assert "https://api-demo.bybit.com" in e["demo_endpoint_allowlist"]
        assert "https://api.bybit.com" in e["live_endpoint_denylist"]


# ===========================================================================
# AG62: real_execution_allowed always False regardless of any flag combo
# ===========================================================================

class TestAG62RealExecutionAllowedAlwaysFalse:
    @pytest.mark.parametrize("approval,guard", [
        (False, False), (True, False), (False, True), (True, True),
    ])
    def test_always_false(self, approval, guard):
        r = _run(allow_cleanup_dry_run_approval=approval,
                 allow_real_cleanup_execution=guard)
        assert r.real_execution_allowed is False
        assert r.real_cleanup_implemented is False
        assert r.current_task_real_execution_allowed is False


# ===========================================================================
# AG63: hard-fail set has at least 24 gates
# ===========================================================================

class TestAG63HardFailGatesCount:
    def test_at_least_twenty_four(self):
        from src.demo_tiny_guarded_cleanup_dry_run_adapter import (
            _HARD_FAIL_GATES,
        )
        assert len(_HARD_FAIL_GATES) >= 24


# ===========================================================================
# AG64: stage_order == ALL_STAGES (9 stages in order)
# ===========================================================================

class TestAG64StageOrder:
    def test_order(self):
        r = _run()
        assert r.stage_order == [
            STAGE_0_ARTIFACT_PREFLIGHT, STAGE_1_CLEANUP_ADAPTER_SCOPE,
            STAGE_2_CLEANUP_PRECONDITION_CONTRACT,
            STAGE_3_MANUAL_CONFIRMATION_DRY_RUN_CONTRACT,
            STAGE_4_CLEANUP_REQUEST_ENVELOPE_DRY_RUN,
            STAGE_5_CLEANUP_READONLY_VERIFICATION_PLAN,
            STAGE_6_CLEANUP_FAILURE_POLICY,
            STAGE_7_AUDIT_ARTIFACT_GENERATION,
            STAGE_8_FINAL_CLEANUP_ADAPTER_VERDICT,
        ]
        assert len(r.stage_order) == 9


# ===========================================================================
# AG65: 14-artifact preflight contract - all 14 must be present
# ===========================================================================

class TestAG6514ArtifactPreflightContract:
    @pytest.mark.parametrize("kw", [
        {"readonly": None}, {"recon": None}, {"protection": None},
        {"contract": None}, {"noop_plan": None}, {"lifecycle": None},
        {"real_permission_gate": None},
        {"tiny_cleanup_permission_gate": None},
        {"lifecycle_summary": None}, {"runner_design": None},
        {"runner_dry_run": None},
        {"guarded_design_review": None},
        {"guarded_entry_adapter": None},
        {"guarded_stop_adapter": None},
    ])
    def test_each_missing_fails_closed(self, kw):
        r = _run(**kw)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert r.failed_stage == STAGE_0_ARTIFACT_PREFLIGHT


# ===========================================================================
# AG66: stage_8 final cleanup adapter verdict mirrors result.status / mode
# ===========================================================================

class TestAG66Stage8MirrorsResult:
    def test_status_match(self):
        r = _run()
        v = r.stages[STAGE_8_FINAL_CLEANUP_ADAPTER_VERDICT]["final_cleanup_adapter_verdict"]
        assert v["status"] == r.status
        assert v["mode"] == r.mode

    def test_status_match_approval(self):
        r = _run(allow_cleanup_dry_run_approval=True)
        v = r.stages[STAGE_8_FINAL_CLEANUP_ADAPTER_VERDICT]["final_cleanup_adapter_verdict"]
        assert v["status"] == r.status
        assert v["mode"] == r.mode

    def test_status_match_guard(self):
        r = _run(allow_real_cleanup_execution=True)
        v = r.stages[STAGE_8_FINAL_CLEANUP_ADAPTER_VERDICT]["final_cleanup_adapter_verdict"]
        assert v["status"] == r.status
        assert v["mode"] == r.mode


# ===========================================================================
# AG67: live URL never surfaces in envelope allowlist;
#       readiness_conclusion never READY_TO_EXECUTE;
#       alternate guarded review / entry / stop adapter statuses accepted.
# ===========================================================================

class TestAG67ReadinessAndAllowlistInvariants:
    def test_live_url_demo_only(self):
        r = _run()
        e = r.cleanup_request_envelope
        assert BASE_URL_LIVE_REF not in e["demo_endpoint_allowlist"]
        assert BASE_URL_LIVE_REF in e["live_endpoint_denylist"]

    def test_readiness_default(self):
        r = _run()
        assert r.readiness_conclusion == "DESIGN_REVIEW_READY_NOT_EXECUTABLE"
        assert r.readiness_conclusion != "READY_TO_EXECUTE"

    def test_readiness_with_approval(self):
        r = _run(allow_cleanup_dry_run_approval=True)
        assert r.readiness_conclusion == "DESIGN_REVIEW_READY_NOT_EXECUTABLE"

    def test_readiness_with_real_guard(self):
        r = _run(allow_real_cleanup_execution=True)
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

    def test_guarded_stop_adapter_execution_disabled_status_accepted(self):
        ada = _valid_guarded_stop_adapter()
        ada["status"] = "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED"
        r = _run(guarded_stop_adapter=ada)
        assert r.status == STATUS_ADAPTER_READY

    def test_guarded_stop_adapter_not_impl_status_accepted(self):
        ada = _valid_guarded_stop_adapter()
        ada["status"] = "REAL_STOP_ATTACH_EXECUTION_NOT_IMPLEMENTED"
        r = _run(guarded_stop_adapter=ada)
        assert r.status == STATUS_ADAPTER_READY


# ===========================================================================
# AG68: dryrun orderLinkId prefix invariant + cleanup token references
# ===========================================================================

class TestAG68DryrunOrderLinkIdPrefix:
    def test_prefix_constant(self):
        assert DRYRUN_ORDER_LINK_ID_PREFIX.startswith("DRYRUN_TINY_CLEANUP_")

    def test_envelope_uses_prefix(self):
        r = _run()
        e = r.cleanup_request_envelope
        assert e["orderLinkId_prefix"] == DRYRUN_ORDER_LINK_ID_PREFIX
        assert e["orderLinkId_example"].startswith("DRYRUN_TINY_CLEANUP_")
        assert "SOLUSDT" in e["orderLinkId_example"]
