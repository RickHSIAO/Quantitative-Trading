# 量化交易系統

## ⚠️ 績效解讀規範（v1.13 後）

任何績效數字都要附上「**範圍 + 期間**」才有意義。本專案用 silo 切資金池，
不同 `--profile` 跑法的數字尺度完全不同，跨範圍對比沒意義。

| 範圍 | 起始資金 | OOS 2y 真實基準 |
|---|---|---|
| `--profile Crypto`（單 silo） | $10k | **+87.17% / 年化 36% / Sharpe 0.93 / PF 1.35** |
| 預設多 silo（Crypto+TW+US+Comm） | $30k | +30.82% / PF 1.25（被 TW/US 拖累） |

**任何新策略改動，必須以 walk-forward OOS 績效是否提升為準**，不能只看連續回測或 IS 數字。

---

## Demo Trading Guarded Lifecycle Status（updated by TASK-014AM-DOCS1, 2026-06-12）

共同狀態板，供 Rick / ChatGPT / Claude / Codex / Opus 三方協作對齊。本區塊由
TASK-014AM-DOCS1 同步更新；不改任何 execution logic、不解除 G20、不開啟 real trading。

| 欄位 | 值 |
|---|---|
| latest_completed_task | TASK-014AM |
| latest_commit | `fdf46df` — `TASK-014AM: add guarded entry real execution manual approval gate`（local；尚未推遠端） |
| current_phase | guarded entry real execution manual approval gate completed（manual-approval-gate-only，EXACT_APPROVAL_PHRASE + 12 REQUIRED_MANUAL_APPROVAL_INPUTS never validated，無實單，無 sender，no auto-git） |
| next_required_task | `TASK-014AN_guarded_entry_real_execution_adapter_design` |
| real_execution_allowed | **False** |
| actual tiny entry | **FORBIDDEN** |
| actual stop attach | **FORBIDDEN** |
| actual cleanup | **FORBIDDEN** |
| live trading | **FORBIDDEN** |
| G20 sender policy | **still active**（無 sender adapter，無 `/v5/order/create`，無 `/v5/position/trading-stop` 真實呼叫） |
| latest validation | `pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py` → 114 PASS |
| protected positions（never touched） | ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT |
| authorization token pattern | `CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT`（documented only — NEVER validated） |
| exact approval phrase | `I AUTHORIZE DEMO TINY ENTRY GATE ONLY FOR SOLUSDT BUY 0.1 MAX 10 USDT; NO ORDER MAY BE SENT BY TASK-014AM`（documented only — NEVER compared） |
| audit response_status | `APPROVAL_GATE_NOT_SENT`（無任何 outbound request） |

權威來源（authoritative pointers — 任何不一致以下列檔案為準）：

- [docs/research/commands/NEXT_ACTION.md](docs/research/commands/NEXT_ACTION.md) — 下一步 Rick action、各 TASK-014X 詳細狀態
- [docs/research/commands/COMMAND_LOG.md](docs/research/commands/COMMAND_LOG.md) — 完整 task 紀錄、驗證輸出、檔案改動

提醒（避免三方協作誤觸）：

1. 任何 dry-run adapter（AE / AF / AG / 後續 AH…）皆**不**呼叫 endpoint、**不**讀 secrets、**不**簽 HMAC。
2. `--allow-real-*-execution` 是 guard probe；source 內部一律回 `REAL_*_EXECUTION_NOT_IMPLEMENTED`，
   不會升級為 real trading。
3. 升級為 real execution 必須由 Rick 在 `NEXT_ACTION.md` 顯式授權，**不**可由 agent 自動推進。
4. `main.py` / `src/risk.py` / `BybitExecutor` / G20 sender policy 在整個 TASK-014 sequential safety chain 中持續未被修改。

---

## TASK-001 Prev3Y Crypto Baseline（2026-05-13）

本次建立獨立 Prev3Y momentum baseline pipeline，不改現有 live strategy、不加 cost / funding / slippage。

輸出檔案：

- `outputs/backtests/prev3y_crypto/20260513_baseline.csv`
- `outputs/backtests/prev3y_crypto/20260513_positions.parquet`
- `outputs/backtests/prev3y_crypto/20260513_stats.json`
- `outputs/logs/prev3y_crypto/20260513.log`
- Final non-overwriting rerun: `outputs/backtests/prev3y_crypto/20260513_run002_baseline.csv`,
  `20260513_run002_positions.parquet`, `20260513_run002_stats.json`,
  `outputs/logs/prev3y_crypto/20260513_run002.log`
- TASK-001c reporting supplement: `outputs/backtests/prev3y_crypto/20260513_run003_stats.json`
- TASK-001b benchmark supplement: `outputs/backtests/prev3y_crypto/20260513_run004_baseline.csv`,
  `20260513_run004_positions.parquet`, `20260513_run004_stats.json`,
  `outputs/logs/prev3y_crypto/20260513_run004.log`
- TASK-001d missing-data supplement: `outputs/backtests/prev3y_crypto/20260513_run007_baseline.csv`,
  `20260513_run007_positions.parquet`, `20260513_run007_stats.json`,
  `outputs/logs/prev3y_crypto/20260513_run007.log`,
  `outputs/data_quality/prev3y_crypto/20260513_run007_data_quality_summary.csv`,
  `outputs/data_quality/prev3y_crypto/20260513_run007_data_quality_aggregate.json`

關鍵結果：

| IR | Sharpe | max DD | annual turnover |
|---:|---:|---:|---:|
| -0.061757 | 0.493574 | -19.4996% | 1.228343x |

樣本與資料：

- Baseline CSV 覆蓋 `2019-01-01` 至 `2026-04-30`；warm-up 起點 `2018-01-01`。
- 本地 Bybit OHLCV coverage 從 `2020-10-21` 開始；3 年 lookback 後，第一個有效持倉日為 `2024-04-01`。
- PIT universe 來源是本機 `data/trading.db`：`prices`、`crypto_market_cap_rankings`、`crypto_bybit_linear_instruments`。
- 平均 universe size：全樣本 76.79；rebalance eligible tradable symbols 平均 15.22。
- Benchmark：TASK-001b 起 primary benchmark 為 cash；`benchmark_return = benchmark_cash_return`。
  `benchmark_eqw_return` 保留舊版 run003 的「同日 PIT universe 等權 long-only」benchmark，缺 return 的 symbol 當日剔除。
  `benchmark_btc_return` 使用 `BYBIT:BTCUSDT.P` open-to-open return；BTC 缺資料日期保留 NaN，不補 0。
- `stats.json` 可由 `baseline.csv` 重算重現，誤差小於 `1e-12`；同一 config/data snapshot 內部雙跑 stats hash 相同。

TASK-001b benchmark IR（run004）：

| benchmark | full IR | active IR |
|---|---:|---:|
| cash | 0.493574 | 0.926682 |
| BTC perp (`BYBIT:BTCUSDT.P`) | -0.324759 | -0.017486 |
| PIT equal-weight long-only | -0.061757 | 0.722657 |

Coverage：BTC return 覆蓋 `2021-03-03` 至 `2026-04-30`；full period 缺 `793` 天，active period 缺 `0` 天。Equal-weight benchmark 平均可用 symbols `76.748226`、最小 `0`、缺 benchmark symbols 天數 `660`。

TASK-001d data-quality policy：missing return 不補 0；nonpositive OHLC 不補值；不 forward fill price；volume <= 0 只記 warning；missing volume / quote_volume hard exclusion。run007 DQ 摘要：abnormal symbol-days `332`、holding exclusions `115`、ranking exclusions `0`、forced holding exits `0`；COMP-USD / ICP-USD 已標記。run007 vs run004 的 portfolio_return、exposure、turnover、positions 均相同。

重現指令：

```powershell
python scripts\validate_prev3y_crypto_inputs.py
python scripts\run_prev3y_crypto_baseline.py
```

注意：baseline runner 只接受已存在且 schema 正確的 parquet/config；缺資料時會以 `BLOCKED_BY_DATA` 停止，不會產生隨機或模擬資料。同日正式輸出檔已存在時，腳本會使用 `YYYYMMDD_run001`、`run002` 這類 stem，不會覆寫既有結果。

---

## Current Crypto Status（2026-05-08）

目前有兩套需要分清楚：

| 指令 / 策略 | 狀態 | 用途 |
|---|---|---|
| `python main.py live` | **正式預設策略** | 已切換為 `volume-top125-lb3-sym035`：前三年平均 `volume_24h` Top125 + symbol WR 0.35 |
| `python main.py live --crypto-candidate config-baseline` | **舊 baseline** | 對應曾跑出 5y full `+627%` 的 config universe 邏輯；保留作對照，不再是預設 live 策略 |
| `python main.py live --crypto-candidate volume-top125-lb3-sym035` | **顯式指定新策略** | 與預設 `python main.py live` 相同；仍需繼續 forward / demo 監控 |

重要判斷：

