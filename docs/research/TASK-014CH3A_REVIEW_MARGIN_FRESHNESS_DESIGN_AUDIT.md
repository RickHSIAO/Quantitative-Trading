# TASK-014CH3A — Review / Margin / Freshness Integration Design Audit

**Status:** code-read-only design audit. No Python/runtime/test changes.
**Audited at HEAD:** `fdfd62e68de9c9cd54028161aa3428fe82d6a968`
**Scope:** design the next stage — *validated canonical WS-bound Plan → read-only
execution review → projected-margin review → freshness/provenance review →
terminal artifact/report* — which must remain terminal **before** readiness,
execution gate, native execution, sender, order transport, and Pilot advancement.

Execution remains unauthorized. Pilot `BYBIT_DEMO_PILOT_7D_202606_V1` remains 0/7.

---

## 2. Current CH2 terminal boundary

- **Terminus:** `scripts/run_demo_strategy_pilot_native_daily.py::_run_ws_bound_plan_only`
  (≈ lines 984–1125). Dispatched as the FIRST branch of `main()` (before
  test-injected/reconcile/`PilotStateStore`). After CH1 PASS it calls
  `wsbpo.atomic_write_wrapper(output, result.wrapper_artifact)` (line 1118) and
  returns `WS_BOUND_PLAN_ONLY_PASS`. Nothing else runs.
- **Object after CH1 PASS:** `wsbpo.WsBoundPlanOnlyResult`. The downstream-exposed
  object is the **raw wrapper Mapping** (`result.wrapper_artifact`), i.e. the binder
  wrapper whose `canonical_bound_plan` holds `planner.target_positions` (50 priced
  targets), `rebuilt_price_dependent_review` (projected margin), `binding_epoch_ns`,
  fingerprints. The CH1 `validated_actions` tuple (frozen `ValidatedBoundAction`) is
  computed inside CH1 and **discarded** — not retained in the CH2 result.
- **Anchors available at the boundary:** `canonical_bound_plan_fingerprint`,
  `source_ws_artifact_fingerprint`, `source_ws_artifact_sha256`,
  `original_plan_fingerprint`, `binding_epoch_ns`, `freshness_threshold_ms`
  (all on `WsBoundPlanOnlyResult`, which is a frozen dataclass).
- **Immutability:** `WsBoundPlanOnlyResult` is frozen; `ValidatedBoundAction` is frozen;
  but `wrapper_artifact` / `canonical_bound_plan` are **plain mutable dict/list**
  Mappings (JSON-loaded). CH3 must treat them as immutable (deep-copy before any view).

## 3. Review functions discovered

| Function | Module | Input | Pure? | Reads Plan prices/qty? | Recomputes? | Reaches gate/exec/sender? |
|---|---|---|---|---|---|---|
| `build_active_v1_review` | `scripts/run_demo_strategy_pilot_native_daily.py:581` | provider + PlannerResult | **NO — REST network** (`provider.market_price`, instrument rules, risk-limit, server-time) | yes (REST) | partially | no, but network-dependent |
| `build_strategy_native_review` | `src/demo_strategy_native_v1_portfolio.py:825` | `plan` object w/ `.target_positions`, prices, evidence | **pure** (imports rd/md/ce constants+helpers only) | reads `target_notional` (uses `.copy_abs()`); recomputes qty/rule fingerprints | yes | **no** (builds non-dispatching `ExecutionBatch`; authorizes nothing) |
| `gate.evaluate_execution_gate` | `src/demo_strategy_pilot_execution_gate.py` | plan + open positions | pure (no net) | yes | yes | **IS the execution-authorization gate** (delegates; no dispatch) — CH3 forbidden |
| `assess_feasibility` / `build_execution_batch` | `demo_strategy_native_v1_portfolio.py:706/541` | targets+rules+account | pure | yes | yes | builds batch only (no send) |

Key: a pure offline review for CH3 already exists in spirit (`build_strategy_native_review`)
**but it expects `plan.target_positions` as an attribute** and is currently fed by the
network `build_active_v1_review`. CH3 needs a thin **read-only adapter** exposing
`canonical_bound_plan.planner.target_positions` (a Mapping list) as `.target_positions`,
plus prices already embedded in the bound actions — **no provider, no REST**.

## 4. Projected-margin path

