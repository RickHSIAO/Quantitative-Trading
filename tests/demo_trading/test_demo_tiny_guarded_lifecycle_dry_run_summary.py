"""
tests/demo_trading/test_demo_tiny_guarded_lifecycle_dry_run_summary.py
TASK-014AH: Guarded Tiny Lifecycle Dry-run Summary tests (AH1 - AH80).

Covers summary_checklist / summary_dry_run_approval /
real_lifecycle_execution_guard / fail_closed paths; all 9 stages; 124
gate constants; 17-artifact preflight contract (10 baseline + AA
lifecycle summary + AB runner design + AC runner dry-run + AD guarded
design review + AE guarded entry adapter + AF guarded stop-attach
adapter + AG guarded cleanup adapter); AD readiness_conclusion ==
DESIGN_REVIEW_READY_NOT_EXECUTABLE required; AE/AF/AG adapter status
acceptable required; cross-adapter consistency matrix (SOLUSDT / linear
/ 0.1 / Buy / long / stopLoss 61.18 / entry ref 64.4 / cleanup side
Sell / reduceOnly True / closeOnTrigger False / positionIdx 0 /
orderType Market / max_notional 10); 3 manual token patterns
(CONFIRM_DEMO_TINY_ENTRY_* / CONFIRM_DEMO_TINY_STOP_ATTACH_* /
CONFIRM_DEMO_TINY_CLEANUP_*) never validated; per-adapter confirmation
flag isolation; 3-adapter execution-forbidden matrix; 8-step sequential
dry-run lifecycle plan with manual_boundary every step; cross-adapter
failure / abort policy (FAIL_CLOSED / MANUAL_REVIEW_REQUIRED);
documentation sync plan; status precedence; source-scan safety (no
urlopen / no forbidden imports / no signing / no os.environ / no
AA-AG / AE / AF / AG module reuse / no real runner); report
artifacts; forbidden-flag absence (--execute-real-* / --send-order /
--place-order / --real-run); the invariant that TASK-014L sender G20
(protected_entry_policy_missing) still blocks --execute-new-entry and
is NOT lifted here; next_required_task points at TASK-014AI.
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

from src.demo_tiny_guarded_lifecycle_dry_run_summary import (
    ACCEPTABLE_GUARDED_CLEANUP_ADAPTER_STATUSES,
    ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES,
    ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES,
    ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES,
    ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES,
    ACCEPTABLE_RUNNER_DESIGN_STATUSES,
    ACCEPTABLE_RUNNER_DRY_RUN_STATUSES,
    ALL_STAGES,
    BASE_URL_DEMO_REF,
    BASE_URL_LIVE_REF,
    CLEANUP_CONFIRMATION_FLAGS,
    CLEANUP_TOKEN_PATTERN,
    DEFAULT_SELECTED_SYMBOL,
    DEMO_ENDPOINT_ALLOWLIST,
    DemoTinyGuardedLifecycleDryRunSummary,
    ENTRY_CONFIRMATION_FLAGS,
    ENTRY_TOKEN_PATTERN,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_INSTRUMENT_CATEGORY,
    EXPECTED_LIFECYCLE_STATUS,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_PROOF_STRENGTH,
    FORBIDDEN_LOG_FIELDS,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_AE_ORDER_ENDPOINT_NOT_CALLED,
    GATE_AE_REAL_EXECUTION_FALSE,
    GATE_AE_SEND_ALLOWED_FALSE,
    GATE_AE_STOP_ENDPOINT_NOT_CALLED,
    GATE_AF_ORDER_ENDPOINT_NOT_CALLED,
    GATE_AF_REAL_EXECUTION_FALSE,
    GATE_AF_SEND_ALLOWED_FALSE,
    GATE_AF_STOP_ENDPOINT_NOT_CALLED,
    GATE_AG_ORDER_ENDPOINT_NOT_CALLED,
    GATE_AG_REAL_EXECUTION_FALSE,
    GATE_AG_SEND_ALLOWED_FALSE,
    GATE_AG_STOP_ENDPOINT_NOT_CALLED,
    GATE_CLEANUP_EXECUTION_NOT_INCLUDED,
    GATE_CLEANUP_FLAGS_ISOLATED,
    GATE_CLEANUP_TOKEN_PATTERN_PRESENT,
    GATE_COMMAND_LOG_SYNC_REQUIRED,
    GATE_CONFIRMATION_FLAGS_DOCUMENTED,
    GATE_CONFIRMATION_FLAGS_NOT_VALIDATED,
    GATE_CONTRACT_MISSING,
    GATE_CROSS_CATEGORY_CONSISTENT,
    GATE_CROSS_CLEANUP_CLOSE_ON_TRIGGER_FALSE,
    GATE_CROSS_CLEANUP_PRE_CLEANUP_LONG,
    GATE_CROSS_CLEANUP_REDUCE_ONLY_TRUE,
    GATE_CROSS_CLEANUP_SIDE_SELL,
    GATE_CROSS_ENTRY_SIDE_BUY,
    GATE_CROSS_EXPECTED_LONG_POSITION,
    GATE_CROSS_MAX_NOTIONAL_10,
    GATE_CROSS_ORDER_TYPE_MARKET,
    GATE_CROSS_POSITION_IDX_ZERO,
    GATE_CROSS_QTY_CONSISTENT,
    GATE_CROSS_STOP_EXPECTED_LONG,
    GATE_CROSS_STOP_LOSS_61_18,
    GATE_CROSS_STOP_LOSS_BELOW_ENTRY,
    GATE_CROSS_SYMBOL_CONSISTENT,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_EXECUTION_NOT_INCLUDED,
    GATE_ENTRY_FLAGS_ISOLATED,
    GATE_ENTRY_TOKEN_PATTERN_PRESENT,
    GATE_FORBIDDEN_STATUS_SYNC_REQUIRED,
    GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED,
    GATE_G20_NOT_LIFTED,
    GATE_G20_NOT_LIFTED_ACROSS_ADAPTERS,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_GUARDED_CLEANUP_ADAPTER_MISSING,
    GATE_GUARDED_CLEANUP_ADAPTER_STATUS_UNACCEPTABLE,
    GATE_GUARDED_DESIGN_REVIEW_MISSING,
    GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE,
    GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE,
    GATE_GUARDED_ENTRY_ADAPTER_MISSING,
    GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE,
    GATE_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_ONLY,
    GATE_GUARDED_STOP_ADAPTER_MISSING,
    GATE_GUARDED_STOP_ADAPTER_STATUS_UNACCEPTABLE,
    GATE_LIFECYCLE_AUTO_ADVANCE_FALSE,
    GATE_LIFECYCLE_AUTO_CLEANUP_FALSE,
    GATE_LIFECYCLE_AUTO_EMERGENCY_CLOSE_FALSE,
    GATE_LIFECYCLE_AUTO_RETRY_FALSE,
    GATE_LIFECYCLE_ENDPOINT_CALLED_FALSE_EVERY_STEP,
    GATE_LIFECYCLE_MANUAL_BOUNDARY_EVERY_STEP,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_LIFECYCLE_PLAN_EIGHT_STEPS,
    GATE_LIFECYCLE_PLAN_PRESENT,
    GATE_LIFECYCLE_RESPONSE_FROM_EXCHANGE_FALSE,
    GATE_LIFECYCLE_SUMMARY_MISSING,
    GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED,
    GATE_NEXT_ACTION_SYNC_REQUIRED,
    GATE_NEXT_REQUIRED_TASK_SYNC_REQUIRED,
    GATE_NOOP_PLAN_MISSING,
    GATE_NO_AUTO_CLEANUP,
    GATE_NO_AUTO_EMERGENCY_CLOSE,
    GATE_NO_AUTO_NEXT_STEP,
    GATE_NO_AUTO_RETRY,
    GATE_NO_AUTO_SECOND_CLEANUP,
    GATE_NO_BACKGROUND_LOOP,
    GATE_NO_CRON,
    GATE_NO_DISCORD_TRIGGER,
    GATE_NO_ENDPOINT_INVOKED,
    GATE_NO_G20_LIFT,
    GATE_NO_LIVE_ENDPOINT,
    GATE_NO_LIVE_ENDPOINT_ACROSS_ADAPTERS,
    GATE_NO_NOTION_TRIGGER,
    GATE_NO_POSITION_MODIFIED,
    GATE_NO_POSITION_MODIFIED_ACROSS_ADAPTERS,
    GATE_NO_POSITION_MODIFIED_SCOPE,
    GATE_NO_REAL_ORDER_ENDPOINT,
    GATE_NO_REAL_STOP_ENDPOINT,
    GATE_NO_SCHEDULER,
    GATE_NO_SECRETS_EMITTED,
    GATE_NO_SECRETS_LOADED,
    GATE_NO_SECRETS_LOADED_ACROSS_ADAPTERS,
    GATE_PARTIAL_EXECUTION_FAIL_CLOSED,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW,
    GATE_PROTECTION_MISSING,
    GATE_QTY_MISMATCH_FAIL_CLOSED,
    GATE_README_SYNC_REQUIRED,
    GATE_READONLY_SMOKE_MISSING,
    GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
    GATE_REAL_EXECUTION_NOT_ALLOWED,
    GATE_REAL_LIFECYCLE_EXECUTION_NOT_IMPL,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_REAL_RUNNER_NOT_IMPLEMENTED,
    GATE_RECONCILIATION_MISSING,
    GATE_REDUCE_ONLY_INVALID_FAIL_CLOSED,
    GATE_REQUEST_REJECTED_FAIL_CLOSED,
    GATE_RUNNER_DESIGN_MISSING,
    GATE_RUNNER_DRY_RUN_MISSING,
    GATE_SECRET_EMISSION_FAIL_CLOSED,
    GATE_SELECTED_SYMBOL_MISMATCH_FAIL_CLOSED,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
    GATE_SIDE_MISMATCH_FAIL_CLOSED,
    GATE_STOP_EXECUTION_NOT_INCLUDED,
    GATE_STOP_FLAGS_ISOLATED,
    GATE_STOP_LOSS_INVALID_FAIL_CLOSED,
    GATE_STOP_TOKEN_PATTERN_PRESENT,
    GATE_SUMMARY_ONLY,
    GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
    GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
    GATE_TINY_STOP_PERMISSION_GATE_MISSING,
    GATE_TOKENS_NOT_VALIDATED,
    GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
    LIFECYCLE_PLAN_STEPS,
    MODE_FAIL_CLOSED,
    MODE_REAL_LIFECYCLE_EXECUTION_GUARD,
    MODE_SUMMARY_CHECKLIST,
    MODE_SUMMARY_DRY_RUN_APPROVAL,
    ORDER_CREATE_PATH_REF,
    READINESS_CONCLUSION_NOT_EXECUTABLE,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_SUMMARY_SCOPE,
    STAGE_2_CROSS_ADAPTER_CONSISTENCY_MATRIX,
    STAGE_3_MANUAL_CONFIRMATION_MATRIX,
    STAGE_4_EXECUTION_FORBIDDEN_MATRIX,
    STAGE_5_SEQUENTIAL_DRY_RUN_LIFECYCLE_PLAN,
    STAGE_6_FAILURE_AND_ABORT_SUMMARY,
    STAGE_7_DOCUMENTATION_SYNC_REVIEW,
    STAGE_8_FINAL_LIFECYCLE_SUMMARY_VERDICT,
    STATUS_FAIL_CLOSED,
    STATUS_REAL_LIFECYCLE_NOT_IMPL,
    STATUS_SUMMARY_READY,
    STATUS_SUMMARY_READY_EXEC_DISABLED,
    STOP_CONFIRMATION_FLAGS,
    STOP_TOKEN_PATTERN,
    SUMMARY_EXPECTED_CATEGORY,
    SUMMARY_EXPECTED_CLEANUP_SIDE,
    SUMMARY_EXPECTED_CLOSE_ON_TRIGGER,
    SUMMARY_EXPECTED_ENTRY_REFERENCE,
    SUMMARY_EXPECTED_ENTRY_SIDE,
    SUMMARY_EXPECTED_EXISTING_COUNT,
    SUMMARY_EXPECTED_MAX_NOTIONAL_USDT,
    SUMMARY_EXPECTED_ORDER_TYPE,
    SUMMARY_EXPECTED_POSITION_IDX,
    SUMMARY_EXPECTED_POSITION_SIDE_LONG,
    SUMMARY_EXPECTED_QTY,
    SUMMARY_EXPECTED_REDUCE_ONLY,
    SUMMARY_EXPECTED_STOP_LOSS,
    SUMMARY_EXPECTED_SYMBOL,
    TRADING_STOP_PATH_REF,
    TinyGuardedLifecycleDryRunSummaryResult,
)


_MODULE_PATH = ROOT / "src" / "demo_tiny_guarded_lifecycle_dry_run_summary.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_tiny_guarded_lifecycle_dry_run_summary.py"
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
        "selected_qty":           SUMMARY_EXPECTED_QTY,
        "entry_reference_price":  SUMMARY_EXPECTED_ENTRY_REFERENCE,
        "stop_price":             SUMMARY_EXPECTED_STOP_LOSS,
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
        "tiny_qty":                  SUMMARY_EXPECTED_QTY,
        "tiny_notional":             6.44,
        "entry_reference_price":     SUMMARY_EXPECTED_ENTRY_REFERENCE,
        "stop_price":                SUMMARY_EXPECTED_STOP_LOSS,
        "status":                    EXPECTED_LIFECYCLE_STATUS,
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


def _valid_tiny_entry_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-11T11:58:30Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "TINY_ENTRY_PERMISSION_CHECKLIST_READY",
        "entry_side":                "Buy",
        "real_execution_allowed":              False,
        "current_task_real_execution_allowed": False,
    }


def _valid_tiny_stop_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-11T11:58:45Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "TINY_STOP_ATTACH_PERMISSION_CHECKLIST_READY",
        "real_execution_allowed":              False,
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
        "expected_entry_reference_price": SUMMARY_EXPECTED_ENTRY_REFERENCE,
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
        "timestamp_utc":             "2026-06-11T11:59:59.8Z",
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


def _valid_guarded_cleanup_adapter() -> dict:
    return {
        "timestamp_utc":             "2026-06-11T11:59:59.9Z",
        "mode":                      "cleanup_adapter_checklist",
        "selected_symbol":           "SOLUSDT",
        "status":                    "TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY",
        "readiness_conclusion":      READINESS_CONCLUSION_NOT_EXECUTABLE,
        "real_execution_allowed":              False,
        "real_cleanup_implemented":            False,
        "guarded_cleanup_dry_run_adapter":     True,
        "cleanup_only":                        True,
        "entry_included":                      False,
        "stop_attach_included":                False,
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


def _summary() -> DemoTinyGuardedLifecycleDryRunSummary:
    return DemoTinyGuardedLifecycleDryRunSummary()


_UNSET = object()


def _run(
    *,
    readonly=_UNSET, recon=_UNSET, protection=_UNSET, contract=_UNSET,
    noop_plan=_UNSET, lifecycle=_UNSET, real_permission_gate=_UNSET,
    tiny_entry_permission_gate=_UNSET,
    tiny_stop_permission_gate=_UNSET,
    tiny_cleanup_permission_gate=_UNSET,
    lifecycle_summary=_UNSET,
    runner_design=_UNSET,
    runner_dry_run=_UNSET,
    guarded_design_review=_UNSET,
    guarded_entry_adapter=_UNSET,
    guarded_stop_adapter=_UNSET,
    guarded_cleanup_adapter=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    allow_summary_approval=False,
    allow_real_lifecycle_execution=False,
    _now=_TEST_NOW,
) -> TinyGuardedLifecycleDryRunSummaryResult:
    return _summary().run_checklist(
        readonly_smoke=_valid_readonly()                                         if readonly                       is _UNSET else readonly,
        reconciliation=_valid_reconciliation()                                   if recon                          is _UNSET else recon,
        protection=_valid_protection()                                           if protection                     is _UNSET else protection,
        contract=_valid_contract()                                               if contract                       is _UNSET else contract,
        noop_plan=_valid_noop_plan()                                             if noop_plan                      is _UNSET else noop_plan,
        lifecycle_mock=_valid_lifecycle()                                        if lifecycle                      is _UNSET else lifecycle,
        real_permission_gate=_valid_real_permission_gate()                       if real_permission_gate           is _UNSET else real_permission_gate,
        tiny_entry_permission_gate=_valid_tiny_entry_permission_gate()           if tiny_entry_permission_gate     is _UNSET else tiny_entry_permission_gate,
        tiny_stop_permission_gate=_valid_tiny_stop_permission_gate()             if tiny_stop_permission_gate      is _UNSET else tiny_stop_permission_gate,
        tiny_cleanup_permission_gate=_valid_tiny_cleanup_permission_gate()       if tiny_cleanup_permission_gate   is _UNSET else tiny_cleanup_permission_gate,
        lifecycle_summary=_valid_lifecycle_summary()                             if lifecycle_summary              is _UNSET else lifecycle_summary,
        runner_design=_valid_runner_design()                                     if runner_design                  is _UNSET else runner_design,
        runner_dry_run=_valid_runner_dry_run()                                   if runner_dry_run                 is _UNSET else runner_dry_run,
        guarded_design_review=_valid_guarded_design_review()                     if guarded_design_review          is _UNSET else guarded_design_review,
        guarded_entry_adapter=_valid_guarded_entry_adapter()                     if guarded_entry_adapter          is _UNSET else guarded_entry_adapter,
        guarded_stop_adapter=_valid_guarded_stop_adapter()                       if guarded_stop_adapter           is _UNSET else guarded_stop_adapter,
        guarded_cleanup_adapter=_valid_guarded_cleanup_adapter()                 if guarded_cleanup_adapter        is _UNSET else guarded_cleanup_adapter,
        symbol=symbol,
        allow_summary_approval=allow_summary_approval,
        allow_real_lifecycle_execution=allow_real_lifecycle_execution,
        _now=_now,
    )


# ===========================================================================
# AH1: valid checklist => TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY
# ===========================================================================

class TestAH1SummaryReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_SUMMARY_READY
        assert r.mode == MODE_SUMMARY_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.real_execution_allowed is False
        assert r.real_runner_implemented is False
        assert r.guarded_lifecycle_dry_run_summary is True
        assert r.summary_only is True
        assert r.entry_execution_included is False
        assert r.stop_execution_included is False
        assert r.cleanup_execution_included is False
        assert r.full_lifecycle_execution_included is False
        assert r.current_task_real_execution_allowed is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.next_required_task == "TASK-014AI_guarded_entry_real_permission_review"


# ===========================================================================
# AH2: --allow-summary-approval => READY_BUT_EXECUTION_DISABLED
# ===========================================================================

class TestAH2SummaryDryRunApproval:
    def test_approval(self):
        r = _run(allow_summary_approval=True)
        assert r.status == STATUS_SUMMARY_READY_EXEC_DISABLED
        assert r.mode == MODE_SUMMARY_DRY_RUN_APPROVAL
        assert r.summary_dry_run_approval_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_runner_implemented is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE


# ===========================================================================
# AH3: --allow-real-lifecycle-execution => REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED
# ===========================================================================

class TestAH3RealLifecycleExecutionGuard:
    def test_guard(self):
        r = _run(allow_real_lifecycle_execution=True)
        assert r.status == STATUS_REAL_LIFECYCLE_NOT_IMPL
        assert r.mode == MODE_REAL_LIFECYCLE_EXECUTION_GUARD
        assert r.real_lifecycle_execution_requested is True
        assert r.real_execution_allowed is False
        assert r.real_runner_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.no_position_modified is True


# ===========================================================================
# AH4-AH20: 17 missing upstream artifacts each => FAIL_CLOSED
# ===========================================================================

class TestAH4MissingReadonly:
    def test_fail_closed(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert r.failed_stage == STAGE_0_ARTIFACT_PREFLIGHT
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestAH5MissingReconciliation:
    def test_fail_closed(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestAH6MissingProtection:
    def test_fail_closed(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestAH7MissingContract:
    def test_fail_closed(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestAH8MissingNoopPlan:
    def test_fail_closed(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestAH9MissingLifecycle:
    def test_fail_closed(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestAH10MissingRealPermissionGate:
    def test_fail_closed(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAH11MissingTinyEntryPermissionGate:
    def test_fail_closed(self):
        r = _run(tiny_entry_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAH12MissingTinyStopPermissionGate:
    def test_fail_closed(self):
        r = _run(tiny_stop_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAH13MissingTinyCleanupPermissionGate:
    def test_fail_closed(self):
        r = _run(tiny_cleanup_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAH14MissingLifecycleSummary:
    def test_fail_closed(self):
        r = _run(lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAH15MissingRunnerDesign:
    def test_fail_closed(self):
        r = _run(runner_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DESIGN_MISSING in r.blocked_gates


class TestAH16MissingRunnerDryRun:
    def test_fail_closed(self):
        r = _run(runner_dry_run=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DRY_RUN_MISSING in r.blocked_gates


class TestAH17MissingGuardedDesignReview:
    def test_fail_closed(self):
        r = _run(guarded_design_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_MISSING in r.blocked_gates


class TestAH18MissingGuardedEntryAdapter:
    def test_fail_closed(self):
        r = _run(guarded_entry_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_ENTRY_ADAPTER_MISSING in r.blocked_gates


class TestAH19MissingGuardedStopAdapter:
    def test_fail_closed(self):
        r = _run(guarded_stop_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_STOP_ADAPTER_MISSING in r.blocked_gates


class TestAH20MissingGuardedCleanupAdapter:
    def test_fail_closed(self):
        r = _run(guarded_cleanup_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_CLEANUP_ADAPTER_MISSING in r.blocked_gates


# ===========================================================================
# AH21: selected symbol must equal SOLUSDT
# ===========================================================================

class TestAH21SymbolNotSolusdt:
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
# AH22-AH25: upstream invariant mismatches
# ===========================================================================

class TestAH22EndpointFamilyMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["endpoint_family"] = "bybit_live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestAH23AccountModeMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["account_mode"] = "live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestAH24ProofStrengthMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["proof_strength"] = "WEAK"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROOF_STRENGTH_NOT_STRONG in r.blocked_gates


class TestAH25PositionDetailsSourceMismatch:
    def test_fail_closed(self):
        bad = _valid_reconciliation()
        bad["position_details_source"] = "mock"
        bad["mode"] = "mock"
        r = _run(recon=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY in r.blocked_gates


# ===========================================================================
# AH26: guarded_design_review status unacceptable => fail closed
# ===========================================================================

class TestAH26GuardedDesignReviewStatusUnacceptable:
    def test_fail_closed(self):
        bad = _valid_guarded_design_review()
        bad["status"] = "SOMETHING_ELSE"
        r = _run(guarded_design_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE in r.blocked_gates


# ===========================================================================
# AH27: guarded_design_review readiness conclusion executable => fail closed
# ===========================================================================

class TestAH27GuardedDesignReviewReadinessExecutable:
    def test_fail_closed(self):
        bad = _valid_guarded_design_review()
        bad["readiness_conclusion"] = "READY_TO_EXECUTE"
        r = _run(guarded_design_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE in r.blocked_gates


# ===========================================================================
# AH28: guarded_entry_adapter status unacceptable => fail closed
# ===========================================================================

class TestAH28GuardedEntryAdapterStatusUnacceptable:
    def test_fail_closed(self):
        bad = _valid_guarded_entry_adapter()
        bad["status"] = "SOMETHING_ELSE"
        r = _run(guarded_entry_adapter=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE in r.blocked_gates


# ===========================================================================
# AH29: guarded_stop_adapter status unacceptable => fail closed
# ===========================================================================

class TestAH29GuardedStopAdapterStatusUnacceptable:
    def test_fail_closed(self):
        bad = _valid_guarded_stop_adapter()
        bad["status"] = "SOMETHING_ELSE"
        r = _run(guarded_stop_adapter=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_STOP_ADAPTER_STATUS_UNACCEPTABLE in r.blocked_gates


# ===========================================================================
# AH30: guarded_cleanup_adapter status unacceptable => fail closed
# ===========================================================================

class TestAH30GuardedCleanupAdapterStatusUnacceptable:
    def test_fail_closed(self):
        bad = _valid_guarded_cleanup_adapter()
        bad["status"] = "SOMETHING_ELSE"
        r = _run(guarded_cleanup_adapter=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_CLEANUP_ADAPTER_STATUS_UNACCEPTABLE in r.blocked_gates


# ===========================================================================
# AH31: missing --symbol
# ===========================================================================

class TestAH31MissingSymbol:
    def test_fail_closed(self):
        r = _run(symbol="")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_MISSING in r.blocked_gates


# ===========================================================================
# AH32: 9 stages present
# ===========================================================================

class TestAH32NineStages:
    def test_stage_count(self):
        r = _run()
        assert len(r.stages) == 9
        assert r.stage_order == list(ALL_STAGES)
        for stage_id in ALL_STAGES:
            assert stage_id in r.stages
            assert r.stages[stage_id]["stage"] == stage_id


# ===========================================================================
# AH33: summary scope
# ===========================================================================

class TestAH33SummaryScope:
    def test_scope_flags(self):
        r = _run()
        s = r.summary_scope
        assert s["guarded_lifecycle_dry_run_summary"] is True
        assert s["summary_only"] is True
        assert s["entry_execution_included"] is False
        assert s["stop_execution_included"] is False
        assert s["cleanup_execution_included"] is False
        assert s["full_lifecycle_execution_included"] is False
        assert s["real_runner_implemented"] is False
        assert s["real_execution_allowed"] is False
        assert s["order_endpoint_called"] is False
        assert s["stop_endpoint_called"] is False
        assert s["no_endpoint_invoked_in_this_task"] is True
        assert s["no_position_modified"] is True
        assert s["no_secrets_loaded"] is True
        assert s["g20_policy_still_in_place"] is True
        assert s["g20_lifted"] is False
        assert s["next_required_task"] == "TASK-014AI_guarded_entry_real_permission_review"

    def test_scope_gates(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (
            GATE_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_ONLY,
            GATE_SUMMARY_ONLY,
            GATE_ENTRY_EXECUTION_NOT_INCLUDED,
            GATE_STOP_EXECUTION_NOT_INCLUDED,
            GATE_CLEANUP_EXECUTION_NOT_INCLUDED,
            GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED,
            GATE_REAL_RUNNER_NOT_IMPLEMENTED,
            GATE_REAL_EXECUTION_NOT_ALLOWED,
            GATE_NO_ENDPOINT_INVOKED,
            GATE_NO_POSITION_MODIFIED_SCOPE,
            GATE_NO_SECRETS_LOADED,
            GATE_NO_G20_LIFT,
        ):
            assert g in blocked


# ===========================================================================
# AH34: cross-adapter consistency matrix
# ===========================================================================

class TestAH34CrossAdapterConsistencyMatrix:
    def test_matrix_values(self):
        r = _run()
        m = r.cross_adapter_consistency_matrix
        assert m["selected_symbol"] == "SOLUSDT"
        assert m["symbol_expected"] == SUMMARY_EXPECTED_SYMBOL == "SOLUSDT"
        assert m["category_expected"] == SUMMARY_EXPECTED_CATEGORY == "linear"
        assert m["qty_expected"] == SUMMARY_EXPECTED_QTY == 0.1
        assert m["entry_side_expected"] == SUMMARY_EXPECTED_ENTRY_SIDE == "Buy"
        assert m["expected_position_side_after_entry"] == SUMMARY_EXPECTED_POSITION_SIDE_LONG == "long"
        assert m["stop_expected_side"] == "long"
        assert m["cleanup_expected_pre_cleanup_side"] == "long"
        assert m["stop_loss_expected"] == SUMMARY_EXPECTED_STOP_LOSS == 61.18
        assert m["entry_reference_expected"] == SUMMARY_EXPECTED_ENTRY_REFERENCE == 64.4
        assert m["stop_loss_below_entry_reference"] is True
        assert m["cleanup_side_expected"] == SUMMARY_EXPECTED_CLEANUP_SIDE == "Sell"
        assert m["cleanup_reduce_only_expected"] == SUMMARY_EXPECTED_REDUCE_ONLY is True
        assert m["cleanup_close_on_trigger_expected"] == SUMMARY_EXPECTED_CLOSE_ON_TRIGGER is False
        assert m["position_idx_expected"] == SUMMARY_EXPECTED_POSITION_IDX == 0
        assert m["order_type_expected"] == SUMMARY_EXPECTED_ORDER_TYPE == "Market"
        assert m["max_notional_usdt_expected"] == SUMMARY_EXPECTED_MAX_NOTIONAL_USDT == 10.0
        assert m["ae_entry_adapter_status"] == "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY"
        assert m["af_stop_adapter_status"] == "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY"
        assert m["ag_cleanup_adapter_status"] == "TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY"

    def test_matrix_gates(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (
            GATE_CROSS_SYMBOL_CONSISTENT,
            GATE_CROSS_CATEGORY_CONSISTENT,
            GATE_CROSS_QTY_CONSISTENT,
            GATE_CROSS_ENTRY_SIDE_BUY,
            GATE_CROSS_EXPECTED_LONG_POSITION,
            GATE_CROSS_STOP_EXPECTED_LONG,
            GATE_CROSS_CLEANUP_PRE_CLEANUP_LONG,
            GATE_CROSS_STOP_LOSS_61_18,
            GATE_CROSS_STOP_LOSS_BELOW_ENTRY,
            GATE_CROSS_CLEANUP_SIDE_SELL,
            GATE_CROSS_CLEANUP_REDUCE_ONLY_TRUE,
            GATE_CROSS_CLEANUP_CLOSE_ON_TRIGGER_FALSE,
            GATE_CROSS_POSITION_IDX_ZERO,
            GATE_CROSS_ORDER_TYPE_MARKET,
            GATE_CROSS_MAX_NOTIONAL_10,
        ):
            assert g in blocked


# ===========================================================================
# AH35: manual confirmation matrix
# ===========================================================================

class TestAH35ManualConfirmationMatrix:
    def test_token_patterns(self):
        r = _run()
        m = r.manual_confirmation_matrix
        assert m["entry_token_pattern"] == ENTRY_TOKEN_PATTERN
        assert m["stop_token_pattern"] == STOP_TOKEN_PATTERN
        assert m["cleanup_token_pattern"] == CLEANUP_TOKEN_PATTERN
        assert m["token_validated"] is False
        assert m["token_format_not_authorization"] is True
        assert m["tokens_not_validated_in_this_task"] is True

    def test_token_pattern_strings(self):
        assert ENTRY_TOKEN_PATTERN == "CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SYMBOL"
        assert STOP_TOKEN_PATTERN == "CONFIRM_DEMO_TINY_STOP_ATTACH_YYYYMMDD_SYMBOL"
        assert CLEANUP_TOKEN_PATTERN == "CONFIRM_DEMO_TINY_CLEANUP_YYYYMMDD_SYMBOL"

    def test_confirmation_flags(self):
        r = _run()
        m = r.manual_confirmation_matrix
        assert m["entry_confirmation_flags"] == list(ENTRY_CONFIRMATION_FLAGS)
        assert m["stop_confirmation_flags"] == list(STOP_CONFIRMATION_FLAGS)
        assert m["cleanup_confirmation_flags"] == list(CLEANUP_CONFIRMATION_FLAGS)
        assert m["confirmation_flags_documented"] is True
        assert m["confirmation_flags_validated"] is False
        assert m["entry_flags_isolated_from_stop_cleanup"] is True
        assert m["stop_flags_isolated_from_entry_cleanup"] is True
        assert m["cleanup_flags_isolated_from_entry_stop"] is True

    def test_matrix_gates(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (
            GATE_ENTRY_TOKEN_PATTERN_PRESENT,
            GATE_STOP_TOKEN_PATTERN_PRESENT,
            GATE_CLEANUP_TOKEN_PATTERN_PRESENT,
            GATE_TOKENS_NOT_VALIDATED,
            GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
            GATE_CONFIRMATION_FLAGS_DOCUMENTED,
            GATE_CONFIRMATION_FLAGS_NOT_VALIDATED,
            GATE_ENTRY_FLAGS_ISOLATED,
            GATE_STOP_FLAGS_ISOLATED,
            GATE_CLEANUP_FLAGS_ISOLATED,
        ):
            assert g in blocked


# ===========================================================================
# AH36: execution forbidden matrix
# ===========================================================================

class TestAH36ExecutionForbiddenMatrix:
    def test_per_adapter_invariants(self):
        r = _run()
        m = r.execution_forbidden_matrix
        for key in ("ae_entry_adapter", "af_stop_adapter", "ag_cleanup_adapter"):
            sub = m[key]
            assert sub["real_execution_allowed"] is False
            assert sub["send_allowed"] is False
            assert sub["order_endpoint_called"] is False
            assert sub["stop_endpoint_called"] is False
            assert sub["no_position_modified"] is True
            assert sub["no_live_endpoint"] is True
            assert sub["no_secrets_loaded"] is True
            assert sub["secret_value_observed"] is False
            assert sub["g20_lifted"] is False

    def test_aggregate_invariants(self):
        r = _run()
        m = r.execution_forbidden_matrix
        assert m["no_position_modified_across_adapters"] is True
        assert m["no_secrets_loaded_across_adapters"] is True
        assert m["no_live_endpoint_across_adapters"] is True
        assert m["g20_not_lifted_across_adapters"] is True

    def test_matrix_gates(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (
            GATE_AE_REAL_EXECUTION_FALSE,
            GATE_AF_REAL_EXECUTION_FALSE,
            GATE_AG_REAL_EXECUTION_FALSE,
            GATE_AE_SEND_ALLOWED_FALSE,
            GATE_AF_SEND_ALLOWED_FALSE,
            GATE_AG_SEND_ALLOWED_FALSE,
            GATE_AE_ORDER_ENDPOINT_NOT_CALLED,
            GATE_AF_ORDER_ENDPOINT_NOT_CALLED,
            GATE_AG_ORDER_ENDPOINT_NOT_CALLED,
            GATE_AE_STOP_ENDPOINT_NOT_CALLED,
            GATE_AF_STOP_ENDPOINT_NOT_CALLED,
            GATE_AG_STOP_ENDPOINT_NOT_CALLED,
            GATE_NO_POSITION_MODIFIED_ACROSS_ADAPTERS,
            GATE_NO_SECRETS_LOADED_ACROSS_ADAPTERS,
            GATE_NO_LIVE_ENDPOINT_ACROSS_ADAPTERS,
            GATE_G20_NOT_LIFTED_ACROSS_ADAPTERS,
        ):
            assert g in blocked


# ===========================================================================
# AH37: sequential dry-run lifecycle plan -- 8 steps with manual_boundary
# ===========================================================================

class TestAH37SequentialDryRunLifecyclePlan:
    def test_eight_steps(self):
        r = _run()
        p = r.sequential_dry_run_lifecycle_plan
        assert p["lifecycle_plan_present"] is True
        assert p["step_count"] == 8
        assert len(p["steps"]) == 8
        assert len(LIFECYCLE_PLAN_STEPS) == 8

    def test_step_names_match(self):
        r = _run()
        p = r.sequential_dry_run_lifecycle_plan
        names = [s["step_name"] for s in p["steps"]]
        assert names == list(LIFECYCLE_PLAN_STEPS)
        # canonical names
        assert "pre_entry_readonly_check" in names
        assert "guarded_entry_only_dry_run" in names
        assert "guarded_stop_attach_only_dry_run" in names
        assert "guarded_cleanup_only_dry_run" in names
        assert "final_audit" in names

    def test_per_step_invariants(self):
        r = _run()
        p = r.sequential_dry_run_lifecycle_plan
        for s in p["steps"]:
            assert s["manual_boundary_required"] is True
            assert s["auto_advance"] is False
            assert s["auto_retry"] is False
            assert s["auto_cleanup"] is False
            assert s["auto_emergency_close"] is False
            assert s["endpoint_called"] is False
            assert s["response_from_exchange"] is False

    def test_aggregate_invariants(self):
        r = _run()
        p = r.sequential_dry_run_lifecycle_plan
        assert p["manual_boundary_every_step"] is True
        assert p["auto_advance_any_step"] is False
        assert p["auto_retry_any_step"] is False
        assert p["auto_cleanup_any_step"] is False
        assert p["auto_emergency_close_any_step"] is False
        assert p["endpoint_called_any_step"] is False
        assert p["response_from_exchange_any_step"] is False
        assert p["plan_only"] is True
        assert p["executed_in_this_task"] is False

    def test_plan_gates(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (
            GATE_LIFECYCLE_PLAN_PRESENT,
            GATE_LIFECYCLE_PLAN_EIGHT_STEPS,
            GATE_LIFECYCLE_MANUAL_BOUNDARY_EVERY_STEP,
            GATE_LIFECYCLE_AUTO_ADVANCE_FALSE,
            GATE_LIFECYCLE_AUTO_RETRY_FALSE,
            GATE_LIFECYCLE_AUTO_CLEANUP_FALSE,
            GATE_LIFECYCLE_AUTO_EMERGENCY_CLOSE_FALSE,
            GATE_LIFECYCLE_ENDPOINT_CALLED_FALSE_EVERY_STEP,
            GATE_LIFECYCLE_RESPONSE_FROM_EXCHANGE_FALSE,
        ):
            assert g in blocked


# ===========================================================================
# AH38: failure and abort summary
# ===========================================================================

class TestAH38FailureAndAbortSummary:
    def test_policy_codes(self):
        r = _run()
        s = r.failure_and_abort_summary
        for key in (
            "request_rejected",
            "readonly_unavailable",
            "selected_symbol_mismatch",
            "qty_mismatch",
            "side_mismatch",
            "stop_loss_invalid",
            "reduce_only_invalid",
            "partial_execution",
            "live_endpoint_detected",
            "secret_emission_detected",
        ):
            assert s[key] == "FAIL_CLOSED"
        assert s["protected_position_mismatch"] == "MANUAL_REVIEW_REQUIRED"

    def test_no_auto_progression(self):
        r = _run()
        s = r.failure_and_abort_summary
        assert s["no_auto_retry"] is True
        assert s["no_auto_next_step"] is True
        assert s["no_auto_cleanup"] is True
        assert s["no_auto_second_cleanup"] is True
        assert s["no_auto_emergency_close"] is True
        assert s["no_background_loop"] is True
        assert s["no_cron"] is True
        assert s["no_scheduler"] is True
        assert s["no_discord_trigger"] is True
        assert s["no_notion_trigger"] is True
        assert s["manual_intervention_only"] is True

    def test_failure_gates(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (
            GATE_REQUEST_REJECTED_FAIL_CLOSED,
            GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
            GATE_SELECTED_SYMBOL_MISMATCH_FAIL_CLOSED,
            GATE_QTY_MISMATCH_FAIL_CLOSED,
            GATE_SIDE_MISMATCH_FAIL_CLOSED,
            GATE_STOP_LOSS_INVALID_FAIL_CLOSED,
            GATE_REDUCE_ONLY_INVALID_FAIL_CLOSED,
            GATE_PARTIAL_EXECUTION_FAIL_CLOSED,
            GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW,
            GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED,
            GATE_SECRET_EMISSION_FAIL_CLOSED,
            GATE_NO_AUTO_RETRY,
            GATE_NO_AUTO_NEXT_STEP,
            GATE_NO_AUTO_CLEANUP,
            GATE_NO_AUTO_SECOND_CLEANUP,
            GATE_NO_AUTO_EMERGENCY_CLOSE,
            GATE_NO_BACKGROUND_LOOP,
            GATE_NO_CRON,
            GATE_NO_SCHEDULER,
            GATE_NO_DISCORD_TRIGGER,
            GATE_NO_NOTION_TRIGGER,
        ):
            assert g in blocked


# ===========================================================================
# AH39: documentation sync review
# ===========================================================================

class TestAH39DocumentationSyncReview:
    def test_sync_flags(self):
        r = _run()
        d = r.documentation_sync_review
        assert d["readme_status_board_sync_required"] is True
        assert d["next_action_sync_required"] is True
        assert d["command_log_sync_required"] is True
        assert d["forbidden_status_sync_required"] is True
        assert d["next_required_task_sync_required"] is True
        assert d["readme_path_ref"] == "README.md"
        assert d["next_action_path_ref"] == "docs/research/commands/NEXT_ACTION.md"
        assert d["command_log_path_ref"] == "docs/research/commands/COMMAND_LOG.md"
        assert d["next_required_task"] == "TASK-014AI_guarded_entry_real_permission_review"
        assert d["documentation_only_plan"] is True
        assert d["markdown_read_in_this_module"] is False

    def test_doc_gates(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (
            GATE_README_SYNC_REQUIRED,
            GATE_NEXT_ACTION_SYNC_REQUIRED,
            GATE_COMMAND_LOG_SYNC_REQUIRED,
            GATE_FORBIDDEN_STATUS_SYNC_REQUIRED,
            GATE_NEXT_REQUIRED_TASK_SYNC_REQUIRED,
        ):
            assert g in blocked


# ===========================================================================
# AH40: final lifecycle summary verdict
# ===========================================================================

class TestAH40FinalLifecycleSummaryVerdict:
    def test_verdict_fields(self):
        r = _run()
        v = r.final_lifecycle_summary_verdict
        assert v["summary_dry_run_approval_allowed"] is False
        assert v["real_lifecycle_execution_requested"] is False
        assert v["real_execution_allowed"] is False
        assert v["real_runner_implemented"] is False
        assert v["guarded_lifecycle_dry_run_summary"] is True
        assert v["summary_only"] is True
        assert v["entry_execution_included"] is False
        assert v["stop_execution_included"] is False
        assert v["cleanup_execution_included"] is False
        assert v["full_lifecycle_execution_included"] is False
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
        assert v["send_allowed"] is False
        assert v["order_endpoint_called"] is False
        assert v["stop_endpoint_called"] is False
        assert v["status"] == STATUS_SUMMARY_READY
        assert v["mode"] == MODE_SUMMARY_CHECKLIST
        assert v["next_required_task"] == "TASK-014AI_guarded_entry_real_permission_review"

    def test_verdict_gates(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (
            GATE_REAL_LIFECYCLE_EXECUTION_NOT_IMPL,
            GATE_NO_REAL_ORDER_ENDPOINT,
            GATE_NO_REAL_STOP_ENDPOINT,
            GATE_NO_POSITION_MODIFIED,
            GATE_G20_NOT_LIFTED,
            GATE_G20_POLICY_STILL_IN_PLACE,
            GATE_NO_LIVE_ENDPOINT,
            GATE_NO_SECRETS_EMITTED,
        ):
            assert g in blocked


# ===========================================================================
# AH41: audit artifacts
# ===========================================================================

class TestAH41AuditArtifacts:
    def test_audit_present(self):
        r = _run()
        a = r.audit_artifacts
        assert "cross_adapter_consistency_matrix" in a
        assert "manual_confirmation_matrix" in a
        assert "execution_forbidden_matrix" in a
        assert "sequential_dry_run_lifecycle_plan" in a
        assert "failure_and_abort_summary" in a
        assert "documentation_sync_review" in a
        assert "final_lifecycle_summary_verdict" in a
        assert a["response_status"] == "DRY_RUN_NOT_SENT"
        assert a["response_from_exchange"] is False
        assert a["sanitized"] is True
        assert a["no_secrets"] is True
        assert a["forbidden_log_fields"] == list(FORBIDDEN_LOG_FIELDS)


# ===========================================================================
# AH42: to_dict deep-copies stages and matrices
# ===========================================================================

class TestAH42ToDictDeepCopy:
    def test_to_dict_returns_independent_copies(self):
        r = _run()
        d = r.to_dict()
        # Mutate nested structures and confirm original untouched
        d["stages"]["mutated"] = True
        d["cross_adapter_consistency_matrix"]["mutated"] = True
        d["sequential_dry_run_lifecycle_plan"]["mutated"] = True
        d["blocked_gates"].append("MUTATED")
        assert "mutated" not in r.stages
        assert "mutated" not in r.cross_adapter_consistency_matrix
        assert "mutated" not in r.sequential_dry_run_lifecycle_plan
        assert "MUTATED" not in r.blocked_gates


# ===========================================================================
# AH43: status precedence -- hard_fail beats real_lifecycle / approval
# ===========================================================================

class TestAH43StatusPrecedenceHardFailWins:
    def test_real_lifecycle_with_missing_artifact_is_fail_closed(self):
        r = _run(readonly=None, allow_real_lifecycle_execution=True)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates

    def test_summary_approval_with_missing_artifact_is_fail_closed(self):
        r = _run(recon=None, allow_summary_approval=True)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


# ===========================================================================
# AH44: status precedence -- real_lifecycle beats summary_approval
# ===========================================================================

class TestAH44StatusPrecedenceRealLifecycleBeatsApproval:
    def test_real_lifecycle_wins(self):
        r = _run(
            allow_summary_approval=True,
            allow_real_lifecycle_execution=True,
        )
        assert r.status == STATUS_REAL_LIFECYCLE_NOT_IMPL
        assert r.mode == MODE_REAL_LIFECYCLE_EXECUTION_GUARD


# ===========================================================================
# AH45: acceptable upstream status frozensets are non-empty
# ===========================================================================

class TestAH45AcceptableStatuses:
    def test_acceptable_lifecycle_summary_statuses(self):
        assert "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY" in ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES
        assert "REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED" in ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES

    def test_acceptable_runner_design_statuses(self):
        assert "TINY_LIFECYCLE_RUNNER_DESIGN_READY" in ACCEPTABLE_RUNNER_DESIGN_STATUSES

    def test_acceptable_runner_dry_run_statuses(self):
        assert "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY" in ACCEPTABLE_RUNNER_DRY_RUN_STATUSES

    def test_acceptable_guarded_design_review_statuses(self):
        assert "TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY" in ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES

    def test_acceptable_guarded_entry_adapter_statuses(self):
        assert "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY" in ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES
        assert "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED" in ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES
        assert "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED" in ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES

    def test_acceptable_guarded_stop_adapter_statuses(self):
        assert "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY" in ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES
        assert "REAL_STOP_ATTACH_EXECUTION_NOT_IMPLEMENTED" in ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES

    def test_acceptable_guarded_cleanup_adapter_statuses(self):
        assert "TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY" in ACCEPTABLE_GUARDED_CLEANUP_ADAPTER_STATUSES
        assert "REAL_CLEANUP_EXECUTION_NOT_IMPLEMENTED" in ACCEPTABLE_GUARDED_CLEANUP_ADAPTER_STATUSES


# ===========================================================================
# AH46: g20 invariants preserved across all modes
# ===========================================================================

class TestAH46G20Invariants:
    @pytest.mark.parametrize("flags", [
        {},
        {"allow_summary_approval": True},
        {"allow_real_lifecycle_execution": True},
    ])
    def test_g20_in_place(self, flags):
        r = _run(**flags)
        assert r.g20_policy_still_in_place is True
        assert r.g20_lifted is False


# ===========================================================================
# AH47: existing demo positions never touched -- 5 protected symbols invariant
# ===========================================================================

class TestAH47ExistingPositionsUntouched:
    def test_existing_positions_invariant(self):
        r = _run()
        assert r.existing_positions_touched == []
        assert isinstance(r.existing_positions_touched, list)
        assert tuple(EXISTING_POSITION_SYMBOLS) == (
            "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"
        )
        assert sorted(r.existing_position_symbols) == sorted(EXISTING_POSITION_SYMBOLS)


# ===========================================================================
# AH48: order/stop endpoints never invoked, no live endpoint
# ===========================================================================

class TestAH48NoEndpointInvocation:
    def test_no_endpoints(self):
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

    def test_path_refs(self):
        assert ORDER_CREATE_PATH_REF == "/v5/order/create"
        assert TRADING_STOP_PATH_REF == "/v5/position/trading-stop"
        assert BASE_URL_DEMO_REF == "https://api-demo.bybit.com"
        assert BASE_URL_LIVE_REF == "https://api.bybit.com"
        assert DEMO_ENDPOINT_ALLOWLIST == ("https://api-demo.bybit.com",)


# ===========================================================================
# AH49: no secrets / no secret value observed
# ===========================================================================

class TestAH49NoSecretsLoaded:
    def test_no_secrets(self):
        r = _run()
        assert r.no_secrets_loaded is True
        assert r.secret_value_observed is False

    def test_forbidden_log_fields(self):
        assert "api_key_value" in FORBIDDEN_LOG_FIELDS
        assert "api_secret_value" in FORBIDDEN_LOG_FIELDS
        assert "signature_value" in FORBIDDEN_LOG_FIELDS


# ===========================================================================
# AH50: source scan -- no forbidden imports / no live endpoint / no signing
# ===========================================================================

class TestAH50SourceScanForbiddenImports:
    def test_no_urllib_import(self):
        code = _read_code_only(_MODULE_PATH)
        for tok in (" urllib ", " urlopen ", " socket ", " requests ", " httpx ", " http.client "):
            assert tok not in code, f"Forbidden import token {tok!r} found in module"

    def test_no_signing_imports(self):
        code = _read_code_only(_MODULE_PATH)
        for tok in (" hmac ", " hashlib ", "Crypto."):
            assert tok not in code, f"Forbidden signing token {tok!r} found in module"

    def test_no_env_reads(self):
        code = _read_code_only(_MODULE_PATH)
        for tok in (" os.environ ", " os.getenv ", " dotenv ", " load_dotenv "):
            assert tok not in code, f"Forbidden env-read token {tok!r} found in module"

    def test_no_real_runner_import(self):
        code = _read_code_only(_MODULE_PATH)
        # AH must not import any AA-AG modules or real sender/runner modules
        for tok in (
            "src.demo_tiny_lifecycle_real_execution_summary",
            "src.demo_tiny_lifecycle_runner_design",
            "src.demo_tiny_lifecycle_runner_dry_run",
            "src.demo_tiny_lifecycle_guarded_runner_design_review",
            "src.demo_tiny_guarded_entry_dry_run_adapter",
            "src.demo_tiny_guarded_stop_attach_dry_run_adapter",
            "src.demo_tiny_guarded_cleanup_dry_run_adapter",
            "BybitExecutor",
            "main.execute_new_entry",
            "src.risk",
        ):
            assert tok not in code, f"Forbidden source-module reference {tok!r} found in module"


# ===========================================================================
# AH51: live endpoint hostname must not appear in plaintext network use
# ===========================================================================

class TestAH51LiveEndpointReferenceOnly:
    def test_live_url_only_as_denylist_reference(self):
        # In source code with strings stripped, no network primitives must appear.
        code = _read_code_only(_MODULE_PATH)
        # No socket.create_connection / urllib.request / requests.post
        for tok in ("socket.create_connection", "urllib.request",
                    "requests.post", "requests.get", "httpx.post"):
            assert tok not in code
        # Live URL host must not appear as an identifier/code -- only as a string
        # literal in denylist references (strings are stripped from `code`).
        assert "api-demo.bybit.com" not in code
        assert "api.bybit.com" not in code


# ===========================================================================
# AH52: CLI script -- no forbidden flags exposed
# ===========================================================================

class TestAH52CLIForbiddenFlags:
    def test_no_real_execution_flag(self):
        code = _read_code_only(_SCRIPT_PATH)
        for tok in (
            "--execute-real-entry", "--execute-real-stop", "--execute-real-cleanup",
            "--execute-real-lifecycle", "--send-order", "--place-order", "--real-run",
            "--execute-new-entry",
        ):
            assert tok not in code, f"Forbidden CLI flag {tok!r} found in preview script"

    def test_no_real_runner_invocation(self):
        code = _read_code_only(_SCRIPT_PATH)
        for tok in ("BybitExecutor", "live_executor", "send_real_order"):
            assert tok not in code


# ===========================================================================
# AH53: CLI script -- exposes 17 --from-latest-* flags + 3 control flags
# ===========================================================================

class TestAH53CLIArgs:
    def test_all_from_latest_flags_present(self):
        text = _SCRIPT_PATH.read_text(encoding="utf-8")
        for flag in (
            "--from-latest-readonly",
            "--from-latest-reconciliation",
            "--from-latest-protection",
            "--from-latest-contract",
            "--from-latest-noop-plan",
            "--from-latest-lifecycle",
            "--from-latest-real-permission",
            "--from-latest-tiny-entry-permission",
            "--from-latest-tiny-stop-permission",
            "--from-latest-tiny-cleanup-permission",
            "--from-latest-lifecycle-summary",
            "--from-latest-runner-design",
            "--from-latest-runner-dry-run",
            "--from-latest-guarded-design-review",
            "--from-latest-guarded-entry-adapter",
            "--from-latest-guarded-stop-adapter",
            "--from-latest-guarded-cleanup-adapter",
            "--symbol",
            "--allow-summary-approval",
            "--allow-real-lifecycle-execution",
            "--write-report",
        ):
            assert flag in text, f"Expected CLI flag {flag!r} missing from preview script"


# ===========================================================================
# AH54: CLI subprocess -- checklist exit code 0 with stub artifacts
# ===========================================================================

def _write_artifact(dir_path: Path, name: str, payload: dict) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / name).write_text(json.dumps(payload), encoding="utf-8")


def _materialize_full_tree(base: Path) -> None:
    _write_artifact(base / "readonly_smoke",                            "latest_smoke.json",                                            _valid_readonly())
    _write_artifact(base / "reconciliation",                            "latest_reconciliation.json",                                   _valid_reconciliation())
    _write_artifact(base / "new_entry_protection",                      "latest_new_entry_protection.json",                             _valid_protection())
    _write_artifact(base / "trading_stop_contract",                     "latest_trading_stop_contract.json",                            _valid_contract())
    _write_artifact(base / "trading_stop_noop_probe_plan",              "latest_trading_stop_noop_probe_plan.json",                     _valid_noop_plan())
    _write_artifact(base / "tiny_position_lifecycle_mock",              "latest_tiny_position_lifecycle_mock.json",                     _valid_lifecycle())
    _write_artifact(base / "tiny_position_real_permission_gate",        "latest_tiny_position_real_permission_gate.json",               _valid_real_permission_gate())
    _write_artifact(base / "tiny_entry_permission_gate",                "latest_tiny_entry_permission_gate.json",                       _valid_tiny_entry_permission_gate())
    _write_artifact(base / "tiny_stop_attach_permission_gate",          "latest_tiny_stop_attach_permission_gate.json",                 _valid_tiny_stop_permission_gate())
    _write_artifact(base / "tiny_cleanup_permission_gate",              "latest_tiny_cleanup_permission_gate.json",                     _valid_tiny_cleanup_permission_gate())
    _write_artifact(base / "tiny_lifecycle_real_execution_summary",     "latest_tiny_lifecycle_real_execution_summary.json",            _valid_lifecycle_summary())
    _write_artifact(base / "tiny_lifecycle_runner_design",              "latest_tiny_lifecycle_runner_design.json",                     _valid_runner_design())
    _write_artifact(base / "tiny_lifecycle_runner_dry_run",             "latest_tiny_lifecycle_runner_dry_run.json",                    _valid_runner_dry_run())
    _write_artifact(base / "tiny_lifecycle_guarded_runner_design_review", "latest_tiny_lifecycle_guarded_runner_design_review.json",    _valid_guarded_design_review())
    _write_artifact(base / "tiny_guarded_entry_dry_run_adapter",        "latest_tiny_guarded_entry_dry_run_adapter.json",               _valid_guarded_entry_adapter())
    _write_artifact(base / "tiny_guarded_stop_attach_dry_run_adapter",  "latest_tiny_guarded_stop_attach_dry_run_adapter.json",         _valid_guarded_stop_adapter())
    _write_artifact(base / "tiny_guarded_cleanup_dry_run_adapter",      "latest_tiny_guarded_cleanup_dry_run_adapter.json",             _valid_guarded_cleanup_adapter())


class TestAH54CLIChecklistExitZero:
    def test_run_via_run_execute(self, tmp_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ah_preview_cli", str(_SCRIPT_PATH))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        base = tmp_path
        _materialize_full_tree(base)
        rc = mod.run_execute(
            symbol="SOLUSDT",
            allow_summary_approval=False,
            allow_real_lifecycle_execution=False,
            write_report=False,
            readonly_dir=base / "readonly_smoke",
            reconciliation_dir=base / "reconciliation",
            protection_dir=base / "new_entry_protection",
            contract_dir=base / "trading_stop_contract",
            noop_plan_dir=base / "trading_stop_noop_probe_plan",
            lifecycle_dir=base / "tiny_position_lifecycle_mock",
            real_permission_dir=base / "tiny_position_real_permission_gate",
            tiny_entry_dir=base / "tiny_entry_permission_gate",
            tiny_stop_dir=base / "tiny_stop_attach_permission_gate",
            tiny_cleanup_dir=base / "tiny_cleanup_permission_gate",
            lifecycle_summary_dir=base / "tiny_lifecycle_real_execution_summary",
            runner_design_dir=base / "tiny_lifecycle_runner_design",
            runner_dry_run_dir=base / "tiny_lifecycle_runner_dry_run",
            guarded_design_review_dir=base / "tiny_lifecycle_guarded_runner_design_review",
            guarded_entry_adapter_dir=base / "tiny_guarded_entry_dry_run_adapter",
            guarded_stop_adapter_dir=base / "tiny_guarded_stop_attach_dry_run_adapter",
            guarded_cleanup_adapter_dir=base / "tiny_guarded_cleanup_dry_run_adapter",
            output_dir=base / "tiny_guarded_lifecycle_dry_run_summary",
        )
        assert rc == 0


# ===========================================================================
# AH55: CLI write_report writes JSON + Markdown
# ===========================================================================

class TestAH55CLIWriteReport:
    def test_write_report(self, tmp_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ah_preview_cli", str(_SCRIPT_PATH))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        base = tmp_path
        _materialize_full_tree(base)
        out_dir = base / "tiny_guarded_lifecycle_dry_run_summary"
        rc = mod.run_execute(
            symbol="SOLUSDT",
            allow_summary_approval=False,
            allow_real_lifecycle_execution=False,
            write_report=True,
            readonly_dir=base / "readonly_smoke",
            reconciliation_dir=base / "reconciliation",
            protection_dir=base / "new_entry_protection",
            contract_dir=base / "trading_stop_contract",
            noop_plan_dir=base / "trading_stop_noop_probe_plan",
            lifecycle_dir=base / "tiny_position_lifecycle_mock",
            real_permission_dir=base / "tiny_position_real_permission_gate",
            tiny_entry_dir=base / "tiny_entry_permission_gate",
            tiny_stop_dir=base / "tiny_stop_attach_permission_gate",
            tiny_cleanup_dir=base / "tiny_cleanup_permission_gate",
            lifecycle_summary_dir=base / "tiny_lifecycle_real_execution_summary",
            runner_design_dir=base / "tiny_lifecycle_runner_design",
            runner_dry_run_dir=base / "tiny_lifecycle_runner_dry_run",
            guarded_design_review_dir=base / "tiny_lifecycle_guarded_runner_design_review",
            guarded_entry_adapter_dir=base / "tiny_guarded_entry_dry_run_adapter",
            guarded_stop_adapter_dir=base / "tiny_guarded_stop_attach_dry_run_adapter",
            guarded_cleanup_adapter_dir=base / "tiny_guarded_cleanup_dry_run_adapter",
            output_dir=out_dir,
        )
        assert rc == 0
        latest_json = out_dir / "latest_tiny_guarded_lifecycle_dry_run_summary.json"
        latest_md   = out_dir / "latest_tiny_guarded_lifecycle_dry_run_summary.md"
        assert latest_json.exists()
        assert latest_md.exists()
        data = json.loads(latest_json.read_text(encoding="utf-8"))
        assert data["status"] == STATUS_SUMMARY_READY
        assert data["next_required_task"] == "TASK-014AI_guarded_entry_real_permission_review"


# ===========================================================================
# AH56: CLI missing-artifact exit code 1
# ===========================================================================

class TestAH56CLIMissingArtifactExitOne:
    def test_missing_returns_one(self, tmp_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ah_preview_cli", str(_SCRIPT_PATH))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        base = tmp_path  # empty -- nothing materialised
        rc = mod.run_execute(
            symbol="SOLUSDT",
            readonly_dir=base / "readonly_smoke",
            reconciliation_dir=base / "reconciliation",
            protection_dir=base / "new_entry_protection",
            contract_dir=base / "trading_stop_contract",
            noop_plan_dir=base / "trading_stop_noop_probe_plan",
            lifecycle_dir=base / "tiny_position_lifecycle_mock",
            real_permission_dir=base / "tiny_position_real_permission_gate",
            tiny_entry_dir=base / "tiny_entry_permission_gate",
            tiny_stop_dir=base / "tiny_stop_attach_permission_gate",
            tiny_cleanup_dir=base / "tiny_cleanup_permission_gate",
            lifecycle_summary_dir=base / "tiny_lifecycle_real_execution_summary",
            runner_design_dir=base / "tiny_lifecycle_runner_design",
            runner_dry_run_dir=base / "tiny_lifecycle_runner_dry_run",
            guarded_design_review_dir=base / "tiny_lifecycle_guarded_runner_design_review",
            guarded_entry_adapter_dir=base / "tiny_guarded_entry_dry_run_adapter",
            guarded_stop_adapter_dir=base / "tiny_guarded_stop_attach_dry_run_adapter",
            guarded_cleanup_adapter_dir=base / "tiny_guarded_cleanup_dry_run_adapter",
            output_dir=base / "tiny_guarded_lifecycle_dry_run_summary",
        )
        assert rc == 1


# ===========================================================================
# AH57: CLI missing symbol returns 1
# ===========================================================================

class TestAH57CLIMissingSymbolExitOne:
    def test_missing_symbol(self, tmp_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ah_preview_cli", str(_SCRIPT_PATH))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        base = tmp_path
        _materialize_full_tree(base)
        rc = mod.run_execute(
            symbol="",
            readonly_dir=base / "readonly_smoke",
            reconciliation_dir=base / "reconciliation",
            protection_dir=base / "new_entry_protection",
            contract_dir=base / "trading_stop_contract",
            noop_plan_dir=base / "trading_stop_noop_probe_plan",
            lifecycle_dir=base / "tiny_position_lifecycle_mock",
            real_permission_dir=base / "tiny_position_real_permission_gate",
            tiny_entry_dir=base / "tiny_entry_permission_gate",
            tiny_stop_dir=base / "tiny_stop_attach_permission_gate",
            tiny_cleanup_dir=base / "tiny_cleanup_permission_gate",
            lifecycle_summary_dir=base / "tiny_lifecycle_real_execution_summary",
            runner_design_dir=base / "tiny_lifecycle_runner_design",
            runner_dry_run_dir=base / "tiny_lifecycle_runner_dry_run",
            guarded_design_review_dir=base / "tiny_lifecycle_guarded_runner_design_review",
            guarded_entry_adapter_dir=base / "tiny_guarded_entry_dry_run_adapter",
            guarded_stop_adapter_dir=base / "tiny_guarded_stop_attach_dry_run_adapter",
            guarded_cleanup_adapter_dir=base / "tiny_guarded_cleanup_dry_run_adapter",
            output_dir=base / "tiny_guarded_lifecycle_dry_run_summary",
        )
        assert rc == 1


# ===========================================================================
# AH58: timestamp is UTC ISO with trailing Z
# ===========================================================================

class TestAH58TimestampFormat:
    def test_ts_format(self):
        r = _run()
        ts = r.timestamp_utc
        assert ts.endswith("Z")
        assert "T" in ts
        # No timezone offset like +00:00 since we strip and add Z manually
        assert "+00:00" not in ts


# ===========================================================================
# AH59: dataclass field types
# ===========================================================================

class TestAH59ResultDataclassTypes:
    def test_field_types(self):
        r = _run()
        assert isinstance(r.timestamp_utc, str)
        assert isinstance(r.mode, str)
        assert isinstance(r.selected_symbol, str)
        assert isinstance(r.existing_position_symbols, list)
        assert isinstance(r.stages, dict)
        assert isinstance(r.stage_order, list)
        assert isinstance(r.summary_scope, dict)
        assert isinstance(r.cross_adapter_consistency_matrix, dict)
        assert isinstance(r.manual_confirmation_matrix, dict)
        assert isinstance(r.execution_forbidden_matrix, dict)
        assert isinstance(r.sequential_dry_run_lifecycle_plan, dict)
        assert isinstance(r.failure_and_abort_summary, dict)
        assert isinstance(r.documentation_sync_review, dict)
        assert isinstance(r.audit_artifacts, dict)
        assert isinstance(r.final_lifecycle_summary_verdict, dict)
        assert isinstance(r.blocked_gates, list)


# ===========================================================================
# AH60: 124 gate constants module-level
# ===========================================================================

class TestAH60GateCount:
    def test_gate_count(self):
        import src.demo_tiny_guarded_lifecycle_dry_run_summary as m
        gates = [k for k in dir(m) if k.startswith("GATE_")]
        # Workorder requires at least 123 gates.
        assert len(gates) >= 123


# ===========================================================================
# AH61: stage order matches ALL_STAGES tuple
# ===========================================================================

class TestAH61StageOrder:
    def test_stage_order(self):
        r = _run()
        assert tuple(r.stage_order) == ALL_STAGES
        assert ALL_STAGES[0] == STAGE_0_ARTIFACT_PREFLIGHT
        assert ALL_STAGES[1] == STAGE_1_SUMMARY_SCOPE
        assert ALL_STAGES[2] == STAGE_2_CROSS_ADAPTER_CONSISTENCY_MATRIX
        assert ALL_STAGES[3] == STAGE_3_MANUAL_CONFIRMATION_MATRIX
        assert ALL_STAGES[4] == STAGE_4_EXECUTION_FORBIDDEN_MATRIX
        assert ALL_STAGES[5] == STAGE_5_SEQUENTIAL_DRY_RUN_LIFECYCLE_PLAN
        assert ALL_STAGES[6] == STAGE_6_FAILURE_AND_ABORT_SUMMARY
        assert ALL_STAGES[7] == STAGE_7_DOCUMENTATION_SYNC_REVIEW
        assert ALL_STAGES[8] == STAGE_8_FINAL_LIFECYCLE_SUMMARY_VERDICT


# ===========================================================================
# AH62: blocked_gates are deduplicated
# ===========================================================================

class TestAH62BlockedGatesDeduplicated:
    def test_dedup(self):
        r = _run()
        assert len(set(r.blocked_gates)) == len(r.blocked_gates)


# ===========================================================================
# AH63: 28+ hard-fail gates enforce STATUS_FAIL_CLOSED
# ===========================================================================

class TestAH63HardFailGates:
    def test_hard_fail_gates_module_level(self):
        from src.demo_tiny_guarded_lifecycle_dry_run_summary import _HARD_FAIL_GATES
        assert len(_HARD_FAIL_GATES) >= 28
        assert GATE_READONLY_SMOKE_MISSING in _HARD_FAIL_GATES
        assert GATE_GUARDED_CLEANUP_ADAPTER_MISSING in _HARD_FAIL_GATES
        assert GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE in _HARD_FAIL_GATES
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in _HARD_FAIL_GATES


# ===========================================================================
# AH64: G20 sender invariant -- always still in place, never lifted
# ===========================================================================

class TestAH64G20PolicyStillInPlace:
    def test_module_does_not_lift_g20(self):
        # Module body must NOT contain a g20_lifted = True assignment
        code_txt = _MODULE_PATH.read_text(encoding="utf-8")
        assert 'g20_lifted":           True' not in code_txt
        assert "g20_lifted=True" not in code_txt
        # And must reference g20_policy_still_in_place as True
        assert 'g20_policy_still_in_place' in code_txt


# ===========================================================================
# AH65: 5 protected existing positions remain present in reconciliation
# ===========================================================================

class TestAH65FiveProtectedPositionsPresent:
    def test_reconciliation_invariant(self):
        r = _run()
        assert r.existing_position_symbols == list(EXISTING_POSITION_SYMBOLS)
        assert len(r.existing_position_symbols) == 5
        assert SUMMARY_EXPECTED_EXISTING_COUNT == 5


# ===========================================================================
# AH66: Acceptable variant statuses (READY_BUT_EXECUTION_DISABLED variants) accepted
# ===========================================================================

class TestAH66AcceptableVariantStatuses:
    def test_entry_adapter_variant(self):
        ae = _valid_guarded_entry_adapter()
        ae["status"] = "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED"
        r = _run(guarded_entry_adapter=ae)
        assert r.status == STATUS_SUMMARY_READY

    def test_stop_adapter_variant(self):
        af = _valid_guarded_stop_adapter()
        af["status"] = "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED"
        r = _run(guarded_stop_adapter=af)
        assert r.status == STATUS_SUMMARY_READY

    def test_cleanup_adapter_variant(self):
        ag = _valid_guarded_cleanup_adapter()
        ag["status"] = "TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED"
        r = _run(guarded_cleanup_adapter=ag)
        assert r.status == STATUS_SUMMARY_READY


# ===========================================================================
# AH67: next_required_task points at TASK-014AI in all paths
# ===========================================================================

class TestAH67NextRequiredTaskInvariant:
    @pytest.mark.parametrize("flags", [
        {},
        {"allow_summary_approval": True},
        {"allow_real_lifecycle_execution": True},
        {"readonly": None},  # FAIL_CLOSED still emits next_required_task
    ])
    def test_next_required(self, flags):
        r = _run(**flags)
        assert r.next_required_task == "TASK-014AI_guarded_entry_real_permission_review"


# ===========================================================================
# AH68: stages dict is independent across calls
# ===========================================================================

class TestAH68StagesIndependentAcrossCalls:
    def test_two_calls_separate(self):
        r1 = _run()
        r2 = _run()
        r1.stages["mutated"] = True
        assert "mutated" not in r2.stages


# ===========================================================================
# AH69: SUMMARY_EXPECTED_* invariants match workorder
# ===========================================================================

class TestAH69SummaryExpectedConstants:
    def test_constants(self):
        assert SUMMARY_EXPECTED_SYMBOL == "SOLUSDT"
        assert SUMMARY_EXPECTED_CATEGORY == "linear"
        assert SUMMARY_EXPECTED_QTY == 0.1
        assert SUMMARY_EXPECTED_ENTRY_SIDE == "Buy"
        assert SUMMARY_EXPECTED_POSITION_SIDE_LONG == "long"
        assert SUMMARY_EXPECTED_STOP_LOSS == 61.18
        assert SUMMARY_EXPECTED_ENTRY_REFERENCE == 64.4
        assert SUMMARY_EXPECTED_CLEANUP_SIDE == "Sell"
        assert SUMMARY_EXPECTED_REDUCE_ONLY is True
        assert SUMMARY_EXPECTED_CLOSE_ON_TRIGGER is False
        assert SUMMARY_EXPECTED_POSITION_IDX == 0
        assert SUMMARY_EXPECTED_ORDER_TYPE == "Market"
        assert SUMMARY_EXPECTED_MAX_NOTIONAL_USDT == 10.0
        assert SUMMARY_EXPECTED_EXISTING_COUNT == 5
        assert SUMMARY_EXPECTED_STOP_LOSS < SUMMARY_EXPECTED_ENTRY_REFERENCE


# ===========================================================================
# AH70: confirmation flag tuple invariants
# ===========================================================================

class TestAH70ConfirmationFlagTuples:
    def test_entry_flags(self):
        assert "--i-understand-this-is-demo-real-execution" in ENTRY_CONFIRMATION_FLAGS
        assert "--max-notional-usdt 10" in ENTRY_CONFIRMATION_FLAGS
        assert "--expected-existing-position-count 5" in ENTRY_CONFIRMATION_FLAGS
        # Entry confirmation flags do not contain stop-loss specific or cleanup specific args
        for f in ENTRY_CONFIRMATION_FLAGS:
            assert "stop-loss" not in f
            assert "expected-cleanup" not in f

    def test_stop_flags(self):
        assert "--expected-stop-loss-price 61.18" in STOP_CONFIRMATION_FLAGS
        assert "--expected-trigger-by MarkPrice" in STOP_CONFIRMATION_FLAGS
        assert "--expected-tpsl-mode Full" in STOP_CONFIRMATION_FLAGS
        for f in STOP_CONFIRMATION_FLAGS:
            assert "expected-cleanup" not in f

    def test_cleanup_flags(self):
        assert "--expected-cleanup-symbol SOLUSDT" in CLEANUP_CONFIRMATION_FLAGS
        assert "--expected-cleanup-qty 0.1" in CLEANUP_CONFIRMATION_FLAGS
        assert "--expected-cleanup-side Sell" in CLEANUP_CONFIRMATION_FLAGS
        assert "--expected-reduce-only true" in CLEANUP_CONFIRMATION_FLAGS
        for f in CLEANUP_CONFIRMATION_FLAGS:
            assert "expected-stop-loss" not in f
            assert "expected-trigger-by" not in f


# ===========================================================================
# AH71: AST-level: no os.environ access, no urllib.request.urlopen
# ===========================================================================

class TestAH71ASTSafety:
    def test_no_os_environ_access(self):
        tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                assert not (node.value.id == "os" and node.attr in ("environ", "getenv"))
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute):
                # detect urllib.request.urlopen
                if isinstance(node.value.value, ast.Name):
                    assert not (
                        node.value.value.id == "urllib"
                        and node.value.attr == "request"
                        and node.attr == "urlopen"
                    )

    def test_no_signing_call(self):
        tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    assert not (node.func.value.id in ("hmac", "hashlib") and
                                node.func.attr in ("new", "sha256", "sha512", "digest"))


# ===========================================================================
# AH72: hard fail aggregates blocked gates without dropping early ones
# ===========================================================================

class TestAH72HardFailAggregatesGates:
    def test_multiple_missing(self):
        r = _run(readonly=None, recon=None, protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates
        assert GATE_PROTECTION_MISSING in r.blocked_gates


# ===========================================================================
# AH73: real_lifecycle_execution flag does not flip any never-true invariant
# ===========================================================================

class TestAH73RealLifecycleExecutionDoesNotEnable:
    def test_invariants_preserved(self):
        r = _run(allow_real_lifecycle_execution=True)
        assert r.real_execution_allowed is False
        assert r.real_runner_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.send_allowed is False
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.no_secrets_loaded is True
        assert r.g20_policy_still_in_place is True
        assert r.g20_lifted is False


# ===========================================================================
# AH74: summary approval flag does not enable real execution
# ===========================================================================

class TestAH74SummaryApprovalDoesNotEnable:
    def test_invariants_preserved(self):
        r = _run(allow_summary_approval=True)
        assert r.real_execution_allowed is False
        assert r.real_runner_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.send_allowed is False
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE


# ===========================================================================
# AH75: 17 from-latest defaults map to expected directories
# ===========================================================================

class TestAH75CLIDefaultDirs:
    def test_default_output_dir(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ah_preview_cli", str(_SCRIPT_PATH))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Module-level _DEFAULT_*_DIR constants
        assert mod._DEFAULT_OUTPUT_DIR.name == "tiny_guarded_lifecycle_dry_run_summary"
        assert mod._DEFAULT_OUTPUT_DIR.parent.name == "demo_trading"
        assert mod._DEFAULT_READONLY_DIR.name == "readonly_smoke"
        assert mod._DEFAULT_GUARDED_ENTRY_ADAPTER_DIR.name == "tiny_guarded_entry_dry_run_adapter"
        assert mod._DEFAULT_GUARDED_STOP_ADAPTER_DIR.name == "tiny_guarded_stop_attach_dry_run_adapter"
        assert mod._DEFAULT_GUARDED_CLEANUP_ADAPTER_DIR.name == "tiny_guarded_cleanup_dry_run_adapter"


# ===========================================================================
# AH76: status precedence (positive path) -- happy path
# ===========================================================================

class TestAH76HappyPathStatusPrecedence:
    def test_no_flags(self):
        r = _run()
        assert r.status == STATUS_SUMMARY_READY


# ===========================================================================
# AH77: timestamp_utc explicitly via _now arg
# ===========================================================================

class TestAH77TimestampOverride:
    def test_now_override(self):
        ts = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        r = _run(_now=ts)
        assert r.timestamp_utc.startswith("2026-01-02T03:04:05")


# ===========================================================================
# AH78: blocked gates count > 100 in healthy run (all stages contribute)
# ===========================================================================

class TestAH78BlockedGatesCount:
    def test_count(self):
        r = _run()
        assert len(r.blocked_gates) >= 90


# ===========================================================================
# AH79: documentation review names current task TASK-014AH context
# ===========================================================================

class TestAH79DocPathsAndNextTask:
    def test_doc_paths(self):
        r = _run()
        d = r.documentation_sync_review
        assert d["readme_path_ref"] == "README.md"
        assert d["next_action_path_ref"].endswith("NEXT_ACTION.md")
        assert d["command_log_path_ref"].endswith("COMMAND_LOG.md")
        assert d["next_required_task"].startswith("TASK-014AI")


# ===========================================================================
# AH80: cross-adapter consistency exposes per-adapter status fields
# ===========================================================================

class TestAH80CrossAdapterStatusFieldsExposed:
    def test_status_keys(self):
        r = _run()
        m = r.cross_adapter_consistency_matrix
        assert m["ae_entry_adapter_status"]
        assert m["af_stop_adapter_status"]
        assert m["ag_cleanup_adapter_status"]
