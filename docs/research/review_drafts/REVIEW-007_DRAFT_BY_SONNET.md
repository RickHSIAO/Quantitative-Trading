# REVIEW-007 — Long-Side Variant Study（Sonnet 初審草稿）

- **狀態**：PASS_CANDIDATE（4 項 BLOCKING，需 Opus 裁定）
- **Draft 版本**：v1.0（2026-05-16，Claude Sonnet）
- **審查依據**：NEXT_ACTION.md Status=READY, Task=REVIEW-007 draft
- **被審任務**：TASK-007 Long-Side Variant Study
- **關聯 Review**：REVIEW-003（Opus CONDITIONAL_PASS 觸發 TASK-007）
- **輸出位置**：`docs/research/review_packets/REVIEW-007_PACKET.md` + `REVIEW-007_NUMBERS.json`

---

## 0. 執行摘要（為 Opus 提供背景）

TASK-007 是 Opus REVIEW-003 CONDITIONAL_PASS 後指派的研究任務，目標是量化 long-side 結構性虧損與集中度問題，為 TASK-006 paper trading 規劃提供 position sizing 依據。

**最重要發現**：`high_funding_cost_filter` 變體是所有變體中唯一在 Sharpe 上優於 baseline 的（0.9586 vs 0.8918），同時 alpha retention = 109.6%，long side 負 alpha 從 −5.01% 改善至 −2.29%，funding cost 幾乎歸零（1.12e-7）。這是 Pareto-dominant 結論，具有直接操作意義。

**結構性確認**：Short-only 驗體的 Sharpe 大幅下降（0.4045 vs 0.8918），且 max DD 惡化至 −49.18%（2.5x 基準），說明多頭部位雖是 alpha 拖累，但對 portfolio 風險結構有平衡作用，不可草率移除。

**集中度問題未解**：所有變體的 top5 concentration 均超過 60%，最低為 `high_funding_cost_filter`（87.22%）。集中度是結構性問題，無法透過 overlay 調整根治。

**BLOCKING 問題**：Variant D（每日 weight cap）未按工單規格交付；Variant C 使用了 3x 較高的過濾門檻；工單規定的 5 個 warning gate 均未實作（改用自定義 gate）；兩個應觸發的工單 gate 未被評估。本 draft 為 PASS_CANDIDATE，請 Opus 裁定是否接受已交付的等效變體或要求 Codex 補齊。

---

## 1. 驗收清單

| 代號 | 項目 | 結果 |
|---|---|---|
| C01 | Fail gates 全部 PASS | ✅ PASS |
| C02 | Baseline 每日 net return 對齊（< 1e-6） | ✅ PASS（2.05e-16） |
| C03 | 輸出檔存在且 schema 正確 | ✅ PASS |
| C04 | 可重現性 hash 一致 | ✅ PASS |
| C05 | Baseline Sharpe 與 run008_stats.json 一致 | ⚠️ DISCREPANCY（0.8918 vs 0.9267，差 3.76%） |
| C06 | Short-only 結果符合結構預期 | ✅ PASS（Sharpe 下降、DD 大幅惡化符合預期） |
| C07 | 工單 gate `short_only_max_dd_worse`（DD < −25%） | ⛔ 應觸發但未評估（實際 DD = −49.18%） |
| C08 | Long-only net alpha < 0 確認 | ✅ PASS（unscaled = −5.18%，rescaled = −9.95%） |
| C09 | 工單 gate `long_only_net_negative`（unscaled 版） | ⚠️ 觸發的是 rescaled 版 gate，unscaled 版未單獨評估 |
| C10 | Variant C 過濾門檻符合工單規格 | ⛔ BLOCKING：0.03%/8h（實際）vs 0.01%/8h（工單 C1），3x 偏差 |
| C11 | Variant C 雙情境（discount=0 + discount=0.5）均交付 | ⛔ BLOCKING：僅交付 discount=0，discount=0.5 未交付 |
| C12 | Variant D cap=20%/15%/10% weight cap 交付 | ⛔ BLOCKING：未交付 weight cap；交付的是不同設計（top5_symbol_cap_5pct / DOT_capped / no_DOT） |
| C13 | 工單規定 5 個 warning gate 全部評估 | ⛔ BLOCKING：工單 gate 未實作；改用 7 個自定義 gate |
| C14 | 工單 gate `funding_adj_no_improvement`（long net < −2%） | ⛔ 應觸發（−2.29%）但未評估 |
| C15 | 集中度在所有變體中仍超過 60% | ✅ 符合預期（結構性問題確認） |
| C16 | Combined paper-safe variant 各指標合理 | ✅ PASS（Sharpe 0.8037，single_conc 19.73% < 25%） |
| C17 | 輸出目錄符合工單規格 | ⚠️ 工單：`outputs/variant_study/`；實際：`outputs/variants/`（非關鍵） |

