# TASK-009 — Forward Record Runner（工單，非執行授權）

- **狀態**：TODO
- **Owner**：Codex（實作）→ Sonnet（review packet）→ Opus（REVIEW-009，若需要）
- **預估**：S（2–3 天）
- **工單版本**：v1.0（2026-05-17，Claude Sonnet）
- **依賴**：
  - TASK-006 ✅ DONE（`combined_paper_safe_variant` 規格 + `apps/paper_trading/` 模組）
  - TASK-007b ✅ DONE（overlay rule 驗證）
  - TASK-008 ✅ CONDITIONAL_PASS（`A_roll12_share20_exclude` shadow-track 可用）
  - TASK-005 ✅ DONE（VPS monitor stack；需 VPS 部署後才實際整合）
  - `docs/research/manual_ops/30_day_forward_record_plan.md` v1.0
  - `docs/research/manual_ops/30_day_forward_start_checklist.md` v1.0

---

## ⛔ 重要聲明（必讀）

**本工單是「forward record runner 技術實作」，不是「paper execution 授權」。**

- Codex 的工作是：建立每日跑訊號 + 計算假設持倉 + 記錄模擬 PnL 的 runner。
- **不得**提交任何訂單（paper 或 live）。
- **不得**連接 Bybit 或任何交易所的下單 endpoint。
- Paper execution 需滿足 `30_day_forward_start_checklist.md` §6 的所有條件，且需要 Opus REVIEW-006b PASS + Rick 明示批准。
- Live trading 在另一輪專屬 Opus review + Rick 明示批准之前，永遠 FORBIDDEN。

---

## 1. 任務一句話

實作 `scripts/run_forward_record.py` 及配套模組 `apps/forward_record/`，每日自動執行 Prev3Y crypto momentum 策略訊號生成 → overlay 套用 → 假設持倉計算 → PnL 計算 → 統計更新 → warning/stop gate 檢查，並同步記錄 primary（`combined_paper_safe_variant`）與 shadow-track（`A_roll12_share20_exclude`）兩條規格，**不提交任何委託單，不連接任何交易所寫入端點。**

---

## 2. 任務目的

### 2.1 解決的問題

`VPS_DEPLOYMENT_CHECKLIST.md` Phase 6 標記為 **DEFERRED**，原因是 forward record runner 尚未建立。30-day clock 無法在沒有 runner 的情況下啟動。本工單補齊這一缺口。

### 2.2 研究路徑中的位置

| 已完成 | 說明 |
|---|---|
| TASK-001 run008 | Sharpe 0.8918，760 天 active 回測 |
| TASK-002 cost stress | Realistic combo PASS |
| TASK-003 attribution | Short-driven alpha 確認 |
| TASK-006 paper infra | `apps/paper_trading/` 模組完成（overlay / sizing / recorder） |
| TASK-007b overlay val | `combined_paper_safe_variant` overlay rule 驗證 |
| TASK-008 alpha-space | `A_roll12_share20_exclude` CONDITIONAL_PASS |
| **TASK-009（本工單）** | **Forward record runner 實作** |
| ❌ 30-day clock | 待 runner + VPS 部署後啟動 |
| ❌ REVIEW-006b | 待 30-day record 完成後 |
| ❌ Paper execution | 待 REVIEW-006b PASS + Rick 批准 |

---

## 3. 為什麼重要

1. **30-day clock 前置條件**：runner 不存在則無法啟動計時。
2. **REVIEW-006b 依賴 runner 產出**：Opus review 需要真實的前向日報酬序列，而非歷史代理。
3. **Shadow-track 需同步運行**：`A_roll12_share20_exclude` 的前向表現只有在同期 primary 資料存在的情況下才有對照意義。
4. **Safety gate 自動化**：W-1~W-6 / S-1~S-6 gate 需要 runner 在每日計算後自動觸發，不靠人工。

---

## 4. Scope

### ✅ Do（Codex 被允許做）

