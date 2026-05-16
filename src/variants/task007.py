from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.attribution.config import AttributionConfig
from src.attribution.costs import load_primary_costs
from src.attribution.reproducibility import build_input_hashes, canonical_hash, git_commit
from src.attribution.returns import build_gross_contributions, load_tradable_membership


@dataclass(frozen=True)
class Task007Config:
    output_date: str = "20260515"
    tolerance: float = 1e-6
    annualization_factor: float = 365.25
    baseline_run_id: str = "20260513_run008"
    cost_stress_run_id: str = "20260515"
    attribution_run_id: str = "20260515"
    primary_scenario: str = "realistic_combo"
    baseline_path: Path = Path("outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv")
    positions_path: Path = Path("outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet")
    cost_stress_path: Path = Path("outputs/backtests/prev3y_crypto/20260515_cost_stress.csv")
    positions_cost_path: Path = Path("outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet")
    attribution_summary_path: Path = Path("outputs/attribution/prev3y_crypto/20260515_attribution_summary.json")
    prices_path: Path = Path("data/crypto/prices_daily.parquet")
    funding_path: Path = Path("data/crypto/funding_rates.parquet")
    universe_path: Path = Path("data/crypto/universe_membership.parquet")
    prev3y_config_path: Path = Path("configs/prev3y_crypto.yaml")
    output_dir: Path = Path("outputs/variants/prev3y_crypto")
    log_dir: Path = Path("outputs/logs/prev3y_crypto")
    review_packet_path: Path = Path("docs/research/review_packets/REVIEW-007_PACKET.md")
    review_numbers_path: Path = Path("docs/research/review_packets/REVIEW-007_NUMBERS.json")
    high_funding_threshold_8h: float = 0.0003
    high_funding_window_days: int = 30
    dot_symbol: str = "BYBIT:DOTUSDT.P"
    cap_weight_abs: float = 0.05
    warning_thresholds: dict[str, float] = field(default_factory=lambda: {
        "short_only_rescaled_dd_multiple": 1.5,
        "combined_sharpe_min": 0.5,
        "combined_ir_eqw_min": 0.2,
        "top5_concentration_max": 0.60,
        "single_symbol_concentration_max": 0.25,
        "cap_alpha_loss_max": 0.50,
    })

    def input_paths(self) -> dict[str, Path]:
        return {
            "run008_baseline_csv": self.baseline_path,
            "run008_positions_parquet": self.positions_path,
            "cost_stress_csv": self.cost_stress_path,
            "cost_stress_positions_cost_parquet": self.positions_cost_path,
            "attribution_summary_json": self.attribution_summary_path,
            "prices_daily_parquet": self.prices_path,
            "funding_rates_parquet": self.funding_path,
            "universe_membership_parquet": self.universe_path,
            "prev3y_crypto_yaml": self.prev3y_config_path,
        }


@dataclass(frozen=True)
class Task007Result:
    daily: pd.DataFrame
    summary: pd.DataFrame
    concentration: pd.DataFrame
    cost_breakdown: pd.DataFrame
    summary_json: dict[str, Any]
    packet_text: str
    log_text: str


VARIANT_ORDER = [
    "baseline_current_long_short",
    "short_only_unscaled",
    "short_only_rescaled",
    "long_only_unscaled",
    "long_only_rescaled",
    "no_long_side",
    "long_half_weight",
    "long_with_50pct_cap",
    "top5_symbol_cap_5pct",
    "DOT_capped",
    "no_DOT",
    "high_funding_cost_filter",
    "combined_paper_safe_variant",
]


