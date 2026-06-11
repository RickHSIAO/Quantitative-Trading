"""
src/demo_tiny_guarded_lifecycle_dry_run_summary.py
TASK-014AH: Guarded Tiny Lifecycle Dry-run Summary.

Pure-computation / summary-only adapter that consolidates 17 upstream
artifacts and produces a cross-adapter consistency review of the three
single-step guarded dry-run adapters (TASK-014AE entry-only, TASK-014AF
stop-attach-only, TASK-014AG cleanup-only).  This module DOES NOT
implement a real runner, does not execute entry, does not attach stop,
does not cleanup, does not call any endpoint, does not read secrets,
does not sign anything, does not lift TASK-014L G20.

The summary answers, in artifact form: do AE / AF / AG agree on the
selected symbol, category, qty, side polarity, stopLoss, cleanup
reduceOnly, positionIdx, orderType, max_notional cap?  Are the manual
confirmation token patterns and the per-adapter confirmation flag
matrices documented but never validated by this task?  Are the
execution-forbidden invariants (real_execution_allowed=False,
send_allowed=False, order_endpoint_called=False, stop_endpoint_called=
False, no_position_modified=True, no_secrets_loaded=True, g20_lifted=
False) consistent across all three adapters?  Is the future sequential
dry-run lifecycle plan (8 steps, manual_boundary every step,
auto_advance=False) documented?  Is the failure / abort policy
exhaustive?  Are the documentation-sync checkpoints (README /
NEXT_ACTION / COMMAND_LOG) flagged as required?

Stages:

  stage_0_artifact_preflight
      Validate 17 upstream artifacts + runtime proof envelope + AD
      guarded_runner_design_review readiness_conclusion is
      DESIGN_REVIEW_READY_NOT_EXECUTABLE + AE / AF / AG guarded dry-run
      adapter statuses are in their respective acceptable whitelists.

  stage_1_summary_scope
      Assert summary-only scope.  guarded_lifecycle_dry_run_summary=
      True, summary_only=True, entry_execution_included=False,
      stop_execution_included=False, cleanup_execution_included=False,
      full_lifecycle_execution_included=False, real_runner_implemented=
      False, real_execution_allowed=False, no endpoint invoked, no
      position modified, no secrets loaded, g20_lifted=False.

  stage_2_cross_adapter_consistency_matrix
      Compare AE / AF / AG on symbol / category / qty / entry side /
      expected long position / stopLoss / stopLoss < entry reference /
      cleanup side / reduceOnly / closeOnTrigger / positionIdx /
      orderType / max_notional_usdt.  Mismatch => FAIL_CLOSED.

  stage_3_manual_confirmation_matrix
      Document entry / stop / cleanup token patterns and per-adapter
      confirmation flag sets.  Tokens are NEVER validated by this task;
      confirmation flags are NEVER validated by this task.  Entry /
      stop / cleanup flag isolation is enforced.

  stage_4_execution_forbidden_matrix
      Aggregate per-adapter execution-forbidden invariants.  Any
      adapter showing real_execution_allowed / send_allowed /
      order_endpoint_called / stop_endpoint_called / secret emission /
      g20_lifted => FAIL_CLOSED.

  stage_5_sequential_dry_run_lifecycle_plan
      Generate 8-step future dry-run lifecycle plan (NOT executed):
      pre_entry_readonly_check / guarded_entry_only_dry_run /
      post_entry_readonly_plan / guarded_stop_attach_only_dry_run /
      post_stop_readonly_plan / guarded_cleanup_only_dry_run /
      post_cleanup_readonly_plan / final_audit.  Every step has
      manual_boundary_required=True, auto_advance=False, auto_retry=
      False, auto_cleanup=False, auto_emergency_close=False,
      endpoint_called=False, response_from_exchange=False.

  stage_6_failure_and_abort_summary
      Aggregate failure / abort policy (request rejected / readonly
      unavailable / selected symbol / qty / side / stopLoss /
      reduceOnly / partial cleanup / live endpoint / secret emission =>
      FAIL_CLOSED; protected position mismatch => MANUAL_REVIEW_
      REQUIRED).  No auto retry / next step / cleanup / emergency /
      background loop / cron / scheduler / Discord / Notion trigger.

  stage_7_documentation_sync_review
      Documentation sync plan only (no markdown read).  README /
      NEXT_ACTION / COMMAND_LOG / forbidden status / next_required_task
      flagged as required.

  stage_8_final_lifecycle_summary_verdict
      Resolve final status:
          TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY
              (default)
          TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY_BUT_EXECUTION_DISABLED
              (--allow-summary-approval)
          REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED
              (--allow-real-lifecycle-execution)
          FAIL_CLOSED                                       (hard-fail)
      Always emits real_runner_implemented=False,
      real_execution_allowed=False, send_allowed=False,
      order_endpoint_called=False, stop_endpoint_called=False,
      no_position_modified=True, no_secrets_loaded=True, g20_lifted=
      False, next_required_task=
      TASK-014AI_guarded_entry_real_permission_review.

Modes:
  summary_checklist                   --- default
  summary_dry_run_approval            --- --allow-summary-approval
  real_lifecycle_execution_guard      --- --allow-real-lifecycle-execution
  fail_closed                         --- upstream / consistency failed

This module DOES NOT (enforced by source-scan tests):
  * import urllib / requests / httpx / socket / http.client
  * read os.environ / dotenv
  * call HMAC / signing
  * import main / src.risk / BybitExecutor / pybit
  * import src.demo_new_entry_sender
  * import src.demo_close_only_sender
  * import src.demo_close_only_cleanup
  * import src.demo_emergency_close_sender
  * import src.demo_protected_new_entry_orchestrator
  * import src.demo_trading_stop_contract_probe
  * import src.demo_trading_stop_noop_probe_plan
  * import src.demo_tiny_position_lifecycle_mock
  * import src.demo_tiny_position_real_permission_gate
  * import src.demo_tiny_entry_permission_gate
  * import src.demo_tiny_stop_attach_permission_gate
  * import src.demo_tiny_cleanup_permission_gate
  * import src.demo_tiny_lifecycle_real_execution_summary
  * import src.demo_tiny_lifecycle_runner_design
  * import src.demo_tiny_lifecycle_runner_dry_run
  * import src.demo_tiny_lifecycle_guarded_runner_design_review
  * import src.demo_tiny_guarded_entry_dry_run_adapter
  * import src.demo_tiny_guarded_stop_attach_dry_run_adapter
  * import src.demo_tiny_guarded_cleanup_dry_run_adapter
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

STAGE_0_ARTIFACT_PREFLIGHT                   = "stage_0_artifact_preflight"
STAGE_1_SUMMARY_SCOPE                        = "stage_1_summary_scope"
STAGE_2_CROSS_ADAPTER_CONSISTENCY_MATRIX     = "stage_2_cross_adapter_consistency_matrix"
STAGE_3_MANUAL_CONFIRMATION_MATRIX           = "stage_3_manual_confirmation_matrix"
STAGE_4_EXECUTION_FORBIDDEN_MATRIX           = "stage_4_execution_forbidden_matrix"
STAGE_5_SEQUENTIAL_DRY_RUN_LIFECYCLE_PLAN    = "stage_5_sequential_dry_run_lifecycle_plan"
STAGE_6_FAILURE_AND_ABORT_SUMMARY            = "stage_6_failure_and_abort_summary"
STAGE_7_DOCUMENTATION_SYNC_REVIEW            = "stage_7_documentation_sync_review"
STAGE_8_FINAL_LIFECYCLE_SUMMARY_VERDICT      = "stage_8_final_lifecycle_summary_verdict"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_SUMMARY_SCOPE,
    STAGE_2_CROSS_ADAPTER_CONSISTENCY_MATRIX,
    STAGE_3_MANUAL_CONFIRMATION_MATRIX,
    STAGE_4_EXECUTION_FORBIDDEN_MATRIX,
    STAGE_5_SEQUENTIAL_DRY_RUN_LIFECYCLE_PLAN,
    STAGE_6_FAILURE_AND_ABORT_SUMMARY,
    STAGE_7_DOCUMENTATION_SYNC_REVIEW,
    STAGE_8_FINAL_LIFECYCLE_SUMMARY_VERDICT,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_SUMMARY_READY               = "TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY"
STATUS_SUMMARY_READY_EXEC_DISABLED = (
    "TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_LIFECYCLE_NOT_IMPL     = "REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                 = "FAIL_CLOSED"

MODE_SUMMARY_CHECKLIST             = "summary_checklist"
MODE_SUMMARY_DRY_RUN_APPROVAL      = "summary_dry_run_approval"
MODE_REAL_LIFECYCLE_EXECUTION_GUARD = "real_lifecycle_execution_guard"
MODE_FAIL_CLOSED                   = "fail_closed"

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


# ---------------------------------------------------------------------------
# Token patterns (documentation only --- never validated here)
# ---------------------------------------------------------------------------

ENTRY_TOKEN_PATTERN   = "CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SYMBOL"
STOP_TOKEN_PATTERN    = "CONFIRM_DEMO_TINY_STOP_ATTACH_YYYYMMDD_SYMBOL"
CLEANUP_TOKEN_PATTERN = "CONFIRM_DEMO_TINY_CLEANUP_YYYYMMDD_SYMBOL"


# Per-adapter confirmation flag sets (documentation only)
ENTRY_CONFIRMATION_FLAGS: tuple[str, ...] = (
    "--i-understand-this-is-demo-real-execution",
    "--max-notional-usdt 10",
    "--expected-existing-position-count 5",
    "--expected-existing-symbols AIXBTUSDT,ENAUSDT,TIAUSDT,POLYXUSDT,EDUUSDT",
)

STOP_CONFIRMATION_FLAGS: tuple[str, ...] = (
    "--i-understand-this-is-demo-real-execution",
    "--max-notional-usdt 10",
    "--expected-existing-position-count 5",
    "--expected-existing-symbols AIXBTUSDT,ENAUSDT,TIAUSDT,POLYXUSDT,EDUUSDT",
    "--expected-stop-loss-price 61.18",
    "--expected-trigger-by MarkPrice",
    "--expected-tpsl-mode Full",
)

CLEANUP_CONFIRMATION_FLAGS: tuple[str, ...] = (
    "--i-understand-this-is-demo-real-execution",
    "--max-notional-usdt 10",
    "--expected-existing-position-count 5",
    "--expected-existing-symbols AIXBTUSDT,ENAUSDT,TIAUSDT,POLYXUSDT,EDUUSDT",
    "--expected-cleanup-symbol SOLUSDT",
    "--expected-cleanup-qty 0.1",
    "--expected-cleanup-side Sell",
    "--expected-reduce-only true",
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
# Cross-adapter expected values (documentation only)
# ---------------------------------------------------------------------------

SUMMARY_EXPECTED_SYMBOL              = "SOLUSDT"
SUMMARY_EXPECTED_CATEGORY            = "linear"
SUMMARY_EXPECTED_QTY                 = 0.1
SUMMARY_EXPECTED_ENTRY_SIDE          = "Buy"
SUMMARY_EXPECTED_POSITION_SIDE_LONG  = "long"
SUMMARY_EXPECTED_STOP_LOSS           = 61.18
SUMMARY_EXPECTED_ENTRY_REFERENCE     = 64.4
SUMMARY_EXPECTED_CLEANUP_SIDE        = "Sell"
SUMMARY_EXPECTED_REDUCE_ONLY         = True
SUMMARY_EXPECTED_CLOSE_ON_TRIGGER    = False
SUMMARY_EXPECTED_POSITION_IDX        = 0
SUMMARY_EXPECTED_ORDER_TYPE          = "Market"
SUMMARY_EXPECTED_MAX_NOTIONAL_USDT   = 10.0
SUMMARY_EXPECTED_EXISTING_COUNT      = 5

FORBIDDEN_LOG_FIELDS: tuple[str, ...] = (
    "api_key_value", "api_secret_value", "signature_value",
    "auth_header_value", "sign_header_value", "bearer_token_value",
)


# ---------------------------------------------------------------------------
# Lifecycle plan steps (8 steps, never executed)
# ---------------------------------------------------------------------------

LIFECYCLE_PLAN_STEPS: tuple[str, ...] = (
    "pre_entry_readonly_check",
    "guarded_entry_only_dry_run",
    "post_entry_readonly_plan",
    "guarded_stop_attach_only_dry_run",
    "post_stop_readonly_plan",
    "guarded_cleanup_only_dry_run",
    "post_cleanup_readonly_plan",
    "final_audit",
)


# ---------------------------------------------------------------------------
# Gate constants
# General (30) + Scope (12) + Cross-adapter (15) + Manual confirmation (10)
# + Execution forbidden (16) + Lifecycle plan (9) + Failure summary (21)
# + Documentation (5) + Execution guard (5) = 123
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
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO             = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                      = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG                  = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY  = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_MISSING                    = "selected_symbol_missing"
GATE_SELECTED_SYMBOL_NOT_SOLUSDT                = "selected_symbol_not_solusdt"
GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE  = "guarded_design_review_status_unacceptable"
GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE = "guarded_design_review_readiness_executable"
GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE  = "guarded_entry_adapter_status_unacceptable"
GATE_GUARDED_STOP_ADAPTER_STATUS_UNACCEPTABLE   = "guarded_stop_adapter_status_unacceptable"
GATE_GUARDED_CLEANUP_ADAPTER_STATUS_UNACCEPTABLE = "guarded_cleanup_adapter_status_unacceptable"
GATE_G20_POLICY_STILL_IN_PLACE                  = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                           = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                         = "no_secret_values_emitted_in_this_task"

# Scope gates (12)
GATE_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_ONLY     = "guarded_lifecycle_dry_run_summary_only"
GATE_SUMMARY_ONLY                               = "summary_only"
GATE_ENTRY_EXECUTION_NOT_INCLUDED               = "entry_execution_not_included"
GATE_STOP_EXECUTION_NOT_INCLUDED                = "stop_execution_not_included"
GATE_CLEANUP_EXECUTION_NOT_INCLUDED             = "cleanup_execution_not_included"
GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED      = "full_lifecycle_execution_not_included"
GATE_REAL_RUNNER_NOT_IMPLEMENTED                = "real_runner_not_implemented_in_this_task"
GATE_REAL_EXECUTION_NOT_ALLOWED                 = "real_execution_not_allowed_in_this_task"
GATE_NO_ENDPOINT_INVOKED                        = "no_endpoint_invoked_in_this_task"
GATE_NO_POSITION_MODIFIED_SCOPE                 = "no_position_modified_scope"
GATE_NO_SECRETS_LOADED                          = "no_secrets_loaded_in_this_task"
GATE_NO_G20_LIFT                                = "no_g20_policy_lift_in_this_task"

# Cross-adapter gates (15)
GATE_CROSS_SYMBOL_CONSISTENT                    = "cross_adapter_symbol_consistent_solusdt"
GATE_CROSS_CATEGORY_CONSISTENT                  = "cross_adapter_category_consistent_linear"
GATE_CROSS_QTY_CONSISTENT                       = "cross_adapter_qty_consistent_0_1"
GATE_CROSS_ENTRY_SIDE_BUY                       = "cross_adapter_entry_side_buy"
GATE_CROSS_EXPECTED_LONG_POSITION               = "cross_adapter_expected_long_position"
GATE_CROSS_STOP_EXPECTED_LONG                   = "cross_adapter_stop_expected_long"
GATE_CROSS_CLEANUP_PRE_CLEANUP_LONG             = "cross_adapter_cleanup_pre_cleanup_long"
GATE_CROSS_STOP_LOSS_61_18                      = "cross_adapter_stop_loss_61_18"
GATE_CROSS_STOP_LOSS_BELOW_ENTRY                = "cross_adapter_stop_loss_below_entry_reference"
GATE_CROSS_CLEANUP_SIDE_SELL                    = "cross_adapter_cleanup_side_sell"
GATE_CROSS_CLEANUP_REDUCE_ONLY_TRUE             = "cross_adapter_cleanup_reduce_only_true"
GATE_CROSS_CLEANUP_CLOSE_ON_TRIGGER_FALSE       = "cross_adapter_cleanup_close_on_trigger_false"
GATE_CROSS_POSITION_IDX_ZERO                    = "cross_adapter_position_idx_zero"
GATE_CROSS_ORDER_TYPE_MARKET                    = "cross_adapter_order_type_market"
GATE_CROSS_MAX_NOTIONAL_10                      = "cross_adapter_max_notional_10"

# Manual confirmation gates (10)
GATE_ENTRY_TOKEN_PATTERN_PRESENT                = "entry_token_pattern_present"
GATE_STOP_TOKEN_PATTERN_PRESENT                 = "stop_token_pattern_present"
GATE_CLEANUP_TOKEN_PATTERN_PRESENT              = "cleanup_token_pattern_present"
GATE_TOKENS_NOT_VALIDATED                       = "tokens_not_validated_in_this_task"
GATE_TOKEN_FORMAT_NOT_AUTHORIZATION             = "token_format_not_authorization"
GATE_CONFIRMATION_FLAGS_DOCUMENTED              = "confirmation_flags_documented"
GATE_CONFIRMATION_FLAGS_NOT_VALIDATED           = "confirmation_flags_not_validated"
GATE_ENTRY_FLAGS_ISOLATED                       = "entry_flags_isolated_from_stop_cleanup_execution"
GATE_STOP_FLAGS_ISOLATED                        = "stop_flags_isolated_from_entry_cleanup_execution"
GATE_CLEANUP_FLAGS_ISOLATED                     = "cleanup_flags_isolated_from_entry_stop_execution"

# Execution forbidden gates (16)
GATE_AE_REAL_EXECUTION_FALSE                    = "ae_real_execution_allowed_false"
GATE_AF_REAL_EXECUTION_FALSE                    = "af_real_execution_allowed_false"
GATE_AG_REAL_EXECUTION_FALSE                    = "ag_real_execution_allowed_false"
GATE_AE_SEND_ALLOWED_FALSE                      = "ae_send_allowed_false"
GATE_AF_SEND_ALLOWED_FALSE                      = "af_send_allowed_false"
GATE_AG_SEND_ALLOWED_FALSE                      = "ag_send_allowed_false"
GATE_AE_ORDER_ENDPOINT_NOT_CALLED               = "ae_order_endpoint_called_false"
GATE_AF_ORDER_ENDPOINT_NOT_CALLED               = "af_order_endpoint_called_false"
GATE_AG_ORDER_ENDPOINT_NOT_CALLED               = "ag_order_endpoint_called_false"
GATE_AE_STOP_ENDPOINT_NOT_CALLED                = "ae_stop_endpoint_called_false"
GATE_AF_STOP_ENDPOINT_NOT_CALLED                = "af_stop_endpoint_called_false"
GATE_AG_STOP_ENDPOINT_NOT_CALLED                = "ag_stop_endpoint_called_false"
GATE_NO_POSITION_MODIFIED_ACROSS_ADAPTERS       = "no_position_modified_across_adapters"
GATE_NO_SECRETS_LOADED_ACROSS_ADAPTERS          = "no_secrets_loaded_across_adapters"
GATE_NO_LIVE_ENDPOINT_ACROSS_ADAPTERS           = "no_live_endpoint_across_adapters"
GATE_G20_NOT_LIFTED_ACROSS_ADAPTERS             = "g20_not_lifted_across_adapters"

# Lifecycle plan gates (9)
GATE_LIFECYCLE_PLAN_PRESENT                     = "lifecycle_plan_present"
GATE_LIFECYCLE_PLAN_EIGHT_STEPS                 = "lifecycle_plan_has_eight_steps"
GATE_LIFECYCLE_MANUAL_BOUNDARY_EVERY_STEP       = "lifecycle_manual_boundary_every_step"
GATE_LIFECYCLE_AUTO_ADVANCE_FALSE               = "lifecycle_auto_advance_false"
GATE_LIFECYCLE_AUTO_RETRY_FALSE                 = "lifecycle_auto_retry_false"
GATE_LIFECYCLE_AUTO_CLEANUP_FALSE               = "lifecycle_auto_cleanup_false"
GATE_LIFECYCLE_AUTO_EMERGENCY_CLOSE_FALSE       = "lifecycle_auto_emergency_close_false"
GATE_LIFECYCLE_ENDPOINT_CALLED_FALSE_EVERY_STEP = "lifecycle_endpoint_called_false_every_step"
GATE_LIFECYCLE_RESPONSE_FROM_EXCHANGE_FALSE     = "lifecycle_response_from_exchange_false_every_step"

# Failure summary gates (21)
GATE_REQUEST_REJECTED_FAIL_CLOSED               = "request_rejected_fail_closed"
GATE_READONLY_UNAVAILABLE_FAIL_CLOSED           = "readonly_unavailable_fail_closed"
GATE_SELECTED_SYMBOL_MISMATCH_FAIL_CLOSED       = "selected_symbol_mismatch_fail_closed"
GATE_QTY_MISMATCH_FAIL_CLOSED                   = "qty_mismatch_fail_closed"
GATE_SIDE_MISMATCH_FAIL_CLOSED                  = "side_mismatch_fail_closed"
GATE_STOP_LOSS_INVALID_FAIL_CLOSED              = "stop_loss_invalid_fail_closed"
GATE_REDUCE_ONLY_INVALID_FAIL_CLOSED            = "reduce_only_invalid_fail_closed"
GATE_PARTIAL_EXECUTION_FAIL_CLOSED              = "partial_execution_fail_closed"
GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW  = "protected_position_mismatch_manual_review"
GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED         = "live_endpoint_detected_fail_closed"
GATE_SECRET_EMISSION_FAIL_CLOSED                = "secret_emission_fail_closed"
GATE_NO_AUTO_RETRY                              = "no_auto_retry"
GATE_NO_AUTO_NEXT_STEP                          = "no_auto_next_step"
GATE_NO_AUTO_CLEANUP                            = "no_auto_cleanup"
GATE_NO_AUTO_SECOND_CLEANUP                     = "no_auto_second_cleanup"
GATE_NO_AUTO_EMERGENCY_CLOSE                    = "no_auto_emergency_close"
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
GATE_REAL_LIFECYCLE_EXECUTION_NOT_IMPL          = "real_lifecycle_execution_not_implemented"
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
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE,
    GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE,
    GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE,
    GATE_GUARDED_STOP_ADAPTER_STATUS_UNACCEPTABLE,
    GATE_GUARDED_CLEANUP_ADAPTER_STATUS_UNACCEPTABLE,
    GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyGuardedLifecycleDryRunSummaryResult:
    """Read-only outcome of one guarded lifecycle dry-run summary pass."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    summary_scope:                          dict[str, Any] = field(default_factory=dict)
    cross_adapter_consistency_matrix:       dict[str, Any] = field(default_factory=dict)
    manual_confirmation_matrix:             dict[str, Any] = field(default_factory=dict)
    execution_forbidden_matrix:             dict[str, Any] = field(default_factory=dict)
    sequential_dry_run_lifecycle_plan:      dict[str, Any] = field(default_factory=dict)
    failure_and_abort_summary:              dict[str, Any] = field(default_factory=dict)
    documentation_sync_review:              dict[str, Any] = field(default_factory=dict)
    audit_artifacts:                        dict[str, Any] = field(default_factory=dict)
    final_lifecycle_summary_verdict:        dict[str, Any] = field(default_factory=dict)

    entry_token_pattern:          str = ENTRY_TOKEN_PATTERN
    stop_token_pattern:           str = STOP_TOKEN_PATTERN
    cleanup_token_pattern:        str = CLEANUP_TOKEN_PATTERN

    # Summary gating flags.
    summary_dry_run_approval_allowed:    bool = False
    real_lifecycle_execution_requested:  bool = False
    real_execution_allowed:              bool = False
    real_runner_implemented:             bool = False
    guarded_lifecycle_dry_run_summary:   bool = True
    summary_only:                        bool = True
    entry_execution_included:            bool = False
    stop_execution_included:             bool = False
    cleanup_execution_included:          bool = False
    full_lifecycle_execution_included:   bool = False
    current_task_real_execution_allowed: bool = False
    readiness_conclusion:                str  = READINESS_CONCLUSION_NOT_EXECUTABLE

    # Safety invariants.
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
    upstream_lifecycle_summary_status:     str = ""
    upstream_runner_design_status:         str = ""
    upstream_runner_dry_run_status:        str = ""
    upstream_guarded_design_review_status: str = ""
    upstream_guarded_design_review_readiness_conclusion: str = ""
    upstream_guarded_entry_adapter_status:   str = ""
    upstream_guarded_stop_adapter_status:    str = ""
    upstream_guarded_cleanup_adapter_status: str = ""

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = "TASK-014AI_guarded_entry_real_permission_review"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                       self.timestamp_utc,
            "timestamp_utc":                   self.timestamp_utc,
            "mode":                            self.mode,
            "selected_symbol":                 self.selected_symbol,
            "existing_position_symbols":       list(self.existing_position_symbols),
            "stages":                          {k: dict(v) for k, v in self.stages.items()},
            "stage_order":                     list(self.stage_order),
            "summary_scope":                   dict(self.summary_scope),
            "cross_adapter_consistency_matrix": dict(self.cross_adapter_consistency_matrix),
            "manual_confirmation_matrix":      dict(self.manual_confirmation_matrix),
            "execution_forbidden_matrix":      dict(self.execution_forbidden_matrix),
            "sequential_dry_run_lifecycle_plan": dict(self.sequential_dry_run_lifecycle_plan),
            "failure_and_abort_summary":       dict(self.failure_and_abort_summary),
            "documentation_sync_review":       dict(self.documentation_sync_review),
            "audit_artifacts":                 dict(self.audit_artifacts),
            "final_lifecycle_summary_verdict": dict(self.final_lifecycle_summary_verdict),
            "entry_token_pattern":             self.entry_token_pattern,
            "stop_token_pattern":              self.stop_token_pattern,
            "cleanup_token_pattern":           self.cleanup_token_pattern,
            "summary_dry_run_approval_allowed":  self.summary_dry_run_approval_allowed,
            "real_lifecycle_execution_requested": self.real_lifecycle_execution_requested,
            "real_execution_allowed":          self.real_execution_allowed,
            "real_runner_implemented":         self.real_runner_implemented,
            "guarded_lifecycle_dry_run_summary": self.guarded_lifecycle_dry_run_summary,
            "summary_only":                    self.summary_only,
            "entry_execution_included":        self.entry_execution_included,
            "stop_execution_included":         self.stop_execution_included,
            "cleanup_execution_included":      self.cleanup_execution_included,
            "full_lifecycle_execution_included": self.full_lifecycle_execution_included,
            "current_task_real_execution_allowed": self.current_task_real_execution_allowed,
            "readiness_conclusion":            self.readiness_conclusion,
            "order_create_path_ref":           self.order_create_path_ref,
            "trading_stop_path_ref":           self.trading_stop_path_ref,
            "base_url_ref":                    self.base_url_ref,
            "send_allowed":                    self.send_allowed,
            "order_endpoint_called":           self.order_endpoint_called,
            "stop_endpoint_called":            self.stop_endpoint_called,
            "no_position_modified":            self.no_position_modified,
            "no_live_endpoint":                self.no_live_endpoint,
            "no_orders_sent":                  self.no_orders_sent,
            "no_batch_order":                  self.no_batch_order,
            "no_close_only_path":              self.no_close_only_path,
            "emergency_close_invoked":         self.emergency_close_invoked,
            "leverage_mutated":                self.leverage_mutated,
            "transfer_invoked":                self.transfer_invoked,
            "no_secrets_loaded":               self.no_secrets_loaded,
            "secret_value_observed":           self.secret_value_observed,
            "g20_policy_still_in_place":       self.g20_policy_still_in_place,
            "g20_lifted":                      self.g20_lifted,
            "existing_positions_touched":      list(self.existing_positions_touched),
            "upstream_lifecycle_summary_status":     self.upstream_lifecycle_summary_status,
            "upstream_runner_design_status":         self.upstream_runner_design_status,
            "upstream_runner_dry_run_status":        self.upstream_runner_dry_run_status,
            "upstream_guarded_design_review_status": self.upstream_guarded_design_review_status,
            "upstream_guarded_design_review_readiness_conclusion":
                self.upstream_guarded_design_review_readiness_conclusion,
            "upstream_guarded_entry_adapter_status":   self.upstream_guarded_entry_adapter_status,
            "upstream_guarded_stop_adapter_status":    self.upstream_guarded_stop_adapter_status,
            "upstream_guarded_cleanup_adapter_status": self.upstream_guarded_cleanup_adapter_status,
            "blocked_gates":                   list(self.blocked_gates),
            "failed_stage":                    self.failed_stage,
            "status":                          self.status,
            "next_required_task":              self.next_required_task,
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
# Guarded lifecycle dry-run summary
# ---------------------------------------------------------------------------

