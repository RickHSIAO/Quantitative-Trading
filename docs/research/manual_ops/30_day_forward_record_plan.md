# 30-Day Forward Paper Record Plan

**文件狀態：** 規劃文件（Planning Only）
**建立日期：** 2026-05-17
**建立者：** Claude Sonnet

---

## ⛔ 重要聲明

**Paper execution 仍 FORBIDDEN。**
本文件是純粹的 record 規劃，說明未來 VPS 上線後應如何進行 30 天前向記錄。
在 Opus REVIEW-006b PASS 與 Rick 明示批准之前，不得提交任何真實或模擬委託單。

**Live trading 仍 FORBIDDEN。**
本文件不涉及任何真實資金、真實委託、或交易所帳戶寫入操作。

---

## 1. 起始條件（Start Conditions）

所有條件必須同時滿足，才可開始計算 30-day clock：

| 條件 | 狀態 | 說明 |
|---|---|---|
| TASK-007b DONE | ✅ 2026-05-17 | `combined_paper_safe_variant` 三條 overlay rule 驗證完畢 |
| TASK-005 VPS monitor online | ❌ NOT_STARTED | VPS 需實際部署 monitor stack |
| TASK-005a --test-send 驗證 | ✅ 2026-05-17 | Discord channel SENT，proof 存在 |
| TASK-006 三補件落地 | ✅ 2026-05-17 | proxy_sharpe_long_window / fill_definition / funding_filter_active_this_month |
| 策略 runner 在 VPS 可讀 Bybit 市場資料（read-only API） | ❌ NOT_STARTED | 只用讀取 API，不得有寫入 key |
| NEXT_ACTION 無 READY 任務 | ❌ 視情況 | 不得在 agent 任務進行中啟動計時 |

**Day 1 = VPS 上線且以上條件全滿足的第一個自然日。**
30-day clock 為連續 30 個自然日，不跳日。若 VPS 停機超過 1 天，clock 暫停並記錄中斷。

---

## 2. 策略規格（Strategy Spec）

使用 `combined_paper_safe_variant`（TASK-006 / TASK-007b primary spec）：

| 規則 | 參數 |
|---|---|
| 基礎策略 | Prev3Y crypto momentum，Bybit perp universe |
| 持倉方向 | Market neutral（long + short） |
| **Overlay Rule 1** | Long-side net exposure cap ±15%（net long ≤ +15%，net short ≥ −15%） |
| **Overlay Rule 2** | Single-symbol concentration < 25%（per side gross weight） |
| **Overlay Rule 3** | 若近 30 天平均 funding rate > 0.03%/8h，多頭部位降重 50% 或剔除 |
| Fill definition | Position delta vs prior period（非 intrabar 成交模擬） |
| Annualization | 365.25 天 |
| Cost model | Realistic combo（slippage + fee + funding）— 同 TASK-002 |

**非 primary spec（不用於此 record）：**
- `high_funding_cost_filter`（Sharpe 0.96）— secondary / sensitivity only
- 無 overlay 的 raw baseline — 不適用

---

## 3. 每日產生的檔案（Daily Artifacts）

每個交易日（UTC 00:05 後，市場資料可用時）產生以下檔案：

```
outputs/forward_record/prev3y_crypto/
├── <YYYYMMDD>_positions.parquet        # 每日持倉快照
├── <YYYYMMDD>_pnl.json                 # 當日 PnL 摘要
├── <YYYYMMDD>_overlay_check.json       # 三條 overlay rule 檢查結果
├── <YYYYMMDD>_forward_stats.json       # 滾動統計（更新累積）
└── forward_summary.json                 # 最新累積 summary（每日覆寫）

outputs/monitor/prev3y_crypto/
├── <YYYYMMDD>_heartbeat.parquet        # monitor heartbeat（既有）
└── alerts/<YYYYMMDD>.jsonl             # monitor alerts（既有）

outputs/logs/prev3y_crypto/
└── <YYYYMMDD>_forward_record.log       # 當日 runner log
```

**注意：** `forward_record/` 是新目錄，需在 VPS 部署時建立。
現有 `outputs/backtests/` 為歷史回測，不得混用。

---

## 4. Metrics Schema

### 4a. `<YYYYMMDD>_positions.parquet`

