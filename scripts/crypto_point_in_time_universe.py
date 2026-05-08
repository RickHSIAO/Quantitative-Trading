"""EXP-005 point-in-time Crypto top-100 universe test.

The script intentionally separates universe construction from strategy logic.
It can run the current-biased benchmark from local OHLCV/config data, and it
can run static/rolling point-in-time universes when a historical market-cap
ranking CSV is supplied.
"""
from __future__ import annotations

import argparse
import copy
import csv
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from config import get_selected_assets
from src.backtester import run_silo_backtest
from src.database import get_all_symbols, get_registry, load_prices
from src.indicators import compute_all_indicators
from src.strategies import apply_cross_asset_filters, generate_all_signals


EXP_ID = "EXP-005"
DEFAULT_START = "2024-05-01"
DEFAULT_END = "2026-05-07"
DEFAULT_RANKING_CSV = "data/crypto_market_cap_rankings.csv"

STABLE_BASES = {
    "USDT", "USDC", "DAI", "TUSD", "FDUSD", "USDE", "USDD", "PYUSD",
    "FRAX", "LUSD", "USD1", "USDP", "GUSD", "BUSD", "EURS", "EURC",
}
WRAPPED_BASES = {
    "WBTC", "WETH", "WBNB", "WSTETH", "STETH", "RETH", "CBETH", "WEETH",
    "WAVAX", "WSOL", "WMATIC", "WFTM",
}
LEVERAGED_SUFFIXES = (
    "2L", "2S", "3L", "3S", "4L", "4S", "5L", "5S",
    "UP", "DOWN", "BULL", "BEAR",
)

BASELINE_COST_OVERRIDES = {
    "BACKTEST_TP_AS_TAKER": False,
    "BACKTEST_SLIPPAGE_ON_TP": False,
    "BACKTEST_FUNDING_DAILY_PCT_BY_CLASS": {"Crypto": 0.0},
    "BACKTEST_EXTRA_SLIPPAGE_PCT_BY_CLASS": {"Crypto": 0.0},
    "BACKTEST_INTRABAR_CONFLICT_MODE": "tp_first",
}


@dataclass(frozen=True)
class UniverseSelection:
    mode: str
    rebalance_date: str
    effective_start: str
    effective_end: str
    symbols: list[str]
    source: str
    status: str
    notes: str
    rejected: list[dict[str, Any]]


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


def _base_from_symbol(symbol: str) -> str:
    s = str(symbol).upper()
    if s.startswith("BYBIT:"):
        s = s[6:]
    if s.endswith(".P"):
        s = s[:-2]
    for quote in ("USDT", "USDC", "USD", "PERP"):
        if s.endswith(quote):
            return s[:-len(quote)]
    return s


def _to_bybit_symbol(value: str) -> str:
    s = str(value).strip().upper()
    if not s:
        return s
    if s.startswith("BYBIT:") and s.endswith(".P"):
        return s
    if s.endswith("USDT"):
        return f"BYBIT:{s}.P"
    return f"BYBIT:{s}USDT.P"


def _is_excluded_name(symbol: str) -> tuple[bool, str]:
    base = _base_from_symbol(symbol)
    if base in STABLE_BASES:
        return True, "stablecoin"
    if base in WRAPPED_BASES or base.startswith("W") and base[1:] in {"BTC", "ETH", "BNB", "SOL", "AVAX"}:
        return True, "wrapped_token"
    if base.endswith(LEVERAGED_SUFFIXES):
        return True, "leveraged_token"
    return False, ""


def _has_enough_ohlcv(df: pd.DataFrame, as_of: pd.Timestamp,
                      min_history_days: int,
                      min_90d_dollar_volume: float) -> tuple[bool, str]:
    hist = df.loc[df.index <= as_of].copy()
    if len(hist) < min_history_days:
        return False, "ohlcv_lt_180d"
    lookback = hist.loc[hist.index > as_of - pd.Timedelta(days=90)]
    if len(lookback) < 30:
        return False, "ohlcv_90d_window_too_sparse"
    dollar_vol = (lookback["Close"].astype(float) * lookback["Volume"].fillna(0).astype(float)).median()
    if not np.isfinite(dollar_vol) or dollar_vol <= min_90d_dollar_volume:
        return False, "volume_90d_below_threshold"
    return True, ""


