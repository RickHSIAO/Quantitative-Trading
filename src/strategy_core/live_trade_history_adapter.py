"""Pure Live trade-history adapter (SR-101D1).

Converts already-loaded Live ledger rows and same-process close events into the
versioned :mod:`src.strategy_core.trade_history` contract objects
(:class:`TradeHistoryRecord` / :class:`TradeHistorySnapshot`).

This module performs NO file, database, environment, credential or network I/O.
It accepts plain Python mappings/sequences and returns immutable contract
objects. It is NOT wired into ``main.py``.

Authoritative-gross rule (schema v1 requires ``pnl_basis=GROSS``)
----------------------------------------------------------------
A record's Kelly-eligible ``gross_pnl`` may be populated ONLY when one of:

  1. the row carries an explicitly named numeric ``gross_pnl`` field; or
  2. the row declares ``pnl_basis == "GROSS"`` AND carries a numeric selected
     ``pnl`` field; or
  3. it is a same-process close event and the adapter itself computes gross from
     the repository-grounded formula ``(exit_price - entry_price) * quantity *
     direction`` (this mirrors ``main.py`` line 2002, the authoritative gross
     same-process close PnL).

Ambiguous legacy / exchange-realized fields (``pnl`` without a GROSS basis,
``closedPnl``, ``realizedPnl``) are NEVER treated as gross. Repository evidence
shows the Live ledger ``pnl`` column mixes gross (same-process closes) with
Bybit exchange-realized ``closedPnl`` (backfill paths, main.py:1503/1543), so a
bare ledger ``pnl`` is genuinely ambiguous: it is retained only via a warning
(not relabeled as net) and the row is not Kelly-eligible.

Repository schema notes
-----------------------
* Live ledger columns (src/live_ledger.py ``EXCEL_COLUMNS``): ``symbol`` (system
  form ``BYBIT:<SYM>.P``), ``bybit_symbol``, ``side``, ``direction``,
  ``quantity``, ``price`` (fill price), ``strategy``, ``reason``, ``pnl``,
  ``fee``, ``order_id``, ``recorded_at`` (timezone-AWARE local ISO via
  ``_now_local``).
* For an EXIT ledger row, ``side`` is the CLOSING side (``_side_for('EXIT',dir)``
  reverses the held direction), so direction is taken from the ``direction``
  column ONLY, never from ``side``.
* Position-side Buy/Sell (from ``get_positions``: Buy->+1, Sell->-1) is honored
  only for same-process close events, where the caller supplies the position
  side directly.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)

from src.strategy_core.trade_history import (
    CompletenessStatus,
    SourceType,
    TradeHistoryRecord,
    TradeHistorySnapshot,
    SCHEMA_VERSION_V1,
)

_SOURCE_RECORD_LEDGER = "LIVE_LEDGER"
_SOURCE_RECORD_CLOSE_EVENT = "LIVE_CLOSE_EVENT"

_LEGACY_AMBIGUOUS_PNL_KEYS = ("pnl", "closedPnl", "realizedPnl")

_RECOGNIZED_LEDGER_KEYS = frozenset({
    "id", "recorded_at", "environment", "action", "symbol", "bybit_symbol",
    "side", "direction", "quantity", "price", "exit_price", "entry_price",
    "stop_loss", "take_profit", "strategy", "strategy_family",
    "strategy_subfamily", "score", "signal_date", "reason", "close_reason",
    "pnl", "gross_pnl", "net_pnl", "pnl_basis", "closedPnl", "realizedPnl",
    "fee", "balance_usdt", "order_id", "order_link_id", "ret_code", "ret_msg",
    "raw_response", "exit_timestamp", "entry_timestamp", "sequence_number",
})

_RECOGNIZED_CLOSE_EVENT_KEYS = frozenset({
    "symbol", "direction", "side", "quantity", "entry_price", "exit_price",
    "exit_timestamp", "entry_timestamp", "order_id", "close_reason", "reason",
    "fee", "strategy_family", "strategy", "strategy_subfamily",
    "sequence_number", "id",
})


class LiveSourceCompleteness(Enum):
    """Caller's trusted attestation about how the input rows were loaded."""
    ATTESTED_COMPLETE = "ATTESTED_COMPLETE"   # source explicitly attests completeness
    LOADED = "LOADED"                         # loaded ok, completeness not attested
    UNKNOWN = "UNKNOWN"                        # completeness cannot be established


