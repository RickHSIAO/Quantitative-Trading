# Codex 工單 — TASK-002：Cost / Funding / Slippage Stress Test（**v2**）

> 這是一張可以**整份貼給 Codex** 的工單。Codex 看到這份檔案後，應先檢查 baseline 與 funding / fees 輸入是否存在；若資料缺失或 `is_proxy` 有 True 列，不可開工，必須回報 BLOCKED_BY_DATA。
> 對應 queue 條目：`docs/research/CODEX_TASK_QUEUE.md` → TASK-002。
> 對應審查條目：`docs/research/CLAUDE_REVIEW_QUEUE.md` → REVIEW-002。

資料檢查後只可回報以下三種狀態之一：

| 狀態 | 意思 |
|---|---|
| `READY_TO_IMPLEMENT` | run008 三件套 + funding（is_proxy 全 False）/ fees / cost_stress 輸入齊備，可實作 |
| `BLOCKED_BY_DATA` | 缺 funding_rates / fees / cost_stress；或 funding_rates 內含 `is_proxy=True` 列；或 run008 檔案異常 |
| `NEED_CLARIFICATION` | 有資料但情境參數、保證金 / 計息口徑、benchmark 對齊規則不清楚 |

---

## v2 Change Log

| 版本 | 日期 | 主要變更 |
|---|---|---|
| v1 | 2026-05-13 | 初版；假設 funding 為固定 8h 結算（每天 3 次）。 |
| **v2** | **2026-05-14** | **「funding 固定 8h」假設被 Bybit 實際資料推翻**——Phase 2 full fetch（REVIEW-002a_phase2_full PASS）發現 273 個 PIT symbol 的 funding interval **是混合的**（1h: 1 / 4h: 145 / 8h: 127）。v2 完成的更新：(1) 全工單把 8h 改為 per-interval；(2) cost_stress.yaml defaults `funding_application` 從 `pit_8h_settlement_accumulated` 改為 `pit_per_interval_settlement_accumulated`；(3) 新增 Bybit interval 分布 caveat；(4) 新增 known-gap 7 symbols 處理（XTZ / FLOW / LPT / AXS / RVN / INJ / CTC）；(5) 新增 outlier contribution breakdown（abs ≥ 0.01、max abs = 0.05）；(6) 新增兩條 WARNING gate（funding gap > 5% / outlier contribution > 30%）；(7) 明確要求 TASK-002 只在 TASK-002a PASS 後執行、funding_rates.parquet 內 `is_proxy` 全 False。 |

**TASK-002 目前狀態（v2 發布時刻）**：`BLOCKED_BY_WORKORDER_UPDATE` → 工單 v2 落地後 Codex 必須**重新跑 readiness check** 才能轉成 READY_TO_IMPLEMENT / BLOCKED_BY_DATA / NEED_CLARIFICATION 之一。

---

## 0. 給 Codex 的開場守則（每張工單都適用）

1. **一次只做一張工單**。做完進 `REVIEW`，不可自己轉 `DONE`。
2. **嚴格遵守** 第 5 節「輸入」、第 6 節「輸出」、第 13 節「禁止修改範圍」。
3. 任何超出本工單範圍的修改（順手重構 backtester、改 strategy 模組、調 universe）——
   **停手，先在這張工單末尾留 `NOTE:` 行**，等 Rick 或 Claude 回覆。
4. 產出的 CSV / parquet 一律附 schema（欄位名、型別、單位）寫在 log 或 README。
5. 沒有 Claude REVIEW-002 通過前，**不可** 把實驗分支 merge 回 main。
6. cost / funding / slippage 模組必須獨立在 `src/costs/` 底下；**不可** 寫進 `src/signals/`、`src/backtest/`、`src/data_quality/`、`src/reporting/`。
7. **run008 是輸入，不是輸出**。本任務從 run008 讀 positions / baseline，自己不重新跑回測引擎。
8. **TASK-002a 必須先 PASS**：`data/crypto/funding_rates.parquet` 必須存在、`is_proxy` 全 False、source 全部為 `bybit_api`。若不滿足 → 回 `BLOCKED_BY_DATA`。

