# TASK-006 — Paper Trading Plan（規劃工單，非執行授權）

- **狀態**：TODO
- **Owner**：Codex（實作 paper trading 基礎架構與監控整合）
- **預估**：M（3–5 天）
- **依賴**：
  - TASK-001 ✓ DONE（run008 baseline）
  - TASK-002 ✓ DONE（cost stress，realistic_combo pass）
  - TASK-003 ✓ DONE（attribution，short-driven alpha 確認）
  - TASK-007 ✓ DONE（Opus REVIEW-007 CONDITIONAL_PASS）
  - TASK-007b **必須完成** 後才可執行 paper（weight cap + redistribution）
  - TASK-005（VPS monitor）**必須上線** 後才可執行 paper
- **工單版本**：v1.0（2026-05-16，由 Claude Sonnet 撰寫）
- **觸發原因**：
  - Opus REVIEW-002 PASS（2026-05-15）開放規劃
  - Opus REVIEW-003 CONDITIONAL_PASS 新增 3 條 mandatory caveat
  - Opus REVIEW-007 CONDITIONAL_PASS 確認 primary spec = `combined_paper_safe_variant`

---

## ⚠️ 重要聲明（必讀）

**本工單是「規劃與基礎架構建設」，不是「paper trading 執行授權」。**

- Codex 的工作是：建立 paper trading 所需的技術架構（訂單記錄系統、監控 hook、position sizing 計算器）。
- **不得**在本工單完成前啟動任何 paper trading。
- Paper trading 執行需滿足 Section 4 的所有前置條件，且需要 Opus 另一輪 final review。
- Live trading 目前**絕對禁止**，無論任何情況。

---

## 1. 任務一句話

基於 Opus REVIEW-007 確認的 `combined_paper_safe_variant` 規格，建立 Bybit perp paper trading 的技術基礎架構（position sizing 計算器、訂單記錄系統、風控規則引擎、監控整合），**不執行任何訂單**，等 TASK-007b 完成 + 30 天 forward validation + Opus 最終 review 後才可啟動執行。

---

## 2. 任務目的

### 研究路徑總結

| 任務 | 關鍵結論 |
|---|---|
| TASK-001 | run008：active Sharpe 0.8918, max DD −19.64%，樣本 760 天 |
| TASK-002 | Realistic cost overlay PASS；slippage > fee > funding，cost drag 1.05% |
| TASK-003 | Long-side net −5.01%，short-driven alpha +33.56%，top5=95.56%（DOT=25.45%）|
| TASK-007 | `high_funding_cost_filter` Pareto-dominant（Sharpe 0.9586）；`combined_paper_safe_variant` 唯一 single_conc < 25% |

### 本工單要解決的問題

1. **Position sizing**：在 5% 單一 symbol cap 下，如何把研究口徑（每日 weight）轉換為 demo 帳戶的實際倉位大小？
2. **Rule engine**：三條 mandatory caveat（5% cap / 50% long cap / funding filter）如何在每個 rebalance 時點被機械性執行？
3. **監控整合**：與 TASK-005 VPS monitor 的 kill switch 如何串接？
4. **記錄系統**：paper trading 的每日 PnL、每次 rebalance 的訂單記錄、與策略預測的偏差，如何被追蹤？
5. **Forward validation**：30 天 forward-validated 的達標條件如何被自動化評估？

---

## 3. 範圍邊界

### ✅ Do（Codex 被允許做）

- 建立 paper trading 計算引擎（`apps/paper_trading/`），輸入為 run008 positions + variant overlay 規則，輸出為每日目標倉位。
- 建立訂單記錄系統（僅記錄、不送單）：模擬以 next-open 成交，記錄預期 fill、預期成本、actual（模擬）fill。
- 實作 position sizing 計算器（Section 6 規格）。
- 實作風控規則引擎（Section 7 三條 mandatory caveat + kill switch 邏輯）。
- 建立 TASK-005 VPS monitor 的 hook 介面（定義協議，不需要 TASK-005 先完成）。
- 建立每日 forward validation 報告產出器（比對策略預測 vs 模擬成交）。
- 為 Codex 完成後的 Opus review 產出 review packet（`docs/research/review_packets/REVIEW-006_PACKET.md`）。

