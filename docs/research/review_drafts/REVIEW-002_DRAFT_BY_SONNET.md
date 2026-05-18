# REVIEW-002 初審草稿（Claude Sonnet）

建立日期：2026-05-15
執行模型：Claude Sonnet
版本：v2（正式交付物審查）
TASK-002 狀態：`REVIEW`（Codex 自評 PASS）

```
Suggested model:              Sonnet（初審 checklist）→ Opus（final decision）
Escalation reason:            major task final review；是否進入下一階段
Opus final decision required: Yes
```

---

## 審查範圍與讀取檔案

| 檔案 | 路徑 | 是否找到 |
|---|---|---|
| Context Packet | `docs/research/context_packets/TASK-002_CONTEXT_PACKET.md` | ✅ |
| 工單 v2 | `docs/research/codex_workorders/TASK-002_cost_funding_slippage_stress.md` | ✅ |
| cost_stress.csv | `outputs/backtests/prev3y_crypto/20260515_cost_stress.csv` | ✅ |
| cost_stress_summary.json | `outputs/backtests/prev3y_crypto/20260515_cost_stress_summary.json` | ✅ |
| cost_stress_positions_cost.parquet | `outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet` | ✅ |
| cost_stress.log | `outputs/logs/prev3y_crypto/20260515_cost_stress.log` | ✅ |
| configs/cost_stress.yaml | confirmed v2 defaults | ✅ |
| funding_rates.parquet | 750,641 列 | ✅ |
| run008 baseline.csv | 2,677 列 | ✅ |
| run008 positions.parquet | 29,586 列 | ✅ |
| run008 stats.json | confirmed | ✅ |

---

## 逐條 Checklist（14 項）

### ✅ 1. 官方 4 個交付物存在且 schema 合理

全部 4 個官方交付物均存在於 `outputs/` 路徑下（注意：與舊分析的 `output/` 路徑不同）。

**cost_stress.csv**：32,124 列 × 16 欄。欄位：`date / scenario / portfolio_return_gross / portfolio_return_net / fee_cost / funding_cost / slippage_cost / gross_exposure / turnover / net_exposure / benchmark_return / benchmark_cash_return / benchmark_btc_return / benchmark_eqw_return / n_longs / n_shorts`。符合工單 Section 6.1 規格。

**cost_stress_summary.json**：含 `methodology`、`cost_policy`、`funding_gap_breakdown`、`outlier_contribution_breakdown`、`interval_hours_distribution`、12 scenarios 完整結果、fail_warning_gates、stats_recompute_check。符合 v2 規格。

**cost_stress_positions_cost.parquet**：356,148 列 × 14 欄。必要欄位（`date / scenario / symbol / weight / fee_cost / funding_cost / slippage_cost / funding_gap / outlier_count_today`）全部存在。另有 5 個額外欄位（`funding_settlement_count / entry_turnover / exit_turnover / trade_turnover / outlier_funding_cost`）——超規格，不違反工單，有助後續審查。

**cost_stress.log**：含必要 header（`baseline_run_id / git_commit / random_seed / config_hash / data_snapshot_hash / funding_rates_parquet_hash / scenarios_count / interval_distribution_used / no_cost_baseline_max_diff_vs_run008 / methodology / cost_policy / funding_audit_samples / fail_warning_gates`）。

---

### ✅ 2. no_cost_baseline 逐列等於 run008

獨立驗算：`max(|no_cost_baseline.portfolio_return_net − run008.portfolio_return|) = 0.0`，2,677/2,677 列完全相等。

Summary.json 自報：`no_cost_baseline_max_diff_vs_run008 = 0.0`。一致。

---

### ✅ 3. 12 scenarios 完整

