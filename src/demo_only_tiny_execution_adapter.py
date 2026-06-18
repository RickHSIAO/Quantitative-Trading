"""TASK-014BH — demo-only tiny execution adapter (implementation path scaffold).

CHAIN-BREAKING: this module starts the demo-only tiny execution adapter
implementation path. It deliberately does NOT spawn another review-chain
suffix such as ``_readiness_review`` / ``_final_pre_execution_review`` /
``_manual_authorization_review`` / ``_dry_run`` (as a chained review
layer).

Stage 1 scope:
    * Strict immutable constants (allowed environment, allowed symbol,
      protected-symbols denylist, tiny size cap, live endpoint denylist).
    * Pure offline payload builder for a demo-only SOLUSDT tiny entry.
    * Pure offline guard helpers that reject non-SOL symbols, protected
      symbols, live endpoints, and tiny-cap violations.
    * Module-level chain-break markers consumed by tests and by the next
      task (TASK-014BI demo-only payload dry-run / endpoint guard
      integration).

Hard safety invariants enforced by this module (cross-checked by tests):
    * No network import (no ``requests`` / ``urllib`` / ``http`` /
      ``socket`` / ``pybit``).
    * No environment-variable / secret read.
    * No reference to ``BybitExecutor`` / live executor wiring.
    * No call to any exchange endpoint.
    * No mutation of any existing position; protected positions cannot
      appear anywhere in adapter input without triggering rejection.
    * G20 sender policy is untouched (no sender, no signing, no
      auth header).

This module is the implementation-path counterpart to the
disabled-implementation-scaffold review chain (TASK-014AQ…TASK-014BG)
that has now been closed by TASK-014BG. The next task is
``TASK-014BI_demo_only_tiny_execution_adapter_payload_dry_run`` (or the
equivalent endpoint-guard-integration task) — NOT another review-chain
suffix.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Any, Mapping, Sequence

# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------

TASK_ID = "TASK-014BH"
IDENTITY = "DEMO-ONLY-TINY-EXECUTION-ADAPTER-IMPLEMENTATION-PATH-SCAFFOLD"
IMPLEMENTATION_PATH_PHASE = "scaffold"
IS_REVIEW_CHAIN_SUFFIX = False
CLOSES_DISABLED_REVIEW_CHAIN_UPSTREAM_TASK = "TASK-014BG"
NEXT_REQUIRED_TASK = (
    "TASK-014BI_demo_only_tiny_execution_adapter_payload_dry_run"
)

FORBIDDEN_NEXT_TASK_SUFFIXES = (
    "_readiness_review",
    "_final_pre_execution_review",
    "_manual_authorization_review",
)


# ---------------------------------------------------------------------------
# Strict immutable safety constants
# ---------------------------------------------------------------------------

ALLOWED_ENVIRONMENT = "bybit_demo"
ALLOWED_SYMBOL = "SOLUSDT"

PROTECTED_SYMBOLS: frozenset[str] = frozenset(
    {"ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"}
)

TINY_SIZE_CAP_USDT = Decimal("5")
TINY_QTY_CAP_SOL = Decimal("0.05")
TINY_QTY_STEP_SOL = Decimal("0.01")

LIVE_ENDPOINT_DENYLIST: frozenset[str] = frozenset(
    {
        "https://api.bybit.com",
        "https://api.bytick.com",
        "wss://stream.bybit.com",
        "wss://stream.bytick.com",
    }
)

DEMO_ENDPOINT_DOCUMENTED_ONLY: frozenset[str] = frozenset(
    {
        # documented only — this module NEVER opens a network connection
        "https://api-demo.bybit.com",
    }
)

ALLOWED_SIDES: frozenset[str] = frozenset({"Buy", "Sell"})
ALLOWED_ORDER_TYPE = "Market"
ALLOWED_TIME_IN_FORCE = "IOC"

ORDER_LINK_ID_PREFIX = "DEMO_ONLY_TINY_BH_"
AUDIT_RESPONSE_STATUS_NOT_SENT = "DEMO_ONLY_TINY_BH_NOT_SENT"
ADAPTER_CONTRACT_VERSION = "demo_only_tiny_execution_adapter_implementation_path_scaffold_v1"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DemoOnlyTinyExecutionAdapterError(Exception):
    """Base class for all demo-only tiny execution adapter rejections."""


class DemoOnlyTinyPayloadRejected(DemoOnlyTinyExecutionAdapterError):
    """The proposed tiny payload violated a safety guard."""


class LiveEndpointDenied(DemoOnlyTinyExecutionAdapterError):
    """A caller attempted to reference a live (non-demo) endpoint."""


# ---------------------------------------------------------------------------
# Result dataclass (offline payload + audit metadata)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DemoOnlyTinyEntryPayload:
    """Offline-built demo-only tiny entry payload.

    Holding this object does NOT cause anything to be sent; this module
    has no sender. The payload is intended to be inspected, logged, and
    handed to a separately-authorized demo-only sender in a future task.
    """

    category: str
    symbol: str
    side: str
    order_type: str
    qty: str
    time_in_force: str
    reduce_only: bool
    close_on_trigger: bool
    order_link_id: str
    environment: str
    tiny_size_cap_usdt: str
    tiny_qty_cap_sol: str
    implementation_path_task: str
    adapter_contract_version: str
    audit_response_status: str
    is_review_chain_suffix: bool

    def to_exchange_payload(self) -> dict[str, Any]:
        """Return the subset of fields that would be sent to the exchange.

        This method is pure — it just returns a dict. It does NOT send.
        """

        return {
            "category": self.category,
            "symbol": self.symbol,
            "side": self.side,
            "orderType": self.order_type,
            "qty": self.qty,
            "timeInForce": self.time_in_force,
            "reduceOnly": self.reduce_only,
            "closeOnTrigger": self.close_on_trigger,
            "orderLinkId": self.order_link_id,
        }

    def to_audit_dict(self) -> dict[str, Any]:
        """Return the full record (exchange fields + audit metadata)."""

        return {
            **self.to_exchange_payload(),
            "_demo_only_environment": self.environment,
            "_demo_only_tiny_size_cap_usdt": self.tiny_size_cap_usdt,
            "_demo_only_tiny_qty_cap_sol": self.tiny_qty_cap_sol,
            "_demo_only_implementation_path_task": self.implementation_path_task,
            "_demo_only_adapter_contract_version": self.adapter_contract_version,
            "_demo_only_audit_response_status": self.audit_response_status,
            "_demo_only_is_review_chain_suffix": self.is_review_chain_suffix,
        }


# ---------------------------------------------------------------------------
# Pure offline guard helpers
# ---------------------------------------------------------------------------


def assert_environment_is_demo(environment: str) -> None:
    if environment != ALLOWED_ENVIRONMENT:
        raise DemoOnlyTinyPayloadRejected(
            f"environment {environment!r} not allowed; "
            f"only {ALLOWED_ENVIRONMENT!r} is permitted"
        )


def assert_symbol_is_allowed(symbol: str) -> None:
    if symbol in PROTECTED_SYMBOLS:
        raise DemoOnlyTinyPayloadRejected(
            f"symbol {symbol!r} is a protected position; rejected"
        )
    if symbol != ALLOWED_SYMBOL:
        raise DemoOnlyTinyPayloadRejected(
            f"symbol {symbol!r} not allowed; only {ALLOWED_SYMBOL!r} is permitted"
        )


def assert_no_protected_position_in_scope(
    existing_positions: Sequence[str],
) -> None:
    overlap = sorted(set(existing_positions) & PROTECTED_SYMBOLS)
    if overlap:
        raise DemoOnlyTinyPayloadRejected(
            f"protected positions present in scope: {overlap!r}; rejected"
        )


def assert_endpoint_is_demo_only(url: str) -> None:
    for live_prefix in LIVE_ENDPOINT_DENYLIST:
        if url == live_prefix or url.startswith(live_prefix + "/") or url.startswith(
            live_prefix + "?"
        ):
            raise LiveEndpointDenied(
                f"endpoint {url!r} is on the live denylist; rejected"
            )


def assert_side_is_allowed(side: str) -> None:
    if side not in ALLOWED_SIDES:
        raise DemoOnlyTinyPayloadRejected(
            f"side {side!r} not allowed; expected one of {sorted(ALLOWED_SIDES)!r}"
        )


def _quantize_qty(qty: Decimal) -> Decimal:
    return qty.quantize(TINY_QTY_STEP_SOL, rounding=ROUND_DOWN)


def assert_qty_under_tiny_cap(qty: Decimal) -> None:
    if qty <= 0:
        raise DemoOnlyTinyPayloadRejected(
            f"qty {qty!r} must be positive"
        )
    if qty > TINY_QTY_CAP_SOL:
        raise DemoOnlyTinyPayloadRejected(
            f"qty {qty!r} exceeds tiny cap {TINY_QTY_CAP_SOL!r} SOL"
        )


def assert_notional_under_tiny_cap(qty: Decimal, mark_price: Decimal) -> None:
    if mark_price <= 0:
        raise DemoOnlyTinyPayloadRejected(
            f"mark_price {mark_price!r} must be positive"
        )
    notional = (qty * mark_price).quantize(Decimal("0.0001"))
    if notional > TINY_SIZE_CAP_USDT:
        raise DemoOnlyTinyPayloadRejected(
            f"notional {notional!r} USDT exceeds tiny size cap "
            f"{TINY_SIZE_CAP_USDT!r} USDT (qty={qty}, mark={mark_price})"
        )


def assert_next_task_is_not_review_chain_suffix(next_task: str) -> None:
    for suffix in FORBIDDEN_NEXT_TASK_SUFFIXES:
        if next_task.endswith(suffix):
            raise DemoOnlyTinyExecutionAdapterError(
                f"next_task {next_task!r} ends with forbidden review-chain "
                f"suffix {suffix!r}"
            )


# ---------------------------------------------------------------------------
# Pure offline payload builder
# ---------------------------------------------------------------------------


def _default_order_link_id(symbol: str) -> str:
    return f"{ORDER_LINK_ID_PREFIX}{symbol}_OFFLINE_BUILD"


def build_demo_only_tiny_solusdt_entry_payload(
    *,
    symbol: str,
    side: str,
    qty: Decimal | str | float | int,
    mark_price: Decimal | str | float | int | None = None,
    environment: str = ALLOWED_ENVIRONMENT,
    existing_positions: Sequence[str] = (),
    order_link_id: str | None = None,
) -> DemoOnlyTinyEntryPayload:
    """Build a demo-only SOLUSDT tiny entry payload offline.

    This function is pure: it performs no I/O, opens no socket, reads no
    environment variables, imports no network library, and does not
    instantiate any executor. Its only output is a frozen dataclass.
    """

    assert_environment_is_demo(environment)
    assert_symbol_is_allowed(symbol)
    assert_no_protected_position_in_scope(existing_positions)
    assert_side_is_allowed(side)

    qty_dec = _quantize_qty(Decimal(str(qty)))
    assert_qty_under_tiny_cap(qty_dec)

    if mark_price is not None:
        assert_notional_under_tiny_cap(qty_dec, Decimal(str(mark_price)))

    link_id = order_link_id or _default_order_link_id(symbol)
    if not link_id.startswith(ORDER_LINK_ID_PREFIX):
        raise DemoOnlyTinyPayloadRejected(
            f"order_link_id {link_id!r} must start with {ORDER_LINK_ID_PREFIX!r}"
        )

    return DemoOnlyTinyEntryPayload(
        category="linear",
        symbol=symbol,
        side=side,
        order_type=ALLOWED_ORDER_TYPE,
        qty=format(qty_dec, "f"),
        time_in_force=ALLOWED_TIME_IN_FORCE,
        reduce_only=False,
        close_on_trigger=False,
        order_link_id=link_id,
        environment=environment,
        tiny_size_cap_usdt=format(TINY_SIZE_CAP_USDT, "f"),
        tiny_qty_cap_sol=format(TINY_QTY_CAP_SOL, "f"),
        implementation_path_task=TASK_ID,
        adapter_contract_version=ADAPTER_CONTRACT_VERSION,
        audit_response_status=AUDIT_RESPONSE_STATUS_NOT_SENT,
        is_review_chain_suffix=IS_REVIEW_CHAIN_SUFFIX,
    )


# ---------------------------------------------------------------------------
# Identity helpers (consumed by tests / preview)
# ---------------------------------------------------------------------------


def describe_implementation_path() -> Mapping[str, Any]:
    """Return a small dict describing this implementation-path scaffold."""

    return {
        "task_id": TASK_ID,
        "identity": IDENTITY,
        "phase": IMPLEMENTATION_PATH_PHASE,
        "is_review_chain_suffix": IS_REVIEW_CHAIN_SUFFIX,
        "closes_disabled_review_chain_upstream_task":
            CLOSES_DISABLED_REVIEW_CHAIN_UPSTREAM_TASK,
        "next_required_task": NEXT_REQUIRED_TASK,
        "allowed_environment": ALLOWED_ENVIRONMENT,
        "allowed_symbol": ALLOWED_SYMBOL,
        "protected_symbols": sorted(PROTECTED_SYMBOLS),
        "tiny_size_cap_usdt": format(TINY_SIZE_CAP_USDT, "f"),
        "tiny_qty_cap_sol": format(TINY_QTY_CAP_SOL, "f"),
        "live_endpoint_denylist": sorted(LIVE_ENDPOINT_DENYLIST),
        "adapter_contract_version": ADAPTER_CONTRACT_VERSION,
        "audit_response_status_not_sent": AUDIT_RESPONSE_STATUS_NOT_SENT,
        "order_link_id_prefix": ORDER_LINK_ID_PREFIX,
    }


__all__ = [
    "ADAPTER_CONTRACT_VERSION",
    "ALLOWED_ENVIRONMENT",
    "ALLOWED_ORDER_TYPE",
    "ALLOWED_SIDES",
    "ALLOWED_SYMBOL",
    "ALLOWED_TIME_IN_FORCE",
    "AUDIT_RESPONSE_STATUS_NOT_SENT",
    "CLOSES_DISABLED_REVIEW_CHAIN_UPSTREAM_TASK",
    "DemoOnlyTinyEntryPayload",
    "DemoOnlyTinyExecutionAdapterError",
    "DemoOnlyTinyPayloadRejected",
    "FORBIDDEN_NEXT_TASK_SUFFIXES",
    "IDENTITY",
    "IMPLEMENTATION_PATH_PHASE",
    "IS_REVIEW_CHAIN_SUFFIX",
    "LIVE_ENDPOINT_DENYLIST",
    "LiveEndpointDenied",
    "NEXT_REQUIRED_TASK",
    "ORDER_LINK_ID_PREFIX",
    "PROTECTED_SYMBOLS",
    "TASK_ID",
    "TINY_QTY_CAP_SOL",
    "TINY_QTY_STEP_SOL",
    "TINY_SIZE_CAP_USDT",
    "assert_endpoint_is_demo_only",
    "assert_environment_is_demo",
    "assert_next_task_is_not_review_chain_suffix",
    "assert_no_protected_position_in_scope",
    "assert_notional_under_tiny_cap",
    "assert_qty_under_tiny_cap",
    "assert_side_is_allowed",
    "assert_symbol_is_allowed",
    "build_demo_only_tiny_solusdt_entry_payload",
    "describe_implementation_path",
]
