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
               leverage_status="TARGET_LEVERAGE_EVIDENCE_OK",
               # Fresh-evidence fields read by the execution-mode validation (harmless to the
               # pure prepare path, which ignores them).
               available_balance="100000", existing_im="0",
               instrument_status="Trading", trading=True,
               qty_step="0.001", min_order_qty="0.001", min_notional_value="5",
               max_market_order_qty="1000000", live_denied=True):
    syms = symbols or [f"SYM{i:02d}USDT" for i in range(n)]
    actions, leverage_by, im_rows = [], {}, []
    for i, s in enumerate(syms):
        is_long = i < long_n
        notional = long_notional if is_long else short_notional
        im = str(Decimal(notional) / Decimal(leverage))
        actions.append({
            "symbol": s, "side": "long" if is_long else "short", "current_price": price,
            "target_signed_notional_usd": (f"+{notional}" if is_long else f"-{notional}"),
            "rounded_quantity": qty, "rounded_notional_usd": notional,
            "quantity_validation_status": "QUANTITY_VALIDATION_OK",
            "instrument_status": instrument_status, "trading": trading,
            "tick_size": "0.01", "qty_step": qty_step, "min_order_qty": min_order_qty,
            "min_notional_value": min_notional_value,
            "max_market_order_qty": max_market_order_qty,
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
               "position_mode": "one_way",
               "available_balance_usd": available_balance,
               "existing_initial_margin_usd": existing_im,
               "live_environment_denied": live_denied}
    review = {"status": feas_status,
              "account_margin_feasibility_status": margin_status,
              "long_count": long_n, "short_count": n - long_n,
              "per_symbol_initial_margin": im_rows,
              "available_balance_usd": available_balance,
              "existing_initial_margin_usd": existing_im,
              "account_equity_usd": available_balance,
              "live_environment_denied": live_denied}
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
# TASK-014 ALLOCATION-INTENT EXECUTION WIRING (strategy-capital correction)
# Offline only: fake transport / injected CH4A collector / placeholder (non-real)
# credentials. No real RealDemoOrderTransport, no network, no order is sent.
#
# Authorization binds an IMMUTABLE ALLOCATION INTENT (per-symbol side + target
# quote-notional + the fixed strategy capital-base snapshot), NOT final quantities.
# Execution recomputes the executable qty from the authorized target + fresh price
# using the canonical floor-to-step rounding, so the authorized quote-notional (and
# the fingerprint) stay stable when only price moves. Account equity / available
# balance are feasibility/safety inputs only -- never the sizing basis.
# No automatic post-close compounding is implemented.
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


# ---------------------------------------------------------------------------
# Immutable allocation-intent artifact + fresh-evidence helpers
# ---------------------------------------------------------------------------

def _prepared_artifact(src=None):
    """Build the IMMUTABLE allocation-intent artifact exactly as the non-sending preparation
    mode publishes it: the prepare() result + per-symbol target_notional_usd + the strategy
    capital-base snapshot + the price-independent intent fingerprint + token."""
    review, market, account = src or _artifacts()
    art = nx.prepare_strategy_native_batch_dry_run(
        feasibility_review=review, current_actions=market["current_actions"],
        account_evidence=account, pilot_id=PILOT, date=DATE)
    allocs, capital = crun._allocations_from_market_targets(
        art["order_payloads"], market["current_actions"])
    cap_str = crun._runner_canon(capital)
    for p, a in zip(art["order_payloads"], allocs):
        p["target_notional_usd"] = a["target_notional_usd"]
    art["strategy_capital_base_usd"] = cap_str
    fp = crun.allocation_intent_fingerprint(
        allocs, pilot_id=PILOT, date=DATE, strategy_capital_base_usd=cap_str)
    art["payload_fingerprint"] = fp
    art["allocation_intent_fingerprint"] = fp
    art["expected_batch_authorization_token"] = crun.expected_batch_authorization_token(DATE, fp)
    return art, fp


def _write_artifact(tmp_path, art, name="prepared_batch.json"):
    path = tmp_path / name
    path.write_text(json.dumps(art), encoding="utf-8")
    return str(path)


def _token_for(art):
    return crun.expected_batch_authorization_token(DATE, art["payload_fingerprint"])


def _allocs(art):
    return crun.verify_immutable_prepared_artifact(
        art, pilot_id=PILOT, date=DATE, token=_token_for(art))[3]


def _fake_collector(review, market, account, *, calls=None):
    def collect(args):
        if calls is not None:
            calls.append(1)
        return review, market["current_actions"], account
    return collect


def _write_running_pilot(out_root):
    rd.PilotStateStore(PILOT, out_root).write_state({
        "pilot_id": PILOT, "lifecycle_state": rd.RUNNING,
        "order_execution_authorized": True, "live_trading_authorized": False,
        "completed_successful_days": 0, "successful_dates": [],
        "target_successful_days": 7, "remaining_successful_days": 7,
    })


def _exec_args(tmp_path, *, token=None, prepared_json=None, send=True, advance=False, date=DATE):
    argv = ["--pilot-id", PILOT, "--date", date, "--execute-prepared-demo-batch",
            "--test-output-root", str(tmp_path / "out")]
    if send:
        argv.append("--send-orders-to-demo")
    if token is not None:
        argv += ["--batch-authorization-token", token]
    if prepared_json is not None:
        argv += ["--prepared-batch-json", prepared_json]
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


def _authorized(tmp_path, *, art_src=None, fresh=None):
    """Common fully-authorized setup: immutable artifact written + token + RUNNING pilot.
    ``fresh`` is the (review, market, account) the fresh CH4A collector returns."""
    art, fp = _prepared_artifact(art_src)
    prepared_json = _write_artifact(tmp_path, art)
    _write_running_pilot(str(tmp_path / "out"))
    fresh = fresh if fresh is not None else _artifacts()
    return art, fp, prepared_json, _token_for(art), fresh


def _expected_qty(target, price, qty_step):
    return crun._runner_canon(crun.wb._floor_qty(Decimal(target), Decimal(price), Decimal(qty_step)))


# ---------------------------------------------------------------------------
# Strategy capital-base sizing: fixed capital base, never account equity (unrealized PnL)
# ---------------------------------------------------------------------------

def test_preparation_sizes_from_capital_base_not_account_equity():
    # Strategy capital base = 10000 (50 x 200 targets, from V1_CAPITAL_BASE_USD cross-validated
    # against config + state artifact). Account equity of 11000 reflects unrealized PnL only
    # and must NEVER enter the sizing basis. Authorized target gross must remain 10000.
    art, _ = _prepared_artifact(_artifacts(available_balance="11000"))
    assert art["strategy_capital_base_usd"] == "10000"
    assert all(p["target_notional_usd"] == "200" for p in art["order_payloads"])


def test_preparation_binds_supplied_upstream_capital_snapshot():
    # SYNTHETIC UNIT TEST: injects a higher upstream capital base (targets now 220) to verify
    # the fingerprint correctly binds whatever capital-base snapshot the upstream strategy plan
    # supplies. This does NOT prove automatic post-close compounding -- no such mechanism exists.
    # In production the capital base is currently fixed at V1_CAPITAL_BASE_USD == 10000.
    art, _ = _prepared_artifact(_artifacts(long_notional="220", short_notional="220"))
    assert art["strategy_capital_base_usd"] == "11000"
    assert all(p["target_notional_usd"] == "220" for p in art["order_payloads"])


# ---------------------------------------------------------------------------
# Pure verification of the immutable allocation intent (no fresh input)
# ---------------------------------------------------------------------------

def test_verify_intent_artifact_accepts_matching_token():
    art, fp = _prepared_artifact()
    ok, blockers, recomputed, allocations, capital = crun.verify_immutable_prepared_artifact(
        art, pilot_id=PILOT, date=DATE, token=_token_for(art))
    assert ok and blockers == []
    assert recomputed == fp and len(allocations) == 50 and capital == "10000"


def test_verify_intent_artifact_rejects_tampered_target_notional():
    art, _ = _prepared_artifact()
    art["order_payloads"][0]["target_notional_usd"] = "9999"   # tamper one target
    ok, blockers, _, _, _ = crun.verify_immutable_prepared_artifact(
        art, pilot_id=PILOT, date=DATE, token=_token_for(art))
    assert not ok
    assert "authorization_token_mismatch" in blockers
    assert "artifact_capital_inconsistent_with_targets" in blockers


def test_verify_intent_artifact_rejects_changed_capital_snapshot():
    art, _ = _prepared_artifact()
    token = _token_for(art)
    art["strategy_capital_base_usd"] = "11000"            # tamper the capital snapshot
    ok, blockers, _, _, _ = crun.verify_immutable_prepared_artifact(
        art, pilot_id=PILOT, date=DATE, token=token)
    assert not ok and "authorization_token_mismatch" in blockers


def test_verify_intent_artifact_rejects_token_from_other_artifact():
    art_a, _ = _prepared_artifact()
    art_b, _ = _prepared_artifact(_artifacts(long_notional="220", short_notional="220"))
    ok, blockers, _, _, _ = crun.verify_immutable_prepared_artifact(
        art_a, pilot_id=PILOT, date=DATE, token=_token_for(art_b))
    assert not ok and "authorization_token_mismatch" in blockers


def test_intent_fingerprint_is_price_independent():
    # Same intent + capital, different prep prices -> identical authorization fingerprint.
    art_100, fp100 = _prepared_artifact(_artifacts(price="100.0"))
    art_137, fp137 = _prepared_artifact(_artifacts(price="137.5"))
    assert fp100 == fp137


# ---------------------------------------------------------------------------
# Recompute executable qty from the authorized target + fresh price
# ---------------------------------------------------------------------------

def test_recompute_keeps_target_and_tracks_notional_when_price_moves():
    art, _ = _prepared_artifact(_artifacts(price="100.0"))
    fresh = _artifacts(price="110")                  # price moved up since preparation
    ok, blockers, actions, evidence = crun.build_executable_actions_from_authorized_intent(
        allocations=_allocs(art), pilot_id=PILOT, date=DATE,
        review=fresh[0], current_actions=fresh[1]["current_actions"], account=fresh[2])
    assert ok and blockers == []
    # Executable qty recomputed at fresh price; authorized target unchanged; actual ~ target.
    assert all(a.qty == _expected_qty("200", "110", "0.001") for a in actions)
    assert evidence["authorized_target_gross_notional_usd"] == "10000"
    # 50 x floor(200/110)*110 = 50 x 199.98 = 9999 (tracks target, NOT 11000).
    assert evidence["executed_actual_gross_notional_usd"] == "9999"


def test_unrealized_loss_does_not_change_sizing_but_low_balance_rejects(tmp_path, capsys):
    # Targets (sizing) unchanged at 10000; an unrealized loss reduced available balance so
    # margin feasibility rejects -- proving balance is a SAFETY input, not the sizing basis.
    art, fp, prepared_json, token, _ = _authorized(tmp_path)
    low_balance = _artifacts(available_balance="1050")
    build, calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        _exec_args(tmp_path, token=token, prepared_json=prepared_json),
        collect_feasibility=_fake_collector(*low_balance),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_BLOCKED and calls == []
    out = json.loads(capsys.readouterr().out)
    assert out["authorized_target_gross_notional_usd"] == "10000"   # sizing unchanged
    assert any("fresh_margin_not_pass" in b for b in out["fresh_feasibility_blockers"])


# ---------------------------------------------------------------------------
# Fresh-CH4A collector unit behaviour (unchanged seam)
# ---------------------------------------------------------------------------

def test_fresh_collector_runs_existing_ch4a_once_with_real_network_flag(tmp_path):
    review, market, account = _artifacts()
    calls = []
    args = _ch4a_args(tmp_path)
    r, ca, a = crun._collect_fresh_ch4a(
        args, invoke=_fake_ch4a_invoke(review, market, account, calls=calls))
    assert len(calls) == 1
    assert "--allow-real-network" in calls[0]
    assert "--current-market-demo-account-feasibility-read-only" in calls[0]
    assert ca == market["current_actions"]
    assert os.path.isdir(str(tmp_path / "preflight"))


def test_fresh_collector_nonzero_ch4a_exit_raises(tmp_path):
    review, market, account = _artifacts()
    with pytest.raises(crun.FreshCh4aError):
        crun._collect_fresh_ch4a(_ch4a_args(tmp_path),
                                 invoke=_fake_ch4a_invoke(review, market, account, rc=4))


def test_fresh_collector_preflight_dir_is_no_clobber(tmp_path):
    review, market, account = _artifacts()
    existing = tmp_path / "preflight"
    existing.mkdir()
    with pytest.raises(ValueError):
        crun._collect_fresh_ch4a(_ch4a_args(tmp_path, preflight=str(existing)),
                                 invoke=_fake_ch4a_invoke(review, market, account))


def test_production_execution_default_uses_fresh_ch4a_collector(tmp_path, capsys, monkeypatch):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    used = []

    def sentinel_collector(a):
        used.append(1)
        return fresh[0], fresh[1]["current_actions"], fresh[2]
    monkeypatch.setattr(crun, "_collect_fresh_ch4a", sentinel_collector)

    rc = crun._run_execute_prepared_demo_batch(
        _exec_args(tmp_path, token=token, prepared_json=prepared_json),
        build_transport=lambda *, credentials, env=None: FakeDemoTransport(),
        executor=nx.execute_daily_native, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_OK and used == [1]


# ---------------------------------------------------------------------------
# Date gate + CH4A failure: reject before transport
# ---------------------------------------------------------------------------

def test_old_execution_date_rejected_before_collection_and_transport(tmp_path):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    collect_calls = []
    build, build_calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        _exec_args(tmp_path, token=token, prepared_json=prepared_json),
        collect_feasibility=_fake_collector(*fresh, calls=collect_calls),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=OTHER_DATE)
    assert rc == crun.EXIT_INVALID
    assert collect_calls == [] and build_calls == []


def test_ch4a_failure_prevents_transport_and_execution(tmp_path):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)

    def failing_collector(a):
        raise crun.FreshCh4aError("ch4a_exit_nonzero:4")
    build, build_calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        _exec_args(tmp_path, token=token, prepared_json=prepared_json),
        collect_feasibility=failing_collector,
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_INPUT_FAILURE and build_calls == []


