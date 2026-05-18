# TASK-009c — Forward Record 技術債修補
# Workorder v1.0
# 建立：Claude Sonnet，2026-05-18
# Owner：Codex
# 預估：XS（< 1 天）
# 依賴：TASK-009b ✓ DONE；TASK-009d ✓ DONE

---

## §1 背景與目的

本工單合併 REVIEW-009b（W-1/W-2/W-3）與 REVIEW-009d（W-1/W-2/W-3）共六項 non-blocking caveat，在不修改策略訊號、不連接 Bybit、不送真實 Discord alert 的前提下，對 `apps/forward_record/` 與 `scripts/drill_forward_alerts.py` 進行技術改進。

這些改動全為防禦性強化，不影響現有 PASS 狀態：A-1~A-7 條件的核心觸發邏輯、dry_run 三重 gate、FORBIDDEN field 設計均保持不變。

---

## §2 六項修補範圍（按執行順序）

### C-1：A-5 log marker 收斂（REVIEW-009b W-1）

**問題（`apps/forward_record/alert_conditions.py` 第 205–209 行）：**

```python
for marker in ("data_source=FAILED", "RuntimeError", "CacheMarketDataProvider"):
    if marker in text:
        errors.append(f"log marker found: {marker}")
```

`"CacheMarketDataProvider"` 是 market data module 的 class 名稱，正常 import/init log 中可能出現此字串，導致 A-5 在沒有真正資料來源失敗的情況下誤射（false positive）。

**修補方案：**
移除 `"CacheMarketDataProvider"` 作為獨立 log marker。保留 `"data_source=FAILED"` 與 `"RuntimeError"` 這兩個仍具有診斷價值的 marker。若未來需要精準識別 cache provider 失敗，改為搜尋 `"CacheMarketDataProvider: ERROR"` 或 `"CacheMarketDataProvider failed"` 等帶明確錯誤語義的字串。

**修改後 marker 列表（最終）：**
```python
for marker in ("data_source=FAILED", "RuntimeError"):
    if marker in text:
        errors.append(f"log marker found: {marker}")
```

**影響範圍：**
- `apps/forward_record/alert_conditions.py`：`check_data_source_failure()` marker loop
- 相關 test：`tests/forward_record/test_alerting.py`（確認移除 CacheMarketDataProvider marker 後 A-5 行為不變）

---

### C-2：`_extract_yyyymmdd()` 邊界強化（REVIEW-009b W-2）

**問題（`apps/forward_record/alert_conditions.py` 第 288–293 行）：**

```python
def _extract_yyyymmdd(text: str) -> str | None:
    for i in range(0, max(len(text) - 7, 0)):
        chunk = text[i : i + 8]
        if chunk.isdigit():
            return chunk
    return None
```

此實作以「第一個連續 8 位數字序列」為準。若路徑含多個 8 位數字序列（例如 `outputs/20260101/20260102_positions.parquet`），會回傳第一個（`20260101`），而非 stem date（`20260102`）。此行為可能在 `dated_path_from_template()` 中產生錯誤替換。

**修補方案：**

改用 pathlib 解析 stem date，讓 date 提取從 filename stem 而非整個 path 字串出發：

```python
def _extract_yyyymmdd(text: str) -> str | None:
    """Extract first 8-digit date token from path stem, then full string fallback."""
    import re
    # 優先從 filename stem 提取
    stem = Path(text).stem
    match = re.search(r'\b(\d{8})\b', stem)
    if match:
        return match.group(1)
    # Fallback：從完整路徑搜尋
    match = re.search(r'(?<!\d)(\d{8})(?!\d)', text)
    return match.group(1) if match else None
```

**邊界 test 新增（`tests/forward_record/test_alerting.py` 或新增 `tests/forward_record/test_alert_conditions.py`）：**

| 測試 | 輸入 | 期望輸出 |
|---|---|---|
| single date in stem | `"outputs/20260102_positions.parquet"` | `"20260102"` |
| multiple dates — stem wins | `"outputs/20260101/20260102_positions.parquet"` | `"20260102"` |
| no date | `"outputs/positions.parquet"` | `None` |
| date in dir only | `"outputs/20260101/positions.parquet"` | `"20260101"` |
| 9-digit sequence not matched | `"outputs/202601010_positions.parquet"` | `None`（無 word boundary） |

