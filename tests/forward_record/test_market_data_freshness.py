"""
tests/forward_record/test_market_data_freshness.py
TASK-011A: Tests for LiveReadOnlyMarketDataProvider, freshness diagnostic,
and the primary.py price-date fix (record_ts vs signal_date).

SAFETY: no live network calls, no order endpoints, no Bybit write API.
All network calls are mocked.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import apps.forward_record.market_data as md


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_cache_parquet(tmp_path: Path, dates: list[str], symbols: list[str],
                        price: float = 100.0) -> Path:
    """Write a minimal prices parquet to tmp_path."""
    rows = []
    for d in dates:
        for sym in symbols:
            rows.append({"date": pd.Timestamp(d), "symbol": sym,
                         "open": price, "close": price})
    df = pd.DataFrame(rows)
    p = tmp_path / "prices_daily.parquet"
    df.to_parquet(p, index=False)
    return p


def _make_funding_parquet(tmp_path: Path) -> Path:
    """Write a minimal funding parquet."""
    df = pd.DataFrame({
        "timestamp":      [pd.Timestamp("2026-04-30", tz="UTC")],
        "symbol":         ["BYBIT:BTCUSDT.P"],
        "funding_rate":   [0.0001],
        "interval_hours": [8],
    })
    p = tmp_path / "funding_rates.parquet"
    df.to_parquet(p, index=False)
    return p


def _bybit_ticker_response(symbols_prices: dict[str, float]) -> bytes:
    """Build a fake Bybit /v5/market/tickers JSON response."""
    items = [{"symbol": sym, "lastPrice": str(px)}
             for sym, px in symbols_prices.items()]
    return json.dumps({"retCode": 0, "retMsg": "OK",
                       "result": {"list": items}}).encode()


# ---------------------------------------------------------------------------
# TestSymbolMapping
# ---------------------------------------------------------------------------

class TestSymbolMapping:
    def test_bybit_to_internal(self):
        assert md._bybit_symbol_to_internal("BTCUSDT") == "BYBIT:BTCUSDT.P"

    def test_bybit_to_internal_1inch(self):
        assert md._bybit_symbol_to_internal("1INCHUSDT") == "BYBIT:1INCHUSDT.P"

    def test_internal_to_bybit(self):
        assert md._internal_to_bybit_symbol("BYBIT:BTCUSDT.P") == "BTCUSDT"

    def test_internal_to_bybit_1inch(self):
        assert md._internal_to_bybit_symbol("BYBIT:1INCHUSDT.P") == "1INCHUSDT"

    def test_roundtrip(self):
        internal = "BYBIT:AAVEUSDT.P"
        assert md._bybit_symbol_to_internal(
            md._internal_to_bybit_symbol(internal)
        ) == internal


# ---------------------------------------------------------------------------
# TestFetchBybitTickers
# ---------------------------------------------------------------------------

class TestFetchBybitTickers:
    def _mock_urlopen(self, body: bytes):
        """Context manager mock for urllib.request.urlopen."""
        cm = mock.MagicMock()
        cm.__enter__ = mock.Mock(return_value=cm)
        cm.__exit__ = mock.Mock(return_value=False)
        cm.read.return_value = body
        return cm

    def test_returns_dataframe_with_correct_columns(self):
        body = _bybit_ticker_response({"BTCUSDT": 80000.0, "ETHUSDT": 3000.0})
        with mock.patch("urllib.request.urlopen", return_value=self._mock_urlopen(body)):
            df = md._fetch_bybit_tickers("https://api.bybit.com", "20260525")
        assert set(df.columns) >= {"date", "symbol", "open", "close"}

    def test_symbol_converted_to_internal_format(self):
        body = _bybit_ticker_response({"BTCUSDT": 80000.0})
        with mock.patch("urllib.request.urlopen", return_value=self._mock_urlopen(body)):
            df = md._fetch_bybit_tickers("https://api.bybit.com", "20260525")
        assert "BYBIT:BTCUSDT.P" in df["symbol"].values

    def test_lastprice_becomes_open_and_close(self):
        body = _bybit_ticker_response({"BTCUSDT": 80000.0})
        with mock.patch("urllib.request.urlopen", return_value=self._mock_urlopen(body)):
            df = md._fetch_bybit_tickers("https://api.bybit.com", "20260525")
        row = df[df["symbol"] == "BYBIT:BTCUSDT.P"].iloc[0]
        assert row["open"] == pytest.approx(80000.0)
        assert row["close"] == pytest.approx(80000.0)

    def test_date_is_as_of_date(self):
        body = _bybit_ticker_response({"BTCUSDT": 80000.0})
        with mock.patch("urllib.request.urlopen", return_value=self._mock_urlopen(body)):
            df = md._fetch_bybit_tickers("https://api.bybit.com", "20260525")
        assert df["date"].iloc[0] == pd.Timestamp("20260525")

    def test_zero_price_excluded(self):
        body = _bybit_ticker_response({"BTCUSDT": 0.0, "ETHUSDT": 3000.0})
        with mock.patch("urllib.request.urlopen", return_value=self._mock_urlopen(body)):
            df = md._fetch_bybit_tickers("https://api.bybit.com", "20260525")
        assert "BYBIT:BTCUSDT.P" not in df["symbol"].values
        assert "BYBIT:ETHUSDT.P" in df["symbol"].values

    def test_empty_lastprice_excluded(self):
        body = json.dumps({"retCode": 0, "result": {"list": [
            {"symbol": "BTCUSDT", "lastPrice": ""},
            {"symbol": "ETHUSDT", "lastPrice": "3000.0"},
        ]}}).encode()
        with mock.patch("urllib.request.urlopen", return_value=self._mock_urlopen(body)):
            df = md._fetch_bybit_tickers("https://api.bybit.com", "20260525")
        assert "BYBIT:BTCUSDT.P" not in df["symbol"].values

    def test_nonzero_retcode_raises(self):
        body = json.dumps({"retCode": 10001, "retMsg": "API error",
                           "result": {"list": []}}).encode()
        with mock.patch("urllib.request.urlopen", return_value=self._mock_urlopen(body)):
            with pytest.raises(RuntimeError, match="retCode=10001"):
                md._fetch_bybit_tickers("https://api.bybit.com", "20260525")

    def test_no_private_endpoint_called(self):
        """Verify only /v5/market/tickers (public GET) is called."""
        body = _bybit_ticker_response({"BTCUSDT": 80000.0})
        captured_urls = []
        def fake_urlopen(req, timeout=None):
            captured_urls.append(req.full_url)
            cm = mock.MagicMock()
            cm.__enter__ = mock.Mock(return_value=cm)
            cm.__exit__ = mock.Mock(return_value=False)
            cm.read.return_value = body
            return cm
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            md._fetch_bybit_tickers("https://api.bybit.com", "20260525")
        assert len(captured_urls) == 1
        assert "/v5/market/tickers" in captured_urls[0]
        assert "order" not in captured_urls[0].lower()
        assert "private" not in captured_urls[0].lower()


# ---------------------------------------------------------------------------
# TestLiveReadOnlyMarketDataProvider
# ---------------------------------------------------------------------------

class TestLiveReadOnlyMarketDataProvider:
    def _make_provider(self, tmp_path: Path) -> md.LiveReadOnlyMarketDataProvider:
        prices_p  = _make_cache_parquet(tmp_path, ["2026-04-30"], ["BYBIT:BTCUSDT.P"], price=75750.0)
        funding_p = _make_funding_parquet(tmp_path)
        return md.LiveReadOnlyMarketDataProvider(
            prices_path=prices_p,
            funding_path=funding_p,
        )

    def _mock_urlopen(self, body: bytes):
        cm = mock.MagicMock()
        cm.__enter__ = mock.Mock(return_value=cm)
        cm.__exit__ = mock.Mock(return_value=False)
        cm.read.return_value = body
        return cm

    def test_data_source_identifier(self, tmp_path: Path):
        p = self._make_provider(tmp_path)
        assert p.data_source == "bybit_read_only_live"

    def test_live_prices_appended_to_cache(self, tmp_path: Path):
        """load_prices should return cache rows PLUS live ticker row for today."""
        provider = self._make_provider(tmp_path)
        body = _bybit_ticker_response({"BTCUSDT": 80000.0})
        with mock.patch("urllib.request.urlopen", return_value=self._mock_urlopen(body)):
            df = provider.load_prices("20260525")
        dates = df["date"].dt.normalize().unique()
        assert pd.Timestamp("20260430") in dates
        assert pd.Timestamp("20260525") in dates

    def test_live_price_overrides_stale_cache(self, tmp_path: Path):
        """Today's row from Bybit tickers should be present and have live price."""
        provider = self._make_provider(tmp_path)
        body = _bybit_ticker_response({"BTCUSDT": 82000.0})
        with mock.patch("urllib.request.urlopen", return_value=self._mock_urlopen(body)):
            df = provider.load_prices("20260525")
        today_btc = df[
            (df["symbol"] == "BYBIT:BTCUSDT.P") &
            (df["date"].dt.normalize() == pd.Timestamp("20260525"))
        ]
        assert not today_btc.empty
        assert today_btc["open"].iloc[0] == pytest.approx(82000.0)

    def test_network_failure_falls_back_to_cache(self, tmp_path: Path):
        """If Bybit API is unreachable, fall back to cache silently (no exception)."""
        provider = self._make_provider(tmp_path)
        with mock.patch("urllib.request.urlopen", side_effect=OSError("network down")):
            df = provider.load_prices("20260525")
        # Should still return cache rows
        assert not df.empty
        assert pd.Timestamp("20260430") in df["date"].dt.normalize().values

    def test_load_funding_uses_cache(self, tmp_path: Path):
        """load_funding must not call the Bybit API."""
        provider = self._make_provider(tmp_path)
        with mock.patch("urllib.request.urlopen") as mock_net:
            df = provider.load_funding("20260430")
            mock_net.assert_not_called()
        assert not df.empty

    def test_no_order_api_called(self, tmp_path: Path):
        """Verify GET method and public-only endpoint."""
        provider = self._make_provider(tmp_path)
        body = _bybit_ticker_response({"BTCUSDT": 80000.0})
        captured = []
        def fake_urlopen(req, timeout=None):
            captured.append((req.method, req.full_url))
            cm = mock.MagicMock()
            cm.__enter__ = mock.Mock(return_value=cm)
            cm.__exit__ = mock.Mock(return_value=False)
            cm.read.return_value = body
            return cm
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            provider.load_prices("20260525")
        assert all(method == "GET" for method, _ in captured)
        assert all("order" not in url.lower() for _, url in captured)
        assert all("private" not in url.lower() for _, url in captured)


