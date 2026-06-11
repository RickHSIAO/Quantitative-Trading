"""
src/demo_tiny_guarded_entry_dry_run_adapter.py
TASK-014AE: Guarded Entry-only Dry-run Adapter.

Pure-computation / dry-run adapter for the future guarded
`guarded_entry_only` command.  Consolidates 12 upstream artifacts
(readonly / reconciliation / protection / contract / noop_plan /
lifecycle_mock / tiny_position_real_permission_gate /
tiny_entry_permission_gate / tiny_lifecycle_real_execution_summary /
tiny_lifecycle_runner_design / tiny_lifecycle_runner_dry_run /
tiny_lifecycle_guarded_runner_design_review) and emits a dry-run
adapter artifact answering: if some future task ever wants to graduate
to a guarded real *entry* (entry only --- no stop attach, no cleanup,
no full lifecycle), what inputs, preconditions, manual confirmations,
preview request envelope, readonly verification plan, failure policy,
and audit artifacts are required?

This module DOES NOT implement, design, or invoke a real entry sender.
No /v5/order/create call, no /v5/position/trading-stop call, no order
send, no position modification, no close-only, no emergency close, no
leverage / transfer / withdraw, no token validation, no socket open,
no .env read, no dotenv, no signing.  It does not modify main.py,
src/risk.py, or BybitExecutor.

Stages:

  stage_0_artifact_preflight
      Validate 12 upstream artifacts + runtime proof envelope + the
      TASK-014AD guarded_runner_design_review readiness_conclusion is
      DESIGN_REVIEW_READY_NOT_EXECUTABLE.

  stage_1_entry_adapter_scope
      Assert entry-only dry-run adapter scope.  Not full lifecycle;
      no stop attach; no cleanup; no real entry implemented; no
      endpoint invoked; no position modified; no secrets loaded.

  stage_2_entry_precondition_contract
      Document the preconditions any future guarded_entry_only command
      must satisfy: selected symbol=SOLUSDT, side=Buy, qty=0.1,
      reduceOnly=False, positionIdx=0, orderType=Market, max notional
      cap 10 USDT, selected symbol absent before entry, expected
      existing 5 protected positions, proof_strength STRONG,
      account_mode demo, endpoint_family bybit_demo.

  stage_3_manual_confirmation_dry_run_contract
      Document the entry token pattern (CONFIRM_DEMO_TINY_ENTRY_*),
      --i-understand-this-is-demo-real-execution,
      --max-notional-usdt 10, --expected-existing-position-count 5,
      and --expected-existing-symbols.  Tokens / flags are NEVER
      validated by this task.

  stage_4_entry_request_envelope_dry_run
      Build a single preview-only entry request envelope mirrored from
      the upstream permission gate / runner dry-run preview payload.
      preview_only=True, send_allowed=False, endpoint_called=False,
      real_payload=False, signature_present=False, private_headers=[],
      endpoint_path_ref=/v5/order/create, base_url_ref=demo only,
      orderLinkId keeps DRYRUN prefix.

  stage_5_entry_readonly_verification_plan
      Pre-entry readonly required.  Post-entry readonly required.
      Pre-entry expects selected_symbol absent and 5 protected
      positions intact.  Post-entry expects selected_symbol present
      with qty=0.1 / side=long and 5 protected positions unchanged.
      Real readonly after execution is NOT performed in this task ---
      verification_plan_only=True.

  stage_6_entry_failure_policy
      Future guarded_entry_only failure policy: rejection / partial
      fill / selected-symbol-already-exists / readonly unavailable /
      live endpoint detected / secret emission detected => FAIL_CLOSED.
      Existing protected position mismatch => MANUAL_REVIEW_REQUIRED.
      No auto retry / cleanup / emergency close / stop attach /
      next step.

  stage_7_audit_artifact_generation
      Audit artifacts emitted: precondition_contract /
      manual_confirmation_contract / entry_request_envelope /
      readonly_verification_plan / failure_policy /
      final_entry_adapter_verdict.  response status fixed to
      DRY_RUN_NOT_SENT, response_from_exchange=False, sanitized=True,
      no secrets.

  stage_8_final_entry_adapter_verdict
      Resolve final status:
          TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY            (default)
          TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED
              (--allow-entry-dry-run-approval)
          REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
              (--allow-real-entry-execution)
          FAIL_CLOSED                                         (hard-fail)
      Always emits real_execution_allowed=False,
      real_entry_implemented=False, send_allowed=False,
      order_endpoint_called=False, stop_endpoint_called=False,
      no_position_modified=True, no_secrets_loaded=True,
      g20_lifted=False.

Modes:
  entry_adapter_checklist                 --- default
  entry_dry_run_approval                  --- --allow-entry-dry-run-approval
  real_entry_execution_guard              --- --allow-real-entry-execution
  fail_closed                             --- upstream / consistency failed

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

STAGE_0_ARTIFACT_PREFLIGHT                  = "stage_0_artifact_preflight"
STAGE_1_ENTRY_ADAPTER_SCOPE                 = "stage_1_entry_adapter_scope"
STAGE_2_ENTRY_PRECONDITION_CONTRACT         = "stage_2_entry_precondition_contract"
STAGE_3_MANUAL_CONFIRMATION_DRY_RUN_CONTRACT = "stage_3_manual_confirmation_dry_run_contract"
STAGE_4_ENTRY_REQUEST_ENVELOPE_DRY_RUN      = "stage_4_entry_request_envelope_dry_run"
STAGE_5_ENTRY_READONLY_VERIFICATION_PLAN    = "stage_5_entry_readonly_verification_plan"
STAGE_6_ENTRY_FAILURE_POLICY                = "stage_6_entry_failure_policy"
STAGE_7_AUDIT_ARTIFACT_GENERATION           = "stage_7_audit_artifact_generation"
STAGE_8_FINAL_ENTRY_ADAPTER_VERDICT         = "stage_8_final_entry_adapter_verdict"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_ENTRY_ADAPTER_SCOPE,
    STAGE_2_ENTRY_PRECONDITION_CONTRACT,
    STAGE_3_MANUAL_CONFIRMATION_DRY_RUN_CONTRACT,
    STAGE_4_ENTRY_REQUEST_ENVELOPE_DRY_RUN,
    STAGE_5_ENTRY_READONLY_VERIFICATION_PLAN,
    STAGE_6_ENTRY_FAILURE_POLICY,
    STAGE_7_AUDIT_ARTIFACT_GENERATION,
    STAGE_8_FINAL_ENTRY_ADAPTER_VERDICT,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_ADAPTER_READY                = "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY"
STATUS_ADAPTER_READY_EXEC_DISABLED  = (
    "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_ENTRY_NOT_IMPL          = "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                  = "FAIL_CLOSED"

MODE_ENTRY_ADAPTER_CHECKLIST        = "entry_adapter_checklist"
MODE_ENTRY_DRY_RUN_APPROVAL         = "entry_dry_run_approval"
MODE_REAL_ENTRY_EXECUTION_GUARD     = "real_entry_execution_guard"
MODE_FAIL_CLOSED                    = "fail_closed"

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


# ---------------------------------------------------------------------------
# Approval token / flag patterns (documentation only --- never validated here)
# ---------------------------------------------------------------------------

ENTRY_TOKEN_PATTERN       = "CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SYMBOL"

REQUIRED_CONFIRMATION_FLAGS: tuple[str, ...] = (
    "--i-understand-this-is-demo-real-execution",
    "--max-notional-usdt 10",
    "--expected-existing-position-count 5",
    "--expected-existing-symbols AIXBTUSDT,ENAUSDT,TIAUSDT,POLYXUSDT,EDUUSDT",
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
# Future guarded entry payload contract (documentation only)
# ---------------------------------------------------------------------------

EXPECTED_ENTRY_SIDE              = "Buy"
EXPECTED_ENTRY_QTY               = 0.1
EXPECTED_ENTRY_REDUCE_ONLY       = False
EXPECTED_ENTRY_POSITION_IDX      = 0
EXPECTED_ENTRY_ORDER_TYPE        = "Market"
EXPECTED_MAX_NOTIONAL_USDT       = 10.0
EXPECTED_POST_ENTRY_SIDE         = "long"
EXPECTED_EXISTING_POSITION_COUNT = 5

ORDER_LINK_ID_DRYRUN_PREFIX      = "DRYRUN_ENTRY_"

FORBIDDEN_LOG_FIELDS: tuple[str, ...] = (
    "api_key_value", "api_secret_value", "signature_value",
    "auth_header_value", "sign_header_value", "bearer_token_value",
)


# ---------------------------------------------------------------------------
# Gate constants (96 total)
# General (23) + Scope (11) + Precondition (12) + Manual confirmation (8)
# + Envelope (11) + Readonly plan (9) + Failure policy (12) + Audit (5)
# + Execution guard (5) = 96
# ---------------------------------------------------------------------------

# General gates (23)
GATE_READONLY_SMOKE_MISSING                     = "readonly_smoke_missing"
GATE_RECONCILIATION_MISSING                     = "reconciliation_missing"
GATE_PROTECTION_MISSING                         = "protection_missing"
GATE_CONTRACT_MISSING                           = "contract_missing"
GATE_NOOP_PLAN_MISSING                          = "noop_plan_missing"
GATE_LIFECYCLE_MOCK_MISSING                     = "lifecycle_mock_missing"
GATE_REAL_PERMISSION_GATE_MISSING               = "real_permission_gate_missing"
GATE_TINY_ENTRY_PERMISSION_GATE_MISSING         = "tiny_entry_permission_gate_missing"
GATE_LIFECYCLE_SUMMARY_MISSING                  = "lifecycle_summary_missing"
GATE_RUNNER_DESIGN_MISSING                      = "runner_design_missing"
GATE_RUNNER_DRY_RUN_MISSING                     = "runner_dry_run_missing"
GATE_GUARDED_DESIGN_REVIEW_MISSING              = "guarded_design_review_missing"
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO             = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                      = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG                  = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY  = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_COLLIDES_EXISTING          = "selected_symbol_collides_with_existing_position"
GATE_SELECTED_SYMBOL_MISSING                    = "selected_symbol_missing"
GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE  = "guarded_design_review_status_unacceptable"
GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE = "guarded_design_review_readiness_executable"
GATE_G20_POLICY_STILL_IN_PLACE                  = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                           = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                         = "no_secret_values_emitted_in_this_task"

# Scope gates (11)
GATE_GUARDED_ENTRY_DRY_RUN_ADAPTER_ONLY         = "guarded_entry_dry_run_adapter_only"
GATE_ENTRY_ONLY                                 = "entry_only"
GATE_STOP_ATTACH_NOT_INCLUDED                   = "stop_attach_not_included"
GATE_CLEANUP_NOT_INCLUDED                       = "cleanup_not_included"
GATE_FULL_LIFECYCLE_NOT_INCLUDED                = "full_lifecycle_not_included"
GATE_REAL_ENTRY_NOT_IMPLEMENTED                 = "real_entry_not_implemented_in_this_task"
GATE_REAL_EXECUTION_NOT_ALLOWED                 = "real_execution_not_allowed_in_this_task"
GATE_NO_ENDPOINT_INVOKED                        = "no_endpoint_invoked_in_this_task"
GATE_NO_POSITION_MODIFIED_SCOPE                 = "no_position_modified_scope"
GATE_NO_SECRETS_LOADED                          = "no_secrets_loaded_in_this_task"
GATE_NO_G20_LIFT                                = "no_g20_policy_lift_in_this_task"

# Precondition gates (12)
GATE_PRECONDITION_SYMBOL_MATCHES                = "precondition_symbol_matches"
GATE_PRECONDITION_SIDE_BUY                      = "precondition_side_buy"
GATE_PRECONDITION_QTY_TINY                      = "precondition_qty_tiny"
GATE_PRECONDITION_REDUCE_ONLY_FALSE             = "precondition_reduce_only_false"
GATE_PRECONDITION_POSITION_IDX_ZERO             = "precondition_position_idx_zero"
GATE_PRECONDITION_ORDER_TYPE_MARKET             = "precondition_order_type_market"
GATE_PRECONDITION_MAX_NOTIONAL_CAP              = "precondition_max_notional_cap"
GATE_PRECONDITION_SELECTED_SYMBOL_ABSENT        = "precondition_selected_symbol_absent_before_entry"
GATE_PRECONDITION_EXPECTED_PROTECTED_LIST       = "precondition_expected_protected_list_documented"
GATE_PRECONDITION_PROOF_STRENGTH_STRONG         = "precondition_proof_strength_strong"
GATE_PRECONDITION_ACCOUNT_MODE_DEMO             = "precondition_account_mode_demo"
GATE_PRECONDITION_ENDPOINT_FAMILY_BYBIT_DEMO    = "precondition_endpoint_family_bybit_demo"

# Manual confirmation gates (8)
GATE_ENTRY_TOKEN_PATTERN_PRESENT                = "entry_token_pattern_present"
GATE_TOKEN_NOT_VALIDATED                        = "token_not_validated_in_this_task"
GATE_TOKEN_FORMAT_NOT_AUTHORIZATION             = "token_format_not_authorization"
GATE_SECOND_CONFIRMATION_DOCUMENTED             = "second_confirmation_documented"
GATE_MAX_NOTIONAL_FLAG_DOCUMENTED               = "max_notional_flag_documented"
GATE_EXPECTED_COUNT_FLAG_DOCUMENTED             = "expected_count_flag_documented"
GATE_EXPECTED_SYMBOLS_FLAG_DOCUMENTED           = "expected_symbols_flag_documented"
GATE_CONFIRMATION_FLAGS_NOT_VALIDATED           = "confirmation_flags_not_validated"

# Envelope gates (11)
GATE_ENTRY_ENVELOPE_PRESENT                     = "entry_envelope_present"
GATE_ENVELOPE_PREVIEW_ONLY                      = "envelope_preview_only_true"
GATE_ENVELOPE_SEND_NOT_ALLOWED                  = "envelope_send_allowed_false"
GATE_ENVELOPE_ENDPOINT_NOT_CALLED               = "envelope_endpoint_called_false"
GATE_ENVELOPE_NOT_REAL_PAYLOAD                  = "envelope_real_payload_false"
GATE_ENVELOPE_NO_SIGNATURE                      = "envelope_signature_absent"
GATE_ENVELOPE_NO_PRIVATE_HEADERS                = "envelope_private_headers_empty"
GATE_ENVELOPE_ORDER_CREATE_PATH                 = "envelope_endpoint_path_order_create"
GATE_ENVELOPE_BASE_URL_DEMO_ONLY                = "envelope_base_url_demo_only"
GATE_ENVELOPE_ORDER_LINK_ID_DRYRUN_PREFIX       = "envelope_order_link_id_dryrun_prefix"
GATE_NO_SENDER_ADAPTER                          = "no_sender_adapter_in_this_task"

# Readonly plan gates (9)
GATE_PRE_ENTRY_READONLY_REQUIRED                = "pre_entry_readonly_required"
GATE_POST_ENTRY_READONLY_REQUIRED               = "post_entry_readonly_required"
GATE_PRE_ENTRY_SELECTED_SYMBOL_ABSENT           = "pre_entry_selected_symbol_absent"
GATE_POST_ENTRY_EXPECTED_SYMBOL                 = "post_entry_expected_symbol_solusdt"
GATE_POST_ENTRY_EXPECTED_QTY                    = "post_entry_expected_qty_tiny"
GATE_POST_ENTRY_EXPECTED_SIDE_LONG              = "post_entry_expected_side_long"
GATE_EXISTING_POSITIONS_UNCHANGED_REQUIRED      = "existing_positions_unchanged_required"
GATE_VERIFICATION_PLAN_ONLY                     = "verification_plan_only"
GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED = "real_readonly_after_execution_not_performed"

# Failure policy gates (12)
GATE_REQUEST_REJECTED_FAIL_CLOSED               = "request_rejected_fail_closed"
GATE_PARTIAL_FILL_FAIL_CLOSED                   = "partial_fill_fail_closed"
GATE_SELECTED_SYMBOL_EXISTS_FAIL_CLOSED         = "selected_symbol_exists_fail_closed"
GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW  = "protected_position_mismatch_manual_review"
GATE_READONLY_UNAVAILABLE_FAIL_CLOSED           = "readonly_unavailable_fail_closed"
GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED         = "live_endpoint_detected_fail_closed"
GATE_SECRET_EMISSION_FAIL_CLOSED                = "secret_emission_fail_closed"
GATE_NO_AUTO_RETRY                              = "no_auto_retry"
GATE_NO_AUTO_CLEANUP                            = "no_auto_cleanup"
GATE_NO_AUTO_EMERGENCY_CLOSE                    = "no_auto_emergency_close"
GATE_NO_AUTO_STOP_ATTACH                        = "no_auto_stop_attach"
GATE_NO_AUTO_NEXT_STEP                          = "no_auto_next_step"

# Audit gates (5)
GATE_AUDIT_ARTIFACTS_PRESENT                    = "audit_artifacts_present"
GATE_AUDIT_RESPONSE_DRY_RUN_NOT_SENT            = "audit_response_dry_run_not_sent"
GATE_AUDIT_RESPONSE_FROM_EXCHANGE_FALSE         = "audit_response_from_exchange_false"
GATE_AUDIT_SANITIZED                            = "audit_sanitized"
GATE_AUDIT_NO_SECRETS                           = "audit_no_secrets"

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
    GATE_LIFECYCLE_SUMMARY_MISSING,
    GATE_RUNNER_DESIGN_MISSING,
    GATE_RUNNER_DRY_RUN_MISSING,
    GATE_GUARDED_DESIGN_REVIEW_MISSING,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE,
    GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyGuardedEntryDryRunAdapterResult:
    """Read-only outcome of one guarded entry dry-run adapter pass."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    entry_adapter_scope:           dict[str, Any] = field(default_factory=dict)
    entry_precondition_contract:   dict[str, Any] = field(default_factory=dict)
    manual_confirmation_dry_run_contract: dict[str, Any] = field(default_factory=dict)
    entry_request_envelope:        dict[str, Any] = field(default_factory=dict)
    entry_readonly_verification_plan: dict[str, Any] = field(default_factory=dict)
    entry_failure_policy:          dict[str, Any] = field(default_factory=dict)
    audit_artifacts:               dict[str, Any] = field(default_factory=dict)
    final_entry_adapter_verdict:   dict[str, Any] = field(default_factory=dict)

    entry_token_pattern:           str = ENTRY_TOKEN_PATTERN
    required_confirmation_flags:   list[str] = field(
        default_factory=lambda: list(REQUIRED_CONFIRMATION_FLAGS),
    )

    # Adapter gating flags.
    entry_dry_run_approval_allowed:   bool = False
    real_entry_execution_requested:   bool = False
    real_execution_allowed:           bool = False
    real_entry_implemented:           bool = False
    guarded_entry_dry_run_adapter:    bool = True
    entry_only:                       bool = True
    stop_attach_included:             bool = False
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
    upstream_lifecycle_summary_status: str = ""
    upstream_runner_design_status:     str = ""
    upstream_runner_dry_run_status:    str = ""
    upstream_guarded_design_review_status: str = ""
    upstream_guarded_design_review_readiness_conclusion: str = ""

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = "TASK-014AF_guarded_stop_attach_only_dry_run_adapter"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                       self.timestamp_utc,
            "timestamp_utc":                   self.timestamp_utc,
            "mode":                            self.mode,
            "selected_symbol":                 self.selected_symbol,
            "existing_position_symbols":       list(self.existing_position_symbols),
            "stages":                          {k: dict(v) for k, v in self.stages.items()},
            "stage_order":                     list(self.stage_order),
            "entry_adapter_scope":             dict(self.entry_adapter_scope),
            "entry_precondition_contract":     dict(self.entry_precondition_contract),
            "manual_confirmation_dry_run_contract": dict(self.manual_confirmation_dry_run_contract),
            "entry_request_envelope":          dict(self.entry_request_envelope),
            "entry_readonly_verification_plan": dict(self.entry_readonly_verification_plan),
            "entry_failure_policy":            dict(self.entry_failure_policy),
            "audit_artifacts":                 dict(self.audit_artifacts),
            "final_entry_adapter_verdict":     dict(self.final_entry_adapter_verdict),
            "entry_token_pattern":             self.entry_token_pattern,
            "required_confirmation_flags":     list(self.required_confirmation_flags),
            "entry_dry_run_approval_allowed":  self.entry_dry_run_approval_allowed,
            "real_entry_execution_requested":  self.real_entry_execution_requested,
            "real_execution_allowed":          self.real_execution_allowed,
            "real_entry_implemented":          self.real_entry_implemented,
            "guarded_entry_dry_run_adapter":   self.guarded_entry_dry_run_adapter,
            "entry_only":                      self.entry_only,
            "stop_attach_included":            self.stop_attach_included,
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
            "upstream_lifecycle_summary_status": self.upstream_lifecycle_summary_status,
            "upstream_runner_design_status":   self.upstream_runner_design_status,
            "upstream_runner_dry_run_status":  self.upstream_runner_dry_run_status,
            "upstream_guarded_design_review_status": self.upstream_guarded_design_review_status,
            "upstream_guarded_design_review_readiness_conclusion":
                self.upstream_guarded_design_review_readiness_conclusion,
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
# Guarded entry dry-run adapter
# ---------------------------------------------------------------------------