---

## 1. 任務一句話

在不動 run008 baseline 的前提下，加入交易成本、滑價、per-interval funding stress 並建立至少 12 個情境，產出一份「策略在實盤摩擦下還活著嗎」的壓力測試報表。

---

## 2. 任務目的

- 為 TASK-001（active Sharpe 0.9267、active IR vs eqw +0.7227）做 reality check：扣掉 fee × per-interval funding × slippage 後 edge 還在嗎？
- 找出 `realistic / conservative / worst_case` 三種綜合情境下 IR / Sharpe / DD 的退化幅度。
- 為 TASK-003 attribution 與後續上線決策提供「成本敏感度」素材。

---

## 3. 為什麼重要

- TASK-001 三組 IR 的計算都是 **gross**（無 fee、無 funding、無 slippage）。Crypto perp 的 funding 在牛市末段可以年化吃掉幾十個百分點；只看 gross PnL 會嚴重高估策略。
- **Bybit funding interval 不是統一 8h**：在我們的 PIT universe 273 symbols 裡，145 個是 4h（每天 6 次結算）、127 個是 8h（每天 3 次）、1 個是 1h（每天 24 次）。若硬寫成 8h，4h symbols 的 funding 會被低估一半、1h symbol 會被低估 ~96%。
- 真錢上線前必須知道：在 fee × 2、funding × 1.5、滑點翻倍的情境下，IR 還剩多少。
- 這是區分「論文型 alpha」與「能上線的 alpha」的關鍵 gate。**TASK-002 沒過，TASK-001 的 +0.72 alpha 直接作廢**。

---

## 4. 範圍邊界（do / don't）

| Do | Don't |
|---|---|
| 從 run008 讀取 positions / baseline 作為輸入 | **重新跑回測引擎**（策略邏輯絕對不動） |
| 新增 `src/costs/` 模組（fee / funding / slippage 三個子層）| 把 cost 寫進 `src/signals/` 或 `src/backtest/` 或 `src/data_quality/` |
| 至少 12 個 stress scenarios（見第 7~10 節）| 自行新增「優化過」的情境（例如 fee × 0.5）以美化結果 |
| Active 口徑為主要判讀，full 口徑仍輸出 | 只報 full 口徑或只報 active 口徑 |
| 所有 scenario 都對 run008 baseline（= no_cost）做差分 | 用 run002 / 003 / 004 / 007 為對照基準 |
| **funding 依 `funding_rates.parquet` 每列的 `timestamp` 與 `interval_hours` 累加** | **假設固定 8h** 結算（v1 的舊規則）|
| slippage 用 bps × notional 對 turnover 計息 | 把 slippage 寫成固定金額 |
| 對已知 funding gap 7 symbols 標 `funding_gap=True`（見第 8 節）| 對缺 funding 的 symbol-day 用 fill 0 或 fill 平均值 |
| 對 outlier（abs ≥ 0.01）照實累加並在 summary 拆解貢獻 | 截斷 / 刪除 / 修正 outlier funding 值 |
| 在 stats.json 寫 `methodology` + `cost_policy` 兩個區塊 | 把成本公式 hard-code 在程式裡不文件化 |
| 重跑兩次內容 hash 應一致（content hash，非檔案 SHA-256） | 改不同 seed / cache key 就視為不同結果 |

---

## 5. 輸入檔案

> 開工前先驗證以下檔案存在且 schema 正確，並驗證 `funding_rates.parquet` 內 `is_proxy` 全 False。缺資料 / 含 proxy → `BLOCKED_BY_DATA`。**禁止** 生成隨機 / 模擬 funding rates。

### 5.1 來自 TASK-001 的不可變輸入（**只讀**）

