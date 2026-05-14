# Codex Task Queue

最後更新：2026-05-12
維護者：Claude（任務卡撰寫） / Rick（核可）
狀態圖例：`TODO` / `READY_TO_IMPLEMENT` / `IN_PROGRESS` / `REVIEW` / `BLOCKED` / `BLOCKED_BY_DATA` / `DONE`

> **給 Codex 的全域守則**
> 1. 一次只做一個任務，做完進 `REVIEW`，**不可** 自行轉 `DONE`。
> 2. 嚴格遵守每張卡的「輸入檔案」「輸出檔案」「禁止修改範圍」。
> 3. 任何超出任務範圍的修改，先停手 → 在卡片下方留 `NOTE` → 等 Claude 或 Rick 回覆。
> 4. 產出的 CSV / parquet 一律附 schema（欄位名、型別、單位）。
> 5. 沒有 Claude 審查通過前，不要把實驗分支 merge 回 main。
> 6. 目前 repo 是空的（只有 `src/__init__.py`），所列「規劃路徑」由 Codex 建立；建立時請保持模組化、不要把所有東西塞進一個檔。

---

## TASK-001 — Prev3Y Crypto Universe 測試

- **狀態**：**DONE**（Claude REVIEW-001_final PASS，2026-05-13）
- **最終正式 baseline**：`20260513_run008`
- **Owner**：Codex
- **預估**：M（2–3 天）
- **依賴**：無（這是第一棒）
- **研究判定**：**需要更多測試**——保留路線、進入 cost stress；不淘汰、不立即上線。

### 任務目的
把現有的 Prev3Y momentum 想法搬到 crypto universe 上，做一次乾淨的 baseline 回測，產出 IR / Sharpe / max DD / turnover 等基本統計，作為後續一切研究的對照組。

### 為什麼重要
- 目前所有「Prev3Y 在 crypto 上會 work」的說法都還是假設，沒有實證。
- 這個 baseline 一旦建立，後面的 cost stress、attribution、dashboard 才有意義。
- 如果這一步就 fail，後面四個任務的優先順序要重新討論，省下大量工程時間。

### 輸入檔案（規劃路徑，由 Codex 建立）
- `data/crypto/prices_daily.parquet`：日線 OHLCV，欄位至少 `[date, symbol, open, high, low, close, volume, quote_volume]`，UTC，已調整。
- `data/crypto/universe_membership.parquet`：每日 universe 名單（**point-in-time**，禁止用「目前還活著」的清單反推歷史）。
- `configs/prev3y_crypto.yaml`：回測參數（lookback、rebalance freq、top-N、ranking method）。

### 資料 Gate（補充要求）
- 實作或回測前必須先執行 `python scripts\validate_prev3y_crypto_inputs.py`。
- 若 `prices_daily.parquet` 或 `universe_membership.parquet` 不存在或 schema 不正確，不可產生假資料、不可隨機模擬、不可跑 fake baseline。
- 缺資料時只建立 validator / 錯誤訊息 / `docs/research/DATA_REQUIREMENTS_PREV3Y.md`，並將狀態標記為 `BLOCKED_BY_DATA`。
- 2026-05-13 local check：三個 required inputs 皆存在且 schema pass；目前缺資料：none。

| 資料檢查狀態 | 意思 |
|---|---|
| `READY_TO_IMPLEMENT` | 資料存在，可以實作 TASK-001 |
| `BLOCKED_BY_DATA` | 缺資料，先不能回測 |
| `NEED_CLARIFICATION` | 有資料但 schema / 日期 / universe 規則不清楚 |

### 輸出檔案
- `outputs/backtests/prev3y_crypto/<YYYYMMDD>_baseline.csv`
  欄位：`date, portfolio_return, benchmark_return, gross_exposure, net_exposure, turnover, n_longs, n_shorts`
- `outputs/backtests/prev3y_crypto/<YYYYMMDD>_positions.parquet`
  欄位：`date, symbol, weight, signal_rank`
- `outputs/backtests/prev3y_crypto/<YYYYMMDD>_stats.json`
  欄位：`ir, sharpe, sortino, max_dd, calmar, turnover_annual, hit_rate, exposure_stats`
- `outputs/logs/prev3y_crypto/<YYYYMMDD>.log`

### 驗收標準
- [ ] 回測期間至少涵蓋 2019-01 ~ 最近一個完整月，且開頭明確標出 warm-up 起點。
- [ ] universe 為 point-in-time，**任何時點的 symbol 集合不得包含當天還未上市或已下市的幣**。
- [ ] 訊號使用 t–1 收盤之前的資料，t 收盤計算 weight，t+1 開盤（或 t+1 收盤，依 config）進場；不可有 `pct_change().shift(0)` 之類的對齊錯誤。
- [ ] CSV 每一列的時間戳唯一，無跳日（停盤日明確處理）。
- [ ] `stats.json` 的 IR / Sharpe 必須可由 CSV 重新計算重現（±1e-6）。
- [ ] log 開頭印出：random seed、config hash、data snapshot hash、git commit。