---

### C-3：output path 模板移至 runtime config（REVIEW-009b W-3）

**問題（`apps/forward_record/alerting.py` 第 27 行）：**

```python
REVIEW_NUMBERS_PATH = Path("docs/research/review_packets/REVIEW-009_NUMBERS.json")
```

`resolve_forward_output_paths()` 讀取此 review artifact 以取得 primary/shadow/log 的路徑模板。這讓 alerting 在 VPS 部署後仍依賴一個只存在於開發環境的 review 產物，而非 runtime config。

**修補方案：**

新增 `configs/forward_record.yaml` 作為 runtime config，將 output path 模板遷移至此。`run_forward_alerting()` 改讀 `configs/forward_record.yaml`；`REVIEW_NUMBERS_PATH` 退場為 fallback（backward-compatible）或完全移除。

**`configs/forward_record.yaml` 格式（新增）：**

```yaml
# Forward record output path templates
# {date} 佔位符或 yyyymmdd stem 替換由 dated_path_from_template() 處理

output_paths:
  log: "outputs/logs/prev3y_crypto/{date}_forward_record.log"
  primary:
    positions: "outputs/forward_record/primary/{date}_positions.parquet"
    forward_stats: "outputs/forward_record/primary/{date}_forward_stats.json"
    overlay_check: "outputs/forward_record/primary/{date}_overlay_check.json"
    pnl: "outputs/forward_record/primary/{date}_pnl.json"
  shadow:
    positions: "outputs/forward_record/shadow/{date}_positions.parquet"
    forward_stats: "outputs/forward_record/shadow/{date}_forward_stats.json"
    overlay_check: "outputs/forward_record/shadow/{date}_overlay_check.json"
    pnl: "outputs/forward_record/shadow/{date}_pnl.json"
```

**`alerting.py` 修改（主要）：**
- 新增 `FORWARD_RECORD_CONFIG_PATH = Path("configs/forward_record.yaml")` 常數
- `run_forward_alerting()` 新增 `forward_record_config_path: Path = FORWARD_RECORD_CONFIG_PATH` 參數
- 新增 `resolve_forward_output_paths_from_config(config_path, record_date)` 函式，讀取 yaml 並替換 `{date}`
- 原有 `resolve_forward_output_paths(review_numbers_path, record_date)` 可保留為 deprecated fallback，或改為讀取 yaml
- `dated_path_from_template()` 邏輯需支援 `{date}` 佔位符替換（目前只支援 stem 提取替換）

**`dated_path_from_template()` 延伸（`alert_conditions.py`）：**
```python
def dated_path_from_template(template: Path, date: str) -> Path:
    text = str(template)
    # 優先支援 {date} 佔位符
    if "{date}" in text:
        return Path(text.replace("{date}", date))
    # 既有 stem-date 提取替換（backward compat）
    stem_date = _extract_yyyymmdd(text)
    if stem_date:
        return Path(text.replace(stem_date, date, 1))
    return template
```

**相關 test：**
- `test_dated_path_from_template_with_placeholder()`：`{date}` 佔位符替換正確
- `test_resolve_output_paths_from_config()`：讀取 yaml 並回傳正確 path dict

---

### C-4：`_message_preview()` template check 與 raw content check 分離（REVIEW-009d W-1）

**問題（`scripts/drill_forward_alerts.py` 第 415–423 行）：**

```python
def _message_preview(condition: AlertConditionResult, scenario_id: str, record_date: str) -> str:
    message = condition.message or condition.detail
    text = (
        f"{scenario_id} {condition.condition_id} {condition.condition_name}\n"
        f"Date: {record_date}\n"
        f"{message}\n"
        f"Action: {condition.action_required}"
    )
    return _sanitize_text(text)
```

`_scenario()` 中以此 preview 做的 `has_date`、`has_condition_id`、`has_action` generic checks 因 inject 的 header/footer 而常 True，無法真正驗證 `condition.message` 的原始內容是否含有這些資訊。

**修補方案：**

