"""7-successful-day Bybit Demo Pilot management CLI.

Modes:
    readiness   read-only; validates configuration, Forward Record availability,
                reporting imports, Notion/Discord credential PRESENCE, dedicated
                Pilot Notion database PRESENCE, and the safety policy. Requires NO
                Bybit credentials, makes no persistent mutation and no network call.
    initialize  creates a new INACTIVE Pilot state (or BLOCKED if readiness
                fails); requires --i-understand-this-creates-an-inactive-7-day-pilot;
                idempotent for the same configuration; conflicting state fails
                closed. Never starts the Pilot, runs strategy, sends reports, or
                calls Bybit.
    status      read-only; displays the current lifecycle state, completed
                successful dates, remaining days, last accepted date, blockers.
    migrate     (TASK-014BX) audited, narrowly scoped policy migration that
                supersedes the previously proposed artificial Pilot caps with the
                strategy-native policy on an INACTIVE state. Requires
                --i-acknowledge-strategy-native-policy-migration. Idempotent;
                preserves the original configuration fingerprint; appends a
                MIGRATION event. Never starts the Pilot and never sends an order.
    start       (TASK-014BX) explicit ONE-TIME manual start: transitions
                INACTIVE -> RUNNING exactly once. Requires the exact flag
                --i-authorize-strategy-native-automatic-bybit-demo-execution-for-this-7-day-pilot,
                an existing INACTIVE strategy-native state, empty readiness
                blockers, and Demo credential PRESENCE (values never printed).
                It authorizes strategy-native automatic Bybit DEMO execution for
                THIS Pilot id only; it NEVER authorizes Live trading and itself
                sends no order.

"7 successful days" means 7 distinct successful Pilot dates, not 7 calendar days.

TASK-014BX (Rick's explicit decision): this is a Bybit Demo-only strategy
validation. The previously proposed artificial caps -- a fixed maximum of 1
opening order/day, a 10 USDT per-order cap, a 10 USDT daily opening cap, a
maximum of 1 simultaneous position, and the averaging/pyramiding prohibition --
are REMOVED. The Pilot executes according to the existing strategy's own rules.
Live trading remains permanently denied.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import demo_strategy_pilot_readiness as rd  # noqa: E402
from src import demo_strategy_pilot_lifecycle as lc  # noqa: E402

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_INVALID = 2
EXIT_CONFLICT = 5
EXIT_SAFETY = 6

NOT_STARTED_BANNER = "7-DAY PILOT NOT STARTED / AUTOMATIC DEMO EXECUTION NOT AUTHORIZED"
STARTED_BANNER = "7-DAY PILOT RUNNING (BYBIT DEMO ONLY) / LIVE TRADING NOT AUTHORIZED"

# Modes that do NOT change lifecycle and must carry the NOT_STARTED banner.
_NON_AUTHORIZING_MODES = ("readiness", "initialize", "status")


def _resolve_test_root(arg_value: str | None, label: str) -> tuple[str | None, str | None]:
    """Production uses the canonical path (None). A supplied test root is only
    accepted when it looks like a temporary/test path."""
    if arg_value is None:
        return None, None
    low = arg_value.replace("\\", "/").lower()
    if not any(m in low for m in ("tmp", "temp", "pytest", "/t/", "test")):
        return None, f"--{label} is test-only and must point to a temporary/test directory"
    return arg_value, None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="manage_demo_strategy_pilot.py",
        description="Manage the 7-successful-day Bybit Demo Pilot "
                    "(readiness/initialize/status/migrate/start).",
    )
    p.add_argument("--mode",
                   choices=["readiness", "initialize", "status", "migrate", "start"],
                   required=True)
    p.add_argument("--pilot-id", required=True)
    p.add_argument("--i-understand-this-creates-an-inactive-7-day-pilot",
                   dest="init_ack", action="store_true")
    p.add_argument("--" + lc.MIGRATION_ACK_FLAG, dest="migrate_ack", action="store_true",
                   help="exact one-time acknowledgement required for --mode migrate")
    p.add_argument("--" + lc.START_ACK_FLAG, dest="start_ack", action="store_true",
                   help="exact one-time acknowledgement required for --mode start")
    p.add_argument("--test-output-root", default=None, help="TEST-ONLY output root (refused outside temp/test)")
    p.add_argument("--forward-source-root", default=None, help="TEST-ONLY Forward Record source root")
    p.add_argument("--json-only", action="store_true")
    return p


def _exit_code(status: str) -> int:
    return {
        rd.STATUS_READY: EXIT_OK, rd.STATUS_INACTIVE: EXIT_OK,
        "ALREADY_INITIALIZED_IDEMPOTENT": EXIT_OK, rd.NOT_INITIALIZED: EXIT_OK,
        lc.STATUS_MIGRATED: EXIT_OK, lc.STATUS_ALREADY_MIGRATED: EXIT_OK,
        lc.STATUS_STARTED: EXIT_OK, lc.STATUS_ALREADY_RUNNING: EXIT_OK,
        rd.RUNNING: EXIT_OK, rd.COMPLETED: EXIT_OK,
        rd.STATUS_BLOCKED: EXIT_BLOCKED, rd.BLOCKED: EXIT_BLOCKED,
        lc.STATUS_REFUSED_MISSING_DEMO_CREDENTIALS: EXIT_BLOCKED,
        lc.STATUS_REFUSED_POLICY_NOT_MIGRATED: EXIT_BLOCKED,
        rd.STATUS_INVALID_CONFIGURATION: EXIT_INVALID,
        "REFUSED_NOT_ACKNOWLEDGED": EXIT_INVALID,
        lc.STATUS_REFUSED_NOT_ACKNOWLEDGED: EXIT_INVALID,
        lc.STATUS_NOT_INITIALIZED: EXIT_OK,
        rd.STATUS_CONFLICTING_EXISTING_STATE: EXIT_CONFLICT,
        lc.STATUS_CONFLICTING: EXIT_CONFLICT,
    }.get(status, EXIT_OK)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    output_root, r1 = _resolve_test_root(args.test_output_root, "test-output-root")
    if r1:
        print(json.dumps({"status": "SAFETY_REFUSAL", "detail": r1, "note": NOT_STARTED_BANNER}))
        return EXIT_SAFETY
    forward_source_root, r2 = _resolve_test_root(args.forward_source_root, "forward-source-root")
    if r2:
        print(json.dumps({"status": "SAFETY_REFUSAL", "detail": r2, "note": NOT_STARTED_BANNER}))
        return EXIT_SAFETY

    if args.mode == "readiness":
        result = rd.run_readiness(pilot_id=args.pilot_id, env=os.environ, output_root=output_root,
                                  forward_source_root=forward_source_root)
    elif args.mode == "initialize":
        result = rd.initialize_pilot(pilot_id=args.pilot_id, acknowledged=bool(args.init_ack),
                                     env=os.environ, output_root=output_root,
                                     forward_source_root=forward_source_root)
    elif args.mode == "status":
        result = rd.pilot_status(pilot_id=args.pilot_id, output_root=output_root)
    elif args.mode == "migrate":
        result = lc.migrate_to_strategy_native(pilot_id=args.pilot_id,
                                               acknowledged=bool(args.migrate_ack),
                                               output_root=output_root)
    else:  # start
        result = lc.start_pilot(pilot_id=args.pilot_id, acknowledged=bool(args.start_ack),
                                env=os.environ, output_root=output_root)

    # Banners. Non-authorizing modes always carry NOT_STARTED. start/migrate
    # report Live = denied explicitly; start success carries the RUNNING banner.
    if args.mode in _NON_AUTHORIZING_MODES:
        result["pilot_started"] = False
        result["automatic_demo_execution_authorized"] = False
        result["banner"] = NOT_STARTED_BANNER
    else:
        result["live_trading_authorized"] = result.get("live_trading_authorized", False)
        if result.get("status") in (lc.STATUS_STARTED, lc.STATUS_ALREADY_RUNNING):
            result["banner"] = STARTED_BANNER
        else:
            result["banner"] = NOT_STARTED_BANNER

    if args.json_only:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"pilot manage -- mode={args.mode} pilot_id={args.pilot_id}")
        print(f"  status          : {result.get('status')}")
        print(f"  lifecycle_state : {result.get('lifecycle_state')}")
        if args.mode == "readiness":
            print(f"  ready_for_manual_start_review: {result.get('ready_for_manual_start_review')}")
            print(f"  blockers        : {result.get('blockers')}")
            print(f"  warnings        : {result.get('warnings')}")
        if args.mode in ("migrate", "start"):
            print(f"  live_trading_authorized: {result.get('live_trading_authorized', False)}")
            print(f"  detail          : {result.get('detail')}")
        print(f"  completed_days  : {result.get('completed_successful_days', 0)} / "
              f"{rd.TARGET_SUCCESSFUL_DAYS}")
        print(f"  {result.get('banner')}")

    return _exit_code(str(result.get("status", "")))


if __name__ == "__main__":
    raise SystemExit(main())
