"""TASK-014CF -- public read-only WebSocket ticker timestamp evidence.

Fully offline. Proves the endpoint/topic/credential guards, the authoritative
symbol-universe derivation, snapshot/delta price-timestamp binding semantics,
fail-closed ordering/replay protection, the canonical artifact + fingerprints,
the WebSocket-vs-REST counter separation, and that this task never promotes
execution readiness or touches the Pilot / orders / Live authorization.
"""
from __future__ import annotations

import importlib
import json
import pathlib
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_pilot_readiness as rd


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

STRATEGY_50 = sorted({f"SYM{i:02d}USDT" for i in range(50)})
LEGACY_2 = ["EDUUSDT", "POLYXUSDT"]


def make_universe(strategy=None, legacy=None):
    return ws.derive_required_symbol_universe(
        strategy_target_symbols=strategy if strategy is not None else STRATEGY_50,
        observed_legacy_symbols=legacy if legacy is not None else LEGACY_2,
        protected_symbol_allowlist=rd.PROTECTED_SYMBOLS,
        strategy_source_reference="unit-fixture-forward-record",
        legacy_source_reference="unit-fixture-observed-legacy",
    )


def snapshot_msg(symbol, *, ts, cs, last_price="100.5", extra=None):
    data = {"symbol": symbol, "lastPrice": last_price}
    if extra:
        data.update(extra)
    return {"topic": f"tickers.{symbol}", "type": "snapshot", "ts": ts, "cs": cs,
            "data": data}


def delta_msg(symbol, *, ts, cs, last_price=None, other=None):
    data = {"symbol": symbol}
    if last_price is not None:
        data["lastPrice"] = last_price
    if other:
        data.update(other)
    return {"topic": f"tickers.{symbol}", "type": "delta", "ts": ts, "cs": cs,
            "data": data}


def fresh_builder(universe=None, *, clock_offset="0.0068", offset_status="CLOCK_OFFSET_AVAILABLE",
                  stale_ms=10_000):
    return ws.PublicWsTickerEvidenceBuilder(
        universe=universe or make_universe(),
        clock_offset_seconds=clock_offset,
        clock_offset_status=offset_status,
        stale_threshold_ms=stale_ms,
    )


def feed_complete_all(builder, universe, *, base_ts, generation=0, now_ns):
    """Feed a valid snapshot for every symbol so all become COMPLETE."""
    for i, sym in enumerate(universe["symbols"]):
        builder.ingest_data_message(
            snapshot_msg(sym, ts=base_ts + i, cs=1000 + i),
            local_received_epoch_ns=now_ns,
            local_monotonic_received_ns=now_ns,
            connection_generation=generation)


# ---------------------------------------------------------------------------
# 1. Endpoint + topic guard
# ---------------------------------------------------------------------------

def test_exact_public_endpoint_allowed():
    assert ws.assert_public_endpoint_allowed(ws.PUBLIC_LINEAR_WS_ENDPOINT) == \
        "wss://stream.bybit.com/v5/public/linear"


@pytest.mark.parametrize("bad", [
    "wss://stream-demo.bybit.com/v5/public/linear",
    "wss://stream-testnet.bybit.com/v5/public/linear",
    "wss://stream.bybit.com/v5/private",
    "wss://stream.bybit.com/v5/trade",
    "wss://stream.bybit.com/v5/public/spot",
    "https://stream.bybit.com/v5/public/linear",
    "ws://stream.bybit.com/v5/public/linear",
])
def test_denied_endpoints(bad):
    with pytest.raises(ws.WsEndpointError):
        ws.assert_public_endpoint_allowed(bad)


def test_demo_private_host_is_not_used_for_public_data():
    # The Demo host supports private streams only; it must never be allowed.
    with pytest.raises(ws.WsEndpointError):
        ws.assert_public_endpoint_allowed("wss://stream-demo.bybit.com/v5/private")


