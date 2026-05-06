# 量化交易系統

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
| 策略訊號 | 3 種獨立策略 + EMA 比例分數環境濾網 + 信心分數門檻（MIN_ENTRY_SCORE=4） |
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
python main.py live [--seed 42] [--interval 60]
```
即時交易循環，每 60 秒掃描一次訊號並透過 ExecutorRouter 分派下單（目前 Bybit 已啟用）。

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
| 加密貨幣 | 2 |
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
python main.py live --interval 60
```

- 每 60 秒掃描一次加密貨幣訊號
- 自動計算 Kelly 倉位（從歷史回測紀錄讀取）
- 使用市價單建倉，附帶 SL/TP 設定
- 可在 `config.py` 設定 `BYBIT_DEMO = True` 使用模擬帳號測試

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

### v1.6（目前）⭐

**三層改善（疊加生效）**：

- **EMA50 斜率方向確認**：過濾 Supertrend 假翻轉（修 2022 chop）。
- **倉位上限放寬 + 風險預設值**：把 Kelly 真正解放（從 5.5% → 9%+ 平均倉位）。
- **類別槓桿（Leverage by Class）**：Crypto 2.5x / 股票 1.5x，把高 alpha 類別（crypto $730/trade）放大。

**v1.5 baseline → v1.6 final 全程對比**：

| 項目 | v1.5 baseline | v1.6 final | 變化 |
|---|---:|---:|---|
| 年化報酬 | 9.01% | **26.08%** | +17.07pp（+189%） |
| 總報酬 | 56.14% | **231.57%** | +312% |
| Sharpe | 0.443 | **0.671** | +51% |
| Profit Factor | 1.308 | **1.416** | +8% |
| 勝率 | 45.4% | **47.6%** | +2.2pp |
| 最大回撤 | -9.73% | **-17.49%** | -7.76pp |
| 2022 年度 PnL | -$5,314 | **+$13,872** | +$19,186 |

**真實交易需注意（回測未模擬）**：

- **保證金利息**：美股/台股融資 5-7% 年息 → 每筆持倉 30 天約 0.2% 拖累 → CAGR 估減 0.5-1pp。
- **永續資金費率**：Bybit ±0.03%/日 → 月持倉約 0.9% 拖累 → CAGR 估減 0.3-0.5pp。
- **gap risk**：crypto 假日跳空可能跌穿 SL，槓桿下虧損超過 -1R 預期。

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
