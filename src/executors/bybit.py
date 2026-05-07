"""
Bybit 執行器（加密貨幣永續合約）。
"""
from __future__ import annotations
import sys, os, math
from decimal import Decimal
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config
from src.executors.base import BaseExecutor


class OrderRejected(Exception):
    """Broker 明確拒絕下單；上游必須處理，不可靜默忽略。"""

try:
    from pybit.unified_trading import HTTP as BybitHTTP
    PYBIT_AVAILABLE = True
except ImportError:
    PYBIT_AVAILABLE = False
    print('[WARN] pybit 未安裝，加密貨幣即時交易功能不可用。執行: pip install pybit')


def _yf_to_bybit(symbol: str) -> str:
    """BYBIT:BTCUSDT.P → BTCUSDT"""
    if symbol.startswith('BYBIT:') and symbol.endswith('.P'):
        return symbol[6:-2]
    return symbol.replace('-USD', 'USDT')


def _floor_to_step(value: float, step: float) -> float:
    if step <= 0:
        return float(value)
    d_step  = Decimal(str(step))
    d_value = Decimal(str(value))
    n = (d_value / d_step).to_integral_value(rounding='ROUND_FLOOR')
    return float(n * d_step)


class BybitExecutor(BaseExecutor):
    asset_class = 'Crypto'

    def __init__(self):
        if not PYBIT_AVAILABLE:
            raise RuntimeError('pybit 未安裝')
        if not config.BYBIT_API_KEY or not config.BYBIT_API_SECRET:
            raise RuntimeError('請在 .env 填入 BYBIT_API_KEY / BYBIT_API_SECRET')

        demo    = getattr(config, 'BYBIT_DEMO',    False)
        testnet = getattr(config, 'BYBIT_TESTNET', False)
        self.session = BybitHTTP(
            testnet=testnet,
            demo=demo,
            api_key=config.BYBIT_API_KEY,
            api_secret=config.BYBIT_API_SECRET,
        )
        self._instr_cache: dict[str, dict] = {}
        self._leverage_cache: set[str] = set()

    # ── Instrument Info（精度查詢，含 cache）──────────────────────────────
    def _get_instrument(self, bybit_sym: str) -> dict:
        if bybit_sym in self._instr_cache:
            return self._instr_cache[bybit_sym]
        try:
            res = self.session.get_instruments_info(category='linear', symbol=bybit_sym)
            lst = res.get('result', {}).get('list', [])
            if lst:
                info       = lst[0]
                price_filt = info.get('priceFilter',   {})
                lot_filt   = info.get('lotSizeFilter', {})
                lev_filt   = info.get('leverageFilter', {})
                meta = {
                    'tick':     float(price_filt.get('tickSize',  '0.0001')),
                    'qty_step': float(lot_filt.get('qtyStep',     '0.001')),
                    'min_qty':  float(lot_filt.get('minOrderQty', '0.001')),
                    # Bybit 每幣對的最大槓桿（可能 50x / 75x / 100x），用於 clamp。
                    'max_lev':  float(lev_filt.get('maxLeverage', '100')),
                }
                self._instr_cache[bybit_sym] = meta
                return meta
        except Exception as e:
            print(f'[WARN] get_instruments_info {bybit_sym}: {e}')
        meta = {'tick': 0.0001, 'qty_step': 0.001, 'min_qty': 0.001, 'max_lev': 100.0}
        self._instr_cache[bybit_sym] = meta
        return meta

    def format_qty(self, symbol: str, qty: float) -> str:
        bybit_sym = _yf_to_bybit(symbol)
        meta = self._get_instrument(bybit_sym)
        step = meta['qty_step']
        floored = _floor_to_step(qty, step)
        if floored < meta['min_qty']:
            # 截斷會吃掉一半以上原始數量時提醒，避免靜默縮水
            if qty > 0 and floored / qty < 0.5:
                print(f'[WARN] {bybit_sym}: 請求 {qty} 被截斷至 0（min_qty={meta["min_qty"]}）')
            floored = 0.0
        decimals = max(0, -int(math.floor(math.log10(step)))) if step < 1 else 0
        return f'{floored:.{decimals}f}'

    def format_price(self, symbol: str, price: float) -> str:
        bybit_sym = _yf_to_bybit(symbol)
        meta = self._get_instrument(bybit_sym)
        tick = meta['tick']
        aligned = _floor_to_step(price, tick)
        decimals = max(0, -int(math.floor(math.log10(tick)))) if tick < 1 else 0
        return f'{aligned:.{decimals}f}'

    def set_leverage(self, symbol: str, leverage: int | float | None = None) -> dict:
        bybit_sym = _yf_to_bybit(symbol)
        lev = leverage if leverage is not None else getattr(config, 'BYBIT_LEVERAGE', 1)
        # Clamp 到該幣種交易所最大槓桿，避免 Bybit 以 retCode 拒絕（且原本只回 dict、上游不易察覺）
        meta = self._get_instrument(bybit_sym)
        max_lev = meta.get('max_lev', 100.0)
        if float(lev) > max_lev:
            print(f'[WARN] {bybit_sym}: 槓桿 {lev} 超過上限 {max_lev}，已 clamp')
            lev = max_lev
        lev_str = str(int(lev)) if float(lev).is_integer() else str(lev)
        try:
            res = self.session.set_leverage(
                category='linear',
                symbol=bybit_sym,
                buyLeverage=lev_str,
                sellLeverage=lev_str,
            )
            # 110043 means the requested leverage is already set.
            if res.get('retCode') in (0, 110043):
                self._leverage_cache.add(bybit_sym)
            return res
        except Exception as e:
            return {'retCode': -1, 'retMsg': str(e)}

    def _ensure_leverage(self, bybit_sym: str) -> dict:
        if bybit_sym in self._leverage_cache:
            return {'retCode': 0, 'retMsg': 'cached'}
        return self.set_leverage(bybit_sym, getattr(config, 'BYBIT_LEVERAGE', 1))

    def set_trading_stop(self, symbol: str,
                         stop_loss=None,
                         take_profit=None,
                         trailing_stop=None,
                         active_price=None,
                         position_idx: int = 0) -> dict:
        """Update Bybit full-position TP/SL/TS for an existing linear position."""
        bybit_sym = _yf_to_bybit(symbol)
        payload = {
            'category': 'linear',
            'symbol': bybit_sym,
            'tpslMode': 'Full',
            'positionIdx': position_idx,
        }
        if stop_loss is not None:
            payload['stopLoss'] = (
                stop_loss if isinstance(stop_loss, str)
                else self.format_price(symbol, float(stop_loss))
            )
            payload['slTriggerBy'] = 'LastPrice'
        if take_profit is not None:
            payload['takeProfit'] = (
                take_profit if isinstance(take_profit, str)
                else self.format_price(symbol, float(take_profit))
            )
            payload['tpTriggerBy'] = 'LastPrice'
        if trailing_stop is not None:
            payload['trailingStop'] = (
                trailing_stop if isinstance(trailing_stop, str)
                else self.format_price(symbol, float(trailing_stop))
            )
        if active_price is not None:
            payload['activePrice'] = (
                active_price if isinstance(active_price, str)
                else self.format_price(symbol, float(active_price))
            )

        try:
            res = self.session.set_trading_stop(**payload)
            if res.get('retCode') != 0:
                raise OrderRejected(f'{symbol}: set_trading_stop failed {res}')
            return res
        except OrderRejected:
            raise
        except Exception as e:
            raise OrderRejected(f'{symbol}: set_trading_stop exception {e}') from e

    def place_order(self, symbol, direction, qty, stop_loss, take_profit,
                    order_type: str = 'Market') -> dict:
        side = 'Buy' if direction == 1 else 'Sell'
        bybit_sym = _yf_to_bybit(symbol)

        qty_str = qty if isinstance(qty, str) else self.format_qty(symbol, float(qty))
        sl_str  = stop_loss   if isinstance(stop_loss,   str) else self.format_price(symbol, float(stop_loss))
        tp_str  = take_profit if isinstance(take_profit, str) else self.format_price(symbol, float(take_profit))

        if float(qty_str) <= 0:
            raise OrderRejected(f'{symbol}: qty {qty} 低於 minOrderQty / step；訂單不送出')

        try:
            lev_res = self._ensure_leverage(bybit_sym)
            if lev_res.get('retCode') not in (0, 110043):
                raise OrderRejected(f'{symbol}: set_leverage 失敗 {lev_res}')

            res = self.session.place_order(
                category='linear',
                symbol=bybit_sym,
                side=side,
                orderType=order_type,
                qty=qty_str,
                stopLoss=sl_str,
                takeProfit=tp_str,
                tpslMode='Full',
                positionIdx=0,
                tpOrderType='Market',
                slOrderType='Market',
                timeInForce='GTC',
                slTriggerBy='LastPrice',
                tpTriggerBy='LastPrice',
            )
            if res.get('retCode') != 0:
                raise OrderRejected(f'{symbol}: place_order 失敗 {res}')
            return res
        except OrderRejected:
            raise
        except Exception as e:
            raise OrderRejected(f'{symbol}: place_order 例外 {e}') from e

    def close_position(self, symbol: str, qty: float, direction: int) -> dict:
        close_side = 'Sell' if direction == 1 else 'Buy'
        bybit_sym  = _yf_to_bybit(symbol)
        qty_str    = self.format_qty(symbol, float(qty))
        if float(qty_str) <= 0:
            return {'retCode': -1, 'retMsg': f'close qty {qty} 低於 minOrderQty'}
        try:
            return self.session.place_order(
                category='linear',
                symbol=bybit_sym,
                side=close_side,
                orderType='Market',
                qty=qty_str,
                reduceOnly=True,
            )
        except Exception as e:
            return {'retCode': -1, 'retMsg': str(e)}

    def get_positions(self) -> list[dict]:
        try:
            res = self.session.get_positions(category='linear', settleCoin='USDT')
            return res.get('result', {}).get('list', [])
        except Exception as e:
            print(f'[ERROR] get_positions: {e}')
            return []

    def get_executions(self, symbol: str, limit: int = 100) -> list[dict]:
        """Return recent linear execution history for a symbol."""
        bybit_sym = _yf_to_bybit(symbol)
        try:
            res = self.session.get_executions(
                category='linear',
                symbol=bybit_sym,
                limit=limit,
            )
            return res.get('result', {}).get('list', [])
        except Exception as e:
            print(f'[ERROR] get_executions {bybit_sym}: {e}')
            return []

    def get_balance(self) -> float:
        try:
            res = self.session.get_wallet_balance(accountType='UNIFIED', coin='USDT')
            items = res.get('result', {}).get('list', [{}])
            for item in items:
                for coin in item.get('coin', []):
                    if coin.get('coin') == 'USDT':
                        val = coin.get('walletBalance') or coin.get('availableToWithdraw') or '0'
                        return float(val) if val else 0.0
            return 0.0
        except Exception as e:
            print(f'[ERROR] get_balance: {e}')
            return 0.0

    def is_market_open(self) -> bool:
        return True   # crypto 24/7
