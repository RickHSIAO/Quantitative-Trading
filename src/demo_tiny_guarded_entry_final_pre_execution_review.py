"""
src/demo_tiny_guarded_entry_final_pre_execution_review.py
TASK-014AL: Guarded Entry Final Pre-execution Review.

Final pre-execution review-only module. This task is the LAST review before
any future real tiny entry. It re-reviews the repo / docs sync state,
re-reviews the runtime read-only proof envelope, re-reviews the entry order
parameters, re-reviews the manual authorization plan, re-reviews the
post-entry stop / cleanup manual boundary, re-reviews the forbidden
automation list, and re-reviews the failure / abort policy. This module
DOES NOT implement a real entry sender, does not send any order, does not
call /v5/order/create, does not call /v5/position/trading-stop, does not
read secrets, does not sign anything, does not lift TASK-014L G20, does
not validate any real token, does not treat any token as authorization,
and does not touch any existing protected demo position.

Inputs: 21 upstream artifacts (the 20 from TASK-014AK + AK's own
        entry_manual_authorization_dry_run output).

Stages:
  stage_0_artifact_preflight
  stage_1_final_pre_execution_review_scope
  stage_2_repo_and_docs_final_review
  stage_3_runtime_readonly_final_review
  stage_4_entry_order_parameters_final_review
  stage_5_manual_authorization_final_review
  stage_6_stop_cleanup_boundary_final_review
  stage_7_forbidden_automation_final_review
  stage_8_failure_and_abort_final_review
  stage_9_documentation_sync_review
  stage_10_final_pre_execution_review_verdict

Modes:
  final_pre_execution_review_checklist  --- default
  final_pre_execution_review_approval   --- --allow-review-approval
  real_entry_execution_guard            --- --allow-real-entry-execution
  fail_closed                           --- upstream failed

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

STAGE_0_ARTIFACT_PREFLIGHT                  = "stage_0_artifact_preflight"
STAGE_1_FINAL_PRE_EXECUTION_REVIEW_SCOPE    = "stage_1_final_pre_execution_review_scope"
STAGE_2_REPO_AND_DOCS_FINAL_REVIEW          = "stage_2_repo_and_docs_final_review"
STAGE_3_RUNTIME_READONLY_FINAL_REVIEW       = "stage_3_runtime_readonly_final_review"
STAGE_4_ENTRY_ORDER_PARAMETERS_FINAL_REVIEW = "stage_4_entry_order_parameters_final_review"
STAGE_5_MANUAL_AUTHORIZATION_FINAL_REVIEW   = "stage_5_manual_authorization_final_review"
STAGE_6_STOP_CLEANUP_BOUNDARY_FINAL_REVIEW  = "stage_6_stop_cleanup_boundary_final_review"
STAGE_7_FORBIDDEN_AUTOMATION_FINAL_REVIEW   = "stage_7_forbidden_automation_final_review"
STAGE_8_FAILURE_AND_ABORT_FINAL_REVIEW      = "stage_8_failure_and_abort_final_review"
STAGE_9_DOCUMENTATION_SYNC_REVIEW           = "stage_9_documentation_sync_review"
STAGE_10_FINAL_PRE_EXECUTION_REVIEW_VERDICT = "stage_10_final_pre_execution_review_verdict"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_FINAL_PRE_EXECUTION_REVIEW_SCOPE,
    STAGE_2_REPO_AND_DOCS_FINAL_REVIEW,
    STAGE_3_RUNTIME_READONLY_FINAL_REVIEW,
    STAGE_4_ENTRY_ORDER_PARAMETERS_FINAL_REVIEW,
    STAGE_5_MANUAL_AUTHORIZATION_FINAL_REVIEW,
    STAGE_6_STOP_CLEANUP_BOUNDARY_FINAL_REVIEW,
    STAGE_7_FORBIDDEN_AUTOMATION_FINAL_REVIEW,
    STAGE_8_FAILURE_AND_ABORT_FINAL_REVIEW,
    STAGE_9_DOCUMENTATION_SYNC_REVIEW,
    STAGE_10_FINAL_PRE_EXECUTION_REVIEW_VERDICT,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_REVIEW_READY               = "TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY"
STATUS_REVIEW_READY_EXEC_DISABLED = (
    "TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_ENTRY_NOT_IMPL        = "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                = "FAIL_CLOSED"

MODE_FINAL_REVIEW_CHECKLIST  = "final_pre_execution_review_checklist"
MODE_FINAL_REVIEW_APPROVAL   = "final_pre_execution_review_approval"
MODE_REAL_ENTRY_EXEC_GUARD   = "real_entry_execution_guard"
MODE_FAIL_CLOSED             = "fail_closed"

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

ACCEPTABLE_ENTRY_MANUAL_AUTH_DRY_RUN_STATUSES: frozenset[str] = frozenset({
    "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY",
    "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY_BUT_EXECUTION_DISABLED",
    "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED",
})


# ---------------------------------------------------------------------------
# Token patterns / sample token (sample is NEVER treated as authorization)
# ---------------------------------------------------------------------------

ENTRY_TOKEN_PATTERN = "CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT"
SAMPLE_TOKEN        = "CONFIRM_DEMO_TINY_ENTRY_20260612_SOLUSDT"

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

REVIEW_EXPECTED_SYMBOL              = "SOLUSDT"
REVIEW_EXPECTED_CATEGORY            = "linear"
REVIEW_EXPECTED_ENTRY_SIDE          = "Buy"
REVIEW_EXPECTED_QTY                 = 0.1
REVIEW_EXPECTED_QTY_STEP            = 0.1
REVIEW_EXPECTED_MIN_ORDER_QTY       = 0.1
REVIEW_EXPECTED_TICK_SIZE           = 0.01
REVIEW_EXPECTED_MAX_NOTIONAL_USDT   = 10.0
REVIEW_EXPECTED_ENTRY_REFERENCE     = 64.4
REVIEW_EXPECTED_ESTIMATED_NOTIONAL  = 6.44   # qty * entry_reference
REVIEW_EXPECTED_POSITION_IDX        = 0
REVIEW_EXPECTED_REDUCE_ONLY         = False
REVIEW_EXPECTED_CLOSE_ON_TRIGGER    = False
REVIEW_EXPECTED_ORDER_TYPE          = "Market"
REVIEW_EXPECTED_STOP_LOSS           = 61.18
REVIEW_EXPECTED_TPSL_MODE           = "Full"
REVIEW_EXPECTED_SL_TRIGGER_BY       = "MarkPrice"
REVIEW_EXPECTED_EXISTING_COUNT      = 5

FORBIDDEN_LOG_FIELDS: tuple[str, ...] = (
    "api_key_value", "api_secret_value", "signature_value",
    "auth_header_value", "sign_header_value", "bearer_token_value",
)


# ---------------------------------------------------------------------------
# Gate constants
# General (32) + Scope (14) + Repo/docs (12) + Runtime readonly (12)
# + Entry params (18) + Manual authorization (12) + Stop/cleanup (11)
# + Forbidden automation (14) + Failure (17) + Documentation (5)
# + Execution guard (5) = 152
# ---------------------------------------------------------------------------

# General gates (32)
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
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO               = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                        = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG                    = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY    = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_NOT_SOLUSDT                  = "selected_symbol_not_solusdt"
GATE_ENTRY_MANUAL_AUTH_DRY_RUN_STATUS_UNACCEPTABLE = "entry_manual_authorization_dry_run_status_unacceptable"
GATE_ENTRY_MANUAL_AUTH_DRY_RUN_READINESS_EXECUTABLE = "entry_manual_authorization_dry_run_readiness_executable"
GATE_DRY_RUN_AUTHORIZATION_RESULT_NOT_DOCUMENTED_ONLY = "dry_run_authorization_result_not_documented_only"
GATE_G20_POLICY_STILL_IN_PLACE                    = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                             = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                           = "no_secret_values_emitted_in_this_task"

# Scope gates (14)
GATE_FINAL_PRE_EXECUTION_REVIEW_ONLY              = "final_pre_execution_review_only"
GATE_ENTRY_EXECUTION_NOT_INCLUDED                 = "entry_execution_not_included"
GATE_STOP_EXECUTION_NOT_INCLUDED                  = "stop_execution_not_included"
GATE_CLEANUP_EXECUTION_NOT_INCLUDED               = "cleanup_execution_not_included"
GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED        = "full_lifecycle_execution_not_included"
GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE             = "real_entry_not_implemented_scope"
GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE             = "real_execution_not_allowed_scope"
GATE_SEND_NOT_ALLOWED_SCOPE                       = "send_not_allowed_scope"
GATE_ORDER_ENDPOINT_NOT_CALLED                    = "order_endpoint_not_called_in_this_task"
GATE_STOP_ENDPOINT_NOT_CALLED                     = "stop_endpoint_not_called_in_this_task"
GATE_NO_ENDPOINT_INVOKED                          = "no_endpoint_invoked_in_this_task"
GATE_NO_POSITION_MODIFIED_SCOPE                   = "no_position_modified_scope"
GATE_NO_SECRETS_LOADED                            = "no_secrets_loaded_in_this_task"
GATE_NO_G20_LIFT                                  = "no_g20_policy_lift_in_this_task"

# Repo/docs final review gates (12)
GATE_EXPECTED_COMMIT_HASH_DOCUMENTED              = "expected_commit_hash_documented"
GATE_CURRENT_COMMIT_HASH_DOCUMENTED_ONLY          = "current_commit_hash_documented_only"
GATE_COMMIT_HASH_MATCH_REQUIRED                   = "commit_hash_match_required"
GATE_README_CURRENT                               = "readme_current"
GATE_NEXT_ACTION_CURRENT                          = "next_action_current"
GATE_COMMAND_LOG_CURRENT                          = "command_log_current"
GATE_NO_UNCOMMITTED_TRACKED_CODE_CHANGES_REQUIRED = "no_uncommitted_tracked_code_changes_required"
GATE_AGENTS_UNTRACKED_ALLOWED                     = "agents_untracked_allowed"
GATE_DOCS_NEXT_REQUIRED_TASK_SYNCED               = "docs_next_required_task_synced"
GATE_FORBIDDEN_STATUS_SYNCED                      = "forbidden_status_synced"
GATE_NO_AUTO_GIT_COMMIT                           = "no_auto_git_commit"
GATE_NO_AUTO_GIT_PUSH                             = "no_auto_git_push"

# Runtime readonly final review gates (12)
GATE_READONLY_SNAPSHOT_PRESENT                    = "readonly_snapshot_present"
GATE_READONLY_TIMESTAMP_PRESENT                   = "readonly_timestamp_present"
GATE_RUNTIME_PROOF_STRENGTH_STRONG                = "runtime_proof_strength_strong"
GATE_RUNTIME_ACCOUNT_MODE_DEMO                    = "runtime_account_mode_demo"
GATE_RUNTIME_ENDPOINT_FAMILY_BYBIT_DEMO           = "runtime_endpoint_family_bybit_demo"
GATE_RUNTIME_POSITION_DETAILS_SOURCE_REAL_READONLY = "runtime_position_details_source_real_readonly"
GATE_EXISTING_POSITION_SYMBOLS_OBSERVED           = "existing_position_symbols_observed"
GATE_PROTECTED_EXPECTED_SYMBOLS_DOCUMENTED        = "protected_expected_symbols_documented"
GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW    = "protected_position_mismatch_manual_review"
GATE_SOLUSDT_ABSENT_BEFORE_ENTRY                  = "solusdt_absent_before_entry"
GATE_SOLUSDT_EXISTS_FAIL_CLOSED                   = "solusdt_already_exists_fail_closed"
GATE_READONLY_ONLY_NO_MODIFICATION                = "readonly_only_no_modification"

# Entry order parameters final review gates (18)
GATE_PARAM_SYMBOL_SOLUSDT                         = "param_symbol_solusdt"
GATE_PARAM_CATEGORY_LINEAR                        = "param_category_linear"
GATE_PARAM_SIDE_BUY                               = "param_side_buy"
GATE_PARAM_QTY_0_1                                = "param_qty_0_1"
GATE_PARAM_QTY_STEP_0_1                           = "param_qty_step_0_1"
GATE_PARAM_MIN_ORDER_QTY_0_1                      = "param_min_order_qty_0_1"
GATE_PARAM_ESTIMATED_NOTIONAL_6_44                = "param_estimated_notional_6_44"
GATE_PARAM_MAX_NOTIONAL_USDT_10                   = "param_max_notional_usdt_10"
GATE_PARAM_ESTIMATED_NOTIONAL_WITHIN_CAP          = "param_estimated_notional_within_cap"
GATE_PARAM_ORDER_TYPE_MARKET                      = "param_order_type_market"
GATE_PARAM_REDUCE_ONLY_FALSE                      = "param_reduce_only_false"
GATE_PARAM_CLOSE_ON_TRIGGER_FALSE                 = "param_close_on_trigger_false"
GATE_PARAM_POSITION_IDX_ZERO                      = "param_position_idx_zero"
GATE_PARAM_BASE_URL_DEMO_ONLY                     = "param_base_url_demo_only"
GATE_PARAM_ENDPOINT_PATH_ORDER_CREATE_REF_ONLY    = "param_endpoint_path_order_create_reference_only"
GATE_PARAM_PREVIEW_ONLY                           = "param_preview_only"
GATE_PARAM_REAL_PAYLOAD_FALSE                     = "param_real_payload_false"
GATE_PARAM_SEND_ALLOWED_FALSE                     = "param_send_allowed_false"

# Manual authorization final review gates (12)
GATE_AUTH_TOKEN_PATTERN_DOCUMENTED                = "auth_token_pattern_documented"
GATE_AUTH_SAMPLE_TOKEN_DOCUMENTED                 = "auth_sample_token_documented"
GATE_AUTH_TOKEN_NOT_VALIDATED                     = "auth_token_not_validated"
GATE_AUTH_REAL_TOKEN_NOT_VALIDATED                = "auth_real_token_not_validated"
GATE_AUTH_SAMPLE_TOKEN_NOT_AUTHORIZATION          = "auth_sample_token_not_authorization"
GATE_AUTH_13_REQUIRED_FLAGS_DOCUMENTED            = "auth_13_required_flags_documented"
GATE_AUTH_FLAGS_NOT_VALIDATED                     = "auth_flags_not_validated"
GATE_AUTH_DRY_RUN_RESULT_DOCUMENTED_ONLY          = "auth_dry_run_result_documented_only_not_authorized"
GATE_AUTH_RICK_EXPLICIT_AUTHORIZATION_REQUIRED    = "auth_rick_explicit_authorization_required"
GATE_AUTH_SECOND_CONFIRMATION_REQUIRED            = "auth_second_confirmation_required"
GATE_AUTH_INDEPENDENT_REVIEWER_RECOMMENDED        = "auth_independent_reviewer_recommended"
GATE_AUTH_FLAGS_COMPLETE_DOES_NOT_AUTHORIZE       = "auth_flags_complete_does_not_authorize_execution"

# Stop/cleanup boundary final review gates (11)
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

# Forbidden automation final review gates (14)
GATE_NO_CRON                                      = "no_cron"
GATE_NO_SCHEDULER                                 = "no_scheduler"
GATE_NO_BACKGROUND_LOOP                           = "no_background_loop"
GATE_NO_DISCORD_TRIGGER                           = "no_discord_trigger"
GATE_NO_NOTION_TRIGGER                            = "no_notion_trigger"
GATE_NO_WEBHOOK_TRIGGER                           = "no_webhook_trigger"
GATE_NO_AUTO_RETRY                                = "no_auto_retry"
GATE_NO_AUTO_NEXT_STEP                            = "no_auto_next_step"
GATE_NO_AUTO_STOP_ATTACH                          = "no_auto_stop_attach"
GATE_NO_AUTO_CLEANUP                              = "no_auto_cleanup"
GATE_NO_AUTO_EMERGENCY_CLOSE                      = "no_auto_emergency_close"
GATE_NO_BATCH_ORDER                               = "no_batch_order"
GATE_NO_CLOSE_ONLY_FALLBACK                       = "no_close_only_fallback"
GATE_NO_EMERGENCY_CLOSE_FALLBACK                  = "no_emergency_close_fallback"

# Failure final review gates (17)
GATE_MISSING_ARTIFACT_FAIL_CLOSED                 = "missing_artifact_fail_closed"
GATE_STALE_READONLY_FAIL_CLOSED                   = "stale_readonly_fail_closed"
GATE_COMMIT_MISMATCH_FAIL_CLOSED                  = "commit_mismatch_fail_closed"
GATE_DOCS_STALE_FAIL_CLOSED                       = "docs_stale_fail_closed"
GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW_FAIL = "protected_position_mismatch_manual_review_failure"
GATE_TOKEN_MISMATCH_FAIL_CLOSED                   = "token_mismatch_fail_closed"
GATE_TOKEN_REUSED_FAIL_CLOSED                     = "token_reused_fail_closed"
GATE_REQUIRED_FLAG_MISSING_FAIL_CLOSED            = "required_flag_missing_fail_closed"
GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED            = "notional_cap_exceeded_fail_closed"
GATE_QTY_MISMATCH_FAIL_CLOSED                     = "qty_mismatch_fail_closed"
GATE_SIDE_MISMATCH_FAIL_CLOSED                    = "side_mismatch_fail_closed"
GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED             = "reduce_only_mismatch_fail_closed"
GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED           = "live_endpoint_detected_fail_closed"
GATE_SECRET_EMISSION_DETECTED_FAIL_CLOSED         = "secret_emission_detected_fail_closed"
GATE_NETWORK_PRIMITIVE_DETECTED_FAIL_CLOSED       = "network_primitive_detected_fail_closed"
GATE_SENDER_ADAPTER_DETECTED_FAIL_CLOSED          = "sender_adapter_detected_fail_closed"
GATE_MANUAL_INTERVENTION_ONLY                     = "manual_intervention_only_on_failure"

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
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_ENTRY_MANUAL_AUTH_DRY_RUN_STATUS_UNACCEPTABLE,
    GATE_ENTRY_MANUAL_AUTH_DRY_RUN_READINESS_EXECUTABLE,
    GATE_DRY_RUN_AUTHORIZATION_RESULT_NOT_DOCUMENTED_ONLY,
    GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyGuardedEntryFinalPreExecutionReviewResult:
    """Read-only outcome of one guarded entry final pre-execution review."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    final_pre_execution_review_scope:        dict[str, Any] = field(default_factory=dict)
    repo_and_docs_final_review:              dict[str, Any] = field(default_factory=dict)
    runtime_readonly_final_review:           dict[str, Any] = field(default_factory=dict)
    entry_order_parameters_final_review:     dict[str, Any] = field(default_factory=dict)
    manual_authorization_final_review:       dict[str, Any] = field(default_factory=dict)
    stop_cleanup_boundary_final_review:      dict[str, Any] = field(default_factory=dict)
    forbidden_automation_final_review:       dict[str, Any] = field(default_factory=dict)
    failure_and_abort_final_review:          dict[str, Any] = field(default_factory=dict)
    documentation_sync_review:               dict[str, Any] = field(default_factory=dict)
    audit_artifacts:                         dict[str, Any] = field(default_factory=dict)
    final_pre_execution_review_verdict:      dict[str, Any] = field(default_factory=dict)

    entry_token_pattern:          str = ENTRY_TOKEN_PATTERN
    sample_token:                 str = SAMPLE_TOKEN

    review_approval_allowed:           bool = False
    real_entry_execution_requested:    bool = False
    real_execution_allowed:            bool = False
    real_entry_implemented:            bool = False
    guarded_entry_final_pre_execution_review: bool = True
    final_pre_execution_review_only:   bool = True
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
    upstream_entry_manual_auth_dry_run_readiness_conclusion: str = ""
    upstream_entry_manual_auth_dry_run_authorization_result: str = ""

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = "TASK-014AM_guarded_entry_real_execution_manual_approval_gate"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                                 self.timestamp_utc,
            "timestamp_utc":                             self.timestamp_utc,
            "mode":                                      self.mode,
            "selected_symbol":                           self.selected_symbol,
            "existing_position_symbols":                 list(self.existing_position_symbols),
            "stages":                                    {k: dict(v) for k, v in self.stages.items()},
            "stage_order":                               list(self.stage_order),
            "final_pre_execution_review_scope":          dict(self.final_pre_execution_review_scope),
            "repo_and_docs_final_review":                dict(self.repo_and_docs_final_review),
            "runtime_readonly_final_review":             dict(self.runtime_readonly_final_review),
            "entry_order_parameters_final_review":       dict(self.entry_order_parameters_final_review),
            "manual_authorization_final_review":         dict(self.manual_authorization_final_review),
            "stop_cleanup_boundary_final_review":        dict(self.stop_cleanup_boundary_final_review),
            "forbidden_automation_final_review":         dict(self.forbidden_automation_final_review),
            "failure_and_abort_final_review":            dict(self.failure_and_abort_final_review),
            "documentation_sync_review":                 dict(self.documentation_sync_review),
            "audit_artifacts":                           dict(self.audit_artifacts),
            "final_pre_execution_review_verdict":        dict(self.final_pre_execution_review_verdict),
            "entry_token_pattern":                       self.entry_token_pattern,
            "sample_token":                              self.sample_token,
            "review_approval_allowed":                   self.review_approval_allowed,
            "real_entry_execution_requested":            self.real_entry_execution_requested,
            "real_execution_allowed":                    self.real_execution_allowed,
            "real_entry_implemented":                    self.real_entry_implemented,
            "guarded_entry_final_pre_execution_review":  self.guarded_entry_final_pre_execution_review,
            "final_pre_execution_review_only":           self.final_pre_execution_review_only,
            "token_validation_simulated":                self.token_validation_simulated,
            "token_validated":                           self.token_validated,
            "real_token_validated":                      self.real_token_validated,
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
            "upstream_entry_manual_auth_dry_run_readiness_conclusion":
                self.upstream_entry_manual_auth_dry_run_readiness_conclusion,
            "upstream_entry_manual_auth_dry_run_authorization_result":
                self.upstream_entry_manual_auth_dry_run_authorization_result,
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
# Guarded entry final pre-execution review
# ---------------------------------------------------------------------------

