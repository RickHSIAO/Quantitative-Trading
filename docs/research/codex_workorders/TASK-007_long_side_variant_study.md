# TASK-007 — Long-Side Variant Study

- **狀態**：TODO
- **Owner**：Codex
- **預估**：M（2–3 天）
- **依賴**：TASK-003 DONE（attribution 已確認 long-side 問題）；TASK-001 DONE（run008）；TASK-002 DONE（cost stress）
- **工單版本**：v1.0（2026-05-15，由 Claude Sonnet 撰寫）
- **觸發原因**：Opus REVIEW-003 CONDITIONAL_PASS，明確指派 TASK-007 研究 long-side 結構性虧損。

---

## 1. 任務一句話

基於 run008 既有持倉資料，不重新執行策略訊號，分析四個持倉調整變體（short-only、long-only、funding-adjusted、single-symbol-capped），量化 long-side 負 alpha 的來源與可行的修正方向，為 paper trading 規劃提供 position sizing 依據。

---

## 2. 任務目的

TASK-003 attribution 揭露的兩個結構性問題：

**問題 A — Long-side 系統性虧損**
- Long side net alpha：−5.10%（gross −2.04%）
- 全部 net alpha 來自空頭（+33.65%）；多頭扣除 funding cost 後持續虧損
- BTC/ETH/LINK 等大市值多頭因 perpetual contango 被 funding 完全蠶食

**問題 B — 極度集中**
- Top 5 symbols = 95.56% of net alpha（per workorder 公式：/net_alpha_total）
- DOT 單一空頭 = 25.45%（超過 25% single-symbol threshold）
- 持倉 90 個 symbol，但有效 alpha 集中在 5 個

本任務回答：
1. 若完全移除多頭部位（short-only），策略績效與風險如何？
2. 若完全移除空頭部位（long-only），損失多少？這些「多頭」在去掉 funding cost 後是否仍為負？
3. 若對高 funding rate 多頭打折（funding-adjusted signal），可以改善多頭端多少？
4. 若對單一 symbol 持倉設 cap（concentration-capped），對績效與集中度的影響？

四個變體的結果將直接輸入 TASK-006 paper trading 規劃（risk limit 設計）。

---

## 3. 為什麼重要

- **Live trading 前必須了解 long-side 的本質**：若 long side 本質是「被動接受 funding cost 的 beta」，paper trading 應考慮 long-only size cap 或完全停用多頭。
- **Concentration 問題尚未解決**：top 5 = 95.56% 在 paper trading 中代表高度個股風險；需要了解 cap 後的績效損耗有多大，才能決定 cap 值。
- **Funding contango 問題是系統性的**：BTC/ETH/LINK 在牛市中 funding 持續為正，momentum 訊號把它們排入多頭，但每一輪都虧錢。需要量化：若把高 funding rate 多頭排除，能減少多少損失？
- 此研究為 TASK-006（paper trading 規劃）提供最關鍵的 position sizing 依據。

---

## 4. 範圍邊界

### ✅ Do（允許做）

- 讀取 run008 positions.parquet，用**持倉過濾 / 持倉調整**的方式模擬四個變體。
- 用 prices_daily.parquet 重建每日 symbol return（與 TASK-003 attribution 相同的方法論）。
- 用 TASK-002 cost_stress_positions_cost.parquet 取 realistic_combo 的 per-symbol cost。
- 對四個變體分別計算 Sharpe / IR_vs_cash / max DD / net alpha / cost breakdown。
- 在 NOTE 和 log 中標記觀察與結構性推論，供 Claude 審查使用。
- 對 paper trading 的 position sizing 提供量化建議範圍（非決策，是數字）。

### ❌ Don't（禁止做）

- **不可重新執行策略訊號或 ranking 邏輯**（不能產生新的 run0XX baseline）。
- **不可修改 run008 任何輸出**（positions.parquet / baseline.csv / stats.json）。
- **不可修改 TASK-002 任何輸出**（cost_stress.csv / summary.json / positions_cost.parquet）。
- **不可修改 TASK-003 任何輸出**（attribution_*）。
- **不可修改 raw data**（data/ 目錄下任何檔案）。
- **不可修改策略程式**（src/ 目錄）。
- **不可自行將 TASK-007 轉 DONE**：完成後狀態改為 `REVIEW`，等 Claude 審查。
- **不可批准 paper trading 或 live trading**：本任務只做研究分析，不做執行決策。
- **不可使用舊輸出 `output/crypto_cost_stress.csv`**。