### 禁止修改範圍
- 不可動 `data/` 內既有 raw 檔（如已存在）。所有衍生資料寫在 `data/derived/` 或 `outputs/`。
- 不可在這支任務裡引入 cost、funding、slippage（那是 TASK-002）。
- 不可改 `configs/prev3y_crypto.yaml` 以外的設定檔。

### Codex 完成後請回報
- baseline 跑出來的 4 個關鍵數字：IR、Sharpe、max DD、年化 turnover。
- 你有沒有遇到「資料缺漏 / 異常值 / universe 不一致」的地方，列出清單。

### Codex 交付摘要（2026-05-13）
- 輸出：`outputs/backtests/prev3y_crypto/20260513_run002_baseline.csv`、`20260513_run002_positions.parquet`、`20260513_run002_stats.json`、`outputs/logs/prev3y_crypto/20260513_run002.log`。
- 關鍵數字：IR `-0.061757`、Sharpe `0.493574`、max DD `-19.4996%`、annual turnover `1.228343x`。
- 樣本：baseline CSV 覆蓋 `2019-01-01` 至 `2026-04-30`，warm-up `2018-01-01`；本地 Bybit price coverage 從 `2020-10-21` 開始，第一個有效持倉日為 `2024-04-01`。
- 可重現性：同一 config/data snapshot 內部重跑兩次，`stats.json` hash 皆為 `6dc6f39c5f5ed4c7d6ca2908c9cd0fa2fcb0c63cec8a6236003187495e59db60`。
- Benchmark：config 未指定 benchmark；本次使用同日 PIT universe 等權 long-only，缺 return 的 symbol 當日剔除。
- NOTE: data source = `data/trading.db` 的 `prices`、`crypto_market_cap_rankings`、`crypto_bybit_linear_instruments`；`quote_volume` 由 `close * volume` 衍生。
- NOTE: supplemental data gate 已落地；baseline runner 現在只驗證並讀取既有 parquet/config，缺資料時輸出 `BLOCKED_BY_DATA` 並停止。

