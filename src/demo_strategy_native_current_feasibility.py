"""TASK-014CH4A -- read-only CURRENT market + Demo-account feasibility (pure core).

This is the STANDALONE, fully-offline-testable core of CH4A. It contains NO network
I/O and NO file I/O; the thin transport (public market reads, authenticated Demo GET
reads, atomic artifact writes) lives in
``scripts/run_demo_strategy_current_feasibility.py``.

Purpose
-------
CH3 completed the HISTORICAL binding-time review of the canonical WS-bound Plan; it
deliberately left ``current_market_freshness_status = NOT_EVALUATED`` and
``account_margin_feasibility_status = UNAVAILABLE_NOT_EVALUATED``. CH4A is the explicit,
terminal, READ-ONLY revalidation that:

  1. pins the trusted CH3C2 inputs (Review artifact, Anchor Manifest, canonical wrapper,
     strategy-symbol source) by EXACT bytes + externally-supplied canonical SHA256;
  2. evaluates FRESH current public market evidence for the 50 strategy symbols;
  3. recomputes the current executable quantity per target from the CURRENT price
     (never the historical binding price/qty) under the exact deterministic rounding;
  4. evaluates authenticated Demo-account read-only evidence (wallet / positions /
     account mode), proving the Demo environment and denying Live;
  5. determines whether the 50-target plan is currently technically + financially
     feasible, using Decimal arithmetic and never assuming a favourable margin rate.

HARD INVARIANTS (mirrored by the caller and proven by tests)
------------------------------------------------------------
  * This module NEVER authorizes or places an order. There is no order / amend /
    cancel / leverage / margin-mode / position-mode mutation anywhere.
  * ``execution_readiness`` / ``execution_authorized`` / ``execution_batch_authorized``
    are ALWAYS False, even when feasibility PASSes.
  * It imports no sender, runner, readiness, execution gate, native execution, Pilot
    store, ``main`` nor ``src.risk``; it contains no order-endpoint string.
  * PASS means technically/account-feasible AT THE COLLECTION TIMESTAMP ONLY; current
    evidence must be recollected before any later execution authorization.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any, Mapping, Sequence

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_native_ws_bound_plan_consumer as consumer
from src import demo_strategy_native_ws_price_binding as wb

TASK_ID = "TASK-014CH4A"

# --- Schemas ----------------------------------------------------------------
MARKET_EVIDENCE_SCHEMA = "demo_strategy_native_current_market_evidence"
ACCOUNT_EVIDENCE_SCHEMA = "demo_strategy_native_demo_account_readonly_evidence"
FEASIBILITY_REVIEW_SCHEMA = "demo_strategy_native_current_feasibility_review"
SCHEMA_VERSION = 1

# --- Fixed Strategy-native V1 identity (repository-pinned; never from artifacts) ---
EXPECTED_POLICY_ID = wb.ACTIVE_STRATEGY_NATIVE_V1_POLICY
EXPECTED_STRATEGY_ID = wb.EXPECTED_STRATEGY_NAME
EXPECTED_STRATEGY_SYMBOL_COUNT = consumer.EXPECTED_STRATEGY_SYMBOL_COUNT  # 50
EXPECTED_LONG_COUNT = consumer.EXPECTED_LONG_COUNT    # 25
EXPECTED_SHORT_COUNT = consumer.EXPECTED_SHORT_COUNT  # 25
V1_ABS_TARGET_NOTIONAL_USD = Decimal("200")           # per-target |signed notional|
V1_GROSS_USD = Decimal("10000")                       # 50 x 200 gross exposure

# Historical protected symbols -- a CONSISTENCY ANCHOR only. The authoritative
# currently-protected set is derived from the live Demo account snapshot; this constant
# is never the sole source of truth (TASK-014CH4A section 9).
_HISTORICAL_PROTECTED_SYMBOLS: frozenset[str] = frozenset(
    {"ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"})

# --- Public market / instrument acceptance --------------------------------
DEMO_PUBLIC_LINEAR_ENDPOINTS: frozenset[str] = frozenset({
    "https://api-demo.bybit.com/v5/market/tickers",
    ws.PUBLIC_LINEAR_WS_ENDPOINT,  # wss://stream.bybit.com/v5/public/linear
})
ACCEPTED_CONTRACT_TYPES: frozenset[str] = frozenset({"LinearPerpetual", "LinearFutures"})
ACCEPTED_SETTLE_COIN = "USDT"
ACCEPTED_INSTRUMENT_STATUS = "Trading"

# Forbidden Live hostnames -- must never appear in any accepted account/market evidence.
_LIVE_HOST_FRAGMENTS: tuple[str, ...] = ("api.bybit.com", "stream.bybit.com/v5/private")
_ACCEPTED_DEMO_HOST = "api-demo.bybit.com"

# --- Defaults (all configurable by the caller) ----------------------------
DEFAULT_MARKET_FRESHNESS_THRESHOLD_MS = 10_000
STRICT_MAX_MARKET_FRESHNESS_THRESHOLD_MS = 60_000
DEFAULT_ACCOUNT_FRESHNESS_THRESHOLD_MS = 60_000
STRICT_MAX_ACCOUNT_FRESHNESS_THRESHOLD_MS = 600_000
DEFAULT_SAFETY_HEADROOM_FRACTION = Decimal("0.10")  # reserve >=10% of available balance
DEFAULT_FEES_BUFFER_USD = Decimal("5")

# --- Top-level status vocabulary ------------------------------------------
CURRENT_FEASIBILITY_PASS = "CURRENT_FEASIBILITY_PASS"
CURRENT_FEASIBILITY_BLOCKED = "CURRENT_FEASIBILITY_BLOCKED"
CURRENT_FEASIBILITY_UNAVAILABLE = "CURRENT_FEASIBILITY_UNAVAILABLE"
CURRENT_FEASIBILITY_INPUT_INVALID = "CURRENT_FEASIBILITY_INPUT_INVALID"
CURRENT_FEASIBILITY_MARKET_EVIDENCE_FAILED = "CURRENT_FEASIBILITY_MARKET_EVIDENCE_FAILED"
CURRENT_FEASIBILITY_ACCOUNT_EVIDENCE_FAILED = "CURRENT_FEASIBILITY_ACCOUNT_EVIDENCE_FAILED"

# --- Sub-status vocabularies -----------------------------------------------
MARKET_EVIDENCE_FRESH = "CURRENT_MARKET_EVIDENCE_FRESH"
MARKET_EVIDENCE_STALE = "CURRENT_MARKET_EVIDENCE_STALE"
MARKET_EVIDENCE_INCOMPLETE = "CURRENT_MARKET_EVIDENCE_INCOMPLETE"

QTY_VALIDATION_OK = "QUANTITY_VALIDATION_OK"
QTY_VALIDATION_FAILED = "QUANTITY_VALIDATION_FAILED"

ACCOUNT_EVIDENCE_OK = "DEMO_ACCOUNT_EVIDENCE_OK"
ACCOUNT_EVIDENCE_UNAVAILABLE = "DEMO_ACCOUNT_EVIDENCE_UNAVAILABLE"
ACCOUNT_EVIDENCE_BLOCKED = "DEMO_ACCOUNT_EVIDENCE_BLOCKED"

MARGIN_FEASIBILITY_PASS = "MARGIN_FEASIBILITY_PASS"
MARGIN_FEASIBILITY_BLOCKED = "MARGIN_FEASIBILITY_BLOCKED"
MARGIN_FEASIBILITY_UNAVAILABLE = "MARGIN_FEASIBILITY_UNAVAILABLE_NO_INDEPENDENT_RATE"

# --- TASK-014CH4A_FIX2: per-symbol Source-A projected-margin vocabulary ----
# Source A resolves ``margin:initial_margin_rate_unknown`` using the EXACT per-symbol
# configured leverage read (read-only) from authenticated Demo ``position/list`` evidence:
#   projected_initial_margin[sym] = current_rounded_notional[sym] / configured_leverage[sym]
# Each symbol is computed INDEPENDENTLY; the 50 rates are never collapsed into one
# account-wide rate, and accountIMRate / maxLeverage / assumed leverage / another symbol's
# leverage are never used. Missing/zero/invalid/ambiguous/cross-symbol coverage for ANY
# target -> MARGIN_FEASIBILITY_UNAVAILABLE (with the missing symbols listed).
LEVERAGE_EVIDENCE_OK = "TARGET_LEVERAGE_EVIDENCE_OK"
LEVERAGE_EVIDENCE_UNAVAILABLE = "TARGET_LEVERAGE_EVIDENCE_UNAVAILABLE"
LEVERAGE_EVIDENCE_NOT_SUPPLIED = "TARGET_LEVERAGE_EVIDENCE_NOT_SUPPLIED"
PER_SYMBOL_LEVERAGE_RATE_SOURCE = "demo_position_list_symbol_configured_leverage"
MARGIN_BASIS_PER_SYMBOL = "per_symbol_configured_leverage"
MARGIN_BASIS_SINGLE_RATE = "single_independent_rate"
MARGIN_BASIS_UNAVAILABLE = "unavailable"

# Account-LEVEL margin-rate sources (e.g. the wallet ``accountIMRate``) describe overall
# account health -- they are NOT per-order/projected initial-margin evidence for the 50
# NEW target positions and must NEVER independently grant a margin PASS (CH4A_FIX1).
_ACCOUNT_LEVEL_RATE_SOURCES: frozenset[str] = frozenset({
    "wallet.accountimrate", "accountimrate", "account.accountimrate",
    "wallet.accountmmrate", "accountmmrate",
})

CREDENTIAL_LEAK_CLEAR = "NO_CREDENTIAL_VALUE_OR_KEY_PRESENT"


# ---------------------------------------------------------------------------
# Small helpers (pure)
# ---------------------------------------------------------------------------

def _is_pos_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _dec(value: Any) -> Decimal | None:
    return wb._dec(value)


def _canon(value: Any) -> str | None:
    return wb._canon_dec_str(value)


def _as_map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def zeroed_network_audit() -> dict[str, int]:
    """All counters zero. The caller increments only the read-only GET / WS counters."""
    return {
        "public_http_get_count": 0,
        "public_websocket_connection_count": 0,
        "private_demo_http_get_count": 0,
        "private_mutating_request_count": 0,
        "order_post_count": 0,
        "amend_post_count": 0,
        "cancel_post_count": 0,
        "live_order_post_count": 0,
    }


_MUTATING_AUDIT_FIELDS = (
    "private_mutating_request_count", "order_post_count", "amend_post_count",
    "cancel_post_count", "live_order_post_count",
)


def network_audit_is_read_only(audit: Mapping[str, Any]) -> bool:
    """True iff every mutating / order counter is exactly zero."""
    return all(_as_map(audit).get(f) == 0 for f in _MUTATING_AUDIT_FIELDS)


def safe_safety_counters() -> dict[str, Any]:
    """The fixed, always-safe terminal read-only posture (never execution-ready)."""
    return {
        "execution_readiness": False,
        "execution_authorized": False,
        "execution_batch_authorized": False,
        "readiness_called": False,
        "execution_gate_called": False,
        "native_execution_called": False,
        "sender_reachable": False,
        "pilot_advanced": False,
        "rest_fallback_used": False,
        "order_post_count": 0,
        "amend_post_count": 0,
        "cancel_post_count": 0,
        "live_order_post_count": 0,
    }


def _credential_leak_check(artifact: Mapping[str, Any]) -> str:
    """Recursively assert no credential KEY/VALUE is present, then stamp the result.
    Reuses the audited WS credential guard; raises ``ws.WsEndpointError`` on a leak."""
    ws.assert_no_credentials(artifact)
    return CREDENTIAL_LEAK_CLEAR


def _fingerprint_excluding(artifact: Mapping[str, Any], *exclude: str) -> str:
    return wb._fingerprint({k: v for k, v in artifact.items() if k not in exclude})


# ---------------------------------------------------------------------------
# 1. Trusted CH3C2 input pinning
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CurrentTarget:
    """One immutable strategy target carried from the trusted canonical bound Plan."""
    symbol: str
    side: str                       # "long" | "short"
    target_signed_notional_usd: str  # "+200" / "-200"
    binding_price: str               # historical WS-bound price (audit anchor only)
    binding_qty: str                 # historical binding qty (audit anchor only)


@dataclass(frozen=True)
class TrustedInputsResult:
    status: str
    blockers: tuple[str, ...]
    targets: tuple[CurrentTarget, ...]
    symbols: tuple[str, ...]
    canonical_bound_plan_fingerprint: str | None
    anchor_manifest_sha256: str | None
    review_artifact_sha256: str | None
    strategy_symbols_sha256: str | None
    run_date: str | None

    @property
    def ok(self) -> bool:
        return self.status == "TRUSTED_INPUTS_OK"


def _ti_fail(*blockers: str) -> TrustedInputsResult:
    return TrustedInputsResult(
        status=CURRENT_FEASIBILITY_INPUT_INVALID, blockers=tuple(blockers),
        targets=(), symbols=(), canonical_bound_plan_fingerprint=None,
        anchor_manifest_sha256=None, review_artifact_sha256=None,
        strategy_symbols_sha256=None, run_date=None)


def validate_trusted_inputs(
    *,
    review_artifact_bytes: bytes,
    expected_review_artifact_sha256: str,
    anchor_manifest_bytes: bytes,
    expected_anchor_manifest_sha256: str,
    wrapper_artifact_bytes: bytes,
    strategy_symbols_bytes: bytes,
    expected_strategy_symbols_sha256: str,
) -> TrustedInputsResult:
    """Independently pin every trusted CH3C2 input by EXACT bytes + external canonical
    SHA256, and cross-check the lineage chain (Review -> Manifest -> wrapper -> symbols).
    Returns the carried 50 strategy targets ONLY when every anchor agrees. Pure; no I/O.

    External SHA values are authoritative and are NEVER inferred from filenames or mutable
    nested metadata."""
    for name, b in (("review_artifact_bytes", review_artifact_bytes),
                    ("anchor_manifest_bytes", anchor_manifest_bytes),
                    ("wrapper_artifact_bytes", wrapper_artifact_bytes),
                    ("strategy_symbols_bytes", strategy_symbols_bytes)):
        if not isinstance(b, (bytes, bytearray)):
            return _ti_fail(f"{name}_not_bytes")
    for name, sha in (("review", expected_review_artifact_sha256),
                      ("anchor_manifest", expected_anchor_manifest_sha256),
                      ("strategy_symbols", expected_strategy_symbols_sha256)):
        if not consumer._is_canonical_sha(sha):
            return _ti_fail(f"expected_{name}_sha256_not_canonical")

    # --- Pin Review artifact by exact bytes ---
    review_sha = wb.compute_file_sha256(bytes(review_artifact_bytes))
    if review_sha != str(expected_review_artifact_sha256):
        return _ti_fail("review_artifact_sha256_not_expected")
    try:
        review = consumer._as_map(json.loads(bytes(review_artifact_bytes)))
    except Exception:  # noqa: BLE001
        return _ti_fail("review_artifact_invalid_json")
    if not review:
        return _ti_fail("review_artifact_not_object")
    if str(review.get("status", "")) != "WS_BOUND_PLAN_REVIEW_PASS":
        return _ti_fail(f"review_status_not_pass:{review.get('status')}")

    # --- Pin Anchor Manifest by exact bytes ---
    manifest_sha = wb.compute_file_sha256(bytes(anchor_manifest_bytes))
    if manifest_sha != str(expected_anchor_manifest_sha256):
        return _ti_fail("anchor_manifest_sha256_not_expected")
    # Review must reference exactly this manifest (lineage chain integrity).
    if str(review.get("anchor_manifest_sha256", "")) != manifest_sha:
        return _ti_fail("review_anchor_manifest_sha256_mismatch")
    try:
        manifest = _as_map(json.loads(bytes(anchor_manifest_bytes)))
    except Exception:  # noqa: BLE001
        return _ti_fail("anchor_manifest_invalid_json")
    if (str(manifest.get("schema", "")) != "demo_strategy_native_ws_bound_plan_anchor_manifest"
            or manifest.get("schema_version") != 1):
        return _ti_fail("anchor_manifest_schema_or_version_unsupported")
    for f in ("policy_id", "strategy_id", "run_date", "canonical_bound_plan_fingerprint",
              "expected_symbol_set_fingerprint", "strategy_symbols"):
        if manifest.get(f) in (None, ""):
            return _ti_fail(f"anchor_manifest_missing_field:{f}")
    if str(manifest.get("policy_id")) != EXPECTED_POLICY_ID:
        return _ti_fail("anchor_manifest_policy_id_incompatible")
    if str(manifest.get("strategy_id")) != EXPECTED_STRATEGY_ID:
        return _ti_fail("anchor_manifest_strategy_id_incompatible")
    cbp_fp = str(manifest.get("canonical_bound_plan_fingerprint"))
    if not consumer._is_canonical_sha(cbp_fp):
        return _ti_fail("anchor_manifest_canonical_fingerprint_not_canonical")
    # Review's recomputed canonical fingerprint must equal the manifest anchor.
    if str(review.get("recomputed_canonical_bound_plan_fingerprint", "")) != cbp_fp:
        return _ti_fail("review_canonical_fingerprint_not_manifest")

    # --- Pin strategy-symbol source by exact bytes ---
    symbols_sha = wb.compute_file_sha256(bytes(strategy_symbols_bytes))
    if symbols_sha != str(expected_strategy_symbols_sha256):
        return _ti_fail("strategy_symbols_sha256_not_expected")
    try:
        parsed_syms = json.loads(bytes(strategy_symbols_bytes))
    except Exception:  # noqa: BLE001
        return _ti_fail("strategy_symbols_invalid_json")
    symbols = _parse_symbol_list(parsed_syms)
    if symbols is None or len(symbols) != EXPECTED_STRATEGY_SYMBOL_COUNT:
        return _ti_fail("strategy_symbols_not_fifty_list")
    for s in symbols:
        if not isinstance(s, str) or not s or s != s.strip().upper():
            return _ti_fail("strategy_symbol_not_normalized")
    if len(set(symbols)) != EXPECTED_STRATEGY_SYMBOL_COUNT:
        return _ti_fail("strategy_symbols_not_fifty_unique")
    if ws.canonical_strategy_symbol_set_fingerprint(symbols) != \
            str(manifest.get("expected_symbol_set_fingerprint")):
        return _ti_fail("strategy_symbol_set_fingerprint_not_manifest")

    # --- Pin wrapper logical fingerprint + carry the canonical targets ---
    try:
        parsed_wrapper = _as_map(json.loads(bytes(wrapper_artifact_bytes)))
    except Exception:  # noqa: BLE001
        return _ti_fail("wrapper_artifact_invalid_json")
    if not parsed_wrapper:
        return _ti_fail("wrapper_artifact_not_object")
    try:
        wrapper_logical_fp = consumer._recompute_wrapper_fingerprint(parsed_wrapper)
    except Exception:  # noqa: BLE001
        return _ti_fail("wrapper_unfingerprintable")
    if str(parsed_wrapper.get("wrapper_fingerprint", "")) != wrapper_logical_fp:
        return _ti_fail("wrapper_fingerprint_does_not_recompute")
    cbp = _as_map(parsed_wrapper.get("canonical_bound_plan"))
    if str(cbp.get("canonical_bound_plan_fingerprint", "")) != cbp_fp:
        return _ti_fail("wrapper_canonical_fingerprint_not_manifest")
    recomputed_cbp_fp = consumer._recompute_canonical_bound_plan_fingerprint(cbp)
    if recomputed_cbp_fp != cbp_fp:
        return _ti_fail("wrapper_canonical_fingerprint_does_not_recompute")

    targets, terr = _extract_targets(cbp, symbols)
    if terr:
        return _ti_fail(*terr)

    return TrustedInputsResult(
        status="TRUSTED_INPUTS_OK", blockers=(), targets=tuple(targets),
        symbols=tuple(symbols), canonical_bound_plan_fingerprint=cbp_fp,
        anchor_manifest_sha256=manifest_sha, review_artifact_sha256=review_sha,
        strategy_symbols_sha256=symbols_sha, run_date=str(manifest.get("run_date")))


def _parse_symbol_list(parsed: Any) -> list[str] | None:
    if isinstance(parsed, list):
        raw = parsed
    elif isinstance(parsed, Mapping) and isinstance(parsed.get("strategy_symbols"), list):
        raw = parsed.get("strategy_symbols")
    else:
        return None
    return list(raw)


def _extract_targets(cbp: Mapping[str, Any], symbols: Sequence[str],
                     ) -> tuple[list[CurrentTarget], list[str]]:
    """Carry the 50 immutable (symbol, side, signed notional, binding anchors) targets
    from the trusted canonical bound Plan, cross-checking the symbol set + 25/25 + ±200."""
    planner = _as_map(cbp.get("planner"))
    tps = _as_list(planner.get("target_positions"))
    if len(tps) != EXPECTED_STRATEGY_SYMBOL_COUNT:
        return [], ["canonical_target_count_not_fifty"]
    expected_set = {s.strip().upper() for s in symbols}
    out: list[CurrentTarget] = []
    seen: set[str] = set()
    longs = shorts = 0
    for tp in tps:
        tp = _as_map(tp)
        sym = str(tp.get("symbol", "")).strip().upper()
        side = str(tp.get("side", "")).strip().lower()
        notional = _dec(tp.get("target_notional"))
        if not sym or sym in seen:
            return [], ["canonical_target_symbol_missing_or_duplicate"]
        seen.add(sym)
        if sym not in expected_set:
            return [], ["canonical_target_symbol_not_in_symbol_source"]
        if side not in ("long", "short"):
            return [], [f"canonical_target_side_invalid:{sym}"]
        if notional is None or notional.copy_abs() != V1_ABS_TARGET_NOTIONAL_USD:
            return [], [f"canonical_target_notional_not_pm200:{sym}"]
        if side == "long":
            if notional <= 0:
                return [], [f"canonical_long_notional_not_positive:{sym}"]
            longs += 1
        else:
            if notional >= 0:
                return [], [f"canonical_short_notional_not_negative:{sym}"]
            shorts += 1
        out.append(CurrentTarget(
            symbol=sym, side=side,
            target_signed_notional_usd=_canon(notional),
            binding_price=str(_canon(tp.get("price")) or ""),
            binding_qty=str(_canon(tp.get("qty")) or "")))
    if seen != expected_set:
        return [], ["canonical_symbol_set_not_equal_symbol_source"]
    if longs != EXPECTED_LONG_COUNT or shorts != EXPECTED_SHORT_COUNT:
        return [], [f"canonical_long_short_not_25_25:{longs}/{shorts}"]
    out.sort(key=lambda t: t.symbol)
    return out, []


# ---------------------------------------------------------------------------
# 2. Current market evidence + current quantity recomputation
# ---------------------------------------------------------------------------

# Required per-symbol current-market record fields (from the read-only collector).
_REQUIRED_MARKET_FIELDS = (
    "symbol", "current_price", "exchange_ts_ms", "local_received_epoch_ns",
    "endpoint", "instrument_status", "tick_size", "qty_step", "min_order_qty",
    "min_notional_value", "max_market_order_qty", "contract_type", "settle_coin",
    "trading",
)


@dataclass(frozen=True)
class CurrentActionFeasibility:
    """Immutable per-action current feasibility row (scalar-only; artifact-ready).

    Retains ALL validated market evidence so the market validation can be replayed
    offline from the artifact alone (TASK-014CH4A_FIX1 completeness)."""
    symbol: str
    side: str
    target_signed_notional_usd: str
    current_price: str
    exchange_ts_ms: Any
    local_received_epoch_ns: Any
    evidence_age_ms: int | None
    endpoint: str
    instrument_status: str
    contract_type: str
    settle_coin: str
    trading: Any
    tick_size: str
    qty_step: str
    min_order_qty: str
    min_notional_value: str
    max_market_order_qty: str
    raw_quantity: str
    rounded_quantity: str
    rounded_notional_usd: str
    binding_price: str
    binding_qty: str
    price_drift_pct: str | None
    quantity_validation_status: str
    quantity_validation_failures: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol, "side": self.side,
            "target_signed_notional_usd": self.target_signed_notional_usd,
            "current_price": self.current_price,
            "exchange_ts_ms": self.exchange_ts_ms,
            "local_received_epoch_ns": self.local_received_epoch_ns,
            "evidence_age_ms": self.evidence_age_ms,
            "endpoint": self.endpoint,
            "instrument_status": self.instrument_status,
            "contract_type": self.contract_type,
            "settle_coin": self.settle_coin,
            "trading": self.trading,
            "tick_size": self.tick_size,
            "qty_step": self.qty_step, "min_order_qty": self.min_order_qty,
            "min_notional_value": self.min_notional_value,
            "max_market_order_qty": self.max_market_order_qty,
            "raw_quantity": self.raw_quantity,
            "rounded_quantity": self.rounded_quantity,
            "rounded_notional_usd": self.rounded_notional_usd,
            "binding_price": self.binding_price, "binding_qty": self.binding_qty,
            "price_drift_pct": self.price_drift_pct,
            "quantity_validation_status": self.quantity_validation_status,
            "quantity_validation_failures": list(self.quantity_validation_failures),
        }


@dataclass(frozen=True)
class MarketEvidenceResult:
    status: str                       # MARKET_EVIDENCE_FRESH / STALE / INCOMPLETE
    blockers: tuple[str, ...]
    actions: tuple[CurrentActionFeasibility, ...]
    evaluated_symbol_count: int
    fresh_symbol_count: int
    long_count: int
    short_count: int
    total_target_gross_notional_usd: str
    total_rounded_gross_notional_usd: str | None
    quantity_all_valid: bool
    market_freshness_threshold_ms: int
    market_freshness_oldest_age_ms: int | None

    @property
    def ok(self) -> bool:
        return self.status == MARKET_EVIDENCE_FRESH and self.quantity_all_valid


def evaluate_current_market_and_quantities(
    market_records: Sequence[Mapping[str, Any]],
    *,
    targets: Sequence[CurrentTarget],
    collection_epoch_ns: int,
    market_freshness_threshold_ms: int = DEFAULT_MARKET_FRESHNESS_THRESHOLD_MS,
) -> MarketEvidenceResult:
    """Validate FRESH current market evidence for exactly the 50 targets and recompute
    the CURRENT executable quantity per target from the CURRENT price under the exact
    deterministic floor-to-step rounding. Pure; no I/O. Fails closed on any missing /
    duplicate / stale / non-trading / unsupported / sub-minimum / zero-after-rounding
    condition. The historical binding price/qty is NEVER used as the current quantity."""
    blockers: list[str] = []
    if not _is_pos_int(collection_epoch_ns):
        return _market_fail(["collection_epoch_ns_not_positive_int"],
                            market_freshness_threshold_ms)
    if not (_is_pos_int(market_freshness_threshold_ms)
            and market_freshness_threshold_ms <= STRICT_MAX_MARKET_FRESHNESS_THRESHOLD_MS):
        return _market_fail(["market_freshness_threshold_invalid"],
                            market_freshness_threshold_ms)

    target_by_symbol = {t.symbol: t for t in targets}
    if len(target_by_symbol) != EXPECTED_STRATEGY_SYMBOL_COUNT:
        return _market_fail(["targets_not_fifty_unique"], market_freshness_threshold_ms)

    by_symbol: dict[str, Mapping[str, Any]] = {}
    for rec in market_records:
        rec = _as_map(rec)
        sym = str(rec.get("symbol", "")).strip().upper()
        if not sym:
            blockers.append("market_record_symbol_missing")
            continue
        if sym in by_symbol:
            blockers.append(f"market_record_duplicate_symbol:{sym}")
            continue
        by_symbol[sym] = rec
    for sym in sorted(target_by_symbol):
        if sym not in by_symbol:
            blockers.append(f"market_record_missing_symbol:{sym}")
    extra = set(by_symbol) - set(target_by_symbol)
    for sym in sorted(extra):
        blockers.append(f"market_record_unexpected_symbol:{sym}")
    if blockers:
        return _market_fail(blockers, market_freshness_threshold_ms,
                            status=MARKET_EVIDENCE_INCOMPLETE)

    actions: list[CurrentActionFeasibility] = []
    oldest_age: int | None = None
    any_stale = False
    all_qty_valid = True
    longs = shorts = 0
    total_target_gross = Decimal("0")
    total_rounded_gross = Decimal("0")
    rounded_gross_known = True

    for sym in sorted(target_by_symbol):
        tgt = target_by_symbol[sym]
        rec = by_symbol[sym]
        row, age_ms, stale, valid = _evaluate_one_symbol(
            tgt, rec, collection_epoch_ns=collection_epoch_ns,
            market_freshness_threshold_ms=market_freshness_threshold_ms)
        actions.append(row)
        if age_ms is not None:
            oldest_age = age_ms if oldest_age is None else max(oldest_age, age_ms)
        any_stale = any_stale or stale
        all_qty_valid = all_qty_valid and valid
        if row.side == "long":
            longs += 1
        else:
            shorts += 1
        total_target_gross += V1_ABS_TARGET_NOTIONAL_USD
        rn = _dec(row.rounded_notional_usd)
        if rn is None:
            rounded_gross_known = False
        else:
            total_rounded_gross += rn

    status = MARKET_EVIDENCE_STALE if any_stale else MARKET_EVIDENCE_FRESH
    return MarketEvidenceResult(
        status=status,
        blockers=tuple(r.symbol + ":stale" for r in actions
                       if "stale_evidence" in r.quantity_validation_failures) if any_stale else (),
        actions=tuple(actions),
        evaluated_symbol_count=len(actions),
        fresh_symbol_count=sum(1 for r in actions
                               if "stale_evidence" not in r.quantity_validation_failures),
        long_count=longs, short_count=shorts,
        total_target_gross_notional_usd=_canon(total_target_gross),
        total_rounded_gross_notional_usd=(_canon(total_rounded_gross)
                                          if rounded_gross_known else None),
        quantity_all_valid=all_qty_valid and not any_stale,
        market_freshness_threshold_ms=market_freshness_threshold_ms,
        market_freshness_oldest_age_ms=oldest_age)


def _market_fail(blockers: list[str], threshold_ms: int,
                 status: str = MARKET_EVIDENCE_INCOMPLETE) -> MarketEvidenceResult:
    return MarketEvidenceResult(
        status=status, blockers=tuple(blockers), actions=(),
        evaluated_symbol_count=0, fresh_symbol_count=0, long_count=0, short_count=0,
        total_target_gross_notional_usd=_canon(Decimal("0")),
        total_rounded_gross_notional_usd=None, quantity_all_valid=False,
        market_freshness_threshold_ms=threshold_ms, market_freshness_oldest_age_ms=None)


def _evaluate_one_symbol(
    tgt: CurrentTarget, rec: Mapping[str, Any], *,
    collection_epoch_ns: int, market_freshness_threshold_ms: int,
) -> tuple[CurrentActionFeasibility, int | None, bool, bool]:
    """Return (row, age_ms, stale, qty_valid) for one symbol. Never raises."""
    failures: list[str] = []
    sym = tgt.symbol

    missing = [f for f in _REQUIRED_MARKET_FIELDS if f not in rec]
    if missing:
        failures.append(f"missing_market_fields:{sorted(missing)}")

    # --- Endpoint / instrument acceptance ---
    endpoint = str(rec.get("endpoint", ""))
    if endpoint not in DEMO_PUBLIC_LINEAR_ENDPOINTS:
        failures.append("endpoint_not_public_demo_linear")
    if any(frag in endpoint for frag in _LIVE_HOST_FRAGMENTS):
        failures.append("live_endpoint_detected")
    if str(rec.get("instrument_status", "")) != ACCEPTED_INSTRUMENT_STATUS:
        failures.append("instrument_not_trading")
    if rec.get("trading") is not True:
        failures.append("instrument_trading_flag_not_true")
    if str(rec.get("contract_type", "")) not in ACCEPTED_CONTRACT_TYPES:
        failures.append("contract_type_unsupported")
    if str(rec.get("settle_coin", "")) != ACCEPTED_SETTLE_COIN:
        failures.append("settle_coin_not_usdt")

    # --- Freshness ---
    age_ms: int | None = None
    stale = False
    lr = rec.get("local_received_epoch_ns")
    ex_ts = rec.get("exchange_ts_ms")
    if not _is_pos_int(ex_ts):
        failures.append("exchange_ts_ms_not_positive_int")
    if not _is_pos_int(lr):
        failures.append("local_received_epoch_ns_not_positive_int")
    else:
        age_ms = int((collection_epoch_ns - lr) / 1_000_000)
        if age_ms < 0:
            failures.append("evidence_in_future")
            stale = True
        elif age_ms > market_freshness_threshold_ms:
            failures.append("stale_evidence")
            stale = True

    # --- Price + rule decimals ---
    price = _dec(rec.get("current_price"))
    qty_step = _dec(rec.get("qty_step"))
    min_qty = _dec(rec.get("min_order_qty"))
    min_notional = _dec(rec.get("min_notional_value"))
    max_mkt = _dec(rec.get("max_market_order_qty"))
    if price is None or price <= 0:
        failures.append("current_price_not_positive")
    if qty_step is None or qty_step <= 0:
        failures.append("qty_step_not_positive")
    if min_qty is None or min_qty < 0:
        failures.append("min_order_qty_invalid")
    if min_notional is None or min_notional < 0:
        failures.append("min_notional_value_invalid")
    if max_mkt is None or max_mkt < 0:
        failures.append("max_market_order_qty_invalid")

    # --- Current quantity recomputation (Decimal, floor-to-step) ---
    raw_q = rounded_q = rounded_notional = None
    drift_pct: str | None = None
    if price is not None and price > 0:
        raw_q = (V1_ABS_TARGET_NOTIONAL_USD / price)
        rounded_q = wb._floor_qty(V1_ABS_TARGET_NOTIONAL_USD, price, qty_step)
        rounded_notional = rounded_q * price
        bp = _dec(tgt.binding_price)
        if bp is not None and bp > 0:
            drift_pct = _canon(((price - bp) / bp) * Decimal("100"))
        # quantity-feasibility checks
        if not (rounded_q > 0):
            failures.append("zero_quantity_after_rounding")
        if min_qty is not None and min_qty >= 0 and rounded_q < min_qty:
            failures.append("below_min_order_qty")
        if min_notional is not None and rounded_notional < min_notional:
            failures.append("below_min_notional")
        if max_mkt is not None and max_mkt > 0 and rounded_q > max_mkt:
            failures.append("above_max_market_order_qty")
        if qty_step is not None and qty_step > 0 and (rounded_q % qty_step) != 0:
            failures.append("qty_not_step_multiple")

    tick_size = _dec(rec.get("tick_size"))
    qty_valid = not failures
    row = CurrentActionFeasibility(
        symbol=sym, side=tgt.side,
        target_signed_notional_usd=tgt.target_signed_notional_usd,
        current_price=str(_canon(price) if price is not None else rec.get("current_price")),
        exchange_ts_ms=rec.get("exchange_ts_ms"),
        local_received_epoch_ns=rec.get("local_received_epoch_ns"),
        evidence_age_ms=age_ms,
        endpoint=endpoint,
        instrument_status=str(rec.get("instrument_status", "")),
        contract_type=str(rec.get("contract_type", "")),
        settle_coin=str(rec.get("settle_coin", "")),
        trading=rec.get("trading"),
        tick_size=str(_canon(tick_size) if tick_size is not None else rec.get("tick_size")),
        qty_step=str(_canon(qty_step) if qty_step is not None else rec.get("qty_step")),
        min_order_qty=str(_canon(min_qty) if min_qty is not None else rec.get("min_order_qty")),
        min_notional_value=str(_canon(min_notional) if min_notional is not None
                               else rec.get("min_notional_value")),
        max_market_order_qty=str(_canon(max_mkt) if max_mkt is not None
                                 else rec.get("max_market_order_qty")),
        raw_quantity=str(_canon(raw_q) if raw_q is not None else ""),
        rounded_quantity=str(_canon(rounded_q) if rounded_q is not None else ""),
        rounded_notional_usd=str(_canon(rounded_notional)
                                 if rounded_notional is not None else ""),
        binding_price=tgt.binding_price, binding_qty=tgt.binding_qty,
        price_drift_pct=drift_pct,
        quantity_validation_status=(QTY_VALIDATION_OK if qty_valid else QTY_VALIDATION_FAILED),
        quantity_validation_failures=tuple(failures))
    return row, age_ms, stale, qty_valid


# ---------------------------------------------------------------------------
# 3. Demo account read-only evidence
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AccountEvidenceResult:
    status: str                       # ACCOUNT_EVIDENCE_OK / UNAVAILABLE / BLOCKED
    blockers: tuple[str, ...]
    demo_environment_verified: bool
    live_environment_denied: bool
    account_mode: str | None
    margin_mode: str | None
    position_mode: str | None
    account_equity_usd: str | None
    available_balance_usd: str | None
    existing_initial_margin_usd: str | None
    existing_maintenance_margin_usd: str | None
    open_position_count: int
    protected_positions: tuple[str, ...]
    historical_protected_anchor: tuple[str, ...]
    strategy_position_overlaps: tuple[str, ...]
    applicable_initial_margin_rate: str | None
    margin_rate_source: str | None
    account_im_rate_context: str | None
    account_freshness_age_ms: int | None
    # TASK-014CH4A_FIX2: per-symbol Source-A configured-leverage evidence (read-only).
    # ``target_configured_leverage_by_symbol`` is populated ONLY for symbols with valid,
    # exact-symbol, unambiguous leverage evidence; coverage failure never blocks the
    # account (it surfaces as MARGIN_FEASIBILITY_UNAVAILABLE in the margin model instead).
    target_leverage_evidence_status: str = LEVERAGE_EVIDENCE_NOT_SUPPLIED
    target_configured_leverage_by_symbol: dict[str, str] = field(default_factory=dict)
    target_leverage_missing_symbols: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == ACCOUNT_EVIDENCE_OK


def _validate_target_leverage_evidence(
    evidence: Any, target_set: set[str],
) -> tuple[str, dict[str, str], tuple[str, ...]]:
    """TASK-014CH4A_FIX2 (Source A). Validate EXACT per-symbol configured-leverage evidence
    for every one of the target symbols. Pure; never raises.

    Returns ``(status, leverage_by_symbol, missing_symbols)``. A symbol qualifies ONLY when
    its record carries leverage tied to that EXACT symbol (no cross-symbol), a single
    unambiguous positive value (hedge Buy/Sell rows must agree), and parses to Decimal > 0.
    Any missing / zero / invalid / ambiguous / cross-symbol target makes the whole result
    UNAVAILABLE and is listed in ``missing_symbols`` (sorted). Never reads maxLeverage,
    accountIMRate, an assumed leverage, or another symbol's leverage."""
    # Accept either {symbol: record} or [record, ...] (each record carrying ``symbol``).
    ev_map: dict[str, Any] = {}
    if isinstance(evidence, Mapping):
        ev_map = {str(k).strip().upper(): v for k, v in evidence.items()}
    elif isinstance(evidence, (list, tuple)):
        for rec in evidence:
            rec_m = _as_map(rec)
            s = str(rec_m.get("symbol", "")).strip().upper()
            if s:
                ev_map[s] = rec_m

    leverage_by_symbol: dict[str, str] = {}
    missing: list[str] = []
    for sym in sorted(target_set):
        rec = _as_map(ev_map.get(sym))
        if not rec:
            missing.append(sym)
            continue
        # Cross-symbol guard: every symbol named by the evidence must be exactly ``sym``.
        ev_syms = rec.get("evidence_symbols")
        if not isinstance(ev_syms, (list, tuple)) or not ev_syms:
            one = rec.get("evidence_symbol")
            ev_syms = [one] if one else []
        if not ev_syms or any(str(x).strip().upper() != sym for x in ev_syms):
            missing.append(sym)
            continue
        lev_values = rec.get("leverage_values")
        if not isinstance(lev_values, (list, tuple)) or not lev_values:
            missing.append(sym)
            continue
        decs = [_dec(v) for v in lev_values]
        if any(d is None or d <= 0 for d in decs):
            missing.append(sym)
            continue
        distinct = {_canon(d) for d in decs}
        if len(distinct) != 1:          # ambiguous (disagreeing leverage rows)
            missing.append(sym)
            continue
        leverage_by_symbol[sym] = next(iter(distinct))

    covered = (not missing) and len(leverage_by_symbol) == len(target_set)
    status = LEVERAGE_EVIDENCE_OK if covered else LEVERAGE_EVIDENCE_UNAVAILABLE
    return status, leverage_by_symbol, tuple(sorted(missing))


