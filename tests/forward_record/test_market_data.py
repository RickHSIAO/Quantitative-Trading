from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from apps.forward_record.market_data import BybitReadOnlyMarketDataProvider, CacheMarketDataProvider


class MarketDataTest(unittest.TestCase):
    def test_cache_provider_filters_by_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            prices = pd.DataFrame({
                "date": ["2026-01-01", "2026-01-02"],
                "symbol": ["A", "A"],
                "open": [1.0, 2.0],
                "close": [1.5, 2.5],
            })
            funding = pd.DataFrame({
                "timestamp": ["2026-01-01T00:00:00Z", "2026-01-03T00:00:00Z"],
                "symbol": ["A", "A"],
                "funding_rate": [0.0, 0.1],
                "interval_hours": [8, 8],
            })
            prices_path = base / "prices.parquet"
            funding_path = base / "funding.parquet"
            prices.to_parquet(prices_path, index=False)
            funding.to_parquet(funding_path, index=False)
            provider = CacheMarketDataProvider(prices_path, funding_path)

            self.assertEqual(len(provider.load_prices("2026-01-01")), 1)
            self.assertEqual(len(provider.load_funding("2026-01-01")), 1)

    def test_bybit_provider_disabled_without_network_flag(self) -> None:
        provider = BybitReadOnlyMarketDataProvider(allow_network=False)
        with self.assertRaises(RuntimeError):
            provider.load_prices("2026-01-01")


if __name__ == "__main__":
    unittest.main()

