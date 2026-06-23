"""TASK-014CF_FIX1 -- bind public WebSocket evidence to authoritative sources.

Fully offline. Proves: clock-offset provenance is bound to a fresh, compatible,
AUTHORITATIVE CE/FIX1 artifact (an arbitrary numeric offset can never qualify);
protected-legacy symbols are derived from the CE current-position evidence (manual
production omission is impossible, new protected positions are auto-included,
malformed/conflicting evidence fails closed); the --require-complete exit gate
returns the documented non-zero codes for PARTIAL / UNAVAILABLE / CONFLICT / ack
failure / credential failure / dependency failure; the artifact is still written
on a safe non-zero outcome; and the task never promotes execution readiness.
"""
from __future__ import annotations

import importlib
import json
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_pilot_forward_source as fs
from src import demo_strategy_pilot_readiness as rd

col = importlib.import_module("scripts.collect_public_ws_ticker_evidence")

STRATEGY_50 = sorted({f"SYM{i:02d}USDT" for i in range(50)})


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def make_ce_artifact(*, date="2026-06-22", policy=ws.ACTIVE_STRATEGY_NATIVE_V1_POLICY,
                     strategy=ws.EXPECTED_STRATEGY_NAME,
                     offset="0.006840791", offset_status="CLOCK_OFFSET_AVAILABLE",
                     clock_status="EXCHANGE_CLOCK_BRACKET_AVAILABLE",
                     bracket_ordered=True, per_symbol_quote=False,
                     server_fp="sha256:deadbeef", source_endpoint="/v5/market/time",
                     account_status="ACCOUNT_MODE_EVIDENCE_AUTHORITATIVE",
                     observed_age_seconds=30,
                     legacy_positions=None, include_clock=True):
    observed_at = _iso(datetime.now(timezone.utc) - timedelta(seconds=observed_age_seconds))
    if legacy_positions is None:
        legacy_positions = [{"symbol": "EDUUSDT", "side": "long", "qty": "1"},
                            {"symbol": "POLYXUSDT", "side": "short", "qty": "2"}]
    clock = {
        "source_endpoint": source_endpoint,
        "exchange_clock_evidence_status": clock_status,
        "clock_offset_evidence_status": offset_status,
        "estimated_local_vs_exchange_clock_offset_seconds": offset,
        "server_time_evidence_fingerprint": server_fp,
        "server_time_bracket_ordered": bracket_ordered,
        "per_symbol_exchange_quote_timestamp_available": per_symbol_quote,
        "after_local_response_received_at_utc": observed_at,
    }
    review = {
        "active_strategy": strategy,
        "account_mode_evidence": {
            "account_mode_evidence_status": account_status,
            "margin_mode": "REGULAR_MARGIN",
            "response_received_at_utc": observed_at,
        },
        "legacy_protected_positions": legacy_positions,
    }
    if include_clock:
        review["exchange_clock_evidence"] = clock
    return {"active_policy": policy, "date": date, "strategy_native_review": review}


def ce_bytes(artifact) -> bytes:
    return json.dumps(artifact).encode("utf-8")


# ---------------------------------------------------------------------------
# 1. Clock-offset provenance
# ---------------------------------------------------------------------------

def test_authoritative_recent_ce_evidence_permits_offset():
    art = make_ce_artifact()
    prov = ws.extract_clock_offset_provenance(
        art, artifact_path="/tmp/ce.json", artifact_bytes=ce_bytes(art),
        requested_strategy_date="2026-06-22", max_age_seconds=900, now_epoch=__import__("time").time())
    assert prov["clock_offset_provenance_status"] == ws.CLOCK_OFFSET_PROVENANCE_AUTHORITATIVE
    assert prov["estimated_local_vs_exchange_clock_offset_seconds"] == "0.006840791"
    assert prov["clock_offset_evidence_status"] == ws.CLOCK_OFFSET_AVAILABLE
    assert prov["clock_offset_source_artifact_sha256"].startswith("sha256:")


