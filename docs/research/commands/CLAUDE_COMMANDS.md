# Claude Commands

Claude must read `docs/research/commands/NEXT_ACTION.md` before starting any project task.

## Execution Rules

- If `NEXT_ACTION.md` status is not `READY`, Claude must not execute tasks on its own.
- Claude should only perform the task named in `NEXT_ACTION.md` unless Rick gives a newer direct instruction.
- Final reviews use Opus.
- Queue updates, summaries, readiness checks, and draft reviews use Sonnet unless Rick specifies otherwise.
- Claude must not mark tasks `DONE` without an explicit review verdict that allows it.
- Claude must preserve the red lines listed in the relevant task workorder.

## Review Routing

- Major final review: Opus.
- Readiness check: Sonnet.
- Queue/status maintenance: Sonnet.
- Context packet or summary drafting: Sonnet.

## Required Inputs

For each task, read in this order:

1. `docs/research/commands/NEXT_ACTION.md`
2. Relevant task queue entry in `docs/research/CODEX_TASK_QUEUE.md`
3. Relevant review queue entry in `docs/research/CLAUDE_REVIEW_QUEUE.md`
4. Relevant workorder or context packet
5. Canonical task inputs listed by the workorder

## review-003-draft

Use Sonnet.

Read:
1. docs/research/codex_workorders/TASK-003_baseline_attribution.md
2. outputs/attribution/prev3y_crypto/20260515_attribution_summary.json
3. outputs/attribution/prev3y_crypto/20260515_attribution_by_symbol.csv
4. outputs/attribution/prev3y_crypto/20260515_attribution_by_year.csv
5. outputs/attribution/prev3y_crypto/20260515_attribution_by_month.csv
6. outputs/attribution/prev3y_crypto/20260515_attribution_by_side.csv
7. outputs/attribution/prev3y_crypto/20260515_attribution_by_funding_gap.csv
8. outputs/attribution/prev3y_crypto/20260515_attribution_by_interval.csv
9. outputs/attribution/prev3y_crypto/20260515_attribution_by_cost_type.csv
10. outputs/attribution/prev3y_crypto/20260515_attribution_top_contributors.csv
11. outputs/attribution/prev3y_crypto/20260515_attribution_drawdown.csv
12. outputs/logs/prev3y_crypto/20260515_attribution.log

Do:
- Perform REVIEW-003 draft only.
- Check all official outputs exist.
- Check schema and reconciliation:
  - gross active daily max diff vs run008 <= 1e-6
  - net active daily max diff vs TASK-002 realistic_combo <= 1e-6
- Check fail gates:
  - gross mismatch
  - net mismatch
  - missing outputs
  - schema mismatch
- Check warning gates:
  - top 5 symbols > 60% net alpha
  - single symbol > 25% net alpha
  - funding gap 7 symbols > 20% net alpha
  - single year > 70% net alpha
  - short side net alpha negative and abs(short) > 50% combined gross alpha
  - gross vs net rank divergence > 10
- Interpret attribution:
  - alpha concentration by symbol
  - alpha concentration by year/month
  - long vs short contribution
  - funding-gap contribution
  - interval group contribution
  - cost type contribution
  - drawdown contributor
- Identify whether Opus final review is required.

Important known results to verify:
- Gross active daily max diff: 1.0495e-16
- Net active daily max diff: 2.0470e-16
- Net alpha total: 28.53%
- Short net: +33.65%
- Long net: -5.10%
- 2025 net: +25.46%
- 2026 net: -1.20%
- Warning: single_year_concentration, 2025 = 85.62% of positive year net alpha
- Warning: gross_net_rank_divergence, max rank change = 13
- Top 5 concentration PASS: 28.92%
- Single symbol concentration PASS: DOT 7.70%
- Funding gap concentration PASS: 3.36%

Output:
Create:
docs/research/review_drafts/REVIEW-003_DRAFT_BY_SONNET.md

Use this format:

## REVIEW-003 Draft Verdict
PASS_CANDIDATE / CONDITIONAL_PASS_CANDIDATE / FAIL_CANDIDATE

## Blocking Issues
None if no blocking issue.

## Warning Gates
List triggered and non-triggered gates.

## Attribution Interpretation
Explain what the attribution means.

## Issues Needing Opus Decision
List decisions requiring Opus, especially:
- Whether short-side dominance changes strategy interpretation.
- Whether long-side negative contribution requires follow-up task.
- Whether 2025 concentration prevents paper trading planning.
- Whether TASK-003 can be DONE.
- Whether TASK-004 / TASK-005 / TASK-006 remain unlocked.

## Suggested Opus Prompt
Write a prompt Rick can paste to Opus for REVIEW-003 final decision.

Do not:
- Do not mark TASK-003 DONE.
- Do not modify strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not modify official outputs.

## review-003-final

Use Opus.

Read:
1. docs/research/review_drafts/REVIEW-003_DRAFT_BY_SONNET.md
2. outputs/attribution/prev3y_crypto/20260515_attribution_summary.json
3. outputs/attribution/prev3y_crypto/20260515_attribution_by_symbol.csv
4. outputs/attribution/prev3y_crypto/20260515_attribution_by_side.csv
5. outputs/attribution/prev3y_crypto/20260515_attribution_by_year.csv
6. outputs/attribution/prev3y_crypto/20260515_attribution_top_contributors.csv
7. outputs/attribution/prev3y_crypto/20260515_attribution_by_cost_type.csv
8. outputs/logs/prev3y_crypto/20260515_attribution.log

Purpose:
Execute REVIEW-003 final decision.

Key issues from Sonnet draft:
1. Concentration gate formula conflict:
   - Codex used denominator = sum_abs_net, top5 = 28.9%, not triggered.
   - Workorder-style interpretation uses denominator = net_alpha_total, top5 = 95.6%, triggered.
   - Decide correct interpretation and impact on TASK-003 verdict / paper trading.

2. Long side negative alpha:
   - Short net alpha = +33.65%.
   - Long net alpha = -5.10%.
   - Short side contributes 117.9% of net alpha.
   - Decide whether this is blocking, caveat, or follow-up task.

Triggered warning gates:
- single_year_concentration: 2025 contributes about 85–89% of net alpha.
- gross_net_rank_divergence: max rank change = 13.

Do:
- Decide REVIEW-003 verdict:
  PASS / CONDITIONAL_PASS / FAIL
- Decide whether TASK-003 can be marked DONE.
- Decide whether TASK-004 dashboard remains unlocked.
- Decide whether TASK-005 VPS / monitor remains unlocked.
- Decide whether TASK-006 paper trading plan remains unlocked.
- Decide whether paper trading planning needs new restrictions.
- Decide whether live trading remains forbidden.
- Define required follow-up tasks if needed.

Output format:

## Verdict
PASS / CONDITIONAL_PASS / FAIL

## Strategy Interpretation
Explain what attribution reveals about alpha source.

## Final Decision On Blocking Issues
### Concentration Gate Formula
State which denominator should be used and why.

### Long Side Negative Alpha
State whether it is blocking, caveat, or follow-up.

## Key Numbers
Include:
- net alpha total
- top 5 concentration under selected formula
- short net alpha
- long net alpha
- 2025 concentration
- gross/net rank divergence

## Blocking Issues
None if none.

## Required Follow-up Tasks
List any new tasks, for example:
- TASK-003b concentration risk audit
- TASK-003c long vs short sleeve ablation
- TASK-006 paper trading constraints update

## Downstream Decisions
- TASK-003 state
- TASK-004 state
- TASK-005 state
- TASK-006 state
- paper trading planning
- live trading

## Queue Updates
List required queue changes.

Append result to:
docs/research/CLAUDE_REVIEW_LOG.md

Update:
docs/research/CODEX_TASK_QUEUE.md
docs/research/CLAUDE_REVIEW_QUEUE.md

Do not:
- Do not modify strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not modify official outputs.
- Do not approve live trading.

## task-007-workorder

Use Sonnet.

Purpose:
Create TASK-007 Long-side Variant Study workorder.

Background:
REVIEW-003 final decision gave TASK-003 a CONDITIONAL_PASS.
Attribution revealed:
- Short net alpha = +33.65%
- Long net alpha = -5.10%
- Short side contributes more than 100% of net alpha
- Top 5 symbols contribute 95.56% of net alpha under workorder formula
- DOT alone contributes 25.45% of net alpha
- Paper trading planning requires:
  - 5% symbol size cap
  - 50% long-side allocation cap
  - high-funding-cost symbol filter

