# REVIEW-009b Draft — TASK-009b Forward Monitor Alerting
# Reviewer: Claude Sonnet（Draft）
# Date: 2026-05-18
# Status: DRAFT（待 Rick 決定是否送 Opus）

---

## §1 Review Scope

| 項目 | 值 |
|---|---|
| Task | TASK-009b Forward Monitor Alerting |
| Workorder | `docs/research/codex_workorders/TASK-009b_forward_monitor_alerting.md` v1.0 |
| 實作檔案 | `apps/forward_record/alerting.py`、`apps/forward_record/alert_conditions.py`、`tests/forward_record/test_alerting.py`、`scripts/run_forward_record.py`（末端整合） |
| Codex 完成報告 | `docs/research/review_packets/REVIEW-009b_PACKET.md`、`REVIEW-009b_NUMBERS.json` |
| Review 基礎 | 程式碼全讀 + pytest 直接執行驗證 |
| Paper execution | FORBIDDEN（不在本 review 範圍） |
| Live trading | FORBIDDEN（不在本 review 範圍） |
| Bybit connection | NOT_ATTEMPTED |
| 30-day clock | NOT_STARTED |

---

## §2 Verdict Summary

| 類別 | 結果 |
|---|---|
| **Sonnet Draft Verdict** | **PASS** |
| Fail gates（10 項）| 全部通過（0 fail） |
| Warning（W-1 ~ W-3） | 3 件，全部 CAVEAT（non-blocking） |
| 建議後續 | TASK-009b 可 DONE；W-1/W-2/W-3 可納入 TASK-009a 或獨立小修補 |

---

## §3 Fail Gates（10 項）

以下 10 項均為 PASS。任何一項 FAIL 即全單否決。

| # | Gate | 判定 | 依據 |
|---|---|---|---|
| FG-1 | 無 order endpoint import | **PASS** | `scan_no_order_endpoints(['alerting.py', 'alert_conditions.py'])` → `violations=[]` |
| FG-2 | FORBIDDEN_live_trading = NOT_ATTEMPTED | **PASS** | `_safety_fields()` hardcoded；alert_log 寫入確認 |
| FG-3 | FORBIDDEN_order_endpoint = NOT_ATTEMPTED | **PASS** | 同上 |
| FG-4 | FORBIDDEN_bybit_write = NOT_ATTEMPTED | **PASS** | 同上；Bybit 無任何 import |
| FG-5 | dry_run 預設 True | **PASS** | `force_dry_run: bool = True`；`live_alerts: bool = False`；雙重 gate |
| FG-6 | 雙重 dry_run gate 邏輯正確 | **PASS** | `alert_dry_run = True if force_dry_run or not live_alerts else discord_channel.dry_run` — 唯有 `force_dry_run=False` AND `live_alerts=True` AND `yaml.dry_run=False` 三條件同時成立才允許實際 POST |
| FG-7 | 全部 7 項 alert conditions 實作 | **PASS** | A-1~A-7 逐一確認；REVIEW-009b_NUMBERS.json 全部 IMPLEMENTED |
| FG-8 | 15/15 tests PASS | **PASS** | `pytest tests/forward_record/test_alerting.py -v` 直接執行；15 collected，15 passed |
| FG-9 | clock_started 不變動 | **PASS** | alerting.py / alert_conditions.py 無任何 `clock_started` 賦值或 mutation |
| FG-10 | 驗證期間無實際 Discord POST | **PASS** | REVIEW-009b_NUMBERS.json `external_post_attempted=false`；`live_alerts_used_in_validation=false` |

---

## §4 Alert Conditions 逐項確認（A-1 ~ A-7）

### A-1：runner_missing_rows

**實作：** `check_runner_missing_rows(record_date, primary_positions_template, lookback_days=2)`

`last_n_calendar_dates()` 產生最近 N 天日期列表，`dated_path_from_template()` 將模板路徑中的日期字串替換後逐日確認 parquet 存在且 row_count > 0。`len(missing) >= lookback_days` 觸發。

**評估：** 邏輯符合工單 §12 規格。lookback_days=2 預設值正確。T-1/T-2 均 PASS。

---

### A-2：stop_gate_hit

**實作：** `check_stop_gate(stats)` 讀取 `stats.get("active_stop_gates")`。

severity="CRITICAL"，action_required 明確為 "rick_decision_required_do_not_restart"。符合工單 §10（Stop gate alerting 優先）。

**評估：** T-3/T-4 均 PASS。訊息格式符合工單 §7 A-2 規格。

---

### A-3：warning_gate_streak

**實作：** `check_warning_gate_streak(record_date, forward_stats_template, streak_days=3)`

設計：對最近 N 天的 `active_warning_gates` 列表取**交集**。只有全部 N 天都有相同 gate 才觸發。這比工單規格更嚴謹（工單規格為「相同 gate 連續 N 天」，交集實作等價）。

edge case：若中間某天 stats 不存在，`_read_json_if_exists()` 回傳 `{}`，對應天的 gates 為 `[]`，交集變空 → 不觸發。這是正確的 fail-safe 行為（數據不完整時不誤報）。

