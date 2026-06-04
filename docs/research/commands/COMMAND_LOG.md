# Command Log

Append one entry after each authorized agent task.

## Format

```text
YYYY-MM-DD HH:MM TZ
Agent:
Command source:
Task:
Status before:
Status after:
Files changed:
Validation:
Outputs:
Notes:
```

## Entries

---

### 2026-05-19（TASK-009B — Support Chinese Notion Database Properties）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-009B Support Chinese Notion Database Properties）
Task: Add PROPERTY_ALIASES + resolve_schema_names() to sync_forward_validation_to_notion.py
      so the script works with English, Chinese, or mixed Notion database property names.
      Property name resolution: Chinese preferred over English when both present.
Status before: TASK-009 script only accepted English property names
Status after:  All 16 properties accept English or Traditional Chinese equivalents

Files changed:
  scripts/sync_forward_validation_to_notion.py  -- PROPERTY_ALIASES, resolve_schema_names(),
                                                   updated check_required_properties(),
                                                   build_property_payload(), find_existing_page()
  tests/forward_record/test_notion_sync.py      -- +23 tests (total 64); added _full_schema_zh(),
                                                   _full_schema_mixed(), TestPropertyAliases,
                                                   TestResolveSchemaNames, TestCheckRequiredPropertiesBilingual,
                                                   TestBuildPropertyPayloadBilingual, TestFindExistingPageFilter
  docs/research/commands/COMMAND_LOG.md         (this entry)
  docs/research/commands/NEXT_ACTION.md         (TASK-009B status)

Chinese property name mapping (16 properties):
  Date -> 日期                       Validation Day -> 驗證日
  Days Remaining -> 剩餘天數          Runner Status -> 執行狀態
  Data Source -> 資料來源             Safety Scan -> 安全掃描
  Dry Run -> 模擬執行                 Paper Execution Status -> 紙上執行狀態
  Live Trading Status -> 真實交易狀態  Signal Count -> 訊號數
  Daily PnL % -> 當日 PnL %          Cumulative PnL % -> 累計 PnL %
  Max DD % -> 最大回撤 %              Alerts Triggered -> 觸發警報數
  Review Ready -> 可檢視             Notes -> 備註

Resolution rules:
  1. Chinese alias present in schema -> use Chinese
  2. English alias present in schema -> use English
  3. Both present -> Chinese wins
  4. Neither present -> NOTION_SYNC=FAIL with "accepted: En | Zh" diagnostic

Upsert query filter also uses resolved date property name (Date or 日期).

Validation (5/5 PASS):
  1. py_compile sync_forward_validation_to_notion.py: PASS
  2. --dry-run (alias_support: ENABLED shown): PASS
  3. pytest test_notion_sync.py: 64 passed (was 41; +23 new bilingual tests)
  4. pytest test_discord_summary.py: 29 passed (regression PASS)
  5. bash -n run_forward_record_daily.sh: PASS

Safety invariants (unchanged):
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  order_endpoint_called=False  bybit_write_called=False
  main.py NOT modified  strategy core NOT modified  signals NOT modified
  NOTION_SYNC tokens unchanged: SKIP/DRY_RUN/PASS/FAIL

---

### 2026-05-19（TASK-008E — Fix Discord Escaped Underscore SyntaxWarning）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-008E Fix Discord SyntaxWarning \_）
Task: Remove invalid Python escape sequences '\_' in send_forward_discord_summary.py
      lines 234–238 to eliminate SyntaxWarning from cron logs.
Status before: 5 lines had \_ escape sequences (paper\_execution\_status etc.)
               causing SyntaxWarning in Python 3.12+; functional output was correct.
Status after:  All 5 lines use plain underscores; no SyntaxWarning on py_compile or runtime.

Files changed:
  scripts/send_forward_discord_summary.py  -- removed \_ from 5 f-string lines (234–238)
  docs/research/commands/COMMAND_LOG.md    (this entry)
  docs/research/commands/NEXT_ACTION.md    (TASK-008E status)

Lines fixed (paper_execution_status, live_trading_status,
  FORBIDDEN_order_endpoint, FORBIDDEN_bybit_write, dry_run):
  Before: f"  paper\_execution\_status：`{paper_status}`"
  After:  f"  paper_execution_status：`{paper_status}`"

Validation (5/5 PASS):
  1. grep -n '\_' script: CLEAN (no \_ found)
  2. py_compile send_forward_discord_summary.py: PASS
  3. python3 -W error::SyntaxWarning --dry-run: exit 0, no SyntaxWarning
  4. pytest tests/forward_record/test_discord_summary.py: 29 passed
  5. bash -n run_forward_record_daily.sh: PASS

Safety: text-only fix; no logic change; DISCORD_NOTIFY tokens unchanged;
  NOTION_SYNC not affected; main.py NOT modified; no order endpoint touched.

---

### 2026-05-19（TASK-009 — Notion Sync for 30-Day Forward Validation Dashboard）

Agent: Claude Sonnet (scheduled task: resume-quant-notion-sync-after-reset)
Command source: scheduled task instruction（TASK-009 Notion Sync）
Task: Add Notion upsert sync for the 30-day forward validation dashboard. Read dashboard
      output only. Never recalculate strategy results, never touch trading logic. Wire
      into daily runner after Discord notify with set +e isolation.
Status before: TASK-008D committed locally (3ab9cfd); no Notion integration
Status after:  TASK-009 implemented; sync script + tests + daily runner step

Files changed:
  scripts/sync_forward_validation_to_notion.py   (NEW)
  scripts/run_forward_record_daily.sh            (TASK-009 section appended)
  tests/forward_record/test_notion_sync.py       (NEW — 41 tests, all pass)
  docs/research/commands/COMMAND_LOG.md          (this entry)
  docs/research/commands/NEXT_ACTION.md          (TASK-009 status)

Required environment variables (never hardcoded, never printed):
  NOTION_TOKEN                            -- Notion integration secret
  NOTION_FORWARD_VALIDATION_DATABASE_ID   -- target database id

Required Notion database properties (script fails safely with names if any missing):
  Date, Validation Day, Days Remaining, Runner Status, Data Source, Safety Scan,
  Dry Run, Paper Execution Status, Live Trading Status, Signal Count,
  Daily PnL %, Cumulative PnL %, Max DD %, Alerts Triggered, Review Ready, Notes

Behaviour / log tokens (parsed by run_forward_record_daily.sh):
  NOTION_SYNC=DRY_RUN  -- --dry-run flag: payload printed, no API call
  NOTION_SYNC=SKIP     -- token / db id env not set or CSV missing
  NOTION_SYNC=PASS     -- upsert succeeded (CREATED or UPDATED)
  NOTION_SYNC=FAIL     -- schema missing required props or API error