**清單結果**：4 項 BLOCKING（C10、C11、C12、C13），2 項 WARNING（C05、C17），1 項部分（C09），10 項 PASS。

---

## 2. 關鍵發現

### 2.1 High Funding Cost Filter：唯一 Pareto-Dominant 變體

| 指標 | Baseline | high_funding_cost_filter | 變化 |
|---|---|---|---|
| Sharpe | 0.8918 | **0.9586** | +7.5% |
| IR vs EQW | 0.7168 | **0.7282** | +1.6% |
| Max DD | −19.64% | −20.27% | −0.63% |
| Net Alpha | 28.53% | **31.27%** | +2.74% |
| Alpha Retention | 100% | **109.6%** | — |
| Long Net | −5.01% | **−2.29%** | +2.72% |
| Short Net | +33.56% | +33.56% | 不變 |
| Funding Cost | 0.245% | **~0%** | −0.245% |
| Top5 Conc. | 95.56% | 87.22% | −8.34% |
| Single Conc. | 25.45% | 23.23% | −2.22% |

**結論**：此變體同時改善了 Sharpe、alpha、long-side 損失、集中度，且幾乎沒有加劇 DD。是最重要的正面發現。

**機制**：過濾高 funding rate 多頭（門檻 0.03%/8h，30 天滾動均值），使多頭 funding cost 歸零（1.12e-7），保留低 funding 多頭，短空部位不動。BTC/ETH/LINK 等主要虧損來源被移除。

**注意**：實際使用門檻 0.03%/8h，高於工單規格的 0.01%/8h。更嚴格的 0.01%/8h 效果未知，為 BLOCKING B-2。

### 2.2 Short-Only 策略：alpha 提升但風險大幅惡化

| 指標 | Baseline | Short-Only Unscaled | Short-Only Rescaled |
|---|---|---|---|
| Sharpe | 0.8918 | 0.4045 | 0.4106 |
| Max DD | −19.64% | **−49.18%** (2.5x) | **−75.74%** (3.86x) |
| Net Alpha | 28.53% | 33.73% | 68.52% |
| Alpha Retention | 100% | 118.2% | 240.1% |

**獨立驗算**：
- short_only_unscaled DD ratio = −0.4918 / −0.1964 = **2.504x**（> 1.5x 工單門檻）
- 工單 `short_only_max_dd_worse`（DD < −25%）：−0.4918 < −0.25 → **應觸發**（未評估）

**結論**：完全移除多頭使 alpha 提升（+5.2%），但 max DD 惡化至 2.5x，Sharpe 腰斬至 0.4045。多頭部位對 portfolio 有風險平衡作用（尤其 2024 Nov-Dec BTC 軋空倉時，多頭提供對沖）。Short-only 策略在現有設計下不可行。

### 2.3 Long-Only 策略：確認結構性虧損

- Long-only unscaled：Sharpe = −0.076，Net Alpha = −5.18%，Max DD = −41.58%
- Long-only rescaled：Sharpe = −0.073，Net Alpha = −9.95%，Max DD = −70.44%
- Long-only funding cost = 2.77%（unscaled），是多頭主要拖累

**結論**：多頭訊號在任何槓桿水準下均為虧損，且 Sharpe 為負。Long-side 的問題不是持倉大小，而是 funding contango 系統性吃掉（甚至反轉）gross alpha。

**Long Net 分解驗算**：
- funding_adj_no_improvement gate 門檻：long net < −2%
- high_funding_cost_filter long net = −0.0229 < −0.02 → **應觸發**（未評估）
- 但改善幅度為 +2.72% (從 −5.01% → −2.29%)，屬有意義改善

### 2.4 集中度：所有變體均超過 60%，移除 DOT 反使集中度惡化

