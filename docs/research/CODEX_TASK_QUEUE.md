# Codex Task Queue

最後更新：2026-05-12
維護者：Claude（任務卡撰寫） / Rick（核可）
狀態圖例：`TODO` / `IN_PROGRESS` / `REVIEW` / `BLOCKED` / `DONE`

> **給 Codex 的全域守則**
> 1. 一次只做一個任務，做完進 `REVIEW`，**不可** 自行轉 `DONE`。
> 2. 嚴格遵守每張卡的「輸入檔案」「輸出檔案」「禁止修改範圍」。
> 3. 任何超出任務範圍的修改，先停手 → 在卡片下方留 `NOTE` → 等 Claude 或 Rick 回覆。
> 4. 產出的 CSV / parquet 一律附 schema（欄位名、型別、單位）。
> 5. 沒有 Claude 審查通過前，不要把實驗分支 merge 回 main。
> 6. 目前 repo 是空的（只有 `src/__init__.py`），所列「規劃路徑」由 Codex 建立；建立時請保持模組化、不要把所有東西塞進一個檔。

---

## TASK-001 — Prev3Y Crypto Universe 測試

- **狀態**：REVIEW
- **Owner**：Codex
- **預估**：M（2–3 天）
- **依賴**：無（這是第一棒）

### 任務目的
把現有的 Prev3Y momentum 想法搬到 crypto universe 上，做一次乾淨的 baseline 回測，產出 IR / Sharpe / max DD / turnover 等基本統計，作為後續一切研究的對照組。

### 為什麼重要
- 目前所有「Prev3Y 在 crypto 上會 work」的說法都還是假設，沒有實證。
- 這個 baseline 一旦建立，後面的 cost stress、attribution、dashboard 才有意義。
- 如果這一步就 fail，後面四個任務的優先順序要重新討論，省下大量工程時間。

### 輸入檔案（規劃路徑，由 Codex 建立）
- `data/crypto/prices_daily.parquet`：日線 OHLCV，欄位至少 `[date, symbol, open, high, low, close, volume, quote_volume]`，UTC，已調整。
- `data/crypto/universe_membership.parquet`：每日 universe 名單（**point-in-time**，禁止用「目前還活著」的清單反推歷史）。
- `configs/prev3y_crypto.yaml`：回測參數（lookback、rebalance freq、top-N、ranking method）。

### 輸出檔案
- `outputs/backtests/prev3y_crypto/<YYYYMMDD>_baseline.csv`
  欄位：`date, portfolio_return, benchmark_return, gross_exposure, net_exposure, turnover, n_longs, n_shorts`
- `outputs/backtests/prev3y_crypto/<YYYYMMDD>_positions.parquet`
  欄位：`date, symbol, weight, signal_rank`
- `outputs/backtests/prev3y_crypto/<YYYYMMDD>_stats.json`
  欄位：`ir, sharpe, sortino, max_dd, calmar, turnover_annual, hit_rate, exposure_stats`
- `outputs/logs/prev3y_crypto/<YYYYMMDD>.log`

### 驗收標準
- [ ] 回測期間至少涵蓋 2019-01 ~ 最近一個完整月，且開頭明確標出 warm-up 起點。
- [ ] universe 為 point-in-time，**任何時點的 symbol 集合不得包含當天還未上市或已下市的幣**。
- [ ] 訊號使用 t–1 收盤之前的資料，t 收盤計算 weight，t+1 開盤（或 t+1 收盤，依 config）進場；不可有 `pct_change().shift(0)` 之類的對齊錯誤。
- [ ] CSV 每一列的時間戳唯一，無跳日（停盤日明確處理）。
- [ ] `stats.json` 的 IR / Sharpe 必須可由 CSV 重新計算重現（±1e-6）。
- [ ] log 開頭印出：random seed、config hash、data snapshot hash、git commit。

