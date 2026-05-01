"""
Three independent signal generators.
Signal values: +1 = LONG, -1 = SHORT, 0 = FLAT
"""
import pandas as pd
import numpy as np

LONG  =  1
SHORT = -1
FLAT  =  0


# ─── 策略 1：趨勢動能 (Supertrend + EMA 200) ──────────────────────────────────
def trend_following_signals(df: pd.DataFrame) -> pd.Series:
    """
    做多：supertrend_dir == +1  AND  Close > EMA200
    做空：supertrend_dir == -1  AND  Close < EMA200
    """
    sig = pd.Series(FLAT, index=df.index, dtype=int)
    if 'supertrend_dir' not in df.columns or 'ema200' not in df.columns:
        return sig

    long_  = (df['supertrend_dir'] == 1)  & (df['Close'] > df['ema200'])
    short_ = (df['supertrend_dir'] == -1) & (df['Close'] < df['ema200'])

    sig[long_]  = LONG
    sig[short_] = SHORT
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


# ─── 主從濾網合併 ─────────────────────────────────────────────────────────────
def combine_signals(df: pd.DataFrame,
                    tf: pd.Series, vp: pd.Series, bb: pd.Series) -> pd.Series:
    """
    以 EMA200 趨勢方向為環境濾網（主），各策略只在大方向一致時才允許進場（從）。
    - 多頭環境（Close > EMA200）：只接受 LONG 訊號
    - 空頭環境（Close < EMA200）：只接受 SHORT 訊號
    """
    result = pd.Series(FLAT, index=tf.index, dtype=int)

    if 'ema200' not in df.columns:
        return result

    # 使用 >= / <= 避免 Close 剛好等於 EMA200 時雙邊皆為 False 封鎖所有訊號
    bull_env = df['Close'] >= df['ema200']
    bear_env = df['Close'] <= df['ema200']

    any_long  = (tf == LONG)  | (vp == LONG)  | (bb == LONG)
    any_short = (tf == SHORT) | (vp == SHORT) | (bb == SHORT)

    result[bull_env & any_long]  = LONG
    result[bear_env & any_short] = SHORT
    return result


def generate_all_signals(df: pd.DataFrame) -> dict[str, pd.Series]:
    tf = trend_following_signals(df)
    vp = volume_profile_signals(df)
    bb = bollinger_reversion_signals(df)
    return {
        'trend':    tf,
        'vp':       vp,
        'bb':       bb,
        'combined': combine_signals(df, tf, vp, bb),
    }