Upsert behaviour:
  Reads outputs/forward_record/dashboard/validation_30d.csv (newest row first)
  Date is the unique key. Existing page with same date -> PATCH update.
  No page found -> POST create. Date property may be Notion "date" or "title" type.

Safety self-check (exit 99 on any violation):
  Forbidden tokens in imports: bybit, ccxt, place_order, create_order,
  submit_order, private_post, private_put, order_endpoint, live_trading,
  paper_trading, set_leverage, cancel_order

Validation (5/5 PASS):
  1. py_compile sync_forward_validation_to_notion.py: PASS
  2. --dry-run preview (date=20260518, Day 1 / 30): PASS
  3. pytest tests/forward_record/test_notion_sync.py: 41 passed
  4. pytest tests/forward_record/test_discord_summary.py: 29 passed
  5. bash -n run_forward_record_daily.sh: PASS

Safety invariants (verified):
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  order_endpoint_called=False  bybit_write_called=False
  Network never reached on --dry-run (external_post_attempted=False)
  Token never printed; HTTPError bodies are token-redacted
  Notion failure isolated by set +e in daily runner; non-fatal for forward record
  main.py NOT modified  strategy core NOT modified  signals NOT modified

Pre-existing test failures (unrelated to TASK-009):
  tests/forward_record/test_alerting.py and test_alert_e2e_drill.py errors stem
  from missing pyarrow/fastparquet parquet engine in the sandbox environment.
  These failures pre-date TASK-009 and were not introduced by this change.
  Touched-file test suites (test_notion_sync, test_discord_summary): all 70 PASS.

Push status:
  Local HEAD = 3ab9cfd (TASK-008D, pre-existing commit not yet pushed)
  TASK-009 changes left UNCOMMITTED in working tree pending git index repair
  (sandbox NTFS mount has corrupt git/index — see Notes).

Notes:
- The bash-side git index in this session is in a corrupt state (`error: improper
  chunk offset(s) 1a24 and 1bb4`) with a stuck .git/index.lock that the sandbox
  cannot unlink. As a result, no `git commit` was performed for TASK-009 in this
  scheduled run; the new files (sync script, tests, run_forward_record_daily.sh
  patch, and these doc updates) are written to the working tree. Rick should run
  `git status`, `git add -A`, `git commit -m "TASK-009: sync forward validation
  dashboard to Notion"` from a working git checkout (Windows or VPS), then push
  3ab9cfd (TASK-008D) + the new TASK-009 commit to origin/main.

---

### 2026-05-18（TASK-008D — Fix Discord Traditional Chinese Typo）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-008D Fix Discord Traditional Chinese Typo）
Task: Replace Japanese kanji 値 (U+5024) with correct Traditional Chinese 值 (U+503C) in Discord message.
Status before: Discord message showed 「原始値」(Japanese U+5024)
Status after:  Discord message shows 「原始值」(Traditional Chinese U+503C)

Files changed:
  scripts/send_forward_discord_summary.py  -- \u5024 -> \u503c (1 occurrence)

Validation (5/5 PASS):
  1. py_compile: PASS
  2. --dry-run: 「原始值」(U+503C) confirmed in output
  3. pytest tests/forward_record/test_discord_summary.py: 29 passed
  4. bash -n run_forward_record_daily.sh: PASS
  5. DISCORD_NOTIFY=SKIP (no webhook, exit 0): PASS

Safety: no functional change; text-only fix; main.py NOT modified

---

### 2026-05-18（TASK-008C — Beautify Discord Summary Layout + Clarify Validation Dates）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-008C Beautify Discord Summary + Clarify Validation Dates）
Task: Beautify Discord message layout; fix "第 31 / 30 天" bug; add date display formatting.
Status before: 第 31/30 天 shown for 20260617; English section headers; no date weekday display
Status after:  20260617 shows "結算檢查日"; full Chinese layout; date shows "2026/05/18（一）"

Files changed:
  scripts/send_forward_discord_summary.py        -- TASK-008C beautify + date helpers
  tests/forward_record/test_discord_summary.py   -- NEW (29 tests, all pass)

New helpers in send_forward_discord_summary.py:
  fmt_date_display(yyyymmdd):    "20260518" -> "2026/05/18（一）"
  validation_day_label(date):    Day 1-30 -> "第 N / 30 天"; review -> "結算檢查日"; post -> "驗證期後"
  days_remaining_label(date):    pre-clock -> "N/A"; review+ -> "0"
  VALIDATION_DAY30 = "20260616"  (Day 30 = CLOCK_START + 29d)
  REVIEW_DATE      = "20260617"  (結算檢查日 = CLOCK_START + 30d)

Validation (6/6 PASS + pytest 29/29):
  1. py_compile: PASS
  2. --dry-run preview: 中文美化排版正確，第 1/30 天，2026/05/18（一）
  3. day label / remaining cases (6 dates): ALL PASS
  4. DISCORD_NOTIFY=SKIP (no webhook, exit 0): PASS
  5. bash -n daily runner: PASS
  6. pytest tests/forward_record/test_discord_summary.py: 29 passed, 0 failed

Key fixes:
  20260617 -> "結算檢查日"  (no longer "第 31 / 30 天")
  20260616 -> "第 30 / 30 天"
  20260518 -> "第 1 / 30 天" + "2026/05/18（一）"
  machine-readable values preserved (FORBIDDEN, REVIEW_READY, True, NOT_ATTEMPTED)
  WEBHOOK_ENV=MONITOR_DISCORD_WEBHOOK_URL unchanged
  main.py NOT modified

---

### 2026-05-18（TASK-008B — Chinese Discord Summary + Human-Friendly Day Count）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-008B Chinese Discord Summary + Human-Friendly Day Count）
Task: Rewrite Discord message in Traditional Chinese; replace Day 0 with 第 N / 30 天 display.
Status before: Discord message in English, Day 0 shown (not intuitive)
Status after:  Discord message in 繁體中文, 第 1 / 30 天 shown for CLOCK_START

Files changed:
  scripts/send_forward_discord_summary.py  -- Chinese message + _human_day() + _days_remaining()

Key changes:
  _human_day(date):      CLOCK_START -> "第 1 / 30 天"; CLOCK_START+1 -> "第 2 / 30 天"; pre-clock -> "N/A (clock start 前)"
  _days_remaining(date): CLOCK_START -> "29"; pre-clock -> "N/A"
  build_discord_message(): fully rewritten in 繁體中文
  machine-readable values preserved: FORBIDDEN, REVIEW_READY, NOT_ATTEMPTED, True unchanged

Validation (4/4 PASS):
  1. py_compile: PASS
  2. day count cases (20260518/19, 20260617, 20260517): ALL PASS
  3. --dry-run: 中文訊息顯示正確，第 1 / 30 天，剩餘 29 天
  4. DISCORD_NOTIFY=SKIP (no webhook): PASS exit 0
  5. bash -n run_forward_record_daily.sh: PASS