# ---------------------------------------------------------------------------
# TestCheckPriceFreshness
# ---------------------------------------------------------------------------

class TestCheckPriceFreshness:
    def _prices(self, dates: list[str], symbols: list[str] = None, price: float = 100.0) -> pd.DataFrame:
        symbols = symbols or ["BYBIT:BTCUSDT.P"]
        rows = [{"date": pd.Timestamp(d), "symbol": s, "open": price, "close": price}
                for d in dates for s in symbols]
        return pd.DataFrame(rows)

    def test_fresh_when_record_date_present(self):
        df = self._prices(["20260525"])
        result = md.check_price_freshness(df, "20260525")
        assert result["freshness_status"] == "FRESH"
        assert result["has_record_date_prices"] is True
        assert result["days_stale"] == 0

    def test_stale_recent_within_3_days(self):
        df = self._prices(["20260522"])
        result = md.check_price_freshness(df, "20260525")
        assert result["freshness_status"] == "STALE_RECENT"
        assert result["days_stale"] == 3

    def test_stale_old_beyond_3_days(self):
        df = self._prices(["20260430"])
        result = md.check_price_freshness(df, "20260525")
        assert result["freshness_status"] == "STALE_OLD"
        assert result["days_stale"] == 25

    def test_empty_frame_returns_no_data(self):
        df = pd.DataFrame(columns=["date", "symbol", "open", "close"])
        result = md.check_price_freshness(df, "20260525")
        assert result["freshness_status"] == "NO_DATA"

    def test_cache_latest_date_correct(self):
        df = self._prices(["20260520", "20260521", "20260522"])
        result = md.check_price_freshness(df, "20260525")
        assert result["cache_latest_date"] == "2026-05-22"

    def test_record_date_in_result(self):
        df = self._prices(["20260525"])
        result = md.check_price_freshness(df, "20260525")
        assert result["record_date"] == "2026-05-25"