class DemoTinyGuardedEntryFinalPreExecutionReview:
    """
    Pure-computation guarded entry final pre-execution review. Re-reviews
    21 upstream artifacts and emits the final pre-execution review verdict.
    Never opens a socket, reads no environment variables, performs no HMAC
    signing, never validates any real token, never treats any token (sample
    or otherwise) as authorization, never auto-commits / auto-pushes git,
    and NEVER invokes the order-create or trading-stop endpoints.

    --allow-review-approval      --> status promoted to
        TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY_BUT_EXECUTION_DISABLED

    --allow-real-entry-execution --> status fixed to
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
        symbol:                               str  = DEFAULT_SELECTED_SYMBOL,
        expected_commit_hash:                 str  = "",
        current_commit_hash:                  str  = "",
        allow_review_approval:                bool = False,
        allow_real_entry_execution:           bool = False,
        _now:                                 datetime | None = None,
    ) -> TinyGuardedEntryFinalPreExecutionReviewResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_entry_execution:
            mode = MODE_REAL_ENTRY_EXEC_GUARD
        elif allow_review_approval:
            mode = MODE_FINAL_REVIEW_APPROVAL
        else:
            mode = MODE_FINAL_REVIEW_CHECKLIST

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
        entry_auth_dry_run_readiness = _safe_str(
            (entry_manual_authorization_dry_run or {}).get("readiness_conclusion", "")
        )
        entry_auth_dry_run_result   = _safe_str(
            (entry_manual_authorization_dry_run or {}).get("dry_run_authorization_result", "")
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

        if readonly_present and endpoint_family and endpoint_family != EXPECTED_ENDPOINT_FAMILY:
            blocked.append(GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO)
        if readonly_present and account_mode and account_mode != EXPECTED_ACCOUNT_MODE:
            blocked.append(GATE_ACCOUNT_MODE_NOT_DEMO)
        if readonly_present and proof_strength and proof_strength != EXPECTED_PROOF_STRENGTH:
            blocked.append(GATE_PROOF_STRENGTH_NOT_STRONG)
        if recon_present and position_details_source and position_details_source != EXPECTED_POSITION_DETAILS_SOURCE:
            blocked.append(GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY)

        if entry_auth_dry_run_present and entry_auth_dry_run_status and (
            entry_auth_dry_run_status not in ACCEPTABLE_ENTRY_MANUAL_AUTH_DRY_RUN_STATUSES
        ):
            blocked.append(GATE_ENTRY_MANUAL_AUTH_DRY_RUN_STATUS_UNACCEPTABLE)

        if entry_auth_dry_run_present and entry_auth_dry_run_readiness and (
            entry_auth_dry_run_readiness != READINESS_CONCLUSION_NOT_EXECUTABLE
        ):
            blocked.append(GATE_ENTRY_MANUAL_AUTH_DRY_RUN_READINESS_EXECUTABLE)

        if entry_auth_dry_run_present and entry_auth_dry_run_result and (
            entry_auth_dry_run_result != DRY_RUN_AUTHORIZATION_RESULT
        ):
            blocked.append(GATE_DRY_RUN_AUTHORIZATION_RESULT_NOT_DOCUMENTED_ONLY)

        if sym and sym != REVIEW_EXPECTED_SYMBOL:
            blocked.append(GATE_SELECTED_SYMBOL_NOT_SOLUSDT)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 21 upstream artifacts + runtime proof envelope + entry manual authorization dry-run status / readiness / result.",
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
            "entry_manual_authorization_dry_run_status_acceptable": sorted(
                ACCEPTABLE_ENTRY_MANUAL_AUTH_DRY_RUN_STATUSES
            ),
            "entry_manual_authorization_dry_run_readiness_observed": entry_auth_dry_run_readiness,
            "entry_manual_authorization_dry_run_readiness_expected": READINESS_CONCLUSION_NOT_EXECUTABLE,
            "entry_manual_authorization_dry_run_authorization_result_observed": entry_auth_dry_run_result,
            "entry_manual_authorization_dry_run_authorization_result_expected": DRY_RUN_AUTHORIZATION_RESULT,
            "selected_symbol":                          sym,
            "selected_symbol_expected":                 REVIEW_EXPECTED_SYMBOL,
            "current_task_real_execution_allowed":      False,
        }

        # ===============================================================
        # stage_1_final_pre_execution_review_scope
        # ===============================================================
        final_pre_execution_review_scope: dict[str, Any] = {
            "guarded_entry_final_pre_execution_review": True,
            "final_pre_execution_review_only":      True,
            "entry_execution_included":             False,
            "stop_execution_included":              False,
            "cleanup_execution_included":           False,
            "full_lifecycle_execution_included":    False,
            "real_entry_implemented":               False,
            "real_execution_allowed":               False,
            "send_allowed":                         False,
            "order_endpoint_called":                False,
            "stop_endpoint_called":                 False,
            "no_endpoint_invoked_in_this_task":     True,
            "no_position_modified":                 True,
            "no_secrets_loaded":                    True,
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "next_required_task":                   "TASK-014AM_guarded_entry_real_execution_manual_approval_gate",
            "scope_summary": (
                "TASK-014AL only performs the final pre-execution review of the "
                "manual authorization, repo/docs sync, runtime readonly envelope, "
                "entry order parameters, stop/cleanup boundary, and forbidden "
                "automation list. It never validates any real token, never treats "
                "any token as authorization, never sends an order, never calls "
                "any endpoint, never modifies any position, never lifts G20, "
                "never loads any secret, and never auto-commits / auto-pushes git."
            ),
        }
        stages[STAGE_1_FINAL_PRE_EXECUTION_REVIEW_SCOPE] = {
            "stage":   STAGE_1_FINAL_PRE_EXECUTION_REVIEW_SCOPE,
            "summary": "Assert guarded entry final pre-execution review scope (review-only).",
            "final_pre_execution_review_scope":      final_pre_execution_review_scope,
        }
        blocked.append(GATE_FINAL_PRE_EXECUTION_REVIEW_ONLY)
        blocked.append(GATE_ENTRY_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_STOP_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_CLEANUP_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE)
        blocked.append(GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE)
        blocked.append(GATE_SEND_NOT_ALLOWED_SCOPE)
        blocked.append(GATE_ORDER_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_STOP_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_NO_ENDPOINT_INVOKED)
        blocked.append(GATE_NO_POSITION_MODIFIED_SCOPE)
        blocked.append(GATE_NO_SECRETS_LOADED)
        blocked.append(GATE_NO_G20_LIFT)

        # ===============================================================
        # stage_2_repo_and_docs_final_review
        # ===============================================================
        repo_and_docs_final_review: dict[str, Any] = {
            "expected_commit_hash":                  _safe_str(expected_commit_hash),
            "current_commit_hash":                   _safe_str(current_commit_hash),
            "commit_hash_match_required":            True,
            "readme_current":                        True,
            "next_action_current":                   True,
            "command_log_current":                   True,
            "no_uncommitted_tracked_code_changes_required": True,
            "agents_directory_untracked_allowed":    True,
            "docs_next_required_task_synced":        True,
            "forbidden_status_synced":               True,
            "readme_path_ref":                       "README.md",
            "next_action_path_ref":                  "docs/research/commands/NEXT_ACTION.md",
            "command_log_path_ref":                  "docs/research/commands/COMMAND_LOG.md",
            "no_auto_git_commit":                    True,
            "no_auto_git_push":                      True,
            "documentation_only_plan":               True,
        }
        stages[STAGE_2_REPO_AND_DOCS_FINAL_REVIEW] = {
            "stage":   STAGE_2_REPO_AND_DOCS_FINAL_REVIEW,
            "summary": "Repo / docs final review (commit hash documented only; no auto-commit / auto-push).",
            "repo_and_docs_final_review":            repo_and_docs_final_review,
        }
        blocked.append(GATE_EXPECTED_COMMIT_HASH_DOCUMENTED)
        blocked.append(GATE_CURRENT_COMMIT_HASH_DOCUMENTED_ONLY)
        blocked.append(GATE_COMMIT_HASH_MATCH_REQUIRED)
        blocked.append(GATE_README_CURRENT)
        blocked.append(GATE_NEXT_ACTION_CURRENT)
        blocked.append(GATE_COMMAND_LOG_CURRENT)
        blocked.append(GATE_NO_UNCOMMITTED_TRACKED_CODE_CHANGES_REQUIRED)
        blocked.append(GATE_AGENTS_UNTRACKED_ALLOWED)
        blocked.append(GATE_DOCS_NEXT_REQUIRED_TASK_SYNCED)
        blocked.append(GATE_FORBIDDEN_STATUS_SYNCED)
        blocked.append(GATE_NO_AUTO_GIT_COMMIT)
        blocked.append(GATE_NO_AUTO_GIT_PUSH)

        # ===============================================================
        # stage_3_runtime_readonly_final_review
        # ===============================================================
        readonly_timestamp = _safe_str((readonly_smoke or {}).get("timestamp_utc",
                                       (readonly_smoke or {}).get("timestamp", "")))
        solusdt_in_existing = REVIEW_EXPECTED_SYMBOL in existing_symbols
        if solusdt_in_existing:
            blocked.append(GATE_SOLUSDT_EXISTS_FAIL_CLOSED)

        runtime_readonly_final_review: dict[str, Any] = {
            "readonly_snapshot_present":             readonly_present,
            "readonly_timestamp_present":            bool(readonly_timestamp),
            "readonly_timestamp_observed":           readonly_timestamp,
            "proof_strength":                        proof_strength,
            "account_mode":                          account_mode,
            "endpoint_family":                       endpoint_family,
            "position_details_source":               position_details_source,
            "existing_position_symbols":             list(existing_symbols),
            "protected_expected_symbols":            list(EXISTING_POSITION_SYMBOLS),
            "protected_expected_symbols_doc_order":  list(EXISTING_POSITION_SYMBOLS_DOC_ORDER),
            "protected_position_mismatch_policy":    "MANUAL_REVIEW_REQUIRED",
            "solusdt_absent_before_entry":           (not solusdt_in_existing),
            "solusdt_exists_policy":                 "FAIL_CLOSED",
            "readonly_only_no_modification":         True,
        }
        stages[STAGE_3_RUNTIME_READONLY_FINAL_REVIEW] = {
            "stage":   STAGE_3_RUNTIME_READONLY_FINAL_REVIEW,
            "summary": "Runtime readonly final review (proof envelope, protected positions, SOLUSDT absent).",
            "runtime_readonly_final_review":         runtime_readonly_final_review,
        }
        blocked.append(GATE_READONLY_SNAPSHOT_PRESENT)
        blocked.append(GATE_READONLY_TIMESTAMP_PRESENT)
        blocked.append(GATE_RUNTIME_PROOF_STRENGTH_STRONG)
        blocked.append(GATE_RUNTIME_ACCOUNT_MODE_DEMO)
        blocked.append(GATE_RUNTIME_ENDPOINT_FAMILY_BYBIT_DEMO)
        blocked.append(GATE_RUNTIME_POSITION_DETAILS_SOURCE_REAL_READONLY)
        blocked.append(GATE_EXISTING_POSITION_SYMBOLS_OBSERVED)
        blocked.append(GATE_PROTECTED_EXPECTED_SYMBOLS_DOCUMENTED)
        blocked.append(GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW)
        blocked.append(GATE_SOLUSDT_ABSENT_BEFORE_ENTRY)
        blocked.append(GATE_READONLY_ONLY_NO_MODIFICATION)

        # ===============================================================
        # stage_4_entry_order_parameters_final_review
        # ===============================================================
        sym_eff = sym or REVIEW_EXPECTED_SYMBOL
        entry_order_parameters_final_review: dict[str, Any] = {
            "symbol":                                sym_eff,
            "category":                              REVIEW_EXPECTED_CATEGORY,
            "side":                                  REVIEW_EXPECTED_ENTRY_SIDE,
            "qty":                                   REVIEW_EXPECTED_QTY,
            "qty_step":                              REVIEW_EXPECTED_QTY_STEP,
            "min_order_qty":                         REVIEW_EXPECTED_MIN_ORDER_QTY,
            "estimated_notional_usdt":               REVIEW_EXPECTED_ESTIMATED_NOTIONAL,
            "max_notional_usdt":                     REVIEW_EXPECTED_MAX_NOTIONAL_USDT,
            "estimated_notional_within_cap": (
                REVIEW_EXPECTED_ESTIMATED_NOTIONAL <= REVIEW_EXPECTED_MAX_NOTIONAL_USDT
            ),
            "orderType":                             REVIEW_EXPECTED_ORDER_TYPE,
            "reduceOnly":                            REVIEW_EXPECTED_REDUCE_ONLY,
            "closeOnTrigger":                        REVIEW_EXPECTED_CLOSE_ON_TRIGGER,
            "positionIdx":                           REVIEW_EXPECTED_POSITION_IDX,
            "base_url_ref":                          BASE_URL_DEMO_REF,
            "endpoint_path_ref":                     ORDER_CREATE_PATH_REF,
            "demo_endpoint_allowlist":               list(DEMO_ENDPOINT_ALLOWLIST),
            "live_endpoint_denylist":                list(LIVE_ENDPOINT_DENYLIST),
            "preview_only":                          True,
            "real_payload":                          False,
            "send_allowed":                          False,
            "signature_present":                     False,
            "private_headers":                       [],
            "sender_adapter_invoked":                False,
        }
        stages[STAGE_4_ENTRY_ORDER_PARAMETERS_FINAL_REVIEW] = {
            "stage":   STAGE_4_ENTRY_ORDER_PARAMETERS_FINAL_REVIEW,
            "summary": "Entry order parameters final review (preview-only; never sent).",
            "entry_order_parameters_final_review":   entry_order_parameters_final_review,
        }
        blocked.append(GATE_PARAM_SYMBOL_SOLUSDT)
        blocked.append(GATE_PARAM_CATEGORY_LINEAR)
        blocked.append(GATE_PARAM_SIDE_BUY)
        blocked.append(GATE_PARAM_QTY_0_1)
        blocked.append(GATE_PARAM_QTY_STEP_0_1)
        blocked.append(GATE_PARAM_MIN_ORDER_QTY_0_1)
        blocked.append(GATE_PARAM_ESTIMATED_NOTIONAL_6_44)
        blocked.append(GATE_PARAM_MAX_NOTIONAL_USDT_10)
        blocked.append(GATE_PARAM_ESTIMATED_NOTIONAL_WITHIN_CAP)
        blocked.append(GATE_PARAM_ORDER_TYPE_MARKET)
        blocked.append(GATE_PARAM_REDUCE_ONLY_FALSE)
        blocked.append(GATE_PARAM_CLOSE_ON_TRIGGER_FALSE)
        blocked.append(GATE_PARAM_POSITION_IDX_ZERO)
        blocked.append(GATE_PARAM_BASE_URL_DEMO_ONLY)
        blocked.append(GATE_PARAM_ENDPOINT_PATH_ORDER_CREATE_REF_ONLY)
        blocked.append(GATE_PARAM_PREVIEW_ONLY)
        blocked.append(GATE_PARAM_REAL_PAYLOAD_FALSE)
        blocked.append(GATE_PARAM_SEND_ALLOWED_FALSE)

        # ===============================================================
        # stage_5_manual_authorization_final_review
        # ===============================================================
        manual_authorization_final_review: dict[str, Any] = {
            "token_pattern":                         ENTRY_TOKEN_PATTERN,
            "sample_token":                          SAMPLE_TOKEN,
            "token_validated":                       False,
            "real_token_validated":                  False,
            "sample_token_not_authorization":        True,
            "required_flags":                        list(REQUIRED_HUMAN_CONFIRMATION_FLAGS),
            "required_flag_count":                   len(REQUIRED_HUMAN_CONFIRMATION_FLAGS),
            "flags_validated":                       False,
            "flags_complete_does_not_authorize_execution": True,
            "dry_run_authorization_result":          DRY_RUN_AUTHORIZATION_RESULT,
            "rick_explicit_authorization_required":  True,
            "second_confirmation_required":          True,
            "independent_reviewer_recommended":      True,
        }
        stages[STAGE_5_MANUAL_AUTHORIZATION_FINAL_REVIEW] = {
            "stage":   STAGE_5_MANUAL_AUTHORIZATION_FINAL_REVIEW,
            "summary": "Manual authorization final review (token never validated; flags never validated).",
            "manual_authorization_final_review":     manual_authorization_final_review,
        }
        blocked.append(GATE_AUTH_TOKEN_PATTERN_DOCUMENTED)
        blocked.append(GATE_AUTH_SAMPLE_TOKEN_DOCUMENTED)
        blocked.append(GATE_AUTH_TOKEN_NOT_VALIDATED)
        blocked.append(GATE_AUTH_REAL_TOKEN_NOT_VALIDATED)
        blocked.append(GATE_AUTH_SAMPLE_TOKEN_NOT_AUTHORIZATION)
        blocked.append(GATE_AUTH_13_REQUIRED_FLAGS_DOCUMENTED)
        blocked.append(GATE_AUTH_FLAGS_NOT_VALIDATED)
        blocked.append(GATE_AUTH_DRY_RUN_RESULT_DOCUMENTED_ONLY)
        blocked.append(GATE_AUTH_RICK_EXPLICIT_AUTHORIZATION_REQUIRED)
        blocked.append(GATE_AUTH_SECOND_CONFIRMATION_REQUIRED)
        blocked.append(GATE_AUTH_INDEPENDENT_REVIEWER_RECOMMENDED)
        blocked.append(GATE_AUTH_FLAGS_COMPLETE_DOES_NOT_AUTHORIZE)

        # ===============================================================
        # stage_6_stop_cleanup_boundary_final_review
        # ===============================================================
        stop_cleanup_boundary_final_review: dict[str, Any] = {
            "stop_attach_required_after_entry":      True,
            "stop_attach_not_included_in_this_task": True,
            "stop_loss":                             REVIEW_EXPECTED_STOP_LOSS,
            "tpsl_mode":                             REVIEW_EXPECTED_TPSL_MODE,
            "sl_trigger_by":                         REVIEW_EXPECTED_SL_TRIGGER_BY,
            "cleanup_not_included_in_this_task":     True,
            "cleanup_separate_manual_boundary":      True,
            "no_automatic_stop_attach":              True,
            "no_automatic_cleanup":                  True,
            "no_automatic_emergency_close":          True,
            "entry_success_without_stop_attach_policy": "MANUAL_REVIEW_REQUIRED",
        }
        stages[STAGE_6_STOP_CLEANUP_BOUNDARY_FINAL_REVIEW] = {
            "stage":   STAGE_6_STOP_CLEANUP_BOUNDARY_FINAL_REVIEW,
            "summary": "Stop attach / cleanup manual boundary final review (separate manual authorizations).",
            "stop_cleanup_boundary_final_review":    stop_cleanup_boundary_final_review,
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

        # ===============================================================
        # stage_7_forbidden_automation_final_review
        # ===============================================================
        forbidden_automation_final_review: dict[str, Any] = {
            "no_cron":                               True,
            "no_scheduler":                          True,
            "no_background_loop":                    True,
            "no_discord_trigger":                    True,
            "no_notion_trigger":                     True,
            "no_webhook_trigger":                    True,
            "no_auto_retry":                         True,
            "no_auto_next_step":                     True,
            "no_auto_stop_attach":                   True,
            "no_auto_cleanup":                       True,
            "no_auto_emergency_close":               True,
            "no_batch_order":                        True,
            "no_close_only_fallback":                True,
            "no_emergency_close_fallback":           True,
            "manual_intervention_only":              True,
        }
        stages[STAGE_7_FORBIDDEN_AUTOMATION_FINAL_REVIEW] = {
            "stage":   STAGE_7_FORBIDDEN_AUTOMATION_FINAL_REVIEW,
            "summary": "Forbidden automation final review (no cron / scheduler / Discord / Notion / webhook / auto-retry / batch / fallback).",
            "forbidden_automation_final_review":     forbidden_automation_final_review,
        }
        blocked.append(GATE_NO_CRON)
        blocked.append(GATE_NO_SCHEDULER)
        blocked.append(GATE_NO_BACKGROUND_LOOP)
        blocked.append(GATE_NO_DISCORD_TRIGGER)
        blocked.append(GATE_NO_NOTION_TRIGGER)
        blocked.append(GATE_NO_WEBHOOK_TRIGGER)
        blocked.append(GATE_NO_AUTO_RETRY)
        blocked.append(GATE_NO_AUTO_NEXT_STEP)
        blocked.append(GATE_NO_AUTO_STOP_ATTACH)
        blocked.append(GATE_NO_AUTO_CLEANUP)
        blocked.append(GATE_NO_AUTO_EMERGENCY_CLOSE)
        blocked.append(GATE_NO_BATCH_ORDER)
        blocked.append(GATE_NO_CLOSE_ONLY_FALLBACK)
        blocked.append(GATE_NO_EMERGENCY_CLOSE_FALLBACK)

        # ===============================================================
        # stage_8_failure_and_abort_final_review
        # ===============================================================
        failure_and_abort_final_review: dict[str, Any] = {
            "missing_artifact":                      "FAIL_CLOSED",
            "stale_readonly":                        "FAIL_CLOSED",
            "commit_mismatch":                       "FAIL_CLOSED",
            "docs_stale":                            "FAIL_CLOSED",
            "solusdt_already_exists":                "FAIL_CLOSED",
            "protected_position_mismatch":           "MANUAL_REVIEW_REQUIRED",
            "token_mismatch":                        "FAIL_CLOSED",
            "token_reused":                          "FAIL_CLOSED",
            "required_flag_missing":                 "FAIL_CLOSED",
            "notional_cap_exceeded":                 "FAIL_CLOSED",
            "qty_mismatch":                          "FAIL_CLOSED",
            "side_mismatch":                         "FAIL_CLOSED",
            "reduce_only_mismatch":                  "FAIL_CLOSED",
            "live_endpoint_detected":                "FAIL_CLOSED",
            "secret_emission_detected":              "FAIL_CLOSED",
            "network_primitive_detected":            "FAIL_CLOSED",
            "sender_adapter_detected":               "FAIL_CLOSED",
            "manual_intervention_only":              True,
        }
        stages[STAGE_8_FAILURE_AND_ABORT_FINAL_REVIEW] = {
            "stage":   STAGE_8_FAILURE_AND_ABORT_FINAL_REVIEW,
            "summary": "Failure / abort policy final review (FAIL_CLOSED / MANUAL_REVIEW_REQUIRED only; no auto-progression).",
            "failure_and_abort_final_review":        failure_and_abort_final_review,
        }
        blocked.append(GATE_MISSING_ARTIFACT_FAIL_CLOSED)
        blocked.append(GATE_STALE_READONLY_FAIL_CLOSED)
        blocked.append(GATE_COMMIT_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_DOCS_STALE_FAIL_CLOSED)
        blocked.append(GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW_FAIL)
        blocked.append(GATE_TOKEN_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_TOKEN_REUSED_FAIL_CLOSED)
        blocked.append(GATE_REQUIRED_FLAG_MISSING_FAIL_CLOSED)
        blocked.append(GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED)
        blocked.append(GATE_QTY_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_SIDE_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_SECRET_EMISSION_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_NETWORK_PRIMITIVE_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_SENDER_ADAPTER_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_MANUAL_INTERVENTION_ONLY)

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
            "next_required_task":                    "TASK-014AM_guarded_entry_real_execution_manual_approval_gate",
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
        # stage_10_final_pre_execution_review_verdict
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
        elif allow_review_approval:
            failed_stage = ""
            status_out = STATUS_REVIEW_READY_EXEC_DISABLED
            mode_out   = MODE_FINAL_REVIEW_APPROVAL
        else:
            failed_stage = ""
            status_out = STATUS_REVIEW_READY
            mode_out   = MODE_FINAL_REVIEW_CHECKLIST

        final_pre_execution_review_verdict: dict[str, Any] = {
            "review_approval_allowed":               allow_review_approval,
            "real_entry_execution_requested":        bool(allow_real_entry_execution),
            "real_execution_allowed":                False,
            "real_entry_implemented":                False,
            "guarded_entry_final_pre_execution_review": True,
            "final_pre_execution_review_only":       True,
            "token_validation_simulated":            True,
            "token_validated":                       False,
            "real_token_validated":                  False,
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
            "next_required_task":                    "TASK-014AM_guarded_entry_real_execution_manual_approval_gate",
        }

        audit_artifacts: dict[str, Any] = {
            "final_pre_execution_review_scope":      dict(final_pre_execution_review_scope),
            "repo_and_docs_final_review":            dict(repo_and_docs_final_review),
            "runtime_readonly_final_review":         dict(runtime_readonly_final_review),
            "entry_order_parameters_final_review":   dict(entry_order_parameters_final_review),
            "manual_authorization_final_review":     dict(manual_authorization_final_review),
            "stop_cleanup_boundary_final_review":    dict(stop_cleanup_boundary_final_review),
            "forbidden_automation_final_review":     dict(forbidden_automation_final_review),
            "failure_and_abort_final_review":        dict(failure_and_abort_final_review),
            "documentation_sync_review":             dict(documentation_sync_review),
            "final_pre_execution_review_verdict":    dict(final_pre_execution_review_verdict),
            "response_status":                       "REVIEW_NOT_SENT",
            "response_from_exchange":                False,
            "sanitized":                             True,
            "no_secrets":                            True,
            "forbidden_log_fields":                  list(FORBIDDEN_LOG_FIELDS),
        }

        stages[STAGE_10_FINAL_PRE_EXECUTION_REVIEW_VERDICT] = {
            "stage":   STAGE_10_FINAL_PRE_EXECUTION_REVIEW_VERDICT,
            "summary": "Final pre-execution review verdict + permanent execution guard.",
            "final_pre_execution_review_verdict":    final_pre_execution_review_verdict,
        }

        return TinyGuardedEntryFinalPreExecutionReviewResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            final_pre_execution_review_scope=final_pre_execution_review_scope,
            repo_and_docs_final_review=repo_and_docs_final_review,
            runtime_readonly_final_review=runtime_readonly_final_review,
            entry_order_parameters_final_review=entry_order_parameters_final_review,
            manual_authorization_final_review=manual_authorization_final_review,
            stop_cleanup_boundary_final_review=stop_cleanup_boundary_final_review,
            forbidden_automation_final_review=forbidden_automation_final_review,
            failure_and_abort_final_review=failure_and_abort_final_review,
            documentation_sync_review=documentation_sync_review,
            audit_artifacts=audit_artifacts,
            final_pre_execution_review_verdict=final_pre_execution_review_verdict,
            review_approval_allowed=allow_review_approval,
            real_entry_execution_requested=bool(allow_real_entry_execution),
            real_execution_allowed=False,
            real_entry_implemented=False,
            guarded_entry_final_pre_execution_review=True,
            final_pre_execution_review_only=True,
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
            upstream_entry_manual_auth_dry_run_readiness_conclusion=entry_auth_dry_run_readiness,
            upstream_entry_manual_auth_dry_run_authorization_result=entry_auth_dry_run_result,
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
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_ENTRY_MANUAL_AUTH_DRY_RUN_STATUS_UNACCEPTABLE,
            GATE_ENTRY_MANUAL_AUTH_DRY_RUN_READINESS_EXECUTABLE,
            GATE_DRY_RUN_AUTHORIZATION_RESULT_NOT_DOCUMENTED_ONLY,
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
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_LIFECYCLE_STATUS",
    "EXPECTED_INSTRUMENT_CATEGORY",
    "REVIEW_EXPECTED_SYMBOL",
    "REVIEW_EXPECTED_CATEGORY",
    "REVIEW_EXPECTED_ENTRY_SIDE",
    "REVIEW_EXPECTED_QTY",
    "REVIEW_EXPECTED_QTY_STEP",
    "REVIEW_EXPECTED_MIN_ORDER_QTY",
    "REVIEW_EXPECTED_TICK_SIZE",
    "REVIEW_EXPECTED_MAX_NOTIONAL_USDT",
    "REVIEW_EXPECTED_ENTRY_REFERENCE",
    "REVIEW_EXPECTED_ESTIMATED_NOTIONAL",
    "REVIEW_EXPECTED_POSITION_IDX",
    "REVIEW_EXPECTED_REDUCE_ONLY",
    "REVIEW_EXPECTED_CLOSE_ON_TRIGGER",
    "REVIEW_EXPECTED_ORDER_TYPE",
    "REVIEW_EXPECTED_STOP_LOSS",
    "REVIEW_EXPECTED_TPSL_MODE",
    "REVIEW_EXPECTED_SL_TRIGGER_BY",
    "REVIEW_EXPECTED_EXISTING_COUNT",
    "FORBIDDEN_LOG_FIELDS",
    "READINESS_CONCLUSION_NOT_EXECUTABLE",
    "DRY_RUN_AUTHORIZATION_RESULT",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_FINAL_PRE_EXECUTION_REVIEW_SCOPE",
    "STAGE_2_REPO_AND_DOCS_FINAL_REVIEW",
    "STAGE_3_RUNTIME_READONLY_FINAL_REVIEW",
    "STAGE_4_ENTRY_ORDER_PARAMETERS_FINAL_REVIEW",
    "STAGE_5_MANUAL_AUTHORIZATION_FINAL_REVIEW",
    "STAGE_6_STOP_CLEANUP_BOUNDARY_FINAL_REVIEW",
    "STAGE_7_FORBIDDEN_AUTOMATION_FINAL_REVIEW",
    "STAGE_8_FAILURE_AND_ABORT_FINAL_REVIEW",
    "STAGE_9_DOCUMENTATION_SYNC_REVIEW",
    "STAGE_10_FINAL_PRE_EXECUTION_REVIEW_VERDICT",
    "ALL_STAGES",
    "STATUS_REVIEW_READY",
    "STATUS_REVIEW_READY_EXEC_DISABLED",
    "STATUS_REAL_ENTRY_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_FINAL_REVIEW_CHECKLIST",
    "MODE_FINAL_REVIEW_APPROVAL",
    "MODE_REAL_ENTRY_EXEC_GUARD",
    "MODE_FAIL_CLOSED",
    # general (32)
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
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_NOT_SOLUSDT",
    "GATE_ENTRY_MANUAL_AUTH_DRY_RUN_STATUS_UNACCEPTABLE",
    "GATE_ENTRY_MANUAL_AUTH_DRY_RUN_READINESS_EXECUTABLE",
    "GATE_DRY_RUN_AUTHORIZATION_RESULT_NOT_DOCUMENTED_ONLY",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # scope (14)
    "GATE_FINAL_PRE_EXECUTION_REVIEW_ONLY",
    "GATE_ENTRY_EXECUTION_NOT_INCLUDED",
    "GATE_STOP_EXECUTION_NOT_INCLUDED",
    "GATE_CLEANUP_EXECUTION_NOT_INCLUDED",
    "GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED",
    "GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE",
    "GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE",
    "GATE_SEND_NOT_ALLOWED_SCOPE",
    "GATE_ORDER_ENDPOINT_NOT_CALLED",
    "GATE_STOP_ENDPOINT_NOT_CALLED",
    "GATE_NO_ENDPOINT_INVOKED",
    "GATE_NO_POSITION_MODIFIED_SCOPE",
    "GATE_NO_SECRETS_LOADED",
    "GATE_NO_G20_LIFT",
    # repo/docs (12)
    "GATE_EXPECTED_COMMIT_HASH_DOCUMENTED",
    "GATE_CURRENT_COMMIT_HASH_DOCUMENTED_ONLY",
    "GATE_COMMIT_HASH_MATCH_REQUIRED",
    "GATE_README_CURRENT",
    "GATE_NEXT_ACTION_CURRENT",
    "GATE_COMMAND_LOG_CURRENT",
    "GATE_NO_UNCOMMITTED_TRACKED_CODE_CHANGES_REQUIRED",
    "GATE_AGENTS_UNTRACKED_ALLOWED",
    "GATE_DOCS_NEXT_REQUIRED_TASK_SYNCED",
    "GATE_FORBIDDEN_STATUS_SYNCED",
    "GATE_NO_AUTO_GIT_COMMIT",
    "GATE_NO_AUTO_GIT_PUSH",
    # runtime readonly (12)
    "GATE_READONLY_SNAPSHOT_PRESENT",
    "GATE_READONLY_TIMESTAMP_PRESENT",
    "GATE_RUNTIME_PROOF_STRENGTH_STRONG",
    "GATE_RUNTIME_ACCOUNT_MODE_DEMO",
    "GATE_RUNTIME_ENDPOINT_FAMILY_BYBIT_DEMO",
    "GATE_RUNTIME_POSITION_DETAILS_SOURCE_REAL_READONLY",
    "GATE_EXISTING_POSITION_SYMBOLS_OBSERVED",
    "GATE_PROTECTED_EXPECTED_SYMBOLS_DOCUMENTED",
    "GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW",
    "GATE_SOLUSDT_ABSENT_BEFORE_ENTRY",
    "GATE_SOLUSDT_EXISTS_FAIL_CLOSED",
    "GATE_READONLY_ONLY_NO_MODIFICATION",
    # entry params (18)
    "GATE_PARAM_SYMBOL_SOLUSDT",
    "GATE_PARAM_CATEGORY_LINEAR",
    "GATE_PARAM_SIDE_BUY",
    "GATE_PARAM_QTY_0_1",
    "GATE_PARAM_QTY_STEP_0_1",
    "GATE_PARAM_MIN_ORDER_QTY_0_1",
    "GATE_PARAM_ESTIMATED_NOTIONAL_6_44",
    "GATE_PARAM_MAX_NOTIONAL_USDT_10",
    "GATE_PARAM_ESTIMATED_NOTIONAL_WITHIN_CAP",
    "GATE_PARAM_ORDER_TYPE_MARKET",
    "GATE_PARAM_REDUCE_ONLY_FALSE",
    "GATE_PARAM_CLOSE_ON_TRIGGER_FALSE",
    "GATE_PARAM_POSITION_IDX_ZERO",
    "GATE_PARAM_BASE_URL_DEMO_ONLY",
    "GATE_PARAM_ENDPOINT_PATH_ORDER_CREATE_REF_ONLY",
    "GATE_PARAM_PREVIEW_ONLY",
    "GATE_PARAM_REAL_PAYLOAD_FALSE",
    "GATE_PARAM_SEND_ALLOWED_FALSE",
    # manual auth (12)
    "GATE_AUTH_TOKEN_PATTERN_DOCUMENTED",
    "GATE_AUTH_SAMPLE_TOKEN_DOCUMENTED",
    "GATE_AUTH_TOKEN_NOT_VALIDATED",
    "GATE_AUTH_REAL_TOKEN_NOT_VALIDATED",
    "GATE_AUTH_SAMPLE_TOKEN_NOT_AUTHORIZATION",
    "GATE_AUTH_13_REQUIRED_FLAGS_DOCUMENTED",
    "GATE_AUTH_FLAGS_NOT_VALIDATED",
    "GATE_AUTH_DRY_RUN_RESULT_DOCUMENTED_ONLY",
    "GATE_AUTH_RICK_EXPLICIT_AUTHORIZATION_REQUIRED",
    "GATE_AUTH_SECOND_CONFIRMATION_REQUIRED",
    "GATE_AUTH_INDEPENDENT_REVIEWER_RECOMMENDED",
    "GATE_AUTH_FLAGS_COMPLETE_DOES_NOT_AUTHORIZE",
    # stop/cleanup (11)
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
    # forbidden automation (14)
    "GATE_NO_CRON",
    "GATE_NO_SCHEDULER",
    "GATE_NO_BACKGROUND_LOOP",
    "GATE_NO_DISCORD_TRIGGER",
    "GATE_NO_NOTION_TRIGGER",
    "GATE_NO_WEBHOOK_TRIGGER",
    "GATE_NO_AUTO_RETRY",
    "GATE_NO_AUTO_NEXT_STEP",
    "GATE_NO_AUTO_STOP_ATTACH",
    "GATE_NO_AUTO_CLEANUP",
    "GATE_NO_AUTO_EMERGENCY_CLOSE",
    "GATE_NO_BATCH_ORDER",
    "GATE_NO_CLOSE_ONLY_FALLBACK",
    "GATE_NO_EMERGENCY_CLOSE_FALLBACK",
    # failure (17)
    "GATE_MISSING_ARTIFACT_FAIL_CLOSED",
    "GATE_STALE_READONLY_FAIL_CLOSED",
    "GATE_COMMIT_MISMATCH_FAIL_CLOSED",
    "GATE_DOCS_STALE_FAIL_CLOSED",
    "GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW_FAIL",
    "GATE_TOKEN_MISMATCH_FAIL_CLOSED",
    "GATE_TOKEN_REUSED_FAIL_CLOSED",
    "GATE_REQUIRED_FLAG_MISSING_FAIL_CLOSED",
    "GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED",
    "GATE_QTY_MISMATCH_FAIL_CLOSED",
    "GATE_SIDE_MISMATCH_FAIL_CLOSED",
    "GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED",
    "GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED",
    "GATE_SECRET_EMISSION_DETECTED_FAIL_CLOSED",
    "GATE_NETWORK_PRIMITIVE_DETECTED_FAIL_CLOSED",
    "GATE_SENDER_ADAPTER_DETECTED_FAIL_CLOSED",
    "GATE_MANUAL_INTERVENTION_ONLY",
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
    "DemoTinyGuardedEntryFinalPreExecutionReview",
    "TinyGuardedEntryFinalPreExecutionReviewResult",
]
