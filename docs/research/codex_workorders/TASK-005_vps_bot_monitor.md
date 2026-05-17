# TASK-005 — VPS Bot Monitor

- **狀態**：READY_TO_IMPLEMENT
- **Owner**：Codex
- **預估**：M（3–5 天）
- **依賴**：可獨立進行；不依賴 TASK-003/004/006/007/007b；後續可與 Ollama 串接做 log 摘要
- **工單版本**：v1.0（2026-05-17，由 Claude Sonnet 撰寫）
- **觸發原因**：
  - Opus REVIEW-002 PASS（2026-05-15）解鎖本任務。
  - TASK-005 VPS monitor 上線是 paper trading 執行的前置條件之一。
  - 30 天 forward paper record 必須有監控基建才能可靠地累積。

---

## ⚠️ 執行閘門聲明

**TASK-005 是 paper trading 執行的前置條件，但本任務本身不包含任何交易行為。**

- 本任務只建立監控層（observer），不可觸碰 bot 的下單邏輯。
- 不可取得可下單的 API key；只准用 read-only / IP-whitelisted key。
- 完成後狀態改為 `REVIEW`，等 Claude Sonnet 審查後送 Rick 確認上線。
- Paper trading 執行仍須等其他前置條件全部完成後由 Opus 另行核准。

---

## 1. 任務一句話

在 VPS 上建立一個旁觀者監控層（observer-only），定期對 trading bot 做心跳檢查、偵測異常沉默、收集錯誤 log 並在出狀況時推播告警，為後續 paper trading 的 30 天 forward record 提供可靠的監控基建。

---

## 2. 任務目的

### 背景

Paper trading forward validation 需要持續 30 天的可靠 paper record，Sharpe > 0.5 才能解鎖 REVIEW-006b。要讓這 30 天不因為「bot 掛了沒人知道」而中斷，必須事先建好監控層。

### 本任務要解決的問題

1. **Bot 死亡偵測**：Bot process crash 或 VPS 斷網時，有沒有人知道？多久才知道？
2. **訂單沉默偵測**：Bot 應該下單但沒下（例如信號觸發但 API timeout），能不能在 N 分鐘內發現？
3. **PnL 異常追蹤**：當天 PnL delta 超出預期範圍時，能不能自動標記？
4. **Error log 彙整**：bot 的錯誤 log 分散在 VPS 多個檔案，能不能集中收集、去重、推播摘要？
5. **安全邊界**：監控工具不能成為另一個下單入口，只能讀取狀態。

---

## 3. 為什麼重要

- 真錢上線後，最致命的不是策略爛，而是「bot 掛了沒人知道」「API key 失效」「斷網 6 小時」。
- 監控層必須在策略上線**前**就準備好；事後補做容易留安全漏洞或覆蓋率缺口。
- 之後 Ollama 可以幫忙摘要每天的 log，讓 Rick 不用每天看上千行原始 log。
- 此基建也是 REVIEW-006b 評審時用以確認 30 天 paper record 完整性的依據之一。

---

## 4. 範圍邊界

### ✅ Do（允許做）

- 在 `apps/monitor/` 下建立獨立監控模組（`monitor.py`、`alerts.py`、`config.py`、`README.md`）。
- 實作心跳 ping（HTTP / process check / exchange REST status endpoint 擇一或組合）。
- 讀取 bot 的 log 檔（`/var/log/quantbot/*.log` 或 config 指定路徑），解析錯誤行並彙整。
- 用交易所 **read-only REST API** 查詢最近成交時間、帳戶 equity（帳戶層級，非下單 API）。
- 計算 PnL daily delta（equity_today − equity_yesterday）並記錄至 `outputs/monitor/heartbeat.parquet`。
- 實作告警 deduplication（同類問題 30 分鐘內不重複推播）。
- 實作至少 1 個通知 channel（Telegram Bot API 優先；Discord Webhook / SMTP 擇一備用）。
- 寫 `configs/monitor.yaml`，讓心跳 interval、告警閾值、通知 channel 全部可設定。
- 寫 unit test：`tests/monitor/test_heartbeat.py`、`tests/monitor/test_alerts.py`。

### ❌ Don't（禁止做）

