"""TASK-014BX_FIX -- bridge native Demo execution results into the existing
Pilot reporting / delivery foundation.

Converts an unambiguous strategy-native daily execution result into the existing
Pilot daily record + output-status ledger, builds the canonical six-sheet
workbook, and (when explicitly allowed) updates the dedicated Notion row and the
Chinese Discord daily report. It REUSES the existing TASK-014BQ/BR/BT/BU
components (PilotStore, PilotDailyRecord, build_demo_strategy_pilot_workbook,
demo_strategy_pilot_notion_sync, demo_strategy_pilot_discord_notify,
demo_strategy_pilot_output_status). It does NOT create another reporting or HTTP
stack, sends no order, and never invokes the execution transport or the planner.

Local JSONL / state / Excel remain authoritative. A Notion/Discord delivery
failure never resends an order and never re-runs strategy execution. A
reconcile-outputs-only pass rebuilds Excel and retries delivery WITHOUT planning
or executing anything.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from src import demo_strategy_pilot_discord_notify as dn
from src import demo_strategy_pilot_notion_sync as ns
from src import demo_strategy_pilot_output_status as osm
from src.demo_strategy_pilot_reporting import PilotAuditEvent, PilotDailyRecord
from src.demo_strategy_pilot_store import DuplicateRecordError, PilotStore

TASK_ID = "TASK-014BX_FIX"

REPORTING_OK = "REPORTING_FINALIZED"
REPORTING_INCOMPLETE = "REPORTING_INCOMPLETE"
RECONCILED = "OUTPUTS_RECONCILED"
NO_COMMITTED_RECORD = "NO_COMMITTED_DAILY_RECORD"


def _utc_now(now: datetime | None = None) -> str:
    n = now or datetime.now(timezone.utc)
    return n.strftime("%Y-%m-%dT%H:%M:%SZ")


def _fp(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _default_workbook_builder():
    from scripts.build_demo_strategy_pilot_workbook import build_workbook
    return build_workbook


def _prior_cumulative(store: PilotStore) -> Decimal:
    rows = store.read_daily()
    if not rows:
        return Decimal("0")
    last = sorted(rows, key=lambda r: str(r.get("date", "")))[-1]
    try:
        return Decimal(str(last.get("cumulative_net_pnl_usdt", "0") or "0"))
    except Exception:  # noqa: BLE001
        return Decimal("0")


def build_daily_record_from_execution(
    exec_result: Mapping[str, Any], *, store: PilotStore, pilot_day: int = 0,
) -> PilotDailyRecord:
    """Map a DailyExecutionResult dict into the canonical PilotDailyRecord.

    Trading-data fields (order/filled/closed counts, fees) come from the
    execution result; output-delivery statuses start PENDING and are advanced by
    the output-status ledger only."""
    accepted = list(exec_result.get("accepted", []))
    ambiguous = list(exec_result.get("ambiguous", []))
    fees = Decimal("0")
    filled = 0
    closed = 0
    for a in accepted:
        try:
            fees += Decimal(str(a.get("exec_fee", "0") or "0"))
        except Exception:  # noqa: BLE001
            pass
        if str(a.get("final_status", "")) in ("Filled", "PartiallyFilled"):
            filled += 1
    order_count = len(accepted) + len(ambiguous)
    cumulative = _prior_cumulative(store)
    return PilotDailyRecord(
        date=str(exec_result.get("date", "")),
        pilot_day=pilot_day,
        runner_status="NATIVE_DEMO_EXECUTION",
        signal_count=int(exec_result.get("proposed_count", 0)),
        order_count=order_count,
        filled_count=filled,
        closed_trade_count=closed,
        realized_pnl_usdt=Decimal("0"),
        trading_fees_usdt=fees,
        funding_pnl_usdt=Decimal("0"),
        daily_net_pnl_usdt=Decimal("0"),
        cumulative_net_pnl_usdt=cumulative,
        daily_return_pct=Decimal("0"),
        cumulative_return_pct=Decimal("0"),
        max_drawdown_pct=Decimal("0"),
        current_position_symbol="",
        current_position_side="",
        current_position_qty=Decimal("0"),
        notion_sync_status="PENDING",
        excel_export_status="PENDING",
        discord_notify_status="PENDING",
        alerts_triggered=(),
        notes=f"strategy-native Demo execution; accepted={len(accepted)} ambiguous={len(ambiguous)}",
    )


def finalize_native_day(
    *,
    pilot_id: str,
    date: str,
    exec_result: Mapping[str, Any],
    output_root: str | None = None,
    pilot_day: int = 0,
    notion_enabled: bool = True,
    discord_enabled: bool = True,
    allow_notion_network: bool = False,
    allow_discord_network: bool = False,
    notion_sync: Any = None,
    discord_notify: Any = None,
    workbook_builder: Any = None,
    snapshot_date: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Commit the immutable daily record, build Excel, finalize the output-status
    ledger, and (optionally) deliver Notion/Discord. Delivery is recorded but
    never resends an order. ``reporting_ok`` is True only when Excel built OK."""
    ts = _utc_now(now)
    store = PilotStore(pilot_id, output_root)

    record = build_daily_record_from_execution(exec_result, store=store, pilot_day=pilot_day)
    daily_dict = record.to_dict()
    try:
        store.append_daily(record)
        committed = True
    except DuplicateRecordError:
        committed = False  # idempotent: immutable record already present
        existing = [r for r in store.read_daily() if r.get("date") == date]
        if existing:
            daily_dict = existing[-1]

    input_fp = _fp({"pilot_id": pilot_id, "date": date,
                    "proposed": exec_result.get("proposed", [])})
    plan_fp = _fp({"accepted": exec_result.get("accepted", []),
                   "rejected": exec_result.get("rejected", [])})
    core_fp = osm.compute_daily_core_fingerprint(
        pilot_id=pilot_id, daily_record=daily_dict,
        input_fingerprint=input_fp, plan_fingerprint=plan_fp)
    status_store = osm.OutputStatusStore(pilot_id, output_root)
    builder = workbook_builder or _default_workbook_builder()

    # BUILD EXCEL.
    try:
        builder(pilot_id, output_root, snapshot_date=snapshot_date)
        excel_status, excel_detail = osm.STATUS_OK, ""
    except Exception as exc:  # noqa: BLE001 -- Excel failure must not resend orders
        excel_status, excel_detail = osm.STATUS_FAIL, str(exc)

    # OPTIONAL Notion delivery (gated; default skipped).
    if notion_enabled and allow_notion_network:
        payload = ns.build_notion_payload(pilot_id, daily_dict,
                                          plan_fingerprint=plan_fp, input_fingerprint=input_fp)
        sync = notion_sync or ns.NotionDailySync(allow_network=True)
        res = sync.upsert(payload)
        notion_status = res.status
        notion_detail = str(res.to_dict().get("detail", ""))
    else:
        notion_status, notion_detail = ns.SYNC_SKIPPED, ""

    # OPTIONAL Discord delivery (gated; default skipped).
    if discord_enabled and allow_discord_network:
        summary = dn.build_discord_summary(pilot_id, daily_dict,
                                           proposed_action_count=int(exec_result.get("proposed_count", 0)))
        notify = discord_notify or dn.DiscordDailyNotify(allow_network=True)
        res = notify.notify(summary)
        discord_status = res.status
        discord_detail = str(res.to_dict().get("detail", ""))
    else:
        discord_status, discord_detail = dn.NOTIFY_SKIPPED, ""

    status_store.record_status(osm.OutputStatusRecord(
        pilot_id=pilot_id, date=date, excel_status=excel_status, notion_status=notion_status,
        discord_status=discord_status, excel_detail=excel_detail, notion_detail=notion_detail,
        discord_detail=discord_detail, updated_at_utc=ts, plan_fingerprint=plan_fp,
        input_fingerprint=input_fp, daily_core_fingerprint=core_fp))

    store.append_audit(PilotAuditEvent(
        timestamp_utc=ts, pilot_id=pilot_id, event_type="NATIVE_REPORTING_FINALIZED",
        component="native_reporting", status="OK" if excel_status == osm.STATUS_OK else "FAIL",
        message=f"excel={excel_status} notion={notion_status} discord={discord_status}",
        reference_id=date))

    reporting_ok = excel_status == osm.STATUS_OK
    return {"task_id": TASK_ID, "pilot_id": pilot_id, "date": date,
            "status": REPORTING_OK if reporting_ok else REPORTING_INCOMPLETE,
            "committed": committed, "reporting_ok": reporting_ok,
            "excel_status": excel_status, "notion_status": notion_status,
            "discord_status": discord_status, "daily_core_fingerprint": core_fp}


