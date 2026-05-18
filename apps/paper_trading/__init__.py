"""TASK-006 offline paper-trading planning package.

The package is intentionally limited to local planning, simulation, and
logging. It does not contain exchange clients or external execution paths.
"""

from apps.paper_trading.config import PaperTradingConfig

__all__ = ["PaperTradingConfig"]