### Claude 審查結論（2026-05-13，REVIEW-001）
- 結論：**CONDITIONAL_PASS**。詳見 `docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-001。
- 工程：7 條形式驗收全 PASS（時間對齊、PIT universe、可重現、無未來視）。
- 風險：實際有效樣本只有 2024-04-01 ~ 2026-04-30 共 760 天，**樣本太短，無法支撐「Prev3Y momentum 在 crypto 上 work 或不 work」之結論**。
- 風險：benchmark 為同日 PIT 等權 long-only，與 market-neutral 策略 beta-mismatch；headline IR −0.06 主要來自 benchmark 選錯。
- 風險：平均 tradable symbols 僅 15.2，遠低於 top_n+bottom_n=50；策略每月實際只跑 ~7×7 對，集中度風險偏高。
- **不允許 TASK-001 從 REVIEW 轉 DONE**，需先完成 TASK-001b / 001c / 001d 三張補件並重審。
- **TASK-002 / TASK-003 暫停**；TASK-004 / TASK-005 可平行進行（004 第一版可只放 baseline 雙口徑）。

---

## TASK-001b — Benchmark 重新定義（補件）

- **狀態**：DONE（Claude REVIEW-001b PASS，2026-05-13）
- **Owner**：Codex
- **預估**：S（0.5–1 天）
- **依賴**：直接接續 TASK-001；可與 001c、001d 平行

### 任務目的
為 Prev3Y baseline 提供合理 benchmark。當前同日 PIT 等權 long-only 與 market-neutral 策略 beta-mismatch，導致 IR 失真。

### 為什麼重要
若繼續以 long-only 為 benchmark，未來所有 IR 比較都會被偏壓；TASK-002 cost stress 的「IR 是否仍正」門檻無法正確套用。

### 輸入檔案
- `configs/prev3y_crypto.yaml`
- 既有的 prices_daily.parquet（取 BTC-USDT perp 價格）

### 輸出檔案
- `configs/prev3y_crypto.yaml` 新增區塊：
  ```yaml
  benchmark:
    primary: cash         # 三選一：cash / btc_perp / equal_weight_long_only
    btc_symbol: BYBIT:BTCUSDT.P
    alternatives:
      - btc_perp
      - equal_weight_long_only
  ```
- `outputs/backtests/prev3y_crypto/<YYYYMMDD>_baseline.csv` 新增欄位：`benchmark_cash_return, benchmark_btc_return, benchmark_eqw_return`（原 `benchmark_return` 等於 primary）。
- `stats.json` 新增：`ir_vs_cash_full/_active, ir_vs_btc_full/_active, ir_vs_equal_weight_full/_active`，並保留原 `ir`（= primary full alias）。

### 驗收標準
- [ ] 三個 IR 都產出且可由 CSV 重算重現（±1e-6）。
- [ ] log 註明 primary benchmark 為何、與 strategy beta 的不匹配風險如何被 caveat 標出。
- [ ] 不破壞舊 schema（CSV 是新增欄位，不改動現有欄位語意）。

### 禁止修改範圍
- 訊號邏輯、ranking、universe 一律不動。
- 不引入 cost / funding（仍是 TASK-002）。

### Codex 交付摘要（2026-05-13）
- 輸出：`outputs/backtests/prev3y_crypto/20260513_run004_baseline.csv`、`20260513_run004_positions.parquet`、`20260513_run004_stats.json`、`outputs/logs/prev3y_crypto/20260513_run004.log`。
- Primary benchmark：`cash`；`benchmark_return = benchmark_cash_return`。
- Benchmark 欄位：`benchmark_cash_return` 每日為 `0.0`；`benchmark_btc_return` 使用 `BYBIT:BTCUSDT.P` open-to-open return，缺資料保留 NaN；`benchmark_eqw_return` 等於 run003 舊版 equal_weight_long_only benchmark。
- IR 比較：`ir_vs_cash_full=0.493574`、`ir_vs_cash_active=0.926682`；`ir_vs_btc_full=-0.324759`、`ir_vs_btc_active=-0.017486`；`ir_vs_equal_weight_full=-0.061757`、`ir_vs_equal_weight_active=0.722657`。
- BTC coverage：`2021-03-03` 至 `2026-04-30`；full missing days `793`，active missing days `0`。
- Equal-weight coverage：avg symbols `76.748226`，min symbols `0`，missing days `660`。
- 驗證：run004 `positions.parquet` 與 run003 byte-identical；baseline 策略欄位 `date, portfolio_return, gross_exposure, net_exposure, turnover, n_longs, n_shorts` 與 run003 完全一致。
- 可重現性：同一 config/data snapshot 內部重跑兩次，`stats.json` hash 皆為 `03dbff25584de179478fcf626e5a6025366eaf3b1ac970b7e1f7715fc11396c4`。
- 驗證：`stats.json` 的 full / active benchmark IR 與既有績效欄位可由 `baseline.csv` 重算重現（max diff `1.60e-14`）。
- NOTE: 本補件只新增/更新 benchmark 相關欄位；未修改策略訊號、ranking、universe selection、missing-data 處理、cost/funding/slippage 或 raw data。

### Claude REVIEW-001b 結論（2026-05-13）
- 結論：**PASS**。詳見 `docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-001b。
- 重要發現：methodology 區塊（annualization=365.25、ddof=1、IR/Sortino 公式）一併補上，連帶滿足 REVIEW-001c 的 nice-to-have；6 個 IR 全部從 CSV 重算到 1e-14；positions 與 run003 byte-identical。
- **允許 TASK-001b 轉 DONE**；**允許 Codex 開始 TASK-001d**。
- **TASK-001 整體仍不可轉 DONE**：需等 TASK-001d 完成、做 `REVIEW-001_final` 通過後才能放行 TASK-002 / TASK-003。
- 下一輪請順手補的小事（不擋此次 PASS）：
  - stats.json 加 `ir_vs_btc_full_effective_days`（標示 BTC IR 實際覆蓋 1884 天而非 2677 天）。
  - stats.json 加 `benchmark_btc_first_return_date`（與 `benchmark_btc_start_date` 區隔語意）。
  - methodology 補 `equal_weight_empty_basket_policy: "fill 0 when no PIT members or no returns available"`。
  - TASK-001b 完成後 commit；下次 run 的 git_commit 應更新到新 commit hash。

---

## TASK-001c — 報表雙口徑（補件）

- **狀態**：DONE
- **Owner**：Codex
- **預估**：S（半天）
- **依賴**：可與 001b、001d 平行

### 任務目的
消除「全期口徑（2677 天）」與「有效持倉口徑（760 天）」的數字混淆，避免 headline 數字誤導後續決策。

### 為什麼重要
目前 stats.json 的 Sharpe 0.49、IR −0.06 都是全期口徑（包含 1917 個零部位天）。Claude 重算後有效口徑下 Sharpe ≈ 0.93、IR vs long-only ≈ +0.72。兩種口徑都不算錯，但拿錯口徑當門面會誤導 cost stress / attribution 的門檻決策。

### 輸入檔案
- TASK-001 既有輸出

