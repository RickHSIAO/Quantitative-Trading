"""
src/demo_tiny_guarded_entry_real_execution_adapter_design.py
TASK-014AN: Guarded Entry Real Execution Adapter Design.

Adapter-design-only module. This task documents the contract / inputs /
outputs / boundaries / forbidden surfaces / fail-closed policy / audit
schema for the FUTURE real tiny entry execution adapter. This module
DOES NOT implement the adapter, does not import any sender / private
client / network primitive, does not call /v5/order/create, does not
call /v5/position/trading-stop, does not read secrets, does not sign
anything, does not lift TASK-014L G20, does not validate any token /
phrase / approval input, does not treat any token / phrase / input as
authorization, does not touch any existing protected demo position,
and does not auto-commit / auto-push git.

Inputs: 23 upstream artifacts (the 22 from TASK-014AM + AM's own
        guarded entry real execution manual approval gate output).

Stages:
  stage_0_artifact_preflight
  stage_1_adapter_design_scope
  stage_2_adapter_contract_design
  stage_3_adapter_input_schema_design
  stage_4_adapter_output_schema_design
  stage_5_entry_payload_design_preview
  stage_6_secret_and_signature_boundary_design
  stage_7_stop_cleanup_boundary_design
  stage_8_forbidden_execution_surface_design
  stage_9_failure_and_abort_adapter_design
  stage_10_documentation_sync_review
  stage_11_final_adapter_design_verdict

Modes:
  adapter_design_checklist     --- default
  adapter_design_approval      --- --allow-adapter-design-approval
  real_entry_execution_guard   --- --allow-real-entry-execution
  fail_closed                  --- upstream failed

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

STAGE_0_ARTIFACT_PREFLIGHT                  = "stage_0_artifact_preflight"
STAGE_1_ADAPTER_DESIGN_SCOPE                = "stage_1_adapter_design_scope"
STAGE_2_ADAPTER_CONTRACT_DESIGN             = "stage_2_adapter_contract_design"
STAGE_3_ADAPTER_INPUT_SCHEMA_DESIGN         = "stage_3_adapter_input_schema_design"
STAGE_4_ADAPTER_OUTPUT_SCHEMA_DESIGN        = "stage_4_adapter_output_schema_design"
STAGE_5_ENTRY_PAYLOAD_DESIGN_PREVIEW        = "stage_5_entry_payload_design_preview"
STAGE_6_SECRET_AND_SIGNATURE_BOUNDARY_DESIGN = "stage_6_secret_and_signature_boundary_design"
STAGE_7_STOP_CLEANUP_BOUNDARY_DESIGN        = "stage_7_stop_cleanup_boundary_design"
STAGE_8_FORBIDDEN_EXECUTION_SURFACE_DESIGN  = "stage_8_forbidden_execution_surface_design"
STAGE_9_FAILURE_AND_ABORT_ADAPTER_DESIGN    = "stage_9_failure_and_abort_adapter_design"
STAGE_10_DOCUMENTATION_SYNC_REVIEW          = "stage_10_documentation_sync_review"
STAGE_11_FINAL_ADAPTER_DESIGN_VERDICT       = "stage_11_final_adapter_design_verdict"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_ADAPTER_DESIGN_SCOPE,
    STAGE_2_ADAPTER_CONTRACT_DESIGN,
    STAGE_3_ADAPTER_INPUT_SCHEMA_DESIGN,
    STAGE_4_ADAPTER_OUTPUT_SCHEMA_DESIGN,
    STAGE_5_ENTRY_PAYLOAD_DESIGN_PREVIEW,
    STAGE_6_SECRET_AND_SIGNATURE_BOUNDARY_DESIGN,
    STAGE_7_STOP_CLEANUP_BOUNDARY_DESIGN,
    STAGE_8_FORBIDDEN_EXECUTION_SURFACE_DESIGN,
    STAGE_9_FAILURE_AND_ABORT_ADAPTER_DESIGN,
    STAGE_10_DOCUMENTATION_SYNC_REVIEW,
    STAGE_11_FINAL_ADAPTER_DESIGN_VERDICT,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_DESIGN_READY = (
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DESIGN_READY"
)
STATUS_DESIGN_READY_EXEC_DISABLED = (
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DESIGN_"
    "READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_ENTRY_NOT_IMPL = "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED         = "FAIL_CLOSED"

MODE_DESIGN_CHECKLIST        = "adapter_design_checklist"
MODE_DESIGN_APPROVAL         = "adapter_design_approval"
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

ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES: frozenset[str] = frozenset({
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_READY",
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_READY_BUT_EXECUTION_DISABLED",
    "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED",
})


# ---------------------------------------------------------------------------
# Adapter contract identity (documented only, never instantiated as sender)
# ---------------------------------------------------------------------------

ADAPTER_NAME            = "GuardedTinyEntryRealExecutionAdapter"
ADAPTER_CONTRACT_VERSION = "design_only_v1"
ADAPTER_RESPONSE_STATUS = "ADAPTER_DESIGN_NOT_SENT"
ORDER_LINK_ID_PREFIX    = "ADAPTER_DESIGN_TINY_ENTRY_"


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
DESIGN_EXPECTED_ESTIMATED_NOTIONAL  = 6.44   # qty * entry_reference
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

# General gates (36)
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
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO               = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                        = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG                    = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY    = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_NOT_SOLUSDT                  = "selected_symbol_not_solusdt"
GATE_ENTRY_MANUAL_APPROVAL_GATE_STATUS_UNACCEPTABLE = (
    "entry_manual_approval_gate_status_unacceptable"
)
GATE_ENTRY_MANUAL_APPROVAL_GATE_READINESS_EXECUTABLE = (
    "entry_manual_approval_gate_readiness_executable"
)
GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION = (
    "entry_manual_approval_gate_approval_grants_execution_true"
)
GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED = (
    "entry_manual_approval_gate_exact_phrase_validated_true"
)
GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED = (
    "entry_manual_approval_gate_approval_inputs_validated_true"
)
GATE_G20_POLICY_STILL_IN_PLACE                    = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                             = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                           = "no_secret_values_emitted_in_this_task"

# Scope gates (18)
GATE_ADAPTER_DESIGN_ONLY                          = "adapter_design_only"
GATE_ADAPTER_IMPLEMENTATION_NOT_INCLUDED          = "adapter_implementation_not_included"
GATE_ADAPTER_EXECUTION_NOT_INCLUDED               = "adapter_execution_not_included"
GATE_ENTRY_EXECUTION_NOT_INCLUDED                 = "entry_execution_not_included"
GATE_STOP_EXECUTION_NOT_INCLUDED                  = "stop_execution_not_included"
GATE_CLEANUP_EXECUTION_NOT_INCLUDED               = "cleanup_execution_not_included"
GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED        = "full_lifecycle_execution_not_included"
GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE             = "real_entry_not_implemented_scope"
GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE             = "real_execution_not_allowed_scope"
GATE_ADAPTER_DOES_NOT_GRANT_EXECUTION_SCOPE       = "adapter_does_not_grant_execution_scope"
GATE_APPROVAL_GATE_DOES_NOT_GRANT_EXECUTION_SCOPE = "approval_gate_does_not_grant_execution_scope"
GATE_SEND_NOT_ALLOWED_SCOPE                       = "send_not_allowed_scope"
GATE_ORDER_ENDPOINT_NOT_CALLED                    = "order_endpoint_not_called_in_this_task"
GATE_STOP_ENDPOINT_NOT_CALLED                     = "stop_endpoint_not_called_in_this_task"
GATE_NO_ENDPOINT_INVOKED                          = "no_endpoint_invoked_in_this_task"
GATE_NO_POSITION_MODIFIED_SCOPE                   = "no_position_modified_scope"
GATE_NO_SECRETS_LOADED                            = "no_secrets_loaded_in_this_task"
GATE_NO_G20_LIFT                                  = "no_g20_policy_lift_in_this_task"

# Adapter contract gates (13)
GATE_ADAPTER_NAME_DOCUMENTED                      = "adapter_name_documented"
GATE_ADAPTER_CONTRACT_VERSION_DOCUMENTED          = "adapter_contract_version_documented"
GATE_ADAPTER_INPUT_SCHEMA_DOCUMENTED              = "adapter_input_schema_documented"
GATE_ADAPTER_OUTPUT_SCHEMA_DOCUMENTED             = "adapter_output_schema_documented"
GATE_ADAPTER_ERROR_SCHEMA_DOCUMENTED              = "adapter_error_schema_documented"
GATE_ADAPTER_AUDIT_SCHEMA_DOCUMENTED              = "adapter_audit_schema_documented"
GATE_ADAPTER_HAS_NO_SEND_METHOD                   = "adapter_has_no_send_method"
GATE_ADAPTER_HAS_NO_PRIVATE_CLIENT                = "adapter_has_no_private_client"
GATE_ADAPTER_HAS_NO_SIGNATURE_METHOD              = "adapter_has_no_signature_method"
GATE_ADAPTER_HAS_NO_SECRET_LOADER                 = "adapter_has_no_secret_loader"
GATE_ADAPTER_HAS_NO_NETWORK_TRANSPORT             = "adapter_has_no_network_transport"
GATE_ADAPTER_CONTRACT_DOES_NOT_EXECUTE            = "adapter_contract_does_not_execute"
GATE_ADAPTER_CONTRACT_REQUIRES_FUTURE_TASK        = "adapter_contract_requires_future_task_implementation"

# Input schema gates (21)
GATE_INPUT_SYMBOL_SOLUSDT                         = "input_symbol_solusdt"
GATE_INPUT_CATEGORY_LINEAR                        = "input_category_linear"
GATE_INPUT_SIDE_BUY                               = "input_side_buy"
GATE_INPUT_QTY_0_1                                = "input_qty_0_1"
GATE_INPUT_ORDER_TYPE_MARKET                      = "input_order_type_market"
GATE_INPUT_REDUCE_ONLY_FALSE                      = "input_reduce_only_false"
GATE_INPUT_CLOSE_ON_TRIGGER_FALSE                 = "input_close_on_trigger_false"
GATE_INPUT_POSITION_IDX_ZERO                      = "input_position_idx_zero"
GATE_INPUT_MAX_NOTIONAL_10                        = "input_max_notional_10"
GATE_INPUT_EXPECTED_EXISTING_SYMBOLS              = "input_expected_existing_symbols_documented"
GATE_INPUT_EXPECTED_SOLUSDT_ABSENT                = "input_expected_solusdt_absent"
GATE_INPUT_EXPECTED_STOP_LOSS_61_18               = "input_expected_stop_loss_61_18"
GATE_INPUT_EXPECTED_TPSL_MODE_FULL                = "input_expected_tpsl_mode_full"
GATE_INPUT_EXPECTED_SL_TRIGGER_BY_MARKPRICE       = "input_expected_sl_trigger_by_markprice"
GATE_INPUT_EXPECTED_COMMIT_HASH                   = "input_expected_commit_hash_documented_only"
GATE_INPUT_APPROVAL_GATE_ARTIFACT_REQUIRED        = "input_approval_gate_artifact_required"
GATE_INPUT_MANUAL_APPROVAL_PHRASE_REQUIRED        = "input_manual_approval_phrase_required"
GATE_INPUT_TOKEN_REQUIRED_IN_FUTURE_TASK          = "input_token_required_in_future_task"
GATE_INPUT_SCHEMA_DOCUMENTED                      = "input_schema_documented"
GATE_INPUT_SCHEMA_NOT_VALIDATED                   = "input_schema_not_validated"
GATE_INPUT_SCHEMA_DOES_NOT_AUTHORIZE_EXECUTION    = "input_schema_does_not_authorize_execution"

# Output schema gates (16)
GATE_OUTPUT_RESPONSE_STATUS_ADAPTER_DESIGN_NOT_SENT = "output_response_status_adapter_design_not_sent"
GATE_OUTPUT_RESPONSE_FROM_EXCHANGE_FALSE          = "output_response_from_exchange_false"
GATE_OUTPUT_EXCHANGE_ORDER_ID_NONE                = "output_exchange_order_id_none"
GATE_OUTPUT_ORDER_LINK_ID_PREFIX                  = "output_order_link_id_prefix_documented"
GATE_OUTPUT_SEND_ALLOWED_FALSE                    = "output_send_allowed_false"
GATE_OUTPUT_ENDPOINT_CALLED_FALSE                 = "output_endpoint_called_false"
GATE_OUTPUT_ORDER_ENDPOINT_CALLED_FALSE           = "output_order_endpoint_called_false"
GATE_OUTPUT_STOP_ENDPOINT_CALLED_FALSE            = "output_stop_endpoint_called_false"
GATE_OUTPUT_REAL_PAYLOAD_FALSE                    = "output_real_payload_false"
GATE_OUTPUT_SIGNATURE_PRESENT_FALSE               = "output_signature_present_false"
GATE_OUTPUT_PRIVATE_HEADERS_EMPTY                 = "output_private_headers_empty"
GATE_OUTPUT_NO_SECRETS                            = "output_no_secrets"
GATE_OUTPUT_SANITIZED                             = "output_sanitized"
GATE_OUTPUT_NO_POSITION_MODIFIED                  = "output_no_position_modified"
GATE_OUTPUT_SCHEMA_DOCUMENTED                     = "output_schema_documented"
GATE_OUTPUT_SCHEMA_DOES_NOT_EXECUTE               = "output_schema_does_not_execute"

# Payload design preview gates (19)
GATE_PAYLOAD_PREVIEW_ONLY                         = "payload_preview_only"
GATE_PAYLOAD_ADAPTER_DESIGN_ONLY                  = "payload_adapter_design_only"
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

# Secret / signature boundary gates (12)
GATE_SECRETS_REQUIRED_IN_FUTURE_TASK              = "secrets_required_in_future_task"
GATE_SECRETS_LOADED_FALSE                         = "secrets_loaded_false_in_this_task"
GATE_ENV_READ_FALSE                               = "env_read_false_in_this_task"
GATE_DOTENV_CALLED_FALSE                          = "dotenv_called_false_in_this_task"
GATE_HMAC_SIGNATURE_FALSE                         = "hmac_signature_false_in_this_task"
GATE_SIGNATURE_HEADER_FALSE                       = "signature_header_false_in_this_task"
GATE_PRIVATE_HEADERS_FALSE                        = "private_headers_false_in_this_task"
GATE_API_KEY_VALUE_NOT_OBSERVED                   = "api_key_value_not_observed_in_this_task"
GATE_API_SECRET_VALUE_NOT_OBSERVED                = "api_secret_value_not_observed_in_this_task"
GATE_SIGNING_REQUIRES_FUTURE_TASK                 = "signing_requires_future_task"
GATE_SECRET_REDACTION_REQUIRED                    = "secret_redaction_required"
GATE_FORBIDDEN_LOG_FIELDS_DOCUMENTED              = "forbidden_log_fields_documented"

# Stop/cleanup gates (13)
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
GATE_FUTURE_ADAPTER_MUST_NOT_AUTO_ATTACH_STOP     = "future_adapter_must_not_auto_attach_stop"
GATE_FUTURE_ADAPTER_REQUIRES_SEPARATE_STOP_TASK   = "future_adapter_must_require_separate_stop_task"

# Forbidden execution surface gates (20)
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

# Failure gates (19)
GATE_MISSING_ARTIFACT_FAIL_CLOSED                 = "missing_artifact_fail_closed"
GATE_STALE_READONLY_FAIL_CLOSED                   = "stale_readonly_fail_closed"
GATE_MANUAL_APPROVAL_GATE_STALE_FAIL_CLOSED       = "manual_approval_gate_stale_fail_closed"
GATE_APPROVAL_GRANTS_EXECUTION_TRUE_FAIL_CLOSED   = "approval_grants_execution_true_fail_closed"
GATE_PHRASE_ALREADY_VALIDATED_FAIL_CLOSED         = "phrase_already_validated_fail_closed"
GATE_INPUTS_ALREADY_VALIDATED_FAIL_CLOSED         = "inputs_already_validated_fail_closed"
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
GATE_EXECUTABLE_ADAPTER_DETECTED_FAIL_CLOSED      = "executable_adapter_detected_fail_closed"
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
    GATE_ENTRY_MANUAL_APPROVAL_GATE_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_STATUS_UNACCEPTABLE,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_READINESS_EXECUTABLE,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED,
    GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
    GATE_SOLUSDT_EXISTS_FAIL_CLOSED,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyGuardedEntryRealExecutionAdapterDesignResult:
    """Read-only outcome of one guarded entry real execution adapter design review."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    adapter_design_scope:               dict[str, Any] = field(default_factory=dict)
    adapter_contract_design:            dict[str, Any] = field(default_factory=dict)
    adapter_input_schema_design:        dict[str, Any] = field(default_factory=dict)
    adapter_output_schema_design:       dict[str, Any] = field(default_factory=dict)
    entry_payload_design_preview:       dict[str, Any] = field(default_factory=dict)
    secret_and_signature_boundary_design: dict[str, Any] = field(default_factory=dict)
    stop_cleanup_boundary_design:       dict[str, Any] = field(default_factory=dict)
    forbidden_execution_surface_design: dict[str, Any] = field(default_factory=dict)
    failure_and_abort_adapter_design:   dict[str, Any] = field(default_factory=dict)
    documentation_sync_review:          dict[str, Any] = field(default_factory=dict)
    audit_artifacts:                    dict[str, Any] = field(default_factory=dict)
    final_adapter_design_verdict:       dict[str, Any] = field(default_factory=dict)

    adapter_name:                 str = ADAPTER_NAME
    adapter_contract_version:     str = ADAPTER_CONTRACT_VERSION
    order_link_id_prefix:         str = ORDER_LINK_ID_PREFIX

    adapter_design_approval_allowed:   bool = False
    real_entry_execution_requested:    bool = False
    real_execution_allowed:            bool = False
    real_entry_implemented:            bool = False
    guarded_entry_real_execution_adapter_design: bool = True
    adapter_design_only:               bool = True
    adapter_implementation_included:   bool = False
    adapter_execution_included:        bool = False
    adapter_grants_execution:          bool = False
    approval_gate_grants_execution:    bool = False
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
    upstream_entry_manual_approval_gate_status: str = ""
    upstream_entry_manual_approval_gate_readiness_conclusion: str = ""
    upstream_entry_manual_approval_gate_approval_grants_execution: bool = False
    upstream_entry_manual_approval_gate_exact_phrase_validated: bool = False
    upstream_entry_manual_approval_gate_approval_inputs_validated: bool = False

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = "TASK-014AO_guarded_entry_real_execution_adapter_dry_run"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                                 self.timestamp_utc,
            "timestamp_utc":                             self.timestamp_utc,
            "mode":                                      self.mode,
            "selected_symbol":                           self.selected_symbol,
            "existing_position_symbols":                 list(self.existing_position_symbols),
            "stages":                                    {k: dict(v) for k, v in self.stages.items()},
            "stage_order":                               list(self.stage_order),
            "adapter_design_scope":                      dict(self.adapter_design_scope),
            "adapter_contract_design":                   dict(self.adapter_contract_design),
            "adapter_input_schema_design":               dict(self.adapter_input_schema_design),
            "adapter_output_schema_design":              dict(self.adapter_output_schema_design),
            "entry_payload_design_preview":              dict(self.entry_payload_design_preview),
            "secret_and_signature_boundary_design":      dict(self.secret_and_signature_boundary_design),
            "stop_cleanup_boundary_design":              dict(self.stop_cleanup_boundary_design),
            "forbidden_execution_surface_design":        dict(self.forbidden_execution_surface_design),
            "failure_and_abort_adapter_design":          dict(self.failure_and_abort_adapter_design),
            "documentation_sync_review":                 dict(self.documentation_sync_review),
            "audit_artifacts":                           dict(self.audit_artifacts),
            "final_adapter_design_verdict":              dict(self.final_adapter_design_verdict),
            "adapter_name":                              self.adapter_name,
            "adapter_contract_version":                  self.adapter_contract_version,
            "order_link_id_prefix":                      self.order_link_id_prefix,
            "adapter_design_approval_allowed":           self.adapter_design_approval_allowed,
            "real_entry_execution_requested":            self.real_entry_execution_requested,
            "real_execution_allowed":                    self.real_execution_allowed,
            "real_entry_implemented":                    self.real_entry_implemented,
            "guarded_entry_real_execution_adapter_design":
                self.guarded_entry_real_execution_adapter_design,
            "adapter_design_only":                       self.adapter_design_only,
            "adapter_implementation_included":           self.adapter_implementation_included,
            "adapter_execution_included":                self.adapter_execution_included,
            "adapter_grants_execution":                  self.adapter_grants_execution,
            "approval_gate_grants_execution":            self.approval_gate_grants_execution,
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
            "upstream_entry_manual_approval_gate_status":
                self.upstream_entry_manual_approval_gate_status,
            "upstream_entry_manual_approval_gate_readiness_conclusion":
                self.upstream_entry_manual_approval_gate_readiness_conclusion,
            "upstream_entry_manual_approval_gate_approval_grants_execution":
                self.upstream_entry_manual_approval_gate_approval_grants_execution,
            "upstream_entry_manual_approval_gate_exact_phrase_validated":
                self.upstream_entry_manual_approval_gate_exact_phrase_validated,
            "upstream_entry_manual_approval_gate_approval_inputs_validated":
                self.upstream_entry_manual_approval_gate_approval_inputs_validated,
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
# Guarded entry real execution adapter design
# ---------------------------------------------------------------------------

