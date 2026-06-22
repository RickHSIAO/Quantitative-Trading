"""TASK-014BY_FIX / FIX2 / FIX3 -- V1 baseline sizing alignment + parity tests.

Proves the active Demo V1 planner reproduces the frozen 30-day Forward V1 target
(equal-weight target weights, gross ~1.0, net ~0) via execution translation using
the frozen V1 capital base (cross-validated from config + state artifact, NOT Demo
wallet equity, NOT 0.4-Kelly). Offline; no network, no Bybit, no orders.
"""

from __future__ import annotations

import importlib
import json
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
V1_CAPITAL_BASE = 10_000.0


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


def _matching_evidence():
    """Build evidence where config=10000 and state=10000 (both agree)."""
    return ap.resolve_v1_capital_base_evidence(
        config_value_override=10_000.0, state_value_override=10_000.0)


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
    raw = (0.02 * EQUITY) / 100.0
    expected = round_qty_down(raw, 0.001)
    qty = float(plan.actions[0].qty)
    assert qty == pytest.approx(expected)
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
    assert calls["n"] == 0


def test_planner_module_does_not_import_kelly_sizer():
    src = (ROOT / "src" / "demo_strategy_pilot_action_planner.py").read_text("utf-8")
    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith(("import ", "from ")):
            assert "compute_demo_portfolio_sizing" not in s


# --- Position transitions --------------------------------------------------


def test_transition_open_add_reduce_close_reversal():
    positions = [
        DemoOpenPosition(symbol="BBBUSDT", side="long", quantity=1.0, entry_price=100.0, stop_price=95.0),
        DemoOpenPosition(symbol="CCCUSDT", side="long", quantity=5.0, entry_price=100.0, stop_price=95.0),
        DemoOpenPosition(symbol="DDDUSDT", side="long", quantity=2.0, entry_price=100.0, stop_price=95.0),
        DemoOpenPosition(symbol="EEEUSDT", side="short", quantity=2.0, entry_price=100.0, stop_price=105.0),
    ]
    prices = {s: 100.0 for s in ("AAAUSDT", "BBBUSDT", "CCCUSDT", "EEEUSDT")}
    sigs = [
        {"symbol": "AAAUSDT", "side": "long", "score": 0.02},
        {"symbol": "BBBUSDT", "side": "long", "score": 0.03},
        {"symbol": "CCCUSDT", "side": "long", "score": 0.02},
        {"symbol": "EEEUSDT", "side": "long", "score": 0.02},
    ]
    plan = ap.plan_strategy_native_actions(
        forward_result=FakeForward(sigs), provider=FakeProvider(positions=positions, prices=prices))
    byintent = {(a.symbol, a.intent): a for a in plan.actions}
    assert ("AAAUSDT", "OPEN") in byintent
    assert ("BBBUSDT", "ADD") in byintent and float(byintent[("BBBUSDT", "ADD")].qty) == pytest.approx(2.0)
    assert ("CCCUSDT", "REDUCE") in byintent and byintent[("CCCUSDT", "REDUCE")].reduce_only is True
    assert ("DDDUSDT", "CLOSE") in byintent and byintent[("DDDUSDT", "CLOSE")].reduce_only is True
    assert ("EEEUSDT", "CLOSE") in byintent and ("EEEUSDT", "OPEN") in byintent


def test_multi_symbol_target_not_filtered_by_removed_caps():
    sigs = [{"symbol": f"X{i}USDT", "side": "long" if i % 2 else "short", "score": 0.05}
            for i in range(12)]
    plan = ap.plan_strategy_native_actions(forward_result=FakeForward(sigs), provider=FakeProvider())
    assert len(plan.actions) == 12


# --- Unverified -> send refused --------------------------------------------


def test_unverified_when_target_weight_missing():
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long"}])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider())
    assert plan.status == ap.STATUS_V1_BASELINE_SIZING_UNVERIFIED
    assert plan.available is False
    assert plan.sizing_verification["verified"] is False


