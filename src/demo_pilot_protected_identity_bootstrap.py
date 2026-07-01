"""TASK-014CA: READ-ONLY pre-Day-1 protected-position identity bootstrap for a NEW Demo Pilot.

Before any NEW-Pilot Day-1 strategy order can be authorized, this seals the IMMUTABLE identity of
every pre-existing PROTECTED position (``symbol in`` the canonical PROTECTED_SYMBOLS anchor) from a
formal Bybit Demo PRIVATE read-only, fully-paginated snapshot. It NEVER sends / cancels / amends /
closes / resizes anything, never changes leverage or position mode, never initializes a sender,
never calls an execution adapter, never advances a Pilot, and never authorizes execution.

Two ORTHOGONAL states are SEMANTICALLY self-verifying (FIX3): evidence validity is separate from
bootstrap readiness, and neither may be trusted from a stored boolean -- both are RE-DERIVED from the
canonical classification and exact-matched:

  * ``snapshot_evidence_valid`` -- the sealed protected identity is trustworthy (complete pagination
    with validated per-page request evidence, accounted counters, no mutation, no duplicate composite
    key, complete protected identity + audit, valid Demo/account evidence, not a retired Pilot).
  * ``bootstrap_ready`` -- RE-DERIVED via ``derive_snapshot_readiness`` from the canonical
    non-protected classification; ``_snapshot_is_sealed`` re-derives and exact-matches the stored
    ``bootstrap_ready`` / ``bootstrap_verdict`` / ``readiness_blockers``. A flipped stored flag can
    never make an ownership-unresolved account look ready.

Binding ``execution_ready`` is re-derived from the sealed snapshot's readiness (never from the
binding's own stored boolean); continuity carries a full fingerprint + digest and is verdict-replayed
from its canonical evidence. Retired Pilots can neither bootstrap nor be repaired.
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
POSITIONS_ENDPOINT = "/v5/position/list"

EVIDENCE_VALID = "PROTECTED_IDENTITY_EVIDENCE_VALID"
EVIDENCE_INVALID = "PROTECTED_IDENTITY_EVIDENCE_INVALID"
BOOTSTRAP_READY = "NEW_PILOT_BOOTSTRAP_READY"
BOOTSTRAP_BLOCKED = "NEW_PILOT_BOOTSTRAP_BLOCKED"
BINDING_EVIDENCE_VALID = "PROTECTED_IDENTITY_BINDING_EVIDENCE_VALID"
BINDING_EVIDENCE_INVALID = "PROTECTED_IDENTITY_BINDING_EVIDENCE_INVALID"
CONTINUITY_PASS = "PASS"
CONTINUITY_BLOCKED = "PROTECTED_IDENTITY_CONTINUITY_BLOCKED"

OWNERSHIP_READINESS_BLOCKER = "preexisting_nonprotected_positions_require_ownership_resolution"

PAGINATION_COMPLETE_REASONS = frozenset({"empty_cursor"})
CANONICAL_PROTECTED_ANCHOR = frozenset(_NX_PROTECTED_SYMBOLS)
RETIRED_PILOT_IDS = frozenset({"BYBIT_DEMO_PILOT_7D_202606_V1"})

_REQUIRED_ACCOUNT_FIELDS = ("account_mode", "demo_flag", "endpoint_family")
_PAGE_EVIDENCE_FIELDS = ("page_number", "request_started_at_utc", "response_received_at_utc",
                         "request_elapsed_ms", "request_cursor_present",
                         "response_next_cursor_present", "raw_row_count", "nonzero_row_count",
                         "endpoint")

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FORBIDDEN_ACCOUNT_KEY_RE = re.compile(r"api[_-]?key|secret|signature|passphrase|x-bapi", re.I)

_CRUN = None


def _crun():
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
    return {"symbol": row["symbol"], "side": row["side"],
            "qty": row["qty"], "position_idx": row["position_idx"]}


def _sorted_cores(rows: Any) -> list[dict[str, Any]]:
    rows = rows if isinstance(rows, list) else []
    return sorted((_identity_core(r) for r in rows if isinstance(r, Mapping)),
                  key=lambda r: (r["symbol"], r["position_idx"] if r["position_idx"] is not None else -1))


def _account_audit_evidence(account_evidence: Any) -> tuple[dict[str, Any], str, bool, list[str]]:
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


def validate_position_page_request_evidence(
    pagination_evidence: Mapping[str, Any], page_request_evidence: Any, *, prefix: str,
) -> list[str]:
    """Formally validate the per-page read-only request provenance against the pagination summary.
    Never inspects api key / signature / headers / raw query. Returns a list of reasons (empty when
    fully consistent)."""
    reasons: list[str] = []
    if not isinstance(page_request_evidence, list):
        return [f"{prefix}_page_evidence_not_list"]
    page_count = _as_int((pagination_evidence or {}).get("page_count"))
    api_rows = _as_int((pagination_evidence or {}).get("api_position_rows"))
    nonzero_total_expected = _as_int((pagination_evidence or {}).get("nonzero_position_count"))
    if page_count is None or len(page_request_evidence) != page_count:
        reasons.append(f"{prefix}_page_evidence_count_mismatch:{len(page_request_evidence)}!={page_count}")
    raw_sum = nonzero_sum = 0
    n = len(page_request_evidence)
    for i, pg in enumerate(page_request_evidence):
        tag = f"{prefix}_page{i + 1}"
        if not isinstance(pg, Mapping):
            reasons.append(f"{tag}_not_object")
            continue
        if _as_int(pg.get("page_number")) != i + 1:
            reasons.append(f"{tag}_page_number_not_sequential")
        if str(pg.get("endpoint", "")) != POSITIONS_ENDPOINT:
            reasons.append(f"{tag}_endpoint_unexpected")
        if not str(pg.get("request_started_at_utc", "")).strip():
            reasons.append(f"{tag}_request_started_missing")
        if not str(pg.get("response_received_at_utc", "")).strip():
            reasons.append(f"{tag}_response_received_missing")
        elapsed = pg.get("request_elapsed_ms")
        if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or elapsed < 0:
            reasons.append(f"{tag}_request_elapsed_invalid")
        if not isinstance(pg.get("request_cursor_present"), bool):
            reasons.append(f"{tag}_request_cursor_present_not_bool")
        if not isinstance(pg.get("response_next_cursor_present"), bool):
            reasons.append(f"{tag}_response_next_cursor_present_not_bool")
        raw = _as_int(pg.get("raw_row_count"))
        nz = _as_int(pg.get("nonzero_row_count"))
        if raw is None or raw < 0:
            reasons.append(f"{tag}_raw_row_count_invalid")
            raw = 0
        if nz is None or nz < 0:
            reasons.append(f"{tag}_nonzero_row_count_invalid")
            nz = 0
        if nz > raw:
            reasons.append(f"{tag}_nonzero_exceeds_raw")
        raw_sum += raw
        nonzero_sum += nz
        is_first, is_last = (i == 0), (i == n - 1)
        # Full cursor-chain shape: page1 has no request cursor; every continuation page (>=2) does;
        # every non-final page hands out a next cursor; the final page does not.
        if is_first and pg.get("request_cursor_present") is not False:
            reasons.append(f"{tag}_first_page_cursor_present")
        if not is_first and pg.get("request_cursor_present") is not True:
            reasons.append(f"{tag}_continuation_cursor_absent")
        if is_last and pg.get("response_next_cursor_present") is not False:
            reasons.append(f"{tag}_final_page_next_cursor_present")
        if not is_last and pg.get("response_next_cursor_present") is not True:
            reasons.append(f"{tag}_nonfinal_next_cursor_absent")
    if api_rows is not None and raw_sum != api_rows:
        reasons.append(f"{prefix}_page_raw_row_total_mismatch:{raw_sum}!={api_rows}")
    if nonzero_total_expected is not None and nonzero_sum != nonzero_total_expected:
        reasons.append(f"{prefix}_page_nonzero_row_total_mismatch:{nonzero_sum}!={nonzero_total_expected}")
    return reasons


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


# --------------------------------------------------------------------------- readiness derivation
def derive_snapshot_readiness(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Re-derive bootstrap readiness from the canonical classification (never trust a stored flag).
    A non-empty ``preexisting_nonprotected_positions`` set is an unresolved-ownership readiness
    blocker; readiness also requires evidence validity."""
    nonprot = snapshot.get("preexisting_nonprotected_positions") if isinstance(snapshot, Mapping) else None
    nonprot = nonprot if isinstance(nonprot, list) else []
    evidence_valid = bool(snapshot.get("snapshot_evidence_valid")) if isinstance(snapshot, Mapping) else False
    blockers: list[str] = []
    if nonprot:
        blockers.append(OWNERSHIP_READINESS_BLOCKER)
    ready = evidence_valid and not blockers
    return {"expected_readiness_blockers": sorted(blockers),
            "expected_bootstrap_ready": ready,
            "expected_bootstrap_verdict": BOOTSTRAP_READY if ready else BOOTSTRAP_BLOCKED}