| 欄位 | 型態 | 說明 |
|---|---|---|
| `date` | date | UTC 日期 |
| `symbol` | str | Bybit perp symbol（e.g., `BTCUSDT`） |
| `side` | str | `long` / `short` |
| `weight` | float | 策略權重（post-overlay，-1 to +1） |
| `weight_raw` | float | overlay 前原始權重 |
| `funding_rate_30d_avg` | float | 近 30 天平均 funding rate（%/8h） |
| `overlay_rule1_applied` | bool | net cap 是否觸發 |
| `overlay_rule2_applied` | bool | concentration cap 是否觸發 |
| `overlay_rule3_applied` | bool | funding filter 是否觸發 |
| `hypothetical_fill_px` | float | 假設成交價（prior close，無滑點模擬） |
| `position_usd` | float | 假設持倉名義金額 USD |

### 4b. `<YYYYMMDD>_pnl.json`

```json
{
  "date": "YYYYMMDD",
  "day_number": 1,
  "nav_usd": 10000.00,
  "nav_change_usd": 0.00,
  "daily_pnl_pct": 0.0000,
  "cumulative_pnl_pct": 0.0000,
  "gross_exposure": 0.00,
  "net_exposure": 0.00,
  "long_weight_sum": 0.00,
  "short_weight_sum": 0.00,
  "top1_symbol_weight": 0.00,
  "funding_cost_usd": 0.00,
  "fee_cost_usd": 0.00,
  "slippage_cost_usd": 0.00,
  "paper_execution_status": "FORBIDDEN",
  "live_trading_status": "FORBIDDEN"
}
```

### 4c. `<YYYYMMDD>_overlay_check.json`

```json
{
  "date": "YYYYMMDD",
  "rule1_net_exposure_within_15pct": true,
  "rule1_actual_net_pct": 0.00,
  "rule2_all_symbols_below_25pct": true,
  "rule2_max_single_weight": 0.00,
  "rule2_violating_symbols": [],
  "rule3_funding_filtered_symbols": [],
  "rule3_funding_reduced_symbols": [],
  "overlay_pass": true
}
```

### 4d. `<YYYYMMDD>_forward_stats.json`

```json
{
  "date": "YYYYMMDD",
  "day_number": 1,
  "days_elapsed": 1,
  "sharpe_rolling_30d": null,
  "sharpe_cumulative": null,
  "max_dd_pct": 0.00,
  "current_dd_pct": 0.00,
  "tracking_error_vs_baseline_30d": null,
  "calmar_ratio": null,
  "hit_rate": null,
  "annualization": 365.25,
  "ddof": 1,
  "status": "RECORDING",
  "review_006b_trigger_ready": false,
  "paper_execution_status": "FORBIDDEN",
  "live_trading_status": "FORBIDDEN"
}
```

### 4e. `forward_summary.json`（每日覆寫）

```json
{
  "strategy": "prev3y_crypto_combined_paper_safe_variant",
  "start_date": "YYYYMMDD",
  "latest_date": "YYYYMMDD",
  "days_elapsed": 0,
  "days_required": 30,
  "clock_paused": false,
  "pause_reason": null,
  "sharpe_rolling_30d": null,
  "sharpe_cumulative": null,
  "max_dd_pct": 0.00,
  "tracking_error_vs_baseline_30d": null,
  "gate_status": {
    "sharpe_pass": null,
    "max_dd_pass": null,
    "overlay_always_pass": null,
    "no_stop_gate_triggered": null
  },
  "review_006b_trigger_ready": false,
  "paper_execution_status": "FORBIDDEN",
  "live_trading_status": "FORBIDDEN"
}
```

---

## 5. Sharpe / DD / Tracking Error 判定方式

### 5a. Sharpe Ratio

**公式（與歷史回測口徑一致，不得更改）：**

```
daily_returns = daily_pnl_pct  （每日 NAV 變動率）
mean_return   = mean(daily_returns)
std_return    = std(daily_returns, ddof=1)
sharpe_annualized = mean_return / std_return * sqrt(365.25)
```

**計算時機：**
- `sharpe_rolling_30d`：最近 30 個有效交易日的日報酬（不含停機日）
- `sharpe_cumulative`：從 Day 1 至今所有有效交易日
- Day 1–29：`sharpe_rolling_30d = null`（不足 30 天，不做門檻判斷）
- Day 30+：開始評估門檻

