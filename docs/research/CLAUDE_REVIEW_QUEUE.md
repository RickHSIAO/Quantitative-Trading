# Claude Review Queue

最後更新：2026-05-12
維護者：Claude
狀態圖例：`WAITING_INPUT`（等 Codex 產出） / `IN_REVIEW` / `PASS` / `CONDITIONAL_PASS` / `FAIL` / `BLOCKED`

> **給 Rick 的閱讀指引**
> 1. 每張卡的「審查重點」是 Claude 會逐條檢查的清單，不是建議。
> 2. 結論一律落在 `PASS / CONDITIONAL_PASS / FAIL` 三選一，並附理由。
> 3. `CONDITIONAL_PASS` 代表「結果大致可信，但有需要 Codex 補的事」，補完才轉 `PASS`。
> 4. Claude 不會直接改 Codex 的程式，只會把問題寫成新的 TASK 進 `CODEX_TASK_QUEUE.md`。

---

## REVIEW-001_final — TASK-001 整體最終總審（2026-05-13）

- **狀態**：**`PASS`**
- **TASK-001 整體狀態**：**DONE**（最終正式 baseline = `20260513_run008`）
- **TASK-002 / TASK-003 狀態**：**TODO**（BLOCKED 已解除）
- **研究判定**：**需要更多測試**（保留路線、進入 cost stress；不淘汰、不立即上線）
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-001_final
- **核心數字（active 口徑）**：Sharpe `0.9267`、IR_vs_cash `0.9267`、IR_vs_btc `-0.0175`、IR_vs_eqw `+0.7227`、max DD `-19.50%`、有效持倉 760 天
- **下一張工單**：把 TASK-002 簡述展開成可直接貼給 Codex 的工單（仿 `codex_workorders/TASK-001_*.md`）

---

## REVIEW-001 — Prev3Y Crypto Universe Baseline

- **狀態**：`CONDITIONAL_PASS`（2026-05-13）→ 後續由 b/c/d/e + REVIEW-001_final 全部 PASS 後，TASK-001 整體 DONE
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-001
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-001
- **審查產物**：
  - `outputs/backtests/prev3y_crypto/20260513_run002_baseline.csv`
  - `outputs/backtests/prev3y_crypto/20260513_run002_positions.parquet`
  - `outputs/backtests/prev3y_crypto/20260513_run002_stats.json`
  - `outputs/logs/prev3y_crypto/20260513_run002.log`
- **一句話結論**：所有 7 條形式驗收都過；但有效樣本只有 2024-04 起的 ~25 個月，benchmark 為 long-only equal-weight 與 market-neutral 策略 beta-mismatch，headline Sharpe 0.49 / IR −0.06 屬全期口徑、會誤導。需先做 TASK-001b/c/d 補件後再評估 TASK-002。

### 審查重點

**A. 未來視 / 資料對齊**
- [ ] 訊號計算用到的最後一筆資料時點 ≤ 交易決策時點。
- [ ] universe membership 是 point-in-time，不是「現在還活著」的清單反推。
- [ ] 沒有用到 next-day open 之類在訊號時點還拿不到的價格。
- [ ] resample / forward-fill 沒有把未來價格灌進 t–1。

**B. Survivorship / 退市偏誤**
- [ ] 已退市 / 下架的幣是否仍在歷史 universe 中（應該要在）。
- [ ] 跌到歸零的幣是否被當成「資料缺失」直接踢掉（不應該）。

**C. 過擬合風險**
- [ ] 參數（lookback、top-N、rebalance freq）是否被多次調整以最佳化 IR？看 git history 與 config diff。
- [ ] 是否有「樣本內 vs 樣本外」分割？若無，需補。
- [ ] IR / Sharpe 是否高得不真實（> 3）？高得不真實的數字十次有九次是 bug。

**D. 統計可重現**
- [ ] 從 CSV 重新算 IR / Sharpe / max DD 是否與 `stats.json` 一致（±1e-6）。
- [ ] random seed、config hash、data snapshot hash 是否寫進 log。

**E. 經濟合理性**
- [ ] turnover 是否在合理範圍（年化幾百％ 對 momentum 算正常；幾千％ 就要解釋）。
- [ ] 多空 exposure 與設計一致（market-neutral 還是 long-bias）。
- [ ] 最大回撤的時間點是否對得上已知市場事件（如 2020-03、2022-05 LUNA、2022-11 FTX）。

