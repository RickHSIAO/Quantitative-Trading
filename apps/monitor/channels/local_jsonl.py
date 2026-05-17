from __future__ import annotations

from pathlib import Path

from apps.monitor.alerts import Alert, write_alerts_jsonl
from apps.monitor.config import ChannelConfig

from .base import ChannelResult


def send_local_jsonl(
    path: Path,
    alerts: list[Alert],
    channel: ChannelConfig,
    test_send: bool = False,
) -> ChannelResult:
    if not channel.enabled:
        return ChannelResult(
            channel="local_jsonl",
            enabled=False,
            dry_run=channel.dry_run,
            test_send=test_send,
            status="SKIPPED",
            detail="local_jsonl disabled",
        )
    write_alerts_jsonl(path, alerts)
    return ChannelResult(
        channel="local_jsonl",
        enabled=True,
        dry_run=channel.dry_run,
        test_send=test_send,
        status="WRITTEN",
        detail="alerts JSONL written",
        delivered_count=len(alerts),
        external_post_attempted=False,
        endpoint=str(path),
    )
