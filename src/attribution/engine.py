from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype

from src.attribution.config import AttributionConfig
from src.attribution.costs import funding_interval_map, load_primary_costs
from src.attribution.metrics import (
    aggregate_by_funding_gap,
    aggregate_by_interval,
    aggregate_by_side,
    aggregate_by_symbol,
    aggregate_cost_type,
    aggregate_period,
    drawdown_contributors,
    fail_gates,
    signed_side,
    top_contributors,
    warning_gates,
)
from src.attribution.reproducibility import build_input_hashes, canonical_hash, git_commit
from src.attribution.returns import build_gross_contributions, load_tradable_membership


@dataclass(frozen=True)
class AttributionResult:
    tables: dict[str, pd.DataFrame]
    summary: dict[str, Any]
    log_text: str


def run_attribution(config: AttributionConfig) -> AttributionResult:
    baseline = pd.read_csv(config.baseline_path, parse_dates=["date"])
    cost_stress = pd.read_csv(config.cost_stress_path, parse_dates=["date"])
    positions = pd.read_parquet(config.positions_path)
    positions_cost = pd.read_parquet(config.positions_cost_path)
    prices = pd.read_parquet(config.prices_path)
    funding = pd.read_parquet(config.funding_path)
    cost_summary = json.loads(config.cost_summary_path.read_text(encoding="utf-8"))

    _normalize_dates(baseline, ["date"])
    _normalize_dates(cost_stress, ["date"])
    active_dates = set(baseline.loc[baseline["gross_exposure"].astype(float).gt(0), "date"])
    active_start = min(active_dates)
    active_end = max(active_dates)

    tradable = load_tradable_membership(
        config.prev3y_config_path,
        config.prices_path,
        config.universe_path,
    )
    gross = build_gross_contributions(positions, prices, tradable)
    primary_costs = load_primary_costs(positions_cost, config.primary_scenario)
    interval = funding_interval_map(funding)
    fact = _build_fact_table(gross, primary_costs, interval, active_dates, config)
    daily = _daily_reconciliation(fact, baseline, cost_stress, config)
    reconciliation = _reconciliation_stats(daily, config.tolerance)
    if reconciliation["gross_active_daily_max_diff"] > config.tolerance:
        raise RuntimeError(
            "NEED_CLARIFICATION: gross attribution does not reconcile to run008 "
            f"max_diff={reconciliation['gross_active_daily_max_diff']}"
        )
    if reconciliation["net_active_daily_max_diff"] > config.tolerance:
        raise RuntimeError(
            "NEED_CLARIFICATION: net attribution does not reconcile to TASK-002 realistic_combo "
            f"max_diff={reconciliation['net_active_daily_max_diff']}"
        )

    gap_symbols = set(config.known_funding_gap_symbols)
    by_symbol = aggregate_by_symbol(fact, gap_symbols)
    by_year = aggregate_period(fact, "year")
    by_month = aggregate_period(fact, "month")
    by_side = aggregate_by_side(fact)
    by_gap = aggregate_by_funding_gap(fact)
    by_interval = aggregate_by_interval(fact)
    by_cost_type = aggregate_cost_type(fact)
    top = top_contributors(by_symbol)
    drawdown, drawdown_metadata = drawdown_contributors(baseline, fact)

    warnings = warning_gates(by_symbol, by_year, by_side, by_gap, config.warning_thresholds)
    failures = fail_gates(
        reconciliation["gross_active_daily_max_diff"],
        reconciliation["net_active_daily_max_diff"],
        config.tolerance,
    )
    input_hashes = build_input_hashes(config.input_paths())
    commit = git_commit()
    totals = _totals(fact)
    summary = {
        "run_date": config.output_date,
        "baseline_run_id": config.baseline_run_id,
        "cost_stress_run_id": config.cost_stress_run_id,
        "primary_scenario": config.primary_scenario,
        "active_start": pd.Timestamp(active_start).strftime("%Y-%m-%d"),
        "active_end": pd.Timestamp(active_end).strftime("%Y-%m-%d"),
        "active_days": int(len(active_dates)),
        "gross_alpha_total": totals["gross_alpha_total"],
        "net_alpha_total": totals["net_alpha_total"],
        "total_cost_drag": totals["total_cost_drag"],
        "cost_breakdown": totals["cost_breakdown"],
        "reconciliation": reconciliation,
        "warning_gates": warnings,
        "fail_gates": failures,
        "drawdown": drawdown_metadata,
        "funding_gap_symbols": sorted(gap_symbols),
        "funding_gap_cost_days_from_task002": int(primary_costs["funding_gap"].sum()),
        "interval_groups": sorted(by_interval["funding_interval_group"].astype(str).tolist()),
        "task002_reproducibility_hash": cost_summary.get("reproducibility_hash", ""),
        "input_hashes": input_hashes,
        "git_commit": commit,
        "methodology": {
            "return_dating": "positions.date + 1 day = return_date",
            "return_dating_reason": (
                "run008 computes each day's portfolio_return from weights held before applying that "
                "day's effective target; positions rows are emitted after the target update."
            ),
            "gross_formula": "gross_contribution = prior_day_weight * symbol_open_to_open_return",
            "net_formula": "net_contribution = gross_contribution - fee_cost - slippage_cost - funding_cost",
            "tradable_filter": (
                "existing data_quality.apply_data_quality_policy tradable_membership is applied on "
                "return_date + symbol before calculating gross contribution"
            ),
            "primary_cost_source": "TASK-002 positions_cost parquet filtered to realistic_combo",
            "funding_gap_source": "TASK-002 positions_cost funding_gap column; no funding cost recomputation",
            "funding_interval_source": "data/crypto/funding_rates.parquet interval_hours mapped by symbol",
        },
    }
    summary["reproducibility_hash"] = canonical_hash({
        "summary_without_hash": summary,
        "table_hashes": _table_hashes({
            "by_symbol": by_symbol,
            "by_year": by_year,
            "by_month": by_month,
            "by_side": by_side,
            "by_funding_gap": by_gap,
            "by_interval": by_interval,
            "by_cost_type": by_cost_type,
            "top_contributors": top,
            "drawdown": drawdown,
        }),
    })
    summary["reproducibility_hash_check_passed"] = (
        summary["reproducibility_hash"]
        == canonical_hash({
            "summary_without_hash": {k: v for k, v in summary.items() if k != "reproducibility_hash"},
            "table_hashes": _table_hashes({
                "by_symbol": by_symbol,
                "by_year": by_year,
                "by_month": by_month,
                "by_side": by_side,
                "by_funding_gap": by_gap,
                "by_interval": by_interval,
                "by_cost_type": by_cost_type,
                "top_contributors": top,
                "drawdown": drawdown,
            }),
        })
    )
    # The check above intentionally differs because the first hash includes the
    # check field after insertion. Recompute a stable final hash instead.
    stable_payload = {
        "summary_without_hash": {
            k: v
            for k, v in summary.items()
            if k not in {"reproducibility_hash", "reproducibility_hash_check_passed"}
        },
        "table_hashes": _table_hashes({
            "by_symbol": by_symbol,
            "by_year": by_year,
            "by_month": by_month,
            "by_side": by_side,
            "by_funding_gap": by_gap,
            "by_interval": by_interval,
            "by_cost_type": by_cost_type,
            "top_contributors": top,
            "drawdown": drawdown,
        }),
    }
    summary["reproducibility_hash"] = canonical_hash(stable_payload)
    summary["reproducibility_hash_check_passed"] = summary["reproducibility_hash"] == canonical_hash(stable_payload)

    tables = {
        "by_symbol": by_symbol,
        "by_year": by_year,
        "by_month": by_month,
        "by_side": by_side,
        "by_funding_gap": by_gap,
        "by_interval": by_interval,
        "by_cost_type": by_cost_type,
        "top_contributors": top,
        "drawdown": drawdown,
    }
    log_text = build_log_text(summary)
    return AttributionResult(tables=tables, summary=summary, log_text=log_text)


