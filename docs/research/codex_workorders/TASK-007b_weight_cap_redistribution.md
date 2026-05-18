# TASK-007b — Weight Cap + Redistribution Study

- **狀態**：TODO
- **Owner**：Codex
- **預估**：S（0.5–1 天）
- **依賴**：TASK-007 ✓ DONE；TASK-003 ✓ DONE；run008 + cost stress 輸入已就位
- **工單版本**：v1.0（2026-05-16，由 Claude Sonnet 撰寫）
- **觸發原因**：
  - Opus REVIEW-007 CONDITIONAL_PASS — B-1 BLOCKING：工單規格的 Variant D（每日 weight cap + redistribution）未按規格交付；TASK-007 交付的是 alpha-based symbol selection，設計不同。
  - TASK-006 執行前置條件：paper trading 啟動前**必須完成**本任務。

---

## ⚠️ 執行閘門聲明

**TASK-007b 是 paper trading 執行的硬性前置條件（hard gate）。**

- 本任務完成並通過 Claude REVIEW-007b 後，結果才可輸入 TASK-006 overlay 規格。
- 本任務只做研究分析，**不可啟動任何 paper trading 或 live trading**。
- 完成後狀態改為 `REVIEW`，等 Claude 審查。

---

## 1. 任務一句話

基於 run008 既有持倉，實作「每日按 symbol `|weight|/gross_exposure` 占比」的動態截斷（cap）+ 等比例分配（redistribution）邏輯，產出 cap=20%、15%、10% 三個 variant 的績效統計，與 TASK-007 的 alpha-based selection 變體並列比較，確認哪種設計更適合作為 TASK-006 paper trading 的 Rule 3 規格。

---

## 2. 任務目的

### 背景：TASK-007 的 Variant D 缺口

TASK-007 工單規格的 Variant D 要求：每日計算每個 symbol 的 `|weight| / gross_exposure`，超過 cap 的部分**等比例補回同方向其他 symbol**（redistribution）。但 TASK-007 實際交付的是：
- `top5_symbol_cap_5pct`：按 net alpha（非 weight）限制 top5 symbol
- `DOT_capped`：僅針對 DOT 截斷
- `no_DOT`：完全移除 DOT

設計邏輯完全不同：TASK-007 交付的是**事後 alpha-based symbol selection**，而非**每日動態 weight cap + 同方向 redistribution**。

### 本任務要回答

1. 若在每日 rebalance 時把任何 symbol 的 `|weight|/gross_exposure` 截斷至 20%/15%/10%，並把超出部分**等比例補回同方向其他 symbol（long→long，short→short）**，績效與集中度如何變化？
2. Redistribution 版的 cap 與 TASK-007 的「截斷不分配（no_redistribution）」版相比，哪種 top5 concentration 更低？Sharpe 損失更小？
3. Cap = 15% 時，top5 concentration（/net_alpha_total）是否降至 70% 以下？（工單原始 gate `concentration_not_reduced`）
4. Cap = 10% 時，Sharpe 是否跌超過 30%？（工單原始 gate `cap10_sharpe_drop`）
5. 哪個 cap 值最適合作為 TASK-006 paper trading 的 Rule 3 symbol cap 設計？

---

## 3. 範圍邊界

### ✅ Do（允許做）

- 讀取 run008 positions.parquet，按每日動態 weight cap 邏輯調整 weights。
- 實作 redistribution 邏輯（超出 cap 的 weight 等比例補回同方向其他 symbol）。
- 用 TASK-002 realistic_combo 的 per-symbol cost 計算各 variant 的 net returns。
- 與 TASK-007 已交付的 `top5_symbol_cap_5pct`、`DOT_capped` 並列輸出比較表。
- 評估工單原始 warning gates：`concentration_not_reduced`（cap=15%）和 `cap10_sharpe_drop`。
- 在 log 中標記每日被截斷的 symbol、截斷金額、redistribution 目標。

### ❌ Don't（禁止做）

