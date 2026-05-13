# TASK-001 Prev3Y Crypto Universe Baseline

- 狀態：送 REVIEW
- 日期：2026-05-13
- config：`configs/prev3y_crypto.yaml`
- input validation：`python scripts\validate_prev3y_crypto_inputs.py`
- command：`python scripts\run_prev3y_crypto_baseline.py`

## 輸出

- `outputs/backtests/prev3y_crypto/20260513_run002_baseline.csv`
- `outputs/backtests/prev3y_crypto/20260513_run002_positions.parquet`
- `outputs/backtests/prev3y_crypto/20260513_run002_stats.json`
- `outputs/logs/prev3y_crypto/20260513_run002.log`

## 關鍵數字

| IR | Sharpe | Sortino | max DD | Calmar | annual turnover | hit rate |
|---:|---:|---:|---:|---:|---:|---:|
| -0.061757 | 0.493574 | 0.291535 | -19.4996% | 0.193255 | 1.228343x | 55.5263% |

## 樣本

- Baseline rows：2677 daily rows，`2019-01-01` 至 `2026-04-30`，無跳日。
- Warm-up：`2018-01-01`。
- 本地 price coverage：`2020-10-21` 至 `2026-04-30`。
- 第一個有效持倉日：`2024-04-01`。
- 有效持倉日數：760。
- 平均 universe size：全樣本 76.791184。
- 平均 tradable symbols（rebalance eligible ranked symbols）：15.218391。

## 資料來源與限制

- 補充資料 gate 已加入：baseline runner 現在只讀取已存在且 schema pass 的 parquet/config，不再自動產生輸入資料。
- 缺少 `prices_daily.parquet` 或 `universe_membership.parquet` 時，流程會輸出 `BLOCKED_BY_DATA` 並停止，不產生 fake baseline。
- `data/crypto/prices_daily.parquet` 由 `data/trading.db.prices` 衍生。
- `data/crypto/universe_membership.parquet` 由 `data/trading.db.crypto_market_cap_rankings` 與 `crypto_bybit_linear_instruments` 衍生。
- `quote_volume` 因本地 prices table 沒有 turnover 欄位，使用 `close * volume` 衍生。
- Universe membership 只存 true rows；缺少的 date/symbol 視為非 member。
- CMC ranking snapshot 最晚到 `2025-12-28`，2026-01 至 2026-04 使用該日以前可知的最後 snapshot。
- Benchmark：config 未指定 benchmark；使用同日 PIT universe 等權 long-only，缺 return 的 symbol 當日剔除。
- Positions：包含 `date, decision_date, effective_date, symbol, weight, signal_rank, signal_value, is_member`；最終輸出中 `is_member=False` rows 為 0。

## Input Validation

- `data/crypto/prices_daily.parquet`：exists，schema valid，341786 rows，324 symbols。
- `data/crypto/universe_membership.parquet`：exists，schema valid，205570 rows，273 symbols。
- `configs/prev3y_crypto.yaml`：exists，required keys valid。
- Missing required files：none。
- Validator warnings：price/universe coverage starts at `2020-10-21`, so early baseline rows are zero exposure until real lookback history exists。

## 可重現性

- `config_hash`：`3cd7ead1b912b032cf46c79fcaa0b0a49844613f733e01580a06213a2897cac5`
- `data_snapshot_hash`：`55191c754fca722c04025716952c05548048e140851b3c738c6c409d70ac2a38`
- stats hash run 1：`6dc6f39c5f5ed4c7d6ca2908c9cd0fa2fcb0c63cec8a6236003187495e59db60`
- stats hash run 2：`6dc6f39c5f5ed4c7d6ca2908c9cd0fa2fcb0c63cec8a6236003187495e59db60`
- `baseline.csv` 重算 stats 與 `stats.json` 差異小於 `1e-12`。

## 資料異常

這些異常存在於本地 price snapshot，但未進入最終 positions：

- `COMP-USD`：`2021-04-19` 至 `2021-08-15`，nonpositive open 5 rows。
- `ICP-USD`：`2021-05-10`，nonpositive open 1 row。
- `COMP-USD`：`2021-04-19` 至 `2021-08-15`，nonpositive low 11 rows。
- `ICP-USD`：`2021-05-10`，nonpositive low 1 row。
- `COMP-USD`：`2021-04-17` 至 `2022-01-15`，nonpositive close 205 rows。
- `COMP-USD`：`2021-04-17` 至 `2022-01-15`，missing OHLCV 205 rows。

## 暫緩

- 未加入 cost、funding、slippage；保留給 TASK-002。
- 未做參數優化；`top_n=25`、`bottom_n=25`、monthly rebalance、`return` ranking 均為固定 baseline。
- 未把 REVIEW-001 改為 PASS / FAIL；這留給 Claude review。
