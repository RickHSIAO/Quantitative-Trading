# Codex 工單 — TASK-002a：Cost / Funding Input Builder

> 這是一張可以**整份貼給 Codex** 的工單。Codex 看到這份檔案後，應先檢查資料源是否可用；若無法取得真實 funding，必須回報 BLOCKED_BY_DATA 或建立明確標註的 proxy-only config。
> 對應 queue 條目：`docs/research/CODEX_TASK_QUEUE.md` → TASK-002a。
> 對應審查條目：`docs/research/CLAUDE_REVIEW_QUEUE.md` → REVIEW-002a。

資料檢查後只可回報以下三種狀態之一：

| 狀態 | 意思 |
|---|---|
| `READY_TO_IMPLEMENT` | 可取得真實 funding 資料源（Bybit API / 既有 cache / 第三方 mirror） |
| `BLOCKED_BY_DATA` | 完全無法取得真實 funding；不可開工 |
| `NEED_CLARIFICATION` | 有資料但 symbol mapping / interval / 缺漏處理規則不清楚 |

**特別狀態**：`PROXY_ONLY` —— 真實資料部分可得、部分缺，Codex 可以建立 proxy 補洞，但 proxy_only 結果**禁止** 進 TASK-002 正式 stress；必須在 NOTE 區明示「此 run 標 `is_proxy=true` 的列不得進入 TASK-002 正式 fail gate 判斷」。

---

## 0. 給 Codex 的開場守則（每張工單都適用）

1. **一次只做一張工單**。做完進 `REVIEW`，不可自己轉 `DONE`。
2. **嚴格遵守** 第 5 節「輸入」、第 6 節「輸出」、第 13 節「禁止修改範圍」。
3. 任何超出本工單範圍的修改（順手調 baseline / 跑 stress / 改策略）——
   **停手，先在這張工單末尾留 `NOTE:` 行**，等 Rick 或 Claude 回覆。
4. 產出的 parquet / yaml 一律附 schema 文件（在 README 或 log）。
5. **本工單只建輸入，不執行 TASK-002 stress**。TASK-002 是下一棒。
6. 沒有 Claude REVIEW-002a 通過前，**不可** 把 funding_rates.parquet 視為「可用」。

---

## 1. 任務一句話

建立 TASK-002 Cost / Funding / Slippage Stress Test 所需的 3 個輸入檔案（funding_rates.parquet、fees.yaml、cost_stress.yaml），但**不執行任何 stress 計算**。

---

## 2. 任務目的

- 解除 TASK-002 的 `BLOCKED_BY_DATA` 狀態。
- 建立可被 TASK-002 與後續 attribution / forward 共用的 funding / fee 資料底層。
- 若 funding 無法取得真實資料，明確劃出 proxy 邊界，避免 TASK-002 用假資料做出錯誤結論。

---

## 3. 為什麼重要

- 真實的 funding 在 crypto perp 上是 PnL 的主要 sink（牛市末段年化可達兩位數百分點）。**若用平均化 / 隨機 / 模擬 funding 跑 TASK-002，整份 stress 報告作廢**。
- run008 baseline active period 是 2024-04-01 ~ 2026-04-30；funding 必須覆蓋這 760 個交易日。
- positions 用 Bybit perp 命名（`BYBIT:XXXUSDT.P`），funding source 通常用 `XXXUSDT`；**symbol mapping 寫錯就會大規模 silent miss**，必須在這一步驗證一次到位。

---

## 4. 範圍邊界（do / don't）

| Do | Don't |
|---|---|
| 建立 `data/crypto/funding_rates.parquet` 含 active period 覆蓋率報告 | 執行 TASK-002 stress（那是下一棒） |
| 建立 `data/crypto/fees.yaml`（單一交易所、明確口徑）| 改動 run008 任何檔案 |
| 建立 `configs/cost_stress.yaml`（12 個 scenarios 的乘數設定）| 改策略 / signals / universe / DQ / benchmark / backtester |
| 用真實 Bybit funding API / 既有 cache 為主要來源 | 用「平均 funding × 365 天」生成假資料當正式 |
| 缺資料時標 `is_proxy=true` 並 NOTE 明示 | 把 proxy 與真實 mix 後不打標籤 |
| Symbol mapping 寫成獨立函式並單元測試 | hard-code mapping 散在多處 |
| 對 active period 760 天逐日計算 coverage | 只報整體覆蓋率不報 daily |

