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
        'stop_loss':        f'止損出場 SL  {r_str}',
        'trailing_stop':    f'移動停利出場 TSL  {r_str}',
        'take_profit':      f'止盈出場 TP  {r_str}',
        'signal_flip':      f'信號翻轉平倉  {r_str}',
        'eod':              f'回測結束強制平倉  {r_str}',
        'bb_mid':           f'BB 抄底單 · 觸及中軌平倉  {r_str}',
        'bb_rsi':           f'BB 抄底單 · RSI 回中性平倉  {r_str}',
        'bb_target_profit': f'BB 抄底單 · 達 +{int(config.STRAT_BB_PROFIT_PCT*100)}% 短打停利  {r_str}',
        'soft_stop':        f'軟停損出場（浮虧≥{int(config.SOFT_STOP_PCT*100)}%）  {r_str}',
        'max_hold':         f'最長持倉強制出場（{config.MAX_HOLD_DAYS}天）  {r_str}',
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
        # 熔斷狀態
        self._cb_consec_loss: int = 0
        self._cb_pause_until: pd.Timestamp | None = None
        self._cb_daily_pnl:    dict[str, float] = {}   # date_str → 當日已實現 PnL
        self._cb_daily_trades: dict[str, int]   = {}   # date_str → 當日新進場數
        self._cb_trigger_count: int = 0                # 觸發暫停次數
        self._equity_peak: float = initial_capital     # 即時權益峰值（用於熔斷 DD 條件）

    # ── 平倉輔助 ─────────────────────────────────────────────────────────────
    def _close_trade(self, trade: Trade, exit_date: str,
                     exit_price: float, reason_code: str) -> float:
        pnl = (exit_price - trade.entry_price) * trade.quantity * trade.direction
        ret = (exit_price / trade.entry_price - 1.0) * trade.direction * 100 if trade.entry_price else 0.0
        orig_sl = self._orig_stop.get(trade.symbol, trade.stop_loss)
        r_dist  = abs(trade.entry_price - orig_sl)
        r_mult  = (pnl / (r_dist * trade.quantity)) if r_dist > 0 and trade.quantity > 0 else 0.0

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

        # 熔斷統計：連虧計數 + 當日 PnL
        if config.ENABLE_CIRCUIT_BREAKER:
            self._cb_daily_pnl[exit_date] = self._cb_daily_pnl.get(exit_date, 0.0) + pnl
            if pnl < 0:
                self._cb_consec_loss += 1
                if self._cb_consec_loss >= config.CB_CONSEC_LOSS_LIMIT:
                    # 額外回撤條件：避免在波段低點誤殺反彈
                    cur_dd_pct = ((self.capital - self._equity_peak) / self._equity_peak
                                  if self._equity_peak > 0 else 0.0)
                    dd_ok = (not config.CB_REQUIRE_DRAWDOWN
                             or cur_dd_pct <= -config.CB_REQUIRE_DRAWDOWN_PCT)
                    if dd_ok:
                        pause_days = config.CB_CONSEC_LOSS_PAUSE_DAYS
                        self._cb_pause_until = (pd.Timestamp(exit_date)
                                                 + pd.tseries.offsets.BusinessDay(pause_days))
                        self._cb_consec_loss   = 0
                        self._cb_trigger_count += 1
                    # DD 未達標時不重設 consec_loss，等待後續勝/負交易自然處理
            elif pnl > 0:
                self._cb_consec_loss = 0

        return pnl

    # ── 主回測迴圈 ─────────────────────────────────────────────────────────────
    def run(self,
            data:       dict[str, pd.DataFrame],
            signals:    dict[str, dict[str, pd.Series]],
            asset_types: dict[str, str]) -> list[Trade]:

        # ── Pre-build per-symbol numpy caches ────────────────────────────────
        # Hot loop avoids pandas .loc / Series construction by reading from
        # ndarrays via O(1) date→index dict lookups.
        idx_map:    dict[str, dict[pd.Timestamp, int]] = {}
        last_idx:   dict[str, int]                    = {}
        a_close:    dict[str, np.ndarray] = {}
        a_high:     dict[str, np.ndarray] = {}
        a_low:      dict[str, np.ndarray] = {}
        a_atr:      dict[str, np.ndarray] = {}
        a_atr_med:  dict[str, np.ndarray] = {}
        a_bbmid:    dict[str, np.ndarray] = {}
        a_rsi:      dict[str, np.ndarray] = {}

        def _arr(df: pd.DataFrame, col: str) -> np.ndarray:
            return (df[col].to_numpy(dtype=float)
                    if col in df.columns
                    else np.full(len(df), np.nan, dtype=float))

        atr_med_enabled = config.ATR_KELLY_MULT > 0
        for sym, df in data.items():
            n = len(df)
            idx_map[sym]  = {ts: i for i, ts in enumerate(df.index)}
            last_idx[sym] = n - 1
            a_close[sym]  = df['Close'].to_numpy(dtype=float)
            a_high[sym]   = df['High'].to_numpy(dtype=float)
            a_low[sym]    = df['Low'].to_numpy(dtype=float)
            a_atr[sym]    = _arr(df, 'atr')
            a_bbmid[sym]  = _arr(df, 'bb_mid')
            a_rsi[sym]    = _arr(df, 'rsi')
            # ATR 50-day rolling median (only built when ATR_KELLY_MULT enabled)
            if atr_med_enabled:
                a_atr_med[sym] = (pd.Series(a_atr[sym])
                                  .rolling(50, min_periods=10).median()
                                  .to_numpy())

        # Signal arrays (combined / score / per-strategy)
        sig_idx_map: dict[str, dict[pd.Timestamp, int]] = {}
        s_combined:  dict[str, np.ndarray] = {}
        s_score:     dict[str, np.ndarray] = {}
        s_trend:     dict[str, np.ndarray] = {}
        s_vp:        dict[str, np.ndarray] = {}
        s_bb:        dict[str, np.ndarray] = {}

        def _sig_arr(sigs: dict, key: str, n: int) -> np.ndarray:
            ser = sigs.get(key)
            if ser is None:
                return np.zeros(n, dtype=np.int64)
            return ser.fillna(0).to_numpy(dtype=np.int64)

        for sym, sigs in signals.items():
            ref = sigs.get('combined')
            if ref is None:
                continue
            n = len(ref)
            sig_idx_map[sym] = {ts: i for i, ts in enumerate(ref.index)}
            s_combined[sym]  = _sig_arr(sigs, 'combined', n)
            s_score[sym]     = _sig_arr(sigs, 'score',    n)
            s_trend[sym]     = _sig_arr(sigs, 'trend',    n)
            s_vp[sym]        = _sig_arr(sigs, 'vp',       n)
            s_bb[sym]        = _sig_arr(sigs, 'bb',       n)

        all_dates: list[pd.Timestamp] = sorted(
            {d for df in data.values() for d in df.index}
        )

        open_positions:  dict[str, Trade]       = {}
        history_by_sym:  dict[str, list[Trade]] = {s: [] for s in data}
        # Cache entry timestamp per open symbol (for hold-day computation
        # without re-parsing pos.entry_date string each iteration).
        entry_dt_cache:  dict[str, pd.Timestamp] = {}

        for dt in all_dates:
            date_str = dt.strftime('%Y-%m-%d')

            # ── Step 1: 更新持倉 MAE/MFE，檢查止損/止盈 ──────────────────
            for sym in list(open_positions.keys()):
                im = idx_map.get(sym)
                if im is None:
                    continue
                i = im.get(dt)
                if i is None:
                    continue
                price = float(a_close[sym][i])
                hi    = float(a_high[sym][i])
                lo    = float(a_low[sym][i])
                pos   = open_positions[sym]

                # 追蹤 MAE/MFE：多頭用 Low/High；空頭用 High/Low
                if pos.direction == 1:
                    adv_pct = (lo  / pos.entry_price - 1.0) * 100
                    fav_pct = (hi  / pos.entry_price - 1.0) * 100
                else:
                    adv_pct = (1.0 - hi / pos.entry_price) * 100
                    fav_pct = (1.0 - lo / pos.entry_price) * 100
                self._excursion.setdefault(sym, []).extend([adv_pct, fav_pct])

                # ATR 移動停利：BB 抄底單不啟用 TSL（避免抄底變趨勢）；其餘正常追蹤
                bb_no_tsl = config.STRAT_BB_DISABLE_TSL and pos.strategy == 'bb'
                if not bb_no_tsl:
                    atr_v   = a_atr[sym][i]
                    atr_now = float(atr_v) if not np.isnan(atr_v) else price * 0.02
                    trail_dist = atr_now * config.ATR_STOP_MULTIPLIER
                    if pos.direction == 1:   # 多頭：追蹤最高價
                        peak = max(self._trail_peak.get(sym, pos.entry_price), hi)
                        self._trail_peak[sym] = peak
                        new_sl = peak - trail_dist
                        if new_sl > pos.stop_loss and new_sl > pos.entry_price:
                            pos.stop_loss = new_sl
                    else:                    # 空頭：追蹤最低價
                        trough = min(self._trail_peak.get(sym, pos.entry_price), lo)
                        self._trail_peak[sym] = trough
                        new_sl = trough + trail_dist
                        if new_sl < pos.stop_loss and new_sl < pos.entry_price:
                            pos.stop_loss = new_sl

                # 用 High/Low 判斷日內是否觸及 SL/TP，TP 優先
                hit_tp = ((pos.direction ==  1 and hi  >= pos.take_profit) or
                          (pos.direction == -1 and lo  <= pos.take_profit))
                hit_sl = (not hit_tp) and (
                         (pos.direction ==  1 and lo  <= pos.stop_loss) or
                         (pos.direction == -1 and hi  >= pos.stop_loss))

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
                    entry_dt_cache.pop(sym, None)
                    continue

                # 持倉天數（用於 MIN_HOLD_DAYS 閘門 + SOFT_STOP / MAX_HOLD）
                entry_dt   = entry_dt_cache.get(sym, dt)
                hold_days  = (dt - entry_dt).days
                min_hold_ok = hold_days >= config.MIN_HOLD_DAYS

                # BB 抄底單早出（受 MIN_HOLD_DAYS 限制）
                if pos.strategy == 'bb' and min_hold_ok:
                    bb_v  = a_bbmid[sym][i]
                    rsi_v = a_rsi[sym][i]
                    bb_mid  = float(bb_v)  if not np.isnan(bb_v)  else None
                    rsi_now = float(rsi_v) if not np.isnan(rsi_v) else None
                    profit_pct = (price / pos.entry_price - 1.0) * pos.direction

                    early_code = None
                    if profit_pct >= config.STRAT_BB_PROFIT_PCT:
                        early_code = 'bb_target_profit'
                    elif bb_mid is not None and (
                            (pos.direction ==  1 and price >= bb_mid) or
                            (pos.direction == -1 and price <= bb_mid)):
                        early_code = 'bb_mid'
                    elif rsi_now is not None and (
                            (pos.direction ==  1 and rsi_now >= config.STRAT_BB_RSI_EXIT) or
                            (pos.direction == -1 and rsi_now <= config.STRAT_BB_RSI_EXIT)):
                        early_code = 'bb_rsi'

                    if early_code is not None:
                        self._close_trade(pos, date_str, price, early_code)
                        history_by_sym[sym].append(pos)
                        del open_positions[sym]
                        entry_dt_cache.pop(sym, None)
                        continue

                # 軟停損：滿 MIN_HOLD_DAYS 後浮虧 ≥ SOFT_STOP_PCT 即出場
                if config.SOFT_STOP_PCT > 0 and min_hold_ok:
                    unrealised_pct = (price / pos.entry_price - 1.0) * pos.direction
                    if unrealised_pct <= -config.SOFT_STOP_PCT:
                        self._close_trade(pos, date_str, price, 'soft_stop')
                        history_by_sym[sym].append(pos)
                        del open_positions[sym]
                        entry_dt_cache.pop(sym, None)
                        continue

                # 最長持倉強制出場（不問盈虧，釋放卡死資金）
                if config.MAX_HOLD_DAYS > 0 and hold_days >= config.MAX_HOLD_DAYS:
                    self._close_trade(pos, date_str, price, 'max_hold')
                    history_by_sym[sym].append(pos)
                    del open_positions[sym]
                    entry_dt_cache.pop(sym, None)
                    continue

                # 信號翻轉 → 平倉（受 MIN_HOLD_DAYS 限制）
                sim = sig_idx_map.get(sym)
                if sim is not None and min_hold_ok:
                    si = sim.get(dt)
                    if si is not None:
                        sig_val = int(s_combined[sym][si])
                        if sig_val != 0 and sig_val != pos.direction:
                            self._close_trade(pos, date_str, price, 'signal_flip')
                            history_by_sym[sym].append(pos)
                            del open_positions[sym]
                            entry_dt_cache.pop(sym, None)

                # 資料截止自動平倉（始終允許）
                if sym in open_positions and i == last_idx[sym]:
                    self._close_trade(pos, date_str, price, 'eod')
                    history_by_sym[sym].append(pos)
                    del open_positions[sym]
                    entry_dt_cache.pop(sym, None)

            # ── Step 2: 開新倉（依訊號共識度優先）────────────────────────
            if len(open_positions) < config.MAX_TOTAL_POSITIONS:
                candidates: list[tuple[str, int, int, str]] = []
                for sym in data:
                    if sym in open_positions:
                        continue
                    im = idx_map.get(sym)
                    if im is None or dt not in im:
                        continue
                    sim = sig_idx_map.get(sym)
                    if sim is None:
                        continue
                    si = sim.get(dt)
                    if si is None:
                        continue
                    sig_val = int(s_combined[sym][si])
                    if sig_val == 0:
                        continue
                    score_val = int(s_score[sym][si])
                    if score_val < config.MIN_ENTRY_SCORE:
                        continue
                    # 個股勝率過濾：近 SYM_WR_WINDOW 筆勝率低於門檻則跳過
                    if config.SYM_MIN_WINRATE > 0:
                        hist = history_by_sym[sym][-config.SYM_WR_WINDOW:]
                        if len(hist) >= config.SYM_WR_MIN_TRADES:
                            wins = sum(1 for t in hist if t.pnl is not None and t.pnl > 0)
                            if wins / len(hist) < config.SYM_MIN_WINRATE:
                                continue
                    # Dominant strategy via cached arrays
                    matched = []
                    if int(s_trend[sym][si]) == sig_val: matched.append('trend')
                    if int(s_vp[sym][si])    == sig_val: matched.append('vp')
                    if int(s_bb[sym][si])    == sig_val: matched.append('bb')
                    strat = matched[0] if len(matched) == 1 else 'combined'
                    candidates.append((sym, sig_val, score_val, strat))

                candidates.sort(key=lambda x: x[2], reverse=True)

                class_counts: dict[str, int] = {}
                strat_counts: dict[str, int] = {}
                for pos in open_positions.values():
                    class_counts[pos.asset_type] = class_counts.get(pos.asset_type, 0) + 1
                    strat_counts[pos.strategy]   = strat_counts.get(pos.strategy, 0)   + 1

                cb_paused = (self._cb_pause_until is not None
                             and dt < self._cb_pause_until)
                if self._cb_pause_until is not None and dt >= self._cb_pause_until:
                    self._cb_pause_until = None

                daily_pnl    = self._cb_daily_pnl.get(date_str, 0.0)
                daily_trades = self._cb_daily_trades.get(date_str, 0)
                daily_loss_blocked = (config.ENABLE_CIRCUIT_BREAKER and
                                      daily_pnl <= -config.CB_DAILY_LOSS_PCT * self.capital)
                daily_count_blocked = (config.ENABLE_CIRCUIT_BREAKER and
                                       daily_trades >= config.CB_MAX_DAILY_TRADES)
                cb_block_today = (config.ENABLE_CIRCUIT_BREAKER and
                                  (cb_paused or daily_loss_blocked or daily_count_blocked))

                for sym, sig_val, score_val, strat in (candidates if not cb_block_today else []):
                    if len(open_positions) >= config.MAX_TOTAL_POSITIONS:
                        break

                    atype       = asset_types.get(sym, '')
                    class_limit = config.MAX_POS_PER_CLASS.get(atype, config.MAX_TOTAL_POSITIONS)
                    if class_counts.get(atype, 0) >= class_limit:
                        continue

                    strat_limit = config.MAX_POS_PER_STRATEGY.get(strat) \
                                  if config.MAX_POS_PER_STRATEGY else None
                    if strat_limit is not None and strat_counts.get(strat, 0) >= strat_limit:
                        continue

                    i = idx_map[sym][dt]
                    price = float(a_close[sym][i])
                    atr_v = a_atr[sym][i]
                    atr   = float(atr_v) if not np.isnan(atr_v) else price * 0.02

                    sl, tp = calculate_stops(price, sig_val, atr, strategy=strat)

                    if config.ENABLE_GEOMETRIC_RR and not _geometric_rr_ok_arr(
                            a_high[sym], a_low[sym], i, sig_val, tp, atr,
                            lookback=config.GEO_RR_LOOKBACK,
                            buffer_atr=config.GEO_RR_BUFFER_ATR):
                        continue

                    kf = estimate_kelly_from_history(history_by_sym[sym])

                    if config.ENABLE_SCORE_TIER_SIZING:
                        tier_mult = config.SCORE_TIER_MULT.get(score_val, 1.0)
                        kf       = kf * tier_mult

                    # ATR 高波動減半：當日 ATR > 50 日中位數 × N → Kelly × 0.5
                    if atr_med_enabled and sym in a_atr_med:
                        med = a_atr_med[sym][i]
                        if (not np.isnan(med) and med > 0
                                and atr > med * config.ATR_KELLY_MULT):
                            kf = kf * 0.5

                    available_cash = self.capital - sum(
                        pos.entry_price * pos.quantity for pos in open_positions.values()
                    )
                    if available_cash <= 0:
                        break

                    # 同日候選均分剩餘現金（依剩餘可進場名額）
                    if config.EQUAL_CASH_SPLIT:
                        slots_left = config.MAX_TOTAL_POSITIONS - len(open_positions)
                        budget = available_cash / max(slots_left, 1)
                    else:
                        budget = available_cash

                    qty = position_size(budget, kf, price, sl)
                    if qty <= 0 or qty * price > available_cash:
                        continue

                    self._cb_daily_trades[date_str] = self._cb_daily_trades.get(date_str, 0) + 1

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
                        asset_type   = atype,
                        entry_reason = _entry_reason(strat, sig_val),
                        risk_usd     = round(r_dist * qty, 2),
                    )
                    open_positions[sym]  = trade
                    self._orig_stop[sym] = sl
                    entry_dt_cache[sym]  = dt
                    class_counts[atype]  = class_counts.get(atype, 0) + 1
                    strat_counts[strat]  = strat_counts.get(strat, 0) + 1

            # ── Step 3: 記錄淨值 ──────────────────────────────────────────
            unrealised = 0.0
            allocated  = 0.0
            for sym, pos in open_positions.items():
                im = idx_map.get(sym)
                if im is None:
                    continue
                i = im.get(dt)
                if i is None:
                    continue
                close_v = float(a_close[sym][i])
                unrealised += (close_v - pos.entry_price) * pos.quantity * pos.direction
                allocated  += pos.entry_price * pos.quantity

            total_equity = round(self.capital + unrealised, 2)
            if total_equity > self._equity_peak:
                self._equity_peak = total_equity
            self.equity_curve.append({
                'date':           date_str,
                'capital':        total_equity,
                'allocated':      round(allocated, 2),
                'remaining':      round(self.capital - allocated, 2),
                'pnl':            round(total_equity - self.initial_capital, 2),
                'open_positions': len(open_positions),
            })

        # ── Step 4: 強制平倉（回測結束）─────────────────────────────────
        for sym, pos in open_positions.items():
            i = last_idx[sym]
            last_dt = data[sym].index[i]
            self._close_trade(pos, last_dt.strftime('%Y-%m-%d'),
                              float(a_close[sym][i]), 'eod')
            history_by_sym[sym].append(pos)
            entry_dt_cache.pop(sym, None)

        self.trades = [t for lst in history_by_sym.values() for t in lst]
        return self.trades

    # ── 績效指標 ──────────────────────────────────────────────────────────────
    def get_metrics(self) -> dict:
        closed = [t for t in self.trades if t.pnl is not None]
        if not closed:
            return {}

        pnls   = [t.pnl for t in closed]
        wins   = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]
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
        annual_ret = ((self.capital / self.initial_capital) ** (1.0 / max(years, 1)) - 1.0) * 100
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
            er = t.exit_reason or ''
            if 'BB 抄底' in er:
                if   '中軌' in er: key = 'BB-Mid'
                elif 'RSI'  in er: key = 'BB-RSI'
                else:              key = 'BB-Tgt'
            elif '止盈'   in er: key = 'TP'
            elif '移動停利' in er: key = 'TSL'
            elif '止損'   in er: key = 'SL'
            elif '翻轉'   in er: key = 'Flip'
            else:                key = 'EOD'
            exit_dist[key] = exit_dist.get(key, 0) + 1

        # 各策略分解
        strat_stats: dict[str, dict] = {}
        for strat in ('trend', 'vp', 'bb', 'combined'):
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
                                 if any(t.r_multiple is not None for t in st) else 0.0,
                }

        # 各資產類型分解
        type_stats: dict[str, dict] = {}
        for atype in set(t.asset_type for t in closed):
            at = [t for t in closed if t.asset_type == atype]
            ap = [t.pnl for t in at]
            type_pnl = sum(ap)
            type_stats[atype] = {
                'trades':          len(at),
                'win_rate':        round(len([p for p in ap if p > 0]) / len(ap), 4),
                'total_pnl':       round(type_pnl, 2),
                'annual_pnl_pct':  round(type_pnl / self.initial_capital / max(years, 1) * 100, 2),
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
            'cb_trigger_count':  self._cb_trigger_count,
            'features_enabled':  {
                'score_tier_sizing': bool(config.ENABLE_SCORE_TIER_SIZING),
                'circuit_breaker':   bool(config.ENABLE_CIRCUIT_BREAKER),
                'geometric_rr':      bool(config.ENABLE_GEOMETRIC_RR),
            },
        }


