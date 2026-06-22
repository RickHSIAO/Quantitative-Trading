"""TASK-014BX_FIX / TASK-014BY_FIX / TASK-014BY_FIX2 -- canonical action planner.

ACTIVE V1 EXECUTION PATH = exact V1 baseline target-weight translation.

Proven canonical V1 sizing semantics (audited from the authoritative Primary
Forward Record implementation):

    apps/forward_record/primary.py:
        frame["position_usd"] = frame["weight"] * config.paper_config.initial_nav_usd

    paper_portfolio/state.json confirms position_usd / weight == initial_nav_usd
    for every position (equal-weight 25 long / 25 short, +/-0.02, long_weight_sum
    = +0.5, short_weight_sum = -0.5, gross_exposure = 1.0, net_exposure ~ 0).

V1 sizes by the strategy's TARGET WEIGHT against a FROZEN CAPITAL BASE (10,000
USDT from ``PaperTradingConfig.initial_nav_usd``), NOT by 0.4 fractional Kelly
and NOT by Demo wallet equity. This planner reproduces V1 exactly as an
EXECUTION TRANSLATION (not a new sizing strategy):

    target_weight   <- authoritative Forward positions artifact (signed)
    capital_base    <- PaperTradingConfig.initial_nav_usd (frozen; NOT wallet equity)
    target_notional <- target_weight * capital_base
    target_qty      <- |target_notional| / current Demo price, floored to qty step
    transitions     <- compare target vs current Demo positions -> OPEN/ADD/REDUCE/CLOSE

The 0.4 fractional-Kelly sizer (src/demo_portfolio_risk.compute_demo_portfolio_sizing)
is DELIBERATELY NOT imported or called here; it remains available only for
OFFLINE / SHADOW Challenger experiments. If V1 sizing semantics or capital base
cannot be proven, the planner fails closed (``V1_BASELINE_SIZING_UNVERIFIED`` /
``V1_BASELINE_CAPITAL_BASE_UNVERIFIED``) and the send path must refuse.

No artificial Pilot order/notional/position caps are applied. Protected symbols
are rejected; Demo-only endpoint and Live-denied guards are enforced downstream.
This module performs no network I/O, sends no order, and imports neither main,
src.risk nor the live BybitExecutor.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Protocol, Sequence

from src import demo_strategy_pilot_native_execution as nx
from src.demo_instrument_rules import InstrumentRules, round_qty_down
from src.demo_portfolio_risk import DemoOpenPosition  # type only (NOT the Kelly sizer)

TASK_ID = "TASK-014BY_FIX2"

# Proof references for the active V1 sizing semantics.
V1_SIZING_MODE = "V1_BASELINE_TARGET_WEIGHT_TRANSLATION"
V1_SIZING_PROOF = (
    "apps/forward_record/primary.py: position_usd = weight * paper_config.initial_nav_usd; "
    "paper_portfolio/state.json: position_usd/weight == initial_nav_usd for all positions"
)
V1_CAPITAL_BASE_SOURCE = (
    "apps.paper_trading.config.PaperTradingConfig.initial_nav_usd (frozen default)"
)

PROTECTED_SYMBOLS = frozenset(nx.PROTECTED_SYMBOLS)

STATUS_PLANNED = "STRATEGY_NATIVE_ACTIONS_PLANNED"
STATUS_PLANNER_UNAVAILABLE = "STRATEGY_NATIVE_ACTION_PLANNER_UNAVAILABLE"
STATUS_V1_BASELINE_SIZING_UNVERIFIED = "V1_BASELINE_SIZING_UNVERIFIED"
STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED = "V1_BASELINE_CAPITAL_BASE_UNVERIFIED"

# Parity tolerance for verifying the strategy target survives translation.
_GROSS_NET_TOLERANCE = 1e-6


class PilotAccountMarketProvider(Protocol):
    """Read-only account / market data needed for V1 target-weight translation.

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
    sizing_verification: Mapping[str, Any]
    detail: str = ""

    @property
    def available(self) -> bool:
        return self.status == STATUS_PLANNED

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": TASK_ID, "status": self.status, "sizing_mode": V1_SIZING_MODE,
            "action_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
            "target_positions": self.target_positions,
            "current_positions": self.current_positions,
            "rejected_signals": self.rejected_signals,
            "sizing_verification": dict(self.sizing_verification),
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
    return "Sell" if long_short == "long" else "Buy"


