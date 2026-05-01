import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from tqdm import tqdm
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from src.database import init_db, upsert_prices


def asset_type_of(symbol: str) -> str:
    if symbol.endswith('.TW') or symbol.endswith('.TWO'):
        return 'TW Stock'
    if symbol.endswith('-USD'):
        return 'Crypto'
    if symbol in config.COMMODITIES:
        return 'Commodity'
    return 'US Stock'


def _download_single(symbol: str, start: str, end: str) -> pd.DataFrame | None:
    try:
        df = yf.download(
            symbol,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if df is None or df.empty:
            return None

        # yfinance >= 0.2 may return MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        cols = {c.lower(): c for c in df.columns}
        needed = ['open', 'high', 'low', 'close', 'volume']
        if not all(c in cols for c in needed):
            return None

        df = df[[cols[c] for c in needed]].copy()
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        df = df.dropna(subset=['Close'])
        df.index = pd.DatetimeIndex(df.index).tz_localize(None)
        return df
    except Exception as exc:
        print(f"  [ERROR] {symbol}: {exc}")
        return None


def fetch_all_assets(assets: dict, years: int = config.DATA_YEARS):
    init_db()
    end   = datetime.now()
    start = end - timedelta(days=years * 365 + 60)
    start_str = start.strftime('%Y-%m-%d')
    end_str   = end.strftime('%Y-%m-%d')

    all_syms = assets['all']
    print(f"\n下載 {len(all_syms)} 個資產 ({start_str} → {end_str})\n")

    ok, skip = 0, 0
    for sym in tqdm(all_syms, desc='下載中', unit='檔'):
        df = _download_single(sym, start_str, end_str)
        if df is not None and len(df) >= 20:
            upsert_prices(df, sym, asset_type_of(sym))
            ok += 1
        else:
            tqdm.write(f'  [SKIP] {sym}: 資料不足')
            skip += 1

    print(f"\n完成：成功 {ok} 檔，跳過 {skip} 檔")