### 輸出檔案
- `stats.json` 內所有效能指標一律輸出兩組：
  - `*_full`（2677 天，現行口徑）
  - `*_active`（gross_exposure > 0 的天數）
  - 涵蓋：`sharpe, sortino, ir_*, hit_rate, mean_daily_return, volatility, calmar`
- `log` 開頭新增：`effective_sample_start, effective_sample_end, effective_active_days, effective_active_fraction`

### 驗收標準
- [ ] 全期 / 有效 兩組指標都存在，命名一致（`*_full` / `*_active`）。
- [ ] 兩組數字可由 CSV 重新計算重現（±1e-6）。
- [ ] 舊欄位名（`sharpe`、`ir`、`max_dd`…）保留為 alias，指向 `*_full`，以維持向後相容；同時在 log 標示「primary 報表口徑建議使用 `*_active`」。

### 禁止修改範圍
- 不改 CSV / positions schema（只在 stats.json 與 log 加欄位）。
- 不重新計算 returns（只是換口徑彙總）。

### Codex 交付摘要（2026-05-13）
- 輸出：`outputs/backtests/prev3y_crypto/20260513_run003_baseline.csv`、`20260513_run003_positions.parquet`、`20260513_run003_stats.json`、`outputs/logs/prev3y_crypto/20260513_run003.log`。
- 報表口徑：`*_full` 使用完整 `2019-01-01` 至 `2026-04-30` 共 `2677` 天；`*_active` 使用 `gross_exposure > 0` 的 `2024-04-01` 至 `2026-04-30` 共 `760` 天。
- 舊欄位 alias：`ir`、`sharpe`、`sortino`、`max_dd`、`calmar`、`turnover_annual`、`hit_rate` 皆等於對應 `*_full`。
- 關鍵比較：`sharpe_full=0.493574`、`sharpe_active=0.926682`；`ir_full=-0.061757`、`ir_active=0.722657`。
- 可重現性：同一 config/data snapshot 內部重跑兩次，`stats.json` hash 皆為 `80042293bed7397d9ef8656b376beb66192fda79830baf527b38c96616c32602`。
- 驗證：`stats.json` 可由 `baseline.csv` 重算重現（±1e-6）；`baseline.csv` 與 `positions.parquet` 相較 `20260513_run002` 完全一致。
- NOTE: 本補件只改報表/統計/log，未修改策略訊號、ranking、universe selection、cost/funding/slippage、missing-data 處理或 raw data。
- Claude REVIEW-001c 結論：**PASS**，允許 TASK-001c 轉 `DONE`。
- Caveat: `hit_rate` 舊欄位在 run003 依規格改為 `hit_rate_full` alias；run002 的 `hit_rate` 實際為 active-only 計算，因此此欄位的數值從 `0.555263` 變為 `0.157639`。本差異為報表語意修正，不代表策略產出改變。
- NOTE: TASK-001 整體仍不可轉 `DONE`；需等 TASK-001b、TASK-001d 完成後做最終重審。

---

## TASK-001d — Missing-data 處理升級（補件）

- **狀態**：DONE（Claude REVIEW-001d PASS，2026-05-13）
- **Owner**：Codex
- **預估**：S–M（1 天）
- **依賴**：可與 001b、001c 平行

### 任務目的
把當前「missing return = 0」改成「symbol-day excluded from ranking & holding」，並抽成獨立 data-quality 模組。

### 為什麼重要
COMP-USD 在 2021-04..2022-01 有 205 列 missing OHLCV，目前以 return=0 處理。在本次回測中 COMP 從未進入持倉視窗，所以實際 P&L 影響 = 0。但若 lookback 視窗變動 / 之後做 attribution，這個處理會讓 COMP 的 3 年累積回報被低估其下行幅度，可能在 ranking 中被高估，是潛在埋雷。

### 輸入檔案
- 既有 prices_daily.parquet

### 輸出檔案
- 新模組（建議路徑）：`src/data_quality/missing.py`、`tests/data_quality/test_missing.py`
- 規則：對任一 symbol-day，若 `close <= 0` 或 OHLCV 缺列，該 symbol-day 從 universe 候選、ranking 候選、持倉候選中**全部移除**（不是 fill 0）。
- log 新增：每日被排除的 symbol 列表（壓縮輸出，例如 `excluded_today=[COMP-USD, ...]`）。
- 重跑一次 baseline，新 stats.json / positions / baseline 帶日期戳。

### 驗收標準
- [ ] 單元測試覆蓋 COMP-USD 與 ICP-USD fixture，明確驗證「異常日不進 universe」。
- [ ] 新跑的 positions.parquet 不應出現過去視為 missing→0 的 symbol-day。
- [ ] 與舊 baseline 的差異要寫進 log（差幾筆部位、有效持倉天數有無變化）。

