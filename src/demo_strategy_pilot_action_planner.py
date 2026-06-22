"""TASK-014BX_FIX -- canonical strategy-native action planner for the Demo Pilot.

Derives the strategy's OWN desired Bybit Demo actions for a Pilot date by reusing
the existing canonical sizing / portfolio / position-transition logic already in
this repository. It does NOT invent a weight-to-quantity formula:

    * signals come from the authoritative Primary Forward Record source
      (TASK-014BS adapter: src/demo_strategy_pilot_forward_source.py);
    * per-signal entry/stop prices use the existing TASK-014P stop model
      (src/demo_new_entry_candidate_builder.DEFAULT_*_STOP_PCT) anchored to the
      realtime market price and rounded to the instrument tick;
    * position sizing uses the existing canonical 0.4 fractional-Kelly portfolio
      sizer (src/demo_portfolio_risk.compute_demo_portfolio_sizing), whose own
      portfolio limits (<=10 positions, gross/net/single-position caps) are the
      STRATEGY's risk logic -- NOT the removed artificial Pilot caps;
    * quantities are floored to the instrument qty step
      (src/demo_instrument_rules.round_qty_down).

Target positions are then compared against the CURRENT Bybit Demo positions to
produce OPEN / ADD / REDUCE / CLOSE actions (the canonical target-vs-current
position transition). Multiple orders, notionals above 10 USDT, multiple
positions, additions, reductions and partial closes are all preserved.

Account / market / instrument data is read through an injected provider
(``PilotAccountMarketProvider``). In production the provider is built from the
existing read-only Demo client + market-price guard; in tests a fake provider
supplies fixtures. If a usable planner cannot run (no provider, or required
account/market inputs unavailable) it FAILS CLOSED with
``STRATEGY_NATIVE_ACTION_PLANNER_UNAVAILABLE`` and does not pretend the Pilot is
ready.

This module performs no network I/O itself, sends no order, and imports neither
``main``, ``src.risk`` nor the live ``BybitExecutor``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping, Protocol, Sequence

from src import demo_strategy_pilot_native_execution as nx
from src.demo_new_entry_candidate_builder import (
    DEFAULT_LONG_STOP_PCT,
    DEFAULT_SHORT_STOP_PCT,
)
from src.demo_instrument_rules import InstrumentRules, round_price_to_tick, round_qty_down
from src.demo_portfolio_risk import (
    DemoOpenPosition,
    DemoSignalCandidate,
    compute_demo_portfolio_sizing,
)

TASK_ID = "TASK-014BX_FIX"

# Canonical full-Kelly fraction: with the repo's KELLY_MULTIPLIER=0.40 this makes
# the portfolio risk budget equity * 1.0 * 0.40 == equity * 0.40, exactly the
# canonical demo budget (apps/demo_trading/kelly_sizer total_risk_budget). This
# is the existing sizing, not an invented value.
CANONICAL_FULL_KELLY_FRACTION = 1.0

PROTECTED_SYMBOLS = frozenset(nx.PROTECTED_SYMBOLS)

STATUS_PLANNED = "STRATEGY_NATIVE_ACTIONS_PLANNED"
STATUS_PLANNER_UNAVAILABLE = "STRATEGY_NATIVE_ACTION_PLANNER_UNAVAILABLE"


class PilotAccountMarketProvider(Protocol):
    """Read-only account / market data needed by the canonical sizer.

    Production implementations read Bybit DEMO (read-only). Test implementations
    return fixtures. Any method raising / returning unusable data makes the
    planner fail closed."""

    def equity_usd(self) -> float: ...
    def available_balance_usd(self) -> float: ...
    def open_positions(self) -> Sequence[DemoOpenPosition]: ...
    def market_price(self, symbol: str) -> float | None: ...
    def instrument_rule(self, symbol: str) -> InstrumentRules | None: ...


@dataclass
class PlannerResult:
    status: str
    actions: list[nx.StrategyNativeAction]
    target_positions: list[dict[str, Any]]
    current_positions: list[dict[str, Any]]
    rejected_signals: list[dict[str, Any]]
    sizing: Mapping[str, Any] | None
    detail: str = ""

    @property
    def available(self) -> bool:
        return self.status == STATUS_PLANNED

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": TASK_ID, "status": self.status,
            "action_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
            "target_positions": self.target_positions,
            "current_positions": self.current_positions,
            "rejected_signals": self.rejected_signals,
            "sizing": dict(self.sizing) if self.sizing else None,
            "detail": self.detail,
        }


def _side_to_long_short(side: str) -> str:
    s = str(side or "").strip().lower()
    if s in ("long", "buy"):
        return "long"
    if s in ("short", "sell"):
        return "short"
    return ""


def _open_side(long_short: str) -> str:
    return "Buy" if long_short == "long" else "Sell"


def _close_side(long_short: str) -> str:
    # Reduce/close uses the opposite side of the held position.
    return "Sell" if long_short == "long" else "Buy"


def _qty_str(value: float) -> str:
    # Deterministic, non-scientific decimal string.
    return format(Decimal(str(value)).normalize(), "f")


def plan_strategy_native_actions(
    *,
    forward_result: Any,
    provider: PilotAccountMarketProvider | None,
    full_kelly_fraction: float | None = None,
) -> PlannerResult:
    """Produce strategy-native actions for a date from the canonical pipeline.

    ``forward_result`` is the TASK-014BS ``ForwardStrategySourceResult`` (or any
    object exposing ``normalized_signals``). Returns a ``PlannerResult``; on any
    missing provider / unusable account data it fails closed with
    ``STRATEGY_NATIVE_ACTION_PLANNER_UNAVAILABLE``.
    """
    if provider is None:
        return PlannerResult(STATUS_PLANNER_UNAVAILABLE, [], [], [], [], None,
                             "no account/market provider available")

    signals = list(getattr(forward_result, "normalized_signals", None)
                   or (forward_result.get("signals") if isinstance(forward_result, Mapping) else []))

    # 1. Read canonical account state (fail closed on any read problem).
    try:
        equity = float(provider.equity_usd())
        balance = float(provider.available_balance_usd())
        open_positions = list(provider.open_positions())
    except Exception as exc:  # noqa: BLE001
        return PlannerResult(STATUS_PLANNER_UNAVAILABLE, [], [], [], [], None,
                             f"account read failed: {exc}")
    if not (equity > 0):
        return PlannerResult(STATUS_PLANNER_UNAVAILABLE, [], [], [], [], None,
                             "equity unavailable / non-positive")

    # 2. Build canonical candidates (entry/stop via the existing TASK-014P model).
    candidates: list[DemoSignalCandidate] = []
    rejected: list[dict[str, Any]] = []
    for sig in signals:
        symbol = str(sig.get("symbol", "")).strip().upper()
        ls = _side_to_long_short(sig.get("side"))
        if not symbol or not ls:
            rejected.append({"symbol": symbol, "reason": "invalid_signal"})
            continue
        if symbol in PROTECTED_SYMBOLS:
            rejected.append({"symbol": symbol, "reason": "protected_symbol"})
            continue
        price = provider.market_price(symbol)
        rule = provider.instrument_rule(symbol)
        if price is None or not (float(price) > 0) or rule is None:
            rejected.append({"symbol": symbol, "reason": "no_market_price_or_instrument_rule"})
            continue
        entry = round_price_to_tick(float(price), rule.tick_size)
        stop_pct = DEFAULT_LONG_STOP_PCT if ls == "long" else DEFAULT_SHORT_STOP_PCT
        raw_stop = entry * (1.0 - stop_pct) if ls == "long" else entry * (1.0 + stop_pct)
        stop = round_price_to_tick(raw_stop, rule.tick_size)
        if stop <= 0 or entry <= 0 or (ls == "long" and not stop < entry) \
                or (ls == "short" and not stop > entry):
            rejected.append({"symbol": symbol, "reason": "invalid_stop_distance"})
            continue
        score = 0.0
        try:
            score = abs(float(sig.get("score", 0) or 0))
        except (TypeError, ValueError):
            score = 0.0
        candidates.append(DemoSignalCandidate(symbol=symbol, side=ls, entry_price=entry,
                                              stop_price=stop, score=score))

    fk = CANONICAL_FULL_KELLY_FRACTION if full_kelly_fraction is None else float(full_kelly_fraction)

    # 3. Canonical 0.4 fractional-Kelly portfolio sizing (strategy risk logic).
    sizing = compute_demo_portfolio_sizing(
        equity_usd=equity, available_balance_usd=balance,
        full_kelly_fraction=fk, open_positions=list(open_positions),
        candidates=candidates, demo_environment_expected=True)

    # 4. Build target positions (accepted proposals), snapped to qty step.
    rule_by_symbol = {c.symbol: provider.instrument_rule(c.symbol) for c in candidates}
    targets: dict[str, dict[str, Any]] = {}
    for p in sizing.proposals:
        if not p.accepted:
            continue
        rule = rule_by_symbol.get(p.symbol)
        qty = round_qty_down(float(p.quantity), rule.qty_step) if rule else float(p.quantity)
        if qty <= 0:
            rejected.append({"symbol": p.symbol, "reason": "qty_floored_to_zero"})
            continue
        targets[p.symbol] = {"symbol": p.symbol, "side": p.side, "qty": qty,
                             "entry_price": p.entry_price, "notional": p.proposed_notional_usd}

    current = {pos.symbol: pos for pos in open_positions}

    # 5. Canonical target-vs-current position transition.
    actions = _diff_positions(targets, current)

    return PlannerResult(
        STATUS_PLANNED, actions,
        target_positions=list(targets.values()),
        current_positions=[{"symbol": p.symbol, "side": p.side,
                            "qty": float(p.quantity), "entry_price": float(p.entry_price)}
                           for p in open_positions],
        rejected_signals=rejected, sizing=sizing.to_dict(),
        detail="strategy-native actions planned via canonical sizer")


def _diff_positions(targets: Mapping[str, Mapping[str, Any]],
                    current: Mapping[str, Any]) -> list[nx.StrategyNativeAction]:
    """Compare strategy target positions to current Demo positions.

    Produces OPEN / ADD / REDUCE / CLOSE (and CLOSE+OPEN for a side flip),
    preserving the strategy-produced quantity and direction. No removed Pilot
    cap is applied here."""
    actions: list[nx.StrategyNativeAction] = []
    seq = 0
    symbols = sorted(set(targets) | set(current))
    for symbol in symbols:
        tgt = targets.get(symbol)
        cur = current.get(symbol)
        cur_side = _side_to_long_short(getattr(cur, "side", "")) if cur is not None else ""
        cur_qty = float(getattr(cur, "quantity", 0) or 0) if cur is not None else 0.0

        if tgt is None:
            # Held but no longer a target -> full close (reduce-only).
            if cur_qty > 0:
                actions.append(nx.StrategyNativeAction(
                    symbol=symbol, side=_close_side(cur_side), qty=_qty_str(cur_qty),
                    intent=nx.INTENT_CLOSE, reduce_only=True, action_seq=seq,
                    source_reference="target_exit")); seq += 1
            continue

        tgt_side = tgt["side"]
        tgt_qty = float(tgt["qty"])
        if cur is None or cur_qty <= 0:
            actions.append(nx.StrategyNativeAction(
                symbol=symbol, side=_open_side(tgt_side), qty=_qty_str(tgt_qty),
                intent=nx.INTENT_OPEN, reduce_only=False,
                notional_usdt=_qty_str(tgt.get("notional", 0)), action_seq=seq,
                source_reference="target_open")); seq += 1
            continue

        if cur_side == tgt_side:
            delta = round(tgt_qty - cur_qty, 12)
            if delta > 0:
                actions.append(nx.StrategyNativeAction(
                    symbol=symbol, side=_open_side(tgt_side), qty=_qty_str(delta),
                    intent=nx.INTENT_ADD, reduce_only=False, action_seq=seq,
                    source_reference="target_add")); seq += 1
            elif delta < 0:
                actions.append(nx.StrategyNativeAction(
                    symbol=symbol, side=_close_side(tgt_side), qty=_qty_str(abs(delta)),
                    intent=nx.INTENT_REDUCE, reduce_only=True, action_seq=seq,
                    source_reference="target_reduce")); seq += 1
            # delta == 0: position already at target; no action.
            continue

        # Opposite side -> close current, then open target.
        actions.append(nx.StrategyNativeAction(
            symbol=symbol, side=_close_side(cur_side), qty=_qty_str(cur_qty),
            intent=nx.INTENT_CLOSE, reduce_only=True, action_seq=seq,
            source_reference="target_flip_close")); seq += 1
        actions.append(nx.StrategyNativeAction(
            symbol=symbol, side=_open_side(tgt_side), qty=_qty_str(tgt_qty),
            intent=nx.INTENT_OPEN, reduce_only=False, action_seq=seq,
            source_reference="target_flip_open")); seq += 1
    return actions


__all__ = [
    "CANONICAL_FULL_KELLY_FRACTION",
    "PROTECTED_SYMBOLS",
    "PilotAccountMarketProvider",
    "PlannerResult",
    "STATUS_PLANNED",
    "STATUS_PLANNER_UNAVAILABLE",
    "TASK_ID",
    "plan_strategy_native_actions",
]
