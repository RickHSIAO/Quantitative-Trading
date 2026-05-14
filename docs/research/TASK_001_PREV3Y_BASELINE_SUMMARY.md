# TASK-001 Prev3Y Crypto Universe Baseline 研究進度總整理

> **本文件是一份獨立的總整理（standalone summary）**，目的是讓未來的 Codex、Claude、ChatGPT 或 Rick 不用翻完整對話也能在 5 分鐘內掌握 TASK-001 的當前狀態。如需細節，請對照：
> - `docs/research/AI_WORKFLOW.md`（分工守則）
> - `docs/research/CODEX_TASK_QUEUE.md`（Codex 工作 queue）
> - `docs/research/CLAUDE_REVIEW_QUEUE.md`（Claude 審查 queue）
> - `docs/research/CLAUDE_REVIEW_LOG.md`（每次審查的完整紀錄）
> - `docs/research/codex_workorders/TASK-001_prev3y_crypto_baseline.md`（原始工單）
>
> 最後更新：2026-05-13
> 維護者：Claude（總管 / 審查）

---

## 1. 研究目標

驗證 **Prev3Y momentum 概念** 在 crypto universe 上是否成立，並提供一份乾淨可重現的 baseline 回測，作為後續所有研究（cost stress、attribution、dashboard、forward）的對照組。

研究假設：

- 用過去約 3 年（lookback 1095 日）的累積報酬作為動能訊號，月度 rebalance、long top-N / short bottom-N，在 crypto 上應該能產生正的風險調整後超額報酬。
- 預期是「approximately market-neutral L/S」結構，而非 long-only beta。

成功 / 失敗的判斷：

- 不在這個 baseline 階段下「保留 / 淘汰」結論。
- 此階段只負責**把乾淨數字產出來**；後續 cost stress、attribution 才會決定是否進入 forward。

---

## 2. 使用資料與回測範圍

| 項目 | 內容 |
|---|---|
| 訊號 | Prev3Y cumulative return ranking |
| Lookback | `1095` 日（calendar） |
| Rebalance | 每月 |
| Top-N / Bottom-N | 25 / 25（多空各取） |
| Entry price | t+1 open |
| 訊號使用價 | t–1 close |
| 名目回測期間 | `2019-01-01` ~ `2026-04-30`（2677 calendar days） |
| Warm-up | `2018-01-01` 起 |
| 實際有效持倉期間 | **`2024-04-01` ~ `2026-04-30`（760 天）** |
| Active fraction | `28.39%` |
| Universe | Bybit perpetual symbols，每日 PIT 名單 |
| 平均 universe size | 76.79 |
| 平均 tradable symbols | **15.22**（遠低於 top_n + bottom_n = 50） |
| 資料來源 | `data/trading.db` 的 `prices` / `crypto_market_cap_rankings` / `crypto_bybit_linear_instruments`，由 `scripts/validate_prev3y_crypto_inputs.py` gate |
| 原始 OHLCV 起始 | `2020-10-21` |

> **重要**：name-of-record 上回測涵蓋 2019-01 ~ 2026-04，但因 OHLCV 從 2020-10-21 才開始，加上 3 年 lookback 需要累積，**第一個實際持倉日是 2024-04-01**。所有「全期」數字都包含 1917 個零部位天，會嚴重稀釋分子分母——這是 active 口徑存在的原因。

---

## 3. 已完成的 run 對照表

| Run | 日期 | 目的 | 對應 task | 對應 review | Codex 狀態 |
|---|---|---|---|---|---|
| `20260513_run002` | 2026-05-13 | TASK-001 baseline 初版（單 IR、單口徑） | TASK-001 | REVIEW-001 | 已被 003 / 004 取代為報表口徑，策略產出仍是 run002 之底 |
| `20260513_run003` | 2026-05-13 | TASK-001c：加入 `*_full / *_active` 雙口徑 | TASK-001c | REVIEW-001c | **DONE** |
| `20260513_run004` | 2026-05-13 | TASK-001b：三 benchmark + IR + methodology 區塊 | TASK-001b | REVIEW-001b | **DONE** |
| `20260513_run007` | 2026-05-13 | TASK-001d：missing-data data-quality layer + DQ summary | TASK-001d | REVIEW-001d | **REVIEW** |

