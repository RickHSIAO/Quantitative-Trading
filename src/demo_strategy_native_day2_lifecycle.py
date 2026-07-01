"""TASK-014BY: READ-ONLY Day-2 strategy-position lifecycle reconciliation + dry-run plan.

PURE, read-only analysis. It NEVER sends/closes/cancels/amends/resizes/opens anything, never
advances the Pilot, never writes a batch_attempt, never initializes a sender, and never calls
execute_daily_native. It only classifies, per symbol, what the FORMAL strategy reconciliation
would do on Day 2, and emits a machine-readable dry-run plan.

PROVENANCE (no forgeable READY):

  * The authoritative Day-2 target is the PRODUCTION recompute -- the formal Forward per-date
    call chain (``load_primary_forward_strategy_result`` -> ``plan_strategy_native_actions``).
    A self-sealed/hand-built target artifact carries only integrity, NOT provenance: it is
    accepted ONLY when it EXACTLY matches the production recompute (every symbol/side/notional/
    qty/qty_step), its ``source_identifier`` is the canonical strategy name, its ``signal_date``
    equals the production effective date, and the source-artifact SHA-256 set matches.
  * The lifecycle policy must be a recognized canonical ID (never a free-text CLI string).
  * Day-1 evidence is MANDATORY and re-derived: the Day-1 allocation-intent fingerprint is
    RECOMPUTED from ``order_payloads`` with the production fingerprint function and must equal the
    stored payload/allocation fingerprints, the Day-1 post-fill audit fingerprint, and the CLI
    fingerprint; the post-fill audit must re-validate as POST_FILL_AUDIT_PASS.
  * Only EDUUSDT may be an extra open symbol, proven by Day-1 protected evidence (side included);
    any other extra symbol -- including other canonical-protected names -- fails closed.

Durable identity uses Decimal canonical strings end-to-end (no float round-trip). REVERSE is split
into two un-executed phases (reduce-only close, then open opposite only after the close
reconciles) with DISTINCT close/open batch identities. Any gap, mismatch, missing evidence field,
incomplete pagination, or non-zero mutating request yields DAY2_LIFECYCLE_DRY_RUN_BLOCKED.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

from src import demo_strategy_native_postfill_audit as au
from src import demo_strategy_pilot_action_planner as planner
from src import demo_strategy_pilot_forward_source as fs
from src import demo_strategy_pilot_native_execution as nx

# Verdicts
DRY_RUN_READY = "DAY2_LIFECYCLE_DRY_RUN_READY"
DRY_RUN_BLOCKED = "DAY2_LIFECYCLE_DRY_RUN_BLOCKED"

SCHEMA_VERSION = "demo_strategy_native_day2_lifecycle_dry_run_v2"
# v2 separates the IMMUTABLE target intent (symbol/side/notional only) from the volatile runtime
# sizing translation (price/qty/qty_step). v1 artifacts are NEVER silently upgraded (see ADR).
TARGET_SCHEMA_VERSION = "demo_strategy_native_day2_target_intent_v2"
TARGET_SCHEMA_VERSION_V1 = "demo_strategy_native_day2_target_intent_v1"
ENVIRONMENT_DEMO = "BYBIT_DEMO"
STRATEGY_CAPITAL_BASE_USD = "10000"
COMPLETE_PAGINATION_TERMINATION = "empty_cursor"
TARGET_DIGEST_FIELD = "target_digest"
TARGET_FINGERPRINT_FIELD = "target_intent_fingerprint"
RUNTIME_FINGERPRINT_FIELD = "runtime_translation_fingerprint"

EXPECTED_STRATEGY_SYMBOLS = 50
EXPECTED_SIDE_COUNT = 25
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

LIFECYCLE_POLICY_FORWARD_RECONCILE = "FORWARD_RECORD_PER_DATE_RECONCILE"
RECOGNIZED_LIFECYCLE_POLICIES = frozenset({LIFECYCLE_POLICY_FORWARD_RECONCILE})
# The ONLY canonical strategy source identifier (the production Forward strategy identity).
RECOGNIZED_STRATEGY_SOURCES = frozenset({fs.EXPECTED_STRATEGY_NAME})
# The only symbol allowed to be open beyond the 50 Day-1 strategy positions.
ALLOWED_EXTRA_OPEN_SYMBOL = "EDUUSDT"

ACTION_HOLD = "HOLD"
ACTION_CLOSE = "CLOSE"
ACTION_OPEN = "OPEN"
ACTION_REVERSE = "REVERSE"
ACTION_INCREASE = "INCREASE"
ACTION_DECREASE = "DECREASE"
ACTION_PROTECTED_UNTOUCHED = "PROTECTED_UNTOUCHED"
ACTION_BLOCKED = "BLOCKED"

PROTECTED_SYMBOLS = frozenset(nx.PROTECTED_SYMBOLS)

_REASON_TO_ACTION = {
    "target_exit": ACTION_CLOSE, "target_open": ACTION_OPEN,
    "target_add": ACTION_INCREASE, "target_reduce": ACTION_DECREASE,
}

_REQUIRED_POSITION_FIELDS = ("position_idx", "entry_price", "mark_price", "unrealized_pnl")

# Exactly these four Forward source artifact roles must be present (each {path, sha256}).
REQUIRED_SOURCE_ROLES = ("positions", "forward_stats", "pnl", "forward_summary")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
# Every network component must report these three counters (no partial accounting).
_REQUIRED_COUNTER_KEYS = ("private_read_only_request_count", "public_read_only_request_count",
                          "private_mutating_request_count")


def merge_network_counters(
    components: Mapping[str, Any],
) -> tuple[dict[str, int], list[str], dict[str, Any]]:
    """Merge the transport counters of EVERY network component into one audit. Each named
    component must supply all three counters (a missing/None component -> unaccounted -> blocker,
    never silently skipped). Returns (merged_counts, blockers, per_component_breakdown)."""
    blockers: list[str] = []
    merged = {k: 0 for k in _REQUIRED_COUNTER_KEYS}
    breakdown: dict[str, Any] = {}
    for name, counters in components.items():
        if not isinstance(counters, Mapping) or any(
                _as_int(counters.get(k)) is None for k in _REQUIRED_COUNTER_KEYS):
            blockers.append(f"unaccounted_network_component:{name}")
            breakdown[name] = None
            continue
        comp = {k: _as_int(counters.get(k)) for k in _REQUIRED_COUNTER_KEYS}
        breakdown[name] = comp
        for k in _REQUIRED_COUNTER_KEYS:
            merged[k] += comp[k]
    if merged["private_mutating_request_count"] != 0:
        blockers.append(f"private_mutating_requests_detected:{merged['private_mutating_request_count']}")
    if not blockers and merged["private_read_only_request_count"] < 1:
        blockers.append("no_private_read_only_request_recorded")
    return merged, blockers, breakdown


def _validate_source_artifacts(sources: Any, prefix: str) -> list[str]:
    """Require EXACTLY the four canonical roles, each a {path, sha256} object with a non-empty path
    and a well-formed sha256. Missing/extra role, or malformed hash, fails closed."""
    reasons: list[str] = []
    if not isinstance(sources, Mapping):
        return [f"{prefix}_source_artifacts_not_object"]
    roles = set(sources)
    if roles != set(REQUIRED_SOURCE_ROLES):
        missing = sorted(set(REQUIRED_SOURCE_ROLES) - roles)
        extra = sorted(roles - set(REQUIRED_SOURCE_ROLES))
        if missing:
            reasons.append(f"{prefix}_source_artifact_role_missing:{missing}")
        if extra:
            reasons.append(f"{prefix}_source_artifact_role_unexpected:{extra}")
    for role in REQUIRED_SOURCE_ROLES:
        entry = sources.get(role)
        if not isinstance(entry, Mapping):
            reasons.append(f"{prefix}_source_artifact_malformed:{role}")
            continue
        if not str(entry.get("path", "")).strip():
            reasons.append(f"{prefix}_source_artifact_path_missing:{role}")
        if not _SHA256_RE.match(str(entry.get("sha256", ""))):
            reasons.append(f"{prefix}_source_artifact_hash_invalid:{role}")
    return reasons


# --------------------------------------------------------------------------- decimal helpers
def _dec(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _canon(v: Any) -> str | None:
    d = _dec(v)
    if d is None:
        return None
    d = d.normalize()
    return format(d if d != 0 else Decimal(0), "f")


def _mul(qty: Any, price: Any) -> str | None:
    q, p = _dec(qty), _dec(price)
    if q is None or p is None or p <= 0:
        return None
    return _canon(q * p)


def _as_int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _norm_long_short(side: Any) -> str:
    s = str(side or "").strip().lower()
    if s in ("buy", "long"):
        return "long"
    if s in ("sell", "short"):
        return "short"
    return ""


def _display_side(long_short: str) -> str:
    return "Buy" if long_short == "long" else ("Sell" if long_short == "short" else "")


def _valid_date(s: Any) -> bool:
    return bool(_DATE_RE.match(str(s or "")))


def _digest(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                   default=str).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- target artifact
def _canon_intent_allocations(intent_allocations: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Canonical IMMUTABLE intent view: symbol / side / target_notional_usd ONLY. Deliberately
    excludes price / qty / qty_step (those are volatile runtime translation, not intent)."""
    out = []
    for a in intent_allocations:
        out.append({
            "symbol": str(a.get("symbol", "")).strip().upper(),
            "side": _norm_long_short(a.get("side")),
            "target_notional_usd": _canon(a.get("target_notional_usd")) or "",
        })
    return sorted(out, key=lambda d: d["symbol"])


