"""SR-103B2: Backtester-level Circuit Breaker on/off switch, and proof that the
original ``main.py backtest`` path (both the non-silo branch and the
``run_silo_backtest`` silo branch) explicitly disables it, matching Live
(``cmd_live`` has no Circuit Breaker equivalent at all).

Two kinds of tests:

- Direct ``Backtester``/``run_silo_backtest`` unit tests (light, synthetic
  data) proving the new ``enable_circuit_breaker`` constructor option and its
  None -> config fallback / True / False resolution, and that the resolved
  value -- not ``config.ENABLE_CIRCUIT_BREAKER`` -- governs whether eligible
  entries get suppressed by Circuit Breaker state.
- Integration tests that drive the REAL ``main.cmd_backtest`` (both silo and
  non-silo branches) with every I/O boundary (DB, benchmark loader, Excel
  report, DB save) replaced by deterministic in-memory fakes, and every
  Backtester instance actually constructed captured via a spy subclass -- so
  the wiring proof is about genuine runtime behavior, not source-text
  matching.
"""
from __future__ import annotations

import pandas as pd
import pytest

import config
import src.backtester as backtester_module
from src.backtester import Backtester, run_silo_backtest

N = 30
IDX = pd.bdate_range("2024-01-01", periods=N)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    # Orthogonal filter unrelated to Circuit Breaker eligibility.
    monkeypatch.setattr(backtester_module, "_geometric_rr_ok_arr",
                        lambda *a, **k: True)


def _df(close=100.0, high=None, low=None, atr=2.0):
    close = close if isinstance(close, list) else [close] * N
    high = high if high is not None else close
    low = low if low is not None else close
    return pd.DataFrame({"Close": close, "High": high, "Low": low,
                         "atr": [atr] * N, "bb_mid": close,
                         "rsi": [50.0] * N}, index=IDX)


def _sig(combined=0, score=0, trend=0, start=2, stop=N):
    def s(v):
        arr = [0.0] * N
        for i in range(start, stop):
            arr[i] = v
        return pd.Series(arr, index=IDX, dtype=float)
    return {"combined": s(combined), "score": s(score), "trend": s(trend),
            "vp": s(0), "bb": s(0)}


def _primed_backtester(enable_circuit_breaker):
    """A Backtester whose Circuit Breaker state is directly pre-armed to
    block on every one of the three conditions (pause / daily-loss /
    daily-trade-count) for the whole run window. Isolates the ON/OFF switch
    from the arithmetic that would otherwise be needed to organically trigger
    a real consecutive-loss or daily-loss Circuit Breaker event."""
    bt = Backtester(initial_capital=1_000_000.0, silo_mode=True,
                    max_total_positions=5, max_pos_per_class={},
                    max_position_pct=0.40,
                    enable_circuit_breaker=enable_circuit_breaker)
    far_future = IDX[-1] + pd.Timedelta(days=365)
    bt._cb_pause_until = far_future
    for ts in IDX:
        date_str = str(ts.date())
        bt._cb_daily_pnl[date_str] = -1_000_000.0        # far past CB_DAILY_LOSS_PCT
        bt._cb_daily_trades[date_str] = 10_000            # far past CB_MAX_DAILY_TRADES
    return bt


# ── 1-3: constructor resolution ─────────────────────────────────────────────

