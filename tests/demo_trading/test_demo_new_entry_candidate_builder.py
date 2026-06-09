"""
tests/demo_trading/test_demo_new_entry_candidate_builder.py
TASK-014P: Tests for the market-backed Demo new-entry candidate builder.

Tests are grouped P1-P12 + structural-invariant suites covering:
  P1  SOLUSDT realtime 65.92 -> entry_reference_price = 65.92
  P2  long stop_price < entry_price
  P3  short stop_price > entry_price
  P4  stop_distance > 0 after tick rounding
  P5  no realtime price -> skipped no_realtime_price
  P6  no fallback to stale fixture price
  P7  AAVEUSDT realtime 62.14 -> not 120 fixture
  P8  invalid stop_pct (<=0 or >=1) -> skipped invalid_stop_pct
  P9  invalid requested_risk_usd -> skipped invalid_requested_risk_usd
  P10 missing instrument rule -> skipped missing_instrument_rule
  P11 batch helper preserves input order
  P12 to_dict serialization round-trip
"""
from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from src.demo_instrument_rules import InstrumentRules
from src.demo_market_price_guard import (
    PRICE_SOURCE_BYBIT_DEMO_TICKER,
    RealtimeMarketPrice,
)
from src.demo_new_entry_candidate_builder import (
    DEFAULT_LONG_STOP_PCT,
    DEFAULT_SHORT_STOP_PCT,
    SKIP_INVALID_REALTIME_PRICE,
    SKIP_INVALID_RISK_USD,
    SKIP_INVALID_SIDE,
    SKIP_INVALID_STOP_DISTANCE,
    SKIP_INVALID_STOP_PCT,
    SKIP_INVALID_STOP_PRICE,
    SKIP_MISSING_INSTRUMENT_RULE,
    SKIP_NO_REALTIME_PRICE,
    CandidateBuildResult,
    NewEntryIntent,
    build_market_backed_candidate,
    build_market_backed_candidates,
)


_ROOT = Path(__file__).resolve().parents[2]
_BUILDER_PATH = _ROOT / "src" / "demo_new_entry_candidate_builder.py"


_RULES: dict[str, InstrumentRules] = {
    "SOLUSDT":  InstrumentRules("SOLUSDT",  0.1,  0.1,  0, 0.01,   1.0, 2, 1),
    "AAVEUSDT": InstrumentRules("AAVEUSDT", 0.01, 0.01, 0, 0.01,   1.0, 2, 2),
    "AVAXUSDT": InstrumentRules("AVAXUSDT", 0.1,  0.1,  0, 0.01,   1.0, 2, 1),
    "LINKUSDT": InstrumentRules("LINKUSDT", 0.1,  0.1,  0, 0.001,  1.0, 3, 1),
    "BTCUSDT":  InstrumentRules("BTCUSDT",  0.001, 0.001, 0, 0.1,  1.0, 1, 3),
}


def _market_price(
    symbol:    str,
    price:     float,
    source:    str   = PRICE_SOURCE_BYBIT_DEMO_TICKER,
    timestamp: str   = "2026-06-09T12:00:00Z",
    error:     str   = "",
) -> RealtimeMarketPrice:
    return RealtimeMarketPrice(
        symbol=symbol,
        realtime_market_price=price,
        price_source=source,
        price_timestamp_utc=timestamp,
        fetch_error_reason=error,
    )


def _intent(symbol: str, side: str, risk: float = 25.0, score: float = 0.8) -> NewEntryIntent:
    return NewEntryIntent(
        symbol=symbol, side=side,
        requested_risk_usd=risk, score=score,
    )


# ---------------------------------------------------------------------------
# P1 — SOLUSDT realtime 65.92 -> entry_reference_price = 65.92
# ---------------------------------------------------------------------------

