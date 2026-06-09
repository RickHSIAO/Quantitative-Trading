"""
tests/demo_trading/test_demo_market_price_guard.py
TASK-014O: Tests for the realtime market price guard module.

Test groups:
  O1   missing realtime market price -> guard fails closed
  O2   stale candidate price (deviation > threshold) -> rejected
  O3   SOLUSDT incident replay (cand=160, real=66.47) -> stale rejected
  O4   price within threshold -> verified True
  O5   threshold edge case (deviation == threshold) -> verified True
  O6   invalid threshold -> guard fails with invalid_price_guard_threshold
  O7   invalid candidate entry_reference_price -> guard fails
  O8   fixture-mode client returns FIXTURE_MARKET_PRICES (no I/O)
  O9   real-mode client hits api-demo.bybit.com /v5/market/tickers only
  O10  no order endpoint paths or live hostname in module source
  O11  no forbidden imports (main / src.risk / BybitExecutor / sender / pybit)
  O12  RealtimeMarketPrice.is_usable() semantics

All tests are pure-computation except O9 which mocks urllib.request.urlopen.
"""
from __future__ import annotations

import ast
import json
import math
from pathlib import Path
from unittest.mock import patch

import pytest

from src.demo_market_price_guard import (
    DEFAULT_PRICE_GUARD_THRESHOLD_PCT,
    DEMO_BASE_URL,
    FIXTURE_MARKET_PRICES,
    GUARD_FAIL_INVALID_CANDIDATE_PRICE,
    GUARD_FAIL_INVALID_REALTIME_PRICE,
    GUARD_FAIL_INVALID_THRESHOLD,
    GUARD_FAIL_MISSING_REALTIME_PRICE,
    GUARD_FAIL_STALE_ENTRY_REFERENCE_PRICE,
    MARKET_TICKERS_ENDPOINT,
    PRICE_SOURCE_BYBIT_DEMO_TICKER,
    PRICE_SOURCE_FIXTURE,
    PRICE_SOURCE_NONE,
    DemoMarketPriceGuard,
    PriceGuardEvaluation,
    RealtimeMarketPrice,
    evaluate_candidates_against_market,
    evaluate_price_guard,
)


_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _ROOT / "src" / "demo_market_price_guard.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _market_price(
    symbol:     str,
    price:      float,
    source:     str = PRICE_SOURCE_BYBIT_DEMO_TICKER,
    timestamp:  str = "2026-06-09T12:00:00Z",
    error:      str = "",
) -> RealtimeMarketPrice:
    return RealtimeMarketPrice(
        symbol=symbol,
        realtime_market_price=price,
        price_source=source,
        price_timestamp_utc=timestamp,
        fetch_error_reason=error,
    )


# ---------------------------------------------------------------------------
# O1 — missing realtime market price -> fails closed
# ---------------------------------------------------------------------------

class TestO1MissingRealtimePrice:
    def test_market_price_is_none_fails(self):
        ev = evaluate_price_guard(
            symbol="SOLUSDT",
            candidate_entry_reference_price=66.0,
            market_price=None,
            threshold_pct=5.0,
        )
        assert ev.realtime_price_guard_verified is False
        assert ev.price_guard_fail_reason == GUARD_FAIL_MISSING_REALTIME_PRICE
        assert ev.realtime_market_price == 0.0
        assert ev.price_source == PRICE_SOURCE_NONE

    def test_market_price_with_fetch_error_fails(self):
        mp = _market_price("SOLUSDT", 0.0, error="fetch_error:HTTPError")
        ev = evaluate_price_guard(
            symbol="SOLUSDT",
            candidate_entry_reference_price=66.0,
            market_price=mp,
            threshold_pct=5.0,
        )
        assert ev.realtime_price_guard_verified is False
        assert ev.price_guard_fail_reason == GUARD_FAIL_MISSING_REALTIME_PRICE

    def test_market_price_zero_fails(self):
        mp = _market_price("SOLUSDT", 0.0)
        ev = evaluate_price_guard(
            symbol="SOLUSDT",
            candidate_entry_reference_price=66.0,
            market_price=mp,
            threshold_pct=5.0,
        )
        assert ev.realtime_price_guard_verified is False
        assert ev.price_guard_fail_reason == GUARD_FAIL_MISSING_REALTIME_PRICE

    def test_market_price_negative_fails(self):
        mp = _market_price("SOLUSDT", -1.0)
        ev = evaluate_price_guard(
            symbol="SOLUSDT",
            candidate_entry_reference_price=66.0,
            market_price=mp,
            threshold_pct=5.0,
        )
        assert ev.realtime_price_guard_verified is False
        assert ev.price_guard_fail_reason == GUARD_FAIL_MISSING_REALTIME_PRICE

    def test_market_price_nan_fails(self):
        mp = _market_price("SOLUSDT", float("nan"))
        ev = evaluate_price_guard(
            symbol="SOLUSDT",
            candidate_entry_reference_price=66.0,
            market_price=mp,
            threshold_pct=5.0,
        )
        assert ev.realtime_price_guard_verified is False
        assert ev.price_guard_fail_reason == GUARD_FAIL_MISSING_REALTIME_PRICE


