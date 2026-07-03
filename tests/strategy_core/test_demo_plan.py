"""TASK-DEMO-ORIG-001: tests for the original-strategy Demo PLAN-ONLY bridge.

These cover the 20 required proofs: original-strategy entry/exit authority,
family-specific stops, existing-position suppression, the non-FLIP re-entry
block, eligible FLIP, Kelly/position_size/stop reuse (never fixed weights),
strategy identity, Prev3Y rejection, live-endpoint fail-closed, plan-only order
isolation, instrument-rule blocked plan (no fallback qty), deterministic JSON,
and credential-free output.
"""
from __future__ import annotations

import json

import pytest

import src.strategy_core.demo_plan as dp
from src.demo_instrument_rules import InstrumentRules, round_qty_down
from src.risk import (
    calculate_stops,
    estimate_kelly_from_history,
    position_size,
)
from src.strategy_core.demo_plan import (
    STRATEGY_ID,
    DemoPlanError,
    OriginalStrategyDemoSymbolInput,
    PlanAction,
    build_demo_plan,
    build_symbol_demo_plan,
)

DECISION_TS = "2026-07-02T00:00:00Z"


def _rules(symbol="BTCUSDT", *, min_qty=0.001, min_notional=5.0, qty_step=0.001):
    return InstrumentRules(
        symbol=symbol, qty_step=qty_step, min_qty=min_qty, max_qty=0.0,
        tick_size=0.01, min_notional=min_notional,
        price_precision=2, qty_precision=3,
    )


def _inp(symbol="BTCUSDT", **kw):
    base = dict(
        symbol=symbol,
        signal_timestamp="2026-07-01",
        combined_signal=1,
        score=6,
        trend_signal=1,
        volume_profile_signal=0,
        bollinger_signal=0,
        minimum_score=3,
        symbol_tradable=True,
        reentry_blocked=False,
        symbol_winrate_ok=True,
        reference_price=100.0,
        atr=2.0,
        existing_position=0,
        existing_quantity=0.0,
        existing_stop_loss=0.0,
        existing_take_profit=0.0,
        min_hold_ok=True,
        early_exit=None,
        available_capital=100_000.0,
        max_position_pct=0.40,
        leverage=1.0,
        closed_trade_pnls=(),
        kelly_window=0,
        instrument_rules=_rules(symbol),
        geometric_rr_ok=True,
    )
    base.update(kw)
    return OriginalStrategyDemoSymbolInput(**base)


def _act(inp):
    return build_symbol_demo_plan(inp, decision_timestamp=DECISION_TS)


# 1 -------------------------------------------------------------------------
def test_trend_long_signal_creates_open_long():
    a = _act(_inp(combined_signal=1, trend_signal=1))
    assert a.action == PlanAction.OPEN_LONG.value
    assert a.direction == 1
    assert a.strategy_family == "trend"
    assert a.execution_allowed is True


# 2 -------------------------------------------------------------------------
def test_trend_short_signal_creates_open_short():
    a = _act(_inp(combined_signal=-1, trend_signal=-1))
    assert a.action == PlanAction.OPEN_SHORT.value
    assert a.direction == -1
    assert a.strategy_family == "trend"
    assert a.execution_allowed is True


# 3 -------------------------------------------------------------------------
def test_vp_family_preserves_family_and_family_specific_stops():
    a = _act(_inp(combined_signal=1, trend_signal=0, volume_profile_signal=1))
    assert a.strategy_family == "vp"
    exp_sl, exp_tp = calculate_stops(100.0, 1, 2.0, strategy="vp",
                                     asset_type="Crypto")
    assert a.stop_loss == exp_sl
    assert a.take_profit == exp_tp
    # vp stops must differ from trend stops (proves family-specific SL/TP)
    trend_sl, trend_tp = calculate_stops(100.0, 1, 2.0, strategy="trend",
                                         asset_type="Crypto")
    assert (exp_sl, exp_tp) != (trend_sl, trend_tp)


# 4 -------------------------------------------------------------------------
def test_bb_family_preserves_family_and_family_specific_stops():
    a = _act(_inp(combined_signal=1, trend_signal=0, bollinger_signal=1))
    assert a.strategy_family == "bb"
    exp_sl, exp_tp = calculate_stops(100.0, 1, 2.0, strategy="bb",
                                     asset_type="Crypto")
    assert a.stop_loss == exp_sl
    assert a.take_profit == exp_tp


