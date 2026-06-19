"""TASK-014BM -- demo-only tiny execution adapter explicit tiny order execution.

Single narrow one-shot execution path for *exactly one* Bybit Demo tiny
SOLUSDT order, gated behind:

    * the TASK-014BL ``PreparationPacket`` (``all_passed`` + packet marked
      ``packet_is_not_execution_authorization=True``),
    * two explicit confirmation flags
      (``--execute-demo-order`` + ``--i-understand-this-sends-one-bybit-demo-order``),
    * presence of *demo-scoped* credentials only
      (``BYBIT_DEMO_API_KEY`` / ``BYBIT_DEMO_API_SECRET``),
    * Bybit Demo endpoint allowlist
      (host must equal ``api-demo.bybit.com`` and full URL must be
      ``https://api-demo.bybit.com/v5/order/create``),
    * BJ guard (live endpoint denylist) re-applied.

Default mode is **dry-run / readiness only** -- no network, no order, no
endpoint call, no secret read attempt unless the caller has explicitly
opted into execute mode AND provided both confirmation flags. When demo
credentials are missing, the task does NOT fall back to live credentials
and does NOT raise -- it produces a ``MISSING_DEMO_CREDENTIALS`` report
and keeps every test passing.

Implementation-path successor -- NOT a review-chain suffix:

    BH (scaffold) -> BI (offline payload dry-run) -> BJ (endpoint guard
    integration) -> BK (final pre-execution checklist) -> BL (tiny
    order preparation) -> BM (tiny order execution) -> next:
    TASK-014BN_demo_only_tiny_execution_postfill_audit (or equivalent
    explicit demo-only post-fill audit task) -- NEVER another
    review-chain suffix.

Hard safety invariants (cross-checked by tests):
    * Only ``urllib`` (stdlib) is imported as a network surface; no
      ``requests`` / ``pybit`` / ``aiohttp`` / ``httpx`` / ``websocket``.
    * Only demo-scoped env names are read
      (``BYBIT_DEMO_API_KEY`` / ``BYBIT_DEMO_API_SECRET`` /
      ``BYBIT_DEMO_RECV_WINDOW``). Live names such as ``BYBIT_API_KEY``
      / ``BYBIT_API_SECRET`` are NEVER referenced.
    * No reference to ``BybitExecutor`` / live executor wiring.
    * Does not import ``main`` or ``src.risk``.
    * Single allowed demo endpoint URL; any other endpoint aborts before
      network.
    * Maximum order count is 1; no retry loop; no scheduler.
    * No stop endpoint call; no take-profit / stop-loss attachment.
    * Reduce-only / close-on-trigger are hard-coded False for this tiny
      entry.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import os
import pathlib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Mapping

from src import demo_only_tiny_execution_adapter as bh
from src import demo_only_tiny_execution_adapter_endpoint_guard_integration as bj
from src import (
    demo_only_tiny_execution_adapter_final_pre_execution_checklist as bk,
)
from src import demo_only_tiny_execution_adapter_payload_dry_run as bi
from src import demo_only_tiny_execution_adapter_tiny_order_preparation as bl

# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------

TASK_ID = "TASK-014BM"
IDENTITY = "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-EXECUTION"
IMPLEMENTATION_PATH_PHASE = "tiny_order_execution"
IS_REVIEW_CHAIN_SUFFIX = False
UPSTREAM_TASKS: tuple[str, ...] = (
    "TASK-014BH",
    "TASK-014BI",
    "TASK-014BJ",
    "TASK-014BK",
    "TASK-014BL",
)
NEXT_REQUIRED_TASK = "TASK-014BN_demo_only_tiny_execution_postfill_audit"

REPORT_NAME = "demo_only_tiny_execution_adapter_tiny_order_execution"
DEFAULT_OUTPUT_DIR = pathlib.Path("outputs/demo_trading") / REPORT_NAME

EXECUTION_CONTRACT_VERSION = (
    "demo_only_tiny_execution_adapter_tiny_order_execution_v1"
)

# Re-assert at import time that BM itself is not a review-chain suffix.
bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)

# ---------------------------------------------------------------------------
# Strict immutable execution constants
# ---------------------------------------------------------------------------

ALLOWED_DEMO_ENDPOINT_HOST = "api-demo.bybit.com"
ALLOWED_DEMO_ENDPOINT_URL = "https://api-demo.bybit.com/v5/order/create"
ALLOWED_DEMO_CATEGORY = "linear"

MAX_ORDER_COUNT = 1

EXECUTE_FLAG_NAME = "--execute-demo-order"
CONFIRM_FLAG_NAME = "--i-understand-this-sends-one-bybit-demo-order"

# Only demo-scoped environment variable names are read.
DEMO_API_KEY_ENV = "BYBIT_DEMO_API_KEY"
DEMO_API_SECRET_ENV = "BYBIT_DEMO_API_SECRET"
DEMO_RECV_WINDOW_ENV = "BYBIT_DEMO_RECV_WINDOW"
DEFAULT_RECV_WINDOW = "5000"
DEMO_SCOPED_ENV_NAMES: tuple[str, ...] = (
    DEMO_API_KEY_ENV,
    DEMO_API_SECRET_ENV,
    DEMO_RECV_WINDOW_ENV,
)

# Modes the BM module supports.
MODE_DRY_RUN = "dry_run"
MODE_READINESS = "readiness"
MODE_EXECUTE_DEMO_ORDER = "execute_demo_order"
SUPPORTED_MODES: tuple[str, ...] = (
    MODE_DRY_RUN,
    MODE_READINESS,
    MODE_EXECUTE_DEMO_ORDER,
)

# Final status outcomes.
STATUS_DRY_RUN_OK_NO_NETWORK = "DRY_RUN_OK_NO_NETWORK"
STATUS_READINESS_OK_NO_NETWORK = "READINESS_OK_NO_NETWORK"
STATUS_GATE_REJECTED_NO_NETWORK = "GATE_REJECTED_NO_NETWORK"
STATUS_MISSING_DEMO_CREDENTIALS = "MISSING_DEMO_CREDENTIALS"
STATUS_EXECUTED_DEMO_ONLY = "EXECUTED_DEMO_ONLY"
STATUS_NETWORK_ERROR_DEMO_ONLY = "NETWORK_ERROR_DEMO_ONLY"
# Bybit accepted the HTTP POST but returned a non-zero retCode (e.g.
# 10004 "Error sign"), so no order was actually placed. order_sent
# stays False; final_status is NEVER EXECUTED_DEMO_ONLY in this case.
STATUS_BYBIT_REJECTED_NO_ORDER_SENT = "BYBIT_REJECTED_NO_ORDER_SENT"

# Bybit V5 sign-type header. For HMAC-SHA256 the documented value is "2".
BAPI_SIGN_TYPE_HEADER = "X-BAPI-SIGN-TYPE"
BAPI_SIGN_TYPE_VALUE = "2"

# Ordered gate names -- gates 1..13 are evaluated in every mode; gates
# 14..16 are evaluated only in MODE_EXECUTE_DEMO_ORDER.
GATE_NAMES: tuple[str, ...] = (
    "bl_packet_loaded",
    "bl_packet_all_passed",
    "packet_marked_not_execution_authorization",
    "packet_audit_status_from_bh",
    "environment_is_bybit_demo",
    "symbol_is_solusdt",
    "qty_within_tiny_cap",
    "order_type_market",
    "time_in_force_ioc",
    "reduce_only_false",
    "endpoint_target_demo_only",
    "protected_symbols_not_in_scope",
    "order_count_locked_to_one",
    "explicit_execute_flag",
    "explicit_confirm_flag",
    "demo_credentials_present",
)
PRE_NETWORK_GATE_NAMES: tuple[str, ...] = GATE_NAMES[:13]
EXECUTE_GATE_NAMES: tuple[str, ...] = GATE_NAMES[13:]

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ExplicitTinyOrderExecutionError(bh.DemoOnlyTinyExecutionAdapterError):
    """Raised when BM cannot honor an execute request before network."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DemoCredentials:
    """Demo-scoped credentials. Held only inside the execute path."""

    api_key: str
    api_secret: str
    recv_window: str = DEFAULT_RECV_WINDOW

    @property
    def present(self) -> bool:
        return bool(self.api_key) and bool(self.api_secret)