### 禁止修改範圍
- 訊號計算、ranking 排序方法、backtester 引擎本身一律不動。
- 不可把 data-quality 規則寫進 signals/strategy 模組（必須在 data 層完成）。

### Codex 完成紀錄（2026-05-13）
- 輸出：`outputs/backtests/prev3y_crypto/20260513_run007_baseline.csv`、`20260513_run007_positions.parquet`、`20260513_run007_stats.json`、`outputs/logs/prev3y_crypto/20260513_run007.log`。
- Data-quality 輸出：`outputs/data_quality/prev3y_crypto/20260513_run007_data_quality_summary.csv`、`20260513_run007_data_quality_aggregate.json`。
- 新增模組 / 測試：`src/data_quality/missing.py`、`tests/data_quality/test_missing.py`。
- Policy：missing return 不補 0；nonpositive OHLC 不補值；不 forward fill price；volume <= 0 warning-only；missing volume / quote_volume hard exclusion。
- DQ 摘要：abnormal symbol-days `332`；holding exclusions `115`；ranking exclusions `0`；forced holding exits `0`；affected symbols `117`。
- COMP-USD / ICP-USD 已標記：COMP-USD `2021-04-17..2022-01-15`，ICP-USD `2021-05-10`，並包含 missing / nonpositive / warning-only events。
- run007 vs run004：portfolio_return、gross/net exposure、turnover、n_longs/n_shorts 全部逐列相同；positions.parquet SHA-256 也相同；active days 皆為 `760`。
- 驗證：`stats.json` 可由 `baseline.csv` 重算，最大差異 `1.60e-14`；兩次重跑 stats hash 相同 `10dfa956b795374dbb4d11c32b824d9c8750e69b2baec846b36716f664d58822`。
- NOTE: run005 / run006 是同日不覆寫規則下的中間驗證輸出；正式送審輸出為 run007。