Task:
Create:
docs/research/codex_workorders/TASK-007_long_side_variant_study.md

The workorder must include:
1. 任務一句話
2. 任務目的
3. 為什麼重要
4. do / don't 範圍
5. input files
6. output files
7. variants to test
8. metrics
9. warning / fail gates
10. 禁止修改範圍
11. 完成後回報格式
12. NOTE 區

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

Required analysis:
- active Sharpe
- IR vs equal-weight
- IR vs BTC
- max DD
- net alpha
- long contribution
- short contribution
- top 5 concentration
- single symbol concentration
- turnover impact
- fee / slippage / funding impact

Important rules:
- Do not modify strategy code.
- Do not rerun baseline unless the workorder explicitly tells Codex how to create variant overlays.
- Prefer overlay / post-process variant study first.
- Do not touch run008 or TASK-002/TASK-003 official outputs.
- Do not approve paper trading.
- Do not approve live trading.
- TASK-007 is research only.

Output:
Write the workorder file.
Update COMMAND_LOG.md.
Do not execute TASK-007 implementation.
Do not mark TASK-007 DONE.

## review-007-draft

Use Sonnet.

Read:
1. docs/research/review_packets/REVIEW-007_PACKET.md
2. docs/research/review_packets/REVIEW-007_NUMBERS.json
3. outputs/variants/prev3y_crypto/20260515_task007_variant_summary.json
4. outputs/variants/prev3y_crypto/20260515_task007_variant_summary.csv
5. outputs/variants/prev3y_crypto/20260515_task007_variant_concentration.csv
6. outputs/variants/prev3y_crypto/20260515_task007_variant_cost_breakdown.csv
7. outputs/logs/prev3y_crypto/20260515_task007_variant_study.log
8. docs/research/codex_workorders/TASK-007_long_side_variant_study.md

Do:
- Perform REVIEW-007 draft only.
- Check official outputs exist.
- Check baseline reconciliation:
  - baseline_current_long_short vs TASK-002 realistic_combo max diff <= 1e-6
- Check fail gates.
- Check warning gates.
- Compare all variants.
- Identify whether any variant improves baseline without introducing unacceptable risk.
- Pay special attention to:
  - short_only_unscaled
  - short_only_rescaled
  - long_only_unscaled
  - long_only_rescaled
  - long_half_weight
  - long_with_50pct_cap
  - top5_symbol_cap_5pct
  - DOT_capped
  - no_DOT
  - high_funding_cost_filter
  - combined_paper_safe_variant
- Decide whether Opus final review is required.

Known Codex summary to verify:
- status = REVIEW_READY
- baseline reconciliation max diff = 2.05e-16
- fail gates all false
- reproducibility hash = 824ff334e30810aeeaef8a06319a9ac8563b61f903835c89ae6cfbd9e140066f
- best Sharpe overlay = high_funding_cost_filter
- high_funding_cost_filter Sharpe = 0.9586
- high_funding_cost_filter IR_vs_eqw = 0.7282
- high_funding_cost_filter max DD = -20.27%
- high_funding_cost_filter net alpha = 31.27%

Output:
Create:
docs/research/review_drafts/REVIEW-007_DRAFT_BY_SONNET.md

Use this format:

## REVIEW-007 Draft Verdict
PASS_CANDIDATE / CONDITIONAL_PASS_CANDIDATE / FAIL_CANDIDATE

## Blocking Issues
None if no blocking issue.

## Warning Gates
List triggered and non-triggered gates.

## Variant Comparison
Summarize key variants and what they imply.

## Interpretation
Explain:
- Whether long-side modifications helped.
- Whether short-only variants are better or riskier.
- Whether high_funding_cost_filter is genuinely promising.
- Whether combined_paper_safe_variant is viable.

## Issues Needing Opus Decision
List decisions requiring Opus, especially:
- Whether TASK-007 can be DONE.
- Whether high_funding_cost_filter should become preferred paper-planning variant.
- Whether long-side cap is enough or long side needs separate ablation.
- Whether paper trading plan can proceed with constraints.

## Suggested Opus Prompt
Write a prompt Rick can paste to Opus for REVIEW-007 final decision.

Do not:
- Do not mark TASK-007 DONE.
- Do not modify strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not rerun variant study.
- Do not modify official outputs.
- Do not approve paper trading execution.
- Do not approve live trading.

## review-007-final

Use Opus.

Read:
1. docs/research/review_drafts/REVIEW-007_DRAFT_BY_SONNET.md
2. docs/research/review_packets/REVIEW-007_PACKET.md
3. docs/research/review_packets/REVIEW-007_NUMBERS.json
4. outputs/variants/prev3y_crypto/20260515_task007_variant_summary.json
5. outputs/variants/prev3y_crypto/20260515_task007_variant_summary.csv
6. outputs/variants/prev3y_crypto/20260515_task007_variant_concentration.csv
7. outputs/logs/prev3y_crypto/20260515_task007_variant_study.log

Purpose:
Execute REVIEW-007 final decision.

Key Sonnet findings to verify:
1. `high_funding_cost_filter` may be Pareto-dominant:
   - Sharpe = 0.9586
   - Alpha retention = 109.6%
   - Long side loss improves from -5.01% to -2.29%
   - Funding cost nearly zero
   - Top5 concentration improves to 87.22%
   - Single symbol concentration improves to 23.23%

2. Short-only appears not viable:
   - Sharpe around 0.4045
   - Max DD worsens to about -49.18%

3. Long-only confirms long-side weakness:
   - Problem may be high funding specific symbols such as BTC / ETH / LINK.

4. Combined paper-safe variant:
   - Long net turns positive around +4.21%
   - Single concentration improves to around 19.73%

5. Concentration remains unresolved:
   - Minimum top5 concentration still around 87.22%.

Blocking issues from Sonnet draft:
- B-1: Variant D not delivered according to spec.
- B-2: Variant C threshold deviates by about 3x.
- B-3: Workorder warning gate system not implemented.
- B-4: Baseline Sharpe inconsistency, 0.8918 vs 0.9267.

Do:
- Decide REVIEW-007 verdict:
  PASS / CONDITIONAL_PASS / FAIL
- Resolve B-1 to B-4.
- Decide whether TASK-007 can be marked DONE.
- Decide whether high_funding_cost_filter becomes preferred research variant.
- Decide whether combined_paper_safe_variant is viable for paper trading planning.
- Decide whether Codex must produce a patch / addendum before TASK-007 DONE.
- Decide whether TASK-006 paper trading plan may proceed.
- Define mandatory paper trading constraints if planning is allowed.
- Decide whether live trading remains forbidden.

Output format:

## Verdict
PASS / CONDITIONAL_PASS / FAIL

## Final Decision On Blocking Issues
### B-1 Variant D Delivery
### B-2 Variant C Threshold Deviation
### B-3 Warning Gate System
### B-4 Baseline Sharpe Inconsistency

## Variant Decision
- high_funding_cost_filter:
- combined_paper_safe_variant:
- short_only:
- long_only:

## Key Numbers
Include:
- baseline_current_long_short
- high_funding_cost_filter
- combined_paper_safe_variant
- short_only_rescaled
- long_only_rescaled

## Strategy Interpretation
Explain what TASK-007 means for the strategy.

## Required Follow-up Tasks
List any required addendum or patch tasks.

## Downstream Decisions
- TASK-007 state
- TASK-006 paper trading plan
- TASK-004 dashboard
- TASK-005 VPS monitor
- live trading

## Queue Updates
List required queue changes.

Append result to:
docs/research/CLAUDE_REVIEW_LOG.md

Update:
docs/research/CODEX_TASK_QUEUE.md
docs/research/CLAUDE_REVIEW_QUEUE.md
docs/research/commands/COMMAND_LOG.md

Do not:
- Do not modify strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not rerun variant study.
- Do not modify official outputs.
- Do not approve paper trading execution.
- Do not approve live trading.

## task-006-workorder

Use Sonnet.

Purpose:
Create TASK-006 Paper Trading Plan workorder.

Background:
REVIEW-007 final decision gave TASK-007 a CONDITIONAL_PASS and marked it DONE.
Paper trading planning is now allowed, but paper trading execution is not allowed.
Live trading remains forbidden.

Primary paper planning variant:
- combined_paper_safe_variant

Secondary comparison variant:
- high_funding_cost_filter

