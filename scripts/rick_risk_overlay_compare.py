"""Ad hoc comparison for Rick's proposed risk overlay.

This reads official run008/TASK-002 outputs only. It does not rerun signals,
ranking, universe selection, baseline, cost stress, or attribution.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.attribution.costs import load_primary_costs
from src.attribution.reproducibility import build_input_hashes, canonical_hash, git_commit
from src.attribution.returns import build_gross_contributions, load_tradable_membership
from src.variants.task007 import (
    Task007Config,
    _annual_ratio,
    _apply_variant_costs,
    _build_base_fact,
    _max_drawdown,
    _safe_div,
)


@dataclass(frozen=True)
class RiskOverlayConfig:
    output_date: str = "20260516"
    baseline_run_id: str = "20260513_run008"
    cost_stress_run_id: str = "20260515"
    primary_scenario: str = "realistic_combo"
    max_positions: int = 10
    symbol_cap_abs_weight: float = 0.05
    long_gross_cap: float = 0.50
    short_gross_cap: float = 0.50
    total_risk_cap: float = 0.04
    per_trade_risk_cap: float = 0.005
    min_trade_risk: float = 0.0015
    risk_proxy_stop_pct: float = 0.10
    annualization_factor: float = 365.25
    baseline_path: Path = Path("outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv")
    positions_path: Path = Path("outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet")
    positions_cost_path: Path = Path("outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet")
    prices_path: Path = Path("data/crypto/prices_daily.parquet")
    universe_path: Path = Path("data/crypto/universe_membership.parquet")
    prev3y_config_path: Path = Path("configs/prev3y_crypto.yaml")
    output_dir: Path = Path("outputs/variants/prev3y_crypto")
    log_dir: Path = Path("outputs/logs/prev3y_crypto")

    def input_paths(self) -> dict[str, Path]:
        return {
            "run008_baseline_csv": self.baseline_path,
            "run008_positions_parquet": self.positions_path,
            "cost_stress_positions_cost_parquet": self.positions_cost_path,
            "prices_daily_parquet": self.prices_path,
            "universe_membership_parquet": self.universe_path,
            "prev3y_crypto_yaml": self.prev3y_config_path,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-date", default="20260516")
    args = parser.parse_args()

    config = RiskOverlayConfig(output_date=args.output_date)
    result = run_compare(config)
    paths = write_outputs(result, config)
    print(json.dumps({
        "status": "REVIEW_READY",
        "outputs": {key: str(path) for key, path in paths.items()},
        "reproducibility_hash": result["summary_json"]["reproducibility_hash"],
        "summary": result["summary"].to_dict(orient="records"),
    }, indent=2, sort_keys=True))


def run_compare(config: RiskOverlayConfig) -> dict[str, Any]:
    baseline = pd.read_csv(config.baseline_path, parse_dates=["date"])
    positions = pd.read_parquet(config.positions_path)
    positions_cost = pd.read_parquet(config.positions_cost_path)
    prices = pd.read_parquet(config.prices_path)
    baseline["date"] = pd.to_datetime(baseline["date"]).dt.normalize()
    active_dates = set(baseline.loc[baseline["gross_exposure"].astype(float).gt(0), "date"])

    tradable = load_tradable_membership(
        config.prev3y_config_path,
        config.prices_path,
        config.universe_path,
    )
    gross = build_gross_contributions(positions, prices, tradable)
    primary_costs = load_primary_costs(positions_cost, config.primary_scenario)
    fact = _build_base_fact(gross, primary_costs, baseline, active_dates)

    targets = {
        "proposal_top5x2_at_5pct_notional": _build_target_table(
            positions,
            config,
            total_risk_cap=None,
        ),
        "proposal_top5x2_total_risk_4pct_proxy": _build_target_table(
            positions,
            config,
            total_risk_cap=config.total_risk_cap,
        ),
        "top5x2_keep_original_weight_cap5": _build_keep_original_target(positions, config),
    }

    frames = [_baseline_variant_fact(fact)]
    for variant, target in targets.items():
        frames.append(_target_variant_fact(fact, target, variant))
    all_fact = pd.concat(frames, ignore_index=True)

    daily_returns = _daily_returns(all_fact, baseline, config)
    exposure_tables = {"baseline_current_long_short": _baseline_exposure(positions, active_dates)}
    exposure_tables.update({variant: _target_exposure(target, active_dates) for variant, target in targets.items()})
    summary = _summary(all_fact, daily_returns, exposure_tables, config)
    daily = _daily_with_exposure(daily_returns, exposure_tables)
    summary_json = _summary_json(summary, daily, targets, config)
    summary_json["table_hashes"] = {
        "summary": _frame_hash(summary),
        "daily": _frame_hash(daily),
    }
    summary_json["reproducibility_hash"] = canonical_hash({
        "summary_without_hash": {
            key: value for key, value in summary_json.items()
            if key != "reproducibility_hash"
        },
    })
    log_text = _log_text(summary_json, config)
    return {
        "summary": summary,
        "daily": daily,
        "summary_json": summary_json,
        "log_text": log_text,
    }


def write_outputs(result: dict[str, Any], config: RiskOverlayConfig) -> dict[str, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.log_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary_csv": config.output_dir / f"{config.output_date}_rick_risk_overlay_summary.csv",
        "daily_csv": config.output_dir / f"{config.output_date}_rick_risk_overlay_daily.csv",
        "summary_json": config.output_dir / f"{config.output_date}_rick_risk_overlay_summary.json",
        "log": config.log_dir / f"{config.output_date}_rick_risk_overlay_compare.log",
    }
    result["summary"].to_csv(paths["summary_csv"], index=False)
    result["daily"].to_csv(paths["daily_csv"], index=False)
    paths["summary_json"].write_text(
        json.dumps(result["summary_json"], indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["log"].write_text(result["log_text"], encoding="utf-8")
    return paths


def _baseline_variant_fact(fact: pd.DataFrame) -> pd.DataFrame:
    out = fact.copy()
    return_weight = out["return_base_weight"].astype(float)
    cost_weight = out["cost_base_weight"].astype(float)
    out["variant"] = "baseline_current_long_short"
    out["variant_return_weight"] = return_weight
    out["variant_cost_weight"] = cost_weight
    out["variant_weight"] = np.where(cost_weight.abs().gt(0), cost_weight, return_weight)
    return _apply_variant_costs(out)


def _target_variant_fact(fact: pd.DataFrame, target: pd.DataFrame, variant: str) -> pd.DataFrame:
    out = fact.copy()
    out["variant"] = variant
    out["variant_return_weight"] = _weights_from_target(out, target, "position_date")
    out["variant_cost_weight"] = _weights_from_target(out, target, "date")
    cost_weight = out["variant_cost_weight"].astype(float)
    return_weight = out["variant_return_weight"].astype(float)
    out["variant_weight"] = np.where(cost_weight.abs().gt(0), cost_weight, return_weight)
    return _apply_variant_costs(out)


def _build_target_table(
    positions: pd.DataFrame,
    config: RiskOverlayConfig,
    total_risk_cap: float | None,
) -> pd.DataFrame:
    pos = _positions_frame(positions)
    rows: list[dict[str, Any]] = []
    long_slots = config.max_positions // 2
    short_slots = config.max_positions - long_slots
    for date, group in pos.groupby("date", sort=True):
        longs = (
            group[group["weight"].gt(0)]
            .sort_values(["signal_rank", "symbol"], ascending=[True, True])
            .head(long_slots)
        )
        shorts = (
            group[group["weight"].lt(0)]
            .sort_values(["signal_rank", "symbol"], ascending=[False, True])
            .head(short_slots)
        )
        weights = pd.Series(dtype=float)
        if not longs.empty:
            long_abs = min(config.symbol_cap_abs_weight, config.long_gross_cap / max(len(longs), 1))
            weights = pd.concat([weights, pd.Series(long_abs, index=longs["symbol"].astype(str))])
        if not shorts.empty:
            short_abs = min(config.symbol_cap_abs_weight, config.short_gross_cap / max(len(shorts), 1))
            weights = pd.concat([weights, pd.Series(-short_abs, index=shorts["symbol"].astype(str))])
        if weights.empty:
            continue
        weights = _apply_risk_proxy(weights, config, total_risk_cap)
        for symbol, weight in weights.items():
            if abs(float(weight)) > 0.0:
                rows.append({"date": date, "symbol": str(symbol), "target_weight": float(weight)})
    return pd.DataFrame(rows, columns=["date", "symbol", "target_weight"])


def _build_keep_original_target(positions: pd.DataFrame, config: RiskOverlayConfig) -> pd.DataFrame:
    pos = _positions_frame(positions)
    rows: list[dict[str, Any]] = []
    for date, group in pos.groupby("date", sort=True):
        longs = (
            group[group["weight"].gt(0)]
            .sort_values(["signal_rank", "symbol"], ascending=[True, True])
            .head(config.max_positions // 2)
        )
        shorts = (
            group[group["weight"].lt(0)]
            .sort_values(["signal_rank", "symbol"], ascending=[False, True])
            .head(config.max_positions - config.max_positions // 2)
        )
        selected = pd.concat([longs, shorts], axis=0)
        for row in selected.itertuples(index=False):
            capped = max(min(float(row.weight), config.symbol_cap_abs_weight), -config.symbol_cap_abs_weight)
            rows.append({"date": date, "symbol": str(row.symbol), "target_weight": capped})
    return pd.DataFrame(rows, columns=["date", "symbol", "target_weight"])


def _apply_risk_proxy(
    weights: pd.Series,
    config: RiskOverlayConfig,
    total_risk_cap: float | None,
) -> pd.Series:
    max_abs_by_trade_risk = config.per_trade_risk_cap / config.risk_proxy_stop_pct
    out = pd.Series(
        np.sign(weights) * np.minimum(np.abs(weights), max_abs_by_trade_risk),
        index=weights.index,
        dtype=float,
    )
    if total_risk_cap is not None:
        total_risk = float((out.abs() * config.risk_proxy_stop_pct).sum())
        if total_risk > total_risk_cap and total_risk > 0.0:
            out = out * (total_risk_cap / total_risk)
    trade_risk = out.abs() * config.risk_proxy_stop_pct
    return out.where(trade_risk.ge(config.min_trade_risk), 0.0)


def _positions_frame(positions: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "symbol", "weight", "signal_rank"}
    missing = required - set(positions.columns)
    if missing:
        raise ValueError(f"positions missing columns: {sorted(missing)}")
    pos = positions.loc[:, ["date", "symbol", "weight", "signal_rank"]].copy()
    pos["date"] = pd.to_datetime(pos["date"]).dt.normalize()
    pos["symbol"] = pos["symbol"].astype(str)
    pos["weight"] = pd.to_numeric(pos["weight"], errors="coerce").fillna(0.0)
    pos["signal_rank"] = pd.to_numeric(pos["signal_rank"], errors="coerce").fillna(0).astype(int)
    return pos


def _weights_from_target(fact: pd.DataFrame, target: pd.DataFrame, date_col: str) -> pd.Series:
    keys = fact.loc[:, [date_col, "symbol"]].copy().rename(columns={date_col: "date"})
    keys["date"] = pd.to_datetime(keys["date"]).dt.normalize()
    target_norm = target.copy()
    target_norm["date"] = pd.to_datetime(target_norm["date"]).dt.normalize()
    merged = keys.merge(target_norm, on=["date", "symbol"], how="left")
    return pd.Series(merged["target_weight"].fillna(0.0).to_numpy(dtype=float), index=fact.index)


def _daily_returns(all_fact: pd.DataFrame, baseline: pd.DataFrame, config: RiskOverlayConfig) -> pd.DataFrame:
    daily = all_fact.groupby(["variant", "date"], as_index=False).agg(
        portfolio_return_gross=("variant_gross_contribution", "sum"),
        portfolio_return_net=("variant_net_contribution", "sum"),
        fee_cost=("variant_fee_cost", "sum"),
        slippage_cost=("variant_slippage_cost", "sum"),
        funding_cost=("variant_funding_cost", "sum"),
        turnover_proxy=("variant_trade_turnover", "sum"),
    )
    daily = daily.merge(
        baseline.loc[:, ["date", "benchmark_cash_return", "benchmark_btc_return", "benchmark_eqw_return"]],
        on="date",
        how="left",
    )
    return daily.sort_values(["variant", "date"]).reset_index(drop=True)


def _baseline_exposure(positions: pd.DataFrame, active_dates: set[pd.Timestamp]) -> pd.DataFrame:
    pos = _positions_frame(positions)
    pos = pos[pos["date"].isin(active_dates)].copy()
    return _exposure_from_weight_rows(pos.rename(columns={"weight": "target_weight"}), active_dates)


def _target_exposure(target: pd.DataFrame, active_dates: set[pd.Timestamp]) -> pd.DataFrame:
    return _exposure_from_weight_rows(target, active_dates)


def _exposure_from_weight_rows(frame: pd.DataFrame, active_dates: set[pd.Timestamp]) -> pd.DataFrame:
    dates = pd.DataFrame({"date": sorted(active_dates)})
    if frame.empty:
        grouped = pd.DataFrame(columns=["date"])
    else:
        grouped = frame.groupby("date", as_index=False).agg(
            gross_exposure=("target_weight", lambda x: float(np.abs(x).sum())),
            long_gross=("target_weight", lambda x: float(x[x > 0].sum())),
            short_gross=("target_weight", lambda x: float(np.abs(x[x < 0]).sum())),
            net_exposure=("target_weight", "sum"),
            n_longs=("target_weight", lambda x: int((x > 0).sum())),
            n_shorts=("target_weight", lambda x: int((x < 0).sum())),
            max_abs_weight=("target_weight", lambda x: float(np.abs(x).max()) if len(x) else 0.0),
        )
    out = dates.merge(grouped, on="date", how="left").fillna(0.0)
    out["n_longs"] = out["n_longs"].astype(int)
    out["n_shorts"] = out["n_shorts"].astype(int)
    return out


def _daily_with_exposure(daily_returns: pd.DataFrame, exposure_tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for variant, group in daily_returns.groupby("variant", sort=False):
        exposure = exposure_tables[str(variant)]
        merged = group.merge(exposure, on="date", how="left")
        frames.append(merged)
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out.sort_values(["variant", "date"]).reset_index(drop=True)


def _summary(
    all_fact: pd.DataFrame,
    daily_returns: pd.DataFrame,
    exposure_tables: dict[str, pd.DataFrame],
    config: RiskOverlayConfig,
) -> pd.DataFrame:
    rows = []
    baseline_net = None
    variant_order = [
        "baseline_current_long_short",
        "proposal_top5x2_at_5pct_notional",
        "proposal_top5x2_total_risk_4pct_proxy",
        "top5x2_keep_original_weight_cap5",
    ]
    for variant in variant_order:
        variant_daily = daily_returns[daily_returns["variant"].eq(variant)].sort_values("date").copy()
        exposure = exposure_tables[variant]
        net_returns = variant_daily["portfolio_return_net"].astype(float)
        gross_returns = variant_daily["portfolio_return_gross"].astype(float)
        equity = (1.0 + net_returns).cumprod()
        years = max(len(variant_daily) / config.annualization_factor, 1.0 / config.annualization_factor)
        cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0) if len(equity) and equity.iloc[-1] > 0 else -1.0
        net_alpha = float(net_returns.sum())
        gross_alpha = float(gross_returns.sum())
        if baseline_net is None:
            baseline_net = net_alpha
        variant_fact = all_fact[all_fact["variant"].eq(variant)].copy()
        long_net = float(variant_fact.loc[variant_fact["variant_return_weight"].gt(0), "variant_net_contribution"].sum())
        short_net = float(variant_fact.loc[variant_fact["variant_return_weight"].lt(0), "variant_net_contribution"].sum())
        nonzero_risk = exposure.loc[exposure["max_abs_weight"].gt(0), "max_abs_weight"] * config.risk_proxy_stop_pct
        rows.append({
            "variant": variant,
            "active_days": int(len(variant_daily)),
            "cum_return_net": float(equity.iloc[-1] - 1.0) if len(equity) else 0.0,
            "cagr_active": cagr,
            "sharpe_active": _annual_ratio(net_returns, config.annualization_factor),
            "ir_vs_equal_weight_active": _annual_ratio(
                net_returns - variant_daily["benchmark_eqw_return"].astype(float).fillna(0.0),
                config.annualization_factor,
            ),
            "ir_vs_btc_active": _annual_ratio(
                net_returns - variant_daily["benchmark_btc_return"].astype(float),
                config.annualization_factor,
            ),
            "max_dd": _max_drawdown(net_returns),
            "gross_alpha": gross_alpha,
            "net_alpha": net_alpha,
            "net_alpha_delta_vs_baseline": net_alpha - baseline_net,
            "alpha_retention_pct": _safe_div(net_alpha, baseline_net),
            "long_net_contribution": long_net,
            "short_net_contribution": short_net,
            "avg_gross_exposure": float(exposure["gross_exposure"].mean()),
            "max_gross_exposure": float(exposure["gross_exposure"].max()),
            "avg_long_gross": float(exposure["long_gross"].mean()),
            "max_long_gross": float(exposure["long_gross"].max()),
            "avg_short_gross": float(exposure["short_gross"].mean()),
            "max_short_gross": float(exposure["short_gross"].max()),
            "avg_positions": float((exposure["n_longs"] + exposure["n_shorts"]).mean()),
            "max_positions": int((exposure["n_longs"] + exposure["n_shorts"]).max()),
            "max_abs_weight": float(exposure["max_abs_weight"].max()),
            "max_total_risk_proxy": float((exposure["gross_exposure"] * config.risk_proxy_stop_pct).max()),
            "max_trade_risk_proxy": float((exposure["max_abs_weight"] * config.risk_proxy_stop_pct).max()),
            "min_nonzero_trade_risk_proxy": float(nonzero_risk.min()) if len(nonzero_risk) else 0.0,
            "turnover_proxy_sum": float(variant_daily["turnover_proxy"].sum()),
            "fee_cost": float(variant_fact["variant_fee_cost"].sum()),
            "slippage_cost": float(variant_fact["variant_slippage_cost"].sum()),
            "funding_cost": float(variant_fact["variant_funding_cost"].sum()),
        })
    return pd.DataFrame(rows)


def _summary_json(
    summary: pd.DataFrame,
    daily: pd.DataFrame,
    targets: dict[str, pd.DataFrame],
    config: RiskOverlayConfig,
) -> dict[str, Any]:
    return {
        "run_date": config.output_date,
        "analysis_basis": "ad hoc post-processing overlay study requested by Rick; not a trading decision",
        "baseline_run_id": config.baseline_run_id,
        "cost_stress_run_id": config.cost_stress_run_id,
        "primary_scenario": config.primary_scenario,
        "methodology": {
            "signals_ranking_universe_data_quality": "unchanged; official run008/TASK-002 inputs are read-only",
            "selection": "keep strongest 5 longs by lowest signal_rank and strongest 5 shorts by highest signal_rank",
            "return_dating": "uses TASK-007 convention: positions.date + 1 day = return_date",
            "cost_policy": "TASK-002 realistic_combo symbol-day costs scaled by abs(variant_cost_weight / original_cost_weight); costs are not fully recomputed from turnover",
            "risk_proxy": (
                "run008 has no stop-loss or R-distance columns; risk caps are checked with "
                f"risk_proxy = abs(weight) * {config.risk_proxy_stop_pct:.2%}"
            ),
            "total_risk_cap": config.total_risk_cap,
            "per_trade_risk_cap": config.per_trade_risk_cap,
            "min_trade_risk": config.min_trade_risk,
            "symbol_cap_abs_weight": config.symbol_cap_abs_weight,
            "max_positions": config.max_positions,
            "long_gross_cap": config.long_gross_cap,
            "short_gross_cap": config.short_gross_cap,
        },
        "summary": summary.to_dict(orient="records"),
        "input_hashes": build_input_hashes(config.input_paths()),
        "git_commit": git_commit(),
    }


def _log_text(summary_json: dict[str, Any], config: RiskOverlayConfig) -> str:
    return "\n".join([
        "Rick risk overlay comparison",
        f"run_date={config.output_date}",
        "analysis_basis=ad hoc post-processing overlay study, not a trading decision",
        f"baseline_run_id={config.baseline_run_id}",
        f"cost_stress_run_id={config.cost_stress_run_id}",
        f"primary_scenario={config.primary_scenario}",
        f"git_commit={summary_json['git_commit']}",
        f"reproducibility_hash={summary_json['reproducibility_hash']}",
        "",
        "methodology:",
        json.dumps(summary_json["methodology"], indent=2, sort_keys=True, ensure_ascii=True),
        "",
        "input_hashes:",
        json.dumps(summary_json["input_hashes"], indent=2, sort_keys=True, ensure_ascii=True),
    ]) + "\n"


def _frame_hash(frame: pd.DataFrame) -> str:
    records = json.loads(frame.to_json(orient="records", date_format="iso", double_precision=12))
    return canonical_hash(records)


if __name__ == "__main__":
    main()