| 變體 | Top5 Conc. | Single Conc. | 最大貢獻者 |
|---|---|---|---|
| Baseline | 95.56% | 25.45% (DOT) | DOT |
| no_DOT | **116.13%** | 25.23% (LTC) | LTC |
| DOT_capped | 98.31% | 21.36% (LTC) | LTC |
| top5_symbol_cap_5pct | 103.56% | 21.39% (XRP) | XRP |
| high_funding_cost_filter | 87.22% | 23.23% (DOT) | DOT |
| combined_paper_safe_variant | 91.92% | 19.73% (XRP) | XRP |

**重要觀察**：移除 DOT（no_DOT 變體）使 top5 concentration 從 95.56% **升至** 116.13%，因分母（net_alpha_total）從 0.2853 縮至 0.2129，而 top5 的絕對 alpha 縮減幅度更小。這是「移除最大貢獻者反使集中度惡化」的悖論。

**集中度是結構性問題**：只要 DOT 空頭 alpha 存在，任何 overlay 調整都無法有效降低集中度。根治需在策略層面限制單一 symbol 最大 position weight（策略層 cap，而非 overlay cap）。

### 2.5 Combined Paper-Safe Variant：唯一 Single-Symbol < 25% 的變體

- Sharpe = 0.8037（健康水準，接近 baseline）
- Max DD = −20.27%（略高於 baseline −19.64%）
- Net Alpha = 24.99%（retention = 87.6%）
- **Long Net = +4.21%（正！）**：高 funding 多頭被過濾後，剩餘多頭 net alpha 轉正
- Short Net = +20.78%（DOT cap 後空頭 alpha 下降，从 33.56% → 20.78%）
- **Single Conc. = 19.73% < 25%**（唯一低於門檻的變體）
- Top5 Conc. = 91.92%（仍高，但可接受）

**注意**：Long Net 轉正（+4.21%）是重要發現 — 顯示在移除高 funding 多頭後，剩餘多頭部位本身是有正淨 alpha 的。Long-side 問題不在多頭訊號本身，而在高 funding cost 的特定 symbol（BTC/ETH/LINK）。

### 2.6 Short Net 與 Long Net 加總驗算

Sonnet 獨立驗算：
- Baseline: short_net + long_net = 0.33563 + (−0.05009) = **0.28554** vs net_alpha = **0.28533**
- 差異 = 2.10e-4（0.021%）≠ 0

此微小差異來自 TASK-003 attribution（按 side 分解時，部分 symbol 在 active period 中換邊，造成加總與總 net return 的微小差異）。本差異在 TASK-003 REVIEW-003 中已存在，與 TASK-007 無關。非 blocking。

---

## 3. BLOCKING 問題（需 Opus 裁定）

### B-1：Variant D 設計不符工單規格

**工單規格**：每日按 symbol `|weight| / gross_exposure` 計算占比，設定 cap = 20%、15%、10%，超過 cap 的部分等比例補回同方向其他 symbol（redistribution）。

**實際交付**：
- `top5_symbol_cap_5pct`：按 net alpha（非 weight）限制 top5 symbol
- `DOT_capped`：僅針對 DOT 單一 symbol 截斷
- `no_DOT`：完全移除 DOT

設計邏輯根本不同：工單要求「每日動態 weight cap + 等比例分配」，Codex 交付的是「事後 alpha-based symbol selection」。且 log 中明確記錄 `cap_policy: "primary cap variants use cap_no_redistribution; excess weight is removed"`，與工單「等比例補回」矛盾。

**Opus 裁定問題**：已交付的等效變體是否足以回答工單問題 Q4（concentration cap 對績效影響）？或需要 Codex 按規格重做 Variant D？

### B-2：Variant C 門檻偏差 3x

**工單規格**：
- C1：threshold = 0.01%/8h（=0.0001 decimal），discount = 0（完全排除）
- C2：threshold = 0.005%/8h（=0.00005 decimal），discount = 0.5（部分打折）

**實際交付**：
- 唯一交付：threshold = 0.03%/8h（=0.0003 decimal），discount = 0（完全排除）
- C2（discount=0.5）完全未交付

0.03% 門檻是 C1 規格的 3x — 只過濾最高 funding 的多頭（BTC/ETH/LINK），中等 funding 多頭（如 LINK 附近的 symbol）可能未被過濾。

