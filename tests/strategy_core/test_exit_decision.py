"""SR-102B: unit tests for the pure shared exit-decision core.

These pin the extracted same-process exit arbitration (HOLD vs CLOSE), the exact
close-reason precedence (SL > TP > early-exit label > FLIP), the boundary
semantics (``<=`` stop side / ``>=`` take-profit side), FLIP conditions,
long/short symmetry, determinism and immutability. They must not duplicate
PnL / Kelly / sizing / execution tests -- the core does none of that.
"""
from __future__ import annotations

import dataclasses

import pytest

from src.strategy_core import (
    ExitAction,
    ExitDecisionInput,
    ExitDecisionResult,
    decide_exit,
)
import src.strategy_core.exit_decision as exit_decision


def _inp(**over):
    """A baseline HOLD long input (price strictly inside SL/TP, no signal, no
    early exit); override single fields per test."""
    base = dict(
        symbol="BYBIT:BTCUSDT.P",
        direction=1,
        current_price=100.0,
        stop_loss=90.0,
        take_profit=130.0,
        combined_signal=0,
        min_hold_ok=True,
        early_exit=None,
    )
    base.update(over)
    return ExitDecisionInput(**base)


# ── 1. long, no exit condition → HOLD ───────────────────────────────────────
def test_long_no_condition_holds():
    res = decide_exit(_inp(direction=1, current_price=100.0,
                           stop_loss=90.0, take_profit=130.0))
    assert res.action is ExitAction.HOLD
    assert res.close_reason is None
    assert not (res.hit_stop_loss or res.hit_take_profit
                or res.is_flip or res.is_early_exit)


# ── 2. short, no exit condition → HOLD ──────────────────────────────────────
def test_short_no_condition_holds():
    res = decide_exit(_inp(direction=-1, current_price=100.0,
                           stop_loss=110.0, take_profit=70.0))
    assert res.action is ExitAction.HOLD
    assert res.close_reason is None


# ── 3. long stop loss → CLOSE 'SL' ──────────────────────────────────────────
def test_long_stop_loss_closes_sl():
    res = decide_exit(_inp(direction=1, current_price=90.0,
                           stop_loss=90.0, take_profit=130.0))
    assert res.action is ExitAction.CLOSE
    assert res.close_reason == "SL"
    assert res.hit_stop_loss is True


# ── 4. long take profit → CLOSE 'TP' ────────────────────────────────────────
def test_long_take_profit_closes_tp():
    res = decide_exit(_inp(direction=1, current_price=104.0,
                           stop_loss=90.0, take_profit=104.0))
    assert res.action is ExitAction.CLOSE
    assert res.close_reason == "TP"
    assert res.hit_take_profit is True


# ── 5. short stop loss → CLOSE 'SL' ─────────────────────────────────────────
def test_short_stop_loss_closes_sl():
    res = decide_exit(_inp(direction=-1, current_price=110.0,
                           stop_loss=110.0, take_profit=70.0))
    assert res.action is ExitAction.CLOSE
    assert res.close_reason == "SL"
    assert res.hit_stop_loss is True


# ── 6. short take profit → CLOSE 'TP' ───────────────────────────────────────
def test_short_take_profit_closes_tp():
    res = decide_exit(_inp(direction=-1, current_price=96.0,
                           stop_loss=110.0, take_profit=96.0))
    assert res.action is ExitAction.CLOSE
    assert res.close_reason == "TP"
    assert res.hit_take_profit is True


# ── 7. long FLIP → CLOSE 'FLIP' ─────────────────────────────────────────────
def test_long_flip_closes_flip():
    # held long (dir +1), opposite signal (-1), price strictly inside SL/TP
    res = decide_exit(_inp(direction=1, current_price=100.0,
                           stop_loss=90.0, take_profit=130.0,
                           combined_signal=-1))
    assert res.action is ExitAction.CLOSE
    assert res.close_reason == "FLIP"
    assert res.is_flip is True
    assert res.hit_stop_loss is False and res.hit_take_profit is False


# ── 8. short FLIP → CLOSE 'FLIP' ────────────────────────────────────────────
def test_short_flip_closes_flip():
    res = decide_exit(_inp(direction=-1, current_price=100.0,
                           stop_loss=110.0, take_profit=70.0,
                           combined_signal=1))
    assert res.action is ExitAction.CLOSE
    assert res.close_reason == "FLIP"
    assert res.is_flip is True


