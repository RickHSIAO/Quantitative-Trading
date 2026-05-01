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


def estimate_kelly_from_history(closed_trades: list) -> float:
    """
    從已平倉交易估算 1/4 Kelly。
    若樣本不足 KELLY_MIN_TRADES 則使用保守預設值 2%。
    """
    if len(closed_trades) < config.KELLY_MIN_TRADES:
        return 0.02

    pnls = [t.pnl for t in closed_trades if t.pnl is not None]
    wins  = [p for p in pnls if p > 0]
    losses = [abs(p) for p in pnls if p <= 0]

    if not wins or not losses:
        return 0.02

    wr    = len(wins) / len(pnls)
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
def calculate_stops(entry_price: float,
                    direction: int,
                    atr: float,
                    rr: float = config.RISK_REWARD_RATIO,
                    atr_mult: float = config.ATR_STOP_MULTIPLIER) -> tuple[float, float]:
    """
    止損距離 = ATR × atr_mult
    止盈距離 = 止損距離 × RR (1:3)
    Returns: (stop_loss, take_profit)
    """
    dist = atr * atr_mult
    if direction == 1:   # Long
        return entry_price - dist, entry_price + dist * rr
    else:                # Short
        return entry_price + dist, entry_price - dist * rr