- **不可重新執行策略訊號或 ranking 邏輯**。
- **不可修改 run008 任何輸出**。
- **不可修改 TASK-002、TASK-003、TASK-007 任何輸出**。
- **不可修改 raw data**（`data/` 目錄）。
- **不可修改策略程式**（`src/` 目錄）。
- **不可啟動 paper trading 或 live trading**。
- **不可自行將 TASK-007b 轉 DONE**。

---

## 4. 輸入檔案（read-only）

| 路徑 | 說明 |
|---|---|
| `outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet` | 每日持倉 weight，含 `date, symbol, weight, signal_rank` |
| `outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv` | 每日 gross portfolio return |
| `outputs/backtests/prev3y_crypto/20260515_cost_stress_positions_cost.parquet` | Per-symbol cost（取 `realistic_combo`）|
| `data/crypto/prices_daily.parquet` | 日線 OHLCV，用於重建 symbol daily return |
| `outputs/variants/prev3y_crypto/20260515_task007_variant_summary.csv` | TASK-007 已有 variant 結果（供並列比較）|
| `outputs/variants/prev3y_crypto/20260515_task007_variant_summary.json` | TASK-007 variant numbers（含 top5_conc / single_conc）|

**計算基礎（與 TASK-003 / TASK-007 一致）**：
- Return dating：`positions.date + 1 day = return_date`
- Cost source：`cost_stress_positions_cost.parquet` 的 `realistic_combo` 列
- Annualization：365.25；std ddof：1
- Active period：gross_exposure > 0，760 天（2024-04-01 ~ 2026-04-30）

---

## 5. Cap + Redistribution 邏輯規格

### 5.1 核心計算流程（每日獨立計算）

```
For each rebalance date t:
  1. 從 positions.parquet 取當日 weights
  2. 計算 gross_exposure_t = sum(|weight_i|)
  3. 計算每個 symbol 的 pct_i = |weight_i| / gross_exposure_t
  4. 識別需截斷的 symbol：overcap_symbols = {i : pct_i > cap}
  5. 對每個 overcap symbol i：
     a. excess_weight_i = |weight_i| - cap × gross_exposure_t
     b. weight_i_new = sign(weight_i) × cap × gross_exposure_t
     c. 將 excess_weight_i 按 |weight_j| 的比例分配給同方向（同 sign）的非 overcap symbols
  6. 若所有同方向 symbol 都在 cap 以下：accept the reduction（gross_exposure 略減）
  7. 驗證：sum(|weight_i_new|) ≤ sum(|weight_i|) + 1e-10（浮點容忍）
```

**三個 cap 值**：20%（cap_20pct）、15%（cap_15pct）、10%（cap_10pct）

### 5.2 Edge Cases（繼承 TASK-007 工單 NOTE-4）

- 若某日只有 1 個多頭 symbol 且 |weight| > cap：截斷至 cap，剩餘不分配（gross_exposure 略降）。
- 若截斷後所有同方向 symbol 均已達 cap（redistribution 無空間）：接受 gross_exposure 下降，不強制塞回。
- 浮點誤差 < 1e-10 視為通過。
- 所有 edge case 在 log 中標記日期、symbol、原因。

### 5.3 Cost Scaling

- 截斷後 weight 改變，cost 按比例縮放：`cost_scale = |weight_new| / |weight_original|`
- 若 symbol 未被截斷，cost 不變。
- 被 redistribution 增加 weight 的 symbol，cost 按比例放大：`cost_scale = |weight_new| / |weight_original|`

---

## 6. 輸出檔案

所有輸出寫入 `outputs/variants/prev3y_crypto/`，以執行日期為前綴。

