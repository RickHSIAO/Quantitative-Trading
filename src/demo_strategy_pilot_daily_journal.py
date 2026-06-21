"""TASK-014BR -- per-day journal + rerun protection for the demo pilot runner.

Strictly OFFLINE. Stores one journal directory per pilot/date OUTSIDE source
control:

    outputs/demo_trading/pilot/<pilot_id>/daily_runs/<YYYY-MM-DD>/
        run_journal.json      (atomic; full state history preserved)
        daily_plan.json       (atomic)
        notion_payload.json   (atomic)
        discord_summary.txt   (atomic)
        run_result.json       (atomic)

The journal path derives ONLY from the canonical output root, a validated
``pilot_id`` (``^[A-Za-z0-9_]+$``), and a validated ISO date
(``YYYY-MM-DD``). Path traversal is refused.

No network, no secrets, no order endpoints.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
from datetime import datetime
from typing import Any, Mapping

from src.demo_strategy_pilot_store import CANONICAL_PILOT_ROOT

RUN_JOURNAL_FILENAME = "run_journal.json"
DAILY_PLAN_FILENAME = "daily_plan.json"
NOTION_PAYLOAD_FILENAME = "notion_payload.json"
DISCORD_SUMMARY_FILENAME = "discord_summary.txt"
RUN_RESULT_FILENAME = "run_result.json"

_PILOT_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Journal states.
RUN_INTENT_RECORDED = "RUN_INTENT_RECORDED"
DAILY_RECORD_COMMITTED = "DAILY_RECORD_COMMITTED"
EXCEL_BUILT = "EXCEL_BUILT"
NOTION_PREVIEW_BUILT = "NOTION_PREVIEW_BUILT"
NOTION_SYNC_PASS = "NOTION_SYNC_PASS"
NOTION_SYNC_FAIL = "NOTION_SYNC_FAIL"
NOTION_SYNC_SKIPPED = "NOTION_SYNC_SKIPPED"
DISCORD_PREVIEW_BUILT = "DISCORD_PREVIEW_BUILT"
DISCORD_NOTIFY_PASS = "DISCORD_NOTIFY_PASS"
DISCORD_NOTIFY_FAIL = "DISCORD_NOTIFY_FAIL"
DISCORD_NOTIFY_SKIPPED = "DISCORD_NOTIFY_SKIPPED"
RUN_COMPLETED = "RUN_COMPLETED"
RUN_FAILED_BEFORE_RECORD = "RUN_FAILED_BEFORE_RECORD"
RUN_FAILED_AFTER_RECORD = "RUN_FAILED_AFTER_RECORD"


class DailyJournalError(Exception):
    """Base error for the daily journal."""


class UnsafeJournalPathError(DailyJournalError):
    """pilot_id / date failed validation (possible path traversal)."""


class MalformedJournalError(DailyJournalError):
    """An existing journal file is malformed."""


def validate_pilot_id(pilot_id: str) -> str:
    if not pilot_id or not _PILOT_ID_RE.match(pilot_id):
        raise UnsafeJournalPathError(f"unsafe pilot_id {pilot_id!r}")
    return pilot_id


def validate_iso_date(date: str) -> str:
    if not date or not _DATE_RE.match(date):
        raise UnsafeJournalPathError(f"unsafe date {date!r} (expected YYYY-MM-DD)")
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise UnsafeJournalPathError(f"invalid calendar date {date!r}: {exc}") from exc
    return date


def sha256_fingerprint(obj: Any) -> str:
    """Deterministic SHA-256 of a canonical JSON encoding (sorted keys)."""
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class DailyRunJournal:
    """Atomic, history-preserving per-day journal. No reset/force/delete API."""

    def __init__(self, pilot_id: str, date: str, output_root: str | os.PathLike[str] | None = None) -> None:
        self.pilot_id = validate_pilot_id(pilot_id)
        self.date = validate_iso_date(date)
        root = pathlib.Path(output_root) if output_root is not None else CANONICAL_PILOT_ROOT
        root = pathlib.Path(root)
        self.dir = (root / self.pilot_id / "daily_runs" / self.date).resolve()
        # Path-traversal containment: dir must live under root/pilot_id/daily_runs.
        expected_parent = (root / self.pilot_id / "daily_runs").resolve()
        try:
            self.dir.relative_to(expected_parent)
        except ValueError as exc:
            raise UnsafeJournalPathError(f"journal dir {self.dir!r} escapes {expected_parent!r}") from exc
        self.journal_path = self.dir / RUN_JOURNAL_FILENAME

    # ------------------------------------------------------------------
    def _atomic_write_text(self, path: pathlib.Path, text: str) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def write_json(self, filename: str, data: Mapping[str, Any]) -> None:
        self._atomic_write_text(self.dir / filename, json.dumps(dict(data), ensure_ascii=False, indent=2, sort_keys=True))

    def write_text(self, filename: str, text: str) -> None:
        self._atomic_write_text(self.dir / filename, text)

    def exists(self) -> bool:
        return self.journal_path.exists()

    def read(self) -> dict[str, Any] | None:
        if not self.journal_path.exists():
            return None
        try:
            with open(self.journal_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError as exc:
            raise MalformedJournalError(f"malformed run journal at {self.journal_path}: {exc}") from exc

    def state(self) -> str | None:
        data = self.read()
        return None if data is None else str(data.get("state"))

    def history(self) -> list[dict[str, Any]]:
        data = self.read() or {}
        return list(data.get("history", []))

    def init_journal(self, *, state: str, generated_at_utc: str, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
        record = {
            "task_id": "TASK-014BR",
            "pilot_id": self.pilot_id,
            "date": self.date,
            "state": state,
            "created_at_utc": generated_at_utc,
            "updated_at_utc": generated_at_utc,
            "history": [{"state": state, "at_utc": generated_at_utc}],
        }
        if extra:
            record.update(dict(extra))
        self.write_json(RUN_JOURNAL_FILENAME, record)
        return record

    def transition(self, new_state: str, *, at_utc: str, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = self.read()
        if data is None:
            return self.init_journal(state=new_state, generated_at_utc=at_utc, extra=extra)
        data["state"] = new_state
        data["updated_at_utc"] = at_utc
        history = list(data.get("history", []))
        history.append({"state": new_state, "at_utc": at_utc})
        data["history"] = history
        if extra:
            for k, v in extra.items():
                data[k] = v
        self.write_json(RUN_JOURNAL_FILENAME, data)
        return data


__all__ = [
    "DAILY_PLAN_FILENAME",
    "DAILY_RECORD_COMMITTED",
    "DISCORD_NOTIFY_FAIL",
    "DISCORD_NOTIFY_PASS",
    "DISCORD_NOTIFY_SKIPPED",
    "DISCORD_PREVIEW_BUILT",
    "DISCORD_SUMMARY_FILENAME",
    "DailyJournalError",
    "DailyRunJournal",
    "EXCEL_BUILT",
    "MalformedJournalError",
    "NOTION_PAYLOAD_FILENAME",
    "NOTION_PREVIEW_BUILT",
    "NOTION_SYNC_FAIL",
    "NOTION_SYNC_PASS",
    "NOTION_SYNC_SKIPPED",
    "RUN_COMPLETED",
    "RUN_FAILED_AFTER_RECORD",
    "RUN_FAILED_BEFORE_RECORD",
    "RUN_INTENT_RECORDED",
    "RUN_JOURNAL_FILENAME",
    "RUN_RESULT_FILENAME",
    "UnsafeJournalPathError",
    "sha256_fingerprint",
    "validate_iso_date",
    "validate_pilot_id",
]
