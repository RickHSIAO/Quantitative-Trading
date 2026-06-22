"""Tests for TASK-014BW 7-successful-day Demo Pilot readiness foundation.

Fully offline: no real network, no Bybit, no order POSTs, temp roots, presence-
only credential checks via injected env.
"""

from __future__ import annotations

import importlib
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import demo_strategy_pilot_readiness as rd

cli = importlib.import_module("scripts.manage_demo_strategy_pilot")

PILOT = "BYBIT_DEMO_PILOT_7D_202606_V1"
FULL_ENV = {"NOTION_TOKEN": "tok", "NOTION_PILOT_DATABASE_ID": "db",
            "MONITOR_DISCORD_WEBHOOK_URL": "http://hook"}


@pytest.fixture
def fwd_root(tmp_path):
    d = tmp_path / "fwd" / "prev3y_crypto"
    d.mkdir(parents=True)
    (d / "forward_summary.json").write_text(
        json.dumps({"strategy": "prev3y_crypto_combined_paper_safe_variant", "latest_date": "20260518"}),
        encoding="utf-8")
    return str(tmp_path / "fwd")


def readiness(tmp_path, fwd_root, *, env=None, pilot_id=PILOT):
    return rd.run_readiness(pilot_id=pilot_id, env=FULL_ENV if env is None else env,
                            output_root=str(tmp_path / "out"), forward_source_root=fwd_root)


def initialize(tmp_path, fwd_root, *, ack=True, env=None, pilot_id=PILOT):
    return rd.initialize_pilot(pilot_id=pilot_id, acknowledged=ack, env=FULL_ENV if env is None else env,
                               output_root=str(tmp_path / "out"), forward_source_root=fwd_root)


def day(**over):
    base = dict(date="2026-06-22", pilot_date="2026-06-22", source_date="2026-06-22",
                runner_status="COMPLETED")
    base.update(over)
    return rd.DayEvidence(**base)


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------


def test_readiness_succeeds_with_full_presence_config(tmp_path, fwd_root):
    r = readiness(tmp_path, fwd_root)
    assert r["status"] == rd.STATUS_READY
    assert r["ready_for_manual_start_review"] is True
    assert r["blockers"] == []
    assert r["order_execution_authorized"] is False
    assert r["automatic_execution_authorized"] is False
    assert r["live_trading_authorized"] is False
    assert r["network_attempted"] is False
    assert r["bybit_call_count"] == 0 and r["order_post_count"] == 0


def test_missing_notion_token_blocks(tmp_path, fwd_root):
    env = {"NOTION_PILOT_DATABASE_ID": "db", "MONITOR_DISCORD_WEBHOOK_URL": "h"}
    r = readiness(tmp_path, fwd_root, env=env)
    assert r["status"] == rd.STATUS_BLOCKED and "notion_token_present" in r["blockers"]


def test_missing_pilot_database_id_blocks(tmp_path, fwd_root):
    env = {"NOTION_TOKEN": "t", "MONITOR_DISCORD_WEBHOOK_URL": "h"}
    r = readiness(tmp_path, fwd_root, env=env)
    assert r["status"] == rd.STATUS_BLOCKED and "notion_pilot_database_id_present" in r["blockers"]


def test_missing_discord_webhook_blocks(tmp_path, fwd_root):
    env = {"NOTION_TOKEN": "t", "NOTION_PILOT_DATABASE_ID": "db"}
    r = readiness(tmp_path, fwd_root, env=env)
    assert r["status"] == rd.STATUS_BLOCKED and "discord_webhook_present" in r["blockers"]


def test_no_bybit_credentials_required(tmp_path, fwd_root):
    # No Bybit env at all -> readiness still READY (execution unauthorized).
    r = readiness(tmp_path, fwd_root, env=FULL_ENV)
    assert r["status"] == rd.STATUS_READY
    names = [c["name"] for c in r["checks"]]
    assert not any("bybit" in n.lower() for n in names)


def test_bybit_credentials_never_printed_or_used(tmp_path, fwd_root):
    env = dict(FULL_ENV, BYBIT_DEMO_API_KEY="SECRET_KEY", BYBIT_DEMO_API_SECRET="SECRET_SECRET")
    r = readiness(tmp_path, fwd_root, env=env)
    blob = json.dumps(r)
    assert "SECRET_KEY" not in blob and "SECRET_SECRET" not in blob


