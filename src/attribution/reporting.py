from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


OUTPUT_KEYS = {
    "by_symbol": "attribution_by_symbol",
    "by_year": "attribution_by_year",
    "by_month": "attribution_by_month",
    "by_side": "attribution_by_side",
    "by_funding_gap": "attribution_by_funding_gap",
    "by_interval": "attribution_by_interval",
    "by_cost_type": "attribution_by_cost_type",
    "top_contributors": "attribution_top_contributors",
    "drawdown": "attribution_drawdown",
}


REQUIRED_BY_SYMBOL_COLUMNS = {
    "symbol",
    "side_primary",
    "holding_days",
    "gross_alpha_contribution",
    "net_alpha_contribution",
    "fee_cost_total",
    "slippage_cost_total",
    "funding_cost_total",
    "total_cost",
    "gross_alpha_rank",
    "net_alpha_rank",
    "rank_change",
    "is_funding_gap",
    "funding_interval_group",
}


def write_outputs(
    tables: dict[str, pd.DataFrame],
    summary: dict[str, Any],
    log_text: str,
    output_date: str,
    output_dir: str | Path,
    log_dir: str | Path,
) -> tuple[dict[str, Path], list[str]]:
    out_dir = Path(output_dir)
    logs = Path(log_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    for key, stem in OUTPUT_KEYS.items():
        path = out_dir / f"{output_date}_{stem}.csv"
        tables[key].to_csv(path, index=False)
        paths[key] = path
    paths["summary"] = out_dir / f"{output_date}_attribution_summary.json"
    paths["log"] = logs / f"{output_date}_attribution.log"
    summary_with_paths = dict(summary)
    summary_with_paths["output_paths"] = {key: str(path) for key, path in paths.items()}
    paths["summary"].write_text(
        json.dumps(summary_with_paths, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["log"].write_text(log_text, encoding="utf-8")

    schema_errors = validate_output_schemas(tables)
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        schema_errors.extend(f"missing output file: {path}" for path in missing)
    return paths, schema_errors


def validate_output_schemas(tables: dict[str, pd.DataFrame]) -> list[str]:
    errors: list[str] = []
    by_symbol_cols = set(tables["by_symbol"].columns)
    missing = sorted(REQUIRED_BY_SYMBOL_COLUMNS - by_symbol_cols)
    if missing:
        errors.append(f"by_symbol missing columns: {missing}")
    for key in OUTPUT_KEYS:
        if key not in tables:
            errors.append(f"missing table: {key}")
        elif tables[key].empty:
            errors.append(f"empty table: {key}")
    return errors

