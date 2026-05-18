"""Phase 5 — final sweet-spot lock-in around HOLD=21/30 × cap=3/4/5 × score."""
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
        data[sym] = df; signals[sym] = sigs
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
        print(f'{label:<50} '
              f'CAGR {m.get("annual_return_pct", 0):>+6.2f}% '
              f'WR {m.get("win_rate", 0)*100:>4.1f}% '
              f'T {m.get("total_trades", 0):>3} '
              f'/yr {m.get("total_trades", 0)/yrs:>4.1f} '
              f'PF {m.get("profit_factor", 0):>4.2f} '
              f'DD {m.get("max_drawdown_pct", 0):>5.1f}% '
              f'avgR {m.get("avg_r_multiple", 0):>+5.2f}')
        return m
    finally:
        for k, v in saved.items(): setattr(config, k, v)
        _patch()


if __name__ == '__main__':
    base = _build_inputs(use_vp=True)

    common = {'TSL_USE_CLOSE': True, 'TSL_TIGHT_AFTER_R': 2.0,
              'TSL_TIGHT_ATR_MULT': 1.5, 'CRYPTO_POS_PCT': 0.40,
              'MIN_ENTRY_SCORE': 3}

    print('\n=== Grid: cap × HOLD ===')
    for cap in (3, 4, 5):
        for hd in (0, 21, 30, 45):
            run_one(f'cap={cap} HOLD={hd}',
                    {**common, 'CRYPTO_MAX_POSITIONS': cap, 'MAX_HOLD_DAYS': hd}, base)

    print('\n=== Best zone + soft_stop ===')
    for ss in (0.0, 0.08, 0.12, 0.15):
        run_one(f'cap=4 HOLD=21 SOFT={ss}',
                {**common, 'CRYPTO_MAX_POSITIONS': 4, 'MAX_HOLD_DAYS': 21,
                 'SOFT_STOP_PCT': ss}, base)

    print('\n=== Best zone + circuit breaker variants ===')
    run_one('cap=4 HOLD=21 CB ON',
            {**common, 'CRYPTO_MAX_POSITIONS': 4, 'MAX_HOLD_DAYS': 21,
             'ENABLE_CIRCUIT_BREAKER': True}, base)
    run_one('cap=4 HOLD=21 CB OFF',
            {**common, 'CRYPTO_MAX_POSITIONS': 4, 'MAX_HOLD_DAYS': 21,
             'ENABLE_CIRCUIT_BREAKER': False}, base)

    print('\n=== Best zone + min_hold + score variations ===')
    for mh in (0, 3, 5):
        run_one(f'cap=4 HOLD=21 MIN_H={mh}',
                {**common, 'CRYPTO_MAX_POSITIONS': 4, 'MAX_HOLD_DAYS': 21,
                 'MIN_HOLD_DAYS': mh}, base)
    for sc in (3, 4, 5):
        run_one(f'cap=4 HOLD=21 sc>={sc}',
                {**common, 'CRYPTO_MAX_POSITIONS': 4, 'MAX_HOLD_DAYS': 21,
                 'MIN_ENTRY_SCORE': sc}, base)

    print('\n=== Pareto candidates ===')
    run_one('★ cap=4 HOLD=21',
            {**common, 'CRYPTO_MAX_POSITIONS': 4, 'MAX_HOLD_DAYS': 21}, base)
    run_one('★ cap=4 HOLD=30',
            {**common, 'CRYPTO_MAX_POSITIONS': 4, 'MAX_HOLD_DAYS': 30}, base)
    run_one('★ cap=5 HOLD=21',
            {**common, 'CRYPTO_MAX_POSITIONS': 5, 'MAX_HOLD_DAYS': 21}, base)
    run_one('★ cap=5 HOLD=30',
            {**common, 'CRYPTO_MAX_POSITIONS': 5, 'MAX_HOLD_DAYS': 30}, base)