**Pass gate（Day 30 時評估）：**
- `sharpe_rolling_30d >= 0.5` → PASS（REVIEW-006b 可啟動）
- `sharpe_rolling_30d < 0.5` → WARN（延長記錄，見 § 6）
- `sharpe_rolling_30d < -0.5` → STOP（見 § 6）

**歷史參考：**
- Active 760-day Sharpe: **0.9267**（目標：forward 不低於 0.5）
- Cost stress realistic Sharpe: **0.892**
- 90-day proxy Sharpe: **1.1681**
- 30-day proxy Sharpe: **−2.9012**（已知為 30-day 年化雜訊，不代表策略崩潰）

### 5b. Maximum Drawdown

**公式：**
```
equity_curve = cumulative product of (1 + daily_pnl_pct)
running_max  = cummax(equity_curve)
drawdown     = (equity_curve - running_max) / running_max
max_dd       = min(drawdown)   （負數，e.g., −0.15 = −15%）
```

**Pass gate：**
- `max_dd > -0.30` → PASS（forward 期間最大 DD < 30%）
- `max_dd <= -0.30` → WARN
- `max_dd <= -0.40` → STOP

**歷史參考：**
- Baseline max DD: **−19.50%**
- Cost stress realistic max DD: **−19.64%**
- Stop gate 設 −40%（歷史 2× margin，審慎設定）

### 5c. Tracking Error vs Historical Baseline

**公式：**
```
baseline_daily_returns = 從歷史 CSV 取最近 30 個對應日曆日的日報酬
forward_daily_returns  = forward record 的日報酬
tracking_error_30d     = std(forward_returns - baseline_returns, ddof=1) * sqrt(365.25)
```

**注意：**
- baseline 用 `combined_paper_safe_variant` 回測的對應期間，非 raw baseline
- 若市場日曆不對齊，取最近 N 個有共同交易日
- tracking_error 為資訊性指標，不作為 STOP gate（只作為 WARN）

**Pass gate：**
- `tracking_error_30d < 0.30`（年化 30%）→ PASS
- `tracking_error_30d >= 0.30` → WARN（需 Claude 解釋原因）
- tracking_error 持續 > 0.50 連續 5 天 → 升級為 STOP

---

## 6. Warning / Stop Gate

### Warning Gates（記錄，不停止）

| Gate | 觸發條件 | 處置 |
|---|---|---|
| W-1 低 Sharpe | Day 30+ 且 `sharpe_rolling_30d < 0.5`（但 ≥ −0.5） | 延長記錄至 Day 45；Claude 記錄警告 |
| W-2 中度 DD | `max_dd <= -0.25`（但 > −0.30） | Claude 記錄警告；Rick 知情 |
| W-3 高 tracking error | `tracking_error_30d >= 0.30` | Claude 記錄警告；分析偏差原因 |
| W-4 overlay rule 頻繁觸發 | 連續 5 天 overlay_pass=false（任一 rule） | Claude 分析是否市場結構改變 |
| W-5 Monitor heartbeat 中斷 | VPS heartbeat 缺失 > 2 小時 | Monitor alert 觸發；clock 暫停計時 |
| W-6 Clock 中斷 | VPS 停機導致資料缺失 > 1 天 | 記錄中斷原因；clock 暫停；Rick 決定是否重置 |

### Stop Gates（立即暫停，通知 Rick）

| Gate | 觸發條件 | 處置 |
|---|---|---|
| S-1 Sharpe 崩潰 | `sharpe_rolling_30d < -0.5`（任何時間點，≥10 天資料後評估） | 停止計時；Claude 寫 STOP 報告；等 Rick 指示 |
| S-2 重大 DD | `max_dd <= -0.40` | 停止計時；Claude 寫 STOP 報告；等 Rick 指示 |
| S-3 高 tracking error 持續 | tracking_error_30d > 0.50 連續 5 天 | 停止計時；Claude 分析偏差原因 |
| S-4 Overlay rule 失效 | 連續 10 天 overlay_pass=false | 停止計時；Codex 檢查 rule 實作 |
| S-5 Safety scan FAIL | 任何時間 safety.py 回傳 FAIL | 立即停止；Claude + Rick 共同審查 |
| S-6 資料異常 | 當日 universe < 10 個 symbol，或缺失 > 20% | 跳過當日（clock 不計入）；記錄原因 |

**Stop 處置流程：**
1. Monitor alert 觸發（channel: Telegram / Discord）
2. Claude 在 `COMMAND_LOG.md` 記錄 STOP 事件
3. 更新 `forward_summary.json`：`clock_paused: true`、`pause_reason: "S-X"`
4. 等待 Rick 明示指令決定：重置 / 繼續 / 中止