### ❌ Don't（絕對禁止）

- **不可送出任何訂單**（paper 或 live）。
- **不可連接 Bybit API 的下單 endpoint**（即使是 demo 帳戶）。
- **不可修改策略訊號、ranking 邏輯**。
- **不可修改 run008、TASK-002、TASK-003、TASK-007 的任何輸出**。
- **不可自行宣稱 paper trading 可以執行**。
- **不可修改 data/ 目錄下任何檔案**。
- **不可在 Opus REVIEW-006 通過前 merge 回 main**。
- **不可以任何形式啟動 live trading**。

---

## 4. Paper Trading 執行前必要條件（Codex 本工單完成後仍需等待）

Paper trading **實際執行** 需滿足以下所有條件，**缺一不可**：

| 條件 | 狀態 | 說明 |
|---|---|---|
| TASK-006 基礎架構完成 + Opus REVIEW-006 PASS | ❌ 待完成 | 本工單 |
| TASK-007b Weight Cap 完成 + PASS | ❌ 待完成 | paper 執行前必須完成；見 Section 8 |
| TASK-005 VPS Monitor 上線 | ❌ 待完成 | kill switch 必須就位 |
| Opus paper trading plan 最終 review（REVIEW-006b） | ❌ 待完成 | 在以上三項完成後觸發 |
| 30 天 forward validation 合格 | ❌ 待完成 | 見 Section 9 |

---

## 5. 研究依據（Primary / Secondary 規格）

### Primary 規格：`combined_paper_safe_variant`

Opus REVIEW-007 確認此為 paper trading primary spec，同時滿足所有三條 mandatory caveat：

| 指標 | 數值 | 說明 |
|---|---|---|
| Sharpe (active) | 0.8037 | 健康水準 |
| Max DD | −20.27% | 略高於 baseline −19.64%（可接受） |
| Net Alpha | 24.99% | Alpha retention 87.6% |
| Long Net | +4.21% | 正值！過濾高 funding 後多頭轉正 |
| Short Net | +20.78% | cap 後略降 |
| Single Conc. | 19.73% | **< 25% 門檻**（唯一達標變體） |
| Top5 Conc. | 91.92% | 仍高，但 overlay 已盡力 |
| Max DD / Baseline DD | 1.032x | 非常接近 baseline |

**構成規則**（此三規則同時施加即為此 variant）：
1. 多頭中最近 30 天平均 funding rate > 0.03%/8h 的 symbol → 完全排除
2. 多頭部位總量不超過 gross exposure 50%（超過則等比例縮減 long weights）
3. 單一 symbol |weight| 占 gross exposure 上限 5%（超過則截斷，無 redistribution）

### Secondary 規格：`high_funding_cost_filter`（Sensitivity）

| 指標 | 數值 | 說明 |
|---|---|---|
| Sharpe (active) | **0.9586** | 最高，超越 baseline |
| Max DD | −20.27% | 同 primary |
| Net Alpha | 31.27% | Alpha retention 109.6% |
| Long Net | −2.29% | 仍負，但改善 +2.72% |
| Single Conc. | 23.23% | < 25%（勉強達標） |
| Top5 Conc. | 87.22% | 最佳（仍 > 60% 結構問題）|
| Funding Cost | ~0 | 高 funding 多頭全排除 |

**構成規則**：僅施加 Rule 1（funding filter），不施加 Rule 2 / Rule 3。

### Tertiary 規格（Shadow-Track）：`A_roll12_share20_exclude`

> **加入時間**：2026-05-17，Opus REVIEW-008 CONDITIONAL_PASS 後。
> **用途**：shadow-track；不取代 primary；不列入 paper execution 前置條件。

Opus REVIEW-008 確認此為 TASK-008 推薦 variant，Pareto-dominant vs baseline，列為 TASK-006 tertiary / 平行觀察規格，供後續研究參考：

| 指標 | 數值 | 說明 |
|---|---|---|
| Sharpe (active) | **0.9636** | 高於 baseline（0.8918）與 secondary（0.9586） |
| Max DD | 待 30-day forward record 確認 | — |
| Net Alpha | 31.00% | Alpha retention **108.65%**（超越 baseline） |
| Single Conc. | **23.43%** | < 25% ✅ |
| Top5 Conc. | 87.95% | W-1 observation；Opus 裁定可接受上限 ≤ 90% |
| Cost Impact | −9.73 bps | 成本降低 |
| Turnover | 0.964× | 略低於 baseline |

