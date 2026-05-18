# 30-Day Forward Paper Record — Start Checklist

**文件狀態：** 操作清單（Operational Checklist）
**版本：** v1.0
**建立日期：** 2026-05-17
**建立者：** Claude Sonnet
**參考規劃文件：** `docs/research/manual_ops/30_day_forward_record_plan.md`

---

## ⛔ 核心聲明（每次使用前必讀）

- **本清單不授權 paper execution。**
- **本清單不授權 live trading。**
- **30-day forward record 是純粹的模擬記錄（signal generation + hypothetical fill tracking），不得連接交易 API 寫入端點，不得提交任何委託單。**
- Paper execution 在 Opus **REVIEW-006b PASS** + **Rick 明示批准** 之前，永遠 FORBIDDEN。
- Live trading 在另一輪專屬 Opus review + Rick 明示批准之前，永遠 FORBIDDEN。

---

## 0. 前置狀態確認（啟動前必須全部 ✅）

| 項目 | 狀態 | 說明 |
|---|---|---|
| TASK-006 primary spec 確認 | ✅ | `combined_paper_safe_variant`（3 overlay rules）|
| TASK-007b weight-cap 驗證 | ✅ 2026-05-17 | overlay rule 路徑正式關閉；alpha-space 問題另案 |
| TASK-005 VPS monitor（code） | ✅ 2026-05-17 | 程式碼完成；**VPS 部署尚未發生**（見 §0b）|
| TASK-005a real --test-send | ✅ 2026-05-17 | Discord channel SENT；proof 存在；token 已 REDACTED |
| TASK-006 三補件落地 | ✅ 2026-05-17 | proxy_sharpe / fill_definition / funding_filter_active |
| TASK-008 CONDITIONAL_PASS | ✅ 2026-05-17 | Opus REVIEW-008；A_roll12_share20_exclude = shadow-track |
| **VPS 實際部署** | ❌ NOT_STARTED | **30-day clock 不得在此完成前啟動** |
| **Bybit read-only API 配置** | ❌ NOT_STARTED | 只讀行情；不得有寫入 key |
| **Rick 指定起算日** | ❌ PENDING | **見 §1** |
| NEXT_ACTION 無 READY 任務 | ✅（WAITING）| 確認 NEXT_ACTION.md status = WAITING 後啟動 |

### §0b. VPS 部署狀態說明

**30-day clock 尚未啟動。** VPS 部署是 clock 啟動的必要前置條件。
本清單可在 VPS 部署前提前準備；但 §2 之後的項目只有在 VPS 上線後才有意義。

---

## 1. Rick 需要指定的事項

在指示 Claude 或 Codex 啟動 30-day forward record 之前，Rick 需要明確決定：

### 1a. 起算日（必要）

```
30-day clock Day 1 = ________________（請填入 YYYY-MM-DD）
```

**建議起算日邏輯：**
- Day 1 = VPS 實際上線且所有 §0 條件滿足的第一個自然日
- 不可回填（不可指定過去日期）
- 建議選擇月初或 rebalance 日後第一天，以便與策略週期對齊

### 1b. Shadow-Track 同步記錄（optional，強烈建議）

| 選項 | 說明 |
|---|---|
| **A. 同步記錄**（推薦）| primary + shadow-track 同時跑；每日各自輸出；REVIEW-006b 以 primary 為準 |
| B. 只記錄 primary | shadow-track 稍後補開 |

> **推薦選 A**：`A_roll12_share20_exclude` 目前是 TASK-008 最優 variant，同步追蹤可在 30 天後為 REVIEW-006b 提供額外對照資料。

### 1c. Initial NAV 設定（用於持倉 USD 換算）

```
initial_nav_usd = ________________（預設 10,000；可設 50,000）
```

---

## 2. 策略規格確認

### Primary（必跑）：`combined_paper_safe_variant`

| 規則 | 參數 | 狀態 |
|---|---|---|
| 基礎策略 | Prev3Y crypto momentum，Bybit perp universe | ✅ run008 confirmed |
| Overlay Rule 1 | 多頭 symbol avg_funding_30d > 0.03%/8h → 排除 | ✅ TASK-006 verified |
| Overlay Rule 2 | sum(long_weights) > 50% gross_exposure → 等比縮減 | ✅ TASK-007b verified |
| Overlay Rule 3 | 單一 symbol \|weight\| > 5% gross_exposure → 截斷 | ✅ TASK-007b verified |
| Fill definition | Position delta vs prior period（非 intrabar） | ✅ TASK-006 補件確認 |
| Annualization | 365.25 | ✅ |
| Cost model | Realistic combo（slippage + fee + funding）| ✅ TASK-002 |