def evaluate_demo_account_evidence(
    snapshot: Mapping[str, Any],
    *,
    target_symbols: Sequence[str],
    collection_epoch_ns: int,
    account_freshness_threshold_ms: int = DEFAULT_ACCOUNT_FRESHNESS_THRESHOLD_MS,
) -> AccountEvidenceResult:
    """Validate authenticated Demo-only read-only account evidence. Proves the Demo
    environment, denies Live, evaluates freshness, parses positions, identifies the
    currently-protected legacy positions from THIS snapshot, and fails closed on any
    strategy/protected overlap or incompatible position mode. Pure; no I/O; never reads
    or returns any credential value."""
    blockers: list[str] = []
    snap = _as_map(snapshot)
    target_set = {s.strip().upper() for s in target_symbols}

    # --- TASK-014CH4A_FIX2: per-symbol Source-A configured-leverage evidence ---
    # Validated independently of wallet/position checks. A coverage failure does NOT block
    # the account (the account can still be OK); it only denies a margin PASS downstream.
    if "target_leverage_evidence" in snap:
        lev_status, lev_by_symbol, lev_missing = _validate_target_leverage_evidence(
            snap.get("target_leverage_evidence"), target_set)
    else:
        lev_status, lev_by_symbol, lev_missing = (
            LEVERAGE_EVIDENCE_NOT_SUPPLIED, {}, ())

    # --- Demo environment proof / Live denial ---
    endpoint_family = str(snap.get("endpoint_family", ""))
    base_url = str(snap.get("base_url", ""))
    demo_flag = snap.get("demo_flag") is True
    live_fallback = snap.get("live_endpoint_fallback_detected") is True
    demo_verified = (
        endpoint_family == "bybit_demo" and demo_flag
        and _ACCEPTED_DEMO_HOST in base_url
        and not any(frag in base_url for frag in _LIVE_HOST_FRAGMENTS))
    live_denied = (not live_fallback
                   and not any(frag in base_url for frag in _LIVE_HOST_FRAGMENTS))
    if not demo_verified:
        blockers.append("demo_environment_not_verified")
    if not live_denied:
        blockers.append("live_environment_not_denied")

    # --- Freshness ---
    age_ms: int | None = None
    if not (_is_pos_int(account_freshness_threshold_ms)
            and account_freshness_threshold_ms <= STRICT_MAX_ACCOUNT_FRESHNESS_THRESHOLD_MS):
        blockers.append("account_freshness_threshold_invalid")
    snap_epoch = snap.get("snapshot_epoch_ns")
    if not _is_pos_int(snap_epoch):
        blockers.append("snapshot_epoch_ns_not_positive_int")
    elif not _is_pos_int(collection_epoch_ns):
        blockers.append("collection_epoch_ns_not_positive_int")
    else:
        age_ms = int((collection_epoch_ns - snap_epoch) / 1_000_000)
        if age_ms < 0:
            blockers.append("account_evidence_in_future")
        elif (_is_pos_int(account_freshness_threshold_ms)
              and age_ms > account_freshness_threshold_ms):
            blockers.append("account_evidence_stale")

    # --- Wallet evidence presence ---
    equity = _dec(snap.get("account_equity_usd"))
    available = _dec(snap.get("available_balance_usd"))
    existing_im = _dec(snap.get("existing_initial_margin_usd"))
    existing_mm = _dec(snap.get("existing_maintenance_margin_usd"))
    wallet_present = snap.get("wallet_evidence_present") is True
    if not wallet_present or equity is None or available is None:
        # Missing wallet evidence is UNAVAILABLE (not a hard BLOCK).
        return AccountEvidenceResult(
            status=ACCOUNT_EVIDENCE_UNAVAILABLE,
            blockers=tuple(blockers + ["wallet_evidence_unavailable"]),
            demo_environment_verified=demo_verified, live_environment_denied=live_denied,
            account_mode=_opt_str(snap.get("account_mode")),
            margin_mode=_opt_str(snap.get("margin_mode")),
            position_mode=_opt_str(snap.get("position_mode")),
            account_equity_usd=(_canon(equity) if equity is not None else None),
            available_balance_usd=(_canon(available) if available is not None else None),
            existing_initial_margin_usd=(_canon(existing_im) if existing_im is not None else None),
            existing_maintenance_margin_usd=(_canon(existing_mm) if existing_mm is not None else None),
            open_position_count=0, protected_positions=(), historical_protected_anchor=(),
            strategy_position_overlaps=(),
            applicable_initial_margin_rate=None, margin_rate_source=None,
            account_im_rate_context=_opt_str(snap.get("account_im_rate_context")),
            account_freshness_age_ms=age_ms,
            target_leverage_evidence_status=lev_status,
            target_configured_leverage_by_symbol=dict(lev_by_symbol),
            target_leverage_missing_symbols=lev_missing)

    # --- Positions ---
    positions = snap.get("positions")
    if not isinstance(positions, (list, tuple)):
        blockers.append("positions_malformed")
        positions = []
    held: list[str] = []
    overlaps: list[str] = []
    seen_pos: set[str] = set()
    for p in positions:
        p = _as_map(p)
        psym = str(p.get("symbol", "")).strip().upper()
        side = str(p.get("side", "")).strip().lower()
        size = _dec(p.get("size"))
        if not psym:
            blockers.append("position_symbol_missing")
            continue
        if size is None:
            blockers.append(f"position_size_unparseable:{psym}")
            continue
        if size <= 0:
            continue  # flat row -- ignored
        if side not in ("long", "short"):
            blockers.append(f"position_side_invalid:{psym}")
            continue
        if psym in seen_pos:
            blockers.append(f"position_duplicate_symbol:{psym}")
            continue
        seen_pos.add(psym)
        held.append(psym)
        if psym in target_set:
            # A current open position that coincides with a strategy target would be
            # silently resized -- fail closed (this task performs NO reconciliation).
            overlaps.append(psym)

    # EVERY currently non-zero pre-existing position is PROTECTED: this run owns no
    # positions (read-only, no execution), so any open position is pre-existing and must
    # default to protected -- not merely the historically-known symbols. The historical
    # constant is retained ONLY as a consistency anchor.
    protected_now = sorted(held)
    historical_anchor = sorted(set(held) & _HISTORICAL_PROTECTED_SYMBOLS)
    # Protected symbols (historical anchor) must never appear among the strategy targets.
    for s in sorted(_HISTORICAL_PROTECTED_SYMBOLS & target_set):
        blockers.append(f"protected_symbol_in_strategy_targets:{s}")
    for s in sorted(overlaps):
        blockers.append(f"strategy_target_overlaps_open_position:{s}")

    # --- Position mode must be explicit + supported ---
    position_mode = _opt_str(snap.get("position_mode"))
    if position_mode is None:
        blockers.append("position_mode_unavailable")
    elif position_mode not in ("one_way", "hedge"):
        blockers.append(f"position_mode_unsupported:{position_mode}")

    # --- Optional INDEPENDENT projected-margin evidence (never assumed favourable) ---
    # ``applicable_initial_margin_rate`` must be per-order/projected evidence for the NEW
    # positions. An account-LEVEL source (e.g. wallet accountIMRate) is rejected here and
    # kept only as ``account_im_rate_context`` -- it can never grant a margin PASS.
    rate = _dec(snap.get("applicable_initial_margin_rate"))
    rate_source = _opt_str(snap.get("margin_rate_source"))
    account_level = bool(rate_source and rate_source.strip().lower() in _ACCOUNT_LEVEL_RATE_SOURCES)
    rate_str = (_canon(rate) if (rate is not None and rate > 0 and rate_source
                                 and not account_level) else None)

    status = ACCOUNT_EVIDENCE_OK if not blockers else ACCOUNT_EVIDENCE_BLOCKED
    return AccountEvidenceResult(
        status=status, blockers=tuple(blockers),
        demo_environment_verified=demo_verified, live_environment_denied=live_denied,
        account_mode=_opt_str(snap.get("account_mode")),
        margin_mode=_opt_str(snap.get("margin_mode")),
        position_mode=position_mode,
        account_equity_usd=_canon(equity), available_balance_usd=_canon(available),
        existing_initial_margin_usd=(_canon(existing_im) if existing_im is not None else None),
        existing_maintenance_margin_usd=(_canon(existing_mm) if existing_mm is not None else None),
        open_position_count=len(held),
        protected_positions=tuple(protected_now),
        historical_protected_anchor=tuple(historical_anchor),
        strategy_position_overlaps=tuple(sorted(overlaps)),
        applicable_initial_margin_rate=rate_str,
        margin_rate_source=(rate_source if rate_str else None),
        account_im_rate_context=_opt_str(snap.get("account_im_rate_context")),
        account_freshness_age_ms=age_ms,
        target_leverage_evidence_status=lev_status,
        target_configured_leverage_by_symbol=dict(lev_by_symbol),
        target_leverage_missing_symbols=lev_missing)


