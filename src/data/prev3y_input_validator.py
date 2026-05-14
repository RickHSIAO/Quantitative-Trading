"""Schema and availability checks for TASK-001 Prev3Y inputs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
    is_string_dtype,
)

from src.data.crypto_daily import PriceSnapshotInfo, load_price_snapshot
from src.universe.prev3y_crypto import UniverseSnapshotInfo, load_universe_membership


REQUIRED_PRICE_COLUMNS = {
    "date": "datetime64",
    "symbol": "string",
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "volume": "float64",
    "quote_volume": "float64",
}

REQUIRED_UNIVERSE_COLUMNS = {
    "date": "datetime64",
    "symbol": "string",
    "is_member": "bool",
}

REQUIRED_CONFIG_KEYS = {
    "lookback_days",
    "rebalance_freq",
    "top_n",
    "bottom_n",
    "ranking_method",
    "entry_price",
    "start_date",
    "end_date",
    "warmup_start_date",
}


@dataclass(frozen=True)
class ValidatedPrev3YInputs:
    config: dict[str, Any]
    prices: pd.DataFrame
    membership: pd.DataFrame
    price_info: PriceSnapshotInfo
    universe_info: UniverseSnapshotInfo
    warnings: list[str]


class DataRequirementError(RuntimeError):
    """Raised when required TASK-001 input files are missing or invalid."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(format_blocked_by_data(errors))


def validate_prev3y_inputs(
    config_path: Path,
    prices_path: Path,
    universe_path: Path,
) -> ValidatedPrev3YInputs:
    errors: list[str] = []
    warnings: list[str] = []
    missing = [path for path in [config_path, prices_path, universe_path] if not path.exists()]
    if missing:
        errors.extend(f"missing required file: {path}" for path in missing)
        raise DataRequirementError(errors)

    try:
        config = load_simple_yaml(config_path)
    except Exception as exc:
        raise DataRequirementError([f"invalid config {config_path}: {exc}"]) from exc

    errors.extend(validate_config(config))
    if errors:
        raise DataRequirementError(errors)

    try:
        prices = load_price_snapshot(prices_path)
    except Exception as exc:
        raise DataRequirementError([f"cannot read prices parquet {prices_path}: {exc}"]) from exc
    try:
        membership = load_universe_membership(universe_path)
    except Exception as exc:
        raise DataRequirementError([f"cannot read universe parquet {universe_path}: {exc}"]) from exc

    errors.extend(validate_price_schema(prices, prices_path))
    errors.extend(validate_universe_schema(membership, universe_path))
    warnings.extend(validate_coverage(config, prices, membership))
    if errors:
        raise DataRequirementError(errors)

    price_info = PriceSnapshotInfo(
        path=prices_path,
        row_count=int(len(prices)),
        symbol_count=int(prices["symbol"].nunique()),
        min_date=str(pd.Timestamp(prices["date"].min()).date()) if not prices.empty else "",
        max_date=str(pd.Timestamp(prices["date"].max()).date()) if not prices.empty else "",
        created=False,
    )
    universe_info = UniverseSnapshotInfo(
        path=universe_path,
        row_count=int(len(membership)),
        symbol_count=int(membership["symbol"].nunique()),
        min_date=str(pd.Timestamp(membership["date"].min()).date()) if not membership.empty else "",
        max_date=str(pd.Timestamp(membership["date"].max()).date()) if not membership.empty else "",
        avg_size_start_end=float(
            membership[membership["is_member"]]
            .groupby("date")["symbol"]
            .nunique()
            .reindex(pd.date_range(str(config["start_date"]), str(config["end_date"])), fill_value=0)
            .mean()
        ),
        created=False,
    )
    return ValidatedPrev3YInputs(config, prices, membership, price_info, universe_info, warnings)