# ---------------------------------------------------------------------------
# O2 — stale candidate price (deviation > threshold) -> rejected
# ---------------------------------------------------------------------------

class TestO2StaleCandidatePrice:
    def test_high_candidate_deviation_rejected(self):
        # candidate=100, real=90 => |100-90|/90 = 11.1% > 5%
        mp = _market_price("AAVEUSDT", 90.0)
        ev = evaluate_price_guard(
            symbol="AAVEUSDT",
            candidate_entry_reference_price=100.0,
            market_price=mp,
            threshold_pct=5.0,
        )
        assert ev.realtime_price_guard_verified is False
        assert ev.price_guard_fail_reason == GUARD_FAIL_STALE_ENTRY_REFERENCE_PRICE
        assert ev.price_deviation_pct > 5.0
        assert ev.realtime_market_price == 90.0

    def test_low_candidate_deviation_rejected(self):
        # candidate=80, real=100 => 20% > 5%
        mp = _market_price("AAVEUSDT", 100.0)
        ev = evaluate_price_guard(
            symbol="AAVEUSDT",
            candidate_entry_reference_price=80.0,
            market_price=mp,
            threshold_pct=5.0,
        )
        assert ev.realtime_price_guard_verified is False
        assert ev.price_guard_fail_reason == GUARD_FAIL_STALE_ENTRY_REFERENCE_PRICE
        assert ev.price_deviation_pct == pytest.approx(20.0, abs=1e-6)


# ---------------------------------------------------------------------------
# O3 — SOLUSDT incident replay
# ---------------------------------------------------------------------------

class TestO3SolusdtIncidentReplay:
    """The actual production incident: review preview had entry_reference_price=160,
    but the realtime SOLUSDT price was ~66.47.  The guard must reject."""

    def test_solusdt_160_vs_real_6647_rejected(self):
        mp = _market_price("SOLUSDT", 66.47)
        ev = evaluate_price_guard(
            symbol="SOLUSDT",
            candidate_entry_reference_price=160.0,
            market_price=mp,
            threshold_pct=5.0,
        )
        assert ev.realtime_price_guard_verified is False
        assert ev.price_guard_fail_reason == GUARD_FAIL_STALE_ENTRY_REFERENCE_PRICE
        # |160-66.47|/66.47 ≈ 140.7%
        assert ev.price_deviation_pct > 100.0
        assert ev.realtime_market_price == 66.47
        assert ev.candidate_entry_reference_price == 160.0

    def test_aaveusdt_120_vs_real_90_rejected(self):
        mp = _market_price("AAVEUSDT", 90.0)
        ev = evaluate_price_guard(
            symbol="AAVEUSDT",
            candidate_entry_reference_price=120.0,
            market_price=mp,
            threshold_pct=5.0,
        )
        assert ev.realtime_price_guard_verified is False
        assert ev.price_guard_fail_reason == GUARD_FAIL_STALE_ENTRY_REFERENCE_PRICE


# ---------------------------------------------------------------------------
# O4 — price within threshold -> verified True
# ---------------------------------------------------------------------------

