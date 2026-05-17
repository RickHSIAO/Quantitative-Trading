from __future__ import annotations

import glob
import hashlib
from pathlib import Path

from apps.monitor.alerts import Alert, make_alert
from apps.monitor.config import MonitorConfig


ERROR_MARKERS = ("ERROR", "CRITICAL", "EXCEPTION")


def scan_logs(config: MonitorConfig, timestamp: str) -> list[Alert]:
    alerts: list[Alert] = []
    for pattern in config.logging.bot_log_paths:
        for path_text in glob.glob(pattern):
            path = Path(path_text)
            if not path.is_file():
                continue
            alerts.extend(_scan_log_file(path, config, timestamp))
    return alerts


def _scan_log_file(path: Path, config: MonitorConfig, timestamp: str) -> list[Alert]:
    alerts: list[Alert] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        upper = line.upper()
        if not any(marker in upper for marker in ERROR_MARKERS):
            continue
        digest = hashlib.sha256(line.encode("utf-8", errors="replace")).hexdigest()[:16]
        alerts.append(make_alert(
            category="LOG_ERROR",
            severity="WARNING",
            message=f"{path.name}: {line[:180]}",
            source=f"log:{path}",
            config=config,
            action_required="inspect_bot_log",
            timestamp=timestamp,
        ))
        alerts[-1] = Alert(
            **{
                **alerts[-1].to_dict(),
                "dedupe_key": f"LOG_ERROR:{digest}",
            }
        )
    return alerts
