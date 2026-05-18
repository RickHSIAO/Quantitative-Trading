# Codex Commands

Codex must read `docs/research/commands/NEXT_ACTION.md` before starting any project task.

## Execution Rules

- Only execute the task explicitly specified in `NEXT_ACTION.md` or Rick's latest direct chat instruction.
- If `NEXT_ACTION.md` status is not `READY`, do not start task work unless Rick's current chat message explicitly authorizes it.
- Do not use old TASK-002 artifacts or architecture:
  - `output/crypto_cost_stress.csv`
  - `scripts/crypto_cost_stress.py`
- Do not independently clear `BLOCKED` status.
- Do not mark any task `DONE`; completion should move to `REVIEW` unless Rick explicitly instructs otherwise.
- After completing an authorized task, update `docs/research/commands/COMMAND_LOG.md`.
- Preserve task red lines: do not modify strategy signals, ranking, universe, data-quality policy, immutable run outputs, or raw data unless the active workorder explicitly allows it.

## Default Completion Checklist

- Write only the files required by the active task.
- Run the smallest meaningful validation.
- Report official output paths, validation results, and skipped/deferred items.
- Leave unrelated dirty files untouched.


## task-003-implementation-plan

Read:
1. docs/research/codex_workorders/TASK-003_baseline_attribution.md
2. docs/research/commands/COMMAND_LOG.md
3. outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet
4. outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet
5. outputs/backtests/prev3y_crypto/20260515_cost_stress_summary.json
6. data/crypto/funding_rates.parquet
7. data/crypto/prices_daily.parquet
8. data/crypto/universe_membership.parquet

Do:
- Provide TASK-003 implementation plan only.
- Do not implement yet.
- Explain attribution methodology.
- Explain gross vs net-of-cost reconciliation.
- Explain `positions.date + 1` return dating.
- Explain tradable-membership filtering.
- Explain output files and schemas.
- Explain warning / fail gates.
- Explain reproducibility hash.

Do not:
- Do not implement TASK-003 yet.
- Do not modify strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not modify official outputs.
- Do not mark TASK-003 DONE.

## produce-review-packet

Read:
1. The task workorder.
2. The official task outputs.
3. The official task log.
4. Relevant summary JSON files.
5. Relevant queue entries only if needed.

Do:
- Read official task outputs.
- Compute key numbers.
- Extract gate results.
- Extract caveats.
- Extract reconciliation diagnostics.
- Extract reproducibility status.
- Write review packet to:
  docs/research/review_packets/<TASK_ID>_REVIEW_PACKET.md
- Write machine-readable numbers to:
  docs/research/review_packets/<TASK_ID>_REVIEW_NUMBERS.json
- Update COMMAND_LOG.md.

Do not:
- Do not modify strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not modify official outputs.
- Do not decide PASS / FAIL.
- Do not update task status to DONE.

Expected output:
- REVIEW_PACKET.md
- REVIEW_NUMBERS.json
- COMMAND_LOG.md updated

## task-007-readiness

Read:
1. docs/research/codex_workorders/TASK-007_long_side_variant_study.md
2. docs/research/CODEX_TASK_QUEUE.md
3. docs/research/CLAUDE_REVIEW_QUEUE.md
4. docs/research/commands/COMMAND_LOG.md
5. outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv
6. outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet
7. outputs/backtests/prev3y_crypto/20260515_cost_stress.csv
8. outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet
9. outputs/attribution/prev3y_crypto/20260515_attribution_summary.json

Do:
- Perform TASK-007 readiness check only.
- Check required input files exist.
- Check schemas are compatible with the long-side variant study.
- Confirm variants can be computed as overlays without modifying strategy code.
- Confirm whether short_only / long_only / long_half_weight / symbol cap / DOT cap can be computed from official outputs.
- Return readiness_status:
  - READY_TO_IMPLEMENT
  - BLOCKED_BY_DATA
  - NEED_CLARIFICATION
- If READY_TO_IMPLEMENT, provide implementation plan.

Do not:
- Do not implement TASK-007 yet.
- Do not modify strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not modify official outputs.
- Do not approve paper trading.
- Do not approve live trading.
- Do not mark TASK-007 DONE.

## task-007-implementation-plan

Read:
1. docs/research/codex_workorders/TASK-007_long_side_variant_study.md
2. docs/research/commands/COMMAND_LOG.md
3. outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv
4. outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet
5. outputs/backtests/prev3y_crypto/20260515_cost_stress.csv
6. outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet
7. outputs/attribution/prev3y_crypto/20260515_attribution_summary.json
8. data/crypto/prices_daily.parquet
9. data/crypto/funding_rates.parquet

Do:
- Prepare TASK-007 implementation plan only.
- Do not implement yet.
- Explain how each variant will be computed as a post-processing overlay.
- Explain how positions.date + 1 return dating will be reused.
- Explain how realistic_combo costs will be reused.
- Explain how gross/net reconciliation will be checked.
- Explain output files and schemas.
- Explain warning / fail gates.
- Explain reproducibility hash.
- Explain how TASK-007 review packet will be generated.

Variants must include:
- baseline current long/short
- short_only
- long_only
- no_long_side
- long_half_weight
- long_with_50pct_cap
- top5_symbol_cap_5pct
- no_DOT_or_DOT_capped
- high_funding_cost_filter
- combined_paper_safe_variant

Do not:
- Do not implement TASK-007 yet.
- Do not modify strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not modify official outputs.
- Do not approve paper trading.
- Do not approve live trading.
- Do not mark TASK-007 DONE.

## task-007-plan-revision

Read:
1. docs/research/codex_workorders/TASK-007_long_side_variant_study.md
2. docs/research/commands/COMMAND_LOG.md
3. outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet
4. outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet

Do:
- Revise TASK-007 implementation plan only.
- Do not implement yet.
- Clarify these required methodology points:

1. Weight scaling policy:
   - Include both unscaled and rescaled variants where needed:
     - short_only_unscaled
     - short_only_rescaled
     - long_only_unscaled
     - long_only_rescaled
   - Explain gross exposure target for each.

2. Cap policy:
   - For symbol caps and DOT cap, use cap_no_redistribution as primary.
   - Explain whether any redistribution variant will be included.
   - If redistribution is included, name it separately.

3. Cost scaling policy:
   - For each symbol-day:
     - if original_weight != 0:
       cost_scale = abs(variant_weight / original_weight)
       variant_fee_cost = original_fee_cost * cost_scale
       variant_slippage_cost = original_slippage_cost * cost_scale
       variant_funding_cost = original_funding_cost * cost_scale
     - if variant_weight == 0:
       all costs = 0
   - Do not recalculate funding from raw funding rates for TASK-007 primary outputs.
   - Use official TASK-002 realistic_combo symbol costs.

4. Baseline reconciliation:
   - baseline_current_long_short must exactly match TASK-002 realistic_combo net return.
   - max diff must be <= 1e-6.

5. Variant interpretation:
   - Clearly mark variants as overlay studies, not new strategy backtests.
   - Do not treat results as live-ready.

Output:
- Revised implementation plan in the reply.
- Update COMMAND_LOG.md.

Do not:
- Do not implement TASK-007.
- Do not modify strategy code.
- Do not rerun baseline / cost stress / attribution.
- Do not modify official outputs.
- Do not approve paper or live trading.

## task-007-implement

Read:
1. docs/research/codex_workorders/TASK-007_long_side_variant_study.md
2. docs/research/commands/COMMAND_LOG.md
3. outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv
4. outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet
5. outputs/backtests/prev3y_crypto/20260515_cost_stress.csv
6. outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet
7. outputs/attribution/prev3y_crypto/20260515_attribution_summary.json
8. data/crypto/prices_daily.parquet
9. data/crypto/funding_rates.parquet

Do:
- Implement TASK-007 Long-side Variant Study using post-processing overlays only.
- Use positions.date + 1 day = return_date.
- Use official TASK-002 realistic_combo symbol-day costs.
- Do not recalculate primary costs from raw funding.
- Produce official TASK-007 outputs.
- Produce REVIEW-007 packet and numbers JSON.
- Update CODEX_TASK_QUEUE.md to REVIEW when complete.
- Update COMMAND_LOG.md.

Required variants:
- baseline_current_long_short
- short_only_unscaled
- short_only_rescaled
- long_only_unscaled
- long_only_rescaled
- no_long_side
- long_half_weight
- long_with_50pct_cap
- top5_symbol_cap_5pct
- DOT_capped
- no_DOT
- high_funding_cost_filter
- combined_paper_safe_variant

Required policies:
1. Weight scaling:
   - short_only_unscaled: keep original short weights, set long weights to zero.
   - short_only_rescaled: set long weights to zero, rescale short side to original same-day gross exposure.
   - long_only_unscaled: keep original long weights, set short weights to zero.
   - long_only_rescaled: set short weights to zero, rescale long side to original same-day gross exposure.

