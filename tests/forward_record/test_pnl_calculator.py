from __future__ import annotations

import unittest

import pandas as pd

from apps.forward_record.config import ForwardRecordConfig
from apps.forward_record.pnl_calculator import build_pnl_payload


class PnlCalculatorTest(unittest.TestCase):
    def test_pnl_payload_is_offline_and_forbidden(self) -> None:
        config = ForwardRecordConfig(output_date="20260101")
        positions = pd.DataFrame({
            "symbol": ["A", "B"],
            "weight": [0.2, -0.1],
            "data_source": ["cache_fallback", "cache_fallback"],
        })

        payload = build_pnl_payload(config, positions, config.primary_variant, day_number=0)

        self.assertEqual(payload["daily_pnl_pct"], 0.0)
        self.assertAlmostEqual(payload["gross_exposure"], 0.3)
        self.assertEqual(payload["paper_execution_status"], "FORBIDDEN")
        self.assertEqual(payload["live_trading_status"], "FORBIDDEN")
        self.assertFalse(payload["clock_started"])


if __name__ == "__main__":
    unittest.main()
