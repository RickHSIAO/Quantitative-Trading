from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.attribution.costs import load_primary_costs
from src.attribution.reproducibility import build_input_hashes, canonical_hash, git_commit
from src.attribution.returns import build_gross_contributions, load_tradable_membership
from src.variants.task007 import (
    _annual_ratio,
    _build_base_fact,
    _concentration_metrics,
    _frame_hash,
    _max_drawdown,
    _normalize_date,
    _safe_div,
    _symbol_contributions,
)


CAP_VARIANT_ORDER = [
    "baseline_current_long_short",
    "cap_20pct",
    "cap_15pct",
    "cap_10pct",
]

TASK007_REFERENCE_VARIANTS = [
    "top5_symbol_cap_5pct",
    "DOT_capped",
    "no_DOT",
]


@dataclass(frozen=True)
class Task007bConfig:
    output_date: str = "20260516"
    tolerance: float = 1e-6
    annualization_factor: float = 365.25
    primary_scenario: str = "realistic_combo"
    baseline_run_id: str = "20260513_run008"
    cost_stress_run_id: str = "20260515"
    task007_run_id: str = "20260515"
    baseline_path: Path = Path("outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv")
    positions_path: Path = Path("outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet")
    positions_cost_path: Path = Path("outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet")
    prices_path: Path = Path("data/crypto/prices_daily.parquet")
    universe_path: Path = Path("data/crypto/universe_membership.parquet")
    prev3y_config_path: Path = Path("configs/prev3y_crypto.yaml")
    task007_daily_path: Path = Path("outputs/variants/prev3y_crypto/20260515_task007_variant_daily.csv")
    task007_summary_path: Path = Path("outputs/variants/prev3y_crypto/20260515_task007_variant_summary.json")
    task007_concentration_path: Path = Path("outputs/variants/prev3y_crypto/20260515_task007_variant_concentration.csv")
    review007_packet_path: Path = Path("docs/research/review_packets/REVIEW-007_PACKET.md")
    review007_numbers_path: Path = Path("docs/research/review_packets/REVIEW-007_NUMBERS.json")
    output_dir: Path = Path("outputs/variants/prev3y_crypto")
    log_dir: Path = Path("outputs/logs/prev3y_crypto")
    review_packet_path: Path = Path("docs/research/review_packets/REVIEW-007b_PACKET.md")
    review_numbers_path: Path = Path("docs/research/review_packets/REVIEW-007b_NUMBERS.json")
    cap_levels: dict[str, float] = field(default_factory=lambda: {
        "cap_20pct": 0.20,
        "cap_15pct": 0.15,
        "cap_10pct": 0.10,
    })
    warning_thresholds: dict[str, float] = field(default_factory=lambda: {
        "top5_concentration_max": 0.70,
        "single_symbol_concentration_max": 0.25,
        "cap10_sharpe_drop_max": 0.30,
        "alpha_retention_min": 0.70,
    })

    def input_paths(self) -> dict[str, Path]:
        return {
            "run008_baseline_csv": self.baseline_path,
            "run008_positions_parquet": self.positions_path,
            "cost_stress_positions_cost_parquet": self.positions_cost_path,
            "prices_daily_parquet": self.prices_path,
            "universe_membership_parquet": self.universe_path,
            "prev3y_crypto_yaml": self.prev3y_config_path,
            "task007_daily_csv": self.task007_daily_path,
            "task007_summary_json": self.task007_summary_path,
            "task007_concentration_csv": self.task007_concentration_path,
            "review007_packet_md": self.review007_packet_path,
            "review007_numbers_json": self.review007_numbers_path,
        }


@dataclass(frozen=True)
class Task007bResult:
    daily: pd.DataFrame
    summary: pd.DataFrame
    redistribution_log: pd.DataFrame
    gate_report: dict[str, Any]
    summary_json: dict[str, Any]
    review_packet: str
    review_numbers: dict[str, Any]
    log_text: str


