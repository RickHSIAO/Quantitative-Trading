# Next Action

## Status
WAITING

## Owner
Rick

## Task
Windows baseline validation 記錄完了。等待 Rick 決定 VPS 部署の次のステップ。

## Last Completed
Windows baseline validation（2026-05-18，Rick 手動実行）
- `python -m unittest discover -v`：**PASS，90 tests**
- `python scripts/run_forward_record.py --date 20260517 --dry-run --shadow-track`：**PASS，REVIEW_READY**
- `python scripts/drill_forward_alerts.py --date 20260517`：**PASS，13/13 scenarios**
- safety scan：**PASS**
- Baseline artifact path：`outputs/forward_record/baselines/20260518/`
- Combined baseline SHA-256：`b8d4fd69fb77c52ad557b307cae3ecf23cc869f287e95702cd26ac2aaeb73476`
- paper/live：FORBIDDEN；clock：NOT_STARTED；Bybit：NOT_ATTEMPTED

## Paper Execution Gate 現況（5/7）
- TASK-007b DONE ✅
- TASK-005 DONE ✅
- TASK-005a DONE ✅
- TASK-006 三補件 ✅
- Rick test-send ✅
- ❌ 30 天 forward paper record（VPS 部署 + Rick 明示啟動後計時）
- ❌ REVIEW-006b + Rick 批准

## 30-day Clock 啟動前需完成的前置條件

| 條件 | 狀態 |
|---|---|
| TASK-009 runner DONE | ✅ |
| TASK-009b forward monitor alerting DONE | ✅ |
| TASK-009c tech debt 收斂 DONE | ✅ |
| TASK-009d alert E2E drill DONE | ✅ |
| Windows baseline pytest + safety scan artifact | ✅（2026-05-18；90 tests；SHA-256 b8d4fd69…） |
| VPS 實際部署（Phase 1–5 + 7–8）| ❌ NOT_STARTED |
| read-only data source 驗證（Bybit API 可讀） | ❌ NOT_STARTED |
| working tree clean（git stash / commit） | ❌ 需確認 |
| Discord webhook / monitor config 上 VPS | ❌ NOT_STARTED |
| Rick 明示「開始計時」| ❌ 待 Rick 指示 |

## Baseline Artifact 記錄

| Artifact | Path |
|---|---|
| pytest result | `outputs/forward_record/baselines/20260518/pytest_result.txt` |
| forward record result | `outputs/forward_record/baselines/20260518/forward_record_result.json` |
| drill result | `outputs/forward_record/baselines/20260518/drill_result.json` |
| safety scan | `outputs/forward_record/baselines/20260518/safety_scan.json` |
| baseline hash | `outputs/forward_record/baselines/20260518/baseline_hash.json` |
| **Combined SHA-256** | `b8d4fd69fb77c52ad557b307cae3ecf23cc869f287e95702cd26ac2aaeb73476` |

## Next Step Options

### Option A — Rick VPS 部署
- 參考：`docs/research/manual_ops/VPS_DEPLOYMENT_CHECKLIST.md`
- Phase 1–5 + 7–8（Phase 6 已解鎖）
- 完成後即可進行 Option B/C/D

### Option B — read-only data source 驗證
- 在 VPS 上確認 Bybit read-only API key 可正常讀取市場資料
- 依賴：Option A 完成
- 禁止：不可使用 write API；不可下單

### Option C — working tree clean
- `git stash` 或 `git commit` 現有 uncommitted diffs（含 task007 CSV / trading.db）
- 可在本機（Windows）執行，不依賴 VPS
- 啟動 30-day clock 前的必要條件

### Option D — Discord webhook / monitor config 上 VPS
- 在 VPS 上設定 Discord webhook URL（`configs/monitor_secrets.local.yaml`）
- 驗證 dry-run alert 可正常生成（不送實際 Discord）
- 依賴：Option A 完成

### Option E — 準備 start-date selection
- 確認 30-day forward record 的 start date（即 clock 啟動日）
- 討論 start date 選擇邏輯（交易日？月初？Rick 指定日？）
- 不需 VPS 完成即可討論

## Do Not
- 不得在沒有 Rick 指示下自行啟動任何 Option
- 不得啟動 30-day forward clock（需 Rick 明示「開始計時」）
- 不得批准 paper execution
- 不得批准 live trading
- 不得修改策略程式或官方輸出
- 不得連接 Bybit
- 不得送真實 Discord alert
- 不得使用 --live-alerts
- 不得重跑測試或 baseline