# ---------------------------------------------------------------------------
# Pre-send gates: none may construct a transport or call the engine
# ---------------------------------------------------------------------------

def _assert_rejected_no_transport(tmp_path, *, exit_code, fresh=None, env=DEMO_ENV,
                                  base_url=None, today=DATE, **arg_over):
    fresh = fresh if fresh is not None else _artifacts()
    build, calls = _tracking_builder()
    kw = dict(collect_feasibility=_fake_collector(*fresh),
              build_transport=build, executor=_boom_executor, env=env, today=today)
    if base_url is not None:
        kw["base_url"] = base_url
    rc = crun._run_execute_prepared_demo_batch(_exec_args(tmp_path, **arg_over), **kw)
    assert rc == exit_code
    assert calls == []
    return rc


def test_missing_send_flag_rejects_before_transport(tmp_path):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    _assert_rejected_no_transport(tmp_path, exit_code=crun.EXIT_INVALID, fresh=fresh,
                                  token=token, prepared_json=prepared_json, send=False)


def test_advance_on_success_flag_rejected_for_execution_mode(tmp_path):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    _assert_rejected_no_transport(tmp_path, exit_code=crun.EXIT_INVALID, fresh=fresh,
                                  token=token, prepared_json=prepared_json, advance=True)


def test_missing_token_rejects_before_transport(tmp_path):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    _assert_rejected_no_transport(tmp_path, exit_code=crun.EXIT_INVALID, fresh=fresh,
                                  token=None, prepared_json=prepared_json)