| Function | Module | Offline-pure? | Signed handling |
|---|---|---|---|
| `build_projected_margin_model` | `demo_strategy_native_margin_freshness_audit.py:365` | **pure/offline** | takes a scalar `strategy_gross_notional`; `strat_im = strat*rate`. Does NOT abs internally — caller must pass absolute gross |
| `normalize_margin_evidence` | `…freshness_audit.py:220` | pure | per-position margin; account-data driven |
| `project_action_margin` / `build_account_margin_model` | `…risk_tier_audit.py:351/431` | pure but needs **risk-limit tiers (private/public REST)** | per-action tiers |
| `_rebuild_projected_margin` | `demo_strategy_native_ws_price_binding.py:884` | **pure/offline** | `strategy_gross = sum(_dec(t.target_notional).copy_abs())` → already embedded in `canonical_bound_plan.rebuilt_price_dependent_review` |
| `build_strategy_native_review` gross | `…v1_portfolio.py:874` | pure | `sum(_dec(t.target_notional).copy_abs())` |

- **From the Plan (offline):** gross/long/short notional, projected strategy IM (needs an
  authoritative applicable rate), per-symbol contribution, qty/price/notional consistency.
- **From account/private API:** wallet equity, available balance, per-position IM/leverage,
  risk-limit tiers. **Not available offline** → CH3 projected-margin is *strategy-gross +
  price/qty consistency* only; account-feasibility stays UNAVAILABLE/None (fail-closed),
  never fabricated.
- **Signed-notional safety:** the binder already preserves signed `target_notional`
  (long `+200`, short `-200`). Absolute exposure is taken at the `.copy_abs()` boundary in
  both `_rebuild_projected_margin` and `build_strategy_native_review`. **Risk:**
  `build_projected_margin_model` will mis-size if a caller sums *signed* notionals
  (net≈0 → IM≈0). **CH3 rule:** gross MUST be `sum(|target_notional|)` (== 10,000), long
  gross `sum(+200)=5,000`, short gross `sum(|-200|)=5,000`. Active prices come ONLY from
  the WS-bound actions (`price == price_evidence.selected_price`); REST seed price is
  audit-only (`rest_planning_price`) and must never re-enter.
- **Narrowest safe CH3 margin fn:** re-verify the binder's already-embedded
  `rebuilt_price_dependent_review` and recompute `strategy_gross` via `.copy_abs()` from the
  canonical targets; optionally call `md.build_projected_margin_model` with that absolute
  gross + `md.unavailable_margin_evidence()` (no account data) → status stays PARTIAL/UNAVAILABLE.

## 5. Freshness / provenance consumers

| Field | Consumer (recompute vs trust) | Needs source artifact / exact bytes / clock |
|---|---|---|
| wrapper / cbp / source-msg / action / original-plan fingerprints | **CH1 `validate_ws_bound_plan_artifact` recomputes all** (binder fns) | source artifact yes; bytes-SHA yes; clock no |
| `source_ws_artifact_sha256` | CH2 core computes from **exact bytes** | exact bytes yes |
| `source_ws_artifact_fingerprint` | CH2 core recomputes via `ws._fingerprint` | source mapping (from exact bytes) |
| `execution_grade_freshness_complete`, `price_binding_freshness_status`, binding status counts, per-action FRESH | **CH1 recomputes via `wb._evaluate_binding_freshness`** with authoritative clock-offset + caller binding epoch/threshold; stored values never trusted alone | source records yes; clock NO (caller epoch) |
| `binding_epoch_ns`, `freshness_threshold_ms`, evidence age | CH1 re-derives age exactly; compares stored age | caller-supplied epoch/threshold |

**CH1 invariant to preserve:** stored PASS/FRESH/COMPLETE alone are never sufficient.
**Stale-time risk:** between CH1 PASS and CH3 review nothing recomputes against the wall
clock (binding epoch is frozen, caller-supplied), so there is no clock drift; the only
stale risk is a *mutated source artifact* between validation and review → CH3 must re-pin
to the **same exact source bytes + Mapping** (re-run CH1) rather than trust the CH2 result.

## 6. Execution-capable boundary table