- `outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv`
- `outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet`
- `outputs/backtests/prev3y_crypto/20260513_run008_stats.json`
- `outputs/logs/prev3y_crypto/20260513_run008.log`

### 5.2 來自 TASK-002a 的不可變輸入（**只讀**）

- `data/crypto/funding_rates.parquet`（TASK-002a Phase 2 full fetch 產出）
  - 欄位：`[timestamp, symbol, exchange, funding_rate, interval_hours, source, is_proxy]`
  - active period 2024-04-01 ~ 2026-04-30 real coverage active position 98.84%、active PIT 97.56%。
  - **驗證項**：
    - `is_proxy` 必須全部 False（任一 True → BLOCKED_BY_DATA）。
    - `source` 必須全部 `bybit_api`。
    - `interval_hours` 必須在 `{1, 4, 8}` 之內。
    - symbol 必須在 run008 PIT universe 內。
  - 必須是 PIT、UTC、未調整、未平滑。
- `data/crypto/fees.yaml`
  - 結構：
    ```yaml
    exchange: bybit_perp
    maker_bps: 2.0
    taker_bps: 5.5
    notes: |
      Snapshot date / source URL / tier (VIP 0 / Non-VIP) / fee rebate.
    ```
- `configs/cost_stress.yaml`（TASK-002a 已建立的 12 scenarios）
  - **本 v2 工單要求把 defaults 區塊更新為**：
    ```yaml
    defaults:
      annualization_factor: 365.25
      std_ddof: 1
      slippage_application: "per_turnover_one_side_bps"
      fee_application: "per_turnover_both_sides"
      funding_application: "pit_per_interval_settlement_accumulated"  # v2: was pit_8h_settlement_accumulated
      funding_proxy_policy: "exclude_from_fail_gate"
      funding_interval_policy: "use_interval_hours_per_row"            # v2 新增
      funding_gap_policy: "mark_funding_gap_true_no_fill"               # v2 新增
      outlier_policy: "report_no_clamp"                                  # v2 新增
    ```
  - 開工前 Codex 必須**先 commit cost_stress.yaml defaults 的更新**（且 v1 的 `pit_8h_settlement_accumulated` 必須在這次 commit 內被取代），才能往下執行。

### 5.3 既有 config（**只讀**）

- `configs/prev3y_crypto.yaml`（取 `entry_price`, `start_date`, `end_date`）。
- `configs/prev3y_crypto.yaml` 內 `benchmark` 區塊（取 primary、btc_symbol）。

---

## 6. 輸出檔案（路徑與欄位嚴格固定）

> 檔名中的 `<YYYYMMDD>` 是執行當日（UTC）。一旦寫出，**不可覆寫**，需另開日期。

1. `outputs/backtests/prev3y_crypto/<YYYYMMDD>_cost_stress.csv`
   每日每情境一列；欄位：
   - `date, scenario, portfolio_return_gross, portfolio_return_net, fee_cost, funding_cost, slippage_cost, gross_exposure, turnover, net_exposure`
   - 約束：`portfolio_return_net = portfolio_return_gross − fee_cost − funding_cost − slippage_cost`（每列誤差 < 1e-8）。

