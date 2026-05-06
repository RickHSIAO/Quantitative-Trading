"""
Kelly Criterion + Quarter-Kelly position sizing + 1:3 RR stop/target calculation.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


# ─── Kelly 公式 ───────────────────────────────────────────────────────────────
def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    f* = W - (1-W)/R
    W  = 勝率
    R  = 平均獲利 / 平均虧損
    回傳 0 若結果為負（不交易優於虧損）
    """
    if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
        return 0.0
    R = avg_win / avg_loss
    if R <= 0:
        return 0.0
    return max(0.0, win_rate - (1.0 - win_rate) / R)


def quarter_kelly(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """1/4 凱利，降低波動、保護資金"""
    return kelly_criterion(win_rate, avg_win, avg_loss) * config.KELLY_FRACTION


def estimate_kelly_from_history(closed_trades: list, window: int = 0) -> float:
    """
    從已平倉交易估算 1/4 Kelly。
    若樣本不足 KELLY_MIN_TRADES 則使用 config.DEFAULT_RISK_PCT 作為預設值。
    window > 0 時只取最近 N 筆（避免遠期 regime 干擾當下倉位）。
    """
    if window > 0 and len(closed_trades) > window:
        closed_trades = closed_trades[-window:]
    default_risk = getattr(config, 'DEFAULT_RISK_PCT', 0.02)
    if len(closed_trades) < config.KELLY_MIN_TRADES:
        return default_risk

    pnls = [t.pnl for t in closed_trades if t.pnl is not None]
    wins   = [p      for p in pnls if p > 0]
    losses = [abs(p) for p in pnls if p < 0]   # 與 backtester 一致：零損益不計入贏也不計入輸

    if not wins or not losses:
        return default_risk

    decisive = len(wins) + len(losses)          # 排除平手交易，勝率分母對齊
    wr    = len(wins) / decisive
    avg_w = sum(wins)   / len(wins)
    avg_l = sum(losses) / len(losses)
    k     = quarter_kelly(wr, avg_w, avg_l)
    # 限制上限，避免過度槓桿
    return min(k, config.MAX_RISK_PCT)


# ─── 倉位計算 ─────────────────────────────────────────────────────────────────
def position_size(capital: float,
                  kelly_frac: float,
                  entry_price: float,
                  stop_loss_price: float) -> float:
    """
    風險金額 = 資金 × Kelly 比例
    倉位數量 = 風險金額 / 每單位風險（entry - stop）
    同時不超過 MAX_POSITION_PCT 的資金
    """
    price_risk = abs(entry_price - stop_loss_price)
    if price_risk == 0 or entry_price == 0:
        return 0.0

    risk_amount = capital * min(kelly_frac, config.MAX_RISK_PCT)
    qty = risk_amount / price_risk
    max_qty = (capital * config.MAX_POSITION_PCT) / entry_price
    return max(0.0, min(qty, max_qty))


# ─── 止損/止盈 ────────────────────────────────────────────────────────────────
_STRAT_PARAMS = {
    'trend':    (config.STRAT_TREND_ATR_MULT, config.STRAT_TREND_RR),
    'combined': (config.STRAT_TREND_ATR_MULT, config.STRAT_TREND_RR),
    'vp':       (config.STRAT_VP_ATR_MULT,    config.STRAT_VP_RR),
    'bb':       (config.STRAT_BB_ATR_MULT,    config.STRAT_BB_RR),
}


def calculate_stops(entry_price: float,
                    direction: int,
                    atr: float,
                    strategy: str = 'trend',
                    rr: float | None = None,
                    atr_mult: float | None = None) -> tuple[float, float]:
    """
    依進場通道分流停損/停利：
      trend / combined : ATR×3.0, RR 3:1（讓利潤奔跑）
      vp               : ATR×2.0, RR 2:1（中等持有）
      bb               : ATR×1.5, RR 2:1（窄停損兜底；主要靠早出條件）
    呼叫者可顯式覆寫 rr / atr_mult 強制指定。
    Returns: (stop_loss, take_profit)
    """
    default_mult, default_rr = _STRAT_PARAMS.get(
        strategy, (config.ATR_STOP_MULTIPLIER, config.RISK_REWARD_RATIO)
    )
    if atr_mult is None:
        atr_mult = default_mult
    if rr is None:
        rr = default_rr

    dist = atr * atr_mult
    if direction == 1:   # Long
        return entry_price - dist, entry_price + dist * rr
    else:                # Short
        return entry_price + dist, entry_price - dist * rr
