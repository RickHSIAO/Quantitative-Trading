"""TASK-014 -- terminal DRY-RUN preparation of the Strategy-native 50-order Demo batch.

Narrow offline tests for the dry-run wiring only. The non-sending preparation mode lives on
the canonical runner (``scripts/run_demo_strategy_pilot_native_daily.py
--prepare-from-current-feasibility-artifacts``) and reuses the existing native-execution
builders (``classify_action`` / ``build_order_body`` / ``order_link_id``) to turn the three
CH4A artifacts into the EXACT 50 order payloads WITHOUT sending. Proves: 50 payloads + 25/25;
natural (non-redistributed) gross/net; protected overlap rejects the whole batch; failed
feasibility / missing leverage rejects; and that no transport / ``execute_daily_native`` /
POST is ever reached. (Per-symbol sizing / freshness are already covered by the CH4A and
native-execution suites and are not re-tested here.)
"""
from __future__ import annotations

import importlib.util
import json
import os
from decimal import Decimal

import pytest

from src import demo_strategy_pilot_native_execution as nx
from src import demo_strategy_pilot_readiness as rd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_RUNNER = os.path.join(_ROOT, "scripts", "run_demo_strategy_pilot_native_daily.py")
_spec = importlib.util.spec_from_file_location("crun_batch_prep", _RUNNER)
crun = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crun)


# ---------------------------------------------------------------------------
# CH4A-shaped artifacts (match demo_strategy_native_current_feasibility output)
# ---------------------------------------------------------------------------

def _artifacts(*, n=50, long_n=25, leverage="10", price="100.0",
               long_notional="200", short_notional="200", qty="2",
               protected=("EDUUSDT",), overlaps=(), symbols=None,
               feas_status="CURRENT_FEASIBILITY_PASS",
               margin_status="MARGIN_FEASIBILITY_PASS",
               leverage_status="TARGET_LEVERAGE_EVIDENCE_OK"):
    syms = symbols or [f"SYM{i:02d}USDT" for i in range(n)]
    actions, leverage_by, im_rows = [], {}, []
    for i, s in enumerate(syms):
        is_long = i < long_n
        notional = long_notional if is_long else short_notional
        im = str(Decimal(notional) / Decimal(leverage))
        actions.append({
            "symbol": s, "side": "long" if is_long else "short", "current_price": price,
            "rounded_quantity": qty, "rounded_notional_usd": notional,
            "quantity_validation_status": "QUANTITY_VALIDATION_OK",
            "tick_size": "0.01", "qty_step": "0.001", "min_order_qty": "0.001",
            "min_notional_value": "5",
        })
        leverage_by[s] = leverage
        im_rows.append({"symbol": s, "configured_leverage": leverage,
                        "projected_initial_margin_usd": im})
    market = {"schema": "demo_strategy_native_current_market_evidence",
              "current_actions": actions}
    account = {"account_evidence_status": "DEMO_ACCOUNT_EVIDENCE_OK",
               "target_leverage_evidence_status": leverage_status,
               "target_configured_leverage_by_symbol": leverage_by,
               "protected_positions": list(protected),
               "strategy_position_overlaps": list(overlaps),
               "position_mode": "one_way"}
    review = {"status": feas_status,
              "account_margin_feasibility_status": margin_status,
              "long_count": long_n, "short_count": n - long_n,
              "per_symbol_initial_margin": im_rows}
    return review, market, account


def _prepare(review, market, account, *, pilot_id="BYBIT_DEMO_PILOT_7D_202606_V1",
             date="2026-06-30"):
    return nx.prepare_strategy_native_batch_dry_run(
        feasibility_review=review, current_actions=market["current_actions"],
        account_evidence=account, pilot_id=pilot_id, date=date)


# ===========================================================================
# Pure function
# ===========================================================================

def test_pass_artifacts_produce_fifty_payloads_25_25_with_required_fields():
    r = _prepare(*_artifacts())
    assert r["verdict"] == nx.BATCH_PREP_PREPARED and r["blockers"] == []
    assert r["order_count"] == 50
    assert r["buy_count"] == 25 and r["sell_count"] == 25
    assert len(r["order_payloads"]) == 50
    p0 = r["order_payloads"][0]
    for field in ("symbol", "side", "qty", "current_reference_price", "rounded_notional_usd",
                  "configured_leverage", "projected_initial_margin_usd",
                  "instrument_rule_validation", "order_link_id", "order_body"):
        assert field in p0, field
    body = p0["order_body"]
    assert body["orderType"] == "Market" and body["reduceOnly"] is False
    assert body["orderLinkId"] == p0["order_link_id"]
    assert body["orderLinkId"].startswith(nx.ORDER_LINK_ID_PREFIX)