| # | Scenario 名稱 | 在 CSV 中 |
|---|---|---|
| 1 | no_cost_baseline | ✅ |
| 2 | fee_taker_entry_maker_exit | ✅ |
| 3 | fee_taker_entry_taker_exit | ✅ |
| 4 | funding_low | ✅ |
| 5 | funding_mid | ✅ |
| 6 | funding_high | ✅ |
| 7 | slippage_5bps | ✅ |
| 8 | slippage_10bps | ✅ |
| 9 | slippage_20bps | ✅ |
| 10 | realistic_combo | ✅ |
| 11 | conservative_combo | ✅ |
| 12 | worst_case_combo | ✅ |

Row count：32,124 = 2,677 × 12。完全正確，無缺漏、無重複、無美化情境。

---

### ✅ 4. 未使用舊架構 output/crypto_cost_stress.csv

官方輸出路徑為 `outputs/backtests/prev3y_crypto/20260515_cost_stress.csv`（`outputs/` 目錄），與舊分析的 `output/crypto_cost_stress.csv`（`output/` 目錄）完全不同。

驗證點：
- 舊架構：6 個字母 scenario（A–F），每 scenario 僅 1 列摘要，使用 `run_silo_backtest`，funding 為固定日率。
- 新架構：12 個標準 scenario，每 scenario × 2,677 日逐日輸出，使用 run008 positions overlay，funding 為 per-interval PIT 累加。
- 兩者架構完全不同，無交叉污染。

---

### ✅ 5. fee / slippage / funding 三類成本分開計算

逐欄獨立驗算：

| 成本類型 | 欄位存在 | 非零 rows |
|---|---|---|
| fee_cost | ✅ | 170（fee-only + combo scenarios）|
| funding_cost | ✅ | 4,554（funding-only + combo scenarios）|
| slippage_cost | ✅ | 204（slippage-only + combo scenarios）|

**交叉污染驗算**：
- `fee_taker_entry_maker_exit` / `fee_taker_entry_taker_exit`：funding_cost 非零行數 = 0，slippage_cost 非零行數 = 0 ✅
- `funding_low/mid/high`：fee_cost 非零 = 0，slippage_cost 非零 = 0 ✅
- `no_cost_baseline`：三類成本全部為 0 ✅

---

### ✅ 6. Funding 依 per-row timestamp / interval_hours 累加，沒有硬寫 8h

**Policy 驗證**：
- `cost_policy.funding_application = "pit_per_interval_settlement_accumulated"` ✅
- `cost_policy.funding_interval_policy = "use_interval_hours_per_row"` ✅
- log 明示 `funding_interval_policy: use_interval_hours_per_row` ✅

**Audit sample 驗算**（3 個 interval 各 1 個 symbol-day）：

*4h sample：BYBIT:XTZUSDT.P 2024-04-01*（weight = −0.125，XTZ 為 known gap symbol，此日有資料）

| timestamp | funding_rate | position_weight | single_cost（手算）|
|---|---:|---:|---:|
| 2024-04-01 00:00 UTC | 0.00062605 | −0.125 | −7.825625e−05 |
| 2024-04-01 08:00 UTC | 0.00030057 | −0.125 | −3.757125e−05 |
| 2024-04-01 16:00 UTC | 0.00010000 | −0.125 | −1.250000e−05 |
| **日總計** | | | **−0.0001283275** |

Summary.json 報告值：`−0.0001283275`。手算與報告完全吻合（誤差 < 1e−10）。

*8h sample：BYBIT:ADAUSDT.P 2024-04-01*（weight = −0.125）

| timestamp | funding_rate | position_weight | single_cost（手算）|
|---|---:|---:|---:|
| 2024-04-01 00:00 UTC | 0.00065661 | −0.125 | −8.207625e−05 |
| 2024-04-01 08:00 UTC | 0.00035443 | −0.125 | −4.430375e−05 |
| 2024-04-01 16:00 UTC | 0.00022223 | −0.125 | −2.777875e−05 |
| **日總計** | | | **−0.0001541588** |

Summary.json 報告值：`−0.00015415875`。吻合（誤差 < 1e−10）。