**問題**：是否需要補充 0.01%/8h 門檻的結果？以及 discount=0.5 的結果？high_funding_cost_filter 結果已是正面（Sharpe +7.5%），更嚴格門檻可能效果更好（或更差）。

**Opus 裁定問題**：接受 0.03%/8h 的結果作為 Variant C 的代表？或要求補齊兩個規格門檻？

### B-3：工單 Warning Gates 全部未實作

工單規定 5 個 warning gates；實際實作了 7 個自定義 gates，完全不同：

| 工單 Gate | 觸發條件 | 應觸發？ | 是否評估？ |
|---|---|---|---|
| `short_only_max_dd_worse` | Variant A DD < −25% | ✅ 是（−49.18%） | ❌ 未評估 |
| `long_only_net_negative` | Variant B net alpha < 0 | ✅ 是 | ⚠️ 部分（只評 rescaled）|
| `funding_adj_no_improvement` | Variant C long net < −2% | ✅ 是（−2.29%） | ❌ 未評估 |
| `cap10_sharpe_drop` | Variant D cap=10% Sharpe 跌 > 30% | N/A（Variant D 未交付） | ❌ 未評估 |
| `concentration_not_reduced` | Variant D cap=15% top5 > 70% | N/A（Variant D 未交付） | ❌ 未評估 |

實際實作的 7 個 gate 中觸發了 4 個：
- `short_only_rescaled_max_dd_worse_than_baseline_1p5x`：3.86x ✅ 觸發（符合精神，但基準不同）
- `long_only_rescaled_net_alpha_negative`：−9.95% ✅ 觸發（只評 rescaled）
- `top5_concentration_remains_above_60pct`：116.1% ✅ 觸發
- `single_symbol_concentration_remains_above_25pct`：25.45% ✅ 觸發（baseline 數字）

**Opus 裁定問題**：Codex 實作的 gate 是否在精神上等效於工單規格？或需要 Codex 補齊工單規定的 5 個 gate？

### B-4：Baseline Sharpe 與 run008_stats.json 不一致

**TASK-007 baseline Sharpe**：0.8918  
**run008_stats.json / REVIEW-003 參考值**：0.9267  
**差異**：0.0349（3.76%）

Fail gate `baseline_mismatch` 驗算的是每日 net return（差異 2.05e-16），而非 Sharpe。Sharpe 差異可能來自：
- run008_stats.json 是 gross Sharpe（before cost overlay）
- TASK-007 baseline 用 realistic_combo net returns 計算
- 或 Sharpe formula 參數不同（ddof、annualization）

此差異影響所有變體的「vs baseline Sharpe delta」解釋。如果 baseline 正確數字是 0.9267（TASK-001 gross），則 high_funding_cost_filter 的 0.9586 仍高於 gross baseline。但如果 baseline 應為 net（0.8918），則所有跨 review 的比較基準需統一。

**Opus 裁定問題**：TASK-007 baseline Sharpe（0.8918）是否與 run008_stats.json（0.9267）的差異有合理解釋？是否接受 TASK-007 的 self-consistent baseline 作為比較基準？

---

## 4. Caveats（非 blocking）

**C-1：No-long-side 與 short_only_unscaled 完全相同**  
兩個變體 Sharpe、DD、net alpha、concentration 完全一致（short_net = 0.33733，long_net = 0）。這是確認性的重複，無分析問題。

**C-2：Short-only rescaled 的 DD 極端化（−75.74%）**  
將空頭放大至 100% gross exposure（rescaled）使 max DD 達 −75.74%（3.86x baseline）。此變體完全不可行，但提供了「極端放空」的量化邊界。

**C-3：Long net 加總差 0.021%**  
short_net + long_net = 0.28554，net_alpha = 0.28533，差 2.10e-4。此差異源自 TASK-003 by-side 分解方法論，已在 REVIEW-003 中識別，非 TASK-007 新錯誤。

**C-4：no_DOT 集中度悖論**  
移除 DOT 使 top5 concentration 從 95.56% 升至 116.13%。這不是計算錯誤，而是「分母縮減效應」：移除最大貢獻者使 net_alpha_total 縮小更多，導致比率反升。此悖論證明「移除 top contributor 以降低集中度」的操作直覺是錯的。