def _opt_str(value: Any) -> str | None:
    return None if value is None else str(value)


# ---------------------------------------------------------------------------
# 4. Margin-feasibility model (Decimal; never assumes a favourable rate)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MarginFeasibilityResult:
    status: str                       # MARGIN_FEASIBILITY_PASS / BLOCKED / UNAVAILABLE
    failures: tuple[str, ...]
    account_equity_usd: str | None
    available_balance_usd: str | None
    existing_initial_margin_usd: str | None
    projected_additional_initial_margin_usd: str | None
    projected_total_initial_margin_usd: str | None
    estimated_fees_buffer_usd: str
    safety_headroom_usd: str | None
    remaining_available_balance_usd: str | None
    margin_rate_source: str | None
    conservative_1x_envelope_usd: str
    conservative_1x_envelope_label: str
    # TASK-014CH4A_FIX2: which evidence basis produced the projection, and the per-symbol
    # Source-A breakdown (sorted by symbol) so the margin verdict replays offline.
    margin_basis: str = MARGIN_BASIS_UNAVAILABLE
    target_leverage_evidence_status: str = LEVERAGE_EVIDENCE_NOT_SUPPLIED
    per_symbol_initial_margin: tuple[Mapping[str, Any], ...] = ()


def evaluate_margin_feasibility(
    *,
    account_result: AccountEvidenceResult,
    target_gross_notional_usd: Decimal,
    market_result: "MarketEvidenceResult | None" = None,
    safety_headroom_fraction: Decimal = DEFAULT_SAFETY_HEADROOM_FRACTION,
    fees_buffer_usd: Decimal = DEFAULT_FEES_BUFFER_USD,
) -> MarginFeasibilityResult:
    """Decimal margin-feasibility model. Never claims PASS when the required initial
    margin rate is unknown (-> UNAVAILABLE). A conservative 1x envelope is always
    reported and clearly labelled, but never used to grant PASS without independent
    evidence. Reserves a configurable safety headroom of available balance.

    TASK-014CH4A_FIX2 (Source A): when per-symbol configured-leverage evidence was supplied
    (``account_result.target_leverage_evidence_status != NOT_SUPPLIED``), the projection is
    computed INDEPENDENTLY per target as ``current_rounded_notional / configured_leverage``
    and summed -- never collapsed to one account-wide rate, never using accountIMRate /
    maxLeverage / an assumed leverage. Full 50-symbol coverage is required; otherwise the
    status is UNAVAILABLE and the uncovered symbols are listed. When no leverage evidence is
    supplied, the legacy single independent-rate path (CH4A_FIX1) is used unchanged."""
    available = _dec(account_result.available_balance_usd)
    equity = _dec(account_result.account_equity_usd)
    existing_im = _dec(account_result.existing_initial_margin_usd) or Decimal("0")
    fees = fees_buffer_usd if fees_buffer_usd is not None and fees_buffer_usd >= 0 else Decimal("0")
    gross = target_gross_notional_usd
    one_x_envelope = gross  # 1x initial margin == full gross notional (worst case)
    headroom_frac = (safety_headroom_fraction
                     if (safety_headroom_fraction is not None
                         and Decimal("0") <= safety_headroom_fraction < Decimal("1"))
                     else DEFAULT_SAFETY_HEADROOM_FRACTION)

    base = MarginFeasibilityResult(
        status=MARGIN_FEASIBILITY_UNAVAILABLE, failures=(),
        account_equity_usd=(_canon(equity) if equity is not None else None),
        available_balance_usd=(_canon(available) if available is not None else None),
        existing_initial_margin_usd=_canon(existing_im),
        projected_additional_initial_margin_usd=None,
        projected_total_initial_margin_usd=None,
        estimated_fees_buffer_usd=_canon(fees),
        safety_headroom_usd=None, remaining_available_balance_usd=None,
        margin_rate_source=None,
        conservative_1x_envelope_usd=_canon(one_x_envelope),
        conservative_1x_envelope_label="1x_initial_margin_equals_full_gross_notional",
        margin_basis=MARGIN_BASIS_UNAVAILABLE,
        target_leverage_evidence_status=account_result.target_leverage_evidence_status)

    if not account_result.ok:
        return replace(base, status=MARGIN_FEASIBILITY_UNAVAILABLE,
                        failures=("account_evidence_not_ok",))
    if available is None or available < 0:
        return replace(base, status=MARGIN_FEASIBILITY_UNAVAILABLE,
                        failures=("available_balance_unavailable",))

    # --- Source A (preferred): per-symbol configured leverage, computed independently ---
    if account_result.target_leverage_evidence_status != LEVERAGE_EVIDENCE_NOT_SUPPLIED:
        return _per_symbol_margin_feasibility(
            base, account_result=account_result, market_result=market_result,
            available=available, existing_im=existing_im, fees=fees,
            headroom_frac=headroom_frac)

    # --- Legacy single independent-rate path (CH4A_FIX1; unchanged) ---
    rate = _dec(account_result.applicable_initial_margin_rate)
    if rate is None or rate <= 0 or not account_result.margin_rate_source:
        # Required margin rate unknown -> never PASS.
        return replace(base, status=MARGIN_FEASIBILITY_UNAVAILABLE,
                        failures=("initial_margin_rate_unknown",))

    additional_im = (gross * rate)
    projected_total = existing_im + additional_im
    headroom = (available * headroom_frac)
    remaining = available - additional_im - fees
    failures: list[str] = []
    if remaining < 0:
        failures.append("insufficient_available_balance")
    if remaining < headroom:
        failures.append("safety_headroom_violation")
    status = MARGIN_FEASIBILITY_PASS if not failures else MARGIN_FEASIBILITY_BLOCKED
    return replace(
        base, status=status, failures=tuple(failures), margin_basis=MARGIN_BASIS_SINGLE_RATE,
        projected_additional_initial_margin_usd=_canon(additional_im),
        projected_total_initial_margin_usd=_canon(projected_total),
        safety_headroom_usd=_canon(headroom),
        remaining_available_balance_usd=_canon(remaining),
        margin_rate_source=account_result.margin_rate_source)


