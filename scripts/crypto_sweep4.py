"""Phase 4: explore MAX_POSITION_PCT, MAX_HOLD_DAYS, and final combo lock."""
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


def _patch():
    risk_mod._STRAT_PARAMS = {
        'trend':    (config.STRAT_TREND_ATR_MULT, config.STRAT_TREND_RR),
        'combined': (config.STRAT_TREND_ATR_MULT, config.STRAT_TREND_RR),
        'vp':       (config.STRAT_VP_ATR_MULT,    config.STRAT_VP_RR),
        'bb':       (config.STRAT_BB_ATR_MULT,    config.STRAT_BB_RR),
    }


def run_one(label, ov, base, recompute=False):
    saved = {k: getattr(config, k) for k in ov if hasattr(config, k)}
    for k, v in ov.items(): setattr(config, k, v)
    _patch()
    try:
        if recompute:
            base = _build_inputs(use_vp=True)
        data, signals, type_map = base
        profile = copy.deepcopy(config.STRATEGY_PROFILES['Crypto'])
        if 'CRYPTO_MAX_POSITIONS' in ov:
            profile['max_total_positions'] = ov['CRYPTO_MAX_POSITIONS']
        if 'CRYPTO_POS_PCT' in ov:
            profile['max_position_pct'] = ov['CRYPTO_POS_PCT']
        profiles = {'Crypto': profile}
        trades, results = run_silo_backtest(
            data, signals, type_map, {'Crypto': ['Crypto']},
            config.SILO_CAPITAL, profiles)
        m = results['Crypto']['metrics']
        ec = results['Crypto']['equity_curve']
        d0, d1 = pd.Timestamp(ec[0]['date']), pd.Timestamp(ec[-1]['date'])
        yrs = max((d1 - d0).days / 365.25, 0.01)
        bs = m.get('by_strategy', {})
        sb = ' '.join(f'{k[0].upper()}={v["trades"]}/{int(v["win_rate"]*100)}%'
                      for k, v in bs.items())
        eb = m.get('entry_block_stats', {})
        print(f'{label:<48} '
              f'CAGR {m.get("annual_return_pct", 0):>+6.2f}% '
              f'WR {m.get("win_rate", 0)*100:>4.1f}% '
              f'T {m.get("total_trades", 0):>3} '
              f'/yr {m.get("total_trades", 0)/yrs:>4.1f} '
              f'PF {m.get("profit_factor", 0):>4.2f} '
              f'DD {m.get("max_drawdown_pct", 0):>5.1f}% '
              f'avgR {m.get("avg_r_multiple", 0):>+5.2f} '
              f'zQ={eb.get("zero_qty_rejections",0)}')
        return m
    finally:
        for k, v in saved.items(): setattr(config, k, v)
        _patch()


if __name__ == '__main__':
    base = _build_inputs(use_vp=True)

    # Best so far: cap=3 sc=3 TSL@2R close
    common = {'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 3,
              'TSL_USE_CLOSE': True, 'TSL_TIGHT_AFTER_R': 2.0,
              'TSL_TIGHT_ATR_MULT': 1.5}

    print('\n=== Bump MAX_POSITION_PCT (per-silo) — should let qty hit Kelly target ===')
    for pc in (0.20, 0.30, 0.40, 0.60, 0.80, 1.0):
        run_one(f'POS_PCT={pc}', {**common, 'CRYPTO_POS_PCT': pc}, base)

    print('\n=== Bump POS_PCT and MAX_RISK_PCT ===')
    for rp in (0.07, 0.10, 0.15):
        run_one(f'rp={rp} POS_PCT=0.40',
                {**common, 'CRYPTO_POS_PCT': 0.40, 'MAX_RISK_PCT': rp,
                 'DEFAULT_RISK_PCT_BY_CLASS': {'Crypto': rp, 'US Stock': 0.030,
                                                 'TW Stock': 0.020, 'Commodity': 0.030}},
                base)

    print('\n=== MAX_HOLD_DAYS recycling ===')
    for hd in (0, 14, 21, 30, 45):
        run_one(f'HOLD={hd} POS_PCT=0.40',
                {**common, 'CRYPTO_POS_PCT': 0.40, 'MAX_HOLD_DAYS': hd}, base)

    print('\n=== Combine: best composite ===')
    run_one('FINAL: cap3 sc3 TSL POS40 HOLD30',
            {**common, 'CRYPTO_POS_PCT': 0.40, 'MAX_HOLD_DAYS': 30}, base)
    run_one('FINAL: cap4 sc3 TSL POS40 HOLD30',
            {**common, 'CRYPTO_MAX_POSITIONS': 4,
             'CRYPTO_POS_PCT': 0.40, 'MAX_HOLD_DAYS': 30}, base)
    run_one('FINAL: cap5 sc4 TSL POS40',
            {**common, 'CRYPTO_MAX_POSITIONS': 5, 'MIN_ENTRY_SCORE': 4,
             'CRYPTO_POS_PCT': 0.40}, base)

    print('\n=== Higher Kelly fraction (1/3 Kelly) ===')
    run_one('1/3 Kelly cap=3 sc=3 TSL POS40',
            {**common, 'KELLY_FRACTION': 0.333, 'CRYPTO_POS_PCT': 0.40,
             'MAX_RISK_PCT': 0.10}, base)
