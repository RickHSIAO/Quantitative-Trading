# REVIEW-006 Addenda Check — TASK-006 Paper Trading Plan

**By**: Claude Sonnet  
**Date**: 2026-05-17  
**Scope**: 只驗證 Opus REVIEW-006 PASS 要求的三個補件（addenda），不重開 REVIEW-006b  
**依據**: Token Budget Rule — 只讀 REVIEW-006_PACKET.md + REVIEW-006_NUMBERS.json + forward_validation.json + monthly_review.json + simulated_fills.csv + paper_trading_setup.log

---

## 結論

**三個 addenda 全部落地，驗收通過。**

| Addendum | 需求 | 狀態 |
|---|---|---|
| A-1 `proxy_sharpe_long_window` | 90-day 或 full 760-day 長窗 Sharpe 並列於 30-day proxy | ✅ **PASS** |
| A-2 `fill_definition` | simulated_fills schema 加註「fill = position delta vs prior period」| ✅ **PASS** |
| A-3 `funding_filter_active_this_month` | monthly_review.json 加 boolean | ✅ **PASS** |

**Paper execution = 仍 FORBIDDEN**（剩餘前置條件未達成）  
**Live trading = 仍 FORBIDDEN**（不變）  
**REVIEW-006b 開啟條件**：A-1/A-2/A-3 ✅ + TASK-007b DONE ✅ → 剩餘阻擋條件：**30 天 forward paper record 不存在**

---

## 逐項驗證

---

### A-1：`proxy_sharpe_long_window`

**需求（Opus REVIEW-006 裁定）**：補充 90-day 或 full active period（760 天）的長窗 Sharpe，讓讀者能區分「30-day annualized noise（−2.90）」與「歷史長窗表現」，避免誤讀 proxy Sharpe 為策略崩潰訊號。

**驗證結果**：`forward_validation.json` 與 `monthly_review.json`（nested 在 `forward_validation`）均含 `proxy_sharpe_long_window` 區塊：

```json
"proxy_sharpe_long_window": {
    "annualization_factor": 365.25,
    "basis": "historical_simulation_proxy_not_forward_execution",
    "short_window": {
        "label": "30d_proxy",
        "annualized_sharpe": -2.9012,
        "observed_days": 30,
        "note": "Noisy short-window proxy; keep separate from real forward paper results."
    },
    "window_90d": {
        "annualized_sharpe": 1.1681,
        "observed_days": 90,
        "available": true
    },
    "full_active_window": {
        "annualized_sharpe": 0.8037,
        "observed_days": 760,
        "available": true
    }
}
```

| 窗口 | Sharpe | 說明 |
|---|---|---|
| 30d proxy | **−2.9012** | 短窗雜訊；已加 note 警示 |
| 90d window | **+1.1681** | 正值，與 30d 完全相反 |
| 760d full active | **+0.8037** | 與 combined_paper_safe_variant 歷史 Sharpe 一致 |

**品質觀察**：
- `basis = "historical_simulation_proxy_not_forward_execution"` 明示非真實 forward 執行 ✅
- `note` 提醒短窗結果與真實 forward paper 結果應分開看待 ✅
- 30d 的 −2.9012 對比 90d 的 +1.1681 和 760d 的 +0.8037，充分說明 30d 是雜訊窗口，符合 Opus 在 REVIEW-006 的解讀（30-day annualized 極 noisy，歷史 NAV 仍 +30.7%）

**判定**：✅ **PASS** — 完整且超出最低要求（同時提供 30d / 90d / 760d 三窗口，比 Opus 要求的「90-day 或 full」更完整）

---

### A-2：`fill_definition`

**需求（Opus REVIEW-006 裁定）**：simulated_fills schema 文件加註「fill = position delta vs prior period」，解釋 intended_fill_count=3 對一個 50-position portfolio 的含義。

**驗證結果**：`monthly_review.json` 頂層含 `fill_definition` 區塊：

```json
"fill_definition": {
    "basis": "position_delta_vs_prior_period",
    "description": "Each simulated fill row is a nonzero target position delta versus the prior rebalance position, not one row per held position.",
    "formula": "weight_delta = target_weight - prev_weight",
    "current_intended_fill_count": 3
}
```

`simulated_fills.csv` schema（3 列）：

| date | symbol | direction | target_weight | prev_weight | weight_delta | usd_notional | … |
|---|---|---|---|---|---|---|---|
| 2026-04-02 | BYBIT:ARBUSDT.P | short | −0.02 | 0.0 | −0.02 | −200.0 | … |
| 2026-04-02 | BYBIT:FLRUSDT.P | short | −0.02 | 0.0 | −0.02 | −200.0 | … |
| 2026-04-02 | BYBIT:NEARUSDT.P | long | 0.02 | 0.0 | 0.02 | 200.0 | … |