def test_arbitrary_numeric_offset_cannot_create_authoritative_provenance():
    # The builder gate: a raw offset + "CLOCK_OFFSET_AVAILABLE" with non-authoritative
    # provenance can never yield a COMPLETE symbol.
    u = ws.derive_required_symbol_universe(
        strategy_target_symbols=["AAAUSDT"], observed_legacy_symbols=[],
        protected_symbol_allowlist=rd.PROTECTED_SYMBOLS,
        strategy_source_reference="x", legacy_source_reference="y")
    import time as _t
    b = ws.PublicWsTickerEvidenceBuilder(
        universe=u, clock_offset_seconds="0.5", clock_offset_status="CLOCK_OFFSET_AVAILABLE",
        clock_offset_provenance_status=ws.CLOCK_OFFSET_PROVENANCE_MISSING)
    now = _t.time_ns()
    b.ingest_data_message(
        {"topic": "tickers.AAAUSDT", "type": "snapshot", "ts": int(now / 1e6), "cs": 1,
         "data": {"symbol": "AAAUSDT", "lastPrice": "1.0"}},
        local_received_epoch_ns=now, local_monotonic_received_ns=now, connection_generation=0)
    art = b.build_artifact(finalize_epoch_ns=now + 1_000_000, subscription_acknowledged=True)
    row = art["per_symbol_evidence"][0]
    assert row["estimated_transport_delay_ms"] is None
    assert row["evidence_status"] != ws.WS_PRICE_TIMESTAMP_EVIDENCE_COMPLETE


def test_stale_ce_clock_evidence_blocks_complete():
    art = make_ce_artifact(observed_age_seconds=4000)  # > 900s default
    prov = ws.extract_clock_offset_provenance(
        art, artifact_path="/tmp/ce.json", artifact_bytes=ce_bytes(art),
        requested_strategy_date="2026-06-22", max_age_seconds=900,
        now_epoch=__import__("time").time())
    assert prov["clock_offset_provenance_status"] == ws.CLOCK_OFFSET_PROVENANCE_STALE
    assert prov["estimated_local_vs_exchange_clock_offset_seconds"] is None


def test_missing_clock_evidence_blocks_complete():
    art = make_ce_artifact(include_clock=False)
    prov = ws.extract_clock_offset_provenance(
        art, artifact_path="/tmp/ce.json", artifact_bytes=ce_bytes(art),
        requested_strategy_date="2026-06-22", max_age_seconds=900,
        now_epoch=__import__("time").time())
    assert prov["clock_offset_provenance_status"] == ws.CLOCK_OFFSET_PROVENANCE_MISSING


@pytest.mark.parametrize("kw", [
    {"date": "2026-06-01"},
    {"policy": "SOME_OTHER_POLICY"},
    {"strategy": "shadow_variant"},
    {"source_endpoint": "/v5/market/tickers"},
    {"per_symbol_quote": True},
])
def test_incompatible_ce_evidence_blocks_complete(kw):
    art = make_ce_artifact(**kw)
    prov = ws.extract_clock_offset_provenance(
        art, artifact_path="/tmp/ce.json", artifact_bytes=ce_bytes(art),
        requested_strategy_date="2026-06-22", max_age_seconds=900,
        now_epoch=__import__("time").time())
    assert prov["clock_offset_provenance_status"] in (
        ws.CLOCK_OFFSET_PROVENANCE_INCOMPATIBLE, ws.CLOCK_OFFSET_PROVENANCE_CONFLICT)
    assert prov["estimated_local_vs_exchange_clock_offset_seconds"] is None


def test_bracket_not_ordered_is_conflict():
    art = make_ce_artifact(bracket_ordered=False)
    prov = ws.extract_clock_offset_provenance(
        art, artifact_path="/tmp/ce.json", artifact_bytes=ce_bytes(art),
        requested_strategy_date="2026-06-22", max_age_seconds=900,
        now_epoch=__import__("time").time())
    assert prov["clock_offset_provenance_status"] == ws.CLOCK_OFFSET_PROVENANCE_CONFLICT


def test_source_artifact_sha256_deterministic():
    art = make_ce_artifact()
    raw = ce_bytes(art)
    a = ws.extract_clock_offset_provenance(
        art, artifact_path="/tmp/ce.json", artifact_bytes=raw,
        requested_strategy_date="2026-06-22", now_epoch=1.0)
    b = ws.extract_clock_offset_provenance(
        art, artifact_path="/tmp/ce.json", artifact_bytes=raw,
        requested_strategy_date="2026-06-22", now_epoch=1.0)
    assert a["clock_offset_source_artifact_sha256"] == b["clock_offset_source_artifact_sha256"]


# ---------------------------------------------------------------------------
# 2. Authoritative protected-legacy universe
# ---------------------------------------------------------------------------

