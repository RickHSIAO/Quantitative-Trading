"""TASK-014CH3C1 -- trusted CH3 review anchor-bundle builder.

Validates `src/demo_strategy_native_ws_review_anchor_bundle.py` (pure core) and
`scripts/build_demo_strategy_ws_review_anchor_bundle.py` (CLI): build a versioned anchor
manifest from an externally-pinned CH2 PASS summary + exact wrapper/source bytes + an
independent 50-symbol source, and prove the produced manifest is accepted by the CH3B1
pure review core. Offline temp fixtures only.
"""
from __future__ import annotations

import importlib.util
import json
import os
import time

import pytest

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_native_ws_price_binding as wb
from src import demo_strategy_native_ws_bound_plan_only as wsbpo
from src import demo_strategy_native_ws_bound_plan_review as wsbpr
from src import demo_strategy_native_ws_review_anchor_bundle as bundle

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

_CG = os.path.join(_HERE, "test_demo_strategy_native_ws_price_binding_cg.py")
_spec = importlib.util.spec_from_file_location("_cg_helpers_ch3c1", _CG)
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)

_SCRIPT = os.path.join(_ROOT, "scripts", "build_demo_strategy_ws_review_anchor_bundle.py")
_sspec = importlib.util.spec_from_file_location("nbuild_ch3c1", _SCRIPT)
nbuild = importlib.util.module_from_spec(_sspec)
_sspec.loader.exec_module(nbuild)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _signed_plan(rest_price="100.0"):
    plan = cg.build_plan(rest_price=rest_price)
    for tp in plan["planner"]["target_positions"]:
        if str(tp["side"]).strip().lower() == "short":
            tp["target_notional"] = "-200"
    return plan


def _make_inputs(now=None):
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
    summary = {
        "status": wsbpo.WS_BOUND_PLAN_ONLY_PASS, "mode": "WS_BOUND_PLAN_ONLY",
        "canonical_bound_plan_fingerprint":
            wrapper["canonical_bound_plan"]["canonical_bound_plan_fingerprint"],
        "source_ws_artifact_sha256": source_sha,
        "source_ws_artifact_fingerprint": ws._fingerprint(
            {k: v for k, v in ws_art.items() if k != "artifact_fingerprint"}),
        "original_plan_fingerprint": wb._fingerprint(plan),
        "binding_epoch_ns": epoch, "freshness_threshold_ms": threshold,
    }
    summary_bytes = json.dumps(summary).encode("utf-8")
    summary_sha = wb.compute_file_sha256(summary_bytes)
    symbols = list(cg.STRATEGY_50)
    symbols_bytes = json.dumps(symbols).encode("utf-8")
    symbols_sha = wb.compute_file_sha256(symbols_bytes)
    return dict(now=now, ws_art=ws_art, source_bytes=source_bytes, source_sha=source_sha,
                plan=plan, epoch=epoch, threshold=threshold, wrapper=wrapper,
                wrapper_bytes=wrapper_bytes, summary=summary, summary_bytes=summary_bytes,
                summary_sha=summary_sha, symbols=symbols, symbols_bytes=symbols_bytes,
                symbols_sha=symbols_sha)


def _build(i, **over):
    kw = dict(
        ch2_summary_bytes=i["summary_bytes"], expected_ch2_summary_sha256=i["summary_sha"],
        wrapper_artifact_bytes=i["wrapper_bytes"], source_ws_artifact_bytes=i["source_bytes"],
        expected_strategy_symbols_bytes=i["symbols_bytes"],
        expected_strategy_symbols_sha256=i["symbols_sha"], run_date=cg.DATE)
    kw.update(over)
    return bundle.build_ws_review_anchor_bundle(**kw)


def _summary_with(i, **over):
    s = dict(i["summary"])
    s.update(over)
    raw = json.dumps(s).encode("utf-8")
    return raw, wb.compute_file_sha256(raw)


def _symbols_with(symbols):
    raw = json.dumps(symbols).encode("utf-8")
    return raw, wb.compute_file_sha256(raw)


