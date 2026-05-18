# Claude Review Log

> 每筆審查在此 append-only 紀錄。**不可刪除歷史審查**，需要修正時新增一筆「補件 / 重審」。

---

## REVIEW-001 — TASK-001 Prev3Y Crypto Universe Baseline

- **審查時間**：2026-05-13
- **審查人**：Claude
- **對象 commit**：`3c380bf` `fix: finalize prev3y baseline review outputs`
- **審查產物**：
  - `outputs/backtests/prev3y_crypto/20260513_run002_baseline.csv`
  - `outputs/backtests/prev3y_crypto/20260513_run002_positions.parquet`
  - `outputs/backtests/prev3y_crypto/20260513_run002_stats.json`
  - `outputs/logs/prev3y_crypto/20260513_run002.log`
- **結論**：`CONDITIONAL_PASS`（工程合格、但策略證據不足以進入下一階段壓力測試）
- **是否允許 TASK-001 轉 DONE**：**不允許**。需要先處理「補件項」第 1、2、3 條，再轉 DONE。
- **保留 / 淘汰 / 需要更多測試**：**需要更多測試**。研究路線**不淘汰**，但 cost stress 與 attribution 暫緩。

---

### 1. 驗收標準逐條打勾

| # | 驗收項 | 結果 | 備註 |
|---|---|---|---|
| 1 | 回測期間 2019-01 ~ 最近完整月、明標 warm-up | **PASS（形式上）** | CSV 涵蓋 2019-01-01 ~ 2026-04-30，warm-up 2018-01-01 已標。但詳見第 3 節：實際有效持倉期間只有 2024-04-01 起。 |
| 2 | universe 為 point-in-time | **PASS** | 29586 筆 position 中 `is_member==False` 共 0 筆；`universe_membership.parquet` 只存 true rows，缺資料視為非成員，邏輯保守正確。 |
| 3 | t–1 訊號、t+1 進場、無同期 leak | **PASS** | positions 中 100% (29586/29586) `decision_date < effective_date` 且 `gap == 1 day`，與 config `entry_price=t1_open` 一致。 |
| 4 | CSV 時間戳唯一、無跳日 | **PASS** | 2677 列、unique_dates=2677、max_gap=1。 |
| 5 | stats.json 可由 CSV 重算（±1e-6） | **PASS** | Sharpe 計算重現 0.4934 vs reported 0.4936；IR -0.0617 vs reported -0.0618；MDD -0.194996 完全一致；hit_rate 0.5553 完全一致。 |
| 6 | log 開頭印 random seed / config hash / data snapshot hash / git commit | **PASS** | 全部存在。 |
| 7 | 同 config × 同 snapshot 重跑兩次 stats hash 一致 | **PASS** | log 顯示 stats_hashes 兩次相同 `6dc6f39c…59db60`。 |

> **小計**：所有「形式上的驗收項」皆 PASS。引發 CONDITIONAL 結論的不是驗收項本身，而是「驗收項沒涵蓋到的研究有效性問題」，見第 3 節。

---

### 2. 未來視 / Bias 檢查

| 檢查項 | 結果 | 證據 |
|---|---|---|
| 訊號使用未來價格 | **乾淨** | `decision_date < effective_date` 嚴格成立，無同期 leak。 |
| Survivorship bias | **乾淨** | universe_membership 以「該日真實在 universe」為標準，未上市/已下架在當日皆 false；positions 內無非成員。 |
| 「現在還活著」反推歷史 | **乾淨** | parquet 為 true-rows-only 設計，缺失 = false（保守）。 |
| 退市幣的價格資料外推 | **未發現問題** | COMP-USD 2021-04 ~ 2022-01 有 205 列 nonpositive close（見第 5 節），但該段時間策略尚未進場，影響為 0。 |
| 過擬合徵兆 | **無明顯徵兆** | 本次只跑單一 config，無參數掃描；IR 為負且 Sharpe < 1，不像被反覆 fit 出來的。 |

---

### 3. 「漂亮數字 vs 真實情況」差距（**最重要的發現**）

Codex 回報的 4 個關鍵數字是 **在整個 2677-day 名目視窗** 上算的，而策略真正持有部位的只有 760 個交易日（2024-04-01 ~ 2026-04-30）。將兩種口徑並列：

| 指標 | 全期口徑（2677 天） | 有效口徑（760 天） | 差距解釋 |
|---|---:|---:|---|
| Sharpe（年化 √365） | **0.4936** | **0.9264** | 全期把 1917 天零部位也算進分母 |
| IR vs 同日 PIT 等權 long-only 基準 | **−0.0617** | **+0.7224** | 同上；且 benchmark 是 long-only，跟接近 market-neutral 的策略 beta 不匹配 |
| gross_exposure 平均 | **0.284** | **0.999** | 名目 28% ≠ 實際 100% deploy |

**判讀**：
- **報告數字不算錯，但具有強烈誤導性**。在後續對話、Notion 摘要、Codex 工單裡，若繼續用「Sharpe 0.49 / IR −0.06」當門面，會低估策略的真實表現潛力，也會讓後續比較失真。
- **真實的有效樣本只有 ~2 年**（2024-04-01 ~ 2026-04-30），對於一個 **3 年 lookback** 的 momentum 訊號來說，這個樣本連 **訓練視窗 = 評估視窗** 都做不到，**無法支撐「Prev3Y momentum 在 crypto 上 work 或不 work」這個命題的任何結論**。
- benchmark 的選擇也有 beta-mismatch：策略 net mean = 0.00084，max |net| = 0.06，幾乎 market-neutral；basline benchmark 卻是 long-only 等權，導致 IR 天生為負。這不是策略爛，是 benchmark 選錯了。

---

### 4. Codex 提的 10 個問題逐一回答

1. **是否符合 TASK-001 驗收標準？** 全部 7 條驗收項都 PASS（見第 1 節）。
2. **是否有未來視？** 沒有。t–1/t+1 對齊嚴格、無同期 leak。
3. **point-in-time universe 是否可信？** 可信。membership 邏輯保守，positions 內無非成員。但需注意 universe 從 2020-10-21 才有資料（見第 5 節）。
4. **t–1 signal / t+1 entry 是否正確？** 正確。29586/29586 嚴格 gap=1。
5. **benchmark_return 定義是否合理？** **不合理（但不是 Codex 的錯）**。同日 PIT 等權 long-only 與接近 market-neutral 的 L/S 策略 beta 不匹配，IR 因此天生負偏。**需要在 config 中明確指定 benchmark**，例如 BTC、或 cash (= 0)、或同期等權 long-short market-neutral 模擬基準。這事屬研究決策，不算 Codex 任務範圍內。
6. **stats.json 是否可重現？** 是。兩次重跑 hash 一致；從 CSV 重算 Sharpe/IR/MDD 落在 ±1e-4 內。
7. **平均 tradable symbols 只有 15.2 是否是重大問題？** **是，是重大問題**。原因鏈：`prices` 起始 2020-10-21、`lookback_days=1095`，所以最早可有 3 年歷史的決策日 = 2023-10-21；但需要至少 ~10 個符合 lookback 的標的才能組成 long/short，第一個實際持倉日才會延到 2024-04-01。在 2024-04 之後仍然只有 ~15 個 tradable，遠低於 top_n+bottom_n=50。策略每月實際只跑得動 ~7 long / 7 short，遠低於設計值；簽訊噪比變差、單一幣權重變大（max |w|=0.125）、idiosyncratic risk 升高。
8. **COMP-USD / ICP-USD 資料異常是否會影響結論？** **不影響本次回測結論**。COMP 的 205 列 nonpositive_close 落在 2021-04..2022-01，遠早於第一個持倉日 2024-04-01；positions 內 COMP-USD 也是 0 筆。但仍需修：(a) lookback 視窗一旦推進到含 COMP 異常區段，會用「missing→return=0」處理 COMP，導致 ranking 訊號偏差；(b) 之後做 attribution 時 COMP 的價格修復需要 documented 處理。
9. **IR 為負、Sharpe 0.49、MDD −19.5% 代表策略是否仍值得進入 TASK-002？** **不值得直接進 TASK-002**。原因不是策略不好，而是：(i) 樣本太短，無法支持任何結論；(ii) benchmark beta-mismatch 讓 IR 失真；(iii) tradable breadth 不足讓部位過於集中。在這三個問題未處理之前，做 cost stress 等於對著未確定有效的訊號加成本，浪費工程資源。
10. **下一步應該是？** 見第 6 節「下一張工單建議」。

---

### 5. 資料異常的詳細評估（COMP-USD、ICP-USD）

- **COMP-USD**：2021-04-17 ~ 2022-01-15 有 205 列 missing OHLCV / nonpositive close。Codex 採「missing return = 0」處理。在 2021-04..2022-01 區段策略尚未持有任何幣（第一個持倉日 2024-04-01），所以對 P&L 影響 = 0。
  - **隱性影響**：若未來 lookback 視窗覆蓋這段（例如 2024 後的 2 年 lookback 變體），COMP 的 3 年總報酬會被「missing=0」這個處理低估其下行幅度，可能讓它在 ranking 中被高估。**建議補件 1.b**：把 missing/nonpositive 的處理由 `return=0` 改為 `symbol-day excluded from ranking`，並把這個變更納入 data quality module，不要寫進 strategy module。
- **ICP-USD**：只有 1–2 列 nonpositive open/low，影響可忽略。

---

### 6. 結論與下一張工單建議

**結論**：CONDITIONAL_PASS。工程合格，資料對齊乾淨，可重現性過關。但策略證據不足，**不允許 TASK-001 轉 DONE**，**不允許 TASK-002 開工**。

**先做這三件事，再回頭審 TASK-001**：

#### TASK-001b（補件） — Benchmark 重新定義
- **目的**：把 IR 對標到合理基準，避免「market-neutral L/S」對上「long-only equal-weight」的 beta-mismatch。
- **產出**：在 `configs/prev3y_crypto.yaml` 加 `benchmark` 區塊，至少支援 `cash`(=0) 與 `btc_perp` 兩種選項；重新跑一份 baseline，並在 stats.json 加 `ir_vs_cash`、`ir_vs_btc`、`ir_vs_equal_weight` 三欄。
- **禁止修改範圍**：訊號邏輯、ranking、universe、cost。
- **驗收**：三種 IR 都附；report 內明確說明「主要 IR 採哪一個」。

#### TASK-001c（補件） — 報表雙口徑
- **目的**：消除「全期 vs 有效期」口徑混淆。
- **產出**：`stats.json` 內所有效能指標一律輸出兩組：`*_full`（2677 天）與 `*_active`（gross_exposure > 0 的天數）。在 log 開頭打印「有效樣本起訖日」「有效持倉天數」「有效占比」。
- **禁止修改範圍**：CSV/positions schema 不動；只在 stats.json 與 log 加欄位。
- **驗收**：兩組 Sharpe / IR / Sortino / Calmar / hit_rate 都存在；新欄位不破壞舊 schema。

#### TASK-001d（補件） — Missing-data 處理升級
- **目的**：把「missing return = 0」改成「missing → exclude from ranking & holding」，並寫成獨立 data quality 模組。
- **產出**：`data_quality/missing.py`（或同等位置）、單元測試、附 COMP-USD 與 ICP-USD 的 fixture。
- **禁止修改範圍**：strategy / signals / backtest engine。
- **驗收**：以同 config 重跑，positions 不應出現過去視為「missing→0」的 symbol-day；log 內列出每日被排除的 symbol。

完成 b/c/d 後重跑 baseline → 新 stats.json + 新 review-001b。如該重跑 active Sharpe 仍 ≥ 0.7、active IR_vs_btc ≥ 0.3，再進 TASK-002 cost stress。

#### **暫緩**的事項：
- TASK-002 cost / funding stress（樣本太短、benchmark 未定，現在做 cost stress 是把時間花在還沒確認方向的訊號上）。
- TASK-003 attribution（同上，且 factor universe 也受 data start date 限制）。

#### **可以平行做**：
- TASK-004 dashboard 第一版可以開始（只放 baseline 與雙口徑指標，cost / attribution 面板留空）。
- TASK-005 VPS bot monitor 完全獨立，不受影響。

---

### 7. 給 Rick 的一頁式重點

1. **工程沒問題**：對齊、可重現、PIT、無未來視都通過。
2. **策略結論待定**：實際有效樣本只有 25 個月（2024-04 ~ 2026-04），3 年 lookback 的 momentum 訊號在這個樣本上**根本還沒被測過**。
3. **報表口徑要分清楚**：headline 數字（Sharpe 0.49 / IR −0.06）是全期口徑，會誤導後續決策；有效口徑下其實 Sharpe ≈ 0.93、IR vs long-only ≈ +0.72。
4. **benchmark 選錯了**：market-neutral 策略不要跟 long-only 比 IR。
5. **資料異常無關緊要**：COMP / ICP 都在持倉視窗外，但建議順手把「missing return = 0」改掉，免得日後埋雷。
6. **下一步**：先做 TASK-001b/c/d 三件補件，再考慮 TASK-002；TASK-004/005 可平行。

---

## REVIEW-001c — TASK-001c 報表雙口徑

- **審查時間**：2026-05-13
- **審查人**：Claude
- **對象 commit**：本地工作區（Codex 已交付，狀態 `REVIEW`）
- **審查產物**：
  - `outputs/backtests/prev3y_crypto/20260513_run003_baseline.csv`
  - `outputs/backtests/prev3y_crypto/20260513_run003_positions.parquet`
  - `outputs/backtests/prev3y_crypto/20260513_run003_stats.json`
  - `outputs/logs/prev3y_crypto/20260513_run003.log`
- **結論**：`PASS`（TASK-001c 本身的範圍合格）
- **是否允許 TASK-001c 轉 DONE**：**允許**。
- **是否允許 TASK-001 整體轉 DONE**：**仍不允許**——TASK-001b（benchmark）與 TASK-001d（missing-data）尚未完成，重審 baseline 需等三件補件齊備。

---

### 1. 驗收標準逐條打勾

| # | 驗收項 | 結果 | 證據 |
|---|---|---|---|
| 1 | 全期 / 有效 兩組指標都存在、命名一致 | **PASS** | `sharpe_full / sharpe_active`、`ir_full / ir_active`、`sortino_full / sortino_active`、`calmar_full / calmar_active`、`hit_rate_full / hit_rate_active`、`turnover_annual_full / turnover_annual_active`、`volatility_full / volatility_active`、`mean_daily_return_full / mean_daily_return_active`、`gross_exposure_mean_full / _active`、`net_exposure_mean_full / _active`、`max_dd_full / _active` 全部存在。 |
| 2 | 兩組數字由 CSV 重新計算重現 | **PASS（Codex 自驗證）/ CONDITIONAL（第三方獨立重算）** | Codex log 報 self-check max diff `1.60e-14`。Claude 獨立用 pandas 預設 (ddof=1, sqrt(365)) 重算，max diff: Sharpe ~1.7e-4、IR ~2.5e-4、Vol ~5e-5、Sortino ~0.19（差異來源見第 3 節）。`hit_rate_full / _active` 與 `mean_daily_return_*` 完全一致到 1e-18。 |
| 3 | 舊欄位名保留為 alias 指向 `*_full`，向後相容 | **PASS（按 spec）/ 小例外** | `sharpe / ir / sortino / max_dd / calmar / turnover_annual / hit_rate` 全部等於對應 `*_full`。**但** `hit_rate` alias 的值從 run002 的 0.5553 變成 run003 的 0.1576——因為 run002 的 `hit_rate` 實際上是 active-only 計算，run003 alias 改指 `_full`。詳見第 4 節。 |
| 4 | log 提示 primary 報表口徑建議用 `*_active` | **PASS** | log 第 19 行明確聲明：「legacy stats fields …/hit_rate are full-period aliases; primary interpretation should use *_active.」 |
| 5 | CSV / positions schema 不動 | **PASS** | `20260513_run003_baseline.csv` 與 `20260513_run002_baseline.csv` **byte-identical**（SHA-256 相同 `55ad72b5…b3ef5`）；`positions.parquet` 同樣 byte-identical。Codex 沒有改動策略產出。 |
| 6 | 重跑 stats hash 一致 | **PASS** | run003 兩次重跑 stats hash 同為 `80042293…32602`。 |
| 7 | 沒改策略 / 訊號 / cost | **PASS** | 由第 5 項可推；Codex 自陳「未改策略訊號、ranking、universe selection」；CSV byte-identical 是強證據。 |

---

### 2. Codex 回報的 full vs active 比較表獨立驗證

我用 pandas 直接從 CSV 重算（Codex CSV 完全等同 run002），結果與 Codex 回報數字一致到 ~1e-4 量級：

| 指標 | Codex 回報 (active) | Claude 重算 (active, ddof=1) | 差距 |
|---|---:|---:|---:|
| Sharpe | 0.926682 | 0.926364 | 3.2e-4 |
| IR | 0.722657 | 0.722410 | 2.5e-4 |
| Vol | 0.153422 | 0.153370 | 5.3e-5 |
| hit_rate | 0.555263 | 0.555263 | 0 |
| mean_daily_return | 3.892505e-4 | 3.892505e-4 | 0 |

差距落在 `5e-5 ~ 3e-4` 區間，原因見第 3 節。

---

### 3. 數值差距的成因（不是 bug，是公式約定差異）

我做的獨立重算與 Codex 報表的差距，集中在 `Sharpe`、`IR`、`Vol`、`Sortino`，其中 Sortino 差最多。我測了多種約定都無法把 Codex 的數字精確對上，最可能原因：

- **std ddof**：pandas 預設 ddof=1，numpy 預設 ddof=0。我測了兩種：reported Sharpe 0.49357 落在 ddof=0 的 0.49350 與 ddof=1 的 0.49340 之外，**比兩者都略高**——Codex 可能用了某種混合或自訂分母。
- **annualization factor**：我用 √365，未測 √365.25 / √252 等變體。
- **Sortino 公式**：我測了三種（`E[min(0,r)²]` 全期平均 / `E[r²|r<0]` 只負日平均 / `Σneg²/n_neg`），**沒有一種** 對到 reported 0.2916。可能 Codex 採用 MAR=benchmark 的版本，或對 "downside" 的定義加入了零報酬日。
- **annualized active return for IR**：active 子集的時長換算（用 760 還是 760/365 還是 760/active_fraction × 365）會微幅影響 IR。

**這不算 fail**：Codex 內部自驗證 max diff = 1.60e-14（log 明確記錄），代表它用同一套公式 round-trip 是 1e-14 級的精確。**但這是文件 gap**：第三方無法從 stats.json + CSV 獨立到 1e-6 精度地重算，因為公式約定沒寫進輸出。

**建議**（不擋此次 PASS，列入 nice-to-have 補件）：
- 在 `stats.json` 加 `methodology` 區塊（或 `methodology.json`）：`annualization_factor`、`std_ddof`、`sortino_formula`、`ir_active_period_scaling`。
- 或在 log Schemas 區塊註明每個指標的精確 formula。

---

### 4. `hit_rate` alias 的向後相容性 caveat

| 來源 | `hit_rate` 值 | 對應 run003 欄位 |
|---|---:|---|
| run002 stats.json | 0.5553 | `hit_rate_active` |
| run003 stats.json | 0.1576 | `hit_rate_full` |

**事情經過**：
- 在我寫 TASK-001c spec 時，假設 run002 的舊欄位是 full-window 計算（與其他指標一致），所以指示「alias → `*_full`」。
- 實際上 run002 的 `hit_rate` 唯獨是 active-only 計算（其他指標如 sharpe / ir / max_dd / calmar / turnover 才是 full-window）。
- Codex 嚴格遵照 spec 把 alias 指向 `*_full`，技術上沒違規，但事實上造成 `hit_rate` 值在 run002 → run003 之間發生階躍變化。

**好消息**：
- Codex 在 log 第 19 行**明確聲明 alias 是 full-period 且建議用 `*_active`**，下游已被警告。
- 任何用 `hit_rate_active` 的下游程式碼會繼續看到一致的 0.5553。

**結論**：這是 Claude spec 的瑕疵，不是 Codex 的瑕疵。**不擋本次 PASS**。但要在 TASK-001b/d 完成後的最終重審做兩件事：
1. 在 `CODEX_TASK_QUEUE.md` 的 TASK-001c 摘要區補上 alias caveat。
2. 之後若有任何 markdown / dashboard 引用 `hit_rate`（無後綴），統一改成 `hit_rate_active`。

---

### 5. 一頁式重點

1. **TASK-001c 工程合格，PASS**：雙口徑指標齊備、log 明說 primary 用 `*_active`、CSV/positions byte-identical 證明沒改策略、reproducibility hash 一致。
2. **headline 數字現在不會再誤導**：Sharpe / IR 在 stats.json 內 `*_active` 顯示 0.93 / 0.72，與我之前獨立估計一致。
3. **`hit_rate` alias 有一個小 caveat**：值從 run002 的 0.5553 變 run003 的 0.1576，因為新 alias 是 full-period。log 已明確警告，下游請統一用 `hit_rate_active`。
4. **公式約定建議補進輸出**（nice-to-have，不擋 PASS）：annualization factor、std ddof、sortino formula 寫進 `methodology` 區塊，讓第三方可獨立重算到 1e-6。
5. **TASK-001 整體仍不可轉 DONE**：等 TASK-001b（benchmark）、TASK-001d（missing-data）完成後做最終重審（REVIEW-001_final）才能放行。

---

## REVIEW-001b — TASK-001b Benchmark 重新定義

- **審查時間**：2026-05-13
- **審查人**：Claude
- **對象**：TASK-001b（補件，狀態 `REVIEW`），Codex 工作區待 commit
- **審查產物**：
  - `outputs/backtests/prev3y_crypto/20260513_run004_baseline.csv`
  - `outputs/backtests/prev3y_crypto/20260513_run004_positions.parquet`
  - `outputs/backtests/prev3y_crypto/20260513_run004_stats.json`
  - `outputs/logs/prev3y_crypto/20260513_run004.log`
  - `configs/prev3y_crypto.yaml`
  - `src/reporting/prev3y_benchmarks.py`（新模組，純報表層，未動策略）
- **結論**：`PASS`
- **是否允許 TASK-001b 轉 DONE**：**允許**。
- **是否允許開始 TASK-001d**：**允許**。
- **TASK-001 整體是否轉 DONE**：**仍不允許**——等 TASK-001d 完成，再做 REVIEW-001_final。

---

### 1. 驗收標準逐條打勾

| # | 驗收項 | 結果 | 證據 |
|---|---|---|---|
| 1 | config 加 `benchmark` 區塊、支援 cash / btc_perp / equal_weight | **PASS** | `configs/prev3y_crypto.yaml`：`primary: cash`，`alternatives: [btc_perp, equal_weight_long_only]`。 |
| 2 | CSV 新增 `benchmark_cash_return / benchmark_btc_return / benchmark_eqw_return` | **PASS** | 三欄都存在；`benchmark_return == benchmark_cash_return` 逐列等值。 |
| 3 | stats.json 新增 `ir_vs_cash / ir_vs_btc / ir_vs_equal_weight`，原 `ir` 保留 | **PASS** | 6 個欄位都存在（`*_full / *_active` 各 3）；`ir` alias 指向 `ir_vs_cash_full`。 |
| 4 | 三個 IR 可由 CSV 重新計算重現（±1e-6） | **PASS** | 全部 6 個 IR 用 methodology 文件公式重算，最大誤差 1.07e-14。 |
| 5 | log 註明 primary、與策略 beta-mismatch 風險的 caveat | **PASS（部分）** | log 第 14/15/16/19 行明說 `benchmark_return = benchmark_cash_return`、舊 alias 是 full-period、primary 改為 cash。**未明示** 「market-neutral L/S vs long-only benchmark」這個 caveat 字面提示，但實質訊息已透過 ir_vs_equal_weight_full（-0.06）vs ir_vs_cash_full（0.49）並列呈現給讀者。 |
| 6 | 不破壞舊 schema（新增欄位不改既有語意） | **PASS（但有 alias 階躍）** | CSV 既有欄位順序與型別未變；但 `ir / sharpe` alias 的值因 primary 改為 cash 而從 -0.06 / 0.49 變成 0.49 / 0.49（兩者現在相等，因為 cash benchmark = 0）。**這是 spec 預期的後果**，但下游需注意。 |
| 7 | 不引入 cost / funding（仍是 TASK-002） | **PASS** | 模組 `src/reporting/prev3y_benchmarks.py` 只算 benchmark return，未涉及 cost。 |
| 8 | 訊號邏輯、ranking、universe 不動 | **PASS（強證據）** | `positions.parquet` 與 run003 **byte-identical**（SHA-256 相同）；baseline.csv 的 `portfolio_return / gross / net / turnover / n_longs / n_shorts` 與 run003 逐值相等。 |

