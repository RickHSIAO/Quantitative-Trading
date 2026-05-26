#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_forward_record_daily.sh
# 30-day forward validation daily runner (DRY-RUN ONLY)
#
# Safety invariants — this script MUST NOT be modified to remove these:
#   --dry-run is MANDATORY (script aborts if absent from command)
#   live trading = FORBIDDEN
#   paper execution = FORBIDDEN
#   Discord live alerts = FORBIDDEN
#   Bybit write API = NOT called
#
# Designed for VPS: instance-20260506-0945 (Ubuntu 24.04)
# Cron schedule: 10 10 * * *  (10:10 UTC = 18:10 Asia/Taipei daily)
# ---------------------------------------------------------------------------

set -euo pipefail

# --- Configuration ----------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON="${PROJECT_ROOT}/.venv/bin/python"
CONFIG="${PROJECT_ROOT}/configs/prev3y_crypto.yaml"
OUTPUT_DIR="${PROJECT_ROOT}/outputs/forward_record/prev3y_crypto"
LOG_DIR="${PROJECT_ROOT}/outputs/forward_record/daily_logs"

# --- Safety guard: --dry-run MUST be in the command we build ----------------
SAFETY_FLAG="--dry-run"

# --- Compute today in Asia/Taipei ------------------------------------------
DATE_TAIPEI="$("${PYTHON}" -c "
from datetime import datetime
import zoneinfo
print(datetime.now(zoneinfo.ZoneInfo('Asia/Taipei')).strftime('%Y%m%d'))
")"

# --- Validate date format ---------------------------------------------------
if ! [[ "${DATE_TAIPEI}" =~ ^[0-9]{8}$ ]]; then
    echo "ERROR: invalid date: ${DATE_TAIPEI}" >&2
    exit 1
fi

# --- Prepare log directory --------------------------------------------------
mkdir -p "${LOG_DIR}"
RUN_LOG="${LOG_DIR}/${DATE_TAIPEI}_run.log"

# --- Log header -------------------------------------------------------------
{
echo "=================================================="
echo "run_forward_record_daily.sh"
echo "date_taipei=${DATE_TAIPEI}"
echo "run_ts=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "project_root=${PROJECT_ROOT}"
echo "python=${PYTHON}"
echo "safety_flag=${SAFETY_FLAG}"
echo "paper_execution_status=FORBIDDEN"
echo "live_trading_status=FORBIDDEN"
echo "bybit_connection=NOT_ATTEMPTED"
echo "=================================================="
} | tee "${RUN_LOG}"

# --- Safety check: verify --dry-run is present in our command ---------------
CMD=(
    "${PYTHON}"
    "scripts/run_forward_record.py"
    "--date" "${DATE_TAIPEI}"
    "--config" "${CONFIG}"
    "--output-dir" "${OUTPUT_DIR}"
    "${SAFETY_FLAG}"
)

# Abort if --dry-run is somehow missing from CMD array
DRY_RUN_PRESENT=0
for arg in "${CMD[@]}"; do
    if [[ "${arg}" == "--dry-run" ]]; then
        DRY_RUN_PRESENT=1
        break
    fi
done

if [[ "${DRY_RUN_PRESENT}" -ne 1 ]]; then
    echo "FATAL: --dry-run not found in command. Aborting." | tee -a "${RUN_LOG}" >&2
    exit 2
fi

# --- Run forward record -----------------------------------------------------
echo "Running: ${CMD[*]}" | tee -a "${RUN_LOG}"
cd "${PROJECT_ROOT}"

set +e
"${CMD[@]}" 2>&1 | tee -a "${RUN_LOG}"
EXIT_CODE="${PIPESTATUS[0]}"
set -e

# --- Log footer (forward record) --------------------------------------------
{
echo "=================================================="
echo "exit_code=${EXIT_CODE}"
echo "paper_execution_status=FORBIDDEN"
echo "live_trading_status=FORBIDDEN"
echo "=================================================="
} | tee -a "${RUN_LOG}"

if [[ "${EXIT_CODE}" -ne 0 ]]; then
    echo "ERROR: forward record exited with code ${EXIT_CODE}" >&2
    exit "${EXIT_CODE}"
fi

echo "DONE: ${DATE_TAIPEI} forward record complete → ${RUN_LOG}"

# ---------------------------------------------------------------------------
# TASK-010 / TASK-010B: Paper Portfolio PnL engine
#   Runs BEFORE dashboard so dashboard can overlay daily_pnl_pct /
#   cumulative_pnl_pct / max_dd_pct from the paper portfolio JSON.
#
# DEFAULT (cron): write mode — produces state.json, daily_pnl.csv,
#   {date}_paper_pnl.json under outputs/forward_record/paper_portfolio/.
#
# MANUAL dry-run (testing): set PAPER_PNL_DRY_RUN=1 before invoking this
#   script to pass --dry-run to the engine (no files written).
#   Example: PAPER_PNL_DRY_RUN=1 bash scripts/run_forward_record_daily.sh
#
# Safety: runs in isolation (set +e). Failure is non-fatal.
# Tokens: PAPER_PNL=PASS | PAPER_PNL=DRY_RUN | PAPER_PNL=SKIP | PAPER_PNL=FAIL
# ---------------------------------------------------------------------------
echo "--------------------------------------------------" | tee -a "${RUN_LOG}"
echo "PAPER_PNL: starting paper_portfolio_engine.py" | tee -a "${RUN_LOG}"