class LiveTradeHistoryAdapterError(ValueError):
    """Adapter-level misuse (malformed input container or invalid config)."""


# ─── small pure helpers ───────────────────────────────────────────────────────
def _is_number(value: Any) -> bool:
    """True only for a FINITE numeric value. NaN / Infinity (float, Decimal or
    string form) are rejected so they can never become authoritative gross."""
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return Decimal(str(value)).is_finite()
    if isinstance(value, Decimal):
        return value.is_finite()
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return False
        try:
            return Decimal(s).is_finite()
        except (InvalidOperation, ValueError):
            return False
    return False


def _positive_number(value: Any) -> bool:
    return _is_number(value) and _to_decimal(value) > 0


def _provenance_num(value: Any) -> Any:
    """Pass a numeric provenance field through only when finite; drop non-finite
    (NaN/Infinity) so it never reaches the contract (which rejects non-finite).
    Absence and blank stay absent. Non-numeric strings are left for the contract
    to validate/raise (they indicate genuinely malformed provenance)."""
    if value is None:
        return None
    if isinstance(value, float) and not _is_number(value):
        return None
    if isinstance(value, Decimal) and not value.is_finite():
        return None
    return value


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, float):
        d = Decimal(str(value))
    elif isinstance(value, str):
        d = Decimal(value.strip())
    else:
        raise LiveTradeHistoryAdapterError(f"not a numeric value: {value!r}")
    if not d.is_finite():
        raise LiveTradeHistoryAdapterError(f"non-finite value: {value!r}")
    return d


def _coerce_timestamp(value: Any) -> tuple[Optional[datetime], bool]:
    """Return (aware-UTC datetime or None, ok). ok is False only for an
    invalid/ambiguous value (naive string/datetime, bare int of unknown epoch
    unit, unparseable string). Absence (None/"") returns (None, True)."""
    if value is None:
        return None, True
    if isinstance(value, bool):
        return None, False
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return None, False
        return value.astimezone(timezone.utc), True
    if isinstance(value, Mapping):
        if "epoch_ms" in value and _is_number(value["epoch_ms"]):
            # 1 ms == 1000 microseconds: preserve sub-second (microsecond) precision.
            return _micros_to_utc(_to_decimal(value["epoch_ms"]) * 1000), True
        if "epoch_s" in value and _is_number(value["epoch_s"]):
            return _micros_to_utc(_to_decimal(value["epoch_s"]) * 1_000_000), True
        return None, False
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return None, True
        iso = s[:-1] + "+00:00" if s.endswith("Z") else s
        try:
            dt = datetime.fromisoformat(iso)
        except ValueError:
            return None, False
        if dt.tzinfo is None or dt.utcoffset() is None:
            return None, False
        return dt.astimezone(timezone.utc), True
    # bare int/float: ambiguous epoch unit -> refuse to guess
    return None, False


def _micros_to_utc(micros: Decimal) -> datetime:
    """Aware UTC datetime from an exact microseconds-since-epoch Decimal.
    Sub-microsecond fractions are rounded deterministically (ROUND_HALF_EVEN)."""
    micros_int = int(micros.to_integral_value(rounding=ROUND_HALF_EVEN))
    return _EPOCH_UTC + timedelta(microseconds=micros_int)


def _direction_from_field(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int) and value in (1, -1):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s in ("1", "+1"):
            return 1
        if s == "-1":
            return -1
    return None


def _position_side_to_direction(value: Any) -> Optional[int]:
    if isinstance(value, str):
        s = value.strip()
        if s == "Buy":
            return 1
        if s == "Sell":
            return -1
    return None


def _ref(symbol: Any, order_id: Any) -> str:
    return f"symbol={str(symbol)!r} order_id={str(order_id or '')!r}"


def _require_family(strategy_family: Any) -> str:
    fam = str(strategy_family or "").strip()
    if fam == "":
        raise LiveTradeHistoryAdapterError("strategy_family must be non-empty")
    return fam


