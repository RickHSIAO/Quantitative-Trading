"""TASK-014BI preview CLI — demo-only tiny execution adapter payload
dry-run.

Runs the canonical BI dry-run case table offline and optionally writes
a JSON + Markdown report (latest_* + timestamped). No network, no
endpoint, no secret read.

Exit codes:
    0 — every case matched its expectation
    1 — at least one outcome did not match expectation
"""

from __future__ import annotations

import argparse
import json
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

from src import demo_only_tiny_execution_adapter_payload_dry_run as bi  # noqa: E402


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "TASK-014BI demo-only tiny execution adapter payload dry-run "
            "(offline; consumes the TASK-014BH module directly; does NOT send)."
        ),
    )
    p.add_argument(
        "--write-report",
        action="store_true",
        help="Write JSON + Markdown report (latest_* + timestamped).",
    )
    p.add_argument(
        "--output-dir",
        default=None,
        help=f"Output dir for reports (default: {bi.DEFAULT_OUTPUT_DIR}).",
    )
    p.add_argument(
        "--print-payloads",
        action="store_true",
        help="Print full audit dict for each built payload.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    print(
        "TASK-014BI demo-only tiny execution adapter payload dry-run "
        "(offline)"
    )
    print(
        f"upstream_task = {bi.UPSTREAM_TASK} | next_required_task = "
        f"{bi.NEXT_REQUIRED_TASK} (implementation path; NOT a "
        "review-chain suffix)"
    )

    report = bi.run_dry_run()

    print(
        f"summary: total={report.total_cases} built={report.built_cases} "
        f"rejected={report.rejected_cases} "
        f"unexpected={report.unexpected_outcomes} "
        f"all_match={report.all_match_expectation}"
    )

    for outcome in report.outcomes:
        marker = "OK " if outcome.matches_expectation else "FAIL"
        print(
            f"  [{marker}] {outcome.case_id} expected={outcome.expected} "
            f"actual={outcome.actual} — {outcome.description}"
        )
        if outcome.actual == "rejected" and outcome.rejection_reason:
            print(f"        rejection_reason: {outcome.rejection_reason}")
        if args.print_payloads and outcome.payload_audit:
            print(
                "        payload_audit: "
                + json.dumps(dict(outcome.payload_audit), sort_keys=True)
            )

    if args.write_report:
        output_dir = pathlib.Path(args.output_dir) if args.output_dir else None
        paths = bi.write_report(report, output_dir=output_dir)
        print("wrote reports:")
        for key, path in sorted(paths.items()):
            print(f"  {key}: {path}")

    return 0 if report.all_match_expectation else 1


if __name__ == "__main__":
    raise SystemExit(main())
