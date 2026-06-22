"""TASK-014BW -- 7-successful-day Bybit Demo Pilot management CLI (readiness only).

Modes:
    readiness   read-only; validates configuration, Forward Record availability,
                reporting imports, Notion/Discord credential PRESENCE, dedicated
                Pilot Notion database PRESENCE, and the inactive safety policy.
                Requires NO Bybit credentials (execution is unauthorized) and
                makes no persistent mutation and no network call.
    initialize  creates a new INACTIVE Pilot state (or BLOCKED if readiness
                fails); requires --i-understand-this-creates-an-inactive-7-day-pilot;
                idempotent for the same configuration; conflicting state fails
                closed. Never starts the Pilot, runs strategy, sends reports, or
                calls Bybit. Never produces RUNNING or COMPLETED.
    status      read-only; displays the current lifecycle state, completed
                successful dates, remaining days, last accepted date, blockers.

There is intentionally NO start / execute / order-authorizing mode.
"7 successful days" means 7 distinct successful Pilot dates, not 7 calendar days.

READY_FOR_MANUAL_START_REVIEW does NOT authorize or start the Pilot; manual
start authorization is a SEPARATE future task. Automatic Bybit Demo execution
remains unauthorized.
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

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_INVALID = 2
EXIT_CONFLICT = 5
EXIT_SAFETY = 6

NOT_STARTED_BANNER = "7-DAY PILOT NOT STARTED / AUTOMATIC DEMO EXECUTION NOT AUTHORIZED"


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
        description="Manage the inactive 7-successful-day Bybit Demo Pilot (readiness/initialize/status only).",
    )
    p.add_argument("--mode", choices=["readiness", "initialize", "status"], required=True)
    p.add_argument("--pilot-id", required=True)
    p.add_argument("--i-understand-this-creates-an-inactive-7-day-pilot", dest="ack", action="store_true")
    p.add_argument("--test-output-root", default=None, help="TEST-ONLY output root (refused outside temp/test)")
    p.add_argument("--forward-source-root", default=None, help="TEST-ONLY Forward Record source root")
    p.add_argument("--json-only", action="store_true")
    return p


def _exit_code(status: str) -> int:
    return {
        rd.STATUS_READY: EXIT_OK, rd.STATUS_INACTIVE: EXIT_OK,
        "ALREADY_INITIALIZED_IDEMPOTENT": EXIT_OK, rd.NOT_INITIALIZED: EXIT_OK,
        rd.STATUS_BLOCKED: EXIT_BLOCKED, rd.BLOCKED: EXIT_BLOCKED,
        rd.STATUS_INVALID_CONFIGURATION: EXIT_INVALID, "REFUSED_NOT_ACKNOWLEDGED": EXIT_INVALID,
        rd.STATUS_CONFLICTING_EXISTING_STATE: EXIT_CONFLICT,
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
        result = rd.initialize_pilot(pilot_id=args.pilot_id, acknowledged=bool(args.ack), env=os.environ,
                                     output_root=output_root, forward_source_root=forward_source_root)
    else:  # status
        result = rd.pilot_status(pilot_id=args.pilot_id, output_root=output_root)

    result["pilot_started"] = False
    result["automatic_demo_execution_authorized"] = False
    result["banner"] = NOT_STARTED_BANNER

    if args.json_only:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"TASK-014BW pilot manage -- mode={args.mode} pilot_id={args.pilot_id}")
        print(f"  status          : {result.get('status')}")
        print(f"  lifecycle_state : {result.get('lifecycle_state')}")
        if args.mode == "readiness":
            print(f"  ready_for_manual_start_review: {result.get('ready_for_manual_start_review')}")
            print(f"  blockers        : {result.get('blockers')}")
            print(f"  warnings        : {result.get('warnings')}")
        print(f"  completed_days  : {result.get('completed_successful_days', 0)} / "
              f"{rd.TARGET_SUCCESSFUL_DAYS}")
        print(f"  remaining_days  : {result.get('remaining_successful_days', rd.TARGET_SUCCESSFUL_DAYS)}")
        print(f"  {NOT_STARTED_BANNER}")

    return _exit_code(str(result.get("status", "")))


if __name__ == "__main__":
    raise SystemExit(main())