Mandatory caveats:
1. Paper trading execution is not approved.
2. Live trading is forbidden.
3. TASK-007b must be completed before any paper execution.
4. At least 30 days forward sample is required before any execution decision.
5. Another Opus review is required before execution.
6. combined_paper_safe_variant is primary because it makes long_net positive and keeps single_conc below 25%.
7. high_funding_cost_filter is secondary because it has best Sharpe but still has long_net negative.

Create:
docs/research/codex_workorders/TASK-006_paper_trading_plan.md

The workorder must include:
1. 任務一句話
2. 任務目的
3. 為什麼重要
4. Scope: planning only, no execution
5. Inputs
6. Outputs
7. Paper trading design
8. Risk controls
9. Mandatory constraints
10. Monitoring requirements
11. Stop conditions
12. Review gates
13. Forbidden actions
14. Completion report format
15. NOTE section

Required paper trading plan content:
- primary variant: combined_paper_safe_variant
- secondary tracking variant: high_funding_cost_filter
- 5% symbol size cap
- 50% long-side allocation cap
- high-funding-cost symbol filter
- no live trading
- no real capital
- no automated execution yet
- forward sample minimum: 30 days
- daily monitoring checklist
- weekly review checklist
- drawdown stop rule
- data failure stop rule
- exchange/API failure stop rule
- funding anomaly warning
- symbol concentration warning
- long-side contribution tracking
- short-side contribution tracking
- comparison against run008 baseline and TASK-007 variants

Must include gating:
- TASK-007b must be DONE before paper execution.
- TASK-006 only produces a plan, not code that trades.
- Paper execution requires a separate future task and Opus review.
- Live trading remains forbidden.

Do not:
- Do not implement paper trading.
- Do not write exchange execution code.
- Do not modify strategy code.
- Do not modify run008 / TASK-002 / TASK-003 / TASK-007 outputs.
- Do not start VPS monitor.
- Do not approve live trading.
- Do not mark TASK-006 DONE unless only the workorder is created and reviewed.

## review-006-draft

Use Sonnet.

Read:
1. docs/research/codex_workorders/TASK-006_paper_trading_plan.md
2. docs/research/review_packets/REVIEW-006_PACKET.md
3. docs/research/review_packets/REVIEW-006_NUMBERS.json
4. outputs/paper_trading/prev3y_crypto/20260516_target_positions.json
5. outputs/paper_trading/prev3y_crypto/20260516_simulated_fills.csv
6. outputs/paper_trading/prev3y_crypto/20260516_daily_pnl.csv
7. outputs/paper_trading/prev3y_crypto/20260516_monthly_review.json
8. outputs/paper_trading/prev3y_crypto/20260516_risk_events.jsonl
9. outputs/paper_trading/prev3y_crypto/20260516_forward_validation.json
10. outputs/logs/prev3y_crypto/20260516_paper_trading_setup.log
11. docs/research/CODEX_TASK_QUEUE.md
12. docs/research/CLAUDE_REVIEW_QUEUE.md

Do:
- Perform REVIEW-006 draft only.
- Verify TASK-006 stayed within planning / simulation / logging scope.
- Verify no exchange order submission code exists.
- Verify no Bybit trading API connection exists.
- Verify no API key / secret handling exists.
- Verify paper_execution_status is NOT_STARTED.
- Verify live_trading_status is FORBIDDEN.
- Verify forward_validation_pass is false.
- Verify target_positions / simulated_fills / daily_pnl / monthly_review / risk_events / forward_validation outputs exist.
- Verify REVIEW-006_PACKET.md and REVIEW-006_NUMBERS.json exist.
- Verify tests passed:
  - overlay tests
  - kill switch tests
  - local recorder tests
  - forward validation tests
  - safety scan
- Verify mandatory overlays:
  - funding_filter > 0.03%/8h
  - long_cap_50pct
  - symbol_cap_5pct
- Verify kill switches:
  - max DD > 30%
  - 5 consecutive losing cycles
  - NAV < 70%
- Identify whether Opus final review is required.

Known Codex results to verify:
- python -m unittest tests.paper_trading.test_overlay tests.paper_trading.test_risk_recorder_validator PASS, 6 tests
- python -m apps.paper_trading.report --output-date 20260516 returned REVIEW_READY
- safety scan PASS
- paper_execution_status = NOT_STARTED
- live_trading_status = FORBIDDEN
- forward_validation_pass = false
- reproducibility hash = 40ab5158eb7fdf69bcd86083dd55cffe5a7a9619050df8eeadd6498eca520fa1

Output:
Create:
docs/research/review_drafts/REVIEW-006_DRAFT_BY_SONNET.md

Use this format:

## REVIEW-006 Draft Verdict
PASS_CANDIDATE / CONDITIONAL_PASS_CANDIDATE / FAIL_CANDIDATE

## Blocking Issues
None if no blocking issue.

## Safety Review
- order submission code
- Bybit trading API
- API credentials
- paper execution status
- live trading status

## Output Review
List whether required outputs exist and are schema-valid.

## Risk / Kill Switch Review
List overlay and kill switch results.

## Forward Validation Review
Explain why forward_validation_pass is false and whether that is expected.

## Issues Needing Opus Decision
List decisions requiring Opus:
- Whether TASK-006 can be marked DONE.
- Whether paper trading planning is accepted.
- Whether paper execution remains blocked.
- Whether TASK-007b / TASK-005 / REVIEW-006b remain required.
- Whether live trading remains forbidden.

## Suggested Opus Prompt
Write a short prompt Rick can paste to Opus for final decision.

Do not:
- Do not mark TASK-006 DONE.
- Do not start paper trading.
- Do not start live trading.
- Do not modify strategy code.
- Do not modify paper outputs.
- Do not connect to exchange APIs.


## review-006-final

Use Opus.

Read:
1. docs/research/review_drafts/REVIEW-006_DRAFT_BY_SONNET.md
2. docs/research/review_packets/REVIEW-006_PACKET.md
3. docs/research/review_packets/REVIEW-006_NUMBERS.json
4. outputs/paper_trading/prev3y_crypto/20260516_forward_validation.json
5. outputs/paper_trading/prev3y_crypto/20260516_risk_events.jsonl
6. outputs/logs/prev3y_crypto/20260516_paper_trading_setup.log

Purpose:
Execute REVIEW-006 final decision.

Context:
TASK-006 implements paper trading planning / simulation / logging only.
It does not execute trades.
It does not connect to Bybit.
It does not accept API keys or secrets.
It does not submit orders.
Live trading remains forbidden.

Sonnet draft summary:
- Safety scan PASS, violations = [].
- No exchange connection.
- No credentials.
- No order submission path.
- paper_execution_approval = false.
- live_trading_status = FORBIDDEN.
- All outputs contain safety flags.
- Architecture cannot submit orders.
- Overlay rule validation passed.
- On 2026-04-01, BTC/ETH/LINK 30-day average funding rates were below the 0.03%/8h threshold, so overlay_event_count = 0 is correct.
- Funding filter effect is regime-dependent.

Blocking issues needing Opus decision:
B-1:
Proxy Sharpe = -2.9012, from recent 30-day proxy window during weak 2026 Q1. Known net alpha = -1.20%, but historical NAV accumulation remains positive with peak around +30.7%.
Question: Is this acceptable as NOT_STARTED planning state, or does it block TASK-006?

B-2:
System self-triggered STOP_PAPER_PENDING_REVIEW because Sharpe -2.90 < 0.2 threshold.
Question: Is this evidence that risk control works, and should paper execution remain blocked pending further review?

Do:
- Decide REVIEW-006 verdict:
  PASS / CONDITIONAL_PASS / FAIL
- Decide whether TASK-006 can be marked DONE.
- Decide whether paper trading planning is accepted.
- Decide whether paper trading execution remains blocked.
- Decide whether TASK-007b / TASK-005 / REVIEW-006b / 30-day forward validation remain required.
- Decide whether live trading remains forbidden.
- Define required follow-up tasks.

Output format:

## Verdict
PASS / CONDITIONAL_PASS / FAIL

## Final Decision On Blocking Issues
### B-1 Proxy Sharpe
### B-2 STOP_PAPER_PENDING_REVIEW

## Safety Decision
- order submission:
- exchange API:
- API credentials:
- paper execution:
- live trading:

## TASK-006 Decision
- state:
- can mark DONE:
- required caveats:

## Downstream Decisions
- TASK-005:
- TASK-007b:
- REVIEW-006b:
- 30-day forward validation:
- paper execution:
- live trading:

## Required Follow-up Tasks

## Queue Updates

Append result to:
docs/research/CLAUDE_REVIEW_LOG.md

Update:
docs/research/CODEX_TASK_QUEUE.md
docs/research/CLAUDE_REVIEW_QUEUE.md
docs/research/commands/COMMAND_LOG.md

Do not:
- Do not modify strategy code.
- Do not rerun paper simulation.
- Do not modify official outputs.
- Do not approve paper execution.
- Do not approve live trading.
- Do not connect to exchange APIs.


## task-007b-workorder

Use Sonnet.

Purpose:
Create TASK-007b Weight Cap + Redistribution workorder.

Background:
REVIEW-006 final decision PASS.
TASK-006 is DONE as planning/simulation/logging only.
Paper trading execution remains FORBIDDEN.
Opus REVIEW-006 states TASK-007b is a hard gate before any paper execution.

TASK-007b objective:
Study whether strategy-level or overlay-level weight cap with redistribution can reduce concentration risk without destroying alpha.

Create:
docs/research/codex_workorders/TASK-007b_weight_cap_redistribution.md

The workorder must include:
1. 任務一句話
2. 任務目的
3. 為什麼重要
4. Scope: research / overlay study only
5. Inputs
6. Outputs
7. Redistribution variants
8. Metrics
9. Warning / fail gates
10. 禁止修改範圍
11. 完成後回報格式
12. NOTE 區

Required variants:
- baseline combined_paper_safe_variant
- cap_5pct_no_redistribution
- cap_5pct_redistribute_same_side
- cap_5pct_redistribute_all_eligible
- cap_3pct_no_redistribution
- cap_3pct_redistribute_same_side
- DOT_cap_5pct_redistribute_same_side
- top5_cap_5pct_redistribute_same_side
- combined_cap_5pct_plus_funding_filter
- paper_safe_redistributed_variant

Required analysis:
- Sharpe
- IR vs equal-weight
- IR vs BTC
- max DD
- net alpha
- alpha retention vs combined_paper_safe_variant
- top5 concentration
- single symbol concentration
- long net
- short net
- gross exposure
- net exposure
- turnover proxy
- fee / slippage / funding cost impact

Hard requirements:
- Do not modify strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not modify official outputs.
- Use post-processing overlays only unless the workorder explicitly asks for a separate future strategy-layer implementation.
- Paper execution remains forbidden.
- Live trading remains forbidden.

Warning gates:
- Sharpe drops below 0.7 → WARNING
- IR vs equal-weight drops below 0.3 → WARNING
- max DD worsens by more than 1.25x → WARNING
- top5 concentration remains above 60% → WARNING
- single symbol concentration remains above 25% → WARNING
- alpha retention below 70% → WARNING
- redistribution increases turnover proxy by more than 50% → WARNING

Fail gates:
- baseline reconciliation mismatch > 1e-6 → FAIL
- missing outputs → FAIL
- schema mismatch → FAIL
- paper/live execution code appears → FAIL

Do not:
- Do not implement TASK-007b.
- Do not modify strategy code.
- Do not approve paper execution.
- Do not approve live trading.

Output:
Write the workorder file.
Update COMMAND_LOG.md.
Do not execute TASK-007b implementation.


## review-007b-draft

Use Sonnet.

Read:
1. docs/research/codex_workorders/TASK-007b_weight_cap_redistribution.md
2. docs/research/review_packets/REVIEW-007b_PACKET.md
3. docs/research/review_packets/REVIEW-007b_NUMBERS.json
4. outputs/variants/prev3y_crypto/20260516_task007b_cap_summary.csv
5. outputs/variants/prev3y_crypto/20260516_task007b_cap_daily.csv
6. outputs/variants/prev3y_crypto/20260516_task007b_redistribution_log.csv
7. outputs/variants/prev3y_crypto/20260516_task007b_gate_report.json
8. outputs/logs/prev3y_crypto/20260516_task007b_weight_cap_redistribution.log
9. docs/research/CODEX_TASK_QUEUE.md
10. docs/research/CLAUDE_REVIEW_QUEUE.md

Do:
- Perform REVIEW-007b draft only.
- Verify official outputs exist.
- Verify baseline reconciliation max diff <= 1e-6.
- Verify fail gates all pass.
- Verify cap20 / cap15 / cap10 results.
- Verify 20% and 15% caps are no-op.
- Verify 10% cap breaches:
  - 61 dates
  - 488 redistribution_has_no_room events
- Verify cap10 Sharpe drop is about 6.48%, below 30% warning threshold.
- Interpret whether TASK-007b meaningfully reduces concentration risk.
- Identify whether Opus final review is required.

Known Codex results to verify:
- Runner status = REVIEW_READY
- py_compile = PASS
- baseline reconciliation max diff = 2.05e-16
- fail gates all PASS
- reproducibility hash = f5c962e11189cc4f91dedbc50b00456830d1fdc6e868c1638ad6b3e3e4db07b7
- baseline Sharpe = 0.8918
- baseline net alpha = 28.53%
- baseline top5 concentration = 95.56%
- baseline single concentration = 25.45%
- cap20 is no-op
- cap15 is no-op
- cap10 Sharpe = 0.8341
- cap10 net alpha = 26.36%
- cap10 alpha retention = 92.38%
- cap10 top5 concentration = 98.69%
- cap10 single concentration = 24.81%

Output:
Create:
docs/research/review_drafts/REVIEW-007b_DRAFT_BY_SONNET.md

Use this format:

## REVIEW-007b Draft Verdict
PASS_CANDIDATE / CONDITIONAL_PASS_CANDIDATE / FAIL_CANDIDATE

## Blocking Issues
None if no blocking issue.

## Output Verification
Check files, schema, reconciliation, gates, reproducibility.

## Cap Variant Review
Review cap20, cap15, cap10.

## Concentration Interpretation
Explain whether redistribution solved concentration risk.

## Issues Needing Opus Decision
List decisions requiring Opus:
- Whether TASK-007b can be DONE.
- Whether cap10 is enough for paper execution gate.
- Whether TASK-008 remains required.
- Whether paper execution remains blocked.

## Suggested Opus Prompt
Write a short prompt Rick can paste to Opus for final decision.

Do not:
- Do not mark TASK-007b DONE.
- Do not modify strategy code.
- Do not rerun baseline.
- Do not rerun cost stress.
- Do not rerun attribution.
- Do not rerun TASK-007.
- Do not rerun TASK-007b.
- Do not modify official outputs.
- Do not approve paper execution.
- Do not approve live trading.


## record-review-007b-final

Use Sonnet.

Purpose:
Record REVIEW-007b Opus final decision into project files.

Final decision summary:
- REVIEW-007b verdict: PASS
- TASK-007b: DONE
- B-1 decision: choose A
- Interpretation: TASK-007b completed its research goal. The fact that weight cap + redistribution failed to reduce concentration is a valid research result, not a task failure.
- Key conclusion: concentration is alpha-space, not weight-space.
- cap20 / cap15 were no-op.
- cap10 triggered but all 488 redistribution events had no same-side room.
- cap10 worsened top5 concentration from 95.56% to 98.69%.
- cap10 slightly improved single concentration from 25.45% to 24.81%.
- Weight cap + redistribution should be excluded from future concentration-control proposals unless REVIEW-007b is explicitly revisited.
- TASK-008 remains required and must focus on alpha-space concentration control.
- TASK-006 remains DONE / PASS.
- Paper planning remains completed.
- Paper execution remains FORBIDDEN.
- Live trading remains FORBIDDEN.

Required TASK-008 queue update:
- Scope must be alpha-space cap, not weight-space cap.
- Add explicit warning: do not redo weight cap + redistribution; REVIEW-007b already excluded it.
- Candidate variants:
  1. rolling alpha-contribution cap
  2. alpha-share-based position sizing
  3. explicit cooldown / blacklist after sustained top contribution

Do:
- Append final decision to docs/research/CLAUDE_REVIEW_LOG.md.
- Update docs/research/CODEX_TASK_QUEUE.md:
  - TASK-007b -> DONE
  - TASK-008 -> TODO / READY_FOR_WORKORDER or equivalent
  - TASK-008 scope = alpha-space concentration control
- Update docs/research/CLAUDE_REVIEW_QUEUE.md:
  - REVIEW-007b -> PASS
