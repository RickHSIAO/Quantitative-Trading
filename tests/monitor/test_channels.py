from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from apps.monitor.alerts import make_sample_alert
from apps.monitor.channels import dispatch_alerts
from apps.monitor.channels.base import DefaultHttpClient, HttpResult
from apps.monitor.channels.discord import send_discord_alerts
from apps.monitor.channels.redaction import redact_text
from apps.monitor.channels.telegram import send_telegram_alerts
from apps.monitor.config import AlertsConfig, ChannelConfig, MonitorConfig
from apps.monitor.safety import scan_monitor_safety


class FakeHttpClient:
    def __init__(
        self,
        status_code: int = 200,
        fail: bool = False,
        text: str = "ok",
        exception_message: str = "mock failure",
    ) -> None:
        self.status_code = status_code
        self.fail = fail
        self.text = text
        self.exception_message = exception_message
        self.calls: list[dict[str, Any]] = []

    def post_json(self, url: str, payload: dict[str, Any], timeout_seconds: int) -> HttpResult:
        self.calls.append({"url": url, "payload": payload, "timeout_seconds": timeout_seconds})
        if self.fail:
            raise RuntimeError(self.exception_message)
        return HttpResult(status_code=self.status_code, text=self.text)


class FakeUrlopenResponse:
    status = 204

    def __enter__(self) -> "FakeUrlopenResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return b""


def _alert(config: MonitorConfig):
    return make_sample_alert(config, timestamp="2026-05-17T00:00:00Z")


class ChannelTest(unittest.TestCase):
    def test_default_http_client_sends_json_headers(self) -> None:
        captured: dict[str, Any] = {}

        def fake_urlopen(request: Any, timeout: int) -> FakeUrlopenResponse:
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeUrlopenResponse()

        with patch("apps.monitor.channels.base.urllib.request.urlopen", side_effect=fake_urlopen):
            result = DefaultHttpClient().post_json("https://example.invalid/webhook", {"content": "unit"}, 7)

        self.assertEqual(result.status_code, 204)
        self.assertEqual(captured["timeout"], 7)
        request = captured["request"]
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(headers["accept"], "application/json")
        self.assertEqual(headers["user-agent"], "QuantMonitor/1.0")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.data.decode("utf-8"), '{"content": "unit"}')

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

    def test_discord_204_is_sent(self) -> None:
        config = MonitorConfig()
        channel = ChannelConfig(
            type="discord",
            enabled=True,
            dry_run=False,
            secrets_env_webhook_url="MONITOR_DISCORD_WEBHOOK_URL",
        )
        client = FakeHttpClient(status_code=204, text="")
        env = {"MONITOR_DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123456/unit-webhook"}
        result = send_discord_alerts(config, channel, [_alert(config)], http_client=client, test_send=True, environ=env)
        self.assertEqual(result.status, "SENT")
        self.assertTrue(result.external_post_attempted)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(result.delivered_count, 1)
        self.assertIn("content", client.calls[0]["payload"])
        self.assertTrue(client.calls[0]["payload"]["content"])
        self.assertNotIn(env["MONITOR_DISCORD_WEBHOOK_URL"], str(result.to_dict()))

    def test_discord_200_is_sent(self) -> None:
        config = MonitorConfig()
        channel = ChannelConfig(
            type="discord",
            enabled=True,
            dry_run=False,
            secrets_env_webhook_url="MONITOR_DISCORD_WEBHOOK_URL",
        )
        client = FakeHttpClient(status_code=200)
        env = {"MONITOR_DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123456/unit-webhook"}
        result = send_discord_alerts(config, channel, [_alert(config)], http_client=client, test_send=True, environ=env)
        self.assertEqual(result.status, "SENT")
        self.assertEqual(result.delivered_count, 1)
        self.assertEqual(result.error_count, 0)

    def test_discord_4xx_and_5xx_are_failed(self) -> None:
        config = MonitorConfig()
        channel = ChannelConfig(
            type="discord",
            enabled=True,
            dry_run=False,
            secrets_env_webhook_url="MONITOR_DISCORD_WEBHOOK_URL",
        )
        env = {"MONITOR_DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123456/unit-webhook"}
        for status_code in (400, 500):
            with self.subTest(status_code=status_code):
                client = FakeHttpClient(status_code=status_code)
                result = send_discord_alerts(
                    config,
                    channel,
                    [_alert(config)],
                    http_client=client,
                    test_send=True,
                    environ=env,
                )
                self.assertEqual(result.status, "FAILED")
                self.assertEqual(result.delivered_count, 0)
                self.assertEqual(result.error_count, 1)
                self.assertNotIn(env["MONITOR_DISCORD_WEBHOOK_URL"], str(result.to_dict()))

    def test_discord_exception_diagnostic_is_redacted(self) -> None:
        config = MonitorConfig()
        channel = ChannelConfig(
            type="discord",
            enabled=True,
            dry_run=False,
            secrets_env_webhook_url="MONITOR_DISCORD_WEBHOOK_URL",
        )
        webhook = "https://discord.com/api/webhooks/123456/unit-webhook"
        client = FakeHttpClient(fail=True, exception_message=f"failed posting to {webhook}")
        result = send_discord_alerts(
            config,
            channel,
            [_alert(config)],
            http_client=client,
            test_send=True,
            environ={"MONITOR_DISCORD_WEBHOOK_URL": webhook},
        )
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.diagnostics["errors"][0]["exception_class"], "RuntimeError")
        self.assertIn("<redacted>", result.diagnostics["errors"][0]["exception_message"])
        self.assertNotIn(webhook, str(result.to_dict()))

    def test_discord_4xx_diagnostic_is_redacted(self) -> None:
        config = MonitorConfig()
        channel = ChannelConfig(
            type="discord",
            enabled=True,
            dry_run=False,
            secrets_env_webhook_url="MONITOR_DISCORD_WEBHOOK_URL",
        )
        webhook = "https://discord.com/api/webhooks/123456/unit-webhook"
        client = FakeHttpClient(status_code=400, text=f"bad webhook {webhook}")
        result = send_discord_alerts(
            config,
            channel,
            [_alert(config)],
            http_client=client,
            test_send=True,
            environ={"MONITOR_DISCORD_WEBHOOK_URL": webhook},
        )
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.diagnostics["errors"][0]["http_status"], 400)
        self.assertIn("<redacted>", result.diagnostics["errors"][0]["response_text_preview"])
        self.assertNotIn(webhook, str(result.to_dict()))

    def test_discord_403_cloudflare_diagnostic_is_redacted(self) -> None:
        config = MonitorConfig()
        channel = ChannelConfig(
            type="discord",
            enabled=True,
            dry_run=False,
            secrets_env_webhook_url="MONITOR_DISCORD_WEBHOOK_URL",
        )
        webhook = "https://discord.com/api/webhooks/123456/unit-webhook"
        client = FakeHttpClient(status_code=403, text=f"error code: 1010 for {webhook}")
        result = send_discord_alerts(
            config,
            channel,
            [_alert(config)],
            http_client=client,
            test_send=True,
            environ={"MONITOR_DISCORD_WEBHOOK_URL": webhook},
        )
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.diagnostics["errors"][0]["http_status"], 403)
        self.assertIn("error code: 1010", result.diagnostics["errors"][0]["response_text_preview"])
        self.assertNotIn(webhook, str(result.to_dict()))

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
