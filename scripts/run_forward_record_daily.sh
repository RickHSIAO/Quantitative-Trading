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
echo "ALL_DONE: ${DATE_TAIPEI} forward record + dashboard complete → ${RUN_LOG}"