2. Cap policy:
   - Primary cap variants use cap_no_redistribution.
   - Excess weight is removed, not redistributed.
   - Any redistribution variant must be separately named and not mixed into primary results.

3. Cost scaling:
   - For each symbol-day:
     - if original_weight != 0:
       cost_scale = abs(variant_weight / original_weight)
       variant_fee_cost = original_fee_cost * cost_scale
       variant_slippage_cost = original_slippage_cost * cost_scale
       variant_funding_cost = original_funding_cost * cost_scale
     - if variant_weight == 0:
       all costs = 0
   - Use official TASK-002 realistic_combo symbol-day costs.
   - Do not recalculate primary funding costs from raw funding rates.

4. Baseline reconciliation:
   - baseline_current_long_short must match TASK-002 realistic_combo net return.
   - max diff must be <= 1e-6.
   - If mismatch > 1e-6, stop and report NEED_CLARIFICATION.

Outputs:
- outputs/variants/prev3y_crypto/<YYYYMMDD>_task007_variant_daily.csv
- outputs/variants/prev3y_crypto/<YYYYMMDD>_task007_variant_summary.csv
- outputs/variants/prev3y_crypto/<YYYYMMDD>_task007_variant_summary.json
- outputs/variants/prev3y_crypto/<YYYYMMDD>_task007_variant_concentration.csv
- outputs/variants/prev3y_crypto/<YYYYMMDD>_task007_variant_cost_breakdown.csv
- outputs/logs/prev3y_crypto/<YYYYMMDD>_task007_variant_study.log
- docs/research/review_packets/REVIEW-007_PACKET.md
- docs/research/review_packets/REVIEW-007_NUMBERS.json

Metrics:
- active Sharpe
- IR vs cash
- IR vs equal-weight
- IR vs BTC
- max DD
- net alpha
- gross alpha
- long contribution
- short contribution
- top 5 concentration
- single symbol concentration
- fee cost
- slippage cost
- funding cost
- gross exposure
- net exposure
- turnover proxy if available

Warning / fail gates:
- baseline mismatch > 1e-6 → FAIL
- missing outputs → FAIL
- schema mismatch → FAIL
- short_only_rescaled max DD worse than baseline by > 1.5x → WARNING
- long_only_rescaled net alpha remains negative → WARNING
- combined_paper_safe_variant Sharpe drops below 0.5 → WARNING
- combined_paper_safe_variant IR vs equal-weight drops below 0.2 → WARNING
- top 5 concentration remains > 60% → WARNING
- single symbol concentration remains > 25% → WARNING
- cap variants destroy more than 50% of net alpha → WARNING

Do not:
- Do not modify strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not modify official outputs.
- Do not approve paper trading.
- Do not approve live trading.
- Do not mark TASK-007 DONE.

## task-006-readiness

Read:
1. docs/research/codex_workorders/TASK-006_paper_trading_plan.md
2. docs/research/CODEX_TASK_QUEUE.md
3. docs/research/CLAUDE_REVIEW_QUEUE.md
4. docs/research/commands/COMMAND_LOG.md
5. docs/research/review_packets/REVIEW-007_PACKET.md
6. docs/research/review_packets/REVIEW-007_NUMBERS.json

Do:
- Perform TASK-006 readiness check only.
- Verify the workorder is planning / simulation / logging only.
- Verify no real exchange order submission is allowed.
- Verify primary spec is combined_paper_safe_variant.
- Verify secondary spec is high_funding_cost_filter.
- Verify mandatory overlays are present:
  - funding_filter > 0.03%/8h
  - long_cap_50pct
  - symbol_cap_5pct
- Verify execution prerequisites are present:
  - TASK-007b PASS before paper execution
  - TASK-005 VPS monitor online
  - REVIEW-006b PASS
  - 30 days forward validation
- Verify kill switch rules are present.
- Verify live trading remains forbidden.
- Return readiness_status:
  - READY_TO_IMPLEMENT
  - BLOCKED_BY_SPEC
  - NEED_CLARIFICATION
- If READY_TO_IMPLEMENT, provide implementation plan only.

Do not:
- Do not implement TASK-006 yet.
- Do not write exchange order submission code.
- Do not connect to Bybit API for trading.
- Do not start paper trading.
- Do not start live trading.
- Do not modify strategy code.
- Do not modify official research outputs.
- Do not mark TASK-006 DONE.

## task-006-implementation-plan

Read:
1. docs/research/codex_workorders/TASK-006_paper_trading_plan.md
2. docs/research/commands/COMMAND_LOG.md
3. docs/research/review_packets/REVIEW-007_PACKET.md
4. docs/research/review_packets/REVIEW-007_NUMBERS.json
5. docs/research/CODEX_TASK_QUEUE.md
6. docs/research/CLAUDE_REVIEW_QUEUE.md

Do:
- Prepare TASK-006 implementation plan only.
- Do not implement yet.
- Explain the exact module structure under apps/paper_trading/.
- Explain how primary spec combined_paper_safe_variant will be represented.
- Explain how secondary spec high_funding_cost_filter will be tracked.
- Explain how mandatory overlays will be enforced:
  - funding_filter > 0.03%/8h
  - long_cap_50pct
  - symbol_cap_5pct
- Explain sizing calculator.
- Explain risk rules engine.
- Explain order recorder that records intended orders only.
- Explain forward validation evaluator.
- Explain monitor hook stub for TASK-005.
- Explain report outputs and review packet.
- Explain kill switches:
  - max DD > 30%
  - 5 consecutive losing cycles
  - NAV < 70%
- Explain how the implementation prevents real exchange order submission.
- Explain tests / validation checks.
- Explain reproducibility hash and logs.

Do not:
- Do not implement TASK-006 yet.
- Do not write exchange order submission code.
- Do not connect to Bybit API for trading.
- Do not start paper trading execution.
- Do not start live trading.
- Do not modify strategy code.
- Do not modify ranking / universe / data-quality policy.
- Do not modify official research outputs.
- Do not mark TASK-006 DONE.

Expected output:
- TASK-006 implementation plan in the reply.
- COMMAND_LOG.md updated.

## task-006-implement

Read:
1. docs/research/codex_workorders/TASK-006_paper_trading_plan.md
2. docs/research/commands/COMMAND_LOG.md
3. docs/research/review_packets/REVIEW-007_PACKET.md
4. docs/research/review_packets/REVIEW-007_NUMBERS.json
5. docs/research/CODEX_TASK_QUEUE.md
6. docs/research/CLAUDE_REVIEW_QUEUE.md

Do:
- Implement TASK-006 planning / simulation / logging modules only.
- Create apps/paper_trading/ with:
  - __init__.py
  - config.py
  - overlay.py
  - sizing.py
  - risk.py
  - recorder.py
  - validator.py
  - monitor_hook.py
  - report.py
  - README.md
- Implement primary spec: combined_paper_safe_variant.
- Implement secondary tracking spec: high_funding_cost_filter.
- Enforce mandatory overlays:
  - funding_filter: recent 30-day average funding rate > 0.03%/8h long symbol weight = 0
  - long_cap_50pct: long gross <= 50% of total gross
  - symbol_cap_5pct: abs(symbol weight) <= 5% gross exposure, no redistribution
- Implement sizing calculator that converts overlay-adjusted target weights into NAV-based USD notional.
- Implement risk engine with kill switches:
  - max DD > 30%
  - 5 consecutive losing cycles
  - NAV < 70%
- Implement recorder that records intended orders and simulated fills only.
- Implement validator for 30-day forward validation metrics.
- Implement monitor_hook stub for TASK-005 only:
  - heartbeat
  - risk_event
  - rebalance_summary
- Implement report generation and REVIEW-006 packet.
- Add tests / validation checks proving no real order submission is possible.
- Update CODEX_TASK_QUEUE.md to REVIEW when complete.
- Update COMMAND_LOG.md.

Required outputs:
- outputs/paper_trading/prev3y_crypto/<YYYYMMDD>_target_positions.json
- outputs/paper_trading/prev3y_crypto/<YYYYMMDD>_simulated_fills.csv
- outputs/paper_trading/prev3y_crypto/<YYYYMMDD>_daily_pnl.csv
- outputs/paper_trading/prev3y_crypto/<YYYYMMDD>_monthly_review.json
- outputs/paper_trading/prev3y_crypto/<YYYYMMDD>_risk_events.jsonl
- outputs/paper_trading/prev3y_crypto/<YYYYMMDD>_forward_validation.json
- outputs/logs/prev3y_crypto/<YYYYMMDD>_paper_trading_setup.log
- docs/research/review_packets/REVIEW-006_PACKET.md
- docs/research/review_packets/REVIEW-006_NUMBERS.json

Hard safety rules:
- Do not write exchange order submission code.
- Do not call Bybit private trading endpoints.
- Do not create place_order / submit_order / create_order functions.
- Do not accept API key or API secret.
- Do not connect to exchange trading API.
- Do not start paper trading execution.
- Do not start live trading.
- Do not modify strategy code.
- Do not modify ranking / universe / data-quality policy.
- Do not modify official research outputs.
- Do not mark TASK-006 DONE.
- If any code path can submit real or paper orders externally, stop and report NEED_CLARIFICATION.