新增 `_raw_content_check(condition)` 函式，對 `condition.message`（不含 inject 的 scenario header / Action footer）做 generic checks。`_scenario()` 拆成兩層：

1. **raw check 層**：對 `condition.message` 做 `has_date_in_raw`、`has_condition_id_in_raw`、`has_action_in_raw`
2. **preview 層**：`_message_preview()` 仍用於 redaction scan 與 `required_terms` 比對（因為 required_terms 是 condition-specific 實詞，不依賴 inject 字段）

```python
def _raw_content_check(condition: AlertConditionResult, record_date: str) -> dict[str, bool]:
    """Check condition.message raw text (no injected context)."""
    raw = condition.message or condition.detail
    return {
        "has_date_in_raw": record_date in raw,
        "has_condition_id_in_raw": condition.condition_id in raw,
        "has_action_in_raw": bool(condition.action_required) and len(condition.action_required) > 0,
    }
```

`_scenario()` 中 `content_checks` 新增 `"raw_content"` 子 dict，原有 `has_date`/`has_condition_id`/`has_action` 保留（用於向後相容），但標記為 `_injected_context=True`，讓 review 時能識別其限制。

**test 更新（`test_alert_e2e_drill.py`）：**
- 確認所有 12 scenarios 的 `raw_content.has_date_in_raw` 為 True（A-2 例外：A-2 的 message 使用 `stats.get('date', '')` — 可能需確認 fixture 含 date 欄位）
- 確認 `raw_content.has_action_in_raw` 為 True（all conditions 均有 action_required）

---

### C-5：`_sanitize_text()` None reject 前移至 payload schema 層（REVIEW-009d W-2）

**問題（`scripts/drill_forward_alerts.py` 第 426–427 行）：**

```python
def _sanitize_text(text: str) -> str:
    return text.replace("\r", " ").replace("None", "n/a")
```

`_scenario()` 的 `no_placeholder` check 是在 `_message_preview()` 呼叫 `_sanitize_text()` 之後才對 preview 做 `"None" not in preview`，因此即使 `condition.message` 含有 Python `None` 被 f-string 化為 `"None"` 的情況，sanitize 後也會回報 `no_placeholder=True`，形成漏洞。

**修補方案（兩層防護）：**

**層 1（AlertConditionResult schema 層）** — 在 `AlertConditionResult.to_dict()` 或 `message` 屬性加 None guard：

```python
# alert_conditions.py — AlertConditionResult
def __post_init__(self) -> None:
    # Reject None in message and action_required at construction time
    if self.message is None:
        raise ValueError("AlertConditionResult.message must not be None; use empty string")
    if self.action_required is None:
        raise ValueError("AlertConditionResult.action_required must not be None")
```

或更輕量：在所有 `check_*()` 函式確保 `message=` 使用非 None f-string（目前程式碼已如此，此為防禦性 guard）。

**層 2（drill 層）** — `_scenario()` 新增 `no_placeholder` pre-sanitize check，對 raw `condition.message` 先做一次 None 掃描，再呼叫 `_message_preview()`：

```python
# _scenario() 內
raw_message = condition.message or ""
raw_none_check = "None" not in raw_message  # check before sanitization
```

`content_checks["no_placeholder_raw"]` 記錄 raw check 結果，`content_checks["no_placeholder"]`（現有）保留 sanitized 版本，讓 review 時雙層可見。

**test 更新：**
- `test_no_none_in_raw_messages()`：確認所有 12 scenarios 的 `raw_message` 不含 `"None"` 字串

---

### C-6：S-A5c negative scenario 補入 drill（REVIEW-009d W-3）

**前提：C-1 必須先完成**（移除 `"CacheMarketDataProvider"` marker 後，S-A5c 才有意義）

**問題：**
TASK-009d drill 缺少「runner log 含 CacheMarketDataProvider 字串但 A-5 不應觸發」的 negative scenario，導致 C-1 修補的正確性無法被 drill 自動驗證。

**新增 scenario S-A5c（`scripts/drill_forward_alerts.py` `_build_scenarios()`）：**