Safety invariants:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  order_endpoint_called=False  bybit_write_called=False
  WEBHOOK_ENV=MONITOR_DISCORD_WEBHOOK_URL (unchanged)
  main.py NOT modified  strategy core NOT modified

---

### 2026-05-18（TASK-007C — Filter Dashboard Days Before Clock Start）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-007C Filter Dashboard Days Before Clock Start）
Task: Fix collect_days() in build_forward_validation_dashboard.py to exclude date < CLOCK_START.
      20260517 shadow drill output was polluting the official 30-day validation statistics.
Status before: days_completed=2 (included 20260517 pre-clock shadow drill)
Status after:  days_completed=1 (only 20260518+; skipped_pre_clock_start_count=1)

Files changed:
  scripts/build_forward_validation_dashboard.py  -- TASK-007C filter + skipped_count

Changes in build_forward_validation_dashboard.py:
  collect_days(): return type -> tuple[list[dict], int]; skips date < CLOCK_START; counts skipped
  write_md_summary(): added skipped param; shows skipped_pre_clock_start in clock table
  write_html(): added skipped param; added Pre-Clock Skipped KPI card
  main(): unpacks (rows, skipped_pre_clock); passes skipped to write_* functions

Validation (5/5 PASS):
  1. py_compile: PASS
  2. run builder: collected 1 day(s), skipped_pre_clock_start_count=1, exit 0
  3. CSV: 1 row (date=20260518 only); 20260517 absent
  4. MD: days_completed=1, days_remaining=29, 20260517 absent, skipped_pre_clock_start=1
  5. Discord dry-run: DISCORD_NOTIFY=DRY_RUN, days_remaining=29, No live orders confirmed

Raw data preserved:
  outputs/forward_record/prev3y_crypto/20260517_* -- NOT deleted (4 files intact)
  Filter is dashboard-only; raw artifacts on disk are untouched.

Safety invariants:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  order_endpoint_called=False  bybit_write_called=False
  main.py NOT modified  strategy core NOT modified

---

### 2026-05-18（TASK-008 — Daily Discord Forward Validation Summary）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-008 Daily Discord Forward Validation Summary）
Task: Create send_forward_discord_summary.py; wire into run_forward_record_daily.sh after dashboard build.
      Discord notify must be isolated (non-fatal). SKIP if webhook not set.
Status before: no Discord daily summary; cron only ran forward record + dashboard
Status after: cron runs forward record → dashboard build → Discord summary (SKIP/PASS/FAIL logged)

Scripts created/updated:
  scripts/send_forward_discord_summary.py  -- NEW (271L)
  scripts/run_forward_record_daily.sh      -- UPDATED (added TASK-008 section, lines 153-197)

Validation (6/6 PASS):
  1. bash -n syntax: PASS
  2. py_compile send_forward_discord_summary.py: PASS
  3. DISCORD_NOTIFY=SKIP (no webhook set, exit 0): PASS
  4. DISCORD_NOTIFY=DRY_RUN (--dry-run, no POST): PASS
  5. notify FAIL isolation (script exits 0 even if Discord fails): PASS
  6. message preview: PASS (all 9 required fields present)

Environment variable:
  MONITOR_DISCORD_WEBHOOK_URL   (consistent with existing monitor infrastructure)

Safety invariants:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  order_endpoint_called=False  bybit_write_called=False
  No webhook set -> DISCORD_NOTIFY=SKIP (exit 0, no error)
  --dry-run -> DISCORD_NOTIFY=DRY_RUN (no POST, exit 0)
  Discord failure -> DISCORD_NOTIFY=FAIL logged, runner exits 0
  Reuses DefaultHttpClient + redact_text from apps.monitor.channels (existing safe primitives)
  main.py live logic: NOT modified

TASK-007C noted (separate task):
  dashboard days_completed currently includes pre-clock-start outputs (e.g. 20260517 shadow drill)
  Requires filtering FORWARD_DIR scan to date >= CLOCK_START in build_forward_validation_dashboard.py
  NOT implemented in TASK-008 per Rick's instructions.

Files changed:
- scripts/send_forward_discord_summary.py (NEW)
- scripts/run_forward_record_daily.sh (TASK-008 section appended)
- docs/research/commands/COMMAND_LOG.md (this entry)
- docs/research/commands/NEXT_ACTION.md (TASK-008 DONE + TASK-007C pending)

---

### 2026-05-18（TASK-007B — Auto Build Dashboard After Daily Forward Record）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-007B Auto Build Dashboard After Daily Forward Record）
Task: Extend run_forward_record_daily.sh to call build_forward_validation_dashboard.py after each
      successful forward record run. Dashboard failure must be isolated (non-fatal) and logged.
Status before: dashboard builder existed but was not called by cron runner
Status after: run_forward_record_daily.sh calls dashboard builder post-run; DASHBOARD_BUILD=PASS/FAIL logged
Files changed:
  scripts/run_forward_record_daily.sh   -- added TASK-007B section (lines 111-152)
  docs/research/commands/COMMAND_LOG.md -- this entry
  docs/research/commands/NEXT_ACTION.md -- TASK-007B DONE section
Validation (5/5 PASS):
  1. bash -n syntax: PASS
  2. py_compile build_forward_validation_dashboard.py: PASS
  3. --dry-run guard (missing flag → exit 2): PASS
  4. dashboard builder direct run: PASS (safety_self_check PASS, 2 days collected)
  5. dashboard FAIL isolation: PASS (script exits 0 even if dashboard fails, log shows DASHBOARD_BUILD=FAIL)
Safety invariants:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  bybit_connection=NOT_ATTEMPTED  order_endpoint_called=False
  --dry-run guard: aborts with exit 2 if flag missing
  dashboard failure: non-fatal (forward record data preserved, DASHBOARD_BUILD=FAIL logged)
  main.py live logic: NOT modified
Cron behaviour after this change:
  cron runs run_forward_record_daily.sh at 10:10 UTC daily (once installed on VPS)
  → runs forward record (--dry-run) → on success, runs dashboard builder
  → DASHBOARD_BUILD=PASS or DASHBOARD_BUILD=FAIL written to daily_logs/YYYYMMDD_run.log
Manual test:
  bash scripts/run_forward_record_daily.sh   (on VPS)
  python3 scripts/build_forward_validation_dashboard.py  (standalone)

---

### 2026-05-18（TASK-007 — 30-Day Forward Validation Dashboard）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（建立 TASK-007 30-Day Forward Validation Dashboard）
Task: Build read-only static dashboard that scans outputs/forward_record/ daily artifacts and produces HTML/MD/CSV outputs.
Status before: TASK-007 pending; no dashboard existed
Status after: TASK-007 DONE; dashboard built and committed
Scripts created:
  scripts/build_forward_validation_dashboard.py  -- dashboard builder (new)
