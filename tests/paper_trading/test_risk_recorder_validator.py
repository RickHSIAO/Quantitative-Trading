from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from apps.paper_trading.config import PaperTradingConfig
from apps.paper_trading.recorder import SIMULATED_FILL_COLUMNS, build_intended_fills
from apps.paper_trading.report import validate_no_external_execution_paths
from apps.paper_trading.risk import evaluate_kill_switches
from apps.paper_trading.validator import evaluate_forward_validation


class RiskRecorderValidatorTest(unittest.TestCase):
    def test_risk_engine_triggers_all_kill_switches(self) -> None:
        daily = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=6),
            "paper_return": [-0.10, -0.10, -0.10, -0.10, -0.10, -0.01],
            "nav_usd": [9000, 8100, 7290, 6561, 5904.9, 5845.851],
        })
        events = evaluate_kill_switches(daily)
        event_types = {event["event_type"] for event in events}
        self.assertIn("MAX_DRAWDOWN_STOP", event_types)
        self.assertIn("CONSECUTIVE_LOSING_CYCLES_STOP", event_types)
        self.assertIn("MIN_NAV_STOP", event_types)

    def test_recorder_builds_local_simulated_fills_schema(self) -> None:
        config = PaperTradingConfig()
        target = pd.DataFrame({
            "date": ["2026-04-30", "2026-04-30"],
            "symbol": ["A", "B"],
            "weight": [0.05, 0.02],
            "overlay_rules_applied": ["", ""],
            "excluded_reason": ["", ""],
        })
        all_positions = pd.DataFrame({
            "date": ["2026-04-29", "2026-04-29", "2026-04-30", "2026-04-30"],
            "symbol": ["A", "B", "A", "B"],
            "weight": [0.00, 0.02, 0.05, 0.02],
        })
        prices = pd.DataFrame({
            "date": ["2026-05-01"],
            "symbol": ["A"],
            "open": [10.0],
        })
        fills = build_intended_fills(target, all_positions, prices, config)
        self.assertEqual(list(fills.columns), SIMULATED_FILL_COLUMNS)
        self.assertEqual(fills["symbol"].tolist(), ["A"])
        self.assertAlmostEqual(float(fills["prev_weight"].iloc[0]), 0.0)
        self.assertAlmostEqual(float(fills["target_weight"].iloc[0]), 0.05)
        self.assertAlmostEqual(float(fills["weight_delta"].iloc[0]), 0.05)
        self.assertEqual(float(fills["simulated_fill_price"].iloc[0]), 10.0)
        self.assertGreater(float(fills["simulated_fee_usd"].iloc[0]), 0.0)

    def test_forward_validation_metrics_are_reproducible(self) -> None:
        daily = pd.DataFrame({
            "paper_return": [0.01, -0.005, 0.002] * 10,
            "model_return": [0.01, -0.005, 0.002] * 10,
            "nav_usd": [10000 + i for i in range(30)],
        })
        first = evaluate_forward_validation(daily, days=30)
        second = evaluate_forward_validation(daily, days=30)
        self.assertEqual(first, second)
        self.assertFalse(first["forward_validation_pass"])
        self.assertEqual(first["tracking_error_monthly"], 0.0)
        self.assertEqual(first["paper_sharpe"], first["paper_sharpe_30d_proxy"])
        proxy_sharpe = first["proxy_sharpe_long_window"]
        self.assertEqual(proxy_sharpe["short_window"]["observed_days"], 30)
        self.assertFalse(proxy_sharpe["window_90d"]["available"])
        self.assertIsNone(proxy_sharpe["window_90d"]["annualized_sharpe"])
        self.assertTrue(proxy_sharpe["full_active_window"]["available"])
        self.assertEqual(proxy_sharpe["full_active_window"]["observed_days"], 30)

    def test_safety_scanner_passes_package(self) -> None:
        scan = validate_no_external_execution_paths([Path("apps/paper_trading")])
        self.assertEqual(scan["status"], "PASS")
        self.assertEqual(scan["violations"], [])


if __name__ == "__main__":
    unittest.main()