Validation requirements:
- Tests or scanner must confirm no forbidden order submission terms / endpoints are present.
- Overlay tests must cover funding_filter, long_cap_50pct, symbol_cap_5pct.
- Risk tests must trigger all three kill switches.
- Recorder tests must confirm intended orders are only written to local CSV/JSON.
- Validator tests must confirm forward validation metrics are reproducible.
- Reproducibility hashes must be written to log and review packet.

## task-007b-readiness

Read:
1. docs/research/codex_workorders/TASK-007b_weight_cap_redistribution.md
2. docs/research/CODEX_TASK_QUEUE.md
3. docs/research/CLAUDE_REVIEW_QUEUE.md
4. docs/research/commands/COMMAND_LOG.md
5. outputs/variants/prev3y_crypto/20260515_task007_variant_daily.csv
6. outputs/variants/prev3y_crypto/20260515_task007_variant_summary.json
7. outputs/variants/prev3y_crypto/20260515_task007_variant_concentration.csv
8. docs/research/review_packets/REVIEW-007_PACKET.md
9. docs/research/review_packets/REVIEW-007_NUMBERS.json

Do:
- Perform TASK-007b readiness check only.
- Verify all required inputs exist.
- Verify schema compatibility.
- Verify cap redistribution can be computed as post-processing overlay.
- Verify cap values 20% / 15% / 10% can be tested.
- Verify same-side redistribution can be implemented:
  - long excess redistributed only to eligible long symbols
  - short excess redistributed only to eligible short symbols
- Verify warning gates are computable:
  - concentration_not_reduced
  - cap10_sharpe_drop
- Return readiness_status:
  - READY_TO_IMPLEMENT
  - BLOCKED_BY_DATA
  - NEED_CLARIFICATION
- If READY_TO_IMPLEMENT, provide implementation plan only.
- Update COMMAND_LOG.md.

Do not:
- Do not implement TASK-007b yet.
- Do not modify strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not rerun TASK-007.
- Do not modify official outputs.
- Do not approve paper execution.
- Do not approve live trading.
- Do not mark TASK-007b DONE.

## task-007b-implement

Read:
1. docs/research/codex_workorders/TASK-007b_weight_cap_redistribution.md
2. docs/research/commands/COMMAND_LOG.md
3. outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv
4. outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet
5. outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet
6. outputs/variants/prev3y_crypto/20260515_task007_variant_daily.csv
7. outputs/variants/prev3y_crypto/20260515_task007_variant_summary.json
8. outputs/variants/prev3y_crypto/20260515_task007_variant_concentration.csv
9. docs/research/review_packets/REVIEW-007_PACKET.md
10. docs/research/review_packets/REVIEW-007_NUMBERS.json

Do:
- Implement TASK-007b Weight Cap + Redistribution as post-processing overlays only.
- Add:
  - src/variants/task007b.py
  - scripts/task007b_weight_cap_redistribution.py
- Rebuild baseline overlay and verify max diff vs TASK-002 realistic_combo / TASK-007 baseline <= 1e-6.
- Implement cap levels:
  - cap_20pct
  - cap_15pct
  - cap_10pct
- Apply caps daily and separately by side:
  - long excess redistributes only to eligible long symbols
  - short excess redistributes only to eligible short symbols
- If same-side redistribution has no room:
  - reduce gross exposure
  - record redistribution_has_no_room
  - do not force redistribution to opposite side
- Scale costs by weight ratio:
  - cost_scale = abs(new_weight / original_weight)
  - if new_weight == 0, costs = 0
- Compute metrics:
  - Sharpe
  - IR vs equal-weight
  - IR vs BTC if available
  - max DD
  - net alpha
  - alpha retention
  - top5 concentration
  - single-symbol concentration
  - long net
  - short net
  - gross exposure
  - net exposure
  - fee / slippage / funding impact
- Compute warning gates:
  - concentration_not_reduced
  - cap10_sharpe_drop
  - top5 concentration remains above threshold
  - single-symbol concentration remains above threshold
  - alpha retention below threshold
- Compute fail gates:
  - baseline reconciliation mismatch > 1e-6
  - missing outputs
  - schema mismatch
  - any paper/live execution code appears
- Produce official TASK-007b outputs.
- Produce REVIEW-007b packet and numbers JSON.
- Update CODEX_TASK_QUEUE.md to REVIEW when complete.
- Update COMMAND_LOG.md.

Expected outputs:
- outputs/variants/prev3y_crypto/<YYYYMMDD>_task007b_cap_daily.csv
- outputs/variants/prev3y_crypto/<YYYYMMDD>_task007b_cap_summary.csv
- outputs/variants/prev3y_crypto/<YYYYMMDD>_task007b_cap_summary.json
- outputs/variants/prev3y_crypto/<YYYYMMDD>_task007b_redistribution_log.csv
- outputs/variants/prev3y_crypto/<YYYYMMDD>_task007b_gate_report.json
- outputs/logs/prev3y_crypto/<YYYYMMDD>_task007b_weight_cap_redistribution.log
- docs/research/review_packets/REVIEW-007b_PACKET.md
- docs/research/review_packets/REVIEW-007b_NUMBERS.json

Important caveats to document:
- 20% and 15% caps may be no-op because current max symbol weight is about 12.5% of gross.
- 10% cap has actual breaches: 61 dates and 488 position breaches from readiness check.
- 10% cap may have no redistribution room, so gross exposure may drop.
- cap15 concentration_not_reduced warning may trigger if cap15 is no-op.

Do not:
- Do not modify strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not rerun TASK-007.
- Do not modify official outputs.
- Do not approve paper execution.
- Do not approve live trading.
- Do not mark TASK-007b DONE.


## task-006-review006b-addenda

Read:
1. docs/research/CLAUDE_REVIEW_LOG.md
2. docs/research/CODEX_TASK_QUEUE.md
3. docs/research/commands/COMMAND_LOG.md
4. docs/research/review_packets/REVIEW-006_PACKET.md
5. docs/research/review_packets/REVIEW-006_NUMBERS.json
6. outputs/paper_trading/prev3y_crypto/20260516_forward_validation.json
7. outputs/paper_trading/prev3y_crypto/20260516_monthly_review.json
8. outputs/paper_trading/prev3y_crypto/20260516_simulated_fills.csv
9. outputs/logs/prev3y_crypto/20260516_paper_trading_setup.log

Do:
- Implement the three REVIEW-006 addenda only.
- Add proxy_sharpe_long_window to forward_validation.json:
  - include 90-day proxy Sharpe if enough data exists
  - include 760-day or full active-window proxy Sharpe if available
  - keep the existing 30-day proxy Sharpe
  - clearly label 30-day Sharpe as noisy short-window proxy
- Add fill_definition documentation:
  - document that simulated fills are position deltas versus prior period
  - explain why few fills can appear even when many positions exist
  - update README or review packet section as appropriate
- Add funding_filter_active_this_month to monthly_review.json:
  - boolean field
  - explain whether the funding filter actually triggered in the current monthly window
  - if false, explain that funding filter is regime-dependent and may be inactive when funding normalizes
- Update REVIEW-006_PACKET.md and REVIEW-006_NUMBERS.json.
- Update COMMAND_LOG.md.
- Move this addendum task to REVIEW or report completion status.

Do not:
- Do not start paper trading execution.
- Do not connect to Bybit or any exchange API.
- Do not write order submission code.
- Do not modify strategy code.
- Do not modify run008 / TASK-002 / TASK-003 / TASK-007 official outputs.
- Do not rerun baseline / cost stress / attribution / TASK-007 / TASK-007b.
- Do not approve paper execution.
- Do not approve live trading.
- Do not mark REVIEW-006b PASS.


## task-005-readiness

Read:
1. docs/research/codex_workorders/TASK-005_vps_bot_monitor.md
2. docs/research/CODEX_TASK_QUEUE.md
3. docs/research/CLAUDE_REVIEW_QUEUE.md
4. docs/research/commands/COMMAND_LOG.md
5. apps/paper_trading/monitor_hook.py
6. docs/research/review_packets/REVIEW-006_PACKET.md
7. docs/research/review_packets/REVIEW-006_NUMBERS.json

Do:
- Perform TASK-005 readiness check only.
- Verify the workorder is monitoring / logging / alerting only.
- Verify no order submission is allowed.
- Verify only read-only API access is allowed.
- Verify read-only key requirements are explicit:
  - no trade permission
  - no withdraw permission
  - no transfer permission
- Verify secret handling requirements:
  - secrets only from environment variables or local untracked config
  - secrets never written to repo
  - secrets never written to logs
  - secrets never written to outputs
