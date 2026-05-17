# TASK-005a — Real Alert Channel

- **狀態**：TODO
- **Owner**：Codex
- **預估**：S（0.5–1 天）
- **依賴**：TASK-005 ✓ DONE（2026-05-17）；`apps/monitor/` 已存在
- **工單版本**：v1.0（2026-05-17，由 Claude Sonnet 撰寫）
- **觸發原因**：
  - REVIEW-005 PASS caveat — `single_channel_only` warning：目前 `configs/monitor.yaml` 只有 `local_jsonl (dry_run=true)`，無任何真實推播能力。
  - TASK-005a 是 paper execution 的前置條件之一（除非 Rick 明示豁免）。

---

## ⚠️ 執行閘門聲明

**本任務只新增通知 channel，不做任何交易行為。**

- 不可使用可下單的 API key（只准 read-only / IP-whitelisted key）。
- 不可修改 bot 本身的任何下單邏輯或策略程式。
- 不可啟動 paper trading 或 live trading。
- **不可要求 Rick 把 token / webhook URL 貼到聊天視窗**——secret 只能存在環境變數或 `configs/monitor_secrets.local.yaml`（gitignored）。
- 完成後狀態改為 `REVIEW`，等 Claude Sonnet 確認。

---

## 1. 任務一句話

在 TASK-005 已建好的 `apps/monitor/` 基礎上，接通至少一個真實外部推播 channel（Telegram Bot API 優先，Discord Webhook 備用），使 CRITICAL / WARNING 告警在 bot 出狀況時能即時送達 Rick，同時保留既有的 `local_jsonl` 寫入。

---

## 2. 任務目的

TASK-005 完成了監控基建：heartbeat、alerts JSONL、schema、safety scan、tests 全部 PASS。唯一缺口是通知 channel 只有本地 JSONL（`dry_run=true`）——bot 掛掉時，log 會記錄但 Rick 不會即時知道。

本任務補齊這個缺口：接通一個真實的外部推播 channel，讓「bot 三次心跳失敗」這類 CRITICAL 事件能在幾秒內送出通知。

---

## 3. 範圍邊界

### ✅ Do（允許做）

- 修改 `configs/monitor.yaml`：在 `channels` 列表中新增 Telegram 或 Discord 條目，並設 `dry_run: false`（生產模式）。
- 在 `apps/monitor/alerts.py`（或新增 `apps/monitor/channels/`）實作 channel dispatch 邏輯。
- 保留 `local_jsonl` channel 不變（兩個 channel 並存）。
- 實作 `--dry-run` flag：讀取 secret、構造 payload，但不實際發送（用於 CI / offline 測試）。
- 實作 `--test-send` flag：發送一筆測試告警到真實 channel，確認通道暢通。
- 補充 `tests/monitor/test_channels.py`：用 mock patch 測試 dispatch 邏輯（不需要真實 token）。
- 更新 `apps/monitor/README.md`：補充 channel 設定說明（如何填寫 `configs/monitor_secrets.local.yaml`）。

### ❌ Don't（禁止做）

- **不可**要求 Rick 把 Telegram token / Discord webhook URL 貼到聊天視窗。
- **不可**把任何 secret 硬編碼進程式碼或 YAML（必須從環境變數或 gitignored local config 讀取）。
- **不可**把 `configs/monitor_secrets.local.yaml` 從 `.gitignore` 移除（必須維持 gitignored）。
- **不可**修改 bot 下單邏輯、策略信號、ranking、universe 選擇。
- **不可**讓 monitor 取得可下單 API key。
- **不可**啟動 paper trading 或 live trading。
- **不可**修改 `outputs/`、`src/`、`apps/paper_trading/`、`docs/research/review_packets/` 下任何既有研究檔案。

---

## 4. 輸入

| 來源 | 說明 |
|---|---|
| `apps/monitor/`（既有）| TASK-005 交付的監控模組；`alerts.py`、`config.py` 等已存在 |
| `configs/monitor.yaml`（既有）| 目前有 `local_jsonl (dry_run=true)` 一個 channel |
| `configs/monitor_secrets.local.yaml`（gitignored，Rick 自行建立）| 含 Telegram token + chat_id，或 Discord webhook_url |
| 環境變數（備選）| `MONITOR_TELEGRAM_TOKEN`、`MONITOR_TELEGRAM_CHAT_ID` 或 `MONITOR_DISCORD_WEBHOOK_URL` |

### `configs/monitor_secrets.local.yaml` 範本（不含真實值）

```yaml
# gitignored — 不可進版控
telegram:
  token: ""         # Telegram Bot token（從 @BotFather 取得）
  chat_id: ""       # 目標 chat ID（個人或群組）

discord:
  webhook_url: ""   # Discord Webhook URL
```

