# Prev3Y Crypto Data Requirements

This document is the data gate for TASK-001. The baseline must only run on real,
pre-existing input files. It must not create random, simulated, or synthetic
data to satisfy missing inputs.

## Required Files

1. `data/crypto/prices_daily.parquet`
2. `data/crypto/universe_membership.parquet`
3. `configs/prev3y_crypto.yaml`

Run the validator before any baseline run:

```powershell
python scripts\validate_prev3y_crypto_inputs.py
```

Machine-readable form:

```powershell
python scripts\validate_prev3y_crypto_inputs.py --json
```

If any required file is missing or schema-invalid, TASK-001 must be marked
`BLOCKED_BY_DATA`. Do not write `baseline.csv`, `positions.parquet`, or
`stats.json` from substitute data.

## Schema

### `prices_daily.parquet`

Required columns:

| column | type | unit / meaning |
|---|---|---|
| `date` | datetime64 | UTC calendar date |
| `symbol` | string | crypto symbol from the data source |
| `open` | float64 | price |
| `high` | float64 | price |
| `low` | float64 | price |
| `close` | float64 | price |
| `volume` | float64 | base asset contracts / coins |
| `quote_volume` | float64 | quote currency volume; if unavailable from source, document derivation |

Requirements:

- One row per `date, symbol`.
- Dates must be UTC daily bars.
- Prices and volume must come from a real exchange/vendor/local raw dataset.
- Do not backfill unavailable symbols from a current survivor list.

### `universe_membership.parquet`

Required columns:

| column | type | unit / meaning |
|---|---|---|
| `date` | datetime64 | UTC calendar date |
| `symbol` | string | same symbol namespace as prices |
| `is_member` | bool | true if the symbol is in the point-in-time universe on that date |

Requirements:

- One row per `date, symbol`.
- Store true membership rows only; absent rows are treated as non-members.
- Membership must be point-in-time and must not include symbols before listing
  or after delisting.
- It may use historical ranking snapshots, exchange listing metadata, or another
  auditable PIT source, but not a current live universe projected backward.

### `configs/prev3y_crypto.yaml`

Required keys:

| key | allowed values |
|---|---|
| `lookback_days` | positive integer |
| `rebalance_freq` | `monthly` / `weekly` |
| `top_n` | non-negative integer |
| `bottom_n` | non-negative integer |
| `ranking_method` | `return` / `risk_adjusted_return` |
| `entry_price` | `t1_open` / `t1_close` |
| `start_date` | `YYYY-MM-DD` |
| `end_date` | `YYYY-MM-DD` |
| `warmup_start_date` | `YYYY-MM-DD`, must be <= `start_date` |

## Missing Data Behavior

If `prices_daily.parquet` or `universe_membership.parquet` does not exist:

1. Stop the baseline run.
2. Emit `BLOCKED_BY_DATA` with the missing file list.
3. Keep or change TASK-001 status to `BLOCKED_BY_DATA`.
4. Add a NOTE naming the missing files and how to obtain them.
5. Do not generate random, simulated, synthetic, or placeholder data.

To unblock:

- Build `prices_daily.parquet` from a real OHLCV source covering the configured
  warm-up and backtest period.
- Build `universe_membership.parquet` from a real point-in-time universe source.
- Run `python scripts\validate_prev3y_crypto_inputs.py`.
- Only run `python scripts\run_prev3y_crypto_baseline.py` after validation passes.

## Current Local Check

Checked on 2026-05-13:

- `data/crypto/prices_daily.parquet`: exists, schema valid, `341786` rows,
  `324` symbols, date range `2020-10-21` to `2026-04-30`.
- `data/crypto/universe_membership.parquet`: exists, schema valid, `205570`
  rows, `273` symbols, date range `2020-10-21` to `2026-04-30`.
- `configs/prev3y_crypto.yaml`: exists, required keys valid.
- Missing required files: none.

Validator warnings are expected for this local snapshot because price coverage
starts after `warmup_start_date`; early baseline rows remain zero exposure until
enough real lookback history exists.