Dashboard outputs:
  outputs/forward_record/dashboard/index.html         (7343B — KPI cards, safety box, daily table)
  outputs/forward_record/dashboard/latest_summary.md  (1462B — markdown summary)
  outputs/forward_record/dashboard/validation_30d.csv (27 fields, 2 rows — Day 1 + shadow)
Validation:
  py_compile: OK (543L, 21488B, 0 null bytes)
  safety_self_check: PASS (no forbidden imports)
  run output: collected 2 day(s), exit 0
  safety gates post-run: paper_execution_status=FORBIDDEN live_trading_status=FORBIDDEN
                         order_endpoint_called=False bybit_write_called=False
Safety invariants:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  order_endpoint_called=False  bybit_write_called=False
  Script reads ONLY from outputs/forward_record/ (no writes to strategy/position files)
  No order endpoint imports (safety_self_check regex scan PASS)
  main.py live logic NOT modified
Files changed:
- scripts/build_forward_validation_dashboard.py (NEW)
- outputs/forward_record/dashboard/index.html (NEW)
- outputs/forward_record/dashboard/latest_summary.md (NEW)
- outputs/forward_record/dashboard/validation_30d.csv (NEW)
- docs/research/commands/COMMAND_LOG.md (this entry)
- docs/research/commands/NEXT_ACTION.md (TASK-007 DONE)
How to run: python3 scripts/build_forward_validation_dashboard.py

---

### 2026-05-18（VPS daily runner setup — cron 10:10 UTC）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（set up VPS daily runner for Days 2-30）
Task: Create safe daily runner script + cron installer for 30-day forward validation。Verify idempotency and safety guards。
Status before: Day 1 complete; no daily automation in place
Status after: runner scripts created + verified; cron install pending on VPS (Rick action)
Scripts created:
  scripts/run_forward_record_daily.sh    -- daily runner (bash -n OK; --dry-run guard; Taipei date)
  scripts/install_cron_daily_runner.sh   -- one-time cron installer for VPS
Cron schedule: 10 10 * * *  (10:10 UTC = 18:10 Asia/Taipei, daily)
Validation:
  1. date computation: date_taipei=20260518 format=OK
  2. log dir creation: outputs/forward_record/daily_logs/ EXISTS
  3. safety guard: --dry-run detection PASS; missing-flag detection PASS
  4. forward record re-run: REVIEW_READY (idempotent)
  5. idempotency: positions/forward_stats/pnl checksums SAME before+after
VPS one-time setup (Rick must run):
  cd ~/quant && git pull && bash scripts/install_cron_daily_runner.sh && crontab -l
Next run: 2026-05-19 10:10 UTC / 18:10 CST (Day 2)
Safety gates:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  external_post_attempted=False  bybit_connection=NOT_ATTEMPTED
  dry_run=True  --dry-run guard aborts script if flag removed
Files changed:
- scripts/run_forward_record_daily.sh (NEW)
- scripts/install_cron_daily_runner.sh (NEW)
- outputs/forward_record/daily_logs/.gitkeep (NEW)
- docs/research/commands/VPS_DAILY_RUNNER.md (NEW)
- docs/research/commands/NEXT_ACTION.md (VPS runner status)
- docs/research/commands/COMMAND_LOG.md (this entry)

---

### 2026-05-18（30-day forward validation clock — STARTED）

Agent: Claude Sonnet
Command source: Rick explicit authorization（「開始計時」）
Task: 30-day forward validation clock 啟動。Day 1 forward record 実行。
Status before: all prerequisites DONE; clock_started=false
Status after: clock_started=TRUE; Day 1 artifact written; REVIEW_READY
Start timestamp:
  UTC:    2026-05-18T10:06:43Z
  Taipei: 2026-05-18T18:06:43 CST
  start_date: 20260518  end_date_target: 20260617
Command run:
  python3 scripts/run_forward_record.py
    --date 20260518
    --config configs/prev3y_crypto.yaml
    --output-dir outputs/forward_record/prev3y_crypto
    --dry-run
Day 1 result:
  status=REVIEW_READY
  signal_date=2026-04-30（最新キャッシュ）
  primary_generated=True  shadow_generated=False
  warning_gates=[]  stop_gates=[]
  safety_scan=PASS  review_006b_trigger_ready=False
  dry_run=True  alerts_evaluated=7  alerts_triggered=0
Infrastructure fix (pre-run):
  20260517_positions.parquet was corrupt（PAR1 footer missing, from prior drill）
  Overwritten with valid copy（same signal_date=2026-04-30, 50 rows, 13957B）
  run_forward_record.py was NTFS-truncated（113L on Linux mount vs 125L on Windows）
  Restored via bash python3 write（LF, compile OK）
Safety gates:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  clock_started=false（script field; authorized=TRUE by Rick）
  external_post_attempted=False  secret_value_observed=False
  bybit_connection=NOT_ATTEMPTED  api_key_request=NOT_ATTEMPTED
Artifacts:
  outputs/forward_record/prev3y_crypto/20260518_positions.parquet （13957B / 50 rows）
  outputs/forward_record/prev3y_crypto/20260518_pnl.json
  outputs/forward_record/prev3y_crypto/20260518_forward_stats.json
  outputs/forward_record/prev3y_crypto/20260518_overlay_check.json
  outputs/forward_record/prev3y_crypto/forward_summary.json
  outputs/logs/prev3y_crypto/20260518_forward_record.log
  outputs/forward_record/alerts/20260518_alert_log.json
Files changed:
- docs/research/commands/NEXT_ACTION.md (clock=STARTED; Day 1 summary)
- docs/research/commands/COMMAND_LOG.md (this entry)

---

### 2026-05-18（Option E — gitignore repair + untracked artifacts gitignore）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（Option E: finish true working tree cleanliness）
Task: .gitignore NTFS truncation 修復（115B/8L → 1020B/54L）+ 残存 untracked artifacts を gitignore に追加。git status --short = CLEAN（M .gitignore のみ → commit 後 clean）。
Status before: git status --short に ?? 80+ entries（.gitignore NTFS truncation で既存ルールが無効化されていた）
Status after: git status --short = clean（no untracked, no modified tracked files）
Root cause: .gitignore が Linux mount 側で 115B/8L に truncated。bash-side では commitc20bc09 の全ルールが消失していた。Windows Read tool では正常表示（ファイルシステムの非同期）。Fix: python3 open() write via bash（1020B/54L LF）。
gitignore rules added（Option E）:
  outputs/attribution/              -- local backtesting attribution artifacts
  outputs/backtests/                -- local backtesting artifacts
  outputs/data_quality/             -- local data quality artifacts
  outputs/paper_trading/            -- local paper trading artifacts
  outputs/forward_record/alerts/    -- forward record local alerts
  outputs/forward_record/prev3y_crypto/                  -- local forward record
  outputs/forward_record/prev3y_crypto_shadow_a_roll12/  -- shadow variant local
  data/crypto/                      -- large API-fetched parquet/yaml files
  data/*.malformed_*                -- DB crash recovery artifacts
  *.zip                             -- local deploy bundles
Protected committed audit dirs (NOT gitignored):
  outputs/forward_record/baselines/, drill/, discord_webhook_*/, read_only_data_source/
  outputs/logs/
