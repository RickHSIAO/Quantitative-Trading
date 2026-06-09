"""
scripts/execute_demo_protected_new_entry_mock.py
TASK-014S: Protected New-entry Orchestrator CLI (dry-run / mock-chain only).

Usage (DRY-RUN — default, no network at all):
  python scripts/execute_demo_protected_new_entry_mock.py \\
    --from-latest-review \\
    --from-latest-protection \\
    --symbol SOLUSDT \\
    [--write-report]

Usage (MOCK CHAIN — still no network, synthetic envelope chain):
  python scripts/execute_demo_protected_new_entry_mock.py \\
    --from-latest-review \\
    --from-latest-protection \\
    --symbol SOLUSDT \\
    --confirm-token CONFIRM_DEMO_PROTECTED_ENTRY_YYYYMMDD \\
    --mock-chain \\
    --write-report

Reads:
  outputs/demo_trading/new_entry_review/latest_new_entry_review.json
  outputs/demo_trading/new_entry_protection/latest_new_entry_protection.json

Writes (when --write-report):
  outputs/demo_trading/protected_new_entry/{ts}_protected_new_entry.json
  outputs/demo_trading/protected_new_entry/{ts}_protected_new_entry.md
  outputs/demo_trading/protected_new_entry/latest_protected_new_entry.json
  outputs/demo_trading/protected_new_entry/latest_protected_new_entry.md

IMPORTANT:
  - There is NO --execute-protected-entry flag.  TASK-014S is intentionally
    dry-run + mock-only.  Real protected entry execution is reserved for
    TASK-014T+ (after a real /v5/position/trading-stop endpoint contract
    probe + permission gate).
  - --mock-chain does NOT open a socket; it produces a synthetic entry +
    stop-attach envelope chain.
  - TASK-014L sender G20 (protected_entry_policy_missing) is intentionally
    NOT lifted by this orchestrator.

Exit codes:
  0  result produced (dry-run allowed OR mock-chain success / mock fail-closed)
  1  review missing / protection missing / required arg missing
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

from src.demo_protected_new_entry_orchestrator import (
    DemoProtectedNewEntryOrchestrator,
    ProtectedEntryChainResult,
    STATUS_DRY_RUN_ALLOWED,
    STATUS_MOCK_SUCCESS,
    STATUS_MOCK_FAIL_CLOSED,
)

_SEP = "-" * 72
_DEFAULT_REVIEW_DIR     = ROOT / "outputs" / "demo_trading" / "new_entry_review"
_DEFAULT_PROTECTION_DIR = ROOT / "outputs" / "demo_trading" / "new_entry_protection"
_DEFAULT_CHAIN_DIR      = ROOT / "outputs" / "demo_trading" / "protected_new_entry"


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_latest_review(review_dir: Path) -> dict | None:
    return _load_json(review_dir / "latest_new_entry_review.json")


def load_latest_protection(protection_dir: Path) -> dict | None:
    return _load_json(protection_dir / "latest_new_entry_protection.json")


def _print_result(r: ProtectedEntryChainResult) -> None:
    print(f"  mode                              : {r.mode}")
    print(f"  selected_symbol                   : {r.selected_symbol}")
    print(f"  selected_side                     : {r.selected_side}")
    print(f"  qty                               : {r.qty}")
    print(f"  entry_reference_price             : {r.entry_reference_price}")
    print(f"  stop_price                        : {r.stop_price}")
    print(f"  realtime_price_guard_verified     : {r.realtime_price_guard_verified}")
    print(f"  protection_status                 : {r.protection_status}")
    print(f"  stop_payload_preview_only         : {r.stop_payload_preview_only}")
    print(f"  mock_entry_order_sent             : {r.mock_entry_order_sent}")
    print(f"  mock_order_id                     : {r.mock_order_id or '(none)'}")
    print(f"  mock_stop_attached                : {r.mock_stop_attached}")
    print(f"  mock_stop_attach_id               : {r.mock_stop_attach_id or '(none)'}")
    print(f"  mock_final_position_stop_price    : {r.mock_final_position_stop_price}")
    print(f"  missing_stop_price                : {r.missing_stop_price}")
    print(f"  protected_entry_status            : {r.protected_entry_status}")
    print(f"  fail_closed                       : {r.fail_closed}")
    print(f"  recommended_action                : {r.recommended_action or '(none)'}")
    print(f"  stop_attach_endpoint              : {r.stop_attach_endpoint}  (NOT invoked)")
    print(f"  order_create_endpoint             : {r.order_create_endpoint}  (NOT invoked)")
    print(f"  no_orders_sent                    : {r.no_orders_sent}")
    print(f"  order_endpoint_called             : {r.order_endpoint_called}")
    print(f"  stop_endpoint_called              : {r.stop_endpoint_called}")
    print(f"  no_position_modified              : {r.no_position_modified}")
    print(f"  no_live_endpoint                  : {r.no_live_endpoint}")
    print(f"  no_batch_order                    : {r.no_batch_order}")
    print(f"  no_close_only_path                : {r.no_close_only_path}")
    print(f"  emergency_close_invoked           : {r.emergency_close_invoked}")
    print(f"  secret_value_observed             : {r.secret_value_observed}")
    print(f"  confirm_token_prefix              : {r.confirm_token_prefix or '(none)'}")
    print(f"  confirm_token_valid               : {r.confirm_token_valid}")
    print(f"  status                            : {r.status}")
    if r.blocked_gates:
        print(f"  blocked_gates                     : {r.blocked_gates}")
    if r.stop_payload_preview:
        print("  stop_payload_preview:")
        for k, v in r.stop_payload_preview.items():
            print(f"    {k}: {v}")
    if r.mock_post_fill_position:
        print("  mock_post_fill_position:")
        for k, v in r.mock_post_fill_position.items():
            print(f"    {k}: {v}")


def _write_report(r: ProtectedEntryChainResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_safe = (
        r.timestamp_utc
        .replace(":", "")
        .replace("-", "")
        .replace("T", "_")
        .replace("Z", "")
    )
    json_path   = output_dir / f"{ts_safe}_protected_new_entry.json"
    json_latest = output_dir / "latest_protected_new_entry.json"
    md_path     = output_dir / f"{ts_safe}_protected_new_entry.md"
    md_latest   = output_dir / "latest_protected_new_entry.md"

    data      = r.to_dict()
    json_text = json.dumps(data, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    md_lines = [
        "# Demo Protected New-entry Mock Chain Report (TASK-014S)",
        "",
        f"timestamp: `{r.timestamp_utc}`  ",
        f"mode: `{r.mode}`  ",
        f"status: **{r.status}**  ",
        f"protected_entry_status: `{r.protected_entry_status}`  ",
        "",
        "## Summary",
        "",
        "| field | value |",
        "|---|---|",
        f"| selected_symbol | {r.selected_symbol} |",
        f"| selected_side | {r.selected_side} |",
        f"| qty | {r.qty} |",
        f"| entry_reference_price | {r.entry_reference_price} |",
        f"| stop_price | {r.stop_price} |",
        f"| realtime_price_guard_verified | {r.realtime_price_guard_verified} |",
        f"| protection_status | {r.protection_status} |",
        f"| mock_entry_order_sent | {r.mock_entry_order_sent} |",
        f"| mock_order_id | {r.mock_order_id or '(none)'} |",
        f"| mock_stop_attached | {r.mock_stop_attached} |",
        f"| mock_stop_attach_id | {r.mock_stop_attach_id or '(none)'} |",
        f"| mock_final_position_stop_price | {r.mock_final_position_stop_price} |",
        f"| missing_stop_price | {r.missing_stop_price} |",
        f"| fail_closed | {r.fail_closed} |",
        f"| recommended_action | {r.recommended_action or '(none)'} |",
        f"| order_create_endpoint | `{r.order_create_endpoint}` (NOT invoked) |",
        f"| stop_attach_endpoint | `{r.stop_attach_endpoint}` (NOT invoked) |",
        f"| next_required_task | {r.next_required_task} |",
        "",
    ]
    if r.blocked_gates:
        md_lines += ["## Blocked Gates", ""]
        for g in r.blocked_gates:
            md_lines.append(f"- {g}")
        md_lines.append("")
    if r.stop_payload_preview:
        md_lines += [
            "## Stop Payload Preview (NOT sent)",
            "",
            "```json",
            json.dumps(r.stop_payload_preview, indent=2),
            "```",
            "",
        ]
    if r.mock_post_fill_position:
        md_lines += [
            "## Mock Post-fill Position (synthetic, no real position)",
            "",
            "```json",
            json.dumps(r.mock_post_fill_position, indent=2),
            "```",
            "",
        ]
    md_lines += [
        "## Safety Invariants",
        "",
        f"- no_orders_sent: `{r.no_orders_sent}`",
        f"- order_endpoint_called: `{r.order_endpoint_called}`",
        f"- stop_endpoint_called: `{r.stop_endpoint_called}`",
        f"- no_position_modified: `{r.no_position_modified}`",
        f"- no_live_endpoint: `{r.no_live_endpoint}`",
        f"- no_batch_order: `{r.no_batch_order}`",
        f"- no_close_only_path: `{r.no_close_only_path}`",
        f"- emergency_close_invoked: `{r.emergency_close_invoked}`",
        f"- secret_value_observed: `{r.secret_value_observed}`",
        "",
        "> This orchestrator NEVER opens a socket.",
        "> No orders sent; no positions modified; no stop endpoint called.",
        "> TASK-014L sender G20 (protected_entry_policy_missing) is NOT",
        "> lifted by this task.  Real attachment is reserved for TASK-014T+.",
        "",
    ]
    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    md_latest.write_text(md_text, encoding="utf-8")

    print(f"  report: {json_latest}")
    print(f"  report: {md_latest}")


def run_execute(
    symbol:          str  = "",
    confirm_token:   str  = "",
    mock_chain:      bool = False,
    write_report:    bool = False,
    review_dir:      Path | None = None,
    protection_dir:  Path | None = None,
    chain_dir:       Path | None = None,
    _now:            datetime | None = None,
) -> int:
    _review_dir     = review_dir     or _DEFAULT_REVIEW_DIR
    _protection_dir = protection_dir or _DEFAULT_PROTECTION_DIR
    _chain_dir      = chain_dir      or _DEFAULT_CHAIN_DIR

    print(_SEP)
    if mock_chain:
        print("MOCK CHAIN — NO NETWORK — SYNTHETIC ENTRY + STOP ATTACH")
    else:
        print("DRY RUN — NO NETWORK — PROTECTED-NEW-ENTRY CHAIN VALIDATION")
    print("TASK-014S: Demo Protected New-entry Orchestrator")
    print(_SEP)

    review     = load_latest_review(_review_dir)
    protection = load_latest_protection(_protection_dir)
    if review is None:
        print("\n[FAIL CLOSED] latest_new_entry_review.json not found or unreadable.")
        print(f"  Expected: {_review_dir / 'latest_new_entry_review.json'}")
        print(_SEP)
        return 1
    if protection is None:
        print("\n[FAIL CLOSED] latest_new_entry_protection.json not found or unreadable.")
        print(f"  Expected: {_protection_dir / 'latest_new_entry_protection.json'}")
        print(_SEP)
        return 1

    if not symbol:
        print("\n[FAIL CLOSED] --symbol is required.")
        print(_SEP)
        return 1

    if mock_chain and not confirm_token:
        print("\n[FAIL CLOSED] --confirm-token is required for --mock-chain.")
        print("  Pattern: CONFIRM_DEMO_PROTECTED_ENTRY_YYYYMMDD (today UTC)")
        print(_SEP)
        return 1

    print(f"\n  mode             : {'mock_chain' if mock_chain else 'dry_run'}")
    print(f"  symbol           : {symbol}")
    if confirm_token:
        print(f"  confirm_token    : {confirm_token[:8]}***")
    print(f"  review_source    : {_review_dir / 'latest_new_entry_review.json'}")
    print(f"  protection_src   : {_protection_dir / 'latest_new_entry_protection.json'}")

    orchestrator = DemoProtectedNewEntryOrchestrator()
    result = orchestrator.submit_chain(
        review=review,
        protection=protection,
        symbol=symbol,
        confirm_token=confirm_token,
        mock_chain=mock_chain,
        _now=_now,
    )

    print()
    _print_result(result)
    print(_SEP)

    if write_report:
        _write_report(result, _chain_dir)

    return 1 if result.blocked_gates else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Demo protected new-entry orchestrator — dry-run / mock-chain only "
            "(no network, no live endpoint, no orders / positions modified)."
        ),
    )
    parser.add_argument("--from-latest-review", action="store_true",
                        help="Read review JSON from outputs/.../new_entry_review/.")
    parser.add_argument("--from-latest-protection", action="store_true",
                        help="Read protection JSON from outputs/.../new_entry_protection/.")
    parser.add_argument("--symbol", default="", metavar="SYMBOL",
                        help="Symbol to chain (must match review + protection).")
    parser.add_argument("--confirm-token", default="", metavar="TOKEN",
                        help=("Manual confirmation token (only required for "
                              "--mock-chain). Pattern: CONFIRM_DEMO_PROTECTED_"
                              "ENTRY_YYYYMMDD (today UTC)."))
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Dry-run validation only (default; no network, "
                             "no mock entry/attach).")
    parser.add_argument("--mock-chain", action="store_true",
                        help=("Run the synthetic entry + stop-attach chain. "
                              "Still does NOT open a socket; no real attach "
                              "or order occurs."))
    parser.add_argument("--write-report", action="store_true",
                        help="Write JSON + Markdown report to "
                             "outputs/demo_trading/protected_new_entry/.")
    args = parser.parse_args()
    sys.exit(run_execute(
        symbol=args.symbol,
        confirm_token=args.confirm_token,
        mock_chain=args.mock_chain,
        write_report=args.write_report,
    ))


if __name__ == "__main__":
    main()
