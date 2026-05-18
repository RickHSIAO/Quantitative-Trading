# TASK-009d — Alert Delivery E2E Drill

**Version:** 1.0
**Created:** 2026-05-18
**Author:** Claude Sonnet（draft for Codex execution）
**Status:** TODO
**Size:** S（預估 1–2 天）
**Priority:** 30-day clock 啟動前置條件（必辦）

---

## §1 任務一句話

在 **dry-run / mock 模式**下，對 A-1~A-7 全部 7 個 alert conditions 逐一人工觸發，驗證 alert content、redaction、dedupe、Discord template rendering 均正確，產出演練報告，供 REVIEW-009d 審查。

---

## §2 任務目的

TASK-009b 已實作 `apps/forward_record/alerting.py`，unit tests 15/15 PASS。但 unit tests 使用 mock fixtures，無法驗證：

1. **Alert content 正確性**：每個 condition 觸發時，Discord 訊息的實際文字是否清晰、可操作
2. **Redaction**：訊息中是否有意外洩漏 secret / webhook URL / API key 的風險
3. **Dedupe 行為**：A-6 的 "不重複通知" 機制在跨日場景下是否正確
4. **Discord template rendering**：`ChannelResult` 的 `dry_run_preview` 欄位是否包含完整、可讀的訊息預覽
5. **全流程整合**：從 `run_forward_record.py` 末端呼叫 `run_forward_alerting()` 到 `alert_log.json` 寫出，完整路徑是否暢通

TASK-009d 透過一組腳本或 pytest scenario，在 dry-run 模式下人工構造每個 condition 的觸發狀態，逐一驗證上述 5 點。

---

## §3 為什麼重要

- **30-day clock 前置必辦**：NEXT_ACTION.md 明確列出 TASK-009d 為 clock 啟動前置條件
- **silent failure 風險**：若 alerting 層在 VPS 上靜默失敗（格式錯誤、redaction 誤觸、dedupe 誤判），stop gate 命中時 Rick 完全不知情；forward record 中斷也無通知
- **REVIEW-009b W-1 後遺症**：A-5 的 `CacheMarketDataProvider` marker 若修補後引入新 false positive，E2E drill 是最快的驗收手段
- **TASK-009c 修補驗收**：TASK-009c 修改了 alert_conditions.py；TASK-009d 是其整合驗收的自然場合

---

## §4 Scope（範圍）

**In scope（本工單只做以下）：**
- `scripts/drill_forward_alerts.py`（新腳本）：執行 A-1~A-7 七個 drill scenarios，輸出 drill_report.json
- `tests/forward_record/test_alert_e2e_drill.py`（新測試）：驗證 drill scenarios 的觸發結果、content、redaction、dedupe
- `docs/research/review_packets/REVIEW-009d_NUMBERS.json`：drill 結果摘要
- `docs/research/review_packets/REVIEW-009d_PACKET.md`：Codex 完成報告

**Out of scope（本工單不做）：**
- 不送實際 Discord POST（dry_run=True 強制）
- 不修改 `alerting.py` / `alert_conditions.py`（只執行，不改）
- 不修改 `gate_checker.py` / `discord.py`
- 不修改策略訊號、ranking、universe
- 不連接 Bybit
- 不啟動 30-day forward clock
- 不批准 paper / live execution
- 不修改任何 immutable run output

---

## §5 Inputs（輸入）

| 來源 | 說明 |
|---|---|
| `apps/forward_record/alerting.py` | `run_forward_alerting()`、`evaluate_alert_conditions()` |
| `apps/forward_record/alert_conditions.py` | A-1~A-7 condition functions |
| `apps/monitor/channels/discord.py` | `send_discord_alerts()`；`ChannelResult.dry_run_preview` |
| `configs/monitor.yaml` | Discord channel 設定（dry_run 必須維持 true） |
| Drill fixture data | 由腳本在 tempfile / tmpdir 內動態建立；不依賴任何真實 output |

---

## §6 Outputs（輸出）

| 檔案 | 說明 |
|---|---|
| `outputs/forward_record/drill/YYYYMMDD_drill_report.json` | 7 個 drill scenario 的執行結果、triggered 狀態、訊息預覽、redaction check、dedupe check |
| `docs/research/review_packets/REVIEW-009d_NUMBERS.json` | drill 摘要（7 scenarios pass/fail、redaction pass、dedupe pass、dry_run confirmed） |
| `docs/research/review_packets/REVIEW-009d_PACKET.md` | Codex 完成報告（含 Forbidden Items Confirmation） |

`YYYYMMDD_drill_report.json` schema（最小）：

