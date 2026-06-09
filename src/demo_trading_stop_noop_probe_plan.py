"""
src/demo_trading_stop_noop_probe_plan.py
TASK-014U: Real Demo Trading-stop No-op Probe Design / Tiny Isolated
           Position Plan.

Pure-computation / mock-safe design module.  Does not execute any real
probe and does not invoke /v5/position/trading-stop or /v5/order/create.

Background:
  TASK-014T documented the trading-stop contract and added a permission
  probe shell that hard-returns REAL_PROBE_NOT_IMPLEMENTED.  The
  underlying reason was: there are 5 existing demo short positions
  (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT) and any direct
  call to /v5/position/trading-stop on those symbols would mutate live
  stop-loss state.  Until a documented "no-op" path exists that
  provably cannot touch any existing position's stop_price, the real
  probe stays disabled.

This module produces the design plan:

  * Three candidate plans are described:
      1. tiny_isolated_position_plan  (RECOMMENDED next path)
      2. read_only_endpoint_research
      3. expected_error_probe
  * 33 gates classify why the real no-op probe stays disabled in this
    task, split as:
      - general              (G01 - G09)
      - tiny isolated        (G10 - G24)
      - expected-error       (G25 - G27)
      - read-only            (G28 - G30)
      - defense-in-depth     (G31 - G33)
  * Status NOOP_PROBE_PLAN_READY means the plan has been produced; it
    does NOT mean the real probe can run.
  * Status REAL_NOOP_PROBE_NOT_IMPLEMENTED is returned when the caller
    sets --allow-real-noop-probe; even with that flag and a valid
    token-shaped argument, no network call is performed.  Designing
    and executing the real no-op probe is reserved for TASK-014V+.
  * current_task_real_execution_allowed is always False in TASK-014U.

This module DOES NOT (enforced by source-scan tests):
  * import urllib / requests / httpx / socket / http.client
  * read os.environ / dotenv
  * call HMAC / signing
  * import main / src.risk / BybitExecutor / pybit / src.bybit_executor
  * import src.demo_new_entry_sender
  * import src.demo_close_only_sender
  * import src.demo_emergency_close_sender
  * import src.demo_protected_new_entry_orchestrator
  * import src.demo_trading_stop_contract_probe (avoid coupling back)
  * import scripts.execute_*
  * invoke /v5/order/create or /v5/position/trading-stop
  * lift TASK-014L sender G20 (protected_entry_policy_missing)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Known live state / defaults (string-only references; never invoked)
# ---------------------------------------------------------------------------

EXISTING_POSITION_SYMBOLS: tuple[str, ...] = (
    "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT",
)

DEFAULT_SELECTED_SYMBOL = "SOLUSDT"

TRADING_STOP_PATH_REF = "/v5/position/trading-stop"   # NOT invoked
ORDER_CREATE_PATH_REF = "/v5/order/create"            # NOT invoked
BASE_URL_DEMO_REF     = "https://api-demo.bybit.com"  # informational only


# ---------------------------------------------------------------------------
# Plan path identifiers
# ---------------------------------------------------------------------------

PATH_TINY_ISOLATED  = "tiny_isolated_position_plan"
PATH_READ_ONLY      = "read_only_endpoint_research"
PATH_EXPECTED_ERROR = "expected_error_probe"

RECOMMENDED_PATH    = PATH_TINY_ISOLATED


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_PLAN_READY        = "NOOP_PROBE_PLAN_READY"
STATUS_REAL_NOOP_NOT_IMPL = "REAL_NOOP_PROBE_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED       = "FAIL_CLOSED"

MODE_PLAN                = "plan"
MODE_REAL_NOOP_PROBE     = "real_noop_probe"


# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------

# General gates (G01 - G09)
GATE_READONLY_SMOKE_MISSING            = "readonly_smoke_missing"
GATE_RECONCILIATION_MISSING            = "reconciliation_missing"
GATE_PROTECTION_MISSING                = "protection_missing"
GATE_CONTRACT_MISSING                  = "contract_missing"
GATE_SELECTED_SYMBOL_MISSING           = "selected_symbol_missing"
GATE_SYMBOL_COLLIDES_EXISTING_POSITION = "selected_symbol_collides_with_existing_position"
GATE_REALTIME_PRICE_GUARD_MISSING      = "realtime_price_guard_missing"
GATE_REVIEW_FAIL_CLOSED                = "review_fail_closed"
GATE_PRIOR_PROBE_FLIPPED_REAL          = "prior_probe_real_implemented_unexpectedly"

# Tiny isolated position plan gates (G10 - G24)
GATE_TINY_QTY_MIN_UNKNOWN                  = "tiny_qty_below_instrument_minimum_unknown"
GATE_TINY_ISOLATION_UNVERIFIED             = "tiny_qty_isolation_unverified"
GATE_TINY_NOTIONAL_MIN_UNKNOWN             = "tiny_notional_under_minimum_unknown"
GATE_TINY_ACCOUNT_MODE_UNVERIFIED          = "tiny_isolation_account_mode_unverified"
GATE_TINY_SYMBOL_OVERLAPS_EXISTING         = "tiny_symbol_overlaps_existing_position"
GATE_TINY_SYMBOL_NOT_LINEAR_PERPETUAL      = "tiny_symbol_not_linear_perpetual"
GATE_TINY_STOP_ATTACH_WINDOW_UNCOVERED     = "tiny_entry_no_stop_attached_within_window"
GATE_TINY_EMERGENCY_CLOSE_UNVERIFIED       = "tiny_entry_emergency_close_path_unverified"
GATE_TINY_BALANCE_INSUFFICIENT_UNKNOWN     = "tiny_entry_balance_insufficient_unknown"
GATE_TINY_LEVERAGE_UNVERIFIED              = "tiny_entry_leverage_unverified"
GATE_TINY_SESSION_RESUME_UNCOVERED         = "tiny_entry_session_resume_uncovered"
GATE_TINY_MARKET_PRICE_DRIFT_UNVERIFIED    = "tiny_entry_market_price_drift_unverified"
GATE_TINY_PARTIAL_FILL_UNHANDLED           = "tiny_entry_partial_fill_unhandled"
GATE_TINY_POST_FILL_AUDIT_MISSING          = "tiny_entry_post_fill_audit_missing"
GATE_TINY_LIFECYCLE_DOC_MISSING            = "tiny_entry_lifecycle_documentation_missing"

# Expected-error plan gates (G25 - G27)
GATE_EXPECTED_ERR_IDEMPOTENCY_UNVERIFIED = "expected_error_endpoint_idempotency_unverified"
GATE_EXPECTED_ERR_MODIFIES_ON_MATCH      = "expected_error_modifies_existing_position_on_any_match"
GATE_EXPECTED_ERR_CANNOT_DISAMBIGUATE    = "expected_error_cannot_disambiguate_no_position_vs_perm_denied"

# Read-only research plan gates (G28 - G30)
GATE_READONLY_ENDPOINT_NOT_AVAILABLE     = "readonly_endpoint_does_not_exist_for_stop_permission"
GATE_READONLY_WORKAROUND_REQUIRES_WRITE  = "readonly_endpoint_workaround_requires_position_write"
GATE_READONLY_RESEARCH_INCONCLUSIVE      = "readonly_endpoint_research_inconclusive"

# Defense-in-depth gates (G31 - G33)
GATE_REAL_NOOP_PROBE_NOT_IMPL            = "real_noop_probe_not_implemented"
GATE_EXISTING_POSITIONS_MUST_NOT_TOUCH   = "existing_positions_must_not_be_touched"
GATE_G20_POLICY_STILL_IN_PLACE           = "g20_sender_policy_still_in_place"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class NoopProbePlanResult:
    """Read-only outcome of one no-op probe design pass."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    # Plan tables (string-only contents).
    plans:                        dict[str, dict[str, Any]] = field(default_factory=dict)
    plan_comparison_summary:      list[dict[str, Any]] = field(default_factory=list)

    recommended_path:             str  = RECOMMENDED_PATH

    # Real-probe gating flags (TASK-014U keeps all of these conservative).
    real_probe_allowed:           bool = False
    real_noop_probe_implemented:  bool = False
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

    blocked_gates:                list[str] = field(default_factory=list)
    status:                       str = STATUS_FAIL_CLOSED
    next_required_task:           str = (
        "TASK-014V_tiny_isolated_demo_position_lifecycle_mock"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                  self.timestamp_utc,
            "timestamp_utc":              self.timestamp_utc,
            "mode":                       self.mode,
            "selected_symbol":            self.selected_symbol,
            "existing_position_symbols":  list(self.existing_position_symbols),
            "plans":                      {k: dict(v) for k, v in self.plans.items()},
            "plan_comparison_summary":    [dict(row) for row in self.plan_comparison_summary],
            "recommended_path":           self.recommended_path,
            "real_probe_allowed":         self.real_probe_allowed,
            "real_noop_probe_implemented": self.real_noop_probe_implemented,
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
            "blocked_gates":              list(self.blocked_gates),
            "status":                     self.status,
            "next_required_task":         self.next_required_task,
        }


