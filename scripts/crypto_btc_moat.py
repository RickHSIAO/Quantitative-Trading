"""在 v1.9 設定下測試 BTC moat 的三種模式：long_only / full / disabled。"""
import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import config
from config import get_selected_assets
from src.database import load_prices, get_all_symbols
from src.indicators import compute_all_indicators
from src.strategies import apply_cross_asset_filters, generate_all_signals
from src.backtester import run_silo_backtest


def _build(moat_enabled: bool, mode: str):
    saved_en   = config.ENABLE_CRYPTO_BTC_MOAT
    saved_mode = config.CRYPTO_BTC_MOAT_MODE
    config.ENABLE_CRYPTO_BTC_MOAT = moat_enabled
    config.CRYPTO_BTC_MOAT_MODE   = mode
    try:
        assets = get_selected_assets(42)
        avail  = set(get_all_symbols())
        cryptos = [s for s in assets['cryptos'] if s in avail]
        type_map = {s: 'Crypto' for s in cryptos}
        data, signals = {}, {}
        for sym in cryptos:
            df = load_prices(sym)
            if df is None or len(df) < config.EMA_PERIOD + 10:
                continue
            df = compute_all_indicators(df, include_vp=True)
            sigs = generate_all_signals(df, asset_type='Crypto', moat_tf_only=True)
            data[sym] = df; signals[sym] = sigs
        apply_cross_asset_filters(data, signals, type_map)
        profiles = {'Crypto': copy.deepcopy(config.STRATEGY_PROFILES['Crypto'])}
        trades, results = run_silo_backtest(
            data, signals, type_map, {'Crypto': ['Crypto']},
            config.SILO_CAPITAL, profiles)
        return results['Crypto']
    finally:
        config.ENABLE_CRYPTO_BTC_MOAT = saved_en
        config.CRYPTO_BTC_MOAT_MODE   = saved_mode


def fmt(label, sr):
    m  = sr['metrics']
    ec = sr['equity_curve']
    yrs = max((pd.Timestamp(ec[-1]['date']) - pd.Timestamp(ec[0]['date'])).days/365.25, 0.01)
    bs = m.get('by_strategy', {})
    sb = ' '.join(f'{k[0].upper()}={v["trades"]}/{int(v["win_rate"]*100)}%'
                  for k, v in bs.items())
    print(f'{label:<26} CAGR {m.get("annual_return_pct", 0):>+6.2f}% '
          f'WR {m.get("win_rate", 0)*100:>4.1f}% '
          f'T {m.get("total_trades", 0):>3} '
          f'/yr {m.get("total_trades", 0)/yrs:>4.1f} '
          f'PF {m.get("profit_factor", 0):>4.2f} '
          f'DD {m.get("max_drawdown_pct", 0):>5.1f}%   {sb}')


if __name__ == '__main__':
    print('=== v1.9 設定下，比較 BTC moat 模式 ===\n')
    fmt('long_only (v1.9 預設)', _build(True,  'long_only'))
    fmt('full (擋多+擋空)',      _build(True,  'full'))
    fmt('disabled (完全關閉)',   _build(False, 'long_only'))
