"""TASK-014BK preview CLI -- final pre-execution checklist smoke runner.

Runs the BK checklist offline and prints a short summary. Optionally
writes the JSON + Markdown report under the BK output directory.

Exit code 0 when ``all_passed`` is True; 1 otherwise.
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
            "TASK-014BK -- demo-only tiny execution adapter final "
            "pre-execution checklist preview"
        )
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="write JSON + Markdown report to the BK output directory",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="override the BK output directory (default: outputs/demo_trading/...)",
    )
    parser.add_argument(
        "--print-items",
        action="store_true",
        help="print every checklist item line (default: only failures)",
    )
    args = parser.parse_args(argv)

    from src import (
        demo_only_tiny_execution_adapter_final_pre_execution_checklist as bk,
    )

    report = bk.run_final_pre_execution_checklist()

    print(
        f"task_id={report.task_id} identity={report.identity} "
        f"phase={report.phase}"
    )
    print(
        f"upstream_tasks={','.join(report.upstream_tasks)} "
        f"next_required_task={report.next_required_task}"
    )
    print(
        f"checklist_contract_version={report.checklist_contract_version} "
        f"is_review_chain_suffix={report.is_review_chain_suffix}"
    )
    print(
        f"bh_identity={report.bh_identity} bi_identity={report.bi_identity} "
        f"bj_identity={report.bj_identity}"
    )
    print(
        f"bi_dry_run_total={report.bi_dry_run_total_cases} "
        f"bi_all_match={report.bi_dry_run_all_match} "
        f"bj_integration_total={report.bj_integration_total_cases} "
        f"bj_all_match={report.bj_integration_all_match}"
    )
    print(
        f"total={report.total_items} passed={report.passed_items} "
        f"failed={report.failed_items} all_passed={report.all_passed}"
    )

    for item in report.items:
        if args.print_items or not item.passed:
            marker = "OK  " if item.passed else "FAIL"
            print(f"  [{marker}] {item.item_id} :: {item.category} :: {item.detail}")

    if args.write_report:
        paths = bk.write_report(report, output_dir=args.output_dir)
        print("wrote:")
        for key, path in paths.items():
            print(f"  {key}: {path}")

    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