def reconcile_outputs_only(
    *,
    pilot_id: str,
    date: str,
    output_root: str | None = None,
    notion_enabled: bool = True,
    discord_enabled: bool = True,
    allow_notion_network: bool = False,
    allow_discord_network: bool = False,
    notion_sync: Any = None,
    discord_notify: Any = None,
    workbook_builder: Any = None,
    snapshot_date: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Rebuild Excel and retry ONLY failed/skipped Notion/Discord delivery for an
    already-committed date. Never plans, never executes, never resends an order;
    leaves the immutable daily record and execution ledgers untouched."""
    ts = _utc_now(now)
    store = PilotStore(pilot_id, output_root)
    rows = [r for r in store.read_daily() if r.get("date") == date]
    if not rows:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "date": date,
                "status": NO_COMMITTED_RECORD, "detail": "no committed daily record to reconcile"}
    daily = rows[-1]

    status_store = osm.OutputStatusStore(pilot_id, output_root)
    prior = status_store.latest_by_date().get(date, {})
    prior_notion = str(prior.get("notion_status", ns.SYNC_SKIPPED))
    prior_discord = str(prior.get("discord_status", dn.NOTIFY_SKIPPED))
    plan_fp = str(prior.get("plan_fingerprint", ""))
    input_fp = str(prior.get("input_fingerprint", ""))
    core_fp = str(prior.get("daily_core_fingerprint", "")) or osm.compute_daily_core_fingerprint(
        pilot_id=pilot_id, daily_record=daily, input_fingerprint=input_fp, plan_fingerprint=plan_fp)

    # Retry ONLY FAIL/SKIPPED deliveries (PASS untouched). No order ever sent.
    notion_status, notion_detail = prior_notion, ""
    if notion_enabled and allow_notion_network and prior_notion in (ns.SYNC_FAIL, ns.SYNC_SKIPPED):
        payload = ns.build_notion_payload(pilot_id, daily, plan_fingerprint=plan_fp,
                                          input_fingerprint=input_fp)
        sync = notion_sync or ns.NotionDailySync(allow_network=True)
        res = sync.upsert(payload)
        notion_status = res.status
        notion_detail = str(res.to_dict().get("detail", ""))

    discord_status, discord_detail = prior_discord, ""
    if discord_enabled and allow_discord_network and prior_discord in (dn.NOTIFY_FAIL, dn.NOTIFY_SKIPPED):
        summary = dn.build_discord_summary(pilot_id, daily)
        notify = discord_notify or dn.DiscordDailyNotify(allow_network=True)
        res = notify.notify(summary)
        discord_status = res.status
        discord_detail = str(res.to_dict().get("detail", ""))

    builder = workbook_builder or _default_workbook_builder()
    try:
        builder(pilot_id, output_root, snapshot_date=snapshot_date)
        excel_status, excel_detail = osm.STATUS_OK, ""
    except Exception as exc:  # noqa: BLE001
        excel_status, excel_detail = osm.STATUS_FAIL, str(exc)

    status_store.record_status(osm.OutputStatusRecord(
        pilot_id=pilot_id, date=date, excel_status=excel_status, notion_status=notion_status,
        discord_status=discord_status, excel_detail=excel_detail, notion_detail=notion_detail,
        discord_detail=discord_detail, updated_at_utc=ts, plan_fingerprint=plan_fp,
        input_fingerprint=input_fp, daily_core_fingerprint=core_fp))

    store.append_audit(PilotAuditEvent(
        timestamp_utc=ts, pilot_id=pilot_id, event_type="NATIVE_RECONCILE_OUTPUTS",
        component="native_reporting", status="OK",
        message=f"reconcile excel={excel_status} notion={notion_status} discord={discord_status}",
        reference_id=date))

    return {"task_id": TASK_ID, "pilot_id": pilot_id, "date": date, "status": RECONCILED,
            "excel_status": excel_status, "notion_status": notion_status,
            "discord_status": discord_status}


__all__ = [
    "NO_COMMITTED_RECORD",
    "RECONCILED",
    "REPORTING_INCOMPLETE",
    "REPORTING_OK",
    "TASK_ID",
    "build_daily_record_from_execution",
    "finalize_native_day",
    "reconcile_outputs_only",
]
