"""
scripts/verify_demo_new_entry_postfill.py
TASK-014M: Post-fill verification CLI for Demo new-entry orders.

Reads the most recent Demo new-entry execution report and the most recent Demo
read-only smoke snapshot (optionally also the most recent new-entry review)
and re-confirms the actual exchange state matches what was submitted.

Detects (all PREVIEW + READ-ONLY):
  - last execution did not actually claim ORDER_SENT
  - selected symbol is missing from the live positions snapshot
  - actual side / qty / entry price disagree with the order that was sent
  - missing_stop_price (stop_price <= 0)  -- the headline TASK-014M gate
  - stale_price_mismatch (|actual_entry - preview_entry| / preview_entry > 5%)

This CLI is READ-ONLY:
  - no order endpoint is ever called
  - no position is ever modified
  - no secret value is ever printed
  - no live (production) endpoint is ever touched

Usage:
  python scripts/verify_demo_new_entry_postfill.py \\
    --from-latest-execution \\
    --from-latest-readonly-smoke \\
    [--from-latest-review] \\
    [--write-report] \\
    [--with-emergency-close-preview]

VPS flow:
  1. python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
  2. python3 scripts/verify_demo_new_entry_postfill.py \\
       --from-latest-execution --from-latest-readonly-smoke --write-report
  3. cat outputs/demo_trading/new_entry_postfill/latest_new_entry_postfill.md

Exit codes:
  0  Verification result produced (PASS or fail-closed report).
  1  Inputs missing / unreadable (no result produced).
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

from src.demo_new_entry_postfill_verify import (
    ACTION_EMERGENCY_PREV,
    ACTION_MANUAL_UI,
    ACTION_NONE_REQUIRED,
    PostFillVerificationResult,
    verify_postfill,
)

_SEP = "-" * 72
_DEFAULT_EXECUTION_DIR = ROOT / "outputs" / "demo_trading" / "new_entry_execution"
_DEFAULT_READONLY_DIR  = ROOT / "outputs" / "demo_trading" / "readonly_smoke"
_DEFAULT_REVIEW_DIR    = ROOT / "outputs" / "demo_trading" / "new_entry_review"
_DEFAULT_POSTFILL_DIR  = ROOT / "outputs" / "demo_trading" / "new_entry_postfill"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_latest_execution(execution_dir: Path) -> dict | None:
    """Load latest_new_entry_execution.json. Returns None if missing/unreadable."""
    path = execution_dir / "latest_new_entry_execution.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_latest_readonly_smoke(readonly_dir: Path) -> dict | None:
    """Load latest_smoke.json. Returns None if missing/unreadable."""
    path = readonly_dir / "latest_smoke.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_latest_review(review_dir: Path) -> dict | None:
    """Load latest_new_entry_review.json. Returns None if missing/unreadable."""
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

def _write_postfill_report(
    result:     PostFillVerificationResult,
    output_dir: Path,
    ts_utc:     str,
) -> None:
    """Write timestamped + latest JSON and Markdown post-fill verification reports."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ts_safe     = ts_utc.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "")
    json_path   = output_dir / f"{ts_safe}_new_entry_postfill.json"
    json_latest = output_dir / "latest_new_entry_postfill.json"
    md_path     = output_dir / f"{ts_safe}_new_entry_postfill.md"
    md_latest   = output_dir / "latest_new_entry_postfill.md"

    data      = result.to_dict()
    json_text = json.dumps(data, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    status_str = "FAIL_CLOSED" if result.fail_closed else "PASS"

    md_lines = [
        "# Demo New-entry Post-fill Verification Report",
        "",
        f"timestamp: `{result.timestamp_utc}`  ",
        f"mode: `postfill_verify`  ",
        f"status: **{status_str}**  ",
        f"recommended_action: `{result.recommended_action}`  ",
        "",
        "## Inputs",
        "",
        "| field | value |",
        "|---|---|",
        f"| execution_loaded | {result.execution_loaded} |",
        f"| execution_timestamp | {result.execution_timestamp or '(none)'} |",
        f"| readonly_loaded | {result.readonly_loaded} |",
        f"| readonly_timestamp | {result.readonly_timestamp or '(none)'} |",
        f"| review_loaded | {result.review_loaded} |",
        f"| review_timestamp | {result.review_timestamp or '(none)'} |",
        "",
        "## Expected vs Actual",
        "",
        "| field | expected | actual |",
        "|---|---|---|",
        f"| selected_symbol | {result.selected_symbol} | {result.selected_symbol} |",
        f"| side | {result.expected_side} | {result.actual_side or '(none)'} |",
        f"| qty | {result.expected_qty} | {result.actual_qty} |",
        f"| entry_price | {result.expected_entry_reference_price} | {result.actual_entry_price} |",
        f"| stop_price | (>0 required) | {result.actual_stop_price} |",
        "",
        "## Gate Outcomes",
        "",
        "| field | value |",
        "|---|---|",
        f"| last_execution_status | {result.last_execution_status} |",
        f"| position_found | {result.position_found} |",
        f"| side_mismatch | {result.side_mismatch} |",
        f"| qty_mismatch | {result.qty_mismatch} |",
        f"| entry_price_deviation_pct | {round(result.entry_price_deviation_pct, 4)} |",
        f"| stale_price_threshold_pct | {result.stale_price_threshold_pct} |",
        f"| stale_price_mismatch | {result.stale_price_mismatch} |",
        f"| missing_stop_price | {result.missing_stop_price} |",
        f"| new_entry_allowed | {result.new_entry_allowed} |",
        f"| fail_closed | {result.fail_closed} |",
        "",
    ]
    if result.fail_closed_reasons:
        md_lines += ["## Fail-closed Reasons", ""]
        for r in result.fail_closed_reasons:
            md_lines.append(f"- {r}")
        md_lines.append("")
    if result.emergency_close_preview:
        md_lines += [
            "## Emergency Close-only PREVIEW (NOT executed)",
            "",
            "| field | value |",
            "|---|---|",
        ]
        for k in [
            "symbol", "position_side", "close_order_side", "order_type",
            "qty", "reference_entry_price", "reduce_only", "preview_only",
            "confirmation_required", "order_sent", "order_endpoint_called",
            "no_orders_sent", "no_position_modified", "reason",
            "next_required_task",
        ]:
            md_lines.append(f"| {k} | {result.emergency_close_preview.get(k)} |")
        md_lines.append("")
        md_lines.append(
            "> This is a PREVIEW only. No close order was submitted. "
            "Actual emergency close execution is reserved for TASK-014N."
        )
        md_lines.append("")
    md_lines += [
        "## Safety Invariants",
        "",
        f"- no_orders_sent: `{result.no_orders_sent}`",
        f"- order_endpoint_called: `{result.order_endpoint_called}`",
        f"- no_position_modified: `{result.no_position_modified}`",
        f"- no_live_endpoint: `{result.no_live_endpoint}`",
        f"- no_batch_order: `{result.no_batch_order}`",
        f"- no_close_only_path: `{result.no_close_only_path}`",
        f"- secret_value_observed: `{result.secret_value_observed}`",
        "",
        "> This report is READ-ONLY. No order was sent, no position was modified,",
        "> no secret was observed, no live endpoint was contacted.",
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

def _print_result(result: PostFillVerificationResult) -> None:
    print(f"  execution_loaded            : {result.execution_loaded}")
    print(f"  execution_timestamp         : {result.execution_timestamp or '(none)'}")
    print(f"  readonly_loaded             : {result.readonly_loaded}")
    print(f"  readonly_timestamp          : {result.readonly_timestamp or '(none)'}")
    print(f"  review_loaded               : {result.review_loaded}")
    print(f"  review_timestamp            : {result.review_timestamp or '(none)'}")
    print(f"  last_execution_status       : {result.last_execution_status}")
    print(f"  selected_symbol             : {result.selected_symbol}")
    print(f"  expected_side / order_side  : {result.expected_side} / {result.expected_order_side}")
    print(f"  expected_qty                : {result.expected_qty}")
    print(f"  expected_entry_reference    : {result.expected_entry_reference_price}")
    print(f"  position_found              : {result.position_found}")
    print(f"  actual_side                 : {result.actual_side or '(none)'}")
    print(f"  actual_qty                  : {result.actual_qty}")
    print(f"  actual_entry_price          : {result.actual_entry_price}")
    print(f"  actual_stop_price           : {result.actual_stop_price}")
    print(f"  side_mismatch               : {result.side_mismatch}")
    print(f"  qty_mismatch                : {result.qty_mismatch}")
    print(f"  entry_price_deviation_pct   : {round(result.entry_price_deviation_pct, 4)}")
    print(f"  stale_price_threshold_pct   : {result.stale_price_threshold_pct}")
    print(f"  stale_price_mismatch        : {result.stale_price_mismatch}")
    print(f"  missing_stop_price          : {result.missing_stop_price}")
    print(f"  new_entry_allowed           : {result.new_entry_allowed}")
    print(f"  fail_closed                 : {result.fail_closed}")
    if result.fail_closed_reasons:
        print(f"  fail_closed_reasons         : {result.fail_closed_reasons}")
    print(f"  recommended_action          : {result.recommended_action}")
    if result.emergency_close_preview:
        ep = result.emergency_close_preview
        print(
            f"  emergency_close_preview     : "
            f"{ep.get('symbol')} / {ep.get('position_side')} -> "
            f"{ep.get('close_order_side')} qty={ep.get('qty')} "
            f"reduce_only={ep.get('reduce_only')} preview_only={ep.get('preview_only')}"
        )
    print(f"  no_orders_sent              : {result.no_orders_sent}")
    print(f"  order_endpoint_called       : {result.order_endpoint_called}")
    print(f"  no_position_modified        : {result.no_position_modified}")
    print(f"  no_live_endpoint            : {result.no_live_endpoint}")
    print(f"  no_batch_order              : {result.no_batch_order}")
    print(f"  no_close_only_path          : {result.no_close_only_path}")
    print(f"  secret_value_observed       : {result.secret_value_observed}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_verify(
    write_report:                  bool = False,
    with_emergency_close_preview:  bool = False,
    execution_dir:                 Path | None = None,
    readonly_dir:                  Path | None = None,
    review_dir:                    Path | None = None,
    postfill_dir:                  Path | None = None,
) -> int:
    """
    Run the post-fill verification.

    Returns 0 when a verification result is produced (PASS or fail-closed).
    Returns 1 only when required inputs are missing/unreadable.
    """
    _exec_dir     = execution_dir or _DEFAULT_EXECUTION_DIR
    _readonly_dir = readonly_dir  or _DEFAULT_READONLY_DIR
    _review_dir   = review_dir    or _DEFAULT_REVIEW_DIR
    _postfill_dir = postfill_dir  or _DEFAULT_POSTFILL_DIR

    print(_SEP)
    print("POST-FILL VERIFICATION — READ-ONLY — DEMO ENDPOINT ONLY")
    print("TASK-014M: Demo New-entry Post-fill Verification")
    print(_SEP)

    execution = load_latest_execution(_exec_dir)
    if execution is None:
        print("\n[FAIL CLOSED] latest_new_entry_execution.json not found or unreadable.")
        print(f"  Expected: {_exec_dir / 'latest_new_entry_execution.json'}")
        print("  Run: python scripts/execute_demo_new_entry.py "
              "--from-latest-review --symbol <S> --confirm-token ... --execute-new-entry --write-report")
        print(_SEP)
        return 1

    readonly = load_latest_readonly_smoke(_readonly_dir)
    if readonly is None:
        print("\n[FAIL CLOSED] latest_smoke.json not found or unreadable.")
        print(f"  Expected: {_readonly_dir / 'latest_smoke.json'}")
        print("  Run: python scripts/preview_demo_readonly_runtime.py "
              "--real-readonly --write-report")
        print(_SEP)
        return 1

    review = load_latest_review(_review_dir)

    print(f"\n  execution_source : {_exec_dir / 'latest_new_entry_execution.json'}")
    print(f"  readonly_source  : {_readonly_dir / 'latest_smoke.json'}")
    if review is not None:
        print(f"  review_source    : {_review_dir / 'latest_new_entry_review.json'}")
    else:
        print(f"  review_source    : (not loaded — stale-price deviation cannot be computed)")
    print(f"  emit_emergency_close_preview: {with_emergency_close_preview}")

    result = verify_postfill(
        execution=execution,
        readonly_snapshot=readonly,
        review=review,
        emit_emergency_close_preview=with_emergency_close_preview,
    )

    print()
    _print_result(result)
    print(_SEP)

    if write_report:
        ts_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_postfill_report(result, _postfill_dir, ts_utc)

    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Post-fill verification for the most recent Demo new-entry order. "
            "READ-ONLY: never sends an order, never modifies a position, "
            "never prints secrets, never contacts the live (production) endpoint."
        )
    )
    parser.add_argument(
        "--from-latest-execution",
        action="store_true",
        help=(
            "Read execution result from "
            "outputs/demo_trading/new_entry_execution/latest_new_entry_execution.json"
        ),
    )
    parser.add_argument(
        "--from-latest-readonly-smoke",
        action="store_true",
        help=(
            "Read read-only smoke snapshot from "
            "outputs/demo_trading/readonly_smoke/latest_smoke.json"
        ),
    )
    parser.add_argument(
        "--from-latest-review",
        action="store_true",
        help=(
            "Also read review file from "
            "outputs/demo_trading/new_entry_review/latest_new_entry_review.json "
            "(used to recover the preview entry_reference_price for "
            "stale-price-mismatch detection). Loaded by default; this flag is "
            "present for symmetry with the other --from-latest-* arguments."
        ),
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write JSON + Markdown report to outputs/demo_trading/new_entry_postfill/.",
    )
    parser.add_argument(
        "--with-emergency-close-preview",
        action="store_true",
        help=(
            "On missing_stop_price + position_found, emit an emergency close-only "
            "PREVIEW dict in the result (reduce_only=True, preview_only=True, "
            "order_sent=False). Actual execution of such a close is reserved for "
            "TASK-014N and intentionally NOT performed here."
        ),
    )
    args = parser.parse_args()
    sys.exit(run_verify(
        write_report=args.write_report,
        with_emergency_close_preview=args.with_emergency_close_preview,
    ))


if __name__ == "__main__":
    main()
