import random
import os
from dotenv import load_dotenv
load_dotenv()

# ─── 美股池 (120+) ────────────────────────────────────────
US_STOCKS_POOL = [
    # 科技
    'AAPL','MSFT','GOOGL','AMZN','TSLA','META','NVDA','NFLX','AMD','INTC',
    'QCOM','AVGO','TXN','MU','AMAT','LRCX','KLAC','MRVL','ON','ENPH',
    'ORCL','CRM','ADBE','NOW','SNOW','PLTR','UBER','LYFT','ABNB','DASH',
    # 金融
    'JPM','BAC','WFC','GS','MS','C','USB','PNC','TFC','COF',
    'V','MA','AXP','PYPL','COIN','HOOD','BLK','SCHW','ICE','CME',
    # 醫療
    'JNJ','PFE','ABBV','MRK','BMY','LLY','UNH','CVS','CI','HUM',
    'AMGN','GILD','BIIB','REGN','VRTX','MRNA','ILMN','DXCM','ISRG','EW',
    # 能源
    'XOM','CVX','COP','SLB','EOG','MPC','VLO','PSX','PXD','HAL',
    # 消費
    'WMT','TGT','COST','HD','LOW','MCD','SBUX','NKE','DG','DLTR',
    # 傳媒電信（PARA 已下市，改用 FOXA）
    'DIS','CMCSA','VZ','T','TMUS','CHTR','FOXA','WBD','SIRI','ROKU',
    # 工業
    'BA','LMT','RTX','NOC','GD','CAT','DE','MMM','GE','HON',
    'EMR','ETN','PH','ROK','ITW','DOV','FDX','UPS','DAL','UAL',
    # REITs & 其他
    'AMT','PLD','CCI','EQIX','SPG','O','WELL','AVB','EQR','ARE',
]

# ─── 台股池 (100+, TWSE上市) ────────────────────────────────────────
TW_STOCKS_POOL = [
    # 半導體/電子
    '2330.TW','2454.TW','2303.TW','2308.TW','3711.TW','2382.TW','2395.TW',
    '4938.TW','2357.TW','2379.TW','2301.TW','3034.TW','2474.TW','2409.TW',
    '2408.TW','2406.TW','3481.TW','6415.TW','6669.TW','6770.TW','6491.TW',
    '6533.TW','3008.TW','3037.TW','3017.TW','3006.TW','3016.TW','2376.TW',
    '2377.TW','2352.TW','2353.TW','2356.TW','2360.TW','2362.TW','2363.TW',
    '6239.TW','6271.TW','6278.TW','6285.TW','6289.TW','6290.TW',
    '5347.TW','3443.TW','2327.TW',
    # 金融
    '2882.TW','2881.TW','2886.TW','2884.TW','2891.TW','2892.TW','2880.TW',
    '2801.TW','5880.TW','2855.TW','2845.TW','5876.TW','2836.TW','2809.TW',
    '5871.TW','2002.TW',
    # 傳產/化工
    '1101.TW','1301.TW','1303.TW','6505.TW','1402.TW','1216.TW','1210.TW','1203.TW',
    '1218.TW','1215.TW','1436.TW','1409.TW','1417.TW','1419.TW',
    # 電信/傳媒
    '2412.TW','4904.TW','4906.TW','4958.TW','3231.TW','3045.TW',
    # 鋼鐵/汽車
    '2317.TW','2207.TW','2201.TW','2204.TW','2206.TW',
    # 航運
    '2609.TW','2615.TW','2618.TW','2603.TW','2610.TW',
    # 零售/食品
    '2912.TW','2915.TW','9910.TW','9914.TW','9917.TW','9921.TW','9907.TW',
    # 生技
    '6446.TW',
    # 其他電子
    '2374.TW','2373.TW','2371.TW','2369.TW','2368.TW','6116.TW',
]

