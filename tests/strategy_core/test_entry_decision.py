"""SR-102A: unit tests for the pure shared entry-decision core.

These pin the extracted per-symbol entry arbitration behaviour (HOLD vs
ENTER LONG/SHORT), the strategy-family selection, gate precedence, determinism
and immutability. They must not duplicate Kelly/stop/sizing tests -- the core
does none of that.
"""
from __future__ import annotations

import dataclasses

import pytest

from src.strategy_core import (
    EntryAction,
    EntryDecisionInput,
    EntryDecisionResult,
    EntryReasonCode,
    decide_entry,
    dominant_strategy_family,
)
import src.strategy_core.entry_decision as entry_decision


def _inp(**over):
    """A baseline ELIGIBLE long input; override single fields per test."""
    base = dict(
        symbol="BYBIT:BTCUSDT.P",
        asset_class="Crypto",
        combined_signal=1,
        score=5,
        trend_signal=1,
        volume_profile_signal=0,
        bollinger_signal=0,
        minimum_score=3,
        symbol_tradable=True,
        has_open_position=False,
        reentry_blocked=False,
        symbol_winrate_ok=True,
        position_cap_reached=False,
    )
    base.update(over)
    return EntryDecisionInput(**base)


# ── 1. zero combined signal → HOLD / NO_SIGNAL ──────────────────────────────
def test_zero_signal_holds_no_signal():
    res = decide_entry(_inp(combined_signal=0))
    assert res.action is EntryAction.HOLD
    assert res.direction == 0
    assert res.reason_code is EntryReasonCode.NO_SIGNAL


# ── 2. long below threshold → HOLD ──────────────────────────────────────────
def test_long_below_threshold_holds():
    res = decide_entry(_inp(combined_signal=1, score=2, minimum_score=3))
    assert res.action is EntryAction.HOLD
    assert res.reason_code is EntryReasonCode.SCORE_BELOW_THRESHOLD


# ── 3. short below threshold → HOLD ─────────────────────────────────────────
def test_short_below_threshold_holds():
    res = decide_entry(_inp(combined_signal=-1, trend_signal=-1,
                            score=2, minimum_score=3))
    assert res.action is EntryAction.HOLD
    assert res.reason_code is EntryReasonCode.SCORE_BELOW_THRESHOLD


# ── 4. valid long → ENTER +1 ────────────────────────────────────────────────
def test_valid_long_enters_direction_plus_one():
    res = decide_entry(_inp(combined_signal=1, trend_signal=1))
    assert res.action is EntryAction.ENTER
    assert res.direction == 1
    assert res.reason_code is EntryReasonCode.ELIGIBLE_LONG


# ── 5. valid short → ENTER -1 ───────────────────────────────────────────────
def test_valid_short_enters_direction_minus_one():
    res = decide_entry(_inp(combined_signal=-1, trend_signal=-1))
    assert res.action is EntryAction.ENTER
    assert res.direction == -1
    assert res.reason_code is EntryReasonCode.ELIGIBLE_SHORT


# ── 6. existing position suppresses entry ───────────────────────────────────
def test_existing_position_suppresses_entry():
    res = decide_entry(_inp(has_open_position=True))
    assert res.action is EntryAction.HOLD
    assert res.reason_code is EntryReasonCode.EXISTING_POSITION


# ── 7. re-entry block suppresses entry ──────────────────────────────────────
def test_reentry_block_suppresses_entry():
    res = decide_entry(_inp(reentry_blocked=True))
    assert res.action is EntryAction.HOLD
    assert res.reason_code is EntryReasonCode.REENTRY_BLOCKED


# ── 8. position-cap gate suppresses entry ───────────────────────────────────
def test_position_cap_suppresses_entry():
    res = decide_entry(_inp(position_cap_reached=True))
    assert res.action is EntryAction.HOLD
    assert res.reason_code is EntryReasonCode.POSITION_CAP_REACHED


# ── 9. exact threshold accepted (>=) ────────────────────────────────────────
def test_exact_threshold_is_accepted():
    res = decide_entry(_inp(score=3, minimum_score=3))
    assert res.action is EntryAction.ENTER
    assert res.reason_code is EntryReasonCode.ELIGIBLE_LONG


# ── 10. above threshold accepted ────────────────────────────────────────────
def test_above_threshold_is_accepted():
    res = decide_entry(_inp(score=9, minimum_score=3))
    assert res.action is EntryAction.ENTER


# ── 11. dominant trend family ───────────────────────────────────────────────
def test_dominant_trend_family_selected():
    res = decide_entry(_inp(combined_signal=1, trend_signal=1,
                            volume_profile_signal=0, bollinger_signal=0))
    assert res.strategy_family == "trend"


# ── 12. dominant volume-profile family ──────────────────────────────────────
def test_dominant_volume_profile_family_selected():
    res = decide_entry(_inp(combined_signal=1, trend_signal=0,
                            volume_profile_signal=1, bollinger_signal=0))
    assert res.strategy_family == "vp"