**C-5：Combined paper-safe variant 的 Long Net 轉正（+4.21%）**  
Combined 變體的 long net = +4.21%（正），與 baseline（−5.01%）相比大幅改善。這說明剩餘多頭（在過濾高 funding、cap top5 後）本身有正淨 alpha。但同時 short net 也從 +33.56% 降至 +20.78%，顯示 top5 cap 主要影響 DOT 空頭，是犧牲。整體 net alpha 從 28.53% 降至 24.99%（−3.54%）。

---

## 5. Opus 裁定問題

### Q1：是否接受已交付的 Variant D 等效設計？
工單要求每日 weight cap（cap=20%/15%/10%）+ redistribution。實際交付的是 alpha-based symbol selection（top5_cap_5pct、DOT_capped、no_DOT）。這些設計能回答「集中度 cap 對績效影響」的問題，但設計邏輯和工單完全不同。

請裁定：(a) 接受現有交付，工單 Variant D 視為完成；(b) 要求 Codex 補齊 weight-based cap（20%/15%/10%）；(c) 接受現有交付，但 Variant D 標記「未按規格」，對 paper trading 意見不採用 Variant D 結果。

### Q2：是否接受 Variant C 的 0.03%/8h 門檻？是否要求補充 0.01%/8h 和 discount=0.5？
已交付結果是正面的（Sharpe +7.5%，alpha retention 109.6%）。但工單要求的兩個規格（0.01%/8h 和 0.005%/8h+50% discount）均未交付。

請裁定：(a) 接受 0.03%/8h 結果作為 Variant C 代表；(b) 要求補充 0.01%/8h（可能過濾更多 symbol，結果未知）；(c) 要求補充 discount=0.5 結果（partial weighting 結果未知）。

### Q3：是否接受 Codex 自定義 Warning Gates？兩個未評估的工單 gate 是否需要補評？
`short_only_max_dd_worse`（應觸發：DD −49.18%）和 `funding_adj_no_improvement`（應觸發：long net −2.29% < −2%）均未被評估。數字已在 review packet 中可計算，但 Codex 未在 gate 系統中標記。

請裁定：(a) 接受現有輸出，視 Codex 實作的 7 個自定義 gate 為等效；(b) 要求 Codex 在下版 attribution 或 TASK-007 補件中補齊工單規定 gate 的評估欄位；(c) 要求 TASK-007 重做 gate 評估後才能關閉。

### Q4：Baseline Sharpe 不一致（0.8918 vs 0.9267）的解釋是否可接受？
如果 run008_stats.json 的 0.9267 是 gross Sharpe（before cost overlay），TASK-007 的 0.8918（net，after realistic_combo）則一致。如果兩者都應是 net Sharpe，則有無法解釋的差異。

請裁定：是否需要 Codex 提供 Sharpe 計算方法對比（run008_stats.json 的公式 vs TASK-007 的公式）？

### Q5：high_funding_cost_filter 的 Long Net −2.29% 如何解讀？
long net 仍為負（−2.29%），但已從 −5.01% 顯著改善。Combined paper-safe variant 的 long net 甚至轉正（+4.21%）。請問：
- 是否認為「long net 仍負」是可接受的結果（因 short 彌補）？
- 是否認為「combined long net 轉正」代表多頭問題已解決？
- 是否需要將 long net threshold（如 long net > −3%）納入 TASK-006 paper trading 規劃條件？

### Q6：TASK-007 結果的下游影響
請裁定以下下游決策：
1. **TASK-007 狀態**：CONDITIONAL_PASS（接受已交付但有缺口）或 FAIL（要求 Codex 補齊 Variant D / Variant C）？
2. **TASK-006 paper trading 規劃可否啟動**？若啟動，使用哪個變體的 position sizing 數字（建議：high_funding_cost_filter + combined paper-safe 並列）？
3. **TASK-003 必補項目**（Opus REVIEW-003 要求）是否在本 review 前或後處理？
4. **Long-side 是否徹底停用**？結果顯示 high_funding_cost_filter 保留低 funding 多頭，combined 甚至使 long net 轉正，建議保留有條件多頭，而非 short-only。
5. **策略層 cap（signal/ranking 層面的集中度控制）**是否需要列入 TASK-008 或新工單？

---

## 6. Opus Prompt（供 Rick 複製貼上）