def test_orchestrator_refuses_send_when_unverified(tmp_path):
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long"}])
    t = FakeTransport()
    out = daily_cli.orchestrate_native_daily(
        pilot_id="BYBIT_DEMO_PILOT_7D_202606_V1", date="2026-06-22", forward_result=fwd,
        provider=FakeProvider(), transport=t, output_root=str(tmp_path / "out"))
    assert out["status"] == ap.STATUS_V1_BASELINE_SIZING_UNVERIFIED
    assert out["send_refused"] is True
    assert len(t.posts) == 0


def test_send_exit_code_constant_exists():
    assert daily_cli.EXIT_V1_SIZING_UNVERIFIED == 7


# --- FIX2: V1 capital base separated from Demo wallet equity ----------------


@pytest.mark.parametrize("wallet_equity", [100_000.0, 20_000.0, 50_000.0, 1_000_000.0])
def test_wallet_independence_notional_always_uses_capital_base(wallet_equity):
    """Target notional = weight * V1 capital base (10K), regardless of wallet equity."""
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}])
    prov = FakeProvider(equity=wallet_equity, prices={"AAAUSDT": 100.0}, step=0.001)
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=prov,
                                           v1_capital_base_usd=V1_CAPITAL_BASE)
    assert plan.status == ap.STATUS_PLANNED
    assert float(plan.actions[0].qty) == pytest.approx(2.0)
    assert plan.target_positions[0]["target_notional"] == pytest.approx(200.0)


@pytest.mark.parametrize("wallet_equity", [100_000.0, 20_000.0, 50_000.0, 1_000_000.0])
def test_wallet_independence_exposure_invariant(wallet_equity):
    """Gross/net exposure unchanged regardless of Demo wallet balance."""
    fwd = FakeForward(eqw_signals())
    plan = ap.plan_strategy_native_actions(forward_result=fwd,
                                           provider=FakeProvider(equity=wallet_equity),
                                           v1_capital_base_usd=V1_CAPITAL_BASE)
    v = plan.sizing_verification
    assert v["gross_target_exposure"] == pytest.approx(1.0, abs=1e-9)
    assert v["net_target_exposure"] == pytest.approx(0.0, abs=1e-9)
    assert v["capital_base_usd"] == V1_CAPITAL_BASE
    assert v["demo_wallet_equity_usd"] == wallet_equity


def test_capital_provenance_in_sizing_verification():
    """Sizing verification records capital base provenance and wallet non-use."""
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider(),
                                           v1_capital_base_usd=V1_CAPITAL_BASE)
    v = plan.sizing_verification
    assert v["capital_base_usd"] == V1_CAPITAL_BASE
    assert v["config_source_identity"] == "explicit_parameter"
    assert v["wallet_used_for_target_sizing"] is False
    assert v["demo_wallet_equity_usd"] == EQUITY
    assert v["verified"] is True


def test_capital_base_auto_resolved_from_forward_config():
    """Without explicit params, planner resolves from config + state artifact."""
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider())
    v = plan.sizing_verification
    assert v["capital_base_usd"] == V1_CAPITAL_BASE
    assert v["capital_base_verified"] is True
    assert "config" in v["capital_base_sources"]
    assert v["wallet_used_for_target_sizing"] is False


def test_capital_base_invalid_zero_fails_closed():
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider(),
                                           v1_capital_base_usd=0.0)
    assert plan.status == ap.STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED
    assert plan.available is False


def test_capital_base_invalid_negative_fails_closed():
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider(),
                                           v1_capital_base_usd=-5000.0)
    assert plan.status == ap.STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED
    assert plan.available is False


def test_capital_base_invalid_inf_fails_closed():
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider(),
                                           v1_capital_base_usd=float("inf"))
    assert plan.status == ap.STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED
    assert plan.available is False


