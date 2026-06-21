"""Tests for TASK-014BS primary Forward Record source wiring.

All tests are strictly offline: temporary source fixtures, injected positions
reader (no parquet engine needed), zero HTTP, no orders.
"""

from __future__ import annotations

import argparse
import importlib
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import demo_strategy_pilot_daily_runner as rr
from src import demo_strategy_pilot_forward_source as fs
from src.demo_strategy_pilot_reporting import PilotConfig
from src.demo_strategy_pilot_store import PilotStore
from decimal import Decimal

cli = importlib.import_module("scripts.run_demo_strategy_pilot_daily")

DATE = "20260518"
DATE_ISO = "2026-05-18"


# ---------------------------------------------------------------------------
# Fixture source builder
# ---------------------------------------------------------------------------


VALIDATION_HEADER = ["date", "day_number", "runner_status", "data_source", "safety_scan",
                     "dry_run", "signal_count", "n_longs", "n_shorts"]


def make_source(tmp_path, *, date=DATE, strategy="prev3y_crypto_combined_paper_safe_variant",
                latest_date=None, n_longs=2, n_shorts=1, signal_count=None, positions_rows=None,
                runner_status="REVIEW_READY", safety="PASS", dry_run=True,
                data_source="cache_fallback", variant="combined_paper_safe_variant",
                write_positions=True, stats_date=None, pnl_date=None, write_summary=True,
                summary_text=None):
    root = tmp_path / "fwd"
    pdir = root / "prev3y_crypto"
    pdir.mkdir(parents=True, exist_ok=True)
    (root / "dashboard").mkdir(parents=True, exist_ok=True)
    latest_date = latest_date or date
    signal_count = (n_longs + n_shorts) if signal_count is None else signal_count
    positions_rows = signal_count if positions_rows is None else positions_rows

    if write_summary:
        if summary_text is not None:
            (pdir / "forward_summary.json").write_text(summary_text, encoding="utf-8")
        else:
            (pdir / "forward_summary.json").write_text(
                json.dumps({"strategy": strategy, "latest_date": latest_date}), encoding="utf-8")
    (pdir / f"{date}_forward_stats.json").write_text(
        json.dumps({"date": stats_date or date, "dry_run": dry_run, "status": "DRY_RUN",
                    "variant": variant}), encoding="utf-8")
    (pdir / f"{date}_pnl.json").write_text(
        json.dumps({"date": pnl_date or date, "n_longs": n_longs, "n_shorts": n_shorts,
                    "data_source": data_source, "dry_run": dry_run,
                    "reproducibility": {"positions_rows": positions_rows}}), encoding="utf-8")
    if write_positions:
        (pdir / f"{date}_positions.parquet").write_bytes(b"PAR1_fake_positions_bytes_%b" % date.encode())

    with open(root / "dashboard" / "validation_30d.csv", "w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(VALIDATION_HEADER) + "\n")
        fh.write(",".join([date, "0", runner_status, data_source, safety,
                           "True" if dry_run else "False", str(signal_count),
                           str(n_longs), str(n_shorts)]) + "\n")
    return root


def reader_for(n_longs=2, n_shorts=1, symbols_long=None, symbols_short=None, override=None):
    if override is not None:
        return lambda path: list(override)

    def _reader(path):
        rows = []
        longs = symbols_long or [f"BYBIT:LONG{i}USDT.P" for i in range(n_longs)]
        shorts = symbols_short or [f"BYBIT:SHORT{i}USDT.P" for i in range(n_shorts)]
        for s in longs:
            rows.append({"symbol": s, "side": "long", "weight": 0.02})
        for s in shorts:
            rows.append({"symbol": s, "side": "short", "weight": -0.02})
        return rows
    return _reader


def load(tmp_path, *, run_date=DATE_ISO, reader=None, **kw):
    root = make_source(tmp_path, **kw)
    if reader is None:
        reader = reader_for(n_longs=kw.get("n_longs", 2), n_shorts=kw.get("n_shorts", 1))
    return fs.load_primary_forward_strategy_result(
        run_date=run_date, repo_root=tmp_path, forward_source_root=str(root),
        positions_reader=reader)


# ---------------------------------------------------------------------------
# 1-6. Identity / acceptance
# ---------------------------------------------------------------------------


def test_task_identity():
    assert fs.TASK_ID == "TASK-014BS"
    assert fs.PRIMARY_RUN_KEY == "prev3y_crypto"
    assert fs.EXPECTED_STRATEGY_NAME == "prev3y_crypto_combined_paper_safe_variant"


def test_primary_run_key_accepted(tmp_path):
    res = load(tmp_path)
    assert res.run_key == "prev3y_crypto"


def test_exact_strategy_identifier_accepted(tmp_path):
    res = load(tmp_path)
    assert res.strategy_name == "prev3y_crypto_combined_paper_safe_variant"


def test_shadow_run_rejected(tmp_path):
    with pytest.raises(fs.ForwardSourceError):
        load(tmp_path, strategy="prev3y_crypto_shadow_a_roll12")


def test_strategy_mismatch_rejected(tmp_path):
    with pytest.raises(fs.ForwardSourceError):
        load(tmp_path, strategy="some_other_strategy")


def test_missing_summary_rejected(tmp_path):
    with pytest.raises(fs.ForwardSourceError):
        load(tmp_path, write_summary=False)


# ---------------------------------------------------------------------------
# 7-15. Fail-closed conditions
# ---------------------------------------------------------------------------


def test_malformed_summary_rejected(tmp_path):
    with pytest.raises(fs.ForwardSourceError):
        load(tmp_path, summary_text="{not json")


def test_missing_source_date_rejected(tmp_path):
    # Request a date not present in the source artifacts.
    with pytest.raises(fs.ForwardSourceError):
        load(tmp_path, run_date="2026-05-19")


def test_runner_failure_rejected(tmp_path):
    with pytest.raises(fs.ForwardSourceError):
        load(tmp_path, runner_status="FAILED")


def test_safety_scan_failure_rejected(tmp_path):
    with pytest.raises(fs.ForwardSourceError):
        load(tmp_path, safety="FAIL")


def test_unexpected_non_dry_run_source_rejected(tmp_path):
    with pytest.raises(fs.ForwardSourceError):
        load(tmp_path, dry_run=False)


def test_authoritative_zero_signal_day_accepted(tmp_path):
    res = load(tmp_path, n_longs=0, n_shorts=0, reader=reader_for(0, 0))
    assert res.signal_count == 0 and res.normalized_signals == ()


def test_nonzero_signal_count_without_rows_rejected(tmp_path):
    # signal_count=3 but reader returns 0 rows.
    with pytest.raises(fs.ForwardSourceError):
        load(tmp_path, n_longs=2, n_shorts=1, reader=reader_for(0, 0))


def test_signal_count_mismatch_rejected(tmp_path):
    # validation signal_count (3) != positions_rows (5).
    with pytest.raises(fs.ForwardSourceError):
        load(tmp_path, n_longs=2, n_shorts=1, positions_rows=5)


def test_unsupported_direction_rejected(tmp_path):
    bad = [{"symbol": "BYBIT:XUSDT.P", "side": "flat", "weight": 0.0},
           {"symbol": "BYBIT:YUSDT.P", "side": "long", "weight": 0.02},
           {"symbol": "BYBIT:ZUSDT.P", "side": "short", "weight": -0.02}]
    with pytest.raises(fs.ForwardSourceError):
        load(tmp_path, n_longs=2, n_shorts=1, reader=reader_for(override=bad))


# ---------------------------------------------------------------------------
# 16-22. Normalization / protected / hashing / credentials
# ---------------------------------------------------------------------------


def test_deterministic_signal_normalization(tmp_path):
    r1 = load(tmp_path / "a")
    r2 = load(tmp_path / "b")
    assert [s["symbol"] for s in r1.normalized_signals] == [s["symbol"] for s in r2.normalized_signals]
    assert r1.source_fingerprint == r2.source_fingerprint


def test_protected_symbol_preserved_but_blocked(tmp_path):
    rows = [{"symbol": "BYBIT:ENAUSDT.P", "side": "long", "weight": 0.02},
            {"symbol": "BYBIT:BTCUSDT.P", "side": "long", "weight": 0.02},
            {"symbol": "BYBIT:ETHUSDT.P", "side": "short", "weight": -0.02}]
    res = load(tmp_path, n_longs=2, n_shorts=1, reader=reader_for(override=rows))
    ena = [s for s in res.normalized_signals if s["symbol"] == "ENAUSDT"][0]
    assert ena["eligibility_hint"] == "PROTECTED_SYMBOL_BLOCKED"
    # Runner classification confirms it is blocked and not executable.
    actions = rr.classify_actions(rr.normalize_signals(res.to_strategy_result()))
    ena_action = [a for a in actions if a["symbol"] == "ENAUSDT"][0]
    assert ena_action["eligibility"] == rr.PROTECTED_BLOCKED and ena_action["executable"] is False


def test_duplicate_conflicting_signals_rejected(tmp_path):
    rows = [{"symbol": "BYBIT:BTCUSDT.P", "side": "long", "weight": 0.02},
            {"symbol": "BYBIT:BTCUSDT.P", "side": "short", "weight": -0.02},
            {"symbol": "BYBIT:ETHUSDT.P", "side": "short", "weight": -0.02}]
    with pytest.raises(fs.ForwardSourceError):
        load(tmp_path, n_longs=2, n_shorts=1, reader=reader_for(override=rows))


def test_source_paths_repository_relative(tmp_path):
    res = load(tmp_path)
    for a in res.source_artifacts:
        assert not a.path.startswith("/") and ":" not in a.path
        assert a.path.startswith("fwd/")


def test_artifact_sha256_deterministic_and_size_recorded(tmp_path):
    res = load(tmp_path)
    by_role = {a.role: a for a in res.source_artifacts}
    assert by_role["pnl"].sha256.startswith("sha256:")
    assert by_role["pnl"].size > 0
    assert by_role["positions"].size == len(
        (tmp_path / "fwd" / "prev3y_crypto" / f"{DATE}_positions.parquet").read_bytes())


def test_credential_files_never_read():
    src = pathlib.Path(fs.__file__).read_text(encoding="utf-8")
    assert ".env" not in src and "getenv" not in src and "environ" not in src
    assert "NOTION_TOKEN" not in src and "WEBHOOK" not in src


# ---------------------------------------------------------------------------
# 23-28. CLI no-fixture / fixture / plan
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self):
        self._sr = {"data_date": DATE_ISO, "data_status": "cache_fallback",
                    "signals": [{"symbol": "BTCUSDT", "side": "long"}],
                    "forward_summary": {"strategy": fs.EXPECTED_STRATEGY_NAME},
                    "run_key": "prev3y_crypto", "market_data_date": DATE_ISO,
                    "source_metadata": {"run_key": "prev3y_crypto", "source_fingerprint": "abc"}}

    def to_strategy_result(self):
        return self._sr