### 禁止修改範圍
- 不可動 `data/` 內既有 raw 檔（如已存在）。所有衍生資料寫在 `data/derived/` 或 `outputs/`。
- 不可在這支任務裡引入 cost、funding、slippage（那是 TASK-002）。
- 不可改 `configs/prev3y_crypto.yaml` 以外的設定檔。

### Codex 完成後請回報
- baseline 跑出來的 4 個關鍵數字：IR、Sharpe、max DD、年化 turnover。
- 你有沒有遇到「資料缺漏 / 異常值 / universe 不一致」的地方，列出清單。

### Codex 交付摘要（2026-05-13）
- 輸出：`outputs/backtests/prev3y_crypto/20260513_baseline.csv`、`20260513_positions.parquet`、`20260513_stats.json`、`outputs/logs/prev3y_crypto/20260513.log`。
- 關鍵數字：IR `-0.052954`、Sharpe `0.517207`、max DD `-19.4996%`、annual turnover `1.228343x`。
- 樣本：baseline CSV 覆蓋 `2019-01-01` 至 `2026-04-30`，warm-up `2018-01-01`；本地 Bybit price coverage 從 `2020-10-21` 開始，第一個有效持倉日為 `2024-04-01`。
- 可重現性：同一 config/data snapshot 內部重跑兩次，`stats.json` hash 皆為 `02bfeffd2b7f84f456566d2c605e2683a65d3fc316f8410a456e9714fdcbf87c`。
- NOTE: data source = `data/trading.db` 的 `prices`、`crypto_market_cap_rankings`、`crypto_bybit_linear_instruments`；`quote_volume` 由 `close * volume` 衍生。

---

## TASK-002 — Funding / Cost Stress Test

- **狀態**：TODO
- **Owner**：Codex
- **預估**：M（2–3 天）
- **依賴**：TASK-001 必須先 `REVIEW` 通過

### 任務目的
在 TASK-001 baseline 之上，加入交易成本 / funding rate / 滑點，做多情境壓力測試，找出策略「在多悲觀的假設下還活著」的邊界。

### 為什麼重要
- Crypto perp 的 funding 在牛市末段可以年化吃掉幾十個百分點；只看 gross PnL 會嚴重高估策略。
- 真實上線前必須知道：在 fee × 2、funding × 1.5、滑點翻倍的情境下，IR 還剩多少。
- 這是區分「論文型 alpha」與「能上線的 alpha」的關鍵 gate。

### 輸入檔案（規劃路徑）
- TASK-001 的 `positions.parquet` 與 `baseline.csv`。
- `data/crypto/funding_rates.parquet`：欄位 `[timestamp, symbol, funding_rate, interval]`。
- `data/crypto/fees.yaml`：maker / taker fee，可分交易所。
- `configs/cost_stress.yaml`：定義 N 個情境（例如 base / pessimistic / extreme）。

### 輸出檔案
- `outputs/backtests/prev3y_crypto/<YYYYMMDD>_cost_stress.csv`
  欄位：`date, scenario, portfolio_return_gross, portfolio_return_net, fee_cost, funding_cost, slippage_cost`
- `outputs/backtests/prev3y_crypto/<YYYYMMDD>_cost_stress_summary.json`
  每個情境一組：`ir, sharpe, max_dd, annual_cost_bps_breakdown`
- `outputs/logs/prev3y_crypto/<YYYYMMDD>_cost_stress.log`

### 驗收標準
- [ ] 至少 3 個情境：`base`（實際 fee + 實際 funding）、`pessimistic`（fee × 2、funding × 1.5、滑點 × 2）、`extreme`（fee × 3、funding × 2、滑點 × 3）。
- [ ] funding 必須以 **持倉時間段內** 的 funding 結算次數加總，不能只取月末快照。
- [ ] fee 同時涵蓋進場與出場（包含 rebalance 中的雙邊）。
- [ ] 任一情境下若年化淨 IR < 0.3，必須在 summary 內顯眼標記 `WARNING`。
- [ ] `cost_stress.csv` 的 `portfolio_return_net = gross − fee − funding − slippage`，每列須能逐項對得回去。

