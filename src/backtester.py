"""
Event-driven daily backtester.
處理流程（每個交易日）：
  1. 更新持倉 → 觸發止損/止盈
  2. 讀取合併信號 → 開新倉（若未持該標的）
  3. 記錄當日淨值
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from src.risk import estimate_kelly_from_history, position_size, calculate_stops


# ─── Trade 資料結構 ────────────────────────────────────────────────────────────
@dataclass
class Trade:
    symbol:        str
    strategy:      str
    direction:     int          # +1 Long / -1 Short
    entry_date:    str
    entry_price:   float
    quantity:      float
    stop_loss:     float
    take_profit:   float
    asset_type:    str  = ''
    entry_reason:  str  = ''    # 進場原因（人類可讀）
    risk_usd:      float = 0.0  # 本次風險金額（USD）
    # ── 平倉後填入 ───────────────────────────────────────────────────────────
    exit_date:     Optional[str]   = None
    exit_price:    Optional[float] = None
    exit_reason:   Optional[str]   = None   # 出場原因（人類可讀）
    pnl:           Optional[float] = None
    return_pct:    Optional[float] = None
    holding_days:  Optional[int]   = None   # 持倉天數
    r_multiple:    Optional[float] = None   # 損益 / 每 R 風險（e.g. +3 = TP, -1 = SL）
    mae:           Optional[float] = None   # 最大不利偏移 (Max Adverse Excursion, %)
    mfe:           Optional[float] = None   # 最大有利偏移 (Max Favorable Excursion, %)


# ─── 進場原因文字 ──────────────────────────────────────────────────────────────
def _entry_reason(strategy: str, direction: int) -> str:
    side = '做多 ↑' if direction == 1 else '做空 ↓'
    reasons = {
        'trend': (
            f'Supertrend 翻多 · 價格突破 EMA{config.EMA_PERIOD}  →  {side}'
            if direction == 1 else
            f'Supertrend 翻空 · 價格跌破 EMA{config.EMA_PERIOD}  →  {side}'
        ),
        'vp': (
            f'價格回測 POC 支撐區  →  {side}'
            if direction == 1 else
            f'價格反彈至 POC 阻力區  →  {side}'
        ),
        'bb': (
            f'布林下軌觸碰 · RSI 超賣 (<30)  →  {side}'
            if direction == 1 else
            f'布林上軌觸碰 · RSI 超買 (>70)  →  {side}'
        ),
    }
    return reasons.get(strategy, f'多策略同向 (≥2)  →  {side}')


# ─── 出場原因文字 ──────────────────────────────────────────────────────────────
def _exit_reason(code: str, r_mult: float) -> str:
    r_str = f'({r_mult:+.2f}R)' if r_mult is not None else ''
    mapping = {
        'stop_loss':     f'止損出場 SL  {r_str}',
        'trailing_stop': f'移動停利出場 TSL  {r_str}',
        'take_profit':   f'止盈出場 TP 1:{int(config.RISK_REWARD_RATIO)}  {r_str}',
        'signal_flip':   f'信號翻轉平倉  {r_str}',
        'eod':           f'回測結束強制平倉  {r_str}',
    }
    return mapping.get(code, code)


# ─── Backtester ────────────────────────────────────────────────────────────────
class Backtester:
    def __init__(self, initial_capital: float = config.INITIAL_CAPITAL):
        self.initial_capital = initial_capital
        self.capital: float   = initial_capital
        self.trades:  list[Trade] = []
        self.equity_curve: list[dict] = []
        self._excursion:   dict[str, list[float]] = {}
        # ATR 移動停利：記錄極值與原始止損，用於判斷是否為移動停利出場
        self._trail_peak:  dict[str, float] = {}
        self._orig_stop:   dict[str, float] = {}

    # ── 平倉輔助 ─────────────────────────────────────────────────────────────
    def _close_trade(self, trade: Trade, exit_date: str,
                     exit_price: float, reason_code: str) -> float:
        pnl = (exit_price - trade.entry_price) * trade.quantity * trade.direction
        ret = (exit_price / trade.entry_price - 1.0) * trade.direction * 100 if trade.entry_price else 0.0
        r_dist = abs(trade.entry_price - trade.stop_loss)
        r_mult = (pnl / (r_dist * trade.quantity)) if r_dist > 0 and trade.quantity > 0 else 0.0

        trade.exit_date    = exit_date
        trade.exit_price   = exit_price
        trade.pnl          = pnl
        trade.return_pct   = ret
        trade.r_multiple   = round(r_mult, 2)
        trade.exit_reason  = _exit_reason(reason_code, r_mult)
        trade.holding_days = max(0, (pd.Timestamp(exit_date) - pd.Timestamp(trade.entry_date)).days)

        # MAE / MFE
        excursions = self._excursion.pop(trade.symbol, [])
        if excursions:
            trade.mae = round(min(excursions), 2)
            trade.mfe = round(max(excursions), 2)

        self._trail_peak.pop(trade.symbol, None)
        self._orig_stop.pop(trade.symbol, None)
        self.capital += pnl
        return pnl

    # ── 主回測迴圈 ─────────────────────────────────────────────────────────────
    def run(self,
            data:       dict[str, pd.DataFrame],
            signals:    dict[str, dict[str, pd.Series]],
            asset_types: dict[str, str]) -> list[Trade]:

        all_dates: list[pd.Timestamp] = sorted(
            {d for df in data.values() for d in df.index}
        )

        open_positions:  dict[str, Trade]       = {}
        history_by_sym:  dict[str, list[Trade]] = {s: [] for s in data}

        for dt in all_dates:
            date_str = dt.strftime('%Y-%m-%d')

            # ── Step 1: 更新持倉 MAE/MFE，檢查止損/止盈 ──────────────────
            for sym in list(open_positions.keys()):
                if dt not in data[sym].index:
                    continue
                price = float(data[sym].loc[dt, 'Close'])
                pos   = open_positions[sym]

                # 追蹤最大有利/不利偏移（%）
                chg_pct = (price / pos.entry_price - 1.0) * pos.direction * 100
                self._excursion.setdefault(sym, []).append(chg_pct)

                # ATR 移動停利：止損只往有利方向移動
                row_data = data[sym].loc[dt]
                atr_now  = float(row_data.get('atr', price * 0.02) or price * 0.02)
                trail_dist = atr_now * config.ATR_STOP_MULTIPLIER
                if pos.direction == 1:   # 多頭：追蹤最高價
                    peak = max(self._trail_peak.get(sym, pos.entry_price), price)
                    self._trail_peak[sym] = peak
                    new_sl = peak - trail_dist
                    if new_sl > pos.stop_loss:
                        pos.stop_loss = new_sl
                else:                    # 空頭：追蹤最低價
                    trough = min(self._trail_peak.get(sym, pos.entry_price), price)
                    self._trail_peak[sym] = trough
                    new_sl = trough + trail_dist
                    if new_sl < pos.stop_loss:
                        pos.stop_loss = new_sl

                hit_sl = ((pos.direction ==  1 and price <= pos.stop_loss) or
                          (pos.direction == -1 and price >= pos.stop_loss))
                hit_tp = ((pos.direction ==  1 and price >= pos.take_profit) or
                          (pos.direction == -1 and price <= pos.take_profit))

                if hit_sl or hit_tp:
                    ep   = pos.stop_loss if hit_sl else pos.take_profit
                    if hit_sl:
                        orig = self._orig_stop.get(sym, pos.stop_loss)
                        code = 'trailing_stop' if pos.stop_loss != orig else 'stop_loss'
                    else:
                        code = 'take_profit'
                    self._close_trade(pos, date_str, ep, code)
                    history_by_sym[sym].append(pos)
                    del open_positions[sym]
                    continue

                # 信號翻轉 → 平倉
                comb = signals.get(sym, {}).get('combined')
                if comb is not None and dt in comb.index:
                    sig_val = int(comb.loc[dt])
                    if sig_val != 0 and sig_val != pos.direction:
                        self._close_trade(pos, date_str, price, 'signal_flip')
                        history_by_sym[sym].append(pos)
                        del open_positions[sym]

            # ── Step 2: 開新倉 ────────────────────────────────────────────
            if len(open_positions) < config.MAX_TOTAL_POSITIONS:
                for sym, df in data.items():
                    if sym in open_positions:
                        continue
                    if len(open_positions) >= config.MAX_TOTAL_POSITIONS:
                        break
                    if dt not in df.index:
                        continue

                    sym_sigs = signals.get(sym, {})
                    comb     = sym_sigs.get('combined')
                    if comb is None or dt not in comb.index:
                        continue
                    sig_val = int(comb.loc[dt])
                    if sig_val == 0:
                        continue

                    row   = df.loc[dt]
                    price = float(row['Close'])
                    atr   = float(row.get('atr', price * 0.02) or price * 0.02)

                    sl, tp  = calculate_stops(price, sig_val, atr)
                    kf      = estimate_kelly_from_history(history_by_sym[sym])
                    qty     = position_size(self.capital, kf, price, sl)

                    if qty <= 0 or self.capital < price * qty * 0.05:
                        continue

                    strat  = _dominant_strategy(sym_sigs, dt)
                    r_dist = abs(price - sl)
                    trade  = Trade(
                        symbol       = sym,
                        strategy     = strat,
                        direction    = sig_val,
                        entry_date   = date_str,
                        entry_price  = price,
                        quantity     = qty,
                        stop_loss    = sl,
                        take_profit  = tp,
                        asset_type   = asset_types.get(sym, ''),
                        entry_reason = _entry_reason(strat, sig_val),
                        risk_usd     = round(r_dist * qty, 2),
                    )
                    open_positions[sym]      = trade
                    self._orig_stop[sym]     = sl

            # ── Step 3: 記錄淨值 ──────────────────────────────────────────
            unrealised = sum(
                (float(data[sym].loc[dt, 'Close']) - pos.entry_price) * pos.quantity * pos.direction
                for sym, pos in open_positions.items()
                if dt in data[sym].index
            )
            self.equity_curve.append({
                'date':           date_str,
                'capital':        round(self.capital + unrealised, 2),
                'open_positions': len(open_positions),
            })

        # ── Step 4: 強制平倉（回測結束）─────────────────────────────────
        for sym, pos in open_positions.items():
            df = data[sym]
            self._close_trade(pos, df.index[-1].strftime('%Y-%m-%d'),
                              float(df['Close'].iloc[-1]), 'eod')
            history_by_sym[sym].append(pos)

        self.trades = [t for lst in history_by_sym.values() for t in lst]
        return self.trades

    # ── 績效指標 ──────────────────────────────────────────────────────────────
    def get_metrics(self) -> dict:
        closed = [t for t in self.trades if t.pnl is not None]
        if not closed:
            return {}

        pnls   = [t.pnl for t in closed]
        wins   = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p <= 0]
        wr     = len(wins) / len(pnls)
        avg_w  = float(np.mean(wins))   if wins   else 0.0
        avg_l  = float(np.mean(losses)) if losses else 0.0
        pf     = sum(wins) / max(sum(losses), 1e-9)

        equity_s      = pd.Series([e['capital'] for e in self.equity_curve])
        daily_ret     = equity_s.pct_change().dropna()
        sharpe        = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)
                         if daily_ret.std() > 0 else 0.0)

        equity    = pd.Series([e['capital'] for e in self.equity_curve])
        dd_series = (equity - equity.cummax()) / equity.cummax() * 100
        max_dd    = float(dd_series.min())
        dd_usd    = float((equity - equity.cummax()).min())

        total_ret  = (self.capital - self.initial_capital) / self.initial_capital * 100
        eq_dates   = [e['date'] for e in self.equity_curve]
        years      = (pd.Timestamp(eq_dates[-1]) - pd.Timestamp(eq_dates[0])).days / 365.25 if len(eq_dates) > 1 else 1.0
        annual_ret = total_ret / max(years, 1)
        calmar     = annual_ret / abs(max_dd) if max_dd != 0 else 0.0
        recovery   = (self.capital - self.initial_capital) / abs(dd_usd) if dd_usd != 0 else 0.0
        expectancy = wr * avg_w - (1 - wr) * avg_l  # USD per trade

        # 持倉天數
        hold_days = [t.holding_days for t in closed if t.holding_days]
        avg_hold  = float(np.mean(hold_days)) if hold_days else 0.0

        # R-multiple
        r_mults   = [t.r_multiple for t in closed if t.r_multiple is not None]
        avg_r     = float(np.mean(r_mults)) if r_mults else 0.0

        # 最大連勝/連敗
        streak_w, streak_l, cur_w, cur_l = 0, 0, 0, 0
        for p in pnls:
            if p > 0:
                cur_w += 1; cur_l = 0
            else:
                cur_l += 1; cur_w = 0
            streak_w = max(streak_w, cur_w)
            streak_l = max(streak_l, cur_l)

        # 多空勝率
        longs  = [t for t in closed if t.direction ==  1]
        shorts = [t for t in closed if t.direction == -1]
        wr_l   = len([t for t in longs  if t.pnl > 0]) / len(longs)  if longs  else 0.0
        wr_s   = len([t for t in shorts if t.pnl > 0]) / len(shorts) if shorts else 0.0

        # 出場原因分布
        exit_dist: dict[str, int] = {}
        for t in closed:
            key = 'TP'  if t.exit_reason and '止盈'   in t.exit_reason else \
                  'TSL' if t.exit_reason and '移動停利' in t.exit_reason else \
                  'SL'  if t.exit_reason and '止損'   in t.exit_reason else \
                  'Flip' if t.exit_reason and '翻轉'  in t.exit_reason else 'EOD'
            exit_dist[key] = exit_dist.get(key, 0) + 1

        # 各策略分解
        strat_stats: dict[str, dict] = {}
        for strat in ('trend', 'vp', 'bb'):
            st = [t for t in closed if t.strategy == strat]
            if st:
                sp = [t.pnl for t in st]
                strat_stats[strat] = {
                    'trades':    len(st),
                    'win_rate':  round(len([p for p in sp if p > 0]) / len(sp), 4),
                    'total_pnl': round(sum(sp), 2),
                    'avg_pnl':   round(float(np.mean(sp)), 2),
                    'avg_r':     round(float(np.mean([t.r_multiple for t in st
                                                       if t.r_multiple is not None])), 2)
                                 if any(t.r_multiple for t in st) else 0.0,
                }

        # 各資產類型分解
        type_stats: dict[str, dict] = {}
        for atype in set(t.asset_type for t in closed):
            at = [t for t in closed if t.asset_type == atype]
            ap = [t.pnl for t in at]
            type_stats[atype] = {
                'trades':    len(at),
                'win_rate':  round(len([p for p in ap if p > 0]) / len(ap), 4),
                'total_pnl': round(sum(ap), 2),
            }

        return {
            'initial_capital':   self.initial_capital,
            'final_capital':     round(self.capital, 2),
            'total_pnl':         round(self.capital - self.initial_capital, 2),
            'total_return_pct':  round(total_ret, 2),
            'annual_return_pct': round(annual_ret, 2),
            'total_trades':      len(closed),
            'win_rate':          round(wr, 4),
            'win_rate_long':     round(wr_l, 4),
            'win_rate_short':    round(wr_s, 4),
            'avg_win':           round(avg_w, 2),
            'avg_loss':          round(avg_l, 2),
            'profit_factor':     round(pf, 3),
            'expectancy':        round(expectancy, 2),
            'sharpe_ratio':      round(sharpe, 3),
            'calmar_ratio':      round(calmar, 3),
            'recovery_factor':   round(recovery, 3),
            'max_drawdown_pct':  round(max_dd, 2),
            'max_drawdown_usd':  round(dd_usd, 2),
            'avg_r_multiple':    round(avg_r, 3),
            'avg_holding_days':  round(avg_hold, 1),
            'max_consec_wins':   streak_w,
            'max_consec_losses': streak_l,
            'best_trade':        round(max(pnls), 2),
            'worst_trade':       round(min(pnls), 2),
            'exit_distribution': exit_dist,
            'by_strategy':       strat_stats,
            'by_asset_type':     type_stats,
        }


# ─── 輔助函式 ─────────────────────────────────────────────────────────────────
def _dominant_strategy(sym_sigs: dict[str, pd.Series], dt: pd.Timestamp) -> str:
    for s in ('trend', 'vp', 'bb'):
        ser = sym_sigs.get(s)
        if ser is not None and dt in ser.index and ser.loc[dt] != 0:
            return s
    return 'combined'