class TestO4PriceWithinThreshold:
    def test_exact_match_verified(self):
        mp = _market_price("SOLUSDT", 66.47)
        ev = evaluate_price_guard(
            symbol="SOLUSDT",
            candidate_entry_reference_price=66.47,
            market_price=mp,
            threshold_pct=5.0,
        )
        assert ev.realtime_price_guard_verified is True
        assert ev.price_guard_fail_reason == ""
        assert ev.price_deviation_pct == pytest.approx(0.0, abs=1e-12)

    def test_small_deviation_verified(self):
        # cand=68, real=66.47 => 2.3% < 5%
        mp = _market_price("SOLUSDT", 66.47)
        ev = evaluate_price_guard(
            symbol="SOLUSDT",
            candidate_entry_reference_price=68.0,
            market_price=mp,
            threshold_pct=5.0,
        )
        assert ev.realtime_price_guard_verified is True
        assert ev.price_deviation_pct < 5.0


# ---------------------------------------------------------------------------
# O5 — threshold edge case
# ---------------------------------------------------------------------------

class TestO5ThresholdEdge:
    def test_deviation_at_threshold_verified(self):
        # |105-100|/100 = 5% == threshold
        mp = _market_price("BTCUSDT", 100.0)
        ev = evaluate_price_guard(
            symbol="BTCUSDT",
            candidate_entry_reference_price=105.0,
            market_price=mp,
            threshold_pct=5.0,
        )
        assert ev.realtime_price_guard_verified is True

    def test_deviation_just_over_threshold_rejected(self):
        # |105.001-100|/100 ≈ 5.001%
        mp = _market_price("BTCUSDT", 100.0)
        ev = evaluate_price_guard(
            symbol="BTCUSDT",
            candidate_entry_reference_price=105.01,
            market_price=mp,
            threshold_pct=5.0,
        )
        assert ev.realtime_price_guard_verified is False
        assert ev.price_guard_fail_reason == GUARD_FAIL_STALE_ENTRY_REFERENCE_PRICE


# ---------------------------------------------------------------------------
# O6 — invalid threshold
# ---------------------------------------------------------------------------

class TestO6InvalidThreshold:
    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
    def test_invalid_threshold_fails(self, bad):
        mp = _market_price("SOLUSDT", 66.47)
        ev = evaluate_price_guard(
            symbol="SOLUSDT",
            candidate_entry_reference_price=66.0,
            market_price=mp,
            threshold_pct=bad,
        )
        assert ev.realtime_price_guard_verified is False
        assert ev.price_guard_fail_reason == GUARD_FAIL_INVALID_THRESHOLD


# ---------------------------------------------------------------------------
# O7 — invalid candidate entry_reference_price
# ---------------------------------------------------------------------------

class TestO7InvalidCandidatePrice:
    @pytest.mark.parametrize("bad", [0.0, -10.0, float("nan"), float("inf")])
    def test_invalid_candidate_price_fails(self, bad):
        mp = _market_price("SOLUSDT", 66.47)
        ev = evaluate_price_guard(
            symbol="SOLUSDT",
            candidate_entry_reference_price=bad,
            market_price=mp,
            threshold_pct=5.0,
        )
        assert ev.realtime_price_guard_verified is False
        assert ev.price_guard_fail_reason == GUARD_FAIL_INVALID_CANDIDATE_PRICE


# ---------------------------------------------------------------------------
# O8 — fixture-mode client returns FIXTURE_MARKET_PRICES (no I/O)
# ---------------------------------------------------------------------------

class TestO8FixtureClient:
    def test_fixture_client_returns_solusdt_6647(self):
        client = DemoMarketPriceGuard(allow_real_network=False)
        snap   = client.fetch_market_price("SOLUSDT")
        assert snap.symbol == "SOLUSDT"
        assert snap.realtime_market_price == FIXTURE_MARKET_PRICES["SOLUSDT"]
        assert snap.realtime_market_price == 66.47   # incident value baked in
        assert snap.price_source == PRICE_SOURCE_FIXTURE
        assert snap.fetch_error_reason == ""
        assert snap.is_usable() is True

    def test_fixture_client_unknown_symbol_returns_zero(self):
        client = DemoMarketPriceGuard(allow_real_network=False)
        snap   = client.fetch_market_price("NOTREAL")
        assert snap.symbol == "NOTREAL"
        assert snap.realtime_market_price == 0.0
        assert snap.fetch_error_reason  # populated
        assert snap.is_usable() is False

    def test_fixture_client_makes_no_network_call(self):
        client = DemoMarketPriceGuard(allow_real_network=False)
        # If fixture mode ever called urlopen, this would error
        with patch("urllib.request.urlopen", side_effect=AssertionError("no I/O allowed")):
            snap = client.fetch_market_price("SOLUSDT")
        assert snap.realtime_market_price == 66.47

    def test_fixture_client_batch_fetch(self):
        client = DemoMarketPriceGuard(allow_real_network=False)
        prices = client.fetch_market_prices(["SOLUSDT", "AAVEUSDT", "ZZZUSDT"])
        assert prices["SOLUSDT"].realtime_market_price == 66.47
        assert prices["AAVEUSDT"].realtime_market_price == 90.0
        assert prices["ZZZUSDT"].realtime_market_price == 0.0


