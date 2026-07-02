"""Pure, versioned TradeHistory contract for the shared strategy engine.

This module is intentionally free of filesystem, network, credential and
wall-clock I/O. It defines immutable data structures, validation,
canonicalization and three deterministic SHA-256 fingerprints that future
Live / Backtest / Forward / Paper / Demo adapters can all supply identically.

SR-101A / SR-101B established that ``estimate_kelly_from_history`` consumes only
a bare ``.pnl`` numeric per record and is gross/net basis-agnostic. This contract
makes the basis EXPLICIT: schema version 1 declares ``pnl_basis = "GROSS"`` as
the authoritative Kelly input, preserving the current same-process live-close
sizing behavior. Changing v1 from GROSS to NET later must cross a
``strategy_spec_version`` boundary and cannot happen silently: a v1 snapshot that
declares NET is rejected (see :class:`UnsupportedPnlBasisError`).

This module does NOT reimplement any Kelly mathematics; it only selects and
fingerprints the input list that the existing Kelly function will later consume.

Fingerprint responsibilities (see section H of the contract):
  * ``kelly_input_fingerprint``     -> Kelly parity identity (basis + selected
                                       gross PnL sequence + record identity only)
  * ``history_data_fingerprint``    -> full canonical record data identity
                                       (includes fee / net_pnl / provenance)
  * ``provenance_fingerprint``      -> artifact provenance (source, generated_at,
                                       cutoff, completeness, warnings)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Sequence


SCHEMA_VERSION_V1 = 1

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


# ─── Enums ────────────────────────────────────────────────────────────────────
class PnlBasis(Enum):
    GROSS = "GROSS"
    NET = "NET"


class CompletenessStatus(Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class SourceType(Enum):
    BACKTEST = "BACKTEST"
    FORWARD = "FORWARD"
    PAPER = "PAPER"
    DEMO_DRY_RUN = "DEMO_DRY_RUN"
    DEMO_EXECUTION = "DEMO_EXECUTION"
    LIVE = "LIVE"
    EMPTY_PILOT = "EMPTY_PILOT"
    FIXTURE = "FIXTURE"


# ─── Exceptions ───────────────────────────────────────────────────────────────
class TradeHistoryValidationError(ValueError):
    """A snapshot or record failed contract validation."""


class ConflictingDuplicateError(TradeHistoryValidationError):
    """Two records share a duplicate key but disagree on Kelly-relevant data."""


class UnsupportedPnlBasisError(TradeHistoryValidationError):
    """The declared pnl_basis is not permitted for the schema version."""


# ─── Scalar canonicalization helpers ─────────────────────────────────────────
def _canonical_decimal(value: Any, *, field: str, symbol: str = "") -> Optional[Decimal]:
    """Return a finite Decimal (or None). Rejects bool and non-finite values.

    Floats are routed through ``str`` so no binary-float artifact ever reaches
    canonical output.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise TradeHistoryValidationError(
            f"{field} must be numeric, not bool (symbol={symbol!r})")
    try:
        if isinstance(value, Decimal):
            d = value
        elif isinstance(value, int):
            d = Decimal(value)
        elif isinstance(value, float):
            d = Decimal(str(value))
        elif isinstance(value, str):
            s = value.strip()
            if s == "":
                return None
            d = Decimal(s)
        else:
            raise TradeHistoryValidationError(
                f"{field} has unsupported type {type(value).__name__} "
                f"(symbol={symbol!r})")
    except (InvalidOperation, ValueError) as exc:
        raise TradeHistoryValidationError(
            f"{field} is not a valid decimal: {value!r} (symbol={symbol!r})"
        ) from exc
    if not d.is_finite():
        raise TradeHistoryValidationError(
            f"{field} must be finite: {value!r} (symbol={symbol!r})")
    return d


def _decimal_str(d: Optional[Decimal]) -> Optional[str]:
    """Canonical decimal string with no scientific notation (stable round-trip)."""
    if d is None:
        return None
    return format(d, "f")


