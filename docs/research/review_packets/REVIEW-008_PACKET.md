# REVIEW-008 Packet

- Status: REVIEW_READY
- Output date: 20260517
- Paper execution: FORBIDDEN
- Live trading: FORBIDDEN
- Baseline mismatch: 5.55111512313e-17
- Candidate variants: 11
- Lowest concentration candidate: A_roll12_share20_exclude
- Fail gates: 0
- Warning gates: 19

## Files
- comparison_csv: `outputs\variants\prev3y_crypto\20260517_task008_comparison.csv`
- comparison_json: `outputs\variants\prev3y_crypto\20260517_task008_comparison.json`
- detail_csv: `outputs\variants\prev3y_crypto\20260517_task008_variant_detail.csv`
- attribution_json: `outputs\variants\prev3y_crypto\20260517_task008_attribution.json`
- log: `outputs\logs\prev3y_crypto\20260517_task008_alpha_conc.log`

## Notes
- Alpha-space cap variants are implemented outside the main strategy.
- `src/signals/prev3y_momentum.py` is read-only for this task.
- TASK-007b weight-space redistribution is not used.