- 建立 `scripts/run_forward_record.py` — 每日 CLI 入口（接受 `--date`、`--config`、`--output-dir`、`--dry-run`、`--shadow-track`）
- 建立 `apps/forward_record/` 模組組（signal_loader / pnl_calculator / stats_updater / gate_checker / report_writer）
- **重用** `apps/paper_trading/overlay.py`、`apps/paper_trading/config.py`、`apps/paper_trading/recorder.py`、`apps/paper_trading/validator.py` — 直接 import，不複製
- **重用** `src/variants/task008.py` — `apply_alpha_contribution_cap()` 用於 shadow-track
- **重用** `src/signals/prev3y_momentum.py` — `build_prev3y_targets()`（read-only import；不修改）
- 實作 `apps/forward_record/market_data.py` — 從 Bybit **read-only** REST API 取得最新 OHLCV / funding rate（或 fallback 至本地 parquet cache）
- 實作 warning / stop gate 自動檢查（依 `30_day_forward_record_plan.md` § 6）
- 建立 `tests/forward_record/` 單元測試（含 mock market data；不打真實 API）
- 為 Sonnet review 產出 `docs/research/review_packets/REVIEW-009_PACKET.md`（若 runner 完成後需 review）

### ❌ Don't（絕對禁止）

- **不得**提交任何委託單（paper 或 live）
- **不得**連接 Bybit 的下單 endpoint（POST /v5/order/create 或任何 write endpoint）
- **不得**使用帶 Trade 或 Withdrawal 權限的 API key
- **不得**修改 `src/signals/prev3y_momentum.py`（策略主流程）
- **不得**修改 `run008`、`TASK-002`、`TASK-003`、`TASK-007`、`TASK-008` 的任何官方輸出
- **不得**修改 `data/` 目錄下任何歷史資料
- **不得**把 Bybit API key 或 Discord webhook URL 寫入任何 source file、log、或輸出 JSON
- **不得**重跑 baseline / cost stress / attribution backtest
- **不得**自行宣稱 30-day clock 已啟動或 forward record 已開始（需 Rick 明示）
- **不得**自行宣稱 paper execution 可以執行
- **不得**在 Opus REVIEW-009 通過前 merge 回 main（若 review 被要求）

---

## 5. Inputs

### 5.1 每日 Runner 所需輸入

| 輸入 | 來源 | 說明 |
|---|---|---|
| 最新 OHLCV（前 1 日收盤 / 今日開盤） | Bybit read-only API 或本地 parquet cache | 用於 signal 計算 + hypothetical fill price |
| 近 30 天 funding rates | Bybit read-only API 或本地 parquet cache | Overlay Rule 3 用 |
| 策略 config | `configs/prev3y_crypto.yaml` | lookback、universe、signal params |
| Paper trading config | `apps/paper_trading/config.py` — `PaperTradingConfig` | overlay params（threshold / cap / etc.）|
| 前一日 positions（若存在） | `outputs/forward_record/prev3y_crypto/<PREV_DATE>_positions.parquet` | PnL delta 計算 |
| forward_summary.json（若存在） | `outputs/forward_record/prev3y_crypto/forward_summary.json` | 累積統計延續 |
| Baseline daily returns（歷史）| `outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv` | tracking error 計算用 |

### 5.2 API 存取原則

- **只使用 read-only endpoints**（`GET /v5/market/kline`、`GET /v5/market/funding/history` 等）
- 若 API 不可達：fallback 至本地 parquet cache（`data/crypto/prices_daily.parquet`、`data/crypto/funding_rates.parquet`）；記錄 `data_source: "cache_fallback"` 至 log
- **API key 透過環境變數讀取**（`BYBIT_API_KEY` / `BYBIT_API_SECRET`）；不得寫入任何輸出檔案或 log

### 5.3 Shadow-Track 額外輸入

- `src/variants/task008.py` — `apply_alpha_contribution_cap()`
- 參數：`variant="A_roll12_share20_exclude"`、`rolling_window_periods=12`、`max_alpha_share=0.20`

---

## 6. Outputs

### 6.1 Primary 每日輸出（必存）