# 5 -------------------------------------------------------------------------
def test_no_signal_produces_hold():
    a = _act(_inp(combined_signal=0, trend_signal=0))
    assert a.action == PlanAction.HOLD.value
    assert a.direction == 0
    assert a.execution_allowed is False
    assert a.reason_code == "NO_SIGNAL"


# 6 -------------------------------------------------------------------------
def test_existing_same_direction_position_produces_hold():
    # Long held, same-direction signal, price between SL/TP -> exit HOLD,
    # entry suppressed by EXISTING_POSITION.
    a = _act(_inp(combined_signal=1, existing_position=1, existing_quantity=1.0,
                  existing_stop_loss=90.0, existing_take_profit=130.0))
    assert a.action == PlanAction.HOLD.value
    assert a.reason_code == "EXISTING_POSITION"


# 7 -------------------------------------------------------------------------
def test_non_flip_reentry_block_produces_hold():
    a = _act(_inp(combined_signal=1, reentry_blocked=True))
    assert a.action == PlanAction.HOLD.value
    assert a.reason_code == "REENTRY_BLOCKED"


def test_same_bar_non_flip_close_blocks_reentry():
    # Long held; price hits SL (non-FLIP close). Same-bar re-entry must be
    # blocked -> action CLOSE, never re-opened.
    a = _act(_inp(combined_signal=1, existing_position=1, existing_quantity=2.0,
                  existing_stop_loss=101.0, existing_take_profit=130.0,
                  reference_price=100.0))
    assert a.action == PlanAction.CLOSE.value
    assert a.reason_code == "SL"


# 8 -------------------------------------------------------------------------
def test_eligible_flip_not_blocked_by_non_flip_reentry_rule():
    # Long held, opposite signal, min-hold met -> FLIP close then reverse entry.
    a = _act(_inp(combined_signal=-1, trend_signal=-1, existing_position=1,
                  existing_quantity=1.0, existing_stop_loss=90.0,
                  existing_take_profit=130.0, min_hold_ok=True))
    assert a.action == PlanAction.FLIP_LONG_TO_SHORT.value
    assert a.direction == -1
    assert a.reason_code == "FLIP"
    assert a.execution_allowed is True


def test_flip_short_to_long():
    a = _act(_inp(combined_signal=1, trend_signal=1, existing_position=-1,
                  existing_quantity=1.0, existing_stop_loss=110.0,
                  existing_take_profit=70.0, min_hold_ok=True))
    assert a.action == PlanAction.FLIP_SHORT_TO_LONG.value
    assert a.direction == 1


# 9 -------------------------------------------------------------------------
def test_shared_entry_core_is_the_entry_authority(monkeypatch):
    calls = []
    real = dp.decide_entry

    def spy(inp):
        calls.append(inp)
        return real(inp)

    monkeypatch.setattr(dp, "decide_entry", spy)
    a = _act(_inp(combined_signal=1, trend_signal=1))
    assert len(calls) == 1
    assert a.action == PlanAction.OPEN_LONG.value

    # Forcing the core to HOLD must flip the plan to HOLD (sole authority).
    from src.strategy_core.entry_decision import (
        EntryAction, EntryReasonCode, EntryDecisionResult)
    monkeypatch.setattr(dp, "decide_entry", lambda inp: EntryDecisionResult(
        EntryAction.HOLD, 0, inp.score, "trend",
        EntryReasonCode.SYMBOL_WINRATE_BLOCKED))
    a2 = _act(_inp(combined_signal=1, trend_signal=1))
    assert a2.action == PlanAction.HOLD.value


