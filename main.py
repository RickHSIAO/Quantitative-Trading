#!/usr/bin/env python3
"""
量化交易系統 — 主程式入口

用法：
  python main.py fetch              # 下載 120 個資產的歷史資料至 SQLite
  python main.py fetch --years 3    # 只抓 3 年
  python main.py backtest           # 執行預設完整模式回測並輸出 Output.xlsx（VP + moat-tf-only）
  python main.py backtest --no-with-vp # 關閉 Volume Profile（速度較快）
  python main.py live               # 即時交易（Bybit，僅加密貨幣）
  python main.py info               # 顯示已下載資產摘要
"""

import argparse
import sys
import os
import json

# 確保根目錄在 path 上
sys.path.insert(0, os.path.dirname(__file__))


# ─── Sub-commands ─────────────────────────────────────────────────────────────
def cmd_fetch(args):
    from config import get_selected_assets
    from src.fetcher import fetch_all_assets
    from src.benchmarks import fetch_benchmarks
    assets = get_selected_assets(args.seed)
    _print_asset_summary(assets)
    fetch_all_assets(assets, years=args.years)
    fetch_benchmarks(years=max(args.years, 6))


def cmd_update(args):
    from config import get_selected_assets
    from src.fetcher import update_all_assets
    from src.benchmarks import update_benchmarks
    assets = get_selected_assets(args.seed)
    update_all_assets(assets)
    update_benchmarks()


def cmd_info(args):
    from src.database import get_registry
    reg = get_registry()
    if reg.empty:
        print('資料庫為空，請先執行: python main.py fetch')
        return
    print(reg.to_string(index=False))
    print(f'\n共 {len(reg)} 個資產，總計 {reg["bar_count"].sum():,} 筆K線')