---

## 5. 輸入檔案（**只讀**）

> 開工前先驗證以下檔案存在；缺則直接回 `BLOCKED_BY_DATA`。

### 5.1 來自 TASK-001 的不可變輸入（**只讀，不重新生成**）

- `outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet` — 用來抽 active period 內所有 PIT symbol 集合。
- `outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv` — 用來確認 active period 起訖（2024-04-01 ~ 2026-04-30）與 gross_exposure > 0 的天集合。

### 5.2 既有資料源（**只讀，可能不存在**）

- 主要候選：本機 `data/trading.db`（檢查是否有 funding_rates 表）。
- 次要候選：Bybit public API（`GET /v5/market/funding/history`）。
- 第三候選：第三方 mirror / CSV cache（若 Codex 已有）。

> 若 1 / 2 / 3 全部不可用，回報 `BLOCKED_BY_DATA`，附上嘗試紀錄。

---

## 6. 輸出檔案（路徑與 schema 嚴格固定）

1. `data/crypto/funding_rates.parquet`
   - 欄位見第 7 節。
   - 覆蓋至少 active period `2024-04-01 ~ 2026-04-30` 的所有 PIT-active symbol。
   - 不可包含未來資料（覆蓋上界 = run008 的 active_end_date）。

2. `data/crypto/fees.yaml`
   - 結構見第 8 節。

3. `configs/cost_stress.yaml`
   - 12 scenarios 完整列出；結構見第 9 節。

4. `outputs/data_quality/funding_coverage/<YYYYMMDD>_funding_coverage_report.csv`
   - 逐 symbol-day coverage report：`[date, symbol, has_funding, is_proxy, source]`
   - 讓 TASK-002 / Claude review 能直接判斷哪些 symbol-day 用真資料、哪些用 proxy。

5. `outputs/data_quality/funding_coverage/<YYYYMMDD>_funding_coverage_summary.json`
   - 欄位至少：
     - `active_period_start, active_period_end`
     - `total_pit_symbol_days_active`
     - `funded_symbol_days_active`
     - `proxy_symbol_days_active`
     - `missing_symbol_days_active`
     - `coverage_real_pct`、`coverage_proxy_pct`、`coverage_total_pct`
     - `top_missing_symbols`（top 20）

6. `outputs/logs/cost_inputs/<YYYYMMDD>_build.log`
   - 開頭必印：`random_seed`、`config_hash`、`data_snapshot_hash`、`git_commit`、`baseline_run_id=20260513_run008`。

7. `tests/cost_inputs/test_symbol_mapping.py`
   - 單元測試覆蓋 BYBIT perp ↔ funding source 的 mapping 規則（見第 11 節）。

---

## 7. `funding_rates.parquet` Schema

**必要欄位**：

| 欄位 | 型別 | 單位 / 說明 |
|---|---|---|
| `timestamp` | datetime64[ns, UTC] | funding 結算時點，UTC，**不可** 截斷到日 |
| `symbol` | string | **Bybit perp 全名格式** `BYBIT:XXXUSDT.P`（與 run008 positions 一致；若原始來源是 `XXXUSDT`，必須經 mapping 轉換後存入）|
| `exchange` | string | 例：`bybit_perp` |
| `funding_rate` | float64 | 小數（例：`0.0001` = 0.01%）；**非百分比**；正值表 long 付 short |
| `interval_hours` | int16 | 一般 perp = 8；若 Bybit 改 1h / 4h，須逐筆紀錄該筆 interval |
| `source` | string | `bybit_api` / `bybit_db_cache` / `proxy_universe_median` / `proxy_zero` 等 |
| `is_proxy` | bool | True 表本筆為 proxy；TASK-002 fail gate 須排除 proxy=True 的列 |

**強制規則**：

