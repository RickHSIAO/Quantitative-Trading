# TASK-009b — Forward Monitor Alerting

**Version:** 1.0  
**Created:** 2026-05-17  
**Author:** Claude Sonnet (draft for Codex execution)  
**Status:** TODO  
**Size:** S（預估 2–3 天）  
**Priority:** 30-day clock 啟動前置條件之一

---

## §1 任務一句話

在 `apps/forward_record/alerting.py` 實作 forward record alerting 模組，整合現有 Discord channel（`apps/monitor/channels/discord.py`），在 runner 靜默失敗、gate 命中、或 review_006b 觸發條件達成時，主動向 Discord 發出通知。

---

## §2 任務目的

TASK-009 forward record runner 已完成（DONE）。runner 設計為本地/VPS 上的無人值守 daily job。若 runner 靜默失敗（如資料缺失、gate 命中、或 stop 觸發），Rick 無法即時得知，導致：

1. forward record 產出中斷卻未被發現
2. Stop gate 命中後繼續執行（違反設計意圖）
3. 30-day paper record 品質不足（影響 REVIEW-006b 時序判斷）

TASK-009b 的目標是為 forward runner 加上主動 alerting，讓 Rick 在不盯盤的情況下依然能及時掌握系統狀態。

---

## §3 為什麼重要

- **30-day clock 啟動前置條件**：NEXT_ACTION.md 明確列出 TASK-009b 為前置條件之一
- **Stop gate 設計閉環**：gate_checker.py 已定義 S-1~S-6 stop gate，但目前無 alerting；沒有 alerting 的 stop gate 形同虛設
- **REVIEW-006b 觸發通知**：`review_006b_trigger_ready()` 為 paper execution 批准前置；若靜默達成但 Rick 未收到通知，錯失批准時機
- **W gate 趨勢監控**：連續 N 天 W gate 為 stop gate 前兆；早期通知可讓 Rick 做出決策
- **最小化 Rick 手動盯盤負擔**：VPS 部署後 Rick 無法逐日手動確認輸出

---

## §4 Scope（範圍）

**In scope（本工單只做以下）：**
- `apps/forward_record/alerting.py`：新模組，alerting 主邏輯
- `apps/forward_record/alert_conditions.py`（或 inline in alerting.py）：各項條件判斷函式
- `scripts/run_forward_record.py`：在 daily pipeline 末端呼叫 alerting
- `configs/monitor.yaml`：不修改結構；alerting 讀取現有 discord channel 設定
- 單元測試：`tests/forward_record/test_alerting.py`

**Out of scope（本工單不做）：**
- 不修改 `gate_checker.py`（只讀取其輸出）
- 不修改 `apps/monitor/channels/discord.py`（只呼叫其介面）
- 不修改策略訊號、ranking、universe
- 不連接 Bybit
- 不啟動 30-day forward clock
- 不批准 paper / live execution
- 不修改任何 immutable run output（`outputs/` 下已存在的 parquet/json）
- 不實作 Email / Telegram / 其他 channel（僅 Discord）
- 不實作 web dashboard / metrics endpoint

---

## §5 Inputs（輸入）

| 來源 | 說明 |
|---|---|
| `apps/forward_record/gate_checker.py` | `evaluate_gates()` 回傳 `GateResult`（含 warnings / stops 列表）；`review_006b_trigger_ready()` 回傳 bool |
| `outputs/forward_record/primary/YYYYMMDD/forward_stats.json` | 當日 primary stats（days_elapsed, sharpe_rolling_30d, max_dd_pct, tracking_error 等） |
| `outputs/forward_record/primary/YYYYMMDD/positions.parquet` | 當日 primary positions（row count 驗證用） |
| `outputs/forward_record/shadow/YYYYMMDD/positions.parquet`（optional） | 當日 shadow positions（divergence 計算用；shadow 未啟用時跳過） |
| `outputs/forward_record/primary/YYYYMMDD/overlay_check.json` | overlay_always_pass, exception_recorded 欄位 |
| `outputs/forward_record/review_artifacts/YYYYMMDD_forward_record.log` | runner 執行日誌（heartbeat/status 行驗證用） |
| `configs/monitor.yaml` | Discord channel 設定（enabled, dry_run, secrets_env_webhook_url） |
| `configs/monitor_secrets.local.yaml`（runtime only，不得 commit） | Discord webhook URL secret |