**評估：** T-5/T-6 均 PASS。

---

### A-4：primary_shadow_alpha_gap

**實作：** `check_alpha_gap()` → `compute_alpha_gap()`

shadow 不存在時 `AlphaGapResult(skipped=True, mean_abs_diff=None, ...)` → `triggered=False`。matched 為空 DataFrame 時 `mean_abs_diff=None` → 不觸發。正確處理 edge cases。

unmatched symbol 計數（`unmatched_primary`、`unmatched_shadow`）已記錄至 data 欄位，供後續分析。

**評估：** T-7/T-8 均 PASS。threshold=0.05 預設值符合工單規格。

---

### A-5：data_source_failure

**實作：** `check_data_source_failure()` 三層檢查：
1. `forward_stats.json` 不存在
2. `forward_stats.data_source == "FAILED"`
3. log 中含 `data_source=FAILED`、`RuntimeError`、`CacheMarketDataProvider`

**評估：** T-9 PASS。詳見 §5 W-1（`CacheMarketDataProvider` marker 潛在 false positive 分析）。

---

### A-6：review_006b_trigger_ready

**實作：** `check_review_006b_trigger(stats, previous_alert_log)`

duplicate 抑制：讀取前日 alert_log 的 `alerts_sent` 清單，若其中有 `condition_id == "A-6"` 則 `duplicate=True` → 當日不觸發。

severity="INFO"，action_required="rick_may_initiate_review_006b_process"，訊息末加 "Informational only. Paper execution requires explicit Rick approval."

**評估：** T-10/T-11 均 PASS。不自動批准 paper execution，符合 project 紅線。

---

### A-7：forbidden_field_violation

**實作：** `check_forbidden_field_violation(fields)` 比對 `_safety_fields()` 回傳的 dict。

實際運行時 `_safety_fields()` 永遠回傳 `{FORBIDDEN_*: "NOT_ATTEMPTED"}`，故 A-7 在正常路徑下永遠不觸發。這是正確設計：A-7 是「最後防線」，用於捕捉未來程式碼被錯誤修改後引入的 bug。

**評估：** T-12 PASS。

---

## §5 Warnings（non-blocking CAVEAT）

### W-1：A-5 `CacheMarketDataProvider` log marker 潛在 false positive

**問題：** `check_data_source_failure()` 中對 log 檔掃描的 markers 包含字串 `"CacheMarketDataProvider"`。若未來 log 格式改變（如 runner 加入 debug-level 初始化日誌，寫入類別名稱），或有外部工具在同一 log 目錄寫入含此字串的行，則正常日次也會觸發 A-5。

**目前風險：** 低。`write_log()` 只寫入明確的 key=value 字串清單，無類別名稱。Codex 驗證日（20260517）A-5 未觸發（alerts_sent=0）確認目前無 false positive。

**建議：** 後續可考慮移除 `"CacheMarketDataProvider"` marker，改為在 log 中加入明確的 `data_source_error=True` 標記，讓 A-5 掃描更精準。可納入 TASK-009a 或另立 XS 工單。

---

### W-2：`_extract_yyyymmdd()` 日期替換方式脆弱

**問題：** `dated_path_from_template()` 依賴 `_extract_yyyymmdd()` 掃描路徑字串中的第一個 8 位數字序列，作為要替換的日期。若路徑中有其他 8 位數字（例如某些 config path 或 file identifier 含數字），替換可能對到錯誤位置。

**目前風險：** 低。現有路徑格式為 `outputs/forward_record/primary/YYYYMMDD_positions.parquet`，`YYYYMMDD` 確實是第一個 8 位數字序列，替換正確。

**建議：** 長期可改為 `pathlib` 解析檔名中的日期部分（如 `stem.split('_')[0]`），或在路徑模板中用 `{date}` 佔位符。無需立即修改，低優先級。

---

### W-3：`REVIEW_NUMBERS_PATH` 依賴 review artifact 而非 runtime config

**問題：** `alerting.py` 的 `REVIEW_NUMBERS_PATH` 預設值為 `docs/research/review_packets/REVIEW-009_NUMBERS.json`，即 TASK-009 review 產生的副產品。alerting 的 output path 解析依賴此檔。若此檔被歸檔移動、或 output 路徑結構改變，alerting 需同步更新。

**目前風險：** 低。REVIEW-009_NUMBERS.json 是穩定的已完成 review 產出，不會被修改。且 `run_forward_alerting()` 接受 `review_numbers_path` 參數可覆蓋預設值，保留靈活性。

**建議：** 長期可將 output path 模板移入 `configs/prev3y_crypto.yaml` 或 `configs/forward_record.yaml`，讓 alerting 讀 config 而非 review artifact。可納入未來的 config consolidation 工單。無需立即修改。

---

## §6 Integration 驗證（run_forward_record.py）

```python
alert_log = run_forward_alerting(
    config.output_date,
    live_alerts=bool(args.live_alerts),
    force_dry_run=bool(args.dry_run) or not bool(args.live_alerts),
)
```