def validate_price_schema(df: pd.DataFrame, path: Path) -> list[str]:
    errors = _validate_required_columns(df, REQUIRED_PRICE_COLUMNS, path)
    if errors:
        return errors
    errors.extend(_validate_common_frame(df, path))
    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        if not is_numeric_dtype(df[col]):
            errors.append(f"{path}: column {col} must be numeric, got {df[col].dtype}")
    dupes = int(df.duplicated(["date", "symbol"]).sum())
    if dupes:
        errors.append(f"{path}: duplicate date/symbol rows={dupes}")
    return errors


def validate_universe_schema(df: pd.DataFrame, path: Path) -> list[str]:
    errors = _validate_required_columns(df, REQUIRED_UNIVERSE_COLUMNS, path)
    if errors:
        return errors
    errors.extend(_validate_common_frame(df, path))
    if not is_bool_dtype(df["is_member"]):
        errors.append(f"{path}: column is_member must be bool, got {df['is_member'].dtype}")
    dupes = int(df.duplicated(["date", "symbol"]).sum())
    if dupes:
        errors.append(f"{path}: duplicate date/symbol rows={dupes}")
    if not bool(df["is_member"].all()):
        errors.append(f"{path}: membership parquet should store true rows only; found false rows")
    return errors


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_CONFIG_KEYS - set(config))
    if missing:
        errors.append(f"config missing keys: {', '.join(missing)}")
        return errors
    for key in ["lookback_days", "top_n", "bottom_n"]:
        try:
            value = int(config[key])
        except (TypeError, ValueError):
            errors.append(f"config {key} must be integer")
            continue
        if value < 0 or (key == "lookback_days" and value <= 0):
            errors.append(f"config {key} must be positive")
    if config["rebalance_freq"] not in {"monthly", "weekly"}:
        errors.append("config rebalance_freq must be monthly or weekly")
    if config["ranking_method"] not in {"return", "risk_adjusted_return"}:
        errors.append("config ranking_method must be return or risk_adjusted_return")
    if config["entry_price"] not in {"t1_open", "t1_close"}:
        errors.append("config entry_price must be t1_open or t1_close")
    benchmark = config.get("benchmark", {})
    if benchmark and not isinstance(benchmark, dict):
        errors.append("config benchmark must be a mapping when provided")
    if isinstance(benchmark, dict) and benchmark:
        primary = benchmark.get("primary", "cash")
        if primary not in {"cash", "btc_perp", "equal_weight_long_only"}:
            errors.append("config benchmark.primary must be cash, btc_perp, or equal_weight_long_only")
        btc_symbol = benchmark.get("btc_symbol", "")
        if not isinstance(btc_symbol, str) or not btc_symbol:
            errors.append("config benchmark.btc_symbol must be a non-empty string")
        alternatives = benchmark.get("alternatives", [])
        if alternatives and not isinstance(alternatives, list):
            errors.append("config benchmark.alternatives must be a list when provided")
    try:
        warmup = pd.Timestamp(str(config["warmup_start_date"]))
        start = pd.Timestamp(str(config["start_date"]))
        end = pd.Timestamp(str(config["end_date"]))
    except Exception as exc:
        errors.append(f"config dates must be parseable YYYY-MM-DD values: {exc}")
        return errors
    if warmup > start:
        errors.append("config warmup_start_date must be <= start_date")
    if start > end:
        errors.append("config start_date must be <= end_date")
    return errors