```python
# S-A5c: log 含 CacheMarketDataProvider（正常 init log），A-5 不應觸發
a5c_dir = base / "a5c"
_write_json(a5c_dir / "forward_stats.json", {
    "date": record_date,
    "data_source": "LIVE",
    "rows": 50,
})
# 模擬正常 runner log，含 CacheMarketDataProvider 的 init 行（非 ERROR）
a5c_log = a5c_dir / f"{record_date}_forward_record.log"
a5c_log.parent.mkdir(parents=True, exist_ok=True)
a5c_log.write_text(
    f"status=REVIEW_READY\n"
    f"CacheMarketDataProvider initialized successfully\n",
    encoding="utf-8",
)
scenarios.append(_scenario(
    "S-A5c",
    check_data_source_failure(record_date, a5c_dir / "forward_stats.json", a5c_log),
    False,  # expected_triggered = False
    record_date,
    required_terms=["data source readable"],
))
```

**對應 test（`tests/forward_record/test_alert_e2e_drill.py`）：**

```python
def test_s_a5c_no_trigger_on_cache_provider_log(self) -> None:
    """After C-1 fix: CacheMarketDataProvider in log must not trigger A-5."""
    item = self.scenarios["S-A5c"]
    self.assertFalse(item["triggered"])
    self.assertEqual(item["result"], "PASS")
```

**drill report 更新：**
- `_write_review_numbers()` 中 `positive_scenarios_triggered` / `negative_scenarios_not_triggered` dict 加入 `"S-A5c": not item["triggered"]`
- scenario 總數從 12 → 13

---

## §3 修改檔案清單

| 檔案 | 修改項目 |
|---|---|
| `apps/forward_record/alert_conditions.py` | C-1（A-5 marker）；C-2（`_extract_yyyymmdd()`）；C-3（`dated_path_from_template()` `{date}` 支援）；C-5（AlertConditionResult None guard） |
| `apps/forward_record/alerting.py` | C-3（`FORWARD_RECORD_CONFIG_PATH`；`resolve_forward_output_paths_from_config()`；`run_forward_alerting()` 新增 config path 參數） |
| `configs/forward_record.yaml` | C-3（新增 runtime config） |
| `scripts/drill_forward_alerts.py` | C-4（`_raw_content_check()`；`_scenario()` 拆層）；C-5（`no_placeholder_raw` pre-check）；C-6（S-A5c scenario 加入） |
| `tests/forward_record/test_alerting.py` | C-1（移除 CacheMarketDataProvider marker test）；C-2（邊界 test）；C-3（config path test） |
| `tests/forward_record/test_alert_e2e_drill.py` | C-4（raw content check test）；C-5（no_none_in_raw test）；C-6（S-A5c test） |

---

## §4 測試規格（T-1 ~ T-14）

### C-1 Tests

| # | 測試 | 期望 |
|---|---|---|
| T-1 | `check_data_source_failure()` with log containing `"CacheMarketDataProvider initialized"` only | `triggered=False` |
| T-2 | `check_data_source_failure()` with log containing `"data_source=FAILED"` | `triggered=True` |
| T-3 | `check_data_source_failure()` with log containing `"RuntimeError"` | `triggered=True` |

### C-2 Tests

| # | 測試 | 期望 |
|---|---|---|
| T-4 | `_extract_yyyymmdd("outputs/20260102_positions.parquet")` | `"20260102"` |
| T-5 | `_extract_yyyymmdd("outputs/20260101/20260102_positions.parquet")` | `"20260102"`（stem wins） |
| T-6 | `_extract_yyyymmdd("outputs/positions.parquet")` | `None` |
| T-7 | `_extract_yyyymmdd("outputs/20260101/positions.parquet")` | `"20260101"` |
| T-8 | `dated_path_from_template(Path("outputs/{date}_positions.parquet"), "20260102")` | `Path("outputs/20260102_positions.parquet")` |

### C-3 Tests

| # | 測試 | 期望 |
|---|---|---|
| T-9 | `resolve_forward_output_paths_from_config(config_path, "20260102")` | `primary["positions"]` = `Path("outputs/forward_record/primary/20260102_positions.parquet")` |
| T-10 | `run_forward_alerting()` with `forward_record_config_path` pointing to temp yaml | no exception；paths resolved correctly |

### C-4 Tests

