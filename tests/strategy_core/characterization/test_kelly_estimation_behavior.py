"""SR-101B: characterization of the current mathematical behavior of
``src.risk.estimate_kelly_from_history`` (and the ``kelly_criterion`` /
``quarter_kelly`` helpers it composes).

Tests-only. Freezes CURRENT behavior; does not judge or change it, and does not
implement any TradeHistorySnapshot contract.

Basis-agnosticism (SR-101A finding): estimate_kelly_from_history consumes only
a bare ``.pnl`` numeric attribute per record. It has no concept of gross vs net
PnL, no timestamp semantics, and no ordering guarantee beyond "list position".
Whether upstream callers feed it gross or net PnL is an ADAPTER decision (main.py
live vs src/backtester.py) outside this function's scope -- see test 11 below.
These tests characterize the function in isolation with a minimal local stub;
they do not claim to enforce (or even observe) any particular PnL basis.

Expected values in every test are computed independently by hand from the
production formula transcribed in comments, NOT by calling estimate_kelly_from_history
or kelly_criterion/quarter_kelly to generate their own expected answer.

Production formula (src/risk.py), transcribed for reference:

    default_risk = DEFAULT_RISK_PCT_BY_CLASS[asset_type] or DEFAULT_RISK_PCT (0.02 ultimate fallback)
    if len(closed_trades) < KELLY_MIN_TRADES: return default_risk      # gate on RAW length (pre-filter)
    pnls   = [t.pnl for t in closed_trades if t.pnl is not None]       # None dropped HERE, after the gate
    wins   = [p for p in pnls if p > 0]
    losses = [abs(p) for p in pnls if p < 0]                           # zero excluded from both
    if not wins or not losses: return default_risk
    decisive = len(wins) + len(losses)
    wr    = len(wins) / decisive
    avg_w = sum(wins) / len(wins)
    avg_l = sum(losses) / len(losses)
    R     = avg_w / avg_l
    k     = max(0.0, wr - (1.0 - wr) / R)          # kelly_criterion
    q     = k * KELLY_FRACTION                      # quarter_kelly
    return min(q, MAX_RISK_PCT)
"""
from __future__ import annotations

import pytest

import config
from src.risk import estimate_kelly_from_history


class _TradeStub:
    """Minimal local stand-in exposing only .pnl, matching what
    estimate_kelly_from_history actually reads (main.py's ClosedTradeStub and
    src/backtester.py's Trade both satisfy this same narrow interface)."""
    __slots__ = ("pnl",)

    def __init__(self, pnl):
        self.pnl = pnl


def _crypto_default() -> float:
    # Referenced from config, never hardcoded, so this test tracks config if it changes.
    return config.DEFAULT_RISK_PCT_BY_CLASS["Crypto"]


# ── 1. Empty history -> fallback ────────────────────────────────────────────
def test_empty_history_uses_crypto_default_fallback():
    result = estimate_kelly_from_history([], window=0, asset_type="Crypto")
    assert result == _crypto_default()


# ── 2. Insufficient history (below KELLY_MIN_TRADES) -> fallback ───────────
def test_insufficient_history_uses_fallback_despite_wins_and_losses():
    assert config.KELLY_MIN_TRADES > 5, "fixture assumes KELLY_MIN_TRADES > 5"
    trades = [
        _TradeStub(10.0), _TradeStub(-5.0), _TradeStub(10.0),
        _TradeStub(-5.0), _TradeStub(10.0),
    ]  # 5 records, both wins and losses present, but below KELLY_MIN_TRADES
    result = estimate_kelly_from_history(trades, window=0, asset_type="Crypto")
    assert result == _crypto_default()


