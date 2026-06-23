"""TASK-014CF_FIX2 -- early-complete finalization + canonical evidence parity.

Fully offline. Proves: collection can finalize as soon as every required symbol
is simultaneously fresh-and-complete in one generation (no waiting for the
deadline); the selected-price source-message provenance is immutable and is not
overwritten by a later delta without lastPrice; coverage_summary and
message_audit counters are derived from one canonical source and are identical
(ws_complete_symbol_count is no longer a stale zero); a counter-parity failure
blocks COMPLETE; the canonical execution_grade_freshness_complete lives under
freshness_summary, stays False at 52/52, and the top-level alias mirrors it.
"""
from __future__ import annotations

import time

import pytest

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_pilot_readiness as rd

STRATEGY_50 = sorted({f"SYM{i:02d}USDT" for i in range(50)})
LEGACY_2 = ["EDUUSDT", "POLYXUSDT"]
OFFSET = "0.0068"


def make_universe(strategy=None, legacy=None):
    return ws.derive_required_symbol_universe(
        strategy_target_symbols=strategy if strategy is not None else STRATEGY_50,
        observed_legacy_symbols=legacy if legacy is not None else LEGACY_2,
        protected_symbol_allowlist=rd.PROTECTED_SYMBOLS,
        strategy_source_reference="fix2-fixture", legacy_source_reference="fix2-fixture")


def builder(universe=None, *, stale_ms=10_000):
    return ws.PublicWsTickerEvidenceBuilder(
        universe=universe or make_universe(), clock_offset_seconds=OFFSET,
        clock_offset_status="CLOCK_OFFSET_AVAILABLE",
        clock_offset_provenance_status=ws.CLOCK_OFFSET_PROVENANCE_AUTHORITATIVE,
        stale_threshold_ms=stale_ms)


def snap(symbol, *, ts, cs, last_price="100.5"):
    return {"topic": f"tickers.{symbol}", "type": "snapshot", "ts": ts, "cs": cs,
            "data": {"symbol": symbol, "lastPrice": last_price}}


def delta(symbol, *, ts, cs, last_price=None, other=None):
    data = {"symbol": symbol}
    if last_price is not None:
        data["lastPrice"] = last_price
    if other:
        data.update(other)
    return {"topic": f"tickers.{symbol}", "type": "delta", "ts": ts, "cs": cs, "data": data}


def feed_fresh_all(b, universe, *, now_ns):
    """Feed one fresh snapshot per symbol with ts ~ now (so age is tiny)."""
    base_ts = int(now_ns / 1e6)
    for i, sym in enumerate(universe["symbols"]):
        b.ingest_data_message(snap(sym, ts=base_ts - i, cs=1000 + i),
                              local_received_epoch_ns=now_ns,
                              local_monotonic_received_ns=now_ns, connection_generation=0)


# ---------------------------------------------------------------------------
# A. Early successful finalization
# ---------------------------------------------------------------------------

def test_52_fresh_snapshots_trigger_early_completion():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    ev = b.evaluate_completion(check_epoch_ns=now + 1_000_000)
    assert ev["all_required_complete"] is True
    assert ev["complete_symbol_count"] == 52
    assert ev["connection_generation"] == 0


def test_completion_triggers_exactly_at_full_coverage_not_before():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    base_ts = int(now / 1e6)
    syms = u["symbols"]
    for i, sym in enumerate(syms[:-1]):  # 51/52
        b.ingest_data_message(snap(sym, ts=base_ts - i, cs=1000 + i),
                              local_received_epoch_ns=now,
                              local_monotonic_received_ns=now, connection_generation=0)
    assert b.evaluate_completion(check_epoch_ns=now + 1_000_000)["all_required_complete"] is False
    # the 52nd symbol flips it to complete (early, before any deadline)
    b.ingest_data_message(snap(syms[-1], ts=base_ts, cs=2000),
                          local_received_epoch_ns=now,
                          local_monotonic_received_ns=now, connection_generation=0)
    assert b.evaluate_completion(check_epoch_ns=now + 1_000_000)["all_required_complete"] is True