### Claude REVIEW-001d 結論（2026-05-13）
- 結論：**PASS**。詳見 `docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-001d。
- 工程合格：模組設計乾淨（filtered views + events 雙產出）、policy 文件齊全（8 條 in stats.json）、單元測試核心路徑全綠、DQ summary CSV / aggregate JSON / stats.json 三者數字逐欄一致。
- 策略未動：baseline.csv 與 positions.parquet **byte-identical with run004**（SHA-256 相同），所有差異純粹是 DQ reporting 欄位。
- 「DQ 對最終績效零影響」的原因（不是 bug）：COMP-USD / ICP-USD 都不在 PIT 成員（PIT 全是 BYBIT perp 格式）；Bybit perp 的 1-event 多發生在 first-listing-day（2021 年），落在 2024-04+ 持倉視窗的 lookback 窗外。未來資料推進時 DQ 會自然啟動。
- **允許 TASK-001d 轉 DONE**；**允許 Claude 開 REVIEW-001_final**。
- REVIEW-001_final 之前建議補件（不擋此次 PASS）：
  - 單元測試補 (a) `exclude_from_ranking_candidate` 路徑、(b) `missing_price_row` 事件、(c) `aggregate_data_quality_events` 邊界三個 fixture-driven test。
  - 補 `ir_vs_btc_full_effective_days`（揭露 BTC IR 實際覆蓋 1884 天）。
  - 補 `benchmark_btc_first_return_date`（與 `benchmark_btc_start_date` 區隔）。
  - methodology 補 `equal_weight_empty_basket_policy`。
  - 把 TASK-001b / 001c / 001d 的變更整理 commit；下個 run 的 git_commit 應更新。

---

## TASK-001e - Final Review Readiness Patch

- **Status**: DONE（Claude REVIEW-001e PASS，2026-05-13）
- **Owner**: Codex
- **Date**: 2026-05-14
- **Dependency**: TASK-001b / TASK-001c / TASK-001d are DONE; TASK-001 remains REVIEW, not DONE.

### Goal
Close the small REVIEW-001d final-review gaps before `REVIEW-001_final`, without changing strategy behavior.

### Scope Completed
- Added fixture-driven coverage in `tests/data_quality/test_missing.py` for:
  - `exclude_from_ranking_candidate` when a hard abnormal price day appears inside the lookback window.
  - `missing_price_row` for a PIT member with no price bar.
  - `aggregate_data_quality_events` boundaries: empty events, warning-only, hard-only, and mixed actions.
- Added stats/log metadata:
  - `ir_vs_btc_full_effective_days = 1884`
  - `ir_vs_btc_active_effective_days = 760`
  - `benchmark_eqw_effective_days_full = 2017`
  - `benchmark_eqw_effective_days_active = 760`
- Clarified existing equal-weight empty-basket methodology text: dates with no PIT members or no available returns use `0.0` `benchmark_eqw_return`.
- Re-ran baseline as `20260513_run008`.

### Validation
- `python -m unittest tests.data_quality.test_missing` PASS: 5 tests.
- `python -m unittest discover -s tests` PASS: 5 tests.
- run008 outputs:
  - `outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv`
  - `outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet`
  - `outputs/backtests/prev3y_crypto/20260513_run008_stats.json`
  - `outputs/logs/prev3y_crypto/20260513_run008.log`
  - `outputs/data_quality/prev3y_crypto/20260513_run008_data_quality_summary.csv`
  - `outputs/data_quality/prev3y_crypto/20260513_run008_data_quality_aggregate.json`
- run008 vs run007: `portfolio_return`, exposure, turnover, long/short counts, and all benchmark columns max diff `0.0`.
- run008 vs run007: `positions.parquet` equal; pandas-object hash `3cf0e47169c56a0b29d73f05211b5b92be4e2df8cc0b1c7a36fa1b851e49cba8`.
- `stats.json` recomputed from run008 `baseline.csv`; max metric diff `1.07e-14`.
- Reproducibility hash: `ee8031732d1eda1406a9c10c57d11e49b6f54b3ac03c8e06fe84e63bbbe2a06f` in both repeat runs.

### Guardrails Confirmed
- No strategy signal changes.
- No ranking method changes.
- No universe selection changes.
- No benchmark return definition changes.
- No data-quality policy behavior changes.
- No cost / funding / slippage added.
- No raw data modified.
- TASK-001 remains REVIEW and must wait for `REVIEW-001_final`.
- TASK-002 / TASK-003 remain BLOCKED.

### Claude REVIEW-001e 結論（2026-05-13）
- 結論：**PASS**。詳見 `docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-001e。
- 強證據：baseline.csv / positions.parquet / DQ summary / DQ aggregate 四份檔案與 run007 **byte-identical**（SHA-256 全相同），證明只動報表 + 測試。
- 新 metadata 4 欄獨立驗算：`ir_vs_btc_full_effective_days=1884`、`ir_vs_btc_active_effective_days=760`、`benchmark_eqw_effective_days_full=2017`、`benchmark_eqw_effective_days_active=760` 全部可由 CSV 重算對到。
- 三個 REVIEW-001d 列的單元測試缺口（ranking exclusion / missing_price_row / aggregator 邊界）全部被新測試覆蓋；Read tool 直接驗證 Windows-side 5 test 完整存在。
- 環境註記（非 Codex 問題）：Linux mount 同步延遲 + stale pyc cache 讓本環境 `python -m unittest` 看不到新測試；Codex Windows 端自報 5 tests PASS，視為可信。建議下次把 unittest console output 一併貼進交付摘要。
- **允許 TASK-001e 轉 DONE**；**允許 Claude 開 REVIEW-001_final**。
- final review 通過後：TASK-001 整體轉 DONE，TASK-002 / TASK-003 解除 BLOCKED，SUMMARY.md 更新到最終態。

---

## TASK-002 — Funding / Cost Stress Test

- **狀態**：**TODO**（2026-05-13 由 REVIEW-001_final 解除 BLOCKED）
- **Owner**：Codex
- **預估**：M（2–3 天）
- **依賴**：TASK-001 已 DONE；input 用 `20260513_run008_*`
- **入場條件已達成**：active Sharpe = 0.9267 ≥ 0.7 ✓；active IR_vs_eqw = 0.7227 ≥ 0.3 ✓
- **必須繼承的 caveat / methodology**（見 SUMMARY.md 第 7 節 + REVIEW-001_final）：
  - 所有結論以 active 口徑（760 天）為主，full 口徑僅供 reference。
  - annualization=365.25、ddof=1、IR/Sortino 公式不可變更。
  - cost stress 自身的 fail gate：pessimistic 情境下若 active IR_vs_eqw < 0.3 標 WARNING；extreme 情境下 < 0 標 FAIL。
  - 不可動策略 / 訊號 / ranking / universe / data quality / benchmark 邏輯。

### 任務目的
在 TASK-001 baseline 之上，加入交易成本 / funding rate / 滑點，做多情境壓力測試，找出策略「在多悲觀的假設下還活著」的邊界。

### 為什麼重要
- Crypto perp 的 funding 在牛市末段可以年化吃掉幾十個百分點；只看 gross PnL 會嚴重高估策略。
- 真實上線前必須知道：在 fee × 2、funding × 1.5、滑點翻倍的情境下，IR 還剩多少。
- 這是區分「論文型 alpha」與「能上線的 alpha」的關鍵 gate。

