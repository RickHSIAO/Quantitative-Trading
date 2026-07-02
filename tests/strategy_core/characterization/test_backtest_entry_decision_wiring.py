"""SR-102C1: characterization that src/backtester.py's ENTRY arbitration is now
driven authoritatively by the shared Entry Decision Core (decide_entry).

These tests drive the real ``Backtester.run`` engine -- the ORIGINAL main.py
strategy backtest path (the one ``cmd_backtest`` / ``run_silo_backtest`` use, and
which the Prev3Y cross-sectional script merely REUSES with a different universe).
They pin: no-signal / below-threshold rejection, valid long/short entry, the
exact ``>=`` score threshold, existing-position suppression, absence of a
re-entry cooldown, the global cap (break) vs per-strategy cap (continue), the
trend/vp/bb/combined family selection, malformed-family coercion, fill/sizing
invariants, exit behavior, and that decide_entry is the sole authority.

Signal timing: ``Backtester`` shifts every signal by one bar (a signal computed
at the close of bar t-1 acts on bar t), so a signal active from bar ``s`` first
takes effect on bar ``s+1``.

Isolation: the geometric-RR entry filter and the circuit breaker are portfolio
mechanics ORTHOGONAL to entry eligibility; both are neutralized here (as the Live
characterization harness neutralizes ``_geometric_rr_ok``) so these tests observe
the entry-arbitration verdict in isolation. Sizing/fees/fills run UNPATCHED.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
import src.backtester as backtester_module
from src.backtester import Backtester, _slip
from src.risk import calculate_stops, estimate_kelly_from_history, position_size
from src.strategy_core.entry_decision import EntryAction, EntryReasonCode, EntryDecisionResult

N = 20
IDX = pd.bdate_range("2024-01-01", periods=N)


@pytest.fixture(autouse=True)
def _isolate_entry_arbitration(monkeypatch):
    # Neutralize the geometric-RR entry filter (so flat synthetic prices don't
    # spuriously reject otherwise-eligible entries) and the circuit breaker
    # (a daily portfolio-risk throttle unrelated to entry eligibility).
    monkeypatch.setattr(backtester_module, "_geometric_rr_ok_arr",
                        lambda *a, **k: True)
    monkeypatch.setattr(config, "ENABLE_CIRCUIT_BREAKER", False)


def _df(close=100.0, atr=2.0, high=None, low=None):
    highs = [close] * N if high is None else high
    lows = [close] * N if low is None else low
    return pd.DataFrame(
        {"Close": [close] * N if not isinstance(close, list) else close,
         "High": highs, "Low": lows,
         "atr": [atr] * N, "bb_mid": [close] * N if not isinstance(close, list) else close,
         "rsi": [50.0] * N},
        index=IDX,
    )


# Signals are switched OFF a few bars before the end: the backtester EOD-closes
# any open position on the final bar and (with the signal still live) would
# re-enter it the same bar -- a pre-existing engine quirk, identical old vs new
# (proven by the byte-exact parity harness). Ending the signal early isolates a
# single clean entry without that final-bar re-entry.
_STOP = N - 4


def _sig(spec, stop=_STOP):
    """spec: dict of key -> (start_bar, value); each signal is ``value`` from
    start_bar up to (not including) ``stop``, else 0. Returns a signals dict."""
    out = {}
    for key in ("combined", "score", "trend", "vp", "bb"):
        start, value = spec.get(key, (0, 0))
        arr = [0.0] * N
        for i in range(start, stop):
            arr[i] = value
        out[key] = pd.Series(arr, index=IDX, dtype=float)
    return out


def _persistent(combined, score, trend=0, vp=0, bb=0, start=2, stop=_STOP):
    return _sig({"combined": (start, combined), "score": (start, score),
                 "trend": (start, trend), "vp": (start, vp), "bb": (start, bb)}, stop=stop)


def _run(symbols, *, max_total_positions=5, max_pos_per_class=None,
         capital=1_000_000.0):
    data = {s: spec[0] for s, spec in symbols.items()}
    signals = {s: spec[1] for s, spec in symbols.items()}
    atypes = {s: spec[2] for s, spec in symbols.items()}
    bt = Backtester(
        initial_capital=capital, silo_mode=True,
        max_total_positions=max_total_positions,
        max_pos_per_class={} if max_pos_per_class is None else max_pos_per_class,
        max_position_pct=0.40,
    )
    trades = bt.run(data, signals, atypes)
    return bt, trades


# ── 1. no signal -> no entry ────────────────────────────────────────────────
def test_no_signal_produces_no_entry():
    _, trades = _run({"A": (_df(), _persistent(0, 0), "Crypto")})
    assert trades == []


# ── 2. below-threshold signal -> no entry ───────────────────────────────────
def test_below_threshold_signal_produces_no_entry():
    # Crypto min score is 3; score 2 must be rejected.
    assert config.MIN_ENTRY_SCORE_BY_CLASS["Crypto"] == 3
    _, trades = _run({"A": (_df(), _persistent(1, 2, trend=1), "Crypto")})
    assert trades == []


# ── 3. valid long -> exactly one long entry ─────────────────────────────────
def test_valid_long_produces_one_long_entry():
    _, trades = _run({"A": (_df(), _persistent(1, 6, trend=1), "Crypto")})
    assert len(trades) == 1
    assert trades[0].direction == 1
    assert trades[0].strategy == "trend"


# ── 4. valid short -> exactly one short entry ───────────────────────────────
def test_valid_short_produces_one_short_entry():
    _, trades = _run({"A": (_df(), _persistent(-1, 6, trend=-1), "Crypto")})
    assert len(trades) == 1
    assert trades[0].direction == -1
    assert trades[0].strategy == "trend"


# ── 5. exact threshold accepted (>=) ────────────────────────────────────────
def test_exact_threshold_is_accepted():
    _, trades = _run({"A": (_df(), _persistent(1, 3, trend=1), "Crypto")})
    assert len(trades) == 1
    assert trades[0].direction == 1


# ── 6. existing position suppresses duplicate entry ─────────────────────────
def test_existing_position_suppresses_duplicate_entry():
    # The long signal is active for ~17 consecutive bars; only ONE entry is
    # opened -- every later bar is suppressed because the position is open.
    _, trades = _run({"A": (_df(), _persistent(1, 6, trend=1), "Crypto")})
    assert len(trades) == 1                       # not 17


# ── 7. no re-entry cooldown: a flip closes and reverses in the same engine ──
def test_backtest_has_no_reentry_cooldown_flip_reverses():
    # Long from bar 2, flips to short from bar 9. The signal_flip closes the long
    # and -- with NO re-entry block in the backtest -- a reverse short is opened
    # the same/next bar (proving reentry_blocked is faithfully False, unchanged).
    sig = _sig({"combined": (2, 1), "score": (2, 6), "trend": (2, 1)}, stop=9)
    for i in range(9, _STOP):        # short from bar 9, off before EOD
        sig["combined"].iloc[i] = -1.0
        sig["score"].iloc[i] = 6.0
        sig["trend"].iloc[i] = -1.0
    _, trades = _run({"A": (_df(), sig, "Crypto")})
    trades = sorted(trades, key=lambda t: t.entry_date)
    assert len(trades) == 2
    assert trades[0].direction == 1
    assert trades[1].direction == -1
    assert "flip" in (trades[0].exit_reason or "").lower() or trades[0].exit_reason


# ── 8. global cap -> break (later lower-score candidates not entered) ────────
def test_global_cap_break_stops_lower_score_candidates():
    symbols = {
        "A": (_df(close=100.0), _persistent(1, 7, trend=1), "Crypto"),
        "B": (_df(close=50.0), _persistent(1, 6, trend=1), "Crypto"),
        "C": (_df(close=30.0), _persistent(1, 5, trend=1), "Crypto"),
    }
    bt, trades = _run(symbols, max_total_positions=2)
    entered = {t.symbol for t in trades}
    assert entered == {"A", "B"}                  # C never enters (cap filled)
    assert "C" not in entered
    assert bt._entry_block_stats["max_total_positions_hits"] >= 1


# ── 9. per-strategy cap -> continue (a different-family later candidate still
#      enters) ──────────────────────────────────────────────────────────────
def test_strategy_cap_continue_allows_other_family(monkeypatch):
    monkeypatch.setattr(config, "MAX_POS_PER_STRATEGY", {"trend": 1})
    symbols = {
        "A": (_df(close=100.0), _persistent(1, 7, trend=1), "Crypto"),   # trend
        "B": (_df(close=50.0), _persistent(1, 6, trend=1), "Crypto"),    # trend (capped)
        "C": (_df(close=30.0), _persistent(1, 5, vp=1), "Crypto"),       # vp (still ok)
    }
    bt, trades = _run(symbols, max_total_positions=5)
    entered = {t.symbol for t in trades}
    assert "A" in entered                          # first trend fills the cap
    assert "B" not in entered                      # second trend skipped (continue)
    assert "C" in entered                          # different family still enters
    assert bt._entry_block_stats["strategy_limit_hits"] >= 1
    assert bt._entry_block_stats["max_total_positions_hits"] == 0


# ── 10-12. family selection matches the shared core ─────────────────────────
def test_trend_family_selected():
    _, trades = _run({"A": (_df(), _persistent(1, 6, trend=1), "Crypto")})
    assert trades[0].strategy == "trend"


def test_vp_family_selected():
    _, trades = _run({"A": (_df(), _persistent(1, 6, vp=1), "Crypto")})
    assert trades[0].strategy == "vp"


def test_bb_family_selected():
    # BB has TSL disabled; flat prices keep it open to EOD.
    _, trades = _run({"A": (_df(), _persistent(-1, 6, bb=-1), "Crypto")})
    assert trades[0].strategy == "bb"


# ── 13. family tie -> 'combined' ────────────────────────────────────────────
def test_family_tie_resolves_to_combined():
    # trend AND vp both match the +1 direction -> combined
    _, trades = _run({"A": (_df(), _persistent(1, 6, trend=1, vp=1), "Crypto")})
    assert trades[0].strategy == "combined"


# ── 14. malformed family data: coerced to 0 (fillna), never raises ──────────
def test_malformed_family_data_is_coerced_not_raised():
    # The trend family carries NaN; the backtester's _sig_arr fillna(0)-cleans it
    # BEFORE the shared core sees it (distinct from Live, where int(NaN) raises),
    # so the symbol still enters and the family resolves to the clean vp signal.
    sig = _persistent(1, 6, vp=1)
    sig["trend"] = pd.Series([float("nan")] * N, index=IDX, dtype=float)
    _, trades = _run({"A": (_df(), sig, "Crypto")})
    assert len(trades) == 1
    assert trades[0].direction == 1
    assert trades[0].strategy == "vp"             # NaN trend -> 0 -> excluded


# ── 15. fill price and Kelly sizing are unchanged (unpatched real math) ─────
def test_fill_price_and_sizing_are_unchanged():
    capital = 1_000_000.0
    atr = 2.0
    close = 100.0
    bt, trades = _run(
        {"A": (_df(close=close, atr=atr), _persistent(1, 6, trend=1), "Crypto")},
        max_total_positions=1, capital=capital,
    )
    assert len(trades) == 1
    t = trades[0]
    # Exact slipped fill (long pays a touch more): entry = close*(1 + dir*slip)
    expected_entry = close * (1.0 + 1 * _slip("Crypto", is_limit=False))
    assert t.entry_price == pytest.approx(expected_entry)
    # Independent quantity via the real position_size, replicating the engine's
    # single-slot budget path (EQUAL_CASH_SPLIT off, no score-tier, no ATR halve).
    kf = estimate_kelly_from_history([], window=config.KELLY_WINDOW, asset_type="Crypto")
    sl, _tp = calculate_stops(expected_entry, 1, atr, strategy="trend", asset_type="Crypto")
    expected_qty = position_size(capital, kf, expected_entry, sl,
                                 asset_type="Crypto", max_position_pct=0.40)
    assert t.quantity == pytest.approx(expected_qty)
    assert t.quantity > 0


# ── 16. exits are unchanged: a long that reaches TP closes at TP ────────────
def test_exit_behavior_unchanged_take_profit():
    # Rising highs let a long reach take-profit; assert it closes as a profit exit.
    highs = [100.0] * N
    for i in range(5, N):
        highs[i] = 100.0 + (i - 4) * 5.0
    df = _df(close=100.0, high=highs, low=[99.0] * N)
    # A brief entry pulse (bars 2-3) so the position enters once at bar 3 and,
    # after the TP closes it, no live signal re-enters it.
    _, trades = _run({"A": (df, _persistent(1, 6, trend=1, start=2, stop=4), "Crypto")})
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_price is not None and t.pnl is not None
    assert t.exit_price >= t.take_profit - 1e-6    # closed at/through TP
    assert t.pnl > 0


# ── 17. decide_entry is the sole authority: forcing HOLD blocks all entries ──
def test_decide_entry_is_authoritative(monkeypatch):
    consulted = {"n": 0}

    def forced_hold(inp):
        consulted["n"] += 1
        return EntryDecisionResult(EntryAction.HOLD, 0, inp.score, "combined",
                                   EntryReasonCode.NO_SIGNAL)

    monkeypatch.setattr(backtester_module, "decide_entry", forced_hold)
    _, trades = _run({"A": (_df(), _persistent(1, 6, trend=1), "Crypto")})
    assert consulted["n"] > 0                      # the engine consulted the core
    assert trades == []                            # and obeyed HOLD -> no entry


# ── 18. existing-position suppression is decided authoritatively through the
#       shared core (Stage 0), BEFORE any signal/win-rate/family access ───────
def test_existing_position_suppression_is_authoritative(monkeypatch):
    # Spy on the shared core to capture exactly which EntryDecisionInput the
    # backtester hands it. A long from bar 2 opens A at bar 3; A then stays open
    # for many later bars. On every such bar the engine must consult the core
    # with has_open_position=True and obey its HOLD -- and, crucially, that call
    # must carry ONLY the Stage-0 neutral placeholders (no real signal / score /
    # family), proving the already-open symbol's data was never read (the old
    # `if sym in open_positions: continue` short-circuit, now routed through
    # decide_entry with no second inline existing-position gate).
    real_decide_entry = backtester_module.decide_entry
    calls = []

    def spy(inp):
        calls.append(inp)
        return real_decide_entry(inp)

    monkeypatch.setattr(backtester_module, "decide_entry", spy)
    _, trades = _run({"A": (_df(), _persistent(1, 6, trend=1), "Crypto")})

    # (4) no duplicate entry despite the multi-bar signal
    assert len(trades) == 1

    open_calls = [c for c in calls if c.symbol == "A" and c.has_open_position]
    # (1) the core received has_open_position=True while A was already open
    assert open_calls, "expected Stage-0 calls with has_open_position=True"
    for c in open_calls:
        # (2)+(3) HOLD obeyed AND signals untouched: each is the Stage-0
        # placeholder (combined_signal=1, score==minimum_score, family all 0),
        # never a call carrying A's real signal/score/family values.
        assert c.combined_signal == 1
        assert c.score == c.minimum_score
        assert c.trend_signal == 0
        assert c.volume_profile_signal == 0
        assert c.bollinger_signal == 0


# ═══════════════════════════════════════════════════════════════════════════
# SR-103B1: Backtest re-entry block must match Live exactly.
# Live (main.py): after every successful close whose reason != 'FLIP',
# `_block_reentry(sym, dt_latest, reason)` blocks re-entry until a strictly
# later daily signal; FLIP is excluded so same-cycle reverse entry stays
# possible. The backtester now records the close bar for blocking reasons and
# passes reentry_blocked into decide_entry (the sole authority).
# ═══════════════════════════════════════════════════════════════════════════

def _sorted(trades):
    return sorted(trades, key=lambda t: (t.entry_date, t.exit_date or ""))


def _same_bar_reentries(trades):
    """Entry dates that coincide with the immediately-preceding close's exit
    date -- i.e. a re-entry on the SAME signal bar as a close (what Live forbids
    for non-FLIP closes)."""
    ts = _sorted(trades)
    return [b.entry_date for a, b in zip(ts, ts[1:]) if b.entry_date == a.exit_date]


def _one_sl_dip_low(entry_bar_low=100.0, dip_bars=(6, 7)):
    lows = [100.0] * N
    for i in dip_bars:
        lows[i] = 90.0            # drives a long SL (stop ~96 from entry 100)
    return lows


def _one_sl_spike_high(spike_bars=(6, 7)):
    highs = [100.0] * N
    for i in spike_bars:
        highs[i] = 110.0          # drives a short SL
    return highs


# ── 1. Long SL close does not re-enter on the same signal bar ───────────────
def test_long_sl_no_same_bar_reentry():
    df = _df(close=[100.0] * N, high=[100.0] * N, low=_one_sl_dip_low())
    _, trades = _run({"A": (df, _persistent(1, 6, trend=1), "Crypto")})
    assert _same_bar_reentries(trades) == []          # Live rule
    assert len(trades) >= 2                            # re-entry DID resume later


# ── 2. Short SL close does not re-enter on the same signal bar ───────────────
def test_short_sl_no_same_bar_reentry():
    df = _df(close=[100.0] * N, high=_one_sl_spike_high(), low=[100.0] * N)
    _, trades = _run({"A": (df, _persistent(-1, 6, trend=-1), "Crypto")})
    assert _same_bar_reentries(trades) == []
    assert len(trades) >= 2


# ── 3. Long TP close does not re-enter on the same signal bar ───────────────
def test_long_tp_no_same_bar_reentry():
    highs = [100.0] * N
    for i in range(6, N):
        highs[i] = 200.0          # long TP (~108) reached repeatedly
    df = _df(close=[100.0] * N, high=highs, low=[100.0] * N)
    _, trades = _run({"A": (df, _persistent(1, 6, trend=1), "Crypto")})
    assert _same_bar_reentries(trades) == []
    assert len(trades) >= 2


# ── 4. Short TP close does not re-enter on the same signal bar ───────────────
def test_short_tp_no_same_bar_reentry():
    lows = [100.0] * N
    for i in range(6, N):
        lows[i] = 40.0            # short TP reached repeatedly
    df = _df(close=[100.0] * N, high=[100.0] * N, low=lows)
    _, trades = _run({"A": (df, _persistent(-1, 6, trend=-1), "Crypto")})
    assert _same_bar_reentries(trades) == []
    assert len(trades) >= 2


# ── 5. Early-exit (BB) close does not re-enter on the same signal bar ────────
def test_bb_early_exit_no_same_bar_reentry():
    # bb_mid below price -> a long 'bb' position hits the bb_mid early exit.
    df = _df(close=[100.0] * N, high=[100.0] * N, low=[100.0] * N)
    df["bb_mid"] = 95.0
    _, trades = _run({"A": (df, _persistent(1, 6, bb=1), "Crypto")})
    assert all(t.strategy == "bb" for t in trades)     # dominant family = bb
    assert _same_bar_reentries(trades) == []
    assert len(trades) >= 2


# ── 6. FLIP still closes and reverses same-cycle (NOT blocked) ───────────────
def test_flip_reverse_entry_still_allowed_same_bar():
    sig = _sig({"combined": (2, 1), "score": (2, 6), "trend": (2, 1)}, stop=8)
    for i in range(8, _STOP):        # opposite (short) signal, then off before EOD
        sig["combined"].iloc[i] = -1.0
        sig["score"].iloc[i] = 6.0
        sig["trend"].iloc[i] = -1.0
    _, trades = _run({"A": (_df(), sig, "Crypto")})
    ts = _sorted(trades)
    assert len(ts) == 2
    assert ts[0].direction == 1 and ts[1].direction == -1
    # FLIP reverse entry occurs on the SAME bar as the flip close (unblocked) --
    # exactly Live's `reason != 'FLIP'` exclusion.
    assert ts[1].entry_date == ts[0].exit_date


# ── 7. A held (never-stopped) position creates no re-entry state ─────────────
def test_no_close_creates_no_reentry_state():
    # Brief signal -> one entry, flat price -> holds to EOD. The only close is
    # EOD, which is NOT a blocking reason; nothing spurious is created. (The
    # backtester has no failed-close path, so "failed/nonexistent close" reduces
    # to: a non-blocking close never blocks.)
    _, trades = _run({"A": (_df(), _persistent(1, 6, trend=1, start=2, stop=4), "Crypto")})
    assert len(trades) == 1
    assert _same_bar_reentries(trades) == []


# ── 8. The block expires at the next bar (exact Live-equivalent point) ───────
def test_block_expires_on_next_bar():
    # One SL dip at bars 6-7 only; price recovers after. Entry -> SL close on the
    # dip bar (blocked that bar) -> re-entry on the FOLLOWING bar (block cleared).
    df = _df(close=[100.0] * N, high=[100.0] * N, low=_one_sl_dip_low(dip_bars=(6, 7)))
    _, trades = _run({"A": (df, _persistent(1, 6, trend=1), "Crypto")})
    ts = _sorted(trades)
    assert len(ts) >= 2
    first_exit = ts[0].exit_date
    reentry = ts[1].entry_date
    assert reentry > first_exit                        # strictly later bar
    # and the re-entry is the VERY NEXT trading bar after the close
    bars = list(IDX.strftime("%Y-%m-%d"))
    assert bars.index(reentry) == bars.index(first_exit) + 1


# ── 9. decide_entry receives reentry_blocked=True when applicable ───────────
def test_decide_entry_receives_reentry_blocked_true(monkeypatch):
    real = backtester_module.decide_entry
    calls = []

    def spy(inp):
        calls.append(inp)
        return real(inp)

    monkeypatch.setattr(backtester_module, "decide_entry", spy)
    df = _df(close=[100.0] * N, high=[100.0] * N, low=_one_sl_dip_low())
    _run({"A": (df, _persistent(1, 6, trend=1), "Crypto")})
    assert any(c.symbol == "A" and c.reentry_blocked for c in calls), \
        "expected at least one decide_entry call with reentry_blocked=True"


# ── 10. A REENTRY_BLOCKED HOLD short-circuits before family reads / sizing ───
def test_reentry_blocked_hold_prevents_family_and_sizing(monkeypatch):
    real = backtester_module.decide_entry
    calls = []

    def spy(inp):
        calls.append(inp)
        return real(inp)

    monkeypatch.setattr(backtester_module, "decide_entry", spy)
    df = _df(close=[100.0] * N, high=[100.0] * N, low=_one_sl_dip_low())
    _run({"A": (df, _persistent(1, 6, trend=1), "Crypto")})
    blocked_calls = [c for c in calls if c.reentry_blocked]
    assert blocked_calls
    for c in blocked_calls:
        # the re-entry stage runs BEFORE the family stage: family signals are
        # still the neutral placeholder 0, proving no family read happened before
        # the REENTRY_BLOCKED HOLD (and thus no sizing followed).
        assert c.trend_signal == 0
        assert c.volume_profile_signal == 0
        assert c.bollinger_signal == 0


# ── 11-14 are covered by the existing suite + the isolated parity harness:
#   11 existing-position short-circuit  -> test_existing_position_suppression_is_authoritative
#   12 global/class/strategy caps       -> test_global_cap_break_*, test_strategy_cap_continue_*
#   13 Kelly/sizing/fill unchanged      -> test_fill_price_and_sizing_are_unchanged
# ── 14. Tradability is pinned to the ACTUAL Backtest universe semantics ──────
def test_tradability_is_accurate_via_zero_signal_masking(monkeypatch):
    # The real `main.py backtest` path enforces per-year universe membership by
    # MASKING non-eligible symbol-days to combined_signal=0 (main._mask_crypto_
    # signals_by_year), which decide_entry rejects via NO_SIGNAL -- a gate that
    # precedes SYMBOL_NOT_TRADABLE. So symbol_tradable=True is an accurate
    # representation: a masked/non-tradable day (combined=0) never enters, and
    # every decide_entry call the backtester makes carries symbol_tradable=True.
    real = backtester_module.decide_entry
    calls = []

    def spy(inp):
        calls.append(inp)
        return real(inp)

    monkeypatch.setattr(backtester_module, "decide_entry", spy)
    # A masked/non-tradable symbol-day is represented by combined_signal=0.
    _, trades = _run({"A": (_df(), _persistent(0, 6, trend=1), "Crypto")})
    assert trades == []                                   # masked day never enters
    assert calls and all(c.symbol_tradable is True for c in calls)