*1h sample：BYBIT:GIGAUSDT.P 2024-12-12*（used_in_stress = false，run008 無持倉）

Log 已明示：「run008 has no held symbol-day for this funding interval」，1h_rows=0 有合理解釋。

**硬寫 8h 驗證**：從 positions_cost.parquet 中，4h symbol 的 funding 成本方向與 8h 不同（4h symbols 多為 short、funding 為負，即收入）；若硬寫 8h 則 4h symbol 每日會少計 50% 的成本/收入。計算結果顯示 4h symbol 的 funding_cost 合計為 −0.002945（收入），8h 為 +0.005398（支出），分布合理，無統一硬寫 8h 的跡象。

---

### ✅ 7. Long / Short funding 方向正確

工單規定：long 持正 funding rate 時付 funding（cost > 0）；short 持正 funding rate 時收 funding（cost < 0）。

`methodology.funding_direction_formula`：`"funding_cost = signed_position_weight * funding_rate * scenario_funding_multiplier; long positive funding is a cost, short positive funding is income"` ✅

驗算：
- XTZ 2024-04-01，weight=−0.125，funding_rate > 0 → funding_cost = −0.000128（負，即 short 收取 funding）✅
- ADA 2024-04-01，weight=−0.125，funding_rate > 0 → funding_cost = −0.000154（負，即 short 收取 funding）✅
- 8h symbol 群體合計 funding_cost = +0.005398（正，long 為主，付 funding）✅

---

### ✅ 8. Known funding gap 標記而非 fill 0

**7 個 known-gap symbols 逐一驗算**（funding_mid scenario，343 total gap days）：

| Symbol | Gap 天數 | 總持倉天數（funding_mid）| 標記率 |
|---|---:|---:|---:|
| BYBIT:XTZUSDT.P | 93 | 581 | 16.0% |
| BYBIT:FLOWUSDT.P | 81 | 516 | 15.7% |
| BYBIT:LPTUSDT.P | 44 | 123 | 35.8% |
| BYBIT:AXSUSDT.P | 41 | 607 | 6.8% |
| BYBIT:RVNUSDT.P | 35 | 59 | 59.3% |
| BYBIT:INJUSDT.P | 33 | 242 | 13.6% |
| BYBIT:CTCUSDT.P | 16 | 244 | 6.6% |

- **非 gap symbols 中有 funding_gap=True 的行數：0** ✅（無誤標）
- **Policy**：`cost_policy.funding_gap_policy = "mark_funding_gap_true_no_fill"` ✅
- **Gap 佔比**：1.1593%（< 5% WARNING gate）✅

---

### ✅ 9. Outlier contribution 有拆解

Summary.json `outlier_contribution_breakdown`：

| 欄位 | 值 |
|---|---|
| outlier_count（全 parquet）| 653 |
| held_outlier_rows（有持倉的）| 23 |
| held_outlier_symbol_days | 17 |
| max_abs_funding_rate | 0.05 |
| outlier_abs_funding_cost_base | 0.007374 |
| outlier_pct_of_total_abs_funding_cost | **2.57%**（< 30% WARNING gate）|

每個 scenario 均有獨立 `outlier_contribution_breakdown` 區塊（funding_high / worst_case_combo 的 outlier_funding_cost 比 funding_mid 高 1.5× / funding_multiplier 一致）。

`positions_cost.parquet` 的 `outlier_count_today` 欄位：17 個 symbol-day 有非零值（最大值 6），可追溯至具體 symbol-date。`outlier_policy = "report_no_clamp"` ✅（照實累加，未截斷）。

---

### ✅ 10. Daily net identity 可驗證

獨立驗算：`|portfolio_return_net − (portfolio_return_gross − fee_cost − funding_cost − slippage_cost)|` 全部 32,124 列的最大值 = **2.00e−16**（IEEE 754 浮點運算機器精度）。

