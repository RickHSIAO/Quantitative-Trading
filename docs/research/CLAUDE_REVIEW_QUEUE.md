# Claude Review Queue

最後更新：2026-05-15
維護者：Claude
狀態圖例：`WAITING_INPUT`（等 Codex 產出） / `IN_REVIEW` / `PASS` / `CONDITIONAL_PASS` / `FAIL` / `BLOCKED`

> **給 Rick 的閱讀指引**
> 1. 每張卡的「審查重點」是 Claude 會逐條檢查的清單，不是建議。
> 2. 結論一律落在 `PASS / CONDITIONAL_PASS / FAIL` 三選一，並附理由。
> 3. `CONDITIONAL_PASS` 代表「結果大致可信，但有需要 Codex 補的事」，補完才轉 `PASS`。
> 4. Claude 不會直接改 Codex 的程式，只會把問題寫成新的 TASK 進 `CODEX_TASK_QUEUE.md`。

---

## REVIEW-002a_phase1 — TASK-002a Phase 1 Scaffolding + Smoke（2026-05-14）

- **狀態**：**`PASS`**（Phase 1 範圍合格；允許 Phase 1 sub-task 轉 DONE、允許 Phase 2 開工）
- **TASK-002a 整體狀態**：**仍 IN_PROGRESS**（funding_rates.parquet 尚未存在；coverage 0%）
- **TASK-002 狀態**：**仍 BLOCKED_BY_TASK_002A**
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-002a_phase1
- **審查產物**：
  - `data/crypto/fees.yaml`、`configs/cost_stress.yaml`、`src/costs/symbol_mapping.py` + `tests/cost_inputs/test_symbol_mapping.py`（7 tests PASS）
  - `scripts/build_cost_funding_inputs.py`
  - `outputs/data_quality/funding_coverage/20260514_funding_coverage_{report.csv, summary.json}`
  - `outputs/logs/cost_inputs/20260514_build.log`
- **一句話結論**：Phase 1 鷹架 + Bybit API smoke check 都到位；fees / cost_stress / symbol mapping 三項驗收全 PASS（7 unit tests OK，含 RLUSD/1000PEPE 邊界）。**但 funding_rates.parquet 尚未存在，TASK-002 仍 BLOCKED**。Phase 2 開工前必須把 `phase1_status` 命名改成更明確的 `phase_status` enum（避免下游誤判 ready）。

### Phase 2 必補（12 條，見 LOG 第 4 節）
- Coverage gate：real ≥ 80% 才 `PHASE2_READY`；50–80% 為 `PHASE2_PROXY_ONLY`（需 Rick 同意）；< 50% 為 `PHASE2_BLOCKED_BY_DATA`。
- Symbol mapping integration test：對 PIT 273 symbol 全跑一次。
- Bybit API：rate-limit、分頁、raw response cache、log 內帶 `bybit_api_calls_made / errors / pages / first / last`。
- funding_rate sanity 抽查：10 筆 vs Bybit live diff < 1e-9。
- timestamp 必須是真實結算時點（00:00/08:00/16:00 UTC），禁止 resample 到日。
- 缺資料 symbol-day 不出現在 parquet 內。
- Proxy 順序：`proxy_universe_median` → 最後才 `proxy_zero`。
- `phase_status` enum 命名修正 + top-level `task_002a_overall_status: INCOMPLETE`。

---

## REVIEW-002a_phase2_dryrun — TASK-002a Phase 2 Bybit Funding Dry-Run（2026-05-14）

- **狀態**：**`PASS`**（dry-run 範圍合格；允許進 controlled full fetch）
- **TASK-002a 整體狀態**：**仍 IN_PROGRESS**（`data/crypto/funding_rates.parquet` 尚未存在）
- **TASK-002 狀態**：**仍 BLOCKED_BY_TASK_002A**
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-002a_phase2_dryrun
- **審查產物**：
  - `outputs/data_quality/funding_coverage/20260514_phase2_dryrun_funding_rates.parquet`（4 symbols × 7 days = 84 列）
  - `outputs/data_quality/funding_coverage/20260514_phase2_dryrun_coverage_{report.csv, summary.json}`
  - `outputs/logs/cost_inputs/20260514_phase2_dryrun.log`
- **一句話結論**：dry-run 把 full fetch 6 個最會出包的風險點（API rate-limit / schema / mapping / 8h boundary / unit / live diff）全驗到位：parquet 84 列 / hours={0,8,16} / abs max funding 0.00075 / mapping 273/273 / live diff = 0.0 / API 0 errors。Phase 1 提的 `phase_status` 命名誤導也已修。**但正式 `data/crypto/funding_rates.parquet` 仍不存在**，TASK-002 仍 BLOCKED。

### Full fetch 必守 12 條限制（見 LOG 第 3 節）
- 範圍 273 symbols × 760 days；正式輸出路徑 `data/crypto/funding_rates.parquet`。
- Raw API cache + idempotency 兩次同 hash。
- Coverage gate ≥ 80% real（50–80% PROXY_ONLY 須 Rick 同意；< 50% BLOCKED_BY_DATA）。
- 30 筆 live diff 抽查跨 2024/2025/2026 各年 ≥ 5 筆。
- 異常值 flag（`abs > 0.01`）、連續性檢查（> 24h gap）。
- `phase_status` 終態三選一 + top-level `task_002a_overall_status`。
- 禁動 run008 / strategy / DQ / benchmark；禁開 TASK-002 stress。

---

## REVIEW-002a_phase2_full — TASK-002a Phase 2 Bybit Funding Full Fetch（2026-05-14）

- **狀態**：**`PASS`（含 caveat）**
- **TASK-002a 整體狀態**：**DONE**（最終正式 `data/crypto/funding_rates.parquet` 已落地）
- **TASK-002 狀態**：從 `BLOCKED_BY_TASK_002A` 改為 **`BLOCKED_BY_WORKORDER_UPDATE`**（funding interval 假設被資料推翻）
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-002a_phase2_full
- **審查產物**：
  - `data/crypto/funding_rates.parquet`（750,641 列、273 symbols、無 proxy）
  - `outputs/data_quality/funding_coverage/20260514_phase2_full_coverage_{report.csv, summary.json}`
  - `outputs/logs/cost_inputs/20260514_phase2_full_fetch.log`
