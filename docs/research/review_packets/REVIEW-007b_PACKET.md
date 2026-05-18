# REVIEW-007b Packet - TASK-007b Weight Cap + Redistribution

Analysis basis: post-processing overlay on official run008/TASK-002/TASK-007 inputs.
No paper trading or live trading approval is implied by this packet.

## Methodology
- Cap is applied daily as abs(weight) <= cap * original gross exposure.
- Long excess redistributes only to eligible long symbols; short excess redistributes only to eligible short symbols.
- If no same-side room exists, gross exposure is reduced and the event is logged.
- Costs use official TASK-002 realistic_combo symbol-day costs scaled by abs(new_weight / original_weight).
- Return dating follows TASK-007: positions.date + 1 day = return_date.

## Key Results
| Variant | Cap | Sharpe | IR vs EQW | Max DD | Net Alpha | Alpha Retention | Top5 Conc | Single Conc | No-room Events |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_current_long_short | - | 0.8918 | 0.7168 | -19.64% | 28.53% | 100.00% | 95.56% | 25.45% | 0 |
| cap_20pct | 20% | 0.8918 | 0.7168 | -19.64% | 28.53% | 100.00% | 95.56% | 25.45% | 0 |
| cap_15pct | 15% | 0.8918 | 0.7168 | -19.64% | 28.53% | 100.00% | 95.56% | 25.45% | 0 |
| cap_10pct | 10% | 0.8341 | 0.7053 | -19.64% | 26.36% | 92.38% | 98.69% | 24.81% | 488 |

## TASK-007 Alpha-based Reference
| Variant | Sharpe | Max DD | Net Alpha | Alpha Retention | Top5 Conc | Single Conc |
|---|---:|---:|---:|---:|---:|---:|
| top5_symbol_cap_5pct | 0.7225 | -19.64% | 22.99% | 80.58% | 103.56% | 21.39% |
| DOT_capped | 0.7922 | -19.64% | 25.15% | 88.15% | 98.31% | 21.36% |
| no_DOT | 0.7132 | -17.58% | 21.29% | 74.62% | 116.13% | 25.23% |

## Gates
- Fail gates triggered: none.
- Warning gates triggered: ['concentration_not_reduced_cap15', 'top5_concentration_above_threshold', 'single_symbol_concentration_above_threshold', 'redistribution_has_no_room'].
- Redistribution event counts: {'redistribution_has_no_room': 488}.

## Caveats
- 20% and 15% caps are no-op on current run008 weights because max symbol weight is about 12.5% of original gross.
- 10% cap has real breaches; same-side redistribution has no room on those breach days, so gross exposure is reduced.
- This is an overlay study only and not a strategy-layer sizing change.

## Reproducibility
- reproducibility_hash: `f5c962e11189cc4f91dedbc50b00456830d1fdc6e868c1638ad6b3e3e4db07b7`
- git_commit: `c44e12e54fde5a46ce0f0f1d53f5deabc92022f4`
- output_date: `20260516`

