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
]