三個 run 的策略產出（`positions.parquet`、`baseline.csv` 中的策略欄位 portfolio_return / gross / net / turnover / n_longs / n_shorts）**完全相同**（byte-identical / 逐列相等），證明補件期間策略未被動到。

### 3.1 每個 run 的差異

#### run002 — baseline 初版（TASK-001）

- 第一份完整 baseline。產出 baseline.csv、positions.parquet、stats.json、log。
- 單口徑（全期 2677 天）、單 benchmark（同日 PIT 等權 long-only）。
- 通過所有形式驗收（PIT、t-1/t+1、可重現性）。
- **但**：headline Sharpe 0.49 / IR −0.06 數字會誤導，因為混合了 1917 個零部位天，且 benchmark 選錯。

#### run003 — 雙口徑（TASK-001c）

- baseline.csv 與 positions.parquet **與 run002 byte-identical**（SHA-256 一致）。
- stats.json 新增 12 對 `*_full / *_active` 指標。
- log 明說「primary interpretation should use `*_active`」。
- 舊欄位 (`ir / sharpe / sortino / max_dd / calmar / turnover_annual / hit_rate`) 全部變成 `*_full` 的 alias。
- 解決了「全期 vs 有效期」口徑混淆。

#### run004 — 三 benchmark（TASK-001b）

- baseline.csv 新增 3 個 benchmark 欄位：`benchmark_cash_return / benchmark_btc_return / benchmark_eqw_return`。
- `benchmark_return` 改指向 `benchmark_cash_return`（primary 改為 cash）。
- stats.json 新增 6 個 IR：`ir_vs_<cash|btc|equal_weight>_<full|active>`。
- **新增 `methodology` 區塊**：annualization=365.25、std_ddof=1、IR / Sortino 公式都明示。
- positions.parquet **與 run003 byte-identical**；baseline 策略欄位逐列等值。
- 新模組：`src/reporting/prev3y_benchmarks.py`（純報表層，未進策略模組）。
- config 新增 `benchmark` 區塊。

---

## 4. 目前關鍵數字總表

### 4.1 自身績效（不對任何 benchmark）

| 指標 | Full 口徑（2677 天） | Active 口徑（760 天） |
|---:|---:|---:|
| Sharpe | 0.4936 | **0.9267** |
| Sortino | 0.2915 | 1.0269 |
| Mean daily return | 1.11e-4 | 3.89e-4 |
| Volatility（年化）| 8.18% | 15.34% |
| Hit rate | 0.1576 | **0.5553** |
| Max DD | **−19.50%** | −19.50% |
| Calmar | 0.1933 | 0.7137 |
| Annual turnover | 1.23x | 4.33x |
| Avg gross exposure | 28.4% | **99.9%** |
| Avg net exposure | 0.024% | 0.084%（≈ market-neutral） |

### 4.2 三組 IR（核心研究結論）

| Benchmark | Full IR | Active IR | 解讀 |
|---|---:|---:|---|
| Cash（=0） | 0.4936 | **+0.9267** | 等於 Sharpe；策略絕對風險調整後正報酬 |
| BTC perp（BYBIT:BTCUSDT.P） | −0.3248 | **−0.0175** | **幾乎不擊敗 BTC**（但策略本意 market-neutral，這是預期） |
| Equal-weight long-only（同 PIT universe） | −0.0618 | **+0.7227** | **明顯擊敗同 universe 平均**（這是真正的 alpha 跡象） |

**核心 narrative**：策略相對「同 universe 平均」有可觀 alpha；相對 BTC 幾乎無 alpha；絕對 Sharpe 在 active 期內接近 1。這對 market-neutral momentum 設計是合理結果。

