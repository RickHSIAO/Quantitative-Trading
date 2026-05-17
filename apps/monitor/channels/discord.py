from __future__ import annotations

from collections.abc import Mapping

from apps.monitor.alerts import Alert
from apps.monitor.config import ChannelConfig, MonitorConfig

from .base import ChannelResult, DefaultHttpClient, HttpClient, format_alert_message
from .redaction import redacted_discord_endpoint
from .secrets import load_channel_secrets


def send_discord_alerts(
    config: MonitorConfig,
    channel: ChannelConfig,
    alerts: list[Alert],
    http_client: HttpClient | None = None,
    test_send: bool = False,
    environ: Mapping[str, str] | None = None,
) -> ChannelResult:
    if not channel.enabled:
        return ChannelResult(
            channel="discord",
            enabled=False,
            dry_run=channel.dry_run,
            test_send=test_send,
            status="SKIPPED",
            detail="discord disabled",
            endpoint=redacted_discord_endpoint(),
        )
    if channel.dry_run:
        return ChannelResult(
            channel="discord",
            enabled=True,
            dry_run=True,
            test_send=test_send,
            status="DRY_RUN",
            detail="would send Discord alerts; no POST attempted",
            delivered_count=len(alerts),
            external_post_attempted=False,
            endpoint=redacted_discord_endpoint(),
        )

    secrets = load_channel_secrets(channel, environ=environ)
    if not secrets.discord_webhook_url:
        return ChannelResult(
            channel="discord",
            enabled=True,
            dry_run=False,
            test_send=test_send,
            status="FAILED",
            detail="missing Discord webhook URL",
            error_count=len(alerts) or 1,
            external_post_attempted=False,
            endpoint=redacted_discord_endpoint(),
        )

    client = http_client or DefaultHttpClient()
    delivered = 0
    errors = 0
    for alert in alerts:
        payload = {"content": format_alert_message(alert, config.bot_name)}
        try:
            response = client.post_json(secrets.discord_webhook_url, payload, channel.timeout_seconds)
        except Exception:
            errors += 1
            continue
        if 200 <= response.status_code < 300:
            delivered += 1
        else:
            errors += 1
    return ChannelResult(
        channel="discord",
        enabled=True,
        dry_run=False,
        test_send=test_send,
        status="SENT" if errors == 0 else "FAILED",
        detail="Discord dispatch completed" if errors == 0 else "Discord dispatch had errors",
        delivered_count=delivered,
        error_count=errors,
        external_post_attempted=True,
        endpoint=redacted_discord_endpoint(),
    )