PAPER_SCRIPT="${PROJECT_ROOT}/scripts/paper_portfolio_engine.py"

# Honour optional env var for manual dry-run testing (default: write mode)
if [[ "${PAPER_PNL_DRY_RUN:-0}" == "1" ]]; then
    PAPER_FLAGS="--dry-run"
    echo "PAPER_PNL: dry-run mode (PAPER_PNL_DRY_RUN=1)" | tee -a "${RUN_LOG}"
else
    PAPER_FLAGS=""
    echo "PAPER_PNL: write mode (outputs/forward_record/paper_portfolio/)" | tee -a "${RUN_LOG}"
fi

if [[ ! -f "${PAPER_SCRIPT}" ]]; then
    echo "PAPER_PNL=SKIP (script not found: ${PAPER_SCRIPT})" | tee -a "${RUN_LOG}"
else
    set +e
    # shellcheck disable=SC2086
    PAPER_OUTPUT="$( cd "${PROJECT_ROOT}" && "${PYTHON}" "${PAPER_SCRIPT}" ${PAPER_FLAGS} 2>&1 )"
    PAPER_EXIT=$?
    set -e

    if [[ "${PAPER_EXIT}" -eq 0 ]]; then
        {
        echo "PAPER_PNL_OUTPUT_BEGIN"
        echo "${PAPER_OUTPUT}"
        echo "PAPER_PNL_OUTPUT_END"
        } | tee -a "${RUN_LOG}"
        PAPER_STATUS="$(echo "${PAPER_OUTPUT}" | grep "PAPER_PNL=" | tail -1)"
        echo "${PAPER_STATUS:-PAPER_PNL=PASS}"
    else
        {
        echo "PAPER_PNL=FAIL (exit_code=${PAPER_EXIT})"
        echo "PAPER_PNL_ERROR_BEGIN"
        echo "${PAPER_OUTPUT}"
        echo "PAPER_PNL_ERROR_END"
        } | tee -a "${RUN_LOG}" >&2
        echo "WARNING: paper portfolio engine failed — forward record data is intact" >&2
        # NOTE: paper failure is non-fatal. Runner continues.
    fi
fi

# ---------------------------------------------------------------------------
# TASK-007B: Build dashboard after successful forward record
#
# Safety: dashboard build runs in isolation (set +e).
# A dashboard failure MUST NOT destroy forward record data or cause
# data loss. It only affects the dashboard output files.
# Result is written to the same daily log so cron.log captures it.
# ---------------------------------------------------------------------------
echo "--------------------------------------------------" | tee -a "${RUN_LOG}"
echo "DASHBOARD_BUILD: starting build_forward_validation_dashboard.py" | tee -a "${RUN_LOG}"

DASHBOARD_SCRIPT="${PROJECT_ROOT}/scripts/build_forward_validation_dashboard.py"

if [[ ! -f "${DASHBOARD_SCRIPT}" ]]; then
    echo "DASHBOARD_BUILD=FAIL (script not found: ${DASHBOARD_SCRIPT})" | tee -a "${RUN_LOG}" >&2
else
    set +e
    DASHBOARD_OUTPUT="$("${PYTHON}" "${DASHBOARD_SCRIPT}" 2>&1)"
    DASHBOARD_EXIT="${?}"
    set -e

    if [[ "${DASHBOARD_EXIT}" -eq 0 ]]; then
        {
        echo "DASHBOARD_BUILD=PASS"
        echo "${DASHBOARD_OUTPUT}"
        } | tee -a "${RUN_LOG}"
        echo "DASHBOARD_BUILD=PASS: outputs/forward_record/dashboard/ updated"
    else
        {
        echo "DASHBOARD_BUILD=FAIL (exit_code=${DASHBOARD_EXIT})"
        echo "DASHBOARD_ERROR_BEGIN"
        echo "${DASHBOARD_OUTPUT}"
        echo "DASHBOARD_ERROR_END"
        } | tee -a "${RUN_LOG}" >&2
        echo "WARNING: dashboard build failed — forward record data is intact, dashboard not updated" >&2
        # NOTE: we do NOT exit non-zero here.
        # Forward record data is safe; dashboard failure is non-fatal.
    fi
fi

echo "--------------------------------------------------" | tee -a "${RUN_LOG}"

