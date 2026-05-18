from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from apps.forward_record.config import ForwardRecordConfig
from apps.forward_record.signal_loader import load_latest_positions
from apps.paper_trading.config import PaperTradingConfig


class SignalLoaderTest(unittest.TestCase):
    def test_load_latest_position_date_on_or_before_record_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "positions.parquet"
            pd.DataFrame({
                "date": ["2026-01-01", "2026-01-03"],
                "symbol": ["A", "A"],
                "weight": [0.1, 0.2],
            }).to_parquet(path, index=False)
            config = ForwardRecordConfig(
                output_date="20260104",
                paper_config=PaperTradingConfig(positions_path=path),
            )

            loaded = load_latest_positions(config, "20260104")

            self.assertEqual(loaded.signal_date.strftime("%Y-%m-%d"), "2026-01-03")
            self.assertAlmostEqual(float(loaded.positions["weight"].iloc[0]), 0.2)


if __name__ == "__main__":
    unittest.main()