- Update docs/research/commands/COMMAND_LOG.md.
- Update docs/research/commands/NEXT_ACTION.md to STANDBY / WAITING, Owner = Rick.

Do not:
- Do not modify strategy code.
- Do not rerun any research output.
- Do not modify official outputs.
- Do not approve paper execution.
- Do not approve live trading.
- Do not implement TASK-008.


## review-006-addenda-check

Use Sonnet.

Purpose:
Review TASK-006 REVIEW-006 addenda only.
This is not REVIEW-006b PASS.
This does not approve paper execution.

Read:
1. docs/research/review_packets/REVIEW-006_PACKET.md
2. docs/research/review_packets/REVIEW-006_NUMBERS.json
3. outputs/paper_trading/prev3y_crypto/20260516_forward_validation.json
4. outputs/paper_trading/prev3y_crypto/20260516_monthly_review.json
5. outputs/paper_trading/prev3y_crypto/20260516_simulated_fills.csv
6. outputs/logs/prev3y_crypto/20260516_paper_trading_setup.log
7. docs/research/CODEX_TASK_QUEUE.md
8. docs/research/commands/COMMAND_LOG.md

Do:
- Verify the three REVIEW-006 addenda are implemented:
  1. proxy_sharpe_long_window
  2. fill_definition
  3. funding_filter_active_this_month
- Verify proxy Sharpe fields:
  - 30d = -2.9012
  - 90d = 1.1681
  - full active 760d = 0.8037
- Verify 30d proxy Sharpe is clearly labeled noisy / short-window.
- Verify fill_definition explains fills are weight deltas, not total positions.
- Verify funding_filter_active_this_month=false and explains regime-dependent behavior.
- Verify paper_execution remains FORBIDDEN.
- Verify live_trading remains FORBIDDEN.
- Verify no exchange / Bybit / API key / order submission code was added.
- Update COMMAND_LOG.md.

Output:
Create:
docs/research/review_drafts/REVIEW-006_ADDENDA_CHECK_BY_SONNET.md

Do not:
- Do not mark REVIEW-006b PASS.
- Do not approve paper execution.
- Do not approve live trading.
- Do not modify strategy code.
- Do not rerun paper simulation.
- Do not modify official outputs beyond review notes.


## review-005-draft

Use Sonnet.

Read:
1. docs/research/codex_workorders/TASK-005_vps_bot_monitor.md
2. docs/research/review_packets/REVIEW-005_PACKET.md
3. docs/research/review_packets/REVIEW-005_NUMBERS.json
4. outputs/monitor/prev3y_crypto/20260517_heartbeat.parquet
5. outputs/monitor/prev3y_crypto/alerts/20260517.jsonl
6. outputs/logs/prev3y_crypto/20260517_monitor_setup.log
7. configs/monitor.yaml
8. .gitignore
9. docs/research/CODEX_TASK_QUEUE.md
10. docs/research/CLAUDE_REVIEW_QUEUE.md
11. docs/research/commands/COMMAND_LOG.md

Do:
- Perform REVIEW-005 draft only.
- Verify TASK-005 stayed within observer-only monitoring / logging / alerting scope.
- Verify no exchange API connection exists.
- Verify no API key / secret handling exists beyond env/local ignored config policy.
- Verify configs/monitor.yaml contains only safe non-secret defaults.
- Verify configs/monitor_secrets.yaml was not created.
- Verify .gitignore protects monitor secret config patterns.
- Verify no order submission code exists.
- Verify no auto-restart code exists.
- Verify paper/live trading remain forbidden.
- Verify official outputs exist:
  - heartbeat parquet
  - alerts JSONL
  - monitor setup log
  - REVIEW-005_PACKET.md
  - REVIEW-005_NUMBERS.json
- Verify schema checks:
  - heartbeat schema PASS
  - alerts JSONL schema PASS
- Verify tests:
  - py_compile PASS
  - unittest monitor tests PASS, 6 tests
  - runner returned REVIEW_READY
  - safety scan PASS
- Verify reproducibility hash:
  - 25cbf9c172b7bf377974e0fd1d568d57a888c8b090c25049f460b3c2ca42a606
- Decide whether Opus final review is required.

Known Codex results to verify:
- python -m py_compile ... PASS
- python -m unittest tests.monitor.test_heartbeat tests.monitor.test_alerts PASS, 6 tests
- python scripts\task005_vps_bot_monitor.py --output-date 20260517 -> REVIEW_READY
- safety scan PASS
- heartbeat schema PASS
- alerts JSONL schema PASS
- no exchange API
- no secrets
- no configs/monitor_secrets.yaml
- no order code
- no auto-restart code
- no paper/live execution

Output:
Create:
docs/research/review_drafts/REVIEW-005_DRAFT_BY_SONNET.md

Use this format:

## REVIEW-005 Draft Verdict
PASS_CANDIDATE / CONDITIONAL_PASS_CANDIDATE / FAIL_CANDIDATE

## Blocking Issues
None if no blocking issue.

## Safety Review
- exchange API connection
- API credentials / secrets
- order submission code
- auto-restart code
- paper execution status
- live trading status

## Output Review
Check heartbeat parquet, alerts JSONL, monitor setup log, REVIEW-005 packet, REVIEW-005 numbers.

## Schema / Test Review
Check schema validation, tests, safety scan, reproducibility hash.

## Monitor Functionality Review
Evaluate heartbeat, alerts, log scanner, safety gates, monitor hook integration.

## Issues Needing Opus Decision
List decisions requiring Opus:
- Whether TASK-005 can be marked DONE.
- Whether TASK-005 is sufficient for 30-day forward record infrastructure.
- Whether paper execution remains blocked.
- Whether live trading remains forbidden.

## Suggested Opus Prompt
Write a short prompt Rick can paste to Opus for final decision.

Do not:
- Do not mark TASK-005 DONE.
- Do not connect to exchange APIs.
- Do not ask for API keys or secrets.
- Do not modify monitor outputs.
- Do not modify strategy code.
- Do not start paper trading.
- Do not approve paper execution.
- Do not approve live trading.


## review-005-b1-hotfix-check

Use Sonnet.

Purpose:
Verify REVIEW-005 B-1 hotfix only.

Read:
1. docs/research/review_drafts/REVIEW-005_DRAFT_BY_SONNET.md
2. docs/research/review_packets/REVIEW-005_PACKET.md
3. docs/research/review_packets/REVIEW-005_NUMBERS.json
4. .gitignore
5. outputs/logs/prev3y_crypto/20260517_monitor_setup.log
6. docs/research/commands/COMMAND_LOG.md

Do:
- Verify .gitignore contains exactly these monitor secret patterns:
  - configs/monitor_secrets.yaml
  - configs/monitor_secrets.yml
  - configs/monitor_secrets.local.yaml
  - configs/monitor_secrets.local.yml
- Verify safety scan PASS.
- Verify secret_in_vcs=false.
- Verify monitor tests PASS, 6 tests.
- Verify runner returned REVIEW_READY.
- Verify REVIEW-005_PACKET.md and REVIEW-005_NUMBERS.json were refreshed.
- Verify paper_execution remains FORBIDDEN.
- Verify live_trading remains FORBIDDEN.
- Decide whether B-1 is closed.
- Decide whether REVIEW-005 can proceed to Opus final decision.
- Update COMMAND_LOG.md.

Output:
Create or update:
docs/research/review_drafts/REVIEW-005_B1_HOTFIX_CHECK_BY_SONNET.md

Do not:
- Do not mark TASK-005 DONE.
- Do not connect to exchange APIs.
- Do not ask for API keys or secrets.
- Do not approve paper execution.
- Do not approve live trading.


## record-review-005-final

Use Sonnet.

Purpose:
Record REVIEW-005 Opus final decision into project files.

Final decision summary:
- REVIEW-005 verdict: PASS
- TASK-005: DONE
- single_channel_only: caveat, not blocker
- TASK-005 observer-only monitor scaffold is accepted
- TASK-005 has no exchange API, no secrets, no order submission, no auto-restart
- paper execution remains FORBIDDEN
- live trading remains FORBIDDEN
- TASK-005a Real Alert Channel must be created as TODO and required before paper execution unless Rick explicitly waives it

TASK-005a required scope:
- At least one real external push channel:
  - Telegram bot or Discord webhook preferred
  - SMTP secondary