def test_already_stale_snapshot_does_not_trigger_early_completion():
    u = make_universe()
    b = builder(u, stale_ms=5_000)
    now = time.time_ns()
    # 51 fresh (ts ~ now); one with a 100s-old source ts -> unambiguously stale.
    base_ts = int(now / 1e6)
    for i, sym in enumerate(u["symbols"][:-1]):
        b.ingest_data_message(snap(sym, ts=base_ts - i, cs=1000 + i),
                              local_received_epoch_ns=now,
                              local_monotonic_received_ns=now, connection_generation=0)
    stale_sym = u["symbols"][-1]
    b.ingest_data_message(snap(stale_sym, ts=base_ts - 100_000, cs=999),  # 100s old ts
                          local_received_epoch_ns=now,
                          local_monotonic_received_ns=now, connection_generation=0)
    ev = b.evaluate_completion(check_epoch_ns=now + 1_000_000)
    assert ev["all_required_complete"] is False
    assert ev["complete_symbol_count"] == 51


def test_mixed_generations_never_trigger_early_completion():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    base_ts = int(now / 1e6)
    syms = u["symbols"]
    for i, sym in enumerate(syms[:-1]):
        b.ingest_data_message(snap(sym, ts=base_ts - i, cs=1000 + i),
                              local_received_epoch_ns=now,
                              local_monotonic_received_ns=now, connection_generation=0)
    # last symbol's snapshot arrives under a DIFFERENT generation
    b.ingest_data_message(snap(syms[-1], ts=base_ts, cs=2000),
                          local_received_epoch_ns=now,
                          local_monotonic_received_ns=now, connection_generation=1)
    ev = b.evaluate_completion(check_epoch_ns=now + 1_000_000)
    assert ev["all_required_complete"] is False
    assert ev["single_generation"] is False


def test_ages_calculated_at_early_completion_time():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = builder(u)
    now = time.time_ns()
    ts_ms = int(now / 1e6)
    b.ingest_data_message(snap("AAAUSDT", ts=ts_ms, cs=1),
                          local_received_epoch_ns=now,
                          local_monotonic_received_ns=now, connection_generation=0)
    # finalize at completion time (now + 2ms) -> age ~ offset + 2ms, small & fresh
    art = b.build_artifact(finalize_epoch_ns=now + 2_000_000, subscription_acknowledged=True)
    row = art["per_symbol_evidence"][0]
    assert row["evidence_status"] == ws.WS_PRICE_TIMESTAMP_EVIDENCE_COMPLETE
    assert row["evidence_age_at_finalize_ms"] < 100  # not aged by waiting for a deadline


# ---------------------------------------------------------------------------
# B. Immutable selected-price source-message provenance
# ---------------------------------------------------------------------------

def test_later_delta_without_price_does_not_overwrite_source_provenance():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = builder(u)
    now = time.time_ns()
    ts0 = int(now / 1e6)
    b.ingest_data_message(snap("AAAUSDT", ts=ts0, cs=1, last_price="100.0"),
                          local_received_epoch_ns=now,
                          local_monotonic_received_ns=now, connection_generation=0)
    # a much later delta WITHOUT lastPrice (ts/cs advance)
    b.ingest_data_message(delta("AAAUSDT", ts=ts0 + 5000, cs=2, other={"turnover24h": "9"}),
                          local_received_epoch_ns=now + 5_000_000_000,
                          local_monotonic_received_ns=now + 5_000_000_000,
                          connection_generation=0)
    art = b.build_artifact(finalize_epoch_ns=now + 5_001_000_000, subscription_acknowledged=True)
    row = art["per_symbol_evidence"][0]
    # immutable price-source provenance unchanged
    assert row["selected_price_source_ts_ms"] == ts0
    assert row["selected_price_source_cs"] == 1
    assert row["selected_price_source_local_received_epoch_ns"] == now
    assert row["selected_price"] == "100.0"
    assert row["selected_price_source_message_included_field"] is True
    # latest PROTOCOL ts advanced independently
    assert row["last_accepted_ts"] == ts0 + 5000
    assert row["last_accepted_ts"] != row["selected_price_source_ts_ms"]
    # transient flag reflects the last (no-price) message
    assert row["last_processed_message_updated_selected_price"] is False