```json
{
  "drill_date": "YYYYMMDD",
  "run_ts": "ISO8601",
  "dry_run": true,
  "scenarios": [
    {
      "scenario_id": "S-A1",
      "condition_id": "A-1",
      "condition_name": "runner_missing_rows",
      "triggered": true,
      "message_preview": "...",
      "redaction_pass": true,
      "content_checks": { "has_date": true, "has_action": true, "no_secret": true },
      "result": "PASS"
    }
  ],
  "dedupe_scenario": {
    "a6_day1_triggered": true,
    "a6_day2_suppressed": true,
    "result": "PASS"
  },
  "redaction_summary": { "all_pass": true, "violations": [] },
  "overall_result": "PASS",
  "FORBIDDEN_live_trading": "NOT_ATTEMPTED",
  "FORBIDDEN_order_endpoint": "NOT_ATTEMPTED",
  "FORBIDDEN_bybit_write": "NOT_ATTEMPTED",
  "FORBIDDEN_real_discord_post": "NOT_ATTEMPTED"
}
```

---

## §7 A-1~A-7 Drill Scenarios（逐一觸發規格）

每個 scenario 必須：
1. 構造可觸發該 condition 的 fixture（在 tmpdir 內）
2. 呼叫對應的 `check_*()` 函式或 `run_forward_alerting()`
3. 確認 `triggered=True`（或依場景 `triggered=False`）
4. 確認 `message_preview` 包含必要欄位（見各 scenario 的 content_checks）
5. 確認訊息不含任何 secret / webhook / api_key 字串
6. 結果寫入 drill_report.json

---

### S-A1：runner_missing_rows 觸發

**構造方式：** 建立 tmpdir；不建立任何 parquet 檔；呼叫 `check_runner_missing_rows("20260102", tmpdir / "20260102_positions.parquet")`

**預期：** `triggered=True`

**Content checks：**
- 訊息含 `"FORWARD RECORD"`
- 訊息含 `"Runner missing rows"` 或等效
- 訊息含 record date
- 訊息含 `"Action required"`

---

### S-A1b：runner_missing_rows 不觸發（正常日）

**構造方式：** 建立兩天的非空 parquet；呼叫 `check_runner_missing_rows()`

**預期：** `triggered=False`（smoke check，確認正常路徑不誤報）

---

### S-A2：stop_gate_hit 觸發

**構造方式：** `stats = {"date": "20260102", "active_stop_gates": ["S-2"], "active_warning_gates": []}`；呼叫 `check_stop_gate(stats)`

**預期：** `triggered=True`，`severity="CRITICAL"`

**Content checks：**
- 訊息含 `"STOP GATE"`
- 訊息含 `"S-2"`
- 訊息含 `"Do NOT restart automatically"` 或等效
- 訊息含 record date

---

### S-A3：warning_gate_streak 觸發（W-1 連續 3 天）

**構造方式：** 建立 3 天的 forward_stats.json，每天均含 `"active_warning_gates": ["W-1"]`；呼叫 `check_warning_gate_streak("20260103", ...)`

**預期：** `triggered=True`，`data.streak_gates == ["W-1"]`

**Content checks：**
- 訊息含 `"Warning gate streak"`
- 訊息含 `"W-1"`
- 訊息含連續天數（3）

---

### S-A3b：warning_gate_streak 不觸發（gap 中斷）

**構造方式：** day1 有 W-1，day2 無 gate，day3 有 W-1；呼叫 `check_warning_gate_streak()`

**預期：** `triggered=False`（交集為空）

---

### S-A4：primary_shadow_alpha_gap 觸發

**構造方式：** primary positions 含 symbol S0 weight_raw=0.10、S1 weight_raw=−0.10；shadow positions 含 S0 weight_raw=0.00、S1 weight_raw=−0.20；threshold=0.05；mean abs diff = 0.10 > 0.05

**預期：** `triggered=True`，`data.mean_abs_diff ≈ 0.10`

**Content checks：**
- 訊息含 `"alpha gap exceeded"`
- 訊息含 mean abs diff 數值
- 訊息含 top divergent symbols

---

### S-A4b：primary_shadow_alpha_gap 跳過（shadow 不存在）

**構造方式：** shadow_positions_path 指向不存在的檔案

**預期：** `triggered=False`，`data.skipped=True`

---

### S-A5：data_source_failure 觸發（stats 不存在）

**構造方式：** forward_stats_path 指向不存在的檔案；log_path 指向不存在的檔案

**預期：** `triggered=True`，errors 包含 "missing forward_stats"