- Verify integration with apps/paper_trading/monitor_hook.py can be implemented as a stub/interface.
- Verify heartbeat output schema is implementable.
- Verify alerts JSONL schema is implementable.
- Verify fail gates are computable:
  - api_key_permission_violation
  - secret_in_vcs
  - order_submission_code_present
  - monitor_auto_restart_present
  - heartbeat_schema_invalid
  - alerts_schema_invalid
- Return readiness_status:
  - READY_TO_IMPLEMENT
  - BLOCKED_BY_SPEC
  - NEED_CLARIFICATION
- If READY_TO_IMPLEMENT, provide implementation plan only.
- Update COMMAND_LOG.md.

Do not:
- Do not implement TASK-005 yet.
- Do not connect to any exchange API.
- Do not ask for API keys or secrets.
- Do not write order submission code.
- Do not write auto-restart code.
- Do not start paper execution.
- Do not start live trading.
- Do not modify strategy code.
- Do not modify official research outputs.
- Do not mark TASK-005 DONE.


## task-005-implementation-plan

Read:
1. docs/research/codex_workorders/TASK-005_vps_bot_monitor.md
2. docs/research/commands/COMMAND_LOG.md
3. apps/paper_trading/monitor_hook.py
4. .gitignore

Do:
- Prepare TASK-005 implementation plan only.
- Do not implement yet.
- Explain module structure under apps/monitor/.
- Explain heartbeat collector.
- Explain alert writer.
- Explain log scanner.
- Explain paper monitor hook integration.
- Explain read-only API boundary.
- Explain secret handling.
- Explain safety gates.
- Explain tests / validation.
- Explain outputs.
- Explain reproducibility / logs.

Mandatory first safety patch in implementation:
- Add configs/monitor_secrets.yaml to .gitignore.
- Add any other local secret patterns required by the workorder.
- Ensure secret_in_vcs gate checks this.

Required module plan:
- apps/monitor/__init__.py
- apps/monitor/config.py
- apps/monitor/heartbeat.py
- apps/monitor/alerts.py
- apps/monitor/log_scanner.py
- apps/monitor/schema.py
- apps/monitor/safety.py
- apps/monitor/report.py
- apps/monitor/README.md
- scripts/task005_vps_bot_monitor.py

Required outputs:
- outputs/monitor/prev3y_crypto/<YYYYMMDD>_heartbeat.parquet
- outputs/monitor/prev3y_crypto/alerts/<YYYYMMDD>.jsonl
- outputs/logs/prev3y_crypto/<YYYYMMDD>_monitor_setup.log
- docs/research/review_packets/REVIEW-005_PACKET.md
- docs/research/review_packets/REVIEW-005_NUMBERS.json

Safety requirements:
- read-only API only
- no trade permission
- no withdraw permission
- no transfer permission
- secrets only from environment variables or local untracked config
- secrets never in repo/log/output
- no order submission code
- no auto-restart bot code
- no paper execution
- no live trading

Forbidden terms / behaviors to scan:
- place_order
- submit_order
- create_order
- cancel_order
- set_leverage
- set_position_mode
- withdraw
- transfer
- api_secret written to logs or outputs
- auto_restart
- restart_bot

Do not:
- Do not implement TASK-005 yet.
- Do not connect to any exchange API.
- Do not ask for API keys or secrets.
- Do not write order submission code.
- Do not write auto-restart code.
- Do not start paper execution.
- Do not start live trading.
- Do not modify strategy code.
- Do not modify official research outputs.
- Do not mark TASK-005 DONE.

Expected output:
- TASK-005 implementation plan in reply.
- COMMAND_LOG.md updated.


## task-005-implement

Read:
1. docs/research/codex_workorders/TASK-005_vps_bot_monitor.md
2. docs/research/commands/COMMAND_LOG.md
3. apps/paper_trading/monitor_hook.py
4. .gitignore

Do:
- Implement TASK-005 VPS Bot Monitor as monitoring / logging / alerting only.
- Create apps/monitor/ modules:
  - apps/monitor/__init__.py
  - apps/monitor/config.py
  - apps/monitor/heartbeat.py
  - apps/monitor/alerts.py
  - apps/monitor/log_scanner.py
  - apps/monitor/schema.py
  - apps/monitor/safety.py
  - apps/monitor/report.py
  - apps/monitor/README.md
- Create scripts/task005_vps_bot_monitor.py.
- Create configs/monitor.yaml with safe non-secret defaults only.
- Do not create configs/monitor_secrets.yaml.
- Generate sample monitor outputs only.
- Generate REVIEW-005 packet and numbers JSON.
- Update CODEX_TASK_QUEUE.md to REVIEW when complete.
- Update COMMAND_LOG.md.

Required outputs:
- outputs/monitor/prev3y_crypto/<YYYYMMDD>_heartbeat.parquet
- outputs/monitor/prev3y_crypto/alerts/<YYYYMMDD>.jsonl
- outputs/logs/prev3y_crypto/<YYYYMMDD>_monitor_setup.log
- docs/research/review_packets/REVIEW-005_PACKET.md
- docs/research/review_packets/REVIEW-005_NUMBERS.json

Heartbeat requirements:
- timestamp
- bot_name
- environment
- status
- equity
- nav
- active_positions
- last_order_timestamp
- api_latency_ms
- process_alive
- paper_execution_status
- live_trading_status
- warning_count
- critical_count

Alert JSONL requirements:
- timestamp
- severity
- category
- message
- dedupe_key
- source
- action_required
- paper_execution_status
- live_trading_status

Safety requirements:
- read-only API only
- no trade permission
- no withdraw permission
- no transfer permission
- secrets only from environment variables or local ignored config
- secrets never in repo
- secrets never in logs
- secrets never in outputs
- no order submission code
- no auto-restart bot code
- no paper execution
- no live trading

Forbidden terms / behaviors to scan:
- place_order
- submit_order
- create_order
- cancel_order
- set_leverage
- set_position_mode
- withdraw
- transfer
- api_secret written to logs or outputs
- auto_restart
- restart_bot

Validation requirements:
- Safety scan must PASS.
- secret_in_vcs gate must PASS.
- heartbeat schema validation must PASS.
- alerts JSONL schema validation must PASS.
- monitor_hook integration stub must remain side-effect free.
- No exchange connection should be made.
- No API key should be requested.
- Reproducibility hash must be written to REVIEW-005_NUMBERS.json and log.

Do not:
- Do not connect to any exchange API.
- Do not ask for API keys or secrets.
- Do not write order submission code.
- Do not write auto-restart code.
- Do not start paper execution.
- Do not start live trading.
- Do not modify strategy code.
- Do not modify official research outputs.
- Do not mark TASK-005 DONE.


## fix-review-005-b1-gitignore

Read:
1. docs/research/review_drafts/REVIEW-005_DRAFT_BY_SONNET.md
2. .gitignore
3. apps/monitor/safety.py
4. tests/monitor/test_heartbeat.py
5. tests/monitor/test_alerts.py
6. docs/research/review_packets/REVIEW-005_PACKET.md
7. docs/research/review_packets/REVIEW-005_NUMBERS.json

Do:
- Fix the truncated .gitignore monitor secret pattern.
- Ensure .gitignore contains:
  - configs/monitor_secrets.yaml
  - configs/monitor_secrets.yml
  - configs/monitor_secrets.local.yaml
  - configs/monitor_secrets.local.yml
- Rerun:
  - python -m unittest tests.monitor.test_heartbeat tests.monitor.test_alerts
  - python scripts/task005_vps_bot_monitor.py --output-date 20260517
- Verify:
  - safety scan PASS
  - secret_in_vcs false
  - heartbeat schema PASS
  - alerts JSONL schema PASS
  - no exchange API
  - no API key / secret
  - no order code
  - no auto-restart code
- Refresh REVIEW-005_PACKET.md and REVIEW-005_NUMBERS.json if runner output changes.
- Update COMMAND_LOG.md.

Do not:
- Do not connect to exchange APIs.
- Do not ask for API keys or secrets.
- Do not write order submission code.
- Do not write auto-restart code.
- Do not start paper execution.
- Do not start live trading.
- Do not modify strategy code.
- Do not mark TASK-005 DONE.


## task-005a-readiness

Read:
1. docs/research/codex_workorders/TASK-005a_real_alert_channel.md
2. docs/research/CODEX_TASK_QUEUE.md
3. docs/research/CLAUDE_REVIEW_QUEUE.md
4. docs/research/commands/COMMAND_LOG.md
5. apps/monitor/
6. configs/monitor.yaml
7. .gitignore

Do:
- Perform TASK-005a readiness check only.
- Verify the workorder scope is real alert channel extension only.
- Verify local_jsonl must be preserved.
- Verify Telegram Bot API and Discord Webhook are supported as planned channels.
- Verify dry_run=true is default.
- Verify --test-send is explicit and separate from normal runs.
- Verify secrets are only allowed from:
  - environment variables
  - configs/monitor_secrets.local.yaml
