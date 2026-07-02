"""SR-100B1: characterization of main.cmd_live EXIT arbitration for an already-open
LONG position, driven through the SR-100A one-cycle harness (conftest.run_one_cycle).

Covers HOLD, hard stop-loss, hard take-profit, and opposite-signal FLIP. These tests
freeze the CURRENT observed behavior; they do not judge or change it. The real
src.risk sizing/stop functions run unpatched; indicator/signal outputs are fixtures.

Scope: existing LONG position only (short mirrors deferred to SR-100B2).

Observed close-position call convention (main.py:1998):
    executor.close_position(symbol, pos['qty'], pos['dir'])
i.e. the HELD position direction is passed (long -> 1), NOT a reversed/closing side.

Observed exit reasons (main.py:2004): 'SL' | 'TP' | 'FLIP' (SL precedes TP precedes
early-exit precedes FLIP).

Observed replacement-entry behavior:
- SL / TP call _block_reentry (main.py:2024-2025) -> NO same-cycle replacement entry.
- FLIP does NOT block reentry -> a same-cycle REVERSE short entry IS created when the
  opposite signal's score passes the Crypto threshold (characterized below).

Config relied upon (current production values, not overridden):
- MIN_HOLD_DAYS = 0            -> min_hold_ok is True, so FLIP is active.
- TSL_TIGHT_AFTER_R_BY_CLASS['Crypto'] = 2.0, ATR_STOP_MULTIPLIER = 3.0
  With atr=2 and the prices below, the trailing-stop candidate never rises above the
  entry, so no set_trading_stop fires -- keeping each exit trigger isolated.
"""
from __future__ import annotations

import src.strategy_core.exit_decision as exit_decision_module
from src.strategy_core.exit_decision import ExitAction, ExitDecisionResult

ENTRY_PX = 100.0
BTC = "BYBIT:BTCUSDT.P"

# signal spec tuple = (combined, score, trend, vp, bb)
_FLAT = (0, 0, 0, 0, 0)
_SHORT_S5 = (-1, 5, -1, 0, 0)   # opposite-of-long (flip) signal; dominant family = trend


def _held_long(*, sl, tp, mark):
    """A pre-existing LONG position as returned by executor.get_positions()."""
    return {"symbol": "BTCUSDT", "size": "1.0", "side": "Buy",
            "avgPrice": f"{ENTRY_PX}", "markPrice": f"{mark}",
            "stopLoss": f"{sl}", "takeProfit": f"{tp}"}


def _exits(ledger):
    return [c for c in ledger if str(c.get("action", "")).upper() == "EXIT"]


def _entries(ledger):
    return [c for c in ledger if str(c.get("action", "")).upper() == "ENTRY"]


def _strategy_entries(ledger):
    # A fresh strategy order, as opposed to the bookkeeping backfill of a held position.
    return [c for c in _entries(ledger) if "backfill" not in str(c.get("reason", "")).lower()]


# ── HOLD: price strictly inside SL/TP, no signal -> nothing happens ────────────
def test_hold_position_places_no_orders(run_one_cycle):
    fake, ledger = run_one_cycle(
        cryptos=[BTC],
        signals={BTC: _FLAT},
        positions=(_held_long(sl=90.0, tp=130.0, mark=ENTRY_PX),),
        live_price=ENTRY_PX,          # 100, strictly between SL 90 and TP 130
    )
    assert fake.calls["place_order"] == []
    assert fake.calls["close_position"] == []
    assert fake.calls["set_trading_stop"] == []
    assert _exits(ledger) == []                       # position remains held
    # Observed: only a bookkeeping backfill of the HELD 1.0 qty may appear -- never
    # an exchange entry order and never an exit.
    for e in _entries(ledger):
        assert "backfill" in str(e.get("reason", "")).lower()
        assert float(e["quantity"]) == 1.0


# ── Hard stop-loss: price at effective SL, clearly below TP ────────────────────
def test_hard_stop_loss_exit(run_one_cycle):
    price = 90.0
    fake, ledger = run_one_cycle(
        cryptos=[BTC],
        signals={BTC: _FLAT},
        positions=(_held_long(sl=90.0, tp=130.0, mark=price),),
        live_price=price,             # at SL (90 <= SL), unambiguous vs TP 130
    )
    closes = fake.calls["close_position"]
    assert len(closes) == 1
    assert closes[0]["symbol"] == BTC
    assert float(closes[0]["qty"]) == 1.0
    assert closes[0]["direction"] == 1            # HELD long direction (not reversed)
    assert fake.calls["place_order"] == []        # no automatic replacement entry
    assert fake.calls["set_trading_stop"] == []

    exits = _exits(ledger)
    assert len(exits) == 1
    assert exits[0]["reason"] == "SL"
    assert str(exits[0]["symbol"]) == BTC
    assert exits[0]["direction"] == 1
    assert float(exits[0]["quantity"]) == 1.0
    assert float(exits[0]["price"]) == price
    assert float(exits[0]["pnl"]) == (price - ENTRY_PX) * 1.0 * 1   # -10.0
    assert _strategy_entries(ledger) == []        # no same-cycle replacement


