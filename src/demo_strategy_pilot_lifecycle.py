"""TASK-014BX -- strategy-native lifecycle for the 7-successful-day Bybit Demo Pilot.

This module supersedes the previously proposed *artificial* inactive Pilot
caps and adds the explicit, one-time manual START authorization that may move
the Pilot from ``INACTIVE`` to ``RUNNING``. It also implements a narrowly
scoped, audited policy MIGRATION for an already-initialized INACTIVE state
whose fingerprint still encodes the old caps.

Rick's explicit decision (recorded verbatim in docs):
    This is a Bybit Demo-only strategy validation. Do NOT impose artificial
    Pilot trading limits that are not part of the strategy. The Pilot must
    execute according to the existing strategy's own rules.

Removed / superseded artificial caps (NO LONGER part of the active policy):
    * a fixed maximum of 1 opening order per day;
    * a fixed 10 USDT per-order notional cap;
    * a fixed 10 USDT daily opening-notional cap;
    * a fixed maximum of 1 simultaneous position;
    * a prohibition on averaging / pyramiding / adding / partial-closing /
      multi-position behaviour produced by the existing strategy.

Hard safety boundaries that REMAIN mandatory (never weakened here):
    1. Bybit Demo endpoint only.
    2. Live endpoint permanently denied; Live credentials never used.
    3. Existing protected-symbol exclusions remain
       (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT).
    4. No fallback from Demo to Live.
    5. No automatic retry that can create another order.
    6. Ambiguous outcome fails closed and requires reconciliation.

This module performs NO Bybit/Notion/Discord network call, sends NO order, and
imports neither ``main``, ``src.risk`` nor the live ``BybitExecutor``. Starting
the Pilot is a pure state transition; it does NOT itself execute any order.
Demo credential checks are PRESENCE-ONLY -- credential values are never read
into the state, printed, or serialized.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Mapping

from src import demo_strategy_pilot_readiness as rd

TASK_ID = "TASK-014BX"
SCHEMA_VERSION = 2  # strategy-native policy schema (supersedes the BW caps schema v1)

ENVIRONMENT = rd.ENVIRONMENT
TARGET_SUCCESSFUL_DAYS = rd.TARGET_SUCCESSFUL_DAYS
PROTECTED_SYMBOLS = rd.PROTECTED_SYMBOLS

# Demo credential env names (PRESENCE-ONLY; values never read here).
ENV_DEMO_API_KEY = "BYBIT_DEMO_API_KEY"
ENV_DEMO_API_SECRET = "BYBIT_DEMO_API_SECRET"

# The exact one-time start acknowledgement flag.
START_ACK_FLAG = (
    "i-authorize-strategy-native-automatic-bybit-demo-execution-for-this-7-day-pilot"
)
# The exact one-time policy-migration acknowledgement flag.
MIGRATION_ACK_FLAG = "i-acknowledge-strategy-native-policy-migration"

# Names of the artificial-cap keys that must be ABSENT from the active policy.
REMOVED_ARTIFICIAL_CAP_KEYS = (
    "max_new_opening_orders_per_successful_day",
    "max_simultaneous_open_positions",
    "max_per_order_notional_usdt",
    "max_daily_new_opening_notional_usdt",
)

REMOVED_ARTIFICIAL_CAPS = {
    "max_new_opening_orders_per_successful_day": "REMOVED_STRATEGY_NATIVE",
    "max_simultaneous_open_positions": "REMOVED_STRATEGY_NATIVE",
    "max_per_order_notional_usdt": "REMOVED_STRATEGY_NATIVE",
    "max_daily_new_opening_notional_usdt": "REMOVED_STRATEGY_NATIVE",
    "averaging_down_pyramiding_adding": "REMOVED_STRATEGY_NATIVE (allowed when strategy-produced)",
}

# The ACTIVE strategy-native safety policy. It intentionally contains NONE of
# the artificial cap keys above; all order count / sizing / position behaviour
# is whatever the existing strategy produces.
STRATEGY_NATIVE_SAFETY_POLICY: dict[str, Any] = {
    "environment": ENVIRONMENT,
    "live_endpoint": "PERMANENTLY_DENIED",
    "live_trading": "PERMANENTLY_DENIED",
    "live_credentials": "NEVER_USED",
    "demo_to_live_fallback": "FORBIDDEN",
    # Strategy-native behaviour (NO extra Pilot business caps).
    "strategy_native_order_count": "STRATEGY_DETERMINED_NO_PILOT_CAP",
    "strategy_native_sizing_notional": "STRATEGY_DETERMINED_NO_PILOT_CAP",
    "strategy_native_simultaneous_positions": "STRATEGY_DETERMINED_NO_PILOT_CAP",
    "averaging_pyramiding_adding_partial_close_multi_position":
        "ALLOWED_WHEN_STRATEGY_PRODUCED",
    "extra_pilot_business_caps": "NONE",
    "removed_artificial_caps": dict(REMOVED_ARTIFICIAL_CAPS),
    # Hard safety rules that remain mandatory.
    "automatic_order_retry": "FORBIDDEN",
    "close_orders": "REDUCE_ONLY_WHERE_REQUIRED_BY_EXCHANGE",
    "duplicate_same_pilot_date_signal": "FORBIDDEN_RECONCILE_NOT_RESEND",
    "incomplete_or_stale_data": "FAIL_CLOSED",
    "unsupported_symbol": "FAIL_CLOSED",
    "ambiguous_outcome": "FAIL_CLOSED_REQUIRE_RECONCILIATION",
    "protected_symbols": list(PROTECTED_SYMBOLS),
    # Authorization gates (only flipped by an explicit START on this Pilot id).
    "automatic_demo_execution": "AUTHORIZED_ONLY_AFTER_EXPLICIT_START",
    "manual_bo_bp_and_smoke_records": "EXCLUDED_FROM_PILOT_PERFORMANCE",
}

# Lifecycle states (re-exported from readiness for callers' convenience).
NOT_INITIALIZED = rd.NOT_INITIALIZED
INACTIVE = rd.INACTIVE
RUNNING = rd.RUNNING
BLOCKED = rd.BLOCKED
COMPLETED = rd.COMPLETED

# Status verdicts for migrate / start.
STATUS_MIGRATED = "MIGRATED_TO_STRATEGY_NATIVE"
STATUS_ALREADY_MIGRATED = "ALREADY_STRATEGY_NATIVE_IDEMPOTENT"
STATUS_STARTED = "STARTED_RUNNING"
STATUS_ALREADY_RUNNING = "ALREADY_RUNNING_IDEMPOTENT"
STATUS_NOT_INITIALIZED = rd.STATUS_NOT_INITIALIZED
STATUS_REFUSED_NOT_ACKNOWLEDGED = "REFUSED_NOT_ACKNOWLEDGED"
STATUS_REFUSED_MISSING_DEMO_CREDENTIALS = "REFUSED_MISSING_DEMO_CREDENTIALS"
STATUS_REFUSED_POLICY_NOT_MIGRATED = "REFUSED_POLICY_STILL_HAS_ARTIFICIAL_CAPS"
STATUS_BLOCKED = rd.STATUS_BLOCKED
STATUS_CONFLICTING = rd.STATUS_CONFLICTING_EXISTING_STATE

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_INVALID = 2
EXIT_CONFLICT = 5
EXIT_SAFETY = 6


def _utc_now(now: datetime | None = None) -> str:
    n = now or datetime.now(timezone.utc)
    return n.strftime("%Y-%m-%dT%H:%M:%SZ")


def strategy_native_fingerprint(pilot_id: str) -> str:
    """Configuration fingerprint of the strategy-native policy for ``pilot_id``."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "pilot_id": pilot_id,
        "environment": ENVIRONMENT,
        "target_successful_days": TARGET_SUCCESSFUL_DAYS,
        "policy": STRATEGY_NATIVE_SAFETY_POLICY,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def policy_has_artificial_caps(policy: Mapping[str, Any] | None) -> bool:
    """True if ``policy`` still encodes any removed artificial Pilot cap."""
    if not isinstance(policy, Mapping):
        return False
    if any(k in policy for k in REMOVED_ARTIFICIAL_CAP_KEYS):
        return True
    if str(policy.get("averaging_down_pyramiding_adding", "")).upper() == "FORBIDDEN":
        return True
    return False


