# TASK-006 Paper Trading Planning

This package creates local planning, simulation, and logging artifacts only.
It has no exchange client, no credential intake, and no external execution
transport.

Primary spec: `combined_paper_safe_variant`.
Secondary tracking spec: `high_funding_cost_filter`.

Mandatory overlays:

- `funding_filter_0.03pct_8h`
- `long_cap_50pct`
- `symbol_cap_5pct`

## Simulated Fill Definition

`simulated_fills.csv` records intended position deltas only. A fill row exists
when `weight_delta = target_weight - prev_weight` is nonzero versus the prior
rebalance. Unchanged open positions remain in `target_positions.json` and do
not create fill rows.

Run:

```powershell
python -m apps.paper_trading.report --output-date 20260516
```

The generated files are review inputs. They do not authorize paper execution
or live trading.
