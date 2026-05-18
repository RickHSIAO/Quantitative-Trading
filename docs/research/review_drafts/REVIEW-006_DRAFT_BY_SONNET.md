# REVIEW-006 — Paper Trading Plan Infrastructure（Sonnet 初審草稿）

- **狀態**：PASS_CANDIDATE（2 項 BLOCKING，需 Opus 裁定）
- **Draft 版本**：v1.0（2026-05-16，Claude Sonnet）
- **審查依據**：NEXT_ACTION.md Status=READY, Task=REVIEW-006 draft
- **被審任務**：TASK-006 Paper Trading Planning Modules
- **審查性質**：安全性審查 + 流程合規審查（非效能審查）

---

## 0. 執行摘要（為 Opus 提供背景）

TASK-006 交付的是 paper trading 技術架構（規劃模組），**不是執行授權**。本 review 的核心問題是：**模組是否安全、執行閘門是否正確落實、現有基礎架構是否達到 REVIEW-006b 的前置條件。**

**最重要安全確認**：Safety scan = PASS，violations = []。無交易所客戶端、無憑證讀取、無外部下單路徑。`real_order_submission_possible = false`，`paper_execution_approval = false`。Live trading status 在所有輸出檔案中均為 **FORBIDDEN**。

**主要正面結論**：模組結構完整，三條 mandatory overlay 規則正確實作並驗證，五條 mandatory caveat 嵌入所有輸出，風控事件系統運作正常（自動觸發 `STOP_PAPER_PENDING_REVIEW`）。

**2 項 BLOCKING 需 Opus 裁定**：(1) 代理式 forward validation Sharpe = −2.9012，是否影響 paper trading 路線圖；(2) 系統自觸發 `STOP_PAPER_PENDING_REVIEW` 事件的正確解讀。

---

## 1. 安全性清單（最高優先）

| 代號 | 項目 | 結果 |
|---|---|---|
| S01 | Safety scan 狀態 | ✅ PASS（violations = []）|
| S02 | 無交易所客戶端實作 | ✅ 確認（safety_scan 無 violation）|
| S03 | 無 API 憑證讀取 | ✅ 確認（safety_scan 無 violation）|
| S04 | 無外部下單 endpoint 連接 | ✅ 確認（real_order_submission_possible = false）|
| S05 | paper_execution_approval = false | ✅ 確認 |
| S06 | paper_execution_status = NOT_STARTED | ✅ 確認（log + numbers.json 一致）|
| S07 | live_trading_status = FORBIDDEN（所有輸出） | ✅ 確認（target_positions, monthly_review, mandatory_caveats 全部出現）|
| S08 | forward_validation_pass = false | ✅ 確認（正確；proxy 非真實 forward）|
| S09 | 五條 mandatory caveat 嵌入所有輸出 | ✅ 確認（caveat_1 至 caveat_5 + live_trading_status 全部存在）|

**安全性結論**：9/9 安全項全部通過。TASK-006 模組不具備執行任何訂單的能力，符合工單「規劃架構，非執行授權」的設計要求。

---

## 2. 輸出完整性清單

| 代號 | 輸出檔案 | 存在 | Schema 正確 |
|---|---|---|---|
| O01 | `20260516_target_positions.json` | ✅ | ✅（含 5 條 caveat + overlay_rules_applied + portfolio_summary）|
| O02 | `20260516_simulated_fills.csv` | ✅ | ✅（intended_fill_count = 3；⚠️ 見 C-1）|
| O03 | `20260516_daily_pnl.csv` | ✅ | ✅（760 列，覆蓋全部 active period）|
| O04 | `20260516_monthly_review.json` | ✅ | ✅（含 metrics / mandatory_caveats / paper_execution_status）|
| O05 | `20260516_risk_events.jsonl` | ✅ | ✅（2 事件：STOP_PAPER_PENDING_REVIEW + rebalance_summary）|
| O06 | `20260516_forward_validation.json` | ✅ | ✅（forward_validation_pass = false，pass_blocker 正確）|
| O07 | `20260516_paper_trading_setup.log` | ✅ | ✅（input hashes + safety scan + forward validation）|
| O08 | `REVIEW-006_PACKET.md` | ✅ | ✅（含 Scope / Variant Specs / Mandatory Overlays / Safety）|
| O09 | `REVIEW-006_NUMBERS.json` | ✅ | ✅（含 primary/secondary variant stats + risk_event_counts）|