---

## 5. 輸入檔案（read-only）

| 路徑 | 說明 |
|---|---|
| `outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet` | 每日持倉 weight，含 `date, symbol, weight, signal_rank` |
| `outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv` | 每日 gross portfolio return（active period 760 天）|
| `outputs/backtests/prev3y_crypto/20260513_run008_stats.json` | Sharpe / IR / max DD 等基準數字 |
| `outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet` | 每日每 symbol cost 細項（取 `realistic_combo`）|
| `outputs/backtests/prev3y_crypto/20260515_cost_stress_summary.json` | TASK-002 摘要，含 realistic_combo 總覽 |
| `outputs/attribution/prev3y_crypto/20260515_attribution_by_symbol.csv` | TASK-003 symbol attribution，含 side / interval / funding_gap |
| `outputs/attribution/prev3y_crypto/20260515_attribution_summary.json` | TASK-003 摘要，含 warning gate 結果與 cost breakdown |
| `data/crypto/prices_daily.parquet` | 日線 OHLCV，用於重建 symbol daily return |
| `data/crypto/funding_rates.parquet` | Bybit funding rate（per-interval），用於辨識高 funding 多頭 |

**主要計算依據**（與 TASK-003 一致）：
- Symbol daily return 從 `prices_daily.parquet` + `run008_positions.parquet` 重建
- Per-symbol cost 取自 `cost_stress_positions_cost.parquet` 的 `realistic_combo` 列
- Return dating：`positions.date + 1 day = return_date`（繼承 TASK-003 methodology）

---

## 6. 四個研究變體定義

### Variant A：Short-Only

**定義**：將 run008_positions.parquet 中所有 `weight > 0` 的多頭列設為 0，空頭持倉保持不變（weight < 0），重新計算各日 portfolio return。

**不需要**：重新跑策略引擎；只需過濾現有持倉。

**研究問題**：
- 移除多頭後，Sharpe / IR / max DD 如何變化？
- 多頭的 cost 負擔（funding + fee + slippage）消失後，net alpha 是否提升？
- Short-only 策略的最大 drawdown 是否小於 run008（去除多頭可能降低 Nov-Dec 2024 軋倉衝擊的對沖效果）？

**注意**：短空 portfolio 的 gross exposure 定義需明確說明（用 abs(weight) 還是 -weight 計算 IR）；在 log 中標記。

---

### Variant B：Long-Only

**定義**：將 run008_positions.parquet 中所有 `weight < 0` 的空頭列設為 0，多頭持倉保持不變（weight > 0）。

**研究問題**：
- Long-only 策略在 gross 口徑是否為正？（TASK-003 顯示 gross −2.04%）
- Long-only 策略扣除 funding + fee + slippage 後 net 如何？
- Long-only 的前 10 名持股（DOT 除外，它是純空頭）是哪些？Alpha 來源是否集中？

---

### Variant C：Funding-Adjusted Long-Side（高 funding 多頭打折）

**定義**：
1. 計算每個 symbol 在 active period 的平均 funding rate（從 `funding_rates.parquet`）。
2. 對平均 funding rate > **threshold_high**（建議先用 0.01%/8h 等值，即 ~4.56% 年化）的多頭 symbol，將其 weight 乘以 **discount_factor**（建議先用 0.0，即完全排除）。
3. 空頭持倉不調整。
4. 產出兩組結果：（a）threshold = 0.01%/8h，discount = 0（完全排除高 funding 多頭）；（b）threshold = 0.005%/8h，discount = 0.5（部分打折）。

**研究問題**：
- 排除 BTC/ETH/LINK 等高 funding 多頭後，long side net alpha 是否轉正？
- Funding-adjusted 後，top 5 symbol concentration 如何變化？
- Cost drag 中的 funding 成分減少多少？

