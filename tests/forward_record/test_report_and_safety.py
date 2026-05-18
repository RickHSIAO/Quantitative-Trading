from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from apps.forward_record.config import ForwardRecordConfig
from apps.forward_record.report_writer import write_track_outputs
from apps.forward_record.safety import output_flags_present, scan_no_order_endpoints


class ReportAndSafetyTest(unittest.TestCase):
    def test_report_outputs_have_forbidden_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = ForwardRecordConfig(output_date="20260101", output_dir=base)
            positions = pd.DataFrame({
                "date": ["2026-01-01"],
                "record_date": ["2026-01-01"],
                "signal_date": ["2026-01-01"],
                "symbol": ["A"],
                "side": ["long"],
                "weight": [0.1],
                "weight_raw": [0.1],
                "funding_rate_30d_avg": [0.0],
                "overlay_rule1_applied": [False],
                "overlay_rule2_applied": [False],
                "overlay_rule3_applied": [False],
                "overlay_rules_applied": [""],
                "excluded_reason": [""],
                "hypothetical_fill_px": [1.0],
                "position_usd": [1000.0],
                "data_source": ["cache_fallback"],
                "variant": [config.primary_variant],
                "dry_run": [True],
                "clock_started": [False],
                "paper_execution_status": ["FORBIDDEN"],
                "live_trading_status": ["FORBIDDEN"],
            })
            pnl = {
                "date": "20260101",
                "variant": config.primary_variant,
                "paper_execution_status": "FORBIDDEN",
                "live_trading_status": "FORBIDDEN",
            }
            stats = {
                "date": "20260101",
                "variant": config.primary_variant,
                "active_warning_gates": [],
                "active_stop_gates": [],
                "review_006b_trigger_ready": False,
                "paper_execution_status": "FORBIDDEN",
                "live_trading_status": "FORBIDDEN",
            }
            summary = dict(stats)
            write_track_outputs(base, "20260101", positions, pnl, stats, summary)

            self.assertTrue(output_flags_present(base, "20260101"))
            written = json.loads((base / "20260101_pnl.json").read_text(encoding="utf-8"))
            self.assertIn("reproducibility", written)

    def test_no_order_endpoint_scan_passes_forward_record_sources(self) -> None:
        scan = scan_no_order_endpoints([Path("apps/forward_record"), Path("scripts/run_forward_record.py")])
        self.assertEqual(scan["status"], "PASS")
        self.assertEqual(scan["violations"], [])


if __name__ == "__main__":
    unittest.main()

