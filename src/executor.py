"""
Bybit 執行器（僅限加密貨幣）。
股票/大宗商品不在 Bybit 支援範圍，需接不同券商 API。
使用前請在 config.py 填入真實 API Key。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

try:
    from pybit.unified_trading import HTTP as BybitHTTP
    PYBIT_AVAILABLE = True
except ImportError:
    PYBIT_AVAILABLE = False
    print('[WARN] pybit 未安裝，即時交易功能不可用。執行: pip install pybit')


def _yf_to_bybit(symbol: str) -> str:
    """BTC-USD → BTCUSDT"""
    return symbol.replace('-USD', 'USDT')


class BybitExecutor:
    def __init__(self):
        if not PYBIT_AVAILABLE:
            raise RuntimeError('pybit 未安裝')
        if not config.BYBIT_API_KEY or not config.BYBIT_API_SECRET:
            raise RuntimeError('請在 config.py 填入 BYBIT_API_KEY / BYBIT_API_SECRET')

        demo    = getattr(config, 'BYBIT_DEMO',    False)
        testnet = getattr(config, 'BYBIT_TESTNET', False)
        self.session = BybitHTTP(
            testnet=testnet,
            demo=demo,
            api_key=config.BYBIT_API_KEY,
            api_secret=config.BYBIT_API_SECRET,
        )

    def place_order(self,
                    symbol: str,
                    direction: int,
                    qty: float,
                    stop_loss: float,
                    take_profit: float,
                    order_type: str = 'Market') -> dict:
        side = 'Buy' if direction == 1 else 'Sell'
        bybit_sym = _yf_to_bybit(symbol)
        try:
            res = self.session.place_order(
                category='linear',
                symbol=bybit_sym,
                side=side,
                orderType=order_type,
                qty=str(round(qty, 4)),
                stopLoss=str(round(stop_loss, 6)),
                takeProfit=str(round(take_profit, 6)),
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
        try:
            return self.session.place_order(
                category='linear',
                symbol=bybit_sym,
                side=close_side,
                orderType='Market',
                qty=str(round(qty, 4)),
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
                        return float(coin.get('availableToWithdraw', 0))
            return 0.0
        except Exception as e:
            print(f'[ERROR] get_balance: {e}')
            return 0.0