2. `outputs/backtests/prev3y_crypto/<YYYYMMDD>_cost_stress_summary.json`
   每個 scenario 一組（**逐欄都要 full / active 兩份**）：
   - `total_return_full / total_return_active`
   - `sharpe_full / sharpe_active`
   - `ir_vs_cash_full / ir_vs_cash_active`
   - `ir_vs_btc_full / ir_vs_btc_active`
   - `ir_vs_equal_weight_full / ir_vs_equal_weight_active`
   - `max_dd_full / max_dd_active`
   - `calmar_full / calmar_active`
   - `turnover_annual_full / turnover_annual_active`
   - `total_fee_cost`
   - `total_slippage_cost`
   - `total_funding_cost`
   - `cost_per_turnover`（= 總 cost / 總 turnover，bps）
   - `net_alpha_decay_vs_run008`（active IR_vs_eqw 相對 run008 的下降百分點）
   - `effective_days_active`（沿用 run008 = 760）
   - **v2 新增** `funding_gap_breakdown`：{`active_position_symbol_days_with_gap`, `pct_of_active_position`, `per_symbol_breakdown`}
   - **v2 新增** `outlier_contribution_breakdown`：{`outlier_count`, `max_abs_funding_rate`, `outlier_funding_cost`, `outlier_pct_of_total_funding_cost`}
   - **v2 新增** `interval_distribution_used`：{`1h_rows`, `4h_rows`, `8h_rows`}（從本次實際引用的 funding rows 統計）
   - 必須含 top-level `methodology` 與 `cost_policy` 兩個區塊。

3. `outputs/backtests/prev3y_crypto/<YYYYMMDD>_cost_stress_positions_cost.parquet`
   逐 symbol-day 的成本拆解（讓 attribution 與後續審查能對得回去）：
   - `date, scenario, symbol, weight, fee_cost, funding_cost, slippage_cost, funding_gap, outlier_count_today`
   - **v2 新增** `funding_gap`（bool）：該 symbol-day 是否屬 7 個 known-gap symbols 且該日沒有 funding 列 → True。
   - **v2 新增** `outlier_count_today`（int）：該 symbol-day 內 abs ≥ 0.01 的 funding 結算次數。

4. `outputs/logs/prev3y_crypto/<YYYYMMDD>_cost_stress.log`
   開頭必印：`random_seed`、`config_hash`、`data_snapshot_hash`、`git_commit`、`baseline_run_id=20260513_run008`、`funding_rates_parquet_hash`、`scenarios_count`、`interval_distribution_used`。

---

## 7. 成本情境設計（fee scenarios）

| Scenario | maker bps | taker bps | 進場側 | 出場側 | 備註 |
|---|---:|---:|---|---|---|
| `no_cost_baseline` | 0 | 0 | maker | maker | = run008，做 sanity check 之用 |
| `fee_taker_entry_maker_exit` | 2.0 | 5.5 | taker | maker | 反映多數實盤習慣 |
| `fee_taker_entry_taker_exit` | 2.0 | 5.5 | taker | taker | 緊急平倉 / 抓不到 maker 場景 |

> fee 對每次 turnover 雙邊計算（賣舊 + 買新）。每月 rebalance 的 turnover 在 baseline.csv 已給出，**禁止** 用 round-trip 假設 / 平均化簡化。

---

## 8. Funding 情境設計（**v2 per-interval**）

| Scenario | funding 乘數 | 備註 |
|---|---:|---|
| `funding_low` | × 0.5 | 「實盤可能比歷史好」的樂觀情境 |
| `funding_mid` | × 1.0 | 直接套 PIT funding_rates 內每筆實際結算 |
| `funding_high` | × 1.5 | 牛市末段 / 擁擠多單 funding 拉高 |

### 8.1 **核心規則：per-interval settlement accumulated**

- funding cost 必須以 **funding_rates.parquet 內每筆 funding row 實際結算累加**：
  - 對每筆 row（`(timestamp, symbol, funding_rate, interval_hours)`），若該 timestamp 落在該 symbol 的持倉時段內：
    - `single_settlement_funding_payment = position_notional × funding_rate × funding_multiplier`
    - long 付 funding（funding_rate > 0 時）；short 收 funding（symbol 是 short leg 時符號相反）。
  - 該 symbol-day 的 funding cost = 該日所有 funding settlements 的累加（**1h: 24 次 / 4h: 6 次 / 8h: 3 次**）。
- **禁止** 假設固定 8h、不可用日平均 funding rate、不可用月末快照。

### 8.2 **Bybit 實際 interval 分布（v2 caveat）**

