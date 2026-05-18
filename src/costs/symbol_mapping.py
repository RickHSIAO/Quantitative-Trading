from __future__ import annotations

BYBIT_PREFIX = "BYBIT:"
PERP_SUFFIX = ".P"
QUOTE_SUFFIX = "USDT"
DEFAULT_EXCHANGE = "bybit_perp"


def to_funding_symbol(perp_symbol: str) -> str:
    """Convert a Bybit perp symbol to the raw funding symbol used by Bybit APIs."""
    if not isinstance(perp_symbol, str):
        raise ValueError("perp_symbol must be a string")
    if not perp_symbol.startswith(BYBIT_PREFIX) or not perp_symbol.endswith(PERP_SUFFIX):
        raise ValueError(f"unsupported Bybit perp symbol format: {perp_symbol!r}")

    core = perp_symbol[len(BYBIT_PREFIX) : -len(PERP_SUFFIX)]
    if not core or core != core.upper() or not core.endswith(QUOTE_SUFFIX):
        raise ValueError(f"unsupported Bybit USDT perp symbol: {perp_symbol!r}")
    return core


def to_perp_symbol(funding_symbol: str, exchange: str = DEFAULT_EXCHANGE) -> str:
    """Convert a raw Bybit funding symbol to the canonical run008 perp symbol."""
    if exchange != DEFAULT_EXCHANGE:
        raise ValueError(f"unsupported exchange: {exchange!r}")
    if not isinstance(funding_symbol, str):
        raise ValueError("funding_symbol must be a string")
    if not funding_symbol or funding_symbol != funding_symbol.upper():
        raise ValueError(f"unsupported funding symbol: {funding_symbol!r}")
    if funding_symbol.startswith(BYBIT_PREFIX) or funding_symbol.endswith(PERP_SUFFIX):
        raise ValueError(f"funding symbol must be raw Bybit format: {funding_symbol!r}")
    if not funding_symbol.endswith(QUOTE_SUFFIX):
        raise ValueError(f"unsupported non-USDT funding symbol: {funding_symbol!r}")
    return f"{BYBIT_PREFIX}{funding_symbol}{PERP_SUFFIX}"

