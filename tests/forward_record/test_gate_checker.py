from __future__ import annotations

import unittest

from apps.forward_record.gate_checker import evaluate_gates, review_006b_trigger_ready


class GateCheckerTest(unittest.TestCase):
    def test_warning_and_stop_gates(self) -> None:
        stats = {
            "days_elapsed": 30,
            "sharpe_rolling_30d": 0.1,
            "max_dd_pct": -0.41,
            "tracking_error_vs_baseline_30d": 0.60,
        }
        result = evaluate_gates(
            stats=stats,
            overlay_false_streak=10,
            safety_pass=False,
            universe_count=8,
        )
        self.assertIn("W-1", result["active_warning_gates"])
        self.assertIn("W-2", result["active_warning_gates"])
        self.assertIn("W-3", result["active_warning_gates"])
        self.assertIn("W-4", result["active_warning_gates"])
        self.assertIn("S-2", result["active_stop_gates"])
        self.assertIn("S-4", result["active_stop_gates"])
        self.assertIn("S-5", result["active_stop_gates"])
        self.assertIn("S-6", result["active_stop_gates"])
        self.assertTrue(result["clock_paused"])

    def test_review_006b_ready_requires_all_conditions(self) -> None:
        stats = {
            "days_elapsed": 30,
            "sharpe_rolling_30d": 0.6,
            "max_dd_pct": -0.1,
            "active_stop_gates": [],
        }
        self.assertTrue(review_006b_trigger_ready(stats, overlay_always_pass=True, exception_recorded=False))
        stats["days_elapsed"] = 29
        self.assertFalse(review_006b_trigger_ready(stats, overlay_always_pass=True, exception_recorded=False))


if __name__ == "__main__":
    unittest.main()

