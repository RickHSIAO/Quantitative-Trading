import sqlite3
import json
import threading
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


_conn: sqlite3.Connection | None = None
_conn_lock = threading.Lock()
_write_lock = threading.Lock()


def get_connection() -> sqlite3.Connection:
    """Singleton connection with WAL + tuned PRAGMAs.

    sqlite3 's `with conn:` context manager commits on exit but does NOT close
    the connection — the singleton stays alive for the process lifetime.
    """
    global _conn
    if _conn is None:
        with _conn_lock:
            if _conn is None:
                Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=-65536")     # ~64 MB page cache
                conn.execute("PRAGMA temp_store=MEMORY")
                conn.execute("PRAGMA mmap_size=268435456")    # 256 MB mmap
                conn.commit()
                _conn = conn
    return _conn


def close_connection() -> None:
    """Close the singleton (test teardown / explicit shutdown)."""
    global _conn
    with _conn_lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def init_db():
    conn = get_connection()
    with _write_lock, conn:
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

            CREATE TABLE IF NOT EXISTS backtest_runs (
                run_id            INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at            TEXT    NOT NULL,
                version           TEXT,
                initial_capital   REAL,
                final_capital     REAL,
                total_return_pct  REAL,
                annual_return_pct REAL,
                total_trades      INTEGER,
                win_rate          REAL,
                profit_factor     REAL,
                sharpe_ratio      REAL,
                max_drawdown_pct  REAL,
                note              TEXT
            );

            CREATE TABLE IF NOT EXISTS backtest_trades (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id       INTEGER NOT NULL REFERENCES backtest_runs(run_id),
                symbol       TEXT,
                strategy     TEXT,
                direction    INTEGER,
                asset_type   TEXT,
                entry_date   TEXT,
                exit_date    TEXT,
                entry_price  REAL,
                exit_price   REAL,
                quantity     REAL,
                pnl          REAL,
                return_pct   REAL,
                holding_days INTEGER,
                r_multiple   REAL,
                mae          REAL,
                mfe          REAL,
                exit_reason  TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_bt_trades_run
                ON backtest_trades(run_id);
        """)
        # 舊資料庫 migration：補 version 欄位
        existing = {row[1] for row in conn.execute("PRAGMA table_info(backtest_runs)")}
        if 'version' not in existing:
            conn.execute("ALTER TABLE backtest_runs ADD COLUMN version TEXT")


def upsert_prices(df: pd.DataFrame, symbol: str, asset_type: str):
    """Insert or ignore duplicate (symbol, date) rows."""
    if df is None or df.empty:
        return

    # Build (symbol, date, open, high, low, close, volume, asset_type) tuples
    # without copying the whole frame.
    if isinstance(df.index, pd.DatetimeIndex):
        date_iter = df.index.strftime('%Y-%m-%d')
    else:
        date_iter = df.index.astype(str)

    cols_lower = {c.lower(): c for c in df.columns}
    def _col(name):
        return df[cols_lower[name]] if name in cols_lower else pd.Series([None] * len(df), index=df.index)

    o = _col('open').to_numpy()
    h = _col('high').to_numpy()
    lo = _col('low').to_numpy()
    c = _col('close').to_numpy()
    v = _col('volume').to_numpy()
    dates = list(date_iter)

    rows = [
        (symbol, dates[i], o[i], h[i], lo[i], c[i], v[i], asset_type)
        for i in range(len(df))
        if pd.notna(c[i])
    ]
    if not rows:
        return

    first = min(r[1] for r in rows)
    last  = max(r[1] for r in rows)
    count = len(rows)

    conn = get_connection()
    with _write_lock, conn:
        conn.executemany(
            """INSERT OR IGNORE INTO prices
               (symbol, date, open, high, low, close, volume, asset_type)
               VALUES (?,?,?,?,?,?,?,?)""",
            rows,
        )
        conn.execute(
            """INSERT INTO asset_registry(symbol, asset_type, first_date, last_date, bar_count)
               VALUES (?,?,?,?,?)
               ON CONFLICT(symbol) DO UPDATE SET
               last_date  = MAX(last_date,  excluded.last_date),
               first_date = MIN(first_date, excluded.first_date),
               bar_count  = (SELECT COUNT(*) FROM prices WHERE symbol=excluded.symbol)""",
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


def get_last_date(symbol: str) -> str | None:
    """回傳該標的在 DB 中最新的日期字串（YYYY-MM-DD），不存在則 None。"""
    with get_connection() as conn:
        row = conn.execute(
            'SELECT last_date FROM asset_registry WHERE symbol=?', (symbol,)
        ).fetchone()
    return row[0] if row else None


def get_all_symbols() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute('SELECT symbol FROM asset_registry').fetchall()
    return [r[0] for r in rows]


def get_registry() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query('SELECT * FROM asset_registry ORDER BY asset_type, symbol', conn)


# ─── 回測歷史 ─────────────────────────────────────────────────────────────────
def save_backtest_run(trades: list, metrics: dict, note: str = '',
                      version: str = '') -> int:
    """
    將回測結果寫入 backtest_runs 和 backtest_trades。
    回傳本次回測的 run_id。
    """
    init_db()
    run_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_connection()
    with _write_lock, conn:
        cur = conn.execute(
            """INSERT INTO backtest_runs
               (run_at, version, initial_capital, final_capital,
                total_return_pct, annual_return_pct, total_trades,
                win_rate, profit_factor, sharpe_ratio, max_drawdown_pct, note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_at,
                version,
                metrics.get('initial_capital'),
                metrics.get('final_capital'),
                metrics.get('total_return_pct'),
                metrics.get('annual_return_pct'),
                metrics.get('total_trades'),
                metrics.get('win_rate'),
                metrics.get('profit_factor'),
                metrics.get('sharpe_ratio'),
                metrics.get('max_drawdown_pct'),
                note,
            ),
        )
        run_id = cur.lastrowid

        rows = [
            (
                run_id,
                t.symbol, t.strategy, t.direction, t.asset_type,
                t.entry_date, t.exit_date,
                t.entry_price, t.exit_price, t.quantity,
                t.pnl, t.return_pct, t.holding_days,
                t.r_multiple, t.mae, t.mfe, t.exit_reason,
            )
            for t in trades if t.exit_date is not None
        ]
        conn.executemany(
            """INSERT INTO backtest_trades
               (run_id, symbol, strategy, direction, asset_type,
                entry_date, exit_date, entry_price, exit_price, quantity,
                pnl, return_pct, holding_days, r_multiple, mae, mfe, exit_reason)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )

    return run_id


def load_backtest_history(limit: int = 20) -> pd.DataFrame:
    """回傳最近 N 次回測的摘要（最新在前）。"""
    init_db()
    with get_connection() as conn:
        return pd.read_sql_query(
            'SELECT * FROM backtest_runs ORDER BY run_id DESC LIMIT ?',
            conn,
            params=(int(limit),),
        )


def load_backtest_trades(run_id: int) -> pd.DataFrame:
    """回傳指定 run_id 的所有交易明細。"""
    init_db()
    with get_connection() as conn:
        return pd.read_sql_query(
            'SELECT * FROM backtest_trades WHERE run_id=? ORDER BY entry_date',
            conn,
            params=(run_id,),
        )
