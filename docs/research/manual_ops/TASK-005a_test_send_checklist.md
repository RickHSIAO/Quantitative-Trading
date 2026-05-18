# TASK-005a — Real --test-send 手動操作清單

**操作者：** Rick（只有 Rick 可執行此步驟）
**目的：** 驗證至少 1 個外部 alert channel（Telegram 或 Discord）可在真實環境發出訊息
**前置條件：** TASK-005a DONE，REVIEW-005a PASS
**Paper Execution Gate：** 此操作完成並存檔後，paper execution 前置條件 +1（共 5/7）
**更新時間：** 2026-05-17

---

## ⚠️ 操作安全規則

- **不得在聊天視窗貼 token 或 webhook URL**（AI agent 規則）
- **只需完成 Telegram 或 Discord 其中一個即可**通過此 gate（建議先做 Telegram）
- 測試前後 `configs/monitor.yaml` 的 `dry_run` 必須還原為 `true`
- 測試結果存檔前必須遮蔽敏感值
- `configs/monitor_secrets.local.yaml` 是 gitignored，不要手動 git add 它

---

## 前置準備

### 確認 .gitignore 保護

```powershell
# 在專案根目錄執行，確認 gitignore 有保護 local secrets
Select-String -Path ".gitignore" -Pattern "monitor_secrets"
```

預期輸出（4 行）：
```
configs/monitor_secrets.yaml
configs/monitor_secrets.yml
configs/monitor_secrets.local.yaml
configs/monitor_secrets.local.yml
```

如果少於 4 行，**停止操作，先修復 .gitignore**。

---

## Path A：Telegram

### A1. 取得 Telegram Bot Token 與 Chat ID

前往 Telegram，在私訊或群組中確認你的 Bot Token 與 Chat ID。

**方法（二選一）：**
- 環境變數（推薦）：不建立 local yaml，直接設環境變數
- Local YAML 檔：建立 `configs/monitor_secrets.local.yaml`

---

### 方法 1：環境變數方式（Telegram）

```powershell
# 在 PowerShell 中暫時設定環境變數（本次 session 有效）
$env:MONITOR_TELEGRAM_TOKEN = "你的bot_token"
$env:MONITOR_TELEGRAM_CHAT_ID = "你的chat_id"

# 確認已設定（值不顯示在螢幕上的安全版）
[System.Environment]::GetEnvironmentVariable("MONITOR_TELEGRAM_TOKEN") -ne ""
[System.Environment]::GetEnvironmentVariable("MONITOR_TELEGRAM_CHAT_ID") -ne ""
# 兩個都應輸出 True
```

---

### 方法 2：Local YAML 方式（Telegram）

參考 `configs/monitor_secrets.example.yaml` 建立真實 secrets 檔：

```powershell
# 複製 example 再填入真實值
Copy-Item configs\monitor_secrets.example.yaml configs\monitor_secrets.local.yaml

# 用你偏好的編輯器開啟並填入真實值
# 格式：
# telegram:
#   token: "填入真實 bot token"
#   chat_id: "填入真實 chat id"
# discord:
#   webhook_url: ""
```

---

### A2. 暫時開啟 Telegram 的 dry_run=false

編輯 `configs/monitor.yaml`，將 telegram channel 的 `dry_run: true` 改為 `false`：

```yaml
# 改前
    - type: telegram
      enabled: true
      dry_run: true         # ← 改這行
      ...

# 改後（測試期間）
    - type: telegram
      enabled: true
      dry_run: false        # ← 測試完立刻改回 true
      ...
```

---

### A3. 執行 --test-send

```powershell
# 在專案根目錄執行（啟動 .venv）
.venv\Scripts\Activate.ps1

# 執行 test-send（替換日期為今天）
python scripts\task005_vps_bot_monitor.py --test-send --output-date 20260517
```

**預期輸出（Telegram channel 部分）：**
```json
{
  "channel": "telegram",
  "dry_run": false,
  "external_post_attempted": true,
  "status": "SENT",
  "test_send": true
}
```

確認 Telegram 手機收到訊息。

---

### A4. 立刻還原 dry_run=true

```yaml
# configs/monitor.yaml — 立刻改回
    - type: telegram
      enabled: true
      dry_run: true         # ← 還原
```

---

### A5. 存檔遮蔽後的證據

```powershell
# 建立目錄
New-Item -ItemType Directory -Force -Path "outputs\monitor\test_send"

# 儲存遮蔽版輸出（手動把輸出中的 token 換成 <redacted>）
# 範本指令（將指令輸出導至檔案）
python scripts\task005_vps_bot_monitor.py --test-send --output-date 20260517 |
    ForEach-Object { $_ -replace 'bot[A-Za-z0-9_:-]+', 'bot<redacted>' } |
    Out-File -FilePath "outputs\monitor\test_send\20260517_telegram_proof.txt" -Encoding UTF8
```