def _bind_family(row: Mapping[str, Any], snapshot_family: str, ref: str) -> str:
    """Every produced record must belong to the snapshot family. A missing row
    family inherits it; a matching one is accepted; a different non-empty one
    fails closed."""
    raw = row.get("strategy_family")
    if raw is None:
        raw = row.get("strategy")
    if raw is None or str(raw).strip() == "":
        return snapshot_family
    rs = str(raw).strip()
    if rs != snapshot_family:
        raise LiveTradeHistoryAdapterError(
            f"row strategy_family {rs!r} conflicts with snapshot strategy_family "
            f"{snapshot_family!r} ({ref})")
    return snapshot_family


# ─── internal per-row preparation ─────────────────────────────────────────────
class _Prepared:
    __slots__ = ("record", "kelly_expected", "problem", "sort_key", "_explicit_seq")

    def __init__(self, record, kelly_expected, problem, sort_key):
        self.record = record            # TradeHistoryRecord
        self.kelly_expected = kelly_expected  # bool: this row was meant to be authoritative
        self.problem = problem          # bool: expected-authoritative but unusable
        self.sort_key = sort_key
        self._explicit_seq = False      # set by the preparers


def _finalize(prepared_list, *, strategy_family, strategy_spec_version,
              source_reference, generated_at, snapshot_cutoff_timestamp,
              source_completeness, warnings, had_input_problems):
    # Deterministic sequence assignment (never input-position based).
    # If every record carries an explicit repository-grounded sequence/id we keep
    # it; otherwise derive from a canonical content sort so that input order
    # cannot influence the outcome.
    if not _all_have_explicit_sequence(prepared_list):
        # Rank by UNIQUE content sort-key so that two fully identical rows receive
        # the SAME sequence_number (and thus remain identical for the contract's
        # deterministic dedup), while distinct rows get distinct, content-derived,
        # input-order-independent sequence numbers.
        rank_of = {key: rank for rank, key in
                   enumerate(sorted({p.sort_key for p in prepared_list}))}
        for p in prepared_list:
            p.record = _with_sequence(p.record, rank_of[p.sort_key])

    status = _resolve_completeness(
        source_completeness=source_completeness,
        record_count=len(prepared_list),
        had_problems=had_input_problems or any(p.problem for p in prepared_list),
    )

    gen_dt = _require_config_timestamp(generated_at, "generated_at")
    cutoff_dt = _require_config_timestamp(snapshot_cutoff_timestamp,
                                          "snapshot_cutoff_timestamp")

    return TradeHistorySnapshot(
        schema_version=SCHEMA_VERSION_V1,
        strategy_family=strategy_family,
        strategy_spec_version=strategy_spec_version,
        pnl_basis="GROSS",
        source_type=SourceType.LIVE,
        source_reference=source_reference,
        generated_at=gen_dt,
        snapshot_cutoff_timestamp=cutoff_dt,
        completeness_status=status,
        records=[p.record for p in prepared_list],
        warnings=sorted(warnings),
    )


def _all_have_explicit_sequence(prepared_list) -> bool:
    return len(prepared_list) > 0 and all(
        getattr(p, "_explicit_seq", False) for p in prepared_list)


def _with_sequence(rec: TradeHistoryRecord, seq: int) -> TradeHistoryRecord:
    d = rec.to_dict()
    d["sequence_number"] = seq
    return TradeHistoryRecord.from_dict(d)


def _require_config_timestamp(value, field):
    dt, ok = _coerce_timestamp(value)
    if not ok:
        raise LiveTradeHistoryAdapterError(
            f"{field} must be timezone-aware / unambiguous, got {value!r}")
    return dt


def _resolve_completeness(*, source_completeness, record_count, had_problems):
    if source_completeness is LiveSourceCompleteness.UNKNOWN:
        return CompletenessStatus.UNKNOWN
    if source_completeness is LiveSourceCompleteness.LOADED:
        return CompletenessStatus.PARTIAL
    if source_completeness is LiveSourceCompleteness.ATTESTED_COMPLETE:
        return (CompletenessStatus.PARTIAL if had_problems
                else CompletenessStatus.COMPLETE)
    raise LiveTradeHistoryAdapterError(
        f"unknown source_completeness: {source_completeness!r}")


def _coerce_source_completeness(value) -> LiveSourceCompleteness:
    if isinstance(value, LiveSourceCompleteness):
        return value
    if isinstance(value, str):
        try:
            return LiveSourceCompleteness(value)
        except ValueError:
            try:
                return LiveSourceCompleteness[value]
            except KeyError:
                pass
    raise LiveTradeHistoryAdapterError(
        f"invalid source_completeness: {value!r}; expected one of "
        f"{[m.value for m in LiveSourceCompleteness]}")


