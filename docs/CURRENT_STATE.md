# Current State

## Project

Multi-asset quantitative trading research system. Crypto momentum strategy
with Bybit Demo execution pipeline, forward/paper recording, and monitoring.
Strategy-native V1 architecture with cost-aware signal generation.

## Git State

- **Remote stable (origin/main):** `703db19` (TASK-014CF closeout)
- **Local HEAD:** `f76d0ae` (repo: stop tracking obvious runtime outputs)
- **Local unpushed commits:**
  1. `c5c4bf2` — TASK-014CG: bind plan-only actions to websocket price evidence
  2. `4edbe50` — TASK-014CG_FIX1: emit canonical websocket-bound plan artifact
  3. `f76d0ae` — repo: stop tracking obvious runtime outputs

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
- **No integrated downstream runtime consumer.** The default REST price path
  remains the only active runtime integration. CG binding is orphaned code
  with no pipeline caller.

## Repository Cleanup

- TASK-REPO-001: Read-only audit complete
- TASK-REPO-002A: Runtime outputs untracked (31 files), .gitignore updated
- TASK-REPO-002B: Legacy AI logs frozen, CURRENT_STATE created
- Broken ref `refs/heads/feat/bb-slope-gate-v1.5.lock.cleared` still present
- Stray untracked files (`commit＃85550e0`, `fix`) await owner review

## Next Decision

Decide whether to integrate the WS evidence binding into the runtime pipeline,
archive it as reference code, or defer pending forward-validation results.
README rewrite is queued as a separate task after architecture documentation.
