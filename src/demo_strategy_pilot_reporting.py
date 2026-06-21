"""TASK-014BQ -- demo strategy pilot reporting data model + round-trip closeout.

This module is strictly OFFLINE. It defines:

  * the permanent, sanitized closeout record for the manually-authorized
    TASK-014BO opening / TASK-014BP reduce-only closing Bybit Demo round trip
    (an execution-pipeline VALIDATION trade -- NOT a strategy trade and NOT
    pilot performance); and
  * frozen dataclasses for the upcoming 7-14 day Bybit Demo strategy pilot
    reporting foundation.

It performs no network I/O, sends no orders, starts no scheduler, and never
reads secrets. It does NOT import the live order-execution stack (main, the
risk module, or the live Bybit executor module) and imports no network client.
All monetary and quantity values use ``Decimal``.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping, Sequence

TASK_ID = "TASK-014BQ"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Decimal serialization helpers
# ---------------------------------------------------------------------------


def dec(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def dec_str(value: Any) -> str:
    """Serialize a Decimal-ish value to a canonical string (never float)."""
    if value is None:
        return ""
    return format(dec(value), "f")


# ---------------------------------------------------------------------------
# Verified round-trip evidence (sanitized; no secrets)
# ---------------------------------------------------------------------------

ROUND_TRIP_QUANTITY = Decimal("0.1")

OPENING_EVIDENCE: dict[str, Any] = {
    "task": "TASK-014BO",
    "environment": "Bybit Demo",
    "symbol": "SOLUSDT",
    "side": "Buy",
    "order_type": "Market",
    "time_in_force": "IOC",
    "quantity": "0.1",
    "reduce_only": False,
    "order_id": "77173918-71f6-4829-91c9-025bd8cd76fa",
    "order_link_id": "BO1-4696d511edf11b50",
    "avg_fill_price": "74.11",
    "cum_exec_qty": "0.1",
    "execution_fee": "0.00407605",
    "position_after": "0.1",
    "final_conclusion": "DEMO_ORDER_FILLED_VERIFIED",
    "journal_final_state": "POST_RESULT_VERIFIED",
    "armed_utc": "2026-06-21T10:30:39Z",
    "verified_utc": "2026-06-21T10:30:40Z",
}

CLOSING_EVIDENCE: dict[str, Any] = {
    "task": "TASK-014BP",
    "environment": "Bybit Demo",
    "symbol": "SOLUSDT",
    "side": "Sell",
    "order_type": "Market",
    "time_in_force": "IOC",
    "quantity": "0.1",
    "reduce_only": True,
    "close_order_id": "4ae9e849-655c-4ac3-b830-d49d587c4f4c",
    "close_order_link_id": "BC1-566b8509e96b2def",
    "avg_fill_price": "73.8",
    "cum_exec_qty": "0.1",
    "execution_fee": "0.004059",
    "position_before": "0.1",
    "position_after": "0",
    "short_position_after": False,
    "final_conclusion": "DEMO_REDUCE_ONLY_CLOSE_FILLED_POSITION_ZERO_VERIFIED",
    "journal_final_state": "CLOSE_RESULT_VERIFIED",
    "armed_utc": "2026-06-21T11:09:21Z",
    "verified_utc": "2026-06-21T11:09:22Z",
}

TRADE_CLASSIFICATION = "MANUAL_EXECUTION_PIPELINE_VALIDATION"


# ---------------------------------------------------------------------------
# Round-trip PnL (Decimal only)
# ---------------------------------------------------------------------------


def compute_round_trip_pnl(
    *,
    open_avg_price: Any,
    close_avg_price: Any,
    quantity: Any,
    open_fee: Any,
    close_fee: Any,
) -> dict[str, Decimal]:
    """Compute round-trip PnL with Decimal arithmetic only.

    gross_price_pnl = (close - open) * qty
    total_fees = open_fee + close_fee
    estimated_net_pnl_excluding_funding = gross_price_pnl - total_fees
    """
    o = dec(open_avg_price)
    c = dec(close_avg_price)
    q = dec(quantity)
    of = dec(open_fee)
    cf = dec(close_fee)
    gross = (c - o) * q
    total_fees = of + cf
    net = gross - total_fees
    return {
        "gross_price_pnl": gross,
        "total_fees": total_fees,
        "estimated_net_pnl_excluding_funding": net,
    }


def build_round_trip_closeout() -> dict[str, Any]:
    """Build the full sanitized round-trip closeout artifact (dict)."""
    pnl = compute_round_trip_pnl(
        open_avg_price=OPENING_EVIDENCE["avg_fill_price"],
        close_avg_price=CLOSING_EVIDENCE["avg_fill_price"],
        quantity=ROUND_TRIP_QUANTITY,
        open_fee=OPENING_EVIDENCE["execution_fee"],
        close_fee=CLOSING_EVIDENCE["execution_fee"],
    )
    return {
        "task_id": TASK_ID,
        "title": "Bybit Demo SOLUSDT manual execution-pipeline validation round trip",
        "environment": "BYBIT_DEMO_ONLY",
        "opening": dict(OPENING_EVIDENCE),
        "closing": dict(CLOSING_EVIDENCE),
        "lifecycle": {
            "opened_armed_utc": OPENING_EVIDENCE["armed_utc"],
            "opened_verified_utc": OPENING_EVIDENCE["verified_utc"],
            "closed_armed_utc": CLOSING_EVIDENCE["armed_utc"],
            "closed_verified_utc": CLOSING_EVIDENCE["verified_utc"],
            "round_trip_symbol": "SOLUSDT",
            "round_trip_quantity": dec_str(ROUND_TRIP_QUANTITY),
        },
        "calculation": {
            "method": "Decimal",
            "open_avg_price": OPENING_EVIDENCE["avg_fill_price"],
            "close_avg_price": CLOSING_EVIDENCE["avg_fill_price"],
            "quantity": dec_str(ROUND_TRIP_QUANTITY),
            "open_fee": OPENING_EVIDENCE["execution_fee"],
            "close_fee": CLOSING_EVIDENCE["execution_fee"],
            "gross_price_pnl": dec_str(pnl["gross_price_pnl"]),
            "total_fees": dec_str(pnl["total_fees"]),
            "estimated_net_pnl_excluding_funding": dec_str(pnl["estimated_net_pnl_excluding_funding"]),
            "funding_pnl": "unknown_not_included",
            "currency": "USDT",
        },
        "safety": {
            "opening_post_count": 1,
            "closing_post_count": 1,
            "automatic_retry_count": 0,
            "position_zero_verified": True,
            "short_position_created": False,
            "real_credentials_committed": False,
            "secrets_in_artifact": False,
        },
        "classification": {
            "trade_classification": TRADE_CLASSIFICATION,
            "included_in_strategy_performance": False,
            "included_in_pilot_performance": False,
            "note": (
                "Manually authorized execution-pipeline validation trade. NOT a "
                "strategy trade and NOT pilot performance. Do not mix this result "
                "into future strategy pilot metrics."
            ),
        },
    }


def render_round_trip_closeout_markdown(closeout: Mapping[str, Any] | None = None) -> str:
    """Render the closeout as sanitized Markdown."""
    c = dict(closeout) if closeout is not None else build_round_trip_closeout()
    o = c["opening"]
    cl = c["closing"]
    calc = c["calculation"]
    safety = c["safety"]
    cls = c["classification"]
    lines = [
        f"# {c['task_id']} — {c['title']}",
        "",
        f"**Environment:** {c['environment']}",
        "",
        "> Manually authorized **execution-pipeline validation** round trip. "
        "**NOT** a strategy trade and **NOT** pilot performance. "
        "Excluded from all strategy/pilot metrics.",
        "",
        "## Opening (TASK-014BO)",
        "",
        f"- order_id: `{o['order_id']}`",
        f"- orderLinkId: `{o['order_link_id']}`",
        f"- side / type / TIF: {o['side']} / {o['order_type']} / {o['time_in_force']}",
        f"- quantity: {o['quantity']} (reduceOnly={o['reduce_only']})",
        f"- avg_fill_price: {o['avg_fill_price']}",
        f"- cum_exec_qty: {o['cum_exec_qty']}",
        f"- execution_fee: {o['execution_fee']}",
        f"- position_after: {o['position_after']}",
        f"- final_conclusion: `{o['final_conclusion']}`",
        f"- journal_final_state: `{o['journal_final_state']}`",
        f"- armed_utc / verified_utc: {o['armed_utc']} / {o['verified_utc']}",
        "",
        "## Closing (TASK-014BP, reduce-only)",
        "",
        f"- close_order_id: `{cl['close_order_id']}`",
        f"- close_orderLinkId: `{cl['close_order_link_id']}`",
        f"- side / type / TIF: {cl['side']} / {cl['order_type']} / {cl['time_in_force']}",
        f"- quantity: {cl['quantity']} (reduceOnly={cl['reduce_only']})",
        f"- avg_fill_price: {cl['avg_fill_price']}",
        f"- cum_exec_qty: {cl['cum_exec_qty']}",
        f"- execution_fee: {cl['execution_fee']}",
        f"- position_before / after: {cl['position_before']} / {cl['position_after']}",
        f"- short_position_after: {cl['short_position_after']}",
        f"- final_conclusion: `{cl['final_conclusion']}`",
        f"- journal_final_state: `{cl['journal_final_state']}`",
        f"- armed_utc / verified_utc: {cl['armed_utc']} / {cl['verified_utc']}",
        "",
        "## Round-trip calculation (Decimal)",
        "",
        f"- gross_price_pnl = (close - open) * qty = ({calc['close_avg_price']} - "
        f"{calc['open_avg_price']}) * {calc['quantity']} = **{calc['gross_price_pnl']}**",
        f"- total_fees = {calc['open_fee']} + {calc['close_fee']} = **{calc['total_fees']}**",
        f"- estimated_net_pnl_excluding_funding = **{calc['estimated_net_pnl_excluding_funding']}** "
        f"{calc['currency']} (funding: {calc['funding_pnl']})",
        "",
        "## Safety",
        "",
        f"- opening_post_count: {safety['opening_post_count']}",
        f"- closing_post_count: {safety['closing_post_count']}",
        f"- automatic_retry_count: {safety['automatic_retry_count']}",
        f"- position_zero_verified: {safety['position_zero_verified']}",
        f"- short_position_created: {safety['short_position_created']}",
        "",
        "## Classification",
        "",
        f"- trade_classification: `{cls['trade_classification']}`",
        f"- included_in_strategy_performance: {cls['included_in_strategy_performance']}",
        f"- included_in_pilot_performance: {cls['included_in_pilot_performance']}",
        "",
        f"{cls['note']}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pilot reporting frozen dataclasses
# ---------------------------------------------------------------------------

ENVIRONMENT_DEMO_ONLY = "BYBIT_DEMO_ONLY"


@dataclass(frozen=True)
class PilotConfig:
    pilot_id: str
    start_date: str
    strategy_name: str
    initial_equity_usdt: Decimal
    comparison_forward_period: str = ""
    maximum_calendar_days: int = 14
    minimum_closed_trades: int = 10
    environment: str = ENVIRONMENT_DEMO_ONLY
    notion_enabled: bool = False
    excel_enabled: bool = True
    discord_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "pilot_id": self.pilot_id,
            "start_date": self.start_date,
            "strategy_name": self.strategy_name,
            "initial_equity_usdt": dec_str(self.initial_equity_usdt),
            "comparison_forward_period": self.comparison_forward_period,
            "maximum_calendar_days": self.maximum_calendar_days,
            "minimum_closed_trades": self.minimum_closed_trades,
            "environment": self.environment,
            "notion_enabled": self.notion_enabled,
            "excel_enabled": self.excel_enabled,
            "discord_enabled": self.discord_enabled,
        }


@dataclass(frozen=True)
class PilotDailyRecord:
    date: str
    pilot_day: int
    runner_status: str = "NOT_STARTED"
    signal_count: int = 0
    order_count: int = 0
    filled_count: int = 0
    closed_trade_count: int = 0
    realized_pnl_usdt: Decimal = Decimal("0")
    trading_fees_usdt: Decimal = Decimal("0")
    funding_pnl_usdt: Decimal = Decimal("0")
    daily_net_pnl_usdt: Decimal = Decimal("0")
    cumulative_net_pnl_usdt: Decimal = Decimal("0")
    daily_return_pct: Decimal = Decimal("0")
    cumulative_return_pct: Decimal = Decimal("0")
    max_drawdown_pct: Decimal = Decimal("0")
    current_position_symbol: str = ""
    current_position_side: str = ""
    current_position_qty: Decimal = Decimal("0")
    notion_sync_status: str = "PENDING"
    excel_export_status: str = "PENDING"
    discord_notify_status: str = "PENDING"
    alerts_triggered: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "pilot_day": self.pilot_day,
            "runner_status": self.runner_status,
            "signal_count": self.signal_count,
            "order_count": self.order_count,
            "filled_count": self.filled_count,
            "closed_trade_count": self.closed_trade_count,
            "realized_pnl_usdt": dec_str(self.realized_pnl_usdt),
            "trading_fees_usdt": dec_str(self.trading_fees_usdt),
            "funding_pnl_usdt": dec_str(self.funding_pnl_usdt),
            "daily_net_pnl_usdt": dec_str(self.daily_net_pnl_usdt),
            "cumulative_net_pnl_usdt": dec_str(self.cumulative_net_pnl_usdt),
            "daily_return_pct": dec_str(self.daily_return_pct),
            "cumulative_return_pct": dec_str(self.cumulative_return_pct),
            "max_drawdown_pct": dec_str(self.max_drawdown_pct),
            "current_position_symbol": self.current_position_symbol,
            "current_position_side": self.current_position_side,
            "current_position_qty": dec_str(self.current_position_qty),
            "notion_sync_status": self.notion_sync_status,
            "excel_export_status": self.excel_export_status,
            "discord_notify_status": self.discord_notify_status,
            "alerts_triggered": list(self.alerts_triggered),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class PilotTradeRecord:
    pilot_id: str
    trade_id: str
    signal_id: str
    symbol: str
    side: str
    entry_order_id: str
    exit_order_id: str
    entry_order_link_id: str
    exit_order_link_id: str
    entry_time_utc: str
    exit_time_utc: str
    requested_qty: Decimal
    executed_qty: Decimal
    entry_price: Decimal
    exit_price: Decimal
    entry_fee: Decimal
    exit_fee: Decimal
    funding_pnl: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
    slippage_entry_bps: Decimal
    slippage_exit_bps: Decimal
    final_status: str
    included_in_performance: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "pilot_id": self.pilot_id,
            "trade_id": self.trade_id,
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_order_id": self.entry_order_id,
            "exit_order_id": self.exit_order_id,
            "entry_order_link_id": self.entry_order_link_id,
            "exit_order_link_id": self.exit_order_link_id,
            "entry_time_utc": self.entry_time_utc,
            "exit_time_utc": self.exit_time_utc,
            "requested_qty": dec_str(self.requested_qty),
            "executed_qty": dec_str(self.executed_qty),
            "entry_price": dec_str(self.entry_price),
            "exit_price": dec_str(self.exit_price),
            "entry_fee": dec_str(self.entry_fee),
            "exit_fee": dec_str(self.exit_fee),
            "funding_pnl": dec_str(self.funding_pnl),
            "gross_pnl": dec_str(self.gross_pnl),
            "net_pnl": dec_str(self.net_pnl),
            "slippage_entry_bps": dec_str(self.slippage_entry_bps),
            "slippage_exit_bps": dec_str(self.slippage_exit_bps),
            "final_status": self.final_status,
            "included_in_performance": self.included_in_performance,
        }


@dataclass(frozen=True)
class PilotAuditEvent:
    timestamp_utc: str
    pilot_id: str
    event_type: str
    component: str
    status: str
    message: str
    reference_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_utc": self.timestamp_utc,
            "pilot_id": self.pilot_id,
            "event_type": self.event_type,
            "component": self.component,
            "status": self.status,
            "message": self.message,
            "reference_id": self.reference_id,
        }


__all__ = [
    "CLOSING_EVIDENCE",
    "ENVIRONMENT_DEMO_ONLY",
    "OPENING_EVIDENCE",
    "PROJECT_ROOT",
    "PilotAuditEvent",
    "PilotConfig",
    "PilotDailyRecord",
    "PilotTradeRecord",
    "ROUND_TRIP_QUANTITY",
    "TASK_ID",
    "TRADE_CLASSIFICATION",
    "build_round_trip_closeout",
    "compute_round_trip_pnl",
    "dec",
    "dec_str",
    "render_round_trip_closeout_markdown",
]