def _canonical_timestamp(value: Any, *, field: str) -> Optional[str]:
    """Normalize a timestamp to a canonical UTC ISO-8601 string.

    Strict timestamp policy (SR-101C-R1 section D): every non-None timestamp
    MUST be timezone-aware. Naive datetimes and naive ISO strings are rejected
    with :class:`TradeHistoryValidationError`; aware timestamps are converted to
    UTC so that equivalent instants (e.g. ``...Z``, ``...+00:00`` and a non-UTC
    offset of the same instant) collapse to one canonical representation.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        s = value.strip()
        if s == "":
            return None
        iso = s[:-1] + "+00:00" if s.endswith("Z") else s
        try:
            dt = datetime.fromisoformat(iso)
        except ValueError as exc:
            raise TradeHistoryValidationError(
                f"{field} is not a valid ISO-8601 timestamp: {value!r}") from exc
    else:
        raise TradeHistoryValidationError(
            f"{field} has unsupported type {type(value).__name__}")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise TradeHistoryValidationError(
            f"{field} must be timezone-aware; naive timestamps are rejected "
            f"(got {value!r})")
    return dt.astimezone(timezone.utc).isoformat()


def _epoch_seconds(canonical_ts: str) -> float:
    """Comparable epoch seconds for a canonical timestamp string.

    Naive timestamps are treated as UTC for ordering purposes only.
    """
    dt = datetime.fromisoformat(canonical_ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt - _EPOCH).total_seconds()


def _normalize_symbol(value: Any) -> str:
    """Normalize to canonical system form ``BYBIT:<SYMBOL>.P`` when possible.

    * already system form (contains ':') -> upper-cased, idempotent
    * bare alphanumeric exchange token   -> wrapped as ``BYBIT:<TOKEN>.P``
    * anything else                      -> upper-cased as-is (best effort)
    """
    if not isinstance(value, str):
        raise TradeHistoryValidationError(
            f"symbol must be a string, got {type(value).__name__}")
    s = value.strip().upper()
    if s == "":
        raise TradeHistoryValidationError("symbol must be non-empty")
    if ":" in s:
        return s
    if s.isalnum():
        return f"BYBIT:{s}.P"
    return s


# ─── TradeHistoryRecord ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class TradeHistoryRecord:
    """Immutable single closed-trade record. Values are canonicalized on
    construction (symbol normalized, decimals -> Decimal, timestamps -> ISO)."""

    symbol: str
    strategy_family: str
    strategy_subfamily: str = ""
    entry_timestamp: Optional[str] = None
    exit_timestamp: Optional[str] = None
    direction: Optional[int] = None
    quantity: Optional[Decimal] = None
    entry_price: Optional[Decimal] = None
    exit_price: Optional[Decimal] = None
    gross_pnl: Optional[Decimal] = None
    fee: Optional[Decimal] = None
    net_pnl: Optional[Decimal] = None
    close_reason: str = ""
    order_id: str = ""
    source: str = ""
    sequence_number: int = 0

    def __post_init__(self) -> None:
        set_ = object.__setattr__
        sym = _normalize_symbol(self.symbol)
        set_(self, "symbol", sym)
        set_(self, "strategy_family", str(self.strategy_family))
        set_(self, "strategy_subfamily", str(self.strategy_subfamily or ""))
        set_(self, "entry_timestamp",
             _canonical_timestamp(self.entry_timestamp, field="entry_timestamp"))
        set_(self, "exit_timestamp",
             _canonical_timestamp(self.exit_timestamp, field="exit_timestamp"))

        if self.direction is not None:
            if isinstance(self.direction, bool) or self.direction not in (-1, 1):
                raise TradeHistoryValidationError(
                    f"direction must be -1 or +1 when present, got "
                    f"{self.direction!r} (symbol={sym!r})")

        set_(self, "quantity",
             _canonical_decimal(self.quantity, field="quantity", symbol=sym))
        set_(self, "entry_price",
             _canonical_decimal(self.entry_price, field="entry_price", symbol=sym))
        set_(self, "exit_price",
             _canonical_decimal(self.exit_price, field="exit_price", symbol=sym))
        set_(self, "gross_pnl",
             _canonical_decimal(self.gross_pnl, field="gross_pnl", symbol=sym))
        set_(self, "fee",
             _canonical_decimal(self.fee, field="fee", symbol=sym))
        set_(self, "net_pnl",
             _canonical_decimal(self.net_pnl, field="net_pnl", symbol=sym))

        set_(self, "close_reason", str(self.close_reason or ""))
        set_(self, "order_id", str(self.order_id or ""))
        set_(self, "source", str(self.source or ""))

        if isinstance(self.sequence_number, bool) or not isinstance(self.sequence_number, int):
            raise TradeHistoryValidationError(
                f"sequence_number must be a non-negative integer, got "
                f"{self.sequence_number!r} (symbol={sym!r})")
        if self.sequence_number < 0:
            raise TradeHistoryValidationError(
                f"sequence_number must be non-negative, got "
                f"{self.sequence_number} (symbol={sym!r})")

    # -- intrinsic Kelly eligibility (cutoff/dedup are applied at snapshot level) --
    @property
    def kelly_eligible(self) -> bool:
        return bool(self.symbol) and self.exit_timestamp is not None and self.gross_pnl is not None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "strategy_family": self.strategy_family,
            "strategy_subfamily": self.strategy_subfamily,
            "entry_timestamp": self.entry_timestamp,
            "exit_timestamp": self.exit_timestamp,
            "direction": self.direction,
            "quantity": _decimal_str(self.quantity),
            "entry_price": _decimal_str(self.entry_price),
            "exit_price": _decimal_str(self.exit_price),
            "gross_pnl": _decimal_str(self.gross_pnl),
            "fee": _decimal_str(self.fee),
            "net_pnl": _decimal_str(self.net_pnl),
            "close_reason": self.close_reason,
            "order_id": self.order_id,
            "source": self.source,
            "sequence_number": self.sequence_number,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TradeHistoryRecord":
        return cls(
            symbol=data["symbol"],
            strategy_family=data.get("strategy_family", ""),
            strategy_subfamily=data.get("strategy_subfamily", ""),
            entry_timestamp=data.get("entry_timestamp"),
            exit_timestamp=data.get("exit_timestamp"),
            direction=data.get("direction"),
            quantity=data.get("quantity"),
            entry_price=data.get("entry_price"),
            exit_price=data.get("exit_price"),
            gross_pnl=data.get("gross_pnl"),
            fee=data.get("fee"),
            net_pnl=data.get("net_pnl"),
            close_reason=data.get("close_reason", ""),
            order_id=data.get("order_id", ""),
            source=data.get("source", ""),
            sequence_number=data.get("sequence_number", 0),
        )


# ─── Duplicate / ordering keys ───────────────────────────────────────────────
def _dup_key(r: TradeHistoryRecord) -> tuple:
    oid = r.order_id.strip()
    if oid:
        return ("oid", oid)
    return ("nat", r.symbol, r.exit_timestamp or "",
            _decimal_str(r.quantity), _decimal_str(r.exit_price))


def _record_identity(r: TradeHistoryRecord) -> dict:
    """Deterministic logical-trade identity used inside kelly_input_fingerprint,
    so two logically distinct repeated trades never collapse to the same Kelly
    identity. Uses order_id when present, otherwise the natural key."""
    oid = r.order_id.strip()
    if oid:
        return {"identity_type": "order_id", "symbol": r.symbol, "order_id": oid}
    return {
        "identity_type": "natural",
        "symbol": r.symbol,
        "exit_timestamp": r.exit_timestamp,
        "quantity": _decimal_str(r.quantity),
        "exit_price": _decimal_str(r.exit_price),
    }


def _sort_key(r: TradeHistoryRecord) -> tuple:
    if r.exit_timestamp is not None:
        primary = (0, _epoch_seconds(r.exit_timestamp))
    else:
        primary = (1, 0.0)
    return (primary[0], primary[1], r.sequence_number, r.order_id, r.symbol)


# ─── Canonical JSON / fingerprint helpers ────────────────────────────────────
def _canonical_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def _fingerprint(payload: Any) -> str:
    body = _canonical_dumps(payload)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


# ─── TradeHistorySnapshot ────────────────────────────────────────────────────
class TradeHistorySnapshot:
    """Immutable, versioned collection of TradeHistoryRecords.

    Construction validates the schema/basis, canonicalizes records (sort ->
    deduplicate -> cutoff-filter) and exposes derived counts, the selected Kelly
    PnL list and three fingerprints. Original inputs are never mutated.
    """

    def __init__(
        self,
        *,
        schema_version: int,
        strategy_family: str,
        strategy_spec_version: str,
        pnl_basis: Any,
        source_type: Any,
        source_reference: str = "",
        generated_at: Any = None,
        snapshot_cutoff_timestamp: Any = None,
        completeness_status: Any,
        records: Iterable[TradeHistoryRecord] = (),
        warnings: Sequence[str] = (),
    ) -> None:
        # Immutability latch: attribute writes are permitted only while this is
        # False (i.e. during construction); __setattr__ locks afterwards.
        object.__setattr__(self, "_initialized", False)
        if schema_version != SCHEMA_VERSION_V1:
            raise TradeHistoryValidationError(
                f"unsupported schema_version {schema_version!r}; "
                f"this module implements v{SCHEMA_VERSION_V1}")
        self._schema_version = SCHEMA_VERSION_V1
        self._strategy_family = str(strategy_family)
        self._strategy_spec_version = str(strategy_spec_version)

        basis = _coerce_enum(PnlBasis, pnl_basis, "pnl_basis")
        # V1 authoritative-basis boundary: only GROSS may validate under v1.
        if basis is not PnlBasis.GROSS:
            raise UnsupportedPnlBasisError(
                f"schema v{SCHEMA_VERSION_V1} requires pnl_basis=GROSS "
                f"(the authoritative v1 Kelly basis); got {basis.value}. "
                f"Switching to NET requires a strategy_spec_version boundary.")
        self._pnl_basis = basis

        self._source_type = _coerce_enum(SourceType, source_type, "source_type")
        self._source_reference = str(source_reference or "")
        self._generated_at = _canonical_timestamp(generated_at, field="generated_at")
        self._cutoff = _canonical_timestamp(
            snapshot_cutoff_timestamp, field="snapshot_cutoff_timestamp")
        self._completeness_status = _coerce_enum(
            CompletenessStatus, completeness_status, "completeness_status")

        recs = tuple(records)
        for i, r in enumerate(recs):
            if not isinstance(r, TradeHistoryRecord):
                raise TradeHistoryValidationError(
                    f"records[{i}] must be a TradeHistoryRecord, got "
                    f"{type(r).__name__}")
        self._records = recs
        self._input_warnings = tuple(str(w) for w in warnings)

        canonical, derived = self._canonicalize(recs)
        self._canonical_records = canonical
        self._derived_warnings = tuple(derived)

        object.__setattr__(self, "_initialized", True)

    # -- immutability guard (SR-101C-R1 section A) --
    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_initialized", False):
            raise AttributeError(
                f"TradeHistorySnapshot is immutable; cannot set {name!r}")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        raise AttributeError(
            f"TradeHistorySnapshot is immutable; cannot delete {name!r}")

    # -- canonicalization: sort -> dedup (fail-closed) -> cutoff filter --
    def _canonicalize(self, recs) -> tuple:
        derived: list[str] = []
        ordered = sorted(recs, key=_sort_key)

        seen: dict = {}
        deduped: list = []
        for r in ordered:
            key = _dup_key(r)
            if key in seen:
                kept = seen[key]
                if r == kept:
                    # Fully identical canonical record: deterministic dedup.
                    derived.append(f"deduplicated identical record key={key!r}")
                    continue
                # Any canonical-field difference under a shared duplicate key is
                # fail-closed: keeping first/last would make output input-order
                # dependent (SR-101C-R1 section B).
                kd, rd = kept.to_dict(), r.to_dict()
                diffs = sorted(k for k in rd if rd[k] != kd.get(k))
                raise ConflictingDuplicateError(
                    f"conflicting duplicate for key={key!r} symbol={r.symbol!r}: "
                    f"records share a duplicate key but differ in fields {diffs}")
            seen[key] = r
            deduped.append(r)

        canonical: list = []
        for r in deduped:
            if (self._cutoff is not None and r.exit_timestamp is not None
                    and _epoch_seconds(r.exit_timestamp) > _epoch_seconds(self._cutoff)):
                derived.append(
                    f"excluded post-cutoff record symbol={r.symbol!r} "
                    f"exit_timestamp={r.exit_timestamp!r} > cutoff={self._cutoff!r}")
                continue
            canonical.append(r)

        return tuple(canonical), derived

    # -- scalar accessors --
    @property
    def schema_version(self) -> int:
        return self._schema_version

    @property
    def strategy_family(self) -> str:
        return self._strategy_family

    @property
    def strategy_spec_version(self) -> str:
        return self._strategy_spec_version

    @property
    def pnl_basis(self) -> PnlBasis:
        return self._pnl_basis

    @property
    def source_type(self) -> SourceType:
        return self._source_type

    @property
    def source_reference(self) -> str:
        return self._source_reference

    @property
    def generated_at(self) -> Optional[str]:
        return self._generated_at

    @property
    def snapshot_cutoff_timestamp(self) -> Optional[str]:
        return self._cutoff

    @property
    def completeness_status(self) -> CompletenessStatus:
        return self._completeness_status

    @property
    def records(self) -> tuple:
        """The original input records (unsorted, unfiltered), never mutated."""
        return self._records

    @property
    def warnings(self) -> tuple:
        """Caller-supplied warnings followed by deterministic derived notes
        (deduplication / cutoff exclusions)."""
        return self._input_warnings + self._derived_warnings

    # -- derived --
    @property
    def canonical_records(self) -> tuple:
        """Sorted, deduplicated, cutoff-filtered records (authoritative set)."""
        return self._canonical_records

    @property
    def record_count(self) -> int:
        return len(self._canonical_records)

    @property
    def kelly_eligible_records(self) -> tuple:
        return tuple(r for r in self._canonical_records if r.kelly_eligible)

    @property
    def kelly_eligible_count(self) -> int:
        return len(self.kelly_eligible_records)

    @property
    def selected_kelly_pnls(self) -> tuple:
        """v1: the selected gross PnL Decimals (zero retained; None excluded).

        This is the exact list a future adapter feeds to the existing
        ``estimate_kelly_from_history`` (as ``.pnl`` values). No Kelly math here.
        """
        return tuple(r.gross_pnl for r in self.kelly_eligible_records)

    # -- fingerprints --
    def _kelly_input_payload(self) -> dict:
        return {
            "schema_version": self._schema_version,
            "strategy_family": self._strategy_family,
            "strategy_spec_version": self._strategy_spec_version,
            "pnl_basis": self._pnl_basis.value,
            "records": [
                {
                    "record_identity": _record_identity(r),
                    "sequence_number": r.sequence_number,
                    "gross_pnl": _decimal_str(r.gross_pnl),
                }
                for r in self.kelly_eligible_records
            ],
        }

    def _history_data_payload(self) -> dict:
        return {
            "schema_version": self._schema_version,
            "records": [r.to_dict() for r in self._canonical_records],
        }

    def _provenance_payload(self) -> dict:
        return {
            "schema_version": self._schema_version,
            "strategy_spec_version": self._strategy_spec_version,
            "source_type": self._source_type.value,
            "source_reference": self._source_reference,
            "generated_at": self._generated_at,
            "snapshot_cutoff_timestamp": self._cutoff,
            "completeness_status": self._completeness_status.value,
            "warnings": list(self.warnings),
        }

    @property
    def kelly_input_fingerprint(self) -> str:
        """Kelly-parity identity: basis + ordered (record_identity,
        sequence_number, gross_pnl) of Kelly-eligible records only. The
        record_identity (order_id-based, else natural key) distinguishes
        logically different repeated trades. Excludes fee/net_pnl/provenance/
        generated_at/source_reference."""
        return _fingerprint(self._kelly_input_payload())

    @property
    def history_data_fingerprint(self) -> str:
        """Full canonical record-data identity (includes fee/net_pnl/provenance
        fields on each record)."""
        return _fingerprint(self._history_data_payload())

    @property
    def provenance_fingerprint(self) -> str:
        """Artifact-provenance identity (source, generated_at, cutoff,
        completeness, warnings, schema/spec version)."""
        return _fingerprint(self._provenance_payload())

    # -- serialization --
    def to_dict(self) -> dict:
        """Lossless round-trippable dict. Serializes ORIGINAL input records and
        caller-supplied warnings so ``from_dict`` reproduces identical
        canonicalization, derived warnings and fingerprints. Included fingerprints
        are informational; ``from_dict`` recomputes them."""
        return {
            "schema_version": self._schema_version,
            "strategy_family": self._strategy_family,
            "strategy_spec_version": self._strategy_spec_version,
            "pnl_basis": self._pnl_basis.value,
            "source_type": self._source_type.value,
            "source_reference": self._source_reference,
            "generated_at": self._generated_at,
            "snapshot_cutoff_timestamp": self._cutoff,
            "completeness_status": self._completeness_status.value,
            "warnings": list(self._input_warnings),
            "records": [r.to_dict() for r in self._records],
            "fingerprints": {
                "kelly_input_fingerprint": self.kelly_input_fingerprint,
                "history_data_fingerprint": self.history_data_fingerprint,
                "provenance_fingerprint": self.provenance_fingerprint,
            },
        }

    def canonical_json(self) -> str:
        """Deterministic, input-order-independent JSON of the CANONICAL form
        (sorted/deduped/cutoff-filtered records + combined warnings). Suitable as
        a stable identity string. Does not write any file."""
        payload = {
            "schema_version": self._schema_version,
            "strategy_family": self._strategy_family,
            "strategy_spec_version": self._strategy_spec_version,
            "pnl_basis": self._pnl_basis.value,
            "source_type": self._source_type.value,
            "source_reference": self._source_reference,
            "generated_at": self._generated_at,
            "snapshot_cutoff_timestamp": self._cutoff,
            "completeness_status": self._completeness_status.value,
            "warnings": list(self.warnings),
            "records": [r.to_dict() for r in self._canonical_records],
        }
        return _canonical_dumps(payload)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TradeHistorySnapshot":
        records = [TradeHistoryRecord.from_dict(rd) for rd in data.get("records", ())]
        return cls(
            schema_version=data["schema_version"],
            strategy_family=data.get("strategy_family", ""),
            strategy_spec_version=data.get("strategy_spec_version", ""),
            pnl_basis=data["pnl_basis"],
            source_type=data["source_type"],
            source_reference=data.get("source_reference", ""),
            generated_at=data.get("generated_at"),
            snapshot_cutoff_timestamp=data.get("snapshot_cutoff_timestamp"),
            completeness_status=data["completeness_status"],
            records=records,
            warnings=data.get("warnings", ()),
        )


def _coerce_enum(enum_cls, value: Any, field: str):
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            try:
                return enum_cls[value]
            except KeyError:
                pass
    raise TradeHistoryValidationError(
        f"invalid {field}: {value!r}; expected one of "
        f"{[m.value for m in enum_cls]}")