def _per_symbol_margin_feasibility(
    base: MarginFeasibilityResult, *,
    account_result: AccountEvidenceResult,
    market_result: "MarketEvidenceResult | None",
    available: Decimal, existing_im: Decimal, fees: Decimal, headroom_frac: Decimal,
) -> MarginFeasibilityResult:
    """Source A core. Projects initial margin PER SYMBOL from the exact configured leverage
    and the current rounded notional, summing independently. Requires complete coverage for
    every target; otherwise UNAVAILABLE with the uncovered symbols listed."""
    leverage_by_symbol = account_result.target_configured_leverage_by_symbol

    # Leverage coverage must be complete for ALL targets (no missing/zero/invalid/ambiguous/
    # cross-symbol evidence).
    if account_result.target_leverage_evidence_status != LEVERAGE_EVIDENCE_OK:
        miss = account_result.target_leverage_missing_symbols
        return replace(
            base, status=MARGIN_FEASIBILITY_UNAVAILABLE, margin_basis=MARGIN_BASIS_PER_SYMBOL,
            margin_rate_source=PER_SYMBOL_LEVERAGE_RATE_SOURCE,
            failures=("target_leverage_evidence_incomplete",
                      *(f"leverage_missing:{s}" for s in miss)))

    # Current rounded notional per symbol comes from the validated market evidence.
    notional_by_symbol: dict[str, Decimal] = {}
    if market_result is not None:
        for a in market_result.actions:
            rn = _dec(a.rounded_notional_usd)
            if rn is not None and rn > 0:
                notional_by_symbol[a.symbol] = rn

    lev_syms = set(leverage_by_symbol)
    missing_notional = sorted(lev_syms - set(notional_by_symbol))
    if market_result is None or not lev_syms or missing_notional:
        return replace(
            base, status=MARGIN_FEASIBILITY_UNAVAILABLE, margin_basis=MARGIN_BASIS_PER_SYMBOL,
            margin_rate_source=PER_SYMBOL_LEVERAGE_RATE_SOURCE,
            failures=("per_symbol_notional_unavailable",
                      *(f"notional_missing:{s}" for s in missing_notional)))

    breakdown: list[dict[str, Any]] = []
    additional_im = Decimal("0")
    for sym in sorted(lev_syms):
        lev = _dec(leverage_by_symbol[sym])
        rn = notional_by_symbol[sym]
        im = rn / lev                       # projected_initial_margin = notional / leverage
        additional_im += im
        breakdown.append({
            "symbol": sym,
            "rounded_notional_usd": _canon(rn),
            "configured_leverage": _canon(lev),
            "initial_margin_rate": _canon(Decimal(1) / lev),
            "projected_initial_margin_usd": _canon(im),
        })

    projected_total = existing_im + additional_im
    headroom = (available * headroom_frac)
    remaining = available - additional_im - fees
    failures: list[str] = []
    if remaining < 0:
        failures.append("insufficient_available_balance")
    if remaining < headroom:
        failures.append("safety_headroom_violation")
    status = MARGIN_FEASIBILITY_PASS if not failures else MARGIN_FEASIBILITY_BLOCKED
    return replace(
        base, status=status, failures=tuple(failures), margin_basis=MARGIN_BASIS_PER_SYMBOL,
        projected_additional_initial_margin_usd=_canon(additional_im),
        projected_total_initial_margin_usd=_canon(projected_total),
        safety_headroom_usd=_canon(headroom),
        remaining_available_balance_usd=_canon(remaining),
        margin_rate_source=PER_SYMBOL_LEVERAGE_RATE_SOURCE,
        per_symbol_initial_margin=tuple(breakdown))


