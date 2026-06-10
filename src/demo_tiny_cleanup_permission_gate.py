"""
src/demo_tiny_cleanup_permission_gate.py
TASK-014Z: Tiny Isolated Demo Cleanup Permission Gate / Dry-run Only.

Pure-computation / mock-safe permission gate for the future real
cleanup (close-only) of the (hypothetical) tiny SOLUSDT long opened
by TASK-014X and stopped by TASK-014Y.  Produces a checklist + a
preview-only cleanup close-only payload that documents what must be
in place before a future real cleanup could execute.

This module does NOT execute anything: no /v5/order/create,
no /v5/position/trading-stop, no close-only, no emergency close,
no leverage mutation, no transfers.

Stages:

  stage_0_artifact_preflight
      Validate 9 upstream artifacts (readonly_smoke / reconciliation /
      protection / contract / noop_plan / lifecycle_mock /
      tiny_position_real_permission_gate / tiny_entry_permission_gate /
      tiny_stop_attach_permission_gate) plus the runtime proof
      envelope.

  stage_1_existing_position_pre_snapshot
      Snapshot the 5 existing demo shorts.  Selected symbol must be
      disjoint from existing position symbols.  existing_positions_touched
      must remain [].

  stage_2_cleanup_payload_preview
      Derive expected_tiny_qty (from entry permission gate
      rounded_tiny_qty + lifecycle mock tiny_qty), verify
      expected_tiny_qty > 0, and build the preview-only close-only
      payload: category=linear, symbol=SOLUSDT, side=Sell,
      orderType=Market, qty=<expected_tiny_qty>, reduceOnly=True,
      positionIdx=0, orderLinkId=DRYRUN-TINY-CLEANUP-...  No socket
      opened.

  stage_3_cleanup_token_checklist
      Document the cleanup confirmation token pattern.  Token is
      NEVER validated in this task.  Entry / stop-attach tokens are
      NOT accepted in this task.

  stage_4_post_cleanup_required_verification_plan
      Document the readonly verification checklist that MUST follow
      a future real cleanup: SOLUSDT position absent or qty=0,
      no dangling tiny position, existing 5 shorts still present,
      existing 5 stops unchanged, no new unexpected position.

  stage_5_failure_response_plan
      Document the failure-response plan: cleanup rejected,
      partial fill, readonly unavailable, SOLUSDT still open,
      existing stop mismatch, unexpected position appears.

  stage_6_execution_guard
      Permanent guard: real_execution_allowed=False,
      real_cleanup_implemented=False.  Even with --allow-real-cleanup,
      returns REAL_CLEANUP_NOT_IMPLEMENTED with no socket opened.

Modes:
  checklist                      --- default
  real_cleanup_permission_dry_run --- with --allow-real-cleanup-permission
  real_cleanup_guard             --- with --allow-real-cleanup
  fail_closed                    --- upstream / risk validation failed

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

STAGE_0_ARTIFACT_PREFLIGHT                       = "stage_0_artifact_preflight"
STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT           = "stage_1_existing_position_pre_snapshot"
STAGE_2_CLEANUP_PAYLOAD_PREVIEW                  = "stage_2_cleanup_payload_preview"
STAGE_3_CLEANUP_TOKEN_CHECKLIST                  = "stage_3_cleanup_token_checklist"
STAGE_4_POST_CLEANUP_REQUIRED_VERIFICATION_PLAN  = (
    "stage_4_post_cleanup_required_verification_plan"
)
STAGE_5_FAILURE_RESPONSE_PLAN                    = "stage_5_failure_response_plan"
STAGE_6_EXECUTION_GUARD                          = "stage_6_execution_guard"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT,
    STAGE_2_CLEANUP_PAYLOAD_PREVIEW,
    STAGE_3_CLEANUP_TOKEN_CHECKLIST,
    STAGE_4_POST_CLEANUP_REQUIRED_VERIFICATION_PLAN,
    STAGE_5_FAILURE_RESPONSE_PLAN,
    STAGE_6_EXECUTION_GUARD,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_CHECKLIST_READY                = "TINY_CLEANUP_PERMISSION_CHECKLIST_READY"
STATUS_PERMISSION_READY_EXEC_DISABLED = (
    "TINY_CLEANUP_PERMISSION_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_CLEANUP_NOT_IMPL          = "REAL_CLEANUP_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                    = "FAIL_CLOSED"

MODE_CHECKLIST                        = "checklist"
MODE_REAL_CLEANUP_PERMISSION_DRY_RUN  = "real_cleanup_permission_dry_run"
MODE_REAL_CLEANUP_GUARD               = "real_cleanup_guard"
MODE_FAIL_CLOSED                      = "fail_closed"


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
EXPECTED_ORDER_TYPE              = "Market"
EXPECTED_POSITION_IDX            = 0


# ---------------------------------------------------------------------------
# Gate constants  (22 general + 13 cleanup payload + 6 manual approval +
#                  7 failure + 5 execution guard = 53)
# ---------------------------------------------------------------------------

# General gates
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
GATE_G20_POLICY_STILL_IN_PLACE               = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                        = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                      = "no_secret_values_emitted_in_this_task"

# Cleanup payload gates
GATE_EXPECTED_TINY_QTY_MISSING               = "expected_tiny_qty_missing"
GATE_EXPECTED_TINY_QTY_NOT_POSITIVE          = "expected_tiny_qty_not_positive"
GATE_EXPECTED_TINY_QTY_MISMATCH_ENTRY_GATE   = (
    "expected_tiny_qty_mismatch_with_entry_permission_rounded_tiny_qty"
)
GATE_CLEANUP_SIDE_NOT_SELL_FOR_LONG          = "cleanup_side_not_sell_for_long"
GATE_CLEANUP_CATEGORY_NOT_LINEAR             = "cleanup_category_not_linear"
GATE_CLEANUP_SYMBOL_MISMATCH                 = "cleanup_symbol_mismatch"
GATE_CLEANUP_ORDER_TYPE_NOT_MARKET           = "cleanup_order_type_not_market"
GATE_CLEANUP_REDUCE_ONLY_NOT_TRUE            = "cleanup_reduce_only_not_true"
GATE_CLEANUP_POSITION_IDX_NOT_ZERO           = "cleanup_position_idx_not_zero"
GATE_CLEANUP_PAYLOAD_NOT_PREVIEW_ONLY        = "cleanup_payload_not_preview_only"
GATE_CLEANUP_ORDER_LINK_ID_NOT_DRYRUN        = "cleanup_order_link_id_not_dryrun"
GATE_CLEANUP_ORDER_ENDPOINT_CALLED           = "cleanup_order_endpoint_called_forbidden_in_this_task"
GATE_CLEANUP_POSITION_MODIFIED               = "cleanup_position_modified_forbidden_in_this_task"

# Manual approval gates
GATE_CLEANUP_TOKEN_PATTERN_REQUIRED          = "cleanup_token_pattern_required_in_future_task"
GATE_CLEANUP_TOKEN_NOT_VALIDATED_THIS_TASK   = "cleanup_token_not_validated_in_this_task"
GATE_ENTRY_TOKEN_NOT_ACCEPTED_THIS_TASK      = "entry_token_not_accepted_in_this_task"
GATE_STOP_ATTACH_TOKEN_NOT_ACCEPTED_THIS_TASK = "stop_attach_token_not_accepted_in_this_task"
GATE_POST_CLEANUP_READONLY_VERIFICATION_REQUIRED = (
    "post_cleanup_readonly_verification_required"
)
GATE_NO_AUTO_RETRY_AFTER_CLEANUP_FAIL        = "no_automatic_retry_after_cleanup_failure"

# Failure gates
GATE_READONLY_UNAVAILABLE_AFTER_CLEANUP_FAIL_CLOSED = (
    "readonly_unavailable_after_cleanup_fail_closed"
)
GATE_CLEANUP_REJECTED_FAIL_CLOSED            = "cleanup_order_rejected_fail_closed"
GATE_CLEANUP_PARTIAL_FILL_FAIL_CLOSED        = "cleanup_partial_fill_fail_closed"
GATE_SOLUSDT_STILL_OPEN_AFTER_CLEANUP_FAIL_CLOSED = (
    "tiny_position_still_open_after_cleanup_fail_closed"
)
GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW    = "existing_stop_mismatch_manual_review_required"
GATE_UNEXPECTED_POSITION_APPEARS_MANUAL_REVIEW = (
    "unexpected_position_appears_after_cleanup_manual_review_required"
)
GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK       = "no_real_emergency_close_in_this_task"

# Execution guard gates
GATE_REAL_CLEANUP_NOT_IMPL                   = "real_cleanup_not_implemented"
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
    GATE_EXPECTED_TINY_QTY_MISSING,
    GATE_EXPECTED_TINY_QTY_NOT_POSITIVE,
    GATE_EXPECTED_TINY_QTY_MISMATCH_ENTRY_GATE,
    GATE_CLEANUP_SIDE_NOT_SELL_FOR_LONG,
    GATE_CLEANUP_SYMBOL_MISMATCH,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyCleanupPermissionGateResult:
    """Read-only outcome of one tiny-cleanup permission-gate pass."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    # Cleanup inputs.
    expected_tiny_qty:            float = 0.0
    entry_rounded_tiny_qty:       float = 0.0
    lifecycle_tiny_qty:           float = 0.0
    cleanup_side:                 str   = EXPECTED_CLEANUP_SIDE
    entry_side:                   str   = EXPECTED_ENTRY_SIDE

    # Preview-only cleanup close-only payload (NEVER sent).
    cleanup_payload_preview:      dict[str, Any] = field(default_factory=dict)

    # Token patterns (documented only).
    entry_token_pattern:          str = ENTRY_TOKEN_PATTERN
    stop_attach_token_pattern:    str = STOP_ATTACH_TOKEN_PATTERN
    cleanup_token_pattern:        str = CLEANUP_TOKEN_PATTERN

    # Post-cleanup verification + failure plans.
    post_cleanup_verification_plan: dict[str, Any] = field(default_factory=dict)
    failure_response_plan:        dict[str, Any] = field(default_factory=dict)

    existing_positions_snapshot:  list[dict[str, Any]] = field(default_factory=list)

    # Real-execution gating flags (TASK-014Z keeps all of these conservative).
    real_cleanup_permission_dry_run_allowed: bool = False
    real_execution_allowed:       bool = False
    real_cleanup_implemented:     bool = False
    current_task_real_execution_allowed: bool = False
    real_cleanup_requested:       bool = False

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

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = (
        "TASK-014AA_tiny_lifecycle_real_execution_permission_summary"
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
            "expected_tiny_qty":          self.expected_tiny_qty,
            "entry_rounded_tiny_qty":     self.entry_rounded_tiny_qty,
            "lifecycle_tiny_qty":         self.lifecycle_tiny_qty,
            "cleanup_side":               self.cleanup_side,
            "entry_side":                 self.entry_side,
            "cleanup_payload_preview":    dict(self.cleanup_payload_preview),
            "entry_token_pattern":        self.entry_token_pattern,
            "stop_attach_token_pattern":  self.stop_attach_token_pattern,
            "cleanup_token_pattern":      self.cleanup_token_pattern,
            "post_cleanup_verification_plan": dict(self.post_cleanup_verification_plan),
            "failure_response_plan":      dict(self.failure_response_plan),
            "existing_positions_snapshot": [dict(row) for row in self.existing_positions_snapshot],
            "real_cleanup_permission_dry_run_allowed": self.real_cleanup_permission_dry_run_allowed,
            "real_execution_allowed":     self.real_execution_allowed,
            "real_cleanup_implemented":   self.real_cleanup_implemented,
            "current_task_real_execution_allowed": self.current_task_real_execution_allowed,
            "real_cleanup_requested":     self.real_cleanup_requested,
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


_DRYRUN_LINK_ID_PREFIX = "DRYRUN-TINY-CLEANUP"


def _build_order_link_id(symbol: str, ts_utc: str) -> str:
    ts_compact = (
        ts_utc
        .replace("-", "")
        .replace(":", "")
        .replace("T", "")
        .replace("Z", "")
    )
    sym = (symbol or "").strip().upper() or "UNKNOWN"
    return f"{_DRYRUN_LINK_ID_PREFIX}-{sym}-{ts_compact}"


def _qty_close_enough(a: float, b: float, tol: float = 1e-9) -> bool:
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


# ---------------------------------------------------------------------------
# Permission gate
# ---------------------------------------------------------------------------

class DemoTinyCleanupPermissionGate:
    """
    Pure-computation permission gate for the future real tiny cleanup
    (close-only) of the hypothetical SOLUSDT long.

    Reads 9 upstream JSON artifacts and emits a
    TinyCleanupPermissionGateResult.  Holds no network client, reads
    no environment variables, and NEVER invokes the order-create or
    trading-stop endpoints.

    --allow-real-cleanup-permission  --> status promoted to
        TINY_CLEANUP_PERMISSION_READY_BUT_EXECUTION_DISABLED
        (no execution; checklist only).

    --allow-real-cleanup             --> status fixed to
        REAL_CLEANUP_NOT_IMPLEMENTED  (no socket opened).
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
        symbol:                           str  = DEFAULT_SELECTED_SYMBOL,
        allow_real_cleanup_permission:    bool = False,
        allow_real_cleanup:               bool = False,
        _now:                             datetime | None = None,
    ) -> TinyCleanupPermissionGateResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_cleanup:
            mode = MODE_REAL_CLEANUP_GUARD
        elif allow_real_cleanup_permission:
            mode = MODE_REAL_CLEANUP_PERMISSION_DRY_RUN
        else:
            mode = MODE_CHECKLIST

        blocked: list[str] = []
        stages:  dict[str, dict[str, Any]] = {}

        # ===============================================================
        # stage_0_artifact_preflight
        # ===============================================================
        sym = (symbol or "").strip()
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

        endpoint_family = str(((readonly_smoke or {}).get(
            "endpoint_family", "")) or "").strip()
        account_mode    = str(((readonly_smoke or {}).get(
            "account_mode", "")) or "").strip()
        proof_strength  = str(((readonly_smoke or {}).get(
            "proof_strength", "")) or "").strip()
        position_details_source = str(((reconciliation or {}).get(
            "position_details_source",
            (reconciliation or {}).get("mode", ""))) or "").strip()
        lifecycle_status = str(((lifecycle_mock or {}).get(
            "status", "")) or "").strip()
        real_perm_status = str(((real_permission_gate or {}).get(
            "status", "")) or "").strip()
        entry_perm_status = str(((tiny_entry_permission_gate or {}).get(
            "status", "")) or "").strip()
        stop_perm_status = str(((tiny_stop_attach_permission_gate or {}).get(
            "status", "")) or "").strip()

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

        if not sym:
            blocked.append(GATE_SELECTED_SYMBOL_MISSING)
        elif sym in existing_symbols:
            blocked.append(GATE_SELECTED_SYMBOL_COLLIDES_EXISTING)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 9 upstream artifacts + runtime proof envelope.",
            "readonly_smoke_present":            readonly_present,
            "reconciliation_present":            recon_present,
            "protection_present":                protection_present,
            "contract_present":                  contract_present,
            "noop_plan_present":                 noop_present,
            "lifecycle_mock_present":            lifecycle_present,
            "real_permission_gate_present":      real_perm_present,
            "tiny_entry_permission_gate_present": entry_perm_present,
            "tiny_stop_attach_permission_gate_present": stop_perm_present,
            "endpoint_family_observed":          endpoint_family,
            "endpoint_family_expected":          EXPECTED_ENDPOINT_FAMILY,
            "account_mode_observed":             account_mode,
            "account_mode_expected":             EXPECTED_ACCOUNT_MODE,
            "proof_strength_observed":           proof_strength,
            "proof_strength_expected":           EXPECTED_PROOF_STRENGTH,
            "position_details_source_observed":  position_details_source,
            "position_details_source_expected":  EXPECTED_POSITION_DETAILS_SOURCE,
            "lifecycle_status_observed":         lifecycle_status,
            "lifecycle_status_expected":         EXPECTED_LIFECYCLE_STATUS,
            "real_permission_gate_status_observed": real_perm_status,
            "real_permission_gate_status_acceptable": sorted(
                ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES
            ),
            "tiny_entry_permission_gate_status_observed": entry_perm_status,
            "tiny_entry_permission_gate_status_acceptable": sorted(
                ACCEPTABLE_TINY_ENTRY_PERMISSION_GATE_STATUSES
            ),
            "tiny_stop_attach_permission_gate_status_observed": stop_perm_status,
            "tiny_stop_attach_permission_gate_status_acceptable": sorted(
                ACCEPTABLE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUSES
            ),
            "selected_symbol":                   sym,
            "current_task_real_execution_allowed": False,
        }

        # ===============================================================
        # stage_1_existing_position_pre_snapshot
        # ===============================================================
        snapshot_fields_ok = all(
            all(k in row for k in ("symbol", "side", "qty", "entry", "stop"))
            for row in existing_snapshot
        )
        stages[STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT] = {
            "stage":   STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT,
            "summary": "Pre-snapshot 5 existing demo shorts + verify selected disjoint.",
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
        # stage_2_cleanup_payload_preview
        # ===============================================================
        entry_rounded_tiny_qty = _safe_float(
            (tiny_entry_permission_gate or {}).get("rounded_tiny_qty", 0.0), 0.0,
        )
        lifecycle_tiny_qty = _safe_float(
            (lifecycle_mock or {}).get("tiny_qty", 0.0), 0.0,
        )

        # expected_tiny_qty derives from entry permission gate when present,
        # otherwise the lifecycle mock.  Both should agree.
        if entry_rounded_tiny_qty > 0.0:
            expected_tiny_qty = entry_rounded_tiny_qty
        else:
            expected_tiny_qty = lifecycle_tiny_qty

        if expected_tiny_qty <= 0.0 and entry_rounded_tiny_qty == 0.0 and lifecycle_tiny_qty == 0.0:
            blocked.append(GATE_EXPECTED_TINY_QTY_MISSING)
        elif expected_tiny_qty <= 0.0:
            blocked.append(GATE_EXPECTED_TINY_QTY_NOT_POSITIVE)

        if (
            entry_rounded_tiny_qty > 0.0
            and lifecycle_tiny_qty > 0.0
            and not _qty_close_enough(entry_rounded_tiny_qty, lifecycle_tiny_qty)
        ):
            blocked.append(GATE_EXPECTED_TINY_QTY_MISMATCH_ENTRY_GATE)

        order_link_id = _build_order_link_id(sym, ts_utc)

        cleanup_payload_preview: dict[str, Any] = {
            "preview_only":       True,
            "category":           EXPECTED_INSTRUMENT_CATEGORY,
            "symbol":             sym,
            "side":               EXPECTED_CLEANUP_SIDE,
            "orderType":          EXPECTED_ORDER_TYPE,
            "qty":                expected_tiny_qty,
            "reduceOnly":         True,
            "closeOnTrigger":     False,
            "positionIdx":        EXPECTED_POSITION_IDX,
            "orderLinkId":        order_link_id,
            "endpoint_path_ref":  ORDER_CREATE_PATH_REF,
            "endpoint_called":    False,
        }

        # Self-check on the preview payload (defense in depth).
        if cleanup_payload_preview.get("preview_only") is not True:
            blocked.append(GATE_CLEANUP_PAYLOAD_NOT_PREVIEW_ONLY)
        if str(cleanup_payload_preview.get("category", "")).strip().lower() != EXPECTED_INSTRUMENT_CATEGORY:
            blocked.append(GATE_CLEANUP_CATEGORY_NOT_LINEAR)
        if str(cleanup_payload_preview.get("symbol", "")).strip() != sym:
            blocked.append(GATE_CLEANUP_SYMBOL_MISMATCH)
        if cleanup_payload_preview.get("side") != EXPECTED_CLEANUP_SIDE:
            blocked.append(GATE_CLEANUP_SIDE_NOT_SELL_FOR_LONG)
        if cleanup_payload_preview.get("orderType") != EXPECTED_ORDER_TYPE:
            blocked.append(GATE_CLEANUP_ORDER_TYPE_NOT_MARKET)
        if cleanup_payload_preview.get("reduceOnly") is not True:
            blocked.append(GATE_CLEANUP_REDUCE_ONLY_NOT_TRUE)
        if cleanup_payload_preview.get("positionIdx") != EXPECTED_POSITION_IDX:
            blocked.append(GATE_CLEANUP_POSITION_IDX_NOT_ZERO)
        if not str(cleanup_payload_preview.get("orderLinkId", "")).startswith(
            _DRYRUN_LINK_ID_PREFIX
        ):
            blocked.append(GATE_CLEANUP_ORDER_LINK_ID_NOT_DRYRUN)

        stages[STAGE_2_CLEANUP_PAYLOAD_PREVIEW] = {
            "stage":   STAGE_2_CLEANUP_PAYLOAD_PREVIEW,
            "summary": "Build preview-only cleanup close-only payload.",
            "selected_symbol":                       sym,
            "entry_side":                            EXPECTED_ENTRY_SIDE,
            "cleanup_side":                          EXPECTED_CLEANUP_SIDE,
            "entry_rounded_tiny_qty":                entry_rounded_tiny_qty,
            "lifecycle_tiny_qty":                    lifecycle_tiny_qty,
            "expected_tiny_qty":                     expected_tiny_qty,
            "cleanup_payload_preview":               cleanup_payload_preview,
            "order_endpoint_called":                 False,
            "stop_endpoint_called":                  False,
            "no_position_modified":                  True,
            "payload_preview_only":                  True,
            "closeOnTrigger_documentation":          (
                "closeOnTrigger=False keeps the cleanup order as a "
                "regular reduce-only market.  The real cleanup task "
                "may revisit this flag if Bybit semantics change."
            ),
        }

        # ===============================================================
        # stage_3_cleanup_token_checklist
        # ===============================================================
        stages[STAGE_3_CLEANUP_TOKEN_CHECKLIST] = {
            "stage":   STAGE_3_CLEANUP_TOKEN_CHECKLIST,
            "summary": "Document cleanup confirmation token (NEVER validated here).",
            "entry_token_pattern":                       ENTRY_TOKEN_PATTERN,
            "stop_attach_token_pattern":                 STOP_ATTACH_TOKEN_PATTERN,
            "cleanup_token_pattern":                     CLEANUP_TOKEN_PATTERN,
            "cleanup_token_not_validated_in_this_task": True,
            "entry_token_not_accepted_in_this_task":     True,
            "stop_attach_token_not_accepted_in_this_task": True,
            "token_must_be_distinct_per_step":           True,
            "next_step_after_cleanup":                   "readonly_verification",
        }
        # Always-on documentation gates.
        blocked.append(GATE_CLEANUP_TOKEN_PATTERN_REQUIRED)
        blocked.append(GATE_CLEANUP_TOKEN_NOT_VALIDATED_THIS_TASK)
        blocked.append(GATE_ENTRY_TOKEN_NOT_ACCEPTED_THIS_TASK)
        blocked.append(GATE_STOP_ATTACH_TOKEN_NOT_ACCEPTED_THIS_TASK)
        blocked.append(GATE_POST_CLEANUP_READONLY_VERIFICATION_REQUIRED)
        blocked.append(GATE_NO_AUTO_RETRY_AFTER_CLEANUP_FAIL)

        # ===============================================================
        # stage_4_post_cleanup_required_verification_plan
        # ===============================================================
        post_cleanup_plan: dict[str, Any] = {
            "verify_tiny_position_absent_or_qty_zero":  True,
            "verify_no_dangling_tiny_position":         True,
            "verify_existing_5_shorts_still_present":   True,
            "verify_existing_5_stops_unchanged":        True,
            "verify_no_new_unexpected_position":        True,
            "verify_no_order_endpoint_retry_loop":      True,
            "readonly_unavailable_after_cleanup":       "fail_closed",
            "cleanup_rejected":                         "fail_closed",
            "cleanup_partial_fill":                     "fail_closed",
            "tiny_position_still_open_after_cleanup":   "fail_closed",
            "existing_stop_mismatch":                   "manual_review",
            "unexpected_position_appears":              "manual_review",
            "expected_symbol":                          sym,
            "expected_qty_to_be_zero":                  True,
            "expected_existing_position_symbols":       list(EXISTING_POSITION_SYMBOLS),
        }
        stages[STAGE_4_POST_CLEANUP_REQUIRED_VERIFICATION_PLAN] = {
            "stage":   STAGE_4_POST_CLEANUP_REQUIRED_VERIFICATION_PLAN,
            "summary": "Document the readonly verification plan after a future real cleanup.",
            "post_cleanup_verification_plan":           post_cleanup_plan,
        }

        # ===============================================================
        # stage_5_failure_response_plan
        # ===============================================================
        failure_plan: dict[str, Any] = {
            "cleanup_rejected":                         "fail_closed",
            "cleanup_partial_fill":                     "fail_closed",
            "readonly_unavailable_after_cleanup":       "fail_closed",
            "tiny_position_still_open_after_cleanup":   "fail_closed",
            "existing_stop_mismatch":                   "manual_review",
            "unexpected_position_appears":              "manual_review",
            "no_automatic_retry_after_cleanup_failure": True,
            "no_automatic_second_order":                True,
            "no_real_emergency_close_in_this_task":     True,
        }
        stages[STAGE_5_FAILURE_RESPONSE_PLAN] = {
            "stage":   STAGE_5_FAILURE_RESPONSE_PLAN,
            "summary": "Document the failure-response plan for cleanup failures.",
            "failure_response_plan":                    failure_plan,
        }
        # Always-on documentation gates.
        blocked.append(GATE_READONLY_UNAVAILABLE_AFTER_CLEANUP_FAIL_CLOSED)
        blocked.append(GATE_CLEANUP_REJECTED_FAIL_CLOSED)
        blocked.append(GATE_CLEANUP_PARTIAL_FILL_FAIL_CLOSED)
        blocked.append(GATE_SOLUSDT_STILL_OPEN_AFTER_CLEANUP_FAIL_CLOSED)
        blocked.append(GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW)
        blocked.append(GATE_UNEXPECTED_POSITION_APPEARS_MANUAL_REVIEW)
        blocked.append(GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK)

        # ===============================================================
        # stage_6_execution_guard
        # ===============================================================
        blocked.append(GATE_REAL_CLEANUP_NOT_IMPL)
        blocked.append(GATE_NO_REAL_ORDER_ENDPOINT)
        blocked.append(GATE_NO_REAL_STOP_ENDPOINT)
        blocked.append(GATE_NO_POSITION_MODIFIED)
        blocked.append(GATE_G20_NOT_LIFTED)
        blocked.append(GATE_G20_POLICY_STILL_IN_PLACE)
        blocked.append(GATE_NO_LIVE_ENDPOINT)
        blocked.append(GATE_NO_SECRETS_EMITTED)

        stages[STAGE_6_EXECUTION_GUARD] = {
            "stage":   STAGE_6_EXECUTION_GUARD,
            "summary": "Permanent execution guard --- TASK-014Z never executes.",
            "real_cleanup_permission_dry_run_allowed": allow_real_cleanup_permission,
            "real_execution_allowed":                  False,
            "real_cleanup_implemented":                False,
            "current_task_real_execution_allowed":     False,
            "real_cleanup_requested":                  bool(allow_real_cleanup),
            "g20_policy_still_in_place":               True,
            "g20_lifted":                              False,
            "no_real_order_endpoint":                  True,
            "no_real_stop_endpoint":                   True,
            "no_position_modified":                    True,
            "no_live_endpoint":                        True,
            "no_secrets_emitted":                      True,
        }

        # ===============================================================
        # Status resolution
        # ===============================================================
        unique = self._dedupe(blocked)
        hard_fail = any(g in unique for g in _HARD_FAIL_GATES)

        if hard_fail:
            failed_stage = self._first_failed_stage(unique)
            status_out = STATUS_FAIL_CLOSED
            mode_out   = MODE_FAIL_CLOSED
        elif allow_real_cleanup:
            failed_stage = ""
            status_out = STATUS_REAL_CLEANUP_NOT_IMPL
            mode_out   = MODE_REAL_CLEANUP_GUARD
        elif allow_real_cleanup_permission:
            failed_stage = ""
            status_out = STATUS_PERMISSION_READY_EXEC_DISABLED
            mode_out   = MODE_REAL_CLEANUP_PERMISSION_DRY_RUN
        else:
            failed_stage = ""
            status_out = STATUS_CHECKLIST_READY
            mode_out   = MODE_CHECKLIST

        return TinyCleanupPermissionGateResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            expected_tiny_qty=expected_tiny_qty,
            entry_rounded_tiny_qty=entry_rounded_tiny_qty,
            lifecycle_tiny_qty=lifecycle_tiny_qty,
            cleanup_side=EXPECTED_CLEANUP_SIDE,
            entry_side=EXPECTED_ENTRY_SIDE,
            cleanup_payload_preview=cleanup_payload_preview,
            post_cleanup_verification_plan=post_cleanup_plan,
            failure_response_plan=failure_plan,
            existing_positions_snapshot=existing_snapshot,
            real_cleanup_permission_dry_run_allowed=allow_real_cleanup_permission,
            real_execution_allowed=False,
            real_cleanup_implemented=False,
            current_task_real_execution_allowed=False,
            real_cleanup_requested=bool(allow_real_cleanup),
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
            blocked_gates=unique,
            failed_stage=failed_stage,
            status=status_out,
        )

    # ----------------------------------------------------------------- util
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
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_LIFECYCLE_MOCK_NOT_SUCCESS,
            GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE,
            GATE_TINY_ENTRY_PERMISSION_GATE_STATUS_UNACCEPTABLE,
            GATE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUS_UNACCEPTABLE,
            GATE_SELECTED_SYMBOL_MISSING,
            GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
        }
        for g in blocked:
            if g in stage_0_set:
                return STAGE_0_ARTIFACT_PREFLIGHT
        stage_2_set = {
            GATE_EXPECTED_TINY_QTY_MISSING,
            GATE_EXPECTED_TINY_QTY_NOT_POSITIVE,
            GATE_EXPECTED_TINY_QTY_MISMATCH_ENTRY_GATE,
            GATE_CLEANUP_SIDE_NOT_SELL_FOR_LONG,
            GATE_CLEANUP_CATEGORY_NOT_LINEAR,
            GATE_CLEANUP_SYMBOL_MISMATCH,
            GATE_CLEANUP_ORDER_TYPE_NOT_MARKET,
            GATE_CLEANUP_REDUCE_ONLY_NOT_TRUE,
            GATE_CLEANUP_POSITION_IDX_NOT_ZERO,
            GATE_CLEANUP_PAYLOAD_NOT_PREVIEW_ONLY,
            GATE_CLEANUP_ORDER_LINK_ID_NOT_DRYRUN,
        }
        for g in blocked:
            if g in stage_2_set:
                return STAGE_2_CLEANUP_PAYLOAD_PREVIEW
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
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_NOOP_RECOMMENDED_PATH",
    "EXPECTED_LIFECYCLE_STATUS",
    "EXPECTED_INSTRUMENT_CATEGORY",
    "EXPECTED_ENTRY_SIDE",
    "EXPECTED_CLEANUP_SIDE",
    "EXPECTED_ORDER_TYPE",
    "EXPECTED_POSITION_IDX",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT",
    "STAGE_2_CLEANUP_PAYLOAD_PREVIEW",
    "STAGE_3_CLEANUP_TOKEN_CHECKLIST",
    "STAGE_4_POST_CLEANUP_REQUIRED_VERIFICATION_PLAN",
    "STAGE_5_FAILURE_RESPONSE_PLAN",
    "STAGE_6_EXECUTION_GUARD",
    "ALL_STAGES",
    "STATUS_CHECKLIST_READY",
    "STATUS_PERMISSION_READY_EXEC_DISABLED",
    "STATUS_REAL_CLEANUP_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_CHECKLIST",
    "MODE_REAL_CLEANUP_PERMISSION_DRY_RUN",
    "MODE_REAL_CLEANUP_GUARD",
    "MODE_FAIL_CLOSED",
    # general gates
    "GATE_READONLY_SMOKE_MISSING",
    "GATE_RECONCILIATION_MISSING",
    "GATE_PROTECTION_MISSING",
    "GATE_CONTRACT_MISSING",
    "GATE_NOOP_PLAN_MISSING",
    "GATE_LIFECYCLE_MOCK_MISSING",
    "GATE_REAL_PERMISSION_GATE_MISSING",
    "GATE_TINY_ENTRY_PERMISSION_GATE_MISSING",
    "GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING",
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
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # cleanup payload gates
    "GATE_EXPECTED_TINY_QTY_MISSING",
    "GATE_EXPECTED_TINY_QTY_NOT_POSITIVE",
    "GATE_EXPECTED_TINY_QTY_MISMATCH_ENTRY_GATE",
    "GATE_CLEANUP_SIDE_NOT_SELL_FOR_LONG",
    "GATE_CLEANUP_CATEGORY_NOT_LINEAR",
    "GATE_CLEANUP_SYMBOL_MISMATCH",
    "GATE_CLEANUP_ORDER_TYPE_NOT_MARKET",
    "GATE_CLEANUP_REDUCE_ONLY_NOT_TRUE",
    "GATE_CLEANUP_POSITION_IDX_NOT_ZERO",
    "GATE_CLEANUP_PAYLOAD_NOT_PREVIEW_ONLY",
    "GATE_CLEANUP_ORDER_LINK_ID_NOT_DRYRUN",
    "GATE_CLEANUP_ORDER_ENDPOINT_CALLED",
    "GATE_CLEANUP_POSITION_MODIFIED",
    # manual approval gates
    "GATE_CLEANUP_TOKEN_PATTERN_REQUIRED",
    "GATE_CLEANUP_TOKEN_NOT_VALIDATED_THIS_TASK",
    "GATE_ENTRY_TOKEN_NOT_ACCEPTED_THIS_TASK",
    "GATE_STOP_ATTACH_TOKEN_NOT_ACCEPTED_THIS_TASK",
    "GATE_POST_CLEANUP_READONLY_VERIFICATION_REQUIRED",
    "GATE_NO_AUTO_RETRY_AFTER_CLEANUP_FAIL",
    # failure gates
    "GATE_READONLY_UNAVAILABLE_AFTER_CLEANUP_FAIL_CLOSED",
    "GATE_CLEANUP_REJECTED_FAIL_CLOSED",
    "GATE_CLEANUP_PARTIAL_FILL_FAIL_CLOSED",
    "GATE_SOLUSDT_STILL_OPEN_AFTER_CLEANUP_FAIL_CLOSED",
    "GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW",
    "GATE_UNEXPECTED_POSITION_APPEARS_MANUAL_REVIEW",
    "GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK",
    # execution guard gates
    "GATE_REAL_CLEANUP_NOT_IMPL",
    "GATE_NO_REAL_ORDER_ENDPOINT",
    "GATE_NO_REAL_STOP_ENDPOINT",
    "GATE_NO_POSITION_MODIFIED",
    "GATE_G20_NOT_LIFTED",
    "TinyCleanupPermissionGateResult",
    "DemoTinyCleanupPermissionGate",
]