### 預設輸出
- `docs/research/prev3y_crypto/<YYYYMMDD>_review.md`：Pass/Cond/Fail + 證據 + 建議下一步。
- 若 `FAIL`：把需要修的事寫進 `CODEX_TASK_QUEUE.md` 對應任務的補丁卡。

---

## REVIEW-001b — TASK-001b Benchmark 重新定義

- **狀態**：`PASS`（2026-05-13）— 允許 TASK-001b 轉 DONE；允許開始 TASK-001d
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-001b
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-001b
- **審查產物**：
  - `outputs/backtests/prev3y_crypto/20260513_run004_baseline.csv`
  - `outputs/backtests/prev3y_crypto/20260513_run004_positions.parquet`
  - `outputs/backtests/prev3y_crypto/20260513_run004_stats.json`
  - `outputs/logs/prev3y_crypto/20260513_run004.log`
  - `src/reporting/prev3y_benchmarks.py`、`configs/prev3y_crypto.yaml`
- **一句話結論**：三 benchmark 與三組 IR 全部齊備、可由 CSV 重算到 1e-14；methodology 區塊把 REVIEW-001c 的 nice-to-have 補完；positions 與 run003 byte-identical 證明策略未動。**TASK-001 整體仍待 TASK-001d 完成後做 REVIEW-001_final**。

### 審查重點

- [x] `benchmark_return` 等於 `benchmark_cash_return`；primary 為 `cash` 在 stats/log/config 都明示。
- [x] `benchmark_eqw_return` 等於 run003 舊版 equal_weight_long_only benchmark（active 期內值一致）。
- [x] `benchmark_btc_return` 使用 `BYBIT:BTCUSDT.P`；缺資料保持 NaN；active 期內 missing=0，並有 RuntimeError 防呆。
- [x] 6 個 IR（`ir_vs_cash / ir_vs_btc / ir_vs_equal_weight` × `_full / _active`）都存在，CSV 重算最大誤差 1.07e-14。
- [x] BTC active missing=0；full missing=793 已記錄。
- [x] equal-weight coverage：avg 76.75、min 0、missing 660 已記錄。
- [x] `positions.parquet` 與 run003 byte-identical（SHA-256 一致）；baseline 策略欄位逐值相等。
- [x] 未動策略訊號、ranking、universe、missing-data、cost/funding。

### Caveat（不擋 PASS）

- `ir / sharpe` alias 值因 primary 改為 cash 而從 run003 的 `-0.06 / 0.49` 變成 `0.49 / 0.49`（兩者現在數學上相等）；下游請統一改用 `ir_vs_<bench>_<window>` 顯式欄位。
- `ir_vs_btc_full` 實際只覆蓋 1884 天（BTC available 子集），不是完整 2677 天；建議在 stats.json 補 `ir_vs_btc_full_effective_days`。
- `benchmark_btc_start_date=2021-03-03` 是第一筆 BTC 價格日；CSV 第一筆非 NaN return 是 2021-03-04（open-to-open 滯後）；建議補 `benchmark_btc_first_return_date`。
- eqw 在 universe 全空日 fill 0（非 NaN），methodology 未明示此 day-level policy（symbol-level policy 已寫）。對 active IR 無影響。

---

## REVIEW-001c — TASK-001c 報表雙口徑

- **狀態**：`PASS`（2026-05-13）— 允許 TASK-001c 轉 DONE
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-001c
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-001c
- **審查產物**：
  - `outputs/backtests/prev3y_crypto/20260513_run003_baseline.csv`
  - `outputs/backtests/prev3y_crypto/20260513_run003_positions.parquet`
  - `outputs/backtests/prev3y_crypto/20260513_run003_stats.json`
  - `outputs/logs/prev3y_crypto/20260513_run003.log`
- **一句話結論**：雙口徑指標齊備；baseline.csv 與 positions.parquet 與 run002 byte-identical（證明未動策略）；reproducibility hash 一致；log 已明確標示 alias 是 full-period、建議用 `*_active`。**TASK-001 整體仍不可轉 DONE**，需等 TASK-001b、TASK-001d 完成後做最終重審。

### 審查重點

