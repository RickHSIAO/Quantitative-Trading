# TASK-005 VPS Bot Monitor

This package is an observer-only monitor for TASK-005. It writes local
heartbeat, alert, setup log, and review artifacts. It does not contain an
exchange client and it does not control the trading process.

## Modules

- `config.py`: loads and validates `configs/monitor.yaml`.
- `heartbeat.py`: builds heartbeat rows and writes parquet output.
- `alerts.py`: creates alert rows, deduplicates them, and writes JSONL output.
- `channels/`: dispatches alerts to local JSONL, Telegram, or Discord.
- `log_scanner.py`: reads configured local log files for error markers.
- `schema.py`: validates heartbeat parquet and alerts JSONL schemas.
- `safety.py`: checks secret ignore rules and forbidden monitor behavior.
- `report.py`: builds REVIEW-005 packet, numbers JSON, and setup log text.

## Run

```powershell
python scripts\task005_vps_bot_monitor.py --output-date 20260517
```

The default run generates sample local artifacts only. Secrets must come from
environment variables or an ignored local config file. Do not create or commit
secret material under the repository.

## Alert Channels

`local_jsonl` remains the durable local alert record and must stay enabled.
Telegram and Discord channels are configured in `configs/monitor.yaml` with
`dry_run: true` by default. In dry-run mode the monitor records that it would
send a notification, but it does not make an external POST.

Use `--test-send` only as an explicit operator action. With the default config
it still stays dry-run. Real channel credentials must be provided only through
environment variables or `configs/monitor_secrets.local.yaml`, which is ignored
by Git. The committed `configs/monitor_secrets.example.yaml` file contains only
empty placeholders.

Supported environment variables:

- `MONITOR_TELEGRAM_TOKEN`
- `MONITOR_TELEGRAM_CHAT_ID`
- `MONITOR_DISCORD_WEBHOOK_URL`

Logs, outputs, review packets, and command logs must contain redacted channel
metadata only.

## Boundaries

- Read-only account observation only.
- No trading action interface.
- No automated process-control action.
- No paper execution.
- No live trading.