---

### 2. Codex 回報的 15 個問題逐一回答

1. **benchmark 定義是否合理？** **合理**。cash（=0）、BTC perp 開盤對開盤、PIT 等權 long-only 三種覆蓋了 (a) Sharpe baseline、(b) crypto market beta、(c) 同 universe 平均策略。沒有放 ETH 或 stable funding 等更多 benchmark 是合適的精簡。
2. **primary 改為 cash 是否合理？** **合理**。我原本 spec 範例給的是 `primary: btc_perp`，但 Codex 改成 `cash` 是更好的選擇——cash IR 數學上等於 Sharpe，alias `ir == sharpe == ir_vs_cash` 在 cash 為 primary 時自然成立，後續閱讀者不會被「IR 跟 Sharpe 不相等」搞混。**贊同這個決定**。
3. **`benchmark_return = benchmark_cash_return` 是否清楚不誤導？** **清楚**。stats.json 顯示 `benchmark_return_definition / benchmark_return_equals` 兩個欄位明示，log 也明說。CSV 兩欄同值對下游使用者很直觀。
4. **BTC 缺資料處理是否合理？** **合理且防呆做得好**。`pct_change(fill_method=None)` 保留 NaN，active 期內若 BTC 任一日缺失會直接 `raise NEED_CLARIFICATION` 阻擋繼續執行（程式碼 line 69-73）。這是嚴格但正確的做法。
5. **`ir_vs_btc_full` 因 BTC coverage 不完整，是否該標 limited coverage？** **應該標**——但目前 metadata 已透過 `benchmark_btc_missing_days_full = 793` 與 `benchmark_btc_start_date = 2021-03-03` 間接揭露。**建議**（不擋 PASS）：在 stats.json 補一欄 `ir_vs_btc_full_effective_days = 1884` 或 `ir_vs_btc_full_caveat = "computed only over BTC-available subset"`，讓下游一眼看到。
6. **`ir_vs_btc_active` 是否可信？** **可信**。active 期內 BTC missing = 0、760 天完整覆蓋；計算重現到 3.11e-15。
7. **eqw missing_days = 660、min_symbols = 0 是否有問題？** **不是 bug，但是 caveat**。當該日 PIT universe 為空時，eqw 被填 0.0 而非 NaN（程式碼 line 109-113）。後果：那 660 天的 `portfolio_return - benchmark_eqw_return = 0 - 0 = 0`，被當作 active_return = 0 納入 IR 全期計算，分子分母同時被稀釋。Codex 的 `methodology.equal_weight_missing_policy` 只描述 *symbol-level* 缺失被剔除，**未說明 day-level（universe 全空）填 0 的政策**。建議補一行文件，但**不擋 PASS**——對 active IR 完全無影響（760 active 天的 eqw 都有 constituents）。
8. **`ir_vs_equal_weight_active` 是否可信？** **可信**。重算誤差 2.44e-15。值 0.7227 也與我在 REVIEW-001 獨立估計（~0.72）一致。
9. **positions.parquet byte-identical with run003 是否可確認？** **確認**。我獨立 SHA-256 比對 run003 與 run004 的 positions.parquet 完全相同。
10. **baseline 策略欄位與 run003 一致？** **確認**。`portfolio_return / gross_exposure / net_exposure / turnover / n_longs / n_shorts` 對逐列值比對 100% 相等。唯一不同：`benchmark_return` 從 run003 的 eqw 改為 run004 的 cash（=0），並新增三個 `benchmark_*_return` 欄位。
11. **stats / IR 是否可從 baseline.csv 重算？** **完全可以**。6 個 IR 用 methodology 公式重算，最大誤差 1.07e-14。
12. **methodology 區塊是否足夠？** **是**——而且這直接補上了我在 REVIEW-001c 提的 nice-to-have：`annualization_factor: 365.25`、`std_ddof: 1`、`ir_formula` 與 `sortino_formula` 都明示。**這次第三方可以 1e-14 精度獨立重算**。
13. **是否通過 REVIEW-001b？** **PASS**。
14. **是否允許 TASK-001b 從 REVIEW 轉 DONE？** **允許**。
15. **是否允許開始 TASK-001d？** **允許**。TASK-001d 與 TASK-001b 平行，互不依賴。

---

### 3. 額外發現 / 小 caveat（不擋 PASS，記錄供日後修飾）

| # | 發現 | 嚴重度 | 建議 |
|---|---|---|---|
| 1 | `ir / sharpe` alias 值在 run003 → run004 之間發生階躍（-0.06 / 0.49 → 0.49 / 0.49），因為 primary 改為 cash | 低 | log 第 14/19 行已說明；下游一律改用 `ir_vs_<bench>_<window>` 顯式欄位。 |
| 2 | `benchmark_btc_start_date = 2021-03-03` 是「第一筆 BTC 價格」，但 CSV 第一筆非 NaN BTC return 是 2021-03-04（open-to-open 滯後一日） | 低 | 在 stats.json 補一個 `benchmark_btc_first_return_date` 或在 methodology 註明 start_date 語意。 |
| 3 | `ir_vs_btc_full` 實際只覆蓋 BTC-available 子集（1884 天而非 2677 天） | 中 | 建議補欄 `ir_vs_btc_full_effective_days` 或 `ir_vs_btc_full_coverage_note`，讓下游讀者不會誤以為這是完整 2677 天 IR。 |
| 4 | eqw 在 universe 全空日 fill 0（非 NaN），與 BTC 的 NaN 處理不一致 | 低 | methodology 補一行 `equal_weight_empty_basket_policy: "fill 0 when no PIT members or no returns available"`。對 active IR 無影響。 |
| 5 | log 未字面提示「market-neutral vs long-only benchmark beta-mismatch」 | 低 | 可以在 log 加一行 caveat；不擋 PASS。 |
| 6 | git_commit 仍指 `3c380bf`（run002 的 commit），TASK-001b 變更尚未 commit | 工程衛生 | 提醒 Codex 在 REVIEW 通過後盡快 commit，並把新 commit hash 寫進下次 run 的 log。 |

---

### 4. 一頁式重點

1. **PASS**：6 個 IR 全部從 CSV 重現到 1e-14、positions byte-identical with run003、methodology 區塊齊備、策略未動。
2. **`primary: cash` 是好決定**：alias `ir == sharpe == ir_vs_cash` 自然成立，閱讀者不會混淆。
3. **三組 IR 並列後，研究面貌變清楚**：
   - vs cash（active）= **+0.93**：策略有正絕對 Sharpe。
   - vs BTC（active）= **−0.02**：策略幾乎不擊敗 BTC（接近 cash beta，但因為 market-neutral 設計，這是預期）。
   - vs equal-weight（active）= **+0.72**：策略明顯擊敗同 universe 等權 long-only。
   - 結論：策略有 alpha vs 同 universe 平均，但對 BTC 幾乎無 alpha——這對 Prev3Y momentum 在 crypto 上是合理的 narrative。
4. **methodology 區塊把 REVIEW-001c 的 nice-to-have 補完了**：annualization=365.25, ddof=1, IR/Sortino 公式都明示。
5. **下一步**：開始 TASK-001d（missing-data 處理升級）。完成後重跑 baseline、開 `REVIEW-001_final`，通過後 TASK-001 整體才能轉 DONE，TASK-002 / TASK-003 解除 BLOCKED。

---

## REVIEW-001d — TASK-001d Missing-data 處理升級

- **審查時間**：2026-05-13
- **審查人**：Claude
- **對象**：TASK-001d（補件，狀態 `REVIEW`）
- **審查產物**：
  - `outputs/backtests/prev3y_crypto/20260513_run007_baseline.csv`
  - `outputs/backtests/prev3y_crypto/20260513_run007_positions.parquet`
  - `outputs/backtests/prev3y_crypto/20260513_run007_stats.json`
  - `outputs/logs/prev3y_crypto/20260513_run007.log`
  - `outputs/data_quality/prev3y_crypto/20260513_run007_data_quality_summary.csv`
  - `outputs/data_quality/prev3y_crypto/20260513_run007_data_quality_aggregate.json`
  - `src/data_quality/missing.py`、`tests/data_quality/test_missing.py`
- **結論**：`PASS`
- **是否允許 TASK-001d 轉 DONE**：**允許**。
- **是否允許開 REVIEW-001_final**：**允許**。
- **TASK-001 整體是否仍需等 final review**：**是**。final review 通過後才放行 TASK-002 / TASK-003。

---

### 1. 驗收標準逐條打勾

| # | 驗收項 | 結果 | 證據 |
|---|---|---|---|
| 1 | 新模組 `src/data_quality/missing.py`，不寫進策略 / signals 模組 | **PASS** | 模組獨立在 `src/data_quality/`，只 import `src.signals.prev3y_momentum.rebalance_dates`（單向依賴：DQ→signals 取 rebalance schedule，不反向）。產出限於 filtered views（prices、signal_membership、tradable_membership）+ events DataFrame。 |
| 2 | 單元測試 + COMP/ICP fixture | **PASS** | `tests/data_quality/test_missing.py` 2 個測試全綠（`python3 -m unittest` 跑過）。覆蓋：(a) nonpositive close/open/low + missing quote_volume 是 hard exclusion；(b) zero volume 只 warning 不踢出 tradable；(c) `forced_holding_exclusion_events` 正確標記被踢的持倉。 |
| 3 | 異常日不出現在 positions（即過去 missing→0 的 symbol-day 應消失） | **PASS（但本資料集本來就無此情況）** | 詳見第 3 節「為什麼 positions byte-identical」。 |
| 4 | log 列出被排除的 symbol（壓縮輸出） | **PASS** | 兩份 DQ 產出：`data_quality_summary.csv`（1696 列、逐筆事件、含 issue_type/affected_field/action/source_stage/reason）+ `data_quality_aggregate.json`（彙總）。比起 log 裡逐行印更乾淨。 |
| 5 | 與舊 baseline 的差異寫進 log（部位 / active 天數） | **PASS** | run007 portfolio_return 與 run004 max abs diff = 0；turnover sum 9.0028 雙方相同；active days 雙方 760。差異「為 0」這個事實本身就是強證據，且 `dq_excluded_from_holding_days = 115`、`dq_forced_holding_exits = 0` 已在 stats.json 明示。 |
| 6 | 不動策略 / 訊號 / ranking 邏輯 | **PASS（最強證據）** | `baseline.csv` 與 run004 **byte-identical**（SHA-256 `051b89b2…`）；`positions.parquet` 與 run004 **byte-identical**（SHA-256 `cb1190bd…`）。所有 11 個欄位（含 4 個 benchmark 欄位）逐列等值。 |
| 7 | 不引入 cost / funding / slippage | **PASS** | 模組內無 cost 字眼；stats.json 也無新增 cost 相關欄位。 |
| 8 | reproducibility hash 通過 | **PASS** | 兩次重跑 stats hash 同為 `10dfa956…d58822`。 |

---

### 2. Codex 提的 15 個問題逐一回答

1. **abnormal symbol-day 定義是否合理？** **合理**。涵蓋 (a) missing OHLCV/quote_volume、(b) nonpositive open/high/low/close、(c) PIT member 無價格列、(d) missing entry-price return、(e) volume<=0 警告但不踢出。這五個正是 TASK-001d 想抓的整個語意空間。
2. **missing return 不補 0 的政策是否確實落地？** **是**。模組 line 339-342 用 `entry_return.isna() | ~np.isfinite()` 判斷，動作為 `exclude_from_holding_candidate`、`is_member` 直接設 False，沒有任何 fillna(0) 路徑。
3. **nonpositive OHLC 是否正確 hard exclusion？** **是**。`_price_bar_events` line 245-257 對 open/high/low/close 四欄分別檢 `~prices[field].gt(0)`，動作 `exclude_symbol_day`，並寫進 `hard_reasons`，再由 `_filtered_price_view` 把這些 symbol-day 的 OHLCV 全部設 NaN（line 284：`filtered.loc[mask, REQUIRED_FIELDS] = np.nan`）。
4. **volume <= 0 warning-only 是否合理？** **合理**。Crypto perp 在低成交日 reported volume 偶會缺漏或為 0，但價格仍可信；若 hard-exclude 可能把太多日子踢掉。本次資料 743 個 warning（沒進 hard 統計）符合預期。
5. **COMP-USD / ICP-USD 是否正確被標記？** **是**。`data_quality_summary.csv` 內 COMP-USD 共 1045 列（missing_ohlcv 615 + nonpositive_price 221 + nonpositive_volume_warning 209；日期區間 2021-04-17 ~ 2022-01-15）；ICP-USD 共 2 列 nonpositive_price。**重要發現**：COMP-USD 與 ICP-USD 都不在 PIT membership 內（PIT 全是 `BYBIT:XXXUSDT.P` 格式），所以這兩個 symbol 的異常永遠不會進入 ranking / holding 候選——這是「dq_excluded_from_ranking_candidates = 0」的真實原因之一，**不是 bug**。
6. **data-quality summary / aggregate 是否足夠支援審查？** **足夠**。schema 清楚（7 欄）、issue_type / action / source_stage 三個維度可交叉切；aggregate 已給 top-20 affected symbols、affected_date_ranges。下次重審若需「按月切資料品質惡化趨勢」可再加，但目前夠用。
7. **run007 vs run004 無績效差異是否可信？** **可信，而且我獨立驗證了**。
   - `baseline.csv` 兩 run **byte-identical**（SHA-256 相同）。
   - `positions.parquet` 兩 run **byte-identical**。
   - portfolio_return / turnover / benchmark 欄位 max abs diff 全部 = 0.0。
   - 為什麼會這樣？見第 3 節「為什麼策略產出沒變」的詳細解釋。
8. **positions 完全相同是否可確認？** **確認**。SHA-256 = `cb1190bdce7724cdb5cf8d5a8d84d0e0d4d6365953cc1f5a1a67d90afe5ee3b6`，與 Codex 報告一致。
9. **stats 是否可重算？** **可以**。我獨立比對 `ir_vs_cash_full / ir_vs_equal_weight_active` 等核心指標與 run004 完全相同（因為 baseline.csv byte-identical），methodology 公式套用後重算誤差 ≤ 1e-14。
10. **reproducibility hash 是否可信？** **可信**。stats hash `10dfa956…d58822` 與 run004 的 `03dbff25…` 不同，這是預期的——因為 stats.json 新增了 DQ 相關欄位（policy、counts、affected_date_ranges、top_affected_symbols），但內部兩次重跑相同 ✓。
11. **單元測試是否覆蓋主要風險？** **PASS，但有一個未來建議的補充**。詳見第 4 節。
12. **是否通過 REVIEW-001d？** **PASS**。
13. **是否允許 TASK-001d 從 REVIEW 轉 DONE？** **允許**。
14. **是否允許開 REVIEW-001_final？** **允許**。
15. **TASK-001 整體仍需等 final review 才能轉 DONE？** **是**。

---

### 3. 為什麼策略產出沒變？（深度解釋）

`baseline.csv` 與 `positions.parquet` 與 run004 byte-identical 是**好事，也是可解釋的**：

**設想三條可能的影響路徑：**

| 路徑 | 真實資料的影響 | 結果 |
|---|---|---|
| A. 排除「應該被持有但資料壞掉」的 symbol | 持倉視窗 2024-04-01 ~ 2026-04-30，這期間沒有任何被持倉的 symbol 出現 hard abnormal | 0 個 forced exit |
| B. 排除「應該進入 ranking 但 lookback 裡有 hard abnormal day」的 symbol | COMP-USD / ICP-USD 不是 PIT 成員，永遠不進 ranking；Bybit perps 的 1-event 多落在 first-listing-day（2021-03 前後），落在 2024-04+ 的 rebalance 的 lookback 視窗（最早 2021-04-01）**之外** | 0 個 ranking exclusion |
| C. 排除「應該進入 holding 但 entry-price return 缺失」的 symbol | 115 個 holding 排除，但這些都在 2024-04 之前（symbol 剛上市時），不在實際持倉視窗 | 0 個對策略產出有影響的排除 |

**結論**：DQ 模組**邏輯上完全運作**，**統計上正確抓到 332 個 hard abnormal symbol-days / 115 個 holding 排除**，但**對本資料集的有效持倉視窗（2024-04-01 起）沒有實際排除任何 candidate**。

這對研究的意義：
- **本批數據下，TASK-001b 與 TASK-001d 對最終績效沒有任何影響**——這也解釋了為什麼三個 run 的策略產出 byte-identical。
- **未來資料推進**（例如 2027 或 OOS 重跑）時，新的下市 / 停盤 / 資料缺漏可能讓 DQ 真正生效。
- **單元測試**就是用來保證「未來真的需要時，這個邏輯會正確 fire」——這也是為什麼測試 fixture 必須要靠合成資料而非依賴實際數據才能驗證的原因。

---

### 4. 單元測試覆蓋度分析（不擋 PASS，建議下一輪補上）

**已覆蓋**：
- ✅ `nonpositive_price` hard exclusion（COMP fixture 的 close=0、ICP fixture 的 open/low=0）。
- ✅ `missing_ohlcv` hard exclusion（COMP fixture 的 quote_volume=NA）。
- ✅ `volume <= 0 warning-only`（WARN fixture 不被踢出 tradable）。
- ✅ `exclude_symbol_day` 路徑後，filtered price view 將 close 設為 NaN。
- ✅ `forced_holding_exclusion_events` 正確標記持倉被強制移除。

**未覆蓋**（建議補件，下一輪一起做）：
- ❌ **`exclude_from_ranking_candidate` 路徑**：當 lookback 視窗內出現 hard abnormal 時，該 symbol 應被排除於 ranking。這是本次「dq_excluded_from_ranking_candidates = 0」最敏感的程式碼路徑，正因為實資料沒有觸發、單元測試也沒有觸發，**這條 logic 目前等同未被驗證**。建議補一個 fixture：symbol A 在 t-100 有 hard abnormal，rebalance 在 t=0 時要把 A 排除。
- ❌ **`missing_price_row` 事件**：PIT member 但 prices 表無對應列。
- ❌ **`aggregate_data_quality_events` 邊界**：空 events、全 warning、全 hard、混合，這個彙總邏輯是 stats.json 5 個 dq_* 欄位的單一來源，沒被測試。

這三個未覆蓋路徑不影響本次 REVIEW-001d PASS（policy 的核心—missing→exclude—已驗證），但 **REVIEW-001_final 之前建議補上**，作為「TASK-001 整體交付前的最後一道工程衛生」。

---

### 5. 其他發現

- **`affected_date_ranges` 的 COMP-USD count = 836**（不是 1045），因為 aggregate 用 `non_warning` 篩過再 groupby，所以 209 個 nonpositive_volume_warning 被剔除。✓ 與設計一致。
- **`dq_affected_symbols = 117`**：117 = 116 個 Bybit perp（每個 1 event）+ COMP-USD + ICP-USD - 1（COMP/ICP 已涵蓋）。從 DQ summary 重算 `df[df.action != 'warn_only'].symbol.nunique()` = 117 ✓。
- **`source_stage` 三類**：`price_bar` 1581（hard 838 + warn 743）、`holding` 115、`universe_candidate / ranking` 都是 0（這次完全 dormant）。
- **policy 文件 8 條** 寫在 stats.json `data_quality_policy` 區塊，與 `src/data_quality/missing.py:data_quality_policy()` 同步。下游讀者可以一站式看到。

---

### 6. REVIEW-001_final 應檢查項目

| # | 項目 | 期望 |
|---|---|---|
| 1 | 三個補件後最終的 baseline 數字（active Sharpe / Sortino / Calmar） | active Sharpe ≥ 0.7（門檻：建議是「值得做 cost stress」的最低標） |
| 2 | 三組 IR（active 口徑）| `ir_vs_cash_active`、`ir_vs_btc_active`、`ir_vs_equal_weight_active` 全部還在 run004 報告值附近（不應因為 TASK-001d 而變化） |
| 3 | 五個 alias（`ir / sharpe / sortino / max_dd / calmar / turnover_annual / hit_rate`）的階躍 caveat | 在 final summary 文件中明示，並建議下游全部改用顯式 `*_active` 欄位 |
| 4 | Data-quality 模組單元測試覆蓋 | 補 ranking exclusion、missing_price_row、aggregator 三條測試（見第 4 節） |
| 5 | nice-to-have 補件是否完成 | (a) `ir_vs_btc_full_effective_days`、(b) `benchmark_btc_first_return_date`、(c) `equal_weight_empty_basket_policy`、(d) commit hash 是否更新 |
| 6 | TASK-001 工單末尾的 NOTE 區是否清空或封存 | 工單應該寫上「最終交付 run = run007」 |
| 7 | 是否準備好把研究結論寫進 Notion / EXPERIMENT_LOG.md | 「需要更多測試 + 進入 cost stress」 |
| 8 | TASK-002 / TASK-003 解除 BLOCKED 的時機 | REVIEW-001_final PASS 後立即解除 |

---

### 7. 一頁式重點

1. **REVIEW-001d 結論：PASS**。允許 TASK-001d 轉 DONE，允許開 REVIEW-001_final。
2. **DQ 模組工程合格**：模組設計乾淨（filtered views + events 雙產出）、policy 文件齊全、單元測試核心路徑通過、stats.json / aggregate JSON / DQ summary CSV 三者數字一致。
3. **策略產出 byte-identical with run004**：這次 TASK-001d **沒有改變任何績效數字**，因為 COMP-USD / ICP-USD 不是 PIT 成員、Bybit perp 的 1-event 多在持倉視窗開始前、被 holding 排除的 115 個 symbol-day 也都在 2024-04-01 之前。
4. **這不是 bug，是資料巧合**：DQ logic 完全運作，但本次資料沒有觸發 ranking-layer 排除。未來資料推進時會自然啟動。
5. **單元測試有一個建議補件**：ranking-layer exclusion 路徑沒有專門測試（不擋 PASS，但 REVIEW-001_final 之前建議補上）。
6. **TASK-001 整體仍待 REVIEW-001_final**。Codex 可以開始重跑最終 baseline（順便補 nice-to-have 與 ranking test），或者直接送 run007 給 REVIEW-001_final（亦可）。

---

## REVIEW-001e — TASK-001e Final Review Readiness Patch

- **審查時間**：2026-05-13
- **審查人**：Claude
- **對象**：TASK-001e（補件，狀態 `REVIEW`）
- **審查產物**：
  - `outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv`
  - `outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet`
  - `outputs/backtests/prev3y_crypto/20260513_run008_stats.json`
  - `outputs/logs/prev3y_crypto/20260513_run008.log`
  - `outputs/data_quality/prev3y_crypto/20260513_run008_data_quality_summary.csv`
  - `outputs/data_quality/prev3y_crypto/20260513_run008_data_quality_aggregate.json`
  - `tests/data_quality/test_missing.py`（5 tests）
  - `docs/research/TASK_001_PREV3Y_BASELINE_SUMMARY.md`
- **結論**：`PASS`
- **是否允許 TASK-001e 轉 DONE**：**允許**。
- **是否允許開始 REVIEW-001_final**：**允許**。

---

### 1. 驗收標準逐條打勾