- timestamp 必須是 funding 實際結算時點（一般是 UTC 00:00 / 08:00 / 16:00），**不可** resample 到日。
- 缺資料的 symbol-day 一律 **不出現在 funding_rates.parquet 內**（不要 fill 0），由 coverage report 紀錄。
- 若使用 proxy，proxy 規則必須在 NOTE 區與 log 明示，且 `is_proxy=True`。
- 不可包含 active_end_date `2026-04-30` 之後的資料。
- 不可包含未在 run008 PIT universe 中出現過的 symbol（避免污染）。

---

## 8. `fees.yaml` Schema

最小版本（v1）：

```yaml
exchange: bybit_perp
maker_bps: 2.0
taker_bps: 5.5
notes: |
  Snapshot taken on 2026-05-XX from Bybit VIP-0 fee tier (USDT perp).
  Source: <URL or screenshot path>.
  These bps values are used by TASK-002 cost_stress as the baseline fee level;
  cost_stress.yaml multipliers apply on top.
```

**強制規則**：

- bps 採整體 `0.01%` 計（`taker_bps: 5.5` = 0.055% = 5.5 bps）。
- `maker_bps` 不可為 0（除非真有 0% maker 計畫，並在 notes 明確說明來源）。
- `notes` 必須含：取數日期、來源、會員等級、是否包含 fee rebate。
- 若多個 fee tier 需要支援，等 TASK-002 真正用到再加；本版只需單一 tier。

---

## 9. `cost_stress.yaml` Schema（12 scenarios）

完整檔案範本：

```yaml
version: 1
description: |
  TASK-002 Cost / Funding / Slippage Stress Test scenarios.
  Multipliers apply on top of fees.yaml base bps and funding_rates.parquet real values.
  Scenario "no_cost_baseline" must reproduce run008 portfolio_return exactly.

baseline_run_id: "20260513_run008"

defaults:
  annualization_factor: 365.25
  std_ddof: 1
  slippage_application: "per_turnover_one_side_bps"
  fee_application: "per_turnover_both_sides"
  funding_application: "pit_8h_settlement_accumulated"
  funding_proxy_policy: "exclude_from_fail_gate"

scenarios:
  - name: no_cost_baseline
    fee_multiplier_taker: 0.0
    fee_multiplier_maker: 0.0
    funding_multiplier: 0.0
    slippage_bps_one_side: 0.0
    entry_side: maker
    exit_side: maker

  - name: fee_taker_entry_maker_exit
    fee_multiplier_taker: 1.0
    fee_multiplier_maker: 1.0
    funding_multiplier: 0.0
    slippage_bps_one_side: 0.0
    entry_side: taker
    exit_side: maker

  - name: fee_taker_entry_taker_exit
    fee_multiplier_taker: 1.0
    fee_multiplier_maker: 1.0
    funding_multiplier: 0.0
    slippage_bps_one_side: 0.0
    entry_side: taker
    exit_side: taker

  - name: funding_low
    fee_multiplier_taker: 0.0
    fee_multiplier_maker: 0.0
    funding_multiplier: 0.5
    slippage_bps_one_side: 0.0
    entry_side: maker
    exit_side: maker

  - name: funding_mid
    fee_multiplier_taker: 0.0
    fee_multiplier_maker: 0.0
    funding_multiplier: 1.0
    slippage_bps_one_side: 0.0
    entry_side: maker
    exit_side: maker

  - name: funding_high
    fee_multiplier_taker: 0.0
    fee_multiplier_maker: 0.0
    funding_multiplier: 1.5
    slippage_bps_one_side: 0.0
    entry_side: maker
    exit_side: maker

  - name: slippage_5bps
    fee_multiplier_taker: 0.0
    fee_multiplier_maker: 0.0
    funding_multiplier: 0.0
    slippage_bps_one_side: 5.0
    entry_side: maker
    exit_side: maker

  - name: slippage_10bps
    fee_multiplier_taker: 0.0
    fee_multiplier_maker: 0.0
    funding_multiplier: 0.0
    slippage_bps_one_side: 10.0
    entry_side: maker
    exit_side: maker

  - name: slippage_20bps
    fee_multiplier_taker: 0.0
    fee_multiplier_maker: 0.0
    funding_multiplier: 0.0
    slippage_bps_one_side: 20.0
    entry_side: maker
    exit_side: maker

  - name: realistic_combo
    fee_multiplier_taker: 1.0
    fee_multiplier_maker: 1.0
    funding_multiplier: 1.0
    slippage_bps_one_side: 5.0
    entry_side: taker
    exit_side: maker

  - name: conservative_combo
    fee_multiplier_taker: 1.0
    fee_multiplier_maker: 1.0
    funding_multiplier: 1.0
    slippage_bps_one_side: 10.0
    entry_side: taker
    exit_side: taker

  - name: worst_case_combo
    fee_multiplier_taker: 1.0
    fee_multiplier_maker: 1.0
    funding_multiplier: 1.5
    slippage_bps_one_side: 20.0
    entry_side: taker
    exit_side: taker
```