@dataclass(frozen=True)
class ExecutionGate:
    name: str
    passed: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "reason": self.reason}


@dataclass(frozen=True)
class ExecutionPlan:
    """The single tiny order this module would send, if all gates pass."""

    task_id: str
    upstream_tasks: tuple[str, ...]
    environment: str
    endpoint_target: str
    category: str
    symbol: str
    side: str
    qty: str
    mark_price: str | None
    notional_estimate: str | None
    order_type: str
    time_in_force: str
    reduce_only: bool
    close_on_trigger: bool
    order_link_id: str
    order_link_id_prefix: str
    max_order_count: int
    packet_audit_response_status: str
    packet_is_not_execution_authorization: bool
    body_preview: Mapping[str, Any]
    execution_contract_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "upstream_tasks": list(self.upstream_tasks),
            "environment": self.environment,
            "endpoint_target": self.endpoint_target,
            "category": self.category,
            "symbol": self.symbol,
            "side": self.side,
            "qty": self.qty,
            "mark_price": self.mark_price,
            "notional_estimate": self.notional_estimate,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "reduce_only": self.reduce_only,
            "close_on_trigger": self.close_on_trigger,
            "order_link_id": self.order_link_id,
            "order_link_id_prefix": self.order_link_id_prefix,
            "max_order_count": self.max_order_count,
            "packet_audit_response_status": self.packet_audit_response_status,
            "packet_is_not_execution_authorization": (
                self.packet_is_not_execution_authorization
            ),
            "body_preview": dict(self.body_preview),
            "execution_contract_version": self.execution_contract_version,
        }


@dataclass(frozen=True)
class SendOutcome:
    network_attempted: bool
    order_endpoint_called: bool
    order_sent: bool
    endpoint_target: str
    http_status: int | None
    bybit_ret_code: int | None
    bybit_ret_msg: str
    bybit_order_id: str
    raw_response_summary: str
    sender_kind: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "network_attempted": self.network_attempted,
            "order_endpoint_called": self.order_endpoint_called,
            "order_sent": self.order_sent,
            "endpoint_target": self.endpoint_target,
            "http_status": self.http_status,
            "bybit_ret_code": self.bybit_ret_code,
            "bybit_ret_msg": self.bybit_ret_msg,
            "bybit_order_id": self.bybit_order_id,
            "raw_response_summary": self.raw_response_summary,
            "sender_kind": self.sender_kind,
        }


