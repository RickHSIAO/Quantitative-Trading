"""Validate TASK-001 Prev3Y crypto input files before any backtest."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.prev3y_input_validator import DataRequirementError, validate_prev3y_inputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/prev3y_crypto.yaml")
    parser.add_argument("--prices", default="data/crypto/prices_daily.parquet")
    parser.add_argument("--universe", default="data/crypto/universe_membership.parquet")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable validation summary.")
    args = parser.parse_args()

    try:
        validated = validate_prev3y_inputs(Path(args.config), Path(args.prices), Path(args.universe))
    except DataRequirementError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc

    payload = {
        "status": "ok",
        "config": args.config,
        "prices": {
            "path": args.prices,
            "rows": validated.price_info.row_count,
            "symbols": validated.price_info.symbol_count,
            "min_date": validated.price_info.min_date,
            "max_date": validated.price_info.max_date,
        },
        "universe": {
            "path": args.universe,
            "rows": validated.universe_info.row_count,
            "symbols": validated.universe_info.symbol_count,
            "min_date": validated.universe_info.min_date,
            "max_date": validated.universe_info.max_date,
            "avg_size": validated.universe_info.avg_size_start_end,
        },
        "warnings": validated.warnings,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    print("OK: TASK-001 input files exist and schema validation passed.")
    print(
        f"prices: rows={validated.price_info.row_count} symbols={validated.price_info.symbol_count} "
        f"date_range={validated.price_info.min_date}..{validated.price_info.max_date}"
    )
    print(
        f"universe: rows={validated.universe_info.row_count} symbols={validated.universe_info.symbol_count} "
        f"date_range={validated.universe_info.min_date}..{validated.universe_info.max_date}"
    )
    for warning in validated.warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
