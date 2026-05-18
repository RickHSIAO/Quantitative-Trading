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


## TASK-007 Dashboard Status

| item | status |
|---|---|
| scripts/build_forward_validation_dashboard.py | DONE (py_compile OK, run OK) |
| outputs/forward_record/dashboard/index.html | DONE (7343B) |
| outputs/forward_record/dashboard/latest_summary.md | DONE (1462B) |
| outputs/forward_record/dashboard/validation_30d.csv | DONE (2 rows) |
| safety_self_check | PASS |
| order endpoint called | False |
| How to run | python3 scripts/build_forward_validation_dashboard.py |

## TASK-007B Auto Dashboard Status

| item | status |
|---|---|
| scripts/run_forward_record_daily.sh | UPDATED — dashboard build appended post-run |
| DASHBOARD_BUILD=PASS log on success | IMPLEMENTED |
| DASHBOARD_BUILD=FAIL log on failure | IMPLEMENTED (non-fatal, forward data preserved) |
| bash -n syntax | PASS |
| py_compile dashboard builder | PASS |
| --dry-run guard | PASS (exit 2 if missing) |
| dashboard FAIL isolation | PASS (script exits 0 even if dashboard fails) |
| Cron auto-updates dashboard | YES — after cron installs on VPS |
| How to test manually (VPS) | bash scripts/run_forward_record_daily.sh |
| Standalone dashboard rebuild | python3 scripts/build_forward_validation_dashboard.py |

## TASK-008 Discord Daily Summary Status

| item | status |
|---|---|
| scripts/send_forward_discord_summary.py | DONE (py_compile OK, dry-run OK) |
| run_forward_record_daily.sh TASK-008 section | DONE (appended after dashboard build) |
| DISCORD_NOTIFY=SKIP (no webhook) | IMPLEMENTED |
| DISCORD_NOTIFY=DRY_RUN (--dry-run) | IMPLEMENTED |
| DISCORD_NOTIFY=PASS/FAIL | IMPLEMENTED |
| Discord failure isolation | PASS (runner exits 0 even on Discord fail) |
| Environment variable | MONITOR_DISCORD_WEBHOOK_URL |
| Cron auto-sends Discord | YES (after VPS cron install + webhook set) |
| Dry-run test | python3 scripts/send_forward_discord_summary.py --dry-run |
| Live send test | MONITOR_DISCORD_WEBHOOK_URL=<url> python3 scripts/send_forward_discord_summary.py |

## TASK-007C Filter Dashboard Days Before Clock Start

| item | status |
|---|---|
| collect_days() date filter | DONE (skip date < CLOCK_START) |
| skipped_pre_clock_start_count | DONE (printed + shown in MD + HTML KPI card) |
| days_completed | FIXED: 2 → 1 (only 20260518+) |
| days_remaining | FIXED: 28 → 29 |
| 20260517 excluded from Daily Log | CONFIRMED |
| 20260517 raw data on disk | PRESERVED (not deleted) |
| Discord dry-run post-fix | PASS |
| py_compile | PASS |

## TASK-008B Chinese Discord Summary Status

| item | status |
|---|---|
| scripts/send_forward_discord_summary.py | UPDATED (superseded by TASK-008C) |
| Discord message language | 繁體中文 |
| WEBHOOK_ENV | MONITOR_DISCORD_WEBHOOK_URL (unchanged) |

## TASK-008C Beautify Discord Summary Status

| item | status |
|---|---|
| scripts/send_forward_discord_summary.py | UPDATED — beautified layout + date helpers |
| tests/forward_record/test_discord_summary.py | NEW — 29 tests, 29 passed |
| fmt_date_display() | DONE ("20260518" -> "2026/05/18（一）") |
| validation_day_label() | DONE (第 1-30/30 天, 結算檢查日, 驗證期後) |
| days_remaining_label() | DONE (pre-clock -> N/A) |
| VALIDATION_DAY30 | 20260616 (Day 30) |
| REVIEW_DATE | 20260617 (結算檢查日) |
| "第 31 / 30 天" bug | FIXED — 20260617 now shows 結算檢查日 |
| py_compile | PASS |
| --dry-run preview | PASS (中文美化排版) |
| pytest 29/29 | PASS |
| DISCORD_NOTIFY log tokens | UNCHANGED (SKIP/DRY_RUN/PASS/FAIL) |
| machine-readable values | PRESERVED (FORBIDDEN, REVIEW_READY, True) |

## TASK-008D Fix Discord Typo Status

| item | status |
|---|---|
| scripts/send_forward_discord_summary.py | FIXED (\u5024 -> \u503c) |
| 原始値 -> 原始值 | CONFIRMED in --dry-run |
| pytest 29/29 | PASS |
| DISCORD_NOTIFY tokens | UNCHANGED |
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
- 不得連接 Bybit w