"""測試 4H / 1H K 線框架對 Crypto 策略的影響。

注意：
- 直接從 Bybit 抓資料到記憶體，不寫進 DB（避免污染日線資料）
- 指標週期維持原值（EMA200/ATR14），所以 4H 的 EMA200 約等於 33 天均線；
  這是「同參數移植到不同時間框架」的對照測試，未專門針對 4H/1H 重調參。
- BTC moat 的 EMA200 也跟著用該時間框架算
"""
import sys, os, copy, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import pandas as pd
import config
from config import get_selected_assets
from src.indicators import compute_all_indicators
from src.strategies import apply_cross_asset_filters, generate_all_signals
from src.backtester import run_silo_backtest

try:
    from pybit.unified_trading import HTTP as BybitHTTP
except ImportError:
    raise SystemExit('pybit 未安裝')


def fetch_bybit(symbol: str, interval: str, years: int = 5) -> pd.DataFrame | None:
    """interval: '60' = 1H, '240' = 4H, 'D' = 1D"""
    bybit_sym = symbol[6:-2]
    end_dt   = datetime.now()
    start_dt = end_dt - timedelta(days=years * 365)
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts   = int(end_dt.timestamp()   * 1000)
    sess = BybitHTTP()
    rows, cursor = [], end_ts
    while True:
        try:
            res = sess.get_kline(category='linear', symbol=bybit_sym,
                                 interval=interval, start=start_ts, end=cursor, limit=1000)
        except Exception as e:
            print(f'  [ERR] {symbol} {interval}: {e}')
            return None
        chunk = res.get('result', {}).get('list', [])
        if not chunk:
            break
        rows.extend(chunk)
        oldest_ts = int(chunk[-1][0])
        if oldest_ts <= start_ts:
            break
        cursor = oldest_ts - 1
        time.sleep(0.05)
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=['ts','Open','High','Low','Close','Volume','_'])
    df['ts'] = pd.to_datetime(df['ts'].astype('int64'), unit='ms')
    df = df.set_index('ts').sort_index()
    df = df[['Open','High','Low','Close','Volume']].astype(float)
    df.index.name = None
    return df


def run_silo_for_tf(interval: str, label: str, years: int = 5):
    print(f'\n=== {label} ({interval}) — 抓資料中…')
    assets   = get_selected_assets(42)
    cryptos  = assets['cryptos']
    type_map = {s: 'Crypto' for s in cryptos}

    data, signals = {}, {}
    for sym in cryptos:
        df = fetch_bybit(sym, interval, years=years)
        if df is None or len(df) < config.EMA_PERIOD + 50:
            print(f'  {sym}: skip (len={0 if df is None else len(df)})')
            continue
        df = compute_all_indicators(df, include_vp=True)
        sigs = generate_all_signals(df, asset_type='Crypto', moat_tf_only=True)
        data[sym] = df; signals[sym] = sigs
        print(f'  {sym}: {len(df)} bars  ({df.index[0]} → {df.index[-1]})')

    if not data:
        print('  ⚠️  無資料')
        return

    apply_cross_asset_filters(data, signals, type_map)
    profiles = {'Crypto': copy.deepcopy(config.STRATEGY_PROFILES['Crypto'])}
    print(f'  跑回測 ({sum(len(d) for d in data.values()):,} bars total)…')
    trades, results = run_silo_backtest(
        data, signals, type_map, {'Crypto': ['Crypto']},
        config.SILO_CAPITAL, profiles)

    sr = results['Crypto']
    m  = sr['metrics']
    ec = sr['equity_curve']
    yrs = max((pd.Timestamp(ec[-1]['date']) - pd.Timestamp(ec[0]['date'])).days/365.25, 0.01)
    bs = m.get('by_strategy', {})
    sb = ' '.join(f'{k[0].upper()}={v["trades"]}/{int(v["win_rate"]*100)}%'
                  for k, v in bs.items())
    print(f'\n>>> {label:<8}  CAGR {m.get("annual_return_pct",0):>+6.2f}% '
          f'WR {m.get("win_rate",0)*100:>4.1f}% '
          f'T {m.get("total_trades",0):>4} '
          f'/yr {m.get("total_trades", 0)/yrs:>5.1f} '
          f'PF {m.get("profit_factor", 0):>4.2f} '
          f'DD {m.get("max_drawdown_pct", 0):>5.1f}% '
          f'avgR {m.get("avg_r_multiple", 0):>+5.2f} '
          f'avgHold {m.get("avg_holding_days", 0):>4.1f}d  {sb}')


if __name__ == '__main__':
    # 預設：1D（baseline）→ 4H → 1H
    run_silo_for_tf('D',   '1D baseline')
    run_silo_for_tf('240', '4H')
    run_silo_for_tf('60',  '1H')