| 路徑 | 格式 | 說明 |
|---|---|---|
| `<YYYYMMDD>_task007b_cap20_daily.csv` | CSV | Cap=20% 每日 gross / net return |
| `<YYYYMMDD>_task007b_cap15_daily.csv` | CSV | Cap=15% 每日 gross / net return |
| `<YYYYMMDD>_task007b_cap10_daily.csv` | CSV | Cap=10% 每日 gross / net return |
| `<YYYYMMDD>_task007b_comparison_summary.csv` | CSV | 3 個 cap + TASK-007 alpha-based variants 並列比較表 |
| `<YYYYMMDD>_task007b_comparison_summary.json` | JSON | 同上，含 warning gate 觸發狀態 |
| `<YYYYMMDD>_task007b_redistribution_log.csv` | CSV | 每日被截斷 symbol + redistribution 記錄 |
| `outputs/logs/prev3y_crypto/<YYYYMMDD>_task007b.log` | log | 執行記錄，含 input hashes + edge cases |

### `_task007b_comparison_summary.json` 必含欄位

```json
{
  "run_date": "YYYYMMDD",
  "methodology": {
    "cap_logic": "daily_weight_pct_of_gross_exposure_with_same_direction_redistribution",
    "cost_scaling": "proportional_to_weight_change",
    "return_dating": "positions.date + 1 day",
    "annualization_factor": 365.25,
    "std_ddof": 1
  },
  "baseline_run008": {
    "sharpe_active": 0.8918,
    "net_alpha": 0.2853,
    "top5_concentration_net_alpha_total": 0.9556,
    "single_symbol_concentration_net_alpha_total": 0.2545,
    "max_dd": -0.1964
  },
  "task007_alpha_based_reference": {
    "top5_symbol_cap_5pct": { "sharpe_active": 0.7225, "top5_conc": 1.0356, "max_dd": -0.1964 },
    "DOT_capped":            { "sharpe_active": 0.7922, "top5_conc": 0.9831, "max_dd": -0.1964 },
    "no_DOT":                { "sharpe_active": 0.7132, "top5_conc": 1.1613, "max_dd": -0.1758 }
  },
  "task007b_weight_cap_redistribution": {
    "cap_20pct": {
      "sharpe_active": null,
      "net_alpha": null,
      "top5_concentration_net_alpha_total": null,
      "single_symbol_concentration_net_alpha_total": null,
      "max_dd": null,
      "alpha_retention_pct": null,
      "sharpe_vs_baseline_delta": null,
      "warning_concentration_not_reduced": null,
      "warning_cap10_sharpe_drop": null
    },
    "cap_15pct": { ... },
    "cap_10pct": { ... }
  },
  "gate_results": {
    "concentration_not_reduced_cap15": {
      "description": "cap=15% top5_conc > 70%",
      "triggered": null,
      "value": null
    },
    "cap10_sharpe_drop": {
      "description": "cap=10% Sharpe drop vs baseline > 30%",
      "triggered": null,
      "value": null
    }
  },
  "recommended_cap_for_task006": "TBD",
  "paper_trading_note": "not a trading decision; for TASK-006 Rule 3 spec input only",
  "reproducibility_hash": "...",
  "git_commit": "..."
}
```

---

## 7. 方法論規範（繼承 TASK-003 / TASK-007）

| 項目 | 規範 |
|---|---|
| Annualization | 365.25 |
| Std ddof | 1 |
| IR formula | `mean(net_return) / std(net_return, ddof=1) * sqrt(365.25)` |
| Active period | gross_exposure > 0，760 天（2024-04-01 ~ 2026-04-30）|
| Return dating | `positions.date + 1 day = return_date` |
| Net formula | `net = gross - fee_cost - slippage_cost - funding_cost` |
| Cost source | `cost_stress_positions_cost.parquet` realistic_combo |
| Concentration formula | top5_conc = top5_net_alpha_sum / net_alpha_total（工單規格，分母為 net_alpha_total）|

**重要**：Concentration 公式使用 **`/net_alpha_total`**（TASK-003 工單規格，Opus REVIEW-003 裁定採用），**不使用** `/sum_abs_net` 或 `/sum_positive_net`。

---

## 8. 驗收標準

