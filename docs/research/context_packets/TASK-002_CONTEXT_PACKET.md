# TASK-002 Context Packet

建立日期：2026-05-15
維護者：Rick
用途：讓 Claude / Codex / ChatGPT 無需重讀完整歷史，即可掌握 TASK-002 目前狀態，直接參與決策或執行。

---

## 1. Current State（目前狀態）

| 任務 | 狀態 | 說明 |
|---|---|---|
| TASK-001 | ✅ DONE | 基礎回測框架建立完成（run008 為 baseline） |
| TASK-002a | ✅ DONE | funding rate 資料完整性驗證完成 |
| TASK-002 v2 工單 | ✅ 已落地 | 工單已更新至 v2，含 per-interval funding 實作規格 |
| TASK-002 主體 | ⏳ 待啟動 | 目前等待 readiness check 通過，尚未交給 Codex 執行 |

**目前卡點：** readiness check 尚未正式執行，pending Rick 確認可以開始。

---

## 2. Canonical Inputs（標準輸入檔案）

下列為 TASK-002 實作時的唯一合法輸入來源，Codex 不得自行替換或使用其他版本：

| 用途 | 路徑 |
|---|---|
| run008 基礎回測（baseline / positions / stats） | `outputs/backtests/run008/`（含 baseline CSV、positions CSV、stats CSV） |
| Funding rate 資料 | `data/crypto/funding_rates.parquet` |
| 交易手續費設定 | `data/crypto/fees.yaml` |
| Cost stress 參數設定 | `configs/cost_stress.yaml` |

> ⚠️ 以上路徑為規劃路徑，由 Codex 在執行任務時依工單規格建立或確認存在。若路徑不存在，應停下來回報，不可自行建立替代版本。

---

## 3. Key Facts（已確認關鍵數據）

下列數據均來自 TASK-001 / TASK-002a 的審查結果，已經 Claude 確認，可直接引用。

### 3.1 績效指標

| 指標 | 數值 | 說明 |
|---|---|---|
| Active IR vs cash | **+0.93** | 策略相對現金有顯著 alpha |
| Active IR vs BTC | **-0.02** | 策略幾乎無法超越 BTC，無 BTC alpha |
| Active IR vs equal-weight | **+0.72** | 相對等權組合有正向超額報酬 |

### 3.2 Funding Rate 覆蓋率

| 指標 | 數值 |
|---|---|
| Funding active position coverage | **98.84%** |
| Funding active PIT coverage | **97.56%** |
| `is_proxy` 欄位 | 全部為 `False`（無代理填補資料） |

### 3.3 Funding Interval 分布

| Interval | 筆數 |
|---|---|
| 1h | 1 |
| 4h | 145 |
| 8h | 127 |

> 此分布確認 funding 資料混有 1h / 4h / 8h 三種結算週期，實作時**必須使用 per-interval 換算**，不可統一硬寫 8h。

---

## 4. Caveats（已知限制與風險）

在解讀上述數據或進行 TASK-002 實作前，必須了解以下已知限制：

**樣本期間**
- Active sample 僅 760 天，樣本相對偏短，結果的統計穩健性有限。

**Alpha 結構**
- 策略對 BTC 無顯著 alpha（Active IR vs BTC = −0.02），alpha 主要來自 alt coin 組合配置，而非 BTC 方向性押注。

**Funding gap 幣種**
- 下列幣種的 funding rate 資料存在缺口，coverage 分析時已識別，但尚未補全：
  `XTZ` / `FLOW` / `LPT` / `AXS` / `RVN` / `INJ` / `CTC`
- 這些幣種的 funding cost 估算結果可信度較低，TASK-002 報告中需單獨標記。

**Funding Outliers**
- 存在極端值：`abs(funding rate) >= 0.01`，最大絕對值達 **0.05**。
- 實作 cost stress 時，outlier 處理方式需依 `configs/cost_stress.yaml` 定義，不可由 Codex 自行決定截斷門檻。

**實作硬性限制**
- TASK-002 **必須使用 per-interval funding 換算**（依各筆資料的 interval 欄位計算），不可硬寫固定的 8h 基準。

---

## 5. Current Decision Needed（目前待決策事項）

以下兩個決策需要 Rick 確認，才能推進 TASK-002：

### Decision A：是否啟動 TASK-002 Readiness Check？

**背景：** TASK-002 v2 工單已落地，canonical inputs 已定義，key facts 已確認。
**問題：** 是否授權 Claude (Sonnet) 執行 readiness check，驗證所有前置條件滿足？

- ☐ Yes，開始 readiness check
- ☐ No，待補充 ___________

### Decision B：若 Readiness Check PASS，是否交給 Codex 實作？

**背景：** Readiness check PASS 代表輸入檔案齊備、工單無歧義、禁改範圍清楚。
**問題：** PASS 後是否直接授權 Codex 執行 cost stress 實作，或需先經 Rick 再次確認？

- ☐ PASS 後直接授權 Codex
- ☐ PASS 後仍需 Rick 再確認才授權

---

## 6. Model Routing（模型分工）

依 `AI_WORKFLOW.md` 第 3 節的模型分工規則：

| 工作項目 | 指定模型 | 說明 |
|---|---|---|
| TASK-002 readiness check | **Claude Sonnet** | 屬於 schema / readiness check，Sonnet 全權處理 |
| REVIEW-002 final review | **Claude Opus** | 屬於 major task final review，需升級至 Opus |

每次 review 輸出必須標註：

```
Suggested model:              Sonnet / Opus
Escalation reason:            <若建議 Opus，說明原因；否則填 N/A>
Opus final decision required: Yes / No
```

---

## 7. 嚴格禁止事項（本 Context Packet 有效期間）

- ❌ 不修改任何策略程式（`strategies/`、`backtest/`、`data/` 等核心目錄）
- ❌ 不執行 TASK-002 cost stress 或任何回測
- ❌ 不替換 canonical inputs（不得使用 run008 以外的基礎回測）
- ❌ Codex 未獲授權前，不得自行開始實作

---

*本 Context Packet 由 Claude Sonnet 依 AI_WORKFLOW.md 規範建立。下一次更新時機：Readiness Check 完成後，或 Decision A / B 有任一確認結果。*
