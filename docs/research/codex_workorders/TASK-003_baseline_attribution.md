# TASK-003 — Baseline Attribution 分析

- **狀態**：TODO
- **Owner**：Codex
- **預估**：M（2–3 天）
- **依賴**：TASK-001 DONE（run008）、TASK-002 DONE（20260515 cost stress，Opus REVIEW-002 PASS）
- **工單版本**：v1.0（2026-05-15，由 Claude Sonnet 撰寫）

---

## 1. 任務一句話

拆解 run008 baseline 與 20260515 cost stress 的 alpha 來源，確認策略 edge 是否由少數 symbol / 特定期間 / 特定 side / 特定 cost 類型主導，並產出可重現的 attribution report。

---

## 2. 任務目的

TASK-002 已確認成本未殺死策略，Opus REVIEW-002 裁定為 PASS。  
但「成本後仍有正 alpha」≠「alpha 穩健且分散」。

本任務回答以下問題：

- Alpha 集中在哪幾個 symbol？若 top 5 symbol 移除後 alpha 消失 → 邊緣策略。
- Alpha 是否跨年分佈？若只由 2024 年底 BTC 牛市期間貢獻 → 市況依賴。
- Long side 與 short side 各自貢獻如何？若 short side 持續拖累 → 方向性問題。
- Cost 結構：fee / slippage / funding 各吃多少 alpha？哪一類最需要優化？
- Funding gap 的 7 個 symbol（XTZ/FLOW/LPT/AXS/RVN/INJ/CTC）有無不當高估？
- Funding interval 分組（1h/4h/8h）在 gross vs net-of-cost 上有無系統性差異？
- Max drawdown 期間由哪些 symbol / side 主導？

上述問題的答案將決定後續研究優先順序與是否值得推進 paper trading 規劃。

---

## 3. 為什麼重要

- 若 alpha 高度集中於少數 symbol，策略的「市場中性」假設在實務上偏弱，live risk 被低估。
- 若 alpha 跨年穩定（2024 / 2025 / 2026 各年皆正），可信度顯著提高；若只有一個年度支撐，則需更多樣本才能做任何決策。
- Short side alpha 若持續負貢獻，可考慮研究僅做 long side momentum 的對比實驗（不在本任務做，但 attribution 先量化問題大小）。
- Funding gap symbol 的 cost=0 處理，可能讓這些 symbol 在 net-of-cost 排名中被高估，attribution 可驗證此效應的量級。
- 此報告為後續 TASK-004 dashboard 與 TASK-005 VPS monitor 提供「哪些維度最重要」的優先判斷依據。

---

## 4. 範圍邊界

### ✅ Do（允許做）

- 讀取 run008 / TASK-002 官方輸出，進行統計計算與分組彙整。
- 計算所有 attribution 維度（見第 7 節），產出 CSV / JSON / log。
- 發現異常（如單一 symbol 貢獻異常高）→ 在 log 中標記 WARNING，寫入 attribution summary。
- 在 NOTE 區留下觀察，供 Claude 後續審查使用。

### ❌ Don't（禁止做）

- **不可修改策略訊號、ranking 邏輯、universe 選擇。**
- **不可重新跑 baseline（禁止產生新的 run009 或任何 run0XX）。**
- **不可重新跑 cost stress（禁止重算 20260515_cost_stress.*）。**
- **不可修改 run008 任何輸出（baseline.csv / positions.parquet / stats.json）。**
- **不可修改 20260515 cost stress 任何輸出（cost_stress.csv / summary.json / positions_cost.parquet）。**
- **不可使用舊架構輸出 `output/crypto_cost_stress.csv` 或 `scripts/crypto_cost_stress.py`。**
- **不可修改 raw data（data/ 目錄下的任何 parquet / DB 檔）。**
- **不可自行將 TASK-003 從 REVIEW 轉 DONE**；需等 Claude 審查通過。
- **不可解鎖或開始執行 TASK-004 / TASK-005**；本任務範圍只到 attribution 產出。