# 10 ------------------------------------------------------------------------
def test_shared_exit_core_used_for_open_positions(monkeypatch):
    calls = []
    real = dp.decide_exit

    def spy(inp):
        calls.append(inp)
        return real(inp)

    monkeypatch.setattr(dp, "decide_exit", spy)
    _act(_inp(combined_signal=1, existing_position=1, existing_quantity=1.0,
              existing_stop_loss=90.0, existing_take_profit=130.0))
    assert len(calls) == 1  # exit core consulted for the open position

    # Force CLOSE -> plan CLOSE.
    from src.strategy_core.exit_decision import ExitAction, ExitDecisionResult
    monkeypatch.setattr(dp, "decide_exit", lambda inp: ExitDecisionResult(
        ExitAction.CLOSE, "SL", True, False, False, False))
    a = _act(_inp(combined_signal=1, existing_position=1, existing_quantity=1.0,
                  existing_stop_loss=90.0, existing_take_profit=130.0))
    assert a.action == PlanAction.CLOSE.value


# 11 ------------------------------------------------------------------------
def test_kelly_sizing_and_stops_use_existing_functions(monkeypatch):
    seen = {"stops": 0, "kelly": 0, "size": 0}
    real_stops, real_kelly, real_size = (
        dp.calculate_stops, dp.estimate_kelly_from_history, dp.position_size)

    def stops_spy(*a, **k):
        seen["stops"] += 1
        return real_stops(*a, **k)

    def kelly_spy(*a, **k):
        seen["kelly"] += 1
        return real_kelly(*a, **k)

    def size_spy(*a, **k):
        seen["size"] += 1
        return real_size(*a, **k)

    monkeypatch.setattr(dp, "calculate_stops", stops_spy)
    monkeypatch.setattr(dp, "estimate_kelly_from_history", kelly_spy)
    monkeypatch.setattr(dp, "position_size", size_spy)

    a = _act(_inp(combined_signal=1, trend_signal=1))
    assert seen == {"stops": 1, "kelly": 1, "size": 1}

    # quantity is exactly position_size floored to qty_step (not a weight).
    sl, _tp = calculate_stops(100.0, 1, 2.0, strategy="trend", asset_type="Crypto")
    kf = estimate_kelly_from_history([], window=0, asset_type="Crypto")
    raw = position_size(100_000.0, kf, 100.0, sl, asset_type="Crypto",
                        max_position_pct=0.40)
    assert a.quantity == round_qty_down(raw, 0.001)
    assert a.quantity > 0


# 12 ------------------------------------------------------------------------
def test_no_prev3y_25_25_rule_but_configurable_limits_apply():
    # There is NO Prev3Y 25-long/25-short rule: quantities are sizing-derived,
    # never the fixed +/-0.02 weight / +/-200 USDT leg. The original strategy's
    # OWN configurable global cap still applies (here 15 of 60 eligible longs).
    inputs = [_inp(symbol=f"SY{i:02d}USDT", combined_signal=1, trend_signal=1)
              for i in range(60)]
    plan = build_demo_plan(inputs, decision_timestamp=DECISION_TS,
                           starting_available_capital=1e12,
                           max_total_positions=15)
    opened = [a for a in plan.actions if a.execution_allowed
              and a.open_quantity > 0]
    assert plan.projected_open_count == 15
    assert len(opened) == 15                       # global cap binds, not 25
    fixed_weight_qty = 0.02 * 100_000.0 / 100.0    # the Prev3Y assumption
    for a in opened:
        assert a.open_quantity != fixed_weight_qty
        assert a.notional_usdt != 200.0            # not the fixed +/-200 USDT leg


# 13 ------------------------------------------------------------------------
def test_strategy_id_is_original_shared_strategy_v1():
    assert STRATEGY_ID == "ORIGINAL_SHARED_STRATEGY_V1"
    plan = build_demo_plan([_inp()], decision_timestamp=DECISION_TS)
    assert plan.strategy_id == "ORIGINAL_SHARED_STRATEGY_V1"
    assert all(a.strategy_id == "ORIGINAL_SHARED_STRATEGY_V1"
               for a in plan.actions)


# 14 ------------------------------------------------------------------------
def test_prev3y_identity_rejected():
    for bad in ("prev3y_momentum", "prev3y", "STRATEGY_NATIVE_V1",
                "demo_strategy_native_v1"):
        with pytest.raises(DemoPlanError):
            build_demo_plan([_inp()], decision_timestamp=DECISION_TS,
                            strategy_id=bad)


def test_missing_identity_rejected():
    with pytest.raises(DemoPlanError):
        build_demo_plan([_inp()], decision_timestamp=DECISION_TS, strategy_id="")


