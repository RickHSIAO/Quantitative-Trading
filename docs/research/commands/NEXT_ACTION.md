# Next Action

## Next Rick Action (set by 2026-05-25 scheduled task)

1. Verify working tree (Windows or VPS) has uncommitted TASK-009 + TASK-010 files:
     git status
     -> expect: new scripts/paper_portfolio_engine.py,
                new tests/forward_record/test_paper_portfolio.py,
                modified scripts/build_forward_validation_dashboard.py,
                modified scripts/run_forward_record_daily.sh,
                modified docs/research/commands/{COMMAND_LOG,NEXT_ACTION}.md
2. Stage and commit:
     git add scripts/paper_portfolio_engine.py \
             scripts/build_forward_validation_dashboard.py \
             scripts/run_forward_record_daily.sh \
             tests/forward_record/test_paper_portfolio.py \
             docs/research/commands/COMMAND_LOG.md \
             docs/research/commands/NEXT_ACTION.md
     git commit -m "TASK-010: paper portfolio PnL simulation"
3. Push (also delivers TASK-008D 3ab9cfd + TASK-009 b9dcf5f + TASK-010 98380a4):
     git push origin main
4. On the VPS:
     cd ~/quant && git pull
     # Confirm paper_portfolio_engine.py is present
     python3 scripts/paper_portfolio_engine.py --dry-run
     # Run rebuild to process all existing dates:
     python3 scripts/paper_portfolio_engine.py --rebuild
     # Rebuild dashboard to pick up paper PnL overlay:
     python3 scripts/build_forward_validation_dashboard.py

Sandbox committed files via git commit-tree (HEAD.lock workaround).
The Windows-side working tree on F:\RickHSIAO\Python\量化交易 has all
new files written correctly (verified by pytest 194/194 + bash -n PASS).

## Status
WAITING (Rick action: commit TASK-010 changes + push origin main + VPS pull)

## Owner
Rick

## Task
30-day forward validation clock RUNNING（Day 8 done, 2026-05-25）。
VPS daily runner script ACTIVE（cron 10:10 UTC daily）。
Paper portfolio PnL engine DONE — will show non-zero PnL on VPS once prices update.

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
| days_completed | 8 |
| days_remaining | 22 |

## TASK-010 Paper Portfolio PnL Simulation Status

| item | status |
|---|---|
| scripts/paper_portfolio_engine.py | DONE (py_compile OK, --dry-run OK, --rebuild PASS) |
| tests/forward_record/test_paper_portfolio.py | DONE (48 tests, 48 PASS) |
| scripts/build_forward_validation_dashboard.py | UPDATED — PAPER_DIR + overlay in collect_days() |
| scripts/run_forward_record_daily.sh | UPDATED — PAPER_PNL section before dashboard build |
| pytest 194/194 (all forward_record tests) | PASS |
| bash -n run_forward_record_daily.sh | PASS |
| py_compile all scripts | PASS |
| local commit 98380a4 | DONE (via commit-tree) |
| pushed to origin/main | PENDING (Rick must git push) |
| VPS: python3 paper_portfolio_engine.py --rebuild | PENDING (Rick must run after git pull) |

### How PnL becomes non-zero on VPS

In development (cache_fallback), `hypothetical_fill_px` is frozen from the
historical dataset → prices identical across days → PnL = 0.

On VPS with live daily data downloads, `hypothetical_fill_px` updates each day
to the current close price. The MTM formula:

  daily_pnl_usd = position_usd * (today_px / prev_px - 1)

will produce non-zero values as soon as the VPS has two consecutive days of
`_positions.parquet` with different prices.

Run `python3 scripts/paper_portfolio_engine.py --rebuild` on VPS after `git pull`
to reprocess all existing dates and populate `paper_portfolio/` output files.

## TASK-010 Output Files

| file | description |
|---|---|
| outputs/forward_record/paper_portfolio/state.json | current nav, peak, positions (gitignored) |
| outputs/forward_record/paper_portfolio/daily_pnl.csv | daily PnL log (gitignored) |
| outputs/forward_record/paper_portfolio/trades.csv | exited positions log (gitignored) |
| outputs/forward_record/paper_portfolio/{date}_paper_pnl.json | per-day JSON read by dashboard |

## TASK-009B Support Chinese Notion Database Properties Status

| item | status |
|---|---|
| scripts/sync_forward_validation_to_notion.py | UPDATED — PROPERTY_ALIASES + resolve_schema_names() |
| PROPERTY_ALIASES | DONE (16 properties, each with English + Chinese alias) |
| resolve_schema_names() | DONE (prefers Chinese over English when both present) |
| pytest 64/64 | PASS |
| local commit b9dcf5f | DONE |
| pushed to origin/main | PENDING |

## TASK-009 Notion Sync Status

| item | status |
|---|---|
| scripts/sync_forward_validation_to_notion.py | CREATED (urllib only, no new deps) |
| tests/forward_record/test_notion_sync.py | DONE — 64 tests, all PASS |
| NOTION_SYNC tokens | SKIP/DRY_RUN/PASS/FAIL |
| local commit | PENDING (Rick must commit TASK-009 + push) |

## TASK-008E Fix Discord Escaped Underscore SyntaxWarning Status

| item | status |
|---|---|
| scripts/send_forward_discord_summary.py | FIXED — \_ removed from 5 f-string lines |
| SyntaxWarning eliminated | CONFIRMED |
| pytest 29/29 | PASS |

## VPS Daily Runner Status

| item | status |
|---|---|
| scripts/run_forward_record_daily.sh | UPDATED (PAPER_PNL + TASK-010 section) |
| scripts/install_cron_daily_runner.sh | CREATED |
| cron installed on VPS | ASSUMED ACTIVE (Rick ran install_cron_daily_runner.sh) |
| PAPER_PNL step in cron | YES — runs before dashboard build |

## TASK-007 Dashboard Status

| item | status |
|---|---|
| scripts/build_forward_validation_dashboard.py | UPDATED (TASK-010 paper PnL overlay) |
| outputs/forward_record/dashboard/index.html | REGENERATED |
| outputs/forward_record/dashboard/validation_30d.csv | daily_pnl_pct=0.0 (expected in dev) |
| paper PnL overlay active | YES — reads paper_portfolio/{date}_paper_pnl.json |
