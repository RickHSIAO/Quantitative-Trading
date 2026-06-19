"""TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY -- authorized candidate qty wiring.

Stage 1, decision-only, demo-only **planning/readiness** layer that wires
the authorized cap-escalation decision (from
TASK-014BM_CAP_ESCALATION_GATE) into the BM execution-planning surface so
BM can report an ``execution_qty`` equal to the exchange-minimum
``candidate_qty`` (=0.1 SOL) instead of the invalid old BL packet
``qty=0.01`` -- but **only** when the cap-escalation gate returns
``ESCALATION_AUTHORIZED`` with ``cap_escalated_demo_only=True``,
``explicit_demo_min_qty_cap_authorized=True``, and every other lock
(``environment=bybit_demo``, ``symbol=SOLUSDT``, ``side=Buy``,
``order_type=Market``, ``time_in_force=IOC``, ``max_order_count=1``,
``candidate_notional <= 20 USDT``) is satisfied.

This module is **NOT** an execution path. It does not send any order,
does not call ``/v5/order/create``, does not touch live endpoints, does
not read any secrets, does not retry, does not run a scheduler. It only
returns an ``AuthorizedExecutionQtyResolution`` that callers (and the BM
``ExecutionReport``) can surface for visibility.

Hard safety invariants (cross-checked by tests):
    * **No order endpoint call.** This module has no sender, no
      ``urllib`` import. It never references ``/v5/order/create``,
      ``/v5/order/cancel``, ``/v5/position/*``, or any live host outside
      the documented denylist constants.
    * **Readiness/planning-only.** ``run_authorized_execution_qty_wiring``
      returns a frozen ``AuthorizedExecutionQtyWiringReport``. No state
      mutation occurs outside the optional report writer.
    * **Default fail-closed.** Every reject path returns
      ``execution_qty=""`` and ``execution_qty_source ==
      "REJECTED_NO_FALLBACK_TO_0_01"`` (or ``"NONE"`` when wiring is not
      required). The wiring **never** silently substitutes the old
      invalid ``qty=0.01`` for execute mode when the instrument rules
      have confirmed it invalid.
    * **No silent global tiny cap lift.** ``TINY_QTY_CAP_SOL`` and
      ``TINY_SIZE_CAP_USDT`` in BH are not mutated by this module.
    * **No mutation of main.py / src/risk.py / BybitExecutor.**
    * **No double-confirmation flag weakening.** This module does not
      observe or store BM's ``--execute-demo-order`` /
      ``--i-understand-this-sends-one-bybit-demo-order`` flags; the
      execute decision still requires those flags in BM's own gate
      pipeline. This module only resolves the *planned* qty.
    * **No live secrets.** No ``BYBIT_API_KEY`` / ``BYBIT_API_SECRET`` /
      ``BYBIT_DEMO_API_KEY`` / ``BYBIT_DEMO_API_SECRET`` reference.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from src import demo_only_tiny_execution_adapter as bh
from src import (
    demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate as ce,
)

# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------

TASK_ID = "TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY"
IDENTITY = (
    "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-AUTHORIZED-EXECUTION-QTY-WIRING"
)
IMPLEMENTATION_PATH_PHASE = "tiny_order_authorized_execution_qty_wiring"
IS_REVIEW_CHAIN_SUFFIX = False
UPSTREAM_TASKS: tuple[str, ...] = (
    "TASK-014BH",
    "TASK-014BM",
    "TASK-014BM_FIX",
    "TASK-014BM_MIN_QTY_FIX",
    "TASK-014BM_CAP_ESCALATION_GATE",
)
NEXT_REQUIRED_TASK = "TASK-014BN_demo_only_tiny_execution_postfill_audit"

REPORT_NAME = (
    "demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring"
)
DEFAULT_OUTPUT_DIR = pathlib.Path("outputs/demo_trading") / REPORT_NAME

WIRING_CONTRACT_VERSION = (
    "demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring_v1"
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

# Original BL packet qty that the BM_MIN_QTY_FIX discovery confirmed as
# invalid against Bybit's SOLUSDT linear minimum (~0.1 SOL).
ORIGINAL_PACKET_QTY = "0.01"

# Mirror the cap-escalation gate's narrow demo-only ceiling.
MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT = ce.MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT

FORBIDDEN_URL_TOKENS: tuple[str, ...] = (
    "/v5/order/create",
    "/v5/order/cancel",
    "/v5/position/set-trading-stop",
    "https://api.bybit.com",
    "https://api.bytick.com",
    "wss://stream.bybit.com",
    "wss://stream.bytick.com",
)

# ---------------------------------------------------------------------------
# Wiring resolution statuses
# ---------------------------------------------------------------------------

STATUS_WIRING_AUTHORIZED_CANDIDATE_QTY = "WIRING_AUTHORIZED_CANDIDATE_QTY"
STATUS_WIRING_NOT_REQUIRED_ORIGINAL_PASSES = (
    "WIRING_NOT_REQUIRED_ORIGINAL_PASSES"
)
STATUS_WIRING_NOT_AUTHORIZED_NO_OVERRIDE = (
    "WIRING_NOT_AUTHORIZED_NO_OVERRIDE"
)
STATUS_WIRING_REJECTED_RULES_NOT_LOADED = (
    "WIRING_REJECTED_RULES_NOT_LOADED"
)
STATUS_WIRING_REJECTED_GATE_MISSING = "WIRING_REJECTED_GATE_MISSING"
STATUS_WIRING_REJECTED_GATE_OVER_CAP = "WIRING_REJECTED_GATE_OVER_CAP"
STATUS_WIRING_REJECTED_WRONG_SYMBOL = "WIRING_REJECTED_WRONG_SYMBOL"
STATUS_WIRING_REJECTED_WRONG_ENVIRONMENT = (
    "WIRING_REJECTED_WRONG_ENVIRONMENT"
)
STATUS_WIRING_REJECTED_WRONG_SIDE = "WIRING_REJECTED_WRONG_SIDE"
STATUS_WIRING_REJECTED_QTY_MISMATCH = "WIRING_REJECTED_QTY_MISMATCH"
STATUS_WIRING_REJECTED_PROTECTED_SYMBOL = (
    "WIRING_REJECTED_PROTECTED_SYMBOL"
)
STATUS_WIRING_REJECTED_CANDIDATE_INVALID = (
    "WIRING_REJECTED_CANDIDATE_INVALID"
)

# ``execution_qty_source`` enum.
EXECUTION_QTY_SOURCE_CAP_ESCALATION_AUTHORIZED = (
    "CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY"
)
EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK = "REJECTED_NO_FALLBACK_TO_0_01"
EXECUTION_QTY_SOURCE_NONE = "NONE"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AuthorizedExecutionQtyWiringError(
    bh.DemoOnlyTinyExecutionAdapterError
):
    """Raised when the wiring contract is violated."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthorizedExecutionQtyResolution:
    """Frozen resolution record produced by the wiring."""

    status: str
    original_packet_qty: str
    qty_0_01_confirmed_invalid: bool
    cap_gate_status: str
    cap_escalated_demo_only: bool
    explicit_demo_min_qty_cap_authorized: bool
    execution_qty_source: str
    execution_qty: str
    execution_notional_estimate: str
    mark_price_used: str
    candidate_qty: str
    candidate_notional: str
    max_demo_min_qty_notional_cap_usdt: str
    environment: str
    symbol: str
    side: str
    order_type: str
    time_in_force: str
    max_order_count: int
    order_endpoint_called: bool
    order_sent: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "original_packet_qty": self.original_packet_qty,
            "qty_0_01_confirmed_invalid": self.qty_0_01_confirmed_invalid,
            "cap_gate_status": self.cap_gate_status,
            "cap_escalated_demo_only": self.cap_escalated_demo_only,
            "explicit_demo_min_qty_cap_authorized": (
                self.explicit_demo_min_qty_cap_authorized
            ),
            "execution_qty_source": self.execution_qty_source,
            "execution_qty": self.execution_qty,
            "execution_notional_estimate": self.execution_notional_estimate,
            "mark_price_used": self.mark_price_used,
            "candidate_qty": self.candidate_qty,
            "candidate_notional": self.candidate_notional,
            "max_demo_min_qty_notional_cap_usdt": (
                self.max_demo_min_qty_notional_cap_usdt
            ),
            "environment": self.environment,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "max_order_count": self.max_order_count,
            "order_endpoint_called": self.order_endpoint_called,
            "order_sent": self.order_sent,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class AuthorizedExecutionQtyWiringReport:
    task_id: str
    identity: str
    phase: str
    upstream_tasks: tuple[str, ...]
    next_required_task: str
    is_review_chain_suffix: bool
    wiring_contract_version: str
    allowed_environment: str
    allowed_symbol: str
    allowed_side: str
    allowed_order_type: str
    allowed_time_in_force: str
    allowed_max_order_count: int
    original_packet_qty: str
    max_demo_min_qty_notional_cap_usdt: str
    network_attempted: bool
    order_endpoint_called: bool
    order_sent: bool
    instrument_rules_loaded: bool
    instrument_rules_discovery_status: str
    cap_gate_status: str
    resolution: AuthorizedExecutionQtyResolution
    generated_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "identity": self.identity,
            "phase": self.phase,
            "upstream_tasks": list(self.upstream_tasks),
            "next_required_task": self.next_required_task,
            "is_review_chain_suffix": self.is_review_chain_suffix,
            "wiring_contract_version": self.wiring_contract_version,
            "allowed_environment": self.allowed_environment,
            "allowed_symbol": self.allowed_symbol,
            "allowed_side": self.allowed_side,
            "allowed_order_type": self.allowed_order_type,
            "allowed_time_in_force": self.allowed_time_in_force,
            "allowed_max_order_count": self.allowed_max_order_count,
            "original_packet_qty": self.original_packet_qty,
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
            "cap_gate_status": self.cap_gate_status,
            "resolution": self.resolution.to_dict(),
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


