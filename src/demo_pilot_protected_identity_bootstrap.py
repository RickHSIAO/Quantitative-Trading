"""TASK-014CA: READ-ONLY pre-Day-1 protected-position identity bootstrap for a NEW Demo Pilot.

Before any NEW-Pilot Day-1 strategy order can be authorized, this seals the IMMUTABLE identity of
every pre-existing PROTECTED position (``symbol in`` the canonical PROTECTED_SYMBOLS anchor) from a
formal Bybit Demo PRIVATE read-only, fully-paginated snapshot. It NEVER sends / cancels / amends /
closes / resizes anything, never changes leverage or position mode, never initializes a sender,
never calls an execution adapter, never advances a Pilot, and never authorizes execution.

Two ORTHOGONAL states (FIX2):

  * ``snapshot_evidence_valid`` -- the sealed protected identity is trustworthy (complete pagination,
    accounted counters, no mutation, no duplicate composite key, complete protected identity + audit,
    valid Demo/account evidence, not a retired Pilot). ONLY an evidence-integrity failure clears the
    fingerprint/digest.
  * ``bootstrap_ready`` -- the NEW Pilot may begin Day 1. A valid snapshot is NOT ready while the
    account still holds the previous Pilot's non-protected strategy positions
    (``preexisting_nonprotected_positions_require_ownership_resolution``). That readiness blocker is
    NOT evidence corruption and never empties an already-sealed protected fingerprint/digest. An
    EMPTY protected set is itself a VALID, ready state.

Three pure stages + a Day-2 chain verifier:

  1. ``build_pre_day1_protected_snapshot`` -- classify observed positions into all / protected /
     preexisting-nonprotected; canonicalize each PROTECTED position by COMPOSITE identity
     ``(symbol, position_idx)``; seal ``protected_position_snapshot_fingerprint`` + ``..._digest``
     (both self-recomputable from the single ``canonical_protected_positions`` source of truth).
  2. ``build_day1_protected_binding`` -- validate a FORMAL Day-1 allocation artifact with the
     production allocation-fingerprint recompute, then bind it to the sealed snapshot. Binding
     evidence can be VALID while ``execution_ready`` is False (ownership unresolved).
  3. ``verify_post_fill_protected_continuity`` -- require EXACT protected identity continuity by
     composite key.

Retired Pilots can neither bootstrap nor be repaired. Immutable side/qty/position_idx come ONLY from
the read-only API snapshot.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from src.demo_strategy_native_day2_lifecycle import merge_network_counters
from src.demo_strategy_pilot_native_execution import PROTECTED_SYMBOLS as _NX_PROTECTED_SYMBOLS

# --------------------------------------------------------------------------- constants
SNAPSHOT_SCHEMA_VERSION = "demo_pilot_protected_position_pre_day1_snapshot_v1"
BINDING_SCHEMA_VERSION = "demo_pilot_day1_protected_binding_v1"
CONTINUITY_SCHEMA_VERSION = "demo_pilot_day1_post_fill_protected_continuity_v1"

ENVIRONMENT = "DEMO"
PHASE_PRE_DAY1 = "PRE_DAY1"
STRATEGY_CAPITAL_BASE_USD = "10000"
EXPECTED_STRATEGY_SYMBOLS = 50
EXPECTED_SIDE_COUNT = 25

# Evidence-validity vs bootstrap-readiness verdicts are DISTINCT (FIX2).
EVIDENCE_VALID = "PROTECTED_IDENTITY_EVIDENCE_VALID"
EVIDENCE_INVALID = "PROTECTED_IDENTITY_EVIDENCE_INVALID"
BOOTSTRAP_READY = "NEW_PILOT_BOOTSTRAP_READY"
BOOTSTRAP_BLOCKED = "NEW_PILOT_BOOTSTRAP_BLOCKED"
BINDING_EVIDENCE_VALID = "PROTECTED_IDENTITY_BINDING_EVIDENCE_VALID"
BINDING_EVIDENCE_INVALID = "PROTECTED_IDENTITY_BINDING_EVIDENCE_INVALID"
CONTINUITY_PASS = "PASS"
CONTINUITY_BLOCKED = "PROTECTED_IDENTITY_CONTINUITY_BLOCKED"

OWNERSHIP_READINESS_BLOCKER = "preexisting_nonprotected_positions_require_ownership_resolution"

# The only cursor-pagination termination that proves a COMPLETE read (Bybit empty nextPageCursor).
PAGINATION_COMPLETE_REASONS = frozenset({"empty_cursor"})

# The canonical protected-symbol anchor. ONLY these symbols may enter the protected identity set.
CANONICAL_PROTECTED_ANCHOR = frozenset(_NX_PROTECTED_SYMBOLS)

# Retired Pilots may never be repaired with a newly captured snapshot (no back-dated evidence).
RETIRED_PILOT_IDS = frozenset({"BYBIT_DEMO_PILOT_7D_202606_V1"})

_REQUIRED_ACCOUNT_FIELDS = ("account_mode", "demo_flag", "endpoint_family")
_PAGE_EVIDENCE_FIELDS = ("page_number", "request_started_at_utc", "response_received_at_utc",
                         "request_elapsed_ms", "request_cursor_present",
                         "response_next_cursor_present", "raw_row_count", "nonzero_row_count",
                         "endpoint")

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")           # bare production allocation fingerprint
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FORBIDDEN_ACCOUNT_KEY_RE = re.compile(r"api[_-]?key|secret|signature|passphrase|x-bapi", re.I)

_CRUN = None


def _crun():
    """Lazy-load the production daily runner for its canonical ``allocation_intent_fingerprint``."""
    global _CRUN
    if _CRUN is None:
        import importlib.util
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "scripts", "run_demo_strategy_pilot_native_daily.py")
        spec = importlib.util.spec_from_file_location("_crun_pib_fp", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _CRUN = mod
    return _CRUN


# --------------------------------------------------------------------------- small pure helpers
def _digest(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                   default=str).encode("utf-8")).hexdigest()


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


def _as_int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _norm_side(side: Any) -> str:
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


def _sym(v: Any) -> str:
    return str(v or "").strip().upper()


def _position_row(p: Any) -> tuple[dict[str, Any], list[str], list[str]]:
    """Parse ONE position (dataclass or Mapping) into identity + audit fields. Returns
    (row, missing_identity_fields, missing_audit_fields)."""
    g = (lambda k, d=None: p.get(k, d)) if isinstance(p, Mapping) else (lambda k, d=None: getattr(p, k, d))
    sym = _sym(g("symbol", ""))
    side = _norm_side(g("side"))
    qty = _dec(g("qty", g("size", g("quantity"))))
    pidx = _as_int(g("position_idx", g("positionIdx")))
    entry = _canon(g("entry_price", g("avgPrice", g("avg_price"))))
    lev = _canon(g("leverage"))
    row = {"symbol": sym, "side": side, "display_side": _display_side(side),
           "qty": _canon(qty) if qty is not None else None, "position_idx": pidx,
           "entry_price": entry, "leverage": lev}
    missing_id: list[str] = []
    if not sym:
        missing_id.append("symbol")
    if side not in ("long", "short"):
        missing_id.append("side")
    if qty is None or qty <= 0:
        missing_id.append("qty")
    if pidx is None:
        missing_id.append("position_idx")
    missing_audit: list[str] = []
    if entry is None:
        missing_audit.append("entry_price")
    if lev is None:
        missing_audit.append("leverage")
    return row, missing_id, missing_audit


def _identity_core(row: Mapping[str, Any]) -> dict[str, Any]:
    """ONLY the four immutable identity fields bound into the fingerprint."""
    return {"symbol": row["symbol"], "side": row["side"],
            "qty": row["qty"], "position_idx": row["position_idx"]}


def _account_audit_evidence(account_evidence: Any) -> tuple[dict[str, Any], str, bool, list[str]]:
    """Non-sensitive account/runtime audit evidence + its safe digest. Any credential-shaped key,
    a missing required field, or a live-endpoint fallback fails closed. ``account_identifier`` is
    optional -- when absent, ``account_identifier_available=False`` (never faked from base_url)."""
    reasons: list[str] = []
    if not isinstance(account_evidence, Mapping):
        return {}, "", False, ["account_evidence_not_object"]
    safe = {k: v for k, v in account_evidence.items()}
    for k in safe:
        if _FORBIDDEN_ACCOUNT_KEY_RE.search(str(k)):
            reasons.append(f"account_evidence_forbidden_key:{k}")
    if reasons:
        return {}, "", False, reasons
    for f in _REQUIRED_ACCOUNT_FIELDS:
        if not safe.get(f):
            reasons.append(f"account_evidence_incomplete:{f}")
    if safe.get("live_endpoint_fallback_detected") is not False:
        reasons.append("account_live_endpoint_fallback_detected")
    account_identifier_available = bool(safe.get("account_identifier"))
    return safe, _digest(safe), account_identifier_available, reasons


def _canonical_page_evidence(provenance: Any) -> list[dict[str, Any]]:
    """Canonical per-page request provenance (timing / cursor flags / row counts). Never carries
    any api key / signature / header / raw query."""
    if not isinstance(provenance, Mapping):
        return []
    pages = provenance.get("position_page_request_evidence")
    out: list[dict[str, Any]] = []
    if isinstance(pages, list):
        for pg in pages:
            if isinstance(pg, Mapping):
                out.append({f: pg.get(f) for f in _PAGE_EVIDENCE_FIELDS})
    return out


def _pagination_evidence(provenance: Any, *, prefix: str) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    if not isinstance(provenance, Mapping):
        return {}, [f"{prefix}_pagination_evidence_missing"]
    reason = str(provenance.get("termination_reason", ""))
    ev = {"termination_reason": reason,
          "page_count": _as_int(provenance.get("page_count")),
          "api_position_rows": _as_int(provenance.get("api_position_rows")),
          "nonzero_position_count": _as_int(provenance.get("nonzero_position_count"))}
    if reason not in PAGINATION_COMPLETE_REASONS:
        reasons.append(f"{prefix}_pagination_incomplete:{reason or 'none'}")
    if ev["page_count"] is None or ev["page_count"] < 1:
        reasons.append(f"{prefix}_pagination_page_count_invalid")
    return ev, reasons


def _position_mode_evidence(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    idxs = sorted({r["position_idx"] for r in rows if r.get("position_idx") is not None})
    if not idxs:
        mode = "unknown"
    elif idxs == [0]:
        mode = "one_way"
    elif all(i in (1, 2) for i in idxs):
        mode = "hedge"
    else:
        mode = "mixed"
    return {"position_mode": mode, "observed_position_idx_values": idxs}


# --------------------------------------------------------------------------- canonical recompute
def canonical_protected_snapshot_fingerprint(snapshot: Mapping[str, Any]) -> str:
    """Recompute the immutable-identity fingerprint from the snapshot's SINGLE
    ``canonical_protected_positions`` source (so a tampered value no longer matches the stored
    fingerprint even if the outer digest was re-derived). An empty protected set binds an explicit
    empty list -- never null / an omitted field."""
    rows = snapshot.get("canonical_protected_positions")
    rows = rows if isinstance(rows, list) else []
    cores = sorted((_identity_core(r) for r in rows if isinstance(r, Mapping)),
                   key=lambda r: (r["symbol"], r["position_idx"] if r["position_idx"] is not None else -1))
    return _digest({
        "kind": "pre_day1_protected_snapshot", "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "pilot_id": snapshot.get("pilot_id"), "day1_date": snapshot.get("day1_date"),
        "environment": snapshot.get("environment"),
        "account_identity_digest": snapshot.get("account_identity_digest"),
        "canonical_protected_positions": cores,
        "pagination_evidence": snapshot.get("pagination_evidence"),
        "protected_symbol_set": snapshot.get("protected_symbol_set"),
        "generated_snapshot_evidence": snapshot.get("generated_snapshot_evidence"),
    })


def canonical_protected_snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    return _digest({k: v for k, v in snapshot.items() if k != "protected_position_snapshot_digest"})


def canonical_binding_fingerprint(binding: Mapping[str, Any]) -> str:
    return _digest({
        "kind": "day1_protected_binding", "schema_version": BINDING_SCHEMA_VERSION,
        "pilot_id": binding.get("pilot_id"), "day1_date": binding.get("day1_date"),
        "allocation_intent_fingerprint": binding.get("allocation_intent_fingerprint"),
        "protected_position_snapshot_fingerprint": binding.get("protected_position_snapshot_fingerprint"),
        "protected_position_snapshot_digest": binding.get("protected_position_snapshot_digest"),
        "protected_symbols": binding.get("protected_symbols")})


def canonical_binding_digest(binding: Mapping[str, Any]) -> str:
    return _digest({k: v for k, v in binding.items() if k != "binding_digest"})


def canonical_continuity_fingerprint(continuity: Mapping[str, Any]) -> str:
    rows = continuity.get("protected_continuity_evidence")
    rows = rows if isinstance(rows, list) else []
    cores = sorted((_identity_core(r) for r in rows if isinstance(r, Mapping)),
                   key=lambda r: (r["symbol"], r["position_idx"] if r["position_idx"] is not None else -1))
    return _digest({
        "kind": "day1_post_fill_protected_continuity", "schema_version": CONTINUITY_SCHEMA_VERSION,
        "pilot_id": continuity.get("pilot_id"), "day1_date": continuity.get("day1_date"),
        "binding_fingerprint": continuity.get("binding_fingerprint"),
        "protected_position_snapshot_fingerprint": continuity.get("protected_position_snapshot_fingerprint"),
        "protected_continuity": cores})


# --------------------------------------------------------------------------- allocation validation
def validate_day1_allocation_artifact(
    allocation_artifact: Any, *, pilot_id: str, day1_date: str,
) -> tuple[bool, list[str], str]:
    """Validate a FORMAL Day-1 allocation artifact with the production allocation-fingerprint
    recompute (pilot / date / capital base / 50 symbols / 25-25 sides / symbol uniqueness /
    stored == recomputed). Any present formal ``environment`` field must be consistent. Returns
    (ok, reasons, recomputed_fingerprint)."""
    reasons: list[str] = []
    if not isinstance(allocation_artifact, Mapping):
        return False, ["allocation_artifact_not_object"], ""
    if str(allocation_artifact.get("pilot_id", "")) != str(pilot_id):
        reasons.append("allocation_pilot_id_mismatch")
    if str(allocation_artifact.get("date", "")) != str(day1_date):
        reasons.append("allocation_date_mismatch")
    if str(allocation_artifact.get("strategy_capital_base_usd", "")) != STRATEGY_CAPITAL_BASE_USD:
        reasons.append("allocation_capital_base_mismatch")
    # Present formal fields must be self-consistent (never silently ignored).
    if "environment" in allocation_artifact and str(allocation_artifact.get("environment")) not in ("", ENVIRONMENT, "BYBIT_DEMO"):
        reasons.append("allocation_environment_unexpected")
    payloads = allocation_artifact.get("order_payloads")
    if not isinstance(payloads, list) or len(payloads) != EXPECTED_STRATEGY_SYMBOLS:
        reasons.append(f"allocation_symbol_count_not_50:"
                       f"{len(payloads) if isinstance(payloads, list) else 'NA'}")
        payloads = payloads if isinstance(payloads, list) else []

    seen: set[str] = set()
    buys = sells = 0
    allocs: list[dict[str, Any]] = []
    for p in payloads:
        if not isinstance(p, Mapping):
            reasons.append("allocation_payload_not_object")
            continue
        sym = _sym(p.get("symbol"))
        side = str(p.get("side", "")).strip()
        if not sym or sym in seen:
            reasons.append(f"allocation_duplicate_or_empty_symbol:{sym or '?'}")
            continue
        seen.add(sym)
        if side == "Buy":
            buys += 1
        elif side == "Sell":
            sells += 1
        else:
            reasons.append(f"allocation_invalid_side:{sym}")
        allocs.append({"symbol": sym, "side": side,
                       "target_notional_usd": p.get("target_notional_usd")})
    if len(payloads) == EXPECTED_STRATEGY_SYMBOLS and (buys != EXPECTED_SIDE_COUNT or sells != EXPECTED_SIDE_COUNT):
        reasons.append(f"allocation_side_distribution_not_25_25:{buys}/{sells}")

    recomputed = ""
    try:
        recomputed = _crun().allocation_intent_fingerprint(
            allocs, pilot_id=str(pilot_id), date=str(day1_date),
            strategy_capital_base_usd=STRATEGY_CAPITAL_BASE_USD)
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"allocation_fingerprint_recompute_failed:{type(exc).__name__}")
    stored = {str(allocation_artifact.get("payload_fingerprint", "")),
              str(allocation_artifact.get("allocation_intent_fingerprint", ""))}
    if not recomputed or len(stored) != 1 or recomputed not in stored:
        reasons.append("allocation_fingerprint_mismatch")
    return (not reasons), reasons, (recomputed if not reasons else "")


# --------------------------------------------------------------------------- stage 1: snapshot
def build_pre_day1_protected_snapshot(
    *, pilot_id: str, day1_date: str, positions: Sequence[Any],
    positions_provenance: Mapping[str, Any], network_counter_components: Mapping[str, Any],
    account_evidence: Mapping[str, Any], source_endpoint: str, generated_at: str,
) -> dict[str, Any]:
    """Seal the immutable identity of every pre-existing PROTECTED nonzero position BEFORE any
    NEW-Pilot Day-1 order is authorized. Read-only; ``trading_authorized`` is always False. Evidence
    validity and bootstrap readiness are DISTINCT: an ownership readiness blocker never empties an
    otherwise-valid sealed protected fingerprint/digest."""
    evidence_blockers: list[str] = []
    readiness_blockers: list[str] = []
    pilot_id = str(pilot_id or "").strip()
    if not pilot_id:
        evidence_blockers.append("pilot_id_missing")
    if pilot_id in RETIRED_PILOT_IDS:
        evidence_blockers.append(f"retired_pilot_cannot_bootstrap:{pilot_id}")
    if not _valid_date(day1_date):
        evidence_blockers.append("day1_date_invalid")

    merged, net_blockers, breakdown = merge_network_counters(network_counter_components)
    evidence_blockers.extend(net_blockers)

    pagination_evidence, pag_blockers = _pagination_evidence(
        positions_provenance, prefix="protected_snapshot")
    evidence_blockers.extend(pag_blockers)
    page_request_evidence = _canonical_page_evidence(positions_provenance)

    account_safe, account_identity_digest, account_identifier_available, acct_blockers = \
        _account_audit_evidence(account_evidence)
    evidence_blockers.extend(acct_blockers)

    all_observed: list[dict[str, Any]] = []
    protected_rows: list[dict[str, Any]] = []
    nonprotected_rows: list[dict[str, Any]] = []
    composite_seen: set[tuple[str, Any]] = set()
    for p in (positions or []):
        row, miss_id, miss_audit = _position_row(p)
        key = (row["symbol"], row["position_idx"])
        if key in composite_seen:
            evidence_blockers.append(
                f"duplicate_position_composite_key:{row['symbol'] or '?'}:{row['position_idx']}")
            continue
        composite_seen.add(key)
        all_observed.append(row)
        if row["symbol"] in CANONICAL_PROTECTED_ANCHOR:
            if miss_id:
                evidence_blockers.append(
                    f"protected_position_incomplete:{row['symbol'] or '?'}:{'+'.join(miss_id)}")
                continue
            if miss_audit:
                evidence_blockers.append(
                    f"protected_position_audit_incomplete:{row['symbol']}:{'+'.join(miss_audit)}")
            protected_rows.append(row)
        elif row["symbol"]:
            nonprotected_rows.append(row)
        else:
            evidence_blockers.append("observed_position_missing_symbol")

    protected_rows.sort(key=lambda r: (r["symbol"], r["position_idx"]))
    nonprotected_rows.sort(key=lambda r: (r["symbol"], r["position_idx"] if r["position_idx"] is not None else -1))

    # Classification total must equal the observed nonzero set and the paginated nonzero count.
    nonzero = pagination_evidence.get("nonzero_position_count")
    if nonzero is not None and not pag_blockers and nonzero != len(all_observed):
        evidence_blockers.append(f"protected_snapshot_row_count_mismatch:{len(all_observed)}!={nonzero}")
    if len(protected_rows) + len(nonprotected_rows) != len(all_observed):
        evidence_blockers.append("protected_snapshot_classification_count_inconsistent")

    # An inherited non-protected position is a READINESS blocker -- NOT evidence corruption.
    if nonprotected_rows:
        readiness_blockers.append(OWNERSHIP_READINESS_BLOCKER)

    protected_symbol_set = sorted({r["symbol"] for r in protected_rows})
    snapshot_evidence_valid = not evidence_blockers
    bootstrap_ready = snapshot_evidence_valid and not readiness_blockers
    generated_snapshot_evidence = {"source_endpoint": str(source_endpoint or ""),
                                   "generated_at": str(generated_at or "")}

    artifact: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION, "phase": PHASE_PRE_DAY1,
        "environment": ENVIRONMENT, "pilot_id": pilot_id, "day1_date": day1_date,
        "generated_at": str(generated_at or ""), "source_endpoint": str(source_endpoint or ""),
        "trading_authorized": False, "execution_ready": False,
        "snapshot_evidence_valid": snapshot_evidence_valid,
        "bootstrap_ready": bootstrap_ready,
        "snapshot_evidence_verdict": EVIDENCE_VALID if snapshot_evidence_valid else EVIDENCE_INVALID,
        "bootstrap_verdict": BOOTSTRAP_READY if bootstrap_ready else BOOTSTRAP_BLOCKED,
        "evidence_blockers": sorted(evidence_blockers),
        "readiness_blockers": sorted(readiness_blockers),
        "blockers": sorted(evidence_blockers + readiness_blockers),
        "account_identity_evidence": account_safe,
        "account_identity_digest": account_identity_digest,
        "account_identifier_available": account_identifier_available,
        "demo_runtime_proof": account_safe,
        "position_mode_evidence": _position_mode_evidence(all_observed),
        "canonical_protected_positions": protected_rows,   # single source of truth
        "protected_positions_summary": {"count": len(protected_rows), "symbols": protected_symbol_set},
        "preexisting_nonprotected_positions": nonprotected_rows,
        "all_observed_nonzero_positions": all_observed,
        "protected_symbol_set": protected_symbol_set,
        "canonical_protected_anchor": sorted(CANONICAL_PROTECTED_ANCHOR),
        "all_observed_nonzero_count": len(all_observed),
        "protected_position_count": len(protected_rows),
        "preexisting_nonprotected_position_count": len(nonprotected_rows),
        "generated_snapshot_evidence": generated_snapshot_evidence,
        "pagination_evidence": pagination_evidence,
        "position_page_request_evidence": page_request_evidence,
        "network_audit_counters": {**merged, "component_breakdown": breakdown},
        "private_mutating_request_count": merged["private_mutating_request_count"],
    }
    artifact["protected_position_snapshot_fingerprint"] = (
        canonical_protected_snapshot_fingerprint(artifact) if snapshot_evidence_valid else "")
    artifact["protected_position_snapshot_digest"] = (
        canonical_protected_snapshot_digest(artifact) if snapshot_evidence_valid else "")
    return artifact


def _snapshot_is_sealed(snapshot: Any) -> tuple[bool, list[str], str, str, bool]:
    """Validate a snapshot has VALID EVIDENCE and is self-consistent: RECOMPUTE both the
    immutable-identity fingerprint and the artifact digest, exact-match the stored values, and check
    the single-source classification is internally consistent (no double-truth divergence). Returns
    (ok, reasons, snapshot_fingerprint, snapshot_digest, bootstrap_ready)."""
    reasons: list[str] = []
    if not isinstance(snapshot, Mapping):
        return False, ["snapshot_not_object"], "", "", False
    if snapshot.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        reasons.append("snapshot_schema_version_unexpected")
    if not snapshot.get("snapshot_evidence_valid") or snapshot.get("snapshot_evidence_verdict") != EVIDENCE_VALID:
        reasons.append("snapshot_evidence_invalid")
    if snapshot.get("environment") != ENVIRONMENT:
        reasons.append("snapshot_environment_unexpected")
    fp = str(snapshot.get("protected_position_snapshot_fingerprint", ""))
    digest = str(snapshot.get("protected_position_snapshot_digest", ""))
    if not _SHA256_RE.match(fp):
        reasons.append("snapshot_fingerprint_missing")
    if not _SHA256_RE.match(digest):
        reasons.append("snapshot_digest_missing")
    if not reasons:
        if canonical_protected_snapshot_fingerprint(snapshot) != fp:
            reasons.append("snapshot_fingerprint_mismatch")
        if canonical_protected_snapshot_digest(snapshot) != digest:
            reasons.append("snapshot_digest_mismatch")
        canon = snapshot.get("canonical_protected_positions") or []
        summary = snapshot.get("protected_positions_summary") or {}
        canon_syms = sorted({r.get("symbol") for r in canon if isinstance(r, Mapping)})
        if summary.get("count") != len(canon) or sorted(summary.get("symbols") or []) != canon_syms:
            reasons.append("snapshot_protected_summary_inconsistent")
        nonprot = snapshot.get("preexisting_nonprotected_positions") or []
        allobs = snapshot.get("all_observed_nonzero_positions") or []
        if len(canon) + len(nonprot) != len(allobs):
            reasons.append("snapshot_classification_count_inconsistent")
    bootstrap_ready = bool(snapshot.get("bootstrap_ready")) if isinstance(snapshot, Mapping) else False
    return (not reasons), reasons, fp, digest, bootstrap_ready


# --------------------------------------------------------------------------- stage 2: binding
def build_day1_protected_binding(
    *, pilot_id: str, day1_date: str, day1_allocation_artifact: Mapping[str, Any],
    snapshot_artifact: Mapping[str, Any], allocation_source_path: str | None = None,
    allocation_source_sha256: str | None = None,
) -> dict[str, Any]:
    """Bind a FORMAL Day-1 allocation artifact (validated by production recompute) to the sealed
    PRE_DAY1 snapshot. ``binding_evidence_valid`` can be True while ``execution_ready`` is False when
    the snapshot's ownership readiness is unresolved -- the binding identity is NOT discarded, but no
    Day-1 execution authorization forms."""
    evidence_blockers: list[str] = []
    pilot_id = str(pilot_id or "").strip()
    if pilot_id in RETIRED_PILOT_IDS:
        evidence_blockers.append(f"retired_pilot_cannot_be_repaired:{pilot_id}")

    ok, snap_reasons, snapshot_fp, snapshot_digest, snap_bootstrap_ready = _snapshot_is_sealed(snapshot_artifact)
    if not ok:
        evidence_blockers.extend(snap_reasons)
    snap = snapshot_artifact if isinstance(snapshot_artifact, Mapping) else {}
    if ok and str(snap.get("pilot_id", "")) != pilot_id:
        evidence_blockers.append("binding_pilot_id_mismatch")
    if ok and str(snap.get("day1_date", "")) != str(day1_date):
        evidence_blockers.append("binding_day1_date_mismatch")

    alloc_ok, alloc_reasons, alloc_fp = validate_day1_allocation_artifact(
        day1_allocation_artifact, pilot_id=pilot_id, day1_date=day1_date)
    if not alloc_ok:
        evidence_blockers.extend(alloc_reasons)

    readiness_blockers = sorted(snap.get("readiness_blockers") or []) if ok else []
    protected_symbols = sorted(snap.get("protected_symbol_set") or []) if ok else []
    binding_evidence_valid = not evidence_blockers
    execution_ready = binding_evidence_valid and not readiness_blockers

    artifact: dict[str, Any] = {
        "schema_version": BINDING_SCHEMA_VERSION, "environment": ENVIRONMENT,
        "pilot_id": pilot_id, "day1_date": str(day1_date),
        "allocation_intent_fingerprint": alloc_fp if binding_evidence_valid else "",
        "allocation_artifact_source_path": str(allocation_source_path or ""),
        "allocation_artifact_source_sha256": str(allocation_source_sha256 or ""),
        "protected_position_snapshot_fingerprint": snapshot_fp if binding_evidence_valid else "",
        "protected_position_snapshot_digest": snapshot_digest if binding_evidence_valid else "",
        "protected_symbols": protected_symbols,
        "binding_evidence_valid": binding_evidence_valid,
        "binding_evidence_verdict": BINDING_EVIDENCE_VALID if binding_evidence_valid else BINDING_EVIDENCE_INVALID,
        "execution_ready": execution_ready,
        "evidence_blockers": sorted(evidence_blockers),
        "readiness_blockers": readiness_blockers,
        "blockers": sorted(evidence_blockers + readiness_blockers),
    }
    artifact["binding_fingerprint"] = canonical_binding_fingerprint(artifact) if binding_evidence_valid else ""
    artifact["binding_digest"] = canonical_binding_digest(artifact) if binding_evidence_valid else ""
    return artifact


def _binding_is_sealed(binding: Any, snapshot_fp: str, snapshot_digest: str, *,
                       require_execution_ready: bool = True) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(binding, Mapping):
        return False, ["binding_not_object"]
    if binding.get("schema_version") != BINDING_SCHEMA_VERSION:
        reasons.append("binding_schema_version_unexpected")
    if not binding.get("binding_evidence_valid") or binding.get("binding_evidence_verdict") != BINDING_EVIDENCE_VALID:
        reasons.append("binding_evidence_invalid")
    if require_execution_ready and not binding.get("execution_ready"):
        reasons.append("binding_not_execution_ready")
    if binding.get("environment") != ENVIRONMENT:
        reasons.append("binding_environment_unexpected")
    if str(binding.get("protected_position_snapshot_fingerprint", "")) != snapshot_fp:
        reasons.append("binding_snapshot_fingerprint_mismatch")
    if str(binding.get("protected_position_snapshot_digest", "")) != snapshot_digest:
        reasons.append("binding_snapshot_digest_mismatch")
    if not _HEX64_RE.match(str(binding.get("allocation_intent_fingerprint", ""))):
        reasons.append("binding_allocation_fingerprint_missing")
    if not reasons:
        if canonical_binding_fingerprint(binding) != str(binding.get("binding_fingerprint", "")):
            reasons.append("binding_fingerprint_mismatch")
        if canonical_binding_digest(binding) != str(binding.get("binding_digest", "")):
            reasons.append("binding_digest_mismatch")
    return (not reasons), reasons


# --------------------------------------------------------------------------- stage 3: continuity
def verify_post_fill_protected_continuity(
    *, pilot_id: str, day1_date: str, snapshot_artifact: Mapping[str, Any],
    binding_artifact: Mapping[str, Any], post_fill_positions: Sequence[Any],
    post_fill_provenance: Mapping[str, Any], network_counter_components: Mapping[str, Any],
    strategy_symbols: Sequence[str], generated_at: str = "",
) -> dict[str, Any]:
    """Re-read positions post-fill and require EXACT protected identity continuity by COMPOSITE key
    ``(symbol, position_idx)``. Strategy and protected positions are counted/reported separately.
    Fail-closed on any change, a missing protected position, or an extra unauthorized position. An
    empty protected set is a valid PASS state."""
    blockers: list[str] = []
    pilot_id = str(pilot_id or "").strip()
    if pilot_id in RETIRED_PILOT_IDS:
        blockers.append(f"retired_pilot_cannot_be_repaired:{pilot_id}")

    ok, snap_reasons, snapshot_fp, snapshot_digest, _ready = _snapshot_is_sealed(snapshot_artifact)
    if not ok:
        blockers.extend(snap_reasons)
    bok, bind_reasons = _binding_is_sealed(binding_artifact, snapshot_fp, snapshot_digest)
    if not bok:
        blockers.extend(bind_reasons)

    snap = snapshot_artifact if isinstance(snapshot_artifact, Mapping) else {}
    if ok and str(snap.get("pilot_id", "")) != pilot_id:
        blockers.append("continuity_snapshot_pilot_id_mismatch")
    if ok and str(snap.get("day1_date", "")) != str(day1_date):
        blockers.append("continuity_snapshot_day1_date_mismatch")
    bind = binding_artifact if isinstance(binding_artifact, Mapping) else {}
    if bok and str(bind.get("pilot_id", "")) != pilot_id:
        blockers.append("continuity_binding_pilot_id_mismatch")
    if bok and str(bind.get("day1_date", "")) != str(day1_date):
        blockers.append("continuity_binding_day1_date_mismatch")

    merged, net_blockers, breakdown = merge_network_counters(network_counter_components)
    blockers.extend(net_blockers)

    pagination_evidence, pag_blockers = _pagination_evidence(post_fill_provenance, prefix="post_fill")
    blockers.extend(pag_blockers)
    page_request_evidence = _canonical_page_evidence(post_fill_provenance)

    strategy_set = {_sym(s) for s in (strategy_symbols or [])}
    expected_protected = {(_identity_core(r)["symbol"], _identity_core(r)["position_idx"]): _identity_core(r)
                          for r in (snap.get("canonical_protected_positions") or [])
                          if isinstance(r, Mapping)}

    current: dict[tuple[str, Any], dict[str, Any]] = {}
    for p in (post_fill_positions or []):
        row, miss_id, _miss_audit = _position_row(p)
        if miss_id:
            blockers.append(f"post_fill_position_incomplete:{row['symbol'] or '?'}:{'+'.join(miss_id)}")
            continue
        key = (row["symbol"], row["position_idx"])
        if key in current:
            blockers.append(f"duplicate_post_fill_composite_key:{row['symbol']}:{row['position_idx']}")
            continue
        current[key] = row

    protected_checked: list[dict[str, Any]] = []
    for key, exp in expected_protected.items():
        cur = current.get(key)
        if cur is None:
            blockers.append(f"protected_position_missing:{key[0]}:{key[1]}")
            continue
        if cur["side"] != exp["side"]:
            blockers.append(f"protected_position_side_changed:{key[0]}:{key[1]}")
        if cur["qty"] != exp["qty"]:
            blockers.append(f"protected_position_qty_changed:{key[0]}:{key[1]}")
        protected_checked.append(_identity_core(cur))

    for key in current:
        if key[0] not in strategy_set and key not in expected_protected:
            blockers.append(f"unauthorized_protected_position:{key[0]}:{key[1]}")

    strategy_present = sorted({k[0] for k in current if k[0] in strategy_set})
    protected_present = sorted({k for k in current if k in expected_protected})
    continuity_ok = not blockers

    artifact: dict[str, Any] = {
        "schema_version": CONTINUITY_SCHEMA_VERSION, "environment": ENVIRONMENT,
        "pilot_id": pilot_id, "day1_date": str(day1_date), "generated_at": str(generated_at or ""),
        "trading_authorized": False, "execution_ready": False,
        "protected_position_identity_continuity": CONTINUITY_PASS if continuity_ok else CONTINUITY_BLOCKED,
        "continuity_pass": continuity_ok,
        "verdict": CONTINUITY_PASS if continuity_ok else CONTINUITY_BLOCKED,
        "blockers": sorted(blockers),
        "binding_fingerprint": str(bind.get("binding_fingerprint", "")),
        "protected_position_snapshot_fingerprint": snapshot_fp,
        "strategy_position_count": len(strategy_present),
        "strategy_positions_present": strategy_present,
        "protected_position_count": len(protected_present),
        "protected_positions_present": [k[0] for k in protected_present],
        "protected_continuity_evidence": (
            sorted(protected_checked, key=lambda r: (r["symbol"], r["position_idx"]))
            if continuity_ok else []),
        "pagination_evidence": pagination_evidence,
        "position_page_request_evidence": page_request_evidence,
        "network_audit_counters": {**merged, "component_breakdown": breakdown},
        "private_mutating_request_count": merged["private_mutating_request_count"],
    }
    artifact["post_fill_continuity_fingerprint"] = (
        canonical_continuity_fingerprint(artifact) if continuity_ok else "")
    return artifact


def _continuity_is_sealed(continuity: Any, binding: Any, snapshot_fp: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(continuity, Mapping):
        return False, ["continuity_not_object"]
    if continuity.get("schema_version") != CONTINUITY_SCHEMA_VERSION:
        reasons.append("continuity_schema_version_unexpected")
    if not continuity.get("continuity_pass") or continuity.get("verdict") != CONTINUITY_PASS:
        reasons.append("continuity_not_pass")
    if continuity.get("environment") != ENVIRONMENT:
        reasons.append("continuity_environment_unexpected")
    bind_fp = str((binding or {}).get("binding_fingerprint", "")) if isinstance(binding, Mapping) else ""
    if str(continuity.get("binding_fingerprint", "")) != bind_fp:
        reasons.append("continuity_binding_fingerprint_mismatch")
    if str(continuity.get("protected_position_snapshot_fingerprint", "")) != snapshot_fp:
        reasons.append("continuity_snapshot_fingerprint_mismatch")
    if not reasons:
        if canonical_continuity_fingerprint(continuity) != str(continuity.get("post_fill_continuity_fingerprint", "")):
            reasons.append("continuity_fingerprint_mismatch")
    return (not reasons), reasons


# --------------------------------------------------------------------------- Day-2 chain verifier
def verify_day1_protected_identity_chain(
    *, pilot_id: str, day1_date: str, snapshot: Any, binding: Any, continuity: Any,
    current_protected_identities: Mapping[tuple[str, Any], Mapping[str, Any]],
    day1_allocation_intent: Any = None,
) -> tuple[bool, list[str]]:
    """Re-validate the whole PRE_DAY1 -> binding -> continuity chain for Day-2. Every artifact is
    self-recomputed (fingerprint + digest), the binding must be EXECUTION-READY (ownership resolved),
    the continuity must be PASS, cross-artifact pilot/date/environment must match exactly, and the
    CURRENT protected identity must EXACTLY equal the sealed identity by composite key. Returns
    (ok, sorted_reasons)."""
    reasons: list[str] = []
    pilot_id = str(pilot_id or "").strip()
    if pilot_id in RETIRED_PILOT_IDS:
        reasons.append(f"retired_pilot_cannot_be_repaired:{pilot_id}")
    if snapshot is None or binding is None or continuity is None:
        reasons.append("protected_identity_chain_incomplete")
        return False, sorted(set(reasons))

    ok, snap_reasons, snapshot_fp, snapshot_digest, _ready = _snapshot_is_sealed(snapshot)
    reasons.extend(snap_reasons)
    bok, bind_reasons = _binding_is_sealed(binding, snapshot_fp, snapshot_digest)
    reasons.extend(bind_reasons)
    cok, cont_reasons = _continuity_is_sealed(continuity, binding, snapshot_fp)
    reasons.extend(cont_reasons)

    for name, art in (("snapshot", snapshot), ("binding", binding), ("continuity", continuity)):
        if isinstance(art, Mapping):
            if str(art.get("pilot_id", "")) != pilot_id:
                reasons.append(f"{name}_pilot_id_mismatch")
            if str(art.get("day1_date", "")) != str(day1_date):
                reasons.append(f"{name}_day1_date_mismatch")
            if str(art.get("environment", "")) != ENVIRONMENT:
                reasons.append(f"{name}_environment_mismatch")

    if day1_allocation_intent is not None and isinstance(binding, Mapping):
        aok, areasons, afp = validate_day1_allocation_artifact(
            day1_allocation_intent, pilot_id=pilot_id, day1_date=day1_date)
        if not aok:
            reasons.extend(f"allocation_{r}" for r in areasons)
        elif afp != str(binding.get("allocation_intent_fingerprint", "")):
            reasons.append("binding_allocation_fingerprint_mismatch")

    sealed = {}
    if isinstance(snapshot, Mapping):
        for r in snapshot.get("canonical_protected_positions") or []:
            if isinstance(r, Mapping):
                core = _identity_core(r)
                sealed[(core["symbol"], core["position_idx"])] = core
    cur = dict(current_protected_identities or {})
    for key, exp in sealed.items():
        c = cur.get(key)
        if c is None:
            reasons.append(f"current_protected_missing:{key[0]}:{key[1]}")
        elif _identity_core(c) != exp:
            reasons.append(f"current_protected_identity_mismatch:{key[0]}:{key[1]}")
    for key in cur:
        if key not in sealed:
            reasons.append(f"current_protected_unsealed:{key[0]}:{key[1]}")

    return (not reasons), sorted(set(reasons))