# ---------------------------------------------------------------------------
# 5. Artifact builders + top-level orchestration (pure)
# ---------------------------------------------------------------------------

def build_market_evidence_artifact(
    *, trusted: TrustedInputsResult, market: MarketEvidenceResult,
    collection_epoch_ns: int, collected_at_utc: str, network_audit: Mapping[str, Any],
) -> dict[str, Any]:
    """Artifact A: the current public market evidence + per-action current sizing."""
    art: dict[str, Any] = {
        "schema": MARKET_EVIDENCE_SCHEMA, "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID, "collected_at_utc": collected_at_utc,
        "collection_epoch_ns": int(collection_epoch_ns),
        "canonical_bound_plan_fingerprint": trusted.canonical_bound_plan_fingerprint,
        "anchor_manifest_sha256": trusted.anchor_manifest_sha256,
        "review_artifact_sha256": trusted.review_artifact_sha256,
        "strategy_symbols_sha256": trusted.strategy_symbols_sha256,
        "market_evidence_status": market.status,
        "market_freshness_threshold_ms": market.market_freshness_threshold_ms,
        "market_freshness_oldest_age_ms": market.market_freshness_oldest_age_ms,
        "evaluated_symbol_count": market.evaluated_symbol_count,
        "fresh_symbol_count": market.fresh_symbol_count,
        "long_count": market.long_count, "short_count": market.short_count,
        "total_target_gross_notional_usd": market.total_target_gross_notional_usd,
        "total_rounded_gross_notional_usd": market.total_rounded_gross_notional_usd,
        "quantity_all_valid": market.quantity_all_valid,
        "current_actions": [a.to_dict() for a in market.actions],
        "market_blockers": list(market.blockers),
        "network_audit": dict(network_audit),
        **safe_safety_counters(),
    }
    art["credential_leak_check"] = _credential_leak_check(art)
    art["artifact_fingerprint"] = _fingerprint_excluding(art, "artifact_fingerprint")
    return art