def test_natural_gross_net_exposure_preserved_no_redistribution():
    # Longs round to 199, shorts to 200 -> natural short bias; never padded to 10000 / 0.
    r = _prepare(*_artifacts(long_notional="199", short_notional="200"))
    assert r["verdict"] == nx.BATCH_PREP_PREPARED
    assert r["gross_notional_usd"] == "9975"     # 25*199 + 25*200
    assert r["net_notional_usd"] == "-25"        # short bias
    assert r["short_bias_usd"] == "25"
    assert r["total_projected_initial_margin_usd"] == "997.5"


def test_protected_symbol_target_rejects_whole_batch():
    syms = [f"SYM{i:02d}USDT" for i in range(49)] + ["EDUUSDT"]
    r = _prepare(*_artifacts(symbols=syms))
    assert r["verdict"] == nx.BATCH_PREP_REJECTED
    assert any("EDUUSDT" in b and "not_eligible" in b for b in r["blockers"])
    assert r["order_payloads"] == [] and r["order_count"] == 0  # never a partial batch


@pytest.mark.parametrize("over,frag", [
    ({"feas_status": "CURRENT_FEASIBILITY_BLOCKED"}, "feasibility_status_not_pass"),
    ({"margin_status": "MARGIN_FEASIBILITY_UNAVAILABLE_NO_INDEPENDENT_RATE"},
     "margin_status_not_pass"),
    ({"leverage_status": "TARGET_LEVERAGE_EVIDENCE_UNAVAILABLE"}, "leverage_status_not_ok"),
    ({"overlaps": ("SYM00USDT",)}, "strategy_position_overlap"),
])
def test_failed_gate_rejects_with_no_payloads(over, frag):
    r = _prepare(*_artifacts(**over))
    assert r["verdict"] == nx.BATCH_PREP_REJECTED
    assert any(frag in b for b in r["blockers"])
    assert r["order_payloads"] == []


# ===========================================================================
# Canonical runner mode -- nothing is ever sent
# ===========================================================================

def _write(tmp_path, review, market, account):
    (tmp_path / "review.json").write_text(json.dumps(review), encoding="utf-8")
    (tmp_path / "market.json").write_text(json.dumps(market), encoding="utf-8")
    (tmp_path / "account.json").write_text(json.dumps(account), encoding="utf-8")


def _argv(tmp_path, *, out=None):
    argv = ["--prepare-from-current-feasibility-artifacts",
            "--pilot-id", "BYBIT_DEMO_PILOT_7D_202606_V1", "--date", "2026-06-30",
            "--current-feasibility-review-json", str(tmp_path / "review.json"),
            "--current-market-evidence-json", str(tmp_path / "market.json"),
            "--demo-account-evidence-json", str(tmp_path / "account.json")]
    if out:
        argv += ["--prepare-output-json", str(out)]
    return argv


def test_runner_mode_prepares_and_never_touches_transport_or_execution(tmp_path, capsys, monkeypatch):
    _write(tmp_path, *_artifacts())

    def _boom(*a, **k):
        raise AssertionError("send path must never be reached in dry-run preparation")

    # If the prepare mode ever constructed a transport or dispatched, these would fire.
    monkeypatch.setattr(crun, "RealDemoOrderTransport", _boom, raising=False)
    monkeypatch.setattr(crun.nx, "execute_daily_native", _boom)

    out = tmp_path / "preview.json"
    rc = crun.main(_argv(tmp_path, out=out))
    assert rc == crun.EXIT_OK
    summary = json.loads(capsys.readouterr().out)
    assert summary["verdict"] == nx.BATCH_PREP_PREPARED
    assert summary["order_count"] == 50
    for c in ("order_post_count", "amend_post_count", "cancel_post_count",
              "live_order_post_count", "sender_call_count"):
        assert summary[c] == 0
    assert summary["execution_authorized"] is False
    assert summary["transport_touched"] is False
    written = json.loads(out.read_text(encoding="utf-8"))
    assert len(written["order_payloads"]) == 50


