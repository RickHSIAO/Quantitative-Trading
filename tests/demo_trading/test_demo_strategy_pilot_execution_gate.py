"""TASK-014CB -- single-tiny-order execution gate + plan/audit hardening tests.

Proves the raw 50-action V1 plan can never be sent, that single tiny execution
requires explicit fingerprint + authorization marker, that existing protected
positions block new opening, that audit counts are corrected, and that quantity
serialization is canonical. Fully offline: zero real HTTP, zero Bybit, zero orders.
"""

from __future__ import annotations

import importlib
import json
import pathlib
import sys
from decimal import Decimal

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import demo_strategy_pilot_action_planner as ap
from src import demo_strategy_pilot_execution_gate as gate
from src import demo_strategy_pilot_lifecycle as lc
from src import demo_strategy_pilot_native_execution as nx
from src import demo_strategy_pilot_readiness as rd
from src.demo_instrument_rules import InstrumentRules
from src.demo_portfolio_risk import DemoOpenPosition
from src.demo_readonly_client import DemoReadOnlyClient, InstrumentSnapshot
from src.demo_market_price_guard import DemoMarketPriceGuard

daily_cli = importlib.import_module("scripts.run_demo_strategy_pilot_native_daily")

PILOT = "BYBIT_DEMO_PILOT_7D_202606_V1"
DATE = "2026-06-22"
PROTECTED = frozenset(rd.PROTECTED_SYMBOLS)
INIT = 10_000.0
FULL_ENV = {"NOTION_TOKEN": "tok", "NOTION_PILOT_DATABASE_ID": "db",
            "MONITOR_DISCORD_WEBHOOK_URL": "http://hook"}
DEMO_ENV = dict(FULL_ENV, BYBIT_DEMO_API_KEY="DEMOKEY", BYBIT_DEMO_API_SECRET="DEMOSECRET")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class FakeForward:
    def __init__(self, signals):
        self.normalized_signals = tuple(signals)


class FakeProvider:
    """Real canonical sizer runs on these injected fixtures (no network)."""

    def __init__(self, *, positions=None, prices=None, steps=None, symbols=None):
        self._positions = positions or []
        self._symbols = symbols or []
        self._prices = prices or {s: 2.0 for s in self._symbols}
        self._steps = steps or {}

    def equity_usd(self): return INIT
    def available_balance_usd(self): return 8_500.0
    def open_positions(self): return list(self._positions)
    def market_price(self, symbol): return self._prices.get(symbol)

    def instrument_rule(self, symbol):
        step = self._steps.get(symbol, 0.1)
        return InstrumentRules(symbol=symbol, qty_step=step, min_qty=step, max_qty=0.0,
                               tick_size=0.0001, min_notional=1.0,
                               price_precision=4, qty_precision=3)


class SpyTransport:
    """Records every order POST / reconcile so we can assert ZERO sends."""

    def __init__(self):
        self.posts = []
        self.reconciles = []

    def post_order_create(self, *, url, body):
        self.posts.append((url, dict(body)))
        link = body["orderLinkId"]
        return {"retCode": 0, "retMsg": "OK",
                "result": {"orderId": "OID-" + link, "orderLinkId": link}}

    def reconcile(self, *, order_link_id):
        self.reconciles.append(order_link_id)
        return {"retCode": 0, "result": {"list": [{
            "orderLinkId": order_link_id, "orderId": "OID-" + order_link_id,
            "orderStatus": "Filled", "cumExecQty": "1", "avgPrice": "2",
            "cumExecFee": "0.01"}]}}


def fake_workbook_builder(*a, **k):
    return {"latest_xlsx": "fake.xlsx"}


def _50_symbols():
    base = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOT", "LINK", "AAVE", "AVAX",
            "MATIC", "ATOM", "UNI", "LTC", "BCH", "FIL", "APT", "ARB", "OP", "INJ",
            "SUI", "SEI", "TIA2", "NEAR", "ALGO", "ICP", "HBAR", "VET", "GRT", "STX",
            "IMX", "RENDER", "FET", "RUNE", "AXS", "SAND", "MANA", "GALA", "CHZ", "CRV",
            "DYDX", "SNX", "COMP", "MKR", "1INCH", "ENJ", "BAT", "ZEC", "DASH", "KSM"]
    return [b + "USDT" for b in base]