class TestP1SolusdtMarketBackedEntry:
    def test_entry_equals_realtime_price(self):
        intent = _intent("SOLUSDT", "long", risk=40.0, score=1.0)
        mp = _market_price("SOLUSDT", 65.92)
        r = build_market_backed_candidate(
            intent=intent, market_price=mp,
            instrument_rule=_RULES["SOLUSDT"],
        )
        assert r.skipped is False
        assert r.skip_reason == ""
        assert r.candidate is not None
        assert r.candidate.entry_reference_price == pytest.approx(65.92)
        # entry must NOT be the legacy fixture 160.0
        assert r.candidate.entry_reference_price != pytest.approx(160.0)
        # stop is 5% below realtime, rounded to tick 0.01
        # 65.92 * 0.95 = 62.624 -> 62.62
        assert r.candidate.stop_price == pytest.approx(62.62)
        assert r.candidate.side == "long"
        assert r.realtime_market_price == pytest.approx(65.92)
        assert r.price_source == PRICE_SOURCE_BYBIT_DEMO_TICKER

    def test_requested_risk_and_score_preserved(self):
        intent = _intent("SOLUSDT", "long", risk=40.0, score=1.0)
        mp = _market_price("SOLUSDT", 65.92)
        r = build_market_backed_candidate(
            intent=intent, market_price=mp,
            instrument_rule=_RULES["SOLUSDT"],
        )
        assert r.candidate is not None
        assert r.candidate.requested_risk_usd == pytest.approx(40.0)
        assert r.candidate.score == pytest.approx(1.0)
        assert r.candidate.order_type == "Market"


# ---------------------------------------------------------------------------
# P2 — long stop_price < entry_price
# ---------------------------------------------------------------------------

class TestP2LongStopBelowEntry:
    def test_long_stop_strictly_below_entry(self):
        intent = _intent("AAVEUSDT", "long", risk=30.0)
        mp = _market_price("AAVEUSDT", 62.14)
        r = build_market_backed_candidate(
            intent=intent, market_price=mp,
            instrument_rule=_RULES["AAVEUSDT"],
        )
        assert r.skipped is False
        c = r.candidate
        assert c is not None
        assert c.side == "long"
        assert c.stop_price < c.entry_reference_price
        # 62.14 * 0.95 = 59.033 -> 59.03 at tick 0.01
        assert c.stop_price == pytest.approx(59.03)


# ---------------------------------------------------------------------------
# P3 — short stop_price > entry_price
# ---------------------------------------------------------------------------

class TestP3ShortStopAboveEntry:
    def test_short_stop_strictly_above_entry(self):
        intent = _intent("AVAXUSDT", "short", risk=25.0)
        mp = _market_price("AVAXUSDT", 6.696)
        r = build_market_backed_candidate(
            intent=intent, market_price=mp,
            instrument_rule=_RULES["AVAXUSDT"],
        )
        assert r.skipped is False
        c = r.candidate
        assert c is not None
        assert c.side == "short"
        assert c.stop_price > c.entry_reference_price
        # 6.696 * 1.05 = 7.0308 -> 7.03 at tick 0.01
        assert c.stop_price == pytest.approx(7.03)


# ---------------------------------------------------------------------------
# P4 — stop_distance > 0 after tick rounding
# ---------------------------------------------------------------------------

class TestP4StopDistancePositive:
    @pytest.mark.parametrize("symbol,price,side", [
        ("SOLUSDT",  65.92, "long"),
        ("AAVEUSDT", 62.14, "long"),
        ("AVAXUSDT",  6.70, "short"),
        ("LINKUSDT",  7.887, "short"),
        ("BTCUSDT",  64_000.0, "long"),
    ])
    def test_stop_distance_nonzero(self, symbol, price, side):
        intent = _intent(symbol, side)
        mp = _market_price(symbol, price)
        r = build_market_backed_candidate(
            intent=intent, market_price=mp,
            instrument_rule=_RULES[symbol],
        )
        assert r.skipped is False, f"unexpected skip: {r.skip_reason}"
        c = r.candidate
        assert c is not None
        assert abs(c.entry_reference_price - c.stop_price) > 0.0


# ---------------------------------------------------------------------------
# P5 — no realtime price -> skipped no_realtime_price
# ---------------------------------------------------------------------------

