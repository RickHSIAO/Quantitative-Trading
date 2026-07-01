"""TASK-014CA: READ-ONLY pre-Day-1 protected-position identity bootstrap for a NEW Demo Pilot.

Before any NEW-Pilot Day-1 strategy order can be authorized, this seals the IMMUTABLE identity of
every pre-existing protected (non-strategy-owned) position from a formal Bybit Demo PRIVATE
read-only, fully-paginated snapshot. It NEVER sends / cancels / amends / closes / resizes anything,
never changes leverage or position mode, never initializes a sender, never calls an execution
adapter, never advances a Pilot, and never authorizes execution.

Three pure stages:

  1. ``build_pre_day1_protected_snapshot`` -- canonicalize the PRE_DAY1 protected snapshot and seal
     ``protected_position_snapshot_fingerprint`` + ``..._digest``. ``phase = PRE_DAY1``,
     ``trading_authorized = False``, ``private_mutating_request_count = 0``.
  2. ``build_day1_protected_binding`` -- bind that sealed snapshot to the Day-1
     ``allocation_intent_fingerprint`` via a ``binding_fingerprint`` (co-locating the two files is
     NOT a binding). A Pilot cannot become execution-ready until this binding is COMPLETE.
  3. ``verify_post_fill_protected_continuity`` -- re-read positions and require EXACT
     symbol/side/qty/position_idx continuity for every protected position; only exact continuity is
     ``protected_position_identity_continuity = PASS``. Strategy positions and protected positions
     are counted and reported separately.

Any incomplete pagination, non-zero mutating request, missing/malformed network counter, identity
change, extra unauthorized protected position, or an attempt to repair a RETIRED Pilot fails closed.
The immutable side/qty/position_idx come ONLY from the formal read-only API snapshot -- never from a
user-supplied value and never inferred from a prior artifact.
"""
from __future__ import annotations

import hashlib
import json
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

SNAPSHOT_READY = "PROTECTED_IDENTITY_SNAPSHOT_READY"
SNAPSHOT_BLOCKED = "PROTECTED_IDENTITY_SNAPSHOT_BLOCKED"
BINDING_COMPLETE = "PROTECTED_IDENTITY_BINDING_COMPLETE"
BINDING_BLOCKED = "PROTECTED_IDENTITY_BINDING_BLOCKED"
CONTINUITY_PASS = "PASS"
CONTINUITY_BLOCKED = "PROTECTED_IDENTITY_CONTINUITY_BLOCKED"

# The only cursor-pagination termination that proves a COMPLETE read (Bybit empty nextPageCursor).
PAGINATION_COMPLETE_REASONS = frozenset({"empty_cursor"})

# The canonical protected-symbol anchor (consistency reference only; the actual protected set is
# whatever nonzero positions the formal snapshot observes).
CANONICAL_PROTECTED_ANCHOR = frozenset(_NX_PROTECTED_SYMBOLS)

# Retired Pilots may never be repaired with a newly captured snapshot (no back-dated evidence).
RETIRED_PILOT_IDS = frozenset({"BYBIT_DEMO_PILOT_7D_202606_V1"})

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Non-sensitive account-evidence keys only; any credential-shaped key fails closed.
_FORBIDDEN_ACCOUNT_KEY_RE = re.compile(r"api[_-]?key|secret|signature|passphrase|x-bapi", re.I)


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


def _canonical_identity(p: Any) -> tuple[dict[str, Any], list[str]]:
    """Immutable identity of ONE position (symbol/side/qty/position_idx) from the read-only API row
    (dataclass or Mapping). Returns (canonical_row, missing_fields)."""
    g = (lambda k, d=None: p.get(k, d)) if isinstance(p, Mapping) else (lambda k, d=None: getattr(p, k, d))
    sym = _sym(g("symbol", ""))
    side = _norm_side(g("side"))
    qty = _dec(g("qty", g("size", g("quantity"))))
    pidx = _as_int(g("position_idx", g("positionIdx")))
    row = {"symbol": sym, "side": side, "display_side": _display_side(side),
           "qty": _canon(qty) if qty is not None else None, "position_idx": pidx}
    missing: list[str] = []
    if not sym:
        missing.append("symbol")
    if side not in ("long", "short"):
        missing.append("side")
    if qty is None or qty <= 0:
        missing.append("qty")
    if pidx is None:
        missing.append("position_idx")
    return row, missing


