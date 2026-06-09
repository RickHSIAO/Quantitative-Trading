"""
scripts/execute_demo_stop_loss_attachment.py
TASK-014R: Demo Stop-loss Attachment Sender CLI (dry-run / mock-execute only).

Usage (DRY-RUN — default, no network at all):
  python scripts/execute_demo_stop_loss_attachment.py \\
    --from-latest-protection \\
    --symbol SOLUSDT \\
    [--write-report]

Usage (MOCK execute — still no network, synthetic success envelope):
  python scripts/execute_demo_stop_loss_attachment.py \\
    --from-latest-protection \\
    --symbol SOLUSDT \\
    --confirm-token CONFIRM_DEMO_STOP_ATTACH_YYYYMMDD \\
    --mock-execute-stop \\
    --write-report

Reads:
  outputs/demo_trading/new_entry_protection/latest_new_entry_protection.json

Writes (when --write-report):
  outputs/demo_trading/stop_loss_attachment/{ts}_stop_loss_attachment.json
  outputs/demo_trading/stop_loss_attachment/{ts}_stop_loss_attachment.md
  outputs/demo_trading/stop_loss_attachment/latest_stop_loss_attachment.json
  outputs/demo_trading/stop_loss_attachment/latest_stop_loss_attachment.md

IMPORTANT:
  - There is NO --execute-stop-loss path here.  TASK-014R is intentionally
    dry-run + mock-only.  Real attachment is reserved for TASK-014S onwards.
  - --mock-execute-stop does not open a socket; it produces a synthetic
    success envelope so the report pipeline / downstream gate can be tested.
  - No live endpoint, no fallback, no secrets, no orders, no position
    modification.

Exit codes:
  0  result produced (dry-run or mock-success or mock-blocked)
  1  protection report missing / unreadable / no symbol / no token (mock)
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

from src.demo_stop_loss_attachment_sender import (
    DemoStopLossAttachmentSender,
    StopAttachmentResult,
)


_SEP = "-" * 72
_DEFAULT_PROTECTION_DIR = ROOT / "outputs" / "demo_trading" / "new_entry_protection"
_DEFAULT_ATTACHMENT_DIR = ROOT / "outputs" / "demo_trading" / "stop_loss_attachment"


def load_latest_protection(protection_dir: Path) -> dict | None:
    """Load latest_new_entry_protection.json. Returns None if missing/unreadable."""
    path = protection_dir / "latest_new_entry_protection.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _print_result(result: StopAttachmentResult) -> None:
    print(f"  mode                       : {result.mode}")
    print(f"  selected_symbol            : {result.selected_symbol}")
    print(f"  selected_side              : {result.selected_side}")
    print(f"  qty                        : {result.qty}")
    print(f"  entry_reference_price      : {result.entry_reference_price}")
    print(f"  stop_price                 : {result.stop_price}")
    print(f"  stop_order_side            : {result.stop_order_side}")
    print(f"  stop_trigger_direction     : {result.stop_trigger_direction}")
    print(f"  endpoint_family            : {result.endpoint_family}")
    print(f"  stop_attach_endpoint       : {result.stop_attach_endpoint}  (NOT invoked)")
    print(f"  payload_preview_only       : {result.payload_preview_only}")
    print(f"  execute_requested          : {result.execute_requested}")
    print(f"  mock_execute_requested     : {result.mock_execute_requested}")
    print(f"  mock_stop_attached         : {result.mock_stop_attached}")
    print(f"  stop_endpoint_called       : {result.stop_endpoint_called}")
    print(f"  order_endpoint_called      : {result.order_endpoint_called}")
    print(f"  no_orders_sent             : {result.no_orders_sent}")
    print(f"  no_position_modified       : {result.no_position_modified}")
    print(f"  no_live_endpoint           : {result.no_live_endpoint}")
    print(f"  no_batch_order             : {result.no_batch_order}")
    print(f"  no_close_only_path         : {result.no_close_only_path}")
    print(f"  secret_value_observed      : {result.secret_value_observed}")
    print(f"  confirm_token_prefix       : {result.confirm_token_prefix or '(none)'}")
    print(f"  confirm_token_valid        : {result.confirm_token_valid}")
    print(f"  status                     : {result.status}")
    if result.blocked_gates:
        print(f"  blocked_gates              : {result.blocked_gates}")
    if result.payload_preview:
        print("  payload_preview:")
        for k, v in result.payload_preview.items():
            print(f"    {k}: {v}")
    if result.mock_response:
        print("  mock_response:")
        for k, v in result.mock_response.items():
            print(f"    {k}: {v}")


def _write_attachment_report(
    result:     StopAttachmentResult,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_safe = (
        result.timestamp_utc
        .replace(":", "")
        .replace("-", "")
        .replace("T", "_")
        .replace("Z", "")
    )
    json_path   = output_dir / f"{ts_safe}_stop_loss_attachment.json"
    json_latest = output_dir / "latest_stop_loss_attachment.json"
    md_path     = output_dir / f"{ts_safe}_stop_loss_attachment.md"
    md_latest   = output_dir / "latest_stop_loss_attachment.md"

    data      = result.to_dict()
    json_text = json.dumps(data, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    md_lines = [
        "# Demo Stop-loss Attachment Report (TASK-014R)",
        "",
        f"timestamp: `{result.timestamp_utc}`  ",
        f"mode: `{result.mode}`  ",
        f"status: **{result.status}**  ",
        "",
        "## Summary",
        "",
        "| field | value |",
        "|---|---|",
        f"| selected_symbol | {result.selected_symbol} |",
        f"| selected_side | {result.selected_side} |",
        f"| qty | {result.qty} |",
        f"| entry_reference_price | {result.entry_reference_price} |",
        f"| stop_price | {result.stop_price} |",
        f"| stop_order_side | {result.stop_order_side} |",
        f"| stop_trigger_direction | {result.stop_trigger_direction} |",
        f"| endpoint_family | {result.endpoint_family} |",
        f"| stop_attach_endpoint | `{result.stop_attach_endpoint}` (NOT invoked) |",
        f"| payload_preview_only | {result.payload_preview_only} |",
        f"| execute_requested | {result.execute_requested} |",
        f"| mock_execute_requested | {result.mock_execute_requested} |",
        f"| mock_stop_attached | {result.mock_stop_attached} |",
        f"| confirm_token_valid | {result.confirm_token_valid} |",
        f"| next_required_task | {result.next_required_task} |",
        "",
    ]
    if result.blocked_gates:
        md_lines += ["## Blocked Gates", ""]
        for g in result.blocked_gates:
            md_lines.append(f"- {g}")
        md_lines.append("")
    if result.payload_preview:
        md_lines += [
            "## Payload Preview (NOT sent)",
            "",
            "```json",
            json.dumps(result.payload_preview, indent=2),
            "```",
            "",
            "> Excludes: takeProfit, leverage, transfer/withdraw/deposit, "
            "order-create fields (side/qty/orderType).",
            "",
        ]
    if result.mock_response:
        md_lines += [
            "## Mock Response (synthetic, no network)",
            "",
            "```json",
            json.dumps(result.mock_response, indent=2),
            "```",
            "",
        ]
    md_lines += [
        "## Safety Invariants",
        "",
        f"- stop_endpoint_called: `{result.stop_endpoint_called}`",
        f"- order_endpoint_called: `{result.order_endpoint_called}`",
        f"- no_orders_sent: `{result.no_orders_sent}`",
        f"- no_position_modified: `{result.no_position_modified}`",
        f"- no_live_endpoint: `{result.no_live_endpoint}`",
        f"- no_batch_order: `{result.no_batch_order}`",
        f"- no_close_only_path: `{result.no_close_only_path}`",
        f"- secret_value_observed: `{result.secret_value_observed}`",
        "",
        "> This sender NEVER opens a socket.",
        "> No orders sent; no positions modified; no stop endpoint called.",
        "> Real attachment is reserved for TASK-014S onwards.",
        "",
    ]
    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    md_latest.write_text(md_text, encoding="utf-8")

    print(f"  report: {json_latest}")
    print(f"  report: {md_latest}")


def run_execute(
    symbol:            str  = "",
    confirm_token:     str  = "",
    mock_execute_stop: bool = False,
    write_report:      bool = False,
    protection_dir:    Path | None = None,
    attachment_dir:    Path | None = None,
    _now:              datetime | None = None,
) -> int:
    _protection_dir = protection_dir or _DEFAULT_PROTECTION_DIR
    _attachment_dir = attachment_dir or _DEFAULT_ATTACHMENT_DIR

    print(_SEP)
    if mock_execute_stop:
        print("MOCK EXECUTE STOP — NO NETWORK — SYNTHETIC RESPONSE ONLY")
    else:
        print("DRY RUN — NO NETWORK — STOP-LOSS ATTACHMENT PAYLOAD PREVIEW")
    print("TASK-014R: Demo Stop-loss Attachment Sender")
    print(_SEP)

    protection = load_latest_protection(_protection_dir)
    if protection is None:
        print("\n[FAIL CLOSED] latest_new_entry_protection.json not found or unreadable.")
        print(f"  Expected: {_protection_dir / 'latest_new_entry_protection.json'}")
        print("  Run: python scripts/preview_demo_new_entry_protection.py "
              "--from-latest-review --symbol <SYMBOL> --write-report")
        print(_SEP)
        return 1

    if not symbol:
        plan_symbol = str(protection.get("selected_symbol", "") or "?")
        print("\n[FAIL CLOSED] --symbol is required.")
        print(f"  Protection report selected_symbol: {plan_symbol}")
        print(_SEP)
        return 1

    if mock_execute_stop and not confirm_token:
        print("\n[FAIL CLOSED] --confirm-token is required for --mock-execute-stop.")
        print("  Pattern: CONFIRM_DEMO_STOP_ATTACH_YYYYMMDD (today UTC)")
        print(_SEP)
        return 1

    print(f"\n  mode             : {'mock_execute_stop' if mock_execute_stop else 'dry_run'}")
    print(f"  symbol           : {symbol}")
    if confirm_token:
        print(f"  confirm_token    : {confirm_token[:8]}***")
    print(f"  protection_src   : {_protection_dir / 'latest_new_entry_protection.json'}")

    sender = DemoStopLossAttachmentSender()
    result = sender.submit_stop_attachment(
        protection=protection,
        symbol=symbol,
        confirm_token=confirm_token,
        mock_execute_stop=mock_execute_stop,
        _now=_now,
    )

    print()
    _print_result(result)
    print(_SEP)

    if write_report:
        _write_attachment_report(result, _attachment_dir)

    return 1 if result.blocked_gates else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Demo stop-loss attachment sender — dry-run / mock-execute only "
            "(no network, no live endpoint, no order/position changes)."
        ),
    )
    parser.add_argument(
        "--from-latest-protection",
        action="store_true",
        help=(
            "Read protection report from outputs/demo_trading/"
            "new_entry_protection/latest_new_entry_protection.json"
        ),
    )
    parser.add_argument(
        "--symbol", default="", metavar="SYMBOL",
        help="Symbol to attach stop-loss for (must match protection.selected_symbol).",
    )
    parser.add_argument(
        "--confirm-token", default="", metavar="TOKEN",
        help=(
            "Manual confirmation token (only required for --mock-execute-stop). "
            "Pattern: CONFIRM_DEMO_STOP_ATTACH_YYYYMMDD (today UTC)."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Dry-run preview only (default; no network, no mock response).",
    )
    parser.add_argument(
        "--mock-execute-stop", action="store_true",
        help=(
            "Emit a synthetic MOCK_STOP_ATTACH_SUCCESS envelope. Still does "
            "NOT open a socket; no real attach occurs."
        ),
    )
    parser.add_argument(
        "--write-report", action="store_true",
        help="Write JSON + Markdown report to outputs/demo_trading/stop_loss_attachment/.",
    )
    args = parser.parse_args()
    sys.exit(run_execute(
        symbol=args.symbol,
        confirm_token=args.confirm_token,
        mock_execute_stop=args.mock_execute_stop,
        write_report=args.write_report,
    ))


if __name__ == "__main__":
    main()