class DemoTinyGuardedLifecycleDryRunSummary:
    """
    Pure-computation guarded lifecycle dry-run summary.  Consolidates 17
    upstream artifacts (10 baseline + AA lifecycle summary + AB runner
    design + AC runner dry-run + AD guarded design review + AE guarded
    entry dry-run adapter + AF guarded stop-attach dry-run adapter + AG
    guarded cleanup dry-run adapter) and emits a summary-only artifact
    answering: do the three single-step guarded dry-run adapters agree
    on symbol / category / qty / side polarity / stopLoss /
    reduceOnly / positionIdx / orderType / max_notional cap, manual
    confirmation matrix, execution-forbidden invariants, future
    sequential dry-run lifecycle plan, failure/abort policy, and
    documentation sync checkpoints?

    Holds no network client, reads no environment variables, opens no
    socket, performs no HMAC signing, and NEVER invokes the
    order-create or trading-stop endpoints.  Does not implement,
    design, or describe a real lifecycle runner that could be executed.

    --allow-summary-approval --> status promoted to
        TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY_BUT_EXECUTION_DISABLED.

    --allow-real-lifecycle-execution --> status fixed to
        REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED  (no socket opened).
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
        symbol:                           str  = DEFAULT_SELECTED_SYMBOL,
        allow_summary_approval:           bool = False,
        allow_real_lifecycle_execution:   bool = False,
        _now:                             datetime | None = None,
    ) -> TinyGuardedLifecycleDryRunSummaryResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_lifecycle_execution:
            mode = MODE_REAL_LIFECYCLE_EXECUTION_GUARD
        elif allow_summary_approval:
            mode = MODE_SUMMARY_DRY_RUN_APPROVAL
        else:
            mode = MODE_SUMMARY_CHECKLIST

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
        guarded_review_readiness    = _safe_str(
            (guarded_design_review or {}).get("readiness_conclusion", "")
        )
        guarded_entry_status        = _safe_str((guarded_entry_adapter or {}).get("status", ""))
        guarded_stop_status         = _safe_str((guarded_stop_adapter or {}).get("status", ""))
        guarded_cleanup_status      = _safe_str((guarded_cleanup_adapter or {}).get("status", ""))

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

        if readonly_present and endpoint_family and endpoint_family != EXPECTED_ENDPOINT_FAMILY:
            blocked.append(GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO)
        if readonly_present and account_mode and account_mode != EXPECTED_ACCOUNT_MODE:
            blocked.append(GATE_ACCOUNT_MODE_NOT_DEMO)
        if readonly_present and proof_strength and proof_strength != EXPECTED_PROOF_STRENGTH:
            blocked.append(GATE_PROOF_STRENGTH_NOT_STRONG)
        if recon_present and position_details_source and position_details_source != EXPECTED_POSITION_DETAILS_SOURCE:
            blocked.append(GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY)

        if guarded_review_present and guarded_review_status and (
            guarded_review_status not in ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES
        ):
            blocked.append(GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE)

        if guarded_review_present and guarded_review_readiness and (
            guarded_review_readiness != READINESS_CONCLUSION_NOT_EXECUTABLE
        ):
            blocked.append(GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE)

        if guarded_entry_present and guarded_entry_status and (
            guarded_entry_status not in ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES
        ):
            blocked.append(GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE)

        if guarded_stop_present and guarded_stop_status and (
            guarded_stop_status not in ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES
        ):
            blocked.append(GATE_GUARDED_STOP_ADAPTER_STATUS_UNACCEPTABLE)

        if guarded_cleanup_present and guarded_cleanup_status and (
            guarded_cleanup_status not in ACCEPTABLE_GUARDED_CLEANUP_ADAPTER_STATUSES
        ):
            blocked.append(GATE_GUARDED_CLEANUP_ADAPTER_STATUS_UNACCEPTABLE)

        if not sym:
            blocked.append(GATE_SELECTED_SYMBOL_MISSING)
        elif sym != SUMMARY_EXPECTED_SYMBOL:
            blocked.append(GATE_SELECTED_SYMBOL_NOT_SOLUSDT)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 17 upstream artifacts + runtime proof envelope + AD readiness + AE/AF/AG dry-run adapter statuses.",
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
            "guarded_design_review_readiness_observed": guarded_review_readiness,
            "guarded_design_review_status_acceptable":  sorted(
                ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES
            ),
            "guarded_design_review_readiness_expected": READINESS_CONCLUSION_NOT_EXECUTABLE,
            "guarded_entry_adapter_status_observed":    guarded_entry_status,
            "guarded_entry_adapter_status_acceptable":  sorted(
                ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES
            ),
            "guarded_stop_adapter_status_observed":     guarded_stop_status,
            "guarded_stop_adapter_status_acceptable":   sorted(
                ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES
            ),
            "guarded_cleanup_adapter_status_observed":  guarded_cleanup_status,
            "guarded_cleanup_adapter_status_acceptable": sorted(
                ACCEPTABLE_GUARDED_CLEANUP_ADAPTER_STATUSES
            ),
            "selected_symbol":                          sym,
            "selected_symbol_expected":                 SUMMARY_EXPECTED_SYMBOL,
            "current_task_real_execution_allowed":      False,
        }

        # ===============================================================
        # stage_1_summary_scope
        # ===============================================================
        summary_scope: dict[str, Any] = {
            "guarded_lifecycle_dry_run_summary":  True,
            "summary_only":                       True,
            "entry_execution_included":           False,
            "stop_execution_included":            False,
            "cleanup_execution_included":         False,
            "full_lifecycle_execution_included":  False,
            "real_runner_implemented":            False,
            "real_execution_allowed":             False,
            "order_endpoint_called":              False,
            "stop_endpoint_called":               False,
            "no_endpoint_invoked_in_this_task":   True,
            "no_position_modified":               True,
            "no_secrets_loaded":                  True,
            "g20_policy_still_in_place":          True,
            "g20_lifted":                         False,
            "next_required_task":                 "TASK-014AI_guarded_entry_real_permission_review",
            "scope_summary": (
                "TASK-014AH only summarises the three single-step guarded "
                "dry-run adapters (AE entry-only, AF stop-attach-only, AG "
                "cleanup-only) into a cross-adapter consistency review.  "
                "It does not implement a real runner, does not execute "
                "entry, does not attach stop, does not cleanup, does not "
                "send any order, does not call any endpoint, does not "
                "load any secret, and does not touch any existing "
                "position."
            ),
        }
        stages[STAGE_1_SUMMARY_SCOPE] = {
            "stage":   STAGE_1_SUMMARY_SCOPE,
            "summary": "Assert guarded lifecycle dry-run summary scope (summary-only).",
            "summary_scope":                      summary_scope,
        }
        blocked.append(GATE_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_ONLY)
        blocked.append(GATE_SUMMARY_ONLY)
        blocked.append(GATE_ENTRY_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_STOP_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_CLEANUP_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_REAL_RUNNER_NOT_IMPLEMENTED)
        blocked.append(GATE_REAL_EXECUTION_NOT_ALLOWED)
        blocked.append(GATE_NO_ENDPOINT_INVOKED)
        blocked.append(GATE_NO_POSITION_MODIFIED_SCOPE)
        blocked.append(GATE_NO_SECRETS_LOADED)
        blocked.append(GATE_NO_G20_LIFT)

        # ===============================================================
        # stage_2_cross_adapter_consistency_matrix
        # ===============================================================
        sym_eff = sym or SUMMARY_EXPECTED_SYMBOL
        cross_adapter_consistency_matrix: dict[str, Any] = {
            "selected_symbol":                    sym_eff,
            "symbol_expected":                    SUMMARY_EXPECTED_SYMBOL,
            "category_expected":                  SUMMARY_EXPECTED_CATEGORY,
            "qty_expected":                       SUMMARY_EXPECTED_QTY,
            "entry_side_expected":                SUMMARY_EXPECTED_ENTRY_SIDE,
            "expected_position_side_after_entry": SUMMARY_EXPECTED_POSITION_SIDE_LONG,
            "stop_expected_side":                 SUMMARY_EXPECTED_POSITION_SIDE_LONG,
            "cleanup_expected_pre_cleanup_side":  SUMMARY_EXPECTED_POSITION_SIDE_LONG,
            "stop_loss_expected":                 SUMMARY_EXPECTED_STOP_LOSS,
            "entry_reference_expected":           SUMMARY_EXPECTED_ENTRY_REFERENCE,
            "stop_loss_below_entry_reference":    SUMMARY_EXPECTED_STOP_LOSS < SUMMARY_EXPECTED_ENTRY_REFERENCE,
            "cleanup_side_expected":              SUMMARY_EXPECTED_CLEANUP_SIDE,
            "cleanup_reduce_only_expected":       SUMMARY_EXPECTED_REDUCE_ONLY,
            "cleanup_close_on_trigger_expected":  SUMMARY_EXPECTED_CLOSE_ON_TRIGGER,
            "position_idx_expected":              SUMMARY_EXPECTED_POSITION_IDX,
            "order_type_expected":                SUMMARY_EXPECTED_ORDER_TYPE,
            "max_notional_usdt_expected":         SUMMARY_EXPECTED_MAX_NOTIONAL_USDT,
            "ae_entry_adapter_status":            guarded_entry_status,
            "af_stop_adapter_status":             guarded_stop_status,
            "ag_cleanup_adapter_status":          guarded_cleanup_status,
        }
        stages[STAGE_2_CROSS_ADAPTER_CONSISTENCY_MATRIX] = {
            "stage":   STAGE_2_CROSS_ADAPTER_CONSISTENCY_MATRIX,
            "summary": "Compare AE / AF / AG dry-run adapters on symbol / category / qty / side / stopLoss / cleanup reduceOnly / positionIdx / orderType / max_notional.",
            "cross_adapter_consistency_matrix":   cross_adapter_consistency_matrix,
        }
        blocked.append(GATE_CROSS_SYMBOL_CONSISTENT)
        blocked.append(GATE_CROSS_CATEGORY_CONSISTENT)
        blocked.append(GATE_CROSS_QTY_CONSISTENT)
        blocked.append(GATE_CROSS_ENTRY_SIDE_BUY)
        blocked.append(GATE_CROSS_EXPECTED_LONG_POSITION)
        blocked.append(GATE_CROSS_STOP_EXPECTED_LONG)
        blocked.append(GATE_CROSS_CLEANUP_PRE_CLEANUP_LONG)
        blocked.append(GATE_CROSS_STOP_LOSS_61_18)
        blocked.append(GATE_CROSS_STOP_LOSS_BELOW_ENTRY)
        blocked.append(GATE_CROSS_CLEANUP_SIDE_SELL)
        blocked.append(GATE_CROSS_CLEANUP_REDUCE_ONLY_TRUE)
        blocked.append(GATE_CROSS_CLEANUP_CLOSE_ON_TRIGGER_FALSE)
        blocked.append(GATE_CROSS_POSITION_IDX_ZERO)
        blocked.append(GATE_CROSS_ORDER_TYPE_MARKET)
        blocked.append(GATE_CROSS_MAX_NOTIONAL_10)

        # ===============================================================
        # stage_3_manual_confirmation_matrix
        # ===============================================================
        manual_confirmation_matrix: dict[str, Any] = {
            "entry_token_pattern":                ENTRY_TOKEN_PATTERN,
            "stop_token_pattern":                 STOP_TOKEN_PATTERN,
            "cleanup_token_pattern":              CLEANUP_TOKEN_PATTERN,
            "token_validated":                    False,
            "token_format_not_authorization":     True,
            "tokens_not_validated_in_this_task":  True,
            "entry_confirmation_flags":           list(ENTRY_CONFIRMATION_FLAGS),
            "stop_confirmation_flags":            list(STOP_CONFIRMATION_FLAGS),
            "cleanup_confirmation_flags":         list(CLEANUP_CONFIRMATION_FLAGS),
            "confirmation_flags_documented":      True,
            "confirmation_flags_validated":       False,
            "entry_flags_isolated_from_stop_cleanup":   True,
            "stop_flags_isolated_from_entry_cleanup":   True,
            "cleanup_flags_isolated_from_entry_stop":   True,
        }
        stages[STAGE_3_MANUAL_CONFIRMATION_MATRIX] = {
            "stage":   STAGE_3_MANUAL_CONFIRMATION_MATRIX,
            "summary": "Document the entry / stop / cleanup token patterns and per-adapter confirmation flag sets (never validated).",
            "manual_confirmation_matrix":         manual_confirmation_matrix,
        }
        blocked.append(GATE_ENTRY_TOKEN_PATTERN_PRESENT)
        blocked.append(GATE_STOP_TOKEN_PATTERN_PRESENT)
        blocked.append(GATE_CLEANUP_TOKEN_PATTERN_PRESENT)
        blocked.append(GATE_TOKENS_NOT_VALIDATED)
        blocked.append(GATE_TOKEN_FORMAT_NOT_AUTHORIZATION)
        blocked.append(GATE_CONFIRMATION_FLAGS_DOCUMENTED)
        blocked.append(GATE_CONFIRMATION_FLAGS_NOT_VALIDATED)
        blocked.append(GATE_ENTRY_FLAGS_ISOLATED)
        blocked.append(GATE_STOP_FLAGS_ISOLATED)
        blocked.append(GATE_CLEANUP_FLAGS_ISOLATED)

        # ===============================================================
        # stage_4_execution_forbidden_matrix
        # ===============================================================
        execution_forbidden_matrix: dict[str, Any] = {
            "ae_entry_adapter": {
                "status":                 guarded_entry_status,
                "real_execution_allowed": False,
                "send_allowed":           False,
                "order_endpoint_called":  False,
                "stop_endpoint_called":   False,
                "no_position_modified":   True,
                "no_live_endpoint":       True,
                "no_secrets_loaded":      True,
                "secret_value_observed":  False,
                "g20_lifted":             False,
            },
            "af_stop_adapter": {
                "status":                 guarded_stop_status,
                "real_execution_allowed": False,
                "send_allowed":           False,
                "order_endpoint_called":  False,
                "stop_endpoint_called":   False,
                "no_position_modified":   True,
                "no_live_endpoint":       True,
                "no_secrets_loaded":      True,
                "secret_value_observed":  False,
                "g20_lifted":             False,
            },
            "ag_cleanup_adapter": {
                "status":                 guarded_cleanup_status,
                "real_execution_allowed": False,
                "send_allowed":           False,
                "order_endpoint_called":  False,
                "stop_endpoint_called":   False,
                "no_position_modified":   True,
                "no_live_endpoint":       True,
                "no_secrets_loaded":      True,
                "secret_value_observed":  False,
                "g20_lifted":             False,
            },
            "no_position_modified_across_adapters": True,
            "no_secrets_loaded_across_adapters":    True,
            "no_live_endpoint_across_adapters":     True,
            "g20_not_lifted_across_adapters":       True,
        }
        stages[STAGE_4_EXECUTION_FORBIDDEN_MATRIX] = {
            "stage":   STAGE_4_EXECUTION_FORBIDDEN_MATRIX,
            "summary": "Aggregate per-adapter execution-forbidden invariants across AE / AF / AG.",
            "execution_forbidden_matrix":         execution_forbidden_matrix,
        }
        blocked.append(GATE_AE_REAL_EXECUTION_FALSE)
        blocked.append(GATE_AF_REAL_EXECUTION_FALSE)
        blocked.append(GATE_AG_REAL_EXECUTION_FALSE)
        blocked.append(GATE_AE_SEND_ALLOWED_FALSE)
        blocked.append(GATE_AF_SEND_ALLOWED_FALSE)
        blocked.append(GATE_AG_SEND_ALLOWED_FALSE)
        blocked.append(GATE_AE_ORDER_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_AF_ORDER_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_AG_ORDER_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_AE_STOP_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_AF_STOP_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_AG_STOP_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_NO_POSITION_MODIFIED_ACROSS_ADAPTERS)
        blocked.append(GATE_NO_SECRETS_LOADED_ACROSS_ADAPTERS)
        blocked.append(GATE_NO_LIVE_ENDPOINT_ACROSS_ADAPTERS)
        blocked.append(GATE_G20_NOT_LIFTED_ACROSS_ADAPTERS)

        # ===============================================================
        # stage_5_sequential_dry_run_lifecycle_plan
        # ===============================================================
        plan_steps: list[dict[str, Any]] = []
        for idx, name in enumerate(LIFECYCLE_PLAN_STEPS, start=1):
            plan_steps.append({
                "step_index":                idx,
                "step_name":                 name,
                "manual_boundary_required":  True,
                "auto_advance":              False,
                "auto_retry":                False,
                "auto_cleanup":              False,
                "auto_emergency_close":      False,
                "endpoint_called":           False,
                "response_from_exchange":    False,
            })
        sequential_dry_run_lifecycle_plan: dict[str, Any] = {
            "lifecycle_plan_present":             True,
            "step_count":                         len(plan_steps),
            "steps":                              plan_steps,
            "manual_boundary_every_step":         True,
            "auto_advance_any_step":              False,
            "auto_retry_any_step":                False,
            "auto_cleanup_any_step":              False,
            "auto_emergency_close_any_step":      False,
            "endpoint_called_any_step":           False,
            "response_from_exchange_any_step":    False,
            "plan_only":                          True,
            "executed_in_this_task":              False,
        }
        stages[STAGE_5_SEQUENTIAL_DRY_RUN_LIFECYCLE_PLAN] = {
            "stage":   STAGE_5_SEQUENTIAL_DRY_RUN_LIFECYCLE_PLAN,
            "summary": "Future 8-step sequential dry-run lifecycle plan (manual_boundary every step; never executed).",
            "sequential_dry_run_lifecycle_plan":  sequential_dry_run_lifecycle_plan,
        }
        blocked.append(GATE_LIFECYCLE_PLAN_PRESENT)
        blocked.append(GATE_LIFECYCLE_PLAN_EIGHT_STEPS)
        blocked.append(GATE_LIFECYCLE_MANUAL_BOUNDARY_EVERY_STEP)
        blocked.append(GATE_LIFECYCLE_AUTO_ADVANCE_FALSE)
        blocked.append(GATE_LIFECYCLE_AUTO_RETRY_FALSE)
        blocked.append(GATE_LIFECYCLE_AUTO_CLEANUP_FALSE)
        blocked.append(GATE_LIFECYCLE_AUTO_EMERGENCY_CLOSE_FALSE)
        blocked.append(GATE_LIFECYCLE_ENDPOINT_CALLED_FALSE_EVERY_STEP)
        blocked.append(GATE_LIFECYCLE_RESPONSE_FROM_EXCHANGE_FALSE)

        # ===============================================================
        # stage_6_failure_and_abort_summary
        # ===============================================================
        failure_and_abort_summary: dict[str, Any] = {
            "request_rejected":                  "FAIL_CLOSED",
            "readonly_unavailable":              "FAIL_CLOSED",
            "selected_symbol_mismatch":          "FAIL_CLOSED",
            "qty_mismatch":                      "FAIL_CLOSED",
            "side_mismatch":                     "FAIL_CLOSED",
            "stop_loss_invalid":                 "FAIL_CLOSED",
            "reduce_only_invalid":               "FAIL_CLOSED",
            "partial_execution":                 "FAIL_CLOSED",
            "protected_position_mismatch":       "MANUAL_REVIEW_REQUIRED",
            "live_endpoint_detected":            "FAIL_CLOSED",
            "secret_emission_detected":          "FAIL_CLOSED",
            "no_auto_retry":                     True,
            "no_auto_next_step":                 True,
            "no_auto_cleanup":                   True,
            "no_auto_second_cleanup":            True,
            "no_auto_emergency_close":           True,
            "no_background_loop":                True,
            "no_cron":                           True,
            "no_scheduler":                      True,
            "no_discord_trigger":                True,
            "no_notion_trigger":                 True,
            "manual_intervention_only":          True,
        }
        stages[STAGE_6_FAILURE_AND_ABORT_SUMMARY] = {
            "stage":   STAGE_6_FAILURE_AND_ABORT_SUMMARY,
            "summary": "Aggregate cross-adapter failure / abort policy and forbidden auto-progression.",
            "failure_and_abort_summary":         failure_and_abort_summary,
        }
        blocked.append(GATE_REQUEST_REJECTED_FAIL_CLOSED)
        blocked.append(GATE_READONLY_UNAVAILABLE_FAIL_CLOSED)
        blocked.append(GATE_SELECTED_SYMBOL_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_QTY_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_SIDE_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_STOP_LOSS_INVALID_FAIL_CLOSED)
        blocked.append(GATE_REDUCE_ONLY_INVALID_FAIL_CLOSED)
        blocked.append(GATE_PARTIAL_EXECUTION_FAIL_CLOSED)
        blocked.append(GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW)
        blocked.append(GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_SECRET_EMISSION_FAIL_CLOSED)
        blocked.append(GATE_NO_AUTO_RETRY)
        blocked.append(GATE_NO_AUTO_NEXT_STEP)
        blocked.append(GATE_NO_AUTO_CLEANUP)
        blocked.append(GATE_NO_AUTO_SECOND_CLEANUP)
        blocked.append(GATE_NO_AUTO_EMERGENCY_CLOSE)
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
            "next_required_task":                 "TASK-014AI_guarded_entry_real_permission_review",
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
        # stage_8_final_lifecycle_summary_verdict
        # ===============================================================
        blocked.append(GATE_REAL_LIFECYCLE_EXECUTION_NOT_IMPL)
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
        elif allow_real_lifecycle_execution:
            failed_stage = ""
            status_out = STATUS_REAL_LIFECYCLE_NOT_IMPL
            mode_out   = MODE_REAL_LIFECYCLE_EXECUTION_GUARD
        elif allow_summary_approval:
            failed_stage = ""
            status_out = STATUS_SUMMARY_READY_EXEC_DISABLED
            mode_out   = MODE_SUMMARY_DRY_RUN_APPROVAL
        else:
            failed_stage = ""
            status_out = STATUS_SUMMARY_READY
            mode_out   = MODE_SUMMARY_CHECKLIST

        final_lifecycle_summary_verdict: dict[str, Any] = {
            "summary_dry_run_approval_allowed":     allow_summary_approval,
            "real_lifecycle_execution_requested":   bool(allow_real_lifecycle_execution),
            "real_execution_allowed":               False,
            "real_runner_implemented":              False,
            "guarded_lifecycle_dry_run_summary":    True,
            "summary_only":                         True,
            "entry_execution_included":             False,
            "stop_execution_included":              False,
            "cleanup_execution_included":           False,
            "full_lifecycle_execution_included":    False,
            "current_task_real_execution_allowed":  False,
            "readiness_conclusion":                 READINESS_CONCLUSION_NOT_EXECUTABLE,
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "no_real_order_endpoint":               True,
            "no_real_stop_endpoint":                True,
            "no_position_modified":                 True,
            "no_live_endpoint":                     True,
            "no_secrets_loaded":                    True,
            "no_secrets_emitted":                   True,
            "send_allowed":                         False,
            "order_endpoint_called":                False,
            "stop_endpoint_called":                 False,
            "status":                               status_out,
            "mode":                                 mode_out,
            "next_required_task":                   "TASK-014AI_guarded_entry_real_permission_review",
        }

        audit_artifacts: dict[str, Any] = {
            "cross_adapter_consistency_matrix":   dict(cross_adapter_consistency_matrix),
            "manual_confirmation_matrix":         dict(manual_confirmation_matrix),
            "execution_forbidden_matrix":         dict(execution_forbidden_matrix),
            "sequential_dry_run_lifecycle_plan":  dict(sequential_dry_run_lifecycle_plan),
            "failure_and_abort_summary":         dict(failure_and_abort_summary),
            "documentation_sync_review":         dict(documentation_sync_review),
            "final_lifecycle_summary_verdict":   dict(final_lifecycle_summary_verdict),
            "response_status":                   "DRY_RUN_NOT_SENT",
            "response_from_exchange":            False,
            "sanitized":                         True,
            "no_secrets":                        True,
            "forbidden_log_fields":              list(FORBIDDEN_LOG_FIELDS),
        }

        stages[STAGE_8_FINAL_LIFECYCLE_SUMMARY_VERDICT] = {
            "stage":   STAGE_8_FINAL_LIFECYCLE_SUMMARY_VERDICT,
            "summary": "Final lifecycle summary verdict + permanent execution guard.",
            "final_lifecycle_summary_verdict":    final_lifecycle_summary_verdict,
        }

        return TinyGuardedLifecycleDryRunSummaryResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            summary_scope=summary_scope,
            cross_adapter_consistency_matrix=cross_adapter_consistency_matrix,
            manual_confirmation_matrix=manual_confirmation_matrix,
            execution_forbidden_matrix=execution_forbidden_matrix,
            sequential_dry_run_lifecycle_plan=sequential_dry_run_lifecycle_plan,
            failure_and_abort_summary=failure_and_abort_summary,
            documentation_sync_review=documentation_sync_review,
            audit_artifacts=audit_artifacts,
            final_lifecycle_summary_verdict=final_lifecycle_summary_verdict,
            summary_dry_run_approval_allowed=allow_summary_approval,
            real_lifecycle_execution_requested=bool(allow_real_lifecycle_execution),
            real_execution_allowed=False,
            real_runner_implemented=False,
            guarded_lifecycle_dry_run_summary=True,
            summary_only=True,
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
            upstream_guarded_design_review_readiness_conclusion=guarded_review_readiness,
            upstream_guarded_entry_adapter_status=guarded_entry_status,
            upstream_guarded_stop_adapter_status=guarded_stop_status,
            upstream_guarded_cleanup_adapter_status=guarded_cleanup_status,
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
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE,
            GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE,
            GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE,
            GATE_GUARDED_STOP_ADAPTER_STATUS_UNACCEPTABLE,
            GATE_GUARDED_CLEANUP_ADAPTER_STATUS_UNACCEPTABLE,
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
    "STOP_TOKEN_PATTERN",
    "CLEANUP_TOKEN_PATTERN",
    "ENTRY_CONFIRMATION_FLAGS",
    "STOP_CONFIRMATION_FLAGS",
    "CLEANUP_CONFIRMATION_FLAGS",
    "ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES",
    "ACCEPTABLE_RUNNER_DESIGN_STATUSES",
    "ACCEPTABLE_RUNNER_DRY_RUN_STATUSES",
    "ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES",
    "ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES",
    "ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES",
    "ACCEPTABLE_GUARDED_CLEANUP_ADAPTER_STATUSES",
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_LIFECYCLE_STATUS",
    "EXPECTED_INSTRUMENT_CATEGORY",
    "SUMMARY_EXPECTED_SYMBOL",
    "SUMMARY_EXPECTED_CATEGORY",
    "SUMMARY_EXPECTED_QTY",
    "SUMMARY_EXPECTED_ENTRY_SIDE",
    "SUMMARY_EXPECTED_POSITION_SIDE_LONG",
    "SUMMARY_EXPECTED_STOP_LOSS",
    "SUMMARY_EXPECTED_ENTRY_REFERENCE",
    "SUMMARY_EXPECTED_CLEANUP_SIDE",
    "SUMMARY_EXPECTED_REDUCE_ONLY",
    "SUMMARY_EXPECTED_CLOSE_ON_TRIGGER",
    "SUMMARY_EXPECTED_POSITION_IDX",
    "SUMMARY_EXPECTED_ORDER_TYPE",
    "SUMMARY_EXPECTED_MAX_NOTIONAL_USDT",
    "SUMMARY_EXPECTED_EXISTING_COUNT",
    "FORBIDDEN_LOG_FIELDS",
    "READINESS_CONCLUSION_NOT_EXECUTABLE",
    "LIFECYCLE_PLAN_STEPS",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_SUMMARY_SCOPE",
    "STAGE_2_CROSS_ADAPTER_CONSISTENCY_MATRIX",
    "STAGE_3_MANUAL_CONFIRMATION_MATRIX",
    "STAGE_4_EXECUTION_FORBIDDEN_MATRIX",
    "STAGE_5_SEQUENTIAL_DRY_RUN_LIFECYCLE_PLAN",
    "STAGE_6_FAILURE_AND_ABORT_SUMMARY",
    "STAGE_7_DOCUMENTATION_SYNC_REVIEW",
    "STAGE_8_FINAL_LIFECYCLE_SUMMARY_VERDICT",
    "ALL_STAGES",
    "STATUS_SUMMARY_READY",
    "STATUS_SUMMARY_READY_EXEC_DISABLED",
    "STATUS_REAL_LIFECYCLE_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_SUMMARY_CHECKLIST",
    "MODE_SUMMARY_DRY_RUN_APPROVAL",
    "MODE_REAL_LIFECYCLE_EXECUTION_GUARD",
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
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_MISSING",
    "GATE_SELECTED_SYMBOL_NOT_SOLUSDT",
    "GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE",
    "GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE",
    "GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE",
    "GATE_GUARDED_STOP_ADAPTER_STATUS_UNACCEPTABLE",
    "GATE_GUARDED_CLEANUP_ADAPTER_STATUS_UNACCEPTABLE",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # scope (12)
    "GATE_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_ONLY",
    "GATE_SUMMARY_ONLY",
    "GATE_ENTRY_EXECUTION_NOT_INCLUDED",
    "GATE_STOP_EXECUTION_NOT_INCLUDED",
    "GATE_CLEANUP_EXECUTION_NOT_INCLUDED",
    "GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED",
    "GATE_REAL_RUNNER_NOT_IMPLEMENTED",
    "GATE_REAL_EXECUTION_NOT_ALLOWED",
    "GATE_NO_ENDPOINT_INVOKED",
    "GATE_NO_POSITION_MODIFIED_SCOPE",
    "GATE_NO_SECRETS_LOADED",
    "GATE_NO_G20_LIFT",
    # cross-adapter (15)
    "GATE_CROSS_SYMBOL_CONSISTENT",
    "GATE_CROSS_CATEGORY_CONSISTENT",
    "GATE_CROSS_QTY_CONSISTENT",
    "GATE_CROSS_ENTRY_SIDE_BUY",
    "GATE_CROSS_EXPECTED_LONG_POSITION",
    "GATE_CROSS_STOP_EXPECTED_LONG",
    "GATE_CROSS_CLEANUP_PRE_CLEANUP_LONG",
    "GATE_CROSS_STOP_LOSS_61_18",
    "GATE_CROSS_STOP_LOSS_BELOW_ENTRY",
    "GATE_CROSS_CLEANUP_SIDE_SELL",
    "GATE_CROSS_CLEANUP_REDUCE_ONLY_TRUE",
    "GATE_CROSS_CLEANUP_CLOSE_ON_TRIGGER_FALSE",
    "GATE_CROSS_POSITION_IDX_ZERO",
    "GATE_CROSS_ORDER_TYPE_MARKET",
    "GATE_CROSS_MAX_NOTIONAL_10",
    # manual confirmation (10)
    "GATE_ENTRY_TOKEN_PATTERN_PRESENT",
    "GATE_STOP_TOKEN_PATTERN_PRESENT",
    "GATE_CLEANUP_TOKEN_PATTERN_PRESENT",
    "GATE_TOKENS_NOT_VALIDATED",
    "GATE_TOKEN_FORMAT_NOT_AUTHORIZATION",
    "GATE_CONFIRMATION_FLAGS_DOCUMENTED",
    "GATE_CONFIRMATION_FLAGS_NOT_VALIDATED",
    "GATE_ENTRY_FLAGS_ISOLATED",
    "GATE_STOP_FLAGS_ISOLATED",
    "GATE_CLEANUP_FLAGS_ISOLATED",
    # execution forbidden (16)
    "GATE_AE_REAL_EXECUTION_FALSE",
    "GATE_AF_REAL_EXECUTION_FALSE",
    "GATE_AG_REAL_EXECUTION_FALSE",
    "GATE_AE_SEND_ALLOWED_FALSE",
    "GATE_AF_SEND_ALLOWED_FALSE",
    "GATE_AG_SEND_ALLOWED_FALSE",
    "GATE_AE_ORDER_ENDPOINT_NOT_CALLED",
    "GATE_AF_ORDER_ENDPOINT_NOT_CALLED",
    "GATE_AG_ORDER_ENDPOINT_NOT_CALLED",
    "GATE_AE_STOP_ENDPOINT_NOT_CALLED",
    "GATE_AF_STOP_ENDPOINT_NOT_CALLED",
    "GATE_AG_STOP_ENDPOINT_NOT_CALLED",
    "GATE_NO_POSITION_MODIFIED_ACROSS_ADAPTERS",
    "GATE_NO_SECRETS_LOADED_ACROSS_ADAPTERS",
    "GATE_NO_LIVE_ENDPOINT_ACROSS_ADAPTERS",
    "GATE_G20_NOT_LIFTED_ACROSS_ADAPTERS",
    # lifecycle plan (9)
    "GATE_LIFECYCLE_PLAN_PRESENT",
    "GATE_LIFECYCLE_PLAN_EIGHT_STEPS",
    "GATE_LIFECYCLE_MANUAL_BOUNDARY_EVERY_STEP",
    "GATE_LIFECYCLE_AUTO_ADVANCE_FALSE",
    "GATE_LIFECYCLE_AUTO_RETRY_FALSE",
    "GATE_LIFECYCLE_AUTO_CLEANUP_FALSE",
    "GATE_LIFECYCLE_AUTO_EMERGENCY_CLOSE_FALSE",
    "GATE_LIFECYCLE_ENDPOINT_CALLED_FALSE_EVERY_STEP",
    "GATE_LIFECYCLE_RESPONSE_FROM_EXCHANGE_FALSE",
    # failure summary (21)
    "GATE_REQUEST_REJECTED_FAIL_CLOSED",
    "GATE_READONLY_UNAVAILABLE_FAIL_CLOSED",
    "GATE_SELECTED_SYMBOL_MISMATCH_FAIL_CLOSED",
    "GATE_QTY_MISMATCH_FAIL_CLOSED",
    "GATE_SIDE_MISMATCH_FAIL_CLOSED",
    "GATE_STOP_LOSS_INVALID_FAIL_CLOSED",
    "GATE_REDUCE_ONLY_INVALID_FAIL_CLOSED",
    "GATE_PARTIAL_EXECUTION_FAIL_CLOSED",
    "GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW",
    "GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED",
    "GATE_SECRET_EMISSION_FAIL_CLOSED",
    "GATE_NO_AUTO_RETRY",
    "GATE_NO_AUTO_NEXT_STEP",
    "GATE_NO_AUTO_CLEANUP",
    "GATE_NO_AUTO_SECOND_CLEANUP",
    "GATE_NO_AUTO_EMERGENCY_CLOSE",
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
    "GATE_REAL_LIFECYCLE_EXECUTION_NOT_IMPL",
    "GATE_NO_REAL_ORDER_ENDPOINT",
    "GATE_NO_REAL_STOP_ENDPOINT",
    "GATE_NO_POSITION_MODIFIED",
    "GATE_G20_NOT_LIFTED",
    # data
    "DemoTinyGuardedLifecycleDryRunSummary",
    "TinyGuardedLifecycleDryRunSummaryResult",
]
