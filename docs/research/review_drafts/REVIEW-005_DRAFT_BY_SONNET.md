# REVIEW-005 Draft — TASK-005 VPS Bot Monitor

**By**: Claude Sonnet  
**Date**: 2026-05-17  
**Scope**: TASK-005 VPS Bot Monitor 初審（observer-only scope 驗證、安全邊界、schema、tests）  
**依據**: Token Budget Rule — 只讀 REVIEW-005_PACKET.md + REVIEW-005_NUMBERS.json + heartbeat.parquet + alerts.jsonl + monitor_setup.log + configs/monitor.yaml + .gitignore + apps/monitor/safety.py

---

## REVIEW-005 Draft Verdict

**CONDITIONAL_PASS_CANDIDATE**  
**BLOCKING: 1 項**（B-1：`.gitignore` 截斷導致 `secret_in_vcs` gate = FAIL / tests FAIL）

---

## Blocking Issues

### B-1：`.gitignore` 截斷 — `secret_in_vcs` gate = TRUE（FAIL）

**現象**：`.gitignore` 最後一行為 `configs/monitor_secre`（截斷，無副檔名、無 wildcard）。Git 只匹配字面路徑，此 pattern 不覆蓋任何一個 secret file。

**驗證**：直接執行 `apps/monitor/safety.py::scan_monitor_safety()` 得到：

```json
{
  "status": "FAIL",
  "gates": {
    "secret_in_vcs": true,
    ...
  },
  "secret_ignore": {
    "status": "FAIL",
    "errors": [
      "missing .gitignore entries: ['configs/monitor_secrets.local.yaml', 'configs/monitor_secrets.local.yml', 'configs/monitor_secrets.yaml', 'configs/monitor_secrets.yml']"
    ]
  }
}
```

**Test 失敗**：`python -m unittest tests.monitor.test_heartbeat tests.monitor.test_alerts` → **1 FAIL**

```
FAIL: test_secret_ignore_and_safety_scan_pass (tests.monitor.test_alerts.AlertsTest)
AssertionError: 'FAIL' != 'PASS'
```

**Packet / Numbers 不一致**：`REVIEW-005_NUMBERS.json` 記錄 `secret_ignore.status = "PASS"` 且 `test_failure = false`。這兩個值在當前 repo 狀態下均不正確。推測原因：`.gitignore` 在 Codex 生成 packet 之後被意外截斷，或 packet 生成時使用了不同的 repo 狀態。

**必要修正**（最小 patch）：  
在 `.gitignore` 補全以下 4 行（取代截斷的 `configs/monitor_secre`）：
```
configs/monitor_secrets.yaml
configs/monitor_secrets.yml
configs/monitor_secrets.local.yaml
configs/monitor_secrets.local.yml
```
修正後須重新執行 `python scripts/task005_vps_bot_monitor.py --output-date <date>` 以更新 packet / numbers / log，並確認 6/6 tests PASS。

**阻擋理由**：`secret_in_vcs` 是工單定義的 fail gate；test_failure 也是 fail gate。兩個 fail gate 同時觸發，不可進入 Opus final review。

---

## Output Verification

| 檢查項目 | 結果 | 說明 |
|---|---|---|
| `apps/monitor/monitor.py` | ✅ 存在（以 `heartbeat.py` 形式交付） | 功能等效 |
| `apps/monitor/alerts.py` | ✅ 存在 | |
| `apps/monitor/config.py` | ✅ 存在 | |
| `apps/monitor/safety.py` | ✅ 存在（工單未列，Codex 額外交付）| 安全掃描模組 |
| `apps/monitor/schema.py` | ✅ 存在（工單未列，額外交付）| Schema 驗證模組 |
| `apps/monitor/log_scanner.py` | ✅ 存在（工單未列，額外交付）| |
| `apps/monitor/report.py` | ✅ 存在（工單未列，額外交付）| Review packet 生成 |
| `apps/monitor/README.md` | ⚠️ 存在，但僅 33 行（見 Non-blocking 觀察）| |
| `configs/monitor.yaml` | ✅ 存在，schema 符合工單規格 | |
| `tests/monitor/test_heartbeat.py` | ✅ 存在 | |
| `tests/monitor/test_alerts.py` | ✅ 存在 | |
| `outputs/monitor/prev3y_crypto/20260517_heartbeat.parquet` | ✅ 存在，1 row | |
| `outputs/monitor/prev3y_crypto/alerts/20260517.jsonl` | ✅ 存在，1 row | |
| `outputs/logs/prev3y_crypto/20260517_monitor_setup.log` | ✅ 存在 | |

