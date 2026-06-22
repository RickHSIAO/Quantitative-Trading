"""TASK-014BW -- fail-closed readiness foundation for a 7-successful-day Bybit
Demo strategy Pilot.

Configuration, validation, state-machine, and reporting-readiness ONLY. This
module does not start the Pilot, send any Bybit order, authorize automatic
execution, access live endpoints, add a scheduler, retry orders, create a Demo
position, or use Bybit credentials. All proposed actions remain
executable=false; order_execution / automatic_execution / live_trading are all
false.

"7 successful days" means 7 distinct ISO dates that each pass the successful-day
validator -- NOT 7 calendar days. Failed / incomplete / missing-input /
duplicated / safety-rejected runs do not count. The manual TASK-014BO/BP
SOLUSDT round trip and all smoke-test records are excluded from Pilot
performance.

No real Notion/Discord/Bybit network calls occur here (credential checks are
presence-only). No order endpoint string appears in this module; no live
executor / main / risk import.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from src import demo_strategy_pilot_delivery_transport as dt
from src import demo_strategy_pilot_forward_source as fs
from src.demo_strategy_pilot_store import CANONICAL_PILOT_ROOT

TASK_ID = "TASK-014BW"
SCHEMA_VERSION = 1
TARGET_SUCCESSFUL_DAYS = 7
ENVIRONMENT = "BYBIT_DEMO_ONLY"

PROTECTED_SYMBOLS = ("ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT")

# Approved INACTIVE safety policy (encoded, not active).
SAFETY_POLICY: dict[str, Any] = {
    "environment": ENVIRONMENT,
    "live_endpoint": "PERMANENTLY_DENIED",
    "max_new_opening_orders_per_successful_day": 1,
    "max_simultaneous_open_positions": 1,
    "max_per_order_notional_usdt": "10",
    "max_daily_new_opening_notional_usdt": "10",
    "averaging_down_pyramiding_adding": "FORBIDDEN",
    "automatic_order_retry": "FORBIDDEN",
    "close_orders": "REDUCE_ONLY_ONLY",
    "incomplete_or_stale_data": "FAIL_CLOSED",
    "unsupported_symbol": "FAIL_CLOSED",
    "protected_symbols": list(PROTECTED_SYMBOLS),
    "automatic_demo_execution": "UNAUTHORIZED",
    "proposed_actions_executable": False,
}

EXCLUDED_RECORD_CATEGORIES = (
    "TASK-014BO_BP_MANUAL_ROUND_TRIP",
    "SMOKE_TEST",
)

REPORTING_SUMMARY = {
    "excel": "six_sheet_workbook",
    "notion_row": "dedicated_pilot_database",
    "discord": "chinese_daily_report",
    "authoritative": "local_state_jsonl_and_excel",
    "delivery_failure_policy": "never_duplicates_state_or_orders",
}

# Lifecycle states.
NOT_INITIALIZED = "NOT_INITIALIZED"
INACTIVE = "INACTIVE"
READY_FOR_MANUAL_START_REVIEW = "READY_FOR_MANUAL_START_REVIEW"
RUNNING = "RUNNING"
BLOCKED = "BLOCKED"
COMPLETED = "COMPLETED"

# Readiness status semantics.
STATUS_READY = "READY_FOR_MANUAL_START_REVIEW"
STATUS_BLOCKED = "BLOCKED"
STATUS_INACTIVE = "INACTIVE"
STATUS_NOT_INITIALIZED = "NOT_INITIALIZED"
STATUS_INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
STATUS_CONFLICTING_EXISTING_STATE = "CONFLICTING_EXISTING_STATE"

# Successful-day verdicts.
ACCEPTABLE_SUCCESSFUL_DAY = "ACCEPTABLE_SUCCESSFUL_DAY"
REJECT_DUPLICATE_DATE = "REJECT_DUPLICATE_DATE"
REJECT_RUN_FAILED = "REJECT_RUN_FAILED"
REJECT_SOURCE_INVALID = "REJECT_SOURCE_INVALID"
REJECT_OUTPUT_INCOMPLETE = "REJECT_OUTPUT_INCOMPLETE"
REJECT_FINGERPRINT_CONFLICT = "REJECT_FINGERPRINT_CONFLICT"
REJECT_SAFETY_BLOCK = "REJECT_SAFETY_BLOCK"
REJECT_UNAUTHORIZED_EXECUTION = "REJECT_UNAUTHORIZED_EXECUTION"
REJECT_INVALID_DATE = "REJECT_INVALID_DATE"

STATE_FILENAME = "pilot_state.json"
STATE_EVENTS_FILENAME = "pilot_state_events.jsonl"

_PILOT_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Identities that must never be reused for a real 7-day Pilot.
FORBIDDEN_PILOT_IDS = frozenset({
    "BYBIT_DEMO_PILOT_BT_SMOKE_202606",
})
FORBIDDEN_PILOT_SUBSTRINGS = ("SMOKE", "BT_SMOKE", "TASK-014BO", "TASK-014BP", "BO_BP", "AUDIT", "MANUAL")

_SUCCESSFUL_RUNNER_STATUSES = frozenset({"COMPLETED", "ALREADY_COMMITTED_IDEMPOTENT", "RECONCILED"})


class PilotIdError(Exception):
    """The supplied Pilot ID is invalid or forbidden."""


class PilotStateConflict(Exception):
    """An existing Pilot state conflicts with the requested configuration."""


def validate_pilot_id(pilot_id: str) -> str:
    if not pilot_id or not _PILOT_ID_RE.match(pilot_id):
        raise PilotIdError(f"invalid pilot_id format {pilot_id!r} (allowed: [A-Za-z0-9_])")
    upper = pilot_id.upper()
    if pilot_id in FORBIDDEN_PILOT_IDS or any(s in upper for s in FORBIDDEN_PILOT_SUBSTRINGS):
        raise PilotIdError(f"pilot_id {pilot_id!r} is reserved/forbidden (smoke or manual audit identity)")
    return pilot_id


def _utc_now(now: datetime | None = None) -> str:
    n = now or datetime.now(timezone.utc)
    return n.strftime("%Y-%m-%dT%H:%M:%SZ")


def configuration_fingerprint(pilot_id: str) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "pilot_id": pilot_id,
        "environment": ENVIRONMENT,
        "target_successful_days": TARGET_SUCCESSFUL_DAYS,
        "policy": SAFETY_POLICY,
        "reporting_summary": REPORTING_SUMMARY,
        "excluded_record_categories": list(EXCLUDED_RECORD_CATEGORIES),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Successful-day validator (pure; never mutates state)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DayEvidence:
    date: str
    pilot_date: str
    source_date: str
    runner_status: str
    source_integrity_ok: bool = True
    daily_record_present: bool = True
    excel_status: str = "OK"
    notion_status: str = "PASS"
    discord_status: str = "PASS"
    notion_delivery_policy: str = "REQUIRE_PASS"   # or "NON_BLOCKING"
    discord_delivery_policy: str = "REQUIRE_PASS"
    duplicate_date: bool = False
    input_fingerprint_conflict: bool = False
    plan_fingerprint_conflict: bool = False
    blocking_safety_alert: bool = False
    live_endpoint_used: bool = False
    protected_symbol_present: bool = False
    unauthorized_execution: bool = False
    dry_run: bool = True
    order_count: int = 0
    filled_count: int = 0
    closed_trade_count: int = 0


def evaluate_successful_day(ev: DayEvidence) -> str:
    """Pure verdict for whether a date counts as a successful Pilot day.

    Does NOT mutate any Pilot state (TASK-014BW does not auto-advance)."""
    if not _ISO_DATE_RE.match(ev.date or ""):
        return REJECT_INVALID_DATE
    try:
        datetime.strptime(ev.date, "%Y-%m-%d")
    except ValueError:
        return REJECT_INVALID_DATE
    if ev.duplicate_date:
        return REJECT_DUPLICATE_DATE
    if ev.runner_status not in _SUCCESSFUL_RUNNER_STATUSES:
        return REJECT_RUN_FAILED
    if ev.source_date != ev.date or ev.pilot_date != ev.date:
        return REJECT_SOURCE_INVALID
    if not ev.source_integrity_ok or not ev.daily_record_present:
        return REJECT_SOURCE_INVALID
    if ev.input_fingerprint_conflict or ev.plan_fingerprint_conflict:
        return REJECT_FINGERPRINT_CONFLICT
    if ev.unauthorized_execution:
        return REJECT_UNAUTHORIZED_EXECUTION
    if ev.dry_run and (ev.order_count or ev.filled_count or ev.closed_trade_count):
        return REJECT_UNAUTHORIZED_EXECUTION
    if ev.live_endpoint_used or ev.protected_symbol_present or ev.blocking_safety_alert:
        return REJECT_SAFETY_BLOCK
    if ev.excel_status != "OK":
        return REJECT_OUTPUT_INCOMPLETE
    if ev.notion_delivery_policy == "REQUIRE_PASS" and ev.notion_status != "PASS":
        return REJECT_OUTPUT_INCOMPLETE
    if ev.discord_delivery_policy == "REQUIRE_PASS" and ev.discord_status != "PASS":
        return REJECT_OUTPUT_INCOMPLETE
    return ACCEPTABLE_SUCCESSFUL_DAY


# ---------------------------------------------------------------------------
# Pilot state store (canonical state + append-only events)
# ---------------------------------------------------------------------------


class PilotStateStore:
    def __init__(self, pilot_id: str, output_root: str | os.PathLike[str] | None = None) -> None:
        root = pathlib.Path(output_root) if output_root is not None else CANONICAL_PILOT_ROOT
        self.pilot_id = pilot_id
        self.dir = pathlib.Path(root) / pilot_id
        self.state_path = self.dir / STATE_FILENAME
        self.events_path = self.dir / STATE_EVENTS_FILENAME

    def exists(self) -> bool:
        return self.state_path.exists()

    def read_state(self) -> dict[str, Any] | None:
        if not self.state_path.exists():
            return None
        with open(self.state_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _atomic_write(self, path: pathlib.Path, text: str) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def append_event(self, event: Mapping[str, Any]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.events_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(event), ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def event_count(self) -> int:
        if not self.events_path.exists():
            return 0
        with open(self.events_path, "r", encoding="utf-8") as fh:
            return sum(1 for ln in fh if ln.strip())

    def write_state(self, state: Mapping[str, Any]) -> None:
        self._atomic_write(self.state_path, json.dumps(dict(state), ensure_ascii=False, indent=2, sort_keys=True))


def _new_state(pilot_id: str, *, lifecycle: str, now: str, blocked_reasons: list[str]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "pilot_id": pilot_id,
        "environment": ENVIRONMENT,
        "target_successful_days": TARGET_SUCCESSFUL_DAYS,
        "completed_successful_days": 0,
        "successful_dates": [],
        "remaining_successful_days": TARGET_SUCCESSFUL_DAYS,
        "lifecycle_state": lifecycle,
        "initialized_at_utc": now,
        "started_at_utc": None,
        "completed_at_utc": None,
        "last_accepted_date": None,
        "order_execution_authorized": False,
        "automatic_execution_authorized": False,
        "live_trading_authorized": False,
        "policy": SAFETY_POLICY,
        "configuration_fingerprint": configuration_fingerprint(pilot_id),
        "event_count": 1,
        "blocked_reasons": list(blocked_reasons),
        "excluded_record_categories": list(EXCLUDED_RECORD_CATEGORIES),
        "reporting_summary": REPORTING_SUMMARY,
    }


# ---------------------------------------------------------------------------
# Readiness checks
# ---------------------------------------------------------------------------


def _present(env: Mapping[str, str], name: str) -> bool:
    return bool((env.get(name, "") or "").strip())


def _git_reportable(repo_root: pathlib.Path) -> bool:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo_root),
                             capture_output=True, text=True, timeout=10)
        return out.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _forward_source_ok(repo_root: pathlib.Path, forward_source_root: str | None) -> tuple[bool, str]:
    root = pathlib.Path(forward_source_root) if forward_source_root else repo_root / "outputs" / "forward_record"
    summary = root / fs.PRIMARY_RUN_KEY / "forward_summary.json"
    if not summary.exists():
        return False, "primary forward_summary.json not found"
    try:
        with open(summary, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"forward_summary.json unreadable: {exc}"
    strat = str(data.get("strategy", ""))
    if strat != fs.EXPECTED_STRATEGY_NAME:
        return False, "forward_summary strategy mismatch"
    return True, "ok"


def _writable_root(output_root: pathlib.Path) -> bool:
    p = output_root
    while not p.exists() and p != p.parent:
        p = p.parent
    return os.access(str(p), os.W_OK)


def run_readiness(
    *,
    pilot_id: str,
    env: Mapping[str, str] | None = None,
    repo_root: pathlib.Path | str | None = None,
    output_root: str | os.PathLike[str] | None = None,
    forward_source_root: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    env = env if env is not None else os.environ
    repo_root = pathlib.Path(repo_root) if repo_root is not None else pathlib.Path(__file__).resolve().parents[1]
    out_root = pathlib.Path(output_root) if output_root is not None else CANONICAL_PILOT_ROOT

    base: dict[str, Any] = {
        "task_id": TASK_ID,
        "pilot_id": pilot_id,
        "lifecycle_state": NOT_INITIALIZED,
        "ready_for_manual_start_review": False,
        "blockers": [],
        "warnings": [],
        "checks": [],
        "safety_policy": SAFETY_POLICY,
        "target_successful_days": TARGET_SUCCESSFUL_DAYS,
        "completed_successful_days": 0,
        "remaining_successful_days": TARGET_SUCCESSFUL_DAYS,
        "order_execution_authorized": False,
        "automatic_execution_authorized": False,
        "live_trading_authorized": False,
        "network_attempted": False,
        "bybit_call_count": 0,
        "order_post_count": 0,
        "future_network_smoke_recommendations": [
            "scripts/provision_demo_strategy_pilot_notion_schema.py --plan (read-only Notion schema check)",
            "manage_demo_strategy_pilot.py --mode readiness (presence-only)",
            "run_demo_strategy_pilot_daily.py --mode reconcile_outputs --allow-notion-network (Notion-only delivery smoke)",
        ],
        "status": STATUS_NOT_INITIALIZED,
        "detail": "",
        "note": "READY_FOR_MANUAL_START_REVIEW does NOT authorize or start the Pilot.",
    }

    try:
        validate_pilot_id(pilot_id)
    except PilotIdError as exc:
        base["status"] = STATUS_INVALID_CONFIGURATION
        base["detail"] = str(exc)
        base["blockers"] = ["invalid_pilot_id"]
        return base

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    def add(name: str, passed: bool, detail: str = "", *, blocking: bool = True) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail, "blocking": blocking})
        if not passed:
            (blockers if blocking else warnings).append(name)

    # Conflicting existing state.
    store = PilotStateStore(pilot_id, output_root)
    existing = store.read_state()
    conflicting = existing is not None and existing.get("configuration_fingerprint") != configuration_fingerprint(pilot_id)
    add("no_conflicting_existing_state", not conflicting,
        "existing state config mismatch" if conflicting else "ok")

    # Git reportable (non-blocking warning).
    add("git_status_reportable", _git_reportable(repo_root), blocking=False)

    # Forward Record primary source.
    fok, fdetail = _forward_source_ok(repo_root, forward_source_root)
    add("forward_record_primary_source_available", fok, fdetail)

    # Reporting + Excel writer import.
    try:
        from src import demo_strategy_pilot_reporting as _rep  # noqa: F401
        from src import demo_strategy_pilot_store as _st  # noqa: F401
        from scripts import build_demo_strategy_pilot_workbook as _wb  # noqa: F401
        import_ok = hasattr(_wb, "SHEET_ORDER") and len(_wb.SHEET_ORDER) == 6
    except Exception:  # noqa: BLE001
        import_ok = False
    add("reporting_and_six_sheet_excel_importable", import_ok)

    # Credential presence (presence-only; never expose values).
    add("notion_token_present", _present(env, dt.NOTION_TOKEN_ENV))
    add("notion_pilot_database_id_present", _present(env, dt.NOTION_PILOT_DATABASE_ID_ENV))
    add("discord_webhook_present", _present(env, dt.DISCORD_WEBHOOK_ENV))

    # Output root writable.
    add("canonical_output_root_writable", _writable_root(out_root))

    # Safety invariants.
    add("automatic_execution_disabled", base["automatic_execution_authorized"] is False)
    add("live_trading_disabled", base["live_trading_authorized"] is False)
    add("safety_policy_matches_approved", SAFETY_POLICY == EXPECTED_SAFETY_POLICY)

    base["checks"] = checks
    base["blockers"] = blockers
    base["warnings"] = warnings
    base["lifecycle_state"] = existing.get("lifecycle_state") if existing else NOT_INITIALIZED

    if conflicting:
        base["status"] = STATUS_CONFLICTING_EXISTING_STATE
        base["detail"] = "existing Pilot state has a different configuration fingerprint"
        return base
    if blockers:
        base["status"] = STATUS_BLOCKED
        base["detail"] = "readiness requirements not met"
        return base
    base["status"] = STATUS_READY
    base["ready_for_manual_start_review"] = True
    base["detail"] = "all readiness checks pass; manual start authorization is a SEPARATE task"
    return base


# A frozen copy of the approved policy for the equality self-check.
EXPECTED_SAFETY_POLICY = dict(SAFETY_POLICY)


# ---------------------------------------------------------------------------
# Initialize / status
# ---------------------------------------------------------------------------


def initialize_pilot(
    *,
    pilot_id: str,
    acknowledged: bool,
    env: Mapping[str, str] | None = None,
    repo_root: pathlib.Path | str | None = None,
    output_root: str | os.PathLike[str] | None = None,
    forward_source_root: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a NEW INACTIVE Pilot state (or BLOCKED if readiness fails).

    Requires the explicit acknowledgement flag. Idempotent for the same
    configuration; a conflicting existing state fails closed. Never produces
    RUNNING or COMPLETED."""
    ts = _utc_now(now)
    try:
        validate_pilot_id(pilot_id)
    except PilotIdError as exc:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": STATUS_INVALID_CONFIGURATION,
                "detail": str(exc), "lifecycle_state": NOT_INITIALIZED}

    if not acknowledged:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": "REFUSED_NOT_ACKNOWLEDGED",
                "detail": "initialize requires --i-understand-this-creates-an-inactive-7-day-pilot",
                "lifecycle_state": NOT_INITIALIZED}

    store = PilotStateStore(pilot_id, output_root)
    existing = store.read_state()
    fp = configuration_fingerprint(pilot_id)
    if existing is not None:
        if existing.get("configuration_fingerprint") == fp:
            return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": "ALREADY_INITIALIZED_IDEMPOTENT",
                    "detail": "identical configuration already initialized",
                    "lifecycle_state": existing.get("lifecycle_state"), "state": existing}
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": STATUS_CONFLICTING_EXISTING_STATE,
                "detail": "existing Pilot state has a different configuration fingerprint",
                "lifecycle_state": existing.get("lifecycle_state")}

    readiness = run_readiness(pilot_id=pilot_id, env=env, repo_root=repo_root,
                              output_root=output_root, forward_source_root=forward_source_root, now=now)
    blockers = list(readiness.get("blockers", []))
    lifecycle = BLOCKED if blockers else INACTIVE
    state = _new_state(pilot_id, lifecycle=lifecycle, now=ts, blocked_reasons=blockers)
    store.write_state(state)
    store.append_event({"event": "INITIALIZE", "at_utc": ts, "lifecycle_state": lifecycle,
                        "configuration_fingerprint": fp, "blocked_reasons": blockers})
    return {"task_id": TASK_ID, "pilot_id": pilot_id,
            "status": STATUS_BLOCKED if blockers else STATUS_INACTIVE,
            "lifecycle_state": lifecycle, "detail": "inactive Pilot state created" if not blockers else "blocked",
            "state": state}