# ===========================================================================
# Pure core -- happy path + CH3B1 compatibility
# ===========================================================================

def test_valid_build_passes():
    r = _build(_make_inputs())
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_PASS
    assert r.manifest is not None and r.manifest_bytes is not None
    assert r.manifest_sha256 == wb.compute_file_sha256(r.manifest_bytes)
    assert r.action_count == 50 and r.long_count == 25 and r.short_count == 25
    assert r.execution_readiness is False and r.pilot_advanced is False
    # No wrapper / canonical Plan embedded.
    assert "canonical_bound_plan" not in r.manifest and "planner" not in r.manifest


def test_produced_manifest_accepted_by_ch3b1():
    i = _make_inputs()
    r = _build(i)
    rev = wsbpr.build_ws_bound_plan_review(
        anchor_manifest_bytes=r.manifest_bytes,
        expected_anchor_manifest_sha256=r.manifest_sha256,
        wrapper_artifact_bytes=i["wrapper_bytes"],
        source_ws_artifact_bytes=i["source_bytes"])
    assert rev.status == wsbpr.WS_BOUND_PLAN_REVIEW_PASS
    assert rev.binding_time_freshness_verified is True
    assert rev.current_market_freshness_status == wsbpr.CURRENT_MARKET_FRESHNESS_NOT_EVALUATED
    assert rev.offline_projected_margin_review_complete is False
    assert rev.account_margin_feasibility_status == wsbpr.ACCOUNT_MARGIN_FEASIBILITY_UNAVAILABLE
    assert rev.execution_readiness is False


def test_manifest_has_valid_logical_fingerprint():
    r = _build(_make_inputs())
    m = r.manifest
    assert m["manifest_fingerprint"] == ws._fingerprint(
        {k: v for k, v in m.items() if k != "manifest_fingerprint"})


# ===========================================================================
# Pure core -- failure cases
# ===========================================================================

def test_noncanonical_summary_sha_fails():
    r = _build(_make_inputs(), expected_ch2_summary_sha256="nope")
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID
    assert r.manifest is None


def test_wrong_summary_sha_fails():
    r = _build(_make_inputs(), expected_ch2_summary_sha256="sha256:" + "0" * 64)
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_SUMMARY_MISMATCH


def test_malformed_summary_fails():
    raw = b"{not json"
    r = _build(_make_inputs(), ch2_summary_bytes=raw,
               expected_ch2_summary_sha256=wb.compute_file_sha256(raw))
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID


def test_summary_status_not_pass_fails():
    i = _make_inputs()
    raw, sha = _summary_with(i, status="SOMETHING_ELSE")
    r = _build(i, ch2_summary_bytes=raw, expected_ch2_summary_sha256=sha)
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_SUMMARY_MISMATCH


def test_missing_summary_anchor_fails():
    i = _make_inputs()
    s = dict(i["summary"])
    s.pop("binding_epoch_ns")
    raw = json.dumps(s).encode("utf-8")
    r = _build(i, ch2_summary_bytes=raw, expected_ch2_summary_sha256=wb.compute_file_sha256(raw))
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID


def test_source_sha_differs_from_summary_fails():
    i = _make_inputs()
    raw, sha = _summary_with(i, source_ws_artifact_sha256="sha256:" + "1" * 64)
    r = _build(i, ch2_summary_bytes=raw, expected_ch2_summary_sha256=sha)
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_SOURCE_MISMATCH


def test_source_fingerprint_differs_from_summary_fails():
    i = _make_inputs()
    raw, sha = _summary_with(i, source_ws_artifact_fingerprint="sha256:" + "2" * 64)
    r = _build(i, ch2_summary_bytes=raw, expected_ch2_summary_sha256=sha)
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_SOURCE_MISMATCH


