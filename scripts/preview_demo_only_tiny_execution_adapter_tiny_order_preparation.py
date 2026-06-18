"""TASK-014BL preview CLI -- tiny order preparation smoke runner.

Runs the BL preparation pipeline offline and prints a short summary.
Optionally writes the JSON + Markdown report under the BL output
directory.

Exit code 0 when the report's ``all_passed`` is True; 1 otherwise.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

os.environ.setdefault("COLUMNS", "400")
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "TASK-014BL -- demo-only tiny execution adapter tiny order "
            "preparation preview"
        )
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="write JSON + Markdown report to the BL output directory",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="override the BL output directory (default: outputs/demo_trading/...)",
    )
    parser.add_argument(
        "--symbol",
        default=None,
        help="override request symbol (default: SOLUSDT)",
    )
    parser.add_argument(
        "--side",
        default=None,
        help="override request side (default: Buy)",
    )
    parser.add_argument(
        "--qty",
        default=None,
        help="override request qty (default: 0.01)",
    )
    parser.add_argument(
        "--mark-price",
        default=None,
        help="override request mark price (default: 100)",
    )
    args = parser.parse_args(argv)

    from src import (
        demo_only_tiny_execution_adapter_tiny_order_preparation as bl,
    )

    kwargs: dict[str, object] = {}
    if args.symbol is not None:
        kwargs["symbol"] = args.symbol
    if args.side is not None:
        kwargs["side"] = args.side
    if args.qty is not None:
        kwargs["qty"] = args.qty
    if args.mark_price is not None:
        kwargs["mark_price"] = args.mark_price

    report = bl.run_tiny_order_preparation(**kwargs)

    print(
        f"task_id={report.task_id} identity={report.identity} "
        f"phase={report.phase}"
    )
    print(
        f"upstream_tasks={','.join(report.upstream_tasks)} "
        f"next_required_task={report.next_required_task}"
    )
    print(
        f"target_future_task={report.target_future_task} "
        f"is_review_chain_suffix={report.is_review_chain_suffix}"
    )
    print(
        f"preparation_contract_version={report.preparation_contract_version}"
    )
    print(
        f"bk_checklist total={report.bk_checklist_total_items} "
        f"passed={report.bk_checklist_passed_items} "
        f"failed={report.bk_checklist_failed_items} "
        f"all_passed={report.bk_checklist_all_passed}"
    )
    print(
        f"bj_integration ok={report.bj_integration_ok} "
        f"rejection_step={report.bj_integration_rejection_step!r} "
        f"rejection_reason={report.bj_integration_rejection_reason!r}"
    )
    if report.packet is None:
        print("packet=None")
    else:
        pkt = report.packet
        print(
            f"packet symbol={pkt.symbol} side={pkt.side} qty={pkt.qty} "
            f"mark_price={pkt.mark_price} notional={pkt.notional_estimate} "
            f"order_link_id={pkt.order_link_id!r}"
        )
        print(
            f"packet audit_response_status={pkt.audit_response_status!r} "
            f"packet_is_not_execution_authorization="
            f"{pkt.packet_is_not_execution_authorization}"
        )
    print(f"all_passed={report.all_passed}")

    if args.write_report:
        paths = bl.write_report(report, output_dir=args.output_dir)
        print("wrote:")
        for key, path in paths.items():
            print(f"  {key}: {path}")

    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