def validate_coverage(config: dict[str, Any], prices: pd.DataFrame, membership: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    warmup = pd.Timestamp(str(config["warmup_start_date"]))
    start = pd.Timestamp(str(config["start_date"]))
    end = pd.Timestamp(str(config["end_date"]))
    if not prices.empty and prices["date"].min() > warmup:
        warnings.append(
            f"prices start at {prices['date'].min().date()}, after warmup_start_date {warmup.date()}; "
            "early baseline rows may be zero exposure until lookback history exists"
        )
    if not membership.empty and membership["date"].min() > start:
        warnings.append(
            f"universe starts at {membership['date'].min().date()}, after start_date {start.date()}; "
            "early baseline rows may be zero exposure"
        )
    if not prices.empty and prices["date"].max() < end:
        warnings.append(f"prices end at {prices['date'].max().date()}, before end_date {end.date()}")
    if not membership.empty and membership["date"].max() < end:
        warnings.append(f"universe ends at {membership['date'].max().date()}, before end_date {end.date()}")
    return warnings


def load_simple_yaml(path: Path) -> dict[str, Any]:
    config: dict[str, Any] = {}
    current_map: dict[str, Any] | None = None
    current_list_key: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line_without_comment = raw.split("#", 1)[0].rstrip()
        line = line_without_comment.strip()
        if not line:
            continue
        indent = len(line_without_comment) - len(line_without_comment.lstrip(" "))
        if indent >= 4 and current_map is not None and current_list_key is not None and line.startswith("- "):
            current_map.setdefault(current_list_key, []).append(parse_scalar(line[2:].strip()))
            continue
        if indent >= 2 and current_map is not None:
            if ":" not in line:
                raise ValueError(f"Invalid nested config line: {raw}")
            key, value = line.split(":", 1)
            nested_key = key.strip()
            nested_value = value.strip()
            if nested_value == "":
                current_map[nested_key] = []
                current_list_key = nested_key
            else:
                current_map[nested_key] = parse_scalar(nested_value)
                current_list_key = None
            continue
        if ":" not in line:
            raise ValueError(f"Invalid config line: {raw}")
        key, value = line.split(":", 1)
        top_key = key.strip()
        top_value = value.strip()
        if top_value == "":
            config[top_key] = {}
            current_map = config[top_key]
            current_list_key = None
        else:
            config[top_key] = parse_scalar(top_value)
            current_map = None
            current_list_key = None
    return config


def parse_scalar(value: str) -> Any:
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def format_blocked_by_data(errors: list[str]) -> str:
    lines = [
        "BLOCKED_BY_DATA: TASK-001 required input data is missing or schema-invalid.",
        "",
        "Do not run a baseline. Do not create random, simulated, or synthetic data.",
        "",
        "Problems:",
    ]
    lines.extend(f"- {error}" for error in errors)
    lines.extend([
        "",
        "Required files:",
        "- data/crypto/prices_daily.parquet",
        "- data/crypto/universe_membership.parquet",
        "- configs/prev3y_crypto.yaml",
        "",
        "Next steps:",
        "- Populate prices_daily.parquet from a real daily OHLCV source.",
        "- Populate universe_membership.parquet from a real point-in-time universe source.",
        "- Run: python scripts\\validate_prev3y_crypto_inputs.py",
        "- Keep TASK-001 as BLOCKED_BY_DATA until validation passes.",
        "- See docs/research/DATA_REQUIREMENTS_PREV3Y.md.",
    ])
    return "\n".join(lines)


def _validate_required_columns(df: pd.DataFrame, expected: dict[str, str], path: Path) -> list[str]:
    errors: list[str] = []
    missing = [col for col in expected if col not in df.columns]
    if missing:
        errors.append(f"{path}: missing columns: {', '.join(missing)}")
    return errors


def _validate_common_frame(df: pd.DataFrame, path: Path) -> list[str]:
    errors: list[str] = []
    if df.empty:
        errors.append(f"{path}: file is empty")
        return errors
    if not is_datetime64_any_dtype(df["date"]):
        errors.append(f"{path}: column date must be datetime64, got {df['date'].dtype}")
    if not (is_string_dtype(df["symbol"]) or is_object_dtype(df["symbol"])):
        errors.append(f"{path}: column symbol must be string-like, got {df['symbol'].dtype}")
    nulls = df[["date", "symbol"]].isna().sum()
    for col, count in nulls.items():
        if int(count):
            errors.append(f"{path}: column {col} contains nulls={int(count)}")
    return errors