def build_log_text(summary: dict[str, Any]) -> str:
    warning_names = [
        name for name, gate in summary["warning_gates"].items() if gate.get("triggered")
    ]
    failure_names = [
        name for name, gate in summary["fail_gates"].items() if gate.get("triggered")
    ]
    lines = [
        "TASK-003 baseline attribution",
        f"run_date={summary['run_date']}",
        f"baseline_run_id={summary['baseline_run_id']}",
        f"cost_stress_run_id={summary['cost_stress_run_id']}",
        f"primary_scenario={summary['primary_scenario']}",
        f"git_commit={summary['git_commit']}",
        f"reproducibility_hash={summary['reproducibility_hash']}",
        f"active_window={summary['active_start']}..{summary['active_end']}",
        f"active_days={summary['active_days']}",
        "",
        "methodology:",
        json.dumps(summary["methodology"], indent=2, sort_keys=True, ensure_ascii=True),
        "",
        "reconciliation:",
        json.dumps(summary["reconciliation"], indent=2, sort_keys=True, ensure_ascii=True),
        "",
        "warning_gates:",
        json.dumps(summary["warning_gates"], indent=2, sort_keys=True, ensure_ascii=True),
        "",
        "fail_gates:",
        json.dumps(summary["fail_gates"], indent=2, sort_keys=True, ensure_ascii=True),
        "",
        f"warnings_triggered={warning_names if warning_names else 'none'}",
        f"failures_triggered={failure_names if failure_names else 'none'}",
        "",
        "input_hashes:",
        json.dumps(summary["input_hashes"], indent=2, sort_keys=True, ensure_ascii=True),
    ]
    return "\n".join(lines) + "\n"