def build_account_evidence_artifact(
    *, account: AccountEvidenceResult, collection_epoch_ns: int,
    collected_at_utc: str, network_audit: Mapping[str, Any],
) -> dict[str, Any]:
    """Artifact B: the authenticated Demo-only read-only account evidence (no secrets)."""
    art: dict[str, Any] = {
        "schema": ACCOUNT_EVIDENCE_SCHEMA, "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID, "collected_at_utc": collected_at_utc,
        "collection_epoch_ns": int(collection_epoch_ns),
        "account_evidence_status": account.status,
        "demo_environment_verified": account.demo_environment_verified,
        "live_environment_denied": account.live_environment_denied,
        "account_mode": account.account_mode, "margin_mode": account.margin_mode,
        "position_mode": account.position_mode,
        "account_equity_usd": account.account_equity_usd,
        "available_balance_usd": account.available_balance_usd,
        "existing_initial_margin_usd": account.existing_initial_margin_usd,
        "existing_maintenance_margin_usd": account.existing_maintenance_margin_usd,
        "open_position_count": account.open_position_count,
        "protected_positions": list(account.protected_positions),
        "historical_protected_anchor": list(account.historical_protected_anchor),
        "strategy_position_overlaps": list(account.strategy_position_overlaps),
        "applicable_initial_margin_rate": account.applicable_initial_margin_rate,
        "margin_rate_source": account.margin_rate_source,
        "account_im_rate_context": account.account_im_rate_context,
        "account_freshness_age_ms": account.account_freshness_age_ms,
        # TASK-014CH4A_FIX2: per-symbol Source-A configured-leverage evidence (replayable).
        "target_leverage_evidence_status": account.target_leverage_evidence_status,
        "target_configured_leverage_by_symbol":
            dict(sorted(account.target_configured_leverage_by_symbol.items())),
        "target_leverage_missing_symbols": list(account.target_leverage_missing_symbols),
        "account_blockers": list(account.blockers),
        "network_audit": dict(network_audit),
        **safe_safety_counters(),
    }
    art["credential_leak_check"] = _credential_leak_check(art)
    art["artifact_fingerprint"] = _fingerprint_excluding(art, "artifact_fingerprint")
    return art