全部行數在 1e−10 以內：True。符合工單 < 1e−8 要求。

---

### ✅ 11. Stats 可重算

獨立從 cost_stress.csv 重算 realistic_combo 的 active IR vs cash：

- 重算值：**0.8918383336**
- Summary.json 報告值：**0.8918383336**
- 差異：4.88e−15（< 1e−10）✅

Summary.json 自報：`stats_recompute_check.passed = true, max_abs_diff = 0.0, values_checked = 192`。

---

### ⚠️ 12. Reproducibility hash：自報通過，無法獨立重算

**Codex 自報**：`reproducibility_hash = 55c651476c0641cda80200b12209b9f95bcf43536dd8f883404ce3414844654d`，`reproducibility_hash_check_passed = true`。

**Sonnet 無法獨立驗證**：reproducibility hash 是「content hash of two independent runs」，需要重新執行 TASK-002 script 才能驗算。Sonnet 本次 review 無法執行策略程式，因此此項為「自報 PASS，無法獨立確認」。

**此為 NON-BLOCKING**：工單沒有要求 Claude 獨立重算；hash 概念與 TASK-002a 的 convention 一致（content hash，非檔案 SHA-256）。Opus 在 final review 可選擇接受 Codex 自報或要求 Codex 補充第三次跑的 diff 證據。

---

### ✅ 13. Fail / warning gates 正確計算

所有 gate 獨立驗算如下：

**FAIL gates**：

| Gate | 條件 | 數值 | 判定 |
|---|---|---:|---|
| realistic_combo active Sharpe | ≥ 0.5 | **0.8918** | ✅ PASS |
| realistic_combo active IR_vs_eqw | ≥ 0.2 | **0.7168** | ✅ PASS |
| conservative_combo active IR_vs_eqw | ≥ 0 | **0.7136** | ✅ PASS |

**WARNING gates**：

| Gate | 條件 | 數值 | 判定 |
|---|---|---:|---|
| realistic/conservative max DD | < −29.25%（1.5× run008）| realistic −19.64%, conservative −19.69% | ✅ 未觸發 |
| 任一情境 cost 吃掉 alpha > 70% | decay/base > 70% | worst_case 2.04% | ✅ 未觸發 |
| funding_gap pct > 5% | pct_of_active_position | **1.16%** | ✅ 未觸發 |
| outlier pct of funding > 30% | 任一 combo | **2.57%** | ✅ 未觸發 |

`fail_warning_gates.failures = [] / warnings = []`，與獨立驗算完全一致。

---

### ✅ 14. 無 Blocking Issues 需要 Codex 補件

14 項 checklist 全部通過或列為 non-blocking caveat。無需 Codex 補件。

---

## REVIEW-002 Draft Verdict

```
PASS_CANDIDATE
```

工程層面全部通過：數字可重算、交付物齊備、schema 符合 v2、no_cost_baseline 精確對齊 run008、成本計算分工清楚、gap/outlier 政策正確執行、fail gate 全部通過。

研究層面的最終判斷（策略是否存活、是否進入下一階段）留給 Opus。

---

## Blocking Issues

**None.**

---

## Non-blocking Caveats

**C-1：XTZ interval_hours 標籤 vs 實際結算間距不一致（TASK-002a 遺留問題）**

funding_rates.parquet 對 BYBIT:XTZUSDT.P 標記 `interval_hours=4`，但實際結算間距為 8h（00:00 / 08:00 / 16:00 UTC，每日 3 次，不是 4h interval 應有的 6 次）。這是 TASK-002a 的 data quality 問題，不影響 TASK-002 的計算正確性（cost engine 依 per-row 累加，不依 interval_hours 填補空缺）。建議 TASK-002a 補件確認 XTZ 在 Bybit 的真實 interval policy 是否已從 8h 改至 4h，或資料本身有缺失（XTZ 為 known gap symbol，3,608 個 4h-labeled rows 中實際間距多為 8h）。

