"""TASK-014BY_FIX -- V1 baseline sizing alignment + parity tests.

Proves the active Demo V1 planner reproduces the frozen 30-day Forward V1 target
(equal-weight target weights, gross ~1.0, net ~0) via execution translation, NOT
0.4-Kelly. Offline; no network, no Bybit, no orders.
"""

from __future__ import annotations

import importlib
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import demo_strategy_pilot_action_planner as ap
from src import demo_portfolio_risk as risk
from src.demo_instrument_rules import InstrumentRules, round_qty_down
from src.demo_portfolio_risk import DemoOpenPosition

daily_cli = importlib.import_module("scripts.run_demo_strategy_pilot_native_daily")

EQUITY = 10_000.0


class FakeForward:
    def __init__(self, signals):
        self.normalized_signals = tuple(signals)


class FakeProvider:
    def __init__(self, *, equity=EQUITY, positions=None, prices=None, step=0.001):
        self._equity = equity
        self._positions = positions or []
        self._prices = prices or {}
        self._step = step

    def equity_usd(self): return self._equity
    def available_balance_usd(self): return self._equity
    def open_positions(self): return list(self._positions)
    def market_price(self, symbol): return self._prices.get(symbol, 100.0)

    def instrument_rule(self, symbol):
        return InstrumentRules(symbol=symbol, qty_step=self._step, min_qty=self._step, max_qty=0.0,
                               tick_size=0.0001, min_notional=5.0, price_precision=4, qty_precision=3)


class FakeTransport:
    def __init__(self):
        self.posts = []

    def post_order_create(self, *, url, body):
        self.posts.append((url, dict(body)))
        return {"retCode": 0, "result": {"orderId": "x", "orderLinkId": body["orderLinkId"]}}

    def reconcile(self, *, order_link_id):
        return {"retCode": 0, "result": {"list": [{"orderLinkId": order_link_id, "orderId": "x",
                                                   "orderStatus": "Filled", "cumExecQty": "1"}]}}


def eqw_signals():
    """25 long / 25 short, +/-0.02 target weights (the frozen V1 portfolio shape)."""
    sigs = []
    for i in range(25):
        sigs.append({"symbol": f"L{i}USDT", "side": "long", "score": 0.02})
        sigs.append({"symbol": f"S{i}USDT", "side": "short", "score": 0.02})
    return sigs


# --- Target-weight + exposure parity --------------------------------------


def test_target_weights_survive_unchanged_before_rounding():
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.0337},
                       {"symbol": "BBBUSDT", "side": "short", "score": 0.0125}])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider())
    tw = {t["symbol"]: t["target_weight"] for t in plan.target_positions}
    assert tw["AAAUSDT"] == pytest.approx(0.0337)
    assert tw["BBBUSDT"] == pytest.approx(-0.0125)  # signed: short is negative


def test_equal_weight_exposure_parity_25_long_25_short():
    plan = ap.plan_strategy_native_actions(forward_result=FakeForward(eqw_signals()),
                                           provider=FakeProvider())
    v = plan.sizing_verification
    assert v["long_target_exposure"] == pytest.approx(0.5, abs=1e-9)
    assert v["short_target_exposure"] == pytest.approx(-0.5, abs=1e-9)
    assert v["gross_target_exposure"] == pytest.approx(1.0, abs=1e-9)
    assert v["net_target_exposure"] == pytest.approx(0.0, abs=1e-9)
    assert v["verified"] is True and v["kelly_used"] is False


def test_quantity_is_weight_times_equity_over_price_rounded():
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}])
    prov = FakeProvider(prices={"AAAUSDT": 100.0}, step=0.001)
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=prov)
    # target_notional = 0.02 * 10000 = 200 ; raw qty = 200/100 = 2.0
    raw = (0.02 * EQUITY) / 100.0
    expected = round_qty_down(raw, 0.001)
    qty = float(plan.actions[0].qty)
    assert qty == pytest.approx(expected)
    # Drift from the unrounded target is strictly below one exchange step.
    assert abs(raw - qty) < 0.001


# --- Kelly is NOT used by the active V1 path -------------------------------


def test_active_v1_planner_does_not_call_kelly(monkeypatch):
    calls = {"n": 0}
    orig = risk.compute_demo_portfolio_sizing

    def spy(*a, **k):
        calls["n"] += 1
        return orig(*a, **k)

    monkeypatch.setattr(risk, "compute_demo_portfolio_sizing", spy)
    ap.plan_strategy_native_actions(forward_result=FakeForward(eqw_signals()), provider=FakeProvider())
    assert calls["n"] == 0  # active V1 path never invokes the Kelly sizer


