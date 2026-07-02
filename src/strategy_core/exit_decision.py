"""SR-102B: authoritative shared exit-decision core.

Pure, deterministic same-process exit arbitration extracted verbatim from
``main.cmd_live``'s live position-management path. It decides whether an
already-open position should HOLD (stay open) or CLOSE, and -- on CLOSE -- the
exact production close reason ('SL' / 'TP' / an early-exit label / 'FLIP').

It performs NO signal generation, indicator computation, trailing-stop math,
PnL calculation, order sizing, filesystem/network/environment/clock access,
logging, or execution. Callers compute the trailing-stop mutation, the
early-exit label, the min-hold gate and the live price BEFORE calling this core
and pass in the resulting scalars; the core reads nothing else.

Behaviour mirror (main.py live path, pre-extraction inline logic):

    hit_sl = (dir == 1 and price <= sl) or (dir == -1 and price >= sl)
    hit_tp = (dir == 1 and price >= tp) or (dir == -1 and price <= tp)
    flip   = min_hold_ok and latest_sig != 0 and latest_sig != dir
    if hit_sl or hit_tp or early_exit or flip:          # CLOSE
        reason = 'SL' if hit_sl else ('TP' if hit_tp else (early_exit or 'FLIP'))

Reason precedence (first matching wins): SL > TP > early-exit label > FLIP.
The comparisons use ``<=`` on the stop-loss side and ``>=`` on the take-profit
side, per direction, exactly as the original code did -- including the raw
behaviour for zero/inactive stop values (no missing-value guard exists in the
original arbitration; the caller ensures live SL/TP are populated upstream).

The close reason strings are production ledger / re-entry values and MUST stay
byte-identical: 'SL', 'TP', 'FLIP', or whatever early-exit label the caller
computed ('BB-TGT', 'BB-MID', 'BB-RSI', 'SOFT', 'MAXHOLD', ...).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

# Close-reason string literals for the two conditions this core names itself.
# Early-exit labels are supplied by the caller and passed through unchanged.
CLOSE_REASON_STOP_LOSS = "SL"
CLOSE_REASON_TAKE_PROFIT = "TP"
CLOSE_REASON_FLIP = "FLIP"


class ExitAction(str, Enum):
    """What the caller should do with an already-open position this cycle."""

    HOLD = "HOLD"
    CLOSE = "CLOSE"


@dataclass(frozen=True)
class ExitDecisionInput:
    """Immutable, fully-resolved same-process exit inputs for one open position.

    Every field is a plain scalar the caller has already computed:

      * ``direction``       held position direction (+1 long / -1 short).
      * ``current_price``   the live price used for exit checks (main's ``price``).
      * ``stop_loss``       the current (possibly trailed) stop (main's pos['sl']).
      * ``take_profit``     the current take-profit (main's pos['tp']).
      * ``combined_signal`` the latest combined signal (main's ``latest_sig``),
                            used only for the FLIP test.
      * ``min_hold_ok``     whether the minimum hold has elapsed (main's
                            ``min_hold_ok``); FLIP is inert until this is True.
      * ``early_exit``      the already-computed early-exit label, or None. Its
                            truthiness drives the early-exit close (matching the
                            original ``or early_exit or`` test) and its exact
                            string becomes the close reason.
    """

    symbol: str
    direction: int
    current_price: float
    stop_loss: float
    take_profit: float
    combined_signal: int
    min_hold_ok: bool
    early_exit: Optional[str]


@dataclass(frozen=True)
class ExitDecisionResult:
    """Immutable exit decision.

    On HOLD ``close_reason`` is None. On CLOSE it is the exact production reason
    string. The boolean flags report which condition(s) were satisfied (an
    observability aid; the caller acts only on ``action`` + ``close_reason``).
    """

    action: ExitAction
    close_reason: Optional[str]
    hit_stop_loss: bool
    hit_take_profit: bool
    is_flip: bool
    is_early_exit: bool


def decide_exit(inp: ExitDecisionInput) -> ExitDecisionResult:
    """Return the authoritative HOLD/CLOSE decision for one open position.

    Behaviour-identical to main.cmd_live's inline arbitration:

      * CLOSE when ``hit_stop_loss or hit_take_profit or early_exit or is_flip``.
      * Reason precedence: SL, then TP, then the early-exit label, then FLIP.
    """
    direction = int(inp.direction)
    price = inp.current_price

    hit_stop_loss = (
        (direction == 1 and price <= inp.stop_loss)
        or (direction == -1 and price >= inp.stop_loss)
    )
    hit_take_profit = (
        (direction == 1 and price >= inp.take_profit)
        or (direction == -1 and price <= inp.take_profit)
    )
    is_early_exit = bool(inp.early_exit)
    is_flip = (
        inp.min_hold_ok
        and inp.combined_signal != 0
        and inp.combined_signal != direction
    )

    if hit_stop_loss or hit_take_profit or is_early_exit or is_flip:
        # Exact original precedence:
        #   reason = 'SL' if hit_sl else ('TP' if hit_tp else (early_exit or 'FLIP'))
        if hit_stop_loss:
            reason = CLOSE_REASON_STOP_LOSS
        elif hit_take_profit:
            reason = CLOSE_REASON_TAKE_PROFIT
        else:
            reason = inp.early_exit or CLOSE_REASON_FLIP
        return ExitDecisionResult(
            ExitAction.CLOSE, reason,
            hit_stop_loss, hit_take_profit, is_flip, is_early_exit)

    return ExitDecisionResult(
        ExitAction.HOLD, None,
        hit_stop_loss, hit_take_profit, is_flip, is_early_exit)