### 禁止修改範圍
- 不可改動 TASK-001 產出的任何檔案。
- 不可動策略訊號邏輯（這支任務只加 cost layer）。
- 不可把 cost model 寫死進 strategy module，要獨立成 `costs/` 模組。

---

## TASK-003 — Baseline Attribution

- **狀態**：TODO
- **Owner**：Codex
- **預估**：S–M（1–2 天）
- **依賴**：TASK-001 通過；TASK-002 可平行

### 任務目的
把 TASK-001 baseline 的 PnL 拆解成幾個解釋來源：market beta、size / liquidity factor、sector（如有）、idiosyncratic。輸出標準格式的 attribution 表。

### 為什麼重要
- 沒有 attribution 就無法判斷「這是真 alpha 還是隱性 beta」。
- 之後若 Claude 在審查中懷疑「策略只是長期 long BTC」，可以用這份表直接證偽 / 證實。
- Attribution 是和 ChatGPT 討論方向時最有用的素材。

### 輸入檔案（規劃路徑）
- TASK-001 的 `positions.parquet`、`baseline.csv`。
- `data/crypto/factor_returns.parquet`：欄位 `[date, factor_name, return]`，至少含 `market, size, liquidity, momentum_short`。

### 輸出檔案
- `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution.csv`
  欄位：`date, total_return, market_contrib, size_contrib, liquidity_contrib, mom_short_contrib, residual`
- `outputs/attribution/prev3y_crypto/<YYYYMMDD>_attribution_summary.json`
  欄位：`r2, avg_beta_market, avg_beta_size, ..., residual_sharpe`
- `outputs/logs/prev3y_crypto/<YYYYMMDD>_attribution.log`

### 驗收標準
- [ ] 對 daily portfolio return 做 rolling regression（window 至少 90 天）以及 full-sample regression，兩份都產出。
- [ ] `total_return = sum(*_contrib) + residual`，每列誤差 < 1e-8。
- [ ] residual 不可顯示出明顯季節 / 月份 pattern（若有，log 警告）。
- [ ] regression 樣本內 R² 在 summary.json 明確記錄。
- [ ] 若 market beta 的 t-stat > 5 且持續存在，標 `WARNING: high market beta — alpha 可能不純`。

### 禁止修改範圍
- 不可改 TASK-001、TASK-002 的輸出。
- 不可把 factor 計算寫進策略模組（attribution 屬於分析層，不是策略層）。

---

## TASK-004 — Quant Cowork Lab Dashboard

- **狀態**：TODO
- **Owner**：Codex
- **預估**：M（3–4 天）
- **依賴**：TASK-001 通過後可開始；TASK-002 / 003 結果出來後再加面板

### 任務目的
建一個輕量化 web dashboard，集中顯示目前各策略的 baseline 績效、cost 情境、attribution、近期變化，作為 Rick 每日早上的「Cowork Lab 首頁」。

### 為什麼重要
- 目前所有結果都散在 CSV / parquet，每次要看都要手動跑 notebook。
- 有了 dashboard，Rick 一眼能看出「昨天 funding 突然惡化」「最近殘差變大」等異常。
- 也讓 Claude 在審查時可以直接從同一個介面截圖貼回 review。

### 輸入檔案（規劃路徑）
- TASK-001 / 002 / 003 的所有輸出檔。
- `configs/dashboard.yaml`：顯示哪些策略、哪些情境、要不要顯示 attribution 面板。

### 輸出檔案
- `apps/dashboard/`（新模組）：含 `app.py`、`components/`、`README.md`。
  建議用 Streamlit 或 FastAPI + 靜態 HTML；不要用重量級框架。