| Boundary | Module/function | Read-only? | Network? | Pilot mutation? | Order capable? | Allowed in CH3? |
|---|---|---|---|---|---|---|
| WS-bound Plan-only terminus | `_run_ws_bound_plan_only` | yes | no | no | no | **yes (CH2, terminal)** |
| Active V1 review | `build_active_v1_review` (script:581) | yes | **yes (REST)** | no | no | **no (REST)** |
| Pure V1 review | `v1.build_strategy_native_review` (825) | yes | no | no | no | yes (via offline adapter) |
| Projected margin (gross) | `md.build_projected_margin_model` (365) | yes | no | no | no | yes (offline) |
| Risk-tier margin | `ce.project_action_margin` (351) | yes | **yes (risk-limit REST)** | no | no | no |
| Execution gate | `gate.evaluate_execution_gate` (824/1227) | yes | no | no | no (delegates) | **no (authorization gate)** |
| Gated send surface | `orchestrate_gated_send` (791) | n/a | no | no | no (refuses) | **no** |
| Native execution | `nx.execute_daily_native` (902) | no | **yes** | no | **yes (transport)** | **no** |
| Pilot advancement | `nx.advance_successful_day` (915) | no | no | **yes** | no | **no** |
| Reporting/reconcile | `nrep.finalize_native_day`/`reconcile_outputs_only` (909/1153) | no | **yes (Notion/Discord)** | no | no | **no** |
| Readiness/Pilot state | `rd.PilotStateStore` (1161) | read | no | **yes (write paths)** | no | **no** |

CH3 stops before the first row that is readiness-capable / account-network-dependent /
execution-authorizing / sender-capable / Pilot-mutating — i.e. before
`build_active_v1_review`, `evaluate_execution_gate`, `execute_daily_native`,
`advance_successful_day`, `PilotStateStore`, and reporting.

## 7. Integration options

| Criterion | A: extend CH2 result + new pure CH3 orchestrator | B: CLI reloads written wrapper + source, re-run CH1, then review | C: modify `build_active_v1_review`/`build_strategy_native_review` to read the CH2 wrapper directly |
|---|---|---|---|
| Trust-boundary clarity | high (anchors flow in-process) | **highest** (review re-pins to exact bytes on disk; matches CH2 file artifact) | low (review entangled w/ network provider) |
| Duplicate-validation risk | medium (CH1 once; re-verify view) | re-runs CH1 (intended, cheap, deterministic) | high |
| Mutation risk | wrapper is mutable dict in-process | re-load from bytes → fresh immutable parse | high (shared mutable review state) |
| Fingerprint/provenance preservation | good | **exact (re-pins SHA + fp from bytes)** | poor |
| Stale-time risk | low | **lowest** (re-pins to file bytes) | medium |
| Testing complexity | medium | low–medium (pure fns + file I/O seam) | high |
| Default-path compatibility | unchanged | unchanged | **risk of changing default review** |
| Risk of reaching readiness/exec | low | **lowest** (separate pure orchestrator) | **high** (review path is adjacent to gate) |

> **SUPERSEDED by the FIX1 corrections at the end of this document.** The original
> Option B sketch below under-specified the external anchors and immutability; the
> corrected, authoritative design is in **"FIX1 — External-anchor & margin-semantics
> corrections"**. Read that section as the binding design for CH3.

**Recommendation (original, superseded): Option B** — a separate `--ws-bound-plan-review-only` mode that reads
the already-written CH2 wrapper **and** the original source WS evidence file (exact bytes),
re-runs the CH1 consumer to re-pin all fingerprints/SHA/freshness, then builds an offline
review+margin artifact. It maximizes trust-boundary clarity, re-pins to exact bytes (no
stale-time risk), reuses CH1 verbatim, keeps the default and CH2 paths byte-unchanged, and
is structurally farthest from readiness/gate/execution. (Option A is the close second if a
single-invocation bind+review is later desired; Option C is rejected — it entangles the
network review path and risks the default behavior.)

## 8. Proposed CH3 contract

```python
@dataclass(frozen=True)
class WsBoundPlanReviewResult:
    status: str
    blockers: tuple[str, ...]
    review_artifact: Mapping[str, Any] | None     # envelope referencing wrapper by fp
    canonical_bound_plan_fingerprint: str | None
    source_ws_artifact_fingerprint: str | None
    source_ws_artifact_sha256: str | None
    original_plan_fingerprint: str | None
    binding_epoch_ns: int | None
    freshness_threshold_ms: int | None
    review_complete: bool
    projected_margin_review_complete: bool
    freshness_provenance_verified: bool
    readiness_called: bool            # always False
    execution_gate_called: bool       # always False
    native_execution_called: bool     # always False
    pilot_advanced: bool              # always False
```