**構成規則（alpha-space 介入，非 overlay）**：
- 在 `build_prev3y_targets()` post-selection，施加 rolling 12-period alpha-contribution cap（max alpha share 20%）
- 超過 20% 貢獻度上限的 symbol → exclude（不納入本期 target）
- 實作位置：`src/variants/task008.py` — `apply_alpha_contribution_cap()`

**使用限制**：
- 本規格**不替代** `combined_paper_safe_variant` 作為 paper trading primary spec
- 30-day forward record 仍以 `combined_paper_safe_variant` 為準
- 若 Rick 決定以此為 paper 正式規格，需另開 TASK-009 + Opus review

---

## 6. Position Sizing 計算規格

### 6.1 Demo 帳戶基本設定

```yaml
paper_trading:
  venue: bybit_perp
  account_type: demo  # Bybit testnet 或 unified demo account
  initial_nav: 10000  # USD 10,000 作為第一階段；可升至 50,000
  currency: USDT
  leverage_max: 1.0   # 不使用槓桿；weight 直接對應 USDT 金額
  order_type: market  # 以 next-open 模擬 fill（與 run008 return dating 一致）
  rebalance_freq: monthly  # 與 run008 一致
```

### 6.2 每日目標倉位計算流程

```
Step 1: 讀取最新 run008 positions.parquet 的對應日期 weights
Step 2: 施加 combined_paper_safe_variant 三條 overlay 規則：
        - Rule 1: 排除 avg_funding_rate_30d > 0.0003（0.03%/8h）的多頭 symbol
        - Rule 2: 若 sum(long_weights) > 0.5 * sum(abs(all_weights))
                  → 等比例縮減所有 long weights 至合規水準
        - Rule 3: 對每個 symbol，若 |weight| > 0.05 * gross_exposure
                  → 截斷至 0.05 * gross_exposure（無 redistribution）
Step 3: 重新正規化 weights（確保 sum(abs(weight)) ≤ 1.0）
Step 4: 計算目標持倉（USD）= weight × NAV
Step 5: 四捨五入至合理最小合約單位
Step 6: 輸出 target_positions.json
```

### 6.3 Position Sizing 輸出格式

```json
{
  "date": "YYYY-MM-DD",
  "nav_usd": 10000,
  "variant": "combined_paper_safe_variant",
  "overlay_rules_applied": ["funding_filter_0.03pct_8h", "long_cap_50pct", "symbol_cap_5pct"],
  "excluded_symbols": ["BTCUSDT", "ETHUSDT"],
  "positions": [
    {
      "symbol": "BYBIT:DOTUSDT.P",
      "weight": -0.048,
      "direction": "short",
      "usd_notional": -480,
      "funding_rate_30d_avg": 0.000012,
      "rule_applied": null
    }
  ],
  "portfolio_summary": {
    "gross_exposure_pct": 0.88,
    "long_exposure_pct": 0.12,
    "short_exposure_pct": 0.76,
    "n_longs": 8,
    "n_shorts": 22,
    "max_single_symbol_pct": 0.048
  },
  "analysis_basis": "planning only, not a trading decision",
  "disclaimer": "This is a paper trading simulation. No actual orders will be placed."
}
```

---

## 7. 風控規則引擎

### 7.1 三條 Mandatory Caveat（Opus REVIEW-003 + REVIEW-007 指定）

| 規則 | 觸發條件 | 動作 |
|---|---|---|
| `funding_filter` | 多頭 symbol 近 30 天平均 funding rate（8h 等效）> 0.03% | 該 symbol 本次 rebalance 多頭 weight 設為 0 |
| `long_cap_50pct` | sum(long_weights) > 0.5 × gross_exposure | 等比例縮減所有 long weights 至 50% × gross_exposure |
| `symbol_cap_5pct` | 任一 symbol |weight| > 0.05 × gross_exposure | 截斷至 0.05 × gross_exposure（不 redistribute） |