**注意**：此 variant 改變了 portfolio weight，net exposure 可能不再為零（非市場中性）。請在 log 明確標記 net exposure 偏移，並計算新的 gross/net exposure。

---

### Variant D：Single-Symbol-Capped（集中度上限）

**定義**：
1. 每日計算每個 symbol 的 |weight| 占當日 portfolio gross exposure 的比例。
2. 對 |weight| 占比超過 **cap** 的 symbol，將 weight 截斷至 cap（空頭維持負號）。
3. 截斷後的剩餘 weight 等比例補回其他 symbol（使 gross exposure 不變）。
4. 產出三個 cap 值：cap = 20%、cap = 15%、cap = 10%。

**研究問題**：
- Cap 15% / 10% 後，top 5 concentration（/net_alpha_total）降至多少？DOT 的個別佔比是否低於 25%？
- Cap 對 Sharpe / IR / max DD 的影響是正向還是負向？
- 哪些 symbol 在哪些日期被截斷？截斷的累積 weight 有多少？

---

## 7. 輸出檔案

所有輸出寫入 `outputs/variant_study/prev3y_crypto/`，檔名前綴統一使用執行日期（`YYYYMMDD`）。

| 路徑 | 格式 | 說明 |
|---|---|---|
| `<YYYYMMDD>_variant_A_short_only_daily.csv` | CSV | 每日 gross / net portfolio return（short-only）|
| `<YYYYMMDD>_variant_A_short_only_stats.json` | JSON | Sharpe / IR / max DD / net alpha / cost breakdown |
| `<YYYYMMDD>_variant_B_long_only_daily.csv` | CSV | 每日 gross / net portfolio return（long-only）|
| `<YYYYMMDD>_variant_B_long_only_stats.json` | JSON | 同上 |
| `<YYYYMMDD>_variant_C_funding_adj_daily.csv` | CSV | 兩組 funding-adjusted 結果（並列兩個 scenario 欄位）|
| `<YYYYMMDD>_variant_C_funding_adj_stats.json` | JSON | 兩組摘要 + 被排除 / 打折 symbol 清單 |
| `<YYYYMMDD>_variant_D_capped_daily.csv` | CSV | 三個 cap 值的每日 return（並列）|
| `<YYYYMMDD>_variant_D_capped_stats.json` | JSON | 三個 cap 值的摘要 + 被截斷 symbol / 日期統計 |
| `<YYYYMMDD>_variant_comparison_summary.json` | JSON | 四個變體 + run008 baseline 的並列比較表 |
| `<YYYYMMDD>_variant_paper_trading_sizing.json` | JSON | 基於 Variant C/D 的 paper trading position sizing 建議數字（不是決策）|
| `outputs/logs/prev3y_crypto/<YYYYMMDD>_variant_study.log` | log | 執行紀錄，含 input hashes / git commit / 各變體的 WARNING 清單 |

### `_variant_comparison_summary.json` 必含欄位

```json
{
  "run_date": "YYYYMMDD",
  "baseline_run008": {
    "sharpe_active": 0.9267,
    "ir_vs_cash_active": 0.9267,
    "ir_vs_eqw_active": 0.7227,
    "max_dd": -0.195,
    "gross_alpha": 0.2958,
    "net_alpha": 0.2853,
    "short_net_alpha": 0.3365,
    "long_net_alpha": -0.0510,
    "top5_concentration_workorder": 0.9556,
    "top1_concentration_workorder": 0.2545
  },
  "variant_A_short_only": { ... },
  "variant_B_long_only": { ... },
  "variant_C_funding_adj_0pct": { ... },
  "variant_C_funding_adj_50pct": { ... },
  "variant_D_cap20pct": { ... },
  "variant_D_cap15pct": { ... },
  "variant_D_cap10pct": { ... },
  "methodology": {
    "return_dating": "positions.date + 1 day = return_date",
    "cost_scenario": "realistic_combo",
    "annualization_factor": 365.25,
    "std_ddof": 1
  },
  "reproducibility_hash": "...",
  "git_commit": "..."
}
```

### `_variant_paper_trading_sizing.json` 必含欄位

