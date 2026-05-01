import sqlite3
import pandas as pd
from pathlib import Path
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


def get_connection() -> sqlite3.Connection:
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(config.DB_PATH)


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS prices (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol      TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                open        REAL,
                high        REAL,
                low         REAL,
                close       REAL,
                volume      REAL,
                asset_type  TEXT,
                UNIQUE(symbol, date)
            );
            CREATE INDEX IF NOT EXISTS idx_prices_symbol_date
                ON prices(symbol, date);

            CREATE TABLE IF NOT EXISTS asset_registry (
                symbol      TEXT PRIMARY KEY,
                asset_type  TEXT,
                first_date  TEXT,
                last_date   TEXT,
                bar_count   INTEGER
            );
        """)


def upsert_prices(df: pd.DataFrame, symbol: str, asset_type: str):
    """Insert or ignore duplicate (symbol, date) rows."""
    work = df.copy()
    if isinstance(work.index, pd.DatetimeIndex):
        work.index = work.index.strftime('%Y-%m-%d')
    work.index.name = 'date'
    work = work.reset_index()

    # Normalise column names to lowercase
    work.columns = [c.lower() for c in work.columns]
    work['symbol']     = symbol
    work['asset_type'] = asset_type

    needed = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'asset_type']
    for col in needed:
        if col not in work.columns:
            work[col] = None
    work = work[needed].dropna(subset=['close'])

    with get_connection() as conn:
        conn.executemany(
            """INSERT OR IGNORE INTO prices
               (symbol, date, open, high, low, close, volume, asset_type)
               VALUES (?,?,?,?,?,?,?,?)""",
            work[needed].itertuples(index=False, name=None),
        )
        # Update registry
        first = work['date'].min()
        last  = work['date'].max()
        count = len(work)
        conn.execute(
            """INSERT INTO asset_registry(symbol, asset_type, first_date, last_date, bar_count)
               VALUES (?,?,?,?,?)
               ON CONFLICT(symbol) DO UPDATE SET
               last_date=excluded.last_date, bar_count=excluded.bar_count""",
            (symbol, asset_type, first, last, count),
        )


def load_prices(symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    q = 'SELECT date, open, high, low, close, volume, asset_type FROM prices WHERE symbol=?'
    params = [symbol]
    if start_date:
        q += ' AND date>=?'; params.append(start_date)
    if end_date:
        q += ' AND date<=?'; params.append(end_date)
    q += ' ORDER BY date ASC'

    with get_connection() as conn:
        df = pd.read_sql_query(q, conn, params=params, parse_dates=['date'])
    df = df.set_index('date')
    df.index = pd.DatetimeIndex(df.index)
    df.columns = [c.capitalize() if c in ('open','high','low','close','volume') else c
                  for c in df.columns]
    df = df.rename(columns={'asset_type': 'asset_type'})
    return df


def get_all_symbols() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute('SELECT symbol FROM asset_registry').fetchall()
    return [r[0] for r in rows]


def get_registry() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query('SELECT * FROM asset_registry ORDER BY asset_type, symbol', conn)