@dataclass(frozen=True)
class ExecutionReport:
    task_id: str
    identity: str
    phase: str
    mode: str
    upstream_tasks: tuple[str, ...]
    next_required_task: str
    is_review_chain_suffix: bool
    execution_contract_version: str
    bl_packet_loaded: bool
    bl_packet_all_passed: bool
    packet_symbol: str
    packet_audit_response_status: str
    packet_is_not_execution_authorization: bool
    explicit_execute_flag_present: bool
    explicit_confirm_flag_present: bool
    demo_credentials_present: bool
    live_endpoint_denied: bool
    protected_symbols_untouched: bool
    allowed_demo_endpoint_host: str
    allowed_demo_endpoint_url: str
    max_order_count: int
    gates: tuple[ExecutionGate, ...]
    all_pre_network_gates_passed: bool
    all_execute_gates_passed: bool
    final_status: str
    network_attempted: bool
    order_endpoint_called: bool
    order_sent: bool
    bybit_order_id: str
    bybit_ret_code: int | None
    bybit_ret_msg: str
    generated_at_utc: str
    plan: ExecutionPlan | None = None
    outcome: SendOutcome | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "identity": self.identity,
            "phase": self.phase,
            "mode": self.mode,
            "upstream_tasks": list(self.upstream_tasks),
            "next_required_task": self.next_required_task,
            "is_review_chain_suffix": self.is_review_chain_suffix,
            "execution_contract_version": self.execution_contract_version,
            "bl_packet_loaded": self.bl_packet_loaded,
            "bl_packet_all_passed": self.bl_packet_all_passed,
            "packet_symbol": self.packet_symbol,
            "packet_audit_response_status": self.packet_audit_response_status,
            "packet_is_not_execution_authorization": (
                self.packet_is_not_execution_authorization
            ),
            "explicit_execute_flag_present": self.explicit_execute_flag_present,
            "explicit_confirm_flag_present": self.explicit_confirm_flag_present,
            "demo_credentials_present": self.demo_credentials_present,
            "live_endpoint_denied": self.live_endpoint_denied,
            "protected_symbols_untouched": self.protected_symbols_untouched,
            "allowed_demo_endpoint_host": self.allowed_demo_endpoint_host,
            "allowed_demo_endpoint_url": self.allowed_demo_endpoint_url,
            "max_order_count": self.max_order_count,
            "gates": [g.to_dict() for g in self.gates],
            "all_pre_network_gates_passed": self.all_pre_network_gates_passed,
            "all_execute_gates_passed": self.all_execute_gates_passed,
            "final_status": self.final_status,
            "network_attempted": self.network_attempted,
            "order_endpoint_called": self.order_endpoint_called,
            "order_sent": self.order_sent,
            "bybit_order_id": self.bybit_order_id,
            "bybit_ret_code": self.bybit_ret_code,
            "bybit_ret_msg": self.bybit_ret_msg,
            "generated_at_utc": self.generated_at_utc,
            "plan": self.plan.to_dict() if self.plan is not None else None,
            "outcome": (
                self.outcome.to_dict() if self.outcome is not None else None
            ),
        }


# ---------------------------------------------------------------------------
# Credential loading (demo-scoped only)
# ---------------------------------------------------------------------------


def load_demo_credentials_from_env(
    env: Mapping[str, str] | None = None,
) -> DemoCredentials:
    """Load BYBIT_DEMO_* credentials only.

    Never touches BYBIT_API_KEY / BYBIT_API_SECRET (live names). If
    either of the two required demo names is missing, the returned
    ``DemoCredentials`` has ``present=False`` so the caller can produce
    a clean MISSING_DEMO_CREDENTIALS report.
    """

    source: Mapping[str, str] = env if env is not None else os.environ
    api_key = source.get(DEMO_API_KEY_ENV, "") or ""
    api_secret = source.get(DEMO_API_SECRET_ENV, "") or ""
    recv_window = source.get(DEMO_RECV_WINDOW_ENV, DEFAULT_RECV_WINDOW) or (
        DEFAULT_RECV_WINDOW
    )
    return DemoCredentials(
        api_key=api_key.strip(),
        api_secret=api_secret.strip(),
        recv_window=str(recv_window).strip() or DEFAULT_RECV_WINDOW,
    )


# ---------------------------------------------------------------------------
# Plan builder + gate evaluation
# ---------------------------------------------------------------------------


def _packet_audit_status_from_bh(packet: bl.PreparationPacket) -> str:
    audit = dict(packet.payload_audit)
    return str(audit.get("_demo_only_audit_response_status", "") or "")


def _build_body_preview(packet: bl.PreparationPacket) -> dict[str, Any]:
    return {
        "category": ALLOWED_DEMO_CATEGORY,
        "symbol": packet.symbol,
        "side": packet.side,
        "orderType": packet.order_type,
        "qty": packet.qty,
        "timeInForce": packet.time_in_force,
        "reduceOnly": packet.reduce_only,
        "closeOnTrigger": False,
        "orderLinkId": packet.order_link_id,
    }


def build_execution_plan(
    packet: bl.PreparationPacket,
    *,
    endpoint_target: str = ALLOWED_DEMO_ENDPOINT_URL,
) -> ExecutionPlan:
    """Convert a BL ``PreparationPacket`` into the BM ``ExecutionPlan``.

    This function does not call the network and does not evaluate gates;
    gate evaluation is the responsibility of ``_evaluate_gates``.
    """

    return ExecutionPlan(
        task_id=TASK_ID,
        upstream_tasks=UPSTREAM_TASKS,
        environment=packet.environment,
        endpoint_target=endpoint_target,
        category=ALLOWED_DEMO_CATEGORY,
        symbol=packet.symbol,
        side=packet.side,
        qty=packet.qty,
        mark_price=packet.mark_price,
        notional_estimate=packet.notional_estimate,
        order_type=packet.order_type,
        time_in_force=packet.time_in_force,
        reduce_only=packet.reduce_only,
        close_on_trigger=False,
        order_link_id=packet.order_link_id,
        order_link_id_prefix=packet.order_link_id_prefix,
        max_order_count=MAX_ORDER_COUNT,
        packet_audit_response_status=packet.audit_response_status,
        packet_is_not_execution_authorization=(
            packet.packet_is_not_execution_authorization
        ),
        body_preview=_build_body_preview(packet),
        execution_contract_version=EXECUTION_CONTRACT_VERSION,
    )