- **Pure core:** `build_ws_bound_plan_review(*, wrapper, source_ws_artifact, source_ws_artifact_bytes,
  expected_policy_id, expected_strategy_id, expected_run_date, expected_symbols,
  expected_binding_epoch_ns, expected_freshness_threshold_ms) -> WsBoundPlanReviewResult`.
- **Caller-owned anchors:** policy/strategy/date/symbols/epoch/threshold + exact source bytes
  (never derived from the wrapper). **Original source WS Mapping + exact bytes are MANDATORY.**
- **CH1 reuse:** **re-run** `validate_ws_bound_plan_artifact` (do not trust the CH2 result);
  expose review only on CH1 PASS.
- **Immutability:** deep-copy the canonical plan into a read-only view before computing;
  assert the wrapper/cbp fingerprints recompute identically afterward (review never mutates).
- **Signed vs absolute:** review carries signed `target_notional` (long `+200`/short `-200`)
  verbatim; all margin/exposure math uses `|target_notional|` (gross 10,000; long 5,000;
  short 5,000) — never net.
- **Status vocab:** `WS_BOUND_PLAN_REVIEW_PASS`, `…_INPUT_INVALID`, `…_CONSUMER_FAILED`,
  `…_REVIEW_FAILED`, `…_MARGIN_REVIEW_FAILED`, `…_PROVENANCE_FAILED`, `…_OUTPUT_EXISTS`,
  `…_OUTPUT_FAILED`. **Failure precedence:** input → consumer(CH1) → provenance/freshness →
  review → margin → output. Any failure ⇒ terminal, no artifact, `*_called`/`pilot_advanced` all False.

## 9. Proposed CLI mode

- Introduce a **separate, mutually exclusive** flag **`--ws-bound-plan-review-only`** with
  `--ws-bound-plan-wrapper-json <IN>`, `--ws-ticker-evidence-json <IN>`,
  `--ws-bound-plan-review-output-json <OUT>` (+ optional explicit epoch/threshold to re-pin).
  Explicit opt-in; disabled by default; mutually exclusive with `--ws-bound-plan-only`.
- Guarantees: no second Plan generation; no duplicate wrapper output (review envelope only);
  no REST fallback; no readiness/gate/execution/Pilot; exact source bytes authoritative;
  CH2 Plan-only behavior byte-unchanged.
- **Rejected flags in CH3 mode:** `--ws-bound-plan-only`, `--send-orders-to-demo`,
  `--advance-on-success`, `--reconcile-outputs-only`, `--allow-notion-network`,
  `--allow-discord-network`, `--test-injected-actions-json` → deterministic `_INPUT_INVALID`.

## 10. Artifact design

- Write **one separate review artifact** = an **envelope** that **references the canonical
  wrapper by fingerprint** (`canonical_bound_plan_fingerprint`, `wrapper_fingerprint`,
  `source_ws_artifact_sha256`, `source_ws_artifact_fingerprint`, `original_plan_fingerprint`)
  plus the review/margin/freshness results. **Do NOT duplicate the full Plan** (only
  reference + per-symbol review rows). Input wrapper path, source path, and review output
  path must all differ.
- Output uses the **same CH2 atomic create-if-absent / no-clobber** policy
  (`os.link` publication, `os.path.lexists` reject, temp-only cleanup, race-safe).
- **Stale-artifact prevention:** the envelope binds the review to the *current* wrapper +
  source SHA/fingerprints; on read, mismatched fingerprints/SHA between the supplied wrapper
  and source ⇒ fail; a prior run's envelope cannot be mistaken because it is keyed to its
  source SHA and is never overwritten (fresh-path only).

## 11. Future CH3 test matrix (summary)