# ── 9. early exit returns the current production label ──────────────────────
@pytest.mark.parametrize("label", ["BB-TGT", "BB-MID", "BB-RSI", "SOFT", "MAXHOLD"])
def test_early_exit_returns_production_label(label):
    # price strictly inside SL/TP and no flip -> the early-exit label is the reason
    res = decide_exit(_inp(direction=1, current_price=100.0,
                           stop_loss=90.0, take_profit=130.0,
                           combined_signal=0, early_exit=label))
    assert res.action is ExitAction.CLOSE
    assert res.close_reason == label
    assert res.is_early_exit is True


# ── 10. zero combined signal does not create a FLIP ─────────────────────────
def test_zero_signal_is_not_flip():
    res = decide_exit(_inp(direction=1, current_price=100.0,
                           stop_loss=90.0, take_profit=130.0,
                           combined_signal=0))
    assert res.is_flip is False
    assert res.action is ExitAction.HOLD


# ── 11. same-direction signal does not create a FLIP ────────────────────────
def test_same_direction_signal_is_not_flip():
    long_same = decide_exit(_inp(direction=1, current_price=100.0,
                                 stop_loss=90.0, take_profit=130.0,
                                 combined_signal=1))
    short_same = decide_exit(_inp(direction=-1, current_price=100.0,
                                  stop_loss=110.0, take_profit=70.0,
                                  combined_signal=-1))
    assert long_same.is_flip is False and long_same.action is ExitAction.HOLD
    assert short_same.is_flip is False and short_same.action is ExitAction.HOLD


# ── 11b. FLIP is inert until the minimum hold has elapsed ────────────────────
def test_flip_requires_min_hold_ok():
    res = decide_exit(_inp(direction=1, current_price=100.0,
                           stop_loss=90.0, take_profit=130.0,
                           combined_signal=-1, min_hold_ok=False))
    assert res.is_flip is False
    assert res.action is ExitAction.HOLD


# ── 12. exact SL boundary uses <= (long) / >= (short) ───────────────────────
def test_stop_loss_boundary_semantics():
    # long: price == sl -> hit (price <= sl); a hair above -> no hit
    assert decide_exit(_inp(direction=1, current_price=90.0,
                            stop_loss=90.0)).hit_stop_loss is True
    assert decide_exit(_inp(direction=1, current_price=90.01,
                            stop_loss=90.0)).hit_stop_loss is False
    # short: price == sl -> hit (price >= sl); a hair below -> no hit
    assert decide_exit(_inp(direction=-1, current_price=110.0,
                            stop_loss=110.0, take_profit=70.0)).hit_stop_loss is True
    assert decide_exit(_inp(direction=-1, current_price=109.99,
                            stop_loss=110.0, take_profit=70.0)).hit_stop_loss is False


# ── 13. exact TP boundary uses >= (long) / <= (short) ───────────────────────
def test_take_profit_boundary_semantics():
    # long: price == tp -> hit (price >= tp); a hair below -> no hit
    assert decide_exit(_inp(direction=1, current_price=130.0,
                            stop_loss=90.0, take_profit=130.0)).hit_take_profit is True
    assert decide_exit(_inp(direction=1, current_price=129.99,
                            stop_loss=90.0, take_profit=130.0)).hit_take_profit is False
    # short: price == tp -> hit (price <= tp); a hair above -> no hit
    assert decide_exit(_inp(direction=-1, current_price=70.0,
                            stop_loss=110.0, take_profit=70.0)).hit_take_profit is True
    assert decide_exit(_inp(direction=-1, current_price=70.01,
                            stop_loss=110.0, take_profit=70.0)).hit_take_profit is False


# ── 14. missing/inactive (0.0) stop values -> raw comparison, no guard ───────
def test_missing_stop_values_match_raw_comparison():
    # The original arbitration has NO missing-value guard; it does the raw
    # comparison. With stop_loss=0.0 and take_profit=0.0 at a positive price:
    #   long : price <= 0 -> no SL ; price >= 0 -> TP hit
    #   short: price >= 0 -> SL hit (SL precedes TP in reason)
    long_zero = decide_exit(_inp(direction=1, current_price=100.0,
                                 stop_loss=0.0, take_profit=0.0, combined_signal=0))
    assert long_zero.hit_stop_loss is False
    assert long_zero.hit_take_profit is True
    assert long_zero.action is ExitAction.CLOSE
    assert long_zero.close_reason == "TP"

    short_zero = decide_exit(_inp(direction=-1, current_price=100.0,
                                  stop_loss=0.0, take_profit=0.0, combined_signal=0))
    assert short_zero.hit_stop_loss is True
    assert short_zero.action is ExitAction.CLOSE
    assert short_zero.close_reason == "SL"


