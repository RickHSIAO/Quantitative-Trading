"""TASK-014BN_demo_only_tiny_execution_postfill_audit.

Offline / fake-only postfill audit scaffold for the one-shot
authorized execution orchestrator.

This module consumes an already-produced
:class:`OrchestrationReport` (from
``demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator``)
and re-validates the simulated Stage 1 fake-sender run against the
pre-validated cap-escalation contract:

    * Transport must be the injected fake sender (never the real demo
      sender). All ``real_order_*`` audit booleans must be False.
    * Stage 1 real execute path must remain disabled.
    * The exchange-shaped body that BM would have transmitted must
      match the locked SOLUSDT / linear / Buy / Market / IOC contract,
      with the authorized 0.1 candidate qty (NOT the BL packet 0.01),
      sourced from ``CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY``, with
      notional <= 20 USDT.
    * Cap gate / wiring authorization invariants must hold.
    * Legacy ``order_sent`` business-outcome semantics must be
      consistent with ``bybit_ret_code`` + ``bybit_order_id``.

This module is strictly OFFLINE / FAKE-ONLY:

    * Never sends any real or simulated order.
    * Never opens any HTTP connection.
    * Never imports the real Bybit executor, BybitExecutor,
      ``main.py``, ``src/risk.py``, ``src/executors/bybit.py``, or any
      live endpoint.
    * Never reads credentials.
    * Never mutates any global tiny cap, ``MAX_ORDER_COUNT``, the
      protected symbols denylist, or any BL packet field.
    * Does not authorize a Stage 2 real Bybit Demo dispatch.

The audit produces a frozen :class:`PostfillAuditReport` with one of
five terminal :data:`AUDIT_STATUS_*` values and a deterministic
list of 30 named integrity checks (each a frozen
:class:`PostfillAuditCheck`). A JSON + Markdown report writer is
included; nothing is written unless the caller asks for it.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from src import demo_only_tiny_execution_adapter as bh
from src import (
    demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator as orch,
)


# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------

TASK_ID = "TASK-014BN"
IDENTITY = "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-POSTFILL-AUDIT"
IMPLEMENTATION_PATH_PHASE = "tiny_order_postfill_audit"
IS_REVIEW_CHAIN_SUFFIX = False
UPSTREAM_TASKS: tuple[str, ...] = (
    "TASK-014BH",
    "TASK-014BM",
    "TASK-014BM_FIX",
    "TASK-014BM_MIN_QTY_FIX",
    "TASK-014BM_CAP_ESCALATION_GATE",
    "TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY",
    "TASK-014BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH",
    "TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR",
    "TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT",
)
NEXT_REQUIRED_TASK = (
    "TASK-014BNB_demo_only_tiny_execution_postfill_audit_vps_validation"
)

bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)

POSTFILL_AUDIT_CONTRACT_VERSION = (
    "demo_only_tiny_execution_adapter_tiny_order_postfill_audit_v1"
)

REPORT_NAME = "demo_only_tiny_execution_adapter_tiny_order_postfill_audit"
DEFAULT_OUTPUT_DIR = pathlib.Path("outputs/demo_trading") / REPORT_NAME


# ---------------------------------------------------------------------------
# Audit statuses
# ---------------------------------------------------------------------------

AUDIT_STATUS_SIMULATED_ACCEPTED = "POSTFILL_AUDIT_SIMULATED_ACCEPTED"
AUDIT_STATUS_SIMULATED_REJECTED = "POSTFILL_AUDIT_SIMULATED_REJECTED"
AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR = (
    "POSTFILL_AUDIT_SIMULATED_TRANSPORT_ERROR"
)
AUDIT_STATUS_NOT_AUDITABLE = "POSTFILL_AUDIT_NOT_AUDITABLE"
AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT = (
    "POSTFILL_AUDIT_FORBIDDEN_REAL_TRANSPORT"
)
AUDIT_STATUSES: tuple[str, ...] = (
    AUDIT_STATUS_SIMULATED_ACCEPTED,
    AUDIT_STATUS_SIMULATED_REJECTED,
    AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR,
    AUDIT_STATUS_NOT_AUDITABLE,
    AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT,
)
AUDIT_STATUSES_AUDITABLE: tuple[str, ...] = (
    AUDIT_STATUS_SIMULATED_ACCEPTED,
    AUDIT_STATUS_SIMULATED_REJECTED,
    AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR,
)


# ---------------------------------------------------------------------------
# Expected cap-escalation contract (locked Stage 1 invariants)
# ---------------------------------------------------------------------------

EXPECTED_SYMBOL = orch.ALLOWED_SYMBOL
EXPECTED_CATEGORY = orch.ALLOWED_CATEGORY
EXPECTED_SIDE = orch.ALLOWED_SIDE
EXPECTED_ORDER_TYPE = orch.ALLOWED_ORDER_TYPE
EXPECTED_TIME_IN_FORCE = orch.ALLOWED_TIME_IN_FORCE
EXPECTED_REDUCE_ONLY = False
EXPECTED_CLOSE_ON_TRIGGER = False
EXPECTED_ORIGINAL_PACKET_QTY = orch.ORIGINAL_PACKET_QTY  # "0.01"
EXPECTED_AUTHORIZED_QTY = orch.EXPECTED_CANDIDATE_QTY    # "0.1"
EXPECTED_AUTHORIZED_QTY_SOURCE = "CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY"
EXPECTED_WIRING_STATUS_AUTHORIZED = "WIRING_AUTHORIZED_CANDIDATE_QTY"
EXPECTED_MAX_NOTIONAL_USDT = orch.MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT


@dataclass(frozen=True)
class ExpectedContract:
    """Locked Stage 1 cap-escalation contract used by the audit."""

    symbol: str = EXPECTED_SYMBOL
    category: str = EXPECTED_CATEGORY
    side: str = EXPECTED_SIDE
    order_type: str = EXPECTED_ORDER_TYPE
    time_in_force: str = EXPECTED_TIME_IN_FORCE
    reduce_only: bool = EXPECTED_REDUCE_ONLY
    close_on_trigger: bool = EXPECTED_CLOSE_ON_TRIGGER
    original_packet_qty: str = EXPECTED_ORIGINAL_PACKET_QTY
    authorized_qty: str = EXPECTED_AUTHORIZED_QTY
    authorized_qty_source: str = EXPECTED_AUTHORIZED_QTY_SOURCE
    wiring_status_authorized: str = EXPECTED_WIRING_STATUS_AUTHORIZED
    max_notional_usdt: Decimal = EXPECTED_MAX_NOTIONAL_USDT

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "category": self.category,
            "side": self.side,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "reduce_only": self.reduce_only,
            "close_on_trigger": self.close_on_trigger,
            "original_packet_qty": self.original_packet_qty,
            "authorized_qty": self.authorized_qty,
            "authorized_qty_source": self.authorized_qty_source,
            "wiring_status_authorized": self.wiring_status_authorized,
            "max_notional_usdt": format(self.max_notional_usdt, "f"),
        }


DEFAULT_EXPECTED_CONTRACT = ExpectedContract()


# ---------------------------------------------------------------------------
# Deterministic check name registry
# ---------------------------------------------------------------------------

CHECK_NAMES: tuple[str, ...] = (
    "transport_is_fake_sender",
    "fake_sender_used",
    "sender_call_count_exactly_one",
    "simulated_network_attempted",
    "simulated_endpoint_called",
    "real_network_not_attempted",
    "real_endpoint_not_called",
    "real_order_not_sent",
    "stage1_real_execute_disabled",
    "symbol_is_solusdt",
    "category_is_linear",
    "side_is_buy",
    "order_type_is_market",
    "time_in_force_is_ioc",
    "reduce_only_false",
    "close_on_trigger_false",
    "original_packet_qty_is_0_01",
    "actual_qty_is_authorized_0_1",
    "actual_qty_source_is_authorized_candidate",
    "resolved_qty_is_authorized_0_1",
    "resolved_qty_source_is_authorized_candidate",
    "candidate_qty_is_0_1",
    "body_qty_authorized_override_true",
    "candidate_notional_within_20_usdt",
    "resolved_notional_within_20_usdt",
    "cap_gate_authorized",
    "wiring_authorized",
    "no_real_transport_evidence",
    "accepted_outcome_consistent",
    "no_protected_symbol_scope",
)
assert len(CHECK_NAMES) == 30
assert len(set(CHECK_NAMES)) == 30


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PostfillAuditError(bh.DemoOnlyTinyExecutionAdapterError):
    """Raised when the postfill audit detects a structural input error."""


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PostfillAuditCheck:
    """One named integrity check result."""

    name: str
    passed: bool
    expected: str
    actual: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "expected": self.expected,
            "actual": self.actual,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PostfillAuditReport:
    """Frozen postfill audit report over one orchestration run."""

    # Identity
    task_id: str
    identity: str
    phase: str
    upstream_tasks: tuple[str, ...]
    next_required_task: str
    is_review_chain_suffix: bool
    postfill_audit_contract_version: str

    # Overall audit
    audit_status: str
    audit_passed: bool
    audit_reason: str
    auditable: bool
    integrity_all_passed: bool
    integrity_failed_checks: tuple[str, ...]
    summary: str

    # Source orchestration provenance
    source_task_id: str
    source_status: str
    source_mode: str
    source_generated_at_utc: str

    # Transport evidence (re-stated from orchestration report)
    order_transport_kind: str
    fake_sender_used: bool
    sender_call_count: int
    simulated_order_network_attempted: bool
    simulated_order_endpoint_called: bool
    simulated_order_sent: bool
    real_order_network_attempted: bool
    real_order_endpoint_called: bool
    real_order_sent: bool
    real_execute_disabled_stage1: bool

    # Contract / qty evidence
    body_preview: dict[str, Any]
    original_packet_qty: str
    actual_request_body_qty: str
    actual_request_body_qty_source: str
    resolved_execution_qty: str
    resolved_execution_qty_source: str
    candidate_qty: str
    candidate_notional: str
    resolved_notional: str
    body_qty_authorized_override: bool
    cap_gate_authorized: bool
    cap_gate_status: str
    wiring_status: str

    # Business outcome
    order_sent: bool
    bybit_ret_code: int | None
    bybit_ret_msg: str
    bybit_order_id: str
    bm_final_status: str

    # Locks snapshot
    expected_contract: dict[str, Any]
    protected_symbols_untouched: bool

    # Checks
    checks: tuple[PostfillAuditCheck, ...]

    generated_at_utc: str
    audited_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "identity": self.identity,
            "phase": self.phase,
            "upstream_tasks": list(self.upstream_tasks),
            "next_required_task": self.next_required_task,
            "is_review_chain_suffix": self.is_review_chain_suffix,
            "postfill_audit_contract_version": (
                self.postfill_audit_contract_version
            ),
            "audit_status": self.audit_status,
            "audit_passed": self.audit_passed,
            "audit_reason": self.audit_reason,
            "auditable": self.auditable,
            "integrity_all_passed": self.integrity_all_passed,
            "integrity_failed_checks": list(self.integrity_failed_checks),
            "summary": self.summary,
            "source_task_id": self.source_task_id,
            "source_status": self.source_status,
            "source_mode": self.source_mode,
            "source_generated_at_utc": self.source_generated_at_utc,
            "order_transport_kind": self.order_transport_kind,
            "fake_sender_used": self.fake_sender_used,
            "sender_call_count": self.sender_call_count,
            "simulated_order_network_attempted": (
                self.simulated_order_network_attempted
            ),
            "simulated_order_endpoint_called": (
                self.simulated_order_endpoint_called
            ),
            "simulated_order_sent": self.simulated_order_sent,
            "real_order_network_attempted": self.real_order_network_attempted,
            "real_order_endpoint_called": self.real_order_endpoint_called,
            "real_order_sent": self.real_order_sent,
            "real_execute_disabled_stage1": self.real_execute_disabled_stage1,
            "body_preview": dict(self.body_preview),
            "original_packet_qty": self.original_packet_qty,
            "actual_request_body_qty": self.actual_request_body_qty,
            "actual_request_body_qty_source": (
                self.actual_request_body_qty_source
            ),
            "resolved_execution_qty": self.resolved_execution_qty,
            "resolved_execution_qty_source": self.resolved_execution_qty_source,
            "candidate_qty": self.candidate_qty,
            "candidate_notional": self.candidate_notional,
            "resolved_notional": self.resolved_notional,
            "body_qty_authorized_override": self.body_qty_authorized_override,
            "cap_gate_authorized": self.cap_gate_authorized,
            "cap_gate_status": self.cap_gate_status,
            "wiring_status": self.wiring_status,
            "order_sent": self.order_sent,
            "bybit_ret_code": self.bybit_ret_code,
            "bybit_ret_msg": self.bybit_ret_msg,
            "bybit_order_id": self.bybit_order_id,
            "bm_final_status": self.bm_final_status,
            "expected_contract": dict(self.expected_contract),
            "protected_symbols_untouched": self.protected_symbols_untouched,
            "checks": [c.to_dict() for c in self.checks],
            "generated_at_utc": self.generated_at_utc,
            "audited_at_utc": self.audited_at_utc,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_body_preview(
    orchestration_report: orch.OrchestrationReport,
) -> dict[str, Any]:
    """Pull the BM plan's body preview from the nested bm_report dict.

    Returns an empty dict when the orchestration never reached BM
    planning (e.g., rejected upstream of plan construction).
    """

    bm_report = orchestration_report.bm_report
    if not isinstance(bm_report, Mapping):
        return {}
    plan = bm_report.get("plan")
    if not isinstance(plan, Mapping):
        return {}
    body_preview = plan.get("body_preview")
    if isinstance(body_preview, Mapping):
        return dict(body_preview)
    return {}


def _try_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _check(
    name: str,
    *,
    passed: bool,
    expected: Any,
    actual: Any,
    reason: str = "",
) -> PostfillAuditCheck:
    return PostfillAuditCheck(
        name=name,
        passed=bool(passed),
        expected="" if expected is None else str(expected),
        actual="" if actual is None else str(actual),
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Audit-status determination
# ---------------------------------------------------------------------------


# Source bm_report final status that means BM caught a sender exception
# and converted it to the safe network-error sentinel. Hard-coded here
# to avoid importing the BM module (the audit must stay structurally
# decoupled from the live order executor).
_BM_FINAL_STATUS_NETWORK_ERROR = "STATUS_NETWORK_ERROR_DEMO_ONLY"


def _determine_audit_status(
    report: orch.OrchestrationReport,
) -> str:
    # Highest priority: any real-transport evidence is a hard safety
    # violation and trumps every other classification.
    if (
        report.real_order_network_attempted
        or report.real_order_endpoint_called
        or report.real_order_sent
        or report.order_transport_kind
        == orch.ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER
    ):
        return AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT

    # Not auditable: no fake-sender execution path reached BM.
    if report.mode != orch.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER:
        return AUDIT_STATUS_NOT_AUDITABLE
    if not report.bm_invoked:
        return AUDIT_STATUS_NOT_AUDITABLE
    if not report.fake_sender_used:
        return AUDIT_STATUS_NOT_AUDITABLE
    if report.order_transport_kind != orch.ORDER_TRANSPORT_KIND_FAKE_SENDER:
        return AUDIT_STATUS_NOT_AUDITABLE

    # Sender raised → BM converted to safe network-error sentinel.
    if report.bm_final_status == _BM_FINAL_STATUS_NETWORK_ERROR:
        return AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR

    # Auditable simulated outcome. Distinguish accepted (Bybit replied
    # retCode==0 with a non-empty order id) from rejected (everything
    # else -- non-zero retCode, missing id, etc.).
    if (
        report.simulated_order_sent
        and report.bybit_ret_code == 0
        and bool(report.bybit_order_id)
    ):
        return AUDIT_STATUS_SIMULATED_ACCEPTED
    return AUDIT_STATUS_SIMULATED_REJECTED


# ---------------------------------------------------------------------------
# Check construction (deterministic order)
# ---------------------------------------------------------------------------


def _build_checks(
    report: orch.OrchestrationReport,
    contract: ExpectedContract,
    body_preview: Mapping[str, Any],
) -> tuple[PostfillAuditCheck, ...]:
    accepted_outcome_actual = (
        report.bybit_ret_code == 0 and bool(report.bybit_order_id)
    )
    candidate_notional = _try_decimal(report.candidate_notional)
    resolved_notional = _try_decimal(report.resolved_notional)

    body_symbol = str(body_preview.get("symbol", ""))
    body_category = str(body_preview.get("category", ""))
    body_side = str(body_preview.get("side", ""))
    body_order_type = str(body_preview.get("orderType", ""))
    body_tif = str(body_preview.get("timeInForce", ""))
    body_reduce_only = body_preview.get("reduceOnly", None)
    body_close_on_trigger = body_preview.get("closeOnTrigger", None)

    return (
        _check(
            "transport_is_fake_sender",
            passed=report.order_transport_kind
            == orch.ORDER_TRANSPORT_KIND_FAKE_SENDER,
            expected=orch.ORDER_TRANSPORT_KIND_FAKE_SENDER,
            actual=report.order_transport_kind,
        ),
        _check(
            "fake_sender_used",
            passed=bool(report.fake_sender_used),
            expected=True,
            actual=report.fake_sender_used,
        ),
        _check(
            "sender_call_count_exactly_one",
            passed=report.sender_call_count == 1,
            expected=1,
            actual=report.sender_call_count,
        ),
        _check(
            "simulated_network_attempted",
            passed=bool(report.simulated_order_network_attempted),
            expected=True,
            actual=report.simulated_order_network_attempted,
        ),
        _check(
            "simulated_endpoint_called",
            passed=bool(report.simulated_order_endpoint_called),
            expected=True,
            actual=report.simulated_order_endpoint_called,
        ),
        _check(
            "real_network_not_attempted",
            passed=not report.real_order_network_attempted,
            expected=False,
            actual=report.real_order_network_attempted,
        ),
        _check(
            "real_endpoint_not_called",
            passed=not report.real_order_endpoint_called,
            expected=False,
            actual=report.real_order_endpoint_called,
        ),
        _check(
            "real_order_not_sent",
            passed=not report.real_order_sent,
            expected=False,
            actual=report.real_order_sent,
        ),
        _check(
            "stage1_real_execute_disabled",
            passed=bool(report.real_execute_disabled_stage1),
            expected=True,
            actual=report.real_execute_disabled_stage1,
        ),
        _check(
            "symbol_is_solusdt",
            passed=body_symbol == contract.symbol,
            expected=contract.symbol,
            actual=body_symbol,
        ),
        _check(
            "category_is_linear",
            passed=body_category == contract.category,
            expected=contract.category,
            actual=body_category,
        ),
        _check(
            "side_is_buy",
            passed=body_side == contract.side,
            expected=contract.side,
            actual=body_side,
        ),
        _check(
            "order_type_is_market",
            passed=body_order_type == contract.order_type,
            expected=contract.order_type,
            actual=body_order_type,
        ),
        _check(
            "time_in_force_is_ioc",
            passed=body_tif == contract.time_in_force,
            expected=contract.time_in_force,
            actual=body_tif,
        ),
        _check(
            "reduce_only_false",
            passed=body_reduce_only is False,
            expected=False,
            actual=body_reduce_only,
        ),
        _check(
            "close_on_trigger_false",
            passed=body_close_on_trigger is False,
            expected=False,
            actual=body_close_on_trigger,
        ),
        _check(
            "original_packet_qty_is_0_01",
            passed=report.original_packet_qty == contract.original_packet_qty,
            expected=contract.original_packet_qty,
            actual=report.original_packet_qty,
        ),
        _check(
            "actual_qty_is_authorized_0_1",
            passed=report.actual_request_body_qty == contract.authorized_qty,
            expected=contract.authorized_qty,
            actual=report.actual_request_body_qty,
        ),
        _check(
            "actual_qty_source_is_authorized_candidate",
            passed=report.actual_request_body_qty_source
            == contract.authorized_qty_source,
            expected=contract.authorized_qty_source,
            actual=report.actual_request_body_qty_source,
        ),
        _check(
            "resolved_qty_is_authorized_0_1",
            passed=report.resolved_execution_qty == contract.authorized_qty,
            expected=contract.authorized_qty,
            actual=report.resolved_execution_qty,
        ),
        _check(
            "resolved_qty_source_is_authorized_candidate",
            passed=report.resolved_execution_qty_source
            == contract.authorized_qty_source,
            expected=contract.authorized_qty_source,
            actual=report.resolved_execution_qty_source,
        ),
        _check(
            "candidate_qty_is_0_1",
            passed=report.candidate_qty == contract.authorized_qty,
            expected=contract.authorized_qty,
            actual=report.candidate_qty,
        ),
        _check(
            "body_qty_authorized_override_true",
            passed=bool(report.body_qty_authorized_override),
            expected=True,
            actual=report.body_qty_authorized_override,
        ),
        _check(
            "candidate_notional_within_20_usdt",
            passed=(
                candidate_notional is not None
                and candidate_notional <= contract.max_notional_usdt
            ),
            expected=f"<= {format(contract.max_notional_usdt, 'f')}",
            actual=report.candidate_notional,
            reason="" if candidate_notional is not None else "unparseable",
        ),
        _check(
            "resolved_notional_within_20_usdt",
            passed=(
                resolved_notional is not None
                and resolved_notional <= contract.max_notional_usdt
            ),
            expected=f"<= {format(contract.max_notional_usdt, 'f')}",
            actual=report.resolved_notional,
            reason="" if resolved_notional is not None else "unparseable",
        ),
        _check(
            "cap_gate_authorized",
            passed=bool(report.cap_gate_authorized),
            expected=True,
            actual=report.cap_gate_authorized,
        ),
        _check(
            "wiring_authorized",
            passed=report.wiring_status == contract.wiring_status_authorized,
            expected=contract.wiring_status_authorized,
            actual=report.wiring_status,
        ),
        _check(
            "no_real_transport_evidence",
            passed=(
                not report.real_order_network_attempted
                and not report.real_order_endpoint_called
                and not report.real_order_sent
                and report.order_transport_kind
                != orch.ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER
            ),
            expected="no real_order_* and transport != REAL_DEMO_SENDER",
            actual=(
                f"real_attempted={report.real_order_network_attempted} "
                f"real_endpoint={report.real_order_endpoint_called} "
                f"real_sent={report.real_order_sent} "
                f"transport={report.order_transport_kind}"
            ),
        ),
        _check(
            "accepted_outcome_consistent",
            passed=bool(report.order_sent) == bool(accepted_outcome_actual),
            expected=(
                f"order_sent={accepted_outcome_actual} "
                f"(retCode==0 AND non-empty orderId)"
            ),
            actual=(
                f"order_sent={report.order_sent} "
                f"retCode={report.bybit_ret_code} "
                f"orderId={report.bybit_order_id!r}"
            ),
        ),
        _check(
            "no_protected_symbol_scope",
            passed=bool(report.protected_symbols_untouched),
            expected=True,
            actual=report.protected_symbols_untouched,
        ),
    )


def _summary_for_status(audit_status: str, integrity_all_passed: bool) -> str:
    if audit_status == AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT:
        return (
            "Real-transport evidence detected; Stage 1 safety boundary "
            "violated."
        )
    if audit_status == AUDIT_STATUS_NOT_AUDITABLE:
        return (
            "Orchestration did not produce a fake-sender execution path; "
            "postfill audit not applicable."
        )
    if audit_status == AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR:
        suffix = (
            "all 30 checks passed."
            if integrity_all_passed
            else "one or more integrity checks failed."
        )
        return (
            "Fake sender raised; orchestrator converted to safe "
            f"network-error sentinel; {suffix}"
        )
    if audit_status == AUDIT_STATUS_SIMULATED_REJECTED:
        suffix = (
            "all 30 checks passed."
            if integrity_all_passed
            else "one or more integrity checks failed."
        )
        return (
            "Fake sender returned a non-accepted Bybit response "
            f"(retCode != 0 or missing orderId); {suffix}"
        )
    # SIMULATED_ACCEPTED
    suffix = (
        "all 30 checks passed."
        if integrity_all_passed
        else "one or more integrity checks failed."
    )
    return (
        "Fake sender returned an accepted Bybit response "
        f"(retCode == 0, non-empty orderId); {suffix}"
    )


# ---------------------------------------------------------------------------
# Authoritative audit-integrity result (audit_passed / audit_reason)
# ---------------------------------------------------------------------------


def compute_audit_passed(
    *,
    auditable: bool,
    integrity_all_passed: bool,
    audit_status: str,
) -> bool:
    """Authoritative Stage 1 postfill audit-integrity result.

    ``audit_passed`` means the supplied offline / fake-only evidence is
    internally consistent and satisfies the authorized Stage 1 postfill
    audit contract. It does NOT mean a real order succeeded, that a real
    order was sent, that Bybit Demo accepted a real order, or that Stage 2
    is authorized.

    Fail-closed deterministic formula: an audit only passes when the run
    is auditable, every named integrity check passed, and the terminal
    status is one of the three simulated (fake-only) outcomes.
    """

    return bool(
        auditable
        and integrity_all_passed
        and audit_status
        in {
            AUDIT_STATUS_SIMULATED_ACCEPTED,
            AUDIT_STATUS_SIMULATED_REJECTED,
            AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR,
        }
    )


def _not_auditable_reason(report: orch.OrchestrationReport) -> str:
    """Name the primary missing/invalid evidence for a NOT_AUDITABLE run.

    Mirrors the precedence in :func:`_determine_audit_status` so the reason
    points at the first failing precondition.
    """

    if report.mode != orch.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER:
        return (
            f"orchestration mode {report.mode!r} is not the fake-sender "
            "execute mode"
        )
    if not report.bm_invoked:
        return "BM execution layer was not invoked"
    if not report.fake_sender_used:
        return "no injected fake sender was used"
    if report.order_transport_kind != orch.ORDER_TRANSPORT_KIND_FAKE_SENDER:
        return (
            f"order_transport_kind {report.order_transport_kind!r} is not "
            "FAKE_SENDER"
        )
    return "insufficient fake-sender evidence to audit"


def _build_audit_reason(
    report: orch.OrchestrationReport,
    *,
    audit_status: str,
    audit_passed: bool,
    integrity_failed_checks: tuple[str, ...],
) -> str:
    """Deterministic, sanitized, non-empty audit-integrity explanation.

    Never includes API keys, secrets, signatures, authorization marker
    contents, or authentication headers. Each auditable-pass reason
    explicitly distinguishes audit integrity, business outcome, and real
    order activity.
    """

    if audit_status == AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT:
        return (
            "Audit FORBIDDEN: real transport evidence is forbidden in "
            "Stage 1 (a real_order_* field or a REAL_DEMO_SENDER transport "
            "was present). audit_passed=False; no real order may be "
            "dispatched at this stage."
        )
    if audit_status == AUDIT_STATUS_NOT_AUDITABLE:
        return (
            "Audit NOT auditable: "
            + _not_auditable_reason(report)
            + ". audit_passed=False; no fake-sender evidence to validate "
            "and no real order occurred."
        )
    if not audit_passed:
        failed = ", ".join(integrity_failed_checks) or "(unspecified)"
        return (
            f"Audit integrity FAIL for {audit_status}: required checks "
            f"failed: {failed}. This is an audit-integrity failure only; "
            "it is not a statement about real order activity (no real order "
            "occurred and real_order_sent=False)."
        )
    if audit_status == AUDIT_STATUS_SIMULATED_ACCEPTED:
        return (
            "Audit integrity PASS: the offline fake-only evidence is "
            "internally consistent with the authorized Stage 1 postfill "
            "contract. Business outcome: simulated ACCEPTED (the fake "
            "transport returned a Bybit-shaped accepted reply). Real order "
            "activity: none (real_order_sent=False). This audit pass does "
            "NOT mean a real order succeeded, that a real order was sent, "
            "or that Stage 2 is authorized."
        )
    if audit_status == AUDIT_STATUS_SIMULATED_REJECTED:
        return (
            "Audit integrity PASS: the offline fake-only evidence is "
            "internally consistent with the authorized Stage 1 postfill "
            "contract. Business outcome: simulated REJECTED (the fake "
            "transport completed but the Bybit-shaped reply was not an "
            "accepted order). Real order activity: none "
            "(real_order_sent=False). Audit integrity passed; the order "
            "itself was not accepted."
        )
    # AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR
    return (
        "Audit integrity PASS: the offline fake-only evidence is "
        "internally consistent with the authorized Stage 1 postfill "
        "contract. Business outcome: simulated TRANSPORT ERROR (the fake "
        "transport attempt produced internally consistent network-error "
        "evidence; no order was accepted). Real order activity: none "
        "(real_order_sent=False). Audit integrity passed; this is not "
        "transport or order success."
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_postfill_audit(
    orchestration_report: orch.OrchestrationReport,
    *,
    expected_contract: ExpectedContract | None = None,
) -> PostfillAuditReport:
    """Audit a completed Stage 1 fake-sender orchestration report.

    No network, no order send, no credential read. The function is
    pure: same input → same output (modulo ``generated_at_utc``).
    """

    if not isinstance(orchestration_report, orch.OrchestrationReport):
        raise PostfillAuditError(
            "orchestration_report must be an OrchestrationReport instance"
        )

    contract = expected_contract or DEFAULT_EXPECTED_CONTRACT
    body_preview = _extract_body_preview(orchestration_report)
    audit_status = _determine_audit_status(orchestration_report)
    checks = _build_checks(orchestration_report, contract, body_preview)
    integrity_failed_checks = tuple(c.name for c in checks if not c.passed)
    integrity_all_passed = not integrity_failed_checks
    auditable = audit_status in AUDIT_STATUSES_AUDITABLE
    audit_passed = compute_audit_passed(
        auditable=auditable,
        integrity_all_passed=integrity_all_passed,
        audit_status=audit_status,
    )
    audit_reason = _build_audit_reason(
        orchestration_report,
        audit_status=audit_status,
        audit_passed=audit_passed,
        integrity_failed_checks=integrity_failed_checks,
    )
    summary = _summary_for_status(audit_status, integrity_all_passed)
    audited_at_utc = _utc_timestamp()

    return PostfillAuditReport(
        task_id=TASK_ID,
        identity=IDENTITY,
        phase=IMPLEMENTATION_PATH_PHASE,
        upstream_tasks=UPSTREAM_TASKS,
        next_required_task=NEXT_REQUIRED_TASK,
        is_review_chain_suffix=IS_REVIEW_CHAIN_SUFFIX,
        postfill_audit_contract_version=POSTFILL_AUDIT_CONTRACT_VERSION,
        audit_status=audit_status,
        audit_passed=audit_passed,
        audit_reason=audit_reason,
        auditable=auditable,
        integrity_all_passed=integrity_all_passed,
        integrity_failed_checks=integrity_failed_checks,
        summary=summary,
        source_task_id=orchestration_report.task_id,
        source_status=orchestration_report.status,
        source_mode=orchestration_report.mode,
        source_generated_at_utc=orchestration_report.generated_at_utc,
        order_transport_kind=orchestration_report.order_transport_kind,
        fake_sender_used=orchestration_report.fake_sender_used,
        sender_call_count=orchestration_report.sender_call_count,
        simulated_order_network_attempted=(
            orchestration_report.simulated_order_network_attempted
        ),
        simulated_order_endpoint_called=(
            orchestration_report.simulated_order_endpoint_called
        ),
        simulated_order_sent=orchestration_report.simulated_order_sent,
        real_order_network_attempted=(
            orchestration_report.real_order_network_attempted
        ),
        real_order_endpoint_called=(
            orchestration_report.real_order_endpoint_called
        ),
        real_order_sent=orchestration_report.real_order_sent,
        real_execute_disabled_stage1=(
            orchestration_report.real_execute_disabled_stage1
        ),
        body_preview=body_preview,
        original_packet_qty=orchestration_report.original_packet_qty,
        actual_request_body_qty=orchestration_report.actual_request_body_qty,
        actual_request_body_qty_source=(
            orchestration_report.actual_request_body_qty_source
        ),
        resolved_execution_qty=orchestration_report.resolved_execution_qty,
        resolved_execution_qty_source=(
            orchestration_report.resolved_execution_qty_source
        ),
        candidate_qty=orchestration_report.candidate_qty,
        candidate_notional=orchestration_report.candidate_notional,
        resolved_notional=orchestration_report.resolved_notional,
        body_qty_authorized_override=(
            orchestration_report.body_qty_authorized_override
        ),
        cap_gate_authorized=orchestration_report.cap_gate_authorized,
        cap_gate_status=orchestration_report.cap_gate_status,
        wiring_status=orchestration_report.wiring_status,
        order_sent=orchestration_report.order_sent,
        bybit_ret_code=orchestration_report.bybit_ret_code,
        bybit_ret_msg=orchestration_report.bybit_ret_msg,
        bybit_order_id=orchestration_report.bybit_order_id,
        bm_final_status=orchestration_report.bm_final_status,
        expected_contract=contract.to_dict(),
        protected_symbols_untouched=(
            orchestration_report.protected_symbols_untouched
        ),
        checks=checks,
        generated_at_utc=audited_at_utc,
        audited_at_utc=audited_at_utc,
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_markdown(report: PostfillAuditReport) -> str:
    lines: list[str] = []
    lines.append(f"# {REPORT_NAME}")
    lines.append("")
    lines.append(f"- task_id: `{report.task_id}`")
    lines.append(f"- identity: `{report.identity}`")
    lines.append(f"- phase: `{report.phase}`")
    lines.append(f"- next_required_task: `{report.next_required_task}`")
    lines.append(
        f"- postfill_audit_contract_version: "
        f"`{report.postfill_audit_contract_version}`"
    )
    lines.append(f"- generated_at_utc: `{report.generated_at_utc}`")
    lines.append(f"- audited_at_utc: `{report.audited_at_utc}`")
    lines.append("")
    lines.append("## Overall")
    lines.append(f"- audit_status: `{report.audit_status}`")
    lines.append(f"- audit_passed: {report.audit_passed}")
    lines.append(f"- audit_reason: {report.audit_reason}")
    lines.append(f"- auditable: {report.auditable}")
    lines.append(f"- integrity_all_passed: {report.integrity_all_passed}")
    if report.integrity_failed_checks:
        lines.append(
            "- integrity_failed_checks: "
            + ", ".join(f"`{n}`" for n in report.integrity_failed_checks)
        )
    else:
        lines.append("- integrity_failed_checks: (none)")
    lines.append(f"- summary: {report.summary}")
    lines.append(
        "- note: `audit_passed` is the authoritative audit-integrity result "
        "(offline/fake-only evidence is internally consistent). It is NOT a "
        "business outcome and NOT real order activity. A real order still "
        "requires `real_order_sent=True`; Stage 1 guarantees "
        "`real_order_sent=False`."
    )
    lines.append("")
    lines.append("## Source orchestration")
    lines.append(f"- source_task_id: `{report.source_task_id}`")
    lines.append(f"- source_mode: `{report.source_mode}`")
    lines.append(f"- source_status: `{report.source_status}`")
    lines.append(
        f"- source_generated_at_utc: `{report.source_generated_at_utc}`"
    )
    lines.append("")
    lines.append("## Transport evidence")
    lines.append(f"- order_transport_kind: `{report.order_transport_kind}`")
    lines.append(f"- fake_sender_used: {report.fake_sender_used}")
    lines.append(f"- sender_call_count: {report.sender_call_count}")
    lines.append(
        f"- simulated: network_attempted="
        f"{report.simulated_order_network_attempted} "
        f"endpoint_called={report.simulated_order_endpoint_called} "
        f"order_sent={report.simulated_order_sent}"
    )
    lines.append(
        f"- real: network_attempted={report.real_order_network_attempted} "
        f"endpoint_called={report.real_order_endpoint_called} "
        f"order_sent={report.real_order_sent}"
    )
    lines.append(
        f"- real_execute_disabled_stage1: "
        f"{report.real_execute_disabled_stage1}"
    )
    lines.append("")
    lines.append("## Contract / qty")
    lines.append(f"- original_packet_qty: `{report.original_packet_qty}`")
    lines.append(
        f"- actual_request_body_qty: `{report.actual_request_body_qty}` "
        f"(source=`{report.actual_request_body_qty_source}`)"
    )
    lines.append(
        f"- resolved_execution_qty: `{report.resolved_execution_qty}` "
        f"(source=`{report.resolved_execution_qty_source}`)"
    )
    lines.append(
        f"- candidate_qty: `{report.candidate_qty}` "
        f"candidate_notional=`{report.candidate_notional}` "
        f"resolved_notional=`{report.resolved_notional}`"
    )
    lines.append(
        f"- body_qty_authorized_override: "
        f"{report.body_qty_authorized_override}"
    )
    lines.append(
        f"- cap_gate_authorized: {report.cap_gate_authorized} "
        f"cap_gate_status=`{report.cap_gate_status}`"
    )
    lines.append(f"- wiring_status: `{report.wiring_status}`")
    lines.append("")
    lines.append("## Business outcome")
    lines.append(
        f"- order_sent={report.order_sent} "
        f"bybit_ret_code={report.bybit_ret_code} "
        f"bybit_order_id=`{report.bybit_order_id}` "
        f"bm_final_status=`{report.bm_final_status}`"
    )
    lines.append("")
    lines.append("## Body preview")
    if report.body_preview:
        for key in sorted(report.body_preview):
            lines.append(f"- `{key}` = `{report.body_preview[key]!r}`")
    else:
        lines.append("- (empty — orchestration did not reach BM plan)")
    lines.append("")
    lines.append("## Expected contract")
    for key in sorted(report.expected_contract):
        lines.append(f"- `{key}` = `{report.expected_contract[key]!r}`")
    lines.append("")
    lines.append("## Checks (deterministic order)")
    for check in report.checks:
        marker = "PASS" if check.passed else "FAIL"
        lines.append(
            f"- [{marker}] `{check.name}` "
            f"expected=`{check.expected}` actual=`{check.actual}`"
            + (f" — {check.reason}" if check.reason else "")
        )
    return "\n".join(lines) + "\n"


def write_report(
    report: PostfillAuditReport,
    *,
    output_dir: pathlib.Path | str | None = None,
) -> dict[str, pathlib.Path]:
    """Write the audit report to JSON + Markdown (timestamped + ``latest_*``).

    No directories are created unless this function is called.
    """

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
    payload = json.dumps(
        report.to_dict(), indent=2, sort_keys=True, default=str
    )
    md = _render_markdown(report)
    paths["json_latest"].write_text(payload, encoding="utf-8")
    paths["md_latest"].write_text(md, encoding="utf-8")
    paths["json_ts"].write_text(payload, encoding="utf-8")
    paths["md_ts"].write_text(md, encoding="utf-8")
    return paths


__all__ = [
    "AUDIT_STATUSES",
    "AUDIT_STATUSES_AUDITABLE",
    "AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT",
    "AUDIT_STATUS_NOT_AUDITABLE",
    "AUDIT_STATUS_SIMULATED_ACCEPTED",
    "AUDIT_STATUS_SIMULATED_REJECTED",
    "AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR",
    "CHECK_NAMES",
    "DEFAULT_EXPECTED_CONTRACT",
    "DEFAULT_OUTPUT_DIR",
    "EXPECTED_AUTHORIZED_QTY",
    "EXPECTED_AUTHORIZED_QTY_SOURCE",
    "EXPECTED_CATEGORY",
    "EXPECTED_CLOSE_ON_TRIGGER",
    "EXPECTED_MAX_NOTIONAL_USDT",
    "EXPECTED_ORDER_TYPE",
    "EXPECTED_ORIGINAL_PACKET_QTY",
    "EXPECTED_REDUCE_ONLY",
    "EXPECTED_SIDE",
    "EXPECTED_SYMBOL",
    "EXPECTED_TIME_IN_FORCE",
    "EXPECTED_WIRING_STATUS_AUTHORIZED",
    "ExpectedContract",
    "IDENTITY",
    "IMPLEMENTATION_PATH_PHASE",
    "IS_REVIEW_CHAIN_SUFFIX",
    "NEXT_REQUIRED_TASK",
    "POSTFILL_AUDIT_CONTRACT_VERSION",
    "PostfillAuditCheck",
    "PostfillAuditError",
    "PostfillAuditReport",
    "REPORT_NAME",
    "TASK_ID",
    "UPSTREAM_TASKS",
    "compute_audit_passed",
    "run_postfill_audit",
    "write_report",
]
