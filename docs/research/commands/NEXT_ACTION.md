# Next Action

## Next Rick Action (set by 2026-06-04 TASK-013)

1. Verify working tree has uncommitted TASK-010B files:
     git status
     -> expect: modified scripts/run_forward_record_daily.sh,
                modified tests/forward_record/test_paper_portfolio.py,
                modified docs/research/commands/{COMMAND_LOG,NEXT_ACTION}.md
2. Stage and commit all pending TASK-010 through TASK-013 work:
     git add scripts/paper_portfolio_engine.py \
             scripts/build_forward_validation_dashboard.py \
             scripts/run_forward_record_daily.sh \
             scripts/run_forward_record.py \
             tests/forward_record/test_paper_portfolio.py \
             tests/forward_record/test_market_data_freshness.py \
             apps/forward_record/market_data.py \
             apps/forward_record/primary.py \
             docs/research/commands/COMMAND_LOG.md \
             docs/research/commands/NEXT_ACTION.md
     git commit -m "TASK-013: add Notion historical backfill sync"
3. Push (delivers TASK-008D through TASK-013):
     git push origin main
4. On the VPS:
     cd ~/quant && git pull
     # Reprocess all dates with guard fix:
     python3 scripts/paper_portfolio_engine.py --rebuild
     # Run exposure audit:
     python3 scripts/audit_paper_portfolio_exposure.py
     # Rebuild dashboard:
     python3 scripts/build_forward_validation_dashboard.py
     # Backfill corrected PnL to Notion:
     python3 scripts/sync_forward_validation_to_notion.py --all --dry-run
     python3 scripts/sync_forward_validation_to_notion.py --all

Sandbox committed files via git commit-tree (HEAD.lock workaround).
The Windows-side working tree on F:\RickHSIAO\Python\量化交易 has all
new files written correctly (verified by pytest 194/194 + bash -n PASS).

## Status
WAITING (Rick action: commit TASK-013 changes + push origin main + VPS backfill)

## Owner
Rick

## Task
30-day forward validation clock RUNNING（Day 17 done, 2026-06-04, Day 18 in progress）。
VPS daily runner script ACTIVE（cron 10:10 UTC daily）。
Paper portfolio PnL engine DONE (write mode enabled via TASK-010B).
TASK-011A: live read-only prices fix DONE.
TASK-011B: stale-state-reset fix DONE.
TASK-012: exposure guard DONE.
TASK-013: Notion historical backfill DONE — --date / --all / default(latest) supported.
On VPS: after git pull, run --all --dry-run to preview, then --all to backfill corrected PnL.

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






## TASK-013 Notion Historical Backfill Status

| item | status |
|---|---|
| load_all_rows() | DONE |
| load_row_by_date(date) | DONE |
| _parse_cli() | DONE |
| _select_rows() | DONE |
| multi-row upsert loop in main() | DONE |
| --date YYYYMMDD single backfill | DONE |
| --all full history backfill | DONE |
| default (no args) → latest row only | PRESERVED |
| Chinese alias schema (TASK-009B) | PRESERVED |
| NOTION_TOKEN never printed | VERIFIED |
| output: selected_rows / processed_rows / created_count / updated_count | DONE |
| tests/forward_record/test_notion_sync.py | +27 tests (91 total) |
| pytest 330/330 | PASS |
| local commit | PENDING (Rick must git push) |
| VPS: git pull + --all --dry-run to preview | PENDING |
| VPS: --all to backfill corrected 20260528 row | PENDING |

### Backfill commands (run on VPS after git pull)

```bash
# Preview what will be synced
python3 scripts/sync_forward_validation_to_notion.py --all --dry-run

# Backfill specific date (e.g. corrected 20260528)
python3 scripts/sync_forward_validation_to_notion.py --date 20260528

# Full history backfill (all rows in validation_30d.csv)
python3 scripts/sync_forward_validation_to_notion.py --all
```

## TASK-012 Portfolio Exposure Guard Status

| item | status |
|---|---|
| GUARD_MAX_OPEN_POSITIONS | 50 |
| GUARD_MAX_LONG_POSITIONS | 25 |
| GUARD_MAX_SHORT_POSITIONS | 25 |
| GUARD_MAX_GROSS_EXPOSURE_RATIO | 1.0x |
| GUARD_MAX_NET_EXPOSURE_RATIO | 0.5x |
| GUARD_MAX_SINGLE_POSITION_PCT | 2.0% |
| apply_exposure_guard() in paper_portfolio_engine.py | DONE |
| guard_summary in {date}_paper_pnl.json | DONE |
| n_skipped / gross_exposure_ratio / net_exposure_ratio / guard_status in daily_pnl.csv | DONE |
| guard_status / gross / net / signals_skipped in dashboard latest_summary.md | DONE |
| audit reads guard_summary + warns on threshold violations | DONE |
| tests/forward_record/test_paper_portfolio_guard.py | NEW — 34 tests |
| pytest 303/303 | PASS |
| bash -n run_forward_record_daily.sh | PASS |
| py_compile all scripts | PASS |
| local commits | PENDING (Rick must git push) |
| VPS: --rebuild after git pull | PENDING |

### guard_status tokens

