#!/usr/bin/env python3
"""
量化交易系統 — 主程式入口

用法：
  python main.py fetch              # 下載 120 個資產的歷史資料至 SQLite
  python main.py fetch --years 3    # 只抓 3 年
  python main.py backtest           # 執行回測並輸出 Output.xlsx（Volume Profile 預設關閉）
  python main.py backtest --with-vp # 啟用 Volume Profile（速度較慢）
  python main.py live               # 即時交易（Bybit，僅加密貨幣）
  python main.py info               # 顯示已下載資產摘要
"""

import argparse
import sys
import os

# 確保根目錄在 path 上
sys.path.insert(0, os.path.dirname(__file__))


# ─── Sub-commands ─────────────────────────────────────────────────────────────
def cmd_fetch(args):
    from config import get_selected_assets
    from src.fetcher import fetch_all_assets
    assets = get_selected_assets(args.seed)
    _print_asset_summary(assets)
    fetch_all_assets(assets, years=args.years)


def cmd_update(args):
    from config import get_selected_assets
    from src.fetcher import update_all_assets
    assets = get_selected_assets(args.seed)
    update_all_assets(assets)


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
    from datetime import datetime, timedelta
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


def cmd_backtest(args):
    import pandas as pd
    from tqdm import tqdm
    import config
    from config import get_selected_assets
    from src.database import load_prices, get_all_symbols
    from src.indicators import compute_all_indicators
    from src.strategies import generate_all_signals
    from src.backtester import Backtester
    from src.reporter import generate_excel_report

    assets    = get_selected_assets(args.seed)
    available = set(get_all_symbols())

    if not available:
        print('資料庫為空，請先執行: python main.py fetch')
        return

    type_map: dict[str, str] = {}
    for sym in assets['us_stocks']:  type_map[sym] = 'US Stock'
    for sym in assets['tw_stocks']:  type_map[sym] = 'TW Stock'
    for sym in assets['cryptos']:    type_map[sym] = 'Crypto'
    for sym in assets['commodities']:type_map[sym] = 'Commodity'

    # 下載大盤基準指數（用於護城河濾網）
    print('\n下載大盤基準指數...')
    tw_benchmark = _load_benchmark(config.TW_MARKET_SYMBOL)
    us_benchmark = _load_benchmark(config.US_MARKET_SYMBOL)
    if tw_benchmark is not None:
        print(f'  ^TWII: {len(tw_benchmark)} 筆  ({tw_benchmark.index[0].date()} → {tw_benchmark.index[-1].date()})')
    else:
        print('  [WARN] 台股大盤指數載入失敗，台股護城河濾網停用')
    if us_benchmark is not None:
        print(f'  ^GSPC: {len(us_benchmark)} 筆  ({us_benchmark.index[0].date()} → {us_benchmark.index[-1].date()})')
    else:
        print('  [WARN] 美股大盤指數載入失敗，美股護城河濾網停用')

    selected = [s for s in assets['all'] if s in available]
    print(f'\n載入 {len(selected)} 個資產，計算指標與信號中...\n')

    data:    dict[str, pd.DataFrame]          = {}
    signals: dict[str, dict[str, pd.Series]] = {}
    skipped = 0

    use_vp = getattr(args, 'with_vp', False)
    if not use_vp:
        print('[INFO] Volume Profile 已停用（預設）；加 --with-vp 可啟用')

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
                moat_tf_only=getattr(args, 'moat_tf_only', False),
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

    bt     = Backtester(initial_capital=args.capital)
    trades = bt.run(data, signals, type_map)
    metrics = bt.get_metrics()

    # ── 印出績效摘要 ──────────────────────────────────────────────────────
    print('\n' + '='*48)
    print('  回測績效摘要')
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
    generate_excel_report(trades, metrics, bt.equity_curve, output_path)

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