def test_runner_mode_rejects_blocked_feasibility(tmp_path, capsys):
    _write(tmp_path, *_artifacts(feas_status="CURRENT_FEASIBILITY_BLOCKED"))
    rc = crun.main(_argv(tmp_path))
    assert rc == crun.EXIT_BLOCKED
    summary = json.loads(capsys.readouterr().out)
    assert summary["verdict"] == nx.BATCH_PREP_REJECTED
    assert summary["order_count"] == 0


# ===========================================================================
# Per-symbol evidence validation (corrections item 1)
# ===========================================================================

def _artifacts_with_row_override(row_index, **overrides):
    """Return artifacts where one row at row_index has fields overridden."""
    review, market, account = _artifacts()
    row = dict(market["current_actions"][row_index])
    row.update(overrides)
    market = dict(market)
    market["current_actions"] = list(market["current_actions"])
    market["current_actions"][row_index] = row
    return review, market, account


def test_missing_configured_leverage_rejects_whole_batch():
    review, market, account = _artifacts()
    # Remove one symbol from the leverage map.
    sym = market["current_actions"][3]["symbol"]
    account = dict(account)
    account["target_configured_leverage_by_symbol"] = {
        k: v for k, v in account["target_configured_leverage_by_symbol"].items() if k != sym}
    r = _prepare(review, market, account)
    assert r["verdict"] == nx.BATCH_PREP_REJECTED
    assert any(f"missing_configured_leverage:{sym}" == b for b in r["blockers"])
    assert r["order_payloads"] == [] and r["order_count"] == 0


def test_invalid_projected_initial_margin_rejects_whole_batch():
    review, market, account = _artifacts()
    sym = market["current_actions"][7]["symbol"]
    # Corrupt that symbol's IM row in the review.
    review = dict(review)
    review["per_symbol_initial_margin"] = [
        ({"symbol": r["symbol"], "projected_initial_margin_usd": "-5"}
         if r["symbol"] == sym else r)
        for r in review["per_symbol_initial_margin"]
    ]
    r = _prepare(review, market, account)
    assert r["verdict"] == nx.BATCH_PREP_REJECTED
    assert any(f"invalid_projected_initial_margin:{sym}" == b for b in r["blockers"])
    assert r["order_payloads"] == []


def test_invalid_quantity_validation_status_rejects_whole_batch():
    review, market, account = _artifacts_with_row_override(
        5, quantity_validation_status="QUANTITY_VALIDATION_FAILED")
    r = _prepare(review, market, account)
    sym = market["current_actions"][5]["symbol"]
    assert r["verdict"] == nx.BATCH_PREP_REJECTED
    assert any(f"quantity_not_valid:{sym}" == b for b in r["blockers"])
    assert r["order_payloads"] == []


def test_duplicate_symbol_rejects_whole_batch():
    review, market, account = _artifacts()
    # Replace last row's symbol with the first row's symbol.
    dup_sym = market["current_actions"][0]["symbol"]
    market = dict(market)
    market["current_actions"] = list(market["current_actions"])
    market["current_actions"][-1] = dict(market["current_actions"][-1], symbol=dup_sym)
    r = _prepare(review, market, account)
    assert r["verdict"] == nx.BATCH_PREP_REJECTED
    assert any(f"duplicate_symbol:{dup_sym}" == b for b in r["blockers"])
    assert r["order_payloads"] == []


# ===========================================================================
# Conflicting-mode rejection (corrections item 2)
# ===========================================================================

def test_prepare_mode_combined_with_send_orders_returns_exit_invalid(tmp_path, capsys, monkeypatch):
    _write(tmp_path, *_artifacts())

    def _boom(*a, **k):
        raise AssertionError("transport / execution must never be reached when flag conflict detected")

    monkeypatch.setattr(crun, "RealDemoOrderTransport", _boom, raising=False)
    monkeypatch.setattr(crun.nx, "execute_daily_native", _boom)

    argv = _argv(tmp_path) + ["--send-orders-to-demo"]
    rc = crun.main(argv)
    assert rc == crun.EXIT_INVALID
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == nx.BATCH_PREP_REJECTED
    assert any("incompatible_flag:send_orders_to_demo" == b for b in out["blockers"])


# ===========================================================================
# TASK-014_CANONICAL_DEMO_BATCH_EXECUTION_WIRING
# Offline only: fake transport / injected CH4A / placeholder (non-real)
# credentials. No real RealDemoOrderTransport, no network, no order is sent.
# Execution recollects fresh CH4A INSIDE the command and never advances Pilot.
# ===========================================================================