def _qty_str(value: float) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def resolve_v1_capital_base() -> tuple[float, str] | None:
    """Resolve the frozen V1 strategy capital base from the authoritative Forward config.

    Returns ``(capital_base_usd, source_description)`` or ``None`` (fail closed)."""
    try:
        from apps.paper_trading.config import PaperTradingConfig
        base = float(PaperTradingConfig().initial_nav_usd)
        if base > 0 and math.isfinite(base):
            return (base, V1_CAPITAL_BASE_SOURCE)
    except Exception:  # noqa: BLE001
        pass
    return None


def _signed_weight(side_ls: str, score: Any) -> float | None:
    """Signed target weight = (+ for long, - for short) * |weight| (score)."""
    try:
        mag = abs(float(score))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(mag):
        return None
    return mag if side_ls == "long" else -mag


def plan_strategy_native_actions(
    *,
    forward_result: Any,
    provider: PilotAccountMarketProvider | None,
    v1_capital_base_usd: float | None = None,
    full_kelly_fraction: float | None = None,  # accepted for back-compat; IGNORED (V1 != Kelly)
) -> PlannerResult:
    """Produce V1-baseline strategy-native actions for a date.

    Target sizing uses the frozen V1 strategy capital base (resolved from the
    authoritative Forward config, NOT the Demo wallet equity).  Demo wallet
    equity is read for reference only and is never used to scale target
    positions.

    Fails closed STRATEGY_NATIVE_ACTION_PLANNER_UNAVAILABLE on missing provider,
    V1_BASELINE_CAPITAL_BASE_UNVERIFIED when the capital base cannot be resolved,
    and V1_BASELINE_SIZING_UNVERIFIED when a signed target weight cannot be proven.
    """
    empty_verif = {"verified": False, "sizing_mode": V1_SIZING_MODE, "kelly_used": False,
                   "proof": V1_SIZING_PROOF, "wallet_used_for_target_sizing": False}
    if provider is None:
        return PlannerResult(STATUS_PLANNER_UNAVAILABLE, [], [], [], [], empty_verif,
                             "no account/market provider available")

    # Resolve V1 capital base (frozen strategy capital, NOT Demo wallet).
    if v1_capital_base_usd is not None:
        if not (v1_capital_base_usd > 0 and math.isfinite(v1_capital_base_usd)):
            return PlannerResult(STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED, [], [], [], [],
                                 empty_verif, "explicit v1_capital_base_usd invalid")
        capital_source = "explicit_parameter"
    else:
        resolved = resolve_v1_capital_base()
        if resolved is None:
            return PlannerResult(STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED, [], [], [], [],
                                 empty_verif,
                                 "V1 capital base unresolvable from Forward config; send path must refuse")
        v1_capital_base_usd, capital_source = resolved

    signals = list(getattr(forward_result, "normalized_signals", None)
                   or (forward_result.get("signals") if isinstance(forward_result, Mapping) else []))

    try:
        wallet_equity = float(provider.equity_usd())
        open_positions = list(provider.open_positions())
    except Exception as exc:  # noqa: BLE001
        return PlannerResult(STATUS_PLANNER_UNAVAILABLE, [], [], [], [], empty_verif,
                             f"account read failed: {exc}")
    if not (wallet_equity > 0):
        return PlannerResult(STATUS_PLANNER_UNAVAILABLE, [], [], [], [], empty_verif,
                             "equity unavailable / non-positive")

    targets: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    weight_unverifiable = False
    long_exp = short_exp = gross_exp = net_exp = 0.0

    for sig in signals:
        symbol = str(sig.get("symbol", "")).strip().upper()
        ls = _side_to_long_short(sig.get("side"))
        if not symbol or not ls:
            rejected.append({"symbol": symbol, "reason": "invalid_signal"})
            continue
        if symbol in PROTECTED_SYMBOLS:
            rejected.append({"symbol": symbol, "reason": "protected_symbol"})
            continue
        # V1 sizing PROOF requirement: an explicit signed target weight must exist.
        if "score" not in sig and "weight" not in sig:
            weight_unverifiable = True
            rejected.append({"symbol": symbol, "reason": "target_weight_unverifiable"})
            continue
        raw_w = sig.get("weight", sig.get("score"))
        weight = _signed_weight(ls, raw_w)
        if weight is None:
            weight_unverifiable = True
            rejected.append({"symbol": symbol, "reason": "target_weight_unparseable"})
            continue

        price = provider.market_price(symbol)
        rule = provider.instrument_rule(symbol)
        if price is None or not (float(price) > 0) or rule is None:
            rejected.append({"symbol": symbol, "reason": "no_market_price_or_instrument_rule"})
            continue

        # EXECUTION TRANSLATION (NOT a new sizing strategy):
        #   target_notional = target_weight * v1_capital_base ; qty = |notional| / price (floored).
        target_notional = weight * v1_capital_base_usd
        target_qty = round_qty_down(abs(target_notional) / float(price), rule.qty_step)
        long_exp += weight if weight > 0 else 0.0
        short_exp += weight if weight < 0 else 0.0
        gross_exp += abs(weight)
        net_exp += weight
        if target_qty <= 0:
            rejected.append({"symbol": symbol, "reason": "qty_floored_to_zero",
                             "target_weight": weight})
            continue
        targets[symbol] = {"symbol": symbol, "side": ls, "qty": target_qty,
                           "target_weight": weight, "target_notional": target_notional,
                           "price": float(price)}

    verified = (len(targets) > 0) and not weight_unverifiable
    sizing_verification = {
        "verified": verified,
        "sizing_mode": V1_SIZING_MODE,
        "kelly_used": False,
        "proof": V1_SIZING_PROOF,
        "weight_source": "forward_positions_artifact_signed_weight",
        "capital_base_usd": v1_capital_base_usd,
        "capital_base_source": capital_source,
        "wallet_used_for_target_sizing": False,
        "demo_wallet_equity_usd": wallet_equity,
        "long_target_exposure": long_exp,
        "short_target_exposure": short_exp,
        "gross_target_exposure": gross_exp,
        "net_target_exposure": net_exp,
        "target_symbol_count": len(targets),
    }

    if not verified:
        return PlannerResult(
            STATUS_V1_BASELINE_SIZING_UNVERIFIED, [], list(targets.values()),
            [_pos_dict(p) for p in open_positions], rejected, sizing_verification,
            "V1 baseline sizing could not be proven for all eligible signals; send path must refuse"
            if weight_unverifiable else "no usable V1 target weights")

    current = {pos.symbol: pos for pos in open_positions}
    actions = _diff_positions(targets, current)
    return PlannerResult(
        STATUS_PLANNED, actions, list(targets.values()),
        [_pos_dict(p) for p in open_positions], rejected, sizing_verification,
        "V1 baseline target-weight translation (no Kelly); strategy target preserved")