def test_missing_prepared_batch_json_rejects_before_transport(tmp_path):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    _assert_rejected_no_transport(tmp_path, exit_code=crun.EXIT_INVALID, fresh=fresh,
                                  token=token, prepared_json=None)


def test_wrong_token_rejects_before_transport(tmp_path):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    stale = crun.expected_batch_authorization_token(DATE, "deadbeefdeadbeef0000")
    _assert_rejected_no_transport(tmp_path, exit_code=crun.EXIT_INVALID, fresh=fresh,
                                  token=stale, prepared_json=prepared_json)


def test_token_from_other_artifact_rejects_before_transport(tmp_path):
    art_a, _ = _prepared_artifact()
    prepared_json = _write_artifact(tmp_path, art_a)
    _write_running_pilot(str(tmp_path / "out"))
    art_b, _ = _prepared_artifact(_artifacts(long_notional="220", short_notional="220"))
    _assert_rejected_no_transport(tmp_path, exit_code=crun.EXIT_INVALID,
                                  token=_token_for(art_b), prepared_json=prepared_json)


def test_tampered_target_notional_rejects_before_transport(tmp_path):
    art, _ = _prepared_artifact()
    token = _token_for(art)
    art["order_payloads"][0]["target_notional_usd"] = "9999"   # tamper after token issued
    prepared_json = _write_artifact(tmp_path, art)
    _write_running_pilot(str(tmp_path / "out"))
    _assert_rejected_no_transport(tmp_path, exit_code=crun.EXIT_INVALID,
                                  token=token, prepared_json=prepared_json)


