# ADR-014CA — Seal pre-existing protected-position identity before a new Demo Pilot's Day 1

- Status: Accepted
- Date: 2026-07-01
- Scope: `src/demo_pilot_protected_identity_bootstrap.py`,
  `scripts/run_demo_pilot_protected_identity_snapshot.py`
- Related: ADR-014BZ (Day-2 target-intent / runtime separation); the Day-2 lifecycle
  `day1_eduusdt_position_identity_evidence_unavailable` blocker.

## Context

The retired Pilot `BYBIT_DEMO_PILOT_7D_202606_V1` is stuck at 1/7 with the single blocker
`day1_eduusdt_position_identity_evidence_unavailable`. The cause is not a strategy or lifecycle
defect: that Pilot began Day 1 **without** first sealing the immutable identity of the pre-existing
protected EDUUSDT position. Day-2 lifecycle then correctly refuses to treat an open EDUUSDT as
"allowed" because no immutable Day-1 artifact binds its `side` / `qty` / `position_idx` to the Day-1
allocation fingerprint.

That evidence cannot be manufactured after the fact — back-dating a protected-position identity
would defeat the very tamper-resistance it exists to provide. The retired Pilot must stay frozen,
un-migrated and un-repaired, and EDUUSDT must not be closed or modified.

## Protected is NOT "every open position" (FIX1)

A NEW Pilot owns nothing it created, but the account it inherits may still hold the previous Pilot's
50 strategy positions. Those are **not** protected — they are
``preexisting_nonprotected_positions`` this run does not own. Only symbols in the canonical
`PROTECTED_SYMBOLS` anchor (currently `AIXBTUSDT`, `EDUUSDT`, `ENAUSDT`, `POLYXUSDT`, `TIAUSDT`)
enter the sealed protected identity set. The snapshot therefore reports three disjoint groups —
``all_observed_nonzero_positions`` / ``protected_positions`` / ``preexisting_nonprotected_positions``
— and any inherited non-protected position **BLOCKS** bootstrap
(``preexisting_nonprotected_positions_require_ownership_resolution``). Those 50 positions are not
this task's to close, rebalance, or adopt; they require a separate, formal, immutable
inherited-strategy-baseline artifact, which this task never fabricates. So with the current account
shape (50 strategy + 1 EDUUSDT) the snapshot correctly reports `protected_position_count = 1`,
`protected_symbols = ["EDUUSDT"]`, `preexisting_nonprotected_position_count = 50`, and stays BLOCKED.

## Composite position identity (FIX1)

All identity maps key on the COMPOSITE ``(symbol, position_idx)`` — never on ``symbol`` alone — so a
hedge-mode account's `position_idx = 1` and `position_idx = 2` legs of the same symbol are sealed and
verified independently, and a repeated `(symbol, position_idx)` fails closed. Canonical identity is
``symbol / side / qty / position_idx``; ``entry_price`` / ``leverage`` / account & position mode /
request timing are retained as AUDIT evidence (missing required audit evidence BLOCKS) but are not
part of the continuity identity.

## Self-verifying fingerprints and formal allocation binding (FIX1)

`canonical_protected_snapshot_fingerprint/_digest` and `canonical_binding_fingerprint/_digest`
RECOMPUTE from each artifact's own fields, and the sealed checks exact-match both the fingerprint and
the digest — never a format-only SHA check. A value tampered in `canonical_protected_positions` (or a
swapped allocation fingerprint) that only re-derives the OUTER digest still fails, because the
recomputed identity fingerprint no longer matches the stored one. The binding no longer accepts a raw
allocation SHA string: it takes a FORMAL Day-1 allocation artifact and validates it with the
production `allocation_intent_fingerprint` recompute (pilot/date/capital-base/50-symbol/25-25/symbol
uniqueness/stored==recomputed) before binding the recomputed fingerprint. Binding, continuity, and the
Day-2 chain verifier all exact-check `pilot_id` / `day1_date` / `environment` / snapshot & binding
fingerprints+digests across artifacts, so a cross-pilot or cross-date replay fails closed.

## Day-2 lifecycle integration (FIX1)