# 15 ------------------------------------------------------------------------
def test_live_endpoint_selection_fails_closed():
    for live in ("https://api.bybit.com", "https://api.bybit.com/v5/order/create",
                 "wss://stream.bybit.com"):
        with pytest.raises(Exception):
            build_demo_plan([_inp()], decision_timestamp=DECISION_TS,
                            endpoint=live)


def test_non_demo_environment_fails_closed():
    with pytest.raises(Exception):
        build_demo_plan([_inp()], decision_timestamp=DECISION_TS,
                        environment="bybit_live")


# 16 ------------------------------------------------------------------------
def test_plan_only_cannot_invoke_order_functions():
    import inspect
    src = inspect.getsource(dp)
    forbidden = ("BybitExecutor", "place_order", "close_position",
                 "set_trading_stop", "cancel_order", "amend_order",
                 "order/create", "order/cancel", "import requests",
                 "import pybit", "urllib.request")
    for token in forbidden:
        assert token not in src, token
    assert not hasattr(dp, "place_order")
    assert not hasattr(dp, "close_position")


# 17 ------------------------------------------------------------------------
def test_missing_instrument_rule_creates_blocked_plan_no_fallback_qty():
    a = _act(_inp(combined_signal=1, trend_signal=1, instrument_rules=None))
    assert a.action == PlanAction.OPEN_LONG.value    # strategy still decided ENTER
    assert a.execution_allowed is False
    assert a.execution_block_reason == "missing_instrument_rule"
    assert a.quantity == 0.0                         # no fabricated fallback qty


def test_min_qty_failure_blocks_without_bumping_quantity():
    # Force a min_qty far above what sizing yields for a small allocation.
    a = _act(_inp(combined_signal=1, trend_signal=1, available_capital=100.0,
                  instrument_rules=_rules(min_qty=1_000_000.0)))
    assert a.action == PlanAction.OPEN_LONG.value
    assert a.execution_allowed is False
    assert a.execution_block_reason == "min_qty_after_rounding"
    assert a.quantity < 1_000_000.0                  # not bumped up to satisfy min


def test_protected_symbol_open_is_blocked():
    a = _act(_inp(symbol="ENAUSDT", combined_signal=1, trend_signal=1,
                  instrument_rules=_rules("ENAUSDT")))
    assert a.execution_allowed is False
    assert a.execution_block_reason == "protected_symbol"


# 18 ------------------------------------------------------------------------
def test_machine_readable_json_is_deterministic():
    inputs = [_inp(symbol="BTCUSDT"), _inp(symbol="ETHUSDT",
                                           combined_signal=-1, trend_signal=-1)]
    p1 = build_demo_plan(inputs, decision_timestamp=DECISION_TS)
    p2 = build_demo_plan(list(reversed(inputs)), decision_timestamp=DECISION_TS)
    j1 = json.dumps(p1.to_dict(), sort_keys=True, indent=2)
    j2 = json.dumps(p2.to_dict(), sort_keys=True, indent=2)
    assert j1 == j2                                  # order-independent + stable
    assert p1.plan_only is True
    assert p1.to_dict()["order_execution_authorized"] is False


# 19 ------------------------------------------------------------------------
def test_no_credentials_in_output():
    plan = build_demo_plan(
        [_inp(symbol="BTCUSDT"), _inp(symbol="ETHUSDT")],
        decision_timestamp=DECISION_TS)
    blob = json.dumps(plan.to_dict(), sort_keys=True).lower()
    for token in ("api_key", "apikey", "api-key", "secret", "signature",
                  "x-bapi", "passphrase", "bybit_api"):
        assert token not in blob, token


# ===========================================================================
# R1: plan-level portfolio arbitration (global/family caps, score order,
# shared capital, FLIP two-leg contract)
# ===========================================================================

_FAM_SIG = {"trend": (1, 0, 0), "vp": (0, 1, 0), "bb": (0, 0, 1)}


def _cand(symbol, *, score=6, family="trend", capital=100_000.0,
          rules=None, **kw):
    t, v, b = _FAM_SIG[family]
    return _inp(symbol=symbol, combined_signal=1, score=score,
                trend_signal=t, volume_profile_signal=v, bollinger_signal=b,
                available_capital=capital,
                instrument_rules=rules if rules is not None else _rules(symbol),
                **kw)


