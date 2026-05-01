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
    - 前一根 Close 低於 POC → 反彈做多
    - 前一根 Close 高於 POC → 壓力做空
    同時配合 RSI 避免追高殺低。
    """
    sig = pd.Series(FLAT, index=df.index, dtype=int)
    if 'poc' not in df.columns or 'rsi' not in df.columns:
        return sig

    near_poc = (
        (df['Close'] >= df['poc'] * (1 - tol)) &
        (df['Close'] <= df['poc'] * (1 + tol))
    )
    prev_below = df['Close'].shift(1) < df['poc']
    prev_above = df['Close'].shift(1) > df['poc']

    long_  = near_poc & prev_below & (df['rsi'] < 60)
    short_ = near_poc & prev_above & (df['rsi'] > 40)

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


# ─── 多數決合併 ───────────────────────────────────────────────────────────────
def combine_signals(tf: pd.Series, vp: pd.Series, bb: pd.Series,
                    threshold: int = 2) -> pd.Series:
    """
    至少 threshold 個策略同向才產生信號。
    threshold=2 → 三取二，減少假訊號。
    """
    vote = tf + vp + bb
    result = pd.Series(FLAT, index=tf.index, dtype=int)
    result[vote >=  threshold] = LONG
    result[vote <= -threshold] = SHORT
    return result


def generate_all_signals(df: pd.DataFrame,
                         threshold: int = 2) -> dict[str, pd.Series]:
    """
    threshold=1: 任一策略觸發即交易（較激進，交易次數多）
    threshold=2: 至少兩個策略同向（預設，平衡品質與數量）
    threshold=3: 三策略全同向（最保守，高品質信號）
    """
    tf = trend_following_signals(df)
    vp = volume_profile_signals(df)
    bb = bollinger_reversion_signals(df)
    return {
        'trend':    tf,
        'vp':       vp,
        'bb':       bb,
        'combined': combine_signals(tf, vp, bb, threshold=threshold),
    }