class DemoTinyGuardedEntryDryRunAdapter:
    """
    Pure-computation guarded entry dry-run adapter.  Consolidates the 12
    upstream artifacts (10 baseline + AA lifecycle summary + AB runner
    design + AC runner dry-run + AD guarded design review --- minus the
    stop / cleanup permission gates, since this adapter is entry-only)
    and emits a dry-run adapter artifact answering: what inputs,
    preconditions, manual confirmations, request envelope, readonly
    verification plan, and audit artifacts are required for any future
    guarded_entry_only command?

    Holds no network client, reads no environment variables, opens no
    socket, performs no HMAC signing, and NEVER invokes the
    order-create or trading-stop endpoints.  Does not implement, design,
    or describe a real entry sender that could be executed.

    --allow-entry-dry-run-approval --> status promoted to
        TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED.

    --allow-real-entry-execution --> status fixed to
        REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED  (no socket opened).
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
        lifecycle_summary:                dict[str, Any] | None,
        runner_design:                    dict[str, Any] | None,
        runner_dry_run:                   dict[str, Any] | None,
        guarded_design_review:            dict[str, Any] | None,
        symbol:                           str  = DEFAULT_SELECTED_SYMBOL,
        allow_entry_dry_run_approval:     bool = False,
        allow_real_entry_execution:       bool = False,
        _now:                             datetime | None = None,
    ) -> TinyGuardedEntryDryRunAdapterResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_entry_execution:
            mode = MODE_REAL_ENTRY_EXECUTION_GUARD
        elif allow_entry_dry_run_approval:
            mode = MODE_ENTRY_DRY_RUN_APPROVAL
        else:
            mode = MODE_ENTRY_ADAPTER_CHECKLIST

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
        summary_present      = isinstance(lifecycle_summary, dict) and bool(lifecycle_summary)
        runner_design_present = isinstance(runner_design, dict) and bool(runner_design)
        runner_dry_run_present = isinstance(runner_dry_run, dict) and bool(runner_dry_run)
        guarded_review_present = isinstance(guarded_design_review, dict) and bool(guarded_design_review)

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
        if not summary_present:
            blocked.append(GATE_LIFECYCLE_SUMMARY_MISSING)
        if not runner_design_present:
            blocked.append(GATE_RUNNER_DESIGN_MISSING)
        if not runner_dry_run_present:
            blocked.append(GATE_RUNNER_DRY_RUN_MISSING)
        if not guarded_review_present:
            blocked.append(GATE_GUARDED_DESIGN_REVIEW_MISSING)

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

        if not sym:
            blocked.append(GATE_SELECTED_SYMBOL_MISSING)
        elif sym in existing_symbols:
            blocked.append(GATE_SELECTED_SYMBOL_COLLIDES_EXISTING)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 12 upstream artifacts + runtime proof envelope + AD readiness.",
            "readonly_smoke_present":                   readonly_present,
            "reconciliation_present":                   recon_present,
            "protection_present":                       protection_present,
            "contract_present":                         contract_present,
            "noop_plan_present":                        noop_present,
            "lifecycle_mock_present":                   lifecycle_present,
            "real_permission_gate_present":             real_perm_present,
            "tiny_entry_permission_gate_present":       entry_perm_present,
            "lifecycle_summary_present":                summary_present,
            "runner_design_present":                    runner_design_present,
            "runner_dry_run_present":                   runner_dry_run_present,
            "guarded_design_review_present":            guarded_review_present,
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
            "selected_symbol":                          sym,
            "current_task_real_execution_allowed":      False,
        }

        # ===============================================================
        # stage_1_entry_adapter_scope
        # ===============================================================
        entry_adapter_scope: dict[str, Any] = {
            "guarded_entry_dry_run_adapter":        True,
            "entry_only":                           True,
            "stop_attach_included":                 False,
            "cleanup_included":                     False,
            "full_lifecycle_included":              False,
            "real_entry_implemented":               False,
            "real_execution_allowed":               False,
            "order_endpoint_called":                False,
            "stop_endpoint_called":                 False,
            "no_endpoint_invoked_in_this_task":     True,
            "no_position_modified":                 True,
            "no_secrets_loaded":                    True,
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "next_required_task":                   "TASK-014AF_guarded_stop_attach_only_dry_run_adapter",
            "scope_summary": (
                "TASK-014AE only adapts the future guarded_entry_only "
                "command into a dry-run artifact.  It does not implement "
                "the real entry sender, does not include stop attach or "
                "cleanup, does not run the full lifecycle, does not send "
                "any order, does not call any endpoint, does not load any "
                "secret, and does not touch any existing position."
            ),
        }
        stages[STAGE_1_ENTRY_ADAPTER_SCOPE] = {
            "stage":   STAGE_1_ENTRY_ADAPTER_SCOPE,
            "summary": "Assert guarded entry dry-run adapter scope (entry-only).",
            "entry_adapter_scope":                  entry_adapter_scope,
        }
        blocked.append(GATE_GUARDED_ENTRY_DRY_RUN_ADAPTER_ONLY)
        blocked.append(GATE_ENTRY_ONLY)
        blocked.append(GATE_STOP_ATTACH_NOT_INCLUDED)
        blocked.append(GATE_CLEANUP_NOT_INCLUDED)
        blocked.append(GATE_FULL_LIFECYCLE_NOT_INCLUDED)
        blocked.append(GATE_REAL_ENTRY_NOT_IMPLEMENTED)
        blocked.append(GATE_REAL_EXECUTION_NOT_ALLOWED)
        blocked.append(GATE_NO_ENDPOINT_INVOKED)
        blocked.append(GATE_NO_POSITION_MODIFIED_SCOPE)
        blocked.append(GATE_NO_SECRETS_LOADED)
        blocked.append(GATE_NO_G20_LIFT)

        # ===============================================================
        # stage_2_entry_precondition_contract
        # ===============================================================
        entry_precondition_contract: dict[str, Any] = {
            "symbol":                               EXPECTED_INSTRUMENT_CATEGORY + ":" + (sym or DEFAULT_SELECTED_SYMBOL),
            "selected_symbol":                      sym or DEFAULT_SELECTED_SYMBOL,
            "side":                                 EXPECTED_ENTRY_SIDE,
            "qty":                                  EXPECTED_ENTRY_QTY,
            "reduceOnly":                           EXPECTED_ENTRY_REDUCE_ONLY,
            "positionIdx":                          EXPECTED_ENTRY_POSITION_IDX,
            "orderType":                            EXPECTED_ENTRY_ORDER_TYPE,
            "max_notional_usdt":                    EXPECTED_MAX_NOTIONAL_USDT,
            "selected_symbol_absent_before_entry":  True,
            "expected_existing_position_count":     EXPECTED_EXISTING_POSITION_COUNT,
            "expected_existing_symbols":            list(EXISTING_POSITION_SYMBOLS),
            "proof_strength":                       EXPECTED_PROOF_STRENGTH,
            "account_mode":                         EXPECTED_ACCOUNT_MODE,
            "endpoint_family":                      EXPECTED_ENDPOINT_FAMILY,
            "category":                             EXPECTED_INSTRUMENT_CATEGORY,
        }
        stages[STAGE_2_ENTRY_PRECONDITION_CONTRACT] = {
            "stage":   STAGE_2_ENTRY_PRECONDITION_CONTRACT,
            "summary": "Document the preconditions any future guarded_entry_only command must satisfy.",
            "entry_precondition_contract":          entry_precondition_contract,
        }
        blocked.append(GATE_PRECONDITION_SYMBOL_MATCHES)
        blocked.append(GATE_PRECONDITION_SIDE_BUY)
        blocked.append(GATE_PRECONDITION_QTY_TINY)
        blocked.append(GATE_PRECONDITION_REDUCE_ONLY_FALSE)
        blocked.append(GATE_PRECONDITION_POSITION_IDX_ZERO)
        blocked.append(GATE_PRECONDITION_ORDER_TYPE_MARKET)
        blocked.append(GATE_PRECONDITION_MAX_NOTIONAL_CAP)
        blocked.append(GATE_PRECONDITION_SELECTED_SYMBOL_ABSENT)
        blocked.append(GATE_PRECONDITION_EXPECTED_PROTECTED_LIST)
        blocked.append(GATE_PRECONDITION_PROOF_STRENGTH_STRONG)
        blocked.append(GATE_PRECONDITION_ACCOUNT_MODE_DEMO)
        blocked.append(GATE_PRECONDITION_ENDPOINT_FAMILY_BYBIT_DEMO)

        # ===============================================================
        # stage_3_manual_confirmation_dry_run_contract
        # ===============================================================
        manual_confirmation_dry_run_contract: dict[str, Any] = {
            "entry_token_pattern":                  ENTRY_TOKEN_PATTERN,
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
        }
        stages[STAGE_3_MANUAL_CONFIRMATION_DRY_RUN_CONTRACT] = {
            "stage":   STAGE_3_MANUAL_CONFIRMATION_DRY_RUN_CONTRACT,
            "summary": "Document the manual confirmation contract (token + flags), never validated.",
            "manual_confirmation_dry_run_contract": manual_confirmation_dry_run_contract,
        }
        blocked.append(GATE_ENTRY_TOKEN_PATTERN_PRESENT)
        blocked.append(GATE_TOKEN_NOT_VALIDATED)
        blocked.append(GATE_TOKEN_FORMAT_NOT_AUTHORIZATION)
        blocked.append(GATE_SECOND_CONFIRMATION_DOCUMENTED)
        blocked.append(GATE_MAX_NOTIONAL_FLAG_DOCUMENTED)
        blocked.append(GATE_EXPECTED_COUNT_FLAG_DOCUMENTED)
        blocked.append(GATE_EXPECTED_SYMBOLS_FLAG_DOCUMENTED)
        blocked.append(GATE_CONFIRMATION_FLAGS_NOT_VALIDATED)

        # ===============================================================
        # stage_4_entry_request_envelope_dry_run
        # ===============================================================
        entry_request_envelope: dict[str, Any] = {
            "preview_only":                         True,
            "send_allowed":                         False,
            "endpoint_called":                      False,
            "real_payload":                         False,
            "signature_present":                    False,
            "private_headers":                      [],
            "endpoint_path_ref":                    ORDER_CREATE_PATH_REF,
            "base_url_ref":                         BASE_URL_DEMO_REF,
            "demo_endpoint_allowlist":              list(DEMO_ENDPOINT_ALLOWLIST),
            "live_endpoint_denylist":               list(LIVE_ENDPOINT_DENYLIST),
            "category":                             EXPECTED_INSTRUMENT_CATEGORY,
            "symbol":                               sym or DEFAULT_SELECTED_SYMBOL,
            "side":                                 EXPECTED_ENTRY_SIDE,
            "qty":                                  EXPECTED_ENTRY_QTY,
            "orderType":                            EXPECTED_ENTRY_ORDER_TYPE,
            "reduceOnly":                           EXPECTED_ENTRY_REDUCE_ONLY,
            "positionIdx":                          EXPECTED_ENTRY_POSITION_IDX,
            "orderLinkId":                          (
                ORDER_LINK_ID_DRYRUN_PREFIX + (sym or DEFAULT_SELECTED_SYMBOL)
            ),
            "no_sender_adapter":                    True,
        }
        stages[STAGE_4_ENTRY_REQUEST_ENVELOPE_DRY_RUN] = {
            "stage":   STAGE_4_ENTRY_REQUEST_ENVELOPE_DRY_RUN,
            "summary": "Build preview-only entry request envelope (no sender adapter, no signature).",
            "entry_request_envelope":               entry_request_envelope,
        }
        blocked.append(GATE_ENTRY_ENVELOPE_PRESENT)
        blocked.append(GATE_ENVELOPE_PREVIEW_ONLY)
        blocked.append(GATE_ENVELOPE_SEND_NOT_ALLOWED)
        blocked.append(GATE_ENVELOPE_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_ENVELOPE_NOT_REAL_PAYLOAD)
        blocked.append(GATE_ENVELOPE_NO_SIGNATURE)
        blocked.append(GATE_ENVELOPE_NO_PRIVATE_HEADERS)
        blocked.append(GATE_ENVELOPE_ORDER_CREATE_PATH)
        blocked.append(GATE_ENVELOPE_BASE_URL_DEMO_ONLY)
        blocked.append(GATE_ENVELOPE_ORDER_LINK_ID_DRYRUN_PREFIX)
        blocked.append(GATE_NO_SENDER_ADAPTER)

        # ===============================================================
        # stage_5_entry_readonly_verification_plan
        # ===============================================================
        entry_readonly_verification_plan: dict[str, Any] = {
            "pre_entry_readonly_required":              True,
            "post_entry_readonly_required":             True,
            "pre_entry_selected_symbol_absent":         True,
            "pre_entry_existing_positions_unchanged":   True,
            "post_entry_expected_symbol":               sym or DEFAULT_SELECTED_SYMBOL,
            "post_entry_expected_qty":                  EXPECTED_ENTRY_QTY,
            "post_entry_expected_side":                 EXPECTED_POST_ENTRY_SIDE,
            "existing_positions_unchanged_required":    True,
            "verification_plan_only":                   True,
            "real_readonly_after_execution_not_performed": True,
        }
        stages[STAGE_5_ENTRY_READONLY_VERIFICATION_PLAN] = {
            "stage":   STAGE_5_ENTRY_READONLY_VERIFICATION_PLAN,
            "summary": "Pre/post readonly verification plan (plan only; never executed).",
            "entry_readonly_verification_plan":     entry_readonly_verification_plan,
        }
        blocked.append(GATE_PRE_ENTRY_READONLY_REQUIRED)
        blocked.append(GATE_POST_ENTRY_READONLY_REQUIRED)
        blocked.append(GATE_PRE_ENTRY_SELECTED_SYMBOL_ABSENT)
        blocked.append(GATE_POST_ENTRY_EXPECTED_SYMBOL)
        blocked.append(GATE_POST_ENTRY_EXPECTED_QTY)
        blocked.append(GATE_POST_ENTRY_EXPECTED_SIDE_LONG)
        blocked.append(GATE_EXISTING_POSITIONS_UNCHANGED_REQUIRED)
        blocked.append(GATE_VERIFICATION_PLAN_ONLY)
        blocked.append(GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED)

        # ===============================================================
        # stage_6_entry_failure_policy
        # ===============================================================
        entry_failure_policy: dict[str, Any] = {
            "request_rejected":                  "FAIL_CLOSED",
            "partial_fill":                      "FAIL_CLOSED",
            "selected_symbol_already_exists":    "FAIL_CLOSED",
            "existing_protected_mismatch":       "MANUAL_REVIEW_REQUIRED",
            "readonly_unavailable":              "FAIL_CLOSED",
            "live_endpoint_detected":            "FAIL_CLOSED",
            "secret_emission_detected":          "FAIL_CLOSED",
            "no_auto_retry":                     True,
            "no_auto_cleanup":                   True,
            "no_auto_emergency_close":           True,
            "no_auto_stop_attach":               True,
            "no_auto_next_step":                 True,
            "manual_intervention_only":          True,
        }
        stages[STAGE_6_ENTRY_FAILURE_POLICY] = {
            "stage":   STAGE_6_ENTRY_FAILURE_POLICY,
            "summary": "Future guarded_entry_only failure / abort policy.",
            "entry_failure_policy":                 entry_failure_policy,
        }
        blocked.append(GATE_REQUEST_REJECTED_FAIL_CLOSED)
        blocked.append(GATE_PARTIAL_FILL_FAIL_CLOSED)
        blocked.append(GATE_SELECTED_SYMBOL_EXISTS_FAIL_CLOSED)
        blocked.append(GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW)
        blocked.append(GATE_READONLY_UNAVAILABLE_FAIL_CLOSED)
        blocked.append(GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_SECRET_EMISSION_FAIL_CLOSED)
        blocked.append(GATE_NO_AUTO_RETRY)
        blocked.append(GATE_NO_AUTO_CLEANUP)
        blocked.append(GATE_NO_AUTO_EMERGENCY_CLOSE)
        blocked.append(GATE_NO_AUTO_STOP_ATTACH)
        blocked.append(GATE_NO_AUTO_NEXT_STEP)

        # ===============================================================
        # stage_7_audit_artifact_generation
        # ===============================================================
        audit_artifacts: dict[str, Any] = {
            "precondition_contract":                dict(entry_precondition_contract),
            "manual_confirmation_contract":         dict(manual_confirmation_dry_run_contract),
            "entry_request_envelope":               dict(entry_request_envelope),
            "readonly_verification_plan":           dict(entry_readonly_verification_plan),
            "failure_policy":                       dict(entry_failure_policy),
            "final_entry_adapter_verdict":          {},  # filled below
            "response_status":                      DRY_RUN_NOT_SENT_MARKER,
            "response_from_exchange":               False,
            "sanitized":                            True,
            "no_secrets":                           True,
            "forbidden_log_fields":                 list(FORBIDDEN_LOG_FIELDS),
        }
        stages[STAGE_7_AUDIT_ARTIFACT_GENERATION] = {
            "stage":   STAGE_7_AUDIT_ARTIFACT_GENERATION,
            "summary": "Emit entry-only dry-run audit artifacts (DRY_RUN_NOT_SENT).",
            "audit_artifacts":                      audit_artifacts,
        }
        blocked.append(GATE_AUDIT_ARTIFACTS_PRESENT)
        blocked.append(GATE_AUDIT_RESPONSE_DRY_RUN_NOT_SENT)
        blocked.append(GATE_AUDIT_RESPONSE_FROM_EXCHANGE_FALSE)
        blocked.append(GATE_AUDIT_SANITIZED)
        blocked.append(GATE_AUDIT_NO_SECRETS)

        # ===============================================================
        # stage_8_final_entry_adapter_verdict
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
        elif allow_entry_dry_run_approval:
            failed_stage = ""
            status_out = STATUS_ADAPTER_READY_EXEC_DISABLED
            mode_out   = MODE_ENTRY_DRY_RUN_APPROVAL
        else:
            failed_stage = ""
            status_out = STATUS_ADAPTER_READY
            mode_out   = MODE_ENTRY_ADAPTER_CHECKLIST

        final_entry_adapter_verdict: dict[str, Any] = {
            "entry_dry_run_approval_allowed":       allow_entry_dry_run_approval,
            "real_entry_execution_requested":       bool(allow_real_entry_execution),
            "real_execution_allowed":               False,
            "real_entry_implemented":               False,
            "guarded_entry_dry_run_adapter":        True,
            "entry_only":                           True,
            "stop_attach_included":                 False,
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
            "next_required_task":                   "TASK-014AF_guarded_stop_attach_only_dry_run_adapter",
        }
        audit_artifacts["final_entry_adapter_verdict"] = dict(final_entry_adapter_verdict)

        stages[STAGE_8_FINAL_ENTRY_ADAPTER_VERDICT] = {
            "stage":   STAGE_8_FINAL_ENTRY_ADAPTER_VERDICT,
            "summary": "Final entry adapter verdict + permanent execution guard.",
            "final_entry_adapter_verdict":          final_entry_adapter_verdict,
        }

        return TinyGuardedEntryDryRunAdapterResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            entry_adapter_scope=entry_adapter_scope,
            entry_precondition_contract=entry_precondition_contract,
            manual_confirmation_dry_run_contract=manual_confirmation_dry_run_contract,
            entry_request_envelope=entry_request_envelope,
            entry_readonly_verification_plan=entry_readonly_verification_plan,
            entry_failure_policy=entry_failure_policy,
            audit_artifacts=audit_artifacts,
            final_entry_adapter_verdict=final_entry_adapter_verdict,
            entry_dry_run_approval_allowed=allow_entry_dry_run_approval,
            real_entry_execution_requested=bool(allow_real_entry_execution),
            real_execution_allowed=False,
            real_entry_implemented=False,
            guarded_entry_dry_run_adapter=True,
            entry_only=True,
            stop_attach_included=False,
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
            GATE_LIFECYCLE_SUMMARY_MISSING,
            GATE_RUNNER_DESIGN_MISSING,
            GATE_RUNNER_DRY_RUN_MISSING,
            GATE_GUARDED_DESIGN_REVIEW_MISSING,
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE,
            GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE,
            GATE_SELECTED_SYMBOL_MISSING,
            GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
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
    "REQUIRED_CONFIRMATION_FLAGS",
    "ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES",
    "ACCEPTABLE_RUNNER_DESIGN_STATUSES",
    "ACCEPTABLE_RUNNER_DRY_RUN_STATUSES",
    "ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES",
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_LIFECYCLE_STATUS",
    "EXPECTED_INSTRUMENT_CATEGORY",
    "EXPECTED_ENTRY_SIDE",
    "EXPECTED_ENTRY_QTY",
    "EXPECTED_ENTRY_REDUCE_ONLY",
    "EXPECTED_ENTRY_POSITION_IDX",
    "EXPECTED_ENTRY_ORDER_TYPE",
    "EXPECTED_MAX_NOTIONAL_USDT",
    "EXPECTED_POST_ENTRY_SIDE",
    "EXPECTED_EXISTING_POSITION_COUNT",
    "ORDER_LINK_ID_DRYRUN_PREFIX",
    "FORBIDDEN_LOG_FIELDS",
    "READINESS_CONCLUSION_NOT_EXECUTABLE",
    "DRY_RUN_NOT_SENT_MARKER",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_ENTRY_ADAPTER_SCOPE",
    "STAGE_2_ENTRY_PRECONDITION_CONTRACT",
    "STAGE_3_MANUAL_CONFIRMATION_DRY_RUN_CONTRACT",
    "STAGE_4_ENTRY_REQUEST_ENVELOPE_DRY_RUN",
    "STAGE_5_ENTRY_READONLY_VERIFICATION_PLAN",
    "STAGE_6_ENTRY_FAILURE_POLICY",
    "STAGE_7_AUDIT_ARTIFACT_GENERATION",
    "STAGE_8_FINAL_ENTRY_ADAPTER_VERDICT",
    "ALL_STAGES",
    "STATUS_ADAPTER_READY",
    "STATUS_ADAPTER_READY_EXEC_DISABLED",
    "STATUS_REAL_ENTRY_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_ENTRY_ADAPTER_CHECKLIST",
    "MODE_ENTRY_DRY_RUN_APPROVAL",
    "MODE_REAL_ENTRY_EXECUTION_GUARD",
    "MODE_FAIL_CLOSED",
    # general (23)
    "GATE_READONLY_SMOKE_MISSING",
    "GATE_RECONCILIATION_MISSING",
    "GATE_PROTECTION_MISSING",
    "GATE_CONTRACT_MISSING",
    "GATE_NOOP_PLAN_MISSING",
    "GATE_LIFECYCLE_MOCK_MISSING",
    "GATE_REAL_PERMISSION_GATE_MISSING",
    "GATE_TINY_ENTRY_PERMISSION_GATE_MISSING",
    "GATE_LIFECYCLE_SUMMARY_MISSING",
    "GATE_RUNNER_DESIGN_MISSING",
    "GATE_RUNNER_DRY_RUN_MISSING",
    "GATE_GUARDED_DESIGN_REVIEW_MISSING",
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_COLLIDES_EXISTING",
    "GATE_SELECTED_SYMBOL_MISSING",
    "GATE_GUARDED_DESIGN_REVIEW_STATUS_UNACCEPTABLE",
    "GATE_GUARDED_DESIGN_REVIEW_READINESS_EXECUTABLE",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # scope (11)
    "GATE_GUARDED_ENTRY_DRY_RUN_ADAPTER_ONLY",
    "GATE_ENTRY_ONLY",
    "GATE_STOP_ATTACH_NOT_INCLUDED",
    "GATE_CLEANUP_NOT_INCLUDED",
    "GATE_FULL_LIFECYCLE_NOT_INCLUDED",
    "GATE_REAL_ENTRY_NOT_IMPLEMENTED",
    "GATE_REAL_EXECUTION_NOT_ALLOWED",
    "GATE_NO_ENDPOINT_INVOKED",
    "GATE_NO_POSITION_MODIFIED_SCOPE",
    "GATE_NO_SECRETS_LOADED",
    "GATE_NO_G20_LIFT",
    # precondition (12)
    "GATE_PRECONDITION_SYMBOL_MATCHES",
    "GATE_PRECONDITION_SIDE_BUY",
    "GATE_PRECONDITION_QTY_TINY",
    "GATE_PRECONDITION_REDUCE_ONLY_FALSE",
    "GATE_PRECONDITION_POSITION_IDX_ZERO",
    "GATE_PRECONDITION_ORDER_TYPE_MARKET",
    "GATE_PRECONDITION_MAX_NOTIONAL_CAP",
    "GATE_PRECONDITION_SELECTED_SYMBOL_ABSENT",
    "GATE_PRECONDITION_EXPECTED_PROTECTED_LIST",
    "GATE_PRECONDITION_PROOF_STRENGTH_STRONG",
    "GATE_PRECONDITION_ACCOUNT_MODE_DEMO",
    "GATE_PRECONDITION_ENDPOINT_FAMILY_BYBIT_DEMO",
    # manual confirmation (8)
    "GATE_ENTRY_TOKEN_PATTERN_PRESENT",
    "GATE_TOKEN_NOT_VALIDATED",
    "GATE_TOKEN_FORMAT_NOT_AUTHORIZATION",
    "GATE_SECOND_CONFIRMATION_DOCUMENTED",
    "GATE_MAX_NOTIONAL_FLAG_DOCUMENTED",
    "GATE_EXPECTED_COUNT_FLAG_DOCUMENTED",
    "GATE_EXPECTED_SYMBOLS_FLAG_DOCUMENTED",
    "GATE_CONFIRMATION_FLAGS_NOT_VALIDATED",
    # envelope (11)
    "GATE_ENTRY_ENVELOPE_PRESENT",
    "GATE_ENVELOPE_PREVIEW_ONLY",
    "GATE_ENVELOPE_SEND_NOT_ALLOWED",
    "GATE_ENVELOPE_ENDPOINT_NOT_CALLED",
    "GATE_ENVELOPE_NOT_REAL_PAYLOAD",
    "GATE_ENVELOPE_NO_SIGNATURE",
    "GATE_ENVELOPE_NO_PRIVATE_HEADERS",
    "GATE_ENVELOPE_ORDER_CREATE_PATH",
    "GATE_ENVELOPE_BASE_URL_DEMO_ONLY",
    "GATE_ENVELOPE_ORDER_LINK_ID_DRYRUN_PREFIX",
    "GATE_NO_SENDER_ADAPTER",
    # readonly plan (9)
    "GATE_PRE_ENTRY_READONLY_REQUIRED",
    "GATE_POST_ENTRY_READONLY_REQUIRED",
    "GATE_PRE_ENTRY_SELECTED_SYMBOL_ABSENT",
    "GATE_POST_ENTRY_EXPECTED_SYMBOL",
    "GATE_POST_ENTRY_EXPECTED_QTY",
    "GATE_POST_ENTRY_EXPECTED_SIDE_LONG",
    "GATE_EXISTING_POSITIONS_UNCHANGED_REQUIRED",
    "GATE_VERIFICATION_PLAN_ONLY",
    "GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED",
    # failure policy (12)
    "GATE_REQUEST_REJECTED_FAIL_CLOSED",
    "GATE_PARTIAL_FILL_FAIL_CLOSED",
    "GATE_SELECTED_SYMBOL_EXISTS_FAIL_CLOSED",
    "GATE_PROTECTED_POSITION_MISMATCH_MANUAL_REVIEW",
    "GATE_READONLY_UNAVAILABLE_FAIL_CLOSED",
    "GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED",
    "GATE_SECRET_EMISSION_FAIL_CLOSED",
    "GATE_NO_AUTO_RETRY",
    "GATE_NO_AUTO_CLEANUP",
    "GATE_NO_AUTO_EMERGENCY_CLOSE",
    "GATE_NO_AUTO_STOP_ATTACH",
    "GATE_NO_AUTO_NEXT_STEP",
    # audit (5)
    "GATE_AUDIT_ARTIFACTS_PRESENT",
    "GATE_AUDIT_RESPONSE_DRY_RUN_NOT_SENT",
    "GATE_AUDIT_RESPONSE_FROM_EXCHANGE_FALSE",
    "GATE_AUDIT_SANITIZED",
    "GATE_AUDIT_NO_SECRETS",
    # execution guard (5)
    "GATE_REAL_ENTRY_EXECUTION_NOT_IMPL",
    "GATE_NO_REAL_ORDER_ENDPOINT",
    "GATE_NO_REAL_STOP_ENDPOINT",
    "GATE_NO_POSITION_MODIFIED",
    "GATE_G20_NOT_LIFTED",
    # data
    "DemoTinyGuardedEntryDryRunAdapter",
    "TinyGuardedEntryDryRunAdapterResult",
]