```
outputs/forward_record/prev3y_crypto/
├── <YYYYMMDD>_positions.parquet
├── <YYYYMMDD>_pnl.json
├── <YYYYMMDD>_overlay_check.json
├── <YYYYMMDD>_forward_stats.json
└── forward_summary.json             （每日覆寫）
```

### 6.2 Shadow-Track 每日輸出（--shadow-track 啟用時）

```
outputs/forward_record/prev3y_crypto_shadow_a_roll12/
├── <YYYYMMDD>_positions.parquet
├── <YYYYMMDD>_pnl.json
├── <YYYYMMDD>_forward_stats.json
└── forward_summary.json
```

### 6.3 Runner Log

```
outputs/logs/prev3y_crypto/<YYYYMMDD>_forward_record.log
```

### 6.4 Stop Gate 觸發時額外輸出

```
outputs/forward_record/prev3y_crypto/STOP_GATE_<SX>_<YYYYMMDD>.json
```

---

## 7. Daily Record Schema

### 7a. `<YYYYMMDD>_positions.parquet`

| 欄位 | 型態 | 說明 |
|---|---|---|
| `date` | date | UTC 日期 |
| `symbol` | str | Bybit perp symbol |
| `side` | str | `long` / `short` / `flat` |
| `weight` | float | 策略權重（post-overlay） |
| `weight_raw` | float | overlay 前原始權重 |
| `funding_rate_30d_avg` | float | 近 30 天平均 funding rate（%/8h） |
| `overlay_rule1_applied` | bool | long cap 觸發 |
| `overlay_rule2_applied` | bool | symbol cap 觸發 |
| `overlay_rule3_applied` | bool | funding filter 觸發 |
| `overlay_rules_applied` | str | 觸發規則名稱（`;` 分隔） |
| `hypothetical_fill_px` | float | 假設成交價（next open） |
| `position_usd` | float | 假設持倉名義金額 USD |
| `data_source` | str | `"live_api"` / `"cache_fallback"` |
| `paper_execution_status` | str | `"FORBIDDEN"`（常數）|
| `live_trading_status` | str | `"FORBIDDEN"`（常數）|

### 7b. `<YYYYMMDD>_pnl.json`

```json
{
  "date": "YYYYMMDD",
  "variant": "combined_paper_safe_variant",
  "day_number": 1,
  "nav_usd": 10000.00,
  "nav_change_usd": 0.00,
  "daily_pnl_pct": 0.0000,
  "cumulative_pnl_pct": 0.0000,
  "gross_exposure": 0.00,
  "net_exposure": 0.00,
  "long_weight_sum": 0.00,
  "short_weight_sum": 0.00,
  "top1_symbol": "",
  "top1_symbol_weight": 0.00,
  "n_longs": 0,
  "n_shorts": 0,
  "funding_cost_usd": 0.00,
  "fee_cost_usd": 0.00,
  "slippage_cost_usd": 0.00,
  "overlay_events": [],
  "data_source": "live_api",
  "annualization": 365.25,
  "paper_execution_status": "FORBIDDEN",
  "live_trading_status": "FORBIDDEN"
}
```

### 7c. `<YYYYMMDD>_overlay_check.json`

```json
{
  "date": "YYYYMMDD",
  "variant": "combined_paper_safe_variant",
  "rule1_long_cap_50pct": {
    "triggered": false,
    "long_gross_before": 0.00,
    "long_gross_after": 0.00,
    "scale_applied": 1.0
  },
  "rule2_symbol_cap_5pct": {
    "triggered": false,
    "capped_symbols": [],
    "max_single_weight_before": 0.00
  },
  "rule3_funding_filter_0.03pct_8h": {
    "triggered": false,
    "filtered_symbols": [],
    "reduced_symbols": []
  },
  "overlay_pass": true,
  "paper_execution_status": "FORBIDDEN",
  "live_trading_status": "FORBIDDEN"
}
```

### 7d. `<YYYYMMDD>_forward_stats.json`

