# Next Action

## TASK-014H Status (2026-06-09)

| item | status |
|---|---|
| scripts/preview_demo_readonly_runtime.py — positions[] + position_details_source | DONE |
| scripts/preview_demo_position_reconcile.py — load real positions, fail-closed on missing | DONE |
| scripts/preview_demo_close_only_cleanup.py — thread position_details_source through plan_cleanup | DONE |
| scripts/execute_demo_close_only_cleanup.py — report displays position_details_source | DONE |
| src/demo_position_reconcile.py — ReconciliationResult.position_details_source + positions[] | DONE |
| src/demo_close_only_cleanup.py — CleanupPlan.position_details_source, execute_ready gated | DONE |
| src/demo_close_only_sender.py — Gate 5b position_details_source_not_real_readonly | DONE |
| tests/demo_trading/test_demo_task_014h.py — 30 tests (H1-H13) | DONE |
| tests/demo_trading/test_demo_close_only_cleanup.py — fixtures updated | DONE |
| tests/demo_trading/test_demo_close_only_sender.py — helper updated | DONE |
| pytest tests/demo_trading | 614/614 PASS |
| py_compile all modified files | PASS |
| reconciliation fail-closed when real smoke lacks positions details | CONFIRMED |
| cleanup execute_ready=False when source != real_readonly | CONFIRMED |
| sender Gate 5b blocks fixture-only candidates (ETHUSDT / BNBUSDT) | CONFIRMED |
| no orders sent / no Demo POST issued in pipeline | CONFIRMED |
| no API key / secret bytes in any JSON or MD report | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| local commit | PENDING (Rick must git push) |

## Next Rick Action (set by 2026-06-09 TASK-014H)

1. git push origin main (delivers TASK-014D through TASK-014H)
2. On VPS after git pull — refresh pipeline (in order):
     source .env.demo
     python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
     python3 scripts/preview_demo_position_reconcile.py --from-latest-smoke --write-report
     python3 scripts/preview_demo_close_only_cleanup.py --from-latest-reconciliation \\
         --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) --write-report
3. Verify the cleanup plan now references the REAL Demo symbols (e.g. AIXBTUSDT,
   ENAUSDT, BOMEUSDT, EDUUSDT, MERLUSDT, XAUTUSDT, POLYXUSDT, TIAUSDT), not
   ETHUSDT / BNBUSDT.
4. Dry-run single close gated on real symbol (review before executing):
     python3 scripts/execute_demo_close_only_cleanup.py \\
         --from-latest-cleanup \\
         --symbol <REAL_SYMBOL_FROM_RECONCILIATION> \\
         --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) \\
         --write-report
5. Review outputs/demo_trading/close_only_execution/latest_close_only_execution.md
   (position_details_source must read `real_readonly`; source_position_details_is_real
   must be True before execute is permitted).
6. Manual execute decision is Rick's; sender still requires --execute-close-only.

## Status
READY (Rick action: git push + VPS pipeline + dry-run review + manual execute decision)

## Owner
Rick

## TASK-014G Status (2026-06-06)

| item | status |
|---|---|
| src/demo_close_only_sender.py — DemoCloseOnlySender, CloseOrderResult | DONE |
| src/demo_close_only_sender.py — layered gate checks + pre-send refresh | DONE |
| scripts/execute_demo_close_only_cleanup.py — CLI gate + one-order limit | DONE |
| tests/demo_trading/test_demo_close_only_sender.py — 90 tests (G1-G23) | DONE |
| pytest tests/demo_trading/ | 584/584 PASS |
| py_compile all new files | PASS |
| .gitignore — outputs/demo_trading/close_only_execution/ | DONE |
| dry-run default: no send | CONFIRMED |
| execute_close_only=True: pre-send refresh + Demo endpoint only | CONFIRMED |
| one-order-per-invocation limit enforced in CLI | CONFIRMED |
| reduce_only=True enforced at gate | CONFIRMED |
| close_side: Buy=close short, Sell=close long | CONFIRMED |
| secret_value_observed=False always | CONFIRMED |
| no_live_endpoint=True always | CONFIRMED |
| source scan: no live hostname, no leverage/stop/fund-movement ops | PASS |
| main.py / src/risk.py / exchange executors | NOT MODIFIED |
| local commit | PENDING (Rick must git push) |

## Next Rick Action (set by 2026-06-06 TASK-014G)

1. git push origin main (delivers TASK-014D through TASK-014G)
2. On VPS after git pull — refresh pipeline (in order):
     source .env.demo
     python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
     python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report
     python3 scripts/preview_demo_close_only_cleanup.py --from-latest-reconciliation \\
         --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) --write-report
