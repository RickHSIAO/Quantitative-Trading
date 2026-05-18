# REVIEW-003 Draft — Baseline Attribution
# 由 Claude Sonnet 初審，2026-05-15

```
狀態：PASS_CANDIDATE（含 2 個 BLOCKING 問題需 Opus 裁定）
審查者：Claude Sonnet
依據工單：docs/research/codex_workorders/TASK-003_baseline_attribution.md v1.0
審查輸出：outputs/attribution/prev3y_crypto/20260515_attribution_*
```

---

## 一、Checklist（14 項）

| # | 項目 | 結果 | 說明 |
|---|---|---|---|
| C01 | 全部 11 個輸出檔存在 | ✅ PASS | fail_gate: missing_output_files = false；路徑全在 summary.json output_paths |
| C02 | Schema 正確（欄位名、型別） | ✅ PASS | fail_gate: schema_mismatch = false；errors = [] |
| C03 | Gross 逐日對帳（symbol sum vs run008） | ✅ PASS | max diff = 1.05e-16 < 1e-6；bad_days = 0 |
| C04 | Net 逐日對帳（symbol sum vs realistic_combo） | ✅ PASS | max diff = 2.05e-16 < 1e-6；bad_days = 0 |
| C05 | By-month 對帳：各月 net 合計 = by-year net | ✅ PASS | 2024: 0.04274329；2025: 0.25460075；2026: -0.01201849；Grand total = 0.28532555 ≈ net_alpha_total（機器精度） |
| C06 | By-year 對帳：各年 net 合計 = net_alpha_total | ✅ PASS | 0.04274 + 0.25460 − 0.01202 = 0.28532 = net_alpha_total（±1e-10） |
| C07 | Fail gates 全通過 | ✅ PASS | 4/4 gates 未觸發；symbol_pnl mismatch 1.05e-16、net_pnl mismatch 2.05e-16 |
| C08 | 可重現性 hash 通過 | ✅ PASS | reproducibility_hash_check_passed = true；hash = 483ad042… |
| C09 | Input hashes 已記錄（run008 + TASK-002） | ✅ PASS | summary.json 含 10 個 input hash；run008_baseline_csv = 051b89b2…；cost_stress_csv = f8663c9e… |
| C10 | 方法論對齊（per-interval funding、realistic_combo 主口徑） | ✅ PASS | methodology 區塊明確記錄 return_dating、gross_formula、net_formula；primary_scenario = realistic_combo |
| C11 | Warning gate: single_year_concentration | ⚠️ TRIGGERED | 2025 年佔 85.6%（threshold 70%）；workorder 公式計算 = 89.2%（詳見第二節） |
| C12 | Warning gate: gross_net_rank_divergence | ⚠️ TRIGGERED | 最大排名差 = 13（BTCUSDT.P gross rank 40 → net rank 53）；threshold 10 |
| C13 | Warning gate: top5_symbol_concentration | 🔴 BLOCKING | Codex 回報 28.9%（NOT triggered）；Sonnet 獨立計算 = 95.6%（TRIGGERED）；公式定義不一致，需 Opus 裁定 |
| C14 | Warning gate: single_symbol_concentration | 🔴 BLOCKING | Codex 回報 7.7%（NOT triggered）；Sonnet 計算 DOT = 25.5%（TRIGGERED）；同為公式問題 |

### 其他 Warning Gates 結果

| Gate | 結果 | 實際值 | 說明 |
|---|---|---|---|
| short_side_drag | ✅ NOT triggered | short net alpha = +33.6%（正值） | Gate 定義為「short 為負」，此處 short 為正且主導策略 |
| funding_gap_concentration | ✅ NOT triggered | gap 7 symbols = 3.4%（Codex）/ 11.1%（workorder spec） | 兩種公式均低於 20% threshold |

---

## 二、關鍵發現

### 2.1 Concentration Gate 公式不一致（BLOCKING）

工單規格明確定義：
- `top5_symbol_concentration` = **top5 net alpha 貢獻 / net_alpha_total**
- `single_symbol_concentration` = **單一 symbol net alpha 貢獻 / net_alpha_total**

Codex 實際使用：
- 分母 ≈ **所有 symbol 的 |net_alpha_contribution| 總和**（估算 ≈ 0.9429）

