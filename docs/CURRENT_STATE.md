# Current State

## Project

Multi-asset quantitative trading research system. Crypto momentum strategy
with Bybit Demo execution pipeline, forward/paper recording, and monitoring.
Strategy-native V1 architecture with cost-aware signal generation.

Architecture source of truth: [`docs/ARCHITECTURE.md`](ARCHITECTURE.md)

## Git State

- **Remote stable (origin/main):** `703db19` (TASK-014CF closeout)
- **Local HEAD:** `6a0bd4f` (docs: freeze legacy AI logs and add current state)
- **Local unpushed commits:**
  1. `c5c4bf2` — TASK-014CG: bind plan-only actions to websocket price evidence
  2. `4edbe50` — TASK-014CG_FIX1: emit canonical websocket-bound plan artifact
  3. `f76d0ae` — repo: stop tracking obvious runtime outputs
  4. `6a0bd4f` — docs: freeze legacy AI logs and add current state

## Strategy-Native V1

- 50 signals (25 long / 25 short), prev3y_crypto universe
- Cost-aware ranking with transaction-cost stress testing complete
- Rick risk overlay comparison done (TASK-007)
- Alpha concentration analysis done (TASK-008)

## 30-Day Forward Validation

- Start date: 2026-05-18 (day 0)
- Runner status: REVIEW_READY
- Data source: cache_fallback
- Dry run mode: True
- Paper execution: FORBIDDEN
- Live trading: FORBIDDEN
- NAV: $10,000 (initial), no drawdown

## Authorization State

- **Demo API:** .env.demo configured, read-only smoke tests pass
- **Pilot/Live trading:** FORBIDDEN — no order endpoints attempted
- **Bybit write operations:** NOT_ATTEMPTED

## WebSocket Evidence Binding

- CG binding code complete in `src/demo_strategy_native_ws_price_binding.py`
- Provides `bind_plan_prices_to_ws_evidence()`, `build_ws_bound_plan_artifact()`,
  `canonical_bound_plan_actions()`
- CH1 consumer contract complete in
  `src/demo_strategy_native_ws_bound_plan_consumer.py`
  (`validate_ws_bound_plan_artifact()`): fail-closed validation of a canonical
  WS-bound Plan (fingerprint/provenance, signed V1 semantics, authoritative
  clock-offset freshness, per-symbol source-record cross-validation).
- **CH2: explicit opt-in terminal native Plan-only consumer is wired.**
  `scripts/run_demo_strategy_pilot_native_daily.py --ws-bound-plan-only`
  builds the REST seed Plan, reads a caller-supplied public-WS evidence JSON
  file, binds it, validates via the CH1 consumer, and writes exactly one
  canonical WS-bound Plan wrapper (orchestration in
  `src/demo_strategy_native_ws_bound_plan_only.py`).
- Opt-in only; the source WS artifact is supplied by file (no live WS
  collection in this path). No REST fallback once WS binding begins. The path
  is terminal **before** review / readiness / execution gate / native
  execution; execution remains unauthorized and the Pilot is never advanced.
- CH2_FIX1 hardening: Plan-only mode-conflict validation runs **first** in
  `main()`, before reconcile / PilotStateStore / reporting / provider / read /
  write (rejects `--send-orders-to-demo`, `--advance-on-success`,
  `--reconcile-outputs-only`, `--allow-notion-network`, `--allow-discord-network`,
  `--test-injected-actions-json`). The **exact source-file bytes** are the
  authoritative parse and SHA256 source (the parsed object drives fingerprint,
  binder input and consumer); a supplied Mapping must deep-equal that parse.
  Input and output paths must differ (no source overwrite), and output uses a
  **fresh-path, no-clobber** policy (the atomic writer independently refuses an
  existing destination; only the task-created temp is removed on failure).