def _load_benchmark(symbol: str, years: int = 6) -> 'pd.DataFrame | None':
    """下載基準指數日線（^TWII, ^GSPC），用於大盤護城河濾網。"""
    import yfinance as yf
    import pandas as pd
    from datetime import datetime, timedelta, timezone
    end   = datetime.now()
    start = (end - timedelta(days=years * 365 + 60)).strftime('%Y-%m-%d')
    end   = end.strftime('%Y-%m-%d')
    try:
        df = yf.download(symbol, start=start, end=end, auto_adjust=True,
                         progress=False, threads=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, __import__('pandas').MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = __import__('pandas').DatetimeIndex(df.index).tz_localize(None)
        return df.dropna(subset=['Close'])
    except Exception as e:
        print(f'[WARN] 無法載入基準指數 {symbol}: {e}')
        return None


def _crypto_to_bybit_symbol(symbol: str) -> str:
    s = str(symbol).strip().upper()
    if s.startswith('BYBIT:') and s.endswith('.P'):
        return s
    if s.endswith('USDT'):
        return f'BYBIT:{s}.P'
    return f'BYBIT:{s}USDT.P'


def _has_crypto_rankings_table() -> bool:
    import sqlite3
    import config

    conn = sqlite3.connect(config.DB_PATH)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='crypto_market_cap_rankings'"
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _prev3y_crypto_top_by_year(year: int, top_n: int,
                               rank_by: str = 'market_cap') -> 'pd.DataFrame':
    import sqlite3
    import pandas as pd
    import config

    if not _has_crypto_rankings_table():
        return pd.DataFrame()
    rank_cols = {
        'market_cap': 'market_cap',
        'volume_24h': 'volume_24h',
    }
    if rank_by not in rank_cols:
        raise ValueError(f'Unsupported crypto rank_by: {rank_by}')
    rank_col = rank_cols[rank_by]

    lookback_start = f'{year - 3}-01-01'
    lookback_end = f'{year - 1}-12-31'
    conn = sqlite3.connect(config.DB_PATH)
    try:
        df = pd.read_sql_query(
            f"""
            SELECT
                symbol,
                MAX(name) AS name,
                AVG({rank_col}) AS avg_rank_value,
                AVG(market_cap) AS avg_market_cap,
                AVG(volume_24h) AS avg_volume_24h,
                AVG(rank) AS avg_cmc_rank,
                COUNT(*) AS snapshots
            FROM crypto_market_cap_rankings
            WHERE snapshot_date BETWEEN ? AND ?
              AND {rank_col} IS NOT NULL
              AND COALESCE(is_stablecoin, 0) = 0
              AND COALESCE(is_wrapped, 0) = 0
              AND COALESCE(is_leveraged, 0) = 0
            GROUP BY symbol
            ORDER BY avg_rank_value DESC
            LIMIT ?
            """,
            conn,
            params=(lookback_start, lookback_end, int(top_n)),
        )
    finally:
        conn.close()

    if df.empty:
        return df
    df['bybit_symbol'] = df['symbol'].map(_crypto_to_bybit_symbol)
    return df


def _build_prev3y_crypto_universe(start_date: str,
                                  end_date: str,
                                  available: set[str],
                                  top_n: int,
                                  min_history_days: int,
                                  rank_by: str = 'market_cap',
                                  ) -> tuple[dict[int, set[str]], set[str], list[dict]]:
    import pandas as pd
    from src.database import load_prices

    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    years = range(int(start_ts.year), int(end_ts.year) + 1)

    allowed_by_year: dict[int, set[str]] = {}
    all_symbols: set[str] = set()
    summary: list[dict] = []
    history_cache: dict[str, pd.DataFrame] = {}

    for year in years:
        year_start = pd.Timestamp(f'{year}-01-01')
        ranked = _prev3y_crypto_top_by_year(year, top_n, rank_by)
        eligible: set[str] = set()
        if ranked.empty:
            allowed_by_year[year] = eligible
            summary.append({
                'year': year,
                'ranked': 0,
                'bybit_available': 0,
                'eligible': 0,
            })
            continue

        bybit_symbols = ranked['bybit_symbol'].dropna().astype(str).tolist()
        bybit_available = [s for s in bybit_symbols if s in available]
        for sym in bybit_available:
            if sym not in history_cache:
                try:
                    history_cache[sym] = load_prices(sym)
                except Exception:
                    history_cache[sym] = pd.DataFrame()
            df = history_cache[sym]
            if df is None or df.empty:
                continue
            if len(df.loc[df.index < year_start]) < min_history_days:
                continue
            eligible.add(sym)

        allowed_by_year[year] = eligible
        all_symbols.update(eligible)
        summary.append({
            'year': year,
            'ranked': int(len(ranked)),
            'bybit_available': int(len(set(bybit_available))),
            'eligible': int(len(eligible)),
        })

    return allowed_by_year, all_symbols, summary


def _mask_crypto_signals_by_year(signals: dict,
                                 type_map: dict[str, str],
                                 allowed_by_year: dict[int, set[str]]) -> None:
    import pandas as pd

    if not allowed_by_year:
        return
    years = set(allowed_by_year)
    for sym, sigs in signals.items():
        if type_map.get(sym) != 'Crypto' or not isinstance(sigs, dict):
            continue
        ref = sigs.get('combined')
        if not isinstance(ref, pd.Series):
            ref = next((v for v in sigs.values() if isinstance(v, pd.Series)), None)
        if ref is None:
            continue

        disallowed = pd.Series(False, index=ref.index)
        for year in years:
            year_mask = ref.index.year == year
            if sym not in allowed_by_year.get(year, set()):
                disallowed.loc[year_mask] = True
        if not disallowed.any():
            continue

        for ser in sigs.values():
            if isinstance(ser, pd.Series):
                ser.loc[disallowed] = 0


CRYPTO_CANDIDATES: dict[str, dict] = {
    'volume-top125-lb3-sym035': {
        'universe': 'prev3y-volume-top100',
        'rank_by': 'volume_24h',
        'top_n': 125,
        'min_history_days': 180,
        'sym_wr_threshold': 0.35,
        'description': 'EXP-010 frozen forward candidate: prev3y volume Top125 + symbol WR 0.35',
    },
}

DEFAULT_CRYPTO_CANDIDATE = 'volume-top125-lb3-sym035'
LEGACY_CRYPTO_BASELINE = 'config-baseline'


def _apply_crypto_candidate(args, config) -> dict | None:
    candidate_name = getattr(args, 'crypto_candidate', '') or ''
    if not candidate_name or candidate_name == LEGACY_CRYPTO_BASELINE:
        if candidate_name == LEGACY_CRYPTO_BASELINE:
            print('[INFO] Crypto candidate disabled: using legacy config baseline')
        return None
    if candidate_name not in CRYPTO_CANDIDATES:
        valid = ', '.join([LEGACY_CRYPTO_BASELINE] + sorted(CRYPTO_CANDIDATES))
        raise ValueError(f'Unknown crypto candidate: {candidate_name}. Valid: {valid}')

    cand = CRYPTO_CANDIDATES[candidate_name]
    args.crypto_universe = cand['universe']
    args.crypto_top_n = int(cand['top_n'])
    args.crypto_min_history_days = int(cand['min_history_days'])

    wr_map = dict(getattr(config, 'SYM_MIN_WINRATE_BY_CLASS', {}) or {})
    wr_map['Crypto'] = float(cand['sym_wr_threshold'])
    config.SYM_MIN_WINRATE_BY_CLASS = wr_map
    print(f"[INFO] Crypto candidate enabled: {candidate_name}")
    print(f"       {cand['description']}")
    return cand


def cmd_backtest(args):
    import pandas as pd
    from tqdm import tqdm
    import config
    from config import get_selected_assets
    from src.database import load_prices, get_all_symbols
    from src.indicators import compute_all_indicators
    from src.strategies import apply_cross_asset_filters, generate_all_signals
    from src.backtester import Backtester
    from src.reporter import generate_excel_report
    from src.benchmarks import load_or_update_benchmark

    assets    = get_selected_assets(args.seed)
    available = set(get_all_symbols())

    if not available:
        print('資料庫為空，請先執行: python main.py fetch')
        return

    try:
        crypto_candidate = _apply_crypto_candidate(args, config)
    except ValueError as exc:
        print(f'[ERROR] {exc}')
        return

    crypto_universe_mode = getattr(args, 'crypto_universe', 'config')
    crypto_allowed_by_year: dict[int, set[str]] = {}
    prev3y_modes = {'prev3y-mcap-top100', 'prev3y-volume-top100'}
    if crypto_universe_mode in prev3y_modes:
        from datetime import date

        if not getattr(args, 'start_date', None):
            args.start_date = '2021-01-01'
        if not getattr(args, 'end_date', None):
            args.end_date = date.today().isoformat()

        crypto_rank_by = (
            'volume_24h' if crypto_universe_mode == 'prev3y-volume-top100'
            else 'market_cap'
        )
        crypto_allowed_by_year, crypto_symbols, crypto_uni_summary = _build_prev3y_crypto_universe(
            args.start_date,
            args.end_date,
            available,
            int(getattr(args, 'crypto_top_n', 100)),
            int(getattr(args, 'crypto_min_history_days', 180)),
            crypto_rank_by,
        )
        if not crypto_symbols:
            print(f'[ERROR] {crypto_universe_mode} 找不到任何符合條件的 Crypto 標的。')
            print('        請先確認 crypto_market_cap_rankings 與 Bybit OHLCV 已寫入 SQLite。')
            return

        market_symbol = getattr(config, 'CRYPTO_MARKET_SYMBOL', 'BYBIT:BTCUSDT.P')
        crypto_context_symbols = set(crypto_symbols)
        if market_symbol in available:
            crypto_context_symbols.add(market_symbol)
        assets['cryptos'] = sorted(crypto_context_symbols)
        assets['all'] = (
            list(assets['us_stocks']) +
            list(assets['tw_stocks']) +
            list(assets['cryptos']) +
            list(assets['commodities'])
        )

        rank_label = 'volume_24h' if crypto_rank_by == 'volume_24h' else 'market-cap'
        print(f'\n[INFO] Crypto universe = prev3y average {rank_label} Top{int(getattr(args, "crypto_top_n", 100))}')
        print(f'       backtest: {args.start_date} ~ {args.end_date}')
        print(f'       tradable union: {len(crypto_symbols)} symbols; context: {len(crypto_context_symbols)} symbols')
        for item in crypto_uni_summary:
            print(
                f"       {item['year']}: ranked={item['ranked']} "
                f"bybit_available={item['bybit_available']} eligible={item['eligible']}"
            )

    type_map: dict[str, str] = {}
    for sym in assets['us_stocks']:  type_map[sym] = 'US Stock'
    for sym in assets['tw_stocks']:  type_map[sym] = 'TW Stock'
    for sym in assets['cryptos']:    type_map[sym] = 'Crypto'
    for sym in assets['commodities']:type_map[sym] = 'Commodity'

    strategy_profiles = getattr(config, 'STRATEGY_PROFILES', {})
    profile_name = getattr(args, 'profile', None)
    profile_asset_types = None
    if profile_name:
        if profile_name not in strategy_profiles:
            valid = ', '.join(strategy_profiles.keys())
            print(f'[ERROR] Unknown profile: {profile_name}. Valid profiles: {valid}')
            return
        profile_asset_types = set(strategy_profiles[profile_name].get('asset_types', []))

    # 下載大盤基準指數（用於護城河濾網）
    print('\n載入/更新大盤基準指數...')
    tw_benchmark = load_or_update_benchmark(config.TW_MARKET_SYMBOL)
    us_benchmark = load_or_update_benchmark(config.US_MARKET_SYMBOL)
    if tw_benchmark is not None:
        print(f'  ^TWII: {len(tw_benchmark)} 筆  ({tw_benchmark.index[0].date()} → {tw_benchmark.index[-1].date()})')
    else:
        print('  [WARN] 台股大盤指數載入失敗，台股護城河濾網停用')
    if us_benchmark is not None:
        print(f'  ^GSPC: {len(us_benchmark)} 筆  ({us_benchmark.index[0].date()} → {us_benchmark.index[-1].date()})')
    else:
        print('  [WARN] 美股大盤指數載入失敗，美股護城河濾網停用')

    selected = [
        s for s in assets['all']
        if s in available and (
            profile_asset_types is None or type_map.get(s) in profile_asset_types
        )
    ]
    print(f'\n載入 {len(selected)} 個資產，計算指標與信號中...\n')

    data:    dict[str, pd.DataFrame]          = {}
    signals: dict[str, dict[str, pd.Series]] = {}
    skipped = 0

    use_vp = getattr(args, 'with_vp', True)
    if not use_vp:
        print('[INFO] Volume Profile 已停用；移除 --no-with-vp 可回到預設完整模式')

    for sym in tqdm(selected, desc='指標計算', unit='檔'):
        df = load_prices(sym)
        if df is None or len(df) < config.EMA_PERIOD + 10:
            skipped += 1
            continue

        try:
            atype = type_map.get(sym, '')
            bm    = tw_benchmark if atype == 'TW Stock' else \
                    us_benchmark if atype == 'US Stock' else None

            df = compute_all_indicators(df, include_vp=use_vp)
            sigs = generate_all_signals(
                df, asset_type=atype, benchmark_df=bm,
                moat_tf_only=getattr(args, 'moat_tf_only', True),
                rs_pct=getattr(args, 'rs_pct', None) or config.RS_OUTPERFORM_PCT,
            )
            data[sym]    = df
            signals[sym] = sigs
        except Exception as exc:
            tqdm.write(f'  [WARN] {sym}: {exc}')
            skipped += 1

    print(f'\n有效資產：{len(data)} 檔，跳過：{skipped} 檔')

    # 日期區間篩選：指標用完整歷史暖身，交易只在指定區間內發生
    start_date = getattr(args, 'start_date', None)
    end_date   = getattr(args, 'end_date',   None)
    if start_date or end_date:
        import pandas as pd
        for sym in list(data.keys()):
            df_sym = data[sym]
            mask = pd.Series(True, index=df_sym.index)
            if start_date:
                mask &= df_sym.index >= pd.Timestamp(start_date)
            if end_date:
                mask &= df_sym.index <= pd.Timestamp(end_date)
            data[sym] = df_sym.loc[mask]
            for k, s in signals[sym].items():
                signals[sym][k] = s.loc[mask]
            if data[sym].empty:
                del data[sym]
                del signals[sym]

    if crypto_universe_mode in prev3y_modes:
        _mask_crypto_signals_by_year(signals, type_map, crypto_allowed_by_year)

    apply_cross_asset_filters(data, signals, type_map)

    silo_mode = getattr(config, 'ENABLE_SILO_MODE', False)

    if silo_mode:
        from src.backtester import run_silo_backtest, _combine_silo_equity_curves
        silo_classes = getattr(config, 'SILO_CLASSES', {})
        silo_capital = getattr(config, 'SILO_CAPITAL', 10_000.0)
        if profile_name:
            strategy_profiles = {profile_name: strategy_profiles[profile_name]}

        trades, silo_results = run_silo_backtest(
            data, signals, type_map, silo_classes, silo_capital,
            strategy_profiles=strategy_profiles,
        )

        total_initial = sum(sr['bt'].initial_capital for sr in silo_results.values())
        total_final   = sum(sr['bt'].capital for sr in silo_results.values())
        silo_capitals = {k: sr['bt'].initial_capital for k, sr in silo_results.items()}
        equity_curve  = _combine_silo_equity_curves(
            {k: sr['equity_curve'] for k, sr in silo_results.items()},
            total_initial,
            silo_capital=silo_capital,
            silo_capitals=silo_capitals,
        )

        # 組合整體指標（利用虛擬 Backtester 計算 Sharpe / DD 等）
        combined_bt = Backtester(initial_capital=total_initial)
        combined_bt.trades       = trades
        combined_bt.capital      = total_final
        combined_bt.equity_curve = equity_curve
        metrics = combined_bt.get_metrics()
        metrics['silo_results'] = {k: sr['metrics'] for k, sr in silo_results.items()}

        # 印出各艙位摘要
        print('\n' + '='*56)
        print('  艙位回測摘要（各艙位初始資金 ${:,.0f}）'.format(silo_capital))
        print('='*56)
        for sname, sr in silo_results.items():
            m = sr['metrics']
            if m:
                print(f"  {sname:<12}  "
                      f"損益 ${m.get('total_pnl', 0):>+8,.2f}  "
                      f"年化 {m.get('annual_return_pct', 0):>+6.2f}%  "
                      f"勝率 {m.get('win_rate', 0)*100:>5.1f}%  "
                      f"交易 {m.get('total_trades', 0):>3} 筆  "
                      f"最大回撤 {m.get('max_drawdown_pct', 0):>6.2f}%")
        print('='*56)
    else:
        bt     = Backtester(initial_capital=args.capital)
        trades = bt.run(data, signals, type_map)
        metrics = bt.get_metrics()
        equity_curve = bt.equity_curve

    # 護城河狀態
    metrics['moat_status'] = {
        'TW': 'enabled' if tw_benchmark is not None else 'disabled (^TWII 載入失敗)',
        'US': 'enabled' if us_benchmark is not None else 'disabled (^GSPC 載入失敗)',
        'moat_tf_only': bool(getattr(args, 'moat_tf_only', True)),
    }

    # ── 印出整體績效摘要 ──────────────────────────────────────────────────
    if crypto_universe_mode in prev3y_modes:
        metrics['crypto_universe'] = {
            'mode': crypto_universe_mode,
            'rank_by': (
                'volume_24h' if crypto_universe_mode == 'prev3y-volume-top100'
                else 'market_cap'
            ),
            'top_n': int(getattr(args, 'crypto_top_n', 100)),
            'min_history_days': int(getattr(args, 'crypto_min_history_days', 180)),
            'start_date': getattr(args, 'start_date', None),
            'end_date': getattr(args, 'end_date', None),
            'candidate': getattr(args, 'crypto_candidate', '') or '',
        }

    print('\n' + '='*48)
    print('  整體回測績效摘要')
    print('='*48)
    labels = {
        'total_return_pct': '總報酬率 (%)',
        'total_trades':     '總交易次數',
        'win_rate':         '勝率',
        'profit_factor':    '盈虧比 (PF)',
        'sharpe_ratio':     '夏普比率',
        'max_drawdown_pct': '最大回撤 (%)',
        'best_trade':       '最佳單筆 (USD)',
        'worst_trade':      '最差單筆 (USD)',
    }
    for k, label in labels.items():
        v = metrics.get(k, 'N/A')
        if isinstance(v, float):
            print(f'  {label:<22}: {v:>10.3f}')
        else:
            print(f'  {label:<22}: {v}')
    print('='*48)

    output_path = args.output or None
    generate_excel_report(trades, metrics, equity_curve, output_path)

    # ── 儲存回測結果到 SQLite ─────────────────────────────────────────────
    from src.database import save_backtest_run
    note    = getattr(args, 'note', '') or ''
    version = getattr(args, 'ver',  None) or config.SYSTEM_VERSION
    run_id  = save_backtest_run(trades, metrics, note=note, version=version)
    print(f'\n  [DB] 回測記錄已儲存  run_id={run_id}  version={version}  (python main.py history 查詢歷史)')


def cmd_history(args):
    """列出歷史回測摘要，可加 --run-id 查看該次交易明細。"""
    from src.database import load_backtest_history, load_backtest_trades

    if args.run_id:
        df = load_backtest_trades(args.run_id)
        if df.empty:
            print(f'找不到 run_id={args.run_id} 的交易記錄')
            return
        print(f'\n== run_id={args.run_id} 交易明細（共 {len(df)} 筆）==')
        cols = ['symbol', 'strategy', 'direction', 'entry_date', 'exit_date',
                'pnl', 'return_pct', 'r_multiple', 'exit_reason']
        print(df[cols].to_string(index=False))
    else:
        df = load_backtest_history(args.limit)
        if df.empty:
            print('尚無回測記錄，請先執行: python main.py backtest')
            return
        print(f'\n== 最近 {len(df)} 次回測記錄 ==')
        cols = ['run_id', 'version', 'run_at', 'initial_capital', 'final_capital',
                'total_return_pct', 'annual_return_pct', 'total_trades',
                'win_rate', 'profit_factor', 'sharpe_ratio', 'max_drawdown_pct', 'note']
        print(df[cols].to_string(index=False))
        print('\n  提示：python main.py history --run-id <ID>  查看該次交易明細')


def _shadow_close_event_now():
    """Timezone-aware UTC clock for the optional same-process close-event
    observation seam (SR-101D2). Module-level so tests can monkeypatch it to a
    fixed aware UTC value. Not used by any trading/sizing logic."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def cmd_live(args):
    """
    即時交易迴圈：
    1. 增量更新最新 K 線資料（不重抓整年）
    2. 計算指標/信號（與回測同參數）
    3. 根據 1/4 Kelly 下單（Bybit，僅限加密貨幣）
    """
    import time
    import pandas as pd
    import config
    from config import get_selected_assets
    from src.fetcher import _download_single
    from src.indicators import compute_all_indicators
    from src.strategies import apply_cross_asset_filters, generate_all_signals
    from src.risk import estimate_kelly_from_history, position_size, calculate_stops
    from src.backtester import _geometric_rr_ok
    from src.executor import BybitExecutor
    from src.database import get_all_symbols, get_connection, init_db
    from src.live_ledger import (
        ensure_bybit_live_order_ledger,
        export_bybit_live_orders_to_excel,
        record_bybit_order,
    )
    from dataclasses import replace as _dc_replace
    from src.strategy_core.entry_decision import (
        EntryAction,
        EntryDecisionInput,
        decide_entry,
    )
    from src.strategy_core.exit_decision import (
        ExitAction,
        ExitDecisionInput,
        decide_exit,
    )

    try:
        executor = BybitExecutor()
    except RuntimeError as e:
        print(f'[ERROR] {e}')
        return

    init_db()
    ensure_bybit_live_order_ledger()
    ledger_path = export_bybit_live_orders_to_excel()
    print(f'[INFO] Bybit live order ledger: SQLite={config.DB_PATH} Excel={ledger_path}')
    try:
        crypto_candidate = _apply_crypto_candidate(args, config)
    except ValueError as exc:
        print(f'[ERROR] {exc}')
        return

    assets   = get_selected_assets(args.seed)
    crypto_tradable_symbols = set(assets['cryptos'])
    if crypto_candidate is not None:
        from datetime import date

        available = set(get_all_symbols())
        live_date = date.today().isoformat()
        _, crypto_symbols, crypto_uni_summary = _build_prev3y_crypto_universe(
            live_date,
            live_date,
            available,
            int(getattr(args, 'crypto_top_n', crypto_candidate['top_n'])),
            int(getattr(args, 'crypto_min_history_days', crypto_candidate['min_history_days'])),
            crypto_candidate['rank_by'],
        )
        if not crypto_symbols:
            print('[ERROR] Crypto candidate 找不到任何符合條件的 live universe 標的。')
            print('        請先確認 crypto_market_cap_rankings 與 Bybit OHLCV 已寫入 SQLite。')
            return
        crypto_tradable_symbols = set(crypto_symbols)
        crypto_context_symbols = set(crypto_symbols)
        market_symbol = getattr(config, 'CRYPTO_MARKET_SYMBOL', 'BYBIT:BTCUSDT.P')
        if market_symbol in available:
            crypto_context_symbols.add(market_symbol)
        assets['cryptos'] = sorted(crypto_context_symbols)
        print('[INFO] Live Crypto candidate universe')
        for item in crypto_uni_summary:
            print(
                f"       {item['year']}: ranked={item['ranked']} "
                f"bybit_available={item['bybit_available']} eligible={item['eligible']}"
            )

    cryptos  = assets['cryptos']
    type_map = {s: 'Crypto' for s in cryptos}
    _init_acct = getattr(executor, 'get_account_info', None)
    _init_acct = _init_acct() if _init_acct else {}
    balance  = _init_acct.get('wallet_balance') or executor.get_balance()
    crypto_profile = getattr(config, 'STRATEGY_PROFILES', {}).get('Crypto', {})
    crypto_max_positions = int(crypto_profile.get('max_total_positions', config.MAX_TOTAL_POSITIONS))
    crypto_max_position_pct = float(crypto_profile.get('max_position_pct', config.MAX_POSITION_PCT))
    print(f'Bybit 帳戶餘額：{balance:.2f} USDT')
    print(f'監控 {len(cryptos)} 個加密貨幣 | 每 {args.interval} 分鐘掃描一次')
    print('[注意] Demo Trading：', config.BYBIT_DEMO, '| 測試網模式：', config.BYBIT_TESTNET)

    from datetime import datetime, timedelta, timezone
    from src.database import upsert_prices, load_prices, get_last_date
    from src.fetcher import asset_type_of

    # 啟動時若 DB 沒有歷史，先做一次完整下載
    for sym in cryptos:
        if get_last_date(sym) is None:
            start_str = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            end_str   = datetime.now().strftime('%Y-%m-%d')
            df0 = _download_single(sym, start_str, end_str)
            if df0 is not None and len(df0) >= 20:
                upsert_prices(df0, sym, asset_type_of(sym))

    # Lightweight closed-trade record（Kelly 估算只需要 .pnl 屬性）
    class ClosedTradeStub:
        __slots__ = ('pnl',)
        def __init__(self, pnl): self.pnl = pnl

    def _cls_get(name: str, asset_type: str, default):
        d = getattr(config, name, None) or {}
        return d.get(asset_type, default) if isinstance(d, dict) else default

    def _closed_daily_df(df: pd.DataFrame) -> pd.DataFrame:
        """Drop the still-forming current UTC daily candle for live parity."""
        if df is None or df.empty:
            return df
        utc_today = pd.Timestamp(datetime.now(timezone.utc).date())
        if df.index[-1] >= utc_today:
            return df.loc[df.index < utc_today]
        return df

    def _live_price(sym: str, signal_price: float) -> float:
        getter = getattr(executor, 'get_last_price', None)
        live_price = getter(sym) if getter is not None else None
        if live_price is None or live_price <= 0:
            return signal_price
        if signal_price > 0:
            drift = abs(live_price / signal_price - 1.0)
            if drift >= 0.02:
                print(
                    f'  [PRICE] {sym}: live={live_price:.6f}, '
                    f'signal_close={signal_price:.6f}; using live'
                )
        return live_price

    def _crypto_leverage() -> float:
        lev_map = getattr(config, 'LEVERAGE_BY_CLASS', {})
        try:
            lev = float(lev_map.get('Crypto', 1.0))
        except Exception:
            lev = 1.0
        return lev if lev > 0 else 1.0

    def _position_invested_margin(pos: dict) -> float:
        try:
            notional = abs(
                float(pos.get('entry') or 0.0) * float(pos.get('qty') or 0.0)
            )
            return notional / _crypto_leverage()
        except Exception:
            return 0.0

    def _fmt_live_price(value) -> str:
        try:
            val = float(value)
        except Exception:
            return '-'
        if val <= 0:
            return '-'
        if val >= 100:
            return f'{val:.2f}'
        if val >= 1:
            return f'{val:.4f}'
        return f'{val:.6f}'

    def _fmt_live_qty(value) -> str:
        try:
            val = float(value)
        except Exception:
            return '-'
        return f'{val:.8f}'.rstrip('0').rstrip('.')

    def _taker_fee(qty, price) -> float:
        try:
            return abs(float(qty or 0.0) * float(price or 0.0)) * float(config.BYBIT_TAKER_FEE)
        except Exception:
            return 0.0

    def _record_live_order(action: str, sym: str, direction: int, qty, price,
                           *, response=None, reason: str = '', stop_loss=None,
                           take_profit=None, strategy: str = '', score=None,
                           signal_date: str = '', pnl=None, fee=None,
                           recorded_at: str = '') -> int | None:
        try:
            row_id = record_bybit_order(
                action=action,
                symbol=sym,
                direction=direction,
                quantity=qty,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy=strategy,
                score=score,
                signal_date=signal_date,
                reason=reason,
                response=response or {},
                pnl=pnl,
                fee=fee,
                balance_usdt=balance,
                recorded_at=recorded_at or None,
            )
            print(f'  [LEDGER] {action.upper()} {sym} row_id={row_id}')
            return row_id
        except Exception as exc:
            print(f'  [LEDGER WARN] {sym}: {exc}')
            return None

    def _print_open_positions(acct: dict | None = None) -> None:
        if acct is None:
            acct = {}
        wallet   = acct.get('wallet_balance', 0.0)
        equity   = acct.get('equity', wallet)
        pos_im   = acct.get('position_im', 0.0)
        avail    = acct.get('available', 0.0)
        upl      = acct.get('unrealised_pnl', 0.0)
        cum_pnl  = acct.get('cum_realised_pnl', 0.0)
        if open_pos:
            print(f'  持倉明細（{len(open_pos)} 個）：')
            total = len(open_pos)
            rows = []
            for idx, (sym, pos) in enumerate(sorted(open_pos.items()), start=1):
                direction = '做多' if int(pos.get('dir', 0) or 0) == 1 else '做空'
                strategy = pos.get('strategy', 'unknown')
                score = pos.get('score', 0)
                last_price = pos.get('last_price') or pos.get('mark_price') or pos.get('entry')
                rows.append({
                    'idx':  f'{idx:02d}/{total}',
                    'sym':  sym,
                    'dir':  direction,
                    'tag':  f'[{strategy} s={score}]',
                    'qty':  _fmt_live_qty(pos.get('qty')),
                    'ent':  _fmt_live_price(pos.get('entry')),
                    'cur':  _fmt_live_price(last_price),
                    'sl':   _fmt_live_price(pos.get('sl')),
                    'tp':   _fmt_live_price(pos.get('tp')),
                })
            w = {k: max(len(r[k]) for r in rows)
                 for k in ('sym', 'tag', 'qty', 'ent', 'cur', 'sl', 'tp')}
            for r in rows:
                print(
                    f'    {r["idx"]} {r["sym"]:<{w["sym"]}} {r["dir"]} '
                    f'{r["tag"]:<{w["tag"]}}  '
                    f'qty={r["qty"]:>{w["qty"]}}  '
                    f'entry={r["ent"]:>{w["ent"]}}  '
                    f'cur={r["cur"]:>{w["cur"]}}  '
                    f'SL={r["sl"]:>{w["sl"]}}  '
                    f'TP={r["tp"]:>{w["tp"]}}'
                )
        sign = '+' if upl >= 0 else ''
        cum_sign = '+' if cum_pnl >= 0 else ''
        print()
        print(
            f'  帳戶餘額：{wallet:.2f} USDT | '
            f'已投入保證金：{pos_im:.2f} USDT | '
            f'可開倉額度：{avail:.2f} USDT'
        )
        print(
            f'  帳戶淨值：{equity:.2f} USDT | '
            f'未實現損益：{sign}{upl:.2f} USDT | '
            f'已實現損益：{cum_sign}{cum_pnl:.2f} USDT | '
            f'持倉：{len(open_pos)} 個'
        )

    def _latest_family_signal(sigs: dict, name: str) -> int:
        # Latest per-family signal for the shared entry-decision core. Mirrors the
        # guarded access the old _dominant_live_strategy used: a missing/empty
        # series yields 0, which never equals a +/-1 direction (so that family is
        # excluded from dominance -- identical to the original behaviour). Any
        # OTHER conversion failure (e.g. non-numeric latest value) is NOT
        # swallowed here -- it propagates to the existing outer per-symbol
        # try/except, exactly as the original int(sigs[name].iloc[-1]) call
        # inside _dominant_live_strategy did.
        if name not in sigs:
            return 0
        ser = sigs[name]
        if len(ser) == 0:
            return 0
        return int(ser.iloc[-1])

    def _dominant_strategy_at(sigs: dict, dt: pd.Timestamp, direction: int) -> str:
        matched = []
        for name in ('trend', 'vp', 'bb'):
            ser = sigs.get(name)
            if ser is not None and dt in ser.index and int(ser.loc[dt]) == direction:
                matched.append(name)
        return matched[0] if len(matched) == 1 else 'combined'

    def _signal_dt_at_or_before(sigs: dict, dt: pd.Timestamp) -> pd.Timestamp | None:
        ref = sigs.get('combined')
        if ref is None or ref.empty:
            return None
        idx = ref.index[ref.index <= dt]
        return idx[-1] if len(idx) else None

    trade_history: dict[str, list] = {s: [] for s in cryptos}
    reentry_block_signal_dt: dict[str, pd.Timestamp] = {}
    remote_closed_symbols: set[str] = set()

    def _ensure_live_context_symbol(sym: str, source: str) -> None:
        if not sym.startswith('BYBIT:') or not sym.endswith('.P'):
            return
        if sym not in type_map:
            type_map[sym] = 'Crypto'
        trade_history.setdefault(sym, [])
        if sym not in cryptos:
            cryptos.append(sym)
            print(f'  [SYNC] {sym}: monitoring existing Bybit position from {source}')

    def _block_reentry(sym: str, signal_dt: pd.Timestamp, reason: str) -> None:
        signal_ts = pd.Timestamp(signal_dt)
        if reentry_block_signal_dt.get(sym) != signal_ts:
            print(
                f'  [COOLDOWN] {sym}: {reason}; '
                f'skip re-entry until next daily signal'
            )
        reentry_block_signal_dt[sym] = signal_ts

    def _reentry_blocked(sym: str, signal_dt: pd.Timestamp) -> bool:
        blocked_dt = reentry_block_signal_dt.get(sym)
        if blocked_dt is None:
            return False
        signal_ts = pd.Timestamp(signal_dt)
        if signal_ts <= blocked_dt:
            return True
        del reentry_block_signal_dt[sym]
        return False

    def _sym_wr_ok(sym: str) -> bool:
        min_wr = _cls_get('SYM_MIN_WINRATE_BY_CLASS', 'Crypto', config.SYM_MIN_WINRATE)
        if min_wr <= 0:
            return True
        window = _cls_get('SYM_WR_WINDOW_BY_CLASS', 'Crypto', config.SYM_WR_WINDOW)
        min_trades = _cls_get('SYM_WR_MIN_TRADES_BY_CLASS', 'Crypto',
                              config.SYM_WR_MIN_TRADES)
        hist = trade_history.get(sym, [])[-window:]
        if len(hist) < min_trades:
            return True
        wins = sum(1 for t in hist if getattr(t, 'pnl', None) is not None and t.pnl > 0)
        return wins / len(hist) >= min_wr

    live_meta_path = os.path.join(getattr(config, 'DB_PATH', 'data/trading.db'))
    live_meta_path = os.path.join(os.path.dirname(live_meta_path), 'live_positions.json')

    def _load_live_meta() -> dict:
        try:
            if os.path.exists(live_meta_path):
                with open(live_meta_path, 'r', encoding='utf-8') as fh:
                    return json.load(fh)
        except Exception as exc:
            print(f'[WARN] load live metadata failed: {exc}')
        return {}

    def _save_live_meta(meta: dict) -> None:
        try:
            os.makedirs(os.path.dirname(live_meta_path), exist_ok=True)
            with open(live_meta_path, 'w', encoding='utf-8') as fh:
                json.dump(meta, fh, ensure_ascii=False, indent=2, sort_keys=True)
        except Exception as exc:
            print(f'[WARN] save live metadata failed: {exc}')

    live_meta = _load_live_meta()
    for _meta_sym in sorted(live_meta):
        _ensure_live_context_symbol(str(_meta_sym), 'live metadata')

    def _position_meta(sym: str) -> dict:
        item = live_meta.get(sym, {})
        return item if isinstance(item, dict) else {}

    def _remember_position(sym: str, pos: dict) -> None:
        live_meta[sym] = {
            'symbol': sym,
            'direction': pos.get('dir'),
            'qty': pos.get('qty'),
            'entry': pos.get('entry'),
            'invested_margin': _position_invested_margin(pos),
            'entry_dt': pos.get('entry_dt', ''),
            'strategy': pos.get('strategy', 'unknown'),
            'score': pos.get('score', 0),
            'entry_reason': pos.get('entry_reason', ''),
            'entry_order_id': pos.get('entry_order_id', ''),
            'exit_order_id': pos.get('exit_order_id', ''),
            'orig_sl': pos.get('orig_sl', pos.get('sl', 0.0)),
            'sl': pos.get('sl', 0.0),
            'tp': pos.get('tp', 0.0),
            'trail_anchor': pos.get('trail_anchor', pos.get('entry', 0.0)),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        _save_live_meta(live_meta)

    def _forget_position(sym: str) -> None:
        if sym in live_meta:
            del live_meta[sym]
            _save_live_meta(live_meta)

    def _recover_entry_from_executions(sym: str, qty: float, direction: int) -> dict:
        side = 'Buy' if direction == 1 else 'Sell'
        executions = executor.get_executions(sym, limit=100)
        rows = []
        for e in executions:
            if e.get('side') != side:
                continue
            try:
                exec_qty = float(e.get('execQty') or 0.0)
                exec_price = float(e.get('execPrice') or 0.0)
                exec_time = int(e.get('execTime') or e.get('execTimeNs') or 0)
            except Exception:
                continue
            if exec_qty <= 0 or exec_price <= 0:
                continue
            rows.append((exec_time, exec_qty, exec_price))
        rows.sort(reverse=True)

        accum_qty = 0.0
        notional = 0.0
        oldest_time = 0
        for exec_time, exec_qty, exec_price in rows:
            take_qty = min(exec_qty, max(qty - accum_qty, 0.0))
            if take_qty <= 0:
                continue
            accum_qty += take_qty
            notional += take_qty * exec_price
            oldest_time = exec_time
            if accum_qty >= qty * 0.999:
                break
        if accum_qty <= 0:
            return {}

        entry_dt = ''
        if oldest_time > 0:
            try:
                unit = 'ns' if oldest_time > 10**15 else 'ms'
                entry_dt = pd.to_datetime(oldest_time, unit=unit).strftime('%Y-%m-%d')
            except Exception:
                entry_dt = ''
        return {
            'entry': notional / accum_qty,
            'entry_dt': entry_dt,
            'recovered_from': 'bybit_executions',
        }

    def _float_or_none(value) -> float | None:
        if value in (None, ''):
            return None
        try:
            val = float(value)
        except Exception:
            return None
        return val if val == val else None

    def _row_float(row: dict, *keys: str) -> float | None:
        for key in keys:
            val = _float_or_none(row.get(key))
            if val is not None:
                return val
        return None

    def _row_time_ms(row: dict) -> int:
        for key in ('updatedTime', 'createdTime', 'execTime', 'execTimeNs'):
            raw = row.get(key)
            if raw in (None, ''):
                continue
            try:
                val = int(float(raw))
            except Exception:
                continue
            if val > 10**15:
                return val // 1_000_000
            return val
        return 0

    def _entry_floor_ms(entry_dt: str) -> int:
        if not entry_dt:
            return 0
        try:
            ts = pd.Timestamp(entry_dt)
            if ts.tzinfo is None:
                ts = ts.tz_localize('UTC')
            return int((ts - pd.Timedelta(days=1)).timestamp() * 1000)
        except Exception:
            return 0

    def _meta_to_position(sym: str, meta: dict) -> dict | None:
        try:
            direction = int(meta.get('direction') or meta.get('dir') or 0)
            qty = float(meta.get('qty') or 0.0)
            entry = float(meta.get('entry') or 0.0)
        except Exception:
            return None
        if direction not in (1, -1) or qty <= 0 or entry <= 0:
            return None
        return {
            'dir': direction,
            'qty': qty,
            'entry': entry,
            'sl': float(meta.get('sl') or meta.get('orig_sl') or 0.0),
            'tp': float(meta.get('tp') or 0.0),
            'orig_sl': float(meta.get('orig_sl') or meta.get('sl') or 0.0),
            'strategy': meta.get('strategy', 'unknown'),
            'entry_dt': meta.get('entry_dt', ''),
            'score': meta.get('score', 0),
            'entry_reason': meta.get('entry_reason', ''),
            'entry_order_id': meta.get('entry_order_id', ''),
        }

    def _ledger_exit_recorded(sym: str, order_id: str = '') -> bool:
        if not order_id:
            return False
        try:
            with get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT id FROM bybit_live_orders
                    WHERE action = 'EXIT' AND symbol = ? AND order_id = ?
                    LIMIT 1
                    """,
                    (sym, str(order_id)),
                ).fetchone()
            return row is not None
        except Exception as exc:
            print(f'  [LEDGER WARN] {sym}: duplicate check failed: {exc}')
            return False

    def _ledger_entry_recorded(sym: str, pos: dict, order_id: str = '') -> bool:
        try:
            with get_connection() as conn:
                if order_id:
                    row = conn.execute(
                        """
                        SELECT id FROM bybit_live_orders
                        WHERE action = 'ENTRY' AND symbol = ? AND order_id = ?
                        LIMIT 1
                        """,
                        (sym, str(order_id)),
                    ).fetchone()
                    if row is not None:
                        return True
                qty = abs(float(pos.get('qty') or 0.0))
                price = float(pos.get('entry') or 0.0)
                direction = int(pos.get('dir') or 0)
                qty_tol = max(qty * 0.001, 1e-12)
                price_tol = max(abs(price) * 0.001, 1e-12)
                row = conn.execute(
                    """
                    SELECT id FROM bybit_live_orders
                    WHERE action = 'ENTRY'
                      AND symbol = ?
                      AND direction = ?
                      AND ABS(COALESCE(quantity, 0) - ?) <= ?
                      AND ABS(COALESCE(price, 0) - ?) <= ?
                    LIMIT 1
                    """,
                    (sym, direction, qty, qty_tol, price, price_tol),
                ).fetchone()
            return row is not None
        except Exception as exc:
            print(f'  [LEDGER WARN] {sym}: entry duplicate check failed: {exc}')
            return False

    def _ledger_matching_entry(sym: str, pos: dict, order_id: str = '') -> dict:
        try:
            with get_connection() as conn:
                if order_id:
                    row = conn.execute(
                        """
                        SELECT stop_loss, take_profit, strategy, score,
                               signal_date, recorded_at, reason, order_id
                        FROM bybit_live_orders
                        WHERE action = 'ENTRY' AND symbol = ? AND order_id = ?
                        ORDER BY recorded_at DESC, id DESC
                        LIMIT 1
                        """,
                        (sym, str(order_id)),
                    ).fetchone()
                    if row is not None:
                        return {
                            'sl': row[0],
                            'tp': row[1],
                            'strategy': row[2] or 'unknown',
                            'score': row[3],
                            'entry_dt': row[4] or '',
                            'recorded_at': row[5] or '',
                            'entry_reason': row[6] or '',
                            'entry_order_id': row[7] or '',
                        }

                qty = abs(float(pos.get('qty') or 0.0))
                price = float(pos.get('entry') or 0.0)
                direction = int(pos.get('dir') or 0)
                qty_tol = max(qty * 0.001, 1e-12)
                price_tol = max(abs(price) * 0.002, 1e-12)
                row = conn.execute(
                    """
                    SELECT stop_loss, take_profit, strategy, score,
                           signal_date, recorded_at, reason, order_id
                    FROM bybit_live_orders
                    WHERE action = 'ENTRY'
                      AND symbol = ?
                      AND direction = ?
                      AND ABS(COALESCE(quantity, 0) - ?) <= ?
                      AND ABS(COALESCE(price, 0) - ?) <= ?
                    ORDER BY recorded_at DESC, id DESC
                    LIMIT 1
                    """,
                    (sym, direction, qty, qty_tol, price, price_tol),
                ).fetchone()
            if row is None:
                return {}
            return {
                'sl': row[0],
                'tp': row[1],
                'strategy': row[2] or 'unknown',
                'score': row[3],
                'entry_dt': row[4] or '',
                'recorded_at': row[5] or '',
                'entry_reason': row[6] or '',
                'entry_order_id': row[7] or '',
            }
        except Exception as exc:
            print(f'  [LEDGER WARN] {sym}: entry context lookup failed: {exc}')
            return {}

    def _local_iso_from_ms(value_ms: int) -> str:
        if value_ms <= 0:
            return ''
        try:
            dt = pd.to_datetime(value_ms, unit='ms', utc=True)
            tz = datetime.now().astimezone().tzinfo
            return dt.tz_convert(tz).to_pydatetime().isoformat(timespec='seconds')
        except Exception:
            return ''

    def _closed_pnl_close(sym: str, pos: dict) -> dict | None:
        getter = getattr(executor, 'get_closed_pnl', None)
        if getter is None:
            return None
        rows = getter(sym, limit=20)
        if not rows:
            return None
        floor_ms = _entry_floor_ms(pos.get('entry_dt', ''))
        pos_qty = abs(float(pos.get('qty') or 0.0))
        candidates = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            closed_at = _row_time_ms(row)
            if floor_ms and closed_at and closed_at < floor_ms:
                continue
            qty = _row_float(row, 'qty', 'closedSize') or pos_qty
            exit_price = _row_float(row, 'avgExitPrice', 'execPrice')
            if exit_price is None or exit_price <= 0:
                continue
            pnl = _row_float(row, 'closedPnl')
            close_fee = _row_float(row, 'closeFee', 'execFee')
            if close_fee is None:
                close_fee = _taker_fee(qty, exit_price)
            order_id = str(row.get('orderId') or '')
            qty_penalty = abs(qty - pos_qty) / pos_qty if pos_qty > 0 else 0.0
            candidates.append((closed_at, -qty_penalty, {
                'qty': qty,
                'price': exit_price,
                'pnl': pnl,
                'fee': abs(close_fee),
                'order_id': order_id,
                'closed_at': closed_at,
                'ret_msg': 'backfilled from Bybit execution and closed PnL',
                'raw': row,
            }))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return candidates[0][2]

    def _execution_close(sym: str, pos: dict) -> dict | None:
        direction = int(pos.get('dir') or 0)
        close_side = 'Sell' if direction == 1 else 'Buy'
        executions = executor.get_executions(sym, limit=100)
        floor_ms = _entry_floor_ms(pos.get('entry_dt', ''))
        rows = []
        for row in executions:
            if not isinstance(row, dict) or row.get('side') != close_side:
                continue
            exec_time = _row_time_ms(row)
            if floor_ms and exec_time and exec_time < floor_ms:
                continue
            qty = _row_float(row, 'execQty')
            price = _row_float(row, 'execPrice')
            if qty is None or price is None or qty <= 0 or price <= 0:
                continue
            fee = _row_float(row, 'execFee') or _taker_fee(qty, price)
            rows.append((exec_time, qty, price, abs(fee), str(row.get('orderId') or ''), row))
        if not rows:
            return None
        rows.sort(reverse=True)
        target_qty = abs(float(pos.get('qty') or 0.0))
        accum_qty = 0.0
        notional = 0.0
        fee_total = 0.0
        order_id = ''
        raw_rows = []
        for exec_time, qty, price, fee, row_order_id, raw in rows:
            take_qty = min(qty, max(target_qty - accum_qty, 0.0)) if target_qty > 0 else qty
            if take_qty <= 0:
                continue
            accum_qty += take_qty
            notional += take_qty * price
            fee_total += fee * (take_qty / qty)
            order_id = order_id or row_order_id
            raw_rows.append(raw)
            if target_qty > 0 and accum_qty >= target_qty * 0.999:
                break
        if accum_qty <= 0:
            return None
        exit_price = notional / accum_qty
        pnl = (
            (exit_price - float(pos.get('entry') or 0.0))
            * accum_qty
            * direction
        )
        return {
            'qty': accum_qty,
            'price': exit_price,
            'pnl': pnl,
            'fee': fee_total,
            'order_id': order_id,
            'closed_at': rows[0][0],
            'ret_msg': 'backfilled from Bybit execution',
            'raw': {'executions': raw_rows},
        }

    def _find_remote_close(sym: str, pos: dict) -> dict | None:
        return _closed_pnl_close(sym, pos) or _execution_close(sym, pos)

    def _entry_fill(sym: str, pos: dict) -> dict:
        direction = int(pos.get('dir') or 0)
        entry_side = 'Buy' if direction == 1 else 'Sell'
        target_qty = abs(float(pos.get('qty') or 0.0))
        rows = []
        for row in executor.get_executions(sym, limit=100):
            if not isinstance(row, dict) or row.get('side') != entry_side:
                continue
            if str(row.get('execType') or '').lower() == 'funding':
                continue
            if str(row.get('orderType') or '').upper() == 'UNKNOWN':
                continue
            qty = _row_float(row, 'execQty')
            price = _row_float(row, 'execPrice')
            if qty is None or price is None or qty <= 0 or price <= 0:
                continue
            fee = _row_float(row, 'execFee') or _taker_fee(qty, price)
            rows.append((
                _row_time_ms(row),
                qty,
                price,
                abs(fee),
                str(row.get('orderId') or ''),
                row,
            ))
        rows.sort(reverse=True)

        accum_qty = 0.0
        notional = 0.0
        fee_total = 0.0
        order_id = str(pos.get('entry_order_id') or '')
        raw_rows = []
        first_ms = 0
        for exec_time, qty, price, fee, row_order_id, raw in rows:
            take_qty = min(qty, max(target_qty - accum_qty, 0.0)) if target_qty > 0 else qty
            if take_qty <= 0:
                continue
            accum_qty += take_qty
            notional += take_qty * price
            fee_total += fee * (take_qty / qty)
            order_id = order_id or row_order_id
            raw_rows.append(raw)
            first_ms = exec_time
            if target_qty > 0 and accum_qty >= target_qty * 0.999:
                break

        if accum_qty > 0:
            return {
                'qty': accum_qty,
                'price': notional / accum_qty,
                'fee': fee_total,
                'order_id': order_id,
                'entry_ms': first_ms,
                'ret_msg': 'backfilled from Bybit execution',
                'raw': {'executions': raw_rows},
            }

        return {
            'qty': target_qty,
            'price': float(pos.get('entry') or 0.0),
            'fee': _taker_fee(target_qty, pos.get('entry')),
            'order_id': order_id,
            'entry_ms': _entry_floor_ms(pos.get('entry_dt', '')),
            'ret_msg': 'backfilled from remote Bybit position',
            'raw': {},
        }

    def _record_missing_entry(sym: str, pos: dict) -> None:
        fill = _entry_fill(sym, pos)
        if not fill.get('qty') or not fill.get('price'):
            return
        order_id = str(fill.get('order_id') or '')
        ledger_pos = dict(pos)
        ledger_pos['qty'] = fill.get('qty')
        ledger_pos['entry'] = fill.get('price')
        if _ledger_entry_recorded(sym, ledger_pos, order_id):
            return
        entry_ms = int(fill.get('entry_ms') or 0)
        response = {
            'retCode': 0,
            'retMsg': fill.get('ret_msg') or 'backfilled from Bybit execution',
            'result': {'orderId': order_id},
            'raw': fill.get('raw') or {},
        }
        row_id = _record_live_order(
            'ENTRY',
            sym,
            int(pos.get('dir') or 0),
            fill.get('qty'),
            fill.get('price'),
            response=response,
            reason=pos.get('entry_reason') or 'backfilled from Bybit execution',
            stop_loss=pos.get('sl'),
            take_profit=pos.get('tp'),
            strategy=pos.get('strategy', ''),
            score=pos.get('score'),
            signal_date=pos.get('entry_dt') or _date_from_ms(entry_ms),
            fee=fill.get('fee'),
            recorded_at=_local_iso_from_ms(entry_ms),
        )
        if row_id is None:
            return
        if order_id:
            pos['entry_order_id'] = order_id
            if sym in open_pos:
                open_pos[sym]['entry_order_id'] = order_id
            if sym in live_meta:
                live_meta[sym]['entry_order_id'] = order_id
                _save_live_meta(live_meta)
        print(f'  [LEDGER] backfilled missing entry for {sym}')

    def _remote_close_reason(pos: dict, close: dict) -> str:
        sl = float(pos.get('sl') or pos.get('orig_sl') or 0.0)
        price = float(close.get('price') or 0.0)
        direction = int(pos.get('dir') or 0)
        if sl <= 0 or price <= 0 or direction not in (1, -1):
            return 'REMOTE_CLOSED'
        tolerance = max(abs(sl) * 0.005, 1e-12)
        if direction == 1 and price <= sl + tolerance:
            return 'REMOTE_CLOSED_SL'
        if direction == -1 and price >= sl - tolerance:
            return 'REMOTE_CLOSED_SL'
        return 'REMOTE_CLOSED'

    def _record_remote_close(sym: str, pos: dict, close: dict) -> bool:
        order_id = str(close.get('order_id') or '')
        if _ledger_exit_recorded(sym, order_id):
            print(f'  [LEDGER] EXIT {sym} already recorded order_id={order_id}')
            return True
        qty = close.get('qty') or pos.get('qty')
        price = close.get('price') or pos.get('last_price') or pos.get('entry')
        pnl = close.get('pnl')
        if pnl is None:
            try:
                pnl = (
                    (float(price) - float(pos.get('entry') or 0.0))
                    * float(qty or 0.0)
                    * int(pos.get('dir') or 0)
                )
            except Exception:
                pnl = None
        reason = _remote_close_reason(pos, close)
        response = {
            'retCode': 0,
            'retMsg': close.get('ret_msg') or 'remote position closed',
            'result': {'orderId': order_id},
            'raw': close.get('raw') or {},
        }
        row_id = _record_live_order(
            'EXIT',
            sym,
            int(pos.get('dir') or 0),
            qty,
            price,
            response=response,
            reason=reason,
            stop_loss=pos.get('sl'),
            take_profit=pos.get('tp'),
            strategy=pos.get('strategy', ''),
            score=pos.get('score'),
            signal_date=pos.get('entry_dt', ''),
            pnl=pnl,
            fee=close.get('fee') or _taker_fee(qty, price),
            recorded_at=_local_iso_from_ms(int(close.get('closed_at') or 0)),
        )
        if row_id is None:
            return False
        if pnl is not None:
            trade_history.setdefault(sym, []).append(ClosedTradeStub(pnl))
        remote_closed_symbols.add(sym)
        return True

    def _date_from_ms(value_ms: int) -> str:
        if value_ms <= 0:
            return ''
        try:
            return pd.to_datetime(value_ms, unit='ms', utc=True).strftime('%Y-%m-%d')
        except Exception:
            return ''

    def _backfill_recent_closed_pnl(remote_symbols: set[str]) -> None:
        getter = getattr(executor, 'get_closed_pnl', None)
        if getter is None:
            return
        rows = getter(None, limit=50)
        if not rows:
            return
        for row in sorted(rows, key=_row_time_ms):
            if not isinstance(row, dict):
                continue
            closed_at = _row_time_ms(row)
            bybit_sym = str(row.get('symbol') or '').strip()
            if not bybit_sym:
                continue
            sym = f'BYBIT:{bybit_sym}.P'
            order_id = str(row.get('orderId') or '')
            if _ledger_exit_recorded(sym, order_id):
                continue
            close_side = str(row.get('side') or '')
            direction = -1 if close_side == 'Buy' else (1 if close_side == 'Sell' else 0)
            qty = _row_float(row, 'qty', 'closedSize')
            entry_price = _row_float(row, 'avgEntryPrice')
            exit_price = _row_float(row, 'avgExitPrice')
            if direction == 0 or qty is None or exit_price is None:
                continue
            pnl = _row_float(row, 'closedPnl')
            fee = _row_float(row, 'closeFee', 'execFee') or _taker_fee(qty, exit_price)
            entry_pos = {
                'dir': direction,
                'qty': qty,
                'entry': entry_price or exit_price,
            }
            entry_ctx = _ledger_matching_entry(sym, entry_pos)
            if not entry_ctx:
                continue
            meta = {**entry_ctx, **_position_meta(sym)}
            reason = 'REMOTE_CLOSED_SL' if pnl is not None and pnl < 0 else 'REMOTE_CLOSED'
            response = {
                'retCode': 0,
                'retMsg': 'backfilled from Bybit execution and closed PnL',
                'result': {'orderId': order_id},
                'raw': row,
            }
            row_id = _record_live_order(
                'EXIT',
                sym,
                direction,
                qty,
                exit_price,
                response=response,
                reason=reason,
                stop_loss=meta.get('sl') or (exit_price if reason == 'REMOTE_CLOSED_SL' else None),
                take_profit=meta.get('tp'),
                strategy=meta.get('strategy', 'unknown'),
                score=meta.get('score'),
                signal_date=meta.get('entry_dt') or _date_from_ms(
                    _row_time_ms({'updatedTime': row.get('createdTime')})
                ),
                pnl=pnl,
                fee=abs(fee),
                recorded_at=_local_iso_from_ms(closed_at),
            )
            if row_id is None:
                continue
            if pnl is not None:
                trade_history.setdefault(sym, []).append(ClosedTradeStub(pnl))
            remote_closed_symbols.add(sym)
            if sym not in remote_symbols:
                _forget_position(sym)
            entry_txt = f' entry={entry_price}' if entry_price is not None else ''
            print(
                f'  [LEDGER] backfilled recent closed PnL for {sym}'
                f'{entry_txt} exit={exit_price} pnl={pnl}'
            )

    def _backfill_entries_for_unpaired_exits() -> None:
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT symbol, direction, quantity, price, stop_loss,
                           take_profit, strategy, score, signal_date, order_id
                    FROM bybit_live_orders
                    WHERE action = 'EXIT'
                    ORDER BY recorded_at DESC, id DESC
                    LIMIT 50
                    """
                ).fetchall()
        except Exception as exc:
            print(f'  [LEDGER WARN] exit entry-pair scan failed: {exc}')
            return

        for row in rows:
            sym = str(row[0] or '')
            direction = int(row[1] or 0)
            qty = float(row[2] or 0.0)
            exit_price = float(row[3] or 0.0)
            if not sym or direction not in (1, -1) or qty <= 0:
                continue
            pos = {
                'dir': direction,
                'qty': qty,
                'entry': exit_price,
                'sl': row[4],
                'tp': row[5],
                'strategy': row[6] or 'unknown',
                'score': row[7],
                'entry_dt': row[8] or '',
                'entry_reason': 'backfilled from paired exit',
                'entry_order_id': '',
            }
            if _ledger_entry_recorded(sym, pos):
                continue
            exit_order_id = str(row[9] or '')
            closed_rows = executor.get_closed_pnl(sym, limit=20)
            matched = None
            for closed in closed_rows:
                if str(closed.get('orderId') or '') == exit_order_id:
                    matched = closed
                    break
            if matched is not None:
                entry_price = _row_float(matched, 'avgEntryPrice')
                if entry_price is not None and entry_price > 0:
                    pos['entry'] = entry_price
            _record_missing_entry(sym, pos)

    def _backfill_missing_meta_closures(remote_symbols: set[str]) -> None:
        for sym, meta in list(live_meta.items()):
            if sym in open_pos or sym in remote_symbols:
                continue
            if not isinstance(meta, dict):
                continue
            pos = _meta_to_position(sym, meta)
            if pos is None:
                print(f'  [LEDGER WARN] {sym}: stale metadata is incomplete; keeping it')
                continue
            close = _find_remote_close(sym, pos)
            if close is None:
                print(f'  [LEDGER WARN] {sym}: no Bybit close record found; keeping metadata')
                continue
            if _record_remote_close(sym, pos, close):
                print(f'  [LEDGER] backfilled missing remote close for {sym}')
                _forget_position(sym)
    # open_pos stores local state for exchange-protected positions.

    def _normalise_remote_position(p: dict) -> tuple[str, dict] | None:
        qty = float(p.get('size', 0) or 0)
        if qty <= 0:
            return None
        sys_sym = f"BYBIT:{p.get('symbol', '')}.P"
        if sys_sym not in cryptos:
            return None
        side = p.get('side', '')
        direction = 1 if side == 'Buy' else (-1 if side == 'Sell' else 0)
        if direction == 0:
            return None
        entry = float(p.get('avgPrice') or 0.0)
        sl = float(p.get('stopLoss') or 0.0)
        tp = float(p.get('takeProfit') or 0.0)
        mark_price = float(p.get('markPrice') or 0.0)
        meta = _position_meta(sys_sym)
        recovered = {}
        if not meta:
            recovered = _recover_entry_from_executions(sys_sym, qty, direction)
        entry_dt = meta.get('entry_dt') or recovered.get('entry_dt', '')
        strategy = meta.get('strategy', 'unknown')
        score = int(meta.get('score', 0) or 0)
        entry_reason = meta.get('entry_reason', '')
        orig_sl = float(meta.get('orig_sl') or sl or 0.0)
        trail_anchor = float(meta.get('trail_anchor') or entry or 0.0)
        if recovered.get('entry') and not meta.get('entry'):
            entry = float(recovered['entry'])
        return sys_sym, {
            'dir': direction,
            'qty': qty,
            'sl': sl,
            'tp': tp,
            'entry': entry,
            'orig_sl': orig_sl,
            'trail_anchor': trail_anchor,
            'strategy': strategy,
            'entry_dt': entry_dt,
            'score': score,
            'entry_reason': entry_reason,
            'entry_order_id': meta.get('entry_order_id', ''),
            'exit_order_id': meta.get('exit_order_id', ''),
            'last_price': mark_price or entry,
        }

    def _sync_remote_positions() -> None:
        remote = {}
        remote_symbols = set()
        raw_positions = executor.get_positions()
        positions_error = ''
        err_getter = getattr(executor, 'last_positions_error', None)
        if err_getter is not None:
            positions_error = err_getter() or ''
        for p in raw_positions:
            try:
                qty = float(p.get('size', 0) or 0)
            except Exception:
                qty = 0.0
            if qty > 0:
                remote_sym = f"BYBIT:{p.get('symbol', '')}.P"
                remote_symbols.add(remote_sym)
                _ensure_live_context_symbol(remote_sym, 'remote positions')
            item = _normalise_remote_position(p)
            if item is not None:
                remote[item[0]] = item[1]
        for sym in list(open_pos):
            if sym not in remote_symbols:
                pos = open_pos[sym]
                close = _find_remote_close(sym, pos)
                if close is None:
                    exit_price = (
                        executor.get_last_price(sym)
                        or pos.get('last_price')
                        or pos.get('entry')
                        or 0.0
                    )
                    try:
                        pnl = (
                            (float(exit_price) - float(pos.get('entry') or 0.0))
                            * float(pos.get('qty') or 0.0)
                            * int(pos.get('dir') or 0)
                        )
                    except Exception:
                        pnl = None
                    close = {
                        'qty': pos.get('qty'),
                        'price': exit_price,
                        'pnl': pnl,
                        'fee': _taker_fee(pos.get('qty'), exit_price),
                        'ret_msg': 'remote position closed',
                    }
                if _record_remote_close(sym, pos, close):
                    del open_pos[sym]
                    _forget_position(sym)
        for sym, pos in remote.items():
            if sym in open_pos:
                open_pos[sym].update({
                    'qty': pos['qty'],
                    'tp': pos['tp'],
                    'entry': pos['entry'] or open_pos[sym].get('entry', 0.0),
                })
                if pos['sl'] > 0:
                    open_pos[sym]['sl'] = pos['sl']
                if pos.get('last_price'):
                    open_pos[sym]['last_price'] = pos['last_price']
                for key in ('strategy', 'entry_dt', 'score', 'entry_reason',
                            'entry_order_id', 'orig_sl', 'trail_anchor'):
                    if pos.get(key) and not open_pos[sym].get(key):
                        open_pos[sym][key] = pos[key]
                _remember_position(sym, open_pos[sym])
            else:
                open_pos[sym] = pos
                _remember_position(sym, pos)
            _record_missing_entry(sym, open_pos[sym])
        if positions_error:
            print('  [LEDGER WARN] skip missing-position backfill; Bybit position sync failed')
        else:
            _backfill_missing_meta_closures(remote_symbols)
            _backfill_recent_closed_pnl(remote_symbols)
            _backfill_entries_for_unpaired_exits()
    open_pos: dict[str, dict] = {}  # symbol → {dir, qty, sl, tp, entry}

    print('正在同步交易所持倉狀態...')
    try:
        for p in executor.get_positions():
            qty = float(p.get('size', 0))
            if qty > 0:
                sys_sym = f"BYBIT:{p.get('symbol', '')}.P"
                if sys_sym in cryptos:
                    side = p.get('side', '')
                    direction = 1 if side == 'Buy' else (-1 if side == 'Sell' else 0)
                    if direction != 0:
                        open_pos[sys_sym] = {
                            'dir': direction,
                            'qty': qty,
                            'sl': float(p.get('stopLoss') or 0.0),
                            'tp': float(p.get('takeProfit') or 0.0),
                            'entry': float(p.get('avgPrice') or 0.0),
                            'last_price': float(p.get('markPrice') or 0.0),
                            'strategy': 'unknown',
                            'entry_dt': '',
                        }
                        meta = _position_meta(sys_sym)
                        if meta:
                            open_pos[sys_sym].update({
                                'strategy': meta.get('strategy', 'unknown'),
                                'entry_dt': meta.get('entry_dt', ''),
                                'score': meta.get('score', 0),
                                'entry_reason': meta.get('entry_reason', ''),
                                'entry_order_id': meta.get('entry_order_id', ''),
                                'orig_sl': meta.get('orig_sl', open_pos[sys_sym]['sl']),
                                'trail_anchor': meta.get('trail_anchor',
                                                         open_pos[sys_sym]['entry']),
                            })
                        else:
                            recovered = _recover_entry_from_executions(
                                sys_sym, qty, direction
                            )
                            if recovered.get('entry'):
                                open_pos[sys_sym]['entry'] = recovered['entry']
                            if recovered.get('entry_dt'):
                                open_pos[sys_sym]['entry_dt'] = recovered['entry_dt']
                        _remember_position(sys_sym, open_pos[sys_sym])
                        print(
                            f'  [同步] {sys_sym} {"做多" if direction==1 else "做空"} '
                            f'{_fmt_live_qty(qty)} 單位 '
                            f'投入資金={_position_invested_margin(open_pos[sys_sym]):.2f} USDT'
                        )
    except Exception as e:
        print(f'[WARN] 同步倉位失敗: {e}')

    for pos in open_pos.values():
        pos.setdefault('orig_sl', pos.get('sl', 0.0))
        pos.setdefault('trail_anchor', pos.get('entry', 0.0))
        pos.setdefault('strategy', 'unknown')
        pos.setdefault('entry_dt', '')
        pos.setdefault('entry_order_id', '')

    if getattr(args, 'sync_only', False):
        try:
            _sync_remote_positions()
        except Exception as e:
            print(f'[WARN] sync Bybit positions failed: {e}')
        export_bybit_live_orders_to_excel()
        _acct = getattr(executor, 'get_account_info', None)
        _acct = _acct() if _acct else {}
        balance = _acct.get('wallet_balance') or executor.get_balance()
        _print_open_positions(_acct)
        print('[INFO] sync-only complete; no new orders were placed.')
        return

    while True:
        try:
            _sync_remote_positions()
        except Exception as e:
            print(f'[WARN] sync Bybit positions failed: {e}')
        print(f'\n[{datetime.now():%Y-%m-%d %H:%M:%S}] 掃描中...')
        end_str   = datetime.now().strftime('%Y-%m-%d')

        data: dict[str, pd.DataFrame] = {}
        signals: dict[str, dict[str, pd.Series]] = {}

        for sym in cryptos:
            try:
                last = get_last_date(sym)
                if last is None:
                    start_inc = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
                else:
                    last_dt = datetime.strptime(last, '%Y-%m-%d')
                    start_inc = (last_dt + timedelta(days=1)).strftime('%Y-%m-%d')

                if datetime.strptime(start_inc, '%Y-%m-%d').date() <= datetime.now().date():
                    df_new = _download_single(sym, start_inc, end_str)
                    if df_new is not None and not df_new.empty:
                        upsert_prices(df_new, sym, asset_type_of(sym))

                df = load_prices(sym)
                if df is None or len(df) < config.EMA_PERIOD + 10:
                    continue
                df = _closed_daily_df(df)
                if df is None or len(df) < config.EMA_PERIOD + 10:
                    continue

                df = compute_all_indicators(df, include_vp=True)
                sigs = generate_all_signals(
                    df,
                    asset_type='Crypto',
                    benchmark_df=None,
                    moat_tf_only=True,
                )
                data[sym] = df
                signals[sym] = sigs
            except Exception as exc:
                print(f'  [ERROR] {sym}: {exc}')

        apply_cross_asset_filters(data, signals, type_map)
        candidates: list[tuple[str, int, int, str]] = []

        for sym, df in data.items():
            try:
                sigs = signals[sym]
                sig = sigs['combined']
                if len(sig) == 0:
                    continue

                latest_sig = int(sig.iloc[-1])
                score_val = int(sigs.get('score', pd.Series([0])).iloc[-1])
                signal_price = float(df['Close'].iloc[-1])
                price = signal_price
                dt_latest = df.index[-1]
                atr_raw = df['atr'].iloc[-1]
                atr = (float(atr_raw) if atr_raw is not None
                       and not pd.isna(atr_raw) else signal_price * 0.02)

                if sym in open_pos:
                    price = _live_price(sym, signal_price)
                    pos = open_pos[sym]
                    pos['last_price'] = price
                    pos.setdefault('orig_sl', pos.get('sl', 0.0))
                    pos.setdefault('trail_anchor', pos.get('entry', price))
                    pos.setdefault('strategy', 'unknown')
                    pos.setdefault('entry_dt', '')
                    pos.setdefault('entry_order_id', '')
                    if pos.get('strategy') == 'unknown' and pos.get('entry_dt'):
                        signal_dt = _signal_dt_at_or_before(sigs, pd.Timestamp(pos['entry_dt']))
                        if signal_dt is not None:
                            sig_at_entry = int(sigs['combined'].loc[signal_dt])
                            if sig_at_entry == pos['dir']:
                                entry_score = int(sigs.get('score', pd.Series([0])).loc[signal_dt])
                                inferred = _dominant_strategy_at(sigs, signal_dt, pos['dir'])
                                pos['strategy'] = inferred
                                pos['score'] = entry_score
                                pos['entry_reason'] = (
                                    f'inferred:{inferred} score={entry_score} '
                                    f'signal_dt={signal_dt:%Y-%m-%d}'
                                )
                                print(f'  [META] {sym} inferred {pos["entry_reason"]}')
                                _remember_position(sym, pos)
                    orig_sl = pos.get('orig_sl') or pos.get('sl') or 0.0
                    if orig_sl <= 0:
                        fallback_sl, fallback_tp = calculate_stops(
                            pos['entry'], pos['dir'], atr,
                            strategy=pos.get('strategy', 'trend'),
                            asset_type='Crypto',
                        )
                        orig_sl = fallback_sl
                        pos['orig_sl'] = fallback_sl
                        if pos.get('sl', 0.0) <= 0:
                            pos['sl'] = fallback_sl
                        if pos.get('tp', 0.0) <= 0:
                            pos['tp'] = fallback_tp
                        executor.set_trading_stop(
                            sym,
                            stop_loss=executor.format_price(sym, pos['sl']),
                            take_profit=executor.format_price(sym, pos['tp']),
                        )

                    r_dist = abs(pos['entry'] - orig_sl)
                    profit_r = 0.0
                    if r_dist > 0:
                        profit_r = ((price - pos['entry']) / r_dist
                                    if pos['dir'] == 1
                                    else (pos['entry'] - price) / r_dist)

                    new_sl = None
                    if not (config.STRAT_BB_DISABLE_TSL and pos.get('strategy') == 'bb'):
                        tight_after = _cls_get('TSL_TIGHT_AFTER_R_BY_CLASS',
                                               'Crypto', config.TSL_TIGHT_AFTER_R)
                        trail_mult = (config.TSL_TIGHT_ATR_MULT
                                      if tight_after > 0 and profit_r >= tight_after
                                      else config.ATR_STOP_MULTIPLIER)
                        trail_dist = atr * trail_mult
                        if pos['dir'] == 1:
                            anchor = max(pos.get('trail_anchor', pos['entry']), price)
                            pos['trail_anchor'] = anchor
                            candidate_sl = anchor - trail_dist
                            if candidate_sl > pos.get('sl', 0.0) and candidate_sl > pos['entry']:
                                new_sl = candidate_sl
                        else:
                            anchor = min(pos.get('trail_anchor', pos['entry']), price)
                            pos['trail_anchor'] = anchor
                            candidate_sl = anchor + trail_dist
                            cur_sl = pos.get('sl', 0.0)
                            if candidate_sl < cur_sl and candidate_sl < pos['entry']:
                                new_sl = candidate_sl

                    if new_sl is not None:
                        sl_str = executor.format_price(sym, new_sl)
                        tp_val = pos.get('tp') or None
                        tp_str = executor.format_price(sym, tp_val) if tp_val else None
                        executor.set_trading_stop(sym, stop_loss=sl_str, take_profit=tp_str)
                        pos['sl'] = float(sl_str)
                        _remember_position(sym, pos)
                        print(f'  [TSL] {sym} stopLoss -> {sl_str}')

                    hold_days = 0
                    if pos.get('entry_dt'):
                        try:
                            hold_days = (dt_latest - pd.Timestamp(pos['entry_dt'])).days
                        except Exception:
                            hold_days = 0
                    min_hold_ok = hold_days >= config.MIN_HOLD_DAYS

                    early_exit = None
                    if pos.get('strategy') == 'bb' and min_hold_ok:
                        bb_mid = float(df['bb_mid'].iloc[-1]) if 'bb_mid' in df.columns else None
                        rsi_now = float(df['rsi'].iloc[-1]) if 'rsi' in df.columns else None
                        profit_pct = (price / pos['entry'] - 1.0) * pos['dir']
                        if profit_pct >= config.STRAT_BB_PROFIT_PCT:
                            early_exit = 'BB-TGT'
                        elif bb_mid is not None and (
                                (pos['dir'] == 1 and price >= bb_mid) or
                                (pos['dir'] == -1 and price <= bb_mid)):
                            early_exit = 'BB-MID'
                        elif rsi_now is not None and (
                                (pos['dir'] == 1 and rsi_now >= config.STRAT_BB_RSI_EXIT) or
                                (pos['dir'] == -1 and rsi_now <= config.STRAT_BB_RSI_EXIT)):
                            early_exit = 'BB-RSI'

                    if config.SOFT_STOP_PCT > 0 and min_hold_ok:
                        unrealised_pct = (price / pos['entry'] - 1.0) * pos['dir']
                        if unrealised_pct <= -config.SOFT_STOP_PCT:
                            early_exit = 'SOFT'

                    max_hold_class = _cls_get('MAX_HOLD_DAYS_BY_CLASS',
                                              'Crypto', config.MAX_HOLD_DAYS)
                    if max_hold_class > 0 and hold_days >= max_hold_class:
                        early_exit = 'MAXHOLD'

                    # Authoritative same-process exit arbitration via the shared
                    # pure core. It receives the already-computed live price,
                    # current (possibly trailed) SL/TP, latest combined signal,
                    # the min-hold gate and the resolved early-exit label, and
                    # returns HOLD or CLOSE with the exact production reason
                    # ('SL' > 'TP' > early-exit label > 'FLIP'). Trailing-stop
                    # mutation (above) and remote/backfill reconciliation stay
                    # OUTSIDE the core; no second inline SL/TP/early/FLIP copy
                    # remains here.
                    exit_decision = decide_exit(ExitDecisionInput(
                        symbol=sym,
                        direction=pos['dir'],
                        current_price=price,
                        stop_loss=pos['sl'],
                        take_profit=pos['tp'],
                        combined_signal=latest_sig,
                        min_hold_ok=min_hold_ok,
                        early_exit=early_exit,
                    ))
                    if exit_decision.action is ExitAction.CLOSE:
                        close_res = executor.close_position(sym, pos['qty'], pos['dir']) or {}
                        if close_res.get('retCode') != 0:
                            print(f'  [CLOSE FAIL] {sym}: {close_res.get("retMsg", close_res)}')
                            continue
                        pnl = (price - pos['entry']) * pos['qty'] * pos['dir']
                        trade_history[sym].append(ClosedTradeStub(pnl))
                        reason = exit_decision.close_reason
                        _record_live_order(
                            'EXIT',
                            sym,
                            pos['dir'],
                            pos['qty'],
                            price,
                            response=close_res,
                            reason=reason,
                            stop_loss=pos.get('sl'),
                            take_profit=pos.get('tp'),
                            strategy=pos.get('strategy', ''),
                            score=pos.get('score'),
                            signal_date=dt_latest.strftime('%Y-%m-%d'),
                            pnl=pnl,
                            fee=_taker_fee(pos.get('qty'), price),
                        )
                        print(f'  平倉 {sym} @ {price:.4f}  PnL={pnl:+.2f}  ({reason})')
                        # SR-101D2 shadow parity seam (observational only). Emits
                        # ONE authoritative same-process close event AFTER the
                        # legacy EXIT ledger record + gross ClosedTradeStub are
                        # already written. Default-disabled: does nothing unless an
                        # observer is injected via args. Never influences close
                        # execution, ledger reason, re-entry, or Kelly sizing.
                        _close_event_observer = getattr(
                            args, '_trade_history_close_event_observer', None)
                        if callable(_close_event_observer):
                            _cres = close_res.get('result') if isinstance(close_res, dict) else {}
                            _order_id = _cres.get('orderId', '') if isinstance(_cres, dict) else ''
                            _close_event_observer({
                                'symbol': sym,
                                'direction': pos['dir'],
                                'quantity': pos['qty'],
                                'entry_price': pos['entry'],
                                'exit_price': price,
                                'exit_timestamp': _shadow_close_event_now(),
                                'close_reason': reason,
                                'strategy_family': pos.get('strategy', ''),
                                'fee': _taker_fee(pos.get('qty'), price),
                                'order_id': _order_id,
                            })
                        del open_pos[sym]
                        _forget_position(sym)
                        if reason != 'FLIP':
                            _block_reentry(sym, dt_latest, reason)

                min_score_class = _cls_get('MIN_ENTRY_SCORE_BY_CLASS',
                                            'Crypto', config.MIN_ENTRY_SCORE)
                if sym in remote_closed_symbols:
                    remote_closed_symbols.discard(sym)
                    _block_reentry(sym, dt_latest, 'remote position closed')
                # Authoritative per-symbol entry eligibility via the shared pure
                # core, resolved in STAGES so later gates -- and the
                # potentially-exception-raising family-signal reads -- are only
                # touched once every earlier gate has already passed, exactly
                # mirroring the original short-circuiting `and` chain:
                #   tradable and not-open and signal!=0 and score>=min
                #   and not reentry_blocked and sym_wr_ok
                # Each stage calls the SAME decide_entry; unresolved fields carry
                # neutral placeholders that can never themselves cause a HOLD
                # (reentry_blocked=False, symbol_winrate_ok=True, family
                # signals=0, cap=False), so a HOLD at any stage is genuinely
                # attributable to an already-resolved gate. Portfolio caps remain
                # cross-candidate state, applied at the phase-2 commit gate below.
                stage_input = EntryDecisionInput(
                    symbol=sym,
                    asset_class='Crypto',
                    combined_signal=latest_sig,
                    score=score_val,
                    trend_signal=0,
                    volume_profile_signal=0,
                    bollinger_signal=0,
                    minimum_score=min_score_class,
                    symbol_tradable=sym in crypto_tradable_symbols,
                    has_open_position=sym in open_pos,
                    reentry_blocked=False,
                    symbol_winrate_ok=True,
                    position_cap_reached=False,
                )
                # Stage 1: tradable / no existing position / signal / score.
                if decide_entry(stage_input).action is not EntryAction.ENTER:
                    continue
                # Stage 2: re-entry block.
                stage_input = _dc_replace(
                    stage_input, reentry_blocked=_reentry_blocked(sym, dt_latest))
                if decide_entry(stage_input).action is not EntryAction.ENTER:
                    continue
                # Stage 3: symbol win-rate gate.
                stage_input = _dc_replace(
                    stage_input, symbol_winrate_ok=_sym_wr_ok(sym))
                if decide_entry(stage_input).action is not EntryAction.ENTER:
                    continue
                # Stage 4: strategy-family latest signals -- read only now, for a
                # symbol that has already passed every earlier gate.
                entry_input = _dc_replace(
                    stage_input,
                    trend_signal=_latest_family_signal(sigs, 'trend'),
                    volume_profile_signal=_latest_family_signal(sigs, 'vp'),
                    bollinger_signal=_latest_family_signal(sigs, 'bb'),
                )
                decision = decide_entry(entry_input)
                if decision.action is EntryAction.ENTER:
                    candidates.append(
                        (sym, latest_sig, score_val,
                         decision.strategy_family, entry_input))
            except Exception as exc:
                print(f'  [ERROR] {sym}: {exc}')

        candidates.sort(key=lambda x: x[2], reverse=True)
        strat_counts: dict[str, int] = {}
        for pos in open_pos.values():
            strat = pos.get('strategy', 'unknown')
            strat_counts[strat] = strat_counts.get(strat, 0) + 1

        # Use Bybit's availableToWithdraw so margin sizing reflects actual reserved margin.
        # Decrement locally as orders are placed within this cycle.
        cycle_available = getattr(executor, 'get_available_balance', executor.get_balance)()

        for sym, latest_sig, score_val, strat, entry_input in candidates:
            # Authoritative commit gate: the SAME pure core, now with the
            # cross-candidate portfolio caps resolved from current cycle state
            # (global max positions OR per-family MAX_POS_PER_STRATEGY). A HOLD
            # here means the caps rejected this candidate -- no order is placed.
            # global_cap_reached and strategy_cap_reached are tracked SEPARATELY
            # (only their OR is passed to the shared core, which remains the sole
            # ENTER/HOLD authority) so the original control-flow distinction can
            # be restored below: the global cap stops processing every remaining
            # candidate (break), while a per-strategy cap only skips this one
            # (continue) -- exactly as the pre-extraction inline code did.
            global_cap_reached = len(open_pos) >= crypto_max_positions
            strat_limit = config.MAX_POS_PER_STRATEGY.get(strat) \
                          if config.MAX_POS_PER_STRATEGY else None
            strategy_cap_reached = (
                strat_limit is not None
                and strat_counts.get(strat, 0) >= strat_limit)
            commit_decision = decide_entry(_dc_replace(
                entry_input,
                has_open_position=sym in open_pos,
                position_cap_reached=global_cap_reached or strategy_cap_reached))
            if commit_decision.action is not EntryAction.ENTER:
                if global_cap_reached:
                    break
                continue
            try:
                df = data[sym]
                signal_price = float(df['Close'].iloc[-1])
                price = _live_price(sym, signal_price)
                atr_raw = df['atr'].iloc[-1]
                atr = (float(atr_raw) if atr_raw is not None
                       and not pd.isna(atr_raw) else signal_price * 0.02)
                atype = 'Crypto'
                sl, tp = calculate_stops(price, latest_sig, atr,
                                         strategy=strat, asset_type=atype)
                if config.ENABLE_GEOMETRIC_RR and not _geometric_rr_ok(
                        df, df.index[-1], latest_sig, tp, atr,
                        lookback=config.GEO_RR_LOOKBACK,
                        buffer_atr=config.GEO_RR_BUFFER_ATR):
                    continue

                kf = estimate_kelly_from_history(
                    trade_history[sym],
                    window=config.KELLY_WINDOW,
                    asset_type=atype,
                )
                lev = _crypto_leverage()
                available = max(0.0, cycle_available)
                qty = position_size(
                    available, kf, price, sl,
                    asset_type=atype,
                    max_position_pct=crypto_max_position_pct,
                )
                qty_str = executor.format_qty(sym, qty)
                order_qty = float(qty_str)
                sl_str = executor.format_price(sym, sl)
                tp_str = executor.format_price(sym, tp)
                margin_need = (order_qty * price) / lev
                if order_qty > 0 and margin_need <= available:
                    res = executor.place_order(sym, latest_sig, qty_str, sl_str, tp_str)
                    if res.get('retCode') == 0:
                        order_result = res.get('result') if isinstance(res, dict) else {}
                        entry_order_id = (
                            order_result.get('orderId', '')
                            if isinstance(order_result, dict) else ''
                        )
                        open_pos[sym] = {
                            'dir': latest_sig, 'qty': order_qty, 'sl': sl, 'tp': tp,
                            'entry': price, 'orig_sl': sl, 'trail_anchor': price,
                            'last_price': price,
                            'strategy': strat,
                            'score': score_val,
                            'entry_reason': f'{strat} score={score_val}',
                            'entry_dt': df.index[-1].strftime('%Y-%m-%d'),
                            'entry_order_id': entry_order_id,
                        }
                        _remember_position(sym, open_pos[sym])
                        _record_live_order(
                            'ENTRY',
                            sym,
                            latest_sig,
                            order_qty,
                            price,
                            response=res,
                            reason=f'{strat} score={score_val}',
                            stop_loss=sl_str,
                            take_profit=tp_str,
                            strategy=strat,
                            score=score_val,
                            signal_date=df.index[-1].strftime('%Y-%m-%d'),
                            fee=_taker_fee(order_qty, price),
                        )
                        strat_counts[strat] = strat_counts.get(strat, 0) + 1
                        cycle_available = max(0.0, cycle_available - margin_need)
                        print(f'  {"做多" if latest_sig==1 else "做空"} {sym} '
                              f'[{strat} score={score_val}] qty={qty_str} '
                              f'@ {price:.4f}  投入資金={margin_need:.2f} USDT '
                              f'SL={sl_str}  TP={tp_str}')
                    else:
                        print(f'  [ORDER FAIL] {sym}: {res.get("retMsg")}')
            except Exception as exc:
                print(f'  [ORDER ERROR] {sym}: {exc}')

        for sym in []:
            try:
                # 增量更新：只抓 DB 最後日期之後的新資料
                last = get_last_date(sym)
                if last is None:
                    start_inc = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
                else:
                    last_dt   = datetime.strptime(last, '%Y-%m-%d')
                    start_inc = (last_dt + timedelta(days=1)).strftime('%Y-%m-%d')

                if datetime.strptime(start_inc, '%Y-%m-%d').date() <= datetime.now().date():
                    df_new = _download_single(sym, start_inc, end_str)
                    if df_new is not None and not df_new.empty:
                        upsert_prices(df_new, sym, asset_type_of(sym))

                # 從 DB 載入完整歷史做指標
                df = load_prices(sym)
                if df is None or len(df) < config.EMA_PERIOD + 10:
                    continue

                df  = compute_all_indicators(df, include_vp=False)
                # 與回測一致的訊號參數（moat_tf_only=True；crypto 不受影響但保持參數對齊）
                sig = generate_all_signals(
                    df,
                    asset_type=asset_type_of(sym),
                    benchmark_df=None,
                    moat_tf_only=True,
                )['combined']

                if len(sig) == 0:
                    continue

                latest_sig = int(sig.iloc[-1])
                price      = float(df['Close'].iloc[-1])
                atr_raw    = df['atr'].iloc[-1]
                atr        = (float(atr_raw) if atr_raw is not None
                              and not pd.isna(atr_raw) else price * 0.02)

                # 管理現有倉位
                if sym in open_pos:
                    pos   = open_pos[sym]
                    pos.setdefault('orig_sl', pos.get('sl', 0.0))
                    pos.setdefault('trail_anchor', pos.get('entry', price))
                    orig_sl = pos.get('orig_sl') or pos.get('sl') or 0.0
                    if orig_sl <= 0:
                        fallback_sl, fallback_tp = calculate_stops(
                            pos['entry'], pos['dir'], atr, asset_type='Crypto'
                        )
                        orig_sl = fallback_sl
                        pos['orig_sl'] = fallback_sl
                        if pos.get('sl', 0.0) <= 0:
                            pos['sl'] = fallback_sl
                        if pos.get('tp', 0.0) <= 0:
                            pos['tp'] = fallback_tp
                        executor.set_trading_stop(
                            sym,
                            stop_loss=executor.format_price(sym, pos['sl']),
                            take_profit=executor.format_price(sym, pos['tp']),
                        )
                    r_dist = abs(pos['entry'] - orig_sl)
                    profit_r = 0.0
                    if r_dist > 0:
                        profit_r = ((price - pos['entry']) / r_dist
                                    if pos['dir'] == 1
                                    else (pos['entry'] - price) / r_dist)
                    tight_after = getattr(config, 'TSL_TIGHT_AFTER_R_BY_CLASS', {}).get(
                        'Crypto', config.TSL_TIGHT_AFTER_R
                    )
                    trail_mult = (config.TSL_TIGHT_ATR_MULT
                                  if tight_after > 0 and profit_r >= tight_after
                                  else config.ATR_STOP_MULTIPLIER)
                    trail_dist = atr * trail_mult
                    new_sl = None
                    if pos['dir'] == 1:
                        anchor = max(pos.get('trail_anchor', pos['entry']), price)
                        pos['trail_anchor'] = anchor
                        candidate = anchor - trail_dist
                        if candidate > pos.get('sl', 0.0) and candidate > pos['entry']:
                            new_sl = candidate
                    else:
                        anchor = min(pos.get('trail_anchor', pos['entry']), price)
                        pos['trail_anchor'] = anchor
                        candidate = anchor + trail_dist
                        cur_sl = pos.get('sl', 0.0)
                        if candidate < cur_sl and candidate < pos['entry']:
                            new_sl = candidate
                    if new_sl is not None:
                        sl_str = executor.format_price(sym, new_sl)
                        tp_val = pos.get('tp') or None
                        tp_str = executor.format_price(sym, tp_val) if tp_val else None
                        executor.set_trading_stop(sym, stop_loss=sl_str, take_profit=tp_str)
                        pos['sl'] = float(sl_str)
                        print(f'  [TSL] {sym} stopLoss -> {sl_str}')
                    hit_sl = (pos['dir'] ==  1 and price <= pos['sl']) or \
                             (pos['dir'] == -1 and price >= pos['sl'])
                    hit_tp = (pos['dir'] ==  1 and price >= pos['tp']) or \
                             (pos['dir'] == -1 and price <= pos['tp'])
                    if hit_sl or hit_tp or (latest_sig != 0 and latest_sig != pos['dir']):
                        close_res = executor.close_position(sym, pos['qty'], pos['dir']) or {}
                        if close_res.get('retCode') != 0:
                            print(f'  [CLOSE FAIL] {sym}: {close_res.get("retMsg", close_res)}')
                            continue
                        # 估算本筆損益並寫入 Kelly 樣本
                        pnl = (price - pos['entry']) * pos['qty'] * pos['dir']
                        trade_history[sym].append(ClosedTradeStub(pnl))
                        reason = 'SL' if hit_sl else ('TP' if hit_tp else 'FLIP')
                        print(f'  平倉 {sym} @ {price:.4f}  PnL={pnl:+.2f}  ({reason})')
                        del open_pos[sym]
                        _forget_position(sym)

                # 開新倉
                if (sym not in open_pos and latest_sig != 0
                        and len(open_pos) < crypto_max_positions):
                    atype = 'Crypto'   # live 模式只跑加密
                    kf  = estimate_kelly_from_history(trade_history[sym], asset_type=atype)
                    sl, tp = calculate_stops(price, latest_sig, atr, asset_type=atype)
                    lev_map = getattr(config, 'LEVERAGE_BY_CLASS', {})
                    lev     = lev_map.get(atype, 1.0)
                    # 用保證金口徑計算可用資金（Bybit 永續以保證金抵押）
                    allocated_margin = sum(
                        (p['entry'] * p['qty']) / lev for p in open_pos.values()
                    )
                    available = max(0.0, balance - allocated_margin)
                    qty = position_size(
                        available, kf, price, sl,
                        asset_type=atype,
                        max_position_pct=crypto_max_position_pct,
                    )
                    # 用 executor 提供的精度修正再下單
                    qty_str = executor.format_qty(sym, qty)
                    sl_str  = executor.format_price(sym, sl)
                    tp_str  = executor.format_price(sym, tp)
                    margin_need = (qty * price) / lev
                    if qty > 0 and margin_need <= available:        # 保證金夠才下單
                        res = executor.place_order(sym, latest_sig, qty_str, sl_str, tp_str)
                        if res.get('retCode') == 0:
                            open_pos[sym] = {'dir': latest_sig, 'qty': qty,
                                             'sl': sl, 'tp': tp, 'entry': price,
                                             'orig_sl': sl, 'trail_anchor': price}
                            print(f'  {"做多" if latest_sig==1 else "做空"} {sym} '
                                  f'qty={qty_str} @ {price:.4f}  SL={sl_str}  TP={tp_str}')
                        else:
                            print(f'  [ORDER FAIL] {sym}: {res.get("retMsg")}')

            except Exception as exc:
                print(f'  [ERROR] {sym}: {exc}')

        _acct = getattr(executor, 'get_account_info', None)
        _acct = _acct() if _acct else {}
        balance = _acct.get('wallet_balance') or executor.get_balance()
        _print_open_positions(_acct)
        export_bybit_live_orders_to_excel()
        time.sleep(args.interval * 60)


# ─── 輔助 ─────────────────────────────────────────────────────────────────────
def _print_asset_summary(assets: dict):
    print('\n=== 已選資產清單 ===')
    print(f'  美股 ({len(assets["us_stocks"])}):      {", ".join(assets["us_stocks"][:8])} ...')
    print(f'  台股 ({len(assets["tw_stocks"])}):      {", ".join(assets["tw_stocks"][:8])} ...')
    print(f'  加密幣 ({len(assets["cryptos"])}):   {", ".join(assets["cryptos"])}')
    print(f'  大宗商品 ({len(assets["commodities"])}): {", ".join(assets["commodities"])}')
    print(f'  合計: {len(assets["all"])} 個資產\n')


# ─── Argument Parser ──────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='量化交易系統',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest='command')

    # fetch
    p_fetch = sub.add_parser('fetch', help='下載歷史資料到 SQLite')
    p_fetch.add_argument('--years', type=int, default=5, help='下載年數 (default=5)')
    p_fetch.add_argument('--seed',  type=int, default=42, help='隨機種子')

    # update
    p_upd = sub.add_parser('update', help='增量更新：只補最新資料（平日收盤後執行）')
    p_upd.add_argument('--seed', type=int, default=42, help='隨機種子')

    # info
    sub.add_parser('info', help='顯示資料庫已下載資產資訊')

    # backtest
    p_bt = sub.add_parser('backtest', help='執行回測並輸出 Excel')
    p_bt.add_argument('--capital', type=float, default=100_000.0, help='初始資金 (USD)')
    p_bt.add_argument('--seed',    type=int,   default=42,        help='隨機種子')
    p_bt.add_argument('--with-vp', action=argparse.BooleanOptionalAction, default=True,
                      help='啟用 Volume Profile 策略（預設啟用；用 --no-with-vp 關閉）')
    p_bt.add_argument('--output',   type=str,  default=None,      help='自訂輸出路徑')
    p_bt.add_argument('--note',       type=str,  default='',        help='本次回測備註（儲存至 DB）')
    p_bt.add_argument('--ver',        type=str,  default=None,      help='版號（預設讀 config.SYSTEM_VERSION）')
    p_bt.add_argument('--start-date',    type=str,   default=None,   help='回測起始日（YYYY-MM-DD），指標仍用完整歷史暖身')
    p_bt.add_argument('--end-date',      type=str,   default=None,   help='回測結束日（YYYY-MM-DD）')
    p_bt.add_argument('--moat-tf-only', action=argparse.BooleanOptionalAction, default=True,
                      help='護城河只封鎖 Supertrend，VP/BB 豁免（預設啟用；用 --no-moat-tf-only 關閉）')
    p_bt.add_argument('--rs-pct',        type=float, default=None,   help='RS 豁免門檻（預設 0.03）')
    p_bt.add_argument('--profile',       type=str,   default=None,
                      help='只回測指定 strategy profile，例如 Crypto、TW Stock、US+Commodity')

    p_bt.add_argument('--crypto-candidate', type=str, default=DEFAULT_CRYPTO_CANDIDATE,
                      choices=[LEGACY_CRYPTO_BASELINE] + sorted(CRYPTO_CANDIDATES.keys()),
                      help='Crypto strategy mode. Default is volume-top125-lb3-sym035; use config-baseline for the legacy config universe.')
    p_bt.add_argument('--crypto-universe', type=str, default='config',
                      choices=['config', 'prev3y-mcap-top100', 'prev3y-volume-top100'],
                      help='Crypto backtest universe mode')
    p_bt.add_argument('--crypto-top-n', type=int, default=100,
                      help='Top N symbols for prev3y Top100 universe modes')
    p_bt.add_argument('--crypto-min-history-days', type=int, default=180,
                      help='Required pre-year OHLCV days for prev3y Top100 universe modes')

    # history
    p_hist = sub.add_parser('history', help='查詢歷史回測記錄')
    p_hist.add_argument('--limit',  type=int, default=20,   help='顯示最近幾筆（default=20）')
    p_hist.add_argument('--run-id', type=int, default=None, help='查看指定回測的交易明細')

    # live
    p_live = sub.add_parser('live', help='即時交易（Bybit 加密貨幣）')
    p_live.add_argument('--seed',     type=int, default=42, help='隨機種子')
    p_live.add_argument('--interval', type=int, default=15, help='掃描間隔（分鐘，default=15）')
    p_live.add_argument('--sync-only', action='store_true',
                        help='只同步 Bybit 倉位與 live Excel ledger，不掃描新訊號或下新單')
    p_live.add_argument('--crypto-candidate', type=str, default=DEFAULT_CRYPTO_CANDIDATE,
                        choices=[LEGACY_CRYPTO_BASELINE] + sorted(CRYPTO_CANDIDATES.keys()),
                        help='Crypto strategy mode. Default is volume-top125-lb3-sym035; use config-baseline for the legacy config universe.')

    return parser


def main():
    parser  = build_parser()
    args    = parser.parse_args()

    if args.command == 'fetch':
        cmd_fetch(args)
    elif args.command == 'update':
        cmd_update(args)
    elif args.command == 'info':
        cmd_info(args)
    elif args.command == 'backtest':
        cmd_backtest(args)
    elif args.command == 'history':
        cmd_history(args)
    elif args.command == 'live':
        try:
            cmd_live(args)
        except KeyboardInterrupt:
            print('\n[INFO] 已收到 Ctrl+C，live 模式已停止。')
            sys.exit(130)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
