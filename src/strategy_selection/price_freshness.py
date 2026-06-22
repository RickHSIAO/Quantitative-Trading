"""TASK-014BZ_FIX2 -- stale-cache vs fresh-mark vs multi-day catch-up classification.

Daily mark freshness is derived from the STRUCTURAL positions artifacts
(``prev3y_crypto/<date>_positions.parquet`` -> a deterministic price-vector
fingerprint of sorted ``symbol`` + ``hypothetical_fill_px``) combined with the
operational ``data_source`` from ``prev3y_crypto/<date>_pnl.json``.

Two analytical scopes are kept distinct:
  A. Calendar holding-period scope (all official calendar days; the +6.077668%
     30-day holding return is valid here).
  B. Fresh one-day risk-observation scope (ENTRY_PRICE_ANCHOR,
     STALE_CACHE_NO_PRICE_CHANGE and FRESH_MULTI_DAY_CATCHUP_MARK are EXCLUDED;
     only FRESH_DAILY_MARK days feed daily Sharpe/Sortino/streaks).

When no parquet engine is available (price vector unreadable) every date is
PRICE_FRESHNESS_UNAVAILABLE and daily risk metrics fail closed.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any, Mapping, Sequence

TASK_ID = "TASK-014BZ_FIX2"

ENTRY_PRICE_ANCHOR = "ENTRY_PRICE_ANCHOR"
STALE_CACHE_NO_PRICE_CHANGE = "STALE_CACHE_NO_PRICE_CHANGE"
FRESH_MULTI_DAY_CATCHUP_MARK = "FRESH_MULTI_DAY_CATCHUP_MARK"
FRESH_DAILY_MARK = "FRESH_DAILY_MARK"
PRICE_FRESHNESS_UNAVAILABLE = "PRICE_FRESHNESS_UNAVAILABLE"

# Documented minimum count of FRESH_DAILY_MARK observations required before daily
# risk ratios are published (review threshold; mirrors the 20-day minimum).
MIN_FRESH_DAILY_OBSERVATIONS = 20
INSUFFICIENT_FRESH_DAILY_OBSERVATIONS = "INSUFFICIENT_FRESH_DAILY_OBSERVATIONS"

# Candidate column names for the per-symbol hypothetical fill price.
_PX_COLUMNS = ("hypothetical_fill_px", "fill_px", "price", "px", "close")
_SYMBOL_COLUMNS = ("symbol", "ticker", "instrument")


def build_price_vector_fingerprint(positions_path: str | pathlib.Path) -> str | None:
    """Deterministic fingerprint of the sorted (symbol, hypothetical_fill_px) price
    vector. Returns None when the parquet artifact is missing or no parquet engine
    is installed (never fabricated)."""
    p = pathlib.Path(positions_path)
    if not p.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_parquet(p)
    except Exception:  # noqa: BLE001 -- missing engine / unreadable -> UNAVAILABLE
        return None
    sym_col = next((c for c in _SYMBOL_COLUMNS if c in df.columns), None)
    px_col = next((c for c in _PX_COLUMNS if c in df.columns), None)
    if sym_col is None or px_col is None:
        return None
    pairs = []
    for _, r in df.iterrows():
        try:
            sym = str(r[sym_col]).strip().upper()
            px = float(r[px_col])
        except (TypeError, ValueError):
            continue
        pairs.append((sym, px))
    pairs.sort(key=lambda x: x[0])
    payload = "|".join(f"{s}:{px:.10g}" for s, px in pairs)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_data_source(pnl_json_path: str | pathlib.Path) -> str | None:
    p = pathlib.Path(pnl_json_path)
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    ds = obj.get("data_source")
    return str(ds) if ds is not None else None


def build_date_signatures(snapshot_dir: str | pathlib.Path, dates: Sequence[str]) -> dict[str, dict[str, Any]]:
    """Build {compact_date: {price_vector_fingerprint, data_source}} from the
    structural positions parquet + operational pnl.json. Read-only."""
    d = pathlib.Path(snapshot_dir)
    out: dict[str, dict[str, Any]] = {}
    for dt in dates:
        out[dt] = {
            "price_vector_fingerprint": build_price_vector_fingerprint(d / f"{dt}_positions.parquet"),
            "data_source": read_data_source(d / f"{dt}_pnl.json"),
        }
    return out


def classify_freshness(dates: Sequence[str], signatures: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Classify each ordered calendar date. The first date is the entry anchor; a
    date whose price vector is unchanged from the prior date is a stale-cache mark;
    the FIRST price change immediately following a stale run is a multi-day catch-up
    mark; subsequent price changes are fresh daily marks."""
    classifications: "dict[str, str]" = {}
    prev_fp: str | None = None
    prev_cls: str | None = None
    for i, dt in enumerate(dates):
        sig = signatures.get(dt, {})
        fp = sig.get("price_vector_fingerprint")
        if fp is None:
            cls = PRICE_FRESHNESS_UNAVAILABLE
        elif i == 0:
            cls = ENTRY_PRICE_ANCHOR
        elif prev_fp is not None and fp == prev_fp:
            cls = STALE_CACHE_NO_PRICE_CHANGE
        else:
            # Price vector changed. A change immediately after a stale run is a
            # multi-day catch-up mark; otherwise a normal fresh daily mark.
            cls = (FRESH_MULTI_DAY_CATCHUP_MARK if prev_cls == STALE_CACHE_NO_PRICE_CHANGE
                   else FRESH_DAILY_MARK)
        classifications[dt] = cls
        prev_fp = fp if fp is not None else prev_fp
        prev_cls = cls

    counts: dict[str, int] = {}
    for c in classifications.values():
        counts[c] = counts.get(c, 0) + 1
    fresh_daily_dates = [d for d in dates if classifications[d] == FRESH_DAILY_MARK]
    stale_dates = [d for d in dates if classifications[d] == STALE_CACHE_NO_PRICE_CHANGE]
    catchup_dates = [d for d in dates if classifications[d] == FRESH_MULTI_DAY_CATCHUP_MARK]
    anchor_dates = [d for d in dates if classifications[d] == ENTRY_PRICE_ANCHOR]
    unavailable = any(c == PRICE_FRESHNESS_UNAVAILABLE for c in classifications.values())
    return {
        "task_id": TASK_ID,
        "classifications": {k: classifications[k] for k in dates},
        "counts": counts,
        "anchor_dates": anchor_dates,
        "stale_dates": stale_dates,
        "catchup_dates": catchup_dates,
        "fresh_daily_dates": fresh_daily_dates,
        "fresh_daily_observation_count": len(fresh_daily_dates),
        "flat_ledger_date_count": len(anchor_dates) + len(stale_dates),
        "price_freshness_unavailable": unavailable,
        "note": "Holding-period scope keeps ALL calendar days; one-day risk scope uses only "
                "FRESH_DAILY_MARK days (anchor, stale and multi-day catch-up are excluded).",
    }


__all__ = [
    "ENTRY_PRICE_ANCHOR", "FRESH_DAILY_MARK", "FRESH_MULTI_DAY_CATCHUP_MARK",
    "INSUFFICIENT_FRESH_DAILY_OBSERVATIONS", "MIN_FRESH_DAILY_OBSERVATIONS",
    "PRICE_FRESHNESS_UNAVAILABLE", "STALE_CACHE_NO_PRICE_CHANGE", "TASK_ID",
    "build_date_signatures", "build_price_vector_fingerprint", "classify_freshness",
    "read_data_source",
]
