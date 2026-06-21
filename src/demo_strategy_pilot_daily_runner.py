"""TASK-014BR -- deterministic daily orchestration (DRY-RUN) for the demo pilot.

Strictly a reporting/orchestration DRY-RUN. It builds an auditable daily
*execution-plan preview* and wires the reporting outputs (append-only store,
real Excel workbook, gated Notion/Discord). It NEVER executes an order:
``order_execution_authorized`` is always ``False`` and there is no
order-execution mode.

It reuses the existing verified pilot reporting modules and does not modify the
strategy, the strategy parameters, the protected-symbol policy, or the
TASK-014BO / TASK-014BP one-shot execution modules. It contains no order
endpoint and does not import the live order-execution stack.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

from src import demo_strategy_pilot_daily_journal as jr
from src import demo_strategy_pilot_discord_notify as dn
from src import demo_strategy_pilot_notion_sync as ns
from src import demo_strategy_pilot_output_status as osm
from src.demo_strategy_pilot_reporting import (
    PilotAuditEvent,
    PilotConfig,
    PilotDailyRecord,
    dec_str,
)
from src.demo_strategy_pilot_store import DuplicateRecordError, PilotStore

TASK_ID = "TASK-014BR"
IDENTITY = "DEMO-STRATEGY-PILOT-DAILY-RUNNER-DRY-RUN"

# Canonical strategy/profile identifier of the COMPLETED 30-day forward
# validation (primary forward-record run "prev3y_crypto"; strategy label emitted
# by apps/forward_record/stats_updater.py). The "_shadow_a_roll12" run is a
# shadow, NOT the primary candidate.
PRIMARY_FORWARD_RUN_KEY = "prev3y_crypto"
SHADOW_FORWARD_RUN_KEY = "prev3y_crypto_shadow_a_roll12"
EXPECTED_STRATEGY_NAME = "prev3y_crypto_combined_paper_safe_variant"

PROTECTED_SYMBOLS = frozenset({"ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"})

MODE_PLAN = "plan"
MODE_DRY_RUN = "dry_run"
MODE_RECONCILE = "reconcile_outputs"
MODES = (MODE_PLAN, MODE_DRY_RUN, MODE_RECONCILE)

ORDER_EXECUTION_AUTHORIZED = False
REASON_NOT_AUTHORIZED = "TASK-014BR_IS_DRY_RUN_REPORTING_WIRING_ONLY"

# Action eligibility classifications.
ELIGIBLE = "ELIGIBLE_FOR_FUTURE_DEMO_PILOT"
PROTECTED_BLOCKED = "PROTECTED_SYMBOL_BLOCKED"
INVALID_BLOCKED = "INVALID_SIGNAL_BLOCKED"
NO_ACTION = "NO_ACTION"

PHASES = (
    "LOAD_CONFIG",
    "VALIDATE_PILOT_WINDOW",
    "LOAD_AND_VALIDATE_INPUTS",
    "CALCULATE_OR_LOAD_STRATEGY_RESULT",
    "BUILD_DAILY_PLAN",
    "PERSIST_RUN_INTENT",
    "APPEND_DAILY_RECORD",
    "APPEND_AUDIT_EVENTS",
    "BUILD_EXCEL",
    "BUILD_NOTION_PAYLOAD",
    "OPTIONAL_NOTION_SYNC",
    "BUILD_DISCORD_SUMMARY",
    "OPTIONAL_DISCORD_NOTIFY",
    "WRITE_LATEST_SUMMARY",
    "FINALIZE_RUN",
)

# Result statuses.
STATUS_PLAN_ONLY = "PLAN_ONLY"
STATUS_COMPLETED = "COMPLETED"
STATUS_ALREADY_COMMITTED_IDEMPOTENT = "ALREADY_COMMITTED_IDEMPOTENT"
STATUS_DAILY_PLAN_CONFLICT = "DAILY_PLAN_CONFLICT"
STATUS_PARTIAL_OUTPUT_FAILURE = "PARTIAL_OUTPUT_FAILURE"
STATUS_INPUT_FAILURE = "INPUT_FAILURE"
STATUS_SAFETY_REFUSAL = "SAFETY_REFUSAL"
STATUS_RECONCILED = "RECONCILED"

# Exit codes.
EXIT_OK = 0
EXIT_INVALID = 2
EXIT_INPUT_FAILURE = 3
EXIT_PARTIAL_OUTPUT = 4
EXIT_CONFLICT = 5
EXIT_SAFETY = 6


class StrategyAmbiguousError(Exception):
    """The strategy/profile mapping for the 30-day forward validation is
    ambiguous; refuse rather than choose silently."""


def resolve_strategy_name(forward_summary: Mapping[str, Any] | None = None) -> str:
    """Resolve the exact strategy identifier of the completed 30-day forward
    validation. Fail closed if an authoritative summary names a different or
    shadow strategy."""
    if forward_summary is None:
        return EXPECTED_STRATEGY_NAME
    declared = str(forward_summary.get("strategy", "")).strip()
    if not declared:
        return EXPECTED_STRATEGY_NAME
    if "shadow" in declared.lower():
        raise StrategyAmbiguousError(
            f"authoritative forward summary names a shadow strategy {declared!r}; "
            f"candidates: {[EXPECTED_STRATEGY_NAME, declared]}"
        )
    if declared != EXPECTED_STRATEGY_NAME:
        raise StrategyAmbiguousError(
            f"strategy identifier mismatch: summary={declared!r} expected="
            f"{EXPECTED_STRATEGY_NAME!r}; candidates: {[EXPECTED_STRATEGY_NAME, declared]}"
        )
    return declared


def _norm_side(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in ("long", "buy"):
        return "long"
    if s in ("short", "sell"):
        return "short"
    return ""


def normalize_signals(strategy_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Deterministically normalize raw strategy signals (sanitized)."""
    raw = strategy_result.get("signals", []) if isinstance(strategy_result, Mapping) else []
    out: list[dict[str, Any]] = []
    for sig in raw or []:
        if not isinstance(sig, Mapping):
            out.append({"symbol": "", "side": "", "raw_side": str(sig), "valid": False})
            continue
        symbol = str(sig.get("symbol", "")).strip().upper()
        side = _norm_side(sig.get("side"))
        valid = bool(symbol) and side in ("long", "short")
        entry = {"symbol": symbol, "side": side, "raw_side": str(sig.get("side", "")), "valid": valid}
        if "score" in sig:
            entry["score"] = str(sig.get("score"))
        out.append(entry)
    out.sort(key=lambda e: (e.get("symbol", ""), e.get("side", "")))
    return out


