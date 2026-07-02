"""SR-100A one-cycle characterization harness for ``main.cmd_live``.

Tests-only. Drives EXACTLY one scan cycle of the real live-arbitration loop by
monkeypatching every I/O boundary (executor, data, indicators, signals, ledger,
clock) and raising a sentinel from ``time.sleep`` -- the sole statement at the end
of the ``while True`` body (main.py:2291) -- so the loop can never iterate twice
and no real sleep is ever performed.

Zero real network, zero credentials, zero real orders. The real ``src.risk``
sizing/stop functions are left UNPATCHED so sizing behaviour is characterized, not
faked.
"""
from __future__ import annotations

import os
import socket
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd
import pytest

# Repo root (this file: tests/strategy_core/characterization/conftest.py).
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class OneCycleComplete(Exception):
    """Raised from the patched ``time.sleep`` to end the loop after one cycle."""


class NetworkAccessError(AssertionError):
    """Raised if any socket is opened during the driven cycle."""


class FakeExecutor:
    """In-memory stand-in for BybitExecutor. Records every order-ish call and
    performs no network I/O. All returns are deterministic."""

    def __init__(self, *, positions=(), wallet=5000.0, available=3123.45, live_price=100.0,
                 positions_after_sync=None):
        self._positions = [dict(p) for p in positions]
        # If given, returned by get_positions() from the SECOND call onward instead
        # of `positions`. Models a real exchange-side change between the cmd_live
        # startup sync call and the in-cycle _sync_remote_positions() reconciliation
        # call (e.g. a position closed externally in between) -- not a fake code
        # path, just a call-counted exchange snapshot.
        self._positions_after_sync = (
            None if positions_after_sync is None
            else [dict(p) for p in positions_after_sync]
        )
        self._get_positions_calls = 0
        self._wallet = float(wallet)
        self._available = float(available)
        self._live_price = float(live_price)
        self.calls = {"place_order": [], "close_position": [], "set_trading_stop": []}

    # --- account / market reads ---
    def get_account_info(self):
        return {"wallet_balance": self._wallet, "equity": self._wallet,
                "available": self._available, "position_im": 0.0,
                "unrealised_pnl": 0.0, "cum_realised_pnl": 0.0}

    def get_balance(self):
        return self._wallet

    def get_available_balance(self):
        return self._available

    def get_positions(self):
        self._get_positions_calls += 1
        if self._positions_after_sync is not None and self._get_positions_calls > 1:
            return [dict(p) for p in self._positions_after_sync]
        return [dict(p) for p in self._positions]

    def get_executions(self, *args, **kwargs):
        return []

    def get_closed_pnl(self, *args, **kwargs):
        return []

    def get_last_price(self, symbol):
        return self._live_price

    # --- formatting (identity-ish, deterministic) ---
    def format_qty(self, symbol, qty):
        return f"{float(qty):.8f}"

    def format_price(self, symbol, price):
        return f"{float(price):.4f}"

    # --- order-ish calls (recorded; never networked) ---
    def place_order(self, symbol, direction, qty, stop_loss, take_profit):
        self.calls["place_order"].append(
            {"symbol": symbol, "direction": direction, "qty": qty,
             "stop_loss": stop_loss, "take_profit": take_profit})
        return {"retCode": 0, "retMsg": "OK", "result": {"orderId": "FAKE-ORDER-1"}}

    def close_position(self, symbol, qty, direction):
        self.calls["close_position"].append(
            {"symbol": symbol, "qty": qty, "direction": direction})
        return {"retCode": 0, "retMsg": "OK", "result": {"orderId": "FAKE-CLOSE-1"}}

    def set_trading_stop(self, symbol, stop_loss=None, take_profit=None):
        self.calls["set_trading_stop"].append(
            {"symbol": symbol, "stop_loss": stop_loss, "take_profit": take_profit})
        return {"retCode": 0, "retMsg": "OK"}


def _make_price_df(sym, *, close=100.0, atr=2.0, rows=260):
    """A deterministic OHLCV+indicator frame long enough to pass the EMA_PERIOD+10
    length gate, ending safely before 'today' so _closed_daily_df keeps every row.
    The symbol is stashed on df.attrs so the faked signal generator can key on it."""
    end = pd.Timestamp.now().normalize() - pd.Timedelta(days=2)
    idx = pd.bdate_range(end=end, periods=rows)
    df = pd.DataFrame(
        {"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1.0,
         "atr": atr, "bb_mid": close, "rsi": 50.0},
        index=idx)
    df.attrs["sym"] = sym
    return df


def _make_signals(df, spec):
    """Build a signals dict aligned to df.index from a spec tuple
    (combined, score, trend, vp, bb)."""
    combined, score, trend, vp, bb = spec
    n = len(df.index)

    def s(v):
        return pd.Series([int(v)] * n, index=df.index, dtype=int)

    return {"combined": s(combined), "score": s(score), "trend": s(trend),
            "vp": s(vp), "bb": s(bb), "ema_bull": s(4), "ema_bear": s(0)}


def _fs_snapshot(*dirs):
    out = {}
    for d in dirs:
        base = _ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file():
                try:
                    st = p.stat()
                    out[str(p)] = (st.st_size, st.st_mtime_ns)
                except OSError:
                    pass
    return out


