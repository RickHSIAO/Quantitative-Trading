# Next Action

## Status
WAITING

## Owner
Rick

## Task
30-day forward validation clock RUNNING（Day 1 done）。
VPS daily runner script created + verified（scheduler install pending on VPS）。
Rick must run `bash scripts/install_cron_daily_runner.sh` on VPS to activate daily automation.

## 30-day Clock Status

| field | value |
|---|---|
| clock_started | TRUE |
| start_date | 2026-05-18（Day 1） |
| start_time_UTC | 2026-05-18T10:06:43Z |
| start_time_Taipei | 2026-05-18T18:06:43 CST |
| end_date_target | 2026-06-17 |
| validation_mode | forward-record / dry-run only |
| paper_execution_status | FORBIDDEN |
| live_trading_status | FORBIDDEN |
| clock_paused | false |
| days_completed | 1 |
| days_remaining | 29 |

## VPS Daily Runner Status

| item | status |
|---|---|
| scripts/run_forward_record_daily.sh | CREATED（bash -n OK, idempotency PASS） |
| scripts/install_cron_daily_runner.sh | CREATED（installs cron 10:10 UTC daily） |
| outputs/forward_record/daily_logs/ | CREATED（.gitkeep committed） |
| docs/research/commands/VPS_DAILY_RUNNER.md | CREATED |
| cron installed on VPS | PENDING（Rick must run install_cron_daily_runner.sh on VPS） |

## VPS One-time Setup (Rick action required)

On instance-20260506-0945:
  cd ~/quant
  git pull
  bash scripts/install_cron_daily_runner.sh
  crontab -l   # verify entry

## Daily Runner Spec

| parameter | value |
|---|---|
| scheduler | cron |
| schedule (UTC) | 10 10 * * * |
| schedule (Taipei) | 18:10 CST daily |
| runner script | scripts/run_forward_record_daily.sh |
| log dir | outputs/forward_record/daily_logs/ |
| next run (Day 2) | 2026-05-19T10:10Z / 18:10 CST |
| safety_flag | --dry-run MANDATORY (aborts if missing) |
| paper_execution_status | FORBIDDEN |
| live_trading_status | FORBIDDEN |

## Day 1 Run Summary (2026-05-18)

status=REVIEW_READY  signal_date=2026-04-30  positions=50  alerts=0/7
Artifacts: outputs/forward_record/prev3y_crypto/20260518_*

## Daily Action (each day on VPS)

Cron runs automatically at 18:10 CST once cron is installed.
Manual run: bash ~/quant/scripts/run_forward_record_daily.sh

## Paper Execution Gate 現況（5/7）
- TASK-007b DONE
- TASK-005 DONE
- TASK-005a DONE
- TASK-006 三補件 DONE
- Rick test-send DONE
- 30-day forward paper record（Day 1 done; 29 remaining）
- REVIEW-006b + Rick 批准（after day 30）

## Do Not
- 不得啟動 live trading
- 不得啟動 paper execution（FORBIDDEN）
- 不得把 discord dry_run 改為 false
- 不得送真實 Discord alert
- 不得使用 --live-alerts
- 不得連接 Bybit write API
- 不得修改策略程式或官方輸出
- 不得更改 clock start date（2026-05-18）