**若自動遮蔽不完整，請手動開啟 `outputs\monitor\test_send\20260517_telegram_proof.txt` 確認：**
- `token` 欄位不應含真實 token
- `endpoint` 不應含 `bot123456:ABC...` 格式的字串
- `chat_id` 可保留（非 secret，但若要保守也可以遮蔽）

---

## Path B：Discord

### B1. 取得 Discord Webhook URL

在 Discord Server → Channel Settings → Integrations → Webhooks → 新增或複製已有的 Webhook URL。

格式：`https://discord.com/api/webhooks/1234567890/xxxxxxxxxxxxxxxx`

---

### 方法 1：環境變數方式（Discord）

```powershell
$env:MONITOR_DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/你的webhook_url"

# 確認
[System.Environment]::GetEnvironmentVariable("MONITOR_DISCORD_WEBHOOK_URL") -ne ""
# 應輸出 True
```

---

### 方法 2：Local YAML 方式（Discord）

```yaml
# configs/monitor_secrets.local.yaml
telegram:
  token: ""
  chat_id: ""
discord:
  webhook_url: "https://discord.com/api/webhooks/你的webhook_url"
```

---

### B2. 暫時開啟 Discord 的 dry_run=false

```yaml
# configs/monitor.yaml
    - type: discord
      enabled: true
      dry_run: false        # ← 測試完立刻改回 true
      ...
```

---

### B3. 執行 --test-send

```powershell
python scripts\task005_vps_bot_monitor.py --test-send --output-date 20260517
```

**預期輸出（Discord channel 部分）：**
```json
{
  "channel": "discord",
  "dry_run": false,
  "external_post_attempted": true,
  "status": "SENT",
  "test_send": true
}
```

確認 Discord 頻道收到訊息。

---

### B4. 立刻還原 dry_run=true

```yaml
    - type: discord
      enabled: true
      dry_run: true         # ← 還原
```

---

### B5. 存檔遮蔽後的證據

```powershell
New-Item -ItemType Directory -Force -Path "outputs\monitor\test_send"

python scripts\task005_vps_bot_monitor.py --test-send --output-date 20260517 |
    ForEach-Object { $_ -replace 'webhooks/[0-9]+/[A-Za-z0-9_-]+', 'webhooks/<redacted>' } |
    Out-File -FilePath "outputs\monitor\test_send\20260517_discord_proof.txt" -Encoding UTF8
```

手動確認 `outputs\monitor\test_send\20260517_discord_proof.txt` 中：
- `webhook_url` 欄位不含完整 webhook URL
- `endpoint` 顯示為 `https://discord.com/api/webhooks/<redacted>` 或類似遮蔽格式

---

## 最終確認清單

執行完成後，逐一確認以下項目（全部 ✅ 才算通過）：

| 項目 | 確認 |
|---|---|
| 手機 / Discord 頻道實際收到訊息 | ☐ |
| 輸出中 `external_post_attempted: true` | ☐ |
| 輸出中 `status: "SENT"` | ☐ |
| `configs/monitor.yaml` 的 `dry_run` 已全部還原為 `true` | ☐ |
| `configs/monitor_secrets.local.yaml` **未被** `git add` | ☐ |
| 証據檔存至 `outputs/monitor/test_send/<YYYYMMDD>_<channel>_proof.txt` | ☐ |
| 証據檔中 token / webhook URL 已遮蔽 | ☐ |

確認 `configs/monitor.yaml` 已還原：
```powershell
Select-String -Path "configs\monitor.yaml" -Pattern "dry_run"
```
所有行應顯示 `dry_run: true`。

確認 secrets 未進入 git：
```powershell
git status configs\monitor_secrets.local.yaml
```
應顯示 `ignored` 或 `nothing to commit`（不應出現在 staged 或 modified）。

---

## 完成後通知 AI Agent

執行完畢後，告訴 Claude（Sonnet 即可）：

> TASK-005a test-send 完成。使用 \<channel\>（Telegram / Discord）。證據存於 `outputs/monitor/test_send/<YYYYMMDD>_<channel>_proof.txt`。

Claude 將更新 `CODEX_TASK_QUEUE.md` 中 Rick test-send gate 狀態，paper execution gate 進展至 5/7。

---

## 常見錯誤排除

**`status: "FAILED"` + `detail: "missing Telegram token or chat id"`**
→ 環境變數未正確設定，或 secrets 檔路徑錯誤。確認 `$env:MONITOR_TELEGRAM_TOKEN` 不為空。

**`status: "DRY_RUN"` 而非 `SENT`**
→ `configs/monitor.yaml` 的 `dry_run` 仍為 `true`。必須改為 `false` 才能實際發送。

**Telegram Bot 沒有加入你的 chat**
→ 在 Telegram 搜尋你的 bot 名稱，先傳一條訊息給它，再取得 chat_id。

**Discord 403 Forbidden**
→ Webhook URL 已失效或被刪除，重新在 Discord 建立一個新的 Webhook。

**Python import error**
→ 確認已啟動 `.venv`：`.venv\Scripts\Activate.ps1`
