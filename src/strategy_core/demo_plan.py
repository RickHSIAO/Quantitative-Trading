"""TASK-DEMO-ORIG-001: original-strategy Demo plan bridge (PLAN-ONLY).

Pure, deterministic bridge that turns the ORIGINAL main.py strategy decision
(the Supertrend/trend + Volume-Profile + Bollinger families, score threshold,
Kelly / original Live sizing, family-specific SL/TP, existing-position
suppression, re-entry block, FLIP) into a Bybit **Demo** execution PLAN. It
produces a plan action per symbol and NEVER places, amends, cancels or closes an
order.

Reuse, not re-implementation
----------------------------
The strategy *rules* are the already-extracted shared cores; this module imports
and calls them as the sole decision authority -- it copies none of their logic:

  * entry ENTER/HOLD + reason + family : ``strategy_core.entry_decision.decide_entry``
  * exit  HOLD/CLOSE + close reason     : ``strategy_core.exit_decision.decide_exit``
  * family-specific SL / TP             : ``src.risk.calculate_stops``
  * 1/4 Kelly fraction                  : ``src.risk.estimate_kelly_from_history``
  * original Live position sizing       : ``src.risk.position_size``
  * qty-step floor / min-qty / min-notional : ``src.demo_instrument_rules``
  * demo-only environment / live-endpoint denial / protected symbols :
    ``src.demo_only_tiny_execution_adapter`` (BH guard primitives)

It invents NO Prev3Y cross-sectional weight, no fixed +/-0.02 weight, no 25L/25S
split and no frozen 10,000 NAV -- quantity comes only from ``position_size``.

Single-symbol action resolution (mirrors main.cmd_live's per-symbol sequence:
exit arbitration first, then staged entry arbitration on the same signal bar):

  * existing flat + entry ENTER            -> OPEN_LONG / OPEN_SHORT
  * existing flat + entry HOLD             -> HOLD
  * existing pos  + exit HOLD              -> HOLD (position kept; entry suppressed)
  * existing pos  + exit CLOSE(non-FLIP)   -> CLOSE   (same-bar re-entry blocked, as Live)
  * existing pos  + exit CLOSE(FLIP) + reverse ENTER
                                           -> FLIP_LONG_TO_SHORT / FLIP_SHORT_TO_LONG
  * existing pos  + exit CLOSE(FLIP) + reverse HOLD -> CLOSE

``execution_allowed`` is a PLAN-level feasibility flag for a later authorized
Demo execution task; it is True only when every downstream Demo guard passes
(demo endpoint/env at plan level, symbol not protected, instrument rules present
and satisfied AFTER floor-to-qty-step, margin sufficient, live entry filter ok).
A guard failure yields a BLOCKED plan action with an explicit
``execution_block_reason`` and the true (never a fabricated fallback) quantity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence

from src import demo_only_tiny_execution_adapter as bh
from src.demo_instrument_rules import (
    InstrumentRules,
    round_qty_down,
    validate_min_notional,
    validate_min_qty,
)
from src.risk import (
    calculate_stops,
    estimate_kelly_from_history,
    position_size,
)
from src.strategy_core.entry_decision import (
    EntryAction,
    EntryDecisionInput,
    decide_entry,
)
from src.strategy_core.exit_decision import (
    CLOSE_REASON_FLIP,
    ExitAction,
    ExitDecisionInput,
    decide_exit,
)

# ---------------------------------------------------------------------------
# Identity / contract constants
# ---------------------------------------------------------------------------

STRATEGY_ID = "ORIGINAL_SHARED_STRATEGY_V1"
PLAN_CONTRACT_VERSION = "original_strategy_demo_plan_v1"
ASSET_CLASS = "Crypto"

# Demo-only execution target (positive allowlist). The live endpoints are
# permanently denied via the BH live denylist below.
DEMO_ENVIRONMENT = bh.ALLOWED_ENVIRONMENT       # "bybit_demo"
DEMO_ENDPOINT = "https://api-demo.bybit.com"

# Strategy identities that are NOT the original strategy and must fail closed if
# supplied as the plan's strategy source (the invalid Prev3Y cross-sectional /
# native-V1 lineage: ranking, 25L/25S, fixed +/-0.02 weights, frozen 10k NAV).
REJECTED_STRATEGY_IDS: frozenset[str] = frozenset({
    "prev3y",
    "prev3y_momentum",
    "prev3y_crypto",
    "STRATEGY_NATIVE_V1",
    "strategy_native_v1",
    "demo_strategy_native_v1",
    "demo_strategy_pilot",
})


class PlanAction(str, Enum):
    """The six deterministic plan actions."""

    HOLD = "HOLD"
    OPEN_LONG = "OPEN_LONG"
    OPEN_SHORT = "OPEN_SHORT"
    CLOSE = "CLOSE"
    FLIP_LONG_TO_SHORT = "FLIP_LONG_TO_SHORT"
    FLIP_SHORT_TO_LONG = "FLIP_SHORT_TO_LONG"


# Execution block-reason constants (empty string = execution allowed).
BLOCK_NONE = ""
BLOCK_NO_ACTION = "no_actionable_order"
BLOCK_PROTECTED_SYMBOL = "protected_symbol"
BLOCK_MISSING_INSTRUMENT_RULE = "missing_instrument_rule"
BLOCK_INVALID_RULES = "invalid_instrument_rules"
BLOCK_ZERO_QTY = "zero_qty_after_sizing"
BLOCK_MIN_QTY = "min_qty_after_rounding"
BLOCK_MIN_NOTIONAL = "min_notional_after_rounding"
BLOCK_INSUFFICIENT_MARGIN = "insufficient_margin"
BLOCK_GEOMETRIC_RR = "geometric_rr_rejected"


class DemoPlanError(Exception):
    """Raised when the plan bridge fails closed (identity / endpoint / env)."""


# ---------------------------------------------------------------------------
# Fail-closed guards (identity + demo execution target)
# ---------------------------------------------------------------------------


def assert_original_strategy_identity(strategy_id: str) -> None:
    """Fail closed unless ``strategy_id`` is exactly the original-strategy id.

    Rejects a missing identity and any Prev3Y / native-V1 identity supplied as
    the original-strategy source (never infers equivalence from a filename).
    """
    if not strategy_id or not str(strategy_id).strip():
        raise DemoPlanError("strategy identity is missing")
    sid = str(strategy_id).strip()
    if sid in REJECTED_STRATEGY_IDS or "prev3y" in sid.lower():
        raise DemoPlanError(
            f"strategy identity {sid!r} is the invalid Prev3Y/native source; "
            f"the original strategy id is {STRATEGY_ID!r}"
        )
    if sid != STRATEGY_ID:
        raise DemoPlanError(
            f"strategy identity {sid!r} is not {STRATEGY_ID!r}; rejected"
        )


def assert_demo_execution_target(*, environment: str, endpoint: str) -> None:
    """Fail closed unless the target is the demo environment + demo endpoint.

    Reuses the BH environment guard and the BH live-endpoint denylist so a live
    endpoint (``api.bybit.com`` / ``stream.bybit.com`` / ...) is permanently
    denied, then requires a positive match on the demo endpoint host.
    """
    bh.assert_environment_is_demo(environment)      # raises for non bybit_demo
    bh.assert_endpoint_is_demo_only(endpoint)       # raises LiveEndpointDenied
    if not str(endpoint).startswith(DEMO_ENDPOINT):
        raise DemoPlanError(
            f"endpoint {endpoint!r} is not the demo endpoint {DEMO_ENDPOINT!r}"
        )


# ---------------------------------------------------------------------------
# Input / output contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OriginalStrategyDemoSymbolInput:
    """Fully-resolved per-symbol scalars for one plan cycle.

    Every field is already computed by the caller (closed-bar signals,
    reference price, ATR, position state, sizing context, instrument rules).
    This module reads nothing else -- no signal generation, no I/O, no network.
    """

    symbol: str
    signal_timestamp: str
    combined_signal: int
    score: int
    trend_signal: int
    volume_profile_signal: int
    bollinger_signal: int
    minimum_score: int
    symbol_tradable: bool
    reentry_blocked: bool
    symbol_winrate_ok: bool
    reference_price: float
    atr: float
    # existing position (0 = flat, +1 long, -1 short)
    existing_position: int = 0
    existing_quantity: float = 0.0
    existing_stop_loss: float = 0.0
    existing_take_profit: float = 0.0
    existing_strategy_family: str = "combined"   # family a HELD position occupies
    min_hold_ok: bool = True
    early_exit: Optional[str] = None
    # sizing context (reused by src.risk functions -- never fixed weights)
    available_capital: float = 0.0
    max_position_pct: float = 0.0
    leverage: float = 1.0
    closed_trade_pnls: tuple[float, ...] = ()
    kelly_window: int = 0
    # downstream Demo guards
    instrument_rules: Optional[InstrumentRules] = None
    geometric_rr_ok: bool = True


@dataclass(frozen=True)
class OriginalStrategyDemoPlanAction:
    """One deterministic plan action. Never triggers an order by itself.

    A FLIP is an unambiguous two-leg plan: the CLOSE leg uses the exact existing
    position quantity; the OPEN leg uses a freshly Kelly/instrument-sized reverse
    quantity. ``execution_sequence`` is ("CLOSE",) / ("OPEN",) / ("CLOSE","OPEN")
    / () for CLOSE / OPEN / FLIP / HOLD respectively.
    """

    strategy_id: str
    decision_timestamp: str
    signal_timestamp: str
    symbol: str
    action: str
    direction: int
    strategy_family: str
    score: int
    reason_code: str
    reference_price: float
    quantity: float
    notional_usdt: float
    stop_loss: float
    take_profit: float
    reentry_blocked: bool
    existing_position: int
    execution_allowed: bool
    execution_block_reason: str
    # unambiguous two-leg fields (FLIP never assumes close_qty == open_qty)
    close_quantity: float = 0.0
    close_direction: int = 0
    open_quantity: float = 0.0
    open_direction: int = 0
    execution_sequence: tuple[str, ...] = ()
    projected_margin: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "decision_timestamp": self.decision_timestamp,
            "signal_timestamp": self.signal_timestamp,
            "symbol": self.symbol,
            "action": self.action,
            "direction": self.direction,
            "strategy_family": self.strategy_family,
            "score": self.score,
            "reason_code": self.reason_code,
            "reference_price": self.reference_price,
            "quantity": self.quantity,
            "notional_usdt": self.notional_usdt,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "reentry_blocked": self.reentry_blocked,
            "existing_position": self.existing_position,
            "execution_allowed": self.execution_allowed,
            "execution_block_reason": self.execution_block_reason,
            "close_quantity": self.close_quantity,
            "close_direction": self.close_direction,
            "open_quantity": self.open_quantity,
            "open_direction": self.open_direction,
            "execution_sequence": list(self.execution_sequence),
            "projected_margin": self.projected_margin,
        }


@dataclass(frozen=True)
class OriginalStrategyDemoPlan:
    """A PLAN-ONLY collection of per-symbol actions plus its safety + portfolio
    arbitration envelope (global/family caps + shared-cycle-capital accounting).
    """

    strategy_id: str
    plan_only: bool
    plan_contract_version: str
    environment: str
    endpoint: str
    decision_timestamp: str
    max_total_positions: Optional[int]
    max_positions_per_family: dict[str, int]
    starting_available_capital: float
    projected_remaining_capital: float
    projected_total_margin: float
    projected_total_notional: float
    projected_open_count: int
    actions: tuple[OriginalStrategyDemoPlanAction, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        actionable = tuple(
            a for a in self.actions if a.action != PlanAction.HOLD.value
        )
        return {
            "strategy_id": self.strategy_id,
            "plan_only": self.plan_only,
            "plan_contract_version": self.plan_contract_version,
            "environment": self.environment,
            "endpoint": self.endpoint,
            "decision_timestamp": self.decision_timestamp,
            "order_execution_authorized": False,
            "max_total_positions": self.max_total_positions,
            "max_positions_per_family": dict(sorted(
                self.max_positions_per_family.items())),
            "starting_available_capital": self.starting_available_capital,
            "projected_remaining_capital": self.projected_remaining_capital,
            "projected_total_margin": self.projected_total_margin,
            "projected_total_notional": self.projected_total_notional,
            "projected_open_count": self.projected_open_count,
            "total_symbols": len(self.actions),
            "actionable_count": len(actionable),
            "execution_allowed_count": sum(
                1 for a in self.actions if a.execution_allowed
            ),
            "actions": [a.to_dict() for a in self.actions],
        }


# ---------------------------------------------------------------------------
# Sizing / execution-feasibility helpers (pure)
# ---------------------------------------------------------------------------


class _PnlStub:
    """Minimal closed-trade record for estimate_kelly_from_history (.pnl only)."""

    __slots__ = ("pnl",)

    def __init__(self, pnl: float) -> None:
        self.pnl = pnl


def _resolve_open_execution(
    *,
    symbol: str,
    raw_qty: float,
    price: float,
    rules: Optional[InstrumentRules],
    leverage: float,
    available: float,
    geometric_rr_ok: bool,
) -> tuple[bool, str, float, float, float]:
    """Feasibility of an OPEN/FLIP entry through every downstream Demo guard.

    Returns ``(execution_allowed, block_reason, quantity, notional, margin)``.
    On any instrument-rule failure the plan is BLOCKED and the true rounded
    quantity is reported -- never a fabricated fallback quantity.
    """
    lev = leverage if leverage and leverage > 0 else 1.0
    if symbol in bh.PROTECTED_SYMBOLS:
        return False, BLOCK_PROTECTED_SYMBOL, 0.0, 0.0, 0.0
    if rules is None:
        return False, BLOCK_MISSING_INSTRUMENT_RULE, 0.0, 0.0, 0.0
    ok, _err = rules.is_valid()
    if not ok:
        return False, BLOCK_INVALID_RULES, 0.0, 0.0, 0.0

    rounded = round_qty_down(raw_qty, rules.qty_step)
    notional = rounded * price if price > 0 else 0.0
    margin = notional / lev
    if rounded <= 0:
        return False, BLOCK_ZERO_QTY, rounded, notional, 0.0

    qty_ok, _ = validate_min_qty(rounded, rules.min_qty)
    if not qty_ok:
        return False, BLOCK_MIN_QTY, rounded, notional, 0.0
    notional_ok, _ = validate_min_notional(notional, rules.min_notional)
    if not notional_ok:
        return False, BLOCK_MIN_NOTIONAL, rounded, notional, 0.0

    if margin > max(0.0, available):
        return False, BLOCK_INSUFFICIENT_MARGIN, rounded, notional, 0.0
    if not geometric_rr_ok:
        return False, BLOCK_GEOMETRIC_RR, rounded, notional, 0.0

    return True, BLOCK_NONE, rounded, notional, margin


def _resolve_close_execution(symbol: str, quantity: float) -> tuple[bool, str]:
    if symbol in bh.PROTECTED_SYMBOLS:
        return False, BLOCK_PROTECTED_SYMBOL
    if quantity <= 0:
        return False, BLOCK_ZERO_QTY
    return True, BLOCK_NONE


def _size_entry(inp: "OriginalStrategyDemoSymbolInput", entry_dir: int,
                family: str, available: float) -> tuple[float, float, float]:
    """Original-strategy sizing for one entry leg. Returns (raw_qty, sl, tp)."""
    sl, tp = calculate_stops(
        float(inp.reference_price), entry_dir, float(inp.atr),
        strategy=family, asset_type=ASSET_CLASS,
    )
    kelly_frac = estimate_kelly_from_history(
        [_PnlStub(p) for p in inp.closed_trade_pnls],
        window=int(inp.kelly_window), asset_type=ASSET_CLASS,
    )
    raw_qty = position_size(
        max(0.0, float(available)), kelly_frac,
        float(inp.reference_price), sl,
        asset_type=ASSET_CLASS, max_position_pct=float(inp.max_position_pct),
    )
    return raw_qty, sl, tp


# ---------------------------------------------------------------------------
# Core: single-symbol plan action
# ---------------------------------------------------------------------------


def build_symbol_demo_plan(
    inp: OriginalStrategyDemoSymbolInput,
    *,
    decision_timestamp: str,
    strategy_id: str = STRATEGY_ID,
    available_capital: Optional[float] = None,
    position_cap_reached: bool = False,
) -> OriginalStrategyDemoPlanAction:
    """Resolve the single deterministic plan action for one symbol.

    The shared entry/exit cores are the sole ENTER/HOLD/CLOSE authority; sizing
    and stops come only from the original ``src.risk`` functions.
    ``position_cap_reached`` is the commit-stage portfolio-cap verdict computed
    by :func:`build_demo_plan`; ``available_capital`` overrides the per-symbol
    field with the plan's shared remaining cycle capital.
    """
    eff_capital = (float(inp.available_capital) if available_capital is None
                   else float(available_capital))
    existing = int(inp.existing_position)

    # --- Exit arbitration (only when a position is open) --------------------
    exit_close = False
    exit_reason: Optional[str] = None
    if existing in (1, -1):
        exit_res = decide_exit(ExitDecisionInput(
            symbol=inp.symbol,
            direction=existing,
            current_price=float(inp.reference_price),
            stop_loss=float(inp.existing_stop_loss),
            take_profit=float(inp.existing_take_profit),
            combined_signal=int(inp.combined_signal),
            min_hold_ok=bool(inp.min_hold_ok),
            early_exit=inp.early_exit,
        ))
        exit_close = exit_res.action is ExitAction.CLOSE
        exit_reason = exit_res.close_reason

    # --- Entry arbitration (shared core is the authority) -------------------
    # Mirror main.cmd_live: a same-bar CLOSE removes the position (entry sees no
    # open position), and a NON-FLIP close blocks re-entry on this signal bar
    # while a FLIP close does not. The commit-stage portfolio cap is fed in as
    # position_cap_reached so decide_entry stays the sole ENTER/HOLD authority.
    entry_has_open = existing in (1, -1) and not exit_close
    if exit_close and exit_reason != CLOSE_REASON_FLIP:
        entry_reentry_blocked = True
    else:
        entry_reentry_blocked = bool(inp.reentry_blocked)

    entry_res = decide_entry(EntryDecisionInput(
        symbol=inp.symbol,
        asset_class=ASSET_CLASS,
        combined_signal=int(inp.combined_signal),
        score=int(inp.score),
        trend_signal=int(inp.trend_signal),
        volume_profile_signal=int(inp.volume_profile_signal),
        bollinger_signal=int(inp.bollinger_signal),
        minimum_score=int(inp.minimum_score),
        symbol_tradable=bool(inp.symbol_tradable),
        has_open_position=entry_has_open,
        reentry_blocked=entry_reentry_blocked,
        symbol_winrate_ok=bool(inp.symbol_winrate_ok),
        position_cap_reached=bool(position_cap_reached),
    ))
    entering = entry_res.action is EntryAction.ENTER
    entry_dir = int(entry_res.direction)
    family = entry_res.strategy_family

    # --- Resolve the single action -----------------------------------------
    if exit_close and entering and entry_dir == -existing:
        action = (PlanAction.FLIP_LONG_TO_SHORT if existing == 1
                  else PlanAction.FLIP_SHORT_TO_LONG)
        act_dir = entry_dir
        reason_code = exit_reason or CLOSE_REASON_FLIP
        kind = "FLIP"
    elif exit_close:
        action = PlanAction.CLOSE
        act_dir = 0
        reason_code = exit_reason or ""
        kind = "CLOSE"
    elif entering:
        action = (PlanAction.OPEN_LONG if entry_dir == 1
                  else PlanAction.OPEN_SHORT)
        act_dir = entry_dir
        reason_code = entry_res.reason_code.value
        kind = "OPEN"
    else:
        action = PlanAction.HOLD
        act_dir = 0
        reason_code = entry_res.reason_code.value
        kind = "HOLD"

    # --- Sizing / execution feasibility + unambiguous two legs --------------
    quantity = 0.0
    notional = 0.0
    stop_loss = 0.0
    take_profit = 0.0
    close_quantity = 0.0
    close_direction = 0
    open_quantity = 0.0
    open_direction = 0
    execution_sequence: tuple[str, ...] = ()
    projected_margin = 0.0

    if kind in ("OPEN", "FLIP"):
        raw_qty, stop_loss, take_profit = _size_entry(
            inp, entry_dir, family, eff_capital)
        open_allowed, open_reason, open_qty, open_notional, open_margin = (
            _resolve_open_execution(
                symbol=inp.symbol, raw_qty=raw_qty,
                price=float(inp.reference_price), rules=inp.instrument_rules,
                leverage=float(inp.leverage), available=eff_capital,
                geometric_rr_ok=bool(inp.geometric_rr_ok)))
        open_quantity = open_qty
        open_direction = entry_dir
        quantity = open_qty
        notional = open_notional

        if kind == "FLIP":
            close_quantity = abs(float(inp.existing_quantity))
            close_direction = existing
            execution_sequence = ("CLOSE", "OPEN")
            close_allowed, close_reason = _resolve_close_execution(
                inp.symbol, close_quantity)
            execution_allowed = open_allowed and close_allowed
            if not open_allowed:
                block_reason = open_reason
            elif not close_allowed:
                block_reason = close_reason
            else:
                block_reason = BLOCK_NONE
        else:  # OPEN
            execution_sequence = ("OPEN",)
            execution_allowed = open_allowed
            block_reason = open_reason

        projected_margin = open_margin if execution_allowed else 0.0

    elif kind == "CLOSE":
        close_quantity = abs(float(inp.existing_quantity))
        close_direction = existing
        quantity = close_quantity
        notional = close_quantity * float(inp.reference_price)
        stop_loss = float(inp.existing_stop_loss)
        take_profit = float(inp.existing_take_profit)
        execution_sequence = ("CLOSE",)
        execution_allowed, block_reason = _resolve_close_execution(
            inp.symbol, close_quantity)
    else:  # HOLD
        execution_allowed = False
        block_reason = BLOCK_NO_ACTION

    return OriginalStrategyDemoPlanAction(
        strategy_id=strategy_id,
        decision_timestamp=decision_timestamp,
        signal_timestamp=inp.signal_timestamp,
        symbol=inp.symbol,
        action=action.value,
        direction=act_dir,
        strategy_family=family,
        score=int(inp.score),
        reason_code=reason_code,
        reference_price=float(inp.reference_price),
        quantity=quantity,
        notional_usdt=notional,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reentry_blocked=bool(inp.reentry_blocked),
        existing_position=existing,
        execution_allowed=execution_allowed,
        execution_block_reason=block_reason,
        close_quantity=close_quantity,
        close_direction=close_direction,
        open_quantity=open_quantity,
        open_direction=open_direction,
        execution_sequence=execution_sequence,
        projected_margin=projected_margin,
    )


# ---------------------------------------------------------------------------
# Plan-level portfolio arbitration (mirrors main.cmd_live's two phases)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Resolution:
    """Pre-commit classification of one symbol (uses the shared cores only)."""

    symbol: str
    kind: str          # HELD / CLOSE / FLIP_CAND / OPEN_CAND / HOLD
    family: str
    direction: int
    score: int


def _classify(inp: OriginalStrategyDemoSymbolInput) -> _Resolution:
    """Pre-cap classification, mirroring build_symbol_demo_plan's action logic
    with ``position_cap_reached=False`` (so candidates are known before the
    commit loop assigns caps and shared capital)."""
    existing = int(inp.existing_position)
    exit_close = False
    exit_reason: Optional[str] = None
    if existing in (1, -1):
        exit_res = decide_exit(ExitDecisionInput(
            symbol=inp.symbol, direction=existing,
            current_price=float(inp.reference_price),
            stop_loss=float(inp.existing_stop_loss),
            take_profit=float(inp.existing_take_profit),
            combined_signal=int(inp.combined_signal),
            min_hold_ok=bool(inp.min_hold_ok), early_exit=inp.early_exit))
        exit_close = exit_res.action is ExitAction.CLOSE
        exit_reason = exit_res.close_reason

    entry_has_open = existing in (1, -1) and not exit_close
    if exit_close and exit_reason != CLOSE_REASON_FLIP:
        entry_reentry_blocked = True
    else:
        entry_reentry_blocked = bool(inp.reentry_blocked)

    entry_res = decide_entry(EntryDecisionInput(
        symbol=inp.symbol, asset_class=ASSET_CLASS,
        combined_signal=int(inp.combined_signal), score=int(inp.score),
        trend_signal=int(inp.trend_signal),
        volume_profile_signal=int(inp.volume_profile_signal),
        bollinger_signal=int(inp.bollinger_signal),
        minimum_score=int(inp.minimum_score),
        symbol_tradable=bool(inp.symbol_tradable),
        has_open_position=entry_has_open,
        reentry_blocked=entry_reentry_blocked,
        symbol_winrate_ok=bool(inp.symbol_winrate_ok),
        position_cap_reached=False))
    entering = entry_res.action is EntryAction.ENTER
    entry_dir = int(entry_res.direction)
    family = entry_res.strategy_family

    if exit_close and entering and entry_dir == -existing:
        return _Resolution(inp.symbol, "FLIP_CAND", family, entry_dir,
                           int(inp.score))
    if exit_close:
        return _Resolution(inp.symbol, "CLOSE", family, 0, int(inp.score))
    if entering:
        return _Resolution(inp.symbol, "OPEN_CAND", family, entry_dir,
                           int(inp.score))
    if existing in (1, -1):
        return _Resolution(inp.symbol, "HELD", inp.existing_strategy_family,
                           existing, int(inp.score))
    return _Resolution(inp.symbol, "HOLD", family, 0, int(inp.score))


def build_demo_plan(
    inputs: Sequence[OriginalStrategyDemoSymbolInput],
    *,
    decision_timestamp: str,
    strategy_id: str = STRATEGY_ID,
    environment: str = DEMO_ENVIRONMENT,
    endpoint: str = DEMO_ENDPOINT,
    starting_available_capital: Optional[float] = None,
    max_total_positions: Optional[int] = None,
    max_positions_per_family: Optional[dict] = None,
) -> OriginalStrategyDemoPlan:
    """Build a PLAN-ONLY plan with plan-level portfolio arbitration.

    Fails closed on a missing/Prev3Y identity or a non-demo execution target.
    Then, mirroring main.cmd_live:

      * Phase 1 -- resolve exits; HELD positions keep their global + family slot,
        CLOSE / FLIP free the existing slot. Entry candidates are the flat-ENTER
        symbols plus FLIP reverse entries.
      * Candidates are ordered by score DESC then symbol ASC.
      * Phase 2 (commit) -- each candidate is gated by the real
        ``position_cap_reached`` (global cap OR family cap) via ``decide_entry``,
        and sized from ONE shared remaining cycle capital; an accepted, feasible
        entry consumes a slot, a family slot and ``notional/leverage`` margin.
        Cap-blocked / instrument-blocked / margin-blocked candidates consume
        neither a slot nor capital.
    """
    assert_original_strategy_identity(strategy_id)
    assert_demo_execution_target(environment=environment, endpoint=endpoint)

    fam_caps = dict(max_positions_per_family or {})
    inp_list = list(inputs)
    if starting_available_capital is None:
        starting_available_capital = max(
            (float(i.available_capital) for i in inp_list), default=0.0)

    resolutions = {i.symbol: _classify(i) for i in inp_list}
    inp_by_symbol = {i.symbol: i for i in inp_list}

    # Phase 1: projected state from positions that remain open (HELD only).
    projected_open = sum(1 for r in resolutions.values() if r.kind == "HELD")
    family_counts: dict = {}
    for r in resolutions.values():
        if r.kind == "HELD":
            family_counts[r.family] = family_counts.get(r.family, 0) + 1

    # Candidate ordering: score DESC, symbol ASC.
    candidate_symbols = sorted(
        [s for s, r in resolutions.items()
         if r.kind in ("OPEN_CAND", "FLIP_CAND")],
        key=lambda s: (-resolutions[s].score, s),
    )

    actions: dict = {}

    # Non-candidates (HELD / CLOSE / HOLD) -- capital-independent.
    for sym, r in resolutions.items():
        if r.kind in ("OPEN_CAND", "FLIP_CAND"):
            continue
        actions[sym] = build_symbol_demo_plan(
            inp_by_symbol[sym], decision_timestamp=decision_timestamp,
            strategy_id=strategy_id,
            available_capital=starting_available_capital,
            position_cap_reached=False)

    # Phase 2 commit loop over score-ordered candidates with shared capital.
    cycle_capital = float(starting_available_capital)
    total_margin = 0.0
    total_notional = 0.0
    for sym in candidate_symbols:
        r = resolutions[sym]
        global_reached = (max_total_positions is not None
                          and projected_open >= int(max_total_positions))
        fam_limit = fam_caps.get(r.family)
        family_reached = (fam_limit is not None
                          and family_counts.get(r.family, 0) >= fam_limit)
        cap_reached = global_reached or family_reached

        act = build_symbol_demo_plan(
            inp_by_symbol[sym], decision_timestamp=decision_timestamp,
            strategy_id=strategy_id, available_capital=cycle_capital,
            position_cap_reached=cap_reached)
        actions[sym] = act

        # A committed, feasible entry consumes a slot, a family slot and margin.
        if act.open_quantity > 0 and act.execution_allowed:
            projected_open += 1
            family_counts[r.family] = family_counts.get(r.family, 0) + 1
            total_margin += act.projected_margin
            total_notional += act.notional_usdt
            cycle_capital = max(0.0, cycle_capital - act.projected_margin)

    ordered = tuple(actions[s] for s in sorted(actions))
    return OriginalStrategyDemoPlan(
        strategy_id=strategy_id,
        plan_only=True,
        plan_contract_version=PLAN_CONTRACT_VERSION,
        environment=environment,
        endpoint=endpoint,
        decision_timestamp=decision_timestamp,
        max_total_positions=max_total_positions,
        max_positions_per_family=fam_caps,
        starting_available_capital=float(starting_available_capital),
        projected_remaining_capital=cycle_capital,
        projected_total_margin=total_margin,
        projected_total_notional=total_notional,
        projected_open_count=projected_open,
        actions=ordered,
    )


__all__ = [
    "ASSET_CLASS",
    "BLOCK_GEOMETRIC_RR",
    "BLOCK_INSUFFICIENT_MARGIN",
    "BLOCK_INVALID_RULES",
    "BLOCK_MIN_NOTIONAL",
    "BLOCK_MIN_QTY",
    "BLOCK_MISSING_INSTRUMENT_RULE",
    "BLOCK_NONE",
    "BLOCK_NO_ACTION",
    "BLOCK_PROTECTED_SYMBOL",
    "BLOCK_ZERO_QTY",
    "DEMO_ENDPOINT",
    "DEMO_ENVIRONMENT",
    "DemoPlanError",
    "OriginalStrategyDemoPlan",
    "OriginalStrategyDemoPlanAction",
    "OriginalStrategyDemoSymbolInput",
    "PLAN_CONTRACT_VERSION",
    "PlanAction",
    "REJECTED_STRATEGY_IDS",
    "STRATEGY_ID",
    "assert_demo_execution_target",
    "assert_original_strategy_identity",
    "build_demo_plan",
    "build_symbol_demo_plan",
]
