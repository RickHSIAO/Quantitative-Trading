"""
tests/demo_trading/test_demo_tiny_guarded_entry_real_permission_review.py
TASK-014AI: Guarded Tiny Entry Real Permission Review tests (AI1 - AI72+).

Covers permission_review_checklist / permission_review_approval /
real_entry_execution_guard / fail_closed paths; all 9 stages; 125 gate
constants; 18-artifact preflight contract (10 baseline + AA lifecycle
summary + AB runner design + AC runner dry-run + AD guarded design
review + AE guarded entry adapter + AF guarded stop-attach adapter +
AG guarded cleanup adapter + AH guarded lifecycle summary);
entry-permission expectations (SOLUSDT / linear / Buy / 0.1 / market /
positionIdx 0 / reduceOnly false / max_notional 10 / stopLoss 61.18);
entry_token_pattern (CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SYMBOL) never
validated; 8-flag confirmation flag documentation never validated;
review-only envelope (no sender adapter, signature_present False,
private_headers empty, send_allowed False); post-entry protection
manual boundary (stop_attach_required True but never executed);
failure / abort policy (FAIL_CLOSED / MANUAL_REVIEW_REQUIRED);
documentation sync plan; status precedence; source-scan safety (no
urlopen / no forbidden imports / no signing / no os.environ / no
AA-AH module reuse / no real sender); report artifacts; forbidden-
flag absence (--execute-real-* / --send-order / --place-order /
--real-run); the invariant that TASK-014L sender G20
(protected_entry_policy_missing) still blocks --execute-new-entry and
is NOT lifted here; next_required_task points at
TASK-014AJ_guarded_entry_manual_authorization_design.
"""
from __future__ import annotations

import ast
import json
import sys
import tokenize
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_tiny_guarded_entry_real_permission_review import (
    ACCEPTABLE_GUARDED_CLEANUP_ADAPTER_STATUSES,
    ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES,
    ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES,
    ACCEPTABLE_GUARDED_LIFECYCLE_SUMMARY_STATUSES,
    ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES,
    ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES,
    ACCEPTABLE_RUNNER_DESIGN_STATUSES,
    ACCEPTABLE_RUNNER_DRY_RUN_STATUSES,
    ALL_STAGES,
    BASE_URL_DEMO_REF,
    BASE_URL_LIVE_REF,
    DEFAULT_SELECTED_SYMBOL,
    DEMO_ENDPOINT_ALLOWLIST,
    DemoTinyGuardedEntryRealPermissionReview,
    ENTRY_CONFIRMATION_FLAGS,
    ENTRY_REVIEW_ORDER_LINK_ID_PREFIXES,
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
    GATE_CLEANUP_EXECUTION_NOT_INCLUDED,
    GATE_CLEANUP_SEPARATE_MANUAL_BOUNDARY,
    GATE_COMMAND_LOG_SYNC_REQUIRED,
    GATE_CONFIRMATION_FLAGS_DOCUMENTED,
    GATE_CONFIRMATION_FLAGS_NOT_VALIDATED,
    GATE_CONTRACT_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_ACCOUNT_MODE_DEMO,
    GATE_ENTRY_CATEGORY_LINEAR,
    GATE_ENTRY_DEMO_ENDPOINT_ONLY,
    GATE_ENTRY_ENDPOINT_FAMILY_BYBIT_DEMO,
    GATE_ENTRY_ESTIMATED_NOTIONAL_WITHIN_CAP,
    GATE_ENTRY_EXECUTION_NOT_INCLUDED,
    GATE_ENTRY_MAX_NOTIONAL_USDT_10,
    GATE_ENTRY_MIN_ORDER_QTY_0_1,
    GATE_ENTRY_ORDER_TYPE_MARKET,
    GATE_ENTRY_POSITION_IDX_ZERO,
    GATE_ENTRY_PROOF_STRENGTH_STRONG,
    GATE_ENTRY_QTY_0_1,
    GATE_ENTRY_QTY_STEP_0_1,
    GATE_ENTRY_REDUCE_ONLY_FALSE,
    GATE_ENTRY_REVIEW_ENVELOPE_PRESENT,
    GATE_ENTRY_SIDE_BUY,
    GATE_ENTRY_SUCCESS_NO_STOP_REQUIRES_MANUAL,
    GATE_ENTRY_SYMBOL_SOLUSDT,
    GATE_ENTRY_TICK_SIZE_0_01,
    GATE_ENTRY_TOKEN_PATTERN_PRESENT,
    GATE_ENVELOPE_BASE_URL_DEMO_ONLY,
    GATE_ENVELOPE_CLOSE_ON_TRIGGER_FALSE,
    GATE_ENVELOPE_ENDPOINT_CALLED_FALSE,
    GATE_ENVELOPE_ENDPOINT_PATH_ORDER_CREATE,
    GATE_ENVELOPE_NO_SENDER_ADAPTER,
    GATE_ENVELOPE_ORDER_TYPE_MARKET,
    GATE_ENVELOPE_POSITION_IDX_ZERO,
    GATE_ENVELOPE_PREVIEW_ONLY,
    GATE_ENVELOPE_PRIVATE_HEADERS_EMPTY,
    GATE_ENVELOPE_QTY_0_1,
    GATE_ENVELOPE_REAL_PAYLOAD_FALSE,
    GATE_ENVELOPE_REDUCE_ONLY_FALSE,
    GATE_ENVELOPE_SEND_ALLOWED_FALSE,
    GATE_ENVELOPE_SIDE_BUY,
    GATE_ENVELOPE_SIGNATURE_PRESENT_FALSE,
    GATE_EXISTING_PROTECTED_POSITIONS_DOCUMENTED,
    GATE_EXPECTED_ENTRY_QTY_FLAG_DOCUMENTED,
    GATE_EXPECTED_ENTRY_SIDE_FLAG_DOCUMENTED,
    GATE_EXPECTED_ENTRY_SYMBOL_FLAG_DOCUMENTED,
    GATE_EXPECTED_REDUCE_ONLY_FALSE_FLAG_DOCUMENTED,
    GATE_FORBIDDEN_STATUS_SYNC_REQUIRED,
    GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED,
    GATE_G20_NOT_LIFTED,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_GUARDED_CLEANUP_ADAPTER_MISSING,
    GATE_GUARDED_DESIGN_REVIEW_MISSING,
    GATE_GUARDED_ENTRY_ADAPTER_MISSING,
    GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE,
    GATE_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_ONLY,
    GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING,
    GATE_GUARDED_LIFECYCLE_SUMMARY_READINESS_EXECUTABLE,
    GATE_GUARDED_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE,
    GATE_GUARDED_STOP_ADAPTER_MISSING,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_LIFECYCLE_SUMMARY_MISSING,
    GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED,
    GATE_MANUAL_BOUNDARY_REQUIRED,
    GATE_NEXT_ACTION_SYNC_REQUIRED,
    GATE_NEXT_REQUIRED_TASK_SYNC_REQUIRED,
    GATE_NOOP_PLAN_MISSING,
    GATE_NO_AUTOMATIC_CLEANUP,
    GATE_NO_AUTOMATIC_STOP_ATTACH,
    GATE_NO_AUTO_CLEANUP_FAILURE,
    GATE_NO_AUTO_EMERGENCY_CLOSE,
    GATE_NO_AUTO_NEXT_STEP,
    GATE_NO_AUTO_RETRY,
    GATE_NO_AUTO_STOP_ATTACH_FAILURE,
    GATE_NO_BACKGROUND_LOOP,
    GATE_NO_CRON,
    GATE_NO_DISCORD_TRIGGER,
    GATE_NO_ENDPOINT_INVOKED,
    GATE_NO_EXISTING_SOLUSDT_POSITION,
    GATE_NO_G20_LIFT,
    GATE_NO_LIVE_ENDPOINT,
    GATE_NO_NOTION_TRIGGER,
    GATE_NO_POSITION_MODIFIED,
    GATE_NO_POSITION_MODIFIED_SCOPE,
    GATE_NO_REAL_ORDER_ENDPOINT,
    GATE_NO_REAL_STOP_ENDPOINT,
    GATE_NO_SCHEDULER,
    GATE_NO_SECRETS_EMITTED,
    GATE_NO_SECRETS_LOADED,
    GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED,
    GATE_PERMISSION_REVIEW_ONLY,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_POST_ENTRY_SL_TRIGGER_BY_MARKPRICE,
    GATE_POST_ENTRY_STOP_LOSS_61_18,
    GATE_POST_ENTRY_TPSL_MODE_FULL,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW,
    GATE_PROTECTION_MISSING,
    GATE_QTY_MISMATCH_FAIL_CLOSED,
    GATE_README_SYNC_REQUIRED,
    GATE_READONLY_SMOKE_MISSING,
    GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
    GATE_REAL_ENTRY_EXECUTION_NOT_IMPL,
    GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE,
    GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_RECONCILIATION_MISSING,
    GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED,
    GATE_REQUEST_REJECTED_FAIL_CLOSED,
    GATE_RUNNER_DESIGN_MISSING,
    GATE_RUNNER_DRY_RUN_MISSING,
    GATE_SECOND_CONFIRMATION_REQUIRED,
    GATE_SECRET_EMISSION_FAIL_CLOSED,
    GATE_SELECTED_SYMBOL_EXISTS_FAIL_CLOSED,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
    GATE_SIDE_MISMATCH_FAIL_CLOSED,
    GATE_STOP_ATTACH_REQUIRED,
    GATE_STOP_ATTACH_SEPARATE_MANUAL_BOUNDARY,
    GATE_STOP_EXECUTION_NOT_INCLUDED,
    GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
    GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
    GATE_TINY_STOP_PERMISSION_GATE_MISSING,
    GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
    GATE_TOKEN_NOT_VALIDATED,
    LIVE_ENDPOINT_DENYLIST,
    MODE_FAIL_CLOSED,
    MODE_PERMISSION_REVIEW_APPROVAL,
    MODE_PERMISSION_REVIEW_CHECKLIST,
    MODE_REAL_ENTRY_EXECUTION_GUARD,
    ORDER_CREATE_PATH_REF,
    READINESS_CONCLUSION_NOT_EXECUTABLE,
    REVIEW_EXPECTED_CATEGORY,
    REVIEW_EXPECTED_CLOSE_ON_TRIGGER,
    REVIEW_EXPECTED_ENTRY_REFERENCE,
    REVIEW_EXPECTED_ENTRY_SIDE,
    REVIEW_EXPECTED_ESTIMATED_NOTIONAL,
    REVIEW_EXPECTED_EXISTING_COUNT,
    REVIEW_EXPECTED_MAX_NOTIONAL_USDT,
    REVIEW_EXPECTED_MIN_ORDER_QTY,
    REVIEW_EXPECTED_ORDER_TYPE,
    REVIEW_EXPECTED_POSITION_IDX,
    REVIEW_EXPECTED_QTY,
    REVIEW_EXPECTED_QTY_STEP,
    REVIEW_EXPECTED_REDUCE_ONLY,
    REVIEW_EXPECTED_SL_TRIGGER_BY,
    REVIEW_EXPECTED_STOP_LOSS,
    REVIEW_EXPECTED_SYMBOL,
    REVIEW_EXPECTED_TICK_SIZE,
    REVIEW_EXPECTED_TPSL_MODE,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_PERMISSION_REVIEW_SCOPE,
    STAGE_2_ENTRY_REAL_PERMISSION_CONDITIONS,
    STAGE_3_MANUAL_AUTHORIZATION_REVIEW,
    STAGE_4_ENTRY_REQUEST_REVIEW_ENVELOPE,
    STAGE_5_REQUIRED_POST_ENTRY_PROTECTION_REVIEW,
    STAGE_6_FAILURE_AND_ABORT_REVIEW,
    STAGE_7_DOCUMENTATION_SYNC_REVIEW,
    STAGE_8_FINAL_ENTRY_REAL_PERMISSION_REVIEW_VERDICT,
    STATUS_FAIL_CLOSED,
    STATUS_REAL_ENTRY_NOT_IMPL,
    STATUS_REVIEW_READY,
    STATUS_REVIEW_READY_EXEC_DISABLED,
    TRADING_STOP_PATH_REF,
    TinyGuardedEntryRealPermissionReviewResult,
)


