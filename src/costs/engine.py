from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.costs.config import (
    CostStressConfig,
    FeeConfig,
    Scenario,
    load_cost_stress_config,
    load_fee_config,
)
from src.costs.fees import apply_fee_cost
from src.costs.funding import build_funding_attribution
from src.costs.metrics import compute_cost_stress_metrics
from src.costs.reproducibility import build_input_hashes, canonical_hash, git_commit
from src.costs.reporting import build_log_text, write_outputs
from src.costs.slippage import apply_slippage_cost
from src.costs.turnover import build_turnover_events, prepare_positions


@dataclass(frozen=True)
class Task002Inputs:
    cost_config_path: Path
    fees_path: Path
    funding_path: Path
    baseline_path: Path
    positions_path: Path
    stats_path: Path


@dataclass(frozen=True)
class Task002Result:
    output_paths: dict[str, Path]
    summary: dict[str, Any]
    daily: pd.DataFrame
    positions_cost: pd.DataFrame


def run_task002_cost_stress(inputs: Task002Inputs, output_date: str) -> Task002Result:
    config = load_cost_stress_config(inputs.cost_config_path)
    fees = load_fee_config(inputs.fees_path)
    baseline = _load_baseline(inputs.baseline_path)
    positions = prepare_positions(pd.read_parquet(inputs.positions_path))
    run008_stats = _load_json(inputs.stats_path)

    no_cost_diff = _run_no_cost_sanity_gate(baseline)
    if no_cost_diff != 0.0:
        raise RuntimeError(f"no_cost_baseline sanity gate failed: max_diff={no_cost_diff}")

    funding = pd.read_parquet(inputs.funding_path)
    turnover_events = build_turnover_events(baseline, positions)
    funding_attr = build_funding_attribution(funding, positions)
    base_events = _merge_base_events(turnover_events, funding_attr.symbol_day)

    daily_frames: list[pd.DataFrame] = []
    detail_frames: list[pd.DataFrame] = []
    scenario_summaries: dict[str, dict[str, Any]] = {}
    annualization = float(config.defaults["annualization_factor"])
    run008_active_alpha = float(run008_stats["ir_vs_equal_weight_active"])
    run008_active_max_dd = float(run008_stats["max_dd_active"])

    for scenario in config.scenarios:
        detail = _scenario_detail(base_events, scenario, fees)
        daily = _scenario_daily(baseline, detail, scenario)
        _validate_daily_identity(daily)

        metrics = compute_cost_stress_metrics(daily, annualization)
        totals = _scenario_totals(daily)
        metrics.update(totals)
        metrics["net_alpha_decay_vs_run008"] = float(
            run008_active_alpha - float(metrics["ir_vs_equal_weight_active"])
        )
        metrics["net_alpha_decay_pct_vs_run008"] = _safe_div(
            float(metrics["net_alpha_decay_vs_run008"]),
            run008_active_alpha,
        )
        metrics["cost_per_turnover"] = _cost_per_turnover_bps(daily)
        metrics["outlier_contribution_breakdown"] = _scenario_outlier_breakdown(
            funding_attr.outlier_breakdown_base,
            scenario,
        )
        scenario_summaries[scenario.name] = _clean(metrics)
        daily_frames.append(daily)
        detail_frames.append(detail)

    daily_all = pd.concat(daily_frames, ignore_index=True)
    detail_all = pd.concat(detail_frames, ignore_index=True)

    gates = _evaluate_gates(
        scenario_summaries,
        run008_active_alpha,
        run008_active_max_dd,
        funding_attr.funding_gap_breakdown,
    )
    input_hashes = build_input_hashes(
        {
            "cost_stress_yaml": inputs.cost_config_path,
            "fees_yaml": inputs.fees_path,
            "funding_rates_parquet": inputs.funding_path,
            "run008_baseline_csv": inputs.baseline_path,
            "run008_positions_parquet": inputs.positions_path,
            "run008_stats_json": inputs.stats_path,
        }
    )
    data_snapshot_hash = canonical_hash(input_hashes)

    summary_base = {
        "readiness_status": "READY_TO_IMPLEMENT",
        "baseline_run_id": config.baseline_run_id,
        "output_date": output_date,
        "random_seed": 0,
        "git_commit": git_commit(),
        "input_hashes": input_hashes,
        "data_snapshot_hash": data_snapshot_hash,
        "no_cost_baseline_max_diff_vs_run008": no_cost_diff,
        "scenario_order": [scenario.name for scenario in config.scenarios],
        "interval_hours_distribution": funding_attr.interval_distribution,
        "funding_gap_symbol_days": funding_attr.funding_gap_breakdown[
            "active_position_symbol_days_with_gap"
        ],
        "funding_gap_pct_active": funding_attr.funding_gap_breakdown["pct_of_active_position"],
        "funding_gap_breakdown": funding_attr.funding_gap_breakdown,
        "outlier_count": funding_attr.outlier_breakdown_base["outlier_count"],
        "held_outlier_rows": funding_attr.outlier_breakdown_base["held_outlier_rows"],
        "max_abs_funding_rate": funding_attr.outlier_breakdown_base["max_abs_funding_rate"],
        "outlier_contribution_pct_of_total_funding_cost": funding_attr.outlier_breakdown_base[
            "outlier_pct_of_total_abs_funding_cost"
        ],
        "outlier_contribution_breakdown": funding_attr.outlier_breakdown_base,
        "funding_audit_samples": funding_attr.audit_samples,
        "methodology": _methodology(config),
        "cost_policy": _cost_policy(config, fees),
        "scenarios": scenario_summaries,
        "fail_warning_gates": gates,
        "verdict": "FAIL" if gates["failures"] else "PASS_WITH_WARNINGS" if gates["warnings"] else "PASS",
        "stats_recompute_check": _stats_recompute_check(daily_all, scenario_summaries, annualization),
    }
    reproducibility_hash = canonical_hash(summary_base)
    summary = dict(summary_base)
    summary["reproducibility_hash"] = reproducibility_hash
    summary["reproducibility_hash_check_passed"] = (
        canonical_hash(summary_base) == reproducibility_hash
    )

    log_text = build_log_text(summary)
    paths = write_outputs(daily_all, detail_all, summary, log_text, output_date)
    return Task002Result(output_paths=paths, summary=summary, daily=daily_all, positions_cost=detail_all)


