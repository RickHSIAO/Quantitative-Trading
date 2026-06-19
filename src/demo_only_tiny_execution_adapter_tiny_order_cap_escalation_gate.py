"""TASK-014BM_CAP_ESCALATION_GATE -- demo-only SOLUSDT cap escalation gate.

Stage 1, decision-only, demo-only **authorization gate** that records
whether Rick has explicitly opted in to placing **one** Bybit Demo
SOLUSDT tiny order at the exchange-minimum quantity surfaced by
TASK-014BM_MIN_QTY_FIX (``InstrumentRulesReport``) when that minimum is
above the original tiny safety caps
(``TINY_QTY_CAP_SOL=0.05`` / ``TINY_SIZE_CAP_USDT=5``).

This module is **NOT** an execution path. It does not send any order,
does not call ``/v5/order/create``, does not touch live endpoints, does
not read any secrets, does not retry, does not run a scheduler. It only
returns an ``EscalationAuthorizationDecision`` that callers (and the BM
``ExecutionReport``) can surface for visibility.

Hard safety invariants (cross-checked by tests):
    * **No order endpoint call.** This module has no sender, no
      ``urllib.request`` call. It never references ``/v5/order/create``,
      ``/v5/order/cancel``, ``/v5/position/*``, or any live host outside
      the documented denylist constants.
    * **Decision-only.** ``run_cap_escalation_gate`` returns a frozen
      ``CapEscalationGateReport``. No state mutation occurs outside the
      report writer.
    * **Default fail-closed.** Every reject path returns
      ``authorized=False`` and ``cap_escalated_demo_only=False``. The
      ``explicit_demo_min_qty_cap_authorized`` flag is the **only** way
      to lift the original tiny caps for this single SOLUSDT demo path.
    * **Symbol locked to SOLUSDT.** Any other symbol (including
      protected symbols ENA / TIA / AIXBT / POLYX / EDU) is rejected
      before any other check.
    * **Environment locked to bybit_demo.** Any other environment is
      rejected.
    * **Side locked to Buy.** No Sell, no reduce-only, no close.
    * **Order type locked to Market.** Time-in-force locked to IOC.
    * **Max order count = 1.** Higher counts rejected.
    * **No stop / TP / SL.** Any non-empty stop_loss / take_profit
      attachments are rejected.
    * **Notional cap = 20 USDT.** ``max_demo_min_qty_notional_cap_usdt``
      defaults to ``Decimal("20")`` -- candidate_notional must be
      ``<=`` this cap. Higher notionals fail closed.
    * **No silent global tiny cap lift.** This module never writes to
      ``TINY_QTY_CAP_SOL`` / ``TINY_SIZE_CAP_USDT`` in BH; those
      constants stay at their original 0.05 / 5 values. The escalation
      is purely narrow to this single SOLUSDT demo path and is
      explicitly marked ``cap_escalated_demo_only=True`` only when
      authorization succeeds.
    * **No live secrets.** No ``BYBIT_API_KEY`` / ``BYBIT_API_SECRET`` /
      ``BYBIT_DEMO_API_KEY`` / ``BYBIT_DEMO_API_SECRET`` reference.
    * **No mutation of main.py / src/risk.py / BybitExecutor.**
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from src import demo_only_tiny_execution_adapter as bh

# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------

TASK_ID = "TASK-014BM_CAP_ESCALATION_GATE"
IDENTITY = "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-CAP-ESCALATION-GATE"
IMPLEMENTATION_PATH_PHASE = "tiny_order_cap_escalation_gate"
IS_REVIEW_CHAIN_SUFFIX = False
UPSTREAM_TASKS: tuple[str, ...] = (
    "TASK-014BH",
    "TASK-014BM",
    "TASK-014BM_FIX",
    "TASK-014BM_MIN_QTY_FIX",
)
NEXT_REQUIRED_TASK = "TASK-014BN_demo_only_tiny_execution_postfill_audit"

REPORT_NAME = "demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate"
DEFAULT_OUTPUT_DIR = pathlib.Path("outputs/demo_trading") / REPORT_NAME

CAP_ESCALATION_GATE_CONTRACT_VERSION = (
    "demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate_v1"
)

# Re-assert at import time that this task pointer is not a review-chain suffix.
bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)


# ---------------------------------------------------------------------------
# Strict immutable constants
# ---------------------------------------------------------------------------

ALLOWED_ENVIRONMENT = bh.ALLOWED_ENVIRONMENT  # "bybit_demo"
ALLOWED_SYMBOL = bh.ALLOWED_SYMBOL  # "SOLUSDT"
ALLOWED_SIDE = "Buy"
ALLOWED_ORDER_TYPE = bh.ALLOWED_ORDER_TYPE  # "Market"
ALLOWED_TIME_IN_FORCE = bh.ALLOWED_TIME_IN_FORCE  # "IOC"
ALLOWED_MAX_ORDER_COUNT = 1

# The narrow demo-only ceiling for the SOLUSDT exchange-minimum path.
# This is INTENTIONALLY larger than ``TINY_SIZE_CAP_USDT=5`` to allow the
# exchange minimum (~10 USDT at mark_price=100), but is still tightly
# bounded so a flash-quote spike cannot let a small-cap escalation balloon.
MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT = Decimal("20")

# The single explicit authorization marker. Callers must supply this exact
# string (or its constant) via the CLI / call kwarg to lift the original
# tiny caps for this single SOLUSDT demo path.
EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_FLAG_NAME = (
    "--i-understand-demo-solusdt-exchange-min-qty-exceeds-old-tiny-cap"
)
EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER = (
    "DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1"
)

# Forbidden tokens cross-checked by tests. This module never constructs
# any URL, but any non-empty endpoint hint passed in by the caller is
# scanned for these tokens as defense-in-depth.
FORBIDDEN_URL_TOKENS: tuple[str, ...] = (
    "/v5/order/create",
    "/v5/order/cancel",
    "/v5/position/set-trading-stop",
    "https://api.bybit.com",
    "https://api.bytick.com",
    "wss://stream.bybit.com",
    "wss://stream.bytick.com",
)

# Gate decision status values.
STATUS_ESCALATION_NOT_REQUIRED = "ESCALATION_NOT_REQUIRED"
STATUS_ESCALATION_AUTHORIZED = "ESCALATION_AUTHORIZED"
STATUS_ESCALATION_NOT_AUTHORIZED = "ESCALATION_NOT_AUTHORIZED"
STATUS_ESCALATION_REJECTED_NOTIONAL_OVER_CAP = (
    "ESCALATION_REJECTED_NOTIONAL_OVER_CAP"
)
STATUS_ESCALATION_REJECTED_WRONG_SYMBOL = (
    "ESCALATION_REJECTED_WRONG_SYMBOL"
)
STATUS_ESCALATION_REJECTED_WRONG_ENVIRONMENT = (
    "ESCALATION_REJECTED_WRONG_ENVIRONMENT"
)
STATUS_ESCALATION_REJECTED_WRONG_SIDE = "ESCALATION_REJECTED_WRONG_SIDE"
STATUS_ESCALATION_REJECTED_LIVE_ENDPOINT = (
    "ESCALATION_REJECTED_LIVE_ENDPOINT"
)
STATUS_ESCALATION_REJECTED_PROTECTED_SYMBOL = (
    "ESCALATION_REJECTED_PROTECTED_SYMBOL"
)
STATUS_ESCALATION_REJECTED_QTY_MISMATCH = (
    "ESCALATION_REJECTED_QTY_MISMATCH"
)
STATUS_ESCALATION_REJECTED_MAX_ORDER_COUNT = (
    "ESCALATION_REJECTED_MAX_ORDER_COUNT"
)
STATUS_ESCALATION_REJECTED_DISALLOWED_ORDER_TYPE = (
    "ESCALATION_REJECTED_DISALLOWED_ORDER_TYPE"
)
STATUS_ESCALATION_REJECTED_DISALLOWED_TIF = (
    "ESCALATION_REJECTED_DISALLOWED_TIF"
)
STATUS_ESCALATION_REJECTED_REDUCE_ONLY = (
    "ESCALATION_REJECTED_REDUCE_ONLY"
)
STATUS_ESCALATION_REJECTED_TPSL = "ESCALATION_REJECTED_TPSL"
STATUS_ESCALATION_REJECTED_INVALID_RULES = (
    "ESCALATION_REJECTED_INVALID_RULES"
)
STATUS_ESCALATION_REJECTED_RULES_NOT_LOADED = (
    "ESCALATION_REJECTED_RULES_NOT_LOADED"
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CapEscalationGateError(bh.DemoOnlyTinyExecutionAdapterError):
    """Raised when the cap escalation gate contract is violated."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EscalationAuthorizationRequest:
    """Caller-supplied authorization request payload (decision-only).

    All fields default to the conservative-rejection baseline (no
    authorization, no escalation). Callers pass an
    ``InstrumentRulesReport`` separately to ``run_cap_escalation_gate``;
    this dataclass only carries the *human-supplied* authorization
    intent and proposed order parameters.
    """

    environment: str = ALLOWED_ENVIRONMENT
    symbol: str = ALLOWED_SYMBOL
    side: str = ALLOWED_SIDE
    order_type: str = ALLOWED_ORDER_TYPE
    time_in_force: str = ALLOWED_TIME_IN_FORCE
    proposed_qty: str = ""
    max_order_count: int = ALLOWED_MAX_ORDER_COUNT
    reduce_only: bool = False
    close_on_trigger: bool = False
    stop_loss: str = ""
    take_profit: str = ""
    endpoint_url_hint: str = ""
    explicit_demo_min_qty_cap_authorization_flag: bool = False
    explicit_demo_min_qty_cap_authorization_marker: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "proposed_qty": self.proposed_qty,
            "max_order_count": self.max_order_count,
            "reduce_only": self.reduce_only,
            "close_on_trigger": self.close_on_trigger,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "endpoint_url_hint": self.endpoint_url_hint,
            "explicit_demo_min_qty_cap_authorization_flag": (
                self.explicit_demo_min_qty_cap_authorization_flag
            ),
            "explicit_demo_min_qty_cap_authorization_marker": (
                self.explicit_demo_min_qty_cap_authorization_marker
            ),
        }


