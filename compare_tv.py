"""
TradingView vs Python APR 對齊腳本
對齊 TradingView 執行模型：
  - 入場：訊號K棒收盤 → 下一根開盤成交
  - 追蹤峰值：用 High（多）/ Low（空），而非收盤價
  - SL 距離：固定於入場 ATR（不隨後續 ATR 更新）
  - SL/TP：用 High/Low 判斷日內觸發，SL 優先
  - Flip 平倉：下一根開盤成交
  - 場上有倉不開單
"""
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from src.database import load_prices
from src.indicators import compute_all_indicators
import config

# ─── 參數（與 TradingView 對齊）─────────────────────────────────────────────
SYMBOL          = 'BYBIT:BTCUSDT.P'
START           = '2022-01-01'
END             = '2026-05-02'
INITIAL_CAPITAL = 100_000.0
EQUITY_PCT      = 0.10
COMMISSION_PCT  = 0.001
ATR_SL_MULT     = 2.0
RR_RATIO        = 3.0
ST_PERIOD       = config.SUPERTREND_ATR_PERIOD   # 10
ST_MULT         = config.SUPERTREND_MULTIPLIER   # 3.0
VP_TOL          = 0.015   # ±1.5% POC 容差
RSI_OS          = 30
RSI_OB          = 70
BB_BW_MULT      = 1.5


def _signals(df: pd.DataFrame) -> pd.Series:
    """完整複製 Pine Script 三策略合併邏輯"""
    # ── Supertrend：只在方向改變那根觸發 ────────────────────────────────────
    dir_now  = df['supertrend_dir']
    dir_prev = dir_now.shift(1)
    sig_tf   = pd.Series(0, index=df.index)
    sig_tf[(dir_now == 1)  & (dir_prev == -1)] =  1
    sig_tf[(dir_now == -1) & (dir_prev ==  1)] = -1

    # ── VP POC ──────────────────────────────────────────────────────────────
    sig_vp = pd.Series(0, index=df.index)
    if 'poc' in df.columns:
        near = (df['Close'] >= df['poc'] * (1 - VP_TOL)) & \
               (df['Close'] <= df['poc'] * (1 + VP_TOL))
        prev_abv = df['Close'].shift(1) > df['poc']
        prev_blw = df['Close'].shift(1) < df['poc']
        sig_vp[near & prev_abv & (df['rsi'] < 60)] =  1
        sig_vp[near & prev_blw & (df['rsi'] > 40)] = -1

    # ── Bollinger 均值回歸 ───────────────────────────────────────────────────
    sig_bb = pd.Series(0, index=df.index)
    if 'bb_upper' in df.columns and 'bb_bw' in df.columns:
        bw_mean    = df['bb_bw'].rolling(50).mean()
        normal_vol = df['bb_bw'] < bw_mean * BB_BW_MULT
        ready      = df['bb_bw'].rolling(50).count() >= 50
        sig_bb[(df['Close'] <= df['bb_lower']) & (df['rsi'] < RSI_OS) & normal_vol & ready] =  1
        sig_bb[(df['Close'] >= df['bb_upper']) & (df['rsi'] > RSI_OB) & normal_vol & ready] = -1

    # ── EMA200 環境濾網合併 ──────────────────────────────────────────────────
    bull_env  = df['Close'] > df['ema200']
    bear_env  = df['Close'] < df['ema200']
    any_long  = (sig_tf == 1)  | (sig_vp == 1)  | (sig_bb == 1)
    any_short = (sig_tf == -1) | (sig_vp == -1) | (sig_bb == -1)

    sig = pd.Series(0, index=df.index)
    sig[bull_env & any_long]  =  1
    sig[bear_env & any_short] = -1
    return sig


