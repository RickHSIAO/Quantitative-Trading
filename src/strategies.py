"""
Three independent signal generators.
Signal values: +1 = LONG, -1 = SHORT, 0 = FLAT
"""
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from typing import Optional

LONG  =  1
SHORT = -1
FLAT  =  0


# ─── 大盤護城河濾網 ───────────────────────────────────────────────────────────
def _market_moat_filter(df: pd.DataFrame,
                         asset_type: str,
                         benchmark_df: Optional[pd.DataFrame],
                         rs_pct: float = config.RS_OUTPERFORM_PCT) -> pd.Series:
    """
    True = 市場環境允許做多進場。
    台股：加權指數 > SMA250，否則封鎖多單；
          近 RS_LOOKBACK_DAYS 天個股漲幅超越大盤 RS_OUTPERFORM_PCT 可豁免。
    美股：S&P500 > SMA200，邏輯相同。
    其他類別：永遠 True（不限制）。
    """
    if benchmark_df is None or asset_type not in ('TW Stock', 'US Stock'):
        return pd.Series(True, index=df.index)

    ma_period = config.TW_MARKET_MA_PERIOD if asset_type == 'TW Stock' else config.US_MARKET_MA_PERIOD
    bm_close  = benchmark_df['Close']
    bm_ma     = bm_close.rolling(ma_period).mean()

    bm_above  = (bm_close >= bm_ma).reindex(df.index, method='ffill').fillna(False)

    stock_ret = df['Close'].pct_change(config.RS_LOOKBACK_DAYS)
    bm_ret    = bm_close.pct_change(config.RS_LOOKBACK_DAYS) \
                        .reindex(df.index, method='ffill').fillna(0)
    rs_strong = ((stock_ret - bm_ret) > rs_pct).fillna(False)

    return bm_above | rs_strong


# ─── 策略 1：趨勢動能 (Supertrend) ───────────────────────────────────────────
def trend_following_signals(df: pd.DataFrame, asset_type: str = '') -> pd.Series:
    """
    只在 Supertrend 方向反轉那根 K 棒觸發訊號（對齊 Pine Script）：
      -1 → +1 翻多 / +1 → -1 翻空
    EMA200 環境濾網由 combine_signals 統一處理，此處只負責觸發訊號。
    美股額外要求：Supertrend 翻多時 MACD > 0 且柱狀圖 > 0（雙重確認，過濾假突破）。
    """
    sig = pd.Series(FLAT, index=df.index, dtype=int)
    if 'supertrend_dir' not in df.columns:
        return sig

    dir_chg = df['supertrend_dir'].diff()
    sig[dir_chg > 0] = LONG   # -1 → +1
    sig[dir_chg < 0] = SHORT  # +1 → -1

    # 美股 HFT 假突破過濾：MACD 柱狀圖 > 0（動能由空轉多）才允許做多
    # 只要求 hist > 0，不強求 macd > 0，避免 MACD 滯後砍掉早期有效翻多
    if config.ENABLE_US_MACD_FILTER and asset_type == 'US Stock' and 'macd_hist' in df.columns:
        sig[(sig == LONG) & (df['macd_hist'] <= 0)] = FLAT

    return sig


