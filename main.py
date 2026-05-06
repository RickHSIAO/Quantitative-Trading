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
    from src.benchmarks import load_or_update_benchmark

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

    selected = [s for s in assets['all'] if s in available]
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

    bt     = Backtester(initial_capital=args.capital)
    trades = bt.run(data, signals, type_map)
    metrics = bt.get_metrics()

    # 紀錄護城河啟用狀態，避免之後忘記哪些濾網因資料缺失而失效
    metrics['moat_status'] = {
        'TW': 'enabled' if tw_benchmark is not None else 'disabled (^TWII 載入失敗)',
        'US': 'enabled' if us_benchmark is not None else 'disabled (^GSPC 載入失敗)',
        'moat_tf_only': bool(getattr(args, 'moat_tf_only', True)),
    }

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
    from src.database import upsert_prices, load_prices, get_last_date, init_db
    from src.fetcher import asset_type_of

    init_db()

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

    trade_history: dict[str, list] = {s: [] for s in cryptos}
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
                            'entry': float(p.get('avgPrice') or 0.0)
                        }
                        print(f'  [同步] {sys_sym} {"做多" if direction==1 else "做空"} {qty} 單位')
    except Exception as e:
        print(f'[WARN] 同步倉位失敗: {e}')

    while True:
        print(f'\n[{datetime.now():%Y-%m-%d %H:%M:%S}] 掃描中...')
        end_str   = datetime.now().strftime('%Y-%m-%d')

        for sym in cryptos:
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
                    hit_sl = (pos['dir'] ==  1 and price <= pos['sl']) or \
                             (pos['dir'] == -1 and price >= pos['sl'])
                    hit_tp = (pos['dir'] ==  1 and price >= pos['tp']) or \
                             (pos['dir'] == -1 and price <= pos['tp'])
                    if hit_sl or hit_tp or (latest_sig != 0 and latest_sig != pos['dir']):
                        executor.close_position(sym, pos['qty'], pos['dir'])
                        # 估算本筆損益並寫入 Kelly 樣本
                        pnl = (price - pos['entry']) * pos['qty'] * pos['dir']
                        trade_history[sym].append(ClosedTradeStub(pnl))
                        reason = 'SL' if hit_sl else ('TP' if hit_tp else 'FLIP')
                        print(f'  平倉 {sym} @ {price:.4f}  PnL={pnl:+.2f}  ({reason})')
                        del open_pos[sym]

                # 開新倉
                if sym not in open_pos and latest_sig != 0:
                    atype = 'Crypto'   # live 模式只跑加密
                    kf  = estimate_kelly_from_history(trade_history[sym], asset_type=atype)
                    sl, tp = calculate_stops(price, latest_sig, atr)
                    lev_map = getattr(config, 'LEVERAGE_BY_CLASS', {})
                    lev     = lev_map.get(atype, 1.0)
                    # 用保證金口徑計算可用資金（Bybit 永續以保證金抵押）
                    allocated_margin = sum(
                        (p['entry'] * p['qty']) / lev for p in open_pos.values()
                    )
                    available = max(0.0, balance - allocated_margin)
                    qty = position_size(balance, kf, price, sl, asset_type=atype)
                    # 用 executor 提供的精度修正再下單
                    qty_str = executor.format_qty(sym, qty)
                    sl_str  = executor.format_price(sym, sl)
                    tp_str  = executor.format_price(sym, tp)
                    margin_need = (qty * price) / lev
                    if qty > 0 and margin_need <= available:        # 保證金夠才下單
                        res = executor.place_order(sym, latest_sig, qty_str, sl_str, tp_str)
                        if res.get('retCode') == 0:
                            open_pos[sym] = {'dir': latest_sig, 'qty': qty,
                                             'sl': sl, 'tp': tp, 'entry': price}
                            print(f'  {"做多" if latest_sig==1 else "做空"} {sym} '
                                  f'qty={qty_str} @ {price:.4f}  SL={sl_str}  TP={tp_str}')
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
