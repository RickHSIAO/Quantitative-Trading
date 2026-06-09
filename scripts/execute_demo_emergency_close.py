"""
scripts/execute_demo_emergency_close.py
TASK-014N: Execute a single Demo emergency missing-stop close order.

Submits ONE reduce-only Market close for the single symbol whose
emergency_close_preview was emitted by the TASK-014M post-fill verifier
(latest_new_entry_postfill.json) with reason="missing_stop_price".

Usage (dry-run — DEFAULT, safe to run anytime):
  python scripts/execute_demo_emergency_close.py \\
    --from-latest-postfill \\
    --symbol SOLUSDT \\
    --confirm-token CONFIRM_DEMO_EMERGENCY_CLOSE_YYYYMMDD \\
    [--write-report]

Usage (execute — requires all gates AND pre-send refresh to pass):
  python scripts/execute_demo_emergency_close.py \\
    --from-latest-postfill \\
    --symbol SOLUSDT \\
    --confirm-token CONFIRM_DEMO_EMERGENCY_CLOSE_YYYYMMDD \\
    --execute-emergency-close \\
    --write-report

IMPORTANT:
  - Default mode is DRY-RUN.  Use --execute-emergency-close for real
    reduce-only close submission.
  - Exactly ONE symbol per invocation.  --symbol is REQUIRED and must
    equal the postfill emergency_close_preview.symbol.
  - All safety gates enforced before any order submission.
  - Pre-send read-only refresh re-validates state right before POST.
  - Endpoint: Demo only (api-demo.bybit.com).  No live fallback.

VPS flow (in order):
  1. source .env.demo
  2. python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
  3. python3 scripts/verify_demo_new_entry_postfill.py \\
         --from-latest-execution --from-latest-readonly-smoke \\
         --from-latest-review --with-emergency-close-preview --write-report
  4. python3 scripts/execute_demo_emergency_close.py \\
         --from-latest-postfill --symbol SOLUSDT \\
         --confirm-token CONFIRM_DEMO_EMERGENCY_CLOSE_$(date -u +%Y%m%d) [--dry-run]
  5. After dry-run review, add --execute-emergency-close to submit.

Exit codes:
  0  Execution result produced (may be dry-run; check order_sent).
  1  Fail-closed: missing postfill, missing symbol/token, gate failure.
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

from src.demo_emergency_close_sender import (
    DemoEmergencyCloseSender,
    EmergencyCloseOrderResult,
)

_SEP = "-" * 72
_DEFAULT_POSTFILL_DIR  = ROOT / "outputs" / "demo_trading" / "new_entry_postfill"
_DEFAULT_EXECUTION_DIR = ROOT / "outputs" / "demo_trading" / "emergency_close_execution"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_latest_postfill(postfill_dir: Path) -> dict | None:
    """Load latest_new_entry_postfill.json.  Returns None if missing/unreadable."""
    path = postfill_dir / "latest_new_entry_postfill.json"
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
    result:     EmergencyCloseOrderResult,
    output_dir: Path,
    ts_utc:     str,
) -> None:
    """Write timestamped + latest JSON and Markdown emergency-close reports."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ts_safe     = ts_utc.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "")
    json_path   = output_dir / f"{ts_safe}_emergency_close_execution.json"
    json_latest = output_dir / "latest_emergency_close_execution.json"
    md_path     = output_dir / f"{ts_safe}_emergency_close_execution.md"
    md_latest   = output_dir / "latest_emergency_close_execution.md"

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
        "# Demo Emergency Missing-stop Close Execution Report",
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
        f"| position_side | {result.position_side} |",
        f"| close_order_side | {result.close_order_side} |",
        f"| selected_qty | {result.selected_qty} |",
        f"| order_type | {result.order_type} |",
        f"| reduce_only | {result.reduce_only} |",
        f"| preview_only_source | {result.preview_only_source} |",
        f"| preview_reason | {result.preview_reason} |",
        f"| execute_requested | {result.execute_requested} |",
        f"| execute_allowed | {result.execute_allowed} |",
        f"| order_sent | {result.order_sent} |",
        f"| order_response_status | {result.order_response_status or '(none)'} |",
        f"| order_id | {result.order_id or '(not sent)'} |",
        f"| postfill_loaded | {result.postfill_loaded} |",
        f"| postfill_timestamp | {result.postfill_timestamp or '(none)'} |",
        f"| postfill_fail_closed | {result.postfill_fail_closed} |",
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
        f"- no_new_entry_path: `{result.no_new_entry_path}`",
        f"- no_close_only_sender_reused: `{result.no_close_only_sender_reused}`",
        f"- no_secrets: `{result.no_secrets}`",
        f"- reduce_only: `{result.reduce_only}`  (always True for emergency close)",
        f"- secret_value_observed: `{result.secret_value_observed}`",
        f"- order_endpoint_called: `{result.order_endpoint_called}`",
        f"- no_position_modified: `{result.no_position_modified}`",
        "",
        "> secret_value_observed is always False.",
        "> no_live_endpoint is always True.",
        "> no_batch_order is always True.",
        "> no_new_entry_path is always True.",
        "> reduce_only is always True for emergency close.",
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