**Content checks：**
- 訊息含 `"Data source failure"`
- 訊息含 `"Action: Check parquet cache"` 或等效

---

### S-A5b：data_source_failure 觸發（stats 含 data_source=FAILED）

**構造方式：** 建立 forward_stats.json 含 `"data_source": "FAILED"`

**預期：** `triggered=True`，errors 包含 "forward_stats data_source=FAILED"

---

### S-A6：review_006b_trigger_ready 觸發（首日）

**構造方式：** `stats = {"review_006b_trigger_ready": True, ...}`；`previous_alert_log=None`

**預期：** `triggered=True`，`severity="INFO"`

**Content checks：**
- 訊息含 `"REVIEW-006b trigger conditions met"` 或等效
- 訊息含 `"Informational only"` 或等效
- 訊息**不含** `"paper execution approved"` 或任何批准語言

---

### S-A6b：review_006b_trigger_ready dedupe 抑制（第二日）

**構造方式：** 建立前日 alert_log.json，其中 `alerts_sent` 含 `{"condition_id": "A-6"}`；再以 `review_006b_trigger_ready=True` 呼叫 `check_review_006b_trigger()`

**預期：** `triggered=False`（duplicate=True，抑制）

---

### S-A7：forbidden_field_violation 觸發

**構造方式：** `fields = {"FORBIDDEN_live_trading": "POST_ATTEMPTED", "FORBIDDEN_order_endpoint": "NOT_ATTEMPTED", "FORBIDDEN_bybit_write": "NOT_ATTEMPTED"}`；呼叫 `check_forbidden_field_violation(fields)`

**預期：** `triggered=True`，`severity="CRITICAL"`，violations 含 FORBIDDEN_live_trading

**Content checks：**
- 訊息含 `"FORBIDDEN field violation"`
- 訊息含 `"IMMEDIATE review required"`
- 訊息含違反欄位名稱

---

## §8 Redaction Validation（機密資訊遮罩驗證）

對每個 triggered scenario 的 `message_preview`，執行以下字串掃描，確保**無任何**以下字串出現：

| 掃描字串 | 說明 |
|---|---|
| `"webhook"` | Discord webhook URL |
| `"MONITOR_DISCORD_WEBHOOK_URL"` | env var 名稱（不應出現在訊息正文） |
| `"api_key"` | Bybit API key |
| `"api_secret"` | Bybit API secret |
| `"BYBIT_API_KEY"` | env var |
| `"BYBIT_API_SECRET"` | env var |
| `"token"` | Telegram token |
| `"Bearer "` | Authorization header |
| `"https://discord.com/api/"` | 完整 webhook URL prefix |

掃描結果記錄至 `drill_report.json` → `redaction_summary`。若任一掃描命中，則 `redaction_summary.all_pass=False`，整體 drill 判為 FAIL。

---

## §9 Dedupe Validation（重複通知驗證）

**必須驗證的兩個場景：**

1. **A-6 首日觸發**：`previous_alert_log` 不存在 → `triggered=True`
2. **A-6 次日不重複**：`previous_alert_log` 存在且含 A-6 entry → `triggered=False`（duplicate 抑制）

**另需驗證：**
- A-2（stop gate）**不** dedupe：每日均應觸發（stop gate 是持續狀態，每日都要通知）
- A-1（missing rows）**不** dedupe：每次執行均獨立評估（lookback window 機制已涵蓋）

dedupe 結果記錄至 `drill_report.json` → `dedupe_scenario`。

---

## §10 Discord Template Validation（訊息模板驗證）

對每個 triggered scenario，驗證 `ChannelResult.dry_run_preview`（或 `AlertConditionResult.message`）的格式：

| 驗證項 | 要求 |
|---|---|
| 訊息非空 | `len(message) > 0` |
| 含 condition 識別符 | 訊息中可識別是哪個 condition（A-1/A-2/...） |
| 含日期 | `record_date` 字串出現在訊息中 |
| 含 Action required | 訊息末端有明確 action 指引 |
| severity 對應正確 | A-2/A-5/A-7 = CRITICAL；A-1/A-3/A-4 = WARNING；A-6 = INFO |
| 無空白 placeholder | 訊息中無 `"{}"` 或 `"None"` 等未填入的格式符 |

---

## §11 dry-run Default / No Real POST（強制規定）

- `drill_forward_alerts.py` 中所有 `run_forward_alerting()` 呼叫必須使用 `force_dry_run=True`
- 禁止在腳本中傳入 `live_alerts=True`
- 禁止修改 `configs/monitor.yaml` 的 `dry_run` 欄位
- `drill_report.json` 必須包含 `"FORBIDDEN_real_discord_post": "NOT_ATTEMPTED"`
- `REVIEW-009d_NUMBERS.json` 必須包含 `"live_alerts_used": false` 及 `"external_post_attempted": false`