@pytest.mark.parametrize("topic", [
    "position", "order", "wallet", "execution.linear", "greeks.BTC", "dcp",
    "orderbook.1.BTCUSDT", "publicTrade.BTCUSDT", "tickers.BTC", "tickers.",
])
def test_non_public_ticker_topics_denied(topic):
    with pytest.raises(ws.WsEndpointError):
        ws.assert_public_topic(topic)


def test_public_ticker_topic_accepted():
    assert ws.assert_public_topic("tickers.BTCUSDT") == "tickers.BTCUSDT"


# ---------------------------------------------------------------------------
# 2. Subscription / authentication impossibility + credential guard
# ---------------------------------------------------------------------------

def test_subscription_topics_are_deterministic_and_sorted():
    a = ws.build_subscription_message(["ETHUSDT", "BTCUSDT", "BTCUSDT"])
    b = ws.build_subscription_message(["BTCUSDT", "ETHUSDT"])
    assert a["args"] == b["args"] == ["tickers.BTCUSDT", "tickers.ETHUSDT"]
    assert a["op"] == "subscribe"


def test_subscription_message_has_no_auth_fields():
    msg = ws.build_subscription_message(["BTCUSDT"])
    assert "op" in msg and msg["op"] == "subscribe"
    assert not any(k.lower() in ("api_key", "sign", "signature") for k in msg)


def test_auth_op_payload_is_rejected():
    with pytest.raises(ws.WsEndpointError):
        ws.assert_no_credentials({"op": "auth", "args": ["k", "expires", "sig"]})


@pytest.mark.parametrize("payload", [
    {"api_key": "abc"},
    {"args": [{"X-BAPI-API-KEY": "abc"}]},
    {"nested": {"secret": "shh"}},
    {"sign": "deadbeef"},
])
def test_credential_keys_rejected(payload):
    with pytest.raises(ws.WsEndpointError):
        ws.assert_no_credentials(payload)


def test_credential_value_leak_rejected():
    with pytest.raises(ws.WsEndpointError):
        ws.assert_no_credentials({"note": "MYSECRETKEY"}, secret_values=["MYSECRETKEY"])


def test_clean_payload_passes_credential_guard():
    ws.assert_no_credentials({"op": "subscribe", "args": ["tickers.BTCUSDT"]},
                             secret_values=["MYSECRETKEY"])


# ---------------------------------------------------------------------------
# 3. Symbol-universe derivation
# ---------------------------------------------------------------------------

def test_universe_counts_52():
    u = make_universe()
    assert u["strategy_symbol_count"] == 50
    assert u["legacy_symbol_count"] == 2
    assert u["requested_symbol_count"] == 52
    assert u["unique_symbol_count"] == 52
    assert u["symbols"] == sorted(u["symbols"])
    assert "EDUUSDT" in u["symbols"] and "POLYXUSDT" in u["symbols"]


def test_universe_fingerprint_deterministic():
    assert make_universe()["symbol_universe_fingerprint"] == \
        make_universe()["symbol_universe_fingerprint"]


def test_universe_rejects_empty_symbol():
    with pytest.raises(ws.WsEndpointError):
        make_universe(strategy=STRATEGY_50[:-1] + [""])


def test_universe_rejects_non_linear_symbol():
    with pytest.raises(ws.WsEndpointError):
        make_universe(strategy=STRATEGY_50[:-1] + ["BTCUSD"])


def test_universe_rejects_duplicate_after_canonicalization():
    dup = STRATEGY_50[:-1] + [STRATEGY_50[0].lower()]
    with pytest.raises(ws.WsEndpointError):
        make_universe(strategy=dup)


def test_universe_rejects_legacy_outside_protected_allowlist():
    with pytest.raises(ws.WsEndpointError):
        make_universe(legacy=["EDUUSDT", "DOGEUSDT"])


def test_universe_rejects_protected_symbol_as_strategy_target():
    with pytest.raises(ws.WsEndpointError):
        make_universe(strategy=STRATEGY_50[:-1] + ["EDUUSDT"])