def run_task007(config: Task007Config) -> Task007Result:
    baseline = pd.read_csv(config.baseline_path, parse_dates=["date"])
    cost_stress = pd.read_csv(config.cost_stress_path, parse_dates=["date"])
    positions = pd.read_parquet(config.positions_path)
    positions_cost = pd.read_parquet(config.positions_cost_path)
    prices = pd.read_parquet(config.prices_path)
    funding = pd.read_parquet(config.funding_path)
    attribution_summary = json.loads(config.attribution_summary_path.read_text(encoding="utf-8"))

    _normalize_date(baseline, "date")
    _normalize_date(cost_stress, "date")
    active_dates = set(baseline.loc[baseline["gross_exposure"].astype(float).gt(0), "date"])
    if not active_dates:
        raise RuntimeError("NEED_CLARIFICATION: run008 baseline has no active dates")

    attribution_cfg = AttributionConfig()
    tradable = load_tradable_membership(
        config.prev3y_config_path,
        config.prices_path,
        config.universe_path,
    )
    gross = build_gross_contributions(positions, prices, tradable)
    primary_costs = load_primary_costs(positions_cost, config.primary_scenario)
    fact = _build_base_fact(gross, primary_costs, baseline, active_dates)
    funding_flags = _high_funding_flags(funding, fact, config)
    fact = fact.merge(funding_flags, on=["date", "symbol"], how="left")
    fact["high_funding_filter_flag"] = fact["high_funding_filter_flag"].fillna(False).astype(bool)
    fact["funding_avg_30d_8h"] = fact["funding_avg_30d_8h"].fillna(0.0).astype(float)

    baseline_symbol = _symbol_contributions(
        _apply_variant_costs(
            fact.assign(
                variant="baseline_current_long_short",
                variant_return_weight=fact["return_base_weight"],
                variant_cost_weight=fact["cost_base_weight"],
                variant_weight=fact["original_weight"],
            )
        )
    )
    top5_symbols = (
        baseline_symbol[baseline_symbol["net_alpha_contribution"].gt(0)]
        .sort_values("net_alpha_contribution", ascending=False)
        .head(5)["symbol"]
        .astype(str)
        .tolist()
    )

    variant_frames = []
    for variant in VARIANT_ORDER:
        return_weights = _variant_weights(fact, fact["return_base_weight"], variant, top5_symbols, config)
        cost_weights = _variant_weights(fact, fact["cost_base_weight"], variant, top5_symbols, config)
        variant_fact = fact.copy()
        variant_fact["variant"] = variant
        variant_fact["variant_return_weight"] = return_weights
        variant_fact["variant_cost_weight"] = cost_weights
        variant_fact["variant_weight"] = np.where(
            variant_fact["variant_cost_weight"].abs().gt(0),
            variant_fact["variant_cost_weight"],
            variant_fact["variant_return_weight"],
        )
        variant_fact = _apply_variant_costs(variant_fact)
        variant_frames.append(variant_fact)
    all_fact = pd.concat(variant_frames, ignore_index=True)

    daily = _daily_table(all_fact, baseline, cost_stress, config)
    summary = _summary_table(all_fact, daily, baseline, attribution_summary, config)
    concentration = _concentration_table(all_fact, top5_symbols)
    cost_breakdown = _cost_breakdown_table(all_fact)
    summary_json = _summary_json(summary, concentration, cost_breakdown, daily, top5_symbols, attribution_summary, config)
    _apply_gates(summary_json, daily, cost_stress, config)
    if summary_json["fail_gates"]["baseline_mismatch"]["triggered"]:
        raise RuntimeError(
            "NEED_CLARIFICATION: baseline_current_long_short does not match TASK-002 realistic_combo "
            f"max_diff={summary_json['fail_gates']['baseline_mismatch']['value']}"
        )

    output_table_hashes = {
        "daily": _frame_hash(daily),
        "summary": _frame_hash(summary),
        "concentration": _frame_hash(concentration),
        "cost_breakdown": _frame_hash(cost_breakdown),
    }
    summary_json["table_hashes"] = output_table_hashes
    summary_json["reproducibility_hash"] = canonical_hash({
        "summary_without_hash": {
            key: value for key, value in summary_json.items()
            if key != "reproducibility_hash"
        },
        "table_hashes": output_table_hashes,
    })

    packet_text = _review_packet(summary_json, summary, concentration, config)
    log_text = _log_text(summary_json, config)
    return Task007Result(
        daily=daily,
        summary=summary,
        concentration=concentration,
        cost_breakdown=cost_breakdown,
        summary_json=summary_json,
        packet_text=packet_text,
        log_text=log_text,
    )