任何 `ChannelResult.status` 若為 `"SENT"`（而非 `"DRY_RUN"`）即為 **FAIL**。

---

## §12 Tests / Validation（測試要求）

以下測試必須全部通過（`pytest tests/forward_record/test_alert_e2e_drill.py -v`）：

| 編號 | 測試名稱 | 說明 |
|---|---|---|
| T-1 | `test_s_a1_trigger` | S-A1 missing rows → triggered=True |
| T-2 | `test_s_a1b_no_trigger` | S-A1b 正常日 → triggered=False |
| T-3 | `test_s_a2_trigger` | S-A2 stop gate → triggered=True，severity=CRITICAL |
| T-4 | `test_s_a3_trigger` | S-A3 streak 3 天 → triggered=True |
| T-5 | `test_s_a3b_no_trigger` | S-A3b gap 中斷 → triggered=False |
| T-6 | `test_s_a4_trigger` | S-A4 alpha gap > 0.05 → triggered=True |
| T-7 | `test_s_a4b_skip` | S-A4b shadow 不存在 → triggered=False，skipped=True |
| T-8 | `test_s_a5_trigger_missing` | S-A5 stats 不存在 → triggered=True |
| T-9 | `test_s_a5b_trigger_failed` | S-A5b data_source=FAILED → triggered=True |
| T-10 | `test_s_a6_trigger_first_day` | S-A6 首日 → triggered=True，severity=INFO |
| T-11 | `test_s_a6b_dedupe` | S-A6b 次日 → triggered=False（dedupe） |
| T-12 | `test_s_a7_trigger` | S-A7 FORBIDDEN violation → triggered=True，severity=CRITICAL |
| T-13 | `test_redaction_all_scenarios` | 全部 triggered message_preview 無 secret 字串 |
| T-14 | `test_discord_channel_result_dry_run` | 全部 ChannelResult.status == DRY_RUN（非 SENT） |
| T-15 | `test_drill_report_written` | drill_report.json 存在且 overall_result = PASS |
| T-16 | `test_forbidden_fields_all_not_attempted` | drill_report.json 四個 FORBIDDEN 欄位均為 NOT_ATTEMPTED |
| T-17 | `test_a6_no_paper_approval_language` | A-6 訊息不含任何批准 / 下單語言 |
| T-18 | `test_no_import_order_endpoints` | drill 腳本不含 order endpoint import |

---

## §13 Safety Gates（安全護欄）

以下為 hard-coded 安全護欄，**不得透過任何 config 或 flag 繞過**：

1. **FORBIDDEN_real_discord_post = "NOT_ATTEMPTED"**：drill 腳本不得實際 POST 任何訊息至 Discord
2. **FORBIDDEN_live_trading = "NOT_ATTEMPTED"**：drill 腳本不含任何下單 / cancel / 修改倉位邏輯
3. **FORBIDDEN_order_endpoint = "NOT_ATTEMPTED"**：不得 import 任何含有 order endpoint 的模組
4. **FORBIDDEN_bybit_write = "NOT_ATTEMPTED"**：不得呼叫任何 Bybit write API
5. **A-6 不觸發自動決策**：A-6 drill 結果為通知訊息預覽，不觸發任何 paper / live 執行邏輯
6. **force_dry_run=True 強制**：drill 腳本所有 `run_forward_alerting()` 呼叫均帶 `force_dry_run=True`，不得有例外路徑

---

## §14 Forbidden Actions（禁止事項）

以下事項 Codex **絕對不得執行**：

- 連接 Bybit 任何 endpoint（read 或 write）
- 要求或讀取 API key / API secret / Discord webhook URL（drill 使用 mock / fixture）
- 啟動 30-day forward clock（`clock_started = True`）
- 批准 paper execution 或 live trading
- 修改策略訊號、排名、universe
- 修改 `outputs/` 下既有的 immutable run output
- 修改 `apps/forward_record/alerting.py` 或 `alert_conditions.py`（若需修改，先停手並在工單下方留 NOTE 等 Claude / Rick 指示）
- 修改 `apps/monitor/channels/discord.py`
- 設定 `force_dry_run=False` 或 `live_alerts=True`
- 實際 POST 任何訊息至 Discord（包括測試訊息）

---

## §15 Completion Report Format

Codex 完成後必須提交以下格式的 completion report（寫入 `docs/research/review_packets/REVIEW-009d_PACKET.md`）：