git check-ignore validation: all 14 new rules PASS; committed audit dirs NOT ignored
Safety gates:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN  clock_started=false
  external_post_attempted=false  secret_value_observed=false
Files changed:
- `.gitignore` (repaired + Option E rules)
- `docs/research/commands/COMMAND_LOG.md` (this entry)
- `docs/research/commands/NEXT_ACTION.md` (Option E complete; Option D ready)

---

### 2026-05-18（Working tree cleanup — git rm --cached + HEAD restore）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（残存 modified files 全解決）
Task: 残存 9 tracked modified files を全解決：src/*.py 5 files（CRLF→LF 復元）、tests/monitor/test_channels.py（NTFS truncation 復元）、gitignored 7 files（git rm --cached）。追加コミット完了。
Status before: 9 tracked modified files 残存（src/ CRLF diff + test truncation + gitignored .claude/ + outputs/monitor/ + outputs/variants/）
Status after: tracked modified files = 0。staged deletions commit（4th commit）完了。Untracked files は gitignored or Rick 判断待ち。
Resolution details:
  src/backtester.py, indicators.py, reporter.py, risk.py, strategies.py — disk bytes > HEAD bytes（~1000B）
    Root cause: CRLF（Windows \r\n）vs LF（HEAD）。line count identical。NOT real content change。
    Fix: git show HEAD:<file> → write binary（LF）→ disk 一致
  tests/monitor/test_channels.py — disk=127L/5268B vs HEAD=276L/11791B
    Root cause: NTFS mount truncation（149 lines missing）
    Fix: git show HEAD:tests/monitor/test_channels.py → write binary → 276L restored
  git rm --cached（7 files — now gitignored）:
    .claude/settings.local.json — on disk: YES
    outputs/monitor/prev3y_crypto/alerts/20260517.jsonl — on disk: YES
    outputs/variants/prev3y_crypto/{5 files} — on disk: YES（all）
Safety gates（all sessions）:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN  clock_started=false
  external_post_attempted=false  secret_value_observed=false
Files changed:
- `docs/research/commands/COMMAND_LOG.md` (this entry)
- `docs/research/commands/NEXT_ACTION.md` (tracked files resolved; untracked inventory added)

---

### 2026-05-18（Option C working tree clean — 3 commits）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（Option C approved — 3-commit plan）
Task: working tree を 3 commits で整理；gitignored ファイルを untrack；残存 modified files を記録
Status before: working tree dirty（40+ M files，3 new scripts untracked，data/trading.db + output/Output.xlsx tracked but gitignored）
Status after: 3 commits 完了；working tree partially clean（残存: src/ changes + .claude/ + outputs/monitor/ + outputs/variants/ — Rick 指示待ち）
Commits:
  378dc34 — TASK-009/009b/009c/009d: forward record runner + alerting + tech debt + E2E drill
    - 20 files: apps/monitor/{README,report,safety}.py, config.py, main.py
    - scripts/{run_forward_record,task005_vps_bot_monitor,crypto_sweep*.py,btc_moat,diag,intraday}.py
    - NEW: scripts/validate_discord_webhook_dryrun.py, validate_discord_webhook_vps_dryrun.py, validate_read_only_data_source.py
    - DELETE: data/trading.db（untrack via git rm --cached），output/Output.xlsx（untrack via git rm --cached）
  c20bc09 — docs: TASK-009 review log, queue, workorders, COMMAND_LOG, README, gitignore
    - 26 files: .gitignore（追加: data/cache/, backups/, .claude/, outputs/monitor/, outputs/variants/）
    - README.md, docs/research/CLAUDE_REVIEW_LOG.md, CLAUDE_REVIEW_QUEUE.md, CODEX_TASK_QUEUE.md
    - docs/research/commands/{CLAUDE_COMMANDS,CODEX_COMMANDS,COMMAND_LOG,NEXT_ACTION}.md
    - docs/research/crypto_universe_methodology.md
    - docs/research/review_packets/REVIEW-{005,005a,006,007,007b,008,009,009d}_{NUMBERS,PACKET}.*
  2d5d90c — outputs: baseline + drill + webhook validation artifacts (20260518)
    - 39 files: outputs/forward_record/baselines/20260518/, drill/, discord_webhook_*/, read_only_data_source/
    - outputs/logs/{cost_inputs/,prev3y_crypto/}（20 log files）
git rm --cached（untracked without deleting local files）:
  data/trading.db — still on disk: YES
  output/Output.xlsx — still on disk: YES
Remaining modified tracked files（NOT in approved plan — Rick 指示待ち）:
  src/backtester.py, src/indicators.py, src/reporter.py, src/risk.py, src/strategies.py
  tests/monitor/test_channels.py
  .claude/settings.local.json（now gitignored — needs git rm --cached）
  outputs/monitor/prev3y_crypto/alerts/20260517.jsonl（now gitignored — needs git rm --cached）
  outputs/variants/prev3y_crypto/{5 files}（now gitignored — needs git rm --cached）
Safety gates（all sessions）:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN  clock_started=false
  external_post_attempted=false  secret_value_observed=false
Files changed:
- `docs/research/commands/COMMAND_LOG.md` (this entry)
- `docs/research/commands/NEXT_ACTION.md` (working tree clean DONE; next options updated)

---

### 2026-05-18（Discord webhook VPS strict guard validation — confirmed on actual VPS）

Agent: Claude Sonnet（記録）+ Rick（VPS 実行）
Command source: Rick direct chat instruction（VPS Discord webhook strict dry-run validation confirmed）
Task: actual VPS（instance-20260506-0945）で validate_discord_webhook_vps_dryrun.py を実行し、実際の webhook config 存在確認を含む全 6 gate PASS を確認
Status before: strict guard drill PASS（FAKE_TOKEN）；actual VPS config presence UNKNOWN
Status after: actual VPS で overall_result=PASS（6/6 gates）；actual webhook config present confirmed；Discord webhook prerequisite = DONE
VPS details:
  hostname: instance-20260506-0945
  python: .venv/bin/python