---

## §6 Outputs（輸出）

| 檔案 | 說明 |
|---|---|
| `outputs/forward_record/alerts/YYYYMMDD_alert_log.json` | 當日 alert 執行紀錄（條件命中清單 + Discord 回應狀態） |
| Discord channel message（若 dry_run=False） | 格式見 §7；實際 POST 至 webhook |
| `outputs/forward_record/alerts/YYYYMMDD_alert_log.json` 中 `dry_run_preview` 欄位 | dry_run=True 時的預覽訊息內容，供人工確認 |

`YYYYMMDD_alert_log.json` schema（最小）：

```json
{
  "record_date": "YYYYMMDD",
  "run_ts": "ISO8601",
  "dry_run": true,
  "alerts_evaluated": [
    {
      "condition_id": "A-1",
      "condition_name": "runner_missing_rows",
      "triggered": false,
      "detail": "primary positions row_count=45"
    }
  ],
  "alerts_sent": [],
  "discord_results": [],
  "review_006b_trigger_ready": false,
  "FORBIDDEN_live_trading": "NOT_ATTEMPTED",
  "FORBIDDEN_order_endpoint": "NOT_ATTEMPTED",
  "FORBIDDEN_bybit_write": "NOT_ATTEMPTED"
}
```

---

## §7 Alert Conditions（告警條件）

以下為必實作的 7 類條件（condition_id A-1 ~ A-7）。每個條件必須有獨立函式，可單獨測試。

### A-1：runner 連續 2 天未產出 row

**觸發條件：**
```
最近 2 個日曆日（含今日）均無 primary/YYYYMMDD/positions.parquet，
或該檔案存在但 row_count == 0
```

**說明：** 檔案缺失或空 parquet 表示 runner 完全失敗。連續 1 天允許（可能為假日/資料延遲），連續 2 天視為異常。

**Discord 訊息格式：**
```
⚠️ [FORWARD RECORD] Runner missing rows
Date: {date}
Missing: {list of missing/empty dates}
Action required: Check VPS cron + runner log
```

---

### A-2：Stop gate 命中

**觸發條件：**
```
evaluate_gates() 回傳的 stops 列表非空（S-1 ~ S-6 任一命中）
```

**說明：** Stop gate 命中表示 forward record 進入強制中止條件。Rick 必須即時知悉，由 Rick 決定是否明示停止計時、是否聯繫調查。

**Discord 訊息格式：**
```
🛑 [FORWARD RECORD] STOP GATE triggered
Date: {date}
Gates: {stop_gate_ids}
Details:
  {gate_id}: {condition detail}
Action required: Rick decision required. Do NOT restart automatically.
```

---

### A-3：Warning gate 連續 N 天（可配置，預設 N=3）

**觸發條件：**
```
最近 N 個連續日均有相同 warning gate 命中（W-1 ~ W-6 任一）
```

**說明：** 單日 warning 為觀察；連續 N 天視為趨勢，為 stop gate 前兆。N 值透過 config 設定（預設 3）。

**Discord 訊息格式：**
```
⚠️ [FORWARD RECORD] Warning gate streak: {gate_id} × {N} days
Date: {date}
Gate: {warning_gate_id}
Recent values: {last_N_values}
Action: Monitor closely; stop gate threshold at {stop_threshold}
```

---

### A-4：Primary / shadow alpha gap 超出預設帶寬

**觸發條件：**
```
shadow track 已啟用，且
mean(abs(primary_weight[i] - shadow_weight[i])) > alpha_gap_threshold（預設 0.05）
across all matched symbols on record_date
```

