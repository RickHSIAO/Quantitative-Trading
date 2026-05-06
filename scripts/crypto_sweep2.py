"""Phase 2 sweep: lock in VP, vary cap / score / EMA gate / stops with proper patching."""
from __future__ import annotations
import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import config
from config import get_selected_assets
from src.database import load_prices, get_all_symbols
from src.indicators import compute_all_indicators
from src.strategies import apply_cross_asset_filters, generate_all_signals
from src.backtester import run_silo_backtest
from src import risk as risk_mod


def _build_inputs(use_vp: bool):
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
        sigs = generate_all_signals(df, asset_type='Crypto', moat_tf_only=True)
        data[sym] = df
        signals[sym] = sigs
    apply_cross_asset_filters(data, signals, type_map)
    return data, signals, type_map


def _patch_strat_params():
    """Rebuild risk_mod._STRAT_PARAMS from current config (call after override)."""
    risk_mod._STRAT_PARAMS = {
        'trend':    (config.STRAT_TREND_ATR_MULT, config.STRAT_TREND_RR),
        'combined': (config.STRAT_TREND_ATR_MULT, config.STRAT_TREND_RR),
        'vp':       (config.STRAT_VP_ATR_MULT,    config.STRAT_VP_RR),
        'bb':       (config.STRAT_BB_ATR_MULT,    config.STRAT_BB_RR),
    }


def run_one(label: str, overrides: dict, base, recompute_signals: bool = False):
    saved = {k: getattr(config, k) for k in overrides if hasattr(config, k)}
    for k, v in overrides.items():
        setattr(config, k, v)
    _patch_strat_params()
    try:
        if recompute_signals:
            data, signals, type_map = _build_inputs(use_vp=True)
        else:
            data, signals, type_map = base

        profile = copy.deepcopy(config.STRATEGY_PROFILES['Crypto'])
        if 'CRYPTO_MAX_POSITIONS' in overrides:
            profile['max_total_positions'] = overrides['CRYPTO_MAX_POSITIONS']
        profiles = {'Crypto': profile}

        trades, results = run_silo_backtest(
            data, signals, type_map, {'Crypto': ['Crypto']},
            config.SILO_CAPITAL, profiles)
        m = results['Crypto']['metrics']

        ec = results['Crypto']['equity_curve']
        d0 = pd.Timestamp(ec[0]['date']); d1 = pd.Timestamp(ec[-1]['date'])
        yrs = max((d1 - d0).days / 365.25, 0.01)
        tr_per_yr = m.get('total_trades', 0) / yrs

        bs = m.get('by_strategy', {})
        sb = ' '.join(f'{k[0].upper()}={v["trades"]}/{int(v["win_rate"]*100)}%'
                      for k, v in bs.items())
        print(f'{label:<46} '
              f'CAGR {m.get("annual_return_pct", 0):>+6.2f}% '
              f'WR {m.get("win_rate", 0)*100:>4.1f}% '
              f'T {m.get("total_trades", 0):>3} '
              f'/yr {tr_per_yr:>4.1f} '
              f'PF {m.get("profit_factor", 0):>4.2f} '
              f'DD {m.get("max_drawdown_pct", 0):>5.1f}% '
              f'avgR {m.get("avg_r_multiple", 0):>+5.2f}  {sb}')
        return m
    finally:
        for k, v in saved.items():
            setattr(config, k, v)
        _patch_strat_params()