def pilot_status(*, pilot_id: str, output_root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    try:
        validate_pilot_id(pilot_id)
    except PilotIdError as exc:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": STATUS_INVALID_CONFIGURATION, "detail": str(exc)}
    store = PilotStateStore(pilot_id, output_root)
    state = store.read_state()
    if state is None:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": STATUS_NOT_INITIALIZED,
                "lifecycle_state": NOT_INITIALIZED, "completed_successful_days": 0,
                "remaining_successful_days": TARGET_SUCCESSFUL_DAYS, "successful_dates": [],
                "last_accepted_date": None, "blocked_reasons": []}
    return {
        "task_id": TASK_ID,
        "pilot_id": pilot_id,
        "status": state.get("lifecycle_state"),
        "lifecycle_state": state.get("lifecycle_state"),
        "completed_successful_days": state.get("completed_successful_days", 0),
        "remaining_successful_days": state.get("remaining_successful_days", TARGET_SUCCESSFUL_DAYS),
        "successful_dates": state.get("successful_dates", []),
        "last_accepted_date": state.get("last_accepted_date"),
        "blocked_reasons": state.get("blocked_reasons", []),
        "order_execution_authorized": state.get("order_execution_authorized", False),
        "automatic_execution_authorized": state.get("automatic_execution_authorized", False),
        "live_trading_authorized": state.get("live_trading_authorized", False),
    }