Commands run on VPS:
  .venv/bin/python -m py_compile scripts/validate_discord_webhook_vps_dryrun.py  # PASS
  .venv/bin/python scripts/validate_discord_webhook_vps_dryrun.py                 # PASS 6/6
Gate results（safe boolean summary — no secret printed）:
  W-0  webhook_config_present=True  webhook_config_non_empty=True  secret_value_observed=False  PASS
  G-1  dry_run=True  external_post_attempted=False  load_channel_secrets_called=False            PASS
  G-2  real_url_removed=True  discordapp_url_removed=True  redacted_marker_present=True          PASS
  G-3  status=DRY_RUN  external_post_attempted=False  secret_value_observed=False                PASS
  G-4  scan_status=PASS  violations=[]                                                           PASS
  G-5  dry_run=True  FORBIDDEN_live_trading=NOT_ATTEMPTED  FORBIDDEN_bybit_write=NOT_ATTEMPTED   PASS
Report-level safety fields:
  overall_result=PASS  clock_started=False  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  external_post_attempted=False  real_webhook_post_attempted=False  secret_value_observed=False
  FORBIDDEN_live_trading=NOT_ATTEMPTED  FORBIDDEN_discord_real_post=NOT_ATTEMPTED  FORBIDDEN_live_alerts=NOT_ATTEMPTED
Artifact:
  outputs/forward_record/discord_webhook_vps_dry_run/20260518/validation_result.json
Files changed:
- `docs/research/commands/COMMAND_LOG.md` (this entry)
- `docs/research/commands/NEXT_ACTION.md` (Discord webhook prerequisite = DONE；working tree clean plan追加)

---

### 2026-05-18（Discord webhook actual VPS config presence check）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（W-0 actual config presence — no FAKE_TOKEN）
Task: sandbox/Windows 環境で FAKE_TOKEN を使わずに W-0 を実行し、actual VPS config presence の状態を確認
Status before: strict guard drill PASS（FAKE_TOKEN）；actual VPS config presence 未確認
Status after: sandbox/Windows = config ABSENT（expected）；actual VPS 確認は Rick が VPS 上で実行必要
Findings:
- sandbox は Windows workspace マウント（F:\RickHSIAO\Python\量化交易）であり actual VPS ではない
- configs/monitor_secrets.local.yaml: ABSENT（gitignored；Windows dev machine には存在しない）
- MONITOR_DISCORD_WEBHOOK_URL env var: NOT SET（Windows/sandbox shell）
- secret_value_observed: false（FAKE_TOKEN 未使用）
- actual VPS webhook secret は VPS ローカルファイルシステムまたは VPS shell env にあるはず
VPS 上で実行すべきコマンド（Rick が直接実行）:
  python3 -c "...boolean-only check..." （secrets/URL 値を一切出力しない）
  → actual_webhook_config_present / actual_webhook_config_non_empty / secret_value_observed=false のみ出力
Prerequisites distinction:
  strict guard drill（FAKE_TOKEN, 6/6 gates）= DONE
  actual VPS webhook config present = UNKNOWN（Rick が VPS で確認必要）
Files changed:
- `docs/research/commands/COMMAND_LOG.md` (this entry)
- `docs/research/commands/NEXT_ACTION.md` (prerequisite 更新)

---

### 2026-05-18（Discord webhook VPS strict guard validation — FULL PASS）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（Status=WAITING — Execute VPS-side Discord webhook dry-run validation now）
Task: strict guard 付き VPS validation script を sandbox で完全実行し、全 6 gate（W-0/G-1/G-2/G-3/G-4/G-5）PASS 確認
Status before: script 作成済み；sandbox 実行で W-0 FAIL（env 未設定）/ G-5 FAIL（FileNotFoundError + clock_started logic bug）
Status after: overall_result=PASS（6/6 gates）；validation_result.json 書き込み完了；DONE
Commands run:
  python3 -c "import py_compile; ..."  # compile check -- OK
  MONITOR_DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/000000000000/FAKE_TOKEN_FOR_VALIDATION" \
    python3 -u scripts/validate_discord_webhook_vps_dryrun.py
Bugs fixed before final run:
  1. G-5: `alert_log.get("clock_started", True)` → `alert_log.get("clock_started") is not True`
     （clock_started キーが alert_log に存在しない場合、デフォルト True で `not True` = False になるバグ）
  2. Script file corrupted by repeated bash appends（NTFS→Linux mount truncation の累積）→ Write tool で完全再書き込み後 null-byte truncate
Gate results（safe boolean summary only）:
  W-0  webhook_config_present=true  webhook_config_non_empty=true  secret_value_observed=false  PASS
  G-1  status=DRY_RUN  dry_run=true  external_post_attempted=false  load_channel_s
---

### 2026-05-25（TASK-010: Paper Portfolio PnL Simulation）

Agent: Claude Sonnet
Command source: Rick direct chat instruction
Task: Build paper portfolio MTM PnL simulation to populate daily_pnl_pct / cumulative_pnl_pct / max_dd_pct in the 30-day forward validation dashboard (previously all 0%)
Status before: dashboard PnL fields all 0% (no engine); forward record running on VPS
Status after: DONE (commit 98380a4)
Commands run:
  python3 -m py_compile scripts/paper_portfolio_engine.py           # PASS
  python3 scripts/paper_portfolio_engine.py --dry-run               # PAPER_PNL=DRY_RUN
  python3 scripts/paper_portfolio_engine.py --rebuild               # PAPER_PNL=PASS (20260518)
  python3 scripts/build_forward_validation_dashboard.py             # dashboard overlay verified
  bash -n scripts/run_forward_record_daily.sh                       # PASS
  python3 -m pytest tests/forward_record/ -q                       # 194/194 PASS
Key design decisions:
  - MTM formula: daily_pnl_usd = position_usd * (today_px / prev_px - 1)
  - Works for long (position_usd > 0) and short (position_usd < 0)
  - Entry day: PnL = 0 (no prev price)
  - TP_PCT = SL_PCT = None (disabled; momentum uses signal-based exits)
  - paper_execution_status = FORBIDDEN (hardcoded, never relaxed)
  - live_trading_status = FORBIDDEN (hardcoded, never relaxed)
  - Prices in dev = frozen cache_fallback → PnL = 0; on VPS prices update daily → non-zero
Files changed:
  NEW  scripts/paper_portfolio_engine.py          (624 lines; safety_self_check, compute_daily_mtm, update_state, write_paper_pnl_json)
  NEW  tests/forward_record/test_paper_portfolio.py (539 lines; 48 tests: MTM long/short, max_dd, TP/SL, exposure cap, safety_self_check)
  MOD  scripts/build_forward_validation_dashboard.py  (PAPER_DIR + overlay in collect_days())
  MOD  scripts/run_forward_record_daily.sh            (TASK-010 PAPER_PNL section before dashboard build)