# ─── 加密貨幣（Bybit 永續合約格式） ────────────────────────────────────────
CRYPTO_FIXED = ['BYBIT:BTCUSDT.P', 'BYBIT:ETHUSDT.P', 'BYBIT:ADAUSDT.P']
CRYPTO_POOL = [
    'BYBIT:SOLUSDT.P','BYBIT:BNBUSDT.P','BYBIT:XRPUSDT.P','BYBIT:DOTUSDT.P',
    'BYBIT:AVAXUSDT.P','BYBIT:MATICUSDT.P','BYBIT:LINKUSDT.P','BYBIT:UNIUSDT.P',
    'BYBIT:ATOMUSDT.P','BYBIT:NEARUSDT.P','BYBIT:OPUSDT.P','BYBIT:ALGOUSDT.P',
    'BYBIT:VETUSDT.P','BYBIT:ICPUSDT.P','BYBIT:SANDUSDT.P','BYBIT:MANAUSDT.P',
    'BYBIT:AXSUSDT.P','BYBIT:THETAUSDT.P','BYBIT:FILUSDT.P','BYBIT:HBARUSDT.P',
    'BYBIT:ARBUSDT.P','BYBIT:DOGEUSDT.P','BYBIT:LTCUSDT.P','BYBIT:BCHUSDT.P',
    'BYBIT:AAVEUSDT.P','BYBIT:COMPUSDT.P','BYBIT:SNXUSDT.P','BYBIT:CRVUSDT.P',
    'BYBIT:GRTUSDT.P','BYBIT:FLOWUSDT.P','BYBIT:EGLDUSDT.P','BYBIT:ONEUSDT.P',
    'BYBIT:ZILUSDT.P','BYBIT:CHZUSDT.P','BYBIT:MINAUSDT.P','BYBIT:APTUSDT.P',
]
# Added from Bybit linear USDT perpetual 180-day turnover ranking
# checked 2026-05-07; existing symbols were skipped and the list was extended.
CRYPTO_HIGH_VOLUME = [
    'BYBIT:HYPEUSDT.P','BYBIT:ZECUSDT.P','BYBIT:FARTCOINUSDT.P','BYBIT:1000PEPEUSDT.P',
    'BYBIT:SUIUSDT.P','BYBIT:PIPPINUSDT.P','BYBIT:TAOUSDT.P','BYBIT:WIFUSDT.P',
    'BYBIT:ENAUSDT.P','BYBIT:ASTERUSDT.P','BYBIT:PUMPFUNUSDT.P','BYBIT:XPLUSDT.P',
]
CRYPTO_EXTRA_COUNT = len(CRYPTO_POOL)  # v1.12: expand Crypto universe for 70-100 trades/year

# ─── 大宗商品 ────────────────────────────────────────
COMMODITIES = ['XAUUSD', 'XAGUSD']  # 黃金, 白銀

RANDOM_SEED = 42


def get_selected_assets(seed: int = RANDOM_SEED) -> dict:
    rng = random.Random(seed)
    us = rng.sample(US_STOCKS_POOL, min(50, len(US_STOCKS_POOL)))
    tw = rng.sample(TW_STOCKS_POOL, min(50, len(TW_STOCKS_POOL)))
    if CRYPTO_EXTRA_COUNT >= len(CRYPTO_POOL):
        crypto_extra = list(CRYPTO_POOL)
    else:
        crypto_extra = rng.sample(CRYPTO_POOL, min(CRYPTO_EXTRA_COUNT, len(CRYPTO_POOL)))
    cryptos = CRYPTO_FIXED + CRYPTO_HIGH_VOLUME + crypto_extra
    all_assets = us + tw + cryptos + COMMODITIES
    return {
        'us_stocks': us,
        'tw_stocks': tw,
        'cryptos': cryptos,
        'commodities': COMMODITIES,
        'all': all_assets,
    }


