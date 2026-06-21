"""TASK-014BQ -- append-only local store for demo strategy pilot reporting.

Strictly OFFLINE. Stores pilot config, daily records, trade records, and audit
events under a canonical runtime directory OUTSIDE source control:

    outputs/demo_trading/pilot/<pilot_id>/
        pilot_config.json       (atomic write)
        daily_records.jsonl     (append-only)
        trade_records.jsonl     (append-only)
        audit_events.jsonl      (append-only)
        latest_summary.json     (atomic write)

Guarantees:
  * append-only JSONL for daily / trades / audit
  * atomic write (tmp + os.replace + fsync) for config and latest summary
  * UTF-8, deterministic serialization, Decimal serialized as strings
  * duplicate daily date fails closed (unless explicit idempotent upsert)
  * duplicate trade_id fails closed
  * no automatic deletion / overwrite of historical records
  * malformed existing JSONL raises a clear error
  * no network, no secrets

Does not import the live order-execution stack (main, the risk module, or the
live Bybit executor module) and imports no network client.
"""

from __future__ import annotations

import json
import os
import pathlib
from typing import Any, Iterable, Mapping

from src.demo_strategy_pilot_reporting import (
    PROJECT_ROOT,
    PilotAuditEvent,
    PilotConfig,
    PilotDailyRecord,
    PilotTradeRecord,
)

CANONICAL_PILOT_ROOT = PROJECT_ROOT / "outputs" / "demo_trading" / "pilot"

CONFIG_FILENAME = "pilot_config.json"
DAILY_FILENAME = "daily_records.jsonl"
TRADES_FILENAME = "trade_records.jsonl"
AUDIT_FILENAME = "audit_events.jsonl"
LATEST_SUMMARY_FILENAME = "latest_summary.json"


class PilotStoreError(Exception):
    """Base error for the pilot store."""


class DuplicateRecordError(PilotStoreError):
    """A record with an existing unique key was appended (fail closed)."""


class MalformedStoreError(PilotStoreError):
    """An existing JSONL file contains a malformed line."""


def _dumps(obj: Mapping[str, Any]) -> str:
    # Deterministic: sorted keys, compact-but-stable separators, UTF-8 text.
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class PilotStore:
    """Append-only local pilot store. ``output_root`` defaults to the canonical
    runtime root; tests may inject a temporary root."""

    def __init__(self, pilot_id: str, output_root: str | os.PathLike[str] | None = None) -> None:
        if not pilot_id:
            raise PilotStoreError("pilot_id is required")
        self.pilot_id = pilot_id
        root = pathlib.Path(output_root) if output_root is not None else CANONICAL_PILOT_ROOT
        self.dir = pathlib.Path(root) / pilot_id
        self.config_path = self.dir / CONFIG_FILENAME
        self.daily_path = self.dir / DAILY_FILENAME
        self.trades_path = self.dir / TRADES_FILENAME
        self.audit_path = self.dir / AUDIT_FILENAME
        self.latest_summary_path = self.dir / LATEST_SUMMARY_FILENAME

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)

    def _atomic_write_text(self, path: pathlib.Path, text: str) -> None:
        self._ensure_dir()
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def _read_jsonl(self, path: pathlib.Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise MalformedStoreError(
                        f"malformed JSONL in {path} at line {lineno}: {exc}"
                    ) from exc
        return rows

    def _append_jsonl(self, path: pathlib.Path, obj: Mapping[str, Any]) -> None:
        self._ensure_dir()
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(_dumps(obj) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    # ------------------------------------------------------------------
    # Config + summary (atomic)
    # ------------------------------------------------------------------

    def write_config(self, config: PilotConfig) -> dict[str, Any]:
        data = config.to_dict()
        self._atomic_write_text(self.config_path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
        return data

    def read_config(self) -> dict[str, Any] | None:
        if not self.config_path.exists():
            return None
        with open(self.config_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def write_latest_summary(self, summary: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(summary)
        self._atomic_write_text(self.latest_summary_path,
                                json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
        return data

    def read_latest_summary(self) -> dict[str, Any] | None:
        if not self.latest_summary_path.exists():
            return None
        with open(self.latest_summary_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # ------------------------------------------------------------------
    # Daily records
    # ------------------------------------------------------------------

    def read_daily(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.daily_path)

    def append_daily(self, record: PilotDailyRecord) -> dict[str, Any]:
        data = record.to_dict()
        existing = {r.get("date") for r in self.read_daily()}
        if data["date"] in existing:
            raise DuplicateRecordError(
                f"daily record for date {data['date']!r} already exists; use upsert_daily()"
            )
        self._append_jsonl(self.daily_path, data)
        return data

    def upsert_daily(self, record: PilotDailyRecord) -> dict[str, Any]:
        """Idempotent: replace any existing daily record for the same date.

        Rewrites the daily file atomically (the historical file is replaced as a
        whole; individual prior lines are not silently dropped -- all other
        dates are preserved)."""
        data = record.to_dict()
        rows = [r for r in self.read_daily() if r.get("date") != data["date"]]
        rows.append(data)
        rows.sort(key=lambda r: str(r.get("date", "")))
        text = "".join(_dumps(r) + "\n" for r in rows)
        self._atomic_write_text(self.daily_path, text)
        return data

    # ------------------------------------------------------------------
    # Trade records
    # ------------------------------------------------------------------

    def read_trades(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.trades_path)

    def append_trade(self, record: PilotTradeRecord) -> dict[str, Any]:
        data = record.to_dict()
        existing = {r.get("trade_id") for r in self.read_trades()}
        if data["trade_id"] in existing:
            raise DuplicateRecordError(f"trade_id {data['trade_id']!r} already exists")
        self._append_jsonl(self.trades_path, data)
        return data

    # ------------------------------------------------------------------
    # Audit events
    # ------------------------------------------------------------------

    def read_audit(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.audit_path)

    def append_audit(self, event: PilotAuditEvent) -> dict[str, Any]:
        data = event.to_dict()
        self._append_jsonl(self.audit_path, data)
        return data


__all__ = [
    "AUDIT_FILENAME",
    "CANONICAL_PILOT_ROOT",
    "CONFIG_FILENAME",
    "DAILY_FILENAME",
    "DuplicateRecordError",
    "LATEST_SUMMARY_FILENAME",
    "MalformedStoreError",
    "PilotStore",
    "PilotStoreError",
    "TRADES_FILENAME",
]
