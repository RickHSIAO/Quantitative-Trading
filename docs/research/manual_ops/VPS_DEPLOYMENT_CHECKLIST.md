# VPS Deployment Checklist

**文件狀態：** 操作清單（Operational Checklist）
**版本：** v1.0
**建立日期：** 2026-05-17
**建立者：** Claude Sonnet
**前置文件：**
- `docs/research/manual_ops/30_day_forward_start_checklist.md`
- `docs/research/manual_ops/TASK-005a_test_send_checklist.md`
- `docs/research/manual_ops/30_day_forward_record_plan.md`

---

## ⛔ 核心聲明（每次使用前必讀）

- **本清單不授權 paper execution。**
- **本清單不授權 live trading。**
- VPS 上只可配置 **read-only** 的 Bybit API key。下單 endpoint 永遠不得連接。
- Paper execution 在 Opus **REVIEW-006b PASS** + **Rick 明示批准** 之前，永遠 FORBIDDEN。
- Live trading 在另一輪專屬 Opus review + Rick 明示批准之前，永遠 FORBIDDEN。
- **不要把 API key 或 webhook URL 貼到任何 Git commit、任何聊天紀錄、任何 Claude 對話。**

---

## 使用說明

本清單分為 **Phase 1–8**，按順序執行，每項完成後打 `[x]`。
最後 **Phase 9** 是完成後回報給 Claude / Codex 的記錄步驟。

各 Phase 皆獨立可暫停；但 **Phase 5（test-send）通過前不得進入 Phase 6**，
**Phase 6（dry-run 通過）之前不得啟動 30-day clock**。

---

## Phase 1 — VPS OS / Python / Repo 基礎建設

### 1.1 OS 基本確認

```bash
# 建議：Ubuntu 22.04 LTS（或 Debian 12）
uname -a
# 確認 Python 版本 >= 3.10
python3 --version
# 確認時區設為 UTC
timedatectl | grep "Time zone"
# 若非 UTC，執行：
sudo timedatectl set-timezone UTC
```

```
[ ] OS 版本符合（Ubuntu 22.04 / Debian 12）
[ ] Python >= 3.10 確認
[ ] 時區 = UTC 確認
[ ] 磁碟空間充足（建議至少 20 GB 可用）
[ ] 系統時間與 NTP 同步（`timedatectl | grep synchronized`）
```

### 1.2 建立專用使用者（建議，非必須）

```bash
# 建立非 root 使用者（避免以 root 直接運行策略）
sudo adduser quantbot
sudo usermod -aG sudo quantbot
su - quantbot
```

```
[ ] 以非 root 使用者運行（或確認已知風險）
```

### 1.3 Clone / 同步 Repo

```bash
# 方法 A：Git clone（若有 remote）
git clone <repo_url> ~/量化交易
cd ~/量化交易
git checkout main
git log --oneline -5   # 確認版本

# 方法 B：rsync 從本機（若無 remote）
# Rick 在本機執行：
# rsync -avz --exclude '.venv' --exclude '__pycache__' \
#   F:\RickHSIAO\Python\量化交易\ quantbot@<VPS_IP>:~/量化交易/
```

```
[ ] Repo 已同步至 VPS（確認 git log 或 rsync 無錯誤）
[ ] 工作目錄確認：~/量化交易/
[ ] .gitignore 確認 configs/monitor_secrets.local.yaml 在排除清單中（不上傳 secret）
[ ] outputs/ 目錄存在或可建立
```

**確認 .gitignore 必須排除的敏感檔案：**
```bash
grep "monitor_secrets.local" ~/量化交易/.gitignore
# 應出現此行，若無則手動加入：
echo "configs/monitor_secrets.local.yaml" >> ~/量化交易/.gitignore
```

```
[ ] monitor_secrets.local.yaml 已確認在 .gitignore
```

---

## Phase 2 — Python 虛擬環境 / Dependency Install

### 2.1 建立虛擬環境

```bash
cd ~/量化交易
python3 -m venv .venv
source .venv/bin/activate
which python   # 應顯示 ~/量化交易/.venv/bin/python
```

```
[ ] 虛擬環境建立成功
[ ] activate 後 python 指向 venv 內
```

### 2.2 安裝 Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**requirements.txt 關鍵套件（截至 2026-05-17）：**