- [x] `stats.json` 同時存在 `*_full` 與 `*_active` 指標，且舊欄位 `ir`、`sharpe`、`sortino`、`max_dd`、`calmar`、`turnover_annual`、`hit_rate` 為 full alias。
- [x] active period 定義為 `gross_exposure > 0`，有效期間為 `2024-04-01` 至 `2026-04-30`，共 `760` 天。
- [x] full / active 指標可由 `baseline.csv` 重算重現（Codex self-check 1.6e-14；Claude 獨立重算 ~1e-4 量級差距，差距來源為公式約定差異而非 bug）。
- [x] `baseline.csv` 與 `positions.parquet` schema 未改、且 SHA-256 與 run002 完全一致。
- [x] log 開頭標明 `effective_sample_start / _end / _active_days / _active_fraction`。
- [x] 未修改策略訊號、ranking、universe selection、cost/funding/slippage 或 missing-data 處理。

### Caveat（不擋 PASS，列入下一輪修飾）

- `hit_rate` alias 值在 run002 → run003 之間發生階躍（0.5553 → 0.1576），因為 run002 的 `hit_rate` 實為 active-only 計算、run003 alias 改為指 full。**Codex 已在 log 第 19 行明確警告 alias 是 full-period 且建議用 `*_active`**，下游請統一改用 `hit_rate_active`。
- 建議在最終重審前補一份 `methodology` 區塊（`annualization_factor`、`std_ddof`、`sortino_formula`），讓第三方可獨立重算到 1e-6。

---

## REVIEW-001d — TASK-001d Missing-data 處理升級

- **狀態**：`PASS`（2026-05-13）— 允許 TASK-001d 轉 DONE；允許開 REVIEW-001_final
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-001d
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-001d
- **審查產物**：
  - `outputs/backtests/prev3y_crypto/20260513_run007_baseline.csv`
  - `outputs/backtests/prev3y_crypto/20260513_run007_positions.parquet`
  - `outputs/backtests/prev3y_crypto/20260513_run007_stats.json`
  - `outputs/logs/prev3y_crypto/20260513_run007.log`
  - `outputs/data_quality/prev3y_crypto/20260513_run007_data_quality_summary.csv`
  - `outputs/data_quality/prev3y_crypto/20260513_run007_data_quality_aggregate.json`
  - `src/data_quality/missing.py`、`tests/data_quality/test_missing.py`
- **一句話結論**：DQ 模組設計乾淨、policy / aggregate / summary / unit tests 完備；run007 與 run004 策略輸出 byte-identical（COMP/ICP 不在 PIT、Bybit perp 1-event 落在持倉視窗外，故 DQ 對最終績效零影響）；單元測試核心路徑全綠。**TASK-001 整體仍不可 DONE，需等 REVIEW-001_final。**

### 審查 checklist

- [x] Data-quality policy 符合 TASK-001d：8 條 policy 明示於 stats.json `data_quality_policy` 區塊；ranking / holding / return 三層獨立處理。
- [x] `volume <= 0` 只 warning（action=`warn_only`）；missing `volume` / `quote_volume` 為 hard exclusion（action=`exclude_symbol_day`）。
- [x] Held symbol 當日 abnormal 的處理：`holding_abnormal_day_policy` 明示「移除 before return calculation, no position row emitted, re-entry 需 future rebalance」。本資料集 `dq_forced_holding_exits = 0`（沒有實際觸發）。
- [x] `data_quality_summary.csv` schema：7 欄全部存在，1696 列無例外，issue_type/action/source_stage 三維可交叉切。
- [x] `data_quality_aggregate.json` 含 8 個 aggregate 欄位 + `affected_date_ranges` + `top_affected_symbols`。
- [x] COMP-USD 1045 列（836 non-warning）、ICP-USD 2 列 nonpositive_price 正確標記；兩 symbol 都不在 PIT（不是 BYBIT perp），對策略 0 影響。
- [x] run007 vs run004：baseline.csv 與 positions.parquet **byte-identical**（SHA-256 相同），所有差異可由「DQ 對本資料集零影響」解釋。
- [x] stats 可由 baseline.csv 重算到 1e-14（與 run004 相同因為 CSV byte-identical）。
- [x] 重跑 stats hash 一致：`10dfa956…58822`。
- [x] 單元測試核心路徑（nonpositive hard exclusion / warn-only / forced_holding_exit）全綠。