def test_missing_prepared_artifact_file_rejects_before_transport(tmp_path):
    art, fp = _prepared_artifact()
    _write_running_pilot(str(tmp_path / "out"))
    missing = str(tmp_path / "does_not_exist.json")
    build, calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        _exec_args(tmp_path, token=_token_for(art), prepared_json=missing),
        collect_feasibility=_fake_collector(*_artifacts()),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_INPUT_FAILURE and calls == []


def test_non_demo_base_url_rejects_before_transport(tmp_path):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    _assert_rejected_no_transport(tmp_path, exit_code=crun.EXIT_INVALID, fresh=fresh,
                                  token=token, prepared_json=prepared_json, base_url=LIVE_BASE)


def test_missing_demo_credentials_rejects_before_transport(tmp_path):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    _assert_rejected_no_transport(tmp_path, exit_code=crun.EXIT_INVALID, fresh=fresh,
                                  env=NO_CRED_ENV, token=token, prepared_json=prepared_json)


def test_fresh_margin_failure_rejects_before_transport(tmp_path):
    art, fp, prepared_json, token, _ = _authorized(tmp_path)
    _assert_rejected_no_transport(tmp_path, exit_code=crun.EXIT_BLOCKED,
                                  fresh=_artifacts(available_balance="1050"),
                                  token=token, prepared_json=prepared_json)