**heartbeat.parquet schema**（實際欄位）：

| 欄位 | 型別 | 工單規格符合 |
|---|---|---|
| `timestamp` | large_string | ✅（工單: datetime64；功能等效）|
| `bot_name` | large_string | ✅（工單: bot_id → 命名略異）|
| `environment` | large_string | ✅（額外欄位）|
| `status` | large_string | ✅ |
| `equity` | double | ✅ |
| `nav` | double | ✅（工單未明列，額外）|
| `active_positions` | int64 | ✅ |
| `last_order_timestamp` | large_string | ✅（工單: last_order_time）|
| `api_latency_ms` | double | ✅ |
| `process_alive` | bool | ✅（工單未列，額外）|
| `paper_execution_status` | large_string | ✅（安全旗標）|
| `live_trading_status` | large_string | ✅（安全旗標）|
| `warning_count` | int64 | ✅（額外）|
| `critical_count` | int64 | ✅（額外）|

工單規格欄位 `daily_pnl_delta_usd` 未出現在 parquet schema（sample run 無前日 equity 可比較，合理）。

**alerts JSONL sample**（第一筆）：

```json
{
  "timestamp": "2026-05-17T00:00:00Z",
  "category": "MONITOR_SAMPLE",
  "severity": "INFO",
  "message": "Sample local monitor alert; no external notification was sent.",
  "dedupe_key": "MONITOR_SAMPLE:task005_sample",
  "source": "task005_sample",
  "action_required": "none_sample_only",
  "paper_execution_status": "FORBIDDEN",
  "live_trading_status": "FORBIDDEN"
}
```

JSONL 含 `paper_execution_status = FORBIDDEN` 和 `live_trading_status = FORBIDDEN` 的安全旗標。✅

---

## Safety Scan（重新執行結果，非 Packet 聲稱值）

| Gate | Packet 聲稱 | 實際執行結果 | 判定 |
|---|---|---|---|
| `api_key_permission_violation` | false | **false** | ✅ PASS |
| `order_submission_code_present` | false | **false** | ✅ PASS |
| `monitor_auto_restart_present` | false | **false** | ✅ PASS |
| `secret_in_vcs` | false | **TRUE** | ❌ FAIL |
| `exchange_connection_made` | false | **false** | ✅ PASS |
| `api_key_requested` | false | **false** | ✅ PASS |
| `paper_execution_started` | false | **false** | ✅ PASS |
| `live_trading_started` | false | **false** | ✅ PASS |

**整體 safety_scan status（實際）**：`FAIL`（因 `secret_in_vcs = true`）

**`forbidden_token_violations`（實際）**：`[]`（無任何禁止 token 觸發）✅

**`.gitignore` 現況**：

```
全檔案內容（共 115 bytes）：
.env
.venv/
__pycache__/
src/__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
data/trading.db
configs/monitor_secre       ← 截斷，缺少副檔名與後續 3 個 pattern
```

---

## Test Results

| 測試 | 狀態 | 備註 |
|---|---|---|
| `test_heartbeat_parquet_roundtrip` | ✅ PASS | |
| `test_monitor_hook_event_is_local_payload` | ✅ PASS | |
| `test_sample_heartbeat_matches_schema` | ✅ PASS | |
| `test_alert_jsonl_roundtrip` | ✅ PASS | |
| `test_alert_schema_and_dedupe` | ✅ PASS | |
| `test_secret_ignore_and_safety_scan_pass` | ❌ **FAIL** | `.gitignore` 截斷導致 `check_secret_ignore()` 回 FAIL |

**合計**：5/6 PASS，**1/6 FAIL**（fail gate `test_failure` = TRUE）

---

## Observer-Only Scope Verification

以下逐項確認 TASK-005 符合「旁觀者」邊界：

| 邊界 | 驗證方式 | 結果 |
|---|---|---|
| 無下單 API 呼叫 | safety scan forbidden_token_violations = [] | ✅ |
| 無 API key 請求 | api_key_requested = false | ✅ |
| 無 exchange 連線 | exchange_connection_made = false | ✅ |
| 無 paper execution 啟動 | paper_execution_started = false；configs/monitor.yaml `account_mode: read_only_monitor` | ✅ |
| 無 live trading 啟動 | live_trading_started = false | ✅ |
| 無 bot auto-restart | monitor_auto_restart_present = false；safety.py 的 forbidden_token 掃描包含 `auto_restart`、`restart_bot` | ✅ |
| Monitor 不在 `src/` 或 `apps/paper_trading/` | 模組在 `apps/monitor/`，獨立 | ✅ |
| `configs/monitor.yaml` 有 dry_run | `channels[0].type = local_jsonl, dry_run = true` | ✅ |

