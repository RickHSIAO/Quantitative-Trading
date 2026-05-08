"""Baseline Crypto OOS attribution report.

Runs the current baseline Crypto OOS backtest and writes attribution-only
reports. It does not modify strategy signals, parameters, costs, or sizing.
"""
from __future__ import annotations

import argparse
import copy
import csv
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from config import get_selected_assets
from src.backtester import run_silo_backtest
from src.database import get_all_symbols, load_prices
from src.indicators import compute_all_indicators
from src.strategies import apply_cross_asset_filters, generate_all_signals


DEFAULT_START = "2024-05-01"
DEFAULT_END = "2026-05-07"
EXPERIMENT_ID = "EXP-004"

OUTPUTS = {
    "strategy": "crypto_baseline_attribution_by_strategy.csv",
    "exit_reason": "crypto_baseline_attribution_by_exit_reason.csv",
    "year": "crypto_baseline_attribution_by_year.csv",
    "symbol": "crypto_baseline_attribution_by_symbol.csv",
    "holding_days": "crypto_baseline_attribution_by_holding_days.csv",
    "btc_regime": "crypto_baseline_attribution_by_btc_regime.csv",
    "conflicts": "crypto_baseline_attribution_conflicts.csv",
    "summary": "crypto_baseline_attribution_summary.md",
}

BASELINE_COST_OVERRIDES = {
    "BACKTEST_TP_AS_TAKER": False,
    "BACKTEST_SLIPPAGE_ON_TP": False,
    "BACKTEST_FUNDING_DAILY_PCT_BY_CLASS": {"Crypto": 0.0},
    "BACKTEST_EXTRA_SLIPPAGE_PCT_BY_CLASS": {"Crypto": 0.0},
    "BACKTEST_INTRABAR_CONFLICT_MODE": "tp_first",
}


def _deepcopy_attr(name: str) -> Any:
    return copy.deepcopy(getattr(config, name))


def _apply_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    saved = {name: _deepcopy_attr(name) for name in overrides if hasattr(config, name)}
    for name, value in overrides.items():
        if not hasattr(config, name):
            raise AttributeError(f"Unknown config override: {name}")
        setattr(config, name, copy.deepcopy(value))
    return saved


def _restore_overrides(saved: dict[str, Any]) -> None:
    for name, value in saved.items():
        setattr(config, name, value)


def _build_inputs() -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, pd.Series]], dict[str, str]]:
    assets = get_selected_assets(42)
    available = set(get_all_symbols())
    cryptos = [sym for sym in assets["cryptos"] if sym in available]
    type_map = {sym: "Crypto" for sym in cryptos}
    data: dict[str, pd.DataFrame] = {}
    signals: dict[str, dict[str, pd.Series]] = {}

    for sym in cryptos:
        df = load_prices(sym)
        if df is None or len(df) < config.EMA_PERIOD + 10:
            continue
        df = compute_all_indicators(df, include_vp=True)
        sigs = generate_all_signals(df, asset_type="Crypto", moat_tf_only=True)
        data[sym] = df
        signals[sym] = sigs

    if not data:
        raise RuntimeError("No Crypto data available. Run `python main.py update` first.")
    return data, signals, type_map


def _slice_inputs(base: tuple[dict, dict, dict],
                  start: str | None,
                  end: str | None) -> tuple[dict, dict, dict]:
    base_data, base_signals, base_type_map = base
    start_ts = pd.Timestamp(start) if start else None
    end_ts = pd.Timestamp(end) if end else None
    data: dict[str, pd.DataFrame] = {}
    signals: dict[str, dict[str, pd.Series]] = {}
    type_map = dict(base_type_map)

    for sym, df in base_data.items():
        mask = pd.Series(True, index=df.index)
        if start_ts is not None:
            mask &= df.index >= start_ts
        if end_ts is not None:
            mask &= df.index <= end_ts
        sliced = df.loc[mask].copy()
        if sliced.empty:
            continue
        data[sym] = sliced
        signals[sym] = {
            key: series.loc[mask].copy()
            for key, series in base_signals[sym].items()
        }

    apply_cross_asset_filters(data, signals, type_map)
    return data, signals, type_map