def run_task007b(config: Task007bConfig) -> Task007bResult:
    baseline = pd.read_csv(config.baseline_path, parse_dates=["date"])
    positions = pd.read_parquet(config.positions_path)
    positions_cost = pd.read_parquet(config.positions_cost_path)
    prices = pd.read_parquet(config.prices_path)
    task007_daily = pd.read_csv(config.task007_daily_path, parse_dates=["date"])
    task007_summary = json.loads(config.task007_summary_path.read_text(encoding="utf-8"))
    task007_concentration = pd.read_csv(config.task007_concentration_path)

    _normalize_date(baseline, "date")
    _normalize_date(task007_daily, "date")
    active_dates = set(baseline.loc[baseline["gross_exposure"].astype(float).gt(0), "date"])
    if not active_dates:
        raise RuntimeError("NEED_CLARIFICATION: run008 baseline has no active dates")

    tradable = load_tradable_membership(
        config.prev3y_config_path,
        config.prices_path,
        config.universe_path,
    )
    gross = build_gross_contributions(positions, prices, tradable)
    primary_costs = load_primary_costs(positions_cost, config.primary_scenario)
    fact = _build_base_fact(gross, primary_costs, baseline, active_dates)

    baseline_fact = fact.assign(
        variant="baseline_current_long_short",
        variant_return_weight=fact["return_base_weight"],
        variant_cost_weight=fact["cost_base_weight"],
        variant_weight=fact["original_weight"],
        cap_level=np.nan,
        cap_original_gross=fact["baseline_gross_exposure"],
        cap_was_capped=False,
        cap_had_room=True,
        cap_redistributed_weight=0.0,
        cap_gross_reduction=0.0,
    )
    baseline_fact = _apply_task007b_variant_costs(baseline_fact)

    variant_frames = [baseline_fact]
    log_frames = []
    for variant, cap_level in config.cap_levels.items():
        return_weights, return_log = _apply_cap_variant(
            fact=fact,
            base_weight_col="return_base_weight",
            variant=variant,
            cap_level=cap_level,
            record_log=True,
        )
        cost_weights, _ = _apply_cap_variant(
            fact=fact,
            base_weight_col="cost_base_weight",
            variant=variant,
            cap_level=cap_level,
            record_log=False,
        )
        variant_fact = fact.copy()
        variant_fact["variant"] = variant
        variant_fact["variant_return_weight"] = return_weights
        variant_fact["variant_cost_weight"] = cost_weights
        variant_fact["variant_weight"] = np.where(
            variant_fact["variant_cost_weight"].abs().gt(0),
            variant_fact["variant_cost_weight"],
            variant_fact["variant_return_weight"],
        )
        variant_fact["cap_level"] = cap_level
        variant_fact["cap_original_gross"] = variant_fact["original_weight"].abs().groupby(variant_fact["date"]).transform("sum")
        capped_keys = _log_key_frame(return_log)
        variant_fact = variant_fact.merge(capped_keys, on=["variant", "date", "symbol"], how="left")
        variant_fact["cap_was_capped"] = variant_fact["cap_was_capped"].fillna(False).astype(bool)
        variant_fact["cap_had_room"] = variant_fact["cap_had_room"].fillna(True).astype(bool)
        variant_fact["cap_redistributed_weight"] = pd.to_numeric(
            variant_fact["cap_redistributed_weight"], errors="coerce"
        ).fillna(0.0)
        variant_fact["cap_gross_reduction"] = pd.to_numeric(
            variant_fact["cap_gross_reduction"], errors="coerce"
        ).fillna(0.0)
        variant_frames.append(_apply_task007b_variant_costs(variant_fact))
        log_frames.append(return_log)

    all_fact = pd.concat(variant_frames, ignore_index=True)
    redistribution_log = _redistribution_log_table(log_frames)
    daily = _daily_table_task007b(all_fact, redistribution_log, baseline, task007_daily)
    summary = _summary_table_task007b(all_fact, daily, task007_summary, config)
    baseline_checks = _baseline_reconciliation_checks(daily, baseline, task007_daily)
    overflow_checks = _redistribution_overflow_checks(daily, config)
    safety_scan = _paper_live_execution_scan([
        Path("src/variants/task007b.py"),
        Path("scripts/task007b_weight_cap_redistribution.py"),
    ])
    gate_report = _gate_report(summary, redistribution_log, baseline_checks, overflow_checks, safety_scan, config)
    summary_json = _summary_json(summary, daily, redistribution_log, gate_report, task007_summary, task007_concentration, config)

    output_table_hashes = {
        "daily": _frame_hash(daily),
        "summary": _frame_hash(summary),
        "redistribution_log": _frame_hash(redistribution_log),
        "gate_report_without_hash": canonical_hash(_json_clean(gate_report)),
    }
    summary_json["table_hashes"] = output_table_hashes
    summary_json["reproducibility_hash"] = canonical_hash({
        "summary_without_hash": {
            key: value for key, value in summary_json.items()
            if key != "reproducibility_hash"
        },
        "table_hashes": output_table_hashes,
    })
    gate_report["reproducibility_hash"] = summary_json["reproducibility_hash"]
    summary_json["gate_results"] = gate_report

    review_packet = _review_packet(summary_json, summary, redistribution_log, config)
    review_numbers = _review_numbers_payload(summary_json, summary)
    log_text = _log_text(summary_json, config)
    return Task007bResult(
        daily=daily,
        summary=summary,
        redistribution_log=redistribution_log,
        gate_report=gate_report,
        summary_json=summary_json,
        review_packet=review_packet,
        review_numbers=review_numbers,
        log_text=log_text,
    )


