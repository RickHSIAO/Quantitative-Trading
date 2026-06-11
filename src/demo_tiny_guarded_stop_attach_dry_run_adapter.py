"""
src/demo_tiny_guarded_stop_attach_dry_run_adapter.py
TASK-014AF: Guarded Stop-attach-only Dry-run Adapter.

Pure-computation / dry-run adapter for the future guarded
`guarded_stop_attach_only` command.  Consolidates 13 upstream artifacts
(readonly / reconciliation / protection / contract / noop_plan /
lifecycle_mock / tiny_position_real_permission_gate /
tiny_stop_attach_permission_gate / tiny_lifecycle_real_execution_summary /
tiny_lifecycle_runner_design / tiny_lifecycle_runner_dry_run /
tiny_lifecycle_guarded_runner_design_review /
tiny_guarded_entry_dry_run_adapter) and emits a dry-run adapter artifact
answering: if some future task ever wants to graduate to a guarded real
*stop attach* (stop attach only --- no entry, no cleanup, no full
lifecycle), what inputs, preconditions, manual confirmations, preview
stop-request envelope, readonly verification plan, failure policy, and
audit artifacts are required?

This module DOES NOT implement, design, or invoke a real stop-attach
sender.  No /v5/position/trading-stop call, no /v5/order/create call,
no order send, no position modification, no close-only, no emergency
close, no leverage / transfer / withdraw, no token validation, no
socket open, no .env read, no dotenv, no signing.  It does not modify
main.py, src/risk.py, or BybitExecutor.

Stages:

  stage_0_artifact_preflight
      Validate 13 upstream artifacts + runtime proof envelope + the
      TASK-014AD guarded_runner_design_review readiness_conclusion is
      DESIGN_REVIEW_READY_NOT_EXECUTABLE + the TASK-014AE
      guarded_entry_dry_run_adapter status is acceptable.

  stage_1_stop_adapter_scope
      Assert stop-attach-only dry-run adapter scope.  Not full
      lifecycle; no entry included; no cleanup; no real stop attach
      implemented; no endpoint invoked; no position modified; no
      secrets loaded.

  stage_2_stop_precondition_contract
      Document the preconditions any future guarded_stop_attach_only
      command must satisfy: post-entry symbol=SOLUSDT, side=long,
      qty=0.1, entry reference price=64.4, stopLoss=61.18 (below
      entry ref, tick aligned), tpslMode=Full, slTriggerBy=MarkPrice,
      positionIdx=0, category=linear, 5 protected positions
      unchanged, proof_strength STRONG, account_mode demo,
      endpoint_family bybit_demo, selected_symbol PRESENT before
      stop attach.

  stage_3_manual_confirmation_dry_run_contract
      Document the stop-attach token pattern
      (CONFIRM_DEMO_TINY_STOP_ATTACH_*), and the
      --i-understand-this-is-demo-real-execution,
      --max-notional-usdt 10, --expected-existing-position-count 5,
      --expected-existing-symbols AIXBTUSDT,ENAUSDT,TIAUSDT,POLYXUSDT,EDUUSDT,
      --expected-entry-symbol SOLUSDT, --expected-entry-qty 0.1,
      --expected-stop-loss 61.18 flags.  Tokens / flags are NEVER
      validated by this task.

  stage_4_stop_request_envelope_dry_run
      Build a single preview-only stop-attach request envelope.
      preview_only=True, send_allowed=False, endpoint_called=False,
      real_payload=False, signature_present=False, private_headers=[],
      endpoint_path_ref=/v5/position/trading-stop, base_url_ref=demo
      only, category=linear, symbol=SOLUSDT, stopLoss=61.18,
      tpslMode=Full, slTriggerBy=MarkPrice, positionIdx=0.  No sender
      adapter.

  stage_5_stop_readonly_verification_plan
      Pre-stop readonly required.  Post-stop readonly required.
      Pre-stop expects selected_symbol PRESENT with qty=0.1 / side=long
      and 5 protected positions intact.  Post-stop expects stopLoss
      attached at 61.18 with slTriggerBy=MarkPrice on the selected
      symbol and 5 protected positions unchanged.  Real readonly
      after execution is NOT performed in this task ---
      verification_plan_only=True.

  stage_6_stop_failure_policy
      Future guarded_stop_attach_only failure policy: request rejected
      / selected symbol absent / selected symbol side mismatch /
      selected symbol qty mismatch / stopLoss invalid or not tick
      aligned / readonly unavailable / live endpoint detected / secret
      emission detected => FAIL_CLOSED.  Existing protected position
      mismatch => MANUAL_REVIEW_REQUIRED.  No auto retry / cleanup /
      emergency close / entry / next step.

  stage_7_audit_artifact_generation
      Audit artifacts emitted: precondition_contract /
      manual_confirmation_contract / stop_request_envelope /
      readonly_verification_plan / failure_policy /
      final_stop_adapter_verdict.  response status fixed to
      DRY_RUN_NOT_SENT, response_from_exchange=False, sanitized=True,
      no secrets.

  stage_8_final_stop_adapter_verdict
      Resolve final status:
          TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY        (default)
          TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED
              (--allow-stop-dry-run-approval)
          REAL_STOP_ATTACH_EXECUTION_NOT_IMPLEMENTED
              (--allow-real-stop-execution)
          FAIL_CLOSED                                           (hard-fail)
      Always emits real_execution_allowed=False,
      real_stop_attach_implemented=False, send_allowed=False,
      order_endpoint_called=False, stop_endpoint_called=False,
      no_position_modified=True, no_secrets_loaded=True,
      g20_lifted=False.

Modes:
  stop_adapter_checklist              --- default
  stop_dry_run_approval               --- --allow-stop-dry-run-approval
  real_stop_execution_guard           --- --allow-real-stop-execution
  fail_closed                         --- upstream / consistency failed

This module DOES NOT (enforced by source-scan tests):
  * import urllib / requests / httpx / socket / http.client
  * read os.environ / dotenv
  * call HMAC / signing
  * import main / src.risk / BybitExecutor / pybit
  * import src.demo_new_entry_sender
  * import src.demo_close_only_sender
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
STAGE_1_STOP_ADAPTER_SCOPE                   = "stage_1_stop_adapter_scope"
STAGE_2_STOP_PRECONDITION_CONTRACT           = "stage_2_stop_precondition_contract"
STAGE_3_MANUAL_CONFIRMATION_DRY_RUN_CONTRACT = "stage_3_manual_confirmation_dry_run_contract"
STAGE_4_STOP_REQUEST_ENVELOPE_DRY_RUN        = "stage_4_stop_request_envelope_dry_run"
STAGE_5_STOP_READONLY_VERIFICATION_PLAN      = "stage_5_stop_readonly_verification_plan"
STAGE_6_STOP_FAILURE_POLICY                  = "stage_6_stop_failure_policy"
STAGE_7_AUDIT_ARTIFACT_GENERATION            = "stage_7_audit_artifact_generation"
STAGE_8_FINAL_STOP_ADAPTER_VERDICT           = "stage_8_final_stop_adapter_verdict"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_STOP_ADAPTER_SCOPE,
    STAGE_2_STOP_PRECONDITION_CONTRACT,
    STAGE_3_MANUAL_CONFIRMATION_DRY_RUN_CONTRACT,
    STAGE_4_STOP_REQUEST_ENVELOPE_DRY_RUN,
    STAGE_5_STOP_READONLY_VERIFICATION_PLAN,
    STAGE_6_STOP_FAILURE_POLICY,
    STAGE_7_AUDIT_ARTIFACT_GENERATION,
    STAGE_8_FINAL_STOP_ADAPTER_VERDICT,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_ADAPTER_READY               = "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY"
STATUS_ADAPTER_READY_EXEC_DISABLED = (
    "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_STOP_NOT_IMPL          = "REAL_STOP_ATTACH_EXECUTION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                 = "FAIL_CLOSED"

MODE_STOP_ADAPTER_CHECKLIST        = "stop_adapter_checklist"
MODE_STOP_DRY_RUN_APPROVAL         = "stop_dry_run_approval"
MODE_REAL_STOP_EXECUTION_GUARD     = "real_stop_execution_guard"
MODE_FAIL_CLOSED                   = "fail_closed"

READINESS_CONCLUSION_NOT_EXECUTABLE = "DESIGN_REVIEW_READY_NOT_EXECUTABLE"

DRY_RUN_NOT_SENT_MARKER             = "DRY_RUN_NOT_SENT"


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


# ---------------------------------------------------------------------------
# Approval token / flag patterns (documentation only --- never validated here)
# ---------------------------------------------------------------------------

STOP_TOKEN_PATTERN       = "CONFIRM_DEMO_TINY_STOP_ATTACH_YYYYMMDD_SYMBOL"

REQUIRED_CONFIRMATION_FLAGS: tuple[str, ...] = (
    "--i-understand-this-is-demo-real-execution",
    "--max-notional-usdt 10",
    "--expected-existing-position-count 5",
    "--expected-existing-symbols AIXBTUSDT,ENAUSDT,TIAUSDT,POLYXUSDT,EDUUSDT",
    "--expected-entry-symbol SOLUSDT",
    "--expected-entry-qty 0.1",
    "--expected-stop-loss 61.18",
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
# Future guarded stop-attach payload contract (documentation only)
# ---------------------------------------------------------------------------

EXPECTED_POST_ENTRY_SYMBOL       = "SOLUSDT"
EXPECTED_POST_ENTRY_SIDE         = "long"
EXPECTED_POST_ENTRY_QTY          = 0.1
EXPECTED_ENTRY_REFERENCE_PRICE   = 64.4
EXPECTED_STOP_LOSS               = 61.18
EXPECTED_TPSL_MODE               = "Full"
EXPECTED_SL_TRIGGER_BY           = "MarkPrice"
EXPECTED_POSITION_IDX            = 0
EXPECTED_TICK_SIZE               = 0.01
EXPECTED_MAX_NOTIONAL_USDT       = 10.0
EXPECTED_EXISTING_POSITION_COUNT = 5

FORBIDDEN_LOG_FIELDS: tuple[str, ...] = (
    "api_key_value", "api_secret_value", "signature_value",
    "auth_header_value", "sign_header_value", "bearer_token_value",
)


# ---------------------------------------------------------------------------
# Gate constants (total: 111)
# General (24) + Scope (11) + Precondition (17) + Manual confirmation (11)
# + Envelope (13) + Readonly plan (11) + Failure policy (14) + Audit (5)
# + Execution guard (5) = 111
# ---------------------------------------------------------------------------

# General gates (24)
GATE_READONLY_SMOKE_MISSING                     = "readonly_smoke_missing"
GATE_RECONCILIATION_MISSING                     = "reconciliation_missing"
GATE_PROTECTION_MISSING                         = "protection_missing"
GATE_CONTRACT_MISSING                           = "contract_missing"
GATE_NOOP_PLAN_MISSING                          = "noop_plan_missing"
GATE_LIFECYCLE_MOCK_MISSING                     = "lifecycle_mock_missing"
GATE_REAL_PERMISSION_GATE_MISSING               = "real_permission_gate_missing"
GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING   = "tiny_stop_attach_permission_gate_missing"
GATE_LIFECYCLE_SUMMARY_MISSING                  = "lifecycle_summary_missing"
GATE_RUNNER_DESIGN_MISSING                      = "runner_design_missing"
GATE_RUNNER_DRY_RUN_MISSING                     = "runner_dry_run_missing"
GATE_GUARDED_DESIGN_REVIEW_MISSING              = "guarded_design_review_missing"
GATE_GUARDED_ENTRY_ADAPTER_MISSING              = "guarded_entry_adapter_missing"
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO             = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                      = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG                  = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY  = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_MISSING                    = "selected_symbol_missing"
GATE_SELECTED_SYMBOL_NOT_SOLUSDT                = "selected_symbol_not_solusdt"
GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE  = "guarded_design_review_status_unacceptable"
GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE = "guarded_design_review_readiness_executable"
GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE  = "guarded_entry_adapter_status_unacceptable"
GATE_G20_POLICY_STILL_IN_PLACE                  = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                           = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                         = "no_secret_values_emitted_in_this_task"

# Scope gates (11)
GATE_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_ONLY   = "guarded_stop_attach_dry_run_adapter_only"
GATE_STOP_ATTACH_ONLY                           = "stop_attach_only"
GATE_ENTRY_NOT_INCLUDED                         = "entry_not_included"
GATE_CLEANUP_NOT_INCLUDED                       = "cleanup_not_included"
GATE_FULL_LIFECYCLE_NOT_INCLUDED                = "full_lifecycle_not_included"
GATE_REAL_STOP_ATTACH_NOT_IMPLEMENTED           = "real_stop_attach_not_implemented_in_this_task"
GATE_REAL_EXECUTION_NOT_ALLOWED                 = "real_execution_not_allowed_in_this_task"
GATE_NO_ENDPOINT_INVOKED                        = "no_endpoint_invoked_in_this_task"
GATE_NO_POSITION_MODIFIED_SCOPE                 = "no_position_modified_scope"
GATE_NO_SECRETS_LOADED                          = "no_secrets_loaded_in_this_task"
GATE_NO_G20_LIFT                                = "no_g20_policy_lift_in_this_task"

# Precondition gates (17)
GATE_PRECONDITION_SYMBOL_MATCHES                = "precondition_symbol_matches"
GATE_PRECONDITION_EXPECTED_ENTRY_SYMBOL         = "precondition_expected_entry_symbol_solusdt"
GATE_PRECONDITION_SIDE_LONG                     = "precondition_side_long"
GATE_PRECONDITION_QTY_TINY                      = "precondition_qty_tiny"
GATE_PRECONDITION_ENTRY_REFERENCE_VALID         = "precondition_entry_reference_price_valid"
GATE_PRECONDITION_STOP_LOSS_VALUE               = "precondition_stop_loss_61_18"
GATE_PRECONDITION_STOP_LOSS_BELOW_ENTRY         = "precondition_stop_loss_below_entry_reference"
GATE_PRECONDITION_STOP_LOSS_TICK_ALIGNED        = "precondition_stop_loss_tick_aligned"
GATE_PRECONDITION_TPSL_MODE_FULL                = "precondition_tpsl_mode_full"
GATE_PRECONDITION_SL_TRIGGER_BY_MARK_PRICE      = "precondition_sl_trigger_by_mark_price"
GATE_PRECONDITION_POSITION_IDX_ZERO             = "precondition_position_idx_zero"
GATE_PRECONDITION_CATEGORY_LINEAR               = "precondition_category_linear"
GATE_PRECONDITION_SELECTED_SYMBOL_PRESENT       = "precondition_selected_symbol_present_before_stop"
GATE_PRECONDITION_EXPECTED_PROTECTED_LIST       = "precondition_expected_protected_list_documented"
GATE_PRECONDITION_PROOF_STRENGTH_STRONG         = "precondition_proof_strength_strong"
GATE_PRECONDITION_ACCOUNT_MODE_DEMO             = "precondition_account_mode_demo"
GATE_PRECONDITION_ENDPOINT_FAMILY_BYBIT_DEMO    = "precondition_endpoint_family_bybit_demo"

# Manual confirmation gates (11)
GATE_STOP_TOKEN_PATTERN_PRESENT                 = "stop_token_pattern_present"
GATE_TOKEN_NOT_VALIDATED                        = "token_not_validated_in_this_task"
GATE_TOKEN_FORMAT_NOT_AUTHORIZATION             = "token_format_not_authorization"
GATE_SECOND_CONFIRMATION_DOCUMENTED             = "second_confirmation_documented"
GATE_MAX_NOTIONAL_FLAG_DOCUMENTED               = "max_notional_flag_documented"
GATE_EXPECTED_COUNT_FLAG_DOCUMENTED             = "expected_count_flag_documented"
GATE_EXPECTED_SYMBOLS_FLAG_DOCUMENTED           = "expected_symbols_flag_documented"
GATE_EXPECTED_ENTRY_SYMBOL_FLAG_DOCUMENTED      = "expected_entry_symbol_flag_documented"
GATE_EXPECTED_ENTRY_QTY_FLAG_DOCUMENTED         = "expected_entry_qty_flag_documented"
GATE_EXPECTED_STOP_LOSS_FLAG_DOCUMENTED         = "expected_stop_loss_flag_documented"
GATE_CONFIRMATION_FLAGS_NOT_VALIDATED           = "confirmation_flags_not_validated"

# Envelope gates (13)
GATE_STOP_ENVELOPE_PRESENT                      = "stop_envelope_present"
GATE_ENVELOPE_PREVIEW_ONLY                      = "envelope_preview_only_true"
GATE_ENVELOPE_SEND_NOT_ALLOWED                  = "envelope_send_allowed_false"
GATE_ENVELOPE_ENDPOINT_NOT_CALLED               = "envelope_endpoint_called_false"
GATE_ENVELOPE_NOT_REAL_PAYLOAD                  = "envelope_real_payload_false"
GATE_ENVELOPE_NO_SIGNATURE                      = "envelope_signature_absent"
GATE_ENVELOPE_NO_PRIVATE_HEADERS                = "envelope_private_headers_empty"
GATE_ENVELOPE_TRADING_STOP_PATH                 = "envelope_endpoint_path_trading_stop"
GATE_ENVELOPE_BASE_URL_DEMO_ONLY                = "envelope_base_url_demo_only"
GATE_ENVELOPE_STOP_LOSS_VALUE                   = "envelope_stop_loss_61_18"
GATE_ENVELOPE_TPSL_MODE_FULL                    = "envelope_tpsl_mode_full"
GATE_ENVELOPE_SL_TRIGGER_BY_MARK_PRICE          = "envelope_sl_trigger_by_mark_price"
GATE_NO_SENDER_ADAPTER                          = "no_sender_adapter_in_this_task"

# Readonly plan gates (11)
GATE_PRE_STOP_READONLY_REQUIRED                 = "pre_stop_readonly_required"
GATE_POST_STOP_READONLY_REQUIRED                = "post_stop_readonly_required"
GATE_PRE_STOP_SELECTED_SYMBOL_PRESENT           = "pre_stop_selected_symbol_present"
GATE_PRE_STOP_EXPECTED_SYMBOL                   = "pre_stop_expected_symbol_solusdt"
GATE_PRE_STOP_EXPECTED_QTY                      = "pre_stop_expected_qty_tiny"
GATE_PRE_STOP_EXPECTED_SIDE_LONG                = "pre_stop_expected_side_long"
GATE_POST_STOP_EXPECTED_STOP_LOSS               = "post_stop_expected_stop_loss_61_18"
GATE_POST_STOP_EXPECTED_TRIGGER_BY              = "post_stop_expected_trigger_by_mark_price"
GATE_EXISTING_POSITIONS_UNCHANGED_REQUIRED      = "existing_positions_unchanged_required"
GATE_VERIFICATION_PLAN_ONLY                     = "verification_plan_only"
GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED = "real_readonly_after_execution_not_performed"

# Failure policy gates (14)
GATE_REQUEST_REJECTED_FAIL_CLOSED               = "request_rejected_fail_closed"
GATE_SELECTED_SYMBOL_ABSENT_FAIL_CLOSED         = "selected_symbol_absent_fail_closed"
GATE_SELECTED_SYMBOL_SIDE_MISMATCH_FAIL_CLOSED  = "selected_symbol_side_mismatch_fail_closed"
GATE_SELECTED_SYMBOL_QTY_MISMATCH_FAIL_CLOSED   = "selected_symbol_qty_mismatch_fail_closed"
GATE_STOP_LOSS_INVALID_FAIL_CLOSED              = "stop_loss_invalid_fail_closed"
GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW  = "protected_position_mismatch_manual_review"
GATE_READONLY_UNAVAILABLE_FAIL_CLOSED           = "readonly_unavailable_fail_closed"
GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED         = "live_endpoint_detected_fail_closed"
GATE_SECRET_EMISSION_FAIL_CLOSED                = "secret_emission_fail_closed"
GATE_NO_AUTO_RETRY                              = "no_auto_retry"
GATE_NO_AUTO_CLEANUP                            = "no_auto_cleanup"
GATE_NO_AUTO_EMERGENCY_CLOSE                    = "no_auto_emergency_close"
GATE_NO_AUTO_ENTRY                              = "no_auto_entry"
GATE_NO_AUTO_NEXT_STEP                          = "no_auto_next_step"

# Audit gates (5)
GATE_AUDIT_ARTIFACTS_PRESENT                    = "audit_artifacts_present"
GATE_AUDIT_RESPONSE_DRY_RUN_NOT_SENT            = "audit_response_dry_run_not_sent"
GATE_AUDIT_RESPONSE_FROM_EXCHANGE_FALSE         = "audit_response_from_exchange_false"
GATE_AUDIT_SANITIZED                            = "audit_sanitized"
GATE_AUDIT_NO_SECRETS                           = "audit_no_secrets"

# Execution guard gates (5)
GATE_REAL_STOP_ATTACH_EXECUTION_NOT_IMPL        = "real_stop_attach_execution_not_implemented"
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
    GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING,
    GATE_LIFECYCLE_SUMMARY_MISSING,
    GATE_RUNNER_DESIGN_MISSING,
    GATE_RUNNER_DRY_RUN_MISSING,
    GATE_GUARDED_DESIGN_REVIEW_MISSING,
    GATE_GUARDED_ENTRY_ADAPTER_MISSING,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE,
    GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE,
    GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE,
    GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyGuardedStopAttachDryRunAdapterResult:
    """Read-only outcome of one guarded stop-attach dry-run adapter pass."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    stop_adapter_scope:                  dict[str, Any] = field(default_factory=dict)
    stop_precondition_contract:          dict[str, Any] = field(default_factory=dict)
    manual_confirmation_dry_run_contract: dict[str, Any] = field(default_factory=dict)
    stop_request_envelope:               dict[str, Any] = field(default_factory=dict)
    stop_readonly_verification_plan:     dict[str, Any] = field(default_factory=dict)
    stop_failure_policy:                 dict[str, Any] = field(default_factory=dict)
    audit_artifacts:                     dict[str, Any] = field(default_factory=dict)
    final_stop_adapter_verdict:          dict[str, Any] = field(default_factory=dict)

    stop_token_pattern:           str = STOP_TOKEN_PATTERN
    required_confirmation_flags:  list[str] = field(
        default_factory=lambda: list(REQUIRED_CONFIRMATION_FLAGS),
    )

    # Adapter gating flags.
    stop_dry_run_approval_allowed:    bool = False
    real_stop_execution_requested:    bool = False
    real_execution_allowed:           bool = False
    real_stop_attach_implemented:     bool = False
    guarded_stop_attach_dry_run_adapter: bool = True
    stop_attach_only:                 bool = True
    entry_included:                   bool = False
    cleanup_included:                 bool = False
    full_lifecycle_included:          bool = False
    current_task_real_execution_allowed: bool = False
    readiness_conclusion:             str  = READINESS_CONCLUSION_NOT_EXECUTABLE

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
    upstream_guarded_entry_adapter_status: str = ""

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = "TASK-014AG_guarded_cleanup_only_dry_run_adapter"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                       self.timestamp_utc,
            "timestamp_utc":                   self.timestamp_utc,
            "mode":                            self.mode,
            "selected_symbol":                 self.selected_symbol,
            "existing_position_symbols":       list(self.existing_position_symbols),
            "stages":                          {k: dict(v) for k, v in self.stages.items()},
            "stage_order":                     list(self.stage_order),
            "stop_adapter_scope":              dict(self.stop_adapter_scope),
            "stop_precondition_contract":      dict(self.stop_precondition_contract),
            "manual_confirmation_dry_run_contract": dict(self.manual_confirmation_dry_run_contract),
            "stop_request_envelope":           dict(self.stop_request_envelope),
            "stop_readonly_verification_plan": dict(self.stop_readonly_verification_plan),
            "stop_failure_policy":             dict(self.stop_failure_policy),
            "audit_artifacts":                 dict(self.audit_artifacts),
            "final_stop_adapter_verdict":      dict(self.final_stop_adapter_verdict),
            "stop_token_pattern":              self.stop_token_pattern,
            "required_confirmation_flags":     list(self.required_confirmation_flags),
            "stop_dry_run_approval_allowed":   self.stop_dry_run_approval_allowed,
            "real_stop_execution_requested":   self.real_stop_execution_requested,
            "real_execution_allowed":          self.real_execution_allowed,
            "real_stop_attach_implemented":    self.real_stop_attach_implemented,
            "guarded_stop_attach_dry_run_adapter": self.guarded_stop_attach_dry_run_adapter,
            "stop_attach_only":                self.stop_attach_only,
            "entry_included":                  self.entry_included,
            "cleanup_included":                self.cleanup_included,
            "full_lifecycle_included":         self.full_lifecycle_included,
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
            "upstream_guarded_entry_adapter_status": self.upstream_guarded_entry_adapter_status,
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