@dataclass(frozen=True)
class CurrentFeasibilityResult:
    status: str
    blockers: tuple[str, ...]
    review_artifact: Mapping[str, Any] | None
    market_evidence_artifact: Mapping[str, Any] | None
    account_evidence_artifact: Mapping[str, Any] | None
    margin: MarginFeasibilityResult | None

    @property
    def passed(self) -> bool:
        return self.status == CURRENT_FEASIBILITY_PASS


def build_current_feasibility_review(
    *,
    trusted: TrustedInputsResult,
    market: MarketEvidenceResult,
    account: AccountEvidenceResult,
    margin: MarginFeasibilityResult,
    collection_epoch_ns: int,
    reviewed_at_utc: str,
    network_audit: Mapping[str, Any],
    market_evidence_artifact_sha256: str | None = None,
    account_evidence_artifact_sha256: str | None = None,
) -> CurrentFeasibilityResult:
    """Assemble the terminal CH4A feasibility review (artifact C). Determines the single
    top-level status from the trusted-input / market / account / margin sub-results.
    Execution readiness is ALWAYS False, even on PASS."""
    blockers: list[str] = []

    if not network_audit_is_read_only(network_audit):
        blockers.append("network_audit_not_read_only")

    # Precedence: input -> market -> account -> margin.
    if not trusted.ok:
        status = CURRENT_FEASIBILITY_INPUT_INVALID
        blockers.extend(trusted.blockers)
    elif not market.ok:
        status = CURRENT_FEASIBILITY_MARKET_EVIDENCE_FAILED
        blockers.extend(market.blockers)
        blockers.extend(
            f"{a.symbol}:{c}" for a in market.actions
            for c in a.quantity_validation_failures)
    elif account.status == ACCOUNT_EVIDENCE_BLOCKED:
        status = CURRENT_FEASIBILITY_ACCOUNT_EVIDENCE_FAILED
        blockers.extend(account.blockers)
    elif account.status == ACCOUNT_EVIDENCE_UNAVAILABLE:
        status = CURRENT_FEASIBILITY_UNAVAILABLE
        blockers.extend(account.blockers)
    elif margin.status == MARGIN_FEASIBILITY_UNAVAILABLE:
        status = CURRENT_FEASIBILITY_UNAVAILABLE
        blockers.extend(f"margin:{f}" for f in margin.failures)
    elif margin.status == MARGIN_FEASIBILITY_BLOCKED:
        status = CURRENT_FEASIBILITY_BLOCKED
        blockers.extend(f"margin:{f}" for f in margin.failures)
    else:
        status = CURRENT_FEASIBILITY_PASS

    # A read-only-audit breach can never be PASS.
    if "network_audit_not_read_only" in blockers and status == CURRENT_FEASIBILITY_PASS:
        status = CURRENT_FEASIBILITY_BLOCKED

    review: dict[str, Any] = {
        "schema": FEASIBILITY_REVIEW_SCHEMA, "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID, "reviewed_at_utc": reviewed_at_utc,
        "collection_epoch_ns": int(collection_epoch_ns),
        "status": status,
        "blockers": list(dict.fromkeys(blockers)),
        # --- Trusted CH3C2 lineage anchors (read-only) ---
        "canonical_bound_plan_fingerprint": trusted.canonical_bound_plan_fingerprint,
        "anchor_manifest_sha256": trusted.anchor_manifest_sha256,
        "review_artifact_sha256": trusted.review_artifact_sha256,
        "strategy_symbols_sha256": trusted.strategy_symbols_sha256,
        "run_date": trusted.run_date,
        # --- Evidence artifact anchors (A/B) ---
        "market_evidence_artifact_sha256": market_evidence_artifact_sha256,
        "account_evidence_artifact_sha256": account_evidence_artifact_sha256,
        # --- Current market revalidation ---
        "current_market_freshness_status": market.status,
        "current_market_freshness_checked": True,
        "market_freshness_threshold_ms": market.market_freshness_threshold_ms,
        "evaluated_symbol_count": market.evaluated_symbol_count,
        "long_count": market.long_count, "short_count": market.short_count,
        "total_target_gross_notional_usd": market.total_target_gross_notional_usd,
        "total_rounded_gross_notional_usd": market.total_rounded_gross_notional_usd,
        "quantity_all_valid": market.quantity_all_valid,
        # --- Demo account feasibility ---
        "account_evidence_status": account.status,
        "demo_environment_verified": account.demo_environment_verified,
        "live_environment_denied": account.live_environment_denied,
        "position_mode": account.position_mode,
        "protected_positions": list(account.protected_positions),
        "historical_protected_anchor": list(account.historical_protected_anchor),
        "strategy_position_overlaps": list(account.strategy_position_overlaps),
        "account_im_rate_context": account.account_im_rate_context,
        # --- Margin feasibility ---
        "account_margin_feasibility_status": margin.status,
        "account_equity_usd": margin.account_equity_usd,
        "available_balance_usd": margin.available_balance_usd,
        "existing_initial_margin_usd": margin.existing_initial_margin_usd,
        "projected_additional_initial_margin_usd": margin.projected_additional_initial_margin_usd,
        "projected_total_initial_margin_usd": margin.projected_total_initial_margin_usd,
        "estimated_fees_buffer_usd": margin.estimated_fees_buffer_usd,
        "safety_headroom_usd": margin.safety_headroom_usd,
        "remaining_available_balance_usd": margin.remaining_available_balance_usd,
        "margin_rate_source": margin.margin_rate_source,
        "conservative_1x_envelope_usd": margin.conservative_1x_envelope_usd,
        "conservative_1x_envelope_label": margin.conservative_1x_envelope_label,
        # TASK-014CH4A_FIX2: per-symbol Source-A projection basis + breakdown (replayable).
        "margin_basis": margin.margin_basis,
        "target_leverage_evidence_status": account.target_leverage_evidence_status,
        "target_leverage_missing_symbols": list(account.target_leverage_missing_symbols),
        "per_symbol_initial_margin": [dict(r) for r in margin.per_symbol_initial_margin],
        "margin_feasibility_failures": list(margin.failures),
        # --- Network audit + terminal safety posture ---
        "network_audit": dict(network_audit),
        **safe_safety_counters(),
    }
    review["credential_leak_check"] = _credential_leak_check(review)
    review["artifact_fingerprint"] = _fingerprint_excluding(review, "artifact_fingerprint")
    return CurrentFeasibilityResult(
        status=status, blockers=tuple(review["blockers"]), review_artifact=review,
        market_evidence_artifact=None, account_evidence_artifact=None, margin=margin)