### 輸入檔案（規劃路徑）
- TASK-001 的 `positions.parquet` 與 `baseline.csv`。
- `data/crypto/funding_rates.parquet`：欄位 `[timestamp, symbol, funding_rate, interval]`。
- `data/crypto/fees.yaml`：maker / taker fee，可分交易所。
- `configs/cost_stress.yaml`：定義 N 個情境（例如 base / pessimistic / extreme）。

### 輸出檔案
- `outputs/backtests/prev3y_crypto/<YYYYMMDD>_cost_stress.csv`
  欄位：`date, scenario, portfolio_return_gross, portfolio_return_net, fee_cost, funding_cost, slippage_cost`
- `outputs/backtests/prev3y_crypto/<YYYYMMDD>_cost_stress_summary.json`
  每個情境一組：`ir, sharpe, max_dd, annual_cost_bps_breakdown`
- `outputs/logs/prev3y_crypto/<YYYYMMDD>_cost_stress.log`

### 驗收標準
- [ ] 至少 3 個情境：`base`（實際 fee + 實際 funding）、`pessimistic`（fee × 2、funding × 1.5、滑點 × 2）、`extreme`（fee × 3、funding × 2、滑點 × 3）。
- [ ] funding 必須以 **持倉時間段內** 的 funding 結算次數加總，不能只取月末快照。
- [ ] fee 同時涵蓋進場與出場（包含 rebalance 中的雙邊）。
- [ ] 任一情境下若年化淨 IR < 0.3，必須在 summary 內顯眼標記 `WARNING`。
- [ ] `cost_stress.csv` 的 `portfolio_return_net = gross − fee − funding − slippage`，每列須能逐項對得回去。

### 禁止修改範圍
- 不可改動 TASK-001 產出的任何檔案。
- 不可動策略訊號邏輯（這支任務只加 cost layer）。
- 不可把 cost model 寫死進 strategy module，要獨立成 `costs/` 模組。

---

## TASK-003 — Baseline Attribution

- **狀態**：**TODO**（2026-05-13 由 REVIEW-001_final 解除 BLOCKED）
- **Owner**：Codex
- **預估**：S–M（1–2 天）
- **依賴**：TASK-001 已 DONE；input 用 `20260513_run008_*`；TASK-002 可平行
- **開工前先確認**：`data/crypto/factor_returns.parquet` 是否存在且 schema 正確（含 `market, size, liquidity, momentum_short`）。若缺資料，先進 BLOCKED_BY_DATA / NEED_CLARIFICATION，由 Claude / Rick 決定下一步。
- **必須繼承的 methodology**：annualization=365.25、ddof=1；regression 採 rolling + full-sample 雙產出。

### 任務目的
把 TASK-001 baseline 的 PnL 拆解成幾個解釋來源：market beta、size / liquidity factor、sector（如有）、idiosyncratic。輸出標準格式的 attribution 表。

### 為什麼重要
- 沒有 attribution 就無法判斷「這是真 alpha 還是隱性 beta」。
- 之後若 Claude 在審查中懷疑「策略只是長期 long BTC」，可以用這份表直接證偽 / 證實。
- Attribution 是和 ChatGPT 討論方向時最有用的素材。

### 輸入檔案（規劃路徑）
- TASK-001 的 `positions.parquet`、`baseline.csv`。
- `data/crypto/factor_returns.parquet`：欄位 `[date, factor_name, return]`，至少含 `market, size, liquidity, momentum_short`。

### 輸出檔案
- `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution.csv`
  欄位：`date, total_return, market_contrib, size_contrib, liquidity_contrib, mom_short_contrib, residual`
- `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_summary.json`
  欄位：`r2, avg_beta_market, avg_beta_size, ..., residual_sharpe`
- `outputs/logs/prev3y_crypto/<YYYYMMDD>_attribution.log`

### 驗收標準
- [ ] 對 daily portfolio return 做 rolling regression（window 至少 90 天）以及 full-sample regression，兩份都產出。
- [ ] `total_return = sum(*_contrib) + residual`，每列誤差 < 1e-8。
- [ ] residual 不可顯示出明顯季節 / 月份 pattern（若有，log 警告）。
- [ ] regression 樣本內 R² 在 summary.json 明確記錄。
- [ ] 若 market beta 的 t-stat > 5 且持續存在，標 `WARNING: high market beta — alpha 可能不純`。

### 禁止修改範圍
- 不可改 TASK-001、TASK-002 的輸出。
- 不可把 factor 計算寫進策略模組（attribution 屬於分析層，不是策略層）。

---

## TASK-004 — Quant Cowork Lab Dashboard

- **狀態**：TODO
- **Owner**：Codex
- **預估**：M（3–4 天）
- **依賴**：TASK-001 通過後可開始；TASK-002 / 003 結果出來後再加面板

### 任務目的
建一個輕量化 web dashboard，集中顯示目前各策略的 baseline 績效、cost 情境、attribution、近期變化，作為 Rick 每日早上的「Cowork Lab 首頁」。