def _signals(symbols, weight=0.02):
    out = []
    for i, s in enumerate(symbols):
        side = "long" if i < len(symbols) // 2 else "short"
        out.append({"symbol": s, "side": side, "weight": weight, "score": weight})
    return out


def _50_action_plan(prices=None, steps=None, positions=None):
    symbols = _50_symbols()
    prov = FakeProvider(symbols=symbols, prices=prices or {s: 2.0 for s in symbols},
                        steps=steps, positions=positions)
    fwd = FakeForward(_signals(symbols))
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=prov)
    return plan, prov


def running_pilot(tmp_path, fwd_root):
    out = str(tmp_path / "out")
    rd.initialize_pilot(pilot_id=PILOT, acknowledged=True, env=FULL_ENV,
                        output_root=out, forward_source_root=fwd_root)
    lc.migrate_to_strategy_native(pilot_id=PILOT, acknowledged=True, output_root=out)
    lc.start_pilot(pilot_id=PILOT, acknowledged=True, env=DEMO_ENV, output_root=out)
    return out


@pytest.fixture
def fwd_root(tmp_path):
    d = tmp_path / "fwd" / "prev3y_crypto"
    d.mkdir(parents=True)
    (d / "forward_summary.json").write_text(
        json.dumps({"strategy": "prev3y_crypto_combined_paper_safe_variant",
                    "latest_date": "20260518"}), encoding="utf-8")
    return str(tmp_path / "fwd")


# ---------------------------------------------------------------------------
# 1, 14, 15 -- full 50-action V1 plan remains visible & unchanged
# ---------------------------------------------------------------------------


def test_full_50_action_plan_remains_visible():
    plan, _ = _50_action_plan()
    assert plan.status == ap.STATUS_PLANNED
    assert len(plan.actions) == 50
    assert len(plan.target_positions) == 50


def test_full_v1_200usdt_target_unchanged_in_planner():
    plan, _ = _50_action_plan()
    for tp in plan.target_positions:
        assert abs(abs(tp["target_notional"]) - 200.0) < 1e-6
    for a in plan.actions:
        assert abs(abs(float(a.notional_usdt)) - 200.0) < 1e-6


def test_200usdt_not_silently_reduced_in_plan():
    plan, prov = _50_action_plan()
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="sha256:x")
    # The planner still carries 200; the gate reports the tiny cap SEPARATELY.
    assert all(abs(abs(tp["target_notional"]) - 200.0) < 1e-6 for tp in plan.target_positions)
    assert Decimal(res.effective_per_order_notional_cap_usdt) < Decimal("200")


# ---------------------------------------------------------------------------
# 2, 3, 25 -- send path performs zero POST; raw iteration impossible
# ---------------------------------------------------------------------------


def test_unselected_50_action_send_zero_post(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _50_action_plan()
    t = SpyTransport()
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=t,
        output_root=out_root, plan=plan, workbook_builder=fake_workbook_builder)
    assert len(t.posts) == 0
    assert out["order_post_count"] == 0
    assert out["amend_post_count"] == 0
    assert out["cancel_post_count"] == 0
    assert out["order_endpoint_called"] is False
    assert out["live_endpoint_called"] is False
    assert out["execution_authorized"] is False
    assert out["send_path_refused"] is True


def test_multi_action_raw_iteration_impossible(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _50_action_plan()
    t = SpyTransport()
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=t,
        output_root=out_root, plan=plan, workbook_builder=fake_workbook_builder)
    g = out["execution_gate"]
    assert g["multi_action_send_refused"] is True
    assert g["raw_planned_action_count"] == 50
    assert len(t.posts) == 0


def test_gate_refuses_multi_without_protected_positions():
    plan, _ = _50_action_plan()
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="sha256:x")
    assert res.final_execution_authorization_status == gate.EXECUTION_NOT_AUTHORIZED_MULTI_ACTION_PLAN
    assert res.multi_action_send_refused is True
    assert res.authorized is False


# ---------------------------------------------------------------------------
# 4, 5, 6, 7, 8 -- explicit selection / fingerprint / marker required
# ---------------------------------------------------------------------------


def _single_action_plan():
    fwd = FakeForward([{"symbol": "SOLUSDT", "side": "long", "weight": 0.02, "score": 0.02}])
    prov = FakeProvider(symbols=["SOLUSDT"], prices={"SOLUSDT": 2.0}, steps={"SOLUSDT": 0.1})
    return ap.plan_strategy_native_actions(forward_result=fwd, provider=prov), prov


