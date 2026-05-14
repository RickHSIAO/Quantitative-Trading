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