def test_fresh_changed_instrument_rule_rejects_before_transport(tmp_path):
    art, fp, prepared_json, token, _ = _authorized(tmp_path)
    # qty_step huge so floor(200/100) rounds to 0 -> zero_quantity_after_rounding.
    _assert_rejected_no_transport(tmp_path, exit_code=crun.EXIT_BLOCKED,
                                  fresh=_artifacts(qty_step="5", min_order_qty="5"),
                                  token=token, prepared_json=prepared_json)


def test_fresh_protected_overlap_rejects_before_transport(tmp_path):
    art, fp, prepared_json, token, _ = _authorized(tmp_path)
    _assert_rejected_no_transport(tmp_path, exit_code=crun.EXIT_BLOCKED,
                                  fresh=_artifacts(overlaps=("SYM00USDT",)),
                                  token=token, prepared_json=prepared_json)


def test_fresh_symbol_not_trading_rejects_before_transport(tmp_path):
    art, fp, prepared_json, token, _ = _authorized(tmp_path)
    _assert_rejected_no_transport(tmp_path, exit_code=crun.EXIT_BLOCKED,
                                  fresh=_artifacts(instrument_status="PreLaunch", trading=False),
                                  token=token, prepared_json=prepared_json)


def test_pilot_state_incompatible_rejects_before_transport(tmp_path):
    art, fp = _prepared_artifact()
    prepared_json = _write_artifact(tmp_path, art)   # no RUNNING pilot written
    _assert_rejected_no_transport(tmp_path, exit_code=crun.EXIT_BLOCKED,
                                  token=_token_for(art), prepared_json=prepared_json)


def test_execute_mode_conflict_with_prepare_flag_rejects(tmp_path):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    args = _exec_args(tmp_path, token=token, prepared_json=prepared_json)
    args.prepare_from_ch4a = True
    build, calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        args, collect_feasibility=_fake_collector(*fresh),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_INVALID and calls == []


# ---------------------------------------------------------------------------
# send flag WITHOUT execute flag cannot enter the new batch path
# ---------------------------------------------------------------------------

def test_send_flag_without_execute_flag_cannot_dispatch(tmp_path, capsys, monkeypatch):
    def _boom_handler(*a, **k):
        raise AssertionError("execute handler must not run without --execute-prepared-demo-batch")

    def _boom_real(*a, **k):
        raise AssertionError("RealDemoOrderTransport must not be constructed")
    monkeypatch.setattr(crun, "_run_execute_prepared_demo_batch", _boom_handler)
    monkeypatch.setattr(crun, "RealDemoOrderTransport", _boom_real, raising=False)
    monkeypatch.setattr(crun.nx, "execute_daily_native", _boom_real)

    rc = crun.main(["--pilot-id", PILOT, "--date", DATE, "--send-orders-to-demo",
                    "--test-output-root", str(tmp_path / "out")])
    assert rc == crun.EXIT_BLOCKED
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == nx.DAY_NOT_RUNNING


def test_send_without_execute_running_pilot_uses_delegated_path_no_dispatch(
        tmp_path, capsys, monkeypatch):
    _write_running_pilot(str(tmp_path / "out"))

    def _boom(*a, **k):
        raise AssertionError("execution/transport must not run on the send-without-execute path")
    monkeypatch.setattr(crun, "_run_execute_prepared_demo_batch", _boom)
    monkeypatch.setattr(crun, "RealDemoOrderTransport", _boom, raising=False)
    monkeypatch.setattr(crun.nx, "execute_daily_native", _boom)
    monkeypatch.setattr(crun, "orchestrate_native_daily", _boom, raising=False)
    monkeypatch.setattr(crun.fs, "load_primary_forward_strategy_result", lambda **k: object())
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


