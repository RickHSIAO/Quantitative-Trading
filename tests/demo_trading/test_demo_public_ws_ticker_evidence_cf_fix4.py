"""TASK-014CH3C2_FIX1 -- final WS-evidence fingerprint seal.

Proves the WS evidence artifact's stored ``artifact_fingerprint`` always recomputes over
the FINAL persisted payload (including ``credential_leak_check`` when the collector verifies
credentials), via a single sealing boundary ``seal_artifact_fingerprint``. Offline only.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os

import pytest

from src import demo_public_ws_ticker_evidence as ws

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

_CG = os.path.join(_HERE, "test_demo_strategy_native_ws_price_binding_cg.py")
_spec = importlib.util.spec_from_file_location("_cg_helpers_cf_fix4", _CG)
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)

_COLLECTOR = os.path.join(_ROOT, "scripts", "collect_public_ws_ticker_evidence.py")


def _recompute_ok(artifact) -> bool:
    return artifact.get("artifact_fingerprint") == ws._fingerprint(
        {k: v for k, v in artifact.items() if k != "artifact_fingerprint"})


def _fresh_builder():
    u = cg._universe()
    b = ws.PublicWsTickerEvidenceBuilder(
        universe=u, clock_offset_seconds="0.0068",
        clock_offset_status="CLOCK_OFFSET_AVAILABLE",
        clock_offset_provenance_status=ws.CLOCK_OFFSET_PROVENANCE_AUTHORITATIVE,
        stale_threshold_ms=10_000)
    b.record_connection_success(0)
    return b, u


def _build(b, u, *, now, dependency_status=ws.WS_CLIENT_DEPENDENCY_AVAILABLE,
           require_complete=False):
    return b.build_artifact(
        finalize_epoch_ns=now + 1_000_000,
        legacy_position_provenance=cg.AUTH_LEGACY_PROV,
        strategy_source_provenance=cg._auth_strategy_provenance(),
        dependency_status=dependency_status, require_complete=require_complete,
        allow_real_network=True, completion_meta=None)


def _ack(b, u, now):
    b.record_subscription_request(u["unique_symbol_count"], request_id=cg.REQ_ID, generation=0)
    b.ingest_subscription_ack({"op": "subscribe", "success": True, "req_id": cg.REQ_ID},
                              connection_generation=0, received_epoch_ns=now)


def _ingest(b, u, now, *, count=None):
    syms = u["symbols"] if count is None else u["symbols"][:count]
    for i, sym in enumerate(syms):
        b.ingest_data_message(cg._snap(sym, ts=int(now / 1e6) - i, cs=1000 + i),
                              local_received_epoch_ns=now, local_monotonic_received_ns=now,
                              connection_generation=0)


def _state_complete(now):
    return cg.build_complete_ws_artifact(now_ns=now)


def _state_unavailable(now):
    b, u = _fresh_builder()
    b.record_subscription_request(u["unique_symbol_count"], request_id=cg.REQ_ID, generation=0)
    return _build(b, u, now=now)


def _state_ack_missing(now):
    b, u = _fresh_builder()
    b.record_subscription_request(u["unique_symbol_count"], request_id=cg.REQ_ID, generation=0)
    _ingest(b, u, now)
    return _build(b, u, now=now)


def _state_partial(now):
    b, u = _fresh_builder()
    _ack(b, u, now)
    _ingest(b, u, now, count=10)
    return _build(b, u, now=now)


def _state_dependency_missing(now):
    b, u = _fresh_builder()
    _ack(b, u, now)
    _ingest(b, u, now)
    return _build(b, u, now=now, dependency_status=ws.WS_CLIENT_DEPENDENCY_MISSING)


_STATES = {
    "complete": _state_complete,
    "unavailable": _state_unavailable,
    "ack_missing": _state_ack_missing,
    "partial": _state_partial,
    "dependency_missing": _state_dependency_missing,
}


# ---------------------------------------------------------------------------
# build_artifact final seal (all states recompute)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", sorted(_STATES))
def test_build_artifact_fingerprint_recomputes(state):
    art = _STATES[state](1_700_000_000_000_000_000)
    assert _recompute_ok(art)


@pytest.mark.parametrize("state", sorted(_STATES))
def test_sealed_with_credential_check_recomputes(state):
    art = _STATES[state](1_700_000_000_000_000_000)
    sealed = ws.seal_artifact_fingerprint(art, verify_no_credential_leak=True,
                                          secret_values=["a-secret-value-not-present"])
    assert sealed["credential_leak_check"] == "NO_CREDENTIAL_VALUE_OR_KEY_PRESENT"
    assert _recompute_ok(sealed)


# ---------------------------------------------------------------------------
# seal_artifact_fingerprint semantics
# ---------------------------------------------------------------------------

def test_seal_without_flag_no_field_and_recomputes():
    art = _state_complete(1_700_000_000_000_000_000)
    # Re-seal without the flag: no credential_leak_check field, still recomputes.
    sealed = ws.seal_artifact_fingerprint(dict(art))
    assert "credential_leak_check" not in sealed
    assert _recompute_ok(sealed)


def test_seal_includes_credential_check_in_fingerprint_material():
    art = _state_complete(1_700_000_000_000_000_000)
    no_check = ws.seal_artifact_fingerprint(dict(art))["artifact_fingerprint"]
    with_check = ws.seal_artifact_fingerprint(
        dict(art), verify_no_credential_leak=True)["artifact_fingerprint"]
    # Adding credential_leak_check to the payload changes the fingerprint -> it is
    # genuinely part of the fingerprint material.
    assert no_check != with_check


def test_credential_leak_failure_does_not_seal():
    art = _state_complete(1_700_000_000_000_000_000)
    original_fp = art["artifact_fingerprint"]
    leaked = cg.STRATEGY_50[0]  # a real value present in the artifact
    with pytest.raises(ws.WsEndpointError):
        ws.seal_artifact_fingerprint(art, verify_no_credential_leak=True, secret_values=[leaked])
    # Raised before adding the field or recomputing -> no falsely-sealed artifact.
    assert "credential_leak_check" not in art
    assert art["artifact_fingerprint"] == original_fp


def test_sealed_artifact_has_no_credentials():
    art = _state_complete(1_700_000_000_000_000_000)
    sealed = ws.seal_artifact_fingerprint(art, verify_no_credential_leak=True)
    ws.assert_no_credentials(sealed)  # must not raise


def test_seal_preserves_status_and_exit():
    art = _state_partial(1_700_000_000_000_000_000)
    overall, exit_status = art["overall_status"], art["cli_exit_status"]
    sealed = ws.seal_artifact_fingerprint(art, verify_no_credential_leak=True)
    assert sealed["overall_status"] == overall
    assert sealed["cli_exit_status"] == exit_status


def test_sealed_artifact_safety_counters():
    sealed = ws.seal_artifact_fingerprint(
        _state_complete(1_700_000_000_000_000_000), verify_no_credential_leak=True)
    assert sealed["authenticated"] is False
    assert sealed["execution_ready"] is False
    assert sealed["execution_batch_authorized"] is False
    assert sealed["sender_reachable"] is False
    assert sealed["order_post_count"] == 0 and sealed["amend_post_count"] == 0
    assert sealed["cancel_post_count"] == 0 and sealed["live_order_post_count"] == 0


def test_written_json_and_stdout_equivalent_sealed_artifact(tmp_path):
    sealed = ws.seal_artifact_fingerprint(
        _state_complete(1_700_000_000_000_000_000), verify_no_credential_leak=True)
    # Simulate file write + json-only stdout (collector uses indent=2, sort_keys=True).
    out = tmp_path / "ws_evidence.json"
    out.write_text(json.dumps(sealed, indent=2, sort_keys=True), encoding="utf-8")
    stdout_str = json.dumps(sealed, indent=2, sort_keys=True)
    from_file = json.loads(out.read_text(encoding="utf-8"))
    from_stdout = json.loads(stdout_str)
    assert from_file == from_stdout == sealed
    assert _recompute_ok(from_file) and _recompute_ok(from_stdout)


# ---------------------------------------------------------------------------
# Collector static contract: no post-seal mutation
# ---------------------------------------------------------------------------

def test_collector_uses_seal_helper_and_drops_old_mutation():
    src = open(_COLLECTOR, encoding="utf-8").read()
    assert "ws.seal_artifact_fingerprint(" in src
    # The old post-build mutation must be gone.
    assert 'artifact["credential_leak_check"]' not in src


def test_collector_has_no_artifact_subscript_mutation():
    src = open(_COLLECTOR, encoding="utf-8").read()
    tree = ast.parse(src)

    def _is_artifact_subscript(node) -> bool:
        return (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id == "artifact")

    violations: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if _is_artifact_subscript(t):
                    violations.append(node.lineno)
        elif isinstance(node, ast.AugAssign) and _is_artifact_subscript(node.target):
            violations.append(node.lineno)
        elif isinstance(node, ast.Delete):
            for t in node.targets:
                if _is_artifact_subscript(t):
                    violations.append(node.lineno)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "artifact" \
                and node.func.attr in {"update", "pop", "setdefault", "clear", "__setitem__"}:
            violations.append(node.lineno)
    assert violations == [], f"artifact mutation(s) at lines {violations}"


def test_evidence_module_export_and_no_network_added():
    assert "seal_artifact_fingerprint" in ws.__all__
    import src.demo_public_ws_ticker_evidence as m
    src_text = open(m.__file__, encoding="utf-8").read()
    # The seal helper itself adds no network/REST/order capability.
    for tok in ("requests", "/v5/order", "api-demo.bybit", "execute_daily_native"):
        assert tok not in src_text, tok