```json
{
  "analysis_basis": "TASK-007 variant study, not a trading decision",
  "findings": {
    "short_only_sharpe": ...,
    "short_only_vs_baseline_sharpe_delta": ...,
    "funding_adj_long_side_net_alpha": ...,
    "cap15pct_top5_concentration": ...,
    "cap15pct_vs_baseline_sharpe_delta": ...
  },
  "sizing_suggestions": {
    "max_single_symbol_weight_pct": "see Variant D cap results",
    "long_side_enabled": "see Variant C funding_adj results",
    "note": "These are quantitative inputs for TASK-006 paper trading planning. Final decision requires Opus review and Rick approval."
  }
}
```

---

## 8. 方法論規範

以下規範繼承自 TASK-003，必須一致：

| 項目 | 規範 |
|---|---|
| Annualization | 365.25 |
| Std ddof | 1 |
| IR formula | `mean(net_return - benchmark) / std(net_return - benchmark, ddof=1) * sqrt(365.25)` |
| Active period | `gross_exposure > 0`，共 760 天（2024-04-01 ~ 2026-04-30） |
| Benchmark | Primary = cash（benchmark_return = 0.0）；輔助：eqw、BTC |
| Return dating | `positions.date + 1 day = return_date` |
| Net formula | `net = gross - fee_cost - slippage_cost - funding_cost`（per symbol，取 realistic_combo）|
| Cost source | `cost_stress_positions_cost.parquet` 的 realistic_combo 列 |

**Variant A/B 的 portfolio-level 重建**：
- 每日 portfolio gross return = sum(weight_i × return_i) over held symbols（過濾後）
- Per-symbol cost 直接從 positions_cost.parquet 取對應 symbol-day 的 realistic_combo cost 欄位
- 若某 symbol-day 在 variant 中 weight = 0（被過濾），其 cost 也設為 0

**Variant C 的 weight 調整**：
- 調整後 weight 必須重新對 gross exposure 做正規化，保持 portfolio sum(|weight|) 不變
- 若 threshold 排除了所有多頭 symbol 的某一天，當日 long side weight = 0（不補空頭）

**Variant D 的截斷與分配**：
- 截斷後，剩餘 weight 按原始 |weight| 比例等比例補回同方向（long 補 long，short 補 short）
- 若所有 long symbol 都在 cap 以下，不需調整
- 截斷邏輯每日獨立計算（不跨日攤平）

---

## 9. 驗收標準

