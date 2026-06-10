"""
src/demo_tiny_entry_permission_gate.py
TASK-014X: Tiny Isolated Demo Entry Permission Gate / Dry-run Only.

Pure-computation / mock-safe permission gate for the future real tiny
entry.  Produces a checklist + entry payload preview that documents
what must be in place before a future real tiny entry could execute.
This module does NOT execute anything: no /v5/order/create, no
/v5/position/trading-stop, no close-only, no emergency close, no
leverage mutation, no transfers.

Stages:

  stage_0_artifact_preflight
      Validate 7 upstream artifacts (readonly_smoke / reconciliation /
      protection / contract / noop_plan / lifecycle_mock /
      tiny_position_real_permission_gate) plus the runtime proof
      envelope.

  stage_1_existing_position_pre_snapshot
      Snapshot the 5 existing demo shorts.  Selected symbol must be
      disjoint from existing position symbols.  existing_positions_touched
      must remain [].

  stage_2_instrument_min_step_check
      Locate the SOLUSDT instrument rule (category=linear), verify
      min_order_qty / qty_step / tick_size / min_notional are all
      present, and round the lifecycle tiny_qty up to (a) at least
      min_order_qty, (b) aligned with qty_step, (c) producing
      tiny_notional >= min_notional.  Final tiny_notional must remain
      <= 10 USDT (tiny notional cap).

  stage_3_tiny_entry_payload_preview
      Build a preview-only entry payload: category=linear,
      symbol=SOLUSDT, side=Buy, orderType=Market, qty=rounded_tiny_qty,
      reduceOnly=False, positionIdx=0, orderLinkId=DRYRUN-TINY-ENTRY-...,
      preview_only=True.  No socket opened.

  stage_4_entry_token_checklist
      Document the entry confirmation token pattern.  Token is NEVER
      validated in this task.  Stop-attach / cleanup tokens are NOT
      accepted in this task.

  stage_5_post_entry_required_verification_plan
      Document the readonly verification checklist that MUST follow a
      future real entry: SOLUSDT position exists, side=long, qty
      matches, entry price > 0, stop price likely 0 before TASK-014Y,
      naked-tiny window must be time-boxed.

  stage_6_execution_guard
      Permanent guard: real_execution_allowed=False,
      real_tiny_entry_implemented=False.  Even with
      --allow-real-tiny-entry, returns REAL_TINY_ENTRY_NOT_IMPLEMENTED
      with no socket opened.

Modes:
  checklist                       --- default
  real_entry_permission_dry_run   --- with --allow-real-entry-permission
  real_tiny_entry_guard           --- with --allow-real-tiny-entry
  fail_closed                     --- upstream / risk validation failed

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

TRADING_STOP_PATH_REF = "/v5/position/trading-stop"   # NOT invoked
ORDER_CREATE_PATH_REF = "/v5/order/create"            # NOT invoked
BASE_URL_DEMO_REF     = "https://api-demo.bybit.com"  # informational only

TINY_NOTIONAL_CAP_USDT:        float = 10.0
STRATEGY_FULL_SIZE_QTY_REF:    float = 12.2
DEFAULT_MIN_NOTIONAL_FALLBACK: float = 5.0


# ---------------------------------------------------------------------------
# Stage identifiers
# ---------------------------------------------------------------------------

STAGE_0_ARTIFACT_PREFLIGHT            = "stage_0_artifact_preflight"
STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT = "stage_1_existing_position_pre_snapshot"
STAGE_2_INSTRUMENT_MIN_STEP_CHECK     = "stage_2_instrument_min_step_check"
STAGE_3_TINY_ENTRY_PAYLOAD_PREVIEW    = "stage_3_tiny_entry_payload_preview"
STAGE_4_ENTRY_TOKEN_CHECKLIST         = "stage_4_entry_token_checklist"
STAGE_5_POST_ENTRY_REQUIRED_VERIFICATION_PLAN = (
    "stage_5_post_entry_required_verification_plan"
)
STAGE_6_EXECUTION_GUARD               = "stage_6_execution_guard"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT,
    STAGE_2_INSTRUMENT_MIN_STEP_CHECK,
    STAGE_3_TINY_ENTRY_PAYLOAD_PREVIEW,
    STAGE_4_ENTRY_TOKEN_CHECKLIST,
    STAGE_5_POST_ENTRY_REQUIRED_VERIFICATION_PLAN,
    STAGE_6_EXECUTION_GUARD,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_CHECKLIST_READY            = "TINY_ENTRY_PERMISSION_CHECKLIST_READY"
STATUS_PERMISSION_READY_EXEC_DISABLED = (
    "TINY_ENTRY_PERMISSION_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_TINY_ENTRY_NOT_IMPL   = "REAL_TINY_ENTRY_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                = "FAIL_CLOSED"

MODE_CHECKLIST                    = "checklist"
MODE_REAL_ENTRY_PERMISSION_DRY_RUN = "real_entry_permission_dry_run"
MODE_REAL_TINY_ENTRY_GUARD        = "real_tiny_entry_guard"
MODE_FAIL_CLOSED                  = "fail_closed"


# ---------------------------------------------------------------------------
# Acceptable upstream-status whitelists
# ---------------------------------------------------------------------------

ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES: frozenset[str] = frozenset({
    "REAL_PERMISSION_CHECKLIST_READY",
    "REAL_PERMISSION_GATE_READY_BUT_EXECUTION_DISABLED",
    "REAL_TINY_POSITION_NOT_IMPLEMENTED",
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


# ---------------------------------------------------------------------------
# Gate constants  (18 general + 10 instrument + 8 entry payload +
#                  6 manual approval + 6 failure + 5 execution guard = 53)
# ---------------------------------------------------------------------------

# General gates (G01 - G18)
GATE_READONLY_SMOKE_MISSING                = "readonly_smoke_missing"
GATE_RECONCILIATION_MISSING                = "reconciliation_missing"
GATE_PROTECTION_MISSING                    = "protection_missing"
GATE_CONTRACT_MISSING                      = "contract_missing"
GATE_NOOP_PLAN_MISSING                     = "noop_plan_missing"
GATE_LIFECYCLE_MOCK_MISSING                = "lifecycle_mock_missing"
GATE_REAL_PERMISSION_GATE_MISSING          = "real_permission_gate_missing"
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO        = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                 = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG             = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_MISSING               = "selected_symbol_missing"
GATE_SELECTED_SYMBOL_COLLIDES_EXISTING     = "selected_symbol_collides_with_existing_position"
GATE_LIFECYCLE_MOCK_NOT_SUCCESS            = "lifecycle_mock_status_not_success"
GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE = "real_permission_gate_status_unacceptable"
GATE_G20_POLICY_STILL_IN_PLACE             = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                      = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                    = "no_secret_values_emitted_in_this_task"

# Instrument gates (I01 - I10)
GATE_INSTRUMENT_RULE_MISSING               = "instrument_rule_missing_for_selected_symbol"
GATE_INSTRUMENT_CATEGORY_NOT_LINEAR        = "instrument_category_not_linear"
GATE_MIN_ORDER_QTY_MISSING                 = "min_order_qty_missing"
GATE_QTY_STEP_MISSING                      = "qty_step_missing"
GATE_TICK_SIZE_MISSING                     = "tick_size_missing"
GATE_MIN_NOTIONAL_MISSING                  = "min_notional_missing"
GATE_ROUNDED_QTY_BELOW_MIN_ORDER_QTY       = "rounded_tiny_qty_below_min_order_qty"
GATE_ROUNDED_QTY_NOT_ALIGNED_WITH_STEP     = "rounded_tiny_qty_not_aligned_with_qty_step"
GATE_ESTIMATED_NOTIONAL_OVER_CAP           = "estimated_tiny_notional_over_cap"
GATE_STRATEGY_FULL_SIZE_QTY_REUSED         = "strategy_full_size_qty_reused"

# Entry payload gates (P01 - P08)
GATE_PAYLOAD_NOT_PREVIEW_ONLY              = "entry_payload_not_preview_only"
GATE_PAYLOAD_SIDE_NOT_BUY                  = "entry_payload_side_not_buy"
GATE_PAYLOAD_REDUCE_ONLY_NOT_FALSE         = "entry_payload_reduce_only_not_false"
GATE_PAYLOAD_POSITION_IDX_NOT_ZERO         = "entry_payload_position_idx_not_zero"
GATE_PAYLOAD_ORDER_LINK_ID_NOT_DRYRUN      = "entry_payload_order_link_id_not_dryrun"
GATE_ORDER_ENDPOINT_CALLED                 = "order_endpoint_called_forbidden_in_this_task"
GATE_ORDERS_SENT                           = "orders_sent_forbidden_in_this_task"
GATE_POSITION_MODIFIED                     = "position_modified_forbidden_in_this_task"

# Manual approval gates (A01 - A06)
GATE_ENTRY_TOKEN_PATTERN_REQUIRED          = "entry_token_pattern_required_in_future_task"
GATE_ENTRY_TOKEN_NOT_VALIDATED_THIS_TASK   = "entry_token_not_validated_in_this_task"
GATE_STOP_ATTACH_TOKEN_NOT_ACCEPTED_THIS_TASK = "stop_attach_token_not_accepted_in_this_task"
GATE_CLEANUP_TOKEN_NOT_ACCEPTED_THIS_TASK  = "cleanup_token_not_accepted_in_this_task"
GATE_POST_ENTRY_READONLY_VERIFICATION_REQUIRED = "post_entry_readonly_verification_required"
GATE_NO_AUTO_STOP_ATTACH_AFTER_ENTRY       = "no_automatic_stop_attach_after_entry"

# Failure gates (F01 - F06)
GATE_READONLY_UNAVAILABLE_AFTER_ENTRY_FAIL_CLOSED = "readonly_unavailable_after_entry_fail_closed"
GATE_POSITION_MISSING_AFTER_ENTRY_FAIL_CLOSED = "position_missing_after_entry_fail_closed"
GATE_QTY_MISMATCH_AFTER_ENTRY_FAIL_CLOSED  = "qty_mismatch_after_entry_fail_closed"
GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW  = "existing_stop_mismatch_manual_review_required"
GATE_NAKED_TINY_WINDOW_MUST_BE_TIME_BOXED  = "naked_tiny_position_window_must_be_time_boxed"
GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK     = "no_real_emergency_close_in_this_task"

# Execution guard gates (X01 - X05)
GATE_REAL_TINY_ENTRY_NOT_IMPL              = "real_tiny_entry_not_implemented"
GATE_NO_REAL_ORDER_ENDPOINT                = "no_real_order_endpoint_in_this_task"
GATE_NO_REAL_STOP_ENDPOINT                 = "no_real_stop_endpoint_in_this_task"
GATE_NO_POSITION_MODIFIED                  = "no_position_modified_in_this_task"
GATE_G20_NOT_LIFTED                        = "g20_policy_not_lifted_by_this_task"


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
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_LIFECYCLE_MOCK_NOT_SUCCESS,
    GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_INSTRUMENT_RULE_MISSING,
    GATE_INSTRUMENT_CATEGORY_NOT_LINEAR,
    GATE_MIN_ORDER_QTY_MISSING,
    GATE_QTY_STEP_MISSING,
    GATE_TICK_SIZE_MISSING,
    GATE_MIN_NOTIONAL_MISSING,
    GATE_ROUNDED_QTY_BELOW_MIN_ORDER_QTY,
    GATE_ROUNDED_QTY_NOT_ALIGNED_WITH_STEP,
    GATE_ESTIMATED_NOTIONAL_OVER_CAP,
    GATE_STRATEGY_FULL_SIZE_QTY_REUSED,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyEntryPermissionGateResult:
    """Read-only outcome of one tiny-entry permission-gate pass."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    # Quantity / notional fields.
    original_tiny_qty:            float = 0.0
    rounded_tiny_qty:             float = 0.0
    entry_reference_price:        float = 0.0
    estimated_tiny_notional:      float = 0.0
    tiny_notional_cap_usdt:       float = TINY_NOTIONAL_CAP_USDT
    within_tiny_notional_cap:     bool  = False
    strategy_full_size_qty_ref:   float = STRATEGY_FULL_SIZE_QTY_REF

    # Instrument-rule summary (string-only, no live fetch).
    instrument_rule_summary:      dict[str, Any] = field(default_factory=dict)

    # Preview-only entry payload (NEVER sent).
    entry_payload_preview:        dict[str, Any] = field(default_factory=dict)

    # Entry token (documented only).
    entry_token_pattern:          str = ENTRY_TOKEN_PATTERN
    stop_attach_token_pattern:    str = STOP_ATTACH_TOKEN_PATTERN
    cleanup_token_pattern:        str = CLEANUP_TOKEN_PATTERN

    # Post-entry verification plan.
    post_entry_verification_plan: dict[str, Any] = field(default_factory=dict)

    existing_positions_snapshot:  list[dict[str, Any]] = field(default_factory=list)

    # Real-execution gating flags (TASK-014X keeps all of these conservative).
    real_entry_permission_dry_run_allowed: bool = False
    real_execution_allowed:       bool = False
    real_tiny_entry_implemented:  bool = False
    current_task_real_execution_allowed: bool = False
    real_tiny_entry_requested:    bool = False

    # Safety invariants (string-only references / always documented).
    trading_stop_path_ref:        str  = TRADING_STOP_PATH_REF
    order_create_path_ref:        str  = ORDER_CREATE_PATH_REF
    base_url_ref:                 str  = BASE_URL_DEMO_REF

    stop_endpoint_called:         bool = False
    order_endpoint_called:        bool = False
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
        "TASK-014Y_tiny_isolated_demo_stop_attach_permission_gate"
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
            "original_tiny_qty":          self.original_tiny_qty,
            "rounded_tiny_qty":           self.rounded_tiny_qty,
            "entry_reference_price":      self.entry_reference_price,
            "estimated_tiny_notional":    self.estimated_tiny_notional,
            "tiny_notional_cap_usdt":     self.tiny_notional_cap_usdt,
            "within_tiny_notional_cap":   self.within_tiny_notional_cap,
            "strategy_full_size_qty_ref": self.strategy_full_size_qty_ref,
            "instrument_rule_summary":    dict(self.instrument_rule_summary),
            "entry_payload_preview":      dict(self.entry_payload_preview),
            "entry_token_pattern":        self.entry_token_pattern,
            "stop_attach_token_pattern":  self.stop_attach_token_pattern,
            "cleanup_token_pattern":      self.cleanup_token_pattern,
            "post_entry_verification_plan": dict(self.post_entry_verification_plan),
            "existing_positions_snapshot": [dict(row) for row in self.existing_positions_snapshot],
            "real_entry_permission_dry_run_allowed": self.real_entry_permission_dry_run_allowed,
            "real_execution_allowed":     self.real_execution_allowed,
            "real_tiny_entry_implemented": self.real_tiny_entry_implemented,
            "current_task_real_execution_allowed": self.current_task_real_execution_allowed,
            "real_tiny_entry_requested":  self.real_tiny_entry_requested,
            "trading_stop_path_ref":      self.trading_stop_path_ref,
            "order_create_path_ref":      self.order_create_path_ref,
            "base_url_ref":               self.base_url_ref,
            "stop_endpoint_called":       self.stop_endpoint_called,
            "order_endpoint_called":      self.order_endpoint_called,
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