@pytest.fixture
def run_one_cycle(monkeypatch, tmp_path):
    """Return a callable that drives exactly one cmd_live cycle and returns the
    FakeExecutor plus recorded ledger writes. Raises AssertionError if the cycle
    fails any safety invariant (network, >1 cycle, real sleep, stray file write)."""

    import config
    import main
    import src.executor as src_executor
    import src.database as src_database
    import src.fetcher as src_fetcher
    import src.indicators as src_indicators
    import src.strategies as src_strategies
    import src.backtester as src_backtester
    import src.live_ledger as src_live_ledger

    def _run(*, cryptos, signals, positions=(), wallet=5000.0,
             available=3123.45, live_price=100.0, close_event_observer=None,
             positions_after_sync=None):
        # signals: {sym: (combined, score, trend, vp, bb)}
        fake = FakeExecutor(positions=positions, wallet=wallet,
                            available=available, live_price=live_price,
                            positions_after_sync=positions_after_sync)
        ledger_calls = []
        sleep_count = {"n": 0}

        def fake_sleep(_seconds):
            sleep_count["n"] += 1
            raise OneCycleComplete()

        def guard_socket(*args, **kwargs):
            raise NetworkAccessError("socket opened during driven cmd_live cycle")

        def fake_load_prices(sym, *args, **kwargs):
            return _make_price_df(sym)

        def fake_generate_all_signals(df, *args, **kwargs):
            sym = df.attrs.get("sym")
            spec = signals.get(sym, (0, 0, 0, 0, 0))
            return _make_signals(df, spec)

        def fake_record_bybit_order(**kwargs):
            ledger_calls.append(dict(kwargs))
            return len(ledger_calls)

        def fake_get_connection(*args, **kwargs):
            # Fresh in-memory ledger DB with the real column set: SELECTs return
            # empty (no rows), so ledger reconciliation runs cleanly without ever
            # touching the real on-disk database.
            conn = sqlite3.connect(":memory:")
            cols = ", ".join(f'"{c}" TEXT' for c in src_live_ledger.EXCEL_COLUMNS)
            conn.execute(f"CREATE TABLE IF NOT EXISTS bybit_live_orders ({cols})")
            conn.commit()
            return conn

        # --- clock / network guards ---
        monkeypatch.setattr(time, "sleep", fake_sleep)
        monkeypatch.setattr(socket, "socket", guard_socket)
        monkeypatch.delenv("BYBIT_DEMO_API_KEY", raising=False)
        monkeypatch.delenv("BYBIT_DEMO_API_SECRET", raising=False)

        # --- config surface ---
        monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "trading.db"))
        monkeypatch.setattr(
            config, "get_selected_assets",
            lambda seed=None: {"cryptos": list(cryptos), "us_stocks": [],
                               "tw_stocks": [], "commodities": [], "all": list(cryptos)})

        # --- executor ---
        monkeypatch.setattr(src_executor, "BybitExecutor", lambda *a, **k: fake)

        # --- database / fetcher (no real DB, no download) ---
        monkeypatch.setattr(src_database, "init_db", lambda *a, **k: None)
        monkeypatch.setattr(src_database, "get_all_symbols", lambda *a, **k: list(cryptos))
        monkeypatch.setattr(src_database, "get_last_date", lambda *a, **k: "2026-05-01")
        monkeypatch.setattr(src_database, "upsert_prices", lambda *a, **k: None)
        monkeypatch.setattr(src_database, "load_prices", fake_load_prices)
        monkeypatch.setattr(src_database, "get_connection", fake_get_connection)
        monkeypatch.setattr(src_fetcher, "_download_single", lambda *a, **k: None)
        monkeypatch.setattr(src_fetcher, "asset_type_of", lambda *a, **k: "Crypto")

        # --- indicators / signals (deterministic fixtures) ---
        monkeypatch.setattr(src_indicators, "compute_all_indicators", lambda df, *a, **k: df)
        monkeypatch.setattr(src_strategies, "generate_all_signals", fake_generate_all_signals)
        monkeypatch.setattr(src_strategies, "apply_cross_asset_filters", lambda *a, **k: None)
        monkeypatch.setattr(src_backtester, "_geometric_rr_ok", lambda *a, **k: True)

        # --- ledger (no SQLite / Excel writes) ---
        monkeypatch.setattr(src_live_ledger, "ensure_bybit_live_order_ledger", lambda *a, **k: None)
        monkeypatch.setattr(src_live_ledger, "export_bybit_live_orders_to_excel",
                            lambda *a, **k: str(tmp_path / "ledger.xlsx"))
        monkeypatch.setattr(src_live_ledger, "record_bybit_order", fake_record_bybit_order)

        args = _make_live_args()
        # SR-101D2: optionally inject the observational close-event observer.
        # Absent by default, so cmd_live's default behavior is exercised unchanged.
        if close_event_observer is not None:
            args._trade_history_close_event_observer = close_event_observer
        before = _fs_snapshot("data", "outputs")

        completed = False
        try:
            main.cmd_live(args)
        except OneCycleComplete:
            completed = True

        after = _fs_snapshot("data", "outputs")

        # --- safety invariants ---
        assert completed, "cmd_live ended before reaching the end-of-cycle sleep seam"
        assert sleep_count["n"] == 1, (
            f"expected exactly one end-of-cycle sleep (one cycle); got {sleep_count['n']}")
        assert before == after, (
            "cmd_live wrote/modified files under data/ or outputs/ during the cycle")

        return fake, ledger_calls

    return _run


def _make_live_args():
    import argparse
    # crypto_candidate="" makes _apply_crypto_candidate return None (no prev3y
    # universe rebuild), so the controlled get_selected_assets universe is used.
    return argparse.Namespace(command="live", seed=42, interval=15,
                              sync_only=False, crypto_candidate="")
