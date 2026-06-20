"""TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR (Stage 1).

Demo-only, decision-+-validation-only orchestration layer that wires
the entire authorized execution chain together so the BM execution
module receives a fully authorized
:class:`AuthorizedExecutionQtyWiringReport` and therefore plans a
request body with ``qty="0.1"`` instead of the invalid BL packet
``qty="0.01"``.

Stage 1 hard constraints (cross-checked by tests):

    * **No real order network call.** This module never sends a real
      ``/v5/order/create`` request. Real execute mode is unavailable
      from the public surface; the only execute-mode entry point
      requires an explicit fake ``Sender`` callable and rejects the
      stdlib default.
    * **No retry, no scheduler.** A single pass through the chain.
    * **No live endpoint.** The single allowed instrument-rules read
      URL is the demo-only public
      ``https://api-demo.bybit.com/v5/market/instruments-info``.
    * **No live secrets / no live credential loading.** The BM
      credentials kwarg is opaque; this module does not read any
      environment variable named ``BYBIT_*``.
    * **No protected-position interaction.** SOLUSDT is the only
      symbol orchestrated; protected symbols denylist is preserved.
    * **No global tiny-cap mutation.** ``TINY_QTY_CAP_SOL=0.05`` and
      ``TINY_SIZE_CAP_USDT=5`` and ``MAX_ORDER_COUNT=1`` are read but
      never mutated. The orchestrator only authorizes the narrow
      cap-escalation path documented by
      ``TASK-014BM_CAP_ESCALATION_GATE`` /
      ``TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY``.
    * **No `main.py` / `src/risk.py` / `src/executors/bybit.py`
      import.** No ``BybitExecutor`` reference. No scheduler import.

Orchestration sequence:

    1. Discover SOLUSDT instrument rules. Default offline (caller
       supplies a ``pre_parsed_response`` for tests / dry-run); a
       caller-injected ``ir_sender`` may be used to read the public
       read-only endpoint. ``ir_mode="discover"`` without an injected
       sender uses the BM_MIN_QTY_FIX stdlib reader (single bounded
       GET, public endpoint, no signing) -- the orchestrator forbids
       this branch in Stage 1 unless ``allow_real_ir_get=True`` is
       explicitly set, which Stage 1 callers never set.
    2. Validate IR: ``symbol=SOLUSDT``, ``status=Trading``,
       ``min_order_qty=0.1``, ``qty_step=0.1``, candidate
       confirms ``qty=0.01`` invalid.
    3. Build the cap-escalation request with the proposed qty equal
       to the IR-derived candidate qty, the explicit authorization
       flag, and the exact authorization marker.
    4. Run the cap-escalation gate. Require status
       ``ESCALATION_AUTHORIZED``.
    5. Run the authorized execution qty wiring. Require status
       ``WIRING_AUTHORIZED_CANDIDATE_QTY``, source
       ``CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY``,
       ``execution_qty="0.1"``, ``cap_escalated_demo_only=True``,
       ``qty_0_01_confirmed_invalid=True``.
    6. Pass that exact wiring report into BM
       ``run_explicit_tiny_order_execution`` -- either in
       ``readiness`` mode (no network) or in
       ``execute_demo_order`` mode with an explicit *fake* sender
       supplied by the caller. Stage 1 forbids any other
       configuration.

The orchestrator surfaces every chain step on a single frozen
:class:`OrchestrationReport`. JSON+MD report writer is included.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Mapping

from src import demo_only_tiny_execution_adapter as bh
from src import (
    demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring as bm_wire,
)
from src import (
    demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate as bm_ce,
)
from src import (
    demo_only_tiny_execution_adapter_tiny_order_execution as bm,
)
from src import (
    demo_only_tiny_execution_adapter_tiny_order_instrument_rules as bm_ir,
)


# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------

TASK_ID = "TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR"
IDENTITY = (
    "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-"
    "ONE-SHOT-AUTHORIZED-EXECUTION-ORCHESTRATOR"
)
IMPLEMENTATION_PATH_PHASE = (
    "tiny_order_one_shot_authorized_execution_orchestrator"
)
IS_REVIEW_CHAIN_SUFFIX = False
UPSTREAM_TASKS: tuple[str, ...] = (
    "TASK-014BH",
    "TASK-014BM",
    "TASK-014BM_FIX",
    "TASK-014BM_MIN_QTY_FIX",
    "TASK-014BM_CAP_ESCALATION_GATE",
    "TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY",
    "TASK-014BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH",
)
NEXT_REQUIRED_TASK = "TASK-014BN_demo_only_tiny_execution_postfill_audit"

bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)

ORCHESTRATION_CONTRACT_VERSION = (
    "demo_only_tiny_execution_adapter_tiny_order_"
    "one_shot_authorized_execution_orchestrator_v1"
)

REPORT_NAME = (
    "demo_only_tiny_execution_adapter_tiny_order_"
    "one_shot_authorized_execution_orchestrator"
)
DEFAULT_OUTPUT_DIR = pathlib.Path("outputs/demo_trading") / REPORT_NAME


# ---------------------------------------------------------------------------
# Immutable Stage 1 locks
# ---------------------------------------------------------------------------

ALLOWED_ENVIRONMENT = "bybit_demo"
ALLOWED_SYMBOL = "SOLUSDT"
ALLOWED_SIDE = "Buy"
ALLOWED_ORDER_TYPE = "Market"
ALLOWED_TIME_IN_FORCE = "IOC"
ALLOWED_MAX_ORDER_COUNT = 1
ALLOWED_CATEGORY = "linear"

EXPECTED_MIN_ORDER_QTY = "0.1"
EXPECTED_QTY_STEP = "0.1"
EXPECTED_INSTRUMENT_STATUS = "Trading"
EXPECTED_CANDIDATE_QTY = "0.1"
ORIGINAL_PACKET_QTY = "0.01"

MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT = Decimal("20")


# ---------------------------------------------------------------------------
# Orchestration modes & statuses
# ---------------------------------------------------------------------------

ORCH_MODE_READINESS = "readiness"
ORCH_MODE_EXECUTE_WITH_FAKE_SENDER = "execute_with_fake_sender"
# TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1: isolated
# real-demo-execute mode. Stage 1 implements the surface but never
# reaches a real /v5/order/create call: even when every flag, marker,
# and credential is supplied, the orchestrator refuses to invoke BM
# unless a callable ``bm_fake_sender`` is also supplied (testing only).
ORCH_MODE_EXECUTE_REAL_DEMO_ORDER = "execute_real_demo_order"
ORCH_SUPPORTED_MODES: tuple[str, ...] = (
    ORCH_MODE_READINESS,
    ORCH_MODE_EXECUTE_WITH_FAKE_SENDER,
    ORCH_MODE_EXECUTE_REAL_DEMO_ORDER,
)

# TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1: exact
# authorization marker required by the new real-demo execute mode.
# Distinct from the existing cap-escalation marker; both must match.
EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER = (
    "DEMO_ONLY_SOLUSDT_ONE_SHOT_REAL_ORDER_RICK_AUTHORIZED_v1"
)

# Credentials source labels (audit field).
CREDENTIALS_SOURCE_INJECTED = "injected_demo_credentials"
CREDENTIALS_SOURCE_NONE = "none"

# TASK-014BM_STAGE1_REAL_VS_SIMULATED_ORDER_AUDIT_SEMANTICS_SPLIT:
# explicit transport-kind taxonomy distinguishing the injected fake
# sender (Stage 1 offline validation) from a real Bybit Demo
# ``/v5/order/create`` dispatch. Stage 1 must never emit
# ``REAL_DEMO_SENDER`` -- the constant exists only so consumers can
# match against the closed allowlist without importing string literals.
ORDER_TRANSPORT_KIND_NONE = "NONE"
ORDER_TRANSPORT_KIND_FAKE_SENDER = "FAKE_SENDER"
ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER = "REAL_DEMO_SENDER"
ORDER_TRANSPORT_KINDS: tuple[str, ...] = (
    ORDER_TRANSPORT_KIND_NONE,
    ORDER_TRANSPORT_KIND_FAKE_SENDER,
    ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER,
)
STAGE1_FORBIDDEN_ORDER_TRANSPORT_KINDS: tuple[str, ...] = (
    ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER,
)

STATUS_OK_READINESS_NO_NETWORK = "ORCHESTRATION_OK_READINESS_NO_NETWORK"
STATUS_OK_READINESS_READ_ONLY_NETWORK = (
    "ORCHESTRATION_OK_READINESS_READ_ONLY_NETWORK"
)
STATUS_OK_FAKE_SENDER_EXECUTED = (
    "ORCHESTRATION_OK_FAKE_SENDER_EXECUTED_DEMO_ONLY"
)
STATUS_REJECTED_REAL_EXECUTE_FORBIDDEN_STAGE1 = (
    "ORCHESTRATION_REJECTED_REAL_EXECUTE_FORBIDDEN_STAGE1"
)
STATUS_REJECTED_UNSUPPORTED_MODE = (
    "ORCHESTRATION_REJECTED_UNSUPPORTED_MODE"
)
STATUS_REJECTED_RULES_NOT_LOADED = (
    "ORCHESTRATION_REJECTED_RULES_NOT_LOADED"
)
STATUS_REJECTED_RULES_INVALID = "ORCHESTRATION_REJECTED_RULES_INVALID"
STATUS_REJECTED_CAP_GATE_NOT_AUTHORIZED = (
    "ORCHESTRATION_REJECTED_CAP_GATE_NOT_AUTHORIZED"
)
STATUS_REJECTED_WIRING_NOT_AUTHORIZED = (
    "ORCHESTRATION_REJECTED_WIRING_NOT_AUTHORIZED"
)
STATUS_REJECTED_BM_FAILED_CLOSED = (
    "ORCHESTRATION_REJECTED_BM_FAILED_CLOSED"
)
STATUS_REJECTED_BM_BYBIT_NOT_EXECUTED = (
    "ORCHESTRATION_REJECTED_BM_BYBIT_NOT_EXECUTED"
)
STATUS_REJECTED_BM_NETWORK_ERROR = (
    "ORCHESTRATION_REJECTED_BM_NETWORK_ERROR"
)
STATUS_REJECTED_MISSING_FAKE_SENDER = (
    "ORCHESTRATION_REJECTED_MISSING_FAKE_SENDER"
)
STATUS_REJECTED_MISSING_CREDENTIALS = (
    "ORCHESTRATION_REJECTED_MISSING_CREDENTIALS"
)
STATUS_REJECTED_BODY_QTY_NOT_AUTHORIZED = (
    "ORCHESTRATION_REJECTED_BODY_QTY_NOT_AUTHORIZED"
)
# TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1: new
# rejection statuses for the isolated real-demo execute surface.
STATUS_REJECTED_REAL_EXECUTE_NOT_AUTHORIZED = (
    "ORCHESTRATION_REJECTED_REAL_EXECUTE_NOT_AUTHORIZED"
)
STATUS_REJECTED_REAL_EXECUTE_MARKER_MISMATCH = (
    "ORCHESTRATION_REJECTED_REAL_EXECUTE_MARKER_MISMATCH"
)
# TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1_DISCOVERY_GATE_FIX:
# the real-demo execute surface must require a fresh public read-only
# instrument-rules discovery path. Cached / pre-parsed rules are forbidden,
# and the explicit public-read opt-in must be set before any IR or order
# sender can run.
STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED = (
    "ORCHESTRATION_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED"
)
STATUS_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED = (
    "ORCHESTRATION_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED"
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class OneShotAuthorizedExecutionOrchestratorError(
    bh.DemoOnlyTinyExecutionAdapterError
):
    """Raised when the orchestrator detects an explicit safety violation."""


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrchestrationReport:
    """Frozen report covering the full orchestrated chain."""

    task_id: str
    identity: str
    phase: str
    upstream_tasks: tuple[str, ...]
    next_required_task: str
    is_review_chain_suffix: bool
    orchestration_contract_version: str
    mode: str
    status: str
    reason: str

    # IR
    instrument_rules_loaded: bool
    instrument_rules_status: str
    instrument_rules_symbol: str
    instrument_rules_trading_status: str
    instrument_rules_min_order_qty: str
    instrument_rules_qty_step: str
    candidate_qty: str
    candidate_notional: str
    qty_0_01_confirmed_invalid: bool

    # Cap gate
    cap_gate_status: str
    cap_gate_authorized: bool
    cap_escalated_demo_only: bool
    explicit_demo_min_qty_cap_authorized: bool

    # Wiring
    wiring_status: str
    wiring_execution_qty_source: str
    wiring_execution_qty: str
    wiring_execution_notional_estimate: str

    # BM
    bm_invoked: bool
    bm_mode: str
    bm_final_status: str
    original_packet_qty: str
    actual_request_body_qty: str
    actual_request_body_qty_source: str
    body_qty_authorized_override: bool
    body_qty_rejection_reason: str
    read_only_network_attempted: bool
    order_network_attempted: bool
    network_attempted: bool
    order_endpoint_called: bool
    order_sent: bool
    bybit_ret_code: int | None
    bybit_order_id: str

    # Safety / sender
    real_execute_disabled_stage1: bool
    fake_sender_used: bool
    sender_call_count: int

    # Locks (snapshot)
    allowed_environment: str
    allowed_symbol: str
    allowed_side: str
    allowed_order_type: str
    allowed_time_in_force: str
    allowed_max_order_count: int
    tiny_qty_cap_sol: str
    tiny_size_cap_usdt: str
    max_demo_min_qty_notional_cap_usdt: str
    protected_symbols_untouched: bool

    # Nested raw reports (for full traceability)
    instrument_rules_report: dict[str, Any]
    cap_escalation_report: dict[str, Any]
    wiring_report: dict[str, Any]
    bm_report: dict[str, Any]

    generated_at_utc: str

    # TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1: new
    # immutable audit fields for the isolated real-demo execute surface.
    # All have safe defaults so existing callers/tests remain green.
    real_demo_execute_requested: bool = False
    real_demo_execute_authorized: bool = False
    real_demo_authorization_marker_match: bool = False
    credentials_source: str = CREDENTIALS_SOURCE_NONE
    resolved_execution_qty: str = ""
    resolved_execution_qty_source: str = ""
    resolved_notional: str = ""
    bybit_ret_msg: str = ""
    final_status: str = ""

    # TASK-014BM_STAGE1_REAL_VS_SIMULATED_ORDER_AUDIT_SEMANTICS_SPLIT:
    # explicit split of the legacy ``order_*`` audit booleans into a
    # simulated (injected fake sender) facet and a real-network facet.
    # Stage 1 invariant: real_order_* is always False and
    # order_transport_kind is never REAL_DEMO_SENDER. Legacy fields
    # (order_network_attempted / order_endpoint_called / order_sent /
    # network_attempted) remain as documented aggregate ORs of these
    # split fields so existing consumers keep working unchanged.
    simulated_order_network_attempted: bool = False
    simulated_order_endpoint_called: bool = False
    simulated_order_sent: bool = False
    real_order_network_attempted: bool = False
    real_order_endpoint_called: bool = False
    real_order_sent: bool = False
    order_transport_kind: str = ORDER_TRANSPORT_KIND_NONE

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "identity": self.identity,
            "phase": self.phase,
            "upstream_tasks": list(self.upstream_tasks),
            "next_required_task": self.next_required_task,
            "is_review_chain_suffix": self.is_review_chain_suffix,
            "orchestration_contract_version": (
                self.orchestration_contract_version
            ),
            "mode": self.mode,
            "status": self.status,
            "reason": self.reason,
            "instrument_rules_loaded": self.instrument_rules_loaded,
            "instrument_rules_status": self.instrument_rules_status,
            "instrument_rules_symbol": self.instrument_rules_symbol,
            "instrument_rules_trading_status": (
                self.instrument_rules_trading_status
            ),
            "instrument_rules_min_order_qty": (
                self.instrument_rules_min_order_qty
            ),
            "instrument_rules_qty_step": self.instrument_rules_qty_step,
            "candidate_qty": self.candidate_qty,
            "candidate_notional": self.candidate_notional,
            "qty_0_01_confirmed_invalid": self.qty_0_01_confirmed_invalid,
            "cap_gate_status": self.cap_gate_status,
            "cap_gate_authorized": self.cap_gate_authorized,
            "cap_escalated_demo_only": self.cap_escalated_demo_only,
            "explicit_demo_min_qty_cap_authorized": (
                self.explicit_demo_min_qty_cap_authorized
            ),
            "wiring_status": self.wiring_status,
            "wiring_execution_qty_source": self.wiring_execution_qty_source,
            "wiring_execution_qty": self.wiring_execution_qty,
            "wiring_execution_notional_estimate": (
                self.wiring_execution_notional_estimate
            ),
            "bm_invoked": self.bm_invoked,
            "bm_mode": self.bm_mode,
            "bm_final_status": self.bm_final_status,
            "original_packet_qty": self.original_packet_qty,
            "actual_request_body_qty": self.actual_request_body_qty,
            "actual_request_body_qty_source": (
                self.actual_request_body_qty_source
            ),
            "body_qty_authorized_override": self.body_qty_authorized_override,
            "body_qty_rejection_reason": self.body_qty_rejection_reason,
            "read_only_network_attempted": self.read_only_network_attempted,
            "order_network_attempted": self.order_network_attempted,
            "network_attempted": self.network_attempted,
            "order_endpoint_called": self.order_endpoint_called,
            "order_sent": self.order_sent,
            "bybit_ret_code": self.bybit_ret_code,
            "bybit_order_id": self.bybit_order_id,
            "real_execute_disabled_stage1": self.real_execute_disabled_stage1,
            "fake_sender_used": self.fake_sender_used,
            "sender_call_count": self.sender_call_count,
            "allowed_environment": self.allowed_environment,
            "allowed_symbol": self.allowed_symbol,
            "allowed_side": self.allowed_side,
            "allowed_order_type": self.allowed_order_type,
            "allowed_time_in_force": self.allowed_time_in_force,
            "allowed_max_order_count": self.allowed_max_order_count,
            "tiny_qty_cap_sol": self.tiny_qty_cap_sol,
            "tiny_size_cap_usdt": self.tiny_size_cap_usdt,
            "max_demo_min_qty_notional_cap_usdt": (
                self.max_demo_min_qty_notional_cap_usdt
            ),
            "protected_symbols_untouched": self.protected_symbols_untouched,
            "instrument_rules_report": self.instrument_rules_report,
            "cap_escalation_report": self.cap_escalation_report,
            "wiring_report": self.wiring_report,
            "bm_report": self.bm_report,
            "generated_at_utc": self.generated_at_utc,
            "real_demo_execute_requested": self.real_demo_execute_requested,
            "real_demo_execute_authorized": self.real_demo_execute_authorized,
            "real_demo_authorization_marker_match": (
                self.real_demo_authorization_marker_match
            ),
            "credentials_source": self.credentials_source,
            "resolved_execution_qty": self.resolved_execution_qty,
            "resolved_execution_qty_source": (
                self.resolved_execution_qty_source
            ),
            "resolved_notional": self.resolved_notional,
            "bybit_ret_msg": self.bybit_ret_msg,
            "final_status": self.final_status,
            "simulated_order_network_attempted": (
                self.simulated_order_network_attempted
            ),
            "simulated_order_endpoint_called": (
                self.simulated_order_endpoint_called
            ),
            "simulated_order_sent": self.simulated_order_sent,
            "real_order_network_attempted": (
                self.real_order_network_attempted
            ),
            "real_order_endpoint_called": (
                self.real_order_endpoint_called
            ),
            "real_order_sent": self.real_order_sent,
            "order_transport_kind": self.order_transport_kind,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        try:
            value = to_dict()
            if isinstance(value, dict):
                return value
        except Exception:
            return {}
    return {}


def _ir_validate(report: bm_ir.InstrumentRulesReport) -> tuple[bool, str]:
    """Verify IR matches the locked SOLUSDT contract.

    Returns ``(ok, reason)``.
    """

    if not bool(getattr(report, "instrument_rules_loaded", False)):
        return False, "instrument_rules not loaded"
    rules = getattr(report, "rules", None)
    if rules is None:
        return False, "rules object missing"
    if str(getattr(rules, "symbol", "")) != ALLOWED_SYMBOL:
        return False, f"symbol {getattr(rules, 'symbol', '')!r} != {ALLOWED_SYMBOL!r}"
    if str(getattr(rules, "status", "")) != EXPECTED_INSTRUMENT_STATUS:
        return (
            False,
            f"status {getattr(rules, 'status', '')!r} != "
            f"{EXPECTED_INSTRUMENT_STATUS!r}",
        )
    if str(getattr(rules, "min_order_qty", "")) != EXPECTED_MIN_ORDER_QTY:
        return (
            False,
            f"min_order_qty {getattr(rules, 'min_order_qty', '')!r} != "
            f"{EXPECTED_MIN_ORDER_QTY!r}",
        )
    if str(getattr(rules, "qty_step", "")) != EXPECTED_QTY_STEP:
        return (
            False,
            f"qty_step {getattr(rules, 'qty_step', '')!r} != "
            f"{EXPECTED_QTY_STEP!r}",
        )
    candidate = getattr(report, "candidate", None)
    if candidate is None:
        return False, "candidate qty object missing"
    cand_qty = str(getattr(candidate, "candidate_qty", ""))
    if cand_qty != EXPECTED_CANDIDATE_QTY:
        return (
            False,
            f"candidate_qty {cand_qty!r} != {EXPECTED_CANDIDATE_QTY!r}",
        )
    if not bool(getattr(candidate, "confirms_qty_0_01_invalid", False)):
        return False, "candidate does not confirm qty=0.01 invalid"
    return True, ""


def _bm_terminal_status_to_orchestration_status(
    bm_status: str,
    *,
    fake_sender_was_called: bool,
    ir_network_attempted: bool = False,
) -> tuple[str, str]:
    """Map a BM ``final_status`` to an orchestration status."""

    if bm_status == bm.STATUS_EXECUTED_DEMO_ONLY:
        return (
            STATUS_OK_FAKE_SENDER_EXECUTED,
            "BM executed demo-only via injected fake sender",
        )
    if bm_status == bm.STATUS_WIRING_REQUIRED_NO_NETWORK:
        return (
            STATUS_REJECTED_BODY_QTY_NOT_AUTHORIZED,
            "BM rejected pre-network: WIRING_REQUIRED_NO_NETWORK",
        )
    if bm_status == bm.STATUS_GATE_REJECTED_NO_NETWORK:
        return (
            STATUS_REJECTED_BM_FAILED_CLOSED,
            "BM rejected pre-network: GATE_REJECTED_NO_NETWORK",
        )
    if bm_status == bm.STATUS_MISSING_DEMO_CREDENTIALS:
        return (
            STATUS_REJECTED_MISSING_CREDENTIALS,
            "BM rejected: MISSING_DEMO_CREDENTIALS",
        )
    if bm_status == bm.STATUS_NETWORK_ERROR_DEMO_ONLY:
        return (
            STATUS_REJECTED_BM_NETWORK_ERROR,
            "fake sender reported network error",
        )
    if bm_status == bm.STATUS_BYBIT_REJECTED_NO_ORDER_SENT:
        return (
            STATUS_REJECTED_BM_BYBIT_NOT_EXECUTED,
            "Bybit (fake) replied non-zero retCode or empty orderId",
        )
    if bm_status == bm.STATUS_READINESS_OK_NO_NETWORK:
        if ir_network_attempted:
            return (
                STATUS_OK_READINESS_READ_ONLY_NETWORK,
                "BM readiness ok; one authorized public read-only "
                "instrument-rules GET completed; no order network call "
                "attempted.",
            )
        return (
            STATUS_OK_READINESS_NO_NETWORK,
            "BM readiness ok; no network attempted",
        )
    if bm_status == bm.STATUS_DRY_RUN_OK_NO_NETWORK:
        if ir_network_attempted:
            return (
                STATUS_OK_READINESS_READ_ONLY_NETWORK,
                "BM dry-run ok; one authorized public read-only "
                "instrument-rules GET completed; no order network call "
                "attempted.",
            )
        return (
            STATUS_OK_READINESS_NO_NETWORK,
            "BM dry-run ok; no network attempted",
        )
    return (
        STATUS_REJECTED_BM_FAILED_CLOSED,
        f"unexpected BM final_status={bm_status!r}",
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_one_shot_authorized_execution_orchestration(
    *,
    mark_price: str | Decimal,
    mode: str = ORCH_MODE_READINESS,
    explicit_demo_min_qty_cap_authorization_flag: bool = False,
    explicit_demo_min_qty_cap_authorization_marker: str = "",
    ir_mode: str = bm_ir.MODE_OFFLINE,
    ir_pre_parsed_response: Mapping[str, Any] | None = None,
    ir_sender: Any | None = None,
    bm_credentials: bm.DemoCredentials | None = None,
    bm_fake_sender: Any | None = None,
    allow_real_ir_get: bool = False,
    explicit_real_demo_execute_flag: bool = False,
    explicit_real_demo_execute_authorization_marker: str = "",
) -> OrchestrationReport:
    """Run the full Stage 1 demo-only one-shot orchestration.

    See module docstring for the orchestration sequence and Stage 1
    constraints. The orchestrator returns a frozen
    :class:`OrchestrationReport` describing every chain step, and
    never raises on a chain rejection -- all rejections are surfaced
    via the report's ``status`` and ``reason`` fields.

    The orchestrator raises
    :class:`OneShotAuthorizedExecutionOrchestratorError` only for
    *static* programmer errors that would otherwise let an unsafe
    configuration slip past (e.g. asking for real IR network access
    without the explicit opt-in, or supplying a non-callable sender).
    """

    real_demo_requested = (mode == ORCH_MODE_EXECUTE_REAL_DEMO_ORDER)
    real_demo_marker_match = (
        explicit_real_demo_execute_authorization_marker
        == EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER
    )
    real_demo_authorized = bool(
        real_demo_requested
        and explicit_real_demo_execute_flag
        and real_demo_marker_match
    )
    credentials_source = (
        CREDENTIALS_SOURCE_INJECTED
        if bm_credentials is not None
        else CREDENTIALS_SOURCE_NONE
    )

    real_demo_audit = {
        "real_demo_execute_requested": real_demo_requested,
        "real_demo_execute_authorized": real_demo_authorized,
        "real_demo_authorization_marker_match": real_demo_marker_match,
        "credentials_source": credentials_source,
    }

    if mode not in ORCH_SUPPORTED_MODES:
        return _build_rejection_report(
            mode=mode,
            status=STATUS_REJECTED_UNSUPPORTED_MODE,
            reason=(
                f"mode {mode!r} not in supported set {ORCH_SUPPORTED_MODES!r}"
            ),
            fake_sender_used=False,
            sender_call_count=0,
            **real_demo_audit,
        )

    # TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1:
    # gate the new real-demo execute mode on the explicit flag + exact
    # marker BEFORE running any chain step. Reject pre-network.
    if real_demo_requested:
        if not explicit_real_demo_execute_flag:
            return _build_rejection_report(
                mode=mode,
                status=STATUS_REJECTED_REAL_EXECUTE_NOT_AUTHORIZED,
                reason=(
                    "execute_real_demo_order mode requires "
                    "explicit_real_demo_execute_flag=True"
                ),
                fake_sender_used=False,
                sender_call_count=0,
                **real_demo_audit,
            )
        if not real_demo_marker_match:
            return _build_rejection_report(
                mode=mode,
                status=STATUS_REJECTED_REAL_EXECUTE_MARKER_MISMATCH,
                reason=(
                    "explicit_real_demo_execute_authorization_marker does "
                    "not match the exact required marker"
                ),
                fake_sender_used=False,
                sender_call_count=0,
                **real_demo_audit,
            )
        # TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1_DISCOVERY_GATE_FIX:
        # the real-demo execute surface MUST require a fresh public read-only
        # instrument-rules discovery path. Cached / pre-parsed rules are
        # forbidden so that the live demo instrument contract cannot diverge
        # from the validated chain. This gate runs BEFORE any IR or order
        # sender invocation.
        if (
            ir_mode != bm_ir.MODE_DISCOVER
            or ir_pre_parsed_response is not None
        ):
            return _build_rejection_report(
                mode=mode,
                status=STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED,
                reason=(
                    "execute_real_demo_order requires ir_mode=discover with "
                    "no cached/pre-parsed instrument rules. Got "
                    f"ir_mode={ir_mode!r}, ir_pre_parsed_response_set="
                    f"{ir_pre_parsed_response is not None}."
                ),
                fake_sender_used=False,
                sender_call_count=0,
                **real_demo_audit,
            )
        if not allow_real_ir_get:
            return _build_rejection_report(
                mode=mode,
                status=STATUS_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED,
                reason=(
                    "execute_real_demo_order requires the explicit public "
                    "read-only discovery opt-in (allow_real_ir_get=True / "
                    "CLI --i-understand-this-performs-one-public-read-only-"
                    "instrument-rules-get) before any IR or order sender "
                    "can run."
                ),
                fake_sender_used=False,
                sender_call_count=0,
                **real_demo_audit,
            )

    # Stage 1 hard block: any real IR network access requires explicit
    # opt-in. Stage 1 callers never set it.
    if ir_mode == bm_ir.MODE_DISCOVER and ir_sender is None and not allow_real_ir_get:
        raise OneShotAuthorizedExecutionOrchestratorError(
            "Stage 1 forbids real IR network GET without an injected "
            "ir_sender. Pass an injected sender, switch to offline mode "
            "with pre_parsed_response, or explicitly opt in via "
            "allow_real_ir_get=True (not used by Stage 1 callers)."
        )
    if ir_sender is not None and not callable(ir_sender):
        raise OneShotAuthorizedExecutionOrchestratorError(
            "ir_sender must be a callable accepting a URL string"
        )

    # ----- 1. Instrument rules discovery --------------------------------
    ir_report = bm_ir.run_instrument_rules_discovery(
        mode=ir_mode,
        mark_price=mark_price,
        category=ALLOWED_CATEGORY,
        symbol=ALLOWED_SYMBOL,
        sender=ir_sender,
        pre_parsed_response=ir_pre_parsed_response,
    )
    # Track whether a real public read-only GET was attempted.
    # Any MODE_DISCOVER run (injected sender or stdlib) constitutes one.
    ir_network_attempted = (ir_mode == bm_ir.MODE_DISCOVER)

    ir_ok, ir_reason = _ir_validate(ir_report)
    if not ir_ok:
        return _build_rejection_report(
            mode=mode,
            status=(
                STATUS_REJECTED_RULES_NOT_LOADED
                if not bool(
                    getattr(ir_report, "instrument_rules_loaded", False)
                )
                else STATUS_REJECTED_RULES_INVALID
            ),
            reason=f"instrument rules check failed: {ir_reason}",
            instrument_rules_report=_safe_to_dict(ir_report),
            fake_sender_used=False,
            sender_call_count=0,
            ir_network_attempted=ir_network_attempted,
            **real_demo_audit,
        )

    candidate = getattr(ir_report, "candidate")
    candidate_qty = str(getattr(candidate, "candidate_qty", ""))
    candidate_notional = str(getattr(candidate, "candidate_notional", ""))

    # ----- 2. Cap-escalation gate ---------------------------------------
    request = bm_ce.EscalationAuthorizationRequest(
        environment=ALLOWED_ENVIRONMENT,
        symbol=ALLOWED_SYMBOL,
        side=ALLOWED_SIDE,
        order_type=ALLOWED_ORDER_TYPE,
        time_in_force=ALLOWED_TIME_IN_FORCE,
        proposed_qty=candidate_qty,
        max_order_count=ALLOWED_MAX_ORDER_COUNT,
        reduce_only=False,
        close_on_trigger=False,
        stop_loss="",
        take_profit="",
        endpoint_url_hint="",
        explicit_demo_min_qty_cap_authorization_flag=(
            explicit_demo_min_qty_cap_authorization_flag
        ),
        explicit_demo_min_qty_cap_authorization_marker=(
            explicit_demo_min_qty_cap_authorization_marker
        ),
    )
    ce_report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir_report,
        request=request,
        max_demo_min_qty_notional_cap_usdt=MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT,
    )

    cap_decision = getattr(ce_report, "decision", None)
    cap_gate_status = str(getattr(cap_decision, "status", "") or "")
    if cap_gate_status != bm_ce.STATUS_ESCALATION_AUTHORIZED:
        return _build_rejection_report(
            mode=mode,
            status=STATUS_REJECTED_CAP_GATE_NOT_AUTHORIZED,
            reason=(
                f"cap_gate_status={cap_gate_status!r} != "
                f"{bm_ce.STATUS_ESCALATION_AUTHORIZED!r}"
            ),
            instrument_rules_report=_safe_to_dict(ir_report),
            cap_escalation_report=_safe_to_dict(ce_report),
            cap_gate_status=cap_gate_status,
            fake_sender_used=False,
            sender_call_count=0,
            ir_network_attempted=ir_network_attempted,
            **real_demo_audit,
        )

    # ----- 3. Authorized execution qty wiring ---------------------------
    wiring_report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir_report,
        cap_escalation_report=ce_report,
    )
    resolution = getattr(wiring_report, "resolution")
    wiring_status = str(getattr(resolution, "status", "") or "")
    wiring_source = str(getattr(resolution, "execution_qty_source", "") or "")
    wiring_qty = str(getattr(resolution, "execution_qty", "") or "")

    if (
        wiring_status != bm_wire.STATUS_WIRING_AUTHORIZED_CANDIDATE_QTY
        or wiring_source
        != bm_wire.EXECUTION_QTY_SOURCE_CAP_ESCALATION_AUTHORIZED
        or wiring_qty != EXPECTED_CANDIDATE_QTY
        or not bool(getattr(resolution, "cap_escalated_demo_only", False))
        or not bool(getattr(resolution, "qty_0_01_confirmed_invalid", False))
    ):
        return _build_rejection_report(
            mode=mode,
            status=STATUS_REJECTED_WIRING_NOT_AUTHORIZED,
            reason=(
                f"wiring status={wiring_status!r}, source={wiring_source!r}, "
                f"qty={wiring_qty!r} -- does not satisfy authorized contract"
            ),
            instrument_rules_report=_safe_to_dict(ir_report),
            cap_escalation_report=_safe_to_dict(ce_report),
            wiring_report=_safe_to_dict(wiring_report),
            cap_gate_status=cap_gate_status,
            wiring_status=wiring_status,
            wiring_execution_qty_source=wiring_source,
            wiring_execution_qty=wiring_qty,
            fake_sender_used=False,
            sender_call_count=0,
            ir_network_attempted=ir_network_attempted,
            **real_demo_audit,
        )

    # ----- 4. Hand the authorized wiring to BM --------------------------
    bm_mode_to_use, fake_sender_used, sender_call_count, bm_report = (
        _invoke_bm(
            mode=mode,
            wiring_report=wiring_report,
            bm_credentials=bm_credentials,
            bm_fake_sender=bm_fake_sender,
        )
    )

    if bm_report is None:
        # _invoke_bm refused to run. Disambiguate by mode:
        #   * ORCH_MODE_EXECUTE_REAL_DEMO_ORDER: Stage 1 forbids the real
        #     send path. If no demo credentials -> MISSING_CREDENTIALS;
        #     otherwise REAL_EXECUTE_FORBIDDEN_STAGE1 (no fake sender for
        #     offline validation).
        #   * ORCH_MODE_EXECUTE_WITH_FAKE_SENDER: usual missing creds /
        #     missing fake sender.
        if mode == ORCH_MODE_EXECUTE_REAL_DEMO_ORDER:
            if bm_credentials is None:
                reject_status = STATUS_REJECTED_MISSING_CREDENTIALS
                reason = (
                    "execute_real_demo_order mode requires Bybit Demo "
                    "credentials (none supplied)"
                )
            else:
                reject_status = STATUS_REJECTED_REAL_EXECUTE_FORBIDDEN_STAGE1
                reason = (
                    "Stage 1 forbids real /v5/order/create. A separate human-"
                    "authorization task is required before Stage 2 can dispatch "
                    "a real Bybit Demo order. For Stage 1 offline validation, "
                    "supply a callable bm_fake_sender."
                )
        elif mode == ORCH_MODE_EXECUTE_WITH_FAKE_SENDER:
            reject_status = (
                STATUS_REJECTED_MISSING_CREDENTIALS
                if bm_credentials is None
                else STATUS_REJECTED_MISSING_FAKE_SENDER
            )
            reason = (
                "execute_with_fake_sender mode requires both DemoCredentials "
                "and a callable fake bm_fake_sender"
            )
        else:
            reject_status = STATUS_REJECTED_BM_FAILED_CLOSED
            reason = "BM was not invoked (internal)"
        return _build_rejection_report(
            mode=mode,
            status=reject_status,
            reason=reason,
            instrument_rules_report=_safe_to_dict(ir_report),
            cap_escalation_report=_safe_to_dict(ce_report),
            wiring_report=_safe_to_dict(wiring_report),
            cap_gate_status=cap_gate_status,
            wiring_status=wiring_status,
            wiring_execution_qty_source=wiring_source,
            wiring_execution_qty=wiring_qty,
            candidate_qty=candidate_qty,
            candidate_notional=candidate_notional,
            fake_sender_used=False,
            sender_call_count=0,
            ir_network_attempted=ir_network_attempted,
            resolved_execution_qty=wiring_qty,
            resolved_execution_qty_source=wiring_source,
            **real_demo_audit,
        )

    bm_final_status = str(getattr(bm_report, "final_status", "") or "")
    orch_status, orch_reason = _bm_terminal_status_to_orchestration_status(
        bm_final_status,
        fake_sender_was_called=fake_sender_used,
        ir_network_attempted=ir_network_attempted,
    )

    return _build_full_report(
        mode=mode,
        bm_mode=bm_mode_to_use,
        status=orch_status,
        reason=orch_reason,
        ir_report=ir_report,
        ce_report=ce_report,
        wiring_report=wiring_report,
        bm_report=bm_report,
        fake_sender_used=fake_sender_used,
        sender_call_count=sender_call_count,
        ir_network_attempted=ir_network_attempted,
        **real_demo_audit,
    )


# ---------------------------------------------------------------------------
# BM invocation helper
# ---------------------------------------------------------------------------


def _invoke_bm(
    *,
    mode: str,
    wiring_report: Any,
    bm_credentials: bm.DemoCredentials | None,
    bm_fake_sender: Any | None,
) -> tuple[str, bool, int, bm.ExecutionReport | None]:
    """Run BM in the right mode for Stage 1.

    Returns ``(bm_mode, fake_sender_used, sender_call_count, bm_report)``.
    Returns ``(mode, False, 0, None)`` when the caller asked for
    execute_with_fake_sender but did not supply both credentials and a
    callable fake sender.
    """

    if mode == ORCH_MODE_READINESS:
        report = bm.run_explicit_tiny_order_execution(
            mode=bm.MODE_READINESS,
            execute_flag=False,
            confirm_flag=False,
            authorized_execution_qty_wiring=wiring_report,
        )
        return (bm.MODE_READINESS, False, 0, report)

    # ORCH_MODE_EXECUTE_WITH_FAKE_SENDER and
    # ORCH_MODE_EXECUTE_REAL_DEMO_ORDER (Stage 1) -- both hard-require
    # both demo credentials and a callable fake sender. The Stage 1
    # real-mode path is implemented as fake-sender-only validation; the
    # real /v5/order/create dispatch is unavailable until Stage 2.
    if bm_credentials is None or bm_fake_sender is None or not callable(
        bm_fake_sender
    ):
        return (bm.MODE_EXECUTE_DEMO_ORDER, False, 0, None)

    counter = {"n": 0}

    def counting_sender(url: str, headers: Mapping[str, str], body: bytes):
        # TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT_CORRECTION (Correction 2):
        # a fake sender that genuinely raises must not leak an uncaught
        # exception out of the public orchestration surface. Re-shape the
        # exception into the same network-error sentinel BM already
        # understands so the final status / audit fields stay safe and
        # consistent with the sentinel-based test, and so the simulated
        # transport facet correctly records
        # simulated_order_endpoint_called=True / simulated_order_sent=False.
        counter["n"] += 1
        try:
            return bm_fake_sender(url, headers, body)
        except Exception as exc:  # pragma: no cover - exercised by tests
            return {
                "_network_error": True,
                "_error_repr": f"{type(exc).__name__}: {exc}",
            }

    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm_credentials,
        sender=counting_sender,
        authorized_execution_qty_wiring=wiring_report,
    )
    return (bm.MODE_EXECUTE_DEMO_ORDER, True, int(counter["n"]), report)


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------


def _empty_dict() -> dict[str, Any]:
    return {}


def _validate_stage1_order_transport_kind(kind: str) -> None:
    """Fail-closed allowlist check for ``order_transport_kind``.

    TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT_CORRECTION (Correction 3):
    Stage 1 must *never* silently rewrite a forbidden or unknown
    transport-kind into ``NONE`` or ``FAKE_SENDER``. A forbidden /
    unknown value indicates an invariant violation and the orchestrator
    must surface it explicitly.

    Raises:
        OneShotAuthorizedExecutionOrchestratorError: when ``kind`` is
        ``REAL_DEMO_SENDER`` (Stage 1 forbidden) or not a member of the
        documented ``ORDER_TRANSPORT_KINDS`` allowlist.
    """

    if kind in STAGE1_FORBIDDEN_ORDER_TRANSPORT_KINDS:
        raise OneShotAuthorizedExecutionOrchestratorError(
            f"Stage 1 invariant violation: order_transport_kind="
            f"{kind!r} is forbidden in Stage 1 "
            f"(allowlist={ORDER_TRANSPORT_KINDS!r}, "
            f"forbidden={STAGE1_FORBIDDEN_ORDER_TRANSPORT_KINDS!r}). "
            "The orchestrator never silently normalizes this value -- "
            "any caller path that derives REAL_DEMO_SENDER must be fixed."
        )
    if kind not in ORDER_TRANSPORT_KINDS:
        raise OneShotAuthorizedExecutionOrchestratorError(
            f"unknown order_transport_kind={kind!r}; expected one of "
            f"{ORDER_TRANSPORT_KINDS!r}"
        )


def _build_rejection_report(
    *,
    mode: str,
    status: str,
    reason: str,
    instrument_rules_report: dict[str, Any] | None = None,
    cap_escalation_report: dict[str, Any] | None = None,
    wiring_report: dict[str, Any] | None = None,
    bm_report: dict[str, Any] | None = None,
    cap_gate_status: str = "",
    wiring_status: str = "",
    wiring_execution_qty_source: str = "",
    wiring_execution_qty: str = "",
    candidate_qty: str = "",
    candidate_notional: str = "",
    fake_sender_used: bool = False,
    sender_call_count: int = 0,
    ir_network_attempted: bool = False,
    real_demo_execute_requested: bool = False,
    real_demo_execute_authorized: bool = False,
    real_demo_authorization_marker_match: bool = False,
    credentials_source: str = CREDENTIALS_SOURCE_NONE,
    resolved_execution_qty: str = "",
    resolved_execution_qty_source: str = "",
    resolved_notional: str = "",
    bybit_ret_msg: str = "",
    simulated_order_network_attempted: bool = False,
    simulated_order_endpoint_called: bool = False,
    simulated_order_sent: bool = False,
    real_order_network_attempted: bool = False,
    real_order_endpoint_called: bool = False,
    real_order_sent: bool = False,
    order_transport_kind: str = ORDER_TRANSPORT_KIND_NONE,
) -> OrchestrationReport:
    ir_dict = instrument_rules_report or {}
    rules = (ir_dict.get("rules") or {}) if isinstance(ir_dict, dict) else {}
    if not candidate_qty:
        cand = ir_dict.get("candidate") if isinstance(ir_dict, dict) else None
        if isinstance(cand, dict):
            candidate_qty = str(cand.get("candidate_qty", "") or "")
            candidate_notional = str(cand.get("candidate_notional", "") or "")
    # TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT_CORRECTION (Correction 3):
    # fail closed on a forbidden or unknown transport-kind. No silent
    # normalization. Rejection paths must never emit a misleading NONE
    # for a REAL_DEMO_SENDER input.
    _validate_stage1_order_transport_kind(order_transport_kind)
    # Aggregate OR legacy fields for the transport-attempt facets only.
    # ``order_sent`` is NOT an OR aggregate -- it preserves its prior
    # business-outcome meaning (the exchange-shaped response accepted the
    # order). Rejection paths never produced a business outcome, so the
    # legacy field is False.
    agg_order_network_attempted = bool(
        simulated_order_network_attempted or real_order_network_attempted
    )
    agg_order_endpoint_called = bool(
        simulated_order_endpoint_called or real_order_endpoint_called
    )
    agg_order_sent = False
    agg_network_attempted = bool(
        ir_network_attempted or agg_order_network_attempted
    )
    return OrchestrationReport(
        task_id=TASK_ID,
        identity=IDENTITY,
        phase=IMPLEMENTATION_PATH_PHASE,
        upstream_tasks=UPSTREAM_TASKS,
        next_required_task=NEXT_REQUIRED_TASK,
        is_review_chain_suffix=IS_REVIEW_CHAIN_SUFFIX,
        orchestration_contract_version=ORCHESTRATION_CONTRACT_VERSION,
        mode=mode,
        status=status,
        reason=reason,
        instrument_rules_loaded=bool(
            ir_dict.get("instrument_rules_loaded", False)
        ),
        instrument_rules_status=str(ir_dict.get("discovery_status", "") or ""),
        instrument_rules_symbol=str((rules or {}).get("symbol", "") or ""),
        instrument_rules_trading_status=str(
            (rules or {}).get("status", "") or ""
        ),
        instrument_rules_min_order_qty=str(
            (rules or {}).get("min_order_qty", "") or ""
        ),
        instrument_rules_qty_step=str(
            (rules or {}).get("qty_step", "") or ""
        ),
        candidate_qty=candidate_qty,
        candidate_notional=candidate_notional,
        qty_0_01_confirmed_invalid=bool(
            ((ir_dict.get("candidate") or {}) if isinstance(ir_dict, dict) else {}).get(
                "confirms_qty_0_01_invalid", False
            )
        ),
        cap_gate_status=cap_gate_status,
        cap_gate_authorized=False,
        cap_escalated_demo_only=False,
        explicit_demo_min_qty_cap_authorized=False,
        wiring_status=wiring_status,
        wiring_execution_qty_source=wiring_execution_qty_source,
        wiring_execution_qty=wiring_execution_qty,
        wiring_execution_notional_estimate="",
        bm_invoked=False,
        bm_mode="",
        bm_final_status="",
        original_packet_qty=ORIGINAL_PACKET_QTY,
        actual_request_body_qty="",
        actual_request_body_qty_source="",
        body_qty_authorized_override=False,
        body_qty_rejection_reason="",
        read_only_network_attempted=ir_network_attempted,
        order_network_attempted=agg_order_network_attempted,
        network_attempted=agg_network_attempted,
        order_endpoint_called=agg_order_endpoint_called,
        order_sent=agg_order_sent,
        bybit_ret_code=None,
        bybit_order_id="",
        real_execute_disabled_stage1=True,
        fake_sender_used=fake_sender_used,
        sender_call_count=sender_call_count,
        allowed_environment=ALLOWED_ENVIRONMENT,
        allowed_symbol=ALLOWED_SYMBOL,
        allowed_side=ALLOWED_SIDE,
        allowed_order_type=ALLOWED_ORDER_TYPE,
        allowed_time_in_force=ALLOWED_TIME_IN_FORCE,
        allowed_max_order_count=ALLOWED_MAX_ORDER_COUNT,
        tiny_qty_cap_sol=format(bh.TINY_QTY_CAP_SOL, "f"),
        tiny_size_cap_usdt=format(bh.TINY_SIZE_CAP_USDT, "f"),
        max_demo_min_qty_notional_cap_usdt=format(
            MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT, "f"
        ),
        protected_symbols_untouched=True,
        instrument_rules_report=ir_dict if isinstance(ir_dict, dict) else {},
        cap_escalation_report=cap_escalation_report or {},
        wiring_report=wiring_report or {},
        bm_report=bm_report or {},
        generated_at_utc=_utc_timestamp(),
        real_demo_execute_requested=real_demo_execute_requested,
        real_demo_execute_authorized=real_demo_execute_authorized,
        real_demo_authorization_marker_match=real_demo_authorization_marker_match,
        credentials_source=credentials_source,
        resolved_execution_qty=resolved_execution_qty,
        resolved_execution_qty_source=resolved_execution_qty_source,
        resolved_notional=resolved_notional,
        bybit_ret_msg=bybit_ret_msg,
        final_status=status,
        simulated_order_network_attempted=bool(
            simulated_order_network_attempted
        ),
        simulated_order_endpoint_called=bool(
            simulated_order_endpoint_called
        ),
        simulated_order_sent=bool(simulated_order_sent),
        real_order_network_attempted=bool(real_order_network_attempted),
        real_order_endpoint_called=bool(real_order_endpoint_called),
        real_order_sent=bool(real_order_sent),
        order_transport_kind=order_transport_kind,
    )


def _build_full_report(
    *,
    mode: str,
    bm_mode: str,
    status: str,
    reason: str,
    ir_report: Any,
    ce_report: Any,
    wiring_report: Any,
    bm_report: Any,
    fake_sender_used: bool,
    sender_call_count: int,
    ir_network_attempted: bool = False,
    real_demo_execute_requested: bool = False,
    real_demo_execute_authorized: bool = False,
    real_demo_authorization_marker_match: bool = False,
    credentials_source: str = CREDENTIALS_SOURCE_NONE,
) -> OrchestrationReport:
    rules = getattr(ir_report, "rules", None)
    candidate = getattr(ir_report, "candidate", None)
    resolution = getattr(wiring_report, "resolution", None)
    cap_decision = getattr(ce_report, "decision", None)
    # TASK-014BM_STAGE1_REAL_VS_SIMULATED_ORDER_AUDIT_SEMANTICS_SPLIT:
    # Stage 1 always classifies any BM execute traffic as the simulated
    # (injected fake sender) facet. The real-network facet is hard
    # forbidden -- the real /v5/order/create dispatch is unreachable
    # from this orchestrator's _invoke_bm. ``fake_sender_used`` is the
    # authoritative signal that BM ran through the injected counting
    # wrapper. When it is False (e.g. readiness mode) the order
    # transport is NONE and all split fields are False.
    bm_network_attempted = bool(
        getattr(bm_report, "network_attempted", False)
    )
    bm_endpoint_called = bool(
        getattr(bm_report, "order_endpoint_called", False)
    )
    bm_final_status_value = str(
        getattr(bm_report, "final_status", "") or ""
    )
    # The simulated order body is considered "sent" whenever the fake
    # transport completed a normal call to the endpoint, regardless of
    # the Bybit business retCode (a non-zero retCode is still a normal
    # response: the body was transported and Bybit replied). Only a
    # sender exception (surfaced as STATUS_NETWORK_ERROR_DEMO_ONLY)
    # leaves the body un-sent.
    bm_simulated_body_sent = bool(
        bm_endpoint_called
        and bm_final_status_value != bm.STATUS_NETWORK_ERROR_DEMO_ONLY
    )
    if fake_sender_used:
        sim_network_attempted = bm_network_attempted
        sim_endpoint_called = bm_endpoint_called
        sim_order_sent = bm_simulated_body_sent
        transport_kind = ORDER_TRANSPORT_KIND_FAKE_SENDER
    else:
        sim_network_attempted = False
        sim_endpoint_called = False
        sim_order_sent = False
        transport_kind = ORDER_TRANSPORT_KIND_NONE
    real_network_attempted = False
    real_endpoint_called = False
    real_order_sent = False
    # TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT_CORRECTION (Correction 3):
    # fail closed on a forbidden or unknown transport-kind. No silent
    # rewrite from REAL_DEMO_SENDER to FAKE_SENDER -- a derivation that
    # produces REAL_DEMO_SENDER here is an invariant violation.
    _validate_stage1_order_transport_kind(transport_kind)
    # TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT_CORRECTION (Correction 1):
    # ``order_network_attempted`` / ``order_endpoint_called`` remain the
    # aggregate transport-attempt compatibility fields. ``order_sent``
    # preserves the prior business-outcome meaning -- the exchange-shaped
    # response accepted the order and returned a non-empty order id.
    # Source it directly from BM's ``SendOutcome.order_sent`` (BM already
    # computes ``(ret_code == 0) and bool(order_id)``). A simulated fake
    # sender that returns a nonzero ``retCode`` therefore correctly
    # produces ``simulated_order_sent=True`` AND legacy ``order_sent=False``.
    agg_order_network_attempted = bool(
        sim_network_attempted or real_network_attempted
    )
    agg_order_endpoint_called = bool(
        sim_endpoint_called or real_endpoint_called
    )
    agg_order_sent = bool(getattr(bm_report, "order_sent", False))
    agg_network_attempted = bool(
        ir_network_attempted or agg_order_network_attempted
    )
    return OrchestrationReport(
        task_id=TASK_ID,
        identity=IDENTITY,
        phase=IMPLEMENTATION_PATH_PHASE,
        upstream_tasks=UPSTREAM_TASKS,
        next_required_task=NEXT_REQUIRED_TASK,
        is_review_chain_suffix=IS_REVIEW_CHAIN_SUFFIX,
        orchestration_contract_version=ORCHESTRATION_CONTRACT_VERSION,
        mode=mode,
        status=status,
        reason=reason,
        instrument_rules_loaded=bool(
            getattr(ir_report, "instrument_rules_loaded", False)
        ),
        instrument_rules_status=str(
            getattr(ir_report, "discovery_status", "") or ""
        ),
        instrument_rules_symbol=str(getattr(rules, "symbol", "") or ""),
        instrument_rules_trading_status=str(
            getattr(rules, "status", "") or ""
        ),
        instrument_rules_min_order_qty=str(
            getattr(rules, "min_order_qty", "") or ""
        ),
        instrument_rules_qty_step=str(getattr(rules, "qty_step", "") or ""),
        candidate_qty=str(getattr(candidate, "candidate_qty", "") or ""),
        candidate_notional=str(
            getattr(candidate, "candidate_notional", "") or ""
        ),
        qty_0_01_confirmed_invalid=bool(
            getattr(candidate, "confirms_qty_0_01_invalid", False)
        ),
        cap_gate_status=str(getattr(cap_decision, "status", "") or ""),
        cap_gate_authorized=bool(getattr(cap_decision, "authorized", False)),
        cap_escalated_demo_only=bool(
            getattr(cap_decision, "cap_escalated_demo_only", False)
        ),
        explicit_demo_min_qty_cap_authorized=bool(
            getattr(cap_decision, "explicit_demo_min_qty_cap_authorized", False)
        ),
        wiring_status=str(getattr(resolution, "status", "") or ""),
        wiring_execution_qty_source=str(
            getattr(resolution, "execution_qty_source", "") or ""
        ),
        wiring_execution_qty=str(
            getattr(resolution, "execution_qty", "") or ""
        ),
        wiring_execution_notional_estimate=str(
            getattr(resolution, "execution_notional_estimate", "") or ""
        ),
        bm_invoked=True,
        bm_mode=bm_mode,
        bm_final_status=str(getattr(bm_report, "final_status", "") or ""),
        original_packet_qty=ORIGINAL_PACKET_QTY,
        actual_request_body_qty=str(
            getattr(bm_report, "actual_request_body_qty", "") or ""
        ),
        actual_request_body_qty_source=str(
            getattr(bm_report, "actual_request_body_qty_source", "") or ""
        ),
        body_qty_authorized_override=bool(
            getattr(bm_report, "body_qty_authorized_override", False)
        ),
        body_qty_rejection_reason=str(
            getattr(bm_report, "body_qty_rejection_reason", "") or ""
        ),
        read_only_network_attempted=ir_network_attempted,
        order_network_attempted=agg_order_network_attempted,
        network_attempted=agg_network_attempted,
        order_endpoint_called=agg_order_endpoint_called,
        order_sent=agg_order_sent,
        bybit_ret_code=getattr(bm_report, "bybit_ret_code", None),
        bybit_order_id=str(getattr(bm_report, "bybit_order_id", "") or ""),
        real_execute_disabled_stage1=True,
        fake_sender_used=fake_sender_used,
        sender_call_count=sender_call_count,
        allowed_environment=ALLOWED_ENVIRONMENT,
        allowed_symbol=ALLOWED_SYMBOL,
        allowed_side=ALLOWED_SIDE,
        allowed_order_type=ALLOWED_ORDER_TYPE,
        allowed_time_in_force=ALLOWED_TIME_IN_FORCE,
        allowed_max_order_count=ALLOWED_MAX_ORDER_COUNT,
        tiny_qty_cap_sol=format(bh.TINY_QTY_CAP_SOL, "f"),
        tiny_size_cap_usdt=format(bh.TINY_SIZE_CAP_USDT, "f"),
        max_demo_min_qty_notional_cap_usdt=format(
            MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT, "f"
        ),
        protected_symbols_untouched=True,
        instrument_rules_report=_safe_to_dict(ir_report),
        cap_escalation_report=_safe_to_dict(ce_report),
        wiring_report=_safe_to_dict(wiring_report),
        bm_report=_safe_to_dict(bm_report),
        generated_at_utc=_utc_timestamp(),
        real_demo_execute_requested=real_demo_execute_requested,
        real_demo_execute_authorized=real_demo_execute_authorized,
        real_demo_authorization_marker_match=real_demo_authorization_marker_match,
        credentials_source=credentials_source,
        resolved_execution_qty=str(
            getattr(getattr(wiring_report, "resolution", None), "execution_qty", "") or ""
        ),
        resolved_execution_qty_source=str(
            getattr(getattr(wiring_report, "resolution", None), "execution_qty_source", "") or ""
        ),
        resolved_notional=str(
            getattr(getattr(wiring_report, "resolution", None), "execution_notional_estimate", "") or ""
        ),
        bybit_ret_msg=str(getattr(bm_report, "bybit_ret_msg", "") or ""),
        final_status=status,
        simulated_order_network_attempted=sim_network_attempted,
        simulated_order_endpoint_called=sim_endpoint_called,
        simulated_order_sent=sim_order_sent,
        real_order_network_attempted=real_network_attempted,
        real_order_endpoint_called=real_endpoint_called,
        real_order_sent=real_order_sent,
        order_transport_kind=transport_kind,
    )


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------


def _render_markdown(report: OrchestrationReport) -> str:
    lines: list[str] = []
    lines.append(
        f"# {report.task_id} -- one-shot authorized execution orchestrator"
    )
    lines.append("")
    lines.append(f"- identity: `{report.identity}`")
    lines.append(f"- phase: `{report.phase}`")
    lines.append(f"- mode: `{report.mode}`")
    lines.append(f"- status: `{report.status}`")
    lines.append(f"- reason: {report.reason or '(none)'}")
    lines.append(f"- generated_at_utc: `{report.generated_at_utc}`")
    lines.append("")
    lines.append("## Instrument rules")
    lines.append(
        f"- loaded={report.instrument_rules_loaded} "
        f"status=`{report.instrument_rules_status}` "
        f"symbol=`{report.instrument_rules_symbol}` "
        f"trading=`{report.instrument_rules_trading_status}`"
    )
    lines.append(
        f"- min_order_qty=`{report.instrument_rules_min_order_qty}` "
        f"qty_step=`{report.instrument_rules_qty_step}` "
        f"candidate_qty=`{report.candidate_qty}` "
        f"candidate_notional=`{report.candidate_notional}` "
        f"qty_0_01_confirmed_invalid={report.qty_0_01_confirmed_invalid}"
    )
    lines.append("")
    lines.append("## Cap-escalation gate")
    lines.append(
        f"- status=`{report.cap_gate_status}` "
        f"authorized={report.cap_gate_authorized} "
        f"cap_escalated_demo_only={report.cap_escalated_demo_only} "
        f"explicit_authorized={report.explicit_demo_min_qty_cap_authorized}"
    )
    lines.append("")
    lines.append("## Authorized wiring")
    lines.append(
        f"- status=`{report.wiring_status}` "
        f"source=`{report.wiring_execution_qty_source}` "
        f"execution_qty=`{report.wiring_execution_qty}` "
        f"notional=`{report.wiring_execution_notional_estimate}`"
    )
    lines.append("")
    lines.append("## BM execution")
    lines.append(
        f"- bm_invoked={report.bm_invoked} bm_mode=`{report.bm_mode}` "
        f"final_status=`{report.bm_final_status}`"
    )
    lines.append(
        f"- original_packet_qty=`{report.original_packet_qty}` "
        f"actual_request_body_qty=`{report.actual_request_body_qty}` "
        f"source=`{report.actual_request_body_qty_source}` "
        f"override={report.body_qty_authorized_override}"
    )
    lines.append(
        f"- read_only_network_attempted="
        f"{report.read_only_network_attempted} "
        f"order_network_attempted={report.order_network_attempted} "
        f"network_attempted={report.network_attempted}"
    )
    lines.append(
        f"- order_endpoint_called={report.order_endpoint_called} "
        f"order_sent={report.order_sent} "
        f"bybit_ret_code={report.bybit_ret_code} "
        f"bybit_order_id=`{report.bybit_order_id}`"
    )
    lines.append("")
    lines.append("## Safety")
    lines.append(
        f"- real_execute_disabled_stage1={report.real_execute_disabled_stage1} "
        f"fake_sender_used={report.fake_sender_used} "
        f"sender_call_count={report.sender_call_count}"
    )
    lines.append(
        f"- tiny_qty_cap_sol=`{report.tiny_qty_cap_sol}` "
        f"tiny_size_cap_usdt=`{report.tiny_size_cap_usdt}` "
        f"max_demo_min_qty_notional_cap_usdt=`"
        f"{report.max_demo_min_qty_notional_cap_usdt}` "
        f"protected_symbols_untouched={report.protected_symbols_untouched}"
    )
    lines.append("")
    lines.append("## Real-demo execute surface (Stage 1)")
    lines.append(
        f"- real_demo_execute_requested={report.real_demo_execute_requested} "
        f"real_demo_execute_authorized={report.real_demo_execute_authorized} "
        f"marker_match={report.real_demo_authorization_marker_match}"
    )
    lines.append(
        f"- credentials_source=`{report.credentials_source}` "
        f"resolved_execution_qty=`{report.resolved_execution_qty}` "
        f"resolved_execution_qty_source=`{report.resolved_execution_qty_source}` "
        f"resolved_notional=`{report.resolved_notional}`"
    )
    lines.append(
        f"- bybit_ret_msg=`{report.bybit_ret_msg}` "
        f"final_status=`{report.final_status}`"
    )
    lines.append("")
    lines.append("## Order activity audit (simulated vs real)")
    lines.append(
        f"- order_transport_kind=`{report.order_transport_kind}`"
    )
    lines.append(
        f"- simulated_order_network_attempted="
        f"{report.simulated_order_network_attempted} "
        f"simulated_order_endpoint_called="
        f"{report.simulated_order_endpoint_called} "
        f"simulated_order_sent={report.simulated_order_sent}"
    )
    lines.append(
        f"- real_order_network_attempted="
        f"{report.real_order_network_attempted} "
        f"real_order_endpoint_called={report.real_order_endpoint_called} "
        f"real_order_sent={report.real_order_sent}"
    )
    return "\n".join(lines) + "\n"


def write_report(
    report: OrchestrationReport,
    *,
    output_dir: pathlib.Path | str | None = None,
) -> dict[str, pathlib.Path]:
    """Write JSON + Markdown reports (timestamped + ``latest_*``)."""

    out_dir = pathlib.Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = REPORT_NAME
    paths = {
        "json_latest": out_dir / f"latest_{base}.json",
        "md_latest": out_dir / f"latest_{base}.md",
        "json_ts": out_dir / f"{base}_{ts}.json",
        "md_ts": out_dir / f"{base}_{ts}.md",
    }
    payload = json.dumps(report.to_dict(), indent=2, sort_keys=True, default=str)
    md = _render_markdown(report)
    paths["json_latest"].write_text(payload, encoding="utf-8")
    paths["md_latest"].write_text(md, encoding="utf-8")
    paths["json_ts"].write_text(payload, encoding="utf-8")
    paths["md_ts"].write_text(md, encoding="utf-8")
    return paths


__all__ = [
    "ALLOWED_CATEGORY",
    "ALLOWED_ENVIRONMENT",
    "ALLOWED_MAX_ORDER_COUNT",
    "ALLOWED_ORDER_TYPE",
    "ALLOWED_SIDE",
    "ALLOWED_SYMBOL",
    "ALLOWED_TIME_IN_FORCE",
    "CREDENTIALS_SOURCE_INJECTED",
    "CREDENTIALS_SOURCE_NONE",
    "DEFAULT_OUTPUT_DIR",
    "EXPECTED_CANDIDATE_QTY",
    "EXPECTED_INSTRUMENT_STATUS",
    "EXPECTED_MIN_ORDER_QTY",
    "EXPECTED_QTY_STEP",
    "EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER",
    "IDENTITY",
    "IMPLEMENTATION_PATH_PHASE",
    "IS_REVIEW_CHAIN_SUFFIX",
    "MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT",
    "NEXT_REQUIRED_TASK",
    "ORCHESTRATION_CONTRACT_VERSION",
    "ORCH_MODE_EXECUTE_REAL_DEMO_ORDER",
    "ORCH_MODE_EXECUTE_WITH_FAKE_SENDER",
    "ORCH_MODE_READINESS",
    "ORCH_SUPPORTED_MODES",
    "ORDER_TRANSPORT_KIND_FAKE_SENDER",
    "ORDER_TRANSPORT_KIND_NONE",
    "ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER",
    "ORDER_TRANSPORT_KINDS",
    "ORIGINAL_PACKET_QTY",
    "OneShotAuthorizedExecutionOrchestratorError",
    "OrchestrationReport",
    "REPORT_NAME",
    "STAGE1_FORBIDDEN_ORDER_TRANSPORT_KINDS",
    "STATUS_OK_FAKE_SENDER_EXECUTED",
    "STATUS_OK_READINESS_NO_NETWORK",
    "STATUS_OK_READINESS_READ_ONLY_NETWORK",
    "STATUS_REJECTED_BM_BYBIT_NOT_EXECUTED",
    "STATUS_REJECTED_BM_FAILED_CLOSED",
    "STATUS_REJECTED_BM_NETWORK_ERROR",
    "STATUS_REJECTED_BODY_QTY_NOT_AUTHORIZED",
    "STATUS_REJECTED_CAP_GATE_NOT_AUTHORIZED",
    "STATUS_REJECTED_MISSING_CREDENTIALS",
    "STATUS_REJECTED_MISSING_FAKE_SENDER",
    "STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED",
    "STATUS_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED",
    "STATUS_REJECTED_REAL_EXECUTE_FORBIDDEN_STAGE1",
    "STATUS_REJECTED_REAL_EXECUTE_MARKER_MISMATCH",
    "STATUS_REJECTED_REAL_EXECUTE_NOT_AUTHORIZED",
    "STATUS_REJECTED_RULES_INVALID",
    "STATUS_REJECTED_RULES_NOT_LOADED",
    "STATUS_REJECTED_UNSUPPORTED_MODE",
    "STATUS_REJECTED_WIRING_NOT_AUTHORIZED",
    "TASK_ID",
    "UPSTREAM_TASKS",
    "_validate_stage1_order_transport_kind",
    "run_one_shot_authorized_execution_orchestration",
    "write_report",
]