---

## 5. 輸入檔案（read-only）

以下檔案**只讀，不可修改**：

| 路徑 | 說明 |
|---|---|
| `outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv` | 正式 baseline，欄位含 `portfolio_return_gross`、三口徑 benchmark return、exposure、turnover |
| `outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet` | 每日持倉，欄位含 `date, symbol, weight, signal_rank` |
| `outputs/backtests/prev3y_crypto/20260513_run008_stats.json` | 統計摘要，含 full / active 雙口徑 |
| `outputs/backtests/prev3y_crypto/20260515_cost_stress.csv` | TASK-002 主輸出，32,124 列 × 16 欄，含 12 scenarios 每日 net return |
| `outputs/backtests/prev3y_crypto/20260515_cost_stress_summary.json` | TASK-002 摘要，含 12 scenarios 的 Sharpe / IR / max DD / cost 分解 |
| `outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet` | 每日每 symbol 的 cost 細項，含 `fee_cost, slippage_cost, funding_cost, funding_gap` |
| `data/crypto/funding_rates.parquet` | Bybit funding rate 原始資料，750,641 列，含 `interval_hours` |
| `configs/prev3y_crypto.yaml` | 策略參數，read-only 參考 |

**主要 attribution 計算應基於**：

- `run008_positions.parquet` — 每日持倉 weight（long / short / zero）
- `run008_baseline.csv` — 每日 gross portfolio return
- `20260515_cost_stress_positions_cost.parquet` — 每日每 symbol cost 細項
- `20260515_cost_stress.csv` — 每日 net-of-cost portfolio return（以 `realistic_combo` scenario 為主口徑）

---

## 6. 輸出檔案

所有輸出寫入 `outputs/attribution/prev3y_crypto/`，檔名前綴統一使用執行日期（`YYYYMMDD`）。

| 路徑 | 格式 | 說明 |
|---|---|---|
| `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_by_symbol.csv` | CSV | 每個 symbol 的 gross / net alpha 貢獻、cost 分解、持倉天數 |
| `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_by_year.csv` | CSV | 每年的 gross / net alpha，及各 cost 類型年度合計 |
| `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_by_month.csv` | CSV | 每月的 gross / net alpha，及各 cost 類型月度合計 |
| `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_by_side.csv` | CSV | Long-only / Short-only / Net 的 gross / net alpha |
| `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_by_funding_gap.csv` | CSV | Funding gap 7 symbols vs non-gap symbols 的 gross / net 比較 |
| `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_by_interval.csv` | CSV | 按 funding interval 分組（1h / 4h / 8h）的持倉天數、gross / net alpha、funding cost |
| `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_by_cost_type.csv` | CSV | Portfolio 層級 fee / slippage / funding 各自占 gross alpha 的比例（含 realistic_combo 口徑）|
| `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_top_contributors.csv` | CSV | Top N symbol 的累積 net alpha 貢獻排名（gross 排名 vs net 排名並列） |
| `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_drawdown.csv` | CSV | Max drawdown 期間（依 run008 gross equity curve 定義）的 symbol-level 貢獻排名 |
| `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_summary.json` | JSON | 所有維度的摘要數字，包含 warning gate 觸發狀態 |
| `outputs/logs/prev3y_crypto/<YYYYMMDD>_attribution.log` | log | 執行紀錄，含 random seed、config hash、data snapshot hash、git commit、WARNING 清單 |

### 輸出 Schema 規範

**`_attribution_by_symbol.csv`** 欄位（最少）：

```
symbol, side_primary, holding_days, gross_alpha_contribution, net_alpha_contribution,
fee_cost_total, slippage_cost_total, funding_cost_total, total_cost,
gross_alpha_rank, net_alpha_rank, rank_change, is_funding_gap, funding_interval_group
```

**`_attribution_summary.json`** 必含欄位：