def run():
    df = load_prices(SYMBOL, START, END)
    if df.empty:
        print(f'[ERROR] 找不到 {SYMBOL}，請先執行 fetch。')
        return

    df = compute_all_indicators(df, include_vp=True)
    sig = _signals(df)

    # ── 回測模擬（對齊 TradingView 執行模型）────────────────────────────────
    capital       = INITIAL_CAPITAL
    position      = None
    pending_entry = None   # {'dir': int, 'atr': float} 下一根開盤入場
    pending_close = False  # Flip 下一根開盤平倉
    trades        = []
    equity_log    = []

    for dt, row in df.iterrows():
        o = float(row['Open'])
        h = float(row['High'])
        l = float(row['Low'])
        c = float(row['Close'])
        atr = float(row.get('atr', np.nan))
        if np.isnan(atr) or atr <= 0:
            atr = c * 0.02
        s = int(sig.loc[dt])

        # ── Step 0a: Flip 平倉（上一根訊號，本根開盤成交）────────────────────
        if pending_close and position is not None:
            d    = position['dir']
            pnl  = (o - position['entry']) * position['qty'] * d
            comm = o * position['qty'] * COMMISSION_PCT
            capital += pnl - comm
            trades.append({'pnl': pnl - comm, 'reason': 'Flip',
                           'date': dt.strftime('%Y-%m-%d')})
            position     = None
            pending_close = False

        # ── Step 0b: 待入場（上一根訊號，本根開盤成交）──────────────────────
        if pending_entry is not None and position is None:
            pdir    = pending_entry['dir']
            sl_dist = pending_entry['atr'] * ATR_SL_MULT   # 固定 SL 距離
            sl      = o - sl_dist if pdir == 1 else o + sl_dist
            tp      = o + sl_dist * RR_RATIO if pdir == 1 else o - sl_dist * RR_RATIO
            qty     = (capital * EQUITY_PCT) / o
            comm    = o * qty * COMMISSION_PCT
            capital -= comm
            position      = {'dir': pdir, 'entry': o, 'sl': sl, 'tp': tp,
                             'qty': qty, 'trail_peak': o, 'sl_dist': sl_dist}
            pending_entry = None

        # ── Step 1: SL/TP 檢查 → 再更新追蹤止損（對齊 TradingView 時序）────
        # TradingView：trail_peak 在 K 棒收盤後更新，新 SL 從下一根才生效
        # 所以本根用「上一根收盤後設定」的 sl 做判斷，再更新供下一根用
        if position is not None:
            d       = position['dir']
            sl_dist = position['sl_dist']

            # 先用前一根留下的 sl/tp 判斷出場
            hit_tp = (d ==  1 and h >= position['tp']) or \
                     (d == -1 and l <= position['tp'])
            hit_sl = (not hit_tp) and (
                (d ==  1 and l <= position['sl']) or
                (d == -1 and h >= position['sl'])
            )

            if hit_sl or hit_tp:
                ep   = position['sl'] if hit_sl else position['tp']
                pnl  = (ep - position['entry']) * position['qty'] * d
                comm = ep * position['qty'] * COMMISSION_PCT
                capital += pnl - comm
                trades.append({'pnl': pnl - comm,
                               'reason': 'SL' if hit_sl else 'TP',
                               'date': dt.strftime('%Y-%m-%d')})
                position = None
            else:
                # 未出場：更新追蹤峰值，新 SL 下一根生效
                if d == 1:
                    position['trail_peak'] = max(position['trail_peak'], h)
                    new_sl = position['trail_peak'] - sl_dist
                    if new_sl > position['sl']:
                        position['sl'] = new_sl
                else:
                    position['trail_peak'] = min(position['trail_peak'], l)
                    new_sl = position['trail_peak'] + sl_dist
                    if new_sl < position['sl']:
                        position['sl'] = new_sl

                if s != 0 and s != position['dir']:
                    # Flip：下一根開盤平倉
                    pending_close = True

        # ── Step 2: 若無倉，掛入場單（下一根開盤成交）──────────────────────
        if position is None and not pending_close and s != 0:
            pending_entry = {'dir': s, 'atr': atr}

        equity_log.append({'date': dt, 'equity': capital})

    # ── 強制平倉最後一筆 ────────────────────────────────────────────────────
    if position is not None:
        price = float(df.iloc[-1]['Close'])
        d     = position['dir']
        pnl   = (price - position['entry']) * position['qty'] * d
        comm  = price * position['qty'] * COMMISSION_PCT
        capital += pnl - comm
        trades.append({'pnl': pnl - comm, 'reason': 'EOD',
                       'date': df.index[-1].strftime('%Y-%m-%d')})

    # ── 統計 ─────────────────────────────────────────────────────────────────
    days      = (df.index[-1] - df.index[0]).days
    years     = days / 365
    total_ret = (capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    apr       = ((capital / INITIAL_CAPITAL) ** (1 / years) - 1) * 100 if years > 0 else 0

    pnls     = [t['pnl'] for t in trades]
    wins     = [p for p in pnls if p > 0]
    losses   = [p for p in pnls if p <= 0]
    win_rate = len(wins) / len(pnls) * 100 if pnls else 0
    pf       = sum(wins) / abs(sum(losses)) if losses else float('inf')

    equity_df   = pd.DataFrame(equity_log).set_index('date')
    rolling_max = equity_df['equity'].cummax()
    max_dd      = abs(((equity_df['equity'] - rolling_max) / rolling_max * 100).min())

    reason_cnt = {}
    for t in trades:
        reason_cnt[t['reason']] = reason_cnt.get(t['reason'], 0) + 1

    print(f'\n{"="*56}')
    print(f'  Python 結果       {SYMBOL}')
    print(f'  {START} → {END}  ({years:.1f} 年)')
    print(f'{"="*56}')
    print(f'  最終資金:    ${capital:>12,.2f}')
    print(f'  總報酬:      {total_ret:>+8.2f}%')
    print(f'  APR:         {apr:>+8.2f}%   ← 對比 TradingView +1.47%')
    print(f'  最大回撤:    {max_dd:>8.2f}%      (TV: 2.87%)')
    print(f'{"─"*56}')
    print(f'  總交易數:    {len(trades):>4d}       (TV: 25)')
    print(f'  勝率:        {win_rate:>6.1f}%     (TV: 28.0%)')
    print(f'  獲利因子:    {pf:>8.3f}    (TV: 1.224)')
    print(f'{"─"*56}')
    for r, c in sorted(reason_cnt.items()):
        print(f'  {r:6s}: {c} 筆')
    print(f'{"="*56}\n')


if __name__ == '__main__':
    run()
