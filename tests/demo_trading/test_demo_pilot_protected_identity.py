"""TASK-014CA: pre-Day-1 protected-position identity bootstrap tests.

A sealed PRE_DAY1 snapshot binds ONLY immutable identity (symbol/side/qty/position_idx) from a
COMPLETE Demo private read-only pagination; the Day-1 allocation intent is bound to it by
fingerprint; post-fill continuity requires EXACT identity or fails closed. Retired Pilots can never
be repaired. Fully offline (fixtures only, no Bybit, no API key, no Pilot-state write).
"""
from __future__ import annotations

import argparse
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
ALLOC_FP = "sha256:" + "a" * 64
STRATEGY = ["BTCUSDT", "ETHUSDT"]
GEN = "2026-07-05T00:00:00+00:00"


# ------------------------------------------------------------------ fixture builders
def _pos(symbol, side, qty, position_idx):
    return {"symbol": symbol, "side": side, "qty": qty, "position_idx": position_idx}


def _edu(**over):
    row = _pos("EDUUSDT", "Sell", "1234", 2)
    row.update(over)
    return row


def _positions(extra=None):
    rows = [_edu()]
    return rows + list(extra) if extra else rows


def _prov(positions, reason="empty_cursor", pages=1):
    n = len(positions)
    return {"termination_reason": reason, "page_count": pages,
            "api_position_rows": n, "nonzero_position_count": n}


def _ctr(ro=1, pub=0, mut=0):
    return {"private_read_only_request_count": ro, "public_read_only_request_count": pub,
            "private_mutating_request_count": mut}


def _components(ctr="default"):
    return {"protected_position_collector": _ctr() if ctr == "default" else ctr}


def _account():
    return {"account_mode": "demo", "demo_flag": True, "endpoint_family": "bybit_demo",
            "base_url_used": "https://api-demo.bybit.com"}


def _snapshot(positions=None, provenance=None, components="default", account=None,
              pilot_id=PILOT, day1_date=DAY1):
    positions = _positions() if positions is None else positions
    provenance = _prov(positions) if provenance is None else provenance
    return pib.build_pre_day1_protected_snapshot(
        pilot_id=pilot_id, day1_date=day1_date, positions=positions,
        positions_provenance=provenance,
        network_counter_components=_components() if components == "default" else components,
        account_evidence=_account() if account is None else account,
        source_endpoint="/v5/position/list", generated_at=GEN)


def _binding(snapshot=None, alloc_fp=ALLOC_FP, pilot_id=PILOT, day1_date=DAY1):
    snapshot = _snapshot() if snapshot is None else snapshot
    return pib.build_day1_protected_binding(
        pilot_id=pilot_id, day1_date=day1_date, allocation_intent_fingerprint=alloc_fp,
        snapshot_artifact=snapshot)


def _continuity(snapshot=None, binding=None, post_positions=None, post_prov=None,
                components="default", strategy_symbols=None, pilot_id=PILOT, day1_date=DAY1):
    snapshot = _snapshot() if snapshot is None else snapshot
    binding = _binding(snapshot) if binding is None else binding
    post_positions = _positions() if post_positions is None else post_positions
    post_prov = _prov(post_positions) if post_prov is None else post_prov
    return pib.verify_post_fill_protected_continuity(
        pilot_id=pilot_id, day1_date=day1_date, snapshot_artifact=snapshot,
        binding_artifact=binding, post_fill_positions=post_positions,
        post_fill_provenance=post_prov,
        network_counter_components=_components() if components == "default" else components,
        strategy_symbols=STRATEGY if strategy_symbols is None else strategy_symbols,
        generated_at="2026-07-05T23:00:00+00:00")


# =========================================================================== A
def test_a_eduusdt_canonically_sealed():
    art = _snapshot()
    assert art["verdict"] == pib.SNAPSHOT_READY
    edu = next(r for r in art["canonical_protected_positions"] if r["symbol"] == "EDUUSDT")
    assert edu["side"] == "short" and edu["display_side"] == "Sell"
    assert edu["qty"] == "1234" and edu["position_idx"] == 2
    assert "EDUUSDT" in art["protected_symbol_set"]
    assert art["phase"] == "PRE_DAY1" and art["trading_authorized"] is False
    assert art["execution_ready"] is False
    assert art["private_mutating_request_count"] == 0
    assert pib._SHA256_RE.match(art["protected_position_snapshot_fingerprint"])
    assert pib._SHA256_RE.match(art["protected_position_snapshot_digest"])


