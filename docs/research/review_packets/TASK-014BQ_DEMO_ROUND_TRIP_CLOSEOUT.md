# TASK-014BQ — Bybit Demo SOLUSDT manual execution-pipeline validation round trip

**Environment:** BYBIT_DEMO_ONLY

> Manually authorized **execution-pipeline validation** round trip. **NOT** a strategy trade and **NOT** pilot performance. Excluded from all strategy/pilot metrics.

## Opening (TASK-014BO)

- order_id: `77173918-71f6-4829-91c9-025bd8cd76fa`
- orderLinkId: `BO1-4696d511edf11b50`
- side / type / TIF: Buy / Market / IOC
- quantity: 0.1 (reduceOnly=False)
- avg_fill_price: 74.11
- cum_exec_qty: 0.1
- execution_fee: 0.00407605
- position_after: 0.1
- final_conclusion: `DEMO_ORDER_FILLED_VERIFIED`
- journal_final_state: `POST_RESULT_VERIFIED`
- armed_utc / verified_utc: 2026-06-21T10:30:39Z / 2026-06-21T10:30:40Z

## Closing (TASK-014BP, reduce-only)

- close_order_id: `4ae9e849-655c-4ac3-b830-d49d587c4f4c`
- close_orderLinkId: `BC1-566b8509e96b2def`
- side / type / TIF: Sell / Market / IOC
- quantity: 0.1 (reduceOnly=True)
- avg_fill_price: 73.8
- cum_exec_qty: 0.1
- execution_fee: 0.004059
- position_before / after: 0.1 / 0
- short_position_after: False
- final_conclusion: `DEMO_REDUCE_ONLY_CLOSE_FILLED_POSITION_ZERO_VERIFIED`
- journal_final_state: `CLOSE_RESULT_VERIFIED`
- armed_utc / verified_utc: 2026-06-21T11:09:21Z / 2026-06-21T11:09:22Z

## Round-trip calculation (Decimal)

- gross_price_pnl = (close - open) * qty = (73.8 - 74.11) * 0.1 = **-0.031**
- total_fees = 0.00407605 + 0.004059 = **0.00813505**
- estimated_net_pnl_excluding_funding = **-0.03913505** USDT (funding: unknown_not_included)

## Safety

- opening_post_count: 1
- closing_post_count: 1
- automatic_retry_count: 0
- position_zero_verified: True
- short_position_created: False

## Classification

- trade_classification: `MANUAL_EXECUTION_PIPELINE_VALIDATION`
- included_in_strategy_performance: False
- included_in_pilot_performance: False

Manually authorized execution-pipeline validation trade. NOT a strategy trade and NOT pilot performance. Do not mix this result into future strategy pilot metrics.
