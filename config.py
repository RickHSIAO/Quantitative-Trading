import random

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
    'DIS','CMCSA','VZ','T','TMUS','CHTR','FOXA','WBD','NFLX','SIRI',
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
    '5388.TW','6239.TW','6271.TW','6278.TW','6285.TW','6289.TW','6290.TW',
    '5347.TW','3443.TW',
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

# ─── 加密貨幣 ────────────────────────────────────────
CRYPTO_FIXED = ['BTC-USD', 'ETH-USD', 'ADA-USD']
CRYPTO_POOL = [
    'SOL-USD','BNB-USD','XRP-USD','DOT-USD','AVAX-USD','MATIC-USD',
    'LINK-USD','UNI-USD','ATOM-USD','NEAR-USD','FTM-USD','ALGO-USD',
    'VET-USD','ICP-USD','SAND-USD','MANA-USD','AXS-USD','THETA-USD',
    'FIL-USD','HBAR-USD','EOS-USD','DOGE-USD','LTC-USD','BCH-USD',
    'AAVE-USD','COMP-USD','SNX-USD','CRV-USD','GRT-USD','FLOW-USD',
    'EGLD-USD','ONE-USD','ZIL-USD','CHZ-USD','MINA-USD','APT-USD',
]

# ─── 大宗商品 ────────────────────────────────────────
COMMODITIES = ['GC=F', 'SI=F']  # 黃金, 白銀

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
BB_PERIOD              = 20
BB_STD                 = 2.0
RSI_PERIOD             = 14
ATR_PERIOD             = 14
VOLUME_BINS            = 80
VP_LOOKBACK            = 252  # 1年

# ─── 風控參數 ────────────────────────────────────────
RISK_REWARD_RATIO      = 3.0    # 1:3
KELLY_FRACTION         = 0.25   # 1/4 Kelly
ATR_STOP_MULTIPLIER    = 2.0
INITIAL_CAPITAL        = 100_000.0  # USD
MAX_POSITION_PCT       = 0.10   # 單筆最大倉位 10%
MAX_TOTAL_POSITIONS    = 15     # 同時持倉上限
KELLY_MIN_TRADES       = 10     # 觸發 Kelly 所需最少交易紀錄

# ─── 資料庫 ────────────────────────────────────────
DB_PATH   = 'data/trading.db'
DATA_YEARS = 5

# ─── Bybit ────────────────────────────────────────
BYBIT_API_KEY    = 'v3rxkOnsC0ZNyK6qrN'
BYBIT_API_SECRET = 'hhSHbry624FWBQRPXXZOOAzWOSZEK2wISojN'
# 此為模擬帳號
BYBIT_DEMO       = True   # 模擬帳號（Demo Trading）設 True
BYBIT_TESTNET    = False  # 測試網（testnet.bybit.com）才設 True；一般模擬帳號設 False

# ─── 輸出 ────────────────────────────────────────
OUTPUT_DIR      = 'output'
OUTPUT_FILENAME = 'Output.xlsx'