PILOT = "BYBIT_DEMO_PILOT_7D_202606_V1"
DATE = "2026-06-30"
OTHER_DATE = "2026-07-01"
DEMO_ENV = {"BYBIT_DEMO_API_KEY": "DEMOKEY", "BYBIT_DEMO_API_SECRET": "DEMOSECRET"}
NO_CRED_ENV = {"NOTION_TOKEN": "tok"}
LIVE_BASE = "https://api.bybit.com"


class FakeDemoTransport:
    """Records POSTs/reconciles; never networks. ambiguous_first makes exactly one order's
    reconcile come back not-found (ambiguous) to exercise fail-closed behavior."""

    def __init__(self, ambiguous_first=False):
        self.posts = []
        self.reconciles = []
        self.ambiguous_first = ambiguous_first

    def post_order_create(self, *, url, body):
        self.posts.append((url, dict(body)))
        link = body["orderLinkId"]
        return {"retCode": 0, "retMsg": "OK",
                "result": {"orderId": "OID-" + link, "orderLinkId": link}}

    def reconcile(self, *, order_link_id):
        self.reconciles.append(order_link_id)
        if self.ambiguous_first and len(self.reconciles) == 1:
            return {"retCode": 0, "result": {"list": []}}  # not found -> ambiguous
        return {"retCode": 0, "result": {"list": [{
            "orderLinkId": order_link_id, "orderId": "OID-" + order_link_id,
            "orderStatus": "Filled", "cumExecQty": "1", "avgPrice": "100",
            "cumExecFee": "0.01"}]}}


def _fake_collector(review, market, account, *, calls=None):
    def collect(args):
        if calls is not None:
            calls.append(1)
        return review, market["current_actions"], account
    return collect


def _valid_token(review, market, account):
    prepared = nx.prepare_strategy_native_batch_dry_run(
        feasibility_review=review, current_actions=market["current_actions"],
        account_evidence=account, pilot_id=PILOT, date=DATE)
    actions = crun._actions_from_prepared(prepared)
    fp = crun.batch_payload_fingerprint(actions, pilot_id=PILOT, date=DATE)
    return crun.expected_batch_authorization_token(DATE, fp)


def _write_running_pilot(out_root):
    rd.PilotStateStore(PILOT, out_root).write_state({
        "pilot_id": PILOT, "lifecycle_state": rd.RUNNING,
        "order_execution_authorized": True, "live_trading_authorized": False,
        "completed_successful_days": 0, "successful_dates": [],
        "target_successful_days": 7, "remaining_successful_days": 7,
    })


def _exec_args(tmp_path, *, token=None, send=True, advance=False, date=DATE):
    argv = ["--pilot-id", PILOT, "--date", date, "--execute-prepared-demo-batch",
            "--test-output-root", str(tmp_path / "out")]
    if send:
        argv.append("--send-orders-to-demo")
    if token is not None:
        argv += ["--batch-authorization-token", token]
    if advance:
        argv.append("--advance-on-success")
    return crun.build_parser().parse_args(argv)


def _ch4a_args(tmp_path, *, preflight=None):
    pf = preflight if preflight is not None else str(tmp_path / "preflight")
    argv = ["--pilot-id", PILOT, "--date", DATE, "--execute-prepared-demo-batch",
            "--test-output-root", str(tmp_path / "out"),
            "--batch-authorization-token", "dummy",
            "--review-artifact-json", "rev.json", "--review-artifact-sha256", "sha256:" + "a" * 64,
            "--anchor-manifest-json", "man.json", "--anchor-manifest-sha256", "sha256:" + "b" * 64,
            "--wrapper-json", "wrap.json",
            "--strategy-symbols-json", "sym.json", "--strategy-symbols-sha256", "sha256:" + "c" * 64,
            "--ch4a-preflight-dir", pf]
    return crun.build_parser().parse_args(argv)


def _fake_ch4a_invoke(review, market, account, *, rc=0, calls=None):
    """Stand in for the real CH4A runner main(): writes the requested fresh output artifacts
    (when rc == 0) and returns the given exit code. No network."""
    def invoke(argv):
        if calls is not None:
            calls.append(list(argv))
        if rc == 0:
            payload = {"--feasibility-review-output-json": review,
                       "--market-evidence-output-json": market,
                       "--account-evidence-output-json": account,
                       "--summary-output-json": {"schema": "summary"}}
            for i, tok in enumerate(argv):
                if tok in payload:
                    with open(argv[i + 1], "w", encoding="utf-8") as f:
                        json.dump(payload[tok], f)
        return rc
    return invoke