# ─── 輔助函式 ─────────────────────────────────────────────────────────────────
def _dominant_strategy(sym_sigs: dict[str, pd.Series], dt: pd.Timestamp, direction: int) -> str:
    """
    回傳當日主導策略：
      恰好一個子策略命中該方向 → 該策略名稱
      多個命中                  → 'combined'（多策略共識）
      皆未命中（理論上不該發生） → 'combined' 並 fallback（保守處理）
    """
    matched = [
        s for s in ('trend', 'vp', 'bb')
        if (ser := sym_sigs.get(s)) is not None
        and dt in ser.index
        and int(ser.loc[dt]) == direction
    ]
    if len(matched) == 1:
        return matched[0]
    return 'combined'


def _geometric_rr_ok_arr(high_arr: np.ndarray,
                          low_arr:  np.ndarray,
                          i:         int,
                          direction: int,
                          tp:        float,
                          atr:       float,
                          lookback:  int = 20,
                          buffer_atr: float = 1.0) -> bool:
    """Array-backed geometric R:R check. Equivalent to `_geometric_rr_ok`
    but reads ndarrays directly instead of slicing a DataFrame."""
    start = max(0, i - lookback)
    if start >= i or atr <= 0:
        return True
    if direction == 1:
        swing_high = float(high_arr[start:i].max())
        if tp > swing_high and (tp - swing_high) < buffer_atr * atr:
            return False
        return True
    else:
        swing_low = float(low_arr[start:i].min())
        if tp < swing_low and (swing_low - tp) < buffer_atr * atr:
            return False
        return True