- [ ] 三個 cap variant 的每日 daily CSV 存在（3 個檔案）。
- [ ] `_task007b_comparison_summary.json` 存在，schema 符合 Section 6 規格。
- [ ] `_redistribution_log.csv` 存在，至少包含 `date, symbol, original_weight, capped_weight, excess_weight, redistribution_targets` 欄位。
- [ ] Baseline 對齊：`task007b_comparison_summary.json` 的 `baseline_run008` 數字與 run008_stats.json 一致（±1e-6 for net_alpha，Sharpe 使用 TASK-007 口徑 0.8918）。
- [ ] Cap=15% 的 `concentration_not_reduced` gate 有明確觸發 / 未觸發結果。
- [ ] Cap=10% 的 `cap10_sharpe_drop` gate 有明確觸發 / 未觸發結果。
- [ ] 所有 cap variant 的 `sum(|weight|)` 每日 ≤ 原始 run008 同日 `sum(|weight|)` + 1e-10。
- [ ] Log 包含 input file SHA-256 + git commit + edge case 記錄。
- [ ] 可重現性：同 input 兩次，`_comparison_summary.json` 的 reproducibility_hash 相同。

---

## 9. Fail / Warning Gates

### Fail Gates（觸發則停止）

| Gate | 觸發條件 |
|---|---|
| `baseline_mismatch` | comparison_summary.json 的 baseline_run008 net_alpha 與 run008_stats.json 差異 > 1e-6 |
| `missing_outputs` | 任一必要輸出檔案缺失 |
| `schema_error` | 輸出檔案欄位缺失或型別錯誤 |
| `redistribution_overflow` | 任一 cap variant 任一日的 sum(|weight|) 超過原始 sum(|weight|) × (1 + 1e-6) |

### Warning Gates（標記 WARNING，不停止）

| Gate | 觸發條件 | 備注 |
|---|---|---|
| `concentration_not_reduced` | Cap=15% 的 top5_conc（/net_alpha_total）仍 > 70% | TASK-007 原始工單 gate |
| `cap10_sharpe_drop` | Cap=10% 的 Sharpe vs baseline 下降 > 30% | TASK-007 原始工單 gate |
| `redistribution_has_no_room` | 超過 X% 的截斷日期無法完全分配（因同方向都在 cap 以下空間不足）| X 由 Codex 合理設定，建議 5% |

---

## 10. 禁止修改範圍

- **run008 四件套**：read-only
- **20260515 TASK-002 outputs**：read-only
- **20260515 TASK-003 attribution outputs**：read-only
- **20260515 TASK-007 variant outputs**：read-only
- **`data/` 目錄下所有 raw 檔**：read-only
- **策略程式**（`src/`）：不可修改
- **`configs/` yaml**：不可修改
- **任何 baseline runner / cost stress runner**：不可呼叫

---

## 11. 完成後回報格式

```
TASK-007b Weight Cap + Redistribution — Codex 交付摘要（YYYY-MM-DD）

run_date: YYYYMMDD
git_commit: <hash>
reproducibility_hash: <hash>

=== Baseline 參照 ===
Sharpe: 0.8918
net_alpha: 28.53%
top5_conc: 95.56%（/net_alpha_total）
single_conc: 25.45%（DOT）
max_DD: -19.64%

=== TASK-007b Weight Cap + Redistribution ===
              cap=20%    cap=15%    cap=10%
Sharpe:       ____       ____       ____
net_alpha:    ____%      ____%      ____%
top5_conc:    ____%      ____%      ____%（/net_alpha_total）
single_conc:  ____%      ____%      ____%
max_DD:       ____       ____       ____
alpha_ret:    ____%      ____%      ____%

=== TASK-007 Alpha-based 參照（直接讀 TASK-007 輸出，不重算）===
top5_symbol_cap_5pct: Sharpe=0.7225, top5_conc=103.56%, single_conc=21.39%
DOT_capped:           Sharpe=0.7922, top5_conc=98.31%,  single_conc=21.36%
no_DOT:               Sharpe=0.7132, top5_conc=116.13%, single_conc=25.23%

=== Warning Gates ===
concentration_not_reduced（cap=15% top5 > 70%）: TRIGGERED / NOT TRIGGERED
cap10_sharpe_drop（cap=10% Sharpe drop > 30%）: TRIGGERED / NOT TRIGGERED

=== Fail Gates ===
baseline_mismatch: PASS / FAIL
missing_outputs: PASS / FAIL
schema_error: PASS / FAIL
redistribution_overflow: PASS / FAIL

=== 推薦 cap 值（量化輸入，非決策）===
建議 TASK-006 Rule 3 採用 cap=____%（based on top5_conc / Sharpe tradeoff）

=== 輸出檔案清單 ===
[列出 7 個輸出檔案]

=== 遇到的問題 / 異常 ===
（edge case 記錄，如有）
```

