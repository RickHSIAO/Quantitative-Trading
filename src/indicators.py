"""
Technical indicators — pure numpy/pandas, no external TA library needed.
All smoothing uses Wilder's RMA with SMA seed to match TradingView ta.rma / ta.atr / ta.rsi.
"""
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


# ─── Wilder's RMA（對齊 TradingView ta.rma）────────────────────────────────
def _rma(values: np.ndarray, period: int) -> np.ndarray:
    """
    Wilder's Running Moving Average：前 period 根用 SMA 作種子，
    之後 rma = (prev * (period-1) + cur) / period。
    與 TradingView ta.rma / ta.atr / ta.rsi 內部平滑完全一致。
    """
    n = len(values)
    result = np.full(n, np.nan)
    if n < period:
        return result
    result[period - 1] = np.nanmean(values[:period])
    for i in range(period, n):
        result[i] = (result[i - 1] * (period - 1) + values[i]) / period
    return result


# ─── ATR ────────────────────────────────────────────────────────────────────
def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series,
                period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr_arr = _rma(tr.values, period)
    return pd.Series(atr_arr, index=close.index)


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
    ATR uses Wilder's RMA with SMA seed (matches ta.supertrend in Pine Script).
    """
    h, l, c = df['High'].values, df['Low'].values, df['Close'].values
    n = len(c)

    tr = np.empty(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))

    atr = _rma(tr, period)

    hl2 = (h + l) / 2.0
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    direction   = np.zeros(n, dtype=int)

    for i in range(1, n):
        if np.isnan(atr[i]) or np.isnan(atr[i - 1]):
            direction[i] = direction[i-1]
            continue
        final_upper[i] = (basic_upper[i]
                          if basic_upper[i] < final_upper[i-1] or c[i-1] > final_upper[i-1]
                          else final_upper[i-1])
        final_lower[i] = (basic_lower[i]
                          if basic_lower[i] > final_lower[i-1] or c[i-1] < final_lower[i-1]
                          else final_lower[i-1])
        if direction[i-1] == -1:
            direction[i] = 1 if c[i] > final_upper[i] else -1
        else:
            direction[i] = -1 if c[i] < final_lower[i] else 1

    st_line = np.where(direction == 1, final_lower, final_upper)

    out = df.copy()
    out['supertrend']     = st_line
    out['supertrend_dir'] = direction
    return out


# ─── ADX ────────────────────────────────────────────────────────────────────
def compute_adx(df: pd.DataFrame, period: int = config.ADX_PERIOD) -> pd.DataFrame:
    """
    ADX + ±DI — Wilder's RMA with SMA seed, matches TradingView ta.adx / ta.dmi.
    Adds columns: adx, plus_di, minus_di
    """
    h, l, c = df['High'].values, df['Low'].values, df['Close'].values
    n = len(h)

    tr       = np.empty(n)
    plus_dm  = np.zeros(n)
    minus_dm = np.zeros(n)

    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))
        up   = h[i] - h[i-1]
        down = l[i-1] - l[i]
        plus_dm[i]  = up   if up > down and up > 0   else 0.0
        minus_dm[i] = down if down > up and down > 0 else 0.0

    tr_rma  = _rma(tr,       period)
    pdm_rma = _rma(plus_dm,  period)
    mdm_rma = _rma(minus_dm, period)

    with np.errstate(divide='ignore', invalid='ignore'):
        plus_di  = np.where(tr_rma > 0, 100.0 * pdm_rma / tr_rma, 0.0)
        minus_di = np.where(tr_rma > 0, 100.0 * mdm_rma / tr_rma, 0.0)
        denom    = plus_di + minus_di
        dx       = np.where(denom > 0, 100.0 * np.abs(plus_di - minus_di) / denom, 0.0)

    adx = _rma(dx, period)

    out = df.copy()
    out['adx']      = pd.Series(adx,      index=df.index)
    out['plus_di']  = pd.Series(plus_di,  index=df.index)
    out['minus_di'] = pd.Series(minus_di, index=df.index)
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
    bw    = (upper - lower) / mid.replace(0, np.nan) * 100

    out = df.copy()
    out['bb_upper'] = upper
    out['bb_mid']   = mid
    out['bb_lower'] = lower
    out['bb_bw']    = bw
    return out


# ─── RSI ────────────────────────────────────────────────────────────────────
def compute_rsi(df: pd.DataFrame, period: int = config.RSI_PERIOD) -> pd.DataFrame:
    delta = df['Close'].diff()
    gain  = delta.clip(lower=0).values
    loss  = (-delta).clip(lower=0).values

    avg_g = _rma(gain, period)
    avg_l = _rma(loss, period)

    with np.errstate(divide='ignore', invalid='ignore'):
        rs  = np.where(avg_l > 0, avg_g / avg_l, np.inf)
        rsi = np.where(np.isnan(avg_g) | np.isnan(avg_l), np.nan,
              np.where(avg_l == 0, 100.0,
              np.where(avg_g == 0,   0.0,
              100 - 100 / (1 + rs))))

    out = df.copy()
    out['rsi'] = pd.Series(rsi, index=df.index)
    return out


# ─── MACD ────────────────────────────────────────────────────────────────────
def compute_macd(df: pd.DataFrame,
                 fast: int   = config.MACD_FAST,
                 slow: int   = config.MACD_SLOW,
                 signal: int = config.MACD_SIGNAL) -> pd.DataFrame:
    ema_fast  = compute_ema(df['Close'], fast)
    ema_slow  = compute_ema(df['Close'], slow)
    macd_line = ema_fast - ema_slow
    sig_line  = macd_line.ewm(span=signal, adjust=False).mean()
    out = df.copy()
    out['macd']      = macd_line
    out['macd_sig']  = sig_line
    out['macd_hist'] = macd_line - sig_line
    return out


# ─── Volume Profile (VPVR) ───────────────────────────────────────────────────
def compute_volume_profile(df: pd.DataFrame,
                           bins: int = config.VOLUME_BINS,
                           lookback: int = config.VP_LOOKBACK) -> pd.DataFrame:
    """
    Rolling VPVR: POC, Value Area High (VAH), Value Area Low (VAL).
    Bin assignment uses floor/ceil to match TradingView f_rolling_poc exactly.
    """
    out = df.copy()
    out['poc'] = np.nan
    out['vah'] = np.nan
    out['val'] = np.nan

    lows    = df['Low'].values
    highs   = df['High'].values
    volumes = df['Volume'].values
    n       = len(df)

    for i in range(lookback - 1, n):
        s   = max(0, i - lookback + 1)   # 含當前 K 棒，共 lookback 根（對齊 TradingView）
        lo  = lows[s:i + 1]
        hi  = highs[s:i + 1]
        vol = volumes[s:i + 1]

        plo = lo.min()
        phi = hi.max()
        bsize = (phi - plo) / bins
        vol_clean = np.nan_to_num(vol, nan=0.0)   # 部分資料來源 Volume 含 NaN，防止 NaN 汙染整個 profile
        if bsize <= 0 or vol_clean.sum() == 0:
            continue

        vol_profile = np.zeros(bins)

        # TradingView-aligned：sb=floor, eb=ceil，含頭含尾
        sb_arr = np.clip(np.floor((lo - plo) / bsize).astype(int), 0, bins - 1)
        eb_arr = np.clip(np.ceil ((hi - plo) / bsize).astype(int), 0, bins - 1)
        for j in range(len(lo)):
            sb, eb = int(sb_arr[j]), int(eb_arr[j])
            nb = eb - sb + 1
            vol_profile[sb:eb + 1] += vol_clean[j] / nb

        poc_idx   = int(np.argmax(vol_profile))
        poc_price = plo + (poc_idx + 0.5) * bsize
        out.iat[i, out.columns.get_loc('poc')] = poc_price

        total   = vol_profile.sum()
        sorted_ = np.argsort(vol_profile)[::-1]
        cum, va = 0.0, []
        for idx in sorted_:
            cum += vol_profile[idx]
            va.append(idx)
            if cum >= 0.70 * total:
                break
        centers = plo + (np.arange(bins) + 0.5) * bsize
        out.iat[i, out.columns.get_loc('vah')] = centers[max(va)]
        out.iat[i, out.columns.get_loc('val')] = centers[min(va)]

    return out


# ─── Compute All ─────────────────────────────────────────────────────────────
def compute_all_indicators(df: pd.DataFrame, include_vp: bool = True) -> pd.DataFrame:
    df = compute_supertrend(df)
    for p in config.EMA_FAST_PERIODS:
        df[f'ema{p}'] = compute_ema(df['Close'], p)
    df['ema200'] = compute_ema(df['Close'], config.EMA_PERIOD)
    df = compute_bollinger(df)
    df = compute_rsi(df)
    df['atr'] = compute_atr(df['High'], df['Low'], df['Close'], config.ATR_PERIOD)
    df = compute_adx(df)
    df = compute_macd(df)
    if include_vp:
        df = compute_volume_profile(df)
    return df