# ── 3. Exactly KELLY_MIN_TRADES records -> Kelly calculation activates ─────
def test_exact_minimum_trade_count_activates_kelly_formula():
    assert config.KELLY_MIN_TRADES == 10, (
        "fixture below is hand-built for KELLY_MIN_TRADES == 10; "
        "update the fixture if the config value changes")
    trades = (
        [_TradeStub(5.0)] * 6      # 6 wins of +5.0
        + [_TradeStub(-5.0)] * 4   # 4 losses of -5.0
    )
    assert len(trades) == config.KELLY_MIN_TRADES

    # Hand-computed independently of production code:
    # wins=6, losses=4, decisive=10, wr=0.6, avg_w=5.0, avg_l=5.0, R=1.0
    # kelly_criterion = wr - (1-wr)/R = 0.6 - 0.4/1.0 = 0.2
    # quarter_kelly    = 0.2 * KELLY_FRACTION
    expected_kelly_criterion = 0.6 - 0.4 / 1.0
    expected_quarter = expected_kelly_criterion * config.KELLY_FRACTION
    assert expected_quarter < config.MAX_RISK_PCT, (
        "fixture must stay below the cap so this test isolates the quarter-Kelly "
        "formula from the MAX_RISK_PCT cap (see test 9 for the cap itself)")

    result = estimate_kelly_from_history(trades, window=0, asset_type="Crypto")
    assert result == pytest.approx(expected_quarter)
    assert result == pytest.approx(0.05)
    assert result != _crypto_default()          # confirms the fallback branch did NOT fire


# ── 4. Zero-PnL: excluded from win/loss denominator, but still counts toward
#      the initial KELLY_MIN_TRADES length gate ─────────────────────────────
def test_zero_pnl_excluded_from_denominator_but_counts_toward_length_gate():
    assert config.KELLY_MIN_TRADES == 10
    non_zero = (
        [_TradeStub(4.0)] * 5     # 5 wins of +4.0
        + [_TradeStub(-4.0)] * 3  # 3 losses of -4.0
    )
    zero_pnl = [_TradeStub(0.0)] * 2   # 2 zero-PnL closes (e.g. FLIP-at-entry-price)
    trades = non_zero + zero_pnl
    assert len(trades) == 10                     # exactly meets the gate...
    assert len(non_zero) == 8                     # ...but only 8 records are non-zero

    # If the 2 zero-PnL records did NOT count toward the raw length gate, len()
    # would be 8 < KELLY_MIN_TRADES(10) and the fallback would fire instead.
    # Calling with only the 8 non-zero records characterizes that counterfactual:
    below_gate_result = estimate_kelly_from_history(non_zero, window=0, asset_type="Crypto")
    assert below_gate_result == _crypto_default(), (
        "8 records alone must fall below the gate -- this isolates what the "
        "2 zero-PnL records contribute when included")

    # With the 2 zero-PnL records included, len()==10 passes the gate (proving
    # zero-PnL records DO count toward the initial len(closed_trades) check),
    # but they are excluded from wins/losses/decisive once past the gate:
    # wins=5, losses=3, decisive=8 (NOT 10), wr=5/8=0.625, avg_w=4.0, avg_l=4.0, R=1.0
    # kelly_criterion = 0.625 - 0.375/1.0 = 0.25
    # quarter_kelly    = 0.25 * KELLY_FRACTION
    expected_kelly_criterion = 0.625 - 0.375 / 1.0
    expected_quarter = expected_kelly_criterion * config.KELLY_FRACTION
    assert expected_quarter < config.MAX_RISK_PCT

    result = estimate_kelly_from_history(trades, window=0, asset_type="Crypto")
    assert result == pytest.approx(expected_quarter)
    assert result == pytest.approx(0.0625)
    assert result != _crypto_default()            # gate passed: the 10-count included the zeros


# ── 5. All eligible PnL positive (no losses) -> fallback ───────────────────
def test_all_wins_no_losses_uses_fallback():
    trades = [_TradeStub(10.0)] * config.KELLY_MIN_TRADES
    result = estimate_kelly_from_history(trades, window=0, asset_type="Crypto")
    assert result == _crypto_default()