def cmd_live(args):
    """
    即時交易迴圈：
    1. 抓最新 K 線資料
    2. 計算指標/信號
    3. 根據 1/4 Kelly 下單（Bybit，僅限加密貨幣）
    """
    import time
    import config
    from config import get_selected_assets
    from src.fetcher import _download_single
    from src.indicators import compute_all_indicators
    from src.strategies import generate_all_signals
    from src.risk import estimate_kelly_from_history, position_size, calculate_stops
    from src.executor import BybitExecutor

    try:
        executor = BybitExecutor()
    except RuntimeError as e:
        print(f'[ERROR] {e}')
        return

    assets   = get_selected_assets(args.seed)
    cryptos  = assets['cryptos']
    balance  = executor.get_balance()
    print(f'Bybit 餘額：{balance:.2f} USDT')
    print(f'監控 {len(cryptos)} 個加密貨幣 | 每 {args.interval} 分鐘掃描一次')
    print('[注意] 測試網模式：', config.BYBIT_TESTNET)

    from datetime import datetime, timedelta
    from src.database import upsert_prices, load_prices
    from src.fetcher import asset_type_of

    trade_history: dict[str, list] = {s: [] for s in cryptos}
    open_pos: dict[str, dict] = {}  # symbol → {direction, entry, qty, sl, tp}

    while True:
        print(f'\n[{datetime.now():%Y-%m-%d %H:%M:%S}] 掃描中...')
        end_str   = datetime.now().strftime('%Y-%m-%d')
        start_str = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        for sym in cryptos:
            try:
                df = _download_single(sym, start_str, end_str)
                if df is None or len(df) < config.EMA_PERIOD + 10:
                    continue

                upsert_prices(df, sym, asset_type_of(sym))
                df  = compute_all_indicators(df, include_vp=False)
                sig = generate_all_signals(df)['combined']

                if len(sig) == 0:
                    continue

                latest_sig = int(sig.iloc[-1])
                price      = float(df['Close'].iloc[-1])
                atr        = float(df['atr'].iloc[-1] or price * 0.02)

                # 管理現有倉位
                if sym in open_pos:
                    pos   = open_pos[sym]
                    hit_sl = (pos['dir'] ==  1 and price <= pos['sl']) or \
                             (pos['dir'] == -1 and price >= pos['sl'])
                    hit_tp = (pos['dir'] ==  1 and price >= pos['tp']) or \
                             (pos['dir'] == -1 and price <= pos['tp'])
                    if hit_sl or hit_tp or (latest_sig != 0 and latest_sig != pos['dir']):
                        executor.close_position(sym, pos['qty'], pos['dir'])
                        print(f'  平倉 {sym} @ {price:.4f}')
                        del open_pos[sym]

                # 開新倉
                if sym not in open_pos and latest_sig != 0:
                    kf  = estimate_kelly_from_history(trade_history[sym])
                    sl, tp = calculate_stops(price, latest_sig, atr)
                    allocated = sum(p['entry'] * p['qty'] for p in open_pos.values())
                    available = max(0.0, balance - allocated)
                    qty = position_size(balance, kf, price, sl)   # 基數用帳戶總餘額
                    if qty > 0 and qty * price <= available:       # 買得起才下單
                        res = executor.place_order(sym, latest_sig, qty, sl, tp)
                        if res.get('retCode') == 0:
                            open_pos[sym] = {'dir': latest_sig, 'qty': qty,
                                             'sl': sl, 'tp': tp, 'entry': price}
                            print(f'  {"做多" if latest_sig==1 else "做空"} {sym} '
                                  f'qty={qty:.4f} @ {price:.4f}  SL={sl:.4f}  TP={tp:.4f}')
                        else:
                            print(f'  [ORDER FAIL] {sym}: {res.get("retMsg")}')

            except Exception as exc:
                print(f'  [ERROR] {sym}: {exc}')

        balance = executor.get_balance()
        print(f'  帳戶餘額：{balance:.2f} USDT | 持倉：{len(open_pos)} 個')
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
    p_bt.add_argument('--with-vp',   action='store_true',           help='啟用 Volume Profile 策略（速度較慢，預設關閉）')
    p_bt.add_argument('--output',   type=str,  default=None,      help='自訂輸出路徑')
    p_bt.add_argument('--note',       type=str,  default='',        help='本次回測備註（儲存至 DB）')
    p_bt.add_argument('--ver',        type=str,  default=None,      help='版號（預設讀 config.SYSTEM_VERSION）')
    p_bt.add_argument('--start-date',    type=str,   default=None,   help='回測起始日（YYYY-MM-DD），指標仍用完整歷史暖身')
    p_bt.add_argument('--end-date',      type=str,   default=None,   help='回測結束日（YYYY-MM-DD）')
    p_bt.add_argument('--moat-tf-only',  action='store_true',        help='護城河只封鎖 Supertrend，VP/BB 豁免')
    p_bt.add_argument('--rs-pct',        type=float, default=None,   help='RS 豁免門檻（預設 0.03）')

    # history
    p_hist = sub.add_parser('history', help='查詢歷史回測記錄')
    p_hist.add_argument('--limit',  type=int, default=20,   help='顯示最近幾筆（default=20）')
    p_hist.add_argument('--run-id', type=int, default=None, help='查看指定回測的交易明細')

    # live
    p_live = sub.add_parser('live', help='即時交易（Bybit 加密貨幣）')
    p_live.add_argument('--seed',     type=int, default=42, help='隨機種子')
    p_live.add_argument('--interval', type=int, default=60, help='掃描間隔（分鐘，default=60）')

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
        cmd_live(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
