# System Architecture

## System Purpose

Multi-asset quantitative trading research and execution preparation system.
Currently focused on crypto momentum (prev3y lookback, Bybit perpetuals).
Produces strategy signals, constructs target portfolios, plans execution
actions against Demo API prices, records forward validation results, and
generates paper-trading PnL. Live trading is not authorized; execution
remains Demo-only with explicit per-session authorization gates.

## Runtime Modes

| Mode | Description | Order dispatch |
|---|---|---|
| Research / Backtest | Historical signal generation, cost stress, variant studies | None |
| Forward Validation | Daily signal → position recording, PnL tracking, overlay checks | None |
| Paper Portfolio | Simulated fills at next-day open, fee/slippage modeling | None |
| Plan-only Demo | REST price fetch, qty rounding, batch planning; no send | None |
| Authorized Demo Execution | One-shot tiny adapter (SOLUSDT-locked); explicit gate | Demo only |
| Live Trading | Not implemented, not authorized | Forbidden |

## Canonical Data Flow

```
SQLite OHLCV
  → Price snapshot (parquet)
    → Universe membership (point-in-time market-cap filter)
      → Momentum signals (TargetPortfolio: top/bottom N at ±0.02 weight)
        → Forward Record (position_usd = weight × 10,000 frozen capital)
          → Paper fills (simulated at next-day open + fees/slippage)
          → Forward Source (normalized signals + SHA256 artifact proof)
            → Action Planner (REST price → qty floored to qty_step)
              → Strategy Review (reconcile vs open positions)
                → Execution Gate (plan-only; never dispatches)
                  → Reporting (JSON/Excel → Discord/Notion, gated)
```

### Stage Detail

| Stage | Module | Input | Output | Consumer |
|---|---|---|---|---|
| Price snapshot | `src/data/crypto_daily.py` | SQLite DB | PriceSnapshotInfo (parquet) | Universe, signals |
| Universe | `src/universe/prev3y_crypto.py` | Prices + CMC rankings | UniverseSnapshotInfo (parquet) | Signal generation |
| Signals | `src/signals/prev3y_momentum.py` | Prices + universe | List[TargetPortfolio] | Forward record, planner |
| Forward Record | `apps/forward_record/primary.py` | Config + market data | TrackRecord (positions DataFrame) | Forward source, dashboard |
| Paper fills | `apps/paper_trading/recorder.py` | Targets + prices | Simulated fill DataFrame | PnL calculator |
| Forward Source | `src/demo_strategy_pilot_forward_source.py` | Run date + artifacts | ForwardStrategySourceResult | Daily runner |
| Action Planner | `src/demo_strategy_pilot_action_planner.py` | Signals + REST prices | PlannerResult (StrategyNativeAction list) | Strategy review |
| Strategy Review | `src/demo_strategy_native_v1_portfolio.py` | Plan + positions + rules | ExecutionBatch + feasibility | Execution gate |
| Freshness Audit | `src/demo_strategy_native_margin_freshness_audit.py` | Price snapshots + timestamps | Freshness status + blockers | Strategy review |
| Execution Gate | `src/demo_strategy_pilot_execution_gate.py` | Planner actions + readiness | Review verdict (no dispatch) | Daily runner |
| Daily Runner | `src/demo_strategy_pilot_daily_runner.py` | All above | PilotDailyRecord (JSON + Excel) | Reporting |
| Native Execution | `src/demo_strategy_pilot_native_execution.py` | StrategyNativeAction + transport | Delivery ledger | Readiness state |
| Readiness | `src/demo_strategy_pilot_readiness.py` | Pilot state + events | State machine verdict | Daily runner |

## Current Price Paths

### Integrated: REST (active)

The action planner calls `provider.market_price(symbol)` through
`DemoMarketPriceGuard` (`src/demo_market_price_guard.py`), which issues a
public GET to `https://api-demo.bybit.com/v5/market/tickers`. No
authentication required. The returned float price is used to compute
`qty = |target_notional| / price`, floored to instrument `qty_step` via
pure Decimal arithmetic. This is the only price path consumed by the
planner and daily runner.

### Offline: Public WebSocket evidence (not integrated)

`src/demo_public_ws_ticker_evidence.py` defines the schema for collecting
public linear WebSocket ticker snapshots (mainnet
`wss://stream.bybit.com/v5/public/linear`, no credentials). Evidence is
collected via `scripts/collect_public_ws_ticker_evidence.py`.