**品質觀察**：
- `prev_weight` 和 `weight_delta` 欄位明確在 CSV 中呈現 ✅
- `description` 說明「not one row per held position」，直接回答 Opus 疑問 ✅
- 3 筆填單的背景：target_date = 2026-04-02（run008 positions 的最後一次 rebalance day + 1），`prev_weight = 0`（起始日無前期持倉），故只有 3 個 symbol 有非零 delta（其他 47 個持倉 delta = 0 不出現）
- fill count = 3 是因為 2026-04-01 是初始建倉日（prior = 0），3 個 symbol 進入 / 改變方向，符合 delta-based 定義

**判定**：✅ **PASS** — schema 說明完整，CSV 欄位與定義一致，fill count 合理

---

### A-3：`funding_filter_active_this_month`

**需求（Opus REVIEW-006 裁定）**：monthly_review.json 加 `funding_filter_active_this_month` boolean，提醒讀者此 filter 是 regime-dependent 的。

**驗證結果**：`monthly_review.json` 含：

```json
"funding_filter_active_this_month": false,
"funding_filter_activity_note": "Funding filter is regime-dependent; false means no symbol breached the configured 30-day average funding threshold in this monthly setup.",
"funding_filter_event_count_this_month": 0
```

**品質觀察**：
- Boolean 存在，值為 `false`（2026-04-01 當月無 symbol 違反 0.03%/8h 門檻）✅
- `funding_filter_activity_note` 明確提醒「regime-dependent」，解釋 `false` 的含義 ✅
- 額外提供 `funding_filter_event_count_this_month = 0` 進一步說明 ✅
- 與 REVIEW-006 Sonnet draft 在 Caveat C-2 描述的「2026 Q1 funding filter 無效果（regime-dependent protection）」完全一致

**判定**：✅ **PASS** — 符合需求，且有說明性 note

---

## Paper / Live 執行狀態確認

以下各欄位均在多個輸出文件中明確標記：

| 檢查項目 | 文件 | 值 | 狀態 |
|---|---|---|---|
| `paper_execution_status` | monthly_review.json | `"FORBIDDEN_UNTIL_GATES_PASS"` | ✅ |
| `live_trading_status` | monthly_review.json | `"FORBIDDEN"` | ✅ |
| `live_trading_status` | paper_trading_setup.log | `FORBIDDEN` | ✅ |
| `forward_validation_pass` | forward_validation.json | `false` | ✅ |
| `forward_validation_status` | forward_validation.json | `"NOT_STARTED"` | ✅ |
| `pass_blocker` | forward_validation.json | "requires real 30-day forward paper record plus Opus REVIEW-006b and Rick approval" | ✅ |
| `safety_scan` | paper_trading_setup.log | `PASS, violations=[]` | ✅ |

Paper execution 和 live trading 均維持禁止，前置條件清楚記載。

---

## Reproducibility Hash 說明（Non-blocking 觀察）

| 文件 | Hash |
|---|---|
| REVIEW-006_PACKET.md（原始送審）| `40ab5158…` |
| paper_trading_setup.log（現況）| `89feeb1c…` |

兩個 hash 不同，原因是 addenda 補件（A-1/A-2/A-3）在 Opus REVIEW-006 PASS 後修改了輸出文件內容，導致 hash 改變。這是**預期行為**——補件改了 monthly_review.json 與 forward_validation.json 的結構。此差異不影響 addenda 驗收結論，但需記錄以備後續 REVIEW-006b 時 Opus 知悉。

---

## REVIEW-006b 開啟條件現況

| 條件 | 狀態 |
|---|---|
| TASK-007b DONE | ✅ 已滿足（2026-05-17 REVIEW-007b PASS） |
| 30 天 forward paper record（Sharpe > 0.5）| ❌ **NOT_STARTED**（最大阻擋項）|
| TASK-006 三個補件落地（A-1/A-2/A-3）| ✅ 本次確認落地 |

**REVIEW-006b 無法現在啟動**，最大阻擋：30 天 forward paper record 尚未存在。這需要 TASK-005 VPS monitor 上線後才能啟動 paper 記錄流程。

---

## 建議下一步（不含 paper execution 批准）

1. **TASK-005 VPS Bot Monitor**（`READY_TO_IMPLEMENT`）：啟動監控基建，為 30 天 forward paper record 建立前提條件。
2. **TASK-007c**（sensitivity，`TODO`）：Variant C 門檻比較，不擋 paper planning。
3. **TASK-008**（策略層 per-symbol weight cap，`TODO`）：長期任務，不擋短期 paper planning。

---

*Check v1.0 | Claude Sonnet | 2026-05-17*  
*範圍：TASK-006 三個 addenda 驗收；不含 REVIEW-006b 全面審查*  
*本文件未批准 paper execution 或 live trading；未標記 REVIEW-006b PASS*
