"""
向後相容 shim：原本 `from src.executor import BybitExecutor` 仍可用。
新程式請改 import 自 `src.executors`：

    from src.executors import BybitExecutor, ExecutorRouter
"""
from src.executors.bybit    import BybitExecutor   # noqa: F401
from src.executors.ibkr     import IBKRExecutor    # noqa: F401
from src.executors.shinkong import ShinKongExecutor  # noqa: F401
from src.executors.router   import ExecutorRouter  # noqa: F401