```json
{
  "date": "YYYYMMDD",
  "variant": "combined_paper_safe_variant",
  "day_number": 1,
  "days_elapsed": 1,
  "sharpe_rolling_30d": null,
  "sharpe_cumulative": null,
  "max_dd_pct": 0.00,
  "current_dd_pct": 0.00,
  "tracking_error_vs_baseline_30d": null,
  "calmar_ratio": null,
  "hit_rate": null,
  "annualization": 365.25,
  "ddof": 1,
  "status": "RECORDING",
  "active_warning_gates": [],
  "active_stop_gates": [],
  "review_006b_trigger_ready": false,
  "paper_execution_status": "FORBIDDEN",
  "live_trading_status": "FORBIDDEN"
}
```

### 7e. `forward_summary.json`（每日覆寫）

```json
{
  "strategy": "prev3y_crypto_combined_paper_safe_variant",
  "runner_version": "task009_v1.0",
  "start_date": "YYYYMMDD",
  "latest_date": "YYYYMMDD",
  "days_elapsed": 0,
  "days_required": 30,
  "clock_paused": false,
  "pause_reason": null,
  "sharpe_rolling_30d": null,
  "sharpe_cumulative": null,
  "max_dd_pct": 0.00,
  "tracking_error_vs_baseline_30d": null,
  "gate_status": {
    "sharpe_pass": null,
    "max_dd_pass": null,
    "overlay_always_pass": null,
    "no_stop_gate_triggered": null
  },
  "active_warning_gates": [],
  "active_stop_gates": [],
  "review_006b_trigger_ready": false,
  "paper_execution_status": "FORBIDDEN",
  "live_trading_status": "FORBIDDEN"
}
```

---

## 8. Primary / Shadow-Track 同步記錄規則

### 8.1 執行順序

```
Step 1: 取得市場資料（OHLCV + funding rates）— 兩條 track 共用
Step 2: 執行 build_prev3y_targets()（read-only）— 兩條 track 共用
Step 3a: Primary — apply_variant_overlay(variant="combined_paper_safe_variant")
Step 3b: Shadow — apply_alpha_contribution_cap(variant="A_roll12_share20_exclude", ...)
         → 再套 apply_variant_overlay(variant="combined_paper_safe_variant")
Step 4: 分別計算 PnL、overlay check、forward stats
Step 5: 分別寫入各自的輸出目錄
Step 6: Gate check（以 primary 為準）
Step 7: 更新 forward_summary.json（primary 與 shadow 各自一份）
Step 8: 若觸發 Stop gate，寫入 STOP_GATE_*.json 並記錄 clock_paused=true
```

### 8.2 獨立性原則

- Shadow-track 的輸出**永遠不影響** primary 的 gate 判定
- REVIEW-006b 啟動條件以 **primary forward_summary.json** 為唯一依據
- Shadow-track 輸出目錄為 `outputs/forward_record/prev3y_crypto_shadow_a_roll12/`（絕不寫入 primary 目錄）

### 8.3 Shadow-Track 關閉時的行為

若 `--shadow-track` 未指定（預設 off）：
- 只執行 primary
- shadow 輸出目錄不建立、不寫入
- log 中記錄 `shadow_track: disabled`

---

## 9. Warning / Stop Gates（自動檢查）

Runner 每日執行完畢後，自動評估以下 gates。

### Warning Gates（記錄，不停止 clock）

| Gate | 觸發條件 | Runner 動作 |
|---|---|---|
| W-1 | Day 30+，`sharpe_rolling_30d < 0.5`（但 ≥ −0.5） | `active_warning_gates` 加入 `W-1`；log WARNING；monitor alert |
| W-2 | `max_dd_pct ≤ -0.25`（但 > −0.30） | 同上加入 `W-2` |
| W-3 | `tracking_error_vs_baseline_30d ≥ 0.30` | 同上加入 `W-3` |
| W-4 | 連續 5 天 `overlay_pass = false`（任一 rule） | 同上加入 `W-4` |
| W-5 | Monitor heartbeat 缺失 > 2h | Monitor alert（由 TASK-005 monitor 偵測，非 runner） |
| W-6 | VPS 停機 → 輸出缺失 > 1 天 | `clock_paused = true`；`pause_reason = "W-6_data_gap"` |