| token | meaning |
|---|---|
| PASS | no new entries blocked |
| WARNING | some new entries skipped, some entered |
| BLOCKED | all new entries blocked (e.g. portfolio already full) |

## TASK-011B Paper Portfolio Sanity Check / Exposure Audit Status

| item | status |
|---|---|
| Root cause of +460% PnL identified | DONE — STATE_STALENESS bug |
| Bug description | state.json prev_px from cache era (Apr 30); first live-price day computed 28-day accumulated move as 1 day |
| PnL formula correct | YES (pnl = position_usd × (today/prev - 1) is correct) |
| Position sizing normal | YES (gross_exposure = 1.0x, each position = 2% NAV) |
| scripts/audit_paper_portfolio_exposure.py | NEW — exposure metrics, PnL sanity, MD/JSON audit report |
| scripts/paper_portfolio_engine.py | UPDATED — _maybe_reset_stale_state(), STALE_RESET_DAYS=3 |
| tests/forward_record/test_paper_portfolio_audit.py | NEW — 27 tests |
| pytest 269/269 | PASS |
| local commit | PENDING (Rick must git push) |
| VPS: --rebuild after git pull | PENDING (to reprocess all dates with fix) |

### Stale-State Reset Fix

When `gap(today, state.last_processed_date) > STALE_RESET_DAYS (3 days)`:
- All positions treated as **new entries** → PnL = 0 on transition day
- `last_px` seeded from today's live prices → correct day-2 MTM
- NAV / peak / max_dd preserved (not reset)

```bash
# After git pull on VPS — reprocess all dates with the fix:
python3 scripts/paper_portfolio_engine.py --rebuild

# Run exposure audit:
python3 scripts/audit_paper_portfolio_exposure.py
```

### Exposure Thresholds

| metric | WARNING | HIGH_RISK |
|---|---|---|
| gross_exposure_ratio | > 1.0x | > 3.0x |
| max_single_pos_pct_nav | > 10% | — |
| abs(daily_pnl_pct) | > 20% | — |

## TASK-011A Market Data Freshness Fix Status

| item | status |
|---|---|
| Root cause identified | DONE (price lookup used signal_date 2026-04-30, not record_ts) |
| apps/forward_record/market_data.py | UPDATED — LiveReadOnlyMarketDataProvider + freshness helpers |
| apps/forward_record/primary.py | UPDATED — load_prices(record_ts); latest_prices_by_symbol(prices, record_ts) |
| scripts/run_forward_record.py | UPDATED — --data-source live_read_only added |
| scripts/run_forward_record_daily.sh | UPDATED — DATA_SOURCE=live_read_only default |
| tests/forward_record/test_market_data_freshness.py | NEW — 39 tests |
| pytest 242/242 (all forward_record tests) | PASS |
| bash -n run_forward_record_daily.sh | PASS |
| py_compile all modified files | PASS |
| local commits | PENDING (Rick must git push) |
| VPS: git pull then cron will auto-use live prices | PENDING |

### What changes on VPS after git pull

| before (frozen) | after (live) |
|---|---|
| data_source = cache_fallback | data_source = bybit_read_only_live |
| hypothetical_fill_px = 75750.0 every day | hypothetical_fill_px = Bybit lastPrice today |
| daily_pnl_pct = 0 always | daily_pnl_pct = real MTM change |
| freshness_status = STALE_OLD | freshness_status = FRESH |

### Override to force cache (testing)

```bash
DATA_SOURCE=cache_fallback bash scripts/run_forward_record_daily.sh
```

### Bybit public endpoint used

```
GET https://api.bybit.com/v5/market/tickers?category=linear
```
No authentication. Read-only. Returns lastPrice for all linear perpetuals.
Falls back silently to cache if network unavailable.

## TASK-010B Paper Portfolio Write Mode Status

| item | status |
|---|---|
| run_forward_record_daily.sh PAPER_PNL section | UPDATED — write mode by default |
| --dry-run removed from default cron invocation | DONE |
| PAPER_PNL_DRY_RUN=1 env var for manual dry-run | IMPLEMENTED |
| PAPER_FLAGS="" (write mode default) | IMPLEMENTED |
| PAPER_FLAGS="--dry-run" when PAPER_PNL_DRY_RUN=1 | IMPLEMENTED |
| tests/forward_record/test_paper_portfolio.py | +9 tests (TestDailyRunnerInvocation) |
| pytest 203/203 (all forward_record tests) | PASS |
| bash -n run_forward_record_daily.sh | PASS |
| py_compile paper_portfolio_engine.py | PASS |
| local commits | PENDING (Rick must git push) |
| VPS: --rebuild after git pull | PENDING |

### How to use

| mode | command |
|---|---|
| Normal daily cron (write mode) | cron runs run_forward_record_daily.sh (no env var needed) |
| Manual dry-run test | `PAPER_PNL_DRY_RUN=1 bash scripts/run_forward_record_daily.sh` |
| Standalone engine write | `python3 scripts/paper_portfolio_engine.py` |
| Standalone engine dry-run | `python3 scripts/paper_portfolio_engine.py --dry-run` |
| Back-fill all dates | `python3 scripts/paper_portfolio_engine.py --rebuild` |

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