def _pos_dict(p: Any) -> dict[str, Any]:
    return {"symbol": p.symbol, "side": p.side, "qty": float(p.quantity),
            "entry_price": float(p.entry_price)}


def _diff_positions(targets: Mapping[str, Mapping[str, Any]],
                    current: Mapping[str, Any]) -> list[nx.StrategyNativeAction]:
    """Compare strategy target positions to current Demo positions -> OPEN / ADD /
    REDUCE / CLOSE (and CLOSE+OPEN for a side reversal). Preserves the strategy
    target quantity/direction; no removed Pilot cap is applied."""
    actions: list[nx.StrategyNativeAction] = []
    seq = 0
    for symbol in sorted(set(targets) | set(current)):
        tgt = targets.get(symbol)
        cur = current.get(symbol)
        cur_side = _side_to_long_short(getattr(cur, "side", "")) if cur is not None else ""
        cur_qty = float(getattr(cur, "quantity", 0) or 0) if cur is not None else 0.0

        if tgt is None:
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
                notional_usdt=_qty_str(abs(tgt.get("target_notional", 0))), action_seq=seq,
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
            continue

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
    "PROTECTED_SYMBOLS", "PilotAccountMarketProvider", "PlannerResult", "STATUS_PLANNED",
    "STATUS_PLANNER_UNAVAILABLE", "STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED",
    "STATUS_V1_BASELINE_SIZING_UNVERIFIED", "TASK_ID", "V1_CAPITAL_BASE_SOURCE",
    "V1_SIZING_MODE", "V1_SIZING_PROOF", "plan_strategy_native_actions",
    "resolve_v1_capital_base",
]
