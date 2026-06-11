"""
tests/demo_trading/test_demo_tiny_guarded_entry_manual_authorization_design.py
TASK-014AJ: Guarded Tiny Entry Manual Authorization Design tests (AJ1 - AJ81+).

Covers authorization_design_checklist / authorization_design_approval /
real_entry_execution_guard / fail_closed paths; all 10 stages; 147+ gate
constants; 19-artifact preflight contract (10 baseline + AA lifecycle
summary + AB runner design + AC runner dry-run + AD guarded design
review + AE guarded entry adapter + AF guarded stop-attach adapter +
AG guarded cleanup adapter + AH guarded lifecycle summary + AI guarded
entry real permission review); entry-execution design expectations
(SOLUSDT / linear / Buy / 0.1 / market / positionIdx 0 / reduceOnly
false / max_notional 10 / stopLoss 61.18); entry_token_pattern
(CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT) is documented only and
never validated; 13-flag required_human_confirmation_flags
documentation never validated; design-only template (no sender
adapter, signature_present False, private_headers empty, send_allowed
False); post-authorization stop / cleanup separate-manual-boundary
design (stop attach required True but never executed; cleanup
separate manual boundary True but never executed); failure / abort
design (FAIL_CLOSED / MANUAL_REVIEW_REQUIRED); documentation sync
plan; status precedence; source-scan safety (no urlopen / no
forbidden imports / no signing / no os.environ / no AA-AI module
reuse / no real sender); report artifacts; forbidden-flag absence
(--execute-real-* / --send-order / --place-order / --real-run /
--confirm-token); the invariant that TASK-014L sender G20
(protected_entry_policy_missing) still blocks --execute-new-entry and
is NOT lifted here; next_required_task points at
TASK-014AK_guarded_entry_manual_authorization_dry_run.
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

from src.demo_tiny_guarded_entry_manual_authorization_design import (
    ACCEPTABLE_ENTRY_REAL_PERMISSION_REVIEW_STATUSES,
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
    DESIGN_EXPECTED_CATEGORY,
    DESIGN_EXPECTED_CLOSE_ON_TRIGGER,
    DESIGN_EXPECTED_ENTRY_REFERENCE,
    DESIGN_EXPECTED_ENTRY_SIDE,
    DESIGN_EXPECTED_ESTIMATED_NOTIONAL,
    DESIGN_EXPECTED_EXISTING_COUNT,
    DESIGN_EXPECTED_MAX_NOTIONAL_USDT,
    DESIGN_EXPECTED_MIN_ORDER_QTY,
    DESIGN_EXPECTED_ORDER_TYPE,
    DESIGN_EXPECTED_POSITION_IDX,
    DESIGN_EXPECTED_QTY,
    DESIGN_EXPECTED_QTY_STEP,
    DESIGN_EXPECTED_REDUCE_ONLY,
    DESIGN_EXPECTED_SL_TRIGGER_BY,
    DESIGN_EXPECTED_STOP_LOSS,
    DESIGN_EXPECTED_SYMBOL,
    DESIGN_EXPECTED_TICK_SIZE,
    DESIGN_EXPECTED_TPSL_MODE,
    DemoTinyGuardedEntryManualAuthorizationDesign,
    ENTRY_DESIGN_ORDER_LINK_ID_PREFIXES,
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
    GATE_AUTHORIZATION_DESIGN_ONLY,
    GATE_BOUNDARY_SL_TRIGGER_BY_MARKPRICE,
    GATE_BOUNDARY_STOP_LOSS_61_18,
    GATE_BOUNDARY_TPSL_MODE_FULL,
    GATE_CLEANUP_EXECUTION_NOT_INCLUDED,
    GATE_CLEANUP_SEPARATE_MANUAL_AUTH,
    GATE_COMMAND_LOG_SYNC_REQUIRED,
    GATE_CONFIRM_CLEANUP_MANUAL_BOUNDARY_FLAG,
    GATE_CONFIRM_EXISTING_COUNT_FLAG,
    GATE_CONFIRM_EXISTING_SYMBOLS_FLAG,
    GATE_CONFIRM_MAX_NOTIONAL_FLAG,
    GATE_CONFIRM_ORDER_TYPE_FLAG,
    GATE_CONFIRM_POSITION_IDX_FLAG,
    GATE_CONFIRM_QTY_FLAG,
    GATE_CONFIRM_REDUCE_ONLY_FALSE_FLAG,
    GATE_CONFIRM_SIDE_FLAG,
    GATE_CONFIRM_STOP_LOSS_FLAG,
    GATE_CONFIRM_STOP_REQUIRED_FLAG,
    GATE_CONFIRM_SYMBOL_FLAG,
    GATE_CONTRACT_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_EXECUTION_NOT_INCLUDED,
    GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING,
    GATE_ENTRY_REAL_PERMISSION_REVIEW_READINESS_EXECUTABLE,
    GATE_ENTRY_REAL_PERMISSION_REVIEW_STATUS_UNACCEPTABLE,
    GATE_ENTRY_SUCCESS_DOES_NOT_AUTO_ATTACH_STOP,
    GATE_ENTRY_SUCCESS_WITHOUT_STOP_MANUAL_REVIEW,
    GATE_ESTIMATED_NOTIONAL_WITHIN_CAP,
    GATE_FLAGS_NOT_VALIDATED,
    GATE_FORBIDDEN_STATUS_SYNC_REQUIRED,
    GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED,
    GATE_G20_NOT_LIFTED,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_GUARDED_CLEANUP_ADAPTER_MISSING,
    GATE_GUARDED_DESIGN_REVIEW_MISSING,
    GATE_GUARDED_ENTRY_ADAPTER_MISSING,
    GATE_GUARDED_ENTRY_MANUAL_AUTH_DESIGN_ONLY,
    GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING,
    GATE_GUARDED_STOP_ADAPTER_MISSING,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_LIFECYCLE_SUMMARY_MISSING,
    GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED,
    GATE_MANUAL_BOUNDARY_REQUIRED,
    GATE_MISSING_FLAG_FAIL_CLOSED,
    GATE_NEXT_ACTION_SYNC_REQUIRED,
    GATE_NEXT_REQUIRED_TASK_SYNC_REQUIRED,
    GATE_NOOP_PLAN_MISSING,
    GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED,
    GATE_NO_AUTO_CLEANUP_FAILURE,
    GATE_NO_AUTO_EMERGENCY_CLOSE,
    GATE_NO_AUTO_NEXT_STEP,
    GATE_NO_AUTO_RETRY,
    GATE_NO_AUTO_STOP_ATTACH_FAILURE,
    GATE_NO_BACKGROUND_LOOP,
    GATE_NO_CRON,
    GATE_NO_DISCORD_TRIGGER,
    GATE_NO_ENDPOINT_INVOKED,
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
    GATE_PERMISSION_REVIEW_ONLY,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW,
    GATE_PROTECTION_MISSING,
    GATE_QTY_MISMATCH_FAIL_CLOSED,
    GATE_README_SYNC_REQUIRED,
    GATE_READONLY_SMOKE_MISSING,
    GATE_READONLY_STALE_FAIL_CLOSED,
    GATE_REAL_ENTRY_EXECUTION_NOT_IMPL,
    GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE,
    GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_RECONCILIATION_MISSING,
    GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED,
    GATE_REQUIRED_FLAGS_DOCUMENTED,
    GATE_RUNNER_DESIGN_MISSING,
    GATE_RUNNER_DRY_RUN_MISSING,
    GATE_SECOND_CONFIRMATION_REQUIRED,
    GATE_SECRET_EMISSION_FAIL_CLOSED,
    GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
    GATE_SIDE_MISMATCH_FAIL_CLOSED,
    GATE_SOLUSDT_EXISTS_FAIL_CLOSED,
    GATE_STOP_ATTACH_FAIL_MANUAL_REVIEW,
    GATE_STOP_ATTACH_SEPARATE_MANUAL_AUTH,
    GATE_STOP_EXECUTION_NOT_INCLUDED,
    GATE_TEMPLATE_BASE_URL_DEMO_ONLY,
    GATE_TEMPLATE_CLOSE_ON_TRIGGER_FALSE,
    GATE_TEMPLATE_DESIGN_ONLY,
    GATE_TEMPLATE_ENDPOINT_CALLED_FALSE,
    GATE_TEMPLATE_ENDPOINT_PATH_ORDER_CREATE,
    GATE_TEMPLATE_NO_SENDER_ADAPTER,
    GATE_TEMPLATE_ORDER_LINK_ID_PREFIX_DOCUMENTED,
    GATE_TEMPLATE_ORDER_TYPE_MARKET,
    GATE_TEMPLATE_POSITION_IDX_ZERO,
    GATE_TEMPLATE_PRESENT,
    GATE_TEMPLATE_PREVIEW_ONLY,
    GATE_TEMPLATE_PRIVATE_HEADERS_EMPTY,
    GATE_TEMPLATE_QTY_0_1,
    GATE_TEMPLATE_REAL_PAYLOAD_FALSE,
    GATE_TEMPLATE_REDUCE_ONLY_FALSE,
    GATE_TEMPLATE_SEND_ALLOWED_FALSE,
    GATE_TEMPLATE_SIDE_BUY,
    GATE_TEMPLATE_SIGNATURE_PRESENT_FALSE,
    GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
    GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
    GATE_TINY_STOP_PERMISSION_GATE_MISSING,
    GATE_TOKEN_EXPIRY_DOCUMENTED,
    GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
    GATE_TOKEN_INCLUDES_DATE,
    GATE_TOKEN_INCLUDES_SYMBOL,
    GATE_TOKEN_NOT_VALIDATED,
    GATE_TOKEN_NO_SECRET,
    GATE_TOKEN_PATTERN_PRESENT,
    GATE_TOKEN_REUSE_FORBIDDEN,
    LIVE_ENDPOINT_DENYLIST,
    MODE_AUTHORIZATION_DESIGN_APPROVAL,
    MODE_AUTHORIZATION_DESIGN_CHECKLIST,
    MODE_FAIL_CLOSED,
    MODE_REAL_ENTRY_EXECUTION_GUARD,
    ORDER_CREATE_PATH_REF,
    READINESS_CONCLUSION_NOT_EXECUTABLE,
    REQUIRED_HUMAN_CONFIRMATION_FLAGS,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_MANUAL_AUTHORIZATION_DESIGN_SCOPE,
    STAGE_2_AUTHORIZATION_TOKEN_DESIGN,
    STAGE_3_REQUIRED_HUMAN_CONFIRMATION_FLAGS,
    STAGE_4_PRE_EXECUTION_READINESS_CHECKLIST_DESIGN,
    STAGE_5_ENTRY_EXECUTION_REQUEST_TEMPLATE_DESIGN,
    STAGE_6_POST_AUTHORIZATION_STOP_CLEANUP_BOUNDARY,
    STAGE_7_FAILURE_AND_ABORT_DESIGN,
    STAGE_8_DOCUMENTATION_SYNC_REVIEW,
    STAGE_9_FINAL_MANUAL_AUTHORIZATION_DESIGN_VERDICT,
    STATUS_DESIGN_READY,
    STATUS_DESIGN_READY_EXEC_DISABLED,
    STATUS_FAIL_CLOSED,
    STATUS_REAL_ENTRY_NOT_IMPL,
    TRADING_STOP_PATH_REF,
    TinyGuardedEntryManualAuthorizationDesignResult,
)


_MODULE_PATH = ROOT / "src" / "demo_tiny_guarded_entry_manual_authorization_design.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_tiny_guarded_entry_manual_authorization_design.py"
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
        "selected_qty":           DESIGN_EXPECTED_QTY,
        "entry_reference_price":  DESIGN_EXPECTED_ENTRY_REFERENCE,
        "stop_price":             DESIGN_EXPECTED_STOP_LOSS,
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
        "tiny_qty":                  DESIGN_EXPECTED_QTY,
        "tiny_notional":             DESIGN_EXPECTED_ESTIMATED_NOTIONAL,
        "entry_reference_price":     DESIGN_EXPECTED_ENTRY_REFERENCE,
        "stop_price":                DESIGN_EXPECTED_STOP_LOSS,
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


def _valid_entry_real_permission_review() -> dict:
    return {
        "timestamp_utc":             "2026-06-11T11:59:59.99Z",
        "mode":                      "permission_review_checklist",
        "selected_symbol":           "SOLUSDT",
        "status":                    "TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY",
        "readiness_conclusion":      READINESS_CONCLUSION_NOT_EXECUTABLE,
        "real_execution_allowed":              False,
        "real_entry_implemented":              False,
        "guarded_entry_real_permission_review": True,
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


def _design() -> DemoTinyGuardedEntryManualAuthorizationDesign:
    return DemoTinyGuardedEntryManualAuthorizationDesign()


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
    entry_real_permission_review=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    allow_design_approval=False,
    allow_real_entry_execution=False,
    _now=_TEST_NOW,
) -> TinyGuardedEntryManualAuthorizationDesignResult:
    return _design().run_checklist(
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
        entry_real_permission_review=_valid_entry_real_permission_review()       if entry_real_permission_review   is _UNSET else entry_real_permission_review,
        symbol=symbol,
        allow_design_approval=allow_design_approval,
        allow_real_entry_execution=allow_real_entry_execution,
        _now=_now,
    )


# ===========================================================================
# AJ1: valid checklist => TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DESIGN_READY
# ===========================================================================

class TestAJ1DesignReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_DESIGN_READY
        assert r.mode == MODE_AUTHORIZATION_DESIGN_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.guarded_entry_manual_authorization_design is True
        assert r.authorization_design_only is True
        assert r.permission_review_only is True
        assert r.entry_execution_included is False
        assert r.stop_execution_included is False
        assert r.cleanup_execution_included is False
        assert r.full_lifecycle_execution_included is False
        assert r.current_task_real_execution_allowed is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.next_required_task == "TASK-014AK_guarded_entry_manual_authorization_dry_run"


# ===========================================================================
# AJ2: --allow-design-approval => READY_BUT_EXECUTION_DISABLED
# ===========================================================================

class TestAJ2DesignApproval:
    def test_approval(self):
        r = _run(allow_design_approval=True)
        assert r.status == STATUS_DESIGN_READY_EXEC_DISABLED
        assert r.mode == MODE_AUTHORIZATION_DESIGN_APPROVAL
        assert r.design_approval_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE


# ===========================================================================
# AJ3: --allow-real-entry-execution => REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
# ===========================================================================

class TestAJ3RealEntryExecutionGuard:
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
# AJ4-AJ22: 19 missing upstream artifacts each => FAIL_CLOSED
# ===========================================================================

class TestAJ4MissingReadonly:
    def test_fail_closed(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert r.failed_stage == STAGE_0_ARTIFACT_PREFLIGHT
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestAJ5MissingReconciliation:
    def test_fail_closed(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestAJ6MissingProtection:
    def test_fail_closed(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestAJ7MissingContract:
    def test_fail_closed(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestAJ8MissingNoopPlan:
    def test_fail_closed(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestAJ9MissingLifecycle:
    def test_fail_closed(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestAJ10MissingRealPermissionGate:
    def test_fail_closed(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAJ11MissingTinyEntryPermissionGate:
    def test_fail_closed(self):
        r = _run(tiny_entry_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAJ12MissingTinyStopPermissionGate:
    def test_fail_closed(self):
        r = _run(tiny_stop_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAJ13MissingTinyCleanupPermissionGate:
    def test_fail_closed(self):
        r = _run(tiny_cleanup_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAJ14MissingLifecycleSummary:
    def test_fail_closed(self):
        r = _run(lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAJ15MissingRunnerDesign:
    def test_fail_closed(self):
        r = _run(runner_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DESIGN_MISSING in r.blocked_gates


class TestAJ16MissingRunnerDryRun:
    def test_fail_closed(self):
        r = _run(runner_dry_run=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DRY_RUN_MISSING in r.blocked_gates


class TestAJ17MissingGuardedDesignReview:
    def test_fail_closed(self):
        r = _run(guarded_design_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_MISSING in r.blocked_gates


class TestAJ18MissingGuardedEntryAdapter:
    def test_fail_closed(self):
        r = _run(guarded_entry_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_ENTRY_ADAPTER_MISSING in r.blocked_gates


class TestAJ19MissingGuardedStopAdapter:
    def test_fail_closed(self):
        r = _run(guarded_stop_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_STOP_ADAPTER_MISSING in r.blocked_gates


class TestAJ20MissingGuardedCleanupAdapter:
    def test_fail_closed(self):
        r = _run(guarded_cleanup_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_CLEANUP_ADAPTER_MISSING in r.blocked_gates


class TestAJ21MissingGuardedLifecycleSummary:
    def test_fail_closed(self):
        r = _run(guarded_lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAJ22MissingEntryRealPermissionReview:
    def test_fail_closed(self):
        r = _run(entry_real_permission_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING in r.blocked_gates


# ===========================================================================
# AJ23: Symbol not SOLUSDT => FAIL_CLOSED
# ===========================================================================

class TestAJ23SymbolNotSolusdt:
    @pytest.mark.parametrize("bad_symbol", [
        "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT",
        "BTCUSDT", "ETHUSDT", "foo",
    ])
    def test_fail_closed(self, bad_symbol):
        r = _run(symbol=bad_symbol)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in r.blocked_gates


# ===========================================================================
# AJ24-AJ27: invariant mismatches
# ===========================================================================

class TestAJ24EndpointFamilyMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["endpoint_family"] = "bybit_live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestAJ25AccountModeMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["account_mode"] = "live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestAJ26ProofStrengthMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["proof_strength"] = "WEAK"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROOF_STRENGTH_NOT_STRONG in r.blocked_gates


class TestAJ27PositionDetailsSourceMismatch:
    def test_fail_closed(self):
        bad = _valid_reconciliation()
        bad["mode"] = "fake"
        bad["position_details_source"] = "fake"
        r = _run(recon=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY in r.blocked_gates


# ===========================================================================
# AJ28: Entry real permission review status not acceptable
# ===========================================================================

class TestAJ28EntryRealPermissionReviewStatusUnacceptable:
    def test_fail_closed(self):
        bad = _valid_entry_real_permission_review()
        bad["status"] = "REVIEW_FAIL_CLOSED"
        r = _run(entry_real_permission_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_REAL_PERMISSION_REVIEW_STATUS_UNACCEPTABLE in r.blocked_gates


# ===========================================================================
# AJ29: Entry real permission review readiness must be NOT_EXECUTABLE
# ===========================================================================

class TestAJ29EntryRealPermissionReviewReadinessExecutable:
    def test_fail_closed(self):
        bad = _valid_entry_real_permission_review()
        bad["readiness_conclusion"] = "READY_TO_EXECUTE"
        r = _run(entry_real_permission_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_REAL_PERMISSION_REVIEW_READINESS_EXECUTABLE in r.blocked_gates


# ===========================================================================
# AJ30: 10 stages must all be present
# ===========================================================================

class TestAJ30TenStages:
    def test_all_10_stages(self):
        r = _run()
        assert len(r.stages) == 10
        for stage_id in (
            STAGE_0_ARTIFACT_PREFLIGHT,
            STAGE_1_MANUAL_AUTHORIZATION_DESIGN_SCOPE,
            STAGE_2_AUTHORIZATION_TOKEN_DESIGN,
            STAGE_3_REQUIRED_HUMAN_CONFIRMATION_FLAGS,
            STAGE_4_PRE_EXECUTION_READINESS_CHECKLIST_DESIGN,
            STAGE_5_ENTRY_EXECUTION_REQUEST_TEMPLATE_DESIGN,
            STAGE_6_POST_AUTHORIZATION_STOP_CLEANUP_BOUNDARY,
            STAGE_7_FAILURE_AND_ABORT_DESIGN,
            STAGE_8_DOCUMENTATION_SYNC_REVIEW,
            STAGE_9_FINAL_MANUAL_AUTHORIZATION_DESIGN_VERDICT,
        ):
            assert stage_id in r.stages

    def test_stage_order_match(self):
        r = _run()
        assert tuple(r.stage_order) == ALL_STAGES


# ===========================================================================
# AJ31: stage_1_manual_authorization_design_scope
# ===========================================================================

class TestAJ31AuthorizationDesignScope:
    def test_scope_present(self):
        r = _run()
        s = r.authorization_design_scope
        assert s["guarded_entry_manual_authorization_design"] is True
        assert s["authorization_design_only"] is True
        assert s["permission_review_only"] is True
        assert s["entry_execution_included"] is False
        assert s["stop_execution_included"] is False
        assert s["cleanup_execution_included"] is False
        assert s["full_lifecycle_execution_included"] is False
        assert s["real_entry_implemented"] is False
        assert s["real_execution_allowed"] is False
        assert s["order_endpoint_called"] is False
        assert s["stop_endpoint_called"] is False
        assert s["no_endpoint_invoked_in_this_task"] is True
        assert s["no_position_modified"] is True
        assert s["no_secrets_loaded"] is True
        assert s["g20_policy_still_in_place"] is True
        assert s["g20_lifted"] is False
        assert s["next_required_task"] == "TASK-014AK_guarded_entry_manual_authorization_dry_run"


# ===========================================================================
# AJ32: stage_2_authorization_token_design -- documented only, never validated
# ===========================================================================

class TestAJ32AuthorizationTokenDesign:
    def test_token_design_present(self):
        r = _run()
        t = r.authorization_token_design
        assert t["token_pattern"] == ENTRY_TOKEN_PATTERN
        assert t["token_validated"] is False
        assert t["token_format_not_authorization"] is True
        assert t["token_must_be_single_use"] is True
        assert t["token_must_include_date"] is True
        assert t["token_must_include_symbol"] is True
        assert t["token_must_not_include_secret"] is True
        assert t["token_must_not_be_logged_as_secret"] is True
        assert t["tokens_not_validated_in_this_task"] is True
        assert t["tokens_never_treated_as_authorization_in_this_task"] is True

    def test_token_pattern_includes_symbol(self):
        assert "SOLUSDT" in ENTRY_TOKEN_PATTERN
        assert "YYYYMMDD" in ENTRY_TOKEN_PATTERN
        assert ENTRY_TOKEN_PATTERN == "CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT"


# ===========================================================================
# AJ33: stage_3_required_human_confirmation_flags -- 13 flags, never validated
# ===========================================================================

class TestAJ33RequiredHumanConfirmationFlags:
    def test_thirteen_flags(self):
        assert isinstance(REQUIRED_HUMAN_CONFIRMATION_FLAGS, tuple)
        assert len(REQUIRED_HUMAN_CONFIRMATION_FLAGS) == 13
        assert tuple(REQUIRED_HUMAN_CONFIRMATION_FLAGS) == REQUIRED_HUMAN_CONFIRMATION_FLAGS

    def test_required_flags_present(self):
        joined = " ".join(REQUIRED_HUMAN_CONFIRMATION_FLAGS)
        for flag_token in (
            "--i-understand-this-is-demo-real-execution",
            "--confirm-symbol",
            "--confirm-side",
            "--confirm-qty",
            "--confirm-max-notional-usdt",
            "--confirm-existing-position-count",
            "--confirm-existing-symbols",
            "--confirm-reduce-only",
            "--confirm-position-idx",
            "--confirm-order-type",
            "--confirm-stop-required-after-entry",
            "--confirm-stop-loss",
            "--confirm-cleanup-manual-boundary",
        ):
            assert flag_token in joined, f"Missing required flag {flag_token!r}"

    def test_flags_documented_never_validated(self):
        r = _run()
        flags = r.required_human_confirmation_flags
        assert isinstance(flags, dict)
        assert flags.get("flags_documented") is True
        assert flags.get("flags_validated") is False
        assert list(flags.get("required_flags", [])) == list(REQUIRED_HUMAN_CONFIRMATION_FLAGS)


# ===========================================================================
# AJ34: stage_4_pre_execution_readiness_checklist_design
# ===========================================================================

class TestAJ34PreExecutionReadinessChecklistDesign:
    def test_checklist_design(self):
        r = _run()
        p = r.pre_execution_readiness_checklist_design
        assert p["git_commit_hash_must_match_expected"] is True
        assert p["readme_current"] is True
        assert p["next_action_current"] is True
        assert p["command_log_current"] is True
        assert p["latest_readonly_timestamp_recent"] is True
        assert p["protected_positions_unchanged"] is True
        assert set(p["protected_position_symbols"]) == set(EXISTING_POSITION_SYMBOLS)
        assert p["solusdt_absent_before_entry"] is True
        assert p["estimated_notional_usdt"] == DESIGN_EXPECTED_ESTIMATED_NOTIONAL
        assert p["max_notional_usdt"] == DESIGN_EXPECTED_MAX_NOTIONAL_USDT
        assert p["estimated_notional_within_cap"] is True
        assert p["qty"] == DESIGN_EXPECTED_QTY
        assert p["side"] == DESIGN_EXPECTED_ENTRY_SIDE
        assert p["reduce_only"] is False
        assert p["stop_attach_plan_ready"] is True
        assert p["cleanup_plan_ready"] is True
        assert p["discord_must_not_trigger_execution"] is True
        assert p["notion_must_not_trigger_execution"] is True
        assert p["no_cron_or_background_automation"] is True
        assert p["checklist_designed_only"] is True
        assert p["checklist_executed_in_this_task"] is False


# ===========================================================================
# AJ35: stage_5_entry_execution_request_template_design
# ===========================================================================

class TestAJ35EntryExecutionRequestTemplateDesign:
    def test_template_design(self):
        r = _run()
        t = r.entry_execution_request_template_design
        assert t["preview_only"] is True
        assert t["design_only"] is True
        assert t["send_allowed"] is False
        assert t["endpoint_called"] is False
        assert t["real_payload"] is False
        assert t["signature_present"] is False
        assert t["private_headers"] == []
        assert t["endpoint_path_ref"] == ORDER_CREATE_PATH_REF
        assert t["base_url_ref"] == BASE_URL_DEMO_REF
        assert tuple(t["demo_endpoint_allowlist"]) == DEMO_ENDPOINT_ALLOWLIST
        assert tuple(t["live_endpoint_denylist"]) == LIVE_ENDPOINT_DENYLIST
        assert t["category"] == DESIGN_EXPECTED_CATEGORY
        assert t["symbol"] == DESIGN_EXPECTED_SYMBOL
        assert t["side"] == DESIGN_EXPECTED_ENTRY_SIDE
        assert t["orderType"] == DESIGN_EXPECTED_ORDER_TYPE
        assert t["qty"] == DESIGN_EXPECTED_QTY
        assert t["reduceOnly"] is False
        assert t["closeOnTrigger"] is False
        assert t["positionIdx"] == DESIGN_EXPECTED_POSITION_IDX
        assert list(t["orderLinkId_prefixes"]) == list(ENTRY_DESIGN_ORDER_LINK_ID_PREFIXES)
        assert t["sender_adapter_invoked"] is False
        assert t["no_sender_adapter"] is True
        assert t["real_payload_conversion"] is False
        assert t["template_not_sent_in_this_task"] is True


# ===========================================================================
# AJ36: stage_6_post_authorization_stop_cleanup_boundary
# ===========================================================================

class TestAJ36PostAuthorizationStopCleanupBoundary:
    def test_boundary_design(self):
        r = _run()
        b = r.post_authorization_stop_cleanup_boundary_design
        assert b["entry_success_does_not_auto_attach_stop"] is True
        assert b["stop_attach_separate_manual_authorization"] is True
        assert b["stop_loss"] == DESIGN_EXPECTED_STOP_LOSS
        assert b["tpsl_mode"] == DESIGN_EXPECTED_TPSL_MODE
        assert b["sl_trigger_by"] == DESIGN_EXPECTED_SL_TRIGGER_BY
        assert b["cleanup_separate_manual_authorization"] is True
        assert b["no_automatic_cleanup"] is True
        assert b["no_automatic_emergency_close"] is True
        assert b["entry_success_without_stop_attach_manual_review"] is True
        assert b["stop_attach_fail_manual_review"] is True
        assert b["cleanup_needs_separate_manual_boundary_only"] is True
        assert b["stop_attach_executed_in_this_task"] is False
        assert b["cleanup_executed_in_this_task"] is False


# ===========================================================================
# AJ37: stage_7_failure_and_abort_design
# ===========================================================================

class TestAJ37FailureAndAbortDesign:
    def test_design_present(self):
        r = _run()
        f = r.failure_and_abort_design
        assert f["missing_flag"] == "FAIL_CLOSED"
        assert f["token_mismatch"] == "FAIL_CLOSED"
        assert f["token_reused"] == "FAIL_CLOSED"
        assert f["readonly_stale"] == "FAIL_CLOSED"
        assert f["solusdt_already_exists"] == "FAIL_CLOSED"
        assert f["protected_position_mismatch"] == "MANUAL_REVIEW_REQUIRED"
        assert f["notional_cap_exceeded"] == "FAIL_CLOSED"
        assert f["qty_mismatch"] == "FAIL_CLOSED"
        assert f["side_mismatch"] == "FAIL_CLOSED"
        assert f["reduce_only_mismatch"] == "FAIL_CLOSED"
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
# AJ38: stage_8_documentation_sync_review
# ===========================================================================

class TestAJ38DocumentationSyncReview:
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
        assert d["next_required_task"] == "TASK-014AK_guarded_entry_manual_authorization_dry_run"
        assert d["documentation_only_plan"] is True
        assert d["markdown_read_in_this_module"] is False


# ===========================================================================
# AJ39: stage_9_final_manual_authorization_design_verdict
# ===========================================================================

class TestAJ39FinalManualAuthorizationDesignVerdict:
    def test_verdict_present(self):
        r = _run()
        v = r.final_manual_authorization_design_verdict
        assert v["design_approval_allowed"] is False
        assert v["real_entry_execution_requested"] is False
        assert v["real_execution_allowed"] is False
        assert v["real_entry_implemented"] is False
        assert v["guarded_entry_manual_authorization_design"] is True
        assert v["authorization_design_only"] is True
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
        assert v["status"] == STATUS_DESIGN_READY
        assert v["mode"] == MODE_AUTHORIZATION_DESIGN_CHECKLIST
        assert v["next_required_task"] == "TASK-014AK_guarded_entry_manual_authorization_dry_run"


# ===========================================================================
# AJ40: audit_artifacts must aggregate all stage outputs (sanitized)
# ===========================================================================

class TestAJ40AuditArtifacts:
    def test_audit_artifacts(self):
        r = _run()
        a = r.audit_artifacts
        for key in (
            "authorization_design_scope",
            "authorization_token_design",
            "required_human_confirmation_flags",
            "pre_execution_readiness_checklist_design",
            "entry_execution_request_template_design",
            "post_authorization_stop_cleanup_boundary_design",
            "failure_and_abort_design",
            "documentation_sync_review",
            "final_manual_authorization_design_verdict",
        ):
            assert key in a
        assert a["response_status"] == "DESIGN_NOT_SENT"
        assert a["response_from_exchange"] is False
        assert a["sanitized"] is True
        assert a["no_secrets"] is True
        assert tuple(a["forbidden_log_fields"]) == FORBIDDEN_LOG_FIELDS


# ===========================================================================
# AJ41: to_dict() deep-copy independence
# ===========================================================================

class TestAJ41ToDictDeepCopy:
    def test_deep_copy(self):
        r = _run()
        d1 = r.to_dict()
        d1["authorization_design_scope"]["mutated"] = True
        d2 = r.to_dict()
        assert "mutated" not in d2["authorization_design_scope"]
        d1["blocked_gates"].append("FAKE_GATE")
        assert "FAKE_GATE" not in r.blocked_gates


# ===========================================================================
# AJ42: status precedence -- hard-fail beats every flag combination
# ===========================================================================

class TestAJ42StatusPrecedenceHardFailWins:
    @pytest.mark.parametrize("flags", [
        {},
        {"allow_design_approval": True},
        {"allow_real_entry_execution": True},
        {"allow_design_approval": True, "allow_real_entry_execution": True},
    ])
    def test_hard_fail_overrides(self, flags):
        r = _run(readonly=None, **flags)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED


# ===========================================================================
# AJ43: status precedence -- real-entry-execution-guard beats design-approval
# ===========================================================================

class TestAJ43StatusPrecedenceRealEntryBeatsApproval:
    def test_real_entry_beats_approval(self):
        r = _run(allow_design_approval=True, allow_real_entry_execution=True)
        assert r.status == STATUS_REAL_ENTRY_NOT_IMPL
        assert r.mode == MODE_REAL_ENTRY_EXECUTION_GUARD


# ===========================================================================
# AJ44: acceptable upstream status whitelists
# ===========================================================================

class TestAJ44AcceptableStatuses:
    @pytest.mark.parametrize("status", list(ACCEPTABLE_ENTRY_REAL_PERMISSION_REVIEW_STATUSES))
    def test_accepted_entry_review(self, status):
        good = _valid_entry_real_permission_review()
        good["status"] = status
        r = _run(entry_real_permission_review=good)
        assert r.status == STATUS_DESIGN_READY
        assert GATE_ENTRY_REAL_PERMISSION_REVIEW_STATUS_UNACCEPTABLE not in r.blocked_gates

    @pytest.mark.parametrize("status", list(ACCEPTABLE_GUARDED_LIFECYCLE_SUMMARY_STATUSES))
    def test_accepted_lifecycle_summary(self, status):
        good = _valid_guarded_lifecycle_summary()
        good["status"] = status
        r = _run(guarded_lifecycle_summary=good)
        assert r.status == STATUS_DESIGN_READY


# ===========================================================================
# AJ45: G20 invariants -- never lifted regardless of flag combinations
# ===========================================================================

class TestAJ45G20Invariants:
    @pytest.mark.parametrize("flags", [
        {},
        {"allow_design_approval": True},
        {"allow_real_entry_execution": True},
    ])
    def test_g20_in_place(self, flags):
        r = _run(**flags)
        assert r.g20_policy_still_in_place is True
        assert r.g20_lifted is False


# ===========================================================================
# AJ46: existing demo positions never touched
# ===========================================================================

class TestAJ46ExistingPositionsUntouched:
    def test_existing_positions_invariant(self):
        r = _run()
        assert r.existing_positions_touched == []
        assert isinstance(r.existing_positions_touched, list)
        assert tuple(EXISTING_POSITION_SYMBOLS) == (
            "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"
        )
        assert sorted(r.existing_position_symbols) == sorted(EXISTING_POSITION_SYMBOLS)


# ===========================================================================
# AJ47: no endpoint invoked, no live endpoint
# ===========================================================================

class TestAJ47NoEndpointInvocation:
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
# AJ48: no secrets loaded
# ===========================================================================

class TestAJ48NoSecretsLoaded:
    def test_no_secrets(self):
        r = _run()
        assert r.no_secrets_loaded is True
        assert r.secret_value_observed is False

    def test_forbidden_log_fields(self):
        assert "api_key_value" in FORBIDDEN_LOG_FIELDS
        assert "api_secret_value" in FORBIDDEN_LOG_FIELDS
        assert "signature_value" in FORBIDDEN_LOG_FIELDS


# ===========================================================================
# AJ49: source scan -- no forbidden imports / no live endpoint / no signing
# ===========================================================================

class TestAJ49SourceScanForbiddenImports:
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
            "src.demo_tiny_guarded_entry_real_permission_review",
            "BybitExecutor",
            "main.execute_new_entry",
            "src.risk",
        ):
            assert tok not in code, f"Forbidden source-module reference {tok!r} found in module"


# ===========================================================================
# AJ50: live endpoint reference is string-only
# ===========================================================================

class TestAJ50LiveEndpointReferenceOnly:
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
# AJ51: CLI script -- no forbidden execute/send/place/real-run flags exposed
# ===========================================================================

class TestAJ51CLIForbiddenFlags:
    def test_no_real_execution_flag(self):
        code = _read_code_only(_SCRIPT_PATH)
        for tok in (
            "--execute-real-entry", "--execute-real-stop", "--execute-real-cleanup",
            "--execute-real-lifecycle", "--send-order", "--place-order", "--real-run",
            "--execute-new-entry", "--confirm-token",
        ):
            assert tok not in code, f"Forbidden CLI flag {tok!r} found in preview script"

    def test_no_real_runner_invocation(self):
        code = _read_code_only(_SCRIPT_PATH)
        for tok in ("BybitExecutor", "live_executor", "send_real_order"):
            assert tok not in code


# ===========================================================================
# AJ52: CLI script exposes 19 --from-latest-* flags + 4 control flags
# ===========================================================================

class TestAJ52CLIArgs:
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
            "--from-latest-entry-real-permission-review",
            "--symbol",
            "--allow-design-approval",
            "--allow-real-entry-execution",
            "--write-report",
        ):
            assert flag in text, f"Expected CLI flag {flag!r} missing from preview script"


# ===========================================================================
# AJ53/AJ54/AJ55/AJ56: CLI via importlib
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
    _write_artifact(base / "tiny_guarded_entry_real_permission_review", "latest_tiny_guarded_entry_real_permission_review.json",        _valid_entry_real_permission_review())


def _load_cli_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("aj_preview_cli", str(_SCRIPT_PATH))
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
        entry_real_permission_review_dir=base / "tiny_guarded_entry_real_permission_review",
    )


import tempfile as _tempfile
import shutil as _shutil


def _mk_base():
    return Path(_tempfile.mkdtemp(prefix="aj_cli_"))


class TestAJ53CLIChecklistExitZero:
    def test_run_via_run_execute(self):
        mod = _load_cli_module()
        base = _mk_base()
        try:
            _materialize_full_tree(base)
            rc = mod.run_execute(
                symbol="SOLUSDT",
                allow_design_approval=False,
                allow_real_entry_execution=False,
                write_report=False,
                output_dir=base / "tiny_guarded_entry_manual_authorization_design",
                **_cli_kwargs(base),
            )
            assert rc == 0
        finally:
            _shutil.rmtree(base, ignore_errors=True)


class TestAJ54CLIWriteReport:
    def test_write_report(self):
        mod = _load_cli_module()
        base = _mk_base()
        try:
            _materialize_full_tree(base)
            out_dir = base / "tiny_guarded_entry_manual_authorization_design"
            rc = mod.run_execute(
                symbol="SOLUSDT",
                allow_design_approval=False,
                allow_real_entry_execution=False,
                write_report=True,
                output_dir=out_dir,
                **_cli_kwargs(base),
            )
            assert rc == 0
            latest_json = out_dir / "latest_tiny_guarded_entry_manual_authorization_design.json"
            latest_md   = out_dir / "latest_tiny_guarded_entry_manual_authorization_design.md"
            assert latest_json.exists()
            assert latest_md.exists()
            data = json.loads(latest_json.read_text(encoding="utf-8"))
            assert data["status"] == STATUS_DESIGN_READY
            assert data["next_required_task"] == "TASK-014AK_guarded_entry_manual_authorization_dry_run"
        finally:
            _shutil.rmtree(base, ignore_errors=True)


class TestAJ55CLIMissingArtifactExitOne:
    def test_missing_returns_one(self):
        mod = _load_cli_module()
        base = _mk_base()
        try:
            _materialize_full_tree(base)
            (base / "tiny_guarded_entry_real_permission_review"
                  / "latest_tiny_guarded_entry_real_permission_review.json").unlink()
            rc = mod.run_execute(
                symbol="SOLUSDT",
                allow_design_approval=False,
                allow_real_entry_execution=False,
                write_report=False,
                output_dir=base / "tiny_guarded_entry_manual_authorization_design",
                **_cli_kwargs(base),
            )
            assert rc == 1
        finally:
            _shutil.rmtree(base, ignore_errors=True)


class TestAJ56CLIMissingSymbolExitOne:
    def test_missing_symbol_returns_one(self):
        mod = _load_cli_module()
        base = _mk_base()
        try:
            _materialize_full_tree(base)
            rc = mod.run_execute(
                symbol="",
                allow_design_approval=False,
                allow_real_entry_execution=False,
                write_report=False,
                output_dir=base / "tiny_guarded_entry_manual_authorization_design",
                **_cli_kwargs(base),
            )
            assert rc == 1
        finally:
            _shutil.rmtree(base, ignore_errors=True)


# ===========================================================================
# AJ57: Timestamp format
# ===========================================================================

class TestAJ57TimestampFormat:
    def test_timestamp(self):
        r = _run()
        assert r.timestamp_utc == "2026-06-11T12:00:00Z"


# ===========================================================================
# AJ58: Result dataclass types
# ===========================================================================

class TestAJ58ResultDataclassTypes:
    def test_types(self):
        r = _run()
        assert isinstance(r.timestamp_utc, str)
        assert isinstance(r.mode, str)
        assert isinstance(r.selected_symbol, str)
        assert isinstance(r.existing_position_symbols, list)
        assert isinstance(r.stages, dict)
        assert isinstance(r.authorization_design_scope, dict)
        assert isinstance(r.authorization_token_design, dict)
        assert isinstance(r.required_human_confirmation_flags, dict)
        assert isinstance(r.pre_execution_readiness_checklist_design, dict)
        assert isinstance(r.entry_execution_request_template_design, dict)
        assert isinstance(r.post_authorization_stop_cleanup_boundary_design, dict)
        assert isinstance(r.failure_and_abort_design, dict)
        assert isinstance(r.documentation_sync_review, dict)
        assert isinstance(r.audit_artifacts, dict)
        assert isinstance(r.final_manual_authorization_design_verdict, dict)
        assert isinstance(r.blocked_gates, list)
        assert isinstance(r.failed_stage, str)
        assert isinstance(r.status, str)
        assert isinstance(r.next_required_task, str)


# ===========================================================================
# AJ59: Gate count -- >=147 unique GATE_* constants
# ===========================================================================

class TestAJ59GateCount:
    def test_gate_count(self):
        import src.demo_tiny_guarded_entry_manual_authorization_design as m
        gates = [
            getattr(m, name) for name in dir(m)
            if name.startswith("GATE_")
        ]
        assert len(gates) >= 147, f"Expected >=147 gates, found {len(gates)}"
        assert len(set(gates)) == len(gates), "Gate name strings must be unique"


# ===========================================================================
# AJ60: Stage order matches ALL_STAGES
# ===========================================================================

class TestAJ60StageOrder:
    def test_stage_order_default(self):
        r = _run()
        assert tuple(r.stage_order) == ALL_STAGES
        assert len(ALL_STAGES) == 10


# ===========================================================================
# AJ61: Blocked gates deduplicated
# ===========================================================================

class TestAJ61BlockedGatesDeduplicated:
    def test_no_duplicates(self):
        r = _run()
        assert len(r.blocked_gates) == len(set(r.blocked_gates))


# ===========================================================================
# AJ62: Hard-fail gates frozenset
# ===========================================================================

class TestAJ62HardFailGates:
    def test_hard_fail_membership(self):
        from src.demo_tiny_guarded_entry_manual_authorization_design import _HARD_FAIL_GATES
        assert GATE_READONLY_SMOKE_MISSING in _HARD_FAIL_GATES
        assert GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING in _HARD_FAIL_GATES
        assert GATE_ENTRY_REAL_PERMISSION_REVIEW_STATUS_UNACCEPTABLE in _HARD_FAIL_GATES
        assert GATE_ENTRY_REAL_PERMISSION_REVIEW_READINESS_EXECUTABLE in _HARD_FAIL_GATES
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in _HARD_FAIL_GATES
        assert GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING in _HARD_FAIL_GATES


# ===========================================================================
# AJ63: G20 policy still in place
# ===========================================================================

class TestAJ63G20PolicyStillInPlace:
    def test_g20(self):
        r = _run()
        assert r.g20_policy_still_in_place is True
        assert r.g20_lifted is False
        assert GATE_G20_POLICY_STILL_IN_PLACE in r.blocked_gates
        assert GATE_NO_G20_LIFT in r.blocked_gates
        assert GATE_G20_NOT_LIFTED in r.blocked_gates


# ===========================================================================
# AJ64: Five protected demo positions present
# ===========================================================================

class TestAJ64FiveProtectedPositionsPresent:
    def test_five_protected(self):
        r = _run()
        assert DESIGN_EXPECTED_EXISTING_COUNT == 5
        assert len(EXISTING_POSITION_SYMBOLS) == 5
        assert tuple(EXISTING_POSITION_SYMBOLS) == (
            "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"
        )
        assert set(r.existing_position_symbols) == set(EXISTING_POSITION_SYMBOLS)


# ===========================================================================
# AJ65: next_required_task invariant
# ===========================================================================

class TestAJ65NextRequiredTaskInvariant:
    @pytest.mark.parametrize("flags", [
        {},
        {"allow_design_approval": True},
        {"allow_real_entry_execution": True},
    ])
    def test_next_required_task(self, flags):
        r = _run(**flags)
        assert r.next_required_task == "TASK-014AK_guarded_entry_manual_authorization_dry_run"


# ===========================================================================
# AJ66: Stages independent across calls (no shared mutable state)
# ===========================================================================

class TestAJ66StagesIndependentAcrossCalls:
    def test_independent(self):
        r1 = _run()
        r2 = _run()
        r1.stages[STAGE_0_ARTIFACT_PREFLIGHT]["__poison__"] = True
        assert "__poison__" not in r2.stages[STAGE_0_ARTIFACT_PREFLIGHT]


# ===========================================================================
# AJ67: Design-expected constants
# ===========================================================================

class TestAJ67DesignExpectedConstants:
    def test_constants(self):
        assert DESIGN_EXPECTED_SYMBOL == "SOLUSDT"
        assert DESIGN_EXPECTED_CATEGORY == "linear"
        assert DESIGN_EXPECTED_ENTRY_SIDE == "Buy"
        assert DESIGN_EXPECTED_QTY == 0.1
        assert DESIGN_EXPECTED_QTY_STEP == 0.1
        assert DESIGN_EXPECTED_MIN_ORDER_QTY == 0.1
        assert DESIGN_EXPECTED_TICK_SIZE == 0.01
        assert DESIGN_EXPECTED_MAX_NOTIONAL_USDT == 10.0
        assert DESIGN_EXPECTED_ENTRY_REFERENCE == 64.4
        assert DESIGN_EXPECTED_ESTIMATED_NOTIONAL == 6.44
        assert DESIGN_EXPECTED_POSITION_IDX == 0
        assert DESIGN_EXPECTED_REDUCE_ONLY is False
        assert DESIGN_EXPECTED_CLOSE_ON_TRIGGER is False
        assert DESIGN_EXPECTED_ORDER_TYPE == "Market"
        assert DESIGN_EXPECTED_STOP_LOSS == 61.18
        assert DESIGN_EXPECTED_TPSL_MODE == "Full"
        assert DESIGN_EXPECTED_SL_TRIGGER_BY == "MarkPrice"
        assert EXPECTED_INSTRUMENT_CATEGORY == "linear"
        assert DESIGN_EXPECTED_EXISTING_COUNT == 5


# ===========================================================================
# AJ68: orderLinkId prefix design-only
# ===========================================================================

class TestAJ68OrderLinkIdPrefix:
    def test_prefix_design(self):
        assert isinstance(ENTRY_DESIGN_ORDER_LINK_ID_PREFIXES, tuple)
        assert "MANUAL_AUTH_REVIEW_TINY_ENTRY_" in ENTRY_DESIGN_ORDER_LINK_ID_PREFIXES


# ===========================================================================
# AJ69: AST safety -- module source must be parseable, no network calls
# ===========================================================================

class TestAJ69ASTSafety:
    def test_module_ast(self):
        source = _MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                assert attr not in ("urlopen", "create_connection"), (
                    f"Forbidden call {attr} found in module"
                )
                if attr in ("post", "put", "delete", "patch") and isinstance(node.func.value, ast.Name):
                    base = node.func.value.id
                    assert base not in ("requests", "session", "client", "http"), (
                        f"Forbidden network call {base}.{attr} found"
                    )


# ===========================================================================
# AJ70: Hard-fail aggregates each missing-artifact gate
# ===========================================================================

class TestAJ70HardFailAggregatesGates:
    def test_status_fail_closed_on_all_missing(self):
        r = _design().run_checklist(
            readonly_smoke=None, reconciliation=None, protection=None,
            contract=None, noop_plan=None, lifecycle_mock=None,
            real_permission_gate=None, tiny_entry_permission_gate=None,
            tiny_stop_permission_gate=None, tiny_cleanup_permission_gate=None,
            lifecycle_summary=None, runner_design=None, runner_dry_run=None,
            guarded_design_review=None, guarded_entry_adapter=None,
            guarded_stop_adapter=None, guarded_cleanup_adapter=None,
            guarded_lifecycle_summary=None,
            entry_real_permission_review=None,
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
            GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AJ71: Real-entry-execution flag does not enable execution
# ===========================================================================

class TestAJ71RealEntryExecutionDoesNotEnable:
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
# AJ72: Design-approval flag does not enable execution
# ===========================================================================

class TestAJ72DesignApprovalDoesNotEnable:
    def test_does_not_enable(self):
        r = _run(allow_design_approval=True)
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
# AJ73: All scope gates present in blocked_gates
# ===========================================================================

class TestAJ73ScopeGatesPresent:
    def test_scope_gates(self):
        r = _run()
        for gate in (
            GATE_GUARDED_ENTRY_MANUAL_AUTH_DESIGN_ONLY,
            GATE_AUTHORIZATION_DESIGN_ONLY,
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
# AJ74: All token-design gates present in blocked_gates
# ===========================================================================

class TestAJ74TokenDesignGatesPresent:
    def test_token_gates(self):
        r = _run()
        for gate in (
            GATE_TOKEN_PATTERN_PRESENT,
            GATE_TOKEN_NOT_VALIDATED,
            GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
            GATE_TOKEN_INCLUDES_DATE,
            GATE_TOKEN_INCLUDES_SYMBOL,
            GATE_TOKEN_NO_SECRET,
            GATE_TOKEN_REUSE_FORBIDDEN,
            GATE_TOKEN_EXPIRY_DOCUMENTED,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AJ75: All human confirmation flag gates present in blocked_gates
# ===========================================================================

class TestAJ75HumanConfirmationFlagGatesPresent:
    def test_confirmation_gates(self):
        r = _run()
        for gate in (
            GATE_REQUIRED_FLAGS_DOCUMENTED,
            GATE_FLAGS_NOT_VALIDATED,
            GATE_SECOND_CONFIRMATION_REQUIRED,
            GATE_MANUAL_BOUNDARY_REQUIRED,
            GATE_CONFIRM_SYMBOL_FLAG,
            GATE_CONFIRM_SIDE_FLAG,
            GATE_CONFIRM_QTY_FLAG,
            GATE_CONFIRM_MAX_NOTIONAL_FLAG,
            GATE_CONFIRM_EXISTING_COUNT_FLAG,
            GATE_CONFIRM_EXISTING_SYMBOLS_FLAG,
            GATE_CONFIRM_REDUCE_ONLY_FALSE_FLAG,
            GATE_CONFIRM_POSITION_IDX_FLAG,
            GATE_CONFIRM_ORDER_TYPE_FLAG,
            GATE_CONFIRM_STOP_REQUIRED_FLAG,
            GATE_CONFIRM_STOP_LOSS_FLAG,
            GATE_CONFIRM_CLEANUP_MANUAL_BOUNDARY_FLAG,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AJ76: All entry template gates present in blocked_gates
# ===========================================================================

class TestAJ76EntryTemplateGatesPresent:
    def test_template_gates(self):
        r = _run()
        for gate in (
            GATE_TEMPLATE_PRESENT,
            GATE_TEMPLATE_DESIGN_ONLY,
            GATE_TEMPLATE_PREVIEW_ONLY,
            GATE_TEMPLATE_SEND_ALLOWED_FALSE,
            GATE_TEMPLATE_ENDPOINT_CALLED_FALSE,
            GATE_TEMPLATE_REAL_PAYLOAD_FALSE,
            GATE_TEMPLATE_SIGNATURE_PRESENT_FALSE,
            GATE_TEMPLATE_PRIVATE_HEADERS_EMPTY,
            GATE_TEMPLATE_ENDPOINT_PATH_ORDER_CREATE,
            GATE_TEMPLATE_BASE_URL_DEMO_ONLY,
            GATE_TEMPLATE_SIDE_BUY,
            GATE_TEMPLATE_QTY_0_1,
            GATE_TEMPLATE_REDUCE_ONLY_FALSE,
            GATE_TEMPLATE_CLOSE_ON_TRIGGER_FALSE,
            GATE_TEMPLATE_POSITION_IDX_ZERO,
            GATE_TEMPLATE_ORDER_TYPE_MARKET,
            GATE_TEMPLATE_NO_SENDER_ADAPTER,
            GATE_TEMPLATE_ORDER_LINK_ID_PREFIX_DOCUMENTED,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AJ77: All boundary design gates present in blocked_gates
# ===========================================================================

class TestAJ77BoundaryDesignGatesPresent:
    def test_boundary_gates(self):
        r = _run()
        for gate in (
            GATE_ENTRY_SUCCESS_DOES_NOT_AUTO_ATTACH_STOP,
            GATE_STOP_ATTACH_SEPARATE_MANUAL_AUTH,
            GATE_CLEANUP_SEPARATE_MANUAL_AUTH,
            GATE_BOUNDARY_STOP_LOSS_61_18,
            GATE_BOUNDARY_TPSL_MODE_FULL,
            GATE_BOUNDARY_SL_TRIGGER_BY_MARKPRICE,
            GATE_STOP_ATTACH_FAIL_MANUAL_REVIEW,
            GATE_ENTRY_SUCCESS_WITHOUT_STOP_MANUAL_REVIEW,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AJ78: All failure design gates present in blocked_gates
# ===========================================================================

class TestAJ78FailureGatesPresent:
    def test_failure_gates(self):
        r = _run()
        for gate in (
            GATE_MISSING_FLAG_FAIL_CLOSED,
            GATE_READONLY_STALE_FAIL_CLOSED,
            GATE_SOLUSDT_EXISTS_FAIL_CLOSED,
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
# AJ79: All documentation-sync gates present in blocked_gates
# ===========================================================================

class TestAJ79DocumentationSyncGatesPresent:
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
# AJ80: Execution-guard gates present in blocked_gates
# ===========================================================================

class TestAJ80ExecutionGuardGatesPresent:
    def test_execution_guard_gates(self):
        r = _run()
        for gate in (
            GATE_REAL_ENTRY_EXECUTION_NOT_IMPL,
            GATE_NO_REAL_ORDER_ENDPOINT,
            GATE_NO_REAL_STOP_ENDPOINT,
            GATE_NO_POSITION_MODIFIED,
            GATE_NO_LIVE_ENDPOINT,
            GATE_G20_NOT_LIFTED,
            GATE_NO_SECRETS_EMITTED,
        ):
            assert gate in r.blocked_gates


# ===========================================================================
# AJ81: Acceptable status sets contain expected values
# ===========================================================================

class TestAJ81AcceptableStatusSets:
    def test_sets_nonempty(self):
        assert "TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY" in ACCEPTABLE_ENTRY_REAL_PERMISSION_REVIEW_STATUSES
        assert "REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED" in ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES
        assert "TINY_LIFECYCLE_RUNNER_DESIGN_READY" in ACCEPTABLE_RUNNER_DESIGN_STATUSES
        assert "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY" in ACCEPTABLE_RUNNER_DRY_RUN_STATUSES
        assert "TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY" in ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES
        assert "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY" in ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES
        assert "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY" in ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES
        assert "TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY" in ACCEPTABLE_GUARDED_CLEANUP_ADAPTER_STATUSES
        assert "TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY" in ACCEPTABLE_GUARDED_LIFECYCLE_SUMMARY_STATUSES


# ===========================================================================
# AJ82: Upstream status fields propagated to result
# ===========================================================================

class TestAJ82UpstreamStatusFieldsExposed:
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
        assert r.upstream_entry_real_permission_review_status == "TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY"
        assert r.upstream_entry_real_permission_review_readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE


# ===========================================================================
# AJ83: Timestamp override via _now param
# ===========================================================================

class TestAJ83TimestampOverride:
    def test_now_override(self):
        custom = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        r = _run(_now=custom)
        assert r.timestamp_utc == "2030-01-02T03:04:05Z"


# ===========================================================================
# AJ84: Pre-execution checklist estimated notional within cap gate
# ===========================================================================

class TestAJ84EstimatedNotionalGate:
    def test_estimated_notional_gate(self):
        r = _run()
        assert GATE_ESTIMATED_NOTIONAL_WITHIN_CAP in r.blocked_gates


# ===========================================================================
# AJ85: Token pattern hard-coded as design constant
# ===========================================================================

class TestAJ85TokenPatternConstant:
    def test_token_pattern_constant(self):
        assert ENTRY_TOKEN_PATTERN == "CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT"


# ===========================================================================
# AJ86: Existing protected positions documented (5 symbols)
# ===========================================================================

class TestAJ86ExistingProtectedPositionsDocumented:
    def test_docs(self):
        r = _run()
        p = r.pre_execution_readiness_checklist_design
        assert set(p["protected_position_symbols"]) == set(EXISTING_POSITION_SYMBOLS)
        assert "AIXBTUSDT" in p["protected_position_symbols"]
        assert "ENAUSDT" in p["protected_position_symbols"]
        assert "TIAUSDT" in p["protected_position_symbols"]
        assert "POLYXUSDT" in p["protected_position_symbols"]
        assert "EDUUSDT" in p["protected_position_symbols"]