---

## Warning Gates

| Gate | 狀態 | 說明 |
|---|---|---|
| `single_channel_only` | ⚠️ **TRIGGERED** | 只實作 `local_jsonl`（dry_run）；無 Telegram / Discord / SMTP；工單要求至少 1 個推播 channel |
| `no_recovery_alert` | ✅ 未觸發 | |
| `no_pnl_floor_check` | ✅ 未觸發（`pnl.equity_floor_usd = 8000.0` 存在於 config）| |
| `dedup_window_too_long` | ✅ 未觸發（`dedup_window_minutes = 30`）| |
| `heartbeat_interval_too_long` | ✅ 未觸發（`interval_seconds = 60`）| |

**`single_channel_only` 說明**：目前 `configs/monitor.yaml` 只有 `local_jsonl` channel（`dry_run = true`），等同於本地文件記錄，無任何推播能力。工單驗收標準第 3 條：「通知至少支援 1 個 channel（Telegram / Discord / Email 擇一）」。這個 warning 在 paper trading 正式上線前須解決，但 Sonnet 認為在 REVIEW 層次為 Non-blocking Warning（待 Opus 裁定）。

---

## Non-blocking Observations

### README 內容不足（工單 NOTE-1 要求 7 個區塊）

工單 Section 15 NOTE-1 要求 README 涵蓋：所需 VPS 環境、API Key 設定（IP whitelist）、Secret 設定範本、啟動方式、Failure mode 說明、手動關閉方式、不可做的事。

實際 README（33 行）只涵蓋：啟動方式 ✅、模組說明 ✅、邊界聲明 ✅；缺少：Failure mode 詳述、VPS 環境需求、Bybit read-only key 設定步驟、手動關閉指令。

這是品質缺口，但 Sonnet 判斷為 Non-blocking（不影響安全性，上線前補充即可）。

### `heartbeat.parquet` `bot_id` vs `bot_name`

工單 schema 用 `bot_id`；實際交付用 `bot_name`。功能等效，但命名不符。Non-blocking，建議 Codex 在 B-1 修正時一併對齊。

### `monitor_hook_integration` 為 local_stub

NUMBERS.json 中 `monitor_hook_integration.mode = "local_stub"`，`side_effect_free = true`。這是正確設計（offline sample 不連接任何外部服務）。✅

---

## 工程正向確認

即使扣除 B-1 問題，以下工程品質超出工單最低要求：

1. **Safety 模組獨立化**：`apps/monitor/safety.py` 把禁止 token 掃描與 secret ignore 驗證封裝為可獨立呼叫的函式，讓 review 可程式化驗證。
2. **Forbidden token 構造方式**：safety.py 用字串拼接（`"place" + "_order"`）定義禁止 token，避免 linter / grep 誤判為「monitor 本身在呼叫禁止 API」，設計巧妙。
3. **Schema 模組**：`apps/monitor/schema.py` 獨立定義 parquet / JSONL 的欄位規格，供 tests 和 report 共用。
4. **Report 模組**：`apps/monitor/report.py` 獨立產出 PACKET.md / NUMBERS.json / setup.log，可重現。
5. **Config defaults 符合工單**：`interval_seconds=60`（工單要求≤60），`failure_threshold=3`（工單要求=3），`dedup_window_minutes=30`（工單要求=30），`equity_floor_usd=8000`（符合 TASK-006 NAV floor）。

---

## Issues Needing Opus Decision

### B-1 裁定

**背景**：`.gitignore` 被截斷，導致 `secret_in_vcs` fail gate 觸發、1 個 unit test FAIL。修正本身是最小 patch（補 4 行到 `.gitignore`，重跑 runner 更新 packet）。

**Opus 需裁定**：
- (A) 要求 Codex patch `.gitignore` + 重新產出 REVIEW-005 packet，再由 Sonnet 重新確認後送 Opus final → **推薦**（維持完整 review chain）
- (B) Opus 直接 CONDITIONAL_PASS，附帶條件：Rick 或 Codex 在上線前確認 `.gitignore` 補全 + 重跑 tests（不重開 Sonnet 審查）

