"""
src/demo_tiny_position_lifecycle_mock.py
TASK-014V: Tiny Isolated Demo Position Lifecycle Mock.

Pure-computation / mock-safe lifecycle simulator.  Executes a complete
7-phase tiny-isolated-position lifecycle in MEMORY only.  No socket is
opened, no HTTP request is signed, no Bybit endpoint is invoked, and no
real position state is touched.

Lifecycle phases (mock only):

  phase_0_preflight
      Validate the 5 upstream artifacts (readonly_smoke /
      reconciliation / protection / contract / noop_plan) and the
      selected symbol.  Confirms that none of the 5 existing demo
      shorts (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT)
      will be touched by the lifecycle.

  phase_1_tiny_entry_mock
      Synthesise a tiny entry envelope (symbol / side / qty / limit
      price / order link id) using minimum-instrument values.  No
      /v5/order/create call.

  phase_2_post_fill_audit_mock
      Confirm the synthetic order would have filled at the tiny qty
      and document the post-fill audit envelope.

  phase_3_stop_attach_mock
      Synthesise a /v5/position/trading-stop envelope targeting the
      isolated tiny position only.  Honours the failure-injection
      hook _simulate_stop_attach_failure.

  phase_4_protected_verify_mock
      Confirm the tiny position is now protected by a stop_price
      consistent with the protection report.  Honours the failure-
      injection hook _simulate_existing_stop_mismatch (which models
      a hypothetical mismatch between the tiny position's stop and
      the desired stop --- existing 5 positions remain untouched).

  phase_5_cleanup_mock
      Synthesise a close envelope to flatten the tiny position back
      to zero.  Honours the failure-injection hook
      _simulate_cleanup_failure.

  phase_6_final_audit_mock
      Confirm the tiny position is closed, no dangling tiny position
      remains, and that none of the 5 existing demo shorts were
      touched.

Modes:
  preview        --- default; emit lifecycle plan envelopes only.
                     Result status = TINY_LIFECYCLE_PREVIEW_READY.
  mock_lifecycle --- run all 7 phases against in-memory envelopes.
                     Result status = MOCK_TINY_LIFECYCLE_SUCCESS or
                     MOCK_TINY_LIFECYCLE_FAIL_CLOSED.
  real_tiny_position --- guarded sentinel; returns
                     REAL_TINY_POSITION_NOT_IMPLEMENTED.  No socket,
                     no envelope dispatched.
  fail_closed    --- upstream / symbol validation failed.

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
  * import scripts.execute_*
  * invoke /v5/order/create or /v5/position/trading-stop
  * lift TASK-014L sender G20 (protected_entry_policy_missing)
  * touch ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT
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

TRADING_STOP_PATH_REF = "/v5/position/trading-stop"   # NOT invoked
ORDER_CREATE_PATH_REF = "/v5/order/create"            # NOT invoked
BASE_URL_DEMO_REF     = "https://api-demo.bybit.com"  # informational only

# Mock identifier prefixes (deterministic; per-symbol).
MOCK_ENTRY_PREFIX   = "MOCK-TINY-ENTRY-"
MOCK_STOP_PREFIX    = "MOCK-TINY-STOP-"
MOCK_CLEANUP_PREFIX = "MOCK-TINY-CLEANUP-"


# ---------------------------------------------------------------------------
# Phase identifiers
# ---------------------------------------------------------------------------

PHASE_0_PREFLIGHT          = "phase_0_preflight"
PHASE_1_TINY_ENTRY         = "phase_1_tiny_entry_mock"
PHASE_2_POST_FILL_AUDIT    = "phase_2_post_fill_audit_mock"
PHASE_3_STOP_ATTACH        = "phase_3_stop_attach_mock"
PHASE_4_PROTECTED_VERIFY   = "phase_4_protected_verify_mock"
PHASE_5_CLEANUP            = "phase_5_cleanup_mock"
PHASE_6_FINAL_AUDIT        = "phase_6_final_audit_mock"

ALL_PHASES: tuple[str, ...] = (
    PHASE_0_PREFLIGHT,
    PHASE_1_TINY_ENTRY,
    PHASE_2_POST_FILL_AUDIT,
    PHASE_3_STOP_ATTACH,
    PHASE_4_PROTECTED_VERIFY,
    PHASE_5_CLEANUP,
    PHASE_6_FINAL_AUDIT,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_PREVIEW_READY              = "TINY_LIFECYCLE_PREVIEW_READY"
STATUS_MOCK_SUCCESS               = "MOCK_TINY_LIFECYCLE_SUCCESS"
STATUS_MOCK_FAIL_CLOSED           = "MOCK_TINY_LIFECYCLE_FAIL_CLOSED"
STATUS_REAL_TINY_NOT_IMPLEMENTED  = "REAL_TINY_POSITION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                = "FAIL_CLOSED"

MODE_PREVIEW                      = "preview"
MODE_MOCK_LIFECYCLE               = "mock_lifecycle"
MODE_REAL_TINY_POSITION           = "real_tiny_position"
MODE_FAIL_CLOSED                  = "fail_closed"


# ---------------------------------------------------------------------------
# Gate constants (21 general + 8 lifecycle = 29)
# ---------------------------------------------------------------------------

# General gates (G01 - G21)
GATE_READONLY_SMOKE_MISSING            = "readonly_smoke_missing"
GATE_RECONCILIATION_MISSING            = "reconciliation_missing"
GATE_PROTECTION_MISSING                = "protection_missing"
GATE_CONTRACT_MISSING                  = "contract_missing"
GATE_NOOP_PLAN_MISSING                 = "noop_plan_missing"
GATE_SELECTED_SYMBOL_MISSING           = "selected_symbol_missing"
GATE_SYMBOL_COLLIDES_EXISTING_POSITION = "selected_symbol_collides_with_existing_position"
GATE_REALTIME_PRICE_GUARD_MISSING      = "realtime_price_guard_missing"
GATE_REVIEW_FAIL_CLOSED                = "review_fail_closed"
GATE_NOOP_PLAN_RECOMMENDED_PATH_MISMATCH = "noop_plan_recommended_path_mismatch"
GATE_NOOP_PLAN_NOT_READY               = "noop_plan_not_ready"
GATE_PROTECTION_STOP_PRICE_MISSING     = "protection_stop_price_missing"
GATE_PROTECTION_ENTRY_PRICE_MISSING    = "protection_entry_reference_price_missing"
GATE_TINY_QTY_NOT_DEFINED              = "tiny_qty_not_defined"
GATE_TINY_NOTIONAL_NOT_DEFINED         = "tiny_notional_not_defined"
GATE_BALANCE_INSUFFICIENT              = "available_balance_insufficient_for_tiny_notional"
GATE_PRIOR_PROBE_FLIPPED_REAL          = "prior_probe_real_implemented_unexpectedly"
GATE_REAL_TINY_POSITION_NOT_IMPL       = "real_tiny_position_not_implemented"
GATE_EXISTING_POSITIONS_MUST_NOT_TOUCH = "existing_positions_must_not_be_touched"
GATE_G20_POLICY_STILL_IN_PLACE         = "g20_sender_policy_still_in_place"
GATE_LIFECYCLE_DOC_MISSING             = "lifecycle_documentation_missing"

# Lifecycle phase gates (L01 - L08)
GATE_PREFLIGHT_FAILED                  = "lifecycle_preflight_failed"
GATE_TINY_ENTRY_ENVELOPE_INVALID       = "lifecycle_tiny_entry_envelope_invalid"
GATE_POST_FILL_AUDIT_FAILED            = "lifecycle_post_fill_audit_failed"
GATE_STOP_ATTACH_FAILED                = "lifecycle_stop_attach_failed"
GATE_PROTECTED_VERIFY_MISMATCH         = "lifecycle_protected_verify_stop_mismatch"
GATE_CLEANUP_FAILED                    = "lifecycle_cleanup_failed"
GATE_FINAL_AUDIT_DANGLING_POSITION     = "lifecycle_final_audit_dangling_tiny_position"
GATE_FINAL_AUDIT_EXISTING_TOUCHED      = "lifecycle_final_audit_existing_position_touched"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyPositionLifecycleResult:
    """Read-only outcome of one tiny-isolated lifecycle mock pass."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    # Per-phase envelopes (string-only contents).
    phases:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    phase_order:                  list[str] = field(default_factory=lambda: list(ALL_PHASES))

    # Lifecycle summary fields.
    tiny_qty:                     float = 0.0
    tiny_notional:                float = 0.0
    entry_reference_price:        float = 0.0
    stop_price:                   float = 0.0
    tiny_side:                    str   = ""
    mock_entry_order_link_id:     str   = ""
    mock_stop_envelope_id:        str   = ""
    mock_cleanup_order_link_id:   str   = ""

    # Real-execution gating flags (TASK-014V keeps all of these conservative).
    real_execution_allowed:       bool = False
    real_tiny_position_implemented: bool = False
    current_task_real_execution_allowed: bool = False

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
    secret_value_observed:        bool = False
    g20_policy_still_in_place:    bool = True

    # Lifecycle-specific safety invariants.
    dangling_tiny_position:       bool = False
    existing_position_stop_snapshot_match: bool = True
    existing_positions_touched:   list[str] = field(default_factory=list)

    blocked_gates:                list[str] = field(default_factory=list)
    failed_phase:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = (
        "TASK-014W_tiny_isolated_demo_position_real_execution_permission_gate"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                  self.timestamp_utc,
            "timestamp_utc":              self.timestamp_utc,
            "mode":                       self.mode,
            "selected_symbol":            self.selected_symbol,
            "existing_position_symbols":  list(self.existing_position_symbols),
            "phases":                     {k: dict(v) for k, v in self.phases.items()},
            "phase_order":                list(self.phase_order),
            "tiny_qty":                   self.tiny_qty,
            "tiny_notional":              self.tiny_notional,
            "entry_reference_price":      self.entry_reference_price,
            "stop_price":                 self.stop_price,
            "tiny_side":                  self.tiny_side,
            "mock_entry_order_link_id":   self.mock_entry_order_link_id,
            "mock_stop_envelope_id":      self.mock_stop_envelope_id,
            "mock_cleanup_order_link_id": self.mock_cleanup_order_link_id,
            "real_execution_allowed":     self.real_execution_allowed,
            "real_tiny_position_implemented": self.real_tiny_position_implemented,
            "current_task_real_execution_allowed": self.current_task_real_execution_allowed,
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
            "secret_value_observed":      self.secret_value_observed,
            "g20_policy_still_in_place":  self.g20_policy_still_in_place,
            "dangling_tiny_position":     self.dangling_tiny_position,
            "existing_position_stop_snapshot_match": self.existing_position_stop_snapshot_match,
            "existing_positions_touched": list(self.existing_positions_touched),
            "blocked_gates":              list(self.blocked_gates),
            "failed_phase":               self.failed_phase,
            "status":                     self.status,
            "next_required_task":         self.next_required_task,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _positions_from_reconciliation(reconciliation: dict[str, Any] | None) -> list[str]:
    if not isinstance(reconciliation, dict):
        return list(EXISTING_POSITION_SYMBOLS)
    rows = reconciliation.get("positions", None)
    if not isinstance(rows, list) or not rows:
        return list(EXISTING_POSITION_SYMBOLS)
    out: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            sym = str(row.get("symbol", "")).strip()
            if sym:
                out.append(sym)
    return out or list(EXISTING_POSITION_SYMBOLS)


def _available_balance(readonly_smoke: dict[str, Any] | None) -> float:
    if not isinstance(readonly_smoke, dict):
        return 0.0
    val = readonly_smoke.get("available_balance_usd", None)
    if val is None:
        val = readonly_smoke.get("available_balance", 0.0)
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Lifecycle simulator
# ---------------------------------------------------------------------------

class DemoTinyPositionLifecycleMock:
    """
    Pure-computation tiny isolated lifecycle simulator.  Reads 5
    upstream JSON artifacts (readonly_smoke / reconciliation /
    protection / contract / noop_plan) and emits a
    TinyPositionLifecycleResult.

    Holds no network client, reads no environment variables, and never
    invokes the trading-stop or order-create endpoints.  Even when the
    caller sets --allow-real-tiny-position, this simulator returns
    REAL_TINY_POSITION_NOT_IMPLEMENTED.  The real execution gate is
    the subject of TASK-014W+.
    """

    # Tiny-instrument defaults (mock-safe; spec-aligned).
    DEFAULT_TINY_QTY      = 0.1   # SOLUSDT min-instrument-aligned mock qty
    DEFAULT_TINY_LEVERAGE = 1
    DEFAULT_NOTIONAL_BUFFER = 1.5  # multiplier on notional for balance check
    DEFAULT_TINY_SIDE     = "long"

    def __init__(self) -> None:
        pass  # No credentials, no clients, no env reads.

    # ----------------------------------------------------------------- run
    def run_lifecycle(
        self,
        readonly_smoke:               dict[str, Any] | None,
        reconciliation:               dict[str, Any] | None,
        protection:                   dict[str, Any] | None,
        contract:                     dict[str, Any] | None,
        noop_plan:                    dict[str, Any] | None,
        symbol:                       str  = DEFAULT_SELECTED_SYMBOL,
        mock_lifecycle:               bool = False,
        allow_real_tiny_position:     bool = False,
        _simulate_stop_attach_failure: bool = False,
        _simulate_cleanup_failure:     bool = False,
        _simulate_existing_stop_mismatch: bool = False,
        _now:                         datetime | None = None,
    ) -> TinyPositionLifecycleResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_tiny_position:
            mode = MODE_REAL_TINY_POSITION
        elif mock_lifecycle:
            mode = MODE_MOCK_LIFECYCLE
        else:
            mode = MODE_PREVIEW

        blocked: list[str] = []
        phases:  dict[str, dict[str, Any]] = {}

        # ----------------------- phase_0_preflight -----------------------
        preflight_envelope: dict[str, Any] = {
            "phase":   PHASE_0_PREFLIGHT,
            "summary": "Validate 5 upstream artifacts + symbol disjointness.",
            "readonly_smoke_present":  isinstance(readonly_smoke, dict) and bool(readonly_smoke),
            "reconciliation_present":  isinstance(reconciliation, dict) and bool(reconciliation),
            "protection_present":      isinstance(protection, dict) and bool(protection),
            "contract_present":        isinstance(contract, dict) and bool(contract),
            "noop_plan_present":       isinstance(noop_plan, dict) and bool(noop_plan),
            "selected_symbol":         (symbol or "").strip(),
        }

        if not isinstance(readonly_smoke, dict) or not readonly_smoke:
            blocked.append(GATE_READONLY_SMOKE_MISSING)
        if not isinstance(reconciliation, dict) or not reconciliation:
            blocked.append(GATE_RECONCILIATION_MISSING)
        if not isinstance(protection, dict) or not protection:
            blocked.append(GATE_PROTECTION_MISSING)
        if not isinstance(contract, dict) or not contract:
            blocked.append(GATE_CONTRACT_MISSING)
        if not isinstance(noop_plan, dict) or not noop_plan:
            blocked.append(GATE_NOOP_PLAN_MISSING)

        existing = _positions_from_reconciliation(reconciliation)
        sym = (symbol or "").strip()
        if not sym:
            blocked.append(GATE_SELECTED_SYMBOL_MISSING)
        elif sym in existing:
            blocked.append(GATE_SYMBOL_COLLIDES_EXISTING_POSITION)

        # Protection-derived prices and guard flags.
        if isinstance(protection, dict) and protection:
            if not bool(protection.get("realtime_price_guard_verified", False)):
                blocked.append(GATE_REALTIME_PRICE_GUARD_MISSING)
            if bool(protection.get("review_fail_closed", False)):
                blocked.append(GATE_REVIEW_FAIL_CLOSED)
            if protection.get("stop_price", None) in (None, 0, 0.0):
                blocked.append(GATE_PROTECTION_STOP_PRICE_MISSING)
            if protection.get("entry_reference_price", None) in (None, 0, 0.0):
                blocked.append(GATE_PROTECTION_ENTRY_PRICE_MISSING)

        # Contract / no-op plan integrity.
        if isinstance(contract, dict) and contract:
            if bool(contract.get("real_probe_implemented", False)):
                blocked.append(GATE_PRIOR_PROBE_FLIPPED_REAL)
        if isinstance(noop_plan, dict) and noop_plan:
            status_field = str(noop_plan.get("status", "")).strip()
            if status_field not in (
                "NOOP_PROBE_PLAN_READY", "REAL_NOOP_PROBE_NOT_IMPLEMENTED",
            ):
                blocked.append(GATE_NOOP_PLAN_NOT_READY)
            rec_path = str(noop_plan.get("recommended_path", "")).strip()
            if rec_path and rec_path != "tiny_isolated_position_plan":
                blocked.append(GATE_NOOP_PLAN_RECOMMENDED_PATH_MISMATCH)

        # Balance / qty computation (deterministic).
        tiny_qty       = float(self.DEFAULT_TINY_QTY)
        entry_ref      = _safe_float(
            (protection or {}).get("entry_reference_price", 0.0), 0.0,
        )
        stop_price_val = _safe_float(
            (protection or {}).get("stop_price", 0.0), 0.0,
        )
        side           = str((protection or {}).get(
            "selected_side", self.DEFAULT_TINY_SIDE,
        )).strip() or self.DEFAULT_TINY_SIDE
        tiny_notional  = tiny_qty * entry_ref
        balance        = _available_balance(readonly_smoke)
        if tiny_qty <= 0.0:
            blocked.append(GATE_TINY_QTY_NOT_DEFINED)
        if tiny_notional <= 0.0:
            blocked.append(GATE_TINY_NOTIONAL_NOT_DEFINED)
        if balance > 0.0 and tiny_notional > 0.0:
            if balance < tiny_notional * self.DEFAULT_NOTIONAL_BUFFER:
                blocked.append(GATE_BALANCE_INSUFFICIENT)

        # Lifecycle documentation envelope baseline.
        if not ALL_PHASES:
            blocked.append(GATE_LIFECYCLE_DOC_MISSING)

        # Always-on defense-in-depth gates.
        blocked.append(GATE_EXISTING_POSITIONS_MUST_NOT_TOUCH)
        blocked.append(GATE_G20_POLICY_STILL_IN_PLACE)

        # Hard-fail conditions for preflight.
        hard_fail_gates = {
            GATE_READONLY_SMOKE_MISSING,
            GATE_RECONCILIATION_MISSING,
            GATE_PROTECTION_MISSING,
            GATE_CONTRACT_MISSING,
            GATE_NOOP_PLAN_MISSING,
            GATE_SELECTED_SYMBOL_MISSING,
            GATE_SYMBOL_COLLIDES_EXISTING_POSITION,
        }
        preflight_failed = any(g in hard_fail_gates for g in blocked)
        preflight_envelope["preflight_ok"] = not preflight_failed
        phases[PHASE_0_PREFLIGHT] = preflight_envelope

        if preflight_failed:
            blocked.append(GATE_PREFLIGHT_FAILED)
            unique = self._dedupe(blocked)
            return TinyPositionLifecycleResult(
                timestamp_utc=ts_utc,
                mode=MODE_FAIL_CLOSED,
                selected_symbol=sym,
                existing_position_symbols=existing,
                phases=phases,
                tiny_qty=tiny_qty,
                tiny_notional=tiny_notional,
                entry_reference_price=entry_ref,
                stop_price=stop_price_val,
                tiny_side=side,
                real_execution_allowed=allow_real_tiny_position,
                real_tiny_position_implemented=False,
                current_task_real_execution_allowed=False,
                blocked_gates=unique,
                failed_phase=PHASE_0_PREFLIGHT,
                status=STATUS_FAIL_CLOSED,
            )

        # --------- short-circuit: real-tiny-position guard ----------------
        if allow_real_tiny_position:
            blocked.append(GATE_REAL_TINY_POSITION_NOT_IMPL)
            unique = self._dedupe(blocked)
            return TinyPositionLifecycleResult(
                timestamp_utc=ts_utc,
                mode=MODE_REAL_TINY_POSITION,
                selected_symbol=sym,
                existing_position_symbols=existing,
                phases=phases,
                tiny_qty=tiny_qty,
                tiny_notional=tiny_notional,
                entry_reference_price=entry_ref,
                stop_price=stop_price_val,
                tiny_side=side,
                real_execution_allowed=True,
                real_tiny_position_implemented=False,
                current_task_real_execution_allowed=False,
                blocked_gates=unique,
                failed_phase="",
                status=STATUS_REAL_TINY_NOT_IMPLEMENTED,
            )

        # ----------------------- phase_1_tiny_entry ---------------------
        entry_link_id = f"{MOCK_ENTRY_PREFIX}{sym}-{ts_utc}"
        entry_envelope: dict[str, Any] = {
            "phase":               PHASE_1_TINY_ENTRY,
            "summary":             "Synthesise tiny entry envelope (no /v5/order/create).",
            "endpoint_ref":        ORDER_CREATE_PATH_REF,
            "endpoint_called":     False,
            "symbol":              sym,
            "side":                "Buy" if side == "long" else "Sell",
            "qty":                 tiny_qty,
            "notional":            tiny_notional,
            "limit_price":         entry_ref,
            "order_link_id":       entry_link_id,
            "leverage":            self.DEFAULT_TINY_LEVERAGE,
            "envelope_valid":      tiny_qty > 0.0 and tiny_notional > 0.0,
        }
        phases[PHASE_1_TINY_ENTRY] = entry_envelope
        if not entry_envelope["envelope_valid"]:
            blocked.append(GATE_TINY_ENTRY_ENVELOPE_INVALID)

        # ----------------------- phase_2_post_fill_audit ----------------
        post_fill_envelope: dict[str, Any] = {
            "phase":               PHASE_2_POST_FILL_AUDIT,
            "summary":             "Confirm synthetic fill envelope + audit.",
            "endpoint_called":     False,
            "expected_filled_qty": tiny_qty,
            "expected_filled_avg_price": entry_ref,
            "order_link_id":       entry_link_id,
            "audit_ok":            entry_envelope["envelope_valid"],
        }
        phases[PHASE_2_POST_FILL_AUDIT] = post_fill_envelope
        if not post_fill_envelope["audit_ok"]:
            blocked.append(GATE_POST_FILL_AUDIT_FAILED)

        # ----------------------- phase_3_stop_attach --------------------
        stop_envelope_id = f"{MOCK_STOP_PREFIX}{sym}-{ts_utc}"
        stop_attach_ok = not bool(_simulate_stop_attach_failure)
        stop_attach_envelope: dict[str, Any] = {
            "phase":               PHASE_3_STOP_ATTACH,
            "summary":             "Synthesise /v5/position/trading-stop envelope (no call).",
            "endpoint_ref":        TRADING_STOP_PATH_REF,
            "endpoint_called":     False,
            "symbol":              sym,
            "stop_loss":           stop_price_val,
            "envelope_id":         stop_envelope_id,
            "attach_ok":           stop_attach_ok,
            "simulated_failure":   bool(_simulate_stop_attach_failure),
        }
        phases[PHASE_3_STOP_ATTACH] = stop_attach_envelope
        if not stop_attach_ok:
            blocked.append(GATE_STOP_ATTACH_FAILED)

        # ----------------------- phase_4_protected_verify ---------------
        protected_match = (not bool(_simulate_existing_stop_mismatch)) and stop_attach_ok
        protected_envelope: dict[str, Any] = {
            "phase":               PHASE_4_PROTECTED_VERIFY,
            "summary":             "Confirm tiny position stop matches protection report.",
            "endpoint_called":     False,
            "observed_stop_price": stop_price_val if stop_attach_ok else 0.0,
            "expected_stop_price": stop_price_val,
            "match":               protected_match,
            "simulated_mismatch":  bool(_simulate_existing_stop_mismatch),
        }
        phases[PHASE_4_PROTECTED_VERIFY] = protected_envelope
        if not protected_match:
            blocked.append(GATE_PROTECTED_VERIFY_MISMATCH)

        # ----------------------- phase_5_cleanup -----------------------
        cleanup_link_id = f"{MOCK_CLEANUP_PREFIX}{sym}-{ts_utc}"
        cleanup_ok = (not bool(_simulate_cleanup_failure)) and stop_attach_ok and protected_match
        cleanup_envelope: dict[str, Any] = {
            "phase":               PHASE_5_CLEANUP,
            "summary":             "Synthesise flatten envelope to close tiny position.",
            "endpoint_ref":        ORDER_CREATE_PATH_REF,
            "endpoint_called":     False,
            "symbol":              sym,
            "side":                "Sell" if side == "long" else "Buy",
            "qty":                 tiny_qty,
            "reduce_only":         True,
            "order_link_id":       cleanup_link_id,
            "cleanup_ok":          cleanup_ok,
            "simulated_failure":   bool(_simulate_cleanup_failure),
        }
        phases[PHASE_5_CLEANUP] = cleanup_envelope
        if not cleanup_ok:
            blocked.append(GATE_CLEANUP_FAILED)

        # ----------------------- phase_6_final_audit -------------------
        dangling = not cleanup_ok  # if cleanup failed, position is dangling
        # Existing positions must never be touched by this mock; the
        # lifecycle only ever targets `sym`, which has been verified
        # disjoint from EXISTING_POSITION_SYMBOLS in phase_0.
        existing_touched: list[str] = []
        existing_match   = True
        final_audit_envelope: dict[str, Any] = {
            "phase":               PHASE_6_FINAL_AUDIT,
            "summary":             "Confirm clean tear-down + existing positions intact.",
            "endpoint_called":     False,
            "dangling_tiny_position": dangling,
            "existing_positions_touched": existing_touched,
            "existing_position_stop_snapshot_match": existing_match,
        }
        phases[PHASE_6_FINAL_AUDIT] = final_audit_envelope
        if dangling:
            blocked.append(GATE_FINAL_AUDIT_DANGLING_POSITION)
        if existing_touched:
            blocked.append(GATE_FINAL_AUDIT_EXISTING_TOUCHED)

        # ----------------------- final assembly -------------------------
        unique = self._dedupe(blocked)

        # Determine status.
        if mode == MODE_PREVIEW:
            status_out = STATUS_PREVIEW_READY
            failed_phase_out = ""
        elif mode == MODE_MOCK_LIFECYCLE:
            lifecycle_phase_failures = [
                (PHASE_3_STOP_ATTACH,      not stop_attach_ok),
                (PHASE_4_PROTECTED_VERIFY, not protected_match),
                (PHASE_5_CLEANUP,          not cleanup_ok),
                (PHASE_6_FINAL_AUDIT,      dangling or bool(existing_touched)),
            ]
            first_failure = next((p for p, failed in lifecycle_phase_failures if failed), "")
            if first_failure:
                status_out = STATUS_MOCK_FAIL_CLOSED
                failed_phase_out = first_failure
            else:
                status_out = STATUS_MOCK_SUCCESS
                failed_phase_out = ""
        else:
            status_out = STATUS_FAIL_CLOSED
            failed_phase_out = ""

        return TinyPositionLifecycleResult(
            timestamp_utc=ts_utc,
            mode=mode,
            selected_symbol=sym,
            existing_position_symbols=existing,
            phases=phases,
            tiny_qty=tiny_qty,
            tiny_notional=tiny_notional,
            entry_reference_price=entry_ref,
            stop_price=stop_price_val,
            tiny_side=side,
            mock_entry_order_link_id=entry_link_id,
            mock_stop_envelope_id=stop_envelope_id,
            mock_cleanup_order_link_id=cleanup_link_id,
            real_execution_allowed=False,
            real_tiny_position_implemented=False,
            current_task_real_execution_allowed=False,
            stop_endpoint_called=False,
            order_endpoint_called=False,
            no_position_modified=True,
            no_live_endpoint=True,
            no_orders_sent=True,
            no_batch_order=True,
            no_close_only_path=True,
            emergency_close_invoked=False,
            secret_value_observed=False,
            g20_policy_still_in_place=True,
            dangling_tiny_position=dangling,
            existing_position_stop_snapshot_match=existing_match,
            existing_positions_touched=existing_touched,
            blocked_gates=unique,
            failed_phase=failed_phase_out,
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


__all__ = [
    "EXISTING_POSITION_SYMBOLS",
    "DEFAULT_SELECTED_SYMBOL",
    "TRADING_STOP_PATH_REF",
    "ORDER_CREATE_PATH_REF",
    "BASE_URL_DEMO_REF",
    "MOCK_ENTRY_PREFIX",
    "MOCK_STOP_PREFIX",
    "MOCK_CLEANUP_PREFIX",
    "PHASE_0_PREFLIGHT",
    "PHASE_1_TINY_ENTRY",
    "PHASE_2_POST_FILL_AUDIT",
    "PHASE_3_STOP_ATTACH",
    "PHASE_4_PROTECTED_VERIFY",
    "PHASE_5_CLEANUP",
    "PHASE_6_FINAL_AUDIT",
    "ALL_PHASES",
    "STATUS_PREVIEW_READY",
    "STATUS_MOCK_SUCCESS",
    "STATUS_MOCK_FAIL_CLOSED",
    "STATUS_REAL_TINY_NOT_IMPLEMENTED",
    "STATUS_FAIL_CLOSED",
    "MODE_PREVIEW",
    "MODE_MOCK_LIFECYCLE",
    "MODE_REAL_TINY_POSITION",
    "MODE_FAIL_CLOSED",
    # general gates
    "GATE_READONLY_SMOKE_MISSING",
    "GATE_RECONCILIATION_MISSING",
    "GATE_PROTECTION_MISSING",
    "GATE_CONTRACT_MISSING",
    "GATE_NOOP_PLAN_MISSING",
    "GATE_SELECTED_SYMBOL_MISSING",
    "GATE_SYMBOL_COLLIDES_EXISTING_POSITION",
    "GATE_REALTIME_PRICE_GUARD_MISSING",
    "GATE_REVIEW_FAIL_CLOSED",
    "GATE_NOOP_PLAN_RECOMMENDED_PATH_MISMATCH",
    "GATE_NOOP_PLAN_NOT_READY",
    "GATE_PROTECTION_STOP_PRICE_MISSING",
    "GATE_PROTECTION_ENTRY_PRICE_MISSING",
    "GATE_TINY_QTY_NOT_DEFINED",
    "GATE_TINY_NOTIONAL_NOT_DEFINED",
    "GATE_BALANCE_INSUFFICIENT",
    "GATE_PRIOR_PROBE_FLIPPED_REAL",
    "GATE_REAL_TINY_POSITION_NOT_IMPL",
    "GATE_EXISTING_POSITIONS_MUST_NOT_TOUCH",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_LIFECYCLE_DOC_MISSING",
    # lifecycle gates
    "GATE_PREFLIGHT_FAILED",
    "GATE_TINY_ENTRY_ENVELOPE_INVALID",
    "GATE_POST_FILL_AUDIT_FAILED",
    "GATE_STOP_ATTACH_FAILED",
    "GATE_PROTECTED_VERIFY_MISMATCH",
    "GATE_CLEANUP_FAILED",
    "GATE_FINAL_AUDIT_DANGLING_POSITION",
    "GATE_FINAL_AUDIT_EXISTING_TOUCHED",
    "TinyPositionLifecycleResult",
    "DemoTinyPositionLifecycleMock",
]
