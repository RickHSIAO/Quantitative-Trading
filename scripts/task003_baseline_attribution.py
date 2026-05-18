"""Run TASK-003 baseline attribution.

This script is read-only with respect to run008, TASK-002 outputs, raw data,
strategy, ranking, universe, and data-quality policy. It writes only TASK-003
attribution outputs and logs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.attribution.config import AttributionConfig
from src.attribution.engine import run_attribution
from src.attribution.metrics import fail_gates
from src.attribution.reporting import write_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-date", default="20260515")
    args = parser.parse_args()

    config = AttributionConfig(output_date=args.output_date)
    result = run_attribution(config)
    paths, schema_errors = write_outputs(
        result.tables,
        result.summary,
        result.log_text,
        config.output_date,
        config.output_dir,
        config.log_dir,
    )
    final_fail_gates = fail_gates(
        result.summary["reconciliation"]["gross_active_daily_max_diff"],
        result.summary["reconciliation"]["net_active_daily_max_diff"],
        config.tolerance,
        missing_outputs=[str(path) for path in paths.values() if not path.exists()],
        schema_errors=schema_errors,
    )
    if any(gate.get("triggered") for gate in final_fail_gates.values()):
        print(json.dumps({
            "status": "FAIL",
            "fail_gates": final_fail_gates,
            "outputs": {key: str(path) for key, path in paths.items()},
        }, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)

    print(json.dumps({
        "status": "REVIEW_READY",
        "outputs": {key: str(path) for key, path in paths.items()},
        "reconciliation": result.summary["reconciliation"],
        "warning_gates": result.summary["warning_gates"],
        "reproducibility_hash": result.summary["reproducibility_hash"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