> ⚠️ 注意：上述所有 active IR 都基於只有 760 個有效持倉日的樣本，對應約 25 個月。3 年 lookback 的訊號**還沒有跑過完整一個訓練視窗的樣本量**，下面 caveats 章節會詳述。

---

## 5. Claude review 結論

| Review | 對象 | 結論 | 是否允許對應 task → DONE | 詳見 |
|---|---|---|---|---|
| REVIEW-001 | TASK-001（run002） | **CONDITIONAL_PASS**（2026-05-13） | ❌ 不允許 | CLAUDE_REVIEW_LOG.md → REVIEW-001 |
| REVIEW-001c | TASK-001c（run003） | **PASS**（2026-05-13） | ✅ 允許 | CLAUDE_REVIEW_LOG.md → REVIEW-001c |
| REVIEW-001b | TASK-001b（run004） | **PASS**（2026-05-13） | ✅ 允許 | CLAUDE_REVIEW_LOG.md → REVIEW-001b |
| REVIEW-001d | TASK-001d（run007） | **IN_REVIEW** | — | CLAUDE_REVIEW_QUEUE.md → REVIEW-001d |
| REVIEW-001_final | TASK-001 整體重審 | 尚未開始 | — | 等 001d 完成後啟動 |

### 5.1 REVIEW-001 重點

- 形式驗收 7 條全 PASS。
- 發現 headline 數字屬全期口徑、會誤導，催生 TASK-001c。
- 發現 benchmark 選錯（long-only vs market-neutral beta-mismatch），催生 TASK-001b。
- 發現 missing-data 處理是「fill 0」，催生 TASK-001d。

### 5.2 REVIEW-001c 重點

- 雙口徑指標齊全；舊欄位 alias 改指 `*_full`。
- baseline.csv 與 run002 byte-identical（強證據策略未動）。
- Caveat：`hit_rate` alias 值在 run002 → run003 階躍（0.55 → 0.16），下游請改用 `hit_rate_active`。
- Nice-to-have：methodology 區塊（已被 TASK-001b 順手補完）。

### 5.3 REVIEW-001b 重點

- 6 個 IR 全部從 CSV 重算到 `1e-14`。
- positions.parquet 與 run003 byte-identical。
- methodology 區塊（annualization=365.25、ddof=1、IR/Sortino 公式）齊備；REVIEW-001c 的 nice-to-have 一併解決。
- BTC 缺資料政策（保 NaN、不 fill 0）正確；active 期內 BTC missing=0 並有 RuntimeError 防呆。
- Caveat：`ir / sharpe` alias 因 primary 改 cash 而階躍；建議補 `ir_vs_btc_full_effective_days` 揭露 BTC IR 實際只覆蓋 1884 天。

---

## 6. 目前已確認的事項（強證據）

| 確認項 | 證據 |
|---|---|
| 無假 / 模擬 / 隨機資料 | log 內 `data_snapshot_hash` 一致；TASK-001 工單的 supplemental data gate 強制 BLOCKED_BY_DATA 而非生成假資料；獨立檢查資料源 = `data/trading.db` |
| 策略在補件中未被改動 | run003 positions 與 run002 byte-identical；run004 positions 與 run003 byte-identical；baseline.csv 策略欄位三 run 逐列等值 |
| stats 可由 baseline.csv 重算 | run003 / run004 全部指標重算最大誤差 ≤ `1.07e-14`（用 methodology 文件公式） |
| reproducibility hash 通過 | 每個 run 內部重跑兩次 stats hash 完全相同（run002: `6dc6f3…`；run003: `800422…`；run004: `03dbff…`） |
| t-1 / t+1 對齊嚴格 | 29586 / 29586 positions 全部 `decision_date < effective_date` 且 gap = 1 day |
| Point-in-time universe | 29586 / 29586 positions 全部 `is_member == True`，無越界 |
| 無未來視 | resample / forward-fill 沒有把未來資料灌進 t-1；訊號層只用 t-1 收盤前資料 |

