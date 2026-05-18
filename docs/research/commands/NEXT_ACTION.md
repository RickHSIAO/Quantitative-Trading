# Next Action

## Status
WAITING

## Owner
Rick

## Task
30-day forward validation clock STARTED（2026-05-18）。
Day 1 artifact written。Daily run required each day via approved command。

## 30-day Clock Status

| フィールド | 値 |
|---|---|
| clock_started | TRUE |
| start_date | 2026-05-18（Day 1） |
| start_time_UTC | 2026-05-18T10:06:43Z |
| start_time_Taipei | 2026-05-18T18:06:43 CST |
| authorized_by | Rick（explicit "開始計時" instruction） |
| end_date（目標） | 2026-06-17（30 calendar days） |
| validation_mode | forward-record / dry-run only |
| paper_execution_status | FORBIDDEN |
| live_trading_status | FORBIDDEN |
| clock_paused | false |

## Day 1 Run Summary（2026-05-18）

Command run:
  python3 scripts/run_forward_record.py
    --date 20260518
    --config configs/prev3y_crypto.yaml
    --output-dir outputs/forward_record/prev3y_crypto
    --dry-run

| フィールド | 値 |
|---|---|
| status | REVIEW_READY |
| signal_date | 2026-04-30（最新キャッシュ） |
| record_date | 20260518 |
| primary_generated | True |
| shadow_generated | False |
| warning_gates | [] |
| stop_gates | [] |
| safety_scan | PASS |
| review_006b_trigger_ready | False |
| dry_run | True |
| alerts_evaluated | 7 |
| alerts_triggered | 0 |
| bybit_connection | NOT_ATTEMPTED |
| paper_execution_status | FORBIDDEN |
| live_trading_status | FORBIDDEN |
| external_post_attempted | False |

Artifacts:
- outputs/forward_record/prev3y_crypto/20260518_positions.parquet （13957B / 50 rows）
- outputs/forward_record/prev3y_crypto/20260518_pnl.json
- outputs/forward_record/prev3y_crypto/20260518_forward_stats.json
- outputs/forward_record/prev3y_crypto/20260518_overlay_check.json
- outputs/forward_record/prev3y_crypto/forward_summary.json
- outputs/logs/prev3y_crypto/20260518_forward_record.log
- outputs/forward_record/alerts/20260518_alert_log.json

## Last Completed
Discord webhook VPS strict guard validation — confirmed on actual VPS（2026-05-18，Rick + Claude Sonnet）
- VPS hostname: instance-20260506-0945 / python: .venv/bin/python
- overall_result=PASS（6/6 gates）
- clock_started=False  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN

## Paper Execution Gate 現況（5/7）
- TASK-007b DONE ✅
- TASK-005 DONE ✅
- TASK-005a DONE ✅
- TASK-006 三補件 ✅
- Rick test-send ✅
- ❌ 30 天 forward paper record（Day 1 STARTED → 29 days remaining）
- ❌ REVIEW-006b + Rick 批准

## 30-day Clock 前置条件（全 ✅ DONE）

| 條件 | 狀態 |
|---|---|
| TASK-009 runner DONE | ✅ |
| TASK-009b forward monitor alerting DONE | ✅ |
| TASK-009c tech debt 收斂 DONE | ✅ |
| TASK-009d alert E2E drill DONE | ✅ |
| Windows baseline artifact | ✅（90 tests；SHA-256 b8d4fd69…） |
| VPS 部署 + dry-run validation | ✅（Ubuntu 24.04；drill 13/13） |
| Read-only data source validation | ✅（PASS） |
| Discord webhook VPS strict guard | ✅ DONE（PASS 6/6） |
| working tree clean | ✅ DONE（5 commits through 38db728） |
| Rick 明示「開始計時」 | ✅ DONE（2026-05-18） |

## Daily Action（毎日必须 — VPS 上で実行）

  python3 scripts/run_forward_record.py
    --date YYYYMMDD
    --config configs/prev3y_crypto.yaml
    --output-dir outputs/forward_record/prev3y_crypto
    --dry-run

## Do Not
- 不得啟動 live trading
- 不得啟動 paper execution（FORBIDDEN）
- 不得把 discord dry_run 改為 false
- 不得送真實 Discord alert
- 不得使用 --live-alerts
- 不得連接 Bybit write API
- 不得修改策略程式或官方輸出
- 不得進行 start-date selection（已完成）