- **核心數字**：active PIT real coverage **97.56%**、active position real coverage **98.84%**、live diff 30/30 = `0.0`、mapping 273/273、idempotency hash 一致、proxy 完全未使用。

### 最重要的單一發現：funding interval 不是統一 8h
- 1h interval：1 symbol（2,758 列）
- 4h interval：145 symbols（461,513 列）
- 8h interval：127 symbols（286,370 列）
- TASK-002 工單第 8 節「8h funding」假設**被推翻**，必須改為「依 `interval_hours` 與 `timestamp` per-row 累加」。
- `cost_stress.yaml` defaults 的 `funding_application` 從 `pit_8h_settlement_accumulated` 改為 `pit_per_interval_settlement_accumulated`。

### TASK-002 開工前必須保留的 caveats（7 條）
1. Active 樣本 760 天（沿用 REVIEW-001_final）。
2. Funding interval 1h/4h/8h 混合，必須 per-row 累加。
3. 7 個 active position missing symbols：XTZ / FLOW / LPT / AXS / RVN / INJ / CTC——cost engine 對該 symbol-day 標 `funding_gap=True` 而非 fill。
4. 653 個 outliers（abs ≥ 1%，max abs = 0.05）照實累加，cost stress summary 須列出 outlier 對總 funding cost 的貢獻百分比；> 30% 標 WARNING。
5. continuity gaps 68,526 events（active position 影響 1.16%），cost engine 不需修補但 summary 須列出。
6. idempotency hash 是 content hash 不是檔案 hash，TASK-002 須沿用同 convention。
7. strategy / signals / universe / DQ / benchmark 紅線維持不變。

### 下一步
1. Claude 把 TASK-002 工單 v2 patch（5 項必改清單，見 LOG 第 3 節）。
2. Codex 對 v2 跑 readiness check。
3. 若 READY_TO_IMPLEMENT → 開工 TASK-002 cost stress。

---

<!-- 已 SUPERSEDED 的舊版條目 -->
## REVIEW-002a_phase2 — TASK-002a Phase 2（舊版整體 review，已拆 dryrun + full）

- **狀態**：`SUPERSEDED`（被 REVIEW-002a_phase2_dryrun + REVIEW-002a_phase2_full 拆分取代）
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-002a Phase 2
- **預期審查產物**：
  - `data/crypto/funding_rates.parquet`（7 欄；真實 Bybit funding，覆蓋 active period 2024-04-01 ~ 2026-04-30）
  - `data/cache/funding/bybit_raw/*.json`（API raw response cache）
  - 重做版 `outputs/data_quality/funding_coverage/<YYYYMMDD>_funding_coverage_{report.csv, summary.json}`（三個獨立 coverage 欄位）
  - 更新版 `outputs/logs/cost_inputs/<YYYYMMDD>_build.log`（含 API metrics）
- **此 review PASS 後**：TASK-002a 整體轉 DONE、TASK-002 解除 BLOCK、Codex 才可對 TASK-002 重做 readiness check。

### 審查重點（沿用 REVIEW-002a_phase1 第 4 節 12 條規則 + Phase 1 已過的所有 schema 檢查）

- [ ] funding_rates.parquet schema 7 欄正確、symbol 為 `BYBIT:XXXUSDT.P` 格式。
- [ ] active period real coverage ≥ 80%（或經 Rick 同意的 PROXY_ONLY）。
- [ ] funding_rate 為小數；隨機抽查 10 筆與 Bybit API live 對比 diff < 1e-9。
- [ ] interval_hours 為 8 或交易所實際 interval。
- [ ] timestamp 為真實結算時點；無 resample 到日。
- [ ] 缺資料 symbol-day 不在 parquet 內；只在 coverage report 紀錄。
- [ ] Proxy 列 `is_proxy=True` 並標明 source；`proxy_zero` 使用須在 NOTE 列出涉及 symbol-day。
- [ ] log 含 Bybit API metrics：`bybit_api_calls_made / errors / pages_fetched / first_response_at / last_response_at`。
- [ ] `phase_status` enum 與 `task_002a_overall_status` 命名已修正。
- [ ] Symbol mapping integration test：對 PIT 273 symbol 全跑一次並印 mapping miss 名單。
- [ ] 不可動 run008、不可改 strategy / signals / DQ / benchmark / backtester。
- [ ] 不可執行 TASK-002 stress（仍是下一棒）。

---

<!-- REVIEW-002a（舊版整體 review）保留作 trail 參考；實際以 Phase 1 / Phase 2 拆分後的條目為準 -->
## REVIEW-002a — TASK-002a Cost / Funding Input Builder（2026-05-14 新增，已拆 phase1 / phase2）

- **狀態**：`SUPERSEDED`（被 REVIEW-002a_phase1 + REVIEW-002a_phase2 拆分取代）
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-002a
- **對應工單**：`docs/research/codex_workorders/TASK-002a_cost_funding_inputs.md`
- **預期審查產物**：
  - `data/crypto/funding_rates.parquet`
  - `data/crypto/fees.yaml`
  - `configs/cost_stress.yaml`
  - `outputs/data_quality/funding_coverage/<YYYYMMDD>_funding_coverage_report.csv`
  - `outputs/data_quality/funding_coverage/<YYYYMMDD>_funding_coverage_summary.json`
  - `outputs/logs/cost_inputs/<YYYYMMDD>_build.log`
  - `src/costs/symbol_mapping.py` + `tests/cost_inputs/test_symbol_mapping.py`
- **此 review PASS 是 TASK-002 解除 BLOCK 的唯一條件**：TASK-002 仍標 `BLOCKED_BY_TASK_002A`，**只有 REVIEW-002a PASS 之後 Codex 才可重新對 TASK-002 跑 readiness check**（產出 READY_TO_IMPLEMENT / BLOCKED_BY_DATA / NEED_CLARIFICATION）。