---

## 7. 目前 caveats（要記住的弱點）

### 7.1 Active 樣本只有 760 天

- 名目回測 2677 天，**實際有效持倉只有 760 天（≈ 25 個月）**。
- 對於 3 年 lookback 的 momentum 訊號，**這個樣本連半個完整訓練視窗都不到**。
- 任何後續結論都要在「樣本太短」的前提下打折扣；建議不要在這個 baseline 之上就做最終決策。

### 7.2 策略相對 BTC 幾乎無 alpha

- `ir_vs_btc_active = −0.0175`：對 BTC 接近持平。
- 對 market-neutral 設計而言這是預期（不該擊敗 long-only beta），但表示策略「不能取代 buy-and-hold BTC」，只能作為**多元化 alpha 來源**。

### 7.3 Equal-weight benchmark 有 missing days

- `eqw_benchmark_missing_days = 660`（universe 全空日）。
- 這 660 天 benchmark fill 0（非 NaN），對 active IR 無影響（active 內全有 constituents），但 **full IR 會被 660 個 0-0=0 active return 稀釋分子分母**。
- methodology 未明示 day-level（basket empty）的 fill-0 政策，下次重審前建議補。

### 7.4 Missing return = 0 尚未修正

- 當前對 missing OHLCV 的 symbol-day 政策是 `return = 0`。
- 在本回測樣本下無實質影響（COMP / ICP 異常都在持倉視窗外），但是潛在埋雷。
- **TASK-001d** 要把這個改成「missing → exclude from ranking & holding」，並抽成獨立 `data_quality/missing.py` 模組 + 單元測試。

### 7.5 COMP-USD / ICP-USD 資料異常

- COMP-USD：2021-04-17 ~ 2022-01-15 共 205 列 missing OHLCV / nonpositive close。
- ICP-USD：2021-05-10 共 1-2 列 nonpositive open/low。
- 影響範圍：**本回測完全在持倉視窗外**（持倉始於 2024-04-01），COMP-USD positions 0 筆。
- 但若未來 lookback 視窗推進到含這段，COMP 的 3 年累積會被「missing=0」低估其下行幅度，可能在 ranking 中被高估——這是 TASK-001d 要解決的真正動機。

### 7.6 平均 tradable symbols 只有 15.2

- 設計值 top_n + bottom_n = 50，實際每月只跑得動 ~7 long / 7 short。
- 集中度風險升高，max |weight| = 0.125。
- 隨資料覆蓋時間延長會緩解，但短期內難以解決。

### 7.7 Alias 在 run 之間階躍

- run002 的 `hit_rate` 是 active-only（0.55）；run003 / 004 的 `hit_rate` 改指 `_full`（0.16）。
- run003 的 `ir` 是 eqw IR（−0.06）；run004 的 `ir` 改指 cash IR（0.49）。
- log 已明確警告。**下游一律改用顯式欄位**（`hit_rate_active`、`ir_vs_<bench>_<window>`），不要用沒有後綴的舊 alias。

---

## 8. 當前狀態（2026-05-13）

| Task / Review | 狀態 | 備註 |
|---|---|---|
| TASK-001（baseline 主體） | **REVIEW**（CONDITIONAL_PASS） | 不可轉 DONE，等 TASK-001d 完成後做 `REVIEW-001_final` |
| TASK-001b（benchmark） | **DONE** | REVIEW-001b PASS（2026-05-13） |
| TASK-001c（雙口徑） | **DONE** | REVIEW-001c PASS（2026-05-13） |
| TASK-001d（missing-data 升級） | **REVIEW** | run007 ready；等 Claude REVIEW-001d |
| TASK-002（cost / funding stress） | **BLOCKED** | 等 REVIEW-001_final 通過 |
| TASK-003（baseline attribution） | **BLOCKED** | 等 REVIEW-001_final 通過 |
| TASK-004（dashboard） | **TODO**（可平行） | 第一版只放 baseline 雙口徑面板即可 |
| TASK-005（VPS monitor） | **TODO**（完全獨立） | 不受影響 |