### 7.2 Kill Switch（硬停損規則）

```yaml
kill_switch:
  # 絕對停損：觸發後立即平倉並停止 paper trading
  absolute_max_dd: -0.30      # paper portfolio 從 peak 下跌 30%（1.5x baseline max DD）
  
  # 連續虧損停損：連續 5 個 rebalance cycle 均虧損
  consecutive_losing_cycles: 5
  
  # NAV 跌破下限
  min_nav_usd: 7000           # 初始 10,000 的 70%
  
  # 動作：觸發後自動記錄 KILL_SWITCH_TRIGGERED 事件，平所有倉位，發送告警
  action: "close_all_positions_and_halt"
  alert_channels: ["monitor_hook"]  # 與 TASK-005 VPS monitor 串接
```

### 7.3 月度 Paper Review 門檻

每月 rebalance 後自動計算以下指標，若觸發則生成 `MONTHLY_REVIEW_REQUIRED` 事件：

| 指標 | 黃色（WARNING） | 紅色（STOP_PAPER_PENDING_REVIEW） |
|---|---|---|
| 累積 paper Sharpe（active） | < 0.5 | < 0.2 |
| 累積 max DD | > 25% | > 30% |
| Tracking error（paper vs model） | > 5% monthly | > 10% monthly |
| Cost overrun（實際 vs 模擬） | > 50% overage | > 100% overage |

---

## 8. 技術架構（Codex 需實作）

### 8.1 模組結構

```
apps/paper_trading/
├── __init__.py
├── config.py              # paper trading 設定（demo acc / NAV / rebalance freq）
├── overlay.py             # combined_paper_safe_variant overlay 三規則
├── sizing.py              # position sizing 計算器（Section 6.2）
├── risk.py                # 風控規則引擎（Section 7.1 / 7.2）
├── recorder.py            # 訂單記錄（不送單，僅記錄目標倉位 + 模擬 fill）
├── validator.py           # forward validation 評估器（Section 9）
├── monitor_hook.py        # TASK-005 VPS monitor 介面（協議定義）
├── report.py              # 每日 / 每月報告產出
└── README.md
```

### 8.2 輸出檔案

| 路徑 | 格式 | 說明 |
|---|---|---|
| `outputs/paper_trading/prev3y_crypto/<YYYYMMDD>_target_positions.json` | JSON | 每次 rebalance 的目標倉位（Section 6.3 格式）|
| `outputs/paper_trading/prev3y_crypto/<YYYYMMDD>_simulated_fills.csv` | CSV | 模擬成交記錄（next-open fill）|
| `outputs/paper_trading/prev3y_crypto/<YYYYMMDD>_daily_pnl.csv` | CSV | 每日 P&L 追蹤（paper vs model）|
| `outputs/paper_trading/prev3y_crypto/<YYYYMMDD>_monthly_review.json` | JSON | 每月 review 數字（Section 7.3 指標）|
| `outputs/paper_trading/prev3y_crypto/<YYYYMMDD>_risk_events.jsonl` | JSONL | 風控事件記錄（kill switch / rule triggers）|
| `outputs/paper_trading/prev3y_crypto/<YYYYMMDD>_forward_validation.json` | JSON | forward validation 達標評估（Section 9）|
| `docs/research/review_packets/REVIEW-006_PACKET.md` | Markdown | Codex 完成後的 review packet |
| `outputs/logs/prev3y_crypto/<YYYYMMDD>_paper_trading_setup.log` | log | 設定驗證、規則應用記錄 |

### 8.3 `simulated_fills.csv` Schema

| 欄位 | 型別 | 說明 |
|---|---|---|
| `date` | date | 成交日期（positions.date + 1 day）|
| `symbol` | str | BYBIT:XXXUSDT.P |
| `direction` | str | long / short |
| `target_weight` | float | overlay 後目標 weight |
| `prev_weight` | float | 前一期 weight |
| `weight_delta` | float | 本次交易量 |
| `usd_notional` | float | 目標倉位 USD |
| `simulated_fill_price` | float | 下一個 open 價格（模擬 fill）|
| `simulated_fee_usd` | float | 模擬手續費（taker 5.5 bps × turnover）|
| `simulated_slippage_usd` | float | 模擬滑點（基於 TASK-002 realistic_combo）|
| `simulated_funding_usd` | float | 模擬 funding（基於 funding_rates.parquet）|
| `overlay_rules_applied` | str | 逗號分隔的觸發規則名稱（如有）|
| `excluded_reason` | str | 若 weight = 0 且 original ≠ 0，說明原因 |