```json
{
  "run_date": "YYYYMMDD",
  "baseline_run_id": "20260513_run008",
  "cost_stress_run_id": "20260515",
  "primary_scenario": "realistic_combo",
  "active_days": 760,
  "gross_alpha_total": ...,
  "net_alpha_total": ...,
  "total_cost_drag": ...,
  "cost_breakdown": {
    "fee_pct": ...,
    "slippage_pct": ...,
    "funding_pct": ...
  },
  "warning_gates": {
    "top5_symbol_concentration": {"triggered": bool, "value": float, "threshold": 0.60},
    "single_symbol_concentration": {"triggered": bool, "worst_symbol": str, "value": float, "threshold": 0.25},
    "funding_gap_concentration": {"triggered": bool, "value": float, "threshold": 0.20},
    "single_year_concentration": {"triggered": bool, "worst_year": int, "value": float, "threshold": 0.70},
    "short_side_drag": {"triggered": bool, "short_net_alpha": float, "threshold_pct": -0.50},
    "gross_net_rank_divergence": {"triggered": bool, "max_rank_change": int, "threshold": 10}
  },
  "reproducibility_hash": "...",
  "git_commit": "..."
}
```

---

## 7. Attribution 維度

所有維度的 alpha 定義：

- **Gross alpha**：以 `run008_baseline.csv` 的 `portfolio_return` 逐日計算，有效期 = `gross_exposure > 0` 的 760 天。
- **Net alpha**：以 `20260515_cost_stress.csv` 的 `realistic_combo` scenario 的 `portfolio_return_net` 逐日計算，同一 760 天口徑。
- **Symbol-level 貢獻**：用 `run008_positions.parquet` 的 `weight × daily_return` 重建每個 symbol 每日的 P&L 貢獻；cost 來自 `positions_cost.parquet`。

### 7.1 By Symbol

- 每個曾持倉的 symbol，計算其在整個 active period 的：
  - 累積 gross alpha 貢獻（絕對值 + 占總 gross alpha 的百分比）
  - 累積 net-of-cost alpha 貢獻（扣除 fee / slippage / funding 後）
  - 持倉天數（long days / short days / total days）
  - Gross 排名 vs Net 排名（兩者並列，計算 rank change）
- 標記：是否為 funding gap symbol（XTZ/FLOW/LPT/AXS/RVN/INJ/CTC）

### 7.2 By Year

- 按日曆年（2024 / 2025 / 2026）分組，計算每年：
  - Active days（各年有效持倉天數）
  - 累積 gross alpha / net alpha
  - 占整體 active period 的比例
  - Fee / slippage / funding cost 年度合計

### 7.3 By Month

- 按 YYYY-MM 分組，計算每月：
  - Active days
  - Gross alpha / net alpha
  - 各 cost 類型月度合計
- 月度數據為後續 dashboard 視覺化的基礎資料

### 7.4 By Long vs Short

- 將 `weight > 0` 的持倉定義為 long；`weight < 0` 定義為 short。
- 計算：
  - Long side 累積 gross alpha / net alpha / cost
  - Short side 累積 gross alpha / net alpha / cost
  - Long only net alpha / Short only net alpha / Combined
  - 若 short side net alpha 為負：計算其拖累占 combined gross alpha 的比例

### 7.5 By Funding-Gap Symbols

- Funding gap 7 symbols：`XTZ / FLOW / LPT / AXS / RVN / INJ / CTC`
- 分別計算：gap symbols 的累積 gross / net alpha
- 與 non-gap symbols 比較：gap symbols 的 cost=0 設定是否造成相對高估？
- 計算：若 gap symbols 的 funding_cost 以最保守估計（如 realistic 口徑的 funding 平均 rate）填入，net alpha 的變動量級

### 7.6 By Funding Interval Group