- Verify configs/monitor_secrets.local.yaml is gitignored.
- Verify no real secret is required for tests.
- Verify mock tests can be implemented without real token/webhook.
- Verify fail gates are computable:
  - secret_hardcoded
  - secret_written_to_logs
  - local_jsonl_removed
  - exchange_api_present
  - order_submission_code_present
  - auto_restart_present
- Return readiness_status:
  - READY_TO_IMPLEMENT
  - BLOCKED_BY_SPEC
  - NEED_CLARIFICATION
- If READY_TO_IMPLEMENT, provide implementation plan only.
- Update COMMAND_LOG.md.

Do not:
- Do not implement TASK-005a yet.
- Do not ask Rick to paste token/webhook into chat.
- Do not connect to Telegram or Discord.
- Do not send test alert yet.
- Do not connect to exchange APIs.
- Do not write order submission code.
- Do not write auto-restart code.
- Do not approve paper execution.
- Do not approve live trading.
- Do not mark TASK-005a DONE.


## task-005a-implementation-plan

Read:
1. docs/research/codex_workorders/TASK-005a_real_alert_channel.md
2. docs/research/commands/COMMAND_LOG.md
3. apps/monitor/
4. configs/monitor.yaml
5. .gitignore
6. tests/monitor/

Do:
- Prepare TASK-005a implementation plan only.
- Do not implement yet.
- Explain how local_jsonl will be preserved.
- Explain Telegram Bot API channel design.
- Explain Discord Webhook channel design.
- Explain dry_run=true default behavior.
- Explain explicit --test-send behavior.
- Explain secret handling:
  - environment variables
  - configs/monitor_secrets.local.yaml
  - no secrets in repo/log/output/packet/COMMAND_LOG
- Explain config changes.
- Explain tests:
  - mock Telegram dry-run
  - mock Telegram test-send
  - mock Discord dry-run
  - mock Discord test-send
  - secret redaction
  - local_jsonl still written
  - forbidden terms scan
- Explain fail gates:
  - secret_hardcoded
  - secret_written_to_logs
  - local_jsonl_removed
  - exchange_api_present
  - order_submission_code_present
  - auto_restart_present
- Explain outputs and REVIEW-005a packet.
- Explain exactly what will not be done.

Planned modules:
- apps/monitor/channels/__init__.py
- apps/monitor/channels/base.py
- apps/monitor/channels/local_jsonl.py
- apps/monitor/channels/telegram.py
- apps/monitor/channels/discord.py
- apps/monitor/channels/secrets.py
- apps/monitor/channels/redaction.py
- tests/monitor/test_channels.py
- configs/monitor_secrets.example.yaml

Do not:
- Do not implement TASK-005a yet.
- Do not ask Rick to paste token/webhook into chat.
- Do not connect to Telegram or Discord.
- Do not send test alert yet.
- Do not create configs/monitor_secrets.local.yaml with real values.
- Do not connect to exchange APIs.
- Do not write order submission code.
- Do not write auto-restart code.
- Do not approve paper execution.
- Do not approve live trading.
- Do not mark TASK-005a DONE.

Expected output:
- TASK-005a implementation plan in reply.
- COMMAND_LOG.md updated.


## task-005a-implement

Read:
1. docs/research/codex_workorders/TASK-005a_real_alert_channel.md
2. docs/research/commands/COMMAND_LOG.md
3. apps/monitor/
4. configs/monitor.yaml
5. .gitignore
6. tests/monitor/

Do:
- Implement TASK-005a Real Alert Channel.
- Add channel modules:
  - apps/monitor/channels/__init__.py
  - apps/monitor/channels/base.py
  - apps/monitor/channels/local_jsonl.py
  - apps/monitor/channels/telegram.py
  - apps/monitor/channels/discord.py
  - apps/monitor/channels/secrets.py
  - apps/monitor/channels/redaction.py
- Add tests:
  - tests/monitor/test_channels.py
- Add safe example config:
  - configs/monitor_secrets.example.yaml
- Preserve local_jsonl behavior.
- Keep dry_run=true as default.
- Implement explicit --test-send path, but do not execute real test-send.
- Use injectable HTTP client for Telegram / Discord so tests use mocks only.
- Load secrets only from:
  - environment variables
  - configs/monitor_secrets.local.yaml
- Ensure configs/monitor_secrets.local.yaml remains gitignored.
- Redact tokens / webhook URLs / chat IDs from logs, outputs, packets, and COMMAND_LOG.
- Update monitor report / packet / numbers if needed.
- Produce REVIEW-005a packet and numbers JSON.
- Update CODEX_TASK_QUEUE.md to REVIEW when complete.
- Update COMMAND_LOG.md.

Required validations:
- python -m unittest tests.monitor.test_heartbeat tests.monitor.test_alerts tests.monitor.test_channels
- TASK-005a runner or existing monitor runner returns REVIEW_READY if applicable.
- Safety scan PASS.
- local_jsonl still written.
- secret redaction PASS.
- no exchange API.
- no order submission.
- no auto-restart.
- no real Telegram / Discord POST during normal run or tests.
- no configs/monitor_secrets.local.yaml with real values created.

Required outputs:
- docs/research/review_packets/REVIEW-005a_PACKET.md
- docs/research/review_packets/REVIEW-005a_NUMBERS.json
- outputs/logs/prev3y_crypto/<YYYYMMDD>_task005a_alert_channel.log
- Any updated monitor sample outputs if required by implementation.

Do not:
- Do not ask Rick to paste token/webhook into chat.
- Do not connect to Telegram or Discord.
- Do not send real test alert.
- Do not create configs/monitor_secrets.local.yaml with real values.
- Do not connect to exchange APIs.
- Do not write order submission code.
- Do not write auto-restart code.
- Do not start paper execution.
- Do not approve paper execution.
- Do not approve live trading.
- Do not modify strategy code.
- Do not mark TASK-005a DONE.


## task-008-readiness

Read:
1. docs/research/codex_workorders/TASK-008_alpha_space_concentration_cap.md
2. docs/research/CODEX_TASK_QUEUE.md
3. docs/research/CLAUDE_REVIEW_QUEUE.md
4. docs/research/commands/COMMAND_LOG.md
5. outputs/attribution/prev3y_crypto/20260515_attribution_summary.json
6. outputs/attribution/prev3y_crypto/20260515_attribution_by_symbol.csv
7. outputs/variants/prev3y_crypto/20260515_task007_variant_summary.json
8. outputs/variants/prev3y_crypto/20260516_task007b_cap_summary.csv
9. outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet
10. outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet

Do:
- Perform TASK-008 readiness check only.
- Verify this task is alpha-space only.
- Verify weight-space cap / redistribution is excluded and must not be reused.
- Verify required inputs exist and schemas support implementation.
- Verify rolling alpha-contribution cap is implementable.
- Verify alpha-share-based sizing is implementable.
- Verify cooldown blacklist is implementable.
- Verify baseline_current_long_short can be reconstructed.
- Verify combined_paper_safe_variant comparison is available.
- Verify metrics can be computed:
  - Sharpe
  - IR vs equal-weight
  - max DD
  - net alpha
  - top5 concentration
  - single-symbol concentration
  - long_net
  - short_net
  - alpha retention
  - cost impact
- Verify gates are computable.
- Return readiness_status:
  - READY_TO_IMPLEMENT
  - BLOCKED_BY_DATA
  - NEED_CLARIFICATION
- If READY_TO_IMPLEMENT, provide implementation plan only.
- Update COMMAND_LOG.md.

Do not:
- Do not implement TASK-008 yet.
- Do not modify main strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not approve paper execution.
- Do not approve live trading.
- Do not mark TASK-008 DONE.


## task-008-implementation-plan

Read:
1. docs/research/codex_workorders/TASK-008_alpha_space_concentration_cap.md
2. docs/research/commands/COMMAND_LOG.md
3. outputs/attribution/prev3y_crypto/20260515_attribution_summary.json
4. outputs/attribution/prev3y_crypto/20260515_attribution_by_symbol.csv
5. outputs/variants/prev3y_crypto/20260515_task007_variant_summary.json
6. outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet
7. outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet
8. data/crypto/prices_daily.parquet
9. data/crypto/universe_membership.parquet
10. configs/prev3y_crypto.yaml
11. src/signals/prev3y_momentum.py

Do:
- Prepare TASK-008 implementation plan only.
- Do not implement yet.
- Explain how baseline_current_long_short will be reconstructed.
- Explain how replacement candidate ranks will be obtained without modifying strategy code.
- Explain how build_prev3y_targets() will be reused or wrapped safely.
- Explain how rolling alpha-contribution share will be computed.
- Explain the three alpha-space variants:
  1. rolling alpha-contribution cap
  2. alpha-share-based position sizing
  3. top-contributor cooldown / blacklist
- Explain how costs will be scaled or rejoined from TASK-002 realistic_combo.
- Explain how TASK-007 combined_paper_safe_variant will be used as comparison.
- Explain how TASK-007b weight-space cap / redistribution will be excluded.
- Explain output files.
- Explain fail gates and warning gates.
- Explain reproducibility hash.
- Explain tests / validation.
- Update COMMAND_LOG.md.