# ─── 策略 2：成交量分布 POC 支撐/阻力 ────────────────────────────────────────
def volume_profile_signals(df: pd.DataFrame, tol: float = config.VP_POC_TOLERANCE) -> pd.Series:
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

    bw_mean        = df['bb_bw'].rolling(50).mean()
    normal_vol     = df['bb_bw'] < bw_mean * bw_multiplier
    has_bw_history = df['bb_bw'].rolling(50).count() >= 50   # 前 BB_PERIOD+50 棒暖身完成

    long_  = (df['Close'] <= df['bb_lower']) & (df['rsi'] < rsi_oversold)  & normal_vol & has_bw_history
    short_ = (df['Close'] >= df['bb_upper']) & (df['rsi'] > rsi_overbought) & normal_vol & has_bw_history

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
                    ema_min_score: int = config.EMA_MIN_SCORE,
                    asset_type: str = '',
                    benchmark_df: Optional[pd.DataFrame] = None,
                    moat_tf_only: bool = False,
                    rs_pct: float = config.RS_OUTPERFORM_PCT) -> pd.Series:
    """
    EMA 比例分數環境濾網 + 市場護城河 + 處置股/籌碼濾網。

    moat_tf_only=True：護城河只封鎖 Supertrend 多單，VP/BB 均值回歸訊號豁免。
    rs_pct：覆蓋 RS_OUTPERFORM_PCT，用於測試不同豁免門檻。
    """
    bull_ema, bear_ema = _ema_scores(df)
    bull_env = bull_ema >= ema_min_score
    bear_env = bear_ema >= ema_min_score

    if 'ema200' in df.columns and 'ema50' in df.columns:
        ema200_slope = df['ema200'].diff(config.EMA200_SLOPE_PERIOD)
        early_bear = (df['Close'] < df['ema50']) & (ema200_slope < 0)
        early_bull = (df['Close'] > df['ema50']) & (ema200_slope > 0)
        bull_env = bull_env & ~early_bear
        bear_env = bear_env & ~early_bull

    market_long_ok = _market_moat_filter(df, asset_type, benchmark_df, rs_pct=rs_pct)

    not_disposed = (~df['is_disposition'].astype(bool)) \
                   if 'is_disposition' in df.columns \
                   else pd.Series(True, index=df.index)

    chip_ok = (df['chip_buy_days'] >= config.TW_CHIP_MIN_DAYS) \
              if 'chip_buy_days' in df.columns \
              else pd.Series(True, index=df.index)

    if moat_tf_only:
        # 護城河只管 Supertrend；VP/BB 均值回歸繞過
        tf_long_ok  = (tf == LONG)  & market_long_ok
        other_long  = (vp == LONG)  | (bb == LONG)
        any_long    = tf_long_ok    | other_long
    else:
        any_long    = ((tf == LONG) | (vp == LONG) | (bb == LONG)) & market_long_ok

    any_short = (tf == SHORT) | (vp == SHORT) | (bb == SHORT)

    result = pd.Series(FLAT, index=tf.index, dtype=int)
    result[bull_env & any_long  & chip_ok & not_disposed] = LONG
    result[bear_env & any_short & not_disposed]           = SHORT

    conflict = (bull_env & any_long  & chip_ok & not_disposed &
                bear_env & any_short & not_disposed)
    result[conflict & (bull_ema >  bear_ema)] = LONG
    result[conflict & (bull_ema <  bear_ema)] = SHORT
    result[conflict & (bull_ema == bear_ema)] = FLAT
    return result


def generate_all_signals(df: pd.DataFrame,
                          asset_type: str = '',
                          benchmark_df: Optional[pd.DataFrame] = None,
                          moat_tf_only: bool = False,
                          rs_pct: float = config.RS_OUTPERFORM_PCT) -> dict[str, pd.Series]:
    tf       = trend_following_signals(df, asset_type)
    vp       = volume_profile_signals(df)
    bb       = bollinger_reversion_signals(df)
    combined = combine_signals(df, tf, vp, bb, asset_type=asset_type,
                               benchmark_df=benchmark_df,
                               moat_tf_only=moat_tf_only, rs_pct=rs_pct)

    # 子策略共識分數（1–3）
    # moat_tf_only=True 時，Supertrend 多單受護城河限制；評分只計通過護城河的 tf 多單
    if moat_tf_only:
        market_ok    = _market_moat_filter(df, asset_type, benchmark_df, rs_pct=rs_pct)
        tf_long_eff  = (tf == LONG) & market_ok
        tf_short_eff = (tf == SHORT)
    else:
        tf_long_eff  = (tf == LONG)
        tf_short_eff = (tf == SHORT)
    long_strat  = tf_long_eff.astype(int)  + (vp == LONG).astype(int)  + (bb == LONG).astype(int)
    short_strat = tf_short_eff.astype(int) + (vp == SHORT).astype(int) + (bb == SHORT).astype(int)

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