| 套件 | 最低版本 | 用途 |
|---|---|---|
| pandas | >= 2.0.3 | 資料處理 |
| numpy | >= 1.24.0 | 數值計算 |
| pybit | >= 5.6.0 | Bybit API（read-only 市場資料）|
| requests | >= 2.31.0 | Discord webhook / Telegram API |
| python-dotenv | >= 1.0.0 | .env 檔載入 |
| pyarrow | >= 24.0.0 | parquet 讀寫 |
| scipy | >= 1.11.4 | 統計計算 |
| yfinance | >= 0.2.40 | 補充行情（備用）|

```bash
# 驗證關鍵套件
python -c "import pandas, numpy, pybit, requests, dotenv, pyarrow, scipy; print('OK')"
```

```
[ ] pip install 無錯誤
[ ] 關鍵套件 import 驗證 OK
[ ] 無 version conflict 警告（若有，記錄並確認不影響核心功能）
```

### 2.3 專案 Module 可 Import 驗證

```bash
cd ~/量化交易
python -c "from apps.monitor.config import MonitorConfig; print('monitor OK')"
python -c "from apps.monitor.channels.discord import DiscordChannel; print('discord OK')"
python -c "from src.signals.prev3y_momentum import build_prev3y_targets; print('signal OK')"
python -c "from src.variants.task008 import apply_alpha_contribution_cap; print('task008 OK')"
```

```
[ ] apps.monitor import OK
[ ] apps.monitor.channels.discord import OK
[ ] src.signals.prev3y_momentum import OK
[ ] src.variants.task008 import OK（shadow-track 用）
```

---

## Phase 3 — Read-Only Bybit API 設定

### 3.1 API Key 類型確認（重要）

```
[ ] API Key 類型 = READ ONLY（Bybit 控制台確認）
[ ] API Key 無下單（Order）權限
[ ] API Key 無提幣（Withdrawal）權限
[ ] API Key 無轉帳（Transfer）權限
[ ] IP 白名單已設定為 VPS IP（建議）
```

> ⚠️ **不要把 API key 貼到聊天、Git commit 或任何共享空間。**
> 只在 VPS terminal 中直接操作（見 §3.2）。

### 3.2 設定方式

**方法 A：環境變數（推薦，最安全）**

```bash
# 加入 ~/.bashrc 或 ~/.profile（只在 VPS 本地保存）
echo 'export BYBIT_API_KEY="your_key_here"'    >> ~/.bashrc
echo 'export BYBIT_API_SECRET="your_secret_here"' >> ~/.bashrc
source ~/.bashrc

# 驗證（只顯示前 4 碼，不顯示完整 key）
python -c "import os; k=os.environ.get('BYBIT_API_KEY',''); print('Key prefix:', k[:4] if k else 'NOT SET')"
```

**方法 B：.env 檔（備用）**

```bash
# 在 ~/量化交易/ 下建立（確認在 .gitignore 中）
cat > ~/量化交易/.env << 'EOF'
BYBIT_API_KEY=your_key_here
BYBIT_API_SECRET=your_secret_here
EOF
chmod 600 ~/量化交易/.env
```

```bash
# 確認 .env 在 .gitignore
grep "^\.env$" ~/量化交易/.gitignore || echo ".env" >> ~/量化交易/.gitignore
```

### 3.3 Read-Only 連線驗證

```bash
cd ~/量化交易
source .venv/bin/activate
python - << 'EOF'
from pybit.unified_trading import HTTP
import os
session = HTTP(
    api_key=os.environ.get("BYBIT_API_KEY"),
    api_secret=os.environ.get("BYBIT_API_SECRET"),
    testnet=False
)
# 只用 read-only endpoint（取 ticker，無寫入）
result = session.get_tickers(category="linear", symbol="BTCUSDT")
print("Status:", result["retCode"])  # 應為 0
print("BTC last price:", result["result"]["list"][0]["lastPrice"])
print("READ-ONLY connection OK")
EOF
```

```
[ ] retCode = 0（連線成功）
[ ] 可讀取市場資料
[ ] 未使用任何寫入 endpoint
[ ] API key 未出現在 terminal 輸出或 log 中
```

---

## Phase 4 — Discord Alert Secret 設定

