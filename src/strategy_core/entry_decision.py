"""SR-102A: authoritative shared entry-decision core.

Pure, deterministic per-symbol entry arbitration extracted from
``main.cmd_live``'s live entry path. It decides whether a symbol should HOLD
(reject entry) or ENTER (LONG / SHORT) from a set of ALREADY-COMPUTED gate
values. It performs NO signal generation, indicator computation,
Kelly/quantity/stop math, filesystem/network/environment/clock access, logging,
or execution -- callers compute those and pass in the resulting booleans/ints.

Behaviour mirror (main.py live path):

  * Eligibility -- main.py phase-1 candidate gate::

        sym in crypto_tradable_symbols and sym not in open_pos
        and latest_sig != 0 and score_val >= min_score_class
        and not _reentry_blocked(sym, dt) and _sym_wr_ok(sym)

  * Portfolio cap -- main.py phase-2::

        len(open_pos) >= crypto_max_positions              (global cap)
        or strat_counts[strat] >= MAX_POS_PER_STRATEGY[strat]   (per-family cap)

    Both are supplied to this core as the single ``position_cap_reached`` gate.

  * Strategy-family selection -- main.py ``_dominant_live_strategy``: among
    ('trend', 'vp', 'bb'), the single family whose latest signal equals the
    combined-signal direction wins; ties (zero or more-than-one match) fall back
    to 'combined'.

The ENTER/HOLD result is behaviour-identical to the original inline logic. The
``reason_code`` is a new, stable observability field with the documented
precedence in :func:`decide_entry`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Strategy-family labels -- MUST stay byte-identical to the strings main.py uses
# downstream (MAX_POS_PER_STRATEGY lookup, ledger 'strategy' field, entry reason).
TREND_FAMILY = "trend"
VOLUME_PROFILE_FAMILY = "vp"
BOLLINGER_FAMILY = "bb"
COMBINED_FAMILY = "combined"


class EntryAction(str, Enum):
    """What the caller should do for this symbol on this cycle."""

    HOLD = "HOLD"
    ENTER = "ENTER"


class EntryReasonCode(str, Enum):
    """Stable, explicit reason for the decision.

    Evaluated in the fixed precedence declared in :func:`decide_entry`; only the
    first failing gate is reported. ENTER carries ELIGIBLE_LONG / ELIGIBLE_SHORT.
    """

    NO_SIGNAL = "NO_SIGNAL"
    SYMBOL_NOT_TRADABLE = "SYMBOL_NOT_TRADABLE"
    EXISTING_POSITION = "EXISTING_POSITION"
    SCORE_BELOW_THRESHOLD = "SCORE_BELOW_THRESHOLD"
    REENTRY_BLOCKED = "REENTRY_BLOCKED"
    SYMBOL_WINRATE_BLOCKED = "SYMBOL_WINRATE_BLOCKED"
    POSITION_CAP_REACHED = "POSITION_CAP_REACHED"
    ELIGIBLE_LONG = "ELIGIBLE_LONG"
    ELIGIBLE_SHORT = "ELIGIBLE_SHORT"


@dataclass(frozen=True)
class EntryDecisionInput:
    """Immutable, fully-resolved per-symbol entry gate inputs.

    Every field is a plain scalar the caller has already computed; this core
    reads nothing else. ``combined_signal`` and the family signals are the latest
    per-symbol signal integers (-1 / 0 / +1).
    """

    symbol: str
    asset_class: str
    combined_signal: int
    score: int
    trend_signal: int
    volume_profile_signal: int
    bollinger_signal: int
    minimum_score: int
    symbol_tradable: bool
    has_open_position: bool
    reentry_blocked: bool
    symbol_winrate_ok: bool
    position_cap_reached: bool


@dataclass(frozen=True)
class EntryDecisionResult:
    """Immutable decision. ``direction`` is the entry direction on ENTER
    (+1 long / -1 short) and 0 on HOLD."""

    action: EntryAction
    direction: int
    score: int
    strategy_family: str
    reason_code: EntryReasonCode


def dominant_strategy_family(
    direction: int,
    trend_signal: int,
    volume_profile_signal: int,
    bollinger_signal: int,
) -> str:
    """Select the dominant strategy family for ``direction``.

    Exact port of main.py ``_dominant_live_strategy``: among ('trend', 'vp',
    'bb'), the single family whose latest signal equals ``direction`` wins;
    zero or more-than-one match falls back to 'combined'. Without a directional
    signal (``direction`` not in {+1, -1}) there is no meaningful family, so
    'combined' is returned -- main.py only ever selects a family when the
    combined signal is non-zero, so this never diverges on the ENTER path.
    """
    if direction not in (1, -1):
        return COMBINED_FAMILY
    matched = [
        name
        for name, sig in (
            (TREND_FAMILY, trend_signal),
            (VOLUME_PROFILE_FAMILY, volume_profile_signal),
            (BOLLINGER_FAMILY, bollinger_signal),
        )
        if int(sig) == direction
    ]
    return matched[0] if len(matched) == 1 else COMBINED_FAMILY


def decide_entry(inp: EntryDecisionInput) -> EntryDecisionResult:
    """Return the authoritative HOLD/ENTER decision for one symbol.

    Gate precedence (first failing gate reported); ENTER only when every gate
    passes -- behaviour-identical to main.py's ANDed inline eligibility plus the
    phase-2 position cap:

      1. NO_SIGNAL             combined_signal == 0
      2. SYMBOL_NOT_TRADABLE   not symbol_tradable
      3. EXISTING_POSITION     has_open_position
      4. SCORE_BELOW_THRESHOLD score < minimum_score        (main uses >=)
      5. REENTRY_BLOCKED       reentry_blocked
      6. SYMBOL_WINRATE_BLOCKED not symbol_winrate_ok
      7. POSITION_CAP_REACHED  position_cap_reached
      -> ELIGIBLE_LONG / ELIGIBLE_SHORT
    """
    direction = int(inp.combined_signal)
    family = dominant_strategy_family(
        direction,
        inp.trend_signal,
        inp.volume_profile_signal,
        inp.bollinger_signal,
    )

    def hold(reason: EntryReasonCode) -> EntryDecisionResult:
        return EntryDecisionResult(EntryAction.HOLD, 0, inp.score, family, reason)

    if direction == 0:
        return hold(EntryReasonCode.NO_SIGNAL)
    if not inp.symbol_tradable:
        return hold(EntryReasonCode.SYMBOL_NOT_TRADABLE)
    if inp.has_open_position:
        return hold(EntryReasonCode.EXISTING_POSITION)
    if int(inp.score) < int(inp.minimum_score):
        return hold(EntryReasonCode.SCORE_BELOW_THRESHOLD)
    if inp.reentry_blocked:
        return hold(EntryReasonCode.REENTRY_BLOCKED)
    if not inp.symbol_winrate_ok:
        return hold(EntryReasonCode.SYMBOL_WINRATE_BLOCKED)
    if inp.position_cap_reached:
        return hold(EntryReasonCode.POSITION_CAP_REACHED)

    reason = (
        EntryReasonCode.ELIGIBLE_LONG if direction == 1
        else EntryReasonCode.ELIGIBLE_SHORT
    )
    return EntryDecisionResult(EntryAction.ENTER, direction, inp.score, family, reason)