def _build_resolution(
    *,
    status: str,
    cap_gate_status: str,
    cap_escalated_demo_only: bool,
    explicit_demo_min_qty_cap_authorized: bool,
    execution_qty_source: str,
    execution_qty: str,
    execution_notional_estimate: str,
    mark_price_used: str,
    candidate_qty: str,
    candidate_notional: str,
    qty_0_01_confirmed_invalid: bool,
    environment: str,
    symbol: str,
    side: str,
    order_type: str,
    time_in_force: str,
    max_order_count: int,
    reason: str,
) -> AuthorizedExecutionQtyResolution:
    return AuthorizedExecutionQtyResolution(
        status=status,
        original_packet_qty=ORIGINAL_PACKET_QTY,
        qty_0_01_confirmed_invalid=qty_0_01_confirmed_invalid,
        cap_gate_status=cap_gate_status,
        cap_escalated_demo_only=cap_escalated_demo_only,
        explicit_demo_min_qty_cap_authorized=(
            explicit_demo_min_qty_cap_authorized
        ),
        execution_qty_source=execution_qty_source,
        execution_qty=execution_qty,
        execution_notional_estimate=execution_notional_estimate,
        mark_price_used=mark_price_used,
        candidate_qty=candidate_qty,
        candidate_notional=candidate_notional,
        max_demo_min_qty_notional_cap_usdt=format(
            MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT, "f"
        ),
        environment=environment,
        symbol=symbol,
        side=side,
        order_type=order_type,
        time_in_force=time_in_force,
        max_order_count=max_order_count,
        order_endpoint_called=False,
        order_sent=False,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Public wiring entry point
# ---------------------------------------------------------------------------


def run_authorized_execution_qty_wiring(
    *,
    instrument_rules_report: Any | None,
    cap_escalation_report: Any | None,
) -> AuthorizedExecutionQtyWiringReport:
    """Resolve the BM-planning ``execution_qty`` from the cap-escalation gate.

    The wiring is decision-only. It returns a frozen
    ``AuthorizedExecutionQtyWiringReport`` describing the planned
    execution qty and the reason. Callers can then surface this on the
    BM ``ExecutionReport`` (via the optional
    ``authorized_execution_qty_wiring`` kwarg). The wiring **never**
    sends an order, **never** calls ``/v5/order/create``, **never** reads
    secrets, **never** mutates BH global tiny caps.

    Fail-closed defaults:
        * Missing instrument rules report -> ``WIRING_REJECTED_RULES_NOT_LOADED``.
        * Missing cap-escalation report -> ``WIRING_REJECTED_GATE_MISSING``.
        * Cap gate not authorized (or wrong env / symbol / side / qty
          mismatch / over cap) -> ``WIRING_NOT_AUTHORIZED_NO_OVERRIDE``
          or a more specific rejected status. ``execution_qty`` stays
          empty so BM's execute path will fail closed instead of falling
          back to the invalid ``qty=0.01``.
    """

    # Default extraction values (used for the rejected-rules-not-loaded path).
    ir_loaded = False
    ir_status = ""
    candidate_qty_str = ""
    candidate_notional_str = ""
    mark_price_used = ""
    qty_0_01_invalid = False

    if instrument_rules_report is not None:
        ir_loaded = bool(
            getattr(instrument_rules_report, "instrument_rules_loaded", False)
        )
        ir_status = str(
            getattr(instrument_rules_report, "discovery_status", "") or ""
        )
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
            qty_0_01_invalid = bool(
                getattr(candidate_obj, "confirms_qty_0_01_invalid", False)
            )

    # Default cap-gate extraction values.
    cap_status = ""
    cap_escalated_demo_only = False
    cap_authorized = False
    cap_original_passed = False
    gate_environment = ALLOWED_ENVIRONMENT
    gate_symbol = ALLOWED_SYMBOL
    gate_side = ALLOWED_SIDE
    gate_order_type = ALLOWED_ORDER_TYPE
    gate_time_in_force = ALLOWED_TIME_IN_FORCE
    gate_max_order_count = ALLOWED_MAX_ORDER_COUNT
    gate_proposed_qty = ""
    gate_candidate_qty = ""
    gate_candidate_notional = ""

    if cap_escalation_report is not None:
        decision = getattr(cap_escalation_report, "decision", None)
        if decision is not None:
            cap_status = str(getattr(decision, "status", "") or "")
            cap_escalated_demo_only = bool(
                getattr(decision, "cap_escalated_demo_only", False)
            )
            cap_authorized = bool(
                getattr(
                    decision, "explicit_demo_min_qty_cap_authorized", False
                )
            )
            cap_original_passed = bool(
                getattr(decision, "original_tiny_cap_passed", False)
            )
            gate_environment = str(
                getattr(decision, "environment", ALLOWED_ENVIRONMENT)
                or ALLOWED_ENVIRONMENT
            )
            gate_symbol = str(
                getattr(decision, "symbol", ALLOWED_SYMBOL) or ALLOWED_SYMBOL
            )
            gate_side = str(
                getattr(decision, "side", ALLOWED_SIDE) or ALLOWED_SIDE
            )
            gate_order_type = str(
                getattr(decision, "order_type", ALLOWED_ORDER_TYPE)
                or ALLOWED_ORDER_TYPE
            )
            gate_time_in_force = str(
                getattr(decision, "time_in_force", ALLOWED_TIME_IN_FORCE)
                or ALLOWED_TIME_IN_FORCE
            )
            gate_max_order_count = int(
                getattr(decision, "max_order_count", ALLOWED_MAX_ORDER_COUNT)
            )
            gate_proposed_qty = str(
                getattr(decision, "proposed_qty", "") or ""
            )
            gate_candidate_qty = str(
                getattr(decision, "candidate_qty", "") or ""
            )
            gate_candidate_notional = str(
                getattr(decision, "candidate_notional", "") or ""
            )

    # Prefer the cap-gate's candidate values when present (they are the
    # values the gate actually authorized over); fall back to instrument
    # rules report values when only that side is supplied.
    final_candidate_qty = gate_candidate_qty or candidate_qty_str
    final_candidate_notional = (
        gate_candidate_notional or candidate_notional_str
    )

    # ---- Reject path 1: no instrument rules. ----
    if instrument_rules_report is None or not ir_loaded:
        resolution = _build_resolution(
            status=STATUS_WIRING_REJECTED_RULES_NOT_LOADED,
            cap_gate_status=cap_status,
            cap_escalated_demo_only=cap_escalated_demo_only,
            explicit_demo_min_qty_cap_authorized=cap_authorized,
            execution_qty_source=EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK,
            execution_qty="",
            execution_notional_estimate="",
            mark_price_used=mark_price_used,
            candidate_qty=final_candidate_qty,
            candidate_notional=final_candidate_notional,
            qty_0_01_confirmed_invalid=qty_0_01_invalid,
            environment=gate_environment,
            symbol=gate_symbol,
            side=gate_side,
            order_type=gate_order_type,
            time_in_force=gate_time_in_force,
            max_order_count=gate_max_order_count,
            reason=(
                "instrument rules report missing or not loaded; no "
                "candidate qty available to wire"
            ),
        )
        return _wrap_report(
            resolution=resolution,
            ir_loaded=ir_loaded,
            ir_status=ir_status,
        )

    # ---- Reject path 2: no cap-escalation report. ----
    if cap_escalation_report is None:
        resolution = _build_resolution(
            status=STATUS_WIRING_REJECTED_GATE_MISSING,
            cap_gate_status="",
            cap_escalated_demo_only=False,
            explicit_demo_min_qty_cap_authorized=False,
            execution_qty_source=EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK,
            execution_qty="",
            execution_notional_estimate="",
            mark_price_used=mark_price_used,
            candidate_qty=final_candidate_qty,
            candidate_notional=final_candidate_notional,
            qty_0_01_confirmed_invalid=qty_0_01_invalid,
            environment=ALLOWED_ENVIRONMENT,
            symbol=ALLOWED_SYMBOL,
            side=ALLOWED_SIDE,
            order_type=ALLOWED_ORDER_TYPE,
            time_in_force=ALLOWED_TIME_IN_FORCE,
            max_order_count=ALLOWED_MAX_ORDER_COUNT,
            reason=(
                "cap-escalation gate report missing; refuse to override "
                "execution qty"
            ),
        )
        return _wrap_report(
            resolution=resolution,
            ir_loaded=ir_loaded,
            ir_status=ir_status,
        )

    # ---- Hard lock: environment/symbol/side must match the demo lane. ----
    if gate_environment != ALLOWED_ENVIRONMENT:
        return _wrap_report(
            resolution=_build_resolution(
                status=STATUS_WIRING_REJECTED_WRONG_ENVIRONMENT,
                cap_gate_status=cap_status,
                cap_escalated_demo_only=cap_escalated_demo_only,
                explicit_demo_min_qty_cap_authorized=cap_authorized,
                execution_qty_source=(
                    EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK
                ),
                execution_qty="",
                execution_notional_estimate="",
                mark_price_used=mark_price_used,
                candidate_qty=final_candidate_qty,
                candidate_notional=final_candidate_notional,
                qty_0_01_confirmed_invalid=qty_0_01_invalid,
                environment=gate_environment,
                symbol=gate_symbol,
                side=gate_side,
                order_type=gate_order_type,
                time_in_force=gate_time_in_force,
                max_order_count=gate_max_order_count,
                reason=(
                    f"environment {gate_environment!r} != "
                    f"{ALLOWED_ENVIRONMENT!r}"
                ),
            ),
            ir_loaded=ir_loaded,
            ir_status=ir_status,
        )

    if gate_symbol in bh.PROTECTED_SYMBOLS:
        return _wrap_report(
            resolution=_build_resolution(
                status=STATUS_WIRING_REJECTED_PROTECTED_SYMBOL,
                cap_gate_status=cap_status,
                cap_escalated_demo_only=cap_escalated_demo_only,
                explicit_demo_min_qty_cap_authorized=cap_authorized,
                execution_qty_source=(
                    EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK
                ),
                execution_qty="",
                execution_notional_estimate="",
                mark_price_used=mark_price_used,
                candidate_qty=final_candidate_qty,
                candidate_notional=final_candidate_notional,
                qty_0_01_confirmed_invalid=qty_0_01_invalid,
                environment=gate_environment,
                symbol=gate_symbol,
                side=gate_side,
                order_type=gate_order_type,
                time_in_force=gate_time_in_force,
                max_order_count=gate_max_order_count,
                reason=(
                    f"symbol {gate_symbol!r} is in PROTECTED_SYMBOLS"
                ),
            ),
            ir_loaded=ir_loaded,
            ir_status=ir_status,
        )

    if gate_symbol != ALLOWED_SYMBOL:
        return _wrap_report(
            resolution=_build_resolution(
                status=STATUS_WIRING_REJECTED_WRONG_SYMBOL,
                cap_gate_status=cap_status,
                cap_escalated_demo_only=cap_escalated_demo_only,
                explicit_demo_min_qty_cap_authorized=cap_authorized,
                execution_qty_source=(
                    EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK
                ),
                execution_qty="",
                execution_notional_estimate="",
                mark_price_used=mark_price_used,
                candidate_qty=final_candidate_qty,
                candidate_notional=final_candidate_notional,
                qty_0_01_confirmed_invalid=qty_0_01_invalid,
                environment=gate_environment,
                symbol=gate_symbol,
                side=gate_side,
                order_type=gate_order_type,
                time_in_force=gate_time_in_force,
                max_order_count=gate_max_order_count,
                reason=f"symbol {gate_symbol!r} != {ALLOWED_SYMBOL!r}",
            ),
            ir_loaded=ir_loaded,
            ir_status=ir_status,
        )

    if gate_side != ALLOWED_SIDE:
        return _wrap_report(
            resolution=_build_resolution(
                status=STATUS_WIRING_REJECTED_WRONG_SIDE,
                cap_gate_status=cap_status,
                cap_escalated_demo_only=cap_escalated_demo_only,
                explicit_demo_min_qty_cap_authorized=cap_authorized,
                execution_qty_source=(
                    EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK
                ),
                execution_qty="",
                execution_notional_estimate="",
                mark_price_used=mark_price_used,
                candidate_qty=final_candidate_qty,
                candidate_notional=final_candidate_notional,
                qty_0_01_confirmed_invalid=qty_0_01_invalid,
                environment=gate_environment,
                symbol=gate_symbol,
                side=gate_side,
                order_type=gate_order_type,
                time_in_force=gate_time_in_force,
                max_order_count=gate_max_order_count,
                reason=f"side {gate_side!r} != {ALLOWED_SIDE!r}",
            ),
            ir_loaded=ir_loaded,
            ir_status=ir_status,
        )

    # ---- Path: original tiny cap already passes; no override required. ----
    if cap_status == ce.STATUS_ESCALATION_NOT_REQUIRED or cap_original_passed:
        return _wrap_report(
            resolution=_build_resolution(
                status=STATUS_WIRING_NOT_REQUIRED_ORIGINAL_PASSES,
                cap_gate_status=cap_status,
                cap_escalated_demo_only=cap_escalated_demo_only,
                explicit_demo_min_qty_cap_authorized=cap_authorized,
                execution_qty_source=EXECUTION_QTY_SOURCE_NONE,
                execution_qty="",
                execution_notional_estimate="",
                mark_price_used=mark_price_used,
                candidate_qty=final_candidate_qty,
                candidate_notional=final_candidate_notional,
                qty_0_01_confirmed_invalid=qty_0_01_invalid,
                environment=gate_environment,
                symbol=gate_symbol,
                side=gate_side,
                order_type=gate_order_type,
                time_in_force=gate_time_in_force,
                max_order_count=gate_max_order_count,
                reason=(
                    "original tiny cap already passes; BL packet qty "
                    "remains unchanged"
                ),
            ),
            ir_loaded=ir_loaded,
            ir_status=ir_status,
        )

    # ---- Path: cap gate explicitly authorized. ----
    if cap_status == ce.STATUS_ESCALATION_AUTHORIZED:
        # When the gate claims AUTHORIZED, we only honor its OWN
        # candidate_qty / candidate_notional. We do NOT inherit the
        # instrument-rules-report candidate as a silent fallback, since
        # the gate is the contract that did (or did not) actually
        # authorize a specific (qty, notional) pair.
        gate_only_candidate_qty = gate_candidate_qty
        gate_only_candidate_notional = gate_candidate_notional
        # Both authorization markers and the cap-escalated-demo-only flag
        # must be present.
        if not (cap_escalated_demo_only and cap_authorized):
            return _wrap_report(
                resolution=_build_resolution(
                    status=STATUS_WIRING_NOT_AUTHORIZED_NO_OVERRIDE,
                    cap_gate_status=cap_status,
                    cap_escalated_demo_only=cap_escalated_demo_only,
                    explicit_demo_min_qty_cap_authorized=cap_authorized,
                    execution_qty_source=(
                        EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK
                    ),
                    execution_qty="",
                    execution_notional_estimate="",
                    mark_price_used=mark_price_used,
                    candidate_qty=final_candidate_qty,
                    candidate_notional=final_candidate_notional,
                    qty_0_01_confirmed_invalid=qty_0_01_invalid,
                    environment=gate_environment,
                    symbol=gate_symbol,
                    side=gate_side,
                    order_type=gate_order_type,
                    time_in_force=gate_time_in_force,
                    max_order_count=gate_max_order_count,
                    reason=(
                        "ESCALATION_AUTHORIZED received without both "
                        "cap_escalated_demo_only and "
                        "explicit_demo_min_qty_cap_authorized"
                    ),
                ),
                ir_loaded=ir_loaded,
                ir_status=ir_status,
            )

        # Candidate qty must be a positive Decimal -- read from the
        # GATE only (no fallback to instrument rules candidate).
        cqty = _decimal_or_none(gate_only_candidate_qty)
        cnot = _decimal_or_none(gate_only_candidate_notional)
        if cqty is None or cqty <= 0 or cnot is None or cnot <= 0:
            return _wrap_report(
                resolution=_build_resolution(
                    status=STATUS_WIRING_REJECTED_CANDIDATE_INVALID,
                    cap_gate_status=cap_status,
                    cap_escalated_demo_only=cap_escalated_demo_only,
                    explicit_demo_min_qty_cap_authorized=cap_authorized,
                    execution_qty_source=(
                        EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK
                    ),
                    execution_qty="",
                    execution_notional_estimate="",
                    mark_price_used=mark_price_used,
                    candidate_qty=gate_only_candidate_qty,
                    candidate_notional=gate_only_candidate_notional,
                    qty_0_01_confirmed_invalid=qty_0_01_invalid,
                    environment=gate_environment,
                    symbol=gate_symbol,
                    side=gate_side,
                    order_type=gate_order_type,
                    time_in_force=gate_time_in_force,
                    max_order_count=gate_max_order_count,
                    reason=(
                        "candidate_qty or candidate_notional is not a "
                        "positive Decimal"
                    ),
                ),
                ir_loaded=ir_loaded,
                ir_status=ir_status,
            )

        # Notional must respect the demo ceiling.
        if cnot > MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT:
            return _wrap_report(
                resolution=_build_resolution(
                    status=STATUS_WIRING_REJECTED_GATE_OVER_CAP,
                    cap_gate_status=cap_status,
                    cap_escalated_demo_only=cap_escalated_demo_only,
                    explicit_demo_min_qty_cap_authorized=cap_authorized,
                    execution_qty_source=(
                        EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK
                    ),
                    execution_qty="",
                    execution_notional_estimate="",
                    mark_price_used=mark_price_used,
                    candidate_qty=final_candidate_qty,
                    candidate_notional=final_candidate_notional,
                    qty_0_01_confirmed_invalid=qty_0_01_invalid,
                    environment=gate_environment,
                    symbol=gate_symbol,
                    side=gate_side,
                    order_type=gate_order_type,
                    time_in_force=gate_time_in_force,
                    max_order_count=gate_max_order_count,
                    reason=(
                        f"candidate_notional {format(cnot, 'f')} > "
                        f"{format(MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT, 'f')}"
                    ),
                ),
                ir_loaded=ir_loaded,
                ir_status=ir_status,
            )

        # Proposed qty (if present on the gate decision) must exactly
        # match candidate_qty as a Decimal -- defense-in-depth in case
        # the gate accepted a numerically equivalent but textually
        # different value.
        if gate_proposed_qty:
            pqty = _decimal_or_none(gate_proposed_qty)
            if pqty is None or pqty != cqty:
                return _wrap_report(
                    resolution=_build_resolution(
                        status=STATUS_WIRING_REJECTED_QTY_MISMATCH,
                        cap_gate_status=cap_status,
                        cap_escalated_demo_only=cap_escalated_demo_only,
                        explicit_demo_min_qty_cap_authorized=cap_authorized,
                        execution_qty_source=(
                            EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK
                        ),
                        execution_qty="",
                        execution_notional_estimate="",
                        mark_price_used=mark_price_used,
                        candidate_qty=final_candidate_qty,
                        candidate_notional=final_candidate_notional,
                        qty_0_01_confirmed_invalid=qty_0_01_invalid,
                        environment=gate_environment,
                        symbol=gate_symbol,
                        side=gate_side,
                        order_type=gate_order_type,
                        time_in_force=gate_time_in_force,
                        max_order_count=gate_max_order_count,
                        reason=(
                            f"proposed_qty {gate_proposed_qty!r} != "
                            f"candidate_qty {final_candidate_qty!r}"
                        ),
                    ),
                    ir_loaded=ir_loaded,
                    ir_status=ir_status,
                )

        return _wrap_report(
            resolution=_build_resolution(
                status=STATUS_WIRING_AUTHORIZED_CANDIDATE_QTY,
                cap_gate_status=cap_status,
                cap_escalated_demo_only=cap_escalated_demo_only,
                explicit_demo_min_qty_cap_authorized=cap_authorized,
                execution_qty_source=(
                    EXECUTION_QTY_SOURCE_CAP_ESCALATION_AUTHORIZED
                ),
                execution_qty=gate_only_candidate_qty,
                execution_notional_estimate=gate_only_candidate_notional,
                mark_price_used=mark_price_used,
                candidate_qty=gate_only_candidate_qty,
                candidate_notional=gate_only_candidate_notional,
                qty_0_01_confirmed_invalid=qty_0_01_invalid,
                environment=gate_environment,
                symbol=gate_symbol,
                side=gate_side,
                order_type=gate_order_type,
                time_in_force=gate_time_in_force,
                max_order_count=gate_max_order_count,
                reason=(
                    "cap-escalation gate authorized; execution_qty wired "
                    "to candidate_qty"
                ),
            ),
            ir_loaded=ir_loaded,
            ir_status=ir_status,
        )

    # ---- Path: explicit over-cap rejection from the gate. ----
    if cap_status == ce.STATUS_ESCALATION_REJECTED_NOTIONAL_OVER_CAP:
        return _wrap_report(
            resolution=_build_resolution(
                status=STATUS_WIRING_REJECTED_GATE_OVER_CAP,
                cap_gate_status=cap_status,
                cap_escalated_demo_only=cap_escalated_demo_only,
                explicit_demo_min_qty_cap_authorized=cap_authorized,
                execution_qty_source=(
                    EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK
                ),
                execution_qty="",
                execution_notional_estimate="",
                mark_price_used=mark_price_used,
                candidate_qty=final_candidate_qty,
                candidate_notional=final_candidate_notional,
                qty_0_01_confirmed_invalid=qty_0_01_invalid,
                environment=gate_environment,
                symbol=gate_symbol,
                side=gate_side,
                order_type=gate_order_type,
                time_in_force=gate_time_in_force,
                max_order_count=gate_max_order_count,
                reason=(
                    "cap-escalation gate rejected with NOTIONAL_OVER_CAP; "
                    "no override"
                ),
            ),
            ir_loaded=ir_loaded,
            ir_status=ir_status,
        )

    # ---- Default reject path: any other gate status. ----
    return _wrap_report(
        resolution=_build_resolution(
            status=STATUS_WIRING_NOT_AUTHORIZED_NO_OVERRIDE,
            cap_gate_status=cap_status,
            cap_escalated_demo_only=cap_escalated_demo_only,
            explicit_demo_min_qty_cap_authorized=cap_authorized,
            execution_qty_source=EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK,
            execution_qty="",
            execution_notional_estimate="",
            mark_price_used=mark_price_used,
            candidate_qty=final_candidate_qty,
            candidate_notional=final_candidate_notional,
            qty_0_01_confirmed_invalid=qty_0_01_invalid,
            environment=gate_environment,
            symbol=gate_symbol,
            side=gate_side,
            order_type=gate_order_type,
            time_in_force=gate_time_in_force,
            max_order_count=gate_max_order_count,
            reason=(
                f"cap gate status {cap_status!r} does not authorize "
                "an override; refuse silent fallback to qty=0.01"
            ),
        ),
        ir_loaded=ir_loaded,
        ir_status=ir_status,
    )


def _wrap_report(
    *,
    resolution: AuthorizedExecutionQtyResolution,
    ir_loaded: bool,
    ir_status: str,
) -> AuthorizedExecutionQtyWiringReport:
    return AuthorizedExecutionQtyWiringReport(
        task_id=TASK_ID,
        identity=IDENTITY,
        phase=IMPLEMENTATION_PATH_PHASE,
        upstream_tasks=UPSTREAM_TASKS,
        next_required_task=NEXT_REQUIRED_TASK,
        is_review_chain_suffix=IS_REVIEW_CHAIN_SUFFIX,
        wiring_contract_version=WIRING_CONTRACT_VERSION,
        allowed_environment=ALLOWED_ENVIRONMENT,
        allowed_symbol=ALLOWED_SYMBOL,
        allowed_side=ALLOWED_SIDE,
        allowed_order_type=ALLOWED_ORDER_TYPE,
        allowed_time_in_force=ALLOWED_TIME_IN_FORCE,
        allowed_max_order_count=ALLOWED_MAX_ORDER_COUNT,
        original_packet_qty=ORIGINAL_PACKET_QTY,
        max_demo_min_qty_notional_cap_usdt=format(
            MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT, "f"
        ),
        network_attempted=False,
        order_endpoint_called=False,
        order_sent=False,
        instrument_rules_loaded=ir_loaded,
        instrument_rules_discovery_status=ir_status,
        cap_gate_status=resolution.cap_gate_status,
        resolution=resolution,
        generated_at_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Report writer (JSON + Markdown; latest_* + timestamped)
# ---------------------------------------------------------------------------


def _render_markdown(report: AuthorizedExecutionQtyWiringReport) -> str:
    r = report.resolution
    lines: list[str] = []
    lines.append(
        "# TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY -- authorized "
        "execution qty wiring (readiness/planning only)"
    )
    lines.append("")
    lines.append(f"- task_id: `{report.task_id}`")
    lines.append(f"- identity: `{report.identity}`")
    lines.append(f"- phase: `{report.phase}`")
    lines.append(
        f"- next_required_task: `{report.next_required_task}`"
    )
    lines.append(
        f"- is_review_chain_suffix: `{report.is_review_chain_suffix}`"
    )
    lines.append("")
    lines.append("## Locks")
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
    lines.append(f"- original_packet_qty: `{report.original_packet_qty}`")
    lines.append("")
    lines.append("## Network / order surface")
    lines.append(f"- network_attempted: `{report.network_attempted}`")
    lines.append(
        f"- order_endpoint_called: `{report.order_endpoint_called}`"
    )
    lines.append(f"- order_sent: `{report.order_sent}`")
    lines.append("")
    lines.append("## Resolution")
    lines.append(f"- status: `{r.status}`")
    lines.append(f"- execution_qty_source: `{r.execution_qty_source}`")
    lines.append(f"- execution_qty: `{r.execution_qty}`")
    lines.append(
        f"- execution_notional_estimate: `{r.execution_notional_estimate}`"
    )
    lines.append(f"- candidate_qty: `{r.candidate_qty}`")
    lines.append(f"- candidate_notional: `{r.candidate_notional}`")
    lines.append(f"- mark_price_used: `{r.mark_price_used}`")
    lines.append(f"- cap_gate_status: `{r.cap_gate_status}`")
    lines.append(
        f"- cap_escalated_demo_only: `{r.cap_escalated_demo_only}`"
    )
    lines.append(
        f"- explicit_demo_min_qty_cap_authorized: "
        f"`{r.explicit_demo_min_qty_cap_authorized}`"
    )
    lines.append(
        f"- qty_0_01_confirmed_invalid: `{r.qty_0_01_confirmed_invalid}`"
    )
    lines.append(f"- reason: {r.reason}")
    lines.append("")
    lines.append(f"_generated_at_utc_: `{report.generated_at_utc}`")
    return "\n".join(lines) + "\n"


def write_report(
    report: AuthorizedExecutionQtyWiringReport,
    *,
    output_dir: pathlib.Path | None = None,
) -> Mapping[str, pathlib.Path]:
    """Write JSON + Markdown report files.

    Writes:
        * ``latest_<name>.json``
        * ``latest_<name>.md``
        * ``<name>_<utc_stamp>.json``
        * ``<name>_<utc_stamp>.md``

    This function never sends an order and never references any live
    endpoint URL.
    """

    target = output_dir if output_dir is not None else DEFAULT_OUTPUT_DIR
    target.mkdir(parents=True, exist_ok=True)

    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = report.to_dict()
    md = _render_markdown(report)

    paths = {
        "latest_json": target / f"latest_{REPORT_NAME}.json",
        "latest_md": target / f"latest_{REPORT_NAME}.md",
        "stamped_json": target / f"{REPORT_NAME}_{stamp}.json",
        "stamped_md": target / f"{REPORT_NAME}_{stamp}.md",
    }
    for key, path in paths.items():
        if key.endswith("_json"):
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
            )
        else:
            path.write_text(md, encoding="utf-8")
    return paths


__all__ = [
    "TASK_ID",
    "IDENTITY",
    "IMPLEMENTATION_PATH_PHASE",
    "IS_REVIEW_CHAIN_SUFFIX",
    "UPSTREAM_TASKS",
    "NEXT_REQUIRED_TASK",
    "WIRING_CONTRACT_VERSION",
    "ALLOWED_ENVIRONMENT",
    "ALLOWED_SYMBOL",
    "ALLOWED_SIDE",
    "ALLOWED_ORDER_TYPE",
    "ALLOWED_TIME_IN_FORCE",
    "ALLOWED_MAX_ORDER_COUNT",
    "ORIGINAL_PACKET_QTY",
    "MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT",
    "FORBIDDEN_URL_TOKENS",
    "STATUS_WIRING_AUTHORIZED_CANDIDATE_QTY",
    "STATUS_WIRING_NOT_REQUIRED_ORIGINAL_PASSES",
    "STATUS_WIRING_NOT_AUTHORIZED_NO_OVERRIDE",
    "STATUS_WIRING_REJECTED_RULES_NOT_LOADED",
    "STATUS_WIRING_REJECTED_GATE_MISSING",
    "STATUS_WIRING_REJECTED_GATE_OVER_CAP",
    "STATUS_WIRING_REJECTED_WRONG_SYMBOL",
    "STATUS_WIRING_REJECTED_WRONG_ENVIRONMENT",
    "STATUS_WIRING_REJECTED_WRONG_SIDE",
    "STATUS_WIRING_REJECTED_QTY_MISMATCH",
    "STATUS_WIRING_REJECTED_PROTECTED_SYMBOL",
    "STATUS_WIRING_REJECTED_CANDIDATE_INVALID",
    "EXECUTION_QTY_SOURCE_CAP_ESCALATION_AUTHORIZED",
    "EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK",
    "EXECUTION_QTY_SOURCE_NONE",
    "AuthorizedExecutionQtyWiringError",
    "AuthorizedExecutionQtyResolution",
    "AuthorizedExecutionQtyWiringReport",
    "run_authorized_execution_qty_wiring",
    "write_report",
]
