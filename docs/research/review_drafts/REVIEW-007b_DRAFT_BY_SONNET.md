# REVIEW-007b Draft — TASK-007b Weight Cap + Redistribution Study

**Draft by**: Claude Sonnet  
**Date**: 2026-05-16  
**Status**: PASS_CANDIDATE（1 項 BLOCKING，需 Opus 裁定）  
**依據**: Token Budget Rule — 只讀 REVIEW-007b_PACKET.md + REVIEW-007b_NUMBERS.json + cap_summary.csv + redistribution_log.csv + gate_report.json + task log

---

## 1. 工程驗收：Fail Gates（5 條全 PASS）

| Gate | 閾值 | 實際值 | 結論 |
|---|---|---|---|
| `baseline_reconciliation_mismatch` | < 1e-6 | 2.05e-16 | ✅ PASS |
| `missing_outputs` | 0 個缺失 | 0 | ✅ PASS |
| `schema_mismatch` | 0 錯誤 | 0 | ✅ PASS |
| `redistribution_overflow` | max overflow < 1e-6 | 0.0 | ✅ PASS |
| `paper_live_execution_code` | 無禁用代碼 | matches=0 | ✅ PASS |

**Baseline 對齊細節**：
- gross vs run008 max diff: `1.05e-16`（±1e-6 容差內）
- net vs TASK-002 realistic_combo max diff: `2.05e-16`（±1e-6 容差內）
- gross vs TASK-007 max diff: `9.97e-17`
- Reproducibility hash: `f5c962e11189cc4f91dedbc50b00456830d1fdc6e868c1638ad6b3e3e4db07b7`（已落地）

工程面：所有 fail gates 全部通過，overlay 邏輯未觸及策略程式、官方輸出或 raw data。Scan 確認無 paper/live 下單程式碼。

---

## 2. 核心數字表

| Variant | Cap | Sharpe | IR vs EQW | Max DD | Net Alpha | Alpha Retention | Top5 Conc | Single Conc | No-room Events |
|---|---|---|---|---|---|---|---|---|---|
| **Baseline** | — | **0.8918** | **0.7168** | **−19.64%** | **28.53%** | **100.00%** | **95.56%** | **25.45%** | 0 |
| cap_20pct | 20% | 0.8918 | 0.7168 | −19.64% | 28.53% | 100.00% | 95.56% | 25.45% | 0 |
| cap_15pct | 15% | 0.8918 | 0.7168 | −19.64% | 28.53% | 100.00% | 95.56% | 25.45% | 0 |
| cap_10pct | 10% | 0.8341 | 0.7053 | −19.64% | 26.36% | 92.38% | **98.69%** | 24.81% | **488** |

*Concentration formula：top5_conc = top5_net_alpha_sum / net_alpha_total（Opus REVIEW-003 裁定公式）*

### TASK-007 Alpha-based 參照（直接讀 TASK-007 輸出，不重算）

| Variant | Sharpe | Top5 Conc | Single Conc | Net Alpha | Alpha Retention |
|---|---|---|---|---|---|
| top5_symbol_cap_5pct | 0.7225 | 103.56% | 21.39% | 22.99% | 80.58% |
| DOT_capped | 0.7922 | 98.31% | 21.36% | 25.15% | 88.15% |
| no_DOT | 0.7132 | 116.13% | 25.23% | 21.29% | 74.62% |

---

## 3. Warning Gates 結果（4 條觸發）

| Gate | 閾值 | 觸發 | 實際值 |
|---|---|---|---|
| `concentration_not_reduced_cap15` | top5_conc > 70% | ✅ **TRIGGERED** | 95.56%（與 baseline 完全相同） |
| `top5_concentration_above_threshold` | 任一 cap top5 > 70% | ✅ **TRIGGERED** | cap_20=95.56%, cap_15=95.56%, cap_10=98.69% |
| `single_symbol_concentration_above_threshold` | 任一 cap single > 25% | ✅ **TRIGGERED** | cap_20=25.45%, cap_15=25.45% |
| `redistribution_has_no_room` | events > 0 | ✅ **TRIGGERED** | 488 events on 61 dates |
| `cap10_sharpe_drop` | Sharpe drop > 30% | ❌ NOT triggered | 6.48% drop（<<30%） |
| `alpha_retention_below_threshold` | retention < 70% | ❌ NOT triggered | 92.38%（>>70%） |