# ---------------------------------------------------------------------------
# Plan tables (string-only design content)
# ---------------------------------------------------------------------------

def _build_tiny_isolated_plan() -> dict[str, Any]:
    """
    The recommended next path.  Open a single, tiny, isolated demo
    position on a symbol that is NOT in EXISTING_POSITION_SYMBOLS, then
    exercise /v5/position/trading-stop against THAT position only.
    """
    return {
        "path_id":            PATH_TINY_ISOLATED,
        "label":              "Tiny isolated demo position plan",
        "recommended":        True,
        "summary": (
            "Open one tiny demo position on a symbol disjoint from the "
            "5 existing demo shorts, then exercise the trading-stop "
            "endpoint against that single, owned, isolated position."
        ),
        "required_preconditions": [
            "selected_symbol NOT in existing_position_symbols",
            "selected_symbol is a linear perpetual",
            "account is in one-way mode",
            "qty is minimum-instrument-allowed (lot-step rounded)",
            "notional is minimum-instrument-allowed",
            "available_balance covers tiny notional + buffer",
            "leverage is set to the lowest allowed value",
            "realtime price guard is verified at submission time",
            "stop_price is computed from review + protection",
            "emergency close path is wired before entry",
            "post-fill audit step is in place",
            "lifecycle documentation captures all envelope ids",
            "session-resume path documented",
            "partial-fill handling documented",
        ],
        "open_blockers_in_this_task": [
            GATE_TINY_QTY_MIN_UNKNOWN,
            GATE_TINY_ISOLATION_UNVERIFIED,
            GATE_TINY_NOTIONAL_MIN_UNKNOWN,
            GATE_TINY_ACCOUNT_MODE_UNVERIFIED,
            GATE_TINY_SYMBOL_OVERLAPS_EXISTING,
            GATE_TINY_SYMBOL_NOT_LINEAR_PERPETUAL,
            GATE_TINY_STOP_ATTACH_WINDOW_UNCOVERED,
            GATE_TINY_EMERGENCY_CLOSE_UNVERIFIED,
            GATE_TINY_BALANCE_INSUFFICIENT_UNKNOWN,
            GATE_TINY_LEVERAGE_UNVERIFIED,
            GATE_TINY_SESSION_RESUME_UNCOVERED,
            GATE_TINY_MARKET_PRICE_DRIFT_UNVERIFIED,
            GATE_TINY_PARTIAL_FILL_UNHANDLED,
            GATE_TINY_POST_FILL_AUDIT_MISSING,
            GATE_TINY_LIFECYCLE_DOC_MISSING,
        ],
        "next_task_pointer":  "TASK-014V_tiny_isolated_demo_position_lifecycle_mock",
        "touches_existing_positions": False,
        "estimated_risk":     "lowest (tiny notional, owned-only target)",
    }