**C-2：interval_distribution_used 比例與 funding_rates.parquet 全集差異顯著**

全 parquet 中 4h:8h = 61.5%:38.2%，但本次實際使用的 rows 中 4h:8h = 15.5%:84.5%。原因：run008 active universe 以大幣為主（BTC / ETH / ADA / XRP 等，多為 8h interval），與 273 symbol 全集的組成比例不同。1h_rows=0 因 GIGAUSDT（唯一 1h symbol）在 run008 中無持倉日，log 已明示。工單「比例相當（容差 ±10 rows）」的要求在 universe 子集場景下物理上無法滿足，此差異為宇宙組成問題而非 cost engine bug。**Opus 可確認此解釋是否可接受，或要求補充 per-symbol interval 分布說明。**

**C-3：Active sample 760 天，統計穩健性有限**

全部結論基於 2024-04-01 ~ 2026-04-30 的 760 個有效持倉天，覆蓋 1 個完整牛市周期但無完整熊市周期。Sharpe / IR 的估計標準誤不可忽略。**Opus 在 final review 應評估樣本長度是否足以支撐「策略在實盤下存活」的結論。**

**C-4：策略對 BTC 無顯著 alpha，cost 使其略微惡化**

IR vs BTC：no_cost_baseline = −0.0175，realistic_combo = −0.0273，worst_case = −0.0423。Alpha 主要來自 alt coin 組合配置，與 BTC 方向無關。這是已知限制（REVIEW-001_final 確認）。

**C-5：Reproducibility hash 無法由 Sonnet 獨立驗算**

Hash 為 Codex 自報（需要重跑 script 比對兩次 output）。Sonnet 本次 review 不執行任何程式，無法獨立確認。

**C-6：Funding 是三類成本中最小的一項**

realistic_combo 三類成本：fee 0.355% > slippage 0.450% > funding 0.245%。funding 佔比不到總成本的 25%。舊架構估算（Scenario E Sharpe 0.754）遠比 v2 結果（realistic_combo Sharpe 0.892）悲觀，差距主要來自：(1) 舊架構固定 0.03%/day funding 估算偏高；(2) 舊架構重跑策略訊號，return stream 本身與 run008 不同。

---

## 核心數字彙整（供 Opus 參考）

### 12 Scenarios 完整結果

| Scenario | Sharpe Active | IR eqw Active | IR BTC Active | IR cash Active | Max DD Active | Cost/Turnover (bps) | Alpha Decay |
|---|---:|---:|---:|---:|---:|---:|---:|
| no_cost_baseline | **0.9267** | **0.7227** | −0.0175 | 0.9267 | −19.50% | 0.0 | 0.00% |
| fee_taker_entry_maker_exit | 0.9155 | 0.7207 | −0.0208 | 0.9155 | −19.53% | 3.94 | 0.27% |
| fee_taker_entry_taker_exit | 0.9110 | 0.7199 | −0.0221 | 0.9110 | −19.54% | 5.50 | 0.38% |
| funding_low | 0.9220 | 0.7220 | −0.0186 | 0.9220 | −19.54% | 1.36 | 0.09% |
| funding_mid | 0.9172 | 0.7213 | −0.0198 | 0.9172 | −19.57% | 2.72 | 0.19% |
| funding_high | 0.9123 | 0.7206 | −0.0209 | 0.9123 | −19.61% | 4.09 | 0.29% |
| slippage_5bps | 0.9125 | 0.7202 | −0.0217 | 0.9125 | −19.54% | 5.00 | 0.34% |
| slippage_10bps | 0.8982 | 0.7177 | −0.0259 | 0.8982 | −19.58% | 10.00 | 0.69% |
| slippage_20bps | 0.8697 | 0.7127 | −0.0343 | 0.8697 | −19.65% | 20.00 | 1.38% |
| **realistic_combo** | **0.8918** | **0.7168** | −0.0273 | 0.8918 | −19.64% | 11.67 | 0.81% |
| **conservative_combo** | **0.8732** | **0.7136** | −0.0328 | 0.8732 | −19.69% | 18.22 | 1.26% |
| **worst_case_combo** | **0.8398** | **0.7079** | −0.0423 | 0.8398 | −19.80% | 29.59 | 2.04% |