class TestP5NoRealtimePriceSkipped:
    def test_none_market_price_skipped(self):
        intent = _intent("SOLUSDT", "long")
        r = build_market_backed_candidate(
            intent=intent, market_price=None,
            instrument_rule=_RULES["SOLUSDT"],
        )
        assert r.skipped is True
        assert r.skip_reason == SKIP_NO_REALTIME_PRICE
        assert r.candidate is None
        assert r.realtime_market_price == 0.0

    def test_unusable_market_price_skipped(self):
        intent = _intent("SOLUSDT", "long")
        bad = _market_price("SOLUSDT", 0.0)
        r = build_market_backed_candidate(
            intent=intent, market_price=bad,
            instrument_rule=_RULES["SOLUSDT"],
        )
        assert r.skipped is True
        assert r.skip_reason == SKIP_INVALID_REALTIME_PRICE
        assert r.candidate is None

    def test_fetch_error_market_price_skipped(self):
        intent = _intent("SOLUSDT", "long")
        bad = _market_price("SOLUSDT", 65.92, error="network_error")
        r = build_market_backed_candidate(
            intent=intent, market_price=bad,
            instrument_rule=_RULES["SOLUSDT"],
        )
        # fetch_error_reason != "" makes is_usable() False
        assert r.skipped is True
        assert r.skip_reason == SKIP_INVALID_REALTIME_PRICE
        assert r.candidate is None


# ---------------------------------------------------------------------------
# P6 — no fallback to stale fixture price
# ---------------------------------------------------------------------------

class TestP6NoStaleFixtureFallback:
    """The builder MUST NOT emit a candidate carrying a fixture/cached price
    when the realtime feed is missing.  Compare against the historical
    incident values."""

    @pytest.mark.parametrize("symbol,stale_fixture", [
        ("SOLUSDT", 160.0),
        ("AAVEUSDT", 120.0),
    ])
    def test_skipped_candidate_does_not_carry_fixture_price(self, symbol, stale_fixture):
        intent = _intent(symbol, "long", risk=40.0)
        r = build_market_backed_candidate(
            intent=intent, market_price=None,
            instrument_rule=_RULES[symbol],
        )
        assert r.candidate is None
        # Even the skip record carries 0.0 — never the fixture price.
        assert r.realtime_market_price != stale_fixture
        d = r.to_dict()
        assert d["candidate_entry_reference_price"] == 0.0
        assert d["candidate_stop_price"] == 0.0


# ---------------------------------------------------------------------------
# P7 — AAVEUSDT realtime 62.14 -> not 120 fixture
# ---------------------------------------------------------------------------

class TestP7AaveusdtIncidentReplay:
    def test_aave_uses_realtime_not_120_fixture(self):
        intent = _intent("AAVEUSDT", "long", risk=30.0, score=0.9)
        mp = _market_price("AAVEUSDT", 62.14)
        r = build_market_backed_candidate(
            intent=intent, market_price=mp,
            instrument_rule=_RULES["AAVEUSDT"],
        )
        assert r.skipped is False
        c = r.candidate
        assert c is not None
        assert c.entry_reference_price == pytest.approx(62.14)
        assert c.entry_reference_price != pytest.approx(120.0)


# ---------------------------------------------------------------------------
# P8 — invalid stop_pct
# ---------------------------------------------------------------------------

class TestP8InvalidStopPct:
    @pytest.mark.parametrize("bad_pct", [0.0, -0.05, 1.0, 1.5, math.inf, math.nan])
    def test_long_invalid_stop_pct_skipped(self, bad_pct):
        intent = _intent("SOLUSDT", "long")
        mp = _market_price("SOLUSDT", 65.92)
        r = build_market_backed_candidate(
            intent=intent, market_price=mp,
            instrument_rule=_RULES["SOLUSDT"],
            long_stop_pct=bad_pct,
        )
        assert r.skipped is True
        assert r.skip_reason == SKIP_INVALID_STOP_PCT
        assert r.candidate is None

    @pytest.mark.parametrize("bad_pct", [0.0, -0.05, 1.0, 1.5, math.inf, math.nan])
    def test_short_invalid_stop_pct_skipped(self, bad_pct):
        intent = _intent("AVAXUSDT", "short")
        mp = _market_price("AVAXUSDT", 6.70)
        r = build_market_backed_candidate(
            intent=intent, market_price=mp,
            instrument_rule=_RULES["AVAXUSDT"],
            short_stop_pct=bad_pct,
        )
        assert r.skipped is True
        assert r.skip_reason == SKIP_INVALID_STOP_PCT
        assert r.candidate is None