### 審查重點

**A. 資料覆蓋與真實性**
- [ ] active period（2024-04-01 ~ 2026-04-30）內每個 PIT-active symbol-day 都有 `has_funding` 標記。
- [ ] real coverage % ≥ 80%；若低於門檻，Codex 必須回報 `PROXY_ONLY` 或 `BLOCKED_BY_DATA`，且 NOTE 區寫明資料來源嘗試紀錄。
- [ ] 缺資料的 symbol-day **不出現** 在 funding_rates.parquet 內（不 fill 0）；只在 coverage report 紀錄。
- [ ] 不可包含 `2026-04-30` 之後的資料；不可包含未在 run008 PIT 出現過的 symbol。

**B. funding_rates.parquet schema 正確性**
- [ ] 7 欄都存在：`timestamp / symbol / exchange / funding_rate / interval_hours / source / is_proxy`。
- [ ] `funding_rate` 是小數（非百分比）；隨機抽 3 筆對 Bybit 官方比對。
- [ ] `interval_hours` 為 8（或交易所實際 interval）；混合 interval 必須逐筆正確標示。
- [ ] symbol 一律為 `BYBIT:XXXUSDT.P` 格式，與 run008 positions 對齊。
- [ ] timestamp 是實際 funding 結算時點（UTC），未被 resample 到日。

**C. proxy 處理**
- [ ] 任何 proxy 列 `is_proxy=True` 且 `source` 標明 proxy 類別（`proxy_universe_median` / `proxy_zero` 等）。
- [ ] proxy 規則寫進 NOTE 區與 log。
- [ ] proxy 不可與真實資料 mix 後不打標籤。

**D. fees.yaml**
- [ ] 含 `exchange / maker_bps / taker_bps / notes` 四欄。
- [ ] bps 採整體 `0.01%` 計算（`taker_bps: 5.5` = 0.055%）。
- [ ] notes 含：取數日期、來源 URL、會員等級、fee rebate 處理。

**E. cost_stress.yaml**
- [ ] 12 個 scenario 名稱與工單第 9 節**一字不差**。
- [ ] `no_cost_baseline` 全乘數為 0、雙邊 maker、滑點 0。
- [ ] `defaults` 區塊含 `annualization_factor=365.25`、`std_ddof=1`、`slippage_application`、`fee_application`、`funding_application`、`funding_proxy_policy`。
- [ ] 沒有額外的「美化情境」（如 fee × 0.5）。

**F. Symbol mapping**
- [ ] `src/costs/symbol_mapping.py` 是獨立函式，未被寫進 strategy / signals / backtester / DQ / reporting。
- [ ] 單元測試覆蓋至少：`BTCUSDT` round-trip、`1000PEPEUSDT` round-trip、`RLUSDUSDT`（避免 USDT 後綴被切錯）、不合法輸入丟 ValueError。
- [ ] `python -m unittest tests.cost_inputs.test_symbol_mapping` 全綠。

**G. 工程衛生**
- [ ] log 開頭 5 個欄位齊備：`random_seed / config_hash / data_snapshot_hash / git_commit / baseline_run_id=20260513_run008 / funding_source / funding_proxy_pct`。
- [ ] 不可動 run008 任何檔案。
- [ ] 不可改 strategy / signals / universe / DQ / benchmark / backtester。
- [ ] 沒有執行 TASK-002 stress（純輸入準備）。