`src/demo_strategy_native_ws_price_binding.py` (TASK-014CG/FIX1) binds
planner actions to WS source messages post-hoc, producing a
canonical-bound-plan artifact with same-message proof and freshness
completion status.

### Opt-in: native Plan-only WS-bound consumer (CH1/CH2)

`src/demo_strategy_native_ws_bound_plan_consumer.py` (CH1) is a pure,
fail-closed validator (`validate_ws_bound_plan_artifact`) for a canonical
WS-bound Plan: fingerprint/provenance, signed Strategy-native V1 semantics
(±0.02 weight, ±200 USDT notional, 10,000 USDT capital), authoritative
clock-offset freshness, and per-symbol source-record cross-validation.

`src/demo_strategy_native_ws_bound_plan_only.py` (CH2) wires it as an explicit
opt-in TERMINAL Plan-only path of the native daily runner
(`scripts/run_demo_strategy_pilot_native_daily.py --ws-bound-plan-only`): it
produces the REST seed Plan, reads a **caller-supplied** public-WS evidence
JSON file (no live WS collection), binds it, validates through the CH1
consumer, and writes exactly one canonical WS-bound Plan wrapper. The path is
opt-in only, stops **before** active review / readiness / execution gate /
native execution, never advances the Pilot, keeps execution unauthorized, and
has **no REST fallback** once WS binding begins.

The **default** native runtime (flag absent) is unchanged and continues to use
the REST planner path. No readiness/gate/execution/Pilot module is reached by
the Plan-only WS path.

CH2_FIX1 isolation hardening: the Plan-only mode-conflict validation runs as the
FIRST branch of `main()` — before the reconcile/reporting branch, the
`PilotStateStore` RUNNING gate, provider construction, source read and output
write — and rejects every execution/reporting/Pilot-mutating flag. The EXACT
source-file bytes are the single source of truth: they are parsed inside the
pure core and that parsed object drives the logical fingerprint, the binder
input and the consumer source artifact; the byte SHA256 is taken from those same
bytes; any supplied Mapping must deep-equal the exact-bytes parse. Input and
output paths must resolve to different files (the source is never overwritten),
and the output is fresh-path no-clobber (the atomic writer independently refuses
an existing destination and removes only the task-created temp on failure).

## Execution Safety Boundary

- **Plan-only vs send**: The daily runner sets `order_execution_authorized = False`.
  Actions are planned but never dispatched in normal operation.
- **Authorization gate**: Real execution requires the one-shot tiny adapter
  (`src/demo_only_tiny_execution_adapter.py`), locked to SOLUSDT, with
  explicit per-session manual authorization.
- **Demo-only**: All execution targets `api-demo.bybit.com`. Protected
  symbols are rejected. Ambiguous outcomes fail closed.
- **Live**: Not implemented, not authorized. `FORBIDDEN` in all validation
  records.
- **Future safety doc**: `docs/TRADING_SAFETY.md` (to be created) will
  contain the complete execution authorization protocol.

## Reporting and Runtime Artifacts

| Category | Location | Tracked | Retention |
|---|---|---|---|
| Source code | `src/`, `apps/`, `scripts/` | Yes | Permanent |
| Stable test fixtures | `tests/` | Yes | Permanent |
| Configuration | `configs/` | Yes (except secrets) | Permanent |
| Forward record baselines | `outputs/forward_record/baselines/` | Yes | Owner decision |
| Runtime logs | `outputs/logs/` | No (gitignored) | Local/VPS |
| Monitor heartbeats | `outputs/monitor/` | No (gitignored) | Local/VPS |
| Generated dashboard | `outputs/forward_record/dashboard/` | No (gitignored) | Regenerated |
| Daily forward/paper outputs | `outputs/forward_record/daily_logs/` | No (gitignored) | Local/VPS |
| Demo trading outputs | `outputs/demo_trading/` | No (gitignored) | Local |
| Research variant outputs | `outputs/research/` | No (gitignored) | Local |

## Source-of-Truth Table