def _build_read_only_plan() -> dict[str, Any]:
    """
    Research plan: look for a Bybit V5 endpoint that exposes trading-stop
    permission without writing.  As of 2026-06-10 the demo runbook does
    not document one.  This plan stays open but is not the recommended
    next step.
    """
    return {
        "path_id":            PATH_READ_ONLY,
        "label":              "Read-only endpoint research",
        "recommended":        False,
        "summary": (
            "Search Bybit V5 documentation for a read-only endpoint that "
            "reveals trading-stop permission without writing.  None is "
            "currently known; documented attempts (/v5/position/list, "
            "/v5/account/info) confirm permission only after a write."
        ),
        "required_preconditions": [
            "Bybit V5 documentation review",
            "endpoint that returns stop-loss permission flags without write",
            "endpoint coverage for one-way mode position holders",
        ],
        "open_blockers_in_this_task": [
            GATE_READONLY_ENDPOINT_NOT_AVAILABLE,
            GATE_READONLY_WORKAROUND_REQUIRES_WRITE,
            GATE_READONLY_RESEARCH_INCONCLUSIVE,
        ],
        "next_task_pointer":  "(deferred; revisit if Bybit adds a permission endpoint)",
        "touches_existing_positions": False,
        "estimated_risk":     "none (read-only) but currently infeasible",
    }