- `+627.44%` 5 年連續回測不是 look-ahead bug，但很可能包含 current-universe selection bias 與 path-dependency；**不可作為未來預期報酬**。
- 現有 baseline 較可信的參考仍是 Crypto-only OOS：`+87.17% / CAGR 36.49% / PF 1.346 / Sharpe 0.930 / MDD -43.01%`。
- Point-in-time-like universe 測試顯示市值 Top100 raw OOS 只剩 `+7.25% / PF 1.030 / Sharpe 0.289`，確認原 config universe 有高估疑慮。
- 目前最合理的 forward 候選是 `volume-top125-lb3-sym035`：
  - Universe：previous 3-year average `volume_24h` Top125
  - Symbol rolling winrate threshold：`0.35`
  - OOS backtest：`+99.43% / CAGR 40.86% / PF 1.291 / Sharpe 1.012 / MDD -36.57%`
  - 但 lookback 視窗仍敏感，因此雖已切成預設策略，仍必須用 forward monitor 監控是否保留。

Forward monitor:

```powershell
# 純監控，不下單
python scripts\crypto_top100_forward_monitor.py

# 透過 Main 跑候選回測
python main.py backtest --profile Crypto --crypto-candidate volume-top125-lb3-sym035 `
  --start-date 2026-05-08 --end-date YYYY-MM-DD `
  --output output\crypto_candidate_forward.xlsx --note crypto_candidate_forward

# 透過 Main 跑 Bybit Demo 正式預設策略
python main.py live --interval 15

# 若要切回舊 config baseline 對照
python main.py live --crypto-candidate config-baseline --interval 15
```

Forward gate：至少 `90` 天或 `50` 筆 forward trades，且 PF >= `1.15`、Sharpe >= `0.70`、MDD 不差於 `-40%` 才保留為正式預設；若未通過就切回舊 baseline 或進入新一輪研究。

---

## 研究紀錄與最新判決（EXP-001 ~ EXP-012）

研究文件已集中到 `docs/research/`：

- [`TEST_PLAN.md`](docs/research/TEST_PLAN.md)：接下來要做的實驗、通過標準、失敗判斷。
- [`EXPERIMENT_LOG.md`](docs/research/EXPERIMENT_LOG.md)：每次測試的完整紀錄與結論。
- [`experiment_results.csv`](docs/research/experiment_results.csv)：可排序、統計、畫圖的結構化結果。

固定研究規則：

1. 每次實驗必須寫清楚「沒改什麼」。
2. 每次實驗必須先定義通過標準。
3. 結論只能寫：`保留` / `淘汰` / `需要更多測試`。

### 已完成實驗

| 實驗 | 主題 | 結論 | 關鍵發現 |
|---|---|---|---|
| EXP-001 | 成本壓力測試 | 需要更多測試 | TP taker 影響不大；funding 會讓平均 R 轉負，策略邊際偏薄。 |
| EXP-002 | TP-first / SL-first / Conservative K棒路徑 | 需要更多測試 | SL-first 仍 PF > 1.15，但 MDD 惡化到 -53.72%，日 K 路徑假設會影響風險評估。 |
| EXP-003 | 策略 ablation 訊號拆解 | 需要更多測試 | 單一 raw 訊號多數 OOS 失效；baseline 主要靠多模組與風險濾網共同作用。 |
| EXP-004 | Baseline attribution | 需要更多測試 | baseline 正貢獻集中於 Supertrend、TP、15-30 天持倉、BTC above EMA200；短持倉與 SL 拖累明顯。 |
| EXP-005 | Point-in-time Top100 universe | 需要更多測試 | current-biased benchmark 明顯高估；Bybit 補資料後 static PIT 只剩 +52.03%，rolling PIT +37.49%。 |
| EXP-006 | PIT liquidity throttle | 需要更多測試 | 流動性門檻能改善 PIT 結果，但部分結果集中、需分段驗證。 |
| EXP-007 | Prev3Y 市值 Top100 主回測 | 淘汰 | raw Prev3Y market-cap Top100 OOS 只有 +7.25%，PF 1.030，Sharpe 0.289。 |
| EXP-008 | Prev3Y 成交量 Top100 raw | 淘汰 | raw Prev3Y volume Top100 OOS 為 -24.26%，PF 0.907，MDD -57.05%。 |
| EXP-009 | Top100 策略優化 | 需要 forward | volume Top100 + symbol WR off 改善，但 Top100 單點敏感。 |
| EXP-010 | Nested WF + stability overfit check | 需要 forward | `mcap_cap8` 顯示過擬合警訊；`volume_top125_lb3_sym_0.35` 是最佳穩定候選但仍需 forward。 |
| EXP-011 | Top125 volume forward monitor | pending | 候選已接進 `main.py --crypto-candidate`，forward 起點 2026-05-08，等待 90 天或 50 筆交易。 |
| EXP-012 | Top125 candidate stress tests | 需要 forward | 成本壓力大多通過；最嚴格成本組合 Sharpe 降到 0.669。SL-first/conservative 路徑仍有 PF 1.257、Sharpe 0.924。 |
| EXP-013 | Swap default Crypto strategy | forward live | `python main.py live` 已改用 `volume-top125-lb3-sym035`；舊 baseline 用 `--crypto-candidate config-baseline` 指定。 |

### Ablation 初步判斷

- `Symbol rolling winrate`：**保留**。關閉後交易數暴增，OOS PF / Sharpe / Calmar / MDD 全部變差。
- `Geometric RR`：**保留**。關閉後 OOS MDD 破 -50%，平均 R 轉負。
- `Supertrend raw`、`VP POC raw`、`VP + BB`、`Supertrend + EMA score`：**淘汰作為獨立 edge**。
- `Bollinger raw`、`BTC moat`、`baseline 組合`：**需要更多測試**。

下一步：正式預設已切到 `volume-top125-lb3-sym035`，只做 forward / demo 監控，不再用 2024-2026 歷史資料回頭調參。

---

## Latest Local Update: v1.13 — Walk-forward 驗證與 OOS 基準確立

針對 v1.12 candidate 的 +627% 連續回測，做了完整 walk-forward 驗證。

### 1. 先確認沒有 BUG

- ✅ v1.10 的 look-ahead 修正仍在（signal `shift(1)` 在 backtester:282-293）
- ✅ Sharpe 年化因子自動推導仍在（backtester:741-744）
- ✅ `SYM_MIN_WINRATE` 用的 `history_by_sym[sym]` 只含已平倉、point-in-time 正確
- 結論：**+627% 不是 look-ahead 幻覺**，而是 path-dependent 加持下的真實 in-sample 數字

### 2. Crypto-silo Walk-forward（`--profile Crypto`，$10k 起始）

切點 2024-05-01：IS = 2021-03 ~ 2024-04（3 年）/ OOS = 2024-05 ~ 2026-05（2 年）。

| 指標 | IS 3y | **OOS 2y（真實基準）** | 5y full | IS+OOS 複利 |
|---|---:|---:|---:|---:|
| 總報酬 | +229.88% | **+87.17%** | +627.44% | +517.50% |
| 年化 | 45.90% | **36.49%** | 46.71% | — |
| 勝率 | 53.95% | 43.81% | 51.49% | — |
| Profit Factor | 1.533 | **1.346** | 1.546 | — |
| Sharpe | 1.103 | **0.930** | 1.139 | — |
| 最大回撤 | −42.13% | −43.01% | −42.13% | — |
| 交易數 | 291 | 226 (~113/yr) | 470 | — |

**Path-dep gap = +627.44% − +517.50% = +110 pp**。確實存在但不致命；初步以為的 +497 pp 是把多 silo IS/OOS 跟 Crypto-only 5y 混比導致的錯誤。

### 3. 真實可期望基準

- **Crypto silo（1x 槓桿、永續）：年化 ~36% / Sharpe ~0.93 / PF ~1.35 / MDD ~−43%**
- 多 silo 整體：被 TW Stock +2.63% 與 US+Comm −2.54% 拖累，OOS 年化 ~14%
- **WR 從 IS 54% → OOS 44% 退化 10 pp** 是最明顯的 in-sample 過擬合徵兆
- PF 從 1.53 → 1.35 退化 0.19，仍在「可交易」門檻 > 1.3 之上

### 4. 三組 SYM filter 對照（多 silo OOS）

| 設定 | OOS 2y 多 silo | 5y 連續多 silo | Path-dep |
|---|---:|---:|---:|
| **aggressive (3/20)** ✅ | **+30.82%** | ~+209% | 中-大 |
| conservative (30/50) | +23.80% | +346.17% | 中 |
| no filter | +25.17% | +217.07% | ~0 |

OOS 最佳是 aggressive，因此最終保留 (3/20)。conservative (30/50) 雖然 path-dep 較小但 OOS 反而最差 — 過保守把該砍的幣留太久。

### 5. 重現指令