### 預設輸出
- `docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-002a 完整紀錄。
- 結論一律 `PASS / CONDITIONAL_PASS / FAIL`。
- 若 PASS：允許 TASK-002a 轉 DONE、解除 TASK-002 的 `BLOCKED_BY_TASK_002A`。
- 若 CONDITIONAL_PASS：列出補件清單，再開 REVIEW-002a-2。
- 若 FAIL：說明哪些覆蓋率 / schema / mapping 問題不可接受。

---

## REVIEW-001_final — TASK-001 整體最終總審（2026-05-13）

- **狀態**：**`PASS`**
- **TASK-001 整體狀態**：**DONE**（最終正式 baseline = `20260513_run008`）
- **TASK-002 狀態**：**BLOCKED_BY_TASK_002A**（2026-05-14 由 readiness check 標記）
- **TASK-003 狀態**：**READY_TO_IMPLEMENT**（2026-05-15 由 Opus REVIEW-002 PASS 解鎖；完整工單見 `codex_workorders/TASK-003_baseline_attribution.md` v1.0）
- **研究判定**：**需要更多測試**（保留路線、進入 cost stress；不淘汰、不立即上線）
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-001_final
- **核心數字（active 口徑）**：Sharpe `0.9267`、IR_vs_cash `0.9267`、IR_vs_btc `-0.0175`、IR_vs_eqw `+0.7227`、max DD `-19.50%`、有效持倉 760 天
- **下一張工單**：TASK-002a `codex_workorders/TASK-002a_cost_funding_inputs.md`（已就緒）；待 REVIEW-002a PASS 後啟動 TASK-002 readiness recheck

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

## READINESS-002 — TASK-002 v2 Readiness Check（2026-05-15）

- **狀態**：`NEED_CLARIFICATION`（Readiness Check 完成；data PASS，cost_stress.yaml v1 config 待 Codex 更新）
- **執行模型**：Claude Sonnet
- **Suggested model**：Sonnet
- **Escalation reason**：N/A
- **Opus final decision required**：No
- **結論摘要**：13/15 通過；唯一阻塞 = `configs/cost_stress.yaml` defaults 仍為 v1（`funding_application` 舊值 + 缺 3 個 v2 policy key）。資料本身零問題。Codex 更新 yaml（1 次 commit）後立即 READY_TO_IMPLEMENT。
- **完整審查紀錄**：`CLAUDE_REVIEW_LOG.md` → READINESS-002

### Readiness 15 項快速結果

| # | 項目 | 判定 |
|---|---|---|
| 1 | funding_rates.parquet schema 7 欄正確 | ✅ |
| 2 | is_proxy 全 False | ✅ |
| 3 | interval_hours ∈ {1,4,8} | ✅ |
| 4 | timestamp UTC | ✅ |
| 5 | funding_rate 為小數 | ✅ |
| 6 | active position coverage ≥ 80% | ✅ 98.84% |
| 7 | active PIT coverage ≥ 80% | ✅ 97.56% |
| 8 | fees.yaml maker/taker/notes | ✅ |
| 9 | cost_stress.yaml 12 scenarios | ✅ |
| 10 | funding_application = pit_per_interval | ❌ BLOCKED（仍為 v1）|
| 11 | 含 interval/gap/outlier policy | ❌ BLOCKED（全缺）|
| 12 | no_cost_baseline 全 0 | ✅ |
| 13 | known gap symbols 可標記 | ✅ 7/7 吻合 |
| 14 | outlier records 可標記 | ✅ 653 rows |
| 15 | READY_TO_IMPLEMENT | ❌（待 yaml 更新）|

---

## REVIEW-002 — Funding / Cost Stress Test（**對應工單 v2**）

- **狀態**：`WAITING_INPUT`（等 Codex 更新 cost_stress.yaml → 完成 cost stress 實作 → 交付）
- **Opus 第二輪介入（2026-05-15，REVIEW-002 PASS）**：Codex 已交付 `20260515_cost_stress_*` 全部 4 個官方檔；Sonnet 初審升級為 PASS_CANDIDATE（14/14 checklist 過、fail gate 全過、warning 未觸發）。Opus 第二輪複核：**`PASS`**，TASK-002 → DONE，策略判定升級為「保留」，TASK-003 / TASK-004 / TASK-005 全部解鎖；paper trading **可規劃（TASK-006）、不可立即執行**；live trading 仍禁止。核心 cost 發現：**slippage > fee > funding**（推翻事前假設）。詳見 `CLAUDE_REVIEW_LOG.md` → REVIEW-002（Opus 2026-05-15 第二輪）。
- **Opus 第一輪介入紀錄（保留作 trail，2026-05-15）**：當時 0/4 交付物存在，Opus 結論 `BLOCKED_CANNOT_REVIEW`，**不接受** 用舊架構 `output/crypto_cost_stress.csv` 替代。
- **下一次 Opus 介入流程**：(1) Codex commit cost_stress.yaml v2 → (2) Codex 執行工單 v2 → 4 交付物 + 9 件回報 → (3) Sonnet 跑工單 v2 第 11 節 checklist + 填好 Key Numbers 表 → (4) Opus 用 Sonnet draft 的 Suggested Opus Prompt 重啟 final decision（13 道答題）。
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-002（NEED_CLARIFICATION）
- **對應工單**：`docs/research/codex_workorders/TASK-002_cost_funding_slippage_stress.md`（**v2**）
- **預期輸入**：
  - `outputs/backtests/prev3y_crypto/<YYYYMMDD>_cost_stress.csv`（含 `date / scenario / gross / net / fee_cost / funding_cost / slippage_cost / exposure / turnover`）
  - `outputs/backtests/prev3y_crypto/<YYYYMMDD>_cost_stress_summary.json`（含 v2 新增三區塊：`funding_gap_breakdown`、`outlier_contribution_breakdown`、`interval_distribution_used`）
  - `outputs/backtests/prev3y_crypto/<YYYYMMDD>_cost_stress_positions_cost.parquet`（含 v2 新增 `funding_gap` 與 `outlier_count_today` 欄）
  - `outputs/logs/prev3y_crypto/<YYYYMMDD>_cost_stress.log`

### 審查重點（v2 對齊）

**A. v2 funding per-interval 累加**
- [ ] funding 是依 `funding_rates.parquet` 每列的 `timestamp` 與 `interval_hours` 累加，**不是固定 8h**。
- [ ] log audit 抽樣 3 筆（1h / 4h / 8h 各 1 個 symbol-day），每筆列出當日每次 settlement 的 `timestamp / funding_rate / position_notional / 單次 cost / 當日加總`。
- [ ] `interval_distribution_used` 與 funding_rates.parquet 全集（1h:1 / 4h:145 / 8h:127）比例相當（容差 ±10 row）。

**B. cost 計算正確性**
- [ ] `net = gross − fee − funding − slippage`，逐列驗算誤差 < 1e-8。
- [ ] `no_cost_baseline.portfolio_return_net` 與 run008 `portfolio_return` 逐列相等（差 = 0）。
- [ ] rebalance 日同時涵蓋雙邊 fee（賣舊 + 買新）。
- [ ] slippage 採每次 turnover 單邊 bps，整體雙邊。

**C. v2 known-gap 7 symbols 處理**
- [ ] XTZ / FLOW / LPT / AXS / RVN / INJ / CTC 缺料 symbol-day 標 `funding_gap=True`，funding cost = 0，**未被 fill**。
- [ ] `funding_gap_breakdown` 區塊列出每個 known-gap symbol 影響的 symbol-day 數與比例。
- [ ] 任一情境 `pct_of_active_position > 5%` 標 WARNING。

**D. v2 outlier 處理**
- [ ] 653 筆 abs(funding_rate) ≥ 0.01 列**照實累加**、無截斷無修正。
- [ ] `outlier_contribution_breakdown` 給三 combo 情境的 outlier 佔總 funding cost 百分比。
- [ ] 任一 combo `outlier_pct_of_total_funding_cost > 30%` 標 WARNING。

**E. 情境設定（12 scenarios）**
- [ ] 12 scenarios 命名與工單 v2 一字不差；無「美化情境」（如 fee × 0.5）。
- [ ] funding_low / funding_mid / funding_high 三個情境只乘 funding_multiplier，未動 fee / slippage。

**F. 結論 / fail gate**
- [ ] `realistic_combo` active Sharpe < 0.5 → FAIL。
- [ ] `realistic_combo` active IR_vs_eqw < 0.2 → FAIL。
- [ ] `conservative_combo` active IR_vs_eqw < 0 → FAIL。
- [ ] `realistic / conservative` max DD 惡化 > 1.5× run008（−19.5% → −29.25%）→ WARNING。
- [ ] 任一情境成本吃掉 active alpha > 70% → WARNING。

**G. 潛在 trap**
- [ ] funding_rates.parquet 內 `is_proxy` 全 False（任一 True 應在 readiness check 階段就被擋掉）。
- [ ] 不可把 4h funding 折半成「等效 8h」、不可把 1h 折成「等效 8h」（v2 紅線）。
- [ ] 不可把 slippage 與 fee 重複計算（例如使用 effective price 又再扣 fee）。

**H. 工程衛生**
- [ ] 重跑兩次 content hash 一致（不是檔案 SHA-256）。
- [ ] cost / funding / slippage 模組獨立在 `src/costs/`，未污染 strategy / signals / backtester / DQ / reporting / benchmark。
- [ ] log 開頭含 `random_seed / config_hash / data_snapshot_hash / git_commit / baseline_run_id=20260513_run008 / funding_rates_parquet_hash / interval_distribution_used / scenarios_count`。

### 預設輸出
- `docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-002 完整紀錄。
- 「在哪個情境會死」必須白紙黑字寫出來。
- 結論 PASS / CONDITIONAL_PASS / FAIL；若 PASS 則允許 TASK-002 → DONE，並決定是否仍允許 TASK-003 開工。

