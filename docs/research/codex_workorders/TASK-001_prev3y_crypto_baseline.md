# Codex 工單 — TASK-001：Prev3Y Crypto Universe Baseline

> 這是一張可以**整份貼給 Codex** 的工單。Codex 看到這份檔案後，應先檢查資料是否存在；若資料缺失，不可開工回測，必須回報 BLOCKED_BY_DATA。
> 對應 queue 條目：`docs/research/CODEX_TASK_QUEUE.md` → TASK-001。
> 對應審查條目：`docs/research/CLAUDE_REVIEW_QUEUE.md` → REVIEW-001。

資料檢查後只可回報以下三種狀態之一：

| 狀態 | 意思 |
|---|---|
| `READY_TO_IMPLEMENT` | 資料存在，可以實作 TASK-001 |
| `BLOCKED_BY_DATA` | 缺資料，先不能回測 |
| `NEED_CLARIFICATION` | 有資料但 schema / 日期 / universe 規則不清楚 |

---

## 0. 給 Codex 的開場守則（每張工單都適用）

1. **一次只做一張工單**。做完進 `REVIEW`，不可自己轉 `DONE`。
2. **嚴格遵守** 第 5 節「輸入」、第 6 節「輸出」、第 8 節「禁止修改範圍」。
3. 任何超出本工單範圍的修改（順手重構、改其他模組、調整其他 config）——
   **停手，先在這張工單末尾留 `NOTE:` 行**，等 Rick 或 Claude 回覆。
4. 產出的 CSV / parquet 一律附 schema（欄位名、型別、單位）寫在 log 或 README。
5. 沒有 Claude 審查通過前，**不可** 把實驗分支 merge 回 main。
6. 目前 repo 幾乎是空的（只有 `src/__init__.py` + `.venv`），本工單所列「規劃路徑」由你建立。
   建立時請保持模組化，不要把所有東西塞進一個檔。

---

## 1. 任務一句話

把 Prev3Y momentum 概念在 crypto universe 上做一次乾淨的 baseline 回測，產出 IR / Sharpe / max DD / turnover 等基本統計，作為後續所有研究的對照組。

---

## 2. 任務目的

- 為 Prev3Y momentum 在 crypto 上是否 work 提供第一份實證。
- 建立後續 cost stress（TASK-002）、attribution（TASK-003）、dashboard（TASK-004）的資料底層。
- 如果這一步就 fail，整條 pipeline 的優先順序要重排，先停損。

---

## 3. 為什麼重要

- 目前所有「Prev3Y 在 crypto 上會 work」的說法都是假設，沒有實證。
- 沒有這個 baseline，cost / attribution / dashboard 全都失去比較基準。
- 真錢上線前最便宜的「能不能做」答案，就是把 baseline 跑出來看一眼。

---

## 4. 範圍邊界（do / don't）

| Do | Don't |
|---|---|
| 建立 universe / data loader / backtester / config 等模組 | 加入 cost、funding、slippage（TASK-002 才做） |
| 跑出 baseline + 三件套輸出 | 自行嘗試「優化」參數以提高 IR |
| 用 point-in-time universe | 用「現在還活著」的清單反推歷史 |
| 用 t–1 訊號 + t+1 進場（或依 config） | 任何形式的未來視 |

---

## 5. 輸入檔案（規劃路徑，可由你建立）

> 若你已知本機 / 雲端有現成資料來源，請先在工單末端留 `NOTE: data source = ...` 註記後再開工。

- `data/crypto/prices_daily.parquet`
  日線 OHLCV，欄位至少：`[date, symbol, open, high, low, close, volume, quote_volume]`
  - 時區 UTC，已做股息 / 拆分等價格調整（如該交易所有）。
- `data/crypto/universe_membership.parquet`
  每日 universe 名單，**point-in-time**：
  - 欄位：`[date, symbol, is_member]`
  - 不可用「目前還活著」的清單反推歷史。
- `configs/prev3y_crypto.yaml`
  回測參數：
  - `lookback_days`（建議預設 3 年的交易日）
  - `rebalance_freq`（`monthly` / `weekly`）
  - `top_n` / `bottom_n`（多空各取多少）
  - `ranking_method`（`return` / `risk_adjusted_return`）
  - `entry_price`（`t1_open` / `t1_close`）
  - `start_date`、`end_date`、`warmup_start_date`