def test_no_default_first_action_selection():
    plan, _ = _single_action_plan()
    # action_seq=0 must NOT be auto-selected.
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="sha256:x")
    assert res.selected_execution_candidate_count == 0
    assert res.authorized is False
    assert gate.EXECUTION_NOT_AUTHORIZED_NO_SELECTION in res.refusal_reasons


def test_explicit_fingerprint_selection_required():
    plan, _ = _single_action_plan()
    a = plan.actions[0]
    fp = gate.action_fingerprint(a, pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x")
    res = gate.evaluate_execution_gate(
        plan=plan, open_positions=[], pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x",
        selected_action_fingerprint=fp, authorization_marker=gate.REQUIRED_AUTHORIZATION_MARKER)
    assert res.selected_execution_candidate_count == 1
    assert res.authorized is True
    assert res.final_execution_authorization_status == gate.AUTHORIZED_SINGLE_TINY_EXECUTION_CANDIDATE


def test_mismatched_fingerprint_refuses():
    plan, _ = _single_action_plan()
    res = gate.evaluate_execution_gate(
        plan=plan, open_positions=[], pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x",
        selected_action_fingerprint="sha256:STALE", authorization_marker=gate.REQUIRED_AUTHORIZATION_MARKER)
    assert res.authorized is False
    assert res.final_execution_authorization_status == gate.EXECUTION_NOT_AUTHORIZED_FINGERPRINT_MISMATCH


def test_stale_fingerprint_from_different_date_refuses():
    plan, _ = _single_action_plan()
    a = plan.actions[0]
    stale_fp = gate.action_fingerprint(a, pilot_id=PILOT, date="2026-06-21",
                                       forward_fingerprint="sha256:x")
    res = gate.evaluate_execution_gate(
        plan=plan, open_positions=[], pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x",
        selected_action_fingerprint=stale_fp, authorization_marker=gate.REQUIRED_AUTHORIZATION_MARKER)
    assert res.authorized is False
    assert res.final_execution_authorization_status == gate.EXECUTION_NOT_AUTHORIZED_FINGERPRINT_MISMATCH


def test_missing_authorization_marker_refuses():
    plan, _ = _single_action_plan()
    a = plan.actions[0]
    fp = gate.action_fingerprint(a, pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x")
    res = gate.evaluate_execution_gate(
        plan=plan, open_positions=[], pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x",
        selected_action_fingerprint=fp, authorization_marker=None)
    assert res.authorized is False
    assert res.final_execution_authorization_status == gate.EXECUTION_NOT_AUTHORIZED_MISSING_MARKER


def test_wrong_authorization_marker_refuses():
    plan, _ = _single_action_plan()
    a = plan.actions[0]
    fp = gate.action_fingerprint(a, pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x")
    res = gate.evaluate_execution_gate(
        plan=plan, open_positions=[], pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x",
        selected_action_fingerprint=fp, authorization_marker="not-the-marker")
    assert res.authorized is False
    assert gate.EXECUTION_NOT_AUTHORIZED_MISSING_MARKER in res.refusal_reasons


def test_multiple_selected_refuses():
    # Two identical eligible actions -> same fingerprint -> selection is ambiguous.
    a1 = nx.StrategyNativeAction(symbol="SOLUSDT", side="Buy", qty="2.5", intent="OPEN",
                                 reduce_only=False, notional_usdt="5", action_seq=0,
                                 source_reference="target_open")
    a2 = nx.StrategyNativeAction(symbol="SOLUSDT", side="Buy", qty="2.5", intent="OPEN",
                                 reduce_only=False, notional_usdt="5", action_seq=1,
                                 source_reference="target_open")

    class P:
        available = True
        actions = [a1, a2]
        sizing_verification = {"verified": True}
        target_positions = []; current_positions = []; rejected_signals = []
        status = "OK"
        def to_dict(self): return {}

    fp = gate.action_fingerprint(a1, pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x")
    res = gate.evaluate_execution_gate(
        plan=P(), open_positions=[], pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x",
        selected_action_fingerprint=fp, authorization_marker=gate.REQUIRED_AUTHORIZATION_MARKER)
    assert res.selected_execution_candidate_count == 2
    assert res.final_execution_authorization_status == gate.EXECUTION_NOT_AUTHORIZED_MULTIPLE_SELECTED


# ---------------------------------------------------------------------------
# 9, 10 -- effective per-order / daily cap enforced
# ---------------------------------------------------------------------------


def test_effective_per_order_cap_is_strictest():
    pol = gate.resolve_effective_policy()
    # strictest of SAFETY_POLICY 10 and tiny adapter 5 -> 5.
    assert pol.per_order_notional_cap_usdt == Decimal("5")
    assert pol.conflict is False


def test_effective_daily_cap_enforced():
    pol = gate.resolve_effective_policy()
    # daily bounded by per-order(5) * max_new_per_day(1) -> 5.
    assert pol.daily_new_opening_notional_cap_usdt == Decimal("5")


def test_200usdt_target_capped_to_tiny_in_candidate():
    plan, _ = _single_action_plan()
    a = plan.actions[0]
    fp = gate.action_fingerprint(a, pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x")
    res = gate.evaluate_execution_gate(
        plan=plan, open_positions=[], pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x",
        selected_action_fingerprint=fp, authorization_marker=gate.REQUIRED_AUTHORIZATION_MARKER)
    c = res.selected_candidate
    assert c["strategy_target_notional_usdt"] == "200"
    assert Decimal(c["execution_candidate_notional_usdt"]) <= Decimal("5")
    assert res.cap_compliance_status == "TARGET_EXCEEDS_TINY_CAP"


# ---------------------------------------------------------------------------
# 11, 12, 13 -- existing positions limit / protected positions block / candidates
# ---------------------------------------------------------------------------


def _protected_positions():
    return [
        DemoOpenPosition(symbol="EDUUSDT", side="short", quantity=827.0,
                         entry_price=1.0, stop_price=1.5),
        DemoOpenPosition(symbol="POLYXUSDT", side="short", quantity=2807.8,
                         entry_price=0.5, stop_price=0.75),
    ]


def test_existing_protected_positions_block_new_opening():
    plan, _ = _single_action_plan()
    a = plan.actions[0]
    fp = gate.action_fingerprint(a, pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x")
    # Even with a correct selection + marker, 2 protected positions block.
    res = gate.evaluate_execution_gate(
        plan=plan, open_positions=_protected_positions(), pilot_id=PILOT, date=DATE,
        forward_fingerprint="sha256:x", selected_action_fingerprint=fp,
        authorization_marker=gate.REQUIRED_AUTHORIZATION_MARKER)
    assert res.authorized is False
    assert res.final_execution_authorization_status == \
        gate.NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS
    assert res.existing_protected_position_count == 2
    assert res.simultaneous_position_policy_status == gate.SIM_POLICY_PROTECTED_EXCLUSION_UNDEFINED


def test_real_vps_scenario_fails_closed():
    """50 actions + 2 protected positions -> fail closed, zero candidates executable."""
    plan, _ = _50_action_plan(positions=_protected_positions())
    res = gate.evaluate_execution_gate(
        plan=plan, open_positions=_protected_positions(), pilot_id=PILOT, date=DATE,
        forward_fingerprint="sha256:x")
    assert res.final_execution_authorization_status == \
        gate.NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS
    assert res.multi_action_send_refused is True
    assert res.authorized is False


def test_protected_symbols_never_become_candidates():
    # A protected symbol in the signals is dropped by the planner; even if forced
    # into actions, the gate never treats it as eligible.
    protected_action = nx.StrategyNativeAction(
        symbol="ENAUSDT", side="Buy", qty="5", intent="OPEN", reduce_only=False,
        notional_usdt="200", action_seq=0, source_reference="target_open")

    class P:
        available = True
        actions = [protected_action]
        sizing_verification = {"verified": True}
        target_positions = []; current_positions = []; rejected_signals = []
        status = "OK"
        def to_dict(self): return {}

    res = gate.evaluate_execution_gate(plan=P(), open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="sha256:x")
    assert res.eligible_execution_candidate_count == 0


def test_edu_polyx_positions_untouched_in_send(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _50_action_plan(positions=_protected_positions())
    t = SpyTransport()
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=t,
        output_root=out_root, plan=plan, workbook_builder=fake_workbook_builder)
    assert len(t.posts) == 0
    # No CLOSE/REDUCE/OPEN action for any protected symbol reached the transport.
    assert all(p[1].get("symbol") not in PROTECTED for p in t.posts)
    assert out["status"] == gate.NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS


# ---------------------------------------------------------------------------
# 16 -- tiny execution candidate labeled as probe
# ---------------------------------------------------------------------------


def test_tiny_candidate_labeled_as_execution_probe():
    plan, _ = _single_action_plan()
    a = plan.actions[0]
    fp = gate.action_fingerprint(a, pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x")
    res = gate.evaluate_execution_gate(
        plan=plan, open_positions=[], pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x",
        selected_action_fingerprint=fp, authorization_marker=gate.REQUIRED_AUTHORIZATION_MARKER)
    assert res.selected_candidate["candidate_kind"] == "EXECUTION_PROBE_NOT_V1_PORTFOLIO_REPLICATION"


# ---------------------------------------------------------------------------
# 17, 18, 19 -- canonical Decimal quantity serialization
# ---------------------------------------------------------------------------


def test_canonical_qty_is_decimal_string():
    # notional 5, price 1.81, step 0.01 -> 2.76 exactly (no float tail).
    q = gate.canonical_qty_str("5", "1.81", "0.01")
    assert q == "2.76"
    assert not gate.has_float_artifact(q)


def test_canonical_qty_exact_step_multiple():
    q = gate.canonical_qty("200", "0.07287", "0.1")
    assert gate.is_exact_multiple(q, "0.1")


def test_no_float_artifact_in_planner_qty():
    # A price/step combination that would yield a binary-float artifact under
    # naive float serialization must be canonical in the planner output.
    fwd = FakeForward([{"symbol": "ONEINCHUSDT", "side": "long", "weight": 0.02, "score": 0.02}])
    prov = FakeProvider(symbols=["ONEINCHUSDT"], prices={"ONEINCHUSDT": 0.07287},
                        steps={"ONEINCHUSDT": 0.1})
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=prov)
    for a in plan.actions:
        assert not gate.has_float_artifact(a.qty), f"float artifact in qty {a.qty!r}"


def test_no_float_artifact_in_gate_json():
    plan, _ = _single_action_plan()
    a = plan.actions[0]
    fp = gate.action_fingerprint(a, pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x")
    res = gate.evaluate_execution_gate(
        plan=plan, open_positions=[], pilot_id=PILOT, date=DATE, forward_fingerprint="sha256:x",
        selected_action_fingerprint=fp, authorization_marker=gate.REQUIRED_AUTHORIZATION_MARKER)
    text = json.dumps(res.to_dict())
    # canonical qty in the candidate must not carry a binary-float tail.
    assert not gate.has_float_artifact(res.selected_candidate["canonical_qty"])
    assert "0000000001" not in text
    assert "9999999999" not in text


def test_canonical_qty_floors_never_up():
    # 5 / 3 = 1.666...; step 0.01 -> 1.66 (floored), notional <= 5.
    q = gate.canonical_qty("5", "3", "0.01")
    assert q == Decimal("1.66")
    assert q * Decimal("3") <= Decimal("5")


# ---------------------------------------------------------------------------
# 20, 21, 22, 23, 24 -- corrected audit semantics + real network accounting
# ---------------------------------------------------------------------------


def _fixture_provider():
    """Build the production provider with fixture-mode client + guard (offline)."""
    client = DemoReadOnlyClient(allow_real_network=False)
    guard = DemoMarketPriceGuard(allow_real_network=False)
    return daily_cli._build_production_provider(_client=client, _guard=guard)


def test_matched_count_is_requested_not_cache():
    prov = _fixture_provider()
    audit = prov.audit()
    cache_count = audit["instrument_rule_cache_count"]
    # Request only 2 known targets; matched must be 2, NOT the full cache count.
    match = prov.match_targets(["BTCUSDT", "ETHUSDT"])
    assert match["requested_target_symbol_count"] == 2
    assert match["matched_instrument_rule_count"] == 2
    assert match["matched_instrument_rule_count"] != cache_count or cache_count == 2


def test_catalog_cache_count_reported_separately():
    prov = _fixture_provider()
    audit = prov.audit()
    assert audit["instrument_rule_cache_count"] >= 1
    assert "valid_instrument_rule_cache_count" in audit
    # match over a single target is independent of the catalog cache.
    match = prov.match_targets(["BTCUSDT"])
    assert match["matched_instrument_rule_count"] == 1


def test_missing_target_reported():
    prov = _fixture_provider()
    match = prov.match_targets(["BTCUSDT", "NOTLISTEDUSDT"])
    assert match["matched_instrument_rule_count"] == 1
    assert match["missing_instrument_rule_count"] == 1


def test_ticker_get_count_is_real():
    prov = _fixture_provider()
    assert prov.audit()["ticker_public_get_count"] == 0  # none fetched yet
    prov.market_price("BTCUSDT")
    prov.market_price("ETHUSDT")
    prov.market_price("BTCUSDT")  # cached -> no new GET
    assert prov.audit()["ticker_public_get_count"] == 2


def test_instrument_metadata_get_count_is_real():
    prov = _fixture_provider()
    assert prov.audit()["instrument_metadata_public_get_count"] == 1


def test_private_get_counts_are_real():
    prov = _fixture_provider()
    audit = prov.audit()
    assert audit["wallet_private_read_only_get_count"] == 1
    assert audit["positions_private_read_only_get_count"] == 1
    assert audit["total_private_read_only_get_count"] == 2


def test_audit_zero_post_and_live():
    prov = _fixture_provider()
    audit = prov.audit()
    assert audit["order_post_count"] == 0
    assert audit["amend_post_count"] == 0
    assert audit["cancel_post_count"] == 0
    assert audit["live_endpoint_called"] is False


# ---------------------------------------------------------------------------
# 26, 27 -- source / Pilot byte-identity during plan-only & refused send
# ---------------------------------------------------------------------------


def test_pilot_state_byte_identical_on_refused_send(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    state_path = pathlib.Path(out_root)
    # Snapshot all pilot state files.
    before = {p: p.read_bytes() for p in state_path.rglob("pilot_state.json")}
    assert before, "expected a pilot_state.json"
    plan, prov = _50_action_plan(positions=_protected_positions())
    t = SpyTransport()
    daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=t,
        output_root=out_root, plan=plan, workbook_builder=fake_workbook_builder)
    after = {p: p.read_bytes() for p in state_path.rglob("pilot_state.json")}
    assert after == before


def test_no_pilot_advancement_on_refused_send(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _50_action_plan(positions=_protected_positions())
    t = SpyTransport()
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=t,
        output_root=out_root, plan=plan, workbook_builder=fake_workbook_builder)
    assert out["pilot_advanced"] is False
    state = rd.PilotStateStore(PILOT, out_root).read_state()
    assert state["completed_successful_days"] == 0


# ---------------------------------------------------------------------------
# 28, 29 -- live endpoint denied; no secret material
# ---------------------------------------------------------------------------


def test_live_endpoint_remains_denied(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _50_action_plan()
    t = SpyTransport()
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=t,
        output_root=out_root, base_url="https://api.bybit.com", plan=plan,
        workbook_builder=fake_workbook_builder)
    assert out["live_endpoint_called"] is False
    assert out["live_trading_authorized"] is False
    assert len(t.posts) == 0


def test_no_secret_material_in_gate_output():
    plan, prov = _50_action_plan()
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="sha256:x")
    text = json.dumps(res.to_dict()).lower()
    for sensitive in ("api_key", "api_secret", "bybit_demo_api_key", "bybit_demo_api_secret",
                      "demokey", "demosecret", "x-bapi-sign"):
        assert sensitive not in text


# ---------------------------------------------------------------------------
# Authorized path executes EXACTLY ONE tiny order (mechanism w/ fake transport)
# ---------------------------------------------------------------------------


def test_authorized_single_tiny_executes_exactly_one(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _single_action_plan()
    a = plan.actions[0]
    fwd_fp = daily_cli._forward_fingerprint_of(plan)
    fp = gate.action_fingerprint(a, pilot_id=PILOT, date=DATE, forward_fingerprint=fwd_fp)
    t = SpyTransport()
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=t,
        output_root=out_root, plan=plan, selected_action_fingerprint=fp,
        authorization_marker=gate.REQUIRED_AUTHORIZATION_MARKER,
        workbook_builder=fake_workbook_builder)
    assert out["execution_authorized"] is True
    # EXACTLY ONE order POST (the tiny probe), never the 50-action plan.
    assert len(t.posts) == 1
    body = t.posts[0][1]
    assert not gate.has_float_artifact(str(body["qty"]))
    assert Decimal(str(body["qty"])) > 0