- **不可**取得或使用可下單的 API key（任何帶有 `WRITE` / `TRADE` / `WITHDRAW` 權限的 key）。
- **不可**修改 bot 本身的任何下單邏輯、信號生成、rebalance 排程。
- **不可**把 monitor 模組寫進策略核心（`src/` 或 `apps/paper_trading/`）；必須獨立在 `apps/monitor/`。
- **不可**讓 monitor 自動觸發任何交易動作（kill、restart bot 等需人工介入）。
- **不可**在 log 或 output 中記錄完整 API key 或帳戶 secret。
- **不可**連接非 Bybit 的交易所（本任務只針對 Bybit perp 環境）。
- **不可**啟動 paper trading 執行或 live trading。
- **不可**修改任何 `outputs/` 下的既有研究輸出（run008、cost stress、attribution、variants、paper_trading 歷史檔）。

---

## 5. 輸入檔案（規劃路徑）

| 檔案 / 來源 | 說明 |
|---|---|
| `/var/log/quantbot/*.log`（VPS 路徑，或 config 指定）| Bot 寫出的原始 log |
| Bybit REST API（read-only key）| 帳戶 equity、最近成交時間、open positions（唯讀查詢）|
| `configs/monitor.yaml` | 心跳 interval、告警閾值、通知 channel、log 路徑 |
| `configs/monitor_secrets.yaml`（gitignored）| Telegram token / chat ID、SMTP 密碼等（不得進版控）|

### `configs/monitor.yaml` 最低欄位規格

```yaml
heartbeat:
  interval_seconds: 60        # 心跳間隔（≤ 60 秒）
  failure_threshold: 3        # 連續失敗幾次觸發 CRITICAL
  order_silence_minutes: 15   # 超過幾分鐘無成交 → WARNING（rebalance 窗口後）

pnl:
  daily_delta_warn_pct: 5.0   # 單日 equity delta 超過 ±5% → WARNING
  equity_floor_usd: 8000      # equity 低於此值 → CRITICAL（配合 NAV floor）

alerts:
  dedup_window_minutes: 30    # 同類告警去重窗口
  channels:
    - type: telegram
      enabled: true

logging:
  bot_log_paths:
    - /var/log/quantbot/*.log
  output_heartbeat: outputs/monitor/heartbeat.parquet
  output_alerts_dir: outputs/monitor/alerts/
```

---

## 6. 輸出檔案

| 路徑 | 格式 | 說明 |
|---|---|---|
| `apps/monitor/monitor.py` | Python | 主監控 loop：心跳、沉默偵測、PnL delta |
| `apps/monitor/alerts.py` | Python | 告警管理：去重、channel dispatch |
| `apps/monitor/config.py` | Python | YAML 解析、schema validation |
| `apps/monitor/README.md` | Markdown | 操作說明（見 Section 9） |
| `configs/monitor.yaml` | YAML | 設定範本（可提交版控，不含 secret）|
| `tests/monitor/test_heartbeat.py` | Python | 心跳邏輯 unit test |
| `tests/monitor/test_alerts.py` | Python | 告警去重 / dispatch unit test |
| `outputs/monitor/heartbeat.parquet` | Parquet | 每次心跳記錄（schema 見下）|
| `outputs/monitor/alerts/<YYYYMMDD>.jsonl` | JSONL | 每日告警記錄，每筆一行 |
| `outputs/logs/monitor/<YYYYMMDD>_monitor.log` | Log | Monitor 自身 run log |

### `heartbeat.parquet` Schema

| 欄位 | 型別 | 說明 |
|---|---|---|
| `timestamp` | datetime64[ns, UTC] | 心跳時間（UTC） |
| `bot_id` | str | Bot 識別碼（config 指定）|
| `status` | str | `OK` / `WARNING` / `CRITICAL` / `UNKNOWN` |
| `latency_ms` | float | API ping 延遲（ms）|
| `last_order_time` | datetime64[ns, UTC] | 交易所回報的最近成交時間 |
| `equity_usd` | float | 帳戶 equity（USD）|
| `daily_pnl_delta_usd` | float | equity_today − equity_yesterday |
| `active_positions` | int | 目前持倉數量 |
| `notes` | str | 任何異常備註（空字串或描述）|

