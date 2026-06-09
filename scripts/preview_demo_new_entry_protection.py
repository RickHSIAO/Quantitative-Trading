"""
scripts/preview_demo_new_entry_protection.py
TASK-014Q: Preview a protected-entry plan for one Demo new-entry candidate.

Usage:
  python scripts/preview_demo_new_entry_protection.py \\
    --from-latest-review \\
    --symbol SOLUSDT \\
    [--write-report]

Reads:
  outputs/demo_trading/new_entry_review/latest_new_entry_review.json

Outputs (when --write-report):
  outputs/demo_trading/new_entry_protection/{ts}_new_entry_protection.json
  outputs/demo_trading/new_entry_protection/{ts}_new_entry_protection.md
  outputs/demo_trading/new_entry_protection/latest_new_entry_protection.json
  outputs/demo_trading/new_entry_protection/latest_new_entry_protection.md

This CLI is preview-only.  It NEVER:
  * sends an order
  * calls the trading-stop / stop-loss endpoint
  * touches positions
  * reads or prints API keys / secrets
  * contacts the live host (no network at all)

Exit codes:
  0  plan emitted (even fail-closed)
  1  latest_new_entry_review.json missing or unreadable
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

from src.demo_new_entry_protection import (
    PROTECTED_ENTRY_STATUS_FAIL_CLOSED,
    PROTECTED_ENTRY_STATUS_PREVIEW_ONLY,
    ProtectedEntryPlan,
    build_protected_entry_plan,
)


_SEP = "-" * 72
_DEFAULT_REVIEW_DIR     = ROOT / "outputs" / "demo_trading" / "new_entry_review"
_DEFAULT_PROTECTION_DIR = ROOT / "outputs" / "demo_trading" / "new_entry_protection"


def load_latest_review(review_dir: Path) -> dict | None:
    """Load latest_new_entry_review.json from disk."""
    path = review_dir / "latest_new_entry_review.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _print_plan(plan: ProtectedEntryPlan) -> None:
    print(f"  selected_symbol                  : {plan.selected_symbol}")
    print(f"  selected_side                    : {plan.selected_side}")
    print(f"  order_side                       : {plan.order_side}")
    print(f"  selected_qty                     : {plan.selected_qty}")
    print(f"  entry_reference_price            : {plan.entry_reference_price}")
    print(f"  stop_price                       : {plan.stop_price}")
    print(f"  stop_order_side                  : {plan.stop_order_side}")
    print(f"  stop_trigger_direction           : {plan.stop_trigger_direction}")
    print(f"  realtime_price_guard_verified    : {plan.realtime_price_guard_verified}")
    print(f"  lifecycle_phase                  : {plan.lifecycle_phase}")
    print(f"  protected_entry_status           : {plan.protected_entry_status}")
    print(f"  stop_loss_attach_required        : {plan.stop_loss_attach_required}")
    print(f"  stop_loss_endpoint_allowed       : {plan.stop_loss_endpoint_allowed}")
    print(f"  preview_only                     : {plan.preview_only}")
    print(f"  protected_entry_execute_allowed  : {plan.protected_entry_execute_allowed}")
    print(f"  protected_entry_execute_reason   : {plan.protected_entry_execute_reason}")
    print(f"  no_orders_sent                   : {plan.no_orders_sent}")
    print(f"  order_endpoint_called            : {plan.order_endpoint_called}")
    print(f"  stop_endpoint_called             : {plan.stop_endpoint_called}")
    print(f"  no_position_modified             : {plan.no_position_modified}")
    print(f"  no_live_endpoint                 : {plan.no_live_endpoint}")
    print(f"  secret_value_observed            : {plan.secret_value_observed}")
    print(f"  order_create_endpoint            : {plan.order_create_endpoint}")
    print(f"  stop_attach_endpoint             : {plan.stop_attach_endpoint}  (NOT invoked)")
    print(f"  endpoint_family                  : {plan.endpoint_family}")
    print(f"  next_required_task               : {plan.next_required_task}")
    print(f"  review_fail_closed               : {plan.review_fail_closed}")
    print(f"  review_timestamp                 : {plan.review_timestamp}")
    if plan.blocked_reasons:
        print("  blocked_reasons:")
        for r in plan.blocked_reasons:
            print(f"    - {r}")


def _write_report(plan: ProtectedEntryPlan, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_safe = (
        plan.timestamp_utc
        .replace(":", "")
        .replace("-", "")
        .replace("T", "_")
        .replace("Z", "")
    )
    json_path   = output_dir / f"{ts_safe}_new_entry_protection.json"
    json_latest = output_dir / "latest_new_entry_protection.json"
    md_path     = output_dir / f"{ts_safe}_new_entry_protection.md"
    md_latest   = output_dir / "latest_new_entry_protection.md"

    data      = plan.to_dict()
    json_text = json.dumps(data, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    if plan.protected_entry_status == PROTECTED_ENTRY_STATUS_FAIL_CLOSED:
        status_line = "FAIL_CLOSED"
    elif plan.protected_entry_status == PROTECTED_ENTRY_STATUS_PREVIEW_ONLY:
        status_line = "PREVIEW_ONLY (stop-loss attachment not yet implemented)"
    else:
        status_line = plan.protected_entry_status

    md_lines = [
        "# Demo New-entry Protected Entry Plan (TASK-014Q)",
        "",
        f"timestamp: `{plan.timestamp_utc}`  ",
        f"status: **{status_line}**  ",
        f"lifecycle_phase: `{plan.lifecycle_phase}`  ",
        "",
        "## Plan Summary",
        "",
        "| field | value |",
        "|---|---|",
        f"| selected_symbol | {plan.selected_symbol} |",
        f"| selected_side | {plan.selected_side} |",
        f"| order_side | {plan.order_side} |",
        f"| selected_qty | {plan.selected_qty} |",
        f"| entry_reference_price | {plan.entry_reference_price} |",
        f"| stop_price | {plan.stop_price} |",
        f"| stop_order_side | {plan.stop_order_side} |",
        f"| stop_trigger_direction | {plan.stop_trigger_direction} |",
        f"| realtime_price_guard_verified | {plan.realtime_price_guard_verified} |",
        f"| review_fail_closed | {plan.review_fail_closed} |",
        f"| review_timestamp | {plan.review_timestamp} |",
        f"| stop_loss_attach_required | {plan.stop_loss_attach_required} |",
        f"| stop_loss_endpoint_allowed | {plan.stop_loss_endpoint_allowed} |",
        f"| preview_only | {plan.preview_only} |",
        f"| protected_entry_execute_allowed | {plan.protected_entry_execute_allowed} |",
        f"| protected_entry_execute_reason | {plan.protected_entry_execute_reason} |",
        f"| next_required_task | {plan.next_required_task} |",
        "",
    ]

    if plan.blocked_reasons:
        md_lines += ["## Blocked Reasons", ""]
        for r in plan.blocked_reasons:
            md_lines.append(f"- {r}")
        md_lines.append("")

    md_lines += [
        "## Endpoint Group Separation",
        "",
        f"- order_create : `{plan.order_create_endpoint}` (TASK-014L sender path)",
        f"- trading_stop : `{plan.stop_attach_endpoint}` "
        "(RESERVED FOR TASK-014R — NOT invoked here)",
        f"- endpoint_family : `{plan.endpoint_family}` (Demo only, no live fallback)",
        "",
        "## Safety Invariants",
        "",
        f"- no_orders_sent: `{plan.no_orders_sent}`",
        f"- order_endpoint_called: `{plan.order_endpoint_called}`",
        f"- stop_endpoint_called: `{plan.stop_endpoint_called}`",
        f"- no_position_modified: `{plan.no_position_modified}`",
        f"- no_live_endpoint: `{plan.no_live_endpoint}`",
        f"- secret_value_observed: `{plan.secret_value_observed}`",
        "",
        "> This module never invokes the trading-stop endpoint.",
        "> No orders are sent; no positions are modified.",
        "> Actual --execute-new-entry on the TASK-014L sender is blocked",
        "> by the G20 `protected_entry_policy_missing` gate until TASK-014R.",
        "",
    ]
    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    md_latest.write_text(md_text, encoding="utf-8")

    print(f"  report: {json_latest}")
    print(f"  report: {md_latest}")


def run_preview(
    symbol:         str,
    write_report:   bool = False,
    review_dir:     Path | None = None,
    protection_dir: Path | None = None,
    _now:           datetime | None = None,
) -> int:
    _review_dir     = review_dir     or _DEFAULT_REVIEW_DIR
    _protection_dir = protection_dir or _DEFAULT_PROTECTION_DIR

    print(_SEP)
    print("PROTECTED-ENTRY PREVIEW — NO ORDERS SENT — NO STOP ENDPOINT CALLED")
    print("TASK-014Q: Demo New-entry Protected Entry / Stop-loss Policy")
    print(_SEP)

    review = load_latest_review(_review_dir)
    if review is None:
        print("\n[FAIL CLOSED] latest_new_entry_review.json not found or unreadable.")
        print(f"  Expected: {_review_dir / 'latest_new_entry_review.json'}")
        print("  Run: python scripts/preview_demo_new_entry_review.py "
              "--from-latest-reconciliation --allow-real-market-network "
              "--write-report")
        print(_SEP)
        return 1

    ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

    plan = build_protected_entry_plan(
        review=review, symbol=symbol, timestamp_utc=ts_utc,
    )

    print(f"\n  review_source : {_review_dir / 'latest_new_entry_review.json'}")
    print()
    _print_plan(plan)
    print(_SEP)

    if write_report:
        _write_report(plan, _protection_dir)

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Preview a Demo new-entry protected-entry plan "
            "(stop-loss attachment policy). No orders sent."
        ),
    )
    parser.add_argument(
        "--from-latest-review",
        action="store_true",
        help=(
            "Read review JSON from "
            "outputs/demo_trading/new_entry_review/latest_new_entry_review.json"
        ),
    )
    parser.add_argument(
        "--symbol", default="", metavar="SYMBOL",
        help="Symbol to plan for (must appear in review.accepted_candidates).",
    )
    parser.add_argument(
        "--write-report", action="store_true",
        help="Write JSON + Markdown report to "
             "outputs/demo_trading/new_entry_protection/.",
    )
    args = parser.parse_args()
    sys.exit(run_preview(
        symbol=args.symbol,
        write_report=args.write_report,
    ))


if __name__ == "__main__":
    main()
