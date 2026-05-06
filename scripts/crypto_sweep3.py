"""Phase 3: combine C4 (TSL close + tight@2R) with cap/score/moat winners."""
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
    risk_mod._STRAT_PARAMS = {
        'trend':    (config.STRAT_TREND_ATR_MULT, config.STRAT_TREND_RR),
        'combined': (config.STRAT_TREND_ATR_MULT, config.STRAT_TREND_RR),
        'vp':       (config.STRAT_VP_ATR_MULT,    config.STRAT_VP_RR),
        'bb':       (config.STRAT_BB_ATR_MULT,    config.STRAT_BB_RR),
    }


def run_one(label, overrides, base, recompute=False):
    saved = {k: getattr(config, k) for k in overrides if hasattr(config, k)}
    for k, v in overrides.items():
        setattr(config, k, v)
    _patch_strat_params()
    try:
        if recompute:
            base = _build_inputs(use_vp=True)
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
    base = _build_inputs(use_vp=True)

    print('\n=== TSL close + tight@2R + cap variations ===')
    tsl = {'TSL_USE_CLOSE': True, 'TSL_TIGHT_AFTER_R': 2.0, 'TSL_TIGHT_ATR_MULT': 1.5}
    for cap in (2, 3, 4, 5):
        for sc in (3, 4):
            run_one(f'cap={cap} sc>={sc} TSLclose+tight@2R',
                    {**tsl, 'CRYPTO_MAX_POSITIONS': cap, 'MIN_ENTRY_SCORE': sc}, base)

    print('\n=== With BBloose0 EMA1 (more BB entries) ===')
    base_bb = _build_inputs(use_vp=True)  # baseline
    for cap in (2, 3, 4):
        run_one(f'cap={cap} sc=3 BBloose0 EMA1 +TSL',
                {**tsl, 'CRYPTO_MAX_POSITIONS': cap, 'MIN_ENTRY_SCORE': 3,
                 'EMA_MIN_SCORE': 1, 'BB_LOOSE_MIN_EMA_SCORE': 0}, None,
                recompute=True)

    print('\n=== Tighter@1.5R variants ===')
    for tar in (1.0, 1.5, 2.0, 2.5):
        run_one(f'TSL tight@{tar}R',
                {'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 3,
                 'TSL_USE_CLOSE': True,
                 'TSL_TIGHT_AFTER_R': tar, 'TSL_TIGHT_ATR_MULT': 1.5}, base)

    print('\n=== Combine: tighter ATR mult on entry too ===')
    for am, tar in [(2.5, 2.0), (2.5, 1.5), (3.0, 1.5)]:
        run_one(f'STT.ATR={am} tight@{tar}R',
                {'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 3,
                 'STRAT_TREND_ATR_MULT': am, 'TSL_USE_CLOSE': True,
                 'TSL_TIGHT_AFTER_R': tar, 'TSL_TIGHT_ATR_MULT': 1.5}, base)

    print('\n=== Drop BTC moat + TSL ===')
    run_one('NoBTCmoat sc=3 cap=3 +TSL2R',
            {**tsl, 'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 3,
             'ENABLE_CRYPTO_BTC_MOAT': False}, None, recompute=True)
    run_one('NoBTCmoat sc=4 cap=3 +TSL2R',
            {**tsl, 'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 4,
             'ENABLE_CRYPTO_BTC_MOAT': False}, None, recompute=True)
    run_one('NoBTCmoat sc=3 cap=4 +TSL2R',
            {**tsl, 'CRYPTO_MAX_POSITIONS': 4, 'MIN_ENTRY_SCORE': 3,
             'ENABLE_CRYPTO_BTC_MOAT': False}, None, recompute=True)

    print('\n=== BTC moat full mode (block crypto shorts in BTC bull) ===')
    run_one('BTC moat full sc=3 cap=3 +TSL2R',
            {**tsl, 'CRYPTO_MAX_POSITIONS': 3, 'MIN_ENTRY_SCORE': 3,
             'CRYPTO_BTC_MOAT_MODE': 'full'}, None, recompute=True)
