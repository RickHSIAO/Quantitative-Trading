"""
Technical indicators — pure numpy/pandas, no external TA library needed.
"""
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


# ─── ATR ────────────────────────────────────────────────────────────────────
def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series,
                period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    # Wilder smoothing
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    return atr


# ─── EMA ────────────────────────────────────────────────────────────────────
def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


# ─── Supertrend ─────────────────────────────────────────────────────────────
def compute_supertrend(df: pd.DataFrame,
                       period: int = config.SUPERTREND_ATR_PERIOD,
                       multiplier: float = config.SUPERTREND_MULTIPLIER
                       ) -> pd.DataFrame:
    """
    Returns df with columns: supertrend, supertrend_dir
    supertrend_dir: +1 = bullish, -1 = bearish
    """
    h, l, c = df['High'].values, df['Low'].values, df['Close'].values
    n = len(c)

    # ATR (Wilder)
    tr = np.empty(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))

    atr = np.empty(n)
    atr[0] = tr[0]
    alpha = 1.0 / period
    for i in range(1, n):
        atr[i] = alpha * tr[i] + (1 - alpha) * atr[i-1]

    hl2 = (h + l) / 2.0
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    direction   = np.ones(n, dtype=int)
    direction[0] = 1 if c[0] >= hl2[0] else -1
    st_line     = np.empty(n)

    for i in range(1, n):
        # Ratchet bands
        final_upper[i] = (basic_upper[i]
                          if basic_upper[i] < final_upper[i-1] or c[i-1] > final_upper[i-1]
                          else final_upper[i-1])
        final_lower[i] = (basic_lower[i]
                          if basic_lower[i] > final_lower[i-1] or c[i-1] < final_lower[i-1]
                          else final_lower[i-1])
        # Direction flip
        if direction[i-1] == -1:
            direction[i] = 1 if c[i] > final_upper[i] else -1
        else:
            direction[i] = -1 if c[i] < final_lower[i] else 1

    st_line = np.where(direction == 1, final_lower, final_upper)

    out = df.copy()
    out['supertrend']     = st_line
    out['supertrend_dir'] = direction
    return out


# ─── Bollinger Bands ─────────────────────────────────────────────────────────
def compute_bollinger(df: pd.DataFrame,
                      period: int = config.BB_PERIOD,
                      std_mult: float = config.BB_STD) -> pd.DataFrame:
    roll  = df['Close'].rolling(period)
    mid   = roll.mean()
    std   = roll.std(ddof=0)
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    bw    = (upper - lower) / mid.replace(0, np.nan) * 100  # bandwidth %

    out = df.copy()
    out['bb_upper'] = upper
    out['bb_mid']   = mid
    out['bb_lower'] = lower
    out['bb_bw']    = bw
    return out


# ─── RSI ────────────────────────────────────────────────────────────────────
def compute_rsi(df: pd.DataFrame, period: int = config.RSI_PERIOD) -> pd.DataFrame:
    delta = df['Close'].diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    alpha = 1.0 / period
    avg_g = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_l = loss.ewm(alpha=alpha, adjust=False).mean()
    rs  = avg_g / avg_l.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    # avg_l==0 (純上漲) → RSI=100；avg_g==0 (純下跌) → RSI=0
    rsi = rsi.where(avg_l != 0, 100.0)
    rsi = rsi.where(avg_g != 0, 0.0)

    out = df.copy()
    out['rsi'] = rsi
    return out


# ─── Volume Profile (VPVR) ───────────────────────────────────────────────────
def compute_volume_profile(df: pd.DataFrame,
                           bins: int = config.VOLUME_BINS,
                           lookback: int = config.VP_LOOKBACK) -> pd.DataFrame:
    """
    Rolling VPVR: POC, Value Area High (VAH), Value Area Low (VAL).
    Only computed where lookback bars are available.
    """
    out = df.copy()
    out['poc'] = np.nan
    out['vah'] = np.nan
    out['val'] = np.nan

    lows    = df['Low'].values
    highs   = df['High'].values
    volumes = df['Volume'].values
    n       = len(df)

    for i in range(lookback, n):
        s   = max(0, i - lookback)
        lo  = lows[s:i]
        hi  = highs[s:i]
        vol = volumes[s:i]

        pmin, pmax = lo.min(), hi.max()
        if pmax < pmin or vol.sum() == 0:
            continue

        edges       = np.linspace(pmin, pmax, bins + 1)
        vol_profile = np.zeros(bins)

        # Distribute each candle's volume across overlapping bins
        starts = np.searchsorted(edges[1:], lo,  side='left')
        ends   = np.searchsorted(edges[:-1], hi, side='right')
        for j in range(len(lo)):
            sb, eb = starts[j], min(ends[j], bins)
            nb = eb - sb
            if nb > 0:
                vol_profile[sb:eb] += vol[j] / nb

        poc_idx = int(np.argmax(vol_profile))
        centers = (edges[:-1] + edges[1:]) / 2
        out.iat[i, out.columns.get_loc('poc')] = centers[poc_idx]

        # Value Area = top 70% of volume
        total   = vol_profile.sum()
        sorted_ = np.argsort(vol_profile)[::-1]
        cum, va = 0.0, []
        for idx in sorted_:
            cum += vol_profile[idx]
            va.append(idx)
            if cum >= 0.70 * total:
                break
        out.iat[i, out.columns.get_loc('vah')] = centers[max(va)]
        out.iat[i, out.columns.get_loc('val')] = centers[min(va)]

    return out


# ─── Compute All ─────────────────────────────────────────────────────────────
def compute_all_indicators(df: pd.DataFrame, include_vp: bool = True) -> pd.DataFrame:
    df = compute_supertrend(df)
    df['ema200'] = compute_ema(df['Close'], config.EMA_PERIOD)
    df = compute_bollinger(df)
    df = compute_rsi(df)
    df['atr'] = compute_atr(df['High'], df['Low'], df['Close'], config.ATR_PERIOD)
    if include_vp:
        df = compute_volume_profile(df)
    return df