# ---------------------------------------------------------------------------
# Full authorization: dispatch RECOMPUTED orders once, never advance Pilot
# ---------------------------------------------------------------------------

def test_fully_authorized_dispatches_recomputed_orders_once_without_advancing_pilot(
        tmp_path, capsys, monkeypatch):
    def _no_real(*a, **k):
        raise AssertionError("real transport must never be constructed")
    monkeypatch.setattr(crun, "RealDemoOrderTransport", _no_real, raising=False)

    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    fake_tp = FakeDemoTransport()
    builder_calls, exec_calls = [], []

    def build(*, credentials, env=None):
        builder_calls.append(1)
        return fake_tp

    def spy_exec(**kw):
        exec_calls.append(kw)
        return nx.execute_daily_native(**kw)

    rc = crun._run_execute_prepared_demo_batch(
        _exec_args(tmp_path, token=token, prepared_json=prepared_json),
        collect_feasibility=_fake_collector(*fresh),
        build_transport=build, executor=spy_exec, env=DEMO_ENV, today=DATE)

    assert rc == crun.EXIT_OK
    assert builder_calls == [1] and len(exec_calls) == 1
    assert len(exec_calls[0]["actions"]) == 50 and len(fake_tp.posts) == 50
    # At fresh price 100 the canonical qty is floor(200/100)=2.
    assert all(b["qty"] == _expected_qty("200", "100.0", "0.001") for _, b in fake_tp.posts)
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == crun.EXEC_BATCH_DISPATCHED
    assert summary["payload_fingerprint"] == fp
    assert summary["authorized_target_gross_notional_usd"] == "10000"
    assert summary["execute_daily_native_called"] == 1
    assert summary["order_post_count"] == 50
    assert summary["pilot_advanced"] is False
    state = rd.PilotStateStore(PILOT, str(tmp_path / "out")).read_state()
    assert state["completed_successful_days"] == 0 and state["successful_dates"] == []


def test_authorized_execution_recomputes_qty_when_price_moves(tmp_path, capsys):
    # Artifact prepared at price 100 (target 200). Fresh CH4A reports price 110.
    # The executable qty must change with price while the authorized fingerprint/target hold.
    art, fp = _prepared_artifact(_artifacts(price="100.0"))
    prepared_json = _write_artifact(tmp_path, art)
    _write_running_pilot(str(tmp_path / "out"))
    fresh = _artifacts(price="110")
    fake_tp = FakeDemoTransport()

    rc = crun._run_execute_prepared_demo_batch(
        _exec_args(tmp_path, token=_token_for(art), prepared_json=prepared_json),
        collect_feasibility=_fake_collector(*fresh),
        build_transport=lambda *, credentials, env=None: fake_tp,
        executor=nx.execute_daily_native, env=DEMO_ENV, today=DATE)

    assert rc == crun.EXIT_OK
    # Every POST carries the qty recomputed at fresh price 110 (1.818), NOT the prep qty (2).
    assert all(b["qty"] == _expected_qty("200", "110", "0.001") for _, b in fake_tp.posts)
    assert not any(b["qty"] == "2" for _, b in fake_tp.posts)
    summary = json.loads(capsys.readouterr().out)
    assert summary["payload_fingerprint"] == fp                       # fingerprint stable
    assert summary["authorized_target_gross_notional_usd"] == "10000"  # target unchanged
    assert summary["executed_actual_gross_notional_usd"] == "9999"  # ~ target, not 11000


def test_one_ambiguous_result_prevents_pilot_advancement(tmp_path, capsys):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    ambiguous_tp = FakeDemoTransport(ambiguous_first=True)
    rc = crun._run_execute_prepared_demo_batch(
        _exec_args(tmp_path, token=token, prepared_json=prepared_json),
        collect_feasibility=_fake_collector(*fresh),
        build_transport=lambda *, credentials, env=None: ambiguous_tp,
        executor=nx.execute_daily_native, env=DEMO_ENV, today=DATE)
    assert rc == crun.EXIT_AMBIGUOUS
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == crun.EXEC_BATCH_AMBIGUOUS
    assert summary["pilot_advanced"] is False
    state = rd.PilotStateStore(PILOT, str(tmp_path / "out")).read_state()
    assert state["completed_successful_days"] == 0


# ---------------------------------------------------------------------------
# Single machine-readable JSON on stdout (CH4A's own print is suppressed)
# ---------------------------------------------------------------------------