def _opened(plan):
    return [a for a in plan.actions if a.execution_allowed and a.open_quantity > 0]


# R1-1 -----------------------------------------------------------------------
def test_global_cap_limits_projected_opens():
    inputs = [_cand(f"S{i:02d}") for i in range(60)]
    plan = build_demo_plan(inputs, decision_timestamp=DECISION_TS,
                           starting_available_capital=1e12,
                           max_total_positions=15)
    assert plan.projected_open_count == 15
    assert len(_opened(plan)) == 15


# R1-2 -----------------------------------------------------------------------
def test_higher_score_wins_over_alphabetical_tiebreak():
    # "AAA" sorts first alphabetically but has the LOWER score; the higher-score
    # "ZZZ" must take the single available slot.
    inputs = [_cand("AAAUSDT", score=5), _cand("ZZZUSDT", score=7)]
    plan = build_demo_plan(inputs, decision_timestamp=DECISION_TS,
                           starting_available_capital=1e9,
                           max_total_positions=1)
    by = {a.symbol: a for a in plan.actions}
    assert by["ZZZUSDT"].execution_allowed is True
    assert by["ZZZUSDT"].open_quantity > 0
    assert by["AAAUSDT"].execution_allowed is False
    assert by["AAAUSDT"].reason_code == "POSITION_CAP_REACHED"


# R1-3 -----------------------------------------------------------------------
def test_global_cap_stops_later_allocation():
    inputs = [_cand(f"S{i}", score=6) for i in range(5)]
    plan = build_demo_plan(inputs, decision_timestamp=DECISION_TS,
                           starting_available_capital=1e9,
                           max_total_positions=2)
    assert plan.projected_open_count == 2
    blocked = [a for a in plan.actions if a.reason_code == "POSITION_CAP_REACHED"]
    assert len(blocked) == 3


# R1-4 -----------------------------------------------------------------------
def test_family_cap_blocks_only_that_family():
    # trend cap = 1: highest trend opens, second trend blocked, but a later VP
    # candidate still opens (different family, no global cap).
    inputs = [_cand("T1USDT", score=7, family="trend"),
              _cand("T2USDT", score=6, family="trend"),
              _cand("V1USDT", score=5, family="vp")]
    plan = build_demo_plan(inputs, decision_timestamp=DECISION_TS,
                           starting_available_capital=1e9,
                           max_total_positions=100,
                           max_positions_per_family={"trend": 1})
    by = {a.symbol: a for a in plan.actions}
    assert by["T1USDT"].execution_allowed is True
    assert by["T2USDT"].execution_allowed is False
    assert by["T2USDT"].reason_code == "POSITION_CAP_REACHED"
    assert by["V1USDT"].execution_allowed is True      # VP still allowed


# R1-5 -----------------------------------------------------------------------
def test_existing_hold_counts_toward_caps():
    held = _inp(symbol="HELDUSDT", combined_signal=1, existing_position=1,
                existing_quantity=1.0, existing_stop_loss=90.0,
                existing_take_profit=130.0, existing_strategy_family="trend")
    cand = _cand("NEWUSDT", score=7, family="trend")
    # global cap 1: the HELD position already fills it -> new candidate blocked.
    plan = build_demo_plan([held, cand], decision_timestamp=DECISION_TS,
                           starting_available_capital=1e9,
                           max_total_positions=1)
    by = {a.symbol: a for a in plan.actions}
    assert by["HELDUSDT"].action == "HOLD"
    assert by["NEWUSDT"].execution_allowed is False
    assert by["NEWUSDT"].reason_code == "POSITION_CAP_REACHED"
    assert plan.projected_open_count == 1
    # family cap: HELD trend fills trend:1 -> new trend candidate blocked.
    plan2 = build_demo_plan([held, cand], decision_timestamp=DECISION_TS,
                            starting_available_capital=1e9,
                            max_total_positions=100,
                            max_positions_per_family={"trend": 1})
    assert {a.symbol: a for a in plan2.actions}["NEWUSDT"].execution_allowed is False


