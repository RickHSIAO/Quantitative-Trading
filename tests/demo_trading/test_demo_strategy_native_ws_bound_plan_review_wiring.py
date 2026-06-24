"""TASK-014CH3B2 -- review-only CLI wiring.

Wires the CH3B1 pure review core into an explicit terminal `--ws-bound-plan-review-only`
CLI mode: exact anchor-manifest/wrapper/source bytes + externally-supplied expected
manifest SHA256 -> pure historical review -> one race-safe no-clobber review envelope ->
terminal JSON summary. Offline temp files only; no network/sender/Pilot/execution.
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
from src import demo_strategy_native_ws_bound_plan_only as wsbpo
from src import demo_strategy_native_ws_bound_plan_review as wsbpr

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

_CG = os.path.join(_HERE, "test_demo_strategy_native_ws_price_binding_cg.py")
_spec = importlib.util.spec_from_file_location("_cg_helpers_ch3b2", _CG)
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)

_SCRIPT = os.path.join(_ROOT, "scripts", "run_demo_strategy_pilot_native_daily.py")
_sspec = importlib.util.spec_from_file_location("nrun_ch3b2", _SCRIPT)
nrun = importlib.util.module_from_spec(_sspec)
_sspec.loader.exec_module(nrun)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _signed_plan(rest_price="100.0"):
    plan = cg.build_plan(rest_price=rest_price)
    for tp in plan["planner"]["target_positions"]:
        if str(tp["side"]).strip().lower() == "short":
            tp["target_notional"] = "-200"
    return plan


def _seal_manifest(manifest: dict) -> tuple[bytes, str]:
    m = dict(manifest)
    m.pop("manifest_fingerprint", None)
    m["manifest_fingerprint"] = ws._fingerprint(m)
    raw = json.dumps(m).encode("utf-8")
    return raw, wb.compute_file_sha256(raw)


def _make_bytes(now=None):
    now = now or time.time_ns()
    ws_art = cg.build_complete_ws_artifact(now_ns=now)
    source_bytes = json.dumps(ws_art).encode("utf-8")
    source_sha = wb.compute_file_sha256(source_bytes)
    plan = _signed_plan()
    epoch = now + 2_000_000
    threshold = wb.DEFAULT_BINDING_FRESHNESS_THRESHOLD_MS
    wrapper = wb.build_ws_bound_plan_artifact(
        plan_artifact=plan, ws_artifact=ws_art, ws_artifact_path="ws.json",
        ws_artifact_sha256=source_sha, binding_epoch_ns=epoch,
        binding_freshness_threshold_ms=threshold)
    assert wrapper["canonical_bound_plan"] is not None
    wrapper_bytes = json.dumps(wrapper).encode("utf-8")
    symbols = list(cg.STRATEGY_50)
    manifest = {
        "schema": wsbpr.ANCHOR_MANIFEST_SCHEMA,
        "schema_version": wsbpr.ANCHOR_MANIFEST_SCHEMA_VERSION,
        "policy_id": wb.ACTIVE_STRATEGY_NATIVE_V1_POLICY,
        "strategy_id": wb.EXPECTED_STRATEGY_NAME,
        "run_date": cg.DATE,
        "original_plan_fingerprint": wb._fingerprint(plan),
        "source_ws_artifact_sha256": source_sha,
        "source_ws_artifact_fingerprint": ws._fingerprint(
            {k: v for k, v in ws_art.items() if k != "artifact_fingerprint"}),
        "canonical_bound_plan_fingerprint":
            wrapper["canonical_bound_plan"]["canonical_bound_plan_fingerprint"],
        "wrapper_fingerprint": wrapper["wrapper_fingerprint"],
        "binding_epoch_ns": epoch,
        "freshness_threshold_ms": threshold,
        "strategy_symbols": symbols,
        "expected_symbol_set_fingerprint":
            ws.canonical_strategy_symbol_set_fingerprint(symbols),
    }
    manifest_bytes, manifest_sha = _seal_manifest(manifest)
    return manifest_bytes, manifest_sha, wrapper_bytes, source_bytes


def _write_files(tmp_path, *, names=("manifest.json", "wrapper.json", "source.json")):
    manifest_bytes, manifest_sha, wrapper_bytes, source_bytes = _make_bytes()
    mpath = tmp_path / names[0]
    wpath = tmp_path / names[1]
    spath = tmp_path / names[2]
    mpath.write_bytes(manifest_bytes)
    wpath.write_bytes(wrapper_bytes)
    spath.write_bytes(source_bytes)
    return dict(manifest=str(mpath), manifest_sha=manifest_sha, wrapper=str(wpath),
                source=str(spath), out=str(tmp_path / "review.json"),
                manifest_bytes=manifest_bytes, wrapper_bytes=wrapper_bytes,
                source_bytes=source_bytes)


def _argv(b, *, out=None, manifest=None, manifest_sha=None, wrapper=None, source=None,
          date=None, extra=None):
    argv = ["--pilot-id", "P", "--date", date or cg.DATE, "--ws-bound-plan-review-only",
            "--ws-bound-plan-anchor-manifest-json", manifest or b["manifest"],
            "--ws-bound-plan-anchor-manifest-sha256", manifest_sha or b["manifest_sha"],
            "--ws-bound-plan-wrapper-json", wrapper or b["wrapper"],
            "--ws-ticker-evidence-json", source or b["source"],
            "--ws-bound-plan-review-output-json", out or b["out"]]
    if extra:
        argv += extra
    return argv


class _Raiser:
    def __init__(self):
        self.n = 0

    def __call__(self, *a, **k):
        self.n += 1
        raise AssertionError("forbidden review-only-mode call reached")


def _install_forbidden(monkeypatch):
    counters = {}
    for mod, name in (
        (nrun.nrep, "reconcile_outputs_only"),
        (nrun.fs, "load_primary_forward_strategy_result"),
        (nrun, "_build_production_provider"),
        (nrun.planner, "plan_strategy_native_actions"),
        (nrun.gate, "evaluate_execution_gate"),
        (nrun.nx, "execute_daily_native"),
        (nrun.nx, "advance_successful_day"),
        (nrun, "build_active_v1_review"),
    ):
        c = _Raiser()
        counters[name] = c
        monkeypatch.setattr(mod, name, c)

    class _NoPilotStore:
        def __init__(self, *a, **k):
            raise AssertionError("PilotStateStore touched in review-only mode")

    monkeypatch.setattr(nrun.rd, "PilotStateStore", _NoPilotStore)
    return counters


# ===========================================================================
# Happy path
# ===========================================================================

def test_valid_review_only_writes_artifact(tmp_path, monkeypatch, capsys):
    counters = _install_forbidden(monkeypatch)
    b = _write_files(tmp_path)
    rc = nrun.main(_argv(b))
    assert rc == nrun.EXIT_OK
    assert os.path.exists(b["out"])
    # exactly one output + the 3 inputs; no temp left.
    assert sorted(p.name for p in tmp_path.iterdir()) == \
        ["manifest.json", "review.json", "source.json", "wrapper.json"]
    assert all(c.n == 0 for c in counters.values())
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == wsbpr.WS_BOUND_PLAN_REVIEW_PASS
    assert summary["review_artifact_written"] is True
    assert summary["execution_readiness"] is False
    assert summary["rest_fallback_used"] is False


def test_output_bytes_parse_to_pure_core_envelope(tmp_path):
    b = _write_files(tmp_path)
    nrun.main(_argv(b))
    written = json.loads(open(b["out"], encoding="utf-8").read())
    expected = wsbpr.build_ws_bound_plan_review(
        anchor_manifest_bytes=b["manifest_bytes"],
        expected_anchor_manifest_sha256=b["manifest_sha"],
        wrapper_artifact_bytes=b["wrapper_bytes"],
        source_ws_artifact_bytes=b["source_bytes"]).review_artifact
    assert written == expected


def test_summary_freshness_and_margin_semantics(tmp_path, capsys):
    b = _write_files(tmp_path)
    nrun.main(_argv(b))
    s = json.loads(capsys.readouterr().out)
    assert s["binding_time_freshness_verified"] is True
    assert s["current_market_freshness_status"] == "NOT_EVALUATED"
    assert s["current_market_freshness_checked"] is False
    assert s["offline_projected_margin_rate_status"] == "UNAVAILABLE_NO_INDEPENDENT_RATE"
    assert s["offline_projected_margin_review_complete"] is False
    assert s["account_margin_feasibility_status"] == "UNAVAILABLE_NOT_EVALUATED"
    assert s["gross_exposure_usd"] == "10000" and s["net_signed_exposure_usd"] == "0"
    assert s["long_exposure_usd"] == "5000" and s["short_absolute_exposure_usd"] == "5000"
    assert s["action_count"] == 50 and s["long_count"] == 25 and s["short_count"] == 25


def test_review_only_does_not_read_pilot_state(tmp_path, monkeypatch):
    _install_forbidden(monkeypatch)  # PilotStateStore raises if constructed
    b = _write_files(tmp_path)
    assert nrun.main(_argv(b)) == nrun.EXIT_OK  # no AssertionError -> Pilot untouched


# ===========================================================================
# Required flags / manifest SHA
# ===========================================================================

@pytest.mark.parametrize("drop", [
    "--ws-bound-plan-anchor-manifest-json", "--ws-bound-plan-anchor-manifest-sha256",
    "--ws-bound-plan-wrapper-json", "--ws-ticker-evidence-json",
    "--ws-bound-plan-review-output-json"])
def test_missing_required_flag_fails(tmp_path, monkeypatch, capsys, drop):
    counters = _install_forbidden(monkeypatch)
    read_spy = _Raiser()
    monkeypatch.setattr(nrun.wsbpo, "read_source_ws_bytes", read_spy)
    b = _write_files(tmp_path)
    argv = _argv(b)
    i = argv.index(drop)
    del argv[i:i + 2]  # remove flag + its value
    rc = nrun.main(argv)
    assert rc == nrun.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == wsbpr.WS_BOUND_PLAN_REVIEW_INPUT_INVALID
    assert read_spy.n == 0 and all(c.n == 0 for c in counters.values())
    assert not os.path.exists(b["out"])


def test_non_canonical_manifest_sha_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(nrun.wsbpo, "read_source_ws_bytes", _Raiser())  # must not read
    b = _write_files(tmp_path)
    rc = nrun.main(_argv(b, manifest_sha="not-canonical"))
    assert rc == nrun.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == wsbpr.WS_BOUND_PLAN_REVIEW_INPUT_INVALID
    assert not os.path.exists(b["out"])


def test_wrong_manifest_sha_fails(tmp_path, capsys):
    b = _write_files(tmp_path)
    rc = nrun.main(_argv(b, manifest_sha="sha256:" + "0" * 64))
    assert rc == nrun.EXIT_BLOCKED
    assert json.loads(capsys.readouterr().out)["status"] == wsbpr.WS_BOUND_PLAN_REVIEW_MANIFEST_MISMATCH
    assert not os.path.exists(b["out"])


# ===========================================================================
# Mode conflicts (before any read)
# ===========================================================================

@pytest.mark.parametrize("flag", [
    "--ws-bound-plan-only", "--send-orders-to-demo", "--advance-on-success",
    "--reconcile-outputs-only", "--allow-notion-network", "--allow-discord-network"])
def test_mode_conflict_rejected_before_read(tmp_path, monkeypatch, capsys, flag):
    counters = _install_forbidden(monkeypatch)
    read_spy = _Raiser()
    monkeypatch.setattr(nrun.wsbpo, "read_source_ws_bytes", read_spy)
    b = _write_files(tmp_path)
    rc = nrun.main(_argv(b, extra=[flag]))
    assert rc == nrun.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == wsbpr.WS_BOUND_PLAN_REVIEW_INPUT_INVALID
    assert read_spy.n == 0 and all(c.n == 0 for c in counters.values())
    assert not os.path.exists(b["out"])


def test_conflict_ch2_output_flag_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(nrun.wsbpo, "read_source_ws_bytes", _Raiser())
    b = _write_files(tmp_path)
    rc = nrun.main(_argv(b, extra=["--ws-bound-plan-output-json", str(tmp_path / "x.json")]))
    assert rc == nrun.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == wsbpr.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_test_injected_actions_json_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(nrun.wsbpo, "read_source_ws_bytes", _Raiser())
    b = _write_files(tmp_path)
    rc = nrun.main(_argv(b, extra=["--test-injected-actions-json", str(tmp_path / "i.json")]))
    assert rc == nrun.EXIT_INVALID


# ===========================================================================
# Malformed inputs / propagation
# ===========================================================================

def test_malformed_manifest_file_fails(tmp_path, capsys):
    b = _write_files(tmp_path)
    open(b["manifest"], "wb").write(b"{not json")
    sha = wb.compute_file_sha256(b"{not json")
    rc = nrun.main(_argv(b, manifest_sha=sha))
    assert rc in (nrun.EXIT_INVALID, nrun.EXIT_BLOCKED)
    assert json.loads(capsys.readouterr().out)["status"] in (
        wsbpr.WS_BOUND_PLAN_REVIEW_INPUT_INVALID, wsbpr.WS_BOUND_PLAN_REVIEW_MANIFEST_MISMATCH)
    assert not os.path.exists(b["out"])


def test_malformed_wrapper_file_fails(tmp_path, capsys):
    b = _write_files(tmp_path)
    open(b["wrapper"], "wb").write(b"[1,2,3]")
    rc = nrun.main(_argv(b))
    assert rc == nrun.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == wsbpr.WS_BOUND_PLAN_REVIEW_INPUT_INVALID
    assert not os.path.exists(b["out"])


def test_malformed_source_file_fails(tmp_path, capsys):
    b = _write_files(tmp_path)
    open(b["source"], "wb").write(b"{bad")
    rc = nrun.main(_argv(b))
    assert rc == nrun.EXIT_INVALID
    assert not os.path.exists(b["out"])


def test_source_mismatch_propagated(tmp_path, capsys):
    b = _write_files(tmp_path)
    # Replace the source with a different valid WS artifact (different fingerprint/sha).
    other = json.dumps(cg.build_complete_ws_artifact(now_ns=time.time_ns() + 10 ** 9)).encode()
    open(b["source"], "wb").write(other)
    rc = nrun.main(_argv(b))
    assert rc == nrun.EXIT_BLOCKED
    assert json.loads(capsys.readouterr().out)["status"] == wsbpr.WS_BOUND_PLAN_REVIEW_SOURCE_MISMATCH
    assert not os.path.exists(b["out"])


def test_date_mismatch_fails(tmp_path, capsys):
    b = _write_files(tmp_path)
    rc = nrun.main(_argv(b, date="2099-01-01"))
    assert rc == nrun.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == wsbpr.WS_BOUND_PLAN_REVIEW_INPUT_INVALID
    assert not os.path.exists(b["out"])


def test_input_read_failure_fails(tmp_path, capsys):
    b = _write_files(tmp_path)
    os.remove(b["wrapper"])
    rc = nrun.main(_argv(b))
    assert rc == nrun.EXIT_INPUT_FAILURE
    assert json.loads(capsys.readouterr().out)["status"] == "WS_BOUND_PLAN_REVIEW_INPUT_READ_FAILED"
    assert not os.path.exists(b["out"])


# ===========================================================================
# Path identity + occupied output
# ===========================================================================

def test_output_equals_wrapper_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(nrun.wsbpo, "read_source_ws_bytes", _Raiser())
    b = _write_files(tmp_path)
    before = open(b["wrapper"], "rb").read()
    rc = nrun.main(_argv(b, out=b["wrapper"]))
    assert rc == nrun.EXIT_INVALID
    assert open(b["wrapper"], "rb").read() == before  # input untouched


def test_relative_abs_alias_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(nrun.wsbpo, "read_source_ws_bytes", _Raiser())
    b = _write_files(tmp_path)
    alias = os.path.join(str(tmp_path), "sub", "..", "manifest.json")  # == manifest
    rc = nrun.main(_argv(b, out=alias))
    assert rc == nrun.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == wsbpr.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_preexisting_regular_output_rejected_before_read(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(nrun.wsbpo, "read_source_ws_bytes", _Raiser())
    b = _write_files(tmp_path)
    sentinel = b'{"sentinel": true}'
    open(b["out"], "wb").write(sentinel)
    rc = nrun.main(_argv(b))
    assert rc == nrun.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == "WS_BOUND_PLAN_REVIEW_OUTPUT_EXISTS"
    assert open(b["out"], "rb").read() == sentinel  # never modified


def test_output_directory_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(nrun.wsbpo, "read_source_ws_bytes", _Raiser())
    b = _write_files(tmp_path)
    os.mkdir(b["out"])
    rc = nrun.main(_argv(b))
    assert rc == nrun.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == "WS_BOUND_PLAN_REVIEW_OUTPUT_EXISTS"


def test_dangling_symlink_output_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(nrun.wsbpo, "read_source_ws_bytes", _Raiser())
    b = _write_files(tmp_path)
    try:
        os.symlink(str(tmp_path / "missing_target.json"), b["out"])
    except (OSError, NotImplementedError, AttributeError) as exc:
        pytest.skip(f"symlink not permitted: {exc}")
    rc = nrun.main(_argv(b))
    assert rc == nrun.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == "WS_BOUND_PLAN_REVIEW_OUTPUT_EXISTS"


# ===========================================================================
# Race-safe publication
# ===========================================================================

def test_publication_race_no_clobber(tmp_path, monkeypatch, capsys):
    b = _write_files(tmp_path)
    sentinel = b'{"sentinel": "race"}'
    real_link = os.link

    def _racing_link(src, dst, *a, **k):
        if not os.path.lexists(dst):
            with open(dst, "wb") as fh:
                fh.write(sentinel)
        return real_link(src, dst, *a, **k)

    monkeypatch.setattr(nrun.wsbpo.os, "link", _racing_link)
    rc = nrun.main(_argv(b))
    assert rc == nrun.EXIT_INPUT_FAILURE
    assert json.loads(capsys.readouterr().out)["status"] == "WS_BOUND_PLAN_REVIEW_OUTPUT_FAILED"
    assert open(b["out"], "rb").read() == sentinel  # race destination never overwritten
    assert not any(p.suffix == ".tmp" for p in tmp_path.iterdir())


def test_success_leaves_no_temp(tmp_path):
    b = _write_files(tmp_path)
    assert nrun.main(_argv(b)) == nrun.EXIT_OK
    assert not any(p.suffix == ".tmp" for p in tmp_path.iterdir())


# ===========================================================================
# Default / CH2 compatibility
# ===========================================================================

def test_default_path_unchanged(tmp_path, monkeypatch, capsys):
    ns = nrun.build_parser().parse_args(["--pilot-id", "P", "--date", cg.DATE])
    assert ns.ws_bound_plan_review_only is False

    review_spy = _Raiser()
    monkeypatch.setattr(nrun, "_run_ws_bound_plan_review_only", review_spy)

    class _NotRunning:
        def __init__(self, *a, **k):
            pass

        def read_state(self):
            return None

    monkeypatch.setattr(nrun.rd, "PilotStateStore", _NotRunning)
    rc = nrun.main(["--pilot-id", "P", "--date", cg.DATE, "--test-output-root", str(tmp_path)])
    assert rc == nrun.EXIT_BLOCKED
    assert review_spy.n == 0
    assert json.loads(capsys.readouterr().out)["status"] == nrun.nx.DAY_NOT_RUNNING


def test_ch2_plan_only_not_routed_to_review(tmp_path, monkeypatch):
    review_spy = _Raiser()
    ch2_spy = {"n": 0}
    monkeypatch.setattr(nrun, "_run_ws_bound_plan_review_only", review_spy)

    def _ch2(args, output_root):
        ch2_spy["n"] += 1
        return nrun.EXIT_OK

    monkeypatch.setattr(nrun, "_run_ws_bound_plan_only", _ch2)
    rc = nrun.main(["--pilot-id", "P", "--date", cg.DATE, "--ws-bound-plan-only",
                    "--ws-ticker-evidence-json", "x", "--ws-bound-plan-output-json", "y"])
    assert rc == nrun.EXIT_OK
    assert ch2_spy["n"] == 1 and review_spy.n == 0


def test_send_orders_alone_not_routed_to_review(tmp_path, monkeypatch):
    review_spy = _Raiser()
    monkeypatch.setattr(nrun, "_run_ws_bound_plan_review_only", review_spy)

    class _NotRunning:
        def __init__(self, *a, **k):
            pass

        def read_state(self):
            return None

    monkeypatch.setattr(nrun.rd, "PilotStateStore", _NotRunning)
    rc = nrun.main(["--pilot-id", "P", "--date", cg.DATE, "--send-orders-to-demo",
                    "--test-output-root", str(tmp_path)])
    assert rc == nrun.EXIT_BLOCKED  # DAY_NOT_RUNNING (fail-closed), review not entered
    assert review_spy.n == 0