def test_execution_stdout_is_single_json_after_fresh_ch4a(tmp_path, capsys, monkeypatch):
    art, fp = _prepared_artifact()
    prepared_json = _write_artifact(tmp_path, art)
    _write_running_pilot(str(tmp_path / "out"))
    review, market, account = _artifacts()
    argv = ["--pilot-id", PILOT, "--date", DATE, "--execute-prepared-demo-batch",
            "--send-orders-to-demo", "--test-output-root", str(tmp_path / "out"),
            "--batch-authorization-token", _token_for(art),
            "--prepared-batch-json", prepared_json,
            "--review-artifact-json", "rev.json", "--review-artifact-sha256", "sha256:" + "a" * 64,
            "--anchor-manifest-json", "man.json", "--anchor-manifest-sha256", "sha256:" + "b" * 64,
            "--wrapper-json", "wrap.json",
            "--strategy-symbols-json", "sym.json", "--strategy-symbols-sha256", "sha256:" + "c" * 64,
            "--ch4a-preflight-dir", str(tmp_path / "preflight")]
    args = crun.build_parser().parse_args(argv)

    def printing_invoke(a):
        print(json.dumps({"status": "CH4A_INTERNAL_NOISE", "should_not_leak": True}))
        _fake_ch4a_invoke(review, market, account)(a)
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
    assert "CH4A_INTERNAL_NOISE" not in captured


# ---------------------------------------------------------------------------
# Manual-authorization handshake: preparation publishes intent fingerprint + token + capital
# ---------------------------------------------------------------------------

def test_preparation_output_includes_intent_fingerprint_token_and_capital(tmp_path, capsys):
    review, market, account = _artifacts()
    _write(tmp_path, review, market, account)
    out_path = tmp_path / "prepared.json"
    rc = crun.main(_argv(tmp_path, out=out_path))
    assert rc == crun.EXIT_OK
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == nx.BATCH_PREP_PREPARED
    assert out["strategy_capital_base_usd"] == "10000"
    assert all(p["target_notional_usd"] == "200" for p in out["order_payloads"])
    allocs, capital = crun._allocations_from_market_targets(
        out["order_payloads"], market["current_actions"])
    assert out["payload_fingerprint"] == crun.allocation_intent_fingerprint(
        allocs, pilot_id=PILOT, date=DATE, strategy_capital_base_usd="10000")
    assert out["expected_batch_authorization_token"].startswith(
        "CONFIRM_DEMO_NATIVE_BATCH_20260630_")
    # Round-trip: the artifact the prepare MODE wrote authorizes execution end to end.
    written = json.loads(out_path.read_text(encoding="utf-8"))
    ok, blockers, _, allocations, cap = crun.verify_immutable_prepared_artifact(
        written, pilot_id=PILOT, date=DATE,
        token=written["expected_batch_authorization_token"])
    assert ok and blockers == [] and cap == "10000"


# ---------------------------------------------------------------------------
# Durable exactly-once batch guard (pilot/date/allocation_intent_fingerprint)
# ---------------------------------------------------------------------------

def _run_once(tmp_path, *, token, prepared_json, fresh, build_transport=None,
              executor=None, today=DATE):
    return crun._run_execute_prepared_demo_batch(
        _exec_args(tmp_path, token=token, prepared_json=prepared_json),
        collect_feasibility=_fake_collector(*fresh),
        build_transport=build_transport or (lambda *, credentials, env=None: FakeDemoTransport()),
        executor=executor or nx.execute_daily_native, env=DEMO_ENV, today=today)


