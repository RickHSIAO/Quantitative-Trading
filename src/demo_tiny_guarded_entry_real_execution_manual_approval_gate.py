"""
src/demo_tiny_guarded_entry_real_execution_manual_approval_gate.py
TASK-014AM: Guarded Entry Real Execution Manual Approval Gate.

Manual-approval-gate-only module. This task documents the human approval
gate that MUST sit in front of any future real tiny entry execution.
This module DOES NOT implement a real entry sender, does not send any
order, does not call /v5/order/create, does not call
/v5/position/trading-stop, does not read secrets, does not sign
anything, does not lift TASK-014L G20, does not validate any real
approval token, does not treat any token or phrase as authorization,
and does not touch any existing protected demo position.

Inputs: 22 upstream artifacts (the 21 from TASK-014AL + AL's own
        guarded entry final pre-execution review output).

Stages:
  stage_0_artifact_preflight
  stage_1_manual_approval_gate_scope
  stage_2_manual_approval_token_gate
  stage_3_required_manual_approval_inputs
  stage_4_approval_gate_readiness_review
  stage_5_entry_payload_approval_preview
  stage_6_stop_cleanup_manual_gate_review
  stage_7_forbidden_execution_surface_review
  stage_8_failure_and_abort_manual_gate
  stage_9_documentation_sync_review
  stage_10_final_manual_approval_gate_verdict

Modes:
  manual_approval_gate_checklist  --- default
  manual_approval_gate_approval   --- --allow-approval-gate
  real_entry_execution_guard      --- --allow-real-entry-execution
  fail_closed                     --- upstream failed

This module does NOT (enforced by source-scan tests):
  * import urllib / requests / httpx / socket / http.client
  * read os.environ / dotenv
  * call HMAC / signing
  * import main / src.risk / BybitExecutor / pybit
  * import any sender / orchestrator / probe / lifecycle module
  * invoke /v5/order/create or /v5/position/trading-stop
  * lift TASK-014L sender G20 (protected_entry_policy_missing)
  * touch ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT
  * mutate leverage / transfer / withdraw / deposit
  * expose any real-execute / send-order / place-order / real-run flag
  * validate any real token, or treat any token / phrase as authorization
  * auto-commit / auto-push git
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Live state references (string-only; never invoked)
# ---------------------------------------------------------------------------

EXISTING_POSITION_SYMBOLS: tuple[str, ...] = (
    "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT",
)
EXISTING_POSITION_SYMBOLS_DOC_ORDER: tuple[str, ...] = (
    "AIXBTUSDT", "ENAUSDT", "TIAUSDT", "POLYXUSDT", "EDUUSDT",
)

DEFAULT_SELECTED_SYMBOL = "SOLUSDT"

ORDER_CREATE_PATH_REF = "/v5/order/create"            # NOT invoked
TRADING_STOP_PATH_REF = "/v5/position/trading-stop"   # NOT invoked
BASE_URL_DEMO_REF     = "https://api-demo.bybit.com"  # informational only
BASE_URL_LIVE_REF     = "https://api.bybit.com"       # denylist reference

DEMO_ENDPOINT_ALLOWLIST: tuple[str, ...] = (BASE_URL_DEMO_REF,)
LIVE_ENDPOINT_DENYLIST:  tuple[str, ...] = (BASE_URL_LIVE_REF,)


# ---------------------------------------------------------------------------
# Stage identifiers
# ---------------------------------------------------------------------------

STAGE_0_ARTIFACT_PREFLIGHT                   = "stage_0_artifact_preflight"
STAGE_1_MANUAL_APPROVAL_GATE_SCOPE           = "stage_1_manual_approval_gate_scope"
STAGE_2_MANUAL_APPROVAL_TOKEN_GATE           = "stage_2_manual_approval_token_gate"
STAGE_3_REQUIRED_MANUAL_APPROVAL_INPUTS      = "stage_3_required_manual_approval_inputs"
STAGE_4_APPROVAL_GATE_READINESS_REVIEW       = "stage_4_approval_gate_readiness_review"
STAGE_5_ENTRY_PAYLOAD_APPROVAL_PREVIEW       = "stage_5_entry_payload_approval_preview"
STAGE_6_STOP_CLEANUP_MANUAL_GATE_REVIEW      = "stage_6_stop_cleanup_manual_gate_review"
STAGE_7_FORBIDDEN_EXECUTION_SURFACE_REVIEW   = "stage_7_forbidden_execution_surface_review"
STAGE_8_FAILURE_AND_ABORT_MANUAL_GATE        = "stage_8_failure_and_abort_manual_gate"
STAGE_9_DOCUMENTATION_SYNC_REVIEW            = "stage_9_documentation_sync_review"
STAGE_10_FINAL_MANUAL_APPROVAL_GATE_VERDICT  = "stage_10_final_manual_approval_gate_verdict"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_MANUAL_APPROVAL_GATE_SCOPE,
    STAGE_2_MANUAL_APPROVAL_TOKEN_GATE,
    STAGE_3_REQUIRED_MANUAL_APPROVAL_INPUTS,
    STAGE_4_APPROVAL_GATE_READINESS_REVIEW,
    STAGE_5_ENTRY_PAYLOAD_APPROVAL_PREVIEW,
    STAGE_6_STOP_CLEANUP_MANUAL_GATE_REVIEW,
    STAGE_7_FORBIDDEN_EXECUTION_SURFACE_REVIEW,
    STAGE_8_FAILURE_AND_ABORT_MANUAL_GATE,
    STAGE_9_DOCUMENTATION_SYNC_REVIEW,
    STAGE_10_FINAL_MANUAL_APPROVAL_GATE_VERDICT,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_GATE_READY = (
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_READY"
)
STATUS_GATE_READY_EXEC_DISABLED = (
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_"
    "READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_ENTRY_NOT_IMPL = "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED         = "FAIL_CLOSED"

MODE_GATE_CHECKLIST          = "manual_approval_gate_checklist"
MODE_GATE_APPROVAL           = "manual_approval_gate_approval"
MODE_REAL_ENTRY_EXEC_GUARD   = "real_entry_execution_guard"
MODE_FAIL_CLOSED             = "fail_closed"

READINESS_CONCLUSION_NOT_EXECUTABLE = "DESIGN_REVIEW_READY_NOT_EXECUTABLE"
DRY_RUN_AUTHORIZATION_RESULT        = "DOCUMENTED_ONLY_NOT_AUTHORIZED"


# ---------------------------------------------------------------------------
# Acceptable upstream-status whitelists
# ---------------------------------------------------------------------------

ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES: frozenset[str] = frozenset({
    "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY",
    "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY_BUT_EXECUTION_DISABLED",
    "REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED",
})

ACCEPTABLE_RUNNER_DESIGN_STATUSES: frozenset[str] = frozenset({
    "TINY_LIFECYCLE_RUNNER_DESIGN_READY",
    "TINY_LIFECYCLE_RUNNER_DESIGN_READY_BUT_EXECUTION_DISABLED",
    "REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED",
})

ACCEPTABLE_RUNNER_DRY_RUN_STATUSES: frozenset[str] = frozenset({
    "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY",
    "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY_BUT_EXECUTION_DISABLED",
    "REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED",
})

ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES: frozenset[str] = frozenset({
    "TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY",
    "TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY_BUT_EXECUTION_DISABLED",
    "REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED",
})

ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES: frozenset[str] = frozenset({
    "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY",
    "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED",
    "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED",
})

ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES: frozenset[str] = frozenset({
    "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY",
    "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED",
    "REAL_STOP_ATTACH_EXECUTION_NOT_IMPLEMENTED",
})

ACCEPTABLE_GUARDED_CLEANUP_ADAPTER_STATUSES: frozenset[str] = frozenset({
    "TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY",
    "TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED",
    "REAL_CLEANUP_EXECUTION_NOT_IMPLEMENTED",
})

ACCEPTABLE_GUARDED_LIFECYCLE_SUMMARY_STATUSES: frozenset[str] = frozenset({
    "TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY",
    "TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY_BUT_EXECUTION_DISABLED",
    "REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED",
})

ACCEPTABLE_ENTRY_REAL_PERMISSION_REVIEW_STATUSES: frozenset[str] = frozenset({
    "TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY",
    "TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY_BUT_EXECUTION_DISABLED",
    "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED",
})

ACCEPTABLE_ENTRY_MANUAL_AUTH_DESIGN_STATUSES: frozenset[str] = frozenset({
    "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DESIGN_READY",
    "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DESIGN_READY_BUT_EXECUTION_DISABLED",
    "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED",
})

ACCEPTABLE_ENTRY_MANUAL_AUTH_DRY_RUN_STATUSES: frozenset[str] = frozenset({
    "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY",
    "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY_BUT_EXECUTION_DISABLED",
    "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED",
})

ACCEPTABLE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUSES: frozenset[str] = frozenset({
    "TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY",
    "TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY_BUT_EXECUTION_DISABLED",
    "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED",
})


# ---------------------------------------------------------------------------
# Approval phrase / token patterns (NEVER validated, NEVER authorization)
# ---------------------------------------------------------------------------

EXACT_APPROVAL_PHRASE = (
    "I AUTHORIZE DEMO TINY ENTRY GATE ONLY FOR SOLUSDT BUY 0.1 MAX 10 USDT; "
    "NO ORDER MAY BE SENT BY TASK-014AM"
)

ENTRY_TOKEN_PATTERN = "CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT"
SAMPLE_TOKEN        = "CONFIRM_DEMO_TINY_ENTRY_20260612_SOLUSDT"

REQUIRED_MANUAL_APPROVAL_INPUTS: tuple[str, ...] = (
    EXACT_APPROVAL_PHRASE,
    "--confirm-symbol SOLUSDT",
    "--confirm-side Buy",
    "--confirm-qty 0.1",
    "--confirm-max-notional-usdt 10",
    "--confirm-reduce-only false",
    "--confirm-position-idx 0",
    "--confirm-order-type Market",
    "--confirm-existing-symbols AIXBTUSDT,ENAUSDT,TIAUSDT,POLYXUSDT,EDUUSDT",
    "--confirm-stop-required-after-entry true",
    "--confirm-cleanup-manual-boundary true",
    "--confirm-no-order-will-be-sent-by-this-task true",
)

REQUIRED_CONFIRM_FLAGS: tuple[str, ...] = REQUIRED_MANUAL_APPROVAL_INPUTS[1:]


# ---------------------------------------------------------------------------
# Expected upstream invariants
# ---------------------------------------------------------------------------

EXPECTED_ENDPOINT_FAMILY         = "bybit_demo"
EXPECTED_ACCOUNT_MODE            = "demo"
EXPECTED_PROOF_STRENGTH          = "STRONG"
EXPECTED_POSITION_DETAILS_SOURCE = "real_readonly"
EXPECTED_LIFECYCLE_STATUS        = "MOCK_TINY_LIFECYCLE_SUCCESS"
EXPECTED_INSTRUMENT_CATEGORY     = "linear"


# ---------------------------------------------------------------------------
# Entry expected values (documentation only)
# ---------------------------------------------------------------------------

GATE_EXPECTED_SYMBOL              = "SOLUSDT"
GATE_EXPECTED_CATEGORY            = "linear"
GATE_EXPECTED_ENTRY_SIDE          = "Buy"
GATE_EXPECTED_QTY                 = 0.1
GATE_EXPECTED_QTY_STEP            = 0.1
GATE_EXPECTED_MIN_ORDER_QTY       = 0.1
GATE_EXPECTED_TICK_SIZE           = 0.01
GATE_EXPECTED_MAX_NOTIONAL_USDT   = 10.0
GATE_EXPECTED_ENTRY_REFERENCE     = 64.4
GATE_EXPECTED_ESTIMATED_NOTIONAL  = 6.44   # qty * entry_reference
GATE_EXPECTED_POSITION_IDX        = 0
GATE_EXPECTED_REDUCE_ONLY         = False
GATE_EXPECTED_CLOSE_ON_TRIGGER    = False
GATE_EXPECTED_ORDER_TYPE          = "Market"
GATE_EXPECTED_STOP_LOSS           = 61.18
GATE_EXPECTED_TPSL_MODE           = "Full"
GATE_EXPECTED_SL_TRIGGER_BY       = "MarkPrice"
GATE_EXPECTED_EXISTING_COUNT      = 5
ORDER_LINK_ID_PREFIX              = "APPROVAL_GATE_TINY_ENTRY_"

FORBIDDEN_LOG_FIELDS: tuple[str, ...] = (
    "api_key_value", "api_secret_value", "signature_value",
    "auth_header_value", "sign_header_value", "bearer_token_value",
)


# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------

# General gates (33)
GATE_READONLY_SMOKE_MISSING                       = "readonly_smoke_missing"
GATE_RECONCILIATION_MISSING                       = "reconciliation_missing"
GATE_PROTECTION_MISSING                           = "protection_missing"
GATE_CONTRACT_MISSING                             = "contract_missing"
GATE_NOOP_PLAN_MISSING                            = "noop_plan_missing"
GATE_LIFECYCLE_MOCK_MISSING                       = "lifecycle_mock_missing"
GATE_REAL_PERMISSION_GATE_MISSING                 = "real_permission_gate_missing"
GATE_TINY_ENTRY_PERMISSION_GATE_MISSING           = "tiny_entry_permission_gate_missing"
GATE_TINY_STOP_PERMISSION_GATE_MISSING            = "tiny_stop_permission_gate_missing"
GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING         = "tiny_cleanup_permission_gate_missing"
GATE_LIFECYCLE_SUMMARY_MISSING                    = "lifecycle_summary_missing"
GATE_RUNNER_DESIGN_MISSING                        = "runner_design_missing"
GATE_RUNNER_DRY_RUN_MISSING                       = "runner_dry_run_missing"
GATE_GUARDED_DESIGN_REVIEW_MISSING                = "guarded_design_review_missing"
GATE_GUARDED_ENTRY_ADAPTER_MISSING                = "guarded_entry_adapter_missing"
GATE_GUARDED_STOP_ADAPTER_MISSING                 = "guarded_stop_adapter_missing"
GATE_GUARDED_CLEANUP_ADAPTER_MISSING              = "guarded_cleanup_adapter_missing"
GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING            = "guarded_lifecycle_summary_missing"
GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING         = "entry_real_permission_review_missing"
GATE_ENTRY_MANUAL_AUTH_DESIGN_MISSING             = "entry_manual_authorization_design_missing"
GATE_ENTRY_MANUAL_AUTH_DRY_RUN_MISSING            = "entry_manual_authorization_dry_run_missing"
GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING     = "entry_final_pre_execution_review_missing"
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO               = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                        = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG                    = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY    = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_NOT_SOLUSDT                  = "selected_symbol_not_solusdt"
GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUS_UNACCEPTABLE = (
    "entry_final_pre_execution_review_status_unacceptable"
)
GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READINESS_EXECUTABLE = (
    "entry_final_pre_execution_review_readiness_executable"
)
GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_RESULT_NOT_DOCUMENTED_ONLY = (
    "entry_final_pre_execution_review_result_not_documented_only"
)
GATE_G20_POLICY_STILL_IN_PLACE                    = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                             = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                           = "no_secret_values_emitted_in_this_task"

# Scope gates (16)
GATE_MANUAL_APPROVAL_GATE_ONLY                    = "manual_approval_gate_only"
GATE_APPROVAL_GATE_DOES_NOT_EXECUTE               = "approval_gate_does_not_execute"
GATE_ENTRY_EXECUTION_NOT_INCLUDED                 = "entry_execution_not_included"
GATE_STOP_EXECUTION_NOT_INCLUDED                  = "stop_execution_not_included"
GATE_CLEANUP_EXECUTION_NOT_INCLUDED               = "cleanup_execution_not_included"
GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED        = "full_lifecycle_execution_not_included"
GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE             = "real_entry_not_implemented_scope"
GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE             = "real_execution_not_allowed_scope"
GATE_APPROVAL_DOES_NOT_GRANT_EXECUTION_SCOPE      = "approval_does_not_grant_execution_scope"
GATE_SEND_NOT_ALLOWED_SCOPE                       = "send_not_allowed_scope"
GATE_ORDER_ENDPOINT_NOT_CALLED                    = "order_endpoint_not_called_in_this_task"
GATE_STOP_ENDPOINT_NOT_CALLED                     = "stop_endpoint_not_called_in_this_task"
GATE_NO_ENDPOINT_INVOKED                          = "no_endpoint_invoked_in_this_task"
GATE_NO_POSITION_MODIFIED_SCOPE                   = "no_position_modified_scope"
GATE_NO_SECRETS_LOADED                            = "no_secrets_loaded_in_this_task"
GATE_NO_G20_LIFT                                  = "no_g20_policy_lift_in_this_task"

# Token gates (14)
GATE_TOKEN_PATTERN_DOCUMENTED                     = "token_pattern_documented"
GATE_SAMPLE_TOKEN_DOCUMENTED                      = "sample_token_documented"
GATE_TOKEN_NOT_VALIDATED                          = "token_not_validated"
GATE_REAL_TOKEN_NOT_VALIDATED                     = "real_token_not_validated"
GATE_TOKEN_FORMAT_NOT_AUTHORIZATION               = "token_format_not_authorization"
GATE_TOKEN_DOES_NOT_GRANT_EXECUTION               = "token_does_not_grant_execution"
GATE_TOKEN_REQUIRES_FUTURE_TASK_REVALIDATION      = "token_requires_future_task_revalidation"
GATE_TOKEN_SINGLE_USE_DOCUMENTED                  = "token_single_use_documented"
GATE_TOKEN_INCLUDES_DATE                          = "token_includes_date"
GATE_TOKEN_INCLUDES_SYMBOL                        = "token_includes_symbol"
GATE_TOKEN_REUSE_FORBIDDEN                        = "token_reuse_forbidden"
GATE_TOKEN_EXPIRY_DOCUMENTED                      = "token_expiry_documented_only"
GATE_TOKEN_CONTAINS_NO_SECRET                     = "token_contains_no_secret"
GATE_TOKEN_NOT_LOGGED_AS_SECRET                   = "token_not_logged_as_secret"

# Manual approval inputs gates (19)
GATE_EXACT_APPROVAL_PHRASE_DOCUMENTED             = "exact_approval_phrase_documented"
GATE_EXACT_PHRASE_NOT_VALIDATED                   = "exact_phrase_not_validated"
GATE_APPROVAL_INPUTS_DOCUMENTED                   = "approval_inputs_documented"
GATE_APPROVAL_INPUTS_NOT_VALIDATED                = "approval_inputs_not_validated"
GATE_APPROVAL_INPUTS_DO_NOT_AUTHORIZE_EXECUTION   = "approval_inputs_do_not_authorize_execution"
GATE_RICK_EXPLICIT_AUTHORIZATION_REQUIRED         = "rick_explicit_authorization_still_required"
GATE_SECOND_CONFIRMATION_REQUIRED                 = "second_confirmation_required"
GATE_INDEPENDENT_REVIEWER_RECOMMENDED             = "independent_reviewer_recommended"
GATE_CONFIRM_SYMBOL_FLAG                          = "confirm_symbol_flag_documented"
GATE_CONFIRM_SIDE_FLAG                            = "confirm_side_flag_documented"
GATE_CONFIRM_QTY_FLAG                             = "confirm_qty_flag_documented"
GATE_CONFIRM_MAX_NOTIONAL_FLAG                    = "confirm_max_notional_flag_documented"
GATE_CONFIRM_REDUCE_ONLY_FLAG                     = "confirm_reduce_only_flag_documented"
GATE_CONFIRM_POSITION_IDX_FLAG                    = "confirm_position_idx_flag_documented"
GATE_CONFIRM_ORDER_TYPE_FLAG                      = "confirm_order_type_flag_documented"
GATE_CONFIRM_EXISTING_SYMBOLS_FLAG                = "confirm_existing_symbols_flag_documented"
GATE_CONFIRM_STOP_REQUIRED_FLAG                   = "confirm_stop_required_flag_documented"
GATE_CONFIRM_CLEANUP_BOUNDARY_FLAG                = "confirm_cleanup_boundary_flag_documented"
GATE_CONFIRM_NO_ORDER_WILL_BE_SENT_FLAG           = "confirm_no_order_will_be_sent_by_this_task_flag_documented"

# Readiness gates (17)
GATE_FINAL_PRE_EXECUTION_REVIEW_READY             = "final_pre_execution_review_ready"
GATE_AK_DRY_RUN_READY                             = "ak_manual_authorization_dry_run_ready"
GATE_AJ_DESIGN_READY                              = "aj_manual_authorization_design_ready"
GATE_AI_PERMISSION_REVIEW_READY                   = "ai_real_permission_review_ready"
GATE_SOLUSDT_ABSENT_BEFORE_ENTRY                  = "solusdt_absent_before_entry"
GATE_PROTECTED_EXPECTED_SYMBOLS_DOCUMENTED        = "protected_expected_symbols_documented"
GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW    = "protected_position_mismatch_manual_review"
GATE_ESTIMATED_NOTIONAL_WITHIN_CAP                = "estimated_notional_within_cap"
GATE_ENTRY_PARAMS_STABLE                          = "entry_params_stable"
GATE_STOP_BOUNDARY_STABLE                         = "stop_boundary_stable"
GATE_CLEANUP_BOUNDARY_STABLE                      = "cleanup_boundary_stable"
GATE_NO_AUTOMATION_TRIGGERS                       = "no_automation_triggers"
GATE_NO_SENDER_ADAPTER_READINESS                  = "no_sender_adapter_readiness"
GATE_NO_ENDPOINT_PERMISSIONS                      = "no_endpoint_permissions"
GATE_G20_STILL_ACTIVE                             = "g20_still_active"
GATE_READINESS_REVIEW_ONLY                        = "readiness_review_only"
GATE_READINESS_DOES_NOT_AUTHORIZE_EXECUTION       = "readiness_does_not_authorize_execution"

# Payload preview gates (19)
GATE_PAYLOAD_PREVIEW_ONLY                         = "payload_preview_only"
GATE_PAYLOAD_APPROVAL_GATE_ONLY                   = "payload_approval_gate_only"
GATE_PAYLOAD_SEND_ALLOWED_FALSE                   = "payload_send_allowed_false"
GATE_PAYLOAD_ENDPOINT_CALLED_FALSE                = "payload_endpoint_called_false"
GATE_PAYLOAD_REAL_PAYLOAD_FALSE                   = "payload_real_payload_false"
GATE_PAYLOAD_SIGNATURE_PRESENT_FALSE              = "payload_signature_present_false"
GATE_PAYLOAD_PRIVATE_HEADERS_EMPTY                = "payload_private_headers_empty"
GATE_PAYLOAD_ENDPOINT_PATH_ORDER_CREATE_REF       = "payload_endpoint_path_order_create_reference_only"
GATE_PAYLOAD_BASE_URL_DEMO_ONLY                   = "payload_base_url_demo_only"
GATE_PAYLOAD_CATEGORY_LINEAR                      = "payload_category_linear"
GATE_PAYLOAD_SYMBOL_SOLUSDT                       = "payload_symbol_solusdt"
GATE_PAYLOAD_SIDE_BUY                             = "payload_side_buy"
GATE_PAYLOAD_ORDER_TYPE_MARKET                    = "payload_order_type_market"
GATE_PAYLOAD_QTY_0_1                              = "payload_qty_0_1"
GATE_PAYLOAD_REDUCE_ONLY_FALSE                    = "payload_reduce_only_false"
GATE_PAYLOAD_CLOSE_ON_TRIGGER_FALSE               = "payload_close_on_trigger_false"
GATE_PAYLOAD_POSITION_IDX_ZERO                    = "payload_position_idx_zero"
GATE_PAYLOAD_ORDER_LINK_ID_PREFIX                 = "payload_order_link_id_prefix_documented"
GATE_PAYLOAD_NO_SENDER_ADAPTER                    = "payload_no_sender_adapter"

# Stop/cleanup manual gate gates (12)
GATE_STOP_ATTACH_REQUIRED_AFTER_ENTRY             = "stop_attach_required_after_entry"
GATE_STOP_ATTACH_NOT_INCLUDED_IN_THIS_TASK        = "stop_attach_not_included_in_this_task"
GATE_BOUNDARY_STOP_LOSS_61_18                     = "boundary_stop_loss_61_18"
GATE_BOUNDARY_TPSL_MODE_FULL                      = "boundary_tpsl_mode_full"
GATE_BOUNDARY_SL_TRIGGER_BY_MARKPRICE             = "boundary_sl_trigger_by_markprice"
GATE_CLEANUP_NOT_INCLUDED_IN_THIS_TASK            = "cleanup_not_included_in_this_task"
GATE_CLEANUP_SEPARATE_MANUAL_BOUNDARY             = "cleanup_separate_manual_boundary"
GATE_NO_AUTOMATIC_STOP_ATTACH                     = "no_automatic_stop_attach"
GATE_NO_AUTOMATIC_CLEANUP                         = "no_automatic_cleanup"
GATE_NO_AUTOMATIC_EMERGENCY_CLOSE                 = "no_automatic_emergency_close"
GATE_ENTRY_SUCCESS_WITHOUT_STOP_MANUAL_REVIEW     = "entry_success_without_stop_attach_manual_review"
GATE_FUTURE_ENTRY_REQUIRES_FOLLOW_UP_STOP_TASK    = "future_entry_must_require_immediate_follow_up_stop_task"

# Forbidden execution surface gates (17)
GATE_NO_REAL_SENDER                               = "no_real_sender"
GATE_NO_BYBIT_PRIVATE_CLIENT                      = "no_bybit_private_client"
GATE_NO_SIGNED_REQUEST                            = "no_signed_request"
GATE_NO_ENV_SECRET_LOAD                           = "no_env_secret_load"
GATE_NO_ORDER_ENDPOINT_SURFACE                    = "no_order_endpoint_surface"
GATE_NO_TRADING_STOP_ENDPOINT_SURFACE             = "no_trading_stop_endpoint_surface"
GATE_NO_CLOSE_ONLY_FALLBACK                       = "no_close_only_fallback"
GATE_NO_EMERGENCY_CLOSE_FALLBACK                  = "no_emergency_close_fallback"
GATE_NO_SOCKET                                    = "no_socket"
GATE_NO_HTTP_PRIMITIVES                           = "no_requests_httpx_urllib_http_client"
GATE_NO_BATCH_ORDER                               = "no_batch_order"
GATE_NO_LEVERAGE_MUTATION                         = "no_leverage_mutation"
GATE_NO_TRANSFER                                  = "no_transfer"
GATE_NO_WEBHOOK_TRIGGER                           = "no_webhook_trigger"
GATE_NO_DISCORD_TRIGGER                           = "no_discord_trigger"
GATE_NO_NOTION_TRIGGER                            = "no_notion_trigger"
GATE_NO_CRON_OR_SCHEDULER                         = "no_cron_or_scheduler_or_background_loop"

# Failure gates (19)
GATE_MISSING_ARTIFACT_FAIL_CLOSED                 = "missing_artifact_fail_closed"
GATE_STALE_READONLY_FAIL_CLOSED                   = "stale_readonly_fail_closed"
GATE_FINAL_REVIEW_STALE_FAIL_CLOSED               = "final_review_stale_fail_closed"
GATE_APPROVAL_PHRASE_MISMATCH_FAIL_CLOSED         = "approval_phrase_mismatch_fail_closed"
GATE_TOKEN_MISMATCH_FAIL_CLOSED                   = "token_mismatch_fail_closed"
GATE_TOKEN_REUSED_FAIL_CLOSED                     = "token_reused_fail_closed"
GATE_REQUIRED_INPUT_MISSING_FAIL_CLOSED           = "required_input_missing_fail_closed"
GATE_SOLUSDT_EXISTS_FAIL_CLOSED                   = "solusdt_already_exists_fail_closed"
GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW_FAIL = "protected_position_mismatch_manual_review_failure"
GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED            = "notional_cap_exceeded_fail_closed"
GATE_QTY_MISMATCH_FAIL_CLOSED                     = "qty_mismatch_fail_closed"
GATE_SIDE_MISMATCH_FAIL_CLOSED                    = "side_mismatch_fail_closed"
GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED             = "reduce_only_mismatch_fail_closed"
GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED           = "live_endpoint_detected_fail_closed"
GATE_SECRET_EMISSION_DETECTED_FAIL_CLOSED         = "secret_emission_detected_fail_closed"
GATE_NETWORK_PRIMITIVE_DETECTED_FAIL_CLOSED       = "network_primitive_detected_fail_closed"
GATE_SENDER_ADAPTER_DETECTED_FAIL_CLOSED          = "sender_adapter_detected_fail_closed"
GATE_ANY_G20_LIFT_ATTEMPT_FAIL_CLOSED             = "any_g20_lift_attempt_fail_closed"
GATE_ANY_AUTO_EXECUTION_ATTEMPT_FAIL_CLOSED       = "any_auto_execution_attempt_fail_closed"

# Documentation gates (5)
GATE_README_SYNC_REQUIRED                         = "readme_status_board_sync_required"
GATE_NEXT_ACTION_SYNC_REQUIRED                    = "next_action_sync_required"
GATE_COMMAND_LOG_SYNC_REQUIRED                    = "command_log_sync_required"
GATE_FORBIDDEN_STATUS_SYNC_REQUIRED               = "forbidden_status_sync_required"
GATE_NEXT_REQUIRED_TASK_SYNC_REQUIRED             = "next_required_task_sync_required"

# Execution guard gates (5)
GATE_REAL_ENTRY_EXECUTION_NOT_IMPL                = "real_entry_execution_not_implemented"
GATE_NO_REAL_ORDER_ENDPOINT                       = "no_real_order_endpoint_in_this_task"
GATE_NO_REAL_STOP_ENDPOINT                        = "no_real_stop_endpoint_in_this_task"
GATE_NO_POSITION_MODIFIED                         = "no_position_modified_in_this_task"
GATE_G20_NOT_LIFTED                               = "g20_policy_not_lifted_by_this_task"


# Hard-fail-closed gates --- if ANY of these surface the result is
# downgraded to FAIL_CLOSED regardless of other state.
_HARD_FAIL_GATES: frozenset[str] = frozenset({
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
    GATE_ENTRY_MANUAL_AUTH_DESIGN_MISSING,
    GATE_ENTRY_MANUAL_AUTH_DRY_RUN_MISSING,
    GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUS_UNACCEPTABLE,
    GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READINESS_EXECUTABLE,
    GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_RESULT_NOT_DOCUMENTED_ONLY,
    GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
    GATE_SOLUSDT_EXISTS_FAIL_CLOSED,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyGuardedEntryRealExecutionManualApprovalGateResult:
    """Read-only outcome of one guarded entry real execution manual approval gate review."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    manual_approval_gate_scope:        dict[str, Any] = field(default_factory=dict)
    manual_approval_token_gate:        dict[str, Any] = field(default_factory=dict)
    required_manual_approval_inputs:   dict[str, Any] = field(default_factory=dict)
    approval_gate_readiness_review:    dict[str, Any] = field(default_factory=dict)
    entry_payload_approval_preview:    dict[str, Any] = field(default_factory=dict)
    stop_cleanup_manual_gate_review:   dict[str, Any] = field(default_factory=dict)
    forbidden_execution_surface_review: dict[str, Any] = field(default_factory=dict)
    failure_and_abort_manual_gate:     dict[str, Any] = field(default_factory=dict)
    documentation_sync_review:         dict[str, Any] = field(default_factory=dict)
    audit_artifacts:                   dict[str, Any] = field(default_factory=dict)
    final_manual_approval_gate_verdict: dict[str, Any] = field(default_factory=dict)

    exact_approval_phrase:        str = EXACT_APPROVAL_PHRASE
    entry_token_pattern:          str = ENTRY_TOKEN_PATTERN
    sample_token:                 str = SAMPLE_TOKEN
    order_link_id_prefix:         str = ORDER_LINK_ID_PREFIX

    approval_gate_allowed:             bool = False
    real_entry_execution_requested:    bool = False
    real_execution_allowed:            bool = False
    real_entry_implemented:            bool = False
    guarded_entry_real_execution_manual_approval_gate: bool = True
    manual_approval_gate_only:         bool = True
    approval_grants_execution:         bool = False
    token_validation_simulated:        bool = True
    token_validated:                   bool = False
    real_token_validated:              bool = False
    exact_phrase_validated:            bool = False
    approval_inputs_validated:         bool = False
    entry_execution_included:          bool = False
    stop_execution_included:           bool = False
    cleanup_execution_included:        bool = False
    full_lifecycle_execution_included: bool = False
    current_task_real_execution_allowed: bool = False
    readiness_conclusion:              str  = READINESS_CONCLUSION_NOT_EXECUTABLE
    dry_run_authorization_result:      str  = DRY_RUN_AUTHORIZATION_RESULT

    order_create_path_ref:        str  = ORDER_CREATE_PATH_REF
    trading_stop_path_ref:        str  = TRADING_STOP_PATH_REF
    base_url_ref:                 str  = BASE_URL_DEMO_REF

    send_allowed:                 bool = False
    order_endpoint_called:        bool = False
    stop_endpoint_called:         bool = False
    no_position_modified:         bool = True
    no_live_endpoint:             bool = True
    no_orders_sent:               bool = True
    no_batch_order:               bool = True
    no_close_only_path:           bool = True
    emergency_close_invoked:      bool = False
    leverage_mutated:             bool = False
    transfer_invoked:             bool = False
    no_secrets_loaded:            bool = True
    secret_value_observed:        bool = False
    g20_policy_still_in_place:    bool = True
    g20_lifted:                   bool = False

    expected_commit_hash:         str = ""
    current_commit_hash:          str = ""

    existing_positions_touched:   list[str] = field(default_factory=list)
    upstream_lifecycle_summary_status:        str = ""
    upstream_runner_design_status:            str = ""
    upstream_runner_dry_run_status:           str = ""
    upstream_guarded_design_review_status:    str = ""
    upstream_guarded_entry_adapter_status:    str = ""
    upstream_guarded_stop_adapter_status:     str = ""
    upstream_guarded_cleanup_adapter_status:  str = ""
    upstream_guarded_lifecycle_summary_status: str = ""
    upstream_entry_real_permission_review_status: str = ""
    upstream_entry_manual_auth_design_status: str = ""
    upstream_entry_manual_auth_dry_run_status: str = ""
    upstream_entry_final_pre_execution_review_status: str = ""
    upstream_entry_final_pre_execution_review_readiness_conclusion: str = ""
    upstream_entry_final_pre_execution_review_authorization_result: str = ""

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = "TASK-014AN_guarded_entry_real_execution_adapter_design"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                                 self.timestamp_utc,
            "timestamp_utc":                             self.timestamp_utc,
            "mode":                                      self.mode,
            "selected_symbol":                           self.selected_symbol,
            "existing_position_symbols":                 list(self.existing_position_symbols),
            "stages":                                    {k: dict(v) for k, v in self.stages.items()},
            "stage_order":                               list(self.stage_order),
            "manual_approval_gate_scope":                dict(self.manual_approval_gate_scope),
            "manual_approval_token_gate":                dict(self.manual_approval_token_gate),
            "required_manual_approval_inputs":           dict(self.required_manual_approval_inputs),
            "approval_gate_readiness_review":            dict(self.approval_gate_readiness_review),
            "entry_payload_approval_preview":            dict(self.entry_payload_approval_preview),
            "stop_cleanup_manual_gate_review":           dict(self.stop_cleanup_manual_gate_review),
            "forbidden_execution_surface_review":        dict(self.forbidden_execution_surface_review),
            "failure_and_abort_manual_gate":             dict(self.failure_and_abort_manual_gate),
            "documentation_sync_review":                 dict(self.documentation_sync_review),
            "audit_artifacts":                           dict(self.audit_artifacts),
            "final_manual_approval_gate_verdict":        dict(self.final_manual_approval_gate_verdict),
            "exact_approval_phrase":                     self.exact_approval_phrase,
            "entry_token_pattern":                       self.entry_token_pattern,
            "sample_token":                              self.sample_token,
            "order_link_id_prefix":                      self.order_link_id_prefix,
            "approval_gate_allowed":                     self.approval_gate_allowed,
            "real_entry_execution_requested":            self.real_entry_execution_requested,
            "real_execution_allowed":                    self.real_execution_allowed,
            "real_entry_implemented":                    self.real_entry_implemented,
            "guarded_entry_real_execution_manual_approval_gate":
                self.guarded_entry_real_execution_manual_approval_gate,
            "manual_approval_gate_only":                 self.manual_approval_gate_only,
            "approval_grants_execution":                 self.approval_grants_execution,
            "token_validation_simulated":                self.token_validation_simulated,
            "token_validated":                           self.token_validated,
            "real_token_validated":                      self.real_token_validated,
            "exact_phrase_validated":                    self.exact_phrase_validated,
            "approval_inputs_validated":                 self.approval_inputs_validated,
            "entry_execution_included":                  self.entry_execution_included,
            "stop_execution_included":                   self.stop_execution_included,
            "cleanup_execution_included":                self.cleanup_execution_included,
            "full_lifecycle_execution_included":         self.full_lifecycle_execution_included,
            "current_task_real_execution_allowed":       self.current_task_real_execution_allowed,
            "readiness_conclusion":                      self.readiness_conclusion,
            "dry_run_authorization_result":              self.dry_run_authorization_result,
            "order_create_path_ref":                     self.order_create_path_ref,
            "trading_stop_path_ref":                     self.trading_stop_path_ref,
            "base_url_ref":                              self.base_url_ref,
            "send_allowed":                              self.send_allowed,
            "order_endpoint_called":                     self.order_endpoint_called,
            "stop_endpoint_called":                      self.stop_endpoint_called,
            "no_position_modified":                      self.no_position_modified,
            "no_live_endpoint":                          self.no_live_endpoint,
            "no_orders_sent":                            self.no_orders_sent,
            "no_batch_order":                            self.no_batch_order,
            "no_close_only_path":                        self.no_close_only_path,
            "emergency_close_invoked":                   self.emergency_close_invoked,
            "leverage_mutated":                          self.leverage_mutated,
            "transfer_invoked":                          self.transfer_invoked,
            "no_secrets_loaded":                         self.no_secrets_loaded,
            "secret_value_observed":                     self.secret_value_observed,
            "g20_policy_still_in_place":                 self.g20_policy_still_in_place,
            "g20_lifted":                                self.g20_lifted,
            "expected_commit_hash":                      self.expected_commit_hash,
            "current_commit_hash":                       self.current_commit_hash,
            "existing_positions_touched":                list(self.existing_positions_touched),
            "upstream_lifecycle_summary_status":         self.upstream_lifecycle_summary_status,
            "upstream_runner_design_status":             self.upstream_runner_design_status,
            "upstream_runner_dry_run_status":            self.upstream_runner_dry_run_status,
            "upstream_guarded_design_review_status":     self.upstream_guarded_design_review_status,
            "upstream_guarded_entry_adapter_status":     self.upstream_guarded_entry_adapter_status,
            "upstream_guarded_stop_adapter_status":      self.upstream_guarded_stop_adapter_status,
            "upstream_guarded_cleanup_adapter_status":   self.upstream_guarded_cleanup_adapter_status,
            "upstream_guarded_lifecycle_summary_status": self.upstream_guarded_lifecycle_summary_status,
            "upstream_entry_real_permission_review_status":
                self.upstream_entry_real_permission_review_status,
            "upstream_entry_manual_auth_design_status":  self.upstream_entry_manual_auth_design_status,
            "upstream_entry_manual_auth_dry_run_status": self.upstream_entry_manual_auth_dry_run_status,
            "upstream_entry_final_pre_execution_review_status":
                self.upstream_entry_final_pre_execution_review_status,
            "upstream_entry_final_pre_execution_review_readiness_conclusion":
                self.upstream_entry_final_pre_execution_review_readiness_conclusion,
            "upstream_entry_final_pre_execution_review_authorization_result":
                self.upstream_entry_final_pre_execution_review_authorization_result,
            "blocked_gates":                             list(self.blocked_gates),
            "failed_stage":                              self.failed_stage,
            "status":                                    self.status,
            "next_required_task":                        self.next_required_task,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    return f


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _positions_from_reconciliation(
    reconciliation: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(reconciliation, dict):
        return [
            {"symbol": s, "side": "", "qty": 0.0, "entry": 0.0, "stop": 0.0}
            for s in EXISTING_POSITION_SYMBOLS
        ]
    rows = reconciliation.get("positions", None)
    if not isinstance(rows, list) or not rows:
        return [
            {"symbol": s, "side": "", "qty": 0.0, "entry": 0.0, "stop": 0.0}
            for s in EXISTING_POSITION_SYMBOLS
        ]
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            sym = _safe_str(row.get("symbol", ""))
            if not sym:
                continue
            out.append({
                "symbol": sym,
                "side":   _safe_str(row.get("side", "")),
                "qty":    _safe_float(row.get("quantity",    row.get("qty",   0.0))),
                "entry":  _safe_float(row.get("entry_price", row.get("entry", 0.0))),
                "stop":   _safe_float(row.get("stop_price",  row.get("stop",  0.0))),
            })
    if not out:
        out = [
            {"symbol": s, "side": "", "qty": 0.0, "entry": 0.0, "stop": 0.0}
            for s in EXISTING_POSITION_SYMBOLS
        ]
    return out


def _symbols_only(snapshot: list[dict[str, Any]]) -> list[str]:
    return [_safe_str(row.get("symbol", "")) for row in snapshot]


# ---------------------------------------------------------------------------
# Guarded entry real execution manual approval gate
# ---------------------------------------------------------------------------

class DemoTinyGuardedEntryRealExecutionManualApprovalGate:
    """
    Pure-computation guarded entry real execution manual approval gate.
    Re-reviews 22 upstream artifacts and emits the manual approval gate
    verdict. Never opens a socket, reads no environment variables,
    performs no HMAC signing, never validates any real token or phrase,
    never treats any token or phrase as authorization, never auto-commits
    / auto-pushes git, and NEVER invokes the order-create or trading-stop
    endpoints.

    --allow-approval-gate         --> status promoted to
        TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_READY_BUT_EXECUTION_DISABLED

    --allow-real-entry-execution  --> status fixed to
        REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED   (no socket opened)
    """

    def __init__(self) -> None:
        pass

    def run_review(
        self,
        readonly_smoke:                       dict[str, Any] | None,
        reconciliation:                       dict[str, Any] | None,
        protection:                           dict[str, Any] | None,
        contract:                             dict[str, Any] | None,
        noop_plan:                            dict[str, Any] | None,
        lifecycle_mock:                       dict[str, Any] | None,
        real_permission_gate:                 dict[str, Any] | None,
        tiny_entry_permission_gate:           dict[str, Any] | None,
        tiny_stop_permission_gate:            dict[str, Any] | None,
        tiny_cleanup_permission_gate:         dict[str, Any] | None,
        lifecycle_summary:                    dict[str, Any] | None,
        runner_design:                        dict[str, Any] | None,
        runner_dry_run:                       dict[str, Any] | None,
        guarded_design_review:                dict[str, Any] | None,
        guarded_entry_adapter:                dict[str, Any] | None,
        guarded_stop_adapter:                 dict[str, Any] | None,
        guarded_cleanup_adapter:              dict[str, Any] | None,
        guarded_lifecycle_summary:            dict[str, Any] | None,
        entry_real_permission_review:         dict[str, Any] | None,
        entry_manual_authorization_design:    dict[str, Any] | None,
        entry_manual_authorization_dry_run:   dict[str, Any] | None,
        entry_final_pre_execution_review:     dict[str, Any] | None,
        symbol:                               str  = DEFAULT_SELECTED_SYMBOL,
        expected_commit_hash:                 str  = "",
        current_commit_hash:                  str  = "",
        allow_approval_gate:                  bool = False,
        allow_real_entry_execution:           bool = False,
        _now:                                 datetime | None = None,
    ) -> TinyGuardedEntryRealExecutionManualApprovalGateResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_entry_execution:
            mode = MODE_REAL_ENTRY_EXEC_GUARD
        elif allow_approval_gate:
            mode = MODE_GATE_APPROVAL
        else:
            mode = MODE_GATE_CHECKLIST

        blocked: list[str] = []
        stages:  dict[str, dict[str, Any]] = {}

        # ===============================================================
        # stage_0_artifact_preflight
        # ===============================================================
        sym = _safe_str(symbol)
        existing_snapshot = _positions_from_reconciliation(reconciliation)
        existing_symbols  = _symbols_only(existing_snapshot)

        readonly_present       = isinstance(readonly_smoke, dict) and bool(readonly_smoke)
        recon_present          = isinstance(reconciliation, dict) and bool(reconciliation)
        protection_present     = isinstance(protection, dict) and bool(protection)
        contract_present       = isinstance(contract, dict) and bool(contract)
        noop_present           = isinstance(noop_plan, dict) and bool(noop_plan)
        lifecycle_present      = isinstance(lifecycle_mock, dict) and bool(lifecycle_mock)
        real_perm_present      = isinstance(real_permission_gate, dict) and bool(real_permission_gate)
        entry_perm_present     = isinstance(tiny_entry_permission_gate, dict) and bool(tiny_entry_permission_gate)
        stop_perm_present      = isinstance(tiny_stop_permission_gate, dict) and bool(tiny_stop_permission_gate)
        cleanup_perm_present   = isinstance(tiny_cleanup_permission_gate, dict) and bool(tiny_cleanup_permission_gate)
        summary_present        = isinstance(lifecycle_summary, dict) and bool(lifecycle_summary)
        runner_design_present  = isinstance(runner_design, dict) and bool(runner_design)
        runner_dry_run_present = isinstance(runner_dry_run, dict) and bool(runner_dry_run)
        guarded_review_present = isinstance(guarded_design_review, dict) and bool(guarded_design_review)
        guarded_entry_present  = isinstance(guarded_entry_adapter, dict) and bool(guarded_entry_adapter)
        guarded_stop_present   = isinstance(guarded_stop_adapter, dict) and bool(guarded_stop_adapter)
        guarded_cleanup_present = isinstance(guarded_cleanup_adapter, dict) and bool(guarded_cleanup_adapter)
        guarded_lifecycle_present = isinstance(guarded_lifecycle_summary, dict) and bool(guarded_lifecycle_summary)
        entry_perm_review_present = isinstance(entry_real_permission_review, dict) and bool(entry_real_permission_review)
        entry_auth_design_present = isinstance(entry_manual_authorization_design, dict) and bool(entry_manual_authorization_design)
        entry_auth_dry_run_present = isinstance(entry_manual_authorization_dry_run, dict) and bool(entry_manual_authorization_dry_run)
        entry_final_review_present = isinstance(entry_final_pre_execution_review, dict) and bool(entry_final_pre_execution_review)

        endpoint_family = _safe_str((readonly_smoke or {}).get("endpoint_family", ""))
        account_mode    = _safe_str((readonly_smoke or {}).get("account_mode", ""))
        proof_strength  = _safe_str((readonly_smoke or {}).get("proof_strength", ""))
        position_details_source = _safe_str(
            (reconciliation or {}).get(
                "position_details_source",
                (reconciliation or {}).get("mode", ""),
            )
        )
        lifecycle_status            = _safe_str((lifecycle_mock or {}).get("status", ""))
        summary_status              = _safe_str((lifecycle_summary or {}).get("status", ""))
        runner_design_status        = _safe_str((runner_design or {}).get("status", ""))
        runner_dry_run_status       = _safe_str((runner_dry_run or {}).get("status", ""))
        guarded_review_status       = _safe_str((guarded_design_review or {}).get("status", ""))
        guarded_entry_status        = _safe_str((guarded_entry_adapter or {}).get("status", ""))
        guarded_stop_status         = _safe_str((guarded_stop_adapter or {}).get("status", ""))
        guarded_cleanup_status      = _safe_str((guarded_cleanup_adapter or {}).get("status", ""))
        guarded_lifecycle_status    = _safe_str((guarded_lifecycle_summary or {}).get("status", ""))
        entry_perm_review_status    = _safe_str((entry_real_permission_review or {}).get("status", ""))
        entry_auth_design_status    = _safe_str((entry_manual_authorization_design or {}).get("status", ""))
        entry_auth_dry_run_status   = _safe_str((entry_manual_authorization_dry_run or {}).get("status", ""))
        entry_final_review_status   = _safe_str((entry_final_pre_execution_review or {}).get("status", ""))
        entry_final_review_readiness = _safe_str(
            (entry_final_pre_execution_review or {}).get("readiness_conclusion", "")
        )
        entry_final_review_result   = _safe_str(
            (entry_final_pre_execution_review or {}).get("dry_run_authorization_result", "")
        )

        if not readonly_present:
            blocked.append(GATE_READONLY_SMOKE_MISSING)
        if not recon_present:
            blocked.append(GATE_RECONCILIATION_MISSING)
        if not protection_present:
            blocked.append(GATE_PROTECTION_MISSING)
        if not contract_present:
            blocked.append(GATE_CONTRACT_MISSING)
        if not noop_present:
            blocked.append(GATE_NOOP_PLAN_MISSING)
        if not lifecycle_present:
            blocked.append(GATE_LIFECYCLE_MOCK_MISSING)
        if not real_perm_present:
            blocked.append(GATE_REAL_PERMISSION_GATE_MISSING)
        if not entry_perm_present:
            blocked.append(GATE_TINY_ENTRY_PERMISSION_GATE_MISSING)
        if not stop_perm_present:
            blocked.append(GATE_TINY_STOP_PERMISSION_GATE_MISSING)
        if not cleanup_perm_present:
            blocked.append(GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING)
        if not summary_present:
            blocked.append(GATE_LIFECYCLE_SUMMARY_MISSING)
        if not runner_design_present:
            blocked.append(GATE_RUNNER_DESIGN_MISSING)
        if not runner_dry_run_present:
            blocked.append(GATE_RUNNER_DRY_RUN_MISSING)
        if not guarded_review_present:
            blocked.append(GATE_GUARDED_DESIGN_REVIEW_MISSING)
        if not guarded_entry_present:
            blocked.append(GATE_GUARDED_ENTRY_ADAPTER_MISSING)
        if not guarded_stop_present:
            blocked.append(GATE_GUARDED_STOP_ADAPTER_MISSING)
        if not guarded_cleanup_present:
            blocked.append(GATE_GUARDED_CLEANUP_ADAPTER_MISSING)
        if not guarded_lifecycle_present:
            blocked.append(GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING)
        if not entry_perm_review_present:
            blocked.append(GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING)
        if not entry_auth_design_present:
            blocked.append(GATE_ENTRY_MANUAL_AUTH_DESIGN_MISSING)
        if not entry_auth_dry_run_present:
            blocked.append(GATE_ENTRY_MANUAL_AUTH_DRY_RUN_MISSING)
        if not entry_final_review_present:
            blocked.append(GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING)

        if readonly_present and endpoint_family and endpoint_family != EXPECTED_ENDPOINT_FAMILY:
            blocked.append(GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO)
        if readonly_present and account_mode and account_mode != EXPECTED_ACCOUNT_MODE:
            blocked.append(GATE_ACCOUNT_MODE_NOT_DEMO)
        if readonly_present and proof_strength and proof_strength != EXPECTED_PROOF_STRENGTH:
            blocked.append(GATE_PROOF_STRENGTH_NOT_STRONG)
        if recon_present and position_details_source and position_details_source != EXPECTED_POSITION_DETAILS_SOURCE:
            blocked.append(GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY)

        if entry_final_review_present and entry_final_review_status and (
            entry_final_review_status not in ACCEPTABLE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUSES
        ):
            blocked.append(GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUS_UNACCEPTABLE)

        if entry_final_review_present and entry_final_review_readiness and (
            entry_final_review_readiness != READINESS_CONCLUSION_NOT_EXECUTABLE
        ):
            blocked.append(GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READINESS_EXECUTABLE)

        if entry_final_review_present and entry_final_review_result and (
            entry_final_review_result != DRY_RUN_AUTHORIZATION_RESULT
        ):
            blocked.append(GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_RESULT_NOT_DOCUMENTED_ONLY)

        if sym and sym != GATE_EXPECTED_SYMBOL:
            blocked.append(GATE_SELECTED_SYMBOL_NOT_SOLUSDT)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 22 upstream artifacts + runtime proof envelope + final pre-execution review status / readiness / result.",
            "readonly_smoke_present":                   readonly_present,
            "reconciliation_present":                   recon_present,
            "protection_present":                       protection_present,
            "contract_present":                         contract_present,
            "noop_plan_present":                        noop_present,
            "lifecycle_mock_present":                   lifecycle_present,
            "real_permission_gate_present":             real_perm_present,
            "tiny_entry_permission_gate_present":       entry_perm_present,
            "tiny_stop_permission_gate_present":        stop_perm_present,
            "tiny_cleanup_permission_gate_present":     cleanup_perm_present,
            "lifecycle_summary_present":                summary_present,
            "runner_design_present":                    runner_design_present,
            "runner_dry_run_present":                   runner_dry_run_present,
            "guarded_design_review_present":            guarded_review_present,
            "guarded_entry_adapter_present":            guarded_entry_present,
            "guarded_stop_adapter_present":             guarded_stop_present,
            "guarded_cleanup_adapter_present":          guarded_cleanup_present,
            "guarded_lifecycle_summary_present":        guarded_lifecycle_present,
            "entry_real_permission_review_present":     entry_perm_review_present,
            "entry_manual_authorization_design_present": entry_auth_design_present,
            "entry_manual_authorization_dry_run_present": entry_auth_dry_run_present,
            "entry_final_pre_execution_review_present": entry_final_review_present,
            "endpoint_family_observed":                 endpoint_family,
            "endpoint_family_expected":                 EXPECTED_ENDPOINT_FAMILY,
            "account_mode_observed":                    account_mode,
            "account_mode_expected":                    EXPECTED_ACCOUNT_MODE,
            "proof_strength_observed":                  proof_strength,
            "proof_strength_expected":                  EXPECTED_PROOF_STRENGTH,
            "position_details_source_observed":         position_details_source,
            "position_details_source_expected":         EXPECTED_POSITION_DETAILS_SOURCE,
            "lifecycle_status_observed":                lifecycle_status,
            "lifecycle_status_expected":                EXPECTED_LIFECYCLE_STATUS,
            "lifecycle_summary_status_observed":        summary_status,
            "runner_design_status_observed":            runner_design_status,
            "runner_dry_run_status_observed":           runner_dry_run_status,
            "guarded_design_review_status_observed":    guarded_review_status,
            "guarded_entry_adapter_status_observed":    guarded_entry_status,
            "guarded_stop_adapter_status_observed":     guarded_stop_status,
            "guarded_cleanup_adapter_status_observed":  guarded_cleanup_status,
            "guarded_lifecycle_summary_status_observed": guarded_lifecycle_status,
            "entry_real_permission_review_status_observed": entry_perm_review_status,
            "entry_manual_authorization_design_status_observed": entry_auth_design_status,
            "entry_manual_authorization_dry_run_status_observed": entry_auth_dry_run_status,
            "entry_final_pre_execution_review_status_observed": entry_final_review_status,
            "entry_final_pre_execution_review_status_acceptable": sorted(
                ACCEPTABLE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUSES
            ),
            "entry_final_pre_execution_review_readiness_observed": entry_final_review_readiness,
            "entry_final_pre_execution_review_readiness_expected": READINESS_CONCLUSION_NOT_EXECUTABLE,
            "entry_final_pre_execution_review_authorization_result_observed": entry_final_review_result,
            "entry_final_pre_execution_review_authorization_result_expected": DRY_RUN_AUTHORIZATION_RESULT,
            "selected_symbol":                          sym,
            "selected_symbol_expected":                 GATE_EXPECTED_SYMBOL,
            "current_task_real_execution_allowed":      False,
        }

        # ===============================================================
        # stage_1_manual_approval_gate_scope
        # ===============================================================
        manual_approval_gate_scope: dict[str, Any] = {
            "guarded_entry_real_execution_manual_approval_gate": True,
            "manual_approval_gate_only":            True,
            "approval_gate_does_not_execute":       True,
            "entry_execution_included":             False,
            "stop_execution_included":              False,
            "cleanup_execution_included":           False,
            "full_lifecycle_execution_included":    False,
            "real_entry_implemented":               False,
            "real_execution_allowed":               False,
            "approval_grants_execution":            False,
            "send_allowed":                         False,
            "order_endpoint_called":                False,
            "stop_endpoint_called":                 False,
            "no_endpoint_invoked_in_this_task":     True,
            "no_position_modified":                 True,
            "no_secrets_loaded":                    True,
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "next_required_task":                   "TASK-014AN_guarded_entry_real_execution_adapter_design",
            "scope_summary": (
                "TASK-014AM only documents the human-approval gate that must "
                "precede any future real tiny entry execution. It never "
                "validates any real token or phrase, never treats any token "
                "or phrase as authorization, never sends an order, never "
                "calls any endpoint, never modifies any position, never lifts "
                "G20, never loads any secret, and never auto-commits / "
                "auto-pushes git."
            ),
        }
        stages[STAGE_1_MANUAL_APPROVAL_GATE_SCOPE] = {
            "stage":   STAGE_1_MANUAL_APPROVAL_GATE_SCOPE,
            "summary": "Assert guarded entry real execution manual approval gate scope (gate-only).",
            "manual_approval_gate_scope":           manual_approval_gate_scope,
        }
        blocked.append(GATE_MANUAL_APPROVAL_GATE_ONLY)
        blocked.append(GATE_APPROVAL_GATE_DOES_NOT_EXECUTE)
        blocked.append(GATE_ENTRY_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_STOP_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_CLEANUP_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE)
        blocked.append(GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE)
        blocked.append(GATE_APPROVAL_DOES_NOT_GRANT_EXECUTION_SCOPE)
        blocked.append(GATE_SEND_NOT_ALLOWED_SCOPE)
        blocked.append(GATE_ORDER_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_STOP_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_NO_ENDPOINT_INVOKED)
        blocked.append(GATE_NO_POSITION_MODIFIED_SCOPE)
        blocked.append(GATE_NO_SECRETS_LOADED)
        blocked.append(GATE_NO_G20_LIFT)

        # ===============================================================
        # stage_2_manual_approval_token_gate
        # ===============================================================
        manual_approval_token_gate: dict[str, Any] = {
            "token_pattern":                         ENTRY_TOKEN_PATTERN,
            "sample_token":                          SAMPLE_TOKEN,
            "token_validated":                       False,
            "real_token_validated":                  False,
            "token_format_not_authorization":        True,
            "token_does_not_grant_execution":        True,
            "token_requires_future_task_revalidation": True,
            "token_must_be_single_use":              True,
            "token_must_include_date":               True,
            "token_must_include_symbol":             True,
            "token_reuse_policy":                    "forbidden",
            "token_expiry_policy":                   "documented_only",
            "token_contains_no_secret":              True,
            "token_not_logged_as_secret":            True,
        }
        stages[STAGE_2_MANUAL_APPROVAL_TOKEN_GATE] = {
            "stage":   STAGE_2_MANUAL_APPROVAL_TOKEN_GATE,
            "summary": "Manual approval token gate (token never validated; never authorization).",
            "manual_approval_token_gate":            manual_approval_token_gate,
        }
        blocked.append(GATE_TOKEN_PATTERN_DOCUMENTED)
        blocked.append(GATE_SAMPLE_TOKEN_DOCUMENTED)
        blocked.append(GATE_TOKEN_NOT_VALIDATED)
        blocked.append(GATE_REAL_TOKEN_NOT_VALIDATED)
        blocked.append(GATE_TOKEN_FORMAT_NOT_AUTHORIZATION)
        blocked.append(GATE_TOKEN_DOES_NOT_GRANT_EXECUTION)
        blocked.append(GATE_TOKEN_REQUIRES_FUTURE_TASK_REVALIDATION)
        blocked.append(GATE_TOKEN_SINGLE_USE_DOCUMENTED)
        blocked.append(GATE_TOKEN_INCLUDES_DATE)
        blocked.append(GATE_TOKEN_INCLUDES_SYMBOL)
        blocked.append(GATE_TOKEN_REUSE_FORBIDDEN)
        blocked.append(GATE_TOKEN_EXPIRY_DOCUMENTED)
        blocked.append(GATE_TOKEN_CONTAINS_NO_SECRET)
        blocked.append(GATE_TOKEN_NOT_LOGGED_AS_SECRET)

        # ===============================================================
        # stage_3_required_manual_approval_inputs
        # ===============================================================
        required_manual_approval_inputs: dict[str, Any] = {
            "exact_approval_phrase":                 EXACT_APPROVAL_PHRASE,
            "exact_phrase_validated":                False,
            "approval_inputs":                       list(REQUIRED_MANUAL_APPROVAL_INPUTS),
            "required_confirm_flags":                list(REQUIRED_CONFIRM_FLAGS),
            "required_input_count":                  len(REQUIRED_MANUAL_APPROVAL_INPUTS),
            "approval_inputs_documented":            True,
            "approval_inputs_validated":             False,
            "approval_inputs_do_not_authorize_execution": True,
            "rick_explicit_authorization_still_required": True,
            "second_confirmation_required":          True,
            "independent_reviewer_recommended":      True,
        }
        stages[STAGE_3_REQUIRED_MANUAL_APPROVAL_INPUTS] = {
            "stage":   STAGE_3_REQUIRED_MANUAL_APPROVAL_INPUTS,
            "summary": "Required manual approval inputs (phrase + 11 confirm flags) documented; never validated.",
            "required_manual_approval_inputs":       required_manual_approval_inputs,
        }
        blocked.append(GATE_EXACT_APPROVAL_PHRASE_DOCUMENTED)
        blocked.append(GATE_EXACT_PHRASE_NOT_VALIDATED)
        blocked.append(GATE_APPROVAL_INPUTS_DOCUMENTED)
        blocked.append(GATE_APPROVAL_INPUTS_NOT_VALIDATED)
        blocked.append(GATE_APPROVAL_INPUTS_DO_NOT_AUTHORIZE_EXECUTION)
        blocked.append(GATE_RICK_EXPLICIT_AUTHORIZATION_REQUIRED)
        blocked.append(GATE_SECOND_CONFIRMATION_REQUIRED)
        blocked.append(GATE_INDEPENDENT_REVIEWER_RECOMMENDED)
        blocked.append(GATE_CONFIRM_SYMBOL_FLAG)
        blocked.append(GATE_CONFIRM_SIDE_FLAG)
        blocked.append(GATE_CONFIRM_QTY_FLAG)
        blocked.append(GATE_CONFIRM_MAX_NOTIONAL_FLAG)
        blocked.append(GATE_CONFIRM_REDUCE_ONLY_FLAG)
        blocked.append(GATE_CONFIRM_POSITION_IDX_FLAG)
        blocked.append(GATE_CONFIRM_ORDER_TYPE_FLAG)
        blocked.append(GATE_CONFIRM_EXISTING_SYMBOLS_FLAG)
        blocked.append(GATE_CONFIRM_STOP_REQUIRED_FLAG)
        blocked.append(GATE_CONFIRM_CLEANUP_BOUNDARY_FLAG)
        blocked.append(GATE_CONFIRM_NO_ORDER_WILL_BE_SENT_FLAG)

        # ===============================================================
        # stage_4_approval_gate_readiness_review
        # ===============================================================
        solusdt_in_existing = GATE_EXPECTED_SYMBOL in existing_symbols
        if solusdt_in_existing:
            blocked.append(GATE_SOLUSDT_EXISTS_FAIL_CLOSED)

        approval_gate_readiness_review: dict[str, Any] = {
            "final_pre_execution_review_ready":      True,
            "ak_dry_run_ready":                      True,
            "aj_design_ready":                       True,
            "ai_permission_review_ready":            True,
            "solusdt_absent_before_entry":           (not solusdt_in_existing),
            "protected_expected_symbols":            list(EXISTING_POSITION_SYMBOLS),
            "protected_expected_symbols_doc_order":  list(EXISTING_POSITION_SYMBOLS_DOC_ORDER),
            "protected_expected_symbols_documented": True,
            "protected_position_mismatch_policy":    "MANUAL_REVIEW_REQUIRED",
            "estimated_notional_usdt":               GATE_EXPECTED_ESTIMATED_NOTIONAL,
            "max_notional_usdt":                     GATE_EXPECTED_MAX_NOTIONAL_USDT,
            "estimated_notional_within_cap": (
                GATE_EXPECTED_ESTIMATED_NOTIONAL <= GATE_EXPECTED_MAX_NOTIONAL_USDT
            ),
            "entry_params_stable":                   True,
            "stop_boundary_stable":                  True,
            "cleanup_boundary_stable":               True,
            "no_automation_triggers":                True,
            "no_sender_adapter":                     True,
            "no_endpoint_permissions":               True,
            "g20_still_active":                      True,
            "readiness_review_only":                 True,
            "readiness_does_not_authorize_execution": True,
        }
        stages[STAGE_4_APPROVAL_GATE_READINESS_REVIEW] = {
            "stage":   STAGE_4_APPROVAL_GATE_READINESS_REVIEW,
            "summary": "Approval gate readiness review (review-only; never grants execution).",
            "approval_gate_readiness_review":        approval_gate_readiness_review,
        }
        blocked.append(GATE_FINAL_PRE_EXECUTION_REVIEW_READY)
        blocked.append(GATE_AK_DRY_RUN_READY)
        blocked.append(GATE_AJ_DESIGN_READY)
        blocked.append(GATE_AI_PERMISSION_REVIEW_READY)
        blocked.append(GATE_SOLUSDT_ABSENT_BEFORE_ENTRY)
        blocked.append(GATE_PROTECTED_EXPECTED_SYMBOLS_DOCUMENTED)
        blocked.append(GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW)
        blocked.append(GATE_ESTIMATED_NOTIONAL_WITHIN_CAP)
        blocked.append(GATE_ENTRY_PARAMS_STABLE)
        blocked.append(GATE_STOP_BOUNDARY_STABLE)
        blocked.append(GATE_CLEANUP_BOUNDARY_STABLE)
        blocked.append(GATE_NO_AUTOMATION_TRIGGERS)
        blocked.append(GATE_NO_SENDER_ADAPTER_READINESS)
        blocked.append(GATE_NO_ENDPOINT_PERMISSIONS)
        blocked.append(GATE_G20_STILL_ACTIVE)
        blocked.append(GATE_READINESS_REVIEW_ONLY)
        blocked.append(GATE_READINESS_DOES_NOT_AUTHORIZE_EXECUTION)

        # ===============================================================
        # stage_5_entry_payload_approval_preview
        # ===============================================================
        sym_eff = sym or GATE_EXPECTED_SYMBOL
        entry_payload_approval_preview: dict[str, Any] = {
            "preview_only":                          True,
            "approval_gate_only":                    True,
            "send_allowed":                          False,
            "endpoint_called":                       False,
            "real_payload":                          False,
            "signature_present":                     False,
            "private_headers":                       [],
            "endpoint_path_ref":                     ORDER_CREATE_PATH_REF,
            "base_url_ref":                          BASE_URL_DEMO_REF,
            "demo_endpoint_allowlist":               list(DEMO_ENDPOINT_ALLOWLIST),
            "live_endpoint_denylist":                list(LIVE_ENDPOINT_DENYLIST),
            "category":                              GATE_EXPECTED_CATEGORY,
            "symbol":                                sym_eff,
            "side":                                  GATE_EXPECTED_ENTRY_SIDE,
            "orderType":                             GATE_EXPECTED_ORDER_TYPE,
            "qty":                                   GATE_EXPECTED_QTY,
            "reduceOnly":                            GATE_EXPECTED_REDUCE_ONLY,
            "closeOnTrigger":                        GATE_EXPECTED_CLOSE_ON_TRIGGER,
            "positionIdx":                           GATE_EXPECTED_POSITION_IDX,
            "orderLinkId_prefix":                    ORDER_LINK_ID_PREFIX,
            "sender_adapter_invoked":                False,
        }
        stages[STAGE_5_ENTRY_PAYLOAD_APPROVAL_PREVIEW] = {
            "stage":   STAGE_5_ENTRY_PAYLOAD_APPROVAL_PREVIEW,
            "summary": "Entry payload approval preview (gate-only; never sent; never signed).",
            "entry_payload_approval_preview":        entry_payload_approval_preview,
        }
        blocked.append(GATE_PAYLOAD_PREVIEW_ONLY)
        blocked.append(GATE_PAYLOAD_APPROVAL_GATE_ONLY)
        blocked.append(GATE_PAYLOAD_SEND_ALLOWED_FALSE)
        blocked.append(GATE_PAYLOAD_ENDPOINT_CALLED_FALSE)
        blocked.append(GATE_PAYLOAD_REAL_PAYLOAD_FALSE)
        blocked.append(GATE_PAYLOAD_SIGNATURE_PRESENT_FALSE)
        blocked.append(GATE_PAYLOAD_PRIVATE_HEADERS_EMPTY)
        blocked.append(GATE_PAYLOAD_ENDPOINT_PATH_ORDER_CREATE_REF)
        blocked.append(GATE_PAYLOAD_BASE_URL_DEMO_ONLY)
        blocked.append(GATE_PAYLOAD_CATEGORY_LINEAR)
        blocked.append(GATE_PAYLOAD_SYMBOL_SOLUSDT)
        blocked.append(GATE_PAYLOAD_SIDE_BUY)
        blocked.append(GATE_PAYLOAD_ORDER_TYPE_MARKET)
        blocked.append(GATE_PAYLOAD_QTY_0_1)
        blocked.append(GATE_PAYLOAD_REDUCE_ONLY_FALSE)
        blocked.append(GATE_PAYLOAD_CLOSE_ON_TRIGGER_FALSE)
        blocked.append(GATE_PAYLOAD_POSITION_IDX_ZERO)
        blocked.append(GATE_PAYLOAD_ORDER_LINK_ID_PREFIX)
        blocked.append(GATE_PAYLOAD_NO_SENDER_ADAPTER)

        # ===============================================================
        # stage_6_stop_cleanup_manual_gate_review
        # ===============================================================
        stop_cleanup_manual_gate_review: dict[str, Any] = {
            "stop_attach_required_after_entry":      True,
            "stop_attach_not_included_in_this_task": True,
            "stop_loss":                             GATE_EXPECTED_STOP_LOSS,
            "tpsl_mode":                             GATE_EXPECTED_TPSL_MODE,
            "sl_trigger_by":                         GATE_EXPECTED_SL_TRIGGER_BY,
            "cleanup_not_included_in_this_task":     True,
            "cleanup_separate_manual_boundary":      True,
            "no_automatic_stop_attach":              True,
            "no_automatic_cleanup":                  True,
            "no_automatic_emergency_close":          True,
            "entry_success_without_stop_attach_policy": "MANUAL_REVIEW_REQUIRED",
            "future_entry_must_require_immediate_follow_up_stop_task": True,
        }
        stages[STAGE_6_STOP_CLEANUP_MANUAL_GATE_REVIEW] = {
            "stage":   STAGE_6_STOP_CLEANUP_MANUAL_GATE_REVIEW,
            "summary": "Stop attach / cleanup manual gate review (separate manual boundaries).",
            "stop_cleanup_manual_gate_review":       stop_cleanup_manual_gate_review,
        }
        blocked.append(GATE_STOP_ATTACH_REQUIRED_AFTER_ENTRY)
        blocked.append(GATE_STOP_ATTACH_NOT_INCLUDED_IN_THIS_TASK)
        blocked.append(GATE_BOUNDARY_STOP_LOSS_61_18)
        blocked.append(GATE_BOUNDARY_TPSL_MODE_FULL)
        blocked.append(GATE_BOUNDARY_SL_TRIGGER_BY_MARKPRICE)
        blocked.append(GATE_CLEANUP_NOT_INCLUDED_IN_THIS_TASK)
        blocked.append(GATE_CLEANUP_SEPARATE_MANUAL_BOUNDARY)
        blocked.append(GATE_NO_AUTOMATIC_STOP_ATTACH)
        blocked.append(GATE_NO_AUTOMATIC_CLEANUP)
        blocked.append(GATE_NO_AUTOMATIC_EMERGENCY_CLOSE)
        blocked.append(GATE_ENTRY_SUCCESS_WITHOUT_STOP_MANUAL_REVIEW)
        blocked.append(GATE_FUTURE_ENTRY_REQUIRES_FOLLOW_UP_STOP_TASK)

        # ===============================================================
        # stage_7_forbidden_execution_surface_review
        # ===============================================================
        forbidden_execution_surface_review: dict[str, Any] = {
            "no_real_sender":                        True,
            "no_bybit_private_client":               True,
            "no_signed_request":                     True,
            "no_env_secret_load":                    True,
            "no_order_endpoint":                     True,
            "no_trading_stop_endpoint":              True,
            "no_close_only_fallback":                True,
            "no_emergency_close_fallback":           True,
            "no_socket":                             True,
            "no_requests_httpx_urllib_http_client":  True,
            "no_batch_order":                        True,
            "no_leverage_mutation":                  True,
            "no_transfer":                           True,
            "no_webhook_trigger":                    True,
            "no_discord_trigger":                    True,
            "no_notion_trigger":                     True,
            "no_cron_scheduler_or_background_loop":  True,
        }
        stages[STAGE_7_FORBIDDEN_EXECUTION_SURFACE_REVIEW] = {
            "stage":   STAGE_7_FORBIDDEN_EXECUTION_SURFACE_REVIEW,
            "summary": "Forbidden execution surface review (no sender / private client / signed request / network / automation).",
            "forbidden_execution_surface_review":    forbidden_execution_surface_review,
        }
        blocked.append(GATE_NO_REAL_SENDER)
        blocked.append(GATE_NO_BYBIT_PRIVATE_CLIENT)
        blocked.append(GATE_NO_SIGNED_REQUEST)
        blocked.append(GATE_NO_ENV_SECRET_LOAD)
        blocked.append(GATE_NO_ORDER_ENDPOINT_SURFACE)
        blocked.append(GATE_NO_TRADING_STOP_ENDPOINT_SURFACE)
        blocked.append(GATE_NO_CLOSE_ONLY_FALLBACK)
        blocked.append(GATE_NO_EMERGENCY_CLOSE_FALLBACK)
        blocked.append(GATE_NO_SOCKET)
        blocked.append(GATE_NO_HTTP_PRIMITIVES)
        blocked.append(GATE_NO_BATCH_ORDER)
        blocked.append(GATE_NO_LEVERAGE_MUTATION)
        blocked.append(GATE_NO_TRANSFER)
        blocked.append(GATE_NO_WEBHOOK_TRIGGER)
        blocked.append(GATE_NO_DISCORD_TRIGGER)
        blocked.append(GATE_NO_NOTION_TRIGGER)
        blocked.append(GATE_NO_CRON_OR_SCHEDULER)

        # ===============================================================
        # stage_8_failure_and_abort_manual_gate
        # ===============================================================
        failure_and_abort_manual_gate: dict[str, Any] = {
            "missing_artifact":                      "FAIL_CLOSED",
            "stale_readonly":                        "FAIL_CLOSED",
            "final_review_stale":                    "FAIL_CLOSED",
            "approval_phrase_mismatch":              "FAIL_CLOSED",
            "token_mismatch":                        "FAIL_CLOSED",
            "token_reused":                          "FAIL_CLOSED",
            "required_input_missing":                "FAIL_CLOSED",
            "solusdt_already_exists":                "FAIL_CLOSED",
            "protected_position_mismatch":           "MANUAL_REVIEW_REQUIRED",
            "notional_cap_exceeded":                 "FAIL_CLOSED",
            "qty_mismatch":                          "FAIL_CLOSED",
            "side_mismatch":                         "FAIL_CLOSED",
            "reduce_only_mismatch":                  "FAIL_CLOSED",
            "live_endpoint_detected":                "FAIL_CLOSED",
            "secret_emission_detected":              "FAIL_CLOSED",
            "network_primitive_detected":            "FAIL_CLOSED",
            "sender_adapter_detected":               "FAIL_CLOSED",
            "any_g20_lift_attempt":                  "FAIL_CLOSED",
            "any_auto_execution_attempt":            "FAIL_CLOSED",
            "manual_intervention_only":              True,
        }
        stages[STAGE_8_FAILURE_AND_ABORT_MANUAL_GATE] = {
            "stage":   STAGE_8_FAILURE_AND_ABORT_MANUAL_GATE,
            "summary": "Failure / abort manual gate (FAIL_CLOSED / MANUAL_REVIEW_REQUIRED only; no auto-progression).",
            "failure_and_abort_manual_gate":         failure_and_abort_manual_gate,
        }
        blocked.append(GATE_MISSING_ARTIFACT_FAIL_CLOSED)
        blocked.append(GATE_STALE_READONLY_FAIL_CLOSED)
        blocked.append(GATE_FINAL_REVIEW_STALE_FAIL_CLOSED)
        blocked.append(GATE_APPROVAL_PHRASE_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_TOKEN_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_TOKEN_REUSED_FAIL_CLOSED)
        blocked.append(GATE_REQUIRED_INPUT_MISSING_FAIL_CLOSED)
        blocked.append(GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW_FAIL)
        blocked.append(GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED)
        blocked.append(GATE_QTY_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_SIDE_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_SECRET_EMISSION_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_NETWORK_PRIMITIVE_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_SENDER_ADAPTER_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_ANY_G20_LIFT_ATTEMPT_FAIL_CLOSED)
        blocked.append(GATE_ANY_AUTO_EXECUTION_ATTEMPT_FAIL_CLOSED)

        # ===============================================================
        # stage_9_documentation_sync_review
        # ===============================================================
        documentation_sync_review: dict[str, Any] = {
            "readme_status_board_sync_required":     True,
            "next_action_sync_required":             True,
            "command_log_sync_required":             True,
            "forbidden_status_sync_required":        True,
            "next_required_task_sync_required":      True,
            "readme_path_ref":                       "README.md",
            "next_action_path_ref":                  "docs/research/commands/NEXT_ACTION.md",
            "command_log_path_ref":                  "docs/research/commands/COMMAND_LOG.md",
            "next_required_task":                    "TASK-014AN_guarded_entry_real_execution_adapter_design",
            "documentation_only_plan":               True,
            "markdown_read_in_this_module":          False,
        }
        stages[STAGE_9_DOCUMENTATION_SYNC_REVIEW] = {
            "stage":   STAGE_9_DOCUMENTATION_SYNC_REVIEW,
            "summary": "Documentation sync plan (README / NEXT_ACTION / COMMAND_LOG / forbidden status / next_required_task).",
            "documentation_sync_review":             documentation_sync_review,
        }
        blocked.append(GATE_README_SYNC_REQUIRED)
        blocked.append(GATE_NEXT_ACTION_SYNC_REQUIRED)
        blocked.append(GATE_COMMAND_LOG_SYNC_REQUIRED)
        blocked.append(GATE_FORBIDDEN_STATUS_SYNC_REQUIRED)
        blocked.append(GATE_NEXT_REQUIRED_TASK_SYNC_REQUIRED)

        # ===============================================================
        # stage_10_final_manual_approval_gate_verdict
        # ===============================================================
        blocked.append(GATE_REAL_ENTRY_EXECUTION_NOT_IMPL)
        blocked.append(GATE_NO_REAL_ORDER_ENDPOINT)
        blocked.append(GATE_NO_REAL_STOP_ENDPOINT)
        blocked.append(GATE_NO_POSITION_MODIFIED)
        blocked.append(GATE_G20_NOT_LIFTED)
        blocked.append(GATE_G20_POLICY_STILL_IN_PLACE)
        blocked.append(GATE_NO_LIVE_ENDPOINT)
        blocked.append(GATE_NO_SECRETS_EMITTED)

        unique = self._dedupe(blocked)
        hard_fail = any(g in unique for g in _HARD_FAIL_GATES)

        if hard_fail:
            failed_stage = self._first_failed_stage(unique)
            status_out = STATUS_FAIL_CLOSED
            mode_out   = MODE_FAIL_CLOSED
        elif allow_real_entry_execution:
            failed_stage = ""
            status_out = STATUS_REAL_ENTRY_NOT_IMPL
            mode_out   = MODE_REAL_ENTRY_EXEC_GUARD
        elif allow_approval_gate:
            failed_stage = ""
            status_out = STATUS_GATE_READY_EXEC_DISABLED
            mode_out   = MODE_GATE_APPROVAL
        else:
            failed_stage = ""
            status_out = STATUS_GATE_READY
            mode_out   = MODE_GATE_CHECKLIST

        final_manual_approval_gate_verdict: dict[str, Any] = {
            "approval_gate_allowed":                 allow_approval_gate,
            "real_entry_execution_requested":        bool(allow_real_entry_execution),
            "real_execution_allowed":                False,
            "real_entry_implemented":                False,
            "guarded_entry_real_execution_manual_approval_gate": True,
            "manual_approval_gate_only":             True,
            "approval_grants_execution":             False,
            "token_validation_simulated":            True,
            "token_validated":                       False,
            "real_token_validated":                  False,
            "exact_phrase_validated":                False,
            "approval_inputs_validated":             False,
            "entry_execution_included":              False,
            "stop_execution_included":               False,
            "cleanup_execution_included":            False,
            "full_lifecycle_execution_included":     False,
            "current_task_real_execution_allowed":   False,
            "readiness_conclusion":                  READINESS_CONCLUSION_NOT_EXECUTABLE,
            "dry_run_authorization_result":          DRY_RUN_AUTHORIZATION_RESULT,
            "g20_policy_still_in_place":             True,
            "g20_lifted":                            False,
            "no_real_order_endpoint":                True,
            "no_real_stop_endpoint":                 True,
            "no_position_modified":                  True,
            "no_live_endpoint":                      True,
            "no_secrets_loaded":                     True,
            "no_secrets_emitted":                    True,
            "send_allowed":                          False,
            "order_endpoint_called":                 False,
            "stop_endpoint_called":                  False,
            "status":                                status_out,
            "mode":                                  mode_out,
            "next_required_task":                    "TASK-014AN_guarded_entry_real_execution_adapter_design",
        }

        audit_artifacts: dict[str, Any] = {
            "manual_approval_gate_scope":            dict(manual_approval_gate_scope),
            "manual_approval_token_gate":            dict(manual_approval_token_gate),
            "required_manual_approval_inputs":       dict(required_manual_approval_inputs),
            "approval_gate_readiness_review":        dict(approval_gate_readiness_review),
            "entry_payload_approval_preview":        dict(entry_payload_approval_preview),
            "stop_cleanup_manual_gate_review":       dict(stop_cleanup_manual_gate_review),
            "forbidden_execution_surface_review":    dict(forbidden_execution_surface_review),
            "failure_and_abort_manual_gate":         dict(failure_and_abort_manual_gate),
            "documentation_sync_review":             dict(documentation_sync_review),
            "final_manual_approval_gate_verdict":    dict(final_manual_approval_gate_verdict),
            "response_status":                       "APPROVAL_GATE_NOT_SENT",
            "response_from_exchange":                False,
            "sanitized":                             True,
            "no_secrets":                            True,
            "forbidden_log_fields":                  list(FORBIDDEN_LOG_FIELDS),
        }

        stages[STAGE_10_FINAL_MANUAL_APPROVAL_GATE_VERDICT] = {
            "stage":   STAGE_10_FINAL_MANUAL_APPROVAL_GATE_VERDICT,
            "summary": "Final manual approval gate verdict + permanent execution guard.",
            "final_manual_approval_gate_verdict":    final_manual_approval_gate_verdict,
        }

        return TinyGuardedEntryRealExecutionManualApprovalGateResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            manual_approval_gate_scope=manual_approval_gate_scope,
            manual_approval_token_gate=manual_approval_token_gate,
            required_manual_approval_inputs=required_manual_approval_inputs,
            approval_gate_readiness_review=approval_gate_readiness_review,
            entry_payload_approval_preview=entry_payload_approval_preview,
            stop_cleanup_manual_gate_review=stop_cleanup_manual_gate_review,
            forbidden_execution_surface_review=forbidden_execution_surface_review,
            failure_and_abort_manual_gate=failure_and_abort_manual_gate,
            documentation_sync_review=documentation_sync_review,
            audit_artifacts=audit_artifacts,
            final_manual_approval_gate_verdict=final_manual_approval_gate_verdict,
            approval_gate_allowed=allow_approval_gate,
            real_entry_execution_requested=bool(allow_real_entry_execution),
            real_execution_allowed=False,
            real_entry_implemented=False,
            guarded_entry_real_execution_manual_approval_gate=True,
            manual_approval_gate_only=True,
            approval_grants_execution=False,
            token_validation_simulated=True,
            token_validated=False,
            real_token_validated=False,
            exact_phrase_validated=False,
            approval_inputs_validated=False,
            entry_execution_included=False,
            stop_execution_included=False,
            cleanup_execution_included=False,
            full_lifecycle_execution_included=False,
            current_task_real_execution_allowed=False,
            readiness_conclusion=READINESS_CONCLUSION_NOT_EXECUTABLE,
            dry_run_authorization_result=DRY_RUN_AUTHORIZATION_RESULT,
            send_allowed=False,
            order_endpoint_called=False,
            stop_endpoint_called=False,
            no_position_modified=True,
            no_live_endpoint=True,
            no_orders_sent=True,
            no_batch_order=True,
            no_close_only_path=True,
            emergency_close_invoked=False,
            leverage_mutated=False,
            transfer_invoked=False,
            no_secrets_loaded=True,
            secret_value_observed=False,
            g20_policy_still_in_place=True,
            g20_lifted=False,
            expected_commit_hash=_safe_str(expected_commit_hash),
            current_commit_hash=_safe_str(current_commit_hash),
            existing_positions_touched=[],
            upstream_lifecycle_summary_status=summary_status,
            upstream_runner_design_status=runner_design_status,
            upstream_runner_dry_run_status=runner_dry_run_status,
            upstream_guarded_design_review_status=guarded_review_status,
            upstream_guarded_entry_adapter_status=guarded_entry_status,
            upstream_guarded_stop_adapter_status=guarded_stop_status,
            upstream_guarded_cleanup_adapter_status=guarded_cleanup_status,
            upstream_guarded_lifecycle_summary_status=guarded_lifecycle_status,
            upstream_entry_real_permission_review_status=entry_perm_review_status,
            upstream_entry_manual_auth_design_status=entry_auth_design_status,
            upstream_entry_manual_auth_dry_run_status=entry_auth_dry_run_status,
            upstream_entry_final_pre_execution_review_status=entry_final_review_status,
            upstream_entry_final_pre_execution_review_readiness_conclusion=entry_final_review_readiness,
            upstream_entry_final_pre_execution_review_authorization_result=entry_final_review_result,
            blocked_gates=unique,
            failed_stage=failed_stage,
            status=status_out,
        )

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for g in items:
            if g not in seen:
                out.append(g)
                seen.add(g)
        return out

    @staticmethod
    def _first_failed_stage(blocked: list[str]) -> str:
        stage_0_set = {
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
            GATE_ENTRY_MANUAL_AUTH_DESIGN_MISSING,
            GATE_ENTRY_MANUAL_AUTH_DRY_RUN_MISSING,
            GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING,
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUS_UNACCEPTABLE,
            GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READINESS_EXECUTABLE,
            GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_RESULT_NOT_DOCUMENTED_ONLY,
            GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
            GATE_SOLUSDT_EXISTS_FAIL_CLOSED,
        }
        for g in blocked:
            if g in stage_0_set:
                return STAGE_0_ARTIFACT_PREFLIGHT
        return ""