def policy_is_strategy_native(policy: Mapping[str, Any] | None) -> bool:
    """True only for a fully strategy-native active policy (no artificial caps)."""
    if not isinstance(policy, Mapping):
        return False
    if policy_has_artificial_caps(policy):
        return False
    return policy.get("extra_pilot_business_caps") == "NONE"


def demo_credentials_present(env: Mapping[str, str] | None = None) -> bool:
    """PRESENCE-only check of Demo credentials. Values are never read/stored."""
    src = env if env is not None else os.environ
    key = (src.get(ENV_DEMO_API_KEY, "") or "").strip()
    secret = (src.get(ENV_DEMO_API_SECRET, "") or "").strip()
    return bool(key) and bool(secret)


# ---------------------------------------------------------------------------
# Migration: INACTIVE state with old caps -> INACTIVE state, strategy-native
# ---------------------------------------------------------------------------


def migrate_to_strategy_native(
    *,
    pilot_id: str,
    acknowledged: bool,
    output_root: str | os.PathLike[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Audited, narrowly scoped policy migration for an INACTIVE Pilot state.

    Replaces the artificial-cap policy with the strategy-native policy, records
    the new fingerprint, PRESERVES the original configuration fingerprint, and
    appends an append-only ``MIGRATION`` event. Idempotent: a second run after a
    completed migration returns ``ALREADY_STRATEGY_NATIVE_IDEMPOTENT`` and
    appends no further event. Never starts the Pilot, never executes an order,
    never deletes history, and refuses anything other than an INACTIVE state.
    """
    ts = _utc_now(now)
    try:
        rd.validate_pilot_id(pilot_id)
    except rd.PilotIdError as exc:
        return {"task_id": TASK_ID, "pilot_id": pilot_id,
                "status": rd.STATUS_INVALID_CONFIGURATION, "detail": str(exc)}

    if not acknowledged:
        return {"task_id": TASK_ID, "pilot_id": pilot_id,
                "status": STATUS_REFUSED_NOT_ACKNOWLEDGED,
                "detail": f"migration requires --{MIGRATION_ACK_FLAG}"}

    store = rd.PilotStateStore(pilot_id, output_root)
    state = store.read_state()
    if state is None:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": STATUS_NOT_INITIALIZED,
                "lifecycle_state": NOT_INITIALIZED,
                "detail": "no Pilot state to migrate; initialize first"}

    lifecycle = str(state.get("lifecycle_state"))
    if lifecycle != INACTIVE:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": STATUS_CONFLICTING,
                "lifecycle_state": lifecycle,
                "detail": f"migration only permitted from INACTIVE (found {lifecycle})"}

    target_fp = strategy_native_fingerprint(pilot_id)
    if policy_is_strategy_native(state.get("policy")) and \
            state.get("configuration_fingerprint") == target_fp:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": STATUS_ALREADY_MIGRATED,
                "lifecycle_state": lifecycle, "configuration_fingerprint": target_fp,
                "detail": "policy already strategy-native", "state": state}

    original_fp = state.get("original_configuration_fingerprint") \
        or state.get("configuration_fingerprint")
    new_state = dict(state)
    new_state.update({
        "schema_version": SCHEMA_VERSION,
        "policy": dict(STRATEGY_NATIVE_SAFETY_POLICY),
        "configuration_fingerprint": target_fp,
        "original_configuration_fingerprint": original_fp,
        "superseded_artificial_caps": dict(REMOVED_ARTIFICIAL_CAPS),
        "policy_migration": {
            "task_id": TASK_ID,
            "migrated_at_utc": ts,
            "from_fingerprint": original_fp,
            "to_fingerprint": target_fp,
        },
        "event_count": int(state.get("event_count", 0)) + 1,
    })
    store.write_state(new_state)
    store.append_event({
        "event": "MIGRATION", "at_utc": ts, "task_id": TASK_ID,
        "lifecycle_state": lifecycle,
        "original_configuration_fingerprint": original_fp,
        "new_configuration_fingerprint": target_fp,
        "removed_artificial_caps": list(REMOVED_ARTIFICIAL_CAP_KEYS),
    })
    return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": STATUS_MIGRATED,
            "lifecycle_state": lifecycle, "configuration_fingerprint": target_fp,
            "original_configuration_fingerprint": original_fp,
            "detail": "policy migrated to strategy-native", "state": new_state}


# ---------------------------------------------------------------------------
# Start: INACTIVE -> RUNNING (one-time, explicit authorization)
# ---------------------------------------------------------------------------


def start_pilot(
    *,
    pilot_id: str,
    acknowledged: bool,
    env: Mapping[str, str] | None = None,
    output_root: str | os.PathLike[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Explicit, one-time manual start: transition INACTIVE -> RUNNING exactly once.

    Requirements (all fail closed):
        * the Pilot state already exists and is INACTIVE;
        * the active policy is strategy-native (run ``migrate`` first otherwise);
        * readiness blockers are empty;
        * the exact one-time acknowledgement flag is supplied;
        * Demo credentials are present (PRESENCE only; values never read).

    On success it sets ``pilot_started`` / ``order_execution_authorized`` /
    ``automatic_execution_authorized`` / ``automatic_demo_execution_authorized``
    to True and ``live_trading_authorized`` to False, records ``started_at_utc``,
    and appends a single append-only ``START`` event. A repeated start on an
    already-RUNNING state is idempotent (no duplicate event). A COMPLETED or
    otherwise conflicting state fails closed. The authorization applies ONLY to
    this Pilot id and ONLY to Bybit Demo; it NEVER enables Live trading.
    """
    ts = _utc_now(now)
    try:
        rd.validate_pilot_id(pilot_id)
    except rd.PilotIdError as exc:
        return {"task_id": TASK_ID, "pilot_id": pilot_id,
                "status": rd.STATUS_INVALID_CONFIGURATION, "detail": str(exc),
                "live_trading_authorized": False}

    if not acknowledged:
        return {"task_id": TASK_ID, "pilot_id": pilot_id,
                "status": STATUS_REFUSED_NOT_ACKNOWLEDGED,
                "detail": f"start requires --{START_ACK_FLAG}",
                "live_trading_authorized": False}

    store = rd.PilotStateStore(pilot_id, output_root)
    state = store.read_state()
    if state is None:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": STATUS_NOT_INITIALIZED,
                "lifecycle_state": NOT_INITIALIZED,
                "detail": "no Pilot state; initialize and migrate first",
                "live_trading_authorized": False}

    lifecycle = str(state.get("lifecycle_state"))

    # Idempotent: already started/running on this pilot id -> no duplicate event.
    if lifecycle == RUNNING and state.get("pilot_started") is True:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": STATUS_ALREADY_RUNNING,
                "lifecycle_state": RUNNING, "pilot_started": True,
                "order_execution_authorized": state.get("order_execution_authorized", True),
                "automatic_execution_authorized": state.get("automatic_execution_authorized", True),
                "automatic_demo_execution_authorized":
                    state.get("automatic_demo_execution_authorized", True),
                "live_trading_authorized": False,
                "started_at_utc": state.get("started_at_utc"),
                "detail": "Pilot already RUNNING; start is idempotent", "state": state}

    if lifecycle == COMPLETED:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": STATUS_CONFLICTING,
                "lifecycle_state": COMPLETED,
                "detail": "Pilot already COMPLETED; cannot start", "live_trading_authorized": False}

    if lifecycle != INACTIVE:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": STATUS_CONFLICTING,
                "lifecycle_state": lifecycle,
                "detail": f"start only permitted from INACTIVE (found {lifecycle})",
                "live_trading_authorized": False}

    # Policy must be strategy-native (no artificial caps) before start.
    if not policy_is_strategy_native(state.get("policy")):
        return {"task_id": TASK_ID, "pilot_id": pilot_id,
                "status": STATUS_REFUSED_POLICY_NOT_MIGRATED, "lifecycle_state": INACTIVE,
                "detail": f"active policy still has artificial caps; run --mode migrate "
                          f"with --{MIGRATION_ACK_FLAG} first",
                "live_trading_authorized": False}

    # Readiness blockers must be empty.
    blocked = list(state.get("blocked_reasons", []) or [])
    if blocked:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": STATUS_BLOCKED,
                "lifecycle_state": INACTIVE, "blocked_reasons": blocked,
                "detail": "readiness blockers present; cannot start",
                "live_trading_authorized": False}

    # Demo credentials must be present (PRESENCE only).
    if not demo_credentials_present(env):
        return {"task_id": TASK_ID, "pilot_id": pilot_id,
                "status": STATUS_REFUSED_MISSING_DEMO_CREDENTIALS, "lifecycle_state": INACTIVE,
                "detail": "Demo credentials absent "
                          "(BYBIT_DEMO_API_KEY / BYBIT_DEMO_API_SECRET presence required)",
                "live_trading_authorized": False}

    new_state = dict(state)
    new_state.update({
        "lifecycle_state": RUNNING,
        "started_at_utc": ts,
        "pilot_started": True,
        "order_execution_authorized": True,
        "automatic_execution_authorized": True,
        "automatic_demo_execution_authorized": True,
        "live_trading_authorized": False,
        "start_authorization": {
            "task_id": TASK_ID,
            "acknowledgement_flag": START_ACK_FLAG,
            "scope": "THIS_PILOT_ID_AND_BYBIT_DEMO_ONLY",
            "started_at_utc": ts,
        },
        "event_count": int(state.get("event_count", 0)) + 1,
    })
    store.write_state(new_state)
    store.append_event({
        "event": "START", "at_utc": ts, "task_id": TASK_ID,
        "from_lifecycle_state": INACTIVE, "to_lifecycle_state": RUNNING,
        "acknowledgement_flag": START_ACK_FLAG,
        "automatic_demo_execution_authorized": True,
        "live_trading_authorized": False,
        "demo_credentials_present": True,
    })
    return {"task_id": TASK_ID, "pilot_id": pilot_id, "status": STATUS_STARTED,
            "lifecycle_state": RUNNING, "pilot_started": True,
            "order_execution_authorized": True,
            "automatic_execution_authorized": True,
            "automatic_demo_execution_authorized": True,
            "live_trading_authorized": False, "started_at_utc": ts,
            "detail": "Pilot started (Bybit Demo only); Live trading NOT authorized",
            "state": new_state}


