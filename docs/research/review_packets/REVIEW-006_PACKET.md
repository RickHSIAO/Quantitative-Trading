# REVIEW-006 Packet - TASK-006 Paper Trading Planning Modules

Analysis basis: offline planning, simulation, and logging only.
No paper trading execution or live trading approval is implied.

## Scope
- Implemented local modules under `apps/paper_trading/`.
- Outputs are local JSON/CSV/JSONL/Markdown/log files only.
- External execution is unsupported by design.

## Variant Specs
- Primary: `combined_paper_safe_variant` Sharpe=0.8037, Max DD=-20.27%, Net Alpha=24.99%.
- Secondary tracking: `high_funding_cost_filter` Sharpe=0.9586, Max DD=-20.27%, Net Alpha=31.27%.

## Mandatory Overlays
- funding_filter_0.03pct_8h: long weight set to zero when 30-day average funding exceeds 0.03% per 8h.
- long_cap_50pct: long gross capped to 50% of gross exposure.
- symbol_cap_5pct: any symbol absolute weight capped at 5%, no redistribution.

## Output Summary
- Target date: 2026-04-01
- Intended fills: 3
- Daily PnL rows: 760
- Overlay events: 0
- Risk warnings: 0; kill switches: 0

## Forward Validation
- Status: NOT_STARTED
- Basis: historical_simulation_proxy_not_forward_execution
- Pass: False
- Blocker: requires real 30-day forward paper record plus Opus REVIEW-006b and Rick approval

## REVIEW-006b Addenda
- proxy_sharpe_long_window: 30d=-2.9012 (noisy short-window proxy), 90d=1.1681, full_active_760d=0.8037.
- Fill definition: `simulated_fills.csv` records nonzero `weight_delta = target_weight - prev_weight` versus the prior rebalance, not one row per held position.
- Current intended fills: 3; unchanged positions remain in `target_positions.json` and do not create fill rows.
- funding_filter_active_this_month: `false`; false means the funding filter did not trigger in this monthly setup and remains regime-dependent.

## Safety
- Safety scan: PASS
- No exchange client, credential intake, or external execution path is implemented.
- Paper execution remains blocked until TASK-007b PASS, TASK-005 online, REVIEW-006b PASS, 30 days forward validation, and Rick approval.
- Live trading remains FORBIDDEN.

## Reproducibility
- reproducibility_hash: `89feeb1c33fdf7c003ffcf705df1de8c22087463aa2852d65208edb63f53d7de`
- git_commit: `c44e12e54fde5a46ce0f0f1d53f5deabc92022f4`
- output_date: `20260516`

