"""TASK: machine-readable, READ-ONLY post-fill audit of a dispatched Strategy-native Demo batch.

This module is PURE evaluation logic. It consumes already-loaded durable artifacts (execution
summary / execution state / journal / sent ledger / durable batch attempt / allocation-intent
source) plus completely-paginated Demo position evidence, and produces a single machine-readable
audit verdict. It NEVER sends, cancels, closes, mutates a position, advances the Pilot, or writes
any execution artifact -- the only side effect (performed by the calling script) is writing the
audit artifact itself.

The audit cross-checks ONE batch identity (pilot_id + date + allocation_intent_fingerprint) across
every artifact and cross-validates the per-order identity SETS (execution state vs journal vs sent
ledger). Any mismatch, missing required field, or unauthorized open symbol fails the audit closed.

Advancement (Gate 4) does NOT trust a hand-built PASS artifact: it re-validates the full schema +
evidence sections AND a canonical integrity digest before delegating to the existing idempotent
successful-day advancement. A pre-existing open symbol (e.g. the protected EDUUSDT) is allowed ONLY
when it appears in the formal protected-symbol source supplied by the caller.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping, Sequence

# Verdicts
POST_FILL_AUDIT_PASS = "POST_FILL_AUDIT_PASS"
POST_FILL_AUDIT_FAIL = "POST_FILL_AUDIT_FAIL"

AUDIT_SCHEMA_VERSION = "demo_strategy_native_postfill_audit_v1"
AUDIT_TYPE = "STRATEGY_NATIVE_DEMO_POST_FILL_AUDIT"
ENVIRONMENT_DEMO = "BYBIT_DEMO"
AUDIT_DIGEST_FIELD = "audit_digest"

EXPECTED_ORDER_COUNT = 50
EXPECTED_SIDE_COUNT = 25
FILLED_STATUS = "Filled"
RECONCILED_OUTCOME = "RECONCILED"                  # mirrors nx.OUTCOME_RECONCILED
DAY_SUCCESS = "ACCEPTABLE_SUCCESSFUL_DAY"          # mirrors nx.DAY_SUCCESS
BATCH_DISPATCHED_STATUS = "DEMO_BATCH_DISPATCHED"  # mirrors runner EXEC_BATCH_DISPATCHED
COMPLETE_PAGINATION_TERMINATION = "empty_cursor"

# Journal / sent-ledger markers written by execute_daily_native.
JOURNAL_START = "DAILY_EXECUTION_START"
JOURNAL_RECONCILED = "ACTION_RECONCILED"
JOURNAL_FINISHED = "DAILY_EXECUTION_FINISHED"
LEDGER_ATTEMPTED = "ATTEMPTED"
LEDGER_POST_RESPONSE = "POST_RESPONSE_RECEIVED"
LEDGER_RECONCILED = "RECONCILED"

# Underlying idempotent-advancement statuses (mirrors nx.*).
ADV_STATUS_ADVANCED = "SUCCESSFUL_DAY_ADVANCED"
ADV_STATUS_ALREADY_COUNTED = "DATE_ALREADY_COUNTED_NO_ADVANCE"
ADV_STATUS_PILOT_COMPLETED = "PILOT_COMPLETED"

ADVANCE_REFUSED = "PILOT_ADVANCE_REFUSED_AUDIT_NOT_PASSED"
ADVANCE_DELEGATED = "PILOT_ADVANCE_DELEGATED"

REQUIRED_SECTIONS = (
    "batch_identity_checks", "execution_evidence_summary", "identity_set_checks",
    "allocation_intent_summary", "paginated_position_evidence", "protected_position_evidence",
    "network_audit_counters",
)
REQUIRED_SOURCE_KEYS = (
    "allocation_intent_json", "execution_summary_json", "execution_state_json",
    "batch_attempt_json", "execution_journal_jsonl", "sent_ledger_jsonl",
)
REQUIRED_SUMMARY_KEYS = (
    "status", "day_verdict", "accepted_count", "rejected_count", "ambiguous_count",
    "sender_call_count", "order_post_count", "execute_daily_native_called",
    "pilot_advanced", "live_trading_authorized", "blockers",
)
REQUIRED_STATE_KEYS = (
    "proposed_count", "accepted_count", "rejected_count", "ambiguous_count",
    "sender_call_count", "order_post_count", "day_verdict", "accepted",
)
REQUIRED_BATCH_ATTEMPT_KEYS = (
    "pilot_id", "date", "allocation_intent_fingerprint", "status", "day_verdict",
)


def _norm_side(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in ("buy", "long"):
        return "Buy"
    if s in ("sell", "short"):
        return "Sell"
    return ""


def _position_fields(p: Any) -> tuple[str, str, float]:
    if isinstance(p, Mapping):
        sym = str(p.get("symbol", "")).strip().upper()
        side = _norm_side(p.get("side"))
        size_raw = p.get("size", p.get("quantity", 0))
    else:
        sym = str(getattr(p, "symbol", "")).strip().upper()
        side = _norm_side(getattr(p, "side", ""))
        size_raw = getattr(p, "quantity", 0)
    try:
        size = float(size_raw or 0)
    except (TypeError, ValueError):
        size = 0.0
    return sym, side, size


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _identity_set(rows: Sequence[Mapping[str, Any]], *, state: str | None = None,
                  state_key: str = "state") -> tuple[list[str], set[str], bool]:
    """Return (identities, unique_set, has_empty_identity) for rows optionally filtered by state."""
    ids: list[str] = []
    has_empty = False
    for r in rows:
        if not isinstance(r, Mapping):
            continue
        if state is not None and str(r.get(state_key, "")) != state:
            continue
        ident = str(r.get("identity", "")).strip()
        if not ident:
            has_empty = True
            continue
        ids.append(ident)
    return ids, set(ids), has_empty


def canonical_audit_digest(artifact: Mapping[str, Any]) -> str:
    """SHA-256 over the canonical serialization of the artifact with the digest field EXCLUDED.
    Deterministic (sorted keys, compact separators) so a re-computation by the advancement gate
    detects any post-hoc tampering of a genuine artifact."""
    payload = {k: v for k, v in artifact.items() if k != AUDIT_DIGEST_FIELD}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def evaluate_post_fill_audit(
    *,
    pilot_id: str,
    date: str,
    expected_fingerprint: str,
    allocation_intent_artifact: Mapping[str, Any],
    execution_summary: Mapping[str, Any],
    execution_state: Mapping[str, Any],
    journal: Sequence[Mapping[str, Any]],
    sent_ledger: Sequence[Mapping[str, Any]],
    batch_attempt: Mapping[str, Any],
    positions: Sequence[Any],
    positions_provenance: Mapping[str, Any],
    protected_symbols: Sequence[str],
    protected_symbols_source: str,
    network_counters: Mapping[str, Any],
    intent_recomputed_fingerprint: str | None = None,
    intent_structurally_valid: bool = True,
    source_paths: Mapping[str, Any] | None = None,
    generated_at: str = "",
) -> dict[str, Any]:
    """Evaluate every required post-fill condition and return a machine-readable audit artifact
    (including a canonical integrity digest). A non-empty ``blockers`` list ALWAYS yields verdict
    POST_FILL_AUDIT_FAIL. All inputs are already-loaded read-only evidence; no I/O, no order /
    sender / Pilot mutation."""
    blockers: list[str] = []
    protected_set = {str(s).strip().upper() for s in (protected_symbols or [])}

    # ---------------------------------------------------------------- batch identity
    def _check_id(obj: Mapping[str, Any], name: str, fp_keys: Sequence[str]) -> None:
        if str(obj.get("pilot_id", "")) != str(pilot_id):
            blockers.append(f"{name}_pilot_id_mismatch")
        if str(obj.get("date", "")) != str(date):
            blockers.append(f"{name}_date_mismatch")
        for k in fp_keys:
            if obj.get(k) is None:
                blockers.append(f"{name}_missing_fingerprint:{k}")
            elif str(obj.get(k)) != str(expected_fingerprint):
                blockers.append(f"{name}_fingerprint_mismatch:{k}")

    _check_id(allocation_intent_artifact, "allocation_intent",
              ("payload_fingerprint", "allocation_intent_fingerprint"))
    _check_id(execution_summary, "execution_summary", ("payload_fingerprint",))
    _check_id(execution_state, "execution_state", ())
    _check_id(batch_attempt, "batch_attempt", ("allocation_intent_fingerprint",))

    if intent_recomputed_fingerprint is None or \
            str(intent_recomputed_fingerprint) != str(expected_fingerprint):
        blockers.append("allocation_intent_recomputed_fingerprint_mismatch")
    if not intent_structurally_valid:
        blockers.append("allocation_intent_structurally_invalid")

    # ---------------------------------------------------------------- execution evidence (state)
    for k in REQUIRED_STATE_KEYS:
        if k not in execution_state:
            blockers.append(f"execution_state_missing_field:{k}")
    accepted = list(execution_state.get("accepted") or [])
    accepted_ids, unique_exec_ids, exec_has_empty = _identity_set(accepted)
    filled = sum(1 for a in accepted if isinstance(a, Mapping)
                 and str(a.get("final_status", "")) == FILLED_STATUS)
    outcomes_all_reconciled = bool(accepted) and all(
        isinstance(a, Mapping) and str(a.get("outcome", "")) == RECONCILED_OUTCOME for a in accepted)
    final_status_all_filled = bool(accepted) and filled == len(accepted)

    state_count_checks = {
        "proposed_count": (_as_int(execution_state.get("proposed_count")), EXPECTED_ORDER_COUNT),
        "accepted_count": (_as_int(execution_state.get("accepted_count")), EXPECTED_ORDER_COUNT),
        "rejected_count": (_as_int(execution_state.get("rejected_count")), 0),
        "ambiguous_count": (_as_int(execution_state.get("ambiguous_count")), 0),
        "sender_call_count": (_as_int(execution_state.get("sender_call_count")), EXPECTED_ORDER_COUNT),
        "order_post_count": (_as_int(execution_state.get("order_post_count")), EXPECTED_ORDER_COUNT),
    }
    for field, (got, want) in state_count_checks.items():
        if got != want:
            blockers.append(f"execution_state_{field}_not_{want}:{got}")
    if len(accepted) != EXPECTED_ORDER_COUNT:
        blockers.append(f"accepted_rows_not_50:{len(accepted)}")
    if exec_has_empty:
        blockers.append("execution_state_empty_accepted_identity")
    if len(unique_exec_ids) != EXPECTED_ORDER_COUNT:
        blockers.append(f"unique_execution_identities_not_50:{len(unique_exec_ids)}")
    if not outcomes_all_reconciled:
        blockers.append("accepted_outcome_not_all_reconciled")
    if not final_status_all_filled or filled != EXPECTED_ORDER_COUNT:
        blockers.append(f"filled_final_status_not_50:{filled}")
    if str(execution_state.get("day_verdict", "")) != DAY_SUCCESS:
        blockers.append(f"execution_state_day_verdict_not_success:{execution_state.get('day_verdict')}")

    # ---------------------------------------------------------------- execution summary (required)
    for k in REQUIRED_SUMMARY_KEYS:
        if k not in execution_summary:
            blockers.append(f"execution_summary_missing_field:{k}")
    if str(execution_summary.get("status", "")) != BATCH_DISPATCHED_STATUS:
        blockers.append(f"execution_summary_status_not_dispatched:{execution_summary.get('status')}")
    if str(execution_summary.get("day_verdict", "")) != DAY_SUCCESS:
        blockers.append(f"execution_summary_day_verdict_not_success:{execution_summary.get('day_verdict')}")
    if _as_int(execution_summary.get("execute_daily_native_called")) != 1:
        blockers.append(f"execute_daily_native_called_not_1:{execution_summary.get('execute_daily_native_called')}")
    if execution_summary.get("pilot_advanced") is not False:
        blockers.append("execution_summary_pilot_advanced_not_false")
    if execution_summary.get("live_trading_authorized") is not False:
        blockers.append("execution_summary_live_trading_authorized_not_false")
    if list(execution_summary.get("blockers") or []):
        blockers.append(f"execution_summary_has_blockers:{list(execution_summary.get('blockers'))}")
    summary_count_checks = {
        "accepted_count": EXPECTED_ORDER_COUNT, "rejected_count": 0, "ambiguous_count": 0,
        "sender_call_count": EXPECTED_ORDER_COUNT, "order_post_count": EXPECTED_ORDER_COUNT,
    }
    for field, want in summary_count_checks.items():
        if _as_int(execution_summary.get(field)) != want:
            blockers.append(f"execution_summary_{field}_not_{want}:{execution_summary.get(field)}")
    if "proposed_count" in execution_summary and \
            _as_int(execution_summary.get("proposed_count")) != EXPECTED_ORDER_COUNT:
        blockers.append(f"execution_summary_proposed_count_not_50:{execution_summary.get('proposed_count')}")
    # Summary counts must AGREE with the engine state (not stand alone).
    for field in ("accepted_count", "rejected_count", "ambiguous_count",
                  "order_post_count", "sender_call_count"):
        s_val, e_val = _as_int(execution_summary.get(field)), _as_int(execution_state.get(field))
        if s_val is not None and e_val is not None and s_val != e_val:
            blockers.append(f"summary_state_count_disagree:{field}:{s_val}!={e_val}")

    # ---------------------------------------------------------------- batch attempt
    for k in REQUIRED_BATCH_ATTEMPT_KEYS:
        if k not in batch_attempt:
            blockers.append(f"batch_attempt_missing_field:{k}")
    if str(batch_attempt.get("status", "")) != BATCH_DISPATCHED_STATUS:
        blockers.append(f"batch_attempt_status_not_dispatched:{batch_attempt.get('status')}")
    if str(batch_attempt.get("day_verdict", "")) != DAY_SUCCESS:
        blockers.append(f"batch_attempt_day_verdict_not_success:{batch_attempt.get('day_verdict')}")

    # ---------------------------------------------------------------- journal identity set
    jcount = Counter(str(e.get("event", "")) for e in journal if isinstance(e, Mapping))
    journal_recon_rows = [e for e in journal if isinstance(e, Mapping)
                          and str(e.get("event", "")) == JOURNAL_RECONCILED]
    _jids, journal_recon_ids, journal_has_empty = _identity_set(journal_recon_rows)
    if jcount[JOURNAL_START] != 1:
        blockers.append(f"journal_start_not_1:{jcount[JOURNAL_START]}")
    if jcount[JOURNAL_RECONCILED] != EXPECTED_ORDER_COUNT:
        blockers.append(f"journal_reconciled_not_50:{jcount[JOURNAL_RECONCILED]}")
    if jcount[JOURNAL_FINISHED] != 1:
        blockers.append(f"journal_finished_not_1:{jcount[JOURNAL_FINISHED]}")
    if journal_has_empty:
        blockers.append("journal_reconciled_empty_identity")
    if len(journal_recon_ids) != EXPECTED_ORDER_COUNT:
        blockers.append(f"journal_unique_reconciled_identities_not_50:{len(journal_recon_ids)}")
    journal_matches_execution = bool(unique_exec_ids) and journal_recon_ids == unique_exec_ids
    if unique_exec_ids and not journal_matches_execution:
        blockers.append("journal_identity_set_mismatch_execution")

    # ---------------------------------------------------------------- sent-ledger identity sets
    lstate = Counter(str(e.get("state", "")) for e in sent_ledger if isinstance(e, Mapping))
    ledger_unique: dict[str, int] = {}
    ledger_sets: dict[str, set[str]] = {}
    for st, want in ((LEDGER_ATTEMPTED, EXPECTED_ORDER_COUNT),
                     (LEDGER_POST_RESPONSE, EXPECTED_ORDER_COUNT),
                     (LEDGER_RECONCILED, EXPECTED_ORDER_COUNT)):
        if lstate[st] != want:
            blockers.append(f"ledger_{st.lower()}_not_50:{lstate[st]}")
        _ids, uniq, has_empty = _identity_set(sent_ledger, state=st)
        ledger_unique[st] = len(uniq)
        ledger_sets[st] = uniq
        if has_empty:
            blockers.append(f"ledger_{st.lower()}_empty_identity")
        if len(uniq) != EXPECTED_ORDER_COUNT:
            blockers.append(f"ledger_{st.lower()}_unique_identities_not_50:{len(uniq)}")
    ledger_sets_consistent = (ledger_sets.get(LEDGER_ATTEMPTED) == ledger_sets.get(LEDGER_POST_RESPONSE)
                              == ledger_sets.get(LEDGER_RECONCILED)) and bool(ledger_sets.get(LEDGER_RECONCILED))
    if not ledger_sets_consistent:
        blockers.append("ledger_state_identity_sets_inconsistent")
    ledger_matches_execution = bool(unique_exec_ids) and \
        ledger_sets.get(LEDGER_RECONCILED) == unique_exec_ids
    if unique_exec_ids and not ledger_matches_execution:
        blockers.append("ledger_identity_set_mismatch_execution")

    # ---------------------------------------------------------------- allocation intent
    payloads = list(allocation_intent_artifact.get("order_payloads") or [])
    intent_by_symbol: dict[str, str] = {}
    intent_buy = intent_sell = 0
    intent_symbols: list[str] = []
    for p in payloads:
        if not isinstance(p, Mapping):
            continue
        sym = str(p.get("symbol", "")).strip().upper()
        side = _norm_side(p.get("side"))
        intent_symbols.append(sym)
        if side == "Buy":
            intent_buy += 1
        elif side == "Sell":
            intent_sell += 1
        else:
            blockers.append(f"allocation_intent_invalid_side:{sym}")
        intent_by_symbol[sym] = side
    if len(payloads) != EXPECTED_ORDER_COUNT:
        blockers.append(f"allocation_intent_symbol_count_not_50:{len(payloads)}")
    if len(set(intent_symbols)) != len(intent_symbols):
        blockers.append("allocation_intent_duplicate_symbol")
    if intent_buy != EXPECTED_SIDE_COUNT or intent_sell != EXPECTED_SIDE_COUNT:
        blockers.append(f"allocation_intent_side_distribution_not_25_25:{intent_buy}/{intent_sell}")
    strategy_symbol_set = set(intent_by_symbol)

    # ---------------------------------------------------------------- paginated positions
    if str(positions_provenance.get("termination_reason", "")) != COMPLETE_PAGINATION_TERMINATION:
        blockers.append(
            f"position_pagination_incomplete:{positions_provenance.get('termination_reason')}")
    page_count = _as_int(positions_provenance.get("page_count"))
    if page_count is None or page_count < 1:
        blockers.append(f"position_page_count_invalid:{positions_provenance.get('page_count')}")

    pos_side_by_symbol: dict[str, str] = {}
    nonzero = 0
    total_buy = total_sell = 0
    dup_positions: list[str] = []
    for p in positions:
        sym, side, size = _position_fields(p)
        if size <= 0:
            continue
        nonzero += 1
        if sym in pos_side_by_symbol:
            dup_positions.append(sym)
            continue
        pos_side_by_symbol[sym] = side
        if side == "Buy":
            total_buy += 1
        elif side == "Sell":
            total_sell += 1
    if dup_positions:
        blockers.append(f"duplicate_open_position_symbols:{sorted(set(dup_positions))}")

    missing_strategy_symbols = sorted(s for s in strategy_symbol_set if s not in pos_side_by_symbol)
    side_mismatch_symbols = sorted(
        s for s in strategy_symbol_set
        if s in pos_side_by_symbol and pos_side_by_symbol[s] != intent_by_symbol[s])
    unexpected_open_symbols = sorted(s for s in pos_side_by_symbol if s not in strategy_symbol_set)
    disallowed_unexpected = sorted(s for s in unexpected_open_symbols if s not in protected_set)

    if missing_strategy_symbols:
        blockers.append(f"missing_strategy_symbols:{missing_strategy_symbols}")
    if side_mismatch_symbols:
        blockers.append(f"strategy_side_mismatch:{side_mismatch_symbols}")
    if disallowed_unexpected:
        blockers.append(f"unauthorized_unexpected_open_symbols:{disallowed_unexpected}")
    matched_strategy = sorted(s for s in strategy_symbol_set if s in pos_side_by_symbol
                              and s not in set(side_mismatch_symbols))
    allowed_preexisting = sorted(s for s in unexpected_open_symbols if s in protected_set)

    # ---------------------------------------------------------------- network safety
    mutating = _as_int(network_counters.get("private_mutating_request_count"))
    read_only = _as_int(network_counters.get("private_read_only_request_count"))
    if mutating != 0:
        blockers.append(f"private_mutating_requests_detected:{mutating}")
    if read_only is None or read_only < 1:
        blockers.append(f"no_private_read_only_request_recorded:{read_only}")

    verdict = POST_FILL_AUDIT_PASS if not blockers else POST_FILL_AUDIT_FAIL
    artifact: dict[str, Any] = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "audit_type": AUDIT_TYPE,
        "environment": ENVIRONMENT_DEMO,
        "generated_at": generated_at,
        "pilot_id": pilot_id,
        "date": date,
        "allocation_intent_fingerprint": expected_fingerprint,
        "source_paths": dict(source_paths or {}),
        "batch_identity_checks": {
            "expected_fingerprint": expected_fingerprint,
            "allocation_intent_fingerprint": allocation_intent_artifact.get("payload_fingerprint"),
            "execution_summary_fingerprint": execution_summary.get("payload_fingerprint"),
            "batch_attempt_fingerprint": batch_attempt.get("allocation_intent_fingerprint"),
            "intent_recomputed_fingerprint": intent_recomputed_fingerprint,
            "intent_structurally_valid": intent_structurally_valid,
        },
        "execution_evidence_summary": {
            "proposed_count": execution_state.get("proposed_count"),
            "accepted_count": execution_state.get("accepted_count"),
            "rejected_count": execution_state.get("rejected_count"),
            "ambiguous_count": execution_state.get("ambiguous_count"),
            "accepted_rows": len(accepted),
            "filled_final_status_count": filled,
            "accepted_outcomes_all_reconciled": outcomes_all_reconciled,
            "accepted_final_status_all_filled": final_status_all_filled,
            "sender_call_count": execution_state.get("sender_call_count"),
            "order_post_count": execution_state.get("order_post_count"),
            "execute_daily_native_called": execution_summary.get("execute_daily_native_called"),
            "execution_state_day_verdict": execution_state.get("day_verdict"),
            "execution_summary_status": execution_summary.get("status"),
            "execution_summary_day_verdict": execution_summary.get("day_verdict"),
            "execution_summary_pilot_advanced": execution_summary.get("pilot_advanced"),
            "batch_attempt_status": batch_attempt.get("status"),
            "batch_attempt_day_verdict": batch_attempt.get("day_verdict"),
            "live_trading_authorized": execution_summary.get("live_trading_authorized"),
            "execution_summary_blockers": list(execution_summary.get("blockers") or []),
            "authorized_target_gross_notional_usd":
                execution_summary.get("authorized_target_gross_notional_usd"),
            "executed_actual_gross_notional_usd":
                execution_summary.get("executed_actual_gross_notional_usd"),
        },
        "identity_set_checks": {
            "unique_execution_identities": len(unique_exec_ids),
            "journal_reconciled_unique_identities": len(journal_recon_ids),
            "journal_identity_set_matches_execution": journal_matches_execution,
            "ledger_unique_identities": ledger_unique,
            "ledger_identity_sets_consistent": ledger_sets_consistent,
            "ledger_identity_set_matches_execution": ledger_matches_execution,
            "journal_event_counts": dict(jcount),
            "ledger_state_counts": dict(lstate),
        },
        "allocation_intent_summary": {
            "expected_symbol_count": len(payloads),
            "unique_symbol_count": len(set(intent_symbols)),
            "buy_count": intent_buy,
            "sell_count": intent_sell,
        },
        "paginated_position_evidence": {
            "page_count": positions_provenance.get("page_count"),
            "termination_reason": positions_provenance.get("termination_reason"),
            "api_position_rows": positions_provenance.get("api_position_rows"),
            "nonzero_position_count": nonzero,
            "total_buy": total_buy,
            "total_sell": total_sell,
            "strategy_matched_count": len(matched_strategy),
        },
        "protected_position_evidence": {
            "protected_symbols_source": protected_symbols_source,
            "protected_symbols": sorted(protected_set),
            "allowed_preexisting_protected_symbols": allowed_preexisting,
        },
        "missing_strategy_symbols": missing_strategy_symbols,
        "side_mismatch_symbols": side_mismatch_symbols,
        "unexpected_open_symbols": unexpected_open_symbols,
        "allowed_preexisting_protected_symbols": allowed_preexisting,
        "network_audit_counters": {
            "private_read_only_request_count": read_only,
            "public_read_only_request_count":
                _as_int(network_counters.get("public_read_only_request_count")),
            "private_mutating_request_count": mutating,
            "position_pagination_page_count": positions_provenance.get("page_count"),
            "position_cursor_termination_reason": positions_provenance.get("termination_reason"),
        },
        "blockers": blockers,
        "verdict": verdict,
    }
    artifact[AUDIT_DIGEST_FIELD] = canonical_audit_digest(artifact)
    return artifact


# ---------------------------------------------------------------------------
# Gate 4: independent re-validation, then advance via the existing idempotent path.
# ---------------------------------------------------------------------------


def validate_audit_artifact_for_advancement(
    artifact: Mapping[str, Any], *, pilot_id: str, date: str, expected_fingerprint: str,
) -> tuple[bool, list[str]]:
    """Re-validate a completed audit artifact BEFORE advancing the Pilot. Trusts neither the
    top-level ``verdict`` alone nor a partial hand-built artifact: it re-checks the schema, the
    canonical integrity digest, every required evidence section, and the encoded PASS conditions.
    Returns (ok, refusal_reasons); ANY problem fails closed."""
    reasons: list[str] = []
    if not isinstance(artifact, Mapping):
        return False, ["audit_artifact_not_object"]

    # Integrity digest (recomputed; the digest field is excluded from its own computation).
    stored_digest = artifact.get(AUDIT_DIGEST_FIELD)
    if not stored_digest:
        reasons.append("audit_digest_missing")
    elif canonical_audit_digest(artifact) != str(stored_digest):
        reasons.append("audit_digest_mismatch")

    # Schema + identity.
    if artifact.get("schema_version") != AUDIT_SCHEMA_VERSION:
        reasons.append("schema_version_invalid")
    if artifact.get("audit_type") != AUDIT_TYPE:
        reasons.append("audit_type_invalid")
    if artifact.get("environment") != ENVIRONMENT_DEMO:
        reasons.append("environment_not_demo")
    if str(artifact.get("pilot_id", "")) != str(pilot_id):
        reasons.append("pilot_id_mismatch")
    if str(artifact.get("date", "")) != str(date):
        reasons.append("date_mismatch")
    if str(artifact.get("allocation_intent_fingerprint", "")) != str(expected_fingerprint):
        reasons.append("fingerprint_mismatch")
    if artifact.get("verdict") != POST_FILL_AUDIT_PASS:
        reasons.append("verdict_not_pass")
    if list(artifact.get("blockers") or []):
        reasons.append("artifact_has_blockers")

    # Required sections + source evidence must be present.
    missing_section = False
    for sec in REQUIRED_SECTIONS:
        if not isinstance(artifact.get(sec), Mapping):
            reasons.append(f"missing_section:{sec}")
            missing_section = True
    sp = artifact.get("source_paths")
    if not isinstance(sp, Mapping) or any(not sp.get(k) for k in REQUIRED_SOURCE_KEYS):
        reasons.append("source_evidence_incomplete")
    if missing_section:
        return False, reasons

    # Deep evidence re-validation (independent of the top-level verdict).
    bic = artifact["batch_identity_checks"]
    fps = [bic.get("expected_fingerprint"), bic.get("allocation_intent_fingerprint"),
           bic.get("execution_summary_fingerprint"), bic.get("batch_attempt_fingerprint"),
           bic.get("intent_recomputed_fingerprint")]
    if any(f is None or str(f) != str(expected_fingerprint) for f in fps):
        reasons.append("batch_identity_fingerprints_inconsistent")
    if bic.get("intent_structurally_valid") is not True:
        reasons.append("intent_not_structurally_valid")

    ee = artifact["execution_evidence_summary"]
    for field, want in (("proposed_count", EXPECTED_ORDER_COUNT), ("accepted_count", EXPECTED_ORDER_COUNT),
                        ("rejected_count", 0), ("ambiguous_count", 0),
                        ("accepted_rows", EXPECTED_ORDER_COUNT),
                        ("filled_final_status_count", EXPECTED_ORDER_COUNT),
                        ("sender_call_count", EXPECTED_ORDER_COUNT),
                        ("order_post_count", EXPECTED_ORDER_COUNT),
                        ("execute_daily_native_called", 1)):
        if _as_int(ee.get(field)) != want:
            reasons.append(f"execution_evidence_{field}_not_{want}")
    if ee.get("accepted_outcomes_all_reconciled") is not True:
        reasons.append("accepted_outcomes_not_all_reconciled")
    if ee.get("accepted_final_status_all_filled") is not True:
        reasons.append("accepted_final_status_not_all_filled")
    if ee.get("execution_state_day_verdict") != DAY_SUCCESS:
        reasons.append("execution_state_day_verdict_not_success")
    if ee.get("execution_summary_status") != BATCH_DISPATCHED_STATUS:
        reasons.append("execution_summary_status_not_dispatched")
    if ee.get("execution_summary_day_verdict") != DAY_SUCCESS:
        reasons.append("execution_summary_day_verdict_not_success")
    if ee.get("execution_summary_pilot_advanced") is not False:
        reasons.append("execution_summary_pilot_advanced_not_false")
    if ee.get("batch_attempt_status") != BATCH_DISPATCHED_STATUS:
        reasons.append("batch_attempt_status_not_dispatched")
    if ee.get("batch_attempt_day_verdict") != DAY_SUCCESS:
        reasons.append("batch_attempt_day_verdict_not_success")
    if ee.get("live_trading_authorized") is not False:
        reasons.append("live_trading_authorized_not_false")
    if list(ee.get("execution_summary_blockers") or []):
        reasons.append("execution_summary_blockers_present")

    isc = artifact["identity_set_checks"]
    if _as_int(isc.get("unique_execution_identities")) != EXPECTED_ORDER_COUNT:
        reasons.append("unique_execution_identities_not_50")
    if _as_int(isc.get("journal_reconciled_unique_identities")) != EXPECTED_ORDER_COUNT:
        reasons.append("journal_reconciled_unique_identities_not_50")
    if isc.get("journal_identity_set_matches_execution") is not True:
        reasons.append("journal_identity_set_mismatch")
    if isc.get("ledger_identity_sets_consistent") is not True:
        reasons.append("ledger_identity_sets_inconsistent")
    if isc.get("ledger_identity_set_matches_execution") is not True:
        reasons.append("ledger_identity_set_mismatch")
    lu = isc.get("ledger_unique_identities")
    if not isinstance(lu, Mapping) or any(
            _as_int(lu.get(st)) != EXPECTED_ORDER_COUNT
            for st in (LEDGER_ATTEMPTED, LEDGER_POST_RESPONSE, LEDGER_RECONCILED)):
        reasons.append("ledger_unique_identities_not_50")
    jec = isc.get("journal_event_counts") or {}
    if _as_int(jec.get(JOURNAL_START)) != 1 or _as_int(jec.get(JOURNAL_FINISHED)) != 1 \
            or _as_int(jec.get(JOURNAL_RECONCILED)) != EXPECTED_ORDER_COUNT:
        reasons.append("journal_event_counts_invalid")

    ais = artifact["allocation_intent_summary"]
    if _as_int(ais.get("expected_symbol_count")) != EXPECTED_ORDER_COUNT \
            or _as_int(ais.get("unique_symbol_count")) != EXPECTED_ORDER_COUNT \
            or _as_int(ais.get("buy_count")) != EXPECTED_SIDE_COUNT \
            or _as_int(ais.get("sell_count")) != EXPECTED_SIDE_COUNT:
        reasons.append("allocation_intent_summary_invalid")

    pos = artifact["paginated_position_evidence"]
    if pos.get("termination_reason") != COMPLETE_PAGINATION_TERMINATION:
        reasons.append("position_pagination_incomplete")
    if _as_int(pos.get("page_count")) is None or _as_int(pos.get("page_count")) < 1:
        reasons.append("position_page_count_invalid")
    if _as_int(pos.get("strategy_matched_count")) != EXPECTED_ORDER_COUNT:
        reasons.append("strategy_matched_count_not_50")
    if list(artifact.get("missing_strategy_symbols") or []):
        reasons.append("missing_strategy_symbols_present")
    if list(artifact.get("side_mismatch_symbols") or []):
        reasons.append("side_mismatch_symbols_present")
    allowed = set(artifact.get("allowed_preexisting_protected_symbols") or [])
    if any(s not in allowed for s in (artifact.get("unexpected_open_symbols") or [])):
        reasons.append("unauthorized_unexpected_open_symbols")

    nac = artifact["network_audit_counters"]
    if _as_int(nac.get("private_mutating_request_count")) != 0:
        reasons.append("private_mutating_requests_detected")
    if _as_int(nac.get("private_read_only_request_count")) is None \
            or _as_int(nac.get("private_read_only_request_count")) < 1:
        reasons.append("no_private_read_only_request_recorded")
    if nac.get("position_cursor_termination_reason") != COMPLETE_PAGINATION_TERMINATION:
        reasons.append("network_pagination_not_complete")

    return (not reasons), reasons


def gate_and_advance_pilot(
    *,
    audit_artifact: Mapping[str, Any],
    pilot_id: str,
    date: str,
    expected_fingerprint: str,
    output_root: Any = None,
    advance_fn: Any = None,
) -> dict[str, Any]:
    """Advance the successful-day counter via the EXISTING idempotent advancement path, but ONLY
    after fully re-validating ``audit_artifact`` (schema + digest + every evidence section). Never
    edits Pilot JSON directly, never sends an order, never issues an exchange mutating request.

    Reporting distinguishes:
      advanced_now    -- THIS call moved the counter (0->1);
      already_counted -- the date was already counted (idempotent no-op);
      refused         -- validation failed or the Pilot would not advance."""
    base = {"pilot_id": pilot_id, "date": date,
            "advanced_now": False, "already_counted": False, "refused": True}

    ok, reasons = validate_audit_artifact_for_advancement(
        audit_artifact, pilot_id=pilot_id, date=date, expected_fingerprint=expected_fingerprint)
    if not ok:
        return {**base, "status": ADVANCE_REFUSED, "refusal_reasons": reasons}

    if advance_fn is None:
        from src import demo_strategy_pilot_native_execution as nx
        advance_fn = nx.advance_successful_day

    result = advance_fn(pilot_id=pilot_id, date=date, day_verdict=DAY_SUCCESS,
                        output_root=output_root)
    status = str(result.get("status", ""))
    advanced_now = status in (ADV_STATUS_ADVANCED, ADV_STATUS_PILOT_COMPLETED)
    already_counted = status == ADV_STATUS_ALREADY_COUNTED
    refused = not (advanced_now or already_counted)
    return {
        "pilot_id": pilot_id, "date": date,
        "status": ADVANCE_REFUSED if refused else ADVANCE_DELEGATED,
        "advanced_now": advanced_now, "already_counted": already_counted, "refused": refused,
        "advancement_status": status,
        "completed_successful_days": result.get("completed_successful_days"),
        "refusal_reasons": [] if not refused else [f"advancement_refused:{status}"],
        "advancement_result": result,
    }
