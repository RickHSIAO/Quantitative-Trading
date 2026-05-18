"""Run TASK-007b weight cap + same-side redistribution overlays.

This runner creates post-processing overlay outputs only. It reads official
run008, TASK-002 realistic_combo, and TASK-007 outputs, and does not rerun or
modify baseline, cost stress, attribution, strategy, signals, ranking,
universe, raw data, or data-quality policy.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.variants.task007b import Task007bConfig, run_task007b, write_task007b_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-date", default="20260516")
    args = parser.parse_args()

    config = Task007bConfig(output_date=args.output_date)
    result = run_task007b(config)
    paths, schema_errors = write_task007b_outputs(result, config)
    fail_gates = result.gate_report["fail_gates"]
    if schema_errors:
        print(json.dumps({
            "status": "FAIL",
            "schema_errors": schema_errors,
            "outputs": {key: str(path) for key, path in paths.items()},
        }, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
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
        "warning_gates": result.gate_report["warning_gates"],
        "reproducibility_hash": result.summary_json["reproducibility_hash"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
