"""TASK-014CF_FIX3 -- ACK-gated early completion + canonical control-plane status.

Fully offline. Proves: full completion requires BOTH all required same-generation
price-timestamp evidence fresh-and-complete AND a valid subscription ACK; data
messages are never treated as an implicit ACK; a late ACK is accepted only while
all evidence is still fresh; missing/rejected/mismatched ACK fails closed; the
canonical overall_status, completion_achieved, control-plane parity and exit code
are all consistent; and FIX2 data-plane behavior is preserved.
"""
from __future__ import annotations

import time

import pytest

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_pilot_readiness as rd

STRATEGY_50 = sorted({f"SYM{i:02d}USDT" for i in range(50)})
LEGACY_2 = ["EDUUSDT", "POLYXUSDT"]
REQ_ID = "cf-public-ticker"


def make_universe(strategy=None, legacy=None):
    return ws.derive_required_symbol_universe(
        strategy_target_symbols=strategy if strategy is not None else STRATEGY_50,
        observed_legacy_symbols=legacy if legacy is not None else LEGACY_2,
        protected_symbol_allowlist=rd.PROTECTED_SYMBOLS,
        strategy_source_reference="fix3", legacy_source_reference="fix3")


def builder(universe=None, *, stale_ms=10_000, req_id=REQ_ID, generation=0):
    b = ws.PublicWsTickerEvidenceBuilder(
        universe=universe or make_universe(), clock_offset_seconds="0.0068",
        clock_offset_status="CLOCK_OFFSET_AVAILABLE",
        clock_offset_provenance_status=ws.CLOCK_OFFSET_PROVENANCE_AUTHORITATIVE,
        stale_threshold_ms=stale_ms)
    b.record_connection_success(generation)
    b.record_subscription_request(universe["unique_symbol_count"] if universe else 52,
                                  request_id=req_id, generation=generation)
    return b


def ack_msg(*, success=True, req_id=REQ_ID):
    m = {"op": "subscribe", "success": success}
    if req_id is not None:
        m["req_id"] = req_id
    return m


def snap(symbol, *, ts, cs, last_price="100.5"):
    return {"topic": f"tickers.{symbol}", "type": "snapshot", "ts": ts, "cs": cs,
            "data": {"symbol": symbol, "lastPrice": last_price}}


def feed_fresh_all(b, universe, *, now_ns, generation=0):
    base_ts = int(now_ns / 1e6)
    for i, sym in enumerate(universe["symbols"]):
        b.ingest_data_message(snap(sym, ts=base_ts - i, cs=1000 + i),
                              local_received_epoch_ns=now_ns,
                              local_monotonic_received_ns=now_ns,
                              connection_generation=generation)


AUTH_PROV = {"symbol_universe_source_status": ws.SYMBOL_UNIVERSE_SOURCE_AUTHORITATIVE}


# ---------------------------------------------------------------------------
# 1. ACK before symbol completion
# ---------------------------------------------------------------------------

def test_ack_first_then_no_early_termination_until_final_symbol():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    b.ingest_subscription_ack(ack_msg(), connection_generation=0, received_epoch_ns=now)
    base_ts = int(now / 1e6)
    for i, sym in enumerate(u["symbols"][:-1]):  # 51/52
        b.ingest_data_message(snap(sym, ts=base_ts - i, cs=1000 + i),
                              local_received_epoch_ns=now,
                              local_monotonic_received_ns=now, connection_generation=0)
    assert b.evaluate_completion(check_epoch_ns=now + 1_000_000)["full_complete"] is False
    b.ingest_data_message(snap(u["symbols"][-1], ts=base_ts, cs=2000),
                          local_received_epoch_ns=now,
                          local_monotonic_received_ns=now, connection_generation=0)
    assert b.evaluate_completion(check_epoch_ns=now + 1_000_000)["full_complete"] is True


# ---------------------------------------------------------------------------
# 2. All 52 complete before ACK
# ---------------------------------------------------------------------------

def test_data_complete_before_ack_then_ack_completes():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    ev = b.evaluate_completion(check_epoch_ns=now + 1_000_000)
    assert ev["data_complete"] is True
    assert ev["subscription_acknowledged"] is False
    assert ev["full_complete"] is False  # keep reading for ACK
    b.ingest_subscription_ack(ack_msg(), connection_generation=0, received_epoch_ns=now + 2)
    ev2 = b.evaluate_completion(check_epoch_ns=now + 2_000_000)
    assert ev2["full_complete"] is True


# ---------------------------------------------------------------------------
# 3. All symbols complete but ACK never arrives
# ---------------------------------------------------------------------------