- Must use apps/monitor/channels/ or equivalent extension module
- Must keep JSONL alert writing
- Must include dry-run and live-send mode tests
- Secrets must only live in configs/monitor_secrets.local.yaml or environment variables
- No exchange API
- No order submission
- No auto-restart
- No paper execution
- No live trading

Do:
- Append final decision to docs/research/CLAUDE_REVIEW_LOG.md.
- Update docs/research/CODEX_TASK_QUEUE.md:
  - TASK-005 -> DONE
  - TASK-005a -> TODO
  - TASK-005a required before paper execution unless Rick explicitly waives it
- Update docs/research/CLAUDE_REVIEW_QUEUE.md:
  - REVIEW-005 -> PASS
- Update docs/research/commands/COMMAND_LOG.md.
- Update docs/research/commands/NEXT_ACTION.md to STANDBY / WAITING, Owner = Rick.

Do not:
- Do not modify strategy code.
- Do not rerun any research output.
- Do not modify official outputs.
- Do not approve paper execution.
- Do not approve live trading.
- Do not implement TASK-005a.


## task-005a-workorder

Use Sonnet.

Purpose:
Create TASK-005a Real Alert Channel workorder.

Background:
REVIEW-005 final decision PASS.
TASK-005 monitor scaffold is DONE.
single_channel_only was accepted as caveat, not blocker.
TASK-005a is required before paper execution unless Rick explicitly waives it.
Paper execution remains FORBIDDEN.
Live trading remains FORBIDDEN.

Create:
docs/research/codex_workorders/TASK-005a_real_alert_channel.md

The workorder must include:
1. 任務一句話
2. 任務目的
3. 為什麼重要
4. Scope: alert channel extension only
5. Inputs
6. Outputs
7. Channel design
8. Secret handling
9. Tests / validation
10. Safety gates
11. Forbidden actions
12. Completion report format
13. NOTE section

Required design:
- Add at least one real external push channel:
  - Telegram bot preferred
  - Discord webhook acceptable
  - SMTP secondary
- Keep local JSONL output from TASK-005.
- Implement under apps/monitor/channels/ or equivalent.
- Support dry-run mode.
- Support explicit live-send test mode.
- Secrets only from:
  - environment variables, or
  - configs/monitor_secrets.local.yaml
- configs/monitor_secrets.local.yaml must remain gitignored.
- Never write secrets to repo, logs, outputs, packet, or command log.

Required safety:
- No exchange API.
- No order submission.
- No auto-restart.
- No paper execution.
- No live trading.
- No strategy changes.
- No official research output modifications.

Required tests:
- dry-run send test
- schema validation
- secret redaction test
- forbidden terms scan
- channel config validation
- local JSONL still written

Do:
- Write the workorder.
- Update COMMAND_LOG.md.

Do not:
- Do not implement TASK-005a.
- Do not ask Rick to paste bot token / webhook into chat.
- Do not approve paper/live trading.


## review-005a-draft

Use Sonnet.

Read:
1. docs/research/codex_workorders/TASK-005a_real_alert_channel.md
2. docs/research/review_packets/REVIEW-005a_PACKET.md
3. docs/research/review_packets/REVIEW-005a_NUMBERS.json
4. outputs/logs/prev3y_crypto/20260517_task005a_alert_channel.log
5. configs/monitor.yaml
6. configs/monitor_secrets.example.yaml
7. apps/monitor/channels/
8. tests/monitor/test_channels.py
9. docs/research/CODEX_TASK_QUEUE.md
10. docs/research/CLAUDE_REVIEW_QUEUE.md
11. docs/research/commands/COMMAND_LOG.md

Do:
- Perform REVIEW-005a draft only.
- Verify TASK-005a stayed within alert-channel extension scope.
- Verify local_jsonl is preserved.
- Verify Telegram / Discord are implemented with dry_run=true default.
- Verify no real Telegram / Discord POST occurred.
- Verify external_post_attempted=false.
- Verify configs/monitor_secrets.local.yaml was not created.
- Verify configs/monitor_secrets.example.yaml contains placeholders only.
- Verify secret loading only supports env or ignored local config.
- Verify redaction works and secrets are not written to logs / outputs / packets / COMMAND_LOG.
- Verify injectable HTTP client design.
- Verify tests:
  - py_compile PASS
  - monitor unit tests PASS, 13 tests
  - runner REVIEW_READY
  - safety scan PASS
- Verify fail gates:
  - secret_in_vcs=false
  - secret_hardcoded=false
  - secret_written_to_logs=false
  - local_jsonl_removed=false
  - exchange_api_present=false
  - order_submission_code_present=false
  - monitor_auto_restart_present=false
- Decide whether Opus final review is required.

Known Codex results to verify:
- TASK-005a status moved to REVIEW, not DONE.
- Telegram/Discord are DRY_RUN.
- external_post_attempted=false.
- configs/monitor_secrets.local.yaml does not exist.
- tests ran 13 and OK.
- task005a_reproducibility_hash=06a28f791dbfeb931a35dadf1eb856f92c791d0bf8648b09ba004da5b8d58817
- paper/live remain FORBIDDEN.

Output:
Create:
docs/research/review_drafts/REVIEW-005a_DRAFT_BY_SONNET.md

Use this format:

## REVIEW-005a Draft Verdict
PASS_CANDIDATE / CONDITIONAL_PASS_CANDIDATE / FAIL_CANDIDATE

## Blocking Issues
None if no blocking issue.

## Safety Review
- secrets
- external POST
- exchange API
- order submission
- auto-restart
- paper execution
- live trading

## Channel Review
- local_jsonl
- Telegram
- Discord
- dry_run
- test-send separation

## Output / Test Review
- packet
- numbers
- log
- tests
- safety scan
- reproducibility hash

## Issues Needing Opus Decision
List decisions requiring Opus:
- Whether TASK-005a can be DONE.
- Whether TASK-005a satisfies real alert channel gate in dry-run scaffold form.
- Whether a human-run real --test-send is still required before paper execution.
- Whether paper/live remain forbidden.

## Suggested Opus Prompt
Write a minimal prompt Rick can paste to Opus for final decision.

Do not:
- Do not mark TASK-005a DONE.
- Do not ask for token/webhook.
- Do not connect to Telegram or Discord.
- Do not send real test alert.
- Do not modify monitor outputs.
- Do not modify strategy code.
- Do not approve paper execution.
- Do not approve live trading.


## record-review-005a-final

Use Sonnet.

Purpose:
Record REVIEW-005a Opus final decision into project files.

Final decision summary:
- REVIEW-005a verdict: PASS
- TASK-005a: DONE
- external_channels_dry_run_only: caveat for TASK-005a DONE, but blocker for paper execution unlock
- local_jsonl is preserved
- Telegram scaffold: DRY_RUN, external_post_attempted=false, redacted
- Discord scaffold: DRY_RUN, external_post_attempted=false, redacted
- configs/monitor_secrets.local.yaml is not created, which is correct
- no exchange API
- no order submission
- no auto-restart
- no paper execution
- no live trading
- paper execution remains FORBIDDEN
- live trading remains FORBIDDEN

Manual Rick gate:
- Before paper execution, Rick must run real --test-send for at least one external channel.
- Evidence must be redacted and saved to:
  outputs/monitor/test_send/<YYYYMMDD>_<channel>_proof.txt
- This is Rick ops verification, not a Codex task.
- Do not ask Rick to paste token/webhook into chat.

Do:
- Append final decision to docs/research/CLAUDE_REVIEW_LOG.md.
- Update docs/research/CODEX_TASK_QUEUE.md:
  - TASK-005a -> DONE
  - Add Rick manual --test-send evidence as paper execution gate item
- Update docs/research/CLAUDE_REVIEW_QUEUE.md:
  - REVIEW-005a -> PASS
- Update docs/research/commands/COMMAND_LOG.md.
- Update docs/research/commands/NEXT_ACTION.md to STANDBY / WAITING, Owner = Rick.

Do not:
- Do not modify strategy code.
- Do not rerun any research output.
- Do not modify official outputs.
- Do not approve paper execution.
- Do not approve live trading.
- Do not perform real --test-send.
- Do not ask Rick to paste token/webhook into chat.


## task-005a-test-send-checklist

Use Sonnet.

Purpose:
Create a manual ops checklist for Rick to run TASK-005a real --test-send safely.

Create:
docs/research/manual_ops/TASK-005a_test_send_checklist.md