def _is_tick_aligned(value: float, tick: float) -> bool:
    if tick <= 0:
        return False
    scaled = round(value / tick)
    return abs(scaled * tick - value) < 1e-9


# ---------------------------------------------------------------------------
# Guarded stop-attach dry-run adapter
# ---------------------------------------------------------------------------

class DemoTinyGuardedStopAttachDryRunAdapter:
    """
    Pure-computation guarded stop-attach dry-run adapter.  Consolidates
    the 13 upstream artifacts (10 baseline + AA lifecycle summary + AB
    runner design + AC runner dry-run + AD guarded design review + AE
    guarded entry dry-run adapter --- minus the entry / cleanup
    permission gates, since this adapter is stop-attach-only) and emits
    a dry-run adapter artifact answering: what inputs, preconditions,
    manual confirmations, request envelope, readonly verification plan,
    and audit artifacts are required for any future
    guarded_stop_attach_only command?

    Holds no network client, reads no environment variables, opens no
    socket, performs no HMAC signing, and NEVER invokes the
    order-create or trading-stop endpoints.  Does not implement,
    design, or describe a real stop-attach sender that could be
    executed.

    --allow-stop-dry-run-approval --> status promoted to
        TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED.

    --allow-real-stop-execution --> status fixed to
        REAL_STOP_ATTACH_EXECUTION_NOT_IMPLEMENTED  (no socket opened).
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
        tiny_stop_attach_permission_gate: dict[str, Any] | None,
        lifecycle_summary:                dict[str, Any] | None,
        runner_design:                    dict[str, Any] | None,
        runner_dry_run:                   dict[str, Any] | None,
        guarded_design_review:            dict[str, Any] | None,
        guarded_entry_adapter:            dict[str, Any] | None,
        symbol:                           str  = DEFAULT_SELECTED_SYMBOL,
        allow_stop_dry_run_approval:      bool = False,
        allow_real_stop_execution:        bool = False,
        _now:                             datetime | None = None,
    ) -> TinyGuardedStopAttachDryRunAdapterResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_stop_execution:
            mode = MODE_REAL_STOP_EXECUTION_GUARD
        elif allow_stop_dry_run_approval:
            mode = MODE_STOP_DRY_RUN_APPROVAL
        else:
            mode = MODE_STOP_ADAPTER_CHECKLIST

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
        stop_perm_present    = (
            isinstance(tiny_stop_attach_permission_gate, dict)
            and bool(tiny_stop_attach_permission_gate)
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
        if not stop_perm_present:
            blocked.append(GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING)
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

        if not sym:
            blocked.append(GATE_SELECTED_SYMBOL_MISSING)
        elif sym != EXPECTED_POST_ENTRY_SYMBOL:
            blocked.append(GATE_SELECTED_SYMBOL_NOT_SOLUSDT)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 13 upstream artifacts + runtime proof envelope + AD readiness + AE entry adapter status.",
            "readonly_smoke_present":                   readonly_present,
            "reconciliation_present":                   recon_present,
            "protection_present":                       protection_present,
            "contract_present":                         contract_present,
            "noop_plan_present":                        noop_present,
            "lifecycle_mock_present":                   lifecycle_present,
            "real_permission_gate_present":             real_perm_present,
            "tiny_stop_attach_permission_gate_present": stop_perm_present,
            "lifecycle_summary_present":                summary_present,
            "runner_design_present":                    runner_design_present,
            "runner_dry_run_present":                   runner_dry_run_present,
            "guarded_design_review_present":            guarded_review_present,
            "guarded_entry_adapter_present":            guarded_entry_present,
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
            "selected_symbol":                          sym,
            "selected_symbol_expected":                 EXPECTED_POST_ENTRY_SYMBOL,
            "current_task_real_execution_allowed":      False,
        }

        # ===============================================================
        # stage_1_stop_adapter_scope
        # ===============================================================
        stop_adapter_scope: dict[str, Any] = {
            "guarded_stop_attach_dry_run_adapter":  True,
            "stop_attach_only":                     True,
            "entry_included":                       False,
            "cleanup_included":                     False,
            "full_lifecycle_included":              False,
            "real_stop_attach_implemented":         False,
            "real_execution_allowed":               False,
            "order_endpoint_called":                False,
            "stop_endpoint_called":                 False,
            "no_endpoint_invoked_in_this_task":     True,
            "no_position_modified":                 True,
            "no_secrets_loaded":                    True,
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "next_required_task":                   "TASK-014AG_guarded_cleanup_only_dry_run_adapter",
            "scope_summary": (
                "TASK-014AF only adapts the future guarded_stop_attach_only "
                "command into a dry-run artifact.  It does not implement "
                "the real stop-attach sender, does not include entry or "
                "cleanup, does not run the full lifecycle, does not send "
                "any order, does not call any endpoint, does not load any "
                "secret, and does not touch any existing position."
            ),
        }
        stages[STAGE_1_STOP_ADAPTER_SCOPE] = {
            "stage":   STAGE_1_STOP_ADAPTER_SCOPE,
            "summary": "Assert guarded stop-attach dry-run adapter scope (stop-attach-only).",
            "stop_adapter_scope":                   stop_adapter_scope,
        }
        blocked.append(GATE_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_ONLY)
        blocked.append(GATE_STOP_ATTACH_ONLY)
        blocked.append(GATE_ENTRY_NOT_INCLUDED)
        blocked.append(GATE_CLEANUP_NOT_INCLUDED)
        blocked.append(GATE_FULL_LIFECYCLE_NOT_INCLUDED)
        blocked.append(GATE_REAL_STOP_ATTACH_NOT_IMPLEMENTED)
        blocked.append(GATE_REAL_EXECUTION_NOT_ALLOWED)
        blocked.append(GATE_NO_ENDPOINT_INVOKED)
        blocked.append(GATE_NO_POSITION_MODIFIED_SCOPE)
        blocked.append(GATE_NO_SECRETS_LOADED)
        blocked.append(GATE_NO_G20_LIFT)

        # ===============================================================
        # stage_2_stop_precondition_contract
        # ===============================================================
        sym_eff = sym or EXPECTED_POST_ENTRY_SYMBOL
        stop_loss_below_entry  = EXPECTED_STOP_LOSS < EXPECTED_ENTRY_REFERENCE_PRICE
        stop_loss_tick_aligned = _is_tick_aligned(EXPECTED_STOP_LOSS, EXPECTED_TICK_SIZE)
        stop_precondition_contract: dict[str, Any] = {
            "symbol":                               EXPECTED_INSTRUMENT_CATEGORY + ":" + sym_eff,
            "selected_symbol":                      sym_eff,
            "expected_entry_symbol":                EXPECTED_POST_ENTRY_SYMBOL,
            "expected_position_side":               EXPECTED_POST_ENTRY_SIDE,
            "expected_qty":                         EXPECTED_POST_ENTRY_QTY,
            "expected_entry_reference_price":       EXPECTED_ENTRY_REFERENCE_PRICE,
            "stopLoss":                             EXPECTED_STOP_LOSS,
            "stop_loss_below_entry_reference":      stop_loss_below_entry,
            "tick_size":                            EXPECTED_TICK_SIZE,
            "stop_loss_tick_aligned":               stop_loss_tick_aligned,
            "tpslMode":                             EXPECTED_TPSL_MODE,
            "slTriggerBy":                          EXPECTED_SL_TRIGGER_BY,
            "positionIdx":                          EXPECTED_POSITION_IDX,
            "category":                             EXPECTED_INSTRUMENT_CATEGORY,
            "selected_symbol_present_before_stop":  True,
            "expected_existing_position_count":     EXPECTED_EXISTING_POSITION_COUNT,
            "expected_existing_symbols":            list(EXISTING_POSITION_SYMBOLS),
            "proof_strength":                       EXPECTED_PROOF_STRENGTH,
            "account_mode":                         EXPECTED_ACCOUNT_MODE,
            "endpoint_family":                      EXPECTED_ENDPOINT_FAMILY,
            "max_notional_usdt":                    EXPECTED_MAX_NOTIONAL_USDT,
        }
        stages[STAGE_2_STOP_PRECONDITION_CONTRACT] = {
            "stage":   STAGE_2_STOP_PRECONDITION_CONTRACT,
            "summary": "Document the preconditions any future guarded_stop_attach_only command must satisfy.",
            "stop_precondition_contract":           stop_precondition_contract,
        }
        blocked.append(GATE_PRECONDITION_SYMBOL_MATCHES)
        blocked.append(GATE_PRECONDITION_EXPECTED_ENTRY_SYMBOL)
        blocked.append(GATE_PRECONDITION_SIDE_LONG)
        blocked.append(GATE_PRECONDITION_QTY_TINY)
        blocked.append(GATE_PRECONDITION_ENTRY_REFERENCE_VALID)
        blocked.append(GATE_PRECONDITION_STOP_LOSS_VALUE)
        blocked.append(GATE_PRECONDITION_STOP_LOSS_BELOW_ENTRY)
        blocked.append(GATE_PRECONDITION_STOP_LOSS_TICK_ALIGNED)
        blocked.append(GATE_PRECONDITION_TPSL_MODE_FULL)
        blocked.append(GATE_PRECONDITION_SL_TRIGGER_BY_MARK_PRICE)
        blocked.append(GATE_PRECONDITION_POSITION_IDX_ZERO)
        blocked.append(GATE_PRECONDITION_CATEGORY_LINEAR)
        blocked.append(GATE_PRECONDITION_SELECTED_SYMBOL_PRESENT)
        blocked.append(GATE_PRECONDITION_EXPECTED_PROTECTED_LIST)
        blocked.append(GATE_PRECONDITION_PROOF_STRENGTH_STRONG)
        blocked.append(GATE_PRECONDITION_ACCOUNT_MODE_DEMO)
        blocked.append(GATE_PRECONDITION_ENDPOINT_FAMILY_BYBIT_DEMO)

        # ===============================================================
        # stage_3_manual_confirmation_dry_run_contract
        # ===============================================================
        manual_confirmation_dry_run_contract: dict[str, Any] = {
            "stop_token_pattern":                   STOP_TOKEN_PATTERN,
            "token_validated":                      False,
            "token_format_not_authorization":       True,
            "tokens_not_validated_in_this_task":    True,
            "required_confirmation_flags":          list(REQUIRED_CONFIRMATION_FLAGS),
            "confirmation_flags_documented":        True,
            "confirmation_flags_validated":         False,
            "second_confirmation_required":         True,
            "max_notional_cap_required":            True,
            "expected_existing_position_count":     EXPECTED_EXISTING_POSITION_COUNT,
            "expected_existing_symbols":            list(EXISTING_POSITION_SYMBOLS),
            "expected_existing_symbols_required":   True,
            "expected_entry_symbol_required":       True,
            "expected_entry_qty_required":          True,
            "expected_stop_loss_required":          True,
        }
        stages[STAGE_3_MANUAL_CONFIRMATION_DRY_RUN_CONTRACT] = {
            "stage":   STAGE_3_MANUAL_CONFIRMATION_DRY_RUN_CONTRACT,
            "summary": "Document the manual confirmation contract (token + flags), never validated.",
            "manual_confirmation_dry_run_contract": manual_confirmation_dry_run_contract,
        }
        blocked.append(GATE_STOP_TOKEN_PATTERN_PRESENT)
        blocked.append(GATE_TOKEN_NOT_VALIDATED)
        blocked.append(GATE_TOKEN_FORMAT_NOT_AUTHORIZATION)
        blocked.append(GATE_SECOND_CONFIRMATION_DOCUMENTED)
        blocked.append(GATE_MAX_NOTIONAL_FLAG_DOCUMENTED)
        blocked.append(GATE_EXPECTED_COUNT_FLAG_DOCUMENTED)
        blocked.append(GATE_EXPECTED_SYMBOLS_FLAG_DOCUMENTED)
        blocked.append(GATE_EXPECTED_ENTRY_SYMBOL_FLAG_DOCUMENTED)
        blocked.append(GATE_EXPECTED_ENTRY_QTY_FLAG_DOCUMENTED)
        blocked.append(GATE_EXPECTED_STOP_LOSS_FLAG_DOCUMENTED)
        blocked.append(GATE_CONFIRMATION_FLAGS_NOT_VALIDATED)

        # ===============================================================
        # stage_4_stop_request_envelope_dry_run
        # ===============================================================
        stop_request_envelope: dict[str, Any] = {
            "preview_only":                         True,
            "send_allowed":                         False,
            "endpoint_called":                      False,
            "real_payload":                         False,
            "signature_present":                    False,
            "private_headers":                      [],
            "endpoint_path_ref":                    TRADING_STOP_PATH_REF,
            "base_url_ref":                         BASE_URL_DEMO_REF,
            "demo_endpoint_allowlist":              list(DEMO_ENDPOINT_ALLOWLIST),
            "live_endpoint_denylist":               list(LIVE_ENDPOINT_DENYLIST),
            "category":                             EXPECTED_INSTRUMENT_CATEGORY,
            "symbol":                               sym_eff,
            "stopLoss":                             EXPECTED_STOP_LOSS,
            "tpslMode":                             EXPECTED_TPSL_MODE,
            "slTriggerBy":                          EXPECTED_SL_TRIGGER_BY,
            "positionIdx":                          EXPECTED_POSITION_IDX,
            "no_sender_adapter":                    True,
        }
        stages[STAGE_4_STOP_REQUEST_ENVELOPE_DRY_RUN] = {
            "stage":   STAGE_4_STOP_REQUEST_ENVELOPE_DRY_RUN,
            "summary": "Build preview-only stop-attach request envelope (no sender adapter, no signature).",
            "stop_request_envelope":                stop_request_envelope,
        }
        blocked.append(GATE_STOP_ENVELOPE_PRESENT)
        blocked.append(GATE_ENVELOPE_PREVIEW_ONLY)
        blocked.append(GATE_ENVELOPE_SEND_NOT_ALLOWED)
        blocked.append(GATE_ENVELOPE_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_ENVELOPE_NOT_REAL_PAYLOAD)
        blocked.append(GATE_ENVELOPE_NO_SIGNATURE)
        blocked.append(GATE_ENVELOPE_NO_PRIVATE_HEADERS)
        blocked.append(GATE_ENVELOPE_TRADING_STOP_PATH)
        blocked.append(GATE_ENVELOPE_BASE_URL_DEMO_ONLY)
        blocked.append(GATE_ENVELOPE_STOP_LOSS_VALUE)
        blocked.append(GATE_ENVELOPE_TPSL_MODE_FULL)
        blocked.append(GATE_ENVELOPE_SL_TRIGGER_BY_MARK_PRICE)
        blocked.append(GATE_NO_SENDER_ADAPTER)

        # ===============================================================
        # stage_5_stop_readonly_verification_plan
        # ===============================================================
        stop_readonly_verification_plan: dict[str, Any] = {
            "pre_stop_readonly_required":               True,
            "post_stop_readonly_required":              True,
            "pre_stop_selected_symbol_present":         True,
            "pre_stop_expected_symbol":                 sym_eff,
            "pre_stop_expected_qty":                    EXPECTED_POST_ENTRY_QTY,
            "pre_stop_expected_side":                   EXPECTED_POST_ENTRY_SIDE,
            "post_stop_expected_stop_loss":             EXPECTED_STOP_LOSS,
            "post_stop_expected_trigger_by":            EXPECTED_SL_TRIGGER_BY,
            "existing_positions_unchanged_required":    True,
            "verification_plan_only":                   True,
            "real_readonly_after_execution_not_performed": True,
        }
        stages[STAGE_5_STOP_READONLY_VERIFICATION_PLAN] = {
            "stage":   STAGE_5_STOP_READONLY_VERIFICATION_PLAN,
            "summary": "Pre/post readonly verification plan (plan only; never executed).",
            "stop_readonly_verification_plan":      stop_readonly_verification_plan,
        }
        blocked.append(GATE_PRE_STOP_READONLY_REQUIRED)
        blocked.append(GATE_POST_STOP_READONLY_REQUIRED)
        blocked.append(GATE_PRE_STOP_SELECTED_SYMBOL_PRESENT)
        blocked.append(GATE_PRE_STOP_EXPECTED_SYMBOL)
        blocked.append(GATE_PRE_STOP_EXPECTED_QTY)
        blocked.append(GATE_PRE_STOP_EXPECTED_SIDE_LONG)
        blocked.append(GATE_POST_STOP_EXPECTED_STOP_LOSS)
        blocked.append(GATE_POST_STOP_EXPECTED_TRIGGER_BY)
        blocked.append(GATE_EXISTING_POSITIONS_UNCHANGED_REQUIRED)
        blocked.append(GATE_VERIFICATION_PLAN_ONLY)
        blocked.append(GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED)

        # ===============================================================
        # stage_6_stop_failure_policy
        # ===============================================================
        stop_failure_policy: dict[str, Any] = {
            "request_rejected":                  "FAIL_CLOSED",
            "selected_symbol_absent":            "FAIL_CLOSED",
            "selected_symbol_side_mismatch":     "FAIL_CLOSED",
            "selected_symbol_qty_mismatch":      "FAIL_CLOSED",
            "stop_loss_invalid":                 "FAIL_CLOSED",
            "existing_protected_mismatch":       "MANUAL_REVIEW_REQUIRED",
            "readonly_unavailable":              "FAIL_CLOSED",
            "live_endpoint_detected":            "FAIL_CLOSED",
            "secret_emission_detected":          "FAIL_CLOSED",
            "no_auto_retry":                     True,
            "no_auto_cleanup":                   True,
            "no_auto_emergency_close":           True,
            "no_auto_entry":                     True,
            "no_auto_next_step":                 True,
            "manual_intervention_only":          True,
        }
        stages[STAGE_6_STOP_FAILURE_POLICY] = {
            "stage":   STAGE_6_STOP_FAILURE_POLICY,
            "summary": "Future guarded_stop_attach_only failure / abort policy.",
            "stop_failure_policy":                  stop_failure_policy,
        }
        blocked.append(GATE_REQUEST_REJECTED_FAIL_CLOSED)
        blocked.append(GATE_SELECTED_SYMBOL_ABSENT_FAIL_CLOSED)
        blocked.append(GATE_SELECTED_SYMBOL_SIDE_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_SELECTED_SYMBOL_QTY_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_STOP_LOSS_INVALID_FAIL_CLOSED)
        blocked.append(GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW)
        blocked.append(GATE_READONLY_UNAVAILABLE_FAIL_CLOSED)
        blocked.append(GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_SECRET_EMISSION_FAIL_CLOSED)
        blocked.append(GATE_NO_AUTO_RETRY)
        blocked.append(GATE_NO_AUTO_CLEANUP)
        blocked.append(GATE_NO_AUTO_EMERGENCY_CLOSE)
        blocked.append(GATE_NO_AUTO_ENTRY)
        blocked.append(GATE_NO_AUTO_NEXT_STEP)

        # ===============================================================
        # stage_7_audit_artifact_generation
        # ===============================================================
        audit_artifacts: dict[str, Any] = {
            "precondition_contract":                dict(stop_precondition_contract),
            "manual_confirmation_contract":         dict(manual_confirmation_dry_run_contract),
            "stop_request_envelope":                dict(stop_request_envelope),
            "readonly_verification_plan":           dict(stop_readonly_verification_plan),
            "failure_policy":                       dict(stop_failure_policy),
            "final_stop_adapter_verdict":           {},  # filled below
            "response_status":                      DRY_RUN_NOT_SENT_MARKER,
            "response_from_exchange":               False,
            "sanitized":                            True,
            "no_secrets":                           True,
            "forbidden_log_fields":                 list(FORBIDDEN_LOG_FIELDS),
        }
        stages[STAGE_7_AUDIT_ARTIFACT_GENERATION] = {
            "stage":   STAGE_7_AUDIT_ARTIFACT_GENERATION,
            "summary": "Emit stop-attach-only dry-run audit artifacts (DRY_RUN_NOT_SENT).",
            "audit_artifacts":                      audit_artifacts,
        }
        blocked.append(GATE_AUDIT_ARTIFACTS_PRESENT)
        blocked.append(GATE_AUDIT_RESPONSE_DRY_RUN_NOT_SENT)
        blocked.append(GATE_AUDIT_RESPONSE_FROM_EXCHANGE_FALSE)
        blocked.append(GATE_AUDIT_SANITIZED)
        blocked.append(GATE_AUDIT_NO_SECRETS)

        # ===============================================================
        # stage_8_final_stop_adapter_verdict
        # ===============================================================
        blocked.append(GATE_REAL_STOP_ATTACH_EXECUTION_NOT_IMPL)
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
        elif allow_real_stop_execution:
            failed_stage = ""
            status_out = STATUS_REAL_STOP_NOT_IMPL
            mode_out   = MODE_REAL_STOP_EXECUTION_GUARD
        elif allow_stop_dry_run_approval:
            failed_stage = ""
            status_out = STATUS_ADAPTER_READY_EXEC_DISABLED
            mode_out   = MODE_STOP_DRY_RUN_APPROVAL
        else:
            failed_stage = ""
            status_out = STATUS_ADAPTER_READY
            mode_out   = MODE_STOP_ADAPTER_CHECKLIST

        final_stop_adapter_verdict: dict[str, Any] = {
            "stop_dry_run_approval_allowed":        allow_stop_dry_run_approval,
            "real_stop_execution_requested":        bool(allow_real_stop_execution),
            "real_execution_allowed":               False,
            "real_stop_attach_implemented":         False,
            "guarded_stop_attach_dry_run_adapter":  True,
            "stop_attach_only":                     True,
            "entry_included":                       False,
            "cleanup_included":                     False,
            "full_lifecycle_included":              False,
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
            "next_required_task":                   "TASK-014AG_guarded_cleanup_only_dry_run_adapter",
        }
        audit_artifacts["final_stop_adapter_verdict"] = dict(final_stop_adapter_verdict)

        stages[STAGE_8_FINAL_STOP_ADAPTER_VERDICT] = {
            "stage":   STAGE_8_FINAL_STOP_ADAPTER_VERDICT,
            "summary": "Final stop adapter verdict + permanent execution guard.",
            "final_stop_adapter_verdict":           final_stop_adapter_verdict,
        }

        return TinyGuardedStopAttachDryRunAdapterResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            stop_adapter_scope=stop_adapter_scope,
            stop_precondition_contract=stop_precondition_contract,
            manual_confirmation_dry_run_contract=manual_confirmation_dry_run_contract,
            stop_request_envelope=stop_request_envelope,
            stop_readonly_verification_plan=stop_readonly_verification_plan,
            stop_failure_policy=stop_failure_policy,
            audit_artifacts=audit_artifacts,
            final_stop_adapter_verdict=final_stop_adapter_verdict,
            stop_dry_run_approval_allowed=allow_stop_dry_run_approval,
            real_stop_execution_requested=bool(allow_real_stop_execution),
            real_execution_allowed=False,
            real_stop_attach_implemented=False,
            guarded_stop_attach_dry_run_adapter=True,
            stop_attach_only=True,
            entry_included=False,
            cleanup_included=False,
            full_lifecycle_included=False,
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
            GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING,
            GATE_LIFECYCLE_SUMMARY_MISSING,
            GATE_RUNNER_DESIGN_MISSING,
            GATE_RUNNER_DRY_RUN_MISSING,
            GATE_GUARDED_DESIGN_REVIEW_MISSING,
            GATE_GUARDED_ENTRY_ADAPTER_MISSING,
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE,
            GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE,
            GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE,
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
    "STOP_TOKEN_PATTERN",
    "REQUIRED_CONFIRMATION_FLAGS",
    "ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES",
    "ACCEPTABLE_RUNNER_DESIGN_STATUSES",
    "ACCEPTABLE_RUNNER_DRY_RUN_STATUSES",
    "ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES",
    "ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES",
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_LIFECYCLE_STATUS",
    "EXPECTED_INSTRUMENT_CATEGORY",
    "EXPECTED_POST_ENTRY_SYMBOL",
    "EXPECTED_POST_ENTRY_SIDE",
    "EXPECTED_POST_ENTRY_QTY",
    "EXPECTED_ENTRY_REFERENCE_PRICE",
    "EXPECTED_STOP_LOSS",
    "EXPECTED_TPSL_MODE",
    "EXPECTED_SL_TRIGGER_BY",
    "EXPECTED_POSITION_IDX",
    "EXPECTED_TICK_SIZE",
    "EXPECTED_MAX_NOTIONAL_USDT",
    "EXPECTED_EXISTING_POSITION_COUNT",
    "FORBIDDEN_LOG_FIELDS",
    "READINESS_CONCLUSION_NOT_EXECUTABLE",
    "DRY_RUN_NOT_SENT_MARKER",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_STOP_ADAPTER_SCOPE",
    "STAGE_2_STOP_PRECONDITION_CONTRACT",
    "STAGE_3_MANUAL_CONFIRMATION_DRY_RUN_CONTRACT",
    "STAGE_4_STOP_REQUEST_ENVELOPE_DRY_RUN",
    "STAGE_5_STOP_READONLY_VERIFICATION_PLAN",
    "STAGE_6_STOP_FAILURE_POLICY",
    "STAGE_7_AUDIT_ARTIFACT_GENERATION",
    "STAGE_8_FINAL_STOP_ADAPTER_VERDICT",
    "ALL_STAGES",
    "STATUS_ADAPTER_READY",
    "STATUS_ADAPTER_READY_EXEC_DISABLED",
    "STATUS_REAL_STOP_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_STOP_ADAPTER_CHECKLIST",
    "MODE_STOP_DRY_RUN_APPROVAL",
    "MODE_REAL_STOP_EXECUTION_GUARD",
    "MODE_FAIL_CLOSED",
    # general (24)
    "GATE_READONLY_SMOKE_MISSING",
    "GATE_RECONCILIATION_MISSING",
    "GATE_PROTECTION_MISSING",
    "GATE_CONTRACT_MISSING",
    "GATE_NOOP_PLAN_MISSING",
    "GATE_LIFECYCLE_MOCK_MISSING",
    "GATE_REAL_PERMISSION_GATE_MISSING",
    "GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING",
    "GATE_LIFECYCLE_SUMMARY_MISSING",
    "GATE_RUNNER_DESIGN_MISSING",
    "GATE_RUNNER_DRY_RUN_MISSING",
    "GATE_GUARDED_DESIGN_REVIEW_MISSING",
    "GATE_GUARDED_ENTRY_ADAPTER_MISSING",
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_MISSING",
    "GATE_SELECTED_SYMBOL_NOT_SOLUSDT",
    "GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE",
    "GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE",
    "GATE_GUARDED_ENTRY_ADAPTER_STATUS_UNACCEPTABLE",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # scope (11)
    "GATE_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_ONLY",
    "GATE_STOP_ATTACH_ONLY",
    "GATE_ENTRY_NOT_INCLUDED",
    "GATE_CLEANUP_NOT_INCLUDED",
    "GATE_FULL_LIFECYCLE_NOT_INCLUDED",
    "GATE_REAL_STOP_ATTACH_NOT_IMPLEMENTED",
    "GATE_REAL_EXECUTION_NOT_ALLOWED",
    "GATE_NO_ENDPOINT_INVOKED",
    "GATE_NO_POSITION_MODIFIED_SCOPE",
    "GATE_NO_SECRETS_LOADED",
    "GATE_NO_G20_LIFT",
    # precondition (17)
    "GATE_PRECONDITION_SYMBOL_MATCHES",
    "GATE_PRECONDITION_EXPECTED_ENTRY_SYMBOL",
    "GATE_PRECONDITION_SIDE_LONG",
    "GATE_PRECONDITION_QTY_TINY",
    "GATE_PRECONDITION_ENTRY_REFERENCE_VALID",
    "GATE_PRECONDITION_STOP_LOSS_VALUE",
    "GATE_PRECONDITION_STOP_LOSS_BELOW_ENTRY",
    "GATE_PRECONDITION_STOP_LOSS_TICK_ALIGNED",
    "GATE_PRECONDITION_TPSL_MODE_FULL",
    "GATE_PRECONDITION_SL_TRIGGER_BY_MARK_PRICE",
    "GATE_PRECONDITION_POSITION_IDX_ZERO",
    "GATE_PRECONDITION_CATEGORY_LINEAR",
    "GATE_PRECONDITION_SELECTED_SYMBOL_PRESENT",
    "GATE_PRECONDITION_EXPECTED_PROTECTED_LIST",
    "GATE_PRECONDITION_PROOF_STRENGTH_STRONG",
    "GATE_PRECONDITION_ACCOUNT_MODE_DEMO",
    "GATE_PRECONDITION_ENDPOINT_FAMILY_BYBIT_DEMO",
    # manual confirmation (11)
    "GATE_STOP_TOKEN_PATTERN_PRESENT",
    "GATE_TOKEN_NOT_VALIDATED",
    "GATE_TOKEN_FORMAT_NOT_AUTHORIZATION",
    "GATE_SECOND_CONFIRMATION_DOCUMENTED",
    "GATE_MAX_NOTIONAL_FLAG_DOCUMENTED",
    "GATE_EXPECTED_COUNT_FLAG_DOCUMENTED",
    "GATE_EXPECTED_SYMBOLS_FLAG_DOCUMENTED",
    "GATE_EXPECTED_ENTRY_SYMBOL_FLAG_DOCUMENTED",
    "GATE_EXPECTED_ENTRY_QTY_FLAG_DOCUMENTED",
    "GATE_EXPECTED_STOP_LOSS_FLAG_DOCUMENTED",
    "GATE_CONFIRMATION_FLAGS_NOT_VALIDATED",
    # envelope (13)
    "GATE_STOP_ENVELOPE_PRESENT",
    "GATE_ENVELOPE_PREVIEW_ONLY",
    "GATE_ENVELOPE_SEND_NOT_ALLOWED",
    "GATE_ENVELOPE_ENDPOINT_NOT_CALLED",
    "GATE_ENVELOPE_NOT_REAL_PAYLOAD",
    "GATE_ENVELOPE_NO_SIGNATURE",
    "GATE_ENVELOPE_NO_PRIVATE_HEADERS",
    "GATE_ENVELOPE_TRADING_STOP_PATH",
    "GATE_ENVELOPE_BASE_URL_DEMO_ONLY",
    "GATE_ENVELOPE_STOP_LOSS_VALUE",
    "GATE_ENVELOPE_TPSL_MODE_FULL",
    "GATE_ENVELOPE_SL_TRIGGER_BY_MARK_PRICE",
    "GATE_NO_SENDER_ADAPTER",
    # readonly plan (11)
    "GATE_PRE_STOP_READONLY_REQUIRED",
    "GATE_POST_STOP_READONLY_REQUIRED",
    "GATE_PRE_STOP_SELECTED_SYMBOL_PRESENT",
    "GATE_PRE_STOP_EXPECTED_SYMBOL",
    "GATE_PRE_STOP_EXPECTED_QTY",
    "GATE_PRE_STOP_EXPECTED_SIDE_LONG",
    "GATE_POST_STOP_EXPECTED_STOP_LOSS",
    "GATE_POST_STOP_EXPECTED_TRIGGER_BY",
    "GATE_EXISTING_POSITIONS_UNCHANGED_REQUIRED",
    "GATE_VERIFICATION_PLAN_ONLY",
    "GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED",
    # failure policy (14)
    "GATE_REQUEST_REJECTED_FAIL_CLOSED",
    "GATE_SELECTED_SYMBOL_ABSENT_FAIL_CLOSED",
    "GATE_SELECTED_SYMBOL_SIDE_MISMATCH_FAIL_CLOSED",
    "GATE_SELECTED_SYMBOL_QTY_MISMATCH_FAIL_CLOSED",
    "GATE_STOP_LOSS_INVALID_FAIL_CLOSED",
    "GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW",
    "GATE_READONLY_UNAVAILABLE_FAIL_CLOSED",
    "GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED",
    "GATE_SECRET_EMISSION_FAIL_CLOSED",
    "GATE_NO_AUTO_RETRY",
    "GATE_NO_AUTO_CLEANUP",
    "GATE_NO_AUTO_EMERGENCY_CLOSE",
    "GATE_NO_AUTO_ENTRY",
    "GATE_NO_AUTO_NEXT_STEP",
    # audit (5)
    "GATE_AUDIT_ARTIFACTS_PRESENT",
    "GATE_AUDIT_RESPONSE_DRY_RUN_NOT_SENT",
    "GATE_AUDIT_RESPONSE_FROM_EXCHANGE_FALSE",
    "GATE_AUDIT_SANITIZED",
    "GATE_AUDIT_NO_SECRETS",
    # execution guard (5)
    "GATE_REAL_STOP_ATTACH_EXECUTION_NOT_IMPL",
    "GATE_NO_REAL_ORDER_ENDPOINT",
    "GATE_NO_REAL_STOP_ENDPOINT",
    "GATE_NO_POSITION_MODIFIED",
    "GATE_G20_NOT_LIFTED",
    # data
    "DemoTinyGuardedStopAttachDryRunAdapter",
    "TinyGuardedStopAttachDryRunAdapterResult",
]