def write_task007_outputs(result: Task007Result, config: Task007Config) -> tuple[dict[str, Path], list[str]]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.log_dir.mkdir(parents=True, exist_ok=True)
    config.review_packet_path.parent.mkdir(parents=True, exist_ok=True)

    paths = {
        "daily": config.output_dir / f"{config.output_date}_task007_variant_daily.csv",
        "summary_csv": config.output_dir / f"{config.output_date}_task007_variant_summary.csv",
        "summary_json": config.output_dir / f"{config.output_date}_task007_variant_summary.json",
        "concentration": config.output_dir / f"{config.output_date}_task007_variant_concentration.csv",
        "cost_breakdown": config.output_dir / f"{config.output_date}_task007_variant_cost_breakdown.csv",
        "log": config.log_dir / f"{config.output_date}_task007_variant_study.log",
        "review_packet": config.review_packet_path,
        "review_numbers": config.review_numbers_path,
    }
    result.daily.to_csv(paths["daily"], index=False)
    result.summary.to_csv(paths["summary_csv"], index=False)
    result.concentration.to_csv(paths["concentration"], index=False)
    result.cost_breakdown.to_csv(paths["cost_breakdown"], index=False)
    paths["summary_json"].write_text(
        json.dumps(result.summary_json, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["log"].write_text(result.log_text, encoding="utf-8")
    paths["review_packet"].write_text(result.packet_text, encoding="utf-8")
    paths["review_numbers"].write_text(
        json.dumps(_review_numbers_payload(result.summary_json, result.summary), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return paths, _validate_outputs(paths, result)


def _build_base_fact(
    gross: pd.DataFrame,
    primary_costs: pd.DataFrame,
    baseline: pd.DataFrame,
    active_dates: set[pd.Timestamp],
) -> pd.DataFrame:
    fact = gross.merge(primary_costs, on=["date", "symbol"], how="outer")
    fact["date"] = pd.to_datetime(fact["date"]).dt.normalize()
    fact = fact[fact["date"].isin(active_dates)].copy()
    fact["symbol"] = fact["symbol"].astype(str)
    for col in ["weight_prior", "cost_weight", "symbol_return", "gross_contribution"]:
        if col in fact.columns:
            fact[col] = pd.to_numeric(fact[col], errors="coerce").fillna(0.0)
    for col in [
        "fee_cost",
        "funding_cost",
        "slippage_cost",
        "entry_turnover",
        "exit_turnover",
        "trade_turnover",
        "outlier_funding_cost",
        "funding_settlement_count",
    ]:
        if col in fact.columns:
            fact[col] = pd.to_numeric(fact[col], errors="coerce").fillna(0.0)
        else:
            fact[col] = 0.0
    fact["return_base_weight"] = fact["weight_prior"].astype(float)
    fact["cost_base_weight"] = fact["cost_weight"].astype(float)
    fact["original_weight"] = np.where(
        fact["cost_base_weight"].abs().gt(0),
        fact["cost_base_weight"],
        fact["return_base_weight"],
    ).astype(float)
    fact["symbol_return"] = fact["symbol_return"].fillna(0.0).astype(float)
    exposure = baseline.loc[:, ["date", "gross_exposure", "net_exposure"]].copy()
    exposure["date"] = pd.to_datetime(exposure["date"]).dt.normalize()
    exposure = exposure.rename(
        columns={
            "gross_exposure": "baseline_gross_exposure",
            "net_exposure": "baseline_net_exposure",
        }
    )
    fact = fact.merge(exposure, on="date", how="left")
    fact["baseline_gross_exposure"] = pd.to_numeric(
        fact["baseline_gross_exposure"], errors="coerce"
    ).fillna(0.0)
    fact["baseline_net_exposure"] = pd.to_numeric(
        fact["baseline_net_exposure"], errors="coerce"
    ).fillna(0.0)
    return fact.sort_values(["date", "symbol"]).reset_index(drop=True)


def _high_funding_flags(funding: pd.DataFrame, fact: pd.DataFrame, config: Task007Config) -> pd.DataFrame:
    required = {"timestamp", "symbol", "funding_rate", "interval_hours"}
    missing = required - set(funding.columns)
    if missing:
        raise ValueError(f"funding missing columns: {sorted(missing)}")
    frame = funding.loc[:, ["timestamp", "symbol", "funding_rate", "interval_hours"]].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["date"] = frame["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str)
    frame["funding_rate"] = pd.to_numeric(frame["funding_rate"], errors="coerce")
    frame["interval_hours"] = pd.to_numeric(frame["interval_hours"], errors="coerce")
    frame = frame.dropna(subset=["funding_rate", "interval_hours"])
    frame = frame[frame["interval_hours"].gt(0)].copy()
    frame["funding_rate_8h"] = frame["funding_rate"] * 8.0 / frame["interval_hours"]
    daily = (
        frame.groupby(["symbol", "date"], as_index=False)["funding_rate_8h"]
        .mean()
        .sort_values(["symbol", "date"])
    )
    rolled = []
    window = f"{int(config.high_funding_window_days)}D"
    for symbol, group in daily.groupby("symbol", sort=False):
        series = group.set_index("date")["funding_rate_8h"].sort_index()
        avg = series.rolling(window, min_periods=1).mean()
        rolled.append(pd.DataFrame({
            "symbol": symbol,
            "date": avg.index,
            "funding_avg_30d_8h": avg.values,
        }))
    if rolled:
        funding_avg = pd.concat(rolled, ignore_index=True)
    else:
        funding_avg = pd.DataFrame(columns=["symbol", "date", "funding_avg_30d_8h"])
    keys = fact.loc[:, ["date", "symbol"]].drop_duplicates()
    out = keys.merge(funding_avg, on=["date", "symbol"], how="left")
    out["funding_avg_30d_8h"] = pd.to_numeric(
        out["funding_avg_30d_8h"], errors="coerce"
    ).fillna(0.0)
    out["high_funding_filter_flag"] = out["funding_avg_30d_8h"].gt(config.high_funding_threshold_8h)
    return out


def _variant_weights(
    fact: pd.DataFrame,
    base_weights: pd.Series,
    variant: str,
    top5_symbols: list[str],
    config: Task007Config,
) -> pd.Series:
    original = pd.Series(base_weights, index=fact.index, dtype=float)
    if variant == "baseline_current_long_short":
        return original.copy()
    if variant in {"short_only_unscaled", "no_long_side"}:
        return original.where(original.lt(0), 0.0)
    if variant == "long_only_unscaled":
        return original.where(original.gt(0), 0.0)
    if variant == "short_only_rescaled":
        return _rescale_side_to_daily_gross(fact, original.where(original.lt(0), 0.0))
    if variant == "long_only_rescaled":
        return _rescale_side_to_daily_gross(fact, original.where(original.gt(0), 0.0))
    if variant == "long_half_weight":
        return np.where(original.gt(0), original * 0.5, original)
    if variant == "long_with_50pct_cap":
        return _cap_long_gross(fact, original, 0.5)
    if variant == "top5_symbol_cap_5pct":
        return _cap_abs_weight(original, fact["symbol"].isin(set(top5_symbols)), config.cap_weight_abs)
    if variant == "DOT_capped":
        return _cap_abs_weight(original, fact["symbol"].eq(config.dot_symbol), config.cap_weight_abs)
    if variant == "no_DOT":
        return original.where(~fact["symbol"].eq(config.dot_symbol), 0.0)
    if variant == "high_funding_cost_filter":
        mask = original.gt(0) & fact["high_funding_filter_flag"]
        return original.where(~mask, 0.0)
    if variant == "combined_paper_safe_variant":
        weights = original.where(~(original.gt(0) & fact["high_funding_filter_flag"]), 0.0)
        combined = fact.copy()
        combined["original_weight"] = weights
        weights = pd.Series(_cap_long_gross(combined, pd.Series(weights, index=fact.index), 0.5), index=fact.index)
        weights = _cap_abs_weight(weights, pd.Series(True, index=fact.index), config.cap_weight_abs)
        return weights
    raise ValueError(f"unsupported variant={variant}")


def _rescale_side_to_daily_gross(fact: pd.DataFrame, weights: pd.Series) -> pd.Series:
    out = pd.Series(weights, index=fact.index, dtype=float).copy()
    side_gross = out.abs().groupby(fact["date"]).transform("sum")
    target = fact["baseline_gross_exposure"].astype(float)
    scale = np.where(side_gross.gt(0), target / side_gross, 0.0)
    return out * scale


def _cap_long_gross(fact: pd.DataFrame, weights: pd.Series, max_total_gross_share: float) -> pd.Series:
    out = pd.Series(weights, index=fact.index, dtype=float).copy()
    long_gross = out.where(out.gt(0), 0.0).groupby(fact["date"]).transform("sum")
    target = fact["baseline_gross_exposure"].astype(float) * float(max_total_gross_share)
    scale = np.where(long_gross.gt(target) & long_gross.gt(0), target / long_gross, 1.0)
    out = np.where(out.gt(0), out * scale, out)
    return pd.Series(out, index=fact.index, dtype=float)


def _cap_abs_weight(weights: pd.Series, mask: pd.Series, cap: float) -> pd.Series:
    out = pd.Series(weights, index=weights.index, dtype=float).copy()
    capped = np.sign(out) * np.minimum(out.abs(), float(cap))
    return pd.Series(np.where(mask, capped, out), index=weights.index, dtype=float)


def _apply_variant_costs(fact: pd.DataFrame) -> pd.DataFrame:
    out = fact.copy()
    raw_cost_original = out["cost_base_weight"].astype(float)
    cost_original = pd.Series(
        np.where(raw_cost_original.abs().gt(0), raw_cost_original, out["return_base_weight"].astype(float)),
        index=out.index,
        dtype=float,
    )
    raw_cost_variant = out["variant_cost_weight"].astype(float)
    cost_variant = pd.Series(
        np.where(raw_cost_original.abs().gt(0), raw_cost_variant, out["variant_return_weight"].astype(float)),
        index=out.index,
        dtype=float,
    )
    return_variant = out["variant_return_weight"].astype(float)
    scale = np.where((cost_original != 0.0) & (cost_variant != 0.0), np.abs(cost_variant / cost_original), 0.0)
    baseline_zero_weight_cost = (
        out["variant"].astype(str).eq("baseline_current_long_short")
        & cost_original.eq(0.0)
        & (
            out["fee_cost"].astype(float).ne(0.0)
            | out["slippage_cost"].astype(float).ne(0.0)
            | out["funding_cost"].astype(float).ne(0.0)
        )
    )
    scale = np.where(baseline_zero_weight_cost, 1.0, scale)
    out["cost_scale"] = scale
    for col in ["fee_cost", "slippage_cost", "funding_cost", "trade_turnover", "outlier_funding_cost"]:
        out[f"variant_{col}"] = out[col].astype(float) * out["cost_scale"]
    out["variant_gross_contribution"] = return_variant * out["symbol_return"].astype(float)
    out["variant_net_contribution"] = (
        out["variant_gross_contribution"]
        - out["variant_fee_cost"]
        - out["variant_slippage_cost"]
        - out["variant_funding_cost"]
    )
    exposure_weight = out["variant_weight"].astype(float)
    out["variant_side"] = np.where(exposure_weight.gt(0), "long", np.where(exposure_weight.lt(0), "short", "flat"))
    return out


def _daily_table(
    fact: pd.DataFrame,
    baseline: pd.DataFrame,
    cost_stress: pd.DataFrame,
    config: Task007Config,
) -> pd.DataFrame:
    daily = fact.groupby(["variant", "date"], as_index=False).agg(
        portfolio_return_gross=("variant_gross_contribution", "sum"),
        portfolio_return_net=("variant_net_contribution", "sum"),
        fee_cost=("variant_fee_cost", "sum"),
        slippage_cost=("variant_slippage_cost", "sum"),
        funding_cost=("variant_funding_cost", "sum"),
        trade_turnover_proxy=("variant_trade_turnover", "sum"),
        gross_exposure=("variant_weight", lambda x: float(np.abs(x).sum())),
        net_exposure=("variant_weight", "sum"),
        n_longs=("variant_weight", lambda x: int((x > 0).sum())),
        n_shorts=("variant_weight", lambda x: int((x < 0).sum())),
        high_funding_filtered_symbol_days=("high_funding_filter_flag", "sum"),
    )
    benchmark_cols = [
        "date",
        "benchmark_return",
        "benchmark_cash_return",
        "benchmark_btc_return",
        "benchmark_eqw_return",
    ]
    daily = daily.merge(baseline.loc[:, benchmark_cols], on="date", how="left")
    real = cost_stress[cost_stress["scenario"].eq(config.primary_scenario)].copy()
    _normalize_date(real, "date")
    real = real.loc[:, ["date", "portfolio_return_net"]].rename(
        columns={"portfolio_return_net": "task002_realistic_combo_net_return"}
    )
    daily = daily.merge(real, on="date", how="left")
    daily["date"] = pd.to_datetime(daily["date"]).dt.strftime("%Y-%m-%d")
    daily["variant"] = pd.Categorical(daily["variant"], categories=VARIANT_ORDER, ordered=True)
    return daily.sort_values(["variant", "date"]).reset_index(drop=True)


def _summary_table(
    fact: pd.DataFrame,
    daily: pd.DataFrame,
    baseline: pd.DataFrame,
    attribution_summary: dict[str, Any],
    config: Task007Config,
) -> pd.DataFrame:
    rows = []
    baseline_net = float(attribution_summary.get("net_alpha_total", 0.0))
    baseline_max_dd = _max_drawdown(
        daily[daily["variant"].astype(str).eq("baseline_current_long_short")]["portfolio_return_net"]
    )
    for variant in VARIANT_ORDER:
        variant_daily = daily[daily["variant"].astype(str).eq(variant)].copy()
        variant_fact = fact[fact["variant"].eq(variant)].copy()
        net_returns = variant_daily["portfolio_return_net"].astype(float)
        gross_returns = variant_daily["portfolio_return_gross"].astype(float)
        net_alpha = float(net_returns.sum())
        gross_alpha = float(gross_returns.sum())
        by_symbol = _symbol_contributions(variant_fact)
        concentration = _concentration_metrics(by_symbol, net_alpha)
        long_net = float(variant_fact.loc[variant_fact["variant_side"].eq("long"), "variant_net_contribution"].sum())
        short_net = float(variant_fact.loc[variant_fact["variant_side"].eq("short"), "variant_net_contribution"].sum())
        max_dd = _max_drawdown(net_returns)
        rows.append({
            "variant": variant,
            "active_days": int(len(variant_daily)),
            "sharpe_active": _annual_ratio(net_returns, config.annualization_factor),
            "ir_vs_cash_active": _annual_ratio(
                net_returns - variant_daily["benchmark_cash_return"].astype(float).fillna(0.0),
                config.annualization_factor,
            ),
            "ir_vs_equal_weight_active": _annual_ratio(
                net_returns - variant_daily["benchmark_eqw_return"].astype(float).fillna(0.0),
                config.annualization_factor,
            ),
            "ir_vs_btc_active": _annual_ratio(
                net_returns - variant_daily["benchmark_btc_return"].astype(float),
                config.annualization_factor,
            ),
            "max_dd": max_dd,
            "max_dd_vs_baseline_multiple": _safe_div(abs(max_dd), abs(baseline_max_dd)),
            "gross_alpha": gross_alpha,
            "net_alpha": net_alpha,
            "net_alpha_delta_vs_baseline": net_alpha - baseline_net,
            "alpha_decay_vs_baseline": baseline_net - net_alpha,
            "alpha_retention_pct": _safe_div(net_alpha, baseline_net),
            "long_net_contribution": long_net,
            "short_net_contribution": short_net,
            "top5_concentration_net_alpha_total": concentration["top5_concentration"],
            "single_symbol_concentration_net_alpha_total": concentration["single_symbol_concentration"],
            "top_symbol": concentration["top_symbol"],
            "fee_cost": float(variant_fact["variant_fee_cost"].sum()),
            "slippage_cost": float(variant_fact["variant_slippage_cost"].sum()),
            "funding_cost": float(variant_fact["variant_funding_cost"].sum()),
            "gross_exposure_mean": float(variant_daily["gross_exposure"].mean()),
            "net_exposure_mean": float(variant_daily["net_exposure"].mean()),
            "turnover_proxy_sum": float(variant_daily["trade_turnover_proxy"].sum()),
        })
    return pd.DataFrame(rows)


def _symbol_contributions(fact: pd.DataFrame) -> pd.DataFrame:
    grouped = fact.groupby("symbol", as_index=False).agg(
        gross_alpha_contribution=("variant_gross_contribution", "sum"),
        net_alpha_contribution=("variant_net_contribution", "sum"),
        fee_cost_total=("variant_fee_cost", "sum"),
        slippage_cost_total=("variant_slippage_cost", "sum"),
        funding_cost_total=("variant_funding_cost", "sum"),
        holding_days=("variant_weight", lambda x: int((x != 0).sum())),
        long_days=("variant_weight", lambda x: int((x > 0).sum())),
        short_days=("variant_weight", lambda x: int((x < 0).sum())),
    )
    grouped["total_cost"] = grouped["fee_cost_total"] + grouped["slippage_cost_total"] + grouped["funding_cost_total"]
    return grouped.sort_values("net_alpha_contribution", ascending=False).reset_index(drop=True)


def _concentration_table(fact: pd.DataFrame, top5_symbols: list[str]) -> pd.DataFrame:
    frames = []
    for variant, group in fact.groupby("variant", sort=False):
        by_symbol = _symbol_contributions(group)
        net_alpha = float(group["variant_net_contribution"].sum())
        by_symbol["variant"] = variant
        by_symbol["is_baseline_top5_positive_symbol"] = by_symbol["symbol"].isin(set(top5_symbols))
        by_symbol["pct_of_variant_net_alpha"] = by_symbol["net_alpha_contribution"].map(
            lambda value: _safe_div(float(value), net_alpha)
        )
        by_symbol["abs_pct_of_variant_net_alpha"] = by_symbol["pct_of_variant_net_alpha"].abs()
        frames.append(by_symbol)
    columns = [
        "variant",
        "symbol",
        "gross_alpha_contribution",
        "net_alpha_contribution",
        "pct_of_variant_net_alpha",
        "abs_pct_of_variant_net_alpha",
        "fee_cost_total",
        "slippage_cost_total",
        "funding_cost_total",
        "total_cost",
        "holding_days",
        "long_days",
        "short_days",
        "is_baseline_top5_positive_symbol",
    ]
    return pd.concat(frames, ignore_index=True).loc[:, columns]


def _cost_breakdown_table(fact: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variant, group in fact.groupby("variant", sort=False):
        totals = {
            "fee": float(group["variant_fee_cost"].sum()),
            "slippage": float(group["variant_slippage_cost"].sum()),
            "funding": float(group["variant_funding_cost"].sum()),
        }
        total_cost = sum(totals.values())
        gross_alpha = float(group["variant_gross_contribution"].sum())
        for cost_type, value in totals.items():
            rows.append({
                "variant": variant,
                "cost_type": cost_type,
                "total_cost": value,
                "pct_of_total_cost": _safe_div(value, total_cost),
                "pct_of_gross_alpha": _safe_div(value, gross_alpha),
            })
    return pd.DataFrame(rows)


def _summary_json(
    summary: pd.DataFrame,
    concentration: pd.DataFrame,
    cost_breakdown: pd.DataFrame,
    daily: pd.DataFrame,
    top5_symbols: list[str],
    attribution_summary: dict[str, Any],
    config: Task007Config,
) -> dict[str, Any]:
    return {
        "run_date": config.output_date,
        "analysis_basis": "TASK-007 post-processing overlay study, not a trading decision",
        "baseline_run_id": config.baseline_run_id,
        "cost_stress_run_id": config.cost_stress_run_id,
        "attribution_run_id": config.attribution_run_id,
        "primary_scenario": config.primary_scenario,
        "variants": VARIANT_ORDER,
        "baseline_top5_positive_symbols": top5_symbols,
        "methodology": {
            "return_dating": "positions.date + 1 day = return_date",
            "cost_source": "official TASK-002 realistic_combo symbol-day costs",
            "cost_scaling": "cost_scale = abs(variant_weight / original_weight); all costs zero when variant_weight is zero",
            "funding_cost_policy": "primary outputs do not recalculate funding from raw funding rates",
            "cap_policy": "primary cap variants use cap_no_redistribution; excess weight is removed",
            "annualization_factor": config.annualization_factor,
            "std_ddof": 1,
            "high_funding_threshold_8h": config.high_funding_threshold_8h,
            "high_funding_window_days": config.high_funding_window_days,
        },
        "baseline_reference_from_task003": {
            "gross_alpha_total": attribution_summary.get("gross_alpha_total"),
            "net_alpha_total": attribution_summary.get("net_alpha_total"),
            "total_cost_drag": attribution_summary.get("total_cost_drag"),
            "reproducibility_hash": attribution_summary.get("reproducibility_hash"),
        },
        "summary": summary.to_dict(orient="records"),
        "input_hashes": build_input_hashes(config.input_paths()),
        "git_commit": git_commit(),
    }


def _apply_gates(
    summary_json: dict[str, Any],
    daily: pd.DataFrame,
    cost_stress: pd.DataFrame,
    config: Task007Config,
) -> None:
    real = cost_stress[cost_stress["scenario"].eq(config.primary_scenario)].copy()
    _normalize_date(real, "date")
    base = daily[daily["variant"].astype(str).eq("baseline_current_long_short")].copy()
    base["date"] = pd.to_datetime(base["date"]).dt.normalize()
    comp = base.merge(
        real.loc[:, ["date", "portfolio_return_net"]],
        on="date",
        how="left",
        suffixes=("", "_task002"),
    )
    baseline_max_diff = float((comp["portfolio_return_net"] - comp["portfolio_return_net_task002"]).abs().max())
    by_variant = {str(row["variant"]): row for row in summary_json["summary"]}
    baseline_net = float(by_variant["baseline_current_long_short"]["net_alpha"])
    short_dd_multiple = float(by_variant["short_only_rescaled"]["max_dd_vs_baseline_multiple"])
    long_only_net = float(by_variant["long_only_rescaled"]["net_alpha"])
    combined = by_variant["combined_paper_safe_variant"]
    top5_max = max(float(row["top5_concentration_net_alpha_total"]) for row in summary_json["summary"])
    single_max = max(float(row["single_symbol_concentration_net_alpha_total"]) for row in summary_json["summary"])
    cap_variants = ["top5_symbol_cap_5pct", "DOT_capped", "no_DOT", "combined_paper_safe_variant"]
    cap_losses = {
        name: _safe_div(baseline_net - float(by_variant[name]["net_alpha"]), abs(baseline_net))
        for name in cap_variants
    }
    max_cap_loss = max(cap_losses.values()) if cap_losses else 0.0
    summary_json["fail_gates"] = {
        "baseline_mismatch": {
            "triggered": bool(baseline_max_diff > config.tolerance),
            "value": baseline_max_diff,
            "threshold": config.tolerance,
        },
        "missing_outputs": {"triggered": False, "missing": []},
        "schema_mismatch": {"triggered": False, "errors": []},
    }
    summary_json["warning_gates"] = {
        "short_only_rescaled_max_dd_worse_than_baseline_1p5x": {
            "triggered": bool(short_dd_multiple > config.warning_thresholds["short_only_rescaled_dd_multiple"]),
            "value": short_dd_multiple,
            "threshold": config.warning_thresholds["short_only_rescaled_dd_multiple"],
        },
        "long_only_rescaled_net_alpha_negative": {
            "triggered": bool(long_only_net < 0.0),
            "value": long_only_net,
            "threshold": 0.0,
        },
        "combined_paper_safe_variant_sharpe_below_0p5": {
            "triggered": bool(float(combined["sharpe_active"]) < config.warning_thresholds["combined_sharpe_min"]),
            "value": float(combined["sharpe_active"]),
            "threshold": config.warning_thresholds["combined_sharpe_min"],
        },
        "combined_paper_safe_variant_ir_eqw_below_0p2": {
            "triggered": bool(float(combined["ir_vs_equal_weight_active"]) < config.warning_thresholds["combined_ir_eqw_min"]),
            "value": float(combined["ir_vs_equal_weight_active"]),
            "threshold": config.warning_thresholds["combined_ir_eqw_min"],
        },
        "top5_concentration_remains_above_60pct": {
            "triggered": bool(top5_max > config.warning_thresholds["top5_concentration_max"]),
            "value": top5_max,
            "threshold": config.warning_thresholds["top5_concentration_max"],
        },
        "single_symbol_concentration_remains_above_25pct": {
            "triggered": bool(single_max > config.warning_thresholds["single_symbol_concentration_max"]),
            "value": single_max,
            "threshold": config.warning_thresholds["single_symbol_concentration_max"],
        },
        "cap_variants_destroy_more_than_50pct_net_alpha": {
            "triggered": bool(max_cap_loss > config.warning_thresholds["cap_alpha_loss_max"]),
            "value": max_cap_loss,
            "threshold": config.warning_thresholds["cap_alpha_loss_max"],
            "cap_variant_losses": cap_losses,
        },
    }


def _concentration_metrics(by_symbol: pd.DataFrame, net_alpha: float) -> dict[str, Any]:
    positive = by_symbol[by_symbol["net_alpha_contribution"].gt(0)].copy()
    top5 = float(positive.sort_values("net_alpha_contribution", ascending=False).head(5)["net_alpha_contribution"].sum())
    top1 = positive.sort_values("net_alpha_contribution", ascending=False).head(1)
    top_symbol = str(top1["symbol"].iloc[0]) if not top1.empty else ""
    top_value = float(top1["net_alpha_contribution"].iloc[0]) if not top1.empty else 0.0
    return {
        "top5_concentration": _safe_div(top5, net_alpha),
        "single_symbol_concentration": _safe_div(top_value, net_alpha),
        "top_symbol": top_symbol,
    }


def _review_packet(summary_json: dict[str, Any], summary: pd.DataFrame, concentration: pd.DataFrame, config: Task007Config) -> str:
    rows = []
    for _, row in summary.iterrows():
        rows.append(
            f"| {row['variant']} | {row['sharpe_active']:.4f} | {row['ir_vs_equal_weight_active']:.4f} | "
            f"{row['max_dd']:.2%} | {row['net_alpha']:.2%} | {row['alpha_retention_pct']:.2%} | "
            f"{row['top5_concentration_net_alpha_total']:.2%} | {row['single_symbol_concentration_net_alpha_total']:.2%} |"
        )
    warnings = [
        name for name, gate in summary_json["warning_gates"].items()
        if gate.get("triggered")
    ]
    failures = [
        name for name, gate in summary_json["fail_gates"].items()
        if gate.get("triggered")
    ]
    best = summary.sort_values("sharpe_active", ascending=False).head(1)
    best_name = str(best["variant"].iloc[0]) if not best.empty else ""
    best_sharpe = float(best["sharpe_active"].iloc[0]) if not best.empty else 0.0
    top_symbols = (
        concentration[concentration["variant"].eq("baseline_current_long_short")]
        .sort_values("net_alpha_contribution", ascending=False)
        .head(10)
    )
    top_lines = [
        f"- {row.symbol}: net_alpha={row.net_alpha_contribution:.2%}, pct_of_variant_net_alpha={row.pct_of_variant_net_alpha:.2%}"
        for row in top_symbols.itertuples(index=False)
    ]
    return "\n".join([
        "# REVIEW-007 Packet - TASK-007 Long-side Variant Study",
        "",
        "Analysis basis: TASK-007 post-processing overlay study, not a trading decision.",
        "No paper trading or live trading approval is implied by this packet.",
        "",
        "## Methodology",
        "- Inputs are official run008, TASK-002 realistic_combo, TASK-003 attribution, prices_daily, and funding_rates files.",
        "- Return dating: positions.date + 1 day = return_date.",
        "- Costs are official TASK-002 realistic_combo symbol-day costs scaled by abs(variant_weight / original_weight).",
        "- Primary funding costs are not recalculated from raw funding rates.",
        "- Primary cap variants use cap_no_redistribution; excess weight is removed.",
        "",
        "## Key Results",
        "| Variant | Sharpe | IR vs EQW | Max DD | Net Alpha | Alpha Retention | Top5 Conc | Single Conc |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        *rows,
        "",
        "## Review Focus",
        f"- Best Sharpe variant: `{best_name}` ({best_sharpe:.4f}).",
        f"- Warning gates triggered: {warnings if warnings else 'none'}.",
        f"- Fail gates triggered: {failures if failures else 'none'}.",
        "- Treat the combined paper-safe variant as a quantitative input only; final paper/live decisions require review and Rick approval.",
        "",
        "## Baseline Top Contributors",
        *top_lines,
        "",
        "## Reproducibility",
        f"- reproducibility_hash: `{summary_json['reproducibility_hash']}`",
        f"- git_commit: `{summary_json['git_commit']}`",
        f"- output_date: `{config.output_date}`",
        "",
    ]) + "\n"


def _review_numbers_payload(summary_json: dict[str, Any], summary: pd.DataFrame) -> dict[str, Any]:
    key_cols = [
        "variant",
        "sharpe_active",
        "ir_vs_cash_active",
        "ir_vs_equal_weight_active",
        "ir_vs_btc_active",
        "max_dd",
        "net_alpha",
        "gross_alpha",
        "long_net_contribution",
        "short_net_contribution",
        "top5_concentration_net_alpha_total",
        "single_symbol_concentration_net_alpha_total",
    ]
    return {
        "analysis_basis": summary_json["analysis_basis"],
        "run_date": summary_json["run_date"],
        "key_numbers": summary.loc[:, key_cols].to_dict(orient="records"),
        "warning_gates": summary_json["warning_gates"],
        "fail_gates": summary_json["fail_gates"],
        "reproducibility_hash": summary_json["reproducibility_hash"],
        "git_commit": summary_json["git_commit"],
    }


def _log_text(summary_json: dict[str, Any], config: Task007Config) -> str:
    return "\n".join([
        "TASK-007 Long-side Variant Study",
        f"run_date={config.output_date}",
        "analysis_basis=post-processing overlay study, not a trading decision",
        f"baseline_run_id={config.baseline_run_id}",
        f"cost_stress_run_id={config.cost_stress_run_id}",
        f"primary_scenario={config.primary_scenario}",
        f"git_commit={summary_json['git_commit']}",
        f"reproducibility_hash={summary_json['reproducibility_hash']}",
        "",
        "methodology:",
        json.dumps(summary_json["methodology"], indent=2, sort_keys=True, ensure_ascii=True),
        "",
        "fail_gates:",
        json.dumps(summary_json["fail_gates"], indent=2, sort_keys=True, ensure_ascii=True),
        "",
        "warning_gates:",
        json.dumps(summary_json["warning_gates"], indent=2, sort_keys=True, ensure_ascii=True),
        "",
        "input_hashes:",
        json.dumps(summary_json["input_hashes"], indent=2, sort_keys=True, ensure_ascii=True),
        "",
    ]) + "\n"


def _validate_outputs(paths: dict[str, Path], result: Task007Result) -> list[str]:
    errors = []
    for name, path in paths.items():
        if not path.exists():
            errors.append(f"missing output {name}: {path}")
    required_daily = {
        "variant",
        "date",
        "portfolio_return_gross",
        "portfolio_return_net",
        "fee_cost",
        "slippage_cost",
        "funding_cost",
        "gross_exposure",
        "net_exposure",
    }
    missing_daily = required_daily - set(result.daily.columns)
    if missing_daily:
        errors.append(f"daily missing columns: {sorted(missing_daily)}")
    required_summary = {"variant", "sharpe_active", "ir_vs_equal_weight_active", "max_dd", "net_alpha"}
    missing_summary = required_summary - set(result.summary.columns)
    if missing_summary:
        errors.append(f"summary missing columns: {sorted(missing_summary)}")
    if result.daily.empty:
        errors.append("daily output is empty")
    if result.summary.empty:
        errors.append("summary output is empty")
    return errors


def _frame_hash(frame: pd.DataFrame) -> str:
    payload = frame.copy()
    for col in payload.columns:
        if pd.api.types.is_datetime64_any_dtype(payload[col]):
            payload[col] = pd.to_datetime(payload[col]).dt.strftime("%Y-%m-%d")
    return canonical_hash(payload.to_dict(orient="records"))


def _annual_ratio(series: pd.Series, annualization: float) -> float:
    clean = pd.Series(series, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return 0.0
    std = float(clean.std(ddof=1))
    if std == 0.0 or math.isnan(std):
        return 0.0
    return float(clean.mean() / std * math.sqrt(annualization))


def _max_drawdown(returns: pd.Series) -> float:
    clean = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if clean.empty:
        return 0.0
    equity = (1.0 + clean).cumprod()
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def _safe_div(num: float, den: float) -> float:
    if den == 0.0 or math.isnan(float(den)):
        return 0.0
    return float(num / den)


def _normalize_date(frame: pd.DataFrame, col: str) -> None:
    frame[col] = pd.to_datetime(frame[col]).dt.normalize()
