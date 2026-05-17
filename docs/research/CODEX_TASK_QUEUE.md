# Codex Task Queue

最後更新：2026-05-14
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

- **狀態**：**DONE**（Claude REVIEW-001_final PASS，2026-05-14）
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

- **Status**: DONE（Claude REVIEW-001e PASS，2026-05-14）
- **Owner**: Codex
- **Date**: 2026-05-14
- **Dependency**: TASK-001b / TASK-001c / TASK-001d are DONE; TASK-001e is now archived into final TASK-001 closure.

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
- TASK-001 is now DONE after `REVIEW-001_final`.
- TASK-002 / TASK-003 are now TODO, but were not run during TASK-001e.

### Claude REVIEW-001e 結論（2026-05-14）
- 結論：**PASS**。詳見 `docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-001e。
- 強證據：baseline.csv / positions.parquet / DQ summary / DQ aggregate 四份檔案與 run007 **byte-identical**（SHA-256 全相同），證明只動報表 + 測試。
- 新 metadata 4 欄獨立驗算：`ir_vs_btc_full_effective_days=1884`、`ir_vs_btc_active_effective_days=760`、`benchmark_eqw_effective_days_full=2017`、`benchmark_eqw_effective_days_active=760` 全部可由 CSV 重算對到。
- 三個 REVIEW-001d 列的單元測試缺口（ranking exclusion / missing_price_row / aggregator 邊界）全部被新測試覆蓋；Read tool 直接驗證 Windows-side 5 test 完整存在。
- 環境註記（非 Codex 問題）：Linux mount 同步延遲 + stale pyc cache 讓本環境 `python -m unittest` 看不到新測試；Codex Windows 端自報 5 tests PASS，視為可信。建議下次把 unittest console output 一併貼進交付摘要。
- **允許 TASK-001e 轉 DONE**；**允許 Claude 開 REVIEW-001_final**。
- final review 已通過：TASK-001 整體轉 DONE，TASK-002 / TASK-003 解除 BLOCKED 並轉 TODO。

---

## TASK-001f - Final Cleanup / Archive Patch

- **Status**: DONE
- **Owner**: Codex
- **Date**: 2026-05-14

### Scope Completed
- Archived TASK-001 final state in `docs/research/TASK_001_PREV3Y_BASELINE_SUMMARY.md`.
- Added final NOTE lines to `docs/research/codex_workorders/TASK-001_prev3y_crypto_baseline.md`.
- Added cache ignore rules to `.gitignore`.
- Added `docs/research/TASK_001_FINAL_CLEANUP_REPORT.md`.

### Guardrails Confirmed
- No strategy program changes.
- No backtest logic changes.
- No new experiments.
- TASK-002 / TASK-003 were not run.
- run008 outputs and raw data were not modified.
- No stage / commit was performed for TASK-001f.

---

## TASK-002a — Cost / Funding Input Builder

- **狀態**：**DONE**（Claude REVIEW-002a_phase2_full PASS，2026-05-14）
- **最終正式輸出**：`data/crypto/funding_rates.parquet`（750,641 列、273 symbols、active period 2024-04-01 ~ 2026-04-30、無 proxy）
- **子狀態**：
  - Phase 1（scaffolding + smoke）：DONE
  - Phase 2 dry-run（4 symbols × 7 days）：DONE
  - Phase 2 full fetch（273 symbols × 760 days）：**DONE**（Claude REVIEW-002a_phase2_full PASS）
- **重大發現（影響 TASK-002）**：Bybit funding 是 **1h / 4h / 8h 混合 interval**（1 symbol / 145 symbols / 127 symbols），非統一 8h。詳見 REVIEW-002a_phase2_full 第 3 節 5 項必改清單。
- **Owner**：Codex
- **預估**：S–M（Phase 1 已落地；Phase 2 預估 1 天視 API rate-limit / 273 symbol 抓取狀況）
- **工單**：`docs/research/codex_workorders/TASK-002a_cost_funding_inputs.md`（可整份貼給 Codex）；Phase 2 額外規則見 `CLAUDE_REVIEW_LOG.md` → REVIEW-002a_phase1 第 4 節
- **依賴**：TASK-001 已 DONE；run008 三件套作為 read-only 輸入

### 任務目的
建立 TASK-002 所需的 3 個輸入檔案（`data/crypto/funding_rates.parquet`、`data/crypto/fees.yaml`、`configs/cost_stress.yaml`），但**不執行**任何 cost stress 計算。解除 TASK-002 的 `BLOCKED_BY_INPUTS`。

### 為什麼重要
- TASK-002 readiness check 已標記為 `BLOCKED_BY_INPUTS`：缺 funding_rates / fees / cost_stress 三個輸入。
- 真實 funding 是 TASK-002 fail gate 結論的核心；若用平均化 / 模擬 funding，整份 stress test 報廢。
- Symbol mapping（`BYBIT:XXXUSDT.P` ↔ `XXXUSDT`）容易出錯，必須在這一步寫成獨立函式 + 單元測試。

### 主要輸出
- `data/crypto/funding_rates.parquet`（7 欄；含 `is_proxy` / `source` 兩個關鍵欄）
- `data/crypto/fees.yaml`（單一 fee tier；含取數日期 / 來源 / fee rebate 處理）
- `configs/cost_stress.yaml`（**12 個 scenario 名稱與工單一字不差**）
- `outputs/data_quality/funding_coverage/<YYYYMMDD>_funding_coverage_{report.csv,summary.json}`
- `src/costs/symbol_mapping.py` + `tests/cost_inputs/test_symbol_mapping.py`

### 驗收門檻摘要
- Active period（2024-04-01 ~ 2026-04-30）real coverage ≥ 80%（低於門檻 → 必須 `PROXY_ONLY` 或 `BLOCKED_BY_DATA`）。
- funding_rate 為小數（非百分比）；interval_hours 為 8（或交易所實際 interval）。
- symbol 一律 `BYBIT:XXXUSDT.P` 格式，與 run008 positions 對齊。
- 缺資料的 symbol-day **不出現** 在 parquet 內（不 fill 0），由 coverage report 紀錄。
- 任何 proxy 列 `is_proxy=True` 並標 source；TASK-002 fail gate 須排除 proxy 列。
- Symbol mapping 單元測試覆蓋 `1000PEPE` / `RLUSDUSDT` 等邊界 case。

### 禁止修改範圍
- 不可動 run008 任何檔案。
- 不可執行 TASK-002 stress（這是下一棒）。
- 不可改 strategy / signals / universe / DQ / benchmark / backtester。
- 不可用平均 funding / 隨機 funding 當**正式**資料。
- 不可在沒有 Claude REVIEW-002a 通過前 merge 回 main。

### NOTE
- 完成後 Codex 回報 7 件事（狀態、覆蓋率、來源、symbol mapping 邊界、proxy 使用、檔案位置、未做）。
- Claude 開 REVIEW-002a 審查；REVIEW-002a PASS 後 TASK-002 才可重做 readiness check。

### Phase 1 交付摘要（2026-05-14）
- 新增 `src/costs/symbol_mapping.py` 與 `tests/cost_inputs/test_symbol_mapping.py`（7 tests PASS）。
- 建立 `data/crypto/fees.yaml`（Bybit VIP 0 / Non-VIP；maker 2.0 bps、taker 5.5 bps；含取數日期 / URL / tier / 無 rebate）。
- 建立 `configs/cost_stress.yaml`（12 scenarios 完整，名稱與工單一字不差，defaults 6 欄齊備）。
- Bybit public funding API smoke check OK。
- `outputs/data_quality/funding_coverage/20260514_funding_coverage_{report.csv, summary.json}` 已建立，明確標示 funding_rates.parquet 尚未存在、real coverage 0.0%、missing = 29586 symbol-days。
- **未交付**：`data/crypto/funding_rates.parquet` 仍不存在；coverage 0%；TASK-002 仍 BLOCKED_BY_TASK_002A。
- Claude REVIEW-002a_phase1 結論：**PASS**（Phase 1 範圍合格）。詳見 `CLAUDE_REVIEW_LOG.md` → REVIEW-002a_phase1。

### Phase 2 範圍（Codex 接下來執行）
- 抓 Bybit public funding history API 對 run008 PIT universe 273 個 symbol、active period 2024-04-01 ~ 2026-04-30 全部 8h funding 結算。
- 寫進 `data/crypto/funding_rates.parquet`（7 欄 schema，見原工單第 7 節）。
- 重做 `funding_coverage_report.csv` / `funding_coverage_summary.json`；report 帶三個獨立 coverage 欄位（real / proxy / total）。
- 若 real coverage < 80%，依工單第 10 節決策樹啟動 `proxy_universe_median`（優先）或 `proxy_zero`（只能在無同類可參考時用）。
- 完成後 Claude 開 REVIEW-002a_phase2_full；通過後 TASK-002a 才轉 DONE，TASK-002 才可解除 BLOCK。

### Phase 2 dry-run 交付摘要（2026-05-14）
- 範圍：4 symbols（BTCUSDT / ETHUSDT / ADAUSDT / BCHUSDT）× 7 天（2024-04-01 ~ 2024-04-07 UTC）。
- 產出（**非正式**，在 `outputs/data_quality/funding_coverage/`）：parquet 84 列 / 21 列/symbol；schema 7 欄完全合規；timestamp 為 8h 結算（hours={0,8,16}）；funding_rate abs max = 0.00075（小數單位 PASS）；mapping 273/273；live diff max_abs_diff = 0；API 10 calls / 8 cache hits / 0 retry / 0 error。
- 命名修正：summary 採 `phase_status: READY_TO_REVIEW_PHASE2_DRYRUN`，並有 `formal_funding_rates_written: false`。
- Claude REVIEW-002a_phase2_dryrun 結論：**PASS**（dry-run 範圍合格、允許進 controlled full fetch）。詳見 `CLAUDE_REVIEW_LOG.md` → REVIEW-002a_phase2_dryrun。

### Phase 2 full fetch 必守 12 條限制（詳見 LOG 第 3 節）
1. 範圍：273 symbols × 760 days；正式輸出 `data/crypto/funding_rates.parquet`。
2. 不可覆蓋 dry-run 路徑，dry-run 不當正式 input。
3. Raw API cache 到 `data/cache/funding/bybit_raw/<symbol>_<pageN>.json`。
4. Coverage gate：active PIT real ≥ 80% → PHASE2_READY；50–80% → PHASE2_PROXY_ONLY（須 Rick 同意）；< 50% → PHASE2_BLOCKED_BY_DATA。
5. Sanity 抽查擴大到 **30 筆**（跨 2024/2025/2026 各年至少 5 筆）live diff < 1e-9。
6. 任一 funding_rate `abs > 0.01` 在 coverage report 與 summary `outlier_funding_rates` 列出（標記、不修正）。
7. 連續性檢查：> 24h funding 間隙在 coverage report 列出（symbol / from_ts / to_ts / gap_hours）。
8. Idempotency：full fetch 完整跑兩次，第二次完全使用 raw cache（API request count = 0），兩次 parquet SHA-256 必須相同。
9. 缺資料 symbol-day **不出現** 在 parquet 內；proxy 順序：`proxy_universe_median` → `proxy_zero`；`proxy_zero` 涉及的 symbol-day 在 NOTE 區單獨列出。
10. summary.json `phase_status` 終態三選一（PHASE2_READY / PHASE2_PROXY_ONLY / PHASE2_BLOCKED_BY_DATA）+ top-level `task_002a_overall_status: COMPLETE / INCOMPLETE` 二選一。
11. log 印 `bybit_api_calls_made / errors / pages_fetched / first_response_at / last_response_at / cache_hit_count / total_request_seconds`。
12. 禁止項：不可動 run008、不可改 strategy/signals/DQ/benchmark/backtester、不可執行 TASK-002 stress、不可在 active period 外多抓（buffer 同 dry-run）、未過 REVIEW-002a_phase2_full 不可 merge main。

---

## TASK-002 — Funding / Cost Stress Test

- **狀態**：**REVIEW**（2026-05-15 Codex v2 implementation complete；等待 REVIEW-002）
- **Readiness Check 結論（2026-05-15，Claude Sonnet）**：13/15 通過。唯一阻塞點：`configs/cost_stress.yaml` defaults 仍為 v1（`funding_application` 舊值 + 缺 3 個 v2 policy key）。詳見 `CLAUDE_REVIEW_LOG.md` → READINESS-002。
- **Codex 解除阻塞動作（只需 1 次 commit）**：
  ```yaml
  # configs/cost_stress.yaml defaults 區塊改為：
  defaults:
    annualization_factor: 365.25
    std_ddof: 1
    slippage_application: "per_turnover_one_side_bps"
    fee_application: "per_turnover_both_sides"
    funding_application: "pit_per_interval_settlement_accumulated"   # v1→v2 必改
    funding_proxy_policy: "exclude_from_fail_gate"
    funding_interval_policy: "use_interval_hours_per_row"            # v2 新增
    funding_gap_policy: "mark_funding_gap_true_no_fill"               # v2 新增
    outlier_policy: "report_no_clamp"                                  # v2 新增
  ```
- **此 commit 完成後：TASK-002 直接進入 READY_TO_IMPLEMENT，可開始實作 cost stress**。
- **Opus REVIEW-002 結論（2026-05-15，第二輪）**：**`PASS`** —— TASK-002 → DONE。詳見 `CLAUDE_REVIEW_LOG.md` → REVIEW-002（Opus 2026-05-15 第二輪）。
- **狀態**：**DONE**（2026-05-15，Opus PASS；最終交付 = `20260515_cost_stress_*`；fail gates 全過、v2 兩條新 WARNING 全未觸發）。
- **核心數字（active 口徑）**：realistic Sharpe `0.892` / IR_eqw `+0.717` / max DD `−19.64%` / alpha decay `0.81%`；worst_case Sharpe `0.840` / IR_eqw `+0.708` / max DD `−19.80%` / alpha decay `2.04%`。
- **核心發現**：cost rank = **slippage > fee > funding**（推翻事前對 funding 主導的假設）。
- **策略判定**：**保留**（從 REVIEW-001_final 的「需要更多測試」升級）。
- **工單**：`docs/research/codex_workorders/TASK-002_cost_funding_slippage_stress.md`（**v2** — 已修正 funding 固定 8h 假設、改為 per-interval；含 v2 change log）
- **下一個 Codex 動作**：對工單 v2 重新跑 readiness check，產出 `READY_TO_IMPLEMENT` / `BLOCKED_BY_DATA` / `NEED_CLARIFICATION` 三選一。
- **解除 BLOCK 條件**（v2 readiness check 細則）：
  - 驗證 `data/crypto/funding_rates.parquet` 存在 + schema 7 欄 + `is_proxy` 全 False + `source` 全 `bybit_api` + `interval_hours ∈ {1, 4, 8}`。
  - 驗證 `data/crypto/fees.yaml` 與 `configs/cost_stress.yaml` 存在；後者 `defaults.funding_application` 必須是 `pit_per_interval_settlement_accumulated`（若仍是 v1 的 `pit_8h_settlement_accumulated`，須在 readiness check 階段一併 commit 更新後再判斷狀態）。
  - 驗證 run008 三件套唯讀就位。
- **狀態演進**：TODO → BLOCKED_BY_INPUTS → BLOCKED_BY_TASK_002A → BLOCKED_BY_WORKORDER_UPDATE → READY_FOR_READINESS_RECHECK_AGAINST_V2 → **NEED_CLARIFICATION**（2026-05-15 Readiness Check 完成，data PASS，cost_stress.yaml v1 config 待更新）。
- **funding_rates.parquet 已就位** ✓（無 proxy、coverage 97–99%、live diff = 0）；TASK-002 開工只剩 Codex 對 v2 跑 readiness check 與後續 stress 計算。
- **v2 新增的 5 項規則**（Codex 開工前務必讀工單第 v2 Change Log 與 § 8 / § 11 / § 12 / § 14）：
  1. 全面 per-interval funding 累加（依 `interval_hours`，不再硬寫 8h）。
  2. Known funding gap 7 symbols（XTZ / FLOW / LPT / AXS / RVN / INJ / CTC）標 `funding_gap=True`、不 fill。
  3. Outlier（abs ≥ 0.01，max abs = 0.05）照實累加 + 三 combo 情境 outlier 貢獻拆解。
  4. 新增兩條 WARNING gate（funding gap > 5% / outlier contribution > 30%）。
  5. Codex 完成回報從 7 件擴為 9 件（新增 v2 per-interval audit + interval_distribution_used）。
- **Codex v2 交付摘要（2026-05-15）**：
  - 新增 v2 cost layer：`src/costs/config.py`、`turnover.py`、`fees.py`、`slippage.py`、`funding.py`、`engine.py`、`metrics.py`、`reporting.py`、`reproducibility.py`。
  - 新增正式 runner：`scripts/task002_cost_stress_v2.py`；未使用舊 `scripts/crypto_cost_stress.py` 或 `output/crypto_cost_stress.csv`。
  - 官方輸出：`outputs/backtests/prev3y_crypto/20260515_cost_stress.csv`、`20260515_cost_stress_summary.json`、`20260515_cost_stress_positions_cost.parquet`、`outputs/logs/prev3y_crypto/20260515_cost_stress.log`。
  - no-cost sanity gate：`no_cost_baseline_max_diff_vs_run008 = 0.0`；daily net identity max diff `2.00e-16`；12 scenarios 各 2,677 列。
  - Result verdict in summary: `PASS`; failures `[]`; warnings `[]`.
  - Funding diagnostics：known-gap symbol-days `343`（`1.1593%` active positions）；outliers `653` total rows / `23` held rows；max abs funding rate `0.05`; outlier contribution pct `2.5748%`。
  - Reproducibility：同 config/data/output-date 重跑兩次 hash 一致，`55c651476c0641cda80200b12209b9f95bcf43536dd8f883404ce3414844654d`。
  - 未修改 run008、funding_rates.parquet、strategy/signals/ranking/universe/data-quality/backtest engine。
- **Owner**：Codex
- **預估**：M（2–3 天）
- **工單**：`docs/research/codex_workorders/TASK-002_cost_funding_slippage_stress.md`（可整份貼給 Codex）
- **依賴**：TASK-001 已 DONE + **TASK-002a REVIEW-002a PASS**
- **解除 BLOCK 條件**：TASK-002a 三個輸出檔（funding_rates.parquet、fees.yaml、cost_stress.yaml）存在 + Claude REVIEW-002a 結論為 PASS（real coverage ≥ 80% 或 PROXY_ONLY 經 Rick 同意）後，Codex 才可重做 TASK-002 readiness check（READY_TO_IMPLEMENT / BLOCKED_BY_DATA / NEED_CLARIFICATION）。
- **入場條件已達成（研究面）**：active Sharpe = 0.9267 ≥ 0.7 ✓；active IR_vs_eqw = 0.7227 ≥ 0.3 ✓
- **必須繼承的 caveat / methodology**（見 SUMMARY.md 第 7 節 + REVIEW-001_final）：
  - 所有結論以 active 口徑（760 天）為主，full 口徑僅供 reference。
  - annualization=365.25、ddof=1、IR/Sortino 公式不可變更。
  - cost stress 自身的 fail gate：見工單第 12 節（realistic_combo active Sharpe < 0.5 → FAIL；realistic_combo IR_vs_eqw < 0.2 → FAIL；conservative_combo IR_vs_eqw < 0 → FAIL）。
  - 不可動策略 / 訊號 / ranking / universe / data quality / benchmark 邏輯。
  - **proxy funding 列必須從 fail gate 排除**（cost_stress.yaml defaults 已規範 `funding_proxy_policy: exclude_from_fail_gate`）。

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

- **狀態**：**DONE**（2026-05-15 Opus REVIEW-003 = CONDITIONAL_PASS）
- **REVIEW 結論**：詳見 `CLAUDE_REVIEW_LOG.md` → REVIEW-003（Opus 2026-05-15）。**4 條 fail gates 全 PASS、reproducibility hash 一致、對帳機器精度**；4 條 warning（含 Opus 採工單公式後新觸發的 top5=95.56% 與 DOT=25.45%）、2 條結構性發現（long-side net −5.1%、2025 占 89%）一併記錄為 caveat。
- **核心數字**：gross 29.58% / net 28.53% / short net +33.65% / long net −5.10% / cost drag 1.05% / slippage > fee > funding。
- **策略 narrative 更新**：**short-driven crypto alpha + long-side 結構性虧損**（不是對稱多空）。
- **Codex 必補（不擋 DONE）**：(a) 下版 attribution 對 concentration 並列輸出兩個分母（`/net_alpha_total` 與 `/sum_abs_net`）；(b) 補 `long_side_drag` warning gate；(c) 自動產出 review packet（per Token Budget Rule）。
- **Owner**：Codex
- **預估**：M（2–3 天）
- **依賴**：TASK-001 已 DONE；TASK-002 已 DONE；input 用 `20260513_run008_*` + `20260515_cost_stress_*`
- **完整工單**：`docs/research/codex_workorders/TASK-003_baseline_attribution.md`（v1.0，2026-05-15，可整份貼給 Codex）
- **必須繼承的 methodology**：annualization=365.25、ddof=1；active period = gross_exposure > 0，共 760 天（2024-04-01 ~ 2026-04-30）
- **Opus REVIEW-002 指派的 attribution 重點問題**：
  1. 7 個 funding gap symbols（XTZ/FLOW/LPT/AXS/RVN/INJ/CTC）是否貢獻不成比例的 alpha？若是，paper trading 規劃需要 size cap。
  2. alpha 是否集中在 8h interval 大幣（持倉 interval 分布 1:5.4 偏 8h，vs 全集 1:1.9）？
  3. 在 net-of-cost（realistic_combo）口徑下，symbol-level attribution 排名與 gross 排名是否一致？

### 任務目的
拆解 run008 baseline 與 20260515 cost stress 後的 net-of-cost alpha 來源，確認策略是否由少數 symbol / 特定年份 / 特定 side / 特定 funding interval / 特定資料缺口 symbol 主導，輸出可重現的 attribution report。

### 為什麼重要
- 沒有 attribution 就無法判斷「alpha 是否穩健且分散」；TASK-002 只確認成本未殺死策略，但未回答集中度問題。
- Funding gap 7 symbols 以 cost=0 計入，attribution 可量化此效應是否造成結果失真。
- Attribution 是與 ChatGPT 討論下一步（paper trading 規劃 / 策略修改）時最核心的素材。

### 輸入檔案（read-only，不可修改）
- `outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv`
- `outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet`
- `outputs/backtests/prev3y_crypto/20260515_cost_stress.csv`（主口徑：`realistic_combo`）
- `outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet`
- `data/crypto/funding_rates.parquet`（interval_hours 分組用）

### 輸出檔案（寫入 `outputs/attribution/prev3y_crypto/`）
- `<YYYYMMDD>_attribution_by_symbol.csv`
- `<YYYYMMDD>_attribution_by_year.csv`
- `<YYYYMMDD>_attribution_by_month.csv`
- `<YYYYMMDD>_attribution_by_side.csv`
- `<YYYYMMDD>_attribution_by_funding_gap.csv`
- `<YYYYMMDD>_attribution_by_interval.csv`
- `<YYYYMMDD>_attribution_by_cost_type.csv`
- `<YYYYMMDD>_attribution_top_contributors.csv`
- `<YYYYMMDD>_attribution_drawdown.csv`
- `<YYYYMMDD>_attribution_summary.json`（含 warning_gates 觸發狀態）
- `outputs/logs/prev3y_crypto/<YYYYMMDD>_attribution.log`

### Warning Gates（觸發後標記 WARNING，不強制停止）
- Top 5 symbols 合計貢獻 > 60% net alpha
- 任一 symbol 單獨貢獻 > 25% net alpha
- Funding gap 7 symbols 合計貢獻 > 20% net alpha
- 任一年貢獻 > 70% net alpha
- Short side net alpha 為負且 abs(short) > 50% × gross combined
- 任一 symbol gross 排名 vs net 排名相差 > 10 名

### 禁止修改範圍
- **不可修改**：run008 任何輸出、20260515 任何輸出、data/ 目錄、策略程式、configs/
- **不可執行**：任何 baseline runner、任何 cost stress runner
- **不可使用**：舊輸出 `output/crypto_cost_stress.csv`
- **不可自行轉 DONE**：完成後改狀態為 `REVIEW`，等 Claude 審查後才轉 DONE

---

## TASK-004 — Quant Cowork Lab Dashboard

- **狀態**：**READY_TO_IMPLEMENT**（2026-05-15 由 Opus REVIEW-002 PASS 解鎖；可與 TASK-003 平行）
- **Owner**：Codex
- **預估**：M（3–4 天）
- **依賴**：TASK-001 ✓ DONE；TASK-002 ✓ DONE；TASK-003 結果出來後再加 attribution 面板
- **v1 範圍（即刻可做）**：baseline 雙口徑 + 三 benchmark IR + 12 個 cost stress scenarios 比較表 + 最近 30 天每日 PnL
- **v2 範圍（TASK-003 完成後加）**：attribution 面板

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

- **狀態**：**DONE**（Claude REVIEW-005 PASS，2026-05-17；詳見 `CLAUDE_REVIEW_LOG.md` → REVIEW-005）
- **Paper trading 執行前置條件（TASK-005 部分）**：TASK-005 DONE ✅；但 VPS 實際上線 + TASK-005a Real Alert Channel 完成後才算「monitor online」（見 TASK-005a）
- **Owner**：Codex
- **預估**：M（3–5 天）
- **依賴**：可獨立進行；之後會和 Ollama 串接做 log 摘要；**為 paper trading 預先建好監控基建**

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

### Codex implementation output（2026-05-17）
- `apps/monitor/` 已建立為 observer-only monitoring / logging / alerting package。
- `scripts/task005_vps_bot_monitor.py` 已建立；產出 local sample outputs，不連 exchange、不要求 API key、不啟動 paper/live。
- Safe config：`configs/monitor.yaml`；secret patterns 已加入 `.gitignore`，未建立 `configs/monitor_secrets.yaml`。
- Sample outputs：
  - `outputs/monitor/prev3y_crypto/20260517_heartbeat.parquet`
  - `outputs/monitor/prev3y_crypto/alerts/20260517.jsonl`
  - `outputs/logs/prev3y_crypto/20260517_monitor_setup.log`
  - `docs/research/review_packets/REVIEW-005_PACKET.md`
  - `docs/research/review_packets/REVIEW-005_NUMBERS.json`
- Gate status：safety_scan PASS；heartbeat schema PASS；alerts schema PASS；secret_in_vcs false；order_submission_code_present false；monitor_auto_restart_present false。
- Reproducibility hash：`25cbf9c172b7bf377974e0fd1d568d57a888c8b090c25049f460b3c2ca42a606`。
- Paper execution remains FORBIDDEN；Live trading remains FORBIDDEN。

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

## TASK-005a — Real Alert Channel（Telegram / Discord / SMTP）

- **狀態**：**REVIEW**（Codex implementation complete，待 Claude/Rick review；未標 DONE）
- **Owner**：Codex
- **預估**：S（0.5–1 天）
- **依賴**：TASK-005 ✓ DONE；真實 Telegram Bot token 或 Discord Webhook URL 只可由 VPS env 或 ignored local config 提供，Codex 不要求貼到聊天
- **觸發原因**：REVIEW-005 PASS caveat — `single_channel_only` warning。Codex implementation 已加入 Telegram / Discord channel，待 review。

### 任務目的

在 TASK-005 建好的 `apps/monitor/` 基礎上，接通至少 1 個真實推播 channel（Telegram 優先，Discord Webhook / SMTP 備用），使 CRITICAL / WARNING 告警能在 bot 出狀況時即時送達 Rick。

### 範圍

- 修改 `configs/monitor.yaml`：`channels` 新增 `telegram` / `discord`，安全預設維持 `dry_run: true`；VPS 實際啟用需由 operator 明確調整。
- 實作 `apps/monitor/alerts.py` 對應 channel dispatch（若尚未實作）。
- 確認 `configs/monitor_secrets.yaml` 仍在 `.gitignore`，secret 由環境變數或 ignored local config 提供。
- 在 `tests/monitor/` 補充對應 channel mock test。

### Codex implementation output（2026-05-17）

- `apps/monitor/channels/` 已新增：`base.py`、`local_jsonl.py`、`telegram.py`、`discord.py`、`secrets.py`、`redaction.py`。
- `configs/monitor.yaml` 已保留 `local_jsonl`，並加入 `telegram` / `discord` channels，全部維持 `dry_run: true` 安全預設。
- `configs/monitor_secrets.example.yaml` 已新增為空值範本；未建立 `configs/monitor_secrets.local.yaml`，未寫入任何真實 secret。
- `tests/monitor/test_channels.py` 已新增，所有 Telegram / Discord send path 均使用 mock HTTP client。
- Review outputs：
  - `docs/research/review_packets/REVIEW-005a_PACKET.md`
  - `docs/research/review_packets/REVIEW-005a_NUMBERS.json`
  - `outputs/logs/prev3y_crypto/20260517_task005a_alert_channel.log`
- Gate status：`REVIEW_READY`；safety_scan PASS；`local_jsonl_retained=true`；`external_post_attempted=false`；paper/live execution remains FORBIDDEN。
- Reproducibility hash：`06a28f791dbfeb931a35dadf1eb856f92c791d0bf8648b09ba004da5b8d58817`。

### 禁止

- 不可使用可下單 API key。
- 不可修改任何策略程式或官方研究輸出。
- 不可啟動 paper execution 或 live trading。

### 完成條件

- `configs/monitor.yaml` 有至少 1 個可 mock / 可啟用的真實 channel，且預設 `dry_run: true`。
- mock test 通過（不需要真實 token 才能跑 CI）。
- README 更新 channel 設定說明。
- TASK-005a DONE 後，才滿足「TASK-005 VPS monitor online」的 paper execution 前置條件。

### ⚠️ Paper Execution Gate

**TASK-005a 是 paper execution 的前置條件之一**（除非 Rick 明示豁免）。
Paper execution 前置條件完整清單：
- TASK-007b DONE ✅（2026-05-17）
- TASK-005 DONE ✅（2026-05-17）+ TASK-005a REVIEW（未 DONE）
- TASK-006 三個補件落地 ✅（2026-05-17）
- 30 天 forward paper record（Sharpe > 0.5）— NOT_STARTED
- Opus REVIEW-006b PASS — 未開啟
- Rick 明示批准 — 未批准

---

## TASK-006 — Paper Trading Plan（**規劃，非執行**）

- **狀態**：**DONE**（Opus REVIEW-006 PASS，2026-05-16；詳見 `CLAUDE_REVIEW_LOG.md` → REVIEW-006）
- **Paper trading 執行**：**仍 FORBIDDEN**，需 5 條件齊備：(a) TASK-007b 完成、(b) TASK-008 完成或 Rick 豁免、(c) 30 天 forward 實盤 paper record（Sharpe > 0.5）、(d) Opus REVIEW-006b PASS、(e) Rick 明示批准。
- **核心發現（Opus 裁定）**：
  - 9/9 安全項全 PASS；safety_scan PASS / violations [] / real_order_submission_possible = false。
  - 3 條 mandatory overlay rule 在 2026-04-01 數值驗算通過（long 50%、symbol cap 2% < 5%、net 3.47e-17）。
  - reproducibility hash 與 TASK-007 hash 交叉對齊。
  - **proxy Sharpe −2.9012 不是策略崩潰訊號**：30-day annualized noise + 已標 `validation_basis = proxy_not_forward_execution`；歷史 NAV 仍 +30.7%。
  - **STOP_PAPER_PENDING_REVIEW 自觸發是設計成功的證據**：證明風控正確攔截自己。
- **Codex 補件（2026-05-17 已落地；不代表 REVIEW-006b PASS）**：
  1. `proxy_sharpe_long_window` 已寫入 `forward_validation.json`：30-day proxy = -2.9012、90-day proxy = 1.1681、full active 760-day proxy = 0.8037。
  2. `fill_definition` 已寫入 review packet / monthly review / numbers，並在 `apps/paper_trading/README.md` 加註「fill = position delta vs prior period」。
  3. `monthly_review.json` 已加 `funding_filter_active_this_month=false` 與 regime-dependent note。
- **REVIEW-006b 啟動時機**：TASK-007b 完成 + 30-day forward paper record 存在 + 上面 3 個補件落地；補件已完成，但 REVIEW-006b 仍不可由 Codex 自行標 PASS。
- **Owner**：Claude / Rick（規劃工單）→ Codex（後續實作 monitor 整合）
- **預估**：S（0.5–1 天寫工單）
- **依賴**：TASK-002 ✓ DONE；TASK-003 必須 PASS 後才可進「執行」階段
- **範圍邊界**：
  - **本任務只是「寫工單 + 確認規則」**——不可啟動任何 paper trading。
  - paper 執行前需：(a) TASK-003 attribution PASS、(b) TASK-005 VPS monitor 上線、(c) Opus 對 paper plan 做最終 review。
- **工單必須涵蓋**：
  1. 資金大小（建議從 USD 10k–50k demo 帳戶）
  2. Execution venue（Bybit perp）與 maker / taker preference
  3. 停損規則（active max DD 觸發機制、kill switch）
  4. Reporting cadence（每日 / 每週 PnL、attribution 對齊）
  5. Paper-forward sample 最少 30 天才能稱為 forward-validated
  6. 任何違反 TASK-002 caveats（不擊敗 BTC、funding gap、760 天樣本）的執行情境必須有對應的 risk-off 動作
- **REVIEW-003 新增的 3 條 mandatory caveat（2026-05-15 由 Opus 加入，必加進 paper trading 規劃工單）**：
  1. **Position size cap**：單一 symbol 上限不超過總 NAV 的 **5%**（理由：DOT 在 attribution 內貢獻 25.45% net alpha，paper 不能讓單一 symbol 部位這麼集中）。
  2. **Long-side allocation cap**：多頭部位上限不超過 gross exposure 的 **50%**（理由：long-side net −5.1%、被 funding contango 吞噬）。
  3. **High-funding-cost symbol filter**：對最近 30 天平均 funding rate > 0.03% 的 symbol，若被 momentum 訊號排進多頭，**降低 50% 權重** 或 **剔除**（針對 BTC/ETH/LINK 這類 contango 結構性受害者）。

- **REVIEW-007 進一步確認（2026-05-16 由 Opus）**：上面 3 條 caveat **同時施加** 即為 `combined_paper_safe_variant` —— 該 variant 已驗證可同時達到 long_net 轉正（+4.21%）、single_conc < 25%（19.73%）、Sharpe ≥ 0.7（0.80）、max DD < 1.5× baseline。**TASK-006 工單採此為 primary spec**，`high_funding_cost_filter`（Sharpe 0.96）為 secondary / sensitivity spec。
- **TASK-006 工單可立即開始寫**（不必等 TASK-007b/007c/008），但 paper 執行需要 TASK-007b 完成 + 30 天 forward + Opus 另一輪 review。
- **與 live trading 的關係**：paper 完成 30+ 天 forward-validated + 通過 Opus 最終 review 才可考慮 live；現階段**live trading 維持禁止**。

### Codex implementation output（2026-05-16）
- `apps/paper_trading/` created for offline planning / simulation / logging only.
- Required outputs generated under `outputs/paper_trading/prev3y_crypto/` with output date `20260516`.
- `docs/research/review_packets/REVIEW-006_PACKET.md` and `REVIEW-006_NUMBERS.json` generated for review.
- Safety scan PASS: no exchange client, credential intake, or external execution path implemented.
- Paper execution remains blocked until TASK-007b PASS, TASK-005 VPS monitor online, REVIEW-006b PASS, 30 days forward validation, and Rick approval.
- Live trading remains FORBIDDEN.

---

## TASK-007 — Long-side Variant Study（**REVIEW-003 follow-up**，2026-05-15 新增）

- **狀態**：**DONE**（Opus REVIEW-007 = CONDITIONAL_PASS，2026-05-16；詳見 `CLAUDE_REVIEW_LOG.md` → REVIEW-007）
- **核心結論**：(a) **不要砍多頭**（short_only Sharpe 0.40 / DD −49.18%）；(b) `high_funding_cost_filter` 是 Pareto-dominant 變體（Sharpe 0.96 / alpha retention 109.6%）；(c) `combined_paper_safe_variant` 唯一同時達到 long_net 轉正（+4.21%）、single_conc < 25%（19.73%）、Sharpe ≥ 0.7（0.80）。**集中度根源 = 高 funding 大幣 + 過度集中；overlay 無法根治**（no_DOT 悖論 top5 升至 116.13% → TASK-008）。
- **Opus 指派 3 個 follow-up（不擋本次 DONE）**：
  - **TASK-007b**：weight cap + redistribution（cap 20%/15%/10%）—— paper 執行前須完成
  - **TASK-007c**：Variant C 0.01%/8h + 0.005%/8h-discount-0.5 規格 —— sensitivity
  - **TASK-008**：策略層 per-symbol weight cap —— concentration 結構性根治
- **TASK-006 paper trading primary spec = `combined_paper_safe_variant`、secondary = `high_funding_cost_filter`**。
- **Owner**：Claude（寫工單）→ Codex（後續實作）
- **預估**：M（2–3 天，視 variant 數量）
- **依賴**：TASK-001 ✓ DONE；TASK-002 ✓ DONE；TASK-003 ✓ DONE；input 用 `20260513_run008_*` + `20260515_cost_stress_*` + `20260515_attribution_*`

### 任務目的
回答 REVIEW-003 Q2：「Prev3Y crypto 多頭是否該砍？」研究三個 variant 並比較對 active Sharpe / IR_vs_eqw / max DD 的影響：

| Variant | 內容 |
|---|---|
| A. Short-only | 完全砍掉多頭部位，純空頭策略；對比 baseline 的市場暴險變化 |
| B. Long funding-discount filter | 對最近 30 天平均 funding rate > 0.03% 的 symbol，若進多頭則降權或剔除 |
| C. Long size cap | 多頭 gross 上限為 total gross 的 50% |

### 為什麼重要
REVIEW-003 揭露 **long-side net −5.1%、short 貢獻 117.9% 的 net alpha**。BTC / ETH / LINK 因 funding contango 在多頭 net 翻負。若 variant 結果優於 baseline，paper trading 規劃應採用 variant；若劣於 baseline，則 long-side 是必要對沖、cap 設計需細修。

### 輸入檔案
- run008 三件套
- 20260515 cost stress 三件套
- 20260515 attribution 全套
- `data/crypto/funding_rates.parquet`（用於 funding-discount filter）

### 輸出檔案
- `outputs/long_side_variants/<YYYYMMDD>_variant_A_short_only_summary.json`
- `outputs/long_side_variants/<YYYYMMDD>_variant_B_funding_filter_summary.json`
- `outputs/long_side_variants/<YYYYMMDD>_variant_C_long_cap_summary.json`
- `outputs/long_side_variants/<YYYYMMDD>_variants_comparison.csv`（三 variant + baseline 並列）
- `outputs/logs/prev3y_crypto/<YYYYMMDD>_long_side_variants.log`
- Review packet：`docs/research/review_packets/REVIEW-007_PACKET.md`（per Token Budget Rule）

### 禁止修改範圍
- 不可改 baseline / cost stress 既有產出
- 不可動策略訊號的核心 ranking 邏輯（variant 只是 post-processing 過濾 / 砍多頭）
- 不可改 universe / DQ / benchmark
- 不可在 Opus REVIEW-007 通過前 merge 回 main

### 完成後回報
- 三個 variant 對 baseline 的 4 個關鍵數字（active Sharpe / IR_vs_eqw / max DD / alpha decay）
- 哪個 variant 最佳？是否值得作為 paper trading 候選？

### Codex 實作回報（2026-05-15）
- 輸出：
  - `outputs/variants/prev3y_crypto/20260515_task007_variant_daily.csv`
  - `outputs/variants/prev3y_crypto/20260515_task007_variant_summary.csv`
  - `outputs/variants/prev3y_crypto/20260515_task007_variant_summary.json`
  - `outputs/variants/prev3y_crypto/20260515_task007_variant_concentration.csv`
  - `outputs/variants/prev3y_crypto/20260515_task007_variant_cost_breakdown.csv`
  - `outputs/logs/prev3y_crypto/20260515_task007_variant_study.log`
  - `docs/research/review_packets/REVIEW-007_PACKET.md`
  - `docs/research/review_packets/REVIEW-007_NUMBERS.json`
- Baseline reconciliation：`baseline_current_long_short` vs TASK-002 `realistic_combo` net return max diff `2.05e-16`，PASS。
- Best Sharpe overlay：`high_funding_cost_filter`，Sharpe `0.9586`，IR_vs_eqw `0.7282`，max DD `-20.27%`，net alpha `31.27%`。
- Warning gates triggered：`short_only_rescaled_max_dd_worse_than_baseline_1p5x`、`long_only_rescaled_net_alpha_negative`、`top5_concentration_remains_above_60pct`、`single_symbol_concentration_remains_above_25pct`。
- Reproducibility hash：`824ff334e30810aeeaef8a06319a9ac8563b61f903835c89ae6cfbd9e140066f`。
- Note：所有結果都是 post-processing overlay study，不是新策略 backtest，不代表 paper/live trading approval。

---

## TASK-007b — Weight Cap + Redistribution（REVIEW-007 Q1 follow-up，2026-05-16 新增）

- **狀態**：**DONE**（Claude REVIEW-007b PASS，2026-05-17）
- **Paper trading hard gate（TASK-007b 條件）**：**已滿足**（B-1 = 選項 A）
- **研究結論**：weight-based overlay cap + redistribution **無法降低集中度**；此路徑正式關閉；集中度根治需 TASK-008（alpha-space / 策略層）
- **Owner**：Codex
- **預估**：S（0.5–1 天）
- **依賴**：TASK-007 ✓ DONE；input 用 TASK-007 既有 baseline + run008 positions
- **目的**：補齊工單原規格的 weight-cap + redistribution 設計（cap=20%、15%、10%），與 TASK-007 的 alpha-based selection（top5_cap_5pct / DOT_capped / no_DOT）對比。
- **核心規則**：
  - 對每日每 symbol 計算 `|weight| / gross_exposure` 占比。
  - 超過 cap 的部分**等比例補回同方向（long↔long、short↔short）其他 symbol**（redistribution），不是直接砍掉。
  - cap 三檔：20% / 15% / 10%。
- **輸出**：3 個 variant summary（同 TASK-007 schema）+ NUMBERS.json 補充 + log。
- **驗收**：cap=15% 的 top5 concentration 是否 < 70%（工單 gate `concentration_not_reduced` 的反向驗證）；cap=10% 的 Sharpe 是否跌 < 30%（gate `cap10_sharpe_drop`）。
- **禁止**：不動策略訊號、不重跑 baseline / cost stress / attribution；只做 overlay。

### Codex implementation output（2026-05-16）
- Added `src/variants/task007b.py` and `scripts/task007b_weight_cap_redistribution.py`.
- Official outputs generated:
  - `outputs/variants/prev3y_crypto/20260516_task007b_cap_daily.csv`
  - `outputs/variants/prev3y_crypto/20260516_task007b_cap_summary.csv`
  - `outputs/variants/prev3y_crypto/20260516_task007b_cap_summary.json`
  - `outputs/variants/prev3y_crypto/20260516_task007b_redistribution_log.csv`
  - `outputs/variants/prev3y_crypto/20260516_task007b_gate_report.json`
  - `outputs/logs/prev3y_crypto/20260516_task007b_weight_cap_redistribution.log`
  - `docs/research/review_packets/REVIEW-007b_PACKET.md`
  - `docs/research/review_packets/REVIEW-007b_NUMBERS.json`
- Validation: `python scripts\task007b_weight_cap_redistribution.py --output-date 20260516` returned `REVIEW_READY`; `python -m py_compile src\variants\task007b.py scripts\task007b_weight_cap_redistribution.py` PASS.
- Fail gates all PASS: baseline reconciliation max diff `2.05e-16`, missing outputs false, schema mismatch false, redistribution overflow false, paper/live execution code false.
- Key numbers: cap20 and cap15 are no-op vs baseline; cap10 Sharpe `0.8341`, net alpha `26.36%`, alpha retention `92.38%`, top5 concentration `98.69%`, single-symbol concentration `24.81%`, max DD `-19.64%`.
- Redistribution: cap10 has `61` breach dates / `488` no-room rows; same-side redistribution had no eligible room, so gross exposure was reduced per workorder edge-case policy.
- Warnings triggered: `concentration_not_reduced_cap15`, `top5_concentration_above_threshold`, `single_symbol_concentration_above_threshold`, `redistribution_has_no_room`. `cap10_sharpe_drop` did not trigger (`6.48%` drop vs `30%` threshold).
- Reproducibility hash: `f5c962e11189cc4f91dedbc50b00456830d1fdc6e868c1638ad6b3e3e4db07b7`.
- This remains a post-processing overlay study only; paper trading and live trading remain FORBIDDEN.

---

## TASK-007c — Variant C Spec Compliance（REVIEW-007 Q2 follow-up，2026-05-16 新增）

- **狀態**：**TODO**（Opus 指派；sensitivity，與 TASK-007b 平行）
- **Owner**：Codex
- **預估**：S（半天）
- **目的**：補齊工單原規格的兩個 Variant C 門檻：
  - C1：threshold 0.01%/8h（=0.0001 decimal）、discount 0（完全排除）
  - C2：threshold 0.005%/8h（=0.00005 decimal）、discount 0.5（部分打折）
- **與既有 high_funding_cost_filter（0.03%/8h）並列輸出**，做 sensitivity 比較表。
- **輸出**：2 個 variant summary + 三 threshold（0.03 / 0.01 / 0.005-discount-0.5）比較表。
- **禁止**：不重跑 baseline / cost stress / attribution；不改 funding_rates.parquet；只 overlay。

---

## TASK-008 — Strategy-Layer Per-Symbol Weight Cap（REVIEW-007 結構性發現 follow-up，2026-05-16 新增）

- **狀態**：**TODO**（Opus 指派；長期任務、不擋短期 paper 規劃）
- **Alpha-space 範圍確認（REVIEW-007b，2026-05-17）**：TASK-007b 量化驗證 weight-based overlay 無法解決集中度問題（路徑已關閉）。TASK-008 **必須在 alpha-space / 策略層實作**，不可再嘗試 overlay 或 weight-space 設計。
- **Owner**：Claude（寫工單）→ Codex（後續實作）
- **預估**：M（3–5 天，包含 backtest 重跑）
- **目的**：解決 REVIEW-007 揭露的「集中度結構性問題」—— `no_DOT` 悖論顯示 overlay 移除最大貢獻者反使 top5 concentration 升到 116.13%，證明 overlay 無法根治集中度。TASK-007b 進一步確認：即使加入 redistribution，weight-based cap 仍失敗。需要**在策略層（ranking / position sizing layer）加 per-symbol weight cap**。
- **核心規則**：
  - 在 baseline backtester 的 `signals / position sizing` 層加 `max_per_symbol_weight = 0.05`（5%，與 paper trading mandatory caveat 對齊）。
  - 不是 overlay，是策略訊號的一部分；新跑 baseline、cost stress、attribution 全部用新規則。
  - 對比 run008（無 cap）的所有 Key Numbers。
- **預期效果（Opus 假設，需 Codex 驗證）**：
  - top5_conc 應顯著降低（因為 DOT 等大貢獻者被天然 cap）。
  - net alpha 可能略降（DOT 空頭 alpha 被 cap），但 single_conc 應穩定 < 25%。
- **與 TASK-006 paper trading 的關係**：TASK-008 完成後產出的新 baseline 是**正式 paper 上線版本**；TASK-006 第一版用 `combined_paper_safe_variant` 是「等 TASK-008 期間的近似」。
- **禁止**：在 TASK-008 完成前不可上 paper trading；不可在沒有 Opus REVIEW-008 通過下宣稱 baseline 已更新。

---

## 補充：未進 queue 的想法（暫存區）

> Claude 暫存，等 Rick 點頭再轉成正式任務卡。

- TASK-? 多 universe 比較（spot vs perp、tier1 vs tier2）。
- TASK-? 因子腐化（factor decay）追蹤儀表。
- TASK-? 把 Notion 研究紀錄自動回灌 repo 的 docs。
- TASK-? Walk-forward / purged k-fold 框架。