def test_canonical_fingerprint_differs_fails():
    i = _make_inputs()
    raw, sha = _summary_with(i, canonical_bound_plan_fingerprint="sha256:" + "3" * 64)
    r = _build(i, ch2_summary_bytes=raw, expected_ch2_summary_sha256=sha)
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_CANONICAL_MISMATCH


def test_original_plan_fingerprint_differs_fails():
    i = _make_inputs()
    raw, sha = _summary_with(i, original_plan_fingerprint="sha256:" + "4" * 64)
    r = _build(i, ch2_summary_bytes=raw, expected_ch2_summary_sha256=sha)
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_CONSUMER_FAILED


def test_binding_epoch_differs_fails():
    i = _make_inputs()
    raw, sha = _summary_with(i, binding_epoch_ns=i["epoch"] + 5_000_000)
    r = _build(i, ch2_summary_bytes=raw, expected_ch2_summary_sha256=sha)
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_CONSUMER_FAILED


def test_threshold_over_max_fails():
    i = _make_inputs()
    raw, sha = _summary_with(i, freshness_threshold_ms=bundle.STRICT_MAX_FRESHNESS_THRESHOLD_MS + 1)
    r = _build(i, ch2_summary_bytes=raw, expected_ch2_summary_sha256=sha)
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID


def test_date_mismatch_fails():
    r = _build(_make_inputs(), run_date="2099-01-01")
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_CONSUMER_FAILED


def test_invalid_run_date_fails():
    r = _build(_make_inputs(), run_date="2026-13-40")
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID


def test_invalid_wrapper_bytes_fails():
    r = _build(_make_inputs(), wrapper_artifact_bytes=b"[1,2,3]")
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID


def test_invalid_source_bytes_fails():
    i = _make_inputs()
    # Non-object source bytes -> parse fails (INPUT_INVALID) before the sha comparison.
    r = _build(i, source_ws_artifact_bytes=b"{bad")
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID


def test_symbols_wrong_sha_fails():
    i = _make_inputs()
    r = _build(i, expected_strategy_symbols_sha256="sha256:" + "5" * 64)
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_SYMBOL_SOURCE_INVALID


def test_symbols_not_normalized_fails():
    i = _make_inputs()
    syms = list(cg.STRATEGY_50)
    syms[0] = syms[0].lower()
    raw, sha = _symbols_with(syms)
    r = _build(i, expected_strategy_symbols_bytes=raw, expected_strategy_symbols_sha256=sha)
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_SYMBOL_SOURCE_INVALID


def test_symbols_not_fifty_fails():
    i = _make_inputs()
    raw, sha = _symbols_with(list(cg.STRATEGY_50)[:-1])
    r = _build(i, expected_strategy_symbols_bytes=raw, expected_strategy_symbols_sha256=sha)
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_SYMBOL_SOURCE_INVALID


def test_duplicate_symbols_fails():
    i = _make_inputs()
    syms = list(cg.STRATEGY_50)
    syms[1] = syms[0]
    raw, sha = _symbols_with(syms)
    r = _build(i, expected_strategy_symbols_bytes=raw, expected_strategy_symbols_sha256=sha)
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_SYMBOL_SOURCE_INVALID


def test_wrong_symbol_set_fails_at_consumer():
    # 50 unique but a different set than the wrapper -> CH1 symbol-set mismatch.
    i = _make_inputs()
    other = [f"OTHER{n:02d}USDT" for n in range(50)]
    raw, sha = _symbols_with(other)
    r = _build(i, expected_strategy_symbols_bytes=raw, expected_strategy_symbols_sha256=sha)
    assert r.status == bundle.WS_REVIEW_ANCHOR_BUNDLE_CONSUMER_FAILED


# ===========================================================================
# CLI builder
# ===========================================================================