# ─── 指標參數 ────────────────────────────────────────
SUPERTREND_ATR_PERIOD  = 10
SUPERTREND_MULTIPLIER  = 3.0
EMA_PERIOD             = 200
EMA_FAST_PERIODS       = [20, 50, 100]   # 搭配 EMA200 組成 4 根 EMA 比例分數
EMA_MIN_SCORE          = 2               # 允許進場的最低 EMA 比例分數（4 根中至少幾根）
EMA200_SLOPE_PERIOD    = 10              # EMA200 斜率回望期（K 棒數）
MIN_ENTRY_SCORE        = 4               # 進場最低信心分數（子策略共識 + EMA 分數，最高 7）
BB_PERIOD              = 20
BB_STD                 = 2.0
RSI_PERIOD             = 14
ATR_PERIOD             = 14
ADX_PERIOD             = 14
VOLUME_BINS            = 80
VP_LOOKBACK            = 252  # 1年
VP_POC_TOLERANCE       = 0.015  # POC 觸碰容差 ±1.5%

# ─── MACD ────────────────────────────────────────
MACD_FAST              = 12
MACD_SLOW              = 26
MACD_SIGNAL            = 9
ENABLE_US_MACD_FILTER  = False

# ─── 大盤護城河 ────────────────────────────────────
TW_MARKET_SYMBOL       = '^TWII'   # 加權指數
US_MARKET_SYMBOL       = '^GSPC'   # S&P 500
TW_MARKET_MA_PERIOD    = 250       # 台股年線（SMA250）
US_MARKET_MA_PERIOD    = 200       # 美股 200MA（SMA200）
RS_LOOKBACK_DAYS       = 10        # 相對強弱回望天數
RS_OUTPERFORM_PCT      = 0.03      # 近 N 天領先大盤 3% 可豁免市場封鎖

# ─── 台股籌碼濾網 ────────────────────────────────────
# 需外部提供 chip_buy_days 欄位（主力連買天數）；未提供時此濾網不啟動
TW_CHIP_MIN_DAYS       = 3

# ─── 風控參數 ────────────────────────────────────────
RISK_REWARD_RATIO      = 3.0    # 預設 RR（沒有指定 strategy 時的 fallback）
KELLY_FRACTION         = 0.25   # 1/4 Kelly（v1.6 評估：放大 Kelly 對倉位影響很小，回到 0.25）
ATR_STOP_MULTIPLIER    = 3.0    # 預設 ATR 停損 / TSL 倍數
INITIAL_CAPITAL        = 100_000.0  # USD

# ─── 分策略出場參數（v1.3 分流）─────────────────────────
# 趨勢單（Supertrend / 多策略 combined）：讓利潤奔跑
STRAT_TREND_ATR_MULT   = 3.0
STRAT_TREND_RR         = 3.0
# 拉回單（Volume Profile POC）：中等持有時間
STRAT_VP_ATR_MULT      = 2.0
STRAT_VP_RR            = 2.0
# 抄底單（Bollinger 下軌）：搶反彈，不抱長線；硬停利只是兜底，主要靠早出
STRAT_BB_ATR_MULT      = 1.5
STRAT_BB_RR            = 2.0
STRAT_BB_PROFIT_PCT    = 0.03   # 浮盈 ≥ 3% 即出
STRAT_BB_RSI_EXIT      = 50     # RSI 回到中性即出（多頭 ≥50 / 空頭 ≤50）
STRAT_BB_DISABLE_TSL   = True   # BB 單關閉 ATR 移動停利（避免抄底單變趨勢單）

# ─── Plan A：BB 進場放寬（不受嚴格 EMA 守門員限制）────────────────────
# True 時 BB 用「Close vs EMA200 + 至少 BB_LOOSE_MIN_EMA_SCORE 根 EMA 對齊」做環境檢查
# False 時 BB 仍受主守門員 EMA_MIN_SCORE 限制（與 v1.3 一致）
# v1.6：開啟讓 BB 抄底單能在盤整/反轉市況補位（2022 type chop 環境特別有用）
STRAT_PARAMS_BY_CLASS: dict = {
    'Crypto': {
        'trend':    (2.0, 2.0),
        'combined': (2.0, 2.0),
        'vp':       (1.5, 1.5),
    },
}

