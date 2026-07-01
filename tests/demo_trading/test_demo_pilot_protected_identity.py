"""TASK-014CA(+FIX1/FIX2): pre-Day-1 protected-position identity bootstrap tests.

Evidence validity and bootstrap readiness are DISTINCT: a valid EDU identity keeps its
fingerprint/digest even while inherited non-protected positions block readiness; an empty protected
set is a valid, ready state. Protected != every open position. Identity is COMPOSITE
``(symbol, position_idx)``; fingerprints+digests self-recompute from the single
``canonical_protected_positions`` source. Binding needs a FORMAL allocation artifact and can be
evidence-valid while not execution-ready. Three offline/real CLI modes are mutually exclusive and
no-clobber. Fully offline (no Bybit, no key, no Pilot state).
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os

import pytest

from src import demo_pilot_protected_identity_bootstrap as pib

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cli = _load("pib_cli_test", "scripts/run_demo_pilot_protected_identity_snapshot.py")

PILOT = "BYBIT_DEMO_PILOT_7D_202607_V2"
RETIRED = "BYBIT_DEMO_PILOT_7D_202606_V1"
DAY1 = "2026-07-05"
GEN = "2026-07-05T00:00:00+00:00"
STRATEGY = [f"S{i:02d}USDT" for i in range(50)]


# ------------------------------------------------------------------ fixture builders
def _pos(symbol, side, qty, position_idx, entry_price="100", leverage="2"):
    return {"symbol": symbol, "side": side, "qty": qty, "position_idx": position_idx,
            "entry_price": entry_price, "leverage": leverage}


def _edu(**over):
    row = _pos("EDUUSDT", "Sell", "1234", 2, entry_price="9", leverage="3")
    row.update(over)
    return row


def _page_ev(n):
    return [{"page_number": 1, "endpoint": "/v5/position/list",
             "request_started_at_utc": "2026-07-05T00:00:00Z",
             "response_received_at_utc": "2026-07-05T00:00:01Z", "request_elapsed_ms": 12.3,
             "request_cursor_present": False, "response_next_cursor_present": False,
             "raw_row_count": n, "nonzero_row_count": n}]


def _prov(positions, reason="empty_cursor", pages=1):
    n = len(positions)
    return {"termination_reason": reason, "page_count": pages, "api_position_rows": n,
            "nonzero_position_count": n, "position_page_request_evidence": _page_ev(n)}


def _ctr(ro=1, pub=0, mut=0):
    return {"private_read_only_request_count": ro, "public_read_only_request_count": pub,
            "private_mutating_request_count": mut}


def _components(ctr="default"):
    return {"protected_position_collector": _ctr() if ctr == "default" else ctr}


def _account(**over):
    a = {"account_mode": "demo", "demo_flag": True, "endpoint_family": "bybit_demo",
         "base_url_used": "https://api-demo.bybit.com", "live_endpoint_fallback_detected": False}
    a.update(over)
    return a


def _snapshot(positions=None, provenance=None, components="default", account=None,
              pilot_id=PILOT, day1_date=DAY1):
    positions = [_edu()] if positions is None else positions
    provenance = _prov(positions) if provenance is None else provenance
    return pib.build_pre_day1_protected_snapshot(
        pilot_id=pilot_id, day1_date=day1_date, positions=positions,
        positions_provenance=provenance,
        network_counter_components=_components() if components == "default" else components,
        account_evidence=_account() if account is None else account,
        source_endpoint="/v5/position/list", generated_at=GEN)


def _alloc(pilot_id=PILOT, day1_date=DAY1):
    allocs = [{"symbol": STRATEGY[i], "side": ("Buy" if i < 25 else "Sell"),
               "target_notional_usd": "200"} for i in range(50)]
    fp = pib._crun().allocation_intent_fingerprint(
        allocs, pilot_id=pilot_id, date=day1_date, strategy_capital_base_usd="10000")
    return {"pilot_id": pilot_id, "date": day1_date, "strategy_capital_base_usd": "10000",
            "order_payloads": allocs, "payload_fingerprint": fp,
            "allocation_intent_fingerprint": fp}


def _binding(snapshot=None, allocation=None, pilot_id=PILOT, day1_date=DAY1):
    snapshot = _snapshot() if snapshot is None else snapshot
    allocation = _alloc(pilot_id, day1_date) if allocation is None else allocation
    return pib.build_day1_protected_binding(
        pilot_id=pilot_id, day1_date=day1_date, day1_allocation_artifact=allocation,
        snapshot_artifact=snapshot)


def _continuity(snapshot=None, binding=None, post_positions=None, post_prov=None,
                components="default", strategy_symbols=None, pilot_id=PILOT, day1_date=DAY1):
    snapshot = _snapshot() if snapshot is None else snapshot
    binding = _binding(snapshot) if binding is None else binding
    post_positions = [_edu()] if post_positions is None else post_positions
    post_prov = _prov(post_positions) if post_prov is None else post_prov
    return pib.verify_post_fill_protected_continuity(
        pilot_id=pilot_id, day1_date=day1_date, snapshot_artifact=snapshot,
        binding_artifact=binding, post_fill_positions=post_positions,
        post_fill_provenance=post_prov,
        network_counter_components=_components() if components == "default" else components,
        strategy_symbols=STRATEGY if strategy_symbols is None else strategy_symbols,
        generated_at="2026-07-05T23:00:00+00:00")


def _fifty_plus_edu():
    return [_edu()] + [_pos(STRATEGY[i], "Buy", "1", 0) for i in range(50)]


# ============================================================ (1) 51-position: valid evidence, not ready
def test_1_fifty_one_position_valid_evidence_not_ready():
    art = _snapshot(positions=_fifty_plus_edu())
    assert art["snapshot_evidence_valid"] is True
    assert art["snapshot_evidence_verdict"] == pib.EVIDENCE_VALID
    assert art["bootstrap_ready"] is False
    assert art["bootstrap_verdict"] == pib.BOOTSTRAP_BLOCKED
    assert art["protected_position_count"] == 1 and art["protected_symbol_set"] == ["EDUUSDT"]
    assert art["preexisting_nonprotected_position_count"] == 50
    assert pib._SHA256_RE.match(art["protected_position_snapshot_fingerprint"])
    assert pib._SHA256_RE.match(art["protected_position_snapshot_digest"])
    assert art["evidence_blockers"] == []
    assert pib.OWNERSHIP_READINESS_BLOCKER in art["readiness_blockers"]


# ============================================================ (2) empty account: valid + ready
def test_2_empty_account_valid_and_ready():
    art = _snapshot(positions=[])
    assert art["snapshot_evidence_valid"] is True and art["bootstrap_ready"] is True
    assert art["protected_position_count"] == 0
    assert art["protected_symbol_set"] == [] and art["canonical_protected_positions"] == []
    assert pib._SHA256_RE.match(art["protected_position_snapshot_fingerprint"])
    assert "no_protected_positions_observed" not in art["blockers"]
    # empty canonical list is bound explicitly (fingerprint recomputes, not null/omitted)
    assert pib.canonical_protected_snapshot_fingerprint(art) == art["protected_position_snapshot_fingerprint"]


# ============================================================ (3) incomplete pagination: evidence invalid
def test_3_incomplete_pagination_evidence_invalid():
    art = _snapshot(provenance=_prov([_edu()], reason="max_page_cap_exceeded"))
    assert art["snapshot_evidence_valid"] is False
    assert art["snapshot_evidence_verdict"] == pib.EVIDENCE_INVALID
    assert art["protected_position_snapshot_fingerprint"] == ""
    assert art["protected_position_snapshot_digest"] == ""
    assert any("pagination_incomplete" in b for b in art["evidence_blockers"])


# ============================================================ (4) ownership blocker != evidence corruption
def test_4_ownership_blocker_does_not_pollute_evidence():
    edu_only = _snapshot(positions=[_edu()])
    with_fifty = _snapshot(positions=_fifty_plus_edu())
    # evidence stays valid and the EDU protected identity core is byte-identical
    assert with_fifty["snapshot_evidence_valid"] is True
    assert with_fifty["canonical_protected_positions"] == edu_only["canonical_protected_positions"]
    assert with_fifty["protected_position_snapshot_fingerprint"] != ""
    ok, reasons, _fp, _d, ready = pib._snapshot_is_sealed(with_fifty)
    assert ok is True and ready is False and reasons == []


# ============================================================ (5) binding valid, execution not ready
def test_5_binding_valid_but_not_execution_ready_when_ownership_unresolved():
    snap = _snapshot(positions=_fifty_plus_edu())
    b = _binding(snap)
    assert b["binding_evidence_valid"] is True
    assert b["binding_evidence_verdict"] == pib.BINDING_EVIDENCE_VALID
    assert b["execution_ready"] is False
    assert pib._SHA256_RE.match(b["binding_fingerprint"])
    assert pib.OWNERSHIP_READINESS_BLOCKER in b["readiness_blockers"]


# ============================================================ protected scope / composite identity
def test_only_canonical_protected_enters_identity():
    art = _snapshot(positions=[_edu(), _pos("RANDUSDT", "Buy", "3", 0)])
    assert art["protected_symbol_set"] == ["EDUUSDT"]
    assert [r["symbol"] for r in art["preexisting_nonprotected_positions"]] == ["RANDUSDT"]


def test_hedge_mode_positions_do_not_collide():
    art = _snapshot(positions=[_edu(side="Buy", qty="5", position_idx=1),
                               _edu(side="Sell", qty="7", position_idx=2)])
    assert art["snapshot_evidence_valid"] is True
    rows = {(r["symbol"], r["position_idx"]): r["qty"] for r in art["canonical_protected_positions"]}
    assert rows == {("EDUUSDT", 1): "5", ("EDUUSDT", 2): "7"}
    assert art["position_mode_evidence"]["position_mode"] == "hedge"


def test_duplicate_composite_key_blocks():
    art = _snapshot(positions=[_edu(qty="5", position_idx=2), _edu(qty="7", position_idx=2)])
    assert art["snapshot_evidence_valid"] is False
    assert any("duplicate_position_composite_key" in b for b in art["evidence_blockers"])


# ============================================================ (13) classification count consistency
def test_13_classification_count_consistency():
    art = _snapshot(positions=_fifty_plus_edu())
    assert (art["protected_position_count"] + art["preexisting_nonprotected_position_count"]
            == art["all_observed_nonzero_count"] == 51)
    assert art["pagination_evidence"]["nonzero_position_count"] == 51


# ============================================================ (12) no double-truth position arrays
def test_12_no_duplicate_protected_position_arrays():
    art = _snapshot()
    assert "protected_positions" not in art          # removed; only the canonical source remains
    assert art["protected_positions_summary"] == {"count": 1, "symbols": ["EDUUSDT"]}
    # a tampered summary that diverges from the canonical rows is caught
    tampered = copy.deepcopy(art)
    tampered["protected_positions_summary"]["count"] = 5
    tampered["protected_position_snapshot_digest"] = pib.canonical_protected_snapshot_digest(tampered)
    ok, reasons, _fp, _d, _r = pib._snapshot_is_sealed(tampered)
    assert ok is False and "snapshot_protected_summary_inconsistent" in reasons


# ============================================================ tamper / cross replay
def test_snapshot_qty_tamper_with_outer_digest_still_blocks():
    snap = _snapshot()
    tampered = copy.deepcopy(snap)
    tampered["canonical_protected_positions"][0]["qty"] = "9999"
    tampered["protected_position_snapshot_digest"] = pib.canonical_protected_snapshot_digest(tampered)
    ok, reasons, _fp, _d, _r = pib._snapshot_is_sealed(tampered)
    assert ok is False and "snapshot_fingerprint_mismatch" in reasons


def test_binding_allocation_tamper_with_outer_digest_still_blocks():
    b = _binding()
    tampered = copy.deepcopy(b)
    tampered["allocation_intent_fingerprint"] = "f" * 64
    tampered["binding_digest"] = pib.canonical_binding_digest(tampered)
    ok, reasons = pib._binding_is_sealed(
        tampered, b["protected_position_snapshot_fingerprint"], b["protected_position_snapshot_digest"])
    assert ok is False and "binding_fingerprint_mismatch" in reasons


def test_cross_pilot_binding_blocks():
    b = pib.build_day1_protected_binding(
        pilot_id="BYBIT_DEMO_PILOT_7D_202607_V9", day1_date=DAY1,
        day1_allocation_artifact=_alloc("BYBIT_DEMO_PILOT_7D_202607_V9", DAY1),
        snapshot_artifact=_snapshot(pilot_id=PILOT))
    assert b["binding_evidence_valid"] is False and "binding_pilot_id_mismatch" in b["evidence_blockers"]


def test_cross_date_binding_blocks():
    b = pib.build_day1_protected_binding(
        pilot_id=PILOT, day1_date="2026-07-06",
        day1_allocation_artifact=_alloc(PILOT, "2026-07-06"), snapshot_artifact=_snapshot(day1_date=DAY1))
    assert b["binding_evidence_valid"] is False and "binding_day1_date_mismatch" in b["evidence_blockers"]


# ============================================================ missing audit / allocation validation
def test_missing_entry_price_blocks_evidence():
    p = _edu()
    del p["entry_price"]
    art = _snapshot(positions=[p])
    assert art["snapshot_evidence_valid"] is False
    assert any("protected_position_audit_incomplete" in b and "entry_price" in b for b in art["evidence_blockers"])


def test_missing_account_mode_blocks_evidence():
    art = _snapshot(account=_account(account_mode=""))
    assert art["snapshot_evidence_valid"] is False
    assert "account_evidence_incomplete:account_mode" in art["evidence_blockers"]


def test_raw_sha_allocation_does_not_complete():
    fake = {"pilot_id": PILOT, "date": DAY1, "strategy_capital_base_usd": "10000",
            "allocation_intent_fingerprint": "a" * 64, "payload_fingerprint": "a" * 64,
            "order_payloads": []}
    b = _binding(allocation=fake)
    assert b["binding_evidence_valid"] is False and any("allocation_" in x for x in b["evidence_blockers"])


def test_valid_allocation_artifact_binding_execution_ready():
    snap = _snapshot()   # EDU-only, ready
    b = _binding(snap)
    assert b["binding_evidence_valid"] is True and b["execution_ready"] is True
    assert pib._HEX64_RE.match(b["allocation_intent_fingerprint"])
    ok, reasons = pib._binding_is_sealed(
        b, snap["protected_position_snapshot_fingerprint"], snap["protected_position_snapshot_digest"])
    assert ok is True and reasons == []


# ============================================================ continuity
def test_continuity_pass_and_separate_counts_and_timing():
    post = [_edu(), _pos(STRATEGY[0], "Buy", "0.5", 0)]
    c = _continuity(post_positions=post)
    assert c["protected_position_identity_continuity"] == "PASS"
    assert c["strategy_position_count"] == 1 and c["protected_position_count"] == 1
    assert len(c["position_page_request_evidence"]) == 1
    assert pib._SHA256_RE.match(c["post_fill_continuity_fingerprint"])


def test_continuity_empty_protected_set_pass():
    snap = _snapshot(positions=[])
    b = _binding(snap)
    c = _continuity(snapshot=snap, binding=b, post_positions=[_pos(STRATEGY[0], "Buy", "1", 0)])
    assert c["protected_position_identity_continuity"] == "PASS"
    assert c["protected_position_count"] == 0


@pytest.mark.parametrize("over,code", [
    ({"side": "Buy"}, "protected_position_side_changed"),
    ({"qty": "1000"}, "protected_position_qty_changed"),
])
def test_continuity_blocks_on_identity_change(over, code):
    c = _continuity(post_positions=[_edu(**over)])
    assert c["protected_position_identity_continuity"] == pib.CONTINUITY_BLOCKED
    assert any(code in b for b in c["blockers"])


def test_continuity_blocks_on_extra_unauthorized_symbol():
    c = _continuity(post_positions=[_edu(), _pos("RANDUSDT", "Buy", "5", 0)])
    assert c["protected_position_identity_continuity"] == pib.CONTINUITY_BLOCKED
    assert "unauthorized_protected_position:RANDUSDT:0" in c["blockers"]


# ============================================================ (17) retired pilot
def test_retired_pilot_cannot_bootstrap():
    art = _snapshot(pilot_id=RETIRED)
    assert art["snapshot_evidence_valid"] is False
    assert any("retired_pilot_cannot_bootstrap" in b for b in art["evidence_blockers"])


def test_retired_pilot_cannot_be_repaired_via_binding():
    b = pib.build_day1_protected_binding(
        pilot_id=RETIRED, day1_date="2026-06-30",
        day1_allocation_artifact=_alloc(RETIRED, "2026-06-30"), snapshot_artifact=_snapshot())
    assert b["binding_evidence_valid"] is False
    assert any("retired_pilot_cannot_be_repaired" in x for x in b["evidence_blockers"])


# ============================================================ chain verifier + snapshot network
def test_chain_verifier_accepts_valid_edu_chain():
    snap = _snapshot()
    b = _binding(snap)
    c = _continuity(snap, b)
    cur = {("EDUUSDT", 2): {"symbol": "EDUUSDT", "side": "short", "qty": "1234", "position_idx": 2}}
    ok, reasons = pib.verify_day1_protected_identity_chain(
        pilot_id=PILOT, day1_date=DAY1, snapshot=snap, binding=b, continuity=c,
        current_protected_identities=cur, day1_allocation_intent=_alloc())
    assert ok is True and reasons == []


def test_chain_verifier_rejects_execution_not_ready_binding():
    snap = _snapshot(positions=_fifty_plus_edu())   # evidence valid, not bootstrap ready
    b = _binding(snap)
    c = _continuity(snap, b, post_positions=[_edu()])
    cur = {("EDUUSDT", 2): {"symbol": "EDUUSDT", "side": "short", "qty": "1234", "position_idx": 2}}
    ok, reasons = pib.verify_day1_protected_identity_chain(
        pilot_id=PILOT, day1_date=DAY1, snapshot=snap, binding=b, continuity=c,
        current_protected_identities=cur, day1_allocation_intent=_alloc())
    assert ok is False and "binding_not_execution_ready" in reasons


def test_snapshot_network_mutation_and_missing_counter_block():
    assert _snapshot(components=_components(_ctr(mut=1)))["snapshot_evidence_valid"] is False
    assert _snapshot(components={"protected_position_collector": None})["snapshot_evidence_valid"] is False


# ============================================================ (18) fully offline
def test_18_pure_core_is_offline(monkeypatch):
    import socket

    def _boom(*a, **k):
        raise AssertionError("network access attempted by pure core")

    monkeypatch.setattr(socket, "socket", _boom)
    snap = _snapshot()
    b = _binding(snap)
    _continuity(snap, b)
    assert snap["snapshot_evidence_valid"] is True


# ============================================================ CLI: three modes
def test_cli_default_does_nothing(capsys):
    rc = cli.main([])
    out = json.loads(capsys.readouterr().out)
    assert out["blockers"] == ["no_mode_selected"] and rc == cli.EXIT_INVALID


def test_cli_mutually_exclusive_modes(capsys):
    rc = cli.main(["--capture-pre-day1-protected-snapshot", "--build-day1-protected-binding"])
    out = json.loads(capsys.readouterr().out)
    assert any("mutually_exclusive_modes" in b for b in out["blockers"]) and rc == cli.EXIT_INVALID


def test_cli_capture_network_not_authorized(tmp_path, capsys):
    out_path = tmp_path / "snap.json"
    rc = cli.main(["--capture-pre-day1-protected-snapshot", "--pilot-id", PILOT,
                   "--day1-date", DAY1, "--artifact-output-json", str(out_path)])
    data = json.loads(capsys.readouterr().out)
    assert "protected_snapshot_network_not_authorized" in data["blockers"]
    assert rc == cli.EXIT_BLOCKED and not out_path.exists()


def test_cli_capture_offline_provider_includes_timing(tmp_path, capsys):
    out_path = tmp_path / "snap.json"
    provider = lambda: ([_edu()], _prov([_edu()]), _ctr(), _account())  # noqa: E731
    args = argparse.Namespace(
        pilot_id=PILOT, day1_date=DAY1, artifact_output_json=str(out_path), allow_real_network=False,
        capture_pre_day1_protected_snapshot=True, build_day1_protected_binding=False,
        verify_post_fill_protected_continuity=False)
    rc = cli.run_capture(args, snapshot_provider=provider)
    data = json.loads(capsys.readouterr().out)
    assert data["snapshot_evidence_valid"] is True and data["bootstrap_ready"] is True
    assert rc == cli.EXIT_OK and out_path.exists()
    assert len(data["position_page_request_evidence"]) == 1


def test_cli_capture_51_position_valid_but_blocked(tmp_path, capsys):
    out_path = tmp_path / "snap.json"
    pos = _fifty_plus_edu()
    provider = lambda: (pos, _prov(pos), _ctr(), _account())  # noqa: E731
    args = argparse.Namespace(
        pilot_id=PILOT, day1_date=DAY1, artifact_output_json=str(out_path), allow_real_network=False,
        capture_pre_day1_protected_snapshot=True, build_day1_protected_binding=False,
        verify_post_fill_protected_continuity=False)
    rc = cli.run_capture(args, snapshot_provider=provider)
    data = json.loads(capsys.readouterr().out)
    assert data["snapshot_evidence_valid"] is True and data["bootstrap_ready"] is False
    assert rc == cli.EXIT_BLOCKED and out_path.exists()
    assert pib._SHA256_RE.match(data["protected_position_snapshot_fingerprint"])


def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return str(p)


def test_cli_build_binding_fully_offline(tmp_path, monkeypatch, capsys):
    import socket
    monkeypatch.setattr(socket, "socket",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("socket opened")))
    snap_path = _write(tmp_path, "snap.json", _snapshot())
    alloc_path = _write(tmp_path, "alloc.json", _alloc())
    out_path = tmp_path / "binding.json"
    rc = cli.main(["--build-day1-protected-binding", "--pilot-id", PILOT, "--day1-date", DAY1,
                   "--protected-snapshot-json", snap_path,
                   "--day1-allocation-intent-json", alloc_path,
                   "--artifact-output-json", str(out_path)])
    data = json.loads(capsys.readouterr().out)
    assert data["binding_evidence_valid"] is True and data["execution_ready"] is True
    assert rc == cli.EXIT_OK and out_path.exists()
    assert data["allocation_artifact_source_sha256"].startswith("sha256:")
    assert data["allocation_artifact_source_path"] == alloc_path


def test_cli_build_binding_rejects_raw_sha(tmp_path, capsys):
    snap_path = _write(tmp_path, "snap.json", _snapshot())
    fake = {"pilot_id": PILOT, "date": DAY1, "strategy_capital_base_usd": "10000",
            "allocation_intent_fingerprint": "a" * 64, "payload_fingerprint": "a" * 64,
            "order_payloads": []}
    alloc_path = _write(tmp_path, "alloc.json", fake)
    out_path = tmp_path / "binding.json"
    rc = cli.main(["--build-day1-protected-binding", "--pilot-id", PILOT, "--day1-date", DAY1,
                   "--protected-snapshot-json", snap_path,
                   "--day1-allocation-intent-json", alloc_path,
                   "--artifact-output-json", str(out_path)])
    data = json.loads(capsys.readouterr().out)
    assert data["binding_evidence_valid"] is False and rc == cli.EXIT_BLOCKED
    assert any("allocation_" in b for b in data["evidence_blockers"])


def test_cli_continuity_uses_provider_and_emits_timing(tmp_path, capsys):
    snap = _snapshot()
    binding = _binding(snap)
    snap_path = _write(tmp_path, "snap.json", snap)
    bind_path = _write(tmp_path, "binding.json", binding)
    alloc_path = _write(tmp_path, "alloc.json", _alloc())
    out_path = tmp_path / "cont.json"
    post = [_edu()]
    provider = lambda: (post, _prov(post), _ctr())  # noqa: E731
    args = argparse.Namespace(
        pilot_id=PILOT, day1_date=DAY1, protected_snapshot_json=snap_path,
        protected_binding_json=bind_path, day1_allocation_intent_json=alloc_path,
        artifact_output_json=str(out_path), allow_real_network=False,
        capture_pre_day1_protected_snapshot=False, build_day1_protected_binding=False,
        verify_post_fill_protected_continuity=True)
    rc = cli.run_verify_continuity(args, positions_provider=provider)
    data = json.loads(capsys.readouterr().out)
    assert data["protected_position_identity_continuity"] == "PASS" and rc == cli.EXIT_OK
    assert len(data["position_page_request_evidence"]) == 1
    assert data["network_audit_counters"]["private_read_only_request_count"] == 1


def test_cli_all_modes_refuse_overwrite(tmp_path, capsys):
    out_path = tmp_path / "exists.json"
    out_path.write_text("{}", encoding="utf-8")
    snap_path = _write(tmp_path, "snap.json", _snapshot())
    alloc_path = _write(tmp_path, "alloc.json", _alloc())
    bind_path = _write(tmp_path, "binding.json", _binding())
    calls = [
        ["--capture-pre-day1-protected-snapshot", "--pilot-id", PILOT, "--day1-date", DAY1,
         "--artifact-output-json", str(out_path)],
        ["--build-day1-protected-binding", "--pilot-id", PILOT, "--day1-date", DAY1,
         "--protected-snapshot-json", snap_path, "--day1-allocation-intent-json", alloc_path,
         "--artifact-output-json", str(out_path)],
        ["--verify-post-fill-protected-continuity", "--pilot-id", PILOT, "--day1-date", DAY1,
         "--protected-snapshot-json", snap_path, "--protected-binding-json", bind_path,
         "--day1-allocation-intent-json", alloc_path, "--artifact-output-json", str(out_path)],
    ]
    for argv in calls:
        rc = cli.main(argv)
        data = json.loads(capsys.readouterr().out)
        assert "artifact_output_exists_refuse_overwrite" in data["blockers"] and rc == cli.EXIT_INVALID