def test_universe_rejects_strategy_legacy_overlap():
    # POLYXUSDT is protected, so it cannot be a strategy target either; use a
    # protected symbol present in BOTH lists -> overlap caught.
    with pytest.raises(ws.WsEndpointError):
        ws.derive_required_symbol_universe(
            strategy_target_symbols=["EDUUSDT"], observed_legacy_symbols=["EDUUSDT"],
            protected_symbol_allowlist=rd.PROTECTED_SYMBOLS,
            strategy_source_reference="x", legacy_source_reference="y")


# ---------------------------------------------------------------------------
# 4. Snapshot / delta semantics
# ---------------------------------------------------------------------------

def test_snapshot_then_delta_with_price_refreshes_timestamp():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u)
    now = time.time_ns()
    assert b.ingest_data_message(snapshot_msg("AAAUSDT", ts=100, cs=1),
                                 local_received_epoch_ns=now,
                                 local_monotonic_received_ns=now,
                                 connection_generation=0) == "price_updated"
    out = b.ingest_data_message(delta_msg("AAAUSDT", ts=200, cs=2, last_price="101.0"),
                                local_received_epoch_ns=now + 1,
                                local_monotonic_received_ns=now + 1,
                                connection_generation=0)
    assert out == "price_updated"
    ev = b._symbols["AAAUSDT"]
    assert ev.selected_price == "101.0"
    assert ev.selected_price_ts_ms == 200
    assert ev.selected_price_message_type == "delta"


def test_delta_without_price_field_does_not_refresh_price_timestamp():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u)
    now = time.time_ns()
    b.ingest_data_message(snapshot_msg("AAAUSDT", ts=100, cs=1, last_price="100.0"),
                          local_received_epoch_ns=now, local_monotonic_received_ns=now,
                          connection_generation=0)
    out = b.ingest_data_message(
        delta_msg("AAAUSDT", ts=500, cs=2, other={"turnover24h": "9"}),
        local_received_epoch_ns=now + 1, local_monotonic_received_ns=now + 1,
        connection_generation=0)
    assert out == "no_price_change"
    ev = b._symbols["AAAUSDT"]
    # price timestamp stays pinned to the snapshot that carried lastPrice
    assert ev.selected_price == "100.0"
    assert ev.selected_price_ts_ms == 100
    assert ev.selected_price_updated_in_last_message is False
    # ordering counters still advanced
    assert ev.last_accepted_cs == 2 and ev.last_accepted_ts == 500


def test_delta_before_snapshot_fails_closed():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u)
    now = time.time_ns()
    out = b.ingest_data_message(delta_msg("AAAUSDT", ts=100, cs=1, last_price="1.0"),
                                local_received_epoch_ns=now,
                                local_monotonic_received_ns=now,
                                connection_generation=0)
    assert out == "delta_before_snapshot"
    assert b._symbols["AAAUSDT"].hard_fail_status == ws.WS_SNAPSHOT_MISSING


def test_decimal_price_string_preserved():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u)
    now = time.time_ns()
    b.ingest_data_message(snapshot_msg("AAAUSDT", ts=100, cs=1, last_price="0.000012340"),
                          local_received_epoch_ns=now, local_monotonic_received_ns=now,
                          connection_generation=0)
    ev = b._symbols["AAAUSDT"]
    assert ev.selected_price == "0.000012340"  # exact string, no float coercion
    assert isinstance(ev.selected_price, str)


def test_local_epoch_and_monotonic_retained():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u)
    b.ingest_data_message(snapshot_msg("AAAUSDT", ts=100, cs=1),
                          local_received_epoch_ns=123456789,
                          local_monotonic_received_ns=987654321,
                          connection_generation=0)
    ev = b._symbols["AAAUSDT"]
    assert ev.selected_price_local_received_epoch_ns == 123456789
    assert ev.selected_price_local_monotonic_received_ns == 987654321


# ---------------------------------------------------------------------------
# 5/6. Fail-closed validation + ordering/replay protection
# ---------------------------------------------------------------------------