_MODULE_PATH = ROOT / "src" / "demo_tiny_guarded_entry_real_permission_review.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_tiny_guarded_entry_real_permission_review.py"
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
        "selected_qty":           REVIEW_EXPECTED_QTY,
        "entry_reference_price":  REVIEW_EXPECTED_ENTRY_REFERENCE,
        "stop_price":             REVIEW_EXPECTED_STOP_LOSS,
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
        "tiny_qty":                  REVIEW_EXPECTED_QTY,
        "tiny_notional":             REVIEW_EXPECTED_ESTIMATED_NOTIONAL,
        "entry_reference_price":     REVIEW_EXPECTED_ENTRY_REFERENCE,
        "stop_price":                REVIEW_EXPECTED_STOP_LOSS,
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
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _valid_guarded_lifecycle_summary() -> dict:
    return {
        "timestamp_utc":             "2026-06-11T11:59:59.95Z",
        "mode":                      "summary_checklist",
        "selected_symbol":           "SOLUSDT",
        "status":                    "TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY",
        "readiness_conclusion":      READINESS_CONCLUSION_NOT_EXECUTABLE,
        "real_execution_allowed":              False,
        "real_runner_implemented":             False,
        "guarded_lifecycle_dry_run_summary":   True,
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


def _review() -> DemoTinyGuardedEntryRealPermissionReview:
    return DemoTinyGuardedEntryRealPermissionReview()


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
    guarded_lifecycle_summary=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    allow_review_approval=False,
    allow_real_entry_execution=False,
    _now=_TEST_NOW,
) -> TinyGuardedEntryRealPermissionReviewResult:
    return _review().run_checklist(
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
        guarded_lifecycle_summary=_valid_guarded_lifecycle_summary()             if guarded_lifecycle_summary      is _UNSET else guarded_lifecycle_summary,
        symbol=symbol,
        allow_review_approval=allow_review_approval,
        allow_real_entry_execution=allow_real_entry_execution,
        _now=_now,
    )


# ===========================================================================
# AI1: valid checklist => TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY
# ===========================================================================

class TestAI1ReviewReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_REVIEW_READY
        assert r.mode == MODE_PERMISSION_REVIEW_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.guarded_entry_real_permission_review is True
        assert r.permission_review_only is True
        assert r.entry_execution_included is False
        assert r.stop_execution_included is False
        assert r.cleanup_execution_included is False
        assert r.full_lifecycle_execution_included is False
        assert r.current_task_real_execution_allowed is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.next_required_task == "TASK-014AJ_guarded_entry_manual_authorization_design"


# ===========================================================================
# AI2: --allow-review-approval => READY_BUT_EXECUTION_DISABLED
# ===========================================================================

class TestAI2PermissionReviewApproval:
    def test_approval(self):
        r = _run(allow_review_approval=True)
        assert r.status == STATUS_REVIEW_READY_EXEC_DISABLED
        assert r.mode == MODE_PERMISSION_REVIEW_APPROVAL
        assert r.review_approval_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE


# ===========================================================================
# AI3: --allow-real-entry-execution => REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
# ===========================================================================