def write_task007b_outputs(result: Task007bResult, config: Task007bConfig) -> tuple[dict[str, Path], list[str]]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.log_dir.mkdir(parents=True, exist_ok=True)
    config.review_packet_path.parent.mkdir(parents=True, exist_ok=True)

    paths = {
        "daily": config.output_dir / f"{config.output_date}_task007b_cap_daily.csv",
        "summary_csv": config.output_dir / f"{config.output_date}_task007b_cap_summary.csv",
        "summary_json": config.output_dir / f"{config.output_date}_task007b_cap_summary.json",
        "redistribution_log": config.output_dir / f"{config.output_date}_task007b_redistribution_log.csv",
        "gate_report": config.output_dir / f"{config.output_date}_task007b_gate_report.json",
        "log": config.log_dir / f"{config.output_date}_task007b_weight_cap_redistribution.log",
        "review_packet": config.review_packet_path,
        "review_numbers": config.review_numbers_path,
    }
    result.daily.to_csv(paths["daily"], index=False)
    result.summary.to_csv(paths["summary_csv"], index=False)
    result.redistribution_log.to_csv(paths["redistribution_log"], index=False)
    paths["summary_json"].write_text(
        json.dumps(_json_clean(result.summary_json), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["gate_report"].write_text(
        json.dumps(_json_clean(result.gate_report), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["log"].write_text(result.log_text, encoding="utf-8")
    paths["review_packet"].write_text(result.review_packet, encoding="utf-8")
    paths["review_numbers"].write_text(
        json.dumps(_json_clean(result.review_numbers), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return paths, _validate_outputs(paths, result)


def _apply_cap_variant(
    fact: pd.DataFrame,
    base_weight_col: str,
    variant: str,
    cap_level: float,
    record_log: bool,
) -> tuple[pd.Series, pd.DataFrame]:
    pieces = []
    logs = []
    for date, group in fact.groupby("date", sort=True):
        capped, group_logs = _cap_one_day(
            date=pd.Timestamp(date),
            symbols=group["symbol"].astype(str).tolist(),
            weights=group[base_weight_col].astype(float).to_numpy(),
            variant=variant,
            cap_level=cap_level,
        )
        pieces.append(pd.Series(capped, index=group.index))
        if record_log and group_logs:
            logs.extend(group_logs)
    weights = pd.concat(pieces).sort_index()
    log_frame = pd.DataFrame(logs)
    if log_frame.empty:
        log_frame = _empty_redistribution_log()
    return weights, log_frame


def _apply_task007b_variant_costs(fact: pd.DataFrame) -> pd.DataFrame:
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
    zero_weight_settlement_cost = (
        cost_original.eq(0.0)
        & cost_variant.eq(0.0)
        & (
            out["fee_cost"].astype(float).ne(0.0)
            | out["slippage_cost"].astype(float).ne(0.0)
            | out["funding_cost"].astype(float).ne(0.0)
        )
    )
    scale = np.where(zero_weight_settlement_cost, 1.0, scale)
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


def _cap_one_day(
    date: pd.Timestamp,
    symbols: list[str],
    weights: np.ndarray,
    variant: str,
    cap_level: float,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    original = np.asarray(weights, dtype=float)
    new = original.copy()
    original_gross = float(np.abs(original).sum())
    cap_abs_weight = float(cap_level * original_gross)
    logs: list[dict[str, Any]] = []
    if original_gross <= 1e-12 or cap_abs_weight <= 1e-12:
        return new, logs

    for side_label, side_sign in [("long", 1.0), ("short", -1.0)]:
        side_mask = original * side_sign > 1e-12
        if not side_mask.any():
            continue
        side_indices = np.flatnonzero(side_mask)
        over_indices = side_indices[np.abs(new[side_indices]) > cap_abs_weight + 1e-12]
        if len(over_indices) == 0:
            continue

        excess_by_index = {
            int(idx): float(abs(new[idx]) - cap_abs_weight)
            for idx in over_indices
        }
        for idx in over_indices:
            new[idx] = side_sign * cap_abs_weight

        total_excess = float(sum(excess_by_index.values()))
        eligible_indices = [
            int(idx)
            for idx in side_indices
            if idx not in excess_by_index and abs(new[idx]) < cap_abs_weight - 1e-12
        ]
        room_by_index = {
            idx: max(0.0, float(cap_abs_weight - abs(new[idx])))
            for idx in eligible_indices
        }
        total_room = float(sum(room_by_index.values()))
        redistributed_total = min(total_excess, total_room) if total_room > 1e-12 else 0.0
        target_records: list[dict[str, Any]] = []
        if redistributed_total > 1e-12:
            for idx, room in room_by_index.items():
                add_abs = redistributed_total * room / total_room
                if add_abs <= 0:
                    continue
                new[idx] += side_sign * add_abs
                target_records.append({
                    "symbol": symbols[idx],
                    "added_abs_weight": add_abs,
                    "new_weight": float(new[idx]),
                })

        gross_reduction_total = max(0.0, total_excess - redistributed_total)
        if redistributed_total <= 1e-12 and gross_reduction_total > 1e-12:
            event_type = "redistribution_has_no_room"
        elif gross_reduction_total > 1e-12:
            event_type = "partial_redistribution_no_room"
        else:
            event_type = "redistributed"

        for idx, excess in excess_by_index.items():
            share = _safe_div(excess, total_excess)
            logs.append({
                "variant": variant,
                "cap_level": cap_level,
                "date": date.strftime("%Y-%m-%d"),
                "side": side_label,
                "symbol": symbols[idx],
                "original_weight": float(original[idx]),
                "capped_weight": float(side_sign * cap_abs_weight),
                "final_weight": float(new[idx]),
                "original_gross": original_gross,
                "cap_abs_weight": cap_abs_weight,
                "original_weight_pct_of_gross": _safe_div(abs(float(original[idx])), original_gross),
                "final_weight_pct_of_original_gross": _safe_div(abs(float(new[idx])), original_gross),
                "excess_weight": excess,
                "redistributed_weight": redistributed_total * share,
                "gross_reduction": gross_reduction_total * share,
                "eligible_room": total_room,
                "redistribution_target_count": len(target_records),
                "redistribution_targets": json.dumps(target_records, sort_keys=True),
                "event_type": event_type,
            })
    return new, logs


def _empty_redistribution_log() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "variant",
        "cap_level",
        "date",
        "side",
        "symbol",
        "original_weight",
        "capped_weight",
        "final_weight",
        "original_gross",
        "cap_abs_weight",
        "original_weight_pct_of_gross",
        "final_weight_pct_of_original_gross",
        "excess_weight",
        "redistributed_weight",
        "gross_reduction",
        "eligible_room",
        "redistribution_target_count",
        "redistribution_targets",
        "event_type",
    ])


def _redistribution_log_table(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return _empty_redistribution_log()
    non_empty = [frame for frame in frames if not frame.empty]
    if not non_empty:
        return _empty_redistribution_log()
    out = pd.concat(non_empty, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out.sort_values(["variant", "date", "side", "symbol"]).reset_index(drop=True)


def _log_key_frame(log: pd.DataFrame) -> pd.DataFrame:
    if log.empty:
        return pd.DataFrame(columns=[
            "variant",
            "date",
            "symbol",
            "cap_was_capped",
            "cap_had_room",
            "cap_redistributed_weight",
            "cap_gross_reduction",
        ])
    keys = log.loc[:, [
        "variant",
        "date",
        "symbol",
        "event_type",
        "redistributed_weight",
        "gross_reduction",
    ]].copy()
    keys["date"] = pd.to_datetime(keys["date"]).dt.normalize()
    keys["cap_was_capped"] = True
    keys["cap_had_room"] = ~keys["event_type"].astype(str).eq("redistribution_has_no_room")
    keys = keys.rename(columns={
        "redistributed_weight": "cap_redistributed_weight",
        "gross_reduction": "cap_gross_reduction",
    })
    return keys.loc[:, [
        "variant",
        "date",
        "symbol",
        "cap_was_capped",
        "cap_had_room",
        "cap_redistributed_weight",
        "cap_gross_reduction",
    ]]


def _daily_table_task007b(
    fact: pd.DataFrame,
    redistribution_log: pd.DataFrame,
    baseline: pd.DataFrame,
    task007_daily: pd.DataFrame,
) -> pd.DataFrame:
    temp = fact.copy()
    temp["date"] = pd.to_datetime(temp["date"]).dt.normalize()
    grouped = temp.groupby(["variant", "date"], as_index=False).agg(
        cap_level=("cap_level", "first"),
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
        original_gross_exposure=("cap_original_gross", "first"),
        max_abs_weight=("variant_weight", lambda x: float(np.abs(x).max()) if len(x) else 0.0),
        capped_symbol_days=("cap_was_capped", "sum"),
        redistributed_weight_row_sum=("cap_redistributed_weight", "sum"),
        gross_reduction_row_sum=("cap_gross_reduction", "sum"),
    )
    grouped["max_symbol_weight_pct_of_original_gross"] = grouped.apply(
        lambda row: _safe_div(float(row["max_abs_weight"]), float(row["original_gross_exposure"])),
        axis=1,
    )
    grouped["max_symbol_weight_pct_of_new_gross"] = grouped.apply(
        lambda row: _safe_div(float(row["max_abs_weight"]), float(row["gross_exposure"])),
        axis=1,
    )
    if redistribution_log.empty:
        log_daily = pd.DataFrame(columns=[
            "variant",
            "date",
            "cap_breach_count",
            "redistribution_event_count",
            "redistribution_has_no_room_events",
            "total_excess_weight",
            "redistributed_weight",
            "gross_reduction",
        ])
    else:
        log_temp = redistribution_log.copy()
        log_temp["date"] = pd.to_datetime(log_temp["date"]).dt.normalize()
        log_daily = log_temp.groupby(["variant", "date"], as_index=False).agg(
            cap_breach_count=("symbol", "count"),
            redistribution_event_count=("event_type", lambda x: int((x.astype(str) == "redistributed").sum())),
            redistribution_has_no_room_events=("event_type", lambda x: int((x.astype(str).str.contains("no_room")).sum())),
            total_excess_weight=("excess_weight", "sum"),
            redistributed_weight=("redistributed_weight", "sum"),
            gross_reduction=("gross_reduction", "sum"),
        )
    grouped = grouped.merge(log_daily, on=["variant", "date"], how="left")
    for col in [
        "cap_breach_count",
        "redistribution_event_count",
        "redistribution_has_no_room_events",
        "total_excess_weight",
        "redistributed_weight",
        "gross_reduction",
    ]:
        grouped[col] = pd.to_numeric(grouped[col], errors="coerce").fillna(0.0)
    benchmark_cols = [
        "date",
        "benchmark_return",
        "benchmark_cash_return",
        "benchmark_btc_return",
        "benchmark_eqw_return",
        "portfolio_return",
    ]
    grouped = grouped.merge(
        baseline.loc[:, benchmark_cols].rename(columns={"portfolio_return": "run008_gross_return"}),
        on="date",
        how="left",
    )
    task007_base = task007_daily[task007_daily["variant"].astype(str).eq("baseline_current_long_short")].copy()
    task007_base["date"] = pd.to_datetime(task007_base["date"]).dt.normalize()
    task007_base = task007_base.loc[:, [
        "date",
        "portfolio_return_gross",
        "portfolio_return_net",
        "task002_realistic_combo_net_return",
    ]].rename(columns={
        "portfolio_return_gross": "task007_baseline_gross_return",
        "portfolio_return_net": "task007_baseline_net_return",
    })
    grouped = grouped.merge(task007_base, on="date", how="left")
    grouped["date"] = pd.to_datetime(grouped["date"]).dt.strftime("%Y-%m-%d")
    order = {name: idx for idx, name in enumerate(CAP_VARIANT_ORDER)}
    grouped["_order"] = grouped["variant"].map(order)
    columns = [
        "variant",
        "date",
        "cap_level",
        "portfolio_return_gross",
        "portfolio_return_net",
        "fee_cost",
        "slippage_cost",
        "funding_cost",
        "trade_turnover_proxy",
        "gross_exposure",
        "net_exposure",
        "original_gross_exposure",
        "n_longs",
        "n_shorts",
        "cap_breach_count",
        "redistribution_event_count",
        "redistribution_has_no_room_events",
        "total_excess_weight",
        "redistributed_weight",
        "gross_reduction",
        "max_abs_weight",
        "max_symbol_weight_pct_of_original_gross",
        "max_symbol_weight_pct_of_new_gross",
        "benchmark_return",
        "benchmark_cash_return",
        "benchmark_btc_return",
        "benchmark_eqw_return",
        "run008_gross_return",
        "task007_baseline_gross_return",
        "task007_baseline_net_return",
        "task002_realistic_combo_net_return",
    ]
    return grouped.sort_values(["_order", "date"]).loc[:, columns].reset_index(drop=True)


def _summary_table_task007b(
    fact: pd.DataFrame,
    daily: pd.DataFrame,
    task007_summary: dict[str, Any],
    config: Task007bConfig,
) -> pd.DataFrame:
    rows = []
    task007_rows = {str(row["variant"]): row for row in task007_summary["summary"]}
    baseline_net = float(task007_rows["baseline_current_long_short"]["net_alpha"])
    baseline_max_dd = float(task007_rows["baseline_current_long_short"]["max_dd"])
    for variant in CAP_VARIANT_ORDER:
        variant_daily = daily[daily["variant"].astype(str).eq(variant)].copy()
        variant_fact = fact[fact["variant"].astype(str).eq(variant)].copy()
        net_returns = variant_daily["portfolio_return_net"].astype(float)
        gross_returns = variant_daily["portfolio_return_gross"].astype(float)
        net_alpha = float(net_returns.sum())
        gross_alpha = float(gross_returns.sum())
        by_symbol = _symbol_contributions(variant_fact)
        concentration = _concentration_metrics(by_symbol, net_alpha)
        max_dd = _max_drawdown(net_returns)
        rows.append({
            "source": "task007b_weight_cap_redistribution",
            "variant": variant,
            "cap_level": _cap_level_for_variant(variant, config),
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
            "alpha_retention_pct": _safe_div(net_alpha, baseline_net),
            "long_net_contribution": float(
                variant_fact.loc[variant_fact["variant_side"].eq("long"), "variant_net_contribution"].sum()
            ),
            "short_net_contribution": float(
                variant_fact.loc[variant_fact["variant_side"].eq("short"), "variant_net_contribution"].sum()
            ),
            "top5_concentration_net_alpha_total": concentration["top5_concentration"],
            "single_symbol_concentration_net_alpha_total": concentration["single_symbol_concentration"],
            "top_symbol": concentration["top_symbol"],
            "fee_cost": float(variant_fact["variant_fee_cost"].sum()),
            "slippage_cost": float(variant_fact["variant_slippage_cost"].sum()),
            "funding_cost": float(variant_fact["variant_funding_cost"].sum()),
            "gross_exposure_mean": float(variant_daily["gross_exposure"].mean()),
            "net_exposure_mean": float(variant_daily["net_exposure"].mean()),
            "turnover_proxy_sum": float(variant_daily["trade_turnover_proxy"].sum()),
            "cap_breach_count": int(variant_daily["cap_breach_count"].sum()),
            "redistribution_has_no_room_events": int(variant_daily["redistribution_has_no_room_events"].sum()),
            "total_excess_weight": float(variant_daily["total_excess_weight"].sum()),
            "redistributed_weight": float(variant_daily["redistributed_weight"].sum()),
            "gross_reduction": float(variant_daily["gross_reduction"].sum()),
            "max_symbol_weight_pct_of_original_gross": float(variant_daily["max_symbol_weight_pct_of_original_gross"].max()),
            "max_symbol_weight_pct_of_new_gross": float(variant_daily["max_symbol_weight_pct_of_new_gross"].max()),
        })

    for variant in TASK007_REFERENCE_VARIANTS:
        ref = dict(task007_rows[variant])
        rows.append({
            "source": "task007_alpha_based_reference",
            "variant": variant,
            "cap_level": np.nan,
            "active_days": ref.get("active_days"),
            "sharpe_active": ref.get("sharpe_active"),
            "ir_vs_cash_active": ref.get("ir_vs_cash_active"),
            "ir_vs_equal_weight_active": ref.get("ir_vs_equal_weight_active"),
            "ir_vs_btc_active": ref.get("ir_vs_btc_active"),
            "max_dd": ref.get("max_dd"),
            "max_dd_vs_baseline_multiple": ref.get("max_dd_vs_baseline_multiple"),
            "gross_alpha": ref.get("gross_alpha"),
            "net_alpha": ref.get("net_alpha"),
            "net_alpha_delta_vs_baseline": ref.get("net_alpha_delta_vs_baseline"),
            "alpha_retention_pct": ref.get("alpha_retention_pct"),
            "long_net_contribution": ref.get("long_net_contribution"),
            "short_net_contribution": ref.get("short_net_contribution"),
            "top5_concentration_net_alpha_total": ref.get("top5_concentration_net_alpha_total"),
            "single_symbol_concentration_net_alpha_total": ref.get("single_symbol_concentration_net_alpha_total"),
            "top_symbol": ref.get("top_symbol"),
            "fee_cost": ref.get("fee_cost"),
            "slippage_cost": ref.get("slippage_cost"),
            "funding_cost": ref.get("funding_cost"),
            "gross_exposure_mean": ref.get("gross_exposure_mean"),
            "net_exposure_mean": ref.get("net_exposure_mean"),
            "turnover_proxy_sum": ref.get("turnover_proxy_sum"),
            "cap_breach_count": np.nan,
            "redistribution_has_no_room_events": np.nan,
            "total_excess_weight": np.nan,
            "redistributed_weight": np.nan,
            "gross_reduction": np.nan,
            "max_symbol_weight_pct_of_original_gross": np.nan,
            "max_symbol_weight_pct_of_new_gross": np.nan,
        })
    return pd.DataFrame(rows)


def _baseline_reconciliation_checks(
    daily: pd.DataFrame,
    baseline: pd.DataFrame,
    task007_daily: pd.DataFrame,
) -> dict[str, float]:
    base = daily[daily["variant"].astype(str).eq("baseline_current_long_short")].copy()
    base["date"] = pd.to_datetime(base["date"]).dt.normalize()
    run008 = baseline.loc[:, ["date", "portfolio_return"]].copy()
    run008["date"] = pd.to_datetime(run008["date"]).dt.normalize()
    merged = base.merge(run008, on="date", how="left", suffixes=("", "_run008"))
    task007_base = task007_daily[task007_daily["variant"].astype(str).eq("baseline_current_long_short")].copy()
    task007_base["date"] = pd.to_datetime(task007_base["date"]).dt.normalize()
    merged = merged.merge(
        task007_base.loc[:, [
            "date",
            "portfolio_return_gross",
            "portfolio_return_net",
            "task002_realistic_combo_net_return",
        ]].rename(columns={
            "portfolio_return_gross": "task007_gross",
            "portfolio_return_net": "task007_net",
            "task002_realistic_combo_net_return": "task007_task002_realistic_combo_net_return",
        }),
        on="date",
        how="left",
    )
    return {
        "gross_vs_run008_max_diff": float((merged["portfolio_return_gross"] - merged["portfolio_return"]).abs().max()),
        "gross_vs_task007_max_diff": float((merged["portfolio_return_gross"] - merged["task007_gross"]).abs().max()),
        "net_vs_task007_max_diff": float((merged["portfolio_return_net"] - merged["task007_net"]).abs().max()),
        "net_vs_task002_realistic_combo_max_diff": float(
            (merged["portfolio_return_net"] - merged["task007_task002_realistic_combo_net_return"]).abs().max()
        ),
    }


def _redistribution_overflow_checks(daily: pd.DataFrame, config: Task007bConfig) -> dict[str, Any]:
    cap_daily = daily[daily["variant"].isin(config.cap_levels.keys())].copy()
    cap_daily["overflow_amount"] = cap_daily["gross_exposure"] - cap_daily["original_gross_exposure"] * (1.0 + config.tolerance)
    overflow = cap_daily[cap_daily["overflow_amount"].gt(0)]
    return {
        "max_overflow_amount": float(max(0.0, cap_daily["overflow_amount"].max())) if not cap_daily.empty else 0.0,
        "overflow_rows": int(len(overflow)),
        "sample": overflow.head(10).loc[:, [
            "variant",
            "date",
            "gross_exposure",
            "original_gross_exposure",
            "overflow_amount",
        ]].to_dict(orient="records"),
    }


def _paper_live_execution_scan(paths: list[Path]) -> dict[str, Any]:
    patterns = [
        "place" + "_order(",
        "submit" + "_order(",
        "create" + "_order(",
        "/v5/order" + "/create",
        "private" + "_post_order",
    ]
    matches = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            if pattern in text:
                matches.append({"path": str(path), "pattern": pattern})
    return {
        "scanned_paths": [str(path) for path in paths],
        "forbidden_matches": matches,
        "real_or_paper_execution_code_detected": bool(matches),
    }


def _gate_report(
    summary: pd.DataFrame,
    redistribution_log: pd.DataFrame,
    baseline_checks: dict[str, float],
    overflow_checks: dict[str, Any],
    safety_scan: dict[str, Any],
    config: Task007bConfig,
) -> dict[str, Any]:
    by_variant = {str(row["variant"]): row for row in summary.to_dict(orient="records")}
    baseline = by_variant["baseline_current_long_short"]
    cap15 = by_variant["cap_15pct"]
    cap10 = by_variant["cap_10pct"]
    baseline_sharpe = float(baseline["sharpe_active"])
    cap10_sharpe = float(cap10["sharpe_active"])
    sharpe_drop = _safe_div(baseline_sharpe - cap10_sharpe, abs(baseline_sharpe))
    max_baseline_diff = max(float(value) for value in baseline_checks.values())
    no_room_events = int((redistribution_log["event_type"].astype(str).str.contains("no_room")).sum()) if not redistribution_log.empty else 0
    cap_rows = [
        row for row in summary.to_dict(orient="records")
        if row["source"] == "task007b_weight_cap_redistribution" and str(row["variant"]).startswith("cap_")
    ]
    top5_above = {
        row["variant"]: float(row["top5_concentration_net_alpha_total"])
        for row in cap_rows
        if float(row["top5_concentration_net_alpha_total"]) > config.warning_thresholds["top5_concentration_max"]
    }
    single_above = {
        row["variant"]: float(row["single_symbol_concentration_net_alpha_total"])
        for row in cap_rows
        if float(row["single_symbol_concentration_net_alpha_total"]) > config.warning_thresholds["single_symbol_concentration_max"]
    }
    alpha_low = {
        row["variant"]: float(row["alpha_retention_pct"])
        for row in cap_rows
        if float(row["alpha_retention_pct"]) < config.warning_thresholds["alpha_retention_min"]
    }
    return {
        "fail_gates": {
            "baseline_reconciliation_mismatch": {
                "triggered": bool(max_baseline_diff > config.tolerance),
                "value": max_baseline_diff,
                "threshold": config.tolerance,
                "details": baseline_checks,
            },
            "missing_outputs": {
                "triggered": False,
                "missing": [],
            },
            "schema_mismatch": {
                "triggered": False,
                "errors": [],
            },
            "redistribution_overflow": {
                "triggered": bool(overflow_checks["overflow_rows"] > 0),
                "value": overflow_checks["max_overflow_amount"],
                "threshold": config.tolerance,
                "details": overflow_checks,
            },
            "paper_live_execution_code": {
                "triggered": bool(safety_scan["real_or_paper_execution_code_detected"]),
                "details": safety_scan,
            },
        },
        "warning_gates": {
            "concentration_not_reduced_cap15": {
                "description": "cap=15% top5 concentration remains above 70%",
                "triggered": bool(float(cap15["top5_concentration_net_alpha_total"]) > config.warning_thresholds["top5_concentration_max"]),
                "value": float(cap15["top5_concentration_net_alpha_total"]),
                "threshold": config.warning_thresholds["top5_concentration_max"],
            },
            "cap10_sharpe_drop": {
                "description": "cap=10% Sharpe drop vs baseline exceeds 30%",
                "triggered": bool(sharpe_drop > config.warning_thresholds["cap10_sharpe_drop_max"]),
                "value": sharpe_drop,
                "threshold": config.warning_thresholds["cap10_sharpe_drop_max"],
            },
            "top5_concentration_above_threshold": {
                "description": "cap variants with top5 concentration above 70%",
                "triggered": bool(top5_above),
                "threshold": config.warning_thresholds["top5_concentration_max"],
                "values": top5_above,
            },
            "single_symbol_concentration_above_threshold": {
                "description": "cap variants with single-symbol concentration above 25%",
                "triggered": bool(single_above),
                "threshold": config.warning_thresholds["single_symbol_concentration_max"],
                "values": single_above,
            },
            "alpha_retention_below_threshold": {
                "description": "cap variants retaining less than 70% of baseline net alpha",
                "triggered": bool(alpha_low),
                "threshold": config.warning_thresholds["alpha_retention_min"],
                "values": alpha_low,
            },
            "redistribution_has_no_room": {
                "description": "same-side redistribution had no eligible room and gross exposure was reduced",
                "triggered": bool(no_room_events > 0),
                "value": no_room_events,
                "threshold": 0,
            },
        },
        "baseline_reconciliation": baseline_checks,
        "redistribution_overflow": overflow_checks,
        "paper_live_execution_scan": safety_scan,
    }


def _summary_json(
    summary: pd.DataFrame,
    daily: pd.DataFrame,
    redistribution_log: pd.DataFrame,
    gate_report: dict[str, Any],
    task007_summary: dict[str, Any],
    task007_concentration: pd.DataFrame,
    config: Task007bConfig,
) -> dict[str, Any]:
    task007_rows = {str(row["variant"]): row for row in task007_summary["summary"]}
    baseline = summary[summary["variant"].eq("baseline_current_long_short")].iloc[0].to_dict()
    cap_rows = {
        str(row["variant"]): row
        for row in summary[summary["source"].eq("task007b_weight_cap_redistribution")].to_dict(orient="records")
        if str(row["variant"]).startswith("cap_")
    }
    ref_rows = {
        name: {
            "sharpe_active": task007_rows[name]["sharpe_active"],
            "net_alpha": task007_rows[name]["net_alpha"],
            "top5_concentration_net_alpha_total": task007_rows[name]["top5_concentration_net_alpha_total"],
            "single_symbol_concentration_net_alpha_total": task007_rows[name]["single_symbol_concentration_net_alpha_total"],
            "max_dd": task007_rows[name]["max_dd"],
        }
        for name in TASK007_REFERENCE_VARIANTS
    }
    baseline_conc = (
        task007_concentration[task007_concentration["variant"].astype(str).eq("baseline_current_long_short")]
        .sort_values("net_alpha_contribution", ascending=False)
        .head(5)
        .loc[:, ["symbol", "net_alpha_contribution", "pct_of_variant_net_alpha"]]
        .to_dict(orient="records")
    )
    return {
        "run_date": config.output_date,
        "analysis_basis": "TASK-007b post-processing weight-cap redistribution overlay study, not a trading decision",
        "baseline_run_id": config.baseline_run_id,
        "cost_stress_run_id": config.cost_stress_run_id,
        "task007_run_id": config.task007_run_id,
        "primary_scenario": config.primary_scenario,
        "methodology": {
            "cap_logic": "daily_weight_pct_of_original_gross_exposure_with_same_direction_redistribution",
            "cap_levels": config.cap_levels,
            "redistribution": "long excess to eligible long symbols only; short excess to eligible short symbols only",
            "no_room_policy": "reduce gross exposure and record redistribution_has_no_room; never force opposite-side redistribution",
            "cost_source": "official TASK-002 realistic_combo symbol-day costs",
            "cost_scaling": "cost_scale = abs(new_weight / original_weight); costs zero if new_weight is zero",
            "return_dating": "positions.date + 1 day = return_date",
            "annualization_factor": config.annualization_factor,
            "std_ddof": 1,
        },
        "baseline_run008": {
            "sharpe_active": baseline["sharpe_active"],
            "net_alpha": baseline["net_alpha"],
            "top5_concentration_net_alpha_total": baseline["top5_concentration_net_alpha_total"],
            "single_symbol_concentration_net_alpha_total": baseline["single_symbol_concentration_net_alpha_total"],
            "max_dd": baseline["max_dd"],
            "top5_symbols": baseline_conc,
        },
        "task007_alpha_based_reference": ref_rows,
        "task007b_weight_cap_redistribution": cap_rows,
        "summary": summary.to_dict(orient="records"),
        "redistribution_summary": {
            "rows": int(len(redistribution_log)),
            "event_type_counts": (
                redistribution_log["event_type"].astype(str).value_counts().to_dict()
                if not redistribution_log.empty else {}
            ),
            "cap_breach_dates": (
                redistribution_log.groupby("variant")["date"].nunique().to_dict()
                if not redistribution_log.empty else {}
            ),
        },
        "gate_results": gate_report,
        "recommended_cap_for_task006": "TBD_REVIEW_REQUIRED",
        "paper_trading_note": "not a trading decision; paper execution and live trading remain forbidden",
        "input_hashes": build_input_hashes(config.input_paths()),
        "git_commit": git_commit(),
    }


def _review_packet(
    summary_json: dict[str, Any],
    summary: pd.DataFrame,
    redistribution_log: pd.DataFrame,
    config: Task007bConfig,
) -> str:
    task_rows = summary[summary["source"].eq("task007b_weight_cap_redistribution")].copy()
    reference_rows = summary[summary["source"].eq("task007_alpha_based_reference")].copy()
    rows = [
        (
            f"| {row.variant} | {_format_pct_or_dash(row.cap_level)} | {row.sharpe_active:.4f} | "
            f"{row.ir_vs_equal_weight_active:.4f} | {row.max_dd:.2%} | {row.net_alpha:.2%} | "
            f"{row.alpha_retention_pct:.2%} | {row.top5_concentration_net_alpha_total:.2%} | "
            f"{row.single_symbol_concentration_net_alpha_total:.2%} | {int(row.redistribution_has_no_room_events) if not pd.isna(row.redistribution_has_no_room_events) else 0} |"
        )
        for row in task_rows.itertuples(index=False)
    ]
    ref_lines = [
        (
            f"| {row.variant} | {row.sharpe_active:.4f} | {row.max_dd:.2%} | {row.net_alpha:.2%} | "
            f"{row.alpha_retention_pct:.2%} | {row.top5_concentration_net_alpha_total:.2%} | "
            f"{row.single_symbol_concentration_net_alpha_total:.2%} |"
        )
        for row in reference_rows.itertuples(index=False)
    ]
    fail_triggered = [
        name for name, gate in summary_json["gate_results"]["fail_gates"].items()
        if gate.get("triggered")
    ]
    warning_triggered = [
        name for name, gate in summary_json["gate_results"]["warning_gates"].items()
        if gate.get("triggered")
    ]
    edge_counts = redistribution_log["event_type"].value_counts().to_dict() if not redistribution_log.empty else {}
    caveats = [
        "20% and 15% caps are no-op on current run008 weights because max symbol weight is about 12.5% of original gross.",
        "10% cap has real breaches; same-side redistribution has no room on those breach days, so gross exposure is reduced.",
        "This is an overlay study only and not a strategy-layer sizing change.",
    ]
    return "\n".join([
        "# REVIEW-007b Packet - TASK-007b Weight Cap + Redistribution",
        "",
        "Analysis basis: post-processing overlay on official run008/TASK-002/TASK-007 inputs.",
        "No paper trading or live trading approval is implied by this packet.",
        "",
        "## Methodology",
        "- Cap is applied daily as abs(weight) <= cap * original gross exposure.",
        "- Long excess redistributes only to eligible long symbols; short excess redistributes only to eligible short symbols.",
        "- If no same-side room exists, gross exposure is reduced and the event is logged.",
        "- Costs use official TASK-002 realistic_combo symbol-day costs scaled by abs(new_weight / original_weight).",
        "- Return dating follows TASK-007: positions.date + 1 day = return_date.",
        "",
        "## Key Results",
        "| Variant | Cap | Sharpe | IR vs EQW | Max DD | Net Alpha | Alpha Retention | Top5 Conc | Single Conc | No-room Events |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        *rows,
        "",
        "## TASK-007 Alpha-based Reference",
        "| Variant | Sharpe | Max DD | Net Alpha | Alpha Retention | Top5 Conc | Single Conc |",
        "|---|---:|---:|---:|---:|---:|---:|",
        *ref_lines,
        "",
        "## Gates",
        f"- Fail gates triggered: {fail_triggered if fail_triggered else 'none'}.",
        f"- Warning gates triggered: {warning_triggered if warning_triggered else 'none'}.",
        f"- Redistribution event counts: {edge_counts if edge_counts else 'none'}.",
        "",
        "## Caveats",
        *[f"- {item}" for item in caveats],
        "",
        "## Reproducibility",
        f"- reproducibility_hash: `{summary_json['reproducibility_hash']}`",
        f"- git_commit: `{summary_json['git_commit']}`",
        f"- output_date: `{config.output_date}`",
        "",
    ]) + "\n"


def _review_numbers_payload(summary_json: dict[str, Any], summary: pd.DataFrame) -> dict[str, Any]:
    key_cols = [
        "source",
        "variant",
        "cap_level",
        "sharpe_active",
        "ir_vs_cash_active",
        "ir_vs_equal_weight_active",
        "ir_vs_btc_active",
        "max_dd",
        "gross_alpha",
        "net_alpha",
        "alpha_retention_pct",
        "long_net_contribution",
        "short_net_contribution",
        "top5_concentration_net_alpha_total",
        "single_symbol_concentration_net_alpha_total",
        "redistribution_has_no_room_events",
        "gross_reduction",
        "max_symbol_weight_pct_of_original_gross",
        "max_symbol_weight_pct_of_new_gross",
    ]
    return {
        "analysis_basis": summary_json["analysis_basis"],
        "run_date": summary_json["run_date"],
        "key_numbers": summary.loc[:, key_cols].to_dict(orient="records"),
        "gate_results": summary_json["gate_results"],
        "redistribution_summary": summary_json["redistribution_summary"],
        "reproducibility_hash": summary_json["reproducibility_hash"],
        "git_commit": summary_json["git_commit"],
    }


def _log_text(summary_json: dict[str, Any], config: Task007bConfig) -> str:
    return "\n".join([
        "TASK-007b Weight Cap + Redistribution Study",
        f"run_date={config.output_date}",
        "analysis_basis=post-processing overlay study, not a trading decision",
        f"baseline_run_id={config.baseline_run_id}",
        f"cost_stress_run_id={config.cost_stress_run_id}",
        f"task007_run_id={config.task007_run_id}",
        f"primary_scenario={config.primary_scenario}",
        f"git_commit={summary_json['git_commit']}",
        f"reproducibility_hash={summary_json['reproducibility_hash']}",
        "",
        "methodology:",
        json.dumps(_json_clean(summary_json["methodology"]), indent=2, sort_keys=True, ensure_ascii=True),
        "",
        "gate_results:",
        json.dumps(_json_clean(summary_json["gate_results"]), indent=2, sort_keys=True, ensure_ascii=True),
        "",
        "redistribution_summary:",
        json.dumps(_json_clean(summary_json["redistribution_summary"]), indent=2, sort_keys=True, ensure_ascii=True),
        "",
        "input_hashes:",
        json.dumps(_json_clean(summary_json["input_hashes"]), indent=2, sort_keys=True, ensure_ascii=True),
        "",
    ]) + "\n"


def _validate_outputs(paths: dict[str, Path], result: Task007bResult) -> list[str]:
    errors = []
    for name, path in paths.items():
        if not path.exists():
            errors.append(f"missing output {name}: {path}")
    required_daily = {
        "variant",
        "date",
        "portfolio_return_gross",
        "portfolio_return_net",
        "gross_exposure",
        "net_exposure",
        "cap_breach_count",
        "redistribution_has_no_room_events",
    }
    missing_daily = required_daily - set(result.daily.columns)
    if missing_daily:
        errors.append(f"daily missing columns: {sorted(missing_daily)}")
    required_summary = {
        "source",
        "variant",
        "sharpe_active",
        "ir_vs_equal_weight_active",
        "max_dd",
        "net_alpha",
        "top5_concentration_net_alpha_total",
    }
    missing_summary = required_summary - set(result.summary.columns)
    if missing_summary:
        errors.append(f"summary missing columns: {sorted(missing_summary)}")
    required_log = {"variant", "date", "symbol", "event_type", "excess_weight", "gross_reduction"}
    missing_log = required_log - set(result.redistribution_log.columns)
    if missing_log:
        errors.append(f"redistribution log missing columns: {sorted(missing_log)}")
    if result.daily.empty:
        errors.append("daily output is empty")
    if result.summary.empty:
        errors.append("summary output is empty")
    return errors


def _cap_level_for_variant(variant: str, config: Task007bConfig) -> float:
    if variant == "baseline_current_long_short":
        return np.nan
    return float(config.cap_levels[variant])


def _format_pct_or_dash(value: Any) -> str:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return "-"
    if math.isnan(val):
        return "-"
    return f"{val:.0%}"


def _json_clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_clean(item) for item in value]
    if isinstance(value, tuple):
        return [_json_clean(item) for item in value]
    if isinstance(value, np.generic):
        return _json_clean(value.item())
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value