---

## 6. 輸出檔案（路徑與欄位嚴格固定）

> 檔名中的 `<YYYYMMDD>` 是執行當日（UTC）。一旦寫出，**不可覆寫**，需另開日期。

1. `outputs/backtests/prev3y_crypto/<YYYYMMDD>_baseline.csv`
   欄位：`date, portfolio_return, benchmark_return, gross_exposure, net_exposure, turnover, n_longs, n_shorts`

2. `outputs/backtests/prev3y_crypto/<YYYYMMDD>_positions.parquet`
   欄位：`date, symbol, weight, signal_rank`

3. `outputs/backtests/prev3y_crypto/<YYYYMMDD>_stats.json`
   欄位：`ir, sharpe, sortino, max_dd, calmar, turnover_annual, hit_rate, exposure_stats`

4. `outputs/logs/prev3y_crypto/<YYYYMMDD>.log`
   開頭必印：`random_seed`、`config_hash`、`data_snapshot_hash`、`git_commit`。

---

## 7. 驗收標準（逐條打勾）

- [ ] 回測期間至少 **2019-01 ~ 最近一個完整月**，且 log 與 README 明確標出 warm-up 起點。
- [ ] universe 為 point-in-time——任何時點的 symbol 集合**不得包含當天還未上市 / 已下市的幣**。
- [ ] 訊號使用 t–1 收盤之前的資料；t 收盤算 weight；t+1 開盤（或 t+1 收盤，依 config）進場。
      **不可** 出現 `pct_change().shift(0)` 或同期 leak 之類的對齊錯誤。
- [ ] `baseline.csv` 每一列時間戳唯一、無跳日。停盤日 / 無交易日的處理方式寫進 log。
- [ ] `stats.json` 的 IR / Sharpe / max DD 可從 `baseline.csv` 重新計算重現（±1e-6）。
- [ ] log 開頭印出：`random_seed`、`config_hash`、`data_snapshot_hash`、`git_commit`。
- [ ] 同一個 config × 同一份 data snapshot，**重跑兩次** 應產生相同結果（hash 比對）。

---

## 8. 禁止修改範圍

- 不可動 `data/` 下的 raw 檔（如已存在）。所有衍生資料寫在 `data/derived/` 或 `outputs/`。
- 不可在本工單中引入 cost / funding / slippage（那是 TASK-002）。
- 不可修改 `configs/prev3y_crypto.yaml` **以外**的設定檔。
- 不可把策略邏輯（universe 篩選、ranking）寫進 backtester；保持分層：
  - `data/` 純資料
  - `universe/` 篩選邏輯
  - `signals/` 訊號
  - `backtest/` 回測引擎（不知道任何訊號的語意）
  - `configs/` 參數

---

## 9. 完成後請回報以下 5 件事

請把回覆貼回對話，**逐點列出**，方便 Claude 開 REVIEW-001：

1. **4 個關鍵數字**：年化 IR、Sharpe、max DD、年化 turnover。
2. **回測樣本**：起訖日、warm-up 起點、有效交易日數、平均 universe 大小。
3. **資料異常清單**：遇到的缺漏 / 異常值 / universe 不一致；每筆寫出 symbol + 日期區間。
4. **可重現性證據**：兩次重跑的 `stats.json` 是否 hash 相同；不同請說明原因。
5. **未做 / 暫緩**：本工單範圍內但你決定先不做的事項（並說明理由）。

完成後狀態改為 `REVIEW`，等 Claude 進 REVIEW-001。

---

## 10. NOTE 區（Codex 留言處）

> 任何超出範圍的疑問、發現、暫存決策都寫在這。

- NOTE: 2026-05-13 supplemental data gate check = `data/crypto/prices_daily.parquet`、`data/crypto/universe_membership.parquet`、`configs/prev3y_crypto.yaml` all exist and schema validation passes.
- NOTE: current missing required files = none.
- NOTE: if either parquet input is missing or schema-invalid in a future run, TASK-001 must be marked `BLOCKED_BY_DATA`; do not generate random/simulated/synthetic data and do not run a baseline.
- NOTE: data acquisition path = real daily OHLCV source for `prices_daily.parquet` plus real point-in-time membership source for `universe_membership.parquet`; see `docs/research/DATA_REQUIREMENTS_PREV3Y.md`.
