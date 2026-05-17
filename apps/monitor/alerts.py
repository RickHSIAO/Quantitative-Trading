from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apps.monitor.config import MonitorConfig


@dataclass(frozen=True)
class Alert:
    timestamp: str
    severity: str
    category: str
    message: str
    dedupe_key: str
    source: str
    action_required: str
    paper_execution_status: str
    live_trading_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_alert(
    category: str,
    severity: str,
    message: str,
    source: str,
    config: MonitorConfig,
    action_required: str = "review_monitor_output",
    timestamp: str | None = None,
) -> Alert:
    ts = timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return Alert(
        timestamp=ts,
        severity=severity,
        category=category,
        message=message,
        dedupe_key=f"{category}:{source}",
        source=source,
        action_required=action_required,
        paper_execution_status=config.paper_execution_status,
        live_trading_status=config.live_trading_status,
    )


def make_sample_alert(config: MonitorConfig, timestamp: str) -> Alert:
    return make_alert(
        category="MONITOR_SAMPLE",
        severity="INFO",
        message="Sample local monitor alert; no external notification was sent.",
        source="task005_sample",
        config=config,
        action_required="none_sample_only",
        timestamp=timestamp,
    )


def dedupe_alerts(alerts: list[Alert]) -> list[Alert]:
    seen: set[str] = set()
    out: list[Alert] = []
    for alert in alerts:
        if alert.dedupe_key in seen:
            continue
        seen.add(alert.dedupe_key)
        out.append(alert)
    return out


def write_alerts_jsonl(path: Path, alerts: list[Alert]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(alert.to_dict(), sort_keys=True, ensure_ascii=False) + "\n" for alert in alerts),
        encoding="utf-8",
    )


def summarize_alerts(alerts: list[Alert]) -> dict[str, int]:
    counts = {"INFO": 0, "WARNING": 0, "CRITICAL": 0}
    for alert in alerts:
        counts[alert.severity] = counts.get(alert.severity, 0) + 1
    return counts