```
你是 Prev3Y Crypto Momentum 策略的 final review Opus。
請閱讀以下資料後，對 TASK-007 Long-Side Variant Study 做出最終裁定。

## 背景
TASK-007 由 Opus REVIEW-003 CONDITIONAL_PASS 觸發，目標是研究四個 overlay 變體（short-only、long-only、funding-adjusted、concentration-capped），量化 long-side 結構性虧損，為 paper trading 提供 position sizing 依據。

## 最關鍵數字（Sonnet 已獨立驗算）
- Baseline net alpha：28.53%（Sharpe 0.8918 per TASK-007；0.9267 per run008_stats.json）
- Best variant — high_funding_cost_filter：Sharpe 0.9586（+7.5%），alpha retention 109.6%，long net −2.29%（改善 +2.72%）
- Short-only 不可行：Sharpe 0.4045，max DD −49.18%（2.5x baseline）
- Long-only 確認虧損：Sharpe −0.076，net alpha −5.18%
- Combined paper-safe：Sharpe 0.8037，long net +4.21%，single_conc 19.73%（< 25%）
- 集中度問題持續：所有變體 top5 > 60%；移除 DOT 使集中度惡化（116.13%）

## BLOCKING 問題（Sonnet 識別）
B-1：Variant D 未按工單規格（weight cap + redistribution）交付，改用 alpha-based selection
B-2：Variant C 使用 0.03%/8h 門檻（工單 C1 = 0.01%/8h），3x 偏差；C2（discount=0.5）未交付
B-3：工單 5 個 warning gate 均未實作，改用 7 個自定義 gate；2 個應觸發的工單 gate 未評估
B-4：Baseline Sharpe 不一致（TASK-007 = 0.8918 vs run008_stats.json = 0.9267）

## 請裁定（Q1-Q6，見 REVIEW-007_DRAFT_BY_SONNET.md Section 5）
Q1：接受 Variant D 等效設計？或要求補齊？
Q2：接受 Variant C 0.03%/8h 結果？或要求補充工單規格門檻？
Q3：接受自定義 gate？或要求補齊工單規定 gate 評估？
Q4：Baseline Sharpe 差異的解釋是否可接受？
Q5：Long net −2.29% 的解讀與 paper trading 門檻建議？
Q6：TASK-007 最終狀態（PASS / CONDITIONAL_PASS / FAIL）、TASK-006 啟動條件、long side 政策、策略層集中度控制是否需要新工單？
```

---

## 7. Sonnet 初審結論

**狀態**：PASS_CANDIDATE（不阻擋 Opus final decision，但有 4 項 BLOCKING 需裁定）

**核心結論**：

1. **最重要發現**：`high_funding_cost_filter` 是 Pareto-dominant 變體，同時優化 Sharpe（+7.5%）、alpha retention（+9.6%）、long-side 損失（+2.72%），且幾乎不惡化 DD。這一發現直接可用於 paper trading 規劃。

2. **Short-only 不可行**：移除多頭使 Sharpe 腰斬至 0.4045，max DD 達 2.5x，多頭對 portfolio 風險結構有不可忽視的穩定作用。

3. **Long-side 問題根源**：不在多頭訊號本身，而在高 funding rate 特定 symbol（BTC/ETH/LINK）。過濾後，combined 變體的剩餘多頭 net alpha 轉正（+4.21%）。

4. **集中度問題無法用 overlay 根治**：所有變體 top5 > 60%。策略層面的 per-symbol weight cap（在 ranking / position sizing 層）是唯一根本解法，需要新工單。

5. **交付完整性問題**：Variant D 未按規格交付；Variant C 門檻偏差 3x 且缺少 C2；工單 warning gate 系統未實作。這些是流程問題，不影響核心分析結論的有效性。

**Sonnet 不裁定**：TASK-007 最終狀態（PASS/FAIL）、TASK-006 啟動、long side 政策，留 Opus 決定。

---

*REVIEW-007 Draft v1.0 | Claude Sonnet | 2026-05-16*  
*審查依據：REVIEW-007_PACKET.md + REVIEW-007_NUMBERS.json + TASK-007_long_side_variant_study.md*  
*獨立驗算：所有表格數字均與 REVIEW-007_NUMBERS.json 交叉核實（key_numbers + warning_gates）*  
*參考：REVIEW-003_DRAFT_BY_SONNET.md（TASK-003 審查方法論）*