```powershell
# 真實基準（Crypto-only OOS，必跑）
python main.py backtest --profile Crypto `
  --start-date 2024-05-01 --end-date 2026-05-07 `
  --output output\v113_crypto_OOS.xlsx --note v1.13_crypto_OOS

# IS 對照
python main.py backtest --profile Crypto `
  --start-date 2021-03-01 --end-date 2024-04-30 `
  --output output\v113_crypto_IS.xlsx --note v1.13_crypto_IS

# 多 silo 整體
python main.py backtest --start-date 2024-05-01 --end-date 2026-05-07 `
  --output output\v113_multi_OOS.xlsx --note v1.13_multi_OOS
```

### 6. 後續觀察點
- 5y 連續回測 +627% 不是 BUG 但**不可作為宣傳數字**，引用時必須註明「同樣參數 OOS = +87%」
- Sweep 腳本找出的「最佳參數」都是 in-sample，**必須再跑 OOS 驗證**才能採用
- 新流程：propose → IS 跑 → OOS 跑 → rolling OOS 跑 → OOS ≥ 基準且 rolling 不崩 → 才入 main
- US+Commodity silo 在 OOS 仍是負報酬，是結構性議題

### 7. Crypto 優化工具

目前優化以 Crypto OOS 為主基準，IS 只用來篩候選，full 5y 與 rolling OOS 用來擋過擬合。

```powershell
# OOS-first 候選檢查
python scripts\crypto_oos_optimize.py --limit 18 --output output\crypto_oos_optimize_final.csv

