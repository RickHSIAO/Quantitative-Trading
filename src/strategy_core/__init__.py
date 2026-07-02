"""Pure, adapter-agnostic strategy-core contracts shared by the future Live,
Backtest, Forward, Paper and Demo history adapters.

This package is intentionally free of filesystem, network, credential and
wall-clock I/O. It defines immutable data structures, validation,
canonicalization and deterministic fingerprints only.
"""
from src.strategy_core.trade_history import (
    CompletenessStatus,
    ConflictingDuplicateError,
    PnlBasis,
    SourceType,
    TradeHistoryRecord,
    TradeHistorySnapshot,
    TradeHistoryValidationError,
    UnsupportedPnlBasisError,
    SCHEMA_VERSION_V1,
)
from src.strategy_core.live_trade_history_adapter import (
    LiveSourceCompleteness,
    LiveTradeHistoryAdapterError,
    adapt_live_history_rows,
    adapt_same_process_close_events,
)
from src.strategy_core.entry_decision import (
    EntryAction,
    EntryDecisionInput,
    EntryDecisionResult,
    EntryReasonCode,
    decide_entry,
    dominant_strategy_family,
)
from src.strategy_core.exit_decision import (
    ExitAction,
    ExitDecisionInput,
    ExitDecisionResult,
    decide_exit,
)

__all__ = [
    "CompletenessStatus",
    "ConflictingDuplicateError",
    "PnlBasis",
    "SourceType",
    "TradeHistoryRecord",
    "TradeHistorySnapshot",
    "TradeHistoryValidationError",
    "UnsupportedPnlBasisError",
    "SCHEMA_VERSION_V1",
    "LiveSourceCompleteness",
    "LiveTradeHistoryAdapterError",
    "adapt_live_history_rows",
    "adapt_same_process_close_events",
    "EntryAction",
    "EntryDecisionInput",
    "EntryDecisionResult",
    "EntryReasonCode",
    "decide_entry",
    "dominant_strategy_family",
    "ExitAction",
    "ExitDecisionInput",
    "ExitDecisionResult",
    "decide_exit",
]