### Shadow-Track（若 Rick 選 §1b Option A）：`A_roll12_share20_exclude`

| 指標 | 數值 | 說明 |
|---|---|---|
| Sharpe (active 760d) | 0.9636 | Pareto-dominant vs baseline |
| single_conc | 23.43% | < 25% ✅ |
| top5_conc | 87.95% | W-1 observation（Opus 裁定可接受 ≤ 90%） |
| alpha_retention | 108.65% | 超越 baseline |
| 實作位置 | `src/variants/task008.py` | `apply_alpha_contribution_cap()` |
| 介入層 | Alpha-space（post-selection） | 不修改 overlay rules |

> **Shadow-track 不影響 REVIEW-006b 的啟動或通過判定。** REVIEW-006b 以 primary 結果為準。

---

## 3. 每日輸出檔案清單

每個交易日（UTC 00:05 後）應產生以下檔案：

### Primary（每日必存）

```
outputs/forward_record/prev3y_crypto/
├── <YYYYMMDD>_positions.parquet       # 持倉快照（post-overlay）
├── <YYYYMMDD>_pnl.json                # 當日 PnL
├── <YYYYMMDD>_overlay_check.json      # 三條 overlay rule 檢查
├── <YYYYMMDD>_forward_stats.json      # 滾動統計（Sharpe / DD / tracking error）
└── forward_summary.json               # 累積 summary（每日覆寫）
```

### Shadow-Track（若啟用，每日同步）

```
outputs/forward_record/prev3y_crypto_shadow_a_roll12/
├── <YYYYMMDD>_positions.parquet
├── <YYYYMMDD>_pnl.json
├── <YYYYMMDD>_forward_stats.json
└── forward_summary.json
```

### Monitor（既有架構）

```
outputs/monitor/prev3y_crypto/
├── <YYYYMMDD>_heartbeat.parquet
└── alerts/<YYYYMMDD>.jsonl
```

### 每日強制欄位（每個輸出 JSON 必須含）

```json
"paper_execution_status": "FORBIDDEN",
"live_trading_status":    "FORBIDDEN"
```

---

## 4. 每日檢查項（Daily Checklist，UTC 01:00 後）

```
[ ] <YYYYMMDD>_positions.parquet 存在
[ ] <YYYYMMDD>_pnl.json 存在
[ ] <YYYYMMDD>_overlay_check.json 存在且 overlay_pass 有值
[ ] <YYYYMMDD>_forward_stats.json 存在
[ ] forward_summary.json.latest_date == 今日
[ ] overlay_check.overlay_pass = true（或 warning 已記錄）
[ ] Monitor heartbeat 正常
[ ] safety_scan.status = PASS（若有實作）
[ ] paper_execution_status = FORBIDDEN（全部輸出均含此欄）
[ ] live_trading_status = FORBIDDEN（全部輸出均含此欄）
[ ] 無 Stop gate 觸發（若有，立即 §6 流程）
[ ] （若 shadow-track 啟用）shadow 輸出目錄同步存在
```

---

## 5. Warning / Stop Gate 快速參考

### Warning Gates（記錄，不停止 clock）

| Gate | 觸發條件 | 處置 |
|---|---|---|
| W-1 | Day 30+，sharpe_rolling_30d < 0.5（但 ≥ −0.5） | 延長至 Day 45；Claude 記錄警告 |
| W-2 | max_dd ≤ −25%（但 > −30%） | Claude 記錄；Rick 知情 |
| W-3 | tracking_error_30d ≥ 0.30（年化） | Claude 記錄；分析偏差原因 |
| W-4 | 連續 5 天 overlay_pass = false | Claude 分析市場結構 |
| W-5 | VPS heartbeat 缺失 > 2h | Monitor alert；clock 暫停計時 |
| W-6 | VPS 停機 > 1 天 | 記錄中斷；clock 暫停；Rick 決定是否重置 |