### 4.1 Secret 設定方式

**方法 A：環境變數（推薦）**

```bash
echo 'export MONITOR_DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."' >> ~/.bashrc
source ~/.bashrc

# 驗證（顯示 URL 前段，不顯示完整）
python -c "import os; u=os.environ.get('MONITOR_DISCORD_WEBHOOK_URL',''); print('URL set:', bool(u), '| prefix:', u[:35] if u else 'NOT SET')"
```

**方法 B：configs/monitor_secrets.local.yaml（備用）**

```bash
# 參考 configs/monitor_secrets.example.yaml 建立本地版本
cp ~/量化交易/configs/monitor_secrets.example.yaml \
   ~/量化交易/configs/monitor_secrets.local.yaml
chmod 600 ~/量化交易/configs/monitor_secrets.local.yaml

# 手動編輯填入 webhook（不在此顯示）：
# discord:
#   webhook_url: "https://discord.com/api/webhooks/..."
```

```bash
# 確認 monitor_secrets.local.yaml 在 .gitignore
grep "monitor_secrets.local" ~/量化交易/.gitignore \
  || echo "configs/monitor_secrets.local.yaml" >> ~/量化交易/.gitignore
```

### 4.2 monitor.yaml 設定確認

`configs/monitor.yaml` 的預設值（**不得**在沒有 test-send 驗證前改動）：

```yaml
alerts:
  channels:
    - type: discord
      enabled: true
      dry_run: true          # ← 預設 true；Phase 5 test-send 時臨時改為 false，驗證後立即還原
      secrets_env_webhook_url: MONITOR_DISCORD_WEBHOOK_URL
```

```
[ ] monitor_secrets.local.yaml 已建立，webhook_url 已填入（不貼入聊天）
[ ] .gitignore 確認 monitor_secrets.local.yaml 排除
[ ] monitor.yaml discord dry_run 目前 = true（正常狀態）
[ ] Telegram 若不使用：enabled: false 確認
```

---

## Phase 5 — Monitor Test-Send 驗證

> **參考**：`docs/research/manual_ops/TASK-005a_test_send_checklist.md`
> 本 Phase 是該清單在 VPS 上的執行確認。

### 5.1 Pre-Check

```bash
cd ~/量化交易
source .venv/bin/activate

# 確認 monitor_secrets.local.yaml 存在
ls -la configs/monitor_secrets.local.yaml

# 確認 dry_run 目前 = true
grep "dry_run" configs/monitor.yaml
```

```
[ ] monitor_secrets.local.yaml 存在
[ ] monitor.yaml discord dry_run = true（執行前狀態）
```

### 5.2 執行 Test-Send

```bash
# Step 1：臨時將 discord dry_run 改為 false
#   在 configs/monitor.yaml 中，將 discord 的 dry_run: true 改為 dry_run: false
#   （只改 discord 那一條；local_jsonl 和 telegram 不動）

# Step 2：執行 test-send
python scripts/task005_vps_bot_monitor.py --config configs/monitor.yaml --test-send

# Step 3：立即還原 dry_run: true
#   改回 configs/monitor.yaml discord dry_run: true
```

> ⚠️ **dry_run 必須在 test-send 後立即還原。不得讓 dry_run: false 殘留在 configs/monitor.yaml。**

### 5.3 驗證 Test-Send 成功

```bash
# 1. 檢查 proof 檔案
ls outputs/monitor/test_send/
cat outputs/monitor/test_send/<YYYYMMDD>_discord_proof.txt | python -m json.tool

# 2. 確認關鍵欄位
python - << 'EOF'
import json
from pathlib import Path
files = sorted(Path("outputs/monitor/test_send").glob("*_discord_proof.txt"))
if not files:
    print("ERROR: no proof file found")
else:
    data = json.loads(files[-1].read_text())
    assert data.get("status") == "SENT", f"Expected SENT, got {data.get('status')}"
    assert data.get("external_post_attempted") == True
    assert data.get("dry_run_restored_after_test") == True
    assert "REDACTED" in str(data.get("webhook_url", ""))
    assert data.get("paper_execution_status") == "FORBIDDEN"
    assert data.get("live_trading_status") == "FORBIDDEN"
    print("All assertions PASS — test-send verified")
EOF
```