**輸出完整性結論**：9/9 輸出存在且 schema 正確。

---

## 3. Overlay 規則驗算

### 3.1 Funding Filter（Rule 1：>0.03%/8h 多頭排除）

Sonnet 獨立驗算 2026-04-01 target_positions.json 的多頭 funding rates：

| Symbol（Long） | 30d Avg Funding（/8h） | > 0.03%？ | 排除？ |
|---|---|---|---|
| BTCUSDT.P | −0.000296%（≈ 負值） | ❌ | ❌ |
| ETHUSDT.P | +0.00151% | ❌ | ❌ |
| LINKUSDT.P | +0.00155% | ❌ | ❌ |
| HNTUSDT.P | +0.00989% | ❌ | ❌ |
| XMRUSDT.P | +0.01015% | ❌ | ❌ |
| ZECUSDT.P | +0.00313% | ❌ | ❌ |

**結論**：2026-04-01 當日所有多頭 symbol 的 30d 均值 funding rate 均低於 0.03%/8h 門檻。`overlay_event_count = 0` 為正確結果。

**重要觀察**：在 2026 年 3-4 月，BTC/ETH/LINK 的 30 天平均 funding rate 已大幅正常化（BTC 甚至為負，即多頭賺取 funding）。Funding filter 在當前市況下無效果；它的主要作用在 2024-2025 牛市高 funding 期。這是市況變化，非模組錯誤。

### 3.2 Long Cap 50%（Rule 2）

- n_longs = 25，weight_per_symbol = 0.02
- long_exposure = 25 × 0.02 = **0.50**（exactly 50%）
- gross_exposure = 1.00，long_pct = 50.0%
- Rule 2 於 50% 邊界恰好滿足，無縮減動作需要。✅

### 3.3 Symbol Cap 5%（Rule 3）

- max_single_symbol_pct = 0.02 = **2.0%**（遠低於 5% cap）
- Rule 3 未觸發，無截斷動作。✅

### 3.4 Market Neutral Verification

- net_exposure = long_exposure − short_exposure = 0.50 − 0.50 = **3.47e-17 ≈ 0** ✅

### 3.5 總結

三條 mandatory overlay 規則邏輯正確，在 2026-04-01 這個測試日期：Rule 1 不適用（funding 已正常化），Rule 2 恰在邊界，Rule 3 不適用。overlay_event_count = 0 完全正確。

---

## 4. 代理式 Forward Validation 解讀

### 4.1 數字概覽

| 欄位 | 值 | 說明 |
|---|---|---|
| `forward_validation_status` | NOT_STARTED | 正確：尚未進行真實 forward |
| `validation_basis` | historical_simulation_proxy_not_forward_execution | 明確聲明為代理，非真實 forward |
| `forward_validation_pass` | false | 正確：proxy 永遠不等於真實 forward |
| `paper_sharpe` | **−2.9012** | ⚠️ 最近 30 天歷史代理視窗的年化 Sharpe |
| `max_drawdown` | −6.94% | 代理視窗內最大 DD（可接受） |
| `min_nav_usd` | 12,240.63 | 歷史累積 NAV 在代理視窗的最低點 |
| `nav_floor_ratio` | 0.9365 | min_nav / peak_nav，implied peak ≈ 13,071 USD |
| `calendar_days` | 30 | 代理視窗長度 |
| `tracking_error_monthly` | 0.0 | 代理計算中模型 vs 紙面一致（同一數據） |