def _revalidate_observed(all_observed: Sequence[Any]) -> tuple[list[str], list[dict], list[dict]]:
    """Re-run the exact classification/validation of build_pre_day1_protected_snapshot over the
    STORED ``all_observed_nonzero_positions`` rows. Returns (blockers, protected, nonprotected)."""
    blockers: list[str] = []
    protected: list[dict[str, Any]] = []
    nonprotected: list[dict[str, Any]] = []
    seen: set[tuple[str, Any]] = set()
    for row in (all_observed or []):
        if not isinstance(row, Mapping):
            blockers.append("observed_row_not_object")
            continue
        sym = _sym(row.get("symbol"))
        side = _norm_side(row.get("side"))
        qty = _dec(row.get("qty"))
        pidx = _as_int(row.get("position_idx"))
        key = (sym, pidx)
        if key in seen:
            blockers.append(f"duplicate_position_composite_key:{sym or '?'}:{pidx}")
            continue
        seen.add(key)
        miss_id: list[str] = []
        if not sym:
            miss_id.append("symbol")
        if side not in ("long", "short"):
            miss_id.append("side")
        if qty is None or qty <= 0:
            miss_id.append("qty")
        if pidx is None:
            miss_id.append("position_idx")
        if sym in CANONICAL_PROTECTED_ANCHOR:
            if miss_id:
                blockers.append(f"protected_position_incomplete:{sym or '?'}:{'+'.join(miss_id)}")
                continue
            miss_audit: list[str] = []
            if row.get("entry_price") is None:
                miss_audit.append("entry_price")
            if row.get("leverage") is None:
                miss_audit.append("leverage")
            if miss_audit:
                blockers.append(f"protected_position_audit_incomplete:{sym}:{'+'.join(miss_audit)}")
            protected.append(dict(row))
        elif sym:
            nonprotected.append(dict(row))
        else:
            blockers.append("observed_position_missing_symbol")
    protected.sort(key=lambda r: (r["symbol"], r["position_idx"]))
    nonprotected.sort(key=lambda r: (r["symbol"], r["position_idx"] if r["position_idx"] is not None else -1))
    return blockers, protected, nonprotected


