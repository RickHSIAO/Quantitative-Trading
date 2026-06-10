"""
src/demo_tiny_position_real_permission_gate.py
TASK-014W: Tiny Isolated Demo Position Real Execution Permission Gate /
           Manual Approval Checklist.

Pure-computation / mock-safe permission gate.  Produces a checklist
report that documents what would need to be in place before a future
TASK-014X / -014Y / -014Z could execute a real tiny isolated demo
position lifecycle.  This module does NOT execute anything: no
/v5/order/create, no /v5/position/trading-stop, no close-only, no
emergency close, no leverage mutation, no transfers.

Stages:

  stage_0_artifact_preflight
      Validate 6 upstream artifacts and the runtime proof envelope.
      Confirms endpoint_family=bybit_demo, account_mode=demo,
      proof_strength=STRONG, position_details_source=real_readonly,
      noop_plan.recommended_path=tiny_isolated_position_plan and
      lifecycle_mock.status=MOCK_TINY_LIFECYCLE_SUCCESS.

  stage_1_existing_position_snapshot_checklist
      Snapshot the 5 existing demo shorts.  Selected symbol must be
      disjoint from existing position symbols.  Mismatch on post-run
      stop snapshot is documented as a fail-closed manual-review path.

  stage_2_tiny_risk_cap_checklist
      Document tiny_qty / tiny_notional / entry_reference_price /
      stop_price; verify tiny_notional <= 10 USDT and that the
      protection report's selected_qty (12.2 SOL) cannot be reused
      as a real tiny qty.  Records that future real tiny qty still
      requires instrument min/step rounding verification.

  stage_3_three_step_manual_approval_checklist
      Document the three required confirm-token patterns (entry /
      stop-attach / cleanup), each independent, each gated by its
      own dry-run preview and readonly verification.

  stage_4_failure_response_checklist
      Document the four failure response paths: entry-success-but-
      stop-fail / cleanup-fail / existing-stop-mismatch / readonly-
      unavailable.  Every path ends in FAIL_CLOSED + manual review.

  stage_5_real_execution_guard
      Permanent guard: real_execution_allowed=False,
      real_tiny_position_implemented=False.  Even with
      --allow-real-tiny-position, returns
      REAL_TINY_POSITION_NOT_IMPLEMENTED with no socket opened.

Modes:
  checklist                       --- default
  real_permission_gate_dry_run    --- with --allow-real-permission-gate
  real_tiny_position_guard        --- with --allow-real-tiny-position
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
  * import scripts.execute_*
  * invoke /v5/order/create or /v5/position/trading-stop
  * lift TASK-014L sender G20 (protected_entry_policy_missing)
  * touch ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT
  * mutate leverage / transfer / withdraw / deposit
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

# Tiny notional cap (USDT) for the future real tiny position task.
TINY_NOTIONAL_CAP_USDT: float = 10.0

# Strategy-sized qty that MUST NOT be reused as real tiny qty.
STRATEGY_FULL_SIZE_QTY_REF: float = 12.2


# ---------------------------------------------------------------------------
# Stage identifiers
# ---------------------------------------------------------------------------

STAGE_0_ARTIFACT_PREFLIGHT             = "stage_0_artifact_preflight"
STAGE_1_EXISTING_POSITION_SNAPSHOT     = "stage_1_existing_position_snapshot_checklist"
STAGE_2_TINY_RISK_CAP                  = "stage_2_tiny_risk_cap_checklist"
STAGE_3_THREE_STEP_MANUAL_APPROVAL     = "stage_3_three_step_manual_approval_checklist"
STAGE_4_FAILURE_RESPONSE               = "stage_4_failure_response_checklist"
STAGE_5_REAL_EXECUTION_GUARD           = "stage_5_real_execution_guard"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_EXISTING_POSITION_SNAPSHOT,
    STAGE_2_TINY_RISK_CAP,
    STAGE_3_THREE_STEP_MANUAL_APPROVAL,
    STAGE_4_FAILURE_RESPONSE,
    STAGE_5_REAL_EXECUTION_GUARD,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_CHECKLIST_READY                 = "REAL_PERMISSION_CHECKLIST_READY"
STATUS_GATE_READY_EXEC_DISABLED        = "REAL_PERMISSION_GATE_READY_BUT_EXECUTION_DISABLED"
STATUS_REAL_TINY_NOT_IMPLEMENTED       = "REAL_TINY_POSITION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                     = "FAIL_CLOSED"

MODE_CHECKLIST                         = "checklist"
MODE_REAL_PERMISSION_GATE_DRY_RUN      = "real_permission_gate_dry_run"
MODE_REAL_TINY_POSITION_GUARD          = "real_tiny_position_guard"
MODE_FAIL_CLOSED                       = "fail_closed"


# ---------------------------------------------------------------------------
# Approval token patterns (documentation only --- never validated here)
# ---------------------------------------------------------------------------

ENTRY_TOKEN_PATTERN       = "CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SYMBOL"
STOP_ATTACH_TOKEN_PATTERN = "CONFIRM_DEMO_TINY_STOP_ATTACH_YYYYMMDD_SYMBOL"
CLEANUP_TOKEN_PATTERN     = "CONFIRM_DEMO_TINY_CLEANUP_YYYYMMDD_SYMBOL"

APPROVAL_TOKEN_PATTERNS: tuple[str, ...] = (
    ENTRY_TOKEN_PATTERN,
    STOP_ATTACH_TOKEN_PATTERN,
    CLEANUP_TOKEN_PATTERN,
)


# ---------------------------------------------------------------------------
# Expected upstream invariants (string-only constants)
# ---------------------------------------------------------------------------

EXPECTED_ENDPOINT_FAMILY        = "bybit_demo"
EXPECTED_ACCOUNT_MODE           = "demo"
EXPECTED_PROOF_STRENGTH         = "STRONG"
EXPECTED_POSITION_DETAILS_SOURCE = "real_readonly"
EXPECTED_NOOP_RECOMMENDED_PATH  = "tiny_isolated_position_plan"
EXPECTED_LIFECYCLE_STATUS       = "MOCK_TINY_LIFECYCLE_SUCCESS"


# ---------------------------------------------------------------------------
# Gate constants (18 general + 6 risk + 7 manual approval +
#                 5 failure + 5 execution guard = 41)
# ---------------------------------------------------------------------------

# General gates (G01 - G18)
GATE_READONLY_SMOKE_MISSING               = "readonly_smoke_missing"
GATE_RECONCILIATION_MISSING               = "reconciliation_missing"
GATE_PROTECTION_MISSING                   = "protection_missing"
GATE_CONTRACT_MISSING                     = "contract_missing"
GATE_NOOP_PLAN_MISSING                    = "noop_plan_missing"
GATE_LIFECYCLE_MOCK_MISSING               = "lifecycle_mock_missing"
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO       = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG            = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_COLLIDES_EXISTING    = "selected_symbol_collides_with_existing_position"
GATE_SELECTED_SYMBOL_MISSING              = "selected_symbol_missing"
GATE_LIFECYCLE_MOCK_NOT_SUCCESS           = "lifecycle_mock_status_not_success"
GATE_NOOP_RECOMMENDED_PATH_MISMATCH       = "noop_plan_recommended_path_mismatch"
GATE_CURRENT_TASK_REAL_EXECUTION_BLOCKED  = "current_task_real_execution_allowed_false"
GATE_G20_POLICY_STILL_IN_PLACE            = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                     = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                   = "no_secret_values_emitted_in_this_task"

# Risk gates (R01 - R06)
GATE_TINY_NOTIONAL_OVER_CAP               = "tiny_notional_over_cap"
GATE_TINY_QTY_NOT_POSITIVE                = "tiny_qty_not_positive"
GATE_ENTRY_REFERENCE_PRICE_NOT_POSITIVE   = "entry_reference_price_not_positive"
GATE_STOP_PRICE_NOT_POSITIVE              = "stop_price_not_positive"
GATE_INSTRUMENT_MIN_STEP_UNVERIFIED       = "future_real_tiny_qty_requires_instrument_min_step_verification"
GATE_LEVERAGE_MUTATION_FORBIDDEN          = "leverage_mutation_forbidden_in_this_task"

# Manual approval gates (A01 - A07)
GATE_THREE_STEP_APPROVAL_REQUIRED         = "three_step_manual_approval_required"
GATE_ENTRY_TOKEN_REQUIRED_FUTURE          = "entry_token_required_in_future_task"
GATE_STOP_ATTACH_TOKEN_REQUIRED_FUTURE    = "stop_attach_token_required_in_future_task"
GATE_CLEANUP_TOKEN_REQUIRED_FUTURE        = "cleanup_token_required_in_future_task"
GATE_DRY_RUN_REPORT_REQUIRED_PER_STEP     = "dry_run_report_required_before_each_real_step"
GATE_READONLY_VERIFICATION_REQUIRED_PER_STEP = "readonly_verification_required_after_each_real_step"
GATE_NO_AUTO_NEXT_STEP_AFTER_FAILURE      = "no_automatic_next_step_after_failure"

# Failure response gates (F01 - F05)
GATE_ENTRY_OK_STOP_FAIL_EMERGENCY_PREVIEW = "entry_success_stop_fail_emergency_close_preview_only"
GATE_CLEANUP_FAIL_MANUAL_REVIEW           = "cleanup_failure_manual_review_required"
GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW = "existing_stop_mismatch_manual_review_required"
GATE_READONLY_UNAVAILABLE_FAIL_CLOSED     = "readonly_verification_unavailable_fail_closed"
GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK    = "no_real_emergency_close_in_this_task"

# Execution guard gates (X01 - X05)
GATE_REAL_TINY_POSITION_NOT_IMPL          = "real_tiny_position_not_implemented"
GATE_NO_REAL_ORDER_ENDPOINT               = "no_real_order_endpoint_in_this_task"
GATE_NO_REAL_STOP_ENDPOINT                = "no_real_stop_endpoint_in_this_task"
GATE_NO_POSITION_MODIFIED                 = "no_position_modified_in_this_task"
GATE_G20_NOT_LIFTED                       = "g20_policy_not_lifted_by_this_task"


# Hard-fail-closed gates --- if ANY of these surface, the result is
# downgraded to FAIL_CLOSED regardless of other state.
_HARD_FAIL_GATES: frozenset[str] = frozenset({
    GATE_READONLY_SMOKE_MISSING,
    GATE_RECONCILIATION_MISSING,
    GATE_PROTECTION_MISSING,
    GATE_CONTRACT_MISSING,
    GATE_NOOP_PLAN_MISSING,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_LIFECYCLE_MOCK_NOT_SUCCESS,
    GATE_NOOP_RECOMMENDED_PATH_MISMATCH,
    GATE_TINY_NOTIONAL_OVER_CAP,
    GATE_TINY_QTY_NOT_POSITIVE,
    GATE_ENTRY_REFERENCE_PRICE_NOT_POSITIVE,
    GATE_STOP_PRICE_NOT_POSITIVE,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyPositionRealPermissionGateResult:
    """Read-only outcome of one permission-gate checklist pass."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    # Per-stage envelopes (string-only contents).
    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    # Risk summary fields.
    tiny_qty:                     float = 0.0
    tiny_notional:                float = 0.0
    entry_reference_price:        float = 0.0
    stop_price:                   float = 0.0
    tiny_notional_cap_usdt:       float = TINY_NOTIONAL_CAP_USDT
    within_tiny_notional_cap:     bool  = False
    strategy_full_size_qty_ref:   float = STRATEGY_FULL_SIZE_QTY_REF

    # Approval token patterns (documentation only).
    approval_token_patterns:      list[str] = field(
        default_factory=lambda: list(APPROVAL_TOKEN_PATTERNS),
    )
    three_step_approval_required: bool = True

    # Existing positions snapshot.
    existing_positions_snapshot:  list[dict[str, Any]] = field(default_factory=list)

    # Real-execution gating flags (TASK-014W keeps all of these conservative).
    real_permission_gate_dry_run_allowed: bool = False
    real_execution_allowed:       bool = False
    real_tiny_position_implemented: bool = False
    current_task_real_execution_allowed: bool = False
    # Semantic: user passed --allow-real-tiny-position (does NOT mean execution is allowed).
    real_tiny_position_requested: bool = False

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

    # Existing positions untouched.
    existing_position_stop_snapshot_match: bool = True
    existing_positions_touched:   list[str] = field(default_factory=list)

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = (
        "TASK-014X_tiny_isolated_demo_entry_permission_gate"
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
            "tiny_qty":                   self.tiny_qty,
            "tiny_notional":              self.tiny_notional,
            "entry_reference_price":      self.entry_reference_price,
            "stop_price":                 self.stop_price,
            "tiny_notional_cap_usdt":     self.tiny_notional_cap_usdt,
            "within_tiny_notional_cap":   self.within_tiny_notional_cap,
            "strategy_full_size_qty_ref": self.strategy_full_size_qty_ref,
            "approval_token_patterns":    list(self.approval_token_patterns),
            "three_step_approval_required": self.three_step_approval_required,
            "existing_positions_snapshot": [dict(row) for row in self.existing_positions_snapshot],
            "real_permission_gate_dry_run_allowed": self.real_permission_gate_dry_run_allowed,
            "real_execution_allowed":     self.real_execution_allowed,
            "real_tiny_position_implemented": self.real_tiny_position_implemented,
            "current_task_real_execution_allowed": self.current_task_real_execution_allowed,
            "real_tiny_position_requested": self.real_tiny_position_requested,
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

def _positions_from_reconciliation(
    reconciliation: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Return list of {symbol, side, qty, entry, stop} snapshots."""
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Permission gate
# ---------------------------------------------------------------------------

class DemoTinyPositionRealPermissionGate:
    """
    Pure-computation permission gate.  Reads 6 upstream JSON artifacts
    (readonly_smoke / reconciliation / protection / contract /
    noop_plan / lifecycle_mock) and emits a
    TinyPositionRealPermissionGateResult.

    Holds no network client, reads no environment variables, and never
    invokes the trading-stop or order-create endpoints.  Even when the
    caller sets --allow-real-tiny-position, this gate returns
    REAL_TINY_POSITION_NOT_IMPLEMENTED.  Even when the caller sets
    --allow-real-permission-gate, this gate only produces a checklist
    report and never executes anything.  Real execution is reserved
    for TASK-014X / -014Y / -014Z.
    """

    def __init__(self) -> None:
        pass  # No credentials, no clients, no env reads.

    def run_checklist(
        self,
        readonly_smoke:                  dict[str, Any] | None,
        reconciliation:                  dict[str, Any] | None,
        protection:                      dict[str, Any] | None,
        contract:                        dict[str, Any] | None,
        noop_plan:                       dict[str, Any] | None,
        lifecycle_mock:                  dict[str, Any] | None,
        symbol:                          str  = DEFAULT_SELECTED_SYMBOL,
        allow_real_permission_gate:      bool = False,
        allow_real_tiny_position:        bool = False,
        _now:                            datetime | None = None,
    ) -> TinyPositionRealPermissionGateResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_tiny_position:
            mode = MODE_REAL_TINY_POSITION_GUARD
        elif allow_real_permission_gate:
            mode = MODE_REAL_PERMISSION_GATE_DRY_RUN
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

        readonly_present  = isinstance(readonly_smoke, dict) and bool(readonly_smoke)
        recon_present     = isinstance(reconciliation, dict) and bool(reconciliation)
        protection_present = isinstance(protection, dict) and bool(protection)
        contract_present  = isinstance(contract, dict) and bool(contract)
        noop_present      = isinstance(noop_plan, dict) and bool(noop_plan)
        lifecycle_present = isinstance(lifecycle_mock, dict) and bool(lifecycle_mock)

        endpoint_family   = str(((readonly_smoke or {}).get(
            "endpoint_family", "")) or "").strip()
        account_mode      = str(((readonly_smoke or {}).get(
            "account_mode", "")) or "").strip()
        proof_strength    = str(((readonly_smoke or {}).get(
            "proof_strength", "")) or "").strip()
        position_details_source = str(((reconciliation or {}).get(
            "position_details_source",
            (reconciliation or {}).get("mode", ""))) or "").strip()
        noop_recommended_path = str(((noop_plan or {}).get(
            "recommended_path", "")) or "").strip()
        lifecycle_status  = str(((lifecycle_mock or {}).get(
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

        if readonly_present and endpoint_family and endpoint_family != EXPECTED_ENDPOINT_FAMILY:
            blocked.append(GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO)
        if readonly_present and account_mode and account_mode != EXPECTED_ACCOUNT_MODE:
            blocked.append(GATE_ACCOUNT_MODE_NOT_DEMO)
        if readonly_present and proof_strength and proof_strength != EXPECTED_PROOF_STRENGTH:
            blocked.append(GATE_PROOF_STRENGTH_NOT_STRONG)
        if recon_present and position_details_source and position_details_source != EXPECTED_POSITION_DETAILS_SOURCE:
            blocked.append(GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY)
        if noop_present and noop_recommended_path and noop_recommended_path != EXPECTED_NOOP_RECOMMENDED_PATH:
            blocked.append(GATE_NOOP_RECOMMENDED_PATH_MISMATCH)
        if lifecycle_present and lifecycle_status and lifecycle_status != EXPECTED_LIFECYCLE_STATUS:
            blocked.append(GATE_LIFECYCLE_MOCK_NOT_SUCCESS)

        if not sym:
            blocked.append(GATE_SELECTED_SYMBOL_MISSING)
        elif sym in existing_symbols:
            blocked.append(GATE_SELECTED_SYMBOL_COLLIDES_EXISTING)

        stage_0_envelope: dict[str, Any] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 6 upstream artifacts + runtime proof envelope.",
            "readonly_smoke_present":  readonly_present,
            "reconciliation_present":  recon_present,
            "protection_present":      protection_present,
            "contract_present":        contract_present,
            "noop_plan_present":       noop_present,
            "lifecycle_mock_present":  lifecycle_present,
            "endpoint_family_observed":          endpoint_family,
            "endpoint_family_expected":          EXPECTED_ENDPOINT_FAMILY,
            "account_mode_observed":             account_mode,
            "account_mode_expected":             EXPECTED_ACCOUNT_MODE,
            "proof_strength_observed":           proof_strength,
            "proof_strength_expected":           EXPECTED_PROOF_STRENGTH,
            "position_details_source_observed":  position_details_source,
            "position_details_source_expected":  EXPECTED_POSITION_DETAILS_SOURCE,
            "noop_recommended_path_observed":    noop_recommended_path,
            "noop_recommended_path_expected":    EXPECTED_NOOP_RECOMMENDED_PATH,
            "lifecycle_status_observed":         lifecycle_status,
            "lifecycle_status_expected":         EXPECTED_LIFECYCLE_STATUS,
            "selected_symbol":                   sym,
        }
        stages[STAGE_0_ARTIFACT_PREFLIGHT] = stage_0_envelope

        # ===============================================================
        # stage_1_existing_position_snapshot_checklist
        # ===============================================================
        snapshot_fields_ok = all(
            all(k in row for k in ("symbol", "side", "qty", "entry", "stop"))
            for row in existing_snapshot
        )
        stage_1_envelope: dict[str, Any] = {
            "stage":   STAGE_1_EXISTING_POSITION_SNAPSHOT,
            "summary": "Snapshot 5 existing demo shorts + verify selected symbol disjoint.",
            "existing_position_count":   len(existing_snapshot),
            "existing_positions_snapshot": existing_snapshot,
            "snapshot_fields_ok":        snapshot_fields_ok,
            "selected_symbol":           sym,
            "selected_symbol_disjoint":  bool(sym) and (sym not in existing_symbols),
            "post_run_stop_match_required":      True,
            "mismatch_action":                   "fail_closed_manual_review",
        }
        stages[STAGE_1_EXISTING_POSITION_SNAPSHOT] = stage_1_envelope

        # ===============================================================
        # stage_2_tiny_risk_cap_checklist
        # ===============================================================
        entry_ref      = _safe_float(
            (protection or {}).get("entry_reference_price", 0.0), 0.0,
        )
        stop_price_val = _safe_float(
            (protection or {}).get("stop_price", 0.0), 0.0,
        )
        # Tiny qty / notional come from the lifecycle mock if present;
        # otherwise we synthesise from the protection report.
        tiny_qty       = _safe_float(
            (lifecycle_mock or {}).get("tiny_qty", 0.0), 0.0,
        )
        tiny_notional  = _safe_float(
            (lifecycle_mock or {}).get("tiny_notional", 0.0), 0.0,
        )
        if tiny_qty <= 0.0 and entry_ref > 0.0:
            tiny_qty = 0.1  # default ultra-tiny qty (matches lifecycle mock)
        if tiny_notional <= 0.0:
            tiny_notional = tiny_qty * entry_ref

        within_cap = (
            tiny_notional > 0.0
            and tiny_notional <= TINY_NOTIONAL_CAP_USDT
        )

        if tiny_qty <= 0.0:
            blocked.append(GATE_TINY_QTY_NOT_POSITIVE)
        if entry_ref <= 0.0:
            blocked.append(GATE_ENTRY_REFERENCE_PRICE_NOT_POSITIVE)
        if stop_price_val <= 0.0:
            blocked.append(GATE_STOP_PRICE_NOT_POSITIVE)
        if tiny_notional > TINY_NOTIONAL_CAP_USDT:
            blocked.append(GATE_TINY_NOTIONAL_OVER_CAP)

        # Always-on risk acknowledgements (never auto-resolved here).
        blocked.append(GATE_INSTRUMENT_MIN_STEP_UNVERIFIED)
        blocked.append(GATE_LEVERAGE_MUTATION_FORBIDDEN)

        stage_2_envelope: dict[str, Any] = {
            "stage":   STAGE_2_TINY_RISK_CAP,
            "summary": "Verify ultra-tiny risk envelope; reject strategy-sized qty.",
            "selected_symbol":           sym,
            "tiny_qty":                  tiny_qty,
            "tiny_notional_usdt":        tiny_notional,
            "entry_reference_price":     entry_ref,
            "stop_price":                stop_price_val,
            "tiny_notional_cap_usdt":    TINY_NOTIONAL_CAP_USDT,
            "within_tiny_notional_cap":  within_cap,
            "strategy_full_size_qty_ref": STRATEGY_FULL_SIZE_QTY_REF,
            "strategy_full_size_qty_must_not_be_reused": True,
            "future_real_tiny_qty_requires_instrument_min_step": True,
            "leverage_mutation_forbidden_in_this_task": True,
        }
        stages[STAGE_2_TINY_RISK_CAP] = stage_2_envelope

        # ===============================================================
        # stage_3_three_step_manual_approval_checklist
        # ===============================================================
        blocked.append(GATE_THREE_STEP_APPROVAL_REQUIRED)
        blocked.append(GATE_ENTRY_TOKEN_REQUIRED_FUTURE)
        blocked.append(GATE_STOP_ATTACH_TOKEN_REQUIRED_FUTURE)
        blocked.append(GATE_CLEANUP_TOKEN_REQUIRED_FUTURE)
        blocked.append(GATE_DRY_RUN_REPORT_REQUIRED_PER_STEP)
        blocked.append(GATE_READONLY_VERIFICATION_REQUIRED_PER_STEP)
        blocked.append(GATE_NO_AUTO_NEXT_STEP_AFTER_FAILURE)

        stage_3_envelope: dict[str, Any] = {
            "stage":   STAGE_3_THREE_STEP_MANUAL_APPROVAL,
            "summary": "Three independent manual confirmation tokens required.",
            "step_a_entry": {
                "label":                "real tiny entry permission",
                "token_pattern":        ENTRY_TOKEN_PATTERN,
                "dry_run_required":     True,
                "readonly_verification_required": True,
                "future_task":          "TASK-014X_tiny_isolated_demo_entry_permission_gate",
            },
            "step_b_stop_attach": {
                "label":                "real trading-stop attach permission",
                "token_pattern":        STOP_ATTACH_TOKEN_PATTERN,
                "dry_run_required":     True,
                "readonly_verification_required": True,
                "future_task":          "TASK-014Y_tiny_isolated_demo_stop_attach_permission_gate",
            },
            "step_c_cleanup": {
                "label":                "real close-only cleanup permission",
                "token_pattern":        CLEANUP_TOKEN_PATTERN,
                "dry_run_required":     True,
                "readonly_verification_required": True,
                "future_task":          "TASK-014Z_tiny_isolated_demo_cleanup_permission_gate",
            },
            "tokens_must_be_distinct":         True,
            "no_token_validation_in_this_task": True,
            "three_step_approval_required":    True,
            "stop_next_step_on_failure":       True,
        }
        stages[STAGE_3_THREE_STEP_MANUAL_APPROVAL] = stage_3_envelope

        # ===============================================================
        # stage_4_failure_response_checklist
        # ===============================================================
        blocked.append(GATE_ENTRY_OK_STOP_FAIL_EMERGENCY_PREVIEW)
        blocked.append(GATE_CLEANUP_FAIL_MANUAL_REVIEW)
        blocked.append(GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW)
        blocked.append(GATE_READONLY_UNAVAILABLE_FAIL_CLOSED)
        blocked.append(GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK)

        stage_4_envelope: dict[str, Any] = {
            "stage":   STAGE_4_FAILURE_RESPONSE,
            "summary": "Document four failure response paths --- every path fail_closed.",
            "entry_ok_stop_fail": {
                "status":         "fail_closed",
                "next_action":    "emergency_close_preview_only",
                "auto_close":     False,
                "manual_review_required": True,
            },
            "stop_attach_ok_cleanup_fail": {
                "status":         "fail_closed",
                "dangling_tiny_position": True,
                "manual_review_required": True,
            },
            "existing_stop_mismatch": {
                "status":         "fail_closed",
                "manual_review_required": True,
            },
            "readonly_verification_unavailable": {
                "status":         "fail_closed",
                "no_further_real_actions": True,
            },
            "no_real_emergency_close_in_this_task": True,
        }
        stages[STAGE_4_FAILURE_RESPONSE] = stage_4_envelope

        # ===============================================================
        # stage_5_real_execution_guard
        # ===============================================================
        # Always-on execution guard gates.
        blocked.append(GATE_REAL_TINY_POSITION_NOT_IMPL)
        blocked.append(GATE_NO_REAL_ORDER_ENDPOINT)
        blocked.append(GATE_NO_REAL_STOP_ENDPOINT)
        blocked.append(GATE_NO_POSITION_MODIFIED)
        blocked.append(GATE_G20_NOT_LIFTED)
        # Always-on context gates (general).
        blocked.append(GATE_CURRENT_TASK_REAL_EXECUTION_BLOCKED)
        blocked.append(GATE_G20_POLICY_STILL_IN_PLACE)
        blocked.append(GATE_NO_LIVE_ENDPOINT)
        blocked.append(GATE_NO_SECRETS_EMITTED)

        stage_5_envelope: dict[str, Any] = {
            "stage":   STAGE_5_REAL_EXECUTION_GUARD,
            "summary": "Permanent execution guard --- TASK-014W never executes.",
            "real_permission_gate_dry_run_allowed": allow_real_permission_gate,
            "real_execution_allowed":               False,
            "real_tiny_position_implemented":       False,
            "current_task_real_execution_allowed":  False,
            "real_tiny_position_requested":         bool(allow_real_tiny_position),
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "no_real_order_endpoint":               True,
            "no_real_stop_endpoint":                True,
            "no_position_modified":                 True,
            "no_live_endpoint":                     True,
            "no_secrets_emitted":                   True,
        }
        stages[STAGE_5_REAL_EXECUTION_GUARD] = stage_5_envelope

        # ===============================================================
        # Status resolution
        # ===============================================================
        unique = self._dedupe(blocked)
        hard_fail = any(g in unique for g in _HARD_FAIL_GATES)

        if hard_fail:
            failed_stage = self._first_failed_stage(unique)
            status_out = STATUS_FAIL_CLOSED
            mode_out   = MODE_FAIL_CLOSED
        elif allow_real_tiny_position:
            failed_stage = ""
            status_out = STATUS_REAL_TINY_NOT_IMPLEMENTED
            mode_out   = MODE_REAL_TINY_POSITION_GUARD
        elif allow_real_permission_gate:
            failed_stage = ""
            status_out = STATUS_GATE_READY_EXEC_DISABLED
            mode_out   = MODE_REAL_PERMISSION_GATE_DRY_RUN
        else:
            failed_stage = ""
            status_out = STATUS_CHECKLIST_READY
            mode_out   = MODE_CHECKLIST

        return TinyPositionRealPermissionGateResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            tiny_qty=tiny_qty,
            tiny_notional=tiny_notional,
            entry_reference_price=entry_ref,
            stop_price=stop_price_val,
            within_tiny_notional_cap=within_cap,
            existing_positions_snapshot=existing_snapshot,
            real_permission_gate_dry_run_allowed=allow_real_permission_gate,
            real_execution_allowed=False,
            real_tiny_position_implemented=False,
            current_task_real_execution_allowed=False,
            real_tiny_position_requested=bool(allow_real_tiny_position),
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
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_LIFECYCLE_MOCK_NOT_SUCCESS,
            GATE_NOOP_RECOMMENDED_PATH_MISMATCH,
            GATE_SELECTED_SYMBOL_MISSING,
            GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
        }
        for g in blocked:
            if g in stage_0_set:
                return STAGE_0_ARTIFACT_PREFLIGHT
        stage_2_set = {
            GATE_TINY_NOTIONAL_OVER_CAP,
            GATE_TINY_QTY_NOT_POSITIVE,
            GATE_ENTRY_REFERENCE_PRICE_NOT_POSITIVE,
            GATE_STOP_PRICE_NOT_POSITIVE,
        }
        for g in blocked:
            if g in stage_2_set:
                return STAGE_2_TINY_RISK_CAP
        return ""


__all__ = [
    "EXISTING_POSITION_SYMBOLS",
    "DEFAULT_SELECTED_SYMBOL",
    "TRADING_STOP_PATH_REF",
    "ORDER_CREATE_PATH_REF",
    "BASE_URL_DEMO_REF",
    "TINY_NOTIONAL_CAP_USDT",
    "STRATEGY_FULL_SIZE_QTY_REF",
    "ENTRY_TOKEN_PATTERN",
    "STOP_ATTACH_TOKEN_PATTERN",
    "CLEANUP_TOKEN_PATTERN",
    "APPROVAL_TOKEN_PATTERNS",
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_NOOP_RECOMMENDED_PATH",
    "EXPECTED_LIFECYCLE_STATUS",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_EXISTING_POSITION_SNAPSHOT",
    "STAGE_2_TINY_RISK_CAP",
    "STAGE_3_THREE_STEP_MANUAL_APPROVAL",
    "STAGE_4_FAILURE_RESPONSE",
    "STAGE_5_REAL_EXECUTION_GUARD",
    "ALL_STAGES",
    "STATUS_CHECKLIST_READY",
    "STATUS_GATE_READY_EXEC_DISABLED",
    "STATUS_REAL_TINY_NOT_IMPLEMENTED",
    "STATUS_FAIL_CLOSED",
    "MODE_CHECKLIST",
    "MODE_REAL_PERMISSION_GATE_DRY_RUN",
    "MODE_REAL_TINY_POSITION_GUARD",
    "MODE_FAIL_CLOSED",
    # general gates
    "GATE_READONLY_SMOKE_MISSING",
    "GATE_RECONCILIATION_MISSING",
    "GATE_PROTECTION_MISSING",
    "GATE_CONTRACT_MISSING",
    "GATE_NOOP_PLAN_MISSING",
    "GATE_LIFECYCLE_MOCK_MISSING",
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_COLLIDES_EXISTING",
    "GATE_SELECTED_SYMBOL_MISSING",
    "GATE_LIFECYCLE_MOCK_NOT_SUCCESS",
    "GATE_NOOP_RECOMMENDED_PATH_MISMATCH",
    "GATE_CURRENT_TASK_REAL_EXECUTION_BLOCKED",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # risk gates
    "GATE_TINY_NOTIONAL_OVER_CAP",
    "GATE_TINY_QTY_NOT_POSITIVE",
    "GATE_ENTRY_REFERENCE_PRICE_NOT_POSITIVE",
    "GATE_STOP_PRICE_NOT_POSITIVE",
    "GATE_INSTRUMENT_MIN_STEP_UNVERIFIED",
    "GATE_LEVERAGE_MUTATION_FORBIDDEN",
    # manual approval gates
    "GATE_THREE_STEP_APPROVAL_REQUIRED",
    "GATE_ENTRY_TOKEN_REQUIRED_FUTURE",
    "GATE_STOP_ATTACH_TOKEN_REQUIRED_FUTURE",
    "GATE_CLEANUP_TOKEN_REQUIRED_FUTURE",
    "GATE_DRY_RUN_REPORT_REQUIRED_PER_STEP",
    "GATE_READONLY_VERIFICATION_REQUIRED_PER_STEP",
    "GATE_NO_AUTO_NEXT_STEP_AFTER_FAILURE",
    # failure response gates
    "GATE_ENTRY_OK_STOP_FAIL_EMERGENCY_PREVIEW",
    "GATE_CLEANUP_FAIL_MANUAL_REVIEW",
    "GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW",
    "GATE_READONLY_UNAVAILABLE_FAIL_CLOSED",
    "GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK",
    # execution guard gates
    "GATE_REAL_TINY_POSITION_NOT_IMPL",
    "GATE_NO_REAL_ORDER_ENDPOINT",
    "GATE_NO_REAL_STOP_ENDPOINT",
    "GATE_NO_POSITION_MODIFIED",
    "GATE_G20_NOT_LIFTED",
    "TinyPositionRealPermissionGateResult",
    "DemoTinyPositionRealPermissionGate",
]