# ── 6. All eligible PnL negative (no wins) -> fallback ──────────────────────
def test_all_losses_no_wins_uses_fallback():
    trades = [_TradeStub(-10.0)] * config.KELLY_MIN_TRADES
    result = estimate_kelly_from_history(trades, window=0, asset_type="Crypto")
    assert result == _crypto_default()


# ── 7. window=0 disables trimming -> ALL provided records are used ─────────
# Shared 12-record fixture for tests 7 & 8: the first 2 (list-earliest) records
# are wins that are NOT part of the "latest 10" -- so trimming vs not-trimming
# produces two distinguishably different results.
def _window_fixture():
    earliest_extra_wins = [_TradeStub(3.0), _TradeStub(3.0)]     # list positions 0-1
    latest_ten = [_TradeStub(3.0)] * 5 + [_TradeStub(-3.0)] * 5  # list positions 2-11
    return earliest_extra_wins + latest_ten


def test_window_zero_uses_full_history_not_just_latest_records():
    trades = _window_fixture()
    assert len(trades) == 12

    # Full 12: wins=7 (2 extra + 5), losses=5, decisive=12
    # wr=7/12, avg_w=3.0, avg_l=3.0, R=1.0
    # kelly_criterion = 7/12 - (5/12)/1.0 = 2/12 = 1/6
    # quarter_kelly    = (1/6) * KELLY_FRACTION
    wr = 7 / 12
    expected_kelly_criterion = wr - (1 - wr) / 1.0
    expected_quarter = expected_kelly_criterion * config.KELLY_FRACTION
    assert expected_quarter < config.MAX_RISK_PCT

    # Counterfactual: if window=0 had (incorrectly) trimmed to the last 10,
    # the 2 earliest wins would be dropped -> 5 wins/5 losses -> wr=0.5 -> kelly=0.
    counterfactual_last_ten_only = 0.0

    result = estimate_kelly_from_history(trades, window=0, asset_type="Crypto")
    assert result == pytest.approx(expected_quarter)
    assert result != pytest.approx(counterfactual_last_ten_only)


# ── 8. window>0 selects the latest N records by LIST POSITION (insertion
#      order), not by any timestamp -- the stub carries no timestamp at all ─
def test_positive_window_selects_latest_n_by_list_position():
    trades = _window_fixture()          # same 12-record fixture as test 7
    assert len(trades) == 12

    # window=10 -> closed_trades[-10:] drops the 2 earliest (list-position 0-1)
    # wins, leaving exactly the "latest_ten" block: 5 wins/5 losses, wr=0.5.
    # kelly_criterion = 0.5 - 0.5/1.0 = 0.0 -> quarter_kelly = 0.0
    result = estimate_kelly_from_history(trades, window=10, asset_type="Crypto")
    assert result == pytest.approx(0.0)

    # Confirms this differs from the un-windowed (window=0) result on the SAME
    # 12-record list -- proving window>0 actually changes which records count,
    # and that the selection is a plain Python list slice (closed_trades[-window:]),
    # not a sort by any exit/entry timestamp (the stub has none to sort by).
    unwindowed = estimate_kelly_from_history(trades, window=0, asset_type="Crypto")
    assert unwindowed != pytest.approx(result)


# ── 9. MAX_RISK_PCT caps a very strong positive-edge history ───────────────
def test_strong_edge_history_is_capped_at_max_risk_pct():
    assert config.KELLY_MIN_TRADES == 10
    trades = [_TradeStub(100.0)] * 9 + [_TradeStub(-1.0)] * 1   # 9 wins, 1 loss
    assert len(trades) == 10

    # wins=9, losses=1, decisive=10, wr=0.9, avg_w=100.0, avg_l=1.0, R=100.0
    # kelly_criterion = 0.9 - 0.1/100.0 = 0.899
    # quarter_kelly    = 0.899 * KELLY_FRACTION  (well above MAX_RISK_PCT)
    expected_kelly_criterion = 0.9 - 0.1 / 100.0
    expected_uncapped_quarter = expected_kelly_criterion * config.KELLY_FRACTION
    assert expected_uncapped_quarter > config.MAX_RISK_PCT, (
        "fixture must exceed the cap for this test to actually exercise it")

    result = estimate_kelly_from_history(trades, window=0, asset_type="Crypto")
    assert result == pytest.approx(config.MAX_RISK_PCT)
    assert result != pytest.approx(expected_uncapped_quarter)