---

## 9. Forward Validation 規格

### 9.1 達標條件（30 天 minimum）

Paper trading 執行滿 30 個 calendar days 後，自動評估以下指標，**全部通過**才可由 Codex 觸發 `FORWARD_VALIDATION_PASS` 事件：

| 指標 | 通過門檻 | 說明 |
|---|---|---|
| 實際天數 | ≥ 30 calendar days | 最少一個月 |
| Paper Sharpe（active） | ≥ 0.3 | 研究口徑 0.8037，forward 容許大幅衰減 |
| Paper max DD | ≤ −35% | 不超過 kill switch 閾值的 85% |
| Model tracking error | ≤ 15% （monthly） | Paper 與 model 預測的月度 correlation |
| Zero fatal errors | 0 件 CRITICAL 事件 | kill switch 未觸發、無資料缺失 |
| NAV 剩餘 | ≥ 75% 初始 | 即 ≥ USD 7,500 |

### 9.2 Forward Validation 後的步驟

1. Codex 產出 `REVIEW-006_PACKET.md` 更新（含 forward validation 結果）。
2. Claude Sonnet 初審（REVIEW-006b draft）。
3. Opus final review（REVIEW-006b）。
4. **Opus PASS 後 + Rick 明確授權** → 才可考慮升級至 live trading。

---

## 10. Reporting Cadence

| 頻率 | 報告內容 | 格式 |
|---|---|---|
| 每日 | Daily PnL + NAV 更新 + 活躍 risk 事件 | `daily_pnl.csv` 新增一列 |
| 每週 | 7 天滾動 Sharpe + max DD + top contributors | Markdown summary（可選）|
| 每月 | 完整 monthly review（Section 7.3 指標）+ rule application stats | `monthly_review.json` |
| 每次 rebalance | Target positions + overlay 規則應用記錄 | `target_positions.json` + `simulated_fills.csv` |
| 每次 risk event | 即時記錄 kill switch / warning 觸發 | `risk_events.jsonl` 追加一行 |

---

## 11. 監控整合（TASK-005 hook）

與 TASK-005 VPS monitor 的介面協議（Codex 定義 API，TASK-005 實作）：

```python
# apps/paper_trading/monitor_hook.py 定義的介面
class PaperTradingMonitorHook:
    def push_heartbeat(self, timestamp, nav_usd, status):
        """每日推送心跳 + NAV 更新"""
        pass
    
    def push_risk_event(self, event_type, severity, details):
        """推送風控事件（WARNING / CRITICAL / KILL_SWITCH）"""
        pass
    
    def push_rebalance_summary(self, date, n_longs, n_shorts, 
                                gross_exposure, net_exposure):
        """每次 rebalance 後推送持倉摘要"""
        pass
```

**接口優先於實作**：本工單交付介面定義；TASK-005 之後串接具體 push 目標（Telegram / Discord / Email）。

---

## 12. 三條 Mandatory Caveat（必須嵌入所有輸出文件）

以下 caveat 必須出現在每一份 `target_positions.json` 和 `monthly_review.json` 的 header 中：

```json
{
  "mandatory_caveats": {
    "caveat_1_sample_size": "Strategy backtest covers 760 active days (2024-04-01 to 2026-04-30) only. Forward performance may differ materially.",
    "caveat_2_btc_ir": "IR vs BTC = -0.0017 (high_funding_cost_filter). Strategy does not beat buy-and-hold BTC in active period. Paper trading does not imply BTC outperformance.",
    "caveat_3_concentration": "Top 5 symbols = 87-95% of net alpha. Paper trading uses combined_paper_safe_variant (single_conc 19.73%) but structural concentration risk persists. TASK-008 strategy-layer cap is the permanent fix.",
    "caveat_4_long_side": "Long-side net alpha is structurally negative at baseline (-5.01%). combined_paper_safe_variant turns long net positive (+4.21%) but this has NOT been validated forward.",
    "caveat_5_forward_only": "All numbers in this file are based on historical simulation. Paper trading simulation does not constitute approval for live trading.",
    "live_trading_status": "FORBIDDEN"
  }
}
```