def test_complete_records_have_source_included_field_true():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    art = b.build_artifact(finalize_epoch_ns=now + 1_000_000, subscription_acknowledged=True)
    completes = [r for r in art["per_symbol_evidence"]
                 if r["evidence_status"] == ws.WS_PRICE_TIMESTAMP_EVIDENCE_COMPLETE]
    assert len(completes) == 52
    for r in completes:
        assert r["selected_price_source_message_included_field"] is True
        assert r["selected_price_updated_in_message"] is True
        assert r["selected_price_source_message_fingerprint"].startswith("sha256:")


# ---------------------------------------------------------------------------
# C. Canonical counter parity
# ---------------------------------------------------------------------------

def test_coverage_and_audit_counters_match_exactly():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    art = b.build_artifact(finalize_epoch_ns=now + 1_000_000, subscription_acknowledged=True)
    cov, aud = art["coverage_summary"], art["message_audit"]
    assert cov["complete_symbol_count"] == aud["ws_complete_symbol_count"] == 52
    assert cov["covered_symbol_count"] == aud["ws_covered_symbol_count"] == 52
    assert cov["requested_symbol_count"] == aud["ws_required_symbol_count"] == 52
    assert art["counter_parity_status"] == ws.WS_COUNTER_PARITY_PASS
    assert art["overall_status"] == ws.WS_TICKER_EVIDENCE_COMPLETE


def test_ws_complete_symbol_count_is_not_stale_zero():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    art = b.build_artifact(finalize_epoch_ns=now + 1_000_000, subscription_acknowledged=True)
    assert art["message_audit"]["ws_complete_symbol_count"] == 52  # was 0 before FIX2


def test_counter_parity_failure_blocks_complete():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    # completion_meta claims achieved but with a wrong complete count -> parity FAIL
    bad_meta = {"completion_achieved": True, "completion_complete_symbol_count": 51}
    art = b.build_artifact(finalize_epoch_ns=now + 1_000_000, subscription_acknowledged=True,
                           completion_meta=bad_meta)
    assert art["counter_parity_status"] == ws.WS_COUNTER_PARITY_FAIL
    assert art["overall_status"] != ws.WS_TICKER_EVIDENCE_COMPLETE


# ---------------------------------------------------------------------------
# D. Freshness canonical field + alias
# ---------------------------------------------------------------------------

def test_execution_grade_freshness_stays_false_at_52_52():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    art = b.build_artifact(finalize_epoch_ns=now + 1_000_000, subscription_acknowledged=True)
    assert art["overall_status"] == ws.WS_TICKER_EVIDENCE_COMPLETE
    # canonical nested value stays False even at full coverage
    assert art["freshness_summary"]["execution_grade_freshness_complete"] is False
    # top-level alias EXACTLY mirrors the nested canonical value
    assert art["execution_grade_freshness_complete"] == \
        art["freshness_summary"]["execution_grade_freshness_complete"]


# ---------------------------------------------------------------------------
# E/F. Finalization age + timeout PARTIAL
# ---------------------------------------------------------------------------

def test_age_uses_source_ts_and_offset_not_latest_message():
    u = make_universe(strategy=["AAAUSDT"], legacy=[])
    b = builder(u)
    now = time.time_ns()
    ts_ms = int(now / 1e6)
    b.ingest_data_message(snap("AAAUSDT", ts=ts_ms, cs=1),
                          local_received_epoch_ns=now,
                          local_monotonic_received_ns=now, connection_generation=0)
    art = b.build_artifact(finalize_epoch_ns=now + 3_000_000, subscription_acknowledged=True)
    row = art["per_symbol_evidence"][0]
    # age = (finalize_s + offset) - source_ts_s = ~ 3ms + 6.8ms
    assert row["evidence_age_at_finalize_ms"] == pytest.approx(3.0 + 6.8, abs=1.0)


