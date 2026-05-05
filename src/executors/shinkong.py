"""
新光證券 (Shin Kong Securities) 執行器骨架。

⚠️ SDK 確認事項（請與你的營業員或新光官方文件確認）：
  新光證券對 Python 程式交易支援的方式可能是以下幾種之一：
    A. 自家 REST API（少數券商有，需向客服申請憑證）
    B. 透過群益 API gateway 串接（部分台股券商共用）
    C. 透過 Mastel / Multicharts / 其他第三方平台
    D. 僅支援 HTS / 桌面下單（無 API）

  最常見的台股 Python SDK 是【永豐 Shioaji】（pip install shioaji）；
  若新光不提供 Python SDK，務實的選項是：
    1) 改用永豐金證券（同樣可下單台股，Shioaji 文件最齊全）
    2) 用第三方下單工具如 XQ / 全球贏家提供的 API

  在你回報實際 SDK 名稱前，本檔保留通用 TW 股介面骨架。

下單規範（不論哪家券商都通用）：
  - 最小單位：1 張 = 1000 股；零股需另開 "現股零股" 單別
  - 漲跌停：±10%（生技/低價股例外）
  - 交易時段：09:00-13:30（盤中），14:00-14:30 盤後零股
  - T+2 交割
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config
from src.executors.base import BaseExecutor

# TODO: 確定 SDK 後 import
# 例如 (永豐): import shioaji as sj
# 例如 (假設有):  import shinkong_api as sk


class ShinKongExecutor(BaseExecutor):
    asset_class = 'TW Stock'

    def __init__(self,
                 api_key: str = '',
                 api_secret: str = '',
                 ca_path: str = '',
                 ca_passwd: str = '',
                 simulation: bool = True):
        """
        台股下單通常需要：
          - API Key / Secret（向券商申請）
          - 憑證檔 (.pfx) + 憑證密碼（CA，新光要本人臨櫃或網路下載）
          - simulation=True 走模擬，False 才打真錢
        """
        # TODO: 實連
        # self.api = sj.Shioaji(simulation=simulation)
        # self.api.login(api_key, api_secret)
        # self.api.activate_ca(ca_path=ca_path, ca_passwd=ca_passwd, person_id=...)
        self.api_key   = api_key
        self.api_secret = api_secret
        self.simulation = simulation
        self._connected = False
        raise NotImplementedError(
            'ShinKongExecutor 尚未接通；'
            '請先確認新光證券提供的 Python SDK 名稱（見檔案開頭註解），'
            '再把以下方法的 TODO 換成真實作'
        )

    # ── Symbol 規範化 ─────────────────────────────────────────────────────
    def _to_tw_code(self, symbol: str) -> str:
        """'2330.TW' → '2330'；上櫃 .TWO 同處理"""
        return symbol.replace('.TW', '').replace('.TWO', '')

    # ── 帳戶 ───────────────────────────────────────────────────────────────
    def get_balance(self) -> float:
        """回傳台幣可用餘額。"""
        # TODO: self.api.account_balance()
        raise NotImplementedError

    # ── 下單 ───────────────────────────────────────────────────────────────
    def place_order(self, symbol, direction, qty, stop_loss, take_profit,
                    order_type: str = 'Market') -> dict:
        """
        台股下單邏輯：
          - qty 應該是「股數」（1 張 = 1000 股）
          - 多單 ROD（限價）或 IOC（市價當日有效）
          - 台股不能放空現股；放空需借券或現沖（先賣後買，當日平倉）
          - SL/TP 必須拆成「條件單」或自己用程式輪詢價格
        """
        # 台股做空限制檢查
        if direction == -1:
            return {
                'retCode': -1,
                'retMsg': 'TW Stock 做空需借券/現沖額度，請確認帳戶權限'
            }
        # TODO:
        # contract = self.api.Contracts.Stocks.TSE[self._to_tw_code(symbol)]
        # order    = self.api.Order(action='Buy', price=..., quantity=...,
        #                            order_type='ROD', price_type='LMT')
        # res      = self.api.place_order(contract, order)
        return {'retCode': -1, 'retMsg': 'ShinKong.place_order 尚未實作'}

    def close_position(self, symbol: str, qty: float, direction: int) -> dict:
        # TODO: 反向賣出
        return {'retCode': -1, 'retMsg': 'ShinKong.close_position 尚未實作'}

    # ── 精度 ───────────────────────────────────────────────────────────────
    def format_qty(self, symbol: str, qty: float) -> str:
        """台股按張下單；qty 為股數 → 取整千股對齊。"""
        zhang = int(qty // 1000) * 1000   # 向下取整到最近千股
        return str(max(0, zhang))

    def format_price(self, symbol: str, price: float) -> str:
        """
        台股 tick 階梯（依價位範圍）：
          < 10        : 0.01
          10  - 50    : 0.05
          50  - 100   : 0.1
          100 - 500   : 0.5
          500 - 1000  : 1
          > 1000      : 5
        """
        p = float(price)
        if p < 10:    tick = 0.01
        elif p < 50:  tick = 0.05
        elif p < 100: tick = 0.1
        elif p < 500: tick = 0.5
        elif p < 1000:tick = 1.0
        else:         tick = 5.0
        aligned = round(p / tick) * tick
        if   tick == 0.01: return f'{aligned:.2f}'
        elif tick == 0.05: return f'{aligned:.2f}'
        elif tick == 0.1:  return f'{aligned:.1f}'
        else:              return f'{aligned:.1f}'

    # ── 市場時間 ───────────────────────────────────────────────────────────
    def is_market_open(self) -> bool:
        """台股盤中：週一至週五 09:00-13:30（不考慮國定假日）。"""
        from datetime import datetime
        now = datetime.now()
        if now.weekday() >= 5:   # 週末
            return False
        mins = now.hour * 60 + now.minute
        return 9 * 60 <= mins <= 13 * 60 + 30
