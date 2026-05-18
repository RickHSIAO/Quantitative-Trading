from __future__ import annotations

import pandas as pd

from src.costs.config import FeeConfig, Scenario


def apply_fee_cost(events: pd.DataFrame, scenario: Scenario, fees: FeeConfig) -> pd.Series:
    entry_bps = _side_bps(scenario.entry_side, scenario, fees)
    exit_bps = _side_bps(scenario.exit_side, scenario, fees)
    return (
        events["entry_turnover"].astype(float) * entry_bps
        + events["exit_turnover"].astype(float) * exit_bps
    ) / 10000.0


def _side_bps(side: str, scenario: Scenario, fees: FeeConfig) -> float:
    if side == "maker":
        return float(fees.maker_bps) * float(scenario.fee_multiplier_maker)
    if side == "taker":
        return float(fees.taker_bps) * float(scenario.fee_multiplier_taker)
    raise ValueError(f"unsupported fee side: {side}")