def test_timeout_partial_is_written_and_exits_five():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    # only 51/52 fresh -> never simultaneously complete -> PARTIAL at deadline
    for i, sym in enumerate(u["symbols"][:-1]):
        b.ingest_data_message(snap(sym, ts=int(now / 1e6) - i, cs=1000 + i),
                              local_received_epoch_ns=now,
                              local_monotonic_received_ns=now, connection_generation=0)
    art = b.build_artifact(
        finalize_epoch_ns=now + 1_000_000, subscription_acknowledged=True,
        clock_offset_provenance={"clock_offset_provenance_status":
                                 ws.CLOCK_OFFSET_PROVENANCE_AUTHORITATIVE},
        legacy_position_provenance={"symbol_universe_source_status":
                                    ws.SYMBOL_UNIVERSE_SOURCE_AUTHORITATIVE},
        dependency_status=ws.WS_CLIENT_DEPENDENCY_AVAILABLE, require_complete=True,
        allow_real_network=True)
    assert art["overall_status"] == ws.WS_TICKER_EVIDENCE_PARTIAL
    assert art["cli_exit_status"] == ws.EXIT_PARTIAL
    # stale/missing symbol remains explicit (not silently discarded)
    statuses = {r["symbol"]: r["evidence_status"] for r in art["per_symbol_evidence"]}
    assert statuses[u["symbols"][-1]] == ws.WS_SNAPSHOT_MISSING


# ---------------------------------------------------------------------------
# G. Safety invariants preserved
# ---------------------------------------------------------------------------

def test_no_auth_credentials_and_rest_separation_preserved():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    art = b.build_artifact(finalize_epoch_ns=now + 1_000_000, subscription_acknowledged=True)
    assert art["authenticated"] is False
    ws.assert_no_credentials(art, secret_values=["irrelevant"])
    for k in art["message_audit"]:
        assert k.startswith("ws_")
    assert "total_public_get_count" not in art["message_audit"]
    assert art["execution_batch_authorized"] is False
    assert art["execution_ready"] is False
    assert art["sender_reachable"] is False
    assert art["order_post_count"] == 0 and art["live_order_post_count"] == 0
    assert ws.PRICE_FRESHNESS_EVIDENCE_PARTIAL in art["blockers"]


def test_early_completion_metadata_block_present():
    u = make_universe()
    b = builder(u)
    now = time.time_ns()
    feed_fresh_all(b, u, now_ns=now)
    meta = {"early_completion_enabled": True, "completion_achieved": True,
            "completion_achieved_at_epoch_ns": now + 1_000_000,
            "completion_achieved_at_utc": "2026-06-22T00:00:00.000000Z",
            "completion_connection_generation": 0,
            "completion_required_symbol_count": 52, "completion_complete_symbol_count": 52,
            "completion_trigger_message_count": 3738,
            "collection_terminated_reason": "ALL_REQUIRED_SYMBOLS_COMPLETE"}
    art = b.build_artifact(finalize_epoch_ns=now + 1_000_000, subscription_acknowledged=True,
                           completion_meta=meta)
    ec = art["early_completion"]
    assert ec["completion_achieved"] is True
    # FIX3: the canonical successful reason now includes subscription ACK.
    assert ec["collection_terminated_reason"] == \
        "ALL_REQUIRED_SYMBOLS_COMPLETE_AND_SUBSCRIPTION_ACKNOWLEDGED"
    assert ec["completion_complete_symbol_count"] == 52
    assert art["counter_parity_status"] == ws.WS_COUNTER_PARITY_PASS
    assert art["overall_status"] == ws.WS_TICKER_EVIDENCE_COMPLETE