### `alerts/<YYYYMMDD>.jsonl` Schema（每行一筆）

```json
{
  "timestamp": "2026-04-02T08:15:00Z",
  "alert_type": "HEARTBEAT_FAILURE",
  "severity": "CRITICAL",
  "bot_id": "prev3y_crypto_paper",
  "message": "3 consecutive heartbeat failures",
  "dedup_key": "HEARTBEAT_FAILURE:prev3y_crypto_paper",
  "notified": true,
  "channel": "telegram"
}
```

---

## 7. 核心功能規格

### 7.1 心跳檢查（Heartbeat）

- **間隔**：≤ 60 秒一次（`heartbeat.interval_seconds`）。
- **方法**（依優先序）：
  1. Bybit REST API `GET /v5/account/wallet-balance`（read-only key，同時取得 equity）
  2. VPS process check（`ps aux | grep bot_process_name`）
  3. 若兩者都不可用，標記 `status=UNKNOWN`
- **觸發 CRITICAL**：連續 3 次（`failure_threshold`）心跳失敗。
- **回復**：CRITICAL 狀態下一次心跳成功 → 降回 OK，並推播「Bot 恢復正常」通知。

### 7.2 訂單沉默偵測（Order Silence）

- 比較 `last_order_time`（交易所成交記錄）與「預期下一次 rebalance 時間」。
- 若 rebalance 窗口結束後超過 `order_silence_minutes` 分鐘仍無成交 → 推播 `ORDER_SILENCE` WARNING。
- **Rebalance 時間**：從 `configs/monitor.yaml` 設定（例如每日 UTC 00:05）。
- **豁免條件**：若當日信號產生 0 筆 delta（無需 rebalance），不觸發沉默告警。

### 7.3 PnL Daily Delta 告警

- 每日 UTC 00:10 計算：`daily_pnl_delta_usd = equity_now − equity_yesterday_close`。
- 若 `|daily_pnl_delta_usd / equity_yesterday_close| > daily_delta_warn_pct`（預設 5%） → WARNING。
- 若 `equity_usd < equity_floor_usd`（預設 8,000 USD） → CRITICAL（配合 TASK-006 NAV floor 設計）。

### 7.4 Error Log 彙整

- 每 5 分鐘掃描 `bot_log_paths` 下所有 `*.log` 檔案，提取 `ERROR` / `CRITICAL` / `EXCEPTION` 行。
- 對相同 error message 做 30 分鐘去重（`dedup_key = error_type:message_hash[:32]`）。
- 去重後的新 error → 推播摘要（最多前 3 行 context）。
- 所有 error 行寫入當日 `alerts/<YYYYMMDD>.jsonl`，`alert_type = LOG_ERROR`。

---

## 8. 告警設計

### 告警類型與嚴重等級

| `alert_type` | 嚴重等級 | 觸發條件 |
|---|---|---|
| `HEARTBEAT_FAILURE` | CRITICAL | 連續 3 次心跳失敗 |
| `BOT_RECOVERED` | INFO | CRITICAL → 恢復 OK |
| `ORDER_SILENCE` | WARNING | 超過 N 分鐘無成交（rebalance 後）|
| `PNL_SPIKE` | WARNING | 單日 delta 超過 ±5% |
| `EQUITY_FLOOR` | CRITICAL | equity < floor |
| `LOG_ERROR` | WARNING | bot log 出現新 ERROR / EXCEPTION |
| `CONFIG_INVALID` | CRITICAL | monitor.yaml schema 驗證失敗 |
| `API_KEY_INVALID` | CRITICAL | Bybit API 回傳認證錯誤 |

### Deduplication 規則

- `dedup_key = alert_type + ":" + bot_id`（大部分告警）
- `dedup_key = "LOG_ERROR:" + message_hash[:32]`（log error 依 message 去重）
- 同一 `dedup_key` 在 `dedup_window_minutes`（預設 30 分鐘）內不重複推播。
- CRITICAL 等級：去重窗口縮短為 5 分鐘（緊急狀況需要更快重複提醒）。

---

## 9. 通知 Channel

### 優先實作：Telegram Bot API