@dataclass(frozen=True)
class EscalationAuthorizationDecision:
    """Frozen decision record produced by the gate."""

    status: str
    authorized: bool
    original_tiny_cap_passed: bool
    exchange_min_qty_cap_escalation_required: bool
    explicit_demo_min_qty_cap_authorized: bool
    cap_escalated_demo_only: bool
    candidate_qty: str
    candidate_notional: str
    proposed_qty: str
    mark_price_used: str
    tiny_qty_cap_sol: str
    tiny_size_cap_usdt: str
    max_demo_min_qty_notional_cap_usdt: str
    environment: str
    symbol: str
    side: str
    order_type: str
    time_in_force: str
    max_order_count: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "authorized": self.authorized,
            "original_tiny_cap_passed": self.original_tiny_cap_passed,
            "exchange_min_qty_cap_escalation_required": (
                self.exchange_min_qty_cap_escalation_required
            ),
            "explicit_demo_min_qty_cap_authorized": (
                self.explicit_demo_min_qty_cap_authorized
            ),
            "cap_escalated_demo_only": self.cap_escalated_demo_only,
            "candidate_qty": self.candidate_qty,
            "candidate_notional": self.candidate_notional,
            "proposed_qty": self.proposed_qty,
            "mark_price_used": self.mark_price_used,
            "tiny_qty_cap_sol": self.tiny_qty_cap_sol,
            "tiny_size_cap_usdt": self.tiny_size_cap_usdt,
            "max_demo_min_qty_notional_cap_usdt": (
                self.max_demo_min_qty_notional_cap_usdt
            ),
            "environment": self.environment,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "max_order_count": self.max_order_count,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CapEscalationGateReport:
    task_id: str
    identity: str
    phase: str
    upstream_tasks: tuple[str, ...]
    next_required_task: str
    is_review_chain_suffix: bool
    cap_escalation_gate_contract_version: str
    allowed_environment: str
    allowed_symbol: str
    allowed_side: str
    allowed_order_type: str
    allowed_time_in_force: str
    allowed_max_order_count: int
    explicit_authorization_flag_name: str
    explicit_authorization_marker: str
    max_demo_min_qty_notional_cap_usdt: str
    network_attempted: bool
    order_endpoint_called: bool
    order_sent: bool
    instrument_rules_loaded: bool
    instrument_rules_discovery_status: str
    request: EscalationAuthorizationRequest
    decision: EscalationAuthorizationDecision
    generated_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "identity": self.identity,
            "phase": self.phase,
            "upstream_tasks": list(self.upstream_tasks),
            "next_required_task": self.next_required_task,
            "is_review_chain_suffix": self.is_review_chain_suffix,
            "cap_escalation_gate_contract_version": (
                self.cap_escalation_gate_contract_version
            ),
            "allowed_environment": self.allowed_environment,
            "allowed_symbol": self.allowed_symbol,
            "allowed_side": self.allowed_side,
            "allowed_order_type": self.allowed_order_type,
            "allowed_time_in_force": self.allowed_time_in_force,
            "allowed_max_order_count": self.allowed_max_order_count,
            "explicit_authorization_flag_name": (
                self.explicit_authorization_flag_name
            ),
            "explicit_authorization_marker": self.explicit_authorization_marker,
            "max_demo_min_qty_notional_cap_usdt": (
                self.max_demo_min_qty_notional_cap_usdt
            ),
            "network_attempted": self.network_attempted,
            "order_endpoint_called": self.order_endpoint_called,
            "order_sent": self.order_sent,
            "instrument_rules_loaded": self.instrument_rules_loaded,
            "instrument_rules_discovery_status": (
                self.instrument_rules_discovery_status
            ),
            "request": self.request.to_dict(),
            "decision": self.decision.to_dict(),
            "generated_at_utc": self.generated_at_utc,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _build_decision(
    *,
    status: str,
    authorized: bool,
    original_tiny_cap_passed: bool,
    exchange_min_qty_cap_escalation_required: bool,
    explicit_demo_min_qty_cap_authorized: bool,
    cap_escalated_demo_only: bool,
    request: EscalationAuthorizationRequest,
    candidate_qty: str,
    candidate_notional: str,
    mark_price_used: str,
    tiny_qty_cap_sol: str,
    tiny_size_cap_usdt: str,
    notional_cap: Decimal,
    reason: str,
) -> EscalationAuthorizationDecision:
    return EscalationAuthorizationDecision(
        status=status,
        authorized=authorized,
        original_tiny_cap_passed=original_tiny_cap_passed,
        exchange_min_qty_cap_escalation_required=(
            exchange_min_qty_cap_escalation_required
        ),
        explicit_demo_min_qty_cap_authorized=(
            explicit_demo_min_qty_cap_authorized
        ),
        cap_escalated_demo_only=cap_escalated_demo_only,
        candidate_qty=candidate_qty,
        candidate_notional=candidate_notional,
        proposed_qty=request.proposed_qty,
        mark_price_used=mark_price_used,
        tiny_qty_cap_sol=tiny_qty_cap_sol,
        tiny_size_cap_usdt=tiny_size_cap_usdt,
        max_demo_min_qty_notional_cap_usdt=format(notional_cap, "f"),
        environment=request.environment,
        symbol=request.symbol,
        side=request.side,
        order_type=request.order_type,
        time_in_force=request.time_in_force,
        max_order_count=request.max_order_count,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Public gate entry point
# ---------------------------------------------------------------------------


def run_cap_escalation_gate(
    *,
    instrument_rules_report: Any | None,
    request: EscalationAuthorizationRequest | None = None,
    max_demo_min_qty_notional_cap_usdt: Decimal | str | None = None,
) -> CapEscalationGateReport:
    """Evaluate the demo-only SOLUSDT cap escalation authorization gate.

    ``instrument_rules_report`` is expected to be an
    ``InstrumentRulesReport`` produced by
    ``TASK-014BM_MIN_QTY_FIX``. Only its ``rules`` and ``candidate``
    sub-objects (and their fields ``min_order_qty`` / ``qty_step`` /
    ``min_notional_value`` / ``candidate_qty`` / ``candidate_notional`` /
    ``mark_price_used`` / ``is_executable_under_tiny_caps`` /
    ``tiny_qty_cap_sol`` / ``tiny_size_cap_usdt``) are read via
    ``getattr``; no signing, no network, no order.

    ``request`` carries Rick's authorization intent plus the proposed
    order parameters. When omitted the gate defaults to fail-closed
    (no authorization, no escalation).
    """

    req = request if request is not None else EscalationAuthorizationRequest()
    notional_cap = _decimal_or_none(max_demo_min_qty_notional_cap_usdt)
    if notional_cap is None or notional_cap <= 0:
        notional_cap = MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT

    discovery_status = ""
    rules_loaded = False
    candidate_qty_str = ""
    candidate_notional_str = ""
    mark_price_used = ""
    tiny_qty_cap_sol_str = format(bh.TINY_QTY_CAP_SOL, "f")
    tiny_size_cap_usdt_str = format(bh.TINY_SIZE_CAP_USDT, "f")
    is_executable_under_tiny_caps = False
    rules_obj = None
    candidate_obj = None

    if instrument_rules_report is not None:
        discovery_status = str(
            getattr(instrument_rules_report, "discovery_status", "") or ""
        )
        rules_loaded = bool(
            getattr(instrument_rules_report, "instrument_rules_loaded", False)
        )
        rules_obj = getattr(instrument_rules_report, "rules", None)
        candidate_obj = getattr(instrument_rules_report, "candidate", None)
        if candidate_obj is not None:
            candidate_qty_str = str(
                getattr(candidate_obj, "candidate_qty", "") or ""
            )
            candidate_notional_str = str(
                getattr(candidate_obj, "candidate_notional", "") or ""
            )
            mark_price_used = str(
                getattr(candidate_obj, "mark_price_used", "") or ""
            )
            tiny_qty_cap_sol_str = str(
                getattr(candidate_obj, "tiny_qty_cap_sol", "")
                or tiny_qty_cap_sol_str
            )
            tiny_size_cap_usdt_str = str(
                getattr(candidate_obj, "tiny_size_cap_usdt", "")
                or tiny_size_cap_usdt_str
            )
            is_executable_under_tiny_caps = bool(
                getattr(
                    candidate_obj, "is_executable_under_tiny_caps", False
                )
            )

    # Defense-in-depth: any non-empty endpoint hint is scanned for
    # forbidden tokens. The gate itself does not contact the network.
    if req.endpoint_url_hint:
        for token in FORBIDDEN_URL_TOKENS:
            if token in req.endpoint_url_hint:
                decision = _build_decision(
                    status=STATUS_ESCALATION_REJECTED_LIVE_ENDPOINT,
                    authorized=False,
                    original_tiny_cap_passed=is_executable_under_tiny_caps,
                    exchange_min_qty_cap_escalation_required=(
                        not is_executable_under_tiny_caps and rules_loaded
                    ),
                    explicit_demo_min_qty_cap_authorized=False,
                    cap_escalated_demo_only=False,
                    request=req,
                    candidate_qty=candidate_qty_str,
                    candidate_notional=candidate_notional_str,
                    mark_price_used=mark_price_used,
                    tiny_qty_cap_sol=tiny_qty_cap_sol_str,
                    tiny_size_cap_usdt=tiny_size_cap_usdt_str,
                    notional_cap=notional_cap,
                    reason=(
                        f"endpoint_url_hint {req.endpoint_url_hint!r} "
                        f"contains forbidden token {token!r}"
                    ),
                )
                return _wrap_report(
                    req,
                    decision,
                    notional_cap,
                    rules_loaded,
                    discovery_status,
                )

    # Environment lock.
    if req.environment != ALLOWED_ENVIRONMENT:
        decision = _build_decision(
            status=STATUS_ESCALATION_REJECTED_WRONG_ENVIRONMENT,
            authorized=False,
            original_tiny_cap_passed=is_executable_under_tiny_caps,
            exchange_min_qty_cap_escalation_required=(
                not is_executable_under_tiny_caps and rules_loaded
            ),
            explicit_demo_min_qty_cap_authorized=False,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                f"environment {req.environment!r} not allowed; expected "
                f"{ALLOWED_ENVIRONMENT!r}"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    # Protected symbols hard reject.
    if req.symbol in bh.PROTECTED_SYMBOLS:
        decision = _build_decision(
            status=STATUS_ESCALATION_REJECTED_PROTECTED_SYMBOL,
            authorized=False,
            original_tiny_cap_passed=False,
            exchange_min_qty_cap_escalation_required=False,
            explicit_demo_min_qty_cap_authorized=False,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                f"symbol {req.symbol!r} is a protected position; never "
                f"escalate"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    # Symbol lock (SOLUSDT only).
    if req.symbol != ALLOWED_SYMBOL:
        decision = _build_decision(
            status=STATUS_ESCALATION_REJECTED_WRONG_SYMBOL,
            authorized=False,
            original_tiny_cap_passed=is_executable_under_tiny_caps,
            exchange_min_qty_cap_escalation_required=(
                not is_executable_under_tiny_caps and rules_loaded
            ),
            explicit_demo_min_qty_cap_authorized=False,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                f"symbol {req.symbol!r} not allowed; expected "
                f"{ALLOWED_SYMBOL!r}"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    # Side / order_type / TIF locks.
    if req.side != ALLOWED_SIDE:
        decision = _build_decision(
            status=STATUS_ESCALATION_REJECTED_WRONG_SIDE,
            authorized=False,
            original_tiny_cap_passed=is_executable_under_tiny_caps,
            exchange_min_qty_cap_escalation_required=(
                not is_executable_under_tiny_caps and rules_loaded
            ),
            explicit_demo_min_qty_cap_authorized=False,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                f"side {req.side!r} not allowed; expected "
                f"{ALLOWED_SIDE!r}"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    if req.order_type != ALLOWED_ORDER_TYPE:
        decision = _build_decision(
            status=STATUS_ESCALATION_REJECTED_DISALLOWED_ORDER_TYPE,
            authorized=False,
            original_tiny_cap_passed=is_executable_under_tiny_caps,
            exchange_min_qty_cap_escalation_required=(
                not is_executable_under_tiny_caps and rules_loaded
            ),
            explicit_demo_min_qty_cap_authorized=False,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                f"order_type {req.order_type!r} not allowed; expected "
                f"{ALLOWED_ORDER_TYPE!r}"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    if req.time_in_force != ALLOWED_TIME_IN_FORCE:
        decision = _build_decision(
            status=STATUS_ESCALATION_REJECTED_DISALLOWED_TIF,
            authorized=False,
            original_tiny_cap_passed=is_executable_under_tiny_caps,
            exchange_min_qty_cap_escalation_required=(
                not is_executable_under_tiny_caps and rules_loaded
            ),
            explicit_demo_min_qty_cap_authorized=False,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                f"time_in_force {req.time_in_force!r} not allowed; expected "
                f"{ALLOWED_TIME_IN_FORCE!r}"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    # Reduce-only / close / TP / SL hard reject.
    if req.reduce_only or req.close_on_trigger:
        decision = _build_decision(
            status=STATUS_ESCALATION_REJECTED_REDUCE_ONLY,
            authorized=False,
            original_tiny_cap_passed=is_executable_under_tiny_caps,
            exchange_min_qty_cap_escalation_required=(
                not is_executable_under_tiny_caps and rules_loaded
            ),
            explicit_demo_min_qty_cap_authorized=False,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                f"reduce_only={req.reduce_only} / close_on_trigger="
                f"{req.close_on_trigger} not allowed on this entry"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    if req.stop_loss or req.take_profit:
        decision = _build_decision(
            status=STATUS_ESCALATION_REJECTED_TPSL,
            authorized=False,
            original_tiny_cap_passed=is_executable_under_tiny_caps,
            exchange_min_qty_cap_escalation_required=(
                not is_executable_under_tiny_caps and rules_loaded
            ),
            explicit_demo_min_qty_cap_authorized=False,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                f"stop_loss={req.stop_loss!r} / take_profit="
                f"{req.take_profit!r} not allowed on this entry"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    # Max order count lock.
    if req.max_order_count != ALLOWED_MAX_ORDER_COUNT:
        decision = _build_decision(
            status=STATUS_ESCALATION_REJECTED_MAX_ORDER_COUNT,
            authorized=False,
            original_tiny_cap_passed=is_executable_under_tiny_caps,
            exchange_min_qty_cap_escalation_required=(
                not is_executable_under_tiny_caps and rules_loaded
            ),
            explicit_demo_min_qty_cap_authorized=False,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                f"max_order_count={req.max_order_count} not allowed; "
                f"expected {ALLOWED_MAX_ORDER_COUNT}"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    # Need loaded rules + computed candidate to make any decision past here.
    if not rules_loaded or candidate_obj is None:
        decision = _build_decision(
            status=STATUS_ESCALATION_REJECTED_RULES_NOT_LOADED,
            authorized=False,
            original_tiny_cap_passed=False,
            exchange_min_qty_cap_escalation_required=False,
            explicit_demo_min_qty_cap_authorized=False,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                "instrument rules not loaded; cannot evaluate cap "
                "escalation without exchange minimum"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    candidate_qty_dec = _decimal_or_none(candidate_qty_str)
    candidate_notional_dec = _decimal_or_none(candidate_notional_str)
    if (
        candidate_qty_dec is None
        or candidate_qty_dec <= 0
        or candidate_notional_dec is None
        or candidate_notional_dec <= 0
    ):
        decision = _build_decision(
            status=STATUS_ESCALATION_REJECTED_INVALID_RULES,
            authorized=False,
            original_tiny_cap_passed=False,
            exchange_min_qty_cap_escalation_required=False,
            explicit_demo_min_qty_cap_authorized=False,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                f"invalid candidate qty/notional: qty={candidate_qty_str!r} "
                f"notional={candidate_notional_str!r}"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    # Proposed qty must exactly equal the candidate qty (no manual fudge).
    proposed_qty_dec = _decimal_or_none(req.proposed_qty)
    if proposed_qty_dec is None or proposed_qty_dec != candidate_qty_dec:
        decision = _build_decision(
            status=STATUS_ESCALATION_REJECTED_QTY_MISMATCH,
            authorized=False,
            original_tiny_cap_passed=is_executable_under_tiny_caps,
            exchange_min_qty_cap_escalation_required=(
                not is_executable_under_tiny_caps
            ),
            explicit_demo_min_qty_cap_authorized=False,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                f"proposed_qty {req.proposed_qty!r} != candidate_qty "
                f"{candidate_qty_str!r}; only the exchange-minimum candidate "
                f"qty may be authorized"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    # If the original tiny cap already passes, no escalation is needed.
    if is_executable_under_tiny_caps:
        decision = _build_decision(
            status=STATUS_ESCALATION_NOT_REQUIRED,
            authorized=False,
            original_tiny_cap_passed=True,
            exchange_min_qty_cap_escalation_required=False,
            explicit_demo_min_qty_cap_authorized=False,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                "candidate already passes original tiny cap; cap "
                "escalation gate has nothing to authorize"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    # Escalation IS required. Without explicit authorization we fail closed.
    auth_flag = bool(req.explicit_demo_min_qty_cap_authorization_flag)
    auth_marker_ok = (
        req.explicit_demo_min_qty_cap_authorization_marker
        == EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER
    )
    explicit_authorized = auth_flag and auth_marker_ok

    if not explicit_authorized:
        decision = _build_decision(
            status=STATUS_ESCALATION_NOT_AUTHORIZED,
            authorized=False,
            original_tiny_cap_passed=False,
            exchange_min_qty_cap_escalation_required=True,
            explicit_demo_min_qty_cap_authorized=False,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                "explicit cap-escalation authorization is required (flag "
                f"{EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_FLAG_NAME!r} + "
                f"marker {EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER!r}) "
                "but was not provided"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    # Authorization present -- enforce the demo-only notional ceiling.
    if candidate_notional_dec > notional_cap:
        decision = _build_decision(
            status=STATUS_ESCALATION_REJECTED_NOTIONAL_OVER_CAP,
            authorized=False,
            original_tiny_cap_passed=False,
            exchange_min_qty_cap_escalation_required=True,
            explicit_demo_min_qty_cap_authorized=True,
            cap_escalated_demo_only=False,
            request=req,
            candidate_qty=candidate_qty_str,
            candidate_notional=candidate_notional_str,
            mark_price_used=mark_price_used,
            tiny_qty_cap_sol=tiny_qty_cap_sol_str,
            tiny_size_cap_usdt=tiny_size_cap_usdt_str,
            notional_cap=notional_cap,
            reason=(
                f"candidate_notional={candidate_notional_str} exceeds "
                f"max_demo_min_qty_notional_cap_usdt="
                f"{format(notional_cap, 'f')}; fail closed even with "
                "explicit authorization"
            ),
        )
        return _wrap_report(
            req, decision, notional_cap, rules_loaded, discovery_status
        )

    decision = _build_decision(
        status=STATUS_ESCALATION_AUTHORIZED,
        authorized=True,
        original_tiny_cap_passed=False,
        exchange_min_qty_cap_escalation_required=True,
        explicit_demo_min_qty_cap_authorized=True,
        cap_escalated_demo_only=True,
        request=req,
        candidate_qty=candidate_qty_str,
        candidate_notional=candidate_notional_str,
        mark_price_used=mark_price_used,
        tiny_qty_cap_sol=tiny_qty_cap_sol_str,
        tiny_size_cap_usdt=tiny_size_cap_usdt_str,
        notional_cap=notional_cap,
        reason=(
            "explicit demo-only authorization granted; candidate_notional "
            f"{candidate_notional_str} <= cap "
            f"{format(notional_cap, 'f')} USDT; escalation applies only "
            "to this SOLUSDT demo path"
        ),
    )
    return _wrap_report(
        req, decision, notional_cap, rules_loaded, discovery_status
    )


def _wrap_report(
    request: EscalationAuthorizationRequest,
    decision: EscalationAuthorizationDecision,
    notional_cap: Decimal,
    rules_loaded: bool,
    discovery_status: str,
) -> CapEscalationGateReport:
    return CapEscalationGateReport(
        task_id=TASK_ID,
        identity=IDENTITY,
        phase=IMPLEMENTATION_PATH_PHASE,
        upstream_tasks=UPSTREAM_TASKS,
        next_required_task=NEXT_REQUIRED_TASK,
        is_review_chain_suffix=IS_REVIEW_CHAIN_SUFFIX,
        cap_escalation_gate_contract_version=(
            CAP_ESCALATION_GATE_CONTRACT_VERSION
        ),
        allowed_environment=ALLOWED_ENVIRONMENT,
        allowed_symbol=ALLOWED_SYMBOL,
        allowed_side=ALLOWED_SIDE,
        allowed_order_type=ALLOWED_ORDER_TYPE,
        allowed_time_in_force=ALLOWED_TIME_IN_FORCE,
        allowed_max_order_count=ALLOWED_MAX_ORDER_COUNT,
        explicit_authorization_flag_name=(
            EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_FLAG_NAME
        ),
        explicit_authorization_marker=(
            EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER
        ),
        max_demo_min_qty_notional_cap_usdt=format(notional_cap, "f"),
        network_attempted=False,
        order_endpoint_called=False,
        order_sent=False,
        instrument_rules_loaded=rules_loaded,
        instrument_rules_discovery_status=discovery_status,
        request=request,
        decision=decision,
        generated_at_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Report writer (JSON + Markdown; latest_* + timestamped)
# ---------------------------------------------------------------------------


def _utc_timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _render_markdown(report: CapEscalationGateReport) -> str:
    lines: list[str] = []
    lines.append(f"# {report.task_id} -- {report.identity}")
    lines.append("")
    lines.append(f"- generated_at_utc: `{report.generated_at_utc}`")
    lines.append(f"- phase: `{report.phase}`")
    lines.append(f"- upstream_tasks: `{', '.join(report.upstream_tasks)}`")
    lines.append(f"- next_required_task: `{report.next_required_task}`")
    lines.append(
        f"- is_review_chain_suffix: `{report.is_review_chain_suffix}`"
    )
    lines.append(
        f"- cap_escalation_gate_contract_version: "
        f"`{report.cap_escalation_gate_contract_version}`"
    )
    lines.append("")
    lines.append("## Locks")
    lines.append("")
    lines.append(f"- allowed_environment: `{report.allowed_environment}`")
    lines.append(f"- allowed_symbol: `{report.allowed_symbol}`")
    lines.append(f"- allowed_side: `{report.allowed_side}`")
    lines.append(f"- allowed_order_type: `{report.allowed_order_type}`")
    lines.append(
        f"- allowed_time_in_force: `{report.allowed_time_in_force}`"
    )
    lines.append(
        f"- allowed_max_order_count: `{report.allowed_max_order_count}`"
    )
    lines.append(
        f"- max_demo_min_qty_notional_cap_usdt: "
        f"`{report.max_demo_min_qty_notional_cap_usdt}`"
    )
    lines.append(
        f"- explicit_authorization_flag_name: "
        f"`{report.explicit_authorization_flag_name}`"
    )
    lines.append(
        f"- explicit_authorization_marker: "
        f"`{report.explicit_authorization_marker}`"
    )
    lines.append("")
    lines.append("## Surface")
    lines.append("")
    lines.append(f"- network_attempted: `{report.network_attempted}`")
    lines.append(f"- order_endpoint_called: `{report.order_endpoint_called}`")
    lines.append(f"- order_sent: `{report.order_sent}`")
    lines.append(f"- instrument_rules_loaded: `{report.instrument_rules_loaded}`")
    lines.append(
        f"- instrument_rules_discovery_status: "
        f"`{report.instrument_rules_discovery_status}`"
    )
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    d = report.decision
    lines.append(f"- status: `{d.status}`")
    lines.append(f"- authorized: `{d.authorized}`")
    lines.append(
        f"- original_tiny_cap_passed: `{d.original_tiny_cap_passed}`"
    )
    lines.append(
        f"- exchange_min_qty_cap_escalation_required: "
        f"`{d.exchange_min_qty_cap_escalation_required}`"
    )
    lines.append(
        f"- explicit_demo_min_qty_cap_authorized: "
        f"`{d.explicit_demo_min_qty_cap_authorized}`"
    )
    lines.append(
        f"- cap_escalated_demo_only: `{d.cap_escalated_demo_only}`"
    )
    lines.append(f"- candidate_qty: `{d.candidate_qty}`")
    lines.append(f"- candidate_notional: `{d.candidate_notional}`")
    lines.append(f"- proposed_qty: `{d.proposed_qty}`")
    lines.append(f"- mark_price_used: `{d.mark_price_used}`")
    lines.append(f"- tiny_qty_cap_sol: `{d.tiny_qty_cap_sol}`")
    lines.append(f"- tiny_size_cap_usdt: `{d.tiny_size_cap_usdt}`")
    lines.append(
        f"- max_demo_min_qty_notional_cap_usdt: "
        f"`{d.max_demo_min_qty_notional_cap_usdt}`"
    )
    reason = d.reason.replace("|", "\\|") if d.reason else ""
    lines.append(f"- reason: `{reason}`")
    lines.append("")
    lines.append(
        "_demo-only authorization gate -- no network, no order, no live "
        "endpoint, no live credentials, no main.py / src.risk / "
        "BybitExecutor change. Original tiny caps (TINY_QTY_CAP_SOL=0.05, "
        "TINY_SIZE_CAP_USDT=5) remain unchanged globally; only this single "
        "SOLUSDT demo path is escalated when explicitly authorized._"
    )
    lines.append("")
    return "\n".join(lines)


def write_report(
    report: CapEscalationGateReport,
    output_dir: pathlib.Path | str | None = None,
) -> dict[str, pathlib.Path]:
    """Write JSON + Markdown report (latest_* + timestamped)."""

    out_dir = pathlib.Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = _utc_timestamp()
    json_payload = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    md_payload = _render_markdown(report)

    paths = {
        "latest_json": out_dir / f"latest_{REPORT_NAME}.json",
        "latest_md": out_dir / f"latest_{REPORT_NAME}.md",
        "timestamped_json": out_dir / f"{REPORT_NAME}_{ts}.json",
        "timestamped_md": out_dir / f"{REPORT_NAME}_{ts}.md",
    }
    for key, path in paths.items():
        if key.endswith("_json"):
            path.write_text(json_payload, encoding="utf-8")
        else:
            path.write_text(md_payload, encoding="utf-8")
    return paths


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


__all__ = [
    "ALLOWED_ENVIRONMENT",
    "ALLOWED_MAX_ORDER_COUNT",
    "ALLOWED_ORDER_TYPE",
    "ALLOWED_SIDE",
    "ALLOWED_SYMBOL",
    "ALLOWED_TIME_IN_FORCE",
    "CAP_ESCALATION_GATE_CONTRACT_VERSION",
    "CapEscalationGateError",
    "CapEscalationGateReport",
    "DEFAULT_OUTPUT_DIR",
    "EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_FLAG_NAME",
    "EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER",
    "EscalationAuthorizationDecision",
    "EscalationAuthorizationRequest",
    "FORBIDDEN_URL_TOKENS",
    "IDENTITY",
    "IMPLEMENTATION_PATH_PHASE",
    "IS_REVIEW_CHAIN_SUFFIX",
    "MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT",
    "NEXT_REQUIRED_TASK",
    "REPORT_NAME",
    "STATUS_ESCALATION_AUTHORIZED",
    "STATUS_ESCALATION_NOT_AUTHORIZED",
    "STATUS_ESCALATION_NOT_REQUIRED",
    "STATUS_ESCALATION_REJECTED_DISALLOWED_ORDER_TYPE",
    "STATUS_ESCALATION_REJECTED_DISALLOWED_TIF",
    "STATUS_ESCALATION_REJECTED_INVALID_RULES",
    "STATUS_ESCALATION_REJECTED_LIVE_ENDPOINT",
    "STATUS_ESCALATION_REJECTED_MAX_ORDER_COUNT",
    "STATUS_ESCALATION_REJECTED_NOTIONAL_OVER_CAP",
    "STATUS_ESCALATION_REJECTED_PROTECTED_SYMBOL",
    "STATUS_ESCALATION_REJECTED_QTY_MISMATCH",
    "STATUS_ESCALATION_REJECTED_REDUCE_ONLY",
    "STATUS_ESCALATION_REJECTED_RULES_NOT_LOADED",
    "STATUS_ESCALATION_REJECTED_TPSL",
    "STATUS_ESCALATION_REJECTED_WRONG_ENVIRONMENT",
    "STATUS_ESCALATION_REJECTED_WRONG_SIDE",
    "STATUS_ESCALATION_REJECTED_WRONG_SYMBOL",
    "TASK_ID",
    "UPSTREAM_TASKS",
    "run_cap_escalation_gate",
    "write_report",
]
