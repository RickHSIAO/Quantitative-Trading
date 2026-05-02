# 量化交易系統

多資產量化交易系統，支援回測、績效報告與 Bybit 即時下單。涵蓋美股、台股、加密貨幣與商品，內建 3 種獨立策略訊號與 EMA 多空環境濾網。

---

## 目錄

- [功能概覽](#功能概覽)
- [專案結構](#專案結構)
- [快速開始](#快速開始)
- [指令說明](#指令說明)
- [交易策略](#交易策略)
- [風險管理](#風險管理)
- [資料來源](#資料來源)
- [回測報告](#回測報告)
- [即時交易](#即時交易)
- [資料庫結構](#資料庫結構)
- [依賴套件](#依賴套件)

---

## 功能概覽

| 功能 | 說明 |
|------|------|
| 資料抓取 | yfinance（股票/商品）+ Bybit REST API（加密貨幣） |
| 技術指標 | Supertrend、EMA20/50/100/200、布林通道、RSI、ATR、Volume Profile |
| 策略訊號 | 3 種獨立策略 + EMA 比例分數環境濾網 |
| 部位管理 | 1/4 Kelly 倉位計算、ATR 停損、1:3 風報比 |
| 回測引擎 | 事件驅動日線模擬，追蹤 MAE/MFE、Trailing Stop |
| 績效報告 | 多頁籤 Excel（摘要、月度損益、策略比較、逐筆交易） |
| 即時交易 | Bybit 永續合約下單（加密貨幣） |
| 歷史查詢 | SQLite 儲存所有回測結果與逐筆交易紀錄 |
| TradingView 驗證 | `compare_tv.py` 逐根 K 棒對照 Pine Script 結果 |

---

## 專案結構

```
量化交易/
├── main.py              # CLI 入口（fetch / update / backtest / live / history / info）
├── config.py            # 全域設定（資產清單、指標參數、API 金鑰）
├── compare_tv.py        # TradingView 驗證腳本
├── requirements.txt
├── src/
│   ├── strategies.py    # 訊號產生（3 策略 + combine_signals）
│   ├── indicators.py    # 技術指標計算
│   ├── backtester.py    # 回測引擎
│   ├── risk.py          # Kelly 準則倉位計算
│   ├── fetcher.py       # 資料下載
│   ├── database.py      # SQLite 讀寫
│   ├── executor.py      # Bybit 即時下單
│   └── reporter.py      # Excel 報告產生
├── data/
│   └── trading.db       # SQLite 資料庫
└── output/              # Excel 回測報告輸出
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

在 `config.py` 填入 Bybit API Key / Secret：

```python
BYBIT_API_KEY    = "your_api_key"
BYBIT_API_SECRET = "your_api_secret"
BYBIT_DEMO       = True   # 改為 False 正式下單
```

### 首次使用流程

```bash
# 1. 下載 5 年歷史資料（120 檔資產）
python main.py fetch

# 2. 執行回測，輸出 Excel 報告
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

```bash
python main.py update [--seed 42]
```
增量更新（只抓上次日期之後的新 K 棒）。

```bash
python main.py info
```
列出資料庫資產清單（symbol、日期範圍、K 棒數量）。

```bash
python main.py backtest [--capital 100000] [--no-vp] [--output path] [--note "備註"]
```
執行完整回測，產生 Excel 報告並將績效摘要寫入 DB。`--no-vp` 可停用 Volume Profile 策略。

```bash
python main.py history [--limit 20] [--run-id N]
```
查詢歷史回測紀錄；加上 `--run-id N` 可看該次回測的所有逐筆交易。

```bash
python main.py live [--seed 42] [--interval 60]
```
即時交易循環，每 60 秒掃描一次訊號並在 Bybit 下單（僅加密貨幣）。

---

## 交易策略

### 策略一：趨勢跟蹤（Supertrend）

- **指標**：Supertrend（ATR 週期 10、乘數 3.0）
- **邏輯**：Supertrend 方向由空翻多 → 做多；由多翻空 → 做空
- **觸發時機**：只在翻轉那根 K 棒觸發，不連續持倉

### 策略二：成交量分布 POC 支撐/阻力

- **指標**：Volume Profile（252 日滾動視窗、80 個 bins），取 POC（Point of Control）
- **邏輯**：
  - 收盤從 POC 上方跌回 POC 附近（±1.5%）且 RSI < 60 → **做多（支撐）**
  - 收盤從 POC 下方漲回 POC 附近（±1.5%）且 RSI > 40 → **做空（壓力）**

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
- 最終信心分數 = 子策略共識數（1–3）+ EMA 分數（0–4），最高 7 分

---

## 風險管理

| 參數 | 設定值 |
|------|-------|
| 初始資金 | $100,000 USD |
| 每筆風險 | 2% 資金 |
| 倉位上限 | 單一資產 10% |
| 最大持倉數 | 15 個部位 |
| 停損距離 | ATR × 2.0 |
| 停利距離 | 停損 × 3.0（1:3 風報比） |
| Trailing Stop | ATR × 2.0（僅向有利方向移動） |
| 倉位計算 | 1/4 Kelly（需 ≥ 10 筆歷史，否則預設 2%） |

**資產類別限制**：

| 類別 | 最大同時部位數 |
|------|-------------|
| 美股 | 6 |
| 台股 | 6 |
| 加密貨幣 | 2 |
| 商品 | 2 |

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
| 📊 Summary | 所有績效指標 + 權益曲線折線圖 |
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

僅支援 Bybit 加密貨幣永續合約（USDT 保證金）。

```bash
python main.py live --interval 60
```

- 每 60 秒掃描一次加密貨幣訊號
- 自動計算 Kelly 倉位（從歷史回測紀錄讀取）
- 使用市價單建倉，附帶 SL/TP 設定
- 可在 `config.py` 設定 `BYBIT_DEMO = True` 使用模擬帳號測試

---

## TradingView 驗證

```bash
python compare_tv.py
```

對照 Pine Script 輸出，逐根 K 棒驗證 Python 回測結果，確保指標計算（Wilder's RMA、Supertrend、Volume Profile）與 TradingView 一致。

---

## 資料庫結構

```sql
-- 歷史 OHLCV 資料
prices(id, symbol, date, open, high, low, close, volume, asset_type)

-- 資產元資料
asset_registry(symbol, asset_type, first_date, last_date, bar_count)

-- 回測執行摘要
backtest_runs(run_id, run_at, initial_capital, final_capital,
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
yfinance>=0.2.40    # 股票/商品歷史資料
pandas>=2.0.3       # 資料處理
numpy>=1.24.0       # 數值計算
pybit>=5.6.0        # Bybit API
openpyxl>=3.1.2     # Excel 報告
scipy>=1.11.4       # 科學計算
tqdm>=4.66.0        # 進度條
requests>=2.31.0    # HTTP 請求
```

---

## 注意事項

- 本系統僅供研究與學習用途，不構成投資建議
- 即時交易前請務必先以 `BYBIT_DEMO = True` 充分測試
- 回測績效不代表未來實際報酬
- Bybit API 金鑰請妥善保管，勿上傳至版本控制