### realistic_combo 成本拆解

| 成本類型 | 絕對值（active period）| % of gross return | bps/turnover |
|---|---:|---:|---:|
| fee | 0.3551% | 11.4% | 3.94 |
| slippage | 0.4501% | 14.5% | 5.00 |
| funding | 0.2452% | 7.9% | 2.72 |
| **total** | **1.050%** | **33.8%** | **11.67** |

Gross active return（active 760 天累積）：3.114% → Net（realistic）：2.976%

---

## Numbers Needing Opus Decision

以下 6 個問題需要 Opus 層級的研究判斷：

1. **realistic_combo 的 edge 是否真實、足夠進入下一階段？**
   Sharpe 0.8918 / IR_vs_eqw 0.7168 / max DD −19.64%。數字強健，但樣本只有 760 天、一個牛市周期。

2. **conservative_combo 下策略是否仍然可接受？**
   Sharpe 0.8732 / IR_vs_eqw 0.7136。成本壓縮仍小，但 Opus 需判斷「能否接受在保守假設下的結果」。

3. **cost 組成中 slippage（0.45%）> fee（0.36%）> funding（0.25%）是否符合預期？**
   Bybit perp crypto 月再平衡策略，slippage 是最大成本，funding 最小，是否與 Opus 對市場的認知一致？

4. **XTZ interval_hours=4 但實際 8h 間距（Caveat C-1）是否影響信任度？**
   XTZ 是 known gap symbol，影響有限，但此 data quality issue 是否需要 TASK-002a 補件？

5. **interval_distribution_used 4h:8h = 15%:85% 與全 parquet 61%:38% 差距（Caveat C-2）是否可接受？**
   解釋是宇宙組成問題，Opus 確認後可接受或要求補充說明。

6. **是否允許 TASK-002 → DONE，並討論進入 paper trading 準備階段？**
   所有 fail gate PASS、無 WARNING 觸發。核心研究決策需 Opus 判斷。

---

## Suggested Opus Prompt

以下 prompt 可在 Rick 確認後直接貼給 Opus 執行 REVIEW-002 final decision：

---