def test_no_fixture_plan_uses_real_source_adapter(tmp_path, monkeypatch, capsys):
    called = {}

    def fake_loader(*, run_date, repo_root, forward_source_root=None):
        called["run_date"] = run_date
        return _FakeResult()

    monkeypatch.setattr(cli.fs, "load_primary_forward_strategy_result", fake_loader)
    rc = cli.main(["--mode", "plan", "--pilot-id", "P1", "--date", DATE_ISO,
                   "--start-date", DATE_ISO, "--json-only"])
    payload = json.loads(capsys.readouterr().out)
    assert called["run_date"] == DATE_ISO
    assert payload["status"] == rr.STATUS_PLAN_ONLY and rc == rr.EXIT_OK


def test_fixture_path_remains_supported(tmp_path, capsys):
    fixture = tmp_path / "sig.json"
    fixture.write_text(json.dumps({"data_date": DATE_ISO, "data_status": "OK",
                                   "signals": [{"symbol": "SOLUSDT", "side": "long"}]}), encoding="utf-8")
    rc = cli.main(["--mode", "plan", "--pilot-id", "P1", "--date", DATE_ISO,
                   "--fixture", str(fixture), "--json-only"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == rr.STATUS_PLAN_ONLY and rc == rr.EXIT_OK


def test_plan_creates_no_permanent_state(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.fs, "load_primary_forward_strategy_result",
                        lambda **k: _FakeResult())
    cli.main(["--mode", "plan", "--pilot-id", "P1", "--date", DATE_ISO, "--json-only"])
    capsys.readouterr()
    # Default canonical pilot dir must not be created for P1 by a plan.
    assert not (ROOT / "outputs" / "demo_trading" / "pilot" / "P1").exists()


def test_successful_no_fixture_plan_returns_plan_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.fs, "load_primary_forward_strategy_result", lambda **k: _FakeResult())
    rc = cli.main(["--mode", "plan", "--pilot-id", "P1", "--date", DATE_ISO, "--json-only"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == rr.STATUS_PLAN_ONLY and rc == 0


def test_plan_contains_exact_strategy_identifier(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.fs, "load_primary_forward_strategy_result", lambda **k: _FakeResult())
    cli.main(["--mode", "plan", "--pilot-id", "P1", "--date", DATE_ISO, "--json-only"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["plan"]["strategy_name"] == "prev3y_crypto_combined_paper_safe_variant"


def test_plan_keeps_execution_unauthorized(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.fs, "load_primary_forward_strategy_result", lambda **k: _FakeResult())
    cli.main(["--mode", "plan", "--pilot-id", "P1", "--date", DATE_ISO, "--json-only"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["order_execution_authorized"] is False
    assert payload["reason_execution_not_authorized"] == "TASK-014BR_IS_DRY_RUN_REPORTING_WIRING_ONLY"


# ---------------------------------------------------------------------------
# 29-37. Dry-run / idempotency / conflict / reconcile (runner-level)
# ---------------------------------------------------------------------------


def _cfg():
    return PilotConfig(pilot_id="P1", start_date=DATE_ISO, strategy_name=rr.EXPECTED_STRATEGY_NAME,
                       initial_equity_usdt=Decimal("10000"), notion_enabled=True, discord_enabled=True)


def _sr(tmp_path):
    return load(tmp_path).to_strategy_result()


def test_dry_run_creates_one_daily_record_and_no_trade(tmp_path):
    out = tmp_path / "out"
    sr = _sr(tmp_path / "src")
    result = rr.run_daily(mode="dry_run", pilot_id="P1", date=DATE_ISO, config=_cfg(),
                          strategy_result=sr, output_root=str(out), snapshot_date="20260518")
    store = PilotStore("P1", str(out))
    assert len(store.read_daily()) == 1
    assert store.read_trades() == []
    assert result.daily_record["order_count"] == 0
    assert result.daily_record["filled_count"] == 0
    assert result.daily_record["closed_trade_count"] == 0


def test_dry_run_excel_notion_discord_previews(tmp_path):
    out = tmp_path / "out"
    sr = _sr(tmp_path / "src")
    rr.run_daily(mode="dry_run", pilot_id="P1", date=DATE_ISO, config=_cfg(),
                 strategy_result=sr, output_root=str(out), snapshot_date="20260518")
    from src import demo_strategy_pilot_daily_journal as jrm
    assert (out / "P1" / "demo_strategy_pilot_results.xlsx").exists()
    j = jrm.DailyRunJournal("P1", DATE_ISO, str(out))
    summary = (j.dir / jrm.DISCORD_SUMMARY_FILENAME).read_text(encoding="utf-8")
    assert "DRY-RUN／尚未授權自動下單" in summary
    assert (j.dir / jrm.NOTION_PAYLOAD_FILENAME).exists()


def test_identical_source_rerun_idempotent(tmp_path):
    out = tmp_path / "out"
    sr = _sr(tmp_path / "src")
    rr.run_daily(mode="dry_run", pilot_id="P1", date=DATE_ISO, config=_cfg(),
                 strategy_result=sr, output_root=str(out), snapshot_date="20260518")
    r2 = rr.run_daily(mode="dry_run", pilot_id="P1", date=DATE_ISO, config=_cfg(),
                      strategy_result=sr, output_root=str(out), snapshot_date="20260518")
    assert r2.status == rr.STATUS_ALREADY_COMMITTED_IDEMPOTENT


def test_changed_source_bytes_cause_plan_conflict_after_commit(tmp_path):
    out = tmp_path / "out"
    sr = _sr(tmp_path / "src1")
    rr.run_daily(mode="dry_run", pilot_id="P1", date=DATE_ISO, config=_cfg(),
                 strategy_result=sr, output_root=str(out), snapshot_date="20260518")
    # Different source (different signals) for the same date.
    sr2 = load(tmp_path / "src2", n_longs=3, n_shorts=2).to_strategy_result()
    r2 = rr.run_daily(mode="dry_run", pilot_id="P1", date=DATE_ISO, config=_cfg(),
                      strategy_result=sr2, output_root=str(out), snapshot_date="20260518")
    assert r2.status == rr.STATUS_DAILY_PLAN_CONFLICT and r2.exit_code == rr.EXIT_CONFLICT


def test_reconcile_does_not_reload_strategy_source(monkeypatch):
    # _load_strategy_result must return None for reconcile WITHOUT calling the adapter.
    def boom(**k):
        raise AssertionError("adapter must not be called in reconcile")
    monkeypatch.setattr(cli.fs, "load_primary_forward_strategy_result", boom)
    args = argparse.Namespace(mode=rr.MODE_RECONCILE, fixture=None, date=DATE_ISO)
    assert cli._load_strategy_result(args, None) is None


# ---------------------------------------------------------------------------
# 38-41. Restrictions / traversal / safety scans
# ---------------------------------------------------------------------------


def test_test_only_source_root_restriction(capsys):
    rc = cli.main(["--mode", "plan", "--date", DATE_ISO, "--forward-source-root", "/var/lib/production"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "SAFETY_REFUSAL" and rc == rr.EXIT_SAFETY


def test_path_traversal_rejected(tmp_path):
    root = make_source(tmp_path)
    with pytest.raises(fs.ForwardSourceError):
        fs.load_primary_forward_strategy_result(run_date="../../etc", repo_root=tmp_path,
                                                forward_source_root=str(root), positions_reader=reader_for())


def test_no_bybit_imports_network_or_order_endpoint():
    src = pathlib.Path(fs.__file__).read_text(encoding="utf-8")
    assert "/v5/order" not in src and "order/create" not in src and "api-demo.bybit.com" not in src
    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith(("import ", "from ")):
            assert "requests" not in s and "executors.bybit" not in s and "pybit" not in s
    assert "BybitExecutor" not in src


def test_no_strategy_parameter_mutation():
    src = pathlib.Path(fs.__file__).read_text(encoding="utf-8")
    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith(("import ", "from ")):
            assert "STRATEGY_PROFILES" not in s and "src.strategies" not in s


# ---------------------------------------------------------------------------
# 42-46. Docs / outputs / untouched
# ---------------------------------------------------------------------------


def test_documentation_updated():
    for rel in ("README.md", "docs/research/commands/NEXT_ACTION.md",
                "docs/research/commands/COMMAND_LOG.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "TASK-014BS" in text


def test_date_semantics_fields_present(tmp_path):
    res = load(tmp_path)
    d = res.to_dict()
    assert d["requested_run_date"] == DATE_ISO
    assert d["forward_record_date"] == DATE_ISO
    assert d["market_data_date"] == DATE_ISO


def test_market_date_mismatch_fails_closed(tmp_path):
    # pnl/stats internal date differs from the filename/requested date.
    with pytest.raises(fs.ForwardSourceError):
        load(tmp_path, pnl_date="20260101")


def test_requested_newer_than_latest_rejected(tmp_path):
    with pytest.raises(fs.ForwardSourceError):
        load(tmp_path, latest_date="20260510", run_date=DATE_ISO)


def test_to_strategy_result_shape(tmp_path):
    sr = load(tmp_path).to_strategy_result()
    assert sr["forward_summary"]["strategy"] == fs.EXPECTED_STRATEGY_NAME
    assert sr["run_key"] == "prev3y_crypto"
    assert "source_metadata" in sr and "source_fingerprint" in sr["source_metadata"]