兩種公式的結果差異：

| 指標 | Codex 公式（/sum_abs_net） | Workorder 公式（/net_alpha_total） | Gate 結果差異 |
|---|---|---|---|
| Top 5 concentration | 28.9% | **95.6%** | NOT triggered vs **TRIGGERED** |
| DOT single symbol | 7.7% | **25.5%** | NOT triggered vs **TRIGGERED（邊界）** |
| funding_gap (7) | 3.4% | 11.1% | NOT triggered（兩者均低於 20%） |

**計算基礎（Sonnet 獨立驗算）：**
- Top 5 net contributions（DOT+LTC+XRP+XLM+ZEC）= 0.2727（累計）
- Net alpha total = 0.2853
- Top 5 / net_alpha_total = **0.2727 / 0.2853 = 95.6%**

**Opus 裁定問題 Q1：** 工單公式（分母 = net_alpha_total）是正確規格，還是接受 Codex 的替代定義（分母 = sum_abs_net）？若維持工單規格，top5 gate 和 single-symbol gate 均須改為 TRIGGERED，代表策略極度集中於少數 symbol，是重大風險。

---

### 2.2 Long Side Alpha 為負（結構性問題，未被 Gate 捕捉）

**By-side 結果：**

| Side | Gross Alpha | Net Alpha | 說明 |
|---|---|---|---|
| Short | +31.6% | **+33.6%** | 淨空頭獲得 funding income（負 cost） |
| Long | −2.0% | **−5.1%** | 淨多頭虧損，cost 進一步拖累 |
| Combined | +29.6% | **+28.5%** | Short side 貢獻 **117.9%** of net alpha |

**含義：**
- 策略的全部 net alpha 來自空頭部位；多頭部位在 gross 和 net 兩個口徑下均為負。
- 多頭部位的高 funding cost（持有 BTC/ETH/LINK 等大市值正資金費率幣種）進一步拖累 net。
- 現行 `short_side_drag` gate 只檢查「空頭是否為負」；策略中空頭為正，gate 不觸發。但真正的問題是**多頭為負**，沒有 gate 捕捉這個結構性風險。

**極端案例：**
- `BTCUSDT.P`：gross rank 40（+0.46%）→ net rank 53（**−0.07%**）。BTC 被動量訊號排進多頭，但 funding cost 0.51% 完全吞噬並翻轉 gross alpha。
- `ETHUSDT.P`：gross −0.63%，net −1.20%（funding cost 0.55% 疊加在已為負的 gross 上）。
- `LINKUSDT.P`：gross −1.70%，net −2.32%（funding cost 0.60%）。

**Opus 裁定問題 Q2：** 多頭持續虧損是否反映策略邏輯缺陷（例如：「3 年低動量」在加密幣上本質是反市場β做空策略，而非真正的多空動量）？是否應研究純空頭或調整多頭信號的設計？

---

### 2.3 年份集中：2025 年佔 85–89%（TRIGGERED）

| 年份 | Active Days | Net Alpha | 佔比（/net_alpha_total） |
|---|---|---|---|
| 2024（Q2–Q4） | 275 | +4.27% | 15.0% |
| 2025（全年） | 365 | **+25.46%** | **89.2%** ← TRIGGERED |
| 2026（Jan–Apr） | 120 | −1.20% | −4.2% |

2025 年各月均勻度：
- 正月份：Jan, Mar, Apr, Jun, Jul, Aug, Oct, Nov, Dec（9/12）
- 負月份：Feb, May, Sep（3/12）
- 最大單月：Oct 2025 (+5.1%)、Jul (+5.3%)、Dec (+5.2%)

**Opus 裁定問題 Q3：** 760 天中 89% alpha 集中在某一日曆年，是否意味策略仍需更多樣本（跨多個市場週期）才能做 paper trading 決策？2024 年的回測僅涵蓋 9 個月，2026 目前為負，樣本分佈高度不均。

---

### 2.4 Top 7 Symbol 超過 100% Net Alpha

即便使用 Codex 的寬鬆公式，頂部 symbol 的集中度仍極高：

**Top 7 net alpha 貢獻（累計 36.5%）= 127.9% of net alpha total（0.285）**

