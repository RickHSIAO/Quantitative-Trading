# EXP-005 Crypto Universe Methodology

## 目的

檢查目前 Crypto 策略是否受到 survivorship bias / universe selection bias 影響。

## 沒改什麼

- 沒有修改策略訊號。
- 沒有修改策略參數。
- 沒有修改成本模型。
- 沒有修改倉位管理。

## Universe 模式

1. `current_top100_bias_check`：使用目前 config/本地 DB 可用 crypto universe 回測歷史。這是 biased benchmark，只能當對照。
2. `static_pit_top100`：需要歷史市值排名 CSV，在 OOS 起點前一日取當時 top 100，OOS 固定。
3. `rolling_pit_top100_quarterly`：需要歷史市值排名 CSV，每季用 rebalance date 前一日可知 ranking 選出下一季 universe。

## 需要的 PIT Ranking CSV

- 預設路徑：`data\crypto_market_cap_rankings.csv`
- 必要欄位：`date,rank,symbol`。`symbol` 可填 `BTC`、`BTCUSDT` 或 `BYBIT:BTCUSDT.P`。
- 可選欄位：`market_cap`。
- 若沒有此檔案，static/rolling PIT 結果必須標記為 `missing_market_cap_history`，不得產生假績效。

## 排除規則

- 排除 stablecoins。
- 排除 wrapped tokens。
- 排除槓桿代幣。
- 排除 selection date 前 OHLCV 不足 180 天的標的。
- 排除 selection date 前 90 天成交量不足的標的。本腳本預設用 90 天 median dollar volume > 0 作為最低可交易性檢查，可用參數調高。

## 本次資料狀態

- Historical market-cap ranking CSV exists: `False`。
- Historical market-cap ranking SQLite table exists: `True`。
- Bybit-only tradable universe is used; Binance is intentionally excluded.
- Bybit current linear USDT perpetual instruments stored: `553`。
- CMC top200 / Bybit linear USDT perpetual intersection: `302`。
- Bybit OHLCV fetch result: `255` fetched, `45` skipped existing fresh, `2` no rows。
- current_top100_bias_check status: `biased_benchmark`。
- static_pit_top100 status: `ok`。
- rolling_pit_top100_quarterly status: `ok`。

## Bybit-Only Tradable Filter

本策略實盤交易所為 Bybit，因此 universe 最終只取：

```text
CMC historical ranking candidates
- stablecoins
- wrapped tokens
- leveraged tokens
∩ Bybit linear USDT perpetual instruments
∩ local OHLCV coverage / history filter
∩ 90-day liquidity filter
```

新增資料表：

```text
crypto_bybit_linear_instruments
crypto_bybit_ohlcv_fetch_log
```

新增腳本：

```powershell
python scripts\fetch_bybit_pit_universe_ohlcv.py --max-rank 200 --start-date 2018-01-01 --end-date 2026-05-08 --sleep 0.05
```

補資料後，本地 Crypto OHLCV registry 從 70 檔增加到 325 檔。

## Static / Quarterly PIT OOS 結果（Bybit OHLCV 補強後）

| Mode | status | total return | annual return | MDD | PF | Sharpe | Calmar | win rate | avg R | trades | traded symbols |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| current_top100_bias_check | biased_benchmark | +168.09% | +63.13% | -52.14% | 1.637 | 1.414 | 1.211 | 46.72% | +0.089 | 229 | 50 |
| static_pit_top100 | ok | +52.03% | +23.11% | -42.86% | 1.167 | 0.693 | 0.539 | 49.64% | +0.151 | 415 | 100 |
| rolling_pit_top100_quarterly | ok | +37.49% | +17.12% | -50.87% | 1.115 | 0.583 | 0.336 | 47.16% | +0.088 | 405 | 141 |

## Previous-3-Year Average Market Cap 年度結果（Bybit OHLCV 補強後）

| Year | Lookback | status | total return | MDD | PF | Sharpe | Calmar | trades | eligible local OHLCV |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2021 | 2018-2020 | no_backtest_result |  |  |  |  |  |  | 0 |
| 2022 | 2019-2021 | ok | +7.60% | -28.62% | 1.110 | 0.384 | 0.266 | 48 | 11 |
| 2023 | 2020-2022 | ok | +41.66% | -22.77% | 1.453 | 1.275 | 1.837 | 191 | 61 |
| 2024 | 2021-2023 | ok | +6.51% | -42.70% | 1.039 | 0.367 | 0.153 | 180 | 61 |
| 2025 | 2022-2024 | ok | -9.89% | -47.42% | 0.922 | -0.035 | -0.209 | 180 | 67 |
| 2026 | 2023-2025 | ok | +20.27% | -13.33% | 1.519 | 1.530 | 5.308 | 75 | 69 |

## 本次回答

1. 現有 universe 是否明顯高估績效？`是。biased benchmark +168.09%，Bybit-only static PIT +52.03%，rolling PIT +37.49%。`
2. static point-in-time top100 是否仍有 edge？`有弱 edge，但不夠強。PF 1.167 只略高於 1.15，Sharpe 0.693 未達 0.70，Calmar 0.539 偏低。`
3. rolling top100 是否比固定 top100 更穩？`沒有。rolling PF 1.115、Sharpe 0.583、MDD -50.87%，比 static 更弱。`
4. 績效是否集中在少數幣？`是。comparison CSV 的 top/worst contributors 與 EXP-004 都顯示集中風險。`
5. 是否值得繼續研究這個策略？`需要更多測試，但不應再用 current-biased universe 調參。下一步應做 liquidity throttle / symbol cap / regime filter，而不是提高槓桿。`

## 結論

需要更多測試。