- `POST https://api.telegram.org/bot{token}/sendMessage`
- 設定：`configs/monitor_secrets.yaml`（gitignored）含 `telegram.token` + `telegram.chat_id`
- 訊息格式：

```
[CRITICAL] prev3y_crypto_paper
時間: 2026-04-02 08:15 UTC
類型: HEARTBEAT_FAILURE
說明: 3 consecutive heartbeat failures (last OK: 08:12 UTC)
動作: 請立即檢查 VPS + bot process
```

### 備用（至少選一）：Discord Webhook 或 SMTP Email

- Discord：`POST {webhook_url}` with JSON payload
- SMTP：`smtplib.SMTP_SSL`，收件人、Subject、Body 均從 config 設定

### Channel 切換

- `configs/monitor.yaml` 中 `channels` 為列表，支援多 channel 同時推播。
- 若 Telegram 推播失敗，自動降級嘗試備用 channel，並在 log 中標記。

---

## 10. 安全性要求

| 要求 | 說明 |
|---|---|
| API key 最小權限 | 只允許 Bybit read-only key（Unified Account Position / Wallet 查詢）|
| Secret 隔離 | `configs/monitor_secrets.yaml` 必須在 `.gitignore` 中；不得進版控 |
| Log 不露 key | 任何 log 輸出不得含完整 API key 或 secret；最多記錄 key[:8] + "…" |
| 不可下單 | monitor 的 API client 必須只初始化 GET 方法；無任何 POST order endpoint |
| 不可 restart bot | monitor 只能**通知**，不可自動 restart 或 kill bot process |
| IP whitelist 建議 | README 建議把 monitor server IP 加入 Bybit API key 的 IP whitelist |

---

## 11. Fail Gates（完成後 Codex 自查）

以下任一觸發 → **FAIL**，不可進入 REVIEW：

| Gate | 觸發條件 |
|---|---|
| `missing_outputs` | `apps/monitor/*.py`、`configs/monitor.yaml`、`tests/monitor/*.py`、`heartbeat.parquet`（至少 1 筆）、`alerts/` 目錄任一缺失 |
| `test_failure` | `python -m unittest tests.monitor.test_heartbeat tests.monitor.test_alerts` 任一 FAIL |
| `schema_mismatch` | `heartbeat.parquet` 欄位與 Section 6 規格不符 |
| `api_key_permission_violation` | monitor code 含任何 `place_order`、`cancel_order`、`POST /v5/order`、`WITHDRAW` 相關 import 或呼叫 |
| `secret_in_vcs` | `monitor_secrets.yaml` 未在 `.gitignore`，或 log 中含完整 key string |
| `core_module_modified` | `src/`、`apps/paper_trading/`、`outputs/` 下任何既有研究檔案被修改 |

## 12. Warning Gates（完成後 Codex 自查）

以下觸發 → WARNING，記錄於 gate report，不擋 REVIEW：

| Gate | 觸發條件 |
|---|---|
| `single_channel_only` | 只實作 1 個通知 channel（建議 ≥ 2） |
| `no_recovery_alert` | 未實作 `BOT_RECOVERED` INFO 通知 |
| `no_pnl_floor_check` | 未實作 `EQUITY_FLOOR` CRITICAL 告警 |
| `dedup_window_too_long` | CRITICAL 告警去重窗口超過 10 分鐘 |
| `heartbeat_interval_too_long` | 心跳 interval 超過 120 秒 |

---

## 13. 禁止修改範圍

| 範圍 | 說明 |
|---|---|
| `src/` | 所有策略信號、ranking、universe 選擇程式 |
| `apps/paper_trading/` | Paper trading planning / simulation 模組 |
| `outputs/paper_trading/` | TASK-006 官方輸出（monthly_review、forward_validation、simulated_fills 等）|
| `outputs/variants/` | TASK-007 / TASK-007b 官方輸出 |
| `outputs/attribution/` | TASK-003 attribution 官方輸出 |
| `outputs/backtest/` | run008 baseline 官方輸出 |
| `docs/research/review_packets/` | 所有 REVIEW PACKET / NUMBERS.json |
| `data/` / `raw/` | 原始市場資料（價格、funding rate） |