# ── Hard take-profit: price at TP, clearly above SL ───────────────────────────
def test_hard_take_profit_exit(run_one_cycle):
    price = 104.0                     # TP=104 keeps the trailing-stop candidate below entry
    fake, ledger = run_one_cycle(
        cryptos=[BTC],
        signals={BTC: _FLAT},
        positions=(_held_long(sl=90.0, tp=104.0, mark=price),),
        live_price=price,             # at TP (104 >= TP), unambiguous vs SL 90
    )
    closes = fake.calls["close_position"]
    assert len(closes) == 1
    assert closes[0]["symbol"] == BTC
    assert float(closes[0]["qty"]) == 1.0
    assert closes[0]["direction"] == 1
    assert fake.calls["place_order"] == []        # no replacement entry
    assert fake.calls["set_trading_stop"] == []   # trailing stop does not fire here

    exits = _exits(ledger)
    assert len(exits) == 1
    assert exits[0]["reason"] == "TP"
    assert float(exits[0]["quantity"]) == 1.0
    assert float(exits[0]["price"]) == price
    assert float(exits[0]["pnl"]) == (price - ENTRY_PX) * 1.0 * 1   # +4.0
    assert _strategy_entries(ledger) == []


# ── Opposite-signal FLIP: closes the long AND opens a reverse short same cycle ─
def test_opposite_signal_flip_closes_long_and_reverses_short(run_one_cycle):
    price = ENTRY_PX                  # 100, inside SL/TP -> only the FLIP path triggers
    fake, ledger = run_one_cycle(
        cryptos=[BTC],
        signals={BTC: _SHORT_S5},     # combined -1, score 5 (>= Crypto threshold 3)
        positions=(_held_long(sl=90.0, tp=130.0, mark=price),),
        live_price=price,
    )
    # (1) the held long is closed with reason FLIP
    closes = fake.calls["close_position"]
    assert len(closes) == 1
    assert closes[0]["symbol"] == BTC
    assert float(closes[0]["qty"]) == 1.0
    assert closes[0]["direction"] == 1            # closes the HELD long
    exits = _exits(ledger)
    assert len(exits) == 1
    assert exits[0]["reason"] == "FLIP"
    assert float(exits[0]["price"]) == price
    assert float(exits[0]["pnl"]) == 0.0          # exit at entry price

    # (2) OBSERVED: a same-cycle REVERSE SHORT entry IS created (FLIP does not block
    # reentry, and score 5 passes the threshold). Pinned exactly as current behavior.
    orders = fake.calls["place_order"]
    assert len(orders) == 1
    assert orders[0]["symbol"] == BTC
    assert orders[0]["direction"] == -1           # reverse short
    assert float(orders[0]["qty"]) > 0
    reverse = _strategy_entries(ledger)
    assert len(reverse) == 1
    assert reverse[0]["direction"] == -1
    assert reverse[0]["strategy"] == "trend"
    assert int(reverse[0]["score"]) == 5


# ── SR-102B: main.cmd_live uses the shared exit core AUTHORITATIVELY ──────────
def test_exit_core_is_authoritative_over_hard_stop_loss(run_one_cycle, monkeypatch):
    # Replace the shared exit core with one that always returns HOLD, then drive a
    # price sitting exactly at the hard stop loss (which the pre-extraction inline
    # arbitration would unconditionally close as 'SL'). Because cmd_live now defers
    # to the shared core, it must (1) consult it -- proven by the recorded call --
    # and (2) obey its HOLD verdict: no close_position, no EXIT ledger row. This is
    # only possible if no second independent SL/TP/FLIP copy remains in main.py.
    consulted = []

    def forced_hold(inp):
        consulted.append(inp.symbol)
        return ExitDecisionResult(ExitAction.HOLD, None, False, False, False, False)

    monkeypatch.setattr(exit_decision_module, "decide_exit", forced_hold)
    price = 90.0                                  # exactly at the hard SL (90 <= SL)
    fake, ledger = run_one_cycle(
        cryptos=[BTC],
        signals={BTC: _FLAT},
        positions=(_held_long(sl=90.0, tp=130.0, mark=price),),
        live_price=price,
    )
    assert consulted == [BTC]                     # cmd_live consulted the shared core
    assert fake.calls["close_position"] == []     # and obeyed HOLD despite hard SL
    assert _exits(ledger) == []
