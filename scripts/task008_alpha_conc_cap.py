from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.variants.task008 import Task008Config, run_task008


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TASK-008 alpha-space concentration cap study.")
    parser.add_argument("--output-date", default="20260517", help="Output date stamp in YYYYMMDD format.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_task008(Task008Config(output_date=args.output_date))
    print(f"status={result.status}")
    print(f"comparison_csv={result.comparison_csv}")
    print(f"comparison_json={result.comparison_json}")
    print(f"detail_csv={result.detail_csv}")
    print(f"attribution_json={result.attribution_json}")
    print(f"log={result.log_path}")
    print(f"review_packet={result.review_packet_path}")
    print(f"review_numbers={result.review_numbers_path}")
    print("paper_execution=FORBIDDEN")
    print("live_trading=FORBIDDEN")
    if result.fail_gates:
        print(f"fail_gates={result.fail_gates}")
        return 1
    if result.warning_gates:
        print(f"warning_gates={len(result.warning_gates)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