def _tracking_builder():
    calls = []

    def build(*, credentials, env=None):
        calls.append(1)
        return FakeDemoTransport()
    return build, calls


def _boom_executor(**kw):
    raise AssertionError("execute_daily_native must not be reached on a pre-send rejection")


# ---- fresh-CH4A collector (the production default for execution) ----

def test_fresh_collector_runs_existing_ch4a_once_with_real_network_flag(tmp_path):
    review, market, account = _artifacts()
    calls = []
    args = _ch4a_args(tmp_path)
    r, ca, a = crun._collect_fresh_ch4a(
        args, invoke=_fake_ch4a_invoke(review, market, account, calls=calls))
    assert len(calls) == 1                                   # CH4A invoked exactly once
    argv = calls[0]
    assert "--allow-real-network" in argv
    assert "--current-market-demo-account-feasibility-read-only" in argv
    assert ca == market["current_actions"]
    assert os.path.isdir(str(tmp_path / "preflight"))        # fresh outputs written here


def test_fresh_collector_nonzero_ch4a_exit_raises(tmp_path):
    review, market, account = _artifacts()
    args = _ch4a_args(tmp_path)
    with pytest.raises(crun.FreshCh4aError):
        crun._collect_fresh_ch4a(
            args, invoke=_fake_ch4a_invoke(review, market, account, rc=4))


def test_fresh_collector_preflight_dir_is_no_clobber(tmp_path):
    review, market, account = _artifacts()
    existing = tmp_path / "preflight"
    existing.mkdir()
    args = _ch4a_args(tmp_path, preflight=str(existing))
    with pytest.raises(ValueError):
        crun._collect_fresh_ch4a(
            args, invoke=_fake_ch4a_invoke(review, market, account))


def test_production_execution_default_uses_fresh_ch4a_collector(tmp_path, capsys, monkeypatch):
    review, market, account = _artifacts()
    _write_running_pilot(str(tmp_path / "out"))
    args = _exec_args(tmp_path, token=_valid_token(review, market, account))

    used = []

    def sentinel_collector(a):
        used.append(1)
        return review, market["current_actions"], account
    monkeypatch.setattr(crun, "_collect_fresh_ch4a", sentinel_collector)

    rc = crun._run_execute_prepared_demo_batch(
        args, build_transport=lambda *, credentials, env=None: FakeDemoTransport(),
        executor=nx.execute_daily_native, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_OK
    assert used == [1]                                       # default wiring is the fresh collector


# ---- date gate: stale day rejected before collection / transport / execution ----

def test_old_execution_date_rejected_before_collection_and_transport(tmp_path):
    review, market, account = _artifacts()
    collect_calls = []
    args = _exec_args(tmp_path, token=_valid_token(review, market, account))
    build, build_calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=_fake_collector(review, market, account, calls=collect_calls),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=OTHER_DATE)
    assert rc == crun.EXIT_INVALID
    assert collect_calls == []                               # CH4A never collected
    assert build_calls == []                                 # no transport


def test_ch4a_failure_prevents_transport_and_execution(tmp_path):
    args = _exec_args(tmp_path, token="dummy")

    def failing_collector(a):
        raise crun.FreshCh4aError("ch4a_exit_nonzero:4")
    build, build_calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=failing_collector,
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_INPUT_FAILURE
    assert build_calls == []                                 # CH4A failure -> no transport, no engine


# ---- pre-send gates: none may construct a transport or call the engine ----

def test_missing_send_flag_rejects_before_transport(tmp_path):
    review, market, account = _artifacts()
    args = _exec_args(tmp_path, token=_valid_token(review, market, account), send=False)
    build, calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=_fake_collector(review, market, account),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_INVALID
    assert calls == []


def test_advance_on_success_flag_rejected_for_execution_mode(tmp_path):
    review, market, account = _artifacts()
    collect_calls = []
    args = _exec_args(tmp_path, token=_valid_token(review, market, account), advance=True)
    build, build_calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=_fake_collector(review, market, account, calls=collect_calls),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_INVALID
    assert collect_calls == [] and build_calls == []