**說明：** Primary 為 `combined_paper_safe_variant`，shadow 為 `A_roll12_share20_exclude`。alpha cap 觸發時兩者應有差異，但若差異過大或異常，表示計算可能有問題。gap threshold 透過 config 設定（預設 0.05 = 5% per-symbol mean abs diff）。

**Discord 訊息格式：**
```
⚠️ [FORWARD RECORD] Primary/shadow alpha gap exceeded
Date: {date}
Mean abs diff: {value:.4f} (threshold: {threshold})
Top divergent symbols: {top_3_symbols_with_diffs}
Action: Review shadow track output; check if alpha_cap_triggered_today
```

---

### A-5：Data source 連線/讀取失敗

**觸發條件：**
```
runner log 中含有 "data_source=FAILED" 或
forward_stats.json 不存在 / 讀取時 raise exception
```

**說明：** `CacheMarketDataProvider` 的快取讀取失敗（parquet 損毀、路徑錯誤等）。`BybitReadOnlyMarketDataProvider` 的 `allow_network=False` RuntimeError 不應在正常 VPS 環境觸發，但若出現也應 alert。

**Discord 訊息格式：**
```
🛑 [FORWARD RECORD] Data source failure
Date: {date}
Source: {data_source}
Error: {error_summary}
Action: Check parquet cache; verify data pipeline upstream of forward runner
```

---

### A-6：review_006b_trigger_ready = True

**觸發條件：**
```
review_006b_trigger_ready(stats, overlay_always_pass, exception_recorded) == True
```

**說明：** 5 個條件全部達成（days_elapsed >= 30, sharpe_rolling_30d >= 0.5, max_dd_pct > -0.30, no active stop gates, overlay pass/exception）。這是 paper execution 批准的前置通知。**每日只發一次**；若上一日已發過，且條件未改變，不重複發送（透過 alert log 確認）。

**Discord 訊息格式：**
```
✅ [FORWARD RECORD] REVIEW-006b trigger conditions met
Date: {date}
Days elapsed: {days_elapsed}
Sharpe (30d): {sharpe_rolling_30d:.4f}
Max DD: {max_dd_pct:.2%}
Active stop gates: NONE
Overlay: {overlay_status}
Action: Rick may initiate REVIEW-006b approval process.
Note: This is informational only. Paper execution requires explicit Rick approval.
```

---

### A-7：paper/live status 不是 FORBIDDEN

**觸發條件：**
```
alert_log.json 中任一 FORBIDDEN_* 欄位的值不是 "NOT_ATTEMPTED"
```

**說明：** 安全掃描的補充。forward runner 的任何輸出若含有非 NOT_ATTEMPTED 的 FORBIDDEN 欄位值，立即 alert Rick。這是最後一道防線，防止意外觸發下單邏輯。

**Discord 訊息格式：**
```
🚨 [FORWARD RECORD] FORBIDDEN field violation detected
Date: {date}
Field: {field_name}
Value: {field_value} (expected: NOT_ATTEMPTED)
Action: IMMEDIATE review required. Do NOT proceed with any execution.
```

---

## §8 Integration with TASK-005 / TASK-005a Alert Channel

alerting.py **直接呼叫** `apps/monitor/channels/discord.py` 中的 `send_discord_alerts()`，與 TASK-005 使用完全相同的 channel 介面。

### 呼叫方式

```python
from apps.monitor.channels.discord import send_discord_alerts
from apps.monitor.config_loader import load_monitor_config

def send_forward_alert(alert_text: str, dry_run: bool = True) -> ChannelResult:
    config = load_monitor_config("configs/monitor.yaml")
    discord_channel = config.alerts.channels[0]  # type=discord

    alert_obj = Alert(
        source="forward_record",
        severity="WARNING",   # or "STOP" / "INFO"
        message=alert_text,
    )

    return send_discord_alerts(
        config=config,
        channel=discord_channel,
        alerts=[alert_obj],
        dry_run=dry_run,   # 由外部控制；預設 True
    )
```

### dry_run 控制規則