BB_BYPASS_EMA_GATE     = True
BB_LOOSE_MIN_EMA_SCORE = 1

# ─── ADX 趨勢強度濾網（v1.6 評估後停用）─────────────────────────────────
# 0 = 停用；ADX 為滯後指標，硬閾值會砍掉 trend 早期入場（已實測 2024 重傷）。
# 保留參數方便日後測試。
TREND_ADX_MIN          = 0

# ─── 趨勢策略 EMA50 斜率確認（v1.6 啟用）─────────────────────────────
# Supertrend 翻多時要求 EMA50 斜率 > 0；翻空時要求 < 0。
# 過濾「下跌段中急彈翻紅」與「上漲段中假摔翻黑」的假訊號。
# 對 chop 年（2022）與強趨勢年（2024）有效；反轉年（2026）會被拖累。
TREND_EMA50_SLOPE_CONFIRM = True
TREND_EMA50_SLOPE_LOOKBACK = 5

# ─── Plan B：每策略並行倉位上限（dict 為空時不啟用）────────────────────
# 例：{'trend': 8, 'vp': 4, 'bb': 3}；'combined' 不限額
MAX_POS_PER_STRATEGY: dict = {'trend': 12, 'vp': 8, 'bb': 4}
MAX_RISK_PCT           = 0.070  # 單筆最大虧損上限 7%（v1.7：放寬以容納 crypto 真實 1/4 Kelly = 6.6%）
MAX_POSITION_PCT       = 0.20   # 單筆持倉市值上限 20%（實測 0.30 在虧損年放大傷害，留 0.20 當煞車）
DEFAULT_RISK_PCT       = 0.040  # 樣本不足時全域 fallback；類別有特化值時優先用下方 dict

# ─── 類別特化 1/4 Kelly（v1.7 新增）────────────────────────────────
# 從 v1.6 main 回測 928 筆統計反推每類別真實 1/4 Kelly：
#   Crypto:    WR 56.9%, R 1.41 → full Kelly 26.4% → 1/4 Kelly 6.6%
#   US Stock:  WR 45.9%, R 1.57 → full Kelly 11.4% → 1/4 Kelly 2.85%
#   TW Stock:  WR 41.0%, R 1.73 → full Kelly  7.0% → 1/4 Kelly 1.74%
#   Commodity: WR 54.8%, R 1.03 → full Kelly 11.1% → 1/4 Kelly 2.78%
# 樣本 < KELLY_MIN_TRADES 時 fallback 到此 dict（取代統一 4% 預設值）。
# 樣本足夠後，計算的 Kelly 仍受 MAX_RISK_PCT 上限保護。
DEFAULT_RISK_PCT_BY_CLASS: dict = {
    'Crypto':    0.060,   # 1/4 Kelly = 6.6%，給足以發揮 crypto 真實邊緣
    'US Stock':  0.030,   # 1/4 Kelly = 2.85%
    'TW Stock':  0.020,   # 1/4 Kelly = 1.74%（勝率最低，給最少）
    'Commodity': 0.030,   # 1/4 Kelly = 2.78%
}

# ─── 類別槓桿（v1.6 新增）──────────────────────────────────────────
# Bybit 永續合約以保證金交易；現金型回測對 crypto 過於保守。
# 設為 2.0 表示 crypto 倉位用一半保證金，等同 2x 槓桿。
# Bybit 預設可至 10x，這裡保守設 2.0，DD 影響仍可控。
# 股票/商品保持 1.0（無槓桿）。
LEVERAGE_BY_CLASS: dict = {
    'Crypto':    1.0,
    'US Stock':  1.0,
    'TW Stock':  1.0,
    'Commodity': 1.0,
}
MAX_TOTAL_POSITIONS    = 15     # 單一資金池/舊版模式的同時持倉上限；silo 使用 STRATEGY_PROFILES
KELLY_MIN_TRADES       = 10     # 觸發 Kelly 所需最少交易紀錄