def test_missing_token_rejects_before_transport(tmp_path):
    review, market, account = _artifacts()
    args = _exec_args(tmp_path, token=None)
    build, calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=_fake_collector(review, market, account),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_INVALID
    assert calls == []


def test_wrong_fingerprint_token_rejects_before_transport(tmp_path):
    review, market, account = _artifacts()
    stale = crun.expected_batch_authorization_token(DATE, "deadbeefdeadbeef0000")
    args = _exec_args(tmp_path, token=stale)
    _write_running_pilot(str(tmp_path / "out"))
    build, calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=_fake_collector(review, market, account),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_INVALID
    assert calls == []


def test_non_demo_base_url_rejects_before_transport(tmp_path):
    review, market, account = _artifacts()
    args = _exec_args(tmp_path, token=_valid_token(review, market, account))
    build, calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=_fake_collector(review, market, account),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, base_url=LIVE_BASE,
        today=DATE)
    assert rc == crun.EXIT_INVALID
    assert calls == []


def test_missing_demo_credentials_rejects_before_transport(tmp_path):
    review, market, account = _artifacts()
    args = _exec_args(tmp_path, token=_valid_token(review, market, account))
    build, calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=_fake_collector(review, market, account),
        build_transport=build, executor=_boom_executor, env=NO_CRED_ENV, today=DATE)
    assert rc == crun.EXIT_INVALID
    assert calls == []


@pytest.mark.parametrize("over,reason", [
    (dict(symbols=[f"SYM{i:02d}USDT" for i in range(49)] + ["EDUUSDT"]), "protected"),
    (dict(n=49, long_n=25), "49 payloads"),
    (dict(n=51, long_n=26), "51 payloads"),
    (dict(long_n=26), "26/24 split"),
])
def test_preparation_failure_rejects_before_transport(tmp_path, over, reason):
    review, market, account = _artifacts(**over)
    args = _exec_args(tmp_path, token="CONFIRM_DEMO_NATIVE_BATCH_20260630_dummy0000dummy00")
    build, calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=_fake_collector(review, market, account),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_BLOCKED
    assert calls == []


def test_pilot_state_incompatible_rejects_before_transport(tmp_path):
    review, market, account = _artifacts()
    args = _exec_args(tmp_path, token=_valid_token(review, market, account))
    # No running pilot written -> pilot_state_incompatible.
    build, calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=_fake_collector(review, market, account),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_BLOCKED
    assert calls == []


def test_execute_mode_conflict_with_prepare_flag_rejects(tmp_path):
    review, market, account = _artifacts()
    args = _exec_args(tmp_path, token=_valid_token(review, market, account))
    args.prepare_from_ch4a = True
    build, calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=_fake_collector(review, market, account),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_INVALID
    assert calls == []


# ---- send flag WITHOUT execute flag cannot enter the new batch path ----

def test_send_flag_without_execute_flag_cannot_dispatch(tmp_path, capsys, monkeypatch):
    def _boom_handler(*a, **k):
        raise AssertionError("execute handler must not run without --execute-prepared-demo-batch")

    def _boom_real(*a, **k):
        raise AssertionError("RealDemoOrderTransport must not be constructed")
    monkeypatch.setattr(crun, "_run_execute_prepared_demo_batch", _boom_handler)
    monkeypatch.setattr(crun, "RealDemoOrderTransport", _boom_real, raising=False)
    monkeypatch.setattr(crun.nx, "execute_daily_native", _boom_real)

    # No RUNNING pilot -> main stops at the RUNNING gate, far from any send path.
    rc = crun.main(["--pilot-id", PILOT, "--date", DATE, "--send-orders-to-demo",
                    "--test-output-root", str(tmp_path / "out")])
    assert rc == crun.EXIT_BLOCKED
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == nx.DAY_NOT_RUNNING


# ---- full authorization: reaches execute_daily_native exactly once, never advances Pilot ----