Phase 2 full fetch 後對 PIT universe 273 symbols 的 interval 統計：

| Interval | Symbols 數 | Funding rows | 範例 |
|---:|---:|---:|---|
| 1h | 1 | 2,758 | 1 個短週期 symbol |
| 4h | 145 | 461,513 | 多數小幣 / 中小幣（XCN、POLYX、ENJ…）|
| 8h | 127 | 286,370 | BTC / ETH / 主流大幣 |

**這代表 cost engine 必須處理每天可能有 1 / 3 / 6 / 24 個 funding 結算的所有情況。**

### 8.3 **Known funding gap symbols（v2 新增）**

下列 7 個 symbol 在 active position 範圍內有 funding 缺料（TASK-002a Phase 2 full fetch 報告）：

`XTZ / FLOW / LPT / AXS / RVN / INJ / CTC`

對這 7 個 symbol，**若某 symbol-day 在 funding_rates.parquet 內無對應 funding 列**：
- 該 symbol-day 的 funding cost **設為 0** 並在 positions_cost.parquet 標 `funding_gap=True`。
- **禁止** fill 假設值（不可用同 symbol 鄰近日的 funding、不可用 universe median、不可用 0 而不標）。
- summary.json 內 `funding_gap_breakdown` 區塊必須列出每個 known-gap symbol 在本次 stress 內影響的 symbol-day 數與比例。

### 8.4 **Outlier 處理（v2 新增）**

Phase 2 full fetch 發現 **653 筆** funding row 的 `abs(funding_rate) >= 0.01`（1%），最大 `abs = 0.05`（5%）。

對 outlier 列的處理：
- **照實累加**：不截斷、不修正、不刪除。
- positions_cost.parquet 每列加 `outlier_count_today`（int）：該 symbol-day 內 abs ≥ 0.01 的 funding settlements 次數。
- summary.json `outlier_contribution_breakdown` 區塊必須列出：
  - `outlier_count`：本次 stress 引用到的 outlier row 數。
  - `max_abs_funding_rate`：≥ 0.05。
  - `outlier_funding_cost`：outlier rows 貢獻的總 funding cost（不分情境，先給絕對值）。
  - `outlier_pct_of_total_funding_cost`：每個 combo 情境（realistic / conservative / worst_case）下 outlier 佔該情境總 funding cost 的百分比。

---

## 9. Slippage 情境設計

| Scenario | per-turnover slippage（bps） | 備註 |
|---|---:|---|
| `slippage_5bps` | 5 | 高流動性幣的典型滑點 |
| `slippage_10bps` | 10 | 中段幣 / 一般情境 |
| `slippage_20bps` | 20 | 小幣 / 急單 / 不利時段 |

> Slippage 對每次 turnover 單邊計算（即 entry 5bps、exit 5bps，雙邊共 10bps in `slippage_5bps`）。請在 log 明示這個雙邊規則。

---

## 10. 綜合情境

| Scenario | fee | funding | slippage | 用途 |
|---|---|---|---|---|
| `realistic_combo` | taker entry + maker exit | × 1.0 | 5bps | 真錢上線最常見假設 |
| `conservative_combo` | taker entry + taker exit | × 1.0 | 10bps | 上線審慎假設 |
| `worst_case_combo` | taker entry + taker exit | × 1.5 | 20bps | 危機 / 流動性枯竭，壓力上限 |

12 個 scenario 共：`no_cost_baseline` × 1 + fee × 2 + slippage × 3 + funding × 3 + combo × 3 = 12。

---

## 11. 驗收標準（逐條打勾）