---

## 12. NOTE 區

### NOTE-1：與 TASK-007 設計的根本差異

TASK-007 的 alpha-based selection（top5_cap_5pct / DOT_capped / no_DOT）和本任務的 weight-based cap + redistribution 是**不同設計**：

| 維度 | TASK-007 alpha-based | TASK-007b weight-based |
|---|---|---|
| 截斷基準 | 歷史 net alpha（回顧式） | 當日 weight 占比（即時）|
| 分配邏輯 | 無（截斷後丟棄）| 等比例補回同方向 symbol |
| 能否用於 forward | 否（需知道未來 alpha）| 是（只需當日 weights）|
| Paper trading 可行性 | ❌ 不可行 | ✅ 可行 |

**結論**：只有 weight-based cap + redistribution 才能在真實 paper trading 中機械性執行。Alpha-based 設計只能回顧使用，不可用於 forward 規劃。

### NOTE-2：top5_conc 公式

本任務的 concentration 計算使用 `/net_alpha_total`（Opus REVIEW-003 裁定的工單規格）：
- `top5_conc = sum(top5_net_alpha) / net_alpha_total`
- 其中 `net_alpha_total` = 全部 symbol 的 net alpha 加總（正負相消後的總數）
- **不使用** `/sum_abs_net`（Codex TASK-003 的舊公式）

### NOTE-3：redistribution 對集中度的預期效果

若 DOT 空頭（25.45% 貢獻者）在每日被截斷至 cap 後，其超出部分補給其他空頭 symbol，則：
- DOT 的 weight 縮小 → DOT 的 net alpha 貢獻下降
- 其他空頭的 weight 增加 → 分散集中度
- 但 net_alpha_total 也會變化（DOT 貢獻大幅減少）

**NOTE-3 是關鍵觀察**：若截斷後 net_alpha_total 縮小的比例 > top5 貢獻縮小的比例，top5_conc 可能不降反升（no_DOT 悖論）。請在 log 中計算並記錄此效應。

### NOTE-4：此任務完成後的路徑

TASK-007b PASS 後：
1. Claude 審查（REVIEW-007b）比較 redistribution 版 vs TASK-007 alpha-based 版的優劣。
2. Opus 裁定 TASK-006 paper trading 的最佳 Rule 3 規格（weight-based cap 的 cap 值）。
3. 更新 TASK-006 `overlay.py` 的 Rule 3 實作（若 redistribution 版優於 no_redistribution）。
4. 之後才能啟動 paper trading 基礎架構的 REVIEW-006b 流程。

### NOTE-5：TASK-007b 不轉 DONE

完成後狀態改為 `REVIEW`，在 CODEX_TASK_QUEUE.md 下方貼交付摘要，等 Claude REVIEW-007b 通過後由 Claude 標記 DONE。

---

*工單版本 v1.0 | 撰寫：Claude Sonnet | 日期：2026-05-16*  
*觸發依據：Opus REVIEW-007 CONDITIONAL_PASS（B-1 BLOCKING：Variant D 未按規格交付）；TASK-006 paper trading hard gate*  
*參考：REVIEW-007_DRAFT_BY_SONNET.md Section 3（B-1）；CODEX_TASK_QUEUE.md TASK-007b；TASK-007_long_side_variant_study.md Section 6（Variant D 規格）*
