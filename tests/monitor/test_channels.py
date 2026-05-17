from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from apps.monitor.alerts import make_sample_alert
from apps.monitor.channels import dispatch_alerts
from apps.monitor.channels.base import HttpResult
from apps.monitor.channels.discord import send_discord_alerts
from apps.monitor.channels.redaction import redact_text
from apps.monitor.channels.telegram import send_telegram_alerts
from apps.monitor.config import AlertsConfig, ChannelConfig, MonitorConfig
from apps.monitor.safety import scan_monitor_safety


class FakeHttpClient:
    def __init__(self, status_code: int = 200, fail: bool = False) -> None:
        self.status_code = status_code
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def post_json(self, url: str, payload: dict[str, Any], timeout_seconds: int) -> HttpResult:
        self.calls.append({"url": url, "payload": payload, "timeout_seconds": timeout_seconds})
        if self.fail:
            raise RuntimeError("mock failure")
        return HttpResult(status_code=self.status_code, text="ok")


def _alert(config: MonitorConfig):
    return make_sample_alert(config, timestamp="2026-05-17T00:00:00Z")


class ChannelTest(unittest.TestCase):
    def test_telegram_dry_run_does_not_post(self) -> None:
        config = MonitorConfig()
        channel = ChannelConfig(type="telegram", enabled=True, dry_run=True)
        client = FakeHttpClient()
        result = send_telegram_alerts(config, channel, [_alert(config)], http_client=client)
        self.assertEqual(result.status, "DRY_RUN")
        self.assertFalse(result.external_post_attempted)
        self.assertEqual(client.calls, [])

    def test_telegram_test_send_uses_mock_client(self) -> None:
        config = MonitorConfig()
        channel = ChannelConfig(
            type="telegram",
            enabled=True,
            dry_run=False,
            secrets_env_token="MONITOR_TELEGRAM_TOKEN",
            secrets_env_chat_id="MONITOR_TELEGRAM_CHAT_ID",
        )
        client = FakeHttpClient()
        env = {"MONITOR_TELEGRAM_TOKEN": "unit-token", "MONITOR_TELEGRAM_CHAT_ID": "unit-chat"}
        result = send_telegram_alerts(config, channel, [_alert(config)], http_client=client, test_send=True, environ=env)
        self.assertEqual(result.status, "SENT")
        self.assertTrue(result.external_post_attempted)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["payload"]["chat_id"], "unit-chat")

    def test_discord_dry_run_does_not_post(self) -> None:
        config = MonitorConfig()
        channel = ChannelConfig(type="discord", enabled=True, dry_run=True)
        client = FakeHttpClient()
        result = send_discord_alerts(config, channel, [_alert(config)], http_client=client)
        self.assertEqual(result.status, "DRY_RUN")
        self.assertFalse(result.external_post_attempted)
        self.assertEqual(client.calls, [])

    def test_discord_test_send_uses_mock_client(self) -> None:
        config = MonitorConfig()
        channel = ChannelConfig(
            type="discord",
            enabled=True,
            dry_run=False,
            secrets_env_webhook_url="MONITOR_DISCORD_WEBHOOK_URL",
        )
        client = FakeHttpClient()
        env = {"MONITOR_DISCORD_WEBHOOK_URL": "https://example.invalid/unit-webhook"}
        result = send_discord_alerts(config, channel, [_alert(config)], http_client=client, test_send=True, environ=env)
        self.assertEqual(result.status, "SENT")
        self.assertTrue(result.external_post_attempted)
        self.assertEqual(len(client.calls), 1)
        self.assertIn("content", client.calls[0]["payload"])

    def test_channel_failure_keeps_local_jsonl(self) -> None:
        channels = (
            ChannelConfig(type="local_jsonl", enabled=True, dry_run=True),
            ChannelConfig(
                type="telegram",
                enabled=True,
                dry_run=False,
                secrets_env_token="MONITOR_TELEGRAM_TOKEN",
                secrets_env_chat_id="MONITOR_TELEGRAM_CHAT_ID",
            ),
        )
        config = MonitorConfig(alerts=AlertsConfig(channels=channels))
        client = FakeHttpClient(fail=True)
        env = {"MONITOR_TELEGRAM_TOKEN": "unit-token", "MONITOR_TELEGRAM_CHAT_ID": "unit-chat"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alerts.jsonl"
            results = dispatch_alerts(config, [_alert(config)], path, http_client=client, environ=env)
            self.assertTrue(path.exists())
        self.assertEqual(results[0].status, "WRITTEN")
        self.assertEqual(results[1].status, "FAILED")

    def test_secret_redaction(self) -> None:
        text = "token=unit-token webhook=https://discord.com/api/webhooks/123456/abcdef"
        redacted = redact_text(text, ["unit-token"])
        self.assertNotIn("unit-token", redacted)
        self.assertNotIn("123456/abcdef", redacted)

    def test_monitor_safety_scan_passes(self) -> None:
        scan = scan_monitor_safety(Path(".").resolve())
        self.assertEqual(scan["status"], "PASS")
        self.assertFalse(scan["gates"]["local_jsonl_removed"])


if __name__ == "__main__":
    unittest.main()