def _run_baseline(start: str, end: str) -> tuple[list[Any], dict[str, Any], dict[str, pd.DataFrame], list[dict]]:
    base = _build_inputs()
    data, signals, type_map = _slice_inputs(base, start, end)
    profile = copy.deepcopy(config.STRATEGY_PROFILES["Crypto"])
    saved = _apply_overrides(BASELINE_COST_OVERRIDES)
    try:
        trades, results = run_silo_backtest(
            data,
            signals,
            type_map,
            {"Crypto": ["Crypto"]},
            config.SILO_CAPITAL,
            {"Crypto": profile},
        )
    finally:
        _restore_overrides(saved)

    crypto = results["Crypto"]
    return list(trades), dict(crypto["metrics"]), data, list(crypto["equity_curve"])


def _strategy_label(strategy: str) -> str:
    mapping = {
        "trend": "Supertrend",
        "vp": "VP POC",
        "bb": "Bollinger",
        "combined": "combined/overlap",
    }
    return mapping.get(strategy or "", "unknown")


def _holding_bucket(days: float) -> str:
    if days <= 3:
        return "0-3 days"
    if days <= 7:
        return "4-7 days"
    if days <= 14:
        return "8-14 days"
    if days <= 30:
        return "15-30 days"
    return ">30 days"


def _shifted_signal(signals: pd.Series, dt: pd.Timestamp) -> int:
    if dt not in signals.index:
        return 0
    loc = signals.index.get_loc(dt)
    if isinstance(loc, slice) or isinstance(loc, np.ndarray):
        return 0
    if loc <= 0:
        return 0
    return int(signals.iloc[loc - 1])


def _classify_exit(trade: Any, data: dict[str, pd.DataFrame],
                   signals: dict[str, dict[str, pd.Series]]) -> str:
    reason = str(getattr(trade, "exit_reason", "") or "").lower()
    if "tsl" in reason or "trailing" in reason:
        return "trailing stop"
    if "tp" in reason or "take_profit" in reason:
        return "TP"
    if "sl" in reason or "stop_loss" in reason:
        return "SL"

    sym = getattr(trade, "symbol", "")
    exit_dt = pd.Timestamp(getattr(trade, "exit_date", ""))
    df = data.get(sym)
    if df is not None and not df.empty and exit_dt == df.index[-1]:
        return "end of backtest"

    max_hold = getattr(config, "MAX_HOLD_DAYS_BY_CLASS", {}).get(
        "Crypto",
        getattr(config, "MAX_HOLD_DAYS", 0),
    )
    holding_days = int(getattr(trade, "holding_days", 0) or 0)
    if max_hold and holding_days >= max_hold:
        return "max_hold"

    sigs = signals.get(sym, {})
    combined = sigs.get("combined")
    if combined is not None:
        shifted = _shifted_signal(combined, exit_dt)
        if shifted != 0 and shifted != int(getattr(trade, "direction", 0)):
            return "reverse signal"

    if "bb" in reason:
        return "other"
    return "other"


def _btc_regime_for_entry(trade: Any, data: dict[str, pd.DataFrame]) -> str:
    btc_sym = getattr(config, "CRYPTO_MARKET_SYMBOL", "BYBIT:BTCUSDT.P")
    btc = data.get(btc_sym)
    if btc is None or btc.empty or "ema200" not in btc.columns:
        return "unknown"
    entry_dt = pd.Timestamp(getattr(trade, "entry_date", ""))
    if entry_dt not in btc.index:
        loc = btc.index.searchsorted(entry_dt)
        if loc <= 0:
            return "unknown"
        entry_dt = btc.index[loc - 1]
    row = btc.loc[entry_dt]
    if float(row["Close"]) >= float(row["ema200"]):
        return "BTC above EMA200"
    return "BTC below EMA200"


def _has_exit_bar_conflict(trade: Any, data: dict[str, pd.DataFrame]) -> bool:
    df = data.get(getattr(trade, "symbol", ""))
    if df is None:
        return False
    exit_dt = pd.Timestamp(getattr(trade, "exit_date", ""))
    if exit_dt not in df.index:
        return False
    row = df.loc[exit_dt]
    hi = float(row["High"])
    lo = float(row["Low"])
    direction = int(getattr(trade, "direction", 0))
    if direction == 1:
        tp_hit = hi >= float(getattr(trade, "take_profit", np.nan))
        sl_hit = lo <= float(getattr(trade, "stop_loss", np.nan))
    else:
        tp_hit = lo <= float(getattr(trade, "take_profit", np.nan))
        sl_hit = hi >= float(getattr(trade, "stop_loss", np.nan))
    return bool(tp_hit and sl_hit)