def _build_expected_error_plan() -> dict[str, Any]:
    """
    Expected-error probe: send a deliberately malformed trading-stop
    request that the server MUST reject before any state change.  Risky:
    a server-side change in idempotency / matching could cause an
    existing position to be modified.  Rejected as the next step.
    """
    return {
        "path_id":            PATH_EXPECTED_ERROR,
        "label":              "Expected-error probe",
        "recommended":        False,
        "summary": (
            "Send a deliberately malformed trading-stop request whose "
            "rejection would prove the endpoint is reachable.  Rejected "
            "because any change in server idempotency or symbol "
            "matching could cause an existing demo position's stop to "
            "be modified, and the error envelope alone cannot reliably "
            "disambiguate 'no position' from 'permission denied'."
        ),
        "required_preconditions": [
            "documented invariant that server rejects pre-write",
            "idempotency contract that excludes any matching position",
            "error envelope reliably distinguishes no-position vs perm-denied",
        ],
        "open_blockers_in_this_task": [
            GATE_EXPECTED_ERR_IDEMPOTENCY_UNVERIFIED,
            GATE_EXPECTED_ERR_MODIFIES_ON_MATCH,
            GATE_EXPECTED_ERR_CANNOT_DISAMBIGUATE,
        ],
        "next_task_pointer":  "(not pursued; risk-of-mutation too high)",
        "touches_existing_positions": True,
        "estimated_risk":     "high (could mutate existing position state)",
    }


def build_all_plans() -> dict[str, dict[str, Any]]:
    return {
        PATH_TINY_ISOLATED:  _build_tiny_isolated_plan(),
        PATH_READ_ONLY:      _build_read_only_plan(),
        PATH_EXPECTED_ERROR: _build_expected_error_plan(),
    }