def test_topic_data_symbol_mismatch_fails_closed():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u)
    now = time.time_ns()
    msg = {"topic": "tickers.AAAUSDT", "type": "snapshot", "ts": 1, "cs": 1,
           "data": {"symbol": "BBBUSDT", "lastPrice": "1"}}
    assert b.ingest_data_message(msg, local_received_epoch_ns=now,
                                 local_monotonic_received_ns=now,
                                 connection_generation=0) == "symbol_topic_mismatch"
    assert b._symbols["AAAUSDT"].hard_fail_status == ws.WS_SYMBOL_TOPIC_MISMATCH


def test_malformed_ts_fails_closed():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u)
    now = time.time_ns()
    msg = {"topic": "tickers.AAAUSDT", "type": "snapshot", "ts": "not-a-number",
           "cs": 1, "data": {"symbol": "AAAUSDT", "lastPrice": "1"}}
    assert b.ingest_data_message(msg, local_received_epoch_ns=now,
                                 local_monotonic_received_ns=now,
                                 connection_generation=0) == "ts_invalid"
    assert b._symbols["AAAUSDT"].hard_fail_status == ws.WS_TIMESTAMP_INVALID


def test_malformed_cs_fails_closed():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u)
    now = time.time_ns()
    msg = {"topic": "tickers.AAAUSDT", "type": "snapshot", "ts": 1, "cs": None,
           "data": {"symbol": "AAAUSDT", "lastPrice": "1"}}
    assert b.ingest_data_message(msg, local_received_epoch_ns=now,
                                 local_monotonic_received_ns=now,
                                 connection_generation=0) == "cs_invalid"
    assert b._symbols["AAAUSDT"].hard_fail_status == ws.WS_TIMESTAMP_INVALID


def test_sequence_regression_fails_closed():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u)
    now = time.time_ns()
    b.ingest_data_message(snapshot_msg("AAAUSDT", ts=100, cs=10),
                          local_received_epoch_ns=now, local_monotonic_received_ns=now,
                          connection_generation=0)
    out = b.ingest_data_message(delta_msg("AAAUSDT", ts=110, cs=5, last_price="2"),
                                local_received_epoch_ns=now + 1,
                                local_monotonic_received_ns=now + 1,
                                connection_generation=0)
    assert out == "cs_regression"
    assert b._symbols["AAAUSDT"].hard_fail_status == ws.WS_SEQUENCE_REGRESSION
    assert b.ws_out_of_order_message_count == 1


def test_timestamp_regression_fails_closed():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u)
    now = time.time_ns()
    b.ingest_data_message(snapshot_msg("AAAUSDT", ts=500, cs=10),
                          local_received_epoch_ns=now, local_monotonic_received_ns=now,
                          connection_generation=0)
    out = b.ingest_data_message(delta_msg("AAAUSDT", ts=400, cs=11, last_price="2"),
                                local_received_epoch_ns=now + 1,
                                local_monotonic_received_ns=now + 1,
                                connection_generation=0)
    assert out == "ts_regression"
    assert b._symbols["AAAUSDT"].hard_fail_status == ws.WS_TIMESTAMP_REGRESSION


def test_duplicate_messages_counted():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u)
    now = time.time_ns()
    b.ingest_data_message(snapshot_msg("AAAUSDT", ts=100, cs=10),
                          local_received_epoch_ns=now, local_monotonic_received_ns=now,
                          connection_generation=0)
    out = b.ingest_data_message(delta_msg("AAAUSDT", ts=100, cs=10, last_price="2"),
                                local_received_epoch_ns=now + 1,
                                local_monotonic_received_ns=now + 1,
                                connection_generation=0)
    assert out == "duplicate"
    assert b._symbols["AAAUSDT"].duplicate_message_count == 1
    assert b.ws_duplicate_message_count == 1


def test_reconnect_generation_conflict_fails_closed():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u)
    now = time.time_ns()
    b.ingest_data_message(snapshot_msg("AAAUSDT", ts=100, cs=10),
                          local_received_epoch_ns=now, local_monotonic_received_ns=now,
                          connection_generation=0)
    out = b.ingest_data_message(delta_msg("AAAUSDT", ts=110, cs=11, last_price="2"),
                                local_received_epoch_ns=now + 1,
                                local_monotonic_received_ns=now + 1,
                                connection_generation=1)
    assert out == "generation_conflict"
    assert b._symbols["AAAUSDT"].hard_fail_status == ws.WS_CONNECTION_GENERATION_CONFLICT