---

## 14. 完成後回報格式

Codex 完成後，於 `outputs/logs/monitor/<YYYYMMDD>_monitor_delivery.log` 輸出：

```
TASK-005 VPS Bot Monitor Delivery
run_date=<YYYYMMDD>
status=REVIEW_READY

files_created:
  apps/monitor/monitor.py
  apps/monitor/alerts.py
  apps/monitor/config.py
  apps/monitor/README.md
  configs/monitor.yaml
  tests/monitor/test_heartbeat.py
  tests/monitor/test_alerts.py
  outputs/monitor/heartbeat.parquet   (N rows, schema=OK)
  outputs/monitor/alerts/<YYYYMMDD>.jsonl

test_results:
  test_heartbeat: PASS (N tests)
  test_alerts: PASS (N tests)

fail_gates:
  missing_outputs: false
  test_failure: false
  schema_mismatch: false
  api_key_permission_violation: false
  secret_in_vcs: false
  core_module_modified: false

warning_gates:
  single_channel_only: true/false
  no_recovery_alert: true/false
  no_pnl_floor_check: true/false
  dedup_window_too_long: true/false
  heartbeat_interval_too_long: true/false

channels_implemented:
  - telegram: true/false
  - discord: true/false
  - smtp: true/false

heartbeat_sample:
  first_row: {timestamp, bot_id, status, latency_ms, equity_usd, ...}

reproducibility_hash: <sha256 of delivery log>

paper_execution_status: FORBIDDEN
live_trading_status: FORBIDDEN
```

---

## 15. NOTE 區

### NOTE-1：`apps/monitor/README.md` 必須涵蓋以下內容

1. **所需 VPS 環境**：Python ≥ 3.10、pip 套件（`requests`、`pyarrow`、`pyyaml`、`schedule`）
2. **Bybit API Key 設定**：只開 Read 權限、建議 IP whitelist 步驟
3. **Secret 設定**：`configs/monitor_secrets.yaml` 如何填寫（不含真實值的範本）
4. **啟動方式**：`python -m apps.monitor.monitor --config configs/monitor.yaml`
5. **Failure mode 說明**：
   - Monitor 自身掛掉 → 沒有告警（建議用 `systemd` 或 `supervisord` 守護 monitor process）
   - Telegram API 失敗 → 降級備用 channel
   - VPS 斷網 → heartbeat 失敗，但告警無法送達（需 secondary monitor 或 SMS 兜底）
6. **如何手動關閉 monitor**：`kill $(pgrep -f apps.monitor.monitor)` 或 `systemctl stop quantbot-monitor`
7. **不可做的事**：明示不提供下單介面、不自動 restart bot

### NOTE-2：與後續 Ollama 整合的設計預留

- `alerts/<YYYYMMDD>.jsonl` 格式設計為可直接被 Ollama prompt 讀取。
- `monitor.py` 預留 `--summarize` flag（輸出當日告警摘要文字），供 Ollama 消化用。
- 本任務**不實作** Ollama 整合；整合留給後續獨立任務（TASK-009 或同等命名）。

### NOTE-3：Paper Trading 關係

- TASK-005 上線後，30 天 forward paper record 才可開始可靠地累積。
- TASK-005 的 `heartbeat.parquet` 和 `alerts/` log 將作為 REVIEW-006b 評審時「forward record 完整性」的佐證材料之一。
- TASK-005 本身**不啟動 paper trading**、**不執行任何交易**。

### NOTE-4：完成後下一步

```
TASK-005 DONE (REVIEW_READY)
  → Claude REVIEW-005 (Sonnet 初審)
  → Opus REVIEW-005 final (如 Sonnet 判斷需要)
  → 上線 VPS（Rick 人工操作）
  → 30 天 forward paper record 開始累積
  → REVIEW-006b 啟動條件（3/3）：
      TASK-007b DONE ✓ (2026-05-17)
      Addenda ✓ (2026-05-17)
      30-day forward record ← 解鎖中
```

---

*工單 v1.0 | Claude Sonnet | 2026-05-17*
*範圍：建立監控基建工單；不含任何 paper/live trading 批准*
*本工單未批准 paper execution 或 live trading*