def classify_actions(normalized: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Classify each normalized signal; NEVER produces an executable action."""
    actions: list[dict[str, Any]] = []
    for sig in normalized:
        symbol = sig.get("symbol", "")
        if not sig.get("valid", False):
            elig = INVALID_BLOCKED
        elif symbol in PROTECTED_SYMBOLS:
            elig = PROTECTED_BLOCKED
        else:
            elig = ELIGIBLE
        actions.append({
            "symbol": symbol,
            "side": sig.get("side", ""),
            "eligibility": elig,
            "executable": False,
            "hypothetical": True,
        })
    return actions


@dataclass(frozen=True)
class PilotDailyExecutionPlan:
    pilot_id: str
    date: str
    pilot_day: int
    strategy_name: str
    environment: str
    source_data_date: str
    source_data_status: str
    runner_mode: str
    signal_count: int
    normalized_signals: tuple
    proposed_actions: tuple
    current_position_snapshot: Mapping[str, Any]
    order_execution_authorized: bool
    reason_execution_not_authorized: str
    input_fingerprint: str
    plan_fingerprint: str
    generated_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pilot_id": self.pilot_id,
            "date": self.date,
            "pilot_day": self.pilot_day,
            "strategy_name": self.strategy_name,
            "environment": self.environment,
            "source_data_date": self.source_data_date,
            "source_data_status": self.source_data_status,
            "runner_mode": self.runner_mode,
            "signal_count": self.signal_count,
            "normalized_signals": [dict(s) for s in self.normalized_signals],
            "proposed_actions": [dict(a) for a in self.proposed_actions],
            "current_position_snapshot": dict(self.current_position_snapshot),
            "order_execution_authorized": self.order_execution_authorized,
            "reason_execution_not_authorized": self.reason_execution_not_authorized,
            "input_fingerprint": self.input_fingerprint,
            "plan_fingerprint": self.plan_fingerprint,
            "generated_at_utc": self.generated_at_utc,
        }


def _utc_now(clock: Any | None) -> str:
    now = clock.now_utc() if clock is not None else datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _pilot_day(config: PilotConfig, date: str) -> int:
    try:
        start = datetime.strptime(config.start_date, "%Y-%m-%d")
        cur = datetime.strptime(date, "%Y-%m-%d")
        return (cur - start).days + 1
    except (ValueError, TypeError):
        return 0


def build_plan(
    *,
    pilot_id: str,
    date: str,
    config: PilotConfig,
    strategy_result: Mapping[str, Any],
    runner_mode: str,
    current_position_snapshot: Mapping[str, Any] | None = None,
    clock: Any | None = None,
) -> PilotDailyExecutionPlan:
    strategy_name = resolve_strategy_name(strategy_result.get("forward_summary"))
    source_data_date = str(strategy_result.get("data_date", ""))
    source_data_status = str(strategy_result.get("data_status", ""))
    source_meta = strategy_result.get("source_metadata", {})
    normalized = normalize_signals(strategy_result)
    actions = classify_actions(normalized)
    position = dict(current_position_snapshot or {"symbol": "", "side": "", "qty": "0"})

    input_fp = jr.sha256_fingerprint({
        "pilot_id": pilot_id,
        "date": date,
        "run_key": str(strategy_result.get("run_key", "")),
        "strategy_name": strategy_name,
        "source_data_date": source_data_date,
        "market_data_date": str(strategy_result.get("market_data_date", "")),
        "source_metadata": source_meta,
        "normalized_signals": normalized,
    })
    plan_fp = jr.sha256_fingerprint({
        "input_fingerprint": input_fp,
        "normalized_signals": normalized,
        "proposed_actions": actions,
        "current_position_snapshot": position,
        "order_execution_authorized": ORDER_EXECUTION_AUTHORIZED,
        "reason_execution_not_authorized": REASON_NOT_AUTHORIZED,
    })

    return PilotDailyExecutionPlan(
        pilot_id=pilot_id,
        date=date,
        pilot_day=_pilot_day(config, date),
        strategy_name=strategy_name,
        environment=config.environment,
        source_data_date=source_data_date,
        source_data_status=source_data_status,
        runner_mode=runner_mode,
        signal_count=len(normalized),
        normalized_signals=tuple(normalized),
        proposed_actions=tuple(actions),
        current_position_snapshot=position,
        order_execution_authorized=ORDER_EXECUTION_AUTHORIZED,
        reason_execution_not_authorized=REASON_NOT_AUTHORIZED,
        input_fingerprint=input_fp,
        plan_fingerprint=plan_fp,
        generated_at_utc=_utc_now(clock),
    )


@dataclass
class RunResult:
    task_id: str
    mode: str
    pilot_id: str
    date: str
    status: str
    exit_code: int
    journal_state: str | None
    phases_completed: list[str]
    plan: Mapping[str, Any] | None
    daily_record: Mapping[str, Any] | None
    excel: Mapping[str, Any] | None
    notion: Mapping[str, Any] | None
    discord: Mapping[str, Any] | None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "mode": self.mode,
            "pilot_id": self.pilot_id,
            "date": self.date,
            "status": self.status,
            "exit_code": self.exit_code,
            "journal_state": self.journal_state,
            "phases_completed": list(self.phases_completed),
            "plan": dict(self.plan) if self.plan else None,
            "daily_record": dict(self.daily_record) if self.daily_record else None,
            "excel": dict(self.excel) if self.excel else None,
            "notion": dict(self.notion) if self.notion else None,
            "discord": dict(self.discord) if self.discord else None,
            "order_execution_authorized": ORDER_EXECUTION_AUTHORIZED,
            "reason_execution_not_authorized": REASON_NOT_AUTHORIZED,
            "detail": self.detail,
        }


def _prior_cumulative(store: PilotStore) -> Decimal:
    rows = store.read_daily()
    if not rows:
        return Decimal("0")
    last = sorted(rows, key=lambda r: str(r.get("date", "")))[-1]
    try:
        return Decimal(str(last.get("cumulative_net_pnl_usdt", "0") or "0"))
    except Exception:
        return Decimal("0")


def _build_daily_record(plan: PilotDailyExecutionPlan, store: PilotStore, *, notes: str) -> PilotDailyRecord:
    pos = plan.current_position_snapshot
    cumulative = _prior_cumulative(store)
    return PilotDailyRecord(
        date=plan.date,
        pilot_day=plan.pilot_day,
        runner_status="DRY_RUN_PLAN_ONLY",
        signal_count=plan.signal_count,
        order_count=0,
        filled_count=0,
        closed_trade_count=0,
        realized_pnl_usdt=Decimal("0"),
        trading_fees_usdt=Decimal("0"),
        funding_pnl_usdt=Decimal("0"),
        daily_net_pnl_usdt=Decimal("0"),
        cumulative_net_pnl_usdt=cumulative,
        daily_return_pct=Decimal("0"),
        cumulative_return_pct=Decimal("0"),
        max_drawdown_pct=Decimal("0"),
        current_position_symbol=str(pos.get("symbol", "")),
        current_position_side=str(pos.get("side", "")),
        current_position_qty=Decimal(str(pos.get("qty", "0") or "0")),
        notion_sync_status="PENDING",
        excel_export_status="PENDING",
        discord_notify_status="PENDING",
        alerts_triggered=(),
        notes=notes,
    )


def _default_workbook_builder():
    from scripts.build_demo_strategy_pilot_workbook import build_workbook
    return build_workbook


def run_daily(
    *,
    mode: str,
    pilot_id: str,
    date: str,
    config: PilotConfig,
    strategy_result: Mapping[str, Any] | None,
    output_root: str | None = None,
    notion_sync: ns.NotionDailySync | None = None,
    discord_notify: dn.DiscordDailyNotify | None = None,
    allow_notion_network: bool = False,
    allow_discord_network: bool = False,
    current_position_snapshot: Mapping[str, Any] | None = None,
    clock: Any | None = None,
    workbook_builder: Callable[..., Mapping[str, Any]] | None = None,
    snapshot_date: str | None = None,
) -> RunResult:
    """Run one deterministic daily orchestration. Never executes an order."""
    if mode not in MODES:
        return RunResult(TASK_ID, mode, pilot_id, date, STATUS_SAFETY_REFUSAL, EXIT_INVALID,
                         None, [], None, None, None, None, None, f"invalid mode {mode!r}")

    now = _utc_now(clock)
    phases: list[str] = []

    # ---- PLAN mode: offline, no permanent state unless output_root given ----
    if mode == MODE_PLAN:
        if strategy_result is None:
            return RunResult(TASK_ID, mode, pilot_id, date, STATUS_INPUT_FAILURE, EXIT_INPUT_FAILURE,
                             None, phases, None, None, None, None, None, "no strategy_result for plan")
        try:
            plan = build_plan(pilot_id=pilot_id, date=date, config=config,
                              strategy_result=strategy_result, runner_mode=mode,
                              current_position_snapshot=current_position_snapshot, clock=clock)
        except StrategyAmbiguousError as exc:
            return RunResult(TASK_ID, mode, pilot_id, date, STATUS_SAFETY_REFUSAL, EXIT_SAFETY,
                             None, phases, None, None, None, None, None, str(exc))
        phases.extend(["LOAD_CONFIG", "VALIDATE_PILOT_WINDOW", "LOAD_AND_VALIDATE_INPUTS",
                       "CALCULATE_OR_LOAD_STRATEGY_RESULT", "BUILD_DAILY_PLAN"])
        if output_root is not None:
            journal = jr.DailyRunJournal(pilot_id, date, output_root)
            journal.write_json(jr.DAILY_PLAN_FILENAME, plan.to_dict())
        return RunResult(TASK_ID, mode, pilot_id, date, STATUS_PLAN_ONLY, EXIT_OK,
                         None, phases, plan.to_dict(), None, None, None, None,
                         "offline plan preview only")

    store = PilotStore(pilot_id, output_root)
    journal = jr.DailyRunJournal(pilot_id, date, output_root)

    if mode == MODE_RECONCILE:
        return _reconcile_outputs(store=store, journal=journal, pilot_id=pilot_id, date=date,
                                  config=config, notion_sync=notion_sync, discord_notify=discord_notify,
                                  allow_notion_network=allow_notion_network,
                                  allow_discord_network=allow_discord_network,
                                  workbook_builder=workbook_builder, snapshot_date=snapshot_date,
                                  clock=clock)

    # ---- DRY_RUN ----
    if strategy_result is None:
        return RunResult(TASK_ID, mode, pilot_id, date, STATUS_INPUT_FAILURE, EXIT_INPUT_FAILURE,
                         None, phases, None, None, None, None, None, "no strategy_result for dry_run")
    try:
        plan = build_plan(pilot_id=pilot_id, date=date, config=config, strategy_result=strategy_result,
                          runner_mode=mode, current_position_snapshot=current_position_snapshot, clock=clock)
    except StrategyAmbiguousError as exc:
        return RunResult(TASK_ID, mode, pilot_id, date, STATUS_SAFETY_REFUSAL, EXIT_SAFETY,
                         None, phases, None, None, None, None, None, str(exc))
    phases.extend(["LOAD_CONFIG", "VALIDATE_PILOT_WINDOW", "LOAD_AND_VALIDATE_INPUTS",
                   "CALCULATE_OR_LOAD_STRATEGY_RESULT", "BUILD_DAILY_PLAN"])

    # Idempotency / conflict against an existing journal.
    existing = journal.read()
    committed_states = {jr.DAILY_RECORD_COMMITTED, jr.EXCEL_BUILT, jr.NOTION_PREVIEW_BUILT,
                        jr.NOTION_SYNC_PASS, jr.NOTION_SYNC_FAIL, jr.NOTION_SYNC_SKIPPED,
                        jr.DISCORD_PREVIEW_BUILT, jr.DISCORD_NOTIFY_PASS, jr.DISCORD_NOTIFY_FAIL,
                        jr.DISCORD_NOTIFY_SKIPPED, jr.RUN_COMPLETED, jr.RUN_FAILED_AFTER_RECORD}
    if existing is not None:
        stored_fp = str(existing.get("plan_fingerprint", ""))
        if existing.get("state") in committed_states:
            if stored_fp == plan.plan_fingerprint:
                return RunResult(TASK_ID, mode, pilot_id, date, STATUS_ALREADY_COMMITTED_IDEMPOTENT, EXIT_OK,
                                 existing.get("state"), phases, plan.to_dict(), None, None, None, None,
                                 "identical rerun; daily record already committed")
            return RunResult(TASK_ID, mode, pilot_id, date, STATUS_DAILY_PLAN_CONFLICT, EXIT_CONFLICT,
                             existing.get("state"), phases, plan.to_dict(), None, None, None, None,
                             "plan/input fingerprint conflict with committed record")
        if stored_fp and stored_fp != plan.plan_fingerprint:
            return RunResult(TASK_ID, mode, pilot_id, date, STATUS_DAILY_PLAN_CONFLICT, EXIT_CONFLICT,
                             existing.get("state"), phases, plan.to_dict(), None, None, None, None,
                             "plan fingerprint conflict with prior run intent")

    # PERSIST_RUN_INTENT
    journal.init_journal(state=jr.RUN_INTENT_RECORDED, generated_at_utc=now,
                         extra={"plan_fingerprint": plan.plan_fingerprint,
                                "input_fingerprint": plan.input_fingerprint,
                                "strategy_name": plan.strategy_name})
    journal.write_json(jr.DAILY_PLAN_FILENAME, plan.to_dict())
    phases.append("PERSIST_RUN_INTENT")

    # APPEND_DAILY_RECORD
    record = _build_daily_record(plan, store, notes=f"{REASON_NOT_AUTHORIZED}; plan_fp={plan.plan_fingerprint[:12]}")
    try:
        store.append_daily(record)
    except DuplicateRecordError:
        # Store already has this date but journal did not mark it committed.
        return RunResult(TASK_ID, mode, pilot_id, date, STATUS_DAILY_PLAN_CONFLICT, EXIT_CONFLICT,
                         journal.state(), phases, plan.to_dict(), None, None, None, None,
                         "daily record already present in store")
    daily_dict = record.to_dict()
    journal.transition(jr.DAILY_RECORD_COMMITTED, at_utc=now,
                       extra={"plan_fingerprint": plan.plan_fingerprint,
                              "input_fingerprint": plan.input_fingerprint})
    phases.append("APPEND_DAILY_RECORD")

    # APPEND_AUDIT_EVENTS
    store.append_audit(PilotAuditEvent(timestamp_utc=now, pilot_id=pilot_id, event_type="DRY_RUN_DAILY",
                                       component="daily_runner", status="OK",
                                       message=f"dry-run daily record committed; signals={plan.signal_count}",
                                       reference_id=plan.plan_fingerprint[:16]))
    phases.append("APPEND_AUDIT_EVENTS")

    # Immutable daily-core fingerprint (TASK-014BT): trading data is frozen here;
    # only output-delivery statuses may advance afterwards.
    core_fp = osm.compute_daily_core_fingerprint(
        pilot_id=pilot_id, daily_record=daily_dict,
        input_fingerprint=plan.input_fingerprint, plan_fingerprint=plan.plan_fingerprint)
    status_store = osm.OutputStatusStore(pilot_id, output_root)
    builder = workbook_builder or _default_workbook_builder()

    # BUILD_EXCEL (#1 attempt) -> record Excel OK/FAIL.
    excel_result: dict[str, Any]
    try:
        paths = builder(pilot_id, output_root, snapshot_date=snapshot_date)
        excel_result = {"status": osm.STATUS_OK, **dict(paths)}
        journal.transition(jr.EXCEL_BUILT, at_utc=now)
    except Exception as exc:  # noqa: BLE001  (Excel failure must NOT rerun the daily record)
        excel_result = {"status": osm.STATUS_FAIL, "detail": str(exc)}
    excel_status = excel_result.get("status")
    excel_detail = str(excel_result.get("detail", "")) if excel_status == osm.STATUS_FAIL else ""
    phases.append("BUILD_EXCEL")

    # OPTIONAL_NOTION_SYNC -> record PASS/FAIL/SKIPPED.
    notion_result: dict[str, Any]
    interim_payload = ns.build_notion_payload(pilot_id, daily_dict,
                                              plan_fingerprint=plan.plan_fingerprint,
                                              input_fingerprint=plan.input_fingerprint)
    if config.notion_enabled and allow_notion_network:
        sync = notion_sync or ns.NotionDailySync(allow_network=True)
        res = sync.upsert(interim_payload)
        notion_result = res.to_dict()
        journal.transition(jr.NOTION_SYNC_PASS if res.status == ns.SYNC_PASS else jr.NOTION_SYNC_FAIL,
                           at_utc=now, extra={"notion_status": res.status})
    else:
        notion_result = {"status": ns.SYNC_SKIPPED, "network_attempted": False}
        journal.transition(jr.NOTION_SYNC_SKIPPED, at_utc=now, extra={"notion_status": ns.SYNC_SKIPPED})
    notion_status = notion_result.get("status")
    phases.append("OPTIONAL_NOTION_SYNC")

    # OPTIONAL_DISCORD_NOTIFY -> record PASS/FAIL/SKIPPED.
    discord_result: dict[str, Any]
    interim_summary = dn.build_discord_summary(pilot_id, daily_dict, data_status=plan.source_data_status,
                                               proposed_action_count=len(plan.proposed_actions),
                                               plan_fingerprint=plan.plan_fingerprint)
    if config.discord_enabled and allow_discord_network:
        notify = discord_notify or dn.DiscordDailyNotify(allow_network=True)
        res = notify.notify(interim_summary)
        discord_result = res.to_dict()
        journal.transition(jr.DISCORD_NOTIFY_PASS if res.status == dn.NOTIFY_PASS else jr.DISCORD_NOTIFY_FAIL,
                           at_utc=now, extra={"discord_status": res.status})
    else:
        discord_result = {"status": dn.NOTIFY_SKIPPED, "network_attempted": False}
        journal.transition(jr.DISCORD_NOTIFY_SKIPPED, at_utc=now, extra={"discord_status": dn.NOTIFY_SKIPPED})
    discord_status = discord_result.get("status")
    phases.append("OPTIONAL_DISCORD_NOTIFY")

    # PERSIST OUTPUT-STATUS LEDGER (effective statuses; immutable core unchanged).
    status_record = osm.OutputStatusRecord(
        pilot_id=pilot_id, date=date, excel_status=excel_status, notion_status=notion_status,
        discord_status=discord_status, excel_detail=excel_detail,
        notion_detail=str(notion_result.get("detail", "")), discord_detail=str(discord_result.get("detail", "")),
        updated_at_utc=now, plan_fingerprint=plan.plan_fingerprint,
        input_fingerprint=plan.input_fingerprint, daily_core_fingerprint=core_fp)
    status_store.record_status(status_record)

    # REGENERATE local previews with the FINAL effective statuses.
    effective = {**daily_dict, "excel_export_status": excel_status,
                 "notion_sync_status": notion_status, "discord_notify_status": discord_status}
    final_payload = ns.build_notion_payload(pilot_id, effective,
                                            plan_fingerprint=plan.plan_fingerprint,
                                            input_fingerprint=plan.input_fingerprint)
    journal.write_json(jr.NOTION_PAYLOAD_FILENAME, final_payload)
    journal.transition(jr.NOTION_PREVIEW_BUILT, at_utc=now)
    phases.append("BUILD_NOTION_PAYLOAD")
    final_summary = dn.build_discord_summary(pilot_id, effective, data_status=plan.source_data_status,
                                             proposed_action_count=len(plan.proposed_actions),
                                             plan_fingerprint=plan.plan_fingerprint)
    journal.write_text(jr.DISCORD_SUMMARY_FILENAME, final_summary)
    journal.transition(jr.DISCORD_PREVIEW_BUILT, at_utc=now)
    phases.append("BUILD_DISCORD_SUMMARY")

    # REBUILD EXCEL (#2) so the Daily Performance row shows the final statuses.
    if excel_status == osm.STATUS_OK:
        try:
            paths = builder(pilot_id, output_root, snapshot_date=snapshot_date)
            excel_result = {"status": osm.STATUS_OK, **dict(paths)}
        except Exception as exc:  # noqa: BLE001
            excel_result = {"status": osm.STATUS_FAIL, "detail": f"finalization rebuild failed: {exc}"}
            status_store.record_status(osm.OutputStatusRecord(
                pilot_id=pilot_id, date=date, excel_status=osm.STATUS_FAIL, notion_status=notion_status,
                discord_status=discord_status, excel_detail=str(excel_result.get("detail", "")),
                notion_detail="", discord_detail="", updated_at_utc=now,
                plan_fingerprint=plan.plan_fingerprint, input_fingerprint=plan.input_fingerprint,
                daily_core_fingerprint=core_fp))

    # WRITE_LATEST_SUMMARY
    store.write_latest_summary({
        "pilot_id": pilot_id, "date": date, "pilot_day": plan.pilot_day,
        "runner_status": record.runner_status, "signal_count": plan.signal_count,
        "order_count": 0, "filled_count": 0, "closed_trade_count": 0,
        "cumulative_net_pnl_usdt": dec_str(record.cumulative_net_pnl_usdt),
        "excel_export_status": excel_result.get("status"),
        "notion_sync_status": notion_status,
        "discord_notify_status": discord_status,
        "plan_fingerprint": plan.plan_fingerprint,
        "order_execution_authorized": ORDER_EXECUTION_AUTHORIZED,
    })
    phases.append("WRITE_LATEST_SUMMARY")

    # FINALIZE_RUN
    output_failed = (excel_result.get("status") == osm.STATUS_FAIL
                     or notion_status == ns.SYNC_FAIL or discord_status == dn.NOTIFY_FAIL)
    status = STATUS_PARTIAL_OUTPUT_FAILURE if output_failed else STATUS_COMPLETED
    exit_code = EXIT_PARTIAL_OUTPUT if output_failed else EXIT_OK
    journal.transition(jr.RUN_COMPLETED, at_utc=now, extra={"daily_core_fingerprint": core_fp})
    result = RunResult(TASK_ID, mode, pilot_id, date, status, exit_code, journal.state(), phases,
                       plan.to_dict(), effective, excel_result, notion_result, discord_result,
                       "dry-run completed" if not output_failed else "committed; output sync partial failure")
    result_dict = result.to_dict()
    result_dict["output_status"] = status_record.to_dict()
    journal.write_json(jr.RUN_RESULT_FILENAME, result_dict)
    phases.append("FINALIZE_RUN")
    return result


def _with_status(record: PilotDailyRecord, *, excel=None, notion=None, discord=None) -> PilotDailyRecord:
    import dataclasses as _dc
    changes: dict[str, Any] = {}
    if excel is not None:
        changes["excel_export_status"] = excel
    if notion is not None:
        changes["notion_sync_status"] = notion
    if discord is not None:
        changes["discord_notify_status"] = discord
    return _dc.replace(record, **changes)


def _reconcile_outputs(*, store, journal, pilot_id, date, config, notion_sync, discord_notify,
                       allow_notion_network, allow_discord_network, workbook_builder, snapshot_date,
                       clock) -> RunResult:
    """Rebuild Excel and retry ONLY failed/skipped Notion/Discord delivery.

    Never recomputes strategy, never appends a daily record, never modifies
    signal/order/fill/trade/PnL/position data."""
    now = _utc_now(clock)
    data = journal.read()
    if data is None:
        return RunResult(TASK_ID, MODE_RECONCILE, pilot_id, date, STATUS_INPUT_FAILURE, EXIT_INPUT_FAILURE,
                         None, [], None, None, None, None, None, "no committed run to reconcile")
    daily_rows = [r for r in store.read_daily() if r.get("date") == date]
    daily = daily_rows[-1] if daily_rows else None
    if daily is None:
        return RunResult(TASK_ID, MODE_RECONCILE, pilot_id, date, STATUS_INPUT_FAILURE, EXIT_INPUT_FAILURE,
                         data.get("state"), [], None, None, None, None, None, "no committed daily record")

    input_fp = str(data.get("input_fingerprint", ""))
    plan_fp = str(data.get("plan_fingerprint", ""))
    core_fp = osm.compute_daily_core_fingerprint(
        pilot_id=pilot_id, daily_record=daily, input_fingerprint=input_fp, plan_fingerprint=plan_fp)
    status_store = osm.OutputStatusStore(pilot_id, _root_of(store))
    try:
        status_store.assert_immutable_core_unchanged(date=date, expected_core_fp=core_fp)
    except osm.ImmutableDailyCoreConflict as exc:
        return RunResult(TASK_ID, MODE_RECONCILE, pilot_id, date, STATUS_DAILY_PLAN_CONFLICT, EXIT_CONFLICT,
                         data.get("state"), ["RECONCILE_OUTPUTS"], None, daily, None, None, None, str(exc))

    prior = status_store.latest_by_date().get(date, {})
    prior_excel = str(prior.get("excel_status", osm.STATUS_PENDING))
    prior_notion = str(prior.get("notion_status", ns.SYNC_SKIPPED))
    prior_discord = str(prior.get("discord_status", dn.NOTIFY_SKIPPED))

    # Retry ONLY FAIL/SKIPPED deliveries (leave PASS untouched).
    notion_result: dict[str, Any] = {"status": prior_notion, "network_attempted": False}
    if config.notion_enabled and allow_notion_network and prior_notion in (ns.SYNC_FAIL, ns.SYNC_SKIPPED):
        payload = ns.build_notion_payload(pilot_id, daily, plan_fingerprint=plan_fp, input_fingerprint=input_fp)
        sync = notion_sync or ns.NotionDailySync(allow_network=True)
        res = sync.upsert(payload)
        notion_result = res.to_dict()
        journal.transition(jr.NOTION_SYNC_PASS if res.status == ns.SYNC_PASS else jr.NOTION_SYNC_FAIL, at_utc=now,
                           extra={"reconcile": True, "notion_status": res.status})
    new_notion = notion_result.get("status", prior_notion)

    discord_result: dict[str, Any] = {"status": prior_discord, "network_attempted": False}
    if config.discord_enabled and allow_discord_network and prior_discord in (dn.NOTIFY_FAIL, dn.NOTIFY_SKIPPED):
        summary = dn.build_discord_summary(pilot_id, daily)
        notify = discord_notify or dn.DiscordDailyNotify(allow_network=True)
        res = notify.notify(summary)
        discord_result = res.to_dict()
        journal.transition(jr.DISCORD_NOTIFY_PASS if res.status == dn.NOTIFY_PASS else jr.DISCORD_NOTIFY_FAIL, at_utc=now,
                           extra={"reconcile": True, "discord_status": res.status})
    new_discord = discord_result.get("status", prior_discord)

    # Rebuild Excel with the latest statuses (does not touch the daily record).
    builder = workbook_builder or _default_workbook_builder()
    excel_status = prior_excel if prior_excel in (osm.STATUS_OK,) else osm.STATUS_OK
    try:
        # Persist statuses BEFORE rebuilding so the workbook row reflects them.
        status_store.record_status(osm.OutputStatusRecord(
            pilot_id=pilot_id, date=date, excel_status=osm.STATUS_OK, notion_status=new_notion,
            discord_status=new_discord, excel_detail="", notion_detail=str(notion_result.get("detail", "")),
            discord_detail=str(discord_result.get("detail", "")), updated_at_utc=now,
            plan_fingerprint=plan_fp, input_fingerprint=input_fp, daily_core_fingerprint=core_fp))
        paths = builder(pilot_id, _root_of(store), snapshot_date=snapshot_date)
        excel_result = {"status": osm.STATUS_OK, **dict(paths)}
        journal.transition(jr.EXCEL_BUILT, at_utc=now, extra={"reconcile": True})
    except Exception as exc:  # noqa: BLE001
        excel_result = {"status": osm.STATUS_FAIL, "detail": str(exc)}
        status_store.record_status(osm.OutputStatusRecord(
            pilot_id=pilot_id, date=date, excel_status=osm.STATUS_FAIL, notion_status=new_notion,
            discord_status=new_discord, excel_detail=str(exc), notion_detail="", discord_detail="",
            updated_at_utc=now, plan_fingerprint=plan_fp, input_fingerprint=input_fp,
            daily_core_fingerprint=core_fp))

    # REGENERATE local previews from the FINAL effective statuses (TASK-014BU).
    effective = {**daily, "excel_export_status": excel_result.get("status"),
                 "notion_sync_status": new_notion, "discord_notify_status": new_discord}
    final_payload = ns.build_notion_payload(pilot_id, effective, plan_fingerprint=plan_fp,
                                            input_fingerprint=input_fp)
    journal.write_json(jr.NOTION_PAYLOAD_FILENAME, final_payload)
    final_summary = dn.build_discord_summary(pilot_id, effective)
    journal.write_text(jr.DISCORD_SUMMARY_FILENAME, final_summary)

    store.append_audit(PilotAuditEvent(timestamp_utc=now, pilot_id=pilot_id, event_type="RECONCILE_OUTPUTS",
                                       component="daily_runner", status="OK",
                                       message="reconcile rebuilt excel / regenerated previews / retried delivery",
                                       reference_id=date))
    failed = excel_result.get("status") == osm.STATUS_FAIL or new_notion == ns.SYNC_FAIL \
        or new_discord == dn.NOTIFY_FAIL
    result = RunResult(TASK_ID, MODE_RECONCILE, pilot_id, date,
                       STATUS_PARTIAL_OUTPUT_FAILURE if failed else STATUS_RECONCILED,
                       EXIT_PARTIAL_OUTPUT if failed else EXIT_OK, journal.state(), ["RECONCILE_OUTPUTS"],
                       None, daily, excel_result, notion_result, discord_result, "reconcile complete")
    result_dict = result.to_dict()
    result_dict["output_status"] = {"excel_status": excel_result.get("status"),
                                    "notion_status": new_notion, "discord_status": new_discord}
    journal.write_json(jr.RUN_RESULT_FILENAME, result_dict)
    return result


def _root_of(store: PilotStore) -> str:
    # store.dir == <root>/<pilot_id>; return <root>.
    return str(store.dir.parent)


__all__ = [
    "EXIT_CONFLICT",
    "EXIT_INPUT_FAILURE",
    "EXIT_INVALID",
    "EXIT_OK",
    "EXIT_PARTIAL_OUTPUT",
    "EXIT_SAFETY",
    "EXPECTED_STRATEGY_NAME",
    "ELIGIBLE",
    "IDENTITY",
    "INVALID_BLOCKED",
    "MODES",
    "MODE_DRY_RUN",
    "MODE_PLAN",
    "MODE_RECONCILE",
    "NO_ACTION",
    "ORDER_EXECUTION_AUTHORIZED",
    "PHASES",
    "PRIMARY_FORWARD_RUN_KEY",
    "PROTECTED_BLOCKED",
    "PROTECTED_SYMBOLS",
    "PilotDailyExecutionPlan",
    "REASON_NOT_AUTHORIZED",
    "RunResult",
    "SHADOW_FORWARD_RUN_KEY",
    "STATUS_ALREADY_COMMITTED_IDEMPOTENT",
    "STATUS_COMPLETED",
    "STATUS_DAILY_PLAN_CONFLICT",
    "STATUS_PARTIAL_OUTPUT_FAILURE",
    "STATUS_PLAN_ONLY",
    "STATUS_RECONCILED",
    "StrategyAmbiguousError",
    "TASK_ID",
    "build_plan",
    "classify_actions",
    "normalize_signals",
    "resolve_strategy_name",
    "run_daily",
]