# ── 13. dominant bollinger family ───────────────────────────────────────────
def test_dominant_bollinger_family_selected():
    res = decide_entry(_inp(combined_signal=1, trend_signal=0,
                            volume_profile_signal=0, bollinger_signal=1))
    assert res.strategy_family == "bb"


# ── 14. tie behaviour → 'combined' (matches _dominant_live_strategy) ─────────
def test_tie_families_fall_back_to_combined():
    # two families match the direction -> 'combined'
    two = decide_entry(_inp(combined_signal=1, trend_signal=1,
                            volume_profile_signal=1, bollinger_signal=0))
    assert two.strategy_family == "combined"
    # zero families match the direction -> 'combined'
    zero = decide_entry(_inp(combined_signal=1, trend_signal=0,
                             volume_profile_signal=0, bollinger_signal=0))
    assert zero.strategy_family == "combined"
    # all three match -> 'combined'
    allm = decide_entry(_inp(combined_signal=1, trend_signal=1,
                             volume_profile_signal=1, bollinger_signal=1))
    assert allm.strategy_family == "combined"


# ── 15. long/short family selection is symmetric ────────────────────────────
def test_family_selection_is_symmetric_long_short():
    long_vp = decide_entry(_inp(combined_signal=1, trend_signal=0,
                                volume_profile_signal=1, bollinger_signal=0))
    short_vp = decide_entry(_inp(combined_signal=-1, trend_signal=0,
                                 volume_profile_signal=-1, bollinger_signal=0))
    assert long_vp.strategy_family == short_vp.strategy_family == "vp"
    # a family whose signal does NOT match the entry direction is ignored,
    # symmetrically for long and short
    long_mismatch = decide_entry(_inp(combined_signal=1, trend_signal=-1,
                                      volume_profile_signal=1, bollinger_signal=0))
    short_mismatch = decide_entry(_inp(combined_signal=-1, trend_signal=1,
                                       volume_profile_signal=-1, bollinger_signal=0))
    assert long_mismatch.strategy_family == short_mismatch.strategy_family == "vp"


# ── 16. determinism: same input → identical output ──────────────────────────
def test_same_input_produces_identical_output():
    inp = _inp(combined_signal=-1, trend_signal=-1, score=7)
    first = decide_entry(inp)
    second = decide_entry(inp)
    assert first == second
    # a distinct but equal input yields an equal result too
    assert decide_entry(_inp(combined_signal=-1, trend_signal=-1, score=7)) == first


# ── 17. results (and inputs) are immutable ──────────────────────────────────
def test_result_is_immutable():
    res = decide_entry(_inp())
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.action = EntryAction.HOLD          # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.reason_code = EntryReasonCode.NO_SIGNAL   # type: ignore[misc]
    inp = _inp()
    with pytest.raises(dataclasses.FrozenInstanceError):
        inp.score = 999                        # type: ignore[misc]


# ── 18. module exposes no I/O / execution surface ───────────────────────────
def test_module_exposes_no_side_effecting_api():
    forbidden = {
        "os", "sys", "socket", "subprocess", "requests", "open", "time",
        "datetime", "pathlib", "Path", "config", "executor", "BybitExecutor",
        "record_bybit_order", "get_connection", "estimate_kelly_from_history",
        "position_size", "calculate_stops",
    }
    present = forbidden & set(vars(entry_decision))
    assert present == set(), f"entry_decision leaks I/O/execution names: {present}"
    # the public surface is data + the pure decision functions only
    assert callable(decide_entry)
    assert callable(dominant_strategy_family)


# ── extra: HOLD precedence is stable (first failing gate wins) ───────────────
def test_hold_precedence_reports_first_failing_gate():
    # signal precedes every other gate
    res = decide_entry(_inp(combined_signal=0, symbol_tradable=False,
                            has_open_position=True, score=0, minimum_score=3,
                            reentry_blocked=True, symbol_winrate_ok=False,
                            position_cap_reached=True))
    assert res.reason_code is EntryReasonCode.NO_SIGNAL
    # with a signal, non-tradable precedes position/score/cap
    res2 = decide_entry(_inp(symbol_tradable=False, has_open_position=True,
                             position_cap_reached=True))
    assert res2.reason_code is EntryReasonCode.SYMBOL_NOT_TRADABLE
    # winrate gate precedes the cap gate
    res3 = decide_entry(_inp(symbol_winrate_ok=False, position_cap_reached=True))
    assert res3.reason_code is EntryReasonCode.SYMBOL_WINRATE_BLOCKED


# ── extra: dominant_strategy_family without a direction → 'combined' ─────────
def test_family_helper_without_direction_is_combined():
    assert dominant_strategy_family(0, 0, 0, 0) == "combined"
    assert dominant_strategy_family(0, 1, 1, 1) == "combined"