```
TASK-009d Completion Report
============================
Date: YYYY-MM-DD
Codex session: [session ID or identifier]

Files created:
- scripts/drill_forward_alerts.py              [line count]
- tests/forward_record/test_alert_e2e_drill.py [line count]
- outputs/forward_record/drill/YYYYMMDD_drill_report.json
- docs/research/review_packets/REVIEW-009d_NUMBERS.json
- docs/research/review_packets/REVIEW-009d_PACKET.md

Test results:
- T-1 ~ T-18: [PASS / FAIL / SKIP per test]
- Total: [N/18] passed

Drill scenario results:
- S-A1  runner_missing_rows trigger:       PASS / FAIL
- S-A1b runner_missing_rows no-trigger:    PASS / FAIL
- S-A2  stop_gate_hit trigger:             PASS / FAIL
- S-A3  warning_gate_streak trigger:       PASS / FAIL
- S-A3b warning_gate_streak no-trigger:    PASS / FAIL
- S-A4  alpha_gap trigger:                 PASS / FAIL
- S-A4b alpha_gap skip:                    PASS / FAIL
- S-A5  data_source_failure trigger:       PASS / FAIL
- S-A5b data_source_failure FAILED:        PASS / FAIL
- S-A6  review_006b first day:             PASS / FAIL
- S-A6b review_006b dedupe:                PASS / FAIL
- S-A7  forbidden_field_violation:         PASS / FAIL

Redaction validation: [PASS / FAIL]
- Violations found (if any): [list]

Dedupe validation: [PASS / FAIL]
- A-6 day1 triggered:    [true/false]
- A-6 day2 suppressed:   [true/false]
- A-2 not deduped:       [true/false]

Discord template validation: [PASS / FAIL]
- All messages non-empty:   [true/false]
- All have action guidance: [true/false]
- No placeholder artifacts: [true/false]
- Severity mapping correct: [true/false]

dry_run confirmed: [True / False — must be True]
live_alerts used: [false — must be false]
external_post_attempted: [false — must be false]
No order endpoints imported: [CONFIRMED / ISSUE]
No Bybit connection: [CONFIRMED / ISSUE]
No clock_started mutation: [CONFIRMED / ISSUE]

Forbidden Items Confirmation (Codex must explicitly state each):
- [ ] Did NOT send any real Discord POST
- [ ] Did NOT use --live-alerts flag
- [ ] Did NOT connect to Bybit
- [ ] Did NOT request or read any API key / secret / webhook URL
- [ ] Did NOT start or mutate 30-day forward clock
- [ ] Did NOT approve paper or live execution
- [ ] Did NOT modify strategy signals, ranking, or universe
- [ ] Did NOT modify any existing immutable run output in outputs/
- [ ] Did NOT modify alerting.py or alert_conditions.py
- [ ] force_dry_run=True in all drill calls

Overall result: [PASS / FAIL]

Notes / caveats:
[any deviations, TODOs, or known issues]
```

---

## Appendix A：A-1~A-7 Condition 快速參考

| Condition ID | 函式 | 觸發條件 | Severity |
|---|---|---|---|
| A-1 | check_runner_missing_rows | 最近 2 天均無 positions parquet 或 row_count=0 | WARNING |
| A-2 | check_stop_gate | active_stop_gates 非空（S-1~S-6） | CRITICAL |
| A-3 | check_warning_gate_streak | 相同 warning gate 連續 N 天（預設 3） | WARNING |
| A-4 | check_alpha_gap | mean abs diff > threshold（0.05）且 shadow 存在 | WARNING |
| A-5 | check_data_source_failure | stats 不存在 / data_source=FAILED / log 含錯誤 marker | CRITICAL |
| A-6 | check_review_006b_trigger | review_006b_trigger_ready=True 且非 duplicate | INFO |
| A-7 | check_forbidden_field_violation | 任一 FORBIDDEN_* 欄位 ≠ NOT_ATTEMPTED | CRITICAL |

---

## Appendix B：dry_run Gate 快速參考

```python
# run_forward_alerting() 內部邏輯
alert_dry_run = True if force_dry_run or not live_alerts else discord_channel.dry_run

# drill 腳本必須這樣呼叫
run_forward_alerting(
    record_date,
    force_dry_run=True,   # 強制，不得省略
    live_alerts=False,    # 強制，不得改為 True
    ...
)

# 允許的 ChannelResult.status：DRY_RUN / SKIPPED
# 禁止的 ChannelResult.status：SENT
```

---

*End of TASK-009d workorder v1.0*