### Caveat / 建議補件（不擋 PASS，列入 REVIEW-001_final 前完成）

- 單元測試**未覆蓋**：(a) `exclude_from_ranking_candidate` 路徑（lookback 內有 hard abnormal 時 ranking 排除）；(b) `missing_price_row` 事件；(c) `aggregate_data_quality_events` 邊界。建議補三個 fixture-driven test，避免「實資料未觸發 + 測試未覆蓋」的盲區。 → **TASK-001e 已補齊三條 fixture-driven test**，見 REVIEW-001e。
- 本資料集 `dq_excluded_from_ranking_candidates = 0` 是資料巧合，**不是 bug**；未來資料推進時會自然啟動。

---

## REVIEW-001e — TASK-001e Final Review Readiness Patch

- **狀態**：`PASS`（2026-05-13）— 允許 TASK-001e 轉 DONE；允許開 REVIEW-001_final
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-001e
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-001e
- **審查產物**：
  - `outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv`
  - `outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet`
  - `outputs/backtests/prev3y_crypto/20260513_run008_stats.json`
  - `outputs/logs/prev3y_crypto/20260513_run008.log`
  - `outputs/data_quality/prev3y_crypto/20260513_run008_data_quality_summary.csv`
  - `outputs/data_quality/prev3y_crypto/20260513_run008_data_quality_aggregate.json`
  - `tests/data_quality/test_missing.py`（5 tests）
  - `docs/research/TASK_001_PREV3Y_BASELINE_SUMMARY.md`
- **一句話結論**：純粹是「報表 + 測試 + 文件」補件，**baseline.csv / positions / DQ summary / DQ aggregate 與 run007 byte-identical**（四份 SHA-256 相同）；3 個新測試覆蓋 REVIEW-001d 的全部缺口；4 個新 metadata 欄位獨立驗算正確；reproducibility hash 通過。**TASK-001 整體仍 REVIEW，等 REVIEW-001_final**。

### 審查 checklist

- [x] 策略 / DQ 輸出 byte-identical with run007（SHA-256 比對 4 份檔案全相同）。
- [x] 5 個單元測試完整存在於 Windows host（Read tool 驗證 245 行檔案、5 個 `def test_*` 完整、helper 參數化齊全）。
- [x] 4 個新 metadata 欄位：`ir_vs_btc_full_effective_days=1884`、`ir_vs_btc_active_effective_days=760`、`benchmark_eqw_effective_days_full=2017`、`benchmark_eqw_effective_days_active=760`，全由 CSV 獨立驗算對到。
- [x] 既有 IR / Sharpe / DQ 數值與 run007 完全一致（spot-check 11 個關鍵欄位全部 equal）。
- [x] stats 重算誤差 ≤ 1.07e-14（Codex 自驗）；我獨立重算 `ir_vs_btc_full` 也對到 1e-14。
- [x] reproducibility hash 兩次相同 `ee8031732d1eda1406a9c10c57d11e49b6f54b3ac03c8e06fe84e63bbbe2a06f`。
- [x] SUMMARY.md 已更新到含 run007 與 REVIEW-001d 的版本。
- [x] 沒有 stage / commit、TASK-001 仍 REVIEW、TASK-002 / TASK-003 仍 BLOCKED。

### Caveat（環境問題，非 Codex 問題）

- Linux mount 看到的 `test_missing.py` 是舊截斷版本（109 行 / 4 個 broken test），加上 stale `__pycache__/*.pyc` 無權限刪除，導致本環境 `python -m unittest` 無法跑出新測試。**Read tool 直接驗證 Windows-side 是完整 5 test**，Codex 在 Windows 端自報 PASS 視為可信。建議下次 Codex 把 unittest console output 貼進交付摘要，避免此類疑慮。

## REVIEW-001e - TASK-001e Final Review Readiness Patch

- **狀態**：`READY_FOR_CLAUDE`
- **對應任務**：CODEX_TASK_QUEUE.md 的 TASK-001e
- **日期**：2026-05-14
- **提醒**：這是 `REVIEW-001_final` 前的小型補件；TASK-001 仍不可轉 DONE，TASK-002 / TASK-003 仍 BLOCKED。