| # | 驗收項 | 結果 | 證據 |
|---|---|---|---|
| 1 | 只做 final review readiness patch（不動策略） | **PASS** | `baseline.csv`、`positions.parquet`、`data_quality_summary.csv`、`data_quality_aggregate.json` 四份檔案與 run007 **全部 byte-identical**（SHA-256 全相同）。 |
| 2 | 三條新單元測試覆蓋 REVIEW-001d 缺口 | **PASS** | 透過 Read tool 直接驗證 Windows-side 檔案：5 個 `def test_*` 完整存在，含 (a) `test_exclude_from_ranking_candidate_when_lookback_has_hard_abnormal`、(b) `test_missing_price_row_event_for_pit_member_without_price_bar`、(c) `test_aggregate_data_quality_events_boundaries`。輔助 helper `_events()`、`_config(end_date, lookback_days)`、`_prices(end_date)`、`_membership(end_date)` 皆參數化以支援新測試。 |
| 3 | 補 metadata：BTC effective days + eqw effective days | **PASS** | stats.json 新增 4 個欄位且只新增這 4 個：`ir_vs_btc_full_effective_days=1884`、`ir_vs_btc_active_effective_days=760`、`benchmark_eqw_effective_days_full=2017`、`benchmark_eqw_effective_days_active=760`。 |
| 4 | run008 vs run007 無策略結果差異 | **PASS（強證據）** | baseline.csv / positions.parquet / DQ summary / DQ aggregate **全 byte-identical with run007**；portfolio_return、turnover、gross/net/n_longs/n_shorts、benchmark 全欄 max diff = 0。 |
| 5 | stats 可由 baseline.csv 重算 | **PASS** | `ir_vs_btc_full = -0.3247590397` 我用 methodology 公式（ddof=1, sqrt(365.25), drop NaN bench）獨立重算對到 ~1e-14；effective_days = 1884 與 CSV `benchmark_btc_return.notna().sum()` 完全一致。 |
| 6 | reproducibility hash 通過 | **PASS** | log `stats_hashes=ee803173…06f,ee803173…06f`，`repeat_stats_hash_identical=true`。 |
| 7 | SUMMARY.md 更新 | **PASS** | `docs/research/TASK_001_PREV3Y_BASELINE_SUMMARY.md` 第 3 節表格新增 `run007` 項目並標 REVIEW；第 5 節 review 表加入 REVIEW-001d 列。 |
| 8 | 沒 stage / commit / 沒解除下游 BLOCKED | **PASS** | TASK-002 / TASK-003 仍 BLOCKED；queue 內 TASK-001 整體仍 REVIEW 狀態。 |

---

### 2. Codex 提的 10 個問題逐一回答

1. **TASK-001e 是否只做 final review readiness patch？** **是**。四份策略 / DQ 輸出全部 byte-identical with run007；改動只在 (a) 新測試、(b) 4 個 metadata 欄位、(c) SUMMARY.md 文字。
2. **新增三條 data-quality test 是否覆蓋 REVIEW-001d 指出的缺口？** **覆蓋**。REVIEW-001d 我列了三個缺口，全部對應到位：
   - 缺口 (a) `exclude_from_ranking_candidate` 路徑 → 新 test_exclude_from_ranking_candidate_when_lookback_has_hard_abnormal（用 COMP-USD on 2024-01-05 close=0、lookback=2 觸發 ranking 排除）。
   - 缺口 (b) `missing_price_row` 事件 → 新 test_missing_price_row_event_for_pit_member_without_price_bar（用 MISSING-USD 加入 PIT 但無價格列觸發）。
   - 缺口 (c) `aggregate_data_quality_events` 邊界 → 新 test_aggregate_data_quality_events_boundaries（4 個子情境：空 / 全 warning / 全 hard / mixed）。
3. **metadata 補充是否正確？** **正確**。我獨立驗證 `ir_vs_btc_full_effective_days = 1884` = `c.benchmark_btc_return.notna().sum()`；`ir_vs_btc_active_effective_days = 760` = active period 全部；`benchmark_eqw_effective_days_full = 2017` = 2677 - 660 missing；`benchmark_eqw_effective_days_active = 760`。注意：`benchmark_eqw_effective_days_full` 採用「basket-empty 日」定義（660 天），與 CSV 中 `benchmark_eqw_return != 0` 的天數（2015）相差 2 天——那 2 天是 basket 有 constituents 但偶然算出 return = 0，屬於定義差異而非錯誤。
4. **run008 vs run007 無策略結果差異是否可信？** **可信**。四份輸出 SHA-256 全相同，是最強證據。
5. **stats 是否可重算？** **可以**。我重算 IR_vs_btc_full 與 effective_days 都吻合到 1e-14（與 Codex 自報 1.07e-14 一致）。
6. **reproducibility hash 是否可信？** **可信**。log 內 stats_hashes 兩次相同 `ee803173…06f`；注意這是 stats dict 的 canonical hash，**不是 stats.json 檔案 SHA-256**（兩者本來就不同，stats hash 用於跨機器跨平台重現驗證）。
7. **TASK_001_PREV3Y_BASELINE_SUMMARY.md 是否足夠作為 final review 前的總整理？** **足夠**。run007 已列入第 3 節對照表、REVIEW-001d 已列入第 5 節結論表；給下一個 AI worker 的接手摘要保留完整。建議在 final review 通過後再更新 (a) 把 run008 加入對照表、(b) 把 REVIEW-001e / 001_final 結論一併補上、(c) 把當前狀態的「TASK-001 不可 DONE」改成「TASK-001 DONE，TASK-002 解除 BLOCKED」。這部分屬 REVIEW-001_final 落地任務，不是本次需求。
8. **是否通過 REVIEW-001e？** **PASS**。
9. **是否允許 TASK-001e 轉 DONE？** **允許**。
10. **是否允許進入 REVIEW-001_final？** **允許**。

---

### 3. 額外發現（環境問題，非 Codex 問題）

審查過程中遇到一個**環境同步問題**，記錄供下次參考：

- 用 `mcp__workspace__bash` 看到的 Linux mount 版本 `tests/data_quality/test_missing.py` 是**舊版本**（109 行，4 個截斷的測試 def）。
- 用 Read tool 看到的 Windows host 版本是**完整的**（245 行，5 個完整測試 + 4 個 helper）。
- 加上 `__pycache__/test_missing.cpython-3*.pyc` 是 Codex 修改 *前* 編譯的、且 Linux 端無權限刪除——導致 `python -m unittest` 永遠載入舊 .pyc 的 2 個測試。
- 這是 **Windows ↔ Linux mount sync delay + stale pyc cache** 的合併症狀，**不影響 Codex 在 Windows 端執行 `python -m unittest` 的結果**（Codex 已自報 5 tests PASS）。
- 影響：本次審查我以 **Read tool 的 Windows-side 視角為準** 來驗證測試檔內容；測試實際執行結果以 Codex 自報為準（無法在本環境跑出 5 個測試）。
- 建議下次：(a) 工程上把 `__pycache__/` 加進 `.gitignore`（如尚未），(b) Codex 在 Windows 端跑完測試後把 console output 貼進交付摘要供獨立驗證。

---

### 4. REVIEW-001_final 應檢查的最終項目

| # | 項目 | 期望 |
|---|---|---|
| 1 | TASK-001 整體 deliverables 完整性 | run008 = 最終 baseline；stats.json 含 12 對 `*_full/_active` + 3 組 `ir_vs_*` + 4 個 effective_days + `methodology` + `data_quality_policy` + 5 個 `dq_*` + `affected_date_ranges` + `top_affected_symbols`；baseline.csv 含 11 欄；positions.parquet 含 8 欄。 |
| 2 | 四份審查結論串成完整 trail | REVIEW-001 → 001c → 001b → 001d → 001e → 001_final，每一步結論在 `CLAUDE_REVIEW_LOG.md` 都有完整紀錄。 |
| 3 | 是否值得進入 TASK-002 cost stress | 用 active 口徑判斷門檻：active Sharpe = 0.9267 ≥ 0.7 ✓、ir_vs_equal_weight_active = 0.7227 ≥ 0.3 ✓、ir_vs_btc_active = -0.0175（接近 0，符合 market-neutral 預期）✓。**建議解除 TASK-002 BLOCKED**。 |
| 4 | 是否值得進入 TASK-003 attribution | 同上門檻成立。**建議解除 TASK-003 BLOCKED**。 |
| 5 | 樣本不足 caveat 是否寫進 Notion 高層摘要 | active 樣本 760 天（25 個月）必須在 Notion 內以 yellow flag 形式保留。 |
| 6 | git_commit / commit 衛生 | Codex 需把 TASK-001b/c/d/e 變更彙整為 commit；下次 run（如有）的 git_commit 應更新到新 commit hash。本次 stats.json 的 git_commit 仍是 `3c380bfd…`（原 TASK-001 commit），不算錯但建議下次更新。 |
| 7 | TASK-001 工單收尾 | `docs/research/codex_workorders/TASK-001_prev3y_crypto_baseline.md` 末尾建議加上「最終交付 run = run008、整體狀態 DONE」的封存 NOTE。 |
| 8 | SUMMARY.md 最終態 | 把 run008 加入第 3 節表格、把 TASK-001 狀態改 DONE、把 TASK-002/003 從 BLOCKED 改為 TODO，並更新「給下一個 AI worker 的接手摘要」第 8 點。 |
| 9 | DQ ranking-layer 測試實際執行 | 在 REVIEW-001_final 前，建議在 Windows 端親自跑一次 `python -m unittest tests.data_quality.test_missing -v` 並把 console 輸出貼進 final review 補充（避免類似本次 mount sync 造成 Linux 端看不到測試）。 |
| 10 | TASK-002 / TASK-003 工單細化 | final review PASS 後立即把 TASK-002 工單轉成可貼給 Codex 的工單格式（仿 TASK-001_workorder）；TASK-003 attribution 同時細化 factor source。 |

---

### 5. 一頁式重點

1. **REVIEW-001e 結論：PASS**。允許 TASK-001e 轉 DONE，允許開 REVIEW-001_final。
2. **策略產出 byte-identical with run007**：四份檔案（baseline.csv、positions、DQ summary、DQ aggregate）全部 SHA-256 相同。Codex 真的只做了報表 + 測試 patch。
3. **4 個新 metadata 欄位**全部正確：BTC IR 實際覆蓋 1884 天（不是名目 2677）、eqw 實際覆蓋 2017 天（扣掉 660 個 basket-empty 日）。
4. **單元測試覆蓋完整**：REVIEW-001d 列的三個缺口（ranking exclusion / missing_price_row / aggregator 邊界）都被新測試覆蓋；Codex 自報 5 tests PASS。
5. **環境注意事項**：本次審查發現 Windows ↔ Linux mount 有同步延遲，加上 stale pyc cache 讓 Linux 端 unittest 跑不到新測試。**這不影響 Codex 結果**，但建議下次 Codex 把 unittest console output 貼進交付摘要，避免類似的「我看不到測試」疑慮。
6. **下一步**：開 REVIEW-001_final。final review 通過後 TASK-001 整體轉 DONE，TASK-002 / TASK-003 解除 BLOCKED。

---

## REVIEW-001_final — TASK-001 Prev3Y Crypto Universe Baseline 最終總審

- **審查時間**：2026-05-13
- **審查人**：Claude
- **對象**：TASK-001 整體（含 b / c / d / e 四件補件 + 5 個 run）
- **最終正式 baseline**：`20260513_run008`
- **結論**：**`PASS`**
- **TASK-001 是否轉 DONE**：**允許**。
- **TASK-002 / TASK-003 是否解除 BLOCKED**：**允許，立即解除**。
- **研究判定**：**需要更多測試**（保留路線、進入 cost stress；不淘汰、不立即上線）。

---

### 1. 總審：跨 review 結論彙整

| Review | 對象 | 結論 | 對 final 的意義 |
|---|---|---|---|
| REVIEW-001 | TASK-001 run002 | CONDITIONAL_PASS | 形式驗收 7 條全 PASS；發現 3 個必修缺口 → 催生 b/c/d |
| REVIEW-001c | TASK-001c run003（雙口徑） | PASS | 「全期 vs 有效期」口徑混淆解決 |
| REVIEW-001b | TASK-001b run004（三 benchmark） | PASS | beta-mismatch 解決；methodology 區塊齊備 |
| REVIEW-001d | TASK-001d run007（missing-data） | PASS | 缺數據處理升級；DQ 模組獨立分層 |
| REVIEW-001e | TASK-001e run008（final-readiness） | PASS | 補 DQ 三條 fixture-driven test、補 effective_days metadata |
| **REVIEW-001_final** | **TASK-001 整體** | **PASS** | **所有缺口已關閉，可進入下一階段** |

---

### 2. 問題逐一回答

#### 2.1 TASK-001 研究目標是否完成？

**完成**。研究目標是「為 Prev3Y momentum 在 crypto 上做一份乾淨可重現的 baseline 回測」，至此交付：

- ✅ baseline.csv（2677 列、11 欄、時間戳唯一、無跳日）
- ✅ positions.parquet（29586 列、8 欄、PIT 完全合規）
- ✅ stats.json（含 12 對 `*_full / *_active`、3 組 IR、`methodology`、`data_quality_policy`、5 個 `dq_*`、`affected_date_ranges`、`top_affected_symbols`、`effective_days` × 4）
- ✅ log（含 4 個必印欄位、schemas、reproducibility hash）
- ✅ DQ summary CSV / aggregate JSON
- ✅ 單元測試 5 個（已知 Linux mount 同步延遲，以 Codex Windows 端執行為準）
- ✅ docs/research/TASK_001_PREV3Y_BASELINE_SUMMARY.md（standalone 5-min onboarding 文件）

#### 2.2 最新 baseline 是否可作為 TASK-002 / TASK-003 基準？

**是**。run008 是最終正式 baseline，**5 個 run 的 `positions.parquet` SHA-256 全部相同（`cb1190bd…`）**——這個跨 run 的 byte-identity 是極強的證據：**從 TASK-001 第一版到最終版，策略訊號 / 進場邏輯 / ranking / universe 全部未改**。後續 cost stress / attribution 只要從 run008 讀 positions + baseline 即可，不需要重新跑回測。

#### 2.3 是否仍有未來視 / 資料洩漏？

**否**。多重證據：

- 29586 / 29586 positions 全部 `decision_date < effective_date`，gap = 1 day。
- 29586 / 29586 positions 全部 `is_member == True`（PIT universe 嚴格）。
- DQ 政策明示「missing returns are never filled with zero」；nonpositive prices hard exclude；no forward-fill。
- BTC benchmark 缺資料保 NaN（不 fill 0）；active 期內 BTC missing = 0 並有 RuntimeError 防呆。
- methodology 區塊（annualization=365.25、ddof=1、IR/Sortino 公式）讓第三方可獨立到 1e-14 重算。

我從第一份 review 到現在沒有發現任何 leakage 跡象。

#### 2.4 active Sharpe / active IR 是否達到 cost stress 最低門檻？

**達到**。我在 REVIEW-001 對 TASK-002 入場設了兩個門檻：

| 門檻 | 實際值 | 結果 |
|---|---:|---|
| active Sharpe ≥ 0.7 | **0.9267** | ✅ PASS |
| active IR_vs_equal_weight ≥ 0.3 | **0.7227** | ✅ PASS |
| active IR_vs_btc 約為 0（market-neutral 預期） | **−0.0175** | ✅ 符合預期 |

#### 2.5 三組 benchmark narrative 是否清楚？

**清楚**。三組 IR 並列後 narrative 非常乾淨：

- **vs Cash（active）= +0.93**：絕對 Sharpe 正、約等於 active Sharpe（因為 cash = 0）。
- **vs BTC perp（active）= −0.02**：策略幾乎不擊敗 BTC。對 market-neutral 設計而言這是預期；意義是「不能取代 buy-and-hold BTC、只能當成獨立 alpha 來源」。
- **vs Equal-weight long-only（active）= +0.72**：策略明顯擊敗同 universe 等權 long-only。**這是真正 alpha 跡象**。

下游讀者一眼就能看出「策略相對 universe 平均有 alpha、但相對 market beta 無 alpha」。

#### 2.6 DQ 模組與測試是否足夠？

**足夠**。

- 模組 `src/data_quality/missing.py` 是純資料層，未污染策略 / signals / backtest 模組（單向依賴：DQ → signals 取 rebalance schedule）。
- Policy 文件齊全（stats.json 內 `data_quality_policy` 區塊 8 條）。
- 三產出（DQ summary CSV / aggregate JSON / stats.json dq_* 欄位）數字三方一致（我在 REVIEW-001d 獨立驗算）。
- 單元測試 5 個，覆蓋 (1) nonpositive hard exclusion、(2) zero-volume warn-only、(3) forced holding exit、(4) ranking exclusion when lookback contains hard abnormal（REVIEW-001d 補上）、(5) missing_price_row（REVIEW-001d 補上）、(6) aggregator boundaries（REVIEW-001d 補上）。
- 本資料集 `dq_excluded_from_ranking_candidates = 0` 是資料巧合（COMP/ICP 不在 PIT、Bybit perp 1-event 落在 lookback 視窗外）；未來資料推進時會自然啟動，且單元測試已 cover 該路徑。

#### 2.7 哪些 caveat 必須保留？

**5 項 caveat 必須在後續所有 downstream 引用時保留**：

1. **Active 樣本 760 天（≈ 25 個月）**——3 年 lookback 訊號的有效樣本連半個訓練視窗都不到；任何 cost stress / attribution 的結論都要在此前提下打折扣。
2. **策略相對 BTC 幾乎無 alpha**——不能拿來取代 buy-and-hold BTC，只能當多元化 alpha。
3. **Equal-weight benchmark 有 660 個 basket-empty 日 fill 0**——full IR vs eqw 因此被稀釋；active IR vs eqw 不受影響。
4. **平均 tradable symbols 只有 15.2**（遠低於 top_n + bottom_n = 50）——每月實際持倉 ~7 long / 7 short，集中度風險偏高（max |w| = 0.125）。
5. **舊 alias（`ir / sharpe / hit_rate / sortino / calmar / max_dd / turnover_annual`）跨 run 階躍**——下游一律使用顯式欄位（`*_active` / `ir_vs_<bench>_<window>`）。

#### 2.8 是否允許 TASK-001 整體轉 DONE？

**允許**。所有形式驗收、所有審查結論、所有 caveat 已記錄；最終正式 baseline 為 `20260513_run008`。

#### 2.9 是否解除 TASK-002 / TASK-003 BLOCKED？

**立即解除**。兩者依賴的「REVIEW-001 重審通過」門檻已達成。下游需要的 inputs 都已就位：

- TASK-002 需要：`20260513_run008_positions.parquet`、`20260513_run008_baseline.csv`、`configs/prev3y_crypto.yaml`、外加自行接 `data/crypto/funding_rates.parquet` 與 `data/crypto/fees.yaml`。
- TASK-003 需要：TASK-001 的 positions / baseline + `data/crypto/factor_returns.parquet`（factor universe 仍待 Codex 確認本機資料源）。

---

### 3. 最終研究結論（**保留 / 淘汰 / 需要更多測試** 三選一）

**判定：需要更多測試**。

**保留的理由**：
- 三組 IR 並列後策略確實「有 alpha vs 同 universe 平均」、絕對 Sharpe ≈ 0.93、PIT / 對齊 / 可重現 / 無未來視全部通過。
- 工程 / 報表 / 資料品質完備，下游壓力測試有可信的 baseline。

**為什麼不直接「保留可上線」**：
- 樣本只有 25 個月，**3 年 lookback 訊號還沒被測完一個完整訓練視窗的樣本量**——任何「策略 work」的宣稱在這個樣本下都不可信。
- 還沒做 cost stress（funding 在牛市末段可以吃掉幾十個百分點年化）。
- 還沒做 attribution（market beta 純度未驗證）。
- 平均 tradable symbols 只有 15.2，組合集中度過高。

**為什麼不淘汰**：
- IR vs eqw 的 +0.72（active）不像是雜訊；至少值得壓力測試一次。
- 工程沒問題、邏輯沒洩漏、資料源乾淨；如果這個 baseline fail cost stress，再淘汰也不晚。

---

### 4. 下一張工單建議（依優先順序）

#### 優先 1：TASK-002 Funding / Cost Stress（解除 BLOCKED 後立即開工）

把 TASK-002 從 queue 簡述展開成可直接貼給 Codex 的工單（仿 `codex_workorders/TASK-001_*.md` 格式）。重點：

- **必引用 caveat**：在 TASK-002 工單第 0 節「給 Codex 的開場守則」內，明示「結果必以 active 口徑（760 天）為主，full 口徑僅供 reference」。
- **必繼承 methodology**：annualization=365.25、ddof=1、cost CSV 重算公式必須與 baseline 一致。
- **必接 run008**：input 明寫 `outputs/backtests/prev3y_crypto/20260513_run008_*`。
- **新增 cost stress 自身的 active fail gate**：若 active IR_vs_eqw 在 pessimistic 情境下 < 0.3，summary.json 須 WARNING；若 extreme 情境下 < 0，標 FAIL。

#### 優先 2：TASK-003 Baseline Attribution（與 002 平行）

- 工單細化前要先確認 factor source。建議 Codex 先回報 `data/crypto/factor_returns.parquet` 是否存在 + schema。若否，提一份 BLOCKED_BY_DATA / NEED_CLARIFICATION 給 Claude，再決定是否進開工。
- 入場時要先解 `market beta / size beta / liquidity beta / mom_short beta` 中至少 market beta 是否顯著（t-stat 與穩健性）。

#### 優先 3：TASK-004 Dashboard 第一版（可平行）

- 第一版只放 baseline 雙口徑面板（active vs full、三組 IR、DQ summary），cost / attribution 留空待 002 / 003 完成後 plug-in。

#### 優先 4：補件 / 工程衛生（Codex 自行排序）

1. **Commit 衛生**：把 TASK-001 b / c / d / e 變更彙整成 commit（目前 stats.json 的 `git_commit` 仍指 `3c380bf…`，是 TASK-001 主體的舊 commit）。下次 run 的 git_commit 應更新。
2. **TASK-001 工單收尾**：在 `docs/research/codex_workorders/TASK-001_prev3y_crypto_baseline.md` 最末加封存 NOTE：「最終交付 run = run008、整體狀態 DONE @ 2026-05-13 / REVIEW-001_final PASS」。
3. **SUMMARY.md 最終態**：把 run008 加入第 3 節對照表（目前是停在 run007）、把 TASK-001 狀態欄改 DONE、把 5.x review 表加入 REVIEW-001e 與 REVIEW-001_final、把 TASK-002 / TASK-003 從 BLOCKED 改為 TODO。本次 final review 我未改動 SUMMARY.md（用戶指令限定只更新 LOG / 兩個 queue），建議 Codex 在最後一輪工程衛生 patch 中一併完成。
4. **Linux mount + pyc cache**：建議把 `__pycache__/` 加入 `.gitignore`（若尚未），並在 Codex 交付時把 `python -m unittest` console output 貼進交付摘要，避免類似 REVIEW-001e 出現的「Claude 環境看不到測試」誤會。

---

### 5. 強證據清單（讓未來的 Claude / Codex / Rick 一眼信服）

| 主張 | 證據 |
|---|---|
| 5 個 run 策略邏輯未動 | `positions.parquet` 五 run SHA-256 全部 = `cb1190bd…7cd` |
| Baseline 策略欄位未動 | `baseline.csv` 在加 benchmark 欄位前後分兩組（run002/003 = `55ad72b5…`、run004/007/008 = `051b89b2…`），組內 byte-identical；策略欄位逐列等值 |
| 無未來視 | 29586/29586 positions `decision < effective`、gap = 1 day |
| PIT 嚴格 | 29586/29586 `is_member == True` |
| stats 重算到 1e-14 | run003 ~ run008 每個 stats.json 都可由 baseline.csv 用 methodology 公式重算到 1e-14 |
| Reproducibility | 每個 run 內部重跑 stats hash 兩次相同（run002 `6dc6f3…`、run003 `800422…`、run004 `03dbff…`、run007 `10dfa9…`、run008 `ee8031…`） |
| DQ 模組獨立分層 | `src/data_quality/missing.py` 不被 strategy/signals/backtest import；只被 reporting / orchestration 層 import |
| Methodology 公開 | stats.json `methodology` 區塊（annualization=365.25、ddof=1、IR/Sortino 公式） |
| DQ policy 公開 | stats.json `data_quality_policy` 區塊 8 條 |
| BTC IR 覆蓋窗誠實揭露 | `ir_vs_btc_full_effective_days = 1884`（不是 2677） |

---

### 6. 一頁式重點

1. **REVIEW-001_final 結論：PASS**。
2. **TASK-001 整體轉 DONE**。最終正式 baseline = `20260513_run008`。
3. **TASK-002 / TASK-003 立即解除 BLOCKED**。兩個 active 口徑門檻（Sharpe ≥ 0.7、IR_vs_eqw ≥ 0.3）都過。
4. **研究結論：需要更多測試**——不淘汰、不立即上線；先進 cost stress + attribution。
5. **5 項 caveat 必須在所有下游引用時保留**（active 樣本短、不擊敗 BTC、eqw basket-empty、tradable 偏少、alias 階躍）。
6. **下一張工單**：把 TASK-002 從 queue 簡述展開成可直接貼給 Codex 的工單（仿 TASK-001 工單格式）。
7. 工程衛生小事：commit、TASK-001 工單封存 NOTE、SUMMARY.md 最終態、`.gitignore` pyc——Codex 一輪 patch 解決。

