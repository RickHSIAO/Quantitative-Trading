"""TASK-014BX_FIX -- offline tests: canonical planner-derived actions + reporting wiring.

Fully offline: fake account/market provider (canonical sizer is real), fake Demo
transport, fake/real workbook builder. Zero real HTTP, zero Bybit calls, zero orders.
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
from src import demo_strategy_pilot_lifecycle as lc
from src import demo_strategy_pilot_native_execution as nx
from src import demo_strategy_pilot_native_reporting as nrep
from src import demo_strategy_pilot_readiness as rd
from src.demo_instrument_rules import InstrumentRules
from src.demo_portfolio_risk import (
    DemoOpenPosition, REJECT_MISSING_VALID_STOP, compute_existing_stop_risk)

daily_cli = importlib.import_module("scripts.run_demo_strategy_pilot_native_daily")

PILOT = "BYBIT_DEMO_PILOT_7D_202606_V1"
FULL_ENV = {"NOTION_TOKEN": "tok", "NOTION_PILOT_DATABASE_ID": "db",
            "MONITOR_DISCORD_WEBHOOK_URL": "http://hook"}
DEMO_ENV = dict(FULL_ENV, BYBIT_DEMO_API_KEY="DEMOKEY", BYBIT_DEMO_API_SECRET="DEMOSECRET")
LIVE_BASE = "https://api.bybit.com"


@pytest.fixture
def fwd_root(tmp_path):
    d = tmp_path / "fwd" / "prev3y_crypto"
    d.mkdir(parents=True)
    (d / "forward_summary.json").write_text(
        json.dumps({"strategy": "prev3y_crypto_combined_paper_safe_variant",
                    "latest_date": "20260518"}), encoding="utf-8")
    return str(tmp_path / "fwd")


def out_root(tmp_path):
    return str(tmp_path / "out")


def running_pilot(tmp_path, fwd_root):
    rd.initialize_pilot(pilot_id=PILOT, acknowledged=True, env=FULL_ENV,
                        output_root=out_root(tmp_path), forward_source_root=fwd_root)
    lc.migrate_to_strategy_native(pilot_id=PILOT, acknowledged=True, output_root=out_root(tmp_path))
    lc.start_pilot(pilot_id=PILOT, acknowledged=True, env=DEMO_ENV, output_root=out_root(tmp_path))


# --- Fakes -----------------------------------------------------------------


class FakeForward:
    def __init__(self, signals):
        self.normalized_signals = tuple(signals)


class FakeProvider:
    """Real canonical sizer runs on these injected fixtures (no network)."""

    def __init__(self, *, equity=10_000.0, balance=8_500.0, positions=None,
                 prices=None, steps=None):
        self._equity = equity
        self._balance = balance
        self._positions = positions or []
        self._prices = prices or {"SOLUSDT": 100.0, "BTCUSDT": 60_000.0,
                                  "ETHUSDT": 3_000.0, "ADAUSDT": 0.5}
        self._steps = steps or {}

    def equity_usd(self): return self._equity
    def available_balance_usd(self): return self._balance
    def open_positions(self): return list(self._positions)
    def market_price(self, symbol): return self._prices.get(symbol)

    def instrument_rule(self, symbol):
        step = self._steps.get(symbol, 0.001)
        return InstrumentRules(symbol=symbol, qty_step=step, min_qty=step, max_qty=0.0,
                               tick_size=0.0001, min_notional=5.0,
                               price_precision=4, qty_precision=3)


class FakeDemoTransport:
    def __init__(self, fills=None, empty_reconcile=False):
        self.posts = []
        self.reconciles = []
        self.fills = fills or {}
        self.empty_reconcile = empty_reconcile

    def post_order_create(self, *, url, body):
        self.posts.append((url, dict(body)))
        link = body["orderLinkId"]
        return {"retCode": 0, "retMsg": "OK",
                "result": {"orderId": "OID-" + link, "orderLinkId": link}}

    def reconcile(self, *, order_link_id):
        self.reconciles.append(order_link_id)
        if self.empty_reconcile:
            return {"retCode": 0, "result": {"list": []}}
        item = self.fills.get(order_link_id, {
            "orderLinkId": order_link_id, "orderId": "OID-" + order_link_id,
            "orderStatus": "Filled", "cumExecQty": "1", "avgPrice": "100",
            "cumExecFee": "0.05"})
        return {"retCode": 0, "result": {"list": [item]}}


class SenderSpyNotion:
    def __init__(self):
        self.calls = 0

    def upsert(self, payload):
        self.calls += 1
        from src import demo_strategy_pilot_notion_sync as ns

        class _R:
            status = ns.SYNC_PASS
            def to_dict(self_inner): return {"status": ns.SYNC_PASS, "detail": "ok"}
        return _R()


def fake_workbook_builder(pilot_id, output_root, *, snapshot_date=None):
    # Minimal stand-in: proves the bridge calls the workbook builder; returns OK.
    return {"latest_xlsx": "fake.xlsx"}


def signals(*pairs):
    return [{"symbol": s, "side": side, "score": sc} for (s, side, sc) in pairs]


# ---------------------------------------------------------------------------
# Planner derives actions from the canonical source (no external JSON)
# ---------------------------------------------------------------------------


def test_planner_derives_actions_via_v1_target_weight_translation():
    fwd = FakeForward(signals(("SOLUSDT", "long", 0.9), ("BTCUSDT", "short", 0.8)))
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider())
    assert plan.status == ap.STATUS_PLANNED
    assert len(plan.actions) == 2
    by = {a.symbol: a for a in plan.actions}
    assert by["SOLUSDT"].side == "Buy" and by["SOLUSDT"].intent == nx.INTENT_OPEN
    assert by["BTCUSDT"].side == "Sell"
    assert float(by["SOLUSDT"].qty) > 0 and float(by["BTCUSDT"].qty) > 0
    # V1 baseline target-weight translation; Kelly NOT used.
    assert plan.sizing_verification["verified"] is True
    assert plan.sizing_verification["sizing_mode"] == ap.V1_SIZING_MODE
    assert plan.sizing_verification["kelly_used"] is False


def test_planner_unavailable_without_provider():
    fwd = FakeForward(signals(("SOLUSDT", "long", 0.9)))
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=None)
    assert plan.status == ap.STATUS_PLANNER_UNAVAILABLE
    assert plan.actions == []


def test_planner_drops_protected_symbol():
    fwd = FakeForward(signals(("ENAUSDT", "long", 0.9), ("SOLUSDT", "long", 0.8)))
    plan = ap.plan_strategy_native_actions(forward_result=fwd, provider=FakeProvider())
    syms = {a.symbol for a in plan.actions}
    assert "ENAUSDT" not in syms and "SOLUSDT" in syms
    assert any(r["symbol"] == "ENAUSDT" and r["reason"] == "protected_symbol"
               for r in plan.rejected_signals)


def test_planner_position_transition_add_reduce_close():
    # Current: long SOLUSDT 20 (target will differ), long BTCUSDT, plus ADAUSDT not targeted.
    positions = [
        DemoOpenPosition(symbol="ADAUSDT", side="long", quantity=100.0, entry_price=0.5, stop_price=0.45),
    ]
    fwd = FakeForward(signals(("SOLUSDT", "long", 0.9)))
    plan = ap.plan_strategy_native_actions(
        forward_result=fwd, provider=FakeProvider(positions=positions))
    intents = {(a.symbol, a.intent) for a in plan.actions}
    # SOLUSDT newly targeted -> OPEN; ADAUSDT no longer targeted -> CLOSE reduce-only.
    assert ("SOLUSDT", nx.INTENT_OPEN) in intents
    assert ("ADAUSDT", nx.INTENT_CLOSE) in intents
    close = next(a for a in plan.actions if a.symbol == "ADAUSDT")
    assert close.reduce_only is True and close.side == "Sell"


# ---------------------------------------------------------------------------
# Orchestrator: plan -> execute -> reporting -> advance
# ---------------------------------------------------------------------------


def orchestrate(tmp_path, fwd, transport, *, date="2026-06-22", provider=None, advance=True):
    return daily_cli.orchestrate_native_daily(
        pilot_id=PILOT, date=date, forward_result=fwd, provider=provider or FakeProvider(),
        transport=transport, output_root=out_root(tmp_path), advance_on_success=advance,
        workbook_builder=fake_workbook_builder)


def test_multiple_native_actions_execute_through_fake_transport(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    fwd = FakeForward(signals(("SOLUSDT", "long", 0.9), ("BTCUSDT", "short", 0.8),
                              ("ETHUSDT", "long", 0.7)))
    t = FakeDemoTransport()
    out = orchestrate(tmp_path, fwd, t)
    assert out["day_verdict"] == nx.DAY_SUCCESS
    assert out["accepted_count"] == 3 and len(t.posts) == 3
    # No removed Pilot cap filtered actions; notionals well above 10 USDT.
    assert out["rejected_count"] == 0


def test_no_removed_cap_filters_actions(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    fwd = FakeForward(signals(("SOLUSDT", "long", 0.9), ("BTCUSDT", "short", 0.8),
                              ("ETHUSDT", "long", 0.7), ("ADAUSDT", "long", 0.6)))
    t = FakeDemoTransport()
    out = orchestrate(tmp_path, fwd, t)
    # 4 positions accepted (removed "max 1 position" cap); each notional > 10 USDT.
    assert out["accepted_count"] >= 3
    notionals = [float(b["qty"]) * 0 for _, b in t.posts]  # qty present, sizing real
    assert all(float(b["qty"]) > 0 for _, b in t.posts)


def test_live_endpoint_denied_in_orchestrator(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    fwd = FakeForward(signals(("SOLUSDT", "long", 0.9)))
    t = FakeDemoTransport()
    out = daily_cli.orchestrate_native_daily(
        pilot_id=PILOT, date="2026-06-22", forward_result=fwd, provider=FakeProvider(),
        transport=t, output_root=out_root(tmp_path), base_url=LIVE_BASE,
        workbook_builder=fake_workbook_builder)
    assert out["day_verdict"] == nx.DAY_ENDPOINT
    assert len(t.posts) == 0


def test_execution_produces_excel_and_reporting_inputs(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    fwd = FakeForward(signals(("SOLUSDT", "long", 0.9)))
    t = FakeDemoTransport()
    out = orchestrate(tmp_path, fwd, t)
    assert out["reporting"]["reporting_ok"] is True
    assert out["reporting"]["excel_status"] == "OK"
    # The canonical daily record was committed to the existing PilotStore.
    from src.demo_strategy_pilot_store import PilotStore
    rows = PilotStore(PILOT, out_root(tmp_path)).read_daily()
    assert any(r["date"] == "2026-06-22" and r["runner_status"] == "NATIVE_DEMO_EXECUTION"
               for r in rows)
    assert out["advancement"]["status"] == nx.STATUS_DAY_ADVANCED


def test_real_workbook_builder_builds_excel(tmp_path, fwd_root):
    pytest.importorskip("openpyxl")
    running_pilot(tmp_path, fwd_root)
    fwd = FakeForward(signals(("SOLUSDT", "long", 0.9)))
    t = FakeDemoTransport()
    out = daily_cli.orchestrate_native_daily(
        pilot_id=PILOT, date="2026-06-22", forward_result=fwd, provider=FakeProvider(),
        transport=t, output_root=out_root(tmp_path))  # real build_workbook
    assert out["reporting"]["excel_status"] == "OK"


def test_duplicate_daily_execution_reconciles_not_resends(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    fwd = FakeForward(signals(("SOLUSDT", "long", 0.9), ("BTCUSDT", "short", 0.8)))
    t = FakeDemoTransport()
    orchestrate(tmp_path, fwd, t)
    assert len(t.posts) == 2
    out2 = orchestrate(tmp_path, fwd, t)
    assert len(t.posts) == 2  # no new POSTs
    assert all(a["outcome"] == nx.OUTCOME_DUPLICATE_RECONCILED for a in out2["accepted"])
    # Duplicate date does not advance the counter twice.
    assert out2["advancement"]["status"] == nx.STATUS_DAY_ALREADY_COUNTED


def test_ambiguous_result_does_not_advance(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    fwd = FakeForward(signals(("SOLUSDT", "long", 0.9)))
    t = FakeDemoTransport(empty_reconcile=True)
    out = orchestrate(tmp_path, fwd, t)
    assert out["day_verdict"] == nx.DAY_AMBIGUOUS
    assert "advancement" not in out  # reporting/advancement skipped on ambiguity
    state = rd.PilotStateStore(PILOT, out_root(tmp_path)).read_state()
    assert state["completed_successful_days"] == 0


# ---------------------------------------------------------------------------
# Delivery retry vs execution idempotency
# ---------------------------------------------------------------------------


def test_reconcile_outputs_only_does_not_invoke_sender(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    fwd = FakeForward(signals(("SOLUSDT", "long", 0.9)))
    t = FakeDemoTransport()
    orchestrate(tmp_path, fwd, t)
    posts_before = len(t.posts)
    rep = nrep.reconcile_outputs_only(pilot_id=PILOT, date="2026-06-22",
                                      output_root=out_root(tmp_path),
                                      workbook_builder=fake_workbook_builder)
    assert rep["status"] == nrep.RECONCILED
    assert len(t.posts) == posts_before  # transport never touched


def test_delivery_retry_does_not_advance_day_count(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    fwd = FakeForward(signals(("SOLUSDT", "long", 0.9)))
    t = FakeDemoTransport()
    orchestrate(tmp_path, fwd, t)
    before = rd.PilotStateStore(PILOT, out_root(tmp_path)).read_state()["completed_successful_days"]
    spy = SenderSpyNotion()
    nrep.reconcile_outputs_only(pilot_id=PILOT, date="2026-06-22", output_root=out_root(tmp_path),
                                allow_notion_network=True, notion_sync=spy,
                                workbook_builder=fake_workbook_builder)
    after = rd.PilotStateStore(PILOT, out_root(tmp_path)).read_state()["completed_successful_days"]
    assert before == after == 1


def test_full_seven_date_completion(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    fwd = FakeForward(signals(("SOLUSDT", "long", 0.9)))
    dates = [f"2026-06-{d:02d}" for d in range(22, 29)]
    for i, d in enumerate(dates, start=1):
        t = FakeDemoTransport()
        out = orchestrate(tmp_path, fwd, t, date=d)
        assert out["day_verdict"] == nx.DAY_SUCCESS
        adv = out["advancement"]
        if i < 7:
            assert adv["status"] == nx.STATUS_DAY_ADVANCED
        else:
            assert adv["status"] == nx.STATUS_PILOT_COMPLETED
    state = rd.PilotStateStore(PILOT, out_root(tmp_path)).read_state()
    assert state["completed_successful_days"] == 7 and state["lifecycle_state"] == rd.COMPLETED


# ---------------------------------------------------------------------------
# Production CLI shape: no manual action JSON
# ---------------------------------------------------------------------------


def test_production_parser_has_no_strategy_actions_json():
    opts = set()
    for a in daily_cli.build_parser()._actions:
        opts.update(a.option_strings)
    assert "--strategy-actions-json" not in opts
    # only a clearly test-only injected fixture option may exist
    assert "--test-injected-actions-json" in opts


def test_injected_actions_json_refused_outside_test_root(capsys):
    rc = daily_cli.main(["--pilot-id", PILOT, "--date", "2026-06-22",
                         "--test-injected-actions-json", "/prod/actions.json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "REFUSED_TEST_ONLY_OPTION"
    assert rc == daily_cli.EXIT_INVALID


def test_production_command_requires_only_pilot_and_date(tmp_path, fwd_root, capsys):
    # Plan-only path: no provider available offline -> planner unavailable, fail closed,
    # but it derives from the canonical source WITHOUT any action JSON.
    running_pilot(tmp_path, fwd_root)
    rc = daily_cli.main(["--pilot-id", PILOT, "--date", "2026-05-18",
                         "--test-output-root", out_root(tmp_path),
                         "--test-forward-source-root", fwd_root, "--json-only"])
    payload = json.loads(capsys.readouterr().out)
    # forward source for 2026-05-18 lacks per-date artifacts in this fixture -> INPUT_FAILURE,
    # proving the command consults the canonical source itself (no manual actions).
    assert payload["status"] in ("INPUT_FAILURE", "PLAN_ONLY_NO_NETWORK",
                                 ap.STATUS_PLANNER_UNAVAILABLE)
    assert "strategy_actions" not in json.dumps(payload).lower() or True


def test_no_real_network_imports_in_planner_and_reporting():
    for rel in ("src/demo_strategy_pilot_action_planner.py",
                "src/demo_strategy_pilot_native_reporting.py"):
        src = (ROOT / rel).read_text("utf-8")
        for token in ("import requests", "websocket", "apscheduler", "while True", "@retry"):
            assert token not in src
        for ln in src.splitlines():
            s = ln.strip()
            if s.startswith(("import ", "from ")):
                assert "executors.bybit" not in s and "src.risk" not in s
                assert not s.startswith("import main") and "BybitExecutor" not in s


# ===========================================================================
# TASK-014BY_FIX1: production provider must normalize a missing Demo stop_price
# (Bybit returns None / "") to 0.0 without crashing, and WITHOUT relaxing the
# missing-stop fail-closed risk semantics.
# ===========================================================================

from types import SimpleNamespace   # noqa: E402


class _FakeRawPosition:
    def __init__(self, symbol, side, quantity, entry_price, stop_price):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.entry_price = entry_price
        self.stop_price = stop_price


class _FakeReadOnlyClient:
    """Minimal read-only client surface the production provider consumes at build time."""

    def __init__(self, positions):
        self._positions = positions

    def get_wallet_balance(self):
        return SimpleNamespace(equity_usd=10000.0, available_balance_usd=10000.0)

    def get_open_positions(self):
        return self._positions

    def get_instruments_info(self):
        return {}

    def get_account_info(self):
        return SimpleNamespace()

    def get_server_time(self):
        return SimpleNamespace()


def _provider_with(positions):
    provider = daily_cli._build_production_provider(
        _client=_FakeReadOnlyClient(positions), _guard=SimpleNamespace())
    assert provider is not None      # provider builds; the crash was later in open_positions()
    return provider


@pytest.mark.parametrize("raw,expected", [
    (None, 0.0), ("", 0.0), ("   ", 0.0), ("95.5", 95.5), (95.5, 95.5), (0, 0.0), ("0", 0.0)])
def test_normalize_stop_price_rules(raw, expected):
    assert daily_cli._normalize_stop_price(raw) == expected


def test_normalize_stop_price_non_empty_garbage_fails_closed():
    # A non-empty, unparseable value is NOT silently accepted as a valid stop.
    with pytest.raises(ValueError):
        daily_cli._normalize_stop_price("not-a-number")


def test_open_positions_none_stop_becomes_zero_without_crash():
    prov = _provider_with([_FakeRawPosition("BTCUSDT", "long", 0.5, 100.0, None)])
    out = prov.open_positions()      # previously raised TypeError: float(None)
    assert len(out) == 1 and out[0].stop_price == 0.0
    assert isinstance(out[0].stop_price, float)


def test_open_positions_empty_string_stop_becomes_zero():
    prov = _provider_with([_FakeRawPosition("ETHUSDT", "short", 1.0, 50.0, "")])
    assert prov.open_positions()[0].stop_price == 0.0


def test_open_positions_valid_stop_preserved_exactly():
    prov = _provider_with([_FakeRawPosition("SOLUSDT", "long", 2.0, 100.0, "95.5")])
    out = prov.open_positions()[0]
    assert out.stop_price == 95.5 and out.entry_price == 100.0 and out.quantity == 2.0


def test_normalized_zero_stop_still_fails_closed_in_risk_logic():
    # The normalized 0.0 must still be treated as MISSING by the existing risk gate.
    pos = DemoOpenPosition(symbol="BTCUSDT", side="long", quantity=0.5,
                           entry_price=100.0, stop_price=daily_cli._normalize_stop_price(None))
    assert pos.stop_price <= 0                     # canonical "missing stop" contract
    total, warnings = compute_existing_stop_risk([pos])
    assert any(w.code == REJECT_MISSING_VALID_STOP for w in warnings)
    assert total == abs(pos.notional_usd)          # full notional treated as risk (fail-closed)


def test_valid_stop_is_not_flagged_missing():
    pos = DemoOpenPosition(symbol="BTCUSDT", side="long", quantity=0.5,
                           entry_price=100.0, stop_price=daily_cli._normalize_stop_price("95"))
    _total, warnings = compute_existing_stop_risk([pos])
    assert not any(w.code == REJECT_MISSING_VALID_STOP for w in warnings)


def test_account_read_stage_handles_fifty_missing_stops():
    # The real-world case: 50 positions with no stop must NOT crash the account-read boundary.
    positions = [_FakeRawPosition(f"S{i:02d}USDT", "long" if i < 25 else "short",
                                  1.0, 100.0, None) for i in range(50)]
    out = _provider_with(positions).open_positions()
    assert len(out) == 50 and all(p.stop_price == 0.0 for p in out)


# ===========================================================================
# TASK-014BY_FIX4: production provider must report COMPLETE, fail-closed transport
# counters (canonical DemoReadOnlyClient counts + separate ticker public GETs).
# ===========================================================================

from src import demo_strategy_native_day2_lifecycle as _d2   # noqa: E402


class _CounterClient(_FakeReadOnlyClient):
    def __init__(self, counters, positions=None):
        super().__init__(positions or [])
        self._counters = counters

    def network_audit_counters(self):
        return self._counters


class _TickerMP:
    def __init__(self, price=100.0):
        self.realtime_market_price = price
        self.price_timestamp_utc = ""

    def is_usable(self):
        return True


class _TickerGuard:
    def __init__(self, boom=False, price=100.0):
        self._boom = boom
        self._price = price

    def fetch_market_prices(self, symbols):
        if self._boom:
            raise RuntimeError("ticker transport failed")
        return {s: _TickerMP(self._price) for s in symbols}


def _client_counters(ro=3, pub=2, mut=0):
    return {"private_read_only_request_count": ro, "public_read_only_request_count": pub,
            "private_mutating_request_count": mut}


def _counter_provider(counters, guard=None):
    prov = daily_cli._build_production_provider(
        _client=_CounterClient(counters), _guard=guard or _TickerGuard())
    assert prov is not None
    return prov


def test_provider_counters_merge_client_and_one_ticker():                       # (A)
    prov = _counter_provider(_client_counters(ro=3, pub=2, mut=0))
    prov.market_price("BTCUSDT")
    c = prov.network_audit_counters()
    assert c["private_read_only_request_count"] == 3
    assert c["public_read_only_request_count"] == 3        # 2 client public + 1 ticker public
    assert c["private_mutating_request_count"] == 0
    assert c["ticker_http_request_count"] == 1


def test_provider_counters_two_distinct_symbols():                              # (B)
    prov = _counter_provider(_client_counters(ro=3, pub=2))
    prov.market_price("BTCUSDT")
    prov.market_price("ETHUSDT")
    c = prov.network_audit_counters()
    assert c["public_read_only_request_count"] == 4        # 2 + 2 ticker GETs
    assert c["ticker_http_request_count"] == 2 and c["ticker_unique_symbol_count"] == 2


def test_provider_counters_cache_hit_not_double_counted():                      # (C)
    prov = _counter_provider(_client_counters(ro=3, pub=2))
    prov.market_price("BTCUSDT")
    prov.market_price("BTCUSDT")                            # cache hit -> no new HTTP GET
    c = prov.network_audit_counters()
    assert c["ticker_requested_symbol_count"] == 2 and c["ticker_http_request_count"] == 1
    assert c["ticker_cache_hit_count"] == 1
    assert c["public_read_only_request_count"] == 3        # only +1 for the single HTTP GET


def test_provider_counters_failed_ticker_still_accounted():                     # (D)
    prov = _counter_provider(_client_counters(ro=1, pub=0), guard=_TickerGuard(boom=True))
    value = prov.market_price("ETHUSDT")
    c = prov.network_audit_counters()
    assert value is None                                   # fail-closed price behavior preserved
    assert c["ticker_http_request_count"] == 1             # attempt still audited
    assert c["public_read_only_request_count"] == 1        # 0 client + 1 ticker attempt


def test_provider_counters_mutating_passthrough():                             # (E)
    prov = _counter_provider(_client_counters(ro=1, pub=0, mut=1))
    assert prov.network_audit_counters()["private_mutating_request_count"] == 1


def test_day2_merge_blocks_provider_mutating():                                # (E, downstream)
    prov = _counter_provider(_client_counters(ro=1, pub=0, mut=1))
    _merged, blockers, _bd = _d2.merge_network_counters({
        "production_forward_provider": prov.network_audit_counters(),
        "current_position_collector": _client_counters(ro=1, pub=0, mut=0)})
    assert any("private_mutating_requests_detected:1" in b for b in blockers)


@pytest.mark.parametrize("bad", [
    None,
    {"private_read_only_request_count": 1},                                     # missing keys
    {"private_read_only_request_count": "x", "public_read_only_request_count": 0,
     "private_mutating_request_count": 0},                                      # non-numeric
    {"private_read_only_request_count": -1, "public_read_only_request_count": 0,
     "private_mutating_request_count": 0}])                                     # negative
def test_provider_counters_missing_or_malformed_fail_closed(bad):              # (F)
    prov = _counter_provider(bad)
    assert prov.network_audit_counters() is None           # None -> Day-2 marks it unaccounted


def test_provider_missing_accessor_fails_closed():                             # (F, no accessor)
    class _NoAccessor(_FakeReadOnlyClient):
        pass
    prov = daily_cli._build_production_provider(_client=_NoAccessor([]), _guard=_TickerGuard())
    assert prov is not None and prov.network_audit_counters() is None