| 環境 | dry_run 值 | 說明 |
|---|---|---|
| 本機 dev / test | `True`（強制） | 不得實際 POST |
| VPS 正式運行 | 由 `configs/monitor.yaml` 的 `dry_run` 欄位決定 | Phase 6 VPS 部署時由 Rick 手動設定為 `false` |
| CLI `--dry-run` flag | `True`（強制覆蓋） | 即使 yaml 設 false，CLI flag 優先 |
| CLI `--live-alerts` flag | 允許讀取 yaml 設定 | 明示允許實際 POST；需 Rick 在 VPS config 中啟用 |

**重要：** `dry_run=True` 為預設；只有在 VPS 部署後、Rick 明示修改 `configs/monitor.yaml` 中 `dry_run: false` 且使用 `--live-alerts` flag 時，才能實際 POST 至 Discord。

---

## §9 Daily Health Check（每日例行檢查）

每次 runner 執行完畢後，alerting 模組必須執行以下 **health check**（無論是否有 alert 條件觸發）：

```python
def run_daily_health_check(record_date, output_dir) -> HealthCheckResult:
    checks = {
        "primary_positions_present": check_file_exists_and_nonempty(primary_positions_path),
        "forward_stats_present": check_file_exists_and_nonempty(forward_stats_path),
        "overlay_check_present": check_file_exists_and_nonempty(overlay_check_path),
        "log_present": check_file_exists_and_nonempty(log_path),
        "runner_exit_success": check_log_for_exit_success(log_path),
    }
    return HealthCheckResult(date=record_date, checks=checks)
```

health check 結果寫入 `YYYYMMDD_alert_log.json` 的 `health_check` 欄位，不單獨發 Discord alert（除非有條件觸發）。

---

## §10 Stop Gate Alerting（詳細規格）

`evaluate_gates()` 回傳結構（參考 gate_checker.py）：

```python
GateResult(
    warnings=["W-1", "W-4"],   # list[str]
    stops=["S-2"],              # list[str]
    gate_details={
        "W-1": {"sharpe_rolling_30d": 0.32, "threshold": 0.5},
        "S-2": {"max_dd_pct": -0.42, "threshold": -0.40},
    }
)
```

Stop gate alerting（A-2）優先於所有其他 alert，先發送，再繼續其他條件評估。

Stop gate 命中後，alerting 模組**不自動停止 runner**；只發通知。停止 forward clock 需 Rick 明示。

---

## §11 Data Source Failure Alerting（詳細規格）

資料源失敗判斷邏輯：

1. `forward_stats.json` 不存在 → A-5 triggered
2. `forward_stats.json` 存在但 `data_source` 欄位值為 `"FAILED"` → A-5 triggered
3. `forward_stats.json` 存在但無法 JSON parse → A-5 triggered（"json parse error"）
4. Log 檔含有 `RuntimeError` 或 `CacheMarketDataProvider` 相關 exception → A-5 triggered

---

## §12 Missing Row Alerting（詳細規格）

Runner missing 判斷邏輯（A-1）：

```python
def check_runner_missing_rows(record_date: str, output_root: str,
                               lookback_days: int = 2) -> list[str]:
    """
    回傳 missing/empty 的日期列表（最近 lookback_days 日）。
    若列表長度 >= 2，觸發 A-1 alert。
    """
    missing = []
    for d in last_n_calendar_dates(record_date, lookback_days):
        path = f"{output_root}/primary/{d}/positions.parquet"
        if not exists(path) or read_parquet_row_count(path) == 0:
            missing.append(d)
    return missing
```

---

## §13 Primary / Shadow Divergence Alerting（詳細規格）

Alpha gap 計算（A-4）：

```python
def compute_alpha_gap(primary_positions_path: str,
                      shadow_positions_path: str) -> AlphaGapResult:
    primary = read_parquet(primary_positions_path)[["symbol", "weight_raw"]]
    shadow = read_parquet(shadow_positions_path)[["symbol", "weight_raw"]]
    merged = primary.merge(shadow, on="symbol", suffixes=("_p", "_s"))
    merged["abs_diff"] = abs(merged["weight_raw_p"] - merged["weight_raw_s"])
    return AlphaGapResult(
        mean_abs_diff=merged["abs_diff"].mean(),
        top_symbols=merged.nlargest(3, "abs_diff")[["symbol", "abs_diff"]].to_dict("records"),
        symbol_count=len(merged),
    )
```

