from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from apps.monitor.alerts import Alert
from apps.monitor.config import MonitorConfig

from .base import ChannelResult, HttpClient
from .discord import send_discord_alerts
from .local_jsonl import send_local_jsonl
from .telegram import send_telegram_alerts


def dispatch_alerts(
    config: MonitorConfig,
    alerts: list[Alert],
    local_jsonl_path: Path,
    test_send: bool = False,
    http_client: HttpClient | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[ChannelResult]:
    results: list[ChannelResult] = []
    for channel in config.alerts.channels:
        channel_type = channel.type.lower()
        if channel_type == "local_jsonl":
            results.append(send_local_jsonl(local_jsonl_path, alerts, channel, test_send=test_send))
        elif channel_type == "telegram":
            results.append(
                send_telegram_alerts(
                    config,
                    channel,
                    alerts,
                    http_client=http_client,
                    test_send=test_send,
                    environ=environ,
                )
            )
        elif channel_type == "discord":
            results.append(
                send_discord_alerts(
                    config,
                    channel,
                    alerts,
                    http_client=http_client,
                    test_send=test_send,
                    environ=environ,
                )
            )
        else:
            results.append(
                ChannelResult(
                    channel=channel.type,
                    enabled=channel.enabled,
                    dry_run=channel.dry_run,
                    test_send=test_send,
                    status="SKIPPED",
                    detail="unknown channel type",
                )
            )
    return results


__all__ = [
    "ChannelResult",
    "dispatch_alerts",
    "send_discord_alerts",
    "send_local_jsonl",
    "send_telegram_alerts",
]