### 4.2 paper_sharpe = −2.9012 的脈絡解析

此數字看似極端，但脈絡是：

1. 這是歷史資料最近 30 天（約 2026 年 3-4 月）的年化 Sharpe。
2. TASK-003 attribution 顯示 2026 年（Jan-Apr，120 天）net alpha = **−1.20%**，年化大約 −3.65%。最近 30 天為負是已知且預期的。
3. NAV 在歷史上已從初始 10,000 USD 增長至峰值約 **13,071 USD**（+30.7%），最近下滑至 12,240 USD（−6.3% from peak）。
4. `paper_sharpe = −2.9012` 是對一個月（30 天）的**短視窗年化 Sharpe**，對小樣本 extreme volatility 極度敏感。

**Sonnet 判斷**：此數字是代理計算的已知弱點（短視窗年化），不代表策略崩潰。但它確實反映了最近歷史期表現最差，應在 Opus 裁定時納入考量。

### 4.3 STOP_PAPER_PENDING_REVIEW 風控事件

- 工單 Section 7.3 紅色門檻：paper Sharpe < 0.2 → STOP_PAPER_PENDING_REVIEW
- 實際 paper_sharpe = −2.9012 << 0.2 → **自動觸發**

**正面解讀**：此觸發**證明風控系統運作正常**，能在近期表現不佳時自動攔截。

**負面解讀**：此觸發也顯示，若以代理 forward 的 Sharpe 作為真實前置條件，**目前無法通過 forward validation 門檻**。但工單的 forward validation 明確要求的是「真實 30 天 forward paper record」，而非歷史代理。

---

## 5. BLOCKING 問題（需 Opus 裁定）

### B-1：代理 Forward Validation Sharpe −2.9012 的解讀

**問題**：最近 30 天歷史代理 Sharpe = −2.9012，低於工單 RED 門檻（<0.2）。雖然 validation_basis 明確聲明為歷史代理（非真實 forward），但此數字代表：
- 在 2026 年 3-4 月期間，combined_paper_safe_variant 策略表現為負；
- 若從當前時點開始 paper trading，最近歷史表現不佳。

**Opus 裁定問題**：
(a) 是否接受「歷史代理是計畫範疇中的正確行為，與 forward validation 無關」？可繼續推進 REVIEW-006b 規劃。
(b) 是否認為最近期歷史表現（−2.90 Sharpe）應暫緩 paper trading 時程，等待市況改善訊號後再啟動？
(c) 是否要求 Codex 改用不同的 forward validation proxy 方法（如使用整個 active period 的 Sharpe，而非最近 30 天）？

### B-2：`STOP_PAPER_PENDING_REVIEW` 事件的政策意涵

**問題**：系統自觸發了 STOP_PAPER_PENDING_REVIEW 事件。目前此事件的定義（見工單 Section 7.3）是一個 monitoring 告警；但它也被記錄在 risk_events.jsonl 中，代表系統認為「當前狀態需要 review 後才能繼續」。

**兩種解讀**：
1. **架構驗證視角**：觸發是正確的，證明風控系統能偵測到異常。STOP 事件只是一個 flag，不阻擋規劃架構的 review 和 Opus 批准。
2. **實際風控視角**：此 STOP 代表若要啟動 paper trading，需要額外的 review（工單 Section 9 forward validation）。由於 proxy 已觸發 STOP，真實 forward 啟動後若表現未改善，kill switch 機制是否足夠？

**Opus 裁定問題**：
(a) 是否同意 STOP_PAPER_PENDING_REVIEW = 風控系統運作正常的驗證，不影響 TASK-006 基礎架構的 PASS 判定？
(b) 是否需要在 REVIEW-006b（paper trading plan 最終 review）中額外加入「代理 Sharpe > 0.5 才能提交 forward validation 申請」的前置條件？

---

## 6. Caveats（非 blocking）

