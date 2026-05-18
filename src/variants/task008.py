from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from src.attribution.costs import load_primary_costs
from src.attribution.returns import build_gross_contributions, load_tradable_membership
from src.signals.prev3y_momentum import TargetPortfolio, build_prev3y_targets
from src.variants.task007 import (
    _annual_ratio,
    _apply_variant_costs,
    _build_base_fact,
    _frame_hash,
    _max_drawdown,
    _safe_div,
)


def _normalize_date(value: Any) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    return pd.Timestamp(value).normalize()


@dataclass(frozen=True)
class Task008Config:
    output_date: str = "20260517"
    strategy_config: Path = Path("configs/prev3y_crypto.yaml")
    baseline_path: Path = Path("outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv")
    positions_path: Path = Path("outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet")
    positions_cost_path: Path = Path("outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet")
    attribution_summary_path: Path = Path("outputs/attribution/prev3y_crypto/20260515_attribution_summary.json")
    task007_summary_path: Path = Path("outputs/variants/prev3y_crypto/20260515_task007_variant_summary.json")
    prices_path: Path = Path("data/crypto/prices_daily.parquet")
    universe_path: Path = Path("data/crypto/universe_membership.parquet")
    output_dir: Path = Path("outputs/variants/prev3y_crypto")
    log_dir: Path = Path("outputs/logs/prev3y_crypto")
    review_packet_path: Path = Path("docs/research/review_packets/REVIEW-008_PACKET.md")
    review_numbers_path: Path = Path("docs/research/review_packets/REVIEW-008_NUMBERS.json")
    baseline_tolerance: float = 1e-6
    warning_top5_concentration: float = 0.75
    warning_min_sharpe: float = 0.70
    warning_min_alpha_retention: float = 0.85
    warning_max_turnover_change: float = 1.50
    warning_min_long_net: float = -0.10
    warning_max_cost_impact_bps: float = 30.0
    annualization_factor: float = 365.25


@dataclass(frozen=True)
class VariantSpec:
    name: str
    family: str
    rolling_periods: int = 12
    max_alpha_share: float = 0.20
    action: str = "exclude"
    floor_abs_weight: str = "zero"
    cooldown_trigger: int = 6
    cooldown_periods: int = 3
    side_independent: bool = True


@dataclass(frozen=True)
class Task008Result:
    status: str
    comparison_csv: Path
    comparison_json: Path
    detail_csv: Path
    attribution_json: Path
    log_path: Path
    review_packet_path: Path
    review_numbers_path: Path
    fail_gates: list[dict[str, Any]]
    warning_gates: list[dict[str, Any]]


VARIANT_SPECS: tuple[VariantSpec, ...] = (
    VariantSpec("A_roll12_share20_exclude", "rolling_cap", 12, 0.20, "exclude"),
    VariantSpec("A_roll12_share25_exclude", "rolling_cap", 12, 0.25, "exclude"),
    VariantSpec("A_roll12_share20_penalize50", "rolling_cap", 12, 0.20, "penalize50"),
    VariantSpec("A_roll24_share20_exclude", "rolling_cap", 24, 0.20, "exclude"),
    VariantSpec("B_roll12_share20_floor0", "alpha_share_sizing", 12, 0.20, floor_abs_weight="zero"),
    VariantSpec("B_roll12_share25_floor_halfslot", "alpha_share_sizing", 12, 0.25, floor_abs_weight="halfslot"),
    VariantSpec("B_roll24_share20_floor0", "alpha_share_sizing", 24, 0.20, floor_abs_weight="zero"),
    VariantSpec("C_k6_cd3_side", "cooldown", cooldown_trigger=6, cooldown_periods=3, side_independent=True),
    VariantSpec("C_k6_cd2_side", "cooldown", cooldown_trigger=6, cooldown_periods=2, side_independent=True),
    VariantSpec("C_k12_cd3_side", "cooldown", cooldown_trigger=12, cooldown_periods=3, side_independent=True),
    VariantSpec("C_k3_cd2_shared", "cooldown", cooldown_trigger=3, cooldown_periods=2, side_independent=False),
)


def load_strategy_config(path: Path) -> dict[str, Any]:
    try:
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ModuleNotFoundError:
        data: dict[str, Any] = {}
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            data[key.strip()] = _parse_scalar(value.strip())
        return data


