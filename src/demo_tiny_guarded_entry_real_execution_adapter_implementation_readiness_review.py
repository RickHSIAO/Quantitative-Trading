"""
src/demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py
TASK-014AP: Guarded Entry Real Execution Adapter Implementation
            Readiness Review.

Review-only module. This task consumes TASK-014AO's adapter dry-run
output (and the 24 upstream artifacts AO already consumed) and
reviews implementation readiness for the FUTURE TASK-014AQ adapter
implementation design. It identifies preconditions, revalidates the
chain (AI/AJ/AK/AL/AM/AN/AO) status, confirms forbidden surfaces,
confirms secret / signing / transport boundaries, confirms stop and
cleanup separation, confirms risk and idempotency requirements,
documents failure / abort policies, and emits a final implementation
readiness verdict. It does NOT implement the adapter, does NOT
import any sender / private client / network primitive, does NOT
call /v5/order/create, does NOT call /v5/position/trading-stop,
does NOT read secrets, does NOT sign anything, does NOT lift
TASK-014L G20, does NOT validate any token / phrase / approval input,
does NOT treat any token / phrase / input as authorization, does NOT
touch any existing protected demo position, and does NOT
auto-commit / auto-push git.

Inputs: 25 upstream artifacts (the 24 from TASK-014AO + AO's own
        guarded entry real execution adapter dry-run output).

Stages:
  stage_0_artifact_preflight
  stage_1_readiness_review_scope
  stage_2_chain_readiness_summary
  stage_3_implementation_preconditions_review
  stage_4_forbidden_implementation_surface_review
  stage_5_secret_signing_transport_readiness_review
  stage_6_manual_approval_revalidation_review
  stage_7_stop_cleanup_readiness_review
  stage_8_risk_and_idempotency_readiness_review
  stage_9_failure_and_abort_readiness_review
  stage_10_documentation_sync_review
  stage_11_final_implementation_readiness_verdict_and_audit

Modes:
  readiness_review_checklist  --- default
  readiness_review_approval   --- --allow-readiness-review
  real_entry_execution_guard  --- --allow-real-entry-execution
  fail_closed                 --- upstream failed

This module does NOT (enforced by source-scan tests):
  * import urllib / requests / httpx / socket / http.client
  * read os.environ / dotenv
  * call HMAC / signing
  * import main / src.risk / BybitExecutor / pybit
  * import any sender / orchestrator / probe / lifecycle module
  * import any AA-AO demo_tiny_* module from src/
  * invoke /v5/order/create or /v5/position/trading-stop
  * lift TASK-014L sender G20 (protected_entry_policy_missing)
  * touch ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT
  * mutate leverage / transfer / withdraw / deposit
  * expose any real-execute / send-order / place-order / real-run flag
  * expose any adapter `send` method or executable adapter surface
  * validate any token / phrase / approval input, or treat them as authorization
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

STAGE_0_ARTIFACT_PREFLIGHT                          = "stage_0_artifact_preflight"
STAGE_1_READINESS_REVIEW_SCOPE                      = "stage_1_readiness_review_scope"
STAGE_2_CHAIN_READINESS_SUMMARY                     = "stage_2_chain_readiness_summary"
STAGE_3_IMPLEMENTATION_PRECONDITIONS_REVIEW         = "stage_3_implementation_preconditions_review"
STAGE_4_FORBIDDEN_IMPLEMENTATION_SURFACE_REVIEW     = "stage_4_forbidden_implementation_surface_review"
STAGE_5_SECRET_SIGNING_TRANSPORT_READINESS_REVIEW   = "stage_5_secret_signing_transport_readiness_review"
STAGE_6_MANUAL_APPROVAL_REVALIDATION_REVIEW         = "stage_6_manual_approval_revalidation_review"
STAGE_7_STOP_CLEANUP_READINESS_REVIEW               = "stage_7_stop_cleanup_readiness_review"
STAGE_8_RISK_AND_IDEMPOTENCY_READINESS_REVIEW       = "stage_8_risk_and_idempotency_readiness_review"
STAGE_9_FAILURE_AND_ABORT_READINESS_REVIEW          = "stage_9_failure_and_abort_readiness_review"
STAGE_10_DOCUMENTATION_SYNC_REVIEW                  = "stage_10_documentation_sync_review"
STAGE_11_FINAL_IMPLEMENTATION_READINESS_VERDICT     = "stage_11_final_implementation_readiness_verdict_and_audit"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_READINESS_REVIEW_SCOPE,
    STAGE_2_CHAIN_READINESS_SUMMARY,
    STAGE_3_IMPLEMENTATION_PRECONDITIONS_REVIEW,
    STAGE_4_FORBIDDEN_IMPLEMENTATION_SURFACE_REVIEW,
    STAGE_5_SECRET_SIGNING_TRANSPORT_READINESS_REVIEW,
    STAGE_6_MANUAL_APPROVAL_REVALIDATION_REVIEW,
    STAGE_7_STOP_CLEANUP_READINESS_REVIEW,
    STAGE_8_RISK_AND_IDEMPOTENCY_READINESS_REVIEW,
    STAGE_9_FAILURE_AND_ABORT_READINESS_REVIEW,
    STAGE_10_DOCUMENTATION_SYNC_REVIEW,
    STAGE_11_FINAL_IMPLEMENTATION_READINESS_VERDICT,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_READINESS_REVIEW_READY = (
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_IMPLEMENTATION_READINESS_REVIEW_READY"
)
STATUS_READINESS_REVIEW_READY_EXEC_DISABLED = (
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_IMPLEMENTATION_READINESS_REVIEW_"
    "READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_ENTRY_NOT_IMPL = "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED         = "FAIL_CLOSED"

MODE_READINESS_REVIEW_CHECKLIST = "readiness_review_checklist"
MODE_READINESS_REVIEW_APPROVAL  = "readiness_review_approval"
MODE_REAL_ENTRY_EXEC_GUARD      = "real_entry_execution_guard"
MODE_FAIL_CLOSED                = "fail_closed"

IMPLEMENTATION_READINESS_CONCLUSION = "READY_FOR_IMPLEMENTATION_DESIGN_NOT_EXECUTION"
READINESS_REVIEW_AUTHORIZATION_RESULT = "DOCUMENTED_ONLY_NOT_AUTHORIZED"

NEXT_REQUIRED_TASK = (
    "TASK-014AQ_guarded_entry_real_execution_adapter_implementation_design"
)


# ---------------------------------------------------------------------------
# Acceptable upstream-status whitelists (15 total)
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

ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES: frozenset[str] = frozenset({
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_READY",
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_READY_BUT_EXECUTION_DISABLED",
    "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED",
})

ACCEPTABLE_ENTRY_ADAPTER_DESIGN_STATUSES: frozenset[str] = frozenset({
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DESIGN_READY",
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DESIGN_READY_BUT_EXECUTION_DISABLED",
    "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED",
})

# 15th: only READY is acceptable for AO upstream
ACCEPTABLE_ENTRY_ADAPTER_DRY_RUN_STATUSES: frozenset[str] = frozenset({
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DRY_RUN_READY",
})


# ---------------------------------------------------------------------------
# Adapter contract identity (documented only, never instantiated as sender)
# ---------------------------------------------------------------------------

ADAPTER_NAME                          = "GuardedTinyEntryRealExecutionAdapter"
ADAPTER_CONTRACT_VERSION              = "readiness_review_v1"
CONSUMED_DRY_RUN_CONTRACT_VERSION     = "dry_run_v1"
CONSUMED_DESIGN_CONTRACT_VERSION      = "design_only_v1"
ADAPTER_RESPONSE_STATUS               = "READINESS_REVIEW_NOT_SENT"
ORDER_LINK_ID_PREFIX                  = "READINESS_REVIEW_TINY_ENTRY_"


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

DESIGN_EXPECTED_SYMBOL              = "SOLUSDT"
DESIGN_EXPECTED_CATEGORY            = "linear"
DESIGN_EXPECTED_ENTRY_SIDE          = "Buy"
DESIGN_EXPECTED_QTY                 = 0.1
DESIGN_EXPECTED_QTY_STEP            = 0.1
DESIGN_EXPECTED_MIN_ORDER_QTY       = 0.1
DESIGN_EXPECTED_TICK_SIZE           = 0.01
DESIGN_EXPECTED_MAX_NOTIONAL_USDT   = 10.0
DESIGN_EXPECTED_ENTRY_REFERENCE     = 64.4
DESIGN_EXPECTED_ESTIMATED_NOTIONAL  = 6.44
DESIGN_EXPECTED_POSITION_IDX        = 0
DESIGN_EXPECTED_REDUCE_ONLY         = False
DESIGN_EXPECTED_CLOSE_ON_TRIGGER    = False
DESIGN_EXPECTED_ORDER_TYPE          = "Market"
DESIGN_EXPECTED_STOP_LOSS           = 61.18
DESIGN_EXPECTED_TPSL_MODE           = "Full"
DESIGN_EXPECTED_SL_TRIGGER_BY       = "MarkPrice"
DESIGN_EXPECTED_EXISTING_COUNT      = 5

FORBIDDEN_LOG_FIELDS: tuple[str, ...] = (
    "api_key_value", "api_secret_value", "signature_value",
    "auth_header_value", "sign_header_value", "bearer_token_value",
)


# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------

# Missing-artifact gates (25)
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
GATE_ENTRY_MANUAL_APPROVAL_GATE_MISSING           = "entry_manual_approval_gate_missing"
GATE_ENTRY_ADAPTER_DESIGN_MISSING                 = "entry_adapter_design_missing"
GATE_ENTRY_ADAPTER_DRY_RUN_MISSING                = "entry_adapter_dry_run_missing"

# Invariant gates
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO               = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                        = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG                    = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY    = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_NOT_SOLUSDT                  = "selected_symbol_not_solusdt"

# AM acceptance gates
GATE_ENTRY_MANUAL_APPROVAL_GATE_STATUS_UNACCEPTABLE = "entry_manual_approval_gate_status_unacceptable"
GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION  = "entry_manual_approval_gate_approval_grants_execution_true"
GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED = "entry_manual_approval_gate_exact_phrase_validated_true"
GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED = "entry_manual_approval_gate_approval_inputs_validated_true"

# AN acceptance gates
GATE_ENTRY_ADAPTER_DESIGN_STATUS_UNACCEPTABLE     = "entry_adapter_design_status_unacceptable"
GATE_ENTRY_ADAPTER_DESIGN_GRANTS_EXECUTION        = "entry_adapter_design_grants_execution_true"
GATE_ENTRY_ADAPTER_DESIGN_IMPLEMENTATION_INCLUDED = "entry_adapter_design_implementation_included_true"
GATE_ENTRY_ADAPTER_DESIGN_EXECUTION_INCLUDED      = "entry_adapter_design_execution_included_true"

# AO acceptance gates (NEW)
GATE_ENTRY_ADAPTER_DRY_RUN_STATUS_UNACCEPTABLE    = "entry_adapter_dry_run_status_unacceptable"
GATE_ENTRY_ADAPTER_DRY_RUN_GRANTS_EXECUTION       = "entry_adapter_dry_run_grants_execution_true"
GATE_ENTRY_ADAPTER_DRY_RUN_ADAPTER_GRANTS_EXECUTION = "entry_adapter_dry_run_adapter_grants_execution_true"
GATE_ENTRY_ADAPTER_DRY_RUN_IMPLEMENTATION_INCLUDED = "entry_adapter_dry_run_adapter_implementation_included_true"
GATE_ENTRY_ADAPTER_DRY_RUN_EXECUTION_INCLUDED     = "entry_adapter_dry_run_adapter_execution_included_true"
GATE_ENTRY_ADAPTER_DRY_RUN_SEND_METHOD_PRESENT    = "entry_adapter_dry_run_no_send_method_false"
GATE_ENTRY_ADAPTER_DRY_RUN_RESPONSE_STATUS_UNACCEPTABLE = "entry_adapter_dry_run_response_status_unacceptable"

# Conclusion gate
GATE_IMPLEMENTATION_READINESS_CONCLUSION_MISMATCH = "implementation_readiness_conclusion_mismatch"

# Safety / sender invariants
GATE_G20_POLICY_STILL_IN_PLACE                    = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                             = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                           = "no_secret_values_emitted_in_this_task"

# Scope gates
GATE_READINESS_REVIEW_ONLY                        = "readiness_review_only"
GATE_ADAPTER_IMPLEMENTATION_NOT_INCLUDED          = "adapter_implementation_not_included"
GATE_ADAPTER_EXECUTION_NOT_INCLUDED               = "adapter_execution_not_included"
GATE_ENTRY_EXECUTION_NOT_INCLUDED                 = "entry_execution_not_included"
GATE_STOP_EXECUTION_NOT_INCLUDED                  = "stop_execution_not_included"
GATE_CLEANUP_EXECUTION_NOT_INCLUDED               = "cleanup_execution_not_included"
GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED        = "full_lifecycle_execution_not_included"
GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE             = "real_entry_not_implemented_scope"
GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE             = "real_execution_not_allowed_scope"
GATE_DRY_RUN_DOES_NOT_GRANT_EXECUTION_SCOPE       = "dry_run_does_not_grant_execution_scope"
GATE_ADAPTER_DOES_NOT_GRANT_EXECUTION_SCOPE       = "adapter_does_not_grant_execution_scope"
GATE_APPROVAL_GATE_DOES_NOT_GRANT_EXECUTION_SCOPE = "approval_gate_does_not_grant_execution_scope"
GATE_READINESS_REVIEW_DOES_NOT_GRANT_EXECUTION_SCOPE = "readiness_review_does_not_grant_execution_scope"
GATE_SEND_NOT_ALLOWED_SCOPE                       = "send_not_allowed_scope"
GATE_ORDER_ENDPOINT_NOT_CALLED                    = "order_endpoint_not_called_in_this_task"
GATE_STOP_ENDPOINT_NOT_CALLED                     = "stop_endpoint_not_called_in_this_task"
GATE_NO_ENDPOINT_INVOKED                          = "no_endpoint_invoked_in_this_task"
GATE_NO_POSITION_MODIFIED_SCOPE                   = "no_position_modified_scope"
GATE_NO_SECRETS_LOADED                            = "no_secrets_loaded_in_this_task"
GATE_NO_G20_LIFT                                  = "no_g20_policy_lift_in_this_task"

# Chain readiness summary gates
GATE_CHAIN_AI_STATUS_DOCUMENTED                   = "chain_ai_status_documented"
GATE_CHAIN_AJ_STATUS_DOCUMENTED                   = "chain_aj_status_documented"
GATE_CHAIN_AK_STATUS_DOCUMENTED                   = "chain_ak_status_documented"
GATE_CHAIN_AL_STATUS_DOCUMENTED                   = "chain_al_status_documented"
GATE_CHAIN_AM_STATUS_DOCUMENTED                   = "chain_am_status_documented"
GATE_CHAIN_AN_STATUS_DOCUMENTED                   = "chain_an_status_documented"
GATE_CHAIN_AO_STATUS_DOCUMENTED                   = "chain_ao_status_documented"

# Implementation precondition gates
GATE_PRECONDITION_NO_REAL_ENDPOINT_UNTIL_APPROVAL = "precondition_no_real_endpoint_until_additional_approval"
GATE_PRECONDITION_G20_STILL_ACTIVE                = "precondition_g20_policy_still_active"
GATE_PRECONDITION_NO_SENDER_MODULE_EXISTS         = "precondition_no_sender_module_exists_yet"
GATE_PRECONDITION_NO_SIGNING_MODULE_EXISTS        = "precondition_no_signing_module_exists_yet"
GATE_PRECONDITION_NO_SECRET_LOADER_EXISTS         = "precondition_no_secret_loader_exists_yet"
GATE_PRECONDITION_NEXT_TASK_DESIGN_ONLY           = "precondition_next_task_is_design_only_not_execution"

# Forbidden surface review gates
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
GATE_NO_EXECUTABLE_ADAPTER                        = "no_executable_adapter"
GATE_NO_SEND_METHOD                               = "no_send_method"
GATE_NO_PRIVATE_TRANSPORT                         = "no_private_transport"
GATE_NO_AA_AO_MODULE_REUSE                        = "no_aa_to_ao_module_reuse"

# Secret / signature / transport gates
GATE_SECRETS_REQUIRED_IN_FUTURE_TASK              = "secrets_required_in_future_task"
GATE_SECRETS_LOADED_FALSE                         = "secrets_loaded_false_in_this_task"
GATE_ENV_READ_FALSE                               = "env_read_false_in_this_task"
GATE_DOTENV_CALLED_FALSE                          = "dotenv_called_false_in_this_task"
GATE_HMAC_SIGNATURE_FALSE                         = "hmac_signature_false_in_this_task"
GATE_SIGNATURE_HEADER_FALSE                       = "signature_header_false_in_this_task"
GATE_PRIVATE_HEADERS_FALSE                        = "private_headers_false_in_this_task"
GATE_TRANSPORT_REQUIRES_FUTURE_TASK               = "transport_requires_future_task"
GATE_FORBIDDEN_LOG_FIELDS_DOCUMENTED              = "forbidden_log_fields_documented"

# Manual approval revalidation gates
GATE_REVALIDATE_AM_STATUS                         = "revalidate_am_status_acceptable"
GATE_REVALIDATE_AM_GRANTS_FALSE                   = "revalidate_am_grants_execution_false"
GATE_REVALIDATE_AM_PHRASE_FALSE                   = "revalidate_am_phrase_validated_false"
GATE_REVALIDATE_AM_INPUTS_FALSE                   = "revalidate_am_inputs_validated_false"

# Stop / cleanup readiness gates
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
GATE_FUTURE_ADAPTER_MUST_NOT_AUTO_ATTACH_STOP     = "future_adapter_must_not_auto_attach_stop"
GATE_FUTURE_ADAPTER_REQUIRES_SEPARATE_STOP_TASK   = "future_adapter_must_require_separate_stop_task"

# Risk / idempotency gates
GATE_RISK_NOTIONAL_CAP_DOCUMENTED                 = "risk_notional_cap_documented"
GATE_RISK_QTY_PINNED                              = "risk_qty_pinned"
GATE_RISK_SIDE_PINNED                             = "risk_side_pinned"
GATE_RISK_REDUCE_ONLY_FALSE                       = "risk_reduce_only_false"
GATE_RISK_POSITION_IDX_ZERO                       = "risk_position_idx_zero"
GATE_RISK_MAX_NOTIONAL_USDT_10                    = "risk_max_notional_usdt_10"
GATE_IDEMPOTENCY_ORDER_LINK_ID_PREFIX             = "idempotency_order_link_id_prefix"
GATE_IDEMPOTENCY_NO_DUPLICATE_SUBMIT              = "idempotency_no_duplicate_submit"
GATE_IDEMPOTENCY_NO_AUTOMATIC_RETRY               = "idempotency_no_automatic_retry"

# Failure / abort gates
GATE_MISSING_ARTIFACT_FAIL_CLOSED                 = "missing_artifact_fail_closed"
GATE_STALE_READONLY_FAIL_CLOSED                   = "stale_readonly_fail_closed"
GATE_MANUAL_APPROVAL_GATE_STALE_FAIL_CLOSED       = "manual_approval_gate_stale_fail_closed"
GATE_APPROVAL_GRANTS_EXECUTION_TRUE_FAIL_CLOSED   = "approval_grants_execution_true_fail_closed"
GATE_ADAPTER_DESIGN_GRANTS_EXECUTION_TRUE_FAIL_CLOSED = "adapter_design_grants_execution_true_fail_closed"
GATE_ADAPTER_DRY_RUN_GRANTS_EXECUTION_TRUE_FAIL_CLOSED = "adapter_dry_run_grants_execution_true_fail_closed"
GATE_SOLUSDT_EXISTS_FAIL_CLOSED                   = "solusdt_already_exists_fail_closed"
GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW_FAIL = "protected_position_mismatch_manual_review_failure"
GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED           = "live_endpoint_detected_fail_closed"
GATE_SECRET_EMISSION_DETECTED_FAIL_CLOSED         = "secret_emission_detected_fail_closed"
GATE_NETWORK_PRIMITIVE_DETECTED_FAIL_CLOSED       = "network_primitive_detected_fail_closed"
GATE_SENDER_ADAPTER_DETECTED_FAIL_CLOSED          = "sender_adapter_detected_fail_closed"
GATE_EXECUTABLE_ADAPTER_DETECTED_FAIL_CLOSED      = "executable_adapter_detected_fail_closed"
GATE_SEND_METHOD_DETECTED_FAIL_CLOSED             = "send_method_detected_fail_closed"
GATE_ANY_G20_LIFT_ATTEMPT_FAIL_CLOSED             = "any_g20_lift_attempt_fail_closed"
GATE_ANY_AUTO_EXECUTION_ATTEMPT_FAIL_CLOSED       = "any_auto_execution_attempt_fail_closed"

# Documentation gates
GATE_README_SYNC_REQUIRED                         = "readme_status_board_sync_required"
GATE_NEXT_ACTION_SYNC_REQUIRED                    = "next_action_sync_required"
GATE_COMMAND_LOG_SYNC_REQUIRED                    = "command_log_sync_required"
GATE_FORBIDDEN_STATUS_SYNC_REQUIRED               = "forbidden_status_sync_required"
GATE_NEXT_REQUIRED_TASK_SYNC_REQUIRED             = "next_required_task_sync_required"

# Execution guard gates
GATE_REAL_ENTRY_EXECUTION_NOT_IMPL                = "real_entry_execution_not_implemented"
GATE_NO_REAL_ORDER_ENDPOINT                       = "no_real_order_endpoint_in_this_task"
GATE_NO_REAL_STOP_ENDPOINT                        = "no_real_stop_endpoint_in_this_task"
GATE_NO_POSITION_MODIFIED                         = "no_position_modified_in_this_task"
GATE_G20_NOT_LIFTED                               = "g20_policy_not_lifted_by_this_task"


# Hard-fail-closed gates --- if ANY of these surface the result is
# downgraded to FAIL_CLOSED regardless of other state.
_HARD_FAIL_GATES: frozenset[str] = frozenset({
    # 25 missing-artifact gates
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
    GATE_ENTRY_MANUAL_APPROVAL_GATE_MISSING,
    GATE_ENTRY_ADAPTER_DESIGN_MISSING,
    GATE_ENTRY_ADAPTER_DRY_RUN_MISSING,
    # 4 invariant gates
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    # AM acceptance
    GATE_ENTRY_MANUAL_APPROVAL_GATE_STATUS_UNACCEPTABLE,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED,
    # AN acceptance
    GATE_ENTRY_ADAPTER_DESIGN_STATUS_UNACCEPTABLE,
    GATE_ENTRY_ADAPTER_DESIGN_GRANTS_EXECUTION,
    GATE_ENTRY_ADAPTER_DESIGN_IMPLEMENTATION_INCLUDED,
    GATE_ENTRY_ADAPTER_DESIGN_EXECUTION_INCLUDED,
    # AO acceptance (NEW)
    GATE_ENTRY_ADAPTER_DRY_RUN_STATUS_UNACCEPTABLE,
    GATE_ENTRY_ADAPTER_DRY_RUN_GRANTS_EXECUTION,
    GATE_ENTRY_ADAPTER_DRY_RUN_ADAPTER_GRANTS_EXECUTION,
    GATE_ENTRY_ADAPTER_DRY_RUN_IMPLEMENTATION_INCLUDED,
    GATE_ENTRY_ADAPTER_DRY_RUN_EXECUTION_INCLUDED,
    GATE_ENTRY_ADAPTER_DRY_RUN_SEND_METHOD_PRESENT,
    GATE_ENTRY_ADAPTER_DRY_RUN_RESPONSE_STATUS_UNACCEPTABLE,
    # Conclusion mismatch
    GATE_IMPLEMENTATION_READINESS_CONCLUSION_MISMATCH,
    # Symbol gates
    GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
    GATE_SOLUSDT_EXISTS_FAIL_CLOSED,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyGuardedEntryRealExecutionAdapterImplementationReadinessReviewResult:
    """Read-only outcome of one implementation readiness review."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    readiness_review_scope:                   dict[str, Any] = field(default_factory=dict)
    chain_readiness_summary:                  dict[str, Any] = field(default_factory=dict)
    implementation_preconditions_review:      dict[str, Any] = field(default_factory=dict)
    forbidden_implementation_surface_review:  dict[str, Any] = field(default_factory=dict)
    secret_signing_transport_readiness_review: dict[str, Any] = field(default_factory=dict)
    manual_approval_revalidation_review:      dict[str, Any] = field(default_factory=dict)
    stop_cleanup_readiness_review:            dict[str, Any] = field(default_factory=dict)
    risk_and_idempotency_readiness_review:    dict[str, Any] = field(default_factory=dict)
    failure_and_abort_readiness_review:       dict[str, Any] = field(default_factory=dict)
    documentation_sync_review:                dict[str, Any] = field(default_factory=dict)
    final_implementation_readiness_verdict:   dict[str, Any] = field(default_factory=dict)
    audit_artifacts:                          dict[str, Any] = field(default_factory=dict)

    adapter_name:                     str = ADAPTER_NAME
    adapter_contract_version:         str = ADAPTER_CONTRACT_VERSION
    consumed_dry_run_contract_version: str = CONSUMED_DRY_RUN_CONTRACT_VERSION
    consumed_design_contract_version:  str = CONSUMED_DESIGN_CONTRACT_VERSION
    order_link_id_prefix:             str = ORDER_LINK_ID_PREFIX

    readiness_review_allowed:          bool = False
    real_entry_execution_requested:    bool = False
    real_execution_allowed:            bool = False
    real_entry_implemented:            bool = False
    guarded_entry_real_execution_adapter_implementation_readiness_review: bool = True
    readiness_review_only:             bool = True
    adapter_implementation_included:   bool = False
    adapter_execution_included:        bool = False
    dry_run_grants_execution:          bool = False
    adapter_grants_execution:          bool = False
    approval_gate_grants_execution:    bool = False
    readiness_review_grants_execution: bool = False
    entry_execution_included:          bool = False
    stop_execution_included:           bool = False
    cleanup_execution_included:        bool = False
    full_lifecycle_execution_included: bool = False
    current_task_real_execution_allowed: bool = False
    implementation_readiness_conclusion: str = IMPLEMENTATION_READINESS_CONCLUSION
    readiness_review_authorization_result: str = READINESS_REVIEW_AUTHORIZATION_RESULT

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

    upstream_lifecycle_summary_status:                                  str = ""
    upstream_runner_design_status:                                      str = ""
    upstream_runner_dry_run_status:                                     str = ""
    upstream_guarded_design_review_status:                              str = ""
    upstream_guarded_entry_adapter_status:                              str = ""
    upstream_guarded_stop_adapter_status:                               str = ""
    upstream_guarded_cleanup_adapter_status:                            str = ""
    upstream_guarded_lifecycle_summary_status:                          str = ""
    upstream_entry_real_permission_review_status:                       str = ""
    upstream_entry_manual_auth_design_status:                           str = ""
    upstream_entry_manual_auth_dry_run_status:                          str = ""
    upstream_entry_final_pre_execution_review_status:                   str = ""
    upstream_entry_manual_approval_gate_status:                         str = ""
    upstream_entry_manual_approval_gate_approval_grants_execution:      bool = False
    upstream_entry_manual_approval_gate_exact_phrase_validated:         bool = False
    upstream_entry_manual_approval_gate_approval_inputs_validated:      bool = False
    upstream_entry_adapter_design_status:                               str = ""
    upstream_entry_adapter_design_grants_execution:                     bool = False
    upstream_entry_adapter_design_implementation_included:              bool = False
    upstream_entry_adapter_design_execution_included:                   bool = False
    upstream_entry_adapter_dry_run_status:                              str = ""
    upstream_entry_adapter_dry_run_dry_run_grants_execution:            bool = False
    upstream_entry_adapter_dry_run_adapter_grants_execution:            bool = False
    upstream_entry_adapter_dry_run_adapter_implementation_included:     bool = False
    upstream_entry_adapter_dry_run_adapter_execution_included:          bool = False
    upstream_entry_adapter_dry_run_no_send_method:                      bool = True
    upstream_entry_adapter_dry_run_response_status:                     str = ""

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = NEXT_REQUIRED_TASK

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                                 self.timestamp_utc,
            "timestamp_utc":                             self.timestamp_utc,
            "mode":                                      self.mode,
            "selected_symbol":                           self.selected_symbol,
            "existing_position_symbols":                 list(self.existing_position_symbols),
            "stages":                                    {k: dict(v) for k, v in self.stages.items()},
            "stage_order":                               list(self.stage_order),
            "readiness_review_scope":                    dict(self.readiness_review_scope),
            "chain_readiness_summary":                   dict(self.chain_readiness_summary),
            "implementation_preconditions_review":       dict(self.implementation_preconditions_review),
            "forbidden_implementation_surface_review":   dict(self.forbidden_implementation_surface_review),
            "secret_signing_transport_readiness_review": dict(self.secret_signing_transport_readiness_review),
            "manual_approval_revalidation_review":       dict(self.manual_approval_revalidation_review),
            "stop_cleanup_readiness_review":             dict(self.stop_cleanup_readiness_review),
            "risk_and_idempotency_readiness_review":     dict(self.risk_and_idempotency_readiness_review),
            "failure_and_abort_readiness_review":        dict(self.failure_and_abort_readiness_review),
            "documentation_sync_review":                 dict(self.documentation_sync_review),
            "final_implementation_readiness_verdict":    dict(self.final_implementation_readiness_verdict),
            "audit_artifacts":                           dict(self.audit_artifacts),
            "adapter_name":                              self.adapter_name,
            "adapter_contract_version":                  self.adapter_contract_version,
            "consumed_dry_run_contract_version":         self.consumed_dry_run_contract_version,
            "consumed_design_contract_version":          self.consumed_design_contract_version,
            "order_link_id_prefix":                      self.order_link_id_prefix,
            "readiness_review_allowed":                  self.readiness_review_allowed,
            "real_entry_execution_requested":            self.real_entry_execution_requested,
            "real_execution_allowed":                    self.real_execution_allowed,
            "real_entry_implemented":                    self.real_entry_implemented,
            "guarded_entry_real_execution_adapter_implementation_readiness_review":
                self.guarded_entry_real_execution_adapter_implementation_readiness_review,
            "readiness_review_only":                     self.readiness_review_only,
            "adapter_implementation_included":           self.adapter_implementation_included,
            "adapter_execution_included":                self.adapter_execution_included,
            "dry_run_grants_execution":                  self.dry_run_grants_execution,
            "adapter_grants_execution":                  self.adapter_grants_execution,
            "approval_gate_grants_execution":            self.approval_gate_grants_execution,
            "readiness_review_grants_execution":         self.readiness_review_grants_execution,
            "entry_execution_included":                  self.entry_execution_included,
            "stop_execution_included":                   self.stop_execution_included,
            "cleanup_execution_included":                self.cleanup_execution_included,
            "full_lifecycle_execution_included":         self.full_lifecycle_execution_included,
            "current_task_real_execution_allowed":       self.current_task_real_execution_allowed,
            "implementation_readiness_conclusion":       self.implementation_readiness_conclusion,
            "readiness_review_authorization_result":     self.readiness_review_authorization_result,
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
            "upstream_entry_manual_approval_gate_status":
                self.upstream_entry_manual_approval_gate_status,
            "upstream_entry_manual_approval_gate_approval_grants_execution":
                self.upstream_entry_manual_approval_gate_approval_grants_execution,
            "upstream_entry_manual_approval_gate_exact_phrase_validated":
                self.upstream_entry_manual_approval_gate_exact_phrase_validated,
            "upstream_entry_manual_approval_gate_approval_inputs_validated":
                self.upstream_entry_manual_approval_gate_approval_inputs_validated,
            "upstream_entry_adapter_design_status":
                self.upstream_entry_adapter_design_status,
            "upstream_entry_adapter_design_grants_execution":
                self.upstream_entry_adapter_design_grants_execution,
            "upstream_entry_adapter_design_implementation_included":
                self.upstream_entry_adapter_design_implementation_included,
            "upstream_entry_adapter_design_execution_included":
                self.upstream_entry_adapter_design_execution_included,
            "upstream_entry_adapter_dry_run_status":
                self.upstream_entry_adapter_dry_run_status,
            "upstream_entry_adapter_dry_run_dry_run_grants_execution":
                self.upstream_entry_adapter_dry_run_dry_run_grants_execution,
            "upstream_entry_adapter_dry_run_adapter_grants_execution":
                self.upstream_entry_adapter_dry_run_adapter_grants_execution,
            "upstream_entry_adapter_dry_run_adapter_implementation_included":
                self.upstream_entry_adapter_dry_run_adapter_implementation_included,
            "upstream_entry_adapter_dry_run_adapter_execution_included":
                self.upstream_entry_adapter_dry_run_adapter_execution_included,
            "upstream_entry_adapter_dry_run_no_send_method":
                self.upstream_entry_adapter_dry_run_no_send_method,
            "upstream_entry_adapter_dry_run_response_status":
                self.upstream_entry_adapter_dry_run_response_status,
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


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "on"}
    return bool(value)


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
# Implementation readiness review
# ---------------------------------------------------------------------------

