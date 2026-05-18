from __future__ import annotations

import unittest

import pandas as pd

from src.variants.task008 import (
    VariantSpec,
    _alpha_share_lookup,
    build_monthly_variant_weights,
    monthly_to_daily_weights,
    weights_from_daily_targets,
)


class Task008VariantTests(unittest.TestCase):
    def test_alpha_share_lookup_uses_prior_period_only(self) -> None:
        period_alpha = pd.DataFrame(
            [
                {"period_date": "2026-01-01", "symbol": "A", "net_alpha": 2.0},
                {"period_date": "2026-01-01", "symbol": "B", "net_alpha": 1.0},
                {"period_date": "2026-02-01", "symbol": "A", "net_alpha": 1.0},
                {"period_date": "2026-02-01", "symbol": "B", "net_alpha": 3.0},
            ]
        )
        period_alpha["period_date"] = pd.to_datetime(period_alpha["period_date"])

        shares = _alpha_share_lookup(period_alpha, rolling_periods=1)

        self.assertEqual(shares.get((pd.Timestamp("2026-01-01"), "A"), 0.0), 0.0)
        self.assertAlmostEqual(shares[(pd.Timestamp("2026-02-01"), "A")], 2.0 / 3.0)
        self.assertAlmostEqual(shares[(pd.Timestamp("2026-02-01"), "B")], 1.0 / 3.0)

    def test_rolling_cap_excludes_high_prior_alpha_and_refills(self) -> None:
        candidates = [
            {
                "date": pd.Timestamp("2026-02-01"),
                "long_count": 2,
                "short_count": 0,
                "long": ["A", "B", "C"],
                "short": [],
                "base_longs": ["A", "B"],
                "base_shorts": [],
            }
        ]
        spec = VariantSpec("test", "rolling_cap", rolling_periods=1, max_alpha_share=0.20, action="exclude")
        alpha_share = {(pd.Timestamp("2026-02-01"), "A"): 0.40}

        monthly, detail = build_monthly_variant_weights(candidates, alpha_share, spec)

        self.assertEqual(detail["cooldown_fallback_events"], 0)
        self.assertEqual(set(monthly["symbol"]), {"B", "C"})
        self.assertNotIn("A", set(monthly["symbol"]))
        self.assertAlmostEqual(monthly["target_weight"].sum(), 0.5)

    def test_alpha_share_sizing_preserves_side_gross(self) -> None:
        candidates = [
            {
                "date": pd.Timestamp("2026-02-01"),
                "long_count": 2,
                "short_count": 2,
                "long": ["A", "B"],
                "short": ["Y", "Z"],
                "base_longs": ["A", "B"],
                "base_shorts": ["Y", "Z"],
            }
        ]
        spec = VariantSpec("test", "alpha_share_sizing", rolling_periods=1, max_alpha_share=0.25)
        alpha_share = {
            (pd.Timestamp("2026-02-01"), "A"): 0.25,
            (pd.Timestamp("2026-02-01"), "Y"): 0.25,
        }

        monthly, _ = build_monthly_variant_weights(candidates, alpha_share, spec)

        long_sum = monthly.loc[monthly["target_weight"] > 0, "target_weight"].sum()
        short_sum = monthly.loc[monthly["target_weight"] < 0, "target_weight"].sum()
        self.assertAlmostEqual(long_sum, 0.5)
        self.assertAlmostEqual(short_sum, -0.5)
        self.assertLess(
            monthly.loc[monthly["symbol"] == "A", "target_weight"].iloc[0],
            monthly.loc[monthly["symbol"] == "B", "target_weight"].iloc[0],
        )

    def test_cooldown_fallback_records_insufficient_replacement(self) -> None:
        candidates = []
        for month in range(1, 5):
            candidates.append(
                {
                    "date": pd.Timestamp(f"2026-0{month}-01"),
                    "long_count": 1,
                    "short_count": 0,
                    "long": ["A"],
                    "short": [],
                    "base_longs": ["A"],
                    "base_shorts": [],
                }
            )
        spec = VariantSpec("test", "cooldown", cooldown_trigger=2, cooldown_periods=2, side_independent=True)

        monthly, detail = build_monthly_variant_weights(candidates, {}, spec)

        self.assertGreaterEqual(detail["cooldown_fallback_events"], 1)
        self.assertEqual(set(monthly["symbol"]), {"A"})

    def test_daily_target_mapping_is_date_and_symbol_specific(self) -> None:
        monthly = pd.DataFrame(
            [
                {"target_date": pd.Timestamp("2026-01-01"), "symbol": "A", "target_weight": 0.5, "variant": "v"},
                {"target_date": pd.Timestamp("2026-02-01"), "symbol": "B", "target_weight": 0.5, "variant": "v"},
            ]
        )
        daily_targets = monthly_to_daily_weights(
            monthly,
            [pd.Timestamp("2026-01-15"), pd.Timestamp("2026-02-15")],
        )
        fact = pd.DataFrame(
            [
                {"date": pd.Timestamp("2026-01-15"), "position_date": pd.Timestamp("2026-01-15"), "symbol": "A"},
                {"date": pd.Timestamp("2026-01-15"), "position_date": pd.Timestamp("2026-01-15"), "symbol": "B"},
                {"date": pd.Timestamp("2026-02-15"), "position_date": pd.Timestamp("2026-02-15"), "symbol": "B"},
            ]
        )

        weights = weights_from_daily_targets(fact, daily_targets, "date")

        self.assertEqual(weights.tolist(), [0.5, 0.0, 0.5])


if __name__ == "__main__":
    unittest.main()
