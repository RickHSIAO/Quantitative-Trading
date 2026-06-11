"""
src/demo_tiny_guarded_entry_manual_authorization_dry_run.py
TASK-014AK: Guarded Entry Manual Authorization Dry-run.

Manual-authorization dry-run-only module. Dry-runs the future manual
authorization workflow: simulates token-pattern matching, simulates the
required-flags checklist, simulates the pre-execution readiness check,
constructs the dry-run request template, and emits the failure /
documentation envelope. This module DOES NOT implement a real entry
sender, does not send any order, does not call /v5/order/create, does
not call /v5/position/trading-stop, does not read secrets, does not
sign anything, does not lift TASK-014L G20, does not validate any
real token, does not treat any token as authorization, and does not
touch any existing protected demo position.

Inputs: 20 upstream artifacts (the 19 from TASK-014AJ + AJ's own
        entry_manual_authorization_design output).

Stages:
  stage_0_artifact_preflight
  stage_1_manual_authorization_dry_run_scope
  stage_2_authorization_token_dry_run
  stage_3_required_flags_dry_run
  stage_4_pre_execution_readiness_dry_run
  stage_5_entry_request_template_dry_run
  stage_6_post_entry_boundary_dry_run
  stage_7_failure_and_abort_dry_run
  stage_8_documentation_sync_review
  stage_9_final_manual_authorization_dry_run_verdict

Modes:
  authorization_dry_run_checklist  --- default
  authorization_dry_run_approval   --- --allow-dry-run-approval
  real_entry_execution_guard       --- --allow-real-entry-execution
  fail_closed                      --- upstream failed

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
  * validate any real token, or treat any token as authorization
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

STAGE_0_ARTIFACT_PREFLIGHT                       = "stage_0_artifact_preflight"
STAGE_1_MANUAL_AUTHORIZATION_DRY_RUN_SCOPE       = "stage_1_manual_authorization_dry_run_scope"
STAGE_2_AUTHORIZATION_TOKEN_DRY_RUN              = "stage_2_authorization_token_dry_run"
STAGE_3_REQUIRED_FLAGS_DRY_RUN                   = "stage_3_required_flags_dry_run"
STAGE_4_PRE_EXECUTION_READINESS_DRY_RUN          = "stage_4_pre_execution_readiness_dry_run"
STAGE_5_ENTRY_REQUEST_TEMPLATE_DRY_RUN           = "stage_5_entry_request_template_dry_run"
STAGE_6_POST_ENTRY_BOUNDARY_DRY_RUN              = "stage_6_post_entry_boundary_dry_run"
STAGE_7_FAILURE_AND_ABORT_DRY_RUN                = "stage_7_failure_and_abort_dry_run"
STAGE_8_DOCUMENTATION_SYNC_REVIEW                = "stage_8_documentation_sync_review"
STAGE_9_FINAL_MANUAL_AUTHORIZATION_DRY_RUN_VERDICT = "stage_9_final_manual_authorization_dry_run_verdict"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_MANUAL_AUTHORIZATION_DRY_RUN_SCOPE,
    STAGE_2_AUTHORIZATION_TOKEN_DRY_RUN,
    STAGE_3_REQUIRED_FLAGS_DRY_RUN,
    STAGE_4_PRE_EXECUTION_READINESS_DRY_RUN,
    STAGE_5_ENTRY_REQUEST_TEMPLATE_DRY_RUN,
    STAGE_6_POST_ENTRY_BOUNDARY_DRY_RUN,
    STAGE_7_FAILURE_AND_ABORT_DRY_RUN,
    STAGE_8_DOCUMENTATION_SYNC_REVIEW,
    STAGE_9_FINAL_MANUAL_AUTHORIZATION_DRY_RUN_VERDICT,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_DRY_RUN_READY               = "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY"
STATUS_DRY_RUN_READY_EXEC_DISABLED = (
    "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_ENTRY_NOT_IMPL         = "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                 = "FAIL_CLOSED"

MODE_AUTHORIZATION_DRY_RUN_CHECKLIST = "authorization_dry_run_checklist"
MODE_AUTHORIZATION_DRY_RUN_APPROVAL  = "authorization_dry_run_approval"
MODE_REAL_ENTRY_EXECUTION_GUARD      = "real_entry_execution_guard"
MODE_FAIL_CLOSED                     = "fail_closed"

READINESS_CONCLUSION_NOT_EXECUTABLE  = "DESIGN_REVIEW_READY_NOT_EXECUTABLE"
DRY_RUN_AUTHORIZATION_RESULT         = "DOCUMENTED_ONLY_NOT_AUTHORIZED"


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


# ---------------------------------------------------------------------------
# Token patterns / sample token (sample is NEVER treated as authorization)
# ---------------------------------------------------------------------------

ENTRY_TOKEN_PATTERN = "CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT"
SAMPLE_TOKEN        = "CONFIRM_DEMO_TINY_ENTRY_20260611_SOLUSDT"

REQUIRED_HUMAN_CONFIRMATION_FLAGS: tuple[str, ...] = (
    "--i-understand-this-is-demo-real-execution",
    "--confirm-symbol SOLUSDT",
    "--confirm-side Buy",
    "--confirm-qty 0.1",
    "--confirm-max-notional-usdt 10",
    "--confirm-existing-position-count 5",
    "--confirm-existing-symbols AIXBTUSDT,ENAUSDT,TIAUSDT,POLYXUSDT,EDUUSDT",
    "--confirm-reduce-only false",
    "--confirm-position-idx 0",
    "--confirm-order-type Market",
    "--confirm-stop-required-after-entry true",
    "--confirm-stop-loss 61.18",
    "--confirm-cleanup-manual-boundary true",
)

ENTRY_DRY_RUN_ORDER_LINK_ID_PREFIXES: tuple[str, ...] = (
    "DRYRUN_MANUAL_AUTH_TINY_ENTRY_",
)


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
# Entry dry-run expected values (documentation only)
# ---------------------------------------------------------------------------

DRY_RUN_EXPECTED_SYMBOL              = "SOLUSDT"
DRY_RUN_EXPECTED_CATEGORY            = "linear"
DRY_RUN_EXPECTED_ENTRY_SIDE          = "Buy"
DRY_RUN_EXPECTED_QTY                 = 0.1
DRY_RUN_EXPECTED_QTY_STEP            = 0.1
DRY_RUN_EXPECTED_MIN_ORDER_QTY       = 0.1
DRY_RUN_EXPECTED_TICK_SIZE           = 0.01
DRY_RUN_EXPECTED_MAX_NOTIONAL_USDT   = 10.0
DRY_RUN_EXPECTED_ENTRY_REFERENCE     = 64.4
DRY_RUN_EXPECTED_ESTIMATED_NOTIONAL  = 6.44   # qty * entry_reference
DRY_RUN_EXPECTED_POSITION_IDX        = 0
DRY_RUN_EXPECTED_REDUCE_ONLY         = False
DRY_RUN_EXPECTED_CLOSE_ON_TRIGGER    = False
DRY_RUN_EXPECTED_ORDER_TYPE          = "Market"
DRY_RUN_EXPECTED_STOP_LOSS           = 61.18
DRY_RUN_EXPECTED_TPSL_MODE           = "Full"
DRY_RUN_EXPECTED_SL_TRIGGER_BY       = "MarkPrice"
DRY_RUN_EXPECTED_EXISTING_COUNT      = 5

FORBIDDEN_LOG_FIELDS: tuple[str, ...] = (
    "api_key_value", "api_secret_value", "signature_value",
    "auth_header_value", "sign_header_value", "bearer_token_value",
)


# ---------------------------------------------------------------------------
# Gate constants
# General (30) + Scope (15) + Token dry-run (12) + Flags dry-run (20)
# + Pre-execution readiness (18) + Entry request template (18)
# + Boundary dry-run (11) + Failure dry-run (22) + Documentation (5)
# + Execution guard (5) = 156
# ---------------------------------------------------------------------------

# General gates (30)
GATE_READONLY_SMOKE_MISSING                     = "readonly_smoke_missing"
GATE_RECONCILIATION_MISSING                     = "reconciliation_missing"
GATE_PROTECTION_MISSING                         = "protection_missing"
GATE_CONTRACT_MISSING                           = "contract_missing"
GATE_NOOP_PLAN_MISSING                          = "noop_plan_missing"
GATE_LIFECYCLE_MOCK_MISSING                     = "lifecycle_mock_missing"
GATE_REAL_PERMISSION_GATE_MISSING               = "real_permission_gate_missing"
GATE_TINY_ENTRY_PERMISSION_GATE_MISSING         = "tiny_entry_permission_gate_missing"
GATE_TINY_STOP_PERMISSION_GATE_MISSING          = "tiny_stop_permission_gate_missing"
GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING       = "tiny_cleanup_permission_gate_missing"
GATE_LIFECYCLE_SUMMARY_MISSING                  = "lifecycle_summary_missing"
GATE_RUNNER_DESIGN_MISSING                      = "runner_design_missing"
GATE_RUNNER_DRY_RUN_MISSING                     = "runner_dry_run_missing"
GATE_GUARDED_DESIGN_REVIEW_MISSING              = "guarded_design_review_missing"
GATE_GUARDED_ENTRY_ADAPTER_MISSING              = "guarded_entry_adapter_missing"
GATE_GUARDED_STOP_ADAPTER_MISSING               = "guarded_stop_adapter_missing"
GATE_GUARDED_CLEANUP_ADAPTER_MISSING            = "guarded_cleanup_adapter_missing"
GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING          = "guarded_lifecycle_summary_missing"
GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING       = "entry_real_permission_review_missing"
GATE_ENTRY_MANUAL_AUTH_DESIGN_MISSING           = "entry_manual_authorization_design_missing"
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO             = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                      = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG                  = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY  = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_NOT_SOLUSDT                = "selected_symbol_not_solusdt"
GATE_ENTRY_MANUAL_AUTH_DESIGN_STATUS_UNACCEPTABLE = "entry_manual_authorization_design_status_unacceptable"
GATE_ENTRY_MANUAL_AUTH_DESIGN_READINESS_EXECUTABLE = "entry_manual_authorization_design_readiness_executable"
GATE_G20_POLICY_STILL_IN_PLACE                  = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                           = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                         = "no_secret_values_emitted_in_this_task"

# Scope gates (15)
GATE_GUARDED_ENTRY_MANUAL_AUTH_DRY_RUN_ONLY     = "guarded_entry_manual_authorization_dry_run_only"
GATE_AUTHORIZATION_DRY_RUN_ONLY                 = "authorization_dry_run_only"
GATE_TOKEN_VALIDATION_SIMULATED                 = "token_validation_simulated"
GATE_TOKEN_NOT_VALIDATED_SCOPE                  = "token_not_validated_scope"
GATE_REAL_TOKEN_NOT_VALIDATED_SCOPE             = "real_token_not_validated_scope"
GATE_ENTRY_EXECUTION_NOT_INCLUDED               = "entry_execution_not_included"
GATE_STOP_EXECUTION_NOT_INCLUDED                = "stop_execution_not_included"
GATE_CLEANUP_EXECUTION_NOT_INCLUDED             = "cleanup_execution_not_included"
GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED      = "full_lifecycle_execution_not_included"
GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE           = "real_entry_not_implemented_scope"
GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE           = "real_execution_not_allowed_scope"
GATE_NO_ENDPOINT_INVOKED                        = "no_endpoint_invoked_in_this_task"
GATE_NO_POSITION_MODIFIED_SCOPE                 = "no_position_modified_scope"
GATE_NO_SECRETS_LOADED                          = "no_secrets_loaded_in_this_task"
GATE_NO_G20_LIFT                                = "no_g20_policy_lift_in_this_task"

# Token dry-run gates (12)
GATE_TOKEN_PATTERN_PRESENT                      = "token_pattern_present"
GATE_SAMPLE_TOKEN_PRESENT                       = "sample_token_present"
GATE_SAMPLE_TOKEN_MATCHES_PATTERN_SIMULATED     = "sample_token_matches_pattern_simulated"
GATE_TOKEN_NOT_VALIDATED                        = "token_not_validated_in_this_task"
GATE_REAL_TOKEN_NOT_VALIDATED                   = "real_token_not_validated_in_this_task"
GATE_TOKEN_FORMAT_NOT_AUTHORIZATION             = "token_format_not_authorization"
GATE_TOKEN_SINGLE_USE_DOCUMENTED                = "token_single_use_documented"
GATE_TOKEN_REUSE_FORBIDDEN                      = "token_reuse_forbidden_documented"
GATE_TOKEN_EXPIRY_DOCUMENTED                    = "token_expiry_documented_only"
GATE_TOKEN_NOT_LOGGED_AS_SECRET                 = "token_not_logged_as_secret"
GATE_TOKEN_NO_SECRET                            = "token_contains_no_secret"
GATE_SAMPLE_TOKEN_NOT_AUTHORIZATION             = "sample_token_not_treated_as_authorization"

# Flags dry-run gates (20)
GATE_REQUIRED_FLAGS_PRESENT_SIMULATED           = "required_flags_present_simulated"
GATE_REQUIRED_FLAG_COUNT_13                     = "required_flag_count_13"
GATE_FLAGS_NOT_VALIDATED                        = "flags_not_validated_in_this_task"
GATE_SECOND_CONFIRMATION_REQUIRED               = "second_confirmation_required"
GATE_MANUAL_BOUNDARY_REQUIRED                   = "manual_boundary_required"
GATE_RICK_EXPLICIT_AUTHORIZATION_REQUIRED       = "rick_explicit_authorization_required"
GATE_INDEPENDENT_REVIEWER_RECOMMENDED           = "independent_reviewer_recommended"
GATE_DRY_RUN_AUTHORIZATION_RESULT_DOCUMENTED    = "dry_run_authorization_result_documented_only_not_authorized"
GATE_CONFIRM_SYMBOL_FLAG                        = "confirm_symbol_flag_documented"
GATE_CONFIRM_SIDE_FLAG                          = "confirm_side_flag_documented"
GATE_CONFIRM_QTY_FLAG                           = "confirm_qty_flag_documented"
GATE_CONFIRM_MAX_NOTIONAL_FLAG                  = "confirm_max_notional_flag_documented"
GATE_CONFIRM_EXISTING_COUNT_FLAG                = "confirm_existing_count_flag_documented"
GATE_CONFIRM_EXISTING_SYMBOLS_FLAG              = "confirm_existing_symbols_flag_documented"
GATE_CONFIRM_REDUCE_ONLY_FALSE_FLAG             = "confirm_reduce_only_false_flag_documented"
GATE_CONFIRM_POSITION_IDX_FLAG                  = "confirm_position_idx_flag_documented"
GATE_CONFIRM_ORDER_TYPE_FLAG                    = "confirm_order_type_flag_documented"
GATE_CONFIRM_STOP_REQUIRED_FLAG                 = "confirm_stop_required_flag_documented"
GATE_CONFIRM_STOP_LOSS_FLAG                     = "confirm_stop_loss_flag_documented"
GATE_CONFIRM_CLEANUP_MANUAL_BOUNDARY_FLAG       = "confirm_cleanup_manual_boundary_flag_documented"

# Pre-execution readiness dry-run gates (18)
GATE_GIT_COMMIT_HASH_MUST_MATCH                 = "git_commit_hash_must_match_expected"
GATE_README_CURRENT                             = "readme_current"
GATE_NEXT_ACTION_CURRENT                        = "next_action_current"
GATE_COMMAND_LOG_CURRENT                        = "command_log_current"
GATE_LATEST_READONLY_TIMESTAMP_RECENT           = "latest_readonly_timestamp_recent"
GATE_PROTECTED_POSITIONS_UNCHANGED              = "protected_positions_unchanged"
GATE_SOLUSDT_ABSENT_BEFORE_ENTRY                = "solusdt_absent_before_entry"
GATE_ESTIMATED_NOTIONAL_WITHIN_CAP              = "estimated_notional_within_cap"
GATE_PRE_QTY_0_1                                = "pre_execution_qty_0_1"
GATE_PRE_SIDE_BUY                               = "pre_execution_side_buy"
GATE_PRE_REDUCE_ONLY_FALSE                      = "pre_execution_reduce_only_false"
GATE_STOP_ATTACH_PLAN_READY                     = "stop_attach_plan_ready"
GATE_CLEANUP_PLAN_READY                         = "cleanup_plan_ready"
GATE_NO_DISCORD_TRIGGER                         = "no_discord_trigger"
GATE_NO_NOTION_TRIGGER                          = "no_notion_trigger"
GATE_NO_CRON_OR_BACKGROUND_AUTOMATION           = "no_cron_or_background_automation"
GATE_READINESS_CHECK_SIMULATED                  = "readiness_check_simulated"
GATE_READINESS_NOT_VALIDATED_FOR_REAL_EXECUTION = "readiness_not_validated_for_real_execution"

# Entry request template dry-run gates (18)
GATE_TEMPLATE_PRESENT                           = "entry_template_present"
GATE_TEMPLATE_PREVIEW_ONLY                      = "template_preview_only"
GATE_TEMPLATE_DRY_RUN_ONLY                      = "template_dry_run_only"
GATE_TEMPLATE_SEND_ALLOWED_FALSE                = "template_send_allowed_false"
GATE_TEMPLATE_ENDPOINT_CALLED_FALSE             = "template_endpoint_called_false"
GATE_TEMPLATE_REAL_PAYLOAD_FALSE                = "template_real_payload_false"
GATE_TEMPLATE_SIGNATURE_PRESENT_FALSE           = "template_signature_present_false"
GATE_TEMPLATE_PRIVATE_HEADERS_EMPTY             = "template_private_headers_empty"
GATE_TEMPLATE_ENDPOINT_PATH_ORDER_CREATE        = "template_endpoint_path_ref_order_create"
GATE_TEMPLATE_BASE_URL_DEMO_ONLY                = "template_base_url_demo_only"
GATE_TEMPLATE_SIDE_BUY                          = "template_side_buy"
GATE_TEMPLATE_QTY_0_1                           = "template_qty_0_1"
GATE_TEMPLATE_REDUCE_ONLY_FALSE                 = "template_reduce_only_false"
GATE_TEMPLATE_CLOSE_ON_TRIGGER_FALSE            = "template_close_on_trigger_false"
GATE_TEMPLATE_POSITION_IDX_ZERO                 = "template_position_idx_zero"
GATE_TEMPLATE_ORDER_TYPE_MARKET                 = "template_order_type_market"
GATE_TEMPLATE_ORDER_LINK_ID_PREFIX_DOCUMENTED   = "template_order_link_id_prefix_documented"
GATE_TEMPLATE_NO_SENDER_ADAPTER                 = "template_no_sender_adapter"

# Boundary dry-run gates (11)
GATE_ENTRY_SUCCESS_DOES_NOT_AUTO_ATTACH_STOP    = "entry_success_does_not_auto_attach_stop"
GATE_STOP_ATTACH_SEPARATE_MANUAL_AUTH           = "stop_attach_separate_manual_authorization"
GATE_BOUNDARY_STOP_LOSS_61_18                   = "boundary_stop_loss_61_18"
GATE_BOUNDARY_TPSL_MODE_FULL                    = "boundary_tpsl_mode_full"
GATE_BOUNDARY_SL_TRIGGER_BY_MARKPRICE           = "boundary_sl_trigger_by_markprice"
GATE_CLEANUP_SEPARATE_MANUAL_AUTH               = "cleanup_separate_manual_authorization"
GATE_NO_AUTO_CLEANUP_BOUNDARY                   = "no_automatic_cleanup_boundary"
GATE_NO_AUTO_EMERGENCY_CLOSE_BOUNDARY           = "no_automatic_emergency_close_boundary"
GATE_ENTRY_SUCCESS_WITHOUT_STOP_MANUAL_REVIEW   = "entry_success_without_stop_attach_manual_review"
GATE_STOP_ATTACH_FAIL_MANUAL_REVIEW             = "stop_attach_fail_manual_review"
GATE_CLEANUP_SEPARATE_BOUNDARY_ONLY             = "cleanup_separate_boundary_only"

# Failure dry-run gates (22)
GATE_MISSING_FLAG_FAIL_CLOSED                   = "missing_flag_fail_closed"
GATE_TOKEN_MISMATCH_FAIL_CLOSED                 = "token_mismatch_fail_closed"
GATE_TOKEN_REUSED_FAIL_CLOSED                   = "token_reused_fail_closed"
GATE_READONLY_STALE_FAIL_CLOSED                 = "readonly_stale_fail_closed"
GATE_SOLUSDT_EXISTS_FAIL_CLOSED                 = "solusdt_already_exists_fail_closed"
GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW  = "protected_position_mismatch_manual_review"
GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED          = "notional_cap_exceeded_fail_closed"
GATE_QTY_MISMATCH_FAIL_CLOSED                   = "qty_mismatch_fail_closed"
GATE_SIDE_MISMATCH_FAIL_CLOSED                  = "side_mismatch_fail_closed"
GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED           = "reduce_only_mismatch_fail_closed"
GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED         = "live_endpoint_detected_fail_closed"
GATE_SECRET_EMISSION_FAIL_CLOSED                = "secret_emission_fail_closed"
GATE_NO_AUTO_RETRY                              = "no_auto_retry"
GATE_NO_AUTO_STOP_ATTACH_FAILURE                = "no_auto_stop_attach_on_failure"
GATE_NO_AUTO_CLEANUP_FAILURE                    = "no_auto_cleanup_on_failure"
GATE_NO_AUTO_EMERGENCY_CLOSE                    = "no_auto_emergency_close"
GATE_NO_AUTO_NEXT_STEP                          = "no_auto_next_step"
GATE_NO_BACKGROUND_LOOP                         = "no_background_loop"
GATE_NO_CRON                                    = "no_cron"
GATE_NO_SCHEDULER                               = "no_scheduler"
GATE_FAILURE_NO_DISCORD_TRIGGER                 = "failure_no_discord_trigger"
GATE_FAILURE_NO_NOTION_TRIGGER                  = "failure_no_notion_trigger"

# Documentation gates (5)
GATE_README_SYNC_REQUIRED                       = "readme_status_board_sync_required"
GATE_NEXT_ACTION_SYNC_REQUIRED                  = "next_action_sync_required"
GATE_COMMAND_LOG_SYNC_REQUIRED                  = "command_log_sync_required"
GATE_FORBIDDEN_STATUS_SYNC_REQUIRED             = "forbidden_status_sync_required"
GATE_NEXT_REQUIRED_TASK_SYNC_REQUIRED           = "next_required_task_sync_required"

# Execution guard gates (5)
GATE_REAL_ENTRY_EXECUTION_NOT_IMPL              = "real_entry_execution_not_implemented"
GATE_NO_REAL_ORDER_ENDPOINT                     = "no_real_order_endpoint_in_this_task"
GATE_NO_REAL_STOP_ENDPOINT                      = "no_real_stop_endpoint_in_this_task"
GATE_NO_POSITION_MODIFIED                       = "no_position_modified_in_this_task"
GATE_G20_NOT_LIFTED                             = "g20_policy_not_lifted_by_this_task"


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
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_ENTRY_MANUAL_AUTH_DESIGN_STATUS_UNACCEPTABLE,
    GATE_ENTRY_MANUAL_AUTH_DESIGN_READINESS_EXECUTABLE,
    GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyGuardedEntryManualAuthorizationDryRunResult:
    """Read-only outcome of one guarded entry manual authorization dry-run."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    authorization_dry_run_scope:                    dict[str, Any] = field(default_factory=dict)
    authorization_token_dry_run:                    dict[str, Any] = field(default_factory=dict)
    required_flags_dry_run:                         dict[str, Any] = field(default_factory=dict)
    pre_execution_readiness_dry_run:                dict[str, Any] = field(default_factory=dict)
    entry_request_template_dry_run:                 dict[str, Any] = field(default_factory=dict)
    post_entry_boundary_dry_run:                    dict[str, Any] = field(default_factory=dict)
    failure_and_abort_dry_run:                      dict[str, Any] = field(default_factory=dict)
    documentation_sync_review:                      dict[str, Any] = field(default_factory=dict)
    audit_artifacts:                                dict[str, Any] = field(default_factory=dict)
    final_manual_authorization_dry_run_verdict:     dict[str, Any] = field(default_factory=dict)

    entry_token_pattern:          str = ENTRY_TOKEN_PATTERN
    sample_token:                 str = SAMPLE_TOKEN

    dry_run_approval_allowed:          bool = False
    real_entry_execution_requested:    bool = False
    real_execution_allowed:            bool = False
    real_entry_implemented:            bool = False
    guarded_entry_manual_authorization_dry_run: bool = True
    authorization_dry_run_only:        bool = True
    token_validation_simulated:        bool = True
    token_validated:                   bool = False
    real_token_validated:              bool = False
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
    upstream_entry_manual_auth_design_readiness_conclusion: str = ""

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = "TASK-014AL_guarded_entry_final_pre_execution_review"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                          self.timestamp_utc,
            "timestamp_utc":                      self.timestamp_utc,
            "mode":                               self.mode,
            "selected_symbol":                    self.selected_symbol,
            "existing_position_symbols":          list(self.existing_position_symbols),
            "stages":                             {k: dict(v) for k, v in self.stages.items()},
            "stage_order":                        list(self.stage_order),
            "authorization_dry_run_scope":        dict(self.authorization_dry_run_scope),
            "authorization_token_dry_run":        dict(self.authorization_token_dry_run),
            "required_flags_dry_run":             dict(self.required_flags_dry_run),
            "pre_execution_readiness_dry_run":    dict(self.pre_execution_readiness_dry_run),
            "entry_request_template_dry_run":     dict(self.entry_request_template_dry_run),
            "post_entry_boundary_dry_run":        dict(self.post_entry_boundary_dry_run),
            "failure_and_abort_dry_run":          dict(self.failure_and_abort_dry_run),
            "documentation_sync_review":          dict(self.documentation_sync_review),
            "audit_artifacts":                    dict(self.audit_artifacts),
            "final_manual_authorization_dry_run_verdict":
                dict(self.final_manual_authorization_dry_run_verdict),
            "entry_token_pattern":                self.entry_token_pattern,
            "sample_token":                       self.sample_token,
            "dry_run_approval_allowed":           self.dry_run_approval_allowed,
            "real_entry_execution_requested":     self.real_entry_execution_requested,
            "real_execution_allowed":             self.real_execution_allowed,
            "real_entry_implemented":             self.real_entry_implemented,
            "guarded_entry_manual_authorization_dry_run": self.guarded_entry_manual_authorization_dry_run,
            "authorization_dry_run_only":         self.authorization_dry_run_only,
            "token_validation_simulated":         self.token_validation_simulated,
            "token_validated":                    self.token_validated,
            "real_token_validated":               self.real_token_validated,
            "entry_execution_included":           self.entry_execution_included,
            "stop_execution_included":            self.stop_execution_included,
            "cleanup_execution_included":         self.cleanup_execution_included,
            "full_lifecycle_execution_included":  self.full_lifecycle_execution_included,
            "current_task_real_execution_allowed": self.current_task_real_execution_allowed,
            "readiness_conclusion":               self.readiness_conclusion,
            "dry_run_authorization_result":       self.dry_run_authorization_result,
            "order_create_path_ref":              self.order_create_path_ref,
            "trading_stop_path_ref":              self.trading_stop_path_ref,
            "base_url_ref":                       self.base_url_ref,
            "send_allowed":                       self.send_allowed,
            "order_endpoint_called":              self.order_endpoint_called,
            "stop_endpoint_called":               self.stop_endpoint_called,
            "no_position_modified":               self.no_position_modified,
            "no_live_endpoint":                   self.no_live_endpoint,
            "no_orders_sent":                     self.no_orders_sent,
            "no_batch_order":                     self.no_batch_order,
            "no_close_only_path":                 self.no_close_only_path,
            "emergency_close_invoked":            self.emergency_close_invoked,
            "leverage_mutated":                   self.leverage_mutated,
            "transfer_invoked":                   self.transfer_invoked,
            "no_secrets_loaded":                  self.no_secrets_loaded,
            "secret_value_observed":              self.secret_value_observed,
            "g20_policy_still_in_place":          self.g20_policy_still_in_place,
            "g20_lifted":                         self.g20_lifted,
            "existing_positions_touched":         list(self.existing_positions_touched),
            "upstream_lifecycle_summary_status":  self.upstream_lifecycle_summary_status,
            "upstream_runner_design_status":      self.upstream_runner_design_status,
            "upstream_runner_dry_run_status":     self.upstream_runner_dry_run_status,
            "upstream_guarded_design_review_status": self.upstream_guarded_design_review_status,
            "upstream_guarded_entry_adapter_status":   self.upstream_guarded_entry_adapter_status,
            "upstream_guarded_stop_adapter_status":    self.upstream_guarded_stop_adapter_status,
            "upstream_guarded_cleanup_adapter_status": self.upstream_guarded_cleanup_adapter_status,
            "upstream_guarded_lifecycle_summary_status":
                self.upstream_guarded_lifecycle_summary_status,
            "upstream_entry_real_permission_review_status":
                self.upstream_entry_real_permission_review_status,
            "upstream_entry_manual_auth_design_status":
                self.upstream_entry_manual_auth_design_status,
            "upstream_entry_manual_auth_design_readiness_conclusion":
                self.upstream_entry_manual_auth_design_readiness_conclusion,
            "blocked_gates":                      list(self.blocked_gates),
            "failed_stage":                       self.failed_stage,
            "status":                             self.status,
            "next_required_task":                 self.next_required_task,
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
# Guarded entry manual authorization dry-run
# ---------------------------------------------------------------------------