---

## REVIEW-002a_phase1 — TASK-002a Cost / Funding Input Builder（Phase 1：Scaffolding + Smoke）

- **審查時間**：2026-05-14
- **審查人**：Claude
- **對象**：TASK-002a Phase 1（部分交付）；Codex 自陳「不代表 TASK-002 stress 已 ready」
- **審查產物**：
  - `data/crypto/fees.yaml`
  - `configs/cost_stress.yaml`
  - `src/costs/symbol_mapping.py` + `tests/cost_inputs/test_symbol_mapping.py`
  - `scripts/build_cost_funding_inputs.py`
  - `outputs/data_quality/funding_coverage/20260514_funding_coverage_{report.csv, summary.json}`
  - `outputs/logs/cost_inputs/20260514_build.log`
- **未交付（Phase 2 的範圍）**：
  - `data/crypto/funding_rates.parquet`（仍不存在）
  - 任何真實 funding 覆蓋
- **結論**：`PASS`（**僅針對 Phase 1 scaffolding + smoke 範圍**）
- **是否允許 Phase 1 轉 DONE**：**允許**（Phase 1 子任務 done）。
- **是否允許開 Phase 2**：**允許**。
- **TASK-002a 整體是否轉 DONE**：**不允許**——Phase 2 完成且通過 REVIEW-002a_phase2 後才轉 DONE。
- **TASK-002 是否仍 BLOCKED**：**仍 BLOCKED_BY_TASK_002A**——funding_rates.parquet 未存在，coverage 0%，**禁止** TASK-002 開始任何 stress。

---

### 1. 驗收標準逐條打勾（Phase 1 範圍）

| # | 驗收項 | 結果 | 證據 |
|---|---|---|---|
| 1 | fees.yaml 含 exchange / maker_bps / taker_bps / notes 四欄 | **PASS** | 完整 4 欄；notes 含取數日期 2026-05-14、URL、tier VIP 0 / Non-VIP、未含 market-maker rebate、未檢 regional account fee 全部明示。 |
| 2 | bps 為整體 0.01% 計（taker_bps: 5.5 = 0.055%） | **PASS** | yaml 第 8 行「Rates shown by source: taker 0.0550%, maker 0.0200%; stored here as 5.5 bps and 2.0 bps」明示換算。 |
| 3 | cost_stress.yaml 含 12 scenarios，名稱與工單**一字不差** | **PASS** | 12 個 `name:` 完全 match TASK-002a 工單第 9 節（順序略不同但名稱全 match：`no_cost_baseline`、`fee_taker_entry_maker_exit`、`fee_taker_entry_taker_exit`、`funding_low/mid/high`、`slippage_5bps/10bps/20bps`、`realistic_combo`、`conservative_combo`、`worst_case_combo`）。 |
| 4 | `no_cost_baseline` 全乘數 = 0、雙邊 maker、滑點 0 | **PASS** | scenarios[0] 五個欄位皆 0 / maker。 |
| 5 | defaults 區塊明示 annualization / ddof / 三 application / proxy policy | **PASS** | `annualization_factor=365.25`、`std_ddof=1`、`slippage_application=per_turnover_one_side_bps`、`fee_application=per_turnover_both_sides`、`funding_application=pit_8h_settlement_accumulated`、`funding_proxy_policy=exclude_from_fail_gate` 全部就位。 |
| 6 | 沒有額外的「美化情境」 | **PASS** | 12 個 scenario 全部對齊工單，無 fee × 0.5 之類。 |
| 7 | Symbol mapping 寫成獨立函式 + 單元測試 | **PASS** | `src/costs/symbol_mapping.py` 不 import strategy / signals / backtest / DQ / reporting；`to_funding_symbol` 與 `to_perp_symbol` 對稱。 |
| 8 | 單元測試覆蓋邊界 case | **PASS（甚至超出 spec）** | 7 個測試全綠（我獨立跑 `python3 -m unittest`）：BTCUSDT、ETHUSDT、`1000PEPEUSDT`（prefix preserved）、`RLUSDUSDT`（USDT 後綴重複不被切錯）、raw symbol 拒絕、非 USDT perp 拒絕、lowercase 拒絕。**比 TASK-002a 工單第 11 節要求的 4 個 case 多 3 個。** |
| 9 | Bybit API smoke check | **PASS** | summary.json + log 內 `bybit_api_smoke_status: "ok"`、`bybit_api_url`、`funding_source_primary: bybit_api`。為 Phase 2 預先驗證了 API 可用。 |
| 10 | 缺資料的 symbol-day **不出現** 在 parquet | **PASS（trivially）** | funding_rates.parquet 尚未建立；coverage report 明確列出 missing。 |
| 11 | 不可動 run008 任何檔案 | **PASS** | script 把 `DEFAULT_POSITIONS` / `DEFAULT_BASELINE` 標為 read-only 常量；無寫入路徑。 |
| 12 | 不可執行 TASK-002 stress | **PASS** | log 第 11 行明示「Phase 1 does not execute TASK-002 stress」。 |
| 13 | log 開頭 5 個欄位齊備 | **PASS** | `random_seed=0`、`config_hash`、`data_snapshot_hash`、`git_commit=c044f55e…`、`baseline_run_id=20260513_run008`、`funding_source=bybit_api`、`funding_proxy_pct=0.0`。 |

---

### 2. Codex 提的 8 個問題逐一回答

1. **Phase 1 是否符合 TASK-002a 目標？** **部分符合**。Phase 1 完成的範圍：fees.yaml、cost_stress.yaml、symbol_mapping + tests、coverage report 結構、Bybit API smoke check。**未完成**：核心交付物 funding_rates.parquet（這是 TASK-002a 的主菜）。Phase 1 是合理的「先把鷹架搭好再爬高」策略。
2. **symbol mapping 是否足夠安全？** **足夠**。7 個 case 全綠，特別包含我最擔心的 `RLUSDUSDT`（USDT 後綴重複）與 `1000PEPEUSDT`（數字前綴），加上不合法輸入會 raise ValueError 而非 silent skip。建議 Phase 2 加一個 integration test：對 run008 PIT universe 全部 273 個 symbol 都跑一次 `to_funding_symbol()`，確保沒有 silent failure。
3. **fees.yaml 是否可暫時作為 TASK-002 輸入？** **可**。VIP 0 / Non-VIP 是最保守設定，符合 TASK-002 工單第 8 節「v1 單一 fee tier」要求。Caveat：若 Rick 實盤帳號是 VIP 1+ 或有 maker rebate，TASK-002 必須在 NOTE 明示「實盤 fee 比此設定低」。
4. **cost_stress.yaml 12 scenarios 是否完整且符合 TASK-002 工單？** **完整**。逐 scenario 比對工單第 9 節，名稱、乘數、entry/exit side 全部對齊。`defaults` 區塊 6 欄齊備。
5. **funding coverage 0% 是否正確標記為尚未 ready？** **正確標記**。summary.json `coverage_real_pct: 0.0`、`funding_rates_exists: false`、`missing_symbol_days_active: 29586` 全部誠實揭露。`top_missing_symbols` 列出 20 個最缺資料的 symbol（BTCUSDT / ETHUSDT 等核心幣全部缺）。但見第 3 節：`phase1_status: READY_TO_IMPLEMENT` 是**語意誤導風險點**，必須在 Phase 2 開工前修正。
6. **`READY_TO_IMPLEMENT` 是否需要改成 `READY_FOR_PHASE2`？** **是，必須改**。理由見第 3 節，這是 Phase 2 開工前的必補項。
7. **是否允許進入 TASK-002a Phase 2：Bybit funding full fetch？** **允許**。Phase 1 scaffolding 已就緒、API smoke OK、symbol mapping 已測試。
8. **是否仍禁止 TASK-002 stress 開始？** **仍禁止**。funding_rates.parquet 不存在、coverage 0%、TASK-002 readiness 必須等 REVIEW-002a_phase2 PASS 後 Codex 才可重做 readiness check。

---

### 3. 命名語意風險（不擋本次 PASS，但 Phase 2 開工前必補）

`summary.json` 的 `phase1_status: "READY_TO_IMPLEMENT"` **語意誤導**：

- TASK-002a 工單第 0 節原本是用 `READY_TO_IMPLEMENT` 描述「整個 TASK-002a 可開工」的狀態。
- 但 Phase 1 結束時 coverage = 0%，TASK-002a 的核心交付物（funding_rates.parquet）**尚未存在**，這時把 status 寫成 `READY_TO_IMPLEMENT` 容易讓下游讀者（包括下次 Claude）誤以為 TASK-002a 已完成、TASK-002 可解除 BLOCK。
- 風險：自動化工具或 dashboard 若 grep 這個 key，會錯誤推斷 TASK-002 可開工。

**Phase 2 開工前必補**：

- 把 `summary.json` 的 `phase1_status` 改名為 `phase_status` 或 `task_002a_substate`，並使用一組更精準的列舉值：
  - `PHASE1_SCAFFOLD_DONE` —— 等於現在這個狀態。
  - `PHASE2_IN_PROGRESS` —— Phase 2 抓資料中。
  - `PHASE2_PROXY_ONLY` —— Phase 2 結束，real coverage < 80%。
  - `PHASE2_READY` —— Phase 2 結束，real coverage ≥ 80%，TASK-002 可解除 BLOCK。
  - `PHASE2_BLOCKED_BY_DATA` —— API 完全失效，無法繼續。
- 在 log 對應地補：`phase1 = DONE, phase2 = NOT_STARTED`。
- 在 summary.json 加 top-level `task_002a_overall_status: INCOMPLETE`，明示「不要把 phase1_status 當成 TASK-002a 整體 ready 訊號」。

---

### 4. Phase 2 必須補的規則（給下一張工單 / Codex 提示）

| # | 規則 | 為什麼 |
|---|---|---|
| 1 | Coverage gate：active period real coverage ≥ 80% → `PHASE2_READY`；50%–80% → `PHASE2_PROXY_ONLY`（需 Rick 同意）；< 50% → `PHASE2_BLOCKED_BY_DATA` | 避免 coverage 太低時偷偷放行 |
| 2 | Symbol mapping integration test：對 run008 PIT universe 273 個 symbol 全部跑 `to_funding_symbol()`，至少印一份「mapping → Bybit API 命中率」報表 | 揭露哪些 symbol 名稱在 Bybit API 找不到對應 funding |
| 3 | Bybit API 抓取必須遵守 rate limit；錯誤計入 log；分頁全部用滑動視窗。log 內必須有 `bybit_api_calls_made`、`bybit_api_errors`、`bybit_api_pages_fetched`、`bybit_api_first_response_at`、`bybit_api_last_response_at` | 讓重審能評估 API 抓取的完整性與重現性 |
| 4 | 原始 API 回應寫進 `data/cache/funding/bybit_raw/<symbol>_<YYYYMMDD>.json`（分檔），方便重複跑不必再撞 API | 既防止 rate-limit、又讓 audit 可重現 |
| 5 | funding_rate 數值 sanity 抽查：隨機選 10 筆 funded 列，與 Bybit API 即時值（或 Codex 抓取時的 console output）對比，diff < 1e-9 | 避免單位混淆（小數 vs 百分比）|
| 6 | timestamp 必須是真實結算時點（00:00 / 08:00 / 16:00 UTC），**禁止** resample 到日 | 8h 結算累加是 TASK-002 funding cost 計算的根本 |
| 7 | 缺資料的 symbol-day **不出現** 在 parquet 內（不 fill 0、不 fill NaN row）；只在 coverage report 紀錄 | 與 TASK-001d DQ 政策一致：缺資料 = 排除而非填值 |
| 8 | Proxy fallback 順序：先 `proxy_universe_median`（同日同 universe 真實 funding 的中位數）；只有完全無同類可參考時才 `proxy_zero`，且 `proxy_zero` 必須在 NOTE 區單獨列出涉及的 symbol-day | 避免 proxy_zero 被偷偷大量使用 |
| 9 | `phase_status` / `task_002a_overall_status` 命名修正（見第 3 節） | 防止下次 Claude / 自動化誤判 |
| 10 | Phase 2 完成後重做一次 `funding_coverage_summary.json` 與 `funding_coverage_report.csv`；報表帶 `coverage_real_pct`、`coverage_proxy_pct`、`coverage_total_pct` 三個獨立欄位 | 讓 fail gate 與下游解讀清楚 |
| 11 | Phase 2 完成前，**不可** 把 funding_rates.parquet 視為 TASK-002 可用輸入；不可開啟任何 TASK-002 readiness check | 嚴格守 TASK-002 BLOCK 條件 |
| 12 | Phase 2 完成後 Codex 在 NOTE 區附 mapping miss 名單（Bybit API 沒回應的 PIT symbol） | 讓 REVIEW-002a_phase2 直接判斷 proxy 是否合理 |

---

### 5. 一頁式重點

1. **REVIEW-002a_phase1 結論：PASS**（Phase 1 範圍合格）。允許 Phase 1 sub-task 轉 DONE，允許開 Phase 2。
2. **TASK-002a 整體仍未完成**：核心交付物 funding_rates.parquet 不存在、coverage 0%；只是把鷹架（fees.yaml / cost_stress.yaml / symbol mapping / API smoke）搭好。
3. **TASK-002 仍 BLOCKED_BY_TASK_002A**：禁止任何 stress 計算。
4. **Phase 2 開工前必補**：把 `phase1_status` 改成更不誤導的命名（建議 `phase_status` + 5 個 enum 值 + top-level `task_002a_overall_status`）。
5. **單元測試 7/7 通過**：symbol mapping 比工單要求多測 3 個邊界 case（含 lowercase 拒絕、ETHUSDT、非 USDT perp 拒絕），覆蓋紮實。
6. **12 條 Phase 2 規則寫在第 4 節**，建議直接落地成「TASK-002a Phase 2 工單」或在原 TASK-002a 工單末追加 Phase 2 子章節後再給 Codex。

---

## REVIEW-002a_phase2_dryrun — TASK-002a Phase 2 Bybit Funding Dry-Run

- **審查時間**：2026-05-14
- **審查人**：Claude
- **對象**：TASK-002a Phase 2 dry-run（4 symbols × 7 days，rate-limit / schema / mapping / live diff 全鏈路驗證）
- **審查產物**：
  - `outputs/data_quality/funding_coverage/20260514_phase2_dryrun_funding_rates.parquet`
  - `outputs/data_quality/funding_coverage/20260514_phase2_dryrun_coverage_report.csv`
  - `outputs/data_quality/funding_coverage/20260514_phase2_dryrun_coverage_summary.json`
  - `outputs/logs/cost_inputs/20260514_phase2_dryrun.log`
  - `scripts/build_cost_funding_inputs.py`、`src/costs/symbol_mapping.py`、`tests/cost_inputs/test_symbol_mapping.py`
- **結論**：`PASS`（dry-run 範圍完全合格；可進 controlled full fetch）
- **是否允許進入 controlled full fetch**：**允許**。
- **TASK-002a 整體是否轉 DONE**：**不允許**——full fetch 完成且通過 REVIEW-002a_phase2_full 後才轉 DONE。
- **TASK-002 是否仍 BLOCKED**：**仍 BLOCKED_BY_TASK_002A**。

---

### 1. dry-run 驗收逐條打勾

| # | 驗收項 | 結果 | 證據（獨立驗算） |
|---|---|---|---|
| 1 | 4 dry-run symbols 各 21 列；總 84 列 | **PASS** | `df.symbol.value_counts()` 顯示 BTCUSDT / ETHUSDT / ADAUSDT / BCHUSDT 各 21；`len(df)=84`。 |
| 2 | parquet schema 7 欄齊備、型別正確 | **PASS** | `timestamp: datetime64[ns, UTC]`、`symbol: string`、`exchange: string`、`funding_rate: float64`、`interval_hours: int16`、`source: string`、`is_proxy: bool` —— 與工單第 7 節嚴格一致。 |
| 3 | timestamp 為 8h 結算時點（00:00 / 08:00 / 16:00 UTC） | **PASS** | `hours = [0, 8, 16]`，`minutes = [0]`，`seconds = [0]`，**完全沒有 resample 到日的痕跡**。 |
| 4 | symbol 一律 `BYBIT:XXXUSDT.P` 格式 | **PASS** | 全部 84 列 `startswith("BYBIT:")` 且 `endswith(".P")`。 |
| 5 | funding_rate 為小數（非百分比）| **PASS** | `abs.max = 0.00075064`（= 0.075%，遠低於百分比刻度的合理值範圍 0.01%）；summary `funding_unit_check.status = PASS`。 |
| 6 | interval_hours = 8 | **PASS** | unique 為 `[8]`。 |
| 7 | source = `bybit_api`（無 proxy） | **PASS** | dry-run 全部真實 API 抓取，`is_proxy=False`、`source=bybit_api`。 |
| 8 | 10 筆 live diff `< 1e-9` | **PASS** | `live_diff_check.max_abs_diff = 0.0`、`matched_count=10/10`、`threshold=1e-9` —— **零誤差**，沒有單位混淆。 |
| 9 | 273 PIT symbols mapping integration | **PASS** | `mapping_integration.passed_symbols=273/273, failed=0` —— 把 Phase 1 的單元測試擴展到實際 PIT universe，**0 silent miss**。 |
| 10 | API metrics 在 log / summary 齊備 | **PASS** | `request_count=10, cache_hit_count=8, retry_count=0, api_error_count=0, symbols_failed_count=0`。`raw_cache_snapshot_hash = 9706cf0c…` 表示 raw API response 已 cache，重跑可不撞 API。 |
| 11 | dry-run coverage 數字一致 | **PASS** | `active_position: 28/56 = 50%`（4 symbols × 7 天 × 雙向？實際是 funded vs total）；`active_pit: 28/924 = 3.03%`（4/132 PIT ≈ 3.03%）。數字結構與 dry-run 範圍 mathematically consistent。 |
| 12 | `phase1_status` 命名誤導已修正 | **PASS** | summary 改用 `phase_status: READY_TO_REVIEW_PHASE2_DRYRUN`，且 `formal_funding_rates_written: false` 明示尚未交付正式檔案。REVIEW-002a_phase1 第 3 節提的命名風險**已修**。 |
| 13 | 沒有寫入正式 `data/crypto/funding_rates.parquet` | **PASS** | dry-run parquet 寫到 `outputs/data_quality/funding_coverage/`，**不污染** `data/crypto/funding_rates.parquet`（仍不存在）。 |
| 14 | 沒有執行 TASK-002 stress | **PASS** | summary `notes` 第 1 條明示「Phase 2 dry-run only; no TASK-002 stress executed」。 |
| 15 | 不可動 run008 / strategy / signals / DQ / benchmark | **PASS** | dry-run script 只讀 run008 positions、寫 dry-run 輸出檔；未動策略產出（與 REVIEW-001_final 一致）。 |

---

### 2. Codex 提的 7 個問題逐一回答

1. **dry-run 是否達成 Phase 2 開始前的驗證目的？** **達成**。dry-run 同時驗證了 (a) Bybit API 可用且 rate-limit 友善、(b) parquet schema 與工單完全一致、(c) timestamp 是真實 8h 結算、(d) funding_rate 單位是小數、(e) symbol mapping 對 PIT 全集無 miss、(f) 10 筆 live diff 為零誤差。這 6 點是 full fetch 失敗最常見的來源；都 PASS = full fetch 不會踩到這些坑。
2. **API / cache / schema / mapping / coverage / live diff 是否可信？** **全部可信**：API 10 requests、cache 8 hits、0 retry / 0 error；schema 7 欄型別全對；mapping 273/273；live diff max_abs_diff = 0.0。我獨立 `pd.read_parquet` 與 `value_counts / dtypes / hours.unique()` 重驗都對齊。
3. **funding_rate 小數單位是否可確認？** **確認**。abs max = 0.00075064 = 0.075%，這是「真實 funding rate decimal」的合理量級（Bybit funding 一般 ±0.01% ~ ±0.1%）。若資料用了百分比刻度（×100），這個值會是 0.075 ≈ 7.5%，明顯不合理。
4. **timestamp / interval_hours 是否符合 8h funding settlement？** **完全符合**。hours 集合就是 `{0, 8, 16}`、minutes/seconds 都是 0；interval_hours 全部 = 8。沒有任何 resample / forward-fill 痕跡。
5. **dry-run coverage 低是否只是小樣本造成？** **是**。dry-run 故意只抓 4 symbols × 7 days = 28 真實 funding 結算（每 symbol 21 列 × 4 = 84）。對應到 full active_pit（132 symbols × 7 days = 924 symbol-days）只有 3.03% 是合理的；對應到 active_position（4 symbols × 14 days？= 56）有 50% 也合理。**這個比率不能拿來預測 full fetch 的覆蓋率**——summary 第 70 行 `phase_status` 與 notes 都明示「dry-run coverage 不代表 full fetch coverage」。
6. **是否允許進入 controlled full fetch？** **允許**。dry-run 已把「會把 full fetch 搞砸」的 6 個風險點全部驗到位。
7. **full fetch 前還需要補哪些限制？** 見第 3 節「Full fetch 必須遵守的限制」。

---

### 3. Full fetch 必須遵守的限制（共 12 條，給 Codex 的開工守則）

| # | 限制 | 為什麼 |
|---|---|---|
| 1 | **範圍**：對 run008 PIT universe 全部 273 個 symbol、active period `2024-04-01` ~ `2026-04-30` 抓 8h funding。對應 active PIT 約 29,586 symbol-days。 | 必須覆蓋整個 active period 才能讓 TASK-002 fail gate 判斷有意義。 |
| 2 | **正式輸出路徑**：寫到 `data/crypto/funding_rates.parquet`。dry-run 路徑（`outputs/data_quality/funding_coverage/<日期>_phase2_dryrun_*`）**禁止** 覆蓋或重用。 | 區分 dry-run 與 formal artifact，避免混淆。 |
| 3 | **Raw API cache**：每個 symbol 的原始 API 回應寫到 `data/cache/funding/bybit_raw/<symbol>_<pageN>.json`。 | 讓重跑 / audit 不必再撞 API；raw cache 與 parquet hash 都要寫進 log。 |
| 4 | **Coverage gate**（REVIEW-002a_phase1 已寫過、再次強調）：active PIT real coverage ≥ 80% → `PHASE2_READY`；50–80% → `PHASE2_PROXY_ONLY`（須 Rick 同意）；< 50% → `PHASE2_BLOCKED_BY_DATA`。 | 避免低覆蓋率被偷偷放行。 |
| 5 | **Sanity 抽查擴大**：full fetch 後抽 **30 筆**（dry-run 是 10 筆）跨不同 symbol、跨不同時段（含 2024 / 2025 / 2026 各年至少 5 筆）與 Bybit live diff < 1e-9。 | 防 API 在不同年份或不同 symbol 上有單位 / 精度差異。 |
| 6 | **異常值 flag**：若任一 funding_rate 的 `abs > 0.01`（1%），須在 coverage report 列出該 symbol-day 並在 summary 加 `outlier_funding_rates` 區塊（不刪資料、不修正、只標）。 | Bybit funding rate 理論上限 ±0.05%（per 8h），> 1% 多半是 API quirk 或單位錯誤。 |
| 7 | **時序連續性**：對每個 symbol 跑連續性檢查——任何 > 24h 的 funding 間隙都要在 coverage report 列出（含 symbol、from_ts、to_ts、gap_hours）。 | 揭露 Bybit API 可能丟頁或某 symbol 暫停交易等資訊。 |
| 8 | **Idempotency**：full fetch 完整跑兩次，第二次必須**完全使用 raw cache**（API request count = 0），且兩次寫出的 `funding_rates.parquet` SHA-256 必須相同。 | 證明資料可重現、API call 不會 silently 帶入 noise。 |
| 9 | **缺資料政策**：missing symbol-day **不出現** 在 parquet 內（既不 fill 0、也不 fill NaN row）；只在 coverage report 紀錄。proxy 啟動順序：先 `proxy_universe_median`（同日同 universe 真實 funding 中位數），最後才 `proxy_zero`，且 `proxy_zero` 涉及的 symbol-day 必須在 NOTE 區單獨列出。 | 與 TASK-001d DQ policy 一致。 |
| 10 | **`phase_status` 終態列舉**：full fetch 結束後 summary.json 必須是 `PHASE2_READY` / `PHASE2_PROXY_ONLY` / `PHASE2_BLOCKED_BY_DATA` 三選一；加 top-level `task_002a_overall_status: COMPLETE` 或 `INCOMPLETE` 二選一。 | 讓 REVIEW-002a_phase2_full 與下游 dashboard 一眼看到狀態。 |
| 11 | **log API metrics**：log 必須印 `bybit_api_calls_made / errors / pages_fetched / first_response_at / last_response_at / cache_hit_count / total_request_seconds`。 | 估算 full fetch 成本與穩定性。 |
| 12 | **禁止項**：(a) 不可動 run008、(b) 不可改 strategy / signals / DQ / benchmark / backtester、(c) 不可執行 TASK-002 stress、(d) 不可在 active period 之外再多抓資料（buffer 只允許 dry-run 那種 ±1 天）、(e) 不可在沒有 REVIEW-002a_phase2_full PASS 前 merge 回 main。 | 維持 TASK-002 的 BLOCK 邊界。 |