valid review PASS; short `-200` → absolute exposure; gross == 10,000; long == 5,000; short
== 5,000; 50 actions 25/25; active prices all from WS-bound actions; REST seed price cannot
reappear; source WS fp/SHA lineage preserved; original-plan fp preserved; canonical-plan fp
preserved; stale/mutated source fails; review cannot mutate canonical Plan (post-review fp
identical); margin-review failure terminal; **no readiness / gate / native-exec / sender /
Pilot-write / Notion / Discord calls (counter-raisers)**; no REST fallback; default
native-daily unchanged; CH2 Plan-only unchanged; no output/temp on failure; no-clobber
destination-race behavior.

## 12. Future implementation file list (for CH3, NOT this task)

- new `src/demo_strategy_native_ws_bound_plan_review.py` (pure review/margin/freshness core
  + thin envelope writer reusing CH2 atomic helpers);
- `scripts/run_demo_strategy_pilot_native_daily.py` (add `--ws-bound-plan-review-only` branch);
- new `tests/demo_trading/test_demo_strategy_native_ws_bound_plan_review_wiring.py`;
- docs updates only after the runtime truth changes.
Reused unchanged: `demo_strategy_native_ws_bound_plan_consumer` (CH1),
`demo_strategy_native_margin_freshness_audit.build_projected_margin_model`,
`demo_strategy_native_v1_portfolio.build_strategy_native_review` (via offline adapter).

---

# FIX1 — External-anchor & margin-semantics corrections (authoritative; supersedes §7–§13)

The original Option B was incomplete: a *review-only* process must obtain **every** CH1
caller-owned expected value from a source **independent of the wrapper under validation**.
A value copied from that wrapper lets the artifact define its own acceptance and is
rejected. This section is the binding CH3 design.

## F1. Complete CH1 external-anchor contract

`validate_ws_bound_plan_artifact(wrapper, *, source_ws_artifact, expected_policy_id,
expected_strategy_id, expected_run_date, expected_original_plan_fingerprint,
expected_ws_artifact_sha256, expected_ws_artifact_fingerprint, expected_binding_epoch_ns,
expected_freshness_threshold_ms, expected_symbols)`.

| CH1 expected value | Independent CH3 source (never the wrapper) |
|---|---|
| `expected_policy_id` | fixed constant `wb.ACTIVE_STRATEGY_NATIVE_V1_POLICY` (`ACTIVE_STRATEGY_NATIVE_V1_POLICY`) |
| `expected_strategy_id` | fixed constant `wb.EXPECTED_STRATEGY_NAME` = `prev3y_crypto_combined_paper_safe_variant` |
| `expected_run_date` | required CLI `--date`, cross-checked vs Forward Record `forward_summary.latest_date` (offline) |
| `expected_original_plan_fingerprint` | **B1**: required CLI `--expected-original-plan-fingerprint` (from the trusted CH2 run summary) |
| `expected_ws_artifact_sha256` | computed in-core from the EXACT source-WS-evidence bytes (`wb.compute_file_sha256`) |
| `expected_ws_artifact_fingerprint` | recomputed in-core `ws._fingerprint(parsed_source minus artifact_fingerprint)` from exact bytes |
| `expected_binding_epoch_ns` | **required** CLI `--ws-binding-epoch-ns` (from CH2 summary) |
| `expected_freshness_threshold_ms` | **required** CLI `--ws-binding-freshness-threshold-ms` (from CH2 summary; >0, ≤10_000) |
| `expected_symbols` (50) | canonical OFFLINE Forward Record source (F3) or required `--expected-strategy-symbols-json` |

CH1 still recomputes wrapper/canonical/source/source-message/action fingerprints and
exact-offset freshness internally; stored PASS/FRESH/COMPLETE remain insufficient.

## F2. Original-plan fingerprint anchor — choose B1

- **B1 (chosen):** required CLI `--expected-original-plan-fingerprint sha256:<64hex>`. The
  CH2 summary prints `original_plan_fingerprint`; the operator copies it from the trusted
  CH2 stdout, independent of the wrapper file. Narrowest design; no Plan regenerate/duplicate.
- **B2 (rejected default):** re-supply original seed-Plan JSON and re-fingerprint — duplicates
  the Plan, no trust gain.
- **B3 (forbidden):** derive from the wrapper (artifact defines its own expected value).
CH3 validates B1 is canonical `sha256:<64hex>`.

## F3. Expected 50-symbol set anchor — canonical offline source EXISTS