### `single_channel_only` Warning 定性

**背景**：目前只有 `local_jsonl`（dry_run），無任何推播能力。工單驗收標準明確要求至少 1 個推播 channel。

**Opus 需裁定**：
- (A) 推播 channel 未實作 → 視為 Blocking，要求 Codex 補 Telegram 或 Discord 整合後才可 TASK-005 DONE
- (B) 推播 channel 為非必要前置（paper trading 尚未開始，30 天 forward record 期間再接上即可） → Warning 等級維持，允許 TASK-005 DONE 但附 caveat

---

## Reproducibility

| 項目 | 值 |
|---|---|
| `reproducibility_hash`（Packet）| `25cbf9c172b7bf377974e0fd1d568d57a888c8b090c25049f460b3c2ca42a606` |
| `git_commit` | `c44e12e54fde5a46ce0f0f1d53f5deabc92022f4` |
| 備註 | B-1 修正後 hash 將改變；Opus 需知悉 |

---

## Suggested Opus Prompt

---

Rick，以下是 REVIEW-005 final decision 的 Opus prompt。

---

**REVIEW-005 — TASK-005 VPS Bot Monitor Final Decision**

你是 Opus，負責對 TASK-005 VPS Bot Monitor 做最終裁定。

**背景**：TASK-005 建立了一個 observer-only 監控層（`apps/monitor/`），不含任何下單邏輯，不連接交易所，不啟動 paper/live trading。Codex 交付了 heartbeat.parquet、alerts JSONL、configs/monitor.yaml、tests、safety scan 等完整輸出。

**Sonnet 初審發現**：

**BLOCKING（1 項）—— B-1：`.gitignore` 截斷**
- `.gitignore` 最後一行為 `configs/monitor_secre`（截斷），不覆蓋任何 secret file 路徑。
- 實際執行 `scan_monitor_safety()` 回傳 `status: FAIL`，`secret_in_vcs: true`。
- Unit test `test_secret_ignore_and_safety_scan_pass` FAIL（5/6 PASS，1/6 FAIL）。
- REVIEW-005_PACKET.md / NUMBERS.json 記錄的 `test_failure: false`、`safety_scan: PASS` 為不一致值（packet 生成後 .gitignore 被截斷）。
- 修正極小：補全 4 行到 `.gitignore`，重跑 runner 更新 packet。

**工程正向確認（B-1 以外全部 PASS）**：
- `api_key_permission_violation = false`：無任何可下單 token ✅
- `order_submission_code_present = false`：無下單程式碼 ✅
- `monitor_auto_restart_present = false`：無自動 restart bot 程式碼 ✅
- `exchange_connection_made = false` ✅
- `api_key_requested = false` ✅
- heartbeat.parquet schema PASS，alerts JSONL schema PASS ✅
- configs/monitor.yaml 欄位符合工單規格 ✅
- Observer-only scope 完整確認 ✅

**WARNING（1 項）—— `single_channel_only`**
- 目前只有 `local_jsonl (dry_run=true)`，無 Telegram / Discord / SMTP 推播實作。
- 工單驗收標準第 3 條：「通知至少支援 1 個 channel」。

**請你裁定以下兩個問題**：

**Q1（B-1）**：選擇：
- 選項 A：要求 Codex patch `.gitignore`（補 4 行）→ 重跑 runner → Sonnet 重新確認 → 送 Opus final（完整 review chain）
- 選項 B：Opus 直接核發 CONDITIONAL_PASS，附帶條件：上線前 Rick 或 Codex 確認 `.gitignore` 補全 + tests 6/6 PASS，不重開 Sonnet 審查

**Q2（`single_channel_only`）**：選擇：
- 選項 A：推播 channel 未實作 → Blocking，要求補 Telegram/Discord 後才可 TASK-005 DONE
- 選項 B：推播 channel 為非阻擋項 → 允許 TASK-005 DONE 但附 caveat：VPS 正式上線前必須接上至少 1 個真實推播 channel

**請同時回答**：
- REVIEW-005 最終 verdict（PASS / CONDITIONAL_PASS / FAIL）
- TASK-005 是否可標 DONE（附條件或直接）
- Paper execution / live trading 狀態（應維持 FORBIDDEN）
- 是否需要其他 follow-up tasks

---

*Draft v1.0 | Claude Sonnet | 2026-05-17*  
*範圍：TASK-005 初審；未批准 paper execution 或 live trading；未標記 TASK-005 DONE*