def _canonical_identity_core(row: Mapping[str, Any]) -> dict[str, Any]:
    """ONLY the four immutable identity fields bound into the fingerprint (no display/audit fields)."""
    return {"symbol": row["symbol"], "side": row["side"],
            "qty": row["qty"], "position_idx": row["position_idx"]}


def _account_identity_evidence(account_evidence: Any) -> tuple[dict[str, Any], str, list[str]]:
    """Non-sensitive account identity evidence + its safe digest. Any credential-shaped key fails
    closed (never echoed)."""
    reasons: list[str] = []
    if not isinstance(account_evidence, Mapping):
        return {}, "", ["account_evidence_not_object"]
    safe = {k: v for k, v in account_evidence.items()}
    for k in safe:
        if _FORBIDDEN_ACCOUNT_KEY_RE.search(str(k)):
            reasons.append(f"account_evidence_forbidden_key:{k}")
    if reasons:
        return {}, "", reasons
    return safe, _digest(safe), reasons


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


# --------------------------------------------------------------------------- stage 1: snapshot
def build_pre_day1_protected_snapshot(
    *, pilot_id: str, day1_date: str, positions: Sequence[Any],
    positions_provenance: Mapping[str, Any], network_counter_components: Mapping[str, Any],
    account_evidence: Mapping[str, Any], source_endpoint: str, generated_at: str,
) -> dict[str, Any]:
    """Seal the immutable identity of every pre-existing (protected) nonzero position BEFORE any
    NEW-Pilot Day-1 order is authorized. Read-only; ``trading_authorized`` is always False."""
    blockers: list[str] = []
    pilot_id = str(pilot_id or "").strip()
    if not pilot_id:
        blockers.append("pilot_id_missing")
    if pilot_id in RETIRED_PILOT_IDS:
        blockers.append(f"retired_pilot_cannot_bootstrap:{pilot_id}")
    if not _valid_date(day1_date):
        blockers.append("day1_date_invalid")

    merged, net_blockers, breakdown = merge_network_counters(network_counter_components)
    blockers.extend(net_blockers)

    pagination_evidence, pag_blockers = _pagination_evidence(
        positions_provenance, prefix="protected_snapshot")
    blockers.extend(pag_blockers)

    account_safe, account_identity_digest, acct_blockers = _account_identity_evidence(account_evidence)
    blockers.extend(acct_blockers)

    canonical_rows: list[dict[str, Any]] = []
    for p in (positions or []):
        row, missing = _canonical_identity(p)
        if missing:
            blockers.append(f"protected_position_incomplete:{row['symbol'] or '?'}:{'+'.join(missing)}")
            continue
        canonical_rows.append(row)
    canonical_rows.sort(key=lambda r: (r["symbol"], r["position_idx"]))
    # A protected snapshot must actually observe at least one protected position to seal identity.
    if not canonical_rows and not blockers:
        blockers.append("no_protected_positions_observed")

    # Pagination row-count consistency: every observed nonzero position must be captured.
    nonzero = pagination_evidence.get("nonzero_position_count")
    if nonzero is not None and not pag_blockers and nonzero != len(canonical_rows):
        blockers.append(
            f"protected_snapshot_row_count_mismatch:{len(canonical_rows)}!={nonzero}")

    protected_symbol_set = sorted({r["symbol"] for r in canonical_rows})
    identity_core = {
        "kind": "pre_day1_protected_snapshot", "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "pilot_id": pilot_id, "day1_date": day1_date, "environment": ENVIRONMENT,
        "account_identity_digest": account_identity_digest,
        "canonical_protected_positions": [_canonical_identity_core(r) for r in canonical_rows],
        "pagination_evidence": pagination_evidence, "protected_symbol_set": protected_symbol_set,
        "generated_snapshot_evidence": {"source_endpoint": str(source_endpoint or ""),
                                        "generated_at": str(generated_at or "")},
    }
    snapshot_fp = _digest(identity_core)
    snapshot_valid = not blockers

    artifact: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION, "phase": PHASE_PRE_DAY1,
        "environment": ENVIRONMENT, "pilot_id": pilot_id, "day1_date": day1_date,
        "generated_at": str(generated_at or ""), "source_endpoint": str(source_endpoint or ""),
        "trading_authorized": False, "execution_ready": False,
        "snapshot_valid": snapshot_valid,
        "verdict": SNAPSHOT_READY if snapshot_valid else SNAPSHOT_BLOCKED,
        "blockers": sorted(blockers),
        "account_identity_evidence": account_safe,
        "account_identity_digest": account_identity_digest,
        "canonical_protected_positions": canonical_rows,
        "protected_symbol_set": protected_symbol_set,
        "canonical_protected_anchor": sorted(CANONICAL_PROTECTED_ANCHOR),
        "protected_position_count": len(canonical_rows),
        "pagination_evidence": pagination_evidence,
        "network_audit_counters": {**merged, "component_breakdown": breakdown},
        "private_mutating_request_count": merged["private_mutating_request_count"],
        "protected_position_snapshot_fingerprint": snapshot_fp if snapshot_valid else "",
    }
    artifact["protected_position_snapshot_digest"] = (
        _digest({k: v for k, v in artifact.items()
                 if k != "protected_position_snapshot_digest"}) if snapshot_valid else "")
    return artifact