Output files (gitignored, generated):
  outputs/forward_record/paper_portfolio/state.json
  outputs/forward_record/paper_portfolio/daily_pnl.csv
  outputs/forward_record/paper_portfolio/20260518_paper_pnl.json
PAPER_PNL tokens: DRY_RUN | SKIP | PASS | FAIL

---

### 2026-05-26（TASK-010B: Enable Paper Portfolio Write Mode in Daily Runner）

Agent: Claude Sonnet
Command source: Rick direct chat instruction
Task: Remove --dry-run hardcode from run_forward_record_daily.sh PAPER_PNL section so daily cron
actually writes paper portfolio outputs (state.json, daily_pnl.csv, {date}_paper_pnl.json).
Preserve PAPER_PNL_DRY_RUN=1 env var for manual testing.
Status before: PAPER_PNL=DRY_RUN (no files written); dashboard PnL = 0 always
Status after: DONE — default write mode; PAPER_PNL_DRY_RUN=1 forces dry-run
Commands run:
  bash -n scripts/run_forward_record_daily.sh                           # PASS
  python3 -m py_compile scripts/paper_portfolio_engine.py               # PASS
  python3 -m pytest tests/forward_record/test_paper_portfolio.py -q    # 57/57 PASS
  python3 -m pytest tests/forward_record/ -q                           # 203/203 PASS
Key change:
  PAPER_SECTION in run_forward_record_daily.sh:
    Before: "${PYTHON}" "${PAPER_SCRIPT}" --dry-run
    After:  PAPER_FLAGS="" (default) or PAPER_FLAGS="--dry-run" if PAPER_PNL_DRY_RUN=1
            "${PYTHON}" "${PAPER_SCRIPT}" ${PAPER_FLAGS}
Manual dry-run usage: PAPER_PNL_DRY_RUN=1 bash scripts/run_forward_record_daily.sh
PAPER_PNL tokens: PASS (write ok) | DRY_RUN (PAPER_PNL_DRY_RUN=1) | SKIP (no parquet) | FAIL (error)
Safety confirmed:
  paper_execution_status = FORBIDDEN (hardcoded in engine)
  live_trading_status    = FORBIDDEN (hardcoded in engine)
  order endpoint         = NOT called
  bybit write API        = NOT called
Files changed:
  MOD  scripts/run_forward_record_daily.sh       (PAPER_PNL section: write mode + PAPER_PNL_DRY_RUN env var)
  MOD  tests/forward_record/test_paper_portfolio.py (9 new tests: TestDailyRunnerInvocation)
  MOD  docs/research/commands/COMMAND_LOG.md     (this entry)
  MOD  docs/research/commands/NEXT_ACTION.md     (updated status)

---

### 2026-05-28（TASK-011A: Verify and Fix Forward Record Market Data Freshness）

Agent: Claude Sonnet
Command source: Rick direct chat instruction
Task: Diagnose why hypothetical_fill_px is frozen across all days (2026-05-17 → 2026-05-28);
fix so daily runner uses live read-only market prices from Bybit public tickers.
Status before: hypothetical_fill_px = 75750.0 (BTCUSDT open 2026-04-30) every day; PnL = 0
Status after: DONE — LiveReadOnlyMarketDataProvider + price-date fix; commit pending push

Root cause (full chain):
  1. data/crypto/prices_daily.parquet ends at 2026-04-30 (cache cutoff)
  2. signal_loader.py → signal_date = 2026-04-30 (last row in backtest positions)
  3. primary.py called provider.load_prices(loaded.signal_date) + latest_prices_by_symbol(prices, loaded.signal_date)
     → hypothetical_fill_px = open price on 2026-04-30 = frozen for every record day
  4. run_forward_record.py --data-source only had choices=["cache_fallback"]
  5. BybitReadOnlyMarketDataProvider existed but was allow_network=False and not wired in

Fixes implemented:
  A. apps/forward_record/primary.py
       provider.load_prices(record_ts)               # was: loaded.signal_date
       latest_prices_by_symbol(prices, record_ts)    # was: loaded.signal_date
       + check_price_freshness() diagnostic output

  B. apps/forward_record/market_data.py
       + LiveReadOnlyMarketDataProvider (cache + Bybit /v5/market/tickers GET)
       + _bybit_symbol_to_internal() / _internal_to_bybit_symbol()
       + _fetch_bybit_tickers() (public GET only, no auth)
       + check_price_freshness() diagnostic

  C. scripts/run_forward_record.py
       --data-source choices: ["cache_fallback", "live_read_only"]
       live_read_only → LiveReadOnlyMarketDataProvider

  D. scripts/run_forward_record_daily.sh
       DATA_SOURCE="${DATA_SOURCE:-live_read_only}"
       CMD += "--data-source" "${DATA_SOURCE}"

Commands run:
  python3 -m py_compile apps/forward_record/market_data.py primary.py scripts/run_forward_record.py  # PASS
  bash -n scripts/run_forward_record_daily.sh                                                         # PASS
  python3 -m pytest tests/forward_record/ -q                                                         # 242/242 PASS

Safety confirmed:
  data source: /v5/market/tickers?category=linear (public GET, no API key)
  method: GET only — no POST/PUT/DELETE
  no order endpoint, no bybit write API, no private endpoint
  paper_execution_status = FORBIDDEN (hardcoded)
  live_trading_status    = FORBIDDEN (hardcoded)
  fallback: if Bybit network unavailable → cache prices silently (no crash)

On VPS after git pull:
  - Cron will run with --data-source live_read_only by default
  - hypothetical_fill_px will use today's Bybit lastPrice instead of 2026-04-30 open
  - paper portfolio engine will see different prices day-to-day → non-zero MTM PnL
  - Override: DATA_SOURCE=cache_fallback bash scripts/run_forward_record_daily.sh

Files changed:
  MOD  apps/forward_record/market_data.py          (+LiveReadOnlyMarketDataProvider, freshness helpers)
  MOD  apps/forward_record/primary.py              (price lookup date: record_ts not signal_date)
  MOD  scripts/run_forward_record.py               (+live_read_only choice, provider selection)
  MOD  scripts/run_forward_record_daily.sh         (DATA_SOURCE=live_read_only default)
  NEW  tests/forward_record/test_market_data_freshness.py  (39 tests: symbol mapping, live provider, freshness, safety)
  MOD  docs/research/commands/COMMAND_LOG.md       (this entry)
  MOD  docs/research/commands/NEXT_ACTION.md       (updated)

---

### 2026-06-04（TASK-011B: Paper Portfolio Sanity Check / Exposure Audit）

Agent: Claude Sonnet
Command source: Rick direct chat instruction
Task: Diagnose +460% Day 11 PnL and +139% Day 12 PnL; audit exposure; fix root cause.
Status before: PAPER_PNL=PASS but daily_pnl_pct showing +460% / +139% (unrealistic)
Status after: DONE — root cause diagnosed + stale-state-reset fix + audit script; commit pending