# ---------------------------------------------------------------------------
# 7/8/9. Artifact, statuses, coverage
# ---------------------------------------------------------------------------

def test_full_coverage_becomes_complete():
    u = make_universe()
    b = fresh_builder(u)
    now = time.time_ns()
    feed_complete_all(b, u, base_ts=int(now / 1e6) - 1000, now_ns=now)
    art = b.build_artifact(finalize_epoch_ns=now + 5_000_000,
                           subscription_acknowledged=True)
    assert art["overall_status"] == ws.WS_TICKER_EVIDENCE_COMPLETE
    assert art["coverage_summary"]["complete_symbol_count"] == 52
    assert art["coverage_summary"]["all_required_complete"] is True


def test_51_of_52_remains_partial():
    u = make_universe()
    b = fresh_builder(u)
    now = time.time_ns()
    base_ts = int(now / 1e6) - 1000
    for i, sym in enumerate(u["symbols"][:-1]):
        b.ingest_data_message(snapshot_msg(sym, ts=base_ts + i, cs=1000 + i),
                              local_received_epoch_ns=now,
                              local_monotonic_received_ns=now, connection_generation=0)
    art = b.build_artifact(finalize_epoch_ns=now + 5_000_000)
    assert art["overall_status"] == ws.WS_TICKER_EVIDENCE_PARTIAL
    assert art["coverage_summary"]["complete_symbol_count"] == 51
    missing = u["symbols"][-1]
    statuses = {r["symbol"]: r["evidence_status"] for r in art["per_symbol_evidence"]}
    assert statuses[missing] == ws.WS_SNAPSHOT_MISSING


def test_no_coverage_unavailable():
    u = make_universe()
    b = fresh_builder(u)
    art = b.build_artifact(finalize_epoch_ns=time.time_ns())
    assert art["overall_status"] == ws.WS_TICKER_EVIDENCE_UNAVAILABLE


def test_stale_evidence_remains_incomplete():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u, stale_ms=10)
    recv_ns = time.time_ns()
    b.ingest_data_message(snapshot_msg("AAAUSDT", ts=int(recv_ns / 1e6), cs=1),
                          local_received_epoch_ns=recv_ns,
                          local_monotonic_received_ns=recv_ns, connection_generation=0)
    art = b.build_artifact(finalize_epoch_ns=recv_ns + 5_000_000_000)  # +5s, stale@10ms
    row = art["per_symbol_evidence"][0]
    assert row["evidence_status"] == ws.WS_TIMESTAMP_STALE
    assert art["overall_status"] != ws.WS_TICKER_EVIDENCE_COMPLETE


def test_transport_delay_is_deterministic_with_clock_offset():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u, clock_offset="0.0068", offset_status="CLOCK_OFFSET_AVAILABLE")
    recv_ns = 1_700_000_000_000_000_000  # fixed epoch ns
    ts_ms = 1_700_000_000_000             # exchange ts == recv second
    b.ingest_data_message(snapshot_msg("AAAUSDT", ts=ts_ms, cs=1),
                          local_received_epoch_ns=recv_ns,
                          local_monotonic_received_ns=recv_ns, connection_generation=0)
    art = b.build_artifact(finalize_epoch_ns=recv_ns + 1_000_000)
    row = art["per_symbol_evidence"][0]
    # delay = (recv_epoch_s + 0.0068) - ts_s = 0.0068 s = 6.8 ms
    assert row["estimated_transport_delay_ms"] == pytest.approx(6.8, abs=1e-6)