---

## 13. 與 TASK-007b / TASK-008 的關係

### TASK-007b（Weight Cap + Redistribution，執行前必須完成）

TASK-006 目前使用的 `combined_paper_safe_variant` 的 Rule 3 是「截斷不 redistribute」（`cap_no_redistribution`），這與工單原規格（等比例補回同方向）不同。TASK-007b 將補齊 weight-based cap + redistribution 設計（cap=20%/15%/10%）。

- 若 TASK-007b 結果顯示 redistribution 版的 combined_paper_safe_variant 優於當前版本，Codex 需在 paper trading 正式啟動前更新 `overlay.py` 的 Rule 3。
- 若差異 < 0.5% Sharpe，可視為等效，無需重寫。

### TASK-008（策略層 Weight Cap，長期方案）

TASK-008 完成後，run008 的 per-symbol weight cap 將在策略層面實現（ranking / position sizing 層），使集中度問題從根本解決。**TASK-008 完成後產出的新 baseline 是 paper trading 的正式上線版本**。

TASK-006 是 TASK-008 期間的過渡版本，使用 overlay 來近似等效效果。

---

## 14. 驗收標準

- [ ] `apps/paper_trading/` 模組存在，結構符合 Section 8.1。
- [ ] `sizing.py` 可對任意輸入日期的 run008 positions 正確計算 combined_paper_safe_variant overlay 結果（Section 6.2 五個 Step 全部實作）。
- [ ] `risk.py` 的三條 mandatory caveat 可用單元測試驗證（至少 3 個 fixture：BTC 高 funding 被排除、long > 50% 被縮減、DOT > 5% 被截斷）。
- [ ] `recorder.py` 的 `simulated_fills.csv` schema 符合 Section 8.3。
- [ ] `validator.py` 的 forward validation 指標計算可由 CSV 重現（±1e-6）。
- [ ] `monitor_hook.py` 的三個 method 介面定義完整（即使 stub 實作，需有 docstring + type hint）。
- [ ] 所有輸出 JSON 的 header 包含 Section 12 的五條 caveat。
- [ ] Log 記錄每次 overlay rule 應用的詳情（哪個 symbol 被排除 / 截斷，以及原因）。
- [ ] Review packet `REVIEW-006_PACKET.md` 存在且包含所有 Section 的數字摘要。
- [ ] 可重現性：同 input 跑兩次，`target_positions.json` 的 hash 相同。

---

## 15. Fail / Warning Gates

### Warning Gates（標記 WARNING，不停止）

| Gate | 觸發條件 |
|---|---|
| `combined_variant_no_positions` | overlay 後某個 rebalance 日的多頭部位數 = 0 |
| `funding_filter_excludes_over_30pct` | funding filter 排除超過 30% 的原始多頭 weight |
| `long_cap_fires_every_month` | 連續 3 個月 long_cap_50pct 均觸發 |
| `tracker_error_above_5pct` | 30 天 paper vs model tracking error > 5% |

### Fail Gates（觸發則輸出不完整，停止）

| Gate | 觸發條件 |
|---|---|
| `no_run008_positions` | `run008_positions.parquet` 不存在或 schema 不符 |
| `no_funding_rates` | `funding_rates.parquet` 不存在（Rule 1 無法執行）|
| `sizing_error` | Position sizing 計算後有任何 symbol `|weight| > 0.05 + 1e-6`（Rule 3 失效）|
| `schema_error` | 任一輸出檔 schema 缺欄或型別錯誤 |

---

## 16. 禁止修改範圍

- **run008 四件套**：read-only
- **20260515 TASK-002 outputs**：read-only
- **20260515 TASK-003 attribution outputs**：read-only
- **TASK-007 variant outputs**：read-only
- **`data/` 目錄下所有 raw 檔**：read-only
- **策略程式**（`src/` 下所有 `.py`）：不可修改
- **`configs/` 下任何 yaml**：不可修改
- **任何 baseline runner / cost stress runner**：不可呼叫
- **Bybit API 下單 endpoint**：不可連接