- 按 `data/crypto/funding_rates.parquet` 的 `interval_hours` 分組：1h / 4h / 8h
- 對每組計算：持倉 symbol 數、持倉天數、gross alpha 貢獻、net alpha 貢獻、funding cost 合計
- 注意：XTZ 的 interval_hours 標籤為 4h 但實際結算間距為 8h（已知 data quality caveat，請在 log 標記）

### 7.7 By Gross vs Net-of-Cost

- 產出 gross equity curve 與 net equity curve（realistic_combo）的對比序列
- 計算：cost drag 的月度分佈、各月的 alpha decay rate
- 標記：cost 最高的前 5 個月（何時 cost 壓力最大）

### 7.8 By Fee / Slippage / Funding Contribution

- 在 portfolio 層級，計算整個 active period 的：
  - Total fee cost / Total slippage cost / Total funding cost（絕對值）
  - 各類 cost 占 gross alpha 的百分比
  - 各類 cost 的逐月累積分佈
- 以 `realistic_combo` scenario 為主口徑；同時列出 `conservative_combo` 與 `worst_case_combo` 的對應數字作為補充

### 7.9 By Top Contributor Concentration

- 計算 top 1 / 3 / 5 / 10 / 25 symbol 分別貢獻的 net alpha 百分比
- 計算 HHI（Herfindahl–Hirschman Index）for net alpha 集中度
- 輸出：Gross 排名 top 10 vs Net 排名 top 10 的對照表
- 計算：若移除 top 5 symbol，剩餘 alpha 是否仍為正

### 7.10 By Drawdown Contributor

- 以 run008 gross daily equity curve（累積 `portfolio_return`）計算 max drawdown 的開始 / 結束 / 最低點日期
- 在 max drawdown 期間，計算每個 symbol 的 daily P&L 貢獻
- 輸出：drawdown 期間的 top 10 負貢獻 symbol / top 10 正貢獻 symbol
- 同時計算 net-of-cost drawdown 期間（以 realistic_combo）的對應排名

---

## 8. 驗收標準

- [ ] 所有 10 個輸出檔案存在且 schema 正確（欄位名、型別、單位符合第 6 節規範）。
- [ ] `attribution_by_symbol.csv` 的所有 symbol gross alpha 貢獻總和，與 `run008_baseline.csv` active period 的 portfolio_return 累積值 match（±1e-6）。
- [ ] `attribution_by_symbol.csv` 的所有 symbol net alpha 貢獻總和，與 `20260515_cost_stress.csv` realistic_combo active period 的 portfolio_return_net 累積值 match（±1e-6）。
- [ ] `attribution_summary.json` 的 `warning_gates` 每個 key 均有明確 `triggered: true/false` 及實際值。
- [ ] Log 開頭列出：random seed、config hash（attribution 腳本的 config）、input data snapshot hashes（run008_baseline.csv / run008_positions.parquet / cost_stress_positions_cost.parquet 的 SHA-256）、git commit。
- [ ] Log 結尾列出所有觸發的 WARNING（若無，明確標記 `no warnings triggered`）。
- [ ] 可重現性：同一 inputs 跑兩次，`attribution_summary.json` 的 reproducibility_hash 相同。
- [ ] `attribution_by_year.csv` 的各年 net alpha 總和，等於 `attribution_summary.json` 的 `net_alpha_total`（±1e-6）。
- [ ] `attribution_by_month.csv` 的各月 net alpha 總和，等於 `attribution_summary.json` 的 `net_alpha_total`（±1e-6）。
- [ ] Funding gap 7 symbols 在 `attribution_by_symbol.csv` 均有 `is_funding_gap = True` 標記。

---

## 9. Fail / Warning Gate

### Warning Gates（觸發後在 log 標記 `WARNING`，寫入 `attribution_summary.json`，不強制停止）