def test_fully_authorized_dispatches_fifty_orders_once_without_advancing_pilot(
        tmp_path, capsys, monkeypatch):
    def _no_real(*a, **k):
        raise AssertionError("real transport must never be constructed")
    monkeypatch.setattr(crun, "RealDemoOrderTransport", _no_real, raising=False)

    review, market, account = _artifacts()
    _write_running_pilot(str(tmp_path / "out"))
    args = _exec_args(tmp_path, token=_valid_token(review, market, account))

    fake_tp = FakeDemoTransport()
    builder_calls = []

    def build(*, credentials, env=None):
        builder_calls.append(1)
        return fake_tp

    exec_calls = []

    def spy_exec(**kw):
        exec_calls.append(kw)
        return nx.execute_daily_native(**kw)

    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=_fake_collector(review, market, account),
        build_transport=build, executor=spy_exec, env=DEMO_ENV, today=DATE)

    assert rc == crun.EXIT_OK
    assert builder_calls == [1]                       # transport constructed exactly once
    assert len(exec_calls) == 1                        # engine invoked exactly once
    assert len(exec_calls[0]["actions"]) == 50         # with the 50 prepared actions
    assert len(fake_tp.posts) == 50                    # 50 individual /v5/order/create POSTs
    assert all(body["reduceOnly"] is False for _, body in fake_tp.posts)
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == crun.EXEC_BATCH_DISPATCHED
    assert summary["day_verdict"] == nx.DAY_SUCCESS
    assert summary["execute_daily_native_called"] == 1
    assert summary["order_post_count"] == 50
    assert summary["live_trading_authorized"] is False
    assert summary["pilot_advanced"] is False
    # Execution mode must NOT advance the Pilot; that stays owned by the reporting workflow.
    state = rd.PilotStateStore(PILOT, str(tmp_path / "out")).read_state()
    assert state["completed_successful_days"] == 0
    assert state["successful_dates"] == []


def test_one_ambiguous_result_prevents_pilot_advancement(tmp_path, capsys):
    review, market, account = _artifacts()
    _write_running_pilot(str(tmp_path / "out"))
    args = _exec_args(tmp_path, token=_valid_token(review, market, account))
    ambiguous_tp = FakeDemoTransport(ambiguous_first=True)

    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=_fake_collector(review, market, account),
        build_transport=lambda *, credentials, env=None: ambiguous_tp,
        executor=nx.execute_daily_native, env=DEMO_ENV, today=DATE)

    assert rc == crun.EXIT_AMBIGUOUS
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == crun.EXEC_BATCH_AMBIGUOUS
    assert summary["pilot_advanced"] is False
    state = rd.PilotStateStore(PILOT, str(tmp_path / "out")).read_state()
    assert state["completed_successful_days"] == 0     # never advanced


# ---- manual-authorization handshake: preparation publishes fingerprint + token ----

def test_preparation_output_includes_fingerprint_and_expected_token(tmp_path, capsys):
    review, market, account = _artifacts()
    _write(tmp_path, review, market, account)
    rc = crun.main(_argv(tmp_path))
    assert rc == crun.EXIT_OK
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == nx.BATCH_PREP_PREPARED
    # Deterministic, derived via the SAME helpers execution uses.
    assert out["payload_fingerprint"] == crun.batch_payload_fingerprint(
        crun._actions_from_prepared(out), pilot_id=PILOT, date=DATE)
    assert out["expected_batch_authorization_token"] == _valid_token(review, market, account)
    assert out["expected_batch_authorization_token"].startswith(
        "CONFIRM_DEMO_NATIVE_BATCH_20260630_")


def _full_exec_args(tmp_path, *, token, preflight=None):
    pf = preflight if preflight is not None else str(tmp_path / "preflight")
    argv = ["--pilot-id", PILOT, "--date", DATE, "--execute-prepared-demo-batch",
            "--send-orders-to-demo", "--test-output-root", str(tmp_path / "out"),
            "--batch-authorization-token", token,
            "--review-artifact-json", "rev.json", "--review-artifact-sha256", "sha256:" + "a" * 64,
            "--anchor-manifest-json", "man.json", "--anchor-manifest-sha256", "sha256:" + "b" * 64,
            "--wrapper-json", "wrap.json",
            "--strategy-symbols-json", "sym.json", "--strategy-symbols-sha256", "sha256:" + "c" * 64,
            "--ch4a-preflight-dir", pf]
    return crun.build_parser().parse_args(argv)


