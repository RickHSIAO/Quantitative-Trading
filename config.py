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

# ─── 大宗商品 ────────────────────────────────────────
COMMODITIES = ['XAUUSD', 'XAGUSD']  # 黃金, 白銀

RANDOM_SEED = 42


def get_selected_assets(seed: int = RANDOM_SEED) -> dict:
    rng = random.Random(seed)
    us = rng.sample(US_STOCKS_POOL, min(50, len(US_STOCKS_POOL)))
    tw = rng.sample(TW_STOCKS_POOL, min(50, len(TW_STOCKS_POOL)))
    crypto_extra = rng.sample(CRYPTO_POOL, 15)
    cryptos = CRYPTO_FIXED + crypto_extra  # 3 + 15 = 18
    all_assets = us + tw + cryptos + COMMODITIES  # 50+50+18+2 = 120
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
RISK_REWARD_RATIO      = 3.0    # 1:3
KELLY_FRACTION         = 0.25   # 1/4 Kelly
ATR_STOP_MULTIPLIER    = 3.0
INITIAL_CAPITAL        = 100_000.0  # USD
MAX_RISK_PCT           = 0.02   # 單筆最大虧損佔總資金 2%（Kelly risk_amount 上限）
MAX_POSITION_PCT       = 0.10   # 單筆持倉市值上限 10%（position_size max_qty 上限）
MAX_TOTAL_POSITIONS    = 15     # 同時持倉上限
KELLY_MIN_TRADES       = 10     # 觸發 Kelly 所需最少交易紀錄

# 每個資產類別的同時持倉上限（名額隔離，非資金隔離）
# 各類別上限之和可大於 MAX_TOTAL_POSITIONS，整體仍受 MAX_TOTAL_POSITIONS 限制
MAX_POS_PER_CLASS: dict = {
    'US Stock':  6,
    'TW Stock':  6,
    'Crypto':    2,
    'Commodity': 2,
}

# ─── 資料庫 ────────────────────────────────────────
DB_PATH   = 'data/trading.db'
DATA_YEARS = 5

# ─── Bybit ────────────────────────────────────────
BYBIT_API_KEY    = os.environ.get('BYBIT_API_KEY',    '')
BYBIT_API_SECRET = os.environ.get('BYBIT_API_SECRET', '')
# 此為模擬帳號
BYBIT_DEMO       = True   # 模擬帳號（Demo Trading）設 True
BYBIT_TESTNET    = False  # 測試網（testnet.bybit.com）才設 True；一般模擬帳號設 False

# ─── 系統版號 ────────────────────────────────────────
SYSTEM_VERSION  = 'v1.2'

# ─── 輸出 ────────────────────────────────────────
OUTPUT_DIR      = 'output'
OUTPUT_FILENAME = 'Output.xlsx'