def test_data_complete_no_ack_is_partial_exit_four():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    art = b.build_artifact(
        finalize_epoch_ns=now + 1_000_000, legacy_position_provenance=AUTH_PROV,
        dependency_status=ws.WS_CLIENT_DEPENDENCY_AVAILABLE, require_complete=True,
        allow_real_network=True,
        completion_meta={"collection_terminated_reason": ws.TERMINATED_DATA_WAITING_FOR_ACK})
    assert art["overall_status"] == ws.WS_TICKER_EVIDENCE_PARTIAL
    assert art["cli_exit_status"] == ws.EXIT_WS_UNAVAILABLE
    assert art["cli_exit_reason"] == "subscription_not_acknowledged"
    assert art["coverage_summary"]["complete_symbol_count"] == 52  # 52/52 still visible
    assert art["early_completion"]["completion_achieved"] is False
    assert ws.WS_SUBSCRIPTION_ACKNOWLEDGEMENT_MISSING in art["blockers"]
    assert art["subscription_ack"]["subscription_ack_status"] == ws.WS_SUBSCRIPTION_ACK_MISSING


# ---------------------------------------------------------------------------
# 4. ACK after data became stale
# ---------------------------------------------------------------------------

def test_late_ack_after_stale_requires_refresh():
    u = make_universe(strategy=["AAAUSDT", "BBBUSDT"], legacy=[])
    b = builder(u, stale_ms=50)
    now = time.time_ns()
    ts0 = int(now / 1e6)
    for sym in ("AAAUSDT", "BBBUSDT"):
        b.ingest_data_message(snap(sym, ts=ts0, cs=1, last_price="10.0"),
                              local_received_epoch_ns=now,
                              local_monotonic_received_ns=now, connection_generation=0)
    # ACK arrives 5 seconds later -> the earlier evidence is now stale
    late = now + 5_000_000_000
    b.ingest_subscription_ack(ack_msg(), connection_generation=0, received_epoch_ns=late)
    assert b.evaluate_completion(check_epoch_ns=late)["full_complete"] is False
    # a fresh price update for both refreshes the source evidence
    for sym in ("AAAUSDT", "BBBUSDT"):
        b.ingest_data_message(
            {"topic": f"tickers.{sym}", "type": "delta", "ts": int(late / 1e6), "cs": 2,
             "data": {"symbol": sym, "lastPrice": "11.0"}},
            local_received_epoch_ns=late, local_monotonic_received_ns=late,
            connection_generation=0)
    assert b.evaluate_completion(check_epoch_ns=late + 1_000_000)["full_complete"] is True


# ---------------------------------------------------------------------------
# 5/6/7. Rejected / mismatched ACK
# ---------------------------------------------------------------------------

def test_rejected_ack_fails_closed_conflict():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    assert b.ingest_subscription_ack(ack_msg(success=False), connection_generation=0,
                                     received_epoch_ns=now) == ws.WS_SUBSCRIPTION_ACK_REJECTED
    art = b.build_artifact(finalize_epoch_ns=now + 1_000_000, legacy_position_provenance=AUTH_PROV)
    assert art["overall_status"] == ws.WS_TICKER_EVIDENCE_CONFLICT
    assert art["overall_status"] != ws.WS_TICKER_EVIDENCE_COMPLETE
    assert art["early_completion"]["completion_achieved"] is False


def test_ack_request_id_mismatch_is_conflict():
    u = make_universe()
    b = builder(u, req_id="EXPECTED")
    now = time.time_ns()
    assert b.ingest_subscription_ack(ack_msg(req_id="WRONG"), connection_generation=0,
                                     received_epoch_ns=now) == ws.WS_SUBSCRIPTION_ACK_CONFLICT


def test_ack_connection_generation_mismatch_is_conflict():
    u = make_universe()
    b = builder(u, generation=0)  # request issued in generation 0
    now = time.time_ns()
    assert b.ingest_subscription_ack(ack_msg(), connection_generation=1,
                                     received_epoch_ns=now) == ws.WS_SUBSCRIPTION_ACK_CONFLICT


# ---------------------------------------------------------------------------
# 8. Data messages are not an implicit ACK
# ---------------------------------------------------------------------------

def test_data_messages_are_not_implicit_ack():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    assert b.subscription_acknowledged is False
    assert b.ws_subscription_ack_count == 0
    art = b.build_artifact(finalize_epoch_ns=now + 1_000_000, legacy_position_provenance=AUTH_PROV)
    assert art["overall_status"] != ws.WS_TICKER_EVIDENCE_COMPLETE


# ---------------------------------------------------------------------------
# 9/10. COMPLETE implies ACK + parity + exit 0
# ---------------------------------------------------------------------------