def _find_instrument_rule(
    readonly_smoke: dict[str, Any] | None,
    symbol:         str,
) -> dict[str, Any] | None:
    """Locate the symbol-specific instrument rule from readonly_smoke.

    Accepts either a list under `instrument_rules` or a dict keyed by
    symbol.  Returns the matched rule dict, or None.
    """
    if not isinstance(readonly_smoke, dict):
        return None
    rules = readonly_smoke.get("instrument_rules", None)
    if rules is None:
        return None
    sym = (symbol or "").strip().upper()
    if isinstance(rules, list):
        for row in rules:
            if not isinstance(row, dict):
                continue
            row_sym = str(row.get("symbol", "")).strip().upper()
            if row_sym == sym:
                return row
        return None
    if isinstance(rules, dict):
        for k, v in rules.items():
            if str(k).strip().upper() == sym and isinstance(v, dict):
                return v
        return None
    return None


def _round_up_to_step(qty: float, step: float) -> float:
    if step <= 0:
        return qty
    n = math.ceil(qty / step - 1e-12)
    return n * step


def _aligned_with_step(qty: float, step: float, tol: float = 1e-9) -> bool:
    if step <= 0:
        return False
    n = round(qty / step)
    return abs(n * step - qty) <= tol * max(1.0, qty)