| Concern | Canonical Module | Notes |
|---|---|---|
| Strategy signals | `src/signals/prev3y_momentum.py` | 3y lookback, top/bottom N |
| Universe selection | `src/universe/prev3y_crypto.py` | Point-in-time CMC rankings |
| Portfolio construction | `src/demo_strategy_native_v1_portfolio.py` | Reconcile + ExecutionBatch |
| Action planner | `src/demo_strategy_pilot_action_planner.py` | REST price → qty rounding |
| Price freshness | `src/demo_strategy_native_margin_freshness_audit.py` | Fail-closed staleness |
| Margin audit | `src/demo_strategy_native_margin_freshness_audit.py` | Combined with freshness |
| Authorization gate | `src/demo_strategy_pilot_execution_gate.py` | Review only, no dispatch |
| Demo sender | `src/demo_strategy_pilot_native_execution.py` | Demo endpoint only |
| Forward Record | `apps/forward_record/primary.py` | Frozen 10k capital base |
| Paper Portfolio | `apps/paper_trading/recorder.py` | Simulated fills |
| WS evidence schema | `src/demo_public_ws_ticker_evidence.py` | Public linear, no auth |
| WS-bound offline artifact | `src/demo_strategy_native_ws_price_binding.py` | Binder |
| WS-bound Plan consumer | `src/demo_strategy_native_ws_bound_plan_consumer.py` | CH1 fail-closed validator |
| WS-bound Plan-only wiring | `src/demo_strategy_native_ws_bound_plan_only.py` | CH2 opt-in terminal path |
| Daily orchestrator | `src/demo_strategy_pilot_daily_runner.py` | DRY-RUN only |
| Readiness state machine | `src/demo_strategy_pilot_readiness.py` | 7-day gate |
| Current state | `docs/CURRENT_STATE.md` | Updated per cleanup task |

## Parallel and Legacy Paths

| Lineage | Key modules | Status |
|---|---|---|
| Close-only | `demo_close_only_sender.py`, `demo_close_only_cleanup.py` | Pre-V1; owner review needed |
| New-entry | `demo_new_entry_sender.py`, `demo_new_entry_review.py`, `demo_new_entry_candidate_builder.py` | Pre-V1; owner review needed |
| Tiny-guarded / scaffold | `demo_tiny_guarded_entry_*.py` (~30 files), `demo_tiny_lifecycle_*.py` | Pre-V1; owner review needed |
| Strategy-native V1 | `demo_strategy_pilot_*.py`, `demo_strategy_native_*.py` | **Current active path** |
| Report-only | `demo_strategy_pilot_reporting.py`, `demo_strategy_pilot_discord_notify.py`, `demo_strategy_pilot_notion_sync.py` | Active, gated |
| One-shot execution adapter | `demo_only_tiny_execution_adapter*.py` | SOLUSDT-locked; canonical for real Demo orders |

The Strategy-native V1 lineage is the current active path. Close-only,
new-entry, and tiny-guarded lineages are legacy code from earlier
development iterations that require owner review for archival or removal.

## Known Architecture Risks

1. **Multiple Demo lineages**: Close-only, new-entry, tiny-guarded, and
   Strategy-native V1 coexist. Only V1 is current; others are dead code
   risk.
2. **WS-bound artifact consumer**: The canonical-bound-plan now has a CH1
   fail-closed consumer and a CH2 opt-in terminal Plan-only native consumer.
   It is still NOT consumed by readiness, margin audit, the execution gate, or
   native execution (by design — execution remains unauthorized).
3. **Target vs effective notional**: Planner computes `qty = notional / price`
   floored to `qty_step`. The effective notional after rounding differs
   from the strategy target. No reconciliation of this gap exists.
4. **Historical tracking of generated artifacts**: Prior commits tracked
   runtime logs, dashboards, and monitor outputs. REPO-002A untracked 31
   files; residual generated content may remain in history.
5. **No single integrated consumer**: No module combines WS evidence +
   planner actions + execution dispatch in one pipeline. The offline
   binding and the REST planner path remain separate.

## Next Architecture Decision

The native Plan-only pipeline now consumes the canonical WS-bound Plan via an
explicit opt-in TERMINAL path (CH1 consumer + CH2 wiring), gated before
review/readiness/execution. The remaining decision is whether a later task
should extend consumption into readiness / margin provenance (still without
authorizing execution), and whether a guarded live WS collection path is
warranted. Default REST-only planning remains unchanged in the meantime.