class DemoTinyGuardedEntryManualAuthorizationDryRun:
    """
    Pure-computation guarded entry manual authorization dry-run. Dry-runs
    the manual authorization workflow against 20 upstream artifacts. Never
    opens a socket, reads no environment variables, performs no HMAC
    signing, never validates any real token, never treats any token (sample
    or otherwise) as authorization, and NEVER invokes the order-create or
    trading-stop endpoints.

    --allow-dry-run-approval       --> status promoted to
        TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY_BUT_EXECUTION_DISABLED

    --allow-real-entry-execution   --> status fixed to
        REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED   (no socket opened)
    """

    def __init__(self) -> None:
        pass

    def run_checklist(
        self,
        readonly_smoke:                   dict[str, Any] | None,
        reconciliation:                   dict[str, Any] | None,
        protection:                       dict[str, Any] | None,
        contract:                         dict[str, Any] | None,
        noop_plan:                        dict[str, Any] | None,
        lifecycle_mock:                   dict[str, Any] | None,
        real_permission_gate:             dict[str, Any] | None,
        tiny_entry_permission_gate:       dict[str, Any] | None,
        tiny_stop_permission_gate:        dict[str, Any] | None,
        tiny_cleanup_permission_gate:     dict[str, Any] | None,
        lifecycle_summary:                dict[str, Any] | None,
        runner_design:                    dict[str, Any] | None,
        runner_dry_run:                   dict[str, Any] | None,
        guarded_design_review:            dict[str, Any] | None,
        guarded_entry_adapter:            dict[str, Any] | None,
        guarded_stop_adapter:             dict[str, Any] | None,
        guarded_cleanup_adapter:          dict[str, Any] | None,
        guarded_lifecycle_summary:        dict[str, Any] | None,
        entry_real_permission_review:     dict[str, Any] | None,
        entry_manual_authorization_design: dict[str, Any] | None,
        symbol:                           str  = DEFAULT_SELECTED_SYMBOL,
        allow_dry_run_approval:           bool = False,
        allow_real_entry_execution:       bool = False,
        _now:                             datetime | None = None,
    ) -> TinyGuardedEntryManualAuthorizationDryRunResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_entry_execution:
            mode = MODE_REAL_ENTRY_EXECUTION_GUARD
        elif allow_dry_run_approval:
            mode = MODE_AUTHORIZATION_DRY_RUN_APPROVAL
        else:
            mode = MODE_AUTHORIZATION_DRY_RUN_CHECKLIST

        blocked: list[str] = []
        stages:  dict[str, dict[str, Any]] = {}

        # ===============================================================
        # stage_0_artifact_preflight
        # ===============================================================
        sym = _safe_str(symbol)
        existing_snapshot = _positions_from_reconciliation(reconciliation)
        existing_symbols  = _symbols_only(existing_snapshot)

        readonly_present     = isinstance(readonly_smoke, dict) and bool(readonly_smoke)
        recon_present        = isinstance(reconciliation, dict) and bool(reconciliation)
        protection_present   = isinstance(protection, dict) and bool(protection)
        contract_present     = isinstance(contract, dict) and bool(contract)
        noop_present         = isinstance(noop_plan, dict) and bool(noop_plan)
        lifecycle_present    = isinstance(lifecycle_mock, dict) and bool(lifecycle_mock)
        real_perm_present    = isinstance(real_permission_gate, dict) and bool(real_permission_gate)
        entry_perm_present   = (
            isinstance(tiny_entry_permission_gate, dict)
            and bool(tiny_entry_permission_gate)
        )
        stop_perm_present    = (
            isinstance(tiny_stop_permission_gate, dict)
            and bool(tiny_stop_permission_gate)
        )
        cleanup_perm_present = (
            isinstance(tiny_cleanup_permission_gate, dict)
            and bool(tiny_cleanup_permission_gate)
        )
        summary_present      = isinstance(lifecycle_summary, dict) and bool(lifecycle_summary)
        runner_design_present = isinstance(runner_design, dict) and bool(runner_design)
        runner_dry_run_present = isinstance(runner_dry_run, dict) and bool(runner_dry_run)
        guarded_review_present = (
            isinstance(guarded_design_review, dict) and bool(guarded_design_review)
        )
        guarded_entry_present = (
            isinstance(guarded_entry_adapter, dict) and bool(guarded_entry_adapter)
        )
        guarded_stop_present = (
            isinstance(guarded_stop_adapter, dict) and bool(guarded_stop_adapter)
        )
        guarded_cleanup_present = (
            isinstance(guarded_cleanup_adapter, dict) and bool(guarded_cleanup_adapter)
        )
        guarded_lifecycle_present = (
            isinstance(guarded_lifecycle_summary, dict) and bool(guarded_lifecycle_summary)
        )
        entry_perm_review_present = (
            isinstance(entry_real_permission_review, dict) and bool(entry_real_permission_review)
        )
        entry_auth_design_present = (
            isinstance(entry_manual_authorization_design, dict)
            and bool(entry_manual_authorization_design)
        )

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
        entry_auth_design_readiness = _safe_str(
            (entry_manual_authorization_design or {}).get("readiness_conclusion", "")
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

        if readonly_present and endpoint_family and endpoint_family != EXPECTED_ENDPOINT_FAMILY:
            blocked.append(GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO)
        if readonly_present and account_mode and account_mode != EXPECTED_ACCOUNT_MODE:
            blocked.append(GATE_ACCOUNT_MODE_NOT_DEMO)
        if readonly_present and proof_strength and proof_strength != EXPECTED_PROOF_STRENGTH:
            blocked.append(GATE_PROOF_STRENGTH_NOT_STRONG)
        if recon_present and position_details_source and position_details_source != EXPECTED_POSITION_DETAILS_SOURCE:
            blocked.append(GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY)

        if entry_auth_design_present and entry_auth_design_status and (
            entry_auth_design_status not in ACCEPTABLE_ENTRY_MANUAL_AUTH_DESIGN_STATUSES
        ):
            blocked.append(GATE_ENTRY_MANUAL_AUTH_DESIGN_STATUS_UNACCEPTABLE)

        if entry_auth_design_present and entry_auth_design_readiness and (
            entry_auth_design_readiness != READINESS_CONCLUSION_NOT_EXECUTABLE
        ):
            blocked.append(GATE_ENTRY_MANUAL_AUTH_DESIGN_READINESS_EXECUTABLE)

        if sym and sym != DRY_RUN_EXPECTED_SYMBOL:
            blocked.append(GATE_SELECTED_SYMBOL_NOT_SOLUSDT)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 20 upstream artifacts + runtime proof envelope + entry manual authorization design status / readiness.",
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
            "entry_manual_authorization_design_status_acceptable": sorted(
                ACCEPTABLE_ENTRY_MANUAL_AUTH_DESIGN_STATUSES
            ),
            "entry_manual_authorization_design_readiness_observed": entry_auth_design_readiness,
            "entry_manual_authorization_design_readiness_expected": READINESS_CONCLUSION_NOT_EXECUTABLE,
            "selected_symbol":                          sym,
            "selected_symbol_expected":                 DRY_RUN_EXPECTED_SYMBOL,
            "current_task_real_execution_allowed":      False,
        }

        # ===============================================================
        # stage_1_manual_authorization_dry_run_scope
        # ===============================================================
        authorization_dry_run_scope: dict[str, Any] = {
            "guarded_entry_manual_authorization_dry_run": True,
            "authorization_dry_run_only":           True,
            "token_validation_simulated":           True,
            "token_validated":                      False,
            "real_token_validated":                 False,
            "entry_execution_included":             False,
            "stop_execution_included":              False,
            "cleanup_execution_included":           False,
            "full_lifecycle_execution_included":    False,
            "real_entry_implemented":               False,
            "real_execution_allowed":               False,
            "order_endpoint_called":                False,
            "stop_endpoint_called":                 False,
            "no_endpoint_invoked_in_this_task":     True,
            "no_position_modified":                 True,
            "no_secrets_loaded":                    True,
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "next_required_task":                   "TASK-014AL_guarded_entry_final_pre_execution_review",
            "scope_summary": (
                "TASK-014AK only dry-runs the manual authorization workflow "
                "shell. It simulates token-pattern matching and required-flag "
                "completeness, but never validates any real token, never "
                "treats any token as authorization, never sends an order, "
                "never calls any endpoint, never modifies any position, "
                "never lifts G20, and never loads any secret."
            ),
        }
        stages[STAGE_1_MANUAL_AUTHORIZATION_DRY_RUN_SCOPE] = {
            "stage":   STAGE_1_MANUAL_AUTHORIZATION_DRY_RUN_SCOPE,
            "summary": "Assert guarded entry manual authorization dry-run scope (dry-run-only).",
            "authorization_dry_run_scope":          authorization_dry_run_scope,
        }
        blocked.append(GATE_GUARDED_ENTRY_MANUAL_AUTH_DRY_RUN_ONLY)
        blocked.append(GATE_AUTHORIZATION_DRY_RUN_ONLY)
        blocked.append(GATE_TOKEN_VALIDATION_SIMULATED)
        blocked.append(GATE_TOKEN_NOT_VALIDATED_SCOPE)
        blocked.append(GATE_REAL_TOKEN_NOT_VALIDATED_SCOPE)
        blocked.append(GATE_ENTRY_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_STOP_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_CLEANUP_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE)
        blocked.append(GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE)
        blocked.append(GATE_NO_ENDPOINT_INVOKED)
        blocked.append(GATE_NO_POSITION_MODIFIED_SCOPE)
        blocked.append(GATE_NO_SECRETS_LOADED)
        blocked.append(GATE_NO_G20_LIFT)

        # ===============================================================
        # stage_2_authorization_token_dry_run
        # ===============================================================
        # Sample token pattern match is purely a string-level lexical
        # check used for documentation. It is NEVER treated as
        # authorization, NEVER persisted as a secret.
        sample_token_matches_pattern_simulated = (
            SAMPLE_TOKEN.startswith("CONFIRM_DEMO_TINY_ENTRY_")
            and SAMPLE_TOKEN.endswith("_SOLUSDT")
            and len(SAMPLE_TOKEN.split("_")) == 6
        )
        authorization_token_dry_run: dict[str, Any] = {
            "token_pattern":                       ENTRY_TOKEN_PATTERN,
            "sample_token":                        SAMPLE_TOKEN,
            "token_matches_pattern_simulated":     sample_token_matches_pattern_simulated,
            "token_validated":                     False,
            "real_token_validated":                False,
            "token_format_not_authorization":      True,
            "token_must_be_single_use":            True,
            "token_reuse_policy":                  "forbidden",
            "token_expiry_policy":                 "documented_only",
            "token_not_logged_as_secret":          True,
            "token_contains_no_secret":            True,
            "tokens_not_validated_in_this_task":   True,
            "tokens_never_treated_as_authorization_in_this_task": True,
            "sample_token_not_treated_as_authorization": True,
        }
        stages[STAGE_2_AUTHORIZATION_TOKEN_DRY_RUN] = {
            "stage":   STAGE_2_AUTHORIZATION_TOKEN_DRY_RUN,
            "summary": "Dry-run authorization token pattern (sample token only; never validated; never treated as authorization).",
            "authorization_token_dry_run":         authorization_token_dry_run,
        }
        blocked.append(GATE_TOKEN_PATTERN_PRESENT)
        blocked.append(GATE_SAMPLE_TOKEN_PRESENT)
        blocked.append(GATE_SAMPLE_TOKEN_MATCHES_PATTERN_SIMULATED)
        blocked.append(GATE_TOKEN_NOT_VALIDATED)
        blocked.append(GATE_REAL_TOKEN_NOT_VALIDATED)
        blocked.append(GATE_TOKEN_FORMAT_NOT_AUTHORIZATION)
        blocked.append(GATE_TOKEN_SINGLE_USE_DOCUMENTED)
        blocked.append(GATE_TOKEN_REUSE_FORBIDDEN)
        blocked.append(GATE_TOKEN_EXPIRY_DOCUMENTED)
        blocked.append(GATE_TOKEN_NOT_LOGGED_AS_SECRET)
        blocked.append(GATE_TOKEN_NO_SECRET)
        blocked.append(GATE_SAMPLE_TOKEN_NOT_AUTHORIZATION)

        # ===============================================================
        # stage_3_required_flags_dry_run
        # ===============================================================
        required_flags_dry_run: dict[str, Any] = {
            "required_flags":                       list(REQUIRED_HUMAN_CONFIRMATION_FLAGS),
            "required_flag_count":                  len(REQUIRED_HUMAN_CONFIRMATION_FLAGS),
            "flags_present_simulated":              True,
            "flags_validated":                      False,
            "manual_boundary_required":             True,
            "second_confirmation_required":         True,
            "independent_reviewer_recommended":     True,
            "rick_explicit_authorization_required": True,
            "dry_run_authorization_result":         DRY_RUN_AUTHORIZATION_RESULT,
            "confirm_symbol_flag":                  "--confirm-symbol SOLUSDT",
            "confirm_side_flag":                    "--confirm-side Buy",
            "confirm_qty_flag":                     "--confirm-qty 0.1",
            "confirm_max_notional_flag":            "--confirm-max-notional-usdt 10",
            "confirm_existing_count_flag":          "--confirm-existing-position-count 5",
            "confirm_existing_symbols_flag":        "--confirm-existing-symbols AIXBTUSDT,ENAUSDT,TIAUSDT,POLYXUSDT,EDUUSDT",
            "confirm_reduce_only_false_flag":       "--confirm-reduce-only false",
            "confirm_position_idx_flag":            "--confirm-position-idx 0",
            "confirm_order_type_flag":              "--confirm-order-type Market",
            "confirm_stop_required_flag":           "--confirm-stop-required-after-entry true",
            "confirm_stop_loss_flag":               "--confirm-stop-loss 61.18",
            "confirm_cleanup_manual_boundary_flag": "--confirm-cleanup-manual-boundary true",
        }
        stages[STAGE_3_REQUIRED_FLAGS_DRY_RUN] = {
            "stage":   STAGE_3_REQUIRED_FLAGS_DRY_RUN,
            "summary": "Dry-run the 13 required human confirmation flags (simulated only; never validated).",
            "required_flags_dry_run":               required_flags_dry_run,
        }
        blocked.append(GATE_REQUIRED_FLAGS_PRESENT_SIMULATED)
        blocked.append(GATE_REQUIRED_FLAG_COUNT_13)
        blocked.append(GATE_FLAGS_NOT_VALIDATED)
        blocked.append(GATE_SECOND_CONFIRMATION_REQUIRED)
        blocked.append(GATE_MANUAL_BOUNDARY_REQUIRED)
        blocked.append(GATE_RICK_EXPLICIT_AUTHORIZATION_REQUIRED)
        blocked.append(GATE_INDEPENDENT_REVIEWER_RECOMMENDED)
        blocked.append(GATE_DRY_RUN_AUTHORIZATION_RESULT_DOCUMENTED)
        blocked.append(GATE_CONFIRM_SYMBOL_FLAG)
        blocked.append(GATE_CONFIRM_SIDE_FLAG)
        blocked.append(GATE_CONFIRM_QTY_FLAG)
        blocked.append(GATE_CONFIRM_MAX_NOTIONAL_FLAG)
        blocked.append(GATE_CONFIRM_EXISTING_COUNT_FLAG)
        blocked.append(GATE_CONFIRM_EXISTING_SYMBOLS_FLAG)
        blocked.append(GATE_CONFIRM_REDUCE_ONLY_FALSE_FLAG)
        blocked.append(GATE_CONFIRM_POSITION_IDX_FLAG)
        blocked.append(GATE_CONFIRM_ORDER_TYPE_FLAG)
        blocked.append(GATE_CONFIRM_STOP_REQUIRED_FLAG)
        blocked.append(GATE_CONFIRM_STOP_LOSS_FLAG)
        blocked.append(GATE_CONFIRM_CLEANUP_MANUAL_BOUNDARY_FLAG)

        # ===============================================================
        # stage_4_pre_execution_readiness_dry_run
        # ===============================================================
        pre_execution_readiness_dry_run: dict[str, Any] = {
            "git_commit_hash_must_match_expected":  True,
            "readme_current":                       True,
            "next_action_current":                  True,
            "command_log_current":                  True,
            "latest_readonly_timestamp_recent":     True,
            "protected_positions_unchanged":        True,
            "protected_position_symbols":           list(EXISTING_POSITION_SYMBOLS),
            "solusdt_absent_before_entry":          True,
            "estimated_notional_usdt":              DRY_RUN_EXPECTED_ESTIMATED_NOTIONAL,
            "max_notional_usdt":                    DRY_RUN_EXPECTED_MAX_NOTIONAL_USDT,
            "estimated_notional_within_cap":        (
                DRY_RUN_EXPECTED_ESTIMATED_NOTIONAL <= DRY_RUN_EXPECTED_MAX_NOTIONAL_USDT
            ),
            "qty":                                  DRY_RUN_EXPECTED_QTY,
            "side":                                 DRY_RUN_EXPECTED_ENTRY_SIDE,
            "reduce_only":                          DRY_RUN_EXPECTED_REDUCE_ONLY,
            "stop_attach_plan_ready":               True,
            "cleanup_plan_ready":                   True,
            "discord_must_not_trigger_execution":   True,
            "notion_must_not_trigger_execution":    True,
            "no_cron_or_background_automation":     True,
            "readiness_check_simulated":            True,
            "readiness_validated_for_real_execution": False,
            "checklist_executed_in_this_task":      False,
        }
        stages[STAGE_4_PRE_EXECUTION_READINESS_DRY_RUN] = {
            "stage":   STAGE_4_PRE_EXECUTION_READINESS_DRY_RUN,
            "summary": "Pre-execution readiness checklist dry-run (simulated only; never validated for real execution).",
            "pre_execution_readiness_dry_run":      pre_execution_readiness_dry_run,
        }
        blocked.append(GATE_GIT_COMMIT_HASH_MUST_MATCH)
        blocked.append(GATE_README_CURRENT)
        blocked.append(GATE_NEXT_ACTION_CURRENT)
        blocked.append(GATE_COMMAND_LOG_CURRENT)
        blocked.append(GATE_LATEST_READONLY_TIMESTAMP_RECENT)
        blocked.append(GATE_PROTECTED_POSITIONS_UNCHANGED)
        blocked.append(GATE_SOLUSDT_ABSENT_BEFORE_ENTRY)
        blocked.append(GATE_ESTIMATED_NOTIONAL_WITHIN_CAP)
        blocked.append(GATE_PRE_QTY_0_1)
        blocked.append(GATE_PRE_SIDE_BUY)
        blocked.append(GATE_PRE_REDUCE_ONLY_FALSE)
        blocked.append(GATE_STOP_ATTACH_PLAN_READY)
        blocked.append(GATE_CLEANUP_PLAN_READY)
        blocked.append(GATE_NO_DISCORD_TRIGGER)
        blocked.append(GATE_NO_NOTION_TRIGGER)
        blocked.append(GATE_NO_CRON_OR_BACKGROUND_AUTOMATION)
        blocked.append(GATE_READINESS_CHECK_SIMULATED)
        blocked.append(GATE_READINESS_NOT_VALIDATED_FOR_REAL_EXECUTION)

        # ===============================================================
        # stage_5_entry_request_template_dry_run
        # ===============================================================
        sym_eff = sym or DRY_RUN_EXPECTED_SYMBOL
        entry_request_template_dry_run: dict[str, Any] = {
            "preview_only":                  True,
            "dry_run_only":                  True,
            "send_allowed":                  False,
            "endpoint_called":               False,
            "real_payload":                  False,
            "signature_present":             False,
            "private_headers":               [],
            "endpoint_path_ref":             ORDER_CREATE_PATH_REF,
            "base_url_ref":                  BASE_URL_DEMO_REF,
            "demo_endpoint_allowlist":       list(DEMO_ENDPOINT_ALLOWLIST),
            "live_endpoint_denylist":        list(LIVE_ENDPOINT_DENYLIST),
            "category":                      DRY_RUN_EXPECTED_CATEGORY,
            "symbol":                        sym_eff,
            "side":                          DRY_RUN_EXPECTED_ENTRY_SIDE,
            "orderType":                     DRY_RUN_EXPECTED_ORDER_TYPE,
            "qty":                           DRY_RUN_EXPECTED_QTY,
            "reduceOnly":                    DRY_RUN_EXPECTED_REDUCE_ONLY,
            "closeOnTrigger":                DRY_RUN_EXPECTED_CLOSE_ON_TRIGGER,
            "positionIdx":                   DRY_RUN_EXPECTED_POSITION_IDX,
            "orderLinkId_prefixes":          list(ENTRY_DRY_RUN_ORDER_LINK_ID_PREFIXES),
            "sender_adapter_invoked":        False,
            "no_sender_adapter":             True,
            "real_payload_conversion":       False,
            "template_not_sent_in_this_task": True,
        }
        stages[STAGE_5_ENTRY_REQUEST_TEMPLATE_DRY_RUN] = {
            "stage":   STAGE_5_ENTRY_REQUEST_TEMPLATE_DRY_RUN,
            "summary": "Entry request template dry-run (preview-only; never sent; never converted to real payload).",
            "entry_request_template_dry_run":      entry_request_template_dry_run,
        }
        blocked.append(GATE_TEMPLATE_PRESENT)
        blocked.append(GATE_TEMPLATE_PREVIEW_ONLY)
        blocked.append(GATE_TEMPLATE_DRY_RUN_ONLY)
        blocked.append(GATE_TEMPLATE_SEND_ALLOWED_FALSE)
        blocked.append(GATE_TEMPLATE_ENDPOINT_CALLED_FALSE)
        blocked.append(GATE_TEMPLATE_REAL_PAYLOAD_FALSE)
        blocked.append(GATE_TEMPLATE_SIGNATURE_PRESENT_FALSE)
        blocked.append(GATE_TEMPLATE_PRIVATE_HEADERS_EMPTY)
        blocked.append(GATE_TEMPLATE_ENDPOINT_PATH_ORDER_CREATE)
        blocked.append(GATE_TEMPLATE_BASE_URL_DEMO_ONLY)
        blocked.append(GATE_TEMPLATE_SIDE_BUY)
        blocked.append(GATE_TEMPLATE_QTY_0_1)
        blocked.append(GATE_TEMPLATE_REDUCE_ONLY_FALSE)
        blocked.append(GATE_TEMPLATE_CLOSE_ON_TRIGGER_FALSE)
        blocked.append(GATE_TEMPLATE_POSITION_IDX_ZERO)
        blocked.append(GATE_TEMPLATE_ORDER_TYPE_MARKET)
        blocked.append(GATE_TEMPLATE_ORDER_LINK_ID_PREFIX_DOCUMENTED)
        blocked.append(GATE_TEMPLATE_NO_SENDER_ADAPTER)

        # ===============================================================
        # stage_6_post_entry_boundary_dry_run
        # ===============================================================
        post_entry_boundary_dry_run: dict[str, Any] = {
            "entry_success_does_not_auto_attach_stop":  True,
            "stop_attach_separate_manual_authorization": True,
            "stop_loss":                                 DRY_RUN_EXPECTED_STOP_LOSS,
            "tpsl_mode":                                 DRY_RUN_EXPECTED_TPSL_MODE,
            "sl_trigger_by":                             DRY_RUN_EXPECTED_SL_TRIGGER_BY,
            "cleanup_separate_manual_authorization":     True,
            "no_automatic_cleanup":                      True,
            "no_automatic_emergency_close":              True,
            "entry_success_without_stop_attach_manual_review": True,
            "stop_attach_fail_manual_review":            True,
            "cleanup_needs_separate_manual_boundary_only": True,
            "stop_attach_executed_in_this_task":         False,
            "cleanup_executed_in_this_task":             False,
        }
        stages[STAGE_6_POST_ENTRY_BOUNDARY_DRY_RUN] = {
            "stage":   STAGE_6_POST_ENTRY_BOUNDARY_DRY_RUN,
            "summary": "Post-entry stop / cleanup boundary dry-run (never executed).",
            "post_entry_boundary_dry_run":          post_entry_boundary_dry_run,
        }
        blocked.append(GATE_ENTRY_SUCCESS_DOES_NOT_AUTO_ATTACH_STOP)
        blocked.append(GATE_STOP_ATTACH_SEPARATE_MANUAL_AUTH)
        blocked.append(GATE_BOUNDARY_STOP_LOSS_61_18)
        blocked.append(GATE_BOUNDARY_TPSL_MODE_FULL)
        blocked.append(GATE_BOUNDARY_SL_TRIGGER_BY_MARKPRICE)
        blocked.append(GATE_CLEANUP_SEPARATE_MANUAL_AUTH)
        blocked.append(GATE_NO_AUTO_CLEANUP_BOUNDARY)
        blocked.append(GATE_NO_AUTO_EMERGENCY_CLOSE_BOUNDARY)
        blocked.append(GATE_ENTRY_SUCCESS_WITHOUT_STOP_MANUAL_REVIEW)
        blocked.append(GATE_STOP_ATTACH_FAIL_MANUAL_REVIEW)
        blocked.append(GATE_CLEANUP_SEPARATE_BOUNDARY_ONLY)

        # ===============================================================
        # stage_7_failure_and_abort_dry_run
        # ===============================================================
        failure_and_abort_dry_run: dict[str, Any] = {
            "missing_flag":                  "FAIL_CLOSED",
            "token_mismatch":                "FAIL_CLOSED",
            "token_reused":                  "FAIL_CLOSED",
            "readonly_stale":                "FAIL_CLOSED",
            "solusdt_already_exists":        "FAIL_CLOSED",
            "protected_position_mismatch":   "MANUAL_REVIEW_REQUIRED",
            "notional_cap_exceeded":         "FAIL_CLOSED",
            "qty_mismatch":                  "FAIL_CLOSED",
            "side_mismatch":                 "FAIL_CLOSED",
            "reduce_only_mismatch":          "FAIL_CLOSED",
            "live_endpoint_detected":        "FAIL_CLOSED",
            "secret_emission_detected":      "FAIL_CLOSED",
            "no_auto_retry":                 True,
            "no_auto_stop_attach":           True,
            "no_auto_cleanup":               True,
            "no_auto_emergency_close":       True,
            "no_auto_next_step":             True,
            "no_background_loop":            True,
            "no_cron":                       True,
            "no_scheduler":                  True,
            "no_discord_trigger":            True,
            "no_notion_trigger":             True,
            "manual_intervention_only":      True,
        }
        stages[STAGE_7_FAILURE_AND_ABORT_DRY_RUN] = {
            "stage":   STAGE_7_FAILURE_AND_ABORT_DRY_RUN,
            "summary": "Future manual-authorization failure / abort policy dry-run (no auto-progression of any kind).",
            "failure_and_abort_dry_run":     failure_and_abort_dry_run,
        }
        blocked.append(GATE_MISSING_FLAG_FAIL_CLOSED)
        blocked.append(GATE_TOKEN_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_TOKEN_REUSED_FAIL_CLOSED)
        blocked.append(GATE_READONLY_STALE_FAIL_CLOSED)
        blocked.append(GATE_SOLUSDT_EXISTS_FAIL_CLOSED)
        blocked.append(GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW)
        blocked.append(GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED)
        blocked.append(GATE_QTY_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_SIDE_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_SECRET_EMISSION_FAIL_CLOSED)
        blocked.append(GATE_NO_AUTO_RETRY)
        blocked.append(GATE_NO_AUTO_STOP_ATTACH_FAILURE)
        blocked.append(GATE_NO_AUTO_CLEANUP_FAILURE)
        blocked.append(GATE_NO_AUTO_EMERGENCY_CLOSE)
        blocked.append(GATE_NO_AUTO_NEXT_STEP)
        blocked.append(GATE_NO_BACKGROUND_LOOP)
        blocked.append(GATE_NO_CRON)
        blocked.append(GATE_NO_SCHEDULER)
        blocked.append(GATE_FAILURE_NO_DISCORD_TRIGGER)
        blocked.append(GATE_FAILURE_NO_NOTION_TRIGGER)

        # ===============================================================
        # stage_8_documentation_sync_review
        # ===============================================================
        documentation_sync_review: dict[str, Any] = {
            "readme_status_board_sync_required":  True,
            "next_action_sync_required":          True,
            "command_log_sync_required":          True,
            "forbidden_status_sync_required":     True,
            "next_required_task_sync_required":   True,
            "readme_path_ref":                    "README.md",
            "next_action_path_ref":               "docs/research/commands/NEXT_ACTION.md",
            "command_log_path_ref":               "docs/research/commands/COMMAND_LOG.md",
            "next_required_task":                 "TASK-014AL_guarded_entry_final_pre_execution_review",
            "documentation_only_plan":            True,
            "markdown_read_in_this_module":       False,
        }
        stages[STAGE_8_DOCUMENTATION_SYNC_REVIEW] = {
            "stage":   STAGE_8_DOCUMENTATION_SYNC_REVIEW,
            "summary": "Documentation sync plan (README / NEXT_ACTION / COMMAND_LOG / forbidden status / next_required_task).",
            "documentation_sync_review":          documentation_sync_review,
        }
        blocked.append(GATE_README_SYNC_REQUIRED)
        blocked.append(GATE_NEXT_ACTION_SYNC_REQUIRED)
        blocked.append(GATE_COMMAND_LOG_SYNC_REQUIRED)
        blocked.append(GATE_FORBIDDEN_STATUS_SYNC_REQUIRED)
        blocked.append(GATE_NEXT_REQUIRED_TASK_SYNC_REQUIRED)

        # ===============================================================
        # stage_9_final_manual_authorization_dry_run_verdict
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
            mode_out   = MODE_REAL_ENTRY_EXECUTION_GUARD
        elif allow_dry_run_approval:
            failed_stage = ""
            status_out = STATUS_DRY_RUN_READY_EXEC_DISABLED
            mode_out   = MODE_AUTHORIZATION_DRY_RUN_APPROVAL
        else:
            failed_stage = ""
            status_out = STATUS_DRY_RUN_READY
            mode_out   = MODE_AUTHORIZATION_DRY_RUN_CHECKLIST

        final_manual_authorization_dry_run_verdict: dict[str, Any] = {
            "dry_run_approval_allowed":           allow_dry_run_approval,
            "real_entry_execution_requested":     bool(allow_real_entry_execution),
            "real_execution_allowed":             False,
            "real_entry_implemented":             False,
            "guarded_entry_manual_authorization_dry_run": True,
            "authorization_dry_run_only":         True,
            "token_validation_simulated":         True,
            "token_validated":                    False,
            "real_token_validated":               False,
            "entry_execution_included":           False,
            "stop_execution_included":            False,
            "cleanup_execution_included":         False,
            "full_lifecycle_execution_included":  False,
            "current_task_real_execution_allowed": False,
            "readiness_conclusion":               READINESS_CONCLUSION_NOT_EXECUTABLE,
            "dry_run_authorization_result":       DRY_RUN_AUTHORIZATION_RESULT,
            "g20_policy_still_in_place":          True,
            "g20_lifted":                         False,
            "no_real_order_endpoint":             True,
            "no_real_stop_endpoint":              True,
            "no_position_modified":               True,
            "no_live_endpoint":                   True,
            "no_secrets_loaded":                  True,
            "no_secrets_emitted":                 True,
            "send_allowed":                       False,
            "order_endpoint_called":              False,
            "stop_endpoint_called":               False,
            "status":                             status_out,
            "mode":                               mode_out,
            "next_required_task":                 "TASK-014AL_guarded_entry_final_pre_execution_review",
        }

        audit_artifacts: dict[str, Any] = {
            "authorization_dry_run_scope":        dict(authorization_dry_run_scope),
            "authorization_token_dry_run":        dict(authorization_token_dry_run),
            "required_flags_dry_run":             dict(required_flags_dry_run),
            "pre_execution_readiness_dry_run":    dict(pre_execution_readiness_dry_run),
            "entry_request_template_dry_run":     dict(entry_request_template_dry_run),
            "post_entry_boundary_dry_run":        dict(post_entry_boundary_dry_run),
            "failure_and_abort_dry_run":          dict(failure_and_abort_dry_run),
            "documentation_sync_review":          dict(documentation_sync_review),
            "final_manual_authorization_dry_run_verdict":
                dict(final_manual_authorization_dry_run_verdict),
            "response_status":                    "DRY_RUN_NOT_SENT",
            "response_from_exchange":             False,
            "sanitized":                          True,
            "no_secrets":                         True,
            "forbidden_log_fields":               list(FORBIDDEN_LOG_FIELDS),
        }

        stages[STAGE_9_FINAL_MANUAL_AUTHORIZATION_DRY_RUN_VERDICT] = {
            "stage":   STAGE_9_FINAL_MANUAL_AUTHORIZATION_DRY_RUN_VERDICT,
            "summary": "Final manual authorization dry-run verdict + permanent execution guard.",
            "final_manual_authorization_dry_run_verdict":
                final_manual_authorization_dry_run_verdict,
        }

        return TinyGuardedEntryManualAuthorizationDryRunResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            authorization_dry_run_scope=authorization_dry_run_scope,
            authorization_token_dry_run=authorization_token_dry_run,
            required_flags_dry_run=required_flags_dry_run,
            pre_execution_readiness_dry_run=pre_execution_readiness_dry_run,
            entry_request_template_dry_run=entry_request_template_dry_run,
            post_entry_boundary_dry_run=post_entry_boundary_dry_run,
            failure_and_abort_dry_run=failure_and_abort_dry_run,
            documentation_sync_review=documentation_sync_review,
            audit_artifacts=audit_artifacts,
            final_manual_authorization_dry_run_verdict=final_manual_authorization_dry_run_verdict,
            dry_run_approval_allowed=allow_dry_run_approval,
            real_entry_execution_requested=bool(allow_real_entry_execution),
            real_execution_allowed=False,
            real_entry_implemented=False,
            guarded_entry_manual_authorization_dry_run=True,
            authorization_dry_run_only=True,
            token_validation_simulated=True,
            token_validated=False,
            real_token_validated=False,
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
            upstream_entry_manual_auth_design_readiness_conclusion=entry_auth_design_readiness,
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
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_ENTRY_MANUAL_AUTH_DESIGN_STATUS_UNACCEPTABLE,
            GATE_ENTRY_MANUAL_AUTH_DESIGN_READINESS_EXECUTABLE,
            GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
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
    "ENTRY_TOKEN_PATTERN",
    "SAMPLE_TOKEN",
    "REQUIRED_HUMAN_CONFIRMATION_FLAGS",
    "ENTRY_DRY_RUN_ORDER_LINK_ID_PREFIXES",
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
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_LIFECYCLE_STATUS",
    "EXPECTED_INSTRUMENT_CATEGORY",
    "DRY_RUN_EXPECTED_SYMBOL",
    "DRY_RUN_EXPECTED_CATEGORY",
    "DRY_RUN_EXPECTED_ENTRY_SIDE",
    "DRY_RUN_EXPECTED_QTY",
    "DRY_RUN_EXPECTED_QTY_STEP",
    "DRY_RUN_EXPECTED_MIN_ORDER_QTY",
    "DRY_RUN_EXPECTED_TICK_SIZE",
    "DRY_RUN_EXPECTED_MAX_NOTIONAL_USDT",
    "DRY_RUN_EXPECTED_ENTRY_REFERENCE",
    "DRY_RUN_EXPECTED_ESTIMATED_NOTIONAL",
    "DRY_RUN_EXPECTED_POSITION_IDX",
    "DRY_RUN_EXPECTED_REDUCE_ONLY",
    "DRY_RUN_EXPECTED_CLOSE_ON_TRIGGER",
    "DRY_RUN_EXPECTED_ORDER_TYPE",
    "DRY_RUN_EXPECTED_STOP_LOSS",
    "DRY_RUN_EXPECTED_TPSL_MODE",
    "DRY_RUN_EXPECTED_SL_TRIGGER_BY",
    "DRY_RUN_EXPECTED_EXISTING_COUNT",
    "FORBIDDEN_LOG_FIELDS",
    "READINESS_CONCLUSION_NOT_EXECUTABLE",
    "DRY_RUN_AUTHORIZATION_RESULT",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_MANUAL_AUTHORIZATION_DRY_RUN_SCOPE",
    "STAGE_2_AUTHORIZATION_TOKEN_DRY_RUN",
    "STAGE_3_REQUIRED_FLAGS_DRY_RUN",
    "STAGE_4_PRE_EXECUTION_READINESS_DRY_RUN",
    "STAGE_5_ENTRY_REQUEST_TEMPLATE_DRY_RUN",
    "STAGE_6_POST_ENTRY_BOUNDARY_DRY_RUN",
    "STAGE_7_FAILURE_AND_ABORT_DRY_RUN",
    "STAGE_8_DOCUMENTATION_SYNC_REVIEW",
    "STAGE_9_FINAL_MANUAL_AUTHORIZATION_DRY_RUN_VERDICT",
    "ALL_STAGES",
    "STATUS_DRY_RUN_READY",
    "STATUS_DRY_RUN_READY_EXEC_DISABLED",
    "STATUS_REAL_ENTRY_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_AUTHORIZATION_DRY_RUN_CHECKLIST",
    "MODE_AUTHORIZATION_DRY_RUN_APPROVAL",
    "MODE_REAL_ENTRY_EXECUTION_GUARD",
    "MODE_FAIL_CLOSED",
    # general (30)
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
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_NOT_SOLUSDT",
    "GATE_ENTRY_MANUAL_AUTH_DESIGN_STATUS_UNACCEPTABLE",
    "GATE_ENTRY_MANUAL_AUTH_DESIGN_READINESS_EXECUTABLE",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # scope (15)
    "GATE_GUARDED_ENTRY_MANUAL_AUTH_DRY_RUN_ONLY",
    "GATE_AUTHORIZATION_DRY_RUN_ONLY",
    "GATE_TOKEN_VALIDATION_SIMULATED",
    "GATE_TOKEN_NOT_VALIDATED_SCOPE",
    "GATE_REAL_TOKEN_NOT_VALIDATED_SCOPE",
    "GATE_ENTRY_EXECUTION_NOT_INCLUDED",
    "GATE_STOP_EXECUTION_NOT_INCLUDED",
    "GATE_CLEANUP_EXECUTION_NOT_INCLUDED",
    "GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED",
    "GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE",
    "GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE",
    "GATE_NO_ENDPOINT_INVOKED",
    "GATE_NO_POSITION_MODIFIED_SCOPE",
    "GATE_NO_SECRETS_LOADED",
    "GATE_NO_G20_LIFT",
    # token dry-run (12)
    "GATE_TOKEN_PATTERN_PRESENT",
    "GATE_SAMPLE_TOKEN_PRESENT",
    "GATE_SAMPLE_TOKEN_MATCHES_PATTERN_SIMULATED",
    "GATE_TOKEN_NOT_VALIDATED",
    "GATE_REAL_TOKEN_NOT_VALIDATED",
    "GATE_TOKEN_FORMAT_NOT_AUTHORIZATION",
    "GATE_TOKEN_SINGLE_USE_DOCUMENTED",
    "GATE_TOKEN_REUSE_FORBIDDEN",
    "GATE_TOKEN_EXPIRY_DOCUMENTED",
    "GATE_TOKEN_NOT_LOGGED_AS_SECRET",
    "GATE_TOKEN_NO_SECRET",
    "GATE_SAMPLE_TOKEN_NOT_AUTHORIZATION",
    # flags dry-run (20)
    "GATE_REQUIRED_FLAGS_PRESENT_SIMULATED",
    "GATE_REQUIRED_FLAG_COUNT_13",
    "GATE_FLAGS_NOT_VALIDATED",
    "GATE_SECOND_CONFIRMATION_REQUIRED",
    "GATE_MANUAL_BOUNDARY_REQUIRED",
    "GATE_RICK_EXPLICIT_AUTHORIZATION_REQUIRED",
    "GATE_INDEPENDENT_REVIEWER_RECOMMENDED",
    "GATE_DRY_RUN_AUTHORIZATION_RESULT_DOCUMENTED",
    "GATE_CONFIRM_SYMBOL_FLAG",
    "GATE_CONFIRM_SIDE_FLAG",
    "GATE_CONFIRM_QTY_FLAG",
    "GATE_CONFIRM_MAX_NOTIONAL_FLAG",
    "GATE_CONFIRM_EXISTING_COUNT_FLAG",
    "GATE_CONFIRM_EXISTING_SYMBOLS_FLAG",
    "GATE_CONFIRM_REDUCE_ONLY_FALSE_FLAG",
    "GATE_CONFIRM_POSITION_IDX_FLAG",
    "GATE_CONFIRM_ORDER_TYPE_FLAG",
    "GATE_CONFIRM_STOP_REQUIRED_FLAG",
    "GATE_CONFIRM_STOP_LOSS_FLAG",
    "GATE_CONFIRM_CLEANUP_MANUAL_BOUNDARY_FLAG",
    # pre-execution readiness (18)
    "GATE_GIT_COMMIT_HASH_MUST_MATCH",
    "GATE_README_CURRENT",
    "GATE_NEXT_ACTION_CURRENT",
    "GATE_COMMAND_LOG_CURRENT",
    "GATE_LATEST_READONLY_TIMESTAMP_RECENT",
    "GATE_PROTECTED_POSITIONS_UNCHANGED",
    "GATE_SOLUSDT_ABSENT_BEFORE_ENTRY",
    "GATE_ESTIMATED_NOTIONAL_WITHIN_CAP",
    "GATE_PRE_QTY_0_1",
    "GATE_PRE_SIDE_BUY",
    "GATE_PRE_REDUCE_ONLY_FALSE",
    "GATE_STOP_ATTACH_PLAN_READY",
    "GATE_CLEANUP_PLAN_READY",
    "GATE_NO_DISCORD_TRIGGER",
    "GATE_NO_NOTION_TRIGGER",
    "GATE_NO_CRON_OR_BACKGROUND_AUTOMATION",
    "GATE_READINESS_CHECK_SIMULATED",
    "GATE_READINESS_NOT_VALIDATED_FOR_REAL_EXECUTION",
    # entry request template (18)
    "GATE_TEMPLATE_PRESENT",
    "GATE_TEMPLATE_PREVIEW_ONLY",
    "GATE_TEMPLATE_DRY_RUN_ONLY",
    "GATE_TEMPLATE_SEND_ALLOWED_FALSE",
    "GATE_TEMPLATE_ENDPOINT_CALLED_FALSE",
    "GATE_TEMPLATE_REAL_PAYLOAD_FALSE",
    "GATE_TEMPLATE_SIGNATURE_PRESENT_FALSE",
    "GATE_TEMPLATE_PRIVATE_HEADERS_EMPTY",
    "GATE_TEMPLATE_ENDPOINT_PATH_ORDER_CREATE",
    "GATE_TEMPLATE_BASE_URL_DEMO_ONLY",
    "GATE_TEMPLATE_SIDE_BUY",
    "GATE_TEMPLATE_QTY_0_1",
    "GATE_TEMPLATE_REDUCE_ONLY_FALSE",
    "GATE_TEMPLATE_CLOSE_ON_TRIGGER_FALSE",
    "GATE_TEMPLATE_POSITION_IDX_ZERO",
    "GATE_TEMPLATE_ORDER_TYPE_MARKET",
    "GATE_TEMPLATE_ORDER_LINK_ID_PREFIX_DOCUMENTED",
    "GATE_TEMPLATE_NO_SENDER_ADAPTER",
    # boundary dry-run (11)
    "GATE_ENTRY_SUCCESS_DOES_NOT_AUTO_ATTACH_STOP",
    "GATE_STOP_ATTACH_SEPARATE_MANUAL_AUTH",
    "GATE_BOUNDARY_STOP_LOSS_61_18",
    "GATE_BOUNDARY_TPSL_MODE_FULL",
    "GATE_BOUNDARY_SL_TRIGGER_BY_MARKPRICE",
    "GATE_CLEANUP_SEPARATE_MANUAL_AUTH",
    "GATE_NO_AUTO_CLEANUP_BOUNDARY",
    "GATE_NO_AUTO_EMERGENCY_CLOSE_BOUNDARY",
    "GATE_ENTRY_SUCCESS_WITHOUT_STOP_MANUAL_REVIEW",
    "GATE_STOP_ATTACH_FAIL_MANUAL_REVIEW",
    "GATE_CLEANUP_SEPARATE_BOUNDARY_ONLY",
    # failure dry-run (22)
    "GATE_MISSING_FLAG_FAIL_CLOSED",
    "GATE_TOKEN_MISMATCH_FAIL_CLOSED",
    "GATE_TOKEN_REUSED_FAIL_CLOSED",
    "GATE_READONLY_STALE_FAIL_CLOSED",
    "GATE_SOLUSDT_EXISTS_FAIL_CLOSED",
    "GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW",
    "GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED",
    "GATE_QTY_MISMATCH_FAIL_CLOSED",
    "GATE_SIDE_MISMATCH_FAIL_CLOSED",
    "GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED",
    "GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED",
    "GATE_SECRET_EMISSION_FAIL_CLOSED",
    "GATE_NO_AUTO_RETRY",
    "GATE_NO_AUTO_STOP_ATTACH_FAILURE",
    "GATE_NO_AUTO_CLEANUP_FAILURE",
    "GATE_NO_AUTO_EMERGENCY_CLOSE",
    "GATE_NO_AUTO_NEXT_STEP",
    "GATE_NO_BACKGROUND_LOOP",
    "GATE_NO_CRON",
    "GATE_NO_SCHEDULER",
    "GATE_FAILURE_NO_DISCORD_TRIGGER",
    "GATE_FAILURE_NO_NOTION_TRIGGER",
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
    "DemoTinyGuardedEntryManualAuthorizationDryRun",
    "TinyGuardedEntryManualAuthorizationDryRunResult",
]