# ---------------------------------------------------------------------------
# O9 — real-mode client hits api-demo.bybit.com /v5/market/tickers only
# ---------------------------------------------------------------------------

class TestO9RealModeUrl:
    def _mock_urlopen_response(self, *, last_price: float, symbol: str = "SOLUSDT"):
        from io import BytesIO

        class FakeResp:
            def __init__(self, payload: dict) -> None:
                self._payload = json.dumps(payload).encode("utf-8")
            def read(self) -> bytes:
                return self._payload
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.headers)
            return FakeResp({
                "retCode": 0,
                "result": {"list": [{
                    "symbol": symbol,
                    "lastPrice": str(last_price),
                }]},
            })

        captured: dict = {}
        return fake_urlopen, captured

    def test_real_mode_hits_demo_market_tickers_only(self):
        client = DemoMarketPriceGuard(allow_real_network=True)
        fake, captured = self._mock_urlopen_response(last_price=66.47)
        with patch("urllib.request.urlopen", side_effect=fake):
            snap = client.fetch_market_price("SOLUSDT")
        assert snap.realtime_market_price == 66.47
        assert snap.price_source == PRICE_SOURCE_BYBIT_DEMO_TICKER
        assert snap.fetch_error_reason == ""
        # URL invariants
        url = captured["url"]
        assert url.startswith(DEMO_BASE_URL)
        assert MARKET_TICKERS_ENDPOINT in url
        # No live hostname
        assert "api.bybit.com" not in url.replace("api-demo.bybit.com", "")
        # No order endpoint
        assert "/v5/order/" not in url
        # No HMAC signing headers (public endpoint)
        assert "X-BAPI-SIGN" not in captured["headers"]
        assert "x-bapi-sign" not in {k.lower() for k in captured["headers"]}

    def test_real_mode_ret_code_nonzero_fails_gracefully(self):
        client = DemoMarketPriceGuard(allow_real_network=True)
        from io import BytesIO

        class FakeResp:
            def read(self): return b'{"retCode": 10001, "result": {}}'
            def __enter__(self): return self
            def __exit__(self, *a): return False
        with patch("urllib.request.urlopen", return_value=FakeResp()):
            snap = client.fetch_market_price("SOLUSDT")
        assert snap.realtime_market_price == 0.0
        assert "retCode" in snap.fetch_error_reason
        assert snap.is_usable() is False

    def test_real_mode_network_error_fails_gracefully(self):
        client = DemoMarketPriceGuard(allow_real_network=True)
        with patch("urllib.request.urlopen", side_effect=OSError("conn refused")):
            snap = client.fetch_market_price("SOLUSDT")
        assert snap.realtime_market_price == 0.0
        assert "fetch_error" in snap.fetch_error_reason


# ---------------------------------------------------------------------------
# O10 — no order endpoint paths or live hostname in module source
# ---------------------------------------------------------------------------

class TestO10ModuleSourceClean:
    def test_no_order_paths(self):
        src = _MODULE_PATH.read_text(encoding="utf-8").lower()
        forbidden = [
            "/v5/order/create",
            "/v5/order/cancel",
            "/v5/order/create-batch",
            "/v5/order/cancel-all",
            "/v5/order/amend",
            "/v5/position/set-leverage",
            "/v5/position/trading-stop",
            "/v5/asset/transfer",
            "/v5/asset/withdraw",
        ]
        for tok in forbidden:
            assert tok not in src, f"forbidden order path in module: {tok}"

    def test_no_live_hostname_request(self):
        src = _MODULE_PATH.read_text(encoding="utf-8")
        # _LIVE_HOSTNAME is allowed as a sentinel string, but only at its
        # declaration; the demo URL must be the only one used as a request
        # target.  We check that "https://api.bybit.com" is not present.
        assert "https://api.bybit.com" not in src

    def test_no_hmac_signing(self):
        src = _MODULE_PATH.read_text(encoding="utf-8")
        # Public ticker endpoint is unauthenticated; no HMAC is needed.
        assert "X-BAPI-SIGN" not in src
        assert "hmac.new" not in src
        assert "hashlib.sha256" not in src

    def test_no_secret_envvars(self):
        src = _MODULE_PATH.read_text(encoding="utf-8")
        assert "BYBIT_DEMO_API_SECRET" not in src
        assert "BYBIT_DEMO_API_KEY" not in src
        assert "os.environ" not in src


