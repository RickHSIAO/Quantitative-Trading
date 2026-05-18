from __future__ import annotations

import unittest

from apps.forward_record.config import ForwardRecordConfig
from apps.forward_record.stats_updater import build_forward_stats, build_forward_summary


class StatsUpdaterTest(unittest.TestCase):
    def test_dry_run_stats_do_not_start_review_clock(self) -> None:
        config = ForwardRecordConfig(output_date="20260101", dry_run=True)
        pnl = {"variant": config.primary_variant, "day_number": 0}

        stats = build_forward_stats(config, pnl, source_position_count=20)
        summary = build_forward_summary(config, stats)

        self.assertEqual(stats["status"], "DRY_RUN")
        self.assertEqual(stats["days_elapsed"], 0)
        self.assertFalse(stats["review_006b_trigger_ready"])
        self.assertFalse(summary["review_006b_trigger_ready"])
        self.assertEqual(summary["paper_execution_status"], "FORBIDDEN")


if __name__ == "__main__":
    unittest.main()