---

## 4. 最重要發現：Weight Cap Overlay 無法解決集中度問題

### 4.1 為什麼 20% / 15% 是完全 No-op

NUMBERS.json 揭露：`max_symbol_weight_pct_of_original_gross = 0.125`（12.5%）。

Run008 持倉結構為**同方向等權配置**（在每個 rebalance 日，所有多頭/空頭 symbol 各拿相同 weight）。在最集中的早期（2024-04-02 起），每日只有 4 long + 4 short = 8 個 symbol，每個 weight = 1/8 = 12.5%。

- Cap = 20%：>12.5% 才截斷 → **從未觸發，portfolio 100% 不變**
- Cap = 15%：>12.5% 才截斷 → **從未觸發，portfolio 100% 不變**
- Cap = 10%：>12.5% > 10%，所有 symbol 都超過 → 61 個日期觸發

### 4.2 為什麼 Cap = 10% 無法 Redistribute

Redistribution_log 顯示，在所有 488 個 cap 觸發事件中：
- `eligible_room = 0.0`（所有事件）
- `redistribution_target_count = 0`（所有事件）
- `redistribution_targets = []`（所有事件）
- `event_type = redistribution_has_no_room`（所有事件）

**原因**：當所有同方向 symbol 都均等持倉（全部都是 12.5%）時，cap = 10% 同時觸發所有 symbol，沒有任何同方向 symbol 處於 cap 以下有空間接收 redistribution。

結果：excess weight（每 symbol 2.5%）無法分配，直接縮減 gross_exposure。最終 gross_reduction = 12.2（累積縮減量）。

### 4.3 Cap = 10% 的反直覺結果

Cap = 10% 的 top5_conc 從 95.56% **惡化至 98.69%**（+3.3pp）。

**原因**：這是 no_DOT 悖論的 weight-space 版本。Cap 同比例縮減所有 symbol 的 weight，包括 DOT（主要貢獻者）。縮減後：
- DOT 的 net alpha 貢獻略降（weight 縮小，但 DOT 空頭 alpha 沛然莫之能禦）
- net_alpha_total 也縮小（整體 gross 下降）
- `top5_conc = top5_net_alpha_sum / net_alpha_total` 的分母縮小速度 ≥ 分子縮小速度 → 比率上升

**結論**：在 alpha-space 的集中度問題（DOT 長期穩定貢獻 25%+ net alpha）**無法被 weight-space 的等比例縮減解決**。

### 4.4 與 TASK-007 Alpha-based 設計的比較

| 維度 | TASK-007b cap_10pct（weight-based） | TASK-007 alpha-based（DOT_capped） |
|---|---|---|
| Sharpe | **0.8341**（較高）| 0.7922（較低）|
| top5_conc | **98.69%**（略高）| 98.31%（略低）|
| single_conc | **24.81%**（低於25%閾值）| 21.36% |
| alpha_retention | **92.38%** | 88.15% |
| forward 可執行 | ✅ 可機械執行 | ❌ 需知歷史 alpha |

Weight-based cap 保留較多 Sharpe，但集中度改善幾乎為零，且面對等權投資組合時 redistribution 根本無法啟動。

---

## 5. TASK-007b 完成確認

- [x] 三個 cap variant 每日 CSV 存在
- [x] `_task007b_comparison_summary` 存在（CSV + JSON）
- [x] `_redistribution_log.csv` 存在，schema 含 `date, symbol, original_weight, capped_weight, excess_weight, redistribution_targets` 等欄位
- [x] Baseline 對齊（net_alpha 差異 2.05e-16 << 1e-6）
- [x] cap=15% `concentration_not_reduced` gate 有明確結果：**TRIGGERED**（95.56% >> 70%）
- [x] cap=10% `cap10_sharpe_drop` gate 有明確結果：**NOT TRIGGERED**（6.48% < 30%）
- [x] 所有 cap variant 每日 sum(|weight|) ≤ 原始 sum(|weight|)（redistribution_overflow = 0）
- [x] Log 含 input SHA-256 + git commit + edge case 記錄
- [x] Reproducibility hash 落地
- [x] 未修改策略程式 / 官方輸出 / raw data
- [x] 未執行 paper / live trading

