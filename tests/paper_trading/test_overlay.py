from __future__ import annotations

import unittest

import pandas as pd

from apps.paper_trading.config import PaperTradingConfig
from apps.paper_trading.overlay import apply_variant_overlay


class OverlayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = PaperTradingConfig()
        self.positions = pd.DataFrame({
            "date": ["2026-04-30"] * 4,
            "symbol": ["A", "B", "C", "D"],
            "weight": [0.40, 0.20, -0.20, -0.20],
        })
        self.funding = pd.DataFrame({
            "timestamp": [
                "2026-04-25T00:00:00Z",
                "2026-04-25T00:00:00Z",
                "2026-04-25T00:00:00Z",
                "2026-04-25T00:00:00Z",
            ],
            "symbol": ["A", "B", "C", "D"],
            "funding_rate": [0.0004, 0.0, 0.0, 0.0],
            "interval_hours": [8, 8, 8, 8],
        })

    def test_combined_overlay_enforces_funding_long_and_symbol_caps(self) -> None:
        result = apply_variant_overlay(self.positions, self.funding, "2026-04-30", self.config)
        weights = dict(zip(result.positions["symbol"], result.positions["weight"]))
        self.assertEqual(weights["A"], 0.0)
        self.assertLessEqual(sum(value for value in weights.values() if value > 0), 0.5 * sum(abs(v) for v in weights.values()))
        self.assertTrue(all(abs(value) <= 0.05 + 1e-12 for value in weights.values()))
        rules = {event["rule"] for event in result.events}
        self.assertIn("funding_filter_0.03pct_8h", rules)
        self.assertIn("symbol_cap_5pct", rules)

    def test_secondary_overlay_only_applies_funding_filter(self) -> None:
        result = apply_variant_overlay(
            self.positions,
            self.funding,
            "2026-04-30",
            self.config,
            variant=self.config.secondary_variant,
        )
        weights = dict(zip(result.positions["symbol"], result.positions["weight"]))
        self.assertEqual(weights["A"], 0.0)
        self.assertEqual(weights["B"], 0.20)
        self.assertEqual(weights["C"], -0.20)


if __name__ == "__main__":
    unittest.main()
