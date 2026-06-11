"""
src/demo_tiny_guarded_entry_real_permission_review.py
TASK-014AI: Guarded Entry Real Permission Review.

Permission-review-only module.  Reviews whether the future tiny entry
real permission review has the conditions it would need to proceed.
This module DOES NOT implement a real entry sender, does not send any
order, does not call /v5/order/create, does not call
/v5/position/trading-stop, does not read secrets, does not sign
anything, does not lift TASK-014L G20, and does not touch any
existing protected demo position.

Inputs: 18 upstream artifacts
  (10 baseline + AA lifecycle_summary + AB runner_design + AC
   runner_dry_run + AD guarded_design_review + AE guarded_entry_adapter
   + AF guarded_stop_adapter + AG guarded_cleanup_adapter + AH
   guarded_lifecycle_dry_run_summary).

Stages:
  stage_0_artifact_preflight
  stage_1_permission_review_scope
  stage_2_entry_real_permission_conditions
  stage_3_manual_authorization_review
  stage_4_entry_request_review_envelope
  stage_5_required_post_entry_protection_review
  stage_6_failure_and_abort_review
  stage_7_documentation_sync_review
  stage_8_final_entry_real_permission_review_verdict

Modes:
  permission_review_checklist          --- default
  permission_review_approval           --- --allow-review-approval
  real_entry_execution_guard           --- --allow-real-entry-execution
  fail_closed                          --- upstream failed

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
STAGE_1_PERMISSION_REVIEW_SCOPE                  = "stage_1_permission_review_scope"
STAGE_2_ENTRY_REAL_PERMISSION_CONDITIONS         = "stage_2_entry_real_permission_conditions"
STAGE_3_MANUAL_AUTHORIZATION_REVIEW              = "stage_3_manual_authorization_review"
STAGE_4_ENTRY_REQUEST_REVIEW_ENVELOPE            = "stage_4_entry_request_review_envelope"
STAGE_5_REQUIRED_POST_ENTRY_PROTECTION_REVIEW    = "stage_5_required_post_entry_protection_review"
STAGE_6_FAILURE_AND_ABORT_REVIEW                 = "stage_6_failure_and_abort_review"
STAGE_7_DOCUMENTATION_SYNC_REVIEW                = "stage_7_documentation_sync_review"
STAGE_8_FINAL_ENTRY_REAL_PERMISSION_REVIEW_VERDICT = "stage_8_final_entry_real_permission_review_verdict"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_PERMISSION_REVIEW_SCOPE,
    STAGE_2_ENTRY_REAL_PERMISSION_CONDITIONS,
    STAGE_3_MANUAL_AUTHORIZATION_REVIEW,
    STAGE_4_ENTRY_REQUEST_REVIEW_ENVELOPE,
    STAGE_5_REQUIRED_POST_ENTRY_PROTECTION_REVIEW,
    STAGE_6_FAILURE_AND_ABORT_REVIEW,
    STAGE_7_DOCUMENTATION_SYNC_REVIEW,
    STAGE_8_FINAL_ENTRY_REAL_PERMISSION_REVIEW_VERDICT,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_REVIEW_READY               = "TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY"
STATUS_REVIEW_READY_EXEC_DISABLED = (
    "TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_ENTRY_NOT_IMPL        = "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                = "FAIL_CLOSED"

MODE_PERMISSION_REVIEW_CHECKLIST  = "permission_review_checklist"
MODE_PERMISSION_REVIEW_APPROVAL   = "permission_review_approval"
MODE_REAL_ENTRY_EXECUTION_GUARD   = "real_entry_execution_guard"
MODE_FAIL_CLOSED                  = "fail_closed"

READINESS_CONCLUSION_NOT_EXECUTABLE = "DESIGN_REVIEW_READY_NOT_EXECUTABLE"


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


# ---------------------------------------------------------------------------
# Token patterns / confirmation flag documentation (never validated here)
# ---------------------------------------------------------------------------

ENTRY_TOKEN_PATTERN   = "CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SYMBOL"

ENTRY_CONFIRMATION_FLAGS: tuple[str, ...] = (
    "--i-understand-this-is-demo-real-execution",
    "--max-notional-usdt 10",
    "--expected-existing-position-count 5",
    "--expected-existing-symbols AIXBTUSDT,ENAUSDT,TIAUSDT,POLYXUSDT,EDUUSDT",
    "--expected-entry-symbol SOLUSDT",
    "--expected-entry-qty 0.1",
    "--expected-entry-side Buy",
    "--expected-reduce-only false",
)

ENTRY_REVIEW_ORDER_LINK_ID_PREFIXES: tuple[str, ...] = (
    "REVIEW_TINY_ENTRY_",
    "DRYRUN_TINY_ENTRY_",
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
# Entry permission expected values (documentation only)
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
REVIEW_EXPECTED_ESTIMATED_NOTIONAL  = 6.44     # qty * entry_reference
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
# General (29) + Scope (12) + Entry conditions (18) + Manual auth (11)
# + Entry envelope (16) + Post-entry protection (9) + Failure (20)
# + Documentation (5) + Execution guard (5) = 125
# ---------------------------------------------------------------------------

# General gates (29)
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
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO             = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                      = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG                  = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY  = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_MISSING                    = "selected_symbol_missing"
GATE_SELECTED_SYMBOL_NOT_SOLUSDT                = "selected_symbol_not_solusdt"
GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE  = "guarded_entry_adapter_status_unacceptable"
GATE_GUARDED_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE = "guarded_lifecycle_summary_status_unacceptable"
GATE_GUARDED_LIFECYCLE_SUMMARY_READINESS_EXECUTABLE = "guarded_lifecycle_summary_readiness_executable"
GATE_G20_POLICY_STILL_IN_PLACE                  = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                           = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                         = "no_secret_values_emitted_in_this_task"

# Scope gates (12)
GATE_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_ONLY  = "guarded_entry_real_permission_review_only"
GATE_PERMISSION_REVIEW_ONLY                     = "permission_review_only"
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

# Entry permission condition gates (18)
GATE_ENTRY_SYMBOL_SOLUSDT                       = "entry_symbol_solusdt"
GATE_ENTRY_CATEGORY_LINEAR                      = "entry_category_linear"
GATE_ENTRY_SIDE_BUY                             = "entry_side_buy"
GATE_ENTRY_QTY_0_1                              = "entry_qty_0_1"
GATE_ENTRY_QTY_STEP_0_1                         = "entry_qty_step_0_1"
GATE_ENTRY_MIN_ORDER_QTY_0_1                    = "entry_min_order_qty_0_1"
GATE_ENTRY_TICK_SIZE_0_01                       = "entry_tick_size_0_01"
GATE_ENTRY_ESTIMATED_NOTIONAL_WITHIN_CAP        = "entry_estimated_notional_within_cap"
GATE_ENTRY_MAX_NOTIONAL_USDT_10                 = "entry_max_notional_usdt_10"
GATE_ENTRY_POSITION_IDX_ZERO                    = "entry_position_idx_zero"
GATE_ENTRY_REDUCE_ONLY_FALSE                    = "entry_reduce_only_false"
GATE_ENTRY_ORDER_TYPE_MARKET                    = "entry_order_type_market"
GATE_ENTRY_DEMO_ENDPOINT_ONLY                   = "entry_demo_endpoint_only"
GATE_NO_EXISTING_SOLUSDT_POSITION               = "no_existing_solusdt_position_before_entry"
GATE_EXISTING_PROTECTED_POSITIONS_DOCUMENTED    = "existing_protected_positions_documented"
GATE_ENTRY_PROOF_STRENGTH_STRONG                = "entry_proof_strength_strong"
GATE_ENTRY_ACCOUNT_MODE_DEMO                    = "entry_account_mode_demo"
GATE_ENTRY_ENDPOINT_FAMILY_BYBIT_DEMO           = "entry_endpoint_family_bybit_demo"

# Manual authorization gates (11)
GATE_ENTRY_TOKEN_PATTERN_PRESENT                = "entry_token_pattern_present"
GATE_TOKEN_NOT_VALIDATED                        = "token_not_validated_in_this_task"
GATE_TOKEN_FORMAT_NOT_AUTHORIZATION             = "token_format_not_authorization"
GATE_CONFIRMATION_FLAGS_DOCUMENTED              = "confirmation_flags_documented"
GATE_CONFIRMATION_FLAGS_NOT_VALIDATED           = "confirmation_flags_not_validated"
GATE_SECOND_CONFIRMATION_REQUIRED               = "second_confirmation_required"
GATE_MANUAL_BOUNDARY_REQUIRED                   = "manual_boundary_required"
GATE_EXPECTED_ENTRY_SYMBOL_FLAG_DOCUMENTED      = "expected_entry_symbol_flag_documented"
GATE_EXPECTED_ENTRY_QTY_FLAG_DOCUMENTED         = "expected_entry_qty_flag_documented"
GATE_EXPECTED_ENTRY_SIDE_FLAG_DOCUMENTED        = "expected_entry_side_flag_documented"
GATE_EXPECTED_REDUCE_ONLY_FALSE_FLAG_DOCUMENTED = "expected_reduce_only_false_flag_documented"

# Entry request review envelope gates (16)
GATE_ENTRY_REVIEW_ENVELOPE_PRESENT              = "entry_review_envelope_present"
GATE_ENVELOPE_PREVIEW_ONLY                      = "envelope_preview_only"
GATE_ENVELOPE_SEND_ALLOWED_FALSE                = "envelope_send_allowed_false"
GATE_ENVELOPE_ENDPOINT_CALLED_FALSE             = "envelope_endpoint_called_false"
GATE_ENVELOPE_REAL_PAYLOAD_FALSE                = "envelope_real_payload_false"
GATE_ENVELOPE_SIGNATURE_PRESENT_FALSE           = "envelope_signature_present_false"
GATE_ENVELOPE_PRIVATE_HEADERS_EMPTY             = "envelope_private_headers_empty"
GATE_ENVELOPE_ENDPOINT_PATH_ORDER_CREATE        = "envelope_endpoint_path_ref_order_create"
GATE_ENVELOPE_BASE_URL_DEMO_ONLY                = "envelope_base_url_demo_only"
GATE_ENVELOPE_SIDE_BUY                          = "envelope_side_buy"
GATE_ENVELOPE_QTY_0_1                           = "envelope_qty_0_1"
GATE_ENVELOPE_REDUCE_ONLY_FALSE                 = "envelope_reduce_only_false"
GATE_ENVELOPE_CLOSE_ON_TRIGGER_FALSE            = "envelope_close_on_trigger_false"
GATE_ENVELOPE_POSITION_IDX_ZERO                 = "envelope_position_idx_zero"
GATE_ENVELOPE_ORDER_TYPE_MARKET                 = "envelope_order_type_market"
GATE_ENVELOPE_NO_SENDER_ADAPTER                 = "envelope_no_sender_adapter"

# Post-entry protection gates (9)
GATE_STOP_ATTACH_REQUIRED                       = "stop_attach_required_after_entry"
GATE_POST_ENTRY_STOP_LOSS_61_18                 = "post_entry_stop_loss_61_18"
GATE_POST_ENTRY_TPSL_MODE_FULL                  = "post_entry_tpsl_mode_full"
GATE_POST_ENTRY_SL_TRIGGER_BY_MARKPRICE         = "post_entry_sl_trigger_by_markprice"
GATE_STOP_ATTACH_SEPARATE_MANUAL_BOUNDARY       = "stop_attach_separate_manual_boundary"
GATE_NO_AUTOMATIC_STOP_ATTACH                   = "no_automatic_stop_attach"
GATE_CLEANUP_SEPARATE_MANUAL_BOUNDARY           = "cleanup_separate_manual_boundary"
GATE_NO_AUTOMATIC_CLEANUP                       = "no_automatic_cleanup"
GATE_ENTRY_SUCCESS_NO_STOP_REQUIRES_MANUAL      = "entry_success_without_stop_attach_requires_manual_review"

# Failure review gates (20)
GATE_REQUEST_REJECTED_FAIL_CLOSED               = "request_rejected_fail_closed"
GATE_READONLY_UNAVAILABLE_FAIL_CLOSED           = "readonly_unavailable_fail_closed"
GATE_SELECTED_SYMBOL_EXISTS_FAIL_CLOSED         = "selected_symbol_exists_fail_closed"
GATE_QTY_MISMATCH_FAIL_CLOSED                   = "qty_mismatch_fail_closed"
GATE_SIDE_MISMATCH_FAIL_CLOSED                  = "side_mismatch_fail_closed"
GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED           = "reduce_only_mismatch_fail_closed"
GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED          = "notional_cap_exceeded_fail_closed"
GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW  = "protected_position_mismatch_manual_review"
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
GATE_NO_DISCORD_TRIGGER                         = "no_discord_trigger"
GATE_NO_NOTION_TRIGGER                          = "no_notion_trigger"

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
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE,
    GATE_GUARDED_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE,
    GATE_GUARDED_LIFECYCLE_SUMMARY_READINESS_EXECUTABLE,
    GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyGuardedEntryRealPermissionReviewResult:
    """Read-only outcome of one guarded entry real permission review pass."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    permission_review_scope:                        dict[str, Any] = field(default_factory=dict)
    entry_real_permission_conditions:               dict[str, Any] = field(default_factory=dict)
    manual_authorization_review:                    dict[str, Any] = field(default_factory=dict)
    entry_request_review_envelope:                  dict[str, Any] = field(default_factory=dict)
    required_post_entry_protection_review:          dict[str, Any] = field(default_factory=dict)
    failure_and_abort_review:                       dict[str, Any] = field(default_factory=dict)
    documentation_sync_review:                      dict[str, Any] = field(default_factory=dict)
    audit_artifacts:                                dict[str, Any] = field(default_factory=dict)
    final_entry_real_permission_review_verdict:     dict[str, Any] = field(default_factory=dict)

    entry_token_pattern:          str = ENTRY_TOKEN_PATTERN

    review_approval_allowed:           bool = False
    real_entry_execution_requested:    bool = False
    real_execution_allowed:            bool = False
    real_entry_implemented:            bool = False
    guarded_entry_real_permission_review: bool = True
    permission_review_only:            bool = True
    entry_execution_included:          bool = False
    stop_execution_included:           bool = False
    cleanup_execution_included:        bool = False
    full_lifecycle_execution_included: bool = False
    current_task_real_execution_allowed: bool = False
    readiness_conclusion:              str  = READINESS_CONCLUSION_NOT_EXECUTABLE

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
    upstream_guarded_lifecycle_summary_readiness_conclusion: str = ""

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = "TASK-014AJ_guarded_entry_manual_authorization_design"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                          self.timestamp_utc,
            "timestamp_utc":                      self.timestamp_utc,
            "mode":                               self.mode,
            "selected_symbol":                    self.selected_symbol,
            "existing_position_symbols":          list(self.existing_position_symbols),
            "stages":                             {k: dict(v) for k, v in self.stages.items()},
            "stage_order":                        list(self.stage_order),
            "permission_review_scope":            dict(self.permission_review_scope),
            "entry_real_permission_conditions":   dict(self.entry_real_permission_conditions),
            "manual_authorization_review":        dict(self.manual_authorization_review),
            "entry_request_review_envelope":      dict(self.entry_request_review_envelope),
            "required_post_entry_protection_review": dict(self.required_post_entry_protection_review),
            "failure_and_abort_review":           dict(self.failure_and_abort_review),
            "documentation_sync_review":          dict(self.documentation_sync_review),
            "audit_artifacts":                    dict(self.audit_artifacts),
            "final_entry_real_permission_review_verdict":
                dict(self.final_entry_real_permission_review_verdict),
            "entry_token_pattern":                self.entry_token_pattern,
            "review_approval_allowed":            self.review_approval_allowed,
            "real_entry_execution_requested":     self.real_entry_execution_requested,
            "real_execution_allowed":             self.real_execution_allowed,
            "real_entry_implemented":             self.real_entry_implemented,
            "guarded_entry_real_permission_review": self.guarded_entry_real_permission_review,
            "permission_review_only":             self.permission_review_only,
            "entry_execution_included":           self.entry_execution_included,
            "stop_execution_included":            self.stop_execution_included,
            "cleanup_execution_included":         self.cleanup_execution_included,
            "full_lifecycle_execution_included":  self.full_lifecycle_execution_included,
            "current_task_real_execution_allowed": self.current_task_real_execution_allowed,
            "readiness_conclusion":               self.readiness_conclusion,
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
            "upstream_guarded_lifecycle_summary_readiness_conclusion":
                self.upstream_guarded_lifecycle_summary_readiness_conclusion,
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
# Guarded entry real permission review
# ---------------------------------------------------------------------------