三重 dry_run 防護鏈：

1. `force_dry_run = bool(args.dry_run) or not bool(args.live_alerts)` — 無 `--live-alerts` flag 時強制 dry_run
2. `run_forward_alerting()` 內部：`alert_dry_run = True if force_dry_run or not live_alerts else discord_channel.dry_run`
3. `configs/monitor.yaml` 中 `dry_run: true`（第三道防線）

任何一道生效即為 DRY_RUN。實際 POST 需三條件同時滿足：CLI `--live-alerts`、`--dry-run` 未設、yaml `dry_run: false`。設計符合工單 §8 規格。

---

## §7 Architecture Highlights（正面評價）

1. **AlertConditionResult dataclass** 設計乾淨，每個 condition 獨立可測，`to_dict()` 直接序列化。
2. **A-6 duplicate suppression** 透過 previous_alert_log 實作，避免每日重複通知，設計精準。
3. **A-7 作為最後防線** 架構正確：`_safety_fields()` hardcoded，任何 bug 導致 FORBIDDEN 欄位被改寫才觸發，不影響正常路徑。
4. **`_discord_channel()` fallback** 若 monitor config 無 discord channel，回傳 `ChannelConfig(enabled=False, dry_run=True)` 而非 raise exception，符合 fail-safe 原則。
5. **health_check 欄位** 獨立於 alert conditions，每次 run 均記錄 5 項基礎健康狀態，方便 VPS 運行後的日誌審計。

---

## §8 Safety Summary（Sonnet 確認）

| 禁止事項 | 狀態 |
|---|---|
| 連接 Bybit | NOT_ATTEMPTED（無任何 bybit import） |
| 要求或讀取 API key / secret | NOT_ATTEMPTED |
| 啟動 30-day forward clock | NOT_STARTED（無 clock_started mutation） |
| 批准 paper execution | FORBIDDEN（A-6 為通知，不觸發任何執行） |
| 批准 live trading | FORBIDDEN |
| 修改策略訊號 / ranking / universe | 無任何相關操作 |
| 修改 immutable run output | 無（alerting 只讀取 outputs/；只寫入 outputs/forward_record/alerts/） |
| 修改 gate_checker.py / discord.py | 無 |
| dry_run 預設 True | 確認（FG-5 / FG-6） |
| A-6 觸發自動執行 | 無（僅通知） |

---

## §9 是否需要 Opus Final Decision

Sonnet 評估：**不強制需要 Opus**。理由：

- 10/10 fail gates PASS，邏輯清晰
- 3 個 warning 均為技術細節（false positive 風險低、路徑解析脆弱性、config 依賴問題），均非 blocking
- 實作與工單規格高度一致
- 測試覆蓋率完整（15/15 T-1~T-15 全中）

**但 Opus 驗證仍有價值**，特別是針對：
- W-1 的 `CacheMarketDataProvider` marker 是否構成設計瑕疵
- W-3 的 review artifact 依賴是否應在 VPS 部署前解決

決定權在 Rick。

---

## §10 Opus Final Decision 備用 Prompt（如 Rick 需要）

```
你是 Opus，正在對 TASK-009b forward monitor alerting 進行最終 review。

背景：
- TASK-009b 目標：為 Prev3Y crypto forward record runner 加入 Discord alerting
- Sonnet draft verdict: PASS，3 個 non-blocking warning（W-1/W-2/W-3）
- 10/10 fail gates PASS；15/15 tests PASS

禁止事項：
- 不得批准 paper execution 或 live trading
- 不得連接 Bybit
- 不得啟動 30-day forward clock

請確認以下：
1. FG-6 的雙重 dry_run gate 邏輯（force_dry_run OR not live_alerts）是否足夠安全？
2. A-5 的 CacheMarketDataProvider log marker：是否構成應立即修復的設計瑕疵？
3. A-6 的 duplicate suppression 邏輯（前日 alert_log）是否有遺漏場景？
4. W-3 的 REVIEW_NUMBERS_PATH 依賴：是否需要在 VPS 部署前解決？
5. 整體 TASK-009b：PASS / CONDITIONAL_PASS / FAIL？

需要回覆：
- 最終 verdict 與理由
- W-1/W-2/W-3 各自：CAVEAT / BLOCKING / DISMISS
- 是否有 TASK-009c 建議
```

---

## §11 Audit Statement

本 draft 由 Claude Sonnet 執行於 2026-05-18。

- 程式碼全讀：alerting.py（197 行）、alert_conditions.py（294 行）、test_alerting.py（267 行）、run_forward_record.py（末端整合部分）
- pytest 直接執行：15/15 PASS（sandbox 內直接確認）
- safety scan 直接執行：scan_no_order_endpoints → violations=[]
- Codex 完成報告讀取：REVIEW-009b_PACKET.md、REVIEW-009b_NUMBERS.json

未執行：Bybit 連接、Discord 實際 POST、30-day clock 啟動、paper execution 批准、live trading 批准、策略程式修改。