**edge case：**
- shadow track 未啟用（shadow positions 不存在）→ 跳過 A-4，不報 error
- 兩者 symbol 集合不完全重疊 → 只對 intersection 計算；在 detail 中標註 unmatched symbol 數量

---

## §14 Tests / Validation（測試要求）

以下測試必須全部通過（`pytest tests/forward_record/test_alerting.py -v`）：

| 編號 | 測試名稱 | 說明 |
|---|---|---|
| T-1 | `test_a1_missing_rows_no_trigger` | 最近 2 天都有資料 → A-1 not triggered |
| T-2 | `test_a1_missing_rows_trigger` | 最近 2 天均缺失 → A-1 triggered |
| T-3 | `test_a2_stop_gate_trigger` | stops=["S-2"] → A-2 triggered |
| T-4 | `test_a2_stop_gate_no_trigger` | stops=[] → A-2 not triggered |
| T-5 | `test_a3_warning_streak_trigger` | W-1 連續 3 天 → A-3 triggered |
| T-6 | `test_a3_warning_streak_no_trigger` | W-1 連續 2 天（< N=3）→ not triggered |
| T-7 | `test_a4_alpha_gap_trigger` | mean_abs_diff=0.08 > 0.05 → A-4 triggered |
| T-8 | `test_a4_alpha_gap_no_shadow` | shadow positions 不存在 → A-4 skipped |
| T-9 | `test_a5_data_source_failure` | forward_stats.json 不存在 → A-5 triggered |
| T-10 | `test_a6_review006b_trigger` | review_006b_trigger_ready=True → A-6 triggered |
| T-11 | `test_a6_review006b_no_duplicate` | 昨日已發 A-6 → 今日不重複發送 |
| T-12 | `test_a7_forbidden_field_violation` | FORBIDDEN_live_trading != "NOT_ATTEMPTED" → A-7 triggered |
| T-13 | `test_dry_run_no_actual_post` | dry_run=True → ChannelResult.status == DRY_RUN，不發 HTTP |
| T-14 | `test_alert_log_written` | alerting run 後 YYYYMMDD_alert_log.json 存在且 schema valid |
| T-15 | `test_no_import_order_endpoints` | alerting.py import 不含任何 order endpoint 模組 |

---

## §15 Safety Gates（安全護欄）

以下為 hard-coded 安全護欄，**不得透過任何 config 或 flag 繞過**：