The checklist must include:
1. Purpose
2. Safety warnings
3. Telegram setup path
4. Discord setup path
5. How to create configs/monitor_secrets.local.yaml locally
6. Reminder that secrets must never be pasted into chat
7. PowerShell commands to run --test-send
8. What output counts as success
9. How to redact evidence
10. Where to save proof:
   outputs/monitor/test_send/<YYYYMMDD>_<channel>_proof.txt
11. How to update COMMAND_LOG after Rick completes it
12. What remains forbidden:
   - paper execution
   - live trading
   - exchange API
   - order submission

Do:
- Write the manual checklist.
- Update COMMAND_LOG.md.

Do not:
- Do not ask Rick to paste token/webhook into chat.
- Do not create the real secret file.
- Do not run --test-send.
- Do not connect to Telegram or Discord.
- Do not approve paper/live trading.


## review-008-draft

Use Sonnet.

Read:
1. docs/research/codex_workorders/TASK-008_alpha_space_concentration_cap.md
2. docs/research/review_packets/REVIEW-008_PACKET.md
3. docs/research/review_packets/REVIEW-008_NUMBERS.json
4. outputs/variants/prev3y_crypto/20260517_task008_comparison.csv
5. outputs/variants/prev3y_crypto/20260517_task008_comparison.json
6. outputs/variants/prev3y_crypto/20260517_task008_variant_detail.csv
7. outputs/variants/prev3y_crypto/20260517_task008_attribution.json
8. outputs/logs/prev3y_crypto/20260517_task008_alpha_conc.log
9. docs/research/CODEX_TASK_QUEUE.md
10. docs/research/CLAUDE_REVIEW_QUEUE.md
11. docs/research/commands/COMMAND_LOG.md

Do:
- Perform REVIEW-008 draft only.
- Verify TASK-008 stayed alpha-space only.
- Verify no TASK-007b weight-space redistribution was reused.
- Verify src/signals/prev3y_momentum.py was not modified.
- Verify main strategy / ranking / universe / DQ / raw data were not modified.
- Verify no official baseline / cost stress / attribution reruns occurred.
- Verify baseline mismatch <= 1e-6.
- Verify fail gates are zero.
- Review warning gates, especially top5 concentration still > 75%.
- Review best candidates:
  - A_roll12_share20_exclude
  - A_roll12_share20_penalize50
  - A_roll24_share20_exclude
- Compare baseline vs combined_paper_safe_variant vs TASK-008 best candidate.
- Evaluate whether TASK-008 achieved its research purpose.
- Evaluate whether <75% concentration target failure is blocking or caveat.
- Evaluate whether best TASK-008 candidate should become future paper candidate or remain research-only.
- Verify paper execution remains FORBIDDEN.
- Verify live trading remains FORBIDDEN.
- Update COMMAND_LOG.md.

Known Codex results to verify:
- Runner status = REVIEW_READY
- fail gates = 0
- warning gates = 19
- baseline mismatch = 5.55e-17
- reproducibility hash = 4074c89bc2031783901d16a1a40912d99c44a5de0fb6dbb79b0162feec48ff41
- baseline top5 concentration = 95.56%
- best candidate Sharpe = 0.9636
- best candidate IR vs eqw = 0.7289
- best candidate net alpha = 31.00%
- best candidate alpha retention = 108.66%
- best candidate top5 concentration = 87.95%
- paper execution = FORBIDDEN
- live trading = FORBIDDEN

Output:
Create:
docs/research/review_drafts/REVIEW-008_DRAFT_BY_SONNET.md

Use this format:

## REVIEW-008 Draft Verdict
PASS_CANDIDATE / CONDITIONAL_PASS_CANDIDATE / FAIL_CANDIDATE

## Blocking Issues
None if no blocking issue.

## Scope / Safety Review
- alpha-space only
- weight-space excluded
- strategy file unchanged
- no official reruns
- paper/live forbidden

## Numerical Verification
- baseline reconciliation
- fail gates
- warning gates
- reproducibility hash
- key candidate metrics

## Variant Review
- Variant A rolling alpha cap
- Variant B alpha-share sizing
- Variant C cooldown blacklist
- comparison to baseline
- comparison to combined_paper_safe_variant

## Concentration Decision
Discuss whether top5 concentration > 75% is blocker or caveat.

## Paper Candidate Decision
Discuss whether any TASK-008 variant should replace or supplement combined_paper_safe_variant.

## Issues Needing Opus Decision
List decisions:
- TASK-008 PASS / CONDITIONAL_PASS / FAIL
- TASK-008 can be DONE?
- Is <75% miss blocking?
- Should best TASK-008 candidate become paper secondary / future candidate?
- Does TASK-006 primary spec change?
- Does paper execution remain forbidden?
- Does live trading remain forbidden?

## Suggested Opus Prompt
Write minimal prompt for Opus final decision.

Do not:
- Do not mark TASK-008 DONE.
- Do not modify strategy code.
- Do not rerun any task.
- Do not modify official outputs.
- Do not approve paper execution.
- Do not approve live trading.


## review-009-draft

Use Sonnet.

Read:
1. docs/research/codex_workorders/TASK-009_forward_record_runner.md
2. docs/research/review_packets/REVIEW-009_PACKET.md
3. docs/research/review_packets/REVIEW-009_NUMBERS.json
4. outputs/logs/prev3y_crypto/20260517_forward_record.log
5. outputs/forward_record/prev3y_crypto/
6. outputs/forward_record/prev3y_crypto_shadow_a_roll12/
7. apps/forward_record/
8. scripts/run_forward_record.py
9. tests/forward_record/
10. docs/research/CODEX_TASK_QUEUE.md
11. docs/research/CLAUDE_REVIEW_QUEUE.md
12. docs/research/commands/COMMAND_LOG.md

Do:
- Perform REVIEW-009 draft only.
- Verify TASK-009 scope is forward record / offline paper record only.
- Verify no Bybit connection was attempted.
- Verify no API key was requested.
- Verify no private trading endpoint / order endpoint exists.
- Verify 30-day forward clock is NOT_STARTED.
- Verify paper_execution_status=FORBIDDEN.
- Verify live_trading_status=FORBIDDEN.
- Verify primary combined_paper_safe_variant output was generated.
- Verify shadow A_roll12_share20_exclude output was generated.
- Verify primary and shadow outputs are separated.
- Verify review_006b_trigger_ready=false because dry-run and days_elapsed=0.
- Verify W/S gates are empty or correctly reported.
- Verify tests:
  - unittest tests.forward_record PASS, 11 tests
  - py_compile PASS
  - runner REVIEW_READY
  - safety scan PASS
- Evaluate whether local cache latest date 2026-04-30 vs record_date 2026-05-17 is acceptable for dry-run or needs caveat.
- Decide whether Opus final review is required.

Known Codex results to verify:
- TASK-009 moved to REVIEW, not DONE.
- runner command:
  python scripts/run_forward_record.py --date 20260517 --dry-run --shadow-track
- primary rows = 50
- shadow rows = 50
- signal_date = 2026-04-30
- record_date = 2026-05-17
- review_006b_trigger_ready = false
- warning gates = []
- stop gates = []
- Bybit connection = NOT_ATTEMPTED
- API key request = NOT_ATTEMPTED
- 30-day forward clock = NOT_STARTED
- paper/live = FORBIDDEN

Output:
Create:
docs/research/review_drafts/REVIEW-009_DRAFT_BY_SONNET.md

Use this format:

## REVIEW-009 Draft Verdict
PASS_CANDIDATE / CONDITIONAL_PASS_CANDIDATE / FAIL_CANDIDATE

## Blocking Issues
None if no blocking issue.

## Scope / Safety Review
- Bybit
- API keys
- private endpoints
- order endpoints
- 30-day clock
- paper/live status

## Output Review
- primary output
- shadow output
- metrics
- logs
- review packet
- review numbers

## Test / Validation Review
- tests
- py_compile
- runner
- safety scan
- reproducibility hash

## Forward Record Readiness
Assess whether TASK-009 is sufficient as runner infrastructure before VPS deployment / start-date selection.

## Caveats
Include local cache latest date 2026-04-30 vs record_date 2026-05-17 if relevant.

## Issues Needing Opus Decision
List decisions:
- Whether TASK-009 can be DONE.
- Whether local-cache dry-run is sufficient to validate runner.
- Whether forward record clock can be started after VPS + read-only API + Rick start-date.
- Whether paper/live remain forbidden.

## Suggested Opus Prompt
Write minimal prompt for Opus final decision.