---

## 9. 下一步建議（順序）

1. **Codex 開始 TASK-001d**——missing-data 處理升級。
   - 把 `return = 0` 改成「symbol-day 從 ranking 與 holding 中排除」。
   - 抽成 `src/data_quality/missing.py` + 單元測試（COMP / ICP fixture）。
   - 重跑 baseline，產出 `20260513_runXXX_*`（或 `20260514_*`，視日期）。
   - **禁止動策略 / 訊號模組**。

2. **Claude 開 REVIEW-001d**——審查 TASK-001d 補件。
   - 檢查 positions 變化（過去 missing→0 的 symbol-day 應該已不在）。
   - 檢查 active 樣本是否仍 760 天或有微幅變動。
   - 單元測試是否覆蓋 fixture。

3. **Claude 開 REVIEW-001_final**——TASK-001 整體最終重審。
   - 比對 b/c/d 三個補件後的最終 baseline 數字。
   - 確認雙口徑 + 三 benchmark + 嚴格 missing-data 處理之後，active Sharpe / IR vs BTC / IR vs eqw 是否仍符合「值得進入 cost stress 的最低門檻」（建議：active Sharpe ≥ 0.7、active IR_vs_eqw ≥ 0.3）。
   - 若通過 → TASK-001 轉 DONE；TASK-002 / TASK-003 解除 BLOCKED。
   - 若不通過 → 進入「保留 / 淘汰 / 更多測試」討論，由 ChatGPT 與 Rick 決策。

4. **平行進行**：TASK-004 dashboard 第一版（只放 baseline 雙口徑面板，cost/attribution 留空）、TASK-005 VPS bot monitor（與本研究線完全獨立）。

---

## 10. 給下一個 AI worker 的接手摘要

> 這段是給「下一個接手的 Codex / Claude / ChatGPT / Ollama / Rick 自己」的 5 分鐘 onboarding。

**你接手的時候，你需要知道的 8 件事：**

1. **TASK-001 是 baseline，不是 production 策略**。它的功能是把乾淨的數字產出來，不是要上線交易。所以「IR 是負的」「Sharpe 才 0.5」等問題本身不重要，重要的是「這些數字背後有沒有暗坑」。

2. **目前已經抓出三個暗坑**：(a) 全期 vs 有效期口徑混淆（TASK-001c 已修），(b) benchmark 選錯造成 IR 失真（TASK-001b 已修），(c) missing-data 處理是 fill-0（TASK-001d 未修，是當前主要工作）。

3. **三個 run 的策略產出 byte-identical**——TASK-001b / 001c 兩個補件只動報表層，沒動策略。這是 Claude 在每次審查時都會強制驗證的。下個 run（TASK-001d）會是**第一個策略產出實際變動的 run**（因為被 missing-data 處理影響 ranking）。屆時 positions 不再 byte-identical 是預期的。

4. **真實的策略視窗只有 25 個月**（2024-04 ~ 2026-04）。下游做任何結論前，要清楚這是「能不能下一步」的試金石、不是「策略好不好」的證明。

5. **三組 IR 看 active 口徑**：vs cash = +0.93、vs BTC = −0.02、vs eqw long-only = +0.72。最有意義的是 vs eqw 的 +0.72——代表策略確實有「相對同 universe 平均」的 alpha；但 vs BTC 接近 0，代表不能拿來取代 buy-and-hold。

6. **報表約定（重要）**：
   - **不要使用** 沒有後綴的 `ir / sharpe / hit_rate / sortino / calmar / max_dd / turnover_annual` 欄位——它們是 alias，跨 run 會階躍。
   - **永遠用** 顯式欄位：`*_active` / `*_full`、`ir_vs_<cash|btc|equal_weight>_<full|active>`。
   - 公式約定看 stats.json 的 `methodology` 區塊（annualization=365.25、std_ddof=1）。

