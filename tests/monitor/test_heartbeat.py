from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apps.monitor.config import MonitorConfig
from apps.monitor.heartbeat import hook_event_from_heartbeat, sample_heartbeat, write_heartbeat_parquet
from apps.monitor.schema import validate_heartbeat_parquet, validate_heartbeat_rows


class HeartbeatTest(unittest.TestCase):
    def test_sample_heartbeat_matches_schema(self) -> None:
        config = MonitorConfig()
        row = sample_heartbeat(config, timestamp="2026-05-17T00:00:00Z")
        result = validate_heartbeat_rows([row])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(row["paper_execution_status"], "FORBIDDEN")
        self.assertEqual(row["live_trading_status"], "FORBIDDEN")

    def test_heartbeat_parquet_roundtrip(self) -> None:
        config = MonitorConfig()
        row = sample_heartbeat(config, timestamp="2026-05-17T00:00:00Z")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "heartbeat.parquet"
            write_heartbeat_parquet(path, [row])
            result = validate_heartbeat_parquet(path)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["row_count"], 1)

    def test_monitor_hook_event_is_local_payload(self) -> None:
        config = MonitorConfig()
        row = sample_heartbeat(config, timestamp="2026-05-17T00:00:00Z")
        event = hook_event_from_heartbeat(row)
        self.assertEqual(event["source"], "task005_monitor_sample")
        self.assertEqual(event["event_type"], "heartbeat")
        self.assertEqual(event["status"], "OK")


if __name__ == "__main__":
    unittest.main()