def _write_inputs(tmp_path):
    i = _make_inputs()
    p = {
        "summary": str(tmp_path / "ch2_summary.json"),
        "wrapper": str(tmp_path / "wrapper.json"),
        "source": str(tmp_path / "source.json"),
        "symbols": str(tmp_path / "symbols.json"),
        "out": str(tmp_path / "anchor_manifest.json"),
    }
    open(p["summary"], "wb").write(i["summary_bytes"])
    open(p["wrapper"], "wb").write(i["wrapper_bytes"])
    open(p["source"], "wb").write(i["source_bytes"])
    open(p["symbols"], "wb").write(i["symbols_bytes"])
    p["summary_sha"] = i["summary_sha"]
    p["symbols_sha"] = i["symbols_sha"]
    p["_inputs"] = i
    return p


def _argv(p, **over):
    argv = ["--ch2-summary-json", p["summary"], "--ch2-summary-sha256", p["summary_sha"],
            "--ws-bound-plan-wrapper-json", p["wrapper"], "--ws-ticker-evidence-json", p["source"],
            "--expected-strategy-symbols-json", p["symbols"],
            "--expected-strategy-symbols-sha256", p["symbols_sha"],
            "--output-anchor-manifest-json", p["out"], "--date", over.get("date", cg.DATE)]
    return argv


def test_cli_valid_writes_manifest(tmp_path, capsys):
    p = _write_inputs(tmp_path)
    rc = nbuild.main(_argv(p))
    assert rc == nbuild.EXIT_OK
    assert os.path.exists(p["out"])
    assert not any(x.suffix == ".tmp" for x in tmp_path.iterdir())
    s = json.loads(capsys.readouterr().out)
    assert s["status"] == bundle.WS_REVIEW_ANCHOR_BUNDLE_PASS
    assert s["manifest_written"] is True
    # printed manifest SHA equals the literal output bytes.
    assert s["output_anchor_manifest_sha256"] == wb.compute_file_sha256(open(p["out"], "rb").read())
    assert s["execution_readiness"] is False and s["rest_fallback_used"] is False


def test_cli_output_accepted_by_review(tmp_path):
    p = _write_inputs(tmp_path)
    rc = nbuild.main(_argv(p))
    assert rc == nbuild.EXIT_OK
    manifest_bytes = open(p["out"], "rb").read()
    rev = wsbpr.build_ws_bound_plan_review(
        anchor_manifest_bytes=manifest_bytes,
        expected_anchor_manifest_sha256=wb.compute_file_sha256(manifest_bytes),
        wrapper_artifact_bytes=p["_inputs"]["wrapper_bytes"],
        source_ws_artifact_bytes=p["_inputs"]["source_bytes"])
    assert rev.status == wsbpr.WS_BOUND_PLAN_REVIEW_PASS


def test_cli_noncanonical_summary_sha_fails(tmp_path, capsys):
    p = _write_inputs(tmp_path)
    argv = _argv(p)
    argv[argv.index("--ch2-summary-sha256") + 1] = "not-canonical"
    rc = nbuild.main(argv)
    assert rc == nbuild.EXIT_INVALID
    assert not os.path.exists(p["out"])
    assert json.loads(capsys.readouterr().out)["status"] == bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID


def test_cli_output_equals_input_rejected(tmp_path, capsys):
    p = _write_inputs(tmp_path)
    argv = _argv(p)
    argv[argv.index("--output-anchor-manifest-json") + 1] = p["wrapper"]
    before = open(p["wrapper"], "rb").read()
    rc = nbuild.main(argv)
    assert rc == nbuild.EXIT_INVALID
    assert open(p["wrapper"], "rb").read() == before  # input untouched
    assert json.loads(capsys.readouterr().out)["status"] == bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID


def test_cli_relative_abs_alias_rejected(tmp_path, capsys):
    p = _write_inputs(tmp_path)
    argv = _argv(p)
    alias = os.path.join(str(tmp_path), "sub", "..", "wrapper.json")  # == wrapper
    argv[argv.index("--output-anchor-manifest-json") + 1] = alias
    rc = nbuild.main(argv)
    assert rc == nbuild.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID


def test_cli_preexisting_output_rejected(tmp_path, capsys):
    p = _write_inputs(tmp_path)
    sentinel = b'{"sentinel": true}'
    open(p["out"], "wb").write(sentinel)
    rc = nbuild.main(_argv(p))
    assert rc == nbuild.EXIT_INVALID
    assert open(p["out"], "rb").read() == sentinel
    assert json.loads(capsys.readouterr().out)["status"] == bundle.WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_EXISTS


def test_cli_output_directory_rejected(tmp_path, capsys):
    p = _write_inputs(tmp_path)
    os.mkdir(p["out"])
    rc = nbuild.main(_argv(p))
    assert rc == nbuild.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == bundle.WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_EXISTS


def test_cli_dangling_symlink_output_rejected(tmp_path, capsys):
    p = _write_inputs(tmp_path)
    try:
        os.symlink(str(tmp_path / "missing.json"), p["out"])
    except (OSError, NotImplementedError, AttributeError) as exc:
        pytest.skip(f"symlink not permitted: {exc}")
    rc = nbuild.main(_argv(p))
    assert rc == nbuild.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == bundle.WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_EXISTS


def test_cli_input_read_failure(tmp_path, capsys):
    p = _write_inputs(tmp_path)
    os.remove(p["wrapper"])
    rc = nbuild.main(_argv(p))
    assert rc == nbuild.EXIT_INPUT_FAILURE
    assert not os.path.exists(p["out"])
    assert json.loads(capsys.readouterr().out)["status"] == \
        bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_READ_FAILED


def test_cli_validation_failure_no_manifest(tmp_path, capsys):
    p = _write_inputs(tmp_path)
    argv = _argv(p, date="2099-01-01")
    rc = nbuild.main(argv)
    assert rc == nbuild.EXIT_BLOCKED
    assert not os.path.exists(p["out"])
    assert not any(x.suffix == ".tmp" for x in tmp_path.iterdir())


def test_cli_publication_race_no_clobber(tmp_path, monkeypatch, capsys):
    p = _write_inputs(tmp_path)
    sentinel = b'{"sentinel": "race"}'
    real_link = os.link

    def _racing_link(src, dst, *a, **k):
        if not os.path.lexists(dst):
            with open(dst, "wb") as fh:
                fh.write(sentinel)
        return real_link(src, dst, *a, **k)

    monkeypatch.setattr(nbuild.wsbpo.os, "link", _racing_link)
    rc = nbuild.main(_argv(p))
    assert rc == nbuild.EXIT_INPUT_FAILURE
    assert json.loads(capsys.readouterr().out)["status"] == bundle.WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_FAILED
    assert open(p["out"], "rb").read() == sentinel
    assert not any(x.suffix == ".tmp" for x in tmp_path.iterdir())


# ===========================================================================
# Static safety
# ===========================================================================

def test_builder_modules_have_no_forbidden_imports():
    import ast
    for mod in (bundle, nbuild):
        src_text = open(mod.__file__, encoding="utf-8").read()
        tree = ast.parse(src_text)
        tops: set[str] = set()
        leaves: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    tops.add(n.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                tops.add((node.module or "").split(".")[0])
                if (node.module or "") == "src":
                    for n in node.names:
                        leaves.add(n.name)
        assert not (tops & {"socket", "requests", "urllib", "http", "asyncio", "ssl",
                            "websocket", "websockets"}), (mod.__name__, tops)
        assert not (leaves & {
            "demo_strategy_pilot_readiness", "demo_strategy_pilot_execution_gate",
            "demo_strategy_pilot_native_execution", "demo_strategy_pilot_native_reporting",
            "demo_strategy_pilot_lifecycle", "demo_strategy_pilot_store"}), (mod.__name__, leaves)
        for tok in ("execute_daily_native", "evaluate_execution_gate", "PilotStateStore",
                    "advance_successful_day", "run_demo_strategy_pilot_native_daily",
                    "api-demo.bybit", "wss://", "https://", "/v5/", ".now(", "os.replace"):
            assert tok not in src_text, (mod.__name__, tok)