# 每個資產類別的同時持倉上限（名額隔離，非資金隔離）
# 分倉模式下 Crypto / TW Stock 是獨立交易所帳戶；US Stock 與 Commodity
# 共用同一個 US+Commodity silo，因此比例與持倉名額的互相擠壓主要發生在美股/黃金。
# 各類別上限之和可大於 MAX_TOTAL_POSITIONS，整體仍受 MAX_TOTAL_POSITIONS 限制。
MAX_POS_PER_CLASS: dict = {
    'US Stock':  6,
    'TW Stock':  6,
    'Crypto':    2,
    'Commodity': 2,
}

# ─── Plan C：分數分級倉位（v1.6 評估後停用：低分訊號占多數，縮減傷大於高分加碼）
ENABLE_SCORE_TIER_SIZING = False
SCORE_TIER_MULT: dict[int, float] = {7: 1.0, 6: 0.6, 5: 0.6, 4: 0.3}

# ─── 熔斷機制（Circuit Breaker）────────────────────────────────────────
ENABLE_CIRCUIT_BREAKER    = True   # v1.5 預設啟用（搭配 DD 條件）
CB_CONSEC_LOSS_LIMIT      = 5      # 連虧 N 筆觸發暫停
CB_CONSEC_LOSS_PAUSE_DAYS = 5      # 觸發後暫停 N 個交易日
CB_DAILY_LOSS_PCT         = 0.03   # 當日已實現虧損 ≥ 3% → 當日封盤
CB_MAX_DAILY_TRADES       = 10     # 當日新進場上限
# 額外條件：連虧達標時，需同時滿足「當前回撤 ≥ N%」才真正暫停
# 避免在波段反轉低點誤殺反彈訊號
CB_REQUIRE_DRAWDOWN       = True
CB_REQUIRE_DRAWDOWN_PCT   = 0.05   # 5% 帳戶回撤門檻

# ─── 幾何 R:R 檢查 ─────────────────────────────────────────────────────
# TP 路徑上若有近 N 日 swing high/low 阻擋（距離 < BUFFER×ATR）→ 拒絕進場
ENABLE_GEOMETRIC_RR  = True        # v1.5 預設啟用（單獨即可 +1.1 pp）
GEO_RR_LOOKBACK      = 20
GEO_RR_BUFFER_ATR    = 1.0

# ─── 資料庫 ────────────────────────────────────────
DB_PATH   = 'data/trading.db'
DATA_YEARS = 5

# ─── Bybit ────────────────────────────────────────
BYBIT_API_KEY    = os.environ.get('BYBIT_API_KEY',    '')
BYBIT_API_SECRET = os.environ.get('BYBIT_API_SECRET', '')
# 此為模擬帳號
BYBIT_DEMO       = True   # 模擬帳號（Demo Trading）設 True
BYBIT_TESTNET    = False  # 測試網（testnet.bybit.com）才設 True；一般模擬帳號設 False
BYBIT_LEVERAGE   = 1      # Force linear contract leverage before placing orders.

# ─── A/B 測試開關（Stock_01_share 借鑑，預設全停用以保留 v1.5 行為）──
# 把任一項從預設值改掉，會直接影響 PnL；目的是逐項測試效果。
MIN_HOLD_DAYS      = 0       # 持倉 < N 天時，只允許硬 SL/TP；其餘出場延後（v1.6 測試後復原：signal_flip 對盈虧是淨救援）
SOFT_STOP_PCT      = 0.0     # 軟停損：滿 MIN_HOLD_DAYS 後浮虧 ≥ N → 出場（0 = 停用）
MAX_HOLD_DAYS      = 0       # 最長持倉 N 天，到期強制平倉（0 = 停用）
SYM_MIN_WINRATE    = 0.35    # 該 symbol 近 SYM_WR_WINDOW 筆勝率 < N → 暫停做多（0 = 停用）
SYM_WR_MIN_TRADES  = 5       # SYM_MIN_WINRATE 啟動所需最少樣本
SYM_WR_WINDOW      = 30      # 計算個股勝率的滾動視窗
ATR_KELLY_MULT     = 0.0     # 當日 ATR > 50 日中位數 × N → Kelly 減半（0 = 停用）
EQUAL_CASH_SPLIT   = False   # 同日多訊號時將剩餘現金均分至剩餘進場名額（測試後復原：縮小早期 A 級訊號）