---

## REVIEW-003 — Baseline Attribution

- **狀態**：**`CONDITIONAL_PASS`**（Opus final decision，2026-05-15）
- **TASK-003 狀態**：**DONE**（CONDITIONAL_PASS 不擋 DONE；caveat 進 TASK-007）
- **核心數字（active）**：gross 29.58% / net 28.53% / short net +33.65% / long net −5.10% / top5 / net_alpha_total = **95.56%**（工單公式 → TRIGGERED）/ 2025 占 89%
- **核心發現**：策略 narrative 從「對稱多空 momentum」更新為「**short-driven crypto alpha + long-side 結構性虧損**」
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-003（Opus 2026-05-15）
- **Downstream**：TASK-004 / 005 維持 READY；TASK-006 允許規劃（+3 mandatory caveat）；TASK-007 新增 TODO（long-side variant study）；live trading 仍禁止
- **Codex 必補（不擋 DONE）**：(a) concentration 並列輸出兩個分母；(b) 補 `long_side_drag` warning gate；(c) 自動產出 review packet（per Token Budget Rule）

### 審查重點（已執行）

REVIEW-003 已完成審查；4 條 fail gates 全 PASS、reproducibility 一致、對帳機器精度。詳細結論與 4 條 warning + 2 條結構性 caveat 見 LOG。

### 預期輸入（已收到）

- `outputs/attribution/prev3y_crypto/20260515_attribution_*`（6 個 CSV/JSON）
- `outputs/logs/prev3y_crypto/20260515_attribution.log`

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

## REVIEW-009c — Forward Record Tech Debt Fixes C-1~C-6（2026-05-18）

- **狀態**：**`PASS`**（Opus final decision，2026-05-18）
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-009c **DONE**
- **Verdict**：PASS（C-1~C-6 全部收斂；sandbox stale .pyc = infrastructure noise，非 code regression）
- **核心發現**：
  - C-1：A-5 `CacheMarketDataProvider` marker 移除；S-A5c 驗證 triggered=false
  - C-2：`_extract_yyyymmdd()` pathlib stem + word-boundary regex；多 date 路徑邊界正確
  - C-3：`configs/forward_record.yaml` 新增；`alerting.py` 不再 hardcode review artifact path；`{date}` 佔位符支援
  - C-4：`raw_content` sub-dict 加入 drill；template check 與 raw content check 正式分離
  - C-5：`AlertConditionResult.__post_init__` None guard；`no_placeholder_raw` pre-sanitize check
  - C-6：S-A5c negative scenario；drill 12 → 13 scenarios；REVIEW-009d artifacts 同步更新
  - Windows 測試：97 forward_record tests + 13 monitor tests = 110 PASS；drill 13/13 PASS
  - Linux sandbox stale .pyc（4 failures）判定為 infrastructure noise，不阻擋 DONE
- **30-day clock**：NOT_STARTED（仍需 Rick 明示「開始計時」）
- **Paper execution**：FORBIDDEN（5/7 gates；30 天 forward record + REVIEW-006b + Rick 批准未完成）
- **Live trading**：FORBIDDEN（不變）
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-009c

---

## REVIEW-009d — Alert Delivery E2E Drill（2026-05-18）

- **狀態**：**`PASS`**（Opus final decision，2026-05-18）
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-009d **DONE**
- **Verdict**：PASS（0/10 fail gates；W-1/W-2/W-3 全部 CAVEAT 非 BLOCKING）
- **核心發現**：
  - 18/18 tests PASS（0.083s）；12/12 scenarios PASS（正 trigger 8 + 負 trigger 4）
  - Redaction PASS（9 pattern × 12 scenarios = violation_count=0）
  - Dedupe PASS（A-6 首日 triggered=True、次日 suppressed=True；A-2 非 dedupe 確認）
  - Discord template PASS（6 項格式驗證全 True）
  - dry_run=True；ChannelResult.status=DRY_RUN；external_post_attempted=false；clock_started=false
  - W-1：`_message_preview()` context inject 使 has_date/has_condition_id/has_action inflated → TASK-009c
  - W-2：`_sanitize_text("None"→"n/a")` 使 no_placeholder 形骸化 → TASK-009c
  - W-3：A-5 `CacheMarketDataProvider` false positive negative scenario 未含（TASK-009c 後補 S-A5c）
- **30-day clock 前置條件**：TASK-009d = DONE；VPS 部署尚未執行
- **30-day clock**：NOT_STARTED（仍需 Rick 明示「開始計時」）
- **Paper execution**：FORBIDDEN（5/7 gates；30 天 forward record + REVIEW-006b + Rick 批准未完成）
- **Live trading**：FORBIDDEN（不變）
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-009d