if __name__ == '__main__':
    print('Building base inputs (VP=True)...')
    base = _build_inputs(use_vp=True)

    print('\n=== Phase A: VP+ low cap, vary score/EMA ===')
    run_one('A1: VP cap=2 default', {'CRYPTO_MAX_POSITIONS': 2}, base)
    run_one('A2: VP cap=2 score=3', {'CRYPTO_MAX_POSITIONS': 2, 'MIN_ENTRY_SCORE': 3}, base)
    run_one('A3: VP cap=3 default', {'CRYPTO_MAX_POSITIONS': 3}, base)
    run_one('A4: VP cap=3 score=3', {'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 3}, base)
    run_one('A5: VP cap=4 score=3', {'CRYPTO_MAX_POSITIONS': 4, 'MIN_ENTRY_SCORE': 3}, base)

    print('\n=== Phase B: VP+ tighter TP/RR for trend (avgR is 0.17, TSL strips winners) ===')
    base_b = {'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 3}
    for atr_m, rr in [(2.5, 3.0), (2.0, 3.0), (3.0, 4.0), (2.5, 2.5), (2.0, 2.5)]:
        run_one(f'B: ATR={atr_m} RR={rr}',
                {**base_b, 'STRAT_TREND_ATR_MULT': atr_m, 'STRAT_TREND_RR': rr}, base)

    print('\n=== Phase C: VP+ TSL adjustments ===')
    base_c = {'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 3}
    run_one('C1: looser TSL ATR=4', {**base_c, 'ATR_STOP_MULTIPLIER': 4.0}, base)
    run_one('C2: looser TSL ATR=5', {**base_c, 'ATR_STOP_MULTIPLIER': 5.0}, base)
    run_one('C3: TSL Close-based',  {**base_c, 'TSL_USE_CLOSE': True}, base)
    run_one('C4: TSL Close + tight after 2R',
            {**base_c, 'TSL_USE_CLOSE': True,
             'TSL_TIGHT_AFTER_R': 2.0, 'TSL_TIGHT_ATR_MULT': 1.5}, base)
    run_one('C5: BE@1R',            {**base_c, 'ENABLE_BREAKEVEN_STOP': True,
                                                'BREAKEVEN_TRIGGER_R': 1.0}, base)
    run_one('C6: BE@0.5R',          {**base_c, 'ENABLE_BREAKEVEN_STOP': True,
                                                'BREAKEVEN_TRIGGER_R': 0.5}, base)
    run_one('C7: Close-based-SL trend', {**base_c, 'CLOSE_BASED_SL_TREND': True}, base)

    print('\n=== Phase D: BB stop+RR variations (BB has 654 raw triggers but 0 trades) ===')
    base_d = {'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 3,
              'EMA_MIN_SCORE': 1, 'BB_LOOSE_MIN_EMA_SCORE': 0}
    run_one('D1: EMA1 BBloose0', base_d, None, recompute_signals=True)
    run_one('D2: + score=2',     {**base_d, 'MIN_ENTRY_SCORE': 2},
            None, recompute_signals=True)

    print('\n=== Phase E: combo finalists ===')
    finalists = {
        'E1: VP cap=3 sc=3 BE1R':       {'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 3,
                                          'ENABLE_BREAKEVEN_STOP': True,
                                          'BREAKEVEN_TRIGGER_R': 1.0},
        'E2: VP cap=3 sc=3 ClSL':       {'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 3,
                                          'CLOSE_BASED_SL_TREND': True},
        'E3: VP cap=3 sc=3 ATR4':       {'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 3,
                                          'ATR_STOP_MULTIPLIER': 4.0},
        'E4: VP cap=3 sc=3 BE1R ClSL':  {'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 3,
                                          'ENABLE_BREAKEVEN_STOP': True,
                                          'BREAKEVEN_TRIGGER_R': 1.0,
                                          'CLOSE_BASED_SL_TREND': True},
        'E5: VP cap=4 sc=3 BE1R ClSL':  {'CRYPTO_MAX_POSITIONS': 4, 'MIN_ENTRY_SCORE': 3,
                                          'ENABLE_BREAKEVEN_STOP': True,
                                          'BREAKEVEN_TRIGGER_R': 1.0,
                                          'CLOSE_BASED_SL_TREND': True},
        'E6: VP cap=3 sc=3 noBTCmoat':  {'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 3,
                                          'ENABLE_CRYPTO_BTC_MOAT': False},
    }
    for label, ov in finalists.items():
        rec = ov.get('ENABLE_CRYPTO_BTC_MOAT') is False or 'BB_LOOSE_MIN_EMA_SCORE' in ov \
              or ov.get('EMA_MIN_SCORE') is not None
        run_one(label, ov, base, recompute_signals=rec)
