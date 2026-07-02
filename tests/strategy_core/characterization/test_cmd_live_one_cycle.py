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
import pytest
import src.strategy_core.entry_decision as entry_decision_module
from src.risk import calculate_stops, estimate_kelly_from_history, position_size

BTC = "BYBIT:BTCUSDT.P"
ETH = "BYBIT:ETHUSDT.P"

# signal spec tuple = (combined, score, trend, vp, bb)
_LONG_TREND_S5 = (1, 5, 1, 0, 0)   # combined long, score 5, dominant family = trend
_LONG_TREND_S2 = (1, 2, 1, 0, 0)   # combined long, score 2 (below Crypto threshold)
_FLAT = (0, 0, 0, 0, 0)
# combined long, score 5 (eligible), but the trend family's latest value is NaN
# (a genuine data-quality condition indicator computation can produce) -- not
# integer-convertible.
_LONG_MALFORMED_TREND_S5 = (1, 5, float("nan"), 0, 0)
# combined signal is ZERO (NO_SIGNAL gate fails first) with a malformed trend
# value -- the family-signal read must never happen, so the malformed value is
# never touched.
_ZERO_MALFORMED_TREND = (0, 5, float("nan"), 0, 0)
# combined long, but score is below the Crypto threshold (SCORE gate fails
# first) with a malformed trend value -- same requirement as above.
_BELOW_THRESHOLD_MALFORMED_TREND = (1, 2, float("nan"), 0, 0)

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


# ── SR-102A-R1: malformed family signal must not silently become an entry ─────
def test_malformed_family_signal_places_no_order(run_one_cycle):
    # The trend family's latest value is NaN (unconvertible via int()). The
    # shared entry-decision core's _latest_family_signal helper must NOT swallow
    # this into a silent 0/'combined' entry -- it must propagate to the existing
    # outer per-symbol try/except, exactly as the original
    # int(sigs['trend'].iloc[-1]) call inside _dominant_live_strategy did. The
    # symbol is simply skipped for this cycle: no order, no ledger entry.
    fake, ledger = run_one_cycle(
        cryptos=[BTC],
        signals={BTC: _LONG_MALFORMED_TREND_S5},
    )
    assert fake.calls["place_order"] == []
    assert _entries(ledger) == []


# ── SR-102A-R2: earlier gates must short-circuit before family signals are read ─
@pytest.mark.parametrize("spec", [
    pytest.param(_ZERO_MALFORMED_TREND, id="no_signal_gate_fails_first"),
    pytest.param(_BELOW_THRESHOLD_MALFORMED_TREND, id="score_gate_fails_first"),
])
def test_short_circuit_avoids_reading_family_signal_on_earlier_hold(
        run_one_cycle, capsys, spec):
    # In both cases an EARLIER gate (NO_SIGNAL or SCORE_BELOW_THRESHOLD) must
    # reject the symbol before the trend family's malformed (NaN) latest value
    # is ever read -- mirroring the original short-circuiting `and` chain,
    # which never called `_dominant_live_strategy` unless the signal/score/
    # reentry/winrate gates had already passed. This fails under an eager
    # implementation that reads all three family signals unconditionally,
    # since that would raise on the malformed value and print an [ERROR] line
    # even though no earlier gate depends on the family signal at all.
    fake, ledger = run_one_cycle(
        cryptos=[BTC],
        signals={BTC: spec},
    )
    assert fake.calls["place_order"] == []
    assert _entries(ledger) == []
    captured = capsys.readouterr()
    assert "cannot convert float NaN to integer" not in captured.out
    assert "[ERROR]" not in captured.out


# ── SR-102A-R1: global cap BREAKs the commit-gate loop (not continue) ──────────
def test_global_cap_break_stops_processing_later_candidates(run_one_cycle, monkeypatch):
    # Three distinct-family candidates, sorted by score desc: BTC(9,trend) fills
    # the (patched) single global slot; SOL(7,vp) then hits the cap; ADA(5,bb) is
    # the LATER, lower-score candidate that must never even reach the shared
    # commit-gate call once the global cap breaks the loop. A regression to
    # `continue` (SR-102A's bug) would still invoke decide_entry for ADA with
    # position_cap_reached=True -- observably different from the original
    # `if len(open_pos) >= crypto_max_positions: break` behavior, even though
    # both produce the same single order in THIS scenario.
    real_decide_entry = entry_decision_module.decide_entry
    cap_gate_calls = []

    def spy_decide_entry(inp):
        if inp.position_cap_reached:
            cap_gate_calls.append(inp.symbol)
        return real_decide_entry(inp)

    monkeypatch.setattr(entry_decision_module, "decide_entry", spy_decide_entry)
    crypto_profile = dict(config.STRATEGY_PROFILES.get("Crypto", {}))
    crypto_profile["max_total_positions"] = 1
    monkeypatch.setattr(config, "STRATEGY_PROFILES",
                        {**config.STRATEGY_PROFILES, "Crypto": crypto_profile})

    SOL = "BYBIT:SOLUSDT.P"
    ADA = "BYBIT:ADAUSDT.P"
    fake, ledger = run_one_cycle(
        cryptos=[BTC, SOL, ADA],
        signals={
            BTC: (1, 9, 1, 0, 0),   # trend family, highest score -> fills the cap
            SOL: (1, 7, 0, 1, 0),   # vp family, next -> hits the (now-reached) cap
            ADA: (1, 5, 0, 0, 1),   # bb family, lowest score -> must be unreached
        },
    )

    orders = fake.calls["place_order"]
    assert len(orders) == 1, "expected exactly one order: the cap-filling candidate"
    assert orders[0]["symbol"] == BTC

    # SOL's commit-gate call observes the newly-reached cap and HOLDs; ADA's
    # commit-gate must never run at all (break, not continue-past-cap).
    assert cap_gate_calls == [SOL], (
        f"expected the loop to break after SOL's cap-gated HOLD; got {cap_gate_calls}")