---

## REVIEW-009b — Forward Monitor Alerting（2026-05-18）

- **狀態**：**`PASS`**（Opus final decision，2026-05-18）
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-009b **DONE**
- **Verdict**：PASS（0/10 fail gates；W-1/W-2/W-3 全部 CAVEAT 非 BLOCKING）
- **核心發現**：
  - 15/15 tests PASS；scan_no_order_endpoints violations=[]；FORBIDDEN fields 全部 NOT_ATTEMPTED
  - 7 項 alert conditions（A-1~A-7）全部實作；dry_run 三重 gate 確認
  - Discord external_post_attempted=false；--live-alerts 未使用；clock_started 無 mutation
  - A-6 review_006b_trigger_ready 只送通知（severity=INFO）；不觸發任何自動執行；duplicate 抑制正確
  - W-1：A-5 `CacheMarketDataProvider` log marker 潛在 false positive → TASK-009c
  - W-2：`_extract_yyyymmdd()` path parsing 脆弱 → TASK-009c
  - W-3：`REVIEW_NUMBERS_PATH` 依賴 review artifact → TASK-009c
- **Monitor readiness**：READY（VPS 部署後即可啟用 alerting）
- **30-day clock**：NOT_STARTED（仍需 Rick 明示「開始計時」）
- **Paper execution**：FORBIDDEN（5/7 gates；30 天 forward record + REVIEW-006b + Rick 批准未完成）
- **Live trading**：FORBIDDEN（不變）
- **TASK-009d**：TODO（alert delivery E2E drill；30-day clock 啟動前置必辦）
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-009b

---

## REVIEW-009 — Forward Record Runner（2026-05-17）

- **狀態**：**`PASS`**（Opus final decision，2026-05-17）
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-009 **DONE**
- **Verdict**：PASS（0/10 fail gates；W-1/W-2/W-3 全部 CAVEAT 非 BLOCKING）
- **核心發現**：
  - 11/11 unit tests PASS；CLI dry-run `REVIEW_READY`；endpoint_scan PASS；FORBIDDEN flags 全部存在
  - Primary（`combined_paper_safe_variant`）：50 positions（25L/25S）；overlay_pass=true；clock_started=false
  - Shadow（`A_roll12_share20_exclude`）：獨立輸出目錄；hash ≠ primary
  - W-1：`api_key_request=NOT_ATTEMPTED` substring 誤判（false positive）；建議 TASK-009a 補白名單
  - W-2：dry-run 日 primary = shadow weights（alpha cap 未觸發）；建議 TASK-009a 加 `alpha_cap_triggered_today`
  - W-3：既有 uncommitted diff（task007 CSV / trading.db）；Rick 啟動 forward clock 前需 clean working tree
- **Runner readiness**：READY（VPS 部署後即可啟用）
- **VPS_DEPLOYMENT_CHECKLIST.md Phase 6**：解鎖（DEFERRED → ⬜ 可執行）
- **30-day clock**：NOT_STARTED（尚需 Rick 明示「開始計時」）
- **Paper execution**：FORBIDDEN（5/7 gates；30 天 forward record + REVIEW-006b + Rick 批准未完成）
- **Live trading**：FORBIDDEN（不變）
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-009

---

## REVIEW-008 — Alpha-Space Concentration Cap（2026-05-17）

- **狀態**：**`CONDITIONAL_PASS`**（Opus final decision，2026-05-17）
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-008 **DONE**
- **Verdict**：CONDITIONAL_PASS（W-1 top5_conc 87.95% > 75% = Caveat，非 Blocking）
- **核心發現**：
  - 0/8 fail gates 觸發；baseline mismatch 5.55e-17（機器精度）；reproducibility hash confirmed
  - 推薦 variant：`A_roll12_share20_exclude`（Pareto-dominant vs baseline）
    - Sharpe 0.9636（+8.0% vs baseline 0.8918）
    - single_conc 23.43%（< 25% ✅）
    - top5_conc 87.95%（baseline 95.56%，−7.61pp；W-1 = 87.95% > 75% caveat）
    - net_alpha 31.00%（+8.65%）；alpha_retention 108.65%；cost −9.73 bps
  - Variant B（alpha-share sizing）：集中度幾乎無改善（top5 95.22%）；REJECTED
  - Variant C（cooldown k≥6）：catastrophic；no_DOT paradox 第二次正式重現（top5 最高 642%）；REJECTED + 永久封存
  - A_roll12 = A_roll24 = A_penalize50（三者完全等效，參數退化現象）
- **Opus W-1 裁定**：top5_conc < 75% 改為 observation metric（非 hard target）；實務可接受區間暫定 top5_conc ≤ 90% 且 single_conc < 25%，需 Rick 最終簽核
- **TASK-006 paper runbook 更新**：A_roll12_share20_exclude 加入 secondary / shadow-track candidate；primary（combined_paper_safe_variant）不更動
- **no_DOT paradox（第二次正式紀錄）**：TASK-007 首現；TASK-008 Variant C 規模驗證 — 強制移除高 alpha contributor 使 top5_conc 爆炸至 642%，為動量策略的結構性數學性質
- **Paper execution**：FORBIDDEN（5/7 gates；30 天 forward record + REVIEW-006b + Rick 批准未完成）
- **Live trading**：FORBIDDEN（不變）
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-008

---

## REVIEW-005a — Real Alert Channel（Telegram / Discord / SMTP）