- [ ] 12 個 scenarios 全部產出（命名與本工單 v2 一字不差）。
- [ ] `cost_stress.csv` 每列滿足 `net = gross − fee − funding − slippage` 誤差 < 1e-8。
- [ ] `no_cost_baseline` 的 portfolio_return_net 與 run008 baseline.csv `portfolio_return` **逐列相等**（差 = 0）。
- [ ] **v2** funding 計算為 **per-row（依每筆 funding settlement 的 timestamp 與 interval_hours）累加**；audit log 抽至少 3 個 sample 顯示某幣某日的 funding cash flow 計算過程，每個 sample 必須含「該日有幾次結算 / 每次的 timestamp / 每次的 funding_rate / 每次的 position_notional / 該日 funding cost 加總」。
- [ ] **v2** audit log 抽樣必須涵蓋 3 種 interval：1 個 1h symbol、1 個 4h symbol、1 個 8h symbol。
- [ ] fee 同時涵蓋 entry + exit + rebalance 中的雙邊。
- [ ] slippage 採每次 turnover 單邊 bps，整體雙邊。
- [ ] 任一情境下若 active Sharpe < 0.5 或 active IR_vs_eqw < 0.2，summary.json 內顯眼標 `WARNING`。
- [ ] 任一情境下 max DD 比 run008 惡化超過 1.5 倍（即 < −29.25%），標 `WARNING`。
- [ ] 任一情境下 `cost_per_turnover × turnover_annual_active > 0.7 × active_alpha_run008`（即成本吃掉 70% 以上 alpha），標 `WARNING`。
- [ ] **v2** `funding_gap_breakdown` 完整：列出 7 個 known-gap symbols 在本次 stress 內的 affected symbol-days；任一情境下 `pct_of_active_position > 5%` 標 `WARNING`。
- [ ] **v2** `outlier_contribution_breakdown` 完整；任一 combo 情境下 `outlier_pct_of_total_funding_cost > 30%` 標 `WARNING`。
- [ ] **v2** `interval_distribution_used` 與 funding_rates.parquet 全集分布**比例相當**（容差 ±10 個 row）；若某 interval 完全沒被引用（如 1h 0 rows）須在 log 明示。
- [ ] `summary.json` 內 active 口徑與 full 口徑都齊備。
- [ ] `methodology` 區塊明示：annualization=365.25、std_ddof=1、IR 公式、Sortino 公式、cost 對 PnL 的應用順序（gross → fee → funding → slippage → net）。
- [ ] `cost_policy` 區塊明示：fee 雙邊規則、**v2** per-interval funding 累加規則、known-gap policy、outlier policy、slippage 雙邊規則。
- [ ] 同 config × 同 data snapshot 重跑兩次 → **content hash 一致**（不是檔案 SHA-256；遵循 TASK-002a 同 convention）。
- [ ] log 開頭印 `random_seed`、`config_hash`、`data_snapshot_hash`、`git_commit`、`baseline_run_id=20260513_run008`、`funding_rates_parquet_hash`、`interval_distribution_used`、`scenarios_count`。

---

## 12. Fail / Warning gate（**Codex 自己跑完要先檢查並在 summary 內標出**）

| 條件 | 等級 | 行動 |
|---|---|---|
| `realistic_combo` active Sharpe < 0.5 | **FAIL** | summary.json 加 `verdict: FAIL`；交付後等 Claude 開 REVIEW-002 判斷研究路線是否淘汰 |
| `realistic_combo` active IR vs equal-weight < 0.2 | **FAIL** | 同上 |
| `conservative_combo` active IR vs equal-weight < 0 | **FAIL** | 同上 |
| `worst_case_combo` 任何指標 | 僅參考 | 不直接淘汰；標 `pressure_only` |
| `realistic / conservative` 任一 max DD 惡化 > 1.5 × run008（−19.5% → −29.25%）| **WARNING** | 在 summary 標出，但不直接 FAIL |
| 任一情境成本吃掉 active alpha > 70% | **WARNING** | 在 summary 標出 |
| **v2** 任一情境 `funding_gap_breakdown.pct_of_active_position > 5%` | **WARNING** | 結果被 known-gap symbols 大量影響，需在 review 內檢視 |
| **v2** 任一 combo 情境 `outlier_pct_of_total_funding_cost > 30%` | **WARNING** | 結果被少數 outlier funding row 主導，可信度下降 |