這意味著 top 7 以外的 symbol 合計貢獻 **−27.9%**（虧損），與 top 7 的獲利對沖後才剩 net alpha = 28.5%。

**Net alpha 正貢獻 symbol（前 10 名）：**

| Rank | Symbol | Net Contribution | Side | Gap? | Interval |
|---|---|---|---|---|---|
| 1 | DOTUSDT.P | +7.26% | Short | No | 8h |
| 2 | LTCUSDT.P | +5.37% | Long | No | 8h |
| 3 | XRPUSDT.P | +5.01% | Long | No | 8h |
| 4 | XLMUSDT.P | +4.82% | Long | No | 8h |
| 5 | ZECUSDT.P | +4.81% | Long | No | 8h |
| 6 | XTZUSDT.P | +4.72% | Short | **Gap** | 4h |
| 7 | FLOWUSDT.P | +4.51% | Short | **Gap** | 8h |
| 8 | GALAUSDT.P | +3.87% | Short | No | 8h |
| 9 | EGLDUSDT.P | +3.63% | Short | No | 8h |
| 10 | SANDUSDT.P | +3.22% | Short | No | 8h |

**注意：** Top 6 和 Top 7（XTZ、FLOW）皆為 funding gap symbols。其 cost=0 的處理可能讓其 net alpha 被高估（若加入真實 funding cost，排名可能後退）。

---

### 2.5 Funding Gap Symbols：個別差異大，整體合理

Gap 7 symbols 的 net alpha 分佈：

| Symbol | Net Alpha | Side | 說明 |
|---|---|---|---|
| XTZ | +4.72% | Short | Top 6 整體表現佳；但 interval label 為 4h（實際 8h 間距，已知 caveat） |
| FLOW | +4.51% | Short | Top 7；cost=0 對其 net 有利 |
| RVN | +0.30% | Short | 小幅正貢獻 |
| CTC | −0.41% | Long | 小幅負貢獻 |
| AXS | −1.11% | Short | 中等負貢獻 |
| INJ | −1.84% | Long | 負貢獻（持多且有 funding cost） |
| LPT | −3.01% | Short | 最大負貢獻 gap symbol |
| **合計** | **+3.17%** | — | 11.1% of net alpha（workorder 公式）；未觸發 20% gate |

XTZ 和 FLOW 是兩個正值 gap symbol，各自都有真實的 alpha 貢獻，但其 funding cost 在 TASK-002 中為 0（gap 處理），net alpha 可能被高估。若以現實 funding 水準估算補入，排名可能各退 1–2 名，但仍在正貢獻範圍內（初步估算，非正式）。

---

### 2.6 Drawdown Analysis：Nov–Dec 2024 集中事件

**Max drawdown：**
- 開始：2024-11-15
- 最低：2024-12-06
- 幅度：−19.50%（與 run008 一致）

**Drawdown 期間 top 5 負貢獻（加重 drawdown）：**
1. XLMUSDT.P（long）：+5.18%（**positive，幫助緩和**）
2. ALGOUSDT.P（short）：−3.95%（空頭被軋）
3. KSMUSDT.P（short）：−3.91%（空頭被軋）
4. XRPUSDT.P（long）：+3.83%（**positive，幫助緩和**）
5. CRVUSDT.P（short）：−3.63%（空頭被軋）
6. XTZUSDT.P（short）：−3.07%（空頭被軋）

**Drawdown 結構：** 主要由空頭部位被軋所致（Nov–Dec 2024 = BTC 從 $75k 漲至 $100k，altcoin 同步暴漲，空頭 ALGO/KSM/CRV/XTZ 等遭受軋倉）。多頭 XLM 和 XRP 在同期逆市上漲，部分對沖了空頭損失。

---

### 2.7 Funding Interval 分組

| Interval | Symbols | Gross Alpha | Net Alpha | 說明 |
|---|---|---|---|---|
| 8h | 77 | +24.4% | +23.2% | 主要持倉群；cost drag 約 1.2% |
| 4h | 13 | +5.2% | **+5.4%** | net > gross：4h 空頭持有 funding income 淨為正 |
| 1h | 0 | — | — | Active period 無 1h symbol 持倉（預期行為） |