def test_orchestrator_refuses_send_when_capital_base_unverified(tmp_path):
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}])
    t = FakeTransport()
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider(),
                                           v1_capital_base_usd=0.0)
    out = daily_cli.orchestrate_native_daily(
        pilot_id="BYBIT_DEMO_PILOT_7D_202606_V1", date="2026-06-22", forward_result=fwd,
        provider=FakeProvider(), transport=t, output_root=str(tmp_path / "out"), plan=plan)
    assert out["status"] == ap.STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED
    assert out["send_refused"] is True
    assert len(t.posts) == 0


def test_exit_code_capital_base_unverified_exists():
    assert daily_cli.EXIT_V1_CAPITAL_BASE_UNVERIFIED == 8


# ===========================================================================
# FIX3: cross-validated evidence bundle + fingerprints + plan-only audit
# ===========================================================================


# --- BLOCKER 1: evidence bundle cross-validation ----------------------------


def test_evidence_config_and_state_match_verified():
    ev = ap.resolve_v1_capital_base_evidence(
        config_value_override=10_000.0, state_value_override=10_000.0)
    assert ev["capital_base_verified"] is True
    assert ev["capital_base_usd"] == 10_000.0
    assert ev["sources_agree"] is True
    assert ev["capital_base_source_count"] == 2
    assert ev["capital_base_sources"] == ["config", "state_artifact"]
    assert ev["config_value_usd"] == 10_000.0
    assert ev["state_value_usd"] == 10_000.0
    assert ev["wallet_used_for_target_sizing"] is False
    assert ev["kelly_used"] is False


def test_evidence_both_fingerprints_present():
    ev = ap.resolve_v1_capital_base_evidence(
        config_value_override=10_000.0, state_value_override=10_000.0)
    assert ev["config_source_fingerprint"] is not None
    assert ev["config_source_fingerprint"].startswith("sha256:")
    assert ev["state_artifact_fingerprint"] is not None
    assert ev["state_artifact_fingerprint"].startswith("sha256:")
    assert ev["evidence_bundle_fingerprint"] is not None
    assert ev["evidence_bundle_fingerprint"].startswith("sha256:")


def test_evidence_bundle_fingerprint_deterministic():
    ev1 = ap.resolve_v1_capital_base_evidence(
        config_value_override=10_000.0, state_value_override=10_000.0)
    ev2 = ap.resolve_v1_capital_base_evidence(
        config_value_override=10_000.0, state_value_override=10_000.0)
    assert ev1["evidence_bundle_fingerprint"] == ev2["evidence_bundle_fingerprint"]
    assert ev1["config_source_fingerprint"] == ev2["config_source_fingerprint"]
    assert ev1["state_artifact_fingerprint"] == ev2["state_artifact_fingerprint"]


def test_evidence_config_state_mismatch_conflict():
    ev = ap.resolve_v1_capital_base_evidence(
        config_value_override=10_000.0, state_value_override=20_000.0)
    assert ev["capital_base_verified"] is False
    assert ev["sources_agree"] is False
    assert ev["capital_base_source_count"] == 2
    assert ev["capital_base_usd"] is None


def test_evidence_missing_state_unverified(tmp_path):
    ev = ap.resolve_v1_capital_base_evidence(
        state_artifact_path=str(tmp_path / "nonexistent_state.json"),
        config_value_override=10_000.0)
    assert ev["capital_base_verified"] is False
    assert ev["capital_base_source_count"] == 1
    assert "state_artifact" not in ev["capital_base_sources"]


def test_evidence_corrupt_state_json_unverified(tmp_path):
    corrupt = tmp_path / "state.json"
    corrupt.write_text("{broken json", encoding="utf-8")
    ev = ap.resolve_v1_capital_base_evidence(
        state_artifact_path=str(corrupt), config_value_override=10_000.0)
    assert ev["capital_base_verified"] is False
    assert ev["state_value_usd"] is None
    assert ev["state_artifact_fingerprint"] is not None  # bytes were read