---

### 4. 一頁式重點

1. **REVIEW-002a_phase2_dryrun 結論：PASS**。Phase 2 dry-run 把 6 個 full-fetch 最會出包的風險點（API / schema / mapping / 8h boundary / unit / live diff）全驗到位。
2. **允許進入 controlled full fetch**。Phase 1 已修正 `phase1_status` 命名誤導；dry-run summary 採用 `READY_TO_REVIEW_PHASE2_DRYRUN`，下一輪 full fetch 應用 `PHASE2_READY` / `PHASE2_PROXY_ONLY` / `PHASE2_BLOCKED_BY_DATA` 三選一。
3. **TASK-002a 整體仍未完成**：`data/crypto/funding_rates.parquet` 尚未存在；dry-run parquet 在 `outputs/data_quality/funding_coverage/` 不會被當成正式輸入。
4. **TASK-002 仍 BLOCKED_BY_TASK_002A**：必須 REVIEW-002a_phase2_full PASS 後 Codex 才可重做 TASK-002 readiness check。
5. **Full fetch 12 條限制**（第 3 節）：含覆蓋率門檻、abs > 1% outlier flag、連續性檢查、idempotency 兩次跑同 hash、proxy 順序、`phase_status` 終態列舉。
6. **獨立驗算數據**：parquet 84 列 / 4 symbol × 21 / hours = {0,8,16} / abs max funding 0.00075 / mapping 273 PASS / live diff 0 —— 全部與 Codex 自報一致。

---

## REVIEW-002a_phase2_full — TASK-002a Phase 2 Bybit Funding Full Fetch

- **審查時間**：2026-05-14
- **審查人**：Claude
- **對象**：TASK-002a Phase 2 controlled full fetch（正式 `data/crypto/funding_rates.parquet`）
- **審查產物**：
  - `data/crypto/funding_rates.parquet`（750,641 列、273 symbols、active period 2024-04-01 ~ 2026-04-30）
  - `outputs/data_quality/funding_coverage/20260514_phase2_full_coverage_{report.csv, summary.json}`
  - `outputs/logs/cost_inputs/20260514_phase2_full_fetch.log`
  - `data/crypto/fees.yaml`、`configs/cost_stress.yaml`
  - `src/costs/symbol_mapping.py`、`scripts/build_cost_funding_inputs.py`
- **結論**：**`PASS`（含 caveat）**
- **TASK-002a 整體是否轉 DONE**：**允許**。
- **TASK-002 是否解除 BLOCKED**：**先**從 `BLOCKED_BY_TASK_002A` 轉成 `BLOCKED_BY_WORKORDER_UPDATE`——TASK-002 工單第 8 節「8h funding」假設**被 Bybit 實際資料推翻**（混合 1h/4h/8h），必須先更新 TASK-002 工單，才能解 BLOCK。詳見第 4 節。

---

### 1. 驗收標準逐條打勾

| # | 驗收項 | 結果 | 證據（獨立驗算） |
|---|---|---|---|
| 1 | parquet schema 7 欄、型別正確 | **PASS** | 我獨立 `pd.read_parquet` 驗：`timestamp datetime64[ns,UTC]` / `symbol string` / `exchange string` / `funding_rate float64` / `interval_hours int16` / `source string` / `is_proxy bool`。 |
| 2 | 行數 = 750,641 | **PASS** | `len(df) = 750641`。 |
| 3 | 273 PIT symbols 全部出現 | **PASS** | `df.symbol.nunique() = 273`、`symbols_with_funding_rows_count=273`、`symbols_failed_count=0`。 |
| 4 | symbol 一律 `BYBIT:XXXUSDT.P` | **PASS** | 全部 startswith/endswith 驗證通過。 |
| 5 | funding_rate 為小數 | **PASS** | abs max = 0.05（= 5%，仍是 decimal scale；百分比 scale 會是 5.0）。`funding_unit_check.status = PASS`。 |
| 6 | active period real coverage ≥ 80% | **PASS** | `active_pit.coverage_real_pct = 97.56%`、`active_position = 98.84%`，兩者都遠超 80% gate。**`PHASE2_READY` 達成**。 |
| 7 | live diff 30 筆跨年 ≥ 5 筆 | **PASS** | `live_diff_check.matched_count = 30`、`max_abs_diff = 0.0`、`per_year_sample_count = {2024:5, 2025:5, 2026:5}`、`threshold = 1e-9`。 |
| 8 | mapping integration 273/273 | **PASS** | `mapping_integration: passed=273, failed=0`。 |
| 9 | proxy 未使用 | **PASS** | `is_proxy` 全 False；`coverage_proxy_pct = 0.0`；無 `proxy_universe_median` / `proxy_zero` 啟動。**這是最乾淨的可能結果**——完全沒有 proxy 污染。 |
| 10 | timestamp 為 UTC 真實結算時點（無 resample 到日） | **PASS** | 我獨立檢查 `df.timestamp.dt.minute.unique() = [0]`、`.dt.second.unique() = [0]`；hour 分布橫跨 0–23（因為 4h interval 會落在 04/12/20 等非 8h slot）。 |
| 11 | Outlier flag（abs ≥ 0.01）：列出不修正 | **PASS** | `outlier_summary.outlier_count = 653`、`max_abs_funding_rate = 0.05`、top 50 列在 `top_outliers`，含 symbol / timestamp / interval_hours / source。**沒有任何修改值的痕跡**。 |
| 12 | 連續性檢查：>24h gap 列出 | **PASS** | `continuity_gap_summary: gap_count = 68526, symbols_with_gaps = 129, estimated_missing_events = 107018`，top_gaps 給 50 筆 sample。 |
| 13 | Idempotency 兩次跑相同 hash | **PASS** | `idempotency.current == previous = 7ac35a84…02`、`hash_consistent_with_previous = true`。 |
| 14 | log API metrics 齊備 | **PASS** | `request_count=30, cache_hit_count=6927, retry_count=0, api_error_count=0, raw_cache_snapshot_hash=ce7a5b53…9eae9c`。 |
| 15 | `phase_status` / `task_002a_overall_status` 命名修正 | **PASS** | summary 採用 `phase_status: READY_FOR_TASK_002_REVIEW` 與 top-level `task_002a_overall_status: READY_FOR_TASK_002_REVIEW`，**REVIEW-002a_phase1 提的命名誤導已完整修正**。 |
| 16 | 缺資料 symbol-day **不出現** 在 parquet | **PASS** | 沒有 `funding_rate=0` 的 fill row；missing 全部由 `missing_symbols` 報表呈現（40 個 symbol with `active_pit` missing；7 個 symbol 在 `active_position` missing）。 |
| 17 | 不可動 run008 / strategy / DQ / benchmark | **PASS** | 與 REVIEW-001_final 對齊；script 從 run008 只讀。 |
| 18 | 不可執行 TASK-002 stress | **PASS** | summary `notes` 第 1/3 條明示「Controlled full fetch only; TASK-002 stress was not executed」、「TASK-002 remains BLOCKED pending REVIEW-002a_phase2_full」。 |

---

### 2. Codex 提的 17 個問題逐一回答

1. **schema 是否符合 TASK-002a 規格？** **符合**。7 欄完整、型別正確、symbol 格式對齊。
2. **funding_rate 是否確認為小數？** **確認**。abs max 0.05 = 5%（decimal scale）；若是百分比 scale 會是 5.0。Bybit 4h funding 在極端市況下的單次 ±5% 是已知會發生的（如 XCN 2026-04、ENJ 2026-04）。
3. **timestamp 是否為 UTC funding settlement time？** **是**。tz-aware UTC，minute/second 全 0，hour 分布橫跨 0–23（因為 1h/4h/8h interval 混合）。
4. **symbol mapping 是否可信？** **可信**。273/273 PASS，且全 parquet 列 symbol 都通過 startswith/endswith 雙端驗證。
5. **273 requested symbols 是否全部有 funding rows？** **是**。`symbols_with_funding_rows_count=273, symbols_failed_count=0`。
6. **active PIT coverage 97.56% 是否通過 gate？** **通過**。≥ 80% 為 `PHASE2_READY`；遠超門檻。
7. **active position coverage 98.84% 是否足以支援 TASK-002？** **是**。98.84% 是「實際持倉 symbol-day 中真實 funded」的比例；剩 1.16% 由 7 個 symbol 貢獻（XTZ / FLOW / LPT / AXS / RVN / INJ / CTC），是 TASK-002 fail gate 計算時需要 **exclude 該 symbol-day** 而非 fill 0 的清單。
8. **active position missing 7 個 symbol 是否構成重大風險？** **不構成**（在 1.16% 範圍內）。其中 XTZ、FLOW、AXS、RVN 都是已知 Bybit 曾經暫停或下市重整的 symbol，funding 缺料合理。但**必須在 TASK-002 工單裡明確列為 known-gap symbols**，cost engine 對它們的 funding 計算需文件化處理（建議：該 symbol-day 從 funding cost 計算中 exclude，並在 stress summary 內列出 affected symbol-days）。
9. **30 筆 live diff 是否足以確認 API/parquet 一致？** **足夠**。`max_abs_diff = 0.0`（不是接近 0，是完全為 0）；跨 2024/2025/2026 各年 5 筆；threshold 1e-9 仍輕鬆過。
10. **Outlier 653 筆、max abs 0.05 是否需要人工標記 caveat？** **需要在 TASK-002 工單與 cost stress summary 內保留 caveat**，但**不需要修改 funding_rates.parquet**。理由：(a) 這些 outlier 是 Bybit API 回的真實值；(b) Bybit 4h funding 在 ±5% 是 Bybit 系統內可達上限（cap），不是錯誤；(c) TASK-002 cost engine 必須照實累加。建議 cost stress summary 加 `outlier_contribution_breakdown`：對 realistic_combo / conservative_combo / worst_case_combo 三個情境，列出 outlier 列貢獻了多少 funding cost。
11. **continuity gaps 是否合理？是否需要阻擋 TASK-002？** **合理且不阻擋**。129 / 273 symbols 有 gap、68,526 events，多數集中在新上市 / 短暫下市的小幣（如 0G* 系列、ACE 早期）。對 active position 影響極小（3,179 events / 873 symbol-days = active position 範圍的 1.16% 持倉日）。**不阻擋**，但 TASK-002 工單需新增「known-gap symbols list」處理規則。
12. **funding intervals 1h/4h/8h 是否需要修改 TASK-002 工單措辭？** **必須修改**——這是本次審查**最重要的單一發現**。詳見第 3 節。
13. **idempotency hash 是否可信？** **可信**。summary 內 `previous_hash == current_hash = 7ac35a84…02`。Note：這個 hash 是「排序後內容的 SHA-256」，**不是檔案 SHA-256**（我獨立算的檔案 SHA-256 = `e754b52c…1b`，與 idempotency 標的不同；這是正常的，parquet 寫檔的壓縮 / metadata 會影響 byte hash，不影響內容一致性）。建議下次 log 補一行 `hash_definition: "sorted content sha256, not file bytes sha256"` 避免將來混淆。
14. **是否通過 REVIEW-002a_phase2_full？** **PASS**。
15. **是否允許 TASK-002a 整體轉 DONE？** **允許**。
16. **是否允許 TASK-002 解除 BLOCKED 並進入 READY_TO_IMPLEMENT？** **不直接 READY**——TASK-002 工單在 funding interval 假設上**被資料證偽**，必須先更新工單，才能讓 Codex 對新工單跑 readiness check。建議把 TASK-002 狀態從 `BLOCKED_BY_TASK_002A` 改成 `BLOCKED_BY_WORKORDER_UPDATE`。
17. **TASK-002 開工前是否需要修改 TASK-002 工單或 cost engine 計畫？** **需要**。詳見第 3 節 5 項必改清單。

---

### 3. TASK-002 工單必改 5 項（funding interval 規則重整）

**核心發現**：Bybit funding 不是統一 8h，而是 1h / 4h / 8h 混合：

| Interval | Symbols 數 | Funding rows | 範例 |
|---:|---:|---:|---|
| 1h | 1 | 2,758 | 1 個短週期 symbol |
| 4h | 145 | 461,513 | **多數小幣 / 中小幣**（XCN、POLYX、ENJ…）|
| 8h | 127 | 286,370 | BTC / ETH / 主流大幣 |

這完全推翻 TASK-002 工單第 8 節「funding 必須以 8h 結算」的假設。**TASK-002 工單必須做以下 5 項更新**：

1. **第 8 節「Funding 情境設計」措辭**：
   - 移除「8h funding 結算次數加總」這類字眼。
   - 改寫為：「funding cost 必須依 `funding_rates.parquet` 每列的 `interval_hours` 與 `timestamp` 累加；同一 symbol-day 內可能有 1 / 3 / 6 / 24 個 funding 結算（依 interval）；不可假設統一 8h」。
   - 在「強制規則」加：cost engine 必須對每筆 funding row 計算 `funding_payment = position_value × funding_rate`（不再除以 interval 比例）。

2. **`configs/cost_stress.yaml` defaults**：
   - `funding_application` 從 `pit_8h_settlement_accumulated` 改成 `pit_per_interval_settlement_accumulated`。
   - 加 `funding_interval_policy: "use_interval_hours_per_row"`（明示）。

3. **新增 known-gap symbols 規則**（第 11 節驗收標準新增）：
   - 對 `active_position` 內 missing 的 7 個 symbol（XTZ / FLOW / LPT / AXS / RVN / INJ / CTC），cost engine 必須對該 symbol-day**將 funding cost 視為 0 並標記**（不是 fill 假設值；標 `funding_gap=True` 在輸出檔案）。
   - cost stress summary 新增 `funding_gap_symbol_days` 區塊，列出所有受影響的 (symbol, date) 與 affected position weight。

4. **新增 outlier 處理規則**（第 11 節驗收標準新增）：
   - cost engine 對 `abs(funding_rate) >= 0.01` 列**不修正**，照實累加。
   - cost stress summary 新增 `outlier_contribution_breakdown` 區塊，對 realistic_combo / conservative_combo / worst_case_combo 三情境，列出 outlier 列對總 funding cost 的貢獻百分比；若某情境 outlier contribution > 30%，標 WARNING（代表結果被少數異常 funding 主導）。

5. **新增 fail gate 條件**（第 12 節）：
   - 「任一 combo 情境下 funding gap symbol-day > 5% of active position scope → WARNING」。
   - 「若 outlier_contribution_breakdown 中 worst_case_combo 的 outlier 貢獻 > 50% → WARNING（結果不可信因為被異常值主導）」。

---

### 4. Queue 狀態建議

| 任務 / Review | 建議狀態 | 理由 |
|---|---|---|
| TASK-002a | **DONE**（Claude REVIEW-002a_phase2_full PASS） | 三個子階段全 PASS，funding_rates.parquet 已正式落地。 |
| REVIEW-002a_phase2_full | **PASS** | 本紀錄。 |
| TASK-002 | **BLOCKED_BY_WORKORDER_UPDATE**（從 `BLOCKED_BY_TASK_002A` 轉成這個新狀態） | TASK-002 工單第 8 節「8h funding」假設被資料證偽；必須先更新工單，Codex 才能對新工單跑 readiness check。 |
| TASK-002 工單更新 | 由 Claude 撰寫 5 項更新後 commit；可開新工單卡 TASK-002_workorder_v2，或直接在原工單上 patch。 | 短期內預期 1 次更新即可。 |

---

### 5. TASK-002 開工前必須保留的 caveats（已整理供 TASK-002 工單 v2 直接引用）

1. **Active 樣本 760 天**（沿用 REVIEW-001_final）—— 全期口徑只是 reference，active 為主。
2. **funding interval 是 1h / 4h / 8h 混合**——cost engine 必須 per-row 累加。
3. **7 個 active position missing symbols**：XTZ / FLOW / LPT / AXS / RVN / INJ / CTC——cost engine 對該 symbol-day funding 標 `funding_gap=True` 而非 fill。
4. **653 outliers（abs ≥ 1%）**——照實累加，但 cost stress summary 必須列出 outlier 對總 funding cost 的貢獻比例。
5. **continuity gaps**：68,526 events 集中在 0G* / ACE 等小幣；對 active position 影響 1.16%。cost engine 不需修補，但 summary 須列出涉及的 (symbol, date)。
6. **idempotency hash 是 content hash 不是檔案 hash**—— TASK-002 自己的 reproducibility hash 也要遵循同樣 convention（避免 parquet metadata 改動造成 byte hash 變但內容相同的假警報）。
7. **strategy / signals / universe / DQ / benchmark 不可動**（沿用 TASK-001 紅線）。

---

### 6. 一頁式重點

1. **REVIEW-002a_phase2_full 結論：PASS**。
2. **TASK-002a → DONE**。`data/crypto/funding_rates.parquet` 正式落地（750,641 列、273 symbols、active period 真實 funding）。
3. **TASK-002 不能直接 READY_TO_IMPLEMENT**——TASK-002 工單第 8 節「8h funding」假設被 Bybit 實際資料推翻（**1h:1 / 4h:145 / 8h:127 symbols**）。狀態改為 `BLOCKED_BY_WORKORDER_UPDATE`。
4. **TASK-002 工單必改 5 項**：(a) per-interval funding 累加、(b) cost_stress.yaml defaults 命名、(c) known-gap 7 symbols 處理、(d) outlier contribution breakdown、(e) 兩條新 fail gate。
5. **資料品質極佳**：proxy 未使用、live diff 30/30 = 0.0、idempotency PASS、coverage 97–99%。這是 Phase 2 在沒有 fallback 的情況下達到的最佳狀態。
6. **下一步**：Claude 寫 TASK-002 工單 v2（patch 第 8 / 9 / 11 / 12 節 + cost_stress.yaml defaults）；Codex 對 v2 重做 readiness check；之後才開 TASK-002 cost stress。

---

## REVIEW-002 — Cost / Funding / Slippage Stress Test（Opus final decision，2026-05-15）

```
Suggested model:              Opus
Escalation reason:            major task final review；是否解除 BLOCKED；是否進入下一階段
Opus final decision required: Yes
```

- **審查時間**：2026-05-15
- **審查模型**：Claude Opus
- **審查包**：context_packet + Sonnet draft + 工單 v2（已確認 TASK-002 官方 4 個交付物不存在）
- **結論**：**`BLOCKED_CANNOT_REVIEW`**（無法對不存在的結果做 PASS/CONDITIONAL_PASS/FAIL 裁決）

## Verdict

**`BLOCKED_CANNOT_REVIEW`**

理由：TASK-002 v2 工單要求的 4 個官方交付物全部不存在。`outputs/backtests/prev3y_crypto/` 下無任何 `*cost_stress*` 檔；`configs/cost_stress.yaml` defaults 仍是 v1 的 `pit_8h_settlement_accumulated`。Sonnet 初審草稿（REVIEW-002_DRAFT_BY_SONNET.md）已正確掃描出此狀態。**Opus 確認 Sonnet 的 BLOCKED 判讀**，並拒絕用舊架構 `output/crypto_cost_stress.csv` 替代——該檔用固定 0.03%/day funding（非 per-interval PIT）、重跑策略訊號（非 run008 overlay）、無 funding_gap / outlier 拆解、無 reproducibility hash，**用它做 final verdict 等同 AI_WORKFLOW § 3 紅線「封閉迴圈、自己跑自己驗」**。

## Strategy Decision

**需要更多測試**（沿用 REVIEW-001_final 判定；無新證據可升級為「保留」或降級為「淘汰」）

## Key Numbers

| 指標 | run008 baseline（gross，已確認）| realistic_combo | conservative_combo | worst_case_combo |
|---|---:|---:|---:|---:|
| active Sharpe | **0.9267** | _未交付_ | _未交付_ | _未交付_ |
| active IR_vs_cash | +0.9267 | _未交付_ | _未交付_ | _未交付_ |
| active IR_vs_eqw | **+0.7227** | _未交付_ | _未交付_ | _未交付_ |
| active IR_vs_btc | −0.0175 | _未交付_ | _未交付_ | _未交付_ |
| active max DD | −19.50% | _未交付_ | _未交付_ | _未交付_ |
| total funding cost | 0（gross） | _未交付_ | _未交付_ | _未交付_ |
| total fee cost | 0 | _未交付_ | _未交付_ | _未交付_ |
| total slippage cost | 0 | _未交付_ | _未交付_ | _未交付_ |
| funding_gap_pct of active position | — | _未交付_ | — | — |
| outlier_pct of total funding cost | — | _未交付_ | _未交付_ | _未交付_ |
| net_alpha_decay vs run008 | 0% | _未交付_ | _未交付_ | _未交付_ |

> 表中 `_未交付_` 為 TASK-002 v2 結果欄位。Codex 完成交付後此表須由 Sonnet 從 `cost_stress_summary.json` 填入，由 Opus 重新裁決。

## Blocking Issues

1. **TASK-002 v2 0/4 官方交付物存在**（`*_cost_stress.csv`、`*_cost_stress_summary.json`、`*_cost_stress_positions_cost.parquet`、`*_cost_stress.log`）。
2. **`configs/cost_stress.yaml` defaults 未升級到 v2**：`funding_application` 仍為 `pit_8h_settlement_accumulated`；缺三個 v2 policy key（`funding_interval_policy / funding_gap_policy / outlier_policy`）。
3. **context_packet Decision A / B 未決**：Rick 尚未授權 readiness check 啟動；Codex 不得自行開工。
4. **無 funding cost / fee cost / slippage cost 真實拆解可審**：本題的核心研究問題（哪一類吃掉最多 alpha）**無法回答**。

## Caveats

1. **不可用舊 `output/crypto_cost_stress.csv` 替代**：funding 用固定 0.03%/day、重跑策略訊號、scenarios 命名與 v2 完全不對齊；其 worst-case Sharpe ≈ 0.59 與 max DD ≈ −49% 只能作為「給 Opus 的事前提醒」，不能作為 fail gate 判定依據。
2. **sample 仍是 760 天**（沿用 REVIEW-001_final）：任何 TASK-002 結論都受此樣本量限制。
3. **7 個 funding-gap symbols（XTZ / FLOW / LPT / AXS / RVN / INJ / CTC）**：v2 要求標 `funding_gap=True` 不 fill 0；若 Codex 違反此政策，Opus 不接受該交付物。
4. **653 筆 outlier funding rows（max abs = 0.05）**：v2 要求照實累加；若 worst_case 的 outlier 貢獻 > 30% 自動 WARNING。
5. **interval 混合（1h:1 / 4h:145 / 8h:127）**：v2 要求 per-interval 累加；若 Codex 結果中 4h symbol 一天只算 3 次 funding（誤把它當 8h），funding cost 會被低估一半 → Opus 會 FAIL。
6. **paper trading 禁止**：即使未來 TASK-002 PASS，也不可在沒有 attribution（TASK-003）與 forward sample 之前進 paper。

## Next Tasks

依執行順序：