_DRYRUN_LINK_ID_PREFIX = "DRYRUN-TINY-ENTRY"


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


# ---------------------------------------------------------------------------
# Permission gate
# ---------------------------------------------------------------------------

class DemoTinyEntryPermissionGate:
    """
    Pure-computation permission gate for the future real tiny entry.

    Reads 7 upstream JSON artifacts and emits a
    TinyEntryPermissionGateResult.  Holds no network client, reads no
    environment variables, and NEVER invokes the trading-stop or
    order-create endpoints.

    --allow-real-entry-permission   --> status promoted to
        TINY_ENTRY_PERMISSION_READY_BUT_EXECUTION_DISABLED
        (no execution; checklist only).

    --allow-real-tiny-entry         --> status fixed to
        REAL_TINY_ENTRY_NOT_IMPLEMENTED  (no socket opened).
    """

    def __init__(self) -> None:
        pass

    def run_checklist(
        self,
        readonly_smoke:                  dict[str, Any] | None,
        reconciliation:                  dict[str, Any] | None,
        protection:                      dict[str, Any] | None,
        contract:                        dict[str, Any] | None,
        noop_plan:                       dict[str, Any] | None,
        lifecycle_mock:                  dict[str, Any] | None,
        real_permission_gate:            dict[str, Any] | None,
        symbol:                          str  = DEFAULT_SELECTED_SYMBOL,
        allow_real_entry_permission:     bool = False,
        allow_real_tiny_entry:           bool = False,
        _now:                            datetime | None = None,
    ) -> TinyEntryPermissionGateResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_tiny_entry:
            mode = MODE_REAL_TINY_ENTRY_GUARD
        elif allow_real_entry_permission:
            mode = MODE_REAL_ENTRY_PERMISSION_DRY_RUN
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

        if not sym:
            blocked.append(GATE_SELECTED_SYMBOL_MISSING)
        elif sym in existing_symbols:
            blocked.append(GATE_SELECTED_SYMBOL_COLLIDES_EXISTING)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 7 upstream artifacts + runtime proof envelope.",
            "readonly_smoke_present":            readonly_present,
            "reconciliation_present":            recon_present,
            "protection_present":                protection_present,
            "contract_present":                  contract_present,
            "noop_plan_present":                 noop_present,
            "lifecycle_mock_present":            lifecycle_present,
            "real_permission_gate_present":      real_perm_present,
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
            "selected_symbol":                   sym,
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
        # stage_2_instrument_min_step_check
        # ===============================================================
        rule = _find_instrument_rule(readonly_smoke, sym)
        rule_present = isinstance(rule, dict)

        entry_ref_price = _safe_float(
            (protection or {}).get("entry_reference_price", 0.0), 0.0,
        )
        original_tiny_qty = _safe_float(
            (lifecycle_mock or {}).get("tiny_qty", 0.0), 0.0,
        )
        if original_tiny_qty <= 0.0 and entry_ref_price > 0.0:
            original_tiny_qty = 0.1

        # Strategy-sized qty reuse (hard fail).
        if abs(original_tiny_qty - STRATEGY_FULL_SIZE_QTY_REF) <= 1e-9:
            blocked.append(GATE_STRATEGY_FULL_SIZE_QTY_REUSED)

        if not rule_present:
            blocked.append(GATE_INSTRUMENT_RULE_MISSING)

        category = str((rule or {}).get("category", "")).strip().lower()
        min_order_qty_raw = (rule or {}).get("min_order_qty", None)
        qty_step_raw      = (rule or {}).get("qty_step",      None)
        tick_size_raw     = (rule or {}).get("tick_size",     None)
        min_notional_raw  = (rule or {}).get(
            "min_notional_value",
            (rule or {}).get("min_notional", None),
        )

        if rule_present and category and not category.startswith(EXPECTED_INSTRUMENT_CATEGORY):
            blocked.append(GATE_INSTRUMENT_CATEGORY_NOT_LINEAR)
        if rule_present and min_order_qty_raw is None:
            blocked.append(GATE_MIN_ORDER_QTY_MISSING)
        if rule_present and qty_step_raw is None:
            blocked.append(GATE_QTY_STEP_MISSING)
        if rule_present and tick_size_raw is None:
            blocked.append(GATE_TICK_SIZE_MISSING)
        if rule_present and min_notional_raw is None:
            blocked.append(GATE_MIN_NOTIONAL_MISSING)

        min_order_qty = _safe_float(min_order_qty_raw, 0.0)
        qty_step      = _safe_float(qty_step_raw,      0.0)
        tick_size     = _safe_float(tick_size_raw,     0.0)
        min_notional  = _safe_float(min_notional_raw,
                                    DEFAULT_MIN_NOTIONAL_FALLBACK)

        # Rounding pipeline.
        rounded_tiny_qty       = 0.0
        estimated_tiny_notional = 0.0
        within_cap             = False
        if (
            rule_present
            and min_order_qty_raw is not None
            and qty_step_raw is not None
            and tick_size_raw is not None
            and min_notional_raw is not None
            and entry_ref_price > 0.0
            and original_tiny_qty > 0.0
            and qty_step > 0.0
        ):
            candidate = max(original_tiny_qty, min_order_qty)
            candidate = _round_up_to_step(candidate, qty_step)
            notional  = candidate * entry_ref_price
            if notional < min_notional:
                needed = min_notional / entry_ref_price
                candidate = max(candidate, needed)
                candidate = _round_up_to_step(candidate, qty_step)
                notional  = candidate * entry_ref_price
            rounded_tiny_qty       = candidate
            estimated_tiny_notional = notional
            within_cap = (
                estimated_tiny_notional > 0.0
                and estimated_tiny_notional <= TINY_NOTIONAL_CAP_USDT
            )
            if rounded_tiny_qty < min_order_qty:
                blocked.append(GATE_ROUNDED_QTY_BELOW_MIN_ORDER_QTY)
            if not _aligned_with_step(rounded_tiny_qty, qty_step):
                blocked.append(GATE_ROUNDED_QTY_NOT_ALIGNED_WITH_STEP)
            if estimated_tiny_notional > TINY_NOTIONAL_CAP_USDT:
                blocked.append(GATE_ESTIMATED_NOTIONAL_OVER_CAP)

        instrument_rule_summary: dict[str, Any] = {
            "symbol":             sym,
            "category":           category,
            "category_expected":  EXPECTED_INSTRUMENT_CATEGORY,
            "min_order_qty":      min_order_qty,
            "qty_step":           qty_step,
            "tick_size":          tick_size,
            "min_notional":       min_notional,
            "rule_present":       rule_present,
        }

        stages[STAGE_2_INSTRUMENT_MIN_STEP_CHECK] = {
            "stage":   STAGE_2_INSTRUMENT_MIN_STEP_CHECK,
            "summary": "Locate SOLUSDT instrument rule + round tiny qty/notional.",
            "selected_symbol":                       sym,
            "instrument_rule_summary":               instrument_rule_summary,
            "original_tiny_qty":                     original_tiny_qty,
            "rounded_tiny_qty":                      rounded_tiny_qty,
            "entry_reference_price":                 entry_ref_price,
            "estimated_tiny_notional":               estimated_tiny_notional,
            "tiny_notional_cap_usdt":                TINY_NOTIONAL_CAP_USDT,
            "within_tiny_notional_cap":              within_cap,
            "strategy_full_size_qty_ref":            STRATEGY_FULL_SIZE_QTY_REF,
            "strategy_full_size_qty_must_not_be_reused": True,
        }

        # ===============================================================
        # stage_3_tiny_entry_payload_preview
        # ===============================================================
        order_link_id = _build_order_link_id(sym, ts_utc)
        entry_payload_preview: dict[str, Any] = {
            "preview_only":  True,
            "category":      EXPECTED_INSTRUMENT_CATEGORY,
            "symbol":        sym,
            "side":          "Buy",
            "orderType":     "Market",
            "qty":           rounded_tiny_qty,
            "reduceOnly":    False,
            "positionIdx":   0,
            "orderLinkId":   order_link_id,
            "endpoint_path_ref": ORDER_CREATE_PATH_REF,
            "endpoint_called":   False,
        }

        # Self-check on the preview payload (defense in depth).
        if entry_payload_preview.get("preview_only") is not True:
            blocked.append(GATE_PAYLOAD_NOT_PREVIEW_ONLY)
        if entry_payload_preview.get("side") != "Buy":
            blocked.append(GATE_PAYLOAD_SIDE_NOT_BUY)
        if entry_payload_preview.get("reduceOnly") is not False:
            blocked.append(GATE_PAYLOAD_REDUCE_ONLY_NOT_FALSE)
        if entry_payload_preview.get("positionIdx") != 0:
            blocked.append(GATE_PAYLOAD_POSITION_IDX_NOT_ZERO)
        if not str(entry_payload_preview.get("orderLinkId", "")).startswith(
            _DRYRUN_LINK_ID_PREFIX
        ):
            blocked.append(GATE_PAYLOAD_ORDER_LINK_ID_NOT_DRYRUN)

        stages[STAGE_3_TINY_ENTRY_PAYLOAD_PREVIEW] = {
            "stage":   STAGE_3_TINY_ENTRY_PAYLOAD_PREVIEW,
            "summary": "Build preview-only tiny entry payload (NEVER sent).",
            "entry_payload_preview":     entry_payload_preview,
            "order_endpoint_called":     False,
            "no_orders_sent":            True,
            "no_position_modified":      True,
            "payload_preview_only":      True,
        }

        # ===============================================================
        # stage_4_entry_token_checklist
        # ===============================================================
        stages[STAGE_4_ENTRY_TOKEN_CHECKLIST] = {
            "stage":   STAGE_4_ENTRY_TOKEN_CHECKLIST,
            "summary": "Document entry confirmation token (NEVER validated here).",
            "entry_token_pattern":               ENTRY_TOKEN_PATTERN,
            "stop_attach_token_pattern":         STOP_ATTACH_TOKEN_PATTERN,
            "cleanup_token_pattern":             CLEANUP_TOKEN_PATTERN,
            "entry_token_not_validated_in_this_task":   True,
            "stop_attach_token_not_accepted_in_this_task": True,
            "cleanup_token_not_accepted_in_this_task":   True,
            "token_must_be_distinct_per_step":    True,
            "next_step_after_entry":              "readonly_verification",
        }
        # Always-on documentation gates.
        blocked.append(GATE_ENTRY_TOKEN_PATTERN_REQUIRED)
        blocked.append(GATE_ENTRY_TOKEN_NOT_VALIDATED_THIS_TASK)
        blocked.append(GATE_STOP_ATTACH_TOKEN_NOT_ACCEPTED_THIS_TASK)
        blocked.append(GATE_CLEANUP_TOKEN_NOT_ACCEPTED_THIS_TASK)
        blocked.append(GATE_POST_ENTRY_READONLY_VERIFICATION_REQUIRED)
        blocked.append(GATE_NO_AUTO_STOP_ATTACH_AFTER_ENTRY)

        # ===============================================================
        # stage_5_post_entry_required_verification_plan
        # ===============================================================
        post_entry_plan: dict[str, Any] = {
            "verify_position_exists":            True,
            "verify_side_equals_long":           True,
            "verify_qty_equals_rounded_tiny_qty": True,
            "verify_entry_price_positive":       True,
            "stop_price_expected_zero_before_TASK_014Y": True,
            "naked_tiny_window_time_boxed":      True,
            "readonly_unavailable_after_entry":  "fail_closed",
            "position_missing_after_entry":      "fail_closed",
            "qty_mismatch_after_entry":          "fail_closed",
            "existing_stop_mismatch":            "manual_review",
            "expected_qty":                      rounded_tiny_qty,
            "expected_symbol":                   sym,
            "expected_side":                     "long",
        }
        stages[STAGE_5_POST_ENTRY_REQUIRED_VERIFICATION_PLAN] = {
            "stage":   STAGE_5_POST_ENTRY_REQUIRED_VERIFICATION_PLAN,
            "summary": "Document the readonly verification plan after a future real entry.",
            "post_entry_verification_plan":      post_entry_plan,
        }
        # Always-on documentation gates.
        blocked.append(GATE_READONLY_UNAVAILABLE_AFTER_ENTRY_FAIL_CLOSED)
        blocked.append(GATE_POSITION_MISSING_AFTER_ENTRY_FAIL_CLOSED)
        blocked.append(GATE_QTY_MISMATCH_AFTER_ENTRY_FAIL_CLOSED)
        blocked.append(GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW)
        blocked.append(GATE_NAKED_TINY_WINDOW_MUST_BE_TIME_BOXED)
        blocked.append(GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK)

        # ===============================================================
        # stage_6_execution_guard
        # ===============================================================
        blocked.append(GATE_REAL_TINY_ENTRY_NOT_IMPL)
        blocked.append(GATE_NO_REAL_ORDER_ENDPOINT)
        blocked.append(GATE_NO_REAL_STOP_ENDPOINT)
        blocked.append(GATE_NO_POSITION_MODIFIED)
        blocked.append(GATE_G20_NOT_LIFTED)
        blocked.append(GATE_G20_POLICY_STILL_IN_PLACE)
        blocked.append(GATE_NO_LIVE_ENDPOINT)
        blocked.append(GATE_NO_SECRETS_EMITTED)

        stages[STAGE_6_EXECUTION_GUARD] = {
            "stage":   STAGE_6_EXECUTION_GUARD,
            "summary": "Permanent execution guard --- TASK-014X never executes.",
            "real_entry_permission_dry_run_allowed": allow_real_entry_permission,
            "real_execution_allowed":               False,
            "real_tiny_entry_implemented":          False,
            "current_task_real_execution_allowed":  False,
            "real_tiny_entry_requested":            bool(allow_real_tiny_entry),
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "no_real_order_endpoint":               True,
            "no_real_stop_endpoint":                True,
            "no_position_modified":                 True,
            "no_live_endpoint":                     True,
            "no_secrets_emitted":                   True,
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
        elif allow_real_tiny_entry:
            failed_stage = ""
            status_out = STATUS_REAL_TINY_ENTRY_NOT_IMPL
            mode_out   = MODE_REAL_TINY_ENTRY_GUARD
        elif allow_real_entry_permission:
            failed_stage = ""
            status_out = STATUS_PERMISSION_READY_EXEC_DISABLED
            mode_out   = MODE_REAL_ENTRY_PERMISSION_DRY_RUN
        else:
            failed_stage = ""
            status_out = STATUS_CHECKLIST_READY
            mode_out   = MODE_CHECKLIST

        return TinyEntryPermissionGateResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            original_tiny_qty=original_tiny_qty,
            rounded_tiny_qty=rounded_tiny_qty,
            entry_reference_price=entry_ref_price,
            estimated_tiny_notional=estimated_tiny_notional,
            within_tiny_notional_cap=within_cap,
            instrument_rule_summary=instrument_rule_summary,
            entry_payload_preview=entry_payload_preview,
            post_entry_verification_plan=post_entry_plan,
            existing_positions_snapshot=existing_snapshot,
            real_entry_permission_dry_run_allowed=allow_real_entry_permission,
            real_execution_allowed=False,
            real_tiny_entry_implemented=False,
            current_task_real_execution_allowed=False,
            real_tiny_entry_requested=bool(allow_real_tiny_entry),
            stop_endpoint_called=False,
            order_endpoint_called=False,
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
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_LIFECYCLE_MOCK_NOT_SUCCESS,
            GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE,
            GATE_SELECTED_SYMBOL_MISSING,
            GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
        }
        for g in blocked:
            if g in stage_0_set:
                return STAGE_0_ARTIFACT_PREFLIGHT
        stage_2_set = {
            GATE_INSTRUMENT_RULE_MISSING,
            GATE_INSTRUMENT_CATEGORY_NOT_LINEAR,
            GATE_MIN_ORDER_QTY_MISSING,
            GATE_QTY_STEP_MISSING,
            GATE_TICK_SIZE_MISSING,
            GATE_MIN_NOTIONAL_MISSING,
            GATE_ROUNDED_QTY_BELOW_MIN_ORDER_QTY,
            GATE_ROUNDED_QTY_NOT_ALIGNED_WITH_STEP,
            GATE_ESTIMATED_NOTIONAL_OVER_CAP,
            GATE_STRATEGY_FULL_SIZE_QTY_REUSED,
        }
        for g in blocked:
            if g in stage_2_set:
                return STAGE_2_INSTRUMENT_MIN_STEP_CHECK
        return ""