7. **不可動的東西**：
   - 策略邏輯（universe 篩選、ranking、entry_price 對齊）。
   - raw data（`data/trading.db`）。
   - 既有產出檔（只能新增日期戳的新版本，不可覆寫）。

8. **下一個動作**：開始 TASK-001d。完成後 Claude 會做 `REVIEW-001d` 與 `REVIEW-001_final`，通過後 TASK-001 才能轉 DONE，TASK-002 cost stress 才能開始。

**找東西時的最快路徑：**

- 想看當前 task 清單：`docs/research/CODEX_TASK_QUEUE.md`。
- 想看當前 review 清單：`docs/research/CLAUDE_REVIEW_QUEUE.md`。
- 想看每次審查的完整推理：`docs/research/CLAUDE_REVIEW_LOG.md`。
- 想看 Codex 工單格式範例：`docs/research/codex_workorders/TASK-001_prev3y_crypto_baseline.md`。
- 想看分工守則：`docs/research/AI_WORKFLOW.md`。
- 想看本文件：`docs/research/TASK_001_PREV3Y_BASELINE_SUMMARY.md`（you are here）。

**最重要的一句話**：在 TASK-001d + REVIEW-001_final 跑完之前，**不要碰 TASK-002**，也不要在 Notion 把 Prev3Y 結果歸檔成「策略可上線」或「策略已淘汰」。它目前是「需要更多測試」。

---

## 2026-05-14 Addendum - TASK-001e Final Review Readiness

TASK-001e is now in `REVIEW`, waiting for Claude before `REVIEW-001_final`. TASK-001 remains `REVIEW`, not `DONE`; TASK-002 and TASK-003 remain `BLOCKED`.

### b/c/d conclusions now covered

- TASK-001b: PASS. Cash is the primary benchmark; BTC perp and PIT equal-weight long-only are reported as alternatives. `benchmark_return = benchmark_cash_return`.
- TASK-001c: PASS. Full and active reporting windows are both present. Legacy aliases such as `ir`, `sharpe`, `sortino`, `max_dd`, `calmar`, `turnover_annual`, and `hit_rate` are full-period aliases; use `*_active` for active-period interpretation.
- TASK-001d: PASS. Data-quality reporting is additive and did not change strategy outputs. Missing returns are not filled with zero; abnormal symbol-days are excluded from ranking candidates, holding candidates, and return calculation.

### Current headline metrics

- Active Sharpe: `0.926681647408177`.
- Active IR vs cash: `0.926681647408177`.
- Active IR vs BTC: `-0.017485575012162788`.
- Active IR vs PIT equal-weight: `0.722656939335452`.
- Full IR vs cash: `0.4935738955510849`.
- Full IR vs BTC: `-0.32475903967928543`.
- Full IR vs PIT equal-weight: `-0.061756606572156605`.

### Final-review metadata and DQ checks

- `ir_vs_btc_full_effective_days = 1884`.
- `ir_vs_btc_active_effective_days = 760`.
- `benchmark_eqw_effective_days_full = 2017`.
- `benchmark_eqw_effective_days_active = 760`.
- DQ aggregate remains: abnormal symbol-days `332`, holding exclusions `115`, ranking exclusions `0`, forced holding exits `0`, affected symbols `117`.
- Unit coverage now includes `exclude_from_ranking_candidate`, `missing_price_row`, and `aggregate_data_quality_events` boundary fixtures.

### run008 validation

- New run: `outputs/backtests/prev3y_crypto/20260513_run008_*`.
- Unit tests: `python -m unittest discover -s tests` PASS, 5 tests.
- run008 vs run007: `portfolio_return`, exposure, turnover, long/short counts, and benchmark columns all match with max diff `0.0`.
- run008 vs run007: `positions.parquet` equal.
- Stats recompute from run008 `baseline.csv`: max diff `1.07e-14`.
- Reproducibility hash: `ee8031732d1eda1406a9c10c57d11e49b6f54b3ac03c8e06fe84e63bbbe2a06f`.