def test_legacy_symbols_derived_from_ce_current_positions():
    art = make_ce_artifact()
    prov = ws.extract_legacy_position_provenance(
        art, protected_symbol_allowlist=rd.PROTECTED_SYMBOLS,
        requested_strategy_date="2026-06-22", artifact_bytes=ce_bytes(art))
    assert prov["legacy_protected_symbols"] == ["EDUUSDT", "POLYXUSDT"]
    assert prov["current_protected_position_count"] == 2
    assert prov["symbol_universe_source_status"] == ws.SYMBOL_UNIVERSE_SOURCE_AUTHORITATIVE


def test_newly_observed_protected_position_auto_included():
    art = make_ce_artifact(legacy_positions=[
        {"symbol": "EDUUSDT", "side": "long", "qty": "1"},
        {"symbol": "POLYXUSDT", "side": "short", "qty": "2"},
        {"symbol": "TIAUSDT", "side": "long", "qty": "3"}])  # newly observed protected
    prov = ws.extract_legacy_position_provenance(
        art, protected_symbol_allowlist=rd.PROTECTED_SYMBOLS,
        requested_strategy_date="2026-06-22", artifact_bytes=ce_bytes(art))
    assert prov["legacy_protected_symbols"] == ["EDUUSDT", "POLYXUSDT", "TIAUSDT"]
    assert prov["symbol_universe_source_status"] == ws.SYMBOL_UNIVERSE_SOURCE_AUTHORITATIVE


def test_conflicting_current_position_fails_closed():
    art = make_ce_artifact(legacy_positions=[
        {"symbol": "EDUUSDT", "side": "long", "qty": "1"},
        {"symbol": "EDUUSDT", "side": "short", "qty": "2"}])  # conflicting side
    prov = ws.extract_legacy_position_provenance(
        art, protected_symbol_allowlist=rd.PROTECTED_SYMBOLS,
        requested_strategy_date="2026-06-22", artifact_bytes=ce_bytes(art))
    assert prov["symbol_universe_source_status"] == ws.SYMBOL_UNIVERSE_SOURCE_CONFLICT


def test_non_protected_current_position_fails_closed():
    art = make_ce_artifact(legacy_positions=[
        {"symbol": "DOGEUSDT", "side": "long", "qty": "1"}])  # not a protected symbol
    prov = ws.extract_legacy_position_provenance(
        art, protected_symbol_allowlist=rd.PROTECTED_SYMBOLS,
        requested_strategy_date="2026-06-22", artifact_bytes=ce_bytes(art))
    assert prov["symbol_universe_source_status"] == ws.SYMBOL_UNIVERSE_SOURCE_CONFLICT


def test_ce_targets_and_forward_produce_complete_universe(monkeypatch):
    class FakeResult:
        run_key = "prev3y_crypto"
        strategy_name = ws.EXPECTED_STRATEGY_NAME
        source_fingerprint = "sha256:fake"
        normalized_signals = tuple({"symbol": s, "side": "long"} for s in STRATEGY_50)
    monkeypatch.setattr(fs, "load_primary_forward_strategy_result", lambda **k: FakeResult())
    universe, _ref = col.build_universe(
        run_date="2026-06-22", repo_root=col.ROOT, forward_source_root=None,
        legacy_symbols=["EDUUSDT", "POLYXUSDT"],
        legacy_source_reference="ce")
    assert universe["unique_symbol_count"] == 52
    assert universe["legacy_symbol_count"] == 2


# ---------------------------------------------------------------------------
# 3. Completion-gate exit-code matrix (pure)
# ---------------------------------------------------------------------------

def _gate(**over):
    base = dict(
        overall_status=ws.WS_TICKER_EVIDENCE_COMPLETE, required_count=52, covered_count=52,
        complete_count=52, unique_count=52, requested_count=52, subscription_acknowledged=True,
        clock_offset_provenance_status=ws.CLOCK_OFFSET_PROVENANCE_AUTHORITATIVE,
        legacy_source_status=ws.SYMBOL_UNIVERSE_SOURCE_AUTHORITATIVE,
        dependency_status=ws.WS_CLIENT_DEPENDENCY_AVAILABLE, require_complete=True,
        allow_real_network=True)
    base.update(over)
    return ws.compute_completion_gate(**base)["cli_exit_status"]


def test_require_complete_zero_only_for_exact_complete():
    assert _gate() == ws.EXIT_COMPLETE
    assert _gate(complete_count=51) != ws.EXIT_COMPLETE  # falls through to partial branch


def test_partial_returns_nonzero():
    assert _gate(overall_status=ws.WS_TICKER_EVIDENCE_PARTIAL, complete_count=51) == ws.EXIT_PARTIAL