# ─── public API: persisted ledger rows ────────────────────────────────────────
def adapt_live_history_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    strategy_family: str,
    strategy_spec_version: str,
    source_reference: str,
    source_completeness: Any,
    generated_at: Any = None,
    snapshot_cutoff_timestamp: Any = None,
) -> TradeHistorySnapshot:
    """Adapt already-loaded Live LEDGER rows into a GROSS-basis LIVE snapshot.

    A ledger row becomes Kelly-eligible only if it declares authoritative gross
    (explicit ``gross_pnl`` field, or ``pnl_basis == "GROSS"`` + numeric
    ``pnl``). Bare ``pnl``/``closedPnl``/``realizedPnl`` are ambiguous provenance
    and never become gross.
    """
    completeness = _coerce_source_completeness(source_completeness)
    family = _require_family(strategy_family)
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, Mapping)):
        raise LiveTradeHistoryAdapterError("rows must be a sequence of mappings")

    warnings: list[str] = []
    prepared: list[_Prepared] = []
    had_problems = False

    for idx, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise LiveTradeHistoryAdapterError(
                f"rows[{idx}] must be a mapping, got {type(row).__name__}")
        p, w, problem = _prepare_ledger_row(row, family)
        warnings.extend(w)
        had_problems = had_problems or problem
        if p is not None:                       # non-EXIT rows produce no record
            prepared.append(p)

    for u in _unknown_key_warnings(rows, _RECOGNIZED_LEDGER_KEYS):
        warnings.append(u)

    return _finalize(
        prepared,
        strategy_family=family,
        strategy_spec_version=strategy_spec_version,
        source_reference=source_reference,
        generated_at=generated_at,
        snapshot_cutoff_timestamp=snapshot_cutoff_timestamp,
        source_completeness=completeness,
        warnings=warnings,
        had_input_problems=had_problems,
    )


def _prepare_ledger_row(row: Mapping[str, Any], snapshot_family: str
                        ) -> tuple[Optional[_Prepared], list[str], bool]:
    warnings: list[str] = []
    symbol = row.get("symbol")
    if symbol is None or str(symbol).strip() == "":
        raise LiveTradeHistoryAdapterError("ledger row missing required 'symbol'")
    order_id = row.get("order_id") or ""
    ref = _ref(symbol, order_id)

    # Persisted history is CLOSED trades: only action == "EXIT" is a closed trade.
    action = str(row.get("action") or "").strip().upper()
    if action != "EXIT":
        if action == "ENTRY":
            warnings.append(f"{ref}: skipped non-closed ledger action 'ENTRY'")
            return None, warnings, False
        # missing / blank / unrecognized action: do not guess; conservatively a
        # completeness problem so an ATTESTED_COMPLETE source is downgraded.
        warnings.append(
            f"{ref}: skipped ledger row with missing/unrecognized action "
            f"{action!r}; not a closed trade")
        return None, warnings, True

    family = _bind_family(row, snapshot_family, ref)

    direction = _direction_from_field(row.get("direction"))
    if row.get("direction") is not None and direction is None:
        warnings.append(f"{ref}: invalid direction {row.get('direction')!r}; not mapped")

    gross, gross_state = _resolve_gross_from_row(row, ref, warnings)
    kelly_expected = gross is not None
    problem = (gross_state == "ambiguous")

    exit_ts_dt, exit_ok = _coerce_timestamp(
        row.get("exit_timestamp", row.get("recorded_at")))
    if not exit_ok:
        warnings.append(f"{ref}: invalid/ambiguous exit timestamp; left unset")
    # An authoritative-gross row with no usable exit timestamp cannot be Kelly-
    # eligible; that is a completeness problem.
    if gross is not None and exit_ts_dt is None:
        warnings.append(f"{ref}: authoritative gross present but no usable "
                        f"exit_timestamp; not Kelly-eligible")
        problem = True

    entry_ts_dt, entry_ok = _coerce_timestamp(row.get("entry_timestamp"))
    if not entry_ok:
        warnings.append(f"{ref}: invalid/ambiguous entry timestamp; left unset")

    exit_price = row.get("exit_price", row.get("price"))
    explicit_seq = _explicit_sequence(row)

    record = TradeHistoryRecord(
        symbol=symbol,
        strategy_family=family,
        strategy_subfamily=row.get("strategy_subfamily") or "",
        entry_timestamp=entry_ts_dt,
        exit_timestamp=exit_ts_dt,
        direction=direction,
        quantity=_provenance_num(row.get("quantity")),
        entry_price=_provenance_num(row.get("entry_price")),
        exit_price=_provenance_num(exit_price),
        gross_pnl=gross,
        fee=_provenance_num(row.get("fee")),
        net_pnl=None,
        close_reason=row.get("close_reason") or row.get("reason") or "",
        order_id=str(order_id),
        source=_SOURCE_RECORD_LEDGER,
        sequence_number=explicit_seq if explicit_seq is not None else 0,
    )
    prepared = _Prepared(record, kelly_expected, problem, _sort_key_for(record, gross))
    prepared._explicit_seq = explicit_seq is not None
    return prepared, warnings, problem