def _load_all_crypto_data() -> dict[str, pd.DataFrame]:
    registry = get_registry()
    symbols = registry.loc[registry["asset_type"].eq("Crypto"), "symbol"].tolist()
    data: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = load_prices(sym)
        if df is None or df.empty:
            continue
        data[sym] = df
    return data


def _build_signals(data: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, pd.Series]], dict[str, str]]:
    prepared: dict[str, pd.DataFrame] = {}
    signals: dict[str, dict[str, pd.Series]] = {}
    type_map: dict[str, str] = {}
    for sym, raw in data.items():
        if raw is None or len(raw) < config.EMA_PERIOD + 10:
            continue
        df = compute_all_indicators(raw.copy(), include_vp=True)
        sigs = generate_all_signals(df, asset_type="Crypto", moat_tf_only=True)
        prepared[sym] = df
        signals[sym] = sigs
        type_map[sym] = "Crypto"
    return prepared, signals, type_map


def _slice_and_mask(data: dict[str, pd.DataFrame],
                    signals: dict[str, dict[str, pd.Series]],
                    type_map: dict[str, str],
                    start: str,
                    end: str,
                    allowed_by_date: dict[pd.Timestamp, set[str]]) -> tuple[dict, dict, dict]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    sliced_data: dict[str, pd.DataFrame] = {}
    sliced_signals: dict[str, dict[str, pd.Series]] = {}
    sliced_type_map = dict(type_map)

    for sym, df in data.items():
        mask = (df.index >= start_ts) & (df.index <= end_ts)
        if not mask.any():
            continue
        sliced = df.loc[mask].copy()
        sigs = {
            key: series.loc[mask].copy()
            for key, series in signals[sym].items()
        }
        for dt in sliced.index:
            allowed = allowed_by_date.get(pd.Timestamp(dt), set())
            if sym in allowed:
                continue
            for key in ("trend", "vp", "bb", "combined", "score", "ema_bull", "ema_bear"):
                if key in sigs:
                    sigs[key].loc[dt] = 0
        sliced_data[sym] = sliced
        sliced_signals[sym] = sigs

    apply_cross_asset_filters(sliced_data, sliced_signals, sliced_type_map)
    return sliced_data, sliced_signals, sliced_type_map


def _date_allowed_static(start: str, end: str, symbols: list[str]) -> dict[pd.Timestamp, set[str]]:
    dates = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="D")
    allowed = set(symbols)
    return {pd.Timestamp(dt): allowed for dt in dates}


def _date_allowed_rolling(start: str, end: str, selections: list[UniverseSelection]) -> dict[pd.Timestamp, set[str]]:
    mapping: dict[pd.Timestamp, set[str]] = {}
    for sel in selections:
        dates = pd.date_range(pd.Timestamp(sel.effective_start), pd.Timestamp(sel.effective_end), freq="D")
        allowed = set(sel.symbols)
        for dt in dates:
            if pd.Timestamp(start) <= dt <= pd.Timestamp(end):
                mapping[pd.Timestamp(dt)] = allowed
    return mapping


def _run_universe(data: dict[str, pd.DataFrame],
                  signals: dict[str, dict[str, pd.Series]],
                  type_map: dict[str, str],
                  start: str,
                  end: str,
                  allowed_by_date: dict[pd.Timestamp, set[str]]) -> tuple[list[Any], dict[str, Any]]:
    sliced_data, sliced_signals, sliced_type_map = _slice_and_mask(
        data, signals, type_map, start, end, allowed_by_date,
    )
    profile = copy.deepcopy(config.STRATEGY_PROFILES["Crypto"])
    saved = _apply_overrides(BASELINE_COST_OVERRIDES)
    try:
        trades, results = run_silo_backtest(
            sliced_data,
            sliced_signals,
            sliced_type_map,
            {"Crypto": ["Crypto"]},
            config.SILO_CAPITAL,
            {"Crypto": profile},
        )
    finally:
        _restore_overrides(saved)
    return list(trades), dict(results["Crypto"]["metrics"])


