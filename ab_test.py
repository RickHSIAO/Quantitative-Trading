"""A/B 測試 driver：載入一次指標 + 跑多個 config 比較 PnL。

用法：python ab_test.py
"""
import config as _cfg
from tqdm import tqdm
from config import get_selected_assets
from src.database import (load_prices, get_all_symbols,
                          save_backtest_run, init_db)
from src.indicators import compute_all_indicators
from src.strategies import generate_all_signals
from src.backtester import Backtester
from src.benchmarks import load_or_update_benchmark


def load_inputs():
    init_db()
    assets    = get_selected_assets(42)
    available = set(get_all_symbols())
    tm: dict[str, str] = {}
    for s in assets['us_stocks']:   tm[s] = 'US Stock'
    for s in assets['tw_stocks']:   tm[s] = 'TW Stock'
    for s in assets['cryptos']:     tm[s] = 'Crypto'
    for s in assets['commodities']: tm[s] = 'Commodity'

    tw_bm = load_or_update_benchmark(_cfg.TW_MARKET_SYMBOL)
    us_bm = load_or_update_benchmark(_cfg.US_MARKET_SYMBOL)

    selected = [s for s in assets['all'] if s in available]
    data, signals = {}, {}
    for sym in tqdm(selected, desc='指標', unit='檔'):
        df = load_prices(sym)
        if df is None or len(df) < _cfg.EMA_PERIOD + 10:
            continue
        atype = tm.get(sym, '')
        bm = tw_bm if atype == 'TW Stock' else us_bm if atype == 'US Stock' else None
        try:
            df   = compute_all_indicators(df, include_vp=True)
            sigs = generate_all_signals(df, asset_type=atype, benchmark_df=bm,
                                        moat_tf_only=True,
                                        rs_pct=_cfg.RS_OUTPERFORM_PCT)
        except Exception as exc:
            tqdm.write(f'  [SKIP] {sym}: {exc}')
            continue
        data[sym] = df
        signals[sym] = sigs
    return data, signals, tm


def run_one(data, signals, tm, overrides: dict, note: str) -> dict:
    saved = {k: getattr(_cfg, k) for k in overrides}
    for k, v in overrides.items():
        setattr(_cfg, k, v)
    try:
        bt     = Backtester(initial_capital=_cfg.INITIAL_CAPITAL)
        trades = bt.run(data, signals, tm)
        m      = bt.get_metrics()
        rid    = save_backtest_run(trades, m, note=note,
                                   version=_cfg.SYSTEM_VERSION)
        m['run_id'] = rid
        return m
    finally:
        for k, v in saved.items():
            setattr(_cfg, k, v)


RUNS = [
    ('A0_current_default',   {}),  # 用當前 config.py 預設（含已啟用的旗標）
    ('A1_min_hold_3',        {'MIN_HOLD_DAYS': 3}),
    ('A2_soft_stop_4pct',    {'SOFT_STOP_PCT': 0.04}),
    ('A3_max_hold_120',      {'MAX_HOLD_DAYS': 120}),
    ('A4_sym_wr_35pct',      {'SYM_MIN_WINRATE': 0.35}),
    ('A5_atr_kelly_15x',     {'ATR_KELLY_MULT': 1.5}),
    ('A6_equal_cash_split',  {'EQUAL_CASH_SPLIT': True}),
]


def main():
    print('\n=== 載入資料與指標（一次性）===')
    data, signals, tm = load_inputs()
    print(f'  有效資產：{len(data)} 檔\n')

    rows = []
    for note, ov in RUNS:
        print(f'\n--- {note}  overrides={ov} ---')
        m = run_one(data, signals, tm, ov, note)
        rows.append((note, m))
        print(f'  ret={m.get("total_return_pct"):>6.2f}%  '
              f'trades={m.get("total_trades"):>4}  '
              f'WR={m.get("win_rate"):.3f}  '
              f'PF={m.get("profit_factor"):.3f}  '
              f'Sharpe={m.get("sharpe_ratio"):.3f}  '
              f'MaxDD={m.get("max_drawdown_pct"):.2f}%  '
              f'(run_id={m["run_id"]})')

    print('\n' + '=' * 92)
    print(f'{"name":<22} {"return%":>8} {"trades":>7} {"WR":>6} '
          f'{"PF":>6} {"Sharpe":>7} {"MaxDD%":>8} {"vs A0":>8}')
    print('=' * 92)
    base_ret = rows[0][1].get('total_return_pct', 0)
    for note, m in rows:
        delta = m.get('total_return_pct', 0) - base_ret
        sign  = '+' if delta >= 0 else ''
        print(f'{note:<22} '
              f'{m.get("total_return_pct",0):>8.2f} '
              f'{m.get("total_trades",0):>7} '
              f'{m.get("win_rate",0):>6.3f} '
              f'{m.get("profit_factor",0):>6.3f} '
              f'{m.get("sharpe_ratio",0):>7.3f} '
              f'{m.get("max_drawdown_pct",0):>8.2f} '
              f'{sign}{delta:>7.2f}')


if __name__ == '__main__':
    main()