---

## 6. Sonnet 初步結論

**工程面**：PASS。5 條 fail gates 全部通過，baseline 對齊至機器精度，redistribution overflow = 0，無下單程式碼，可重現性 hash 存在。

**研究面**：核心發現明確且一致：

> **Weight-based daily cap + redistribution 在 run008 等權投資組合結構下無法降低集中度。**
> - Cap 20% / 15% = 完全 no-op（max weight 12.5% 低於 cap）
> - Cap 10% = redistribution 無法執行（全 symbol 同時超限，無同方向接收空間）；top5_conc 反惡化 3.3pp
> - 集中度問題在 alpha-space，不在 weight-space；overlay 無法根治

此結論與 Opus REVIEW-007 指出的「overlay 無法根治集中度，需策略層 cap（TASK-008）」完全吻合，並在量化數字上提供確鑿驗證。

**Paper trading gate 影響**：TASK-007b 的目的是確認 redistribution 是否能作為 TASK-006 Rule 3 的規格。答案是：**redistribution 在當前 portfolio 結構下不適用**；TASK-006 現行 `symbol_cap_5pct`（無 redistribution）的設計是正確的。

---

## 7. BLOCKING 問題（需 Opus 裁定）

### B-1（BLOCKING）：TASK-007b 完成後 paper trading gate 是否解鎖？

**背景**：NEXT_ACTION 與 CODEX_TASK_QUEUE 將 TASK-007b 定為「paper trading 執行的硬性前置條件（hard gate）」。TASK-007b 現已完成，且確認 redistribution 不可行。

**待裁定問題**：

1. TASK-007b 完成 = hard gate 滿足，paper execution 可從「TASK-007b」這一門待解清單上移除？
   - 理由：TASK-007b 的任務是研究 weight cap 設計，已完成並有確鑿結論。
   - 現行 TASK-006 Rule 3（`symbol_cap_5pct` + no redistribution）已是正確設計。

2. 還是 TASK-007b 的結論（redistribution 不可行 + 集中度未解決）代表**必須先完成 TASK-008**（strategy-layer cap）才可移除 paper execution 的集中度阻擋條件？

**Sonnet 傾向**：選項 1（TASK-007b 滿足其 hard gate 功能）。理由：
- TASK-007b 的研究目的已完成：量化確認 redistribution 在當前結構下不可行
- TASK-006 已採用 `symbol_cap_5pct`（5% overlay cap）作為 Rule 3，這一設計已通過 Opus REVIEW-006 PASS
- 集中度的結構性根治在 TASK-008，但 TASK-008 是「長期任務」，設計上不擋短期 paper planning
- Paper execution 仍有 4 個其他前置條件（TASK-005 VPS monitor、30天 forward、REVIEW-006b PASS、Rick 批准）可作為安全緩衝

**但此為重大決策**，涉及 paper trading gate 放行，應由 Opus 最終裁定。

---

## 8. 非 BLOCKING 發現（不擋審查，建議後續補件）

### N-1：redistribution_log 揭露初期 universe 極小（2024-04 只有 8 symbol）

Redistribution_log 顯示 2024-04-02 只有 4 longs + 4 shorts，每個 weight = 12.5%。這與 TASK-006 monthly_review（25 longs + 25 shorts）存在顯著差異，可能代表：
- 2024-04 初期 PIT universe 極小，策略只能持倉 4+4 = 8 個 symbol
- Portfolio 集中度（weight-space）在不同時期可能差異很大

建議 Codex 在 TASK-007b 補件（若有）或 TASK-008 backtest 中補出「每日持倉 symbol 數分布」統計，協助理解集中度問題的動態特徵。**不擋本次 REVIEW。**

### N-2：cap_10pct 的 max_symbol_weight_pct_of_new_gross = 12.5%（重要觀察）

Cap_10pct 截斷後，`max_symbol_weight_pct_of_new_gross` = 12.5%，高於 cap 值（10%）。原因：cap 是相對於**原始** gross 計算的，截斷後 gross 縮減，symbol weight 相對於**新** gross 的占比反而升回 12.5%。