def _snapshot_is_sealed(snapshot: Any) -> tuple[bool, list[str], str, str]:
    """Validate a snapshot artifact is READY and self-consistent (fingerprint + digest recompute).
    Returns (ok, reasons, snapshot_fingerprint, snapshot_digest)."""
    reasons: list[str] = []
    if not isinstance(snapshot, Mapping):
        return False, ["snapshot_not_object"], "", ""
    if snapshot.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        reasons.append("snapshot_schema_version_unexpected")
    if not snapshot.get("snapshot_valid") or snapshot.get("verdict") != SNAPSHOT_READY:
        reasons.append("snapshot_not_valid")
    fp = str(snapshot.get("protected_position_snapshot_fingerprint", ""))
    digest = str(snapshot.get("protected_position_snapshot_digest", ""))
    if not _SHA256_RE.match(fp):
        reasons.append("snapshot_fingerprint_missing")
    if not _SHA256_RE.match(digest):
        reasons.append("snapshot_digest_missing")
    if not reasons:
        recomputed = _digest({k: v for k, v in snapshot.items()
                              if k != "protected_position_snapshot_digest"})
        if recomputed != digest:
            reasons.append("snapshot_digest_mismatch")
    return (not reasons), reasons, fp, digest


# --------------------------------------------------------------------------- stage 2: binding
def build_day1_protected_binding(
    *, pilot_id: str, day1_date: str, allocation_intent_fingerprint: str,
    snapshot_artifact: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind the sealed PRE_DAY1 snapshot to the Day-1 allocation-intent fingerprint. Only a COMPLETE
    binding makes the Pilot execution-ready; a missing allocation fingerprint keeps it pending."""
    blockers: list[str] = []
    pilot_id = str(pilot_id or "").strip()
    if pilot_id in RETIRED_PILOT_IDS:
        blockers.append(f"retired_pilot_cannot_be_repaired:{pilot_id}")

    ok, snap_reasons, snapshot_fp, snapshot_digest = _snapshot_is_sealed(snapshot_artifact)
    if not ok:
        blockers.extend(f"snapshot_{r}" if not r.startswith("snapshot") else r for r in snap_reasons)

    snap = snapshot_artifact if isinstance(snapshot_artifact, Mapping) else {}
    if ok and str(snap.get("pilot_id", "")) != pilot_id:
        blockers.append("binding_pilot_id_mismatch")
    if ok and str(snap.get("day1_date", "")) != str(day1_date):
        blockers.append("binding_day1_date_mismatch")

    alloc_fp = str(allocation_intent_fingerprint or "")
    if not _SHA256_RE.match(alloc_fp):
        blockers.append("allocation_intent_fingerprint_missing")

    protected_symbols = sorted(snap.get("protected_symbol_set") or []) if ok else []
    binding_valid = not blockers
    binding_fp = _digest({
        "kind": "day1_protected_binding", "schema_version": BINDING_SCHEMA_VERSION,
        "pilot_id": pilot_id, "day1_date": str(day1_date),
        "allocation_intent_fingerprint": alloc_fp,
        "protected_position_snapshot_fingerprint": snapshot_fp,
        "protected_position_snapshot_digest": snapshot_digest,
        "protected_symbols": protected_symbols}) if binding_valid else ""

    artifact: dict[str, Any] = {
        "schema_version": BINDING_SCHEMA_VERSION, "environment": ENVIRONMENT,
        "pilot_id": pilot_id, "day1_date": str(day1_date),
        "allocation_intent_fingerprint": alloc_fp if binding_valid else "",
        "protected_position_snapshot_fingerprint": snapshot_fp if binding_valid else "",
        "protected_position_snapshot_digest": snapshot_digest if binding_valid else "",
        "protected_symbols": protected_symbols,
        "binding_valid": binding_valid, "execution_ready": binding_valid,
        "verdict": BINDING_COMPLETE if binding_valid else BINDING_BLOCKED,
        "blockers": sorted(blockers),
        "binding_fingerprint": binding_fp,
    }
    artifact["binding_digest"] = (
        _digest({k: v for k, v in artifact.items() if k != "binding_digest"})
        if binding_valid else "")
    return artifact


def _binding_is_sealed(binding: Any, snapshot_fp: str, snapshot_digest: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(binding, Mapping):
        return False, ["binding_not_object"]
    if binding.get("schema_version") != BINDING_SCHEMA_VERSION:
        reasons.append("binding_schema_version_unexpected")
    if not binding.get("binding_valid") or binding.get("verdict") != BINDING_COMPLETE:
        reasons.append("binding_not_complete")
    if not _SHA256_RE.match(str(binding.get("binding_fingerprint", ""))):
        reasons.append("binding_fingerprint_missing")
    if str(binding.get("protected_position_snapshot_fingerprint", "")) != snapshot_fp:
        reasons.append("binding_snapshot_fingerprint_mismatch")
    if str(binding.get("protected_position_snapshot_digest", "")) != snapshot_digest:
        reasons.append("binding_snapshot_digest_mismatch")
    if not reasons:
        recomputed = _digest({k: v for k, v in binding.items() if k != "binding_digest"})
        if recomputed != str(binding.get("binding_digest", "")):
            reasons.append("binding_digest_mismatch")
    return (not reasons), reasons


# --------------------------------------------------------------------------- stage 3: continuity
def verify_post_fill_protected_continuity(
    *, pilot_id: str, day1_date: str, snapshot_artifact: Mapping[str, Any],
    binding_artifact: Mapping[str, Any], post_fill_positions: Sequence[Any],
    post_fill_provenance: Mapping[str, Any], network_counter_components: Mapping[str, Any],
    strategy_symbols: Sequence[str], generated_at: str = "",
) -> dict[str, Any]:
    """Re-read positions post-fill and require EXACT protected identity continuity. Strategy and
    protected positions are counted/reported separately. Fail-closed on any change or an extra
    unauthorized protected position."""
    blockers: list[str] = []
    pilot_id = str(pilot_id or "").strip()
    if pilot_id in RETIRED_PILOT_IDS:
        blockers.append(f"retired_pilot_cannot_be_repaired:{pilot_id}")

    ok, snap_reasons, snapshot_fp, snapshot_digest = _snapshot_is_sealed(snapshot_artifact)
    blockers.extend(snap_reasons if not ok else [])
    bok, bind_reasons = _binding_is_sealed(binding_artifact, snapshot_fp, snapshot_digest)
    if not bok:
        blockers.extend(bind_reasons)

    merged, net_blockers, breakdown = merge_network_counters(network_counter_components)
    blockers.extend(net_blockers)

    pagination_evidence, pag_blockers = _pagination_evidence(
        post_fill_provenance, prefix="post_fill")
    blockers.extend(pag_blockers)

    strategy_set = {_sym(s) for s in (strategy_symbols or [])}
    snap = snapshot_artifact if isinstance(snapshot_artifact, Mapping) else {}
    expected_protected = {r["symbol"]: r for r in (snap.get("canonical_protected_positions") or [])
                          if isinstance(r, Mapping)}

    current: dict[str, dict[str, Any]] = {}
    for p in (post_fill_positions or []):
        row, missing = _canonical_identity(p)
        if missing:
            blockers.append(f"post_fill_position_incomplete:{row['symbol'] or '?'}:{'+'.join(missing)}")
            continue
        current[row["symbol"]] = row

    # Exact continuity for every protected position captured pre-Day-1.
    protected_checked: list[dict[str, Any]] = []
    for sym, exp in expected_protected.items():
        cur = current.get(sym)
        if cur is None:
            blockers.append(f"protected_position_missing:{sym}")
            continue
        if cur["side"] != exp.get("side"):
            blockers.append(f"protected_position_side_changed:{sym}")
        if cur["qty"] != exp.get("qty"):
            blockers.append(f"protected_position_qty_changed:{sym}")
        if cur["position_idx"] != exp.get("position_idx"):
            blockers.append(f"protected_position_idx_changed:{sym}")
        protected_checked.append(_canonical_identity_core(cur))

    # No position may exist that is neither a Day-1 strategy symbol nor a pre-captured protected one.
    for sym in current:
        if sym not in strategy_set and sym not in expected_protected:
            blockers.append(f"unauthorized_protected_position:{sym}")

    strategy_present = sorted(s for s in current if s in strategy_set)
    protected_present = sorted(s for s in current if s in expected_protected)
    continuity_ok = not blockers

    continuity_fp = _digest({
        "kind": "day1_post_fill_protected_continuity", "schema_version": CONTINUITY_SCHEMA_VERSION,
        "pilot_id": pilot_id, "day1_date": str(day1_date),
        "binding_fingerprint": str((binding_artifact or {}).get("binding_fingerprint", "")),
        "protected_position_snapshot_fingerprint": snapshot_fp,
        "protected_continuity": sorted(protected_checked, key=lambda r: (r["symbol"], r["position_idx"])),
    }) if continuity_ok else ""

    return {
        "schema_version": CONTINUITY_SCHEMA_VERSION, "environment": ENVIRONMENT,
        "pilot_id": pilot_id, "day1_date": str(day1_date), "generated_at": str(generated_at or ""),
        "trading_authorized": False, "execution_ready": False,
        "protected_position_identity_continuity": CONTINUITY_PASS if continuity_ok else CONTINUITY_BLOCKED,
        "continuity_pass": continuity_ok,
        "verdict": CONTINUITY_PASS if continuity_ok else CONTINUITY_BLOCKED,
        "blockers": sorted(blockers),
        "binding_fingerprint": str((binding_artifact or {}).get("binding_fingerprint", "")),
        "protected_position_snapshot_fingerprint": snapshot_fp,
        "post_fill_continuity_fingerprint": continuity_fp,
        # Strategy vs protected positions are ALWAYS counted and reported separately.
        "strategy_position_count": len(strategy_present),
        "strategy_positions_present": strategy_present,
        "protected_position_count": len(protected_present),
        "protected_positions_present": protected_present,
        "protected_continuity_evidence": [
            {**_canonical_identity_core(current[s]), "display_side": current[s]["display_side"]}
            for s in protected_present] if continuity_ok else [],
        "pagination_evidence": pagination_evidence,
        "network_audit_counters": {**merged, "component_breakdown": breakdown},
        "private_mutating_request_count": merged["private_mutating_request_count"],
    }