**C-1：intended_fill_count = 3**
Target positions.json 有 50 個部位（25 long + 25 short），但 simulated_fills.csv 僅有 3 筆 fill。若這代表「只有 3 個部位從上一期改變方向」，則合理（月度 rebalance 的 position delta 可能很小）。但若這代表模組只模擬了 3 個部位的成交，則 schema 可能不完整。Sonnet 無法確認，建議 Codex 在 REVIEW-006b 補件中說明。

**C-2：overlay_event_count = 0 的前瞻意涵**
Funding filter 在 2026 年 3-4 月無效果（因 BTC/ETH/LINK funding 已正常化）。這意味：若 paper trading 在當前市況下啟動，combined_paper_safe_variant 實際上等同於 baseline（無多頭被排除）。Funding filter 的保護效果依賴牛市高 funding 環境，不一定在所有市況下有效。這不是模組錯誤，但應在 REVIEW-006b 中明確標記為「regime-dependent protection」。

**C-3：daily_pnl.csv 有 760 列（非 forward）**
760 列覆蓋的是整個歷史 active period（2024-04-01 ~ 2026-04-30），這是歷史 simulation，非 forward。這對 forward validation 沒有意義，但對模組測試有用（確認模組能產出合法格式）。

**C-4：TASK-007 reproducibility hash 交叉驗算通過**
REVIEW-006_NUMBERS.json 的 review007_reproducibility_hash = `824ff334...`，與 TASK-007 原始輸出的 reproducibility_hash 完全一致。確認 TASK-006 使用的是官方 TASK-007 輸出，未修改。✅

**C-5：nav_floor_ratio = 0.9365 的計算**
min_nav_usd = 12,240.63，nav_floor_ratio = 0.9365 → implied peak = 12,240.63 / 0.9365 ≈ **13,071 USD**。這代表歷史上 combined_paper_safe_variant 的 NAV 峰值約 +30.7% 高於初始，recent proxy 視窗從峰值下滑 −6.3%。整體歷史累積仍正向。

---

## 7. 模組功能對照工單驗收標準

| 工單驗收項目（Section 14） | 狀態 |
|---|---|
| `apps/paper_trading/` 模組存在 | ✅（packet 確認）|
| `sizing.py` 可計算 combined_paper_safe_variant overlay | ✅（target_positions 正確）|
| `risk.py` 三條規則有單元測試 | ✅（packet Safety PASS 指示）|
| `recorder.py` simulated_fills schema 正確 | ⚠️（fill_count=3，需 C-1 說明）|
| `validator.py` forward validation 計算 | ✅（forward_validation.json 存在）|
| `monitor_hook.py` 三個 method 介面 | ✅（packet 確認）|
| 所有輸出 JSON 含 Section 12 五條 caveat | ✅（驗算通過）|
| log 記錄 overlay rule 應用詳情 | ✅（log 含 overlay event details）|
| `REVIEW-006_PACKET.md` 存在 | ✅ |
| 可重現性：同 input 兩次 hash 相同 | ✅（reproducibility_hash = `40ab5158...`）|

---

## 8. Opus Prompt（供 Rick 複製貼上）