def test_credentials_values_never_in_output(tmp_path, fwd_root):
    env = {"NOTION_TOKEN": "TOKVALUE", "NOTION_PILOT_DATABASE_ID": "DBVALUE",
           "MONITOR_DISCORD_WEBHOOK_URL": "http://secret-hook"}
    r = readiness(tmp_path, fwd_root, env=env)
    blob = json.dumps(r)
    assert "TOKVALUE" not in blob and "DBVALUE" not in blob and "secret-hook" not in blob


def test_invalid_pilot_id_refused(tmp_path, fwd_root):
    r = readiness(tmp_path, fwd_root, pilot_id="bad id!")
    assert r["status"] == rd.STATUS_INVALID_CONFIGURATION


def test_smoke_pilot_id_refused(tmp_path, fwd_root):
    r = readiness(tmp_path, fwd_root, pilot_id="BYBIT_DEMO_PILOT_BT_SMOKE_202606")
    assert r["status"] == rd.STATUS_INVALID_CONFIGURATION


def test_forward_source_missing_blocks(tmp_path):
    r = rd.run_readiness(pilot_id=PILOT, env=FULL_ENV, output_root=str(tmp_path / "out"),
                         forward_source_root=str(tmp_path / "nope"))
    assert r["status"] == rd.STATUS_BLOCKED
    assert "forward_record_primary_source_available" in r["blockers"]


# ---------------------------------------------------------------------------
# Initialize
# ---------------------------------------------------------------------------


def test_initialize_requires_acknowledgement(tmp_path, fwd_root):
    r = initialize(tmp_path, fwd_root, ack=False)
    assert r["status"] == "REFUSED_NOT_ACKNOWLEDGED"
    assert not (tmp_path / "out" / PILOT / rd.STATE_FILENAME).exists()


def test_initialize_writes_inactive_only(tmp_path, fwd_root):
    r = initialize(tmp_path, fwd_root)
    assert r["status"] == rd.STATUS_INACTIVE and r["lifecycle_state"] == rd.INACTIVE
    state = json.loads((tmp_path / "out" / PILOT / rd.STATE_FILENAME).read_text(encoding="utf-8"))
    assert state["lifecycle_state"] == rd.INACTIVE
    assert state["started_at_utc"] is None and state["completed_at_utc"] is None


def test_initialize_cannot_create_running_or_completed(tmp_path, fwd_root):
    r = initialize(tmp_path, fwd_root)
    assert r["lifecycle_state"] not in (rd.RUNNING, rd.COMPLETED)


def test_idempotent_initialize(tmp_path, fwd_root):
    initialize(tmp_path, fwd_root)
    r2 = initialize(tmp_path, fwd_root)
    assert r2["status"] == "ALREADY_INITIALIZED_IDEMPOTENT"
    # No duplicate event appended (one INITIALIZE event total).
    store = rd.PilotStateStore(PILOT, str(tmp_path / "out"))
    assert store.event_count() == 1


def test_conflicting_initialize_refused(tmp_path, fwd_root, monkeypatch):
    initialize(tmp_path, fwd_root)
    # Force a different configuration fingerprint for the same pilot id.
    monkeypatch.setattr(rd, "configuration_fingerprint", lambda pid: "DIFFERENT_FP")
    r = rd.initialize_pilot(pilot_id=PILOT, acknowledged=True, env=FULL_ENV,
                            output_root=str(tmp_path / "out"), forward_source_root=fwd_root)
    assert r["status"] == rd.STATUS_CONFLICTING_EXISTING_STATE


def test_initialize_blocked_when_readiness_fails(tmp_path, fwd_root):
    env = {"NOTION_PILOT_DATABASE_ID": "db", "MONITOR_DISCORD_WEBHOOK_URL": "h"}  # no token
    r = initialize(tmp_path, fwd_root, env=env)
    assert r["status"] == rd.STATUS_BLOCKED and r["lifecycle_state"] == rd.BLOCKED
    state = json.loads((tmp_path / "out" / PILOT / rd.STATE_FILENAME).read_text(encoding="utf-8"))
    assert "notion_token_present" in state["blocked_reasons"]


