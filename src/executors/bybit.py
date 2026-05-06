"""
Bybit 執行器（加密貨幣永續合約）。
"""
from __future__ import annotations
import sys, os, math
from decimal import Decimal
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config
from src.executors.base import BaseExecutor

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

    # ── Instrument Info（精度查詢，含 cache）──────────────────────────────
    def _get_instrument(self, bybit_sym: str) -> dict:
        if bybit_sym in self._instr_cache:
            return self._instr_cache[bybit_sym]
        try:
            res = self.session.get_instruments_info(category='linear', symbol=bybit_sym)
            lst = res.get('result', {}).get('list', [])
            if lst:
                info       = lst[0]
                price_filt = info.get('priceFilter',  {})
                lot_filt   = info.get('lotSizeFilter', {})
                meta = {
                    'tick':     float(price_filt.get('tickSize',  '0.0001')),
                    'qty_step': float(lot_filt.get('qtyStep',     '0.001')),
                    'min_qty':  float(lot_filt.get('minOrderQty', '0.001')),
                }
                self._instr_cache[bybit_sym] = meta
                return meta
        except Exception as e:
            print(f'[WARN] get_instruments_info {bybit_sym}: {e}')
        meta = {'tick': 0.0001, 'qty_step': 0.001, 'min_qty': 0.001}
        self._instr_cache[bybit_sym] = meta
        return meta

    def format_qty(self, symbol: str, qty: float) -> str:
        bybit_sym = _yf_to_bybit(symbol)
        meta = self._get_instrument(bybit_sym)
        step = meta['qty_step']
        floored = _floor_to_step(qty, step)
        if floored < meta['min_qty']:
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

    def place_order(self, symbol, direction, qty, stop_loss, take_profit,
                    order_type: str = 'Market') -> dict:
        side = 'Buy' if direction == 1 else 'Sell'
        bybit_sym = _yf_to_bybit(symbol)

        qty_str = qty if isinstance(qty, str) else self.format_qty(symbol, float(qty))
        sl_str  = stop_loss   if isinstance(stop_loss,   str) else self.format_price(symbol, float(stop_loss))
        tp_str  = take_profit if isinstance(take_profit, str) else self.format_price(symbol, float(take_profit))

        if float(qty_str) <= 0:
            return {'retCode': -1, 'retMsg': f'qty {qty} 低於 minOrderQty'}

        try:
            res = self.session.place_order(
                category='linear',
                symbol=bybit_sym,
                side=side,
                orderType=order_type,
                qty=qty_str,
                stopLoss=sl_str,
                takeProfit=tp_str,
                timeInForce='GTC',
                slTriggerBy='LastPrice',
                tpTriggerBy='LastPrice',
            )
            return res
        except Exception as e:
            return {'retCode': -1, 'retMsg': str(e)}

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
