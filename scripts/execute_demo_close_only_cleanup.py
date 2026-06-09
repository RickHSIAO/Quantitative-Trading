"""
scripts/execute_demo_close_only_cleanup.py
TASK-014G: Execute a single Demo close-only order (gate + human confirmation).

Usage (dry-run — DEFAULT, safe to run anytime):
  python scripts/execute_demo_close_only_cleanup.py \\
    --from-latest-cleanup \\
    --symbol ETHUSDT \\
    --confirm-token CONFIRM_DEMO_CLOSE_ONLY_YYYYMMDD \\
    [--write-report]

Usage (execute — requires all gates to pass):
  python scripts/execute_demo_close_only_cleanup.py \\
    --from-latest-cleanup \\
    --symbol ETHUSDT \\
    --confirm-token CONFIRM_DEMO_CLOSE_ONLY_YYYYMMDD \\
    --execute-close-only \\
    --write-report

IMPORTANT:
  - Default mode is dry-run. Use --execute-close-only for real order submission.
  - Only ONE symbol per invocation. Multiple candidates require --symbol.
  - All safety gates enforced before any order submission.
  - Source: outputs/demo_trading/close_only_cleanup/latest_close_only_cleanup.json

VPS flow (in order):
  1. source .env.demo
  2. python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
  3. python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report
  4. python3 scripts/preview_demo_close_only_cleanup.py --from-latest-reconciliation \\
         --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) --write-report
  5. python3 scripts/execute_demo_close_only_cleanup.py --from-latest-cleanup \\
         --symbol ETHUSDT --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) [--dry-run]
  6. After dry-run review, add --execute-close-only to submit.

Exit codes:
  0  Execution result produced (may be dry-run or execute; check order_sent in report).
  1  Fail-closed: missing plan, no candidates, missing token, or gate failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.demo_close_only_sender import CloseOrderResult, DemoCloseOnlySender

_SEP = "-" * 72
_DEFAULT_CLEANUP_DIR   = ROOT / "outputs" / "demo_trading" / "close_only_cleanup"
_DEFAULT_EXECUTION_DIR = ROOT / "outputs" / "demo_trading" / "close_only_execution"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_latest_cleanup(cleanup_dir: Path) -> dict | None:
    """Load latest_close_only_cleanup.json. Returns None if missing or unreadable."""
    path = cleanup_dir / "latest_close_only_cleanup.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_execution_report(
    result:     CloseOrderResult,
    output_dir: Path,
    ts_utc:     str,
) -> None:
    """Write timestamped + latest JSON and Markdown execution reports."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ts_safe     = ts_utc.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "")
    json_path   = output_dir / f"{ts_safe}_close_only_execution.json"
    json_latest = output_dir / "latest_close_only_execution.json"
    md_path     = output_dir / f"{ts_safe}_close_only_execution.md"
    md_latest   = output_dir / "latest_close_only_execution.md"

    data               = result.to_dict()
    data["timestamp_utc"] = ts_utc
    json_text = json.dumps(data, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    status_str = (
        "ORDER_SENT"
        if result.order_sent
        else (
            "DRY_RUN_EXECUTE_ALLOWED"
            if (result.execute_allowed and not result.execute_requested)
            else "BLOCKED"
        )
    )

    md_lines = [
        "# Demo Close-only Execution Report",
        "",
        f"timestamp: `{ts_utc}`  ",
        f"mode: `{result.mode}`  ",
        f"status: **{status_str}**  ",
        "",
        "## Execution Summary",
        "",
        "| field | value |",
        "|---|---|",
        f"| selected_symbol | {result.selected_symbol} |",
        f"| selected_side | {result.selected_side} |",
        f"| close_order_side | {result.close_order_side} |",
        f"| selected_qty | {result.selected_qty} |",
        f"| order_type | {result.order_type} |",
        f"| reduce_only | {result.reduce_only} |",
        f"| execute_requested | {result.execute_requested} |",
        f"| execute_allowed | {result.execute_allowed} |",
        f"| order_sent | {result.order_sent} |",
        f"| order_response_status | {result.order_response_status} |",
        f"| order_id | {result.order_id or '(not sent)'} |",
        f"| position_details_source | {result.position_details_source} |",
        f"| source_position_details_is_real | {result.source_position_details_is_real} |",
        "",
    ]
    if result.blocked_gates:
        md_lines += ["## Blocked Gates", ""]
        for g in result.blocked_gates:
            md_lines.append(f"- {g}")
        md_lines.append("")
    md_lines += [
        "## Safety Invariants",
        "",
        f"- no_live_endpoint: `{result.no_live_endpoint}`",
        f"- no_new_position_intent: `{result.no_new_position_intent}`",
        f"- secret_value_observed: `{result.secret_value_observed}`",
        f"- order_endpoint_called: `{result.order_endpoint_called}`",
        f"- private_order_endpoint_called: `{result.private_order_endpoint_called}`",
        f"- no_position_modified: `{result.no_position_modified}`",
        "",
        "> secret_value_observed is always False.",
        "> no_live_endpoint is always True.",
        "",
    ]
    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    md_latest.write_text(md_text, encoding="utf-8")

    print(f"  report: {json_latest}")
    print(f"  report: {md_latest}")


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _print_result(result: CloseOrderResult) -> None:
    print(f"  selected_symbol          : {result.selected_symbol}")
    print(f"  selected_side            : {result.selected_side}")
    print(f"  close_order_side         : {result.close_order_side}")
    print(f"  selected_qty             : {result.selected_qty}")
    print(f"  order_type               : {result.order_type}")
    print(f"  reduce_only              : {result.reduce_only}")
    print(f"  execute_requested        : {result.execute_requested}")
    print(f"  execute_allowed          : {result.execute_allowed}")
    print(f"  order_sent               : {result.order_sent}")
    print(f"  order_response_status    : {result.order_response_status or '(none)'}")
    print(f"  order_id                 : {result.order_id or '(not sent)'}")
    if result.blocked_gates:
        print(f"  blocked_gates            : {result.blocked_gates}")
    print(f"  no_live_endpoint         : {result.no_live_endpoint}")
    print(f"  no_new_position_intent   : {result.no_new_position_intent}")
    print(f"  secret_value_observed    : {result.secret_value_observed}")
    print(f"  order_endpoint_called    : {result.order_endpoint_called}")
    print(f"  no_position_modified     : {result.no_position_modified}")
    print(f"  position_details_source  : {result.position_details_source}")
    print(f"  source_is_real_readonly  : {result.source_position_details_is_real}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_execute(
    mode:               str  = "from_latest_cleanup",
    symbol:             str  = "",
    confirm_token:      str  = "",
    execute_close_only: bool = False,
    write_report:       bool = False,
    cleanup_dir:        Path | None = None,
    execution_dir:      Path | None = None,
    allow_real_network: bool = False,
) -> int:
    """
    Run the close-only order gate.

    Returns 0 when an execution result is produced (may be dry-run).
    Returns 1 on fail-closed (missing plan, missing token, gate failure).
    """
    _cleanup_dir   = cleanup_dir   or _DEFAULT_CLEANUP_DIR
    _execution_dir = execution_dir or _DEFAULT_EXECUTION_DIR

    print(_SEP)
    if execute_close_only:
        print("EXECUTE MODE — CLOSE-ONLY ORDER GATE — DEMO ENDPOINT ONLY")
    else:
        print("DRY RUN — NO ORDERS SENT — CLOSE-ONLY GATE")
    print("TASK-014G: Demo Close-only Execution")
    print(_SEP)

    # Load cleanup plan
    cleanup_plan = load_latest_cleanup(_cleanup_dir)
    if cleanup_plan is None:
        print("\n[FAIL CLOSED] latest_close_only_cleanup.json not found or unreadable.")
        print(f"  Expected: {_cleanup_dir / 'latest_close_only_cleanup.json'}")
        print("  Run: python scripts/preview_demo_close_only_cleanup.py --write-report")
        print(_SEP)
        return 1

    # One-order limit: require --symbol when multiple candidates exist
    candidates = cleanup_plan.get("suggested_close_candidates", [])
    if not symbol:
        if len(candidates) > 1:
            syms = [c.get("symbol", "?") for c in candidates]
            print(f"\n[FAIL CLOSED] Multiple close candidates: {syms}.")
            print("  Specify --symbol to select exactly one.")
            print("  Example: --symbol ETHUSDT")
            print(_SEP)
            return 1
        elif len(candidates) == 1:
            symbol = str(candidates[0].get("symbol", ""))
        else:
            print("\n[FAIL CLOSED] No candidates in cleanup plan.")
            print("  Run cleanup preview again: preview_demo_close_only_cleanup.py")
            print(_SEP)
            return 1

    # Confirm token required
    if not confirm_token:
        print("\n[FAIL CLOSED] --confirm-token is required.")
        print("  Pattern: CONFIRM_DEMO_CLOSE_ONLY_YYYYMMDD")
        print(_SEP)
        return 1

    print(f"\n  mode            : {'execute_close_only' if execute_close_only else 'dry_run'}")
    print(f"  symbol          : {symbol}")
    print(f"  confirm_token   : {confirm_token[:8]}***")
    print(f"  cleanup_plan    : {_cleanup_dir / 'latest_close_only_cleanup.json'}")

    sender = DemoCloseOnlySender(allow_real_network=allow_real_network)
    result = sender.submit_one_close_order(
        cleanup_plan=cleanup_plan,
        symbol=symbol,
        confirm_token=confirm_token,
        execute_close_only=execute_close_only,
    )

    print()
    _print_result(result)
    print(_SEP)

    if write_report:
        ts_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_execution_report(result, _execution_dir, ts_utc)

    return 1 if result.blocked_gates else 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute a single Demo close-only order (gate + confirmation)"
    )
    parser.add_argument(
        "--from-latest-cleanup",
        action="store_true",
        help=(
            "Read cleanup plan from "
            "outputs/demo_trading/close_only_cleanup/latest_close_only_cleanup.json"
        ),
    )
    parser.add_argument(
        "--symbol",
        default="",
        metavar="SYMBOL",
        help="Symbol to close (required when cleanup plan has multiple candidates).",
    )
    parser.add_argument(
        "--confirm-token",
        default="",
        metavar="TOKEN",
        help=(
            "Human confirmation token. Pattern: CONFIRM_DEMO_CLOSE_ONLY_YYYYMMDD. "
            "Required for all gate checks."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry-run gate check without order submission (default).",
    )
    parser.add_argument(
        "--execute-close-only",
        action="store_true",
        help=(
            "Permit order submission after all gates pass. "
            "Overrides --dry-run. Requires credentials and pre-send refresh."
        ),
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write JSON + Markdown report to outputs/demo_trading/close_only_execution/.",
    )
    args               = parser.parse_args()
    execute_close_only = args.execute_close_only
    allow_real_network = execute_close_only  # real network only needed for actual execution
    sys.exit(run_execute(
        mode="from_latest_cleanup",
        symbol=args.symbol,
        confirm_token=args.confirm_token,
        execute_close_only=execute_close_only,
        write_report=args.write_report,
        allow_real_network=allow_real_network,
    ))


if __name__ == "__main__":
    main()