def _build_fact_table(
    gross: pd.DataFrame,
    costs: pd.DataFrame,
    interval: pd.DataFrame,
    active_dates: set[pd.Timestamp],
    config: AttributionConfig,
) -> pd.DataFrame:
    fact = gross.merge(costs, on=["date", "symbol"], how="outer")
    fact["date"] = pd.to_datetime(fact["date"]).dt.normalize()
    fact = fact[fact["date"].isin(active_dates)].copy()
    fact["symbol"] = fact["symbol"].astype(str)
    fill_zero = [
        "weight_prior",
        "symbol_return",
        "gross_contribution",
        "signal_rank",
        "signal_value",
        "cost_weight",
        "fee_cost",
        "funding_cost",
        "slippage_cost",
        "outlier_count_today",
        "funding_settlement_count",
        "entry_turnover",
        "exit_turnover",
        "trade_turnover",
        "outlier_funding_cost",
    ]
    for col in fill_zero:
        if col in fact.columns:
            fact[col] = pd.to_numeric(fact[col], errors="coerce").fillna(0.0)
    fact["funding_gap"] = fact.get("funding_gap", False)
    fact["funding_gap"] = fact["funding_gap"].fillna(False).astype(bool)
    fact["position_date"] = pd.to_datetime(fact["position_date"], errors="coerce").dt.normalize()
    fact["has_prior_position"] = fact["weight_prior"].abs().gt(0)
    fact["side_weight"] = np.where(
        fact["weight_prior"].abs().gt(0),
        fact["weight_prior"],
        fact["cost_weight"],
    )
    fact["side"] = fact["side_weight"].astype(float).map(signed_side)
    fact["is_long_day"] = fact["weight_prior"].gt(0)
    fact["is_short_day"] = fact["weight_prior"].lt(0)
    fact["net_contribution"] = (
        fact["gross_contribution"].astype(float)
        - fact["fee_cost"].astype(float)
        - fact["slippage_cost"].astype(float)
        - fact["funding_cost"].astype(float)
    )
    fact["is_funding_gap_symbol"] = fact["symbol"].isin(set(config.known_funding_gap_symbols))
    fact = fact.merge(interval, on="symbol", how="left")
    fact["funding_interval_group"] = fact["funding_interval_group"].fillna("unknown")
    return fact.sort_values(["date", "symbol"]).reset_index(drop=True)