### Stop Gates（立即暫停，通知 Rick）

| Gate | 觸發條件 | 處置 |
|---|---|---|
| S-1 | sharpe_rolling_30d < −0.5（≥10 天資料後評估） | 停止計時；Claude 寫 STOP 報告 |
| S-2 | max_dd ≤ −40% | 停止計時；Claude 寫 STOP 報告 |
| S-3 | tracking_error_30d > 0.50 連續 5 天 | 停止計時；Claude 分析原因 |
| S-4 | 連續 10 天 overlay_pass = false | 停止計時；Codex 檢查 rule 實作 |
| S-5 | safety_scan 回傳 FAIL | 立即停止；Claude + Rick 共同審查 |
| S-6 | 當日 universe < 10 symbols 或缺失 > 20% | 跳過當日（clock 不計入）；記錄原因 |

**Stop 處置流程：**
1. Monitor alert 觸發（Telegram / Discord）
2. Claude 在 `COMMAND_LOG.md` 記錄 STOP 事件
3. `forward_summary.json`：`clock_paused: true`、`pause_reason: "S-X"`
4. 等 Rick 明示指令（重置 / 繼續 / 中止）

---

## 6. REVIEW-006b 啟動條件

以下**全部**滿足時，Claude 向 Rick 提議啟動 REVIEW-006b（以 **primary** 結果為準）：

| 條件 | 說明 |
|---|---|
| `days_elapsed >= 30` | 連續 30 自然日完成（無中斷或已補足） |
| `sharpe_rolling_30d >= 0.5` | Day 30 滾動 Sharpe 通過門檻 |
| `max_dd > -0.30` | 前向期間最大 DD 未超 30% |
| `no_stop_gate_triggered = true` | 30 天內無 S-1 至 S-6 任何 Stop gate |
| `overlay_always_pass` 或偏差有記錄 | 三條 overlay rule 均有效執行 |
| TASK-006 三補件落地 | ✅（已完成） |
| TASK-007b DONE | ✅（已完成） |

**重要：** REVIEW-006b 由 **Opus** 執行。Claude Sonnet 只可準備 review packet。
REVIEW-006b PASS 後，paper execution 仍 FORBIDDEN，直到 Rick 明示批准。

---

## 7. 禁止事項（Red Lines）

以下任何操作在 30-day forward record 期間均**絕對禁止**：

```
❌ 連接 Bybit 或任何交易所的下單 / 委託 endpoint
❌ 使用交易所寫入 API key（包含 demo / testnet 帳戶）
❌ 提交任何形式的 paper order 或 live order
❌ 修改 src/signals/prev3y_momentum.py（策略主流程）
❌ 修改 run008 / TASK-002 / TASK-003 / TASK-007 / TASK-008 的任何官方輸出
❌ 修改 data/ 目錄下任何歷史資料
❌ 宣稱 paper execution 已批准（須 REVIEW-006b PASS + Rick 明示）
❌ 宣稱 live trading 已批准（須另一輪 Opus review + Rick 明示）
❌ 回填歷史日期的 forward record（只能向前記錄）
❌ 在 Stop gate 觸發後繼續計時（須 Rick 明示才可重啟）
```

---

## 8. 完成後動作

30-day record 完成且 REVIEW-006b 啟動條件滿足時，Claude 執行以下步驟（需 Rick 指示）：

1. 準備 REVIEW-006b packet（`docs/research/review_packets/REVIEW-006b_PACKET.md`）
2. 更新 CLAUDE_REVIEW_QUEUE.md：加入 REVIEW-006b PENDING
3. 更新 NEXT_ACTION.md：READY / Owner=Opus / Task=REVIEW-006b
4. 通知 Rick review packet 已就緒

每次 Claude 完成任何步驟後，NEXT_ACTION.md 回到 **WAITING / Owner=Rick**，等待 Rick 指示下一步。

---

## 9. 版本紀錄

| 版本 | 日期 | 說明 |
|---|---|---|
| v1.0 | 2026-05-17 | 初版，Claude Sonnet；TASK-008 CONDITIONAL_PASS 後建立 |

---

*本清單不授權任何 paper execution 或 live trading。*
*所有執行授權均需 Opus review PASS + Rick 明示批准。*