def test_second_invocation_after_success_rejects_before_transport(tmp_path, capsys):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    assert _run_once(tmp_path, token=token, prepared_json=prepared_json, fresh=fresh) == crun.EXIT_OK
    capsys.readouterr()
    # Second invocation: SAME token + intent, but fresh price moved (different executable qty).
    collect_calls = []
    build, build_calls = _tracking_builder()
    rc2 = crun._run_execute_prepared_demo_batch(
        _exec_args(tmp_path, token=token, prepared_json=prepared_json),
        collect_feasibility=_fake_collector(*_artifacts(price="110"), calls=collect_calls),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc2 == crun.EXIT_BLOCKED
    assert build_calls == [] and collect_calls == []          # before CH4A + transport
    out = json.loads(capsys.readouterr().out)
    assert out["blockers"] == [crun.EXEC_BATCH_ALREADY_ATTEMPTED]
    assert out["requires_reconciliation"] is True


def test_second_invocation_after_crash_mid_send_rejects_before_transport(tmp_path, capsys):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    sent = []

    def crashing_exec(*, pilot_id, date, actions, transport, output_root, base_url):
        # At least one order reaches Bybit, then the process crashes BEFORE the final summary.
        transport.post_order_create(url=base_url + "/v5/order/create",
                                    body={"orderLinkId": "X", "symbol": "S", "side": "Buy", "qty": "1"})
        sent.append(1)
        raise RuntimeError("crash before durable completion")

    with pytest.raises(RuntimeError):
        crun._run_execute_prepared_demo_batch(
            _exec_args(tmp_path, token=token, prepared_json=prepared_json),
            collect_feasibility=_fake_collector(*fresh),
            build_transport=lambda *, credentials, env=None: FakeDemoTransport(),
            executor=crashing_exec, env=DEMO_ENV, today=DATE)
    assert sent == [1]
    capsys.readouterr()
    # The guard was claimed BEFORE the first send, so it survived the crash -> retry blocked.
    build, build_calls = _tracking_builder()
    rc2 = crun._run_execute_prepared_demo_batch(
        _exec_args(tmp_path, token=token, prepared_json=prepared_json),
        collect_feasibility=_fake_collector(*_artifacts()),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc2 == crun.EXIT_BLOCKED and build_calls == []
    out = json.loads(capsys.readouterr().out)
    assert out["blockers"] == [crun.EXEC_BATCH_ALREADY_ATTEMPTED]


@pytest.mark.parametrize("token_kind,fresh_over,exit_code", [
    ("wrong_token", {}, "EXIT_INVALID"),
    ("good_token", {"available_balance": "1050"}, "EXIT_BLOCKED"),   # margin failure
])
def test_pre_send_rejection_consumes_no_attempt_record(tmp_path, capsys, token_kind, fresh_over, exit_code):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    use_token = token if token_kind == "good_token" else \
        crun.expected_batch_authorization_token(DATE, "deadbeefdeadbeef0000")
    build, calls = _tracking_builder()
    rc = crun._run_execute_prepared_demo_batch(
        _exec_args(tmp_path, token=use_token, prepared_json=prepared_json),
        collect_feasibility=_fake_collector(*_artifacts(**fresh_over)),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc == getattr(crun, exit_code) and calls == []
    capsys.readouterr()
    store = nx.NativeExecutionStore(PILOT, DATE, str(tmp_path / "out"))
    assert crun._read_batch_attempt(store) is None              # nothing consumed


def test_pre_send_rejection_is_retryable_after_correction(tmp_path, capsys):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path)
    wrong = crun.expected_batch_authorization_token(DATE, "deadbeefdeadbeef0000")
    build, calls = _tracking_builder()
    rc1 = crun._run_execute_prepared_demo_batch(
        _exec_args(tmp_path, token=wrong, prepared_json=prepared_json),
        collect_feasibility=_fake_collector(*fresh),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc1 == crun.EXIT_INVALID and calls == []
    capsys.readouterr()
    # Corrected token -> succeeds and only NOW claims the durable guard.
    rc2 = _run_once(tmp_path, token=token, prepared_json=prepared_json, fresh=fresh)
    assert rc2 == crun.EXIT_OK
    store = nx.NativeExecutionStore(PILOT, DATE, str(tmp_path / "out"))
    assert crun._read_batch_attempt(store)["allocation_intent_fingerprint"] == fp


def test_guard_key_is_pilot_date_fingerprint_not_qty_or_price(tmp_path, capsys):
    art, fp, prepared_json, token, fresh = _authorized(tmp_path, fresh=_artifacts(price="100.0"))
    assert _run_once(tmp_path, token=token, prepared_json=prepared_json, fresh=fresh) == crun.EXIT_OK
    capsys.readouterr()
    store = nx.NativeExecutionStore(PILOT, DATE, str(tmp_path / "out"))
    rec = crun._read_batch_attempt(store)
    assert rec["allocation_intent_fingerprint"] == fp
    assert rec["pilot_id"] == PILOT and rec["date"] == DATE
    # The durable identity carries NO qty / orderLinkId / price -> price/qty independent.
    blob = json.dumps(rec)
    assert "orderLinkId" not in blob and "qty" not in blob and "current_price" not in blob
    # A retry at a DIFFERENT fresh price (different executable qty) maps to the SAME identity.
    build, calls = _tracking_builder()
    rc2 = crun._run_execute_prepared_demo_batch(
        _exec_args(tmp_path, token=token, prepared_json=prepared_json),
        collect_feasibility=_fake_collector(*_artifacts(price="137.0")),
        build_transport=build, executor=_boom_executor, env=DEMO_ENV, today=DATE)
    assert rc2 == crun.EXIT_BLOCKED and calls == []
