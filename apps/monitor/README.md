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

`local_jsonl` remains the durable local alert record and must stay enabled