---

## 17. 完成後回報格式

```
TASK-006 Paper Trading Plan — Codex 交付摘要（YYYY-MM-DD）

=== 模組交付 ===
apps/paper_trading/: [列出已建立的檔案]

=== Position Sizing 驗證 ===
測試日期: [YYYY-MM-DD]
原始 run008 n_longs: [N]
overlay 後 n_longs: [N]（-[M] 因 funding_filter）
overlay 後 n_shorts: [N]
long_exposure_pct: [X%]（Rule 2 觸發：是/否）
max_single_symbol_pct: [X%]（Rule 3 觸發：是/否）

=== 風控規則驗證 ===
funding_filter 測試：BTC 排除 = [是/否]
long_cap_50pct 測試：PASS / FAIL
symbol_cap_5pct 測試：PASS / FAIL

=== 單元測試 ===
[測試結果]

=== Review Packet ===
docs/research/review_packets/REVIEW-006_PACKET.md: [存在/不存在]

=== Fail Gates ===
no_run008_positions: PASS / FAIL
no_funding_rates: PASS / FAIL
sizing_error: PASS / FAIL
schema_error: PASS / FAIL

=== 可重現性 ===
reproducibility_hash: [hash]

=== 遇到的問題 / 異常 ===
（若有，逐條列出）

=== 提醒 ===
本工單完成後不代表 paper trading 執行授權。
後續需要：TASK-007b PASS + TASK-005 上線 + REVIEW-006b Opus PASS
```

---

## 18. NOTE 區

### NOTE-1：TASK-006 不轉 DONE
Codex 完成基礎架構後，狀態改為 `REVIEW`，等 Sonnet 初審（REVIEW-006）後，再等 Opus final decision（REVIEW-006b）。不可自行轉 DONE。

### NOTE-2：Paper Trading ≠ Live Trading
本工單建立的是 paper trading 模擬框架，所有「訂單」都是記錄，不是實際交易。從 paper 升級至 live trading 需要：(a) 30+ 天 forward validated, (b) TASK-007b PASS, (c) TASK-008 策略層 cap 實作, (d) Opus 額外一輪 live trading review, (e) Rick 明確書面授權。

### NOTE-3：Combined Variant Long Net 轉正的解讀
`combined_paper_safe_variant` 在 TASK-007 歷史回測中 long net = +4.21%（正），這是在 overlay 後剩餘多頭部位（低 funding 多頭）的淨 alpha。但此數字來自 **歷史回測**，不代表 forward 多頭必然為正。forward validation 期間應監控 long net contribution 是否維持正值。

### NOTE-4：Funding Rate 資料更新需求
`funding_rates.parquet` 目前覆蓋至 2026-04-30。Rule 1（funding_filter）要求最近 30 天的 funding rate 均值。若 paper trading 在 2026 年 5 月之後執行，需要先更新 `funding_rates.parquet`（TASK-002a 的 Phase 2 fetch 流程）。此為執行前的額外前置條件。

### NOTE-5：與 ChatGPT 顧問的協作
如果 Rick 希望讓 ChatGPT 顧問對 paper trading plan 提供意見，可以把本工單（Section 5-11）的關鍵內容放入 `docs/research/advisor/CHATGPT_ADVISOR_CONTEXT.md` 供 ChatGPT 閱讀。Claude 不會主動修改 advisor context，由 Rick 決定時機。

### NOTE-6：TASK-003 Codex 必補項目（未在 TASK-006 範圍內）
Opus REVIEW-003 要求補三件事（concentration 雙分母輸出、`long_side_drag` gate、attribution review packet 自動化），這些不在 TASK-006 範圍內，但應在 TASK-006 完成後的下一版 attribution 更新中處理。

---

*工單版本 v1.0 | 撰寫：Claude Sonnet | 日期：2026-05-16*  
*觸發依據：NEXT_ACTION.md Status=READY；Opus REVIEW-007 CONDITIONAL_PASS（2026-05-16）*  
*參考：CODEX_TASK_QUEUE.md TASK-006/007 節；REVIEW-007_DRAFT_BY_SONNET.md Section 2.5；REVIEW-003_DRAFT_BY_SONNET.md*