def test_planner_module_does_not_import_kelly_sizer():
    src = (ROOT / "src" / "demo_strategy_pilot_action_planner.py").read_text("utf-8")
    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith(("import ", "from ")):
            assert "compute_demo_portfolio_sizing" not in s


# --- Position transitions --------------------------------------------------


def test_transition_open_add_reduce_close_reversal():
    # Targets: AAA long (open), BBB long bigger (add), CCC long smaller (reduce),
    # DDD held but not targeted (close), EEE flip short->long (reversal).
    positions = [
        DemoOpenPosition(symbol="BBBUSDT", side="long", quantity=1.0, entry_price=100.0, stop_price=95.0),
        DemoOpenPosition(symbol="CCCUSDT", side="long", quantity=5.0, entry_price=100.0, stop_price=95.0),
        DemoOpenPosition(symbol="DDDUSDT", side="long", quantity=2.0, entry_price=100.0, stop_price=95.0),
        DemoOpenPosition(symbol="EEEUSDT", side="short", quantity=2.0, entry_price=100.0, stop_price=105.0),
    ]
    prices = {s: 100.0 for s in ("AAAUSDT", "BBBUSDT", "CCCUSDT", "EEEUSDT")}
    sigs = [
        {"symbol": "AAAUSDT", "side": "long", "score": 0.02},   # notional 200/100 = 2.0 -> OPEN
        {"symbol": "BBBUSDT", "side": "long", "score": 0.03},   # 300/100 = 3.0 vs 1.0 -> ADD 2.0
        {"symbol": "CCCUSDT", "side": "long", "score": 0.02},   # 200/100 = 2.0 vs 5.0 -> REDUCE 3.0
        {"symbol": "EEEUSDT", "side": "long", "score": 0.02},   # held short -> CLOSE+OPEN
    ]
    plan = ap.plan_strategy_native_actions(
        forward_result=FakeForward(sigs), provider=FakeProvider(positions=positions, prices=prices))
    byintent = {(a.symbol, a.intent): a for a in plan.actions}
    assert ("AAAUSDT", "OPEN") in byintent
    assert ("BBBUSDT", "ADD") in byintent and float(byintent[("BBBUSDT", "ADD")].qty) == pytest.approx(2.0)
    assert ("CCCUSDT", "REDUCE") in byintent and byintent[("CCCUSDT", "REDUCE")].reduce_only is True
    assert ("DDDUSDT", "CLOSE") in byintent and byintent[("DDDUSDT", "CLOSE")].reduce_only is True
    # Reversal -> close current short then open long.
    assert ("EEEUSDT", "CLOSE") in byintent and ("EEEUSDT", "OPEN") in byintent


def test_multi_symbol_target_not_filtered_by_removed_caps():
    sigs = [{"symbol": f"X{i}USDT", "side": "long" if i % 2 else "short", "score": 0.05}
            for i in range(12)]  # 12 positions, large per-symbol notionals
    plan = ap.plan_strategy_native_actions(forward_result=FakeForward(sigs), provider=FakeProvider())
    assert len(plan.actions) == 12  # no 1-order / 1-position / 10-USDT cap applied


# --- Unverified -> send refused --------------------------------------------


def test_unverified_when_target_weight_missing():
    # Signals lacking score/weight cannot prove V1 sizing -> unverified, fail closed.
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long"}])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider())
    assert plan.status == ap.STATUS_V1_BASELINE_SIZING_UNVERIFIED
    assert plan.available is False
    assert plan.sizing_verification["verified"] is False


def test_orchestrator_refuses_send_when_unverified(tmp_path):
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long"}])  # no weight -> unverified
    t = FakeTransport()
    out = daily_cli.orchestrate_native_daily(
        pilot_id="BYBIT_DEMO_PILOT_7D_202606_V1", date="2026-06-22", forward_result=fwd,
        provider=FakeProvider(), transport=t, output_root=str(tmp_path / "out"))
    assert out["status"] == ap.STATUS_V1_BASELINE_SIZING_UNVERIFIED
    assert out["send_refused"] is True
    assert len(t.posts) == 0  # no order sent while sizing unverified


def test_send_exit_code_constant_exists():
    assert daily_cli.EXIT_V1_SIZING_UNVERIFIED == 7
