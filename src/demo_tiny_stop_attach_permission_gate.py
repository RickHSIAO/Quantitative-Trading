"""
src/demo_tiny_stop_attach_permission_gate.py
TASK-014Y: Tiny Isolated Demo Stop Attach Permission Gate / Dry-run Only.

Pure-computation / mock-safe permission gate for the future real stop
attach against the (hypothetical) tiny SOLUSDT long opened by TASK-014X.
Produces a checklist + stop-attach payload preview that documents what
must be in place before a future real stop attach could execute.

This module does NOT execute anything: no /v5/position/trading-stop,
no /v5/order/create, no close-only, no emergency close, no leverage
mutation, no transfers.

Stages:

  stage_0_artifact_preflight
      Validate 8 upstream artifacts (readonly_smoke / reconciliation /
      protection / contract / noop_plan / lifecycle_mock /
      tiny_position_real_permission_gate / tiny_entry_permission_gate)
      plus the runtime proof envelope.

  stage_1_existing_position_pre_snapshot
      Snapshot the 5 existing demo shorts.  Selected symbol must be
      disjoint from existing position symbols.  existing_positions_touched
      must remain [].

  stage_2_stop_payload_preview
      Locate the SOLUSDT instrument rule, verify tick_size present,
      verify stop_price > 0 and aligned with tick_size, build the
      preview-only stop-attach payload: category=linear, symbol=SOLUSDT,
      stopLoss=<stop_price>, tpslMode=Full, slTriggerBy=MarkPrice,
      positionIdx=0.  No socket opened.

  stage_3_stop_attach_token_checklist
      Document the stop-attach confirmation token pattern.  Token is
      NEVER validated in this task.  Entry / cleanup tokens are NOT
      accepted in this task.

  stage_4_post_stop_attach_required_verification_plan
      Document the readonly verification checklist that MUST follow a
      future real stop attach: SOLUSDT position still exists, stop
      price matches submitted value, tpslMode=Full preserved, no
      qty change.

  stage_5_failure_response_plan
      Document the failure-response plan: readonly unavailable, stop
      response not OK, stop price mismatch, tpsl mode mismatch,
      position missing.

  stage_6_execution_guard
      Permanent guard: real_execution_allowed=False,
      real_stop_attach_implemented=False.  Even with
      --allow-real-tiny-stop-attach, returns
      REAL_STOP_ATTACH_NOT_IMPLEMENTED with no socket opened.

Modes:
  checklist                       --- default
  real_stop_permission_dry_run    --- with --allow-real-stop-permission
  real_stop_attach_guard          --- with --allow-real-tiny-stop-attach
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
  * import src.demo_tiny_entry_permission_gate
  * invoke /v5/position/trading-stop or /v5/order/create
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


# ---------------------------------------------------------------------------
# Stage identifiers
# ---------------------------------------------------------------------------

STAGE_0_ARTIFACT_PREFLIGHT                       = "stage_0_artifact_preflight"
STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT           = "stage_1_existing_position_pre_snapshot"
STAGE_2_STOP_PAYLOAD_PREVIEW                     = "stage_2_stop_payload_preview"
STAGE_3_STOP_ATTACH_TOKEN_CHECKLIST              = "stage_3_stop_attach_token_checklist"
STAGE_4_POST_STOP_ATTACH_REQUIRED_VERIFICATION_PLAN = (
    "stage_4_post_stop_attach_required_verification_plan"
)
STAGE_5_FAILURE_RESPONSE_PLAN                    = "stage_5_failure_response_plan"
STAGE_6_EXECUTION_GUARD                          = "stage_6_execution_guard"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT,
    STAGE_2_STOP_PAYLOAD_PREVIEW,
    STAGE_3_STOP_ATTACH_TOKEN_CHECKLIST,
    STAGE_4_POST_STOP_ATTACH_REQUIRED_VERIFICATION_PLAN,
    STAGE_5_FAILURE_RESPONSE_PLAN,
    STAGE_6_EXECUTION_GUARD,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_CHECKLIST_READY                = "TINY_STOP_ATTACH_PERMISSION_CHECKLIST_READY"
STATUS_PERMISSION_READY_EXEC_DISABLED = (
    "TINY_STOP_ATTACH_PERMISSION_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_STOP_ATTACH_NOT_IMPL      = "REAL_STOP_ATTACH_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                    = "FAIL_CLOSED"

MODE_CHECKLIST                        = "checklist"
MODE_REAL_STOP_PERMISSION_DRY_RUN     = "real_stop_permission_dry_run"
MODE_REAL_STOP_ATTACH_GUARD           = "real_stop_attach_guard"
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

EXPECTED_TPSL_MODE               = "Full"
EXPECTED_SL_TRIGGER_BY           = "MarkPrice"
EXPECTED_POSITION_IDX            = 0


# ---------------------------------------------------------------------------
# Gate constants  (20 general + 12 stop payload + 6 manual approval +
#                  6 failure + 5 execution guard = 49)
# ---------------------------------------------------------------------------

# General gates (G01 - G20)
GATE_READONLY_SMOKE_MISSING                  = "readonly_smoke_missing"
GATE_RECONCILIATION_MISSING                  = "reconciliation_missing"
GATE_PROTECTION_MISSING                      = "protection_missing"
GATE_CONTRACT_MISSING                        = "contract_missing"
GATE_NOOP_PLAN_MISSING                       = "noop_plan_missing"
GATE_LIFECYCLE_MOCK_MISSING                  = "lifecycle_mock_missing"
GATE_REAL_PERMISSION_GATE_MISSING            = "real_permission_gate_missing"
GATE_TINY_ENTRY_PERMISSION_GATE_MISSING      = "tiny_entry_permission_gate_missing"
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
GATE_G20_POLICY_STILL_IN_PLACE               = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                        = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                      = "no_secret_values_emitted_in_this_task"

# Stop payload gates (S01 - S12)
GATE_INSTRUMENT_RULE_MISSING                 = "instrument_rule_missing_for_selected_symbol"
GATE_INSTRUMENT_CATEGORY_NOT_LINEAR          = "instrument_category_not_linear"
GATE_TICK_SIZE_MISSING                       = "tick_size_missing"
GATE_STOP_PRICE_MISSING                      = "stop_price_missing"
GATE_STOP_PRICE_NOT_POSITIVE                 = "stop_price_not_positive"
GATE_STOP_PRICE_NOT_ALIGNED_WITH_TICK        = "stop_price_not_aligned_with_tick_size"
GATE_STOP_PAYLOAD_NOT_PREVIEW_ONLY           = "stop_payload_not_preview_only"
GATE_STOP_PAYLOAD_TPSL_MODE_NOT_FULL         = "stop_payload_tpsl_mode_not_full"
GATE_STOP_PAYLOAD_TRIGGER_BY_NOT_MARK_PRICE  = "stop_payload_sl_trigger_by_not_mark_price"
GATE_STOP_PAYLOAD_POSITION_IDX_NOT_ZERO      = "stop_payload_position_idx_not_zero"
GATE_STOP_ENDPOINT_CALLED                    = "stop_endpoint_called_forbidden_in_this_task"
GATE_POSITION_MODIFIED                       = "position_modified_forbidden_in_this_task"

# Manual approval gates (A01 - A06)
GATE_STOP_ATTACH_TOKEN_PATTERN_REQUIRED      = "stop_attach_token_pattern_required_in_future_task"
GATE_STOP_ATTACH_TOKEN_NOT_VALIDATED_THIS_TASK = "stop_attach_token_not_validated_in_this_task"
GATE_ENTRY_TOKEN_NOT_ACCEPTED_THIS_TASK      = "entry_token_not_accepted_in_this_task"
GATE_CLEANUP_TOKEN_NOT_ACCEPTED_THIS_TASK    = "cleanup_token_not_accepted_in_this_task"
GATE_POST_STOP_ATTACH_READONLY_VERIFICATION_REQUIRED = (
    "post_stop_attach_readonly_verification_required"
)
GATE_NO_AUTO_CLEANUP_AFTER_STOP_ATTACH       = "no_automatic_cleanup_after_stop_attach"

# Failure gates (F01 - F06)
GATE_READONLY_UNAVAILABLE_AFTER_STOP_FAIL_CLOSED = (
    "readonly_unavailable_after_stop_attach_fail_closed"
)
GATE_STOP_RESPONSE_NOT_OK_FAIL_CLOSED        = "stop_attach_response_not_ok_fail_closed"
GATE_STOP_PRICE_MISMATCH_AFTER_ATTACH_FAIL_CLOSED = (
    "stop_price_mismatch_after_attach_fail_closed"
)
GATE_TPSL_MODE_MISMATCH_AFTER_ATTACH_MANUAL_REVIEW = (
    "tpsl_mode_mismatch_after_attach_manual_review_required"
)
GATE_POSITION_MISSING_AFTER_STOP_FAIL_CLOSED = "position_missing_after_stop_attach_fail_closed"
GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK       = "no_real_emergency_close_in_this_task"

# Execution guard gates (X01 - X05)
GATE_REAL_STOP_ATTACH_NOT_IMPL               = "real_stop_attach_not_implemented"
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
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_LIFECYCLE_MOCK_NOT_SUCCESS,
    GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_TINY_ENTRY_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_INSTRUMENT_RULE_MISSING,
    GATE_INSTRUMENT_CATEGORY_NOT_LINEAR,
    GATE_TICK_SIZE_MISSING,
    GATE_STOP_PRICE_MISSING,
    GATE_STOP_PRICE_NOT_POSITIVE,
    GATE_STOP_PRICE_NOT_ALIGNED_WITH_TICK,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyStopAttachPermissionGateResult:
    """Read-only outcome of one tiny-stop-attach permission-gate pass."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    # Stop-attach inputs.
    entry_reference_price:        float = 0.0
    stop_price:                   float = 0.0
    stop_price_aligned_with_tick: bool  = False
    tick_size:                    float = 0.0

    # Instrument-rule summary (string-only, no live fetch).
    instrument_rule_summary:      dict[str, Any] = field(default_factory=dict)

    # Preview-only stop-attach payload (NEVER sent).
    stop_payload_preview:         dict[str, Any] = field(default_factory=dict)

    # Token patterns (documented only).
    entry_token_pattern:          str = ENTRY_TOKEN_PATTERN
    stop_attach_token_pattern:    str = STOP_ATTACH_TOKEN_PATTERN
    cleanup_token_pattern:        str = CLEANUP_TOKEN_PATTERN

    # Post-stop-attach verification + failure plans.
    post_stop_attach_verification_plan: dict[str, Any] = field(default_factory=dict)
    failure_response_plan:        dict[str, Any] = field(default_factory=dict)

    existing_positions_snapshot:  list[dict[str, Any]] = field(default_factory=list)

    # Real-execution gating flags (TASK-014Y keeps all of these conservative).
    real_stop_permission_dry_run_allowed: bool = False
    real_execution_allowed:       bool = False
    real_stop_attach_implemented: bool = False
    current_task_real_execution_allowed: bool = False
    real_stop_attach_requested:   bool = False

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
        "TASK-014Z_tiny_isolated_demo_cleanup_permission_gate"
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
            "entry_reference_price":      self.entry_reference_price,
            "stop_price":                 self.stop_price,
            "stop_price_aligned_with_tick": self.stop_price_aligned_with_tick,
            "tick_size":                  self.tick_size,
            "instrument_rule_summary":    dict(self.instrument_rule_summary),
            "stop_payload_preview":       dict(self.stop_payload_preview),
            "entry_token_pattern":        self.entry_token_pattern,
            "stop_attach_token_pattern":  self.stop_attach_token_pattern,
            "cleanup_token_pattern":      self.cleanup_token_pattern,
            "post_stop_attach_verification_plan": dict(self.post_stop_attach_verification_plan),
            "failure_response_plan":      dict(self.failure_response_plan),
            "existing_positions_snapshot": [dict(row) for row in self.existing_positions_snapshot],
            "real_stop_permission_dry_run_allowed": self.real_stop_permission_dry_run_allowed,
            "real_execution_allowed":     self.real_execution_allowed,
            "real_stop_attach_implemented": self.real_stop_attach_implemented,
            "current_task_real_execution_allowed": self.current_task_real_execution_allowed,
            "real_stop_attach_requested": self.real_stop_attach_requested,
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

    Priority 1: `instrument_rules_by_symbol` (dict keyed by symbol).
    Priority 2: `instrument_rules` (list of dicts or dict keyed by
        symbol) --- legacy / test-fixture format.

    Returns the matched rule dict, or None (gate fails closed).
    No fallback to fabricated data.
    """
    if not isinstance(readonly_smoke, dict):
        return None
    sym = (symbol or "").strip().upper()

    by_sym = readonly_smoke.get("instrument_rules_by_symbol", None)
    if isinstance(by_sym, dict):
        for k, v in by_sym.items():
            if str(k).strip().upper() == sym and isinstance(v, dict):
                return v

    rules = readonly_smoke.get("instrument_rules", None)
    if rules is None:
        return None
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


def _aligned_with_tick(price: float, tick: float, tol: float = 1e-9) -> bool:
    if tick <= 0 or price <= 0:
        return False
    n = round(price / tick)
    return abs(n * tick - price) <= tol * max(1.0, price)


# ---------------------------------------------------------------------------
# Permission gate
# ---------------------------------------------------------------------------

class DemoTinyStopAttachPermissionGate:
    """
    Pure-computation permission gate for the future real tiny stop attach.

    Reads 8 upstream JSON artifacts and emits a
    TinyStopAttachPermissionGateResult.  Holds no network client, reads
    no environment variables, and NEVER invokes the trading-stop or
    order-create endpoints.

    --allow-real-stop-permission   --> status promoted to
        TINY_STOP_ATTACH_PERMISSION_READY_BUT_EXECUTION_DISABLED
        (no execution; checklist only).

    --allow-real-tiny-stop-attach  --> status fixed to
        REAL_STOP_ATTACH_NOT_IMPLEMENTED  (no socket opened).
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
        tiny_entry_permission_gate:      dict[str, Any] | None,
        symbol:                          str  = DEFAULT_SELECTED_SYMBOL,
        allow_real_stop_permission:      bool = False,
        allow_real_tiny_stop_attach:     bool = False,
        _now:                            datetime | None = None,
    ) -> TinyStopAttachPermissionGateResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_tiny_stop_attach:
            mode = MODE_REAL_STOP_ATTACH_GUARD
        elif allow_real_stop_permission:
            mode = MODE_REAL_STOP_PERMISSION_DRY_RUN
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

        if not sym:
            blocked.append(GATE_SELECTED_SYMBOL_MISSING)
        elif sym in existing_symbols:
            blocked.append(GATE_SELECTED_SYMBOL_COLLIDES_EXISTING)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 8 upstream artifacts + runtime proof envelope.",
            "readonly_smoke_present":            readonly_present,
            "reconciliation_present":            recon_present,
            "protection_present":                protection_present,
            "contract_present":                  contract_present,
            "noop_plan_present":                 noop_present,
            "lifecycle_mock_present":            lifecycle_present,
            "real_permission_gate_present":      real_perm_present,
            "tiny_entry_permission_gate_present": entry_perm_present,
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
        # stage_2_stop_payload_preview
        # ===============================================================
        rule = _find_instrument_rule(readonly_smoke, sym)
        rule_present = isinstance(rule, dict)

        entry_ref_price = _safe_float(
            (protection or {}).get("entry_reference_price", 0.0), 0.0,
        )
        stop_price_raw = (protection or {}).get("stop_price", None)
        stop_price = _safe_float(stop_price_raw, 0.0)

        if not rule_present:
            blocked.append(GATE_INSTRUMENT_RULE_MISSING)

        category = str((rule or {}).get("category", "")).strip().lower()
        tick_size_raw = (rule or {}).get("tick_size", None)

        if rule_present and category and not category.startswith(EXPECTED_INSTRUMENT_CATEGORY):
            blocked.append(GATE_INSTRUMENT_CATEGORY_NOT_LINEAR)
        if rule_present and tick_size_raw is None:
            blocked.append(GATE_TICK_SIZE_MISSING)

        tick_size = _safe_float(tick_size_raw, 0.0)

        if stop_price_raw is None:
            blocked.append(GATE_STOP_PRICE_MISSING)
        elif stop_price <= 0.0:
            blocked.append(GATE_STOP_PRICE_NOT_POSITIVE)

        stop_aligned = False
        if (
            rule_present
            and tick_size_raw is not None
            and tick_size > 0.0
            and stop_price > 0.0
        ):
            stop_aligned = _aligned_with_tick(stop_price, tick_size)
            if not stop_aligned:
                blocked.append(GATE_STOP_PRICE_NOT_ALIGNED_WITH_TICK)

        instrument_rule_summary: dict[str, Any] = {
            "symbol":             sym,
            "category":           category,
            "category_expected":  EXPECTED_INSTRUMENT_CATEGORY,
            "tick_size":          tick_size,
            "rule_present":       rule_present,
        }

        stop_payload_preview: dict[str, Any] = {
            "preview_only":      True,
            "category":          EXPECTED_INSTRUMENT_CATEGORY,
            "symbol":            sym,
            "stopLoss":          stop_price,
            "tpslMode":          EXPECTED_TPSL_MODE,
            "slTriggerBy":       EXPECTED_SL_TRIGGER_BY,
            "positionIdx":       EXPECTED_POSITION_IDX,
            "endpoint_path_ref": TRADING_STOP_PATH_REF,
            "endpoint_called":   False,
        }

        # Self-check on the preview payload (defense in depth).
        if stop_payload_preview.get("preview_only") is not True:
            blocked.append(GATE_STOP_PAYLOAD_NOT_PREVIEW_ONLY)
        if stop_payload_preview.get("tpslMode") != EXPECTED_TPSL_MODE:
            blocked.append(GATE_STOP_PAYLOAD_TPSL_MODE_NOT_FULL)
        if stop_payload_preview.get("slTriggerBy") != EXPECTED_SL_TRIGGER_BY:
            blocked.append(GATE_STOP_PAYLOAD_TRIGGER_BY_NOT_MARK_PRICE)
        if stop_payload_preview.get("positionIdx") != EXPECTED_POSITION_IDX:
            blocked.append(GATE_STOP_PAYLOAD_POSITION_IDX_NOT_ZERO)

        stages[STAGE_2_STOP_PAYLOAD_PREVIEW] = {
            "stage":   STAGE_2_STOP_PAYLOAD_PREVIEW,
            "summary": "Locate instrument rule + build preview-only stop-attach payload.",
            "selected_symbol":                       sym,
            "instrument_rule_summary":               instrument_rule_summary,
            "entry_reference_price":                 entry_ref_price,
            "stop_price":                            stop_price,
            "stop_price_aligned_with_tick":          stop_aligned,
            "tick_size":                             tick_size,
            "stop_payload_preview":                  stop_payload_preview,
            "stop_endpoint_called":                  False,
            "no_position_modified":                  True,
            "payload_preview_only":                  True,
        }

        # ===============================================================
        # stage_3_stop_attach_token_checklist
        # ===============================================================
        stages[STAGE_3_STOP_ATTACH_TOKEN_CHECKLIST] = {
            "stage":   STAGE_3_STOP_ATTACH_TOKEN_CHECKLIST,
            "summary": "Document stop-attach confirmation token (NEVER validated here).",
            "entry_token_pattern":                       ENTRY_TOKEN_PATTERN,
            "stop_attach_token_pattern":                 STOP_ATTACH_TOKEN_PATTERN,
            "cleanup_token_pattern":                     CLEANUP_TOKEN_PATTERN,
            "stop_attach_token_not_validated_in_this_task": True,
            "entry_token_not_accepted_in_this_task":     True,
            "cleanup_token_not_accepted_in_this_task":   True,
            "token_must_be_distinct_per_step":           True,
            "next_step_after_stop_attach":               "readonly_verification",
        }
        # Always-on documentation gates.
        blocked.append(GATE_STOP_ATTACH_TOKEN_PATTERN_REQUIRED)
        blocked.append(GATE_STOP_ATTACH_TOKEN_NOT_VALIDATED_THIS_TASK)
        blocked.append(GATE_ENTRY_TOKEN_NOT_ACCEPTED_THIS_TASK)
        blocked.append(GATE_CLEANUP_TOKEN_NOT_ACCEPTED_THIS_TASK)
        blocked.append(GATE_POST_STOP_ATTACH_READONLY_VERIFICATION_REQUIRED)
        blocked.append(GATE_NO_AUTO_CLEANUP_AFTER_STOP_ATTACH)

        # ===============================================================
        # stage_4_post_stop_attach_required_verification_plan
        # ===============================================================
        post_stop_plan: dict[str, Any] = {
            "verify_position_still_exists":          True,
            "verify_stop_price_matches_submitted":   True,
            "verify_tpsl_mode_full_preserved":       True,
            "verify_sl_trigger_by_mark_price":       True,
            "verify_position_qty_unchanged":         True,
            "verify_existing_positions_untouched":   True,
            "readonly_unavailable_after_stop":       "fail_closed",
            "stop_response_not_ok":                  "fail_closed",
            "stop_price_mismatch_after_attach":      "fail_closed",
            "tpsl_mode_mismatch_after_attach":       "manual_review",
            "position_missing_after_stop_attach":    "fail_closed",
            "expected_stop_price":                   stop_price,
            "expected_symbol":                       sym,
            "expected_tpsl_mode":                    EXPECTED_TPSL_MODE,
            "expected_sl_trigger_by":                EXPECTED_SL_TRIGGER_BY,
            "expected_position_idx":                 EXPECTED_POSITION_IDX,
        }
        stages[STAGE_4_POST_STOP_ATTACH_REQUIRED_VERIFICATION_PLAN] = {
            "stage":   STAGE_4_POST_STOP_ATTACH_REQUIRED_VERIFICATION_PLAN,
            "summary": "Document the readonly verification plan after a future real stop attach.",
            "post_stop_attach_verification_plan":     post_stop_plan,
        }

        # ===============================================================
        # stage_5_failure_response_plan
        # ===============================================================
        failure_plan: dict[str, Any] = {
            "readonly_unavailable_after_stop":       "fail_closed",
            "stop_response_not_ok":                  "fail_closed",
            "stop_price_mismatch_after_attach":      "fail_closed",
            "tpsl_mode_mismatch_after_attach":       "manual_review",
            "position_missing_after_stop_attach":    "fail_closed",
            "no_real_emergency_close_in_this_task":  True,
            "no_auto_cleanup_after_stop_attach":     True,
        }
        stages[STAGE_5_FAILURE_RESPONSE_PLAN] = {
            "stage":   STAGE_5_FAILURE_RESPONSE_PLAN,
            "summary": "Document the failure-response plan for stop-attach failures.",
            "failure_response_plan":                  failure_plan,
        }
        # Always-on documentation gates.
        blocked.append(GATE_READONLY_UNAVAILABLE_AFTER_STOP_FAIL_CLOSED)
        blocked.append(GATE_STOP_RESPONSE_NOT_OK_FAIL_CLOSED)
        blocked.append(GATE_STOP_PRICE_MISMATCH_AFTER_ATTACH_FAIL_CLOSED)
        blocked.append(GATE_TPSL_MODE_MISMATCH_AFTER_ATTACH_MANUAL_REVIEW)
        blocked.append(GATE_POSITION_MISSING_AFTER_STOP_FAIL_CLOSED)
        blocked.append(GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK)

        # ===============================================================
        # stage_6_execution_guard
        # ===============================================================
        blocked.append(GATE_REAL_STOP_ATTACH_NOT_IMPL)
        blocked.append(GATE_NO_REAL_ORDER_ENDPOINT)
        blocked.append(GATE_NO_REAL_STOP_ENDPOINT)
        blocked.append(GATE_NO_POSITION_MODIFIED)
        blocked.append(GATE_G20_NOT_LIFTED)
        blocked.append(GATE_G20_POLICY_STILL_IN_PLACE)
        blocked.append(GATE_NO_LIVE_ENDPOINT)
        blocked.append(GATE_NO_SECRETS_EMITTED)

        stages[STAGE_6_EXECUTION_GUARD] = {
            "stage":   STAGE_6_EXECUTION_GUARD,
            "summary": "Permanent execution guard --- TASK-014Y never executes.",
            "real_stop_permission_dry_run_allowed": allow_real_stop_permission,
            "real_execution_allowed":               False,
            "real_stop_attach_implemented":         False,
            "current_task_real_execution_allowed":  False,
            "real_stop_attach_requested":           bool(allow_real_tiny_stop_attach),
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
        elif allow_real_tiny_stop_attach:
            failed_stage = ""
            status_out = STATUS_REAL_STOP_ATTACH_NOT_IMPL
            mode_out   = MODE_REAL_STOP_ATTACH_GUARD
        elif allow_real_stop_permission:
            failed_stage = ""
            status_out = STATUS_PERMISSION_READY_EXEC_DISABLED
            mode_out   = MODE_REAL_STOP_PERMISSION_DRY_RUN
        else:
            failed_stage = ""
            status_out = STATUS_CHECKLIST_READY
            mode_out   = MODE_CHECKLIST

        return TinyStopAttachPermissionGateResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            entry_reference_price=entry_ref_price,
            stop_price=stop_price,
            stop_price_aligned_with_tick=stop_aligned,
            tick_size=tick_size,
            instrument_rule_summary=instrument_rule_summary,
            stop_payload_preview=stop_payload_preview,
            post_stop_attach_verification_plan=post_stop_plan,
            failure_response_plan=failure_plan,
            existing_positions_snapshot=existing_snapshot,
            real_stop_permission_dry_run_allowed=allow_real_stop_permission,
            real_execution_allowed=False,
            real_stop_attach_implemented=False,
            current_task_real_execution_allowed=False,
            real_stop_attach_requested=bool(allow_real_tiny_stop_attach),
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
            GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_LIFECYCLE_MOCK_NOT_SUCCESS,
            GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE,
            GATE_TINY_ENTRY_PERMISSION_GATE_STATUS_UNACCEPTABLE,
            GATE_SELECTED_SYMBOL_MISSING,
            GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
        }
        for g in blocked:
            if g in stage_0_set:
                return STAGE_0_ARTIFACT_PREFLIGHT
        stage_2_set = {
            GATE_INSTRUMENT_RULE_MISSING,
            GATE_INSTRUMENT_CATEGORY_NOT_LINEAR,
            GATE_TICK_SIZE_MISSING,
            GATE_STOP_PRICE_MISSING,
            GATE_STOP_PRICE_NOT_POSITIVE,
            GATE_STOP_PRICE_NOT_ALIGNED_WITH_TICK,
        }
        for g in blocked:
            if g in stage_2_set:
                return STAGE_2_STOP_PAYLOAD_PREVIEW
        return ""


