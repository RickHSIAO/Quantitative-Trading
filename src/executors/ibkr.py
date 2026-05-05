"""
Interactive Brokers (盈透) 執行器骨架。

覆蓋範圍：
  - 美股現股（AAPL/MSFT/...）
  - 黃金期貨 GC=F、白銀期貨 SI=F（透過 IBKR 期貨合約）
  - 未來可擴充：美債、外匯

連線方式：
  IBKR API 必須透過本機跑 TWS（桌面交易軟體）或 IB Gateway（無 GUI 版）
  Python SDK：ib_insync
  預設 paper trading port = 7497；live port = 7496

上線前準備：
  1. 開 IBKR 帳戶 (https://www.interactivebrokers.com)
  2. 下載並啟動 TWS 或 IB Gateway
  3. TWS 設定 → API → Settings：
       - 勾 "Enable ActiveX and Socket Clients"
       - 取消勾 "Read-Only API"
       - 確認 Socket port (預設 7497)
  4. pip install ib_insync
  5. 把以下 NotImplementedError 換成真實作
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config
from src.executors.base import BaseExecutor

try:
    from ib_insync import IB, Stock, Future, MarketOrder, LimitOrder, Order  # noqa
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False


# ─── 符號映射 ─────────────────────────────────────────────────────────────────
# 你的 config 用 yfinance 風格符號，IBKR 需要 Contract 物件
_COMMODITY_TO_IBKR_FUTURE = {
    'XAUUSD': ('GC',  'COMEX',  'USD'),   # 黃金期貨
    'XAGUSD': ('SI',  'COMEX',  'USD'),   # 白銀期貨
}


class IBKRExecutor(BaseExecutor):
    asset_class = 'US Stock + Commodity'

    def __init__(self,
                 host: str = '127.0.0.1',
                 port: int = 7497,        # 7497 = paper, 7496 = live
                 client_id: int = 1):
        if not IB_INSYNC_AVAILABLE:
            raise RuntimeError('ib_insync 未安裝。執行: pip install ib_insync')
        # TODO: 實連 TWS / IB Gateway
        # self.ib = IB()
        # self.ib.connect(host, port, clientId=client_id)
        self.host = host
        self.port = port
        self.client_id = client_id
        self._connected = False
        raise NotImplementedError(
            'IBKRExecutor 尚未接通；'
            '請完成 TWS/Gateway 安裝並在 cmd_live 啟用此執行器後實作 connect()'
        )

    # ── 帳戶 ───────────────────────────────────────────────────────────────
    def get_balance(self) -> float:
        # TODO: self.ib.accountSummary() → 找 'AvailableFunds' (USD)
        raise NotImplementedError

    # ── Symbol → IBKR Contract ─────────────────────────────────────────────
    def _to_contract(self, symbol: str):
        """
        將 yfinance 風格 symbol 轉成 IBKR Contract：
          'AAPL'    → Stock('AAPL', 'SMART', 'USD')
          'XAUUSD'  → Future('GC', exchange='COMEX', currency='USD', lastTradeDateOrContractMonth=...)
        """
        if symbol in _COMMODITY_TO_IBKR_FUTURE:
            # TODO: 期貨還要決定到期月份；建議用最近月或 continuous (depends on broker support)
            sym, exch, ccy = _COMMODITY_TO_IBKR_FUTURE[symbol]
            # return Future(sym, exchange=exch, currency=ccy, lastTradeDateOrContractMonth='...')
            raise NotImplementedError(f'期貨 {symbol} 合約映射尚未實作')
        # 美股
        # return Stock(symbol, 'SMART', 'USD')
        raise NotImplementedError(f'股票 {symbol} contract 建立尚未實作')

    # ── 下單 ───────────────────────────────────────────────────────────────
    def place_order(self, symbol, direction, qty, stop_loss, take_profit,
                    order_type: str = 'Market') -> dict:
        """
        下單。IBKR 推薦用 bracket order（主單 + SL + TP 三張關聯）：
          parent  = MarketOrder('BUY', qty)
          tp_ord  = LimitOrder('SELL', qty, take_profit, parentId=parent.orderId)
          sl_ord  = StopOrder('SELL',  qty, stop_loss,   parentId=parent.orderId)
        """
        # TODO:
        # contract = self._to_contract(symbol)
        # parent   = MarketOrder('BUY' if direction==1 else 'SELL',
        #                        float(qty), transmit=False)
        # parent_trade = self.ib.placeOrder(contract, parent)
        # tp = LimitOrder(...); sl = StopOrder(...); 都帶 parentId
        # ...
        return {'retCode': -1, 'retMsg': 'IBKR.place_order 尚未實作'}

    def close_position(self, symbol: str, qty: float, direction: int) -> dict:
        # TODO: contract + reverse-side market order
        return {'retCode': -1, 'retMsg': 'IBKR.close_position 尚未實作'}

    # ── 精度（美股最小單位 = 1 股；期貨依合約乘數）──────────────────────
    def format_qty(self, symbol: str, qty: float) -> str:
        if symbol in _COMMODITY_TO_IBKR_FUTURE:
            # 期貨整數口數
            return str(int(max(0, qty)))
        # 美股：IBKR 支援零股（fractional）但需要 cash account；保守取整數股
        return str(int(max(0, qty)))

    def format_price(self, symbol: str, price: float) -> str:
        # 美股 tick = $0.01；期貨各合約不同（GC=$0.10、SI=$0.005）
        if symbol == 'XAUUSD':
            return f'{round(price * 10) / 10:.1f}'
        if symbol == 'XAGUSD':
            return f'{round(price * 200) / 200:.3f}'
        return f'{round(price, 2):.2f}'

    # ── 市場時間（台北時區判斷美股盤）──────────────────────────────────────
    def is_market_open(self) -> bool:
        """
        美股常規時段：台北時間 22:30 - 05:00（夏令）/ 23:30 - 06:00（冬令）
        期貨幾乎 23h，但仍有 maintenance window
        TODO: 用 ib_insync.util.isMarketOpen 或自寫日曆
        """
        from datetime import datetime
        hr = datetime.now().hour
        return hr >= 21 or hr < 6