# ---------------------------------------------------------------------------
# P9 — invalid requested_risk_usd
# ---------------------------------------------------------------------------

class TestP9InvalidRiskUsd:
    @pytest.mark.parametrize("bad", [0.0, -10.0, math.inf, math.nan])
    def test_invalid_risk_skipped(self, bad):
        intent = NewEntryIntent(
            symbol="SOLUSDT", side="long",
            requested_risk_usd=bad, score=1.0,
        )
        mp = _market_price("SOLUSDT", 65.92)
        r = build_market_backed_candidate(
            intent=intent, market_price=mp,
            instrument_rule=_RULES["SOLUSDT"],
        )
        assert r.skipped is True
        assert r.skip_reason == SKIP_INVALID_RISK_USD
        assert r.candidate is None


# ---------------------------------------------------------------------------
# P10 — missing instrument rule
# ---------------------------------------------------------------------------

class TestP10MissingInstrumentRule:
    def test_missing_rule_skipped(self):
        intent = _intent("UNKNOWNUSDT", "long")
        mp = _market_price("UNKNOWNUSDT", 100.0)
        r = build_market_backed_candidate(
            intent=intent, market_price=mp,
            instrument_rule=None,
        )
        assert r.skipped is True
        assert r.skip_reason == SKIP_MISSING_INSTRUMENT_RULE
        assert r.candidate is None


# ---------------------------------------------------------------------------
# Invalid side
# ---------------------------------------------------------------------------

class TestInvalidSide:
    @pytest.mark.parametrize("side", ["", "buy", "sell", "neutral"])
    def test_invalid_side_skipped(self, side):
        intent = NewEntryIntent(
            symbol="SOLUSDT", side=side,
            requested_risk_usd=40.0, score=1.0,
        )
        mp = _market_price("SOLUSDT", 65.92)
        r = build_market_backed_candidate(
            intent=intent, market_price=mp,
            instrument_rule=_RULES["SOLUSDT"],
        )
        assert r.skipped is True
        assert r.skip_reason == SKIP_INVALID_SIDE
        assert r.candidate is None


# ---------------------------------------------------------------------------
# Tick collapse / invalid stop distance
# ---------------------------------------------------------------------------

class TestInvalidStopDistance:
    def test_tick_collapse_marked_invalid_stop_distance(self):
        """For very small prices, a 0.5% stop_pct can collapse into the same
        tick after rounding, leaving stop_distance==0 — must skip."""
        # XRPUSDT-like setup with tick 0.0001 and price 0.62 -> 5% stop is
        # outside this collapse, so we synthesize a tighter pct.
        intent = _intent("XRPUSDT", "long")
        # tick=0.0001, price=1.00001 — stop pct 0.001% won't escape one tick
        mp = _market_price("XRPUSDT", 1.00001)
        rule = InstrumentRules("XRPUSDT", 1.0, 1.0, 0, 0.001, 1.0, 3, 0)
        r = build_market_backed_candidate(
            intent=intent, market_price=mp,
            instrument_rule=rule,
            long_stop_pct=1e-6,  # absurdly tight — stop collapses to same tick
        )
        # With pct so small the rounded stop equals rounded entry -> skip
        assert r.skipped is True
        assert r.skip_reason in (
            SKIP_INVALID_STOP_DISTANCE, SKIP_INVALID_STOP_PRICE,
        )


# ---------------------------------------------------------------------------
# P11 — batch helper
# ---------------------------------------------------------------------------

class TestP11BatchHelper:
    def test_batch_preserves_order_and_skips_missing(self):
        intents = [
            _intent("SOLUSDT",  "long",  risk=40.0, score=1.0),
            _intent("AAVEUSDT", "long",  risk=30.0, score=0.9),
            _intent("AVAXUSDT", "short", risk=25.0, score=0.8),
            _intent("LINKUSDT", "short", risk=20.0, score=0.7),
        ]
        market_prices = {
            "SOLUSDT":  _market_price("SOLUSDT",  65.92),
            "AAVEUSDT": _market_price("AAVEUSDT", 62.14),
            # AVAXUSDT — missing on purpose
            "LINKUSDT": _market_price("LINKUSDT",  7.887),
        }
        results = build_market_backed_candidates(
            intents=intents,
            market_prices=market_prices,
            instrument_rules=_RULES,
        )
        assert [r.intent.symbol for r in results] == [
            "SOLUSDT", "AAVEUSDT", "AVAXUSDT", "LINKUSDT"
        ]
        avax = next(r for r in results if r.intent.symbol == "AVAXUSDT")
        assert avax.skipped is True
        assert avax.skip_reason == SKIP_NO_REALTIME_PRICE
        for sym in ("SOLUSDT", "AAVEUSDT", "LINKUSDT"):
            built = next(r for r in results if r.intent.symbol == sym)
            assert built.skipped is False
            assert built.candidate is not None
            assert built.candidate.entry_reference_price == pytest.approx(
                market_prices[sym].realtime_market_price
            )