# 局部網格：trend stop/RR/score + 風險縮放
python scripts\crypto_oos_optimize.py --local-grid --limit 25 --output output\crypto_oos_optimize_local_grid_risk.csv
```

截至目前測試，沒有新參數通過 robust gate；正式 baseline 仍維持 Crypto OOS +87.17% / CAGR 36.49% / PF 1.346 / Sharpe 0.930 / MDD -43.01%。

---

## v1.11 — Post-fix Re-tuning + 資料修復

承接 v1.10 的 look-ahead 修正，本版做兩件事：
1. 修復 SQLite Volume 欄位 BLOB 汙染（救回 102 個資產）
2. 在 de-biased 引擎上重跑 Crypto sweep，找到新的最佳並行倉位數

### 1. BLOB Volume 資料修復

之前每次回測都看到 `[WARN] XXX: unsupported operand type(s) for +: 'float' and 'bytes'`。
根因：yfinance 偶爾把 Volume 回傳成 numpy bytes，SQLite 動態型別照存為 BLOB；
回讀時整列轉成 object dtype，後續 indicators 加法直接炸。

修復：
- `src/database.py upsert_prices` 寫入前統一 `pd.to_numeric(errors='coerce')`，並逐欄 `float()`
- 對既有 DB 跑 in-place migration：3,352 列 BLOB（8-byte little-endian int64）無損還原為 REAL
- 影響資產：`^GSPC`、`^TWII`、102 檔個股（COIN/HOOD/GE/XAUUSD/...）

修復前回測只跑 30 個資產，修復後跑滿 132 個。

### 2. Crypto sweep 重調 — cap=5 → **cap=4**

v1.9 的 cap=5 是基於 pre-fix biased 回測找的最佳值，post-fix 下不再最佳：

| cap (max_total_positions) | CAGR | 勝率 | PF | MDD |
|---:|---:|---:|---:|---:|
| 3 | +14.97% | 54.1% | 1.26 | −46.6% |
| **4** ✨ | **+17.40%** | **52.3%** | **1.28** | **−44.16%** |
| 5 (v1.9) | +9.96% | 50.5% | 1.15 | −50.94% |

### 3. 與 EMA50 slope filter 的非線性互動

跑 2×2 才發現 cap 與 EMA50 slope 不能各自最佳化疊加：

| 整體總報酬 | slope ON | slope OFF |
|---|---:|---:|
| **cap=5** (v1.9) | +21.78% | +30.52% |
| **cap=4** (v1.11) | **+43.75%** ✨ | +26.27% |

各自最佳的疊加（cap=4 + slope OFF）反而負效，最佳是 **cap=4 + slope ON**：cap 緊讓資金集中在最強訊號，slope filter 補上品質檢查 → 雙重增強。

### 修正後完整對比

| 指標 | v1.9 (pre-fix biased) | v1.10 (post-fix, cap=5) | **v1.11 (cap=4)** |
|---|---:|---:|---:|
| 總報酬 | +148.86%* | +21.78% | **+43.75%** |
| Profit Factor | 1.332* | 1.095 | **1.184** |
| 最大回撤 | −47.11%* | −25.56% | **−23.22%** |
| 勝率 | 50.68%* | 43.81% | **44.0%** |
| 總交易 | 296* | 1081 | 1052 |
| Crypto CAGR | +22.35%* | +9.96% | **+17.40%** |
| Crypto MDD | −47.11%* | −50.94% | **−44.16%** |

\* v1.9 數字未含 102 個 BLOB-failed 資產，僅 Crypto silo 30 檔；其餘為 132 檔全集。

### 已知問題（待後續處理）
- **US+Commodity silo 仍是 −2.54%**（cap/slope 在四種組合下均無顯著改善）— 結構性議題，需單獨檢視該 silo 的訊號 / 出場邏輯
- TW Stock +2.63% 偏低，但有正報酬

### 重現指令

```powershell
python main.py backtest --output output\v111_baseline.xlsx --note v1.11_baseline --ver v1.11
```

---

## Latest Local Update: Bybit Live Ledger Reconciliation (2026-05-11)

Bybit Demo live ledger reconciliation was hardened after exchange-side SL fills were found in Bybit but not reflected in Excel:

- `python main.py live --sync-only` now performs a no-order sync of Bybit positions, closed PnL, SQLite, and `output/Bybit_Live_Orders.xlsx`
- Exchange-side TP/SL closes between scan cycles are backfilled from Bybit closed PnL / execution history and recorded as `REMOTE_CLOSED` or `REMOTE_CLOSED_SL`
- Closed-PnL reconciliation is keyed by Bybit exit order id and matched to known ledger `ENTRY` rows, so older exits are not skipped after newer entry backfills
- Open Bybit positions that are outside the current candidate universe are still added to the live monitoring context, so legacy positions are not silently ignored
- Missing `ENTRY` rows for existing remote positions are backfilled from Bybit execution history, keyed by Bybit order id where available
- The live Excel ledger uses Chinese display labels, is ordered by recorded execution time rather than insertion id, and alternates row colors by trading day
- Live mode re-exports `output/Bybit_Live_Orders.xlsx` at the end of each scan, so closing a locked workbook lets the next scan refresh it automatically

Operational sync command:

```powershell
python main.py live --sync-only
```

Validation run on 2026-05-11:

```powershell
python -m py_compile main.py src\executors\bybit.py src\live_ledger.py
python main.py live --sync-only
```

Runtime artifacts remain untracked by design: `data/trading.db`, `data/*-wal`, `data/*-shm`, `data/live_positions.json`, and `output/Bybit_Live_Orders.xlsx`.

---

## Latest Local Update: Bybit Live Order Ledger (2026-05-10)

Bybit live mode now records successful live order events to both SQLite and Excel:

- SQLite table: `bybit_live_orders` in `data/trading.db`
- Excel ledger: `output/Bybit_Live_Orders.xlsx` (`config.BYBIT_LIVE_ORDER_XLSX`)
- `ENTRY` rows are written after successful Bybit market entries
- `EXIT` rows are written after successful strategy-managed exits
- `REMOTE_CLOSED` exit rows are written when the bot syncs a position that was already closed on Bybit
- Recorded fields include symbol, side, direction, quantity, price, SL/TP, strategy, score, signal date, reason, PnL estimate, fee estimate, balance, Bybit order id, retCode/retMsg, and raw response

Operational notes:

```powershell
python main.py live --interval 15
```

`data/trading.db`, `data/*-wal`, `data/*-shm`, and `output/Bybit_Live_Orders.xlsx` are runtime artifacts. The code creates or refreshes them automatically; Git tracks the recorder code, not the generated ledger data.

---

## Latest Local Update: Bybit Demo Live Hardening (2026-05-09)

Live mode now mirrors the Crypto OOS baseline more closely on Bybit Demo:

- Bybit is still configured as demo trading: `BYBIT_DEMO = True`, `BYBIT_TESTNET = False`
- Bybit leverage is explicitly forced to `1x`: `BYBIT_LEVERAGE = 1`
- Startup logs now print Demo Trading and Testnet separately, so `api-demo.bybit.com` is not confused with Bybit Testnet
- Bybit `set_leverage` treats `ErrCode: 110043 / leverage not modified` as success, including the pybit-wrapped `retCode: -1` form
- Live scans use `include_vp=True`, `apply_cross_asset_filters()`, Crypto score gate, SYM win-rate filter, dominant strategy detection, and geometric R:R checks
- Market entries refresh the Bybit ticker price before sizing and SL/TP calculation; when live price differs from the signal close by 2% or more, the bot logs `[PRICE] ... using live`
- Open-position management also refreshes the Bybit ticker price before SL/TP, trailing-stop, BB target-profit, and PnL checks, so stale daily signal closes cannot trigger false live exits
- After a live non-flip exit (`SL`, `TP`, `BB-*`, `SOFT`, `MAXHOLD`, or exchange-side closed position), the bot skips re-entry on the same daily signal candle and waits for the next daily signal
- Before sending a market order, BybitExecutor validates TP/SL against the current ticker price:
  - long: `SL < live price < TP`
  - short: `TP < live price < SL`
- New entries submit full-position exchange-side TP/SL with `tpslMode='Full'`
- Bybit-side protection remains active if the bot is stopped: fixed SL / fixed TP
- Strategy exits still require `python main.py live` to keep running: signal flip, BB mid/RSI/profit exits, max hold, soft stop, and trailing-stop updates
- `Ctrl+C` during `python main.py live` exits cleanly without a traceback
- Live order logs now print `做多` / `做空` instead of corrupted legacy side labels
- The bot syncs existing Bybit positions on every scan and removes local metadata when a position is already closed
- Position metadata is persisted in `data/live_positions.json`:
  - `entry_dt`, `entry`, `strategy`, `score`, `entry_reason`
  - `orig_sl`, `sl`, `tp`, `trail_anchor`
- Existing Bybit positions opened before the bot starts are recovered as far as possible from Bybit execution history; then the bot infers strategy/score from the nearest historical signal date
- If an existing Demo position has no SL/TP, live mode backfills SL/TP from the current ATR stop formula
- Crypto trailing stop is updated through Bybit `set_trading_stop()`:
  - before +2R: stop trails by `ATR x 3.0`
  - after +2R: stop tightens to `ATR x 1.5`

Run:

```powershell
python main.py live --interval 15
```

---

## v1.10 — Look-ahead Bias 修正與引擎硬化

v1.10 是純 bug-fix release，**沒有改任何策略邏輯或參數**，但回測結果會大幅變動，
因為先前的數字含有 look-ahead bias。修正後的數字才是可實盤複製的真實表現。

### 修正項目

| # | 嚴重度 | 檔案 | 修正內容 |
|---|---|---|---|
| 1 | HIGH | [src/backtester.py](src/backtester.py) | 訊號陣列統一 `shift(1)`：t-1 收盤確認的訊號於 t 進場，消除「同根 K 棒收盤同時偵測 + 進場」的 look-ahead |
| 2 | HIGH | [src/backtester.py](src/backtester.py) | Sharpe 年化因子改由 equity curve 自動推導（crypto 7d/週 → 365；股票 5d/週 → 252），不再寫死 252 |
| 3 | HIGH | [src/fetcher.py](src/fetcher.py) | Bybit kline 起訖時戳改用 UTC（原本用本地時區，台北時區會差 8 小時、邊界日少/多一根） |
| 4 | HIGH | [src/executors/bybit.py](src/executors/bybit.py) | `place_order` 失敗改 `raise OrderRejected`，不再回 `{retCode:-1}` 讓上游靜默忽略 |
| 5 | MED | [src/strategies.py](src/strategies.py) | Supertrend 訊號加入 `prev_dir` 守門，避免暖機期 0 → ±1 假觸發 |
| 6 | MED | [src/indicators.py](src/indicators.py) | Supertrend `direction` 初值改 0 + NaN 期沿用前值，不再預設 +1 |
| 7 | MED | [src/executors/bybit.py](src/executors/bybit.py) | 槓桿自動 clamp 到 instrument `maxLeverage`、qty 大幅截斷時 warn |
| 8 | LOW | [src/database.py](src/database.py) | `load_backtest_history` 的 LIMIT 改參數化 |
| 9 | LOW | [src/backtester.py](src/backtester.py) | CAGR 移除 `max(years, 1)` cap（短週期回測會更如實） |
| 10 | LOW | [src/reporter.py](src/reporter.py) | `_auto_width` 收窄 except 範圍 |

### 修正前 vs 修正後 — 同份資料、同套參數

| 指標 | Pre-fix (run 52) | **Post-fix (run 53)** | Δ |
|---|---:|---:|---:|
| 總報酬 | +148.86% | **+63.42%** | **−85.44 pp** |
| 年化 (CAGR) | +19.27% | **+9.96%** | **−9.31 pp** |
| Sharpe | 0.569 | **0.450** | −0.119 |
| Profit Factor | 1.332 | **1.148** | −0.184 |
| 最大回撤 | −47.11% | **−50.94%** | −3.83 pp |
| 勝率 | 50.68% | 50.51% | −0.17 pp |
| 總交易數 | 296 | 293 | −3 |
| 最佳單筆 | $2,693 | $1,791 | −33.5% |

**為什麼勝率幾乎沒變但報酬腰斬？**
交易方向判斷其實是對的（勝率不動），但舊版用「同根 K 棒收盤」同時偵測訊號 + 進場，
等同偷看當天收盤的價格進場。修正後改成 t-1 訊號 → t 進場：
- 贏單利潤被砍 33.5%（原本人為加大）
- 輸單金額幾乎不變（方向錯時，t vs t+1 的價差有限）
- 結果：PF 1.332 → 1.148

### 重現指令

```powershell
python main.py backtest --output output\post_fix.xlsx --note "post bug fixes"
```

### 提醒
- 之前 `scripts/crypto_sweep*.py` 找出的「最佳參數」是基於 biased 回測，**需重跑調參**
- v1.9 README 內 22.35% / Sharpe 等數字是 pre-fix 結果，請以 v1.10 post-fix 為準

---

## v1.9 Crypto-Specific Tuning

v1.9 在保留 v1.8 silo 架構的前提下，針對 **Crypto silo** 做專屬參數最佳化，
其他 silo（TW Stock / US+Commodity）的參數與績效完全不變。

### Crypto silo 改動清單

新增 [config.py](config.py) 類別特化參數（fallback 至全域值）：

```python
MIN_ENTRY_SCORE_BY_CLASS    = {'Crypto': 3}     # 4→3，放寬進場分數
MAX_HOLD_DAYS_BY_CLASS      = {'Crypto': 30}    # 30 天強制平倉，加速資金回收
TSL_USE_CLOSE_BY_CLASS      = {'Crypto': True}  # TSL 用收盤價追蹤，避影線插針掃出
TSL_TIGHT_AFTER_R_BY_CLASS  = {'Crypto': 2.0}   # 浮盈 ≥ 2R 後 TSL 收緊至 1.5×ATR
```

`STRATEGY_PROFILES['Crypto']` 調整：
- `max_total_positions`：2 → **5**
- `max_position_pct`：0.20 → **0.40**（讓 tight stop 時 Kelly 名目不被 cap 砍）

[src/backtester.py](src/backtester.py) 新增 `_cls_get()` helper，於 4 個熱
路徑點（TSL tight、TSL track、max-hold、min-entry-score）按 `pos.asset_type`
查表；其他類別未列在 `*_BY_CLASS` 字典內時 fallback 全域值，行為與 v1.8 相同。

### 五年回測對比（同一份資料、同一條 git commit）

| Silo | v1.8 | **v1.9** | Δ |
|---|---|---|---|
| **Crypto** | +10.08% / 122 筆 / DD -29.86% / PF 1.39 | **+22.35% / 262 筆 / DD -40.63% / PF 1.47** | **+12.27 pp** |
| TW Stock | +3.35% / 383 筆 / DD -13.51% / PF 1.15 | +3.35% / 383 筆 / DD -13.51% / PF 1.15 | 無變化 |
| US+Commodity | +1.43% / 398 筆 / DD -13.37% / PF 1.05 | +1.43% / 398 筆 / DD -13.37% / PF 1.05 | 無變化 |

Crypto 達到使用者目標：
- ✅ 年化報酬 ≥20%（22.35%）
- ✅ 勝率 ≥30%（49.6%）
- ✅ 交易次數 50–100/年（50.7）
- ✅ 1/4 Kelly per-trade 不變（`KELLY_FRACTION=0.25`、Crypto fallback 6%）
- ⚠️ 最大回撤 -40.63%（加密幣特性、5 年含 2022 熊市）

### 已測試但未採用的方向

| 方向 | 結果 | 結論 |
|---|---|---|
| BTC moat → `full`（同時擋多+擋空） | -9.27% / PF 0.79 | 否決：擋空在 BTC 熊市反而砍掉好的空單 |
| BTC moat → 完全關閉 | -4.64% / PF 0.93 | 否決：BTC 熊市的多單虧損會放大 |
| 4H K 線（同樣參數移植） | -4.04% / PF 0.93 / WR 40.5% | 否決：噪音多、勝率掉到 40%；要可行需重調全套指標週期 |
| 1H K 線（同樣參數移植） | +3.68% / PF 1.09 / WR 40.3% | 否決：平均持倉 1.4 天，被 max_hold 提前出場為主 |

### Profile 限額（v1.9）

| Profile | Account | Asset Types | Max Positions | Max Pos % | Class Limits |
|---|---|---|---:|---:|---|
| **Crypto** | Bybit | Crypto | **5** | **0.40** | none |
| TW Stock | Taiwan broker | TW Stock | 6 | 0.20 | none |
| US+Commodity | US broker | US Stock, Commodity | 8 | 0.20 | US Stock 6, Commodity 2 |

### Crypto universe update

Crypto 回測標的已從 18 檔擴充為 30 檔：

- 3 檔固定核心幣：BTC、ETH、ADA
- 12 檔固定高成交量 Bybit USDT 永續合約
- 15 檔從原本 `CRYPTO_POOL` 隨機抽樣

新增的固定高成交量清單：

```text
HYPE, ZEC, FARTCOIN, 1000PEPE, SUI, PIPPIN,
TAO, WIF, ENA, ASTER, PUMPFUN, XPL
```

`python main.py backtest --profile Crypto` 現在只載入 Crypto 標的，
不再掃美股、台股、商品，因此單獨回測 Crypto 會更快，也能確認 30 檔是否全數進入回測。

最新 Crypto 30 檔檢查：

```text
載入 30 個資產
有效資產：30 檔
跳過：0 檔
年化報酬：19.27%
勝率：50.7%
交易：296 筆
Profit Factor：1.332
最大回撤：-47.11%
```

### Report update

Summary 的資金曲線表新增每日交易結果與手續費欄位：

```text
Date | 總資金 | 已配置資金 | 剩餘現金 | 損益 | 手續費 | 累積損益
```

### 重現指令

```powershell
python main.py backtest --output output\Backtest_v19.xlsx --note v19_baseline --ver v1.9
python main.py backtest --profile Crypto --output output\Backtest_Crypto_v19.xlsx --note v19_crypto
```

Sweep 腳本保留在 [scripts/](scripts/) 供後續再調參使用：
- `scripts/crypto_diag.py` — 進場阻塞統計
- `scripts/crypto_sweep[2-5].py` — 漸進式參數網格
- `scripts/crypto_btc_moat.py` — BTC 護城河三模式比較
- `scripts/crypto_intraday.py` — 4H / 1H 時間框架對照

多資產量化交易系統，支援回測、績效報告與即時下單（Bybit 已接通；IBKR / 新光 骨架待完成）。涵蓋美股、台股、加密貨幣與商品，內建 3 種獨立策略訊號、EMA 多空環境濾網、大盤護城河機制、智能熔斷與幾何 R:R 檢查。

---

## 目錄

- [功能概覽](#功能概覽)
- [專案結構](#專案結構)
- [快速開始](#快速開始)
- [指令說明](#指令說明)
- [交易策略](#交易策略)
- [市場環境濾網](#市場環境濾網)
- [風險管理](#風險管理)
- [執行器架構](#執行器架構)
- [資料來源](#資料來源)
- [回測報告](#回測報告)
- [即時交易](#即時交易)
- [資料庫結構](#資料庫結構)
- [依賴套件](#依賴套件)
- [版本記錄](#版本記錄)

---

## 功能概覽

| 功能 | 說明 |
|------|------|
| 資料抓取 | yfinance（股票/商品）+ Bybit REST API（加密貨幣） |
| 技術指標 | Supertrend、EMA20/50/100/200、布林通道、RSI、ATR、MACD、Volume Profile |
| 策略訊號 | 3 種獨立策略 + EMA 比例分數環境濾網 + 信心分數門檻（全域 MIN_ENTRY_SCORE=4，Crypto=3） |
| 市場護城河 | 台股 TAIEX SMA250 / 美股 SPY SMA200，弱市封鎖多單 |
| 智能熔斷 | 連虧 5 筆 **且** 帳戶回撤 ≥ 5% 雙條件觸發，暫停 5 個交易日 |
| 幾何 R:R | 檢查 TP 路徑上是否有近 20 日 swing 阻擋，有阻擋則拒絕進場 |
| 台股特化 | 處置股封鎖 hook、主力籌碼確認 hook（需外部資料） |
| 部位管理 | 1/4 Kelly 倉位計算、**分策略停損/停利**、**分策略並行倉位配額**、ATR Trailing Stop |
| 回測引擎 | 事件驅動日線模擬，追蹤 MAE/MFE、Trailing Stop |
| 績效報告 | 多頁籤 Excel（摘要、月度損益、策略比較、逐筆交易） |
| 即時交易 | 插件式執行器架構（Bybit 已接通；IBKR / 新光 骨架待完成） |
| 歷史查詢 | SQLite 儲存所有回測結果與逐筆交易紀錄 |
| TradingView 驗證 | `compare_tv.py` 逐根 K 棒對照 Pine Script 結果 |

---

## 專案結構

```
量化交易/
├── main.py                  # CLI 入口（fetch / update / backtest / live / history / info）
├── config.py                # 全域設定（資產清單、指標參數、濾網參數、v1.5 新開關）
├── .env                     # API 金鑰（本地保存，不進版本控制）
├── compare_tv.py            # TradingView 驗證腳本
├── requirements.txt
├── src/
│   ├── strategies.py        # 訊號產生（3 策略 + combine_signals + 護城河）
│   ├── indicators.py        # 技術指標計算（含 MACD）
│   ├── backtester.py        # 回測引擎（含熔斷、幾何 R:R、分數倉位）
│   ├── risk.py              # Kelly 準則倉位計算
│   ├── fetcher.py           # 資料下載
│   ├── database.py          # SQLite 讀寫
│   ├── reporter.py          # Excel 報告產生（含護城河狀態頁）
│   ├── executor.py          # 向後相容 shim → 改 import 自 src.executors
│   └── executors/           # 多 Broker 執行器套件
│       ├── __init__.py      # 統一匯出所有執行器
│       ├── base.py          # BaseExecutor 抽象介面
│       ├── bybit.py         # BybitExecutor（已實作，加密貨幣）
│       ├── ibkr.py          # IBKRExecutor（骨架，美股 + 商品，需 IB Gateway）
│       ├── shinkong.py      # ShinKongExecutor（骨架，台股，SDK 待確認）
│       └── router.py        # ExecutorRouter（依 symbol 自動分派 broker）
├── data/
│   └── trading.db           # SQLite 資料庫
└── output/                  # Excel 回測報告輸出
```

---

## 快速開始

### 安裝依賴

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### 設定 API 金鑰（即時交易用）

在專案根目錄建立 `.env`，填入 Bybit API Key / Secret（此檔案已加入 `.gitignore`，不會被版本控制）：

```
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
```

`config.py` 中的模擬帳號開關：

```python
BYBIT_DEMO = True   # 改為 False 正式下單
```

### 首次使用流程

```bash
# 1. 下載 5 年歷史資料（120 檔資產）
python main.py fetch

# 2. 執行預設完整模式回測，輸出 Excel 報告
python main.py backtest

# 3. 查看資料庫資產清單
python main.py info
```

---

## 指令說明

```bash
python main.py fetch [--years 5] [--seed 42]
```
下載全部 120 檔資產到 SQLite，預設 5 年歷史。
同時會下載 `^TWII`、`^GSPC` 大盤基準資料到 SQLite，供護城河濾網使用。

```bash
python main.py update [--seed 42]
```
增量更新（只抓上次日期之後的新 K 棒）。
同時會更新 `^TWII`、`^GSPC`，之後回測只需補最新缺口。

```bash
python main.py info
```
列出資料庫資產清單（symbol、日期範圍、K 棒數量）。

```bash
python main.py backtest [--capital 100000] [--no-with-vp] [--output path] [--note "備註"]
                        [--no-moat-tf-only] [--rs-pct 0.03]
                        [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
```
執行完整回測，產生 Excel 報告並將績效摘要寫入 DB。
回測會優先從 SQLite 載入大盤基準資料；若缺最新資料才嘗試下載，下載失敗時會沿用既有快取。

| 參數 | 說明 |
|------|------|
| `--with-vp` / `--no-with-vp` | Volume Profile 策略預設啟用；需要加速或比較舊模式時可用 `--no-with-vp` 關閉 |
| `--moat-tf-only` / `--no-moat-tf-only` | 預設護城河只封鎖 Supertrend 多單，VP/BB 豁免；可用 `--no-moat-tf-only` 關閉 |
| `--rs-pct 0.03` | 護城河豁免門檻（近 10 天個股漲幅超越大盤 N%，預設 3%） |

```bash
python main.py history [--limit 20] [--run-id N]
```
查詢歷史回測紀錄；加上 `--run-id N` 可看該次回測的所有逐筆交易。

```bash
python main.py live [--seed 42] [--interval 15]
```
即時交易循環，每 15 分鐘掃描一次訊號並透過 ExecutorRouter 分派下單（目前 Bybit 已啟用）。

---

## 交易策略

### 策略一：趨勢跟蹤（Supertrend）

- **指標**：Supertrend（ATR 週期 10、乘數 3.0）
- **邏輯**：Supertrend 方向由空翻多 → 做多；由多翻空 → 做空
- **觸發時機**：只在翻轉那根 K 棒觸發，不連續持倉
- **趨勢過濾**：Supertrend 翻多／空時要求 EMA50 5 日斜率同向，過濾掉 chop 年大量「翻紅後立刻被打回」的假訊號。
- **美股額外條件（可選）**：`config.ENABLE_US_MACD_FILTER = True` 時，翻多需 MACD 柱狀圖 > 0；最新回測中此濾網預設關閉

### 策略二：成交量分布 POC 支撐/阻力

- **指標**：Volume Profile（252 日滾動視窗、80 個 bins），取 POC（Point of Control）
- **邏輯**（已修正 look-ahead bias，使用前一日 POC）：
  - 收盤從 POC 上方跌回 POC 附近（±1.5%）且 RSI < 60 → **做多（支撐）**
  - 收盤從 POC 下方漲回 POC 附近（±1.5%）且 RSI > 40 → **做空（壓力）**
- **預設啟用**：目前回測預設採用完整組合並啟用 VP；若要加速或比較舊模式，可加 `--no-with-vp`

### 策略三：布林通道均值回歸

- **指標**：BB(20, 2.0)、RSI(14)
- **邏輯**：
  - Close ≤ 布林下緣 + RSI < 30 + 正常波動 → **做多**
  - Close ≥ 布林上緣 + RSI > 70 + 正常波動 → **做空**
- **波動過濾**：布林帶寬 < 50 日均值 × 1.5（避免在極端行情交易）

### 訊號合併（combine_signals）

EMA 比例分數環境濾網（0–4 分），統計收盤高/低於幾根 EMA（20/50/100/200）：

| 分數 | 含義 |
|------|------|
| 4 | 完美多頭排列 |
| 3 | 強多頭環境 |
| 2 | 溫和多頭（預設門檻） |
| 1 | 混沌，禁止進場 |
| 0 | 完全反向 |

- 多頭方向需 EMA 多頭分數 ≥ 2 才開放做多訊號
- 空頭方向需 EMA 空頭分數 ≥ 2 才開放做空訊號
- **衝突解消**：多空環境同時達標時，以 EMA 分數決勝；完全相同則不進場（FLAT）
- 共識分數 = 訊號方向一致的子策略數（1–3）+ EMA 對齊分數（0–4），最高 7 分
- `MIN_ENTRY_SCORE = 4`：共識分數低於 4 的訊號直接丟棄

---

## 市場環境濾網

### 大盤護城河（v1.2 新增）

防止在大盤弱勢期間開多倉，台股與美股套用不同基準指數：

| 資產類別 | 基準指數 | MA 週期 | 封鎖條件 |
|---------|---------|---------|---------|
| 台股 | ^TWII（加權指數） | SMA250（年線） | 指數跌破年線 → 封鎖做多 |
| 美股 | ^GSPC（S&P 500） | SMA200 | 指數跌破 200MA → 封鎖做多 |
| 加密/商品 | — | — | 不限制 |

**強勢股豁免（弱水三千，只取最強）**：近 10 天個股漲幅超越大盤 3% 以上，即使大盤弱勢仍允許進場。可透過 `--rs-pct` 調整豁免門檻。

### 美股 MACD 假突破過濾（v1.2 新增，可選）

Supertrend 翻多時，可要求 MACD 柱狀圖（hist）> 0 才允許進場，避免橫盤整理後 HFT 演算法洗盤造成的假突破訊號。

最新單因子回測顯示，此濾網開啟後總報酬與 PF 略降，因此目前預設：

```python
ENABLE_US_MACD_FILTER = False
```

### 台股特化 hook（需外部資料）

以下兩個濾網已預留接口，**預設不啟動**，需在計算指標後手動將欄位寫入 DataFrame：

| 欄位名稱 | 型別 | 說明 |
|---------|------|------|
| `is_disposition` | bool | 處置股標記，True = 目前為處置股（分盤交易），所有訊號全部封鎖 |
| `chip_buy_days` | int | 主力連續淨買超天數，需 ≥ 3 天才允許做多 |

資料來源可接 TWSE MOPS API 或台灣證交所每日公告。

---

## 風險管理

| 參數 | 設定值 |
|------|-------|
| 初始資金 | $100,000 USD |
| 每筆風險 | 預設 4% 資金 (上限 5%) |
| 倉位上限 | 單一資產 20% |
| 最大持倉數 | 15 個部位 |
| Trailing Stop | ATR × 3.0（僅向有利方向移動，**BB 抄底單不啟用**） |
| 倉位計算 | 1/4 Kelly（需 ≥ 10 筆歷史，否則預設 4%；以剩餘可用現金為 sizing 基準） |

### 分策略停損/停利（v1.3 新增）

不同進場通道的損益結構不同，因此每個策略有自己的停損距離與風報比：

| 策略 | ATR 停損倍數 | 風報比（RR）| 額外早出條件 |
|---|---:|---:|---|
| trend / combined | 3.0 | 1:3 | — |
| vp（POC 拉回） | 2.0 | 1:2 | — |
| **bb（布林抄底）** | **1.5** | **1:2** | **觸 BB 中軌 / RSI 回中性 50 / 浮盈 ≥ +3%** 任一觸發即出場 |

BB 是逆勢搶反彈策略，硬抱長線會被接下來的跌勢吞回。窄停損 + 早出條件確保它走「高勝率小利」的本質損益結構，不被當趨勢單對待。

### 分策略並行倉位配額（v1.4 新增）

避免某個策略（特別是 trend）把所有部位名額吃光，留空間給其他策略補位：

| 策略 | 同時部位上限 |
|---|---:|
| trend | 12 |
| vp | 8 |
| bb | 4 |
| combined（多策略同向） | 不限 |

`combined` 訊號代表多策略共識度高、品質最佳，不受配額限制。實證顯示 trend 從不限改為 12 後，被擋掉的是品質較差的後段訊號，trend 平均單筆 PnL 反而提升。

### 資產類別限制（與策略配額並存）

| 類別 | 最大同時部位數 |
|------|-------------|
| 美股 | 6 |
| 台股 | 6 |
| 加密貨幣 | **5（v1.9 從 2 上調）** |
| 商品 | 2 |

### 智能熔斷（v1.5 新增）

雙條件觸發，防止系統在策略失效期間持續虧損：

```python
ENABLE_CIRCUIT_BREAKER    = True
CB_CONSEC_LOSS_LIMIT      = 5      # 連虧 N 筆
CB_CONSEC_LOSS_PAUSE_DAYS = 5      # 觸發後暫停 N 個交易日
CB_DAILY_LOSS_PCT         = 0.03   # 當日虧損 ≥ 3% → 當日封盤
CB_MAX_DAILY_TRADES       = 10     # 當日新進場上限
CB_REQUIRE_DRAWDOWN       = True   # 必須同時滿足回撤條件才觸發（避免在低點誤殺反彈）
CB_REQUIRE_DRAWDOWN_PCT   = 0.05   # 帳戶回撤門檻 5%
```

**設計理由**：純連虧計數在趨勢反轉低點會誤觸（連虧最容易出現在行情剛要轉好前），加上 DD ≥ 5% 的雙條件後，熔斷準確率顯著提升。

### 幾何 R:R 檢查（v1.5 新增）

進場前掃描 TP 路徑是否有近期 swing high/low 阻擋：

```python
ENABLE_GEOMETRIC_RR  = True
GEO_RR_LOOKBACK      = 20      # 往前看 20 根 K 棒
GEO_RR_BUFFER_ATR    = 1.0     # 阻擋判定緩衝 = 1 × ATR
```

若 TP 路徑上有 swing 阻擋（多頭：swing high 在 entry~TP 之間；空頭：swing low），拒絕進場。此功能單獨啟用可改善績效 +1.1 pp。

---

## 執行器架構

### 設計原則

統一程式碼庫 + 插件式多 Broker 執行器，由 `ExecutorRouter` 依 symbol 自動分派：

```
symbol → asset_type_of() → ExecutorRouter → 對應 Executor
  'BYBIT:BTCUSDT.P'  →  Crypto   →  BybitExecutor    ✅ 已接通
  'AAPL'             →  US Stock →  IBKRExecutor      🚧 需 IB Gateway
  'XAUUSD'           →  Commodity→  IBKRExecutor      🚧 需 IB Gateway
  '2330.TW'          →  TW Stock →  ShinKongExecutor  🚧 SDK 待確認
```

### 使用方式

```python
from src.executors import ExecutorRouter

router = ExecutorRouter(enable={'Crypto': True, 'US Stock': False,
                                'Commodity': False, 'TW Stock': False})
router.warmup()                        # 主動建構所有啟用的 broker

ex = router.get('BYBIT:BTCUSDT.P')    # → BybitExecutor
ex.place_order('BYBIT:BTCUSDT.P', direction=1, qty=0.01,
               stop_loss=90000, take_profit=95000)

balances = router.get_balances()       # 所有已建構 broker 的餘額
```

### Broker 上線進度

| Broker | 類別 | 狀態 | 前置需求 |
|--------|------|------|---------|
| Bybit | Crypto | **已接通** | `.env` 設好 `BYBIT_API_KEY` / `BYBIT_API_SECRET` |
| Interactive Brokers | US Stock + Commodity | 骨架完成 | 開 IBKR 帳戶 → 安裝 TWS/IB Gateway → `pip install ib_insync` |
| 新光證券 | TW Stock | 骨架完成 | 確認新光 Python SDK 名稱後填入 `src/executors/shinkong.py` |

---

## 資料來源

| 資產類別 | 來源 | 數量 | 範例 |
|---------|------|------|------|
| 美股 | yfinance | 50 檔 | AAPL, MSFT, JPM, XOM |
| 台股 | yfinance | 50 檔 | 2330.TW, 2882.TW, 2609.TW |
| 加密貨幣 | Bybit REST API | 18 檔 | BTC, ETH, SOL, BNB |
| 商品 | yfinance（期貨） | 2 檔 | XAUUSD（黃金）, XAGUSD（白銀） |

---

## 回測報告

Excel 工作簿包含以下頁籤：

| 頁籤 | 內容 |
|------|------|
| 📊 Summary | 所有績效指標 + 權益曲線折線圖 + v1.6 功能啟用狀態 |
| 📈 Monthly P&L | 月度 × 資產類別損益樞紐分析（熱圖著色）+ 長條圖 |
| 🔍 Strategy Stats | 三策略比較、出場分布、多空勝率 |
| 📋 Asset Stats | 逐資產勝率、交易次數、損益；Top 10 / Bottom 10 |
| YYYY-QN | 按年/季分頁，含凍結標題、自動篩選 |
| 📋 All Trades | 所有已平倉交易（進出場日期、價格、R 倍數、MAE/MFE） |
| Per Symbol Stats | 逐 Symbol 摘要（條件格式著色損益與勝率） |

**主要績效指標**：

- 總報酬、年化報酬
- Sharpe Ratio、Calmar Ratio、Recovery Factor
- 勝率（整體 / 多空分開）
- 獲利因子（Profit Factor）、期望值（Expectancy）
- 最大回撤（% 與 USD）
- 平均持倉天數、平均 R 倍數
- 連續獲利/虧損最大值

---

## 即時交易

目前僅 Bybit 加密貨幣永續合約（USDT 保證金）已實際接通。

```bash
python main.py live --interval 15
```

- 每 15 分鐘掃描一次加密貨幣訊號
- 自動計算 Kelly 倉位（從歷史回測紀錄讀取）
- 使用市價單建倉，會先以 Bybit 即時價重算倉位與 SL/TP，並在送單前檢查 TP/SL 是否位於正確方向
- 可在 `config.py` 設定 `BYBIT_DEMO = True` 使用模擬帳號測試
- 按 `Ctrl+C` 可正常停止 live loop，不會輸出 traceback

---

## TradingView 策略腳本與驗證

本專案提供完整的 TradingView Pine Script 策略，方便您在圖表上直接視覺化與執行：

```bash
TradingView_Strategy.pine
```

此腳本已與 Python 端的最新邏輯 (v1.6+) 完全同步，包含：
- **大盤環境濾網 (Market Moat)**：大盤 MA 濾網與相對強弱 (RS) 豁免
- **MACD 過濾**：可選的 Supertrend MACD 假突破過濾
- **早期趨勢反轉偵測**：EMA200 斜率變化提前封鎖反向單
- **共識分數計算**：完全對齊 Python 的 1~7 分計算與 EMA 比例分數

您可以直接將 `TradingView_Strategy.pine` 複製貼上至 TradingView 的 Pine Editor 中使用。

若要確保 Python 端回測與 Pine Script 輸出一致，可執行驗證腳本：

```bash
python compare_tv.py
```
對照 Pine Script 輸出，逐根 K 棒驗證 Python 回測結果，確保指標計算（Wilder's RMA、Supertrend、Volume Profile）與 TradingView 完全一致。

---

## 資料庫結構

```sql
-- 歷史 OHLCV 資料
prices(id, symbol, date, open, high, low, close, volume, asset_type)

-- 資產元資料
asset_registry(symbol, asset_type, first_date, last_date, bar_count)

-- 回測執行摘要
backtest_runs(run_id, run_at, version, initial_capital, final_capital,
              total_return_pct, annual_return_pct, total_trades,
              win_rate, profit_factor, sharpe_ratio, max_drawdown_pct, note)

-- 回測逐筆交易
backtest_trades(id, run_id, symbol, strategy, direction, asset_type,
                entry_date, exit_date, entry_price, exit_price, quantity,
                pnl, return_pct, holding_days, r_multiple, mae, mfe, exit_reason)
```

---

## 依賴套件

```
yfinance>=0.2.40       # 股票/商品歷史資料
python-dotenv>=1.0.0   # .env 金鑰讀取
pandas>=2.0.3          # 資料處理
numpy>=1.24.0          # 數值計算
pybit>=5.6.0           # Bybit API
openpyxl>=3.1.2        # Excel 報告
scipy>=1.11.4          # 科學計算
tqdm>=4.66.0           # 進度條
requests>=2.31.0       # HTTP 請求
# 選配（即時交易其他 broker）
# ib_insync>=0.9.86    # IBKR（美股/商品）
# shioaji / shinkong_api  # 台股（SDK 待確認）
```

---

## 版本記錄

### v1.9（目前）⭐ — Crypto 專屬調參

**動機**：v1.8 Crypto silo 年化 +10%、僅 24 筆/年，遠低於使用者目標
（≥20% CAGR、50–100 筆/年）。本版透過類別特化參數，把 Crypto 推到目標
帶內，**完全不影響** TW / US+Commodity silo（兩者參數與績效逐項相同）。

**改動範圍**（皆為 Crypto-only override，其他類別自動 fallback v1.8 行為）：

1. `STRATEGY_PROFILES['Crypto']`：
   - `max_total_positions` 2 → 5
   - `max_position_pct` 0.20 → 0.40

2. 新增 `*_BY_CLASS` 字典（`config.py` 中段，未列入字典的類別 fallback 全域）：
   - `MIN_ENTRY_SCORE_BY_CLASS = {'Crypto': 3}`
   - `MAX_HOLD_DAYS_BY_CLASS = {'Crypto': 30}`
   - `TSL_USE_CLOSE_BY_CLASS = {'Crypto': True}`
   - `TSL_TIGHT_AFTER_R_BY_CLASS = {'Crypto': 2.0}`

3. `src/backtester.py` 新增 `_cls_get()` helper，4 個熱路徑點（TSL tight、
   TSL track、max-hold、min-entry-score）改為按 `pos.asset_type` 查表。

**Crypto 績效**：

| 指標 | v1.8 | v1.9 | Δ |
|---|---:|---:|---|
| 年化報酬 | 10.08% | **22.35%** | +12.27 pp |
| 交易筆數（5 年）| 122 | 262 | +115% |
| 交易筆數/年 | 23.7 | 50.7 | +114% |
| 勝率 | 53.3% | 49.6% | -3.7 pp |
| Profit Factor | 1.39 | 1.47 | +0.08 |
| 最大回撤 | -29.86% | -40.63% | -10.8 pp |
| avgR | +0.13 | +0.12 | -0.01 |

**已測試但未採用**：BTC moat 改 full / 完全關閉、4H、1H 時間框架——皆使
PF 跌至 < 1.1 或 < 1（詳見頂部「已測試但未採用的方向」表）。

---

### v1.7 — 類別特化 1/4 Kelly

**核心改動**：把 `DEFAULT_RISK_PCT` 從統一 4% 改成**按類別分配真實 1/4 Kelly**，依 v1.6 main 928 筆回測統計反推：

| 類別 | 勝率 | R | 完整 Kelly | 1/4 Kelly | v1.7 預設值 |
|---|---:|---:|---:|---:|---:|
| Crypto | 56.9% | 1.41 | 26.4% | 6.6% | **6.0%** |
| US Stock | 45.9% | 1.57 | 11.4% | 2.85% | **3.0%** |
| TW Stock | 41.0% | 1.73 | 6.98% | 1.74% | **2.0%** |
| Commodity | 54.8% | 1.03 | 11.1% | 2.78% | **3.0%** |

**為什麼這樣設**：v1.6 統一 4% 對台股太大（壓不住 41% 勝率的劣勢）、對 crypto 太小（餵不飽 57% 勝率的優勢）。改按類別分流後，風險預算自動往真實 alpha 集中。

**配套調整**：
- `MAX_RISK_PCT` 0.05 → 0.07（容納 crypto 真實 1/4 Kelly 6.6%）
- `MAX_POSITION_PCT` 維持 0.20（實測放寬到 0.30 在 2024/2025 虧損年放大傷害，反而 -3pp）

**績效（main 無槓桿版）**：

| 項目 | v1.6 main | **v1.7 main** | Δ |
|---|---:|---:|---|
| 年化報酬 | 13.73% | 13.62% | -0.11pp |
| Sharpe | 0.547 | **0.553** | +1% |
| Profit Factor | 1.390 | **1.396** | +0.4% |
| 最大回撤 | -11.31% | -11.94% | -0.6pp |

實質 CAGR 持平（差 0.1pp 屬雜訊範圍），但**語意更乾淨**——每個類別風險預算對齊真實 Kelly。`crypto-2x` 與 `lev-diversified` 兩個 leverage 分支仍停在 v1.6 risk.py（`DEFAULT_RISK_PCT=4%` 統一），需要前移時可手動 cherry-pick / merge main。

---

### v1.8 — 艙位回測 + Bybit 手續費 + 滑點模型

- 引入 `ENABLE_SILO_MODE` 與 `STRATEGY_PROFILES`，三個 silo 對應實際交易所帳戶（Bybit / 台股券商 / 美股券商），資金完全隔離
- 新增 Bybit `BYBIT:BTCUSDT.P` 為 Crypto market proxy 的長偏向護城河（`ENABLE_CRYPTO_BTC_MOAT = True`、`CRYPTO_BTC_MOAT_MODE = 'long_only'`）
- 進場手續費（Taker 0.055%）+ TP 出場（Maker 0.02%）+ SL/翻轉（Taker）；股票/商品單向 0.05%
- 進出場滑點 0.1%（limit TP 不計）
- Bybit 永續合約強制 leverage = 1x（`BYBIT_LEVERAGE = 1`），對齊 main 風險預算

---

### v1.6 ⭐

**三層改善（疊加生效）**：

1. **EMA50 斜率方向確認**：過濾 Supertrend 假翻轉（修 2022 chop）。
2. **倉位上限放寬 + 風險預設值**：把 Kelly 真正解放（`MAX_RISK_PCT` 0.02→0.05、`MAX_POSITION_PCT` 0.10→0.20、新增 `DEFAULT_RISK_PCT=0.04` 取代硬編 0.02 預設值）。
3. **類別槓桿（Leverage by Class）**：可選；放大 crypto / 股票 alpha。

#### 三個版本（git 分支）

從同一份策略碼分出三個 leverage 配置，依風險偏好選用：

| 分支 | LEVERAGE_BY_CLASS | 年化報酬 | 最大回撤 | Sharpe | 單筆風險上限 |
|---|---|---:|---:|---:|---|
| **`main`（無槓桿）** | 全 1.0 | **13.73%** | -11.31% | 0.547 | 5%（全類別一致） |
| `crypto-2x` | Crypto 2.0、其他 1.0 | **19.42%** | -15.74% | 0.688 | crypto 10%、其他 5% |
| `lev-diversified` | Crypto 2.5、股票 1.5、商品 1.0 | **26.08%** | -17.49% | 0.671 | crypto 12.5%、股票 7.5% |

> 切換版本：`git checkout crypto-2x` 或 `git checkout lev-diversified`，回 main 即無槓桿。

#### v1.5 baseline → v1.6 各版本對比

| 項目 | v1.5 | main（無槓桿）| crypto-2x | lev-diversified |
|---|---:|---:|---:|---:|
| 年化報酬 | 9.01% | **13.73%** | 19.42% | **26.08%** |
| 總報酬（6 年）| 56.14% | 95.17% | 150.10% | **231.57%** |
| Sharpe | 0.443 | 0.547 | **0.688** | 0.671 |
| Profit Factor | 1.308 | 1.390 | 1.450 | 1.416 |
| 勝率 | 45.4% | 45.5% | 47.9% | 47.6% |
| 最大回撤 | -9.73% | **-11.31%** | -15.74% | -17.49% |
| 2022 PnL | -$5,314 | **+$4,879** | +$8,402 | +$13,872 |

#### 槓桿與單筆風險的關係（重要）

槓桿在 [risk.py:78](src/risk.py#L78) 直接乘到 `risk_amount` 上：

```python
risk_amount = capital * min(kelly_frac, MAX_RISK_PCT) * leverage
```

意思是 1/4 Kelly 的 **R 單位（單筆 SL 觸發的虧損）會被同步放大**。例：crypto 2x 時，crypto 單筆 SL hit ≈ 8-10% 帳戶資金；lev-diversified 時 crypto 可達 12.5%、股票 7.5%。`main` 因為全 leverage=1.0，所有類別單筆 SL hit 一律 ≤ 5%。

#### 槓桿版真實交易需注意（回測未模擬）

- **保證金利息**：美股/台股融資 5-7% 年息 → 每筆持倉 30 天約 0.2% 拖累 → CAGR 估減 0.5-1pp。
- **永續資金費率**：Bybit ±0.03%/日 → 月持倉約 0.9% 拖累 → CAGR 估減 0.3-0.5pp。
- **gap risk**：crypto 假日跳空可能跌穿 SL，槓桿下虧損超過 -1R 預期。
- **Bybit 帳戶槓桿設定**：使用 `crypto-2x` 分支需在 Bybit 將該交易對的帳戶槓桿設為 ≥ 2x（建議 3-5x 留 buffer）；否則訂單會因保證金不足被拒絕。

---

### v1.5

**新功能**：

- **智能熔斷**（`ENABLE_CIRCUIT_BREAKER = True`）：連虧 5 筆 **且** 帳戶回撤 ≥ 5% 雙條件觸發，暫停 5 個交易日；純連虧版本反而降績效，雙條件顯著避免在反轉低點誤殺
- **幾何 R:R 檢查**（`ENABLE_GEOMETRIC_RR = True`）：進場前掃描 TP 路徑近 20 日 swing 阻擋，有阻擋拒絕進場；單獨啟用 +1.1 pp
- **多 Broker 執行器架構**：拆出 `src/executors/` 套件；`ExecutorRouter` 依 asset_type 自動分派 broker；Bybit 已接通，IBKR / 新光骨架完成待填實作
- **分數分級倉位**（`ENABLE_SCORE_TIER_SIZING`，預設 off）：7 分 × 1.0 / 5–6 分 × 0.6 / 4 分 × 0.3 Kelly

**Bug 修正**：

- VP 訊號 look-ahead：改用 `poc_prev = df['poc'].shift(1)` 避免用當日 POC 比較昨收（修正後總報酬由 62.79% → 44.22%，去除虛假超額）
- NaN ATR fallback：`float(atr or ...)` 對 `np.nan` 為 True；改用 `pd.isna()` 顯式判斷
- 勝率計算：零 PnL 不計入虧損（`p < 0` 而非 `p <= 0`）；WR 分母只含有勝敗的有效交易

**v1.5 回測績效**（120 檔資產，2020-03 至 2026-05，初始資金 $100k）：

| 指標 | v1.4 基線（修正後） | **v1.5** | 變化 |
|---|---:|---:|---:|
| 總報酬 | 44.22% | **57.71%** | **+13.49 pp** |
| 年化報酬 | 7.19% | **9.22%** | +2.03 pp |
| Profit Factor | 1.312 | **1.338** | +0.026 |
| Sharpe Ratio | 0.399 | **0.455** | +14% |
| 最大回撤 | -13.53% | **-12.59%** | 縮小 7% |

---

### v1.4

- **分策略並行倉位配額**：trend 12 / vp 8 / bb 4 / combined 不限
- trend 從不限改為 12 後，被擋掉的是品質較差的後段訊號，trend 平均單筆 PnL 反而提升

### v1.3

- **分策略停損/停利**：trend ATR×3 + RR 1:3、vp ATR×2 + RR 1:2、bb ATR×1.5 + RR 1:2
- **BB 早出邏輯**：觸 BB 中軌 / RSI≥50 (多) 或 ≤50 (空) / 浮盈 ≥ ±3% 任一觸發即出場；BB 不啟用 ATR Trailing Stop
- `calculate_stops` 接收 `strategy` 參數，依進場通道分流計算

### v1.2

- **MACD 指標**：新增 `macd`、`macd_sig`、`macd_hist` 欄位
- **大盤護城河**：台股 TAIEX SMA250 / 美股 SPY SMA200；弱市封鎖多單，強勢股（RS > 大盤 3%）豁免
- **美股 MACD 雙確認改為可選**：`ENABLE_US_MACD_FILTER` 控制是否啟用，預設 `False`
- **Volume Profile 預設啟用**；可用 `--no-with-vp` 關閉
- **倉位 sizing 修正**：回測開倉以 `available_cash` 作為 `position_size()` 基準

### v1.1

- EMA200 斜率濾網（早期趨勢轉向偵測）
- Asset Stats 頁籤新增各類別年化貢獻欄位

### v1.0

- 初始版本：Supertrend + Volume Profile + Bollinger 三策略
- EMA 比例分數環境濾網
- ATR Trailing Stop、1/4 Kelly 倉位、事件驅動回測引擎

---

## 注意事項

- 本系統僅供研究與學習用途，不構成投資建議
- 即時交易前請務必先以 `BYBIT_DEMO = True` 充分測試
- 回測績效不代表未來實際報酬
- API 金鑰存放於 `.env`，已列入 `.gitignore`，請勿手動提交至版本控制