Important constraints:
- Do not modify src/signals/prev3y_momentum.py.
- Do not modify main strategy code.
- Do not reuse TASK-007b weight-space redistribution logic.
- Do not rerun official baseline / TASK-002 / TASK-003.
- TASK-008 must be isolated under src/variants/task008.py and scripts/task008_alpha_conc_cap.py.

Expected output:
- TASK-008 implementation plan in reply.
- COMMAND_LOG.md updated.

Do not:
- Do not implement TASK-008 yet.
- Do not modify main strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not approve paper execution.
- Do not approve live trading.
- Do not mark TASK-008 DONE.


## task-008-implement

Read:
1. docs/research/codex_workorders/TASK-008_alpha_space_concentration_cap.md
2. docs/research/commands/COMMAND_LOG.md
3. outputs/attribution/prev3y_crypto/20260515_attribution_summary.json
4. outputs/attribution/prev3y_crypto/20260515_attribution_by_symbol.csv
5. outputs/variants/prev3y_crypto/20260515_task007_variant_summary.json
6. outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet
7. outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet
8. data/crypto/prices_daily.parquet
9. data/crypto/universe_membership.parquet
10. configs/prev3y_crypto.yaml
11. src/signals/prev3y_momentum.py

Do:
- Implement TASK-008 alpha-space concentration cap in isolated files only.
- Add:
  - src/variants/task008.py
  - scripts/task008_alpha_conc_cap.py
  - focused tests under tests/variants/
- Reconstruct baseline_current_long_short from run008 positions plus TASK-002 realistic_combo costs.
- Use convention:
  - positions.date + 1 day = return_date
- Validate baseline reconciliation against existing TASK-003/TASK-007 reference max diff <= 1e-6.
- Reconstruct candidate ranks by reusing build_prev3y_targets() as read-only helper.
- Do not modify src/signals/prev3y_momentum.py.
- Implement three alpha-space variants:
  1. rolling alpha-contribution cap
  2. alpha-share-based position sizing
  3. top-contributor cooldown / blacklist
- Include baseline and TASK-007 combined_paper_safe_variant as references.
- Use TASK-002 realistic_combo symbol-day costs.
- Scale costs by abs(variant_weight / original_weight) where applicable.
- Set costs to zero where variant weight is zero.
- Do not recompute funding from raw funding rates.
- Explicitly exclude TASK-007b weight-space cap / redistribution.
- Compute metrics:
  - Sharpe
  - IR vs equal-weight
  - max DD
  - net alpha
  - alpha retention
  - top5 concentration
  - single-symbol concentration
  - long_net
  - short_net
  - cost impact
  - turnover
- Compute fail gates:
  - baseline mismatch > 1e-6
  - paper/live not FORBIDDEN
  - weight-space overlay detected
  - strategy file modified
  - missing outputs
  - bad concentration math
  - reproducibility hash mismatch
- Compute warning gates:
  - top5 > 75%
  - Sharpe < 0.70
  - alpha retention < 85%
  - turnover > 1.5x
  - cooldown fallback
  - long net < -10%
  - cost impact > 30 bps
- Produce outputs:
  - outputs/variants/prev3y_crypto/<YYYYMMDD>_task008_comparison.csv
  - outputs/variants/prev3y_crypto/<YYYYMMDD>_task008_comparison.json
  - outputs/variants/prev3y_crypto/<YYYYMMDD>_task008_variant_detail.csv
  - outputs/variants/prev3y_crypto/<YYYYMMDD>_task008_attribution.json
  - outputs/logs/prev3y_crypto/<YYYYMMDD>_task008_alpha_conc.log
  - docs/research/review_packets/REVIEW-008_PACKET.md
  - docs/research/review_packets/REVIEW-008_NUMBERS.json
- Update CODEX_TASK_QUEUE.md to REVIEW when complete.
- Update COMMAND_LOG.md.

Do not:
- Do not modify main strategy code.
- Do not modify src/signals/prev3y_momentum.py.
- Do not reuse TASK-007b weight-space redistribution.
- Do not rerun official baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not approve paper execution.
- Do not approve live trading.
- Do not mark TASK-008 DONE.


## task-009-readiness

Read:
1. docs/research/codex_workorders/TASK-009_forward_record_runner.md
2. docs/research/CODEX_TASK_QUEUE.md
3. docs/research/CLAUDE_REVIEW_QUEUE.md
4. docs/research/commands/COMMAND_LOG.md
5. apps/paper_trading/config.py
6. apps/paper_trading/overlay.py
7. apps/paper_trading/recorder.py
8. apps/paper_trading/validator.py
9. apps/monitor/
10. src/variants/task008.py
11. docs/research/manual_ops/30_day_forward_record_plan.md
12. docs/research/manual_ops/30_day_forward_start_checklist.md
13. docs/research/manual_ops/VPS_DEPLOYMENT_CHECKLIST.md

Do:
- Perform TASK-009 readiness check only.
- Verify the workorder scope is forward record / offline paper record only.
- Verify no order submission is allowed.
- Verify no private trading endpoint is required.
- Verify Bybit usage is read-only GET only.
- Verify API keys are only allowed from environment variables and never written to output/logs.
- Verify existing apps/paper_trading modules can be reused safely:
  - config.py
  - overlay.py
  - recorder.py
  - validator.py
- Verify TASK-008 shadow-track can be integrated from src/variants/task008.py.
- Verify primary = combined_paper_safe_variant.
- Verify shadow = A_roll12_share20_exclude.
- Verify daily outputs are implementable.
- Verify W-1~W-6 / S-1~S-6 gates can be computed.
- Verify review_006b_trigger_ready logic is implementable.
- Verify tests can be written with mock/stub only.
- Return readiness_status:
  - READY_TO_IMPLEMENT
  - BLOCKED_BY_SPEC
  - NEED_CLARIFICATION
- If READY_TO_IMPLEMENT, provide implementation plan only.
- Update COMMAND_LOG.md.

Do not:
- Do not implement TASK-009 yet.
- Do not connect to Bybit.
- Do not ask Rick for API keys.
- Do not write API keys to files/logs.
- Do not submit or cancel orders.
- Do not connect to private trading endpoints.
- Do not start 30-day forward clock.
- Do not approve paper execution.
- Do not approve live trading.
- Do not modify strategy code.
- Do not mark TASK-009 DONE.


## task-009-implementation-plan

Read:
1. docs/research/codex_workorders/TASK-009_forward_record_runner.md
2. docs/research/commands/COMMAND_LOG.md
3. apps/paper_trading/config.py
4. apps/paper_trading/overlay.py
5. apps/paper_trading/recorder.py
6. apps/paper_trading/validator.py
7. apps/monitor/
8. src/variants/task008.py
9. docs/research/manual_ops/30_day_forward_record_plan.md
10. docs/research/manual_ops/30_day_forward_start_checklist.md
11. docs/research/manual_ops/VPS_DEPLOYMENT_CHECKLIST.md

Do:
- Prepare TASK-009 implementation plan only.
- Do not implement yet.
- Explain apps/forward_record/ module structure.
- Explain scripts/run_forward_record.py CLI.
- Explain how primary combined_paper_safe_variant will be recorded.
- Explain how shadow-track A_roll12_share20_exclude will be recorded.
- Explain TASK-008 adapter/wrapper design:
  - do not require apply_alpha_contribution_cap()
  - use existing VariantSpec / build_monthly_variant_weights or equivalent available TASK-008 machinery
  - do not modify src/variants/task008.py unless strictly necessary; prefer adapter inside apps/forward_record/
- Explain market data layer:
  - local parquet/cache fallback by default
  - Bybit read-only GET abstraction only
  - no private trading endpoint
  - no order endpoint
- Explain API key handling:
  - environment variables only if ever used
  - never written to outputs/logs/packets
- Explain output directories:
  - primary outputs
  - shadow outputs
  - metrics
  - risk events
  - logs
  - REVIEW-009 packet/numbers
- Explain W-1~W-6 and S-1~S-6 gate implementation.
- Explain review_006b_trigger_ready logic.
- Explain tests:
  - schema tests
  - gate tests
  - safety tests
  - mock Bybit read-only GET
  - no order endpoint scan
  - primary/shadow separation
  - FORBIDDEN flags embedded
- Explain reproducibility hash.
- Update COMMAND_LOG.md.

Required planned modules:
- apps/forward_record/__init__.py
- apps/forward_record/config.py
- apps/forward_record/market_data.py
- apps/forward_record/primary.py
- apps/forward_record/shadow.py
- apps/forward_record/pnl.py
- apps/forward_record/gates.py
- apps/forward_record/report.py
- apps/forward_record/safety.py
- scripts/run_forward_record.py
- tests/forward_record/