def target_intent_fingerprint(*, pilot_id: str, lifecycle_date: str, signal_date: str,
                              source_identifier: str,
                              intent_allocations: Sequence[Mapping[str, Any]]) -> str:
    """Immutable Day-2 target-intent fingerprint. Binds ONLY pilot/date/signal/capital/source and
    the per-symbol side + quote-notional -- NEVER price, qty, qty_step, mark price, runtime
    timestamp, current positions, or network counters. So a price/qty/qty_step change between
    when the intent was sealed and when it is executed does NOT change this fingerprint."""
    return _digest({
        "kind": "day2_target_intent_v2", "pilot_id": str(pilot_id),
        "lifecycle_date": str(lifecycle_date), "signal_date": str(signal_date),
        "strategy_capital_base_usd": STRATEGY_CAPITAL_BASE_USD,
        "source_identifier": str(source_identifier),
        "intent_allocations": _canon_intent_allocations(intent_allocations)})


def _canon_runtime_translation(runtime: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    out = []
    for r in runtime:
        out.append({
            "symbol": str(r.get("symbol", "")).strip().upper(),
            "side": _norm_long_short(r.get("side")),
            "target_notional_usd": _canon(r.get("target_notional_usd")) or "",
            "price_snapshot": _canon(r.get("price_snapshot")) or "",
            "qty_step": _canon(r.get("qty_step")) or "",
            "qty": _canon(r.get("qty")) or "",
        })
    return sorted(out, key=lambda d: d["symbol"])


def runtime_translation_fingerprint(*, pilot_id: str, lifecycle_date: str, signal_date: str,
                                    target_intent_fingerprint: str,
                                    runtime_translation: Sequence[Mapping[str, Any]]) -> str:
    """Volatile runtime sizing-translation fingerprint. Binds the intent fingerprint plus the
    per-symbol price_snapshot / qty_step / qty of THIS run, so it CHANGES whenever price or qty
    changes -- the opposite of the immutable intent fingerprint."""
    return _digest({
        "kind": "day2_runtime_translation", "pilot_id": str(pilot_id),
        "lifecycle_date": str(lifecycle_date), "signal_date": str(signal_date),
        "target_intent_fingerprint": str(target_intent_fingerprint),
        "runtime_translation": _canon_runtime_translation(runtime_translation)})


def canonical_target_digest(artifact: Mapping[str, Any]) -> str:
    return _digest({k: v for k, v in artifact.items() if k != TARGET_DIGEST_FIELD})


def seal_target_intent_artifact(*, pilot_id: str, lifecycle_date: str, signal_date: str,
                                source_identifier: str, source_artifacts: Mapping[str, str],
                                intent_allocations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build the IMMUTABLE Day-2 target-intent artifact (v2). It carries ONLY the intent view
    (symbol/side/target_notional_usd) -- never price/qty/qty_step. Integrity only; provenance is
    established later by exact intent-match against the current production recompute."""
    art = {
        "schema_version": TARGET_SCHEMA_VERSION, "pilot_id": pilot_id,
        "lifecycle_date": lifecycle_date, "signal_date": signal_date,
        "strategy_capital_base_usd": STRATEGY_CAPITAL_BASE_USD,
        "source_identifier": source_identifier,
        "source_artifacts": {str(k): dict(v) if isinstance(v, Mapping) else v
                             for k, v in dict(source_artifacts).items()},
        "intent_allocations": [dict(a) for a in intent_allocations],
    }
    art[TARGET_FINGERPRINT_FIELD] = target_intent_fingerprint(
        pilot_id=pilot_id, lifecycle_date=lifecycle_date, signal_date=signal_date,
        source_identifier=source_identifier, intent_allocations=intent_allocations)
    art[TARGET_DIGEST_FIELD] = canonical_target_digest(art)
    return art


def _validate_target_intent_integrity(artifact: Any, *, pilot_id: str, lifecycle_date: str) -> list[str]:
    """Validate a sealed IMMUTABLE v2 target-intent artifact. A v1 (or any non-v2) artifact is
    explicitly REJECTED (never silently upgraded)."""
    reasons: list[str] = []
    if not isinstance(artifact, Mapping):
        return ["target_artifact_not_object"]
    schema = artifact.get("schema_version")
    if schema != TARGET_SCHEMA_VERSION:
        reasons.append(f"unsupported_target_intent_schema_version:{schema}")
        return reasons   # never inspect a non-v2 artifact further
    if str(artifact.get("pilot_id", "")) != str(pilot_id):
        reasons.append("target_pilot_id_mismatch")
    if str(artifact.get("lifecycle_date", "")) != str(lifecycle_date):
        reasons.append("target_lifecycle_date_mismatch")
    if str(artifact.get("strategy_capital_base_usd", "")) != STRATEGY_CAPITAL_BASE_USD:
        reasons.append("target_capital_base_not_10000")
    if not _valid_date(artifact.get("signal_date")):
        reasons.append("target_signal_date_invalid")
    if "allocations" in artifact and "intent_allocations" not in artifact:
        reasons.append("legacy_allocations_field_present")   # v1 qty-bearing field is not honoured
    intent = artifact.get("intent_allocations")
    if not isinstance(intent, list) or not intent:
        reasons.append("target_intent_allocations_missing")
        intent = []
    recomputed_fp = target_intent_fingerprint(
        pilot_id=str(artifact.get("pilot_id", "")),
        lifecycle_date=str(artifact.get("lifecycle_date", "")),
        signal_date=str(artifact.get("signal_date", "")),
        source_identifier=str(artifact.get("source_identifier", "")), intent_allocations=intent)
    if str(artifact.get(TARGET_FINGERPRINT_FIELD, "")) != recomputed_fp:
        reasons.append("target_fingerprint_mismatch")
    stored_digest = artifact.get(TARGET_DIGEST_FIELD)
    if not stored_digest:
        reasons.append("target_digest_missing")
    elif canonical_target_digest(artifact) != str(stored_digest):
        reasons.append("target_digest_mismatch")
    return reasons


def _validate_intent_allocations(intent_allocations: Any, prefix: str
                                 ) -> tuple[list[str], dict[str, dict[str, str]]]:
    """Validate the IMMUTABLE intent view: unique symbol, side in {long, short}, finite-positive
    target_notional_usd. NO qty/qty_step here (those belong to the runtime translation)."""
    reasons: list[str] = []
    if not isinstance(intent_allocations, list) or not intent_allocations:
        return [f"{prefix}_intent_allocations_missing"], {}
    amap: dict[str, dict[str, str]] = {}
    for a in intent_allocations:
        if not isinstance(a, Mapping):
            reasons.append(f"{prefix}_intent_allocation_not_object")
            continue
        sym = str(a.get("symbol", "")).strip().upper()
        if not sym:
            reasons.append(f"{prefix}_intent_empty_symbol")
            continue
        if sym in amap:
            reasons.append(f"{prefix}_intent_duplicate_symbol:{sym}")
            continue
        side = _norm_long_short(a.get("side"))
        if side not in ("long", "short"):
            reasons.append(f"{prefix}_intent_invalid_side:{sym}")
        tn = _dec(a.get("target_notional_usd"))
        if tn is None or not tn.is_finite() or tn <= 0:
            reasons.append(f"{prefix}_intent_invalid_notional:{sym}")
        amap[sym] = {"symbol": sym, "side": side,
                     "target_notional_usd": _canon(tn) if tn is not None and tn.is_finite() else ""}
    return reasons, amap


def _validate_runtime_translation(runtime: Any, prefix: str
                                  ) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Validate the volatile runtime translation: unique symbol, side, and finite-positive
    target_notional_usd / price_snapshot / qty_step / qty (NaN / Infinity / <= 0 rejected)."""
    reasons: list[str] = []
    if not isinstance(runtime, list) or not runtime:
        return [f"{prefix}_runtime_translation_missing"], {}
    rmap: dict[str, dict[str, Any]] = {}
    for r in runtime:
        if not isinstance(r, Mapping):
            reasons.append(f"{prefix}_runtime_row_not_object")
            continue
        sym = str(r.get("symbol", "")).strip().upper()
        if not sym:
            reasons.append(f"{prefix}_runtime_empty_symbol")
            continue
        if sym in rmap:
            reasons.append(f"{prefix}_runtime_duplicate_symbol:{sym}")
            continue
        side = _norm_long_short(r.get("side"))
        if side not in ("long", "short"):
            reasons.append(f"{prefix}_runtime_invalid_side:{sym}")
        vals = {}
        for field in ("target_notional_usd", "price_snapshot", "qty_step", "qty"):
            d = _dec(r.get(field))
            if d is None or not d.is_finite() or d <= 0:
                reasons.append(f"{prefix}_runtime_invalid_{field}:{sym}")
                vals[field] = None
            else:
                vals[field] = d
        # ENFORCE the runtime sizing arithmetic EXACTLY (only once all four are finite-positive):
        #   expected_qty = floor(target_notional_usd / price_snapshot / qty_step) * qty_step
        # Pure Decimal, NO tolerance / epsilon / isclose / nearest-round: the runtime qty must be
        # EXACTLY on the qty_step grid AND its canonical Decimal value must EXACTLY equal
        # expected_qty. An off-grid value (e.g. 1.454 on a 0.01 step) fails -- it is not rounded
        # to the nearest step before comparison. Direction stays in ``side`` (notional is the
        # positive magnitude). The resolver writes canonical step-grid qty so float representation
        # noise from the planner never reaches this exact comparison.
        if all(vals[f] is not None for f in ("target_notional_usd", "price_snapshot",
                                             "qty_step", "qty")):
            step, qty = vals["qty_step"], vals["qty"]
            exp_steps = (vals["target_notional_usd"] / vals["price_snapshot"]
                         / step).to_integral_value(rounding=ROUND_DOWN)
            expected_qty = exp_steps * step
            q_over_step = qty / step
            if q_over_step != q_over_step.to_integral_value(rounding=ROUND_DOWN):
                reasons.append(f"{prefix}_runtime_qty_not_on_step_grid:{sym}")
            if exp_steps <= 0 or qty != expected_qty:
                reasons.append(f"{prefix}_runtime_qty_rounding_mismatch:{sym}")
        rmap[sym] = {"symbol": sym, "side": side,
                     "target_notional_usd": _canon(vals["target_notional_usd"]) if vals["target_notional_usd"] is not None else "",
                     "price_snapshot": _canon(vals["price_snapshot"]) if vals["price_snapshot"] is not None else "",
                     "qty_step": vals["qty_step"], "qty": vals["qty"]}
    return reasons, rmap


def verify_production_target_provenance(
    *, sealed_target: Any, production_recompute: Any, pilot_id: str, lifecycle_date: str,
) -> tuple[bool, list[str], dict[str, dict[str, Any]], str, str]:
    """Establish PROVENANCE for the Day-2 target (v2 intent / runtime separation).

    The immutable INTENT (symbol/side/notional) is exact-matched between the sealed v2 artifact and
    the current production recompute, together with strategy / dates / source-artifact hashes. The
    volatile qty / qty_step / price are NOT compared across time; the runtime sizing used by the
    lifecycle comes ONLY from THIS run's production ``runtime_translation`` (the sealed artifact
    carries no qty). Returns (ok, reasons, target_by_symbol, signal_date, runtime_translation_fp)."""
    reasons: list[str] = []
    if not isinstance(production_recompute, Mapping) or \
            not production_recompute.get("intent_allocations") or \
            not production_recompute.get("runtime_translation"):
        return False, ["no_production_forward_target_recompute"], {}, "", ""

    prod_strategy = str(production_recompute.get("strategy", ""))
    prod_signal = str(production_recompute.get("signal_date", ""))
    prod_run_date = str(production_recompute.get("requested_run_date", ""))
    prod_loader = str(production_recompute.get("loader_validation", ""))
    prod_sources = production_recompute.get("source_artifacts") or {}

    if prod_strategy not in RECOGNIZED_STRATEGY_SOURCES:
        reasons.append(f"production_strategy_not_canonical:{prod_strategy}")
    if prod_run_date != str(lifecycle_date):
        reasons.append("production_requested_run_date_mismatch")
    if not _valid_date(prod_signal):
        reasons.append("production_signal_date_invalid")
    elif prod_signal > str(lifecycle_date):
        reasons.append("production_signal_date_in_future")
    if prod_loader != "PASS":
        reasons.append(f"production_loader_validation_not_pass:{prod_loader or 'ABSENT'}")
    reasons.extend(_validate_source_artifacts(prod_sources, "production"))

    prod_intent_reasons, prod_intent = _validate_intent_allocations(
        production_recompute.get("intent_allocations"), "production_target")
    reasons.extend(prod_intent_reasons)
    prod_rt_reasons, prod_runtime = _validate_runtime_translation(
        production_recompute.get("runtime_translation"), "production_target")
    reasons.extend(prod_rt_reasons)

    # Sealed IMMUTABLE v2 intent integrity + canonical identity (v1 is rejected inside).
    reasons.extend(_validate_target_intent_integrity(sealed_target, pilot_id=pilot_id,
                                                     lifecycle_date=lifecycle_date))
    sealed = sealed_target if isinstance(sealed_target, Mapping) else {}
    sealed_is_v2 = sealed.get("schema_version") == TARGET_SCHEMA_VERSION
    sealed_intent_reasons, sealed_intent = _validate_intent_allocations(
        sealed.get("intent_allocations"), "sealed_target")
    if sealed_is_v2:
        reasons.extend(sealed_intent_reasons)
    if str(sealed.get("source_identifier", "")) not in RECOGNIZED_STRATEGY_SOURCES:
        reasons.append("sealed_source_identifier_not_canonical")
    if str(sealed.get("source_identifier", "")) != prod_strategy:
        reasons.append("sealed_strategy_mismatch_production")
    if str(sealed.get("signal_date", "")) != prod_signal:
        reasons.append("sealed_signal_date_mismatch_production")
    sealed_sources = sealed.get("source_artifacts") or {}
    sealed_source_reasons = _validate_source_artifacts(sealed_sources, "sealed")
    reasons.extend(sealed_source_reasons)
    if not sealed_source_reasons and set(prod_sources) == set(REQUIRED_SOURCE_ROLES):
        if set(sealed_sources) != set(prod_sources):
            reasons.append("source_artifact_role_set_mismatch")
        for role in REQUIRED_SOURCE_ROLES:
            s = (sealed_sources.get(role) or {}) if isinstance(sealed_sources.get(role), Mapping) else {}
            p = (prod_sources.get(role) or {}) if isinstance(prod_sources.get(role), Mapping) else {}
            if str(s.get("sha256", "")) != str(p.get("sha256", "")):
                reasons.append(f"source_artifact_hash_mismatch:{role}")

    # EXACT INTENT match (symbol set + side + notional) -- NOT qty/qty_step/price.
    if sealed_is_v2 and not sealed_intent_reasons and not prod_intent_reasons:
        if set(sealed_intent) != set(prod_intent):
            reasons.append("target_symbol_set_mismatch_production")
        for sym in sorted(set(sealed_intent) & set(prod_intent)):
            s, p = sealed_intent[sym], prod_intent[sym]
            for field in ("side", "target_notional_usd"):
                if s.get(field) != p.get(field):
                    reasons.append(f"target_{field}_mismatch_production:{sym}")

    # The runtime translation must faithfully translate the SAME production intent (side/notional)
    # for the SAME symbol set -- so no runtime row can smuggle a different symbol/side/notional.
    if not prod_intent_reasons and not prod_rt_reasons:
        if set(prod_runtime) != set(prod_intent):
            reasons.append("runtime_symbol_set_mismatch_intent")
        for sym in sorted(set(prod_runtime) & set(prod_intent)):
            if prod_runtime[sym]["side"] != prod_intent[sym]["side"]:
                reasons.append(f"runtime_side_mismatch_intent:{sym}")
            if prod_runtime[sym]["target_notional_usd"] != prod_intent[sym]["target_notional_usd"]:
                reasons.append(f"runtime_notional_mismatch_intent:{sym}")

    # Runtime sizing (qty/qty_step) comes ONLY from THIS run's production runtime_translation.
    target_by_symbol = {sym: {"symbol": sym, "side": r["side"],
                              "target_notional_usd": r["target_notional_usd"],
                              "qty": r["qty"], "qty_step": r["qty_step"]}
                        for sym, r in prod_runtime.items()}
    runtime_fp = runtime_translation_fingerprint(
        pilot_id=pilot_id, lifecycle_date=lifecycle_date, signal_date=prod_signal,
        target_intent_fingerprint=str(sealed.get(TARGET_FINGERPRINT_FIELD, "")),
        runtime_translation=production_recompute.get("runtime_translation") or [])
    return (not reasons), reasons, target_by_symbol, prod_signal, runtime_fp


# --------------------------------------------------------------------------- Day-1 evidence
_CRUN = None


def _crun():
    global _CRUN
    if _CRUN is None:
        import importlib.util
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "scripts", "run_demo_strategy_pilot_native_daily.py")
        spec = importlib.util.spec_from_file_location("_crun_day2_fp", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _CRUN = mod
    return _CRUN


_PIB = None


def _pib():
    """Lazy import of the protected-identity bootstrap (avoids an import cycle: that module imports
    ``merge_network_counters`` from here at module load time)."""
    global _PIB
    if _PIB is None:
        from src import demo_pilot_protected_identity_bootstrap as pib
        _PIB = pib
    return _PIB


def _recompute_day1_fingerprint(order_payloads, pilot_id, date) -> str:
    """Recompute the Day-1 allocation-intent fingerprint from order_payloads using the EXACT
    production canonical fingerprint function (no string trust)."""
    allocs = [{"symbol": p.get("symbol"), "side": p.get("side"),
               "target_notional_usd": p.get("target_notional_usd")} for p in order_payloads]
    return _crun().allocation_intent_fingerprint(
        allocs, pilot_id=pilot_id, date=date, strategy_capital_base_usd=STRATEGY_CAPITAL_BASE_USD)


def validate_day1_evidence(
    *, post_fill_audit: Any, allocation_intent: Any, pilot_id: str, day1_date: str,
    day1_fingerprint: str, fingerprint_recompute_fn=None,
) -> tuple[bool, list[str], dict[str, str]]:
    """Re-validate MANDATORY Day-1 evidence. The post-fill audit must re-validate as PASS, and the
    allocation-intent fingerprint is RECOMPUTED from order_payloads and must equal every stored /
    audit / CLI fingerprint. Returns (ok, reasons, day1_side_by_symbol)."""
    reasons: list[str] = []
    recompute = fingerprint_recompute_fn or _recompute_day1_fingerprint

    if not isinstance(post_fill_audit, Mapping):
        reasons.append("day1_audit_not_object")
    else:
        ok, au_reasons = au.validate_audit_artifact_for_advancement(
            post_fill_audit, pilot_id=pilot_id, date=day1_date, expected_fingerprint=day1_fingerprint)
        if not ok:
            reasons.extend(f"day1_audit:{r}" for r in au_reasons)
        summ = post_fill_audit.get("allocation_intent_summary") or {}
        if (_as_int(summ.get("expected_symbol_count")) != EXPECTED_STRATEGY_SYMBOLS
                or _as_int(summ.get("buy_count")) != EXPECTED_SIDE_COUNT
                or _as_int(summ.get("sell_count")) != EXPECTED_SIDE_COUNT):
            reasons.append("day1_audit_allocation_summary_not_50_25_25")

    day1_sides: dict[str, str] = {}
    if not isinstance(allocation_intent, Mapping):
        reasons.append("day1_allocation_intent_not_object")
        return (not reasons), reasons, day1_sides

    if str(allocation_intent.get("pilot_id", "")) != str(pilot_id):
        reasons.append("day1_allocation_pilot_id_mismatch")
    if str(allocation_intent.get("date", "")) != str(day1_date):
        reasons.append("day1_allocation_date_mismatch")
    payloads = allocation_intent.get("order_payloads") or []
    if not isinstance(payloads, list) or len(payloads) != EXPECTED_STRATEGY_SYMBOLS:
        reasons.append(f"day1_allocation_symbol_count_not_50:"
                       f"{len(payloads) if isinstance(payloads, list) else 'NA'}")
        payloads = payloads if isinstance(payloads, list) else []

    buys = sells = 0
    for p in payloads:
        if not isinstance(p, Mapping):
            continue
        sym = str(p.get("symbol", "")).strip().upper()
        side = str(p.get("side", "")).strip()
        if not sym or sym in day1_sides:
            reasons.append(f"day1_allocation_duplicate_or_empty_symbol:{sym or '?'}")
            continue
        if side == "Buy":
            buys += 1
        elif side == "Sell":
            sells += 1
        else:
            reasons.append(f"day1_allocation_invalid_side:{sym}")
        day1_sides[sym] = side
    if buys != EXPECTED_SIDE_COUNT or sells != EXPECTED_SIDE_COUNT:
        reasons.append(f"day1_allocation_side_distribution_not_25_25:{buys}/{sells}")

    # RECOMPUTE the Day-1 fingerprint from order_payloads -> must equal every stored fingerprint.
    try:
        recomputed_fp = recompute(payloads, pilot_id, day1_date)
    except Exception as exc:  # noqa: BLE001
        recomputed_fp = None
        reasons.append(f"day1_fingerprint_recompute_failed:{type(exc).__name__}")
    bound = {str(allocation_intent.get("payload_fingerprint", "")),
             str(allocation_intent.get("allocation_intent_fingerprint", "")),
             str(day1_fingerprint),
             str((post_fill_audit or {}).get("allocation_intent_fingerprint", ""))}
    if recomputed_fp is not None and (len(bound) != 1 or recomputed_fp not in bound):
        reasons.append("day1_fingerprint_recompute_mismatch")
    return (not reasons), reasons, day1_sides


# --------------------------------------------------------------------------- positions
def _enrich_position(p: Any) -> tuple[dict[str, Any], list[str]]:
    g = (lambda k, d=None: p.get(k, d)) if isinstance(p, Mapping) else (lambda k, d=None: getattr(p, k, d))
    sym = str(g("symbol", "")).strip().upper()
    side = _norm_long_short(g("side"))
    qty = _dec(g("size", g("quantity", g("qty"))))
    mark = _dec(g("mark_price", g("markPrice")))
    entry = _dec(g("entry_price", g("avgPrice", g("avg_price"))))
    upnl = _dec(g("unrealized_pnl", g("unrealised_pnl", g("unrealisedPnl"))))
    pidx = _as_int(g("position_idx", g("positionIdx")))
    row = {
        "symbol": sym, "side": side, "qty_dec": qty,
        "qty": _canon(qty) if qty is not None else None,
        "position_idx": pidx, "entry_price": _canon(entry), "mark_price": _canon(mark),
        "unrealized_pnl": _canon(upnl),
        "current_notional_usd": _mul(qty, mark) if (qty is not None and mark is not None) else None,
    }
    missing: list[str] = []
    if not sym:
        missing.append("symbol")
    if side not in ("long", "short"):
        missing.append("side")
    if qty is None or qty <= 0:
        missing.append("qty")
    if pidx is None:
        missing.append("position_idx")
    if row["entry_price"] is None:
        missing.append("entry_price")
    if row["mark_price"] is None:
        missing.append("mark_price")
    if row["unrealized_pnl"] is None:
        missing.append("unrealized_pnl")
    if row["current_notional_usd"] is None:
        missing.append("current_notional_usd")
    return row, missing


# --------------------------------------------------------------------------- classification
def _classify(target_by_symbol, current_by_symbol) -> dict[str, list[Any]]:
    targets_for_diff: dict[str, dict[str, Any]] = {}
    for sym, t in target_by_symbol.items():
        q = t.get("qty")
        step = _dec(t.get("qty_step"))
        targets_for_diff[sym] = {
            "symbol": sym, "side": t["side"],
            "qty": float(q) if q is not None else 0.0,   # adapter boundary only
            "qty_step": float(step) if step is not None else None,
            "target_notional": float(_dec(t.get("target_notional_usd")) or 0)}
    current_for_diff = {s: SimpleNamespace(symbol=s, side=r["side"], quantity=float(r["qty_dec"]))
                        for s, r in current_by_symbol.items()}
    diff_actions = planner._diff_positions(targets_for_diff, current_for_diff)
    by_symbol: dict[str, list[Any]] = defaultdict(list)
    for a in diff_actions:
        by_symbol[str(a.symbol).strip().upper()].append(a)
    return by_symbol


def _symbol_record(symbol, tgt, cur, acts) -> tuple[dict[str, Any], bool]:
    cur_side = _display_side(cur["side"]) if cur else ""
    cur_qty = cur["qty"] if cur else "0"
    mark = cur["mark_price"] if cur else None
    tgt_side = _display_side(tgt["side"]) if tgt else ""
    tgt_notional = str(tgt.get("target_notional_usd", "")) if tgt else ""
    base = dict(symbol=symbol, current_side=cur_side, current_qty=cur_qty,
                target_side=tgt_side, target_notional_usd=tgt_notional)
    miss = False

    if symbol in PROTECTED_SYMBOLS:
        return {**base, "proposed_action": ACTION_PROTECTED_UNTOUCHED,
                "proposed_reduce_only_qty": "0", "proposed_open_qty": "0",
                "close_notional_estimate_usd": "0", "open_notional_estimate_usd": "0",
                "reason_code": "protected_position_untouched",
                "source_reference": "protected_symbol_source"}, False

    reasons = {str(a.source_reference) for a in acts}
    if {"target_flip_close", "target_flip_open"} & reasons:
        close_a = next(a for a in acts if a.source_reference == "target_flip_close")
        open_a = next(a for a in acts if a.source_reference == "target_flip_open")
        close_est, open_est = _mul(close_a.qty, mark), _mul(open_a.qty, mark)
        miss = close_est is None or open_est is None
        return {**base, "proposed_action": ACTION_REVERSE,
                "proposed_reduce_only_qty": _canon(close_a.qty) or "0",
                "proposed_open_qty": _canon(open_a.qty) or "0",
                "close_notional_estimate_usd": close_est, "open_notional_estimate_usd": open_est,
                "reason_code": "target_side_reversal", "source_reference": "forward_target_intent",
                "reverse_staged_phases": {
                    "phase_1_reduce_only_close": {"side": close_a.side, "qty": _canon(close_a.qty),
                                                  "reduce_only": True, "executed": False,
                                                  "close_notional_estimate_usd": close_est},
                    "phase_2_open_opposite": {"side": open_a.side, "qty": _canon(open_a.qty),
                                              "reduce_only": False, "executed": False,
                                              "precondition": "phase_1_close_reconciled",
                                              "open_notional_estimate_usd": open_est}}}, miss

    if not acts:
        return {**base, "proposed_action": ACTION_HOLD, "proposed_reduce_only_qty": "0",
                "proposed_open_qty": "0", "close_notional_estimate_usd": "0",
                "open_notional_estimate_usd": "0", "reason_code": "target_matches_current_hold",
                "source_reference": "forward_target_intent"}, False

    a = acts[0]
    action = _REASON_TO_ACTION.get(str(a.source_reference), ACTION_BLOCKED)
    reduce_qty = _canon(a.qty) if a.reduce_only else "0"
    open_qty = "0" if a.reduce_only else _canon(a.qty)
    close_est = open_est = "0"
    if action == ACTION_OPEN:
        open_est = tgt_notional or _mul(a.qty, mark)
        miss = open_est in (None, "")
    elif action == ACTION_INCREASE:
        open_est = _mul(a.qty, mark)
        miss = open_est is None
    elif action in (ACTION_CLOSE, ACTION_DECREASE):
        close_est = _mul(a.qty, mark)
        miss = close_est is None
    return {**base, "proposed_action": action, "proposed_reduce_only_qty": reduce_qty or "0",
            "proposed_open_qty": open_qty or "0", "close_notional_estimate_usd": close_est,
            "open_notional_estimate_usd": open_est, "reason_code": str(a.source_reference),
            "source_reference": "forward_target_intent"}, miss


def _snapshot_fingerprint(current_rows) -> str:
    canon = sorted(({"symbol": r["symbol"], "side": _display_side(r["side"]), "qty": r["qty"],
                     "position_idx": r["position_idx"], "protected": r["symbol"] in PROTECTED_SYMBOLS}
                    for r in current_rows), key=lambda d: d["symbol"])
    return _digest({"kind": "current_position_snapshot", "positions": canon})


def _canonical_source_artifacts(sources: Any) -> dict[str, dict[str, Any]]:
    """The four canonical Forward source roles as {role: {path, sha256}} from ALREADY-VALIDATED
    artifact data (never re-hashed / re-guessed here)."""
    out: dict[str, dict[str, Any]] = {}
    if isinstance(sources, Mapping):
        for role in REQUIRED_SOURCE_ROLES:
            entry = sources.get(role)
            if isinstance(entry, Mapping):
                out[role] = {"path": entry.get("path"), "sha256": entry.get("sha256")}
    return out


def _build_target_intent_evidence(*, sealed_target, production_recompute, t_ok, t_reasons,
                                  signal_date, target_symbol_count, pilot_id, lifecycle_date):
    """Immutable Target-Intent v2 evidence. Present in EVERY artifact; on a provenance failure it
    is explicitly ``validated=False`` with empty fingerprint/digest/source_artifacts (never a
    misleading validated object)."""
    sealed = sealed_target if isinstance(sealed_target, Mapping) else {}
    prod = production_recompute if isinstance(production_recompute, Mapping) else {}
    ev = {
        "validated": t_ok,
        "schema_version": sealed.get("schema_version"),
        "pilot_id": pilot_id, "lifecycle_date": lifecycle_date,
        "strategy_capital_base_usd": STRATEGY_CAPITAL_BASE_USD,
        "source_identifier": sealed.get("source_identifier"),
        "production_strategy": prod.get("strategy"),
        "validation_reasons": list(t_reasons),
    }
    if t_ok:
        ev.update({
            "target_intent_fingerprint": str(sealed.get(TARGET_FINGERPRINT_FIELD, "")),
            "target_digest": sealed.get(TARGET_DIGEST_FIELD),
            "signal_date": signal_date,
            "target_symbol_count": target_symbol_count,
            "source_artifacts": _canonical_source_artifacts(sealed.get("source_artifacts")),
            "source_artifacts_match_production": True,
        })
    else:
        ev.update({
            "target_intent_fingerprint": "", "target_digest": None,
            "signal_date": signal_date or "", "target_symbol_count": 0,
            "source_artifacts": {}, "source_artifacts_match_production": False,
        })
    return ev


def _build_runtime_translation_evidence(*, production_recompute, t_ok, t_reasons, runtime_fp,
                                        target_fp):
    """Volatile runtime-translation evidence. The ``canonical_runtime_translation`` rows are the
    EXACT rows fed to ``runtime_translation_fingerprint`` (same canonicalization, no re-rounding).
    Present in every artifact; empty/``validated=False`` on failure."""
    prod = production_recompute if isinstance(production_recompute, Mapping) else {}
    ev = {
        "validated": t_ok,
        "source": "formal_production_recompute_current_run",
        "validation_reasons": list(t_reasons),
    }
    if t_ok:
        rt = prod.get("runtime_translation") or []
        canon = _canon_runtime_translation(rt)
        observations = {str(r.get("symbol", "")).strip().upper(): r.get("price_observation")
                        for r in rt if isinstance(r, Mapping)}
        ev.update({
            "runtime_translation_fingerprint": runtime_fp,
            "target_intent_fingerprint": target_fp,
            "runtime_symbol_count": len(canon),
            "canonical_runtime_translation": canon,
            "price_observations": observations,
        })
    else:
        ev.update({
            "runtime_translation_fingerprint": "", "target_intent_fingerprint": "",
            "runtime_symbol_count": 0, "canonical_runtime_translation": [], "price_observations": {},
        })
    return ev


def _plan_fingerprint(pilot_id, lifecycle_date, snapshot_fp, target_fp, runtime_fp, actions) -> str:
    canon = sorted(({
        "symbol": a["symbol"], "current_side": a["current_side"], "current_qty": a["current_qty"],
        "target_side": a["target_side"], "proposed_action": a["proposed_action"],
        "proposed_reduce_only_qty": a["proposed_reduce_only_qty"],
        "proposed_open_qty": a["proposed_open_qty"], "reason_code": a["reason_code"],
        "source_reference": a["source_reference"],
        "reverse_phase": bool(a.get("reverse_staged_phases")),
        "protected": a["proposed_action"] == ACTION_PROTECTED_UNTOUCHED}
        for a in actions), key=lambda d: d["symbol"])
    return _digest({"kind": "day2_lifecycle_plan", "pilot_id": pilot_id,
                    "lifecycle_date": lifecycle_date,
                    "current_position_snapshot_fingerprint": snapshot_fp,
                    "target_intent_fingerprint": target_fp,
                    "runtime_translation_fingerprint": runtime_fp, "actions": canon})


def build_day2_lifecycle_dry_run(
    *,
    pilot_id: str,
    lifecycle_date: str,
    day1_date: str,
    day1_fingerprint: str,
    lifecycle_policy: Any,
    day1_post_fill_audit: Any,
    day1_allocation_intent: Any,
    sealed_target: Any,
    production_target_recompute: Any,
    current_positions: Sequence[Any],
    positions_provenance: Mapping[str, Any],
    network_counter_components: Mapping[str, Any],
    protected_symbols: Sequence[str],
    protected_symbols_source: str,
    source_paths: Mapping[str, Any] | None = None,
    generated_at: str = "",
    fingerprint_recompute_fn=None,
    day1_protected_snapshot: Any = None,
    day1_protected_binding: Any = None,
    day1_protected_continuity: Any = None,
    day1_allocation_source_sha256: str | None = None,
) -> dict[str, Any]:
    """Build the machine-readable Day-2 lifecycle dry-run plan (read-only, fail-closed). See module
    docstring -- there is no self-sealed / arbitrary-JSON / free-text path to READY."""
    blockers: list[str] = []
    protected_set = {str(s).strip().upper() for s in (protected_symbols or [])}

    if str(lifecycle_policy) not in RECOGNIZED_LIFECYCLE_POLICIES:
        blockers.append(f"unrecognized_lifecycle_policy:{lifecycle_policy}")

    d1_ok, d1_reasons, day1_sides = validate_day1_evidence(
        post_fill_audit=day1_post_fill_audit, allocation_intent=day1_allocation_intent,
        pilot_id=pilot_id, day1_date=day1_date, day1_fingerprint=day1_fingerprint,
        fingerprint_recompute_fn=fingerprint_recompute_fn)
    if not d1_ok:
        blockers.extend(d1_reasons)
    day1_symbols = set(day1_sides)

    t_ok, t_reasons, target_by_symbol, signal_date, runtime_fp = verify_production_target_provenance(
        sealed_target=sealed_target, production_recompute=production_target_recompute,
        pilot_id=pilot_id, lifecycle_date=lifecycle_date)
    if not t_ok:
        blockers.extend(t_reasons)

    if not protected_set or not PROTECTED_SYMBOLS.issubset(protected_set):
        blockers.append("protected_symbol_evidence_incomplete")

    if str(positions_provenance.get("termination_reason", "")) != COMPLETE_PAGINATION_TERMINATION:
        blockers.append(f"position_pagination_incomplete:{positions_provenance.get('termination_reason')}")
    page_count = _as_int(positions_provenance.get("page_count"))
    if page_count is None or page_count < 1:
        blockers.append(f"position_page_count_invalid:{positions_provenance.get('page_count')}")

    merged_counters, counter_blockers, counter_breakdown = merge_network_counters(
        network_counter_components)
    blockers.extend(counter_blockers)
    mutating = merged_counters["private_mutating_request_count"]
    read_only = merged_counters["private_read_only_request_count"]

    # Enrich + completeness-check EVERY nonzero position (all 51, incl. protected).
    current_rows: list[dict[str, Any]] = []
    current_by_symbol: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    nonzero = 0
    protected_present: dict[str, dict[str, Any]] = {}
    for p in current_positions:
        row, missing = _enrich_position(p)
        if row["qty_dec"] is not None and row["qty_dec"] <= 0:
            continue
        nonzero += 1
        sym = row["symbol"]
        if missing:
            blockers.append(f"current_position_evidence_incomplete:{sym or '?'}:{sorted(missing)}")
            continue
        if sym in seen:
            blockers.append(f"duplicate_current_position_symbol:{sym}")
            continue
        seen.add(sym)
        current_rows.append(row)
        current_by_symbol[sym] = row
        if sym in PROTECTED_SYMBOLS:
            protected_present[sym] = row

    # Reconcile against the validated Day-1 baseline.
    if day1_symbols:
        for sym in sorted(day1_symbols):
            cur = current_by_symbol.get(sym)
            if cur is None:
                blockers.append(f"missing_day1_strategy_symbol:{sym}")
            elif _display_side(cur["side"]) != day1_sides[sym]:
                blockers.append(f"current_side_differs_from_day1:{sym}")
        # EDUUSDT is the ONLY symbol allowed to be open beyond the 50 Day-1 strategy positions;
        # any other extra fails closed.
        extra = sorted(s for s in current_by_symbol if s not in day1_symbols)
        unauthorized = [s for s in extra if s != ALLOWED_EXTRA_OPEN_SYMBOL]
        if unauthorized:
            blockers.append(f"unauthorized_unexpected_open_symbols:{unauthorized}")

    # EDUUSDT position-identity continuity is proven ONLY by the formal immutable evidence chain
    # (TASK-014CA): a sealed PRE_DAY1 protected snapshot + Day-1 allocation binding + post-fill
    # continuity, self-recomputed and exactly bound to THIS pilot/date, with the CURRENT EDUUSDT
    # identity equal to the sealed identity. Absent that chain the identity is unprovable (a manual
    # JSON / raw SHA is not trustworthy evidence and the Day-1 post-fill audit lists only the allowed
    # symbol, not its side/qty) -> fail closed with the canonical blocker.
    audit_allowed = set((day1_post_fill_audit or {}).get("allowed_preexisting_protected_symbols") or []) \
        if isinstance(day1_post_fill_audit, Mapping) else set()
    protected_identity_chain_verified = False
    if ALLOWED_EXTRA_OPEN_SYMBOL in current_by_symbol:
        chain_supplied = any(x is not None for x in
                             (day1_protected_snapshot, day1_protected_binding, day1_protected_continuity))
        if chain_supplied:
            current_protected_identities = {
                (r["symbol"], r["position_idx"]): {"symbol": r["symbol"], "side": r["side"],
                                                   "qty": r["qty"], "position_idx": r["position_idx"]}
                for r in current_rows if r["symbol"] in PROTECTED_SYMBOLS}
            chain_ok, chain_reasons = _pib().verify_day1_protected_identity_chain(
                pilot_id=pilot_id, day1_date=day1_date,
                snapshot=day1_protected_snapshot, binding=day1_protected_binding,
                continuity=day1_protected_continuity,
                current_protected_identities=current_protected_identities,
                day1_allocation_intent=day1_allocation_intent,
                allocation_source_sha256=day1_allocation_source_sha256)
            if chain_ok:
                protected_identity_chain_verified = True
            else:
                blockers.extend(f"day1_protected_chain:{r}" for r in chain_reasons)
        else:
            if ALLOWED_EXTRA_OPEN_SYMBOL not in audit_allowed:
                blockers.append("eduusdt_not_in_day1_audit_allowed_protected")
            blockers.append("day1_eduusdt_position_identity_evidence_unavailable")

    # Classification + per-action mark-priced estimates.
    actions: list[dict[str, Any]] = []
    estimate_unavailable = False
    if t_ok and d1_ok and str(lifecycle_policy) in RECOGNIZED_LIFECYCLE_POLICIES:
        by_symbol = _classify(target_by_symbol, current_by_symbol)
        for sym in sorted(set(target_by_symbol) | set(current_by_symbol)):
            rec, miss = _symbol_record(sym, target_by_symbol.get(sym),
                                       current_by_symbol.get(sym), by_symbol.get(sym, []))
            actions.append(rec)
            if miss:
                estimate_unavailable = True
                blockers.append(f"missing_mark_price_for_estimate:{sym}")

    counts = {a: 0 for a in (ACTION_HOLD, ACTION_CLOSE, ACTION_OPEN, ACTION_REVERSE,
                             ACTION_INCREASE, ACTION_DECREASE, ACTION_PROTECTED_UNTOUCHED,
                             ACTION_BLOCKED)}
    for a in actions:
        counts[a["proposed_action"]] = counts.get(a["proposed_action"], 0) + 1
    if any(a["proposed_action"] == ACTION_BLOCKED for a in actions):
        blockers.append("unclassifiable_symbol_action")

    if actions and not estimate_unavailable:
        gc = sum((_dec(a["close_notional_estimate_usd"]) or Decimal(0)) for a in actions)
        go = sum((_dec(a["open_notional_estimate_usd"]) or Decimal(0)) for a in actions)
        gross_close_s, gross_open_s = _canon(gc), _canon(go)
    else:
        gross_close_s = gross_open_s = None

    snapshot_fp = _snapshot_fingerprint(current_rows)
    target_fp = str(sealed_target.get(TARGET_FINGERPRINT_FIELD, "")) \
        if isinstance(sealed_target, Mapping) else ""
    plan_fp = _plan_fingerprint(pilot_id, lifecycle_date, snapshot_fp, target_fp, runtime_fp,
                                actions) if actions else ""
    identity_core = {"pilot_id": pilot_id, "lifecycle_date": lifecycle_date,
                     "current_position_snapshot_fingerprint": snapshot_fp,
                     "target_intent_fingerprint": target_fp,
                     "runtime_translation_fingerprint": runtime_fp,
                     "lifecycle_plan_fingerprint": plan_fp}
    exactly_once_identity = {
        **identity_core,
        "close_batch_identity": _digest({"phase": "CLOSE", **identity_core}),
        "open_batch_identity": _digest({"phase": "OPEN", **identity_core}),
        "note": ("close and open batches use DISTINCT identities; a future open must wait for the "
                 "close reconciliation; partial success must NOT be blindly retried")}

    verdict = DRY_RUN_READY if not blockers else DRY_RUN_BLOCKED
    return {
        "schema_version": SCHEMA_VERSION, "generated_at": generated_at,
        "environment": ENVIRONMENT_DEMO, "pilot_id": pilot_id, "lifecycle_date": lifecycle_date,
        "day1_date": day1_date, "strategy_capital_base_usd": STRATEGY_CAPITAL_BASE_USD,
        "lifecycle_policy": lifecycle_policy, "signal_date": signal_date,
        "current_position_snapshot_fingerprint": snapshot_fp,
        "target_intent_fingerprint": target_fp,
        "runtime_translation_fingerprint": runtime_fp,
        "lifecycle_plan_fingerprint": plan_fp,
        "exactly_once_identity_design": exactly_once_identity,
        "day1_evidence": {"validated": d1_ok, "day1_fingerprint": day1_fingerprint,
                          "day1_strategy_symbol_count": len(day1_symbols),
                          "validation_reasons": d1_reasons},
        "target_intent_evidence": _build_target_intent_evidence(
            sealed_target=sealed_target, production_recompute=production_target_recompute,
            t_ok=t_ok, t_reasons=t_reasons, signal_date=signal_date,
            target_symbol_count=len(target_by_symbol), pilot_id=pilot_id,
            lifecycle_date=lifecycle_date),
        "runtime_translation_evidence": _build_runtime_translation_evidence(
            production_recompute=production_target_recompute, t_ok=t_ok, t_reasons=t_reasons,
            runtime_fp=runtime_fp, target_fp=target_fp),
        "pagination_evidence": {
            "page_count": positions_provenance.get("page_count"),
            "termination_reason": positions_provenance.get("termination_reason"),
            "api_position_rows": positions_provenance.get("api_position_rows"),
            "nonzero_position_count": nonzero},
        "current_strategy_positions": [
            {k: r[k] for k in ("symbol", "side", "qty", "position_idx", "entry_price",
                               "mark_price", "unrealized_pnl", "current_notional_usd")}
            | {"side": _display_side(r["side"])}
            for r in current_rows if r["symbol"] not in PROTECTED_SYMBOLS],
        "protected_positions": {
            "protected_symbols_source": protected_symbols_source,
            "protected_symbols": sorted(protected_set),
            "protected_positions_present": sorted(protected_present)},
        "protected_identity_chain_verified": protected_identity_chain_verified,
        "action_counts": counts, "actions": actions,
        "gross_close_notional_estimate_usd": gross_close_s,
        "gross_open_notional_estimate_usd": gross_open_s,
        "network_audit_counters": {
            "private_read_only_request_count": read_only,
            "public_read_only_request_count": merged_counters["public_read_only_request_count"],
            "private_mutating_request_count": mutating,
            "component_breakdown": counter_breakdown,
            "position_pagination_page_count": positions_provenance.get("page_count"),
            "position_cursor_termination_reason": positions_provenance.get("termination_reason")},
        "source_paths": dict(source_paths or {}),
        "blockers": blockers, "verdict": verdict,
    }