### Stop Gates（clock_paused = true，通知 Rick）

| Gate | 觸發條件 | Runner 動作 |
|---|---|---|
| S-1 | `sharpe_rolling_30d < -0.5`（≥10 天資料後） | `clock_paused = true`；寫 STOP_GATE_S1.json；monitor alert CRITICAL |
| S-2 | `max_dd_pct ≤ -0.40` | 同上，S2 |
| S-3 | `tracking_error_vs_baseline_30d > 0.50` 連續 5 天 | 同上，S3 |
| S-4 | 連續 10 天 `overlay_pass = false` | 同上，S4 |
| S-5 | safety_check() 回傳 FAIL | 立即 `clock_paused = true`；exit code 1 |
| S-6 | 當日 universe < 10 symbols 或缺失 > 20% | 跳過當日（clock 不計入）；log WARNING；`days_elapsed` 不遞增 |

### Safety Check 實作

```python
def safety_check(output_dir: Path, date: str) -> bool:
    """
    必須全部通過才允許 runner 繼續。
    回傳 False 表示 FAIL，觸發 S-5。
    """
    checks = [
        _no_order_endpoint_called(),      # 確認無 Bybit 寫入 call
        _forbidden_flags_present(output_dir, date),  # 所有輸出含 FORBIDDEN 欄位
        _no_api_key_in_outputs(output_dir, date),    # 輸出中無 API key 字串
        _positions_parquet_valid(output_dir, date),  # parquet 可讀，欄位完整
    ]
    return all(checks)
```

---

## 10. REVIEW-006b 啟動條件（Runner 自動評估）

每日 `forward_stats.json` 的 `review_006b_trigger_ready` 欄位在以下**全部**條件滿足時才設為 `true`：

| 條件 | 數值門檻 | 說明 |
|---|---|---|
| `days_elapsed >= 30` | 連續 30 自然日 | 無中斷或中斷已補足 |
| `sharpe_rolling_30d >= 0.5` | Day 30 時評估 | 歷史 active Sharpe 0.9267 的 54% |
| `max_dd_pct > -0.30` | 最大 DD < 30% | 歷史 −19.64% 的 1.5× |
| `no_stop_gate_triggered` | S-1~S-6 均未觸發 | 任何 Stop gate 觸發後此條件永遠 false |
| `overlay_always_pass or exception_recorded` | 三條 overlay rule 有效 | 偏差已有記錄解釋也算通過 |

`review_006b_trigger_ready = true` 時，runner 在 log 中輸出：

```
[REVIEW-006b] All trigger conditions met. Day: {days_elapsed}.
Sharpe(30d)={sharpe_rolling_30d:.4f} MaxDD={max_dd_pct:.2%}
Action: Notify Rick. Claude to prepare REVIEW-006b packet.
Paper execution remains FORBIDDEN until Opus REVIEW-006b PASS + Rick approval.
```

**Runner 不做任何超出通知之外的動作。**

---

## 11. Reproducibility Hash

Runner 在每次執行時計算並記錄以下 hash（寫入 `<YYYYMMDD>_pnl.json` 的 `reproducibility` 欄位）：

```python
def compute_runner_hash(
    positions_parquet: Path,
    prices_snapshot: pd.DataFrame,
    funding_snapshot: pd.DataFrame,
    date: str,
) -> str:
    """
    與 TASK-008 口徑一致：
    sha256(positions_bytes + prices_json + funding_json + date)
    """
    import hashlib, json
    positions_bytes = positions_parquet.read_bytes()
    prices_bytes = prices_snapshot.to_json(orient="records", date_format="iso").encode()
    funding_bytes = funding_snapshot.to_json(orient="records", date_format="iso").encode()
    h = hashlib.sha256()
    h.update(positions_bytes)
    h.update(prices_bytes)
    h.update(funding_bytes)
    h.update(date.encode())
    return h.hexdigest()
```

Hash 格式記錄在輸出 JSON：