def _print_result(result: EmergencyCloseOrderResult) -> None:
    print(f"  selected_symbol            : {result.selected_symbol}")
    print(f"  position_side              : {result.position_side}")
    print(f"  close_order_side           : {result.close_order_side}")
    print(f"  selected_qty               : {result.selected_qty}")
    print(f"  order_type                 : {result.order_type}")
    print(f"  reduce_only                : {result.reduce_only}")
    print(f"  preview_only_source        : {result.preview_only_source}")
    print(f"  preview_reason             : {result.preview_reason}")
    print(f"  execute_requested          : {result.execute_requested}")
    print(f"  execute_allowed            : {result.execute_allowed}")
    print(f"  order_sent                 : {result.order_sent}")
    print(f"  order_response_status      : {result.order_response_status or '(none)'}")
    print(f"  order_id                   : {result.order_id or '(not sent)'}")
    if result.blocked_gates:
        print(f"  blocked_gates              : {result.blocked_gates}")
    print(f"  postfill_loaded            : {result.postfill_loaded}")
    print(f"  postfill_timestamp         : {result.postfill_timestamp or '(none)'}")
    print(f"  postfill_fail_closed       : {result.postfill_fail_closed}")
    print(f"  no_live_endpoint           : {result.no_live_endpoint}")
    print(f"  no_batch_order             : {result.no_batch_order}")
    print(f"  no_new_entry_path          : {result.no_new_entry_path}")
    print(f"  no_close_only_sender_reused: {result.no_close_only_sender_reused}")
    print(f"  no_secrets                 : {result.no_secrets}")
    print(f"  secret_value_observed      : {result.secret_value_observed}")
    print(f"  order_endpoint_called      : {result.order_endpoint_called}")
    print(f"  no_position_modified       : {result.no_position_modified}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_execute(
    symbol:                   str  = "",
    confirm_token:            str  = "",
    execute_emergency_close:  bool = False,
    write_report:             bool = False,
    postfill_dir:             Path | None = None,
    execution_dir:            Path | None = None,
    allow_real_network:       bool = False,
) -> int:
    """
    Run the emergency close order gate.

    Returns 0 when an execution result is produced (may be dry-run).
    Returns 1 on fail-closed (missing postfill, missing symbol/token, gate failure).
    """
    _postfill_dir  = postfill_dir  or _DEFAULT_POSTFILL_DIR
    _execution_dir = execution_dir or _DEFAULT_EXECUTION_DIR

    print(_SEP)
    if execute_emergency_close:
        print("EXECUTE MODE — EMERGENCY MISSING-STOP CLOSE — DEMO ENDPOINT ONLY")
    else:
        print("DRY RUN — NO ORDERS SENT — EMERGENCY CLOSE GATE")
    print("TASK-014N: Demo Emergency Missing-stop Close")
    print(_SEP)

    # Load postfill report
    postfill = load_latest_postfill(_postfill_dir)
    if postfill is None:
        print("\n[FAIL CLOSED] latest_new_entry_postfill.json not found or unreadable.")
        print(f"  Expected: {_postfill_dir / 'latest_new_entry_postfill.json'}")
        print("  Run: python scripts/verify_demo_new_entry_postfill.py "
              "--from-latest-execution --from-latest-readonly-smoke "
              "--with-emergency-close-preview --write-report")
        print(_SEP)
        return 1

    # Symbol REQUIRED (one-order-per-invocation; symbol must equal preview symbol)
    if not symbol:
        preview = postfill.get("emergency_close_preview") or {}
        preview_sym = str(preview.get("symbol", "")) if isinstance(preview, dict) else ""
        print("\n[FAIL CLOSED] --symbol is required.")
        if preview_sym:
            print(f"  Emergency close preview symbol: {preview_sym}")
        else:
            print("  Postfill report has no emergency_close_preview symbol.")
        print("  Example: --symbol SOLUSDT")
        print(_SEP)
        return 1

    # Confirm token required
    if not confirm_token:
        print("\n[FAIL CLOSED] --confirm-token is required.")
        print("  Pattern: CONFIRM_DEMO_EMERGENCY_CLOSE_YYYYMMDD (today UTC)")
        print(_SEP)
        return 1

    print(f"\n  mode             : "
          f"{'execute_emergency_close' if execute_emergency_close else 'dry_run'}")
    print(f"  symbol           : {symbol}")
    print(f"  confirm_token    : {confirm_token[:8]}***")
    print(f"  postfill_source  : "
          f"{_postfill_dir / 'latest_new_entry_postfill.json'}")

    sender = DemoEmergencyCloseSender(allow_real_network=allow_real_network)
    result = sender.submit_one_emergency_close(
        postfill=postfill,
        symbol=symbol,
        confirm_token=confirm_token,
        execute_emergency_close=execute_emergency_close,
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
        description=(
            "Execute a single Demo emergency missing-stop reduce-only close "
            "(gate + manual confirmation).  READ from "
            "outputs/demo_trading/new_entry_postfill/latest_new_entry_postfill.json. "
            "Demo endpoint only.  No live fallback."
        )
    )
    parser.add_argument(
        "--from-latest-postfill",
        action="store_true",
        help=(
            "Read postfill verification report from "
            "outputs/demo_trading/new_entry_postfill/latest_new_entry_postfill.json"
        ),
    )
    parser.add_argument(
        "--symbol",
        default="",
        metavar="SYMBOL",
        help=(
            "Symbol to emergency-close (REQUIRED; must equal the postfill "
            "emergency_close_preview.symbol)."
        ),
    )
    parser.add_argument(
        "--confirm-token",
        default="",
        metavar="TOKEN",
        help=(
            "Manual confirmation token. Pattern: "
            "CONFIRM_DEMO_EMERGENCY_CLOSE_YYYYMMDD (today UTC). "
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
        "--execute-emergency-close",
        action="store_true",
        help=(
            "Permit order submission after all gates AND pre-send refresh pass. "
            "Overrides --dry-run.  Requires credentials and Demo endpoint "
            "reachability."
        ),
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help=(
            "Write JSON + Markdown report to "
            "outputs/demo_trading/emergency_close_execution/."
        ),
    )
    args                    = parser.parse_args()
    execute_emergency_close = args.execute_emergency_close
    allow_real_network      = execute_emergency_close
    sys.exit(run_execute(
        symbol=args.symbol,
        confirm_token=args.confirm_token,
        execute_emergency_close=execute_emergency_close,
        write_report=args.write_report,
        allow_real_network=allow_real_network,
    ))


if __name__ == "__main__":
    main()
