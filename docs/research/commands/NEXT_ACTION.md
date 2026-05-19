# Next Action

## Next Rick Action (set by 2026-05-19 scheduled task)

1. Verify working tree (Windows or VPS) has uncommitted TASK-009 files:
     git status
     -> expect: new scripts/sync_forward_validation_to_notion.py,
                new tests/forward_record/test_notion_sync.py,
                modified scripts/run_forward_record_daily.sh,
                modified docs/research/commands/{COMMAND_LOG,NEXT_ACTION}.md
2. Commit:
     git add scripts/sync_forward_validation_to_notion.py \
             scripts/run_forward_record_daily.sh \
             tests/forward_record/test_notion_sync.py \
             docs/research/commands/COMMAND_LOG.md \
             docs/research/commands/NEXT_ACTION.md
     git commit -m "TASK-009: sync forward validation dashboard to Notion"
3. Push (this also delivers 3ab9cfd / TASK-008D, which is still local-only):
     git push origin main
4. On the VPS:
     cd ~/quant && git pull
     export NOTION_TOKEN=...            # via secrets file or shell
     export NOTION_FORWARD_VALIDATION_DATABASE_ID=...
     # Confirm the Notion database has the 16 required properties listed below.
     python3 scripts/sync_forward_validation_to_notion.py --dry-run
     # Optional once env is set: bash scripts/run_forward_record_daily.sh

Sandbox could not commit/push automatically: the bash-side .git/index in
the Linux mount is corrupt (`fatal: index file corrupt`) and the
.git/index.lock cannot be unlinked from the sandbox. The Windows-side
working tree on F:\RickHSIAO\Python\量\u5316\u4ea4\u6613 has the
new files written correctly (verified by py_compile + pytest 70/70 of the
Notion + Discord suites).

## Status
WAITING (Rick action: commit TASK-009 changes + push origin main)

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

## TASK-009B Support Chinese Notion Database Properties Status

| item | status |
|---|---|
| scripts/sync_forward_validation_to_notion.py | UPDATED — PROPERTY_ALIASES + resolve_schema_names() |
| PROPERTY_ALIASES | DONE (16 properties, each with English + Chinese alias) |
| resolve_schema_names() | DONE (prefers Chinese over English when both present) |
| check_required_properties() | UPDATED (reports canonical + accepted aliases on missing) |
| build_property_payload() | UPDATED (uses resolved prop names as Notion payload keys) |
| find_existing_page() | UPDATED (query filter uses resolved date property name) |
| English schema compatibility | PASS (all 41 original tests pass) |
| Chinese schema support | PASS (新增 23 tests, all pass) |
| Mixed schema support | PASS |
| "both present → Chinese wins" | PASS |
| Missing prop error shows both aliases | PASS |
| pytest 64/64 | PASS |
| NOTION_SYNC tokens | UNCHANGED (SKIP/DRY_RUN/PASS/FAIL) |
| dry-run alias_support output | ENABLED (shown in --dry-run preview) |

### Chinese property name mapping

| English (canonical) | Chinese |
|---|---|
| Date | 日期 |
| Validation Day | 驗證日 |
| Days Remaining | 剩餘天數 |
| Runner Status | 執行狀態 |
| Data Source | 資料來源 |
| Safety Scan | 安全掃描 |
| Dry Run | 模擬執行 |
| Paper Execution Status | 紙上執行狀態 |
| Live Trading Status | 真實交易狀態 |
| Signal Count | 訊號數 |
| Daily PnL % | 當日 PnL % |
| Cumulative PnL % | 累計 PnL % |
| Max DD % | 最大回撤 % |
| Alerts Triggered | 觸發警報數 |
| Review Ready | 可檢視 |
| Notes | 備註 |

## TASK-008E Fix Discord Escaped Underscore SyntaxWarning Status

| item | status |
|---|---|
| scripts/send_forward_discord_summary.py | FIXED — \_ removed from 5 f-string lines |
| lines fixed | 234–238 (paper_execution_status, live_trading_status, FORBIDDEN_order_endpoint, FORBIDDEN_bybit_write, dry_run) |
| SyntaxWarning eliminated | CONFIRMED (-W error::SyntaxWarning exit 0) |
| py_compile | PASS |
| pytest 29/29 | PASS |
| bash -n | PASS |
| DISCORD_NOTIFY tokens | UNCHANGED (SKIP/DRY_RUN/PASS/FAIL) |
| NOTION_SYNC | NOT AFFECTED |
| main.py | NOT MODIFIED |
| order endpoint | NOT TOUCHED |

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
| local commit 3ab9cfd | DONE |
| pushed to origin/main | PENDING (Rick must `git push origin main`) |

## TASK-009 Notion Sync Status

| item | status |
|---|---|
| scripts/sync_forward_validation_to_notion.py | CREATED (urllib only, no new deps) |
| scripts/run_forward_record_daily.sh TASK-009 section | APPENDED (after Discord notify) |
| tests/forward_record/test_notion_sync.py | NEW — 41 tests, all PASS |
| --dry-run never hits network | VERIFIED (test_dry_run_no_secret_leak) |
| NOTION_SYNC=SKIP on missing env | VERIFIED (test_live_missing_*_skip) |
| NOTION_SYNC=PASS / FAIL / DRY_RUN tokens | IMPLEMENTED |
| safety_self_check (forbidden imports) | IMPLEMENTED (exit 99 on violation) |
| schema mismatch -> FAIL with property names | IMPLEMENTED (check_required_properties) |
| Notion API call isolation | upsert only — POST /pages or PATCH /pages/{id} |
| Notion failure isolation in daily runner | set +e block; runner exits 0 |
| Environment variables (never hardcoded) | NOTION_TOKEN, NOTION_FORWARD_VALIDATION_DATABASE_ID |
| pytest test_notion_sync.py 41/41 | PASS |
| pytest test_discord_summary.py 29/29 | PASS |
| py_compile | PASS |
| bash -n run_forward_record_daily.sh | PASS |
| local commit | PENDING (sandbox git index corrupt — Rick must commit) |

## TASK-009 Required Notion Database Properties

The Notion database identified by `NOTION_FORWARD_VALIDATION_DATABASE_ID` must
expose the following properties. If any are missing the script prints them and
emits `NOTION_SYNC=FAIL`; it never alters the database schema automatically.

| Notion property        | suggested type | CSV source                          |
|---|---|---|
| Date                   | date or title  | date (YYYYMMDD -> ISO)              |
| Validation Day         | rich_text      | derived (Day N / 30, Review Day...) |
| Days Remaining         | number         | derived                             |
| Runner Status          | select         | runner_status                       |
| Data Source            | rich_text      | data_source                         |
| Safety Scan            | select         | safety_scan                         |
| Dry Run                | checkbox       | dry_run                             |
| Paper Execution Status | select         | paper_execution_status (FORBIDDEN)  |
| Live Trading Status    | select         | live_trading_status (FORBIDDEN)     |
| Signal Count           | number         | signal_count                        |
| Daily PnL %            | number         | daily_pnl_pct                       |
| Cumulative PnL %       | number         | cumulative_pnl_pct                  |
| Max DD %               | number         | max_dd_pct                          |
| Alerts 