```json
"reproducibility": {
  "runner_version": "task009_v1.0",
  "date": "YYYYMMDD",
  "positions_hash": "sha256:...",
  "prices_snapshot_rows": 0,
  "funding_snapshot_rows": 0,
  "data_source": "live_api",
  "strategy_config_hash": "sha256:...",
  "signal_module": "src.signals.prev3y_momentum",
  "overlay_module": "apps.paper_trading.overlay"
}
```

---

## 12. Tests / Validation

### 12.1 必要單元測試（`tests/forward_record/`）

| 測試檔 | 測試內容 |
|---|---|
| `test_signal_loader.py` | `build_prev3y_targets()` 在 mock 資料下輸出正確 |
| `test_pnl_calculator.py` | daily PnL 計算公式（含 overlay 觸發 / 未觸發兩種情況） |
| `test_stats_updater.py` | Sharpe / DD / tracking error 公式與 `30_day_forward_record_plan.md` §5 一致 |
| `test_gate_checker.py` | W-1~W-6 / S-1~S-6 觸發邏輯；邊界值測試 |
| `test_report_writer.py` | 輸出 JSON/parquet schema 完整；FORBIDDEN 欄位存在 |
| `test_safety_check.py` | `safety_check()` 在有/無 FORBIDDEN 欄位時的回傳 |
| `test_market_data.py` | API fallback 邏輯（mock API 失敗 → 使用 cache）|
| `test_shadow_track.py` | shadow-track 啟用時輸出至正確目錄；不污染 primary |
| `test_no_order_endpoint.py` | 確認 runner import graph 中無任何 Bybit 寫入 endpoint 被 import |

### 12.2 統計公式驗證

Sharpe、DD、tracking error 的計算必須與 `apps/paper_trading/validator.py` 中的 `_annual_ratio()`、`_max_drawdown()` 口徑完全一致（直接 import，不重新實作）：

```python
from apps.paper_trading.validator import _annual_ratio, _max_drawdown
```

### 12.3 CLI Dry-Run 驗證

```bash
python scripts/run_forward_record.py \
  --config configs/prev3y_crypto.yaml \
  --dry-run \
  --date $(date -u +%Y%m%d) \
  --output-dir outputs/forward_record/prev3y_crypto/
```

Dry-run 行為：
- 使用 mock / cache 資料，不打真實 API
- 完整執行訊號 → overlay → PnL → stats → gate check → 輸出
- 輸出標記 `"dry_run": true`
- 任何真實外部呼叫（非 GET /market/）均 raise RuntimeError

### 12.4 Completion 驗證指令

Codex 完成後須回報以下指令全部通過：

```bash
# 單元測試
python -m unittest discover -s tests/forward_record -v

# CLI dry-run（使用 cache fallback）
python scripts/run_forward_record.py --dry-run \
  --config configs/prev3y_crypto.yaml \
  --date 20260517 \
  --output-dir /tmp/forward_record_dryrun/

# Schema 驗證
python -c "
import json, pandas
from pathlib import Path
base = Path('/tmp/forward_record_dryrun')
pnl = json.loads((base / '20260517_pnl.json').read_text())
assert pnl['paper_execution_status'] == 'FORBIDDEN'
assert pnl['live_trading_status'] == 'FORBIDDEN'
assert 'reproducibility' in pnl
pos = pandas.read_parquet(base / '20260517_positions.parquet')
assert 'paper_execution_status' in pos.columns
print('All schema checks PASS')
"

# 確認無寫入 endpoint import
python -c "
import ast, sys
from pathlib import Path
src = Path('scripts/run_forward_record.py').read_text()
tree = ast.parse(src)
forbidden = ['create_order', 'place_order', 'submit_order', 'cancel_order', 'post_order']
names = [n.id for node in ast.walk(tree) for n in ast.walk(node) if isinstance(n, ast.Name)]
hits = [f for f in forbidden if f in names]
assert not hits, f'Forbidden symbols found: {hits}'
print('No order endpoint symbols found — PASS')
"
```

