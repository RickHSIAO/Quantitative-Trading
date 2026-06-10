"""
src/demo_tiny_lifecycle_real_execution_summary.py
TASK-014AA: Tiny Lifecycle Real Execution Permission Summary / Final Review.

Pure-computation / mock-safe summary gate that consolidates the four
upstream permission gates (014W real-permission, 014X tiny-entry,
014Y tiny-stop-attach, 014Z tiny-cleanup) together with the original
readonly / reconciliation / protection / contract / no-op-plan /
lifecycle-mock artifacts, performs cross-artifact consistency checks,
and emits a final readiness verdict for the future real tiny-position
lifecycle execution runner (TASK-014AB).

This module does NOT execute anything: no /v5/order/create,
no /v5/position/trading-stop, no order send, no position modification,
no close-only, no emergency close, no leverage / transfer / withdraw,
no token validation, no socket open.

Stages:

  stage_0_artifact_preflight
      Validate 10 upstream artifacts (readonly_smoke / reconciliation /
      protection / contract / noop_plan / lifecycle_mock /
      tiny_position_real_permission_gate / tiny_entry_permission_gate /
      tiny_stop_attach_permission_gate / tiny_cleanup_permission_gate)
      plus the runtime proof envelope.

  stage_1_lifecycle_plan_consistency
      Cross-artifact consistency checks: selected symbol, entry side,
      cleanup side, tiny qty, stop price, entry reference price,
      instrument category, existing-position symbol set, payload-preview
      payload shapes, lifecycle recommended-path, expected endpoint
      path refs.

  stage_2_existing_position_safety_review
      Snapshot the 5 existing demo shorts.  Selected symbol must be
      disjoint from existing position symbols.  existing_positions_touched
      must remain [].  Existing-stop snapshot must be expected-match.

  stage_3_execution_sequence_review
      Document the fixed 8-step real-lifecycle sequence:
          1. pre_readonly_snapshot
          2. real_tiny_entry
          3. post_entry_readonly
          4. real_stop_attach
          5. post_stop_attach_readonly
          6. real_cleanup
          7. post_cleanup_readonly
          8. final_audit
      Each step is preview-only here: endpoint_called=False,
      preview_only=True.

  stage_4_manual_approval_matrix
      Document the 3 distinct manual approval tokens (entry /
      stop-attach / cleanup).  Tokens are NEVER validated in this task.
      Tokens MUST be distinct per step.

  stage_5_failure_response_matrix
      Document the failure-response matrix: entry rejected / stop
      rejected / cleanup rejected / partial fills / readonly
      unavailable / SOLUSDT still open / existing stop mismatch /
      unexpected position appears / no automatic retry / no real
      emergency-close.

  stage_6_final_readiness_verdict
      Resolve final status:
          TINY_LIFECYCLE_PERMISSION_SUMMARY_READY                       (default)
          TINY_LIFECYCLE_PERMISSION_SUMMARY_READY_BUT_EXECUTION_DISABLED (--allow-real-lifecycle-summary)
          REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED                       (--allow-real-lifecycle-execution)
          FAIL_CLOSED                                                    (hard-fail gate raised)
      Always emits real_execution_allowed=False,
      current_task_real_execution_allowed=False, g20_lifted=False.

Modes:
  checklist                          --- default
  real_lifecycle_summary_dry_run     --- with --allow-real-lifecycle-summary
  real_lifecycle_execution_guard     --- with --allow-real-lifecycle-execution
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
  * invoke /v5/order/create or /v5/position/trading-stop
  * lift TASK-014L sender G20 (protected_entry_policy_missing)
  * touch ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT
  * mutate leverage / transfer / withdraw / deposit
"""
from __future__ import annotations

import math
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

STAGE_0_ARTIFACT_PREFLIGHT                  = "stage_0_artifact_preflight"
STAGE_1_LIFECYCLE_PLAN_CONSISTENCY          = "stage_1_lifecycle_plan_consistency"
STAGE_2_EXISTING_POSITION_SAFETY_REVIEW     = "stage_2_existing_position_safety_review"
STAGE_3_EXECUTION_SEQUENCE_REVIEW           = "stage_3_execution_sequence_review"
STAGE_4_MANUAL_APPROVAL_MATRIX              = "stage_4_manual_approval_matrix"
STAGE_5_FAILURE_RESPONSE_MATRIX             = "stage_5_failure_response_matrix"
STAGE_6_FINAL_READINESS_VERDICT             = "stage_6_final_readiness_verdict"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_LIFECYCLE_PLAN_CONSISTENCY,
    STAGE_2_EXISTING_POSITION_SAFETY_REVIEW,
    STAGE_3_EXECUTION_SEQUENCE_REVIEW,
    STAGE_4_MANUAL_APPROVAL_MATRIX,
    STAGE_5_FAILURE_RESPONSE_MATRIX,
    STAGE_6_FINAL_READINESS_VERDICT,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_SUMMARY_READY                = "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY"