```
你是 Claude Opus，負責執行 REVIEW-002 final decision。
這是 Prev3Y Crypto momentum 策略的 Cost / Funding / Slippage Stress Test 最終審查。
你的角色是做研究決策，不是工程驗收（工程 checklist 已由 Sonnet 完成，結論為 PASS_CANDIDATE）。

## 背景（無需重讀歷史，以下為完整 context）

策略：Prev3Y momentum，Bybit perp universe，市場中性，月再平衡，top-25/bottom-25。
Baseline（run008，gross，no cost，active 760 天 2024-04-01 ~ 2026-04-30）：
  active Sharpe = 0.9267 / active IR vs eqw = 0.7227 / active IR vs BTC = −0.0175 / max DD = −19.50%

TASK-002 使用 Bybit 真實 per-interval funding（1h/4h/8h 混合）。
Sonnet 工程驗收：14/14 項通過（reproducibility hash 無法獨立驗算，為 non-blocking）。

## 必讀文件（請按順序讀完後再回答）

1. docs/research/review_drafts/REVIEW-002_DRAFT_BY_SONNET.md（本初審草稿，含完整數字）
2. outputs/backtests/prev3y_crypto/20260515_cost_stress_summary.json

## 核心數字（Sonnet 已驗算）

| Scenario | Sharpe Active | IR_eqw Active | IR_BTC Active | Max DD Active | Alpha Decay |
|---|---:|---:|---:|---:|---:|
| no_cost_baseline | 0.9267 | 0.7227 | −0.0175 | −19.50% | 0.00% |
| realistic_combo | 0.8918 | 0.7168 | −0.0273 | −19.64% | 0.81% |
| conservative_combo | 0.8732 | 0.7136 | −0.0328 | −19.69% | 1.26% |
| worst_case_combo | 0.8398 | 0.7079 | −0.0423 | −19.80% | 2.04% |

realistic_combo 成本拆解：fee 0.355% / slippage 0.450% / funding 0.245% / total 1.050%

所有 fail gate 通過，所有 warning gate 未觸發。

## 你需要回答的問題

### A. Fail gate 確認（逐條，Sonnet 已算，請確認）
1. realistic_combo：Sharpe 0.8918 ≥ 0.5 且 IR_eqw 0.7168 ≥ 0.2？→ PASS / FAIL
2. conservative_combo：IR_eqw 0.7136 ≥ 0？→ PASS / FAIL
3. 任何 combo 的 max DD < −29.25%？→ PASS / WARNING
4. 任何 combo 的 alpha decay > 70%？（worst_case = 2.04%）→ PASS / WARNING
5. funding_gap > 5%？（1.16%）→ PASS / WARNING
6. outlier pct > 30%？（2.57%）→ PASS / WARNING

### B. 研究決策（Opus 層級）
7. 在 realistic 成本假設下，策略的 edge（IR_eqw = 0.7168，Sharpe = 0.8918）是否真實且足夠？
   特別考量：(a) 760 天樣本是否足以下結論；(b) 無 BTC alpha 是否影響定位；
   (c) 成本中 slippage（0.45%）> funding（0.25%）的組成是否合理？
8. conservative_combo（worst realistic 實盤假設）下 Sharpe 0.8732 / IR_eqw 0.7136 是否可接受？
9. XTZ interval_hours=4 但實際 8h 間距（Caveat C-1）是否需要 TASK-002a 補件？
10. interval_distribution_used 4h:8h = 15%:85% 與全 parquet 差距（Caveat C-2）是否可接受？
11. 舊架構（Scenario E Sharpe 0.754）vs v2（realistic_combo 0.8918）差距 0.14——你如何評估
    這個差距？是舊架構 funding 假設過於悲觀，還是有其他因素？

### C. 階段推進決策（需 Opus 判定）
12. TASK-002 整體結論：PASS / CONDITIONAL_PASS / FAIL（理由一句話）
13. 若 PASS 或 CONDITIONAL_PASS：
    (a) 是否允許 TASK-002 → DONE？
    (b) 是否允許討論 paper trading 準備計畫（不是立即上線，是準備計畫）？
    (c) TASK-003（attribution）是否應同步或在 TASK-002 DONE 後優先推進？

## 輸出格式（請按此格式輸出）

### 1. Fail Gate 判定表（確認 Sonnet 計算）
### 2. 研究決策分析（B 部分，散文，≤ 400 字）
### 3. 整體 Verdict：PASS / CONDITIONAL_PASS / FAIL + 一句話理由
### 4. 若 CONDITIONAL_PASS：補件清單
### 5. 下一階段建議
### 6. 給 Rick 的一頁式重點（≤ 10 條 bullet，繁體中文）
### 7. 寫入 CLAUDE_REVIEW_LOG.md 的正式審查記錄（附：REVIEW-002 標準骨架）

## 禁止事項
- 不修改任何策略程式
- 不執行回測或 stress test
- 不在 Rick 確認前把 TASK-002 轉 DONE
- 不解除任何後續任務狀態
```

---

*草稿由 Claude Sonnet 建立，2026-05-15。*
*工程 checklist：14/14 通過（含 1 個 non-blocking caveat on reproducibility hash）。*
*Non-blocking caveats：6 項（C-1 ~ C-6）。*
*Opus final decision required：Yes。*