def _current_biased_symbols(data: dict[str, pd.DataFrame],
                            start: str,
                            end: str,
                            min_history_days: int,
                            min_90d_dollar_volume: float) -> UniverseSelection:
    configured = get_selected_assets(42)["cryptos"]
    available = set(get_all_symbols())
    selected: list[str] = []
    rejected: list[dict[str, Any]] = []
    as_of = pd.Timestamp(end)
    for sym in configured:
        if sym not in available or sym not in data:
            rejected.append({"symbol": sym, "reason": "not_in_local_db"})
            continue
        excluded, reason = _is_excluded_name(sym)
        if excluded:
            rejected.append({"symbol": sym, "reason": reason})
            continue
        ok, reason = _has_enough_ohlcv(data[sym], as_of, min_history_days, min_90d_dollar_volume)
        if not ok:
            rejected.append({"symbol": sym, "reason": reason})
            continue
        selected.append(sym)
    return UniverseSelection(
        mode="current_top100_bias_check",
        rebalance_date=end,
        effective_start=start,
        effective_end=end,
        symbols=selected[:100],
        source="current config/current local database; biased benchmark, not true current market-cap top100",
        status="biased_benchmark",
        notes="Uses symbols known in current config/DB and therefore can include future-listed or later-selected assets.",
        rejected=rejected,
    )


def _load_rankings(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return _load_rankings_from_sqlite()
    df = pd.read_csv(path)
    lower = {c.lower(): c for c in df.columns}
    required = {"date", "rank"}
    if "symbol" not in lower and "base" not in lower and "coin" not in lower:
        raise ValueError("Ranking CSV needs one of: symbol, base, coin")
    if not required.issubset(lower):
        raise ValueError("Ranking CSV needs date and rank columns")
    sym_col = lower.get("symbol") or lower.get("base") or lower.get("coin")
    out = pd.DataFrame({
        "date": pd.to_datetime(df[lower["date"]]),
        "rank": pd.to_numeric(df[lower["rank"]], errors="coerce"),
        "symbol": df[sym_col].map(_to_bybit_symbol),
    })
    if "market_cap" in lower:
        out["market_cap"] = pd.to_numeric(df[lower["market_cap"]], errors="coerce")
    return out.dropna(subset=["date", "rank", "symbol"]).sort_values(["date", "rank"])


def _load_rankings_from_sqlite() -> pd.DataFrame | None:
    conn = sqlite3.connect(config.DB_PATH)
    try:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crypto_market_cap_rankings'"
        ).fetchone()
        if exists is None:
            return None
        df = pd.read_sql_query(
            """
            SELECT snapshot_date AS date, rank, symbol
            FROM crypto_market_cap_rankings
            WHERE market_cap IS NOT NULL
              AND COALESCE(is_stablecoin, 0) = 0
              AND COALESCE(is_wrapped, 0) = 0
              AND COALESCE(is_leveraged, 0) = 0
            ORDER BY snapshot_date, rank
            """,
            conn,
        )
    finally:
        conn.close()
    if df.empty:
        return None
    return pd.DataFrame({
        "date": pd.to_datetime(df["date"]),
        "rank": pd.to_numeric(df["rank"], errors="coerce"),
        "symbol": df["symbol"].map(_to_bybit_symbol),
    }).dropna(subset=["date", "rank", "symbol"]).sort_values(["date", "rank"])


def _select_from_rankings(mode: str,
                          rankings: pd.DataFrame | None,
                          data: dict[str, pd.DataFrame],
                          as_of: str,
                          effective_start: str,
                          effective_end: str,
                          min_history_days: int,
                          min_90d_dollar_volume: float) -> UniverseSelection:
    if rankings is None:
        return UniverseSelection(
            mode=mode,
            rebalance_date=as_of,
            effective_start=effective_start,
            effective_end=effective_end,
            symbols=[],
            source=DEFAULT_RANKING_CSV,
            status="missing_market_cap_history",
            notes="No historical market-cap ranking CSV found; PIT universe cannot be constructed without external data.",
            rejected=[],
        )
    as_of_ts = pd.Timestamp(as_of)
    known = rankings.loc[rankings["date"] <= as_of_ts].copy()
    if known.empty:
        return UniverseSelection(
            mode=mode,
            rebalance_date=as_of,
            effective_start=effective_start,
            effective_end=effective_end,
            symbols=[],
            source="historical market-cap ranking CSV",
            status="no_ranking_snapshot_before_rebalance",
            notes=f"No ranking rows available on or before {as_of}.",
            rejected=[],
        )
    snapshot_date = known["date"].max()
    snapshot = known.loc[known["date"].eq(snapshot_date)].sort_values("rank")
    selected: list[str] = []
    rejected: list[dict[str, Any]] = []
    for _, row in snapshot.iterrows():
        sym = str(row["symbol"])
        excluded, reason = _is_excluded_name(sym)
        if excluded:
            rejected.append({"symbol": sym, "reason": reason, "rank": row["rank"]})
            continue
        if sym not in data:
            rejected.append({"symbol": sym, "reason": "not_in_local_ohlcv", "rank": row["rank"]})
            continue
        ok, reason = _has_enough_ohlcv(data[sym], as_of_ts, min_history_days, min_90d_dollar_volume)
        if not ok:
            rejected.append({"symbol": sym, "reason": reason, "rank": row["rank"]})
            continue
        selected.append(sym)
        if len(selected) >= 100:
            break
    return UniverseSelection(
        mode=mode,
        rebalance_date=as_of,
        effective_start=effective_start,
        effective_end=effective_end,
        symbols=selected,
        source=f"historical market-cap ranking CSV snapshot={snapshot_date.date()}",
        status="ok" if selected else "empty_after_filters",
        notes=f"Selected {len(selected)} symbols from PIT ranking snapshot {snapshot_date.date()}.",
        rejected=rejected,
    )


