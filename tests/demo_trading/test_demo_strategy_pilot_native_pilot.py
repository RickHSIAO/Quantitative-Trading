"""TASK-014BX -- offline tests for strategy-native start + Bybit Demo execution.

Fully offline: fake transports only, temp roots, presence-only credential checks
via injected env. Zero real network calls; zero real orders.
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

from src import demo_strategy_pilot_lifecycle as lc
from src import demo_strategy_pilot_native_execution as nx
from src import demo_strategy_pilot_readiness as rd

cli = importlib.import_module("scripts.manage_demo_strategy_pilot")

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


def init_inactive(tmp_path, fwd_root):
    return rd.initialize_pilot(pilot_id=PILOT, acknowledged=True, env=FULL_ENV,
                               output_root=out_root(tmp_path), forward_source_root=fwd_root)


def migrate(tmp_path):
    return lc.migrate_to_strategy_native(pilot_id=PILOT, acknowledged=True,
                                         output_root=out_root(tmp_path))


def start(tmp_path, *, env=None, ack=True):
    return lc.start_pilot(pilot_id=PILOT, acknowledged=ack, env=DEMO_ENV if env is None else env,
                          output_root=out_root(tmp_path))


def running_pilot(tmp_path, fwd_root):
    init_inactive(tmp_path, fwd_root)
    migrate(tmp_path)
    return start(tmp_path)


class FakeDemoTransport:
    def __init__(self, fills=None, raise_on_post=False, empty_reconcile=False):
        self.posts = []
        self.reconciles = []
        self.fills = fills or {}
        self.raise_on_post = raise_on_post
        self.empty_reconcile = empty_reconcile

    def post_order_create(self, *, url, body):
        if self.raise_on_post:
            raise TimeoutError("simulated ambiguous timeout")
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
            "cumExecFee": "0.01"})
        return {"retCode": 0, "result": {"list": [item]}}


def act(symbol, side="Buy", qty="1", **kw):
    return nx.StrategyNativeAction(symbol=symbol, side=side, qty=qty, **kw)


# ---------------------------------------------------------------------------
# Policy: removed artificial caps
# ---------------------------------------------------------------------------


def test_active_policy_has_no_artificial_caps():
    p = lc.STRATEGY_NATIVE_SAFETY_POLICY
    for k in lc.REMOVED_ARTIFICIAL_CAP_KEYS:
        assert k not in p
    assert p["extra_pilot_business_caps"] == "NONE"
    assert lc.policy_is_strategy_native(p) is True
    assert lc.policy_has_artificial_caps(p) is False
    assert p["live_endpoint"] == "PERMANENTLY_DENIED"


def test_old_readiness_policy_detected_as_having_caps():
    assert lc.policy_has_artificial_caps(rd.SAFETY_POLICY) is True
    assert lc.policy_is_strategy_native(rd.SAFETY_POLICY) is False


def test_migrated_state_drops_caps_and_preserves_original_fingerprint(tmp_path, fwd_root):
    init_inactive(tmp_path, fwd_root)
    before = rd.PilotStateStore(PILOT, out_root(tmp_path)).read_state()
    original_fp = before["configuration_fingerprint"]
    r = migrate(tmp_path)
    assert r["status"] == lc.STATUS_MIGRATED
    state = rd.PilotStateStore(PILOT, out_root(tmp_path)).read_state()
    assert lc.policy_is_strategy_native(state["policy"]) is True
    assert state["original_configuration_fingerprint"] == original_fp
    assert state["configuration_fingerprint"] == lc.strategy_native_fingerprint(PILOT)
    for k in lc.REMOVED_ARTIFICIAL_CAP_KEYS:
        assert k not in state["policy"]


def test_migration_idempotent_single_event(tmp_path, fwd_root):
    init_inactive(tmp_path, fwd_root)
    migrate(tmp_path)
    r2 = migrate(tmp_path)
    assert r2["status"] == lc.STATUS_ALREADY_MIGRATED
    store = rd.PilotStateStore(PILOT, out_root(tmp_path))
    # INITIALIZE + one MIGRATION = 2 events; no duplicate MIGRATION.
    events = store.events_path.read_text(encoding="utf-8").splitlines()
    assert sum(1 for e in events if '"MIGRATION"' in e) == 1


def test_migration_requires_acknowledgement(tmp_path, fwd_root):
    init_inactive(tmp_path, fwd_root)
    r = lc.migrate_to_strategy_native(pilot_id=PILOT, acknowledged=False,
                                      output_root=out_root(tmp_path))
    assert r["status"] == lc.STATUS_REFUSED_NOT_ACKNOWLEDGED


# ---------------------------------------------------------------------------
# Start authorization
# ---------------------------------------------------------------------------


def test_start_requires_exact_acknowledgement(tmp_path, fwd_root):
    init_inactive(tmp_path, fwd_root)
    migrate(tmp_path)
    r = start(tmp_path, ack=False)
    assert r["status"] == lc.STATUS_REFUSED_NOT_ACKNOWLEDGED
    assert r["live_trading_authorized"] is False


def test_start_requires_existing_inactive_state(tmp_path):
    r = start(tmp_path)
    assert r["status"] == lc.STATUS_NOT_INITIALIZED


def test_start_requires_demo_credentials(tmp_path, fwd_root):
    init_inactive(tmp_path, fwd_root)
    migrate(tmp_path)
    r = start(tmp_path, env=FULL_ENV)  # no demo creds
    assert r["status"] == lc.STATUS_REFUSED_MISSING_DEMO_CREDENTIALS
    assert r["live_trading_authorized"] is False


def test_start_requires_migrated_policy(tmp_path, fwd_root):
    init_inactive(tmp_path, fwd_root)  # not migrated
    r = start(tmp_path)
    assert r["status"] == lc.STATUS_REFUSED_POLICY_NOT_MIGRATED


def test_start_transitions_inactive_to_running(tmp_path, fwd_root):
    r = running_pilot(tmp_path, fwd_root)
    assert r["status"] == lc.STATUS_STARTED
    assert r["lifecycle_state"] == rd.RUNNING
    state = rd.PilotStateStore(PILOT, out_root(tmp_path)).read_state()
    assert state["lifecycle_state"] == rd.RUNNING
    assert state["pilot_started"] is True


def test_start_sets_demo_authorized_and_live_false(tmp_path, fwd_root):
    r = running_pilot(tmp_path, fwd_root)
    assert r["order_execution_authorized"] is True
    assert r["automatic_execution_authorized"] is True
    assert r["automatic_demo_execution_authorized"] is True
    assert r["live_trading_authorized"] is False
    state = rd.PilotStateStore(PILOT, out_root(tmp_path)).read_state()
    assert state["live_trading_authorized"] is False
    assert state["automatic_demo_execution_authorized"] is True
    assert state["started_at_utc"]


def test_start_never_exposes_credential_values(tmp_path, fwd_root):
    r = running_pilot(tmp_path, fwd_root)
    blob = json.dumps(r)
    assert "DEMOKEY" not in blob and "DEMOSECRET" not in blob
    state_text = (pathlib.Path(out_root(tmp_path)) / PILOT / rd.STATE_FILENAME).read_text("utf-8")
    assert "DEMOKEY" not in state_text and "DEMOSECRET" not in state_text


def test_start_idempotent_single_event(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    r2 = start(tmp_path)
    assert r2["status"] == lc.STATUS_ALREADY_RUNNING
    store = rd.PilotStateStore(PILOT, out_root(tmp_path))
    events = store.events_path.read_text(encoding="utf-8").splitlines()
    assert sum(1 for e in events if '"START"' in e) == 1


def test_start_on_completed_fails_closed(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    store = rd.PilotStateStore(PILOT, out_root(tmp_path))
    state = store.read_state()
    state["lifecycle_state"] = rd.COMPLETED
    store.write_state(state)
    r = start(tmp_path)
    assert r["status"] == lc.STATUS_CONFLICTING


# ---------------------------------------------------------------------------
# Strategy-native execution: caps removed
# ---------------------------------------------------------------------------


def test_multiple_orders_not_rejected_for_count_over_one(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    t = FakeDemoTransport()
    actions = [act("SOLUSDT"), act("BTCUSDT"), act("ETHUSDT"), act("ADAUSDT")]
    res = nx.execute_daily_native(pilot_id=PILOT, date="2026-06-22", actions=actions,
                                  transport=t, output_root=out_root(tmp_path))
    assert res.day_verdict == nx.DAY_SUCCESS
    assert len(res.accepted) == 4 and len(res.rejected) == 0
    assert len(t.posts) == 4


def test_large_notional_not_rejected(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    t = FakeDemoTransport()
    actions = [act("SOLUSDT", qty="100", notional_usdt="5000")]
    res = nx.execute_daily_native(pilot_id=PILOT, date="2026-06-22", actions=actions,
                                  transport=t, output_root=out_root(tmp_path))
    assert len(res.accepted) == 1 and res.day_verdict == nx.DAY_SUCCESS


def test_multiple_positions_not_rejected(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    t = FakeDemoTransport()
    actions = [act("SOLUSDT"), act("BTCUSDT"), act("ETHUSDT")]
    res = nx.execute_daily_native(pilot_id=PILOT, date="2026-06-22", actions=actions,
                                  transport=t, output_root=out_root(tmp_path))
    assert len(res.accepted) == 3


def test_strategy_sizing_preserved_in_order_body(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    t = FakeDemoTransport()
    actions = [act("SOLUSDT", qty="0.337"), act("BTCUSDT", side="Sell", qty="12.5")]
    nx.execute_daily_native(pilot_id=PILOT, date="2026-06-22", actions=actions,
                            transport=t, output_root=out_root(tmp_path))
    qtys = {b["symbol"]: b["qty"] for _, b in t.posts}
    assert qtys["SOLUSDT"] == "0.337" and qtys["BTCUSDT"] == "12.5"
    sides = {b["symbol"]: b["side"] for _, b in t.posts}
    assert sides["BTCUSDT"] == "Sell"


def test_closing_action_uses_reduce_only(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    t = FakeDemoTransport()
    actions = [act("SOLUSDT", side="Sell", qty="0.5", intent=nx.INTENT_CLOSE, reduce_only=True)]
    nx.execute_daily_native(pilot_id=PILOT, date="2026-06-22", actions=actions,
                            transport=t, output_root=out_root(tmp_path))
    assert t.posts[0][1]["reduceOnly"] is True


# ---------------------------------------------------------------------------
# Strategy-native execution: hard safety rules remain
# ---------------------------------------------------------------------------


def test_protected_symbol_rejected(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    t = FakeDemoTransport()
    actions = [act("ENAUSDT"), act("SOLUSDT")]
    res = nx.execute_daily_native(pilot_id=PILOT, date="2026-06-22", actions=actions,
                                  transport=t, output_root=out_root(tmp_path))
    rejected = [r for r in res.rejected if r["eligibility"] == nx.REJECT_PROTECTED]
    assert len(rejected) == 1
    posted_symbols = [b["symbol"] for _, b in t.posts]
    assert "ENAUSDT" not in posted_symbols


def test_excluded_manual_and_smoke_records_rejected(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    t = FakeDemoTransport()
    actions = [act("SOLUSDT", record_category="SMOKE_TEST"),
               act("BTCUSDT", record_category="TASK-014BO_BP_MANUAL_ROUND_TRIP")]
    res = nx.execute_daily_native(pilot_id=PILOT, date="2026-06-22", actions=actions,
                                  transport=t, output_root=out_root(tmp_path))
    assert all(r["eligibility"] == nx.REJECT_EXCLUDED for r in res.rejected)
    assert len(t.posts) == 0


def test_live_endpoint_denied(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    t = FakeDemoTransport()
    res = nx.execute_daily_native(pilot_id=PILOT, date="2026-06-22", actions=[act("SOLUSDT")],
                                  transport=t, output_root=out_root(tmp_path), base_url=LIVE_BASE)
    assert res.day_verdict == nx.DAY_ENDPOINT
    assert len(t.posts) == 0


def test_execution_refused_when_not_running(tmp_path, fwd_root):
    init_inactive(tmp_path, fwd_root)
    migrate(tmp_path)  # INACTIVE, not started
    t = FakeDemoTransport()
    res = nx.execute_daily_native(pilot_id=PILOT, date="2026-06-22", actions=[act("SOLUSDT")],
                                  transport=t, output_root=out_root(tmp_path))
    assert res.day_verdict == nx.DAY_NOT_RUNNING
    assert len(t.posts) == 0


# ---------------------------------------------------------------------------
# Idempotency / ambiguity
# ---------------------------------------------------------------------------


def test_duplicate_execution_does_not_resend(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    t = FakeDemoTransport()
    actions = [act("SOLUSDT"), act("BTCUSDT")]
    nx.execute_daily_native(pilot_id=PILOT, date="2026-06-22", actions=actions,
                            transport=t, output_root=out_root(tmp_path))
    assert len(t.posts) == 2
    res2 = nx.execute_daily_native(pilot_id=PILOT, date="2026-06-22", actions=actions,
                                   transport=t, output_root=out_root(tmp_path))
    assert len(t.posts) == 2  # no new POSTs on rerun
    assert all(a["outcome"] == nx.OUTCOME_DUPLICATE_RECONCILED for a in res2.accepted)


def test_ambiguous_send_fails_closed(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    t = FakeDemoTransport(raise_on_post=True)
    res = nx.execute_daily_native(pilot_id=PILOT, date="2026-06-22", actions=[act("SOLUSDT")],
                                  transport=t, output_root=out_root(tmp_path))
    assert res.day_verdict == nx.DAY_AMBIGUOUS
    assert len(res.ambiguous) == 1


def test_ambiguous_reconcile_fails_closed(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    t = FakeDemoTransport(empty_reconcile=True)
    res = nx.execute_daily_native(pilot_id=PILOT, date="2026-06-22", actions=[act("SOLUSDT")],
                                  transport=t, output_root=out_root(tmp_path))
    assert res.day_verdict == nx.DAY_AMBIGUOUS


def test_delivery_retry_does_not_execute_orders(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    t = FakeDemoTransport()
    nx.execute_daily_native(pilot_id=PILOT, date="2026-06-22", actions=[act("SOLUSDT")],
                            transport=t, output_root=out_root(tmp_path))
    posts_before = len(t.posts)
    nx.record_delivery_status(pilot_id=PILOT, date="2026-06-22", channel="notion",
                              status="FAIL", output_root=out_root(tmp_path))
    nx.record_delivery_status(pilot_id=PILOT, date="2026-06-22", channel="notion",
                              status="PASS", output_root=out_root(tmp_path))
    assert len(t.posts) == posts_before


# ---------------------------------------------------------------------------
# Successful-day advancement
# ---------------------------------------------------------------------------


def test_successful_date_advances_once(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    r = nx.advance_successful_day(pilot_id=PILOT, date="2026-06-22", day_verdict=nx.DAY_SUCCESS,
                                  output_root=out_root(tmp_path))
    assert r["status"] == nx.STATUS_DAY_ADVANCED and r["completed_successful_days"] == 1


def test_duplicate_date_does_not_advance(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    nx.advance_successful_day(pilot_id=PILOT, date="2026-06-22", day_verdict=nx.DAY_SUCCESS,
                              output_root=out_root(tmp_path))
    r2 = nx.advance_successful_day(pilot_id=PILOT, date="2026-06-22", day_verdict=nx.DAY_SUCCESS,
                                   output_root=out_root(tmp_path))
    assert r2["status"] == nx.STATUS_DAY_ALREADY_COUNTED
    assert r2["completed_successful_days"] == 1


def test_ambiguous_day_does_not_advance(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    r = nx.advance_successful_day(pilot_id=PILOT, date="2026-06-22", day_verdict=nx.DAY_AMBIGUOUS,
                                  output_root=out_root(tmp_path))
    assert r["status"] == nx.STATUS_DAY_NOT_SUCCESSFUL
    assert r["completed_successful_days"] == 0


def test_completion_after_exactly_seven_dates(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    dates = [f"2026-06-{d:02d}" for d in range(22, 29)]  # 7 distinct dates
    for i, d in enumerate(dates, start=1):
        r = nx.advance_successful_day(pilot_id=PILOT, date=d, day_verdict=nx.DAY_SUCCESS,
                                      output_root=out_root(tmp_path))
        if i < 7:
            assert r["status"] == nx.STATUS_DAY_ADVANCED
            assert r["lifecycle_state"] == rd.RUNNING
        else:
            assert r["status"] == nx.STATUS_PILOT_COMPLETED
            assert r["lifecycle_state"] == rd.COMPLETED
    state = rd.PilotStateStore(PILOT, out_root(tmp_path)).read_state()
    assert state["completed_successful_days"] == 7
    assert state["lifecycle_state"] == rd.COMPLETED


# ---------------------------------------------------------------------------
# Source / engine hygiene
# ---------------------------------------------------------------------------


def test_no_real_network_imports_in_engine():
    src = (ROOT / "src" / "demo_strategy_pilot_native_execution.py").read_text("utf-8")
    # No scheduler / retry / busy-loop anywhere in the engine.
    for token in ("import requests", "websocket", "apscheduler", "crontab",
                  "while True", "@retry", "import tenacity", "import backoff"):
        assert token not in src
    # No live executor / main / risk import statement.
    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith(("import ", "from ")):
            assert "executors.bybit" not in s and "src.risk" not in s
            assert not s.startswith("import main") and "BybitExecutor" not in s


def test_build_actions_preserves_sizing(tmp_path):
    sr = {"signals": [{"symbol": "SOLUSDT", "side": "long"},
                      {"symbol": "BTCUSDT", "side": "short"}]}
    resolver = lambda sig: ("0.5" if sig["symbol"] == "SOLUSDT" else "2.0", "50")
    actions = nx.build_strategy_native_actions(sr, sizing_resolver=resolver)
    assert len(actions) == 2
    by = {a.symbol: a for a in actions}
    assert by["SOLUSDT"].qty == "0.5" and by["SOLUSDT"].side == "Buy"
    assert by["BTCUSDT"].qty == "2.0" and by["BTCUSDT"].side == "Sell"


# ---------------------------------------------------------------------------
# CLI start/migrate
# ---------------------------------------------------------------------------


def test_cli_has_start_and_migrate_modes():
    actions = {a.dest: a for a in cli.build_parser()._actions}
    assert set(actions["mode"].choices) == {"readiness", "initialize", "status", "migrate", "start"}


def test_cli_start_flow(tmp_path, fwd_root, monkeypatch, capsys):
    init_inactive(tmp_path, fwd_root)
    migrate(tmp_path)
    for k, v in DEMO_ENV.items():
        monkeypatch.setenv(k, v)
    rc = cli.main(["--mode", "start", "--pilot-id", PILOT,
                   "--" + lc.START_ACK_FLAG, "--json-only",
                   "--test-output-root", out_root(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == lc.STATUS_STARTED
    assert payload["live_trading_authorized"] is False
    assert payload["banner"] == cli.STARTED_BANNER
    assert "DEMOSECRET" not in json.dumps(payload)
    assert rc == cli.EXIT_OK