# ---------------------------------------------------------------------------
# TestRunnerDataSourceFlag
# ---------------------------------------------------------------------------

class TestRunnerDataSourceFlag:
    """Verify run_forward_record.py wires the correct provider per --data-source."""
    RUNNER = ROOT / "scripts" / "run_forward_record.py"

    def test_live_read_only_in_choices(self):
        src = self.RUNNER.read_text(encoding="utf-8")
        assert "live_read_only" in src

    def test_cache_fallback_still_valid(self):
        src = self.RUNNER.read_text(encoding="utf-8")
        assert "cache_fallback" in src

    def test_livereadonlyprovider_imported(self):
        src = self.RUNNER.read_text(encoding="utf-8")
        assert "LiveReadOnlyMarketDataProvider" in src

    def test_daily_runner_uses_live_read_only_default(self):
        sh = (ROOT / "scripts" / "run_forward_record_daily.sh").read_text(encoding="utf-8")
        assert "live_read_only" in sh
        assert "DATA_SOURCE" in sh

    def test_daily_runner_passes_data_source_flag(self):
        sh = (ROOT / "scripts" / "run_forward_record_daily.sh").read_text(encoding="utf-8")
        assert "--data-source" in sh


# ---------------------------------------------------------------------------
# TestPrimaryPriceDateFix
# ---------------------------------------------------------------------------