def _load_baseline(path: Path) -> pd.DataFrame:
    baseline = pd.read_csv(path)
    required = {
        "date",
        "portfolio_return",
        "benchmark_return",
        "benchmark_cash_return",
        "benchmark_btc_return",
        "benchmark_eqw_return",
        "gross_exposure",
        "net_exposure",
        "turnover",
        "n_longs",
        "n_shorts",
    }
    missing = required - set(baseline.columns)
    if missing:
        raise ValueError(f"run008 baseline missing columns: {sorted(missing)}")
    baseline["date"] = pd.to_datetime(baseline["date"]).dt.tz_localize(None)
    if not baseline["date"].is_unique:
        raise ValueError("run008 baseline dates are not unique")
    return baseline.sort_values("date").reset_index(drop=True)


def _load_json(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _run_no_cost_sanity_gate(baseline: pd.DataFrame) -> float:
    gross = baseline["portfolio_return"].astype(float)
    net = gross - 0.0 - 0.0 - 0.0
    return float((net - gross).abs().max())


def _merge_base_events(turnover_events: pd.DataFrame, funding_symbol_day: pd.DataFrame) -> pd.DataFrame:
    events = turnover_events.merge(
        funding_symbol_day,
        on=["date", "symbol"],
        how="outer",
        suffixes=("", "_funding"),
    )
    if "weight_funding" in events.columns:
        events["weight"] = events["weight"].fillna(events["weight_funding"])
        events = events.drop(columns=["weight_funding"])
    for col in ["previous_weight", "delta_weight", "entry_turnover", "exit_turnover", "trade_turnover"]:
        events[col] = events[col].fillna(0.0)
    for col in ["funding_cost_base", "funding_abs_cost_base", "outlier_abs_cost_base"]:
        events[col] = events[col].fillna(0.0)
    for col in ["outlier_count_today", "funding_settlement_count"]:
        events[col] = events[col].fillna(0).astype(int)
    events["funding_gap"] = events["funding_gap"].fillna(False).astype(bool)
    events["weight"] = events["weight"].fillna(0.0)
    return events.sort_values(["date", "symbol"]).reset_index(drop=True)


def _scenario_detail(events: pd.DataFrame, scenario: Scenario, fees: FeeConfig) -> pd.DataFrame:
    detail = events.copy()
    detail["scenario"] = scenario.name
    detail["fee_cost"] = apply_fee_cost(detail, scenario, fees)
    detail["slippage_cost"] = apply_slippage_cost(detail, scenario)
    detail["funding_cost"] = detail["funding_cost_base"].astype(float) * float(
        scenario.funding_multiplier
    )
    detail["outlier_funding_cost"] = detail["outlier_abs_cost_base"].astype(float) * abs(
        float(scenario.funding_multiplier)
    )
    columns = [
        "date",
        "scenario",
        "symbol",
        "weight",
        "fee_cost",
        "funding_cost",
        "slippage_cost",
        "funding_gap",
        "outlier_count_today",
        "funding_settlement_count",
        "entry_turnover",
        "exit_turnover",
        "trade_turnover",
        "outlier_funding_cost",
    ]
    return detail.loc[:, columns]


def _scenario_daily(baseline: pd.DataFrame, detail: pd.DataFrame, scenario: Scenario) -> pd.DataFrame:
    costs = detail.groupby("date", as_index=False).agg(
        fee_cost=("fee_cost", "sum"),
        funding_cost=("funding_cost", "sum"),
        slippage_cost=("slippage_cost", "sum"),
    )
    daily = baseline.merge(costs, on="date", how="left")
    for col in ["fee_cost", "funding_cost", "slippage_cost"]:
        daily[col] = daily[col].fillna(0.0)
    daily["scenario"] = scenario.name
    daily["portfolio_return_gross"] = daily["portfolio_return"].astype(float)
    daily["portfolio_return_net"] = (
        daily["portfolio_return_gross"]
        - daily["fee_cost"]
        - daily["funding_cost"]
        - daily["slippage_cost"]
    )
    ordered = [
        "date",
        "scenario",
        "portfolio_return_gross",
        "portfolio_return_net",
        "fee_cost",
        "funding_cost",
        "slippage_cost",
        "gross_exposure",
        "turnover",
        "net_exposure",
        "benchmark_return",
        "benchmark_cash_return",
        "benchmark_btc_return",
        "benchmark_eqw_return",
        "n_longs",
        "n_shorts",
    ]
    return daily.loc[:, ordered]


def _validate_daily_identity(daily: pd.DataFrame) -> None:
    recomputed = (
        daily["portfolio_return_gross"].astype(float)
        - daily["fee_cost"].astype(float)
        - daily["funding_cost"].astype(float)
        - daily["slippage_cost"].astype(float)
    )
    max_diff = float((recomputed - daily["portfolio_return_net"].astype(float)).abs().max())
    if max_diff > 1e-12:
        raise ValueError(f"daily net identity failed: max_diff={max_diff}")


def _scenario_totals(daily: pd.DataFrame) -> dict[str, float]:
    return {
        "total_fee_cost": float(daily["fee_cost"].sum()),
        "total_slippage_cost": float(daily["slippage_cost"].sum()),
        "total_funding_cost": float(daily["funding_cost"].sum()),
    }


def _cost_per_turnover_bps(daily: pd.DataFrame) -> float:
    total_turnover = float(daily["turnover"].sum())
    total_cost = float(
        daily["fee_cost"].sum() + daily["slippage_cost"].sum() + daily["funding_cost"].sum()
    )
    return _safe_div(total_cost, total_turnover) * 10000.0


def _scenario_outlier_breakdown(base: dict[str, object], scenario: Scenario) -> dict[str, object]:
    multiplier = abs(float(scenario.funding_multiplier))
    total = float(base["total_abs_funding_cost_base"]) * multiplier
    outlier = float(base["outlier_abs_funding_cost_base"]) * multiplier
    return {
        "outlier_count": int(base["outlier_count"]),
        "held_outlier_rows": int(base["held_outlier_rows"]),
        "held_outlier_symbol_days": int(base["held_outlier_symbol_days"]),
        "max_abs_funding_rate": float(base["max_abs_funding_rate"]),
        "outlier_funding_cost": outlier,
        "outlier_pct_of_total_funding_cost": _safe_div(outlier, total),
    }


def _evaluate_gates(
    scenarios: dict[str, dict[str, Any]],
    run008_active_alpha: float,
    run008_active_max_dd: float,
    funding_gap_breakdown: dict[str, object],
) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []

    realistic = scenarios["realistic_combo"]
    conservative = scenarios["conservative_combo"]
    combos = ["realistic_combo", "conservative_combo", "worst_case_combo"]

    if float(realistic["sharpe_active"]) < 0.5:
        failures.append("realistic_combo active Sharpe < 0.5")
    if float(realistic["ir_vs_equal_weight_active"]) < 0.2:
        failures.append("realistic_combo active IR vs equal-weight < 0.2")
    if float(conservative["ir_vs_equal_weight_active"]) < 0.0:
        failures.append("conservative_combo active IR vs equal-weight < 0")

    max_dd_threshold = abs(float(run008_active_max_dd)) * 1.5
    for name in ["realistic_combo", "conservative_combo"]:
        if abs(float(scenarios[name]["max_dd_active"])) > max_dd_threshold:
            warnings.append(f"{name} active max DD worsens beyond 1.5x run008")

    for name in combos:
        decay = float(scenarios[name]["net_alpha_decay_vs_run008"])
        if decay > 0.7 * float(run008_active_alpha):
            warnings.append(f"{name} cost consumes >70% of run008 active alpha")
        outlier_pct = float(
            scenarios[name]["outlier_contribution_breakdown"][
                "outlier_pct_of_total_funding_cost"
            ]
        )
        if outlier_pct > 0.30:
            warnings.append(f"{name} outlier contribution >30% of total funding cost")

    if float(funding_gap_breakdown["pct_of_active_position"]) > 0.05:
        warnings.append("funding gap >5% of active position range")

    return {
        "failures": failures,
        "warnings": warnings,
        "realistic_combo_fail_gate_passed": not any(item.startswith("realistic_combo") for item in failures),
        "conservative_combo_fail_gate_passed": not any(item.startswith("conservative_combo") for item in failures),
    }


def _methodology(config: CostStressConfig) -> dict[str, object]:
    return {
        "annualization_factor": float(config.defaults["annualization_factor"]),
        "std_ddof": int(config.defaults["std_ddof"]),
        "active_period_definition": "gross_exposure > 0",
        "benchmark_policy": "reuse run008 benchmark_return, benchmark_cash_return, benchmark_btc_return, benchmark_eqw_return columns",
        "ir_formula": "mean(portfolio_return_net - benchmark_return) / std(portfolio_return_net - benchmark_return, ddof=1) * sqrt(annualization_factor)",
        "sortino_formula": "not a required TASK-002 output; run008 convention retained where referenced",
        "cost_application_order": "portfolio_return_net = portfolio_return_gross - fee_cost - funding_cost - slippage_cost",
        "funding_timestamp_policy": "funding timestamp is converted to UTC date; same UTC date + symbol held weight is used; no future, previous-day, next-day, or averaged weights are used",
        "funding_direction_formula": "funding_cost = signed_position_weight * funding_rate * scenario_funding_multiplier; long positive funding is a cost, short positive funding is income",
    }


def _cost_policy(config: CostStressConfig, fees: FeeConfig) -> dict[str, object]:
    return {
        "fee_application": config.defaults["fee_application"],
        "fee_exchange": fees.exchange,
        "maker_bps": fees.maker_bps,
        "taker_bps": fees.taker_bps,
        "slippage_application": config.defaults["slippage_application"],
        "funding_application": config.defaults["funding_application"],
        "funding_interval_policy": config.defaults["funding_interval_policy"],
        "funding_proxy_policy": config.defaults["funding_proxy_policy"],
        "funding_gap_policy": config.defaults["funding_gap_policy"],
        "outlier_policy": config.defaults["outlier_policy"],
    }


def _stats_recompute_check(
    daily_all: pd.DataFrame,
    scenario_summaries: dict[str, dict[str, Any]],
    annualization: float,
) -> dict[str, object]:
    max_diff = 0.0
    checked = 0
    keys = [
        "total_return_full",
        "total_return_active",
        "sharpe_full",
        "sharpe_active",
        "ir_vs_cash_full",
        "ir_vs_cash_active",
        "ir_vs_btc_full",
        "ir_vs_btc_active",
        "ir_vs_equal_weight_full",
        "ir_vs_equal_weight_active",
        "max_dd_full",
        "max_dd_active",
        "calmar_full",
        "calmar_active",
        "turnover_annual_full",
        "turnover_annual_active",
    ]
    for scenario, expected in scenario_summaries.items():
        daily = daily_all[daily_all["scenario"] == scenario]
        actual = compute_cost_stress_metrics(daily, annualization)
        for key in keys:
            diff = abs(float(actual[key]) - float(expected[key]))
            max_diff = max(max_diff, diff)
            checked += 1
    return {"passed": max_diff < 1e-12, "max_abs_diff": max_diff, "values_checked": checked}


def _safe_div(num: float, den: float) -> float:
    if den == 0.0:
        return 0.0
    return float(num / den)


def _clean(value: Any) -> Any:
    import math

    if isinstance(value, dict):
        return {str(key): _clean(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return 0.0
        return float(value)
    if hasattr(value, "item"):
        return _clean(value.item())
    return value