- The **default** native-daily behavior (flag absent) is unchanged.
- CH3A design audit complete, including **FIX1** (external anchors & margin semantics) and
  **FIX2** (historical-artifact anchors & review semantics) — code-read-only; see
  `docs/research/TASK-014CH3A_REVIEW_MARGIN_FRESHNESS_DESIGN_AUDIT.md` (the **FIX2** section
  is authoritative). No runtime wiring changed; CH2 (`--ws-bound-plan-only`) remains the
  latest executable terminal boundary. Corrected next stage (Option B + manifest **M2**): a
  separate `--ws-bound-plan-review-only` mode taking EXACT wrapper + source bytes plus a
  trusted external `--ws-bound-plan-anchor-manifest-json` (captured from the CH2 summary).
  Source/canonical/source-WS SHA+fingerprint identities are **externally pinned** (the
  wrapper fp is NOT exposed by CH2, so it is only internally self-consistent, not externally
  anchored). Freshness is **binding-time only** (`binding_time_freshness_verified=True`;
  `current_market_freshness_status=NOT_EVALUATED`) — a review may run much later and PASS
  proves only historical validity, not present executability. No independent offline
  projected-margin rate exists, so `offline_projected_margin_review_complete=False`
  (`UNAVAILABLE_NO_INDEPENDENT_RATE`); account feasibility `UNAVAILABLE_NOT_EVALUATED`; the
  expected 50-symbol set is pinned to externally-preserved hashes (run-date, not latest_date).
  CH3 PASS is never execution-ready. Execution remains unauthorized; Pilot remains 0/7.
- **CH3B1: the pure offline review core exists** —
  `src/demo_strategy_native_ws_bound_plan_review.py`
  (`build_ws_bound_plan_review`). It takes exact trusted anchor-manifest bytes +
  exact CH2 wrapper bytes + exact source-WS bytes, pins identity to the external
  manifest, re-runs the CH1 consumer, builds an immutable V1 exposure review and an
  offline margin-arithmetic review, and returns a terminal review-envelope Mapping
  (references only; no embedded Plan). **No CLI/runtime wiring yet** (CH3B2 will add
  it and reuse the CH2 race-safe writer). Review is **historical binding-time only**
  (`binding_time_freshness_verified=True`; `current_market_freshness_status=NOT_EVALUATED`,
  `current_market_freshness_checked=False`); the projected-margin rate is unavailable
  (`offline_projected_margin_review_complete=False`,
  `UNAVAILABLE_NO_INDEPENDENT_RATE`); account feasibility `UNAVAILABLE_NOT_EVALUATED`;
  `execution_readiness=False`. The core is pure (no file/network/wall-clock, no
  readiness/gate/execution/sender/Pilot/reporting import). CH2 remains the latest
  executable terminal boundary; Pilot remains 0/7.
- CH3B1_FIX1: immutable review-helper boundary corrected — a single narrow
  `_extract_frozen_projections` is the ONLY reader of the parsed wrapper; the exposure
  and margin-arithmetic helpers now receive frozen scalar projections
  (`WsBoundPlanReviewPriceProvenance` / `WsBoundPlanReviewMarginInputs`) only and never a
  Mapping. Pre/post-extraction wrapper+canonical fingerprints must be identical. Margin
  arithmetic now REQUIRES the wrapper-embedded gross (== 10,000) and rejects a non-null
  applicable account rate; failed results use the dedicated
  `OFFLINE_PROJECTED_MARGIN_RATE_NOT_EVALUATED`. Manifest symbols must be pre-normalized
  (50 unique) and `run_date` is a validated YYYY-MM-DD calendar date (no clock read).
  Still no CLI wiring; historical binding-time review only; execution readiness false;
  CH2 remains the executable boundary; Pilot remains 0/7.

## Repository Cleanup

- TASK-REPO-001: Read-only audit complete
- TASK-REPO-002A: Runtime outputs untracked (31 files), .gitignore updated
- TASK-REPO-002B: Legacy AI logs frozen, CURRENT_STATE created
- TASK-REPO-002C: Architecture source of truth created
- Broken ref `refs/heads/feat/bb-slope-gate-v1.5.lock.cleared` still present
- Stray untracked files (`commit＃85550e0`, `fix`) await owner review

## Next Decision

WS evidence binding now has an explicit opt-in terminal Plan-only runtime
consumer (CH2). Remaining decisions: whether/how a later task consumes the
canonical WS-bound Plan beyond the terminal Plan-only artifact (readiness /
margin provenance), and whether to add a guarded live WS collection path.
README rewrite is queued as a separate task after architecture documentation.