def derive_snapshot_evidence_semantics(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Re-derive snapshot EVIDENCE validity purely from the artifact's stored canonical evidence --
    identity, account, network (re-merged from the component breakdown), pagination + page timing,
    per-row validation, and the EXACT protected/non-protected partition recomputed from
    ``all_observed_nonzero_positions``. Never trusts the stored ``snapshot_evidence_valid``."""
    b: list[str] = []
    if not isinstance(snapshot, Mapping):
        return {"expected_evidence_blockers": ["snapshot_not_object"],
                "expected_snapshot_evidence_valid": False, "expected_snapshot_evidence_verdict": EVIDENCE_INVALID}
    pilot_id = str(snapshot.get("pilot_id", "")).strip()
    if not pilot_id:
        b.append("pilot_id_missing")
    if pilot_id in RETIRED_PILOT_IDS:
        b.append(f"retired_pilot_cannot_bootstrap:{pilot_id}")
    if not _valid_date(snapshot.get("day1_date")):
        b.append("day1_date_invalid")
    if snapshot.get("environment") != ENVIRONMENT:
        b.append("snapshot_environment_unexpected")

    # Account evidence (re-validate + re-digest; forbid double-truth with demo_runtime_proof).
    acct = snapshot.get("account_identity_evidence")
    safe, digest, _avail, acct_reasons = _account_audit_evidence(acct)
    b.extend(acct_reasons)
    if not acct_reasons and digest != str(snapshot.get("account_identity_digest", "")):
        b.append("account_identity_digest_mismatch")
    if snapshot.get("demo_runtime_proof") != (acct if isinstance(acct, Mapping) else None):
        b.append("account_demo_runtime_proof_divergent")

    # Network evidence: re-merge from the component breakdown and exact-match the top-level totals.
    nac = snapshot.get("network_audit_counters") or {}
    merged, net_blockers, _bd = merge_network_counters(nac.get("component_breakdown") or {})
    b.extend(net_blockers)
    for k in ("private_read_only_request_count", "public_read_only_request_count",
              "private_mutating_request_count"):
        if _as_int(nac.get(k)) != merged[k]:
            b.append(f"network_counter_top_level_mismatch:{k}")
    if _as_int(snapshot.get("private_mutating_request_count")) != merged["private_mutating_request_count"]:
        b.append("private_mutating_top_level_mismatch")

    # Pagination + page timing.
    pag = snapshot.get("pagination_evidence") or {}
    _pe, pag_blockers = _pagination_evidence(pag, prefix="protected_snapshot")
    b.extend(pag_blockers)
    b.extend(validate_position_page_request_evidence(
        pag, snapshot.get("position_page_request_evidence"), prefix="protected_snapshot"))

    # Exact canonical partition, recomputed from all_observed_nonzero_positions.
    all_obs = snapshot.get("all_observed_nonzero_positions") or []
    row_blockers, exp_protected, exp_nonprot = _revalidate_observed(all_obs)
    b.extend(row_blockers)
    stored_protected = snapshot.get("canonical_protected_positions") or []
    stored_nonprot = snapshot.get("preexisting_nonprotected_positions") or []
    if sorted(exp_protected, key=lambda r: (r["symbol"], r["position_idx"])) != \
            sorted((dict(r) for r in stored_protected if isinstance(r, Mapping)),
                   key=lambda r: (r["symbol"], r["position_idx"])):
        b.append("canonical_protected_partition_mismatch")
    if [dict(r) for r in exp_nonprot] != [dict(r) for r in stored_nonprot if isinstance(r, Mapping)]:
        b.append("preexisting_nonprotected_partition_mismatch")

    exp_symbols = sorted({r["symbol"] for r in exp_protected})
    if _as_int(snapshot.get("protected_position_count")) != len(exp_protected):
        b.append("protected_position_count_mismatch")
    if _as_int(snapshot.get("preexisting_nonprotected_position_count")) != len(exp_nonprot):
        b.append("preexisting_nonprotected_position_count_mismatch")
    if _as_int(snapshot.get("all_observed_nonzero_count")) != len(all_obs):
        b.append("all_observed_nonzero_count_mismatch")
    if sorted(snapshot.get("protected_symbol_set") or []) != exp_symbols:
        b.append("protected_symbol_set_mismatch")
    if snapshot.get("protected_positions_summary") != {"count": len(exp_protected), "symbols": exp_symbols}:
        b.append("protected_positions_summary_mismatch")
    if sorted(snapshot.get("canonical_protected_anchor") or []) != sorted(CANONICAL_PROTECTED_ANCHOR):
        b.append("canonical_protected_anchor_mismatch")
    if snapshot.get("position_mode_evidence") != _position_mode_evidence(all_obs):
        b.append("position_mode_evidence_mismatch")
    if len(exp_protected) + len(exp_nonprot) != len(all_obs):
        b.append("classification_count_inconsistent")
    if _as_int(pag.get("nonzero_position_count")) != len(all_obs):
        b.append("pagination_nonzero_mismatch")

    valid = not b
    return {"expected_evidence_blockers": sorted(b),
            "expected_snapshot_evidence_valid": valid,
            "expected_snapshot_evidence_verdict": EVIDENCE_VALID if valid else EVIDENCE_INVALID}


def canonical_bootstrap_readiness_fingerprint(snapshot: Mapping[str, Any]) -> str:
    """Binds the canonical evidence that DETERMINES readiness: the protected + non-protected identity
    classification and the observed counts. Bound into the snapshot fingerprint so a deleted /
    reclassified position cannot silently change readiness."""
    return _digest({
        "kind": "bootstrap_readiness",
        "canonical_protected_positions": _sorted_cores(snapshot.get("canonical_protected_positions")),
        "preexisting_nonprotected_positions": _sorted_cores(snapshot.get("preexisting_nonprotected_positions")),
        "protected_position_count": snapshot.get("protected_position_count"),
        "preexisting_nonprotected_position_count": snapshot.get("preexisting_nonprotected_position_count"),
        "all_observed_nonzero_count": snapshot.get("all_observed_nonzero_count"),
    })


# --------------------------------------------------------------------------- canonical recompute
def canonical_protected_snapshot_fingerprint(snapshot: Mapping[str, Any]) -> str:
    """Recompute the identity fingerprint from the single ``canonical_protected_positions`` source
    PLUS the bootstrap-readiness fingerprint (so readiness-affecting evidence is bound). An empty
    protected set binds an explicit empty list."""
    return _digest({
        "kind": "pre_day1_protected_snapshot", "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "pilot_id": snapshot.get("pilot_id"), "day1_date": snapshot.get("day1_date"),
        "environment": snapshot.get("environment"),
        "account_identity_digest": snapshot.get("account_identity_digest"),
        "canonical_protected_positions": _sorted_cores(snapshot.get("canonical_protected_positions")),
        "pagination_evidence": snapshot.get("pagination_evidence"),
        "position_page_request_evidence_digest": _digest(snapshot.get("position_page_request_evidence") or []),
        "protected_symbol_set": snapshot.get("protected_symbol_set"),
        "generated_snapshot_evidence": snapshot.get("generated_snapshot_evidence"),
        "bootstrap_readiness_fingerprint": canonical_bootstrap_readiness_fingerprint(snapshot),
    })


def canonical_protected_snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    return _digest({k: v for k, v in snapshot.items() if k != "protected_position_snapshot_digest"})


def canonical_binding_fingerprint(binding: Mapping[str, Any]) -> str:
    return _digest({
        "kind": "day1_protected_binding", "schema_version": BINDING_SCHEMA_VERSION,
        "pilot_id": binding.get("pilot_id"), "day1_date": binding.get("day1_date"),
        "allocation_intent_fingerprint": binding.get("allocation_intent_fingerprint"),
        "allocation_artifact_source_sha256": binding.get("allocation_artifact_source_sha256"),
        "protected_position_snapshot_fingerprint": binding.get("protected_position_snapshot_fingerprint"),
        "protected_position_snapshot_digest": binding.get("protected_position_snapshot_digest"),
        "protected_symbols": binding.get("protected_symbols"),
        "binding_evidence_valid": binding.get("binding_evidence_valid"),
        "execution_ready": binding.get("execution_ready"),
        "snapshot_bootstrap_ready": binding.get("snapshot_bootstrap_ready"),
        "readiness_blockers": binding.get("readiness_blockers")})


def canonical_binding_digest(binding: Mapping[str, Any]) -> str:
    return _digest({k: v for k, v in binding.items() if k != "binding_digest"})


def canonical_continuity_fingerprint(continuity: Mapping[str, Any]) -> str:
    return _digest({
        "kind": "day1_post_fill_protected_continuity", "schema_version": CONTINUITY_SCHEMA_VERSION,
        "pilot_id": continuity.get("pilot_id"), "day1_date": continuity.get("day1_date"),
        "environment": continuity.get("environment"),
        "protected_position_snapshot_fingerprint": continuity.get("protected_position_snapshot_fingerprint"),
        "binding_fingerprint": continuity.get("binding_fingerprint"),
        "allocation_intent_fingerprint": continuity.get("allocation_intent_fingerprint"),
        "allocation_artifact_source_sha256": continuity.get("allocation_artifact_source_sha256"),
        "canonical_strategy_symbols": continuity.get("canonical_strategy_symbols"),
        "canonical_post_fill_positions": _sorted_cores(continuity.get("canonical_post_fill_positions")),
        "protected_continuity": _sorted_cores(continuity.get("protected_continuity_evidence")),
        "pagination_evidence": continuity.get("pagination_evidence"),
        "position_page_request_evidence_digest": _digest(continuity.get("position_page_request_evidence") or []),
        "network_audit_counters": continuity.get("network_audit_counters"),
        "private_mutating_request_count": continuity.get("private_mutating_request_count"),
        "strategy_position_count": continuity.get("strategy_position_count"),
        "protected_position_count": continuity.get("protected_position_count"),
        "blockers": continuity.get("blockers"),
        "continuity_pass": continuity.get("continuity_pass"),
        "verdict": continuity.get("verdict")})


def canonical_continuity_digest(continuity: Mapping[str, Any]) -> str:
    return _digest({k: v for k, v in continuity.items() if k != "post_fill_continuity_digest"})


# --------------------------------------------------------------------------- allocation validation
def validate_day1_allocation_artifact(
    allocation_artifact: Any, *, pilot_id: str, day1_date: str,
) -> tuple[bool, list[str], str]:
    """Validate a FORMAL Day-1 allocation artifact with the production allocation-fingerprint
    recompute (pilot / date / capital base / 50 symbols / 25-25 sides / symbol uniqueness /
    stored == recomputed). NOTE (FIX3): the current production allocation-intent artifact does NOT
    carry a schema_version / verdict / digest field, so only ``environment`` (when present) is
    additionally validated -- no absent metadata is claimed. Returns (ok, reasons, recomputed_fp)."""
    reasons: list[str] = []
    if not isinstance(allocation_artifact, Mapping):
        return False, ["allocation_artifact_not_object"], ""
    if str(allocation_artifact.get("pilot_id", "")) != str(pilot_id):
        reasons.append("allocation_pilot_id_mismatch")
    if str(allocation_artifact.get("date", "")) != str(day1_date):
        reasons.append("allocation_date_mismatch")
    if str(allocation_artifact.get("strategy_capital_base_usd", "")) != STRATEGY_CAPITAL_BASE_USD:
        reasons.append("allocation_capital_base_mismatch")
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
    """Seal every pre-existing PROTECTED nonzero position's immutable identity BEFORE any NEW-Pilot
    Day-1 order. Evidence validity and readiness are distinct; readiness is derived from the
    classification (see ``derive_snapshot_readiness``)."""
    evidence_blockers: list[str] = []
    pilot_id = str(pilot_id or "").strip()
    if not pilot_id:
        evidence_blockers.append("pilot_id_missing")
    if pilot_id in RETIRED_PILOT_IDS:
        evidence_blockers.append(f"retired_pilot_cannot_bootstrap:{pilot_id}")
    if not _valid_date(day1_date):
        evidence_blockers.append("day1_date_invalid")

    merged, net_blockers, breakdown = merge_network_counters(network_counter_components)
    evidence_blockers.extend(net_blockers)

    pagination_evidence, pag_blockers = _pagination_evidence(positions_provenance, prefix="protected_snapshot")
    evidence_blockers.extend(pag_blockers)
    page_request_evidence = _canonical_page_evidence(positions_provenance)
    evidence_blockers.extend(validate_position_page_request_evidence(
        pagination_evidence, page_request_evidence, prefix="protected_snapshot"))

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

    nonzero = pagination_evidence.get("nonzero_position_count")
    if nonzero is not None and not pag_blockers and nonzero != len(all_observed):
        evidence_blockers.append(f"protected_snapshot_row_count_mismatch:{len(all_observed)}!={nonzero}")
    if len(protected_rows) + len(nonprotected_rows) != len(all_observed):
        evidence_blockers.append("protected_snapshot_classification_count_inconsistent")

    protected_symbol_set = sorted({r["symbol"] for r in protected_rows})
    snapshot_evidence_valid = not evidence_blockers
    # Derive readiness from the classification (not a free flag).
    readiness_blockers = [OWNERSHIP_READINESS_BLOCKER] if nonprotected_rows else []
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
        "canonical_protected_positions": protected_rows,
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
    artifact["bootstrap_readiness_fingerprint"] = (
        canonical_bootstrap_readiness_fingerprint(artifact) if snapshot_evidence_valid else "")
    artifact["protected_position_snapshot_fingerprint"] = (
        canonical_protected_snapshot_fingerprint(artifact) if snapshot_evidence_valid else "")
    artifact["protected_position_snapshot_digest"] = (
        canonical_protected_snapshot_digest(artifact) if snapshot_evidence_valid else "")
    return artifact


def _snapshot_is_sealed(snapshot: Any) -> tuple[bool, list[str], str, str, bool]:
    """Validate a snapshot has VALID EVIDENCE and is self-consistent: recompute both fingerprints +
    the digest, RE-DERIVE readiness from the classification and exact-match the stored
    bootstrap_ready / verdict / readiness_blockers / blockers, re-check single-source classification
    consistency, and re-validate the page request evidence. Returns
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
        if canonical_bootstrap_readiness_fingerprint(snapshot) != str(snapshot.get("bootstrap_readiness_fingerprint", "")):
            reasons.append("snapshot_readiness_fingerprint_mismatch")
        if canonical_protected_snapshot_fingerprint(snapshot) != fp:
            reasons.append("snapshot_fingerprint_mismatch")
        if canonical_protected_snapshot_digest(snapshot) != digest:
            reasons.append("snapshot_digest_mismatch")
        # single-source classification consistency
        canon = snapshot.get("canonical_protected_positions") or []
        summary = snapshot.get("protected_positions_summary") or {}
        canon_syms = sorted({r.get("symbol") for r in canon if isinstance(r, Mapping)})
        if summary.get("count") != len(canon) or sorted(summary.get("symbols") or []) != canon_syms:
            reasons.append("snapshot_protected_summary_inconsistent")
        nonprot = snapshot.get("preexisting_nonprotected_positions") or []
        allobs = snapshot.get("all_observed_nonzero_positions") or []
        if len(canon) + len(nonprot) != len(allobs):
            reasons.append("snapshot_classification_count_inconsistent")
        pag = snapshot.get("pagination_evidence") or {}
        if _as_int(pag.get("nonzero_position_count")) != len(allobs):
            reasons.append("snapshot_pagination_nonzero_mismatch")
        reasons.extend(validate_position_page_request_evidence(
            pag, snapshot.get("position_page_request_evidence"), prefix="protected_snapshot"))
        # RE-DERIVE evidence validity from the stored canonical evidence -- never trust the flags.
        ev = derive_snapshot_evidence_semantics(snapshot)
        if bool(snapshot.get("snapshot_evidence_valid")) != ev["expected_snapshot_evidence_valid"]:
            reasons.append("snapshot_evidence_valid_replay_mismatch")
        if str(snapshot.get("snapshot_evidence_verdict", "")) != ev["expected_snapshot_evidence_verdict"]:
            reasons.append("snapshot_evidence_verdict_replay_mismatch")
        if sorted(snapshot.get("evidence_blockers") or []) != ev["expected_evidence_blockers"]:
            reasons.append("snapshot_evidence_blockers_replay_mismatch")
        # RE-DERIVE readiness -- never trust the stored flag
        der = derive_snapshot_readiness(snapshot)
        if bool(snapshot.get("bootstrap_ready")) != der["expected_bootstrap_ready"]:
            reasons.append("snapshot_bootstrap_ready_derivation_mismatch")
        if str(snapshot.get("bootstrap_verdict", "")) != der["expected_bootstrap_verdict"]:
            reasons.append("snapshot_bootstrap_verdict_derivation_mismatch")
        if sorted(snapshot.get("readiness_blockers") or []) != der["expected_readiness_blockers"]:
            reasons.append("snapshot_readiness_blockers_derivation_mismatch")
        if sorted(snapshot.get("blockers") or []) != sorted((snapshot.get("evidence_blockers") or []) + der["expected_readiness_blockers"]):
            reasons.append("snapshot_blockers_inconsistent")
    bootstrap_ready = bool(snapshot.get("bootstrap_ready")) if isinstance(snapshot, Mapping) else False
    return (not reasons), reasons, fp, digest, bootstrap_ready


# --------------------------------------------------------------------------- stage 2: binding
def build_day1_protected_binding(
    *, pilot_id: str, day1_date: str, day1_allocation_artifact: Mapping[str, Any],
    snapshot_artifact: Mapping[str, Any], allocation_source_path: str | None = None,
    allocation_source_sha256: str | None = None,
) -> dict[str, Any]:
    """Bind a FORMAL Day-1 allocation artifact to the sealed snapshot. ``execution_ready`` is derived
    from the sealed snapshot's RE-DERIVED readiness (never the snapshot's own stored boolean)."""
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

    der = derive_snapshot_readiness(snap) if ok else {"expected_readiness_blockers": [], "expected_bootstrap_ready": False}
    readiness_blockers = der["expected_readiness_blockers"]
    binding_evidence_valid = not evidence_blockers
    execution_ready = binding_evidence_valid and bool(ok and snap_bootstrap_ready)

    artifact: dict[str, Any] = {
        "schema_version": BINDING_SCHEMA_VERSION, "environment": ENVIRONMENT,
        "pilot_id": pilot_id, "day1_date": str(day1_date),
        "allocation_intent_fingerprint": alloc_fp if binding_evidence_valid else "",
        "allocation_artifact_source_path": str(allocation_source_path or ""),
        "allocation_artifact_source_sha256": str(allocation_source_sha256 or ""),
        "protected_position_snapshot_fingerprint": snapshot_fp if binding_evidence_valid else "",
        "protected_position_snapshot_digest": snapshot_digest if binding_evidence_valid else "",
        "protected_symbols": sorted(snap.get("protected_symbol_set") or []) if ok else [],
        "snapshot_bootstrap_ready": bool(ok and snap_bootstrap_ready),
        "readiness_blockers": readiness_blockers,
        "binding_evidence_valid": binding_evidence_valid,
        "binding_evidence_verdict": BINDING_EVIDENCE_VALID if binding_evidence_valid else BINDING_EVIDENCE_INVALID,
        "execution_ready": execution_ready,
        "evidence_blockers": sorted(evidence_blockers),
        "blockers": sorted(evidence_blockers + (readiness_blockers if binding_evidence_valid else [])),
    }
    artifact["binding_fingerprint"] = canonical_binding_fingerprint(artifact) if binding_evidence_valid else ""
    artifact["binding_digest"] = canonical_binding_digest(artifact) if binding_evidence_valid else ""
    return artifact


def _binding_is_sealed(binding: Any, snapshot: Any, *, allocation: Any = None,
                       allocation_source_sha256: str | None = None,
                       require_execution_ready: bool = True) -> tuple[bool, list[str]]:
    """Validate a binding against the FORMAL snapshot (and, when supplied, the FORMAL allocation
    artifact). The snapshot must itself be sealed; ``protected_symbols`` / ``execution_ready`` /
    ``readiness_blockers`` are RE-DERIVED and exact-matched (never trusted from the binding's stored
    fields). When ``allocation`` is provided its recomputed fingerprint must equal the binding's, and
    ``allocation_source_sha256`` (when provided) must equal the binding's recorded file SHA."""
    reasons: list[str] = []
    if not isinstance(binding, Mapping):
        return False, ["binding_not_object"]
    ok, snap_reasons, snapshot_fp, snapshot_digest, snap_ready = _snapshot_is_sealed(snapshot)
    if not ok:
        reasons.extend(f"binding_snapshot_{r}" for r in snap_reasons)
    snap = snapshot if isinstance(snapshot, Mapping) else {}
    if binding.get("schema_version") != BINDING_SCHEMA_VERSION:
        reasons.append("binding_schema_version_unexpected")
    if binding.get("environment") != ENVIRONMENT:
        reasons.append("binding_environment_unexpected")
    if str(binding.get("protected_position_snapshot_fingerprint", "")) != snapshot_fp:
        reasons.append("binding_snapshot_fingerprint_mismatch")
    if str(binding.get("protected_position_snapshot_digest", "")) != snapshot_digest:
        reasons.append("binding_snapshot_digest_mismatch")
    if not _HEX64_RE.match(str(binding.get("allocation_intent_fingerprint", ""))):
        reasons.append("binding_allocation_fingerprint_missing")

    # RE-DERIVE protected_symbols from the sealed snapshot (never the binding's own list).
    expected_symbols = sorted(snap.get("protected_symbol_set") or []) if ok else []
    if sorted(binding.get("protected_symbols") or []) != expected_symbols:
        reasons.append("binding_protected_symbols_mismatch")

    # Validate the FORMAL allocation artifact when supplied and match the binding's bound fp + sha.
    if allocation is not None:
        aok, areasons, afp = validate_day1_allocation_artifact(
            allocation, pilot_id=str(binding.get("pilot_id", "")), day1_date=str(binding.get("day1_date", "")))
        if not aok:
            reasons.extend(f"binding_allocation_{r}" for r in areasons)
        elif afp != str(binding.get("allocation_intent_fingerprint", "")):
            reasons.append("binding_allocation_fingerprint_mismatch")
    if allocation_source_sha256 is not None and \
            str(allocation_source_sha256) != str(binding.get("allocation_artifact_source_sha256", "")):
        reasons.append("binding_allocation_source_sha256_mismatch")

    der = derive_snapshot_readiness(snap)
    if bool(binding.get("snapshot_bootstrap_ready")) != bool(ok and snap_ready):
        reasons.append("binding_snapshot_bootstrap_ready_mismatch")
    if sorted(binding.get("readiness_blockers") or []) != der["expected_readiness_blockers"]:
        reasons.append("binding_readiness_blockers_mismatch")
    # Re-derive binding evidence validity: valid ONLY when the snapshot sealed, symbols match, no
    # retired pilot, and (if provided) the allocation is valid.
    expected_evidence_valid = not [r for r in reasons if not r.startswith("binding_not_execution_ready")]
    if bool(binding.get("binding_evidence_valid")) != expected_evidence_valid or \
            binding.get("binding_evidence_verdict") != (BINDING_EVIDENCE_VALID if expected_evidence_valid else BINDING_EVIDENCE_INVALID):
        reasons.append("binding_evidence_valid_mismatch")
    expected_exec = expected_evidence_valid and bool(ok and snap_ready)
    if bool(binding.get("execution_ready")) != expected_exec:
        reasons.append("binding_execution_ready_mismatch")
    if require_execution_ready and not expected_exec:
        reasons.append("binding_not_execution_ready")
    if not reasons:
        if canonical_binding_fingerprint(binding) != str(binding.get("binding_fingerprint", "")):
            reasons.append("binding_fingerprint_mismatch")
        if canonical_binding_digest(binding) != str(binding.get("binding_digest", "")):
            reasons.append("binding_digest_mismatch")
    return (not reasons), reasons


# --------------------------------------------------------------------------- stage 3: continuity
def _derive_continuity_semantics(
    *, pilot_id: str, day1_date: str, snapshot: Mapping[str, Any], binding: Mapping[str, Any],
    allocation_fp: str, canonical_post_fill: Sequence[Mapping[str, Any]],
    strategy_symbols: Sequence[str], pagination_evidence: Mapping[str, Any],
    page_request_evidence: Any, network_breakdown: Mapping[str, Any],
    allocation: Any = None, allocation_source_sha256: str | None = None,
) -> tuple[list[str], list[str], list[Any], dict[str, int]]:
    """Re-derive continuity blockers from CANONICAL evidence (identity comparison + unauthorized
    detection + pagination + page-evidence + network). Returns (blockers, strategy_present,
    protected_present, merged_counters)."""
    blockers: list[str] = []
    if pilot_id in RETIRED_PILOT_IDS:
        blockers.append(f"retired_pilot_cannot_be_repaired:{pilot_id}")
    ok, snap_reasons, snapshot_fp, _sdig, _sready = _snapshot_is_sealed(snapshot)
    if not ok:
        blockers.extend(snap_reasons)
    bok, bind_reasons = _binding_is_sealed(binding, snapshot, allocation=allocation,
                                           allocation_source_sha256=allocation_source_sha256,
                                           require_execution_ready=True)
    if not bok:
        blockers.extend(bind_reasons)
    if allocation_fp and str((binding or {}).get("allocation_intent_fingerprint", "")) != allocation_fp:
        blockers.append("continuity_binding_allocation_fingerprint_mismatch")

    snap = snapshot if isinstance(snapshot, Mapping) else {}
    if ok and str(snap.get("pilot_id", "")) != pilot_id:
        blockers.append("continuity_snapshot_pilot_id_mismatch")
    if ok and str(snap.get("day1_date", "")) != str(day1_date):
        blockers.append("continuity_snapshot_day1_date_mismatch")
    bind = binding if isinstance(binding, Mapping) else {}
    if bok and str(bind.get("pilot_id", "")) != pilot_id:
        blockers.append("continuity_binding_pilot_id_mismatch")
    if bok and str(bind.get("day1_date", "")) != str(day1_date):
        blockers.append("continuity_binding_day1_date_mismatch")

    merged, net_blockers, _bd = merge_network_counters(network_breakdown or {})
    blockers.extend(net_blockers)
    _pag, pag_blockers = _pagination_evidence(pagination_evidence, prefix="post_fill")
    blockers.extend(pag_blockers)
    blockers.extend(validate_position_page_request_evidence(
        pagination_evidence, page_request_evidence, prefix="post_fill"))

    strategy_set = {_sym(s) for s in (strategy_symbols or [])}
    expected_protected = {(c["symbol"], c["position_idx"]): c
                          for c in _sorted_cores(snap.get("canonical_protected_positions"))}
    current: dict[tuple[str, Any], dict[str, Any]] = {}
    for c in canonical_post_fill or []:
        if not isinstance(c, Mapping):
            continue
        core = _identity_core(c)
        key = (core["symbol"], core["position_idx"])
        if key in current:
            blockers.append(f"duplicate_post_fill_composite_key:{key[0]}:{key[1]}")
            continue
        current[key] = core

    for key, exp in expected_protected.items():
        cur = current.get(key)
        if cur is None:
            blockers.append(f"protected_position_missing:{key[0]}:{key[1]}")
            continue
        if cur["side"] != exp["side"]:
            blockers.append(f"protected_position_side_changed:{key[0]}:{key[1]}")
        if cur["qty"] != exp["qty"]:
            blockers.append(f"protected_position_qty_changed:{key[0]}:{key[1]}")
    for key in current:
        if key[0] not in strategy_set and key not in expected_protected:
            blockers.append(f"unauthorized_protected_position:{key[0]}:{key[1]}")

    strategy_present = sorted({k[0] for k in current if k[0] in strategy_set})
    protected_present = sorted([k for k in current if k in expected_protected])
    return sorted(set(blockers)), strategy_present, protected_present, merged


def verify_post_fill_protected_continuity(
    *, pilot_id: str, day1_date: str, snapshot_artifact: Mapping[str, Any],
    binding_artifact: Mapping[str, Any], post_fill_positions: Sequence[Any],
    post_fill_provenance: Mapping[str, Any], network_counter_components: Mapping[str, Any],
    strategy_symbols: Sequence[str], allocation_intent_fingerprint: str | None = None,
    allocation_artifact_source_sha256: str | None = None, generated_at: str = "",
) -> dict[str, Any]:
    """Re-read positions post-fill and require EXACT protected identity continuity by COMPOSITE key.
    The artifact is fully self-verifying: fingerprint + digest bind the canonical post-fill positions,
    strategy allowlist, allocation fingerprint, pagination/page/network evidence and verdict."""
    pilot_id = str(pilot_id or "").strip()
    merged, _net, breakdown = merge_network_counters(network_counter_components)
    pagination_evidence, _pag_b = _pagination_evidence(post_fill_provenance, prefix="post_fill")
    page_request_evidence = _canonical_page_evidence(post_fill_provenance)

    # Parse raw positions -> canonical cores (raw-only parse blockers).
    parse_blockers: list[str] = []
    canonical_post_fill: list[dict[str, Any]] = []
    seen: set[tuple[str, Any]] = set()
    for p in (post_fill_positions or []):
        row, miss_id, _ma = _position_row(p)
        if miss_id:
            parse_blockers.append(f"post_fill_position_incomplete:{row['symbol'] or '?'}:{'+'.join(miss_id)}")
            continue
        key = (row["symbol"], row["position_idx"])
        if key in seen:
            parse_blockers.append(f"duplicate_post_fill_composite_key:{key[0]}:{key[1]}")
            continue
        seen.add(key)
        canonical_post_fill.append(_identity_core(row))
    canonical_post_fill.sort(key=lambda r: (r["symbol"], r["position_idx"] if r["position_idx"] is not None else -1))
    canonical_strategy = sorted({_sym(s) for s in (strategy_symbols or [])})

    semantic_blockers, strategy_present, protected_present, _merged = _derive_continuity_semantics(
        pilot_id=pilot_id, day1_date=day1_date, snapshot=snapshot_artifact, binding=binding_artifact,
        allocation_fp=str(allocation_intent_fingerprint or ""), canonical_post_fill=canonical_post_fill,
        strategy_symbols=canonical_strategy, pagination_evidence=pagination_evidence,
        page_request_evidence=page_request_evidence, network_breakdown=breakdown)
    blockers = sorted(set(parse_blockers) | set(semantic_blockers))
    continuity_ok = not blockers
    bind = binding_artifact if isinstance(binding_artifact, Mapping) else {}

    protected_present_keys = {(k[0], k[1]) for k in protected_present}
    protected_checked = [c for c in canonical_post_fill
                         if (c["symbol"], c["position_idx"]) in protected_present_keys]

    artifact: dict[str, Any] = {
        "schema_version": CONTINUITY_SCHEMA_VERSION, "environment": ENVIRONMENT,
        "pilot_id": pilot_id, "day1_date": str(day1_date), "generated_at": str(generated_at or ""),
        "trading_authorized": False, "execution_ready": False,
        "protected_position_identity_continuity": CONTINUITY_PASS if continuity_ok else CONTINUITY_BLOCKED,
        "continuity_pass": continuity_ok,
        "verdict": CONTINUITY_PASS if continuity_ok else CONTINUITY_BLOCKED,
        "blockers": blockers,
        "protected_position_snapshot_fingerprint": str(bind.get("protected_position_snapshot_fingerprint", "")),
        "binding_fingerprint": str(bind.get("binding_fingerprint", "")),
        "allocation_intent_fingerprint": str(allocation_intent_fingerprint or ""),
        "allocation_artifact_source_sha256": str(allocation_artifact_source_sha256 or ""),
        "canonical_strategy_symbols": canonical_strategy,
        "canonical_post_fill_positions": canonical_post_fill,
        "strategy_position_count": len(strategy_present),
        "strategy_positions_present": strategy_present,
        "protected_position_count": len(protected_present),
        "protected_positions_present": [k[0] for k in protected_present],
        "protected_continuity_evidence": sorted(protected_checked, key=lambda r: (r["symbol"], r["position_idx"])) if continuity_ok else [],
        "pagination_evidence": pagination_evidence,
        "position_page_request_evidence": page_request_evidence,
        "network_audit_counters": {**merged, "component_breakdown": breakdown},
        "private_mutating_request_count": merged["private_mutating_request_count"],
    }
    artifact["post_fill_continuity_fingerprint"] = canonical_continuity_fingerprint(artifact) if continuity_ok else ""
    artifact["post_fill_continuity_digest"] = canonical_continuity_digest(artifact) if continuity_ok else ""
    return artifact


def _continuity_is_sealed(continuity: Any, snapshot: Any, binding: Any, *, allocation: Any = None,
                          allocation_source_sha256: str | None = None) -> tuple[bool, list[str]]:
    """Validate a PASS continuity artifact: recompute fingerprint + digest, bind the FORMAL
    allocation (recomputed strategy allowlist + fingerprint + file SHA), replay the verdict from the
    canonical evidence, and EXACT-match every stored output (counts / present sets / continuity rows /
    blockers / verdict / top-level network totals)."""
    reasons: list[str] = []
    if not isinstance(continuity, Mapping):
        return False, ["continuity_not_object"]
    if continuity.get("schema_version") != CONTINUITY_SCHEMA_VERSION:
        reasons.append("continuity_schema_version_unexpected")
    if continuity.get("environment") != ENVIRONMENT:
        reasons.append("continuity_environment_unexpected")
    if canonical_continuity_fingerprint(continuity) != str(continuity.get("post_fill_continuity_fingerprint", "")):
        reasons.append("continuity_fingerprint_mismatch")
    if canonical_continuity_digest(continuity) != str(continuity.get("post_fill_continuity_digest", "")):
        reasons.append("continuity_digest_mismatch")

    # The strategy allowlist is the FORMAL allocation's 50 symbols, not the artifact's own list.
    strategy_symbols = continuity.get("canonical_strategy_symbols") or []
    if allocation is not None:
        aok, areasons, afp = validate_day1_allocation_artifact(
            allocation, pilot_id=str(continuity.get("pilot_id", "")),
            day1_date=str(continuity.get("day1_date", "")))
        if not aok:
            reasons.extend(f"continuity_allocation_{r}" for r in areasons)
        else:
            derived_strategy = sorted({_sym(p.get("symbol")) for p in allocation.get("order_payloads") or []
                                       if isinstance(p, Mapping)})
            if sorted(strategy_symbols) != derived_strategy:
                reasons.append("continuity_strategy_symbols_mismatch")
            if afp != str(continuity.get("allocation_intent_fingerprint", "")):
                reasons.append("continuity_allocation_fingerprint_mismatch")
            strategy_symbols = derived_strategy
    if allocation_source_sha256 is not None and \
            str(allocation_source_sha256) != str(continuity.get("allocation_artifact_source_sha256", "")):
        reasons.append("continuity_allocation_source_sha256_mismatch")

    # Semantic replay from canonical evidence -- a PASS must re-derive to zero blockers.
    derived, strat, prot, merged = _derive_continuity_semantics(
        pilot_id=str(continuity.get("pilot_id", "")), day1_date=str(continuity.get("day1_date", "")),
        snapshot=snapshot, binding=binding, allocation=allocation,
        allocation_source_sha256=allocation_source_sha256,
        allocation_fp=str(continuity.get("allocation_intent_fingerprint", "")),
        canonical_post_fill=continuity.get("canonical_post_fill_positions") or [],
        strategy_symbols=strategy_symbols,
        pagination_evidence=continuity.get("pagination_evidence") or {},
        page_request_evidence=continuity.get("position_page_request_evidence"),
        network_breakdown=(continuity.get("network_audit_counters") or {}).get("component_breakdown") or {})
    if derived:
        reasons.append("continuity_semantic_replay_blocked")
        reasons.extend(f"replay:{r}" for r in derived)
    if not continuity.get("continuity_pass") or continuity.get("verdict") != CONTINUITY_PASS:
        reasons.append("continuity_not_pass")
    if sorted(continuity.get("blockers") or []) != []:
        reasons.append("continuity_stored_blockers_nonempty")

    # EXACT-match every stored semantic output against the replay.
    prot_symbols = [k[0] for k in prot]
    prot_cores = sorted((c for c in (continuity.get("canonical_post_fill_positions") or [])
                         if isinstance(c, Mapping) and (c["symbol"], c["position_idx"]) in set(prot)),
                        key=lambda r: (r["symbol"], r["position_idx"]))
    if _as_int(continuity.get("strategy_position_count")) != len(strat):
        reasons.append("continuity_strategy_count_mismatch")
    if list(continuity.get("strategy_positions_present") or []) != strat:
        reasons.append("continuity_strategy_present_mismatch")
    if _as_int(continuity.get("protected_position_count")) != len(prot):
        reasons.append("continuity_protected_count_mismatch")
    if list(continuity.get("protected_positions_present") or []) != prot_symbols:
        reasons.append("continuity_protected_present_mismatch")
    if [_identity_core(c) for c in (continuity.get("protected_continuity_evidence") or [])] != prot_cores:
        reasons.append("continuity_protected_evidence_mismatch")

    # Top-level network totals must equal the re-merged component breakdown.
    nac = continuity.get("network_audit_counters") or {}
    for k in ("private_read_only_request_count", "public_read_only_request_count",
              "private_mutating_request_count"):
        if _as_int(nac.get(k)) != merged[k]:
            reasons.append(f"continuity_network_top_level_mismatch:{k}")
    if _as_int(continuity.get("private_mutating_request_count")) != merged["private_mutating_request_count"]:
        reasons.append("continuity_private_mutating_top_level_mismatch")
    return (not reasons), reasons


# --------------------------------------------------------------------------- Day-2 chain verifier
def verify_day1_protected_identity_chain(
    *, pilot_id: str, day1_date: str, snapshot: Any, binding: Any, continuity: Any,
    current_protected_identities: Mapping[tuple[str, Any], Mapping[str, Any]],
    day1_allocation_intent: Any = None, allocation_source_sha256: str | None = None,
) -> tuple[bool, list[str]]:
    """Re-validate the whole PRE_DAY1 -> binding -> continuity chain for Day-2. Every artifact is
    self-recomputed and semantically replayed; the binding must be EXECUTION-READY, the continuity
    must PASS its replay, cross-artifact pilot/date/environment must match, and the CURRENT protected
    identity must EXACTLY equal the sealed identity by composite key."""
    reasons: list[str] = []
    pilot_id = str(pilot_id or "").strip()
    if pilot_id in RETIRED_PILOT_IDS:
        reasons.append(f"retired_pilot_cannot_be_repaired:{pilot_id}")
    if snapshot is None or binding is None or continuity is None:
        reasons.append("protected_identity_chain_incomplete")
        return False, sorted(set(reasons))

    ok, snap_reasons, snapshot_fp, _sd, _ready = _snapshot_is_sealed(snapshot)
    reasons.extend(snap_reasons)
    bok, bind_reasons = _binding_is_sealed(binding, snapshot, allocation=day1_allocation_intent,
                                           allocation_source_sha256=allocation_source_sha256,
                                           require_execution_ready=True)
    reasons.extend(bind_reasons)
    cok, cont_reasons = _continuity_is_sealed(continuity, snapshot, binding,
                                              allocation=day1_allocation_intent,
                                              allocation_source_sha256=allocation_source_sha256)
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
        for c in _sorted_cores(snapshot.get("canonical_protected_positions")):
            sealed[(c["symbol"], c["position_idx"])] = c
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