def test_unavailable_returns_nonzero():
    assert _gate(overall_status=ws.WS_TICKER_EVIDENCE_UNAVAILABLE, covered_count=0,
                 complete_count=0, subscription_acknowledged=True) == ws.EXIT_WS_UNAVAILABLE


def test_conflict_returns_nonzero():
    assert _gate(overall_status=ws.WS_TICKER_EVIDENCE_CONFLICT) == ws.EXIT_CONFLICT


def test_subscription_ack_failure_returns_nonzero():
    assert _gate(subscription_acknowledged=False) == ws.EXIT_WS_UNAVAILABLE


def test_clock_provenance_failure_returns_nonzero():
    assert _gate(clock_offset_provenance_status=ws.CLOCK_OFFSET_PROVENANCE_STALE) == \
        ws.EXIT_SOURCE_EVIDENCE_FAILURE


def test_dependency_failure_returns_nonzero():
    assert _gate(dependency_status=ws.WS_CLIENT_DEPENDENCY_MISSING) == ws.EXIT_WS_UNAVAILABLE


def test_required_count_mismatch_returns_nonzero():
    assert _gate(unique_count=51) == ws.EXIT_SOURCE_EVIDENCE_FAILURE


def test_no_require_complete_is_zero():
    assert _gate(require_complete=False,
                 overall_status=ws.WS_TICKER_EVIDENCE_UNAVAILABLE) == ws.EXIT_COMPLETE


# ---------------------------------------------------------------------------
# 4. Dependency readiness
# ---------------------------------------------------------------------------

def test_dependency_missing_fails_closed():
    def bad():
        raise ImportError("no websocket")
    assert ws.check_ws_client_dependency(importer=bad)["ws_client_dependency_status"] == \
        ws.WS_CLIENT_DEPENDENCY_MISSING


def test_dependency_incompatible_fails_closed():
    assert ws.check_ws_client_dependency(
        importer=lambda: ("websocket-client", "0.59.0"))["ws_client_dependency_status"] == \
        ws.WS_CLIENT_DEPENDENCY_INCOMPATIBLE


def test_dependency_available():
    assert ws.check_ws_client_dependency(
        importer=lambda: ("websocket-client", "1.9.0"))["ws_client_dependency_status"] == \
        ws.WS_CLIENT_DEPENDENCY_AVAILABLE


# ---------------------------------------------------------------------------
# 5. CLI integration (offline)
# ---------------------------------------------------------------------------

@pytest.fixture
def patched_forward(monkeypatch):
    class FakeResult:
        run_key = "prev3y_crypto"
        strategy_name = ws.EXPECTED_STRATEGY_NAME
        source_fingerprint = "sha256:fake"
        normalized_signals = tuple({"symbol": s, "side": "long"} for s in STRATEGY_50)
    monkeypatch.setattr(fs, "load_primary_forward_strategy_result", lambda **k: FakeResult())


def _write_ce(tmp_path, artifact) -> str:
    p = tmp_path / "ce_evidence.json"
    p.write_text(json.dumps(artifact), encoding="utf-8")
    return str(p)


def test_cli_requires_ce_evidence_in_production(patched_forward, capsys):
    rc = col.main(["--strategy-date", "2026-06-22"])
    assert rc == ws.EXIT_INVALID_CONFIG


def test_cli_unsafe_legacy_rejected_outside_test_context(patched_forward, monkeypatch):
    monkeypatch.setattr(col, "_in_test_or_temp_context", lambda out: False)
    rc = col.main(["--strategy-date", "2026-06-22",
                   "--unsafe-test-legacy-symbol", "EDUUSDT",
                   "--unsafe-allow-test-overrides"])
    assert rc == ws.EXIT_INVALID_CONFIG


def test_cli_unavailable_returns_nonzero_under_require_complete(patched_forward, tmp_path):
    art = make_ce_artifact()
    ce_path = _write_ce(tmp_path, art)
    out = str(tmp_path / "ws_art.json")
    rc = col.main(["--strategy-date", "2026-06-22", "--ce-evidence-json", ce_path,
                   "--require-complete", "--out", out])
    assert rc == ws.EXIT_WS_UNAVAILABLE  # offline -> covered 0 -> unavailable
    # artifact still written for the safe non-zero outcome
    assert os.path.exists(out)
    saved = json.loads(pathlib.Path(out).read_text(encoding="utf-8"))
    assert saved["cli_exit_status"] == ws.EXIT_WS_UNAVAILABLE
    assert saved["overall_status"] == ws.WS_TICKER_EVIDENCE_UNAVAILABLE