class DemoTinyGuardedEntryRealPermissionReview:
    """
    Pure-computation guarded entry real permission review.  Reviews
    the future tiny entry real permission against 18 upstream
    artifacts.  Never opens a socket, reads no environment variables,
    performs no HMAC signing, and NEVER invokes the order-create or
    trading-stop endpoints.

    --allow-review-approval       --> status promoted to
        TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY_BUT_EXECUTION_DISABLED

    --allow-real-entry-execution  --> status fixed to
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
        symbol:                           str  = DEFAULT_SELECTED_SYMBOL,
        allow_review_approval:            bool = False,
        allow_real_entry_execution:       bool = False,
        _now:                             datetime | None = None,
    ) -> TinyGuardedEntryRealPermissionReviewResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_entry_execution:
            mode = MODE_REAL_ENTRY_EXECUTION_GUARD
        elif allow_review_approval:
            mode = MODE_PERMISSION_REVIEW_APPROVAL
        else:
            mode = MODE_PERMISSION_REVIEW_CHECKLIST

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
        guarded_lifecycle_readiness = _safe_str(
            (guarded_lifecycle_summary or {}).get("readiness_conclusion", "")
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

        if readonly_present and endpoint_family and endpoint_family != EXPECTED_ENDPOINT_FAMILY:
            blocked.append(GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO)
        if readonly_present and account_mode and account_mode != EXPECTED_ACCOUNT_MODE:
            blocked.append(GATE_ACCOUNT_MODE_NOT_DEMO)
        if readonly_present and proof_strength and proof_strength != EXPECTED_PROOF_STRENGTH:
            blocked.append(GATE_PROOF_STRENGTH_NOT_STRONG)
        if recon_present and position_details_source and position_details_source != EXPECTED_POSITION_DETAILS_SOURCE:
            blocked.append(GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY)

        if guarded_entry_present and guarded_entry_status and (
            guarded_entry_status not in ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES
        ):
            blocked.append(GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE)

        if guarded_lifecycle_present and guarded_lifecycle_status and (
            guarded_lifecycle_status not in ACCEPTABLE_GUARDED_LIFECYCLE_SUMMARY_STATUSES
        ):
            blocked.append(GATE_GUARDED_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE)

        if guarded_lifecycle_present and guarded_lifecycle_readiness and (
            guarded_lifecycle_readiness != READINESS_CONCLUSION_NOT_EXECUTABLE
        ):
            blocked.append(GATE_GUARDED_LIFECYCLE_SUMMARY_READINESS_EXECUTABLE)

        if not sym:
            blocked.append(GATE_SELECTED_SYMBOL_MISSING)
        elif sym != REVIEW_EXPECTED_SYMBOL:
            blocked.append(GATE_SELECTED_SYMBOL_NOT_SOLUSDT)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 18 upstream artifacts + runtime proof envelope + AE adapter status + AH lifecycle summary status / readiness.",
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
            "guarded_entry_adapter_status_acceptable":  sorted(
                ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES
            ),
            "guarded_stop_adapter_status_observed":     guarded_stop_status,
            "guarded_cleanup_adapter_status_observed":  guarded_cleanup_status,
            "guarded_lifecycle_summary_status_observed":  guarded_lifecycle_status,
            "guarded_lifecycle_summary_status_acceptable": sorted(
                ACCEPTABLE_GUARDED_LIFECYCLE_SUMMARY_STATUSES
            ),
            "guarded_lifecycle_summary_readiness_observed": guarded_lifecycle_readiness,
            "guarded_lifecycle_summary_readiness_expected": READINESS_CONCLUSION_NOT_EXECUTABLE,
            "selected_symbol":                          sym,
            "selected_symbol_expected":                 REVIEW_EXPECTED_SYMBOL,
            "current_task_real_execution_allowed":      False,
        }

        # ===============================================================
        # stage_1_permission_review_scope
        # ===============================================================
        permission_review_scope: dict[str, Any] = {
            "guarded_entry_real_permission_review": True,
            "permission_review_only":               True,
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
            "next_required_task":                   "TASK-014AJ_guarded_entry_manual_authorization_design",
            "scope_summary": (
                "TASK-014AI only reviews whether the future tiny entry "
                "real permission review has the conditions it would need. "
                "It does not implement a real entry sender, does not send "
                "any order, does not call any endpoint, does not attach "
                "any stop, does not modify any position, does not lift "
                "G20, and does not load any secret."
            ),
        }
        stages[STAGE_1_PERMISSION_REVIEW_SCOPE] = {
            "stage":   STAGE_1_PERMISSION_REVIEW_SCOPE,
            "summary": "Assert guarded entry real permission review scope (review-only).",
            "permission_review_scope":              permission_review_scope,
        }
        blocked.append(GATE_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_ONLY)
        blocked.append(GATE_PERMISSION_REVIEW_ONLY)
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
        # stage_2_entry_real_permission_conditions
        # ===============================================================
        sym_eff = sym or REVIEW_EXPECTED_SYMBOL
        existing_solusdt_present = any(s == REVIEW_EXPECTED_SYMBOL for s in existing_symbols)
        entry_real_permission_conditions: dict[str, Any] = {
            "symbol":                            sym_eff,
            "symbol_expected":                   REVIEW_EXPECTED_SYMBOL,
            "category":                          REVIEW_EXPECTED_CATEGORY,
            "entry_side":                        REVIEW_EXPECTED_ENTRY_SIDE,
            "qty":                               REVIEW_EXPECTED_QTY,
            "qty_step":                          REVIEW_EXPECTED_QTY_STEP,
            "min_order_qty":                     REVIEW_EXPECTED_MIN_ORDER_QTY,
            "tick_size":                         REVIEW_EXPECTED_TICK_SIZE,
            "entry_reference":                   REVIEW_EXPECTED_ENTRY_REFERENCE,
            "estimated_notional_usdt":           REVIEW_EXPECTED_ESTIMATED_NOTIONAL,
            "max_notional_usdt":                 REVIEW_EXPECTED_MAX_NOTIONAL_USDT,
            "estimated_notional_within_cap":     (
                REVIEW_EXPECTED_ESTIMATED_NOTIONAL <= REVIEW_EXPECTED_MAX_NOTIONAL_USDT
            ),
            "position_idx":                      REVIEW_EXPECTED_POSITION_IDX,
            "reduce_only":                       REVIEW_EXPECTED_REDUCE_ONLY,
            "order_type":                        REVIEW_EXPECTED_ORDER_TYPE,
            "demo_endpoint_only":                True,
            "no_existing_solusdt_position":      not existing_solusdt_present,
            "existing_protected_position_count": len(EXISTING_POSITION_SYMBOLS),
            "existing_protected_position_symbols": list(EXISTING_POSITION_SYMBOLS),
            "proof_strength":                    EXPECTED_PROOF_STRENGTH,
            "account_mode":                      EXPECTED_ACCOUNT_MODE,
            "endpoint_family":                   EXPECTED_ENDPOINT_FAMILY,
        }
        stages[STAGE_2_ENTRY_REAL_PERMISSION_CONDITIONS] = {
            "stage":   STAGE_2_ENTRY_REAL_PERMISSION_CONDITIONS,
            "summary": "Review the conditions a future tiny entry real permission would need.",
            "entry_real_permission_conditions":  entry_real_permission_conditions,
        }
        blocked.append(GATE_ENTRY_SYMBOL_SOLUSDT)
        blocked.append(GATE_ENTRY_CATEGORY_LINEAR)
        blocked.append(GATE_ENTRY_SIDE_BUY)
        blocked.append(GATE_ENTRY_QTY_0_1)
        blocked.append(GATE_ENTRY_QTY_STEP_0_1)
        blocked.append(GATE_ENTRY_MIN_ORDER_QTY_0_1)
        blocked.append(GATE_ENTRY_TICK_SIZE_0_01)
        blocked.append(GATE_ENTRY_ESTIMATED_NOTIONAL_WITHIN_CAP)
        blocked.append(GATE_ENTRY_MAX_NOTIONAL_USDT_10)
        blocked.append(GATE_ENTRY_POSITION_IDX_ZERO)
        blocked.append(GATE_ENTRY_REDUCE_ONLY_FALSE)
        blocked.append(GATE_ENTRY_ORDER_TYPE_MARKET)
        blocked.append(GATE_ENTRY_DEMO_ENDPOINT_ONLY)
        blocked.append(GATE_NO_EXISTING_SOLUSDT_POSITION)
        blocked.append(GATE_EXISTING_PROTECTED_POSITIONS_DOCUMENTED)
        blocked.append(GATE_ENTRY_PROOF_STRENGTH_STRONG)
        blocked.append(GATE_ENTRY_ACCOUNT_MODE_DEMO)
        blocked.append(GATE_ENTRY_ENDPOINT_FAMILY_BYBIT_DEMO)

        # ===============================================================
        # stage_3_manual_authorization_review
        # ===============================================================
        manual_authorization_review: dict[str, Any] = {
            "entry_token_pattern":                 ENTRY_TOKEN_PATTERN,
            "token_validated":                     False,
            "token_format_not_authorization":      True,
            "tokens_not_validated_in_this_task":   True,
            "entry_confirmation_flags":            list(ENTRY_CONFIRMATION_FLAGS),
            "confirmation_flags_documented":       True,
            "confirmation_flags_validated":        False,
            "second_confirmation_required":        True,
            "manual_boundary_required":            True,
            "expected_entry_symbol_flag":          "--expected-entry-symbol SOLUSDT",
            "expected_entry_qty_flag":             "--expected-entry-qty 0.1",
            "expected_entry_side_flag":            "--expected-entry-side Buy",
            "expected_reduce_only_false_flag":     "--expected-reduce-only false",
        }
        stages[STAGE_3_MANUAL_AUTHORIZATION_REVIEW] = {
            "stage":   STAGE_3_MANUAL_AUTHORIZATION_REVIEW,
            "summary": "Design the manual authorization rules (token pattern + confirmation flags) without validating any real token.",
            "manual_authorization_review":         manual_authorization_review,
        }
        blocked.append(GATE_ENTRY_TOKEN_PATTERN_PRESENT)
        blocked.append(GATE_TOKEN_NOT_VALIDATED)
        blocked.append(GATE_TOKEN_FORMAT_NOT_AUTHORIZATION)
        blocked.append(GATE_CONFIRMATION_FLAGS_DOCUMENTED)
        blocked.append(GATE_CONFIRMATION_FLAGS_NOT_VALIDATED)
        blocked.append(GATE_SECOND_CONFIRMATION_REQUIRED)
        blocked.append(GATE_MANUAL_BOUNDARY_REQUIRED)
        blocked.append(GATE_EXPECTED_ENTRY_SYMBOL_FLAG_DOCUMENTED)
        blocked.append(GATE_EXPECTED_ENTRY_QTY_FLAG_DOCUMENTED)
        blocked.append(GATE_EXPECTED_ENTRY_SIDE_FLAG_DOCUMENTED)
        blocked.append(GATE_EXPECTED_REDUCE_ONLY_FALSE_FLAG_DOCUMENTED)

        # ===============================================================
        # stage_4_entry_request_review_envelope
        # ===============================================================
        entry_request_review_envelope: dict[str, Any] = {
            "preview_only":                  True,
            "send_allowed":                  False,
            "endpoint_called":               False,
            "real_payload":                  False,
            "signature_present":             False,
            "private_headers":               [],
            "endpoint_path_ref":             ORDER_CREATE_PATH_REF,
            "base_url_ref":                  BASE_URL_DEMO_REF,
            "demo_endpoint_allowlist":       list(DEMO_ENDPOINT_ALLOWLIST),
            "live_endpoint_denylist":        list(LIVE_ENDPOINT_DENYLIST),
            "category":                      REVIEW_EXPECTED_CATEGORY,
            "symbol":                        sym_eff,
            "side":                          REVIEW_EXPECTED_ENTRY_SIDE,
            "orderType":                     REVIEW_EXPECTED_ORDER_TYPE,
            "qty":                           REVIEW_EXPECTED_QTY,
            "reduceOnly":                    REVIEW_EXPECTED_REDUCE_ONLY,
            "closeOnTrigger":                REVIEW_EXPECTED_CLOSE_ON_TRIGGER,
            "positionIdx":                   REVIEW_EXPECTED_POSITION_IDX,
            "orderLinkId_prefixes":          list(ENTRY_REVIEW_ORDER_LINK_ID_PREFIXES),
            "sender_adapter_invoked":        False,
            "no_sender_adapter":             True,
            "real_payload_conversion":       False,
        }
        stages[STAGE_4_ENTRY_REQUEST_REVIEW_ENVELOPE] = {
            "stage":   STAGE_4_ENTRY_REQUEST_REVIEW_ENVELOPE,
            "summary": "Future entry request review envelope (preview-only; never sent).",
            "entry_request_review_envelope":  entry_request_review_envelope,
        }
        blocked.append(GATE_ENTRY_REVIEW_ENVELOPE_PRESENT)
        blocked.append(GATE_ENVELOPE_PREVIEW_ONLY)
        blocked.append(GATE_ENVELOPE_SEND_ALLOWED_FALSE)
        blocked.append(GATE_ENVELOPE_ENDPOINT_CALLED_FALSE)
        blocked.append(GATE_ENVELOPE_REAL_PAYLOAD_FALSE)
        blocked.append(GATE_ENVELOPE_SIGNATURE_PRESENT_FALSE)
        blocked.append(GATE_ENVELOPE_PRIVATE_HEADERS_EMPTY)
        blocked.append(GATE_ENVELOPE_ENDPOINT_PATH_ORDER_CREATE)
        blocked.append(GATE_ENVELOPE_BASE_URL_DEMO_ONLY)
        blocked.append(GATE_ENVELOPE_SIDE_BUY)
        blocked.append(GATE_ENVELOPE_QTY_0_1)
        blocked.append(GATE_ENVELOPE_REDUCE_ONLY_FALSE)
        blocked.append(GATE_ENVELOPE_CLOSE_ON_TRIGGER_FALSE)
        blocked.append(GATE_ENVELOPE_POSITION_IDX_ZERO)
        blocked.append(GATE_ENVELOPE_ORDER_TYPE_MARKET)
        blocked.append(GATE_ENVELOPE_NO_SENDER_ADAPTER)

        # ===============================================================
        # stage_5_required_post_entry_protection_review
        # ===============================================================
        required_post_entry_protection_review: dict[str, Any] = {
            "stop_attach_required":                    True,
            "stop_loss":                               REVIEW_EXPECTED_STOP_LOSS,
            "tpsl_mode":                               REVIEW_EXPECTED_TPSL_MODE,
            "sl_trigger_by":                           REVIEW_EXPECTED_SL_TRIGGER_BY,
            "stop_attach_separate_manual_boundary":    True,
            "no_automatic_stop_attach":                True,
            "cleanup_separate_manual_boundary":        True,
            "no_automatic_cleanup":                    True,
            "entry_success_without_stop_requires_manual_review": True,
            "stop_attach_executed_in_this_task":       False,
            "cleanup_executed_in_this_task":           False,
        }
        stages[STAGE_5_REQUIRED_POST_ENTRY_PROTECTION_REVIEW] = {
            "stage":   STAGE_5_REQUIRED_POST_ENTRY_PROTECTION_REVIEW,
            "summary": "Review the post-entry stop-attach + cleanup manual boundaries (never executed).",
            "required_post_entry_protection_review":   required_post_entry_protection_review,
        }
        blocked.append(GATE_STOP_ATTACH_REQUIRED)
        blocked.append(GATE_POST_ENTRY_STOP_LOSS_61_18)
        blocked.append(GATE_POST_ENTRY_TPSL_MODE_FULL)
        blocked.append(GATE_POST_ENTRY_SL_TRIGGER_BY_MARKPRICE)
        blocked.append(GATE_STOP_ATTACH_SEPARATE_MANUAL_BOUNDARY)
        blocked.append(GATE_NO_AUTOMATIC_STOP_ATTACH)
        blocked.append(GATE_CLEANUP_SEPARATE_MANUAL_BOUNDARY)
        blocked.append(GATE_NO_AUTOMATIC_CLEANUP)
        blocked.append(GATE_ENTRY_SUCCESS_NO_STOP_REQUIRES_MANUAL)

        # ===============================================================
        # stage_6_failure_and_abort_review
        # ===============================================================
        failure_and_abort_review: dict[str, Any] = {
            "request_rejected":              "FAIL_CLOSED",
            "readonly_unavailable":          "FAIL_CLOSED",
            "selected_symbol_exists":        "FAIL_CLOSED",
            "qty_mismatch":                  "FAIL_CLOSED",
            "side_mismatch":                 "FAIL_CLOSED",
            "reduce_only_mismatch":          "FAIL_CLOSED",
            "notional_cap_exceeded":         "FAIL_CLOSED",
            "protected_position_mismatch":   "MANUAL_REVIEW_REQUIRED",
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
        stages[STAGE_6_FAILURE_AND_ABORT_REVIEW] = {
            "stage":   STAGE_6_FAILURE_AND_ABORT_REVIEW,
            "summary": "Future entry-real-permission failure / abort policy (no auto-progression of any kind).",
            "failure_and_abort_review":      failure_and_abort_review,
        }
        blocked.append(GATE_REQUEST_REJECTED_FAIL_CLOSED)
        blocked.append(GATE_READONLY_UNAVAILABLE_FAIL_CLOSED)
        blocked.append(GATE_SELECTED_SYMBOL_EXISTS_FAIL_CLOSED)
        blocked.append(GATE_QTY_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_SIDE_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED)
        blocked.append(GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW)
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
        blocked.append(GATE_NO_DISCORD_TRIGGER)
        blocked.append(GATE_NO_NOTION_TRIGGER)

        # ===============================================================
        # stage_7_documentation_sync_review
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
            "next_required_task":                 "TASK-014AJ_guarded_entry_manual_authorization_design",
            "documentation_only_plan":            True,
            "markdown_read_in_this_module":       False,
        }
        stages[STAGE_7_DOCUMENTATION_SYNC_REVIEW] = {
            "stage":   STAGE_7_DOCUMENTATION_SYNC_REVIEW,
            "summary": "Documentation sync plan (README / NEXT_ACTION / COMMAND_LOG / forbidden status / next_required_task).",
            "documentation_sync_review":          documentation_sync_review,
        }
        blocked.append(GATE_README_SYNC_REQUIRED)
        blocked.append(GATE_NEXT_ACTION_SYNC_REQUIRED)
        blocked.append(GATE_COMMAND_LOG_SYNC_REQUIRED)
        blocked.append(GATE_FORBIDDEN_STATUS_SYNC_REQUIRED)
        blocked.append(GATE_NEXT_REQUIRED_TASK_SYNC_REQUIRED)

        # ===============================================================
        # stage_8_final_entry_real_permission_review_verdict
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
        elif allow_review_approval:
            failed_stage = ""
            status_out = STATUS_REVIEW_READY_EXEC_DISABLED
            mode_out   = MODE_PERMISSION_REVIEW_APPROVAL
        else:
            failed_stage = ""
            status_out = STATUS_REVIEW_READY
            mode_out   = MODE_PERMISSION_REVIEW_CHECKLIST

        final_entry_real_permission_review_verdict: dict[str, Any] = {
            "review_approval_allowed":            allow_review_approval,
            "real_entry_execution_requested":     bool(allow_real_entry_execution),
            "real_execution_allowed":             False,
            "real_entry_implemented":             False,
            "guarded_entry_real_permission_review": True,
            "permission_review_only":             True,
            "entry_execution_included":           False,
            "stop_execution_included":            False,
            "cleanup_execution_included":         False,
            "full_lifecycle_execution_included":  False,
            "current_task_real_execution_allowed": False,
            "readiness_conclusion":               READINESS_CONCLUSION_NOT_EXECUTABLE,
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
            "next_required_task":                 "TASK-014AJ_guarded_entry_manual_authorization_design",
        }

        audit_artifacts: dict[str, Any] = {
            "permission_review_scope":             dict(permission_review_scope),
            "entry_real_permission_conditions":    dict(entry_real_permission_conditions),
            "manual_authorization_review":         dict(manual_authorization_review),
            "entry_request_review_envelope":       dict(entry_request_review_envelope),
            "required_post_entry_protection_review": dict(required_post_entry_protection_review),
            "failure_and_abort_review":            dict(failure_and_abort_review),
            "documentation_sync_review":           dict(documentation_sync_review),
            "final_entry_real_permission_review_verdict":
                dict(final_entry_real_permission_review_verdict),
            "response_status":                     "REVIEW_NOT_SENT",
            "response_from_exchange":              False,
            "sanitized":                           True,
            "no_secrets":                          True,
            "forbidden_log_fields":                list(FORBIDDEN_LOG_FIELDS),
        }

        stages[STAGE_8_FINAL_ENTRY_REAL_PERMISSION_REVIEW_VERDICT] = {
            "stage":   STAGE_8_FINAL_ENTRY_REAL_PERMISSION_REVIEW_VERDICT,
            "summary": "Final entry real permission review verdict + permanent execution guard.",
            "final_entry_real_permission_review_verdict":
                final_entry_real_permission_review_verdict,
        }

        return TinyGuardedEntryRealPermissionReviewResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            permission_review_scope=permission_review_scope,
            entry_real_permission_conditions=entry_real_permission_conditions,
            manual_authorization_review=manual_authorization_review,
            entry_request_review_envelope=entry_request_review_envelope,
            required_post_entry_protection_review=required_post_entry_protection_review,
            failure_and_abort_review=failure_and_abort_review,
            documentation_sync_review=documentation_sync_review,
            audit_artifacts=audit_artifacts,
            final_entry_real_permission_review_verdict=final_entry_real_permission_review_verdict,
            review_approval_allowed=allow_review_approval,
            real_entry_execution_requested=bool(allow_real_entry_execution),
            real_execution_allowed=False,
            real_entry_implemented=False,
            guarded_entry_real_permission_review=True,
            permission_review_only=True,
            entry_execution_included=False,
            stop_execution_included=False,
            cleanup_execution_included=False,
            full_lifecycle_execution_included=False,
            current_task_real_execution_allowed=False,
            readiness_conclusion=READINESS_CONCLUSION_NOT_EXECUTABLE,
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
            upstream_guarded_lifecycle_summary_readiness_conclusion=guarded_lifecycle_readiness,
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
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE,
            GATE_GUARDED_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE,
            GATE_GUARDED_LIFECYCLE_SUMMARY_READINESS_EXECUTABLE,
            GATE_SELECTED_SYMBOL_MISSING,
            GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
        }
        for g in blocked:
            if g in stage_0_set:
                return STAGE_0_ARTIFACT_PREFLIGHT
        return ""


__all__ = [
    "EXISTING_POSITION_SYMBOLS",
    "DEFAULT_SELECTED_SYMBOL",
    "ORDER_CREATE_PATH_REF",
    "TRADING_STOP_PATH_REF",
    "BASE_URL_DEMO_REF",
    "BASE_URL_LIVE_REF",
    "DEMO_ENDPOINT_ALLOWLIST",
    "LIVE_ENDPOINT_DENYLIST",
    "ENTRY_TOKEN_PATTERN",
    "ENTRY_CONFIRMATION_FLAGS",
    "ENTRY_REVIEW_ORDER_LINK_ID_PREFIXES",
    "ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES",
    "ACCEPTABLE_RUNNER_DESIGN_STATUSES",
    "ACCEPTABLE_RUNNER_DRY_RUN_STATUSES",
    "ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES",
    "ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES",
    "ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES",
    "ACCEPTABLE_GUARDED_CLEANUP_ADAPTER_STATUSES",
    "ACCEPTABLE_GUARDED_LIFECYCLE_SUMMARY_STATUSES",
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
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_PERMISSION_REVIEW_SCOPE",
    "STAGE_2_ENTRY_REAL_PERMISSION_CONDITIONS",
    "STAGE_3_MANUAL_AUTHORIZATION_REVIEW",
    "STAGE_4_ENTRY_REQUEST_REVIEW_ENVELOPE",
    "STAGE_5_REQUIRED_POST_ENTRY_PROTECTION_REVIEW",
    "STAGE_6_FAILURE_AND_ABORT_REVIEW",
    "STAGE_7_DOCUMENTATION_SYNC_REVIEW",
    "STAGE_8_FINAL_ENTRY_REAL_PERMISSION_REVIEW_VERDICT",
    "ALL_STAGES",
    "STATUS_REVIEW_READY",
    "STATUS_REVIEW_READY_EXEC_DISABLED",
    "STATUS_REAL_ENTRY_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_PERMISSION_REVIEW_CHECKLIST",
    "MODE_PERMISSION_REVIEW_APPROVAL",
    "MODE_REAL_ENTRY_EXECUTION_GUARD",
    "MODE_FAIL_CLOSED",
    # general (29)
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
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_MISSING",
    "GATE_SELECTED_SYMBOL_NOT_SOLUSDT",
    "GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE",
    "GATE_GUARDED_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE",
    "GATE_GUARDED_LIFECYCLE_SUMMARY_READINESS_EXECUTABLE",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # scope (12)
    "GATE_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_ONLY",
    "GATE_PERMISSION_REVIEW_ONLY",
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
    # entry conditions (18)
    "GATE_ENTRY_SYMBOL_SOLUSDT",
    "GATE_ENTRY_CATEGORY_LINEAR",
    "GATE_ENTRY_SIDE_BUY",
    "GATE_ENTRY_QTY_0_1",
    "GATE_ENTRY_QTY_STEP_0_1",
    "GATE_ENTRY_MIN_ORDER_QTY_0_1",
    "GATE_ENTRY_TICK_SIZE_0_01",
    "GATE_ENTRY_ESTIMATED_NOTIONAL_WITHIN_CAP",
    "GATE_ENTRY_MAX_NOTIONAL_USDT_10",
    "GATE_ENTRY_POSITION_IDX_ZERO",
    "GATE_ENTRY_REDUCE_ONLY_FALSE",
    "GATE_ENTRY_ORDER_TYPE_MARKET",
    "GATE_ENTRY_DEMO_ENDPOINT_ONLY",
    "GATE_NO_EXISTING_SOLUSDT_POSITION",
    "GATE_EXISTING_PROTECTED_POSITIONS_DOCUMENTED",
    "GATE_ENTRY_PROOF_STRENGTH_STRONG",
    "GATE_ENTRY_ACCOUNT_MODE_DEMO",
    "GATE_ENTRY_ENDPOINT_FAMILY_BYBIT_DEMO",
    # manual auth (11)
    "GATE_ENTRY_TOKEN_PATTERN_PRESENT",
    "GATE_TOKEN_NOT_VALIDATED",
    "GATE_TOKEN_FORMAT_NOT_AUTHORIZATION",
    "GATE_CONFIRMATION_FLAGS_DOCUMENTED",
    "GATE_CONFIRMATION_FLAGS_NOT_VALIDATED",
    "GATE_SECOND_CONFIRMATION_REQUIRED",
    "GATE_MANUAL_BOUNDARY_REQUIRED",
    "GATE_EXPECTED_ENTRY_SYMBOL_FLAG_DOCUMENTED",
    "GATE_EXPECTED_ENTRY_QTY_FLAG_DOCUMENTED",
    "GATE_EXPECTED_ENTRY_SIDE_FLAG_DOCUMENTED",
    "GATE_EXPECTED_REDUCE_ONLY_FALSE_FLAG_DOCUMENTED",
    # envelope (16)
    "GATE_ENTRY_REVIEW_ENVELOPE_PRESENT",
    "GATE_ENVELOPE_PREVIEW_ONLY",
    "GATE_ENVELOPE_SEND_ALLOWED_FALSE",
    "GATE_ENVELOPE_ENDPOINT_CALLED_FALSE",
    "GATE_ENVELOPE_REAL_PAYLOAD_FALSE",
    "GATE_ENVELOPE_SIGNATURE_PRESENT_FALSE",
    "GATE_ENVELOPE_PRIVATE_HEADERS_EMPTY",
    "GATE_ENVELOPE_ENDPOINT_PATH_ORDER_CREATE",
    "GATE_ENVELOPE_BASE_URL_DEMO_ONLY",
    "GATE_ENVELOPE_SIDE_BUY",
    "GATE_ENVELOPE_QTY_0_1",
    "GATE_ENVELOPE_REDUCE_ONLY_FALSE",
    "GATE_ENVELOPE_CLOSE_ON_TRIGGER_FALSE",
    "GATE_ENVELOPE_POSITION_IDX_ZERO",
    "GATE_ENVELOPE_ORDER_TYPE_MARKET",
    "GATE_ENVELOPE_NO_SENDER_ADAPTER",
    # post-entry protection (9)
    "GATE_STOP_ATTACH_REQUIRED",
    "GATE_POST_ENTRY_STOP_LOSS_61_18",
    "GATE_POST_ENTRY_TPSL_MODE_FULL",
    "GATE_POST_ENTRY_SL_TRIGGER_BY_MARKPRICE",
    "GATE_STOP_ATTACH_SEPARATE_MANUAL_BOUNDARY",
    "GATE_NO_AUTOMATIC_STOP_ATTACH",
    "GATE_CLEANUP_SEPARATE_MANUAL_BOUNDARY",
    "GATE_NO_AUTOMATIC_CLEANUP",
    "GATE_ENTRY_SUCCESS_NO_STOP_REQUIRES_MANUAL",
    # failure (20)
    "GATE_REQUEST_REJECTED_FAIL_CLOSED",
    "GATE_READONLY_UNAVAILABLE_FAIL_CLOSED",
    "GATE_SELECTED_SYMBOL_EXISTS_FAIL_CLOSED",
    "GATE_QTY_MISMATCH_FAIL_CLOSED",
    "GATE_SIDE_MISMATCH_FAIL_CLOSED",
    "GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED",
    "GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED",
    "GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW",
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
    "GATE_NO_DISCORD_TRIGGER",
    "GATE_NO_NOTION_TRIGGER",
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
    "DemoTinyGuardedEntryRealPermissionReview",
    "TinyGuardedEntryRealPermissionReviewResult",
]