**強制規則**：

- 12 個 scenario 名稱與本工單**一字不差**（TASK-002 工單也以此命名為準）。
- `no_cost_baseline` 全部乘數為 0、雙邊 maker、滑點 0；TASK-002 跑出來必須 = run008 baseline。
- 不可加額外的「美化情境」（例如 fee × 0.5），如果你想加，先在 NOTE 區留言問。

---

## 10. Funding 資料來源策略（**決策樹**）

按順序嘗試：

1. **本機 `data/trading.db`**：先 `PRAGMA table_info` 查是否有 funding 相關表。有 → 評估覆蓋率。
2. **本機既有 cache**：檢查 `data/cache/funding/`、`data/crypto/funding_*.parquet` 等可能位置。
3. **Bybit public API**（`GET /v5/market/funding/history`）：可離線一次性 fetch、存到 `data/cache/funding/`。**Rate-limit 與分頁要遵守 Bybit 規範**；錯誤計入 log。
4. **第三方 mirror / CSV**：若以上都不行，文件化說明來源（並寫進 NOTE）。

**proxy 規則（僅在以上都無法填滿 active period 時啟用）**：

- `proxy_universe_median`：用該日同 universe 所有真實 funding 的中位數補；`is_proxy=True`、`source="proxy_universe_median"`。
- `proxy_zero`：對極缺資料、無同類可參考的 symbol 給 0；`is_proxy=True`、`source="proxy_zero"`。**這條只能在 `proxy_universe_median` 完全 unavailable 時使用**。
- 任何 proxy 列在 TASK-002 fail gate 判斷時**必須排除**（由 `funding_proxy_policy: exclude_from_fail_gate` 規範）。

---

## 11. Symbol Mapping 規則

**問題**：run008 positions 用 `BYBIT:XXXUSDT.P`（如 `BYBIT:BTCUSDT.P`），但 Bybit funding API / 多數來源用 `XXXUSDT`（如 `BTCUSDT`）。

**規則**：

- 寫成獨立函式 `src/costs/symbol_mapping.py::to_funding_symbol(perp_symbol: str) -> str` 與反向 `to_perp_symbol(funding_symbol: str, exchange: str = "bybit_perp") -> str`。
- 邊界處理：
  - `BYBIT:BTCUSDT.P` ↔ `BTCUSDT`
  - 含特殊字符 / 重新命名的 symbol（如 `1000PEPE`）— 必須完整保留前綴，**不可** strip。
  - 若 perp_symbol 不以 `BYBIT:` 開頭或不以 `.P` 結尾，丟 `ValueError` 而非 silent skip。
- 單元測試 `tests/cost_inputs/test_symbol_mapping.py` 至少含：
  - `BYBIT:BTCUSDT.P` → `BTCUSDT` round-trip。
  - `BYBIT:1000PEPEUSDT.P` → `1000PEPEUSDT` round-trip。
  - `BYBIT:RLUSDUSDT.P` → `RLUSDUSDT`（避免 `USDT` 後綴重複切錯）。
  - 不合法輸入（如 `BTCUSDT`、`bybit:btcusdt.p`）丟 ValueError。
- `funding_rates.parquet` 內存的 symbol **一律是 `BYBIT:XXX.P` 格式**（與 positions 對齊）；原始 funding source 的 raw symbol 寫進 `source` 欄位的註解或保留 `raw_symbol` 副欄（可選）。

