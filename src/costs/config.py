from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


EXPECTED_SCENARIOS = [
    "no_cost_baseline",
    "fee_taker_entry_maker_exit",
    "fee_taker_entry_taker_exit",
    "funding_low",
    "funding_mid",
    "funding_high",
    "slippage_5bps",
    "slippage_10bps",
    "slippage_20bps",
    "realistic_combo",
    "conservative_combo",
    "worst_case_combo",
]

EXPECTED_DEFAULTS = {
    "annualization_factor": 365.25,
    "std_ddof": 1,
    "active_window_policy": "gross_exposure_gt_0",
    "benchmark_policy": "reuse_run008_benchmark_columns",
    "slippage_application": "per_turnover_one_side_bps",
    "fee_application": "per_turnover_both_sides",
    "funding_application": "pit_per_interval_settlement_accumulated",
    "funding_proxy_policy": "exclude_from_fail_gate",
    "funding_interval_policy": "use_interval_hours_per_row",
    "funding_gap_policy": "mark_funding_gap_true_no_fill",
    "outlier_policy": "report_no_clamp",
}


@dataclass(frozen=True)
class Scenario:
    name: str
    fee_multiplier_taker: float
    fee_multiplier_maker: float
    funding_multiplier: float
    slippage_bps_one_side: float
    entry_side: str
    exit_side: str


@dataclass(frozen=True)
class CostStressConfig:
    version: int
    baseline_run_id: str
    defaults: dict[str, Any]
    scenarios: list[Scenario]


@dataclass(frozen=True)
class FeeConfig:
    exchange: str
    maker_bps: float
    taker_bps: float
    notes: str


def load_cost_stress_config(path: str | Path) -> CostStressConfig:
    data = _parse_simple_yaml(Path(path))
    defaults = data.get("defaults", {})
    scenarios_raw = data.get("scenarios", [])
    scenarios = [Scenario(**scenario) for scenario in scenarios_raw]
    cfg = CostStressConfig(
        version=int(data["version"]),
        baseline_run_id=str(data["baseline_run_id"]),
        defaults=defaults,
        scenarios=scenarios,
    )
    validate_cost_stress_config(cfg)
    return cfg


def load_fee_config(path: str | Path) -> FeeConfig:
    data = _parse_simple_yaml(Path(path))
    cfg = FeeConfig(
        exchange=str(data["exchange"]),
        maker_bps=float(data["maker_bps"]),
        taker_bps=float(data["taker_bps"]),
        notes=str(data.get("notes", "")),
    )
    validate_fee_config(cfg)
    return cfg


def validate_cost_stress_config(config: CostStressConfig) -> None:
    missing = [key for key in EXPECTED_DEFAULTS if key not in config.defaults]
    if missing:
        raise ValueError(f"cost_stress defaults missing keys: {missing}")

    mismatched = {
        key: (config.defaults.get(key), expected)
        for key, expected in EXPECTED_DEFAULTS.items()
        if config.defaults.get(key) != expected
    }
    if mismatched:
        raise ValueError(f"cost_stress defaults mismatch: {mismatched}")

    names = [scenario.name for scenario in config.scenarios]
    if names != EXPECTED_SCENARIOS:
        raise ValueError(f"scenario names/order mismatch: {names}")

    no_cost = config.scenarios[0]
    zero_values = [
        no_cost.fee_multiplier_taker,
        no_cost.fee_multiplier_maker,
        no_cost.funding_multiplier,
        no_cost.slippage_bps_one_side,
    ]
    if no_cost.name != "no_cost_baseline" or any(float(value) != 0.0 for value in zero_values):
        raise ValueError("no_cost_baseline must have zero fee/funding/slippage multipliers")

    for scenario in config.scenarios:
        if scenario.entry_side not in {"maker", "taker"}:
            raise ValueError(f"unsupported entry_side for {scenario.name}: {scenario.entry_side}")
        if scenario.exit_side not in {"maker", "taker"}:
            raise ValueError(f"unsupported exit_side for {scenario.name}: {scenario.exit_side}")


def validate_fee_config(config: FeeConfig) -> None:
    if config.exchange != "bybit_perp":
        raise ValueError(f"unsupported fee exchange: {config.exchange}")
    if config.maker_bps < 0 or config.taker_bps < 0:
        raise ValueError("maker_bps and taker_bps must be non-negative")
    notes = config.notes.lower()
    required = ["source", "2026-05-14", "vip 0", "non-vip", "rebate"]
    missing = [item for item in required if item not in notes]
    if missing:
        raise ValueError(f"fees.yaml notes missing required caveats: {missing}")


def _parse_simple_yaml(path: Path) -> dict[str, Any]:
    """Parse the small YAML subset used by TASK-002 config files."""
    lines = path.read_text(encoding="utf-8").splitlines()
    root: dict[str, Any] = {}
    current_map: dict[str, Any] | None = None
    current_list: list[dict[str, Any]] | None = None
    current_item: dict[str, Any] | None = None
    block_key: str | None = None
    block_indent: int | None = None
    block_lines: list[str] = []

    def flush_block() -> None:
        nonlocal block_key, block_indent, block_lines
        if block_key is not None:
            root[block_key] = "\n".join(block_lines).rstrip() + "\n"
        block_key = None
        block_indent = None
        block_lines = []

    for raw in lines:
        stripped = raw.strip()
        if block_key is not None:
            indent = len(raw) - len(raw.lstrip(" "))
            if stripped and indent >= (block_indent or 0):
                block_lines.append(raw[(block_indent or 0) :])
                continue
            flush_block()

        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0 and stripped.endswith(":"):
            key = stripped[:-1]
            if key == "defaults":
                current_map = {}
                current_list = None
                current_item = None
                root[key] = current_map
            elif key == "scenarios":
                current_list = []
                current_map = None
                current_item = None
                root[key] = current_list
            continue

        if indent == 0 and ": |" in raw:
            key = stripped.split(":", 1)[0]
            block_key = key
            block_indent = indent + 2
            block_lines = []
            continue

        if indent == 0 and ":" in stripped:
            key, value = stripped.split(":", 1)
            root[key] = _coerce_scalar(value.strip())
            continue

        if current_map is not None and indent == 2 and ":" in stripped:
            key, value = stripped.split(":", 1)
            current_map[key] = _coerce_scalar(value.strip())
            continue

        if current_list is not None and indent == 2 and stripped.startswith("- "):
            current_item = {}
            current_list.append(current_item)
            item_text = stripped[2:]
            if ":" in item_text:
                key, value = item_text.split(":", 1)
                current_item[key] = _coerce_scalar(value.strip())
            continue

        if current_item is not None and indent == 4 and ":" in stripped:
            key, value = stripped.split(":", 1)
            current_item[key] = _coerce_scalar(value.strip())
            continue

    flush_block()
    return root


def _coerce_scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if any(ch in value for ch in [".", "e", "E"]):
            return float(value)
        return int(value)
    except ValueError:
        return value