- **狀態**：**`PASS`**（Opus final decision，2026-05-17）
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-005a **DONE**
- **Verdict**：PASS（`external_channels_dry_run_only` warning = caveat for TASK-005a DONE；blocker for paper execution unlock）
- **核心發現**：
  - 11/11 fail gates 全 false：channel_dispatch_failure、exchange_api_present、local_jsonl_removed、missing_outputs、monitor_auto_restart_present、order_submission_code_present、real_external_post_during_validation、secret_hardcoded、secret_in_vcs、secret_written_to_logs、test_failure 全 false。
  - local_jsonl 保留：WRITTEN，delivered_count=1，external_post_attempted=false ✅
  - Telegram scaffold：DRY_RUN，external_post_attempted=false，token redacted ✅
  - Discord scaffold：DRY_RUN，external_post_attempted=false，webhook redacted ✅
  - configs/monitor_secrets.local.yaml 未建立（正確）✅
  - Safety scan PASS；secret_ignore.status=PASS（4 patterns 確認完整）✅
  - Reproducibility hash：06a28f791dbfeb931a35dadf1eb856f92c791d0bf8648b09ba004da5b8d58817（三源一致）
- **Caveat（非 Blocking for DONE；Blocker for paper execution）**：`external_channels_dry_run_only` — 外部 channel 仍為 dry_run，尚未執行真實 --test-send。
- **Rick 手動 Gate（paper execution 前置條件）**：Rick 必須對 ≥1 外部 channel 執行真實 `--test-send`，並將遮蔽後的證據存至 `outputs/monitor/test_send/<YYYYMMDD>_<channel>_proof.txt`。**不得在 chat 貼 token / webhook。**
- **Paper execution**：FORBIDDEN（Rick test-send 未完成 + 30 天 forward record + REVIEW-006b + Rick 批准等條件未達成）。
- **Live trading**：FORBIDDEN（不變）。
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-005a

---

## REVIEW-005 — VPS Bot Monitor

- **狀態**：`PASS`（Opus REVIEW-005 PASS，2026-05-17）
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-005 DONE
- **Verdict**：PASS（`single_channel_only` warning = caveat，非 Blocking）
- **核心發現**：
  - 9/9 fail gates 全 false：`api_key_permission_violation`、`order_submission_code_present`、`monitor_auto_restart_present`、`secret_in_vcs`、`test_failure`、`schema_mismatch`、`missing_outputs`、`heartbeat_schema_invalid`、`alerts_schema_invalid` 全 false。
  - Observer-only scope 確認：無下單程式碼、無 exchange 連線、無 API key 請求、無 paper/live 啟動。
  - `.gitignore` 4 個 secret pattern 完整（`configs/monitor_secrets.yaml / .yml / .local.yaml / .local.yml`）。
  - heartbeat.parquet / alerts JSONL schema PASS；configs/monitor.yaml defaults 符合工單規格。
  - Safety scan PASS；`secret_ignore.status = PASS`；`forbidden_token_violations = []`。
- **Caveat（非 Blocking）**：`single_channel_only` — 目前只有 `local_jsonl (dry_run=true)`；VPS 上線前須完成 TASK-005a（接通 Telegram/Discord/SMTP 真實 channel）。
- **TASK-005a**：TODO（paper execution gate 的一部分，除非 Rick 明示豁免）。
- **Paper execution**：FORBIDDEN（待 TASK-005a、30 天 forward record、REVIEW-006b、Rick 批准等條件）。
- **Live trading**：FORBIDDEN（不變）。
- **預期輸入**（已完成）：
  - `apps/monitor/` 程式碼 ✅
  - `outputs/monitor/heartbeat.parquet` sample ✅
  - `REVIEW-005_PACKET.md` + `REVIEW-005_NUMBERS.json` ✅

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


---

## REVIEW-003 — TASK-003 Baseline Attribution（等 Codex 交付）

- **狀態**：**`WAITING_INPUT`**（等 Codex 完成 TASK-003 並提交交付摘要）
- **TASK-003 狀態**：**READY_TO_IMPLEMENT**
- **完整工單**：`docs/research/codex_workorders/TASK-003_baseline_attribution.md`（v1.0，2026-05-15）
- **依賴**：TASK-001 DONE（run008）、TASK-002 DONE（20260515 cost stress，Opus REVIEW-002 PASS）

### 審查重點（Codex 交付後 Sonnet 執行）

**A. 數字一致性**
- [ ] by-symbol gross alpha 總和 ≈ run008 active period 累積 portfolio_return（±1e-6）。
- [ ] by-symbol net alpha 總和 ≈ realistic_combo active period 累積 portfolio_return_net（±1e-6）。
- [ ] by-year / by-month 各自加總等於 attribution_summary.json `net_alpha_total`（±1e-6）。

**B. Warning Gates**
- [ ] `top5_symbol_concentration`：top 5 symbols 合計 > 60% net alpha → triggered？
- [ ] `single_symbol_concentration`：任一 symbol > 25% net alpha → triggered？
- [ ] `funding_gap_concentration`：gap 7 symbols 合計 > 20% net alpha → triggered？
- [ ] `single_year_concentration`：任一年 > 70% net alpha → triggered？
- [ ] `short_side_drag`：short side net alpha 為負且 abs > 50% gross → triggered？
- [ ] `gross_net_rank_divergence`：任一 symbol rank change > 10 → triggered？

**C. Opus 三大問題（REVIEW-002 指派）**
- [ ] Funding gap 7 symbols 的 net alpha 佔比是否合理？
- [ ] alpha 是否集中於 8h interval 大幣？
- [ ] net-of-cost 排名 vs gross 排名是否一致？

**D. 可重現性**
- [ ] attribution_summary.json 含 `reproducibility_hash`。
- [ ] Log 開頭有：random seed、config hash、input data snapshot hashes（run008 + cost_stress）、git commit。

**E. 禁止項確認**
- [ ] run008 outputs 未被修改（SHA-256 unchanged）。
- [ ] 20260515 cost_stress outputs 未被修改。
- [ ] 未呼叫任何 baseline runner 或 cost stress runner。
- [ ] 未使用舊輸出 `output/crypto_cost_stress.csv`。

### 預計審查模型

```
Suggested model:   Sonnet（初審 checklist）→ Opus（若有 warning gate 大量觸發或 Opus 三大問題答案異常）
Escalation reason: Warning gate 大量觸發 / alpha 集中度極高 / 策略存廢邊緣
Opus final decision required: 視 Sonnet 初審結論而定
```