1. **FORBIDDEN_live_trading = "NOT_ATTEMPTED"**：alerting.py 的任何程式路徑均不得呼叫任何下單/cancel order/修改倉位的函式
2. **FORBIDDEN_order_endpoint = "NOT_ATTEMPTED"**：不得 import 任何含有 order endpoint 的模組（`apps/trading/`、`apps/execution/` 等）
3. **FORBIDDEN_bybit_write = "NOT_ATTEMPTED"**：不得呼叫任何 Bybit write API（POST /v5/order/*、DELETE /v5/order/* 等）
4. **alert 不觸發自動決策**：任何 alert（包括 A-6 review_006b）均只發通知，不觸發任何自動執行邏輯
5. **不修改 runner 輸出**：alerting.py 只讀取 `outputs/forward_record/` 下的輸出；不修改任何既有 parquet/json
6. **dry_run 預設 True**：不得在 code 中以任何方式讓 `dry_run` 的預設值為 `False`

---

## §16 Forbidden Actions（禁止事項）

以下事項 Codex **絕對不得執行**，即使 Rick 或任何人在指示中要求：

- 連接 Bybit 任何 endpoint
- 要求或讀取 API key / API secret
- 啟動 30-day forward clock（`clock_started = True`）
- 批准 paper execution 或 live trading
- 修改策略訊號、排名、universe
- 修改 `outputs/` 下既有的 immutable run output
- 修改 `apps/forward_record/gate_checker.py` 的 gate 邏輯
- 修改 `apps/monitor/channels/discord.py` 的 channel 邏輯
- 讓 `dry_run` 預設值為 `False`
- 讓 A-6 alert 觸發任何自動執行行為

---

## §17 Completion Report Format

Codex 完成後必須提交以下格式的 completion report：

```
TASK-009b Completion Report
============================
Date: YYYY-MM-DD
Codex session: [session ID or identifier]

Files created:
- apps/forward_record/alerting.py         [line count]
- apps/forward_record/alert_conditions.py [line count, if separate]
- tests/forward_record/test_alerting.py   [line count]

Files modified:
- scripts/run_forward_record.py           [brief description of change]

Test results:
- T-1 ~ T-15: [PASS / FAIL / SKIP per test]
- Total: [N/15] passed

Alert conditions implemented:
- A-1 runner_missing_rows:       ✅ / ❌
- A-2 stop_gate:                 ✅ / ❌
- A-3 warning_streak:            ✅ / ❌
- A-4 alpha_gap:                 ✅ / ❌
- A-5 data_source_failure:       ✅ / ❌
- A-6 review_006b_trigger_ready: ✅ / ❌
- A-7 forbidden_field_violation: ✅ / ❌

dry_run default: [True / False — must be True]
No order endpoints imported: [CONFIRMED / ISSUE]
No Bybit write calls: [CONFIRMED / ISSUE]
No clock_started mutations: [CONFIRMED / ISSUE]
FORBIDDEN fields all NOT_ATTEMPTED: [CONFIRMED / ISSUE]

Forbidden Items Confirmation (Codex must explicitly state each):
- [ ] Did NOT connect to Bybit
- [ ] Did NOT request or read any API key / secret
- [ ] Did NOT start or mutate 30-day forward clock
- [ ] Did NOT approve paper or live execution
- [ ] Did NOT modify strategy signals, ranking, or universe
- [ ] Did NOT modify any existing immutable run output in outputs/
- [ ] Did NOT modify gate_checker.py gate logic
- [ ] Did NOT modify discord.py channel logic
- [ ] dry_run default is True in all code paths
- [ ] A-6 alert triggers notification only, no automated execution

Notes / caveats:
[any deviations, TODOs, or known issues]
```

---

## Appendix A：gate_checker.py 參考（節錄）

```python
# W-1: Day 30+, sharpe_rolling_30d < 0.5
# W-2: max_dd_pct <= -0.25
# W-3: tracking_error >= 0.30
# W-4: overlay_false_streak >= 5
# W-5: monitor_heartbeat_missing_hours > 2.0
# W-6: data_gap_days > 1
# S-1: Day 10+, sharpe < -0.5
# S-2: max_dd <= -0.40
# S-3: tracking_error > 0.50 for >= 5 days
# S-4: overlay_false_streak >= 10
# S-5: safety_pass == False
# S-6: universe_count < 10 or missing_ratio > 0.20

def review_006b_trigger_ready(stats, overlay_always_pass, exception_recorded):
    return (
        stats.days_elapsed >= 30
        and stats.sharpe_rolling_30d >= 0.5
        and stats.max_dd_pct > -0.30
        and not stats.active_stop_gates
        and (overlay_always_pass or exception_recorded)
    )
```

---

## Appendix B：discord.py 參考（節錄）

```python
def send_discord_alerts(
    config, channel, alerts, http_client=None,
    test_send=False, environ=None
) -> ChannelResult:
    # Checks channel.enabled, channel.dry_run before any POST
    # Loads secrets via load_channel_secrets(channel, environ=environ)
    # Uses secrets.discord_webhook_url
    # Returns ChannelResult(status=SENT|DRY_RUN|SKIPPED|FAILED)
```

`configs/monitor.yaml`（現況）：
```yaml
alerts:
  channels:
    - type: discord
      enabled: true
      dry_run: true
      secrets_env_webhook_url: MONITOR_DISCORD_WEBHOOK_URL
```

---

*End of TASK-009b workorder v1.0*