def _evaluate_gates(
    *,
    packet: bl.PreparationPacket | None,
    bl_all_passed: bool,
    existing_positions: tuple[str, ...],
    endpoint_target: str,
    execute_flag: bool,
    confirm_flag: bool,
    credentials: DemoCredentials,
    mode: str,
) -> tuple[ExecutionGate, ...]:
    """Evaluate every safety gate in fixed order.

    Returns the full ordered ``ExecutionGate`` tuple. The caller decides
    which gates are required for which mode.
    """

    gates: list[ExecutionGate] = []

    # 1. bl_packet_loaded
    gates.append(
        ExecutionGate(
            name="bl_packet_loaded",
            passed=packet is not None,
            reason="" if packet is not None else "no BL packet provided",
        )
    )

    # 2. bl_packet_all_passed
    gates.append(
        ExecutionGate(
            name="bl_packet_all_passed",
            passed=bool(bl_all_passed and packet is not None),
            reason=(
                ""
                if bl_all_passed and packet is not None
                else "BL preparation report all_passed is False"
            ),
        )
    )

    # 3. packet_marked_not_execution_authorization
    if packet is None:
        gates.append(
            ExecutionGate(
                name="packet_marked_not_execution_authorization",
                passed=False,
                reason="no BL packet provided",
            )
        )
    else:
        gates.append(
            ExecutionGate(
                name="packet_marked_not_execution_authorization",
                passed=packet.packet_is_not_execution_authorization is True,
                reason=(
                    ""
                    if packet.packet_is_not_execution_authorization is True
                    else "packet_is_not_execution_authorization must be True"
                ),
            )
        )

    # 4. packet_audit_status_from_bh
    if packet is None:
        gates.append(
            ExecutionGate(
                name="packet_audit_status_from_bh",
                passed=False,
                reason="no BL packet provided",
            )
        )
    else:
        bh_status = _packet_audit_status_from_bh(packet)
        ok_bh = bh_status == bh.AUDIT_RESPONSE_STATUS_NOT_SENT
        gates.append(
            ExecutionGate(
                name="packet_audit_status_from_bh",
                passed=ok_bh,
                reason=(
                    ""
                    if ok_bh
                    else f"packet BH audit marker {bh_status!r} != "
                    f"{bh.AUDIT_RESPONSE_STATUS_NOT_SENT!r}"
                ),
            )
        )

    # 5. environment_is_bybit_demo
    env_value = packet.environment if packet is not None else ""
    env_ok = env_value == bh.ALLOWED_ENVIRONMENT
    gates.append(
        ExecutionGate(
            name="environment_is_bybit_demo",
            passed=env_ok,
            reason=(
                ""
                if env_ok
                else f"environment {env_value!r} != {bh.ALLOWED_ENVIRONMENT!r}"
            ),
        )
    )

    # 6. symbol_is_solusdt
    symbol_value = packet.symbol if packet is not None else ""
    sym_ok = symbol_value == bh.ALLOWED_SYMBOL
    gates.append(
        ExecutionGate(
            name="symbol_is_solusdt",
            passed=sym_ok,
            reason=(
                "" if sym_ok else f"symbol {symbol_value!r} != "
                f"{bh.ALLOWED_SYMBOL!r}"
            ),
        )
    )

    # 7. qty_within_tiny_cap
    qty_ok = False
    qty_reason = ""
    if packet is not None:
        try:
            qty_dec = Decimal(str(packet.qty))
            qty_ok = (
                qty_dec > 0
                and qty_dec <= bh.TINY_QTY_CAP_SOL
                and qty_dec <= Decimal("0.01")
            )
            if not qty_ok:
                qty_reason = (
                    f"qty {qty_dec!r} not in (0, 0.01] (tiny entry cap)"
                )
        except Exception as exc:  # pragma: no cover - defensive
            qty_reason = f"qty parse error: {exc!r}"
    else:
        qty_reason = "no BL packet provided"
    gates.append(
        ExecutionGate(name="qty_within_tiny_cap", passed=qty_ok, reason=qty_reason)
    )

    # 8. order_type_market
    ot_value = packet.order_type if packet is not None else ""
    ot_ok = ot_value == bh.ALLOWED_ORDER_TYPE
    gates.append(
        ExecutionGate(
            name="order_type_market",
            passed=ot_ok,
            reason=(
                ""
                if ot_ok
                else f"order_type {ot_value!r} != {bh.ALLOWED_ORDER_TYPE!r}"
            ),
        )
    )

    # 9. time_in_force_ioc
    tif_value = packet.time_in_force if packet is not None else ""
    tif_ok = tif_value == bh.ALLOWED_TIME_IN_FORCE
    gates.append(
        ExecutionGate(
            name="time_in_force_ioc",
            passed=tif_ok,
            reason=(
                ""
                if tif_ok
                else f"time_in_force {tif_value!r} != "
                f"{bh.ALLOWED_TIME_IN_FORCE!r}"
            ),
        )
    )

    # 10. reduce_only_false
    reduce_only_value = packet.reduce_only if packet is not None else True
    ro_ok = reduce_only_value is False
    gates.append(
        ExecutionGate(
            name="reduce_only_false",
            passed=ro_ok,
            reason=(
                "" if ro_ok else "reduce_only must be False for tiny entry"
            ),
        )
    )

    # 11. endpoint_target_demo_only (host allowlist + BJ live denylist)
    endpoint_ok = False
    endpoint_reason = ""
    try:
        bh.assert_endpoint_is_demo_only(endpoint_target)
        host_ok = endpoint_target.startswith(
            f"https://{ALLOWED_DEMO_ENDPOINT_HOST}/"
        ) or endpoint_target == f"https://{ALLOWED_DEMO_ENDPOINT_HOST}"
        url_ok = endpoint_target == ALLOWED_DEMO_ENDPOINT_URL
        endpoint_ok = host_ok and url_ok
        if not endpoint_ok:
            endpoint_reason = (
                f"endpoint_target {endpoint_target!r} not equal to "
                f"{ALLOWED_DEMO_ENDPOINT_URL!r}"
            )
    except bh.DemoOnlyTinyExecutionAdapterError as exc:
        endpoint_reason = str(exc)
    gates.append(
        ExecutionGate(
            name="endpoint_target_demo_only",
            passed=endpoint_ok,
            reason=endpoint_reason,
        )
    )

    # 12. protected_symbols_not_in_scope (symbol + existing positions)
    protected_overlap = sorted(
        set(existing_positions) & bh.PROTECTED_SYMBOLS
    )
    sym_protected = (
        (packet.symbol in bh.PROTECTED_SYMBOLS) if packet is not None else False
    )
    prot_ok = (not protected_overlap) and (not sym_protected)
    prot_reason = ""
    if not prot_ok:
        prot_reason = (
            f"protected symbols in scope: overlap={protected_overlap!r} "
            f"symbol_is_protected={sym_protected!r}"
        )
    gates.append(
        ExecutionGate(
            name="protected_symbols_not_in_scope",
            passed=prot_ok,
            reason=prot_reason,
        )
    )

    # 13. order_count_locked_to_one
    gates.append(
        ExecutionGate(
            name="order_count_locked_to_one",
            passed=MAX_ORDER_COUNT == 1,
            reason="" if MAX_ORDER_COUNT == 1 else "max_order_count != 1",
        )
    )

    # 14. explicit_execute_flag
    gates.append(
        ExecutionGate(
            name="explicit_execute_flag",
            passed=bool(execute_flag),
            reason="" if execute_flag else f"{EXECUTE_FLAG_NAME} not provided",
        )
    )

    # 15. explicit_confirm_flag
    gates.append(
        ExecutionGate(
            name="explicit_confirm_flag",
            passed=bool(confirm_flag),
            reason="" if confirm_flag else f"{CONFIRM_FLAG_NAME} not provided",
        )
    )

    # 16. demo_credentials_present
    gates.append(
        ExecutionGate(
            name="demo_credentials_present",
            passed=credentials.present,
            reason=(
                ""
                if credentials.present
                else "BYBIT_DEMO_API_KEY / BYBIT_DEMO_API_SECRET missing"
            ),
        )
    )

    return tuple(gates)