class TestPrimaryPriceDateFix:
    """Verify primary.py loads prices at record_ts, not signal_date."""
    PRIMARY = ROOT / "apps" / "forward_record" / "primary.py"

    def test_prices_loaded_at_record_ts(self):
        src = self.PRIMARY.read_text(encoding="utf-8")
        # The provider.load_prices call must use record_ts, not loaded.signal_date
        assert "provider.load_prices(record_ts)" in src

    def test_latest_prices_at_record_ts(self):
        src = self.PRIMARY.read_text(encoding="utf-8")
        assert "latest_prices_by_symbol(prices, record_ts)" in src

    def test_signal_date_not_used_for_mtm_price(self):
        src = self.PRIMARY.read_text(encoding="utf-8")
        # Ensure old pattern is gone
        assert "latest_prices_by_symbol(prices, loaded.signal_date)" not in src

    def test_freshness_check_imported(self):
        src = self.PRIMARY.read_text(encoding="utf-8")
        assert "check_price_freshness" in src

    def test_freshness_called_in_build_primary_record(self):
        src = self.PRIMARY.read_text(encoding="utf-8")
        assert "check_price_freshness(prices, record_ts" in src


# ---------------------------------------------------------------------------
# TestSafetyInvariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:
    def test_no_order_endpoint_in_market_data(self):
        src = (ROOT / "apps" / "forward_record" / "market_data.py").read_text(encoding="utf-8")
        forbidden = ["place_order", "create_order", "submit_order",
                     "private_post", "cancel_order", "set_leverage"]
        for tok in forbidden:
            assert tok not in src.lower(), f"Forbidden token '{tok}' found in market_data.py"

    def test_only_get_method_in_live_provider(self):
        src = (ROOT / "apps" / "forward_record" / "market_data.py").read_text(encoding="utf-8")
        # The live provider class should only use GET
        assert 'method="GET"' in src

    def test_live_provider_endpoint_is_public_tickers(self):
        src = (ROOT / "apps" / "forward_record" / "market_data.py").read_text(encoding="utf-8")
        assert "/v5/market/tickers" in src

    def test_cache_provider_data_source_unchanged(self, tmp_path: Path):
        p  = _make_cache_parquet(tmp_path, ["2026-04-30"], ["BYBIT:BTCUSDT.P"])
        fp = _make_funding_parquet(tmp_path)
        provider = md.CacheMarketDataProvider(p, fp)
        assert provider.data_source == "cache_fallback"