class DemoTinyGuardedEntryRealExecutionAdapterImplementationReadinessReview:
    """
    Pure-computation guarded entry real execution adapter implementation
    readiness review. Re-reviews 25 upstream artifacts and emits the
    implementation-readiness verdict. Never opens a socket, reads no
    environment variables, performs no HMAC signing, never validates any
    token / phrase / approval input, never treats them as authorization,
    never auto-commits / auto-pushes git, never exposes any adapter
    `send` method, and NEVER invokes the order-create or trading-stop
    endpoints.

    --allow-readiness-review        --> status promoted to
        ..._READY_BUT_EXECUTION_DISABLED

    --allow-real-entry-execution    --> status fixed to
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
        entry_manual_approval_gate:           dict[str, Any] | None,
        entry_adapter_design:                 dict[str, Any] | None,
        entry_adapter_dry_run:                dict[str, Any] | None,
        symbol:                               str  = DEFAULT_SELECTED_SYMBOL,
        expected_commit_hash:                 str  = "",
        current_commit_hash:                  str  = "",
        allow_readiness_review:               bool = False,
        allow_real_entry_execution:           bool = False,
        _now:                                 datetime | None = None,
    ) -> TinyGuardedEntryRealExecutionAdapterImplementationReadinessReviewResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_entry_execution:
            mode = MODE_REAL_ENTRY_EXEC_GUARD
        elif allow_readiness_review:
            mode = MODE_READINESS_REVIEW_APPROVAL
        else:
            mode = MODE_READINESS_REVIEW_CHECKLIST

        blocked: list[str] = []
        stages:  dict[str, dict[str, Any]] = {}

        # ===============================================================
        # stage_0_artifact_preflight
        # ===============================================================
        sym = _safe_str(symbol)
        existing_snapshot = _positions_from_reconciliation(reconciliation)
        existing_symbols  = _symbols_only(existing_snapshot)

        present_flags = {
            "readonly":                isinstance(readonly_smoke, dict) and bool(readonly_smoke),
            "recon":                   isinstance(reconciliation, dict) and bool(reconciliation),
            "protection":              isinstance(protection, dict) and bool(protection),
            "contract":                isinstance(contract, dict) and bool(contract),
            "noop":                    isinstance(noop_plan, dict) and bool(noop_plan),
            "lifecycle":               isinstance(lifecycle_mock, dict) and bool(lifecycle_mock),
            "real_perm":               isinstance(real_permission_gate, dict) and bool(real_permission_gate),
            "entry_perm":              isinstance(tiny_entry_permission_gate, dict) and bool(tiny_entry_permission_gate),
            "stop_perm":               isinstance(tiny_stop_permission_gate, dict) and bool(tiny_stop_permission_gate),
            "cleanup_perm":            isinstance(tiny_cleanup_permission_gate, dict) and bool(tiny_cleanup_permission_gate),
            "summary":                 isinstance(lifecycle_summary, dict) and bool(lifecycle_summary),
            "runner_design":           isinstance(runner_design, dict) and bool(runner_design),
            "runner_dry_run":          isinstance(runner_dry_run, dict) and bool(runner_dry_run),
            "guarded_review":          isinstance(guarded_design_review, dict) and bool(guarded_design_review),
            "guarded_entry":           isinstance(guarded_entry_adapter, dict) and bool(guarded_entry_adapter),
            "guarded_stop":            isinstance(guarded_stop_adapter, dict) and bool(guarded_stop_adapter),
            "guarded_cleanup":         isinstance(guarded_cleanup_adapter, dict) and bool(guarded_cleanup_adapter),
            "guarded_lifecycle":       isinstance(guarded_lifecycle_summary, dict) and bool(guarded_lifecycle_summary),
            "entry_perm_review":       isinstance(entry_real_permission_review, dict) and bool(entry_real_permission_review),
            "entry_auth_design":       isinstance(entry_manual_authorization_design, dict) and bool(entry_manual_authorization_design),
            "entry_auth_dry_run":      isinstance(entry_manual_authorization_dry_run, dict) and bool(entry_manual_authorization_dry_run),
            "entry_final_review":      isinstance(entry_final_pre_execution_review, dict) and bool(entry_final_pre_execution_review),
            "entry_approval_gate":     isinstance(entry_manual_approval_gate, dict) and bool(entry_manual_approval_gate),
            "entry_adapter_design":    isinstance(entry_adapter_design, dict) and bool(entry_adapter_design),
            "entry_adapter_dry_run":   isinstance(entry_adapter_dry_run, dict) and bool(entry_adapter_dry_run),
        }

        endpoint_family = _safe_str((readonly_smoke or {}).get("endpoint_family", ""))
        account_mode    = _safe_str((readonly_smoke or {}).get("account_mode", ""))
        proof_strength  = _safe_str((readonly_smoke or {}).get("proof_strength", ""))
        position_details_source = _safe_str(
            (reconciliation or {}).get(
                "position_details_source",
                (reconciliation or {}).get("mode", ""),
            )
        )

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
        entry_approval_gate_status  = _safe_str((entry_manual_approval_gate or {}).get("status", ""))
        entry_approval_gate_grants = _safe_bool(
            (entry_manual_approval_gate or {}).get("approval_grants_execution", False)
        )
        entry_approval_gate_phrase = _safe_bool(
            (entry_manual_approval_gate or {}).get("exact_phrase_validated", False)
        )
        entry_approval_gate_inputs = _safe_bool(
            (entry_manual_approval_gate or {}).get("approval_inputs_validated", False)
        )
        entry_adapter_design_status = _safe_str((entry_adapter_design or {}).get("status", ""))
        entry_adapter_design_grants = _safe_bool(
            (entry_adapter_design or {}).get("adapter_grants_execution", False)
        )
        entry_adapter_design_impl = _safe_bool(
            (entry_adapter_design or {}).get("adapter_implementation_included", False)
        )
        entry_adapter_design_exec = _safe_bool(
            (entry_adapter_design or {}).get("adapter_execution_included", False)
        )

        # AO dry-run fields
        adr = entry_adapter_dry_run or {}
        entry_adapter_dry_run_status = _safe_str(adr.get("status", ""))
        entry_adapter_dry_run_dry_run_grants = _safe_bool(adr.get("dry_run_grants_execution", False))
        entry_adapter_dry_run_adapter_grants = _safe_bool(adr.get("adapter_grants_execution", False))
        entry_adapter_dry_run_impl = _safe_bool(adr.get("adapter_implementation_included", False))
        entry_adapter_dry_run_exec = _safe_bool(adr.get("adapter_execution_included", False))
        # No-send-method may live inside forbidden_execution_surface_dry_run.
        # If parent has explicit no_send_method, prefer that.
        _ao_audit = adr.get("audit_artifacts") if isinstance(adr.get("audit_artifacts"), dict) else {}
        _ao_forbidden = (
            adr.get("forbidden_execution_surface_dry_run")
            if isinstance(adr.get("forbidden_execution_surface_dry_run"), dict)
            else {}
        )
        if "no_send_method" in adr:
            entry_adapter_dry_run_no_send = _safe_bool(adr.get("no_send_method"))
        elif isinstance(_ao_forbidden, dict) and "no_send_method" in _ao_forbidden:
            entry_adapter_dry_run_no_send = _safe_bool(_ao_forbidden.get("no_send_method"))
        else:
            entry_adapter_dry_run_no_send = True
        entry_adapter_dry_run_response_status = _safe_str(
            _ao_audit.get("response_status", adr.get("response_status", ""))
        )

        # Missing-artifact gates (25)
        if not present_flags["readonly"]:           blocked.append(GATE_READONLY_SMOKE_MISSING)
        if not present_flags["recon"]:              blocked.append(GATE_RECONCILIATION_MISSING)
        if not present_flags["protection"]:         blocked.append(GATE_PROTECTION_MISSING)
        if not present_flags["contract"]:           blocked.append(GATE_CONTRACT_MISSING)
        if not present_flags["noop"]:               blocked.append(GATE_NOOP_PLAN_MISSING)
        if not present_flags["lifecycle"]:          blocked.append(GATE_LIFECYCLE_MOCK_MISSING)
        if not present_flags["real_perm"]:          blocked.append(GATE_REAL_PERMISSION_GATE_MISSING)
        if not present_flags["entry_perm"]:         blocked.append(GATE_TINY_ENTRY_PERMISSION_GATE_MISSING)
        if not present_flags["stop_perm"]:          blocked.append(GATE_TINY_STOP_PERMISSION_GATE_MISSING)
        if not present_flags["cleanup_perm"]:       blocked.append(GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING)
        if not present_flags["summary"]:            blocked.append(GATE_LIFECYCLE_SUMMARY_MISSING)
        if not present_flags["runner_design"]:      blocked.append(GATE_RUNNER_DESIGN_MISSING)
        if not present_flags["runner_dry_run"]:     blocked.append(GATE_RUNNER_DRY_RUN_MISSING)
        if not present_flags["guarded_review"]:     blocked.append(GATE_GUARDED_DESIGN_REVIEW_MISSING)
        if not present_flags["guarded_entry"]:      blocked.append(GATE_GUARDED_ENTRY_ADAPTER_MISSING)
        if not present_flags["guarded_stop"]:       blocked.append(GATE_GUARDED_STOP_ADAPTER_MISSING)
        if not present_flags["guarded_cleanup"]:    blocked.append(GATE_GUARDED_CLEANUP_ADAPTER_MISSING)
        if not present_flags["guarded_lifecycle"]:  blocked.append(GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING)
        if not present_flags["entry_perm_review"]:  blocked.append(GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING)
        if not present_flags["entry_auth_design"]:  blocked.append(GATE_ENTRY_MANUAL_AUTH_DESIGN_MISSING)
        if not present_flags["entry_auth_dry_run"]: blocked.append(GATE_ENTRY_MANUAL_AUTH_DRY_RUN_MISSING)
        if not present_flags["entry_final_review"]: blocked.append(GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING)
        if not present_flags["entry_approval_gate"]: blocked.append(GATE_ENTRY_MANUAL_APPROVAL_GATE_MISSING)
        if not present_flags["entry_adapter_design"]: blocked.append(GATE_ENTRY_ADAPTER_DESIGN_MISSING)
        if not present_flags["entry_adapter_dry_run"]: blocked.append(GATE_ENTRY_ADAPTER_DRY_RUN_MISSING)

        if present_flags["readonly"] and endpoint_family and endpoint_family != EXPECTED_ENDPOINT_FAMILY:
            blocked.append(GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO)
        if present_flags["readonly"] and account_mode and account_mode != EXPECTED_ACCOUNT_MODE:
            blocked.append(GATE_ACCOUNT_MODE_NOT_DEMO)
        if present_flags["readonly"] and proof_strength and proof_strength != EXPECTED_PROOF_STRENGTH:
            blocked.append(GATE_PROOF_STRENGTH_NOT_STRONG)
        if present_flags["recon"] and position_details_source and position_details_source != EXPECTED_POSITION_DETAILS_SOURCE:
            blocked.append(GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY)

        # AM acceptance
        if present_flags["entry_approval_gate"] and entry_approval_gate_status and (
            entry_approval_gate_status not in ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES
        ):
            blocked.append(GATE_ENTRY_MANUAL_APPROVAL_GATE_STATUS_UNACCEPTABLE)
        if present_flags["entry_approval_gate"] and entry_approval_gate_grants:
            blocked.append(GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION)
        if present_flags["entry_approval_gate"] and entry_approval_gate_phrase:
            blocked.append(GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED)
        if present_flags["entry_approval_gate"] and entry_approval_gate_inputs:
            blocked.append(GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED)

        # AN acceptance
        if present_flags["entry_adapter_design"] and entry_adapter_design_status and (
            entry_adapter_design_status not in ACCEPTABLE_ENTRY_ADAPTER_DESIGN_STATUSES
        ):
            blocked.append(GATE_ENTRY_ADAPTER_DESIGN_STATUS_UNACCEPTABLE)
        if present_flags["entry_adapter_design"] and entry_adapter_design_grants:
            blocked.append(GATE_ENTRY_ADAPTER_DESIGN_GRANTS_EXECUTION)
        if present_flags["entry_adapter_design"] and entry_adapter_design_impl:
            blocked.append(GATE_ENTRY_ADAPTER_DESIGN_IMPLEMENTATION_INCLUDED)
        if present_flags["entry_adapter_design"] and entry_adapter_design_exec:
            blocked.append(GATE_ENTRY_ADAPTER_DESIGN_EXECUTION_INCLUDED)

        # AO acceptance (NEW)
        if present_flags["entry_adapter_dry_run"] and entry_adapter_dry_run_status and (
            entry_adapter_dry_run_status not in ACCEPTABLE_ENTRY_ADAPTER_DRY_RUN_STATUSES
        ):
            blocked.append(GATE_ENTRY_ADAPTER_DRY_RUN_STATUS_UNACCEPTABLE)
        if present_flags["entry_adapter_dry_run"] and entry_adapter_dry_run_dry_run_grants:
            blocked.append(GATE_ENTRY_ADAPTER_DRY_RUN_GRANTS_EXECUTION)
        if present_flags["entry_adapter_dry_run"] and entry_adapter_dry_run_adapter_grants:
            blocked.append(GATE_ENTRY_ADAPTER_DRY_RUN_ADAPTER_GRANTS_EXECUTION)
        if present_flags["entry_adapter_dry_run"] and entry_adapter_dry_run_impl:
            blocked.append(GATE_ENTRY_ADAPTER_DRY_RUN_IMPLEMENTATION_INCLUDED)
        if present_flags["entry_adapter_dry_run"] and entry_adapter_dry_run_exec:
            blocked.append(GATE_ENTRY_ADAPTER_DRY_RUN_EXECUTION_INCLUDED)
        if present_flags["entry_adapter_dry_run"] and not entry_adapter_dry_run_no_send:
            blocked.append(GATE_ENTRY_ADAPTER_DRY_RUN_SEND_METHOD_PRESENT)
        if (
            present_flags["entry_adapter_dry_run"]
            and entry_adapter_dry_run_response_status
            and entry_adapter_dry_run_response_status != "ADAPTER_DRY_RUN_NOT_SENT"
        ):
            blocked.append(GATE_ENTRY_ADAPTER_DRY_RUN_RESPONSE_STATUS_UNACCEPTABLE)

        if sym and sym != DESIGN_EXPECTED_SYMBOL:
            blocked.append(GATE_SELECTED_SYMBOL_NOT_SOLUSDT)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 25 upstream artifacts + runtime proof envelope + AM / AN / AO acceptance flags.",
            "present_flags":                     dict(present_flags),
            "endpoint_family_observed":          endpoint_family,
            "endpoint_family_expected":          EXPECTED_ENDPOINT_FAMILY,
            "account_mode_observed":             account_mode,
            "account_mode_expected":             EXPECTED_ACCOUNT_MODE,
            "proof_strength_observed":           proof_strength,
            "proof_strength_expected":           EXPECTED_PROOF_STRENGTH,
            "position_details_source_observed":  position_details_source,
            "position_details_source_expected":  EXPECTED_POSITION_DETAILS_SOURCE,
            "entry_manual_approval_gate_status_observed":  entry_approval_gate_status,
            "entry_adapter_design_status_observed":        entry_adapter_design_status,
            "entry_adapter_dry_run_status_observed":       entry_adapter_dry_run_status,
            "entry_adapter_dry_run_response_status_observed": entry_adapter_dry_run_response_status,
            "entry_adapter_dry_run_status_acceptable":     sorted(ACCEPTABLE_ENTRY_ADAPTER_DRY_RUN_STATUSES),
            "selected_symbol":                   sym,
            "selected_symbol_expected":          DESIGN_EXPECTED_SYMBOL,
        }

        # ===============================================================
        # stage_1_readiness_review_scope
        # ===============================================================
        readiness_review_scope: dict[str, Any] = {
            "guarded_entry_real_execution_adapter_implementation_readiness_review": True,
            "readiness_review_only":                True,
            "adapter_implementation_included":      False,
            "adapter_execution_included":           False,
            "entry_execution_included":             False,
            "stop_execution_included":              False,
            "cleanup_execution_included":           False,
            "full_lifecycle_execution_included":    False,
            "real_entry_implemented":               False,
            "real_execution_allowed":               False,
            "dry_run_grants_execution":             False,
            "adapter_grants_execution":             False,
            "approval_gate_grants_execution":       False,
            "readiness_review_grants_execution":    False,
            "send_allowed":                         False,
            "order_endpoint_called":                False,
            "stop_endpoint_called":                 False,
            "no_endpoint_invoked_in_this_task":     True,
            "no_position_modified":                 True,
            "no_secrets_loaded":                    True,
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "next_required_task":                   NEXT_REQUIRED_TASK,
            "scope_summary": (
                "TASK-014AP consumes TASK-014AO's adapter dry-run output "
                "and reviews implementation readiness for TASK-014AQ. It "
                "documents preconditions, revalidates the entire chain "
                "(AI/AJ/AK/AL/AM/AN/AO), confirms forbidden surfaces, "
                "confirms secret / signing / transport boundary stays "
                "intact, confirms stop / cleanup separation, confirms "
                "risk / idempotency requirements, and documents failure / "
                "abort policies. It does not implement the adapter, does "
                "not build any sender or private client, never validates "
                "any token / phrase / approval input, never treats them "
                "as authorization, never sends an order, never calls any "
                "endpoint, never modifies any position, never lifts G20, "
                "never loads any secret, and never auto-commits / "
                "auto-pushes git."
            ),
        }
        stages[STAGE_1_READINESS_REVIEW_SCOPE] = {
            "stage":   STAGE_1_READINESS_REVIEW_SCOPE,
            "summary": "Assert implementation readiness review scope (review-only, no implementation, no execution).",
            "readiness_review_scope":               readiness_review_scope,
        }
        blocked.append(GATE_READINESS_REVIEW_ONLY)
        blocked.append(GATE_ADAPTER_IMPLEMENTATION_NOT_INCLUDED)
        blocked.append(GATE_ADAPTER_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_ENTRY_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_STOP_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_CLEANUP_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE)
        blocked.append(GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE)
        blocked.append(GATE_DRY_RUN_DOES_NOT_GRANT_EXECUTION_SCOPE)
        blocked.append(GATE_ADAPTER_DOES_NOT_GRANT_EXECUTION_SCOPE)
        blocked.append(GATE_APPROVAL_GATE_DOES_NOT_GRANT_EXECUTION_SCOPE)
        blocked.append(GATE_READINESS_REVIEW_DOES_NOT_GRANT_EXECUTION_SCOPE)
        blocked.append(GATE_SEND_NOT_ALLOWED_SCOPE)
        blocked.append(GATE_ORDER_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_STOP_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_NO_ENDPOINT_INVOKED)
        blocked.append(GATE_NO_POSITION_MODIFIED_SCOPE)
        blocked.append(GATE_NO_SECRETS_LOADED)
        blocked.append(GATE_NO_G20_LIFT)

        # ===============================================================
        # stage_2_chain_readiness_summary
        # ===============================================================
        chain_readiness_summary: dict[str, Any] = {
            "ai_entry_real_permission_review": {
                "status":                  entry_perm_review_status,
                "grants_execution":        False,
            },
            "aj_entry_manual_authorization_design": {
                "status":                  entry_auth_design_status,
                "grants_execution":        False,
            },
            "ak_entry_manual_authorization_dry_run": {
                "status":                  entry_auth_dry_run_status,
                "grants_execution":        False,
            },
            "al_entry_final_pre_execution_review": {
                "status":                  entry_final_review_status,
                "grants_execution":        False,
            },
            "am_entry_manual_approval_gate": {
                "status":                  entry_approval_gate_status,
                "approval_grants_execution": entry_approval_gate_grants,
                "exact_phrase_validated":  entry_approval_gate_phrase,
                "approval_inputs_validated": entry_approval_gate_inputs,
            },
            "an_entry_adapter_design": {
                "status":                          entry_adapter_design_status,
                "adapter_grants_execution":        entry_adapter_design_grants,
                "adapter_implementation_included": entry_adapter_design_impl,
                "adapter_execution_included":      entry_adapter_design_exec,
            },
            "ao_entry_adapter_dry_run": {
                "status":                          entry_adapter_dry_run_status,
                "dry_run_grants_execution":        entry_adapter_dry_run_dry_run_grants,
                "adapter_grants_execution":        entry_adapter_dry_run_adapter_grants,
                "adapter_implementation_included": entry_adapter_dry_run_impl,
                "adapter_execution_included":      entry_adapter_dry_run_exec,
                "no_send_method":                  entry_adapter_dry_run_no_send,
                "response_status":                 entry_adapter_dry_run_response_status,
            },
            "chain_complete":                  True,
            "chain_grants_execution":          False,
        }
        stages[STAGE_2_CHAIN_READINESS_SUMMARY] = {
            "stage":   STAGE_2_CHAIN_READINESS_SUMMARY,
            "summary": "Summarize AI/AJ/AK/AL/AM/AN/AO chain status and grants_execution flags.",
            "chain_readiness_summary":            chain_readiness_summary,
        }
        blocked.append(GATE_CHAIN_AI_STATUS_DOCUMENTED)
        blocked.append(GATE_CHAIN_AJ_STATUS_DOCUMENTED)
        blocked.append(GATE_CHAIN_AK_STATUS_DOCUMENTED)
        blocked.append(GATE_CHAIN_AL_STATUS_DOCUMENTED)
        blocked.append(GATE_CHAIN_AM_STATUS_DOCUMENTED)
        blocked.append(GATE_CHAIN_AN_STATUS_DOCUMENTED)
        blocked.append(GATE_CHAIN_AO_STATUS_DOCUMENTED)

        # ===============================================================
        # stage_3_implementation_preconditions_review
        # ===============================================================
        implementation_preconditions_review: dict[str, Any] = {
            "no_real_endpoint_until_additional_approval":   True,
            "g20_policy_still_active":                      True,
            "no_sender_module_exists_yet":                  True,
            "no_signing_module_exists_yet":                 True,
            "no_secret_loader_exists_yet":                  True,
            "next_task_is_design_only_not_execution":       True,
            "next_required_task":                           NEXT_REQUIRED_TASK,
            "expected_qty":                                 DESIGN_EXPECTED_QTY,
            "expected_side":                                DESIGN_EXPECTED_ENTRY_SIDE,
            "expected_reduce_only":                         DESIGN_EXPECTED_REDUCE_ONLY,
            "expected_order_type":                          DESIGN_EXPECTED_ORDER_TYPE,
            "expected_position_idx":                        DESIGN_EXPECTED_POSITION_IDX,
            "expected_max_notional_usdt":                   DESIGN_EXPECTED_MAX_NOTIONAL_USDT,
            "expected_stop_loss":                           DESIGN_EXPECTED_STOP_LOSS,
            "expected_tpsl_mode":                           DESIGN_EXPECTED_TPSL_MODE,
            "expected_sl_trigger_by":                       DESIGN_EXPECTED_SL_TRIGGER_BY,
            "expected_commit_hash_documented":              True,
            "preconditions_summary": (
                "Implementation design (TASK-014AQ) MAY proceed only when "
                "ALL of: (1) no real endpoint is enabled, (2) G20 sender "
                "policy still active, (3) no sender module exists, (4) no "
                "signing module exists, (5) no secret loader exists, and "
                "(6) next task is design-only not execution. The next task "
                "is a DESIGN review, not an execution authorization."
            ),
        }
        stages[STAGE_3_IMPLEMENTATION_PRECONDITIONS_REVIEW] = {
            "stage":   STAGE_3_IMPLEMENTATION_PRECONDITIONS_REVIEW,
            "summary": "List preconditions for the future TASK-014AQ implementation design.",
            "implementation_preconditions_review": implementation_preconditions_review,
        }
        blocked.append(GATE_PRECONDITION_NO_REAL_ENDPOINT_UNTIL_APPROVAL)
        blocked.append(GATE_PRECONDITION_G20_STILL_ACTIVE)
        blocked.append(GATE_PRECONDITION_NO_SENDER_MODULE_EXISTS)
        blocked.append(GATE_PRECONDITION_NO_SIGNING_MODULE_EXISTS)
        blocked.append(GATE_PRECONDITION_NO_SECRET_LOADER_EXISTS)
        blocked.append(GATE_PRECONDITION_NEXT_TASK_DESIGN_ONLY)

        # ===============================================================
        # stage_4_forbidden_implementation_surface_review
        # ===============================================================
        forbidden_implementation_surface_review: dict[str, Any] = {
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
            "no_executable_adapter":                 True,
            "no_send_method":                        True,
            "no_private_transport":                  True,
            "no_aa_to_ao_module_reuse":              True,
        }
        stages[STAGE_4_FORBIDDEN_IMPLEMENTATION_SURFACE_REVIEW] = {
            "stage":   STAGE_4_FORBIDDEN_IMPLEMENTATION_SURFACE_REVIEW,
            "summary": "Confirm forbidden implementation surface remains in place (no sender / no transport / no signing / no AA-AO reuse).",
            "forbidden_implementation_surface_review": forbidden_implementation_surface_review,
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
        blocked.append(GATE_NO_EXECUTABLE_ADAPTER)
        blocked.append(GATE_NO_SEND_METHOD)
        blocked.append(GATE_NO_PRIVATE_TRANSPORT)
        blocked.append(GATE_NO_AA_AO_MODULE_REUSE)

        # ===============================================================
        # stage_5_secret_signing_transport_readiness_review
        # ===============================================================
        secret_signing_transport_readiness_review: dict[str, Any] = {
            "secrets_required_in_future_task":       True,
            "secrets_loaded_in_this_task":           False,
            "env_read_in_this_task":                 False,
            "dotenv_called_in_this_task":            False,
            "hmac_signature_created":                False,
            "signature_header_created":              False,
            "private_headers_created":               False,
            "transport_required_in_future_task":     True,
            "transport_implemented_in_this_task":    False,
            "forbidden_log_fields":                  list(FORBIDDEN_LOG_FIELDS),
        }
        stages[STAGE_5_SECRET_SIGNING_TRANSPORT_READINESS_REVIEW] = {
            "stage":   STAGE_5_SECRET_SIGNING_TRANSPORT_READINESS_REVIEW,
            "summary": "Secret / signing / transport readiness review (future-task only; nothing implemented here).",
            "secret_signing_transport_readiness_review": secret_signing_transport_readiness_review,
        }
        blocked.append(GATE_SECRETS_REQUIRED_IN_FUTURE_TASK)
        blocked.append(GATE_SECRETS_LOADED_FALSE)
        blocked.append(GATE_ENV_READ_FALSE)
        blocked.append(GATE_DOTENV_CALLED_FALSE)
        blocked.append(GATE_HMAC_SIGNATURE_FALSE)
        blocked.append(GATE_SIGNATURE_HEADER_FALSE)
        blocked.append(GATE_PRIVATE_HEADERS_FALSE)
        blocked.append(GATE_TRANSPORT_REQUIRES_FUTURE_TASK)
        blocked.append(GATE_FORBIDDEN_LOG_FIELDS_DOCUMENTED)

        # ===============================================================
        # stage_6_manual_approval_revalidation_review
        # ===============================================================
        manual_approval_revalidation_review: dict[str, Any] = {
            "am_status_observed":                       entry_approval_gate_status,
            "am_status_acceptable_set":                 sorted(ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES),
            "am_status_acceptable":                     entry_approval_gate_status in ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES
                                                       if entry_approval_gate_status else True,
            "am_approval_grants_execution_observed":    entry_approval_gate_grants,
            "am_approval_grants_execution_expected":    False,
            "am_exact_phrase_validated_observed":       entry_approval_gate_phrase,
            "am_exact_phrase_validated_expected":       False,
            "am_approval_inputs_validated_observed":    entry_approval_gate_inputs,
            "am_approval_inputs_validated_expected":    False,
            "revalidation_summary": (
                "Re-confirm TASK-014AM (manual approval gate) flags are "
                "all in NOT-AUTHORIZED state. Any True flag must FAIL_CLOSED."
            ),
        }
        stages[STAGE_6_MANUAL_APPROVAL_REVALIDATION_REVIEW] = {
            "stage":   STAGE_6_MANUAL_APPROVAL_REVALIDATION_REVIEW,
            "summary": "Re-validate TASK-014AM manual approval gate status / flags remain not-authorized.",
            "manual_approval_revalidation_review": manual_approval_revalidation_review,
        }
        blocked.append(GATE_REVALIDATE_AM_STATUS)
        blocked.append(GATE_REVALIDATE_AM_GRANTS_FALSE)
        blocked.append(GATE_REVALIDATE_AM_PHRASE_FALSE)
        blocked.append(GATE_REVALIDATE_AM_INPUTS_FALSE)

        # ===============================================================
        # stage_7_stop_cleanup_readiness_review
        # ===============================================================
        stop_cleanup_readiness_review: dict[str, Any] = {
            "stop_attach_required_after_entry":      True,
            "stop_attach_not_included_in_this_task": True,
            "stop_loss":                             DESIGN_EXPECTED_STOP_LOSS,
            "tpsl_mode":                             DESIGN_EXPECTED_TPSL_MODE,
            "sl_trigger_by":                         DESIGN_EXPECTED_SL_TRIGGER_BY,
            "cleanup_not_included_in_this_task":     True,
            "cleanup_separate_manual_boundary":      True,
            "no_automatic_stop_attach":              True,
            "no_automatic_cleanup":                  True,
            "no_automatic_emergency_close":          True,
            "future_adapter_must_not_auto_attach_stop": True,
            "future_adapter_must_require_separate_stop_task": True,
        }
        stages[STAGE_7_STOP_CLEANUP_READINESS_REVIEW] = {
            "stage":   STAGE_7_STOP_CLEANUP_READINESS_REVIEW,
            "summary": "Stop attach / cleanup readiness review (separate manual boundaries; future adapter must not auto-attach).",
            "stop_cleanup_readiness_review":        stop_cleanup_readiness_review,
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
        blocked.append(GATE_FUTURE_ADAPTER_MUST_NOT_AUTO_ATTACH_STOP)
        blocked.append(GATE_FUTURE_ADAPTER_REQUIRES_SEPARATE_STOP_TASK)

        # ===============================================================
        # stage_8_risk_and_idempotency_readiness_review
        # ===============================================================
        risk_and_idempotency_readiness_review: dict[str, Any] = {
            "notional_cap_documented":               True,
            "qty":                                   DESIGN_EXPECTED_QTY,
            "side":                                  DESIGN_EXPECTED_ENTRY_SIDE,
            "reduce_only":                           DESIGN_EXPECTED_REDUCE_ONLY,
            "position_idx":                          DESIGN_EXPECTED_POSITION_IDX,
            "max_notional_usdt":                     DESIGN_EXPECTED_MAX_NOTIONAL_USDT,
            "order_link_id_prefix":                  ORDER_LINK_ID_PREFIX,
            "idempotency_no_duplicate_submit":       True,
            "idempotency_no_automatic_retry":        True,
            "symbol":                                DESIGN_EXPECTED_SYMBOL,
            "category":                              DESIGN_EXPECTED_CATEGORY,
            "order_type":                            DESIGN_EXPECTED_ORDER_TYPE,
        }
        stages[STAGE_8_RISK_AND_IDEMPOTENCY_READINESS_REVIEW] = {
            "stage":   STAGE_8_RISK_AND_IDEMPOTENCY_READINESS_REVIEW,
            "summary": "Risk / idempotency readiness review (notional cap; pinned qty / side / positionIdx; idempotent order link id).",
            "risk_and_idempotency_readiness_review": risk_and_idempotency_readiness_review,
        }
        blocked.append(GATE_RISK_NOTIONAL_CAP_DOCUMENTED)
        blocked.append(GATE_RISK_QTY_PINNED)
        blocked.append(GATE_RISK_SIDE_PINNED)
        blocked.append(GATE_RISK_REDUCE_ONLY_FALSE)
        blocked.append(GATE_RISK_POSITION_IDX_ZERO)
        blocked.append(GATE_RISK_MAX_NOTIONAL_USDT_10)
        blocked.append(GATE_IDEMPOTENCY_ORDER_LINK_ID_PREFIX)
        blocked.append(GATE_IDEMPOTENCY_NO_DUPLICATE_SUBMIT)
        blocked.append(GATE_IDEMPOTENCY_NO_AUTOMATIC_RETRY)

        # ===============================================================
        # stage_9_failure_and_abort_readiness_review
        # ===============================================================
        solusdt_in_existing = DESIGN_EXPECTED_SYMBOL in existing_symbols
        if solusdt_in_existing:
            blocked.append(GATE_SOLUSDT_EXISTS_FAIL_CLOSED)

        failure_and_abort_readiness_review: dict[str, Any] = {
            "missing_artifact":                      "FAIL_CLOSED",
            "stale_readonly":                        "FAIL_CLOSED",
            "manual_approval_gate_stale":            "FAIL_CLOSED",
            "approval_grants_execution_true":        "FAIL_CLOSED",
            "adapter_design_grants_execution_true":  "FAIL_CLOSED",
            "adapter_dry_run_grants_execution_true": "FAIL_CLOSED",
            "solusdt_already_exists":                "FAIL_CLOSED",
            "protected_position_mismatch":           "MANUAL_REVIEW_REQUIRED",
            "live_endpoint_detected":                "FAIL_CLOSED",
            "secret_emission_detected":              "FAIL_CLOSED",
            "network_primitive_detected":            "FAIL_CLOSED",
            "sender_adapter_detected":               "FAIL_CLOSED",
            "executable_adapter_detected":           "FAIL_CLOSED",
            "send_method_detected":                  "FAIL_CLOSED",
            "any_g20_lift_attempt":                  "FAIL_CLOSED",
            "any_auto_execution_attempt":            "FAIL_CLOSED",
            "manual_intervention_only":              True,
        }
        stages[STAGE_9_FAILURE_AND_ABORT_READINESS_REVIEW] = {
            "stage":   STAGE_9_FAILURE_AND_ABORT_READINESS_REVIEW,
            "summary": "Failure / abort readiness review (FAIL_CLOSED / MANUAL_REVIEW_REQUIRED only; no auto-progression).",
            "failure_and_abort_readiness_review":   failure_and_abort_readiness_review,
        }
        blocked.append(GATE_MISSING_ARTIFACT_FAIL_CLOSED)
        blocked.append(GATE_STALE_READONLY_FAIL_CLOSED)
        blocked.append(GATE_MANUAL_APPROVAL_GATE_STALE_FAIL_CLOSED)
        blocked.append(GATE_APPROVAL_GRANTS_EXECUTION_TRUE_FAIL_CLOSED)
        blocked.append(GATE_ADAPTER_DESIGN_GRANTS_EXECUTION_TRUE_FAIL_CLOSED)
        blocked.append(GATE_ADAPTER_DRY_RUN_GRANTS_EXECUTION_TRUE_FAIL_CLOSED)
        blocked.append(GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW_FAIL)
        blocked.append(GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_SECRET_EMISSION_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_NETWORK_PRIMITIVE_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_SENDER_ADAPTER_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_EXECUTABLE_ADAPTER_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_SEND_METHOD_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_ANY_G20_LIFT_ATTEMPT_FAIL_CLOSED)
        blocked.append(GATE_ANY_AUTO_EXECUTION_ATTEMPT_FAIL_CLOSED)

        # ===============================================================
        # stage_10_documentation_sync_review
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
            "next_required_task":                    NEXT_REQUIRED_TASK,
            "documentation_only_plan":               True,
            "markdown_read_in_this_module":          False,
        }
        stages[STAGE_10_DOCUMENTATION_SYNC_REVIEW] = {
            "stage":   STAGE_10_DOCUMENTATION_SYNC_REVIEW,
            "summary": "Documentation sync plan (README / NEXT_ACTION / COMMAND_LOG / forbidden status / next_required_task).",
            "documentation_sync_review":            documentation_sync_review,
        }
        blocked.append(GATE_README_SYNC_REQUIRED)
        blocked.append(GATE_NEXT_ACTION_SYNC_REQUIRED)
        blocked.append(GATE_COMMAND_LOG_SYNC_REQUIRED)
        blocked.append(GATE_FORBIDDEN_STATUS_SYNC_REQUIRED)
        blocked.append(GATE_NEXT_REQUIRED_TASK_SYNC_REQUIRED)

        # ===============================================================
        # stage_11_final_implementation_readiness_verdict_and_audit
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
        elif allow_readiness_review:
            failed_stage = ""
            status_out = STATUS_READINESS_REVIEW_READY_EXEC_DISABLED
            mode_out   = MODE_READINESS_REVIEW_APPROVAL
        else:
            failed_stage = ""
            status_out = STATUS_READINESS_REVIEW_READY
            mode_out   = MODE_READINESS_REVIEW_CHECKLIST

        final_implementation_readiness_verdict: dict[str, Any] = {
            "readiness_review_allowed":              allow_readiness_review,
            "real_entry_execution_requested":        bool(allow_real_entry_execution),
            "real_execution_allowed":                False,
            "real_entry_implemented":                False,
            "guarded_entry_real_execution_adapter_implementation_readiness_review": True,
            "readiness_review_only":                 True,
            "adapter_implementation_included":       False,
            "adapter_execution_included":            False,
            "dry_run_grants_execution":              False,
            "adapter_grants_execution":              False,
            "approval_gate_grants_execution":        False,
            "readiness_review_grants_execution":     False,
            "entry_execution_included":              False,
            "stop_execution_included":               False,
            "cleanup_execution_included":            False,
            "full_lifecycle_execution_included":     False,
            "current_task_real_execution_allowed":   False,
            "implementation_readiness_conclusion":   IMPLEMENTATION_READINESS_CONCLUSION,
            "readiness_review_authorization_result": READINESS_REVIEW_AUTHORIZATION_RESULT,
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
            "next_required_task":                    NEXT_REQUIRED_TASK,
        }

        audit_artifacts: dict[str, Any] = {
            "readiness_review_scope":                  dict(readiness_review_scope),
            "chain_readiness_summary":                 dict(chain_readiness_summary),
            "implementation_preconditions_review":     dict(implementation_preconditions_review),
            "forbidden_implementation_surface_review": dict(forbidden_implementation_surface_review),
            "secret_signing_transport_readiness_review": dict(secret_signing_transport_readiness_review),
            "manual_approval_revalidation_review":     dict(manual_approval_revalidation_review),
            "stop_cleanup_readiness_review":           dict(stop_cleanup_readiness_review),
            "risk_and_idempotency_readiness_review":   dict(risk_and_idempotency_readiness_review),
            "failure_and_abort_readiness_review":      dict(failure_and_abort_readiness_review),
            "documentation_sync_review":               dict(documentation_sync_review),
            "final_implementation_readiness_verdict":  dict(final_implementation_readiness_verdict),
            "response_status":                        ADAPTER_RESPONSE_STATUS,
            "response_from_exchange":                 False,
            "sanitized":                              True,
            "no_secrets":                             True,
            "forbidden_log_fields":                   list(FORBIDDEN_LOG_FIELDS),
            "next_required_task":                     NEXT_REQUIRED_TASK,
        }

        stages[STAGE_11_FINAL_IMPLEMENTATION_READINESS_VERDICT] = {
            "stage":   STAGE_11_FINAL_IMPLEMENTATION_READINESS_VERDICT,
            "summary": "Final implementation readiness verdict + permanent execution guard + audit artifacts.",
            "final_implementation_readiness_verdict": final_implementation_readiness_verdict,
            "audit_artifacts":                        dict(audit_artifacts),
        }

        return TinyGuardedEntryRealExecutionAdapterImplementationReadinessReviewResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            readiness_review_scope=readiness_review_scope,
            chain_readiness_summary=chain_readiness_summary,
            implementation_preconditions_review=implementation_preconditions_review,
            forbidden_implementation_surface_review=forbidden_implementation_surface_review,
            secret_signing_transport_readiness_review=secret_signing_transport_readiness_review,
            manual_approval_revalidation_review=manual_approval_revalidation_review,
            stop_cleanup_readiness_review=stop_cleanup_readiness_review,
            risk_and_idempotency_readiness_review=risk_and_idempotency_readiness_review,
            failure_and_abort_readiness_review=failure_and_abort_readiness_review,
            documentation_sync_review=documentation_sync_review,
            final_implementation_readiness_verdict=final_implementation_readiness_verdict,
            audit_artifacts=audit_artifacts,
            readiness_review_allowed=allow_readiness_review,
            real_entry_execution_requested=bool(allow_real_entry_execution),
            real_execution_allowed=False,
            real_entry_implemented=False,
            guarded_entry_real_execution_adapter_implementation_readiness_review=True,
            readiness_review_only=True,
            adapter_implementation_included=False,
            adapter_execution_included=False,
            dry_run_grants_execution=False,
            adapter_grants_execution=False,
            approval_gate_grants_execution=False,
            readiness_review_grants_execution=False,
            entry_execution_included=False,
            stop_execution_included=False,
            cleanup_execution_included=False,
            full_lifecycle_execution_included=False,
            current_task_real_execution_allowed=False,
            implementation_readiness_conclusion=IMPLEMENTATION_READINESS_CONCLUSION,
            readiness_review_authorization_result=READINESS_REVIEW_AUTHORIZATION_RESULT,
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
            upstream_entry_manual_approval_gate_status=entry_approval_gate_status,
            upstream_entry_manual_approval_gate_approval_grants_execution=entry_approval_gate_grants,
            upstream_entry_manual_approval_gate_exact_phrase_validated=entry_approval_gate_phrase,
            upstream_entry_manual_approval_gate_approval_inputs_validated=entry_approval_gate_inputs,
            upstream_entry_adapter_design_status=entry_adapter_design_status,
            upstream_entry_adapter_design_grants_execution=entry_adapter_design_grants,
            upstream_entry_adapter_design_implementation_included=entry_adapter_design_impl,
            upstream_entry_adapter_design_execution_included=entry_adapter_design_exec,
            upstream_entry_adapter_dry_run_status=entry_adapter_dry_run_status,
            upstream_entry_adapter_dry_run_dry_run_grants_execution=entry_adapter_dry_run_dry_run_grants,
            upstream_entry_adapter_dry_run_adapter_grants_execution=entry_adapter_dry_run_adapter_grants,
            upstream_entry_adapter_dry_run_adapter_implementation_included=entry_adapter_dry_run_impl,
            upstream_entry_adapter_dry_run_adapter_execution_included=entry_adapter_dry_run_exec,
            upstream_entry_adapter_dry_run_no_send_method=entry_adapter_dry_run_no_send,
            upstream_entry_adapter_dry_run_response_status=entry_adapter_dry_run_response_status,
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
            GATE_ENTRY_MANUAL_APPROVAL_GATE_MISSING,
            GATE_ENTRY_ADAPTER_DESIGN_MISSING,
            GATE_ENTRY_ADAPTER_DRY_RUN_MISSING,
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_ENTRY_MANUAL_APPROVAL_GATE_STATUS_UNACCEPTABLE,
            GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION,
            GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED,
            GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED,
            GATE_ENTRY_ADAPTER_DESIGN_STATUS_UNACCEPTABLE,
            GATE_ENTRY_ADAPTER_DESIGN_GRANTS_EXECUTION,
            GATE_ENTRY_ADAPTER_DESIGN_IMPLEMENTATION_INCLUDED,
            GATE_ENTRY_ADAPTER_DESIGN_EXECUTION_INCLUDED,
            GATE_ENTRY_ADAPTER_DRY_RUN_STATUS_UNACCEPTABLE,
            GATE_ENTRY_ADAPTER_DRY_RUN_GRANTS_EXECUTION,
            GATE_ENTRY_ADAPTER_DRY_RUN_ADAPTER_GRANTS_EXECUTION,
            GATE_ENTRY_ADAPTER_DRY_RUN_IMPLEMENTATION_INCLUDED,
            GATE_ENTRY_ADAPTER_DRY_RUN_EXECUTION_INCLUDED,
            GATE_ENTRY_ADAPTER_DRY_RUN_SEND_METHOD_PRESENT,
            GATE_ENTRY_ADAPTER_DRY_RUN_RESPONSE_STATUS_UNACCEPTABLE,
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
    "ADAPTER_NAME",
    "ADAPTER_CONTRACT_VERSION",
    "CONSUMED_DRY_RUN_CONTRACT_VERSION",
    "CONSUMED_DESIGN_CONTRACT_VERSION",
    "ADAPTER_RESPONSE_STATUS",
    "ORDER_LINK_ID_PREFIX",
    "IMPLEMENTATION_READINESS_CONCLUSION",
    "READINESS_REVIEW_AUTHORIZATION_RESULT",
    "NEXT_REQUIRED_TASK",
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
    "ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES",
    "ACCEPTABLE_ENTRY_ADAPTER_DESIGN_STATUSES",
    "ACCEPTABLE_ENTRY_ADAPTER_DRY_RUN_STATUSES",
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_LIFECYCLE_STATUS",
    "EXPECTED_INSTRUMENT_CATEGORY",
    "DESIGN_EXPECTED_SYMBOL",
    "DESIGN_EXPECTED_CATEGORY",
    "DESIGN_EXPECTED_ENTRY_SIDE",
    "DESIGN_EXPECTED_QTY",
    "DESIGN_EXPECTED_QTY_STEP",
    "DESIGN_EXPECTED_MIN_ORDER_QTY",
    "DESIGN_EXPECTED_TICK_SIZE",
    "DESIGN_EXPECTED_MAX_NOTIONAL_USDT",
    "DESIGN_EXPECTED_ENTRY_REFERENCE",
    "DESIGN_EXPECTED_ESTIMATED_NOTIONAL",
    "DESIGN_EXPECTED_POSITION_IDX",
    "DESIGN_EXPECTED_REDUCE_ONLY",
    "DESIGN_EXPECTED_CLOSE_ON_TRIGGER",
    "DESIGN_EXPECTED_ORDER_TYPE",
    "DESIGN_EXPECTED_STOP_LOSS",
    "DESIGN_EXPECTED_TPSL_MODE",
    "DESIGN_EXPECTED_SL_TRIGGER_BY",
    "DESIGN_EXPECTED_EXISTING_COUNT",
    "FORBIDDEN_LOG_FIELDS",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_READINESS_REVIEW_SCOPE",
    "STAGE_2_CHAIN_READINESS_SUMMARY",
    "STAGE_3_IMPLEMENTATION_PRECONDITIONS_REVIEW",
    "STAGE_4_FORBIDDEN_IMPLEMENTATION_SURFACE_REVIEW",
    "STAGE_5_SECRET_SIGNING_TRANSPORT_READINESS_REVIEW",
    "STAGE_6_MANUAL_APPROVAL_REVALIDATION_REVIEW",
    "STAGE_7_STOP_CLEANUP_READINESS_REVIEW",
    "STAGE_8_RISK_AND_IDEMPOTENCY_READINESS_REVIEW",
    "STAGE_9_FAILURE_AND_ABORT_READINESS_REVIEW",
    "STAGE_10_DOCUMENTATION_SYNC_REVIEW",
    "STAGE_11_FINAL_IMPLEMENTATION_READINESS_VERDICT",
    "ALL_STAGES",
    "STATUS_READINESS_REVIEW_READY",
    "STATUS_READINESS_REVIEW_READY_EXEC_DISABLED",
    "STATUS_REAL_ENTRY_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_READINESS_REVIEW_CHECKLIST",
    "MODE_READINESS_REVIEW_APPROVAL",
    "MODE_REAL_ENTRY_EXEC_GUARD",
    "MODE_FAIL_CLOSED",
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
    "GATE_ENTRY_MANUAL_APPROVAL_GATE_MISSING",
    "GATE_ENTRY_ADAPTER_DESIGN_MISSING",
    "GATE_ENTRY_ADAPTER_DRY_RUN_MISSING",
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_NOT_SOLUSDT",
    "GATE_ENTRY_MANUAL_APPROVAL_GATE_STATUS_UNACCEPTABLE",
    "GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION",
    "GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED",
    "GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED",
    "GATE_ENTRY_ADAPTER_DESIGN_STATUS_UNACCEPTABLE",
    "GATE_ENTRY_ADAPTER_DESIGN_GRANTS_EXECUTION",
    "GATE_ENTRY_ADAPTER_DESIGN_IMPLEMENTATION_INCLUDED",
    "GATE_ENTRY_ADAPTER_DESIGN_EXECUTION_INCLUDED",
    "GATE_ENTRY_ADAPTER_DRY_RUN_STATUS_UNACCEPTABLE",
    "GATE_ENTRY_ADAPTER_DRY_RUN_GRANTS_EXECUTION",
    "GATE_ENTRY_ADAPTER_DRY_RUN_ADAPTER_GRANTS_EXECUTION",
    "GATE_ENTRY_ADAPTER_DRY_RUN_IMPLEMENTATION_INCLUDED",
    "GATE_ENTRY_ADAPTER_DRY_RUN_EXECUTION_INCLUDED",
    "GATE_ENTRY_ADAPTER_DRY_RUN_SEND_METHOD_PRESENT",
    "GATE_ENTRY_ADAPTER_DRY_RUN_RESPONSE_STATUS_UNACCEPTABLE",
    "GATE_IMPLEMENTATION_READINESS_CONCLUSION_MISMATCH",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    "GATE_READINESS_REVIEW_ONLY",
    "GATE_ADAPTER_IMPLEMENTATION_NOT_INCLUDED",
    "GATE_ADAPTER_EXECUTION_NOT_INCLUDED",
    "GATE_ENTRY_EXECUTION_NOT_INCLUDED",
    "GATE_STOP_EXECUTION_NOT_INCLUDED",
    "GATE_CLEANUP_EXECUTION_NOT_INCLUDED",
    "GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED",
    "GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE",
    "GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE",
    "GATE_DRY_RUN_DOES_NOT_GRANT_EXECUTION_SCOPE",
    "GATE_ADAPTER_DOES_NOT_GRANT_EXECUTION_SCOPE",
    "GATE_APPROVAL_GATE_DOES_NOT_GRANT_EXECUTION_SCOPE",
    "GATE_READINESS_REVIEW_DOES_NOT_GRANT_EXECUTION_SCOPE",
    "GATE_SEND_NOT_ALLOWED_SCOPE",
    "GATE_ORDER_ENDPOINT_NOT_CALLED",
    "GATE_STOP_ENDPOINT_NOT_CALLED",
    "GATE_NO_ENDPOINT_INVOKED",
    "GATE_NO_POSITION_MODIFIED_SCOPE",
    "GATE_NO_SECRETS_LOADED",
    "GATE_NO_G20_LIFT",
    "GATE_CHAIN_AI_STATUS_DOCUMENTED",
    "GATE_CHAIN_AJ_STATUS_DOCUMENTED",
    "GATE_CHAIN_AK_STATUS_DOCUMENTED",
    "GATE_CHAIN_AL_STATUS_DOCUMENTED",
    "GATE_CHAIN_AM_STATUS_DOCUMENTED",
    "GATE_CHAIN_AN_STATUS_DOCUMENTED",
    "GATE_CHAIN_AO_STATUS_DOCUMENTED",
    "GATE_PRECONDITION_NO_REAL_ENDPOINT_UNTIL_APPROVAL",
    "GATE_PRECONDITION_G20_STILL_ACTIVE",
    "GATE_PRECONDITION_NO_SENDER_MODULE_EXISTS",
    "GATE_PRECONDITION_NO_SIGNING_MODULE_EXISTS",
    "GATE_PRECONDITION_NO_SECRET_LOADER_EXISTS",
    "GATE_PRECONDITION_NEXT_TASK_DESIGN_ONLY",
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
    "GATE_NO_EXECUTABLE_ADAPTER",
    "GATE_NO_SEND_METHOD",
    "GATE_NO_PRIVATE_TRANSPORT",
    "GATE_NO_AA_AO_MODULE_REUSE",
    "GATE_SECRETS_REQUIRED_IN_FUTURE_TASK",
    "GATE_SECRETS_LOADED_FALSE",
    "GATE_ENV_READ_FALSE",
    "GATE_DOTENV_CALLED_FALSE",
    "GATE_HMAC_SIGNATURE_FALSE",
    "GATE_SIGNATURE_HEADER_FALSE",
    "GATE_PRIVATE_HEADERS_FALSE",
    "GATE_TRANSPORT_REQUIRES_FUTURE_TASK",
    "GATE_FORBIDDEN_LOG_FIELDS_DOCUMENTED",
    "GATE_REVALIDATE_AM_STATUS",
    "GATE_REVALIDATE_AM_GRANTS_FALSE",
    "GATE_REVALIDATE_AM_PHRASE_FALSE",
    "GATE_REVALIDATE_AM_INPUTS_FALSE",
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
    "GATE_FUTURE_ADAPTER_MUST_NOT_AUTO_ATTACH_STOP",
    "GATE_FUTURE_ADAPTER_REQUIRES_SEPARATE_STOP_TASK",
    "GATE_RISK_NOTIONAL_CAP_DOCUMENTED",
    "GATE_RISK_QTY_PINNED",
    "GATE_RISK_SIDE_PINNED",
    "GATE_RISK_REDUCE_ONLY_FALSE",
    "GATE_RISK_POSITION_IDX_ZERO",
    "GATE_RISK_MAX_NOTIONAL_USDT_10",
    "GATE_IDEMPOTENCY_ORDER_LINK_ID_PREFIX",
    "GATE_IDEMPOTENCY_NO_DUPLICATE_SUBMIT",
    "GATE_IDEMPOTENCY_NO_AUTOMATIC_RETRY",
    "GATE_MISSING_ARTIFACT_FAIL_CLOSED",
    "GATE_STALE_READONLY_FAIL_CLOSED",
    "GATE_MANUAL_APPROVAL_GATE_STALE_FAIL_CLOSED",
    "GATE_APPROVAL_GRANTS_EXECUTION_TRUE_FAIL_CLOSED",
    "GATE_ADAPTER_DESIGN_GRANTS_EXECUTION_TRUE_FAIL_CLOSED",
    "GATE_ADAPTER_DRY_RUN_GRANTS_EXECUTION_TRUE_FAIL_CLOSED",
    "GATE_SOLUSDT_EXISTS_FAIL_CLOSED",
    "GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW_FAIL",
    "GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED",
    "GATE_SECRET_EMISSION_DETECTED_FAIL_CLOSED",
    "GATE_NETWORK_PRIMITIVE_DETECTED_FAIL_CLOSED",
    "GATE_SENDER_ADAPTER_DETECTED_FAIL_CLOSED",
    "GATE_EXECUTABLE_ADAPTER_DETECTED_FAIL_CLOSED",
    "GATE_SEND_METHOD_DETECTED_FAIL_CLOSED",
    "GATE_ANY_G20_LIFT_ATTEMPT_FAIL_CLOSED",
    "GATE_ANY_AUTO_EXECUTION_ATTEMPT_FAIL_CLOSED",
    "GATE_README_SYNC_REQUIRED",
    "GATE_NEXT_ACTION_SYNC_REQUIRED",
    "GATE_COMMAND_LOG_SYNC_REQUIRED",
    "GATE_FORBIDDEN_STATUS_SYNC_REQUIRED",
    "GATE_NEXT_REQUIRED_TASK_SYNC_REQUIRED",
    "GATE_REAL_ENTRY_EXECUTION_NOT_IMPL",
    "GATE_NO_REAL_ORDER_ENDPOINT",
    "GATE_NO_REAL_STOP_ENDPOINT",
    "GATE_NO_POSITION_MODIFIED",
    "GATE_G20_NOT_LIFTED",
    "DemoTinyGuardedEntryRealExecutionAdapterImplementationReadinessReview",
    "TinyGuardedEntryRealExecutionAdapterImplementationReadinessReviewResult",
]