# ── 10. None-PnL: excluded from win/loss arithmetic, but (like zero-PnL)
#       still counts toward the initial KELLY_MIN_TRADES length gate ───────
def test_none_pnl_excluded_from_arithmetic_but_counts_toward_length_gate():
    assert config.KELLY_MIN_TRADES == 10
    valid = (
        [_TradeStub(2.0)] * 5      # 5 wins of +2.0
        + [_TradeStub(-2.0)] * 3   # 3 losses of -2.0
    )
    none_pnl = [_TradeStub(None)] * 2   # 2 records with unresolved/unknown PnL
    trades = valid + none_pnl
    assert len(trades) == 10
    assert len(valid) == 8

    # 8 valid records alone fall below the gate (mirrors the zero-PnL counterfactual):
    below_gate_result = estimate_kelly_from_history(valid, window=0, asset_type="Crypto")
    assert below_gate_result == _crypto_default()

    # With the 2 None records included, len()==10 passes the gate (None DOES
    # count toward the raw length check), but pnls = [t.pnl for t if t.pnl is
    # not None] drops them before wins/losses/decisive are computed:
    # wins=5, losses=3, decisive=8, wr=5/8=0.625, avg_w=2.0, avg_l=2.0, R=1.0
    # kelly_criterion = 0.625 - 0.375/1.0 = 0.25
    # quarter_kelly    = 0.25 * KELLY_FRACTION
    expected_kelly_criterion = 0.625 - 0.375 / 1.0
    expected_quarter = expected_kelly_criterion * config.KELLY_FRACTION
    assert expected_quarter < config.MAX_RISK_PCT

    result = estimate_kelly_from_history(trades, window=0, asset_type="Crypto")
    assert result == pytest.approx(expected_quarter)
    assert result == pytest.approx(0.0625)
    assert result != _crypto_default()


# ── 11. Basis agnosticism: the function sees only numeric .pnl ─────────────
def test_identical_pnl_values_produce_identical_results_regardless_of_label():
    # "gross-source" and "net-source" are TEST-ONLY labels for two histories
    # with numerically identical .pnl values. estimate_kelly_from_history has
    # no field or parameter for PnL basis -- it cannot distinguish gross from
    # net, so equal .pnl sequences MUST produce equal results. Enforcing which
    # basis (gross vs net) actually reaches this function is an ADAPTER-level
    # concern for the future TradeHistorySnapshot contract (SR-101A/C), not a
    # property of this function, so this test asserts equality only.
    pnls = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, -5.0, -5.0, -5.0, -5.0]  # 6 win / 4 loss
    gross_source = [_TradeStub(p) for p in pnls]
    net_source = [_TradeStub(p) for p in pnls]

    gross_result = estimate_kelly_from_history(gross_source, window=0, asset_type="Crypto")
    net_result = estimate_kelly_from_history(net_source, window=0, asset_type="Crypto")
    assert gross_result == net_result


# ── 12. Determinism: same inputs -> same output across repeated calls ──────
def test_repeated_calls_with_same_history_are_deterministic():
    trades = (
        [_TradeStub(5.0)] * 6
        + [_TradeStub(-5.0)] * 4
    )
    first = estimate_kelly_from_history(trades, window=0, asset_type="Crypto")
    second = estimate_kelly_from_history(trades, window=0, asset_type="Crypto")
    assert first == second
