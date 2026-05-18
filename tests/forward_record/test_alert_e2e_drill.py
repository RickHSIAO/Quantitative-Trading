from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from apps.forward_record.safety import scan_no_order_endpoints
from scripts.drill_forward_alerts import run_drill


class ForwardAlertE2EDrillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.tmp.name)
        cls.report = run_drill(
            "20260517",
            output_dir=cls.base / "drill",
            write_review=False,
        )
        cls.scenarios = {item["scenario_id"]: item for item in cls.report["scenarios"]}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_s_a1_trigger(self) -> None:
        item = self.scenarios["S-A1"]
        self.assertTrue(item["triggered"])
        self.assertEqual(item["result"], "PASS")

    def test_s_a1b_no_trigger(self) -> None:
        item = self.scenarios["S-A1b"]
        self.assertFalse(item["triggered"])
        self.assertEqual(item["result"], "PASS")

    def test_s_a2_trigger(self) -> None:
        item = self.scenarios["S-A2"]
        self.assertTrue(item["triggered"])
        self.assertEqual(item["severity"], "CRITICAL")

    def test_s_a3_trigger(self) -> None:
        item = self.scenarios["S-A3"]
        self.assertTrue(item["triggered"])
        self.assertEqual(item["data"]["streak_gates"], ["W-1"])

    def test_s_a3b_no_trigger(self) -> None:
        item = self.scenarios["S-A3b"]
        self.assertFalse(item["triggered"])

    def test_s_a4_trigger(self) -> None:
        item = self.scenarios["S-A4"]
        self.assertTrue(item["triggered"])
        self.assertGreater(item["data"]["mean_abs_diff"], 0.05)

    def test_s_a4b_skip(self) -> None:
        item = self.scenarios["S-A4b"]
        self.assertFalse(item["triggered"])
        self.assertTrue(item["data"]["skipped"])

    def test_s_a5_trigger_missing(self) -> None:
        item = self.scenarios["S-A5"]
        self.assertTrue(item["triggered"])
        self.assertIn("missing forward_stats", item["message_preview"])

    def test_s_a5b_trigger_failed(self) -> None:
        item = self.scenarios["S-A5b"]
        self.assertTrue(item["triggered"])
        self.assertIn("data_source=FAILED", item["message_preview"])

    def test_s_a5c_no_trigger_on_cache_provider_log(self) -> None:
        item = self.scenarios["S-A5c"]
        self.assertFalse(item["triggered"])
        self.assertEqual(item["result"], "PASS")
        self.assertIn("data source readable", item["message_preview"])

    def test_s_a6_trigger_first_day(self) -> None:
        item = self.scenarios["S-A6"]
        self.assertTrue(item["triggered"])
        self.assertEqual(item["severity"], "INFO")

    def test_s_a6b_dedupe(self) -> None:
        item = self.scenarios["S-A6b"]
        self.assertFalse(item["triggered"])
        self.assertTrue(item["data"]["duplicate"])
        self.assertEqual(self.report["dedupe_scenario"]["result"], "PASS")

    def test_s_a7_trigger(self) -> None:
        item = self.scenarios["S-A7"]
        self.assertTrue(item["triggered"])
        self.assertEqual(item["severity"], "CRITICAL")

    def test_redaction_all_scenarios(self) -> None:
        self.assertTrue(self.report["redaction_summary"]["all_pass"])
        for item in self.report["scenarios"]:
            self.assertTrue(item["redaction_pass"], item["scenario_id"])

    def test_discord_channel_result_dry_run(self) -> None:
        probe = self.report["discord_probe"]
        self.assertTrue(probe["dry_run"])
        self.assertEqual(probe["statuses"], ["DRY_RUN"])
        self.assertFalse(probe["external_post_attempted"])
        self.assertFalse(probe["sent_seen"])

    def test_drill_report_written(self) -> None:
        path = Path(self.report["drill_report_path"])
        self.assertTrue(path.exists())
        written = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(written["overall_result"], "PASS")
        self.assertEqual(written["scenario_count"] if "scenario_count" in written else len(written["scenarios"]), 13)

    def test_forbidden_fields_all_not_attempted(self) -> None:
        self.assertEqual(self.report["FORBIDDEN_live_trading"], "NOT_ATTEMPTED")
        self.assertEqual(self.report["FORBIDDEN_order_endpoint"], "NOT_ATTEMPTED")
        self.assertEqual(self.report["FORBIDDEN_bybit_write"], "NOT_ATTEMPTED")
        self.assertEqual(self.report["FORBIDDEN_real_discord_post"], "NOT_ATTEMPTED")
        self.assertFalse(self.report["clock_started"])

    def test_a6_no_paper_approval_language(self) -> None:
        preview = self.scenarios["S-A6"]["message_preview"].lower()
        self.assertNotIn("paper execution approved", preview)
        self.assertNotIn("live trading approved", preview)

    def test_no_import_order_endpoints(self) -> None:
        scan = scan_no_order_endpoints([Path("scripts/drill_forward_alerts.py")])
        self.assertEqual(scan["status"], "PASS")
        self.assertEqual(scan["violations"], [])

    def test_s_a5c_no_trigger_on_cache_provider_log(self) -> None:
        item = self.scenarios["S-A5c"]
        self.assertFalse(item["triggered"])
        self.assertEqual(item["result"], "PASS")

    def test_no_placeholder_raw_all_scenarios(self) -> None:
        for item in self.report["scenarios"]:
            self.assertTrue(
                item["content_checks"]["no_placeholder_raw"],
                f"{item['scenario_id']} has raw None placeholder",
            )

    def test_raw_content_has_action_all_scenarios(self) -> None:
        for item in self.report["scenarios"]:
            self.assertTrue(
                item["content_checks"]["raw_content"]["has_action_in_raw"],
                f"{item['scenario_id']} raw content missing action_required",
            )


if __name__ == "__main__":
    unittest.main()