class DemoTinyGuardedEntryRealExecutionAdapterDesign:
    """
    Pure-computation guarded entry real execution adapter design.
    Re-reviews 23 upstream artifacts and emits the adapter-design
    verdict. Never opens a socket, reads no environment variables,
    performs no HMAC signing, never validates any token / phrase /
    approval input, never treats them as authorization, never
    auto-commits / auto-pushes git, never exposes any adapter `send`
    method, and NEVER invokes the order-create or trading-stop
    endpoints.

    --allow-adapter-design-approval --> status promoted to
        TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DESIGN_READY_BUT_EXECUTION_DISABLED

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
        symbol:                               str  = DEFAULT_SELECTED_SYMBOL,
        expected_commit_hash:                 str  = "",
        current_commit_hash:                  str  = "",
        allow_adapter_design_approval:        bool = False,
        allow_real_entry_execution:           bool = False,
        _now:                                 datetime | None = None,
    ) -> TinyGuardedEntryRealExecutionAdapterDesignResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_entry_execution:
            mode = MODE_REAL_ENTRY_EXEC_GUARD
        elif allow_adapter_design_approval:
            mode = MODE_DESIGN_APPROVAL
        else:
            mode = MODE_DESIGN_CHECKLIST

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
        entry_approval_gate_present = isinstance(entry_manual_approval_gate, dict) and bool(entry_manual_approval_gate)

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
        entry_approval_gate_status  = _safe_str((entry_manual_approval_gate or {}).get("status", ""))
        entry_approval_gate_readiness = _safe_str(
            (entry_manual_approval_gate or {}).get("readiness_conclusion", "")
        )
        entry_approval_gate_grants = _safe_bool(
            (entry_manual_approval_gate or {}).get("approval_grants_execution", False)
        )
        entry_approval_gate_phrase = _safe_bool(
            (entry_manual_approval_gate or {}).get("exact_phrase_validated", False)
        )
        entry_approval_gate_inputs = _safe_bool(
            (entry_manual_approval_gate or {}).get("approval_inputs_validated", False)
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
        if not entry_approval_gate_present:
            blocked.append(GATE_ENTRY_MANUAL_APPROVAL_GATE_MISSING)

        if readonly_present and endpoint_family and endpoint_family != EXPECTED_ENDPOINT_FAMILY:
            blocked.append(GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO)
        if readonly_present and account_mode and account_mode != EXPECTED_ACCOUNT_MODE:
            blocked.append(GATE_ACCOUNT_MODE_NOT_DEMO)
        if readonly_present and proof_strength and proof_strength != EXPECTED_PROOF_STRENGTH:
            blocked.append(GATE_PROOF_STRENGTH_NOT_STRONG)
        if recon_present and position_details_source and position_details_source != EXPECTED_POSITION_DETAILS_SOURCE:
            blocked.append(GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY)

        if entry_approval_gate_present and entry_approval_gate_status and (
            entry_approval_gate_status not in ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES
        ):
            blocked.append(GATE_ENTRY_MANUAL_APPROVAL_GATE_STATUS_UNACCEPTABLE)
        if entry_approval_gate_present and entry_approval_gate_readiness and (
            entry_approval_gate_readiness != READINESS_CONCLUSION_NOT_EXECUTABLE
        ):
            blocked.append(GATE_ENTRY_MANUAL_APPROVAL_GATE_READINESS_EXECUTABLE)
        if entry_approval_gate_present and entry_approval_gate_grants:
            blocked.append(GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION)
        if entry_approval_gate_present and entry_approval_gate_phrase:
            blocked.append(GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED)
        if entry_approval_gate_present and entry_approval_gate_inputs:
            blocked.append(GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED)

        if sym and sym != DESIGN_EXPECTED_SYMBOL:
            blocked.append(GATE_SELECTED_SYMBOL_NOT_SOLUSDT)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 23 upstream artifacts + runtime proof envelope + manual approval gate status / readiness / approval flags.",
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
            "entry_manual_approval_gate_present":       entry_approval_gate_present,
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
            "entry_manual_approval_gate_status_observed": entry_approval_gate_status,
            "entry_manual_approval_gate_status_acceptable": sorted(
                ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES
            ),
            "entry_manual_approval_gate_readiness_observed": entry_approval_gate_readiness,
            "entry_manual_approval_gate_readiness_expected": READINESS_CONCLUSION_NOT_EXECUTABLE,
            "entry_manual_approval_gate_approval_grants_execution_observed": entry_approval_gate_grants,
            "entry_manual_approval_gate_approval_grants_execution_expected": False,
            "entry_manual_approval_gate_exact_phrase_validated_observed": entry_approval_gate_phrase,
            "entry_manual_approval_gate_exact_phrase_validated_expected": False,
            "entry_manual_approval_gate_approval_inputs_validated_observed": entry_approval_gate_inputs,
            "entry_manual_approval_gate_approval_inputs_validated_expected": False,
            "selected_symbol":                          sym,
            "selected_symbol_expected":                 DESIGN_EXPECTED_SYMBOL,
            "current_task_real_execution_allowed":      False,
        }

        # ===============================================================
        # stage_1_adapter_design_scope
        # ===============================================================
        adapter_design_scope: dict[str, Any] = {
            "guarded_entry_real_execution_adapter_design": True,
            "adapter_design_only":                  True,
            "adapter_implementation_included":      False,
            "adapter_execution_included":           False,
            "entry_execution_included":             False,
            "stop_execution_included":              False,
            "cleanup_execution_included":           False,
            "full_lifecycle_execution_included":    False,
            "real_entry_implemented":               False,
            "real_execution_allowed":               False,
            "adapter_grants_execution":             False,
            "approval_gate_grants_execution":       False,
            "send_allowed":                         False,
            "order_endpoint_called":                False,
            "stop_endpoint_called":                 False,
            "no_endpoint_invoked_in_this_task":     True,
            "no_position_modified":                 True,
            "no_secrets_loaded":                    True,
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "next_required_task":                   "TASK-014AO_guarded_entry_real_execution_adapter_dry_run",
            "scope_summary": (
                "TASK-014AN only designs the contract / inputs / outputs / "
                "boundaries / forbidden surfaces / fail-closed policy / "
                "audit schema of the FUTURE real tiny entry execution "
                "adapter. It does not implement the adapter, does not "
                "build any sender or private client, never validates any "
                "token / phrase / approval input, never treats them as "
                "authorization, never sends an order, never calls any "
                "endpoint, never modifies any position, never lifts G20, "
                "never loads any secret, and never auto-commits / "
                "auto-pushes git."
            ),
        }
        stages[STAGE_1_ADAPTER_DESIGN_SCOPE] = {
            "stage":   STAGE_1_ADAPTER_DESIGN_SCOPE,
            "summary": "Assert guarded entry real execution adapter design scope (design-only).",
            "adapter_design_scope":                 adapter_design_scope,
        }
        blocked.append(GATE_ADAPTER_DESIGN_ONLY)
        blocked.append(GATE_ADAPTER_IMPLEMENTATION_NOT_INCLUDED)
        blocked.append(GATE_ADAPTER_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_ENTRY_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_STOP_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_CLEANUP_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED)
        blocked.append(GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE)
        blocked.append(GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE)
        blocked.append(GATE_ADAPTER_DOES_NOT_GRANT_EXECUTION_SCOPE)
        blocked.append(GATE_APPROVAL_GATE_DOES_NOT_GRANT_EXECUTION_SCOPE)
        blocked.append(GATE_SEND_NOT_ALLOWED_SCOPE)
        blocked.append(GATE_ORDER_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_STOP_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_NO_ENDPOINT_INVOKED)
        blocked.append(GATE_NO_POSITION_MODIFIED_SCOPE)
        blocked.append(GATE_NO_SECRETS_LOADED)
        blocked.append(GATE_NO_G20_LIFT)

        # ===============================================================
        # stage_2_adapter_contract_design
        # ===============================================================
        adapter_contract_design: dict[str, Any] = {
            "adapter_name":                         ADAPTER_NAME,
            "adapter_contract_version":             ADAPTER_CONTRACT_VERSION,
            "adapter_input_schema_documented":      True,
            "adapter_output_schema_documented":     True,
            "adapter_error_schema_documented":      True,
            "adapter_audit_schema_documented":      True,
            "adapter_has_no_send_method":           True,
            "adapter_has_no_private_client":        True,
            "adapter_has_no_signature_method":      True,
            "adapter_has_no_secret_loader":         True,
            "adapter_has_no_network_transport":     True,
            "adapter_contract_does_not_execute":    True,
            "adapter_contract_requires_future_task_implementation": True,
            "design_only_contract_note": (
                "Contract describes the FUTURE adapter's surface but does "
                "not include any callable send / sign / network method in "
                "this task. Any future implementation must continue to "
                "respect TASK-014L sender G20 and every documented "
                "forbidden execution surface gate."
            ),
        }
        stages[STAGE_2_ADAPTER_CONTRACT_DESIGN] = {
            "stage":   STAGE_2_ADAPTER_CONTRACT_DESIGN,
            "summary": "Adapter contract design (design-only; no send method / private client / signature / secret loader / network transport).",
            "adapter_contract_design":              adapter_contract_design,
        }
        blocked.append(GATE_ADAPTER_NAME_DOCUMENTED)
        blocked.append(GATE_ADAPTER_CONTRACT_VERSION_DOCUMENTED)
        blocked.append(GATE_ADAPTER_INPUT_SCHEMA_DOCUMENTED)
        blocked.append(GATE_ADAPTER_OUTPUT_SCHEMA_DOCUMENTED)
        blocked.append(GATE_ADAPTER_ERROR_SCHEMA_DOCUMENTED)
        blocked.append(GATE_ADAPTER_AUDIT_SCHEMA_DOCUMENTED)
        blocked.append(GATE_ADAPTER_HAS_NO_SEND_METHOD)
        blocked.append(GATE_ADAPTER_HAS_NO_PRIVATE_CLIENT)
        blocked.append(GATE_ADAPTER_HAS_NO_SIGNATURE_METHOD)
        blocked.append(GATE_ADAPTER_HAS_NO_SECRET_LOADER)
        blocked.append(GATE_ADAPTER_HAS_NO_NETWORK_TRANSPORT)
        blocked.append(GATE_ADAPTER_CONTRACT_DOES_NOT_EXECUTE)
        blocked.append(GATE_ADAPTER_CONTRACT_REQUIRES_FUTURE_TASK)

        # ===============================================================
        # stage_3_adapter_input_schema_design
        # ===============================================================
        adapter_input_schema_design: dict[str, Any] = {
            "symbol":                                DESIGN_EXPECTED_SYMBOL,
            "category":                              DESIGN_EXPECTED_CATEGORY,
            "side":                                  DESIGN_EXPECTED_ENTRY_SIDE,
            "qty":                                   DESIGN_EXPECTED_QTY,
            "orderType":                             DESIGN_EXPECTED_ORDER_TYPE,
            "reduceOnly":                            DESIGN_EXPECTED_REDUCE_ONLY,
            "closeOnTrigger":                        DESIGN_EXPECTED_CLOSE_ON_TRIGGER,
            "positionIdx":                           DESIGN_EXPECTED_POSITION_IDX,
            "max_notional_usdt":                     DESIGN_EXPECTED_MAX_NOTIONAL_USDT,
            "expected_existing_symbols":             list(EXISTING_POSITION_SYMBOLS),
            "expected_existing_symbols_doc_order":   list(EXISTING_POSITION_SYMBOLS_DOC_ORDER),
            "expected_solusdt_absent":               True,
            "expected_stop_loss":                    DESIGN_EXPECTED_STOP_LOSS,
            "expected_tpsl_mode":                    DESIGN_EXPECTED_TPSL_MODE,
            "expected_sl_trigger_by":                DESIGN_EXPECTED_SL_TRIGGER_BY,
            "expected_commit_hash_documented":       True,
            "approval_gate_artifact_required":       True,
            "manual_approval_phrase_required":       True,
            "token_required_in_future_task":         True,
            "input_schema_documented":               True,
            "input_schema_validated":                False,
            "input_schema_does_not_authorize_execution": True,
        }
        stages[STAGE_3_ADAPTER_INPUT_SCHEMA_DESIGN] = {
            "stage":   STAGE_3_ADAPTER_INPUT_SCHEMA_DESIGN,
            "summary": "Adapter input schema design (design-only; never validated; does not authorize execution).",
            "adapter_input_schema_design":          adapter_input_schema_design,
        }
        blocked.append(GATE_INPUT_SYMBOL_SOLUSDT)
        blocked.append(GATE_INPUT_CATEGORY_LINEAR)
        blocked.append(GATE_INPUT_SIDE_BUY)
        blocked.append(GATE_INPUT_QTY_0_1)
        blocked.append(GATE_INPUT_ORDER_TYPE_MARKET)
        blocked.append(GATE_INPUT_REDUCE_ONLY_FALSE)
        blocked.append(GATE_INPUT_CLOSE_ON_TRIGGER_FALSE)
        blocked.append(GATE_INPUT_POSITION_IDX_ZERO)
        blocked.append(GATE_INPUT_MAX_NOTIONAL_10)
        blocked.append(GATE_INPUT_EXPECTED_EXISTING_SYMBOLS)
        blocked.append(GATE_INPUT_EXPECTED_SOLUSDT_ABSENT)
        blocked.append(GATE_INPUT_EXPECTED_STOP_LOSS_61_18)
        blocked.append(GATE_INPUT_EXPECTED_TPSL_MODE_FULL)
        blocked.append(GATE_INPUT_EXPECTED_SL_TRIGGER_BY_MARKPRICE)
        blocked.append(GATE_INPUT_EXPECTED_COMMIT_HASH)
        blocked.append(GATE_INPUT_APPROVAL_GATE_ARTIFACT_REQUIRED)
        blocked.append(GATE_INPUT_MANUAL_APPROVAL_PHRASE_REQUIRED)
        blocked.append(GATE_INPUT_TOKEN_REQUIRED_IN_FUTURE_TASK)
        blocked.append(GATE_INPUT_SCHEMA_DOCUMENTED)
        blocked.append(GATE_INPUT_SCHEMA_NOT_VALIDATED)
        blocked.append(GATE_INPUT_SCHEMA_DOES_NOT_AUTHORIZE_EXECUTION)

        # ===============================================================
        # stage_4_adapter_output_schema_design
        # ===============================================================
        adapter_output_schema_design: dict[str, Any] = {
            "response_status":                       ADAPTER_RESPONSE_STATUS,
            "response_from_exchange":                False,
            "exchange_order_id":                     None,
            "order_link_id_prefix":                  ORDER_LINK_ID_PREFIX,
            "send_allowed":                          False,
            "endpoint_called":                       False,
            "order_endpoint_called":                 False,
            "stop_endpoint_called":                  False,
            "real_payload":                          False,
            "signature_present":                     False,
            "private_headers":                       [],
            "no_secrets":                            True,
            "sanitized":                             True,
            "no_position_modified":                  True,
            "output_schema_documented":              True,
            "output_schema_does_not_execute":        True,
            "error_schema_summary": (
                "Errors are described as docstring/comment-only categories "
                "(network unavailable / signature mismatch / endpoint "
                "rejection / qty mismatch / notional cap exceeded / "
                "protected position mismatch / live endpoint fallback "
                "detected). No exception classes are instantiated or "
                "raised in this task."
            ),
        }
        stages[STAGE_4_ADAPTER_OUTPUT_SCHEMA_DESIGN] = {
            "stage":   STAGE_4_ADAPTER_OUTPUT_SCHEMA_DESIGN,
            "summary": "Adapter output / error / audit schema design (design-only; never executes; no exchange response).",
            "adapter_output_schema_design":         adapter_output_schema_design,
        }
        blocked.append(GATE_OUTPUT_RESPONSE_STATUS_ADAPTER_DESIGN_NOT_SENT)
        blocked.append(GATE_OUTPUT_RESPONSE_FROM_EXCHANGE_FALSE)
        blocked.append(GATE_OUTPUT_EXCHANGE_ORDER_ID_NONE)
        blocked.append(GATE_OUTPUT_ORDER_LINK_ID_PREFIX)
        blocked.append(GATE_OUTPUT_SEND_ALLOWED_FALSE)
        blocked.append(GATE_OUTPUT_ENDPOINT_CALLED_FALSE)
        blocked.append(GATE_OUTPUT_ORDER_ENDPOINT_CALLED_FALSE)
        blocked.append(GATE_OUTPUT_STOP_ENDPOINT_CALLED_FALSE)
        blocked.append(GATE_OUTPUT_REAL_PAYLOAD_FALSE)
        blocked.append(GATE_OUTPUT_SIGNATURE_PRESENT_FALSE)
        blocked.append(GATE_OUTPUT_PRIVATE_HEADERS_EMPTY)
        blocked.append(GATE_OUTPUT_NO_SECRETS)
        blocked.append(GATE_OUTPUT_SANITIZED)
        blocked.append(GATE_OUTPUT_NO_POSITION_MODIFIED)
        blocked.append(GATE_OUTPUT_SCHEMA_DOCUMENTED)
        blocked.append(GATE_OUTPUT_SCHEMA_DOES_NOT_EXECUTE)

        # ===============================================================
        # stage_5_entry_payload_design_preview
        # ===============================================================
        sym_eff = sym or DESIGN_EXPECTED_SYMBOL
        entry_payload_design_preview: dict[str, Any] = {
            "preview_only":                          True,
            "adapter_design_only":                   True,
            "send_allowed":                          False,
            "endpoint_called":                       False,
            "real_payload":                          False,
            "signature_present":                     False,
            "private_headers":                       [],
            "endpoint_path_ref":                     ORDER_CREATE_PATH_REF,
            "base_url_ref":                          BASE_URL_DEMO_REF,
            "demo_endpoint_allowlist":               list(DEMO_ENDPOINT_ALLOWLIST),
            "live_endpoint_denylist":                list(LIVE_ENDPOINT_DENYLIST),
            "category":                              DESIGN_EXPECTED_CATEGORY,
            "symbol":                                sym_eff,
            "side":                                  DESIGN_EXPECTED_ENTRY_SIDE,
            "orderType":                             DESIGN_EXPECTED_ORDER_TYPE,
            "qty":                                   DESIGN_EXPECTED_QTY,
            "reduceOnly":                            DESIGN_EXPECTED_REDUCE_ONLY,
            "closeOnTrigger":                        DESIGN_EXPECTED_CLOSE_ON_TRIGGER,
            "positionIdx":                           DESIGN_EXPECTED_POSITION_IDX,
            "orderLinkId_prefix":                    ORDER_LINK_ID_PREFIX,
            "sender_adapter_invoked":                False,
        }
        stages[STAGE_5_ENTRY_PAYLOAD_DESIGN_PREVIEW] = {
            "stage":   STAGE_5_ENTRY_PAYLOAD_DESIGN_PREVIEW,
            "summary": "Entry payload design preview (design-only; never sent; never signed; sender adapter not invoked).",
            "entry_payload_design_preview":         entry_payload_design_preview,
        }
        blocked.append(GATE_PAYLOAD_PREVIEW_ONLY)
        blocked.append(GATE_PAYLOAD_ADAPTER_DESIGN_ONLY)
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
        # stage_6_secret_and_signature_boundary_design
        # ===============================================================
        secret_and_signature_boundary_design: dict[str, Any] = {
            "secrets_required_in_future_task":       True,
            "secrets_loaded_in_this_task":           False,
            "env_read_in_this_task":                 False,
            "dotenv_called_in_this_task":            False,
            "hmac_signature_created":                False,
            "signature_header_created":              False,
            "private_headers_created":               False,
            "api_key_value_observed":                False,
            "api_secret_value_observed":             False,
            "signing_requires_future_task":          True,
            "secret_redaction_required":             True,
            "forbidden_log_fields":                  list(FORBIDDEN_LOG_FIELDS),
        }
        stages[STAGE_6_SECRET_AND_SIGNATURE_BOUNDARY_DESIGN] = {
            "stage":   STAGE_6_SECRET_AND_SIGNATURE_BOUNDARY_DESIGN,
            "summary": "Secret / signature boundary design (no secrets loaded; no signing; future-task only).",
            "secret_and_signature_boundary_design": secret_and_signature_boundary_design,
        }
        blocked.append(GATE_SECRETS_REQUIRED_IN_FUTURE_TASK)
        blocked.append(GATE_SECRETS_LOADED_FALSE)
        blocked.append(GATE_ENV_READ_FALSE)
        blocked.append(GATE_DOTENV_CALLED_FALSE)
        blocked.append(GATE_HMAC_SIGNATURE_FALSE)
        blocked.append(GATE_SIGNATURE_HEADER_FALSE)
        blocked.append(GATE_PRIVATE_HEADERS_FALSE)
        blocked.append(GATE_API_KEY_VALUE_NOT_OBSERVED)
        blocked.append(GATE_API_SECRET_VALUE_NOT_OBSERVED)
        blocked.append(GATE_SIGNING_REQUIRES_FUTURE_TASK)
        blocked.append(GATE_SECRET_REDACTION_REQUIRED)
        blocked.append(GATE_FORBIDDEN_LOG_FIELDS_DOCUMENTED)

        # ===============================================================
        # stage_7_stop_cleanup_boundary_design
        # ===============================================================
        stop_cleanup_boundary_design: dict[str, Any] = {
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
            "entry_success_without_stop_attach_policy": "MANUAL_REVIEW_REQUIRED",
            "future_adapter_must_not_auto_attach_stop": True,
            "future_adapter_must_require_separate_stop_task": True,
        }
        stages[STAGE_7_STOP_CLEANUP_BOUNDARY_DESIGN] = {
            "stage":   STAGE_7_STOP_CLEANUP_BOUNDARY_DESIGN,
            "summary": "Stop attach / cleanup boundary design (separate manual boundaries; future adapter must not auto-attach).",
            "stop_cleanup_boundary_design":         stop_cleanup_boundary_design,
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
        blocked.append(GATE_FUTURE_ADAPTER_MUST_NOT_AUTO_ATTACH_STOP)
        blocked.append(GATE_FUTURE_ADAPTER_REQUIRES_SEPARATE_STOP_TASK)

        # ===============================================================
        # stage_8_forbidden_execution_surface_design
        # ===============================================================
        forbidden_execution_surface_design: dict[str, Any] = {
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
        }
        stages[STAGE_8_FORBIDDEN_EXECUTION_SURFACE_DESIGN] = {
            "stage":   STAGE_8_FORBIDDEN_EXECUTION_SURFACE_DESIGN,
            "summary": "Forbidden execution surface design (no sender / private client / signed request / network / automation / executable adapter / send method).",
            "forbidden_execution_surface_design":   forbidden_execution_surface_design,
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

        # ===============================================================
        # stage_9_failure_and_abort_adapter_design
        # ===============================================================
        solusdt_in_existing = DESIGN_EXPECTED_SYMBOL in existing_symbols
        if solusdt_in_existing:
            blocked.append(GATE_SOLUSDT_EXISTS_FAIL_CLOSED)

        failure_and_abort_adapter_design: dict[str, Any] = {
            "missing_artifact":                      "FAIL_CLOSED",
            "stale_readonly":                        "FAIL_CLOSED",
            "manual_approval_gate_stale":            "FAIL_CLOSED",
            "approval_grants_execution_true":        "FAIL_CLOSED",
            "phrase_already_validated":              "FAIL_CLOSED",
            "inputs_already_validated":              "FAIL_CLOSED",
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
            "executable_adapter_detected":           "FAIL_CLOSED",
            "any_g20_lift_attempt":                  "FAIL_CLOSED",
            "any_auto_execution_attempt":            "FAIL_CLOSED",
            "manual_intervention_only":              True,
        }
        stages[STAGE_9_FAILURE_AND_ABORT_ADAPTER_DESIGN] = {
            "stage":   STAGE_9_FAILURE_AND_ABORT_ADAPTER_DESIGN,
            "summary": "Failure / abort adapter design (FAIL_CLOSED / MANUAL_REVIEW_REQUIRED only; no auto-progression).",
            "failure_and_abort_adapter_design":     failure_and_abort_adapter_design,
        }
        blocked.append(GATE_MISSING_ARTIFACT_FAIL_CLOSED)
        blocked.append(GATE_STALE_READONLY_FAIL_CLOSED)
        blocked.append(GATE_MANUAL_APPROVAL_GATE_STALE_FAIL_CLOSED)
        blocked.append(GATE_APPROVAL_GRANTS_EXECUTION_TRUE_FAIL_CLOSED)
        blocked.append(GATE_PHRASE_ALREADY_VALIDATED_FAIL_CLOSED)
        blocked.append(GATE_INPUTS_ALREADY_VALIDATED_FAIL_CLOSED)
        blocked.append(GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW_FAIL)
        blocked.append(GATE_NOTIONAL_CAP_EXCEEDED_FAIL_CLOSED)
        blocked.append(GATE_QTY_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_SIDE_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_REDUCE_ONLY_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_SECRET_EMISSION_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_NETWORK_PRIMITIVE_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_SENDER_ADAPTER_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_EXECUTABLE_ADAPTER_DETECTED_FAIL_CLOSED)
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
            "next_required_task":                    "TASK-014AO_guarded_entry_real_execution_adapter_dry_run",
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
        # stage_11_final_adapter_design_verdict
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
        elif allow_adapter_design_approval:
            failed_stage = ""
            status_out = STATUS_DESIGN_READY_EXEC_DISABLED
            mode_out   = MODE_DESIGN_APPROVAL
        else:
            failed_stage = ""
            status_out = STATUS_DESIGN_READY
            mode_out   = MODE_DESIGN_CHECKLIST

        final_adapter_design_verdict: dict[str, Any] = {
            "adapter_design_approval_allowed":       allow_adapter_design_approval,
            "real_entry_execution_requested":        bool(allow_real_entry_execution),
            "real_execution_allowed":                False,
            "real_entry_implemented":                False,
            "guarded_entry_real_execution_adapter_design": True,
            "adapter_design_only":                   True,
            "adapter_implementation_included":       False,
            "adapter_execution_included":            False,
            "adapter_grants_execution":              False,
            "approval_gate_grants_execution":        False,
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
            "next_required_task":                    "TASK-014AO_guarded_entry_real_execution_adapter_dry_run",
        }

        audit_artifacts: dict[str, Any] = {
            "adapter_design_scope":                  dict(adapter_design_scope),
            "adapter_contract_design":               dict(adapter_contract_design),
            "adapter_input_schema_design":           dict(adapter_input_schema_design),
            "adapter_output_schema_design":          dict(adapter_output_schema_design),
            "entry_payload_design_preview":          dict(entry_payload_design_preview),
            "secret_and_signature_boundary_design": dict(secret_and_signature_boundary_design),
            "stop_cleanup_boundary_design":          dict(stop_cleanup_boundary_design),
            "forbidden_execution_surface_design":    dict(forbidden_execution_surface_design),
            "failure_and_abort_adapter_design":      dict(failure_and_abort_adapter_design),
            "documentation_sync_review":             dict(documentation_sync_review),
            "final_adapter_design_verdict":          dict(final_adapter_design_verdict),
            "response_status":                       ADAPTER_RESPONSE_STATUS,
            "response_from_exchange":                False,
            "sanitized":                             True,
            "no_secrets":                            True,
            "forbidden_log_fields":                  list(FORBIDDEN_LOG_FIELDS),
        }

        stages[STAGE_11_FINAL_ADAPTER_DESIGN_VERDICT] = {
            "stage":   STAGE_11_FINAL_ADAPTER_DESIGN_VERDICT,
            "summary": "Final adapter design verdict + permanent execution guard.",
            "final_adapter_design_verdict":         final_adapter_design_verdict,
        }

        return TinyGuardedEntryRealExecutionAdapterDesignResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            adapter_design_scope=adapter_design_scope,
            adapter_contract_design=adapter_contract_design,
            adapter_input_schema_design=adapter_input_schema_design,
            adapter_output_schema_design=adapter_output_schema_design,
            entry_payload_design_preview=entry_payload_design_preview,
            secret_and_signature_boundary_design=secret_and_signature_boundary_design,
            stop_cleanup_boundary_design=stop_cleanup_boundary_design,
            forbidden_execution_surface_design=forbidden_execution_surface_design,
            failure_and_abort_adapter_design=failure_and_abort_adapter_design,
            documentation_sync_review=documentation_sync_review,
            audit_artifacts=audit_artifacts,
            final_adapter_design_verdict=final_adapter_design_verdict,
            adapter_design_approval_allowed=allow_adapter_design_approval,
            real_entry_execution_requested=bool(allow_real_entry_execution),
            real_execution_allowed=False,
            real_entry_implemented=False,
            guarded_entry_real_execution_adapter_design=True,
            adapter_design_only=True,
            adapter_implementation_included=False,
            adapter_execution_included=False,
            adapter_grants_execution=False,
            approval_gate_grants_execution=False,
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
            upstream_entry_manual_approval_gate_status=entry_approval_gate_status,
            upstream_entry_manual_approval_gate_readiness_conclusion=entry_approval_gate_readiness,
            upstream_entry_manual_approval_gate_approval_grants_execution=entry_approval_gate_grants,
            upstream_entry_manual_approval_gate_exact_phrase_validated=entry_approval_gate_phrase,
            upstream_entry_manual_approval_gate_approval_inputs_validated=entry_approval_gate_inputs,
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
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_ENTRY_MANUAL_APPROVAL_GATE_STATUS_UNACCEPTABLE,
            GATE_ENTRY_MANUAL_APPROVAL_GATE_READINESS_EXECUTABLE,
            GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION,
            GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED,
            GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED,
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
    "ADAPTER_RESPONSE_STATUS",
    "ORDER_LINK_ID_PREFIX",
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
    "READINESS_CONCLUSION_NOT_EXECUTABLE",
    "DRY_RUN_AUTHORIZATION_RESULT",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_ADAPTER_DESIGN_SCOPE",
    "STAGE_2_ADAPTER_CONTRACT_DESIGN",
    "STAGE_3_ADAPTER_INPUT_SCHEMA_DESIGN",
    "STAGE_4_ADAPTER_OUTPUT_SCHEMA_DESIGN",
    "STAGE_5_ENTRY_PAYLOAD_DESIGN_PREVIEW",
    "STAGE_6_SECRET_AND_SIGNATURE_BOUNDARY_DESIGN",
    "STAGE_7_STOP_CLEANUP_BOUNDARY_DESIGN",
    "STAGE_8_FORBIDDEN_EXECUTION_SURFACE_DESIGN",
    "STAGE_9_FAILURE_AND_ABORT_ADAPTER_DESIGN",
    "STAGE_10_DOCUMENTATION_SYNC_REVIEW",
    "STAGE_11_FINAL_ADAPTER_DESIGN_VERDICT",
    "ALL_STAGES",
    "STATUS_DESIGN_READY",
    "STATUS_DESIGN_READY_EXEC_DISABLED",
    "STATUS_REAL_ENTRY_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_DESIGN_CHECKLIST",
    "MODE_DESIGN_APPROVAL",
    "MODE_REAL_ENTRY_EXEC_GUARD",
    "MODE_FAIL_CLOSED",
    # general (36)
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
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_NOT_SOLUSDT",
    "GATE_ENTRY_MANUAL_APPROVAL_GATE_STATUS_UNACCEPTABLE",
    "GATE_ENTRY_MANUAL_APPROVAL_GATE_READINESS_EXECUTABLE",
    "GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION",
    "GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED",
    "GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # scope (18)
    "GATE_ADAPTER_DESIGN_ONLY",
    "GATE_ADAPTER_IMPLEMENTATION_NOT_INCLUDED",
    "GATE_ADAPTER_EXECUTION_NOT_INCLUDED",
    "GATE_ENTRY_EXECUTION_NOT_INCLUDED",
    "GATE_STOP_EXECUTION_NOT_INCLUDED",
    "GATE_CLEANUP_EXECUTION_NOT_INCLUDED",
    "GATE_FULL_LIFECYCLE_EXECUTION_NOT_INCLUDED",
    "GATE_REAL_ENTRY_NOT_IMPLEMENTED_SCOPE",
    "GATE_REAL_EXECUTION_NOT_ALLOWED_SCOPE",
    "GATE_ADAPTER_DOES_NOT_GRANT_EXECUTION_SCOPE",
    "GATE_APPROVAL_GATE_DOES_NOT_GRANT_EXECUTION_SCOPE",
    "GATE_SEND_NOT_ALLOWED_SCOPE",
    "GATE_ORDER_ENDPOINT_NOT_CALLED",
    "GATE_STOP_ENDPOINT_NOT_CALLED",
    "GATE_NO_ENDPOINT_INVOKED",
    "GATE_NO_POSITION_MODIFIED_SCOPE",
    "GATE_NO_SECRETS_LOADED",
    "GATE_NO_G20_LIFT",
    # contract (13)
    "GATE_ADAPTER_NAME_DOCUMENTED",
    "GATE_ADAPTER_CONTRACT_VERSION_DOCUMENTED",
    "GATE_ADAPTER_INPUT_SCHEMA_DOCUMENTED",
    "GATE_ADAPTER_OUTPUT_SCHEMA_DOCUMENTED",
    "GATE_ADAPTER_ERROR_SCHEMA_DOCUMENTED",
    "GATE_ADAPTER_AUDIT_SCHEMA_DOCUMENTED",
    "GATE_ADAPTER_HAS_NO_SEND_METHOD",
    "GATE_ADAPTER_HAS_NO_PRIVATE_CLIENT",
    "GATE_ADAPTER_HAS_NO_SIGNATURE_METHOD",
    "GATE_ADAPTER_HAS_NO_SECRET_LOADER",
    "GATE_ADAPTER_HAS_NO_NETWORK_TRANSPORT",
    "GATE_ADAPTER_CONTRACT_DOES_NOT_EXECUTE",
    "GATE_ADAPTER_CONTRACT_REQUIRES_FUTURE_TASK",
    # input schema (21)
    "GATE_INPUT_SYMBOL_SOLUSDT",
    "GATE_INPUT_CATEGORY_LINEAR",
    "GATE_INPUT_SIDE_BUY",
    "GATE_INPUT_QTY_0_1",
    "GATE_INPUT_ORDER_TYPE_MARKET",
    "GATE_INPUT_REDUCE_ONLY_FALSE",
    "GATE_INPUT_CLOSE_ON_TRIGGER_FALSE",
    "GATE_INPUT_POSITION_IDX_ZERO",
    "GATE_INPUT_MAX_NOTIONAL_10",
    "GATE_INPUT_EXPECTED_EXISTING_SYMBOLS",
    "GATE_INPUT_EXPECTED_SOLUSDT_ABSENT",
    "GATE_INPUT_EXPECTED_STOP_LOSS_61_18",
    "GATE_INPUT_EXPECTED_TPSL_MODE_FULL",
    "GATE_INPUT_EXPECTED_SL_TRIGGER_BY_MARKPRICE",
    "GATE_INPUT_EXPECTED_COMMIT_HASH",
    "GATE_INPUT_APPROVAL_GATE_ARTIFACT_REQUIRED",
    "GATE_INPUT_MANUAL_APPROVAL_PHRASE_REQUIRED",
    "GATE_INPUT_TOKEN_REQUIRED_IN_FUTURE_TASK",
    "GATE_INPUT_SCHEMA_DOCUMENTED",
    "GATE_INPUT_SCHEMA_NOT_VALIDATED",
    "GATE_INPUT_SCHEMA_DOES_NOT_AUTHORIZE_EXECUTION",
    # output schema (16)
    "GATE_OUTPUT_RESPONSE_STATUS_ADAPTER_DESIGN_NOT_SENT",
    "GATE_OUTPUT_RESPONSE_FROM_EXCHANGE_FALSE",
    "GATE_OUTPUT_EXCHANGE_ORDER_ID_NONE",
    "GATE_OUTPUT_ORDER_LINK_ID_PREFIX",
    "GATE_OUTPUT_SEND_ALLOWED_FALSE",
    "GATE_OUTPUT_ENDPOINT_CALLED_FALSE",
    "GATE_OUTPUT_ORDER_ENDPOINT_CALLED_FALSE",
    "GATE_OUTPUT_STOP_ENDPOINT_CALLED_FALSE",
    "GATE_OUTPUT_REAL_PAYLOAD_FALSE",
    "GATE_OUTPUT_SIGNATURE_PRESENT_FALSE",
    "GATE_OUTPUT_PRIVATE_HEADERS_EMPTY",
    "GATE_OUTPUT_NO_SECRETS",
    "GATE_OUTPUT_SANITIZED",
    "GATE_OUTPUT_NO_POSITION_MODIFIED",
    "GATE_OUTPUT_SCHEMA_DOCUMENTED",
    "GATE_OUTPUT_SCHEMA_DOES_NOT_EXECUTE",
    # payload preview (19)
    "GATE_PAYLOAD_PREVIEW_ONLY",
    "GATE_PAYLOAD_ADAPTER_DESIGN_ONLY",
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
    # secret/signature (12)
    "GATE_SECRETS_REQUIRED_IN_FUTURE_TASK",
    "GATE_SECRETS_LOADED_FALSE",
    "GATE_ENV_READ_FALSE",
    "GATE_DOTENV_CALLED_FALSE",
    "GATE_HMAC_SIGNATURE_FALSE",
    "GATE_SIGNATURE_HEADER_FALSE",
    "GATE_PRIVATE_HEADERS_FALSE",
    "GATE_API_KEY_VALUE_NOT_OBSERVED",
    "GATE_API_SECRET_VALUE_NOT_OBSERVED",
    "GATE_SIGNING_REQUIRES_FUTURE_TASK",
    "GATE_SECRET_REDACTION_REQUIRED",
    "GATE_FORBIDDEN_LOG_FIELDS_DOCUMENTED",
    # stop/cleanup (13)
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
    "GATE_FUTURE_ADAPTER_MUST_NOT_AUTO_ATTACH_STOP",
    "GATE_FUTURE_ADAPTER_REQUIRES_SEPARATE_STOP_TASK",
    # forbidden execution surface (20)
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
    # failure (19)
    "GATE_MISSING_ARTIFACT_FAIL_CLOSED",
    "GATE_STALE_READONLY_FAIL_CLOSED",
    "GATE_MANUAL_APPROVAL_GATE_STALE_FAIL_CLOSED",
    "GATE_APPROVAL_GRANTS_EXECUTION_TRUE_FAIL_CLOSED",
    "GATE_PHRASE_ALREADY_VALIDATED_FAIL_CLOSED",
    "GATE_INPUTS_ALREADY_VALIDATED_FAIL_CLOSED",
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
    "GATE_EXECUTABLE_ADAPTER_DETECTED_FAIL_CLOSED",
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
    "DemoTinyGuardedEntryRealExecutionAdapterDesign",
    "TinyGuardedEntryRealExecutionAdapterDesignResult",
]