def _geometric_rr_ok(df: pd.DataFrame,
                     dt: pd.Timestamp,
                     direction: int,
                     tp: float,
                     atr: float,
                     lookback: int = 20,
                     buffer_atr: float = 1.0) -> bool:
    """
    幾何 R:R 檢查：TP 路徑上若有近 N 日 swing 阻擋（多單為高點、空單為低點），
    且 swing 距 TP 不到 buffer×ATR，視為「TP 到不了」→ 拒絕進場。
    """
    try:
        idx_loc = df.index.get_loc(dt)
    except KeyError:
        return True
    start = max(0, idx_loc - lookback)
    window = df.iloc[start:idx_loc]
    if window.empty or atr <= 0:
        return True

    if direction == 1:   # 多單：找上方 swing high
        swing_high = float(window['High'].max())
        # 若 TP 在 swing 之上，且 TP 距 swing < buffer×ATR → 阻擋
        if tp > swing_high and (tp - swing_high) < buffer_atr * atr:
            return False
        # 若 TP 還沒到 swing，但 swing 在路徑上（entry < swing < tp 通常已被前項涵蓋）
        return True
    else:                # 空單：找下方 swing low
        swing_low = float(window['Low'].min())
        if tp < swing_low and (swing_low - tp) < buffer_atr * atr:
            return False
        return True
