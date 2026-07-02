"""SR-100A: characterization of main.cmd_live arbitration for ONE scan cycle.

These tests freeze the CURRENT observed behavior of the live arbitration loop.
They do not assert the behavior is ideal; they pin what the code does today so a
later engine extraction cannot silently change it.

Indicator/signal outputs are deterministic fixtures (see conftest); the real
src.risk sizing/stop functions run unpatched so sizing is characterized, not faked.
Safety invariants (no network, exactly one cycle, no real sleep, no stray file
writes) are enforced inside the ``run_one_cycle`` fixture.
"""
from __future__ import annotations

import config
from src.risk import calculate_stops, estimate_kelly_from_history, position_size

BTC = "BYBIT:BTCUSDT.P"
ETH = "BYBIT:ETHUSDT.P"

# signal spec tuple = (combined, score, trend, vp, bb)
_LONG_TREND_S5 = (1, 5, 1, 0, 0)   # combined long, score 5, dominant family = trend
_LONG_TREND_S2 = (1, 2, 1, 0, 0)   # combined long, score 2 (below Crypto threshold)
_FLAT = (0, 0, 0, 0, 0)

_CRYPTO_MIN_SCORE = config.MIN_ENTRY_SCORE_BY_CLASS["Crypto"]   # 3 (documented)


def _entries(ledger_calls):
    return [c for c in ledger_calls if str(c.get("action", "")).upper() == "ENTRY"]


# ── Scenario 1: zero-signal cycle → no orders ─────────────────────────────────
def test_zero_signal_cycle_places_no_orders(run_one_cycle):
    fake, ledger = run_one_cycle(
        cryptos=[BTC, ETH],
        signals={BTC: _FLAT, ETH: _FLAT},
    )
    assert fake.calls["place_order"] == []
    assert fake.calls["close_position"] == []
    assert _entries(ledger) == []


# ── Scenario 2: one valid long entry → exactly one recorded place_order ────────
def test_one_valid_long_entry_is_recorded_with_expected_fields(run_one_cycle):
    available = 3123.45   # deliberately NOT 10_000, to prove sizing uses live equity
    price = 100.0
    fake, ledger = run_one_cycle(
        cryptos=[BTC],
        signals={BTC: _LONG_TREND_S5},
        positions=(),
        wallet=8000.0,
        available=available,
        live_price=price,
    )

    orders = fake.calls["place_order"]
    assert len(orders) == 1, "expected exactly one entry order"
    order = orders[0]
    assert order["symbol"] == BTC
    assert order["direction"] == 1                      # long
    qty = float(order["qty"])
    sl = float(order["stop_loss"])
    tp = float(order["take_profit"])
    assert qty > 0
    assert sl < price < tp                              # long: stop below, target above
    assert fake.calls["close_position"] == []

    # Sizing characterization: the recorded qty is exactly what the REAL
    # position_size() yields from the CURRENT available balance -- and differs
    # from what a fixed 10,000 base would yield. Proves no fixed capital base.
    stop_loss, _ = calculate_stops(price, 1, 2.0, strategy="trend", asset_type="Crypto")
    kelly = estimate_kelly_from_history([], window=config.KELLY_WINDOW, asset_type="Crypto")
    cap_pct = float(config.STRATEGY_PROFILES.get("Crypto", {}).get(
        "max_position_pct", config.MAX_POSITION_PCT))
    expected = position_size(available, kelly, price, stop_loss,
                             asset_type="Crypto", max_position_pct=cap_pct)
    expected_if_10k = position_size(10_000.0, kelly, price, stop_loss,
                                    asset_type="Crypto", max_position_pct=cap_pct)
    assert abs(qty - expected) < 1e-6, "sizing did not use the current available balance"
    assert abs(qty - expected_if_10k) > 1e-6, "sizing appears to use a fixed 10,000 base"

    # Ledger characterization: exactly one ENTRY row carrying the selected family + score.
    entries = _entries(ledger)
    assert len(entries) == 1
    assert entries[0]["strategy"] == "trend"           # dominant single family
    assert int(entries[0]["score"]) == 5


# ── Scenario 3: score below Crypto threshold → no order ───────────────────────
def test_score_below_threshold_places_no_order(run_one_cycle):
    assert _LONG_TREND_S2[1] < _CRYPTO_MIN_SCORE        # guard the fixture's premise
    fake, ledger = run_one_cycle(
        cryptos=[BTC],
        signals={BTC: _LONG_TREND_S2},
    )
    assert fake.calls["place_order"] == []
    assert _entries(ledger) == []


# ── Scenario 4: existing same-direction position → duplicate entry suppressed ──
def test_existing_position_suppresses_duplicate_entry(run_one_cycle):
    held = {
        "symbol": "BTCUSDT", "size": "1.0", "side": "Buy",
        "avgPrice": "100.0", "markPrice": "100.0",
        "stopLoss": "90.0", "takeProfit": "130.0",
    }
    fake, ledger = run_one_cycle(
        cryptos=[BTC],
        signals={BTC: _LONG_TREND_S5},   # same (long) direction as the held position
        positions=(held,),
        live_price=100.0,                # inside [SL 90, TP 130] -> no exit, no TSL
    )
    # PRIMARY duplicate protection: no new entry ORDER, and no exit/stop mutation.
    assert fake.calls["place_order"] == []
    assert fake.calls["close_position"] == []
    assert fake.calls["set_trading_stop"] == []

    # OBSERVED behavior (characterized, not judged): syncing a pre-existing remote
    # position with no matching ledger row backfills a bookkeeping ENTRY. It is a
    # ledger reconciliation of the HELD 1.0 qty -- NOT a fresh strategy-sized order
    # (contrast Scenario 2). We pin this so an engine refactor can't silently drop
    # or mutate it.
    entries = _entries(ledger)
    for e in entries:
        assert "backfill" in str(e.get("reason", "")).lower()
        assert float(e["quantity"]) == float(held["size"])