# ─── B 系列 A/B 旗標（出場機制 + 倉位精修，預設全停用）────────────────────
ENABLE_BREAKEVEN_STOP   = False  # B1a：浮盈 ≥ N×R 時把 stop_loss 移到進場價
BREAKEVEN_TRIGGER_R     = 1.0    # B1a：觸發倍數（1.0 = +1R）
TSL_USE_CLOSE           = False  # B2a：TSL 追蹤改用收盤價（取代日內 High/Low）
TSL_TIGHT_AFTER_R       = 0.0    # B2b：浮盈 ≥ N×R 時收緊 ATR 倍數（0 = 停用）
TSL_TIGHT_ATR_MULT      = 1.5    # B2b：收緊後的 ATR 倍數

# ─── 類別特化參數（v1.9 新增）────────────────────────────────────────────
# 給單一資產類別用的 override；未列出的類別 fallback 到上面全域值。
# 主要用途：crypto 24/7 市場節奏快、波動大，與股票需要不同的出場邏輯。
# 設計準則：
#   * MIN_ENTRY_SCORE_BY_CLASS：crypto 訊號通過率較高，可放寬至 3 以增交易次數
#   * MAX_HOLD_DAYS_BY_CLASS：crypto 趨勢平均 30 天內結束；超過多為盤整 → 強制平倉
#   * TSL_USE_CLOSE_BY_CLASS：crypto 上下影線常見，用收盤確認可避免被插針掃出
#   * TSL_TIGHT_AFTER_R_BY_CLASS：浮盈 ≥ 2R 後收緊 → 鎖住趨勢段獲利（avgR 0.17→0.12）
MIN_ENTRY_SCORE_BY_CLASS: dict = {'Crypto': 3}
MAX_HOLD_DAYS_BY_CLASS:   dict = {'Crypto': 30}
TSL_USE_CLOSE_BY_CLASS:   dict = {'Crypto': True}
TSL_TIGHT_AFTER_R_BY_CLASS: dict = {'Crypto': 2.0}
# SYM filter 設定（v1.13 walk-forward 後拍板：保留 aggressive）
# 三組 OOS 實測：3/20 +30.82%、30/50 +23.80%、no filter +25.17%
# → aggressive (3/20) OOS 最佳，雖然 5y 連跑會產生 +627% path-dep 幻覺，
#   但實盤只能往前走、不會經歷「整段歷史回頭篩選」，OOS 才是真實基準。
# README 必須以 OOS 數字為準，連續回測數字僅供 in-sample 參考。
SYM_MIN_WINRATE_BY_CLASS:   dict = {'Crypto': 0.45}
SYM_WR_MIN_TRADES_BY_CLASS: dict = {'Crypto': 3}
SYM_WR_WINDOW_BY_CLASS:     dict = {'Crypto': 20}
ENABLE_MARKET_SHORT_MOAT = False # B3：大盤指數 < SMA(N) 才允許做空
MARKET_SHORT_MA_PERIOD  = 50     # B3：空頭濾網的 SMA 週期
KELLY_WINDOW            = 0      # B4：Kelly 只取最近 N 筆（0 = 全歷史）
CLOSE_BASED_SL_TREND    = False  # B5：trend/combined 改成「收盤跌破才停損」

