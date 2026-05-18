# VPS Daily Runner — 30-day Forward Validation

## Purpose

Runs the approved forward-record dry-run command once per day on the VPS during the 30-day validation clock (2026-05-18 → 2026-06-17).

## Safety Invariants

- `--dry-run` MANDATORY (script aborts if missing)
- `live_trading_status = FORBIDDEN`
- `paper_execution_status = FORBIDDEN`
- `external_post_attempted = False`
- `bybit_connection = NOT_ATTEMPTED`
- No Discord live alerts

## Schedule

| Parameter | Value |
|---|---|
| Cron (UTC) | `10 10 * * *` |
| Time (UTC) | 10:10 UTC |
| Time (Taipei) | 18:10 CST (UTC+8, no DST) |
| Frequency | Daily |

## One-time VPS Setup

Run once on the VPS (instance-20260506-0945):

```bash
cd ~/quant
git pull                                          # sync scripts
bash scripts/install_cron_daily_runner.sh         # installs cron entry
crontab -l                                        # verify
```

## Manual Verification

```bash
# Check cron is installed
crontab -l | grep forward_record_daily_30d

# Check log dir
ls -la ~/quant/outputs/forward_record/daily_logs/

# Dry-run test (safe — idempotent for same date)
bash ~/quant/scripts/run_forward_record_daily.sh
```

## Daily Log Location

```
outputs/forward_record/daily_logs/YYYYMMDD_run.log   # per-day stdout/stderr
outputs/forward_record/daily_logs/cron.log            # cron combined log
```

## Cron Entry (exact)

```
10 10 * * * bash /home/ubuntu/quant/scripts/run_forward_record_daily.sh >> /home/ubuntu/quant/outputs/forward_record/daily_logs/cron.log 2>&1 # forward_record_daily_30d
```

## Files

| File | Purpose |
|---|---|
| `scripts/run_forward_record_daily.sh` | Daily runner (safe, idempotent) |
| `scripts/install_cron_daily_runner.sh` | One-time cron installer for VPS |
| `outputs/forward_record/daily_logs/` | Per-day run logs |
