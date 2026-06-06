"""
apps/demo_trading/config.py
TASK-014: Bybit Demo Trading — 10-slot fractional Kelly portfolio configuration.

All constants here govern ONLY the Demo Trading path.
They are intentionally separate from the live-trading config (config.py / src/risk.py)
so that changes here CANNOT affect live account behaviour.

SAFETY INVARIANTS (this file):
  - No connection to Bybit is opened here.
  - No order is placed here.
  - This module is import-only configuration.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Environment guard — must be DEMO, never LIVE
# ---------------------------------------------------------------------------
REQUIRED_DEMO_FLAG   = True    # BybitHTTP(demo=True) must be set
REQUIRED_TESTNET_FLAG = False  # testnet.bybit.com is a different env; not used here
DEMO_ENVIRONMENT_LABEL = "bybit_demo_trading"

# ---------------------------------------------------------------------------
# Portfolio position limits (hard caps — enforced before any sizing)
# ---------------------------------------------------------------------------
MAX_OPEN_POSITIONS   = 10
MAX_LONG_POSITIONS   = 5
MAX_SHORT_POSITIONS  = 5

# ---------------------------------------------------------------------------
# Portfolio-level fractional Kelly risk budget
#
# DEFINITION: KELLY_MULTIPLIER applies to the ENTIRE portfolio, not per trade.
#   total_risk_budget_usd = equity_usd × KELLY_MULTIPLIER
#
# With KELLY_MULTIPLIER = 0.4 and equity = $10,000:
#   total_risk_budget = $4,000
#
# If 5 positions are already open and each risks $300 (total $1,500):
#   remaining_risk_budget = $4,000 − $1,500 = $2,500
#   available_slots       = 10 − 5          = 5
#   per_slot_risk         = $2,500 / 5      = $500
# ---------------------------------------------------------------------------
KELLY_MULTIPLIER     = 0.40   # 40% of equity as total risk budget (portfolio-level)

# Absolute floor: if remaining budget per slot < this, refuse new position
MIN_RISK_PER_SLOT_USD = 1.0   # $1 minimum (prevents $0 / epsilon positions)

# ---------------------------------------------------------------------------
# Exposure hard caps (notional / equity)
# ---------------------------------------------------------------------------
MAX_GROSS_EXPOSURE_RATIO = 1.0    # sum(abs(notional)) / equity
MAX_NET_EXPOSURE_RATIO   = 0.5    # abs(long_notional + short_notional) / equity
MAX_SINGLE_POSITION_PCT  = 0.20   # abs(single_notional) / equity

# ---------------------------------------------------------------------------
# Stop distance guards
# ---------------------------------------------------------------------------
MIN_STOP_DISTANCE_PCT = 0.001   # 0.1% — below this, stop is invalid
MAX_STOP_DISTANCE_PCT = 0.50    # 50%  — above this, position would be minuscule → reject

# ---------------------------------------------------------------------------
# Position size guards
# ---------------------------------------------------------------------------
MIN_POSITION_NOTIONAL_USD = 10.0   # $10 minimum notional

# ---------------------------------------------------------------------------
# Reject reason constants
# ---------------------------------------------------------------------------
REJECT_MAX_OPEN_POSITIONS          = "max_open_positions"
REJECT_MAX_LONG_POSITIONS          = "max_long_positions"
REJECT_MAX_SHORT_POSITIONS         = "max_short_positions"
REJECT_INSUFFICIENT_RISK_BUDGET    = "insufficient_risk_budget"
REJECT_INSUFFICIENT_AVAILABLE_BAL  = "insufficient_available_balance"
REJECT_INVALID_KELLY               = "invalid_kelly"
REJECT_INVALID_STOP_DISTANCE       = "invalid_stop_distance"
REJECT_MAX_GROSS_EXPOSURE          = "max_gross_exposure"
REJECT_MAX_NET_EXPOSURE            = "max_net_exposure"
REJECT_DEMO_GUARD_FAILED           = "demo_environment_guard_failed"
REJECT_POSITION_TOO_SMALL          = "position_notional_below_minimum"