def _parse_scalar(value: str) -> Any:
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value.strip("'\"")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _side_counts(eligible_count: int, top_n: int, bottom_n: int) -> tuple[int, int]:
    max_side = max(eligible_count // 2, 0)
    return min(top_n, max_side), min(bottom_n, max_side)


def target_candidates(target: TargetPortfolio, top_n: int, bottom_n: int) -> dict[str, Any]:
    ranks = pd.Series(target.signal_ranks, dtype=float).dropna()
    values = pd.Series(target.signal_values, dtype=float).reindex(ranks.index)
    long_count, short_count = _side_counts(len(ranks), top_n, bottom_n)
    ordered_long = ranks.sort_values(kind="mergesort").index.tolist()
    ordered_short = ranks.sort_values(ascending=False, kind="mergesort").index.tolist()
    return {
        "date": pd.Timestamp(target.effective_date).normalize(),
        "long_count": long_count,
        "short_count": short_count,
        "long": ordered_long,
        "short": ordered_short,
        "ranks": ranks.to_dict(),
        "values": values.to_dict(),
        "base_longs": ordered_long[:long_count],
        "base_shorts": ordered_short[:short_count],
    }


def _ranked_select(
    candidates: list[str],
    count: int,
    blocked: set[str] | None = None,
    penalized: set[str] | None = None,
) -> list[str]:
    blocked = blocked or set()
    penalized = penalized or set()
    ordered = [symbol for symbol in candidates if symbol not in blocked]
    ordered.sort(key=lambda symbol: (symbol in penalized, candidates.index(symbol)))
    return ordered[:count]


def _equal_side_weights(longs: Iterable[str], shorts: Iterable[str]) -> dict[str, float]:
    long_list = list(longs)
    short_list = list(shorts)
    weights: dict[str, float] = {}
    if long_list:
        long_weight = 0.5 / len(long_list)
        weights.update({symbol: long_weight for symbol in long_list})
    if short_list:
        short_weight = -0.5 / len(short_list)
        weights.update({symbol: short_weight for symbol in short_list})
    return weights


def _alpha_share_lookup(period_alpha: pd.DataFrame, rolling_periods: int) -> dict[tuple[pd.Timestamp, str], float]:
    if period_alpha.empty:
        return {}
    pivot = period_alpha.pivot_table(
        index="period_date",
        columns="symbol",
        values="net_alpha",
        aggfunc="sum",
        fill_value=0.0,
    ).sort_index()
    abs_total = pivot.abs().sum(axis=1)
    rolling_symbol = pivot.abs().shift(1).rolling(rolling_periods, min_periods=1).sum()
    rolling_total = abs_total.shift(1).rolling(rolling_periods, min_periods=1).sum()
    shares = rolling_symbol.div(rolling_total.replace(0.0, np.nan), axis=0).fillna(0.0)
    lookup: dict[tuple[pd.Timestamp, str], float] = {}
    for date, row in shares.iterrows():
        for symbol, value in row.items():
            if value:
                lookup[(pd.Timestamp(date).normalize(), str(symbol))] = float(value)
    return lookup


def build_period_alpha(baseline_fact: pd.DataFrame, target_dates: list[pd.Timestamp]) -> pd.DataFrame:
    if not target_dates:
        return pd.DataFrame(columns=["period_date", "symbol", "net_alpha"])
    dates = pd.Series(sorted(pd.Timestamp(date).normalize() for date in target_dates))
    fact = baseline_fact.copy()
    fact["active_date"] = fact["date"].map(_normalize_date)
    period_idx = np.searchsorted(dates.to_numpy(), fact["active_date"].to_numpy(), side="right") - 1
    fact = fact.loc[period_idx >= 0].copy()
    fact["period_date"] = dates.iloc[period_idx[period_idx >= 0]].to_numpy()
    return (
        fact.groupby(["period_date", "symbol"], as_index=False)["variant_net_contribution"]
        .sum()
        .rename(columns={"variant_net_contribution": "net_alpha"})
    )


def _build_rolling_cap_weights(
    candidate: dict[str, Any],
    alpha_share: dict[tuple[pd.Timestamp, str], float],
    spec: VariantSpec,
) -> tuple[dict[str, float], dict[str, Any]]:
    date = candidate["date"]
    blocked = {
        symbol
        for symbol in set(candidate["long"] + candidate["short"])
        if alpha_share.get((date, symbol), 0.0) > spec.max_alpha_share
    }
    penalized = blocked if spec.action == "penalize50" else set()
    active_block = blocked if spec.action == "exclude" else set()
    longs = _ranked_select(candidate["long"], candidate["long_count"], active_block, penalized)
    shorts = _ranked_select(candidate["short"], candidate["short_count"], active_block, penalized)
    return _equal_side_weights(longs, shorts), {
        "blocked_count": len(blocked),
        "selected_count": len(longs) + len(shorts),
    }


def _build_alpha_sizing_weights(
    candidate: dict[str, Any],
    alpha_share: dict[tuple[pd.Timestamp, str], float],
    spec: VariantSpec,
) -> tuple[dict[str, float], dict[str, Any]]:
    date = candidate["date"]
    base = _equal_side_weights(candidate["base_longs"], candidate["base_shorts"])
    adjusted: dict[str, float] = {}
    reductions = 0
    for symbol, weight in base.items():
        share = max(0.0, alpha_share.get((date, symbol), 0.0))
        factor = max(0.0, 1.0 - min(share, spec.max_alpha_share))
        value = weight * factor
        if factor < 1.0:
            reductions += 1
        if spec.floor_abs_weight == "halfslot":
            side_count = candidate["long_count"] if weight > 0 else candidate["short_count"]
            floor = 0.5 / max(side_count, 1) * 0.5
            value = np.sign(weight) * max(abs(value), floor)
        adjusted[symbol] = float(value)
    return _renormalize_sides(adjusted), {"reduced_count": reductions}


def _renormalize_sides(weights: dict[str, float]) -> dict[str, float]:
    result = dict(weights)
    long_sum = sum(weight for weight in result.values() if weight > 0)
    short_sum = sum(abs(weight) for weight in result.values() if weight < 0)
    if long_sum > 0:
        for symbol, weight in list(result.items()):
            if weight > 0:
                result[symbol] = float(weight * 0.5 / long_sum)
    if short_sum > 0:
        for symbol, weight in list(result.items()):
            if weight < 0:
                result[symbol] = float(weight * 0.5 / short_sum)
    return {symbol: weight for symbol, weight in result.items() if abs(weight) > 1e-15}


def _cooldown_key(symbol: str, side: str, side_independent: bool) -> tuple[str, str]:
    return (side, symbol) if side_independent else ("any", symbol)


def build_monthly_variant_weights(
    candidates: list[dict[str, Any]],
    alpha_share: dict[tuple[pd.Timestamp, str], float],
    spec: VariantSpec,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    detail: dict[str, Any] = {"cooldown_fallback_events": 0, "cooldown_filtered_symbols": 0}
    cooldowns: dict[tuple[str, str], int] = {}
    streaks: dict[tuple[str, str], int] = {}

    for candidate in candidates:
        if spec.family == "rolling_cap":
            weights, info = _build_rolling_cap_weights(candidate, alpha_share, spec)
        elif spec.family == "alpha_share_sizing":
            weights, info = _build_alpha_sizing_weights(candidate, alpha_share, spec)
        elif spec.family == "cooldown":
            old_cooldowns = dict(cooldowns)
            blocked_long = {
                symbol
                for symbol in candidate["long"]
                if old_cooldowns.get(_cooldown_key(symbol, "long", spec.side_independent), 0) > 0
            }
            blocked_short = {
                symbol
                for symbol in candidate["short"]
                if old_cooldowns.get(_cooldown_key(symbol, "short", spec.side_independent), 0) > 0
            }
            longs = _ranked_select(candidate["long"], candidate["long_count"], blocked_long)
            shorts = _ranked_select(candidate["short"], candidate["short_count"], blocked_short)
            if len(longs) < candidate["long_count"]:
                detail["cooldown_fallback_events"] += 1
                longs = _ranked_select(candidate["long"], candidate["long_count"])
            if len(shorts) < candidate["short_count"]:
                detail["cooldown_fallback_events"] += 1
                shorts = _ranked_select(candidate["short"], candidate["short_count"])
            detail["cooldown_filtered_symbols"] += len(blocked_long) + len(blocked_short)
            weights = _equal_side_weights(longs, shorts)
            info = {
                "blocked_long": len(blocked_long),
                "blocked_short": len(blocked_short),
            }

            next_cooldowns = {
                key: value - 1 for key, value in cooldowns.items() if value - 1 > 0
            }
            for side, symbols in (("long", candidate["base_longs"]), ("short", candidate["base_shorts"])):
                active_keys = {_cooldown_key(symbol, side, spec.side_independent) for symbol in symbols}
                for key in list(streaks):
                    if key[0] == (side if spec.side_independent else "any") and key not in active_keys:
                        streaks[key] = 0
                for symbol in symbols:
                    key = _cooldown_key(symbol, side, spec.side_independent)
                    streaks[key] = streaks.get(key, 0) + 1
                    if streaks[key] >= spec.cooldown_trigger:
                        next_cooldowns[key] = spec.cooldown_periods
                        streaks[key] = 0
            cooldowns = next_cooldowns
        else:
            raise ValueError(f"Unknown variant family: {spec.family}")

        for symbol, weight in weights.items():
            rows.append(
                {
                    "target_date": candidate["date"],
                    "symbol": symbol,
                    "target_weight": weight,
                    "variant": spec.name,
                    **info,
                }
            )

    return pd.DataFrame(rows), detail


def monthly_to_daily_weights(monthly_weights: pd.DataFrame, active_dates: list[pd.Timestamp]) -> pd.DataFrame:
    if monthly_weights.empty:
        return pd.DataFrame(columns=["date", "symbol", "target_weight", "variant"])
    monthly = monthly_weights.copy()
    monthly["target_date"] = monthly["target_date"].map(_normalize_date)
    target_dates = sorted(monthly["target_date"].unique())
    rows: list[pd.DataFrame] = []
    for active_date in sorted(pd.Timestamp(date).normalize() for date in active_dates):
        idx = np.searchsorted(np.array(target_dates, dtype="datetime64[ns]"), np.datetime64(active_date), side="right") - 1
        if idx < 0:
            continue
        target_date = target_dates[idx]
        frame = monthly.loc[monthly["target_date"] == target_date, ["symbol", "target_weight", "variant"]].copy()
        frame.insert(0, "date", active_date)
        rows.append(frame)
    if not rows:
        return pd.DataFrame(columns=["date", "symbol", "target_weight", "variant"])
    return pd.concat(rows, ignore_index=True)


def weights_from_daily_targets(fact: pd.DataFrame, daily_targets: pd.DataFrame, date_col: str) -> pd.Series:
    if daily_targets.empty:
        return pd.Series(0.0, index=fact.index)
    lookup = daily_targets.rename(columns={"date": "_merge_date", "target_weight": "_target_weight"}).copy()
    lookup["_merge_date"] = lookup["_merge_date"].map(_normalize_date)
    base = fact[["symbol", date_col]].copy()
    base["_merge_date"] = base[date_col].map(_normalize_date)
    merged = base.merge(lookup[["_merge_date", "symbol", "_target_weight"]], on=["_merge_date", "symbol"], how="left")
    return merged["_target_weight"].fillna(0.0).astype(float)


def evaluate_variant(fact: pd.DataFrame, daily_targets: pd.DataFrame, variant_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    variant_fact = fact.copy()
    variant_fact["variant"] = variant_name
    variant_fact["variant_return_weight"] = weights_from_daily_targets(variant_fact, daily_targets, "position_date")
    variant_fact["variant_cost_weight"] = weights_from_daily_targets(variant_fact, daily_targets, "date")
    variant_fact["variant_weight"] = np.where(
        variant_fact["variant_cost_weight"].abs() > 0.0,
        variant_fact["variant_cost_weight"],
        variant_fact["variant_return_weight"],
    )
    variant_fact = _apply_variant_costs(variant_fact)
    daily = build_daily_metrics(variant_fact, variant_name)
    return daily, variant_fact


def evaluate_baseline(fact: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline_fact = fact.copy()
    baseline_fact["variant"] = "baseline_current_long_short"
    baseline_fact["variant_return_weight"] = baseline_fact["return_base_weight"]
    baseline_fact["variant_cost_weight"] = baseline_fact["cost_base_weight"]
    baseline_fact["variant_weight"] = baseline_fact["original_weight"]
    baseline_fact = _apply_variant_costs(baseline_fact)
    return build_daily_metrics(baseline_fact, "baseline_current_long_short"), baseline_fact


def build_daily_metrics(fact: pd.DataFrame, variant_name: str) -> pd.DataFrame:
    daily = (
        fact.groupby("date", as_index=False)
        .agg(
            variant_gross_contribution=("variant_gross_contribution", "sum"),
            variant_fee_cost=("variant_fee_cost", "sum"),
            variant_slippage_cost=("variant_slippage_cost", "sum"),
            variant_funding_cost=("variant_funding_cost", "sum"),
            variant_outlier_funding_cost=("variant_outlier_funding_cost", "sum"),
            variant_net_contribution=("variant_net_contribution", "sum"),
            variant_turnover=("variant_trade_turnover", "sum"),
            benchmark_cash_return=("benchmark_cash_return", "first"),
            benchmark_btc_return=("benchmark_btc_return", "first"),
            benchmark_eqw_return=("benchmark_eqw_return", "first"),
        )
        .sort_values("date")
    )
    daily.insert(0, "variant", variant_name)
    return daily


def summarize_variant(
    daily: pd.DataFrame,
    fact: pd.DataFrame,
    baseline_net_alpha: float,
    baseline_turnover: float,
    annualization_factor: float = 365.25,
) -> dict[str, Any]:
    net = daily["variant_net_contribution"].fillna(0.0)
    eqw = daily["benchmark_eqw_return"].fillna(0.0)
    symbol_net = (
        fact.groupby("symbol", as_index=False)["variant_net_contribution"].sum().sort_values("variant_net_contribution", ascending=False)
    )
    top5 = symbol_net.loc[symbol_net["variant_net_contribution"] > 0, "variant_net_contribution"].head(5).sum()
    single = symbol_net.loc[symbol_net["variant_net_contribution"] > 0, "variant_net_contribution"].head(1).sum()
    gross = float(daily["variant_gross_contribution"].sum())
    fee = float(daily["variant_fee_cost"].sum())
    slippage = float(daily["variant_slippage_cost"].sum())
    funding = float(daily["variant_funding_cost"].sum())
    outlier = float(daily["variant_outlier_funding_cost"].sum())
    turnover = float(daily["variant_turnover"].sum())
    long_net = float(fact.loc[fact["variant_weight"] > 0, "variant_net_contribution"].sum())
    short_net = float(fact.loc[fact["variant_weight"] < 0, "variant_net_contribution"].sum())
    return {
        "sharpe_active": _annual_ratio(net, annualization_factor),
        "ir_vs_equal_weight_active": _annual_ratio(net - eqw, annualization_factor),
        "max_dd": _max_drawdown(net),
        "gross_alpha": gross,
        "net_alpha": float(net.sum()),
        "alpha_retention_pct": _safe_div(float(net.sum()), baseline_net_alpha),
        "top5_concentration": _safe_div(float(top5), float(net.sum())),
        "single_symbol_concentration": _safe_div(float(single), float(net.sum())),
        "long_net_contribution": long_net,
        "short_net_contribution": short_net,
        "fee_cost": fee,
        "slippage_cost": slippage,
        "funding_cost": funding,
        "outlier_funding_cost": outlier,
        "total_cost": fee + slippage + funding + outlier,
        "cost_impact_bps": np.nan,
        "turnover": turnover,
        "turnover_change_x": _safe_div(turnover, baseline_turnover),
    }


def _summary_rows(summary: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for variant, metrics in summary.items():
        row = {"variant": variant}
        row.update(metrics)
        rows.append(row)
    return pd.DataFrame(rows)


def _apply_cost_impacts(summary: dict[str, dict[str, Any]], baseline_cost: float) -> None:
    for metrics in summary.values():
        metrics["cost_impact_bps"] = (float(metrics["total_cost"]) - baseline_cost) * 10000.0


def _input_hashes(paths: Iterable[Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in paths:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        hashes[str(path)] = digest.hexdigest()
    return hashes


def _strategy_modified() -> bool:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--", "src/signals/prev3y_momentum.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _task007_reference(summary_path: Path) -> dict[str, Any]:
    data = _read_json(summary_path)
    return _variant_from_task007_summary(data, "combined_paper_safe_variant")


def _variant_from_task007_summary(data: dict[str, Any], variant_name: str) -> dict[str, Any]:
    summary = data.get("summary", [])
    if isinstance(summary, list):
        for row in summary:
            if isinstance(row, dict) and row.get("variant") == variant_name:
                return dict(row)
    variants = data.get("variants", {})
    if isinstance(variants, dict) and variant_name in variants:
        return dict(variants[variant_name])
    return {}


def _build_candidates(strategy: dict[str, Any], prices: pd.DataFrame, membership: pd.DataFrame) -> list[dict[str, Any]]:
    targets = build_prev3y_targets(
        prices=prices,
        membership=membership,
        start_date=strategy.get("start_date", "2019-01-01"),
        end_date=strategy.get("end_date", "2026-04-30"),
        lookback_days=int(strategy.get("lookback_days", 1095)),
        rebalance_freq=strategy.get("rebalance_freq", "monthly"),
        top_n=int(strategy.get("top_n", 25)),
        bottom_n=int(strategy.get("bottom_n", 25)),
        ranking_method=strategy.get("ranking_method", "return"),
    )
    return [
        target_candidates(target, int(strategy.get("top_n", 25)), int(strategy.get("bottom_n", 25)))
        for target in targets
    ]


def _filter_candidates(candidates: list[dict[str, Any]], active_dates: list[pd.Timestamp]) -> list[dict[str, Any]]:
    if not active_dates:
        return []
    min_date = min(active_dates)
    max_date = max(active_dates)
    return [candidate for candidate in candidates if min_date <= candidate["date"] <= max_date]


def _reference_summary_row(task007_summary: dict[str, Any], baseline_net_alpha: float, baseline_turnover: float, baseline_cost: float) -> dict[str, Any]:
    cost = (
        float(task007_summary.get("fee_cost", 0.0))
        + float(task007_summary.get("slippage_cost", 0.0))
        + float(task007_summary.get("funding_cost", 0.0))
        + float(task007_summary.get("outlier_funding_cost", 0.0))
    )
    return {
        "source": "task007_reference",
        "sharpe_active": task007_summary.get("sharpe_active"),
        "ir_vs_equal_weight_active": task007_summary.get("ir_vs_equal_weight_active"),
        "max_dd": task007_summary.get("max_dd"),
        "gross_alpha": task007_summary.get("gross_alpha"),
        "net_alpha": task007_summary.get("net_alpha"),
        "alpha_retention_pct": task007_summary.get("alpha_retention_pct", _safe_div(float(task007_summary.get("net_alpha", 0.0)), baseline_net_alpha)),
        "top5_concentration": task007_summary.get("top5_concentration_net_alpha_total"),
        "single_symbol_concentration": task007_summary.get("single_symbol_concentration_net_alpha_total"),
        "long_net_contribution": task007_summary.get("long_net_contribution"),
        "short_net_contribution": task007_summary.get("short_net_contribution"),
        "fee_cost": task007_summary.get("fee_cost"),
        "slippage_cost": task007_summary.get("slippage_cost"),
        "funding_cost": task007_summary.get("funding_cost"),
        "outlier_funding_cost": task007_summary.get("outlier_funding_cost", 0.0),
        "total_cost": cost,
        "cost_impact_bps": (cost - baseline_cost) * 10000.0,
        "turnover": task007_summary.get("turnover_proxy_sum", task007_summary.get("turnover")),
        "turnover_change_x": _safe_div(float(task007_summary.get("turnover_proxy_sum", task007_summary.get("turnover", 0.0))), baseline_turnover),
    }


def _gates(
    summary: dict[str, dict[str, Any]],
    baseline_mismatch: float,
    config: Task008Config,
    output_paths: list[Path],
    cooldown_details: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fails: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if baseline_mismatch > config.baseline_tolerance:
        fails.append({"gate": "baseline_mismatch", "value": baseline_mismatch, "limit": config.baseline_tolerance})
    if _strategy_modified():
        fails.append({"gate": "strategy_file_modified", "file": "src/signals/prev3y_momentum.py"})
    if any(not path.exists() for path in output_paths):
        fails.append({"gate": "missing_outputs", "missing": [str(path) for path in output_paths if not path.exists()]})
    if any(str(path).replace("\\", "/").endswith("task007b.py") for path in output_paths):
        fails.append({"gate": "weight_space_overlay_detected", "value": True})
    for variant, metrics in summary.items():
        if variant.startswith("task007_") or variant == "baseline_current_long_short":
            continue
        top5 = float(metrics.get("top5_concentration") or 0.0)
        single = float(metrics.get("single_symbol_concentration") or 0.0)
        if not np.isfinite(top5) or not np.isfinite(single) or top5 < -1e-12 or single < -1e-12:
            fails.append({"gate": "bad_concentration_math", "variant": variant, "top5": top5, "single": single})
        if top5 > config.warning_top5_concentration:
            warnings.append({"gate": "top5_concentration", "variant": variant, "value": top5, "limit": config.warning_top5_concentration})
        if float(metrics.get("sharpe_active") or 0.0) < config.warning_min_sharpe:
            warnings.append({"gate": "sharpe_active", "variant": variant, "value": metrics.get("sharpe_active"), "limit": config.warning_min_sharpe})
        if float(metrics.get("alpha_retention_pct") or 0.0) < config.warning_min_alpha_retention:
            warnings.append({"gate": "alpha_retention_pct", "variant": variant, "value": metrics.get("alpha_retention_pct"), "limit": config.warning_min_alpha_retention})
        if float(metrics.get("turnover_change_x") or 0.0) > config.warning_max_turnover_change:
            warnings.append({"gate": "turnover_change_x", "variant": variant, "value": metrics.get("turnover_change_x"), "limit": config.warning_max_turnover_change})
        if float(metrics.get("long_net_contribution") or 0.0) < config.warning_min_long_net:
            warnings.append({"gate": "long_net_contribution", "variant": variant, "value": metrics.get("long_net_contribution"), "limit": config.warning_min_long_net})
        if float(metrics.get("cost_impact_bps") or 0.0) > config.warning_max_cost_impact_bps:
            warnings.append({"gate": "cost_impact_bps", "variant": variant, "value": metrics.get("cost_impact_bps"), "limit": config.warning_max_cost_impact_bps})
        details = cooldown_details.get(variant, {})
        if details.get("cooldown_fallback_events", 0):
            warnings.append({"gate": "cooldown_fallback", "variant": variant, "value": details["cooldown_fallback_events"]})
    return fails, warnings


def _write_review_packet(path: Path, payload: dict[str, Any], comparison: pd.DataFrame) -> None:
    best = comparison.loc[comparison["variant"].str.startswith(("A_", "B_", "C_"))].sort_values(
        ["top5_concentration", "sharpe_active"], ascending=[True, False]
    ).head(1)
    best_name = best["variant"].iloc[0] if not best.empty else "n/a"
    lines = [
        "# REVIEW-008 Packet",
        "",
        f"- Status: {payload['status']}",
        f"- Output date: {payload['output_date']}",
        "- Paper execution: FORBIDDEN",
        "- Live trading: FORBIDDEN",
        f"- Baseline mismatch: {payload['baseline_mismatch']:.12g}",
        f"- Candidate variants: {len([name for name in payload['summary'] if name.startswith(('A_', 'B_', 'C_'))])}",
        f"- Lowest concentration candidate: {best_name}",
        f"- Fail gates: {len(payload['fail_gates'])}",
        f"- Warning gates: {len(payload['warning_gates'])}",
        "",
        "## Files",
        f"- comparison_csv: `{payload['outputs']['comparison_csv']}`",
        f"- comparison_json: `{payload['outputs']['comparison_json']}`",
        f"- detail_csv: `{payload['outputs']['detail_csv']}`",
        f"- attribution_json: `{payload['outputs']['attribution_json']}`",
        f"- log: `{payload['outputs']['log']}`",
        "",
        "## Notes",
        "- Alpha-space cap variants are implemented outside the main strategy.",
        "- `src/signals/prev3y_momentum.py` is read-only for this task.",
        "- TASK-007b weight-space redistribution is not used.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def run_task008(config: Task008Config) -> Task008Result:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.log_dir.mkdir(parents=True, exist_ok=True)

    comparison_csv = config.output_dir / f"{config.output_date}_task008_comparison.csv"
    comparison_json = config.output_dir / f"{config.output_date}_task008_comparison.json"
    detail_csv = config.output_dir / f"{config.output_date}_task008_variant_detail.csv"
    attribution_json = config.output_dir / f"{config.output_date}_task008_attribution.json"
    log_path = config.log_dir / f"{config.output_date}_task008_alpha_conc.log"

    strategy = load_strategy_config(config.strategy_config)
    baseline = pd.read_csv(config.baseline_path, parse_dates=["date"])
    positions = pd.read_parquet(config.positions_path)
    positions_cost = pd.read_parquet(config.positions_cost_path)
    prices = pd.read_parquet(config.prices_path)
    membership = pd.read_parquet(config.universe_path)
    attribution_summary = _read_json(config.attribution_summary_path)
    task007_summary = _read_json(config.task007_summary_path)

    active_dates = sorted(baseline.loc[baseline["gross_exposure"] > 0, "date"].map(_normalize_date).unique())
    tradable = load_tradable_membership(config.strategy_config, config.prices_path, config.universe_path)
    gross = build_gross_contributions(positions, prices, tradable)
    primary_costs = load_primary_costs(positions_cost, "realistic_combo")
    fact = _build_base_fact(gross, primary_costs, baseline, active_dates)
    benchmark_cols = ["date", "benchmark_cash_return", "benchmark_btc_return", "benchmark_eqw_return"]
    fact = fact.merge(baseline.loc[:, benchmark_cols], on="date", how="left")
    for col in benchmark_cols[1:]:
        fact[col] = pd.to_numeric(fact[col], errors="coerce").fillna(0.0)

    baseline_daily, baseline_fact = evaluate_baseline(fact)
    baseline_summary = summarize_variant(
        baseline_daily,
        baseline_fact,
        baseline_net_alpha=float(baseline_daily["variant_net_contribution"].sum()),
        baseline_turnover=float(baseline_daily["variant_turnover"].sum()),
        annualization_factor=config.annualization_factor,
    )
    baseline_cost = float(baseline_summary["total_cost"])
    baseline_net_alpha = float(baseline_summary["net_alpha"])
    baseline_turnover = float(baseline_summary["turnover"])
    _apply_cost_impacts({"baseline_current_long_short": baseline_summary}, baseline_cost)

    task007_baseline = _variant_from_task007_summary(task007_summary, "baseline_current_long_short")
    baseline_mismatch = max(
        abs(baseline_net_alpha - float(task007_baseline.get("net_alpha", baseline_net_alpha))),
        abs(baseline_net_alpha - float(attribution_summary.get("net_alpha_total", baseline_net_alpha))),
    )

    candidates = _filter_candidates(_build_candidates(strategy, prices, membership), active_dates)
    target_dates = [candidate["date"] for candidate in candidates]
    period_alpha = build_period_alpha(baseline_fact, target_dates)
    alpha_shares = {
        periods: _alpha_share_lookup(period_alpha, periods)
        for periods in sorted({spec.rolling_periods for spec in VARIANT_SPECS})
    }

    summary: dict[str, dict[str, Any]] = {"baseline_current_long_short": baseline_summary}
    daily_frames = [baseline_daily]
    detail_frames = [
        baseline_fact[
            [
                "variant",
                "date",
                "position_date",
                "symbol",
                "original_weight",
                "variant_weight",
                "variant_return_weight",
                "variant_cost_weight",
                "variant_gross_contribution",
                "variant_fee_cost",
                "variant_slippage_cost",
                "variant_funding_cost",
                "variant_net_contribution",
                "variant_trade_turnover",
            ]
        ]
    ]
    cooldown_details: dict[str, dict[str, Any]] = {}

    for spec in VARIANT_SPECS:
        monthly, detail = build_monthly_variant_weights(candidates, alpha_shares.get(spec.rolling_periods, {}), spec)
        daily_targets = monthly_to_daily_weights(monthly, active_dates)
        daily, variant_fact = evaluate_variant(fact, daily_targets, spec.name)
        daily_frames.append(daily)
        detail_frames.append(
            variant_fact[
                [
                    "variant",
                    "date",
                    "position_date",
                    "symbol",
                    "original_weight",
                    "variant_weight",
                    "variant_return_weight",
                    "variant_cost_weight",
                    "variant_gross_contribution",
                    "variant_fee_cost",
                    "variant_slippage_cost",
                    "variant_funding_cost",
                    "variant_net_contribution",
                    "variant_trade_turnover",
                ]
            ]
        )
        summary[spec.name] = summarize_variant(
            daily,
            variant_fact,
            baseline_net_alpha,
            baseline_turnover,
            annualization_factor=config.annualization_factor,
        )
        cooldown_details[spec.name] = detail

    _apply_cost_impacts(summary, baseline_cost)
    reference = _reference_summary_row(_task007_reference(config.task007_summary_path), baseline_net_alpha, baseline_turnover, baseline_cost)
    summary["task007_combined_paper_safe_reference"] = reference

    comparison = _summary_rows(summary)
    detail = pd.concat(detail_frames, ignore_index=True)
    daily_all = pd.concat(daily_frames, ignore_index=True)

    symbol_attr = {}
    for variant, frame in detail.groupby("variant"):
        symbol_table = (
            frame.groupby("symbol", as_index=False)["variant_net_contribution"]
            .sum()
            .sort_values("variant_net_contribution", ascending=False)
        )
        symbol_attr[variant] = {
            "top_contributors": symbol_table.head(10).to_dict(orient="records"),
            "bottom_contributors": symbol_table.tail(10).to_dict(orient="records"),
        }

    comparison.to_csv(comparison_csv, index=False)
    detail.to_csv(detail_csv, index=False)
    attribution_payload = {
        "output_date": config.output_date,
        "paper_execution": "FORBIDDEN",
        "live_trading": "FORBIDDEN",
        "symbol_attribution": symbol_attr,
        "daily_hash": _frame_hash(daily_all),
        "detail_hash": _frame_hash(detail),
    }
    attribution_json.write_text(json.dumps(_json_safe(attribution_payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    provisional_outputs = [comparison_csv, detail_csv, attribution_json]
    fail_gates, warning_gates = _gates(summary, baseline_mismatch, config, provisional_outputs, cooldown_details)
    status = "REVIEW_READY" if not fail_gates else "FAIL"
    payload = {
        "status": status,
        "output_date": config.output_date,
        "paper_execution": "FORBIDDEN",
        "live_trading": "FORBIDDEN",
        "baseline_mismatch": baseline_mismatch,
        "summary": summary,
        "fail_gates": fail_gates,
        "warning_gates": warning_gates,
        "cooldown_details": cooldown_details,
        "outputs": {
            "comparison_csv": str(comparison_csv),
            "comparison_json": str(comparison_json),
            "detail_csv": str(detail_csv),
            "attribution_json": str(attribution_json),
            "log": str(log_path),
            "review_packet": str(config.review_packet_path),
            "review_numbers": str(config.review_numbers_path),
        },
        "input_hashes": _input_hashes(
            [
                config.strategy_config,
                config.baseline_path,
                config.positions_path,
                config.positions_cost_path,
                config.attribution_summary_path,
                config.task007_summary_path,
                config.prices_path,
                config.universe_path,
            ]
        ),
        "table_hashes": {
            "comparison": _frame_hash(comparison),
            "detail": _frame_hash(detail),
            "daily": _frame_hash(daily_all),
        },
    }
    payload["reproducibility_hash"] = hashlib.sha256(
        json.dumps(_json_safe(payload["table_hashes"]), sort_keys=True).encode("utf-8")
    ).hexdigest()
    comparison_json.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    config.review_numbers_path.parent.mkdir(parents=True, exist_ok=True)
    config.review_numbers_path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_review_packet(config.review_packet_path, payload, comparison)
    log_lines = [
        f"status={status}",
        f"output_date={config.output_date}",
        f"baseline_mismatch={baseline_mismatch:.12g}",
        "paper_execution=FORBIDDEN",
        "live_trading=FORBIDDEN",
        f"fail_gates={len(fail_gates)}",
        f"warning_gates={len(warning_gates)}",
        f"comparison_csv={comparison_csv}",
        f"comparison_json={comparison_json}",
        f"detail_csv={detail_csv}",
        f"attribution_json={attribution_json}",
    ]
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    return Task008Result(
        status=status,
        comparison_csv=comparison_csv,
        comparison_json=comparison_json,
        detail_csv=detail_csv,
        attribution_json=attribution_json,
        log_path=log_path,
        review_packet_path=config.review_packet_path,
        review_numbers_path=config.review_numbers_path,
        fail_gates=fail_gates,
        warning_gates=warning_gates,
    )
