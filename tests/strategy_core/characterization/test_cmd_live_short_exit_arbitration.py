"""SR-100B2: characterization of main.cmd_live EXIT arbitration for an already-open
SHORT position, driven through the SR-100A one-cycle harness (conftest.run_one_cycle).
Mirrors test_cmd_live_exit_arbitration.py (LONG) for the SHORT side.

Covers HOLD, hard stop-loss, hard take-profit, and opposite-signal FLIP. These tests
freeze the CURRENT observed behavior; they do not judge or change it. The real
src.risk sizing/stop functions run unpatched; indicator/signal outputs are fixtures.

Scope: existing SHORT position only (long side is covered by
test_cmd_live_exit_arbitration.py).

Observed close-position call convention (main.py:1998):
    executor.close_position(symbol, pos['qty'], pos['dir'])
i.e. the HELD position direction is passed (short -> -1), NOT a reversed/closing side.

Observed exit reasons (main.py:2004): 'SL' | 'TP' | 'FLIP' (SL precedes TP precedes
early-exit precedes FLIP).

Observed PnL formula (main.py:2002): pnl = (price - pos['entry']) * pos['qty'] * pos['dir'].
For a short (dir=-1) this is (entry - price) * qty, i.e. profit when price falls.

Observed replacement-entry behavior:
- SL / TP call _block_reentry (main.py:2024-2025) -> NO same-cycle replacement entry.
- FLIP does NOT block reentry -> a same-cycle REVERSE long entry IS created when the
  opposite signal's score passes the Crypto threshold (characterized below).

Config relied upon (current production values, not overridden):
- MIN_HOLD_DAYS = 0            -> min_hold_ok is True, so FLIP is active.
- TSL_TIGHT_AFTER_R_BY_CLASS['Crypto'] = 2.0, ATR_STOP_MULTIPLIER = 3.0
  With atr=2 and the prices below, the trailing-stop candidate never falls below the
  entry, so no set_trading_stop fires -- keeping each exit trigger isolated.
"""
from __future__ import annotations

ENTRY_PX = 100.0
BTC = "BYBIT:BTCUSDT.P"

# signal spec tuple = (combined, score, trend, vp, bb)
_FLAT = (0, 0, 0, 0, 0)
_LONG_S5 = (1, 5, 1, 0, 0)   # opposite-of-short (flip) signal; dominant family = trend


def _held_short(*, sl, tp, mark):
    """A pre-existing SHORT position as returned by executor.get_positions()."""
    return {"symbol": "BTCUSDT", "size": "1.0", "side": "Sell",
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
        positions=(_held_short(sl=110.0, tp=70.0, mark=ENTRY_PX),),
        live_price=ENTRY_PX,          # 100, strictly between TP 70 and SL 110
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


# ── Hard stop-loss: price at effective SL, clearly above TP ────────────────────
def test_hard_stop_loss_exit(run_one_cycle):
    price = 110.0
    fake, ledger = run_one_cycle(
        cryptos=[BTC],
        signals={BTC: _FLAT},
        positions=(_held_short(sl=110.0, tp=70.0, mark=price),),
        live_price=price,             # at SL (110 >= SL), unambiguous vs TP 70
    )
    closes = fake.calls["close_position"]
    assert len(closes) == 1
    assert closes[0]["symbol"] == BTC
    assert float(closes[0]["qty"]) == 1.0
    assert closes[0]["direction"] == -1           # HELD short direction (not reversed)
    assert fake.calls["place_order"] == []        # no automatic replacement entry
    assert fake.calls["set_trading_stop"] == []

    exits = _exits(ledger)
    assert len(exits) == 1
    assert exits[0]["reason"] == "SL"
    assert str(exits[0]["symbol"]) == BTC
    assert exits[0]["direction"] == -1
    assert float(exits[0]["quantity"]) == 1.0
    assert float(exits[0]["price"]) == price
    assert float(exits[0]["pnl"]) == (price - ENTRY_PX) * 1.0 * -1   # -10.0
    assert _strategy_entries(ledger) == []        # no same-cycle replacement


# ── Hard take-profit: price at TP, clearly below SL ───────────────────────────
def test_hard_take_profit_exit(run_one_cycle):
    price = 96.0                      # TP=96 keeps the trailing-stop candidate above entry
    fake, ledger = run_one_cycle(
        cryptos=[BTC],
        signals={BTC: _FLAT},
        positions=(_held_short(sl=110.0, tp=96.0, mark=price),),
        live_price=price,             # at TP (96 <= TP), unambiguous vs SL 110
    )
    closes = fake.calls["close_position"]
    assert len(closes) == 1
    assert closes[0]["symbol"] == BTC
    assert float(closes[0]["qty"]) == 1.0
    assert closes[0]["direction"] == -1
    assert fake.calls["place_order"] == []        # no replacement entry
    assert fake.calls["set_trading_stop"] == []   # trailing stop does not fire here

    exits = _exits(ledger)
    assert len(exits) == 1
    assert exits[0]["reason"] == "TP"
    assert float(exits[0]["quantity"]) == 1.0
    assert float(exits[0]["price"]) == price
    assert float(exits[0]["pnl"]) == (price - ENTRY_PX) * 1.0 * -1   # +4.0
    assert _strategy_entries(ledger) == []


# ── Opposite-signal FLIP: closes the short AND opens a reverse long same cycle ─
def test_opposite_signal_flip_closes_short_and_reverses_long(run_one_cycle):
    price = ENTRY_PX                  # 100, inside SL/TP -> only the FLIP path triggers
    fake, ledger = run_one_cycle(
        cryptos=[BTC],
        signals={BTC: _LONG_S5},      # combined +1, score 5 (>= Crypto threshold 3)
        positions=(_held_short(sl=110.0, tp=70.0, mark=price),),
        live_price=price,
    )
    # (1) the held short is closed with reason FLIP
    closes = fake.calls["close_position"]
    assert len(closes) == 1
    assert closes[0]["symbol"] == BTC
    assert float(closes[0]["qty"]) == 1.0
    assert closes[0]["direction"] == -1           # closes the HELD short
    exits = _exits(ledger)
    assert len(exits) == 1
    assert exits[0]["reason"] == "FLIP"
    assert float(exits[0]["price"]) == price
    assert float(exits[0]["pnl"]) == 0.0          # exit at entry price

    # (2) OBSERVED: a same-cycle REVERSE LONG entry IS created (FLIP does not block
    # reentry, and score 5 passes the threshold). Pinned exactly as current behavior.
    orders = fake.calls["place_order"]
    assert len(orders) == 1
    assert orders[0]["symbol"] == BTC
    assert orders[0]["direction"] == 1            # reverse long
    assert float(orders[0]["qty"]) > 0
    reverse = _strategy_entries(ledger)
    assert len(reverse) == 1
    assert reverse[0]["direction"] == 1
    assert reverse[0]["strategy"] == "trend"
    assert int(reverse[0]["score"]) == 5