# R1-6 -----------------------------------------------------------------------
def test_close_releases_projected_capacity():
    cand = _cand("NEWUSDT", score=7, family="trend")
    # Case A: HELD position holds the only slot -> candidate blocked.
    held = _inp(symbol="AUSDT", combined_signal=1, existing_position=1,
                existing_quantity=1.0, existing_stop_loss=90.0,
                existing_take_profit=130.0, existing_strategy_family="trend")
    plan_held = build_demo_plan([held, cand], decision_timestamp=DECISION_TS,
                                starting_available_capital=1e9,
                                max_total_positions=1)
    assert {a.symbol: a for a in plan_held.actions}["NEWUSDT"].execution_allowed is False
    # Case B: same position now CLOSEs (price hits SL) -> slot freed, candidate opens.
    closing = _inp(symbol="AUSDT", combined_signal=1, existing_position=1,
                   existing_quantity=1.0, existing_stop_loss=101.0,
                   existing_take_profit=130.0, reference_price=100.0,
                   existing_strategy_family="trend")
    plan_close = build_demo_plan([closing, cand], decision_timestamp=DECISION_TS,
                                 starting_available_capital=1e9,
                                 max_total_positions=1)
    by = {a.symbol: a for a in plan_close.actions}
    assert by["AUSDT"].action == "CLOSE"
    assert by["NEWUSDT"].execution_allowed is True     # capacity released


# R1-7 -----------------------------------------------------------------------
def test_each_accepted_entry_reduces_shared_capital():
    inputs = [_cand("AUSDT"), _cand("BUSDT"), _cand("CUSDT")]
    plan = build_demo_plan(inputs, decision_timestamp=DECISION_TS,
                           starting_available_capital=100_000.0,
                           max_total_positions=10)
    assert plan.projected_remaining_capital < plan.starting_available_capital
    consumed = sum(a.projected_margin for a in _opened(plan))
    assert plan.projected_total_margin == pytest.approx(consumed)
    assert plan.projected_remaining_capital == pytest.approx(
        plan.starting_available_capital - consumed)


# R1-8 -----------------------------------------------------------------------
def test_later_entries_size_from_reduced_capital():
    # Same score/family -> symbol order A,B,C; each sizes from shrinking capital
    # (pos-cap binds at max_position_pct), so quantities strictly decrease.
    inputs = [_cand(s, score=6, family="trend") for s in
              ("AUSDT", "BUSDT", "CUSDT")]
    plan = build_demo_plan(inputs, decision_timestamp=DECISION_TS,
                           starting_available_capital=100_000.0,
                           max_total_positions=10)
    by = {a.symbol: a for a in plan.actions}
    qa, qb, qc = (by["AUSDT"].open_quantity, by["BUSDT"].open_quantity,
                  by["CUSDT"].open_quantity)
    assert qa > qb > qc > 0            # later entries smaller (reduced capital)


# R1-9 -----------------------------------------------------------------------
def test_total_projected_margin_never_exceeds_starting_capital():
    inputs = [_cand(f"S{i}") for i in range(20)]
    plan = build_demo_plan(inputs, decision_timestamp=DECISION_TS,
                           starting_available_capital=50_000.0,
                           max_total_positions=15)
    assert plan.projected_total_margin <= plan.starting_available_capital + 1e-6
    assert plan.projected_remaining_capital >= -1e-6


# R1-10 ----------------------------------------------------------------------
def test_blocked_candidate_consumes_no_capital():
    # A higher-score min-qty-blocked candidate is processed FIRST but consumes
    # nothing; the feasible candidate then sizes from the FULL starting capital.
    blocked = _cand("BADUSDT", score=7, rules=_rules("BADUSDT", min_qty=1e12))
    good = _cand("GOODUSDT", score=6)
    start = 100_000.0
    plan = build_demo_plan([blocked, good], decision_timestamp=DECISION_TS,
                           starting_available_capital=start,
                           max_total_positions=10)
    by = {a.symbol: a for a in plan.actions}
    assert by["BADUSDT"].execution_allowed is False
    assert by["BADUSDT"].projected_margin == 0.0
    assert by["BADUSDT"].execution_block_reason == "min_qty_after_rounding"
    # feasible one sized from full capital (blocked consumed nothing)
    sl, _tp = calculate_stops(100.0, 1, 2.0, strategy="trend", asset_type="Crypto")
    kf = estimate_kelly_from_history([], window=0, asset_type="Crypto")
    exp_qty = round_qty_down(position_size(start, kf, 100.0, sl,
                                           asset_type="Crypto",
                                           max_position_pct=0.40), 0.001)
    assert by["GOODUSDT"].open_quantity == exp_qty
    assert plan.projected_remaining_capital == pytest.approx(
        start - by["GOODUSDT"].projected_margin)