__all__ = [
    "EXISTING_POSITION_SYMBOLS",
    "EXISTING_POSITION_SYMBOLS_DOC_ORDER",
    "DEFAULT_SELECTED_SYMBOL",
    "ORDER_CREATE_PATH_REF",
    "TRADING_STOP_PATH_REF",
    "BASE_URL_DEMO_REF",
    "BASE_URL_LIVE_REF",
    "DEMO_ENDPOINT_ALLOWLIST",
    "LIVE_ENDPOINT_DENYLIST",
    "EXACT_APPROVAL_PHRASE",
    "ENTRY_TOKEN_PATTERN",
    "SAMPLE_TOKEN",
    "ORDER_LINK_ID_PREFIX",
    "REQUIRED_MANUAL_APPROVAL_INPUTS",
    "REQUIRED_CONFIRM_FLAGS",
    "ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES",
    "ACCEPTABLE_RUNNER_DESIGN_STATUSES",
    "ACCEPTABLE_RUNNER_DRY_RUN_STATUSES",
    "ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES",
    "ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES",
    "ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES",
    "ACCEPTABLE_GUARDED_CLEANUP_ADAPTER_STATUSES",
    "ACCEPTABLE_GUARDED_LIFECYCLE_SUMMARY_STATUSES",
    "ACCEPTABLE_ENTRY_REAL_PERMISSION_REVIEW_STATUSES",
    "ACCEPTABLE_ENTRY_MANUAL_AUTH_DESIGN_STATUSES",
    "ACCEPTABLE_ENTRY_MANUAL_AUTH_DRY_RUN_STATUSES",
    "ACCEPTABLE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUSES",
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_LIFECYCLE_STATUS",
    "EXPECTED_INSTRUMENT_CATEGORY",
    "GATE_EXPECTED_SYMBOL",
    "GATE_EXPECTED_CATEGORY",
    "GATE_EXPECTED_ENTRY_SIDE",
    "GATE_EXPECTED_QTY",
    "GATE_EXPECTED_QTY_STEP",
    "GATE_EXPECTED_MIN_ORDER_QTY",
    "GATE_EXPECTED_TICK_SIZE",
    "GATE_EXPECTED_MAX_NOTIONAL_USDT",
    "GATE_EXPECTED_ENTRY_REFERENCE",
    "GATE_EXPECTED_ESTIMATED_NOTIONAL",
    "GATE_EXPECTED_POSITION_IDX",
    "GATE_EXPECTED_REDUCE_ONLY",
    "GATE_EXPECTED_CLOSE_ON_TRIGGER",
    "GATE_EXPECTED_ORDER_TYPE",
    "GATE_EXPECTED_STOP_LOSS",
    "GATE_EXPECTED_TPSL_MODE",
    "GATE_EXPECTED_SL_TRIGGER_BY",
    "GATE_EXPECTED_EXISTING_COUNT",
    "FORBIDDEN_LOG_FIELDS",
    "READINESS_CONCLUSION_NOT_EXECUTABLE",
    "DRY_RUN_AUTHORIZATION_RESULT",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_MANUAL_APPROVAL_GATE_SCOPE",
    "STAGE_2_MANUAL_APPROVAL_TOKEN_GATE",
    "STAGE_3_REQUIRED_MANUAL_APPROVAL_INPUTS",
    "STAGE_4_APPROVAL_GATE_READINESS_REVIEW",
    "STAGE_5_ENTRY_PAYLOAD_APPROVAL_PREVIEW",
    "STAGE_6_STOP_CLEANUP_MANUAL_GATE_REVIEW",
    "STAGE_7_FORBIDDEN_EXECUTION_SURFACE_REVIEW",
    "STAGE_8_FAILURE_AND_ABORT_MANUAL_GATE",
    "STAGE_9_DOCUMENTATION_SYNC_REVIEW",
    "STAGE_10_FINAL_MANUAL_APPROVAL_GATE_VERDICT",
    "ALL_STAGES",
    "STATUS_GATE_READY",
    "STATUS_GATE_READY_EXEC_DISABLED",
    "STATUS_REAL_ENTRY_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_GATE_CHECKLIST",
    "MODE_GATE_APPROVAL",
    "MODE_REAL_ENTRY_EXEC_GUARD",
    "MODE_FAIL_CLOSED",
    # general (33)
    "GATE_READONLY_SMOKE_MISSING",
    "GATE_RECONCILIATION_MISSING",
    "GATE_PROTECTION_MISSING",
    "GATE_CONTRACT_MISSING",
    "GATE_NOOP_PLAN_MISSING",
    "GATE_LIFECYCLE_MOCK_MISSING",
    "GATE_REAL_PERMISSION_GATE_MISSING",
    "GATE_TINY_ENTRY_PERMISSION_GATE_MISSING",
    "GATE_TINY_STOP_PERMISSION_GATE_MISSING",
    "GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING",
    "GATE_LIFECYCLE_SUMMARY_MISSING",
    "GATE_RUNNER_DESIGN_MISSING",
    "GATE_RUNNER_DRY_RUN_MISSING",
    "GATE_GUARDED_DESIGN_REVIEW_MISSING",
    "GATE_GUARDED_ENTRY_ADAPTER_MISSING",
    "GATE_GUARDED_STOP_ADAPTER_MISSING",
    "GATE_GUARDED_CLEANUP_ADAPTER_MISSING",
    "GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING",
    "GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING",
    "GATE_ENTRY_MANUAL_AUTH_DESIGN_MISSING",
    "GATE_ENTRY_MANUAL_AUTH_DRY_RUN_MISSING",
    "GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING",
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_NOT_SOLUSDT",
    "GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUS_UNACCEPTABLE",
    "GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READINESS_EXECUTABLE",
    "GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_RESULT_NOT_DOCUMENTED_ONLY",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # scope (16)
    "GATE_MANUAL_APPROVAL_GATE_ONLY",
    "GATE_APPROVAL_GATE_DOES_NOT_EXECUTE",
    "GATE_ENTRY_EXECUTION_NOT_INCLUDED",
    "GATE_STOP_EXECUTION_NOT_INCLUDED",
    "GATE_CLEANUP_EXECUTION_NOT_INCLUDED",
    "GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED",
    "GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE",
    "GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE",
    "GATE_APPROVAL_DOES_NOT_GRANT_EXECUTION_SCOPE",
    "GATE_SEND_NOT_ALLOWED_SCOPE",
    "GATE_ORDER_ENDPOINT_NOT_CALLED",
    "GATE_STOP_ENDPOINT_NOT_CALLED",
    "GATE_NO_ENDPOINT_INVOKED",
    "GATE_NO_POSITION_MODIFIED_SCOPE",
    "GATE_NO_SECRETS_LOADED",
    "GATE_NO_G20_LIFT",
    # token (14)
    "GATE_TOKEN_PATTERN_DOCUMENTED",
    "GATE_SAMPLE_TOKEN_DOCUMENTED",
    "GATE_TOKEN_NOT_VALIDATED",
    "GATE_REAL_TOKEN_NOT_VALIDATED",
    "GATE_TOKEN_FORMAT_NOT_AUTHORIZATION",
    "GATE_TOKEN_DOES_NOT_GRANT_EXECUTION",
    "GATE_TOKEN_REQUIRES_FUTURE_TASK_REVALIDATION",
    "GATE_TOKEN_SINGLE_USE_DOCUMENTED",
    "GATE_TOKEN_INCLUDES_DATE",
    "GATE_TOKEN_INCLUDES_SYMBOL",
    "GATE_TOKEN_REUSE_FORBIDDEN",
    "GATE_TOKEN_EXPIRY_DOCUMENTED",
    "GATE_TOKEN_CONTAINS_NO_SECRET",
    "GATE_TOKEN_NOT_LOGGED_AS_SECRET",
    # manual approval inputs (19)
    "GATE_EXACT_APPROVAL_PHRASE_DOCUMENTED",
    "GATE_EXACT_PHRASE_NOT_VALIDATED",
    "GATE_APPROVAL_INPUTS_DOCUMENTED",
    "GATE_APPROVAL_INPUTS_NOT_VALIDATED",
    "GATE_APPROVAL_INPUTS_DO_NOT_AUTHORIZE_EXECUTION",
    "GATE_RICK_EXPLICIT_AUTHORIZATION_REQUIRED",
    "GATE_SECOND_CONFIRMATION_REQUIRED",
    "GATE_INDEPENDENT_REVIEWER_RECOMMENDED",
    "GATE_CONFIRM_SYMBOL_FLAG",
    "GATE_CONFIRM_SIDE_FLAG",
    "GATE_CONFIRM_QTY_FLAG",
    "GATE_CONFIRM_MAX_NOTIONAL_FLAG",
    "GATE_CONFIRM_REDUCE_ONLY_FLAG",
    "GATE_CONFIRM_POSITION_IDX_FLAG",
    "GATE_CONFIRM_ORDER_TYPE_FLAG",
    "GATE_CONFIRM_EXISTING_SYMBOLS_FLAG",
    "GATE_CONFIRM_STOP_REQUIRED_FLAG",
    "GATE_CONFIRM_CLEANUP_BOUNDARY_FLAG",
    "GATE_CONFIRM_NO_ORDER_WILL_BE_SENT_FLAG",
    # readiness (17)
    "GATE_FINAL_PRE_EXECUTION_REVIEW_READY",
    "GATE_AK_DRY_RUN_READY",
    "GATE_AJ_DESIGN_READY",
    "GATE_AI_PERMISSION_REVIEW_READY",
    "GATE_SOLUSDT_ABSENT_BEFORE_ENTRY",
    "GATE_PROTECTED_EXPECTED_SYMBOLS_DOCUMENTED",
    "GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW",
    "GATE_ESTIMATED_NOTIONAL_WITHIN_CAP",
    "GATE_ENTRY_PARAMS_STABLE",
    "GATE_STOP_BOUNDARY_STABLE",
    "GATE_CLEANUP_BOUNDARY_STABLE",
    "GATE_NO_AUTOMATION_TRIGGERS",
    "GATE_NO_SENDER_ADAPTER_READINESS",
    "GATE_NO_ENDPOINT_PERMISSIONS",
    "GATE_G20_STILL_ACTIVE",
    "GATE_READINESS_REVIEW_ONLY",
    "GATE_READINESS_DOES_NOT_AUTHORIZE_EXECUTION",
    # payload preview (19)
    "GATE_PAYLOAD_PREVIEW_ONLY",
    "GATE_PAYLOAD_APPROVAL_GATE_ONLY",
    "GATE_PAYLOAD_SEND_ALLOWED_FALSE",
    "GATE_PAYLOAD_ENDPOINT_CALLED_FALSE",
    "GATE_PAYLOAD_REAL_PAYLOAD_FALSE",
    "GATE_PAYLOAD_SIGNATURE_PRESENT_FALSE",
    "GATE_PAYLOAD_PRIVATE_HEADERS_EMPTY",
    "GATE_PAYLOAD_ENDPOINT_PATH_ORDER_CREATE_REF",
    "GATE_PAYLOAD_BASE_URL_DEMO_ONLY",
    "GATE_PAYLOAD_CATEGORY_LINEAR",
    "GATE_PAYLOAD_SYMBOL_SOLUSDT",
    "GATE_PAYLOAD_SIDE_BUY",
    "GATE_PAYLOAD_ORDER_TYPE_MARKET",
    "GATE_PAYLOAD_QTY_0_1",
    "GATE_PAYLOAD_REDUCE_ONLY_FALSE",
    "GATE_PAYLOAD_CLOSE_ON_TRIGGER_FALSE",
    "GATE_PAYLOAD_POSITION_IDX_ZERO",
    "GATE_PAYLOAD_ORDER_LINK_ID_PREFIX",
    "GATE_PAYLOAD_NO_SENDER_ADAPTER",
    # stop/cleanup (12)
    "GATE_STOP_ATTACH_REQUIRED_AFTER_ENTRY",
    "GATE_STOP_ATTACH_NOT_INCLUDED_IN_THIS_TASK",
    "GATE_BOUNDARY_STOP_LOSS_61_18",
    "GATE_BOUNDARY_TPSL_MODE_FULL",
    "GATE_BOUNDARY_SL_TRIGGER_BY_MARKPRICE",
    "GATE_CLEANUP_NOT_INCLUDED_IN_THIS_TASK",
    "GATE_CLEANUP_SEPARATE_MANUAL_BOUNDARY",
    "GATE_NO_AUTOMATIC_STOP_ATTACH",
    "GATE_NO_AUTOMATIC_CLEANUP",
    "GATE_NO_AUTOMATIC_EMERGENCY_CLOSE",
    "GATE_ENTRY_SUCCESS_WITHOUT_STOP_MANUAL_REVIEW",
    "GATE_FUTURE_ENTRY_REQUIRES_FOLLOW_UP_STOP_TASK",
    # forbidden execution surface (17)
    "GATE_NO_REAL_SENDER",
    "GATE_NO_BYBIT_PRIVATE_CLIENT",
    "GATE_NO_SIGNED_REQUEST",
    "GATE_NO_ENV_SECRET_LOAD",
    "GATE_NO_ORDER_ENDPOINT_SURFACE",
    "GATE_NO_TRADING_STOP_ENDPOINT_SURFACE",
    "GATE_NO_CLOSE_ONLY_FALLBACK",
    "GATE_NO_EMERGENCY_CLOSE_FALLBACK",
    "GATE_NO_SOCKET",
    "GATE_NO_HTTP_PRIMITIVES",
    "GATE_NO_BATCH_ORDER",
    "GATE_NO_LEVERAGE_MUTATION",
    "GATE_NO_TRANSFER",
    "GATE_NO_WEBHOOK_TRIGGER",
    "GATE_NO_DISCORD_TRIGGER",
    "GATE_NO_NOTION_TRIGGER",
    "GATE_NO_CRON_OR_SCHEDULER",
    # failure (19)
    "GATE_MISSING_ARTIFACT_FAIL_CLOSED",
    "GATE_STALE_READONLY_FAIL_CLOSED",
    "GATE_FINAL_REVIEW_STALE_FAIL_CLOSED",
    "GATE_APPROVAL_PHRASE_MISMATCH_FAIL_CLOSED",
    "GATE_TOKEN_MISMATCH_FAIL_CLOSED",
    "GATE_TOKEN_REUSED_FAIL_CLOSED",
    "GATE_REQUIRED_INPUT_MISSING_FAIL_CLOSED",
    "GATE_SOLUSDT_EXISTS_FAIL_CLOSED",
    "GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW_FAIL",
    "GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED",
    "GATE_QTY_MISMATCH_FAIL_CLOSED",
    "GATE_SIDE_MISMATCH_FAIL_CLOSED",
    "GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED",
    "GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED",
    "GATE_SECRET_EMISSION_DETECTED_FAIL_CLOSED",
    "GATE_NETWORK_PRIMITIVE_DETECTED_FAIL_CLOSED",
    "GATE_SENDER_ADAPTER_DETECTED_FAIL_CLOSED",
    "GATE_ANY_G20_LIFT_ATTEMPT_FAIL_CLOSED",
    "GATE_ANY_AUTO_EXECUTION_ATTEMPT_FAIL_CLOSED",
    # documentation (5)
    "GATE_README_SYNC_REQUIRED",
    "GATE_NEXT_ACTION_SYNC_REQUIRED",
    "GATE_COMMAND_LOG_SYNC_REQUIRED",
    "GATE_FORBIDDEN_STATUS_SYNC_REQUIRED",
    "GATE_NEXT_REQUIRED_TASK_SYNC_REQUIRED",
    # execution guard (5)
    "GATE_REAL_ENTRY_EXECUTION_NOT_IMPL",
    "GATE_NO_REAL_ORDER_ENDPOINT",
    "GATE_NO_REAL_STOP_ENDPOINT",
    "GATE_NO_POSITION_MODIFIED",
    "GATE_G20_NOT_LIFTED",
    # data
    "DemoTinyGuardedEntryRealExecutionManualApprovalGate",
    "TinyGuardedEntryRealExecutionManualApprovalGateResult",
]