```
[ ] Discord 頻道收到測試訊息（人工確認）
[ ] proof 檔案存在且 status = SENT
[ ] external_post_attempted = true
[ ] dry_run_restored_after_test = true
[ ] webhook_url = REDACTED（proof 中不含明文）
[ ] paper_execution_status = FORBIDDEN
[ ] live_trading_status = FORBIDDEN
[ ] monitor.yaml discord dry_run 已還原為 true
```

---

## Phase 6 — Forward Record Dry-Run 驗證

> 在啟動 30-day clock 之前，先跑一次 dry-run，確認輸出格式正確、無 import 錯誤、無路徑問題。

### 6.1 建立輸出目錄

```bash
cd ~/量化交易
mkdir -p outputs/forward_record/prev3y_crypto
mkdir -p outputs/forward_record/prev3y_crypto_shadow_a_roll12   # 若啟用 shadow-track
mkdir -p outputs/logs/prev3y_crypto
```

```
[ ] outputs/forward_record/prev3y_crypto/ 目錄已建立
[ ] outputs/logs/prev3y_crypto/ 目錄已建立
```

### 6.2 Forward Record Dry-Run

> **注意**：forward record runner script 可能尚未建立（TASK-009 或 Codex 任務）。
> 若 runner 已建立，執行以下步驟；若未建立，此 Phase 暫緩至 runner 完成後。

```bash
# 確認 runner 存在（路徑待 Codex 確認）
ls scripts/run_forward_record.py 2>/dev/null || echo "Runner not yet created — Phase 6 deferred"
```

**若 runner 已存在，執行：**

```bash
python scripts/run_forward_record.py \
  --config configs/prev3y_crypto.yaml \
  --dry-run \
  --date $(date -u +%Y%m%d) \
  --output-dir outputs/forward_record/prev3y_crypto/

# 驗證輸出
python - << 'EOF'
import json
from pathlib import Path
import datetime
today = datetime.datetime.utcnow().strftime("%Y%m%d")
base = Path("outputs/forward_record/prev3y_crypto")
required = [f"{today}_positions.parquet", f"{today}_pnl.json", f"{today}_overlay_check.json"]
for f in required:
    p = base / f
    assert p.exists(), f"MISSING: {f}"
    if f.endswith(".json"):
        data = json.loads(p.read_text())
        assert data.get("paper_execution_status") == "FORBIDDEN", f"FORBIDDEN flag missing in {f}"
        assert data.get("live_trading_status") == "FORBIDDEN", f"FORBIDDEN flag missing in {f}"
print("Dry-run output validation PASS")
EOF
```

```
[ ] runner 存在（或 Phase 6 標記為 DEFERRED 待 TASK-009）
[ ] dry-run 無 import 錯誤
[ ] 輸出目錄下產生 _positions.parquet / _pnl.json / _overlay_check.json
[ ] 每個 JSON 含 paper_execution_status = FORBIDDEN
[ ] 每個 JSON 含 live_trading_status = FORBIDDEN
[ ] forward_summary.json 產生（或 DEFERRED）
```

### 6.3 Safety Check

```bash
# 確認沒有任何 Bybit 寫入 endpoint 被呼叫
grep -r "place_order\|submit_order\|create_order\|post_order\|cancel_order" \
  scripts/run_forward_record.py apps/paper_trading/ 2>/dev/null \
  && echo "WARNING: order endpoint found" || echo "OK: no order endpoints detected"
```

```
[ ] Safety grep 確認無下單 endpoint（或 DEFERRED）
```

---

## Phase 7 — Daily Run / Cron / Log 路徑確認

### 7.1 路徑結構確認

```bash
cd ~/量化交易

# 必要輸出目錄
mkdir -p outputs/forward_record/prev3y_crypto
mkdir -p outputs/monitor/prev3y_crypto/alerts
mkdir -p outputs/logs/prev3y_crypto
mkdir -p outputs/monitor/test_send

# 確認
ls -la outputs/
```

**完整路徑對照表：**