**注意**：Codex 只提供此範本，**不可要求 Rick 在此範本以外的地方提供真實值**。Rick 在 VPS 上線時自行填入。

---

## 5. 輸出

| 路徑 | 說明 |
|---|---|
| `apps/monitor/alerts.py`（修改）| 新增 Telegram / Discord dispatch；保留 local_jsonl |
| `apps/monitor/channels/`（可選）| 若 dispatch 邏輯較複雜，可拆為 `telegram.py`、`discord.py` |
| `configs/monitor.yaml`（修改）| 新增 Telegram 或 Discord channel 條目（`dry_run: true` 預設，可改 false）|
| `configs/monitor_secrets.local.yaml.example`（新建）| 不含真實值的範本（可進版控，.example 副檔名）|
| `tests/monitor/test_channels.py`（新建）| mock patch 測試；不需要真實 token |
| `apps/monitor/README.md`（修改）| 補充 channel 設定說明 |
| `outputs/logs/prev3y_crypto/<YYYYMMDD>_monitor_channels_delivery.log`（新建）| 交付 log |

---

## 6. Channel 規格

### 優先實作：Telegram Bot API

| 項目 | 規格 |
|---|---|
| 端點 | `POST https://api.telegram.org/bot{token}/sendMessage` |
| Payload | `{"chat_id": "{chat_id}", "text": "{message}", "parse_mode": "Markdown"}` |
| Secret 來源 | 環境變數 `MONITOR_TELEGRAM_TOKEN` + `MONITOR_TELEGRAM_CHAT_ID`，或 `configs/monitor_secrets.local.yaml` |
| Timeout | 10 秒（避免 hang）|
| 失敗處理 | 記錄 error 到 `local_jsonl` + retry 1 次；retry 仍失敗 → 降級到備用 channel（若有）或只寫 log |
| `dry_run=true` 時 | 構造完整 payload，log 顯示「DRY_RUN: would send to Telegram」，**不實際 POST** |

### 備用實作（擇一）：Discord Webhook

| 項目 | 規格 |
|---|---|
| 端點 | `POST {webhook_url}` |
| Payload | `{"content": "{message}"}` |
| Secret 來源 | 環境變數 `MONITOR_DISCORD_WEBHOOK_URL`，或 `configs/monitor_secrets.local.yaml` |
| Timeout | 10 秒 |
| 失敗處理 | 同 Telegram |

### `configs/monitor.yaml` 新增欄位（範例）

```yaml
alerts:
  dedup_window_minutes: 30
  channels:
    - type: local_jsonl
      enabled: true
      dry_run: true       # 保留既有，不改
    - type: telegram
      enabled: true
      dry_run: true       # 預設 dry_run；VPS 上線時改為 false
      secrets_path: configs/monitor_secrets.local.yaml
      secrets_env_token: MONITOR_TELEGRAM_TOKEN
      secrets_env_chat_id: MONITOR_TELEGRAM_CHAT_ID
```

---

## 7. 訊息格式規格

Telegram / Discord 推播訊息格式（Markdown）：

```
[{severity}] {bot_name}
時間: {timestamp_utc} UTC
類型: {alert_type}
說明: {message}
動作: {action_required}
```

CRITICAL 告警在最前面加 `🔴`（或等效文字標記）；WARNING 加 `🟡`；INFO 不加前綴。

**注意**：若 Rick 偏好無 emoji，Codex 改用文字前綴 `[CRITICAL]`、`[WARNING]`、`[INFO]`。

---

## 8. 測試規格

### `tests/monitor/test_channels.py` 最低覆蓋

| 測試 | 說明 |
|---|---|
| `test_telegram_dry_run_does_not_post` | dry_run=true 時，mock `requests.post` 確認未被呼叫 |
| `test_telegram_live_send_calls_api` | dry_run=false 時，mock `requests.post` 確認被呼叫一次，payload 含 chat_id 和 text |
| `test_discord_dry_run_does_not_post` | 同上，Discord 版 |
| `test_channel_failure_falls_back_to_log` | POST 拋 exception → 確認 local_jsonl 仍寫入 error 記錄 |
| `test_dedup_prevents_double_send` | 同一 dedup_key 30 分鐘內不重複推播 |
| `test_no_secret_in_log_output` | 確認 log 輸出不含完整 token 字串 |

所有 test 使用 mock，不需要真實 Telegram token 或 Discord URL。

---

## 9. Fail Gates（完成後 Codex 自查）

以下任一觸發 → **FAIL**，不可進入 REVIEW：

