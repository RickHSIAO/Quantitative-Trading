"""
Three independent signal generators.
Signal values: +1 = LONG, -1 = SHORT, 0 = FLAT
"""
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

LONG  =  1
SHORT = -1
FLAT  =  0


# ─── 策略 1：趨勢動能 (Supertrend) ───────────────────────────────────────────
def trend_following_signals(df: pd.DataFrame) -> pd.Series:
    """
    只在 Supertrend 方向反轉那根 K 棒觸發訊號（對齊 Pine Script）：
      -1 → +1 翻多 / +1 → -1 翻空
    EMA200 環境濾網由 combine_signals 統一處理，此處只負責觸發訊號。
    """
    sig = pd.Series(FLAT, index=df.index, dtype=int)
    if 'supertrend_dir' not in df.columns:
        return sig

    dir_chg = df['supertrend_dir'].diff()
    sig[dir_chg > 0] = LONG   # -1 → +1
    sig[dir_chg < 0] = SHORT  # +1 → -1
    return sig


# ─── 策略 2：成交量分布 POC 支撐/阻力 ────────────────────────────────────────
def volume_profile_signals(df: pd.DataFrame, tol: float = 0.015) -> pd.Series:
    """
    價格接近 POC（±tol）時判斷多空方向：
    - 前一根 Close 高於 POC → 從上方跌回 POC（支撐）→ 做多
    - 前一根 Close 低於 POC → 從下方漲到 POC（壓力）→ 做空
    同時配合 RSI 避免追高殺低。
    """
    sig = pd.Series(FLAT, index=df.index, dtype=int)
    if 'poc' not in df.columns or 'rsi' not in df.columns:
        return sig

    near_poc = (
        (df['Close'] >= df['poc'] * (1 - tol)) &
        (df['Close'] <= df['poc'] * (1 + tol))
    )
    # prev_above: 從上方跌到 POC → POC 扮演支撐 → 做多
    # prev_below: 從下方漲到 POC → POC 扮演壓力 → 做空
    prev_above = df['Close'].shift(1) > df['poc']
    prev_below = df['Close'].shift(1) < df['poc']

    long_  = near_poc & prev_above & (df['rsi'] < 60)
    short_ = near_poc & prev_below & (df['rsi'] > 40)

    sig[long_]  = LONG
    sig[short_] = SHORT
    return sig


# ─── 策略 3：布林通道均值回歸 ─────────────────────────────────────────────────
def bollinger_reversion_signals(df: pd.DataFrame,
                                rsi_oversold: int = 30,
                                rsi_overbought: int = 70,
                                bw_multiplier: float = 1.5) -> pd.Series:
    """
    做多：Close <= bb_lower  AND  RSI < 30  AND  ATR 正常（非極端波動）
    做空：Close >= bb_upper  AND  RSI > 70  AND  ATR 正常
    ATR 過濾：布林帶寬 < 50日均值 * bw_multiplier
    """
    sig = pd.Series(FLAT, index=df.index, dtype=int)
    needed = ['bb_upper', 'bb_lower', 'bb_bw', 'rsi']
    if not all(c in df.columns for c in needed):
        return sig

    bw_mean      = df['bb_bw'].rolling(50).mean()
    normal_vol   = df['bb_bw'] < bw_mean * bw_multiplier
    not_first_50 = df['bb_bw'].rolling(50).count() >= 50

    long_  = (df['Close'] <= df['bb_lower']) & (df['rsi'] < rsi_oversold)  & normal_vol & not_first_50
    short_ = (df['Close'] >= df['bb_upper']) & (df['rsi'] > rsi_overbought) & normal_vol & not_first_50

    sig[long_]  = LONG
    sig[short_] = SHORT
    return sig


# ─── EMA 比例分數 ─────────────────────────────────────────────────────────────
def _ema_scores(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """
    計算多空 EMA 比例分數（各 0–4）。
    讀取 df 中所有 ema{p} 欄位（EMA20/50/100/200）：
      收盤高於該 EMA → 多頭 +1
      收盤低於該 EMA → 空頭 +1
    分數越高代表多空排列越整齊，環境越強。
    """
    periods = config.EMA_FAST_PERIODS + [config.EMA_PERIOD]   # [20, 50, 100, 200]
    bull = pd.Series(0, index=df.index, dtype=int)
    bear = pd.Series(0, index=df.index, dtype=int)
    for p in periods:
        col = f'ema{p}'
        if col in df.columns:
            bull += (df['Close'] > df[col]).astype(int)
            bear += (df['Close'] < df[col]).astype(int)
    return bull, bear


# ─── 主從濾網合併 ─────────────────────────────────────────────────────────────
def combine_signals(df: pd.DataFrame,
                    tf: pd.Series, vp: pd.Series, bb: pd.Series,
                    ema_min_score: int = config.EMA_MIN_SCORE) -> pd.Series:
    """
    EMA 比例分數環境濾網：
    多頭/空頭分數 = 收盤高/低於幾根 EMA（EMA20/50/100/200）。
    達到 ema_min_score 根（預設 2/4）才開放該方向的進場訊號。

    分數含義：
      4 = 完美多頭排列（收盤全數高於 EMA20>50>100>200）
      3 = 強多頭環境
      2 = 溫和多頭環境（預設門檻）
      1 = 混沌，禁止進場
      0 = 完全相反方向
    """
    bull_ema, bear_ema = _ema_scores(df)

    bull_env = bull_ema >= ema_min_score
    bear_env = bear_ema >= ema_min_score

    any_long  = (tf == LONG)  | (vp == LONG)  | (bb == LONG)
    any_short = (tf == SHORT) | (vp == SHORT) | (bb == SHORT)

    result = pd.Series(FLAT, index=tf.index, dtype=int)
    result[bull_env & any_long]  = LONG
    result[bear_env & any_short] = SHORT
    return result


def generate_all_signals(df: pd.DataFrame) -> dict[str, pd.Series]:
    tf       = trend_following_signals(df)
    vp       = volume_profile_signals(df)
    bb       = bollinger_reversion_signals(df)
    combined = combine_signals(df, tf, vp, bb)

    # 子策略共識分數（1–3）
    long_strat  = (tf == LONG).astype(int)  + (vp == LONG).astype(int)  + (bb == LONG).astype(int)
    short_strat = (tf == SHORT).astype(int) + (vp == SHORT).astype(int) + (bb == SHORT).astype(int)

    # EMA 比例分數（0–4）
    bull_ema, bear_ema = _ema_scores(df)

    # 總分 = 子策略分數（1–3）+ EMA 對齊分數（0–4），最高 7 分
    score = pd.Series(0, index=combined.index, dtype=int)
    score[combined == LONG]  = long_strat[combined == LONG]  + bull_ema[combined == LONG]
    score[combined == SHORT] = short_strat[combined == SHORT] + bear_ema[combined == SHORT]

    return {
        'trend':    tf,
        'vp':       vp,
        'bb':       bb,
        'combined': combined,
        'score':    score,
        'ema_bull': bull_ema,
        'ema_bear': bear_ema,
    }