class TestAI3RealEntryExecutionGuard:
    def test_guard(self):
        r = _run(allow_real_entry_execution=True)
        assert r.status == STATUS_REAL_ENTRY_NOT_IMPL
        assert r.mode == MODE_REAL_ENTRY_EXECUTION_GUARD
        assert r.real_entry_execution_requested is True
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.no_position_modified is True


# ===========================================================================
# AI4-AI21: 18 missing upstream artifacts each => FAIL_CLOSED
# ===========================================================================

class TestAI4MissingReadonly:
    def test_fail_closed(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert r.failed_stage == STAGE_0_ARTIFACT_PREFLIGHT
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestAI5MissingReconciliation:
    def test_fail_closed(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestAI6MissingProtection:
    def test_fail_closed(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestAI7MissingContract:
    def test_fail_closed(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestAI8MissingNoopPlan:
    def test_fail_closed(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestAI9MissingLifecycle:
    def test_fail_closed(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestAI10MissingRealPermissionGate:
    def test_fail_closed(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAI11MissingTinyEntryPermissionGate:
    def test_fail_closed(self):
        r = _run(tiny_entry_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAI12MissingTinyStopPermissionGate:
    def test_fail_closed(self):
        r = _run(tiny_stop_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAI13MissingTinyCleanupPermissionGate:
    def test_fail_closed(self):
        r = _run(tiny_cleanup_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAI14MissingLifecycleSummary:
    def test_fail_closed(self):
        r = _run(lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAI15MissingRunnerDesign:
    def test_fail_closed(self):
        r = _run(runner_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DESIGN_MISSING in r.blocked_gates


class TestAI16MissingRunnerDryRun:
    def test_fail_closed(self):
        r = _run(runner_dry_run=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DRY_RUN_MISSING in r.blocked_gates


class TestAI17MissingGuardedDesignReview:
    def test_fail_closed(self):
        r = _run(guarded_design_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_MISSING in r.blocked_gates


class TestAI18MissingGuardedEntryAdapter:
    def test_fail_closed(self):
        r = _run(guarded_entry_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_ENTRY_ADAPTER_MISSING in r.blocked_gates


class TestAI19MissingGuardedStopAdapter:
    def test_fail_closed(self):
        r = _run(guarded_stop_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_STOP_ADAPTER_MISSING in r.blocked_gates


class TestAI20MissingGuardedCleanupAdapter:
    def test_fail_closed(self):
        r = _run(guarded_cleanup_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_CLEANUP_ADAPTER_MISSING in r.blocked_gates


class TestAI21MissingGuardedLifecycleSummary:
    def test_fail_closed(self):
        r = _run(guarded_lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


# ===========================================================================
# AI22: Symbol not SOLUSDT => FAIL_CLOSED
# ===========================================================================

class TestAI22SymbolNotSolusdt:
    @pytest.mark.parametrize("bad_symbol", [
        "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT",
        "BTCUSDT", "ETHUSDT", "foo",
    ])
    def test_fail_closed(self, bad_symbol):
        r = _run(symbol=bad_symbol)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in r.blocked_gates


# ===========================================================================
# AI23-AI26: invariant mismatches
# ===========================================================================

class TestAI23EndpointFamilyMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["endpoint_family"] = "bybit_live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestAI24AccountModeMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["account_mode"] = "live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestAI25ProofStrengthMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["proof_strength"] = "WEAK"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROOF_STRENGTH_NOT_STRONG in r.blocked_gates


class TestAI26PositionDetailsSourceMismatch:
    def test_fail_closed(self):
        bad = _valid_reconciliation()
        bad["mode"] = "fake"
        bad["position_details_source"] = "fake"
        r = _run(recon=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY in r.blocked_gates


# ===========================================================================
# AI27: Guarded entry adapter status not acceptable
# ===========================================================================

class TestAI27GuardedEntryAdapterStatusUnacceptable:
    def test_fail_closed(self):
        bad = _valid_guarded_entry_adapter()
        bad["status"] = "ENTRY_ADAPTER_FAIL_CLOSED"
        r = _run(guarded_entry_adapter=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE in r.blocked_gates


# ===========================================================================
# AI28: Guarded lifecycle summary status not acceptable
# ===========================================================================

class TestAI28GuardedLifecycleSummaryStatusUnacceptable:
    def test_fail_closed(self):
        bad = _valid_guarded_lifecycle_summary()
        bad["status"] = "SUMMARY_FAIL_CLOSED"
        r = _run(guarded_lifecycle_summary=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE in r.blocked_gates


# ===========================================================================
# AI29: Guarded lifecycle summary readiness must be NOT_EXECUTABLE
# ===========================================================================

class TestAI29GuardedLifecycleSummaryReadinessExecutable:
    def test_fail_closed(self):
        bad = _valid_guarded_lifecycle_summary()
        bad["readiness_conclusion"] = "READY_TO_EXECUTE"
        r = _run(guarded_lifecycle_summary=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_LIFECYCLE_SUMMARY_READINESS_EXECUTABLE in r.blocked_gates


# ===========================================================================
# AI30: Missing symbol => FAIL_CLOSED
# ===========================================================================

class TestAI30MissingSymbol:
    def test_fail_closed(self):
        r = _run(symbol="")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_MISSING in r.blocked_gates


# ===========================================================================
# AI31: 9 stages must all be present
# ===========================================================================

class TestAI31NineStages:
    def test_all_9_stages(self):
        r = _run()
        assert len(r.stages) == 9
        for stage_id in (
            STAGE_0_ARTIFACT_PREFLIGHT,
            STAGE_1_PERMISSION_REVIEW_SCOPE,
            STAGE_2_ENTRY_REAL_PERMISSION_CONDITIONS,
            STAGE_3_MANUAL_AUTHORIZATION_REVIEW,
            STAGE_4_ENTRY_REQUEST_REVIEW_ENVELOPE,
            STAGE_5_REQUIRED_POST_ENTRY_PROTECTION_REVIEW,
            STAGE_6_FAILURE_AND_ABORT_REVIEW,
            STAGE_7_DOCUMENTATION_SYNC_REVIEW,
            STAGE_8_FINAL_ENTRY_REAL_PERMISSION_REVIEW_VERDICT,
        ):
            assert stage_id in r.stages

    def test_stage_order_match(self):
        r = _run()
        assert tuple(r.stage_order) == ALL_STAGES


# ===========================================================================
# AI32: stage_1_permission_review_scope
# ===========================================================================

class TestAI32PermissionReviewScope:
    def test_scope_present(self):
        r = _run()
        scope = r.permission_review_scope
        assert scope["guarded_entry_real_permission_review"] is True
        assert scope["permission_review_only"] is True
        assert scope["entry_execution_included"] is False
        assert scope["stop_execution_included"] is False
        assert scope["cleanup_execution_included"] is False
        assert scope["full_lifecycle_execution_included"] is False
        assert scope["real_entry_implemented"] is False
        assert scope["real_execution_allowed"] is False
        assert scope["order_endpoint_called"] is False
        assert scope["stop_endpoint_called"] is False
        assert scope["no_endpoint_invoked_in_this_task"] is True
        assert scope["no_position_modified"] is True
        assert scope["no_secrets_loaded"] is True
        assert scope["g20_policy_still_in_place"] is True
        assert scope["g20_lifted"] is False
        assert scope["next_required_task"] == "TASK-014AJ_guarded_entry_manual_authorization_design"


# ===========================================================================
# AI33: stage_2_entry_real_permission_conditions
# ===========================================================================

class TestAI33EntryRealPermissionConditions:
    def test_conditions_present(self):
        r = _run()
        c = r.entry_real_permission_conditions
        assert c["symbol"] == REVIEW_EXPECTED_SYMBOL
        assert c["category"] == REVIEW_EXPECTED_CATEGORY
        assert c["entry_side"] == REVIEW_EXPECTED_ENTRY_SIDE
        assert c["qty"] == REVIEW_EXPECTED_QTY
        assert c["qty_step"] == REVIEW_EXPECTED_QTY_STEP
        assert c["min_order_qty"] == REVIEW_EXPECTED_MIN_ORDER_QTY
        assert c["tick_size"] == REVIEW_EXPECTED_TICK_SIZE
        assert c["entry_reference"] == REVIEW_EXPECTED_ENTRY_REFERENCE
        assert c["estimated_notional_usdt"] == REVIEW_EXPECTED_ESTIMATED_NOTIONAL
        assert c["max_notional_usdt"] == REVIEW_EXPECTED_MAX_NOTIONAL_USDT
        assert c["estimated_notional_within_cap"] is True
        assert c["position_idx"] == REVIEW_EXPECTED_POSITION_IDX
        assert c["reduce_only"] is False
        assert c["order_type"] == REVIEW_EXPECTED_ORDER_TYPE
        assert c["demo_endpoint_only"] is True
        assert c["no_existing_solusdt_position"] is True
        assert c["existing_protected_position_count"] == REVIEW_EXPECTED_EXISTING_COUNT
        assert tuple(c["existing_protected_position_symbols"]) == EXISTING_POSITION_SYMBOLS
        assert c["proof_strength"] == EXPECTED_PROOF_STRENGTH
        assert c["account_mode"] == EXPECTED_ACCOUNT_MODE
        assert c["endpoint_family"] == EXPECTED_ENDPOINT_FAMILY


# ===========================================================================
# AI34: stage_3_manual_authorization_review
# ===========================================================================

class TestAI34ManualAuthorizationReview:
    def test_review_present(self):
        r = _run()
        m = r.manual_authorization_review
        assert m["entry_token_pattern"] == ENTRY_TOKEN_PATTERN
        assert m["token_validated"] is False
        assert m["token_format_not_authorization"] is True
        assert m["tokens_not_validated_in_this_task"] is True
        assert list(m["entry_confirmation_flags"]) == list(ENTRY_CONFIRMATION_FLAGS)
        assert m["confirmation_flags_documented"] is True
        assert m["confirmation_flags_validated"] is False
        assert m["second_confirmation_required"] is True
        assert m["manual_boundary_required"] is True
        assert m["expected_entry_symbol_flag"] == "--expected-entry-symbol SOLUSDT"
        assert m["expected_entry_qty_flag"] == "--expected-entry-qty 0.1"
        assert m["expected_entry_side_flag"] == "--expected-entry-side Buy"
        assert m["expected_reduce_only_false_flag"] == "--expected-reduce-only false"


# ===========================================================================
# AI35: stage_4_entry_request_review_envelope
# ===========================================================================

class TestAI35EntryRequestReviewEnvelope:
    def test_envelope_present(self):
        r = _run()
        e = r.entry_request_review_envelope
        assert e["preview_only"] is True
        assert e["send_allowed"] is False
        assert e["endpoint_called"] is False
        assert e["real_payload"] is False
        assert e["signature_present"] is False
        assert e["private_headers"] == []
        assert e["endpoint_path_ref"] == ORDER_CREATE_PATH_REF
        assert e["base_url_ref"] == BASE_URL_DEMO_REF
        assert tuple(e["demo_endpoint_allowlist"]) == DEMO_ENDPOINT_ALLOWLIST
        assert tuple(e["live_endpoint_denylist"]) == LIVE_ENDPOINT_DENYLIST
        assert e["category"] == REVIEW_EXPECTED_CATEGORY
        assert e["symbol"] == REVIEW_EXPECTED_SYMBOL
        assert e["side"] == REVIEW_EXPECTED_ENTRY_SIDE
        assert e["orderType"] == REVIEW_EXPECTED_ORDER_TYPE
        assert e["qty"] == REVIEW_EXPECTED_QTY
        assert e["reduceOnly"] is False
        assert e["closeOnTrigger"] is False
        assert e["positionIdx"] == REVIEW_EXPECTED_POSITION_IDX
        assert list(e["orderLinkId_prefixes"]) == list(ENTRY_REVIEW_ORDER_LINK_ID_PREFIXES)
        assert e["sender_adapter_invoked"] is False
        assert e["no_sender_adapter"] is True
        assert e["real_payload_conversion"] is False


# ===========================================================================
# AI36: stage_5_required_post_entry_protection_review
# ===========================================================================

class TestAI36RequiredPostEntryProtectionReview:
    def test_protection_present(self):
        r = _run()
        p = r.required_post_entry_protection_review
        assert p["stop_attach_required"] is True
        assert p["stop_loss"] == REVIEW_EXPECTED_STOP_LOSS
        assert p["tpsl_mode"] == REVIEW_EXPECTED_TPSL_MODE
        assert p["sl_trigger_by"] == REVIEW_EXPECTED_SL_TRIGGER_BY
        assert p["stop_attach_separate_manual_boundary"] is True
        assert p["no_automatic_stop_attach"] is True
        assert p["cleanup_separate_manual_boundary"] is True
        assert p["no_automatic_cleanup"] is True
        assert p["entry_success_without_stop_requires_manual_review"] is True
        assert p["stop_attach_executed_in_this_task"] is False
        assert p["cleanup_executed_in_this_task"] is False


# ===========================================================================
# AI37: stage_6_failure_and_abort_review
# ===========================================================================

class TestAI37FailureAndAbortReview:
    def test_review_present(self):
        r = _run()
        f = r.failure_and_abort_review
        assert f["request_rejected"] == "FAIL_CLOSED"
        assert f["readonly_unavailable"] == "FAIL_CLOSED"
        assert f["selected_symbol_exists"] == "FAIL_CLOSED"
        assert f["qty_mismatch"] == "FAIL_CLOSED"
        assert f["side_mismatch"] == "FAIL_CLOSED"
        assert f["reduce_only_mismatch"] == "FAIL_CLOSED"
        assert f["notional_cap_exceeded"] == "FAIL_CLOSED"
        assert f["protected_position_mismatch"] == "MANUAL_REVIEW_REQUIRED"
        assert f["live_endpoint_detected"] == "FAIL_CLOSED"
        assert f["secret_emission_detected"] == "FAIL_CLOSED"
        assert f["no_auto_retry"] is True
        assert f["no_auto_stop_attach"] is True
        assert f["no_auto_cleanup"] is True
        assert f["no_auto_emergency_close"] is True
        assert f["no_auto_next_step"] is True
        assert f["no_background_loop"] is True
        assert f["no_cron"] is True
        assert f["no_scheduler"] is True
        assert f["no_discord_trigger"] is True
        assert f["no_notion_trigger"] is True
        assert f["manual_intervention_only"] is True


# ===========================================================================
# AI38: stage_7_documentation_sync_review
# ===========================================================================

class TestAI38DocumentationSyncReview:
    def test_review_present(self):
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
        assert d["next_required_task"] == "TASK-014AJ_guarded_entry_manual_authorization_design"
        assert d["documentation_only_plan"] is True
        assert d["markdown_read_in_this_module"] is False


# ===========================================================================
# AI39: stage_8_final_entry_real_permission_review_verdict
# ===========================================================================

class TestAI39FinalEntryRealPermissionReviewVerdict:
    def test_verdict_present(self):
        r = _run()
        v = r.final_entry_real_permission_review_verdict
        assert v["review_approval_allowed"] is False
        assert v["real_entry_execution_requested"] is False
        assert v["real_execution_allowed"] is False
        assert v["real_entry_implemented"] is False
        assert v["guarded_entry_real_permission_review"] is True
        assert v["permission_review_only"] is True
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
        assert v["status"] == STATUS_REVIEW_READY
        assert v["mode"] == MODE_PERMISSION_REVIEW_CHECKLIST
        assert v["next_required_task"] == "TASK-014AJ_guarded_entry_manual_authorization_design"


# ===========================================================================
# AI40: audit_artifacts must aggregate all stage outputs (sanitized)
# ===========================================================================

class TestAI40AuditArtifacts:
    def test_audit_artifacts(self):
        r = _run()
        a = r.audit_artifacts
        for key in (
            "permission_review_scope",
            "entry_real_permission_conditions",
            "manual_authorization_review",
            "entry_request_review_envelope",
            "required_post_entry_protection_review",
            "failure_and_abort_review",
            "documentation_sync_review",
            "final_entry_real_permission_review_verdict",
        ):
            assert key in a
        assert a["response_status"] == "REVIEW_NOT_SENT"
        assert a["response_from_exchange"] is False
        assert a["sanitized"] is True
        assert a["no_secrets"] is True
        assert tuple(a["forbidden_log_fields"]) == FORBIDDEN_LOG_FIELDS


# ===========================================================================
# AI41: to_dict() deep-copy independence
# ===========================================================================

class TestAI41ToDictDeepCopy:
    def test_deep_copy(self):
        r = _run()
        d1 = r.to_dict()
        d1["permission_review_scope"]["mutated"] = True
        d2 = r.to_dict()
        assert "mutated" not in d2["permission_review_scope"]
        d1["blocked_gates"].append("FAKE_GATE")
        assert "FAKE_GATE" not in r.blocked_gates


# ===========================================================================
# AI42: status precedence -- hard-fail beats every flag combination
# ===========================================================================

class TestAI42StatusPrecedenceHardFailWins:
    @pytest.mark.parametrize("flags", [
        {},
        {"allow_review_approval": True},
        {"allow_real_entry_execution": True},
        {"allow_review_approval": True, "allow_real_entry_execution": True},
    ])
    def test_hard_fail_overrides(self, flags):
        r = _run(readonly=None, **flags)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED


# ===========================================================================
# AI43: status precedence -- real-entry-execution-guard beats review-approval
# ===========================================================================

class TestAI43StatusPrecedenceRealEntryBeatsApproval:
    def test_real_entry_beats_approval(self):
        r = _run(allow_review_approval=True, allow_real_entry_execution=True)
        assert r.status == STATUS_REAL_ENTRY_NOT_IMPL
        assert r.mode == MODE_REAL_ENTRY_EXECUTION_GUARD


# ===========================================================================
# AI44: acceptable upstream status whitelists
# ===========================================================================

class TestAI44AcceptableStatuses:
    @pytest.mark.parametrize("status", list(ACCEPTABLE_GUARDED_LIFECYCLE_SUMMARY_STATUSES))
    def test_accepted_lifecycle_summary(self, status):
        good = _valid_guarded_lifecycle_summary()
        good["status"] = status
        r = _run(guarded_lifecycle_summary=good)
        assert r.status == STATUS_REVIEW_READY
        assert GATE_GUARDED_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE not in r.blocked_gates

    @pytest.mark.parametrize("status", list(ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES))
    def test_accepted_guarded_entry_adapter(self, status):
        good = _valid_guarded_entry_adapter()
        good["status"] = status
        r = _run(guarded_entry_adapter=good)
        assert r.status == STATUS_REVIEW_READY
        assert GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE not in r.blocked_gates


# ===========================================================================
# AI45: G20 invariants -- never lifted regardless of flag combinations
# ===========================================================================

class TestAI45G20Invariants:
    @pytest.mark.parametrize("flags", [
        {},
        {"allow_review_approval": True},
        {"allow_real_entry_execution": True},
    ])
    def test_g20_in_place(self, flags):
        r = _run(**flags)
        assert r.g20_policy_still_in_place is True
        assert r.g20_lifted is False


# ===========================================================================
# AI46: existing demo positions never touched
# ===========================================================================

class TestAI46ExistingPositionsUntouched:
    def test_existing_positions_invariant(self):
        r = _run()
        assert r.existing_positions_touched == []
        assert isinstance(r.existing_positions_touched, list)
        assert tuple(EXISTING_POSITION_SYMBOLS) == (
            "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"
        )
        assert sorted(r.existing_position_symbols) == sorted(EXISTING_POSITION_SYMBOLS)


# ===========================================================================
# AI47: no endpoint invoked, no live endpoint
# ===========================================================================

class TestAI47NoEndpointInvocation:
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
        assert LIVE_ENDPOINT_DENYLIST == ("https://api.bybit.com",)


# ===========================================================================
# AI48: no secrets loaded
# ===========================================================================

class TestAI48NoSecretsLoaded:
    def test_no_secrets(self):
        r = _run()
        assert r.no_secrets_loaded is True
        assert r.secret_value_observed is False

    def test_forbidden_log_fields(self):
        assert "api_key_value" in FORBIDDEN_LOG_FIELDS
        assert "api_secret_value" in FORBIDDEN_LOG_FIELDS
        assert "signature_value" in FORBIDDEN_LOG_FIELDS


# ===========================================================================
# AI49: source scan -- no forbidden imports / no live endpoint / no signing
# ===========================================================================

class TestAI49SourceScanForbiddenImports:
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

    def test_no_reused_module_imports(self):
        code = _read_code_only(_MODULE_PATH)
        for tok in (
            "src.demo_tiny_lifecycle_real_execution_summary",
            "src.demo_tiny_lifecycle_runner_design",
            "src.demo_tiny_lifecycle_runner_dry_run",
            "src.demo_tiny_lifecycle_guarded_runner_design_review",
            "src.demo_tiny_guarded_entry_dry_run_adapter",
            "src.demo_tiny_guarded_stop_attach_dry_run_adapter",
            "src.demo_tiny_guarded_cleanup_dry_run_adapter",
            "src.demo_tiny_guarded_lifecycle_dry_run_summary",
            "BybitExecutor",
            "main.execute_new_entry",
            "src.risk",
        ):
            assert tok not in code, f"Forbidden source-module reference {tok!r} found in module"


# ===========================================================================
# AI50: live endpoint reference is string-only
# ===========================================================================

class TestAI50LiveEndpointReferenceOnly:
    def test_no_network_primitives(self):
        code = _read_code_only(_MODULE_PATH)
        for tok in ("socket.create_connection", "urllib.request",
                    "requests.post", "requests.get", "httpx.post"):
            assert tok not in code

    def test_live_url_not_in_stripped_code(self):
        code = _read_code_only(_MODULE_PATH)
        # Strings are stripped from `code`; live URL is only a denylist string
        assert "api-demo.bybit.com" not in code
        assert "api.bybit.com" not in code


# ===========================================================================
# AI51: CLI script -- no forbidden execute/send/place/real-run flags exposed
# ===========================================================================

class TestAI51CLIForbiddenFlags:
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
# AI52: CLI script exposes 18 --from-latest-* flags + 4 control flags
# ===========================================================================

class TestAI52CLIArgs:
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
            "--from-latest-guarded-lifecycle-summary",
            "--symbol",
            "--allow-review-approval",
            "--allow-real-entry-execution",
            "--write-report",
        ):
            assert flag in text, f"Expected CLI flag {flag!r} missing from preview script"


# ===========================================================================
# AI53/AI54/AI55/AI56: CLI subprocess via importlib
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
    _write_artifact(base / "tiny_guarded_lifecycle_dry_run_summary",    "latest_tiny_guarded_lifecycle_dry_run_summary.json",           _valid_guarded_lifecycle_summary())


def _load_cli_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ai_preview_cli", str(_SCRIPT_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cli_kwargs(base: Path) -> dict:
    return dict(
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
        guarded_lifecycle_summary_dir=base / "tiny_guarded_lifecycle_dry_run_summary",
    )


class TestAI53CLIChecklistExitZero:
    def test_run_via_run_execute(self, tmp_path):
        mod = _load_cli_module()
        base = tmp_path
        _materialize_full_tree(base)
        rc = mod.run_execute(
            symbol="SOLUSDT",
            allow_review_approval=False,
            allow_real_entry_execution=False,
            write_report=False,
            output_dir=base / "tiny_guarded_entry_real_permission_review",
            **_cli_kwargs(base),
        )
        assert rc == 0


class TestAI54CLIWriteReport:
    def test_write_report(self, tmp_path):
        mod = _load_cli_module()
        base = tmp_path
        _materialize_full_tree(base)
        out_dir = base / "tiny_guarded_entry_real_permission_review"
        rc = mod.run_execute(
            symbol="SOLUSDT",
            allow_review_approval=False,
            allow_real_entry_execution=False,
            write_report=True,
            output_dir=out_dir,
            **_cli_kwargs(base),
        )
        assert rc == 0
        latest_json = out_dir / "latest_tiny_guarded_entry_real_permission_review.json"
        latest_md   = out_dir / "latest_tiny_guarded_entry_real_permission_review.md"
        assert latest_json.exists()
        assert latest_md.exists()
        data = json.loads(latest_json.read_text(encoding="utf-8"))
        assert data["status"] == STATUS_REVIEW_READY
        assert data["next_required_task"] == "TASK-014AJ_guarded_entry_manual_authorization_design"


class TestAI55CLIMissingArtifactExitOne:
    def test_missing_returns_one(self, tmp_path):
        mod = _load_cli_module()
        base = tmp_path
        # Materialize all 18 then delete one to trigger missing
        _materialize_full_tree(base)
        (base / "tiny_guarded_lifecycle_dry_run_summary"
              / "latest_tiny_guarded_lifecycle_dry_run_summary.json").unlink()
        rc = mod.run_execute(
            symbol="SOLUSDT",
            allow_review_approval=False,
            allow_real_entry_execution=False,
            write_report=False,
            output_dir=base / "tiny_guarded_entry_real_permission_review",
            **_cli_kwargs(base),
        )
        assert rc == 1


class TestAI56CLIMissingSymbolExitOne:
    def test_missing_symbol_returns_one(self, tmp_path):
        mod = _load_cli_module()
        base = tmp_path
        _materialize_full_tree(base)
        rc = mod.run_execute(
            symbol="",
            allow_review_approval=False,
            allow_real_entry_execution=False,
            write_report=False,
            output_dir=base / "tiny_guarded_entry_real_permission_review",
            **_cli_kwargs(base),
        )
        assert rc == 1


# ===========================================================================
# AI57: Timestamp format
# ===========================================================================

class TestAI57TimestampFormat:
    def test_timestamp(self):
        r = _run()
        assert r.timestamp_utc == "2026-06-11T12:00:00Z"


# ===========================================================================
# AI58: Result dataclass types
# ===========================================================================

class TestAI58ResultDataclassTypes:
    def test_types(self):
        r = _run()
        assert isinstance(r.timestamp_utc, str)
        assert isinstance(r.mode, str)
        assert isinstance(r.selected_symbol, str)
        assert isinstance(r.existing_position_symbols, list)
        assert isinstance(r.stages, dict)
        assert isinstance(r.permission_review_scope, dict)
        assert isinstance(r.entry_real_permission_conditions, dict)
        assert isinstance(r.manual_authorization_review, dict)
        assert isinstance(r.entry_request_review_envelope, dict)
        assert isinstance(r.required_post_entry_protection_review, dict)
        assert isinstance(r.failure_and_abort_review, dict)
        assert isinstance(r.documentation_sync_review, dict)
        assert isinstance(r.audit_artifacts, dict)
        assert isinstance(r.final_entry_real_permission_review_verdict, dict)
        assert isinstance(r.blocked_gates, list)
        assert isinstance(r.failed_stage, str)
        assert isinstance(r.status, str)
        assert isinstance(r.next_required_task, str)


# ===========================================================================
# AI59: Gate count -- 125 unique GATE_* constants
# ===========================================================================

class TestAI59GateCount:
    def test_gate_count(self):
        import src.demo_tiny_guarded_entry_real_permission_review as m
        gates = [
            getattr(m, name) for name in dir(m)
            if name.startswith("GATE_")
        ]
        assert len(gates) >= 125, f"Expected >=125 gates, found {len(gates)}"
        assert len(set(gates)) == len(gates), "Gate name strings must be unique"


# ===========================================================================
# AI60: Stage order matches ALL_STAGES
# ===========================================================================

class TestAI60StageOrder:
    def test_stage_order_default(self):
        r = _run()
        assert tuple(r.stage_order) == ALL_STAGES
        assert len(ALL_STAGES) == 9


# ===========================================================================
# AI61: Blocked gates deduplicated
# ===========================================================================

class TestAI61BlockedGatesDeduplicated:
    def test_no_duplicates(self):
        r = _run()
        assert len(r.blocked_gates) == len(set(r.blocked_gates))


# ===========================================================================
# AI62: Hard-fail gates frozenset
# ===========================================================================

class TestAI62HardFailGates:
    def test_hard_fail_membership(self):
        from src.demo_tiny_guarded_entry_real_permission_review import _HARD_FAIL_GATES
        assert GATE_READONLY_SMOKE_MISSING in _HARD_FAIL_GATES
        assert GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING in _HARD_FAIL_GATES
        assert GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE in _HARD_FAIL_GATES
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in _HARD_FAIL_GATES


# ===========================================================================
# AI63: G20 policy still in place
# ===========================================================================

class TestAI63G20PolicyStillInPlace:
    def test_g20(self):
        r = _run()
        assert r.g20_policy_still_in_place is True
        assert r.g20_lifted is False
        assert GATE_G20_POLICY_STILL_IN_PLACE in r.blocked_gates
        assert GATE_NO_G20_LIFT in r.blocked_gates
        assert GATE_G20_NOT_LIFTED in r.blocked_gates


# ===========================================================================
# AI64: Five protected demo positions present
# ===========================================================================

class TestAI64FiveProtectedPositionsPresent:
    def test_five_protected(self):
        r = _run()
        assert REVIEW_EXPECTED_EXISTING_COUNT == 5
        assert len(EXISTING_POSITION_SYMBOLS) == 5
        assert tuple(EXISTING_POSITION_SYMBOLS) == (
            "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"
        )
        assert set(r.existing_position_symbols) == set(EXISTING_POSITION_SYMBOLS)


# ===========================================================================
# AI65: next_required_task invariant
# ===========================================================================

class TestAI65NextRequiredTaskInvariant:
    @pytest.mark.parametrize("flags", [
        {},
        {"allow_review_approval": True},
        {"allow_real_entry_execution": True},
    ])
    def test_next_required_task(self, flags):
        r = _run(**flags)
        assert r.next_required_task == "TASK-014AJ_guarded_entry_manual_authorization_design"


# ===========================================================================
# AI66: Stages independent across calls (no shared mutable state)
# ===========================================================================

class TestAI66StagesIndependentAcrossCalls:
    def test_independent(self):
        r1 = _run()
        r2 = _run()
        r1.stages[STAGE_0_ARTIFACT_PREFLIGHT]["__poison__"] = True
        assert "__poison__" not in r2.stages[STAGE_0_ARTIFACT_PREFLIGHT]


# ===========================================================================
# AI67: Review-expected constants
# ===========================================================================

class TestAI67ReviewExpectedConstants:
    def test_constants(self):
        assert REVIEW_EXPECTED_SYMBOL == "SOLUSDT"
        assert REVIEW_EXPECTED_CATEGORY == "linear"
        assert REVIEW_EXPECTED_ENTRY_SIDE == "Buy"
        assert REVIEW_EXPECTED_QTY == 0.1
        assert REVIEW_EXPECTED_QTY_STEP == 0.1
        assert REVIEW_EXPECTED_MIN_ORDER_QTY == 0.1
        assert REVIEW_EXPECTED_TICK_SIZE == 0.01
        assert REVIEW_EXPECTED_MAX_NOTIONAL_USDT == 10.0
        assert REVIEW_EXPECTED_ENTRY_REFERENCE == 64.4
        assert REVIEW_EXPECTED_ESTIMATED_NOTIONAL == 6.44
        assert REVIEW_EXPECTED_POSITION_IDX == 0
        assert REVIEW_EXPECTED_REDUCE_ONLY is False
        assert REVIEW_EXPECTED_CLOSE_ON_TRIGGER is False
        assert REVIEW_EXPECTED_ORDER_TYPE == "Market"
        assert REVIEW_EXPECTED_STOP_LOSS == 61.18
        assert REVIEW_EXPECTED_TPSL_MODE == "Full"
        assert REVIEW_EXPECTED_SL_TRIGGER_BY == "MarkPrice"
        assert EXPECTED_INSTRUMENT_CATEGORY == "linear"
        assert REVIEW_EXPECTED_EXISTING_COUNT == 5


# ===========================================================================
# AI68: Confirmation flag tuple shape
# ===========================================================================

class TestAI68ConfirmationFlagTuples:
    def test_entry_flags(self):
        # Exactly the 8 documented flags
        assert isinstance(ENTRY_CONFIRMATION_FLAGS, tuple)
        assert len(ENTRY_CONFIRMATION_FLAGS) == 8
        # The 4 explicitly cited workorder flags must be present
        joined = " ".join(ENTRY_CONFIRMATION_FLAGS)
        assert "--i-understand-this-is-demo-real-execution" in joined
        assert "--max-notional-usdt" in joined
        assert "--expected-entry-symbol" in joined
        assert "--expected-entry-qty" in joined
        assert "--expected-entry-side" in joined
        assert "--expected-reduce-only" in joined

    def test_entry_token_pattern(self):
        assert ENTRY_TOKEN_PATTERN == "CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SYMBOL"


# ===========================================================================
# AI69: AST safety -- module source must be parseable
# ===========================================================================

class TestAI69ASTSafety:
    def test_module_ast(self):
        source = _MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        # Ensure no Call to dangerous functions at top level
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                assert attr not in ("urlopen", "create_connection"), (
                    f"Forbidden call {attr} found in module"
                )
                # network HTTP methods on a session/client (e.g. requests.post)
                if attr in ("post", "put", "delete", "patch") and isinstance(node.func.value, ast.Name):
                    base = node.func.value.id
                    assert base not in ("requests", "session", "client", "http"), (
                        f"Forbidden network call {base}.{attr} found"
                    )


# ===========================================================================
# AI70: Hard-fail aggregates each missing-artifact gate
# ===========================================================================

class TestAI70HardFailAggregatesGates:
    def test_status_fail_closed_on_all_missing(self):
        r = _review().run_checklist(
            readonly_smoke=None, reconciliation=None, protection=None,
            contract=None, noop_plan=None, lifecycle_mock=None,
            real_permission_gate=None, tiny_entry_permission_gate=None,
            tiny_stop_permission_gate=None, tiny_cleanup_permission_gate=None,
            lifecycle_summary=None, runner_design=None, runner_dry_run=None,
            guarded_design_review=None, guarded_entry_adapter=None,
            guarded_stop_adapter=None, guarded_cleanup_adapter=None,
            guarded_lifecycle_summary=None,
            symbol="SOLUSDT", _now=_TEST_NOW,
        )
        assert r.status == STATUS_FAIL_CLOSED
        for gate in (
            GATE_READONLY_SMOKE_MISSING,
            GATE_RECONCILIATION_MISSING,
            GATE_PROTECTION_MISSING,
            GATE_CONTRACT_MISSING,
            GATE_NOOP_PLAN_MISSING,
            GATE_LIFECYCLE_MOCK_MISSING,
            GATE_REAL_PERMISSION_GATE_MISSING,
            GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
            GATE_TINY_STOP_PERMISSION_GATE_MISSING,
            GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
            GATE_LIFECYCLE_SUMMARY_MISSING,
            GATE_RUNNER_DESIGN_MISSING,
            GATE_RUNNER_DRY_RUN_MISSING,
            GATE_GUARDED_DESIGN_REVIEW_MISSING,
            GATE_GUARDED_ENTRY_ADAPTER_MISSING,
            GATE_GUARDED_STOP_ADAPTER_MISSING,
            GATE_GUARDED_CLEANUP_ADAPTER_MISSING,
            GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AI71: Real-entry-execution flag does not enable execution
# ===========================================================================

class TestAI71RealEntryExecutionDoesNotEnable:
    def test_does_not_enable(self):
        r = _run(allow_real_entry_execution=True)
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.send_allowed is False
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.no_secrets_loaded is True
        assert r.entry_execution_included is False
        assert r.stop_execution_included is False
        assert r.cleanup_execution_included is False
        assert r.full_lifecycle_execution_included is False


# ===========================================================================
# AI72: Review-approval flag does not enable execution
# ===========================================================================

class TestAI72ReviewApprovalDoesNotEnable:
    def test_does_not_enable(self):
        r = _run(allow_review_approval=True)
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.send_allowed is False
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.no_secrets_loaded is True
        assert r.entry_execution_included is False


# ===========================================================================
# AI73: All scope gates present in blocked_gates
# ===========================================================================

class TestAI73ScopeGatesPresent:
    def test_scope_gates(self):
        r = _run()
        for gate in (
            GATE_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_ONLY,
            GATE_PERMISSION_REVIEW_ONLY,
            GATE_ENTRY_EXECUTION_NOT_INCLUDED,
            GATE_STOP_EXECUTION_NOT_INCLUDED,
            GATE_CLEANUP_EXECUTION_NOT_INCLUDED,
            GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED,
            GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE,
            GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE,
            GATE_NO_ENDPOINT_INVOKED,
            GATE_NO_POSITION_MODIFIED_SCOPE,
            GATE_NO_SECRETS_LOADED,
            GATE_NO_G20_LIFT,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AI74: All entry-condition gates present in blocked_gates
# ===========================================================================

class TestAI74EntryConditionGatesPresent:
    def test_entry_condition_gates(self):
        r = _run()
        for gate in (
            GATE_ENTRY_SYMBOL_SOLUSDT,
            GATE_ENTRY_CATEGORY_LINEAR,
            GATE_ENTRY_SIDE_BUY,
            GATE_ENTRY_QTY_0_1,
            GATE_ENTRY_QTY_STEP_0_1,
            GATE_ENTRY_MIN_ORDER_QTY_0_1,
            GATE_ENTRY_TICK_SIZE_0_01,
            GATE_ENTRY_ESTIMATED_NOTIONAL_WITHIN_CAP,
            GATE_ENTRY_MAX_NOTIONAL_USDT_10,
            GATE_ENTRY_POSITION_IDX_ZERO,
            GATE_ENTRY_REDUCE_ONLY_FALSE,
            GATE_ENTRY_ORDER_TYPE_MARKET,
            GATE_ENTRY_DEMO_ENDPOINT_ONLY,
            GATE_NO_EXISTING_SOLUSDT_POSITION,
            GATE_EXISTING_PROTECTED_POSITIONS_DOCUMENTED,
            GATE_ENTRY_PROOF_STRENGTH_STRONG,
            GATE_ENTRY_ACCOUNT_MODE_DEMO,
            GATE_ENTRY_ENDPOINT_FAMILY_BYBIT_DEMO,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AI75: All envelope gates present in blocked_gates
# ===========================================================================

class TestAI75EnvelopeGatesPresent:
    def test_envelope_gates(self):
        r = _run()
        for gate in (
            GATE_ENTRY_REVIEW_ENVELOPE_PRESENT,
            GATE_ENVELOPE_PREVIEW_ONLY,
            GATE_ENVELOPE_SEND_ALLOWED_FALSE,
            GATE_ENVELOPE_ENDPOINT_CALLED_FALSE,
            GATE_ENVELOPE_REAL_PAYLOAD_FALSE,
            GATE_ENVELOPE_SIGNATURE_PRESENT_FALSE,
            GATE_ENVELOPE_PRIVATE_HEADERS_EMPTY,
            GATE_ENVELOPE_ENDPOINT_PATH_ORDER_CREATE,
            GATE_ENVELOPE_BASE_URL_DEMO_ONLY,
            GATE_ENVELOPE_SIDE_BUY,
            GATE_ENVELOPE_QTY_0_1,
            GATE_ENVELOPE_REDUCE_ONLY_FALSE,
            GATE_ENVELOPE_CLOSE_ON_TRIGGER_FALSE,
            GATE_ENVELOPE_POSITION_IDX_ZERO,
            GATE_ENVELOPE_ORDER_TYPE_MARKET,
            GATE_ENVELOPE_NO_SENDER_ADAPTER,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AI76: All post-entry-protection gates present in blocked_gates
# ===========================================================================

class TestAI76PostEntryProtectionGatesPresent:
    def test_post_entry_gates(self):
        r = _run()
        for gate in (
            GATE_STOP_ATTACH_REQUIRED,
            GATE_POST_ENTRY_STOP_LOSS_61_18,
            GATE_POST_ENTRY_TPSL_MODE_FULL,
            GATE_POST_ENTRY_SL_TRIGGER_BY_MARKPRICE,
            GATE_STOP_ATTACH_SEPARATE_MANUAL_BOUNDARY,
            GATE_NO_AUTOMATIC_STOP_ATTACH,
            GATE_CLEANUP_SEPARATE_MANUAL_BOUNDARY,
            GATE_NO_AUTOMATIC_CLEANUP,
            GATE_ENTRY_SUCCESS_NO_STOP_REQUIRES_MANUAL,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AI77: All failure / abort gates present in blocked_gates
# ===========================================================================

class TestAI77FailureGatesPresent:
    def test_failure_gates(self):
        r = _run()
        for gate in (
            GATE_REQUEST_REJECTED_FAIL_CLOSED,
            GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
            GATE_SELECTED_SYMBOL_EXISTS_FAIL_CLOSED,
            GATE_QTY_MISMATCH_FAIL_CLOSED,
            GATE_SIDE_MISMATCH_FAIL_CLOSED,
            GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED,
            GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED,
            GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW,
            GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED,
            GATE_SECRET_EMISSION_FAIL_CLOSED,
            GATE_NO_AUTO_RETRY,
            GATE_NO_AUTO_STOP_ATTACH_FAILURE,
            GATE_NO_AUTO_CLEANUP_FAILURE,
            GATE_NO_AUTO_EMERGENCY_CLOSE,
            GATE_NO_AUTO_NEXT_STEP,
            GATE_NO_BACKGROUND_LOOP,
            GATE_NO_CRON,
            GATE_NO_SCHEDULER,
            GATE_NO_DISCORD_TRIGGER,
            GATE_NO_NOTION_TRIGGER,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AI78: All documentation-sync gates present in blocked_gates
# ===========================================================================

class TestAI78DocumentationSyncGatesPresent:
    def test_documentation_sync_gates(self):
        r = _run()
        for gate in (
            GATE_README_SYNC_REQUIRED,
            GATE_NEXT_ACTION_SYNC_REQUIRED,
            GATE_COMMAND_LOG_SYNC_REQUIRED,
            GATE_FORBIDDEN_STATUS_SYNC_REQUIRED,
            GATE_NEXT_REQUIRED_TASK_SYNC_REQUIRED,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AI79: All manual-auth gates present in blocked_gates
# ===========================================================================

class TestAI79ManualAuthGatesPresent:
    def test_manual_auth_gates(self):
        r = _run()
        for gate in (
            GATE_ENTRY_TOKEN_PATTERN_PRESENT,
            GATE_TOKEN_NOT_VALIDATED,
            GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
            GATE_CONFIRMATION_FLAGS_DOCUMENTED,
            GATE_CONFIRMATION_FLAGS_NOT_VALIDATED,
            GATE_SECOND_CONFIRMATION_REQUIRED,
            GATE_MANUAL_BOUNDARY_REQUIRED,
            GATE_EXPECTED_ENTRY_SYMBOL_FLAG_DOCUMENTED,
            GATE_EXPECTED_ENTRY_QTY_FLAG_DOCUMENTED,
            GATE_EXPECTED_ENTRY_SIDE_FLAG_DOCUMENTED,
            GATE_EXPECTED_REDUCE_ONLY_FALSE_FLAG_DOCUMENTED,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AI80: Execution-guard gates present in blocked_gates
# ===========================================================================

class TestAI80ExecutionGuardGatesPresent:
    def test_execution_guard_gates(self):
        r = _run()
        for gate in (
            GATE_REAL_ENTRY_EXECUTION_NOT_IMPL,
            GATE_NO_REAL_ORDER_ENDPOINT,
            GATE_NO_REAL_STOP_ENDPOINT,
            GATE_NO_POSITION_MODIFIED,
            GATE_G20_NOT_LIFTED,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AI81: Acceptable status sets contain expected values
# ===========================================================================

class TestAI81AcceptableStatusSets:
    def test_sets_nonempty(self):
        assert "REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED" in ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES
        assert "TINY_LIFECYCLE_RUNNER_DESIGN_READY" in ACCEPTABLE_RUNNER_DESIGN_STATUSES
        assert "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY" in ACCEPTABLE_RUNNER_DRY_RUN_STATUSES
        assert "TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY" in ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES
        assert "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY" in ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES
        assert "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY" in ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES
        assert "TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY" in ACCEPTABLE_GUARDED_CLEANUP_ADAPTER_STATUSES
        assert "TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY" in ACCEPTABLE_GUARDED_LIFECYCLE_SUMMARY_STATUSES


# ===========================================================================
# AI82: Upstream status fields propagated to result
# ===========================================================================

class TestAI82UpstreamStatusFieldsExposed:
    def test_upstream_statuses_exposed(self):
        r = _run()
        assert r.upstream_lifecycle_summary_status == "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY"
        assert r.upstream_runner_design_status == "TINY_LIFECYCLE_RUNNER_DESIGN_READY"
        assert r.upstream_runner_dry_run_status == "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY"
        assert r.upstream_guarded_design_review_status == "TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY"
        assert r.upstream_guarded_entry_adapter_status == "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY"
        assert r.upstream_guarded_stop_adapter_status == "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY"
        assert r.upstream_guarded_cleanup_adapter_status == "TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY"
        assert r.upstream_guarded_lifecycle_summary_status == "TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY"
        assert r.upstream_guarded_lifecycle_summary_readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE


# ===========================================================================
# AI83: Timestamp override via _now param
# ===========================================================================

class TestAI83TimestampOverride:
    def test_now_override(self):
        custom = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        r = _run(_now=custom)
        assert r.timestamp_utc == "2030-01-02T03:04:05Z"