**Primary:** `src/demo_strategy_pilot_forward_source.py::load_primary_forward_strategy_result(
run_date=<--date>, repo_root=ROOT).normalized_signals` → the 25-long/25-short signal symbols.
This loader is offline, deterministic, no-network, does **not** invoke the planner, does
**not** read Pilot state; it reads tracked Forward Record artifacts (`forward_summary.json`,
`<YYYYMMDD>_positions.parquet`, `_forward_stats.json`, `_pnl.json`) and SHA256-hashes each,
and carries the authoritative `forward_summary.strategy` (cross-checked vs `expected_strategy_id`).
CH3 normalizes/uppercases, requires exactly 50 unique, and fingerprints via
`ws.canonical_strategy_symbol_set_fingerprint(symbols)`; Forward Record SHAs are recorded as
provenance.

**Alternative (explicit):** required `--expected-strategy-symbols-json <PATH>` (50 unique
normalized symbols), independently fingerprinted, matched to policy/strategy identity, never
from the wrapper. Deriving symbols from the wrapper is impossible by design.

## F4. Binding epoch & threshold are caller-owned (REQUIRED)

`--ws-binding-epoch-ns` and `--ws-binding-freshness-threshold-ms` are **REQUIRED** in
review-only mode; neither is defaulted or read from the wrapper (a separately authenticated
external manifest may alternatively supply them). Threshold is a positive int ≤ 10_000.
**How obtained:** the CH2 (`--ws-bound-plan-only`) run prints a JSON summary with
`binding_epoch_ns`, `freshness_threshold_ms` (and `original_plan_fingerprint`); the operator
copies those from that trusted invocation's stdout — not from the wrapper file.

## F5. Exact wrapper bytes authoritative (corrected pure contract)

```python
def build_ws_bound_plan_review(
    *, wrapper_artifact_bytes: bytes, source_ws_artifact_bytes: bytes,
    expected_original_plan_fingerprint: str, expected_binding_epoch_ns: int,
    expected_freshness_threshold_ms: int, expected_policy_id: str,
    expected_strategy_id: str, expected_run_date: str,
    expected_symbols: Sequence[str]) -> WsBoundPlanReviewResult: ...
```

- Parse BOTH byte inputs **inside** the pure core; require JSON object roots; **no fallback
  to any caller Mapping**.
- `wrapper_file_sha256 = wb.compute_file_sha256(wrapper_artifact_bytes)`;
  `source_file_sha256 = wb.compute_file_sha256(source_ws_artifact_bytes)` (literal bytes).
- Recompute both logical fingerprints from the parsed objects; use the parsed objects for
  CH1 validation and review. Record `wrapper_file_sha256` in the envelope **in addition to**
  the logical wrapper/canonical fingerprints.

## F6. Immutable review projection (corrected)

`deepcopy` is **not** read-only. CH3 builds `review_rows: tuple[ReviewActionRow, ...]` where
`ReviewActionRow` is `@dataclass(frozen=True)` with scalar fields only (symbol, side, signed
`target_notional`, price, qty, qty_step, effective_notional, source_message_fingerprint,
action_fingerprint) + scalar provenance fields; no reference to mutable target-position
dicts is retained, and no review helper receives the shared wrapper Mapping. Defensive:
recompute the wrapper fingerprint **before** and **after** review and the canonical
fingerprint **after**; any drift ⇒ terminal `WS_BOUND_PLAN_REVIEW_PROVENANCE_FAILED`.

## F7. Offline margin semantics (separated)

- **A. Exposure review:** 50 actions; 25 long / 25 short; signed notionals preserved (long
  `+200`, short `-200`); long 5,000; short_absolute 5,000; gross 10,000; net 0; qty/price/
  effective-notional consistency; active prices ONLY from validated WS-bound actions
  (`price == price_evidence.selected_price`; REST `rest_planning_price` never reused).
- **B. Projected strategy margin:** uses **absolute gross** `sum(|target_notional|)` (=10,000)
  → `md.build_projected_margin_model`; an IM rate applies only if an explicitly identified,
  independently-verified offline rate is present, else rate-projection is reported
  rate-unavailable (deterministic). Signed/net is **never** fed to the scalar gross helper.
- **C. Account feasibility:** equity, available balance, account IM/MM, risk tiers,
  leverage/mode, order feasibility — require private data; **not available** in CH3.