Do not:
- Do not implement TASK-009 yet.
- Do not connect to Bybit.
- Do not ask Rick for API keys.
- Do not write API keys to files/logs.
- Do not submit or cancel orders.
- Do not connect to private trading endpoints.
- Do not start 30-day forward clock.
- Do not approve paper execution.
- Do not approve live trading.
- Do not modify strategy code.
- Do not mark TASK-009 DONE.

Expected output:
- TASK-009 implementation plan in reply.
- COMMAND_LOG.md updated.


## task-009-implement

Read:
1. docs/research/codex_workorders/TASK-009_forward_record_runner.md
2. docs/research/commands/COMMAND_LOG.md
3. apps/paper_trading/config.py
4. apps/paper_trading/overlay.py
5. apps/paper_trading/recorder.py
6. apps/paper_trading/validator.py
7. apps/monitor/
8. src/variants/task008.py
9. docs/research/manual_ops/30_day_forward_record_plan.md
10. docs/research/manual_ops/30_day_forward_start_checklist.md
11. docs/research/manual_ops/VPS_DEPLOYMENT_CHECKLIST.md

Do:
- Implement TASK-009 forward record runner.
- Add isolated modules:
  - apps/forward_record/__init__.py
  - apps/forward_record/config.py
  - apps/forward_record/market_data.py
  - apps/forward_record/primary.py
  - apps/forward_record/shadow.py
  - apps/forward_record/pnl.py
  - apps/forward_record/gates.py
  - apps/forward_record/report.py
  - apps/forward_record/safety.py
- Add CLI:
  - scripts/run_forward_record.py
- Add tests:
  - tests/forward_record/
- Primary track:
  - Use combined_paper_safe_variant.
  - Reuse apps.paper_trading overlay/config/recorder/validator where safe.
- Shadow track:
  - Use A_roll12_share20_exclude.
  - Build adapter in apps/forward_record/shadow.py.
  - Use existing TASK-008 machinery such as VariantSpec / VARIANT_SPECS / build_monthly_variant_weights or equivalent.
  - Do not require apply_alpha_contribution_cap().
  - Do not modify src/variants/task008.py unless impossible; prefer adapter.
- Market data:
  - Default to local parquet/cache mode.
  - Add read-only GET abstraction only.
  - Do not connect to Bybit during implementation validation.
  - Tests must use mock/stub only.
- Outputs:
  - outputs/forward_record/prev3y_crypto/<YYYYMMDD>/primary/
  - outputs/forward_record/prev3y_crypto/<YYYYMMDD>/shadow/
  - outputs/forward_record/prev3y_crypto/<YYYYMMDD>/metrics/
  - outputs/forward_record/prev3y_crypto/<YYYYMMDD>/risk_events/
  - outputs/logs/prev3y_crypto/<YYYYMMDD>_forward_record.log
  - docs/research/review_packets/REVIEW-009_PACKET.md
  - docs/research/review_packets/REVIEW-009_NUMBERS.json
- Every output must include:
  - paper_execution_status: FORBIDDEN
  - live_trading_status: FORBIDDEN
