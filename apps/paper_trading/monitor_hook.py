from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PaperTradingMonitorHook:
    """TASK-005 local interface stub.

    Methods return event dictionaries only. The hook has no transport,
    credentials, exchange client, or external side effect.
    """

    source: str = "task006_offline_planning"

    def push_heartbeat(self, timestamp: str, nav_usd: float, status: str) -> dict[str, Any]:
        return {
            "source": self.source,
            "event_type": "heartbeat",
            "timestamp": timestamp,
            "nav_usd": float(nav_usd),
            "status": status,
        }

    def push_risk_event(self, event_type: str, severity: str, details: dict[str, Any]) -> dict[str, Any]:
        return {
            "source": self.source,
            "event_type": event_type,
            "severity": severity,
            "details": dict(details),
        }

    def push_rebalance_summary(
        self,
        date: str,
        n_longs: int,
        n_shorts: int,
        gross_exposure: float,
        net_exposure: float,
    ) -> dict[str, Any]:
        return {
            "source": self.source,
            "event_type": "rebalance_summary",
            "date": date,
            "n_longs": int(n_longs),
            "n_shorts": int(n_shorts),
            "gross_exposure": float(gross_exposure),
            "net_exposure": float(net_exposure),
        }
