"""
src/demo_tiny_lifecycle_runner_dry_run.py
TASK-014AC: Tiny Lifecycle Runner Implementation / Dry-run Only.

Pure-computation / dry-run only module.  Consolidates the 12 upstream
artifacts (readonly / reconciliation / protection / contract / noop_plan
/ lifecycle_mock / tiny_position_real_permission_gate /
tiny_entry_permission_gate / tiny_stop_attach_permission_gate /
tiny_cleanup_permission_gate / tiny_lifecycle_real_execution_summary /
tiny_lifecycle_runner_design) and emits a *dry-run execution trace*
that exercises the 8-step lifecycle without sending any real order
or invoking any real endpoint.

This module DOES NOT execute anything against Bybit: no
/v5/order/create, no /v5/position/trading-stop, no order send,
no position modification, no close-only, no emergency close, no
leverage / transfer / withdraw, no token validation, no socket open,
no .env read, no dotenv, no signing.  It only materialises the
dry-run trace that the future real runner WILL follow.

Stages:

  stage_0_artifact_preflight
      Validate 12 upstream artifacts + runtime proof envelope.

  stage_1_dry_run_scope
      Assert dry-run-only / no real runner implemented / no endpoint
      invocation / no position modification / no secrets loaded.

  stage_2_state_machine_trace
      Generate the 8-step state trace.  Each step records
      state_before / action / state_after / artifact_slot together with
      endpoint_called=False / position_modified=False /
      auto_advanced=False / token_validated=False.

  stage_3_dry_run_payload_materialization
      Materialise dry-run request envelopes from the three permission
      gates (entry / stop / cleanup).  Each envelope keeps
      preview_only=True / endpoint_called=False / send_allowed=False /
      real_payload=False.  No signature, no private headers, no adapter
      invocation.

  stage_4_readonly_verification_simulation
      Simulate the post-step readonly verification using ONLY the
      upstream artifacts (no network).  Each simulated verification is
      labelled verification_is_simulated=True with
      source=artifact_only and real_readonly_after_execution_not_performed=True.

  stage_5_audit_artifact_generation
      Generate the 11 audit slots with DRY_RUN_NOT_SENT sanitized
      responses.  response_from_exchange=False / endpoint_called=False
      / Discord + Notion sanitized-only.

  stage_6_failure_path_simulation
      Simulate every failure path in the AB design.  No auto retry,
      no auto cleanup, no auto emergency close.  Each path is
      labelled FAIL_CLOSED or MANUAL_REVIEW_REQUIRED.

  stage_7_final_dry_run_verdict
      Resolve final status:
          TINY_LIFECYCLE_RUNNER_DRY_RUN_READY                    (default)
          TINY_LIFECYCLE_RUNNER_DRY_RUN_READY_BUT_EXECUTION_DISABLED
              (--allow-dry-run-runner-approval)
          REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED
              (--allow-real-runner-execution)
          FAIL_CLOSED                                            (hard-fail)
      Always emits real_execution_allowed=False,
      real_runner_implemented=False, g20_lifted=False.

Modes:
  dry_run_checklist                  --- default
  dry_run_runner_approval_dry_run    --- with --allow-dry-run-runner-approval
  real_runner_execution_guard        --- with --allow-real-runner-execution
  fail_closed                        --- upstream / consistency validation failed

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
  * invoke /v5/order/create or /v5/position/trading-stop
  * lift TASK-014L sender G20 (protected_entry_policy_missing)
  * touch ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT
  * mutate leverage / transfer / withdraw / deposit
  * expose any real-execute / send-order / place-order flag
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


# ---------------------------------------------------------------------------
# Stage identifiers
# ---------------------------------------------------------------------------

STAGE_0_ARTIFACT_PREFLIGHT                = "stage_0_artifact_preflight"
STAGE_1_DRY_RUN_SCOPE                     = "stage_1_dry_run_scope"
STAGE_2_STATE_MACHINE_TRACE               = "stage_2_state_machine_trace"
STAGE_3_DRY_RUN_PAYLOAD_MATERIALIZATION   = "stage_3_dry_run_payload_materialization"
STAGE_4_READONLY_VERIFICATION_SIMULATION  = "stage_4_readonly_verification_simulation"
STAGE_5_AUDIT_ARTIFACT_GENERATION         = "stage_5_audit_artifact_generation"
STAGE_6_FAILURE_PATH_SIMULATION           = "stage_6_failure_path_simulation"
STAGE_7_FINAL_DRY_RUN_VERDICT             = "stage_7_final_dry_run_verdict"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_DRY_RUN_SCOPE,
    STAGE_2_STATE_MACHINE_TRACE,
    STAGE_3_DRY_RUN_PAYLOAD_MATERIALIZATION,
    STAGE_4_READONLY_VERIFICATION_SIMULATION,
    STAGE_5_AUDIT_ARTIFACT_GENERATION,
    STAGE_6_FAILURE_PATH_SIMULATION,
    STAGE_7_FINAL_DRY_RUN_VERDICT,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_DRY_RUN_READY                = "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY"
STATUS_DRY_RUN_READY_EXEC_DISABLED  = (
    "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_RUNNER_NOT_IMPL         = "REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                  = "FAIL_CLOSED"

MODE_DRY_RUN_CHECKLIST                 = "dry_run_checklist"
MODE_DRY_RUN_RUNNER_APPROVAL_DRY_RUN   = "dry_run_runner_approval_dry_run"
MODE_REAL_RUNNER_EXECUTION_GUARD       = "real_runner_execution_guard"
MODE_FAIL_CLOSED                       = "fail_closed"


# ---------------------------------------------------------------------------
# Acceptable upstream-status whitelist
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


# ---------------------------------------------------------------------------
# Approval token patterns (documentation only --- never validated here)
# ---------------------------------------------------------------------------

ENTRY_TOKEN_PATTERN       = "CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SYMBOL"
STOP_ATTACH_TOKEN_PATTERN = "CONFIRM_DEMO_TINY_STOP_ATTACH_YYYYMMDD_SYMBOL"
CLEANUP_TOKEN_PATTERN     = "CONFIRM_DEMO_TINY_CLEANUP_YYYYMMDD_SYMBOL"


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
# Runner state machine (18 states, mirrored from AB --- no execution)
# ---------------------------------------------------------------------------

RUNNER_STATES: tuple[str, ...] = (
    "INIT",
    "PRE_READONLY_SNAPSHOT_REQUIRED",
    "ENTRY_TOKEN_REQUIRED",
    "ENTRY_READY",
    "ENTRY_SUBMITTED",
    "POST_ENTRY_READONLY_REQUIRED",
    "STOP_TOKEN_REQUIRED",
    "STOP_READY",
    "STOP_SUBMITTED",
    "POST_STOP_READONLY_REQUIRED",
    "CLEANUP_TOKEN_REQUIRED",
    "CLEANUP_READY",
    "CLEANUP_SUBMITTED",
    "POST_CLEANUP_READONLY_REQUIRED",
    "FINAL_AUDIT_REQUIRED",
    "COMPLETE",
    "FAIL_CLOSED",
    "MANUAL_REVIEW_REQUIRED",
)


# ---------------------------------------------------------------------------
# Fixed 8-step dry-run trace skeleton
# ---------------------------------------------------------------------------

DRY_RUN_STEPS: tuple[str, ...] = (
    "pre_readonly_snapshot",
    "dry_run_tiny_entry",
    "post_entry_readonly_simulated",
    "dry_run_stop_attach",
    "post_stop_attach_readonly_simulated",
    "dry_run_cleanup",
    "post_cleanup_readonly_simulated",
    "final_audit",
)

# Step -> (state_before, action, state_after, artifact_slot)
_STEP_DEFS: tuple[tuple[str, str, str, str, str], ...] = (
    ("pre_readonly_snapshot",
     "INIT", "snapshot_open_positions_via_readonly_dry_run",
     "PRE_READONLY_SNAPSHOT_REQUIRED", "pre_snapshot"),
    ("dry_run_tiny_entry",
     "ENTRY_READY", "materialise_entry_request_envelope_dry_run",
     "ENTRY_SUBMITTED", "entry_request_envelope"),
    ("post_entry_readonly_simulated",
     "ENTRY_SUBMITTED", "simulate_post_entry_readonly_from_artifacts",
     "POST_ENTRY_READONLY_REQUIRED", "post_entry_readonly"),
    ("dry_run_stop_attach",
     "STOP_READY", "materialise_stop_request_envelope_dry_run",
     "STOP_SUBMITTED", "stop_request_envelope"),
    ("post_stop_attach_readonly_simulated",
     "STOP_SUBMITTED", "simulate_post_stop_readonly_from_artifacts",
     "POST_STOP_READONLY_REQUIRED", "post_stop_readonly"),
    ("dry_run_cleanup",
     "CLEANUP_READY", "materialise_cleanup_request_envelope_dry_run",
     "CLEANUP_SUBMITTED", "cleanup_request_envelope"),
    ("post_cleanup_readonly_simulated",
     "CLEANUP_SUBMITTED", "simulate_post_cleanup_readonly_from_artifacts",
     "POST_CLEANUP_READONLY_REQUIRED", "post_cleanup_readonly"),
    ("final_audit",
     "FINAL_AUDIT_REQUIRED", "emit_final_dry_run_audit_artifact",
     "COMPLETE", "final_audit"),
)


# ---------------------------------------------------------------------------
# Required per-step audit artifacts (11 slots --- mirrored from AB)
# ---------------------------------------------------------------------------

REQUIRED_AUDIT_ARTIFACTS: tuple[str, ...] = (
    "pre_snapshot",
    "entry_request_envelope",
    "entry_response_sanitized",
    "post_entry_readonly",
    "stop_request_envelope",
    "stop_response_sanitized",
    "post_stop_readonly",
    "cleanup_request_envelope",
    "cleanup_response_sanitized",
    "post_cleanup_readonly",
    "final_audit",
)

FORBIDDEN_LOG_FIELDS: tuple[str, ...] = (
    "api_key_value", "api_secret_value", "signature_value",
    "auth_header_value", "sign_header_value", "bearer_token_value",
)


# ---------------------------------------------------------------------------
# Gate constants (73 total)
# (22 general + 7 dry-run scope + 9 trace + 9 payload + 5 readonly sim
#  + 6 audit + 10 failure sim + 5 execution guard = 73)
# ---------------------------------------------------------------------------

# General gates (22)
GATE_READONLY_SMOKE_MISSING                     = "readonly_smoke_missing"
GATE_RECONCILIATION_MISSING                     = "reconciliation_missing"
GATE_PROTECTION_MISSING                         = "protection_missing"
GATE_CONTRACT_MISSING                           = "contract_missing"
GATE_NOOP_PLAN_MISSING                          = "noop_plan_missing"
GATE_LIFECYCLE_MOCK_MISSING                     = "lifecycle_mock_missing"
GATE_REAL_PERMISSION_GATE_MISSING               = "real_permission_gate_missing"
GATE_TINY_ENTRY_PERMISSION_GATE_MISSING         = "tiny_entry_permission_gate_missing"
GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING   = "tiny_stop_attach_permission_gate_missing"
GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING       = "tiny_cleanup_permission_gate_missing"
GATE_LIFECYCLE_SUMMARY_MISSING                  = "lifecycle_summary_missing"
GATE_RUNNER_DESIGN_MISSING                      = "runner_design_missing"
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO             = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                      = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG                  = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY  = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_COLLIDES_EXISTING          = "selected_symbol_collides_with_existing_position"
GATE_SELECTED_SYMBOL_MISSING                    = "selected_symbol_missing"
GATE_RUNNER_DESIGN_STATUS_UNACCEPTABLE          = "runner_design_status_unacceptable"
GATE_G20_POLICY_STILL_IN_PLACE                  = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                           = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                         = "no_secret_values_emitted_in_this_task"

# Dry-run scope gates (7)
GATE_DRY_RUN_RUNNER_TRUE                        = "dry_run_runner_true"
GATE_REAL_RUNNER_NOT_IMPLEMENTED                = "real_runner_not_implemented_in_this_task"
GATE_REAL_EXECUTION_NOT_ALLOWED                 = "real_execution_not_allowed_in_this_task"
GATE_NO_ENDPOINT_INVOKED                        = "no_endpoint_invoked_in_this_task"
GATE_NO_POSITION_MODIFIED_SCOPE                 = "no_position_modified_scope"
GATE_NO_SECRETS_LOADED                          = "no_secrets_loaded_in_this_task"
GATE_NO_G20_LIFT                                = "no_g20_policy_lift_in_this_task"

# State machine trace gates (9)
GATE_EIGHT_STEP_TRACE_COMPLETE                  = "eight_step_trace_complete"
GATE_REQUIRED_STATES_OBSERVED                   = "required_runner_states_observed"
GATE_NO_AUTO_ADVANCE_TRACE                      = "no_auto_advance_between_real_steps"
GATE_NO_PARALLEL_EXECUTION_TRACE                = "no_parallel_execution_of_real_steps"
GATE_NO_SKIP_STEP_TRACE                         = "no_skip_step_in_dry_run_trace"
GATE_NO_RETRY_LOOP_TRACE                        = "no_retry_loop_in_dry_run_trace"
GATE_TRACE_STEP_ENDPOINT_NOT_CALLED             = "every_trace_step_endpoint_not_called"
GATE_TRACE_STEP_POSITION_NOT_MODIFIED           = "every_trace_step_position_not_modified"
GATE_TRACE_STEP_TOKEN_NOT_VALIDATED             = "every_trace_step_token_not_validated"

# Payload materialization gates (9)
GATE_ENTRY_ENVELOPE_PREVIEW_ONLY                = "entry_envelope_preview_only_true"
GATE_STOP_ENVELOPE_PREVIEW_ONLY                 = "stop_envelope_preview_only_true"
GATE_CLEANUP_ENVELOPE_PREVIEW_ONLY              = "cleanup_envelope_preview_only_true"
GATE_ENTRY_ENVELOPE_SEND_NOT_ALLOWED            = "entry_envelope_send_not_allowed"
GATE_STOP_ENVELOPE_SEND_NOT_ALLOWED             = "stop_envelope_send_not_allowed"
GATE_CLEANUP_ENVELOPE_SEND_NOT_ALLOWED          = "cleanup_envelope_send_not_allowed"
GATE_NO_SIGNATURE                               = "no_signature_in_dry_run_envelope"
GATE_NO_PRIVATE_HEADERS                         = "no_private_headers_in_dry_run_envelope"
GATE_NO_SENDER_ADAPTER                          = "no_sender_adapter_invoked"

# Readonly simulation gates (5)
GATE_POST_ENTRY_VERIFICATION_SIMULATED          = "post_entry_verification_simulated"
GATE_POST_STOP_VERIFICATION_SIMULATED           = "post_stop_verification_simulated"
GATE_POST_CLEANUP_VERIFICATION_SIMULATED        = "post_cleanup_verification_simulated"
GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED = "real_readonly_after_execution_not_performed"
GATE_VERIFICATION_SOURCE_ARTIFACT_ONLY          = "verification_source_artifact_only"

# Audit gates (6)
GATE_ELEVEN_AUDIT_SLOTS_PRESENT                 = "eleven_audit_slots_present"
GATE_RESPONSES_SANITIZED                        = "audit_responses_sanitized"
GATE_RESPONSE_FROM_EXCHANGE_FALSE               = "response_from_exchange_false"
GATE_NO_SECRETS_IN_AUDIT                        = "no_secrets_in_audit"
GATE_DISCORD_SANITIZED_ONLY                     = "discord_notifications_sanitized_only"
GATE_NOTION_SANITIZED_ONLY                      = "notion_sync_sanitized_only"

# Failure path simulation gates (10)
GATE_ENTRY_FAILURE_FAIL_CLOSED                  = "entry_rejected_fail_closed"
GATE_STOP_FAILURE_FAIL_CLOSED                   = "stop_attach_rejected_fail_closed"
GATE_CLEANUP_FAILURE_FAIL_CLOSED                = "cleanup_rejected_fail_closed"
GATE_READONLY_UNAVAILABLE_FAIL_CLOSED           = "readonly_unavailable_between_steps_fail_closed"
GATE_PARTIAL_FILL_FAIL_CLOSED                   = "entry_or_cleanup_partial_fill_fail_closed"
GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW       = "existing_stop_mismatch_manual_review"
GATE_UNEXPECTED_POSITION_MANUAL_REVIEW          = "unexpected_position_appears_manual_review"
GATE_NO_AUTO_RETRY                              = "no_auto_retry_after_failure"
GATE_NO_AUTO_CLEANUP                            = "no_auto_cleanup_after_failure"
GATE_NO_AUTO_EMERGENCY_CLOSE                    = "no_auto_emergency_close_after_failure"

# Execution guard gates (5)
GATE_REAL_RUNNER_EXECUTION_NOT_IMPL             = "real_runner_execution_not_implemented"
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
    GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING,
    GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
    GATE_LIFECYCLE_SUMMARY_MISSING,
    GATE_RUNNER_DESIGN_MISSING,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_RUNNER_DESIGN_STATUS_UNACCEPTABLE,
    GATE_ENTRY_ENVELOPE_PREVIEW_ONLY,
    GATE_STOP_ENVELOPE_PREVIEW_ONLY,
    GATE_CLEANUP_ENVELOPE_PREVIEW_ONLY,
    GATE_ENTRY_ENVELOPE_SEND_NOT_ALLOWED,
    GATE_STOP_ENVELOPE_SEND_NOT_ALLOWED,
    GATE_CLEANUP_ENVELOPE_SEND_NOT_ALLOWED,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyLifecycleRunnerDryRunResult:
    """Read-only outcome of one tiny-lifecycle dry-run pass."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    dry_run_scope:                dict[str, Any] = field(default_factory=dict)
    state_machine_trace:          list[dict[str, Any]] = field(default_factory=list)
    dry_run_request_envelopes:    dict[str, Any] = field(default_factory=dict)
    readonly_verification_simulation: dict[str, Any] = field(default_factory=dict)
    audit_artifacts:              dict[str, Any] = field(default_factory=dict)
    failure_path_simulation:      dict[str, Any] = field(default_factory=dict)
    final_dry_run_verdict:        dict[str, Any] = field(default_factory=dict)

    entry_token_pattern:          str = ENTRY_TOKEN_PATTERN
    stop_attach_token_pattern:    str = STOP_ATTACH_TOKEN_PATTERN
    cleanup_token_pattern:        str = CLEANUP_TOKEN_PATTERN

    runner_states:                list[str] = field(default_factory=lambda: list(RUNNER_STATES))
    required_audit_artifacts:     list[str] = field(
        default_factory=lambda: list(REQUIRED_AUDIT_ARTIFACTS),
    )

    # Dry-run gating flags.
    dry_run_runner_approval_allowed:  bool = False
    real_runner_execution_requested:  bool = False
    real_execution_allowed:           bool = False
    real_runner_implemented:          bool = False
    dry_run_trace_complete:           bool = False
    current_task_real_execution_allowed: bool = False

    # Safety invariants (string-only references / always documented).
    order_create_path_ref:        str  = ORDER_CREATE_PATH_REF
    trading_stop_path_ref:        str  = TRADING_STOP_PATH_REF
    base_url_ref:                 str  = BASE_URL_DEMO_REF

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

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = (
        "TASK-014AD_tiny_lifecycle_real_execution_guarded_runner_design_review"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                       self.timestamp_utc,
            "timestamp_utc":                   self.timestamp_utc,
            "mode":                            self.mode,
            "selected_symbol":                 self.selected_symbol,
            "existing_position_symbols":       list(self.existing_position_symbols),
            "stages":                          {k: dict(v) for k, v in self.stages.items()},
            "stage_order":                     list(self.stage_order),
            "dry_run_scope":                   dict(self.dry_run_scope),
            "state_machine_trace":             [dict(s) for s in self.state_machine_trace],
            "dry_run_request_envelopes":       {k: (dict(v) if isinstance(v, dict) else v) for k, v in self.dry_run_request_envelopes.items()},
            "readonly_verification_simulation": dict(self.readonly_verification_simulation),
            "audit_artifacts":                 {k: dict(v) for k, v in self.audit_artifacts.items()},
            "failure_path_simulation":         dict(self.failure_path_simulation),
            "final_dry_run_verdict":           dict(self.final_dry_run_verdict),
            "entry_token_pattern":             self.entry_token_pattern,
            "stop_attach_token_pattern":       self.stop_attach_token_pattern,
            "cleanup_token_pattern":           self.cleanup_token_pattern,
            "runner_states":                   list(self.runner_states),
            "required_audit_artifacts":        list(self.required_audit_artifacts),
            "dry_run_runner_approval_allowed": self.dry_run_runner_approval_allowed,
            "real_runner_execution_requested": self.real_runner_execution_requested,
            "real_execution_allowed":          self.real_execution_allowed,
            "real_runner_implemented":         self.real_runner_implemented,
            "dry_run_trace_complete":          self.dry_run_trace_complete,
            "current_task_real_execution_allowed": self.current_task_real_execution_allowed,
            "order_create_path_ref":           self.order_create_path_ref,
            "trading_stop_path_ref":           self.trading_stop_path_ref,
            "base_url_ref":                    self.base_url_ref,
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


def _extract_payload_from_summary(
    summary: dict[str, Any] | None, key: str,
) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    val = summary.get(key)
    if isinstance(val, dict):
        return dict(val)
    stages = summary.get("stages")
    if isinstance(stages, dict):
        for stage_env in stages.values():
            if isinstance(stage_env, dict):
                nested = stage_env.get(key)
                if isinstance(nested, dict):
                    return dict(nested)
    return {}


# ---------------------------------------------------------------------------
# Dry-run runner
# ---------------------------------------------------------------------------

class DemoTinyLifecycleRunnerDryRun:
    """
    Pure-computation dry-run runner.  Consolidates the 12 upstream
    artifacts (10 baseline + 014AA lifecycle summary + 014AB runner
    design) and emits a dry-run trace with three dry-run request
    envelopes, an 11-slot audit, a simulated readonly verification, and
    a final readiness verdict.

    Holds no network client, reads no environment variables, opens no
    socket, performs no HMAC signing, and NEVER invokes the
    order-create or trading-stop endpoints.

    --allow-dry-run-runner-approval --> status promoted to
        TINY_LIFECYCLE_RUNNER_DRY_RUN_READY_BUT_EXECUTION_DISABLED.

    --allow-real-runner-execution --> status fixed to
        REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED  (no socket opened).
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
        tiny_stop_attach_permission_gate: dict[str, Any] | None,
        tiny_cleanup_permission_gate:     dict[str, Any] | None,
        lifecycle_summary:                dict[str, Any] | None,
        runner_design:                    dict[str, Any] | None,
        symbol:                           str  = DEFAULT_SELECTED_SYMBOL,
        allow_dry_run_runner_approval:    bool = False,
        allow_real_runner_execution:      bool = False,
        _now:                             datetime | None = None,
    ) -> TinyLifecycleRunnerDryRunResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_runner_execution:
            mode = MODE_REAL_RUNNER_EXECUTION_GUARD
        elif allow_dry_run_runner_approval:
            mode = MODE_DRY_RUN_RUNNER_APPROVAL_DRY_RUN
        else:
            mode = MODE_DRY_RUN_CHECKLIST

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
            isinstance(tiny_stop_attach_permission_gate, dict)
            and bool(tiny_stop_attach_permission_gate)
        )
        cleanup_perm_present = (
            isinstance(tiny_cleanup_permission_gate, dict)
            and bool(tiny_cleanup_permission_gate)
        )
        summary_present      = isinstance(lifecycle_summary, dict) and bool(lifecycle_summary)
        runner_design_present = isinstance(runner_design, dict) and bool(runner_design)

        endpoint_family = _safe_str((readonly_smoke or {}).get("endpoint_family", ""))
        account_mode    = _safe_str((readonly_smoke or {}).get("account_mode", ""))
        proof_strength  = _safe_str((readonly_smoke or {}).get("proof_strength", ""))
        position_details_source = _safe_str(
            (reconciliation or {}).get(
                "position_details_source",
                (reconciliation or {}).get("mode", ""),
            )
        )
        lifecycle_status      = _safe_str((lifecycle_mock or {}).get("status", ""))
        summary_status        = _safe_str((lifecycle_summary or {}).get("status", ""))
        runner_design_status  = _safe_str((runner_design or {}).get("status", ""))

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
            blocked.append(GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING)
        if not cleanup_perm_present:
            blocked.append(GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING)
        if not summary_present:
            blocked.append(GATE_LIFECYCLE_SUMMARY_MISSING)
        if not runner_design_present:
            blocked.append(GATE_RUNNER_DESIGN_MISSING)

        if readonly_present and endpoint_family and endpoint_family != EXPECTED_ENDPOINT_FAMILY:
            blocked.append(GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO)
        if readonly_present and account_mode and account_mode != EXPECTED_ACCOUNT_MODE:
            blocked.append(GATE_ACCOUNT_MODE_NOT_DEMO)
        if readonly_present and proof_strength and proof_strength != EXPECTED_PROOF_STRENGTH:
            blocked.append(GATE_PROOF_STRENGTH_NOT_STRONG)
        if recon_present and position_details_source and position_details_source != EXPECTED_POSITION_DETAILS_SOURCE:
            blocked.append(GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY)

        if runner_design_present and runner_design_status and (
            runner_design_status not in ACCEPTABLE_RUNNER_DESIGN_STATUSES
        ):
            blocked.append(GATE_RUNNER_DESIGN_STATUS_UNACCEPTABLE)

        if not sym:
            blocked.append(GATE_SELECTED_SYMBOL_MISSING)
        elif sym in existing_symbols:
            blocked.append(GATE_SELECTED_SYMBOL_COLLIDES_EXISTING)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 12 upstream artifacts + runtime proof envelope.",
            "readonly_smoke_present":                   readonly_present,
            "reconciliation_present":                   recon_present,
            "protection_present":                       protection_present,
            "contract_present":                         contract_present,
            "noop_plan_present":                        noop_present,
            "lifecycle_mock_present":                   lifecycle_present,
            "real_permission_gate_present":             real_perm_present,
            "tiny_entry_permission_gate_present":       entry_perm_present,
            "tiny_stop_attach_permission_gate_present": stop_perm_present,
            "tiny_cleanup_permission_gate_present":     cleanup_perm_present,
            "lifecycle_summary_present":                summary_present,
            "runner_design_present":                    runner_design_present,
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
            "runner_design_status_acceptable":          sorted(
                ACCEPTABLE_RUNNER_DESIGN_STATUSES
            ),
            "selected_symbol":                          sym,
            "current_task_real_execution_allowed":      False,
        }

        # ===============================================================
        # stage_1_dry_run_scope
        # ===============================================================
        dry_run_scope: dict[str, Any] = {
            "dry_run_runner":                       True,
            "real_runner_implemented":              False,
            "real_execution_allowed":               False,
            "order_endpoint_called":                False,
            "stop_endpoint_called":                 False,
            "no_endpoint_invoked_in_this_task":     True,
            "no_position_modified":                 True,
            "no_secrets_loaded":                    True,
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "next_required_task": (
                "TASK-014AD_tiny_lifecycle_real_execution_guarded_runner_design_review"
            ),
            "scope_summary": (
                "TASK-014AC only emits a dry-run lifecycle trace.  It "
                "does not send any order, does not call any endpoint, "
                "does not load any secret, and does not touch any "
                "existing position."
            ),
        }
        stages[STAGE_1_DRY_RUN_SCOPE] = {
            "stage":   STAGE_1_DRY_RUN_SCOPE,
            "summary": "Assert dry-run-only scope (no runner implemented, no endpoint invoked).",
            "dry_run_scope":                        dry_run_scope,
        }
        blocked.append(GATE_DRY_RUN_RUNNER_TRUE)
        blocked.append(GATE_REAL_RUNNER_NOT_IMPLEMENTED)
        blocked.append(GATE_REAL_EXECUTION_NOT_ALLOWED)
        blocked.append(GATE_NO_ENDPOINT_INVOKED)
        blocked.append(GATE_NO_POSITION_MODIFIED_SCOPE)
        blocked.append(GATE_NO_SECRETS_LOADED)
        blocked.append(GATE_NO_G20_LIFT)

        # ===============================================================
        # stage_2_state_machine_trace
        # ===============================================================
        trace: list[dict[str, Any]] = []
        for idx, (step_name, state_before, action, state_after, slot) in enumerate(_STEP_DEFS):
            trace.append({
                "step_index":          idx,
                "step_name":           step_name,
                "state_before":        state_before,
                "action":              action,
                "state_after":         state_after,
                "artifact_slot":       slot,
                "endpoint_called":     False,
                "position_modified":   False,
                "auto_advanced":       False,
                "token_validated":     False,
                "parallel":            False,
                "skipped":             False,
                "retry":               False,
            })

        state_machine_trace_block: dict[str, Any] = {
            "runner_states":                        list(RUNNER_STATES),
            "dry_run_steps":                        list(DRY_RUN_STEPS),
            "trace":                                [dict(s) for s in trace],
            "eight_step_trace_complete":            len(trace) == 8,
            "required_states_observed":             True,
            "no_auto_advance":                      True,
            "no_parallel_execution":                True,
            "no_skip_step":                         True,
            "no_retry_loop":                        True,
            "every_step_endpoint_not_called":       all(
                s["endpoint_called"] is False for s in trace
            ),
            "every_step_position_not_modified":     all(
                s["position_modified"] is False for s in trace
            ),
            "every_step_token_not_validated":       all(
                s["token_validated"] is False for s in trace
            ),
        }
        stages[STAGE_2_STATE_MACHINE_TRACE] = {
            "stage":   STAGE_2_STATE_MACHINE_TRACE,
            "summary": "Generate the 8-step dry-run trace + safety invariants per step.",
            "state_machine_trace":                  state_machine_trace_block,
        }
        blocked.append(GATE_EIGHT_STEP_TRACE_COMPLETE)
        blocked.append(GATE_REQUIRED_STATES_OBSERVED)
        blocked.append(GATE_NO_AUTO_ADVANCE_TRACE)
        blocked.append(GATE_NO_PARALLEL_EXECUTION_TRACE)
        blocked.append(GATE_NO_SKIP_STEP_TRACE)
        blocked.append(GATE_NO_RETRY_LOOP_TRACE)
        blocked.append(GATE_TRACE_STEP_ENDPOINT_NOT_CALLED)
        blocked.append(GATE_TRACE_STEP_POSITION_NOT_MODIFIED)
        blocked.append(GATE_TRACE_STEP_TOKEN_NOT_VALIDATED)

        # ===============================================================
        # stage_3_dry_run_payload_materialization
        # ===============================================================
        entry_preview = self._payload_from_gate(
            tiny_entry_permission_gate, "entry_payload_preview",
        )
        if not entry_preview:
            entry_preview = _extract_payload_from_summary(
                lifecycle_summary, "entry_payload_preview",
            )
        stop_preview = self._payload_from_gate(
            tiny_stop_attach_permission_gate, "stop_payload_preview",
        )
        if not stop_preview:
            stop_preview = _extract_payload_from_summary(
                lifecycle_summary, "stop_payload_preview",
            )
        cleanup_preview = self._payload_from_gate(
            tiny_cleanup_permission_gate, "cleanup_payload_preview",
        )
        if not cleanup_preview:
            cleanup_preview = _extract_payload_from_summary(
                lifecycle_summary, "cleanup_payload_preview",
            )

        entry_envelope   = self._make_envelope("entry",   entry_preview)
        stop_envelope    = self._make_envelope("stop",    stop_preview)
        cleanup_envelope = self._make_envelope("cleanup", cleanup_preview)

        # Only enforce envelope contract failures when the upstream
        # gate / summary was actually present; otherwise the missing
        # upstream gate covers the case.
        if entry_perm_present or summary_present:
            if (not entry_envelope["preview_only"]) or (
                isinstance(entry_preview, dict)
                and entry_preview.get("preview_only") is False
            ):
                blocked.append(GATE_ENTRY_ENVELOPE_PREVIEW_ONLY)
            if entry_envelope["send_allowed"]:
                blocked.append(GATE_ENTRY_ENVELOPE_SEND_NOT_ALLOWED)
        if stop_perm_present or summary_present:
            if (not stop_envelope["preview_only"]) or (
                isinstance(stop_preview, dict)
                and stop_preview.get("preview_only") is False
            ):
                blocked.append(GATE_STOP_ENVELOPE_PREVIEW_ONLY)
            if stop_envelope["send_allowed"]:
                blocked.append(GATE_STOP_ENVELOPE_SEND_NOT_ALLOWED)
        if cleanup_perm_present or summary_present:
            if (not cleanup_envelope["preview_only"]) or (
                isinstance(cleanup_preview, dict)
                and cleanup_preview.get("preview_only") is False
            ):
                blocked.append(GATE_CLEANUP_ENVELOPE_PREVIEW_ONLY)
            if cleanup_envelope["send_allowed"]:
                blocked.append(GATE_CLEANUP_ENVELOPE_SEND_NOT_ALLOWED)

        dry_run_envelopes: dict[str, Any] = {
            "entry_request_envelope":   entry_envelope,
            "stop_request_envelope":    stop_envelope,
            "cleanup_request_envelope": cleanup_envelope,
            "no_signature":             True,
            "no_private_headers":       True,
            "no_sender_adapter":        True,
        }
        stages[STAGE_3_DRY_RUN_PAYLOAD_MATERIALIZATION] = {
            "stage":   STAGE_3_DRY_RUN_PAYLOAD_MATERIALIZATION,
            "summary": "Materialise 3 dry-run request envelopes (no signature, no adapter).",
            "dry_run_request_envelopes":            dry_run_envelopes,
        }
        blocked.append(GATE_NO_SIGNATURE)
        blocked.append(GATE_NO_PRIVATE_HEADERS)
        blocked.append(GATE_NO_SENDER_ADAPTER)

        # ===============================================================
        # stage_4_readonly_verification_simulation
        # ===============================================================
        expected_qty = _safe_float(entry_preview.get("qty", 0.0))
        if expected_qty <= 0.0:
            expected_qty = _safe_float(cleanup_preview.get("qty", 0.0))
        expected_stop_loss = _safe_float(stop_preview.get("stopLoss", 0.0))

        readonly_verification_simulation: dict[str, Any] = {
            "verification_is_simulated":                  True,
            "real_readonly_after_execution_not_performed": True,
            "post_entry_readonly_simulated": {
                "expected_symbol":                  sym,
                "expected_qty":                     expected_qty,
                "simulated_position_open":          True,
                "source":                           "artifact_only",
            },
            "post_stop_attach_readonly_simulated": {
                "expected_stop_loss":               expected_stop_loss,
                "simulated_stop_attached":          True,
                "source":                           "artifact_only",
            },
            "post_cleanup_readonly_simulated": {
                "expected_position_absent_or_zero": True,
                "simulated_cleanup_complete":       True,
                "source":                           "artifact_only",
            },
        }
        stages[STAGE_4_READONLY_VERIFICATION_SIMULATION] = {
            "stage":   STAGE_4_READONLY_VERIFICATION_SIMULATION,
            "summary": "Simulate post-step readonly verification from artifacts only (no network).",
            "readonly_verification_simulation":     readonly_verification_simulation,
        }
        blocked.append(GATE_POST_ENTRY_VERIFICATION_SIMULATED)
        blocked.append(GATE_POST_STOP_VERIFICATION_SIMULATED)
        blocked.append(GATE_POST_CLEANUP_VERIFICATION_SIMULATED)
        blocked.append(GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED)
        blocked.append(GATE_VERIFICATION_SOURCE_ARTIFACT_ONLY)

        # ===============================================================
        # stage_5_audit_artifact_generation
        # ===============================================================
        audit_artifacts: dict[str, Any] = {}
        for slot in REQUIRED_AUDIT_ARTIFACTS:
            audit_artifacts[slot] = self._make_audit_slot(slot, sym)

        audit_block: dict[str, Any] = {
            "required_audit_artifacts":             list(REQUIRED_AUDIT_ARTIFACTS),
            "audit_artifacts":                      {k: dict(v) for k, v in audit_artifacts.items()},
            "eleven_audit_slots_present":           len(audit_artifacts) == 11,
            "responses_sanitized":                  True,
            "response_from_exchange":               False,
            "forbidden_log_fields":                 list(FORBIDDEN_LOG_FIELDS),
            "no_secrets_in_audit":                  True,
            "discord_sanitized_summary_only":       True,
            "notion_sanitized_summary_only":        True,
        }
        stages[STAGE_5_AUDIT_ARTIFACT_GENERATION] = {
            "stage":   STAGE_5_AUDIT_ARTIFACT_GENERATION,
            "summary": "Generate 11 audit slots with DRY_RUN_NOT_SENT sanitized responses.",
            "audit_artifacts":                      audit_block,
        }
        blocked.append(GATE_ELEVEN_AUDIT_SLOTS_PRESENT)
        blocked.append(GATE_RESPONSES_SANITIZED)
        blocked.append(GATE_RESPONSE_FROM_EXCHANGE_FALSE)
        blocked.append(GATE_NO_SECRETS_IN_AUDIT)
        blocked.append(GATE_DISCORD_SANITIZED_ONLY)
        blocked.append(GATE_NOTION_SANITIZED_ONLY)

        # ===============================================================
        # stage_6_failure_path_simulation
        # ===============================================================
        failure_path_simulation: dict[str, Any] = {
            "entry_rejected": {
                "resolution":                "FAIL_CLOSED",
                "no_auto_retry":             True,
                "no_auto_cleanup":           True,
                "no_auto_emergency_close":   True,
                "no_next_step":              True,
                "manual_review_required":    False,
            },
            "stop_attach_rejected": {
                "resolution":                "FAIL_CLOSED",
                "no_auto_retry":             True,
                "no_auto_cleanup":           True,
                "no_auto_emergency_close":   True,
                "no_next_step":              True,
                "manual_review_required":    False,
            },
            "cleanup_rejected": {
                "resolution":                "FAIL_CLOSED",
                "no_auto_retry":             True,
                "no_auto_cleanup":           True,
                "no_auto_emergency_close":   True,
                "no_next_step":              True,
                "manual_review_required":    False,
            },
            "readonly_unavailable_between_steps": {
                "resolution":                "FAIL_CLOSED",
                "no_auto_retry":             True,
                "no_auto_cleanup":           True,
                "no_auto_emergency_close":   True,
                "no_next_step":              True,
                "manual_review_required":    False,
            },
            "entry_or_cleanup_partial_fill": {
                "resolution":                "FAIL_CLOSED",
                "no_auto_retry":             True,
                "no_auto_cleanup":           True,
                "no_auto_emergency_close":   True,
                "no_next_step":              True,
                "manual_review_required":    False,
            },
            "existing_stop_mismatch": {
                "resolution":                "MANUAL_REVIEW_REQUIRED",
                "no_auto_retry":             True,
                "no_auto_cleanup":           True,
                "no_auto_emergency_close":   True,
                "no_next_step":              True,
                "manual_review_required":    True,
            },
            "unexpected_position_appears": {
                "resolution":                "MANUAL_REVIEW_REQUIRED",
                "no_auto_retry":             True,
                "no_auto_cleanup":           True,
                "no_auto_emergency_close":   True,
                "no_next_step":              True,
                "manual_review_required":    True,
            },
        }
        stages[STAGE_6_FAILURE_PATH_SIMULATION] = {
            "stage":   STAGE_6_FAILURE_PATH_SIMULATION,
            "summary": "Simulate every failure path with no automatic recovery.",
            "failure_path_simulation":              failure_path_simulation,
        }
        blocked.append(GATE_ENTRY_FAILURE_FAIL_CLOSED)
        blocked.append(GATE_STOP_FAILURE_FAIL_CLOSED)
        blocked.append(GATE_CLEANUP_FAILURE_FAIL_CLOSED)
        blocked.append(GATE_READONLY_UNAVAILABLE_FAIL_CLOSED)
        blocked.append(GATE_PARTIAL_FILL_FAIL_CLOSED)
        blocked.append(GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW)
        blocked.append(GATE_UNEXPECTED_POSITION_MANUAL_REVIEW)
        blocked.append(GATE_NO_AUTO_RETRY)
        blocked.append(GATE_NO_AUTO_CLEANUP)
        blocked.append(GATE_NO_AUTO_EMERGENCY_CLOSE)

        # ===============================================================
        # stage_7_final_dry_run_verdict
        # ===============================================================
        blocked.append(GATE_REAL_RUNNER_EXECUTION_NOT_IMPL)
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
            dry_run_trace_complete = False
        elif allow_real_runner_execution:
            failed_stage = ""
            status_out = STATUS_REAL_RUNNER_NOT_IMPL
            mode_out   = MODE_REAL_RUNNER_EXECUTION_GUARD
            dry_run_trace_complete = True
        elif allow_dry_run_runner_approval:
            failed_stage = ""
            status_out = STATUS_DRY_RUN_READY_EXEC_DISABLED
            mode_out   = MODE_DRY_RUN_RUNNER_APPROVAL_DRY_RUN
            dry_run_trace_complete = True
        else:
            failed_stage = ""
            status_out = STATUS_DRY_RUN_READY
            mode_out   = MODE_DRY_RUN_CHECKLIST
            dry_run_trace_complete = True

        final_dry_run_verdict: dict[str, Any] = {
            "dry_run_runner_approval_allowed":      allow_dry_run_runner_approval,
            "real_runner_execution_requested":      bool(allow_real_runner_execution),
            "dry_run_trace_complete":               dry_run_trace_complete,
            "real_execution_allowed":               False,
            "real_runner_implemented":              False,
            "current_task_real_execution_allowed":  False,
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "no_real_order_endpoint":               True,
            "no_real_stop_endpoint":                True,
            "no_position_modified":                 True,
            "no_live_endpoint":                     True,
            "no_secrets_loaded":                    True,
            "no_secrets_emitted":                   True,
            "order_endpoint_called":                False,
            "stop_endpoint_called":                 False,
            "status":                               status_out,
            "mode":                                 mode_out,
            "next_required_task": (
                "TASK-014AD_tiny_lifecycle_real_execution_guarded_runner_design_review"
            ),
        }
        stages[STAGE_7_FINAL_DRY_RUN_VERDICT] = {
            "stage":   STAGE_7_FINAL_DRY_RUN_VERDICT,
            "summary": "Final dry-run verdict + permanent execution guard.",
            "final_dry_run_verdict":                final_dry_run_verdict,
        }

        return TinyLifecycleRunnerDryRunResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            dry_run_scope=dry_run_scope,
            state_machine_trace=trace,
            dry_run_request_envelopes=dry_run_envelopes,
            readonly_verification_simulation=readonly_verification_simulation,
            audit_artifacts=audit_artifacts,
            failure_path_simulation=failure_path_simulation,
            final_dry_run_verdict=final_dry_run_verdict,
            dry_run_runner_approval_allowed=allow_dry_run_runner_approval,
            real_runner_execution_requested=bool(allow_real_runner_execution),
            real_execution_allowed=False,
            real_runner_implemented=False,
            dry_run_trace_complete=dry_run_trace_complete,
            current_task_real_execution_allowed=False,
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
            blocked_gates=unique,
            failed_stage=failed_stage,
            status=status_out,
        )

    # ----------------------------------------------------------------- util
    @staticmethod
    def _payload_from_gate(
        gate: dict[str, Any] | None, key: str,
    ) -> dict[str, Any]:
        if not isinstance(gate, dict):
            return {}
        val = gate.get(key)
        if isinstance(val, dict):
            return dict(val)
        # try nested under stages
        stages = gate.get("stages")
        if isinstance(stages, dict):
            for stage_env in stages.values():
                if isinstance(stage_env, dict):
                    nested = stage_env.get(key)
                    if isinstance(nested, dict):
                        return dict(nested)
        return {}

    @staticmethod
    def _make_envelope(
        which: str, preview: dict[str, Any],
    ) -> dict[str, Any]:
        """Materialise a dry-run request envelope.

        The envelope copies fields from the upstream preview but ALWAYS
        forces preview_only=True / send_allowed=False / real_payload=False /
        endpoint_called=False, regardless of upstream content.  No
        signature header and no private auth header is ever added.
        """
        path_ref = (
            ORDER_CREATE_PATH_REF if which in ("entry", "cleanup")
            else TRADING_STOP_PATH_REF
        )
        # Copy ONLY documented preview fields; never copy auth/signature.
        safe_fields: dict[str, Any] = {}
        if isinstance(preview, dict):
            for k in (
                "category", "symbol", "side", "orderType",
                "qty", "timeInForce", "orderLinkId",
                "reduceOnly", "stopLoss", "positionIdx",
                "endpoint_path_ref",
            ):
                if k in preview:
                    safe_fields[k] = preview[k]
        envelope: dict[str, Any] = {
            "which":              which,
            "endpoint_path_ref":  safe_fields.get("endpoint_path_ref", path_ref),
            "request_preview":    safe_fields,
            "preview_only":       True,
            "endpoint_called":    False,
            "send_allowed":       False,
            "real_payload":       False,
            "signature_present":  False,
            "private_headers":    [],
            "headers_preview":    {"Content-Type": "application/json"},
        }
        return envelope

    @staticmethod
    def _make_audit_slot(slot: str, symbol: str) -> dict[str, Any]:
        return {
            "slot":                       slot,
            "symbol":                     symbol,
            "status":                     "DRY_RUN_NOT_SENT",
            "endpoint_called":            False,
            "response_from_exchange":     False,
            "sanitized":                  True,
            "discord_sanitized_only":     True,
            "notion_sanitized_only":      True,
        }

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
            GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING,
            GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
            GATE_LIFECYCLE_SUMMARY_MISSING,
            GATE_RUNNER_DESIGN_MISSING,
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_RUNNER_DESIGN_STATUS_UNACCEPTABLE,
            GATE_SELECTED_SYMBOL_MISSING,
            GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
        }
        for g in blocked:
            if g in stage_0_set:
                return STAGE_0_ARTIFACT_PREFLIGHT
        stage_3_set = {
            GATE_ENTRY_ENVELOPE_PREVIEW_ONLY,
            GATE_STOP_ENVELOPE_PREVIEW_ONLY,
            GATE_CLEANUP_ENVELOPE_PREVIEW_ONLY,
            GATE_ENTRY_ENVELOPE_SEND_NOT_ALLOWED,
            GATE_STOP_ENVELOPE_SEND_NOT_ALLOWED,
            GATE_CLEANUP_ENVELOPE_SEND_NOT_ALLOWED,
        }
        for g in blocked:
            if g in stage_3_set:
                return STAGE_3_DRY_RUN_PAYLOAD_MATERIALIZATION
        return ""


__all__ = [
    "EXISTING_POSITION_SYMBOLS",
    "DEFAULT_SELECTED_SYMBOL",
    "ORDER_CREATE_PATH_REF",
    "TRADING_STOP_PATH_REF",
    "BASE_URL_DEMO_REF",
    "ENTRY_TOKEN_PATTERN",
    "STOP_ATTACH_TOKEN_PATTERN",
    "CLEANUP_TOKEN_PATTERN",
    "ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES",
    "ACCEPTABLE_RUNNER_DESIGN_STATUSES",
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_LIFECYCLE_STATUS",
    "EXPECTED_INSTRUMENT_CATEGORY",
    "RUNNER_STATES",
    "DRY_RUN_STEPS",
    "REQUIRED_AUDIT_ARTIFACTS",
    "FORBIDDEN_LOG_FIELDS",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_DRY_RUN_SCOPE",
    "STAGE_2_STATE_MACHINE_TRACE",
    "STAGE_3_DRY_RUN_PAYLOAD_MATERIALIZATION",
    "STAGE_4_READONLY_VERIFICATION_SIMULATION",
    "STAGE_5_AUDIT_ARTIFACT_GENERATION",
    "STAGE_6_FAILURE_PATH_SIMULATION",
    "STAGE_7_FINAL_DRY_RUN_VERDICT",
    "ALL_STAGES",
    "STATUS_DRY_RUN_READY",
    "STATUS_DRY_RUN_READY_EXEC_DISABLED",
    "STATUS_REAL_RUNNER_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_DRY_RUN_CHECKLIST",
    "MODE_DRY_RUN_RUNNER_APPROVAL_DRY_RUN",
    "MODE_REAL_RUNNER_EXECUTION_GUARD",
    "MODE_FAIL_CLOSED",
    # general gates (22)
    "GATE_READONLY_SMOKE_MISSING",
    "GATE_RECONCILIATION_MISSING",
    "GATE_PROTECTION_MISSING",
    "GATE_CONTRACT_MISSING",
    "GATE_NOOP_PLAN_MISSING",
    "GATE_LIFECYCLE_MOCK_MISSING",
    "GATE_REAL_PERMISSION_GATE_MISSING",
    "GATE_TINY_ENTRY_PERMISSION_GATE_MISSING",
    "GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING",
    "GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING",
    "GATE_LIFECYCLE_SUMMARY_MISSING",
    "GATE_RUNNER_DESIGN_MISSING",
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_COLLIDES_EXISTING",
    "GATE_SELECTED_SYMBOL_MISSING",
    "GATE_RUNNER_DESIGN_STATUS_UNACCEPTABLE",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # dry-run scope (7)
    "GATE_DRY_RUN_RUNNER_TRUE",
    "GATE_REAL_RUNNER_NOT_IMPLEMENTED",
    "GATE_REAL_EXECUTION_NOT_ALLOWED",
    "GATE_NO_ENDPOINT_INVOKED",
    "GATE_NO_POSITION_MODIFIED_SCOPE",
    "GATE_NO_SECRETS_LOADED",
    "GATE_NO_G20_LIFT",
    # trace (9)
    "GATE_EIGHT_STEP_TRACE_COMPLETE",
    "GATE_REQUIRED_STATES_OBSERVED",
    "GATE_NO_AUTO_ADVANCE_TRACE",
    "GATE_NO_PARALLEL_EXECUTION_TRACE",
    "GATE_NO_SKIP_STEP_TRACE",
    "GATE_NO_RETRY_LOOP_TRACE",
    "GATE_TRACE_STEP_ENDPOINT_NOT_CALLED",
    "GATE_TRACE_STEP_POSITION_NOT_MODIFIED",
    "GATE_TRACE_STEP_TOKEN_NOT_VALIDATED",
    # payload (9)
    "GATE_ENTRY_ENVELOPE_PREVIEW_ONLY",
    "GATE_STOP_ENVELOPE_PREVIEW_ONLY",
    "GATE_CLEANUP_ENVELOPE_PREVIEW_ONLY",
    "GATE_ENTRY_ENVELOPE_SEND_NOT_ALLOWED",
    "GATE_STOP_ENVELOPE_SEND_NOT_ALLOWED",
    "GATE_CLEANUP_ENVELOPE_SEND_NOT_ALLOWED",
    "GATE_NO_SIGNATURE",
    "GATE_NO_PRIVATE_HEADERS",
    "GATE_NO_SENDER_ADAPTER",
    # readonly sim (5)
    "GATE_POST_ENTRY_VERIFICATION_SIMULATED",
    "GATE_POST_STOP_VERIFICATION_SIMULATED",
    "GATE_POST_CLEANUP_VERIFICATION_SIMULATED",
    "GATE_REAL_READONLY_AFTER_EXECUTION_NOT_PERFORMED",
    "GATE_VERIFICATION_SOURCE_ARTIFACT_ONLY",
    # audit (6)
    "GATE_ELEVEN_AUDIT_SLOTS_PRESENT",
    "GATE_RESPONSES_SANITIZED",
    "GATE_RESPONSE_FROM_EXCHANGE_FALSE",
    "GATE_NO_SECRETS_IN_AUDIT",
    "GATE_DISCORD_SANITIZED_ONLY",
    "GATE_NOTION_SANITIZED_ONLY",
    # failure sim (10)
    "GATE_ENTRY_FAILURE_FAIL_CLOSED",
    "GATE_STOP_FAILURE_FAIL_CLOSED",
    "GATE_CLEANUP_FAILURE_FAIL_CLOSED",
    "GATE_READONLY_UNAVAILABLE_FAIL_CLOSED",
    "GATE_PARTIAL_FILL_FAIL_CLOSED",
    "GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW",
    "GATE_UNEXPECTED_POSITION_MANUAL_REVIEW",
    "GATE_NO_AUTO_RETRY",
    "GATE_NO_AUTO_CLEANUP",
    "GATE_NO_AUTO_EMERGENCY_CLOSE",
    # execution guard (5)
    "GATE_REAL_RUNNER_EXECUTION_NOT_IMPL",
    "GATE_NO_REAL_ORDER_ENDPOINT",
    "GATE_NO_REAL_STOP_ENDPOINT",
    "GATE_NO_POSITION_MODIFIED",
    "GATE_G20_NOT_LIFTED",
    # data
    "DemoTinyLifecycleRunnerDryRun",
    "TinyLifecycleRunnerDryRunResult",
]
