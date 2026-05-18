"""Crypto-only diagnostic: dump entry_block_stats, signal counts, BTC moat impact."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import config
from config import get_selected_assets
from src.database import load_prices, get_all_symbols
from src.indicators import compute_all_indicators
from src.strategies import (apply_cross_asset_filters, generate_all_signals,
                             trend_following_signals, volume_profile_signals,
                             bollinger_reversion_signals)
from src.backtester import run_silo_backtest


def main():
    assets = get_selected_assets(42)
    available = set(get_all_symbols())
    cryptos = [s for s in assets['cryptos'] if s in available]
    print(f'Cryptos in DB: {len(cryptos)}')

    type_map = {s: 'Crypto' for s in cryptos}
    data, signals = {}, {}
    for sym in cryptos:
        df = load_prices(sym)
        if df is None or len(df) < config.EMA_PERIOD + 10:
            continue
        df = compute_all_indicators(df, include_vp=False)
        sigs = generate_all_signals(df, asset_type='Crypto', moat_tf_only=True)
        data[sym] = df
        signals[sym] = sigs

    # Raw signal counts (before cross-asset BTC moat)
    raw_long = raw_short = 0
    for sym, s in signals.items():
        c = s['combined']
        raw_long  += int((c == 1).sum())
        raw_short += int((c == -1).sum())
    print(f'Raw signals (pre-BTC moat): long={raw_long}  short={raw_short}')

    # Apply BTC moat
    apply_cross_asset_filters(data, signals, type_map)
    post_long = post_short = 0
    for sym, s in signals.items():
        c = s['combined']
        post_long  += int((c == 1).sum())
        post_short += int((c == -1).sum())
    print(f'After BTC moat:  long={post_long}  short={post_short}')

    # Per-strategy raw counts (no env filter, just trigger)
    per_strat = {'trend': 0, 'vp': 0, 'bb': 0}
    for sym, df in data.items():
        per_strat['trend'] += int((trend_following_signals(df, 'Crypto') != 0).sum())
        per_strat['vp']    += int((volume_profile_signals(df) != 0).sum())
        per_strat['bb']    += int((bollinger_reversion_signals(df) != 0).sum())
    print(f'Per-strategy trigger counts (any direction):')
    for k, v in per_strat.items():
        print(f'  {k}: {v}')

    # Run silo backtest, dump entry_block_stats
    profiles = {'Crypto': config.STRATEGY_PROFILES['Crypto']}
    silo_classes = {'Crypto': ['Crypto']}
    trades, results = run_silo_backtest(data, signals, type_map, silo_classes,
                                          config.SILO_CAPITAL, profiles)
    m = results['Crypto']['metrics']
    print('\n=== Crypto Silo Metrics ===')
    for k in ('total_trades','win_rate','win_rate_long','win_rate_short',
              'annual_return_pct','total_return_pct','profit_factor','sharpe_ratio',
              'max_drawdown_pct','avg_holding_days','avg_r_multiple','expectancy'):
        print(f'  {k}: {m.get(k)}')
    print('exit_distribution:', m.get('exit_distribution'))
    print('by_strategy:', m.get('by_strategy'))
    print('entry_block_stats:', m.get('entry_block_stats'))


if __name__ == '__main__':
    main()
