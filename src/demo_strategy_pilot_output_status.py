"""TASK-014BT -- output-delivery status ledger for the demo pilot daily runner.

Strictly OFFLINE. Records the *effective* Excel / Notion / Discord delivery
statuses for a pilot/date WITHOUT mutating or duplicating authoritative trading
data (signal/order/fill/trade/PnL/position). The immutable daily record stays
single; only output-delivery statuses may advance.

Canonical runtime files (outside Git):
    outputs/demo_trading/pilot/<pilot_id>/
        output_status_events.jsonl   (append-only)
        latest_output_status.json    (atomic)

No network, no secrets, no order endpoints.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
from dataclasses import dataclass
from typing import Any, Mapping

from src.demo_strategy_pilot_store import CANONICAL_PILOT_ROOT

OUTPUT_STATUS_EVENTS_FILENAME = "output_status_events.jsonl"
LATEST_OUTPUT_STATUS_FILENAME = "latest_output_status.json"

STATUS_PENDING = "PENDING"
STATUS_OK = "OK"
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_SKIPPED = "SKIPPED"
ALLOWED_STATUSES = frozenset({STATUS_PENDING, STATUS_OK, STATUS_PASS, STATUS_FAIL, STATUS_SKIPPED})

# Daily-record fields that form the immutable trading core. Output
# reconciliation refuses if any of these change.
IMMUTABLE_DAILY_CORE_FIELDS = (
    "date",
    "signal_count",
    "order_count",
    "filled_count",
    "closed_trade_count",
    "realized_pnl_usdt",
    "trading_fees_usdt",
    "funding_pnl_usdt",
    "daily_net_pnl_usdt",
    "cumulative_net_pnl_usdt",
    "daily_return_pct",
    "cumulative_return_pct",
    "max_drawdown_pct",
    "current_position_symbol",
    "current_position_side",
    "current_position_qty",
)


class OutputStatusError(Exception):
    """Base error for the output-status ledger."""


class InvalidStatusError(OutputStatusError):
    """A status value outside the allowed set was supplied."""


class MalformedStatusLedgerError(OutputStatusError):
    """An existing status ledger file is malformed."""


class ImmutableDailyCoreConflict(OutputStatusError):
    """A reconcile attempted to change immutable daily-core trading data."""


def _validate(status: str, field: str) -> str:
    if status not in ALLOWED_STATUSES:
        raise InvalidStatusError(f"invalid {field} status {status!r}; allowed {sorted(ALLOWED_STATUSES)}")
    return status


def compute_daily_core_fingerprint(
    *,
    pilot_id: str,
    daily_record: Mapping[str, Any],
    input_fingerprint: str,
    plan_fingerprint: str,
) -> str:
    """Deterministic SHA-256 over the immutable daily trading core + fingerprints."""
    core = {"pilot_id": pilot_id, "input_fingerprint": input_fingerprint,
            "plan_fingerprint": plan_fingerprint}
    for f in IMMUTABLE_DAILY_CORE_FIELDS:
        core[f] = daily_record.get(f)
    text = json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OutputStatusRecord:
    pilot_id: str
    date: str
    excel_status: str
    notion_status: str
    discord_status: str
    excel_detail: str
    notion_detail: str
    discord_detail: str
    updated_at_utc: str
    plan_fingerprint: str
    input_fingerprint: str
    daily_core_fingerprint: str = ""

    def __post_init__(self) -> None:
        _validate(self.excel_status, "excel")
        _validate(self.notion_status, "notion")
        _validate(self.discord_status, "discord")

    def effective_key(self) -> tuple:
        return (self.excel_status, self.notion_status, self.discord_status,
                self.plan_fingerprint, self.input_fingerprint, self.daily_core_fingerprint)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pilot_id": self.pilot_id,
            "date": self.date,
            "excel_status": self.excel_status,
            "notion_status": self.notion_status,
            "discord_status": self.discord_status,
            "excel_detail": self.excel_detail,
            "notion_detail": self.notion_detail,
            "discord_detail": self.discord_detail,
            "updated_at_utc": self.updated_at_utc,
            "plan_fingerprint": self.plan_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "daily_core_fingerprint": self.daily_core_fingerprint,
        }


class OutputStatusStore:
    """Append-only output-status ledger; atomic latest snapshot."""

    def __init__(self, pilot_id: str, output_root: str | os.PathLike[str] | None = None) -> None:
        root = pathlib.Path(output_root) if output_root is not None else CANONICAL_PILOT_ROOT
        self.pilot_id = pilot_id
        self.dir = pathlib.Path(root) / pilot_id
        self.events_path = self.dir / OUTPUT_STATUS_EVENTS_FILENAME
        self.latest_path = self.dir / LATEST_OUTPUT_STATUS_FILENAME

    def _ensure_dir(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)

    def read_events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with open(self.events_path, "r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise MalformedStatusLedgerError(
                        f"malformed status ledger {self.events_path} at line {lineno}: {exc}") from exc
        return rows

    def read_latest(self) -> dict[str, Any] | None:
        if not self.latest_path.exists():
            return None
        try:
            with open(self.latest_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError as exc:
            raise MalformedStatusLedgerError(f"malformed latest status {self.latest_path}: {exc}") from exc

    def latest_by_date(self) -> dict[str, dict[str, Any]]:
        """Return {date: most-recent status event} from the append-only log."""
        out: dict[str, dict[str, Any]] = {}
        for ev in self.read_events():
            out[str(ev.get("date"))] = ev
        return out

    def _atomic_write(self, path: pathlib.Path, text: str) -> None:
        self._ensure_dir()
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def record_status(self, record: OutputStatusRecord) -> tuple[dict[str, Any], bool]:
        """Append a status event (idempotent on identical effective status) and
        write the atomic latest snapshot. Returns (data, appended)."""
        data = record.to_dict()
        events = self.read_events()
        appended = False
        if not events or tuple(
            events[-1].get(k) for k in ("excel_status", "notion_status", "discord_status",
                                        "plan_fingerprint", "input_fingerprint", "daily_core_fingerprint")
        ) != record.effective_key() or str(events[-1].get("date")) != record.date:
            self._ensure_dir()
            with open(self.events_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            appended = True
        self._atomic_write(self.latest_path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
        return data, appended

    def assert_immutable_core_unchanged(self, *, date: str, expected_core_fp: str) -> None:
        """Refuse if the recorded immutable daily-core fingerprint for ``date``
        differs from ``expected_core_fp``."""
        by_date = self.latest_by_date()
        ev = by_date.get(date)
        if ev is None:
            return
        recorded = str(ev.get("daily_core_fingerprint", ""))
        if recorded and recorded != expected_core_fp:
            raise ImmutableDailyCoreConflict(
                f"immutable daily-core fingerprint changed for {date}: "
                f"recorded={recorded[:12]} expected={expected_core_fp[:12]}")


__all__ = [
    "ALLOWED_STATUSES",
    "IMMUTABLE_DAILY_CORE_FIELDS",
    "ImmutableDailyCoreConflict",
    "InvalidStatusError",
    "LATEST_OUTPUT_STATUS_FILENAME",
    "MalformedStatusLedgerError",
    "OUTPUT_STATUS_EVENTS_FILENAME",
    "OutputStatusError",
    "OutputStatusRecord",
    "OutputStatusStore",
    "STATUS_FAIL",
    "STATUS_OK",
    "STATUS_PASS",
    "STATUS_PENDING",
    "STATUS_SKIPPED",
    "compute_daily_core_fingerprint",
]