---

## 13. 禁止修改範圍

- 不可動 `data/` 下的 raw 檔。
- **不可動 `data/crypto/funding_rates.parquet`**（TASK-002a 的不可變產物；包含 outlier / known-gap 都不准修改）。
- 不可動 `src/signals/`、`src/backtest/`、`src/universe/`、`src/data_quality/`、`src/reporting/`。
- 不可動 `configs/prev3y_crypto.yaml`。
- **不可** 動或重新生成 `outputs/backtests/prev3y_crypto/20260513_run008_*` 任何檔案。
- 不可調策略參數（lookback / top_n / bottom_n / rebalance_freq / ranking_method / entry_price 全部禁止改動）。
- 不可改 benchmark 定義（cash / btc_perp / equal_weight_long_only）。
- 不可改 DQ policy（missing return = exclude, nonpositive OHLC = hard exclude）。
- 不可把 cost / funding / slippage 邏輯寫進 strategy module、signal module、backtester、DQ module、benchmark module。
- **v2** 不可硬寫 funding 為固定 8h；不可把 4h funding 折半成「等效 8h」、不可把 1h funding 折成「等效 8h」。
- 不可用平均 funding rate / 月末快照當 funding cost。
- 不可在缺資料時生成隨機 / 模擬 funding rates。
- 不可截斷 / 刪除 / 修正 outlier funding 值。
- 不可對 known-gap 7 symbols 的缺料 symbol-day 用 fill 0 而不標、不可用同 symbol 鄰近日 funding fill。
- 不可額外加 scenario 來「美化」結果（例如 fee × 0.5）。如果想加情境，先在 NOTE 區留言問。
- 不可在沒有 Claude REVIEW-002 通過前 merge 回 main。
- **funding_rates.parquet 內若有任一列 `is_proxy=True`**：立即停手回 `BLOCKED_BY_DATA`（v2 與 TASK-002a 約定一致）。

---

## 14. 完成後請回報以下 9 件事（**v2 從 7 件擴為 9 件**）

請把回覆貼回對話，**逐點列出**，方便 Claude 開 REVIEW-002：

1. **三個 combo 情境的 4 個關鍵數字**：active Sharpe、active IR_vs_eqw、active IR_vs_btc、active max DD（共 12 個數字）。
2. **Fail gate 評估**：FAIL / WARNING 條件逐條目前哪些觸發、哪些未觸發（含 v2 新增的兩條 WARNING）。
3. **資料異常清單**：funding / fees / slippage 各層的 missing / outlier 列表；funding 部分必須含 `funding_gap_breakdown` 與 `outlier_contribution_breakdown` 摘要。
4. **可重現性證據**：兩次重跑 `summary.json` 的 **content hash** 是否一致。
5. **net = gross − fee − funding − slippage 校驗**：抽 3 個 symbol-day 把每筆成本逐項對齊。
6. **與 run008 對齊**：`no_cost_baseline.portfolio_return_net` vs run008 `portfolio_return` 是否逐列相等（差 = 0）。
7. **v2 per-interval 累加 audit**：抽 3 個 sample（1h / 4h / 8h 各 1 個 symbol-day），列出該日每次 funding settlement 的 timestamp、funding_rate、position_notional、單次 cost、當日加總 cost。
8. **v2 interval_distribution_used**：本次實際引用的 funding rows 中 1h / 4h / 8h 各幾筆，比對 funding_rates.parquet 全集分布是否成比例。
9. **未做 / 暫緩**：本工單範圍內你決定先不做的事項（理由）。

完成後狀態改為 `REVIEW`，等 Claude 進 REVIEW-002。

---

## 15. NOTE 區（Codex 留言處）

> 任何超出範圍的疑問、發現、暫存決策都寫在這。

- _（待 Codex 填寫）_