---

## REVIEW-007b — TASK-007b Weight Cap + Redistribution（2026-05-17）

- **狀態**：**`PASS`**
- **TASK-007b 狀態**：**DONE**
- **Paper trading hard gate（TASK-007b 條件）**：**已滿足**（B-1 = 選項 A）
- **Paper trading 執行**：**仍 FORBIDDEN**（剩餘 4 個前置條件未達成）；**Live trading**：**仍 FORBIDDEN**
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-007b（2026-05-17）
- **核心發現**：
  1. **Cap 20% / 15% 完全 No-op**：run008 max symbol weight = 12.5%（等權配置），兩個 cap 值從未觸發，portfolio 100% 與 baseline 相同。
  2. **Cap 10% redistribution 全面失敗**：488 個事件全部 `redistribution_has_no_room`（全 symbol 等權超限，無接收空間）；top5_conc 反惡化 95.56% → 98.69%（+3.3pp）。
  3. **結構性結論**：集中度問題在 alpha-space（DOT 長期 25%+ net alpha 貢獻），不在 weight-space（每日 weight 均等）；weight-based overlay cap 無法降低 alpha-space 集中度。
  4. 與 Opus REVIEW-007 結論完全吻合：**overlay 無法根治集中度，TASK-008 必須是 alpha-space / 策略層設計**。
- **Upstream Caveats（不擋 DONE）**：
  - N-1：初期 universe 極小（2024-04 只有 8 symbol），後期應有更多持倉數；集中度問題有時間動態特徵。
  - N-2：cap_10pct 截斷後 new_gross 比例 = 12.5%（高於 10% cap），因基準為 original gross。
- **Downstream**：
  - TASK-007b paper gate 已滿足；REVIEW-006b 可在 30 天 forward record 完成 + 3 補件落地後啟動。
  - **Weight cap + redistribution 路徑正式關閉**；集中度解決必須走 TASK-008（strategy-layer per-symbol weight cap）。
  - TASK-008 範圍確認：在 `signals / position sizing` 層加 `max_per_symbol_weight = 0.05`（5%），需重跑 baseline / cost stress / attribution，為長期任務不擋短期 paper planning。
  - TASK-007c sensitivity 維持 `TODO`。
  - TASK-004 / TASK-005 維持 `READY_TO_IMPLEMENT`。
  - Live trading 仍禁止。

---

## REVIEW-007 — TASK-007 Long-Side Variant Study（Opus final decision，2026-05-16）

- **狀態**：**`CONDITIONAL_PASS`**
- **TASK-007 狀態**：**DONE**（CONDITIONAL_PASS 不擋 DONE；spec deviation 進 follow-up TASK-007b/007c/008）
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-007（Opus 2026-05-16）
- **核心發現**：
  1. 不要砍多頭（short_only Sharpe 0.40 / max DD −49.18% = 2.5× baseline）。
  2. `high_funding_cost_filter` Pareto-dominant：Sharpe 0.96（+7.5%）、alpha retention 109.6%、long_net 改善 +2.72pp、funding cost 幾乎歸零。
  3. `combined_paper_safe_variant` 唯一同時達 long_net **轉正 +4.21%**、single_conc < 25%（19.73%）、Sharpe ≥ 0.7（0.80）—— 三條 REVIEW-003 mandatory caveat 完整滿足。
  4. `no_DOT` 悖論：移除最大貢獻者反使 top5_conc 從 95.56% 升到 116.13% —— overlay 無法根治集中度，需策略層 cap（TASK-008）。
- **Downstream**：
  - TASK-006 paper trading 規劃**可開始寫工單**，primary spec = `combined_paper_safe_variant`、secondary = `high_funding_cost_filter`。
  - TASK-007b（weight cap + redistribution）、TASK-007c（Variant C 0.01% / 0.005%-discount）、TASK-008（策略層 per-symbol weight cap）三個 follow-up 新建。
  - Paper trading 執行 gating 需要：TASK-007b 完成 + 30 天 forward + 另一輪 Opus review。
  - Live trading 仍禁止。
- **Codex 必補（不擋 DONE）**：
  - (a) 在 NUMBERS.json 補上 `short_only_max_dd_worse`（應觸發 −49.18%）與 `funding_adj_no_improvement`（應觸發 −2.29%）兩條工單規格 warning gate 的明示 trigger 欄位。
  - (b) Baseline 標籤改為「realistic_combo baseline」避免與 run008 gross Sharpe 0.9267 混淆。

---

## REVIEW-006 — Paper Trading Plan Infrastructure（Opus final decision，2026-05-16）

- **狀態**：**`PASS`**
- **TASK-006 狀態**：**DONE**
- **Paper trading 執行**：**仍 FORBIDDEN**（不變）；**Live trading**：**仍 FORBIDDEN**（不變）
- **完整審查紀錄**：`docs/research/CLAUDE_REVIEW_LOG.md` → REVIEW-006（Opus 2026-05-16）
- **核心結論**：
  1. 9/9 安全項全 PASS；safety_scan PASS / violations [] / real_order_submission_possible false / live FORBIDDEN。
  2. 3 條 mandatory overlay rule 在 2026-04-01 數值驗算通過。
  3. reproducibility hash 與 TASK-007 hash 交叉對齊（`824ff334…`）。
  4. **Sonnet B-1 proxy Sharpe −2.9012 不是策略崩潰訊號**：30-day annualized noise + `validation_basis = proxy_not_forward_execution` 明示標籤；歷史 NAV 仍 +30.7%。
  5. **Sonnet B-2 STOP_PAPER_PENDING_REVIEW 是設計成功的證據**：證明風控正確攔截自己。
- **REVIEW-006b 啟動時機**：TASK-007b 完成 + 30-day forward paper record + TASK-006 三個補件落地（`proxy_sharpe_long_window` / `fill_definition` / `funding_filter_active_this_month`）。
- **下一張最值得做的工單**：TASK-007b（weight cap + redistribution；paper 執行硬性 gate）。