def test_state_fingerprint_stable():
    assert rd.configuration_fingerprint(PILOT) == rd.configuration_fingerprint(PILOT)


def test_append_only_event_ledger(tmp_path, fwd_root):
    initialize(tmp_path, fwd_root)
    store = rd.PilotStateStore(PILOT, str(tmp_path / "out"))
    assert store.events_path.exists() and store.event_count() == 1


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def test_status_before_initialize(tmp_path):
    r = rd.pilot_status(pilot_id=PILOT, output_root=str(tmp_path / "out"))
    assert r["status"] == rd.STATUS_NOT_INITIALIZED
    assert r["remaining_successful_days"] == 7 and r["completed_successful_days"] == 0


def test_status_after_initialize(tmp_path, fwd_root):
    initialize(tmp_path, fwd_root)
    r = rd.pilot_status(pilot_id=PILOT, output_root=str(tmp_path / "out"))
    assert r["lifecycle_state"] == rd.INACTIVE


def test_remaining_days_seven_initially(tmp_path, fwd_root):
    r = initialize(tmp_path, fwd_root)
    assert r["state"]["remaining_successful_days"] == 7
    assert r["state"]["target_successful_days"] == 7
    assert r["state"]["completed_successful_days"] == 0


# ---------------------------------------------------------------------------
# Successful-day validator (pure)
# ---------------------------------------------------------------------------


def test_validator_accepts_correct_dry_run_day():
    assert rd.evaluate_successful_day(day()) == rd.ACCEPTABLE_SUCCESSFUL_DAY


def test_validator_duplicate_date_rejected():
    assert rd.evaluate_successful_day(day(duplicate_date=True)) == rd.REJECT_DUPLICATE_DATE


def test_validator_failed_run_rejected():
    assert rd.evaluate_successful_day(day(runner_status="PARTIAL_OUTPUT_FAILURE")) == rd.REJECT_RUN_FAILED


def test_validator_fingerprint_conflict_rejected():
    assert rd.evaluate_successful_day(day(plan_fingerprint_conflict=True)) == rd.REJECT_FINGERPRINT_CONFLICT
    assert rd.evaluate_successful_day(day(input_fingerprint_conflict=True)) == rd.REJECT_FINGERPRINT_CONFLICT


def test_validator_unauthorized_execution_rejected():
    assert rd.evaluate_successful_day(day(unauthorized_execution=True)) == rd.REJECT_UNAUTHORIZED_EXECUTION


def test_validator_protected_symbol_rejected():
    assert rd.evaluate_successful_day(day(protected_symbol_present=True)) == rd.REJECT_SAFETY_BLOCK


def test_validator_dry_run_nonzero_counts_rejected():
    assert rd.evaluate_successful_day(day(order_count=1)) == rd.REJECT_UNAUTHORIZED_EXECUTION
    assert rd.evaluate_successful_day(day(filled_count=1)) == rd.REJECT_UNAUTHORIZED_EXECUTION
    assert rd.evaluate_successful_day(day(closed_trade_count=1)) == rd.REJECT_UNAUTHORIZED_EXECUTION


def test_validator_source_invalid_and_output_incomplete():
    assert rd.evaluate_successful_day(day(source_date="2026-06-21")) == rd.REJECT_SOURCE_INVALID
    assert rd.evaluate_successful_day(day(excel_status="FAIL")) == rd.REJECT_OUTPUT_INCOMPLETE
    assert rd.evaluate_successful_day(day(notion_status="FAIL")) == rd.REJECT_OUTPUT_INCOMPLETE
    # Non-blocking delivery policy still accepts a non-PASS Notion status.
    assert rd.evaluate_successful_day(day(notion_status="SKIPPED", notion_delivery_policy="NON_BLOCKING",
                                         discord_status="SKIPPED", discord_delivery_policy="NON_BLOCKING")) \
        == rd.ACCEPTABLE_SUCCESSFUL_DAY


def test_validator_invalid_date_rejected():
    assert rd.evaluate_successful_day(day(date="2026/06/22")) == rd.REJECT_INVALID_DATE


