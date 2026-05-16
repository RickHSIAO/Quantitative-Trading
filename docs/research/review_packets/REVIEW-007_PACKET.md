# REVIEW-007 Packet - TASK-007 Long-side Variant Study

Analysis basis: TASK-007 post-processing overlay study, not a trading decision.
No paper trading or live trading approval is implied by this packet.

## Methodology
- Inputs are official run008, TASK-002 realistic_combo, TASK-003 attribution, prices_daily, and funding_rates files.
- Return dating: positions.date + 1 day = return_date.
- Costs are official TASK-002 realistic_combo symbol-day costs scaled by abs(variant_weight / original_weight).
- Primary funding costs are not recalculated from raw funding rates.
- Primary cap variants use cap_no_redistribution; excess weight is removed.

## Key Results
| Variant | Sharpe | IR vs EQW | Max DD | Net Alpha | Alpha Retention | Top5 Conc | Single Conc |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline_current_long_short | 0.8918 | 0.7168 | -19.64% | 28.53% | 100.00% | 95.56% | 25.45% |
| short_only_unscaled | 0.4045 | 0.5511 | -49.18% | 33.73% | 118.23% | 72.47% | 21.53% |
| short_only_rescaled | 0.4106 | 0.5189 | -75.74% | 68.52% | 240.13% | 71.64% | 21.24% |
| long_only_unscaled | -0.0763 | 0.9493 | -41.58% | -5.18% | -18.15% | -389.35% | -96.64% |
| long_only_rescaled | -0.0733 | 1.7341 | -70.44% | -9.95% | -34.86% | -405.89% | -100.76% |
| no_long_side | 0.4045 | 0.5511 | -49.18% | 33.73% | 118.23% | 72.47% | 21.53% |
| long_half_weight | 0.5846 | 0.6225 | -34.04% | 31.14% | 109.15% | 80.58% | 23.32% |
| long_with_50pct_cap | 0.9000 | 0.7182 | -19.64% | 28.80% | 100.95% | 94.69% | 25.21% |
| top5_symbol_cap_5pct | 0.7225 | 0.6927 | -19.64% | 22.99% | 80.58% | 103.56% | 21.39% |
| DOT_capped | 0.7922 | 0.7030 | -19.64% | 25.15% | 88.15% | 98.31% | 21.36% |
| no_DOT | 0.7132 | 0.6965 | -17.58% | 21.29% | 74.62% | 116.13% | 25.23% |
| high_funding_cost_filter | 0.9586 | 0.7282 | -20.27% | 31.27% | 109.59% | 87.22% | 23.23% |
| combined_paper_safe_variant | 0.8037 | 0.6961 | -20.27% | 24.99% | 87.59% | 91.92% | 19.73% |

## Review Focus
- Best Sharpe variant: `high_funding_cost_filter` (0.9586).
- Warning gates triggered: ['short_only_rescaled_max_dd_worse_than_baseline_1p5x', 'long_only_rescaled_net_alpha_negative', 'top5_concentration_remains_above_60pct', 'single_symbol_concentration_remains_above_25pct'].
- Fail gates triggered: none.
- Treat the combined paper-safe variant as a quantitative input only; final paper/live decisions require review and Rick approval.

## Baseline Top Contributors
- BYBIT:DOTUSDT.P: net_alpha=7.26%, pct_of_variant_net_alpha=25.45%
- BYBIT:LTCUSDT.P: net_alpha=5.37%, pct_of_variant_net_alpha=18.83%
- BYBIT:XRPUSDT.P: net_alpha=5.01%, pct_of_variant_net_alpha=17.54%
- BYBIT:XLMUSDT.P: net_alpha=4.82%, pct_of_variant_net_alpha=16.89%
- BYBIT:ZECUSDT.P: net_alpha=4.81%, pct_of_variant_net_alpha=16.85%
- BYBIT:XTZUSDT.P: net_alpha=4.72%, pct_of_variant_net_alpha=16.55%
- BYBIT:FLOWUSDT.P: net_alpha=4.51%, pct_of_variant_net_alpha=15.81%
- BYBIT:GALAUSDT.P: net_alpha=3.87%, pct_of_variant_net_alpha=13.58%
- BYBIT:EGLDUSDT.P: net_alpha=3.63%, pct_of_variant_net_alpha=12.73%
- BYBIT:SANDUSDT.P: net_alpha=3.22%, pct_of_variant_net_alpha=11.28%

## Reproducibility
- reproducibility_hash: `824ff334e30810aeeaef8a06319a9ac8563b61f903835c89ae6cfbd9e140066f`
- git_commit: `c044f55ea767dbc307e80aa799318cab91458efc`
- output_date: `20260515`