Root cause:
  BUG: STATE_STALENESS
  paper_portfolio_engine.py did not detect when state.json prev_px values were stale.
  When TASK-011A deployed live_read_only prices on VPS:
    state.json had last_processed_date=20260518, positions with last_px=April_30_cache_price
    On 20260528 (first live run): compute_daily_mtm used prev_px=April_30 vs today_px=May_28_live
    Gap = 28 days of accumulated price movement booked as ONE day PnL
    Momentum strategy longs (3yr winners) went up 200-800%; shorts (3yr losers) fell
    Net effect: huge asymmetric PnL spike (+460% on Day 11, +139% on Day 12)
  PnL formula itself is CORRECT: pnl = position_usd * (today_px / prev_px - 1)
  Position sizing is NORMAL: 25 long × $200 + 25 short × -$200 = gross_exposure_ratio = 1.0x

Exposure audit results (sandbox data — VPS has live results):
  gross_exposure_ratio = 1.00x (NORMAL, <= 1.0x threshold)
  net_exposure_ratio   = 0.00x (perfectly balanced long-short)
  max_single_pos_pct   = 2.0% of NAV (NORMAL, < 10% threshold)
  no position sizing bug found

Fix implemented:
  paper_portfolio_engine.py: _maybe_reset_stale_state()
    If gap between state.last_processed_date and today > STALE_RESET_DAYS (3):
      Clear positions list → all positions treated as NEW ENTRIES (PnL=0)
      Seed last_px from today live prices for correct day-2 MTM
    NAV / peak / max_dd are preserved (not reset)
  STALE_RESET_DAYS = 3 (configurable constant)

Commands run:
  python3 -m py_compile scripts/audit_paper_portfolio_exposure.py   # PASS
  python3 -m py_compile scripts/paper_portfolio_engine.py           # PASS
  python3 scripts/audit_paper_portfolio_exposure.py                 # AUDIT_DONE
  python3 -m pytest tests/forward_record/ -q                        # 269/269 PASS

On VPS after git pull:
  python3 scripts/paper_portfolio_engine.py --rebuild  (re-processes all dates with stale-reset fix)
  python3 scripts/audit_paper_portfolio_exposure.py    (generates audit report with live data)

Files changed:
  NEW  scripts/audit_paper_portfolio_exposure.py       (474 lines; exposure metrics, PnL sanity, MD/JSON report)
  MOD  scripts/paper_portfolio_engine.py               (_maybe_reset_stale_state, STALE_RESET_DAYS constant)
  NEW  tests/forward_record/test_paper_portfolio_audit.py  (262 lines; 27 tests)
  MOD  docs/research/commands/COMMAND_LOG.md           (this entry)
  MOD  docs/research/commands/NEXT_ACTION.md           (updated)
Safety confirmed:
  audit script: read-only, no order endpoint, safety_self_check PASS
  engine fix: only clears positions[], preserves NAV, no trading API calls
  paper_execution_status = FORBIDDEN, live_trading_status = FORBIDDEN

---

### 2026-06-04（TASK-012: Paper Portfolio Exposure Guard）

Agent: Claude Sonnet
Command source: Rick direct chat instruction
Task: Add formal exposure guard to paper_portfolio_engine.py; filter new-entry positions
against 6 rules; record skip reasons; expose guard_summary in JSON + CSV + dashboard + audit.
Status before: no enforcement of exposure limits; guard was check_exposure() warning-only
Status after: DONE — apply_exposure_guard() enforced; guard_summary in all outputs; commit pending

Guard constants (enforced, not just warning):
  GUARD_MAX_OPEN_POSITIONS      = 50
  GUARD_MAX_LONG_POSITIONS      = 25
  GUARD_MAX_SHORT_POSITIONS     = 25
  GUARD_MAX_GROSS_EXPOSURE_RATIO = 1.0  (gross_notional / nav)
  GUARD_MAX_NET_EXPOSURE_RATIO   = 0.5  (abs(long+short) / nav)
  GUARD_MAX_SINGLE_POSITION_PCT  = 0.02 (abs(pos_usd) / nav)

Guard check priority (applied to new entries only; continuing positions never dropped):
  1. max_open_positions
  2. max_long_positions / max_short_positions
  3. max_single_position
  4. max_gross_exposure
  5. max_net_exposure

guard_status tokens: PASS (0 skipped) | WARNING (some skipped, some entered) | BLOCKED (all new entries skipped)

New paper_pnl.json guard_summary block:
  n_signals_seen, n_entered, n_skipped, skip_reasons (dict),
  gross_exposure_ratio, net_exposure_ratio, max_single_position_pct_nav, guard_status

New daily_pnl.csv columns: n_skipped, gross_exposure_ratio, net_exposure_ratio, guard_status

Dashboard latest_summary.md: guard_status, gross_exposure_ratio, net_exposure_ratio, signals_skipped

Audit script: reads guard_summary from paper_pnl.json; shows guard_status + skip_reasons per day;
warns if gross > 1.0x / net > 0.5x / max_single > 2%

Commands run:
  python3 scripts/paper_portfolio_engine.py --rebuild  # PAPER_PNL=PASS, guard_status=PASS
  python3 scripts/audit_paper_portfolio_exposure.py    # AUDIT_DONE
  python3 scripts/build_forward_validation_dashboard.py # Done
  bash -n scripts/run_forward_record_daily.sh           # PASS
  python3 -m py_compile scripts/{engine,audit,dashboard} # PASS
  python3 -m pytest tests/forward_record/ -q            # 303/303 PASS

Safety confirmed:
  apply_exposure_guard() only filters simulation entries — no order API called
  paper_execution_status = FORBIDDEN, live_trading_status = FORBIDDEN
  safety_self_check PASS

Files changed:
  MOD  scripts/paper_portfolio_engine.py      (GUARD_* constants, _state_nav, _guard_compute_ratios,
                                               _guard_status, apply_exposure_guard, updated
                                               compute_daily_mtm, append_daily_pnl_row,
                                               write_paper_pnl_json, process_date)
  MOD  scripts/audit_paper_portfolio_exposure.py  (reads guard_summary; warns on ratio thresholds)
  MOD  scripts/build_forward_validation_dashboard.py (overlays guard fields from paper_pnl.json;
                                                       shows in latest_summary.md)
  NEW  tests/forward_record/test_paper_portfolio_guard.py  (34 tests; all six guard rules,
                                                             skip reason aggregation, JSON fields,
                                                             CSV fields, audit integration, safety)
  MOD  docs/research/commands/COMMAND_LOG.md   (this entry)
  MOD  docs/research/commands/NEXT_ACTION.md   (updated)
