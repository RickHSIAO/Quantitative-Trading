"""TASK-014BR -- demo strategy pilot daily runner CLI (DRY-RUN orchestration).

Modes:
    plan              default; fully offline; no Bybit/Notion/Discord network;
                      no order execution; prints the deterministic daily plan.
    dry_run           builds the PilotDailyRecord + audit + Excel + Notion/Discord
                      previews; sends NO order; Notion/Discord network only with
                      explicit --allow-*-network.
    reconcile_outputs rebuilds Excel and retries ONLY failed/skipped Notion/Discord
                      delivery; never recomputes strategy or appends a record.

There is intentionally NO order-execution mode and NO --execute/--send-order/
--allow-bybit-order/qty/symbol/endpoint/live/scheduler/retry-order/reset-journal/
force-rerun flag.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import demo_strategy_pilot_daily_runner as rr  # noqa: E402
from src import demo_strategy_pilot_delivery_transport as dt  # noqa: E402
from src import demo_strategy_pilot_discord_notify as dn  # noqa: E402
from src import demo_strategy_pilot_forward_source as fs  # noqa: E402
from src import demo_strategy_pilot_notion_sync as ns  # noqa: E402
from src.demo_strategy_pilot_reporting import PilotConfig  # noqa: E402

# Sample/default pilot identity (config supplied explicitly).
DEFAULT_PILOT_ID = "BYBIT_DEMO_PILOT_202606"
DEFAULT_START_DATE = "2026-06-22"


def _load_config(pilot_id: str, start_date: str) -> PilotConfig:
    return PilotConfig(
        pilot_id=pilot_id,
        start_date=start_date,
        strategy_name=rr.EXPECTED_STRATEGY_NAME,
        initial_equity_usdt=Decimal("10000"),
        comparison_forward_period="prev3y_crypto_30d_forward_validation",
        maximum_calendar_days=14,
        minimum_closed_trades=5,
        notion_enabled=True,
        excel_enabled=True,
        discord_enabled=True,
    )


def _load_strategy_result(args, forward_source_root: str | None) -> dict | None:
    """Resolve the strategy result for plan/dry_run.

    When --fixture is supplied, use the injected fixture (existing behavior).
    Otherwise load the real local primary Forward Record source via the
    read-only adapter (no network). reconcile_outputs never loads source.
    """
    if args.mode == rr.MODE_RECONCILE:
        return None
    if args.fixture:
        with open(args.fixture, "r", encoding="utf-8") as fh:
            return json.load(fh)
    result = fs.load_primary_forward_strategy_result(
        run_date=args.date, repo_root=pathlib.Path(ROOT), forward_source_root=forward_source_root)
    return result.to_strategy_result()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_demo_strategy_pilot_daily.py",
        description="Demo strategy pilot daily DRY-RUN orchestration (no order execution).",
    )
    p.add_argument("--mode", choices=list(rr.MODES), default=rr.MODE_PLAN)
    p.add_argument("--pilot-id", default=DEFAULT_PILOT_ID)
    p.add_argument("--date", required=True, help="ISO date YYYY-MM-DD")
    p.add_argument("--start-date", default=DEFAULT_START_DATE)
    p.add_argument("--fixture", default=None, help="injected strategy-result JSON fixture path")
    p.add_argument("--test-output-root", default=None,
                   help="TEST-ONLY output root; refused outside a temp/test context")
    p.add_argument("--forward-source-root", default=None,
                   help="TEST-ONLY Forward Record source root; refused outside a temp/test context. "
                        "Production uses the canonical outputs/forward_record location.")
    p.add_argument("--allow-notion-network", action="store_true")
    p.add_argument("--allow-discord-network", action="store_true")
    p.add_argument("--snapshot-date", default=None, help="override Excel snapshot YYYYMMDD (testing)")
    p.add_argument("--json-only", action="store_true")
    return p


def _resolve_output_root(arg_value: str | None) -> tuple[str | None, str | None]:
    """Return (output_root, refusal). Production root stays canonical (None).

    A supplied --test-output-root is accepted only when it looks like a
    temporary/test path; otherwise it is refused so production output cannot be
    silently redirected."""
    if arg_value is None:
        return None, None
    low = arg_value.replace("\\", "/").lower()
    markers = ("tmp", "temp", "pytest", "/t/", "test")
    if not any(m in low for m in markers):
        return None, ("--test-output-root is test-only and must point to a temporary/test "
                      "directory; refusing to redirect production output")
    return arg_value, None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    output_root, refusal = _resolve_output_root(args.test_output_root)
    if refusal:
        print(json.dumps({"status": "SAFETY_REFUSAL", "exit_code": rr.EXIT_SAFETY, "detail": refusal}))
        return rr.EXIT_SAFETY

    forward_source_root, fs_refusal = _resolve_output_root(args.forward_source_root)
    if fs_refusal:
        print(json.dumps({"status": "SAFETY_REFUSAL", "exit_code": rr.EXIT_SAFETY,
                          "detail": fs_refusal.replace("output", "Forward Record source")}))
        return rr.EXIT_SAFETY

    config = _load_config(args.pilot_id, args.start_date)
    try:
        strategy_result = _load_strategy_result(args, forward_source_root)
    except fs.ForwardSourceError as exc:
        payload = {"task_id": rr.TASK_ID, "mode": args.mode, "status": rr.STATUS_INPUT_FAILURE,
                   "exit_code": rr.EXIT_INPUT_FAILURE, "detail": f"forward source error: {exc}",
                   "order_execution_authorized": rr.ORDER_EXECUTION_AUTHORIZED,
                   "reason_execution_not_authorized": rr.REASON_NOT_AUTHORIZED}
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return rr.EXIT_INPUT_FAILURE

    # Construct real delivery transports ONLY when the corresponding explicit
    # allow flag is supplied (credential reads happen only inside these factories
    # when the flag is set). Plan / no-network dry_run / no-flag reconcile pass
    # allow_network=False -> the factories return None and read no credentials.
    notion_transport, _notion_detail = dt.build_notion_transport(
        allow_network=args.allow_notion_network, env=os.environ)
    discord_transport, _discord_detail = dt.build_discord_transport(
        allow_network=args.allow_discord_network, env=os.environ)
    notion_sync = ns.NotionDailySync(allow_network=args.allow_notion_network,
                                     transport=notion_transport, env=os.environ)
    discord_notify = dn.DiscordDailyNotify(allow_network=args.allow_discord_network,
                                           transport=discord_transport, env=os.environ)

    result = rr.run_daily(
        mode=args.mode, pilot_id=args.pilot_id, date=args.date, config=config,
        strategy_result=strategy_result, output_root=output_root,
        notion_sync=notion_sync, discord_notify=discord_notify,
        allow_notion_network=args.allow_notion_network,
        allow_discord_network=args.allow_discord_network,
        snapshot_date=args.snapshot_date,
    )

    payload = result.to_dict()
    if args.json_only:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return result.exit_code

    print(f"TASK-014BR daily runner -- mode={result.mode} status={result.status}")
    print(f"  pilot_id / date        : {result.pilot_id} / {result.date}")
    print(f"  order_execution_authorized: {rr.ORDER_EXECUTION_AUTHORIZED} ({rr.REASON_NOT_AUTHORIZED})")
    print(f"  journal_state          : {result.journal_state}")
    print(f"  phases_completed       : {', '.join(result.phases_completed)}")
    if result.plan:
        print(f"  strategy_name          : {result.plan.get('strategy_name')}")
        print(f"  signal_count           : {result.plan.get('signal_count')}")
        print(f"  plan_fingerprint       : {result.plan.get('plan_fingerprint')}")
    if result.excel:
        print(f"  excel                  : {result.excel.get('status')}")
    if result.notion:
        print(f"  notion                 : {result.notion.get('status')}")
    if result.discord:
        print(f"  discord                : {result.discord.get('status')}")
    print(f"  exit_code              : {result.exit_code}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