### 為什麼重要
- 目前所有結果都散在 CSV / parquet，每次要看都要手動跑 notebook。
- 有了 dashboard，Rick 一眼能看出「昨天 funding 突然惡化」「最近殘差變大」等異常。
- 也讓 Claude 在審查時可以直接從同一個介面截圖貼回 review。

### 輸入檔案（規劃路徑）
- TASK-001 / 002 / 003 的所有輸出檔。
- `configs/dashboard.yaml`：顯示哪些策略、哪些情境、要不要顯示 attribution 面板。

### 輸出檔案
- `apps/dashboard/`（新模組）：含 `app.py`、`components/`、`README.md`。
  建議用 Streamlit 或 FastAPI + 靜態 HTML；不要用重量級框架。
- `outputs/dashboard/screenshots/<YYYYMMDD>_home.png`（Codex 跑一次本機並截圖貼回 review）。

### 驗收標準
- [ ] 啟動命令一行：`make dashboard` 或 `python -m apps.dashboard`。
- [ ] 首頁四個區塊：(a) baseline 績效、(b) cost stress 情境比較、(c) attribution、(d) 最近 30 天每日 PnL。
- [ ] 讀資料時帶 cache，並在頁面顯示「資料 snapshot 時間」。
- [ ] 不直接重新跑回測——只讀 CSV / parquet。
- [ ] 切換策略 / 情境的下拉選單可運作。
- [ ] README 寫明 dependency、本機跑法、與 VPS 上跑的差異。

### 禁止修改範圍
- 不可在 dashboard 內計算新策略指標（只顯示既有產出）。
- 不可把 dashboard 模組和策略模組互相 import（單向：dashboard 依賴 outputs，不依賴 strategies code）。
- 不可加任何會寫入 `outputs/` 的功能（dashboard 是唯讀的）。

---

## TASK-005 — VPS Bot Monitor

- **狀態**：TODO
- **Owner**：Codex
- **預估**：M（3–5 天）
- **依賴**：可獨立進行；之後會和 Ollama 串接做 log 摘要

### 任務目的
為跑在 VPS 上的 trading bot 建一個監控層：心跳檢查、最近一次下單時間、PnL daily delta、錯誤 log 收集，並在出狀況時推播通知。

### 為什麼重要
- 真錢上線後，最致命的不是策略爛，而是「bot 掛了沒人知道」「API key 失效」「斷網 6 小時」。
- 監控層必須在策略還沒上線前就準備好；事後補做容易留洞。
- 之後 Ollama 可以幫忙摘要每天的 log，讓 Rick 不用每天看一萬行。

### 輸入檔案（規劃路徑）
- VPS 上 bot 寫出的 log：`/var/log/quantbot/*.log`（或同等路徑）。
- 交易所 API 帳號（**只讀 key**，禁止使用可下單的 key 做監控）。
- `configs/monitor.yaml`：心跳 interval、告警閾值、通知 channel。

### 輸出檔案
- `apps/monitor/`：含 `monitor.py`、`alerts.py`、`README.md`。
- `outputs/monitor/heartbeat.parquet`：欄位 `[timestamp, bot_id, status, latency_ms, last_order_time, equity, notes]`。
- `outputs/monitor/alerts/<YYYYMMDD>.jsonl`：每筆告警一行。

### 驗收標準
- [ ] 心跳檢查 ≥ 每 1 分鐘一次，連續 3 次失敗觸發 `CRITICAL` 告警。
- [ ] 偵測「最近 N 分鐘無下單但應有下單」的情境（N 由 config 決定）。
- [ ] 通知至少支援 1 個 channel（Telegram / Discord / Email 擇一），可擴充。
- [ ] 任何告警都有 dedupe（同類問題 30 分鐘內不重複通知）。
- [ ] 不會記錄完整 API key、不會把使用者帳號明碼寫入 log。
- [ ] README 列出：所需權限、failure mode、如何手動關閉。

### 禁止修改範圍
- 不可讓 monitor 取得 **可下單 key**（只准用 read-only / IP-whitelisted key）。
- 不可改 bot 本身的下單邏輯（monitor 是旁觀者）。
- 不可把 monitor 直接寫進策略 repo 的核心模組，獨立成 `apps/monitor/`。

---

## 補充：未進 queue 的想法（暫存區）

> Claude 暫存，等 Rick 點頭再轉成正式任務卡。

- TASK-? 多 universe 比較（spot vs perp、tier1 vs tier2）。
- TASK-? 因子腐化（factor decay）追蹤儀表。
- TASK-? 把 Notion 研究紀錄自動回灌 repo 的 docs。
- TASK-? Walk-forward / purged k-fold 框架。