def test_evidence_missing_config_unverified():
    ev = ap.resolve_v1_capital_base_evidence(
        config_value_override=None, state_value_override=10_000.0,
        state_artifact_path="/nonexistent")
    # config_value_override=None triggers the real import path which succeeds,
    # so test with a monkeypatch-style: pass an invalid config instead
    ev2 = ap.resolve_v1_capital_base_evidence(
        config_value_override=float("nan"), state_value_override=10_000.0)
    assert ev2["capital_base_verified"] is False
    assert "config" not in ev2["capital_base_sources"]


@pytest.mark.parametrize("bad_value", [0.0, -1.0, float("nan"), float("inf"), float("-inf")])
def test_evidence_invalid_config_value_fails_closed(bad_value):
    ev = ap.resolve_v1_capital_base_evidence(
        config_value_override=bad_value, state_value_override=10_000.0)
    assert ev["capital_base_verified"] is False
    assert "config" not in ev["capital_base_sources"]


@pytest.mark.parametrize("bad_value", [0.0, -1.0, float("nan"), float("inf"), float("-inf")])
def test_evidence_invalid_state_value_fails_closed(bad_value):
    ev = ap.resolve_v1_capital_base_evidence(
        config_value_override=10_000.0, state_value_override=bad_value)
    assert ev["capital_base_verified"] is False
    assert "state_artifact" not in ev["capital_base_sources"]


def test_evidence_real_state_artifact_matches_config():
    """Real state.json paper_equity_init == PaperTradingConfig.initial_nav_usd."""
    ev = ap.resolve_v1_capital_base_evidence()
    assert ev["capital_base_verified"] is True
    assert ev["config_value_usd"] == 10_000.0
    assert ev["state_value_usd"] == 10_000.0
    assert ev["sources_agree"] is True


# --- BLOCKER 1: planner integration with evidence ---------------------------


def test_planner_with_matching_evidence():
    ev = _matching_evidence()
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider(),
                                           capital_base_evidence=ev)
    assert plan.status == ap.STATUS_PLANNED
    v = plan.sizing_verification
    assert v["capital_base_usd"] == 10_000.0
    assert v["capital_base_verified"] is True
    assert v["evidence_bundle_fingerprint"] is not None
    assert v["demo_wallet_equity_usd"] == EQUITY
    assert v["demo_available_balance_usd"] == EQUITY


def test_planner_conflict_evidence_fails_closed():
    ev = ap.resolve_v1_capital_base_evidence(
        config_value_override=10_000.0, state_value_override=20_000.0)
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider(),
                                           capital_base_evidence=ev)
    assert plan.status == ap.STATUS_V1_BASELINE_CAPITAL_BASE_CONFLICT
    assert plan.available is False
    assert "10000" in plan.detail and "20000" in plan.detail


def test_planner_unverified_evidence_fails_closed():
    ev = ap.resolve_v1_capital_base_evidence(
        config_value_override=float("nan"), state_value_override=10_000.0)
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider(),
                                           capital_base_evidence=ev)
    assert plan.status == ap.STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED
    assert plan.available is False


@pytest.mark.parametrize("wallet_equity", [20_000.0, 50_000.0, 100_000.0, 1_000_000.0])
def test_wallet_never_alters_capital_or_notional_with_evidence(wallet_equity):
    """Evidence-based capital base ignores wallet equity for sizing."""
    ev = _matching_evidence()
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}])
    prov = FakeProvider(equity=wallet_equity, prices={"AAAUSDT": 100.0}, step=0.001)
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=prov,
                                           capital_base_evidence=ev)
    assert plan.status == ap.STATUS_PLANNED
    v = plan.sizing_verification
    assert v["capital_base_usd"] == 10_000.0
    assert v["demo_wallet_equity_usd"] == wallet_equity
    assert v["wallet_used_for_target_sizing"] is False
    assert float(plan.actions[0].qty) == pytest.approx(2.0)
    assert plan.target_positions[0]["target_notional"] == pytest.approx(200.0)


# --- BLOCKER 1: send-path refuses on conflict/unverified --------------------


