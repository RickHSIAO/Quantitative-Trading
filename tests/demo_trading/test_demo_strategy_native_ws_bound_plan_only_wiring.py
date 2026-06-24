"""TASK-014CH2 -- opt-in terminal Plan-only WebSocket-bound wiring.

Proves the native daily runner gains an explicit, terminal Plan-only path that binds
the REST seed Plan to a caller-supplied WS evidence file, validates via the CH1
consumer, writes exactly one canonical wrapper, and stops before review / readiness /
execution gate / native execution / Pilot mutation -- with no REST fallback and no
live WebSocket collection. Offline fixtures + mocks only.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import time

import pytest

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_native_ws_price_binding as wb
from src import demo_strategy_native_ws_bound_plan_consumer as consumer
from src import demo_strategy_native_ws_bound_plan_only as wsbpo

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

# Reuse the canonical CG fixtures/helpers.
_CG = os.path.join(_HERE, "test_demo_strategy_native_ws_price_binding_cg.py")
_spec = importlib.util.spec_from_file_location("_cg_helpers_ch2", _CG)
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)

# Import the native daily script as a module.
_SCRIPT = os.path.join(_ROOT, "scripts", "run_demo_strategy_pilot_native_daily.py")
_sspec = importlib.util.spec_from_file_location("nrun_ch2", _SCRIPT)
nrun = importlib.util.module_from_spec(_sspec)
_sspec.loader.exec_module(nrun)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _signed_plan(rest_price="100.0"):
    plan = cg.build_plan(rest_price=rest_price)
    for tp in plan["planner"]["target_positions"]:
        if str(tp["side"]).strip().lower() == "short":
            tp["target_notional"] = "-200"
    return plan


def _signed_planner_block():
    return _signed_plan()["planner"]


class _FakePlan:
    """Minimal stand-in for the canonical PlannerResult (no network)."""
    available = True
    sizing_verification = {"verified": True, "capital_base_usd": cg.CAPITAL}

    def __init__(self, block):
        self._block = block

    def to_dict(self):
        return self._block


def _pure_kwargs(now=None, *, offset="0.0068"):
    now = now or time.time_ns()
    source = cg.build_complete_ws_artifact(now_ns=now, offset=offset)
    raw = json.dumps(source).encode("utf-8")
    return dict(
        seed_plan=_signed_plan(),
        source_ws_artifact=source,
        source_ws_artifact_bytes=raw,
        binding_epoch_ns=now + 2_000_000,
        freshness_threshold_ms=wsbpo.DEFAULT_FRESHNESS_THRESHOLD_MS,
        expected_policy_id=wsbpo.EXPECTED_POLICY_ID,
        expected_strategy_id=wsbpo.EXPECTED_STRATEGY_ID,
        expected_run_date=cg.DATE,
        expected_symbols=list(cg.STRATEGY_50),
    ), source, raw, now


# ===========================================================================
# Pure build + validation core
# ===========================================================================

def test_pure_valid_seed_plus_source_passes():
    kw, source, raw, now = _pure_kwargs()
    r = wsbpo.build_and_validate_ws_bound_plan_only(**kw)
    assert r.status == wsbpo.WS_BOUND_PLAN_ONLY_PASS
    assert r.wrapper_artifact is not None
    assert r.execution_authorized is False
    assert r.pilot_advanced is False
    assert r.canonical_bound_plan_fingerprint and r.canonical_bound_plan_fingerprint.startswith("sha256:")


def test_pure_wrapper_passes_ch1_consumer():
    kw, source, raw, now = _pure_kwargs()
    r = wsbpo.build_and_validate_ws_bound_plan_only(**kw)
    res = consumer.validate_ws_bound_plan_artifact(
        r.wrapper_artifact, source_ws_artifact=source,
        expected_policy_id=wsbpo.EXPECTED_POLICY_ID, expected_strategy_id=wsbpo.EXPECTED_STRATEGY_ID,
        expected_run_date=cg.DATE,
        expected_original_plan_fingerprint=r.original_plan_fingerprint,
        expected_ws_artifact_sha256=r.source_ws_artifact_sha256,
        expected_ws_artifact_fingerprint=r.source_ws_artifact_fingerprint,
        expected_binding_epoch_ns=r.binding_epoch_ns,
        expected_freshness_threshold_ms=r.freshness_threshold_ms,
        expected_symbols=list(cg.STRATEGY_50))
    assert res.status == consumer.WS_BOUND_PLAN_CONSUMER_PASS


def test_pure_byte_sha_comes_from_exact_supplied_bytes():
    kw, source, raw, now = _pure_kwargs()
    r = wsbpo.build_and_validate_ws_bound_plan_only(**kw)
    assert r.source_ws_artifact_sha256 == wb.compute_file_sha256(raw)
    # Different bytes -> different sha used (the wrapper carries the exact-byte sha).
    assert r.source_ws_artifact_sha256 != wb.compute_file_sha256(raw + b" ")


def test_pure_source_logical_fingerprint_independently_recomputed():
    kw, source, raw, now = _pure_kwargs()
    r = wsbpo.build_and_validate_ws_bound_plan_only(**kw)
    expected = ws._fingerprint({k: v for k, v in source.items() if k != "artifact_fingerprint"})
    assert r.source_ws_artifact_fingerprint == expected
    assert r.source_ws_artifact_fingerprint == source["artifact_fingerprint"]


def test_pure_does_not_trust_stored_source_fingerprint():
    kw, source, raw, now = _pure_kwargs()
    source["artifact_fingerprint"] = "sha256:" + "0" * 64  # stored fp lies; body unchanged
    kw["source_ws_artifact"] = source
    kw["source_ws_artifact_bytes"] = json.dumps(source).encode("utf-8")
    r = wsbpo.build_and_validate_ws_bound_plan_only(**kw)
    assert r.status != wsbpo.WS_BOUND_PLAN_ONLY_PASS
    assert r.wrapper_artifact is None


def test_pure_single_binding_epoch_shared():
    kw, source, raw, now = _pure_kwargs()
    r = wsbpo.build_and_validate_ws_bound_plan_only(**kw)
    assert r.binding_epoch_ns == kw["binding_epoch_ns"]
    assert r.wrapper_artifact["canonical_bound_plan"]["binding_epoch_ns"] == kw["binding_epoch_ns"]


def test_pure_default_strict_threshold_used():
    kw, source, raw, now = _pure_kwargs()
    assert kw["freshness_threshold_ms"] == wsbpo.STRICT_MAX_FRESHNESS_THRESHOLD_MS
    assert wsbpo.build_and_validate_ws_bound_plan_only(**kw).passed


def test_pure_explicit_valid_threshold_works():
    kw, source, raw, now = _pure_kwargs()
    kw["freshness_threshold_ms"] = wsbpo.STRICT_MAX_FRESHNESS_THRESHOLD_MS  # equals stored
    assert wsbpo.build_and_validate_ws_bound_plan_only(**kw).passed


def test_pure_threshold_over_strict_max_fails():
    kw, source, raw, now = _pure_kwargs()
    kw["freshness_threshold_ms"] = wsbpo.STRICT_MAX_FRESHNESS_THRESHOLD_MS + 1
    r = wsbpo.build_and_validate_ws_bound_plan_only(**kw)
    assert r.status == wsbpo.WS_BOUND_PLAN_ONLY_INPUT_INVALID
    assert r.wrapper_artifact is None


def test_pure_incomplete_ws_artifact_binding_failed():
    kw, source, raw, now = _pure_kwargs()
    # Drop one strategy symbol's evidence -> binder cannot produce a canonical plan.
    source["per_symbol_evidence"] = [
        rrec for rrec in source["per_symbol_evidence"]
        if str(rrec["symbol"]).strip().upper() != cg.STRATEGY_50[0]]
    source["artifact_fingerprint"] = ws._fingerprint(
        {k: v for k, v in source.items() if k != "artifact_fingerprint"})
    kw["source_ws_artifact"] = source
    kw["source_ws_artifact_bytes"] = json.dumps(source).encode("utf-8")
    r = wsbpo.build_and_validate_ws_bound_plan_only(**kw)
    assert r.status == wsbpo.WS_BOUND_PLAN_ONLY_BINDING_FAILED
    assert r.wrapper_artifact is None


def test_pure_stale_ws_artifact_binding_failed():
    now = time.time_ns()
    kw, source, raw, _ = _pure_kwargs(now=now)
    kw["binding_epoch_ns"] = now + 60_000_000_000  # 60s later -> all stale at binding
    r = wsbpo.build_and_validate_ws_bound_plan_only(**kw)
    assert r.status == wsbpo.WS_BOUND_PLAN_ONLY_BINDING_FAILED
    assert r.wrapper_artifact is None


def test_pure_mismatched_date_provenance_fails():
    kw, source, raw, now = _pure_kwargs()
    kw["expected_run_date"] = "2099-01-01"  # binder passes (uses seed date); consumer rejects
    r = wsbpo.build_and_validate_ws_bound_plan_only(**kw)
    assert r.status == wsbpo.WS_BOUND_PLAN_ONLY_CONSUMER_FAILED
    assert r.wrapper_artifact is None


def test_pure_mismatched_symbol_set_fails():
    kw, source, raw, now = _pure_kwargs()
    kw["expected_symbols"] = [f"OTHER{i:02d}USDT" for i in range(50)]
    r = wsbpo.build_and_validate_ws_bound_plan_only(**kw)
    assert r.status != wsbpo.WS_BOUND_PLAN_ONLY_PASS
    assert r.wrapper_artifact is None


def test_pure_wrapper_structurally_unmodified():
    kw, source, raw, now = _pure_kwargs()
    r = wsbpo.build_and_validate_ws_bound_plan_only(**kw)
    w = r.wrapper_artifact
    # No CH2 field injected; the binder's own wrapper fingerprint still recomputes.
    assert "ws_bound_plan_only" not in w
    assert w["wrapper_fingerprint"] == consumer._recompute_wrapper_fingerprint(w)
    assert w["execution_batch_authorized"] is False
    assert w["order_post_count"] == 0


# ===========================================================================
# CLI wiring (mocked planner/provider/forward; no network, no Pilot storage)
# ===========================================================================

def _install_seed_mocks(monkeypatch):
    """Mock the REST seed-Plan inputs so no network / Pilot storage is touched."""
    monkeypatch.setattr(nrun.fs, "load_primary_forward_strategy_result",
                        lambda **kw: {"signals": []})
    monkeypatch.setattr(nrun, "_build_production_provider", lambda: object())
    monkeypatch.setattr(nrun.planner, "plan_strategy_native_actions",
                        lambda **kw: _FakePlan(copy.deepcopy(_signed_planner_block())))


class _Counter:
    def __init__(self):
        self.n = 0

    def __call__(self, *a, **k):
        self.n += 1
        raise AssertionError("forbidden Plan-only-mode call reached")


def _install_forbidden_counters(monkeypatch):
    """Any of these being invoked in Plan-only mode is a hard failure."""
    counters = {}
    for mod, name in (
        (nrun.gate, "evaluate_execution_gate"),
        (nrun.nx, "execute_daily_native"),
        (nrun, "build_active_v1_review"),
        (nrun.nx, "advance_successful_day"),
    ):
        c = _Counter()
        counters[name] = c
        monkeypatch.setattr(mod, name, c)

    class _NoPilotStore:
        def __init__(self, *a, **k):
            raise AssertionError("Pilot state store instantiated in Plan-only mode")

    monkeypatch.setattr(nrun.rd, "PilotStateStore", _NoPilotStore)
    return counters


def _write_source(tmp_path, *, now, offset="0.0068"):
    source = cg.build_complete_ws_artifact(now_ns=now, offset=offset)
    p = tmp_path / "ws_evidence.json"
    p.write_text(json.dumps(source), encoding="utf-8")
    return p, source


def _base_argv(tmp_path, ev, out, *, epoch, extra=None):
    argv = ["--pilot-id", "P", "--date", cg.DATE, "--ws-bound-plan-only",
            "--ws-ticker-evidence-json", str(ev), "--ws-bound-plan-output-json", str(out),
            "--ws-binding-epoch-ns", str(epoch), "--test-output-root", str(tmp_path)]
    if extra:
        argv += extra
    return argv


def test_cli_valid_writes_one_wrapper_and_no_forbidden_calls(tmp_path, monkeypatch, capsys):
    _install_seed_mocks(monkeypatch)
    counters = _install_forbidden_counters(monkeypatch)
    now = time.time_ns()
    ev, source = _write_source(tmp_path, now=now)
    out = tmp_path / "bound.json"
    rc = nrun.main(_base_argv(tmp_path, ev, out, epoch=now + 2_000_000))
    assert rc == nrun.EXIT_OK
    assert out.exists()
    # Exactly one Plan artifact file produced (only the wrapper, plus the evidence input).
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bound.json", "ws_evidence.json"]
    # The written wrapper independently passes the CH1 consumer.
    wrapper = json.loads(out.read_text(encoding="utf-8"))
    res = consumer.validate_ws_bound_plan_artifact(
        wrapper, source_ws_artifact=source,
        expected_policy_id=wsbpo.EXPECTED_POLICY_ID, expected_strategy_id=wsbpo.EXPECTED_STRATEGY_ID,
        expected_run_date=cg.DATE,
        expected_original_plan_fingerprint=wrapper["canonical_bound_plan"]["original_plan_fingerprint"],
        expected_ws_artifact_sha256=wb.compute_file_sha256(ev.read_bytes()),
        expected_ws_artifact_fingerprint=source["artifact_fingerprint"],
        expected_binding_epoch_ns=now + 2_000_000,
        expected_freshness_threshold_ms=wsbpo.DEFAULT_FRESHNESS_THRESHOLD_MS,
        expected_symbols=list(cg.STRATEGY_50))
    assert res.status == consumer.WS_BOUND_PLAN_CONSUMER_PASS
    assert all(c.n == 0 for c in counters.values())
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == wsbpo.WS_BOUND_PLAN_ONLY_PASS
    assert summary["execution_authorized"] is False
    assert summary["pilot_advanced"] is False
    assert summary["rest_fallback_used"] is False


def test_cli_exact_file_bytes_drive_sha(tmp_path, monkeypatch, capsys):
    _install_seed_mocks(monkeypatch)
    now = time.time_ns()
    ev, source = _write_source(tmp_path, now=now)
    out = tmp_path / "bound.json"
    nrun.main(_base_argv(tmp_path, ev, out, epoch=now + 2_000_000))
    wrapper = json.loads(out.read_text(encoding="utf-8"))
    assert wrapper["source_ws_artifact_sha256"] == wb.compute_file_sha256(ev.read_bytes())


def test_cli_default_threshold_used(tmp_path, monkeypatch, capsys):
    _install_seed_mocks(monkeypatch)
    now = time.time_ns()
    ev, source = _write_source(tmp_path, now=now)
    out = tmp_path / "bound.json"
    # No --ws-binding-freshness-threshold-ms -> producer strict default.
    argv = ["--pilot-id", "P", "--date", cg.DATE, "--ws-bound-plan-only",
            "--ws-ticker-evidence-json", str(ev), "--ws-bound-plan-output-json", str(out),
            "--ws-binding-epoch-ns", str(now + 2_000_000), "--test-output-root", str(tmp_path)]
    rc = nrun.main(argv)
    assert rc == nrun.EXIT_OK
    summary = json.loads(capsys.readouterr().out)
    assert summary["freshness_threshold_ms"] == wsbpo.DEFAULT_FRESHNESS_THRESHOLD_MS


def test_cli_threshold_over_max_fails(tmp_path, monkeypatch, capsys):
    _install_seed_mocks(monkeypatch)
    now = time.time_ns()
    ev, source = _write_source(tmp_path, now=now)
    out = tmp_path / "bound.json"
    rc = nrun.main(_base_argv(tmp_path, ev, out, epoch=now + 2_000_000,
                              extra=["--ws-binding-freshness-threshold-ms",
                                     str(wsbpo.STRICT_MAX_FRESHNESS_THRESHOLD_MS + 1)]))
    assert rc == nrun.EXIT_INVALID
    assert not out.exists()
    assert json.loads(capsys.readouterr().out)["status"] == wsbpo.WS_BOUND_PLAN_ONLY_INPUT_INVALID


def test_cli_missing_evidence_path_fails(tmp_path, monkeypatch, capsys):
    _install_seed_mocks(monkeypatch)
    out = tmp_path / "bound.json"
    rc = nrun.main(["--pilot-id", "P", "--date", cg.DATE, "--ws-bound-plan-only",
                    "--ws-bound-plan-output-json", str(out), "--test-output-root", str(tmp_path)])
    assert rc == nrun.EXIT_INVALID
    assert not out.exists()
    assert json.loads(capsys.readouterr().out)["status"] == wsbpo.WS_BOUND_PLAN_ONLY_INPUT_INVALID


def test_cli_missing_output_path_fails(tmp_path, monkeypatch, capsys):
    _install_seed_mocks(monkeypatch)
    now = time.time_ns()
    ev, source = _write_source(tmp_path, now=now)
    rc = nrun.main(["--pilot-id", "P", "--date", cg.DATE, "--ws-bound-plan-only",
                    "--ws-ticker-evidence-json", str(ev), "--test-output-root", str(tmp_path)])
    assert rc == nrun.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == wsbpo.WS_BOUND_PLAN_ONLY_INPUT_INVALID


def test_cli_unreadable_evidence_fails(tmp_path, monkeypatch, capsys):
    _install_seed_mocks(monkeypatch)
    out = tmp_path / "bound.json"
    missing = tmp_path / "nope.json"
    rc = nrun.main(_base_argv(tmp_path, missing, out, epoch=time.time_ns() + 2_000_000))
    assert rc == nrun.EXIT_INPUT_FAILURE
    assert not out.exists()
    assert json.loads(capsys.readouterr().out)["status"] == wsbpo.WS_BOUND_PLAN_ONLY_SOURCE_READ_FAILED


def test_cli_invalid_json_fails(tmp_path, monkeypatch, capsys):
    _install_seed_mocks(monkeypatch)
    ev = tmp_path / "bad.json"
    ev.write_text("{not valid json", encoding="utf-8")
    out = tmp_path / "bound.json"
    rc = nrun.main(_base_argv(tmp_path, ev, out, epoch=time.time_ns() + 2_000_000))
    assert rc == nrun.EXIT_INPUT_FAILURE
    assert not out.exists()
    assert json.loads(capsys.readouterr().out)["status"] == wsbpo.WS_BOUND_PLAN_ONLY_SOURCE_JSON_INVALID


def test_cli_binding_failed_no_output_no_temp(tmp_path, monkeypatch, capsys):
    _install_seed_mocks(monkeypatch)
    now = time.time_ns()
    ev, source = _write_source(tmp_path, now=now)
    out = tmp_path / "bound.json"
    # Binding epoch 60s after fresh evidence -> all stale -> BINDING_FAILED.
    rc = nrun.main(_base_argv(tmp_path, ev, out, epoch=now + 60_000_000_000))
    assert rc == nrun.EXIT_BLOCKED
    assert not out.exists()
    assert not any(p.suffix == ".tmp" for p in tmp_path.iterdir())  # no partial temp
    assert json.loads(capsys.readouterr().out)["status"] == wsbpo.WS_BOUND_PLAN_ONLY_BINDING_FAILED


def test_cli_consumer_failed_no_rest_fallback(tmp_path, monkeypatch, capsys):
    _install_seed_mocks(monkeypatch)
    counters = _install_forbidden_counters(monkeypatch)
    now = time.time_ns()
    # Source date differs from the run date -> binder PASS, CH1 consumer rejects.
    source = cg.build_complete_ws_artifact(now_ns=now)
    ev = tmp_path / "ws_evidence.json"
    ev.write_text(json.dumps(source), encoding="utf-8")
    out = tmp_path / "bound.json"
    argv = ["--pilot-id", "P", "--date", "2099-01-01", "--ws-bound-plan-only",
            "--ws-ticker-evidence-json", str(ev), "--ws-bound-plan-output-json", str(out),
            "--ws-binding-epoch-ns", str(now + 2_000_000), "--test-output-root", str(tmp_path)]
    rc = nrun.main(argv)
    assert rc == nrun.EXIT_BLOCKED
    assert not out.exists()
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] in (wsbpo.WS_BOUND_PLAN_ONLY_CONSUMER_FAILED,
                                 wsbpo.WS_BOUND_PLAN_ONLY_BINDING_FAILED)
    assert summary["rest_fallback_used"] is False
    assert all(c.n == 0 for c in counters.values())


def test_cli_rejects_execution_capable_arguments(tmp_path, monkeypatch, capsys):
    _install_seed_mocks(monkeypatch)
    counters = _install_forbidden_counters(monkeypatch)
    now = time.time_ns()
    ev, source = _write_source(tmp_path, now=now)
    out = tmp_path / "bound.json"
    rc = nrun.main(_base_argv(tmp_path, ev, out, epoch=now + 2_000_000,
                              extra=["--send-orders-to-demo"]))
    assert rc == nrun.EXIT_INVALID
    assert not out.exists()
    assert json.loads(capsys.readouterr().out)["status"] == wsbpo.WS_BOUND_PLAN_ONLY_INPUT_INVALID
    assert all(c.n == 0 for c in counters.values())


def test_cli_rejects_advance_on_success(tmp_path, monkeypatch, capsys):
    _install_seed_mocks(monkeypatch)
    now = time.time_ns()
    ev, source = _write_source(tmp_path, now=now)
    out = tmp_path / "bound.json"
    rc = nrun.main(_base_argv(tmp_path, ev, out, epoch=now + 2_000_000,
                              extra=["--advance-on-success"]))
    assert rc == nrun.EXIT_INVALID
    assert not out.exists()


# ===========================================================================
# Default path unchanged when the opt-in flag is absent
# ===========================================================================

def test_default_path_unchanged_without_flag(tmp_path, monkeypatch, capsys):
    parser = nrun.build_parser()
    ns = parser.parse_args(["--pilot-id", "P", "--date", cg.DATE])
    assert ns.ws_bound_plan_only is False

    # Without the flag, main() reaches the existing RUNNING gate and never enters CH2.
    ws_calls = _Counter()
    monkeypatch.setattr(nrun, "_run_ws_bound_plan_only", ws_calls)

    class _NotRunningStore:
        def __init__(self, *a, **k):
            pass

        def read_state(self):
            return None

    monkeypatch.setattr(nrun.rd, "PilotStateStore", _NotRunningStore)
    rc = nrun.main(["--pilot-id", "P", "--date", cg.DATE, "--test-output-root", str(tmp_path)])
    assert rc == nrun.EXIT_BLOCKED
    assert ws_calls.n == 0
    assert json.loads(capsys.readouterr().out)["status"] == nrun.nx.DAY_NOT_RUNNING
