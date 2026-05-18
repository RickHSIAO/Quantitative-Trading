from __future__ import annotations

import pandas as pd

from src.costs.config import Scenario


def apply_slippage_cost(events: pd.DataFrame, scenario: Scenario) -> pd.Series:
    bps = float(scenario.slippage_bps_one_side)
    return events["trade_turnover"].astype(float) * bps / 10000.0