def _resolve_gross_from_row(row, ref, warnings) -> tuple[Optional[Decimal], Optional[str]]:
    # (1) explicit gross_pnl field. If the key is DECLARED it must be finite
    # numeric; an invalid declaration is a problem, not a silent fall-through.
    if "gross_pnl" in row:
        if _is_number(row["gross_pnl"]):
            return _to_decimal(row["gross_pnl"]), "explicit_gross"
        warnings.append(
            f"{ref}: explicit gross_pnl is invalid/non-finite "
            f"{row['gross_pnl']!r}; not Kelly-eligible")
        return None, "ambiguous"
    # (2) explicit GROSS basis + numeric selected pnl
    basis = row.get("pnl_basis")
    if isinstance(basis, str) and basis.strip().upper() == "GROSS":
        if _is_number(row.get("pnl")):
            return _to_decimal(row["pnl"]), "declared_gross"
        warnings.append(f"{ref}: pnl_basis=GROSS declared but no numeric 'pnl'; "
                        f"not Kelly-eligible")
        return None, "ambiguous"
    # (B) ambiguous legacy / exchange-realized fields -> provenance only
    present = [k for k in _LEGACY_AMBIGUOUS_PNL_KEYS
               if k in row and _is_number(row[k])]
    if present:
        warnings.append(
            f"{ref}: ambiguous legacy PnL field(s) {present} retained as "
            f"provenance only; not treated as gross, not Kelly-eligible")
        return None, "ambiguous"
    return None, None


# ─── public API: same-process close events ────────────────────────────────────
def adapt_same_process_close_events(
    events: Sequence[Mapping[str, Any]],
    *,
    strategy_family: str,
    strategy_spec_version: str,
    source_reference: str,
    source_completeness: Any,
    generated_at: Any = None,
    snapshot_cutoff_timestamp: Any = None,
) -> TradeHistorySnapshot:
    """Adapt same-process CLOSE EVENTS into a GROSS-basis LIVE snapshot.

    Gross PnL is computed by the adapter as
    ``(exit_price - entry_price) * quantity * direction`` (the authoritative
    same-process gross formula, main.py:2002). A record is Kelly-eligible only
    when entry_price, exit_price, quantity, direction and a usable aware
    exit_timestamp are all present and valid.
    """
    completeness = _coerce_source_completeness(source_completeness)
    family = _require_family(strategy_family)
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes, Mapping)):
        raise LiveTradeHistoryAdapterError("events must be a sequence of mappings")

    warnings: list[str] = []
    prepared: list[_Prepared] = []
    had_problems = False

    for idx, ev in enumerate(events):
        if not isinstance(ev, Mapping):
            raise LiveTradeHistoryAdapterError(
                f"events[{idx}] must be a mapping, got {type(ev).__name__}")
        p, w, problem = _prepare_close_event(ev, family)
        warnings.extend(w)
        had_problems = had_problems or problem
        prepared.append(p)

    for u in _unknown_key_warnings(events, _RECOGNIZED_CLOSE_EVENT_KEYS):
        warnings.append(u)

    return _finalize(
        prepared,
        strategy_family=family,
        strategy_spec_version=strategy_spec_version,
        source_reference=source_reference,
        generated_at=generated_at,
        snapshot_cutoff_timestamp=snapshot_cutoff_timestamp,
        source_completeness=completeness,
        warnings=warnings,
        had_input_problems=had_problems,
    )