def test_complete_requires_data_plus_ack_and_implies_exit_zero():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    b.ingest_subscription_ack(ack_msg(), connection_generation=0, received_epoch_ns=now + 2)
    art = b.build_artifact(
        finalize_epoch_ns=now + 3_000_000, legacy_position_provenance=AUTH_PROV,
        dependency_status=ws.WS_CLIENT_DEPENDENCY_AVAILABLE, require_complete=True,
        allow_real_network=True,
        completion_meta={"collection_terminated_reason": ws.TERMINATED_COMPLETE_AND_ACKED})
    assert art["overall_status"] == ws.WS_TICKER_EVIDENCE_COMPLETE
    assert art["subscription_ack"]["subscription_acknowledged"] is True
    assert art["message_audit"]["ws_subscription_ack_count"] == 1
    assert art["early_completion"]["completion_achieved"] is True
    assert art["counter_parity_status"] == ws.WS_COUNTER_PARITY_PASS
    assert art["control_plane_parity_status"] == ws.WS_CONTROL_PLANE_PARITY_PASS
    assert art["cli_exit_status"] == ws.EXIT_COMPLETE
    assert art["early_completion"]["collection_terminated_reason"] == \
        ws.TERMINATED_COMPLETE_AND_ACKED


def test_data_completion_block_split_from_full_completion():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    # data complete, but no ACK yet
    art = b.build_artifact(finalize_epoch_ns=now + 1_000_000, legacy_position_provenance=AUTH_PROV)
    assert art["data_completion"]["data_completion_achieved"] is True
    assert art["data_completion"]["data_completion_complete_symbol_count"] == 52
    assert art["early_completion"]["completion_achieved"] is False


# ---------------------------------------------------------------------------
# 11/12/13/14. Preserved FIX2 + safety
# ---------------------------------------------------------------------------

def test_control_plane_parity_pass_when_acked():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    b.ingest_subscription_ack(ack_msg(), connection_generation=0, received_epoch_ns=now)
    art = b.build_artifact(finalize_epoch_ns=now + 1_000_000, legacy_position_provenance=AUTH_PROV)
    assert art["control_plane_parity_status"] == ws.WS_CONTROL_PLANE_PARITY_PASS
    assert (art["subscription_summary"]["subscription_acknowledged"]
            == (art["message_audit"]["ws_subscription_ack_count"] > 0))


def test_no_auth_credentials_and_safety_preserved():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    b.ingest_subscription_ack(ack_msg(), connection_generation=0, received_epoch_ns=now)
    art = b.build_artifact(finalize_epoch_ns=now + 1_000_000, legacy_position_provenance=AUTH_PROV)
    assert art["authenticated"] is False
    ws.assert_no_credentials(art, secret_values=["irrelevant"])
    for k in art["message_audit"]:
        assert k.startswith("ws_")
    assert art["execution_batch_authorized"] is False
    assert art["execution_ready"] is False
    assert art["sender_reachable"] is False
    assert art["order_post_count"] == 0 and art["live_order_post_count"] == 0
    assert art["freshness_summary"]["execution_grade_freshness_complete"] is False
    assert art["execution_grade_freshness_complete"] is False


def test_ack_message_with_credentials_rejected():
    u = make_universe()
    b = builder(u)
    with pytest.raises(ws.WsEndpointError):
        b.ingest_subscription_ack({"op": "subscribe", "success": True, "api_key": "x"},
                                  connection_generation=0, received_epoch_ns=1)


def test_fix2_immutable_source_provenance_preserved():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = builder(u)
    now = time.time_ns()
    ts0 = int(now / 1e6)
    b.ingest_data_message(snap("AAAUSDT", ts=ts0, cs=1, last_price="100.0"),
                          local_received_epoch_ns=now,
                          local_monotonic_received_ns=now, connection_generation=0)
    b.ingest_data_message(
        {"topic": "tickers.AAAUSDT", "type": "delta", "ts": ts0 + 5000, "cs": 2,
         "data": {"symbol": "AAAUSDT", "turnover24h": "9"}},
        local_received_epoch_ns=now + 1, local_monotonic_received_ns=now + 1,
        connection_generation=0)
    b.ingest_subscription_ack(ack_msg(), connection_generation=0, received_epoch_ns=now)
    art = b.build_artifact(finalize_epoch_ns=now + 2_000_000, legacy_position_provenance=AUTH_PROV)
    row = art["per_symbol_evidence"][0]
    assert row["selected_price_source_ts_ms"] == ts0
    assert row["selected_price"] == "100.0"
    assert row["last_accepted_ts"] == ts0 + 5000
    assert row["selected_price_updated_in_message"] is True