| # | 測試 | 期望 |
|---|---|---|
| T-11 | `_raw_content_check(condition, "20260102")` for S-A2 | `has_date_in_raw=True`（condition.message 含 date） |
| T-12 | all 13 scenarios: `content_checks["raw_content"]["has_action_in_raw"]` | all True |

### C-5 Tests

| # | 測試 | 期望 |
|---|---|---|
| T-13 | all 13 scenarios: `content_checks["no_placeholder_raw"]` | all True（無 raw "None"） |

### C-6 Tests

| # | 測試 | 期望 |
|---|---|---|
| T-14 | `test_s_a5c_no_trigger_on_cache_provider_log` | `triggered=False`；`result="PASS"` |

---

## §5 執行順序建議

```
C-1 → C-2 → C-3 → C-6 → C-4 → C-5
```

- C-1 先做：C-6 的 S-A5c 有效性依賴 marker 已移除
- C-2 可與 C-1 平行：獨立函式，無交叉依賴
- C-3 可與 C-1/C-2 平行：只影響 `alerting.py` 與新 config
- C-6 在 C-1 之後：確保 S-A5c fixture 所驗證的行為已落地
- C-4/C-5 最後：drill script 修改，先確保 conditions 層（C-1~C-3）穩定

---

## §6 完成報告格式

Codex 完成後需產出：

```
TASK-009c Completion Report
============================
Date: YYYYMMDD
Items completed: C-1 / C-2 / C-3 / C-4 / C-5 / C-6
Tests: T-1~T-14 (全 PASS 或標明跳過的項目)
unittest output:
  - tests/forward_record/test_alerting.py: X passed
  - tests/forward_record/test_alert_e2e_drill.py: X passed (含 S-A5c)
drill_report (13 scenarios): overall_result=PASS
Files changed: [清單]
FORBIDDEN gates:
  - Bybit connection: NOT_ATTEMPTED
  - Discord real POST: NOT_ATTEMPTED
  - live_alerts used: NOT_ATTEMPTED
  - 30-day clock: NOT_STARTED
  - paper/live execution: FORBIDDEN
Notes: [caveat 若有]
```

---

## §7 禁止事項（Red Lines）

以下任何行為均導致工單立即無效，Codex 必須停止並回報：

- 連接 Bybit（read 或 write）
- 要求或讀取 API key / API secret / Discord webhook URL（`TASK009D_UNUSED_CREDENTIAL` fixture 除外）
- 送出任何真實 Discord message（`--live-alerts` / `live_alerts=True` / `force_dry_run=False` 均禁止）
- 修改策略訊號邏輯（`apps/strategies/`、`apps/rankings/`）
- 修改 `apps/paper_trading/` 任何檔案
- 修改或重跑已有的 immutable run output（`outputs/` 下的 parquet / json）
- 啟動 30-day forward clock
- 批准 paper execution 或 live trading
- 修改 `apps/forward_record/alerting.py` 的 `_safety_fields()` 回傳值（必須保持 `"NOT_ATTEMPTED"`）
- 修改 FORBIDDEN field 設計
- 新增任何 import of order endpoints

---

## §8 Review 後置條件

TASK-009c DONE 後，REVIEW-009c（Sonnet draft + Opus final decision）需確認：

1. C-1：A-5 `CacheMarketDataProvider` marker 已移除；S-A5c PASS
2. C-2：`_extract_yyyymmdd()` 邊界 test T-4~T-7 全 PASS；stem priority 正確
3. C-3：`configs/forward_record.yaml` 存在；`run_forward_alerting()` 不再 hardcode review artifact path
4. C-4：`_raw_content_check()` 存在；`content_checks` 含 `"raw_content"` 子 dict
5. C-5：`no_placeholder_raw` check 存在；T-13 PASS
6. C-6：S-A5c 存在且 `triggered=False`；drill scenario 總數 = 13；overall_result=PASS
7. 全部 tests PASS（含現有 TASK-009b tests 15/15 + TASK-009d tests 18/18 + 新增 T-1~T-14）
8. 所有 FORBIDDEN gates NOT_ATTEMPTED；clock_started=false

---

*工單結束。Codex 執行前請確認 NEXT_ACTION.md status=READY 且 Owner=Codex。*