def _prepare_close_event(ev: Mapping[str, Any], snapshot_family: str
                         ) -> tuple[_Prepared, list[str], bool]:
    warnings: list[str] = []
    symbol = ev.get("symbol")
    if symbol is None or str(symbol).strip() == "":
        raise LiveTradeHistoryAdapterError("close event missing required 'symbol'")
    order_id = ev.get("order_id") or ""
    ref = _ref(symbol, order_id)

    family = _bind_family(ev, snapshot_family, ref)

    direction = _direction_from_field(ev.get("direction"))
    if direction is None and "side" in ev:
        direction = _position_side_to_direction(ev.get("side"))
    if direction is None:
        warnings.append(f"{ref}: missing/invalid direction; gross not computed")

    # Authoritative gross requires strictly-positive finite quantity and prices.
    have_prices = _positive_number(ev.get("entry_price")) and _positive_number(ev.get("exit_price"))
    have_qty = _positive_number(ev.get("quantity"))

    gross: Optional[Decimal] = None
    problem = False
    if direction is not None and have_prices and have_qty:
        gross = ((_to_decimal(ev["exit_price"]) - _to_decimal(ev["entry_price"]))
                 * _to_decimal(ev["quantity"]) * Decimal(direction))
    else:
        warnings.append(f"{ref}: invalid close arithmetic inputs "
                        f"(need direction +/-1, quantity>0, entry_price>0, "
                        f"exit_price>0, all finite); gross not computed, "
                        f"not Kelly-eligible")
        problem = True

    exit_ts_dt, exit_ok = _coerce_timestamp(ev.get("exit_timestamp"))
    if not exit_ok:
        warnings.append(f"{ref}: invalid/ambiguous exit timestamp; left unset")
    if gross is not None and exit_ts_dt is None:
        warnings.append(f"{ref}: computed gross present but no usable "
                        f"exit_timestamp; not Kelly-eligible")
        problem = True

    entry_ts_dt, entry_ok = _coerce_timestamp(ev.get("entry_timestamp"))
    if not entry_ok:
        warnings.append(f"{ref}: invalid/ambiguous entry timestamp; left unset")

    explicit_seq = _explicit_sequence(ev)
    record = TradeHistoryRecord(
        symbol=symbol,
        strategy_family=family,
        strategy_subfamily=ev.get("strategy_subfamily") or "",
        entry_timestamp=entry_ts_dt,
        exit_timestamp=exit_ts_dt,
        direction=direction,
        quantity=_provenance_num(ev.get("quantity")),
        entry_price=_provenance_num(ev.get("entry_price")),
        exit_price=_provenance_num(ev.get("exit_price")),
        gross_pnl=gross,
        fee=_provenance_num(ev.get("fee")),
        net_pnl=None,
        close_reason=ev.get("close_reason") or ev.get("reason") or "",
        order_id=str(order_id),
        source=_SOURCE_RECORD_CLOSE_EVENT,
        sequence_number=explicit_seq if explicit_seq is not None else 0,
    )
    prepared = _Prepared(record, gross is not None, problem,
                         _sort_key_for(record, gross))
    prepared._explicit_seq = explicit_seq is not None
    return prepared, warnings, problem


# ─── sequence / ordering helpers ──────────────────────────────────────────────
def _explicit_sequence(row: Mapping[str, Any]) -> Optional[int]:
    for key in ("sequence_number", "id"):
        if key in row:
            v = row[key]
            if isinstance(v, bool):
                continue
            if isinstance(v, int) and v >= 0:
                return v
    return None


def _sort_key_for(record: TradeHistoryRecord, gross: Optional[Decimal]) -> tuple:
    return (
        record.exit_timestamp or "",
        record.order_id or "",
        record.symbol or "",
        "" if gross is None else format(gross, "f"),
        "" if record.quantity is None else format(record.quantity, "f"),
        "" if record.exit_price is None else format(record.exit_price, "f"),
    )


def _unknown_key_warnings(rows, recognized) -> list[str]:
    unknown: set[str] = set()
    for row in rows:
        if isinstance(row, Mapping):
            unknown |= {str(k) for k in row.keys() if str(k) not in recognized}
    return [f"ignored unrecognized input field {k!r}" for k in sorted(unknown)]