| Gate | 觸發條件 | 建議動作 |
|---|---|---|
| `top5_symbol_concentration` | Top 5 symbol 合計貢獻 > 60% net alpha | 在報告中標記；Claude 審查時需評估集中度風險 |
| `single_symbol_concentration` | 任一 symbol 貢獻 > 25% net alpha | 標記該 symbol 名稱及數值；Claude 需評估是否為偶發事件 |
| `funding_gap_concentration` | Funding gap 7 symbols 合計貢獻 > 20% net alpha | 標記；提醒 cost=0 可能存在高估，建議做敏感性分析 |
| `single_year_concentration` | 任一年貢獻 > 70% net alpha | 標記該年及數值；Claude 需評估市況依賴性 |
| `short_side_drag` | Short side net alpha 為負，且 abs(short net alpha) > 50% × combined gross alpha | 標記 short side 累積 P&L；Claude 需評估 short 端是否值得保留 |
| `gross_net_rank_divergence` | 任一 symbol 在 gross 排名 vs net 排名相差 > 10 名 | 列出差異最大的 top 5 symbol；Claude 需評估 cost 結構對排名的影響 |

### Fail Gate（觸發後在 log 標記 `FAIL`，輸出不完整時停止）

| Gate | 觸發條件 |
|---|---|
| `symbol_pnl_sum_mismatch` | By-symbol gross alpha 總和與 run008 active period 累積不符（誤差 > 1e-6） |
| `net_pnl_sum_mismatch` | By-symbol net alpha 總和與 realistic_combo active period 累積不符（誤差 > 1e-6） |
| `missing_output_files` | 任一必要輸出檔案缺失 |
| `schema_mismatch` | 輸出檔案欄位缺失或型別錯誤 |

---

## 10. 禁止修改範圍

- **run008 三件套**（baseline.csv / positions.parquet / stats.json）：read-only
- **20260515 TASK-002 三件套**（cost_stress.csv / cost_stress_summary.json / cost_stress_positions_cost.parquet）：read-only
- **`data/` 目錄下所有 raw 檔**：read-only
- **策略程式**（`src/` 下所有 `.py`）：不可修改
- **`configs/prev3y_crypto.yaml`**：不可修改
- **`scripts/run_baseline.py` 或任何 baseline runner**：不可呼叫（禁止觸發新的 run）
- **`scripts/cost_stress.py` 或任何 cost stress runner**：不可呼叫
- **舊輸出 `output/crypto_cost_stress.csv`**：禁止作為任何計算的輸入

---

## 11. 完成後回報格式

```
TASK-003 Attribution — Codex 交付摘要（YYYY-MM-DD）

run_date: YYYYMMDD
baseline_run_id: 20260513_run008
cost_stress_run_id: 20260515
primary_scenario: realistic_combo

[關鍵數字]
gross_alpha_total (active 760d): ____%（累積）
net_alpha_total (realistic_combo): ____%（累積）
total_cost_drag: ____%（占 gross alpha 的 ____%）
cost_breakdown: fee ____% / slippage ____% / funding ____%

[Top 5 Symbol 貢獻（net alpha 排名）]
1. <symbol>: ____% net alpha
2. <symbol>: ____% net alpha
3. <symbol>: ____% net alpha
4. <symbol>: ____% net alpha
5. <symbol>: ____% net alpha

[Top 5 合計]: ____%（warning gate: >60%）

[Year 分布]
2024 (active): net alpha ____%，占比 ____%
2025 (full): net alpha ____%，占比 ____%
2026 (partial, to Apr): net alpha ____%，占比 ____%

[Side 分析]
Long side net alpha: ____%
Short side net alpha: ____%（若負請標記）

[Funding Gap 7 Symbols]
合計 net alpha 貢獻: ____%（warning gate: >20%）

[Warning Gates 觸發狀態]
top5_symbol_concentration: PASS / WARNING (___%)
single_symbol_concentration: PASS / WARNING (<symbol> ___%)
funding_gap_concentration: PASS / WARNING (___%)
single_year_concentration: PASS / WARNING (<year> ___%)
short_side_drag: PASS / WARNING (___%)
gross_net_rank_divergence: PASS / WARNING (max rank change _____)

[Fail Gates]
symbol_pnl_sum_mismatch: PASS / FAIL
net_pnl_sum_mismatch: PASS / FAIL
missing_output_files: PASS / FAIL
schema_mismatch: PASS / FAIL

[可重現性]
reproducibility_hash: <hash>
git_commit: <hash>

[輸出檔案清單]
- outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_by_symbol.csv
- outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_by_year.csv
- outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_by_month.csv
- outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_by_side.csv
- outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_by_funding_gap.csv
- outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_by_interval.csv
- outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_by_cost_type.csv
- outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_top_contributors.csv
- outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_drawdown.csv
- outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_summary.json
- outputs/logs/prev3y_crypto/<YYYYMMDD>_attribution.log

[遇到的問題 / 異常]
（若有，逐條列出）
```

