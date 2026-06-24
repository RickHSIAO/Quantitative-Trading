"""TASK-014CG -- CLI for the Plan-only WebSocket price binding.

Proves the default behavior does nothing without the explicit opt-in, the opt-in
requires an explicit WS artifact path, the dry-run fixture command performs 50
Plan-only bindings with zero network and zero execution calls, and an execution
authorization marker / reachable sender refuses the binding path.
"""
from __future__ import annotations

import json
import time

import pytest

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_native_ws_price_binding as wb
from src import demo_strategy_pilot_readiness as rd

import importlib.util
import os

_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "scripts", "bind_plan_prices_to_ws_evidence.py")
_spec = importlib.util.spec_from_file_location("bind_plan_prices_to_ws_evidence", _SCRIPT)
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)

STRATEGY_50 = sorted({f"SYM{i:02d}USDT" for i in range(50)})
LEGACY_2 = ["EDUUSDT", "POLYXUSDT"]


def _build_ws(now_ns):
    u = ws.derive_required_symbol_universe(
        strategy_target_symbols=STRATEGY_50, observed_legacy_symbols=LEGACY_2,
        protected_symbol_allowlist=rd.PROTECTED_SYMBOLS,
        strategy_source_reference="cg", legacy_source_reference="cg")
    b = ws.PublicWsTickerEvidenceBuilder(
        universe=u, clock_offset_seconds="0.0068",
        clock_offset_status="CLOCK_OFFSET_AVAILABLE",
        clock_offset_provenance_status=ws.CLOCK_OFFSET_PROVENANCE_AUTHORITATIVE,
        stale_threshold_ms=10_000)
    b.record_connection_success(0)
    b.record_subscription_request(52, request_id="cf-public-ticker", generation=0)
    b.ingest_subscription_ack({"op": "subscribe", "success": True, "req_id": "cf-public-ticker"},
                              connection_generation=0, received_epoch_ns=now_ns)
    base = int(now_ns / 1e6)
    for i, sym in enumerate(u["symbols"]):
        b.ingest_data_message(
            {"topic": f"tickers.{sym}", "type": "snapshot", "ts": base - i, "cs": 1000 + i,
             "data": {"symbol": sym, "lastPrice": "100.5"}},
            local_received_epoch_ns=now_ns, local_monotonic_received_ns=now_ns,
            connection_generation=0)
    return b.build_artifact(
        finalize_epoch_ns=now_ns + 1_000_000, legacy_position_provenance={
            "symbol_universe_source_status": ws.SYMBOL_UNIVERSE_SOURCE_AUTHORITATIVE},
        dependency_status=ws.WS_CLIENT_DEPENDENCY_AVAILABLE, require_complete=True,
        allow_real_network=True,
        completion_meta={"collection_terminated_reason": ws.TERMINATED_COMPLETE_AND_ACKED})


def _build_plan():
    targets = []
    for i, sym in enumerate(STRATEGY_50):
        side = "long" if i % 2 == 0 else "short"
        weight = "0.02" if side == "long" else "-0.02"
        targets.append({"symbol": sym, "side": side, "price": "100.0",
                        "target_weight": weight, "target_notional": "200",
                        "qty": "1.99", "qty_step": "0.001"})
    return {"date": "2026-06-22", "active_policy": wb.ACTIVE_STRATEGY_NATIVE_V1_POLICY,
            "strategy_native_review": {"active_strategy": wb.EXPECTED_STRATEGY_NAME},
            "planner": {"sizing_verification": {"capital_base_usd": 10000},
                        "target_positions": targets}}


def _write(tmp_path, now_ns):
    plan_p = tmp_path / "plan.json"
    ws_p = tmp_path / "ws.json"
    plan_p.write_text(json.dumps(_build_plan()), encoding="utf-8")
    ws_p.write_text(json.dumps(_build_ws(now_ns)), encoding="utf-8")
    return str(plan_p), str(ws_p)


def test_default_without_opt_in_does_nothing(tmp_path, capsys):
    now = time.time_ns()
    plan_p, ws_p = _write(tmp_path, now)
    rc = cli.main(["--plan-json", plan_p, "--ws-ticker-evidence-json", ws_p])
    assert rc == cli.EXIT_INVALID_CONFIG
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "REFUSED_OPT_IN_REQUIRED"
    assert out["order_post_count"] == 0


def test_opt_in_requires_explicit_ws_path():
    with pytest.raises(SystemExit):
        cli.main(["--plan-json", "x.json", "--bind-plan-prices-to-ws-evidence"])