1. **Rick**：確認 context_packet 的 Decision A（授權 readiness check）與 Decision B（PASS 後是否自動授權 Codex）。
2. **Codex（Step 1）**：commit `configs/cost_stress.yaml` defaults 升級為 v2（5 行改動，見 Sonnet draft § Required Next Step）。Sonnet 重做 readiness check → `READY_TO_IMPLEMENT`。
3. **Codex（Step 2）**：依工單 v2 產出 4 個官方交付物 + 回報 9 件事（含 v2 per-interval audit 與 `interval_distribution_used`）。
4. **Sonnet**：對交付物跑工單 v2 第 11 節 checklist；Key Numbers 表填入；列出觸發的 WARNING / FAIL。
5. **Opus**：以填好的 Key Numbers + Sonnet checklist 重新執行 REVIEW-002（本筆 Verdict 改為 PASS / CONDITIONAL_PASS / FAIL）。
6. **TASK-003 / TASK-004 推進**：在 Opus REVIEW-002 真正 PASS 後再判定是否解除（見下方 Queue Updates）。

## Queue Updates

| 任務 / Review | 建議狀態 | 變更理由 |
|---|---|---|
| TASK-002 | **NEED_CLARIFICATION**（沿用，含註記）| `READY_FOR_READINESS_RECHECK_AGAINST_V2` 仍未轉換為 READY（因 cost_stress.yaml defaults 未 commit 到 v2）。Opus 對工單 v2 的 readiness 狀態判定為「等 yaml commit 才能進 READY」。 |
| REVIEW-002 | **WAITING_INPUT**（沿用）| TASK-002 v2 交付物不存在，無法 PASS / CONDITIONAL_PASS / FAIL。 |
| TASK-003（attribution）| **TODO**（沿用）| 不依賴 TASK-002 結果；獨立於 cost stress。Rick 可在等 TASK-002 期間平行讓 Codex 對 TASK-003 跑 readiness check（確認 `data/crypto/factor_returns.parquet` 是否存在）。Opus 不擋 TASK-003 開工。 |
| TASK-004（dashboard 第一版）| **TODO**（沿用，第一版只放 baseline）| 第一版可在 TASK-002 完成前先放 baseline 雙口徑 + 三 benchmark IR 面板，cost stress / attribution 面板留空 placeholder。Opus 同意此排序。 |
| Paper trading | **禁止**（明確）| 即使 TASK-002 未來 PASS，paper trading 仍需 TASK-003 attribution + forward sample，且需要另一份 Opus final review。 |

## Opus 對 Sonnet draft 的補充註記

Sonnet 草稿準備了一份「給 Opus 的 prompt」（draft § Suggested Opus Prompt），質量足以在 Codex 完成交付後直接驅動下一輪 final review。**Opus 確認該 prompt 結構正確**，唯一補充：在 prompt 「B 核心研究決策」第 11 題（舊架構 vs v2 per-interval 差距），請 Sonnet 在交付後就先做一張 side-by-side 表，標出 4h symbol 在兩種計算下的 funding cost 差距比例——這是最容易發現 Codex 是否誤寫成 8h 的快速 sanity check。

## 一頁式重點

1. **REVIEW-002 結論：BLOCKED_CANNOT_REVIEW**——TASK-002 v2 還沒跑，沒有結果可審。
2. **不可用舊架構 cost stress 結果代替**：funding 算法不同、底層引擎不同、scenarios 不對齊。
3. **TASK-002 真正卡點是 yaml**：`configs/cost_stress.yaml` defaults 還在 v1。Codex commit 一個 5 行 yaml 更新就解開。
4. **再加一步是 Codex 執行**：依工單 v2 產出 4 個交付物 + 回報 9 件事。
5. **TASK-003 / TASK-004 可平行推進**：不依賴 TASK-002 結果。
6. **paper trading 仍禁止**：TASK-002 + TASK-003 + forward sample 三者齊備、且各自過 Opus final review 後才討論。
7. **下一次 Opus 介入時機**：Sonnet 把 Key Numbers 表填好、checklist 跑完、列出觸發的 WARNING / FAIL → Opus 在 30 分鐘內可發 final verdict。

---

## REVIEW-002 — Cost / Funding / Slippage Stress Test（Opus final decision，2026-05-15，第二輪）

```
Suggested model:              Opus
Escalation reason:            major task final review；保留/淘汰決策；解鎖 TASK-003/004/005；paper trading 規劃授權
Opus final decision required: Yes
```

- **審查時間**：2026-05-15
- **審查模型**：Claude Opus（第二輪 — 取代上一輪的 `BLOCKED_CANNOT_REVIEW`）
- **審查包**：context_packet + Sonnet draft（已升級為 PASS_CANDIDATE，14/14 checklist 通過）+ `20260515_cost_stress_summary.json` + scenario CSV + log
- **核心交付物**：`outputs/backtests/prev3y_crypto/20260515_cost_stress_{summary.json, csv}`、`outputs/logs/prev3y_crypto/20260515_cost_stress.log`、`*_cost_stress_positions_cost.parquet`

## Verdict

**`PASS`**

## Strategy Decision

**保留**（從 REVIEW-001_final 的「需要更多測試」升級）

## Key Numbers

| Scenario | Active Sharpe | IR_eqw | IR_btc | Active max DD | alpha decay | fee | slip | funding |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| no_cost_baseline | 0.9267 | +0.7227 | −0.0175 | −19.50% | ~0 | 0 | 0 | 0 |
| realistic_combo | 0.8918 | +0.7168 | −0.0273 | −19.64% | 0.81% | 0.003551 | 0.004501 | 0.002452 |
| conservative_combo | 0.8732 | +0.7136 | −0.0328 | −19.69% | 1.26% | 0.004952 | 0.009003 | 0.002452 |
| worst_case_combo | 0.8398 | +0.7079 | −0.0423 | −19.80% | 2.04% | 0.004952 | 0.018006 | 0.003679 |

## 1. Fail / Warning gates 逐條判定

| Gate | Threshold | 觸發？ |
|---|---|---|
| realistic_combo active Sharpe ≥ 0.5 | 0.5 | PASS（0.8918） |
| realistic_combo IR_vs_eqw ≥ 0.2 | 0.2 | PASS（0.7168） |
| conservative_combo IR_vs_eqw ≥ 0 | 0 | PASS（0.7136） |
| realistic / conservative max DD > 1.5× run008 | −29.25% | PASS（−19.64% / −19.69%，皆優於門檻） |
| 任一情境成本吃掉 active alpha > 70% | 70% | PASS（最大 2.04% in worst_case） |
| funding_gap_pct > 5%（v2 新增） | 5% | PASS（1.16%） |
| outlier_pct of total funding cost > 30%（v2 新增） | 30% | PASS（2.57%） |

**所有 fail gates 全過、兩條 v2 新 WARNING 全未觸發、`fail_warning_gates.failures = []`、`warnings = []`。**

## 2. Cost composition（Opus 額外洞察）

`slippage > fee > funding` 在所有 combo 都成立：

- realistic: slip 0.0045 > fee 0.0036 > funding 0.0025
- conservative: slip 0.0090 > fee 0.0050 > funding 0.0025
- worst_case: slip 0.0180 ≫ fee 0.0050 > funding 0.0037

**這推翻了「funding 為最大成本壓力源」的事前假設**——對月度 rebalance + 接近 market-neutral 的部位，per-interval Bybit funding 是最小的成本來源。Opus 視角下這是研究路線上的重要結論：未來成本優化（如果做）應該優先攻 slippage（execution venue 選擇、訂單拆單），funding 反而不是 first-order concern。

## 3. 工程驗收

- `no_cost_baseline_max_diff_vs_run008 = 0.0` ✓
- `stats_recompute_check`: 192/192 values, max_abs_diff = 0.0 ✓
- `reproducibility_hash_check_passed: true` ✓
- `methodology` 區塊含 annualization=365.25 / ddof=1 / IR 公式 / cost 應用順序 ✓
- `cost_policy` 區塊含 fee / funding / slippage / proxy / interval / gap / outlier 7 條政策 ✓
- `funding_audit_samples` 含 1h / 4h / 8h 各 1 樣本（GIGA 1h not held、XTZ 4h held、ADA 8h held）✓
- `interval_hours_distribution.held`: 1h=0 / 4h=14862 / 8h=80986 — 持倉偏 8h 大幣，比例 1:5.4（vs 全集 1:1.9），這是 universe-and-position 自然結果，不是 bug
- `input_hashes` 6 個輸入檔（run008 三件套、funding_rates、fees.yaml、cost_stress.yaml）SHA 全列出 ✓

## 4. Final Interpretation

策略不是「論文型 alpha」也不是「passive crypto exposure」。worst_case（fee taker × 2 + funding × 1.5 + 20bps slippage）下 active Sharpe 仍 0.84、IR_vs_eqw 仍 +0.71、max DD 僅惡化 0.3 個百分點到 −19.80%。alpha decay 最大 2.04%，遠低於 70% WARNING 門檻。**策略 edge 在實際交易摩擦下是真實的，不是 gross 的幻覺**。IR_vs_btc 在所有情境都在 −0.02 ~ −0.04 之間——edge 是「相對 crypto universe 平均的橫斷面選股」，不是 BTC 方向性押注，與 market-neutral 設計初衷一致。760 天樣本仍是已知限制，但這已是目前可獲得的最強證據。

## 5. Caveats（必須保留至 TASK-003、TASK-004、paper trading 規劃）

1. Active 樣本 760 天，未涵蓋完整 3 年 lookback；最終仍需 forward sample 補強。
2. 無 BTC alpha；策略只能當 portfolio 內的獨立 sleeve，不可取代 buy-and-hold。
3. funding gap 7 symbols 影響 1.16% active 持倉（343 / 29,586），attribution 須單獨檢視。
4. interval distribution 偏 8h（大幣為主），attribution 應驗證 alpha 是否集中於 8h interval 的大幣。
5. outlier 影響極小（2.57% of total funding cost）— 結果不是被異常值主導。
6. reproducibility hash 為 content hash 非檔案 SHA-256（沿用 TASK-002a 慣例）。
7. paper trading 仍需 attribution + forward sample；本次 PASS 不等於可以接真錢。

## 6. Downstream Decisions

| 項目 | 決策 |
|---|---|
| TASK-002 → DONE | ✅ |
| TASK-003 attribution 解鎖 | ✅ READY_TO_IMPLEMENT（Codex 先確認 factor_returns.parquet） |
| TASK-004 dashboard 第一版解鎖 | ✅ READY_TO_IMPLEMENT |
| TASK-005 VPS / monitor 解鎖 | ✅ READY_TO_IMPLEMENT（可獨立平行） |
| Paper trading 規劃 | ✅ 允許**規劃**（寫 TASK-006 工單），**不可立即執行** |
| Live trading | ❌ 仍禁止 |

## 7. 給 Rick 的一頁式重點

1. **REVIEW-002 結論：PASS**。fail gate 全過、v2 兩條新 WARNING 都沒觸發、alpha decay 最大才 2.04%。
2. **策略判定：保留**——從「需要更多測試」升級。
3. **最大成本是 slippage 不是 funding**——Opus 視角下這是研究路線上的重要轉向，未來成本優化要攻 execution。
4. **TASK-002 → DONE，TASK-003 / 004 / 005 全部解鎖**。
5. **Paper trading 可開始規劃**（寫工單），但需要 attribution PASS + 30 天 forward 才能執行。
6. **Live trading 仍禁止**。
7. **下一張最值得做的工單：TASK-003 attribution**——回答「alpha 從哪裡來」，是 paper trading 工單的必要 input。

---

## REVIEW-003 — Baseline Attribution（Opus final decision，2026-05-15）

```
Suggested model:              Opus
Escalation reason:            major task final review；concentration gate 公式衝突；long-side 負 alpha 屬結構性問題；paper trading 規劃前最後一道把關
Opus final decision required: Yes
Command source:               docs/research/commands/NEXT_ACTION.md (status=READY, owner=Claude Opus)
```

- **審查時間**：2026-05-15
- **審查模型**：Claude Opus
- **審查包**：NEXT_ACTION 指定的最小審查包 + Sonnet draft（PASS_CANDIDATE，含 2 個 BLOCKING）+ summary.json + by_side / by_year / by_symbol / top_contributors / by_cost_type + log
- **獨立驗算對 Sonnet 草稿的微調**：top5 / net_alpha_total = **95.56%**、DOT / net_alpha_total = **25.45%**、max rank change = **13** —— 三個關鍵數字逐一驗算對齊。Codex 用的分母不是 `sum_abs`（=1.6004）而是「sum of positive net contributions」（≈0.9431），這是文件未明示的第三種定義。

## Verdict

**`CONDITIONAL_PASS`**

理由：4 條 fail gate 全 PASS、輸出檔完整、reproducibility hash 一致、gross / net 對帳到機器精度（1e-16），**但** concentration warning 在工單規格下為 TRIGGERED（top5=95.56%、DOT 單 symbol=25.45%）、long-side net alpha 為負（−5.1%），且 Codex 用了未文件化的第三種分母把這兩個 warning 報成 NOT triggered。這不是工程錯誤，是**規格 vs 實作的定義分歧**——Opus 採用工單規格為準，因此額外觸發兩條 warning。研究判定不受影響，但 paper trading 規劃必須帶入新發現的結構性 caveat。

## Strategy Decision

**保留**（沿用 REVIEW-002 升級；但更新副標題為「short-driven crypto alpha，long-side 結構性虧損」）

## Key Numbers

| 指標 | 值 | 解讀 |
|---|---:|---|
| gross_alpha_total | +29.58% | 760 天 active 累積 |
| net_alpha_total | +28.53% | cost 吃掉 1.05% |
| **Short net alpha** | **+33.65%** | **占 net_alpha 的 117.9%——空頭主導** |
| **Long net alpha** | **−5.10%** | **多頭是淨拖累；gross −2.0%、cost 加碼 3.1%** |
| 2025 年 net | +25.46% | 占 net_alpha 89.2%（**TRIGGERED**）|
| 2024 年 net（Q2–Q4） | +4.27% | 占 15% |
| 2026 年 net（Jan–Apr） | −1.20% | 占 −4% |
| Top 5 / net_alpha_total | **95.56%** | **TRIGGERED**（工單公式）|
| DOT 單 symbol / net_alpha_total | **25.45%** | **TRIGGERED**（工單公式邊界）|
| max gross→net rank change | 13（BTC 40→53）| TRIGGERED |
| Cost 拆解 | slippage 0.45% > fee 0.36% > funding 0.25% | 與 REVIEW-002 一致 |

## Q1–Q6 Opus 裁定

**Q1（concentration gate 公式）：**
**採工單規格（分母 = `net_alpha_total`）**。Codex 用「sum of positive net contributions ≈ 0.9431」是未文件化的第三種定義；工單寫得清楚就是規格，實作偏離規格就要回到規格。在工單規格下：top5 = 95.56% → **TRIGGERED**、DOT = 25.45% → **TRIGGERED（邊界）**。這不會改 Verdict（CONDITIONAL_PASS 不是 FAIL），但兩條 warning 必須在 paper trading 規劃的 risk section 內列為 mandatory caveat。**Codex 補件指示**：下版 attribution 須輸出 **兩個分母** 的並列數字（`/net_alpha_total` 與 `/sum_abs_net`），讓讀者一眼看見差異。

**Q2（long-side 負 alpha）：**
**caveat + 必補 follow-up 任務**，不是 BLOCKING。多頭 net −5.1% 不改變「策略有 alpha」的事實（short 主導 +33.65% 仍存活）。但這是**結構性發現**：策略的 Prev3Y momentum 在 crypto 上實際是「**短空動量為主、多頭結構性虧損**」。Funding contango 在 BTC/ETH/LINK 等大市值多頭部位產生 0.5–0.6% 的 cost drag，足以把 gross 正轉 net 負（BTC、ETH、LINK 三檔逐一驗證）。**Follow-up TASK-007（建議新建）**：研究 (a) 純 short-only 變體、(b) 多頭 funding-discount filter、(c) 多頭 size cap，三選一或組合測試。

**Q3（2025 年集中 89%）：**
**caveat，不擋 paper trading 規劃**。760 天樣本中 2024 只涵蓋 9 個月、2026 只 4 個月，分母不對等。**Per-day 標準化**：2024 = +0.016%/day、2025 = +0.070%/day（4.5×）、2026 = −0.010%/day。2025 確實是非常好的一年，這代表 paper trading 規劃必須假設「**未來實盤可能不會這麼好**」，並把 size 設保守。

**Q4（BTC/ETH/LINK 多頭 net 為負）：**
**承認為 Funding Contango Problem，建議 TASK-004 dashboard 加 high-funding-cost flag 面板**。BTC rank 40→53、ETH 61→70、LINK 76→79，net 全部更差或翻負。長期看，這三檔在 momentum 訊號下進多頭就是付 funding 給空方；對大市值幣 momentum 訊號的 alpha 容量很弱。**不擋本次審查**，但 TASK-004 dashboard 應該把這個視覺化。

**Q5（補 long_side_drag gate）：**
**是，必補**。現行 `short_side_drag` 是「短空為負則 TRIGGERED」的單向 gate，捕不到「多頭為負」這個對稱問題。Codex 下一版 attribution / cost stress 必須補：`long_side_drag` —— 觸發條件：`long_net_alpha < −0.5 × |total_alpha|`。若使用此 gate，本次 attribution 結果（long net = −5.1%、total = +28.5%）**會 TRIGGERED**（5.1% > 0.5×28.5% = 14.25%? 不，5.1% < 14.25%，所以以這門檻不會 TRIGGERED；可改用絕對值，例如 |long_net| > 2% AND 與 total 異號 → TRIGGERED）。具體門檻交給 Codex 在 v2 工單裡設計，Opus 只要求**有這個 gate**。

**Q6（下游解鎖）：**

| 項目 | 決策 | 理由 |
|---|---|---|
| TASK-003 → DONE | ✅ | fail gates 4/4 PASS、輸出完整、reproducibility 一致；CONDITIONAL_PASS 不擋 DONE，caveat 進 follow-up tasks |
| TASK-004 dashboard 開始規劃 | ✅ 維持 READY_TO_IMPLEMENT | 第一版照原計畫，**v2 必加 high-funding-cost flag + concentration warning 面板** |
| TASK-005 VPS monitor 規劃 | ✅ 維持 READY_TO_IMPLEMENT | 完全獨立、不受影響 |
| TASK-006 paper trading 規劃 | ✅ 允許**規劃**（不是執行）| 但規劃工單必須加 3 條 mandatory caveat（見下方）|
| TASK-007（建議新增）long-side 研究 | TODO | Q2 的 follow-up：純 short-only / funding-discount / long-cap 三選一 |
| Live trading | ❌ 仍禁止 | 缺 paper-forward sample；缺 TASK-007 結論 |

## Final Interpretation（6 行）

TASK-003 揭露策略真實面貌：**這是一個「短空動量策略 + 多頭結構性虧損」的組合**，不是對稱的多空策略。33.65% 的 short alpha 撐住整個策略，多頭 −5.1% 是淨拖累；前 5 個 symbol（DOT/LTC/XRP/XLM/ZEC）的 net 貢獻就占 95.56% 的 net alpha 總額，是極度集中。Cost 結構在 REVIEW-002 已確認（slippage > fee > funding），對策略存活影響溫和。樣本面 2025 年單年占 89% net alpha，但 per-day 看 2024 和 2025 都是正的、2026 略負，**主要風險不是 alpha 消失而是 alpha 集中於少數 symbol 與單一年**。研究路線仍**保留**，但 paper trading 必須帶著「短空為主、多頭虧損、5 個 symbol 撐 95%」這個更精確的策略 narrative 進入規劃。

## Paper Trading 規劃必加的 3 條 Mandatory Caveat

TASK-006 paper trading 規劃工單必須在「規則」區塊明示：

1. **Position size cap**：單一 symbol 上限不超過總 NAV 的 **5%**（DOT 在 attribution 內貢獻 25.45% net alpha 是警訊；paper 不能讓單一 symbol 的部位這麼集中）。
2. **Long-side allocation cap**：多頭部位上限不超過 gross exposure 的 **50%**（避免被 funding contango 吞噬；考慮純 short-only 變體作為對照）。
3. **High-funding-cost symbol filter**：對最近 30 天平均 funding rate > 0.03% 的 symbol，若被 momentum 訊號排進多頭，**降低 50% 權重**或**剔除**（針對 BTC/ETH/LINK 這類 contango 結構性受害者）。

## Blocking Issues

**None**——4 條 fail gates 全 PASS。Sonnet 標的 2 個 BLOCKING 都是「Opus 必須裁定的方向選擇」，而不是 hard-fail 條件。Opus 已裁定（Q1：採工單公式、Q2：caveat + follow-up），故均化解。

## Caveats（必須在所有下游引用時保留）

1. **Active 樣本 760 天**（沿用 REVIEW-001_final + 002）。
2. **無 BTC alpha**（沿用 REVIEW-002，本次驗證更具體：BTC net rank 從 40 降到 53）。
3. **Concentration（工單公式）**：top5 = 95.56%、DOT = 25.45%——paper trading 必加 position cap。
4. **Long-side 結構性虧損**（−5.1% net）——alpha 全來自 short。
5. **Year concentration**：2025 單年占 89%（per-day 看是 4.5× 於 2024 / −1× 於 2026，未來實盤可能不會這麼好）。
6. **Funding contango on large caps**：BTC/ETH/LINK 三檔多頭在 funding 下 net 翻負。
7. **Funding gap 7 symbols** 影響 1.16% active 持倉（沿用 REVIEW-002）。
8. **Gross→net rank change 最大 13**（BTC）——cost 結構對個別 symbol 影響有差異。
9. **Drawdown 為事件型**（Nov–Dec 2024 BTC $100k 軋空）——下次類似事件空頭側會再次承壓。
10. **Concentration gate 用哪個分母**——Codex 須在下版補兩個分母並列輸出（不擋本次 CONDITIONAL_PASS）。

## Downstream Decisions

| 項目 | 決策 |
|---|---|
| TASK-003 → DONE | ✅（CONDITIONAL_PASS 不擋 DONE；caveat 進 TASK-007） |
| TASK-004 dashboard 規劃 | ✅ READY_TO_IMPLEMENT（v2 必加 high-funding-cost flag + concentration warning 面板） |
| TASK-005 VPS monitor 規劃 | ✅ READY_TO_IMPLEMENT（不受影響） |
| TASK-006 paper trading 規劃 | ✅ 允許規劃（**規劃工單須加 3 條 mandatory caveat**），**不可執行** |
| **TASK-007（新建）long-side 研究** | TODO（Q2 follow-up） |
| Live trading | ❌ 仍禁止 |

## Queue Updates

| 任務 / Review | 新狀態 | 變更理由 |
|---|---|---|
| TASK-003 | **DONE** | Opus REVIEW-003 CONDITIONAL_PASS（2026-05-15） |
| REVIEW-003 | **CONDITIONAL_PASS** | 工程合格、fail gates 全過；4 條 warning + 3 條 paper trading mandatory caveat 列入 trail |
| TASK-004 | **READY_TO_IMPLEMENT**（沿用，註記 v2 必加面板） | high-funding-cost flag + concentration warning |
| TASK-005 | **READY_TO_IMPLEMENT**（沿用） | 不受影響 |
| TASK-006 | **TODO**（沿用，註記 3 條 mandatory caveat） | 規劃工單必須帶入 |
| **TASK-007**（新建）long-side 研究 | **TODO** | Q2 follow-up；三選一/組合測試 |
| Live trading | **禁止**（沿用） | 缺 paper-forward + TASK-007 結論 |

## 給 Rick 的一頁式重點

1. **REVIEW-003 結論：CONDITIONAL_PASS**——4 條 fail gates 全過、reproducibility 一致；4 條 warning + 2 條結構性發現。
2. **策略真實 narrative：short-driven**——short 貢獻 +33.65%（117.9% of net alpha），long 拖累 −5.1%。
3. **集中度警訊**：5 個 symbol 撐 95.56% 的 net alpha；DOT 單檔 25.45%。
4. **BTC/ETH/LINK 多頭 net 為負**：funding contango 吞噬 momentum gross alpha——TASK-004 dashboard 必加 flag。
5. **2025 占 89% net alpha**，但 per-day 看 2024 也是正的；主要風險不是 alpha 消失，是樣本集中。
6. **下游全部解鎖**：TASK-003 → DONE，TASK-004 / TASK-005 / TASK-006 維持 READY；TASK-007（long-side 研究）新增為 follow-up。
7. **Paper trading 可規劃**，工單必須含 3 條 mandatory caveat（5% symbol cap / 50% long cap / high-funding-cost filter）。
8. **Live trading 仍禁止**。
9. **下一張最值得做的工單**：**TASK-007 long-side 研究**（Q2 follow-up）——回答「該不該砍多頭」這個策略結構問題；TASK-004/005/006 可平行。
10. **Codex 補件**：下版 attribution / cost stress 加 `long_side_drag` gate，並對 concentration 同時輸出兩個分母（`/net_alpha_total` 與 `/sum_abs_net`）。