---

## 12. NOTE 區

### NOTE-1：Alpha 定義一致性
Attribution 的 gross alpha 必須與 run008 active period 的 portfolio_return 累積值一致（非 full period）。Active period = `gross_exposure > 0`，共 760 天（2024-04-01 ~ 2026-04-30）。不要使用 2019-01-01 起的全期口徑作分子。

### NOTE-2：Symbol-level 日報酬的重建
run008_baseline.csv 只有 portfolio level 的 `portfolio_return`，不含 symbol-level 每日 return。需從 `run008_positions.parquet`（含 `weight`）與 `prices_daily.parquet`（或衍生資料）重建 `symbol_daily_return`，然後計算 `daily_pnl_contribution = weight × symbol_daily_return`。若 `prices_daily.parquet` 有 coverage gap，處理方式需與 run008 的 missing-data policy 一致（即：excluded symbol-day 的 contribution = 0，不補值）。

### NOTE-3：Cost 的 symbol-level 對應
`cost_stress_positions_cost.parquet` 的 cost 欄位已是 scenario-specific 數值，以 `realistic_combo` 為主口徑時，請確認使用的是對應 scenario 的欄位，而非所有 scenario 混合。若 parquet 中 scenario 是以 column 或 row filter 區分，請先確認 schema 再計算。

### NOTE-4：Funding Gap Symbol 的敏感性分析（選做）
若時間允許，可額外計算一個「假設 funding gap 7 symbols 以 realistic 平均 funding rate 補入」後的 net alpha 估算，放在 NOTE 中，不計入正式 attribution 數字（僅供 Claude 審查參考）。此分析不需要重跑 cost stress，只需在 attribution script 中做靜態估算。

### NOTE-5：Drawdown 期間定義
Max drawdown 以 gross equity curve 定義（`cumsum(portfolio_return)` 從 peak 到 trough）。Codex 應先計算 gross equity curve 的全域最大 drawdown 開始 / 結束日期，再在這個固定區間內做 symbol-level 分解。不要用 rolling window 方式計算多個 drawdown。

### NOTE-6：Funding Interval XTZ Caveat
XTZ 的 `interval_hours=4` 是 Bybit 資料的 label，但實際結算間距為 8h（已在 TASK-002 REVIEW 中記錄為 caveat C-1）。Attribution 計算時，XTZ 的 interval group 應按 `interval_hours` label 歸入 `4h` 組，並在 log 中標記此 caveat。不需要重新分類。

### NOTE-7：不要把 TASK-003 轉 DONE
Codex 完成後，只把 TASK-003 狀態改為 `REVIEW`，並在 CODEX_TASK_QUEUE.md 下方貼上第 11 節的交付摘要。等 Claude 審查通過後，才由 Claude 標記 `DONE` 並更新下游任務狀態。

---

*工單版本 v1.0｜撰寫：Claude Sonnet｜日期：2026-05-15*
*依據：TASK-001 DONE (run008)、TASK-002 Opus REVIEW-002 PASS、CHATGPT_ADVISOR_CONTEXT.md 2026-05-15*