def test_dry_run_fixture_binds_fifty_with_zero_network_and_execution(tmp_path, capsys):
    now = time.time_ns()
    plan_p, ws_p = _write(tmp_path, now)
    out_p = tmp_path / "binding.json"
    rc = cli.main([
        "--plan-json", plan_p, "--ws-ticker-evidence-json", ws_p,
        "--bind-plan-prices-to-ws-evidence", "--out", str(out_p),
        "--require-complete", "--verify-no-credential-leak",
        "--unsafe-test-binding-epoch-ns", str(now + 2_000_000),
        "--unsafe-allow-test-overrides", "--json-only"])
    assert rc == cli.EXIT_COMPLETE
    art = json.loads(out_p.read_text(encoding="utf-8"))
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_COMPLETE
    assert art["binding_parity_status"] == wb.WS_PLANNER_BINDING_PARITY_PASS
    assert art["bound_action_count"] == 50
    assert art["failed_action_count"] == 0
    assert art["execution_grade_freshness_complete"] is True
    assert art["execution_batch_authorized"] is False
    assert art["order_post_count"] == 0
    assert art["live_order_post_count"] == 0
    na = art["binding_network_audit"]
    assert na == {"private_http_count": 0, "public_http_count": 0,
                  "websocket_connection_count": 0, "order_endpoint_count": 0}
    assert art["credential_leak_check"] == "NO_CREDENTIAL_VALUE_OR_KEY_PRESENT"


def test_execution_authorization_marker_refuses(tmp_path, capsys, monkeypatch):
    now = time.time_ns()
    plan_p, ws_p = _write(tmp_path, now)
    monkeypatch.setenv("DEMO_EXECUTION_AUTHORIZATION_MARKER", "PRESENT")
    rc = cli.main(["--plan-json", plan_p, "--ws-ticker-evidence-json", ws_p,
                   "--bind-plan-prices-to-ws-evidence"])
    assert rc == cli.EXIT_SAFETY
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "REFUSED_EXECUTION_AUTHORIZATION_MARKER_PRESENT"


def test_sender_reachable_refuses(tmp_path, capsys, monkeypatch):
    now = time.time_ns()
    plan_p, ws_p = _write(tmp_path, now)
    monkeypatch.setenv("DEMO_SENDER_REACHABLE", "1")
    rc = cli.main(["--plan-json", plan_p, "--ws-ticker-evidence-json", ws_p,
                   "--bind-plan-prices-to-ws-evidence"])
    assert rc == cli.EXIT_SAFETY
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "REFUSED_SENDER_REACHABLE_ENABLED"


def test_require_complete_returns_nonzero_on_partial(tmp_path):
    now = time.time_ns()
    plan_p, ws_p = _write(tmp_path, now)
    # Drop one WS evidence symbol -> 49/50 PARTIAL.
    ws_art = json.loads(open(ws_p, encoding="utf-8").read())
    ws_art["per_symbol_evidence"] = [r for r in ws_art["per_symbol_evidence"]
                                     if r["symbol"] != STRATEGY_50[0]]
    ws_art["artifact_fingerprint"] = ws._fingerprint(
        {k: v for k, v in ws_art.items() if k != "artifact_fingerprint"})
    open(ws_p, "w", encoding="utf-8").write(json.dumps(ws_art))
    rc = cli.main([
        "--plan-json", plan_p, "--ws-ticker-evidence-json", ws_p,
        "--bind-plan-prices-to-ws-evidence", "--require-complete", "--json-only",
        "--out", str(tmp_path / "b.json"),
        "--unsafe-test-binding-epoch-ns", str(now + 2_000_000),
        "--unsafe-allow-test-overrides"])
    assert rc == cli.EXIT_PARTIAL


def test_test_only_override_rejected_outside_temp_or_pytest(tmp_path, monkeypatch, capsys):
    # Simulate production: no PYTEST_CURRENT_TEST and a non-temp out path.
    now = time.time_ns()
    plan_p, ws_p = _write(tmp_path, now)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    rc = cli.main([
        "--plan-json", plan_p, "--ws-ticker-evidence-json", ws_p,
        "--bind-plan-prices-to-ws-evidence",
        "--out", "C:/not-a-temp-dir/binding.json",
        "--unsafe-test-binding-epoch-ns", str(now),
        "--unsafe-allow-test-overrides"])
    assert rc == cli.EXIT_INVALID_CONFIG
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "REFUSED_TEST_ONLY_OPTION"