這代表：overlay cap 以「原始 gross 比例」為截斷基準，但截斷後的「新 gross 比例」不受保證在 cap 以下。Codex 應在工單備注或補件中明確記錄此設計選擇。**不擋本次 REVIEW。**

---

## 9. Opus 最終裁定建議

請 Rick 將以下 prompt 貼給 Opus 進行 REVIEW-007b final decision：

---

**Opus Prompt — REVIEW-007b Final Decision**

你是 Claude Opus，擔任最終審查官。本次任務：對 TASK-007b Weight Cap + Redistribution 做 final decision。

請只讀以下資料（Token Budget Rule）：
1. 本 Sonnet draft（REVIEW-007b_DRAFT_BY_SONNET.md）
2. `docs/research/review_packets/REVIEW-007b_PACKET.md`
3. `docs/research/review_packets/REVIEW-007b_NUMBERS.json`

不需要讀大 CSV 或 log 原始檔案。

請回答以下 5 個問題：

**Q1 工程驗收**：5 個 fail gates 全 PASS（baseline max diff 2.05e-16、overflow=0、無缺失輸出、無 schema 錯誤、無下單程式碼），reproducibility hash 存在。你是否接受工程面 PASS？

**Q2 研究結論**：cap_20pct 和 cap_15pct 完全 no-op（max weight 12.5% 低於 cap），cap_10pct 雖有 61 個日期觸發但 redistribution 無法執行（全 488 事件均 redistribution_has_no_room），top5_conc 反惡化至 98.69%。你是否接受「weight-based overlay cap + redistribution 無法降低集中度」的研究結論？

**Q3（BLOCKING）paper trading gate 裁定**：TASK-007b 設為「paper trading 執行的 hard gate」。現在 TASK-007b 研究已完成，確認 redistribution 不可行，且 TASK-006 現行設計（symbol_cap_5pct 無 redistribution）已通過 REVIEW-006 PASS。你的裁定：
- (A) TASK-007b 完成後，其對 paper execution 的 hard gate 功能視為已滿足；paper execution 剩餘阻擋條件為 TASK-005 + 30天 forward + REVIEW-006b + Rick 批准
- (B) 因集中度未獲改善，必須等 TASK-008 完成才可移除集中度相關的 paper execution 阻擋

**Q4 TASK-006 Rule 3 規格確認**：現行 TASK-006 overlay Rule 3 = `symbol_cap_5pct` + no redistribution。鑑於 redistribution 不可行，此設計是否合理？是否需要更新工單？

**Q5 下游**：TASK-007b → DONE 之後，下一步優先順序建議（TASK-007c sensitivity / TASK-008 strategy-layer cap / TASK-004 dashboard / TASK-005 VPS monitor）。

請最後給出：
- REVIEW-007b = PASS / CONDITIONAL_PASS / FAIL
- TASK-007b → DONE 或維持 REVIEW
- Paper trading gate Q3 答案（A 或 B）
- 下游任務優先順序

---

*注意：不要批准 paper execution，不要批准 live trading，不要修改任何策略程式或官方輸出，不要重跑任何任務。*

---

## 10. 本 Draft 備忘

- Token Budget Rule 遵守：未直接讀大 CSV（attribution、daily returns、positions）。只讀 packet + numbers + cap_summary.csv（8行）+ redistribution_log.csv（前 30 行）+ gate_report.json + log。
- 本 draft 未標記 TASK-007b DONE，未批准 paper execution，未批准 live trading。
- REVIEW-007b 建議 = PASS_CANDIDATE（需 Opus B-1 裁定）。

---

*Draft v1.0 | Claude Sonnet | 2026-05-16*  
*觸發依據：NEXT_ACTION.md Status=READY，Owner=Claude Sonnet，Task=REVIEW-007b draft*  
*參考：REVIEW-007b_PACKET.md、REVIEW-007b_NUMBERS.json、20260516_task007b_cap_summary.csv、20260516_task007b_gate_report.json、20260516_task007b_redistribution_log.csv（前 30 行）、20260516_task007b_weight_cap_redistribution.log*