__all__ = [
    "ENV_DEMO_API_KEY",
    "ENV_DEMO_API_SECRET",
    "EXIT_BLOCKED",
    "EXIT_CONFLICT",
    "EXIT_INVALID",
    "EXIT_OK",
    "EXIT_SAFETY",
    "MIGRATION_ACK_FLAG",
    "PROTECTED_SYMBOLS",
    "REMOVED_ARTIFICIAL_CAPS",
    "REMOVED_ARTIFICIAL_CAP_KEYS",
    "SCHEMA_VERSION",
    "START_ACK_FLAG",
    "STATUS_ALREADY_MIGRATED",
    "STATUS_ALREADY_RUNNING",
    "STATUS_BLOCKED",
    "STATUS_CONFLICTING",
    "STATUS_MIGRATED",
    "STATUS_NOT_INITIALIZED",
    "STATUS_REFUSED_MISSING_DEMO_CREDENTIALS",
    "STATUS_REFUSED_NOT_ACKNOWLEDGED",
    "STATUS_REFUSED_POLICY_NOT_MIGRATED",
    "STATUS_STARTED",
    "STRATEGY_NATIVE_SAFETY_POLICY",
    "TASK_ID",
    "demo_credentials_present",
    "migrate_to_strategy_native",
    "policy_has_artificial_caps",
    "policy_is_strategy_native",
    "start_pilot",
    "strategy_native_fingerprint",
]