BUNDLE_COMPLETE = "BUNDLE_COMPLETE"
BUNDLE_INCOMPLETE = "BUNDLE_INCOMPLETE"


def build_cli_summary(
    *, feasibility: CurrentFeasibilityResult, trusted: TrustedInputsResult,
    market: MarketEvidenceResult, account: AccountEvidenceResult,
    network_audit: Mapping[str, Any], review_artifact_sha256: str | None,
    market_artifact_sha256: str | None, account_artifact_sha256: str | None,
    bundle_publication_status: str = BUNDLE_INCOMPLETE,
    published_artifacts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Artifact D: the short, operator-facing CLI summary JSON.

    The four artifacts are individually atomic (no-clobber), NOT bundle-atomic.
    ``bundle_publication_status`` is ``BUNDLE_COMPLETE`` ONLY when the other three files
    were published AND verified (file exists, on-disk SHA matches the recorded SHA);
    a partial publication reports ``BUNDLE_INCOMPLETE`` and never claims success."""
    return {
        "schema": "demo_strategy_native_current_feasibility_summary",
        "schema_version": SCHEMA_VERSION, "task_id": TASK_ID,
        "status": feasibility.status,
        "current_market_freshness_status": market.status,
        "account_evidence_status": account.status,
        "account_margin_feasibility_status": (
            feasibility.margin.status if feasibility.margin else MARGIN_FEASIBILITY_UNAVAILABLE),
        "canonical_bound_plan_fingerprint": trusted.canonical_bound_plan_fingerprint,
        "feasibility_review_artifact_sha256": review_artifact_sha256,
        "market_evidence_artifact_sha256": market_artifact_sha256,
        "account_evidence_artifact_sha256": account_artifact_sha256,
        "bundle_publication_status": bundle_publication_status,
        "published_artifacts": dict(published_artifacts or {}),
        "long_count": market.long_count, "short_count": market.short_count,
        "total_target_gross_notional_usd": market.total_target_gross_notional_usd,
        "network_audit": dict(network_audit),
        **safe_safety_counters(),
    }


__all__ = [
    "TASK_ID", "MARKET_EVIDENCE_SCHEMA", "ACCOUNT_EVIDENCE_SCHEMA",
    "FEASIBILITY_REVIEW_SCHEMA", "SCHEMA_VERSION",
    "EXPECTED_POLICY_ID", "EXPECTED_STRATEGY_ID", "EXPECTED_STRATEGY_SYMBOL_COUNT",
    "EXPECTED_LONG_COUNT", "EXPECTED_SHORT_COUNT", "V1_GROSS_USD",
    "DEFAULT_MARKET_FRESHNESS_THRESHOLD_MS", "DEFAULT_ACCOUNT_FRESHNESS_THRESHOLD_MS",
    "DEFAULT_SAFETY_HEADROOM_FRACTION", "DEFAULT_FEES_BUFFER_USD",
    "CURRENT_FEASIBILITY_PASS", "CURRENT_FEASIBILITY_BLOCKED",
    "CURRENT_FEASIBILITY_UNAVAILABLE", "CURRENT_FEASIBILITY_INPUT_INVALID",
    "CURRENT_FEASIBILITY_MARKET_EVIDENCE_FAILED", "CURRENT_FEASIBILITY_ACCOUNT_EVIDENCE_FAILED",
    "MARKET_EVIDENCE_FRESH", "MARKET_EVIDENCE_STALE", "MARKET_EVIDENCE_INCOMPLETE",
    "ACCOUNT_EVIDENCE_OK", "ACCOUNT_EVIDENCE_UNAVAILABLE", "ACCOUNT_EVIDENCE_BLOCKED",
    "MARGIN_FEASIBILITY_PASS", "MARGIN_FEASIBILITY_BLOCKED", "MARGIN_FEASIBILITY_UNAVAILABLE",
    "LEVERAGE_EVIDENCE_OK", "LEVERAGE_EVIDENCE_UNAVAILABLE", "LEVERAGE_EVIDENCE_NOT_SUPPLIED",
    "PER_SYMBOL_LEVERAGE_RATE_SOURCE", "MARGIN_BASIS_PER_SYMBOL", "MARGIN_BASIS_SINGLE_RATE",
    "MARGIN_BASIS_UNAVAILABLE",
    "BUNDLE_COMPLETE", "BUNDLE_INCOMPLETE",
    "CurrentTarget", "TrustedInputsResult", "CurrentActionFeasibility",
    "MarketEvidenceResult", "AccountEvidenceResult", "MarginFeasibilityResult",
    "CurrentFeasibilityResult",
    "validate_trusted_inputs", "evaluate_current_market_and_quantities",
    "evaluate_demo_account_evidence", "evaluate_margin_feasibility",
    "build_market_evidence_artifact", "build_account_evidence_artifact",
    "build_current_feasibility_review", "build_cli_summary",
    "zeroed_network_audit", "network_audit_is_read_only", "safe_safety_counters",
]