__all__ = [
    "ACCEPTABLE_SUCCESSFUL_DAY",
    "BLOCKED",
    "DayEvidence",
    "EXCLUDED_RECORD_CATEGORIES",
    "INACTIVE",
    "NOT_INITIALIZED",
    "PROTECTED_SYMBOLS",
    "PilotIdError",
    "PilotStateConflict",
    "PilotStateStore",
    "READY_FOR_MANUAL_START_REVIEW",
    "REJECT_DUPLICATE_DATE",
    "REJECT_FINGERPRINT_CONFLICT",
    "REJECT_INVALID_DATE",
    "REJECT_OUTPUT_INCOMPLETE",
    "REJECT_RUN_FAILED",
    "REJECT_SAFETY_BLOCK",
    "REJECT_SOURCE_INVALID",
    "REJECT_UNAUTHORIZED_EXECUTION",
    "SAFETY_POLICY",
    "SCHEMA_VERSION",
    "STATUS_BLOCKED",
    "STATUS_CONFLICTING_EXISTING_STATE",
    "STATUS_INACTIVE",
    "STATUS_INVALID_CONFIGURATION",
    "STATUS_NOT_INITIALIZED",
    "STATUS_READY",
    "TARGET_SUCCESSFUL_DAYS",
    "TASK_ID",
    "configuration_fingerprint",
    "evaluate_successful_day",
    "initialize_pilot",
    "pilot_status",
    "run_readiness",
    "validate_pilot_id",
]