- [ ] 全部 11 個輸出檔存在且 schema 正確。
- [ ] `_variant_comparison_summary.json` 的 `baseline_run008` 數字與 run008_stats.json 一致（±1e-6）。
- [ ] Variant A/B 的每日 net return 之和與 TASK-003 attribution 的 by-side 結果接近（比較方向，不要求完全一致，因 variant 調整了 gross exposure）。
- [ ] Variant D 的所有 cap 值下，每日截斷後的 sum(|weight|) ≤ 原始 run008 同日 sum(|weight|) × (1 + 1e-6）。
- [ ] Log 開頭列出：random seed（若有隨機成分）、input file SHA-256（run008_positions、cost_stress_positions_cost、prices_daily）、git commit。
- [ ] Log 結尾列出所有觸發的 WARNING。
- [ ] `_variant_paper_trading_sizing.json` 存在且明確標注「analysis basis, not a trading decision」。
- [ ] 可重現性：同 input 跑兩次，`_variant_comparison_summary.json` 的 reproducibility_hash 相同。

---

## 10. Fail / Warning Gate

### Warning Gates（標記 WARNING，不停止）

| Gate | 觸發條件 |
|---|---|
| `short_only_max_dd_worse` | Variant A short-only max DD < −25%（比 run008 −19.5% 顯著惡化）|
| `long_only_net_negative` | Variant B long-only net alpha < 0（預期此 gate 會觸發；需量化損失大小）|
| `funding_adj_no_improvement` | Variant C funding-adjusted long side net alpha 仍 < −2%（改善效果不顯著）|
| `cap10_sharpe_drop` | Variant D cap=10% 的 Sharpe 比 run008 下降超過 30%（代價太高）|
| `concentration_not_reduced` | Variant D cap=15% 後 top5 concentration（/net_alpha_total）仍 > 70% |

### Fail Gates（觸發則輸出不完整，停止）

| Gate | 觸發條件 |
|---|---|
| `baseline_mismatch` | `baseline_run008` 欄位與 run008_stats.json 數字不符（誤差 > 1e-6）|
| `missing_output_files` | 任一必要輸出檔案缺失 |
| `schema_error` | 輸出檔案欄位缺失或型別錯誤 |

---

## 11. 禁止修改範圍

- **run008 四件套**（baseline.csv / positions.parquet / stats.json / data_quality.*）：read-only
- **20260515 TASK-002 outputs**（cost_stress.csv / summary.json / positions_cost.parquet）：read-only
- **20260515 TASK-003 attribution outputs**（attribution_*.csv / attribution_summary.json）：read-only
- **`data/` 目錄下所有 raw 檔**（prices_daily.parquet / funding_rates.parquet）：read-only
- **策略程式**（`src/` 下任何 `.py`，attribution 模組除外）：不可修改
- **`configs/` 下任何 yaml**：不可修改
- **任何 baseline runner / cost stress runner**：不可呼叫
- **舊輸出 `output/crypto_cost_stress.csv`**：禁止使用

---

## 12. 完成後回報格式

```
TASK-007 Long-Side Variant Study — Codex 交付摘要（YYYY-MM-DD）

run_date: YYYYMMDD
input_hashes:
  run008_positions_parquet: <SHA-256>
  cost_stress_positions_cost_parquet: <SHA-256>
  prices_daily_parquet: <SHA-256>
git_commit: <hash>

=== Baseline（run008 realistic_combo, for reference）===
Sharpe_active:      0.9267
net_alpha:          28.53%
short_net:         +33.65%
long_net:           -5.10%
top5_concentration: 95.56%（/net_alpha_total）
max_DD:            -19.50%

=== Variant A：Short-Only ===
Sharpe_active:      ____
IR_vs_cash_active:  ____
max_DD:             ____
net_alpha:          ____%
top5_concentration: ____%（/net_alpha_total）
WARNING triggered:  [ ] short_only_max_dd_worse

=== Variant B：Long-Only ===
Sharpe_active:      ____
IR_vs_cash_active:  ____
max_DD:             ____
net_alpha:          ____%
WARNING triggered:  [ ] long_only_net_negative  → 損失：____%

=== Variant C：Funding-Adjusted（threshold=0.01%/8h, discount=0）===
long_side_net_alpha_before: -5.10%
long_side_net_alpha_after:  ____%
excluded_long_symbols:      [<list>]
net_alpha_total:            ____%
WARNING triggered:  [ ] funding_adj_no_improvement

=== Variant C：Funding-Adjusted（threshold=0.005%/8h, discount=0.5）===
long_side_net_alpha_after:  ____%
net_alpha_total:            ____%

=== Variant D：Capped（cap=20% / 15% / 10%）===
              cap=20%    cap=15%    cap=10%
Sharpe:       ____       ____       ____
net_alpha:    ____%      ____%      ____%
top5_conc:    ____%      ____%      ____%（/net_alpha_total）
max_DD:       ____       ____       ____
WARNING:  [ ] concentration_not_reduced（cap=15%）
          [ ] cap10_sharpe_drop

=== Fail Gates ===
baseline_mismatch:      PASS / FAIL
missing_output_files:   PASS / FAIL
schema_error:           PASS / FAIL

=== Paper Trading Sizing Inputs（非決策）===
建議 max single-symbol weight cap：____%（based on Variant D）
Long side 建議：啟用 / 縮減（____%）/ 停用（based on Variant C）
Short-only 策略 Sharpe vs baseline：+ / − ____%

=== 可重現性 ===
reproducibility_hash: <hash>

=== 輸出檔案清單 ===
- outputs/variant_study/prev3y_crypto/<YYYYMMDD>_variant_A_short_only_daily.csv
- outputs/variant_study/prev3y_crypto/<YYYYMMDD>_variant_A_short_only_stats.json
- outputs/variant_study/prev3y_crypto/<YYYYMMDD>_variant_B_long_only_daily.csv
- outputs/variant_study/prev3y_crypto/<YYYYMMDD>_variant_B_long_only_stats.json
- outputs/variant_study/prev3y_crypto/<YYYYMMDD>_variant_C_funding_adj_daily.csv
- outputs/variant_study/prev3y_crypto/<YYYYMMDD>_variant_C_funding_adj_stats.json
- outputs/variant_study/prev3y_crypto/<YYYYMMDD>_variant_D_capped_daily.csv
- outputs/variant_study/prev3y_crypto/<YYYYMMDD>_variant_D_capped_stats.json
- outputs/variant_study/prev3y_crypto/<YYYYMMDD>_variant_comparison_summary.json
- outputs/variant_study/prev3y_crypto/<YYYYMMDD>_variant_paper_trading_sizing.json
- outputs/logs/prev3y_crypto/<YYYYMMDD>_variant_study.log

=== 遇到的問題 / 異常 ===
（若有，逐條列出）
```

---

## 13. NOTE 區

### NOTE-1：不可重新執行訊號引擎
四個 variant 全部基於 run008_positions.parquet 的既有 weight，只做過濾與 weight 調整。不可呼叫任何 baseline runner 或訊號計算函數。若需要某 symbol 的 return 序列，從 prices_daily.parquet 計算 open-to-open return（與 TASK-003 return dating 一致）。

### NOTE-2：Short-Only Portfolio 的 Benchmark
Short-only 策略的 benchmark 仍使用 cash（benchmark_return = 0.0），與 run008 一致。若 Codex 認為需要補充 short-only specific benchmark（如 short index），在 log 中以 NOTE 標記，但正式計算仍用 cash benchmark。

### NOTE-3：Variant C 的 Funding Rate 定義
「平均 funding rate」定義為：在 active period 760 天內，每個 symbol 的所有 funding_rates.parquet 列的 `funding_rate` 算術平均值（不加權 interval_hours）。計算 threshold 時換算成 8h 等效值（`avg_rate * 8 / interval_hours` if needed）。若有更合適的換算方式，請在 log NOTE 說明。

### NOTE-4：Variant D 的截斷分配邏輯的 Edge Cases
- 若某日只有 1 個多頭 symbol 且其 |weight| > cap：截斷至 cap，剩餘不分配（接受 gross exposure 略微下降）。
- 若截斷後所有 symbol 均 ≤ cap 但仍有累積剩餘：等比例補回，直到精確對齊（浮點誤差 < 1e-10 視為通過）。
- 每個 edge case 在 log 中標記日期與 symbol，供 Claude 審查。

### NOTE-5：Paper Trading Sizing 建議範圍的意義
`_variant_paper_trading_sizing.json` 提供的數字是純量化輸入，**不是交易決策**。最終是否採用 short-only、funding-adjusted、或 cap 設定，需由 Opus final review（REVIEW-007）與 Rick 確認後才能納入 TASK-006 paper trading 規劃。Codex 不可在本任務中做「可以 paper trade」的推論。

### NOTE-6：TASK-007 不轉 DONE
完成後狀態改為 `REVIEW`，在 CODEX_TASK_QUEUE.md 下方貼交付摘要。等 Claude REVIEW-007 通過後，才由 Claude 標記 DONE 並決定 TASK-006 paper trading 規劃的 position sizing 參數範圍。

### NOTE-7：TASK-003 Codex 必補項目
Opus REVIEW-003 要求 Codex 在下一版 attribution 補三件事，這些**不在 TASK-007 範圍內**，但應在 TASK-007 完成後的下一輪更新中處理：
- (a) concentration gate 並列輸出 `/net_alpha_total` 與 `/sum_abs_net` 兩個分母的值
- (b) 補 `long_side_drag` warning gate（當 long net alpha < 0 且 abs(long net) > X% gross 時觸發）
- (c) attribution script 自動產出 review packet（含關鍵數字的 markdown 摘要）

---

*工單版本 v1.0｜撰寫：Claude Sonnet｜日期：2026-05-15*
*觸發依據：Opus REVIEW-003 CONDITIONAL_PASS（2026-05-15）；long-side 結構性虧損 + 集中度問題指派 TASK-007*
*參考：docs/research/review_drafts/REVIEW-003_DRAFT_BY_SONNET.md；outputs/attribution/prev3y_crypto/20260515_attribution_summary.json*