def _quarter_selections(rankings: pd.DataFrame | None,
                        data: dict[str, pd.DataFrame],
                        start: str,
                        end: str,
                        min_history_days: int,
                        min_90d_dollar_volume: float) -> list[UniverseSelection]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    quarter_starts = pd.date_range(start_ts, end_ts, freq="QS")
    if start_ts not in quarter_starts:
        quarter_starts = pd.DatetimeIndex([start_ts]).append(quarter_starts[quarter_starts > start_ts])
    selections: list[UniverseSelection] = []
    for idx, q_start in enumerate(quarter_starts):
        q_end = (quarter_starts[idx + 1] - pd.Timedelta(days=1)) if idx + 1 < len(quarter_starts) else end_ts
        q_end = min(q_end, end_ts)
        as_of = (q_start - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        selections.append(_select_from_rankings(
            "rolling_pit_top100_quarterly",
            rankings,
            data,
            as_of,
            q_start.strftime("%Y-%m-%d"),
            q_end.strftime("%Y-%m-%d"),
            min_history_days,
            min_90d_dollar_volume,
        ))
    return selections


def _symbol_contributors(trades: list[Any], n: int = 10) -> tuple[str, str, int]:
    closed = [t for t in trades if getattr(t, "pnl", None) is not None]
    if not closed:
        return "", "", 0
    rows = pd.DataFrame([{
        "symbol": t.symbol,
        "pnl": float(t.pnl or 0.0),
        "r": float(t.r_multiple or 0.0),
    } for t in closed])
    grouped = rows.groupby("symbol", as_index=False).agg(total_pnl=("pnl", "sum"), total_R=("r", "sum"))
    top = grouped.sort_values("total_pnl", ascending=False).head(n)
    worst = grouped.sort_values("total_pnl", ascending=True).head(n)
    return (
        ";".join(f"{r.symbol}:{r.total_pnl:.2f}" for r in top.itertuples()),
        ";".join(f"{r.symbol}:{r.total_pnl:.2f}" for r in worst.itertuples()),
        int(grouped["symbol"].nunique()),
    )


def _comparison_row(mode: str,
                    selection_status: str,
                    universe_symbols: int,
                    trades: list[Any] | None,
                    metrics: dict[str, Any] | None,
                    notes: str) -> dict[str, Any]:
    metrics = metrics or {}
    top, worst, traded_symbols = _symbol_contributors(trades or [])
    return {
        "mode": mode,
        "status": selection_status,
        "total_return": metrics.get("total_return_pct", ""),
        "annual_return": metrics.get("annual_return_pct", ""),
        "MDD": metrics.get("max_drawdown_pct", ""),
        "PF": metrics.get("profit_factor", ""),
        "Sharpe": metrics.get("sharpe_ratio", ""),
        "Calmar": metrics.get("calmar_ratio", ""),
        "win_rate": (metrics.get("win_rate", "") * 100.0 if metrics.get("win_rate", "") != "" else ""),
        "avg_R": metrics.get("avg_r_multiple", ""),
        "trades": metrics.get("total_trades", ""),
        "universe_symbols": universe_symbols,
        "number_of_symbols_traded": traded_symbols,
        "top_contributors": top,
        "worst_contributors": worst,
        "notes": notes,
    }


def _selection_rows(selections: list[UniverseSelection]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sel in selections:
        if not sel.symbols:
            rows.append({
                "mode": sel.mode,
                "rebalance_date": sel.rebalance_date,
                "effective_start": sel.effective_start,
                "effective_end": sel.effective_end,
                "rank": "",
                "symbol": "",
                "base": "",
                "status": sel.status,
                "source": sel.source,
                "notes": sel.notes,
            })
            continue
        for rank, sym in enumerate(sel.symbols, start=1):
            rows.append({
                "mode": sel.mode,
                "rebalance_date": sel.rebalance_date,
                "effective_start": sel.effective_start,
                "effective_end": sel.effective_end,
                "rank": rank,
                "symbol": sym,
                "base": _base_from_symbol(sym),
                "status": sel.status,
                "source": sel.source,
                "notes": sel.notes,
            })
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["status"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_methodology(path: Path, comparison: list[dict[str, Any]], ranking_path: Path) -> None:
    current = next((r for r in comparison if r["mode"] == "current_top100_bias_check"), {})
    static = next((r for r in comparison if r["mode"] == "static_pit_top100"), {})
    rolling = next((r for r in comparison if r["mode"] == "rolling_pit_top100_quarterly"), {})
    has_pit = static.get("status") == "ok" and rolling.get("status") == "ok"
    lines = [
        "# EXP-005 Crypto Universe Methodology",
        "",
        "## 目的",
        "",
        "檢查目前 Crypto 策略是否受到 survivorship bias / universe selection bias 影響。",
        "",
        "## 沒改什麼",
        "",
        "- 沒有修改策略訊號。",
        "- 沒有修改策略參數。",
        "- 沒有修改成本模型。",
        "- 沒有修改倉位管理。",
        "",
        "## Universe 模式",
        "",
        "1. `current_top100_bias_check`：使用目前 config/本地 DB 可用 crypto universe 回測歷史。這是 biased benchmark，只能當對照。",
        "2. `static_pit_top100`：需要歷史市值排名 CSV，在 OOS 起點前一日取當時 top 100，OOS 固定。",
        "3. `rolling_pit_top100_quarterly`：需要歷史市值排名 CSV，每季用 rebalance date 前一日可知 ranking 選出下一季 universe。",
        "",
        "## 需要的 PIT Ranking CSV",
        "",
        f"- 預設路徑：`{ranking_path}`",
        "- 必要欄位：`date,rank,symbol`。`symbol` 可填 `BTC`、`BTCUSDT` 或 `BYBIT:BTCUSDT.P`。",
        "- 可選欄位：`market_cap`。",
        "- 若沒有此檔案，static/rolling PIT 結果必須標記為 `missing_market_cap_history`，不得產生假績效。",
        "",
        "## 排除規則",
        "",
        "- 排除 stablecoins。",
        "- 排除 wrapped tokens。",
        "- 排除槓桿代幣。",
        "- 排除 selection date 前 OHLCV 不足 180 天的標的。",
        "- 排除 selection date 前 90 天成交量不足的標的。本腳本預設用 90 天 median dollar volume > 0 作為最低可交易性檢查，可用參數調高。",
        "",
        "## 本次資料狀態",
        "",
        f"- Historical market-cap ranking CSV exists: `{ranking_path.exists()}`。",
        f"- current_top100_bias_check status: `{current.get('status', '')}`。",
        f"- static_pit_top100 status: `{static.get('status', '')}`。",
        f"- rolling_pit_top100_quarterly status: `{rolling.get('status', '')}`。",
        "",
        "## 本次回答",
        "",
        f"1. 現有 universe 是否明顯高估績效？`{'無法完整判定，因 PIT ranking 缺資料；但 current-biased benchmark 不能當真實績效。' if not has_pit else '見 comparison CSV。'}`",
        f"2. static point-in-time top100 是否仍有 edge？`{'無法判定，缺歷史市值 ranking。' if static.get('status') != 'ok' else '見 comparison CSV。'}`",
        f"3. rolling top100 是否比固定 top100 更穩？`{'無法判定，缺歷史市值 ranking。' if rolling.get('status') != 'ok' else '見 comparison CSV。'}`",
        f"4. 績效是否集中在少數幣？`current-biased benchmark 的 top/worst contributors 已輸出至 comparison CSV；EXP-004 已顯示集中風險。`",
        f"5. 是否值得繼續研究這個策略？`需要更多測試；PIT universe 資料補齊前，不應依 current-biased benchmark 加碼研究結論。`",
        "",
        "## 結論",
        "",
        "需要更多測試。",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="EXP-005 PIT Crypto top-100 universe test.")
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--ranking-csv", default=DEFAULT_RANKING_CSV)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--min-history-days", type=int, default=180)
    parser.add_argument("--min-90d-dollar-volume", type=float, default=0.0)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    ranking_path = Path(args.ranking_csv)
    ranking_data = _load_rankings(ranking_path)
    raw_data = _load_all_crypto_data()
    data, signals, type_map = _build_signals(raw_data)

    current_sel = _current_biased_symbols(
        data,
        args.start_date,
        args.end_date,
        args.min_history_days,
        args.min_90d_dollar_volume,
    )
    static_as_of = (pd.Timestamp(args.start_date) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    static_sel = _select_from_rankings(
        "static_pit_top100",
        ranking_data,
        data,
        static_as_of,
        args.start_date,
        args.end_date,
        args.min_history_days,
        args.min_90d_dollar_volume,
    )
    rolling_sels = _quarter_selections(
        ranking_data,
        data,
        args.start_date,
        args.end_date,
        args.min_history_days,
        args.min_90d_dollar_volume,
    )

    comparison: list[dict[str, Any]] = []

    current_trades, current_metrics = _run_universe(
        data,
        signals,
        type_map,
        args.start_date,
        args.end_date,
        _date_allowed_static(args.start_date, args.end_date, current_sel.symbols),
    )
    comparison.append(_comparison_row(
        current_sel.mode,
        current_sel.status,
        len(current_sel.symbols),
        current_trades,
        current_metrics,
        current_sel.notes,
    ))

    if static_sel.status == "ok":
        static_trades, static_metrics = _run_universe(
            data,
            signals,
            type_map,
            args.start_date,
            args.end_date,
            _date_allowed_static(args.start_date, args.end_date, static_sel.symbols),
        )
        comparison.append(_comparison_row(
            static_sel.mode, static_sel.status, len(static_sel.symbols),
            static_trades, static_metrics, static_sel.notes,
        ))
    else:
        comparison.append(_comparison_row(
            static_sel.mode, static_sel.status, len(static_sel.symbols),
            None, None, static_sel.notes,
        ))

    if rolling_sels and all(sel.status == "ok" for sel in rolling_sels):
        rolling_trades, rolling_metrics = _run_universe(
            data,
            signals,
            type_map,
            args.start_date,
            args.end_date,
            _date_allowed_rolling(args.start_date, args.end_date, rolling_sels),
        )
        comparison.append(_comparison_row(
            "rolling_pit_top100_quarterly", "ok",
            int(np.mean([len(sel.symbols) for sel in rolling_sels])),
            rolling_trades, rolling_metrics,
            "Quarterly PIT universe from supplied historical market-cap ranking CSV.",
        ))
    else:
        status = "missing_market_cap_history" if ranking_data is None else "incomplete_rolling_universe"
        notes = "No historical market-cap ranking CSV found; rolling PIT universe cannot be constructed without external data."
        comparison.append(_comparison_row(
            "rolling_pit_top100_quarterly", status, 0, None, None, notes,
        ))

    _write_csv(out_dir / "crypto_universe_static_pit_top100.csv", _selection_rows([static_sel]))
    _write_csv(out_dir / "crypto_universe_rolling_pit_top100_quarterly.csv", _selection_rows(rolling_sels))
    _write_csv(out_dir / "crypto_universe_bias_comparison.csv", comparison)
    _write_methodology(Path("docs/research/crypto_universe_methodology.md"), comparison, ranking_path)

    print("\nEXP-005 PIT Crypto universe test")
    for row in comparison:
        print(
            f"{row['mode']:<34} status={row['status']:<28} "
            f"return={row['total_return']} PF={row['PF']} trades={row['trades']} "
            f"symbols={row['universe_symbols']}"
        )
    print("\nSaved:")
    print(f"- {out_dir / 'crypto_universe_static_pit_top100.csv'}")
    print(f"- {out_dir / 'crypto_universe_rolling_pit_top100_quarterly.csv'}")
    print(f"- {out_dir / 'crypto_universe_bias_comparison.csv'}")
    print("- docs/research/crypto_universe_methodology.md")


if __name__ == "__main__":
    main()