__all__ = [
    "EXISTING_POSITION_SYMBOLS",
    "DEFAULT_SELECTED_SYMBOL",
    "TRADING_STOP_PATH_REF",
    "ORDER_CREATE_PATH_REF",
    "BASE_URL_DEMO_REF",
    "ENTRY_TOKEN_PATTERN",
    "STOP_ATTACH_TOKEN_PATTERN",
    "CLEANUP_TOKEN_PATTERN",
    "ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES",
    "ACCEPTABLE_TINY_ENTRY_PERMISSION_GATE_STATUSES",
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_NOOP_RECOMMENDED_PATH",
    "EXPECTED_LIFECYCLE_STATUS",
    "EXPECTED_INSTRUMENT_CATEGORY",
    "EXPECTED_TPSL_MODE",
    "EXPECTED_SL_TRIGGER_BY",
    "EXPECTED_POSITION_IDX",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT",
    "STAGE_2_STOP_PAYLOAD_PREVIEW",
    "STAGE_3_STOP_ATTACH_TOKEN_CHECKLIST",
    "STAGE_4_POST_STOP_ATTACH_REQUIRED_VERIFICATION_PLAN",
    "STAGE_5_FAILURE_RESPONSE_PLAN",
    "STAGE_6_EXECUTION_GUARD",
    "ALL_STAGES",
    "STATUS_CHECKLIST_READY",
    "STATUS_PERMISSION_READY_EXEC_DISABLED",
    "STATUS_REAL_STOP_ATTACH_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_CHECKLIST",
    "MODE_REAL_STOP_PERMISSION_DRY_RUN",
    "MODE_REAL_STOP_ATTACH_GUARD",
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
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_MISSING",
    "GATE_SELECTED_SYMBOL_COLLIDES_EXISTING",
    "GATE_LIFECYCLE_MOCK_NOT_SUCCESS",
    "GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE",
    "GATE_TINY_ENTRY_PERMISSION_GATE_STATUS_UNACCEPTABLE",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # stop payload gates
    "GATE_INSTRUMENT_RULE_MISSING",
    "GATE_INSTRUMENT_CATEGORY_NOT_LINEAR",
    "GATE_TICK_SIZE_MISSING",
    "GATE_STOP_PRICE_MISSING",
    "GATE_STOP_PRICE_NOT_POSITIVE",
    "GATE_STOP_PRICE_NOT_ALIGNED_WITH_TICK",
    "GATE_STOP_PAYLOAD_NOT_PREVIEW_ONLY",
    "GATE_STOP_PAYLOAD_TPSL_MODE_NOT_FULL",
    "GATE_STOP_PAYLOAD_TRIGGER_BY_NOT_MARK_PRICE",
    "GATE_STOP_PAYLOAD_POSITION_IDX_NOT_ZERO",
    "GATE_STOP_ENDPOINT_CALLED",
    "GATE_POSITION_MODIFIED",
    # manual approval gates
    "GATE_STOP_ATTACH_TOKEN_PATTERN_REQUIRED",
    "GATE_STOP_ATTACH_TOKEN_NOT_VALIDATED_THIS_TASK",
    "GATE_ENTRY_TOKEN_NOT_ACCEPTED_THIS_TASK",
    "GATE_CLEANUP_TOKEN_NOT_ACCEPTED_THIS_TASK",
    "GATE_POST_STOP_ATTACH_READONLY_VERIFICATION_REQUIRED",
    "GATE_NO_AUTO_CLEANUP_AFTER_STOP_ATTACH",
    # failure gates
    "GATE_READONLY_UNAVAILABLE_AFTER_STOP_FAIL_CLOSED",
    "GATE_STOP_RESPONSE_NOT_OK_FAIL_CLOSED",
    "GATE_STOP_PRICE_MISMATCH_AFTER_ATTACH_FAIL_CLOSED",
    "GATE_TPSL_MODE_MISMATCH_AFTER_ATTACH_MANUAL_REVIEW",
    "GATE_POSITION_MISSING_AFTER_STOP_FAIL_CLOSED",
    "GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK",
    # execution guard gates
    "GATE_REAL_STOP_ATTACH_NOT_IMPL",
    "GATE_NO_REAL_ORDER_ENDPOINT",
    "GATE_NO_REAL_STOP_ENDPOINT",
    "GATE_NO_POSITION_MODIFIED",
    "GATE_G20_NOT_LIFTED",
    "TinyStopAttachPermissionGateResult",
    "DemoTinyStopAttachPermissionGate",
]