# ---------------------------------------------------------------------------
# P12 — to_dict serialization
# ---------------------------------------------------------------------------

class TestP12Serialization:
    def test_built_result_to_dict_keys(self):
        intent = _intent("SOLUSDT", "long", risk=40.0, score=1.0)
        mp = _market_price("SOLUSDT", 65.92)
        r = build_market_backed_candidate(
            intent=intent, market_price=mp,
            instrument_rule=_RULES["SOLUSDT"],
        )
        d = r.to_dict()
        required = {
            "symbol", "side", "requested_risk_usd", "score",
            "skipped", "skip_reason",
            "realtime_market_price", "price_source", "price_timestamp_utc",
            "long_stop_pct", "short_stop_pct",
            "candidate_entry_reference_price", "candidate_stop_price",
            "rounded_stop_price",
        }
        assert required.issubset(d.keys())
        assert d["skipped"] is False
        assert d["candidate_entry_reference_price"] == pytest.approx(65.92)

    def test_skipped_result_to_dict_keys(self):
        intent = _intent("SOLUSDT", "long")
        r = build_market_backed_candidate(
            intent=intent, market_price=None,
            instrument_rule=_RULES["SOLUSDT"],
        )
        d = r.to_dict()
        assert d["skipped"] is True
        assert d["skip_reason"] == SKIP_NO_REALTIME_PRICE
        assert d["candidate_entry_reference_price"] == 0.0


# ---------------------------------------------------------------------------
# Structural — module source cleanliness (TASK-014P invariants 13-16)
# ---------------------------------------------------------------------------

class TestModuleSourceClean:
    def test_no_live_hostname(self):
        src = _BUILDER_PATH.read_text(encoding="utf-8").lower()
        assert "api.bybit.com" not in src
        assert "api-testnet.bybit.com" not in src
        assert "api-demo.bybit.com" not in src

    def test_no_order_endpoint_tokens(self):
        src = _BUILDER_PATH.read_text(encoding="utf-8").lower()
        for tok in ("/v5/order/", "/v5/position/", "x-bapi-sign",
                    "api_key", "api_secret", "private_key", "bapi_sign"):
            assert tok not in src, f"forbidden token in builder module: {tok!r}"

    def test_no_http_client_imports(self):
        src = _BUILDER_PATH.read_text(encoding="utf-8")
        for tok in ("import urllib", "import requests", "import httpx",
                    "import http.client", "urlopen", "hmac"):
            assert tok not in src, f"forbidden token in builder module: {tok!r}"

    def test_no_env_var_reads(self):
        src = _BUILDER_PATH.read_text(encoding="utf-8")
        assert "os.environ" not in src
        assert "getenv" not in src


class TestForbiddenImports:
    def _imports(self) -> set[str]:
        tree = ast.parse(_BUILDER_PATH.read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                names.add(mod)
                for alias in node.names:
                    names.add(f"{mod}.{alias.name}")
        return names

    @pytest.mark.parametrize("forbidden", [
        "main", "src.risk", "BybitExecutor",
        "src.demo_close_only_sender",
        "src.demo_new_entry_sender",
        "src.demo_emergency_close_sender",
        "scripts.execute_demo_close_only_cleanup",
        "scripts.execute_demo_new_entry",
        "scripts.execute_demo_emergency_close",
        "pybit",
    ])
    def test_forbidden_module_not_imported(self, forbidden):
        names = self._imports()
        for n in names:
            assert forbidden not in n, (
                f"forbidden import {forbidden!r} appears in {n!r}"
            )