# R1-11 / R1-12 / R1-13 / R1-14 : FLIP two-leg contract -----------------------
def _flip_action(existing_qty=3.0):
    inp = _inp(combined_signal=-1, trend_signal=-1, existing_position=1,
               existing_quantity=existing_qty, existing_stop_loss=90.0,
               existing_take_profit=130.0, min_hold_ok=True)
    return build_symbol_demo_plan(inp, decision_timestamp=DECISION_TS), inp


def test_flip_has_distinct_close_and_open_quantities():
    a, _ = _flip_action(existing_qty=3.0)
    assert a.action == PlanAction.FLIP_LONG_TO_SHORT.value
    assert a.close_quantity == 3.0
    assert a.open_quantity > 0
    assert a.close_quantity != a.open_quantity       # never assumed equal


def test_flip_execution_sequence_is_close_then_open():
    a, _ = _flip_action()
    assert list(a.execution_sequence) == ["CLOSE", "OPEN"]
    assert a.close_direction == 1
    assert a.open_direction == -1


def test_flip_close_quantity_equals_existing_position_quantity():
    for q in (1.5, 3.0, 7.25):
        a, _ = _flip_action(existing_qty=q)
        assert a.close_quantity == q


def test_flip_open_quantity_independently_kelly_sized():
    a, inp = _flip_action(existing_qty=3.0)
    sl, _tp = calculate_stops(100.0, -1, 2.0, strategy="trend",
                              asset_type="Crypto")
    kf = estimate_kelly_from_history([], window=0, asset_type="Crypto")
    exp = round_qty_down(position_size(inp.available_capital, kf, 100.0, sl,
                                       asset_type="Crypto",
                                       max_position_pct=0.40), 0.001)
    assert a.open_quantity == exp


# R1-15 ----------------------------------------------------------------------
def test_non_flip_close_remains_close_only():
    a = _act(_inp(combined_signal=1, existing_position=1, existing_quantity=2.0,
                  existing_stop_loss=101.0, existing_take_profit=130.0,
                  reference_price=100.0))
    assert a.action == PlanAction.CLOSE.value
    assert list(a.execution_sequence) == ["CLOSE"]
    assert a.open_quantity == 0.0
    assert a.close_quantity == 2.0


# ---------------------------------------------------------------------------
# CLI-level fail-closed guards (return before any DB / market-data access)
# ---------------------------------------------------------------------------


class _Args:
    def __init__(self, **kw):
        defaults = dict(
            seed=42, capital=0.0, output=None, positions_json=None,
            instrument_rules_json=None, endpoint=None, environment=None,
            max_staleness_days=5, live=False,
        )
        defaults.update(kw)
        self.__dict__.update(defaults)


def test_cli_live_flag_fails_closed():
    import main
    assert main.cmd_demo_plan(_Args(live=True)) == 2


def test_cli_live_endpoint_fails_closed():
    import main
    assert main.cmd_demo_plan(
        _Args(endpoint="https://api.bybit.com/v5/order/create")) == 2


def test_cli_non_demo_environment_fails_closed():
    import main
    assert main.cmd_demo_plan(_Args(environment="bybit_live")) == 2


def test_cli_malformed_positions_file_fails_closed(tmp_path):
    import main
    bad = tmp_path / "positions.json"
    bad.write_text("[not an object]", encoding="utf-8")
    assert main.cmd_demo_plan(_Args(positions_json=str(bad))) == 2


def test_cli_malformed_rules_file_fails_closed(tmp_path):
    import main
    bad = tmp_path / "rules.json"
    bad.write_text("\"not an object\"", encoding="utf-8")
    assert main.cmd_demo_plan(_Args(instrument_rules_json=str(bad))) == 2