# ---------------------------------------------------------------------------
# O11 — no forbidden imports
# ---------------------------------------------------------------------------

class TestO11ForbiddenImports:
    def _imports(self) -> set[str]:
        tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))
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
        "main",
        "src.risk",
        "BybitExecutor",
        "demo_close_only_sender",
        "demo_new_entry_sender",
        "demo_emergency_close_sender",
        "execute_demo_close_only_cleanup",
        "execute_demo_new_entry",
        "execute_demo_emergency_close",
        "pybit",
    ])
    def test_forbidden_module_not_imported(self, forbidden):
        names = self._imports()
        # Strict match: no import has the forbidden name as a top-level module,
        # a submodule chain, or a from-import target.
        for n in names:
            assert forbidden not in n.split(".") and not n.endswith(forbidden), (
                f"forbidden import found: {forbidden} in {n}"
            )


# ---------------------------------------------------------------------------
# O12 — RealtimeMarketPrice.is_usable() semantics
# ---------------------------------------------------------------------------

class TestO12IsUsable:
    def test_positive_usable_no_error(self):
        assert _market_price("X", 1.0).is_usable() is True

    def test_zero_not_usable(self):
        assert _market_price("X", 0.0).is_usable() is False

    def test_negative_not_usable(self):
        assert _market_price("X", -1.0).is_usable() is False

    def test_nan_not_usable(self):
        assert _market_price("X", float("nan")).is_usable() is False

    def test_inf_not_usable(self):
        assert _market_price("X", float("inf")).is_usable() is False

    def test_error_reason_not_usable(self):
        assert _market_price("X", 1.0, error="fetch_error").is_usable() is False


# ---------------------------------------------------------------------------
# Batch helper
# ---------------------------------------------------------------------------

class TestBatchHelper:
    def test_evaluate_candidates_against_market(self):
        evals = evaluate_candidates_against_market(
            candidate_entry_prices={
                "SOLUSDT": 160.0,  # stale
                "AAVEUSDT": 91.0,  # within 5% of 90
                "BTCUSDT": 67_000.0,  # not in market dict
            },
            market_prices={
                "SOLUSDT": _market_price("SOLUSDT", 66.47),
                "AAVEUSDT": _market_price("AAVEUSDT", 90.0),
                # BTCUSDT intentionally omitted
            },
            threshold_pct=5.0,
        )
        assert evals["SOLUSDT"].realtime_price_guard_verified is False
        assert evals["SOLUSDT"].price_guard_fail_reason == GUARD_FAIL_STALE_ENTRY_REFERENCE_PRICE
        assert evals["AAVEUSDT"].realtime_price_guard_verified is True
        assert evals["BTCUSDT"].realtime_price_guard_verified is False
        assert evals["BTCUSDT"].price_guard_fail_reason == GUARD_FAIL_MISSING_REALTIME_PRICE


# ---------------------------------------------------------------------------
# Dataclass serialization
# ---------------------------------------------------------------------------

class TestDataclassSerialization:
    def test_price_guard_evaluation_to_dict(self):
        ev = evaluate_price_guard(
            symbol="SOLUSDT",
            candidate_entry_reference_price=66.5,
            market_price=_market_price("SOLUSDT", 66.47),
            threshold_pct=5.0,
        )
        d = ev.to_dict()
        for key in [
            "symbol", "candidate_entry_reference_price",
            "realtime_market_price", "price_source",
            "price_timestamp_utc", "price_guard_threshold_pct",
            "price_deviation_pct", "realtime_price_guard_verified",
            "price_guard_fail_reason",
        ]:
            assert key in d

    def test_realtime_market_price_to_dict(self):
        mp = _market_price("SOLUSDT", 66.47)
        d = mp.to_dict()
        for key in ["symbol", "realtime_market_price", "price_source",
                    "price_timestamp_utc", "fetch_error_reason"]:
            assert key in d