def test_missing_clock_offset_blocks_complete():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = fresh_builder(u, clock_offset=None, offset_status=None)
    recv_ns = time.time_ns()
    b.ingest_data_message(snapshot_msg("AAAUSDT", ts=int(recv_ns / 1e6), cs=1),
                          local_received_epoch_ns=recv_ns,
                          local_monotonic_received_ns=recv_ns, connection_generation=0)
    art = b.build_artifact(finalize_epoch_ns=recv_ns + 1_000_000)
    assert art["per_symbol_evidence"][0]["estimated_transport_delay_ms"] is None
    assert art["per_symbol_evidence"][0]["evidence_status"] == ws.WS_TIMESTAMP_STALE


def test_artifact_fingerprint_deterministic_and_no_credentials():
    u = make_universe()
    now = 1_700_000_000_000_000_000
    arts = []
    for _ in range(2):
        b = fresh_builder(u)
        for i, sym in enumerate(u["symbols"]):
            b.ingest_data_message(snapshot_msg(sym, ts=1_700_000_000_000 + i, cs=1000 + i),
                                  local_received_epoch_ns=now,
                                  local_monotonic_received_ns=now, connection_generation=0)
        arts.append(b.build_artifact(finalize_epoch_ns=now + 1_000_000,
                                     subscription_acknowledged=True))
    assert arts[0]["artifact_fingerprint"] == arts[1]["artifact_fingerprint"]
    # artifact carries no credential key
    ws.assert_no_credentials(arts[0], secret_values=["irrelevant"])


def test_planner_price_field_recorded():
    art = fresh_builder().build_artifact(finalize_epoch_ns=time.time_ns())
    assert art["planner_price_field"] == "lastPrice"
    assert "demo_market_price_guard" in art["planner_price_field_source"]
    assert art["exchange_timestamp_label"] == "exchange_data_generated_ts_ms"


# ---------------------------------------------------------------------------
# 10/11. No execution promotion + counter separation
# ---------------------------------------------------------------------------

def test_task_never_promotes_execution_readiness():
    u = make_universe()
    b = fresh_builder(u)
    now = time.time_ns()
    feed_complete_all(b, u, base_ts=int(now / 1e6) - 1000, now_ns=now)
    art = b.build_artifact(finalize_epoch_ns=now + 1_000_000,
                           subscription_acknowledged=True)
    assert art["overall_status"] == ws.WS_TICKER_EVIDENCE_COMPLETE
    assert art["execution_batch_authorized"] is False
    assert art["execution_ready"] is False
    assert art["sender_reachable"] is False
    assert art["order_post_count"] == 0
    assert art["amend_post_count"] == 0
    assert art["cancel_post_count"] == 0
    assert art["live_order_post_count"] == 0
    assert art["freshness_summary"]["execution_grade_freshness_complete"] is False
    assert art["freshness_summary"]["rest_planner_prices_replaced"] is False
    assert ws.PRICE_FRESHNESS_EVIDENCE_PARTIAL in art["blockers"]
    assert ws.PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE in art["blockers"]
    assert art["blockers"][-1] == ws.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK


def test_websocket_counters_scoped_separately_from_rest():
    art = fresh_builder().build_artifact(finalize_epoch_ns=time.time_ns())
    audit = art["message_audit"]
    for k in audit:
        assert k.startswith("ws_")
    # No REST counter keys leak into the WebSocket audit.
    for forbidden in ("total_public_get_count", "ticker_http_request_count",
                      "total_private_read_only_get_count"):
        assert forbidden not in audit


def test_rest_modules_not_imported_by_ws_core():
    # The pure WS evidence core must not pull in REST client / executor modules.
    import src.demo_public_ws_ticker_evidence as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for forbidden in ("import main", "BybitExecutor", "demo_readonly_client",
                      "demo_only_tiny_execution"):
        assert forbidden not in src


# ---------------------------------------------------------------------------
# 12. Collector script imports offline, derives universe, no network by default
# ---------------------------------------------------------------------------

def test_collector_script_imports_without_websocket_or_network():
    mod = importlib.import_module("scripts.collect_public_ws_ticker_evidence")
    assert hasattr(mod, "main") and hasattr(mod, "build_universe")
    assert mod.PROTECTED_SYMBOL_ALLOWLIST == tuple(rd.PROTECTED_SYMBOLS)