# ---------------------------------------------------------------------------
# TASK-008: Send Discord daily summary after dashboard build
#
# Safety: Discord notify runs in isolation (set +e).
# A notify failure MUST NOT affect forward record data or dashboard outputs.
# Behaviour:
#   DISCORD_NOTIFY=SKIP   -- MONITOR_DISCORD_WEBHOOK_URL not set (silent, exit 0)
#   DISCORD_NOTIFY=PASS   -- message delivered
#   DISCORD_NOTIFY=FAIL   -- send failed (error logged; runner still exits 0)
# ---------------------------------------------------------------------------
echo "--------------------------------------------------" | tee -a "${RUN_LOG}"
echo "DISCORD_NOTIFY: starting send_forward_discord_summary.py" | tee -a "${RUN_LOG}"

NOTIFY_SCRIPT="${PROJECT_ROOT}/scripts/send_forward_discord_summary.py"

if [[ ! -f "${NOTIFY_SCRIPT}" ]]; then
    echo "DISCORD_NOTIFY=SKIP (script not found: ${NOTIFY_SCRIPT})" | tee -a "${RUN_LOG}"
else
    set +e
    NOTIFY_OUTPUT="$("${PYTHON}" "${NOTIFY_SCRIPT}" 2>&1)"
    NOTIFY_EXIT="${?}"
    set -e

    if [[ "${NOTIFY_EXIT}" -eq 0 ]]; then
        {
        echo "${NOTIFY_OUTPUT}"
        } | tee -a "${RUN_LOG}"
        # Extract DISCORD_NOTIFY= line for visibility
        NOTIFY_STATUS="$(echo "${NOTIFY_OUTPUT}" | grep "DISCORD_NOTIFY=" | tail -1)"
        echo "${NOTIFY_STATUS:-DISCORD_NOTIFY=PASS}"
    else
        {
        echo "DISCORD_NOTIFY=FAIL (exit_code=${NOTIFY_EXIT})"
        echo "DISCORD_ERROR_BEGIN"
        echo "${NOTIFY_OUTPUT}"
        echo "DISCORD_ERROR_END"
        } | tee -a "${RUN_LOG}" >&2
        echo "WARNING: Discord notify failed — forward record data and dashboard are intact" >&2
        # NOTE: we do NOT exit non-zero here.
        # Discord failure is non-fatal.
    fi
fi

echo "--------------------------------------------------" | tee -a "${RUN_LOG}"

# ---------------------------------------------------------------------------
# TASK-009: Sync 30-day forward validation dashboard to Notion
#
# Safety: Notion sync runs in isolation (set +e).
# A sync failure MUST NOT affect forward record data, dashboard, or Discord.
# Behaviour:
#   NOTION_SYNC=SKIP    -- NOTION_TOKEN or DB id env var not set (silent, exit 0)
#   NOTION_SYNC=PASS    -- upsert succeeded
#   NOTION_SYNC=FAIL    -- schema missing or API error (logged; runner still exits 0)
#   NOTION_SYNC=DRY_RUN -- only when invoked with --dry-run (not in cron path)
# ---------------------------------------------------------------------------
echo "--------------------------------------------------" | tee -a "${RUN_LOG}"
echo "NOTION_SYNC: starting sync_forward_validation_to_notion.py" | tee -a "${RUN_LOG}"

NOTION_SCRIPT="${PROJECT_ROOT}/scripts/sync_forward_validation_to_notion.py"

if [[ ! -f "${NOTION_SCRIPT}" ]]; then
    echo "NOTION_SYNC=SKIP (script not found: ${NOTION_SCRIPT})" | tee -a "${RUN_LOG}"
else
    set +e
    NOTION_OUTPUT="$("${PYTHON}" "${NOTION_SCRIPT}" 2>&1)"
    NOTION_EXIT="${?}"
    set -e

    if [[ "${NOTION_EXIT}" -eq 0 ]]; then
        {
        echo "${NOTION_OUTPUT}"
        } | tee -a "${RUN_LOG}"
        # Extract NOTION_SYNC= line for visibility
        NOTION_STATUS="$(echo "${NOTION_OUTPUT}" | grep "NOTION_SYNC=" | tail -1)"
        echo "${NOTION_STATUS:-NOTION_SYNC=PASS}"
    else
        {
        echo "NOTION_SYNC=FAIL (exit_code=${NOTION_EXIT})"
        echo "NOTION_ERROR_BEGIN"
        echo "${NOTION_OUTPUT}"
        echo "NOTION_ERROR_END"
        } | tee -a "${RUN_LOG}" >&2
        echo "WARNING: Notion sync failed — forward record, dashboard, and Discord are intact" >&2
        # NOTE: we do NOT exit non-zero here.
        # Notion failure is non-fatal.
    fi
fi

echo "--------------------------------------------------" | tee -a "${RUN_LOG}"
echo "ALL_DONE: ${DATE_TAIPEI} forward record + paper_pnl + dashboard + discord + notion complete → ${RUN_LOG}"
