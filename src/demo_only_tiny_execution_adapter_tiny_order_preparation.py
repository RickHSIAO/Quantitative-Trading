"""TASK-014BL -- demo-only tiny execution adapter tiny order preparation.

Builds the explicit *offline* authorization packet that a future
TASK-014BM_explicit_demo_only_tiny_order_execution task would consume
to send the first Bybit Demo tiny order. This module does NOT execute,
NOT send, NOT open any connection, NOT read any secret. It only
aggregates the BH (scaffold) + BI (offline payload dry-run) + BJ
(endpoint guard integration) + BK (final pre-execution checklist)
safety chain into a single offline packet that explicitly marks itself
as ``NOT_SENT_PREPARED_ONLY_NOT_EXECUTED`` and explicitly states it is
*not* an execution authorization.

Implementation-path successor -- NOT a review-chain suffix:

    BH (scaffold) -> BI (offline payload dry-run) -> BJ (endpoint guard
    integration) -> BK (final pre-execution checklist) -> BL (tiny
    order preparation) -> next:
    TASK-014BM_explicit_demo_only_tiny_order_execution (or equivalent
    explicit demo-only tiny order execution authorization task) --
    NEVER another review-chain suffix.

Hard safety invariants (cross-checked by tests):
    * No network library import (no ``requests`` / ``urllib`` /
      ``http`` / ``socket`` / ``ssl`` / ``pybit`` / ``websocket`` /
      ``aiohttp`` / ``httpx``).
    * No environment-variable / secret read.
    * No reference to ``BybitExecutor`` / live executor wiring.
    * No call to any exchange endpoint.
    * Does not import ``main`` or ``src.risk``.
    * Re-uses BH/BI/BJ/BK directly -- no parallel implementation, no
      relaxed guard, no weakened denylist.
    * The produced packet is explicitly NOT an execution authorization.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping

from src import demo_only_tiny_execution_adapter as bh
from src import demo_only_tiny_execution_adapter_endpoint_guard_integration as bj
from src import (
    demo_only_tiny_execution_adapter_final_pre_execution_checklist as bk,
)
from src import demo_only_tiny_execution_adapter_payload_dry_run as bi

# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------

TASK_ID = "TASK-014BL"
IDENTITY = "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-PREPARATION"
IMPLEMENTATION_PATH_PHASE = "tiny_order_preparation"
IS_REVIEW_CHAIN_SUFFIX = False
UPSTREAM_TASKS: tuple[str, ...] = (
    "TASK-014BH",
    "TASK-014BI",
    "TASK-014BJ",
    "TASK-014BK",
)
NEXT_REQUIRED_TASK = "TASK-014BM_explicit_demo_only_tiny_order_execution"
TARGET_FUTURE_TASK = "TASK-014BM_explicit_demo_only_tiny_order_execution"

REPORT_NAME = "demo_only_tiny_execution_adapter_tiny_order_preparation"
DEFAULT_OUTPUT_DIR = (
    pathlib.Path("outputs/demo_trading") / REPORT_NAME
)

PREPARATION_CONTRACT_VERSION = (
    "demo_only_tiny_execution_adapter_tiny_order_preparation_v1"
)

BL_AUDIT_RESPONSE_STATUS_NOT_SENT = "NOT_SENT_PREPARED_ONLY_NOT_EXECUTED"

# Canonical default request: minimal SOLUSDT Buy 0.01 @ mark 100 -> notional 1
DEFAULT_SYMBOL = "SOLUSDT"
DEFAULT_SIDE = "Buy"
DEFAULT_QTY = "0.01"
DEFAULT_MARK_PRICE = "100"
DEFAULT_ORDER_TYPE = "Market"
DEFAULT_TIME_IN_FORCE = "IOC"
DEFAULT_REDUCE_ONLY = False
DEFAULT_DEMO_ENDPOINT = "https://api-demo.bybit.com/v5/order/create"

PACKET_IS_NOT_EXECUTION_AUTHORIZATION_NOTE = (
    "This packet is PREPARATION ONLY. It does NOT authorize execution, "
    "does NOT send any order, does NOT open any connection, does NOT "
    "read any secret. Execution requires the explicit successor task "
    f"{TARGET_FUTURE_TASK!r} and an independent manual authorization."
)


# Re-assert at import time that BL itself is not a review-chain suffix.
bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TinyOrderPreparationError(bh.DemoOnlyTinyExecutionAdapterError):
    """Raised when the BL preparation pipeline cannot produce a packet.

    Inherits from BH's base exception so existing BH-aware callers
    continue to recognise it as a rejection.
    """


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreparationPacket:
    """Offline authorization packet for a future demo-only tiny order.

    Holding this object does NOT cause anything to be sent. The packet
    is intended to be inspected, logged, and handed to a separately-
    authorized future ``TASK-014BM`` execution task. The
    ``packet_is_not_execution_authorization`` flag is unconditionally
    ``True`` to make the non-authorization status machine-checkable.
    """

    task_id: str
    upstream_tasks: tuple[str, ...]
    target_future_task: str
    environment: str
    symbol: str
    side: str
    qty: str
    mark_price: str | None
    notional_estimate: str | None
    order_type: str
    reduce_only: bool
    time_in_force: str
    order_link_id: str
    order_link_id_prefix: str
    audit_response_status: str
    packet_is_not_execution_authorization: bool
    payload_audit: Mapping[str, Any]
    preparation_contract_version: str
    generated_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "upstream_tasks": list(self.upstream_tasks),
            "target_future_task": self.target_future_task,
            "environment": self.environment,
            "symbol": self.symbol,
            "side": self.side,
            "qty": self.qty,
            "mark_price": self.mark_price,
            "notional_estimate": self.notional_estimate,
            "order_type": self.order_type,
            "reduce_only": self.reduce_only,
            "time_in_force": self.time_in_force,
            "order_link_id": self.order_link_id,
            "order_link_id_prefix": self.order_link_id_prefix,
            "audit_response_status": self.audit_response_status,
            "packet_is_not_execution_authorization": (
                self.packet_is_not_execution_authorization
            ),
            "payload_audit": dict(self.payload_audit),
            "preparation_contract_version": self.preparation_contract_version,
            "generated_at_utc": self.generated_at_utc,
        }


@dataclass(frozen=True)
class PreparationReport:
    """Aggregate BL preparation report.

    Embeds the BK checklist summary and BJ integration result alongside
    the offline ``PreparationPacket``. The report is ``all_passed`` only
    if BK's checklist passes AND the BJ integration call produces a
    guard-validated payload.
    """

    task_id: str
    identity: str
    phase: str
    upstream_tasks: tuple[str, ...]
    next_required_task: str
    target_future_task: str
    is_review_chain_suffix: bool
    preparation_contract_version: str
    bh_identity: str
    bi_identity: str
    bj_identity: str
    bk_identity: str
    bk_checklist_total_items: int
    bk_checklist_passed_items: int
    bk_checklist_failed_items: int
    bk_checklist_all_passed: bool
    bj_integration_ok: bool
    bj_integration_rejection_step: str
    bj_integration_rejection_reason: str
    bl_audit_response_status_not_sent: str
    packet_note: str
    all_passed: bool
    generated_at_utc: str
    packet: PreparationPacket | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "identity": self.identity,
            "phase": self.phase,
            "upstream_tasks": list(self.upstream_tasks),
            "next_required_task": self.next_required_task,
            "target_future_task": self.target_future_task,
            "is_review_chain_suffix": self.is_review_chain_suffix,
            "preparation_contract_version": self.preparation_contract_version,
            "bh_identity": self.bh_identity,
            "bi_identity": self.bi_identity,
            "bj_identity": self.bj_identity,
            "bk_identity": self.bk_identity,
            "bk_checklist_total_items": self.bk_checklist_total_items,
            "bk_checklist_passed_items": self.bk_checklist_passed_items,
            "bk_checklist_failed_items": self.bk_checklist_failed_items,
            "bk_checklist_all_passed": self.bk_checklist_all_passed,
            "bj_integration_ok": self.bj_integration_ok,
            "bj_integration_rejection_step": self.bj_integration_rejection_step,
            "bj_integration_rejection_reason": (
                self.bj_integration_rejection_reason
            ),
            "bl_audit_response_status_not_sent": (
                self.bl_audit_response_status_not_sent
            ),
            "packet_note": self.packet_note,
            "all_passed": self.all_passed,
            "generated_at_utc": self.generated_at_utc,
            "packet": self.packet.to_dict() if self.packet is not None else None,
        }


# ---------------------------------------------------------------------------
# Core builders
# ---------------------------------------------------------------------------


def _compute_notional(qty: str, mark_price: str | None) -> str | None:
    if mark_price is None:
        return None
    return format(Decimal(str(qty)) * Decimal(str(mark_price)), "f")


def _wrap_audit_with_bl_markers(
    bj_audit: Mapping[str, Any],
) -> dict[str, Any]:
    """Layer BL-level audit markers on top of the BJ payload audit.

    Does not mutate the BJ audit -- returns a new dict.
    """

    audit = dict(bj_audit)
    audit["_demo_only_bl_audit_response_status"] = (
        BL_AUDIT_RESPONSE_STATUS_NOT_SENT
    )
    audit["_demo_only_bl_target_future_task"] = TARGET_FUTURE_TASK
    audit["_demo_only_bl_authorization_is_not_execution_authorization"] = True
    audit["_demo_only_bl_preparation_contract_version"] = (
        PREPARATION_CONTRACT_VERSION
    )
    audit["_demo_only_bl_implementation_path_task"] = TASK_ID
    audit["_demo_only_bl_is_review_chain_suffix"] = IS_REVIEW_CHAIN_SUFFIX
    audit["_demo_only_bl_packet_note"] = PACKET_IS_NOT_EXECUTION_AUTHORIZATION_NOTE
    return audit


def build_preparation_packet(
    *,
    symbol: str = DEFAULT_SYMBOL,
    side: str = DEFAULT_SIDE,
    qty: str = DEFAULT_QTY,
    mark_price: str | None = DEFAULT_MARK_PRICE,
    environment: str = bh.ALLOWED_ENVIRONMENT,
    existing_positions: tuple[str, ...] = (),
    order_link_id: str | None = None,
    endpoint_target: str | None = DEFAULT_DEMO_ENDPOINT,
) -> PreparationPacket:
    """Build the offline ``PreparationPacket`` via BJ's guarded entry.

    Raises ``TinyOrderPreparationError`` if any guard step rejects the
    request. The packet's ``payload_audit`` is the BJ audit dict
    (already carrying both BH+BJ NOT_SENT markers) plus BL markers.
    """

    request = bj.IntegrationRequest(
        symbol=symbol,
        side=side,
        qty=qty,
        environment=environment,
        mark_price=mark_price,
        existing_positions=existing_positions,
        order_link_id=order_link_id,
        endpoint_target=endpoint_target,
        note="TASK-014BL offline preparation packet build",
    )
    result = bj.integrate_demo_only_tiny_request(request)
    if not result.ok or result.payload_audit is None:
        raise TinyOrderPreparationError(
            f"BJ rejected request at step {result.rejection_step!r}: "
            f"{result.rejection_reason!s}"
        )

    audit = _wrap_audit_with_bl_markers(result.payload_audit)
    order_link_id_value = str(audit.get("orderLinkId") or "")
    notional = _compute_notional(qty, mark_price)

    return PreparationPacket(
        task_id=TASK_ID,
        upstream_tasks=UPSTREAM_TASKS,
        target_future_task=TARGET_FUTURE_TASK,
        environment=environment,
        symbol=symbol,
        side=side,
        qty=qty,
        mark_price=mark_price,
        notional_estimate=notional,
        order_type=DEFAULT_ORDER_TYPE,
        reduce_only=DEFAULT_REDUCE_ONLY,
        time_in_force=DEFAULT_TIME_IN_FORCE,
        order_link_id=order_link_id_value,
        order_link_id_prefix=bh.ORDER_LINK_ID_PREFIX,
        audit_response_status=BL_AUDIT_RESPONSE_STATUS_NOT_SENT,
        packet_is_not_execution_authorization=True,
        payload_audit=audit,
        preparation_contract_version=PREPARATION_CONTRACT_VERSION,
        generated_at_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(),
    )


def run_tiny_order_preparation(
    *,
    symbol: str = DEFAULT_SYMBOL,
    side: str = DEFAULT_SIDE,
    qty: str = DEFAULT_QTY,
    mark_price: str | None = DEFAULT_MARK_PRICE,
    environment: str = bh.ALLOWED_ENVIRONMENT,
    existing_positions: tuple[str, ...] = (),
    order_link_id: str | None = None,
    endpoint_target: str | None = DEFAULT_DEMO_ENDPOINT,
) -> PreparationReport:
    """Aggregate BK checklist + BJ integration into a ``PreparationReport``.

    Steps (all offline):
        1. Run BK ``run_final_pre_execution_checklist()``.
        2. Run BJ ``integrate_demo_only_tiny_request(...)`` for the
           supplied request.
        3. If both succeed, wrap the BJ audit with BL markers and embed
           the resulting ``PreparationPacket`` in the report.

    The report's ``all_passed`` is True only when both BK and BJ pass.
    """

    # Re-assert at call time as defence-in-depth.
    bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)

    checklist = bk.run_final_pre_execution_checklist()

    request = bj.IntegrationRequest(
        symbol=symbol,
        side=side,
        qty=qty,
        environment=environment,
        mark_price=mark_price,
        existing_positions=existing_positions,
        order_link_id=order_link_id,
        endpoint_target=endpoint_target,
        note="TASK-014BL offline preparation packet build",
    )
    bj_result = bj.integrate_demo_only_tiny_request(request)

    packet: PreparationPacket | None = None
    if checklist.all_passed and bj_result.ok and bj_result.payload_audit is not None:
        audit = _wrap_audit_with_bl_markers(bj_result.payload_audit)
        order_link_id_value = str(audit.get("orderLinkId") or "")
        notional = _compute_notional(qty, mark_price)
        packet = PreparationPacket(
            task_id=TASK_ID,
            upstream_tasks=UPSTREAM_TASKS,
            target_future_task=TARGET_FUTURE_TASK,
            environment=environment,
            symbol=symbol,
            side=side,
            qty=qty,
            mark_price=mark_price,
            notional_estimate=notional,
            order_type=DEFAULT_ORDER_TYPE,
            reduce_only=DEFAULT_REDUCE_ONLY,
            time_in_force=DEFAULT_TIME_IN_FORCE,
            order_link_id=order_link_id_value,
            order_link_id_prefix=bh.ORDER_LINK_ID_PREFIX,
            audit_response_status=BL_AUDIT_RESPONSE_STATUS_NOT_SENT,
            packet_is_not_execution_authorization=True,
            payload_audit=audit,
            preparation_contract_version=PREPARATION_CONTRACT_VERSION,
            generated_at_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        )

    all_passed = checklist.all_passed and bj_result.ok and packet is not None

    return PreparationReport(
        task_id=TASK_ID,
        identity=IDENTITY,
        phase=IMPLEMENTATION_PATH_PHASE,
        upstream_tasks=UPSTREAM_TASKS,
        next_required_task=NEXT_REQUIRED_TASK,
        target_future_task=TARGET_FUTURE_TASK,
        is_review_chain_suffix=IS_REVIEW_CHAIN_SUFFIX,
        preparation_contract_version=PREPARATION_CONTRACT_VERSION,
        bh_identity=bh.IDENTITY,
        bi_identity=bi.IDENTITY,
        bj_identity=bj.IDENTITY,
        bk_identity=bk.IDENTITY,
        bk_checklist_total_items=checklist.total_items,
        bk_checklist_passed_items=checklist.passed_items,
        bk_checklist_failed_items=checklist.failed_items,
        bk_checklist_all_passed=checklist.all_passed,
        bj_integration_ok=bj_result.ok,
        bj_integration_rejection_step=bj_result.rejection_step,
        bj_integration_rejection_reason=bj_result.rejection_reason,
        bl_audit_response_status_not_sent=BL_AUDIT_RESPONSE_STATUS_NOT_SENT,
        packet_note=PACKET_IS_NOT_EXECUTION_AUTHORIZATION_NOTE,
        all_passed=all_passed,
        generated_at_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        packet=packet,
    )


# ---------------------------------------------------------------------------
# Report writer (JSON + Markdown; latest_* + timestamped)
# ---------------------------------------------------------------------------


def _utc_timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _render_markdown(report: PreparationReport) -> str:
    lines: list[str] = []
    lines.append(f"# {report.task_id} -- {report.identity}")
    lines.append("")
    lines.append(f"- generated_at_utc: `{report.generated_at_utc}`")
    lines.append(f"- phase: `{report.phase}`")
    lines.append(
        f"- upstream_tasks: `{', '.join(report.upstream_tasks)}`"
    )
    lines.append(f"- next_required_task: `{report.next_required_task}`")
    lines.append(f"- target_future_task: `{report.target_future_task}`")
    lines.append(f"- is_review_chain_suffix: `{report.is_review_chain_suffix}`")
    lines.append(
        f"- preparation_contract_version: "
        f"`{report.preparation_contract_version}`"
    )
    lines.append(
        f"- bl_audit_response_status_not_sent: "
        f"`{report.bl_audit_response_status_not_sent}`"
    )
    lines.append("")
    lines.append("## Upstream identity")
    lines.append("")
    lines.append(f"- bh_identity: `{report.bh_identity}`")
    lines.append(f"- bi_identity: `{report.bi_identity}`")
    lines.append(f"- bj_identity: `{report.bj_identity}`")
    lines.append(f"- bk_identity: `{report.bk_identity}`")
    lines.append("")
    lines.append("## BK checklist summary")
    lines.append("")
    lines.append(
        f"- bk_checklist_total_items: `{report.bk_checklist_total_items}`"
    )
    lines.append(
        f"- bk_checklist_passed_items: `{report.bk_checklist_passed_items}`"
    )
    lines.append(
        f"- bk_checklist_failed_items: `{report.bk_checklist_failed_items}`"
    )
    lines.append(
        f"- bk_checklist_all_passed: `{report.bk_checklist_all_passed}`"
    )
    lines.append("")
    lines.append("## BJ integration summary")
    lines.append("")
    lines.append(f"- bj_integration_ok: `{report.bj_integration_ok}`")
    lines.append(
        f"- bj_integration_rejection_step: "
        f"`{report.bj_integration_rejection_step}`"
    )
    lines.append(
        f"- bj_integration_rejection_reason: "
        f"`{report.bj_integration_rejection_reason}`"
    )
    lines.append("")
    lines.append("## Packet")
    lines.append("")
    if report.packet is None:
        lines.append("_No packet produced (upstream chain rejected the request)._")
    else:
        pkt = report.packet
        lines.append(f"- task_id: `{pkt.task_id}`")
        lines.append(
            f"- upstream_tasks: `{', '.join(pkt.upstream_tasks)}`"
        )
        lines.append(f"- target_future_task: `{pkt.target_future_task}`")
        lines.append(f"- environment: `{pkt.environment}`")
        lines.append(f"- symbol: `{pkt.symbol}`")
        lines.append(f"- side: `{pkt.side}`")
        lines.append(f"- qty: `{pkt.qty}`")
        lines.append(f"- mark_price: `{pkt.mark_price}`")
        lines.append(f"- notional_estimate: `{pkt.notional_estimate}`")
        lines.append(f"- order_type: `{pkt.order_type}`")
        lines.append(f"- reduce_only: `{pkt.reduce_only}`")
        lines.append(f"- time_in_force: `{pkt.time_in_force}`")
        lines.append(f"- order_link_id: `{pkt.order_link_id}`")
        lines.append(
            f"- order_link_id_prefix: `{pkt.order_link_id_prefix}`"
        )
        lines.append(
            f"- audit_response_status: `{pkt.audit_response_status}`"
        )
        lines.append(
            f"- packet_is_not_execution_authorization: "
            f"`{pkt.packet_is_not_execution_authorization}`"
        )
        lines.append(
            f"- preparation_contract_version: "
            f"`{pkt.preparation_contract_version}`"
        )
        lines.append(f"- generated_at_utc: `{pkt.generated_at_utc}`")
        lines.append("")
        lines.append("### payload_audit (BH+BJ+BL marker layers)")
        lines.append("")
        lines.append("| key | value |")
        lines.append("|---|---|")
        for key in sorted(pkt.payload_audit):
            value = pkt.payload_audit[key]
            value_repr = str(value).replace("|", "\\|")
            key_repr = str(key).replace("|", "\\|")
            lines.append(f"| `{key_repr}` | `{value_repr}` |")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- all_passed: `{report.all_passed}`")
    lines.append("")
    lines.append(f"_{report.packet_note}_")
    lines.append("")
    lines.append(
        "_offline tiny order preparation -- no order sent, no endpoint "
        "called, no secret read; BH/BI/BJ/BK consumed directly._"
    )
    lines.append("")
    return "\n".join(lines)


def write_report(
    report: PreparationReport,
    output_dir: pathlib.Path | str | None = None,
) -> dict[str, pathlib.Path]:
    """Write JSON + Markdown report (latest_* + timestamped) and return paths."""

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
    "BL_AUDIT_RESPONSE_STATUS_NOT_SENT",
    "DEFAULT_DEMO_ENDPOINT",
    "DEFAULT_MARK_PRICE",
    "DEFAULT_ORDER_TYPE",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_QTY",
    "DEFAULT_REDUCE_ONLY",
    "DEFAULT_SIDE",
    "DEFAULT_SYMBOL",
    "DEFAULT_TIME_IN_FORCE",
    "IDENTITY",
    "IMPLEMENTATION_PATH_PHASE",
    "IS_REVIEW_CHAIN_SUFFIX",
    "NEXT_REQUIRED_TASK",
    "PACKET_IS_NOT_EXECUTION_AUTHORIZATION_NOTE",
    "PREPARATION_CONTRACT_VERSION",
    "PreparationPacket",
    "PreparationReport",
    "REPORT_NAME",
    "TARGET_FUTURE_TASK",
    "TASK_ID",
    "TinyOrderPreparationError",
    "UPSTREAM_TASKS",
    "build_preparation_packet",
    "run_tiny_order_preparation",
    "write_report",
]
