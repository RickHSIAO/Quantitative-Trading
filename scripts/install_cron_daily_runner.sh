#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# install_cron_daily_runner.sh
# Adds the 30-day forward validation daily cron job on VPS.
# Run once on the VPS: bash scripts/install_cron_daily_runner.sh
#
# Schedule: 10:10 UTC = 18:10 Asia/Taipei (CST, UTC+8, no DST) daily
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DAILY_SCRIPT="${PROJECT_ROOT}/scripts/run_forward_record_daily.sh"
CRON_LOG="${PROJECT_ROOT}/outputs/forward_record/daily_logs/cron.log"
CRON_TAG="# forward_record_daily_30d"

# Guard: script must exist and be readable
if [[ ! -f "${DAILY_SCRIPT}" ]]; then
    echo "ERROR: ${DAILY_SCRIPT} not found" >&2
    exit 1
fi

# Make executable
chmod +x "${DAILY_SCRIPT}"
echo "chmod +x: ${DAILY_SCRIPT}"

# Create log dir
mkdir -p "$(dirname "${CRON_LOG}")"
echo "log dir: $(dirname "${CRON_LOG}")"

# Cron entry: 10:10 UTC daily
CRON_ENTRY="10 10 * * * bash ${DAILY_SCRIPT} >> ${CRON_LOG} 2>&1 ${CRON_TAG}"

# Check if already installed
if crontab -l 2>/dev/null | grep -q "${CRON_TAG}"; then
    echo "Cron entry already installed:"
    crontab -l | grep "${CRON_TAG}"
    exit 0
fi

# Install
(crontab -l 2>/dev/null || true; echo "${CRON_ENTRY}") | crontab -
echo "Installed cron entry:"
crontab -l | grep "${CRON_TAG}"
echo ""
echo "Schedule: 10 10 * * * (10:10 UTC = 18:10 Asia/Taipei)"
echo "Next run: tomorrow 18:10 CST / 10:10 UTC"