- `outputs/dashboard/screenshots/<YYYYMMDD>_home.png`（Codex 跑一次本機並截圖貼回 review）。

### 驗收標準
- [ ] 啟動命令一行：`make dashboard` 或 `python -m apps.dashboard`。
- [ ] 首頁四個區塊：(a) baseline 績效、(b) cost stress 情境比較、(c) attribution、(d) 最近 30 天每日 PnL。
- [ ] 讀資料時帶 cache，並在頁面顯示「資料 snapshot 時間」。
- [ ] 不直接重新跑回測——只讀 CSV / parquet。
- [ ] 切換策略 / 情境的下拉選單可運作。
- [ ] README 寫明 dependency、本機跑法、與 VPS 上跑的差異。

### 禁止修改範圍
- 不可在 dashboard 內計算新策略指標（只顯示既有產出）。
- 不可把 dashboard 模組和策略模組互相 import（單向：dashboard 依賴 outputs，不依賴 strategies code）。
- 不可加任何會寫入 `outputs/` 的功能（dashboard 是唯讀的）。

---

## TASK-005 — VPS Bot Monitor

- **狀態**：TODO
- **Owner**：Codex
- **預估**：M（3–5 天）
- **依賴**：可獨立進行；之後會和 Ollama 串接做 log 摘要

### 任務目的
為跑在 VPS 上的 trading bot 建一個監控層：心跳檢查、最近一次下單時間、PnL daily delta、錯誤 log 收集，並在出狀況時推播通知。

### 為什麼重要
- 真錢上線後，最致命的不是策略爛，而是「bot 掛了沒人知道」「API key 失效」「斷網 6 小時」。
- 監控層必須在策略還沒上線前就準備好；事後補做容易留洞。
- 之後 Ollama 可以幫忙摘要每天的 log，讓 Rick 不用每天看一萬行。

### 輸入檔案（規劃路徑）
- VPS 上 bot 寫出的 log：`/var/log/quantbot/*.log`（或同等路徑）。
- 交易所 API 帳號（**只讀 key**，禁止使用可下單的 key 做監控）。
- `configs/monitor.yaml`：心跳 interval、告警閾值、通知 channel。

### 輸出檔案
- `apps/monitor/`：含 `monitor.py`、`alerts.py`、`README.md`。
- `outputs/monitor/heartbeat.parquet`：欄位 `[timestamp, bot_id, status, latency_ms, last_order_time, equity, notes]`。
- `outputs/monitor/alerts/<YYYYMMDD>.jsonl`：每筆告警一行。

### 驗收標準
- [ ] 心跳檢查 ≥ 每 1 分鐘一次，連續 3 次失敗觸發 `CRITICAL` 告警。
- [ ] 偵測「最近 N 分鐘無下單但應有下單」的情境（N 由 config 決定）。
- [ ] 通知至少支援 1 個 channel（Telegram / Discord / Email 擇一），可擴充。
- [ ] 任何告警都有 dedupe（同類問題 30 分鐘內不重複通知）。
- [ ] 不會記錄完整 API key、不會把使用者帳號明碼寫入 log。
- [ ] README 列出：所需權限、failure mode、如何手動關閉。

### 禁止修改範圍
- 不可讓 monitor 取得 **可下單 key**（只准用 read-only / IP-whitelisted key）。
- 不可改 bot 本身的下單邏輯（monitor 是旁觀者）。
- 不可把 monitor 直接寫進策略 repo 的核心模組，獨立成 `apps/monitor/`。

---

## 補充：未進 queue 的想法（暫存區）

> Claude 暫存，等 Rick 點頭再轉成正式任務卡。

- TASK-? 多 universe 比較（spot vs perp、tier1 vs tier2）。
- TASK-? 因子腐化（factor decay）追蹤儀表。
- TASK-? 把 Notion 研究紀錄自動回灌 repo 的 docs。
- TASK-? Walk-forward / purged k-fold 框架。