# =========================================================================== B
def test_b_fingerprint_deterministic():
    a, b = _snapshot(), _snapshot()
    assert (a["protected_position_snapshot_fingerprint"]
            == b["protected_position_snapshot_fingerprint"])
    assert a["protected_position_snapshot_digest"] == b["protected_position_snapshot_digest"]


# =========================================================================== C
def test_c_identity_change_changes_fingerprint():
    base = _snapshot()["protected_position_snapshot_fingerprint"]
    side = _snapshot(positions=[_edu(side="Buy")])["protected_position_snapshot_fingerprint"]
    qty = _snapshot(positions=[_edu(qty="1235")])["protected_position_snapshot_fingerprint"]
    idx = _snapshot(positions=[_edu(position_idx=1)])["protected_position_snapshot_fingerprint"]
    assert len({base, side, qty, idx}) == 4


# =========================================================================== D
def test_d_pagination_incomplete_blocks():
    art = _snapshot(provenance=_prov(_positions(), reason="max_page_cap_exceeded"))
    assert art["verdict"] == pib.SNAPSHOT_BLOCKED
    assert any("pagination_incomplete" in b for b in art["blockers"])
    assert art["protected_position_snapshot_fingerprint"] == ""
    assert art["protected_position_snapshot_digest"] == ""


# =========================================================================== E
def test_e_network_mutation_blocks():
    art = _snapshot(components=_components(_ctr(mut=1)))
    assert art["verdict"] == pib.SNAPSHOT_BLOCKED
    assert any("private_mutating_requests_detected" in b for b in art["blockers"])


# =========================================================================== F
def test_f_missing_or_malformed_counter_blocks():
    art = _snapshot(components={"protected_position_collector": {"private_read_only_request_count": 1}})
    assert art["verdict"] == pib.SNAPSHOT_BLOCKED
    assert any("unaccounted_network_component" in b for b in art["blockers"])
    assert _snapshot(components={"protected_position_collector": None})["verdict"] == pib.SNAPSHOT_BLOCKED


# =========================================================================== G
def test_g_binding_binds_fingerprints():
    snap = _snapshot()
    b = _binding(snap)
    assert b["verdict"] == pib.BINDING_COMPLETE and b["execution_ready"] is True
    assert b["allocation_intent_fingerprint"] == ALLOC_FP
    assert (b["protected_position_snapshot_fingerprint"]
            == snap["protected_position_snapshot_fingerprint"])
    assert b["protected_position_snapshot_digest"] == snap["protected_position_snapshot_digest"]
    assert pib._SHA256_RE.match(b["binding_fingerprint"])
    # a different allocation intent or a different snapshot yields a different binding fingerprint
    assert _binding(snap, alloc_fp="sha256:" + "b" * 64)["binding_fingerprint"] != b["binding_fingerprint"]
    assert _binding(_snapshot(positions=[_edu(qty="9")]))["binding_fingerprint"] != b["binding_fingerprint"]


def test_g_missing_allocation_intent_not_execution_ready():
    b = _binding(alloc_fp="")
    assert b["verdict"] == pib.BINDING_BLOCKED and b["execution_ready"] is False
    assert "allocation_intent_fingerprint_missing" in b["blockers"]


def test_g_binding_rejects_invalid_snapshot():
    b = _binding(_snapshot(components=_components(_ctr(mut=1))))
    assert b["verdict"] == pib.BINDING_BLOCKED
    assert "snapshot_not_valid" in b["blockers"]


# =========================================================================== H
def test_h_post_fill_continuity_pass():
    c = _continuity()
    assert c["protected_position_identity_continuity"] == "PASS"
    assert c["continuity_pass"] is True and c["execution_ready"] is False
    assert c["protected_position_count"] == 1
    assert pib._SHA256_RE.match(c["post_fill_continuity_fingerprint"])


def test_h_strategy_and_protected_counted_separately():
    c = _continuity(post_positions=[_edu(), _pos("BTCUSDT", "Buy", "0.5", 0)])
    assert c["protected_position_identity_continuity"] == "PASS"
    assert c["strategy_position_count"] == 1 and c["strategy_positions_present"] == ["BTCUSDT"]
    assert c["protected_position_count"] == 1 and c["protected_positions_present"] == ["EDUUSDT"]


