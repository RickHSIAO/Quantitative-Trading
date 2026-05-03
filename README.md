# 量化交易系統

多資產量化交易系統，支援回測、績效報告與 Bybit 即時下單。涵蓋美股、台股、加密貨幣與商品，內建 3 種獨立策略訊號、EMA 多空環境濾網、MACD 確認濾網與大盤護城河機制。

---

## 目錄

- [功能概覽](#功能概覽)
- [專案結構](#專案結構)
- [快速開始](#快速開始)
- [指令說明](#指令說明)
- [交易策略](#交易策略)
- [市場環境濾網](#市場環境濾網)
- [風險管理](#風險管理)
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
| 策略訊號 | 3 種獨立策略 + EMA 比例分數環境濾網 |
| 市場護城河 | 台股 TAIEX SMA250 / 美股 SPY SMA200，弱市封鎖多單 |
| 美股 MACD 確認 | Supertrend 翻多時需 MACD 柱狀圖 > 0，過濾 HFT 假突破 |
| 台股特化 | 處置股封鎖 hook、主力籌碼確認 hook（需外部資料） |
| 部位管理 | 1/4 Kelly 倉位計算、ATR 停損、1:3 風報比、ATR Trailing Stop |
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
├── config.py            # 全域設定（資產清單、指標參數、濾網參數）
├── .env                 # API 金鑰（本地保存，不進版本控制）
├── compare_tv.py        # TradingView 驗證腳本
├── requirements.txt
├── src/
│   ├── strategies.py    # 訊號產生（3 策略 + combine_signals + 護城河）
│   ├── indicators.py    # 技術指標計算（含 MACD）
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
python main.py backtest [--capital 100000] [--with-vp] [--output path] [--note "備註"]
                        [--moat-tf-only] [--rs-pct 0.03]
                        [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
```
執行完整回測，產生 Excel 報告並將績效摘要寫入 DB。

| 參數 | 說明 |
|------|------|
| `--with-vp` | 啟用 Volume Profile 策略（預設關閉，速度較慢） |
| `--moat-tf-only` | 護城河只封鎖 Supertrend 多單，VP/BB 豁免 |
| `--rs-pct 0.03` | 護城河豁免門檻（近 10 天個股漲幅超越大盤 N%，預設 3%） |

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
- **美股額外條件**：翻多時需 MACD 柱狀圖 > 0（動能由空轉多），過濾 HFT 洗盤假突破

### 策略二：成交量分布 POC 支撐/阻力

- **指標**：Volume Profile（252 日滾動視窗、80 個 bins），取 POC（Point of Control）
- **邏輯**：
  - 收盤從 POC 上方跌回 POC 附近（±1.5%）且 RSI < 60 → **做多（支撐）**
  - 收盤從 POC 下方漲回 POC 附近（±1.5%）且 RSI > 40 → **做空（壓力）**
- **預設關閉**：此策略計算耗時，且經回測驗證對整體績效無正向貢獻，需明確加上 `--with-vp` 才啟用

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

### 美股 MACD 假突破過濾（v1.2 新增）

Supertrend 翻多時，需 MACD 柱狀圖（hist）> 0 才允許進場，避免橫盤整理後 HFT 演算法洗盤造成的假突破訊號。

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
| 每筆風險 | 2% 資金 |
| 倉位上限 | 單一資產 10% |
| 最大持倉數 | 15 個部位 |
| 停損距離 | ATR × 3.0 |
| 停利距離 | 停損 × 3.0（1:3 風報比） |
| Trailing Stop | ATR × 3.0（僅向有利方向移動） |
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
```

---

## 版本記錄

### v1.2（目前）
- **MACD 指標**：新增 `macd`、`macd_sig`、`macd_hist` 欄位
- **大盤護城河**：台股 TAIEX SMA250 / 美股 SPY SMA200；弱市封鎖多單，強勢股（RS > 大盤 3%）豁免
- **美股 MACD 雙確認**：Supertrend 翻多需 hist > 0，過濾橫盤假突破
- **台股特化 hook**：預留處置股（`is_disposition`）與主力籌碼（`chip_buy_days`）欄位接口
- **Volume Profile 預設關閉**：回測驗證 VP 對整體績效無正向貢獻，改為 `--with-vp` 手動啟用
- **新 CLI 參數**：`--with-vp`、`--moat-tf-only`、`--rs-pct`
- **績效提升（vs v1.0）**：總報酬 +8.44%、夏普 +0.046、最大回撤改善 1.7%、勝率 +5.5pp

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
