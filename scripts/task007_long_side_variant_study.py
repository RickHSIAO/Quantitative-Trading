"""Run TASK-007 long-side variant study.

This runner creates post-processing overlay outputs only. It reads official
run008, TASK-002, TASK-003, prices, and funding inputs, and does not rerun or
modify baseline, cost stress, attribution, strategy, signals, ranking,
universe, raw data, or data-quality policy.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.variants.task007 import Task007Config, run_task007, write_task007_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-date", default="20260515")
    args = parser.parse_args()

    config = Task007Config(output_date=args.output_date)
    result = run_task007(config)
    paths, schema_errors = write_task007_outputs(result, config)
    if schema_errors:
        print(json.dumps({
            "status": "FAIL",
            "schema_errors": schema_errors,
            "outputs": {key: str(path) for key, path in paths.items()},
        }, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
    fail_gates = result.summary_json["fail_gates"]
    if any(gate.get("triggered") for gate in fail_gates.values()):
        print(json.dumps({
            "status": "FAIL",
            "fail_gates": fail_gates,
            "outputs": {key: str(path) for key, path in paths.items()},
        }, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps({
        "status": "REVIEW_READY",
        "outputs": {key: str(path) for key, path in paths.items()},
        "fail_gates": fail_gates,
        "warning_gates": result.summary_json["warning_gates"],
        "reproducibility_hash": result.summary_json["reproducibility_hash"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