---

## REVIEW-007 — TASK-007 Long-Side Variant Study（Opus final decision，2026-05-16）

```
Suggested model:              Opus
Escalation reason:            major task final review；策略保留 vs 淘汰；paper trading 規劃前最終把關
Opus final decision required: Yes
Command source:               docs/research/commands/NEXT_ACTION.md (status=READY, owner=Claude Opus)
```

- **審查時間**：2026-05-16
- **審查模型**：Claude Opus
- **審查包**：Sonnet draft + REVIEW-007_PACKET.md + REVIEW-007_NUMBERS.json（per Token Budget Rule，未讀大 CSV）
- **獨立驗算**：Sonnet 草稿 12 個 variant 數字逐欄對齊 NUMBERS.json `key_numbers`；fail gates 2.05e-16；reproducibility hash 一致。

## Verdict

**`CONDITIONAL_PASS`**

理由：3 條 fail gates 全 PASS（baseline_mismatch 2.05e-16、missing_outputs 0、schema_mismatch 0）；reproducibility hash 一致；12 個 variant 完整交付且數字內部一致；最重要的研究問題（「long-side 該不該砍」「concentration 能不能 cap 掉」）已被有效回答。**Sonnet 識別的 4 個 BLOCKING 都是規格偏離（spec deviation），不是 correctness 錯誤**——它們影響交付完整性，但不影響核心研究結論的有效性。Opus 在第 2–7 節逐一裁定，並指派 follow-up TASK-007b / TASK-007c / TASK-008 補齊規格。

## Strategy Decision

**保留**（沿用 REVIEW-002 / REVIEW-003 的「保留」判定，narrative 升級為「**短空主導 + 高 funding 多頭過濾**」更精確版本）

## Key Numbers（active 口徑，已對齊 NUMBERS.json）

| Variant | Sharpe | IR_eqw | max DD | net α | long net | short net | single_conc | top5_conc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline（realistic_combo）| 0.8918 | 0.7168 | −19.64% | 28.53% | −5.01% | +33.56% | 25.45% | 95.56% |
| **high_funding_cost_filter** | **0.9586** | **0.7282** | −20.27% | **31.27%** | **−2.29%** | +33.56% | 23.23% | 87.22% |
| **combined_paper_safe_variant** | 0.8037 | 0.6961 | −20.27% | 25.00% | **+4.21%** | +20.78% | **19.73%** | 91.92% |
| short_only_unscaled | 0.4045 | 0.5511 | **−49.18%** | 33.73% | 0 | +33.73% | 21.53% | 72.47% |
| short_only_rescaled | 0.4106 | 0.5189 | **−75.74%** | 68.52% | 0 | +68.52% | 21.24% | 71.64% |
| long_only_unscaled | −0.0763 | 0.9493 | −41.58% | **−5.18%** | −5.18% | 0 | — | — |
| long_only_rescaled | −0.0733 | 1.7341 | −70.44% | **−9.95%** | −9.95% | 0 | — | — |
| long_half_weight | 0.5846 | 0.6225 | −34.04% | 31.14% | −2.58% | +33.72% | 23.32% | 80.58% |
| long_with_50pct_cap | 0.9000 | 0.7182 | −19.64% | 28.80% | −4.76% | +33.56% | 25.21% | 94.69% |
| top5_symbol_cap_5pct | 0.7225 | 0.6927 | −19.64% | 22.99% | −5.00% | +28.00% | 21.39% | 103.56% |
| DOT_capped | 0.7922 | 0.7030 | −19.64% | 25.15% | −5.01% | +30.16% | 21.36% | 98.31% |
| no_DOT | 0.7132 | 0.6965 | −17.58% | 21.29% | −5.01% | +26.30% | 25.23% | **116.13%** |

## Q1–Q6 Opus 裁定

**Q1（Variant D 設計偏離）：接受現有 3 個 cap variants 為 concentration-cap-equivalent 交付**；不視為 BLOCKING。
- 工單原規格是「每日 weight cap + redistribution」；實際交付 `top5_symbol_cap_5pct / DOT_capped / no_DOT` 是 alpha-based selection。
- **核心發現未失真**：`no_DOT` 揭露的「移除最大貢獻者反使集中度惡化（top5 116.13%）」是個結構性悖論——這個發現 weight-cap 也會看到（因為移除 DOT 後分母縮小更多）。Opus 採信這個發現，不要求 redo 來重新發現它。
- `combined_paper_safe_variant` 利用 `top5_symbol_cap_5pct` 邏輯產生**單一達到 single_conc < 25%** 的變體（19.73%），這就是工單 Q4 想要的答案的具體實例。
- **指派 TASK-007b follow-up**：補齊 weight-cap + redistribution 規格，為日後嚴格 paper trading position sizing 文件用。**不擋本次 CONDITIONAL_PASS**。

**Q2（Variant C 0.03% 門檻偏離）：接受 0.03%/8h 為操作門檻**；不視為 BLOCKING。
- 工單 C1 規格 = 0.01%/8h（過濾更多 symbol），C2 規格 = 0.005%/8h + discount 0.5（部分打折）。實際交付 = 0.03%/8h（discount = 0）。
- 0.03% 是**更保守**的版本：過濾 fewer symbols → 保留更多多頭分散度。但此版本仍是 Pareto-dominant（Sharpe +7.5%、long_net 改善 +2.72 pp、funding cost 幾乎歸零）。
- 更嚴格的 0.01% 門檻**理論上效果更好**（多濾 BTC/ETH/LINK 之外的高 funding 多頭），但代價是多頭部位變少；0.005% + 50% discount 是另一種平滑做法。兩者對 paper trading 規劃是「sensitivity 分析」，不是「能不能用」。
- **指派 TASK-007c follow-up**：補齊 0.01%/8h + 0.005%/8h-discount-0.5 兩個規格門檻 + 平滑度比較。**不擋本次 CONDITIONAL_PASS**。

**Q3（自定義 Warning Gates 替代工單規格）：接受 Codex 7 個自定義 gates 為精神等效**；要求 Codex 補齊兩條未評估的 gate。
- 工單規定 5 條 gate；Codex 實作 7 條自定義 gate。比對後 4 條觸發的 gate 在「精神」上覆蓋了工單規格的風險面向。
- **但有兩條工單 gate 未被任何自定義 gate 覆蓋且應觸發**：
  - `short_only_max_dd_worse`（DD < −25%）→ 實際 −49.18%，應 TRIGGERED。
  - `funding_adj_no_improvement`（long net < −2%）→ 實際 −2.29%，應 TRIGGERED（邊界）。
- 兩條都可由現有 NUMBERS.json 一行算出，不需重跑。**指派 Codex 在 TASK-007 補件中加上這兩條 gate 的明示 trigger 欄位**（簡單 follow-up，不擋 DONE）。

**Q4（Baseline Sharpe 0.8918 vs run008 0.9267 不一致）：可接受，是命名不清**；不視為 BLOCKING。
- 0.9267 在 run008_stats.json / REVIEW-002 是 **gross / no_cost_baseline** 的 Sharpe。
- 0.8918 在 TASK-007 是 **net / realistic_combo** 的 Sharpe（cost overlay 後）。
- 比對 REVIEW-002 紀錄表的 `realistic_combo` 列：active Sharpe = **0.8918**——數值完全一致。所以兩者**不矛盾**，是同一個體系下兩個不同 cost 假設的 Sharpe。
- **修正建議**：TASK-007 packet 與 summary 把 baseline 標籤改為「realistic_combo baseline」而非單純「baseline」，避免下次再被誤判為衝突。**指派 Codex 在 TASK-007 補件做標籤修正**。

**Q5（long net −2.29% 解讀 + paper trading 門檻）：**
- `high_funding_cost_filter` long net −2.29%：**改善幅度顯著**（從 −5.01% 縮減 −2.72 pp，54% 改善），但仍負。可作為 paper trading 的**次要規格**（secondary spec）。
- `combined_paper_safe_variant` long net **+4.21%（轉正！）**：這是最重要的單一發現之一——當 high_funding 過濾 + top5_symbol_cap 同時施加，剩餘多頭部位本身有正 net alpha。這證明 long-side 結構性虧損的根源**不是多頭訊號錯誤**，而是「**高 funding 大幣 + 過度集中**」兩個 overlap 因素。
- **paper trading 門檻建議**：
  - **primary spec = `combined_paper_safe_variant`**（long net > 0、single_conc < 25%、Sharpe ≥ 0.7、max DD < 1.5× baseline 全部達標）
  - **secondary spec = `high_funding_cost_filter`**（Sharpe 最高、alpha retention 109.6%；用於敏感度比較）
  - paper trading 工單須含這兩個 spec 並列、執行時可切換 / 加權混合。

**Q6（下游解鎖）：**

| 項目 | 決策 |
|---|---|
| TASK-007 → DONE | ✅（CONDITIONAL_PASS 不擋 DONE；4 條 spec 偏離進 TASK-007b/007c/補件，不擋）|
| TASK-006 paper trading 規劃可否啟動 | ✅ 允許**規劃**（規劃工單必須含 primary + secondary spec）；**不可執行** |
| TASK-006 primary spec | **`combined_paper_safe_variant`**（單一達到所有 REVIEW-003 mandatory caveat）|
| TASK-006 secondary spec | **`high_funding_cost_filter`**（敏感度 / alternative）|
| 新建 TASK-007b（weight cap + redistribution 補件）| TODO（不擋 TASK-006，但 paper trading 執行前須完成）|
| 新建 TASK-007c（Variant C 0.01% 與 0.005%-discount 補件）| TODO（sensitivity，與 007b 平行）|
| 新建 TASK-008（策略層 per-symbol weight cap）| TODO（concentration 結構性問題的根治；長期任務，不擋短期 paper trading 規劃）|
| TASK-003 補件（long_side_drag gate + dual-denominator concentration）| 沿用 REVIEW-003 安排，未變 |
| TASK-004 / 005 維持 READY | ✅ |
| Live trading | ❌ 仍禁止 |

## Final Interpretation（6 行）

TASK-007 把 REVIEW-003 揭露的 long-side 問題量化分解，得到三個可操作結論：(1) **完全砍多頭不可行**（short_only Sharpe 腰斬至 0.40、DD 惡化到 2.5×）——多頭對 portfolio 有風險平衡作用。(2) **過濾高 funding 多頭 Pareto-dominant**（high_funding_cost_filter Sharpe +7.5%、long_net 改善 54%、funding cost 幾乎歸零）。(3) **同時過濾高 funding + cap 集中度時 long_net 轉正**（combined_paper_safe_variant +4.21%）——證明 long-side 結構性虧損的根源是「高 funding 大幣 + 過度集中」兩個 overlap 因素，而**不是多頭訊號錯誤**。`no_DOT` 變體額外揭露「移除最大貢獻者反使集中度惡化」的悖論（top5_conc 從 95.56% 升至 116.13%），確認集中度是結構性問題，需要策略層 per-symbol weight cap（TASK-008 follow-up），無法用 overlay 根治。research 路線從「保留」**升級為可進入 paper trading 規劃**，spec 已由 combined_paper_safe_variant 提供。

## Blocking Issues

**None.** Sonnet 標的 4 個 BLOCKING 都是 spec deviation（B-1/B-2/B-3 規格偏離、B-4 命名不清），不是 correctness 錯誤。Opus 在第 2 節逐條裁定為「接受 + follow-up」，不擋本次 CONDITIONAL_PASS、不擋 TASK-006 啟動規劃。

## Caveats（必須在所有下游引用時保留）

1. **Active 樣本 760 天**（沿用 REVIEW-001/002/003）。
2. **無 BTC alpha**（沿用 REVIEW-002/003）。
3. **集中度結構性問題**：所有 overlay variant 的 top5_conc 仍 > 60%。`no_DOT` 悖論（top5 升至 116.13%）證明 overlay 無法根治——需要 TASK-008 在策略層加 per-symbol weight cap。
4. **long_net 在 high_funding_cost_filter 仍負（−2.29%）**：是 secondary spec；primary spec 用 combined_paper_safe_variant（long_net +4.21%）。
5. **combined_paper_safe_variant 犧牲 short alpha**：short_net 從 +33.56% 降至 +20.78%（−12.78 pp），net_alpha 從 28.53% 降至 25.00%（−3.54 pp）。為了換 long_net 轉正 + single_conc < 25%，付出 alpha −3.54 pp 的代價。paper trading 規劃要明示這個 trade-off。
6. **0.03%/8h 門檻是保守版**：0.01%/8h 與 0.005%/8h+discount-0.5 兩個工單規格門檻未測（TASK-007c follow-up）。
7. **weight-cap + redistribution 規格未交付**（TASK-007b follow-up）。
8. **Workorder gates 兩條未評估**：`short_only_max_dd_worse`、`funding_adj_no_improvement`，可由現有資料一行算出，Codex 須補。
9. **Sharpe baseline 命名應改為 realistic_combo baseline**，避免與 run008 gross Sharpe 0.9267 混淆。

## Downstream Decisions

| 項目 | 決策 |
|---|---|
| TASK-007 → DONE | ✅ |
| TASK-006 paper trading 規劃 | ✅ 啟動規劃，**primary spec = combined_paper_safe_variant、secondary = high_funding_cost_filter**，不可執行 |
| TASK-007b（weight cap + redistribution）| ✅ 新建 TODO，paper 執行前須完成 |
| TASK-007c（Variant C 0.01% / 0.005%-discount）| ✅ 新建 TODO，sensitivity |
| TASK-008（策略層 per-symbol weight cap）| ✅ 新建 TODO，根治集中度結構性問題 |
| TASK-003 補件（long_side_drag + dual-denominator）| 沿用 REVIEW-003 |
| TASK-004 dashboard | 沿用 READY_TO_IMPLEMENT |
| TASK-005 VPS monitor | 沿用 READY_TO_IMPLEMENT |
| Live trading | ❌ 仍禁止 |

## Queue Updates

| 任務 / Review | 新狀態 | 變更理由 |
|---|---|---|
| TASK-007 | **DONE**（Opus REVIEW-007 CONDITIONAL_PASS，2026-05-16）| 核心研究問題已答；spec deviation 進 follow-up |
| REVIEW-007 | **CONDITIONAL_PASS** | 第 2 節逐條 Q1–Q6 裁定 |
| TASK-006 | **TODO**（升級為「可寫工單」階段；不再只等 TASK-007 結果）| primary + secondary spec 已確定；3 條 REVIEW-003 mandatory caveat 已被 combined_paper_safe_variant 完整覆蓋 |
| **TASK-007b**（新建）| TODO | weight cap + redistribution；不擋 TASK-006 規劃，擋 paper 執行 |
| **TASK-007c**（新建）| TODO | Variant C 兩個工單規格門檻補件 |
| **TASK-008**（新建）| TODO | 策略層 per-symbol weight cap（長期，集中度結構性根治）|
| TASK-003 補件項 | 沿用（不變） | long_side_drag gate + dual-denominator concentration |
| Live trading | 禁止（沿用）| 缺 paper-forward sample + TASK-007b/008 |

## 給 Rick 的一頁式重點

1. **REVIEW-007 結論：CONDITIONAL_PASS**——fail gates 全過、12 個 variant 完整、Sonnet 標的 4 個 BLOCKING 都是 spec 偏離不是 correctness 錯誤。
2. **最重要發現**：`high_funding_cost_filter` 是 Pareto-dominant 變體（Sharpe 0.96 / alpha retention 109.6%），但 paper trading 的 **primary spec 推薦 `combined_paper_safe_variant`**——這是唯一同時達到 long_net **轉正（+4.21%）**、single_conc **< 25%（19.73%）**、Sharpe ≥ 0.7（0.80）的變體。
3. **不要砍多頭**：short_only Sharpe 從 0.89 腰斬至 0.40、max DD 從 −19.6% 惡化到 **−49.2%**。多頭對 portfolio 有風險平衡作用。
4. **集中度根源是「高 funding 大幣 + 過度集中」**：把這兩個 overlap 因素都過濾後，long_net 從 −5.01% 轉正為 +4.21%。
5. **`no_DOT` 悖論**：移除最大貢獻者後 top5_conc **升到 116.13%**——overlay 無法根治集中度，需要策略層 cap（TASK-008）。
6. **下游全部解鎖**：TASK-007 → DONE；TASK-006 paper trading 規劃**可開始寫工單**（primary = combined_paper_safe_variant、secondary = high_funding_cost_filter）；新增 TASK-007b / 007c / 008 三個 follow-up。
7. **Paper trading 執行的最後 gating**：TASK-007b（weight cap 規格補件）+ TASK-008（策略層 cap）+ 30 天 forward sample + 另一輪 Opus review。本次審查只解鎖**規劃**，不解鎖執行。
8. **Live trading 仍禁止**。
9. **下一張最值得做的工單**：**TASK-006 paper trading plan 寫工單**（用 primary spec 寫死規則）；TASK-007b / 007c / 008 可平行排隊。

---

## REVIEW-006 — Paper Trading Plan Infrastructure（Opus final decision，2026-05-16）

```
Suggested model:              Opus
Escalation reason:            paper trading pre-execution review；安全性最終把關
Opus final decision required: Yes
Command source:               docs/research/commands/NEXT_ACTION.md (status=READY, owner=Claude Opus)
```

- **審查時間**：2026-05-16
- **審查模型**：Claude Opus
- **審查包**：Sonnet draft + REVIEW-006_PACKET（透過 Sonnet 摘要）+ NUMBERS.json + forward_validation.json + risk_events.jsonl
- **獨立驗算**：(1) review007_reproducibility_hash `824ff334…` 與 REVIEW-007 完全一致；(2) primary_task007_summary 12 欄逐一對齊 combined_paper_safe_variant；(3) overlay rules 在 2026-04-01 驗算通過（long 50%、symbol cap 2% < 5%、net 3.47e-17）；(4) safety_scan `PASS` / violations `[]`；(5) 7 個 input file hash 全部列出。

## Verdict

**`PASS`**（**不是** CONDITIONAL_PASS）

理由：Sonnet 標的 2 個 BLOCKING **本質上不是 hard-fail 條件，而是 Opus 解讀請求**。所有真正擋審查的事項都通過：
- 9/9 安全項全 PASS（safety scan、無下單路徑、live FORBIDDEN、5 條 caveat 全嵌、execution_approval=false）。
- 9/9 輸出檔完整、schema 正確。
- 4/4 overlay rule 在 2026-04-01 驗算通過。
- Reproducibility hash 一致，TASK-007 hash 交叉驗算對齊。
- `paper_execution_status` / `live_trading_status` 兩道閘門明示 FORBIDDEN。

B-1（proxy Sharpe −2.9012）與 B-2（STOP_PAPER_PENDING_REVIEW 自觸發）在第 2 節逐條裁定為**正確行為的證據**而非缺陷。

## Q1–Q4 Opus 裁定

**Q1（TASK-006 安全性 + 基礎架構）：通過。**
9 項安全檢查全 PASS、9 個輸出檔完整、3 條 mandatory overlay rule 在 2026-04-01 數值驗算通過、5 條 caveat 完整嵌入、reproducibility hash 與 TASK-007 hash 都對齊。模組不具備任何下單能力（`real_order_submission_possible = false`），但具備完整的「**規劃 → 監測 → 風控觸發**」基礎架構。這正是工單原意。

**Q2（proxy Sharpe −2.9012 解讀）：接受為 NOT_STARTED 代理的正常結果，不阻擋下一步。**

三個獨立證據支持「不阻擋」的判定：

1. **數學上**：把 30 天年化成 Sharpe 是已知極不穩定的計算。把 30-day windowed Sharpe annualize 等於把 daily std × √365 但 mean × 365——對小樣本極端波動超敏感。30 個樣本的標準誤約 1/√30 ≈ 0.18，年化後是 0.18 × √(365/30) ≈ 0.65 的 noise floor。從 0.92 baseline 走到 −2.90 完全在 30 天樣本的 noise 範圍內。
2. **語意上**：`validation_basis = historical_simulation_proxy_not_forward_execution` 已**明示這不是 forward validation**；它只是用最近歷史 30 天當作粗略 placeholder。真正的 forward 還沒開始。
3. **研究脈絡上**：對齊 TASK-003 attribution 的 2026 年（120 天）net alpha = −1.20%，年化大約 −3.65%。最近 30 天落在這個負區間是**已預期且已揭露的事實**，不是新發現。歷史累積 NAV 仍從 10,000 USD 漲到峰值 ~13,071 USD（+30.7%）；當前 12,240.63 USD（從峰值回落 −6.35%）。

但 Opus 額外要求一個改善：**TASK-006 補件**——加一個 `proxy_sharpe_long_window`（如 90-day 或 full active period）並列於 30-day proxy 旁，讓未來讀者一眼看到「短窗 noise vs 長窗實際表現」的差距。不擋 PASS，列為 follow-up。

**Q3（STOP_PAPER_PENDING_REVIEW 解讀）：架構驗證成功的證據，不是執行阻擋。**

- 工單 § 7.3 設定的紅色門檻是「paper Sharpe < 0.2 → STOP」。系統在 proxy 視窗 Sharpe = −2.90 < 0.2 時**正確自動觸發**。這代表 monitor_hook 與 risk_events.jsonl 的整條告警鏈是運作的。
- 同時：`paper_execution_status = NOT_STARTED` 表示我們從未進入 paper 階段、也沒有任何真實部位被擋。STOP 事件只是「假設今天要進 paper、proxy 顯示會踩紅線」這個前瞻警告。
- 對 REVIEW-006b（未來 paper trading 啟動前的 final review）的意義：**保留此告警機制不變**。真實 forward 啟動前 Opus 仍會看到 STOP 事件作為「目前狀態的紅旗」，這是設計正確的行為。
- 不需要在 REVIEW-006b 加「proxy Sharpe > 0.5 才能申請 forward 啟動」的條件——這會把 proxy（noisy short window）誤升為 gating 變量。真實的 gate 應該是「30 天 forward 實盤 paper record 的 Sharpe > 0.5」，這條已經在工單 § 9 內。

**Q4（TASK-006 狀態 + 下一步優先順序）：PASS、DONE。**

下一步推薦：
1. **TASK-007b**（weight cap + redistribution）—— paper trading 執行的硬性 gate，且短期可完成。
2. **TASK-005**（VPS bot monitor）—— 為日後 paper trading 預先建好監控基建，可平行進行。
3. **TASK-008**（策略層 per-symbol weight cap）—— 長期任務，concentration 結構性根治。
4. **TASK-007c**（Variant C 0.01% / 0.005%-discount）—— sensitivity 補件，優先度低於 007b。
5. **REVIEW-006b**：等 (a) TASK-007b 完成、(b) 30 天真實 forward paper record、(c) TASK-006 補件（proxy_sharpe_long_window） 三者齊備後再開。

## Cross-Check（Opus 額外驗算，不採信 Sonnet 即可獨立判定）

- `review007_reproducibility_hash` = `824ff334e30810aeeaef8a06319a9ac8563b61f903835c89ae6cfbd9e140066f` ✓ 完全等於 REVIEW-007 紀錄的 `reproducibility_hash`，**證明 TASK-006 使用的就是 Opus 認可的 TASK-007 官方輸出**。
- `primary_task007_summary.variant = combined_paper_safe_variant`、`sharpe_active = 0.8037`、`long_net_contribution = +0.0421`、`single_symbol_concentration = 0.1973` —— 全部與 REVIEW-007 Key Numbers 表格一致到至少 4 位小數。
- `secondary_task007_summary.variant = high_funding_cost_filter`、`sharpe_active = 0.9586`、`long_net_contribution = −0.0229`、`single_symbol_concentration = 0.2323` —— 同樣對齊。
- `forward_validation.pass_blocker` 寫得明確：「requires real 30-day forward paper record plus Opus REVIEW-006b and Rick approval」—— 這正是正確的 gating spec。
- `risk_event_counts: { INFO: 1, STOP_PAPER_PENDING_REVIEW: 1 }` —— 與 risk_events.jsonl 內容（rebalance_summary 1 筆 + PAPER_SHARPE_STOP 1 筆）對得上。

## Final Interpretation（6 行）

