# REVIEW-009c Draft — TASK-009c Forward Record Tech Debt Fixes (C-1 ~ C-6)

**作者**：Claude Sonnet（scheduled-task auto-resume, 2026-05-18）
**本檔為草稿，最終裁決需 Opus 覆審。**
**狀態**：DRAFT_BY_SONNET

---

## 1. Verdict Table（草稿建議：PASS）

| 項目 | 期望值 | 結果 | 根據 |
|---|---|---|---|
| C-1 A-5 marker narrowed | `("data_source=FAILED","RuntimeError")` only | **PASS** | `alert_conditions.py` line 220 確認；`"CacheMarketDataProvider"` 已移除 |
| C-2 `_extract_yyyymmdd()` hardened | pathlib stem + word-boundary regex | **PASS** | lines 303–308；`(?<!\d)(\d{8})(?!\d)` 邊界正確 |
| C-3 output paths in config | `configs/forward_record.yaml` + `resolve_forward_output_paths_from_config()` | **PASS** | yaml 存在（18 行，primary+shadow+log 三區塊）；`alerting.py` 有 `_resolve_runtime_paths()` 優先讀 config |
| C-4 raw/template checks separated | `no_placeholder_raw` ≠ injected-header check | **PASS** | drill report 全 13 個 scenario 有 `no_placeholder_raw` 欄位；`has_condition_id_in_raw=false`（正確反映 raw message 未含 condition_id） |
| C-5 None guard on construction | `AlertConditionResult.__post_init__` raises ValueError for None | **PASS** | lines 23–27 確認 |
| C-6 S-A5c negative drill scenario | S-A5c triggered=false | **PASS** | drill_report.json S-A5c: `triggered=false, result=PASS`；REVIEW-009d_NUMBERS `"S-A5c": true` |
| 22 test_alerting | PASS | **PASS** | COMMAND_LOG（Windows）確認 |
| 21 test_alert_e2e_drill | PASS | **PASS** | COMMAND_LOG（Windows）確認 |
| 54 tests.forward_record | PASS | **PASS** | COMMAND_LOG（Windows）確認 |
| 13 tests.monitor.test_channels | PASS | **PASS（Windows 環境）** | COMMAND_LOG（Windows）確認；見 §3 環境注記 |
| Drill 13/13 scenarios | PASS | **PASS** | drill_report.json overall_result=PASS, scenario_count=13 |
| external_post_attempted | false | **PASS** | drill_report.json + REVIEW-009c_NUMBERS.json |
| FORBIDDEN_bybit_connection | NOT_ATTEMPTED | **PASS** | REVIEW-009c_PACKET.md + NUMBERS.json |
| FORBIDDEN_discord_real_post | NOT_ATTEMPTED | **PASS** | 同上 |
| FORBIDDEN_live_alerts | NOT_ATTEMPTED | **PASS** | 同上 |
| clock_started | false | **PASS** | REVIEW-009c_NUMBERS.json `"clock_started": false` |
| paper_execution_status | FORBIDDEN | **PASS** | configs/forward_record.yaml 及 alerting.py 未更動執行邏輯 |
| live_trading_status | FORBIDDEN | **PASS** | 同上 |
| REVIEW-009d artifacts refreshed | S-A5c 加入後重新跑並更新 | **PASS** | REVIEW-009d_PACKET.md 第20行含 S-A5c；REVIEW-009d_NUMBERS.json 有 `"S-A5c": true` in negative_scenarios_not_triggered |

---

## 2. 逐項確認（C-1 ~ C-6）

### C-1：A-5 log marker 收斂

- **修改位置**：`apps/forward_record/alert_conditions.py` line 220
- **修改後**：`for marker in ("data_source=FAILED", "RuntimeError"):`
- `"CacheMarketDataProvider"` 已移除。
- S-A5c drill scenario 驗證：log 中含 `"CacheMarketDataProvider"` 但不含 FAILED/RuntimeError → `triggered=false` ✓
- **結論**：PASS

### C-2：`_extract_yyyymmdd()` 邊界強化

- **修改位置**：`apps/forward_record/alert_conditions.py` lines 303–308
- 現行實作：先取 `Path(text).stem`，再用 `re.search(r"(?<!\d)(\d{8})(?!\d)")` 提取
- Fallback：若 stem 無 8 位數字，改從全路徑搜尋
- Word boundary 限制排除 9 位數字序列（例如 `202601010_`）
- 依 workorder 要求的 5 條邊界 test 已涵蓋（`test_alerting.py` 22 tests PASS）
- **結論**：PASS

### C-3：runtime output path 移至 config

- **新增檔案**：`configs/forward_record.yaml`（18 行）
  - `output_paths.log`：`{date}` template
  - `output_paths.primary`：5 個路徑均含 `{date}`
  - `output_paths.shadow`：5 個路徑均含 `{date}`
- **新增函式**：`alerting.py` → `resolve_forward_output_paths_from_config()`、`_resolve_runtime_paths()`
- `_resolve_runtime_paths()` 優先讀 config；舊 `REVIEW_NUMBERS_PATH` 常數保留為 legacy fallback（設計意圖：平滑遷移，非 bug，見 §4 NOTE-1）
- **結論**：PASS

### C-4：raw check 與 injected-preview check 分離

- drill report 新增 `raw_content` 欄位（`has_date_in_raw`, `has_action_in_raw`, `has_condition_id_in_raw`）
- `has_condition_id_in_raw=false`：證明 condition_id 僅出現在 injected header，不在 raw `condition.message`（原 caveat 的核心）
- `no_placeholder_raw=true`：raw message 無 placeholder artifacts（C-5 + C-4 合力）
- **結論**：PASS