# ── 15. multiple simultaneous conditions -> production precedence ───────────
def test_precedence_when_multiple_conditions_true():
    # SL beats everything: construct sl>=price>=tp so both hit, plus early+flip.
    all_true = decide_exit(_inp(direction=1, current_price=100.0,
                                stop_loss=110.0, take_profit=90.0,
                                combined_signal=-1, early_exit="SOFT"))
    assert all_true.hit_stop_loss is True and all_true.hit_take_profit is True
    assert all_true.is_early_exit is True and all_true.is_flip is True
    assert all_true.close_reason == "SL"

    # TP beats early-exit and flip (no SL): price at TP, inside SL.
    tp_over = decide_exit(_inp(direction=1, current_price=130.0,
                               stop_loss=90.0, take_profit=130.0,
                               combined_signal=-1, early_exit="SOFT"))
    assert tp_over.hit_stop_loss is False and tp_over.hit_take_profit is True
    assert tp_over.close_reason == "TP"

    # early-exit label beats FLIP (no SL/TP): price inside SL/TP.
    early_over = decide_exit(_inp(direction=1, current_price=100.0,
                                  stop_loss=90.0, take_profit=130.0,
                                  combined_signal=-1, early_exit="MAXHOLD"))
    assert early_over.hit_stop_loss is False and early_over.hit_take_profit is False
    assert early_over.is_early_exit is True and early_over.is_flip is True
    assert early_over.close_reason == "MAXHOLD"


# ── 16. long/short symmetry where current code is symmetric ─────────────────
def test_long_short_symmetry():
    long_sl = decide_exit(_inp(direction=1, current_price=90.0,
                               stop_loss=90.0, take_profit=130.0))
    short_sl = decide_exit(_inp(direction=-1, current_price=110.0,
                                stop_loss=110.0, take_profit=70.0))
    assert long_sl.close_reason == short_sl.close_reason == "SL"

    long_tp = decide_exit(_inp(direction=1, current_price=130.0,
                               stop_loss=90.0, take_profit=130.0))
    short_tp = decide_exit(_inp(direction=-1, current_price=70.0,
                                stop_loss=110.0, take_profit=70.0))
    assert long_tp.close_reason == short_tp.close_reason == "TP"

    long_flip = decide_exit(_inp(direction=1, current_price=100.0,
                                 stop_loss=90.0, take_profit=130.0,
                                 combined_signal=-1))
    short_flip = decide_exit(_inp(direction=-1, current_price=100.0,
                                  stop_loss=110.0, take_profit=70.0,
                                  combined_signal=1))
    assert long_flip.close_reason == short_flip.close_reason == "FLIP"


# ── 17. determinism: same input → identical output ──────────────────────────
def test_same_input_produces_identical_output():
    inp = _inp(direction=-1, current_price=96.0, stop_loss=110.0,
               take_profit=96.0, combined_signal=1)
    first = decide_exit(inp)
    second = decide_exit(inp)
    assert first == second
    assert decide_exit(_inp(direction=-1, current_price=96.0, stop_loss=110.0,
                            take_profit=96.0, combined_signal=1)) == first


# ── 18. results (and inputs) are immutable ──────────────────────────────────
def test_result_and_input_are_immutable():
    res = decide_exit(_inp())
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.action = ExitAction.CLOSE          # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.close_reason = "SL"                # type: ignore[misc]
    inp = _inp()
    with pytest.raises(dataclasses.FrozenInstanceError):
        inp.stop_loss = 0.0                    # type: ignore[misc]


# ── 19. module exposes no I/O / execution surface ───────────────────────────
def test_module_exposes_no_side_effecting_api():
    forbidden = {
        "os", "sys", "socket", "subprocess", "requests", "open", "time",
        "datetime", "pathlib", "Path", "config", "executor", "BybitExecutor",
        "record_bybit_order", "get_connection", "estimate_kelly_from_history",
        "position_size", "calculate_stops", "close_position",
    }
    present = forbidden & set(vars(exit_decision))
    assert present == set(), f"exit_decision leaks I/O/execution names: {present}"
    assert callable(decide_exit)