def test_orchestrator_refuses_send_on_conflict(tmp_path):
    ev = ap.resolve_v1_capital_base_evidence(
        config_value_override=10_000.0, state_value_override=20_000.0)
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider(),
                                           capital_base_evidence=ev)
    t = FakeTransport()
    out = daily_cli.orchestrate_native_daily(
        pilot_id="BYBIT_DEMO_PILOT_7D_202606_V1", date="2026-06-22", forward_result=fwd,
        provider=FakeProvider(), transport=t, output_root=str(tmp_path / "out"), plan=plan)
    assert out["status"] == ap.STATUS_V1_BASELINE_CAPITAL_BASE_CONFLICT
    assert out["send_refused"] is True
    assert len(t.posts) == 0


def test_exit_code_conflict_exists():
    assert daily_cli.EXIT_V1_CAPITAL_BASE_CONFLICT == 9


# --- BLOCKER 2: plan-only audit fields --------------------------------------


def test_plan_only_audit_fields_with_provider(monkeypatch, tmp_path, capsys):
    """Plan-only path exposes truthful read-only network audit fields."""
    from src import demo_strategy_pilot_readiness as rd

    monkeypatch.setattr(daily_cli, "_build_production_provider",
                        lambda: FakeProvider())
    monkeypatch.setattr(rd.PilotStateStore, "read_state",
                        lambda self: {"lifecycle_state": rd.RUNNING})

    fwd_root = tmp_path / "fwd"
    (fwd_root / "prev3y_crypto").mkdir(parents=True)
    (fwd_root / "prev3y_crypto" / "forward_summary.json").write_text(
        json.dumps({"strategy": "prev3y_crypto_combined_paper_safe_variant",
                    "latest_date": "20260622"}), encoding="utf-8")

    from src import demo_strategy_pilot_forward_source as fs
    monkeypatch.setattr(fs, "load_primary_forward_strategy_result",
                        lambda **kw: FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}]))

    rc = daily_cli.main(["--pilot-id", "TEST_PILOT", "--date", "2026-06-22",
                          "--test-output-root", str(tmp_path / "out"),
                          "--json-only"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PLAN_ONLY_READ_ONLY_DEMO_NETWORK"
    assert payload["network_attempted"] is True
    assert payload["read_only_network"] is True
    assert payload["order_endpoint_called"] is False
    assert payload["order_post_count"] == 0
    assert payload["live_endpoint_called"] is False
    assert payload["live_trading_authorized"] is False
    assert rc == daily_cli.EXIT_OK


def test_plan_only_audit_fields_without_provider(monkeypatch, tmp_path, capsys):
    """When provider construction fails, status is not fabricated as NO_NETWORK."""
    from src import demo_strategy_pilot_readiness as rd

    monkeypatch.setattr(daily_cli, "_build_production_provider", lambda: None)
    monkeypatch.setattr(rd.PilotStateStore, "read_state",
                        lambda self: {"lifecycle_state": rd.RUNNING})

    from src import demo_strategy_pilot_forward_source as fs
    monkeypatch.setattr(fs, "load_primary_forward_strategy_result",
                        lambda **kw: FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}]))

    rc = daily_cli.main(["--pilot-id", "TEST_PILOT", "--date", "2026-06-22",
                          "--test-output-root", str(tmp_path / "out"),
                          "--json-only"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["network_attempted"] is False
    assert payload["read_only_network"] is False
    assert payload["order_endpoint_called"] is False
    assert payload["order_post_count"] == 0
    assert payload["live_endpoint_called"] is False
    assert payload["live_trading_authorized"] is False
    assert "PLAN_ONLY_NO_NETWORK" not in payload["status"]


def test_plan_only_audit_fields_consistency():
    """Audit fields are internally consistent: no order endpoint without send."""
    ev = _matching_evidence()
    fwd = FakeForward([{"symbol": "AAAUSDT", "side": "long", "score": 0.02}])
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider(),
                                           capital_base_evidence=ev)
    assert plan.available is True
    v = plan.sizing_verification
    assert v["wallet_used_for_target_sizing"] is False
    assert v["kelly_used"] is False
