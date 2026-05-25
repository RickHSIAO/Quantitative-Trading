# 30-Day Forward Validation — Dashboard Summary

Generated: 2026-05-25T04:05:00Z

## Clock

| field | value |
|---|---|
| start_date | 20260518 |
| days_completed | 1 |
| days_remaining | 29 |
| skipped_pre_clock_start | 1 |
| target_end | 20260617 |
| strategy | prev3y_crypto / combined_paper_safe_variant |
| validation_mode | forward-record / dry-run only |

## Safety Gates (must remain constant)

| gate | value |
|---|---|
| paper_execution_status | FORBIDDEN |
| live_trading_status | FORBIDDEN |
| order_endpoint_called | False |
| bybit_write_called | False |

## Latest Day (20260518)

| metric | value |
|---|---|
| runner_status | REVIEW_READY |
| data_source | cache_fallback |
| safety_scan | PASS |
| dry_run | True |
| paper_execution_status | FORBIDDEN |
| live_trading_status | FORBIDDEN |
| signal_count | 50.0 |
| daily_pnl_pct | 0.0000% |
| cumulative_pnl_pct | 0.0000% |
| max_dd_pct | -0.0000% |
| sharpe_cumulative | N/A |
| alerts_triggered | 0.0 |
| review_006b_ready | False |

## Run Summary (1 days)

| metric | value |
|---|---|
| days_ok (REVIEW_READY/DRY_RUN) | 1 |
| days_error | 0 |
| forward_summary_status | {'max_dd_pass': True, 'no_stop_gate_triggered': True, 'overlay_always_pass': True, 'sharpe_pass': None} |

## Daily Log

| date | status | signals | daily_pnl | cum_pnl | max_dd | alerts |
|---|---|---|---|---|---|---|
| 20260518 | REVIEW_READY | 50.0 | 0.0000% | 0.0000% | -0.0000% | 0.0 |