__all__ = [
    "EXISTING_POSITION_SYMBOLS",
    "DEFAULT_SELECTED_SYMBOL",
    "TRADING_STOP_PATH_REF",
    "ORDER_CREATE_PATH_REF",
    "BASE_URL_DEMO_REF",
    "TINY_NOTIONAL_CAP_USDT",
    "STRATEGY_FULL_SIZE_QTY_REF",
    "DEFAULT_MIN_NOTIONAL_FALLBACK",
    "ENTRY_TOKEN_PATTERN",
    "STOP_ATTACH_TOKEN_PATTERN",
    "CLEANUP_TOKEN_PATTERN",
    "ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES",
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_NOOP_RECOMMENDED_PATH",
    "EXPECTED_LIFECYCLE_STATUS",
    "EXPECTED_INSTRUMENT_CATEGORY",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT",
    "STAGE_2_INSTRUMENT_MIN_STEP_CHECK",
    "STAGE_3_TINY_ENTRY_PAYLOAD_PREVIEW",
    "STAGE_4_ENTRY_TOKEN_CHECKLIST",
    "STAGE_5_POST_ENTRY_REQUIRED_VERIFICATION_PLAN",
    "STAGE_6_EXECUTION_GUARD",
    "ALL_STAGES",
    "STATUS_CHECKLIST_READY",
    "STATUS_PERMISSION_READY_EXEC_DISABLED",
    "STATUS_REAL_TINY_ENTRY_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_CHECKLIST",
    "MODE_REAL_ENTRY_PERMISSION_DRY_RUN",
    "MODE_REAL_TINY_ENTRY_GUARD",
    "MODE_FAIL_CLOSED",
    # general gates
    "GATE_READONLY_SMOKE_MISSING",
    "GATE_RECONCILIATION_MISSING",
    "GATE_PROTECTION_MISSING",
    "GATE_CONTRACT_MISSING",
    "GATE_NOOP_PLAN_MISSING",
    "GATE_LIFECYCLE_MOCK_MISSING",
    "GATE_REAL_PERMISSION_GATE_MISSING",
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_MISSING",
    "GATE_SELECTED_SYMBOL_COLLIDES_EXISTING",
    "GATE_LIFECYCLE_MOCK_NOT_SUCCESS",
    "GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # instrument gates
    "GATE_INSTRUMENT_RULE_MISSING",
    "GATE_INSTRUMENT_CATEGORY_NOT_LINEAR",
    "GATE_MIN_ORDER_QTY_MISSING",
    "GATE_QTY_STEP_MISSING",
    "GATE_TICK_SIZE_MISSING",
    "GATE_MIN_NOTIONAL_MISSING",
    "GATE_ROUNDED_QTY_BELOW_MIN_ORDER_QTY",
    "GATE_ROUNDED_QTY_NOT_ALIGNED_WITH_STEP",
    "GATE_ESTIMATED_NOTIONAL_OVER_CAP",
    "GATE_STRATEGY_FULL_SIZE_QTY_REUSED",
    # entry payload gates
    "GATE_PAYLOAD_NOT_PREVIEW_ONLY",
    "GATE_PAYLOAD_SIDE_NOT_BUY",
    "GATE_PAYLOAD_REDUCE_ONLY_NOT_FALSE",
    "GATE_PAYLOAD_POSITION_IDX_NOT_ZERO",
    "GATE_PAYLOAD_ORDER_LINK_ID_NOT_DRYRUN",
    "GATE_ORDER_ENDPOINT_CALLED",
    "GATE_ORDERS_SENT",
    "GATE_POSITION_MODIFIED",
    # manual approval gates
    "GATE_ENTRY_TOKEN_PATTERN_REQUIRED",
    "GATE_ENTRY_TOKEN_NOT_VALIDATED_THIS_TASK",
    "GATE_STOP_ATTACH_TOKEN_NOT_ACCEPTED_THIS_TASK",
    "GATE_CLEANUP_TOKEN_NOT_ACCEPTED_THIS_TASK",
    "GATE_POST_ENTRY_READONLY_VERIFICATION_REQUIRED",
    "GATE_NO_AUTO_STOP_ATTACH_AFTER_ENTRY",
    # failure gates
    "GATE_READONLY_UNAVAILABLE_AFTER_ENTRY_FAIL_CLOSED",
    "GATE_POSITION_MISSING_AFTER_ENTRY_FAIL_CLOSED",
    "GATE_QTY_MISMATCH_AFTER_ENTRY_FAIL_CLOSED",
    "GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW",
    "GATE_NAKED_TINY_WINDOW_MUST_BE_TIME_BOXED",
    "GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK",
    # execution guard gates
    "GATE_REAL_TINY_ENTRY_NOT_IMPL",
    "GATE_NO_REAL_ORDER_ENDPOINT",
    "GATE_NO_REAL_STOP_ENDPOINT",
    "GATE_NO_POSITION_MODIFIED",
    "GATE_G20_NOT_LIFTED",
    "TinyEntryPermissionGateResult",
    "DemoTinyEntryPermissionGate",
]