def test_cli_offline_without_require_complete_is_zero(patched_forward, tmp_path):
    art = make_ce_artifact()
    ce_path = _write_ce(tmp_path, art)
    rc = col.main(["--strategy-date", "2026-06-22", "--ce-evidence-json", ce_path])
    assert rc == ws.EXIT_COMPLETE  # exploratory run, gate not enforced


def test_cli_credential_leak_returns_seven(patched_forward, tmp_path, monkeypatch):
    art = make_ce_artifact()
    ce_path = _write_ce(tmp_path, art)
    # Force a "secret" whose value appears in the artifact (planner_price_field).
    monkeypatch.setenv("BYBIT_API_KEY", "lastPrice")
    rc = col.main(["--strategy-date", "2026-06-22", "--ce-evidence-json", ce_path,
                   "--verify-no-credential-leak"])
    assert rc == ws.EXIT_CREDENTIAL_SAFETY


def test_cli_dependency_missing_returns_nonzero(patched_forward, tmp_path, monkeypatch):
    art = make_ce_artifact()
    ce_path = _write_ce(tmp_path, art)
    monkeypatch.setattr(ws, "check_ws_client_dependency", lambda **k: {
        "ws_client_dependency_status": ws.WS_CLIENT_DEPENDENCY_MISSING,
        "ws_client_distribution": "websocket-client", "ws_client_version": None,
        "ws_client_dependency_reason": "forced"})
    rc = col.main(["--strategy-date", "2026-06-22", "--ce-evidence-json", ce_path,
                   "--require-complete"])
    assert rc == ws.EXIT_WS_UNAVAILABLE


def test_cli_incompatible_ce_blocks_and_records_provenance(patched_forward, tmp_path):
    art = make_ce_artifact(date="2026-06-01")  # incompatible date
    ce_path = _write_ce(tmp_path, art)
    out = str(tmp_path / "ws_art.json")
    rc = col.main(["--strategy-date", "2026-06-22", "--ce-evidence-json", ce_path,
                   "--require-complete", "--out", out])
    assert rc == ws.EXIT_SOURCE_EVIDENCE_FAILURE
    saved = json.loads(pathlib.Path(out).read_text(encoding="utf-8"))
    assert saved["clock_offset_provenance"]["clock_offset_provenance_status"] == \
        ws.CLOCK_OFFSET_PROVENANCE_INCOMPATIBLE


# ---------------------------------------------------------------------------
# 6. No execution promotion + counter separation (artifact level)
# ---------------------------------------------------------------------------

def test_artifact_blocks_present_and_fingerprinted(patched_forward, tmp_path):
    art = make_ce_artifact()
    ce_path = _write_ce(tmp_path, art)
    out = str(tmp_path / "ws_art.json")
    col.main(["--strategy-date", "2026-06-22", "--ce-evidence-json", ce_path, "--out", out])
    saved = json.loads(pathlib.Path(out).read_text(encoding="utf-8"))
    for block in ("source_evidence", "clock_offset_provenance", "legacy_position_provenance",
                  "completion_gate", "cli_exit_status", "cli_exit_reason"):
        assert block in saved
    # fingerprint covers the new canonical blocks
    import copy
    mutated = copy.deepcopy(saved)
    mutated.pop("artifact_fingerprint")
    mutated["completion_gate"]["cli_exit_reason"] = "tampered"
    assert ws._fingerprint(mutated) != saved["artifact_fingerprint"]
    # never promotes execution readiness
    assert saved["execution_batch_authorized"] is False
    assert saved["execution_ready"] is False
    assert saved["sender_reachable"] is False
    assert saved["order_post_count"] == 0 and saved["live_order_post_count"] == 0
    assert ws.PRICE_FRESHNESS_EVIDENCE_PARTIAL in saved["blockers"]


def test_ws_counters_still_separate_from_rest(patched_forward, tmp_path):
    art = make_ce_artifact()
    ce_path = _write_ce(tmp_path, art)
    out = str(tmp_path / "ws_art.json")
    col.main(["--strategy-date", "2026-06-22", "--ce-evidence-json", ce_path, "--out", out])
    saved = json.loads(pathlib.Path(out).read_text(encoding="utf-8"))
    for k in saved["message_audit"]:
        assert k.startswith("ws_")
    assert "total_public_get_count" not in saved["message_audit"]
