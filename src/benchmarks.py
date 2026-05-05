from datetime import datetime, timedelta

import pandas as pd

import config
from src.database import get_last_date, init_db, load_prices, upsert_prices
from src.fetcher import _download_single


BENCHMARK_ASSET_TYPE = 'Benchmark'


def benchmark_symbols() -> list[str]:
    return [config.TW_MARKET_SYMBOL, config.US_MARKET_SYMBOL]


def fetch_benchmarks(years: int = 6):
    init_db()
    end = datetime.now()
    start = end - timedelta(days=years * 365 + 60)
    start_str = start.strftime('%Y-%m-%d')
    end_str = end.strftime('%Y-%m-%d')

    print(f'\n下載大盤基準資料 ({start_str} -> {end_str})')
    ok, skip = 0, 0
    for sym in benchmark_symbols():
        df = _download_single(sym, start_str, end_str)
        if df is not None and len(df) >= 20:
            upsert_prices(df, sym, BENCHMARK_ASSET_TYPE)
            ok += 1
            print(f'  [OK] {sym}: {len(df)} 筆')
        else:
            skip += 1
            print(f'  [WARN] {sym}: 大盤資料下載失敗')
    print(f'大盤基準完成：成功 {ok} 檔，跳過 {skip} 檔')


def update_benchmarks():
    init_db()
    today = datetime.now()
    end_str = today.strftime('%Y-%m-%d')

    print('\n更新大盤基準資料')
    for sym in benchmark_symbols():
        last = get_last_date(sym)
        if last is None:
            start_str = (today - timedelta(days=6 * 365 + 60)).strftime('%Y-%m-%d')
        else:
            next_dt = datetime.strptime(last, '%Y-%m-%d') + timedelta(days=1)
            if next_dt.date() >= today.date():
                print(f'  [OK] {sym}: 已是最新 ({last})')
                continue
            start_str = next_dt.strftime('%Y-%m-%d')

        df = _download_single(sym, start_str, end_str)
        if df is not None and len(df) >= 1:
            upsert_prices(df, sym, BENCHMARK_ASSET_TYPE)
            print(f'  [+{len(df)}筆] {sym} ({start_str} -> {end_str})')
        else:
            print(f'  [WARN] {sym}: 無法更新，將沿用 SQLite 既有資料')


def load_or_update_benchmark(symbol: str, years: int = 6) -> pd.DataFrame | None:
    init_db()
    today = datetime.now()
    end_str = today.strftime('%Y-%m-%d')
    last = get_last_date(symbol)

    if last is None:
        start_str = (today - timedelta(days=years * 365 + 60)).strftime('%Y-%m-%d')
    else:
        next_dt = datetime.strptime(last, '%Y-%m-%d') + timedelta(days=1)
        start_str = next_dt.strftime('%Y-%m-%d')

    if last is None or datetime.strptime(start_str, '%Y-%m-%d').date() < today.date():
        df_new = _download_single(symbol, start_str, end_str)
        if df_new is not None and len(df_new) >= 1:
            upsert_prices(df_new, symbol, BENCHMARK_ASSET_TYPE)
            print(f'  [DB] {symbol}: 補入 {len(df_new)} 筆基準資料')
        elif last is None:
            print(f'  [WARN] {symbol}: 大盤資料下載失敗，SQLite 也沒有快取')
        else:
            print(f'  [WARN] {symbol}: 大盤資料更新失敗，沿用 SQLite 快取至 {last}')

    cached = load_prices(symbol)
    if cached is None or cached.empty:
        return None
    return cached.dropna(subset=['Close'])