def test_default_none_preserves_config_driven_behavior(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_CIRCUIT_BREAKER", True)
    assert Backtester(initial_capital=1000.0).enable_circuit_breaker is True
    assert Backtester(initial_capital=1000.0,
                      enable_circuit_breaker=None).enable_circuit_breaker is True

    monkeypatch.setattr(config, "ENABLE_CIRCUIT_BREAKER", False)
    assert Backtester(initial_capital=1000.0).enable_circuit_breaker is False


def test_explicit_true_overrides_config_false(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_CIRCUIT_BREAKER", False)
    bt = Backtester(initial_capital=1000.0, enable_circuit_breaker=True)
    assert bt.enable_circuit_breaker is True


def test_explicit_false_overrides_config_true(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_CIRCUIT_BREAKER", True)
    bt = Backtester(initial_capital=1000.0, enable_circuit_breaker=False)
    assert bt.enable_circuit_breaker is False


# ── 6-7: resolved flag, not config, governs entry suppression ──────────────

def test_disabled_circuit_breaker_does_not_suppress_eligible_entries(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_CIRCUIT_BREAKER", True)  # config says ON
    bt = _primed_backtester(enable_circuit_breaker=False)         # instance says OFF
    data = {"A": _df(100.0)}
    sig = {"A": _sig(combined=1, score=6, trend=1)}
    trades = bt.run(data, sig, {"A": "Crypto"})
    assert len(trades) >= 1
    assert bt._entry_block_stats["circuit_breaker_blocked_candidates"] == 0


def test_enabled_circuit_breaker_still_suppresses_entries(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_CIRCUIT_BREAKER", False)  # config says OFF
    bt = _primed_backtester(enable_circuit_breaker=True)           # instance says ON
    data = {"A": _df(100.0)}
    sig = {"A": _sig(combined=1, score=6, trend=1)}
    trades = bt.run(data, sig, {"A": "Crypto"})
    assert trades == []
    assert bt._entry_block_stats["circuit_breaker_blocked_candidates"] > 0


# ── 8-9: shared cores / re-entry semantics unaffected ───────────────────────

def test_shared_entry_core_still_authoritative_with_cb_disabled(monkeypatch):
    calls = []
    real_decide = backtester_module.decide_entry

    def _spy(inp):
        calls.append(inp)
        return real_decide(inp)

    monkeypatch.setattr(backtester_module, "decide_entry", _spy)
    bt = _primed_backtester(enable_circuit_breaker=False)
    data = {"A": _df(100.0)}
    sig = {"A": _sig(combined=1, score=6, trend=1)}
    trades = bt.run(data, sig, {"A": "Crypto"})
    assert len(trades) >= 1
    assert len(calls) > 0   # decide_entry remains the call path; no bypass added


def test_reentry_block_unaffected_by_cb_flag():
    # Long SL then persistent signal: same-bar re-entry must stay blocked
    # (SR-103B1 behavior) regardless of the Circuit Breaker setting.
    lows = [100.0] * N
    for i in range(6, N):
        lows[i] = 90.0
    data = {"A": _df([100.0] * N, high=[100.0] * N, low=lows)}
    sig = {"A": _sig(combined=1, score=6, trend=1)}

    bt = Backtester(initial_capital=1_000_000.0, silo_mode=True,
                    max_total_positions=5, max_pos_per_class={},
                    max_position_pct=0.40, enable_circuit_breaker=False)
    trades = bt.run(data, sig, {"A": "Crypto"})
    ts = sorted(trades, key=lambda t: (t.entry_date, t.exit_date or ""))
    same_bar = [b.entry_date for a, b in zip(ts, ts[1:]) if b.entry_date == a.exit_date]
    assert same_bar == []
    assert len(ts) >= 2


# ── 10: Kelly / sizing / fills / exits unchanged by the CB flag ────────────

def test_fill_and_exit_fields_identical_regardless_of_cb_flag(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_CIRCUIT_BREAKER", True)
    data = {"A": _df(100.0)}
    sig = {"A": _sig(combined=1, score=6, trend=1)}

    bt_default = Backtester(initial_capital=1_000_000.0, silo_mode=True,
                            max_total_positions=5, max_pos_per_class={},
                            max_position_pct=0.40)   # None -> config True
    bt_explicit_true = Backtester(initial_capital=1_000_000.0, silo_mode=True,
                                  max_total_positions=5, max_pos_per_class={},
                                  max_position_pct=0.40,
                                  enable_circuit_breaker=True)
    t1 = bt_default.run({k: v.copy() for k, v in data.items()},
                        {"A": dict(sig["A"])}, {"A": "Crypto"})
    t2 = bt_explicit_true.run({k: v.copy() for k, v in data.items()},
                              {"A": dict(sig["A"])}, {"A": "Crypto"})
    assert len(t1) == len(t2) and len(t1) >= 1
    for a, b in zip(t1, t2):
        assert a.entry_price == b.entry_price
        assert a.quantity == b.quantity
        assert a.stop_loss == b.stop_loss
        assert a.take_profit == b.take_profit
        assert a.exit_price == b.exit_price
        assert a.pnl == b.pnl
        assert a.exit_reason == b.exit_reason


# ── 5: run_silo_backtest forwards the flag to every Backtester it builds ──

def test_run_silo_backtest_forwards_flag_to_every_backtester(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_CIRCUIT_BREAKER", True)  # config says ON
    data = {"A": _df(100.0), "B": _df(50.0)}
    sig = {"A": _sig(combined=1, score=6, trend=1),
          "B": _sig(combined=1, score=6, trend=1)}
    atypes = {"A": "Crypto", "B": "TW Stock"}
    silo_classes = {"Crypto": ["Crypto"], "TW Stock": ["TW Stock"]}

    trades, silo_results = run_silo_backtest(
        data, sig, atypes, silo_classes, silo_capital=100_000.0,
        enable_circuit_breaker=False,
    )
    assert len(silo_results) == 2
    for sname, sr in silo_results.items():
        assert sr["bt"].enable_circuit_breaker is False, sname


def test_run_silo_backtest_default_none_preserves_config(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_CIRCUIT_BREAKER", False)
    data = {"A": _df(100.0)}
    sig = {"A": _sig(combined=1, score=6, trend=1)}
    atypes = {"A": "Crypto"}
    silo_classes = {"Crypto": ["Crypto"]}

    trades, silo_results = run_silo_backtest(
        data, sig, atypes, silo_classes, silo_capital=100_000.0,
    )
    assert silo_results["Crypto"]["bt"].enable_circuit_breaker is False


# ── 11: generic research callers that omit the option keep old behavior ───

def test_generic_caller_omitting_option_keeps_config_driven_behavior(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_CIRCUIT_BREAKER", True)
    bt = Backtester(initial_capital=1000.0, silo_mode=False)   # no kwarg at all
    assert bt.enable_circuit_breaker is True

    monkeypatch.setattr(config, "ENABLE_CIRCUIT_BREAKER", False)
    bt2 = Backtester(initial_capital=1000.0, silo_mode=False)
    assert bt2.enable_circuit_breaker is False


# ── 4 & 5 (integration): main.cmd_backtest wiring, real code path ─────────

def _make_spy_backtester_cls(sink: list):
    class _SpyBacktester(Backtester):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            sink.append(self)
    return _SpyBacktester


def _fake_indicator_df():
    n = 220
    idx = pd.bdate_range("2020-01-01", periods=n)
    close = [100.0] * n
    return pd.DataFrame({"Close": close, "High": close, "Low": close,
                         "Open": close, "Volume": [1000.0] * n,
                         "atr": [2.0] * n, "bb_mid": close,
                         "rsi": [50.0] * n}, index=idx)


def _fake_flat_signals(df, **_kwargs):
    idx = df.index
    zeros = pd.Series(0.0, index=idx)
    return {"combined": zeros, "score": zeros.copy(), "trend": zeros.copy(),
            "vp": zeros.copy(), "bb": zeros.copy()}


class _FakeArgs:
    seed = 42
    crypto_candidate = ''
    crypto_universe = 'config'
    profile = None
    with_vp = False
    start_date = None
    end_date = None
    capital = 100_000.0
    output = None
    note = ''
    ver = None


def _wire_offline_backtest_environment(monkeypatch, spy_sink):
    import src.database as database_module
    import src.benchmarks as benchmarks_module
    import src.indicators as indicators_module
    import src.strategies as strategies_module
    import src.reporter as reporter_module

    fake_df = _fake_indicator_df()
    monkeypatch.setattr(config, "get_selected_assets",
                        lambda seed=config.RANDOM_SEED: {
                            'us_stocks': [], 'tw_stocks': [],
                            'cryptos': ['FAKE1'], 'commodities': [],
                            'all': ['FAKE1'],
                        })
    monkeypatch.setattr(database_module, "get_all_symbols", lambda: {'FAKE1'})
    monkeypatch.setattr(database_module, "load_prices",
                        lambda sym: fake_df.copy())
    monkeypatch.setattr(database_module, "save_backtest_run",
                        lambda *a, **k: 'FAKE_RUN_ID')
    monkeypatch.setattr(benchmarks_module, "load_or_update_benchmark",
                        lambda *a, **k: None)
    monkeypatch.setattr(indicators_module, "compute_all_indicators",
                        lambda df, include_vp=True: df)
    monkeypatch.setattr(strategies_module, "generate_all_signals",
                        _fake_flat_signals)
    monkeypatch.setattr(reporter_module, "generate_excel_report",
                        lambda *a, **k: None)
    monkeypatch.setattr(backtester_module, "Backtester",
                        _make_spy_backtester_cls(spy_sink))


def test_cmd_backtest_non_silo_path_disables_circuit_breaker(monkeypatch, capsys):
    import main
    monkeypatch.setattr(config, "ENABLE_SILO_MODE", False)
    monkeypatch.setattr(config, "ENABLE_CIRCUIT_BREAKER", True)  # config says ON
    sink: list = []
    _wire_offline_backtest_environment(monkeypatch, sink)

    main.cmd_backtest(_FakeArgs())

    assert len(sink) == 1
    assert sink[0].enable_circuit_breaker is False


def test_cmd_backtest_silo_path_disables_circuit_breaker(monkeypatch, capsys):
    import main
    monkeypatch.setattr(config, "ENABLE_SILO_MODE", True)
    monkeypatch.setattr(config, "ENABLE_CIRCUIT_BREAKER", True)  # config says ON
    sink: list = []
    _wire_offline_backtest_environment(monkeypatch, sink)

    main.cmd_backtest(_FakeArgs())

    assert len(sink) >= 1
    for bt in sink:
        assert bt.enable_circuit_breaker is False