STATUS_SUMMARY_READY_EXEC_DISABLED  = (
    "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_LIFECYCLE_NOT_IMPL      = "REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                  = "FAIL_CLOSED"

MODE_CHECKLIST                              = "checklist"
MODE_REAL_LIFECYCLE_SUMMARY_DRY_RUN         = "real_lifecycle_summary_dry_run"
MODE_REAL_LIFECYCLE_EXECUTION_GUARD         = "real_lifecycle_execution_guard"
MODE_FAIL_CLOSED                            = "fail_closed"


# ---------------------------------------------------------------------------
# Acceptable upstream-status whitelists
# ---------------------------------------------------------------------------

ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES: frozenset[str] = frozenset({
    "REAL_PERMISSION_CHECKLIST_READY",
    "REAL_PERMISSION_GATE_READY_BUT_EXECUTION_DISABLED",
    "REAL_TINY_POSITION_NOT_IMPLEMENTED",
})

ACCEPTABLE_TINY_ENTRY_PERMISSION_GATE_STATUSES: frozenset[str] = frozenset({
    "TINY_ENTRY_PERMISSION_CHECKLIST_READY",
    "TINY_ENTRY_PERMISSION_READY_BUT_EXECUTION_DISABLED",
    "REAL_TINY_ENTRY_NOT_IMPLEMENTED",
})

ACCEPTABLE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUSES: frozenset[str] = frozenset({
    "TINY_STOP_ATTACH_PERMISSION_CHECKLIST_READY",
    "TINY_STOP_ATTACH_PERMISSION_READY_BUT_EXECUTION_DISABLED",
    "REAL_STOP_ATTACH_NOT_IMPLEMENTED",
})

ACCEPTABLE_TINY_CLEANUP_PERMISSION_GATE_STATUSES: frozenset[str] = frozenset({
    "TINY_CLEANUP_PERMISSION_CHECKLIST_READY",
    "TINY_CLEANUP_PERMISSION_READY_BUT_EXECUTION_DISABLED",
    "REAL_CLEANUP_NOT_IMPLEMENTED",
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
EXPECTED_NOOP_RECOMMENDED_PATH   = "tiny_isolated_position_plan"
EXPECTED_LIFECYCLE_STATUS        = "MOCK_TINY_LIFECYCLE_SUCCESS"
EXPECTED_INSTRUMENT_CATEGORY     = "linear"

EXPECTED_ENTRY_SIDE              = "long"
EXPECTED_CLEANUP_SIDE            = "Sell"
EXPECTED_ENTRY_ORDER_SIDE        = "Buy"
EXPECTED_ORDER_TYPE              = "Market"
EXPECTED_POSITION_IDX            = 0


# ---------------------------------------------------------------------------
# Fixed real-lifecycle 8-step sequence
# ---------------------------------------------------------------------------

REAL_LIFECYCLE_STEPS: tuple[str, ...] = (
    "pre_readonly_snapshot",
    "real_tiny_entry",
    "post_entry_readonly",
    "real_stop_attach",
    "post_stop_attach_readonly",
    "real_cleanup",
    "post_cleanup_readonly",
    "final_audit",
)


# ---------------------------------------------------------------------------
# Gate constants  (23 general + 13 consistency + 7 manual approval +
#                  11 failure + 5 execution guard = 59)
# ---------------------------------------------------------------------------

# General gates (23)
GATE_READONLY_SMOKE_MISSING                  = "readonly_smoke_missing"
GATE_RECONCILIATION_MISSING                  = "reconciliation_missing"
GATE_PROTECTION_MISSING                      = "protection_missing"
GATE_CONTRACT_MISSING                        = "contract_missing"
GATE_NOOP_PLAN_MISSING                       = "noop_plan_missing"
GATE_LIFECYCLE_MOCK_MISSING                  = "lifecycle_mock_missing"
GATE_REAL_PERMISSION_GATE_MISSING            = "real_permission_gate_missing"
GATE_TINY_ENTRY_PERMISSION_GATE_MISSING      = "tiny_entry_permission_gate_missing"
GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING = (
    "tiny_stop_attach_permission_gate_missing"
)
GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING    = "tiny_cleanup_permission_gate_missing"
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO          = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                   = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG               = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_MISSING                 = "selected_symbol_missing"
GATE_SELECTED_SYMBOL_COLLIDES_EXISTING       = "selected_symbol_collides_with_existing_position"
GATE_LIFECYCLE_MOCK_NOT_SUCCESS              = "lifecycle_mock_status_not_success"
GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE = "real_permission_gate_status_unacceptable"
GATE_TINY_ENTRY_PERMISSION_GATE_STATUS_UNACCEPTABLE = (
    "tiny_entry_permission_gate_status_unacceptable"
)
GATE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUS_UNACCEPTABLE = (
    "tiny_stop_attach_permission_gate_status_unacceptable"
)
GATE_TINY_CLEANUP_PERMISSION_GATE_STATUS_UNACCEPTABLE = (
    "tiny_cleanup_permission_gate_status_unacceptable"
)
GATE_G20_POLICY_STILL_IN_PLACE               = "g20_sender_policy_still_in_place"
GATE_NO_SECRETS_EMITTED                      = "no_secret_values_emitted_in_this_task"

# Consistency gates (13)
GATE_SELECTED_SYMBOL_INCONSISTENT            = "selected_symbol_inconsistent_across_artifacts"
GATE_ENTRY_SIDE_INCONSISTENT                 = "entry_side_inconsistent_across_artifacts"
GATE_CLEANUP_SIDE_INCONSISTENT               = "cleanup_side_inconsistent_across_artifacts"
GATE_TINY_QTY_INCONSISTENT                   = "tiny_qty_inconsistent_across_artifacts"
GATE_STOP_PRICE_INCONSISTENT                 = "stop_price_inconsistent_across_artifacts"
GATE_ENTRY_REFERENCE_PRICE_INCONSISTENT      = "entry_reference_price_inconsistent_across_artifacts"
GATE_INSTRUMENT_CATEGORY_INCONSISTENT        = "instrument_category_inconsistent_across_artifacts"
GATE_EXISTING_POSITION_SYMBOLS_INCONSISTENT  = "existing_position_symbols_inconsistent"
GATE_ENTRY_PAYLOAD_PREVIEW_INCONSISTENT      = "entry_payload_preview_inconsistent"
GATE_STOP_PAYLOAD_PREVIEW_INCONSISTENT       = "stop_payload_preview_inconsistent"
GATE_CLEANUP_PAYLOAD_PREVIEW_INCONSISTENT    = "cleanup_payload_preview_inconsistent"
GATE_LIFECYCLE_RECOMMENDED_PATH_INCONSISTENT = "lifecycle_recommended_path_inconsistent"
GATE_EXPECTED_ENDPOINT_PATH_INCONSISTENT     = "expected_endpoint_path_inconsistent"

# Manual approval gates (7)
GATE_ENTRY_TOKEN_PATTERN_REQUIRED            = "entry_token_pattern_required_in_future_task"
GATE_STOP_ATTACH_TOKEN_PATTERN_REQUIRED      = "stop_attach_token_pattern_required_in_future_task"
GATE_CLEANUP_TOKEN_PATTERN_REQUIRED          = "cleanup_token_pattern_required_in_future_task"
GATE_TOKENS_MUST_BE_DISTINCT_PER_STEP        = "tokens_must_be_distinct_per_step"
GATE_NO_TOKEN_VALIDATED_IN_THIS_TASK         = "no_token_validated_in_this_task"
GATE_MANUAL_APPROVAL_REQUIRED_PER_STAGE      = "manual_approval_required_per_lifecycle_stage"
GATE_REAL_LIFECYCLE_RUNNER_NOT_YET_DESIGNED  = "real_lifecycle_runner_not_yet_designed"

# Failure gates (11)
GATE_ENTRY_REJECTED_FAIL_CLOSED              = "entry_rejected_fail_closed"
GATE_STOP_ATTACH_REJECTED_FAIL_CLOSED        = "stop_attach_rejected_fail_closed"
GATE_CLEANUP_REJECTED_FAIL_CLOSED            = "cleanup_rejected_fail_closed"
GATE_ENTRY_PARTIAL_FILL_FAIL_CLOSED          = "entry_partial_fill_fail_closed"
GATE_CLEANUP_PARTIAL_FILL_FAIL_CLOSED        = "cleanup_partial_fill_fail_closed"
GATE_READONLY_UNAVAILABLE_BETWEEN_STEPS_FAIL_CLOSED = (
    "readonly_unavailable_between_steps_fail_closed"
)
GATE_TINY_POSITION_STILL_OPEN_AFTER_CLEANUP_FAIL_CLOSED = (
    "tiny_position_still_open_after_cleanup_fail_closed"
)
GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW    = "existing_stop_mismatch_manual_review_required"
GATE_UNEXPECTED_POSITION_APPEARS_MANUAL_REVIEW = (
    "unexpected_position_appears_during_lifecycle_manual_review_required"
)
GATE_NO_AUTO_RETRY_AFTER_ANY_FAILURE         = "no_automatic_retry_after_any_lifecycle_failure"
GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK       = "no_real_emergency_close_in_this_task"

# Execution guard gates (5)
GATE_REAL_LIFECYCLE_EXECUTION_NOT_IMPL       = "real_lifecycle_execution_not_implemented"
GATE_NO_REAL_ORDER_ENDPOINT                  = "no_real_order_endpoint_in_this_task"
GATE_NO_REAL_STOP_ENDPOINT                   = "no_real_stop_endpoint_in_this_task"
GATE_NO_POSITION_MODIFIED                    = "no_position_modified_in_this_task"
GATE_G20_NOT_LIFTED                          = "g20_policy_not_lifted_by_this_task"


# Hard-fail-closed gates --- if ANY of these surface, the result is
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
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_LIFECYCLE_MOCK_NOT_SUCCESS,
    GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_TINY_ENTRY_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_TINY_CLEANUP_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_SELECTED_SYMBOL_INCONSISTENT,
    GATE_ENTRY_SIDE_INCONSISTENT,
    GATE_CLEANUP_SIDE_INCONSISTENT,
    GATE_TINY_QTY_INCONSISTENT,
    GATE_STOP_PRICE_INCONSISTENT,
    GATE_ENTRY_REFERENCE_PRICE_INCONSISTENT,
    GATE_INSTRUMENT_CATEGORY_INCONSISTENT,
    GATE_EXISTING_POSITION_SYMBOLS_INCONSISTENT,
    GATE_ENTRY_PAYLOAD_PREVIEW_INCONSISTENT,
    GATE_STOP_PAYLOAD_PREVIEW_INCONSISTENT,
    GATE_CLEANUP_PAYLOAD_PREVIEW_INCONSISTENT,
    GATE_LIFECYCLE_RECOMMENDED_PATH_INCONSISTENT,
    GATE_EXPECTED_ENDPOINT_PATH_INCONSISTENT,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyLifecycleRealExecutionSummaryResult:
    """Read-only outcome of one tiny-lifecycle real-execution summary pass."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    # Consolidated lifecycle plan inputs.
    entry_side:                   str   = EXPECTED_ENTRY_SIDE
    entry_order_side:             str   = EXPECTED_ENTRY_ORDER_SIDE
    cleanup_side:                 str   = EXPECTED_CLEANUP_SIDE
    expected_tiny_qty:            float = 0.0
    expected_stop_price:          float = 0.0
    expected_entry_reference_price: float = 0.0
    expected_instrument_category: str   = EXPECTED_INSTRUMENT_CATEGORY
    expected_lifecycle_recommended_path: str = EXPECTED_NOOP_RECOMMENDED_PATH

    # Payload previews (carried through from upstream gates, NEVER sent).
    entry_payload_preview:        dict[str, Any] = field(default_factory=dict)
    stop_payload_preview:         dict[str, Any] = field(default_factory=dict)
    cleanup_payload_preview:      dict[str, Any] = field(default_factory=dict)

    # Token patterns (documented only).
    entry_token_pattern:          str = ENTRY_TOKEN_PATTERN
    stop_attach_token_pattern:    str = STOP_ATTACH_TOKEN_PATTERN
    cleanup_token_pattern:        str = CLEANUP_TOKEN_PATTERN

    # Fixed real-lifecycle sequence (string-only, preview-only).
    real_lifecycle_steps:         list[str] = field(
        default_factory=lambda: list(REAL_LIFECYCLE_STEPS)
    )
    execution_sequence_plan:      dict[str, Any] = field(default_factory=dict)

    # Approval matrix + failure-response matrix.
    manual_approval_matrix:       dict[str, Any] = field(default_factory=dict)
    failure_response_matrix:      dict[str, Any] = field(default_factory=dict)

    existing_positions_snapshot:  list[dict[str, Any]] = field(default_factory=list)

    # Real-execution gating flags (TASK-014AA keeps all of these conservative).
    real_lifecycle_summary_dry_run_allowed: bool = False
    real_lifecycle_execution_requested:     bool = False
    real_execution_allowed:       bool = False
    real_lifecycle_runner_implemented:     bool = False
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

    existing_position_stop_snapshot_match: bool = True
    existing_positions_touched:   list[str] = field(default_factory=list)

    # Upstream gate status echo (for audit).
    upstream_real_permission_status:        str = ""
    upstream_tiny_entry_permission_status:  str = ""
    upstream_tiny_stop_attach_permission_status: str = ""
    upstream_tiny_cleanup_permission_status: str = ""

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = (
        "TASK-014AB_tiny_lifecycle_real_execution_runner_design_or_manual_approval"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                  self.timestamp_utc,
            "timestamp_utc":              self.timestamp_utc,
            "mode":                       self.mode,
            "selected_symbol":            self.selected_symbol,
            "existing_position_symbols":  list(self.existing_position_symbols),
            "stages":                     {k: dict(v) for k, v in self.stages.items()},
            "stage_order":                list(self.stage_order),
            "entry_side":                 self.entry_side,
            "entry_order_side":           self.entry_order_side,
            "cleanup_side":               self.cleanup_side,
            "expected_tiny_qty":          self.expected_tiny_qty,
            "expected_stop_price":        self.expected_stop_price,
            "expected_entry_reference_price": self.expected_entry_reference_price,
            "expected_instrument_category": self.expected_instrument_category,
            "expected_lifecycle_recommended_path": self.expected_lifecycle_recommended_path,
            "entry_payload_preview":      dict(self.entry_payload_preview),
            "stop_payload_preview":       dict(self.stop_payload_preview),
            "cleanup_payload_preview":    dict(self.cleanup_payload_preview),
            "entry_token_pattern":        self.entry_token_pattern,
            "stop_attach_token_pattern":  self.stop_attach_token_pattern,
            "cleanup_token_pattern":      self.cleanup_token_pattern,
            "real_lifecycle_steps":       list(self.real_lifecycle_steps),
            "execution_sequence_plan":    dict(self.execution_sequence_plan),
            "manual_approval_matrix":     dict(self.manual_approval_matrix),
            "failure_response_matrix":    dict(self.failure_response_matrix),
            "existing_positions_snapshot": [dict(row) for row in self.existing_positions_snapshot],
            "real_lifecycle_summary_dry_run_allowed": self.real_lifecycle_summary_dry_run_allowed,
            "real_lifecycle_execution_requested": self.real_lifecycle_execution_requested,
            "real_execution_allowed":     self.real_execution_allowed,
            "real_lifecycle_runner_implemented": self.real_lifecycle_runner_implemented,
            "current_task_real_execution_allowed": self.current_task_real_execution_allowed,
            "order_create_path_ref":      self.order_create_path_ref,
            "trading_stop_path_ref":      self.trading_stop_path_ref,
            "base_url_ref":               self.base_url_ref,
            "order_endpoint_called":      self.order_endpoint_called,
            "stop_endpoint_called":       self.stop_endpoint_called,
            "no_position_modified":       self.no_position_modified,
            "no_live_endpoint":           self.no_live_endpoint,
            "no_orders_sent":             self.no_orders_sent,
            "no_batch_order":             self.no_batch_order,
            "no_close_only_path":         self.no_close_only_path,
            "emergency_close_invoked":    self.emergency_close_invoked,
            "leverage_mutated":           self.leverage_mutated,
            "transfer_invoked":           self.transfer_invoked,
            "secret_value_observed":      self.secret_value_observed,
            "g20_policy_still_in_place":  self.g20_policy_still_in_place,
            "g20_lifted":                 self.g20_lifted,
            "existing_position_stop_snapshot_match": self.existing_position_stop_snapshot_match,
            "existing_positions_touched": list(self.existing_positions_touched),
            "upstream_real_permission_status": self.upstream_real_permission_status,
            "upstream_tiny_entry_permission_status": self.upstream_tiny_entry_permission_status,
            "upstream_tiny_stop_attach_permission_status": self.upstream_tiny_stop_attach_permission_status,
            "upstream_tiny_cleanup_permission_status": self.upstream_tiny_cleanup_permission_status,
            "blocked_gates":              list(self.blocked_gates),
            "failed_stage":               self.failed_stage,
            "status":                     self.status,
            "next_required_task":         self.next_required_task,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(f):
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
    out: list[dict[str, Any]] = []
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
    for row in rows:
        if isinstance(row, dict):
            sym = str(row.get("symbol", "")).strip()
            if not sym:
                continue
            out.append({
                "symbol": sym,
                "side":   str(row.get("side", "")).strip(),
                "qty":    _safe_float(row.get("quantity",     row.get("qty",     0.0)), 0.0),
                "entry":  _safe_float(row.get("entry_price",  row.get("entry",   0.0)), 0.0),
                "stop":   _safe_float(row.get("stop_price",   row.get("stop",    0.0)), 0.0),
            })
    if not out:
        out = [
            {"symbol": s, "side": "", "qty": 0.0, "entry": 0.0, "stop": 0.0}
            for s in EXISTING_POSITION_SYMBOLS
        ]
    return out


def _symbols_only(snapshot: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("symbol", "")).strip() for row in snapshot]


def _close(a: float, b: float, tol: float = 1e-6) -> bool:
    if a == 0.0 and b == 0.0:
        return True
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


# ---------------------------------------------------------------------------
# Final summary gate
# ---------------------------------------------------------------------------

class DemoTinyLifecycleRealExecutionSummary:
    """
    Pure-computation summary gate consolidating the four tiny-lifecycle
    permission gates (real-permission / entry / stop-attach / cleanup)
    plus the six original demo-trading artifacts.  Performs cross-artifact
    consistency checks and emits the final readiness verdict for the
    future real tiny-position lifecycle runner.

    Holds no network client, reads no environment variables, and NEVER
    invokes the order-create or trading-stop endpoints.

    --allow-real-lifecycle-summary  --> status promoted to
        TINY_LIFECYCLE_PERMISSION_SUMMARY_READY_BUT_EXECUTION_DISABLED
        (no execution; envelope only).

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
        tiny_stop_attach_permission_gate: dict[str, Any] | None,
        tiny_cleanup_permission_gate:     dict[str, Any] | None,
        symbol:                           str  = DEFAULT_SELECTED_SYMBOL,
        allow_real_lifecycle_summary:     bool = False,
        allow_real_lifecycle_execution:   bool = False,
        _now:                             datetime | None = None,
    ) -> TinyLifecycleRealExecutionSummaryResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_lifecycle_execution:
            mode = MODE_REAL_LIFECYCLE_EXECUTION_GUARD
        elif allow_real_lifecycle_summary:
            mode = MODE_REAL_LIFECYCLE_SUMMARY_DRY_RUN
        else:
            mode = MODE_CHECKLIST

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
        real_perm_status = _safe_str((real_permission_gate or {}).get("status", ""))
        entry_perm_status = _safe_str((tiny_entry_permission_gate or {}).get("status", ""))
        stop_perm_status = _safe_str((tiny_stop_attach_permission_gate or {}).get("status", ""))
        cleanup_perm_status = _safe_str((tiny_cleanup_permission_gate or {}).get("status", ""))

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

        if readonly_present and endpoint_family and endpoint_family != EXPECTED_ENDPOINT_FAMILY:
            blocked.append(GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO)
        if readonly_present and account_mode and account_mode != EXPECTED_ACCOUNT_MODE:
            blocked.append(GATE_ACCOUNT_MODE_NOT_DEMO)
        if readonly_present and proof_strength and proof_strength != EXPECTED_PROOF_STRENGTH:
            blocked.append(GATE_PROOF_STRENGTH_NOT_STRONG)
        if recon_present and position_details_source and position_details_source != EXPECTED_POSITION_DETAILS_SOURCE:
            blocked.append(GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY)
        if lifecycle_present and lifecycle_status and lifecycle_status != EXPECTED_LIFECYCLE_STATUS:
            blocked.append(GATE_LIFECYCLE_MOCK_NOT_SUCCESS)
        if real_perm_present and real_perm_status and (
            real_perm_status not in ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES
        ):
            blocked.append(GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE)
        if entry_perm_present and entry_perm_status and (
            entry_perm_status not in ACCEPTABLE_TINY_ENTRY_PERMISSION_GATE_STATUSES
        ):
            blocked.append(GATE_TINY_ENTRY_PERMISSION_GATE_STATUS_UNACCEPTABLE)
        if stop_perm_present and stop_perm_status and (
            stop_perm_status not in ACCEPTABLE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUSES
        ):
            blocked.append(GATE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUS_UNACCEPTABLE)
        if cleanup_perm_present and cleanup_perm_status and (
            cleanup_perm_status not in ACCEPTABLE_TINY_CLEANUP_PERMISSION_GATE_STATUSES
        ):
            blocked.append(GATE_TINY_CLEANUP_PERMISSION_GATE_STATUS_UNACCEPTABLE)

        if not sym:
            blocked.append(GATE_SELECTED_SYMBOL_MISSING)
        elif sym in existing_symbols:
            blocked.append(GATE_SELECTED_SYMBOL_COLLIDES_EXISTING)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 10 upstream artifacts + runtime proof envelope.",
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
            "real_permission_gate_status_observed":         real_perm_status,
            "real_permission_gate_status_acceptable":       sorted(
                ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES
            ),
            "tiny_entry_permission_gate_status_observed":   entry_perm_status,
            "tiny_entry_permission_gate_status_acceptable": sorted(
                ACCEPTABLE_TINY_ENTRY_PERMISSION_GATE_STATUSES
            ),
            "tiny_stop_attach_permission_gate_status_observed": stop_perm_status,
            "tiny_stop_attach_permission_gate_status_acceptable": sorted(
                ACCEPTABLE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUSES
            ),
            "tiny_cleanup_permission_gate_status_observed": cleanup_perm_status,
            "tiny_cleanup_permission_gate_status_acceptable": sorted(
                ACCEPTABLE_TINY_CLEANUP_PERMISSION_GATE_STATUSES
            ),
            "selected_symbol":                              sym,
            "current_task_real_execution_allowed":          False,
        }

        # ===============================================================
        # stage_1_lifecycle_plan_consistency
        # ===============================================================
        # Derive canonical plan values from the most authoritative source
        # per field.  Then check the other artifacts against them.
        protection_dict = protection if isinstance(protection, dict) else {}
        contract_dict   = contract if isinstance(contract, dict) else {}
        noop_dict       = noop_plan if isinstance(noop_plan, dict) else {}
        lifecycle_dict  = lifecycle_mock if isinstance(lifecycle_mock, dict) else {}
        real_perm_dict  = real_permission_gate if isinstance(real_permission_gate, dict) else {}
        entry_dict      = tiny_entry_permission_gate if isinstance(tiny_entry_permission_gate, dict) else {}
        stop_dict       = tiny_stop_attach_permission_gate if isinstance(tiny_stop_attach_permission_gate, dict) else {}
        cleanup_dict    = tiny_cleanup_permission_gate if isinstance(tiny_cleanup_permission_gate, dict) else {}

        entry_payload_preview   = self._extract_payload(entry_dict, "entry_payload_preview")
        stop_payload_preview    = self._extract_payload(stop_dict, "stop_payload_preview")
        cleanup_payload_preview = self._extract_payload(cleanup_dict, "cleanup_payload_preview")

        # Canonical tiny qty: prefer entry permission gate's rounded_tiny_qty.
        entry_rounded_tiny_qty = _safe_float(entry_dict.get("rounded_tiny_qty", 0.0), 0.0)
        lifecycle_tiny_qty     = _safe_float(lifecycle_dict.get("tiny_qty", 0.0), 0.0)
        cleanup_expected_qty   = _safe_float(cleanup_dict.get("expected_tiny_qty", 0.0), 0.0)
        entry_payload_qty      = _safe_float(entry_payload_preview.get("qty", 0.0), 0.0)
        cleanup_payload_qty    = _safe_float(cleanup_payload_preview.get("qty", 0.0), 0.0)

        if entry_rounded_tiny_qty > 0.0:
            expected_tiny_qty = entry_rounded_tiny_qty
        elif lifecycle_tiny_qty > 0.0:
            expected_tiny_qty = lifecycle_tiny_qty
        elif cleanup_expected_qty > 0.0:
            expected_tiny_qty = cleanup_expected_qty
        else:
            expected_tiny_qty = 0.0

        # Canonical stop price: prefer stop-attach permission gate's stop_price.
        stop_stop_price       = _safe_float(stop_dict.get("stop_price", 0.0), 0.0)
        protection_stop_price = _safe_float(protection_dict.get("stop_price", 0.0), 0.0)
        lifecycle_stop_price  = _safe_float(lifecycle_dict.get("stop_price", 0.0), 0.0)
        stop_payload_stop_loss = _safe_float(stop_payload_preview.get("stopLoss", 0.0), 0.0)

        if stop_stop_price > 0.0:
            expected_stop_price = stop_stop_price
        elif protection_stop_price > 0.0:
            expected_stop_price = protection_stop_price
        elif lifecycle_stop_price > 0.0:
            expected_stop_price = lifecycle_stop_price
        else:
            expected_stop_price = 0.0

        protection_entry_ref = _safe_float(protection_dict.get("entry_reference_price", 0.0), 0.0)
        lifecycle_entry_ref  = _safe_float(lifecycle_dict.get("entry_reference_price", 0.0), 0.0)
        if protection_entry_ref > 0.0:
            expected_entry_reference_price = protection_entry_ref
        elif lifecycle_entry_ref > 0.0:
            expected_entry_reference_price = lifecycle_entry_ref
        else:
            expected_entry_reference_price = 0.0

        # Selected symbol consistency.
        sym_candidates: list[tuple[str, str]] = [
            ("protection",         _safe_str(protection_dict.get("selected_symbol", ""))),
            ("contract",           _safe_str(contract_dict.get("selected_symbol", ""))),
            ("noop_plan",          _safe_str(noop_dict.get("selected_symbol", ""))),
            ("lifecycle_mock",     _safe_str(lifecycle_dict.get("selected_symbol", ""))),
            ("real_permission",    _safe_str(real_perm_dict.get("selected_symbol", ""))),
            ("tiny_entry",         _safe_str(entry_dict.get("selected_symbol", ""))),
            ("tiny_stop_attach",   _safe_str(stop_dict.get("selected_symbol", ""))),
            ("tiny_cleanup",       _safe_str(cleanup_dict.get("selected_symbol", ""))),
        ]
        non_empty_syms = [v for _, v in sym_candidates if v]
        sym_consistent = bool(sym) and all(v == sym for v in non_empty_syms)
        if non_empty_syms and not sym_consistent:
            blocked.append(GATE_SELECTED_SYMBOL_INCONSISTENT)

        # Entry side consistency.
        protection_side = _safe_str(protection_dict.get("selected_side", "")).lower()
        lifecycle_side  = _safe_str(lifecycle_dict.get("side", "")).lower()
        entry_side_observed_candidates = [s for s in (protection_side, lifecycle_side) if s]
        entry_side_consistent = all(s == EXPECTED_ENTRY_SIDE for s in entry_side_observed_candidates)
        if entry_side_observed_candidates and not entry_side_consistent:
            blocked.append(GATE_ENTRY_SIDE_INCONSISTENT)

        # Cleanup side consistency.
        cleanup_side_observed = _safe_str(cleanup_dict.get("cleanup_side", EXPECTED_CLEANUP_SIDE))
        cleanup_payload_side  = _safe_str(cleanup_payload_preview.get("side", ""))
        cleanup_side_candidates = [s for s in (cleanup_side_observed, cleanup_payload_side) if s]
        cleanup_side_consistent = all(s == EXPECTED_CLEANUP_SIDE for s in cleanup_side_candidates)
        if cleanup_side_candidates and not cleanup_side_consistent:
            blocked.append(GATE_CLEANUP_SIDE_INCONSISTENT)

        # Tiny qty consistency.
        qty_candidates = [
            q for q in (
                entry_rounded_tiny_qty, lifecycle_tiny_qty, cleanup_expected_qty,
                entry_payload_qty, cleanup_payload_qty,
            ) if q > 0.0
        ]
        qty_consistent = bool(qty_candidates) and all(
            _close(q, expected_tiny_qty) for q in qty_candidates
        )
        if qty_candidates and not qty_consistent:
            blocked.append(GATE_TINY_QTY_INCONSISTENT)

        # Stop price consistency.
        stop_candidates = [
            s for s in (
                stop_stop_price, protection_stop_price, lifecycle_stop_price,
                stop_payload_stop_loss,
            ) if s > 0.0
        ]
        stop_consistent = bool(stop_candidates) and all(
            _close(s, expected_stop_price, tol=1e-4) for s in stop_candidates
        )
        if stop_candidates and not stop_consistent:
            blocked.append(GATE_STOP_PRICE_INCONSISTENT)

        # Entry reference price consistency.
        entry_ref_candidates = [
            v for v in (protection_entry_ref, lifecycle_entry_ref) if v > 0.0
        ]
        entry_ref_consistent = bool(entry_ref_candidates) and all(
            _close(v, expected_entry_reference_price, tol=1e-4)
            for v in entry_ref_candidates
        )
        if entry_ref_candidates and not entry_ref_consistent:
            blocked.append(GATE_ENTRY_REFERENCE_PRICE_INCONSISTENT)

        # Instrument category consistency.
        entry_payload_cat   = _safe_str(entry_payload_preview.get("category", "")).lower()
        stop_payload_cat    = _safe_str(stop_payload_preview.get("category", "")).lower()
        cleanup_payload_cat = _safe_str(cleanup_payload_preview.get("category", "")).lower()
        cat_candidates = [c for c in (entry_payload_cat, stop_payload_cat, cleanup_payload_cat) if c]
        cat_consistent = all(c == EXPECTED_INSTRUMENT_CATEGORY for c in cat_candidates)
        if cat_candidates and not cat_consistent:
            blocked.append(GATE_INSTRUMENT_CATEGORY_INCONSISTENT)

        # Existing position symbols consistency.
        upstream_existing_lists: list[list[str]] = []
        for src in (real_perm_dict, entry_dict, stop_dict, cleanup_dict):
            raw = src.get("existing_position_symbols")
            if isinstance(raw, list) and raw:
                upstream_existing_lists.append([_safe_str(x) for x in raw if _safe_str(x)])
        canonical_existing = sorted(existing_symbols)
        existing_consistent = all(
            sorted(lst) == canonical_existing for lst in upstream_existing_lists
        )
        if upstream_existing_lists and not existing_consistent:
            blocked.append(GATE_EXISTING_POSITION_SYMBOLS_INCONSISTENT)

        # Entry payload preview consistency.
        entry_payload_consistent = (
            entry_payload_preview.get("preview_only") is True
            and _safe_str(entry_payload_preview.get("symbol", "")) in ("", sym)
            and (
                _safe_str(entry_payload_preview.get("side", "")) in ("", EXPECTED_ENTRY_ORDER_SIDE)
            )
            and (
                _safe_str(entry_payload_preview.get("orderType", "")) in ("", EXPECTED_ORDER_TYPE)
            )
            and (
                _safe_float(entry_payload_preview.get("positionIdx", 0), -1)
                in (EXPECTED_POSITION_IDX, -1)
            )
        )
        if entry_perm_present and not entry_payload_consistent:
            blocked.append(GATE_ENTRY_PAYLOAD_PREVIEW_INCONSISTENT)

        # Stop payload preview consistency.
        stop_payload_consistent = (
            stop_payload_preview.get("preview_only") is True
            and _safe_str(stop_payload_preview.get("symbol", "")) in ("", sym)
            and (
                _safe_float(stop_payload_preview.get("positionIdx", 0), -1)
                in (EXPECTED_POSITION_IDX, -1)
            )
            and (
                _safe_str(stop_payload_preview.get("category", "")).lower()
                in ("", EXPECTED_INSTRUMENT_CATEGORY)
            )
        )
        if stop_perm_present and not stop_payload_consistent:
            blocked.append(GATE_STOP_PAYLOAD_PREVIEW_INCONSISTENT)

        # Cleanup payload preview consistency.
        cleanup_payload_consistent = (
            cleanup_payload_preview.get("preview_only") is True
            and cleanup_payload_preview.get("reduceOnly") is True
            and _safe_str(cleanup_payload_preview.get("symbol", "")) in ("", sym)
            and (
                _safe_str(cleanup_payload_preview.get("side", "")) in ("", EXPECTED_CLEANUP_SIDE)
            )
            and (
                _safe_str(cleanup_payload_preview.get("orderType", "")) in ("", EXPECTED_ORDER_TYPE)
            )
            and (
                _safe_float(cleanup_payload_preview.get("positionIdx", 0), -1)
                in (EXPECTED_POSITION_IDX, -1)
            )
        )
        if cleanup_perm_present and not cleanup_payload_consistent:
            blocked.append(GATE_CLEANUP_PAYLOAD_PREVIEW_INCONSISTENT)

        # Lifecycle recommended path consistency.
        noop_recommended_path = _safe_str(noop_dict.get("recommended_path", ""))
        if (
            noop_present
            and noop_recommended_path
            and noop_recommended_path != EXPECTED_NOOP_RECOMMENDED_PATH
        ):
            blocked.append(GATE_LIFECYCLE_RECOMMENDED_PATH_INCONSISTENT)

        # Expected endpoint path consistency.
        contract_path = _safe_str(contract_dict.get("path", ""))
        if (
            contract_present
            and contract_path
            and contract_path != TRADING_STOP_PATH_REF
        ):
            blocked.append(GATE_EXPECTED_ENDPOINT_PATH_INCONSISTENT)

        stages[STAGE_1_LIFECYCLE_PLAN_CONSISTENCY] = {
            "stage":   STAGE_1_LIFECYCLE_PLAN_CONSISTENCY,
            "summary": "Cross-artifact consistency of the lifecycle plan.",
            "selected_symbol":                              sym,
            "selected_symbol_observed_by_artifact":         dict(sym_candidates),
            "selected_symbol_consistent":                   sym_consistent,
            "entry_side_expected":                          EXPECTED_ENTRY_SIDE,
            "entry_side_observed":                          entry_side_observed_candidates,
            "entry_side_consistent":                        entry_side_consistent,
            "cleanup_side_expected":                        EXPECTED_CLEANUP_SIDE,
            "cleanup_side_observed":                        cleanup_side_candidates,
            "cleanup_side_consistent":                      cleanup_side_consistent,
            "expected_tiny_qty":                            expected_tiny_qty,
            "tiny_qty_observed":                            qty_candidates,
            "tiny_qty_consistent":                          qty_consistent,
            "expected_stop_price":                          expected_stop_price,
            "stop_price_observed":                          stop_candidates,
            "stop_price_consistent":                        stop_consistent,
            "expected_entry_reference_price":               expected_entry_reference_price,
            "entry_reference_price_observed":               entry_ref_candidates,
            "entry_reference_price_consistent":             entry_ref_consistent,
            "expected_instrument_category":                 EXPECTED_INSTRUMENT_CATEGORY,
            "instrument_category_observed":                 cat_candidates,
            "instrument_category_consistent":               cat_consistent,
            "existing_position_symbols_canonical":          canonical_existing,
            "existing_position_symbols_upstream":           upstream_existing_lists,
            "existing_position_symbols_consistent":         existing_consistent,
            "entry_payload_preview":                        entry_payload_preview,
            "entry_payload_preview_consistent":             entry_payload_consistent,
            "stop_payload_preview":                         stop_payload_preview,
            "stop_payload_preview_consistent":              stop_payload_consistent,
            "cleanup_payload_preview":                      cleanup_payload_preview,
            "cleanup_payload_preview_consistent":           cleanup_payload_consistent,
            "noop_recommended_path_observed":               noop_recommended_path,
            "noop_recommended_path_expected":               EXPECTED_NOOP_RECOMMENDED_PATH,
            "contract_path_observed":                       contract_path,
            "trading_stop_path_ref":                        TRADING_STOP_PATH_REF,
            "order_create_path_ref":                        ORDER_CREATE_PATH_REF,
        }

        # ===============================================================
        # stage_2_existing_position_safety_review
        # ===============================================================
        snapshot_fields_ok = all(
            all(k in row for k in ("symbol", "side", "qty", "entry", "stop"))
            for row in existing_snapshot
        )
        stages[STAGE_2_EXISTING_POSITION_SAFETY_REVIEW] = {
            "stage":   STAGE_2_EXISTING_POSITION_SAFETY_REVIEW,
            "summary": "Safety review of 5 existing demo shorts.",
            "existing_position_count":           len(existing_snapshot),
            "existing_positions_snapshot":       existing_snapshot,
            "snapshot_fields_ok":                snapshot_fields_ok,
            "selected_symbol":                   sym,
            "selected_symbol_disjoint":          bool(sym) and (sym not in existing_symbols),
            "post_run_stop_match_required":      True,
            "mismatch_action":                   "fail_closed_manual_review",
            "existing_positions_touched":        [],
        }

        # ===============================================================
        # stage_3_execution_sequence_review
        # ===============================================================
        execution_sequence_plan: dict[str, Any] = {
            "step_count":                len(REAL_LIFECYCLE_STEPS),
            "steps":                     list(REAL_LIFECYCLE_STEPS),
            "preview_only":              True,
            "order_endpoint_called":     False,
            "stop_endpoint_called":      False,
            "real_lifecycle_runner_implemented": False,
            "real_execution_allowed":    False,
            "manual_approval_per_real_step": {
                "real_tiny_entry":  "entry_token_required",
                "real_stop_attach": "stop_attach_token_required",
                "real_cleanup":     "cleanup_token_required",
            },
            "readonly_between_real_steps_required": True,
            "no_skipping_allowed":       True,
            "no_reordering_allowed":     True,
            "no_parallel_execution":     True,
            "step_payload_refs": {
                "real_tiny_entry":  entry_payload_preview,
                "real_stop_attach": stop_payload_preview,
                "real_cleanup":     cleanup_payload_preview,
            },
            "step_endpoint_refs": {
                "real_tiny_entry":  ORDER_CREATE_PATH_REF,
                "real_stop_attach": TRADING_STOP_PATH_REF,
                "real_cleanup":     ORDER_CREATE_PATH_REF,
            },
            "no_endpoint_invoked_in_this_task": True,
        }
        stages[STAGE_3_EXECUTION_SEQUENCE_REVIEW] = {
            "stage":   STAGE_3_EXECUTION_SEQUENCE_REVIEW,
            "summary": "Document the fixed 8-step real-lifecycle sequence (preview-only).",
            "execution_sequence_plan":         execution_sequence_plan,
        }

        # ===============================================================
        # stage_4_manual_approval_matrix
        # ===============================================================
        manual_approval_matrix: dict[str, Any] = {
            "entry_token_pattern":                       ENTRY_TOKEN_PATTERN,
            "stop_attach_token_pattern":                 STOP_ATTACH_TOKEN_PATTERN,
            "cleanup_token_pattern":                     CLEANUP_TOKEN_PATTERN,
            "tokens_must_be_distinct_per_step":          True,
            "tokens_validated_in_this_task":             False,
            "approval_required_per_real_step":           True,
            "real_lifecycle_runner_not_yet_designed":    True,
            "approval_steps_to_token_pattern": {
                "real_tiny_entry":  ENTRY_TOKEN_PATTERN,
                "real_stop_attach": STOP_ATTACH_TOKEN_PATTERN,
                "real_cleanup":     CLEANUP_TOKEN_PATTERN,
            },
        }
        stages[STAGE_4_MANUAL_APPROVAL_MATRIX] = {
            "stage":   STAGE_4_MANUAL_APPROVAL_MATRIX,
            "summary": "Document the 3 distinct manual approval tokens (never validated here).",
            "manual_approval_matrix":                    manual_approval_matrix,
        }
        # Always-on documentation gates.
        blocked.append(GATE_ENTRY_TOKEN_PATTERN_REQUIRED)
        blocked.append(GATE_STOP_ATTACH_TOKEN_PATTERN_REQUIRED)
        blocked.append(GATE_CLEANUP_TOKEN_PATTERN_REQUIRED)
        blocked.append(GATE_TOKENS_MUST_BE_DISTINCT_PER_STEP)
        blocked.append(GATE_NO_TOKEN_VALIDATED_IN_THIS_TASK)
        blocked.append(GATE_MANUAL_APPROVAL_REQUIRED_PER_STAGE)
        blocked.append(GATE_REAL_LIFECYCLE_RUNNER_NOT_YET_DESIGNED)

        # ===============================================================
        # stage_5_failure_response_matrix
        # ===============================================================
        failure_response_matrix: dict[str, Any] = {
            "entry_rejected":                            "fail_closed",
            "stop_attach_rejected":                      "fail_closed",
            "cleanup_rejected":                          "fail_closed",
            "entry_partial_fill":                        "fail_closed",
            "cleanup_partial_fill":                      "fail_closed",
            "readonly_unavailable_between_steps":        "fail_closed",
            "tiny_position_still_open_after_cleanup":    "fail_closed",
            "existing_stop_mismatch":                    "manual_review",
            "unexpected_position_appears":               "manual_review",
            "no_automatic_retry_after_any_failure":      True,
            "no_real_emergency_close_in_this_task":      True,
            "expected_existing_position_symbols":        list(EXISTING_POSITION_SYMBOLS),
        }
        stages[STAGE_5_FAILURE_RESPONSE_MATRIX] = {
            "stage":   STAGE_5_FAILURE_RESPONSE_MATRIX,
            "summary": "Document the failure-response matrix for the real lifecycle.",
            "failure_response_matrix":                   failure_response_matrix,
        }
        # Always-on documentation gates.
        blocked.append(GATE_ENTRY_REJECTED_FAIL_CLOSED)
        blocked.append(GATE_STOP_ATTACH_REJECTED_FAIL_CLOSED)
        blocked.append(GATE_CLEANUP_REJECTED_FAIL_CLOSED)
        blocked.append(GATE_ENTRY_PARTIAL_FILL_FAIL_CLOSED)
        blocked.append(GATE_CLEANUP_PARTIAL_FILL_FAIL_CLOSED)
        blocked.append(GATE_READONLY_UNAVAILABLE_BETWEEN_STEPS_FAIL_CLOSED)
        blocked.append(GATE_TINY_POSITION_STILL_OPEN_AFTER_CLEANUP_FAIL_CLOSED)
        blocked.append(GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW)
        blocked.append(GATE_UNEXPECTED_POSITION_APPEARS_MANUAL_REVIEW)
        blocked.append(GATE_NO_AUTO_RETRY_AFTER_ANY_FAILURE)
        blocked.append(GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK)

        # ===============================================================
        # stage_6_final_readiness_verdict
        # ===============================================================
        blocked.append(GATE_REAL_LIFECYCLE_EXECUTION_NOT_IMPL)
        blocked.append(GATE_NO_REAL_ORDER_ENDPOINT)
        blocked.append(GATE_NO_REAL_STOP_ENDPOINT)
        blocked.append(GATE_NO_POSITION_MODIFIED)
        blocked.append(GATE_G20_NOT_LIFTED)
        blocked.append(GATE_G20_POLICY_STILL_IN_PLACE)
        blocked.append(GATE_NO_SECRETS_EMITTED)

        # ===============================================================
        # Status resolution
        # ===============================================================
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
        elif allow_real_lifecycle_summary:
            failed_stage = ""
            status_out = STATUS_SUMMARY_READY_EXEC_DISABLED
            mode_out   = MODE_REAL_LIFECYCLE_SUMMARY_DRY_RUN
        else:
            failed_stage = ""
            status_out = STATUS_SUMMARY_READY
            mode_out   = MODE_CHECKLIST

        stages[STAGE_6_FINAL_READINESS_VERDICT] = {
            "stage":   STAGE_6_FINAL_READINESS_VERDICT,
            "summary": "Final readiness verdict + permanent execution guard.",
            "real_lifecycle_summary_dry_run_allowed":    allow_real_lifecycle_summary,
            "real_lifecycle_execution_requested":        bool(allow_real_lifecycle_execution),
            "real_execution_allowed":                    False,
            "real_lifecycle_runner_implemented":         False,
            "current_task_real_execution_allowed":       False,
            "g20_policy_still_in_place":                 True,
            "g20_lifted":                                False,
            "no_real_order_endpoint":                    True,
            "no_real_stop_endpoint":                     True,
            "no_position_modified":                      True,
            "no_live_endpoint":                          True,
            "no_secrets_emitted":                        True,
            "status":                                    status_out,
            "mode":                                      mode_out,
            "next_required_task":                        (
                "TASK-014AB_tiny_lifecycle_real_execution_runner_design_or_manual_approval"
            ),
        }

        return TinyLifecycleRealExecutionSummaryResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            entry_side=EXPECTED_ENTRY_SIDE,
            entry_order_side=EXPECTED_ENTRY_ORDER_SIDE,
            cleanup_side=EXPECTED_CLEANUP_SIDE,
            expected_tiny_qty=expected_tiny_qty,
            expected_stop_price=expected_stop_price,
            expected_entry_reference_price=expected_entry_reference_price,
            expected_instrument_category=EXPECTED_INSTRUMENT_CATEGORY,
            expected_lifecycle_recommended_path=EXPECTED_NOOP_RECOMMENDED_PATH,
            entry_payload_preview=entry_payload_preview,
            stop_payload_preview=stop_payload_preview,
            cleanup_payload_preview=cleanup_payload_preview,
            execution_sequence_plan=execution_sequence_plan,
            manual_approval_matrix=manual_approval_matrix,
            failure_response_matrix=failure_response_matrix,
            existing_positions_snapshot=existing_snapshot,
            real_lifecycle_summary_dry_run_allowed=allow_real_lifecycle_summary,
            real_lifecycle_execution_requested=bool(allow_real_lifecycle_execution),
            real_execution_allowed=False,
            real_lifecycle_runner_implemented=False,
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
            existing_position_stop_snapshot_match=True,
            existing_positions_touched=[],
            upstream_real_permission_status=real_perm_status,
            upstream_tiny_entry_permission_status=entry_perm_status,
            upstream_tiny_stop_attach_permission_status=stop_perm_status,
            upstream_tiny_cleanup_permission_status=cleanup_perm_status,
            blocked_gates=unique,
            failed_stage=failed_stage,
            status=status_out,
        )

    # ----------------------------------------------------------------- util
    @staticmethod
    def _extract_payload(src: dict[str, Any], key: str) -> dict[str, Any]:
        """Pull a payload-preview dict from an upstream gate artifact."""
        if not isinstance(src, dict):
            return {}
        # Top-level first.
        val = src.get(key)
        if isinstance(val, dict):
            return dict(val)
        # Look in stages dict for the matching field.
        stages = src.get("stages")
        if isinstance(stages, dict):
            for stage_env in stages.values():
                if isinstance(stage_env, dict):
                    nested = stage_env.get(key)
                    if isinstance(nested, dict):
                        return dict(nested)
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
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_LIFECYCLE_MOCK_NOT_SUCCESS,
            GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE,
            GATE_TINY_ENTRY_PERMISSION_GATE_STATUS_UNACCEPTABLE,
            GATE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUS_UNACCEPTABLE,
            GATE_TINY_CLEANUP_PERMISSION_GATE_STATUS_UNACCEPTABLE,
            GATE_SELECTED_SYMBOL_MISSING,
            GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
        }
        for g in blocked:
            if g in stage_0_set:
                return STAGE_0_ARTIFACT_PREFLIGHT
        stage_1_set = {
            GATE_SELECTED_SYMBOL_INCONSISTENT,
            GATE_ENTRY_SIDE_INCONSISTENT,
            GATE_CLEANUP_SIDE_INCONSISTENT,
            GATE_TINY_QTY_INCONSISTENT,
            GATE_STOP_PRICE_INCONSISTENT,
            GATE_ENTRY_REFERENCE_PRICE_INCONSISTENT,
            GATE_INSTRUMENT_CATEGORY_INCONSISTENT,
            GATE_EXISTING_POSITION_SYMBOLS_INCONSISTENT,
            GATE_ENTRY_PAYLOAD_PREVIEW_INCONSISTENT,
            GATE_STOP_PAYLOAD_PREVIEW_INCONSISTENT,
            GATE_CLEANUP_PAYLOAD_PREVIEW_INCONSISTENT,
            GATE_LIFECYCLE_RECOMMENDED_PATH_INCONSISTENT,
            GATE_EXPECTED_ENDPOINT_PATH_INCONSISTENT,
        }
        for g in blocked:
            if g in stage_1_set:
                return STAGE_1_LIFECYCLE_PLAN_CONSISTENCY
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
    "ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES",
    "ACCEPTABLE_TINY_ENTRY_PERMISSION_GATE_STATUSES",
    "ACCEPTABLE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUSES",
    "ACCEPTABLE_TINY_CLEANUP_PERMISSION_GATE_STATUSES",
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_NOOP_RECOMMENDED_PATH",
    "EXPECTED_LIFECYCLE_STATUS",
    "EXPECTED_INSTRUMENT_CATEGORY",
    "EXPECTED_ENTRY_SIDE",
    "EXPECTED_CLEANUP_SIDE",
    "EXPECTED_ENTRY_ORDER_SIDE",
    "EXPECTED_ORDER_TYPE",
    "EXPECTED_POSITION_IDX",
    "REAL_LIFECYCLE_STEPS",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_LIFECYCLE_PLAN_CONSISTENCY",
    "STAGE_2_EXISTING_POSITION_SAFETY_REVIEW",
    "STAGE_3_EXECUTION_SEQUENCE_REVIEW",
    "STAGE_4_MANUAL_APPROVAL_MATRIX",
    "STAGE_5_FAILURE_RESPONSE_MATRIX",
    "STAGE_6_FINAL_READINESS_VERDICT",
    "ALL_STAGES",
    "STATUS_SUMMARY_READY",
    "STATUS_SUMMARY_READY_EXEC_DISABLED",
    "STATUS_REAL_LIFECYCLE_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_CHECKLIST",
    "MODE_REAL_LIFECYCLE_SUMMARY_DRY_RUN",
    "MODE_REAL_LIFECYCLE_EXECUTION_GUARD",
    "MODE_FAIL_CLOSED",
    # general gates (23)
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
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_MISSING",
    "GATE_SELECTED_SYMBOL_COLLIDES_EXISTING",
    "GATE_LIFECYCLE_MOCK_NOT_SUCCESS",
    "GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE",
    "GATE_TINY_ENTRY_PERMISSION_GATE_STATUS_UNACCEPTABLE",
    "GATE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUS_UNACCEPTABLE",
    "GATE_TINY_CLEANUP_PERMISSION_GATE_STATUS_UNACCEPTABLE",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_SECRETS_EMITTED",
    # consistency gates (13)
    "GATE_SELECTED_SYMBOL_INCONSISTENT",
    "GATE_ENTRY_SIDE_INCONSISTENT",
    "GATE_CLEANUP_SIDE_INCONSISTENT",
    "GATE_TINY_QTY_INCONSISTENT",
    "GATE_STOP_PRICE_INCONSISTENT",
    "GATE_ENTRY_REFERENCE_PRICE_INCONSISTENT",
    "GATE_INSTRUMENT_CATEGORY_INCONSISTENT",
    "GATE_EXISTING_POSITION_SYMBOLS_INCONSISTENT",
    "GATE_ENTRY_PAYLOAD_PREVIEW_INCONSISTENT",
    "GATE_STOP_PAYLOAD_PREVIEW_INCONSISTENT",
    "GATE_CLEANUP_PAYLOAD_PREVIEW_INCONSISTENT",
    "GATE_LIFECYCLE_RECOMMENDED_PATH_INCONSISTENT",
    "GATE_EXPECTED_ENDPOINT_PATH_INCONSISTENT",
    # manual approval gates (7)
    "GATE_ENTRY_TOKEN_PATTERN_REQUIRED",
    "GATE_STOP_ATTACH_TOKEN_PATTERN_REQUIRED",
    "GATE_CLEANUP_TOKEN_PATTERN_REQUIRED",
    "GATE_TOKENS_MUST_BE_DISTINCT_PER_STEP",
    "GATE_NO_TOKEN_VALIDATED_IN_THIS_TASK",
    "GATE_MANUAL_APPROVAL_REQUIRED_PER_STAGE",
    "GATE_REAL_LIFECYCLE_RUNNER_NOT_YET_DESIGNED",
    # failure gates (11)
    "GATE_ENTRY_REJECTED_FAIL_CLOSED",
    "GATE_STOP_ATTACH_REJECTED_FAIL_CLOSED",
    "GATE_CLEANUP_REJECTED_FAIL_CLOSED",
    "GATE_ENTRY_PARTIAL_FILL_FAIL_CLOSED",
    "GATE_CLEANUP_PARTIAL_FILL_FAIL_CLOSED",
    "GATE_READONLY_UNAVAILABLE_BETWEEN_STEPS_FAIL_CLOSED",
    "GATE_TINY_POSITION_STILL_OPEN_AFTER_CLEANUP_FAIL_CLOSED",
    "GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW",
    "GATE_UNEXPECTED_POSITION_APPEARS_MANUAL_REVIEW",
    "GATE_NO_AUTO_RETRY_AFTER_ANY_FAILURE",
    "GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK",
    # execution guard gates (5)
    "GATE_REAL_LIFECYCLE_EXECUTION_NOT_IMPL",
    "GATE_NO_REAL_ORDER_ENDPOINT",
    "GATE_NO_REAL_STOP_ENDPOINT",
    "GATE_NO_POSITION_MODIFIED",
    "GATE_G20_NOT_LIFTED",
    "TinyLifecycleRealExecutionSummaryResult",
    "DemoTinyLifecycleRealExecutionSummary",
]
