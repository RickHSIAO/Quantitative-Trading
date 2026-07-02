"""SR-101D2: shadow-parity characterization of the same-process close-event
observation seam in main.cmd_live.

The seam is default-disabled: cmd_live emits ONE authoritative close event only
when an observer is injected via ``args._trade_history_close_event_observer``,
AFTER the legacy EXIT ledger record and gross ClosedTradeStub are already
written. These tests prove (a) the event fires exactly once per successful
same-process close, for long/short SL/TP/FLIP, (b) it never fires for HOLD or
remote/backfill bookkeeping, (c) the new Live adapter reproduces the current
EXIT gross PnL exactly, and (d) the seam changes no legacy close / ledger /
re-entry / Kelly behavior.

Reuses the SR-100A one-cycle harness (conftest.run_one_cycle) and FakeExecutor.
The observation clock (main._shadow_close_event_now) is monkeypatched to a fixed
timezone-aware UTC value.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

import main
from src.strategy_core.live_trade_history_adapter import (
    adapt_same_process_close_events,
    LiveSourceCompleteness,
)
from src.strategy_core.trade_history import CompletenessStatus

ENTRY_PX = 100.0
BTC = "BYBIT:BTCUSDT.P"
_FIXED_UTC = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

# signal spec tuple = (combined, score, trend, vp, bb)
_FLAT = (0, 0, 0, 0, 0)
_SHORT_S5 = (-1, 5, -1, 0, 0)   # flips a long
_LONG_S5 = (1, 5, 1, 0, 0)      # flips a short


def _held_long(*, sl, tp, mark):
    return {"symbol": "BTCUSDT", "size": "1.0", "side": "Buy",
            "avgPrice": f"{ENTRY_PX}", "markPrice": f"{mark}",
            "stopLoss": f"{sl}", "takeProfit": f"{tp}"}


def _held_short(*, sl, tp, mark):
    return {"symbol": "BTCUSDT", "size": "1.0", "side": "Sell",
            "avgPrice": f"{ENTRY_PX}", "markPrice": f"{mark}",
            "stopLoss": f"{sl}", "takeProfit": f"{tp}"}


def _exits(ledger):
    return [c for c in ledger if str(c.get("action", "")).upper() == "EXIT"]


@pytest.fixture
def collect(monkeypatch):
    """Return (events_list, observer) with the observation clock pinned."""
    monkeypatch.setattr(main, "_shadow_close_event_now", lambda: _FIXED_UTC)
    events: list = []
    return events, events.append


# ── 1. HOLD emits no event ──────────────────────────────────────────────────
def test_hold_emits_no_close_event(run_one_cycle, collect):
    events, observer = collect
    fake, ledger = run_one_cycle(
        cryptos=[BTC], signals={BTC: _FLAT},
        positions=(_held_long(sl=90.0, tp=130.0, mark=ENTRY_PX),),
        live_price=ENTRY_PX, close_event_observer=observer,
    )
    assert fake.calls["close_position"] == []
    assert events == []


# ── 2. Long SL emits one event ──────────────────────────────────────────────
def test_long_stop_loss_emits_one_event(run_one_cycle, collect):
    events, observer = collect
    price = 90.0
    fake, ledger = run_one_cycle(
        cryptos=[BTC], signals={BTC: _FLAT},
        positions=(_held_long(sl=90.0, tp=130.0, mark=price),),
        live_price=price, close_event_observer=observer,
    )
    assert len(events) == 1
    ev = events[0]
    assert ev["symbol"] == BTC
    assert ev["direction"] == 1
    assert float(ev["quantity"]) == 1.0
    assert float(ev["entry_price"]) == ENTRY_PX
    assert float(ev["exit_price"]) == price
    assert ev["close_reason"] == "SL"
    assert ev["exit_timestamp"] == _FIXED_UTC
    assert ev["exit_timestamp"].tzinfo is not None       # aware
    assert ev["exit_timestamp"].utcoffset().total_seconds() == 0.0   # UTC


# ── 3. Long TP emits reason TP ──────────────────────────────────────────────
def test_long_take_profit_emits_reason_tp(run_one_cycle, collect):
    events, observer = collect
    price = 104.0
    run_one_cycle(
        cryptos=[BTC], signals={BTC: _FLAT},
        positions=(_held_long(sl=90.0, tp=104.0, mark=price),),
        live_price=price, close_event_observer=observer,
    )
    assert len(events) == 1
    assert events[0]["close_reason"] == "TP"
    assert events[0]["direction"] == 1


# ── 4. Long FLIP emits one close event AND reverse short entry still occurs ──
def test_long_flip_emits_event_and_keeps_reverse_short_entry(run_one_cycle, collect):
    events, observer = collect
    price = ENTRY_PX
    fake, ledger = run_one_cycle(
        cryptos=[BTC], signals={BTC: _SHORT_S5},
        positions=(_held_long(sl=90.0, tp=130.0, mark=price),),
        live_price=price, close_event_observer=observer,
    )
    assert len(events) == 1
    assert events[0]["close_reason"] == "FLIP"
    assert events[0]["direction"] == 1                    # closed the held long
    # the same-cycle reverse SHORT entry is NOT suppressed
    orders = fake.calls["place_order"]
    assert len(orders) == 1
    assert orders[0]["direction"] == -1


# ── 5. Short SL emits direction -1 ──────────────────────────────────────────
def test_short_stop_loss_emits_direction_minus_one(run_one_cycle, collect):
    events, observer = collect
    price = 110.0
    run_one_cycle(
        cryptos=[BTC], signals={BTC: _FLAT},
        positions=(_held_short(sl=110.0, tp=70.0, mark=price),),
        live_price=price, close_event_observer=observer,
    )
    assert len(events) == 1
    assert events[0]["direction"] == -1
    assert events[0]["close_reason"] == "SL"


# ── 6. Short TP emits direction -1 reason TP ────────────────────────────────
def test_short_take_profit_emits_direction_minus_one_reason_tp(run_one_cycle, collect):
    events, observer = collect
    price = 96.0
    run_one_cycle(
        cryptos=[BTC], signals={BTC: _FLAT},
        positions=(_held_short(sl=110.0, tp=96.0, mark=price),),
        live_price=price, close_event_observer=observer,
    )
    assert len(events) == 1
    assert events[0]["direction"] == -1
    assert events[0]["close_reason"] == "TP"


# ── 7. Short FLIP emits event AND reverse long entry still occurs ───────────
def test_short_flip_emits_event_and_keeps_reverse_long_entry(run_one_cycle, collect):
    events, observer = collect
    price = ENTRY_PX
    fake, ledger = run_one_cycle(
        cryptos=[BTC], signals={BTC: _LONG_S5},
        positions=(_held_short(sl=110.0, tp=70.0, mark=price),),
        live_price=price, close_event_observer=observer,
    )
    assert len(events) == 1
    assert events[0]["close_reason"] == "FLIP"
    assert events[0]["direction"] == -1
    orders = fake.calls["place_order"]
    assert len(orders) == 1
    assert orders[0]["direction"] == 1                    # reverse long


# ── 8. Long event parity: adapter gross == EXIT ledger gross pnl ────────────
def _adapt_one(ev):
    return adapt_same_process_close_events(
        [ev],
        strategy_family=ev["strategy_family"] or "unknown",
        strategy_spec_version="v1",
        source_reference="live://shadow-parity",
        source_completeness=LiveSourceCompleteness.ATTESTED_COMPLETE,
        generated_at=_FIXED_UTC,
    )


def test_long_event_adapter_reproduces_exit_gross_pnl(run_one_cycle, collect):
    events, observer = collect
    price = 90.0
    fake, ledger = run_one_cycle(
        cryptos=[BTC], signals={BTC: _FLAT},
        positions=(_held_long(sl=90.0, tp=130.0, mark=price),),
        live_price=price, close_event_observer=observer,
    )
    exit_pnl = float(_exits(ledger)[0]["pnl"])            # legacy gross EXIT pnl
    snap = _adapt_one(events[0])
    assert snap.selected_kelly_pnls == (Decimal(str(exit_pnl)),)
    assert snap.selected_kelly_pnls == (Decimal("-10.0"),)
    assert snap.kelly_eligible_count == 1


# ── 9. Profitable short parity ──────────────────────────────────────────────
def test_short_event_adapter_reproduces_exit_gross_pnl(run_one_cycle, collect):
    events, observer = collect
    price = 96.0                                          # short TP, profit
    fake, ledger = run_one_cycle(
        cryptos=[BTC], signals={BTC: _FLAT},
        positions=(_held_short(sl=110.0, tp=96.0, mark=price),),
        live_price=price, close_event_observer=observer,
    )
    exit_pnl = float(_exits(ledger)[0]["pnl"])
    snap = _adapt_one(events[0])
    assert snap.selected_kelly_pnls == (Decimal(str(exit_pnl)),)
    assert snap.selected_kelly_pnls == (Decimal("4.0"),)  # (96-100)*1*-1 = +4


# ── 10. Zero-PnL FLIP event remains Kelly-eligible ──────────────────────────
def test_zero_pnl_flip_event_is_kelly_eligible(run_one_cycle, collect):
    events, observer = collect
    price = ENTRY_PX                                      # FLIP at entry -> pnl 0
    run_one_cycle(
        cryptos=[BTC], signals={BTC: _SHORT_S5},
        positions=(_held_long(sl=90.0, tp=130.0, mark=price),),
        live_price=price, close_event_observer=observer,
    )
    snap = _adapt_one(events[0])
    assert snap.selected_kelly_pnls == (Decimal("0.0"),)
    assert snap.kelly_eligible_count == 1                 # zero retained
    assert snap.completeness_status is CompletenessStatus.COMPLETE


# ── 11. Remote disappearance reconciliation emits no same-process event ─────
def test_remote_disappearance_reconciliation_emits_no_same_process_event(
        run_one_cycle, collect):
    # cmd_live's startup sync (main.py ~1754) reports a held long from the FIRST
    # executor.get_positions() call, populating open_pos AND persisting local
    # position metadata via _remember_position -- this is the real local
    # ledger/meta/open-position reconstruction, not a fabricated one. By the time
    # the in-cycle _sync_remote_positions() reconciliation runs its OWN
    # get_positions() call, the exchange no longer reports the position (e.g. it
    # was closed externally in between) -> the vanished-position branch in
    # _sync_remote_positions must reconcile it via the remote-close ledger path,
    # which never calls executor.close_position() and never touches the
    # same-process close-event observer.
    events, observer = collect
    fake, ledger = run_one_cycle(
        cryptos=[BTC], signals={BTC: _FLAT},
        positions=(_held_long(sl=90.0, tp=130.0, mark=ENTRY_PX),),
        positions_after_sync=(),         # vanished from the exchange by reconciliation
        live_price=ENTRY_PX, close_event_observer=observer,
    )
    assert fake.calls["close_position"] == []
    assert events == []
    # genuine reconciliation side effect: a remote EXIT ledger record was written
    # by _record_remote_close, distinguishable from a same-process close by its
    # reason and its synthetic "remote position closed" response message.
    exits = _exits(ledger)
    assert len(exits) == 1
    assert exits[0]["reason"] in ("REMOTE_CLOSED", "REMOTE_CLOSED_SL")
    assert exits[0]["response"]["retMsg"] == "remote position closed"


# ── 12. No observer -> unchanged behavior (legacy exit still recorded) ──────
def test_no_observer_leaves_close_and_ledger_unchanged(run_one_cycle):
    price = 90.0
    fake, ledger = run_one_cycle(
        cryptos=[BTC], signals={BTC: _FLAT},
        positions=(_held_long(sl=90.0, tp=130.0, mark=price),),
        live_price=price,                 # no close_event_observer
    )
    closes = fake.calls["close_position"]
    assert len(closes) == 1
    assert closes[0]["direction"] == 1
    exits = _exits(ledger)
    assert len(exits) == 1
    assert exits[0]["reason"] == "SL"
    assert float(exits[0]["pnl"]) == (price - ENTRY_PX) * 1.0 * 1


# ── 13. Exactly one event per successful same-process close ──────────────────
def test_exactly_one_event_per_close(run_one_cycle, collect):
    events, observer = collect
    price = 90.0
    fake, ledger = run_one_cycle(
        cryptos=[BTC], signals={BTC: _FLAT},
        positions=(_held_long(sl=90.0, tp=130.0, mark=price),),
        live_price=price, close_event_observer=observer,
    )
    assert len(fake.calls["close_position"]) == 1
    assert len(events) == 1


# ── 14. Mutating the received event cannot alter written ledger data ─────────
def test_event_mutation_does_not_affect_ledger(run_one_cycle, monkeypatch):
    monkeypatch.setattr(main, "_shadow_close_event_now", lambda: _FIXED_UTC)
    received: list = []

    def mutating_observer(ev):
        received.append(ev)
        ev["quantity"] = "999999"        # mutate AFTER receipt
        ev["exit_price"] = "0"

    price = 90.0
    fake, ledger = run_one_cycle(
        cryptos=[BTC], signals={BTC: _FLAT},
        positions=(_held_long(sl=90.0, tp=130.0, mark=price),),
        live_price=price, close_event_observer=mutating_observer,
    )
    # ledger EXIT already written with the real values, untouched by the mutation
    exit_row = _exits(ledger)[0]
    assert float(exit_row["quantity"]) == 1.0
    assert float(exit_row["pnl"]) == (price - ENTRY_PX) * 1.0 * 1
    # the close_position call recorded the real held qty/direction
    assert float(fake.calls["close_position"][0]["qty"]) == 1.0


# ── 15. Observer result / adapter never influences close/ledger/reentry/sizing
def test_observer_result_does_not_influence_trading(run_one_cycle, monkeypatch):
    monkeypatch.setattr(main, "_shadow_close_event_now", lambda: _FIXED_UTC)

    def returning_observer(ev):
        # adapter runs inside the observer; its return is ignored by trading logic
        _adapt_one(ev)
        return {"applied_kelly": 0.999}   # a value cmd_live must never consume

    price = ENTRY_PX
    fake, ledger = run_one_cycle(
        cryptos=[BTC], signals={BTC: _SHORT_S5},          # long FLIP
        positions=(_held_long(sl=90.0, tp=130.0, mark=price),),
        live_price=price, close_event_observer=returning_observer,
    )
    # FLIP close + reverse short entry unchanged regardless of observer return
    closes = fake.calls["close_position"]
    assert len(closes) == 1 and closes[0]["direction"] == 1
    exits = _exits(ledger)
    assert len(exits) == 1 and exits[0]["reason"] == "FLIP"
    orders = fake.calls["place_order"]
    assert len(orders) == 1 and orders[0]["direction"] == -1
