from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.costs.engine import Task002Inputs, run_task002_cost_stress


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TASK-002 v2 cost/funding/slippage stress.")
    parser.add_argument("--output-date", default=_default_output_date())
    parser.add_argument("--cost-config", default="configs/cost_stress.yaml")
    parser.add_argument("--fees", default="data/crypto/fees.yaml")
    parser.add_argument("--funding", default="data/crypto/funding_rates.parquet")
    parser.add_argument(
        "--baseline",
        default="outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv",
    )
    parser.add_argument(
        "--positions",
        default="outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet",
    )
    parser.add_argument(
        "--stats",
        default="outputs/backtests/prev3y_crypto/20260513_run008_stats.json",
    )
    args = parser.parse_args()

    inputs = Task002Inputs(
        cost_config_path=Path(args.cost_config),
        fees_path=Path(args.fees),
        funding_path=Path(args.funding),
        baseline_path=Path(args.baseline),
        positions_path=Path(args.positions),
        stats_path=Path(args.stats),
    )
    result = run_task002_cost_stress(inputs, args.output_date)

    print("TASK-002 v2 cost stress complete")
    for label, path in result.output_paths.items():
        print(f"{label}: {path}")
    print(f"no_cost_baseline_max_diff_vs_run008: {result.summary['no_cost_baseline_max_diff_vs_run008']}")
    print(f"verdict: {result.summary['verdict']}")
    print(f"reproducibility_hash: {result.summary['reproducibility_hash']}")


def _default_output_date() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y%m%d")


if __name__ == "__main__":
    main()
