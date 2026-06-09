"""
scripts/execute_demo_new_entry.py
TASK-014L: Execute a single Demo new-entry order (gate + manual confirmation).

Usage (dry-run — DEFAULT, safe to run anytime):
  python scripts/execute_demo_new_entry.py \\
    --from-latest-review \\
    --symbol SOLUSDT \\
    --confirm-token CONFIRM_DEMO_NEW_ENTRY_YYYYMMDD \\
    [--write-report]

Usage (execute — requires all gates AND pre-send refresh to pass):
  python scripts/execute_demo_new_entry.py \\
    --from-latest-review \\
    --symbol SOLUSDT \\
    --confirm-token CONFIRM_DEMO_NEW_ENTRY_YYYYMMDD \\
    --execute-new-entry \\
    --write-report

IMPORTANT:
  - Default mode is DRY-RUN. Use --execute-new-entry for real order submission.
  - Exactly ONE symbol per invocation. --symbol is REQUIRED.
  - All safety gates enforced before any order submission.
  - Pre-send read-only refresh re-validates state right before POST.
  - Short new-entries are presently blocked at the static gate level.
  - Source: outputs/demo_trading/new_entry_review/latest_new_entry_review.json
  - Endpoint: Demo only (api-demo.bybit.com). No live fallback.

VPS flow (in order):
  1. source .env.demo
  2. python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
  3. python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report
  4. python3 scripts/preview_demo_new_entry_review.py --from-latest-reconciliation --write-report
  5. python3 scripts/execute_demo_new_entry.py --from-latest-review \\
         --symbol SOLUSDT --confirm-token CONFIRM_DEMO_NEW_ENTRY_$(date +%Y%m%d) [--dry-run]
  6. After dry-run review, add --execute-new-entry to submit.

Exit codes:
  0  Execution result produced (may be dry-run or execute; check order_sent in report).
  1  Fail-closed: missing review, missing symbol/token, gate failure, refresh failure.
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

from src.demo_new_entry_sender import DemoNewEntrySender, NewEntryOrderResult

_SEP = "-" * 72
_DEFAULT_REVIEW_DIR    = ROOT / "outputs" / "demo_trading" / "new_entry_review"
_DEFAULT_EXECUTION_DIR = ROOT / "outputs" / "demo_trading" / "new_entry_execution"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_latest_review(review_dir: Path) -> dict | None:
    """Load latest_new_entry_review.json. Returns None if missing or unreadable."""
    path = review_dir / "latest_new_entry_review.json"
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
    result:     NewEntryOrderResult,
    output_dir: Path,
    ts_utc:     str,
) -> None:
    """Write timestamped + latest JSON and Markdown new-entry execution reports."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ts_safe     = ts_utc.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "")
    json_path   = output_dir / f"{ts_safe}_new_entry_execution.json"
    json_latest = output_dir / "latest_new_entry_execution.json"
    md_path     = output_dir / f"{ts_safe}_new_entry_execution.md"
    md_latest   = output_dir / "latest_new_entry_execution.md"

    data                  = result.to_dict()
    data["timestamp_utc"] = ts_utc
    json_text             = json.dumps(data, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    if result.order_sent:
        status_str = "ORDER_SENT"
    elif result.execute_allowed and not result.execute_requested:
        status_str = "DRY_RUN_EXECUTE_ALLOWED"
    elif result.execute_allowed and result.execute_requested and not result.order_sent:
        status_str = "EXECUTE_FAILED_AT_EXCHANGE"
    else:
        status_str = "BLOCKED"

    md_lines = [
        "# Demo New-entry Execution Report",
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
        f"| order_side | {result.order_side} |",
        f"| selected_qty | {result.selected_qty} |",
        f"| order_type | {result.order_type} |",
        f"| reduce_only | {result.reduce_only} |",
        f"| preview_only_source | {result.preview_only_source} |",
        f"| execute_requested | {result.execute_requested} |",
        f"| execute_allowed | {result.execute_allowed} |",
        f"| order_sent | {result.order_sent} |",
        f"| order_response_status | {result.order_response_status or '(none)'} |",
        f"| order_id | {result.order_id or '(not sent)'} |",
        f"| demo_runtime_verified | {result.demo_runtime_verified} |",
        f"| proof_strength | {result.proof_strength} |",
        f"| endpoint_family | {result.endpoint_family} |",
        f"| account_mode | {result.account_mode} |",
        f"| position_details_source | {result.position_details_source} |",
        f"| available_balance_usd_source | {result.available_balance_usd_source} |",
        f"| review_fail_closed | {result.review_fail_closed} |",
        f"| review_timestamp | {result.review_timestamp} |",
        f"| protected_entry_required | {result.protected_entry_required} |",
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
        f"- no_batch_order: `{result.no_batch_order}`",
        f"- no_close_only_path: `{result.no_close_only_path}`",
        f"- reduce_only: `{result.reduce_only}`  (always False for new entries)",
        f"- secret_value_observed: `{result.secret_value_observed}`",
        f"- order_endpoint_called: `{result.order_endpoint_called}`",
        f"- no_position_modified: `{result.no_position_modified}`",
        "",
        "> secret_value_observed is always False.",
        "> no_live_endpoint is always True.",
        "> no_batch_order is always True.",
        "> no_close_only_path is always True.",
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

def _print_result(result: NewEntryOrderResult) -> None:
    print(f"  selected_symbol          : {result.selected_symbol}")
    print(f"  selected_side            : {result.selected_side}")
    print(f"  order_side               : {result.order_side}")
    print(f"  selected_qty             : {result.selected_qty}")
    print(f"  order_type               : {result.order_type}")
    print(f"  reduce_only              : {result.reduce_only}")
    print(f"  preview_only_source      : {result.preview_only_source}")
    print(f"  execute_requested        : {result.execute_requested}")
    print(f"  execute_allowed          : {result.execute_allowed}")
    print(f"  order_sent               : {result.order_sent}")
    print(f"  order_response_status    : {result.order_response_status or '(none)'}")
    print(f"  order_id                 : {result.order_id or '(not sent)'}")
    if result.blocked_gates:
        print(f"  blocked_gates            : {result.blocked_gates}")
    print(f"  demo_runtime_verified    : {result.demo_runtime_verified}")
    print(f"  proof_strength           : {result.proof_strength}")
    print(f"  endpoint_family          : {result.endpoint_family}")
    print(f"  account_mode             : {result.account_mode}")
    print(f"  position_details_source  : {result.position_details_source}")
    print(f"  available_balance_source : {result.available_balance_usd_source}")
    print(f"  no_live_endpoint         : {result.no_live_endpoint}")
    print(f"  no_batch_order           : {result.no_batch_order}")
    print(f"  no_close_only_path       : {result.no_close_only_path}")
    print(f"  secret_value_observed    : {result.secret_value_observed}")
    print(f"  order_endpoint_called    : {result.order_endpoint_called}")
    print(f"  no_position_modified     : {result.no_position_modified}")
    print(f"  review_fail_closed       : {result.review_fail_closed}")
    print(f"  review_timestamp         : {result.review_timestamp}")
    print(f"  protected_entry_required : {result.protected_entry_required}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_execute(
    mode:               str  = "from_latest_review",
    symbol:             str  = "",
    confirm_token:      str  = "",
    execute_new_entry:  bool = False,
    write_report:       bool = False,
    review_dir:         Path | None = None,
    execution_dir:      Path | None = None,
    allow_real_network: bool = False,
) -> int:
    """
    Run the new-entry order gate.

    Returns 0 when an execution result is produced (may be dry-run).
    Returns 1 on fail-closed (missing review, missing symbol/token, gate failure).
    """
    _review_dir    = review_dir    or _DEFAULT_REVIEW_DIR
    _execution_dir = execution_dir or _DEFAULT_EXECUTION_DIR

    print(_SEP)
    if execute_new_entry:
        print("EXECUTE MODE — NEW-ENTRY ORDER GATE — DEMO ENDPOINT ONLY")
    else:
        print("DRY RUN — NO ORDERS SENT — NEW-ENTRY GATE")
    print("TASK-014L: Demo New-entry Execution")
    print(_SEP)

    # Load review
    review = load_latest_review(_review_dir)
    if review is None:
        print("\n[FAIL CLOSED] latest_new_entry_review.json not found or unreadable.")
        print(f"  Expected: {_review_dir / 'latest_new_entry_review.json'}")
        print("  Run: python scripts/preview_demo_new_entry_review.py "
              "--from-latest-reconciliation --write-report")
        print(_SEP)
        return 1

    # Symbol REQUIRED (one-order-per-invocation)
    if not symbol:
        accepted = review.get("accepted_candidates", []) or []
        syms     = [c.get("symbol", "?") for c in accepted]
        print("\n[FAIL CLOSED] --symbol is required.")
        if syms:
            print(f"  Accepted candidates in review: {syms}")
        else:
            print("  Review has no accepted candidates.")
        print("  Example: --symbol SOLUSDT")
        print(_SEP)
        return 1

    # Confirm token required
    if not confirm_token:
        print("\n[FAIL CLOSED] --confirm-token is required.")
        print("  Pattern: CONFIRM_DEMO_NEW_ENTRY_YYYYMMDD (today UTC)")
        print(_SEP)
        return 1

    print(f"\n  mode            : {'execute_new_entry' if execute_new_entry else 'dry_run'}")
    print(f"  symbol          : {symbol}")
    print(f"  confirm_token   : {confirm_token[:8]}***")
    print(f"  review_source   : {_review_dir / 'latest_new_entry_review.json'}")

    sender = DemoNewEntrySender(allow_real_network=allow_real_network)
    result = sender.submit_one_new_entry(
        review=review,
        symbol=symbol,
        confirm_token=confirm_token,
        execute_new_entry=execute_new_entry,
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
        description="Execute a single Demo new-entry order (gate + manual confirmation)"
    )
    parser.add_argument(
        "--from-latest-review",
        action="store_true",
        help=(
            "Read new-entry review from "
            "outputs/demo_trading/new_entry_review/latest_new_entry_review.json"
        ),
    )
    parser.add_argument(
        "--symbol",
        default="",
        metavar="SYMBOL",
        help="Symbol to enter (REQUIRED; must be in review.accepted_candidates).",
    )
    parser.add_argument(
        "--confirm-token",
        default="",
        metavar="TOKEN",
        help=(
            "Manual confirmation token. Pattern: CONFIRM_DEMO_NEW_ENTRY_YYYYMMDD "
            "(today UTC). Required for all gate checks."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry-run gate check without order submission (default).",
    )
    parser.add_argument(
        "--execute-new-entry",
        action="store_true",
        help=(
            "Permit order submission after all gates AND pre-send refresh pass. "
            "Overrides --dry-run. Requires credentials and Demo endpoint reachability."
        ),
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write JSON + Markdown report to outputs/demo_trading/new_entry_execution/.",
    )
    args               = parser.parse_args()
    execute_new_entry  = args.execute_new_entry
    allow_real_network = execute_new_entry  # real network only needed for actual execution
    sys.exit(run_execute(
        mode="from_latest_review",
        symbol=args.symbol,
        confirm_token=args.confirm_token,
        execute_new_entry=execute_new_entry,
        write_report=args.write_report,
        allow_real_network=allow_real_network,
    ))


if __name__ == "__main__":
    main()
