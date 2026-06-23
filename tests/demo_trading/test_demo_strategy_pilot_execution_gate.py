"""TASK-014CB_FIX -- non-dispatching execution-review gate + canonical delegation.

Proves the native daily send surface no longer dispatches: the full 50-action V1
plan stays planning output, real Demo execution is delegated to the existing
canonical one-shot tiny adapter, qtyStep comes only from authoritative
InstrumentRules (never inferred), unsupported non-SOL symbols are not
execution-eligible, and no independent real-order authorization marker remains.
Fully offline: zero real HTTP, zero Bybit, zero orders.
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
from src import demo_only_tiny_execution_adapter as bh
from src import demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator as osh
from src import demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate as ce
from src.demo_instrument_rules import InstrumentRules
from src.demo_portfolio_risk import DemoOpenPosition
from src.demo_readonly_client import DemoReadOnlyClient
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
    """Canonical sizer runs on these fixtures; also exposes authoritative
    instrument_rule_evidence (qty_step from rules, never inferred)."""

    def __init__(self, *, positions=None, prices=None, steps=None, symbols=None,
                 rule_status=None):
        self._positions = positions or []
        self._symbols = symbols or []
        self._prices = prices or {s: 2.0 for s in self._symbols}
        self._steps = steps or {}
        self._rule_status = rule_status or {}

    def equity_usd(self): return INIT
    def available_balance_usd(self): return 8_500.0
    def open_positions(self): return list(self._positions)
    def market_price(self, symbol): return self._prices.get(symbol)

    def instrument_rule(self, symbol):
        step = self._steps.get(symbol, 0.1)
        return InstrumentRules(symbol=symbol, qty_step=step, min_qty=step, max_qty=0.0,
                               tick_size=0.0001, min_notional=1.0,
                               price_precision=4, qty_precision=3)

    def instrument_rule_evidence(self, symbol):
        status = self._rule_status.get(symbol, "TRADING")
        ev = {"symbol": symbol, "rule_status": status,
              "instrument_rule_source": "fixture_provider",
              "market_price_source": "fixture_guard",
              "market_price": self._prices.get(symbol)}
        if status == "TRADING":
            step = self._steps.get(symbol, 0.1)
            ev.update({"qty_step": step, "min_qty": step, "max_qty": 0.0,
                       "min_notional": 1.0, "tick_size": 0.0001})
        return ev


class SpyTransport:
    def __init__(self):
        self.posts = []
        self.reconciles = []

    def post_order_create(self, *, url, body):
        self.posts.append((url, dict(body)))
        return {"retCode": 0, "result": {"orderId": "X", "orderLinkId": body.get("orderLinkId")}}

    def reconcile(self, *, order_link_id):
        self.reconciles.append(order_link_id)
        return {"retCode": 0, "result": {"list": []}}


def fake_workbook_builder(*a, **k):
    return {"latest_xlsx": "fake.xlsx"}


def _50_symbols():
    base = ["BTC", "ETH", "BNB", "XRP", "ADA", "DOT", "LINK", "AAVE", "AVAX",
            "MATIC", "ATOM", "UNI", "LTC", "BCH", "FIL", "APT", "ARB", "OP", "INJ",
            "SUI", "SEI", "NEAR", "ALGO", "ICP", "HBAR", "VET", "GRT", "STX",
            "IMX", "RENDER", "FET", "RUNE", "AXS", "SAND", "MANA", "GALA", "CHZ", "CRV",
            "DYDX", "SNX", "COMP", "MKR", "ONEINCH", "ENJ", "BAT", "ZEC", "DASH", "KSM",
            "WLD", "PYTH"]
    return [b + "USDT" for b in base]


def _signals(symbols, weight=0.02):
    return [{"symbol": s, "side": "long" if i < len(symbols) // 2 else "short",
             "weight": weight, "score": weight} for i, s in enumerate(symbols)]


def _50_action_plan(positions=None, include_sol=False, sol_step=0.1):
    symbols = _50_symbols()
    if include_sol:
        symbols = symbols[:49] + ["SOLUSDT"]
    steps = {"SOLUSDT": sol_step}
    prov = FakeProvider(symbols=symbols, prices={s: 2.0 for s in symbols}, steps=steps,
                        positions=positions)
    plan = ap.plan_strategy_native_actions(forward_result=FakeForward(_signals(symbols)),
                                           provider=prov)
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


def _sol_plan(sol_step=0.1, rule_status=None):
    prov = FakeProvider(symbols=["SOLUSDT"], prices={"SOLUSDT": 150.0},
                        steps={"SOLUSDT": sol_step}, rule_status=rule_status or {})
    plan = ap.plan_strategy_native_actions(
        forward_result=FakeForward([{"symbol": "SOLUSDT", "side": "long",
                                     "weight": 0.02, "score": 0.02}]), provider=prov)
    return plan, prov


# ---------------------------------------------------------------------------
# 1 -- full 50-action plan remains visible/unchanged
# ---------------------------------------------------------------------------


def test_full_50_action_plan_remains_visible():
    plan, _ = _50_action_plan()
    assert plan.status == ap.STATUS_PLANNED
    assert len(plan.actions) == 50
    assert len(plan.target_positions) == 50
    for tp in plan.target_positions:
        assert abs(abs(tp["target_notional"]) - 200.0) < 1e-6


# ---------------------------------------------------------------------------
# 2, 3, 4, 19, 20 -- native send dispatches nothing
# ---------------------------------------------------------------------------


def test_native_send_zero_transport_calls(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _50_action_plan()
    t = SpyTransport()
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=t,
        output_root=out_root, plan=plan, workbook_builder=fake_workbook_builder)
    assert len(t.posts) == 0 and len(t.reconciles) == 0
    assert out["order_post_count"] == 0
    assert out["amend_post_count"] == 0
    assert out["cancel_post_count"] == 0
    assert out["transport_sender_call_count"] == 0
    assert out["live_endpoint_called"] is False
    assert out["status"] == gate.EXECUTION_DELEGATED_TO_CANONICAL_ONE_SHOT_ADAPTER


def test_native_send_never_calls_execute_daily_native(tmp_path, fwd_root, monkeypatch):
    out_root = running_pilot(tmp_path, fwd_root)
    calls = {"n": 0}

    def _boom(*a, **k):
        calls["n"] += 1
        raise AssertionError("execute_daily_native must NEVER be called by the native send surface")

    monkeypatch.setattr(nx, "execute_daily_native", _boom)
    plan, prov = _50_action_plan(include_sol=True)
    t = SpyTransport()
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=t,
        output_root=out_root, plan=plan, workbook_builder=fake_workbook_builder)
    assert calls["n"] == 0
    assert out["execute_daily_native_called"] is False
    assert len(t.posts) == 0


def test_no_generic_action_reaches_sender(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _50_action_plan(include_sol=True)
    t = SpyTransport()
    daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=t,
        output_root=out_root, plan=plan, workbook_builder=fake_workbook_builder)
    assert t.posts == []


def test_native_dispatch_disabled_flag(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _50_action_plan()
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=None,
        output_root=out_root, plan=plan)
    assert out["native_dispatch_disabled"] is True
    assert out["execution_authorized"] is False
    assert out["execution_ready"] is False
    assert out["sender_reachable"] is False
    assert out["canonical_one_shot_adapter_required"] is True
    assert out["canonical_execution_packet_present"] is False


# ---------------------------------------------------------------------------
# 5, 6 -- no new marker; canonical marker/constants referenced
# ---------------------------------------------------------------------------


def test_no_new_independent_authorization_marker():
    # The TASK-014CB generic marker must be gone.
    assert not hasattr(gate, "REQUIRED_AUTHORIZATION_MARKER")
    assert not hasattr(gate, "AUTHORIZED_SINGLE_TINY_EXECUTION_CANDIDATE")


def test_canonical_marker_and_constants_referenced():
    assert gate.CANONICAL_REAL_ORDER_AUTHORIZATION_MARKER == osh.EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER
    assert gate.CANONICAL_CAP_ESCALATION_AUTHORIZATION_MARKER == ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER
    assert gate.CANONICAL_ONE_SHOT_ALLOWED_SYMBOL == bh.ALLOWED_SYMBOL == "SOLUSDT"
    refs = gate.canonical_one_shot_references()
    assert refs["allowed_symbol"] == "SOLUSDT"
    assert refs["real_order_authorized"] is False
    assert refs["cap_escalation_authorized"] is False
    assert "src.demo_only_tiny_execution_adapter" in refs["modules"]


# ---------------------------------------------------------------------------
# 7, 8, 9, 10 -- authoritative qtyStep provenance
# ---------------------------------------------------------------------------


def test_qty_step_from_instrument_rules():
    plan, prov = _sol_plan(sol_step=0.1)
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="fp", rule_provider=prov)
    ev = res.rule_evidence
    assert ev["qty_step"] == "0.1"
    assert ev["qty_step_source"] == "INSTRUMENT_RULE_PROVIDER"
    assert ev["qty_step_inferred_from_action"] is False


def test_qty_step_not_inferred_from_action_decimals():
    # Planner qty for SOLUSDT (price 150, step 0.01) would have 2 decimals, which
    # a naive inference might read as step 0.01. The authoritative rule says 0.5.
    prov = FakeProvider(symbols=["SOLUSDT"], prices={"SOLUSDT": 150.0},
                        steps={"SOLUSDT": 0.5})
    plan = ap.plan_strategy_native_actions(
        forward_result=FakeForward([{"symbol": "SOLUSDT", "side": "long",
                                     "weight": 0.02, "score": 0.02}]), provider=prov)
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="fp", rule_provider=prov)
    # qty_step reflects the RULE (0.5), regardless of the action qty's decimals.
    assert res.rule_evidence["qty_step"] == "0.5"


def test_same_qty_different_steps_different_outcome():
    plan, _ = _sol_plan(sol_step=0.1)
    r1 = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT, date=DATE,
                                      forward_fingerprint="fp",
                                      rule_provider=FakeProvider(symbols=["SOLUSDT"],
                                                                 prices={"SOLUSDT": 150.0},
                                                                 steps={"SOLUSDT": 0.1}))
    r2 = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT, date=DATE,
                                      forward_fingerprint="fp",
                                      rule_provider=FakeProvider(symbols=["SOLUSDT"],
                                                                 prices={"SOLUSDT": 150.0},
                                                                 steps={"SOLUSDT": 0.01}))
    assert r1.rule_evidence["instrument_rule_fingerprint"] != r2.rule_evidence["instrument_rule_fingerprint"]
    assert r1.rule_evidence["qty_step"] == "0.1"
    assert r2.rule_evidence["qty_step"] == "0.01"


def test_instrument_rule_fingerprint_present():
    plan, prov = _sol_plan()
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="fp", rule_provider=prov)
    assert res.rule_evidence["instrument_rule_fingerprint"].startswith("sha256:")


# ---------------------------------------------------------------------------
# 11, 12, 13 -- rule failures fail closed
# ---------------------------------------------------------------------------


def test_missing_rule_fails_closed():
    plan, _ = _sol_plan(rule_status={"SOLUSDT": "MISSING"})
    prov = FakeProvider(symbols=["SOLUSDT"], prices={"SOLUSDT": 150.0},
                        rule_status={"SOLUSDT": "MISSING"})
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="fp", rule_provider=prov)
    assert res.execution_candidate_eligible is False
    assert res.final_execution_authorization_status == gate.RULE_MISSING


def test_non_trading_rule_fails_closed():
    plan, _ = _sol_plan()
    prov = FakeProvider(symbols=["SOLUSDT"], prices={"SOLUSDT": 150.0},
                        rule_status={"SOLUSDT": "NON_TRADING"})
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="fp", rule_provider=prov)
    assert res.execution_candidate_eligible is False
    assert res.final_execution_authorization_status == gate.RULE_NON_TRADING


def test_malformed_rule_fails_closed():
    plan, _ = _sol_plan()
    prov = FakeProvider(symbols=["SOLUSDT"], prices={"SOLUSDT": 150.0},
                        rule_status={"SOLUSDT": "MALFORMED"})
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="fp", rule_provider=prov)
    assert res.execution_candidate_eligible is False
    assert res.final_execution_authorization_status == gate.RULE_MALFORMED


# ---------------------------------------------------------------------------
# 14, 15, 16 -- symbol scope; SOL delegates (never auto-authorized); no escalation
# ---------------------------------------------------------------------------


def test_unsupported_non_sol_symbols_not_eligible():
    plan, prov = _50_action_plan()  # no SOLUSDT
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="fp", rule_provider=prov)
    assert res.execution_candidate_eligible is False
    assert gate.SYMBOL_NOT_SUPPORTED_BY_CANONICAL_ONE_SHOT_ADAPTER in res.refusal_reasons
    assert res.final_execution_authorization_status == gate.SYMBOL_NOT_SUPPORTED_BY_CANONICAL_ONE_SHOT_ADAPTER


def test_solusdt_delegates_never_auto_authorized():
    plan, prov = _sol_plan()
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="fp", rule_provider=prov)
    # SOLUSDT with a valid rule is review-eligible, but NEVER authorized here.
    assert res.execution_candidate_eligible is True
    assert res.authorized is False
    assert res.execution_authorized is False
    assert res.canonical_execution_packet_present is False
    assert res.final_execution_authorization_status == gate.EXECUTION_DELEGATED_TO_CANONICAL_ONE_SHOT_ADAPTER
    assert res.execution_delegation_status == gate.CANONICAL_ONE_SHOT_EXECUTION_PACKET_REQUIRED


def test_no_cap_escalation_implied():
    plan, prov = _sol_plan()
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="fp", rule_provider=prov)
    refs = res.canonical_one_shot_references
    assert refs["cap_escalation_authorized"] is False
    assert refs["real_order_authorized"] is False
    inv = {s["source"]: s for s in res.policy_sources}
    ceg = [s for s in res.policy_sources if "cap_escalation_gate" in s["source"]][0]
    assert ceg["cap_escalation_authorized"] is False


# ---------------------------------------------------------------------------
# 17, 18 -- protected positions block; protected symbols untouched
# ---------------------------------------------------------------------------


def _protected_positions():
    return [
        DemoOpenPosition(symbol="EDUUSDT", side="short", quantity=827.0,
                         entry_price=1.0, stop_price=1.5),
        DemoOpenPosition(symbol="POLYXUSDT", side="short", quantity=2807.8,
                         entry_price=0.5, stop_price=0.75),
    ]


def test_protected_positions_block_even_with_sol():
    plan, prov = _sol_plan()
    res = gate.evaluate_execution_gate(plan=plan, open_positions=_protected_positions(),
                                       pilot_id=PILOT, date=DATE, forward_fingerprint="fp",
                                       rule_provider=prov)
    assert res.final_execution_authorization_status == \
        gate.NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS
    assert res.existing_protected_position_count == 2
    assert res.execution_candidate_eligible is False


def test_real_vps_scenario_delegates_and_blocks(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _50_action_plan(positions=_protected_positions())
    t = SpyTransport()
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=t,
        output_root=out_root, plan=plan, workbook_builder=fake_workbook_builder)
    assert out["status"] == gate.EXECUTION_DELEGATED_TO_CANONICAL_ONE_SHOT_ADAPTER
    g = out["execution_gate"]
    assert g["final_execution_authorization_status"] == \
        gate.NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS
    assert len(t.posts) == 0


def test_protected_symbols_never_candidates():
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
                                       date=DATE, forward_fingerprint="fp", rule_provider=None)
    assert res.eligible_execution_candidate_count == 0


# ---------------------------------------------------------------------------
# 21, 22 -- Pilot / Forward byte identity
# ---------------------------------------------------------------------------


def test_pilot_state_byte_identical(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    state_path = pathlib.Path(out_root)
    before = {p: p.read_bytes() for p in state_path.rglob("pilot_state.json")}
    assert before
    plan, prov = _50_action_plan(positions=_protected_positions())
    t = SpyTransport()
    daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=t,
        output_root=out_root, plan=plan, workbook_builder=fake_workbook_builder)
    after = {p: p.read_bytes() for p in state_path.rglob("pilot_state.json")}
    assert after == before


def test_no_pilot_advancement(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _50_action_plan()
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=None,
        output_root=out_root, plan=plan)
    assert out["pilot_advanced"] is False
    state = rd.PilotStateStore(PILOT, out_root).read_state()
    assert state["completed_successful_days"] == 0


# ---------------------------------------------------------------------------
# 23 -- no secret material
# ---------------------------------------------------------------------------


def test_no_secret_material_in_output(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _50_action_plan(include_sol=True)
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=None,
        output_root=out_root, plan=plan)
    text = json.dumps(out).lower()
    for sensitive in ("api_key", "api_secret", "bybit_demo_api_key", "bybit_demo_api_secret",
                      "demokey", "demosecret", "x-bapi-sign"):
        assert sensitive not in text


# ---------------------------------------------------------------------------
# 24 (retained planning/audit) -- corrected audit semantics + canonical display
# ---------------------------------------------------------------------------


def _fixture_provider():
    client = DemoReadOnlyClient(allow_real_network=False)
    guard = DemoMarketPriceGuard(allow_real_network=False)
    return daily_cli._build_production_provider(_client=client, _guard=guard)


def test_matched_count_is_requested_not_cache():
    prov = _fixture_provider()
    audit = prov.audit()
    match = prov.match_targets(["BTCUSDT", "ETHUSDT"])
    assert match["requested_target_symbol_count"] == 2
    assert match["matched_instrument_rule_count"] == 2
    assert audit["instrument_rule_cache_count"] >= 2


def test_ticker_get_count_real_and_cached():
    prov = _fixture_provider()
    assert prov.audit()["ticker_public_get_count"] == 0
    prov.market_price("BTCUSDT")
    prov.market_price("BTCUSDT")
    assert prov.audit()["ticker_public_get_count"] == 1


def test_private_get_counts_real():
    prov = _fixture_provider()
    audit = prov.audit()
    assert audit["wallet_private_read_only_get_count"] == 1
    assert audit["positions_private_read_only_get_count"] == 1
    assert audit["order_post_count"] == 0
    assert audit["live_endpoint_called"] is False


def test_provider_rule_evidence_qty_step_from_rule():
    prov = _fixture_provider()
    ev = prov.instrument_rule_evidence("BTCUSDT")
    assert ev["rule_status"] == "TRADING"
    # qty_step comes from the fixture InstrumentSnapshot (0.001), not any action.
    assert float(ev["qty_step"]) == 0.001


def test_canonical_display_no_float_artifact_in_planner():
    prov = FakeProvider(symbols=["ONEINCHUSDT"], prices={"ONEINCHUSDT": 0.07287},
                        steps={"ONEINCHUSDT": 0.1})
    plan = ap.plan_strategy_native_actions(
        forward_result=FakeForward([{"symbol": "ONEINCHUSDT", "side": "long",
                                     "weight": 0.02, "score": 0.02}]), provider=prov)
    for a in plan.actions:
        assert not gate.has_float_artifact(a.qty)


# ---------------------------------------------------------------------------
# Policy-source inventory completeness (F)
# ---------------------------------------------------------------------------


def test_policy_source_inventory_includes_canonical_sources():
    inv = gate.policy_source_inventory()
    sources = " ".join(s["source"] for s in inv)
    assert "SAFETY_POLICY" in sources
    assert "cap_escalation_gate" in sources
    assert "one_shot_authorized_execution_orchestrator" in sources
    assert "tiny_execution_adapter" in sources
    assert "PROTECTED_SYMBOLS" in sources
    # cap escalation + one-shot real order explicitly NOT authorized here.
    ceg = [s for s in inv if "cap_escalation_gate" in s["source"]][0]
    osh_s = [s for s in inv if "one_shot_authorized_execution_orchestrator" in s["source"]][0]
    assert ceg["cap_escalation_authorized"] is False
    assert osh_s["real_order_authorized"] is False


# ===========================================================================
# TASK-014CB_FIX2 -- audit schema: candidate counts, dispatcher call counts,
# decimal output canonicalization, authorization-marker redaction.
# ===========================================================================

import re as _re  # noqa: E402

_REAL_ORDER_MARKER_VALUE = osh.EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER
_CAP_MARKER_VALUE = ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER
_ARTIFACT_RE = _re.compile(r"\d\.\d*(?:000000000000|999999999999)\d*")


def _iter_strings(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _iter_strings(k)
            yield from _iter_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_strings(v)
    else:
        yield str(obj)


def _has_float_artifact_anywhere(obj) -> bool:
    return any(_ARTIFACT_RE.search(s) for s in _iter_strings(obj))


def _50_plan_with_sol_and_protected():
    plan, prov = _50_action_plan(positions=_protected_positions(), include_sol=True)
    return plan, prov


# --- corrected candidate-count semantics -----------------------------------


def test_candidate_counts_explicit_for_vps_scenario():
    plan, prov = _50_plan_with_sol_and_protected()
    res = gate.evaluate_execution_gate(
        plan=plan, open_positions=_protected_positions(), pilot_id=PILOT, date=DATE,
        forward_fingerprint="fp", rule_provider=prov)
    d = res.to_dict()
    assert d["raw_planned_action_count"] == 50
    assert d["canonical_adapter_supported_candidate_count"] == 1
    assert d["rule_valid_supported_candidate_count"] == 1
    assert d["policy_eligible_candidate_count"] == 0
    assert d["selected_review_candidate_count"] == 1
    assert d["execution_candidate_eligible"] is False


def test_legacy_eligible_count_is_not_raw_count():
    plan, prov = _50_plan_with_sol_and_protected()
    res = gate.evaluate_execution_gate(
        plan=plan, open_positions=_protected_positions(), pilot_id=PILOT, date=DATE,
        forward_fingerprint="fp", rule_provider=prov)
    d = res.to_dict()
    assert d["eligible_execution_candidate_count"] != 50
    assert d["eligible_execution_candidate_count"] == d["policy_eligible_candidate_count"]
    assert "POLICY_ELIGIBLE_COUNT" in d["eligible_execution_candidate_count_semantics"]


def test_sol_is_only_canonical_supported_action():
    plan, prov = _50_action_plan(include_sol=True)
    res = gate.evaluate_execution_gate(
        plan=plan, open_positions=[], pilot_id=PILOT, date=DATE,
        forward_fingerprint="fp", rule_provider=prov)
    assert res.canonical_adapter_supported_candidate_count == 1
    assert res.requested_symbol == "SOLUSDT"


# --- explicit dispatcher call-count fields ---------------------------------


def test_dispatcher_call_count_fields_present(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _50_action_plan(include_sol=True)
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=None,
        output_root=out_root, plan=plan)
    assert out["execute_daily_native_called"] is False
    assert out["execute_daily_native_call_count"] == 0
    assert out["transport_sender_call_count"] == 0
    assert out["order_post_count"] == 0
    assert out["amend_post_count"] == 0
    assert out["cancel_post_count"] == 0
    assert out["live_endpoint_called"] is False


# --- decimal output canonicalization ---------------------------------------


def test_target_positions_no_float_artifact():
    # ONEINCHUSDT @ 0.07287 with step 0.1 would yield 2744.6000000000004 naively.
    prov = FakeProvider(symbols=["ONEINCHUSDT"], prices={"ONEINCHUSDT": 0.07287},
                        steps={"ONEINCHUSDT": 0.1})
    plan = ap.plan_strategy_native_actions(
        forward_result=FakeForward([{"symbol": "ONEINCHUSDT", "side": "long",
                                     "weight": 0.02, "score": 0.02}]), provider=prov)
    d = plan.to_dict()
    assert not _has_float_artifact_anywhere(d["target_positions"])
    assert not _has_float_artifact_anywhere(d["actions"])
    tp = d["target_positions"][0]
    assert tp["qty"] == "2744.6"
    assert isinstance(tp["qty"], str) and isinstance(tp["target_notional"], str)
    assert tp["target_weight"] == "0.02"


def test_full_plan_only_json_has_no_float_artifacts():
    plan, prov = _50_action_plan(include_sol=True,
                                 positions=_protected_positions())
    res = gate.evaluate_execution_gate(
        plan=plan, open_positions=_protected_positions(), pilot_id=PILOT, date=DATE,
        forward_fingerprint="fp", rule_provider=prov)
    payload = {"planner": plan.to_dict(), "execution_gate": res.to_dict()}
    assert not _has_float_artifact_anywhere(payload)


def test_rule_evidence_quantities_canonical():
    plan, prov = _sol_plan(sol_step=0.1)
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="fp", rule_provider=prov)
    ev = res.rule_evidence
    assert not _has_float_artifact_anywhere(ev)
    assert ev["qty_step"] == "0.1"


def test_action_quantities_remain_canonical_strings():
    plan, prov = _50_action_plan(include_sol=True)
    for a in plan.to_dict()["actions"]:
        assert isinstance(a["qty"], str)
        assert not gate.has_float_artifact(a["qty"])


# --- authorization-marker redaction ----------------------------------------


def test_marker_names_present_values_absent_in_gate():
    plan, prov = _sol_plan()
    res = gate.evaluate_execution_gate(plan=plan, open_positions=[], pilot_id=PILOT,
                                       date=DATE, forward_fingerprint="fp", rule_provider=prov)
    text = json.dumps(res.to_dict())
    assert "EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER" in text
    assert "EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER" in text
    assert _REAL_ORDER_MARKER_VALUE not in text
    assert _CAP_MARKER_VALUE not in text


def test_no_marker_value_in_full_plan_only_payload(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _50_action_plan(include_sol=True)
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=None,
        output_root=out_root, plan=plan)
    text = json.dumps(out)
    assert _REAL_ORDER_MARKER_VALUE not in text
    assert _CAP_MARKER_VALUE not in text
    # marker NAMES still present for audit.
    assert "EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER" in text


def test_policy_sources_redact_marker_values():
    inv = gate.policy_source_inventory()
    text = json.dumps(inv)
    assert _REAL_ORDER_MARKER_VALUE not in text
    assert _CAP_MARKER_VALUE not in text
    ceg = [s for s in inv if "cap_escalation_gate" in s["source"]][0]
    assert ceg["cap_escalation_authorization_marker_name"] == "EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER"
    assert "cap_escalation_marker" not in ceg  # the old VALUE key is gone


def test_no_api_secret_in_full_payload(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    plan, prov = _50_action_plan(include_sol=True)
    out = daily_cli.orchestrate_gated_send(
        pilot_id=PILOT, date=DATE, forward_result=None, provider=prov, transport=None,
        output_root=out_root, plan=plan)
    text = json.dumps(out).lower()
    for sensitive in ("demokey", "demosecret", "bybit_demo_api_key", "bybit_demo_api_secret",
                      "x-bapi-sign"):
        assert sensitive not in text