---

## 12. 驗收標準（逐條打勾）

- [ ] `funding_rates.parquet` 存在，schema 7 欄完整，型別正確。
- [ ] 覆蓋至少 active period `2024-04-01 ~ 2026-04-30`；上界**不超過** `2026-04-30`。
- [ ] symbol 一律為 `BYBIT:XXXUSDT.P` 格式（與 run008 positions 對齊）。
- [ ] `funding_rate` 為小數（非百分比）；隨機抽 3 個 sample 對 Bybit 官方數值。
- [ ] `interval_hours` 為 8（或交易所實際 interval）；混合 interval 須逐筆正確標示。
- [ ] **覆蓋率報告**：active period 內每個 PIT-active 的 symbol-day 都有對應的 `has_funding` 標記；real coverage % 必須 ≥ 80%（**否則須回報 BLOCKED_BY_DATA 或 PROXY_ONLY 並等指示**）。
- [ ] 缺資料的 symbol-day **不出現** 在 funding_rates.parquet 內（不 fill 0）；只在 coverage report 紀錄。
- [ ] `fees.yaml` 含 `exchange / maker_bps / taker_bps / notes` 四欄；notes 寫明取數日期 / 來源 / 會員等級 / fee rebate 處理。
- [ ] `cost_stress.yaml` 含 12 個 scenarios，名稱與本工單一字不差；defaults 區塊明示 annualization / ddof / 應用順序。
- [ ] Symbol mapping 函式有單元測試覆蓋至少 4 個邊界 case 並全綠。
- [ ] log 開頭印 `random_seed`、`config_hash`、`data_snapshot_hash`、`git_commit`、`baseline_run_id=20260513_run008`、`funding_source`、`funding_proxy_pct`。
- [ ] 任何 proxy 列在 funding_rates.parquet 中 `is_proxy=True` 且 source 標明 proxy 類別。
- [ ] 不可包含未在 run008 PIT universe 內出現過的 symbol。

---

## 13. 禁止修改範圍

- 不可動 run008 任何輸出檔（`outputs/backtests/prev3y_crypto/20260513_run008_*`）。
- 不可動 `src/signals/`、`src/backtest/`、`src/universe/`、`src/data_quality/`、`src/reporting/`。
- 不可動 `configs/prev3y_crypto.yaml`。
- 不可動 raw data 表（`data/trading.db` 內既有 schema 不改）。
- 不可執行 TASK-002 stress（這是下一棒、由 Claude REVIEW-002a PASS 後才啟動）。
- 不可在缺資料時用「平均 funding」「歷史均值」「假隨機」當 **正式** funding；只能用 documented proxy 並標 `is_proxy=True`。
- 不可調策略參數、cost 公式、ranking、benchmark 定義。
- 不可在沒有 Claude REVIEW-002a 通過前 merge 回 main。

---

## 14. 完成後請回報以下 7 件事

請把回覆貼回對話，**逐點列出**，方便 Claude 開 REVIEW-002a：

1. **整體狀態**：`READY_TO_IMPLEMENT` / `BLOCKED_BY_DATA` / `NEED_CLARIFICATION` / `PROXY_ONLY` 四選一。
2. **覆蓋率數字**：active period 內 real / proxy / missing 各自的 symbol-day 數與百分比。
3. **資料來源**：funding 主要源（Bybit API / db cache / 其他）；fees 取數日期與來源 URL。
4. **Symbol mapping 邊界 case**：列出最容易出錯的 5 個 symbol 與 mapping 結果（含 RLUSD / 1000PEPE 之類）。
5. **Proxy 使用情況**：是否用了 proxy、用在哪些 symbol-day、proxy 規則、單元測試覆蓋。
6. **檔案位置**：四份輸出檔的絕對路徑 + 三件套 schema 文件位置。
7. **未做 / 暫緩**：本工單範圍內你決定先不做的事項（理由）。

完成後狀態改為 `REVIEW`，等 Claude 進 REVIEW-002a。

---

## 15. NOTE 區（Codex 留言處）

> 任何超出範圍的疑問、發現、暫存決策都寫在這。

- _（待 Codex 填寫）_