### Review inputs

- `tests/data_quality/test_missing.py`
- `src/data_quality/missing.py`
- `src/reporting/prev3y_benchmarks.py`
- `src/metrics/performance.py`
- `scripts/run_prev3y_crypto_baseline.py`
- `outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv`
- `outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet`
- `outputs/backtests/prev3y_crypto/20260513_run008_stats.json`
- `outputs/logs/prev3y_crypto/20260513_run008.log`
- `outputs/data_quality/prev3y_crypto/20260513_run008_data_quality_summary.csv`
- `outputs/data_quality/prev3y_crypto/20260513_run008_data_quality_aggregate.json`

### Checklist for Claude

- [ ] Confirm the three REVIEW-001d unit-test gaps are covered: `exclude_from_ranking_candidate`, `missing_price_row`, and `aggregate_data_quality_events` boundaries.
- [ ] Confirm stats.json and log include `ir_vs_btc_full_effective_days`, `ir_vs_btc_active_effective_days`, `benchmark_eqw_effective_days_full`, and `benchmark_eqw_effective_days_active`.
- [ ] Confirm run008 vs run007 has no change in `portfolio_return`, positions, or benchmark return columns.
- [ ] Confirm stats recompute from run008 baseline within tolerance.
- [ ] Confirm TASK-001 remains REVIEW and TASK-002 / TASK-003 remain BLOCKED pending `REVIEW-001_final`.

### Codex validation summary

- Unit tests: `python -m unittest discover -s tests` PASS, 5 tests.
- run008 vs run007 core baseline and benchmark columns: max diff `0.0`.
- run008 vs run007 positions: equal.
- run008 stats recompute max diff: `1.07e-14`.
- run008 repeat stats hash: `ee8031732d1eda1406a9c10c57d11e49b6f54b3ac03c8e06fe84e63bbbe2a06f`.

---

## REVIEW-002 — Funding / Cost Stress Test

- **狀態**：`WAITING_INPUT`
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-002
- **預期輸入**：
  - `outputs/backtests/prev3y_crypto/<YYYYMMDD>_cost_stress.csv`
  - `outputs/backtests/prev3y_crypto/<YYYYMMDD>_cost_stress_summary.json`

### 審查重點

**A. cost 計算正確性**
- [ ] `net = gross − fee − funding − slippage`，逐列驗算誤差 < 1e-8。
- [ ] funding 是按 8 小時（或交易所實際 interval）結算累加，不是月末快照。
- [ ] rebalance 日同時涵蓋雙邊 fee（賣舊 + 買新）。
- [ ] 滑點模型在小成交量幣上有沒有設下限（不要小幣 0 bps）。

**B. 情境設定**
- [ ] base / pessimistic / extreme 三個情境的乘數是否如約。
- [ ] funding 在牛市末段（如 2021-Q1、2021-Q4）有沒有顯著拉高策略成本？沒有就懷疑。

**C. 結論一致性**
- [ ] 若 `pessimistic` 下 IR 已 < 0.3，是否在 summary.json 明確標 `WARNING`。
- [ ] gross 與 baseline (TASK-001) 是否吻合（差距應為 0 ± 浮點誤差）。

**D. 潛在 trap**
- [ ] funding 取的是 perp 還是 spot？兩種交易品上 cost 結構完全不同。
- [ ] 是否把 slippage 與 fee 重複計算（例如使用 effective price 又再扣 fee）。

### 預設輸出
- `docs/research/prev3y_crypto/<YYYYMMDD>_cost_stress_review.md`。
- 「在哪個情境會死」必須白紙黑字寫出來。

---

## REVIEW-003 — Baseline Attribution

- **狀態**：`WAITING_INPUT`
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-003
- **預期輸入**：
  - `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution.csv`
  - `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_summary.json`

### 審查重點

**A. 解構正確性**
- [ ] `total_return = sum(contribs) + residual`，逐列誤差 < 1e-8。
- [ ] regression 的 factor returns 是 contemporaneous（同期）而非 lagged，除非有明確理由。

**B. Beta 真假**
- [ ] market beta 平均值與 t-stat。若 |beta| > 0.3 且 t > 5，需在 summary 顯眼註記：「策略有顯著市場暴險，alpha 可能不純」。
- [ ] size / liquidity beta 是否解釋掉大部分 PnL（若 R² > 0.7，純 alpha 部分很小）。