| 類型 | 路徑 | 說明 |
|---|---|---|
| Forward record（primary） | `outputs/forward_record/prev3y_crypto/` | 每日持倉 / PnL / overlay check |
| Forward record（shadow） | `outputs/forward_record/prev3y_crypto_shadow_a_roll12/` | shadow-track（可選）|
| Monitor heartbeat | `outputs/monitor/prev3y_crypto/` | `configs/monitor.yaml` output_heartbeat |
| Monitor alerts | `outputs/monitor/prev3y_crypto/alerts/` | `configs/monitor.yaml` output_alerts_dir |
| Runner log | `outputs/logs/prev3y_crypto/` | `configs/monitor.yaml` output_log_dir |
| Test-send proof | `outputs/monitor/test_send/` | Phase 5 proof 檔 |

### 7.2 Cron Job 設定（Daily Runner）

> **注意**：cron 設定在 30-day clock 正式啟動當天才開啟，不是現在。
> 以下是 cron 格式範本，供 Rick 在 start-date 當天複製使用。

```bash
# 編輯 cron（在 start-date 當天執行）
crontab -e

# 建議排程（UTC 00:10，市場資料可用後）
# Forward record runner（每日）
10 0 * * * cd ~/量化交易 && source .venv/bin/activate && \
  python scripts/run_forward_record.py \
    --config configs/prev3y_crypto.yaml \
    --date $(date -u +\%Y\%m\%d) \
    >> outputs/logs/prev3y_crypto/cron_forward.log 2>&1

# Monitor runner（每分鐘）
* * * * * cd ~/量化交易 && source .venv/bin/activate && \
  python scripts/task005_vps_bot_monitor.py \
    --config configs/monitor.yaml \
    >> outputs/logs/prev3y_crypto/cron_monitor.log 2>&1
```

```
[ ] 輸出目錄全部建立完成
[ ] Cron 格式已理解（start-date 當天才實際啟用）
[ ] Log 路徑與 monitor.yaml 設定一致
```

### 7.3 Log Rotation（可選但建議）

```bash
# 避免 log 無限增大（建議安裝 logrotate）
sudo tee /etc/logrotate.d/quantbot << 'EOF'
/home/quantbot/量化交易/outputs/logs/prev3y_crypto/*.log {
    daily
    rotate 90
    compress
    missingok
    notifempty
}
EOF
```

```
[ ] Log rotation 已設定（或明確接受不設定）
```

---

## Phase 8 — 安全檢查（Security Review）

### 8.1 Secret 安全確認

```bash
# 確認 .gitignore 包含所有 secret 檔案
cat ~/量化交易/.gitignore | grep -E "secrets|\.env|\.key"
```

**必須在 .gitignore 的檔案：**
```
[ ] configs/monitor_secrets.local.yaml
[ ] .env（若使用）
[ ] *.key、*.pem、*.p12（任何 key 檔）
```

### 8.2 API Key 權限二次確認

```bash
# 在 Bybit 控制台（瀏覽器）確認 API key 設定：
# - 帳戶類型：Unified Account 或 Contract
# - 權限清單：僅「讀取」
#   ✓ 允許：Read Position、Read Order、Read Market Data
#   ✗ 不允許：Trade、Withdrawal、Transfer、Sub-account
# - IP 限制：設為 VPS 的固定 IP（強烈建議）
```

```
[ ] Bybit API key 權限：僅 Read（Bybit 控制台二次確認）
[ ] IP 白名單：VPS IP 已設定
[ ] 無 Trade / Withdrawal / Transfer 權限
```

### 8.3 策略程式碼完整性確認

```bash
# 確認策略主流程未被修改（md5/sha256 或 git diff）
cd ~/量化交易
git diff HEAD src/signals/prev3y_momentum.py
# 應顯示空白（無修改）
git diff HEAD src/variants/task008.py
# task008.py 應只含 Codex 添加的 apply_alpha_contribution_cap
```

```
[ ] src/signals/prev3y_momentum.py 未修改（git diff 乾淨）
[ ] run008 / TASK-002 / TASK-003 / TASK-007 / TASK-008 官方輸出未被覆蓋
[ ] data/ 目錄未被修改
```

### 8.4 Port / Firewall 確認

```bash
# 確認 VPS 沒有不必要的開放 port
sudo ss -tlnp | grep LISTEN
# 策略 runner 不需要 inbound port；只有 outbound（Discord webhook / Bybit read API）
```