### C-5：None placeholder raw gate

- `AlertConditionResult.__post_init__`（lines 23–27）：`message is None` 或 `action_required is None` 直接 raise `ValueError`
- 建構期攔截，不依賴後續 sanitize
- drill report `no_placeholder_raw=true` for all 13 scenarios
- **結論**：PASS

### C-6：S-A5c negative drill scenario 補入

- Drill scenario S-A5c：log 含正常 `CacheMarketDataProvider` init text，無 FAILED/RuntimeError → `triggered=false`
- 驗證 C-1 marker 收斂實際產生效果（不只是程式碼改動）
- `s_a5c_not_triggered=true` in REVIEW-009c_NUMBERS.json
- REVIEW-009d_NUMBERS.json 同步更新（`negative_scenarios_not_triggered["S-A5c"]=true`）
- **結論**：PASS

---

## 3. 環境注記（Linux Sandbox Artifact — 非程式碼問題）

在此次 scheduled-task auto-resume 中，Linux sandbox 執行 `tests.monitor.test_channels` 時發生 4 項失敗：

```
TypeError: ChannelConfig.__init__() got an unexpected keyword argument 'secrets_env_token'
AssertionError: 'FAIL' != 'PASS'  (test_monitor_safety_scan_passes)
```

**根因診斷**：
1. `apps/monitor/__pycache__/config.cpython-310.pyc`（timestamp-mode, flags=0）的 source mtime = `2026-05-16 22:41:32`
2. Linux mount 上 `apps/monitor/config.py` 的 mtime 亦為 `May 16 22:41`（NTFS→Linux 同步問題）
3. Python 比對 timestamp 相同 → 使用 **stale pyc**（僅含舊版 3-field `ChannelConfig`，不含 `secrets_env_*` 欄位）
4. 嘗試 `PYTHONPYCACHEPREFIX=/tmp/pycache_fresh` 繞過後，發現 Linux mount 上的 `config.py` 本體亦被截斷於第 187 行（7,395 bytes，最後一行為 `current[list_key].`）

**結論**：Linux sandbox 的 mount snapshot 與 Windows NTFS 實際檔案內容不同步。這是 **沙盒環境同步問題，不是程式碼回歸**。Codex 在 Windows 環境執行的 `python -m unittest tests.monitor.test_channels -v` 結果為 PASS (13 tests)，已記錄於 COMMAND_LOG.md（2026-05-18 08:25 +08:00 條目）。

**Opus 覆審建議**：在 Windows 環境重跑 `python -m unittest tests.monitor.test_channels -v` 以確認 13/13 仍 PASS。

---

## 4. Open Notes（供 Opus 參考）

### NOTE-1：`REVIEW_NUMBERS_PATH` legacy constant 保留

`alerting.py` line 27 仍保有：
```python
REVIEW_NUMBERS_PATH = Path("docs/research/review_packets/REVIEW-009_NUMBERS.json")
```

`_resolve_runtime_paths()` 優先讀 `configs/forward_record.yaml`（C-3 新增），但若兩者均為 default 且 config 不存在，仍 fallback 到舊常數。這是有意的平滑遷移設計（config 現已存在，fallback 不會被觸發），**非 bug**，但可於未來 cleanup sprint 移除。

### NOTE-2：drill_report.json `"task": "TASK-009d"`

drill_report.json 頂層欄位 `"task": "TASK-009d"` — 這是 TASK-009d 原始 drill script 的 tag，TASK-009c re-run 並未更新此欄位。對內容驗證無影響（所有欄位均正確），但 Opus 可視需要要求 Codex 於未來 sprint 更新。

---

## 5. Safety Gate 彙總

| Gate | 期望 | 結果 |
|---|---|---|
| Bybit 連接 | NOT_ATTEMPTED | NOT_ATTEMPTED ✓ |
| Discord 真實 POST | NOT_ATTEMPTED | NOT_ATTEMPTED ✓ |
| --live-alerts | NOT_ATTEMPTED | NOT_ATTEMPTED ✓ |
| 30-day forward clock | NOT_STARTED | NOT_STARTED ✓ |
| Paper execution | FORBIDDEN | FORBIDDEN ✓ |
| Live trading | FORBIDDEN | FORBIDDEN ✓ |
| 策略訊號修改 | 禁止 | 未修改 ✓ |
| ranking / universe 修改 | 禁止 | 未修改 ✓ |
| raw data 修改 | 禁止 | 未修改 ✓ |
| `apps/paper_trading/` 修改 | 禁止 | 未修改 ✓ |
| immutable run outputs 修改 | 禁止 | 未修改 ✓ |

---

## 6. 草稿建議 Verdict

**建議：PASS**

六項 caveat（C-1~C-6）全部正確實作，drill 13/13 PASS（含新增 S-A5c 負向驗證），Windows 環境測試 54+22+21+13 = 110 tests 全 PASS，所有 FORBIDDEN gates 均為 NOT_ATTEMPTED，REVIEW-009d artifacts 已包含 S-A5c。

**Opus 覆審重點：**
1. 在 Windows 環境重跑 `python -m unittest tests.monitor.test_channels -v`，確認 13/13 PASS
2. 確認 drill_report.json 中 S-A5c 的 `triggered=false` 行為確實來自 C-1 marker 收斂（非 scenario 設計漏洞）
3. NOTE-1 legacy constant 是否需要即刻移除，或可留至 cleanup sprint

**不允許動作（此 draft 不改變）：**
- 不可將 TASK-009c 從 REVIEW 轉 DONE（須 Opus 明示）
- 不可送 Discord alert
- 不可連接 Bybit
- 不可啟動 30-day clock
- 不可批准 paper/live execution
