import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from tqdm import tqdm
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from src.database import init_db, upsert_prices, get_last_date

# yfinance is rate-limit sensitive; Bybit public endpoints tolerate parallel calls.
# 6 workers is empirically safe for both.
_FETCH_WORKERS = 6

try:
    from pybit.unified_trading import HTTP as BybitHTTP
    PYBIT_AVAILABLE = True
except ImportError:
    PYBIT_AVAILABLE = False

_COMMODITY_YF_MAP = {
    'XAUUSD': 'GC=F',
    'XAGUSD': 'SI=F',
}

def _to_yf_symbol(symbol: str) -> str:
    if symbol in _COMMODITY_YF_MAP:
        return _COMMODITY_YF_MAP[symbol]
    return symbol


def asset_type_of(symbol: str) -> str:
    if symbol.endswith('.TW') or symbol.endswith('.TWO'):
        return 'TW Stock'
    if symbol.startswith('BYBIT:'):
        return 'Crypto'
    if symbol in config.COMMODITIES:
        return 'Commodity'
    return 'US Stock'


def _download_bybit(symbol: str, start: str, end: str) -> pd.DataFrame | None:
    """從 Bybit 公開 API 抓永續合約日線 OHLCV，自動分頁取完整區間。"""
    if not PYBIT_AVAILABLE:
        print(f'  [WARN] pybit 未安裝，無法抓取 {symbol}，執行: pip install pybit')
        return None

    bybit_sym = symbol[6:-2]  # BYBIT:BTCUSDT.P → BTCUSDT
    start_ts  = int(datetime.strptime(start, '%Y-%m-%d').timestamp() * 1000)
    end_ts    = int(datetime.strptime(end,   '%Y-%m-%d').timestamp() * 1000)

    session  = BybitHTTP()  # K線為公開端點，無需 API Key
    all_rows = []
    cursor   = end_ts

    while True:
        try:
            res = session.get_kline(
                category='linear',
                symbol=bybit_sym,
                interval='D',
                start=start_ts,
                end=cursor,
                limit=200,
            )
        except Exception as e:
            print(f'  [ERROR] {symbol}: {e}')
            return None

        rows = res.get('result', {}).get('list', [])
        if not rows:
            break

        all_rows.extend(rows)
        oldest_ts = int(rows[-1][0])
        if oldest_ts <= start_ts:
            break
        cursor = oldest_ts - 1

    if not all_rows:
        return None

    df = pd.DataFrame(all_rows, columns=['ts', 'Open', 'High', 'Low', 'Close', 'Volume', '_'])
    df['ts'] = pd.to_datetime(df['ts'].astype(int), unit='ms')
    df = df.set_index('ts').sort_index()
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
    df.index.name = None
    df = df[
        (df.index >= pd.Timestamp(start)) &
        (df.index <= pd.Timestamp(end))
    ].dropna(subset=['Close'])
    return df if not df.empty else None


def _download_single(symbol: str, start: str, end: str) -> pd.DataFrame | None:
    if symbol.startswith('BYBIT:'):
        return _download_bybit(symbol, start, end)

    yf_sym = _to_yf_symbol(symbol)
    try:
        df = yf.download(
            yf_sym,
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
    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        futs = {pool.submit(_download_single, sym, start_str, end_str): sym
                for sym in all_syms}
        for fut in tqdm(as_completed(futs), total=len(futs), desc='下載中', unit='檔'):
            sym = futs[fut]
            try:
                df = fut.result()
            except Exception as exc:
                tqdm.write(f'  [ERROR] {sym}: {exc}')
                skip += 1
                continue
            if df is not None and len(df) >= 20:
                upsert_prices(df, sym, asset_type_of(sym))
                ok += 1
            else:
                tqdm.write(f'  [SKIP] {sym}: 資料不足')
                skip += 1

    print(f"\n完成：成功 {ok} 檔，跳過 {skip} 檔")


def update_all_assets(assets: dict):
    """
    增量更新：只抓每個標的最後一筆日期之後的新資料。
    第一次沒資料的標的會自動回退到完整下載。
    """
    init_db()
    today     = datetime.now()
    end_str   = today.strftime('%Y-%m-%d')
    all_syms  = assets['all']

    print(f"\n增量更新 {len(all_syms)} 個資產（只補新資料）\n")
    ok, skip, no_new = 0, 0, 0

    # Plan each symbol's start date first (fast, hits DB only)
    plans: list[tuple[str, str]] = []
    for sym in all_syms:
        last = get_last_date(sym)
        if last is None:
            start_str = (today - timedelta(days=config.DATA_YEARS * 365 + 60)).strftime('%Y-%m-%d')
        else:
            last_dt = datetime.strptime(last, '%Y-%m-%d')
            next_dt = last_dt + timedelta(days=1)
            if next_dt.date() >= today.date():
                no_new += 1
                continue
            start_str = next_dt.strftime('%Y-%m-%d')
        plans.append((sym, start_str))

    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        futs = {pool.submit(_download_single, sym, s, end_str): (sym, s) for sym, s in plans}
        for fut in tqdm(as_completed(futs), total=len(futs), desc='更新中', unit='檔'):
            sym, start_str = futs[fut]
            try:
                df = fut.result()
            except Exception as exc:
                tqdm.write(f'  [ERROR] {sym}: {exc}')
                skip += 1
                continue
            if df is not None and len(df) >= 1:
                upsert_prices(df, sym, asset_type_of(sym))
                ok += 1
                tqdm.write(f'  [+{len(df)}筆] {sym}  ({start_str} → {end_str})')
            else:
                skip += 1

    print(f"\n完成：新增 {ok} 檔，已是最新 {no_new} 檔，無資料 {skip} 檔")