3. Dry-run single close (review before executing):
     python3 scripts/execute_demo_close_only_cleanup.py \\
         --from-latest-cleanup \\
         --symbol ETHUSDT \\
         --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) \\
         --write-report
4. Review outputs/demo_trading/close_only_execution/latest_close_only_execution.md
5. If dry-run passes all gates (execute_allowed=True), Rick manually decides:
     python3 scripts/execute_demo_close_only_cleanup.py \\
         --from-latest-cleanup \\
         --symbol ETHUSDT \\
         --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) \\
         --execute-close-only \\
         --write-report
6. Repeat for BNBUSDT if needed.
7. Commit forward_record bundle (MM files) — see TASK-013 section below.

NOTE: Step 5 is Rick's decision. Claude has not sent any orders.
      TASK-014G is a gate, not an auto-executer.

## Status
READY (Rick action: git push + VPS pipeline + dry-run review + manual execute decision)

## Owner
Rick

## TASK-014F Status (2026-06-06)

| item | status |
|---|---|
| src/demo_close_only_cleanup.py — plan_cleanup() pure computation | DONE |
| src/demo_close_only_cleanup.py — CleanupPlan, ClosePayloadPreview, CloseCandidate | DONE |
| scripts/preview_demo_close_only_cleanup.py — fixture + --from-latest-reconciliation | DONE |
| scripts/preview_demo_close_only_cleanup.py — --confirm-token + --write-report | DONE |
| tests/demo_trading/test_demo_close_only_cleanup.py — 89 tests (E1-E19) | DONE |
| pytest tests/demo_trading/ | 494/494 PASS |
| py_compile all new files | PASS |
| .gitignore — outputs/demo_trading/close_only_cleanup/ | DONE |
| execute_ready gate: all 6 conditions enforced | CONFIRMED |
| no_orders_sent=True always | CONFIRMED |
| no_position_modified=True always | CONFIRMED |
| order_endpoint_called=False always | CONFIRMED |
| close side: Buy=close short, Sell=close long (Bybit derivatives) | CONFIRMED |
| deterministic sort: stop_risk DESC → notional DESC → symbol ASC | CONFIRMED |
| confirmation token expires daily: CONFIRM_DEMO_CLOSE_ONLY_YYYYMMDD | CONFIRMED |
| main.py / src/risk.py / exchange executors | NOT MODIFIED |
| local commit | PENDING (Rick must git push) |

## Next Rick Action (set by 2026-06-06 TASK-014F)

1. git push origin main (delivers TASK-014D through TASK-014F)
2. On VPS after git pull:
     source .env.demo
     python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
     python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report
     python3 scripts/preview_demo_close_only_cleanup.py --from-latest-reconciliation
3. If short_count > 5 or available_balance = 0, generate close confirmation token:
     python3 scripts/preview_demo_close_only_cleanup.py \
       --from-latest-reconciliation \
       --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) \
       --write-report
4. Review outputs/demo_trading/close_only_cleanup/latest_cleanup_plan.md
5. Execute closes manually on Bybit Demo (close-only, reduce_only=True, review each)
6. Commit forward_record bundle (MM files) — see TASK-013 section below

## Status
READY (Rick action: git push + VPS smoke + reconcile + close-only preview + manual closes if needed)

## Owner
Rick

## TASK-014E Status (2026-06-06)

| item | status |
|---|---|
| src/demo_position_reconcile.py | DONE — reconcile() pure computation, 9 violation types |
| scripts/preview_demo_position_reconcile.py | DONE — fixture + --from-latest-readonly-smoke + --write-report |
| tests/demo_trading/test_demo_position_reconcile.py | DONE — 84 tests PASS (F1-F16) |
| pytest tests/demo_trading/ | 405/405 PASS |
| py_compile all new files | PASS |
| .gitignore — outputs/demo_trading/reconciliation/ | DONE |
| main.py / src/risk.py / exchange executors | NOT MODIFIED |
| No orders sent / no positions modified / no secrets | CONFIRMED |
| local commit | PENDING (Rick must git push) |

## Real Demo Account Reconciliation Conclusions

| metric | value | status |
|---|---|---|
| equity_usd | ~11,404.01 | — |
| available_balance_usd | 0.00 | VIOLATION |
| open_positions_count | 8 | within limit (max 10) |
| short_count (estimated) | 7 | VIOLATION (max 5) |
| new_entry_allowed | False | BLOCKED |
| cannot_proceed_to_order_smoke | True | YES |

Suggested actions:
1. pause_new_entries
2. review_legacy_short_positions
3. reduce_short_count_to_max_5_manually (or via TASK-014F close-only task)
4. restore_available_balance_before_enabling_new_entries

→ TASK-014F Demo Close-only Manual Confirmed Cleanup needed if manual reduction required.