def _trade_frame(trades: list[Any], data: dict[str, pd.DataFrame],
                 signals: dict[str, dict[str, pd.Series]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for trade in trades:
        if getattr(trade, "pnl", None) is None:
            continue
        holding_days = int(getattr(trade, "holding_days", 0) or 0)
        rows.append({
            "symbol": getattr(trade, "symbol", "unknown"),
            "strategy": getattr(trade, "strategy", "unknown") or "unknown",
            "signal_source": _strategy_label(getattr(trade, "strategy", "unknown")),
            "direction": int(getattr(trade, "direction", 0) or 0),
            "entry_date": pd.Timestamp(getattr(trade, "entry_date")),
            "exit_date": pd.Timestamp(getattr(trade, "exit_date")),
            "exit_year": int(pd.Timestamp(getattr(trade, "exit_date")).year),
            "exit_reason_group": _classify_exit(trade, data, signals),
            "holding_days": holding_days,
            "holding_bucket": _holding_bucket(holding_days),
            "btc_regime": _btc_regime_for_entry(trade, data),
            "intrabar_conflict": _has_exit_bar_conflict(trade, data),
            "pnl": float(getattr(trade, "pnl", 0.0) or 0.0),
            "r_multiple": float(getattr(trade, "r_multiple", 0.0) or 0.0),
            "return_pct": float(getattr(trade, "return_pct", 0.0) or 0.0),
            "risk_usd": float(getattr(trade, "risk_usd", 0.0) or 0.0),
            "entry_price": float(getattr(trade, "entry_price", 0.0) or 0.0),
            "exit_price": float(getattr(trade, "exit_price", 0.0) or 0.0),
            "stop_loss": float(getattr(trade, "stop_loss", 0.0) or 0.0),
            "take_profit": float(getattr(trade, "take_profit", 0.0) or 0.0),
            "raw_exit_reason": getattr(trade, "exit_reason", "") or "",
        })
    return pd.DataFrame(rows)


def _profit_factor(pnls: pd.Series) -> float:
    wins = pnls[pnls > 0].sum()
    losses = -pnls[pnls < 0].sum()
    if losses <= 0:
        return float("inf") if wins > 0 else 0.0
    return float(wins / losses)


def _group_metrics(df: pd.DataFrame, group_col: str, initial_capital: float) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for label, group in df.groupby(group_col, dropna=False):
        pnls = group["pnl"]
        rs = group["r_multiple"]
        trades = len(group)
        rows.append({
            group_col: label,
            "trades": trades,
            "win_rate": float((pnls > 0).mean()) if trades else 0.0,
            "profit_factor": _profit_factor(pnls),
            "total_R": float(rs.sum()),
            "avg_R": float(rs.mean()) if trades else 0.0,
            "median_R": float(rs.median()) if trades else 0.0,
            "max_loss_R": float(rs.min()) if trades else 0.0,
            "max_win_R": float(rs.max()) if trades else 0.0,
            "total_return_contribution": float(pnls.sum() / initial_capital * 100.0),
            "total_pnl": float(pnls.sum()),
            "average_holding_days": float(group["holding_days"].mean()) if trades else 0.0,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("total_return_contribution", ascending=False)
    return out


def _ensure_categories(df: pd.DataFrame, group_col: str, categories: list[Any]) -> pd.DataFrame:
    existing = set(df[group_col].tolist()) if not df.empty else set()
    rows = []
    for category in categories:
        if category in existing:
            continue
        rows.append({
            group_col: category,
            "trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_R": 0.0,
            "avg_R": 0.0,
            "median_R": 0.0,
            "max_loss_R": 0.0,
            "max_win_R": 0.0,
            "total_return_contribution": 0.0,
            "total_pnl": 0.0,
            "average_holding_days": 0.0,
        })
    if rows:
        df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
    order = {category: idx for idx, category in enumerate(categories)}
    df["_category_order"] = df[group_col].map(order).fillna(len(order))
    return df.sort_values(["_category_order", "total_return_contribution"], ascending=[True, False]).drop(columns=["_category_order"])


def _global_mdd_window(equity_curve: list[dict]) -> tuple[pd.Timestamp | None, pd.Timestamp | None, float]:
    if not equity_curve:
        return None, None, 0.0
    eq = pd.DataFrame(equity_curve)
    eq["date"] = pd.to_datetime(eq["date"])
    eq["peak"] = eq["capital"].cummax()
    eq["drawdown"] = eq["capital"] - eq["peak"]
    trough_idx = eq["drawdown"].idxmin()
    if pd.isna(trough_idx):
        return None, None, 0.0
    trough_date = pd.Timestamp(eq.loc[trough_idx, "date"])
    peak_slice = eq.loc[:trough_idx]
    peak_idx = peak_slice["capital"].idxmax()
    peak_date = pd.Timestamp(eq.loc[peak_idx, "date"])
    dd_usd = float(eq.loc[trough_idx, "drawdown"])
    return peak_date, trough_date, dd_usd


def _symbol_metrics(df: pd.DataFrame, initial_capital: float,
                    equity_curve: list[dict]) -> pd.DataFrame:
    out = _group_metrics(df, "symbol", initial_capital)
    peak_date, trough_date, _ = _global_mdd_window(equity_curve)
    mdd_map: dict[str, float] = {}
    if peak_date is not None and trough_date is not None:
        mask = (df["exit_date"] > peak_date) & (df["exit_date"] <= trough_date)
        for symbol, group in df.loc[mask].groupby("symbol"):
            mdd_map[symbol] = float(group["pnl"].sum())
    if not out.empty:
        out["mdd_contribution_usd"] = out["symbol"].map(mdd_map).fillna(0.0)
        out["mdd_contribution_pct"] = out["mdd_contribution_usd"] / initial_capital * 100.0
        out["rank_by_total_R"] = out["total_R"].rank(ascending=False, method="first").astype(int)
    return out


def _round_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.select_dtypes(include=["float64", "float32"]).columns:
        out[col] = out[col].round(6)
    return out


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _round_frame(df).to_csv(path, index=False, encoding="utf-8")


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def _fmt_num(value: float) -> str:
    return f"{value:.3f}"


def _top_bottom_symbols(symbol_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    top = symbol_df.sort_values("total_R", ascending=False).head(10)
    bottom = symbol_df.sort_values("total_R", ascending=True).head(10)
    return top, bottom


def _md_table(df: pd.DataFrame, cols: list[str], max_rows: int | None = None) -> str:
    subset = df.loc[:, cols].copy()
    if max_rows is not None:
        subset = subset.head(max_rows)
    if subset.empty:
        return "_No data._\n"
    headers = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = []
    for _, row in subset.iterrows():
        vals = []
        for col in cols:
            value = row[col]
            if col in ("trades", "exit_year") and not pd.isna(value):
                vals.append(str(int(value)))
            elif isinstance(value, float):
                vals.append(f"{value:.3f}")
            else:
                vals.append(str(value))
        body.append("| " + " | ".join(vals) + " |")
    return "\n".join([headers, sep, *body]) + "\n"


def _write_summary(path: Path,
                   metrics: dict[str, Any],
                   grouped: dict[str, pd.DataFrame],
                   symbol_df: pd.DataFrame,
                   mdd_window: tuple[pd.Timestamp | None, pd.Timestamp | None, float]) -> None:
    by_strategy = grouped["strategy"].sort_values("total_R", ascending=False)
    by_exit = grouped["exit_reason"].sort_values("total_R", ascending=False)
    by_year = grouped["year"].sort_values("exit_year")
    by_btc = grouped["btc_regime"].sort_values("total_R", ascending=False)
    conflicts = grouped["conflicts"].sort_values("intrabar_conflict", ascending=False)
    top, bottom = _top_bottom_symbols(symbol_df)
    peak_date, trough_date, dd_usd = mdd_window

    main_source = by_strategy.iloc[0]
    main_exit_profit = by_exit.iloc[0]
    main_loss_exit = by_exit.sort_values("total_R", ascending=True).iloc[0]
    main_loss_symbol = symbol_df.sort_values("total_R", ascending=True).iloc[0]
    positive_symbol_r = symbol_df.loc[symbol_df["total_R"] > 0, "total_R"].sum()
    top10_r_share = top["total_R"].sum() / max(positive_symbol_r, 1e-9) * 100.0
    year_r_abs = by_year["total_R"].abs().sum()
    top_year_share = by_year["total_R"].abs().max() / max(year_r_abs, 1e-9) * 100.0
    btc_above = by_btc[by_btc["btc_regime"] == "BTC above EMA200"]
    btc_above_r = float(btc_above["total_R"].iloc[0]) if not btc_above.empty else 0.0

    lines = [
        f"# {EXPERIMENT_ID} Baseline Attribution Summary",
        "",
        "## Scope",
        "",
        "- Period: Crypto OOS 2024-05-01 to 2026-05-07.",
        "- Changed: attribution script and output reports only.",
        "- Not changed: strategy signals, strategy parameters, cost model, position sizing, asset universe.",
        "- BTC regime is classified at trade entry date.",
        "- Intrabar conflict flag follows EXP-002 logic: exit bar high/low touched both TP and SL using recorded TP and final stop.",
        "",
        "## Baseline Metrics",
        "",
        f"- Total return: {_fmt_pct(metrics.get('total_return_pct', 0.0))}",
        f"- Annual return: {_fmt_pct(metrics.get('annual_return_pct', 0.0))}",
        f"- MDD: {_fmt_pct(metrics.get('max_drawdown_pct', 0.0))}",
        f"- PF: {_fmt_num(metrics.get('profit_factor', 0.0))}",
        f"- Sharpe: {_fmt_num(metrics.get('sharpe_ratio', 0.0))}",
        f"- Calmar: {_fmt_num(metrics.get('calmar_ratio', 0.0))}",
        f"- Win rate: {_fmt_pct(metrics.get('win_rate', 0.0) * 100)}",
        f"- Avg R: {_fmt_num(metrics.get('avg_r_multiple', 0.0))}",
        f"- Trades: {int(metrics.get('total_trades', 0))}",
        "",
        "## By Strategy",
        "",
        _md_table(by_strategy, ["signal_source", "trades", "win_rate", "profit_factor", "total_R", "avg_R", "total_return_contribution"]),
        "## By Exit Reason",
        "",
        _md_table(by_exit, ["exit_reason_group", "trades", "win_rate", "profit_factor", "total_R", "avg_R", "total_return_contribution"]),
        "## By Year",
        "",
        _md_table(by_year, ["exit_year", "trades", "win_rate", "profit_factor", "total_R", "avg_R", "total_return_contribution"]),
        "## By BTC Regime",
        "",
        _md_table(by_btc, ["btc_regime", "trades", "win_rate", "profit_factor", "total_R", "avg_R", "total_return_contribution"]),
        "## Intrabar Conflicts",
        "",
        _md_table(conflicts, ["intrabar_conflict", "trades", "win_rate", "profit_factor", "total_R", "avg_R", "total_return_contribution"]),
        "## Top 10 Symbols",
        "",
        _md_table(top, ["symbol", "trades", "win_rate", "profit_factor", "total_R", "avg_R", "mdd_contribution_pct"]),
        "## Bottom 10 Symbols",
        "",
        _md_table(bottom, ["symbol", "trades", "win_rate", "profit_factor", "total_R", "avg_R", "mdd_contribution_pct"]),
        "## Answers",
        "",
        f"1. Baseline 主要獲利來源是 `{main_source['signal_source']}` 訊號與 `{main_exit_profit['exit_reason_group']}` 出場。"
        f"{main_source['signal_source']} total R = {main_source['total_R']:.2f}；"
        f"{main_exit_profit['exit_reason_group']} total R = {main_exit_profit['total_R']:.2f}。BTC above EMA200 交易 total R = {btc_above_r:.2f}，"
        "顯示主要 edge 偏向 BTC 多頭環境中的趨勢/波段延伸。",
        f"2. Baseline 主要虧損來源是 `{main_loss_exit['exit_reason_group']}` 出場，total R = {main_loss_exit['total_R']:.2f}；"
        f"幣種層面最差是 `{main_loss_symbol['symbol']}`，total R = {main_loss_symbol['total_R']:.2f}。",
        f"3. 有集中風險。前 10 名幣種貢獻約 {top10_r_share:.1f}% 的正向 symbol total R；"
        f"單一年份最大絕對貢獻占比約 {top_year_share:.1f}%。2024 total R 為負，2025/2026 才是主要獲利年份。",
        "4. 應保留：baseline 內的 Supertrend 標籤、BTC regime/moat、symbol rolling winrate、geometric RR。"
        "Supertrend 單獨 ablation 失效，但在完整 baseline 的風控與濾網框架內是主要正貢獻來源。",
        "5. 應砍掉或降權：Bollinger 在 baseline 內樣本太少且 total R 為負；VP POC 雖有正報酬貢獻但 total R 幾乎打平，"
        "不得視為獨立 edge。EMA score、raw VP POC、raw Supertrend 作為獨立模組仍維持 EXP-003 的淘汰/降權判斷。",
        "6. 下一個最值得做的實驗：point-in-time universe 測試。理由是 top symbol 貢獻高度集中，且包含較新上市/高動能幣，"
        "必須先排除資產池事後選樣與上市存活偏誤，再做任何參數調整。",
        "",
        "## MDD Window",
        "",
        f"- Peak date: {peak_date.date() if peak_date is not None else 'NA'}",
        f"- Trough date: {trough_date.date() if trough_date is not None else 'NA'}",
        f"- Drawdown USD: {dd_usd:.2f}",
        "",
        "## Conclusion",
        "",
        "需要更多測試。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Crypto baseline attribution reports.")
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    trades, metrics, data, equity_curve = _run_baseline(args.start_date, args.end_date)
    # Rebuild sliced signals for reverse-signal exit attribution.
    base = _build_inputs()
    sliced_data, signals, _ = _slice_inputs(base, args.start_date, args.end_date)
    trade_df = _trade_frame(trades, sliced_data, signals)
    initial_capital = float(metrics.get("initial_capital", config.SILO_CAPITAL))
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    grouped = {
        "strategy": _ensure_categories(
            _group_metrics(trade_df, "signal_source", initial_capital),
            "signal_source",
            ["Supertrend", "VP POC", "Bollinger", "combined/overlap", "unknown"],
        ),
        "exit_reason": _ensure_categories(
            _group_metrics(trade_df, "exit_reason_group", initial_capital),
            "exit_reason_group",
            ["TP", "SL", "max_hold", "trailing stop", "reverse signal", "end of backtest", "other"],
        ),
        "year": _group_metrics(trade_df[trade_df["exit_year"].isin([2024, 2025, 2026])], "exit_year", initial_capital),
        "holding_days": _group_metrics(trade_df, "holding_bucket", initial_capital),
        "btc_regime": _group_metrics(trade_df, "btc_regime", initial_capital),
        "conflicts": _group_metrics(trade_df, "intrabar_conflict", initial_capital),
    }
    symbol_df = _symbol_metrics(trade_df, initial_capital, equity_curve)
    grouped["symbol"] = symbol_df

    _write_csv(grouped["strategy"], out_dir / OUTPUTS["strategy"])
    _write_csv(grouped["exit_reason"], out_dir / OUTPUTS["exit_reason"])
    _write_csv(grouped["year"], out_dir / OUTPUTS["year"])
    _write_csv(grouped["symbol"], out_dir / OUTPUTS["symbol"])
    _write_csv(grouped["holding_days"], out_dir / OUTPUTS["holding_days"])
    _write_csv(grouped["btc_regime"], out_dir / OUTPUTS["btc_regime"])
    _write_csv(grouped["conflicts"], out_dir / OUTPUTS["conflicts"])

    mdd_window = _global_mdd_window(equity_curve)
    _write_summary(out_dir / OUTPUTS["summary"], metrics, grouped, symbol_df, mdd_window)

    print("\nCrypto baseline attribution")
    print(
        f"return {metrics.get('total_return_pct', 0.0):.2f}%  "
        f"PF {metrics.get('profit_factor', 0.0):.3f}  "
        f"Sharpe {metrics.get('sharpe_ratio', 0.0):.3f}  "
        f"Calmar {metrics.get('calmar_ratio', 0.0):.3f}  "
        f"MDD {metrics.get('max_drawdown_pct', 0.0):.2f}%  "
        f"trades {metrics.get('total_trades', 0)}"
    )
    print("\nSaved reports:")
    for name in OUTPUTS.values():
        print(f"- {out_dir / name}")


if __name__ == "__main__":
    main()