```
[ ] 無不必要的 inbound port 開放
[ ] 無 web server 在策略用 VPS 上運行（除非刻意設計）
[ ] Outbound：只有 443（HTTPS）到 Bybit API + Discord
```

---

## Phase 9 — 完成後通知 Claude / Codex 記錄

VPS 部署完成後，Rick 在聊天中指示 Claude 更新記錄。

### 9.1 Rick 通知 Claude 的訊息格式（複製修改後使用）

```
【VPS 部署完成通知】
部署日期：YYYY-MM-DD
VPS Provider：_______________
OS：Ubuntu 22.04 / Debian 12 / 其他：___
Python：3.x.x
Phase 完成：
  - Phase 1 OS/Repo: ✅
  - Phase 2 Dependencies: ✅
  - Phase 3 Bybit Read-Only API: ✅
  - Phase 4 Discord Secret: ✅
  - Phase 5 Test-Send: ✅
  - Phase 6 Forward Record Dry-Run: ✅ / DEFERRED（runner 未建立）
  - Phase 7 Cron/Log Path: ✅（cron 待 start-date 啟用）
  - Phase 8 Security: ✅
Proof 檔案：outputs/monitor/test_send/<YYYYMMDD>_discord_proof.txt（已存在）
30-day clock start-date（若已決定）：YYYY-MM-DD / 尚未決定
Shadow-track 啟用：是 / 否
備注：_______________
```

### 9.2 Claude 收到通知後執行的步驟

Claude 收到以上通知後（需 Rick 明示指示），執行：

1. 更新 `docs/research/manual_ops/30_day_forward_start_checklist.md` §0 的 VPS 部署狀態 → ✅
2. 更新 `docs/research/commands/NEXT_ACTION.md`（若 start-date 已指定，列為 Option A READY）
3. 更新 `docs/research/commands/COMMAND_LOG.md`
4. Paper execution gate 計數更新（若 Phase 6 通過，6/7 → 7/7 仍需 REVIEW-006b + Rick 批准）

> **Claude 不得自行宣告 30-day clock 啟動。clock 啟動需 Rick 明示「開始計時」指令。**

---

## Phase 完成狀態總表

| Phase | 說明 | 狀態 |
|---|---|---|
| Phase 1 | OS / Python / Repo | ⬜ 待執行 |
| Phase 2 | Dependencies | ⬜ 待執行 |
| Phase 3 | Bybit Read-Only API | ⬜ 待執行 |
| Phase 4 | Discord Secret | ⬜ 待執行 |
| Phase 5 | Monitor Test-Send | ⬜ 待執行 |
| Phase 6 | Forward Record Dry-Run | ⬜ DEFERRED（runner 待 TASK-009）|
| Phase 7 | Daily Run / Log Path | ⬜ 待執行 |
| Phase 8 | Security Review | ⬜ 待執行 |
| Phase 9 | 通知 Claude 記錄 | ⬜ 待 Phase 1–8 完成後執行 |

**30-day clock 啟動條件：Phase 1–5 + Phase 7–8 全部 ✅，Phase 6 已驗證或 runner 已上線。**

---

## 禁止事項（Red Lines）

```
❌ 不得在 VPS 上設置任何交易所的「下單 / Trade」API 權限
❌ 不得連接 Bybit order endpoint（POST /v5/order/create 或任何下單路徑）
❌ 不得連接 demo / testnet 帳戶的下單 endpoint
❌ 不得提交任何委託單（paper 或 live）
❌ 不得宣稱 paper execution 已批准（需 REVIEW-006b PASS + Rick 明示）
❌ 不得宣稱 live trading 已批准（需另一輪 Opus review + Rick 明示）
❌ 不得把 API key / webhook URL 貼到聊天、Git commit、任何 Claude 對話
❌ 不得修改 src/signals/prev3y_momentum.py（策略主流程）
❌ 不得修改 run008 / TASK-002 / TASK-003 / TASK-007 / TASK-008 官方輸出
❌ 不得在沒有 Rick 明示「開始計時」前啟動 30-day clock
```

---

## 版本紀錄

| 版本 | 日期 | 說明 |
|---|---|---|
| v1.0 | 2026-05-17 | 初版，Claude Sonnet |

---

*本清單不授權任何 paper execution 或 live trading。*
*所有執行授權均需 Opus review PASS + Rick 明示批准。*