**C. residual 結構**
- [ ] residual 不應有顯著季節性 / 月份效應，畫 monthly mean 圖做眼力測試。
- [ ] residual 自相關不應顯著（顯著代表還有可解釋來源沒被納入）。

**D. 樣本外**
- [ ] 是否同時提供 rolling regression 與 full-sample regression？兩者結論一致嗎？

### 預設輸出
- `docs/research/prev3y_crypto/<YYYYMMDD>_attribution_review.md`。
- 結論回答這題：**這個策略是 alpha，還是高 fee 的 beta？**

---

## REVIEW-004 — Quant Cowork Lab Dashboard

- **狀態**：`WAITING_INPUT`
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-004
- **預期輸入**：
  - Codex 跑起來的 dashboard（給截圖即可）。
  - `apps/dashboard/README.md`。

### 審查重點

**A. 唯讀性**
- [ ] dashboard 是否有任何寫入 `outputs/` 的路徑？有就 FAIL。
- [ ] 是否會重新跑回測？有就 FAIL（這是分析層該做的事，不是 dashboard）。

**B. 資料新鮮度**
- [ ] 首頁是否標示「資料 snapshot 時間」？
- [ ] cache 行為是否合理（不要每次點都重讀大檔，但也不要 cache 到看不到新資料）。

**C. 資訊呈現**
- [ ] baseline / cost / attribution / 30 天 PnL 是否齊備。
- [ ] 切換策略 / 情境的下拉是否真的能切換（不是寫死的）。
- [ ] 數字單位是否一律標明（％、bps、USDT）。

**D. 工程品質**
- [ ] dashboard 與 strategies code 是否有不當的相互依賴？單向：dashboard → outputs only。
- [ ] README 是否寫了 dependency、本機跑法、failure mode。

### 預設輸出
- `docs/research/lab_dashboard/<YYYYMMDD>_review.md`。

---

## REVIEW-005 — VPS Bot Monitor

- **狀態**：`WAITING_INPUT`
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-005
- **預期輸入**：
  - `apps/monitor/` 程式碼。
  - `outputs/monitor/heartbeat.parquet` 的 sample。
  - 一份「Codex 自己壓測過」的 alert 觸發紀錄。

### 審查重點

**A. 安全**
- [ ] 是否只用唯讀 / IP-whitelisted API key？發現可下單 key 直接 FAIL。
- [ ] log 內是否有完整 API key、帳號明碼？有就 FAIL。
- [ ] config 是否有支援從環境變數讀祕密（而不是寫死在 yaml）？

**B. 偵測能力**
- [ ] 心跳失敗連續 3 次能否觸發 CRITICAL？人為斷網測試過嗎？
- [ ] 「應下單卻沒下單」的偵測有沒有實作（不是只有 process alive 檢查）？
- [ ] dedupe 是否運作（同類問題 30 分鐘內不重複）？

**C. 通知**
- [ ] 至少 1 個 channel 實際通得了？
- [ ] 重大告警與 info 告警的等級是否分開？

**D. 不害人**
- [ ] monitor 自己掛掉時會不會被察覺？（需要 watchdog 或外部 ping）
- [ ] 是否有可能 monitor 自己誤殺 bot？應該完全沒這個能力。

### 預設輸出
- `docs/research/vps_monitor/<YYYYMMDD>_review.md`。

---

## 跨任務統一檢查（每次 review 都會掃）

無論在審哪個任務，Claude 都會額外掃以下這幾項，發現問題就直接寫進該 review：

1. **時間戳對齊**：UTC vs local time、08:00 funding cut-off、跨日訊號使用是否一致。
2. **資料 snapshot hash**：同一份輸出能不能對應到唯一的 input snapshot？
3. **log 的可讀性**：能不能從 log 看出「這次跑了哪個 config、哪段時間、哪個 git commit」。
4. **CSV / parquet schema 穩定性**：欄位名、單位有沒有跟前一版相容（或在 changelog 中明確告知 break）。
5. **數字過於漂亮**：IR > 3、Sharpe > 4、max DD < 5% 在 crypto 都是高度可疑訊號，預設懷疑、要求 Codex 提出證據。
