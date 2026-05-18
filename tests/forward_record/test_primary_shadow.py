from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from apps.forward_record.config import ForwardRecordConfig
from apps.forward_record.market_data import CacheMarketDataProvider
from apps.forward_record.primary import build_primary_record
from apps.forward_record.shadow import adapter_status, build_shadow_record
from apps.paper_trading.config import PaperTradingConfig


class PrimaryShadowTest(unittest.TestCase):
    def test_primary_and_shadow_generate_separate_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            positions_path = base / "positions.parquet"
            prices_path = base / "prices.parquet"
            funding_path = base / "funding.parquet"
            detail_path = base / "task008_detail.csv"
            pd.DataFrame({
                "date": ["2026-01-01", "2026-01-01"],
                "symbol": ["A", "B"],
                "weight": [0.6, -0.4],
            }).to_parquet(positions_path, index=False)
            pd.DataFrame({
                "date": ["2026-01-01", "2026-01-01"],
                "symbol": ["A", "B"],
                "open": [10.0, 20.0],
                "close": [11.0, 19.0],
            }).to_parquet(prices_path, index=False)
            pd.DataFrame({
                "timestamp": ["2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"],
                "symbol": ["A", "B"],
                "funding_rate": [0.0, 0.0],
                "interval_hours": [8, 8],
            }).to_parquet(funding_path, index=False)
            pd.DataFrame({
                "variant": ["A_roll12_share20_exclude", "A_roll12_share20_exclude"],
                "date": ["2026-01-01", "2026-01-01"],
                "symbol": ["A", "B"],
                "original_weight": [0.5, -0.5],
                "variant_weight": [0.0, -0.5],
            }).to_csv(detail_path, index=False)
            paper_config = PaperTradingConfig(
                positions_path=positions_path,
                prices_path=prices_path,
                funding_path=funding_path,
            )
            config = ForwardRecordConfig(
                output_date="20260102",
                output_dir=base / "primary",
                shadow_output_dir=base / "shadow",
                paper_config=paper_config,
                task008_detail_path=detail_path,
            )
            provider = CacheMarketDataProvider(prices_path, funding_path)

            primary = build_primary_record(config, provider)
            shadow = build_shadow_record(config, provider)

            self.assertEqual(primary.variant, "combined_paper_safe_variant")
            self.assertEqual(shadow.variant, "A_roll12_share20_exclude")
            self.assertTrue(adapter_status(config).spec_found)
            self.assertNotEqual(primary.positions["weight"].tolist(), shadow.positions["weight"].tolist())
            self.assertTrue(primary.positions["paper_execution_status"].eq("FORBIDDEN").all())
            self.assertTrue(shadow.positions["live_trading_status"].eq("FORBIDDEN").all())


if __name__ == "__main__":
    unittest.main()