4h symbols 的 net 高於 gross，驗證了 TASK-002 的發現：4h 結算周期、空頭持有正 funding rate → funding 為淨收入。

---

### 2.8 Cost Structure：Slippage 仍是最大成本

| Cost Type | 累計金額 | 佔 Gross Alpha | 佔 Total Cost |
|---|---|---|---|
| Slippage | 0.4501% | 1.52% | **42.9%** |
| Fee | 0.3551% | 1.20% | 33.8% |
| Funding | 0.2452% | 0.83% | 23.3% |
| **Total** | **1.0505%** | **3.55%** | 100% |

與 TASK-002 一致：Slippage > Fee > Funding。Cost drag 整體溫和（3.55% of gross），不影響策略存活。

---

## 三、Non-Blocking Caveats（C-1 ~ C-5）

**C-1：BTC/ETH/LINK 多頭 net 為負（Funding Contango Problem）**
BTC（rank 40→53）、ETH（rank 61→70）、LINK（rank 76→79）在 net 口徑下均更差或轉負。這三個大市值幣種長期處於 funding 正值（多頭支付 funding），momentum 訊號將其排入多頭，但 funding cost 侵蝕所有 gross alpha。這是策略在高 funding 環境下的系統性弱點。

**C-2：Drawdown 為特定事件型（BTC $100k 軋倉）**
Nov–Dec 2024 的 drawdown 主要由 BTC 史上首度觸及 $100k 引發的 altcoin 全面上漲（空頭軋倉）造成。此為非典型事件，不代表策略在一般市況下的 drawdown 輪廓。但若未來再出現類似 BTC 牛市加速段，空頭側將再次承壓。

**C-3：2026 Jan 單月 −5.5% 已在 Feb–Mar 部分收復**
2026 前 4 個月：Jan −5.5%、Feb +4.4%、Mar +4.3%、Apr −4.4%。前 4 個月為 −1.2%，但 April 的負值可能與 2026 全球不確定性（非策略固有問題）有關。樣本不足以判斷趨勢。

**C-4：XTZ 的 interval_hours label 問題**
XTZ 在 funding_rates.parquet 中標記 `interval_hours=4` 但實際結算間距為 8h（已知 TASK-002 caveat C-1）。Attribution 中 XTZ 被歸入 4h 組，實際為 8h 結算。此對分組分析有輕微影響，但不影響 cost 計算（TASK-002 已採 per-row 累計）。

**C-5：Funding Gap Symbol 的 Net Alpha 可能被高估**
XTZ 和 FLOW 的 net_alpha > gross_alpha（因為 short 持有時 funding 為收入，gap 處理讓這部分確實為 0，但真實 funding 收入理論上應為正）。TASK-002 選擇對 gap symbol 全部記為 cost=0（無 fill），略微低估了這些 symbol 的 net alpha。但此為已知且保守的處理，不影響審查結論。

---

## 四、Opus 必須裁定的問題（6 項）

**Q1（BLOCKING）：Concentration Gate 公式定義**
工單規格：分母 = net_alpha_total。Codex 實作：分母 = sum_of_all_abs_net_contributions。
採用工單規格時：top5 = 95.6%（TRIGGERED）、DOT = 25.5%（TRIGGERED）。
Opus 需裁定：採用哪一定義？若採工單規格，則策略集中度問題為 major finding，需評估 paper trading 前的 position sizing risk。

**Q2（BLOCKING）：Long Side 持續虧損的策略含義**
Long side net alpha = −5.1%（gross −2.0%）。策略全部 alpha 來自空頭，多頭主動拖累。
Opus 需裁定：這是否改變「Prev3Y momentum 在 crypto 上 work」的結論？是否需在 paper trading 規劃中對多頭部位設置更嚴格的 size cap 或條件？

**Q3：年份集中（2025 = 85–89%）是否達到研究暫停標準**
Opus 裁定：760 天、89% alpha 集中 1 年的情況，是否仍支持「保留策略、進入 paper trading 規劃」的判定？還是需要先延長回測期或補充 out-of-sample 數據？

**Q4：BTC/ETH 大市值多頭 net 為負的處理建議**
BTC 和 ETH 是市場最具代表性的資產。其 gross positive 被 funding cost 翻轉為 net negative，是否建議在 TASK-004 dashboard 加入「high-funding-cost symbol 警示」？是否需要研究對高 funding rate symbol 的多頭訊號做 discount 處理？

