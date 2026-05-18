"""Crypto-only parameter sweep — keep changes localized to runtime overrides."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import copy
import pandas as pd
import config
from config import get_selected_assets
from src.database import load_prices, get_all_symbols
from src.indicators import compute_all_indicators
from src.strategies import apply_cross_asset_filters, generate_all_signals
from src.backtester import run_silo_backtest


def _build_inputs(use_vp: bool, moat_tf_only: bool):
    """Load prices once per use_vp setting (VP changes the indicator frame)."""
    assets = get_selected_assets(42)
    available = set(get_all_symbols())
    cryptos = [s for s in assets['cryptos'] if s in available]

    type_map = {s: 'Crypto' for s in cryptos}
    data, signals = {}, {}
    for sym in cryptos:
        df = load_prices(sym)
        if df is None or len(df) < config.EMA_PERIOD + 10:
            continue
        df = compute_all_indicators(df, include_vp=use_vp)
        sigs = generate_all_signals(df, asset_type='Crypto', moat_tf_only=moat_tf_only)
        data[sym] = df
        signals[sym] = sigs
    apply_cross_asset_filters(data, signals, type_map)
    return data, signals, type_map


def run_one(label: str, overrides: dict, base_data=None, base_signals=None,
            base_type_map=None, use_vp=False, moat_tf_only=True,
            recompute_signals: bool = False):
    """
    overrides accept any config.X attribute (top-level).  We monkey-patch them
    onto the imported `config` module, run, then restore.
    """
    # Snapshot
    saved = {k: getattr(config, k) for k in overrides if hasattr(config, k)}
    for k, v in overrides.items():
        setattr(config, k, v)

    try:
        if recompute_signals or base_data is None:
            data, signals, type_map = _build_inputs(use_vp, moat_tf_only)
        else:
            data, signals, type_map = base_data, base_signals, base_type_map

        profile = copy.deepcopy(config.STRATEGY_PROFILES['Crypto'])
        # Allow per-run override of position cap
        if 'CRYPTO_MAX_POSITIONS' in overrides:
            profile['max_total_positions'] = overrides['CRYPTO_MAX_POSITIONS']
        profiles = {'Crypto': profile}
        silo_classes = {'Crypto': ['Crypto']}
        trades, results = run_silo_backtest(
            data, signals, type_map, silo_classes, config.SILO_CAPITAL, profiles)
        m = results['Crypto']['metrics']

        ec = results['Crypto']['equity_curve']
        if ec:
            d0 = pd.Timestamp(ec[0]['date']); d1 = pd.Timestamp(ec[-1]['date'])
            yrs = max((d1 - d0).days / 365.25, 0.01)
        else:
            yrs = 5.0
        tr_per_yr = m.get('total_trades', 0) / yrs

        eb = m.get('entry_block_stats', {})
        print(f'{label:<48} '
              f'CAGR {m.get("annual_return_pct", 0):>+6.2f}%  '
              f'WR {m.get("win_rate", 0)*100:>5.1f}%  '
              f'Trades {m.get("total_trades", 0):>3}  '
              f'/yr {tr_per_yr:>5.1f}  '
              f'PF {m.get("profit_factor", 0):>4.2f}  '
              f'DD {m.get("max_drawdown_pct", 0):>6.2f}%  '
              f'avgR {m.get("avg_r_multiple", 0):>+5.2f}  '
              f'cap-hit {eb.get("max_total_positions_hits", 0)}')
        return m
    finally:
        for k, v in saved.items():
            setattr(config, k, v)


if __name__ == '__main__':
    print('Building base inputs (VP=False)...')
    base_no_vp = _build_inputs(use_vp=False, moat_tf_only=True)

    print('\n=== Group A: Loosen position cap (no other change) ===')
    for cap in (2, 3, 4, 5, 6):
        run_one(f'A: cap={cap}', {'CRYPTO_MAX_POSITIONS': cap},
                *base_no_vp, recompute_signals=False)

    print('\n=== Group B: Lower MIN_ENTRY_SCORE (cap=4) ===')
    for sc in (4, 3, 2):
        run_one(f'B: cap=4 score>={sc}',
                {'CRYPTO_MAX_POSITIONS': 4, 'MIN_ENTRY_SCORE': sc},
                *base_no_vp, recompute_signals=False)

    print('\n=== Group C: Loosen EMA gate (lower EMA_MIN_SCORE) cap=4 ===')
    for ems in (2, 1):
        run_one(f'C: cap=4 EMA_MIN={ems} score>=3',
                {'CRYPTO_MAX_POSITIONS': 4, 'EMA_MIN_SCORE': ems,
                 'MIN_ENTRY_SCORE': 3},
                None, None, None, recompute_signals=True)

    print('\n=== Group D: Disable BTC moat (cap=4 score>=3) ===')
    run_one('D: cap=4 score>=3 NoBTCmoat',
            {'CRYPTO_MAX_POSITIONS': 4, 'MIN_ENTRY_SCORE': 3,
             'ENABLE_CRYPTO_BTC_MOAT': False},
            None, None, None, recompute_signals=True)

    print('\n=== Group E: Add VP (recompute with VP) cap=4 score>=3 ===')
    base_vp = _build_inputs(use_vp=True, moat_tf_only=True)
    run_one('E: VP+ cap=4 score>=3',
            {'CRYPTO_MAX_POSITIONS': 4, 'MIN_ENTRY_SCORE': 3},
            *base_vp, recompute_signals=False)

    print('\n=== Group F: Tighter TP for higher win-rate-of-TP (cap=4 score>=3) ===')
    # TSL is firing a lot at avg R = 0.17 → shorten ATR mult & RR for trend
    for atr_m, rr in [(2.5, 2.5), (2.0, 2.0), (2.0, 2.5)]:
        run_one(f'F: trend ATR={atr_m} RR={rr}',
                {'CRYPTO_MAX_POSITIONS': 4, 'MIN_ENTRY_SCORE': 3,
                 'STRAT_TREND_ATR_MULT': atr_m, 'STRAT_TREND_RR': rr},
                *base_no_vp, recompute_signals=False)

    print('\n=== Group G: Combo — best from C/D/E + tighter TSL for trailing wins ===')
    # Use breakeven + close-based SL to flip TSL early-kill into BE breaks rather than -SL
    run_one('G1: Combo VP+ cap=4 score=3 BE@1R',
            {'CRYPTO_MAX_POSITIONS': 4, 'MIN_ENTRY_SCORE': 3,
             'ENABLE_BREAKEVEN_STOP': True, 'BREAKEVEN_TRIGGER_R': 1.0},
            *base_vp, recompute_signals=False)
    run_one('G2: Combo VP+ cap=5 score=3 BE@1R EMA1',
            {'CRYPTO_MAX_POSITIONS': 5, 'MIN_ENTRY_SCORE': 3,
             'EMA_MIN_SCORE': 1,
             'ENABLE_BREAKEVEN_STOP': True, 'BREAKEVEN_TRIGGER_R': 1.0},
            None, None, None, recompute_signals=True)
    run_one('G3: Combo VP+ cap=6 score=3 EMA1 NoSlope',
            {'CRYPTO_MAX_POSITIONS': 6, 'MIN_ENTRY_SCORE': 3,
             'EMA_MIN_SCORE': 1, 'TREND_EMA50_SLOPE_CONFIRM': False},
            None, None, None, recompute_signals=True)
    run_one('G4: G3 + BE@1R',
            {'CRYPTO_MAX_POSITIONS': 6, 'MIN_ENTRY_SCORE': 3,
             'EMA_MIN_SCORE': 1, 'TREND_EMA50_SLOPE_CONFIRM': False,
             'ENABLE_BREAKEVEN_STOP': True, 'BREAKEVEN_TRIGGER_R': 1.0},
            None, None, None, recompute_signals=True)