def test_execution_accepts_prepared_token_when_fresh_ch4a_matches(tmp_path, capsys):
    # Operator's token comes from the non-sending preparation review.
    review, market, account = _artifacts()
    token = _valid_token(review, market, account)
    _write_running_pilot(str(tmp_path / "out"))
    args = _full_exec_args(tmp_path, token=token)
    fake_tp = FakeDemoTransport()
    # Default fresh collector + a CH4A that reproduces the SAME 50 order bodies.
    out_rc = crun._run_execute_prepared_demo_batch(
        args,
        collect_feasibility=lambda a: crun._collect_fresh_ch4a(
            a, invoke=_fake_ch4a_invoke(review, market, account)),
        build_transport=lambda *, credentials, env=None: fake_tp,
        executor=nx.execute_daily_native, env=DEMO_ENV, today=DATE)
    assert out_rc == crun.EXIT_OK
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == crun.EXEC_BATCH_DISPATCHED
    assert summary["payload_fingerprint"][:16] == token.split("_")[-1]  # token embeds fp16
    assert len(fake_tp.posts) == 50


def test_changed_fresh_quantity_rejects_token_before_transport(tmp_path):
    # Token issued at preparation for the original 50 quantities.
    review, market, account = _artifacts()
    token = _valid_token(review, market, account)
    _write_running_pilot(str(tmp_path / "out"))
    # Fresh CH4A now returns a DIFFERENT quantity for one symbol -> different fingerprint.
    review2, market2, account2 = _artifacts()
    market2["current_actions"][0]["rounded_quantity"] = "999"
    args = _exec_args(tmp_path, token=token)
    build, calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=_fake_collector(review2, market2, account2),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_INVALID                  # authorization_token_mismatch
    assert calls == []                              # rejected before transport construction


# ---- single machine-readable JSON on stdout (CH4A's own print is suppressed) ----

def test_execution_stdout_is_single_json_after_fresh_ch4a(tmp_path, capsys, monkeypatch):
    review, market, account = _artifacts()
    _write_running_pilot(str(tmp_path / "out"))
    token = _valid_token(review, market, account)
    args = _full_exec_args(tmp_path, token=token)

    def printing_invoke(argv):
        # The real CH4A main() prints its own JSON summary; it must NOT leak to final stdout.
        print(json.dumps({"status": "CH4A_INTERNAL_NOISE", "should_not_leak": True}))
        _fake_ch4a_invoke(review, market, account)(argv)   # write fresh artifacts
        return 0
    monkeypatch.setattr(crun, "_invoke_real_ch4a", printing_invoke)

    rc = crun._run_execute_prepared_demo_batch(
        args, build_transport=lambda *, credentials, env=None: FakeDemoTransport(),
        executor=nx.execute_daily_native, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_OK
    captured = capsys.readouterr().out
    summary = json.loads(captured)                  # exactly one JSON object -> parses cleanly
    assert summary["status"] == crun.EXEC_BATCH_DISPATCHED
    assert summary["order_post_count"] == 50
    assert "CH4A_INTERNAL_NOISE" not in captured     # CH4A stdout was captured, not leaked


# ---- RUNNING-Pilot send-without-execute: legacy delegated path, never our engine ----

def test_send_without_execute_running_pilot_uses_delegated_path_no_dispatch(
        tmp_path, capsys, monkeypatch):
    _write_running_pilot(str(tmp_path / "out"))

    def _boom(*a, **k):
        raise AssertionError("execution/transport must not run on the send-without-execute path")
    monkeypatch.setattr(crun, "_run_execute_prepared_demo_batch", _boom)
    monkeypatch.setattr(crun, "RealDemoOrderTransport", _boom, raising=False)
    monkeypatch.setattr(crun.nx, "execute_daily_native", _boom)
    monkeypatch.setattr(crun, "orchestrate_native_daily", _boom, raising=False)

    # Injected/fake forward data + provider/plan/review (no real network).
    monkeypatch.setattr(crun.fs, "load_primary_forward_strategy_result",
                        lambda **k: object())
    monkeypatch.setattr(crun, "_build_production_provider", lambda *a, **k: object())

    class _Plan:
        status = "OK"
        available = True

        def to_dict(self):
            return {}
    monkeypatch.setattr(crun.planner, "plan_strategy_native_actions", lambda **k: _Plan())
    monkeypatch.setattr(crun, "build_active_v1_review", lambda **k: {"plan_valid": True})

    rc = crun.main(["--pilot-id", PILOT, "--date", DATE, "--send-orders-to-demo",
                    "--test-output-root", str(tmp_path / "out")])
    assert rc == crun.EXIT_BLOCKED
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "STRATEGY_NATIVE_V1_EXECUTION_BATCH_NOT_AUTHORIZED"
    assert out["send_path_refused"] is True
    assert out["execute_daily_native_called"] is False
    assert out["order_post_count"] == 0
    assert out["live_trading_authorized"] is False