# ---------------------------------------------------------------------------
# Sender (single bounded HTTPS POST) -- network-side
# ---------------------------------------------------------------------------


Sender = Callable[[str, Mapping[str, str], bytes], Mapping[str, Any]]


def _serialize_signed_body(body_preview: Mapping[str, Any]) -> tuple[str, bytes]:
    """Serialize the order body once, used identically for sign + POST.

    Returns ``(json_body_string, json_body_bytes)`` where
    ``json_body_bytes == json_body_string.encode("utf-8")`` -- guaranteed
    byte-for-byte equal to what is hashed and what is sent in the HTTP
    request. Compact (no whitespace) and stable key order are required
    by Bybit V5 HMAC.
    """

    body_dict = dict(body_preview)
    json_body_string = json.dumps(
        body_dict,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    json_body_bytes = json_body_string.encode("utf-8")
    assert json_body_bytes.decode("utf-8") == json_body_string  # nosec: B101
    return json_body_string, json_body_bytes


def _sign_bybit_v5(
    *,
    timestamp_ms: str,
    api_key: str,
    api_secret: str,
    recv_window: str,
    json_body_string: str,
) -> str:
    """Compute the Bybit V5 HMAC-SHA256 signature.

    Prehash is ``timestamp_ms + api_key + recv_window + json_body_string``
    where ``json_body_string`` MUST be the exact same string that is
    encoded and sent as the HTTP POST body. The digest is lowercase hex.
    """

    payload = f"{timestamp_ms}{api_key}{recv_window}{json_body_string}"
    return hmac.new(
        api_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _real_sender_via_urllib(
    url: str,
    headers: Mapping[str, str],
    body: bytes,
) -> dict[str, Any]:
    """One-shot HTTPS POST via stdlib urllib. No retry.

    Hard-asserts the URL is the single allowed demo endpoint URL.
    """

    if url != ALLOWED_DEMO_ENDPOINT_URL:
        raise ExplicitTinyOrderExecutionError(
            f"sender refused: url {url!r} != "
            f"{ALLOWED_DEMO_ENDPOINT_URL!r}"
        )

    req = urllib.request.Request(
        url=url,
        data=body,
        headers=dict(headers),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec: B310
            raw = resp.read()
            status = int(resp.status)
    except urllib.error.HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        status = int(getattr(exc, "code", 0) or 0)
    except Exception as exc:  # pragma: no cover - network failure path
        return {
            "_network_error": True,
            "_error_repr": repr(exc),
            "http_status": None,
            "raw_text": "",
            "json": None,
        }

    text = raw.decode("utf-8", errors="replace")
    parsed: dict[str, Any] | None = None
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    return {
        "_network_error": False,
        "http_status": status,
        "raw_text": text,
        "json": parsed,
    }


def _send_one_demo_order(
    plan: ExecutionPlan,
    credentials: DemoCredentials,
    sender: Sender | None = None,
) -> SendOutcome:
    """Send exactly one demo order. Single call, no retry, no loop."""

    if plan.endpoint_target != ALLOWED_DEMO_ENDPOINT_URL:
        raise ExplicitTinyOrderExecutionError(
            f"plan endpoint {plan.endpoint_target!r} != "
            f"{ALLOWED_DEMO_ENDPOINT_URL!r}"
        )
    if not credentials.present:
        raise ExplicitTinyOrderExecutionError(
            "demo credentials missing at send time"
        )
    if plan.max_order_count != 1:
        raise ExplicitTinyOrderExecutionError(
            "plan.max_order_count must be exactly 1"
        )

    timestamp_ms = str(int(_dt.datetime.now(_dt.timezone.utc).timestamp() * 1000))
    json_body_string, body_bytes = _serialize_signed_body(plan.body_preview)
    sign = _sign_bybit_v5(
        timestamp_ms=timestamp_ms,
        api_key=credentials.api_key,
        api_secret=credentials.api_secret,
        recv_window=credentials.recv_window,
        json_body_string=json_body_string,
    )
    headers = {
        "Content-Type": "application/json",
        "X-BAPI-API-KEY": credentials.api_key,
        "X-BAPI-TIMESTAMP": timestamp_ms,
        "X-BAPI-SIGN": sign,
        BAPI_SIGN_TYPE_HEADER: BAPI_SIGN_TYPE_VALUE,
        "X-BAPI-RECV-WINDOW": credentials.recv_window,
    }

    use_sender = sender or _real_sender_via_urllib
    sender_kind = (
        "injected" if sender is not None else "stdlib_urllib_demo_only"
    )

    response = use_sender(plan.endpoint_target, headers, body_bytes)

    network_error = bool(response.get("_network_error"))
    http_status = response.get("http_status")
    raw_text = str(response.get("raw_text", "") or "")
    parsed = response.get("json")

    ret_code: int | None = None
    ret_msg = ""
    order_id = ""
    if isinstance(parsed, dict):
        try:
            ret_code = int(parsed.get("retCode", parsed.get("ret_code", -1)))
        except Exception:
            ret_code = None
        ret_msg = str(parsed.get("retMsg", parsed.get("ret_msg", "")) or "")
        result = parsed.get("result")
        if isinstance(result, dict):
            order_id = str(result.get("orderId", "") or "")

    return SendOutcome(
        network_attempted=True,
        order_endpoint_called=True,
        order_sent=(ret_code == 0) and bool(order_id),
        endpoint_target=plan.endpoint_target,
        http_status=(int(http_status) if isinstance(http_status, int) else None),
        bybit_ret_code=ret_code,
        bybit_ret_msg=ret_msg,
        bybit_order_id=order_id,
        raw_response_summary=raw_text[:2048],
        sender_kind=("network_error" if network_error else sender_kind),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_explicit_tiny_order_execution(
    *,
    mode: str = MODE_DRY_RUN,
    execute_flag: bool = False,
    confirm_flag: bool = False,
    existing_positions: tuple[str, ...] = (),
    endpoint_target: str = ALLOWED_DEMO_ENDPOINT_URL,
    credentials: DemoCredentials | None = None,
    env: Mapping[str, str] | None = None,
    sender: Sender | None = None,
) -> ExecutionReport:
    """Run the BM explicit one-shot tiny order execution path.

    Modes:
        * ``dry_run`` (default) / ``readiness`` -- no network, no order.
        * ``execute_demo_order`` -- requires double-flag + demo credentials
          + every safety gate. Sends *at most one* demo order.

    The function is deliberately structured so that ALL gate evaluation
    happens before any network code is touched, and so that absence of
    demo credentials short-circuits to a MISSING_DEMO_CREDENTIALS report
    instead of failing the task.
    """

    if mode not in SUPPORTED_MODES:
        raise ExplicitTinyOrderExecutionError(
            f"unsupported mode {mode!r}; expected one of {SUPPORTED_MODES!r}"
        )

    # Re-assert at call time as defence-in-depth.
    bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)

    bl_report = bl.run_tiny_order_preparation(
        existing_positions=existing_positions,
        endpoint_target=endpoint_target,
    )
    packet = bl_report.packet

    creds = (
        credentials
        if credentials is not None
        else load_demo_credentials_from_env(env=env)
    )

    gates = _evaluate_gates(
        packet=packet,
        bl_all_passed=bl_report.all_passed,
        existing_positions=existing_positions,
        endpoint_target=endpoint_target,
        execute_flag=execute_flag,
        confirm_flag=confirm_flag,
        credentials=creds,
        mode=mode,
    )

    pre_network_gates = [g for g in gates if g.name in PRE_NETWORK_GATE_NAMES]
    execute_gates = [g for g in gates if g.name in EXECUTE_GATE_NAMES]
    all_pre = all(g.passed for g in pre_network_gates)
    all_exec = all(g.passed for g in execute_gates)

    plan = build_execution_plan(packet, endpoint_target=endpoint_target) if (
        packet is not None and all_pre
    ) else None

    protected_overlap = sorted(
        set(existing_positions) & bh.PROTECTED_SYMBOLS
    )
    sym_protected = (
        (packet.symbol in bh.PROTECTED_SYMBOLS) if packet is not None else False
    )
    protected_untouched = (not protected_overlap) and (not sym_protected)

    # Decide final status and (only in execute mode) maybe send.
    final_status = STATUS_DRY_RUN_OK_NO_NETWORK
    outcome: SendOutcome | None = None
    network_attempted = False
    order_endpoint_called = False
    order_sent = False
    bybit_order_id = ""
    bybit_ret_code: int | None = None
    bybit_ret_msg = ""

    if mode == MODE_DRY_RUN:
        final_status = (
            STATUS_DRY_RUN_OK_NO_NETWORK
            if all_pre
            else STATUS_GATE_REJECTED_NO_NETWORK
        )
    elif mode == MODE_READINESS:
        final_status = (
            STATUS_READINESS_OK_NO_NETWORK
            if all_pre
            else STATUS_GATE_REJECTED_NO_NETWORK
        )
    elif mode == MODE_EXECUTE_DEMO_ORDER:
        if not all_pre:
            final_status = STATUS_GATE_REJECTED_NO_NETWORK
        elif not (execute_flag and confirm_flag):
            final_status = STATUS_GATE_REJECTED_NO_NETWORK
        elif not creds.present:
            final_status = STATUS_MISSING_DEMO_CREDENTIALS
        elif plan is None:
            final_status = STATUS_GATE_REJECTED_NO_NETWORK
        else:
            outcome = _send_one_demo_order(
                plan=plan, credentials=creds, sender=sender
            )
            network_attempted = outcome.network_attempted
            order_endpoint_called = outcome.order_endpoint_called
            order_sent = outcome.order_sent
            bybit_order_id = outcome.bybit_order_id
            bybit_ret_code = outcome.bybit_ret_code
            bybit_ret_msg = outcome.bybit_ret_msg
            if outcome.sender_kind == "network_error":
                final_status = STATUS_NETWORK_ERROR_DEMO_ONLY
            elif (
                outcome.order_sent is True
                and outcome.bybit_ret_code == 0
                and bool(outcome.bybit_order_id)
            ):
                final_status = STATUS_EXECUTED_DEMO_ONLY
            else:
                # Network completed, Bybit replied, but the order was
                # not actually placed (e.g. retCode=10004 "Error sign").
                # NEVER report EXECUTED_DEMO_ONLY in this branch.
                final_status = STATUS_BYBIT_REJECTED_NO_ORDER_SENT

    return ExecutionReport(
        task_id=TASK_ID,
        identity=IDENTITY,
        phase=IMPLEMENTATION_PATH_PHASE,
        mode=mode,
        upstream_tasks=UPSTREAM_TASKS,
        next_required_task=NEXT_REQUIRED_TASK,
        is_review_chain_suffix=IS_REVIEW_CHAIN_SUFFIX,
        execution_contract_version=EXECUTION_CONTRACT_VERSION,
        bl_packet_loaded=(packet is not None),
        bl_packet_all_passed=bl_report.all_passed,
        packet_symbol=(packet.symbol if packet is not None else ""),
        packet_audit_response_status=(
            packet.audit_response_status if packet is not None else ""
        ),
        packet_is_not_execution_authorization=(
            packet.packet_is_not_execution_authorization
            if packet is not None
            else False
        ),
        explicit_execute_flag_present=bool(execute_flag),
        explicit_confirm_flag_present=bool(confirm_flag),
        demo_credentials_present=creds.present,
        live_endpoint_denied=True,
        protected_symbols_untouched=protected_untouched,
        allowed_demo_endpoint_host=ALLOWED_DEMO_ENDPOINT_HOST,
        allowed_demo_endpoint_url=ALLOWED_DEMO_ENDPOINT_URL,
        max_order_count=MAX_ORDER_COUNT,
        gates=gates,
        all_pre_network_gates_passed=all_pre,
        all_execute_gates_passed=all_exec,
        final_status=final_status,
        network_attempted=network_attempted,
        order_endpoint_called=order_endpoint_called,
        order_sent=order_sent,
        bybit_order_id=bybit_order_id,
        bybit_ret_code=bybit_ret_code,
        bybit_ret_msg=bybit_ret_msg,
        generated_at_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        plan=plan,
        outcome=outcome,
    )


# ---------------------------------------------------------------------------
# Report writer (JSON + Markdown; latest_* + timestamped)
# ---------------------------------------------------------------------------


def _utc_timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _render_markdown(report: ExecutionReport) -> str:
    lines: list[str] = []
    lines.append(f"# {report.task_id} -- {report.identity}")
    lines.append("")
    lines.append(f"- generated_at_utc: `{report.generated_at_utc}`")
    lines.append(f"- phase: `{report.phase}`")
    lines.append(f"- mode: `{report.mode}`")
    lines.append(f"- upstream_tasks: `{', '.join(report.upstream_tasks)}`")
    lines.append(f"- next_required_task: `{report.next_required_task}`")
    lines.append(f"- is_review_chain_suffix: `{report.is_review_chain_suffix}`")
    lines.append(
        f"- execution_contract_version: "
        f"`{report.execution_contract_version}`"
    )
    lines.append("")
    lines.append("## Safety summary")
    lines.append("")
    lines.append(f"- bl_packet_loaded: `{report.bl_packet_loaded}`")
    lines.append(f"- bl_packet_all_passed: `{report.bl_packet_all_passed}`")
    lines.append(f"- packet_symbol: `{report.packet_symbol}`")
    lines.append(
        f"- packet_audit_response_status: "
        f"`{report.packet_audit_response_status}`"
    )
    lines.append(
        f"- packet_is_not_execution_authorization: "
        f"`{report.packet_is_not_execution_authorization}`"
    )
    lines.append(
        f"- explicit_execute_flag_present: "
        f"`{report.explicit_execute_flag_present}`"
    )
    lines.append(
        f"- explicit_confirm_flag_present: "
        f"`{report.explicit_confirm_flag_present}`"
    )
    lines.append(
        f"- demo_credentials_present: `{report.demo_credentials_present}`"
    )
    lines.append(f"- live_endpoint_denied: `{report.live_endpoint_denied}`")
    lines.append(
        f"- protected_symbols_untouched: "
        f"`{report.protected_symbols_untouched}`"
    )
    lines.append(
        f"- allowed_demo_endpoint_host: "
        f"`{report.allowed_demo_endpoint_host}`"
    )
    lines.append(
        f"- allowed_demo_endpoint_url: `{report.allowed_demo_endpoint_url}`"
    )
    lines.append(f"- max_order_count: `{report.max_order_count}`")
    lines.append("")
    lines.append("## Gates")
    lines.append("")
    lines.append("| name | passed | reason |")
    lines.append("|---|---|---|")
    for g in report.gates:
        reason = g.reason.replace("|", "\\|") if g.reason else ""
        lines.append(f"| `{g.name}` | `{g.passed}` | {reason} |")
    lines.append("")
    lines.append(
        f"- all_pre_network_gates_passed: "
        f"`{report.all_pre_network_gates_passed}`"
    )
    lines.append(
        f"- all_execute_gates_passed: `{report.all_execute_gates_passed}`"
    )
    lines.append("")
    lines.append("## Plan")
    lines.append("")
    if report.plan is None:
        lines.append("_No plan produced (upstream chain or pre-network gate rejected)._")
    else:
        plan = report.plan
        lines.append(f"- environment: `{plan.environment}`")
        lines.append(f"- endpoint_target: `{plan.endpoint_target}`")
        lines.append(f"- category: `{plan.category}`")
        lines.append(f"- symbol: `{plan.symbol}`")
        lines.append(f"- side: `{plan.side}`")
        lines.append(f"- qty: `{plan.qty}`")
        lines.append(f"- order_type: `{plan.order_type}`")
        lines.append(f"- time_in_force: `{plan.time_in_force}`")
        lines.append(f"- reduce_only: `{plan.reduce_only}`")
        lines.append(f"- close_on_trigger: `{plan.close_on_trigger}`")
        lines.append(f"- order_link_id: `{plan.order_link_id}`")
        lines.append(f"- max_order_count: `{plan.max_order_count}`")
    lines.append("")
    lines.append("## Outcome")
    lines.append("")
    lines.append(f"- final_status: `{report.final_status}`")
    lines.append(f"- network_attempted: `{report.network_attempted}`")
    lines.append(f"- order_endpoint_called: `{report.order_endpoint_called}`")
    lines.append(f"- order_sent: `{report.order_sent}`")
    lines.append(f"- bybit_order_id: `{report.bybit_order_id}`")
    lines.append(f"- bybit_ret_code: `{report.bybit_ret_code}`")
    bybit_msg = report.bybit_ret_msg.replace("|", "\\|") if report.bybit_ret_msg else ""
    lines.append(f"- bybit_ret_msg: `{bybit_msg}`")
    lines.append("")
    lines.append(
        "_demo-only one-shot execution path -- no live endpoint, no live "
        "credentials, no stop attach, no take-profit, no retry, no scheduler, "
        "no main.py / src.risk / BybitExecutor changes._"
    )
    lines.append("")
    return "\n".join(lines)


def write_report(
    report: ExecutionReport,
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
    "ALLOWED_DEMO_CATEGORY",
    "ALLOWED_DEMO_ENDPOINT_HOST",
    "ALLOWED_DEMO_ENDPOINT_URL",
    "BAPI_SIGN_TYPE_HEADER",
    "BAPI_SIGN_TYPE_VALUE",
    "CONFIRM_FLAG_NAME",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_RECV_WINDOW",
    "DEMO_API_KEY_ENV",
    "DEMO_API_SECRET_ENV",
    "DEMO_RECV_WINDOW_ENV",
    "DEMO_SCOPED_ENV_NAMES",
    "DemoCredentials",
    "EXECUTE_FLAG_NAME",
    "EXECUTE_GATE_NAMES",
    "EXECUTION_CONTRACT_VERSION",
    "ExecutionGate",
    "ExecutionPlan",
    "ExecutionReport",
    "ExplicitTinyOrderExecutionError",
    "GATE_NAMES",
    "IDENTITY",
    "IMPLEMENTATION_PATH_PHASE",
    "IS_REVIEW_CHAIN_SUFFIX",
    "MAX_ORDER_COUNT",
    "MODE_DRY_RUN",
    "MODE_EXECUTE_DEMO_ORDER",
    "MODE_READINESS",
    "NEXT_REQUIRED_TASK",
    "PRE_NETWORK_GATE_NAMES",
    "REPORT_NAME",
    "STATUS_BYBIT_REJECTED_NO_ORDER_SENT",
    "STATUS_DRY_RUN_OK_NO_NETWORK",
    "STATUS_EXECUTED_DEMO_ONLY",
    "STATUS_GATE_REJECTED_NO_NETWORK",
    "STATUS_MISSING_DEMO_CREDENTIALS",
    "STATUS_NETWORK_ERROR_DEMO_ONLY",
    "STATUS_READINESS_OK_NO_NETWORK",
    "SUPPORTED_MODES",
    "SendOutcome",
    "Sender",
    "TASK_ID",
    "UPSTREAM_TASKS",
    "_serialize_signed_body",
    "_sign_bybit_v5",
    "build_execution_plan",
    "load_demo_credentials_from_env",
    "run_explicit_tiny_order_execution",
    "write_report",
]