# =========================================================================== I
@pytest.mark.parametrize("over,code", [
    ({"side": "Buy"}, "protected_position_side_changed"),
    ({"qty": "1000"}, "protected_position_qty_changed"),
    ({"position_idx": 1}, "protected_position_idx_changed"),
])
def test_i_post_fill_continuity_blocks_on_change(over, code):
    c = _continuity(post_positions=[_edu(**over)])
    assert c["protected_position_identity_continuity"] == pib.CONTINUITY_BLOCKED
    assert any(code in b for b in c["blockers"])
    assert c["post_fill_continuity_fingerprint"] == ""


def test_i_post_fill_missing_protected_blocks():
    c = _continuity(post_positions=[])
    assert c["protected_position_identity_continuity"] == pib.CONTINUITY_BLOCKED
    assert "protected_position_missing:EDUUSDT" in c["blockers"]


# =========================================================================== J
def test_j_extra_unauthorized_symbol_blocks():
    c = _continuity(post_positions=[_edu(), _pos("RANDUSDT", "Buy", "5", 0)])
    assert c["protected_position_identity_continuity"] == pib.CONTINUITY_BLOCKED
    assert "unauthorized_protected_position:RANDUSDT" in c["blockers"]


# =========================================================================== K
def test_k_retired_pilot_cannot_bootstrap():
    snap = _snapshot(pilot_id=RETIRED)
    assert snap["verdict"] == pib.SNAPSHOT_BLOCKED
    assert any("retired_pilot_cannot_bootstrap" in b for b in snap["blockers"])


def test_k_retired_pilot_cannot_be_repaired_via_binding():
    good = _snapshot()  # a valid NEW-pilot snapshot
    b = pib.build_day1_protected_binding(
        pilot_id=RETIRED, day1_date="2026-06-30",
        allocation_intent_fingerprint=ALLOC_FP, snapshot_artifact=good)
    assert b["verdict"] == pib.BINDING_BLOCKED
    assert any("retired_pilot_cannot_be_repaired" in x for x in b["blockers"])
    assert b["execution_ready"] is False


# =========================================================================== L
def test_l_pure_core_is_offline(monkeypatch):
    import socket

    def _boom(*a, **k):
        raise AssertionError("network access attempted by pure core")

    monkeypatch.setattr(socket, "socket", _boom)
    snap = _snapshot()
    _binding(snap)
    _continuity()
    assert snap["verdict"] == pib.SNAPSHOT_READY


# =========================================================================== CLI
def test_cli_default_does_nothing(capsys):
    rc = cli.main([])
    out = json.loads(capsys.readouterr().out)
    assert out["blockers"] == ["no_mode_selected"] and rc == cli.EXIT_INVALID


def test_cli_network_not_authorized_blocks(tmp_path, capsys):
    out_path = tmp_path / "snap.json"
    rc = cli.main(["--capture-pre-day1-protected-snapshot", "--pilot-id", PILOT,
                   "--day1-date", DAY1, "--artifact-output-json", str(out_path)])
    data = json.loads(capsys.readouterr().out)
    assert "protected_snapshot_network_not_authorized" in data["blockers"]
    assert rc == cli.EXIT_BLOCKED and not out_path.exists()


def test_cli_refuses_overwrite(tmp_path, capsys):
    out_path = tmp_path / "snap.json"
    out_path.write_text("{}", encoding="utf-8")
    rc = cli.main(["--capture-pre-day1-protected-snapshot", "--pilot-id", PILOT,
                   "--day1-date", DAY1, "--artifact-output-json", str(out_path)])
    data = json.loads(capsys.readouterr().out)
    assert "artifact_output_exists_refuse_overwrite" in data["blockers"]
    assert rc == cli.EXIT_INVALID


def test_cli_capture_offline_provider_writes_artifact(tmp_path, capsys):
    out_path = tmp_path / "snap.json"
    provider = lambda: (_positions(), _prov(_positions()), _ctr(), _account())  # noqa: E731
    args = argparse.Namespace(pilot_id=PILOT, day1_date=DAY1,
                              artifact_output_json=str(out_path), allow_real_network=False,
                              capture_pre_day1_protected_snapshot=True)
    rc = cli.run_capture(args, snapshot_provider=provider)
    data = json.loads(capsys.readouterr().out)
    assert data["verdict"] == pib.SNAPSHOT_READY and rc == cli.EXIT_READY
    assert out_path.exists()
    on_disk = json.loads(out_path.read_text(encoding="utf-8"))
    assert on_disk["protected_position_snapshot_fingerprint"] == data["protected_position_snapshot_fingerprint"]