The Day-2 lifecycle now accepts the formal chain (PRE_DAY1 snapshot + Day-1 binding + post-fill
continuity). It clears `day1_eduusdt_position_identity_evidence_unavailable` ONLY when
`verify_day1_protected_identity_chain` passes: every artifact self-recomputes, all bind to THIS
pilot/date/environment, the binding is COMPLETE, continuity is PASS, and the CURRENT EDUUSDT identity
exactly equals the sealed identity by composite key (with mutating request count 0). Absent the chain
the canonical blocker is preserved unchanged; a forged/cross-pilot/cross-date/failed-continuity/
changed-current-identity chain fails closed with a specific `day1_protected_chain:*` blocker. The
retired Pilot supplies no chain, so its Day-2 result remains `DAY2_LIFECYCLE_DRY_RUN_BLOCKED` with the
same core blocker; no old artifact is modified.

## Why protected identity must be sealed BEFORE Day 1

A new Pilot owns no positions on Day 0, so **every** pre-existing nonzero position is a protected
position it must not touch. If those identities are captured only after Day-1 strategy fills, a
protected position that silently changed (or a stray unauthorized position) can no longer be
distinguished from a legitimate one. The identity therefore has to be frozen from a formal read-only
snapshot **before** any Day-1 order is authorized — that is the only point at which "what was already
there" is unambiguous.

## Decision

A new Pilot (new Pilot ID — never a reused/retired one; the fixture uses
`BYBIT_DEMO_PILOT_7D_202607_V2`) runs a three-stage read-only evidence chain. All three stages are
pure (no order/cancel/amend/close, no leverage/position-mode change, no sender, no execution adapter,
no Pilot-state write, no Live endpoint), and every network component is accounted under the FIX4
counter contract (`private_read_only` / `public_read_only` / `private_mutating`); any non-zero
mutating count, or a missing/malformed counter, fails closed.

1. **PRE_DAY1 protected snapshot** (`build_pre_day1_protected_snapshot`). From a COMPLETE Demo
   private read-only paginated position read (only Bybit's empty-cursor termination is accepted as
   complete), it classifies observed positions into all / protected / preexisting-nonprotected and
   canonicalizes each PROTECTED position's immutable identity by composite key —
   `symbol` / `side` / `qty` / `position_idx` — taken **only** from the API snapshot, never from a
   user value and never inferred from a prior artifact. It seals
   `protected_position_snapshot_fingerprint` (binding schema version, pilot id, day1 date,
   `environment = DEMO`, a non-sensitive account-identity digest, the canonical protected positions,
   pagination evidence, the protected symbol set, and the generated-snapshot evidence) plus a whole
   artifact `..._digest`. The artifact is explicitly `phase = PRE_DAY1`, `trading_authorized = false`,
   `private_mutating_request_count = 0`.

2. **Day-1 allocation binding** (`build_day1_protected_binding`). Once the Day-1 allocation intent
   exists, a formal binding artifact ties `allocation_intent_fingerprint` to the sealed snapshot's
   fingerprint + digest via a `binding_fingerprint` (+ `binding_digest`). Co-locating two files in a
   folder is **not** a binding. A Pilot only becomes `execution_ready` when this binding is COMPLETE;
   if the allocation intent does not yet exist the snapshot may be captured but the Pilot stays
   pending.

3. **Day-1 post-fill continuity** (`verify_post_fill_protected_continuity`). A second COMPLETE
   paginated read must reproduce every protected position's `symbol` / `side` / `qty` /
   `position_idx` EXACTLY. Only exact continuity yields
   `protected_position_identity_continuity = PASS`. A protected position that disappears, changes
   side/qty/position_idx, an extra unauthorized (non-strategy, non-pre-captured) position, or an
   incomplete snapshot, all fail closed. The 50 strategy positions and the protected positions are
   counted and reported **separately**.

## Retired Pilots are never repaired

`RETIRED_PILOT_IDS` (currently `BYBIT_DEMO_PILOT_7D_202606_V1`) may neither bootstrap a snapshot nor
receive a binding — a newly captured snapshot can never be assigned to the retired Pilot's
2026-06-30 Day 1. There is no migration path and no way for post-hoc evidence to advance the retired
Pilot.

## Consequences

- A **new** Pilot can keep the existing EDUUSDT position open (no close required): once its PRE_DAY1
  snapshot, allocation binding and post-fill continuity all pass, a future Day-2 lifecycle consuming
  that binding would no longer emit `day1_eduusdt_position_identity_evidence_unavailable`, while a
  missing or inconsistent link still BLOCKS.
- This task only adds the evidence chain (code, fixtures, offline tests, dry-run readiness). It sends
  no orders, advances no Pilot, and does **not** modify the retired Pilot, its Day-2 artifact,
  EDUUSDT, or REVIEW-009. The retired Pilot remains 1/7. Live remains permanently denied.
