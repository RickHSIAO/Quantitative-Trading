# ADR-014BZ — Separate the Day-2 immutable Target Intent from the volatile runtime sizing translation

- Status: Accepted
- Date: 2026-07-01
- Scope: `src/demo_strategy_native_day2_lifecycle.py`, `scripts/run_demo_pilot_day2_lifecycle.py`
- Supersedes: the v1 single-artifact provenance model (`demo_strategy_native_day2_target_intent_v1`)

## Context

The Day-2 read-only lifecycle dry-run establishes provenance by comparing a pre-sealed target
artifact against the current formal Forward/planner production recompute. In v1 the sealed artifact
carried **both** the strategy intent (symbol / side / quote-notional) **and** the execution sizing
(price / qty / qty_step), and provenance exact-matched all of them.

Those are two different kinds of value:

- **Intent** is what the strategy decided for the day: which symbols, which side, how much quote
  notional against the fixed 10 000 USD capital base. It is stable — it does not change when the
  market moves between the moment the intent is sealed and the moment it is executed.
- **Sizing translation** (qty = |notional| / price, floored to qty_step) is a *runtime* function of
  the live price at execution time. It legitimately differs run to run.

Because v1 bound qty/qty_step into the immutable fingerprint and cross-compared them, a normal price
move produced 40 × `target_qty_mismatch_production` blockers on the real VPS Day-2 validation even
though the strategy intent was unchanged and correct.

## Decision

Split the two concerns:

1. **Immutable Target Intent v2** (`demo_strategy_native_day2_target_intent_v2`) contains only:
   `pilot_id`, `lifecycle_date`, `signal_date`, `strategy_capital_base_usd`, `source_identifier`,
   the four Forward source artifacts + SHA-256, `intent_allocations` (`symbol` / `side` /
   `target_notional_usd` only), `target_intent_fingerprint`, `target_digest`.
   The `target_intent_fingerprint` binds **only** those intent fields — never price, qty, qty_step,
   mark price, runtime timestamp, current positions, or network counters. A price/qty change does
   not change it.

2. **Runtime translation** is produced by *this run's* formal production recompute and carries, per
   symbol: `symbol`, `side`, `target_notional_usd`, `price_snapshot`, `qty_step`, `qty`, and any
   available price-observation evidence. Its `runtime_translation_fingerprint` binds the intent
   fingerprint plus the per-symbol price/qty/qty_step, so it changes whenever price or qty changes.

3. **Provenance** exact-matches strategy identity, dates, source-artifact hashes, and the intent
   (symbol set / side / notional) between the sealed artifact and the production recompute. It no
   longer compares qty / qty_step / price across time. The qty/qty_step used by the lifecycle comes
   **only** from this run's production `runtime_translation`; the sealed artifact carries no qty, so
   a stale/legacy qty can never be read as the runtime qty.

4. **`lifecycle_plan_fingerprint`** binds `target_intent_fingerprint` + `runtime_translation_finger
   print` + `current_position_snapshot_fingerprint` + the canonical actions, so it changes when
   either the intent, the runtime sizing, or the current positions change.

## v1 is never silently upgraded

A sealed artifact whose `schema_version` is not exactly `..._target_intent_v2` (including the v1
value, or a v1 artifact that still carries the qty-bearing `allocations` field) is **rejected** with
`unsupported_target_intent_schema_version`. There is no implicit migration path and no way for a
legacy artifact to reach a v2 READY verdict.

## Consequences

- A normal price move between sealing and execution no longer blocks Day-2; the intent stays
  fingerprint-stable while the runtime translation reflects the fresh price/qty.
- Tamper resistance is unchanged: symbol/side/notional/source/date/hash mismatches still block, and
  invalid runtime qty/price/qty_step still block.
- Unrelated invariants are untouched: strategy weights, the 10 000 USD capital base, symbol
  selection, the qty formula and rounding, instrument rules, the FIX4 network accounting, protected
  symbols, Day-1 artifacts, Pilot state, and the permanent
  `day1_eduusdt_position_identity_evidence_unavailable` blocker all remain as-is.