**Q5：Long Side Drag Gate 補充**
現有 `short_side_drag` gate（短空為負）未捕捉到多頭為負的情況。Opus 需裁定：是否需要 Codex 在下一版補一個 `long_side_drag` gate？

**Q6：Paper Trading 規劃是否可解鎖（前提：Q1–Q3 答案均合理）**
若 Opus 判定 concentration gate 採用 Codex 的寬鬆定義、長空結構為策略特性而非缺陷、年份集中可接受，則 paper trading 可否開始規劃？若採用工單嚴格定義，paper trading 是否需要加入 single-symbol position cap？

---

## 五、Suggested Opus Prompt

以下 prompt 可在 Rick 確認後直接貼給 Opus 執行 REVIEW-003 final decision。

---

```
你現在使用 Opus，請執行 REVIEW-003 final decision。

請只讀最小審查包：
1. docs/research/review_drafts/REVIEW-003_DRAFT_BY_SONNET.md
2. outputs/attribution/prev3y_crypto/20260515_attribution_summary.json
3. outputs/attribution/prev3y_crypto/20260515_attribution_by_side.csv
4. outputs/attribution/prev3y_crypto/20260515_attribution_by_year.csv
5. outputs/attribution/prev3y_crypto/20260515_attribution_by_symbol.csv（前 20 行即可）

請不要重新執行 attribution 分析。
請不要修改任何輸出檔案或策略程式。

請就以下 6 個問題做出明確裁定：

Q1：Concentration gate 公式
   工單規格：top5 / net_alpha_total = 95.6% → TRIGGERED
   Codex 實作：top5 / sum_abs_net = 28.9% → NOT triggered
   ↳ 採用哪個定義？若採工單規格，top5 和 single-symbol gate 皆應 TRIGGERED。

Q2：Long side net alpha = −5.1%
   短空貢獻 117.9% net alpha；多頭虧損。
   ↳ 這是否影響策略研究判定？需要設 long-side position cap？

Q3：2025 年佔 89% net alpha（workorder 公式）
   ↳ 樣本集中是否影響 paper trading 解鎖？

Q4：BTC/ETH 大市值多頭 net 為負（funding contango）
   ↳ 是否需要研究 high-funding-cost discount 訊號？

Q5：是否補充 long_side_drag warning gate？
   ↳ 建議 Codex 下一版加入。

Q6：在 Q1–Q3 答案清楚後，是否允許：
   - TASK-003 轉 DONE？
   - TASK-004 dashboard 開始規劃？
   - TASK-005 VPS monitor 開始規劃？
   - Paper trading 開始規劃（TASK-006）？
   - Live trading 是否仍禁止？
   - 策略判定維持「保留」？還是需要降格？

請把結果追加到：
- docs/research/CLAUDE_REVIEW_LOG.md

並更新：
- docs/research/CODEX_TASK_QUEUE.md（TASK-003 狀態）
- docs/research/CLAUDE_REVIEW_QUEUE.md（REVIEW-003 狀態）
```

---

## 六、Sonnet 審查結論

```
Suggested model:         Opus（final decision 必需）
Escalation reason:       Concentration gate 公式衝突（top5 = 95.6% vs 28.9%）；
                         Long side net 為負屬結構性問題，超出 Sonnet 可判範圍。
Opus final decision required: Yes

Sonnet 初審判定：PASS_CANDIDATE
- Fail gates：4/4 PASS
- 資料對帳：機器精度，可重現性 hash 通過，輸入 hash 完整
- 已觸發 gates：single_year_concentration（85.6%）、gross_net_rank_divergence（13）
- BLOCKING 問題：concentration gate 公式定義（Q1）、long side 負 alpha（Q2）

不可在 Opus 裁定前：
- 將 TASK-003 標記 DONE
- 啟動 TASK-004 / TASK-005 / TASK-006
- 批准 paper trading 規劃
```

---

*草稿版本 v1.0｜撰寫：Claude Sonnet｜日期：2026-05-15*
*依據：TASK-003 workorder v1.0、20260515 attribution 官方輸出、獨立數值驗算*
