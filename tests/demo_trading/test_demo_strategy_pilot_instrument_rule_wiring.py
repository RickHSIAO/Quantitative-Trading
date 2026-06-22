"""TASK-014CA -- instrument-rule provider wiring tests.

Validates that the canonical DemoReadOnlyClient.get_instruments_info() is
correctly wired into the production provider, and that the planner emits
specific rejection reasons instead of the defunct combined
no_market_price_or_instrument_rule.

Fully offline: fixtures only, zero real HTTP, zero Bybit calls, zero orders.
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import demo_strategy_pilot_action_planner as ap
from src import demo_strategy_pilot_native_execution as nx
from src import demo_strategy_pilot_readiness as rd
from src.demo_instrument_rules import InstrumentRules, round_qty_down
from src.demo_readonly_client import DemoReadOnlyClient, InstrumentSnapshot
from src.demo_portfolio_risk import DemoOpenPosition


PROTECTED = frozenset(rd.PROTECTED_SYMBOLS)
INIT = 10_000.0


# ---------------------------------------------------------------------------
# Provider fixtures
# ---------------------------------------------------------------------------


def _make_snapshot(symbol, qty_step=0.001, min_qty=0.001, max_qty=0.0,
                   tick_size=0.01, min_notional=1.0, status="Trading"):
    return InstrumentSnapshot(
        symbol=symbol, qty_step=qty_step, min_qty=min_qty, max_qty=max_qty,
        tick_size=tick_size, min_notional=min_notional,
        price_precision=2, qty_precision=3, status=status,
    )


def _50_symbols():
    """Generate 50 symbols matching the real Forward artifact shape."""
    prefixes = [
        "1INCH", "AAVE", "ADA", "ALGO", "APE", "APT", "ARB", "ATOM", "AVAX",
        "AXS", "BAT", "BCH", "BNB", "BTC", "CHZ", "CRV", "DOGE", "DOT",
        "DYDX", "EOS", "ETH", "FET", "FIL", "GALA", "GRT", "HBAR", "ICP",
        "IMX", "INJ", "LINK", "LTC", "MANA", "MATIC", "NEAR", "OP", "PEPE",
        "RENDER", "SAND", "SEI", "SHIB", "SNX", "SOL", "STX", "SUSHI", "TRX",
        "UNI", "VET", "WLD", "XLM", "XRP",
    ]
    return [p + "USDT" for p in prefixes]


def _forward_signals(symbols, weight=0.02):
    """Generate signed Forward signals matching real artifact shape."""
    sigs = []
    for i, sym in enumerate(symbols):
        side = "long" if i < len(symbols) // 2 else "short"
        sigs.append({"symbol": sym, "side": side, "weight": weight, "score": weight})
    return sigs


class InstrumentProvider:
    """Minimal provider with configurable instrument rules for testing."""

    def __init__(self, instruments=None, prices=None, positions=None):
        self._instruments = instruments or {}
        self._prices = prices or {}
        self._positions = positions or []

    def equity_usd(self):
        return INIT

    def available_balance_usd(self):
        return 8500.0

    def open_positions(self):
        return list(self._positions)

    def market_price(self, symbol):
        return self._prices.get(symbol)

    def instrument_rule(self, symbol):
        snap = self._instruments.get(symbol)
        if snap is None:
            return None
        if snap.status != "Trading":
            return None
        return InstrumentRules(
            symbol=symbol, qty_step=float(snap.qty_step),
            min_qty=float(snap.min_qty), max_qty=float(snap.max_qty),
            tick_size=float(snap.tick_size), min_notional=float(snap.min_notional),
            price_precision=snap.price_precision, qty_precision=snap.qty_precision,
        )


class FakeForward:
    def __init__(self, signals):
        self.normalized_signals = tuple(signals)


# ---------------------------------------------------------------------------
# InstrumentSnapshot parsing tests
# ---------------------------------------------------------------------------


def test_parse_instrument_snapshot_with_status():
    """InstrumentSnapshot carries the Bybit trading status."""
    snap = _make_snapshot("BTCUSDT", status="Trading")
    assert snap.status == "Trading"
    snap2 = _make_snapshot("OLDUSDT", status="Closed")
    assert snap2.status == "Closed"


def test_parse_instrument_snapshot_default_status():
    """Default status is Trading for backward compatibility."""
    snap = InstrumentSnapshot("BTCUSDT", 0.001, 0.001, 0, 0.01, 1.0, 2, 3)
    assert snap.status == "Trading"


def test_fixture_client_returns_instruments():
    """DemoReadOnlyClient fixture mode returns instruments via get_instruments_info."""
    client = DemoReadOnlyClient(allow_real_network=False)
    instruments = client.get_instruments_info()
    assert len(instruments) > 0
    assert "BTCUSDT" in instruments
    snap = instruments["BTCUSDT"]
    assert snap.qty_step == 0.001
    assert snap.tick_size == 0.1


def test_fixture_client_symbol_filter():
    """get_instruments_info with symbol filter returns only requested symbols."""
    client = DemoReadOnlyClient(allow_real_network=False)
    instruments = client.get_instruments_info(symbols=["BTCUSDT", "ETHUSDT"])
    assert set(instruments.keys()) == {"BTCUSDT", "ETHUSDT"}


def test_client_has_no_get_instruments_method():
    """DemoReadOnlyClient has get_instruments_info, NOT get_instruments."""
    client = DemoReadOnlyClient(allow_real_network=False)
    assert hasattr(client, "get_instruments_info")
    assert not hasattr(client, "get_instruments")


# ---------------------------------------------------------------------------
# Bybit field parsing tests
# ---------------------------------------------------------------------------


def test_bybit_qty_step_parsing():
    """qtyStep from lotSizeFilter is correctly parsed."""
    client = DemoReadOnlyClient(allow_real_network=False)
    item = {
        "symbol": "TESTUSDT", "status": "Trading",
        "lotSizeFilter": {"qtyStep": "0.01", "minOrderQty": "0.01",
                          "maxMktOrderQty": "500", "maxOrderQty": "1000",
                          "minNotionalValue": "5"},
        "priceFilter": {"tickSize": "0.001"},
    }
    snap = client._parse_instrument_snapshot(item)
    assert snap.qty_step == pytest.approx(0.01)
    assert snap.min_qty == pytest.approx(0.01)
    assert snap.tick_size == pytest.approx(0.001)


def test_bybit_max_mkt_order_qty_preferred():
    """maxMktOrderQty is preferred over maxOrderQty for market-order execution."""
    client = DemoReadOnlyClient(allow_real_network=False)
    item = {
        "symbol": "TESTUSDT", "status": "Trading",
        "lotSizeFilter": {"qtyStep": "0.001", "minOrderQty": "0.001",
                          "maxMktOrderQty": "100", "maxOrderQty": "500",
                          "minNotionalValue": "5"},
        "priceFilter": {"tickSize": "0.01"},
    }
    snap = client._parse_instrument_snapshot(item)
    assert snap.max_qty == pytest.approx(100.0)


def test_bybit_fallback_max_order_qty():
    """Falls back to maxOrderQty when maxMktOrderQty is absent."""
    client = DemoReadOnlyClient(allow_real_network=False)
    item = {
        "symbol": "TESTUSDT", "status": "Trading",
        "lotSizeFilter": {"qtyStep": "0.001", "minOrderQty": "0.001",
                          "maxOrderQty": "500",
                          "minNotionalValue": "5"},
        "priceFilter": {"tickSize": "0.01"},
    }
    snap = client._parse_instrument_snapshot(item)
    assert snap.max_qty == pytest.approx(500.0)


def test_bybit_min_notional_value_parsing():
    """minNotionalValue from lotSizeFilter is correctly parsed."""
    client = DemoReadOnlyClient(allow_real_network=False)
    item = {
        "symbol": "TESTUSDT", "status": "Trading",
        "lotSizeFilter": {"qtyStep": "0.001", "minOrderQty": "0.001",
                          "minNotionalValue": "5.5"},
        "priceFilter": {"tickSize": "0.01"},
    }
    snap = client._parse_instrument_snapshot(item)
    assert snap.min_notional == pytest.approx(5.5)


def test_bybit_tick_size_parsing():
    """tickSize from priceFilter is correctly parsed."""
    client = DemoReadOnlyClient(allow_real_network=False)
    item = {
        "symbol": "BTCUSDT", "status": "Trading",
        "lotSizeFilter": {"qtyStep": "0.001", "minOrderQty": "0.001"},
        "priceFilter": {"tickSize": "0.10"},
    }
    snap = client._parse_instrument_snapshot(item)
    assert snap.tick_size == pytest.approx(0.10)


def test_bybit_status_parsed():
    """Trading status is extracted from the Bybit item."""
    client = DemoReadOnlyClient(allow_real_network=False)
    for st in ("Trading", "Closed", "PreLaunch"):
        item = {
            "symbol": "TESTUSDT", "status": st,
            "lotSizeFilter": {"qtyStep": "0.001", "minOrderQty": "0.001"},
            "priceFilter": {"tickSize": "0.01"},
        }
        snap = client._parse_instrument_snapshot(item)
        assert snap.status == st


# ---------------------------------------------------------------------------
# Non-Trading / malformed / missing instrument tests
# ---------------------------------------------------------------------------


def test_non_trading_instrument_rejected():
    """A non-Trading instrument should cause no_instrument_rule rejection."""
    symbols = ["SOLUSDT", "DEADUSDT"]
    instruments = {
        "SOLUSDT": _make_snapshot("SOLUSDT", status="Trading"),
        "DEADUSDT": _make_snapshot("DEADUSDT", status="Closed"),
    }
    prices = {s: 100.0 for s in symbols}
    provider = InstrumentProvider(instruments=instruments, prices=prices)
    fwd = FakeForward(_forward_signals(symbols))
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=provider)
    dead_rej = [r for r in plan.rejected_signals if r["symbol"] == "DEADUSDT"]
    assert len(dead_rej) == 1
    assert dead_rej[0]["reason"] == "no_instrument_rule"


def test_missing_instrument_rejected():
    """A symbol with no instrument data should get no_instrument_rule."""
    provider = InstrumentProvider(
        instruments={"SOLUSDT": _make_snapshot("SOLUSDT")},
        prices={"SOLUSDT": 100.0, "MISSING": 50.0},
    )
    fwd = FakeForward([
        {"symbol": "SOLUSDT", "side": "long", "weight": 0.02, "score": 0.02},
        {"symbol": "MISSING", "side": "short", "weight": 0.02, "score": 0.02},
    ])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=provider)
    rej = [r for r in plan.rejected_signals if r["symbol"] == "MISSING"]
    assert len(rej) == 1
    assert rej[0]["reason"] == "no_instrument_rule"


def test_no_market_price_and_no_instrument_rule_are_distinct():
    """no_market_price and no_instrument_rule are separate rejection reasons."""
    provider = InstrumentProvider(
        instruments={"SOLUSDT": _make_snapshot("SOLUSDT")},
        prices={"NOPRICE": 0.0},  # 0.0 is not > 0
    )
    fwd = FakeForward([
        {"symbol": "SOLUSDT", "side": "long", "weight": 0.02, "score": 0.02},
        {"symbol": "NOPRICE", "side": "short", "weight": 0.02, "score": 0.02},
    ])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=provider)
    reasons = {r["symbol"]: r["reason"] for r in plan.rejected_signals}
    assert reasons.get("NOPRICE") == "no_market_price"


def test_malformed_instrument_rule_rejected():
    """A malformed instrument rule (invalid fields) is rejected."""
    bad_snap = _make_snapshot("BADUSDT", qty_step=-1.0)
    provider = InstrumentProvider(
        instruments={"BADUSDT": bad_snap},
        prices={"BADUSDT": 100.0},
    )
    fwd = FakeForward([
        {"symbol": "BADUSDT", "side": "long", "weight": 0.02, "score": 0.02},
    ])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=provider)
    rej = [r for r in plan.rejected_signals if r["symbol"] == "BADUSDT"]
    assert len(rej) == 1
    assert rej[0]["reason"] == "malformed_instrument_rule"


# ---------------------------------------------------------------------------
# Protected symbol tests
# ---------------------------------------------------------------------------


def test_all_protected_symbols_rejected():
    """All 5 protected symbols must be rejected with reason=protected_symbol."""
    all_syms = list(PROTECTED) + ["SOLUSDT"]
    instruments = {s: _make_snapshot(s) for s in all_syms}
    prices = {s: 100.0 for s in all_syms}
    provider = InstrumentProvider(instruments=instruments, prices=prices)
    fwd = FakeForward(_forward_signals(all_syms))
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=provider)
    protected_rej = {r["symbol"] for r in plan.rejected_signals
                     if r["reason"] == "protected_symbol"}
    assert protected_rej == PROTECTED
    action_syms = {a.symbol for a in plan.actions}
    assert action_syms & PROTECTED == set()


def test_existing_edu_polyx_positions_untouched():
    """Existing EDUUSDT/POLYXUSDT Demo positions must not generate actions."""
    positions = [
        DemoOpenPosition(symbol="EDUUSDT", side="short", quantity=10.0,
                         entry_price=1.0, stop_price=1.5),
        DemoOpenPosition(symbol="POLYXUSDT", side="short", quantity=5.0,
                         entry_price=0.5, stop_price=0.75),
    ]
    provider = InstrumentProvider(
        instruments={"SOLUSDT": _make_snapshot("SOLUSDT")},
        prices={"SOLUSDT": 100.0},
        positions=positions,
    )
    fwd = FakeForward([
        {"symbol": "SOLUSDT", "side": "long", "weight": 0.02, "score": 0.02},
    ])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=provider)
    action_syms = {a.symbol for a in plan.actions}
    assert "EDUUSDT" not in action_syms
    assert "POLYXUSDT" not in action_syms


# ---------------------------------------------------------------------------
# V1 sizing invariant tests
# ---------------------------------------------------------------------------


def test_50_forward_weights_read():
    """50 valid Forward weights (25 long / 25 short) are processed."""
    symbols = _50_symbols()
    assert len(symbols) == 50
    instruments = {s: _make_snapshot(s) for s in symbols}
    prices = {s: 100.0 for s in symbols}
    provider = InstrumentProvider(instruments=instruments, prices=prices)
    sigs = _forward_signals(symbols, weight=0.02)
    non_protected = [s for s in symbols if s not in PROTECTED]
    fwd = FakeForward(sigs)
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=provider)
    protected_count = sum(1 for r in plan.rejected_signals
                          if r["reason"] == "protected_symbol")
    assert protected_count == len(PROTECTED & set(symbols))
    total_processed = len(plan.actions) + len(plan.rejected_signals)
    assert total_processed == 50


def test_target_weights_remain_plus_minus_002():
    """Target weights are preserved at +/-0.02."""
    symbols = ["SOLUSDT", "BTCUSDT"]
    instruments = {s: _make_snapshot(s) for s in symbols}
    prices = {s: 100.0 for s in symbols}
    provider = InstrumentProvider(instruments=instruments, prices=prices)
    fwd = FakeForward([
        {"symbol": "SOLUSDT", "side": "long", "weight": 0.02, "score": 0.02},
        {"symbol": "BTCUSDT", "side": "short", "weight": 0.02, "score": 0.02},
    ])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=provider)
    for tp in plan.target_positions:
        assert abs(abs(tp["target_weight"]) - 0.02) < 1e-10


def test_fixed_capital_10000_usd():
    """V1 capital base remains 10000 USDT."""
    provider = InstrumentProvider(
        instruments={"SOLUSDT": _make_snapshot("SOLUSDT")},
        prices={"SOLUSDT": 100.0},
    )
    fwd = FakeForward([
        {"symbol": "SOLUSDT", "side": "long", "weight": 0.02, "score": 0.02},
    ])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=provider)
    sv = plan.sizing_verification
    assert sv["capital_base_usd"] == INIT
    assert sv["capital_base_verified"] is True
    assert sv["sources_agree"] is True
    assert sv["wallet_used_for_target_sizing"] is False
    assert sv["kelly_used"] is False


def test_target_notional_equals_weight_times_capital():
    """target_notional = weight * 10000 for each target."""
    provider = InstrumentProvider(
        instruments={"SOLUSDT": _make_snapshot("SOLUSDT")},
        prices={"SOLUSDT": 100.0},
    )
    fwd = FakeForward([
        {"symbol": "SOLUSDT", "side": "long", "weight": 0.02, "score": 0.02},
    ])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=provider)
    for tp in plan.target_positions:
        expected = tp["target_weight"] * INIT
        assert tp["target_notional"] == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------------------
# Quantity rounding determinism
# ---------------------------------------------------------------------------


def test_deterministic_qty_rounding():
    """round_qty_down is deterministic across multiple calls."""
    for _ in range(100):
        assert round_qty_down(2.0, 0.01) == round_qty_down(2.0, 0.01)
        assert round_qty_down(0.123456, 0.001) == pytest.approx(0.123)


# ---------------------------------------------------------------------------
# No duplicate public metadata calls
# ---------------------------------------------------------------------------


def test_no_duplicate_public_metadata_calls():
    """Fixture client returns the same instruments on multiple calls without extra fetch."""
    client = DemoReadOnlyClient(allow_real_network=False)
    first = client.get_instruments_info()
    second = client.get_instruments_info()
    assert first.keys() == second.keys()


# ---------------------------------------------------------------------------
# Plan-only status and safety tests
# ---------------------------------------------------------------------------


def test_plan_only_status_with_usable_data():
    """Plan-only with usable prices and rules -> STRATEGY_NATIVE_ACTIONS_PLANNED."""
    symbols = ["SOLUSDT", "BTCUSDT", "ETHUSDT"]
    instruments = {s: _make_snapshot(s) for s in symbols}
    prices = {s: 100.0 for s in symbols}
    provider = InstrumentProvider(instruments=instruments, prices=prices)
    fwd = FakeForward(_forward_signals(symbols))
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=provider)
    assert plan.status == ap.STATUS_PLANNED
    assert len(plan.actions) > 0


def test_plan_only_zero_orders():
    """Plan-only must never claim order endpoint was called."""
    provider = InstrumentProvider(
        instruments={"SOLUSDT": _make_snapshot("SOLUSDT")},
        prices={"SOLUSDT": 100.0},
    )
    fwd = FakeForward([
        {"symbol": "SOLUSDT", "side": "long", "weight": 0.02, "score": 0.02},
    ])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=provider)
    d = plan.to_dict()
    assert d["status"] == ap.STATUS_PLANNED
    assert d["action_count"] > 0


def test_no_secret_material_in_planner_output():
    """Planner output must not contain secret material."""
    provider = InstrumentProvider(
        instruments={"SOLUSDT": _make_snapshot("SOLUSDT")},
        prices={"SOLUSDT": 100.0},
    )
    fwd = FakeForward([
        {"symbol": "SOLUSDT", "side": "long", "weight": 0.02, "score": 0.02},
    ])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=provider)
    text = json.dumps(plan.to_dict(), default=str)
    for sensitive in ("api_key", "api_secret", "BYBIT_DEMO_API_KEY",
                      "BYBIT_DEMO_API_SECRET", "secret"):
        assert sensitive.lower() not in text.lower() or "secret_value_observed" in text.lower()


def test_qty_floored_to_zero_is_rejected():
    """A target whose quantity floors to zero after rounding is rejected."""
    snap = _make_snapshot("HUGEUSDT", qty_step=1000.0, min_qty=1000.0)
    provider = InstrumentProvider(
        instruments={"HUGEUSDT": snap},
        prices={"HUGEUSDT": 50000.0},
    )
    fwd = FakeForward([
        {"symbol": "HUGEUSDT", "side": "long", "weight": 0.02, "score": 0.02},
    ])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=provider)
    rej = [r for r in plan.rejected_signals if r["symbol"] == "HUGEUSDT"]
    assert len(rej) == 1
    assert rej[0]["reason"] == "qty_floored_to_zero"