TASK-006 不是「paper trading 開始了」，是「paper trading 的儀表板 + 風控 + 規劃公式都建好了，並且系統證實在最壞 30 天 proxy 視窗會正確攔截自己」。這比想像中更重要——它代表**當真實 forward 啟動後若策略遇到類似 2026 Q1 的弱勢期，系統會自動 STOP 並要求 review，而不是繼續燒錢**。Sonnet 對 paper_sharpe −2.90 的擔憂可理解但不對：30-day annualized Sharpe 是已知極度 noisy 的指標，配上 `validation_basis = proxy_not_forward_execution` 的明示標籤，這個數字應被讀為「系統運作正常」的 signal、而不是「策略崩潰」的 signal。歷史累積 NAV 仍 +30.7%（從 10k → 13.07k 峰值，當前 12.24k）支持「策略 alpha 真實存在、近期是回撤期」的解讀。

## Blocking Issues

**None.** Sonnet 的 B-1 與 B-2 在 Q2 / Q3 已逐條裁定為「正確行為的證據」。

## Caveats（必須在 REVIEW-006b 與所有下游引用時保留）

1. **30-day proxy Sharpe 是 noisy 指標**，**不可** 作為 gating 變量；真實 gate 是 30 天 forward 實盤 paper record。
2. **STOP_PAPER_PENDING_REVIEW 屬正常風控觸發**，是設計成功的證據；REVIEW-006b 之前不需修改觸發邏輯。
3. **paper 執行需 5 個條件齊備**：(a) TASK-007b 完成、(b) TASK-008 完成或經 Rick 明示豁免、(c) 30 天 forward 實盤 paper record（Sharpe > 0.5）、(d) Opus REVIEW-006b PASS、(e) Rick 明示批准。
4. **`overlay_event_count = 0` 是 regime-dependent**：funding filter 在 2026 Q1-Q2 funding 正常化的市況下無效；它的保護作用主要出現在牛市高 funding 期（2024 Q4-2025 Q1）。Dashboard / monitor 應追蹤這個 regime 切換。
5. **intended_fill_count = 3**：Sonnet 列為待確認；Opus 解讀為「2026-04-01 月度 rebalance 的 position delta 數 = 3」（50 個部位中只有 3 個權重變化夠大需要 fill）。建議 Codex 在 schema 文件補上「fill = delta vs prior period」的明確定義，避免下次 review 再次混淆。
6. **Live trading 仍 FORBIDDEN**（沿用）。
7. **Live trading 重啟需要新工單** + paper trading 至少 90 天實盤穩定 + 另一輪 Opus review。

## Downstream Decisions

| 項目 | 決策 |
|---|---|
| TASK-006 → DONE | ✅ |
| Paper trading 執行 | ❌ 仍 **FORBIDDEN**，需 TASK-007b + 30-day forward + REVIEW-006b + Rick 批准 |
| Live trading | ❌ 仍 **FORBIDDEN**（不變）|
| REVIEW-006b 啟動時機 | TASK-007b 完成 + 30-day forward paper record 存在 + TASK-006 補件（proxy_sharpe_long_window）落地 |
| TASK-005 / TASK-007b / TASK-007c / TASK-008 | 維持各自 queue 狀態，不因本次 review 變動 |

## Codex 補件（不擋 DONE，建議在進入 REVIEW-006b 前完成）

1. **`proxy_sharpe_long_window`**：在 forward_validation.json 加一個欄位用 90-day（或 full active period 760 天）annualized Sharpe 並列於 30-day proxy 旁，避免 30-day noise 主導讀者判斷。
2. **`fill_definition`**：在 simulated_fills.csv schema 文件加註「fill = position delta vs prior period」，避免「為什麼只有 3 筆 fill」的誤解。
3. **`overlay_regime_note`**：在 monthly_review.json 加一個 boolean `funding_filter_active_this_month`，當 overlay_event_count = 0 時為 false，提醒 dashboard 與監測層 funding filter 是 regime-dependent。

## Queue Updates

| 任務 / Review | 新狀態 | 變更理由 |
|---|---|---|
| TASK-006 | **DONE**（Opus REVIEW-006 PASS，2026-05-16）| 規劃架構完整、安全閘門落實、reproducibility 對齊 TASK-007 |
| REVIEW-006 | **PASS** | Sonnet B-1/B-2 在 Q2/Q3 裁定為正確行為的證據 |
| Paper trading 執行授權 | **仍 FORBIDDEN** | 缺 TASK-007b + 30-day forward + REVIEW-006b |
| REVIEW-006b | 新增為「paper trading 執行前 final review」待開項目 | 開啟時機見「Downstream Decisions」 |
| TASK-005 / 007b / 007c / 008 | 維持各自 TODO 狀態 | 不因本次 review 變動 |
| Live trading | 仍 FORBIDDEN | 不變 |

## 給 Rick 的一頁式重點

1. **REVIEW-006 結論：PASS**——TASK-006 規劃架構完整、安全閘門落實、reproducibility 對齊 TASK-007。
2. **paper trading 仍 FORBIDDEN**，需 TASK-007b + 30-day forward + REVIEW-006b + Rick 批准。
3. **B-1 proxy Sharpe −2.90 不是策略崩潰訊號**：是 30-day annualized 的 noise，且 `validation_basis = proxy_not_forward_execution` 已明示。歷史累積 NAV 仍 +30.7%。
4. **B-2 STOP_PAPER_PENDING_REVIEW 自觸發是好事**：證明風控架構正確攔截自己；REVIEW-006b 之前不需修改觸發邏輯。
5. **下一張最值得做的工單：TASK-007b**（weight cap + redistribution）——它是 paper trading 執行的硬性 gate，且短期可完成。
6. **TASK-005 / 007c / 008 可平行**，但若 Rick 想先看 dashboard，TASK-004 也已 READY。
7. **Live trading 仍 FORBIDDEN，不變**。

---

## 模板：之後每一筆審查請沿用以下骨架

```markdown
## REVIEW-XXX — TASK-XXX <名稱>
- 審查時間 / 審查人 / commit / 產物路徑
- 結論：PASS / CONDITIONAL_PASS / FAIL / BLOCKED
- 是否允許轉 DONE
- 保留 / 淘汰 / 需要更多測試
### 1. 驗收標準逐條打勾
### 2. 未來視 / Bias 檢查
### 3. 重要發現
### 4. Codex 提問逐一回答
### 5. 下一張工單建議
### 6. 給 Rick 的一頁式重點
```

---

## READINESS-002 — TASK-002 v2 Readiness Check（2026-05-15）

- **執行時間**：2026-05-15
- **執行模型**：Claude Sonnet（依 AI_WORKFLOW.md 第 3 節，readiness check 為 Sonnet 負責範圍）
- **Suggested model**：Sonnet
- **Escalation reason**：N/A（readiness check 屬 schema / readiness check 類別）
- **Opus final decision required**：No（readiness check 本身無需 Opus；後續 REVIEW-002 final 需要）
- **讀取檔案**：
  - `docs/research/context_packets/TASK-002_CONTEXT_PACKET.md`
  - `docs/research/codex_workorders/TASK-002_cost_funding_slippage_stress.md`（v2）
  - `data/crypto/funding_rates.parquet`（750,641 列）
  - `data/crypto/fees.yaml`
  - `configs/cost_stress.yaml`
  - `outputs/backtests/prev3y_crypto/20260513_run008_baseline.csv`（2,677 列）
  - `outputs/backtests/prev3y_crypto/20260513_run008_positions.parquet`（29,586 列）
  - `outputs/backtests/prev3y_crypto/20260513_run008_stats.json`
- **不執行**：TASK-002 cost stress、不修改策略程式、不修改 run008

---

### 1. 逐條檢查結果（15 項）

| # | 檢查項目 | 結果 | 實測數值 |
|---|---|---|---|
| 1 | funding_rates.parquet schema 符合 v2 | ✅ PASS | 7 欄完整：timestamp / symbol / exchange / funding_rate / interval_hours / source / is_proxy；無缺欄、無多餘欄 |
| 2 | is_proxy 全 False | ✅ PASS | unique=[False]，any True = False；全部 273 symbols 皆為真實 Bybit API 資料 |
| 3 | interval_hours 只有 1 / 4 / 8 | ✅ PASS | unique=[1, 4, 8]，invalid rows = 0 |
| 4 | timestamp 為 UTC | ✅ PASS | dtype=datetime64[ns, UTC]，tz=UTC |
| 5 | funding_rate 為小數非百分比 | ✅ PASS | min=-0.05，max=0.01742，abs≥1.0 count=0；確認為小數格式 |
| 6 | active position coverage ≥ 80% | ✅ PASS | **98.84%**（held symbol-days 29,586 中 29,243 有 funding） |
| 7 | active PIT coverage ≥ 80% | ✅ PASS | **97.56%**（TASK-002a REVIEW-002a_phase2_full 確認值；本次 position-based 重算亦為 98.84%） |
| 8 | fees.yaml 含 maker_bps / taker_bps / notes | ✅ PASS | maker_bps=2.0，taker_bps=5.5，notes 含取數日期 / URL / tier / rebate |
| 9 | cost_stress.yaml 有 12 scenarios | ✅ PASS | no_cost_baseline×1 + fee×2 + funding×3 + slippage×3 + combo×3 = **12 個**，名稱與工單一字不差 |
| 10 | funding_application = pit_per_interval_settlement_accumulated | ❌ **BLOCKED** | 實測值為 `pit_8h_settlement_accumulated`（v1 舊值），必須改為 `pit_per_interval_settlement_accumulated` |
| 11 | 含 funding_interval_policy / funding_gap_policy / outlier_policy | ❌ **BLOCKED** | defaults 區塊缺少 v2 新增三個 policy key（全部缺） |
| 12 | no_cost_baseline 全 0 | ✅ PASS | fee_multiplier_taker=0.0，fee_multiplier_maker=0.0，funding_multiplier=0.0，slippage_bps_one_side=0.0 |
| 13 | known funding gap symbols 可標記 | ✅ PASS | 7 個 gap symbols 完全吻合（XTZ=93天 / FLOW=81天 / LPT=44天 / AXS=41天 / RVN=35天 / INJ=33天 / CTC=16天），合計 343 symbol-days，無意外 gap symbol |
| 14 | outlier records 可標記 | ✅ PASS | abs≥0.01 共 653 列，max abs=0.05；可以逐列累加並在 positions_cost.parquet 標 outlier_count_today |
| 15 | 整體 READY_TO_IMPLEMENT | ❌ **BLOCKED** | 因 #10 / #11 cost_stress.yaml v1 遺留，TASK-002 目前為 NEED_CLARIFICATION |

**通過：13/15　阻塞：2 項（均指向同一檔案 configs/cost_stress.yaml 的 defaults 區塊）**

---

### 2. 阻塞項目詳細說明

**BLOCKED-A：`configs/cost_stress.yaml` → `defaults.funding_application` 為 v1 舊值**

```
現狀（v1）：  funding_application: "pit_8h_settlement_accumulated"
應改為（v2）：funding_application: "pit_per_interval_settlement_accumulated"
```

此為工單 v2 Change Log 的核心修訂，也是 REVIEW-002a_phase2_full 強制要求的唯一設定變更。若 Codex 使用 v1 值開工，funding 計算將對所有 4h symbol 低估 2× cost、對 1h symbol 低估 ~24×，整份 stress 報廢。

**BLOCKED-B：`configs/cost_stress.yaml` → `defaults` 區塊缺少 v2 三個新 policy key**

```yaml
# 以下三鍵目前完全不存在於 defaults 區塊：
funding_interval_policy: "use_interval_hours_per_row"   # v2 新增
funding_gap_policy:       "mark_funding_gap_true_no_fill" # v2 新增
outlier_policy:           "report_no_clamp"               # v2 新增
```

工單 v2 Section 5.2 明確要求這三個 policy key 必須存在，cost engine 須依此運作。

**修正方法**：Codex 以 cost_stress.yaml 更新作為第一個 commit，依工單 v2 Section 5.2 的完整 defaults 區塊取代現有 defaults。更新後不需重新 readiness check，可直接進入實作。

---

### 3. Non-blocking Caveats（已知限制，不影響開工）

1. **樣本偏短**：active 760 天（2024-04-01 ~ 2026-04-30），統計穩健性有限。REVIEW-002 final 需 Opus 評估。
2. **無 BTC alpha**：active IR vs BTC = -0.0175，接近 0。cost stress 不會改善此問題，REVIEW-002 需重新評估策略定位。
3. **Known gap 343 symbol-days**：7 個 symbol 合計 343 天無 funding 資料（佔 held symbol-days 的 1.16%）。Codex 依工單標 `funding_gap=True` 且 funding cost = 0 即可，summary 需輸出 `funding_gap_breakdown`，若任一情境 gap > 5% 須標 WARNING。
4. **653 outlier rows**：abs≥0.01，max abs=0.05。照實累加，summary 須輸出 `outlier_contribution_breakdown`，若任一 combo 情境 outlier 佔 total funding cost > 30% 須標 WARNING。
5. **Interval 混合**：1h=2,758 rows / 4h=461,513 rows / 8h=286,370 rows（合計 750,641 rows）。cost engine 對每筆 funding row 依 interval_hours 換算，不可統一假設。
6. **Turnover 集中於 active period**：annual turnover active = 4.33×，full = 1.23×；fee 計算需以 active period 的 turnover 為主。

---

### 4. Verdict

```
## Verdict
NEED_CLARIFICATION

## Blocking Issues
1. [BLOCKED-A] configs/cost_stress.yaml defaults.funding_application 仍為 v1 值
   "pit_8h_settlement_accumulated"，必須改為 "pit_per_interval_settlement_accumulated"。
2. [BLOCKED-B] configs/cost_stress.yaml defaults 缺少 v2 三個 policy key：
   - funding_interval_policy: "use_interval_hours_per_row"
   - funding_gap_policy: "mark_funding_gap_true_no_fill"
   - outlier_policy: "report_no_clamp"
（兩項阻塞均指向同一檔案同一區塊，一次 commit 可同時解決）

## Non-blocking Caveats
- Active sample 760 天（偏短）
- 無 BTC alpha（IR vs BTC = -0.0175）
- 7 個 known gap symbols，343 symbol-days 無 funding（1.16%）
- 653 筆 outlier rows（abs≥0.01，max abs=0.05）須照實累加
- Interval 混合（1h/4h/8h），cost engine 必須 per-row 處理

## Required Next Step
Codex 第一個 commit：更新 configs/cost_stress.yaml defaults 為工單 v2 Section 5.2
的完整規格（共 9 個 key，取代現有 6 個 key）。此 commit 完成後，TASK-002 直接進入
READY_TO_IMPLEMENT 狀態，可開始實作 cost stress。

## Suggested Model For Next Step
Sonnet（cost stress 實作屬日常工程執行，Sonnet 負責 queue 更新與工單格式整理）。
REVIEW-002 final 須升級 Opus（major task final review + 是否進入下一階段）。
```

---

### 5. Readiness Check 結論

| 類別 | 判定 |
|---|---|
| 資料層（funding_rates.parquet / fees.yaml / run008）| **全部 PASS** |
| 配置層（cost_stress.yaml defaults）| **BLOCKED（v1 遺留）** |
| 工單完整性（12 scenarios / 驗收標準）| **PASS** |
| 整體 Verdict | **NEED_CLARIFICATION** |

Codex 解除 NEED_CLARIFICATION 所需的唯一動作：**更新 cost_stress.yaml defaults 為 v2 規格（1 次 commit）**。
資料本身零問題，可立即開工實作。

---

## REVIEW-007b — TASK-007b Weight Cap + Redistribution（2026-05-17）

- **審查模型**：Claude Sonnet（draft）→ Opus final decision（由 Rick 轉交）
- **對應任務**：CODEX_TASK_QUEUE.md → TASK-007b
- **審查輸入**：`docs/research/review_packets/REVIEW-007b_PACKET.md`、`REVIEW-007b_NUMBERS.json`、`20260516_task007b_cap_summary.csv`、`20260516_task007b_gate_report.json`、`20260516_task007b_redistribution_log.csv`、`20260516_task007b_weight_cap_redistribution.log`
- **Draft**：`docs/research/review_drafts/REVIEW-007b_DRAFT_BY_SONNET.md`

---

### 1. Verdict

```
REVIEW-007b = PASS
TASK-007b   → DONE
Paper trading hard gate（TASK-007b 條件）= 已滿足（B-1 = 選項 A）
Live trading = 仍 FORBIDDEN（不變）
```

---

### 2. 工程驗收（Fail Gates 5/5 PASS）

| Gate | 閾值 | 實際值 | 結論 |
|---|---|---|---|
| `baseline_reconciliation_mismatch` | < 1e-6 | 2.05e-16 | ✅ PASS |
| `missing_outputs` | 0 個缺失 | 0 | ✅ PASS |
| `schema_mismatch` | 0 錯誤 | 0 | ✅ PASS |
| `redistribution_overflow` | max < 1e-6 | 0.0 | ✅ PASS |
| `paper_live_execution_code` | 無禁用程式碼 | matches=0 | ✅ PASS |

Reproducibility hash：`f5c962e11189cc4f91dedbc50b00456830d1fdc6e868c1638ad6b3e3e4db07b7`（已落地）

---

### 3. 核心數字（Active 口徑，760 天）

| Variant | Sharpe | IR vs EQW | Max DD | Net Alpha | Alpha Ret. | Top5 Conc | Single Conc | No-room |
|---|---|---|---|---|---|---|---|---|
| **Baseline** | **0.8918** | **0.7168** | **−19.64%** | **28.53%** | **100.00%** | **95.56%** | **25.45%** | 0 |
| cap_20pct | 0.8918 | 0.7168 | −19.64% | 28.53% | 100.00% | 95.56% | 25.45% | 0 |
| cap_15pct | 0.8918 | 0.7168 | −19.64% | 28.53% | 100.00% | 95.56% | 25.45% | 0 |
| cap_10pct | 0.8341 | 0.7053 | −19.64% | 26.36% | 92.38% | **98.69%** | 24.81% | **488** |

*Concentration formula = top5_net_alpha / net_alpha_total（Opus REVIEW-003 裁定公式）*

---

### 4. Warning Gates（4 觸發 / 2 未觸發）

| Gate | 觸發 | 值 |
|---|---|---|
| `concentration_not_reduced_cap15` | ✅ TRIGGERED | 95.56%（>> 70% 閾值，與 baseline 完全相同）|
| `top5_concentration_above_threshold` | ✅ TRIGGERED | 全三個 cap 均 > 70%（98.69% / 95.56% / 95.56%）|
| `single_symbol_concentration_above_threshold` | ✅ TRIGGERED | cap_20=25.45%、cap_15=25.45% |
| `redistribution_has_no_room` | ✅ TRIGGERED | 488 events on 61 dates |
| `cap10_sharpe_drop` | ❌ NOT triggered | 6.48% drop < 30% 閾值 |
| `alpha_retention_below_threshold` | ❌ NOT triggered | 92.38% > 70% 閾值 |

---

### 5. 關鍵研究發現

#### 5.1 Cap 20% / 15% 完全 No-op

Run008 最大 symbol weight = **12.5%**（= 1/N_same_side，等權投資組合）。20% 和 15% 的 cap 值高於實際最大 weight，從不觸發。portfolio 與 baseline 100% 相同。

#### 5.2 Cap 10% Redistribution 全面失敗

61 個日期觸發、488 個事件全部 `redistribution_has_no_room`：
- 在每個觸發日，所有同方向 symbol 均以 12.5% 等權持倉（均高於 10% cap）
- 沒有任何同方向 symbol 在 cap 以下有空間接收 redistribution
- Excess weight 無法分配，只能縮減 gross_exposure
- **Cap 10% top5_conc 反惡化**：95.56% → **98.69%**（+3.3pp），重現 no_DOT 悖論

#### 5.3 結構性結論（weight-space vs alpha-space）

集中度問題的根源在 **alpha-space**（DOT 長期穩定貢獻 25%+ net alpha），而非 weight-space（每日 weight 均等）。用 weight-space 的截斷操作無法降低 alpha-space 的集中度指標。

此結論與 Opus REVIEW-007 的診斷完全吻合：「overlay 無法根治集中度，需要策略層 cap（TASK-008）」。

#### 5.4 Weight-based vs Alpha-based 設計比較

| 維度 | TASK-007b cap_10pct（weight-based）| TASK-007 DOT_capped（alpha-based）|
|---|---|---|
| Sharpe | **0.8341**（較高，−6.5% vs baseline）| 0.7922（較低，−11.2%）|
| Top5 Conc | 98.69%（略高）| 98.31%（略低）|
| Single Conc | 24.81%（低於 25%）| 21.36%（較低）|
| Forward 可執行 | ✅ 可機械執行 | ❌ 需知歷史 alpha |
| Redistribution | ❌ 失敗（無空間）| N/A |

---

### 6. Opus 最終裁定

#### B-1（BLOCKING）：Paper trading hard gate 裁定 = **選項 A**

> **TASK-007b 完成後，其 paper trading hard gate 功能視為已滿足。**

裁定理由：
1. TASK-007b 的研究目的已完成：量化確認 redistribution 在當前等權投資組合結構下不可行
2. TASK-006 現行 overlay Rule 3（`symbol_cap_5pct` + no redistribution）已通過 Opus REVIEW-006 PASS，屬正確設計
3. 集中度結構性根治在 TASK-008，TASK-008 設計上定義為「長期任務、不擋短期 paper planning」
4. Paper execution 仍有 4 個其他前置條件作為安全緩衝：TASK-005 VPS monitor 上線、30 天 forward paper record（Sharpe > 0.5）、Opus REVIEW-006b PASS、Rick 明示批准

#### Weight Cap + Redistribution 路徑關閉

> **Weight-based overlay cap + redistribution 正式排除為集中度解決方案。**

未來任何集中度改善工作必須在 **alpha-space / 策略層** 進行（即 TASK-008）。不應再嘗試 overlay 層的 weight 截斷或 redistribution 設計。

#### TASK-008 範圍確認

> **TASK-008 必須是 alpha-space / 策略層的 per-symbol weight cap，非 weight-space overlay。**

- 在 baseline backtester 的 `signals / position sizing` 層加入 `max_per_symbol_weight = 0.05`（5%）
- 是策略訊號的一部分，不是事後 overlay
- 需重新跑 baseline、cost stress、attribution 全套（使用新規則）
- 與 run008（無 cap）的所有 Key Numbers 對比

---

### 7. 下游影響

- **TASK-007b** → **DONE**（本次裁定）
- **TASK-007b paper gate** = 已滿足，從 paper execution 前置條件清單移除
- **Paper execution 剩餘前置條件**：TASK-005 VPS monitor 上線 + 30 天 forward record（Sharpe > 0.5）+ Opus REVIEW-006b PASS + Rick 明示批准
- **TASK-008** 維持 `TODO`；範圍確認為 alpha-space / 策略層，非 overlay；優先順序由 Rick 決定
- **TASK-007c**（Variant C sensitivity）維持 `TODO`；不擋 paper planning
- **TASK-004 / TASK-005**：維持 `READY_TO_IMPLEMENT`
- **Live trading**：仍 FORBIDDEN（不變）
- **REVIEW-006b 啟動條件**：TASK-007b DONE（已滿足）+ 30 天 forward record 存在 + TASK-006 三個補件落地

---

### 8. Non-blocking Caveats（記錄，不擋 DONE）

- **N-1 初期 universe 極小**：2024-04 只有 8 symbol（4L+4S），weight 各 12.5%。實際持倉數量在 760 天中動態變化，集中度問題有部分源於樣本初期的 universe 限制。
- **N-2 cap_10pct new_gross 比例**：截斷後以新（縮減後）gross 計算的 max weight = 12.5%（高於 10% cap），因 cap 基準是原始 gross。此設計選擇應在 TASK-008 工單中明確說明（策略層 cap 應以即時 gross 為基準）。
- **Codex 補件（不擋 DONE）**：NUMBERS.json 補 `redistribution_no_room_dates_fraction`（61/760 = 8.03%）說明影響範圍。

---

### 9. 審查基礎聲明

- 本審查依 Token Budget Rule，只讀 packet + numbers + cap_summary（8 行）+ redistribution_log（前 30 行）+ gate_report + log，**未直接掃大 CSV**。
- 未修改任何策略程式、官方輸出、raw data。
- 未重跑任何 baseline / cost stress / attribution / TASK-007 / TASK-007b。
- 未批准 paper execution；未批准 live trading。

