# TASK-001 Prev3Y Crypto Universe Baseline

- 狀態：送 REVIEW
- 日期：2026-05-13
- config：`configs/prev3y_crypto.yaml`
- command：`python scripts\run_prev3y_crypto_baseline.py`

## 輸出

- `outputs/backtests/prev3y_crypto/20260513_baseline.csv`
- `outputs/backtests/prev3y_crypto/20260513_positions.parquet`
- `outputs/backtests/prev3y_crypto/20260513_stats.json`
- `outputs/logs/prev3y_crypto/20260513.log`

## 關鍵數字

| IR | Sharpe | Sortino | max DD | Calmar | annual turnover | hit rate |
|---:|---:|---:|---:|---:|---:|---:|
| -0.052954 | 0.517207 | 0.305626 | -19.4996% | 0.203754 | 1.228343x | 55.5263% |

## 樣本

- Baseline rows：2677 daily rows，`2019-01-01` 至 `2026-04-30`，無跳日。
- Warm-up：`2018-01-01`。
- 本地 price coverage：`2020-10-21` 至 `2026-04-30`。
- 第一個有效持倉日：`2024-04-01`。
- 有效持倉日數：760。
- 平均 universe size：全樣本 76.791184；有效持倉日 144.115132。

## 資料來源與限制

- `data/crypto/prices_daily.parquet` 由 `data/trading.db.prices` 衍生。
- `data/crypto/universe_membership.parquet` 由 `data/trading.db.crypto_market_cap_rankings` 與 `crypto_bybit_linear_instruments` 衍生。
- `quote_volume` 因本地 prices table 沒有 turnover 欄位，使用 `close * volume` 衍生。
- Universe membership 只存 true rows；缺少的 date/symbol 視為非 member。
- CMC ranking snapshot 最晚到 `2025-12-28`，2026-01 至 2026-04 使用該日以前可知的最後 snapshot。

## 可重現性

- `config_hash`：`3cd7ead1b912b032cf46c79fcaa0b0a49844613f733e01580a06213a2897cac5`
- `data_snapshot_hash`：`55191c754fca722c04025716952c05548048e140851b3c738c6c409d70ac2a38`
- stats hash run 1：`02bfeffd2b7f84f456566d2c605e2683a65d3fc316f8410a456e9714fdcbf87c`
- stats hash run 2：`02bfeffd2b7f84f456566d2c605e2683a65d3fc316f8410a456e9714fdcbf87c`
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