def _daily_reconciliation(
    fact: pd.DataFrame,
    baseline: pd.DataFrame,
    cost_stress: pd.DataFrame,
    config: AttributionConfig,
) -> pd.DataFrame:
    daily = fact.groupby("date", as_index=False).agg(
        gross_sum=("gross_contribution", "sum"),
        net_sum=("net_contribution", "sum"),
        fee_cost=("fee_cost", "sum"),
        slippage_cost=("slippage_cost", "sum"),
        funding_cost=("funding_cost", "sum"),
    )
    real = cost_stress[cost_stress["scenario"].eq(config.primary_scenario)].copy()
    base_cols = ["date", "portfolio_return", "gross_exposure"]
    stress_cols = ["date", "portfolio_return_net"]
    check = (
        baseline.loc[:, base_cols]
        .merge(real.loc[:, stress_cols], on="date", how="left")
        .merge(daily, on="date", how="left")
    )
    for col in ["gross_sum", "net_sum", "fee_cost", "slippage_cost", "funding_cost"]:
        check[col] = check[col].fillna(0.0)
    check["gross_diff"] = check["portfolio_return"].astype(float) - check["gross_sum"].astype(float)
    check["net_diff"] = check["portfolio_return_net"].astype(float) - check["net_sum"].astype(float)
    return check


def _reconciliation_stats(daily: pd.DataFrame, tolerance: float) -> dict[str, Any]:
    active = daily[daily["gross_exposure"].astype(float).gt(0)].copy()
    return {
        "gross_active_daily_max_diff": float(active["gross_diff"].abs().max()),
        "net_active_daily_max_diff": float(active["net_diff"].abs().max()),
        "gross_active_total_diff": float(active["gross_diff"].sum()),
        "net_active_total_diff": float(active["net_diff"].sum()),
        "gross_bad_days_gt_tolerance": int(active["gross_diff"].abs().gt(tolerance).sum()),
        "net_bad_days_gt_tolerance": int(active["net_diff"].abs().gt(tolerance).sum()),
        "tolerance": tolerance,
    }


def _totals(fact: pd.DataFrame) -> dict[str, Any]:
    gross = float(fact["gross_contribution"].sum())
    fee = float(fact["fee_cost"].sum())
    slippage = float(fact["slippage_cost"].sum())
    funding = float(fact["funding_cost"].sum())
    net = float(fact["net_contribution"].sum())
    total_cost = fee + slippage + funding
    return {
        "gross_alpha_total": gross,
        "net_alpha_total": net,
        "total_cost_drag": total_cost,
        "cost_breakdown": {
            "fee": fee,
            "slippage": slippage,
            "funding": funding,
            "fee_pct": float(fee / total_cost) if total_cost else 0.0,
            "slippage_pct": float(slippage / total_cost) if total_cost else 0.0,
            "funding_pct": float(funding / total_cost) if total_cost else 0.0,
        },
    }


def _table_hashes(tables: dict[str, pd.DataFrame]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, table in tables.items():
        payload = table.copy()
        for col in payload.columns:
            if is_datetime64_any_dtype(payload[col]):
                payload[col] = pd.to_datetime(payload[col]).dt.strftime("%Y-%m-%d")
        hashes[name] = canonical_hash(payload.to_dict(orient="records"))
    return hashes


def _normalize_dates(frame: pd.DataFrame, cols: list[str]) -> None:
    for col in cols:
        frame[col] = pd.to_datetime(frame[col]).dt.normalize()