Do not:
- Do not mark TASK-009 DONE.
- Do not connect to Bybit.
- Do not ask for API keys.
- Do not start 30-day clock.
- Do not approve paper execution.
- Do not approve live trading.
- Do not modify strategy code.
- Do not rerun official baseline / cost stress / attribution.


## review-009b-draft

Use Sonnet.

Read:
1. docs/research/codex_workorders/TASK-009b_forward_monitor_alerting.md
2. docs/research/review_packets/REVIEW-009b_PACKET.md
3. docs/research/review_packets/REVIEW-009b_NUMBERS.json
4. outputs/forward_record/alerts/20260517_alert_log.json
5. apps/forward_record/alert_conditions.py
6. apps/forward_record/alerting.py
7. tests/forward_record/test_alerting.py
8. scripts/run_forward_record.py
9. configs/monitor.yaml
10. docs/research/CODEX_TASK_QUEUE.md
11. docs/research/CLAUDE_REVIEW_QUEUE.md
12. docs/research/commands/COMMAND_LOG.md

Do:
- Perform REVIEW-009b draft only.
- Verify TASK-009b stayed within forward monitor / alerting scope.
- Verify A-1~A-7 alert conditions are implemented.
- Verify actual TASK-009 output paths are read from REVIEW-009_NUMBERS.json.
- Verify --live-alerts exists but was not used during validation.
- Verify default alert behavior is dry-run.
- Verify real Discord POST requires both --live-alerts and configs/monitor.yaml discord dry_run=false.
- Verify configs/monitor.yaml Discord remains dry_run=true.
- Verify alert log exists:
  outputs/forward_record/alerts/20260517_alert_log.json
- Verify alert log has dry_run=true, alerts_sent=0, discord_results=[].
- Verify no real Discord alert was sent.
- Verify no Bybit connection.
- Verify no API key request or read.
- Verify no order/private endpoint violation.
- Verify 30-day clock remains NOT_STARTED.
- Verify paper/live remain FORBIDDEN.
- Verify tests:
  - tests.forward_record.test_alerting PASS, 15 tests
  - tests.forward_record PASS, 26 tests
  - tests.monitor.test_channels PASS, 13 tests
  - py_compile PASS
  - dry-run runner PASS
- Decide whether Opus final review is required.

Known Codex results to verify:
- TASK-009b moved to REVIEW, not DONE.
- alert log dry_run=true
- alerts_sent=0
- discord_results=[]
- Discord dry_run=true in configs/monitor.yaml
- no --live-alerts used
- no real Discord POST
- no Bybit
- no API key
- clock NOT_STARTED
- paper/live FORBIDDEN

Output:
Create:
docs/research/review_drafts/REVIEW-009b_DRAFT_BY_SONNET.md

Use this format:

## REVIEW-009b Draft Verdict
PASS_CANDIDATE / CONDITIONAL_PASS_CANDIDATE / FAIL_CANDIDATE

## Blocking Issues
None if no blocking issue.

## Scope / Safety Review
- Discord alerting
- dry-run
- --live-alerts
- Bybit
- API keys
- order/private endpoints
- 30-day clock
- paper/live status

## Alert Condition Review
- A-1
- A-2
- A-3
- A-4
- A-5
- A-6
- A-7

## Output / Test Review
- alert log
- review packet
- review numbers
- tests
- py_compile
- dry-run runner

## Forward Clock Readiness
Assess whether TASK-009b is sufficient as pre-clock monitor / alerting infrastructure.

## Issues Needing Opus Decision
List:
- Whether TASK-009b can be DONE.
- Whether dry-run alerting validation is sufficient.
- Whether real Discord alert should remain Rick manual ops only.
- Whether 30-day clock can start after VPS/read-only source/working tree clean/start date.
- Whether paper/live remain forbidden.

## Suggested Opus Prompt
Write minimal prompt for Opus final decision.

Do not:
- Do not mark TASK-009b DONE.
- Do not send Discord alert.
- Do not use --live-alerts.
- Do not connect to Bybit.
- Do not ask for API keys.
- Do not start 30-day clock.
- Do not approve paper execution.
- Do not approve live trading.


## review-009d-draft

Use Sonnet.

Read:
1. docs/research/codex_workorders/TASK-009d_alert_e2e_drill.md
2. docs/research/review_packets/REVIEW-009d_PACKET.md
3. docs/research/review_packets/REVIEW-009d_NUMBERS.json
4. outputs/forward_record/drill/20260517_drill_report.json
5. scripts/drill_forward_alerts.py
6. tests/forward_record/test_alert_e2e_drill.py
7. apps/forward_record/alerting.py
8. apps/forward_record/alert_conditions.py
9. docs/research/CODEX_TASK_QUEUE.md
10. docs/research/CLAUDE_REVIEW_QUEUE.md
11. docs/research/commands/COMMAND_LOG.md

Do:
- Perform REVIEW-009d draft only.
- Verify TASK-009d stayed dry-run/mock only.
- Verify scripts/drill_forward_alerts.py does not read real webhook/API key/.env.
- Verify apps/forward_record/alerting.py and alert_conditions.py were not modified.
- Verify S-A1~S-A7 positive scenarios behave as expected.
- Verify negative scenarios S-A1b/S-A3b/S-A4b/S-A6b behave as expected.
- Check S-A5b naming/result carefully: Codex summary says S-A5b triggered; verify whether that is intended or a label mismatch.
- Verify Discord probe is DRY_RUN.
- Verify dry_run=true.
- Verify live_alerts_used=false.
- Verify external_post_attempted=false.
- Verify no ChannelResult.status == SENT.
- Verify redaction validation PASS.
- Verify dedupe validation PASS.
- Verify Discord template validation PASS.
- Verify safety scan PASS.
- Verify tests:
  - python scripts\drill_forward_alerts.py --date 20260517 PASS
  - py_compile PASS
  - test_alert_e2e_drill PASS, 18 tests
  - tests.forward_record PASS, 44 tests
  - tests.monitor.test_channels PASS, 13 tests
- Verify REVIEW-009d_NUMBERS.json status = REVIEW_READY.
- Verify TASK-009d moved to REVIEW, not DONE.
- Verify paper execution FORBIDDEN.
- Verify live trading FORBIDDEN.
- Verify 30-day forward clock NOT_STARTED.
- Decide whether Opus final review is required.

Known Codex results to verify:
- S-A1/S-A2/S-A3/S-A4/S-A5/S-A5b/S-A6/S-A7 trigger as expected.
- S-A1b/S-A3b/S-A4b/S-A6b no-trigger / skipped / dedupe as expected.
- Discord probe DRY_RUN.
- dry_run=true.
- live_alerts_used=false.
- external_post_attempted=false.
- SENT fail gate PASS.
- Redaction/dedupe/template/safety PASS.
- status REVIEW_READY.
- no real Discord, no Bybit, no API key/webhook, no clock start.

Output:
Create:
docs/research/review_drafts/REVIEW-009d_DRAFT_BY_SONNET.md

Use this format:

## REVIEW-009d Draft Verdict
PASS_CANDIDATE / CONDITIONAL_PASS_CANDIDATE / FAIL_CANDIDATE

## Blocking Issues
None if no blocking issue.

## Scope / Safety Review
- dry-run/mock only
- Discord POST
- webhook/API key/.env
- Bybit
- clock
- paper/live

## Scenario Review
- S-A1
- S-A2
- S-A3
- S-A4
- S-A5
- S-A5b
- S-A6
- S-A7
- negative scenarios

## Validation Review
- redaction
- dedupe
- template
- SENT fail gate
- test suite
- review packet/numbers
- drill report

## Caveats
List non-blocking caveats if any.

## Clock Readiness Decision
Assess whether TASK-009d satisfies the alert E2E drill prerequisite for 30-day clock readiness.

## Issues Needing Opus Decision
List:
- Whether TASK-009d can be DONE.
- Whether dry-run/mock E2E drill is sufficient.
- Whether 30-day clock can proceed after VPS/read-only source/working tree clean/start date.
- Whether paper/live remain forbidden.

## Suggested Opus Prompt
Write minimal prompt for Opus final decision.

Do not:
- Do not mark TASK-009d DONE.
- Do not send Discord alert.
- Do not use --live-alerts.
- Do not connect Bybit.
- Do not ask for API key/webhook.
- Do not start 30-day clock.
- Do not approve paper execution.
- Do not approve live trading.