---

## 7. REVIEW-006b 啟動條件

以下**全部**滿足時，Claude 可向 Rick 提議啟動 REVIEW-006b：

| 條件 | 說明 |
|---|---|
| `days_elapsed >= 30` | 連續 30 自然日記錄完成（無中斷或中斷已補足） |
| `sharpe_rolling_30d >= 0.5` | Day 30 滾動 Sharpe 通過門檻 |
| `max_dd > -0.30` | 前向期間最大 DD 未超過 30% |
| `no_stop_gate_triggered = true` | 30 天內無 S-1 至 S-6 任何 Stop gate 觸發 |
| `overlay_always_pass` 或 exception 已記錄 | 三條 overlay rule 在 30 天內均有效執行（或偏差有記錄解釋） |
| TASK-006 三補件落地 | proxy_sharpe_long_window ✅ / fill_definition ✅ / funding_filter_active_this_month ✅（均已落地） |
| TASK-007b DONE | ✅（已完成） |

**REVIEW-006b 由 Opus 執行。**
Claude Sonnet 只可準備 review packet，不可自行宣告 PASS。

**REVIEW-006b 啟動後，paper execution 仍 FORBIDDEN，直到 Opus PASS + Rick 明示批准。**

---

## 8. 每日檢查項（Daily Checklist）

每日 UTC 01:00 後，Claude（或 Codex runner）應確認：

```
[ ] outputs/forward_record/prev3y_crypto/<YYYYMMDD>_positions.parquet 存在
[ ] outputs/forward_record/prev3y_crypto/<YYYYMMDD>_pnl.json 存在
[ ] outputs/forward_record/prev3y_crypto/<YYYYMMDD>_overlay_check.json 存在
[ ] <YYYYMMDD>_forward_stats.json 存在且 sharpe_rolling_30d 欄位有值（Day 30+）或 null（Day 1–29）
[ ] forward_summary.json 已更新 latest_date = 今日
[ ] overlay_check.overlay_pass = true（或 warning 已記錄）
[ ] Monitor heartbeat 正常（不含中斷）
[ ] safety_scan.status = PASS
[ ] paper_execution_status = FORBIDDEN（每個輸出檔均需含此欄位）
[ ] live_trading_status = FORBIDDEN（每個輸出檔均需含此欄位）
[ ] 無 Stop gate 觸發（若有，立即暫停並通知 Rick）
```

---

## 9. VPS 部署前置（非本文件範圍，列出以備參考）

以下事項需在 30-day clock 啟動前完成，但不在本文件的執行範圍：

- VPS 主機建立（未開始）
- Monitor stack 部署（TASK-005 code 已完成，待部署）
- `configs/monitor_secrets.local.yaml` 在 VPS 上配置（Rick ops）
- Bybit read-only API key 配置（Rick ops；只讀取行情，不提交委託）
- `combined_paper_safe_variant` runner 在 VPS 上排程（Codex 任務）
- cron job 或 systemd timer 每日跑 forward record + monitor

---

## 10. 關鍵歷史基準（供對照）

| 指標 | 口徑 | 數值 |
|---|---|---|
| Sharpe | active 760d | **0.9267** |
| Sharpe | cost stress realistic | **0.892** |
| IR vs eqw | active 760d | **0.7227** |
| Max DD | baseline | **−19.50%** |
| Max DD | cost stress realistic | **−19.64%** |
| Annual turnover | baseline | **1.228×** |
| 90-day proxy Sharpe | proxy（非前向執行） | **1.1681** |
| 30-day proxy Sharpe | proxy（年化雜訊） | **−2.9012** |

**30-day forward Sharpe 門檻：>= 0.5**（歷史 active Sharpe 0.9267 的約 54%，審慎但不過嚴）

---

## 11. 文件版本

| 版本 | 日期 | 說明 |
|---|---|---|
| v1.0 | 2026-05-17 | 初版，Claude Sonnet |

---

*本文件為規劃文件，不授權任何 paper execution 或 live trading。*
*Paper execution 在 Opus REVIEW-006b PASS + Rick 明示批准前，永遠 FORBIDDEN。*
*Live trading 在另一輪專屬 Opus review + Rick 明示批准前，永遠 FORBIDDEN。*