## Next Rick Action (set by 2026-06-06 TASK-014E)

1. git push origin main (delivers TASK-014D through TASK-014E)
2. On VPS after git pull:
     source .env.demo
     python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
     python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report
3. Review reconciliation report: outputs/demo_trading/reconciliation/latest_reconciliation.md
4. Decide if TASK-014F (close-only confirmed cleanup) is needed
5. Commit forward_record bundle (MM files) — see TASK-013 section below

## TASK-014D Status (2026-06-06)

| item | status |
|---|---|
| src/demo_readonly_client.py — _proof_real STRONG/WEAK/MISSING | DONE |
| src/demo_readonly_client.py — api_secret_present tracking | DONE |
| src/demo_runtime_adapter.py — reject PROOF_WEAK/MISSING | DONE |
| scripts/preview_demo_readonly_runtime.py — --write-report, early exit | DONE |
| scripts/preview_demo_readonly_runtime.py — proof_strength + api_secret_present display | DONE |
| tests/demo_trading/test_demo_readonly_client.py | +25 tests (66 total) |
| tests/demo_trading/test_demo_runtime_adapter.py | +24 tests (97 total) |
| pytest tests/demo_trading/ | 321/321 PASS |
| py_compile all modified files | PASS |
| .gitignore — .env.demo + outputs/demo_trading/readonly_smoke/ | DONE |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| No orders sent / no secrets / no API calls (fixture mode) | CONFIRMED |
| local commit bb511f0 | DONE |

## TASK-014C Status (2026-06-06)

| item | status |
|---|---|
| src/demo_readonly_client.py | DONE — fixture + real mode, HMAC signing, no secrets in output |
| src/demo_runtime_adapter.py | DONE — adapts wallet/positions/instruments/proof to Phase 2 input |
| scripts/preview_demo_readonly_runtime.py | DONE — fixture dry-run preview, --real-readonly flag |
| tests/demo_trading/test_demo_readonly_client.py | DONE — 41 tests PASS |
| tests/demo_trading/test_demo_runtime_adapter.py | DONE — 73 tests PASS |
| pytest tests/demo_trading/ | 291/291 PASS |
| py_compile all new files | PASS |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| No orders sent / no secrets / no API calls (fixture mode) | CONFIRMED |
| local commit | PENDING (Rick must git push) |

## TASK-014B Status (2026-06-06)

| item | status |
|---|---|
| src/demo_runtime_probe.py | DONE — 6-check fail-closed probe, no API calls |
| src/demo_instrument_rules.py | DONE — qty_step / tick_size / min_qty / min_notional rounding |
| src/demo_portfolio_risk.py | DONE — Phase 2 batch fractional-Kelly sizer |
| apps/demo_trading/ (config + kelly_sizer) | DONE |
| scripts/preview_demo_runtime_and_rounding.py | DONE — integrated dry-run preview |
| scripts/preview_demo_portfolio_sizing.py | DONE |
| scripts/demo_trading_preview.py | DONE |
| tests/demo_trading/test_demo_runtime_probe.py | DONE — 55 tests PASS |
| tests/demo_trading/test_demo_instrument_rules.py | DONE — 64 tests PASS |
| tests/demo_trading/test_demo_portfolio_risk.py | DONE — 58 tests PASS |
| pytest tests/demo_trading/ | 177/177 PASS |
| py_compile all new files | PASS |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| No orders sent / no secrets / no API calls | CONFIRMED |
| local commit 815003c | DONE |
| pushed to origin/main | PENDING (Rick must git push) |

## (superseded — see TASK-014E section above for current actions)

### TASK-014D→E Forward Record Bundle (still pending)

1. Stage and commit remaining forward_record TASK-009..013 files
   (these have MM or untracked status after the TASK-014B commit):

     git add apps/forward_record/market_data.py \
             apps/forward_record/primary.py \
             scripts/paper_portfolio_engine.py \
             scripts/build_forward_validation_dashboard.py \
             scripts/run_forward_record.py \
             scripts/run_forward_record_daily.sh \
             scripts/sync_forward_validation_to_notion.py \
             scripts/audit_paper_portfolio_exposure.py \
             tests/forward_record/test_paper_portfolio.py \
             tests/forward_record/test_market_data_freshness.py \
             tests/forward_record/test_paper_portfolio_audit.py \
             tests/forward_record/test_paper_portfolio_guard.py \
             tests/forward_record/test_notion_sync.py \
             docs/research/commands/COMMAND_LOG.md \
             docs/research/commands/NEXT_ACTION.md
     git commit -m "TASK-013: add Notion historical backfill sync (TASK-009..013 bundle)"

2. Push (delivers TASK-008D through TASK-014B):
     git push origin main

3. On the VPS:
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
