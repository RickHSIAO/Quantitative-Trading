from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apps.monitor.alerts import dedupe_alerts, make_alert, make_sample_alert, write_alerts_jsonl
from apps.monitor.config import MonitorConfig
from apps.monitor.safety import check_secret_ignore, scan_monitor_safety
from apps.monitor.schema import validate_alert_rows, validate_alerts_jsonl


class AlertsTest(unittest.TestCase):
    def test_alert_schema_and_dedupe(self) -> None:
        config = MonitorConfig()
        first = make_alert(
            category="LOG_ERROR",
            severity="WARNING",
            message="sample",
            source="unit",
            config=config,
            timestamp="2026-05-17T00:00:00Z",
        )
        second = make_alert(
            category="LOG_ERROR",
            severity="WARNING",
            message="same source",
            source="unit",
            config=config,
            timestamp="2026-05-17T00:01:00Z",
        )
        alerts = dedupe_alerts([first, second])
        self.assertEqual(len(alerts), 1)
        result = validate_alert_rows([alert.to_dict() for alert in alerts])
        self.assertEqual(result["status"], "PASS")

    def test_alert_jsonl_roundtrip(self) -> None:
        config = MonitorConfig()
        alert = make_sample_alert(config, timestamp="2026-05-17T00:00:00Z")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alerts.jsonl"
            write_alerts_jsonl(path, [alert])
            result = validate_alerts_jsonl(path)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["row_count"], 1)

    def test_secret_ignore_and_safety_scan_pass(self) -> None:
        root = Path(".").resolve()
        self.assertEqual(check_secret_ignore(root)["status"], "PASS")
        scan = scan_monitor_safety(root)
        self.assertEqual(scan["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