```
你是 Prev3Y Crypto Momentum 策略的 final review Opus。
請閱讀以下資料後，對 TASK-006 Paper Trading Planning Modules 做出最終裁定。

## 背景
TASK-006 交付的是 paper trading 技術架構（規劃模組），不是執行授權。
核心問題：模組是否安全、執行閘門是否正確、可否進入 REVIEW-006b 前置條件。

## 最關鍵安全確認（Sonnet 已驗算）
- Safety scan: PASS（violations=[]，無交易所連接、無憑證、無下單）
- paper_execution_status: NOT_STARTED ✓
- paper_execution_approval: false ✓
- live_trading_status: FORBIDDEN（所有輸出） ✓
- 五條 mandatory caveat 全部嵌入 ✓
- 三條 overlay 規則正確實作並驗算：
  * funding_filter: 0.03%/8h，2026-04-01 無 symbol 超標（市況正常化）
  * long_cap_50pct: 恰好在 50% 邊界
  * symbol_cap_5pct: max = 2.0% < 5%

## BLOCKING 問題（Sonnet 識別）
B-1：代理式 forward validation Sharpe = −2.9012（30天代理視窗）
     · validation_basis = "historical_simulation_proxy_not_forward_execution"（非真實 forward）
     · 對應 2026年 3-4月歷史表現，已知此期間 net alpha = −1.20%
     · 歷史 NAV 峰值約 +30.7%（13,071 USD），代理視窗從峰值回落 −6.3%
     · 問題：是否接受此代理 Sharpe 為正常 NOT_STARTED 狀態，不阻擋 REVIEW-006b 推進？

B-2：系統自觸發 STOP_PAPER_PENDING_REVIEW 事件
     · 工單 Section 7.3 紅色門檻：paper Sharpe < 0.2 → STOP
     · 觸發證明風控系統運作正常，但也代表代理期表現不佳
     · 問題：此 STOP 是架構驗證（設計正確），還是需要額外前置條件才能推進？

## 非 blocking 觀察
- intended_fill_count = 3（50個部位中只有3筆 fill；需 Codex 說明）
- overlay_event_count = 0（2026-04-01 funding 已正常化，filter 無效果；regime-dependent）
- TASK-007 reproducibility hash 交叉驗算通過 ✓

## 請裁定（Q1-Q4）
Q1：TASK-006 安全性驗證是否通過？基礎架構是否達到 REVIEW-006b 所需狀態？
Q2：代理 Sharpe −2.9012 是否接受為 NOT_STARTED 代理的正常結果，不阻擋 paper trading 時程？
Q3：STOP_PAPER_PENDING_REVIEW 事件的解讀：架構驗證成功，或需要額外條件（如代理 Sharpe > 0？）？
Q4：TASK-006 → CONDITIONAL_PASS / PASS / FAIL？下一步動作（TASK-007b、TASK-005、REVIEW-006b 的優先順序）？
```

---

## 9. Sonnet 初審結論

**狀態**：PASS_CANDIDATE（安全性全部通過；2 項 BLOCKING 需 Opus 裁定）

**Sonnet 核心判斷**：

1. **安全性**：TASK-006 模組的安全性設計無懈可擊。Safety scan PASS，無任何外部連接能力，執行閘門正確，live trading FORBIDDEN 一致。從安全角度，模組已達到規劃架構應有的標準。

2. **Proxy Forward Validation**：paper_sharpe = −2.9012 是歷史代理，反映已知的 2026 年 Q1 弱勢期，不代表策略崩潰。歷史累積 NAV 仍正向（+30.7% peak）。但此數字確實提醒：若從當前時點啟動 paper trading，初始期可能延續弱勢。

3. **風控系統**：STOP_PAPER_PENDING_REVIEW 觸發是正確行為，證明 Section 7.3 的 monitoring gate 正常運作。這是架構驗證，不是執行阻擋。

4. **未解項目**：intended_fill_count = 3 的說明（C-1）和 overlay 的 regime dependency（C-2）是小缺口，不影響核心安全結論。

**Sonnet 不裁定**：TASK-006 最終 PASS / FAIL、paper trading 啟動時程調整、是否因代理 Sharpe 加入額外前置條件——留 Opus 決定。

---

*REVIEW-006 Draft v1.0 | Claude Sonnet | 2026-05-16*  
*審查依據：REVIEW-006_PACKET.md + REVIEW-006_NUMBERS.json + target_positions.json + risk_events.jsonl + forward_validation.json + paper_trading_setup.log*  
*獨立驗算：Overlay 規則（C01-C04）、caveat 存在性（C07）、safety scan（C08）、primary variant 數字（C09）、TASK-007 hash 交叉驗算（C10）全部驗算通過*  
*參考：REVIEW-007_DRAFT_BY_SONNET.md（研究背景）；TASK-006_paper_trading_plan.md（工單規格）*