---

## 13. 禁止事項（Red Lines）

```
❌ 不得提交任何委託單（paper 或 live）
❌ 不得連接 Bybit POST /v5/order/create 或任何寫入 endpoint
❌ 不得使用帶 Trade / Withdrawal / Transfer 權限的 API key
❌ 不得把 API key 或 webhook URL 寫入任何 source file、log、或輸出 JSON
❌ 不得修改 src/signals/prev3y_momentum.py（策略主流程）
❌ 不得修改 run008 / TASK-002 / TASK-003 / TASK-007 / TASK-008 的任何官方輸出
❌ 不得修改 data/ 目錄下任何歷史資料
❌ 不得重跑 baseline / cost stress / attribution backtest
❌ 不得自行宣稱 30-day clock 已啟動（需 Rick 明示「開始計時」指令）
❌ 不得自行宣稱 paper execution 可以執行（需 REVIEW-006b PASS + Rick 批准）
❌ 不得在測試中打真實 Bybit API（所有測試必須使用 mock / stub）
❌ 不得把 live_api 或 cache_fallback 的完整 response 寫入 output JSON（只存統計摘要）
❌ 不得在 Opus review 通過前 merge 回 main（若觸發 review）
```

---

## 14. Completion Report Format

Codex 完成本工單後，回報格式如下（供 Claude Sonnet 記錄 COMMAND_LOG）：

```markdown
## TASK-009 Completion Report

Date: YYYY-MM-DD
Runner version: task009_v1.0

### Files Created
- scripts/run_forward_record.py
- apps/forward_record/__init__.py
- apps/forward_record/signal_loader.py
- apps/forward_record/market_data.py
- apps/forward_record/pnl_calculator.py
- apps/forward_record/stats_updater.py
- apps/forward_record/gate_checker.py
- apps/forward_record/report_writer.py
- apps/forward_record/safety.py
- tests/forward_record/test_signal_loader.py
- tests/forward_record/test_pnl_calculator.py
- tests/forward_record/test_stats_updater.py
- tests/forward_record/test_gate_checker.py
- tests/forward_record/test_report_writer.py
- tests/forward_record/test_safety_check.py
- tests/forward_record/test_market_data.py
- tests/forward_record/test_shadow_track.py
- tests/forward_record/test_no_order_endpoint.py

### Validation Results
- Unit tests: X passed / 0 failed
- CLI dry-run: PASS / FAIL
- Schema checks: PASS / FAIL
- No order endpoint import check: PASS / FAIL

### Dry-Run Output Sample
（貼 /tmp/forward_record_dryrun/20260517_pnl.json 的關鍵欄位）

### Known Issues / Caveats
（若有）

### Forbidden Items Confirmation
- paper_execution: FORBIDDEN confirmed in all outputs ✅
- live_trading: FORBIDDEN confirmed in all outputs ✅
- No Bybit write endpoint imported ✅
- No API key in outputs ✅
- src/signals/prev3y_momentum.py not modified ✅
- Official outputs not modified ✅
```

---

## 15. 後續步驟

TASK-009 完成後，Claude 或 Rick 執行：

1. Claude 更新 `CODEX_TASK_QUEUE.md`：TASK-009 → REVIEW（或 DONE，若不需 Opus review）
2. 更新 `VPS_DEPLOYMENT_CHECKLIST.md` Phase 6：DEFERRED → ⬜ 待執行
3. 更新 `30_day_forward_start_checklist.md` §6：Phase 6 = 可執行
4. 更新 `COMMAND_LOG.md`
5. 更新 `NEXT_ACTION.md`：等待 VPS 部署完成後啟動 30-day clock

---

## 16. 文件版本

| 版本 | 日期 | 說明 |
|---|---|---|
| v1.0 | 2026-05-17 | 初版，Claude Sonnet |

---

*本工單不授權任何 paper execution 或 live trading。*
*Runner 完成後，30-day clock 仍需 Rick 明示「開始計時」指令才可啟動。*
*所有執行授權均需 Opus review PASS + Rick 明示批准。*