def _plan_comparison_summary(
    plans: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path_id, plan in plans.items():
        out.append({
            "path_id":     path_id,
            "label":       plan["label"],
            "recommended": plan["recommended"],
            "touches_existing_positions": plan["touches_existing_positions"],
            "estimated_risk": plan["estimated_risk"],
            "open_blockers_in_this_task": list(plan["open_blockers_in_this_task"]),
        })
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _positions_from_reconciliation(reconciliation: dict[str, Any] | None) -> list[str]:
    """Extract symbols from a reconciliation report.  Falls back to the
    documented EXISTING_POSITION_SYMBOLS when reconciliation is empty."""
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


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class DemoTradingStopNoopProbePlanner:
    """
    Pure-computation no-op probe designer.  Reads four upstream JSON
    artifacts (read-only smoke / reconciliation / protection / contract)
    and emits a NoopProbePlanResult.

    Holds no network client, reads no environment variables, and never
    invokes the trading-stop or order-create endpoints.  Even when the
    caller sets --allow-real-noop-probe, the planner returns
    REAL_NOOP_PROBE_NOT_IMPLEMENTED.
    """

    def __init__(self) -> None:
        pass  # No credentials, no clients, no env reads.

    def design_plan(
        self,
        readonly_smoke:        dict[str, Any] | None,
        reconciliation:        dict[str, Any] | None,
        protection:            dict[str, Any] | None,
        contract:              dict[str, Any] | None,
        symbol:                str  = DEFAULT_SELECTED_SYMBOL,
        allow_real_noop_probe: bool = False,
        _now:                  datetime | None = None,
    ) -> NoopProbePlanResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
        mode = MODE_REAL_NOOP_PROBE if allow_real_noop_probe else MODE_PLAN

        blocked: list[str] = []

        # -- Upstream artifact presence ------------------------------------
        if not isinstance(readonly_smoke, dict) or not readonly_smoke:
            blocked.append(GATE_READONLY_SMOKE_MISSING)
        if not isinstance(reconciliation, dict) or not reconciliation:
            blocked.append(GATE_RECONCILIATION_MISSING)
        if not isinstance(protection, dict) or not protection:
            blocked.append(GATE_PROTECTION_MISSING)
        if not isinstance(contract, dict) or not contract:
            blocked.append(GATE_CONTRACT_MISSING)

        existing = _positions_from_reconciliation(reconciliation)

        sym = (symbol or "").strip()
        if not sym:
            blocked.append(GATE_SELECTED_SYMBOL_MISSING)
        elif sym in existing:
            blocked.append(GATE_SYMBOL_COLLIDES_EXISTING_POSITION)

        # Realtime price guard / review fail-closed checks (advisory).
        if isinstance(protection, dict) and protection:
            if not bool(protection.get("realtime_price_guard_verified", False)):
                blocked.append(GATE_REALTIME_PRICE_GUARD_MISSING)
            if bool(protection.get("review_fail_closed", False)):
                blocked.append(GATE_REVIEW_FAIL_CLOSED)

        # Defense-in-depth: if a previous probe ever claims the real
        # probe got implemented elsewhere, surface it here.
        if isinstance(contract, dict) and contract:
            if bool(contract.get("real_probe_implemented", False)):
                blocked.append(GATE_PRIOR_PROBE_FLIPPED_REAL)

        # Plan-level blockers always present in TASK-014U (these are the
        # work items each downstream task must resolve before the real
        # no-op probe can be implemented):
        for g in (
            # Tiny isolated plan blockers
            GATE_TINY_QTY_MIN_UNKNOWN,
            GATE_TINY_ISOLATION_UNVERIFIED,
            GATE_TINY_NOTIONAL_MIN_UNKNOWN,
            GATE_TINY_ACCOUNT_MODE_UNVERIFIED,
            GATE_TINY_SYMBOL_NOT_LINEAR_PERPETUAL,
            GATE_TINY_STOP_ATTACH_WINDOW_UNCOVERED,
            GATE_TINY_EMERGENCY_CLOSE_UNVERIFIED,
            GATE_TINY_BALANCE_INSUFFICIENT_UNKNOWN,
            GATE_TINY_LEVERAGE_UNVERIFIED,
            GATE_TINY_SESSION_RESUME_UNCOVERED,
            GATE_TINY_MARKET_PRICE_DRIFT_UNVERIFIED,
            GATE_TINY_PARTIAL_FILL_UNHANDLED,
            GATE_TINY_POST_FILL_AUDIT_MISSING,
            GATE_TINY_LIFECYCLE_DOC_MISSING,
            # Expected-error plan blockers
            GATE_EXPECTED_ERR_IDEMPOTENCY_UNVERIFIED,
            GATE_EXPECTED_ERR_MODIFIES_ON_MATCH,
            GATE_EXPECTED_ERR_CANNOT_DISAMBIGUATE,
            # Read-only research plan blockers
            GATE_READONLY_ENDPOINT_NOT_AVAILABLE,
            GATE_READONLY_WORKAROUND_REQUIRES_WRITE,
            GATE_READONLY_RESEARCH_INCONCLUSIVE,
            # Defense-in-depth (always-on safety invariants)
            GATE_EXISTING_POSITIONS_MUST_NOT_TOUCH,
            GATE_G20_POLICY_STILL_IN_PLACE,
        ):
            blocked.append(g)

        # Symbol overlap is also a per-plan block-row for the tiny path.
        if sym and sym in existing:
            blocked.append(GATE_TINY_SYMBOL_OVERLAPS_EXISTING)

        # -- --allow-real-noop-probe is hard-gated in this task ----------
        if allow_real_noop_probe:
            blocked.append(GATE_REAL_NOOP_PROBE_NOT_IMPL)

        # Dedupe while preserving order.
        seen: set[str] = set()
        unique_blocks: list[str] = []
        for g in blocked:
            if g not in seen:
                unique_blocks.append(g)
                seen.add(g)

        # Hard fail-closed conditions: any upstream missing OR symbol
        # missing/collision => FAIL_CLOSED.
        hard_fail = any(g in unique_blocks for g in (
            GATE_READONLY_SMOKE_MISSING,
            GATE_RECONCILIATION_MISSING,
            GATE_PROTECTION_MISSING,
            GATE_CONTRACT_MISSING,
            GATE_SELECTED_SYMBOL_MISSING,
            GATE_SYMBOL_COLLIDES_EXISTING_POSITION,
        ))

        plans = build_all_plans()
        summary = _plan_comparison_summary(plans)

        if hard_fail:
            return NoopProbePlanResult(
                timestamp_utc=ts_utc,
                mode=mode,
                selected_symbol=sym,
                existing_position_symbols=existing,
                plans=plans,
                plan_comparison_summary=summary,
                recommended_path=RECOMMENDED_PATH,
                real_probe_allowed=allow_real_noop_probe,
                real_noop_probe_implemented=False,
                current_task_real_execution_allowed=False,
                stop_endpoint_called=False,
                order_endpoint_called=False,
                no_position_modified=True,
                no_live_endpoint=True,
                no_orders_sent=True,
                blocked_gates=unique_blocks,
                status=STATUS_FAIL_CLOSED,
            )

        if allow_real_noop_probe:
            return NoopProbePlanResult(
                timestamp_utc=ts_utc,
                mode=MODE_REAL_NOOP_PROBE,
                selected_symbol=sym,
                existing_position_symbols=existing,
                plans=plans,
                plan_comparison_summary=summary,
                recommended_path=RECOMMENDED_PATH,
                real_probe_allowed=True,
                real_noop_probe_implemented=False,
                current_task_real_execution_allowed=False,
                stop_endpoint_called=False,
                order_endpoint_called=False,
                no_position_modified=True,
                no_live_endpoint=True,
                no_orders_sent=True,
                blocked_gates=unique_blocks,
                status=STATUS_REAL_NOOP_NOT_IMPL,
            )

        # Default: plan ready (still real_execution_allowed=False).
        return NoopProbePlanResult(
            timestamp_utc=ts_utc,
            mode=MODE_PLAN,
            selected_symbol=sym,
            existing_position_symbols=existing,
            plans=plans,
            plan_comparison_summary=summary,
            recommended_path=RECOMMENDED_PATH,
            real_probe_allowed=False,
            real_noop_probe_implemented=False,
            current_task_real_execution_allowed=False,
            stop_endpoint_called=False,
            order_endpoint_called=False,
            no_position_modified=True,
            no_live_endpoint=True,
            no_orders_sent=True,
            blocked_gates=unique_blocks,
            status=STATUS_PLAN_READY,
        )


__all__ = [
    "EXISTING_POSITION_SYMBOLS",
    "DEFAULT_SELECTED_SYMBOL",
    "TRADING_STOP_PATH_REF",
    "ORDER_CREATE_PATH_REF",
    "BASE_URL_DEMO_REF",
    "PATH_TINY_ISOLATED",
    "PATH_READ_ONLY",
    "PATH_EXPECTED_ERROR",
    "RECOMMENDED_PATH",
    "STATUS_PLAN_READY",
    "STATUS_REAL_NOOP_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_PLAN",
    "MODE_REAL_NOOP_PROBE",
    # general gates
    "GATE_READONLY_SMOKE_MISSING",
    "GATE_RECONCILIATION_MISSING",
    "GATE_PROTECTION_MISSING",
    "GATE_CONTRACT_MISSING",
    "GATE_SELECTED_SYMBOL_MISSING",
    "GATE_SYMBOL_COLLIDES_EXISTING_POSITION",
    "GATE_REALTIME_PRICE_GUARD_MISSING",
    "GATE_REVIEW_FAIL_CLOSED",
    "GATE_PRIOR_PROBE_FLIPPED_REAL",
    # tiny isolated
    "GATE_TINY_QTY_MIN_UNKNOWN",
    "GATE_TINY_ISOLATION_UNVERIFIED",
    "GATE_TINY_NOTIONAL_MIN_UNKNOWN",
    "GATE_TINY_ACCOUNT_MODE_UNVERIFIED",
    "GATE_TINY_SYMBOL_OVERLAPS_EXISTING",
    "GATE_TINY_SYMBOL_NOT_LINEAR_PERPETUAL",
    "GATE_TINY_STOP_ATTACH_WINDOW_UNCOVERED",
    "GATE_TINY_EMERGENCY_CLOSE_UNVERIFIED",
    "GATE_TINY_BALANCE_INSUFFICIENT_UNKNOWN",
    "GATE_TINY_LEVERAGE_UNVERIFIED",
    "GATE_TINY_SESSION_RESUME_UNCOVERED",
    "GATE_TINY_MARKET_PRICE_DRIFT_UNVERIFIED",
    "GATE_TINY_PARTIAL_FILL_UNHANDLED",
    "GATE_TINY_POST_FILL_AUDIT_MISSING",
    "GATE_TINY_LIFECYCLE_DOC_MISSING",
    # expected-error
    "GATE_EXPECTED_ERR_IDEMPOTENCY_UNVERIFIED",
    "GATE_EXPECTED_ERR_MODIFIES_ON_MATCH",
    "GATE_EXPECTED_ERR_CANNOT_DISAMBIGUATE",
    # read-only research
    "GATE_READONLY_ENDPOINT_NOT_AVAILABLE",
    "GATE_READONLY_WORKAROUND_REQUIRES_WRITE",
    "GATE_READONLY_RESEARCH_INCONCLUSIVE",
    # defense-in-depth
    "GATE_REAL_NOOP_PROBE_NOT_IMPL",
    "GATE_EXISTING_POSITIONS_MUST_NOT_TOUCH",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "NoopProbePlanResult",
    "DemoTradingStopNoopProbePlanner",
    "build_all_plans",
]