# Crypto market regime moat. Uses BTC as the crypto market proxy.
# Local yearly sweeps favored a long-only moat: allow crypto longs only when
# BTC is above EMA200, while leaving crypto shorts to the symbol-level signals.
ENABLE_CRYPTO_BTC_MOAT = True
CRYPTO_MARKET_SYMBOL = 'BYBIT:BTCUSDT.P'
CRYPTO_BTC_MOAT_MODE = 'long_only'  # long_only / full
CRYPTO_SHORT_EMA_SLOPE_LOOKBACK = 100

# ─── 艙位回測模式（v1.8 新增）──────────────────────────────────────────
# True  → 三家交易所各自獨立 SILO_CAPITAL 起跑，各艙位 P&L 完全隔離
# False → 舊版單一資金池回測（--capital 參數有效）
# 實盤限制：此專案的 silo 對應不同交易所/帳戶（Bybit、台股券商、美股券商），
# 底層資金不可互相調度，因此最佳化不可關閉 silo 來提高帳面資金效率。
ENABLE_SILO_MODE = True
SILO_CAPITAL     = 10_000.0   # 每個艙位初始資金 (USD)
# 艙位名稱 → 包含的資產類型清單
# 各艙位對應實際交易所：加密=Bybit、台股=台灣券商、美股+黃金=美國券商
SILO_CLASSES: dict = {
    'Crypto':       ['Crypto'],
    'TW Stock':     ['TW Stock'],
    'US+Commodity': ['US Stock', 'Commodity'],
}

# Strategy profiles bind strategy rules to the real execution account.
# The three profiles intentionally remain separate because each maps to a
# different broker/exchange account and cannot share capital.
STRATEGY_PROFILES: dict = {
    'Crypto': {
        'asset_types': ['Crypto'],
        'capital': SILO_CAPITAL,
        # v1.12 target: 70-100 Crypto trades/year with Sharpe/Calmar > 1.
        'max_total_positions': 10,
        'max_position_pct': 0.40,
        'max_pos_per_class': {},
    },
    'TW Stock': {
        'asset_types': ['TW Stock'],
        'capital': SILO_CAPITAL,
        'max_total_positions': 6,
        'max_position_pct': MAX_POSITION_PCT,
        'max_pos_per_class': {},
    },
    'US+Commodity': {
        'asset_types': ['US Stock', 'Commodity'],
        'capital': SILO_CAPITAL,
        'max_total_positions': 8,
        'max_position_pct': MAX_POSITION_PCT,
        'max_pos_per_class': {
            'US Stock': 6,
            'Commodity': 2,
        },
    },
}

# ─── 手續費與滑點（v1.8 新增）────────────────────────────────────────────
# Bybit 永續合約費率（進場 Taker；TP Maker；SL/其他 Taker）
BYBIT_MAKER_FEE  = 0.0002    # 0.02%
BYBIT_TAKER_FEE  = 0.00055   # 0.055%
# 股票/商品 單向手續費估算（US/TW 券商約 0.05%，可自行調整）
STOCK_FEE_PCT    = 0.0005    # 0.05% per side
# 市價成交滑點（進場 + 市價出場各一次；limit TP 不計）
SLIPPAGE_PCT     = 0.001     # 0.1% per side

# Backtest cost stress toggles. Defaults preserve the current cost model.
BACKTEST_TP_AS_TAKER = False
BACKTEST_SLIPPAGE_ON_TP = False
BACKTEST_FUNDING_DAILY_PCT_BY_CLASS: dict = {}
BACKTEST_EXTRA_SLIPPAGE_PCT_BY_CLASS: dict = {}
BACKTEST_INTRABAR_CONFLICT_MODE = 'tp_first'  # tp_first / sl_first / conservative

# ─── 系統版號 ────────────────────────────────────────
SYSTEM_VERSION  = 'v1.13'

# ─── 輸出 ────────────────────────────────────────
OUTPUT_DIR      = 'output'
OUTPUT_FILENAME = 'Output.xlsx'
BYBIT_LIVE_ORDER_XLSX = 'output/Bybit_Live_Orders.xlsx'