def test_validator_does_not_mutate_state(tmp_path, fwd_root):
    initialize(tmp_path, fwd_root)
    before = (tmp_path / "out" / PILOT / rd.STATE_FILENAME).read_text(encoding="utf-8")
    rd.evaluate_successful_day(day())
    after = (tmp_path / "out" / PILOT / rd.STATE_FILENAME).read_text(encoding="utf-8")
    assert before == after


# ---------------------------------------------------------------------------
# Safety policy / no-op invariants / CLI / docs
# ---------------------------------------------------------------------------


def test_safety_policy_values_match_proposal():
    p = rd.SAFETY_POLICY
    assert p["environment"] == "BYBIT_DEMO_ONLY"
    assert p["live_endpoint"] == "PERMANENTLY_DENIED"
    assert p["max_new_opening_orders_per_successful_day"] == 1
    assert p["max_simultaneous_open_positions"] == 1
    assert p["max_per_order_notional_usdt"] == "10"
    assert p["max_daily_new_opening_notional_usdt"] == "10"
    assert p["averaging_down_pyramiding_adding"] == "FORBIDDEN"
    assert p["automatic_order_retry"] == "FORBIDDEN"
    assert p["close_orders"] == "REDUCE_ONLY_ONLY"
    assert p["automatic_demo_execution"] == "UNAUTHORIZED"
    assert p["proposed_actions_executable"] is False
    assert set(p["protected_symbols"]) == {"ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"}


def test_no_order_endpoint_or_bybit_import():
    for rel in ("src/demo_strategy_pilot_readiness.py", "scripts/manage_demo_strategy_pilot.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "/v5/order" not in src and "order/create" not in src and "api-demo.bybit.com" not in src
        assert "BybitExecutor" not in src
        for ln in src.splitlines():
            s = ln.strip()
            if s.startswith(("import ", "from ")):
                assert "executors.bybit" not in s and "src.risk" not in s and not s.startswith("import main")


def test_no_scheduler_or_retry():
    for rel in ("src/demo_strategy_pilot_readiness.py", "scripts/manage_demo_strategy_pilot.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "while True" not in src
        for token in ("import tenacity", "import backoff", "@retry", "apscheduler", "crontab"):
            assert token not in src


def test_cli_status_default_canonical_no_state(capsys):
    rc = cli.main(["--mode", "status", "--pilot-id", PILOT, "--json-only"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["banner"] == "7-DAY PILOT NOT STARTED / AUTOMATIC DEMO EXECUTION NOT AUTHORIZED"
    assert payload["pilot_started"] is False
    assert rc == cli.EXIT_OK


def test_cli_readiness_temp_root(tmp_path, fwd_root, monkeypatch, capsys):
    monkeypatch.setenv("NOTION_TOKEN", "t")
    monkeypatch.setenv("NOTION_PILOT_DATABASE_ID", "db")
    monkeypatch.setenv("MONITOR_DISCORD_WEBHOOK_URL", "h")
    rc = cli.main(["--mode", "readiness", "--pilot-id", PILOT, "--json-only",
                   "--test-output-root", str(tmp_path / "tmp_out"), "--forward-source-root", fwd_root])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == rd.STATUS_READY and payload["pilot_started"] is False
    assert rc == cli.EXIT_OK


def test_cli_test_output_root_refused_outside_temp(capsys):
    rc = cli.main(["--mode", "status", "--pilot-id", PILOT, "--test-output-root", "/var/lib/production"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "SAFETY_REFUSAL" and rc == cli.EXIT_SAFETY


def test_cli_modes_include_strategy_native_start_and_migrate():
    # TASK-014BX supersedes the readiness-only mode set: migrate + explicit
    # one-time start are now first-class modes. Bare --start / --execute /
    # --send-order style flags remain absent (start is --mode start).
    actions = {a.dest: a for a in cli.build_parser()._actions}
    mode_action = actions["mode"]
    assert set(mode_action.choices) == {"readiness", "initialize", "status", "migrate", "start"}
    opts = set()
    for a in cli.build_parser()._actions:
        opts.update(a.option_strings)
    for forbidden in ("--start", "--execute", "--allow-bybit-order", "--run", "--send-order"):
        assert forbidden not in opts


def test_documentation_updated():
    for rel in ("README.md", "docs/research/commands/NEXT_ACTION.md",
                "docs/research/commands/COMMAND_LOG.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "TASK-014BW" in text
