"""
執行器路由：依 symbol 分派到正確的 broker。

使用：
    from src.executors.router import ExecutorRouter
    router = ExecutorRouter(enable={'Crypto': True, 'US Stock': False, ...})
    executor = router.get('AAPL')      # → IBKRExecutor
    executor = router.get('2330.TW')   # → ShinKongExecutor
    executor = router.get('BYBIT:BTCUSDT.P')  # → BybitExecutor
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config
from src.fetcher import asset_type_of
from src.executors.base import BaseExecutor


class ExecutorRouter:
    """依 asset_type 分派執行器；支援延遲建構（lazy init）+ enable 開關。"""

    def __init__(self, enable: dict[str, bool] | None = None):
        # 預設只啟用 Crypto（其他 broker 還未實連）
        self.enable = enable or {
            'Crypto':    True,
            'US Stock':  False,
            'Commodity': False,
            'TW Stock':  False,
        }
        self._cache: dict[str, BaseExecutor] = {}

    # ── 工廠 ───────────────────────────────────────────────────────────────
    def _build(self, asset_type: str) -> BaseExecutor:
        if asset_type == 'Crypto':
            from src.executors.bybit import BybitExecutor
            return BybitExecutor()
        if asset_type in ('US Stock', 'Commodity'):
            from src.executors.ibkr import IBKRExecutor
            return IBKRExecutor()
        if asset_type == 'TW Stock':
            from src.executors.shinkong import ShinKongExecutor
            return ShinKongExecutor()
        raise ValueError(f'未知資產類別：{asset_type}')

    def get(self, symbol: str) -> BaseExecutor | None:
        """
        回傳該 symbol 的執行器；若該類別停用或建構失敗，回傳 None。
        建構失敗的訊息會印到 stderr，不會中斷主程式。
        """
        atype = asset_type_of(symbol)
        if not self.enable.get(atype, False):
            return None

        if atype in self._cache:
            return self._cache[atype]

        try:
            ex = self._build(atype)
        except (RuntimeError, NotImplementedError, ImportError) as e:
            print(f'[WARN] {atype} 執行器建構失敗：{e}')
            self.enable[atype] = False    # 自動禁用，避免反覆嘗試
            return None

        self._cache[atype] = ex
        return ex

    # ── 主迴圈用 ───────────────────────────────────────────────────────────
    def is_market_open(self, symbol: str) -> bool:
        ex = self.get(symbol)
        return ex.is_market_open() if ex else False

    def warmup(self) -> None:
        """主動把所有啟用的執行器建構出來（連線、查精度等），失敗自動禁用。"""
        for atype, on in list(self.enable.items()):
            if not on:
                continue
            try:
                self._cache[atype] = self._build(atype)
            except (RuntimeError, NotImplementedError, ImportError) as e:
                print(f'[WARN] {atype} 執行器建構失敗：{e}')
                self.enable[atype] = False

    def get_balances(self) -> dict[str, float]:
        """回傳每家已建構的 broker 的餘額。"""
        out = {}
        for atype, ex in self._cache.items():
            try:
                out[atype] = ex.get_balance()
            except Exception as e:
                print(f'[WARN] {atype} get_balance: {e}')
        return out
