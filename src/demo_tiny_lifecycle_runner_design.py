"""
src/demo_tiny_lifecycle_runner_design.py
TASK-014AB: Tiny Lifecycle Real Execution Runner Design / Manual Approval.

Pure-computation / design-only module.  Consolidates the 11 upstream
artifacts (readonly / reconciliation / protection / contract / noop_plan
/ lifecycle_mock / tiny_position_real_permission_gate /
tiny_entry_permission_gate / tiny_stop_attach_permission_gate /
tiny_cleanup_permission_gate / tiny_lifecycle_real_execution_summary)
and emits a *design document* for the future real tiny-lifecycle
execution runner together with a final readiness verdict.

This module does NOT execute anything: no /v5/order/create,
no /v5/position/trading-stop, no order send, no position modification,
no close-only, no emergency close, no leverage / transfer / withdraw,
no token validation, no socket open.  It only describes how the future
runner SHOULD be built, approved, and aborted.

Stages:

  stage_0_artifact_preflight
      Validate 11 upstream artifacts + runtime proof envelope.

  stage_1_runner_design_scope
      Assert design-only / no implementation / no endpoint invocation.

  stage_2_state_machine_design
      Document the 18 required runner states + readonly-between-real-steps
      invariant + no auto-advance + no parallel + no skip + no retry.

  stage_3_manual_approval_contract
      Document the 3 distinct manual approval tokens (entry / stop /
      cleanup).  Tokens are NEVER validated in this task.  Token format
      itself is NOT considered authorization --- a future runner will
      require additional confirmation steps.

  stage_4_execution_payload_contract
      Pull the 3 payload previews (entry / stop / cleanup) from the
      lifecycle summary (014AA) and check the design constraints
      (preview_only=True / reduceOnly / qty parity / stopLoss>0 /
      stopLoss<entry_reference / no real-payload conversion).

  stage_5_abort_and_fail_closed_policy
      Document the failure-response matrix: entry / stop / cleanup
      rejected -> fail_closed; readonly unavailable -> fail_closed;
      partial fills -> fail_closed; unexpected position / existing
      stop mismatch -> manual_review; no auto retry / cleanup /
      emergency-close.

  stage_6_observability_and_audit_design
      Document the required artifacts-per-step (11 artifact slots),
      sanitized response requirement, no-secret-in-log policy, and
      Discord / Notion sanitized-summary-only constraint.

  stage_7_final_design_verdict
      Resolve final status:
          TINY_LIFECYCLE_RUNNER_DESIGN_READY                    (default)
          TINY_LIFECYCLE_RUNNER_DESIGN_READY_BUT_EXECUTION_DISABLED
              (--allow-runner-design-approval)
          REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED
              (--allow-real-runner-execution)
          FAIL_CLOSED                                           (hard-fail)
      Always emits real_execution_allowed=False,
      real_runner_implemented=False, g20_lifted=False.

Modes:
  design_checklist                   --- default
  runner_design_approval_dry_run     --- with --allow-runner-design-approval
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
  * invoke /v5/order/create or /v5/position/trading-stop
  * lift TASK-014L sender G20 (protected_entry_policy_missing)
  * touch ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT
  * mutate leverage / transfer / withdraw / deposit
  * expose --execute-real-lifecycle / --execute-real-entry /
    --execute-real-stop / --execute-real-cleanup flags
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

STAGE_0_ARTIFACT_PREFLIGHT             = "stage_0_artifact_preflight"
STAGE_1_RUNNER_DESIGN_SCOPE            = "stage_1_runner_design_scope"
STAGE_2_STATE_MACHINE_DESIGN           = "stage_2_state_machine_design"
STAGE_3_MANUAL_APPROVAL_CONTRACT       = "stage_3_manual_approval_contract"
STAGE_4_EXECUTION_PAYLOAD_CONTRACT     = "stage_4_execution_payload_contract"
STAGE_5_ABORT_AND_FAIL_CLOSED_POLICY   = "stage_5_abort_and_fail_closed_policy"
STAGE_6_OBSERVABILITY_AND_AUDIT_DESIGN = "stage_6_observability_and_audit_design"
STAGE_7_FINAL_DESIGN_VERDICT           = "stage_7_final_design_verdict"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_RUNNER_DESIGN_SCOPE,
    STAGE_2_STATE_MACHINE_DESIGN,
    STAGE_3_MANUAL_APPROVAL_CONTRACT,
    STAGE_4_EXECUTION_PAYLOAD_CONTRACT,
    STAGE_5_ABORT_AND_FAIL_CLOSED_POLICY,
    STAGE_6_OBSERVABILITY_AND_AUDIT_DESIGN,
    STAGE_7_FINAL_DESIGN_VERDICT,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_DESIGN_READY                = "TINY_LIFECYCLE_RUNNER_DESIGN_READY"
STATUS_DESIGN_READY_EXEC_DISABLED  = (
    "TINY_LIFECYCLE_RUNNER_DESIGN_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_RUNNER_NOT_IMPL        = "REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                 = "FAIL_CLOSED"

MODE_DESIGN_CHECKLIST                  = "design_checklist"
MODE_RUNNER_DESIGN_APPROVAL_DRY_RUN    = "runner_design_approval_dry_run"
MODE_REAL_RUNNER_EXECUTION_GUARD       = "real_runner_execution_guard"
MODE_FAIL_CLOSED                       = "fail_closed"


# ---------------------------------------------------------------------------
# Acceptable upstream-status whitelist for the 014AA lifecycle summary
# ---------------------------------------------------------------------------

ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES: frozenset[str] = frozenset({
    "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY",
    "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY_BUT_EXECUTION_DISABLED",
    "REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED",
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
EXPECTED_ENTRY_SIDE              = "long"
EXPECTED_CLEANUP_SIDE            = "Sell"
EXPECTED_ENTRY_ORDER_SIDE        = "Buy"


# ---------------------------------------------------------------------------
# Runner state machine (18 states, design-only --- never executed)
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

# Real-step state set: each real step must be followed by a readonly state.
REAL_SUBMIT_STATES: tuple[str, ...] = (
    "ENTRY_SUBMITTED", "STOP_SUBMITTED", "CLEANUP_SUBMITTED",
)
POST_REAL_READONLY_STATES: tuple[str, ...] = (
    "POST_ENTRY_READONLY_REQUIRED",
    "POST_STOP_READONLY_REQUIRED",
    "POST_CLEANUP_READONLY_REQUIRED",
)


# ---------------------------------------------------------------------------
# Required per-step audit artifacts (observability design --- 11 slots)
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
# Gate constants
# (21 general + 6 design scope + 6 state machine + 7 manual approval +
#  8 payload contract + 10 failure policy + 5 observability +
#  5 execution guard = 68)
# ---------------------------------------------------------------------------

# General gates (21)
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
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO             = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                      = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG                  = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY  = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_COLLIDES_EXISTING          = "selected_symbol_collides_with_existing_position"
GATE_SELECTED_SYMBOL_MISSING                    = "selected_symbol_missing"
GATE_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE      = "lifecycle_summary_status_unacceptable"
GATE_G20_POLICY_STILL_IN_PLACE                  = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                           = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                         = "no_secret_values_emitted_in_this_task"

# Design scope gates (6)
GATE_DESIGN_ONLY_TRUE                           = "runner_design_only_true"
GATE_REAL_RUNNER_NOT_IMPLEMENTED                = "real_runner_not_implemented_in_this_task"
GATE_REAL_EXECUTION_NOT_ALLOWED                 = "real_execution_not_allowed_in_this_task"
GATE_NO_ENDPOINT_INVOKED                        = "no_endpoint_invoked_in_this_task"
GATE_NO_G20_LIFT                                = "no_g20_policy_lift_in_this_task"
GATE_NEXT_TASK_IS_DRY_RUN_IMPL                  = "next_task_is_dry_run_runner_implementation_design"

# State machine gates (6)
GATE_REQUIRED_STATES_PRESENT                    = "required_runner_states_present"
GATE_READONLY_BETWEEN_REAL_STEPS_REQUIRED       = "readonly_between_real_steps_required"
GATE_NO_AUTO_ADVANCE                            = "no_auto_advance_between_real_steps"
GATE_NO_PARALLEL_EXECUTION                      = "no_parallel_execution_of_real_steps"
GATE_NO_SKIP_STEP                               = "no_skip_step_in_real_lifecycle"
GATE_NO_RETRY_LOOP_STATE_MACHINE                = "no_retry_loop_in_state_machine"

# Manual approval gates (7)
GATE_ENTRY_TOKEN_PATTERN_PRESENT                = "entry_token_pattern_present"
GATE_STOP_TOKEN_PATTERN_PRESENT                 = "stop_attach_token_pattern_present"
GATE_CLEANUP_TOKEN_PATTERN_PRESENT              = "cleanup_token_pattern_present"
GATE_TOKENS_DISTINCT                            = "approval_tokens_distinct_per_step"
GATE_TOKENS_NOT_VALIDATED_IN_THIS_TASK          = "approval_tokens_not_validated_in_this_task"
GATE_EACH_STEP_SEPARATE_MANUAL_APPROVAL         = "each_real_step_requires_separate_manual_approval"
GATE_TOKEN_FORMAT_IS_NOT_AUTHORIZATION          = "token_format_alone_is_not_authorization"

# Payload contract gates (8)
GATE_ENTRY_PAYLOAD_PREVIEW_ONLY                 = "entry_payload_preview_only_required"
GATE_STOP_PAYLOAD_PREVIEW_ONLY                  = "stop_payload_preview_only_required"
GATE_CLEANUP_PAYLOAD_PREVIEW_ONLY               = "cleanup_payload_preview_only_required"
GATE_ENTRY_QTY_EQUALS_CLEANUP_QTY               = "entry_payload_qty_equals_cleanup_payload_qty"
GATE_CLEANUP_REDUCE_ONLY_TRUE                   = "cleanup_payload_reduce_only_true"
GATE_STOP_LOSS_POSITIVE                         = "stop_payload_stop_loss_positive"
GATE_STOP_LOSS_LESS_THAN_ENTRY_REF              = "stop_payload_stop_loss_less_than_entry_reference"
GATE_NO_PREVIEW_TO_REAL_CONVERSION              = "no_preview_payload_converted_to_real_payload"

# Failure policy gates (10)
GATE_ENTRY_FAIL_CLOSED                          = "entry_rejected_fail_closed"
GATE_STOP_FAIL_CLOSED                           = "stop_attach_rejected_fail_closed"
GATE_CLEANUP_FAIL_CLOSED                        = "cleanup_rejected_fail_closed"
GATE_READONLY_UNAVAILABLE_FAIL_CLOSED           = "readonly_unavailable_between_steps_fail_closed"
GATE_PARTIAL_FILL_FAIL_CLOSED                   = "entry_or_cleanup_partial_fill_fail_closed"
GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW       = "existing_stop_mismatch_manual_review"
GATE_UNEXPECTED_POSITION_MANUAL_REVIEW          = "unexpected_position_appears_manual_review"
GATE_NO_AUTO_EMERGENCY_CLOSE                    = "no_automatic_emergency_close_on_failure"
GATE_NO_AUTO_CLEANUP                            = "no_automatic_cleanup_on_failure"
GATE_NO_RETRY_LOOP_FAILURE_POLICY               = "no_retry_loop_after_failure"

# Observability gates (5)
GATE_ARTIFACT_PER_STEP_REQUIRED                 = "artifact_per_step_required"
GATE_SANITIZED_RESPONSE_REQUIRED                = "sanitized_response_required"
GATE_NO_SECRETS_IN_LOGS                         = "no_secrets_in_logs_required"
GATE_DISCORD_SANITIZED_ONLY                     = "discord_notifications_sanitized_only"
GATE_NOTION_SANITIZED_ONLY                      = "notion_sync_sanitized_only"

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
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE,
    GATE_ENTRY_PAYLOAD_PREVIEW_ONLY,
    GATE_STOP_PAYLOAD_PREVIEW_ONLY,
    GATE_CLEANUP_PAYLOAD_PREVIEW_ONLY,
    GATE_ENTRY_QTY_EQUALS_CLEANUP_QTY,
    GATE_CLEANUP_REDUCE_ONLY_TRUE,
    GATE_STOP_LOSS_POSITIVE,
    GATE_STOP_LOSS_LESS_THAN_ENTRY_REF,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyLifecycleRunnerDesignResult:
    """Read-only outcome of one tiny-lifecycle runner-design pass."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    runner_design_scope:          dict[str, Any] = field(default_factory=dict)
    state_machine_design:         dict[str, Any] = field(default_factory=dict)
    manual_approval_contract:     dict[str, Any] = field(default_factory=dict)
    execution_payload_contract:   dict[str, Any] = field(default_factory=dict)
    abort_and_fail_closed_policy: dict[str, Any] = field(default_factory=dict)
    observability_and_audit_design: dict[str, Any] = field(default_factory=dict)
    final_design_verdict:         dict[str, Any] = field(default_factory=dict)

    entry_token_pattern:          str = ENTRY_TOKEN_PATTERN
    stop_attach_token_pattern:    str = STOP_ATTACH_TOKEN_PATTERN
    cleanup_token_pattern:        str = CLEANUP_TOKEN_PATTERN

    runner_states:                list[str] = field(default_factory=lambda: list(RUNNER_STATES))
    required_audit_artifacts:     list[str] = field(
        default_factory=lambda: list(REQUIRED_AUDIT_ARTIFACTS),
    )

    entry_payload_preview:        dict[str, Any] = field(default_factory=dict)
    stop_payload_preview:         dict[str, Any] = field(default_factory=dict)
    cleanup_payload_preview:      dict[str, Any] = field(default_factory=dict)
    expected_entry_reference_price: float = 0.0

    # Real-execution gating flags (TASK-014AB keeps all conservative).
    runner_design_approval_allowed: bool = False
    real_runner_execution_requested: bool = False
    real_execution_allowed:       bool = False
    real_runner_implemented:      bool = False
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
    secret_value_observed:        bool = False
    g20_policy_still_in_place:    bool = True
    g20_lifted:                   bool = False

    existing_positions_touched:   list[str] = field(default_factory=list)
    upstream_lifecycle_summary_status: str = ""

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = (
        "TASK-014AC_tiny_lifecycle_runner_implementation_dry_run_only"
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
            "runner_design_scope":             dict(self.runner_design_scope),
            "state_machine_design":            dict(self.state_machine_design),
            "manual_approval_contract":        dict(self.manual_approval_contract),
            "execution_payload_contract":      dict(self.execution_payload_contract),
            "abort_and_fail_closed_policy":    dict(self.abort_and_fail_closed_policy),
            "observability_and_audit_design":  dict(self.observability_and_audit_design),
            "final_design_verdict":            dict(self.final_design_verdict),
            "entry_token_pattern":             self.entry_token_pattern,
            "stop_attach_token_pattern":       self.stop_attach_token_pattern,
            "cleanup_token_pattern":           self.cleanup_token_pattern,
            "runner_states":                   list(self.runner_states),
            "required_audit_artifacts":        list(self.required_audit_artifacts),
            "entry_payload_preview":           dict(self.entry_payload_preview),
            "stop_payload_preview":            dict(self.stop_payload_preview),
            "cleanup_payload_preview":         dict(self.cleanup_payload_preview),
            "expected_entry_reference_price":  self.expected_entry_reference_price,
            "runner_design_approval_allowed":  self.runner_design_approval_allowed,
            "real_runner_execution_requested": self.real_runner_execution_requested,
            "real_execution_allowed":          self.real_execution_allowed,
            "real_runner_implemented":         self.real_runner_implemented,
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
            "secret_value_observed":           self.secret_value_observed,
            "g20_policy_still_in_place":       self.g20_policy_still_in_place,
            "g20_lifted":                      self.g20_lifted,
            "existing_positions_touched":      list(self.existing_positions_touched),
            "upstream_lifecycle_summary_status": self.upstream_lifecycle_summary_status,
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
# Runner-design gate
# ---------------------------------------------------------------------------

class DemoTinyLifecycleRunnerDesign:
    """
    Pure-computation runner-design gate.  Consolidates the 11 upstream
    artifacts (10 baseline + 014AA lifecycle summary) and emits a
    design document together with a final readiness verdict.

    Holds no network client, reads no environment variables, and NEVER
    invokes the order-create or trading-stop endpoints.

    --allow-runner-design-approval --> status promoted to
        TINY_LIFECYCLE_RUNNER_DESIGN_READY_BUT_EXECUTION_DISABLED.

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
        symbol:                           str  = DEFAULT_SELECTED_SYMBOL,
        allow_runner_design_approval:     bool = False,
        allow_real_runner_execution:      bool = False,
        _now:                             datetime | None = None,
    ) -> TinyLifecycleRunnerDesignResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_runner_execution:
            mode = MODE_REAL_RUNNER_EXECUTION_GUARD
        elif allow_runner_design_approval:
            mode = MODE_RUNNER_DESIGN_APPROVAL_DRY_RUN
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

        endpoint_family = _safe_str((readonly_smoke or {}).get("endpoint_family", ""))
        account_mode    = _safe_str((readonly_smoke or {}).get("account_mode", ""))
        proof_strength  = _safe_str((readonly_smoke or {}).get("proof_strength", ""))
        position_details_source = _safe_str(
            (reconciliation or {}).get(
                "position_details_source",
                (reconciliation or {}).get("mode", ""),
            )
        )
        lifecycle_status = _safe_str((lifecycle_mock or {}).get("status", ""))
        summary_status   = _safe_str((lifecycle_summary or {}).get("status", ""))

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

        if readonly_present and endpoint_family and endpoint_family != EXPECTED_ENDPOINT_FAMILY:
            blocked.append(GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO)
        if readonly_present and account_mode and account_mode != EXPECTED_ACCOUNT_MODE:
            blocked.append(GATE_ACCOUNT_MODE_NOT_DEMO)
        if readonly_present and proof_strength and proof_strength != EXPECTED_PROOF_STRENGTH:
            blocked.append(GATE_PROOF_STRENGTH_NOT_STRONG)
        if recon_present and position_details_source and position_details_source != EXPECTED_POSITION_DETAILS_SOURCE:
            blocked.append(GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY)

        if summary_present and summary_status and (
            summary_status not in ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES
        ):
            blocked.append(GATE_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE)

        if not sym:
            blocked.append(GATE_SELECTED_SYMBOL_MISSING)
        elif sym in existing_symbols:
            blocked.append(GATE_SELECTED_SYMBOL_COLLIDES_EXISTING)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 11 upstream artifacts + runtime proof envelope.",
            "readonly_smoke_present":                       readonly_present,
            "reconciliation_present":                       recon_present,
            "protection_present":                           protection_present,
            "contract_present":                             contract_present,
            "noop_plan_present":                            noop_present,
            "lifecycle_mock_present":                       lifecycle_present,
            "real_permission_gate_present":                 real_perm_present,
            "tiny_entry_permission_gate_present":           entry_perm_present,
            "tiny_stop_attach_permission_gate_present":     stop_perm_present,
            "tiny_cleanup_permission_gate_present":         cleanup_perm_present,
            "lifecycle_summary_present":                    summary_present,
            "endpoint_family_observed":                     endpoint_family,
            "endpoint_family_expected":                     EXPECTED_ENDPOINT_FAMILY,
            "account_mode_observed":                        account_mode,
            "account_mode_expected":                        EXPECTED_ACCOUNT_MODE,
            "proof_strength_observed":                      proof_strength,
            "proof_strength_expected":                      EXPECTED_PROOF_STRENGTH,
            "position_details_source_observed":             position_details_source,
            "position_details_source_expected":             EXPECTED_POSITION_DETAILS_SOURCE,
            "lifecycle_status_observed":                    lifecycle_status,
            "lifecycle_status_expected":                    EXPECTED_LIFECYCLE_STATUS,
            "lifecycle_summary_status_observed":            summary_status,
            "lifecycle_summary_status_acceptable":          sorted(
                ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES
            ),
            "selected_symbol":                              sym,
            "current_task_real_execution_allowed":          False,
        }

        # ===============================================================
        # stage_1_runner_design_scope
        # ===============================================================
        runner_design_scope: dict[str, Any] = {
            "design_only":                          True,
            "real_runner_implemented":              False,
            "real_execution_allowed":               False,
            "no_endpoint_invoked_in_this_task":     True,
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "next_required_task": (
                "TASK-014AC_tiny_lifecycle_runner_implementation_dry_run_only"
            ),
            "scope_summary": (
                "TASK-014AB only writes a runner design.  It does not "
                "implement, invoke, or authorise the future real "
                "tiny-position lifecycle runner."
            ),
        }
        stages[STAGE_1_RUNNER_DESIGN_SCOPE] = {
            "stage":   STAGE_1_RUNNER_DESIGN_SCOPE,
            "summary": "Assert design-only scope (no runner implemented, no endpoint invoked).",
            "runner_design_scope":                  runner_design_scope,
        }
        # Always-on design-scope gates.
        blocked.append(GATE_DESIGN_ONLY_TRUE)
        blocked.append(GATE_REAL_RUNNER_NOT_IMPLEMENTED)
        blocked.append(GATE_REAL_EXECUTION_NOT_ALLOWED)
        blocked.append(GATE_NO_ENDPOINT_INVOKED)
        blocked.append(GATE_NO_G20_LIFT)
        blocked.append(GATE_NEXT_TASK_IS_DRY_RUN_IMPL)

        # ===============================================================
        # stage_2_state_machine_design
        # ===============================================================
        # Map each real-submit state to the readonly state that MUST
        # follow.  Auto-advance is forbidden between these pairs.
        readonly_after_real: dict[str, str] = {
            "ENTRY_SUBMITTED":   "POST_ENTRY_READONLY_REQUIRED",
            "STOP_SUBMITTED":    "POST_STOP_READONLY_REQUIRED",
            "CLEANUP_SUBMITTED": "POST_CLEANUP_READONLY_REQUIRED",
        }
        state_machine_design: dict[str, Any] = {
            "runner_states":                        list(RUNNER_STATES),
            "real_submit_states":                   list(REAL_SUBMIT_STATES),
            "post_real_readonly_states":            list(POST_REAL_READONLY_STATES),
            "readonly_after_real":                  readonly_after_real,
            "readonly_between_real_steps_required": True,
            "no_auto_advance":                      True,
            "no_parallel_execution":                True,
            "no_skip_step":                         True,
            "no_retry_loop":                        True,
            "required_states_present":              True,
        }
        stages[STAGE_2_STATE_MACHINE_DESIGN] = {
            "stage":   STAGE_2_STATE_MACHINE_DESIGN,
            "summary": "Document the 18 runner states + readonly-between-real-steps invariant.",
            "state_machine_design":                 state_machine_design,
        }
        # Always-on state-machine gates.
        blocked.append(GATE_REQUIRED_STATES_PRESENT)
        blocked.append(GATE_READONLY_BETWEEN_REAL_STEPS_REQUIRED)
        blocked.append(GATE_NO_AUTO_ADVANCE)
        blocked.append(GATE_NO_PARALLEL_EXECUTION)
        blocked.append(GATE_NO_SKIP_STEP)
        blocked.append(GATE_NO_RETRY_LOOP_STATE_MACHINE)

        # ===============================================================
        # stage_3_manual_approval_contract
        # ===============================================================
        token_patterns = {
            ENTRY_TOKEN_PATTERN,
            STOP_ATTACH_TOKEN_PATTERN,
            CLEANUP_TOKEN_PATTERN,
        }
        manual_approval_contract: dict[str, Any] = {
            "entry_token_pattern":          ENTRY_TOKEN_PATTERN,
            "stop_attach_token_pattern":    STOP_ATTACH_TOKEN_PATTERN,
            "cleanup_token_pattern":        CLEANUP_TOKEN_PATTERN,
            "tokens_distinct_per_step":     len(token_patterns) == 3,
            "tokens_validated_in_this_task": False,
            "each_real_step_requires_separate_manual_approval": True,
            "token_format_alone_is_not_authorization":          True,
            "approval_steps_to_token_pattern": {
                "real_tiny_entry":  ENTRY_TOKEN_PATTERN,
                "real_stop_attach": STOP_ATTACH_TOKEN_PATTERN,
                "real_cleanup":     CLEANUP_TOKEN_PATTERN,
            },
            "future_runner_additional_confirmation_required": True,
        }
        stages[STAGE_3_MANUAL_APPROVAL_CONTRACT] = {
            "stage":   STAGE_3_MANUAL_APPROVAL_CONTRACT,
            "summary": "Document the 3 distinct manual approval tokens (never validated here).",
            "manual_approval_contract":             manual_approval_contract,
        }
        # Always-on manual-approval gates.
        blocked.append(GATE_ENTRY_TOKEN_PATTERN_PRESENT)
        blocked.append(GATE_STOP_TOKEN_PATTERN_PRESENT)
        blocked.append(GATE_CLEANUP_TOKEN_PATTERN_PRESENT)
        blocked.append(GATE_TOKENS_DISTINCT)
        blocked.append(GATE_TOKENS_NOT_VALIDATED_IN_THIS_TASK)
        blocked.append(GATE_EACH_STEP_SEPARATE_MANUAL_APPROVAL)
        blocked.append(GATE_TOKEN_FORMAT_IS_NOT_AUTHORIZATION)

        # ===============================================================
        # stage_4_execution_payload_contract
        # ===============================================================
        summary_dict = lifecycle_summary if isinstance(lifecycle_summary, dict) else {}
        entry_payload   = self._extract_payload(summary_dict, "entry_payload_preview")
        stop_payload    = self._extract_payload(summary_dict, "stop_payload_preview")
        cleanup_payload = self._extract_payload(summary_dict, "cleanup_payload_preview")

        expected_entry_ref = _safe_float(
            summary_dict.get("expected_entry_reference_price", 0.0)
        )
        if expected_entry_ref <= 0.0:
            protection_dict = protection if isinstance(protection, dict) else {}
            expected_entry_ref = _safe_float(
                protection_dict.get("entry_reference_price", 0.0)
            )

        entry_preview_ok   = entry_payload.get("preview_only") is True
        stop_preview_ok    = stop_payload.get("preview_only") is True
        cleanup_preview_ok = cleanup_payload.get("preview_only") is True

        entry_qty   = _safe_float(entry_payload.get("qty", 0.0))
        cleanup_qty = _safe_float(cleanup_payload.get("qty", 0.0))
        qty_match   = (
            entry_qty > 0.0
            and cleanup_qty > 0.0
            and abs(entry_qty - cleanup_qty) <= 1e-9 * max(1.0, entry_qty, cleanup_qty)
        )
        cleanup_reduce_only_ok = cleanup_payload.get("reduceOnly") is True

        stop_loss = _safe_float(stop_payload.get("stopLoss", 0.0))
        stop_loss_positive = stop_loss > 0.0
        stop_loss_below_ref = (
            stop_loss_positive
            and expected_entry_ref > 0.0
            and stop_loss < expected_entry_ref
        )

        # Conditional payload contract failures only fire when the lifecycle
        # summary artifact is present --- otherwise the missing-summary
        # gate covers the case.
        if summary_present:
            if not entry_preview_ok:
                blocked.append(GATE_ENTRY_PAYLOAD_PREVIEW_ONLY)
            if not stop_preview_ok:
                blocked.append(GATE_STOP_PAYLOAD_PREVIEW_ONLY)
            if not cleanup_preview_ok:
                blocked.append(GATE_CLEANUP_PAYLOAD_PREVIEW_ONLY)
            if not qty_match:
                blocked.append(GATE_ENTRY_QTY_EQUALS_CLEANUP_QTY)
            if not cleanup_reduce_only_ok:
                blocked.append(GATE_CLEANUP_REDUCE_ONLY_TRUE)
            if not stop_loss_positive:
                blocked.append(GATE_STOP_LOSS_POSITIVE)
            elif not stop_loss_below_ref:
                blocked.append(GATE_STOP_LOSS_LESS_THAN_ENTRY_REF)

        # Always-on no-real-conversion documentation gate.
        blocked.append(GATE_NO_PREVIEW_TO_REAL_CONVERSION)

        execution_payload_contract: dict[str, Any] = {
            "entry_payload_preview":          entry_payload,
            "stop_payload_preview":           stop_payload,
            "cleanup_payload_preview":        cleanup_payload,
            "entry_preview_only":             entry_preview_ok,
            "stop_preview_only":              stop_preview_ok,
            "cleanup_preview_only":           cleanup_preview_ok,
            "entry_qty":                      entry_qty,
            "cleanup_qty":                    cleanup_qty,
            "entry_qty_equals_cleanup_qty":   qty_match,
            "cleanup_reduce_only":            cleanup_reduce_only_ok,
            "stop_loss":                      stop_loss,
            "expected_entry_reference_price": expected_entry_ref,
            "stop_loss_positive":             stop_loss_positive,
            "stop_loss_less_than_entry_ref":  stop_loss_below_ref,
            "no_preview_to_real_conversion":  True,
        }
        stages[STAGE_4_EXECUTION_PAYLOAD_CONTRACT] = {
            "stage":   STAGE_4_EXECUTION_PAYLOAD_CONTRACT,
            "summary": "Pull 3 payload previews + verify design constraints (no conversion).",
            "execution_payload_contract":           execution_payload_contract,
        }

        # ===============================================================
        # stage_5_abort_and_fail_closed_policy
        # ===============================================================
        abort_and_fail_closed_policy: dict[str, Any] = {
            "entry_rejected":                       "fail_closed",
            "stop_attach_rejected":                 "fail_closed",
            "cleanup_rejected":                     "fail_closed",
            "readonly_unavailable_between_steps":   "fail_closed",
            "entry_or_cleanup_partial_fill":        "fail_closed",
            "existing_stop_mismatch":               "manual_review",
            "unexpected_position_appears":          "manual_review",
            "no_automatic_emergency_close":         True,
            "no_automatic_cleanup":                 True,
            "no_retry_loop_after_failure":          True,
            "emergency_close_preview_only":         True,
            "expected_existing_position_symbols":   list(EXISTING_POSITION_SYMBOLS),
        }
        stages[STAGE_5_ABORT_AND_FAIL_CLOSED_POLICY] = {
            "stage":   STAGE_5_ABORT_AND_FAIL_CLOSED_POLICY,
            "summary": "Document the abort / fail-closed policy for every real step.",
            "abort_and_fail_closed_policy":         abort_and_fail_closed_policy,
        }
        # Always-on failure-policy gates.
        blocked.append(GATE_ENTRY_FAIL_CLOSED)
        blocked.append(GATE_STOP_FAIL_CLOSED)
        blocked.append(GATE_CLEANUP_FAIL_CLOSED)
        blocked.append(GATE_READONLY_UNAVAILABLE_FAIL_CLOSED)
        blocked.append(GATE_PARTIAL_FILL_FAIL_CLOSED)
        blocked.append(GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW)
        blocked.append(GATE_UNEXPECTED_POSITION_MANUAL_REVIEW)
        blocked.append(GATE_NO_AUTO_EMERGENCY_CLOSE)
        blocked.append(GATE_NO_AUTO_CLEANUP)
        blocked.append(GATE_NO_RETRY_LOOP_FAILURE_POLICY)

        # ===============================================================
        # stage_6_observability_and_audit_design
        # ===============================================================
        observability_and_audit_design: dict[str, Any] = {
            "required_audit_artifacts":             list(REQUIRED_AUDIT_ARTIFACTS),
            "artifact_per_step_required":           True,
            "sanitized_response_required":          True,
            "forbidden_log_fields":                 list(FORBIDDEN_LOG_FIELDS),
            "no_secrets_in_logs":                   True,
            "discord_sanitized_summary_only":       True,
            "notion_sanitized_summary_only":        True,
        }
        stages[STAGE_6_OBSERVABILITY_AND_AUDIT_DESIGN] = {
            "stage":   STAGE_6_OBSERVABILITY_AND_AUDIT_DESIGN,
            "summary": "Document required audit artifacts + response sanitisation rules.",
            "observability_and_audit_design":       observability_and_audit_design,
        }
        # Always-on observability gates.
        blocked.append(GATE_ARTIFACT_PER_STEP_REQUIRED)
        blocked.append(GATE_SANITIZED_RESPONSE_REQUIRED)
        blocked.append(GATE_NO_SECRETS_IN_LOGS)
        blocked.append(GATE_DISCORD_SANITIZED_ONLY)
        blocked.append(GATE_NOTION_SANITIZED_ONLY)

        # ===============================================================
        # stage_7_final_design_verdict
        # ===============================================================
        # Always-on execution-guard gates.
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
        elif allow_real_runner_execution:
            failed_stage = ""
            status_out = STATUS_REAL_RUNNER_NOT_IMPL
            mode_out   = MODE_REAL_RUNNER_EXECUTION_GUARD
        elif allow_runner_design_approval:
            failed_stage = ""
            status_out = STATUS_DESIGN_READY_EXEC_DISABLED
            mode_out   = MODE_RUNNER_DESIGN_APPROVAL_DRY_RUN
        else:
            failed_stage = ""
            status_out = STATUS_DESIGN_READY
            mode_out   = MODE_DESIGN_CHECKLIST

        final_design_verdict: dict[str, Any] = {
            "runner_design_approval_allowed":       allow_runner_design_approval,
            "real_runner_execution_requested":      bool(allow_real_runner_execution),
            "real_execution_allowed":               False,
            "real_runner_implemented":              False,
            "current_task_real_execution_allowed":  False,
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "no_real_order_endpoint":               True,
            "no_real_stop_endpoint":                True,
            "no_position_modified":                 True,
            "no_live_endpoint":                     True,
            "no_secrets_emitted":                   True,
            "order_endpoint_called":                False,
            "stop_endpoint_called":                 False,
            "status":                               status_out,
            "mode":                                 mode_out,
            "next_required_task": (
                "TASK-014AC_tiny_lifecycle_runner_implementation_dry_run_only"
            ),
        }
        stages[STAGE_7_FINAL_DESIGN_VERDICT] = {
            "stage":   STAGE_7_FINAL_DESIGN_VERDICT,
            "summary": "Final design verdict + permanent execution guard.",
            "final_design_verdict":                 final_design_verdict,
        }

        return TinyLifecycleRunnerDesignResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            runner_design_scope=runner_design_scope,
            state_machine_design=state_machine_design,
            manual_approval_contract=manual_approval_contract,
            execution_payload_contract=execution_payload_contract,
            abort_and_fail_closed_policy=abort_and_fail_closed_policy,
            observability_and_audit_design=observability_and_audit_design,
            final_design_verdict=final_design_verdict,
            entry_payload_preview=entry_payload,
            stop_payload_preview=stop_payload,
            cleanup_payload_preview=cleanup_payload,
            expected_entry_reference_price=expected_entry_ref,
            runner_design_approval_allowed=allow_runner_design_approval,
            real_runner_execution_requested=bool(allow_real_runner_execution),
            real_execution_allowed=False,
            real_runner_implemented=False,
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
            secret_value_observed=False,
            g20_policy_still_in_place=True,
            g20_lifted=False,
            existing_positions_touched=[],
            upstream_lifecycle_summary_status=summary_status,
            blocked_gates=unique,
            failed_stage=failed_stage,
            status=status_out,
        )

    # ----------------------------------------------------------------- util
    @staticmethod
    def _extract_payload(src: dict[str, Any], key: str) -> dict[str, Any]:
        """Pull a payload-preview dict from an upstream artifact (top-level
        or nested in stages)."""
        if not isinstance(src, dict):
            return {}
        val = src.get(key)
        if isinstance(val, dict):
            return dict(val)
        stages = src.get("stages")
        if isinstance(stages, dict):
            for stage_env in stages.values():
                if isinstance(stage_env, dict):
                    nested = stage_env.get(key)
                    if isinstance(nested, dict):
                        return dict(nested)
                    plan = stage_env.get("execution_sequence_plan")
                    if isinstance(plan, dict):
                        refs = plan.get("step_payload_refs")
                        if isinstance(refs, dict):
                            for v in refs.values():
                                if isinstance(v, dict) and v.get(
                                    "endpoint_path_ref"
                                ) and key.split("_")[0] in _safe_str(
                                    v.get("orderLinkId", "")
                                ).lower():
                                    return dict(v)
        return {}

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
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE,
            GATE_SELECTED_SYMBOL_MISSING,
            GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
        }
        for g in blocked:
            if g in stage_0_set:
                return STAGE_0_ARTIFACT_PREFLIGHT
        stage_4_set = {
            GATE_ENTRY_PAYLOAD_PREVIEW_ONLY,
            GATE_STOP_PAYLOAD_PREVIEW_ONLY,
            GATE_CLEANUP_PAYLOAD_PREVIEW_ONLY,
            GATE_ENTRY_QTY_EQUALS_CLEANUP_QTY,
            GATE_CLEANUP_REDUCE_ONLY_TRUE,
            GATE_STOP_LOSS_POSITIVE,
            GATE_STOP_LOSS_LESS_THAN_ENTRY_REF,
        }
        for g in blocked:
            if g in stage_4_set:
                return STAGE_4_EXECUTION_PAYLOAD_CONTRACT
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
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_LIFECYCLE_STATUS",
    "EXPECTED_INSTRUMENT_CATEGORY",
    "EXPECTED_ENTRY_SIDE",
    "EXPECTED_CLEANUP_SIDE",
    "EXPECTED_ENTRY_ORDER_SIDE",
    "RUNNER_STATES",
    "REAL_SUBMIT_STATES",
    "POST_REAL_READONLY_STATES",
    "REQUIRED_AUDIT_ARTIFACTS",
    "FORBIDDEN_LOG_FIELDS",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_RUNNER_DESIGN_SCOPE",
    "STAGE_2_STATE_MACHINE_DESIGN",
    "STAGE_3_MANUAL_APPROVAL_CONTRACT",
    "STAGE_4_EXECUTION_PAYLOAD_CONTRACT",
    "STAGE_5_ABORT_AND_FAIL_CLOSED_POLICY",
    "STAGE_6_OBSERVABILITY_AND_AUDIT_DESIGN",
    "STAGE_7_FINAL_DESIGN_VERDICT",
    "ALL_STAGES",
    "STATUS_DESIGN_READY",
    "STATUS_DESIGN_READY_EXEC_DISABLED",
    "STATUS_REAL_RUNNER_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_DESIGN_CHECKLIST",
    "MODE_RUNNER_DESIGN_APPROVAL_DRY_RUN",
    "MODE_REAL_RUNNER_EXECUTION_GUARD",
    "MODE_FAIL_CLOSED",
    # general gates (21)
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
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_COLLIDES_EXISTING",
    "GATE_SELECTED_SYMBOL_MISSING",
    "GATE_LIFECYCLE_SUMMARY_STATUS_UNACCEPTABLE",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # design scope (6)
    "GATE_DESIGN_ONLY_TRUE",
    "GATE_REAL_RUNNER_NOT_IMPLEMENTED",
    "GATE_REAL_EXECUTION_NOT_ALLOWED",
    "GATE_NO_ENDPOINT_INVOKED",
    "GATE_NO_G20_LIFT",
    "GATE_NEXT_TASK_IS_DRY_RUN_IMPL",
    # state machine (6)
    "GATE_REQUIRED_STATES_PRESENT",
    "GATE_READONLY_BETWEEN_REAL_STEPS_REQUIRED",
    "GATE_NO_AUTO_ADVANCE",
    "GATE_NO_PARALLEL_EXECUTION",
    "GATE_NO_SKIP_STEP",
    "GATE_NO_RETRY_LOOP_STATE_MACHINE",
    # manual approval (7)
    "GATE_ENTRY_TOKEN_PATTERN_PRESENT",
    "GATE_STOP_TOKEN_PATTERN_PRESENT",
    "GATE_CLEANUP_TOKEN_PATTERN_PRESENT",
    "GATE_TOKENS_DISTINCT",
    "GATE_TOKENS_NOT_VALIDATED_IN_THIS_TASK",
    "GATE_EACH_STEP_SEPARATE_MANUAL_APPROVAL",
    "GATE_TOKEN_FORMAT_IS_NOT_AUTHORIZATION",
    # payload contract (8)
    "GATE_ENTRY_PAYLOAD_PREVIEW_ONLY",
    "GATE_STOP_PAYLOAD_PREVIEW_ONLY",
    "GATE_CLEANUP_PAYLOAD_PREVIEW_ONLY",
    "GATE_ENTRY_QTY_EQUALS_CLEANUP_QTY",
    "GATE_CLEANUP_REDUCE_ONLY_TRUE",
    "GATE_STOP_LOSS_POSITIVE",
    "GATE_STOP_LOSS_LESS_THAN_ENTRY_REF",
    "GATE_NO_PREVIEW_TO_REAL_CONVERSION",
    # failure policy (10)
    "GATE_ENTRY_FAIL_CLOSED",
    "GATE_STOP_FAIL_CLOSED",
    "GATE_CLEANUP_FAIL_CLOSED",
    "GATE_READONLY_UNAVAILABLE_FAIL_CLOSED",
    "GATE_PARTIAL_FILL_FAIL_CLOSED",
    "GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW",
    "GATE_UNEXPECTED_POSITION_MANUAL_REVIEW",
    "GATE_NO_AUTO_EMERGENCY_CLOSE",
    "GATE_NO_AUTO_CLEANUP",
    "GATE_NO_RETRY_LOOP_FAILURE_POLICY",
    # observability (5)
    "GATE_ARTIFACT_PER_STEP_REQUIRED",
    "GATE_SANITIZED_RESPONSE_REQUIRED",
    "GATE_NO_SECRETS_IN_LOGS",
    "GATE_DISCORD_SANITIZED_ONLY",
    "GATE_NOTION_SANITIZED_ONLY",
    # execution guard (5)
    "GATE_REAL_RUNNER_EXECUTION_NOT_IMPL",
    "GATE_NO_REAL_ORDER_ENDPOINT",
    "GATE_NO_REAL_STOP_ENDPOINT",
    "GATE_NO_POSITION_MODIFIED",
    "GATE_G20_NOT_LIFTED",
    # data
    "DemoTinyLifecycleRunnerDesign",
    "TinyLifecycleRunnerDesignResult",
]
