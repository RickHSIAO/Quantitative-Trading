"""
執行器抽象基底（合約）。
所有 broker 接口都實作這個介面，上層 router 不需要關心是哪家券商。
"""
from __future__ import annotations
from abc import ABC, abstractmethod


class BaseExecutor(ABC):
    """所有 broker 執行器共同介面。"""

    asset_class: str = ''   # e.g. 'Crypto', 'US Stock', 'TW Stock', 'Commodity'

    # ── 帳戶 ───────────────────────────────────────────────────────────────
    @abstractmethod
    def get_balance(self) -> float:
        """回傳該 broker 帳戶可用餘額（以該帳戶幣別為單位）。"""

    # ── 下單 ───────────────────────────────────────────────────────────────
    @abstractmethod
    def place_order(self,
                    symbol: str,
                    direction: int,        # +1 = Long, -1 = Short
                    qty,                   # str（已對齊精度）或 float
                    stop_loss,             # str 或 float
                    take_profit,           # str 或 float
                    order_type: str = 'Market') -> dict:
        """
        下單入口。
        回傳格式：{'retCode': int, 'retMsg': str, 'orderId': str | None, ...}
        retCode == 0 視為成功。
        """

    @abstractmethod
    def close_position(self, symbol: str, qty: float, direction: int) -> dict:
        """平倉。回傳格式同 place_order。"""

    # ── 精度對齊 ───────────────────────────────────────────────────────────
    @abstractmethod
    def format_qty(self, symbol: str, qty: float) -> str:
        """依該 broker 規定的最小單位向下對齊（張/股/口/顆）。"""

    @abstractmethod
    def format_price(self, symbol: str, price: float) -> str:
        """依該 broker 規定的 tick 對齊。"""

    # ── 市場時間 ───────────────────────────────────────────────────────────
    def is_market_open(self) -> bool:
        """是否處於該市場交易時段。預設總是 True；股票執行器應覆寫。"""
        return True