| Gate | 觸發條件 |
|---|---|
| `test_failure` | `python -m unittest tests.monitor` 任一 FAIL |
| `secret_hardcoded` | 程式碼或 YAML 中含任何真實 token / webhook URL |
| `secret_in_vcs` | `configs/monitor_secrets.local.yaml`（含真實值）進入版控 |
| `order_submission_code_present` | monitor code 含任何 `place_order`、`POST /v5/order` 等禁止 token |
| `monitor_auto_restart_present` | monitor code 含 `auto_restart`、`restart_bot` 等禁止 token |
| `local_jsonl_removed` | 既有 `local_jsonl` channel 被移除（必須保留）|

## 10. Warning Gates（完成後 Codex 自查）

以下觸發 → WARNING，記錄於 delivery log，不擋 REVIEW：

| Gate | 觸發條件 |
|---|---|
| `only_one_channel` | 只實作 Telegram 或 Discord 其中一個（推薦兩個都實作但非必要）|
| `no_test_send_flag` | 未實作 `--test-send` flag |
| `readme_not_updated` | README 未補充 channel 設定說明 |
| `no_example_secrets_file` | 未提供 `configs/monitor_secrets.local.yaml.example` |

---

## 11. 禁止修改範圍

| 範圍 | 說明 |
|---|---|
| `src/` | 所有策略信號、ranking、universe 選擇程式 |
| `apps/paper_trading/` | Paper trading planning / simulation 模組 |
| `outputs/paper_trading/` | TASK-006 官方輸出 |
| `outputs/variants/` | TASK-007 / TASK-007b 官方輸出 |
| `outputs/attribution/` | TASK-003 attribution 官方輸出 |
| `outputs/backtest/` | run008 baseline 官方輸出 |
| `docs/research/review_packets/` | 所有 REVIEW PACKET / NUMBERS.json |
| `data/` / `raw/` | 原始市場資料 |

---

## 12. 完成後回報格式

Codex 完成後，輸出 `outputs/logs/prev3y_crypto/<YYYYMMDD>_monitor_channels_delivery.log`：

```
TASK-005a Real Alert Channel Delivery
run_date=<YYYYMMDD>
status=REVIEW_READY

channels_implemented:
  - local_jsonl: retained (dry_run=true)
  - telegram: true / false
  - discord: true / false

test_results:
  python -m unittest tests.monitor: PASS (N tests)

fail_gates:
  test_failure: false
  secret_hardcoded: false
  secret_in_vcs: false
  order_submission_code_present: false
  monitor_auto_restart_present: false
  local_jsonl_removed: false

warning_gates:
  only_one_channel: true/false
  no_test_send_flag: true/false
  readme_not_updated: true/false
  no_example_secrets_file: true/false

dry_run_verified: true
test_send_available: true/false

paper_execution_status: FORBIDDEN
live_trading_status: FORBIDDEN
```

---

## 13. NOTE 區

### NOTE-1：Secret 取得方式（Rick 操作，不在 Codex 範圍）

Codex **不可**要求 Rick 在聊天中提供任何 secret。Rick 在 VPS 部署時自行：

1. **Telegram**：從 `@BotFather` 建立 Bot，取得 token；對 Bot 發訊息後用 `getUpdates` API 查 chat_id。
2. **Discord**：在 Discord channel 設定 → Integrations → Webhooks → 建立 Webhook，複製 URL。
3. 把 token / URL 填入 VPS 上的 `configs/monitor_secrets.local.yaml`，或設為 VPS 環境變數。

### NOTE-2：dry_run 預設值

`configs/monitor.yaml` 中新增 channel 的 `dry_run` 預設設為 `true`。VPS 上線時 Rick 改為 `false`。這樣即使 `configs/monitor.yaml` 進版控，也不會意外在 local 環境發出真實通知。

### NOTE-3：Paper Execution Gate

TASK-005a DONE 後，「TASK-005 VPS monitor online」前置條件才算完整滿足（DONE + 真實推播 channel 可用）。

Paper execution 仍需等所有條件齊備：
- TASK-005a DONE ← 本任務
- TASK-005 VPS 實際部署上線（Rick 人工操作）
- 30 天 forward paper record（Sharpe > 0.5）
- Opus REVIEW-006b PASS
- Rick 明示批准

### NOTE-4：完成後下一步

```
TASK-005a DONE (REVIEW_READY)
  → Claude REVIEW-005a (Sonnet 確認)
  → Rick 在 VPS 上部署 + 填入真實 secret
  → configs/monitor.yaml telegram.dry_run: false
  → --test-send 確認推播正常
  → TASK-005 VPS monitor 上線條件滿足
  → 30 天 forward paper record 可開始累積
```

---

*工單 v1.0 | Claude Sonnet | 2026-05-17*
*範圍：新增推播 channel；不含任何 paper/live trading 批准*
*本工單未批准 paper execution 或 live trading*