- Implement W-1~W-6 warning gates.
- Implement S-1~S-6 stop gates.
- Implement review_006b_trigger_ready logic.
- Implement reproducibility hash.
- Run validation/tests:
  - python -m unittest tests.forward_record
  - python -m py_compile apps/forward_record/*.py scripts/run_forward_record.py
  - python scripts/run_forward_record.py --date 20260517 --dry-run --shadow-track
- Update CODEX_TASK_QUEUE.md to REVIEW when complete.
- Update COMMAND_LOG.md.

Do not:
- Do not connect to Bybit.
- Do not ask Rick for API keys.
- Do not write API keys to files/logs/outputs.
- Do not submit orders.
- Do not cancel orders.
- Do not connect to private trading endpoints.
- Do not start 30-day forward clock.
- Do not approve paper execution.
- Do not approve live trading.
- Do not modify strategy code.
- Do not modify src/signals/prev3y_momentum.py.
- Do not rerun official baseline / cost stress / attribution.
- Do not mark TASK-009 DONE.


## task-009b-readiness

Read:
1. docs/research/codex_workorders/TASK-009b_forward_monitor_alerting.md
2. docs/research/commands/COMMAND_LOG.md
3. apps/forward_record/
4. apps/monitor/
5. scripts/run_forward_record.py
6. docs/research/review_packets/REVIEW-009_PACKET.md
7. docs/research/review_packets/REVIEW-009_NUMBERS.json

Do:
- Perform TASK-009b readiness check only.
- Verify scope is forward record monitoring / alerting only.
- Verify all alert conditions are computable:
  - A-1 runner missing row for 2 consecutive days
  - A-2 stop gate hit
  - A-3 warning gate persists N days
  - A-4 primary/shadow alpha gap > threshold
  - A-5 data source read/parse failure
  - A-6 review_006b_trigger_ready=true
  - A-7 paper/live forbidden status violation
- Verify TASK-005 / TASK-005a Discord channel can be reused safely.
- Verify dry_run defaults true.
- Verify real alert requires explicit --live-alerts plus VPS config.
- Verify tests T-1~T-15 can be implemented using mocks only.
- Verify no Bybit connection is required.
- Verify no API keys are required.
- Verify no order/private endpoint is involved.
- Verify 30-day clock is not started.
- Return readiness_status:
  - READY_TO_IMPLEMENT
  - BLOCKED_BY_SPEC
  - NEED_CLARIFICATION
- If READY_TO_IMPLEMENT, provide implementation plan only.
- Update COMMAND_LOG.md.

Do not:
- Do not implement TASK-009b yet.
- Do not connect to Bybit.
- Do not ask for API keys.
- Do not send real Discord alerts.
- Do not start 30-day forward clock.
- Do not approve paper execution.
- Do not approve live trading.
- Do not modify strategy code.
- Do not mark TASK-009b DONE.


## task-009b-implementation-plan

Read:
1. docs/research/codex_workorders/TASK-009b_forward_monitor_alerting.md
2. docs/research/commands/COMMAND_LOG.md
3. docs/research/review_packets/REVIEW-009_PACKET.md
4. docs/research/review_packets/REVIEW-009_NUMBERS.json
5. apps/forward_record/
6. apps/monitor/
7. scripts/run_forward_record.py
8. configs/monitor.yaml

Do:
- Prepare TASK-009b implementation plan only.
- Do not implement yet.
- Explain how implementation will use actual TASK-009 output paths from REVIEW-009_NUMBERS.json, not only example paths from the workorder.
- Explain alert condition modules:
  - apps/forward_record/alert_conditions.py
  - apps/forward_record/alerting.py
- Explain A-1~A-7 implementation:
  - A-1 missing row for 2 consecutive days
  - A-2 stop gate hit
  - A-3 warning gate persists N days
  - A-4 primary/shadow alpha gap threshold
  - A-5 data source read/parse failure
  - A-6 review_006b_trigger_ready=true
  - A-7 paper/live FORBIDDEN status violation
- Explain alert output:
  - outputs/forward_record/alerts/<YYYYMMDD>_alert_log.json
- Explain Discord integration:
  - reuse apps.monitor.channels.discord.send_discord_alerts()
  - default dry_run=true
  - real Discord POST requires both --live-alerts and configs/monitor.yaml channel dry_run=false
- Explain CLI change:
  - scripts/run_forward_record.py adds --live-alerts
  - normal run remains dry-run alert mode
- Explain tests:
  - tests/forward_record/test_alerting.py
  - T-1~T-15 mock-only coverage
- Explain safety gates:
  - no Bybit connection
  - no API key access
  - no order/private endpoint
  - no clock mutation
  - no paper/live approval
- Explain review packet / numbers updates.
- Update COMMAND_LOG.md.

Do not:
- Do not implement TASK-009b yet.
- Do not connect to Bybit.
- Do not ask for API keys.
- Do not send real Discord alerts.
- Do not start 30-day forward clock.
- Do not approve paper execution.
- Do not approve live trading.
- Do not modify strategy code.
- Do not mark TASK-009b DONE.


## task-009b-implement

Read:
1. docs/research/codex_workorders/TASK-009b_forward_monitor_alerting.md
2. docs/research/commands/COMMAND_LOG.md
3. docs/research/review_packets/REVIEW-009_PACKET.md
4. docs/research/review_packets/REVIEW-009_NUMBERS.json
5. apps/forward_record/
6. apps/monitor/
7. scripts/run_forward_record.py
8. configs/monitor.yaml

Do:
- Implement TASK-009b forward monitor alerting.
- Add:
  - apps/forward_record/alert_conditions.py
  - apps/forward_record/alerting.py
  - tests/forward_record/test_alerting.py
- Implement A-1~A-7 alert conditions as pure functions:
  - A-1 missing row for 2 consecutive days
  - A-2 active stop gate hit
  - A-3 warning gate streak N days, default N=3
  - A-4 primary/shadow mean abs weight gap > 0.05
  - A-5 data source read/parse failure
  - A-6 review_006b_trigger_ready=true with de-dup
  - A-7 paper/live safety field violation
- Read actual TASK-009 output paths from REVIEW-009_NUMBERS.json.
- Do not depend on example paths in the workorder.
- Add alert log output:
  - outputs/forward_record/alerts/<YYYYMMDD>_alert_log.json
- Reuse apps.monitor.channels.discord.send_discord_alerts().
- Update scripts/run_forward_record.py with --live-alerts.
- Real Discord POST requires both:
  - --live-alerts
  - configs/monitor.yaml discord dry_run=false
- Normal run must remain alert dry-run.
- --dry-run must force alert dry-run.
- Add tests T-1~T-15 using mocks only.
- Update REVIEW-009_PACKET.md / REVIEW-009_NUMBERS.json or create REVIEW-009b packet/numbers if the repo convention prefers separate REVIEW-009b artifacts.
- Update CODEX_TASK_QUEUE.md to REVIEW when complete.
- Update COMMAND_LOG.md.

Validation:
- python -m unittest tests.forward_record -v
- python -m unittest tests.monitor.test_channels -v
- python -m py_compile apps/forward_record/*.py scripts/run_forward_record.py
- python scripts/run_forward_record.py --date 20260517 --dry-run --shadow-track
- Confirm alert log written.
- Confirm no real Discord POST.
- Confirm no Bybit connection.
- Confirm no API key access.
- Confirm no order/private endpoint.
- Confirm clock remains NOT_STARTED.
- Confirm paper/live remain FORBIDDEN.

Do not:
- Do not connect to Bybit.
- Do not ask for API keys.
- Do not send real Discord alerts.
- Do not use --live-alerts during validation.
- Do not set discord dry_run=false.
- Do not start 30-day forward clock.
- Do not approve paper execution.
- Do not approve live trading.
- Do not modify strategy code.
- Do not mark TASK-009b DONE.


## task-009d-readiness

Read:
1. docs/research/codex_workorders/TASK-009d_alert_e2e_drill.md
2. docs/research/commands/COMMAND_LOG.md
3. apps/forward_record/alert_conditions.py
4. apps/forward_record/alerting.py
5. tests/forward_record/test_alerting.py
6. docs/research/review_packets/REVIEW-009b_NUMBERS.json
7. outputs/forward_record/alerts/20260517_alert_log.json

Do:
- Perform TASK-009d readiness check only.
- Verify scope is alert E2E drill only.
- Verify S-A1~S-A7 positive scenarios can be generated.
- Verify S-A1b/A3b/A4b/A5b/A6b negative scenarios can be generated.
- Verify redaction validation can cover webhook/api_key/api_secret/token sensitive patterns.
- Verify dedupe validation for A-6 can be implemented.
- Verify A-2 daily notification no-dedupe behavior can be implemented.
- Verify Discord template checks are implementable:
  - non-empty
  - condition ID
  - date
  - action guidance
  - severity mapping
  - no placeholders
- Verify force_dry_run=True can be enforced.
- Verify live_alerts=True is forbidden.
- Verify ChannelResult.status == SENT can be treated as drill failure.
- Verify T-1~T-18 can be implemented with mock/temp files only.
- Return readiness_status:
  - READY_TO_IMPLEMENT
  - BLOCKED_BY_SPEC
  - NEED_CLARIFICATION
- If READY_TO_IMPLEMENT, provide implementation plan only.
- Update COMMAND_LOG.md.

Do not:
- Do not implement TASK-009d yet.
- Do not send real Discord alert.
- Do not use --live-alerts.
- Do not set discord dry_run=false.
- Do not connect to Bybit.
- Do not ask for API keys.
- Do not start 30-day forward clock.
- Do not approve paper execution.
- Do not approve live trading.
- Do not mark TASK-009d DONE.


## task-009d-implementation-plan

Read:
1. docs/research/codex_workorders/TASK-009d_alert_e2e_drill.md
2. docs/research/commands/COMMAND_LOG.md
3. apps/forward_record/alert_conditions.py
4. apps/forward_record/alerting.py
5. tests/forward_record/test_alerting.py
6. docs/research/review_packets/REVIEW-009b_NUMBERS.json
7. outputs/forward_record/alerts/20260517_alert_log.json

Do:
- Prepare TASK-009d implementation plan only.
- Do not implement yet.
- Explicitly state that despite any old CODEX_TASK_QUEUE.md wording, TASK-009d is dry-run/mock only.
- Explain scripts/drill_forward_alerts.py design.
- Explain tempdir fixture design for S-A1~S-A7 positive scenarios.
- Explain negative scenarios:
  - S-A1b
  - S-A3b
  - S-A4b
  - S-A5b
  - S-A6b
- Explain redaction validation:
  - webhook
  - api_key
  - api_secret
  - token
  - Bearer
  - Discord webhook URL patterns
- Explain dedupe validation:
  - A-6 dedupes next day
  - A-2 does not dedupe daily stop-gate alert
- Explain Discord template validation:
  - non-empty
  - condition ID
  - date
  - action guidance
  - severity mapping
  - no placeholders
- Explain force_dry_run=True and live_alerts=False enforcement.
- Explain ChannelResult.status == SENT fail gate.
- Explain output:
  - outputs/forward_record/drill/<YYYYMMDD>_drill_report.json
  - docs/research/review_packets/REVIEW-009d_PACKET.md
  - docs/research/review_packets/REVIEW-009d_NUMBERS.json
- Explain tests:
  - tests/forward_record/test_alert_e2e_drill.py
  - T-1~T-18
- Explain safety gates:
  - no real Discord POST
  - no --live-alerts
  - no Bybit
  - no API key
  - no clock mutation
  - paper/live FORBIDDEN
- Update COMMAND_LOG.md.

Do not:
- Do not implement TASK-009d yet.
- Do not send real Discord alert.
- Do not use --live-alerts.
- Do not set discord dry_run=false.
- Do not connect to Bybit.
- Do not ask for API keys.
- Do not start 30-day forward clock.
- Do not approve paper execution.
- Do not approve live trading.
- Do not mark TASK-009d DONE.


## task-009d-implement

Read:
1. docs/research/codex_workorders/TASK-009d_alert_e2e_drill.md
2. docs/research/commands/COMMAND_LOG.md
3. apps/forward_record/alert_conditions.py
4. apps/forward_record/alerting.py
5. tests/forward_record/test_alerting.py
6. docs/research/review_packets/REVIEW-009b_NUMBERS.json
7. outputs/forward_record/alerts/20260517_alert_log.json

Do:
- Implement TASK-009d alert E2E dry-run drill.
- Add:
  - scripts/drill_forward_alerts.py
  - tests/forward_record/test_alert_e2e_drill.py
  - docs/research/review_packets/REVIEW-009d_PACKET.md
  - docs/research/review_packets/REVIEW-009d_NUMBERS.json
- Produce:
  - outputs/forward_record/drill/<YYYYMMDD>_drill_report.json
- Use tempdir fixtures only.
- Do not read real webhook or secret files.
- Force all alert calls:
  - force_dry_run=True
  - live_alerts=False
- Treat any ChannelResult.status == "SENT" as FAIL.
- Implement positive scenarios:
  - S-A1
  - S-A2
  - S-A3
  - S-A4
  - S-A5
  - S-A6
  - S-A7
- Implement negative scenarios:
  - S-A1b
  - S-A3b
  - S-A4b
  - S-A5b
  - S-A6b
- For every scenario, record:
  - triggered
  - expected_triggered
  - pass/fail
  - severity
  - condition_id
  - message_preview
  - action guidance present
  - redaction_pass
  - template_pass
- Redaction scan must fail if message/report contains:
  - webhook
  - MONITOR_DISCORD_WEBHOOK_URL
  - api_key
  - api_secret
  - BYBIT_API_KEY
  - BYBIT_API_SECRET
  - token
  - Bearer 
  - https://discord.com/api/
- Dedupe validation:
  - A-6 day1 triggers
  - A-6 day2 is suppressed when previous alert log contains A-6
  - A-2 stop gate does not dedupe and can trigger daily
- Discord template validation:
  - message non-empty
  - condition ID present
  - date present
  - action guidance present
  - severity mapping correct
  - no "{}" placeholder
  - no "None" placeholder
  - A-6 contains no approval / order / execution language
- Run validations:
  - python -m unittest tests.forward_record.test_alert_e2e_drill -v
  - python -m unittest tests.forward_record -v
  - python -m py_compile scripts/drill_forward_alerts.py
  - python scripts/drill_forward_alerts.py --date 20260517
- Update CODEX_TASK_QUEUE.md to REVIEW when complete.
- Update COMMAND_LOG.md.

Do not:
- Do not send real Discord alert.
- Do not use --live-alerts.
- Do not set discord dry_run=false.
- Do not connect to Bybit.
- Do not ask for API keys.
- Do not read real API keys or webhook.
- Do not start 30-day forward clock.
- Do not approve paper execution.
- Do not approve live trading.
- Do not modify strategy code.
- Do not mark TASK-009d DONE.