Result fields: `offline_exposure_review_complete = True`,
`offline_projected_margin_review_complete = True` (the step ran deterministically;
rate-projection may be rate-unavailable), `account_margin_feasibility_status =
UNAVAILABLE_NOT_EVALUATED`, `execution_readiness = False`. CH3 PASS is **never** described as
account-ready or execution-ready.

## F8. Corrected Option A vs B → corrected Option B

A (single bind+review) has anchors in-process but re-touches REST for the seed build each
run and is not truly "review-only". **Corrected Option B** is recommended: no REST at review
time, re-pins to exact wrapper+source bytes, structurally farthest from readiness/execution,
keeps default/CH2 byte-unchanged. It is acceptable BECAUSE every anchor now has an
independent source (fixed constants; `--date` cross-checked to the Forward Record; B1
original-plan fp; required epoch/threshold; symbols from the offline Forward Record or
explicit JSON; SHAs/fps from exact bytes). No expected value is taken from the wrapper.

## F9. Corrected CLI specification

Mode (mutually exclusive with `--ws-bound-plan-only`): **`--ws-bound-plan-review-only`**.
Required: `--ws-bound-plan-wrapper-json <IN>`, `--ws-ticker-evidence-json <IN>`,
`--ws-bound-plan-review-output-json <OUT>`, `--ws-binding-epoch-ns <POS_INT>`,
`--ws-binding-freshness-threshold-ms <POS_INT ≤ 10000>`,
`--expected-original-plan-fingerprint sha256:<64hex>`; expected symbols default from the
Forward Record (via `--date`) else `--expected-strategy-symbols-json <PATH>`. All THREE
paths pairwise distinct (realpath/normcase); review-out ≠ either input. Output uses the
existing CH2 race-safe atomic create-if-absent / no-clobber writer.
Rejected flags (`_INPUT_INVALID`): `--ws-bound-plan-only`, `--send-orders-to-demo`,
`--advance-on-success`, `--reconcile-outputs-only`, `--allow-notion-network`,
`--allow-discord-network`, `--test-injected-actions-json`.

## F10. Corrected envelope fields (references + results; no full-Plan duplicate)

`wrapper_file_sha256`, `wrapper_logical_fingerprint`, `canonical_bound_plan_fingerprint`,
`source_ws_file_sha256`, `source_ws_logical_fingerprint`, `original_plan_fingerprint`,
`expected_symbol_set_fingerprint`, `binding_epoch_ns`, `freshness_threshold_ms`,
`review_rows` (or aggregate `review_rows_fingerprint`), `offline_exposure_totals`
(long 5,000 / short_abs 5,000 / gross 10,000 / net 0), `offline_projected_margin_result`,
`account_margin_feasibility_status = UNAVAILABLE_NOT_EVALUATED`, `execution_readiness = false`,
and `readiness_called / execution_gate_called / native_execution_called / pilot_advanced`
= false + order/sender/reporting counters = 0. Fresh output path; race-safe atomic
publication; envelope references the wrapper by fingerprint/SHA (no embedded Plan) and is
keyed to the source SHA so a prior run's envelope cannot be mistaken for the current result.

## F11. Corrected future test matrix (additions)

original-plan fp omitted → INPUT_INVALID; wrong original-plan fp → CONSUMER_FAILED;
expected symbols cannot be derived from the wrapper (no such path); wrong external symbol set
→ fail; required epoch omitted → INPUT_INVALID; required threshold omitted → INPUT_INVALID;
wrapper exact-byte SHA preserved in envelope; wrapper bytes invalid/non-object → fail;
wrapper Mapping never separately trusted (only exact bytes); review projection cannot mutate
the wrapper; pre/post wrapper + post canonical fingerprints identical; offline margin complete
while account feasibility = UNAVAILABLE_NOT_EVALUATED; CH3 PASS never sets
`execution_readiness`; gross 10,000 / net 0 / long 5,000 / short absolute 5,000; signed short
notionals remain `-200` in review rows; zero readiness/gate/native-exec/sender/Pilot/Notion/
Discord calls (counter-raisers); no REST fallback; default native-daily + CH2 Plan-only
byte-unchanged; no output/temp on failure; no-clobber destination-race behavior.
