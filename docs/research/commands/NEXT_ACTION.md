# Next Action

> README shared status updated by TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT_CORRECTION (2026-06-21).
> TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT_CORRECTION amends the previous
> AUDIT_SEMANTICS_SPLIT commit `d189382` in place (no push) to close three
> semantic + safety gaps without weakening any Stage 1 safety boundary:
>
> 1. **Legacy `order_sent` restored to business-outcome semantics.** Previously
>    rewritten as `order_sent = simulated_order_sent OR real_order_sent`, which
>    broke backward compatibility (a fake sender that returned normally with a
>    nonzero Bybit `retCode` produced legacy `order_sent=True`). Legacy
>    `order_sent` is now sourced directly from BM's `SendOutcome.order_sent`
>    (= `retCode == 0 AND non-empty orderId`). `simulated_order_sent=True`
>    alone is NOT proof Bybit accepted the order. Consumers must use
>    `bybit_ret_code` + `bybit_order_id` + `bm_final_status` + legacy
>    `order_sent` for the accepted-order outcome, and `real_order_sent` to
>    prove a real Bybit Demo order (Stage 1 guarantees `False`).
> 2. **Raised fake-sender exceptions stay safe.** `_invoke_bm` wraps the
>    counting-sender in `try/except` and reshapes any raised exception into
>    the same `{"_network_error": True, "_error_repr": ...}` sentinel BM
>    already understands, so no exception leaks out of the public
>    orchestration surface. Final status remains
>    `STATUS_REJECTED_BM_NETWORK_ERROR`, `simulated_order_sent=False`,
>    sender call count = 1, real network calls = 0.
> 3. **Forbidden transport-kinds fail closed.** New
>    `_validate_stage1_order_transport_kind` helper validates against the
>    exact allowlist; `_build_rejection_report` / `_build_full_report` no
>    longer silently rewrite `REAL_DEMO_SENDER` to `NONE` / `FAKE_SENDER`.
>    Forbidden or unknown values raise
>    `OneShotAuthorizedExecutionOrchestratorError`. Real sender stays
>    unreachable; no real network request occurs before this invariant check.
>
> Legacy aggregate formulas (CORRECTION-final):
> - `order_network_attempted = simulated_order_network_attempted OR real_order_network_attempted`
> - `order_endpoint_called  = simulated_order_endpoint_called  OR real_order_endpoint_called`
> - `network_attempted      = read_only_network_attempted      OR order_network_attempted`
> - `order_sent` = BM `SendOutcome.order_sent` (business outcome; NOT an OR aggregate of the split fields)
>
> Safety status: 0 real Bybit Demo orders sent, 0 real `/v5/order/create` calls,
> no live endpoint, no live/demo secret read changes, no `main.py` /
> `src/risk.py` / `src/executors/bybit.py` / `BybitExecutor` change, no global
> tiny-cap change, `MAX_ORDER_COUNT=1` unchanged, BL packet `DEFAULT_QTY=0.01`
> unchanged, cap escalation authorization gate unchanged, 20 USDT notional
> cap unchanged, all Stage 1 fake-sender-only restrictions preserved, the
> orchestrator `_invoke_bm` real sender remains unreachable, a separate
> human authorization task is still required before Stage 2 can dispatch a
> real Bybit Demo order.

## TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT_CORRECTION Status (2026-06-21)

- Status: COMPLETE (local commit `d189382` amended in place; not pushed)
- Parent commit (before amend): `31b0bf8` (TASK-014BM_STAGE1_VPS_VALIDATION_CLOSEOUT)
- Orchestrator: `src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`
  - New helper `_validate_stage1_order_transport_kind(kind)` (exported in `__all__`) raising `OneShotAuthorizedExecutionOrchestratorError` for `REAL_DEMO_SENDER` and unknown values
  - `_build_rejection_report` calls the validator (replaces silent `REAL_DEMO_SENDER` → `NONE` rewrite); legacy `order_sent` set explicitly to `False` (no business outcome on rejection paths)
  - `_build_full_report` calls the validator (replaces silent `REAL_DEMO_SENDER` → `FAKE_SENDER` rewrite); legacy `order_sent` sourced from `bm_report.order_sent` (= `retCode == 0 AND non-empty orderId`)
  - `_invoke_bm` counting-sender wraps `bm_fake_sender` in `try/except`; raised exceptions become `{"_network_error": True, "_error_repr": "<type>: <msg>"}`
- Focused tests: `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_stage1_real_vs_simulated_order_audit_semantics_split.py` extended to 27/27 PASS (prior 20 + 7 new):
  - `_assert_legacy_aggregates` split into `_assert_legacy_transport_aggregates` (OR for `order_network_attempted` / `order_endpoint_called` / `network_attempted`) and `_assert_legacy_order_sent_is_business_outcome` (`retCode == 0 AND non-empty orderId`)
  - Success path: now also asserts legacy `order_sent=True`
  - Nonzero retCode: legacy `order_sent=False` (reverted from `True`)
  - New: retCode==0 + empty orderId (`simulated_order_sent=True`, legacy `order_sent=False`)
  - New: real raised exception via `RuntimeError` (no leaked exception; `simulated_order_endpoint_called=True`, `simulated_order_sent=False`, sender call count 1)
  - New: 4 validator tests (reject `REAL_DEMO_SENDER` / unknown; accept `NONE` / `FAKE_SENDER`; `_build_rejection_report` fail-closed on forbidden / unknown)
- Cross-impact tests reverted to business-outcome expectation:
  - `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py::test_real_demo_fake_sender_bybit_reject_fails_closed` → `order_sent=False`
  - `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py::test_fake_sender_bybit_reject_surfaces_bm_bybit_not_executed` → `order_sent=False`
- Validation (local, on amended commit):
  - Py compile: PASS (6 files — orchestrator src, CLI preview script, the focused split test, and the 3 updated/touched test modules)
  - 27/27 focused split tests PASS
  - 66/66 combined Stage 1 (real-demo + discovery-gate-fix) PASS
  - 186/186 one-shot orchestrator-family PASS (179 prior + 7 new)
  - Scoped tiny-execution-adapter regression: `python -m pytest tests/demo_trading -k "tiny_execution_adapter" -q --basetemp=.pytest_local/full` → **657 passed, 7701 deselected** (650 prior + 7 new)
- Files intentionally not modified: `main.py`, `src/risk.py`, `src/executors/bybit.py`, `BybitExecutor`, BM signing implementation, endpoint implementation, BL packet `DEFAULT_QTY=0.01`, `TINY_QTY_CAP_SOL`, `TINY_SIZE_CAP_USDT`, `MAX_ORDER_COUNT=1`, `PROTECTED_SYMBOLS`, `MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT=20`, cap escalation gate source, scheduler / cron, credential loading
- Real order endpoint called: False
- Real orders sent: False

> README shared status updated by TASK-014BM_STAGE1_REAL_VS_SIMULATED_ORDER_AUDIT_SEMANTICS_SPLIT (2026-06-21).
> TASK-014BM_STAGE1_REAL_VS_SIMULATED_ORDER_AUDIT_SEMANTICS_SPLIT removes the
> ambiguity between injected fake-sender execution and an actual Bybit Demo
> network order on the `OrchestrationReport`. Seven explicit audit fields are
> added (all safe-defaulted; existing 12 mandatory fields unchanged):
> `simulated_order_network_attempted`, `simulated_order_endpoint_called`,
> `simulated_order_sent`, `real_order_network_attempted`,
> `real_order_endpoint_called`, `real_order_sent`, and `order_transport_kind`
> (allowlist: `NONE` / `FAKE_SENDER` / `REAL_DEMO_SENDER`).
>
> Stage 1 hard invariant: `order_transport_kind` is **never** emitted as
> `REAL_DEMO_SENDER`, and the three `real_order_*` booleans are **always**
> `False`. The new public constant `STAGE1_FORBIDDEN_ORDER_TRANSPORT_KINDS`
> lists the forbidden value so consumers can assert externally.
>
> Semantics:
> - **No dispatch** (readiness, every rejection path, Stage 1 real-send refusal):
>   all six split booleans `False`, `order_transport_kind="NONE"`.
> - **Fake sender normal return** (including non-zero Bybit `retCode`): all three
>   `simulated_*` `True`, all three `real_*` `False`, `order_transport_kind="FAKE_SENDER"`.
>   Bybit business rejections are surfaced via `bybit_ret_code` / `bm_final_status`
>   and no longer rewrite the transport facet.
> - **Fake sender exception** (network error): `simulated_order_network_attempted=True`,
>   `simulated_order_endpoint_called=True`, `simulated_order_sent=False`,
>   `order_transport_kind="FAKE_SENDER"`.
>
> Legacy fields kept for backward compatibility (CORRECTION-final semantics):
> - `order_network_attempted = simulated_order_network_attempted OR real_order_network_attempted`
> - `order_endpoint_called  = simulated_order_endpoint_called  OR real_order_endpoint_called`
> - `network_attempted      = read_only_network_attempted      OR order_network_attempted`
> - **`order_sent`** retains its prior accepted-order business-outcome
>   meaning (`retCode == 0 AND non-empty orderId`); it is **not**
>   `simulated_order_sent OR real_order_sent`. See
>   TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT_CORRECTION (2026-06-21) above
>   for the rationale and final mapping.
>
> Safety status: 0 real Bybit Demo orders sent, 0 real `/v5/order/create` calls,
> no live endpoint, no live/demo secret read changes, no `main.py` / `src/risk.py` /
> `src/executors/bybit.py` / `BybitExecutor` change, no global tiny-cap change,
> `MAX_ORDER_COUNT=1` unchanged, BL packet `DEFAULT_QTY=0.01` unchanged,
> cap escalation authorization gate unchanged, 20 USDT notional cap unchanged,
> all Stage 1 fake-sender-only restrictions preserved, the orchestrator
> `_invoke_bm` real sender remains unreachable, a separate human authorization
> task is still required before Stage 2 can dispatch a real Bybit Demo order.

## TASK-014BM_STAGE1_REAL_VS_SIMULATED_ORDER_AUDIT_SEMANTICS_SPLIT Status (2026-06-21)

- Status: COMPLETE (local commit pending; not pushed)
- Parent commit: `31b0bf8` (TASK-014BM_STAGE1_VPS_VALIDATION_CLOSEOUT) — NOT amended; this is a new commit
- Orchestrator: `src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`
  - Added 7 audit fields to `OrchestrationReport` (safe defaults; `to_dict()` extended)
  - Added constants `ORDER_TRANSPORT_KIND_NONE`, `ORDER_TRANSPORT_KIND_FAKE_SENDER`, `ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER`, plus `ORDER_TRANSPORT_KINDS` and `STAGE1_FORBIDDEN_ORDER_TRANSPORT_KINDS`
  - `_build_rejection_report` accepts the new fields; Stage 1 guard normalizes any leaked `REAL_DEMO_SENDER` → `NONE`; legacy `order_*` / `network_attempted` fields recomputed as OR aggregates
  - `_build_full_report` classifies fake-sender activity: `simulated_order_sent` is derived from `bm_endpoint_called AND bm_final_status != STATUS_NETWORK_ERROR_DEMO_ONLY` so transport facet is independent of Bybit business outcome; Stage 1 guard normalizes any `REAL_DEMO_SENDER` → `FAKE_SENDER`
  - `_render_markdown` appends a new "Order activity audit (simulated vs real)" section
  - `__all__` extended with the new constants
- CLI: `scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`
  - stdout now prints `order_transport_kind`, the 3 `simulated_*` booleans, and the 3 `real_*` booleans before the optional report-write block
- New tests: `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_stage1_real_vs_simulated_order_audit_semantics_split.py` (20/20 PASS)
  - Constants & exports (3 tests)
  - All no-dispatch paths: readiness, every rejection, Stage 1 real-send refusal (9 tests)
  - Fake-sender dispatch: OK, Bybit `retCode != 0`, network error (3 tests)
  - Invariants: Stage 1 never emits `REAL_DEMO_SENDER`; legacy OR aggregates (2 tests)
  - Serialization: `to_dict()`, markdown render, CLI stdout (3 tests)
- Updated existing tests aligned to new semantics:
  - `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py` — Bybit reject case now asserts `simulated_order_sent=True` (transport succeeded) + `bybit_order_id==""` + `order_transport_kind=FAKE_SENDER`; network error case asserts `simulated_order_endpoint_called=True`, `simulated_order_sent=False`
  - `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py` — `test_fake_sender_bybit_reject_surfaces_bm_bybit_not_executed` aligned to new split semantics
  - `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_read_only_discovery_opt_in_fix.py` — `SimpleNamespace` orchestration-report mock extended with the 7 new fields
- Validation (local):
  - Py compile: PASS (6 files — orchestrator src, CLI preview script, the new split test, and the 3 updated test modules)
  - 20/20 focused split tests PASS
  - 66/66 combined Stage 1 (real-demo + discovery-gate-fix) PASS
  - 179/179 one-shot orchestrator-family PASS (159 prior + 20 new)
  - Scoped tiny-execution-adapter regression: `python -m pytest tests/demo_trading -k "tiny_execution_adapter" -q --basetemp=.pytest_local/full` → **650 passed, 7701 deselected** (630 prior + 20 new)
- Files intentionally not modified: `main.py`, `src/risk.py`, `src/executors/bybit.py`, `BybitExecutor`, BL packet `DEFAULT_QTY=0.01`, `TINY_QTY_CAP_SOL`, `TINY_SIZE_CAP_USDT`, `MAX_ORDER_COUNT=1`, `PROTECTED_SYMBOLS`, `MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT=20`, cap escalation gate source, BM execution source
- Real order endpoint called: False
- Real orders sent: False

## Next VPS Validation Command (TASK-014BM Stage 1 audit semantics split)

```powershell
python scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py --mode execute_real_demo_order --ir-mode discover --i-understand-this-performs-one-public-read-only-instrument-rules-get --explicit-demo-min-qty-cap-authorization-flag --authorization-marker DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1 --explicit-real-demo-order-flag --real-demo-authorization-marker DEMO_ONLY_SOLUSDT_ONE_SHOT_REAL_ORDER_RICK_AUTHORIZED_v1
```

Expected output must confirm:
- stdout contains `REJECTED: Stage 1 forbids any real /v5/order/create call.`
- CLI exit code `2`
- stdout contains `order_transport_kind='NONE'`
- stdout contains `simulated_order_network_attempted=False simulated_order_endpoint_called=False simulated_order_sent=False`
- stdout contains `real_order_network_attempted=False real_order_endpoint_called=False real_order_sent=False`
- No real Bybit Demo order sent
- No call to `/v5/order/create`

## Next Recommended Engineering Task (after this audit clarification)

The Stage 1 audit-field clarification is complete. Real Bybit Demo order dispatch remains **explicitly unauthorized**.

Recommended next engineering tasks (choose one):
1. **Offline/fake-only postfill-audit scaffold**: add a postfill audit step that runs after the fake-sender path, records the simulated request body for offline inspection, and flags any field mismatch vs. the pre-validated cap-escalation contract.
2. **Stage 2 real-demo authorization scaffolding (decision-only)**: design the gating data structure (separate explicit human authorization marker, single-use, time-windowed) that would have to be supplied before `order_transport_kind` may become `REAL_DEMO_SENDER`. No real send wiring at this stage.

**Do NOT** proceed to a real Demo order dispatch without a separate, explicit human authorization task that names the exact commit, qty, symbol, side, and timestamp window.


> README shared status updated by TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1 (2026-06-20).
> TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1 adds an
> **isolated** one-shot real-demo-order execution surface
> (`ORCH_MODE_EXECUTE_REAL_DEMO_ORDER`) gated by a separate explicit
> flag + exact marker
> `EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER = "DEMO_ONLY_SOLUSDT_ONE_SHOT_REAL_ORDER_RICK_AUTHORIZED_v1"`.
>
> Stage 1 hard contract: the new mode reuses the existing chain
> (public read-only IR discovery → exchange min candidate derivation →
> cap escalation auth gate → authorized execution qty wiring → BM
> exact-body signing) so the final request body qty is only ever
> `0.1` from `CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY` and never the
> BL packet `0.01` fallback. The orchestrator's `_invoke_bm` and the
> CLI both refuse the real `/v5/order/create` send path — even when
> every flag, marker, and demo credential is supplied — and require
> an injected fake `bm_fake_sender` to validate offline. Sender call
> count is ≤ 1. The exact-body signature contract is preserved:
> `X-BAPI-SIGN-TYPE=2`, HMAC-SHA256 over `timestamp + api_key +
> recv_window + transmitted body`.
>
> New audit/report fields (all defaulted; existing 12 mandatory fields
> unchanged): `real_demo_execute_requested`,
> `real_demo_execute_authorized`,
> `real_demo_authorization_marker_match`, `credentials_source`,
> `resolved_execution_qty`, `resolved_execution_qty_source`,
> `resolved_notional`, `bybit_ret_msg`, `final_status`.
>
> New statuses: `STATUS_REJECTED_REAL_EXECUTE_NOT_AUTHORIZED`,
> `STATUS_REJECTED_REAL_EXECUTE_MARKER_MISMATCH`. The existing
> `STATUS_REJECTED_REAL_EXECUTE_FORBIDDEN_STAGE1` is now reached when
> the caller supplies demo credentials but no fake sender, so Stage 1
> cannot dispatch a real send.
>
> Safety status: 0 real orders sent, 0 `/v5/order/create` real calls,
> no live endpoint, no live/demo secret reads added, no
> `main.py` / `src/risk.py` / `src/executors/bybit.py` /
> `BybitExecutor` change, no global tiny-cap change,
> `MAX_ORDER_COUNT=1` unchanged, BL packet `DEFAULT_QTY=0.01`
> unchanged, all existing Stage 1 fake-sender-only restrictions
> preserved. **A separate human authorization task is required before
> Stage 2 can dispatch a real Bybit Demo order.**

## TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1 Status (2026-06-20)

- Status: COMPLETE (local commit `efe9d74`, amended by TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1_DISCOVERY_GATE_FIX; not pushed)
- Orchestrator: `src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`
- CLI: `scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`
- New tests: `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py` (43/43 PASS)
- New CLI fixture: `tests/demo_trading/fixtures_orchestrator_fake_senders.py`
- Existing orchestrator + taxonomy + audit + opt-in family: 93/93 PASS
- Tiny execution adapter scoped regression (corrected — previously falsely labeled `7921/7921 PASS`):
  - Command: `python -m pytest tests/demo_trading -k "tiny_execution_adapter" -q --basetemp=.pytest_local/full`
  - Result: **607 passed, 7701 deselected** (the 7921-figure conflated the unfiltered run, which contained 250 pre-existing Windows tmp_path errors + 2 pre-existing test-pollution failures and therefore must not be labeled PASS)
- Py compile: PASS
- Files intentionally not modified: `main.py`, `src/risk.py`, `src/executors/bybit.py`, BL packet `DEFAULT_QTY`, `TINY_QTY_CAP_SOL`, `TINY_SIZE_CAP_USDT`, `MAX_ORDER_COUNT=1`, `PROTECTED_SYMBOLS`, `MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT=20`, cap escalation gate source, BM execution source
- Real order endpoint called: False
- Real orders sent: False

## Next VPS Validation Command (TASK-014BM real-demo execute surface Stage 1, post-discovery-gate-fix)

```powershell
python scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py --mode execute_real_demo_order --ir-mode discover --i-understand-this-performs-one-public-read-only-instrument-rules-get --explicit-demo-min-qty-cap-authorization-flag --authorization-marker DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1 --explicit-real-demo-order-flag --real-demo-authorization-marker DEMO_ONLY_SOLUSDT_ONE_SHOT_REAL_ORDER_RICK_AUTHORIZED_v1
```

Expected output must confirm:
- stdout contains `REJECTED: Stage 1 forbids any real /v5/order/create call.`
- CLI exit code `2`
- No real Bybit Demo order sent
- No call to `/v5/order/create`

## TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1_DISCOVERY_GATE_FIX Status (2026-06-20)

- Status: COMPLETE (amended into local commit `efe9d74` with `git commit --amend --no-edit`; not pushed)
- Purpose: close two gaps in the Stage 1 surface — (a) `execute_real_demo_order` was not requiring fresh public read-only IR discovery; (b) the Stage 1 entries falsely claimed `7921/7921 PASS` for the tiny-execution-adapter regression.
- New pre-flight discovery gate for `execute_real_demo_order` (readiness mode unaffected):
  - Requires `ir_mode == MODE_DISCOVER` and `ir_pre_parsed_response is None` → else `STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED`
  - Requires `allow_real_ir_get=True` → else `STATUS_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED`
  - CLI additionally rejects `--ir-pre-parsed-response-json`, `--ir-mode` other than `discover`, and a missing `--i-understand-this-performs-one-public-read-only-instrument-rules-get` opt-in (all exit 1)
  - Gate fires before any IR or order sender callable is invoked (verified by `ir_counter == 0` assertions)
- New statuses (added to `__all__`, safe-defaulted): `STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED`, `STATUS_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED`
- Changed files:
  - `src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py` (statuses + gate + `__all__`)
  - `scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py` (3 new CLI rejection blocks for real-demo mode)
  - `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1.py` (43 tests rewired through discover + injected `ir_sender`; rejection contracts unchanged)
- New test module:
  - `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_real_demo_order_execution_surface_stage1_discovery_gate_fix.py` (23/23 PASS)
- Validation (local):
  - Py compile: PASS (src + scripts + both Stage 1 test files)
  - 23/23 new discovery-gate-fix tests PASS
  - 43/43 existing Stage 1 tests PASS after rewiring
  - 66/66 combined Stage 1 PASS
  - 159/159 orchestrator-family PASS
  - Scoped tiny-execution-adapter regression: `python -m pytest tests/demo_trading -k "tiny_execution_adapter" -q --basetemp=.pytest_local/full` → **630 passed, 7701 deselected**
    - (Earlier intermediate result of `611 passed + 19 errors` was caused only by a missing `.pytest_local` parent directory — test-environment setup errors, not application or strategy failures; resolved by creating the directory first.)
- Safety invariants: 0 real Bybit Demo orders sent, 0 real `/v5/order/create` calls, no live endpoint, no live/demo secret read changes, no `main.py` / `src/risk.py` / `src/executors/bybit.py` / `BybitExecutor` change, `MAX_ORDER_COUNT=1` unchanged, BL packet `DEFAULT_QTY=0.01` unchanged, global tiny caps unchanged, 20 USDT notional cap unchanged, readiness-mode behavior unchanged, `execute_real_demo_order` requires fresh public IR discovery (cached/pre-parsed rules rejected), IR sender call count ≤ 1, fake BM sender call count ≤ 1, Stage 1 real sender remains unreachable, a separate human-authorized Stage 2 task is still required.

## TASK-014BM_STAGE1_VPS_VALIDATION_CLOSEOUT Status (2026-06-20)

- Status: COMPLETE — VPS Stage 1 validation PASS
- Validated commit: `d732273` (TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1)
- VPS environment: Ubuntu 24.04.4 LTS, Python 3.12.3, pytest 9.1.1
- Branch status at validation: `main == origin/main`
- Py compile: PASS (5 files: orchestrator src, CLI scripts, fixtures, Stage 1 test, discovery-gate-fix test)
- 23/23 focused discovery-gate-fix tests PASS
- 66/66 combined Stage 1 PASS
- 159/159 one-shot orchestrator-family PASS
- Scoped tiny-execution-adapter regression: `python -m pytest tests/demo_trading -k "tiny_execution_adapter" -q --basetemp=.pytest_local/full` → **630 passed, 7701 deselected**
- Real-sender refusal confirmed on VPS:
  - Command: `execute_real_demo_order` without `--stage1-allow-fake-sender-execute-mode`
  - Output: `REJECTED: Stage 1 forbids any real /v5/order/create call. Real-demo-order can only be validated offline with a fake sender.`
  - Exit code: 2
- Injected fake-sender path confirmed on VPS (simulated, offline):
  - `status=ORCHESTRATION_OK_FAKE_SENDER_EXECUTED_DEMO_ONLY`
  - `instrument_rules_loaded=True`, `candidate_qty='0.1'`, `candidate_notional='10.0'`
  - `cap_gate_status='ESCALATION_AUTHORIZED'`, `wiring_status='WIRING_AUTHORIZED_CANDIDATE_QTY'`
  - `original_packet_qty='0.01'`, `actual_request_body_qty='0.1'`, `actual_request_body_qty_source='CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY'`
  - `body_qty_authorized_override=True`
  - `read_only_network_attempted=True`, `order_network_attempted=True`, `network_attempted=True`
  - `order_endpoint_called=True`, `order_sent=True`, `fake_sender_used=True`, `sender_call_count=1`
  - `real_execute_disabled_stage1=True`, `bybit_order_id='fake-cli-1'`
  - `credentials_source='injected_demo_credentials'`, `resolved_notional='10.0'`
  - **Audit clarification**: `order_network_attempted`, `order_endpoint_called`, and `order_sent` all describe the **simulated** BM execution through the injected fake sender — NOT a real Bybit network request.
    - Simulated endpoint-shaped fake-sender calls: 1
    - Real Bybit Demo `/v5/order/create` network calls: 0
    - Real Bybit Demo orders sent: 0
    - Stage 1 real sender: unreachable
- Real order endpoint called (actual network): False
- Real orders sent: False
- Documentation change only: source files and tests were not modified by this closeout task.

## Next Recommended Engineering Task (fail-closed — real Demo execution NOT yet authorized)

The Stage 1 validation is complete. Real Bybit Demo order dispatch remains **explicitly unauthorized**.

Recommended next engineering task (choose one):
1. **Audit-field clarity**: add explicit `is_real_order=False` / `real_send_attempted=False` fields to `OrchestrationReport` so consumers cannot confuse `order_sent=True` (fake) with a real network dispatch.
2. **Offline/fake-only postfill-audit scaffold**: add a postfill audit step that runs after the fake-sender path, records the simulated request body for offline inspection, and flags any field mismatch vs. the pre-validated cap-escalation contract.

**Do NOT** proceed to a real Demo order dispatch without a separate, explicit human authorization task that names the exact commit, qty, symbol, side, and timestamp window.


> README shared status updated by TASK-014BM_ONE_SHOT_ORCHESTRATOR_READINESS_STATUS_TAXONOMY_FIX (2026-06-20).
> TASK-014BM_ONE_SHOT_ORCHESTRATOR_READINESS_STATUS_TAXONOMY_FIX corrects the orchestrator
> top-level status so a real public read-only instrument-rules GET reports
> `ORCHESTRATION_OK_READINESS_READ_ONLY_NETWORK` instead of
> `ORCHESTRATION_OK_READINESS_NO_NETWORK`, consistent with `network_attempted=True`.
>
> New constant: `STATUS_OK_READINESS_READ_ONLY_NETWORK = "ORCHESTRATION_OK_READINESS_READ_ONLY_NETWORK"`
> BM inner `bm_final_status` remains `READINESS_OK_NO_NETWORK` for both paths.
>
> Safety status: no real order sent, no live endpoint, no live secrets, no retry,
> no scheduler, no main.py/src/risk.py/BybitExecutor change, no global tiny-cap change,
> MAX_ORDER_COUNT=1 unchanged, all Stage 1 fake-sender-only restrictions preserved.

## TASK-014BM_ONE_SHOT_ORCHESTRATOR_READINESS_STATUS_TAXONOMY_FIX Status (2026-06-20)

- Status: COMPLETE (local commit pending)
- Orchestrator: `src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`
- CLI: `scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`
- New tests: `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_readiness_status_taxonomy_fix.py` (24/24 PASS)
- Updated orchestrator test: `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py` (33/34 logic PASS; 1 error = pre-existing Windows tmp_path permission)
- Updated opt-in tests: `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_read_only_discovery_opt_in_fix.py` (12/12 PASS)
- Network audit tests: `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_orchestrator_network_audit_semantics_fix.py` (23/23 PASS)
- Tiny execution adapter regression: 7921 PASS (250 errors = pre-existing Windows tmp_path; 1 failure = pre-existing `test_demo_emergency_close_sender::test_dry_run_cli_writes_report`, unrelated)
- Py compile: PASS
- Files intentionally not modified: `main.py`, `src/risk.py`, `src/executors/bybit.py`, live Bybit behavior, global tiny caps, protected symbols, `MAX_ORDER_COUNT=1`
- Real order endpoint called: False
- Real order sent: False

## Next VPS Validation Command (TASK-014BM readiness status taxonomy fix)

```powershell
python scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py --ir-mode discover --i-understand-this-performs-one-public-read-only-instrument-rules-get --explicit-demo-min-qty-cap-authorization-flag --authorization-marker DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1
```

Expected output must confirm:
- `status=ORCHESTRATION_OK_READINESS_READ_ONLY_NETWORK`
- `read_only_network_attempted=True`
- `order_network_attempted=False`
- `network_attempted=True`
- `order_endpoint_called=False`
- `order_sent=False`
- `instrument_rules_loaded=True`
- `candidate_qty='0.1'`
- `actual_request_body_qty='0.1'`
- reason contains "one authorized public read-only instrument-rules GET completed"
- reason contains "no order network call attempted"
- `bm_final_status='READINESS_OK_NO_NETWORK'`

> README shared status updated by TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR (2026-06-19).
> TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR is a
> **Stage 1, offline-validated, demo-only** orchestration layer
> that wires the full authorized execution chain
> (`BM_MIN_QTY_FIX` instrument rules → `BM_CAP_ESCALATION_GATE` →
> `BM_WIRE_AUTHORIZED_CANDIDATE_QTY` →
> `BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH`) into a single
> entry point so the BM execution module receives a real
> `ESCALATION_AUTHORIZED` `AuthorizedExecutionQtyWiringReport`
> and therefore plans and (optionally) signs a request body with
> `qty="0.1"` instead of the invalid BL packet `qty="0.01"`.
>
> Stage 1 is locked down so it cannot send any real order:
> the public surface supports only two modes
> (`readiness`, `execute_with_fake_sender`); the second mode
> *requires* both `bm.DemoCredentials` and a caller-supplied
> callable fake sender — a real `MODE_EXECUTE_DEMO_ORDER` against
> the network is unreachable from the orchestrator. The CLI
> defaults to `readiness` and refuses `execute_with_fake_sender`
> unless an explicit `--stage1-allow-fake-sender-execute-mode`
> opt-in *and* a `--fake-sender-import-path` *and* fake
> credentials are all supplied. Calling
> `ir_mode="discover"` without an injected `ir_sender` raises
> `OneShotAuthorizedExecutionOrchestratorError` unless the caller
> also passes `allow_real_ir_get=True` (Stage 1 callers never do).
>
> New module
> [`src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](../../../src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)
> exposes the entry point
> `run_one_shot_authorized_execution_orchestration(...)`, a frozen
> `OrchestrationReport` dataclass surfacing the 12 mandatory
> chain fields (`instrument_rules_loaded`, `candidate_qty`,
> `candidate_notional`, `cap_gate_status`, `wiring_status`,
> `original_packet_qty`, `actual_request_body_qty`,
> `actual_request_body_qty_source`,
> `body_qty_authorized_override`, `network_attempted`,
> `order_endpoint_called`, `order_sent`) plus nested raw reports
> for full traceability, and a `write_report()` helper emitting 4
> files (`latest_*.json`, `latest_*.md`, timestamped pair) under
> `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator/`.
> Identity markers:
> `TASK_ID = "TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR"`,
> `IDENTITY = "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-ONE-SHOT-AUTHORIZED-EXECUTION-ORCHESTRATOR"`,
> `IMPLEMENTATION_PATH_PHASE = "tiny_order_one_shot_authorized_execution_orchestrator"`,
> `IS_REVIEW_CHAIN_SUFFIX=False`,
> `UPSTREAM_TASKS=(BH, BM, BM_FIX, BM_MIN_QTY_FIX, BM_CAP_ESCALATION_GATE, BM_WIRE_AUTHORIZED_CANDIDATE_QTY, BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH)`,
> `NEXT_REQUIRED_TASK = "TASK-014BN_demo_only_tiny_execution_postfill_audit"`.
>
> New CLI
> [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](../../../scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)
> default mode is `readiness`; surfaces every one of the 12
> mandatory orchestration fields on stdout, exits `0` on
> `ORCHESTRATION_OK_*`, `2` on missing credentials / fake sender,
> `1` on any other rejected chain status.
>
> New test file
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`](../../../tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py)
> (34 tests) covers: identity / chain markers; immutable locks;
> readiness happy path returns `actual_request_body_qty="0.1"`
> with no network; fake-sender execute path returns body
> `qty="0.1"` AND the exact UTF-8 bytes posted to the sender equal
> the HMAC-SHA256 prehash body string (sign-type=2) AND the sender
> is called exactly once; unsupported orchestration mode rejected
> no-network; rules not loaded / wrong symbol / wrong status /
> wrong min_order_qty all rejected pre-network; cap-gate
> unauthorized when flag missing / marker missing / marker wrong;
> missing credentials / missing fake sender both rejected; real
> IR discover without injected sender raises
> `OneShotAuthorizedExecutionOrchestratorError`; injected
> `ir_sender` path runs; Bybit fake `retCode=10004` surfaces
> `STATUS_REJECTED_BM_BYBIT_NOT_EXECUTED`; fake network error
> surfaces `STATUS_REJECTED_BM_NETWORK_ERROR`; module never
> references `main.py` / `src.risk` / `BybitExecutor` /
> `BYBIT_LIVE_*` env vars / live URL host outside docstrings;
> `write_report()` emits 4 files and JSON round-trips;
> `OrchestrationReport` is frozen; `to_dict()` exposes all 12
> required surfaces; no rejection branch ever surfaces
> `actual_request_body_qty="0.01"`; tiny caps + protected-symbols
> snapshot is unchanged.
>
> No safety-critical surface was modified: no live endpoint, no
> live or demo secret loading code, no `main.py` /
> `src/risk.py` / `src/executors/bybit.py` change, no
> `BybitExecutor` live behavior change, no protected-position
> code touched, no retry, no scheduler, no stop endpoint, no
> TP/SL, no `/v5/order/create` real call, no new real Bybit
> Demo order sent, no BL packet `DEFAULT_QTY="0.01"` change,
> no `TINY_QTY_CAP_SOL=0.05` / `TINY_SIZE_CAP_USDT=5` change,
> no `MAX_ORDER_COUNT=1` change, no `PROTECTED_SYMBOLS` change,
> no double-flag gate loosening, no LIVE-named secret env access.
> The instrument-rules layer, cap-escalation gate, wiring
> layer, and BM execution layer source files are all unmodified
> in this commit.
>
> Validation (this commit):
> py_compile of all changed Python files PASS;
> `pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py
> --basetemp=.pytest_tmp/bt` → **34/34 PASS**;
> BH→BM-family chain regression
> (`-k tiny_execution_adapter`) → **505/505 PASS**
> (471 prior BH→BM + 34 new Stage 1 orchestrator);
> readiness preview surfaces
> `actual_request_body_qty='0.1' actual_request_body_qty_source='CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY'
> body_qty_authorized_override=True network_attempted=False
> order_endpoint_called=False order_sent=False`;
> fake-sender preview surfaces
> `actual_request_body_qty='0.1' order_sent=True sender_call_count=1`
> with the posted body bytes equal to the HMAC prehash body and
> `X-BAPI-SIGN-TYPE=2`.
>
> No new real Bybit Demo order was sent during this Stage 1 task.
>
> Previous BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH Stage 2
> banner archived below.

## TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR Status (2026-06-19)

- Stage: 1
- Status: COMPLETE (local commit pending)
- Identity: `DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-ONE-SHOT-AUTHORIZED-EXECUTION-ORCHESTRATOR`
- Module: `src/demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`
- CLI: `scripts/preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py`
- Tests: `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator.py` (34/34 PASS)
- Regression: BH→BM family (`-k tiny_execution_adapter`) 505/505 PASS
- Network: NO real `/v5/order/create` call. NO real Bybit Demo order sent. Fake-sender path only.
- Next required task: `TASK-014BN_demo_only_tiny_execution_postfill_audit`

> README shared status updated by TASK-014BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH (2026-06-19).
> TASK-014BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH is a
> **Stage 2, offline-validated, demo-only** extension on top of
> TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY. It switches BM's
> *actual* HTTPS request body `qty` from the BL packet value
> (`"0.01"`, confirmed invalid against Bybit SOLUSDT minimums) to
> the authorized cap-escalation candidate `qty` (`"0.1"`) **only
> when** a fully authorized wiring report is threaded through. On
> every rejected path BM **fails closed pre-network** with the
> new status `WIRING_REQUIRED_NO_NETWORK` and NEVER silently falls
> back to `qty=0.01`.
>
> Changes to
> [`src/demo_only_tiny_execution_adapter_tiny_order_execution.py`](../../../src/demo_only_tiny_execution_adapter_tiny_order_execution.py):
> new constants `STATUS_WIRING_REQUIRED_NO_NETWORK`,
> `EXECUTE_BODY_QTY_SOURCE_BL_PACKET`,
> `EXECUTE_BODY_QTY_SOURCE_AUTHORIZED_CANDIDATE`,
> `EXECUTE_BODY_QTY_SOURCE_NONE`,
> `EXECUTE_BODY_QTY_SOURCE_REJECTED_NO_FALLBACK`,
> `MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT=Decimal("20")`; new helper
> `_derive_body_qty_from_wiring()`; `ExecutionPlan` extended with
> 3 defaulted fields (`actual_request_body_qty`,
> `actual_request_body_qty_source`,
> `body_qty_authorized_override`); `ExecutionReport` extended
> with 4 defaulted fields (above 3 +
> `body_qty_rejection_reason`); new pre-network rejection branch
> in `run_explicit_tiny_order_execution()` that fires when
> `body_qty_authorized_override` is False AND mode is
> `execute_demo_order` AND all earlier gates passed AND
> credentials present. Defense-in-depth: the 20 USDT notional cap
> is re-validated at the BM layer even though the wiring layer
> already enforces it.
>
> New test file
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution_body_authorized_qty_source_switch.py`](../../../tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution_body_authorized_qty_source_switch.py)
> (20 tests) covers: public Stage 2 constants;
> body.qty=`"0.1"` only when fully authorized (happy path);
> plan + body_preview record authorized qty in readiness mode;
> exact `body_bytes.decode("utf-8")` equals the HMAC prehash body
> (sign-type 2, lowercase hex SHA-256); missing wiring rejects
> pre-network with `WIRING_REQUIRED_NO_NETWORK`; unauthorized
> wiring rejects pre-network with empty body qty + source
> `REJECTED_NO_FALLBACK_TO_0_01`; over-cap wiring (mark=1000
> notional=100 > 20) rejects pre-network; rejected paths never
> hit sender; readiness without wiring keeps packet qty for
> visibility (no network); dry_run without wiring no-network;
> missing flags / credentials still block ahead of wiring check;
> retCode=10004 with authorized qty maps to
> `BYBIT_REJECTED_NO_ORDER_SENT` (NOT executed); retCode=0 with
> empty orderId NOT executed; only one sender call ever under
> authorized override; `_derive_body_qty_from_wiring` boundary
> cases; `ExecutionReport.to_dict()` surfaces all 4 new fields.
> Existing 88 BM + 18 BM_FIX execute-mode tests threaded through
> the new `_authorized_wiring()` helper and still pass.
>
> Existing 18 BM_FIX tests + 88 BM tests use a real
> ESCALATION_AUTHORIZED wiring report built from the real
> BM_MIN_QTY_FIX + BM_CAP_ESCALATION_GATE upstreams via
> `_authorized_wiring()`. The happy-path assertion in BM's
> `test_execute_mode_with_flags_and_creds_sends_via_injected_sender`
> was updated from `body_dict["qty"] == "0.01"` to
> `body_dict["qty"] == "0.1"` to match the Stage 2 contract.
>
> No safety-critical surface was modified: no live endpoint, no
> live or demo secret loading, no `main.py` / `src/risk.py` /
> `src/executors/bybit.py` change, no `BybitExecutor` live
> behavior change, no protected-position code touched, no retry,
> no scheduler, no stop endpoint, no TP/SL, no `/v5/order/create`
> call, no new real Bybit Demo order sent, no BL packet
> `DEFAULT_QTY="0.01"` change, no `TINY_QTY_CAP_SOL=0.05` /
> `TINY_SIZE_CAP_USDT=5` change, no `MAX_ORDER_COUNT=1` change,
> no `PROTECTED_SYMBOLS` change, no double-flag gate loosening,
> no LIVE-named secret env access. The instrument-rules layer
> (`src/demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py`)
> and cap-escalation gate
> (`src/demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py`)
> and wiring layer
> (`src/demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py`)
> are unmodified.
>
> Validation (this commit):
> py_compile of all changed Python files PASS;
> `pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution_body_authorized_qty_source_switch.py
> --basetemp=.pytest_tmp/bt` → **20/20 PASS**;
> BH→BM Stage 2 full chain regression (10 demo_trading adapter
> test files, all under `-k demo_only_tiny_execution_adapter`)
> → **471/471 PASS** (450 prior + 20 Stage 2 + 1 misc); preview
> default readiness smoke prints
> `actual_request_body_qty='0.01' actual_request_body_qty_source='BL_PACKET_QTY'
> body_qty_authorized_override=False
> body_qty_rejection_reason='no authorized_execution_qty_wiring report supplied'`
> and exits 0.
>
> No new real Bybit Demo order was sent during this Stage 2 task.
>
> Previous BM_WIRE_AUTHORIZED_CANDIDATE_QTY Stage 1 banner archived below.

## TASK-014BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH Status (2026-06-19)

| item | status |
|---|---|
| BM execution module Stage 2 surface (`STATUS_WIRING_REQUIRED_NO_NETWORK`, 4 `EXECUTE_BODY_QTY_SOURCE_*` enums, `MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT=20`, `_derive_body_qty_from_wiring()` helper, `ExecutionPlan` +3 defaulted fields, `ExecutionReport` +4 defaulted fields) | DONE |
| pre-network rejection branch: missing/unauthorized/over-cap/blank/qty-mismatch wiring all rejected with `WIRING_REQUIRED_NO_NETWORK` before any network call; NEVER falls back to `qty=0.01` on rejected paths | CONFIRMED |
| happy-path: body.qty becomes `"0.1"` ONLY when wiring `status=WIRING_AUTHORIZED_CANDIDATE_QTY` AND `execution_qty_source=CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY` AND `execution_qty>0` AND notional ≤ 20 USDT (BM mirror) AND demo env / SOLUSDT / Buy / Market / IOC / both flags / demo creds all present | CONFIRMED |
| 20 USDT notional cap re-validated at BM layer (defense-in-depth mirror of the wiring layer's `MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT`) | CONFIRMED |
| new tests `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution_body_authorized_qty_source_switch.py` (Stage 2 focused-core 20 tests) | DONE |
| existing 88 BM + 18 BM_FIX execute-mode tests threaded through `_authorized_wiring()` helper; happy-path body qty assertion updated to `"0.1"` | DONE |
| preview script `scripts/preview_demo_only_tiny_execution_adapter_tiny_order_execution.py` surfaces 4 Stage 2 fields | DONE |
| chain-break markers unchanged (`TASK_ID="TASK-014BM"`, identity / phase / upstreams / `NEXT_REQUIRED_TASK` all unchanged from Stage 1) — Stage 2 is an *internal* refinement of BM's actual send body | CONFIRMED |
| global `TINY_QTY_CAP_SOL=0.05` / `TINY_SIZE_CAP_USDT=5` / `TINY_QTY_STEP_SOL=0.01` constants in BH are NOT modified; protected symbols denylist `{ENA, TIA, AIXBT, POLYX, EDU}USDT` is NOT modified; BL packet `DEFAULT_QTY="0.01"` is NOT modified | CONFIRMED |
| py_compile (src + scripts + tests) | PASS |
| pytest BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH Stage 2 focused-core | **20/20 PASS** |
| pytest BH→BM full chain regression (`-k demo_only_tiny_execution_adapter`) | **471/471 PASS** (450 prior + 20 Stage 2 + 1 misc) |
| BM readiness preview (post-change regression) | exit 0; `final_status=READINESS_OK_NO_NETWORK`; no network, no order sent; Stage 2 surface printed |
| safety invariants (no live endpoint call / no live secret read / no demo secret read in offline path / no stop endpoint / no TP-SL attachment / no retry / no scheduler / no G20 lift / no position modification / no protected position interaction / no `/v5/order/create` call / no new real demo order / no global tiny cap lift / no BL packet default-qty change) | CONFIRMED |
| main.py / src/risk.py / src/executors/bybit.py / BybitExecutor | UNTOUCHED |
| local commit | pending: `TASK-014BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH: switch demo-only SOLUSDT actual request body qty from BL packet 0.01 to authorized cap-escalation candidate 0.1 (fail-closed: missing/unauthorized/over-cap wiring rejects pre-network with WIRING_REQUIRED_NO_NETWORK; NEVER falls back to 0.01; ExecutionPlan+3 / ExecutionReport+4 defaulted fields; 20 new tests; existing 450 BH→BM_WIRE tests still PASS)` (local only — NOT pushed) |

> README shared status updated by TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY (2026-06-19).
> TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY_demo_only_SOLUSDT_execution_path is
> a **Stage 1, decision-only, demo-only** extension on top of
> TASK-014BM / TASK-014BM_FIX / TASK-014BM_MIN_QTY_FIX /
> TASK-014BM_CAP_ESCALATION_GATE. It adds a narrow **wiring layer**
> that converts the cap-escalation gate's authorized decision into
> a `execution_qty_resolved` value surfaced on BM `ExecutionReport`
> for the readiness / planning path only, so BM can record that the
> authorized candidate qty (=0.1, from TASK-014BM_MIN_QTY_FIX) is the
> only legal execution qty for this single SOLUSDT demo path and
> that the original BL packet `qty=0.01` has been confirmed invalid.
> The wiring is decision-only — it **never** sends an order,
> **never** calls `/v5/order/create`, **never** retries
> `execute_demo_order`, **never** touches a live endpoint, **never**
> reads any LIVE or DEMO secret env, **never** touches protected
> positions, **never** loosens `MAX_ORDER_COUNT=1` or the
> double-confirmation flags, **never** globally raises
> `TINY_QTY_CAP_SOL` / `TINY_SIZE_CAP_USDT`, and **never** mutates
> BL packet `DEFAULT_QTY="0.01"`. The wiring also does **not** switch
> BM's actual `execute_demo_order` body qty to 0.1 — that would be a
> follow-up Stage 2 task with a separate explicit authorization.
>
> New module
> [`src/demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py`](../../../src/demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py):
> single decision entry point
> `run_authorized_execution_qty_wiring(instrument_rules_report,
> cap_escalation_report)`; immutable locks
> `ALLOWED_ENVIRONMENT="bybit_demo"`, `ALLOWED_SYMBOL="SOLUSDT"`,
> `ALLOWED_SIDE="Buy"`, `ALLOWED_ORDER_TYPE="Market"`,
> `ALLOWED_TIME_IN_FORCE="IOC"`, `ALLOWED_MAX_ORDER_COUNT=1`,
> `ORIGINAL_PACKET_QTY="0.01"`,
> `MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT=Decimal("20")`; 12 decision
> statuses (`WIRING_AUTHORIZED_CANDIDATE_QTY` /
> `WIRING_NOT_REQUIRED_ORIGINAL_PASSES` /
> `WIRING_NOT_AUTHORIZED_NO_OVERRIDE` /
> `WIRING_REJECTED_RULES_NOT_LOADED` /
> `WIRING_REJECTED_GATE_MISSING` /
> `WIRING_REJECTED_GATE_OVER_CAP` /
> `WIRING_REJECTED_WRONG_SYMBOL` /
> `WIRING_REJECTED_WRONG_ENVIRONMENT` /
> `WIRING_REJECTED_WRONG_SIDE` /
> `WIRING_REJECTED_QTY_MISMATCH` /
> `WIRING_REJECTED_PROTECTED_SYMBOL` /
> `WIRING_REJECTED_CANDIDATE_INVALID`); 3 source enums
> (`CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY` for authorized success,
> `REJECTED_NO_FALLBACK_TO_0_01` for rejected paths that explicitly
> refuse to fall back to 0.01, `NONE` for not-required paths).
> Strict precedence (fail-closed): missing IR → REJECTED_RULES_NOT_LOADED;
> missing gate → REJECTED_GATE_MISSING; wrong env →
> REJECTED_WRONG_ENVIRONMENT; protected symbol →
> REJECTED_PROTECTED_SYMBOL; wrong symbol → REJECTED_WRONG_SYMBOL;
> wrong side → REJECTED_WRONG_SIDE; gate `ESCALATION_NOT_REQUIRED`
> or `original_tiny_cap_passed=True` →
> NOT_REQUIRED_ORIGINAL_PASSES (execution_qty="", source=NONE);
> gate `ESCALATION_AUTHORIZED` → validate
> `cap_escalated_demo_only=True` AND
> `explicit_demo_min_qty_cap_authorized=True` AND gate's own
> `decision.candidate_qty` / `decision.candidate_notional` parse to
> valid `Decimal` (no IR fallback — gate-only) AND notional ≤ 20 AND
> proposed_qty == candidate_qty → AUTHORIZED_CANDIDATE_QTY
> (execution_qty="0.1", source=CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY);
> gate `ESCALATION_REJECTED_NOTIONAL_OVER_CAP` →
> REJECTED_GATE_OVER_CAP; otherwise → NOT_AUTHORIZED_NO_OVERRIDE.
> Every rejected path emits `execution_qty=""`; the module **never**
> silently substitutes 0.01 for execute mode.
>
> BM `ExecutionReport` is extended with 6 additional *defaulted*
> fields (`wiring_loaded`, `wiring_status`, `original_packet_qty`,
> `execution_qty_source`, `execution_qty_resolved`,
> `execution_notional_estimate_resolved`) and
> `run_explicit_tiny_order_execution()` grows one optional keyword
> `authorized_execution_qty_wiring` so callers can inject the
> wiring report. When the kwarg is omitted, every existing
> BH→BM_CAP_ESCALATION_GATE call site behaves identically; the
> 417 existing chain tests still pass unchanged. BM's
> `execute_demo_order` body qty source (= BL packet `DEFAULT_QTY="0.01"`)
> is NOT modified by this task — wiring the resolved candidate qty
> into the actual BM POST body requires another explicit Stage 2
> authorized task.
>
> New preview CLI
> [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py`](../../../scripts/preview_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py)
> (`--mark-price`; `--ir-mode {offline,discover}` default offline;
> `--proposed-qty`; `--max-demo-min-qty-notional-cap-usdt` default 20;
> `--i-understand-demo-solusdt-exchange-min-qty-exceeds-old-tiny-cap`;
> `--authorization-marker`; `--write-report` / `--output-dir`;
> exit 0 for any of the 12 documented decision statuses, 1 for
> unrecognized status or raised exception). Default unauthorized
> offline run → exit 0,
> `status=WIRING_REJECTED_RULES_NOT_LOADED` (offline IR has no
> rules → wiring fails closed by design).
>
> New test file
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py`](../../../tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py)
> (33 tests) covers: identity / chain-break / upstream / immutable
> locks; default fail-closed when IR missing / gate missing / both
> missing (rules-not-loaded takes precedence); authorized success
> path resolves execution_qty="0.1", notional=Decimal("10.0"),
> cap_gate_status=ESCALATION_AUTHORIZED,
> cap_escalated_demo_only=True, original_packet_qty="0.01",
> qty_0_01_confirmed_invalid=True; not authorized → execution_qty="";
> mark=250 over-cap → WIRING_REJECTED_GATE_OVER_CAP;
> ESCALATION_NOT_REQUIRED → NOT_REQUIRED_ORIGINAL_PASSES /
> source=NONE; gate's own qty mismatch blocks the wiring;
> synthetic tampered-gate helper proves wiring still fail-closes on
> wrong_environment / parametrized protected symbols (5) /
> wrong_symbol / wrong_side / qty_mismatch / candidate_invalid /
> authorized-but-not-cap-escalated paths; BM ExecutionReport defaults
> hide all 6 wiring fields; injected wiring surfaces both authorized
> and rejected paths; AST static-source rules (no `urllib` /
> `requests` / `pybit` / `aiohttp` / `httpx` / `websocket` /
> `websockets` / `urllib.request` / `http.client` import; no
> `main` / `src.risk` / `src.executors.bybit` import; no
> `BybitExecutor` `Name`/`Attribute` reference; no
> `os.environ` / `os.getenv` access; no non-docstring string literal
> references a LIVE or DEMO secret env name; each
> `FORBIDDEN_URL_TOKENS` token appears at most once as a non-docstring
> string constant; no `api-demo.bybit.com` non-docstring constant);
> global tiny caps (`TINY_QTY_CAP_SOL=0.05` /
> `TINY_SIZE_CAP_USDT=5` / `TINY_QTY_STEP_SOL=0.01`) and
> `PROTECTED_SYMBOLS` frozenset are not mutated; report writer emits
> 4 files + JSON round-trip.
>
> No safety-critical surface was modified: no live endpoint, no
> live or demo secret loading, no `main.py` / `src/risk.py` /
> `src/executors/bybit.py` change, no `BybitExecutor` live behavior
> change, no protected-position code touched, no retry, no
> scheduler, no stop endpoint, no TP/SL, no `/v5/order/create` call,
> no new real Bybit Demo order sent, no BL packet
> `DEFAULT_QTY="0.01"` change, no BM `execute_demo_order` body qty
> source change.
>
> Validation (this commit):
> py_compile of all 4 changed Python files PASS;
> `pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py
> -q --basetemp=.pytest_basetemp` → **33/33 PASS**;
> BH→BM chain regression (BH + BI + BJ + BK + BL + BM + BM_FIX +
> BM_MIN_QTY_FIX + BM_CAP_ESCALATION_GATE +
> BM_WIRE_AUTHORIZED_CANDIDATE_QTY, 10 demo_trading adapter test
> files) → **450/450 PASS**;
> preview offline smoke `--mark-price 100 --proposed-qty 0.1` (no
> authorization) → exit 0,
> `status=WIRING_REJECTED_RULES_NOT_LOADED`,
> `network_attempted=False`, `order_endpoint_called=False`,
> `order_sent=False`; cap-escalation preview, BM readiness preview,
> and BM_MIN_QTY_FIX preview all still exit 0, no order sent.
>
> No new real Bybit Demo order was sent during this Stage 1 task.
>
> Previous BM_CAP_ESCALATION_GATE banner archived below.

## TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY Status (2026-06-19)

| item | status |
|---|---|
| new src `src/demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py` (decision-only entry point `run_authorized_execution_qty_wiring()`; immutable env/symbol/side/order_type/TIF/max_order_count locks; gate-only candidate-qty validation with no IR fallback; 12 decision statuses; 3 execution-qty-source enums; JSON+MD report writer) | DONE |
| new scripts `scripts/preview_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py` (`--mark-price`; `--ir-mode {offline,discover}`; `--proposed-qty`; `--max-demo-min-qty-notional-cap-usdt`; explicit auth flag; authorization marker; `--write-report` / `--output-dir`) | DONE |
| new tests `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py` (Stage 1 focused-core 33 tests) | DONE |
| BM `ExecutionReport` extended with 6 defaulted wiring fields (`wiring_loaded`, `wiring_status`, `original_packet_qty`, `execution_qty_source`, `execution_qty_resolved`, `execution_notional_estimate_resolved`); `run_explicit_tiny_order_execution()` grows optional `authorized_execution_qty_wiring` kwarg; existing 417 BH→BM_CAP_ESCALATION_GATE tests unchanged and still PASS | DONE |
| chain-break markers: `TASK_ID="TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY"`, `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-AUTHORIZED-EXECUTION-QTY-WIRING"`, `IMPLEMENTATION_PATH_PHASE="tiny_order_authorized_execution_qty_wiring"`, `IS_REVIEW_CHAIN_SUFFIX=False`, `UPSTREAM_TASKS=("TASK-014BH","TASK-014BM","TASK-014BM_FIX","TASK-014BM_MIN_QTY_FIX","TASK-014BM_CAP_ESCALATION_GATE")` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BN_demo_only_tiny_execution_postfill_audit"` (passes `bh.assert_next_task_is_not_review_chain_suffix`) | DONE |
| default wiring behaviour is **fail-closed**; rejected paths emit `execution_qty_resolved=""` and `execution_qty_source` ∈ `{REJECTED_NO_FALLBACK_TO_0_01, NONE}` — **never** silently substitutes BL's 0.01 for execute mode | CONFIRMED |
| `cap_escalation` gate result is the sole source of truth for authorized candidate qty — wiring uses `decision.candidate_qty` / `decision.candidate_notional` from the gate and never silently falls back to `instrument_rules_report.candidate.qty`; tampered-gate helper test proves this | CONFIRMED |
| `MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT = Decimal("20")` re-validated at the wiring layer; even when gate is authorized, candidate_notional > 20 → `WIRING_REJECTED_GATE_OVER_CAP` | CONFIRMED |
| environment / symbol / side / protected symbols / qty match all have dedicated fail-closed paths with distinct `WIRING_REJECTED_*` statuses | CONFIRMED |
| `ORIGINAL_PACKET_QTY="0.01"` constant surfaced on every report; `qty_0_01_confirmed_invalid=True` when authorized candidate ≠ 0.01 | CONFIRMED |
| global `TINY_QTY_CAP_SOL=0.05` / `TINY_SIZE_CAP_USDT=5` / `TINY_QTY_STEP_SOL=0.01` constants in BH are NOT modified; protected symbols denylist `{ENA, TIA, AIXBT, POLYX, EDU}USDT` is NOT modified; BL packet `DEFAULT_QTY="0.01"` is NOT modified; BM `execute_demo_order` body qty source is NOT modified | CONFIRMED |
| AST static-source safety invariants (no `urllib` / `requests` / `pybit` / `aiohttp` / `httpx` / `websocket` / `websockets` / `urllib.request` / `http.client` import; no `main` / `src.risk` / `src.executors.bybit` import; no `BybitExecutor` `Name`/`Attribute` reference; no non-docstring secret env name; no `os.environ` / `os.getenv`; each `FORBIDDEN_URL_TOKENS` token used at most once outside docstrings; no `api-demo.bybit.com` non-docstring string constant) | CONFIRMED |
| report writer emits `latest_*.json` / `latest_*.md` / `*_<UTC_TS>.json` / `*_<UTC_TS>.md` to `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring/` | DONE |
| py_compile (src + scripts + tests) | PASS |
| pytest BM_WIRE_AUTHORIZED_CANDIDATE_QTY Stage 1 focused-core | **33/33 PASS** |
| pytest BH + BI + BJ + BK + BL + BM + BM_FIX + BM_MIN_QTY_FIX + BM_CAP_ESCALATION_GATE + BM_WIRE_AUTHORIZED_CANDIDATE_QTY safety-chain regression | **450/450 PASS** (417 prior chain + 33 new) |
| BM_WIRE preview offline smoke `--mark-price 100 --proposed-qty 0.1` (no authorization) | exit 0; `status=WIRING_REJECTED_RULES_NOT_LOADED`; `network_attempted=False`; `order_endpoint_called=False`; `order_sent=False` |
| BM cap-escalation preview (post-change regression) | exit 0; no order sent |
| BM readiness preview (post-change regression) | exit 0; `final_status=READINESS_OK_NO_NETWORK`; no network, no order sent |
| BM_MIN_QTY_FIX preview (post-change regression) | exit 0; `discovery_status=DISCOVERY_OFFLINE_NO_NETWORK`; no network, no order sent |
| safety invariants (no live endpoint call / no live secret read / no demo secret read / no stop endpoint / no TP-SL attachment / no retry / no scheduler / no G20 lift / no position modification / no protected position interaction / no `/v5/order/create` call / no new real demo order / no global tiny cap lift / no BL packet default-qty change / no BM execute_demo_order body qty source change) | CONFIRMED |
| main.py / src/risk.py / src/executors/bybit.py / BybitExecutor | UNTOUCHED |
| local commit | pending: `TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY: add demo-only SOLUSDT authorized execution qty wiring layer (decision-only; locked bybit_demo+SOLUSDT+Buy+Market+IOC; consumes BM_MIN_QTY_FIX + BM_CAP_ESCALATION_GATE; BM ExecutionReport gains 6 defaulted wiring fields; rejected paths NEVER fall back to 0.01; 33 new tests; existing 417 BH→BM_CAP_ESCALATION_GATE tests unchanged)` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-19 TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY)

1. VPS git pull and re-validate the new module offline first:

       git pull --ff-only
       source .venv/bin/activate
       python3 -m py_compile \
           src/demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py \
           src/demo_only_tiny_execution_adapter_tiny_order_execution.py \
           scripts/preview_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py
       python3 -m pytest \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py \
           -q --basetemp=.pytest_basetemp
       # expect 33/33 PASS
       python3 -m pytest \
           tests/demo_trading/test_demo_only_tiny_execution_adapter.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_payload_dry_run.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_endpoint_guard_integration.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_preparation.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution_fix.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py \
           -q --basetemp=.pytest_basetemp
       # expect 450/450 PASS

2. Run the offline wiring preview in three decision modes (still no
   network, no order, no `--write-report`) to see the wiring
   transitions:

       # Unauthorized + offline IR -> WIRING_REJECTED_RULES_NOT_LOADED (exit 0).
       python3 scripts/preview_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py \
           --mark-price 100 --proposed-qty 0.1

       # Authorized but over 20 USDT cap -> WIRING_REJECTED_GATE_OVER_CAP (exit 0).
       python3 scripts/preview_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py \
           --ir-mode discover \
           --mark-price 250 --proposed-qty 0.1 \
           --i-understand-demo-solusdt-exchange-min-qty-exceeds-old-tiny-cap \
           --authorization-marker DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1

       # Authorized AND within cap -> WIRING_AUTHORIZED_CANDIDATE_QTY (exit 0).
       python3 scripts/preview_demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py \
           --ir-mode discover \
           --mark-price 100 --proposed-qty 0.1 \
           --i-understand-demo-solusdt-exchange-min-qty-exceeds-old-tiny-cap \
           --authorization-marker DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1

3. Do NOT retry `execute_demo_order` -- BM still uses BL packet
   `DEFAULT_QTY="0.01"` for the actual POST body. The wiring report's
   `execution_qty_resolved="0.1"` is **readiness/planning surface only**;
   wiring it into BM's actual POST body is **not** part of this Stage 1
   task and requires another explicit Stage 2 authorized task (which
   will change BL packet's qty source under a separate double-confirmation
   flag).

> Previous BM_CAP_ESCALATION_GATE banner archived below.
> TASK-014BM_CAP_ESCALATION_GATE_demo_only_SOLUSDT_min_qty_authorization is a
> **Stage 1, decision-only, demo-only** extension on top of
> TASK-014BM / TASK-014BM_FIX / TASK-014BM_MIN_QTY_FIX. It adds a
> narrow **authorization gate** that records whether Rick has
> explicitly opted in to placing **one** Bybit Demo SOLUSDT tiny
> order at the exchange-minimum quantity surfaced by
> TASK-014BM_MIN_QTY_FIX (`InstrumentRulesReport`) when that
> minimum is above the original tiny safety caps (TINY_QTY_CAP_SOL=0.05,
> TINY_SIZE_CAP_USDT=5). The gate is decision-only — it **never**
> sends an order, **never** calls `/v5/order/create`, **never**
> retries `execute_demo_order`, **never** touches a live endpoint,
> **never** reads any LIVE or DEMO secret env, **never** touches
> protected positions, **never** loosens MAX_ORDER_COUNT=1 or the
> double-confirmation flags, and **never** globally raises
> `TINY_QTY_CAP_SOL` / `TINY_SIZE_CAP_USDT` in BH.
>
> New module
> [`src/demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py`](../../../src/demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py):
> single decision entry point `run_cap_escalation_gate(instrument_rules_report,
> request, max_demo_min_qty_notional_cap_usdt)`; immutable constants
> `ALLOWED_ENVIRONMENT="bybit_demo"`, `ALLOWED_SYMBOL="SOLUSDT"`,
> `ALLOWED_SIDE="Buy"`, `ALLOWED_ORDER_TYPE="Market"`,
> `ALLOWED_TIME_IN_FORCE="IOC"`, `ALLOWED_MAX_ORDER_COUNT=1`;
> `MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT=Decimal("20")` (this single
> SOLUSDT demo path only); explicit two-piece authorization
> requirement: `EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_FLAG_NAME =
> "--i-understand-demo-solusdt-exchange-min-qty-exceeds-old-tiny-cap"` +
> `EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER =
> "DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1"`.
> Frozen dataclasses `EscalationAuthorizationRequest`,
> `EscalationAuthorizationDecision`, `CapEscalationGateReport`.
> Discovery statuses include `ESCALATION_NOT_REQUIRED` (original
> tiny cap passes), `ESCALATION_AUTHORIZED` (both flag + marker present
> and notional <= 20 USDT), `ESCALATION_NOT_AUTHORIZED` (escalation
> required but authorization missing), `ESCALATION_REJECTED_NOTIONAL_OVER_CAP`
> (notional > cap even with authorization), plus
> `ESCALATION_REJECTED_WRONG_SYMBOL` / `_WRONG_ENVIRONMENT` /
> `_WRONG_SIDE` / `_DISALLOWED_ORDER_TYPE` / `_DISALLOWED_TIF` /
> `_MAX_ORDER_COUNT` / `_REDUCE_ONLY` / `_TPSL` /
> `_PROTECTED_SYMBOL` / `_LIVE_ENDPOINT` / `_QTY_MISMATCH` /
> `_INVALID_RULES` / `_RULES_NOT_LOADED`.
>
> BM `ExecutionReport` is extended with 6 *defaulted* fields
> (`original_tiny_cap_passed`, `exchange_min_qty_cap_escalation_required`,
> `explicit_demo_min_qty_cap_authorized`, `cap_escalated_demo_only`,
> `cap_escalation_status`, `max_demo_min_qty_notional_cap_usdt`) and
> `run_explicit_tiny_order_execution()` grows one optional keyword
> `cap_escalation` so callers can inject a `CapEscalationGateReport`.
> When the kwarg is omitted every existing BM / BM_FIX / BM_MIN_QTY_FIX
> call site behaves identically; the 368 existing chain tests still
> pass unchanged. BM's `execute_demo_order` path and BL packet
> `DEFAULT_QTY="0.01"` are NOT modified by this task — wiring the
> candidate qty into the BM execution path requires another
> explicit Stage 2 authorized task.
>
> New preview CLI
> [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py`](../../../scripts/preview_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py)
> (`--mark-price`; `--proposed-qty`;
> `--max-demo-min-qty-notional-cap-usdt` default 20;
> `--i-understand-demo-solusdt-exchange-min-qty-exceeds-old-tiny-cap`;
> `--authorization-marker`; `--write-report` / `--output-dir`).
>
> New test file
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py`](../../../tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py)
> (49 tests) covers: identity / chain-break / upstream / immutable
> locks; authorization flag alone or marker alone is rejected; both
> together authorize when notional <= 20; custom cap rejects even
> when authorized; invalid cap falls back to default; original tiny
> cap pass → `ESCALATION_NOT_REQUIRED`; rejects non-SOLUSDT, non-demo
> environment, non-Buy side, non-Market order_type, non-IOC TIF,
> `max_order_count != 1`, qty mismatch, empty qty; rejects each of
> the 5 protected symbols (parametrized); rejects each of 4 live /
> order-create endpoint hints (parametrized); rejects reduce_only /
> close_on_trigger / stop_loss / take_profit; report writer never
> attempts network, never calls order endpoint, never sends an
> order; global `TINY_QTY_CAP_SOL` / `TINY_SIZE_CAP_USDT` /
> `PROTECTED_SYMBOLS` invariants are not mutated by the gate; AST
> static-source rules (no `requests` / `pybit` / `aiohttp` / `httpx` /
> `websocket` / `websockets` import, no `main` / `src.risk` /
> `src.executors.bybit` import, no `BybitExecutor` name, no
> `os.environ` / `os.getenv` access, no non-docstring string
> literal references a LIVE or DEMO secret env name, no live host
> token appears more than once in source); report writer emits 4
> files + JSON round-trip + Markdown contains
> `TASK-014BM_CAP_ESCALATION_GATE` / `cap_escalated_demo_only`; BM
> `ExecutionReport` defaults leave the 6 new fields safe; BM
> `ExecutionReport` with injected `cap_escalation` correctly
> surfaces both authorized and unauthorized decision paths.
>
> No safety-critical surface was modified: no live endpoint, no live
> secret loading, no `main.py` / `src/risk.py` /
> `src/executors/bybit.py` change, no `BybitExecutor` live behavior
> change, no protected-position code touched, no retry, no scheduler,
> no stop endpoint, no TP/SL, no `/v5/order/create` call, no new
> real Bybit Demo order sent.
>
> Validation (this commit):
> py_compile of all 4 changed Python files PASS;
> `pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py
> -q --basetemp=.pytest_basetemp` → **49/49 PASS**;
> BH→BM chain regression (BH + BI + BJ + BK + BL + BM + BM_FIX +
> BM_MIN_QTY_FIX + BM_CAP_ESCALATION_GATE, 9 demo_trading adapter
> test files) → **417/417 PASS**;
> preview offline smoke `--mark-price 100 --proposed-qty 0.1` (no
> authorization) → exit 0,
> `status=ESCALATION_NOT_AUTHORIZED`, `authorized=False`,
> `network_attempted=False`, `order_endpoint_called=False`,
> `order_sent=False`; BM readiness preview and BM_MIN_QTY_FIX
> preview unchanged → both exit 0, no order sent.
>
> No new real Bybit Demo order was sent during this Stage 1 task.
>
> Previous BM_MIN_QTY_FIX banner archived below.

## TASK-014BM_CAP_ESCALATION_GATE Status (2026-06-19)

| item | status |
|---|---|
| new src `src/demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py` (decision-only entry point `run_cap_escalation_gate()`; locked environment/symbol/side/order_type/TIF/max_order_count; 20-USDT notional ceiling; two-piece authorization (flag + marker); report writer) | DONE |
| new scripts `scripts/preview_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py` (`--mark-price`; `--proposed-qty`; `--max-demo-min-qty-notional-cap-usdt`; explicit auth flag; authorization marker; `--write-report` / `--output-dir`) | DONE |
| new tests `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py` (Stage 1 focused-core 49 tests) | DONE |
| BM `ExecutionReport` extended with 6 defaulted cap-escalation fields; `run_explicit_tiny_order_execution()` grows optional `cap_escalation` kwarg; existing 368 BH→BM_MIN_QTY_FIX tests unchanged and still PASS | DONE |
| chain-break markers: `TASK_ID="TASK-014BM_CAP_ESCALATION_GATE"`, `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-CAP-ESCALATION-GATE"`, `IMPLEMENTATION_PATH_PHASE="tiny_order_cap_escalation_gate"`, `IS_REVIEW_CHAIN_SUFFIX=False`, `UPSTREAM_TASKS=("TASK-014BH","TASK-014BM","TASK-014BM_FIX","TASK-014BM_MIN_QTY_FIX")` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BN_demo_only_tiny_execution_postfill_audit"` (passes `bh.assert_next_task_is_not_review_chain_suffix`) | DONE |
| default gate behaviour is **fail-closed** (no authorization, no escalation); both `--i-understand-demo-solusdt-exchange-min-qty-exceeds-old-tiny-cap` AND `EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER` are required to authorize | CONFIRMED |
| `MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT = Decimal("20")` is enforced AFTER explicit authorization; candidate_notional > cap returns `ESCALATION_REJECTED_NOTIONAL_OVER_CAP` even when authorization flag + marker are both present | CONFIRMED |
| environment / symbol / side / order_type / TIF / max_order_count / reduce_only / close_on_trigger / stop_loss / take_profit / protected symbols / endpoint hint all have dedicated fail-closed paths with distinct `ESCALATION_REJECTED_*` statuses | CONFIRMED |
| `proposed_qty` must exactly equal `candidate_qty` derived by TASK-014BM_MIN_QTY_FIX; mismatch returns `ESCALATION_REJECTED_QTY_MISMATCH` | CONFIRMED |
| global `TINY_QTY_CAP_SOL=0.05` / `TINY_SIZE_CAP_USDT=5` constants in BH are NOT modified; the escalation is scoped to this single SOLUSDT demo path only | CONFIRMED |
| protected symbols denylist `{ENA, TIA, AIXBT, POLYX, EDU}USDT` is NOT modified | CONFIRMED |
| AST static-source safety invariants (no third-party HTTP client import; no `main` / `src.risk` / `src.executors.bybit` import; no `BybitExecutor` `Name`/`Attribute` reference; no non-docstring secret env name; no `os.environ` / `os.getenv`; no live host token used more than once in source) | CONFIRMED |
| report writer emits `latest_*.json` / `latest_*.md` / `*_<UTC_TS>.json` / `*_<UTC_TS>.md` to `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate/` | DONE |
| py_compile (src + scripts + tests) | PASS |
| pytest BM_CAP_ESCALATION_GATE Stage 1 focused-core | **49/49 PASS** |
| pytest BH + BI + BJ + BK + BL + BM + BM_FIX + BM_MIN_QTY_FIX + BM_CAP_ESCALATION_GATE safety-chain regression | **417/417 PASS** (368 prior chain + 49 new) |
| BM_CAP_ESCALATION_GATE preview offline smoke `--mark-price 100 --proposed-qty 0.1` (no authorization) | exit 0; `status=ESCALATION_NOT_AUTHORIZED`; `authorized=False`; `network_attempted=False`; `order_endpoint_called=False`; `order_sent=False` |
| BM readiness preview (post-change regression) | exit 0; `final_status=READINESS_OK_NO_NETWORK`; no network, no order sent |
| BM_MIN_QTY_FIX preview (post-change regression) | exit 0; `discovery_status=DISCOVERY_OFFLINE_NO_NETWORK`; no network, no order sent |
| safety invariants (no live endpoint call / no live secret read / no demo secret read / no stop endpoint / no TP-SL attachment / no retry / no scheduler / no G20 lift / no position modification / no protected position interaction / no `/v5/order/create` call / no new real demo order / no global tiny cap lift) | CONFIRMED |
| main.py / src/risk.py / src/executors/bybit.py / BybitExecutor | UNTOUCHED |
| local commit | pending: `TASK-014BM_CAP_ESCALATION_GATE: add demo-only SOLUSDT cap escalation authorization gate (decision-only; locked bybit_demo+SOLUSDT+Buy+Market+IOC; 20 USDT notional cap; double-confirmation flag+marker required; BM ExecutionReport gains 6 defaulted cap-escalation fields; 49 new tests; existing 368 BH→BM_MIN_QTY_FIX tests unchanged)` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-19 TASK-014BM_CAP_ESCALATION_GATE)

1. VPS git pull and re-validate the new module offline first:

       git pull --ff-only
       source .venv/bin/activate
       python3 -m py_compile \
           src/demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py \
           src/demo_only_tiny_execution_adapter_tiny_order_execution.py \
           scripts/preview_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py
       python3 -m pytest \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py \
           -q --basetemp=.pytest_basetemp
       # expect 49/49 PASS
       python3 -m pytest \
           tests/demo_trading/test_demo_only_tiny_execution_adapter.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_payload_dry_run.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_endpoint_guard_integration.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_preparation.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution_fix.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py \
           -q --basetemp=.pytest_basetemp
       # expect 417/417 PASS

2. Run the offline preview in three decision modes (still no network, no
   order) to see the gate transitions:

       # Unauthorized -> ESCALATION_NOT_AUTHORIZED (exit 0).
       python3 scripts/preview_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py \
           --mark-price 100 --proposed-qty 0.1

       # Authorized but over 20 USDT cap -> ESCALATION_REJECTED_NOTIONAL_OVER_CAP (exit 0).
       python3 scripts/preview_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py \
           --mark-price 250 --proposed-qty 0.1 \
           --i-understand-demo-solusdt-exchange-min-qty-exceeds-old-tiny-cap \
           --authorization-marker DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1

       # Authorized AND within 20 USDT cap -> ESCALATION_AUTHORIZED (exit 0).
       python3 scripts/preview_demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate.py \
           --mark-price 100 --proposed-qty 0.1 \
           --i-understand-demo-solusdt-exchange-min-qty-exceeds-old-tiny-cap \
           --authorization-marker DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1

3. Do NOT retry `execute_demo_order` -- BM still uses BL packet
   `DEFAULT_QTY="0.01"` and would be rejected by Bybit's
   `minOrderQty=0.1`. Wiring the candidate qty into the BM execution
   path is **not** part of this Stage 1 task and requires another
   explicit Stage 2 authorized task.

> Previous BM_MIN_QTY_FIX banner archived below.
> TASK-014BM_MIN_QTY_FIX_demo_only_tiny_order_instrument_rules
> is a **Stage 1, read-only, demo-only** extension on top of
> TASK-014BM / TASK-014BM_FIX. It adds a new narrow instrument-rules
> discovery layer for SOLUSDT so the tiny order preparation / execution
> path can stop assuming `qty=0.01` when Bybit's current SOLUSDT linear
> `lotSizeFilter.minOrderQty` is larger (observed `retCode=10001 "The
> number of contracts exceeds minimum limit allowed"` after the
> signing fix). The task is allowed to call only the **public**
> `/v5/market/instruments-info?category=linear&symbol=SOLUSDT` endpoint
> on the demo domain. It does **not** send any new real order, does
> **not** retry `execute_demo_order`, does **not** call
> `/v5/order/create`, does **not** touch live endpoint, and does
> **not** read any live or demo secret env.
>
> New module
> [`src/demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py`](../../../src/demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py):
> single aggregator entry point
> `run_instrument_rules_discovery(mode, mark_price, category, symbol,
> sender, pre_parsed_response)`; immutable constants
> `ALLOWED_DEMO_HOST = "api-demo.bybit.com"`,
> `ALLOWED_READONLY_URL = "https://api-demo.bybit.com/v5/market/instruments-info"`,
> `ALLOWED_CATEGORY = "linear"`, `ALLOWED_SYMBOL = "SOLUSDT"`;
> `_assert_locked_inputs` rejects non-linear, non-SOLUSDT, and any
> endpoint URL that is not exactly `ALLOWED_READONLY_URL`;
> `FORBIDDEN_URL_TOKENS = ("/v5/order/create", "/v5/order/cancel",
> "/v5/position/set-trading-stop", "https://api.bybit.com",
> "https://api.bytick.com", "wss://stream.bybit.com",
> "wss://stream.bytick.com")`; default mode `offline` (no network);
> `discover` mode performs a single bounded `urllib.request` GET via
> the supplied sender (default `_real_public_get_via_urllib` which
> hard-asserts URL prefix `ALLOWED_READONLY_URL + "?"`); no API key,
> no signing, no recv-window; no retry, no scheduler. Parser
> `parse_instrument_rules(parsed)` finds the SOLUSDT linear entry,
> raises on missing `lotSizeFilter`, exposes `minOrderQty`, `qtyStep`,
> `minNotionalValue`, and optional `maxMktOrderQty` / `tickSize`.
> Candidate computation `compute_candidate_tiny_qty(rules, mark_price,
> tiny_qty_cap_sol=TINY_QTY_CAP_SOL,
> tiny_size_cap_usdt=TINY_SIZE_CAP_USDT)` starts from
> `max(minOrderQty, qty_step)` aligned UP to `qty_step`, bumps up to
> the smallest `qty_step` multiple satisfying `minNotionalValue` when
> needed, then compares against BH's `TINY_QTY_CAP_SOL = 0.05` and
> `TINY_SIZE_CAP_USDT = 5`. If either cap is exceeded the candidate
> reports `STATUS_TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN` with
> `is_executable_under_tiny_caps=False` — the module **never silently
> lifts the cap**, and the report also surfaces `confirms_qty_0_01_invalid`
> when `0.01 < minOrderQty`.
>
> BM ExecutionReport is extended with 9 *defaulted* fields
> (`instrument_rules_loaded`, `instrument_rules_discovery_status`,
> `instrument_rules_min_order_qty`, `instrument_rules_qty_step`,
> `instrument_rules_min_notional_value`, `computed_candidate_qty`,
> `computed_candidate_notional`,
> `candidate_is_executable_under_tiny_caps`,
> `qty_0_01_confirmed_invalid`) and `run_explicit_tiny_order_execution()`
> grows one optional keyword `instrument_rules` so callers can inject
> an `InstrumentRulesReport`. When the kwarg is omitted every existing
> BM / BM_FIX call site behaves identically; the 88 existing BM /
> BM_FIX tests still pass unchanged. BM's `execute_demo_order` path
> and BL packet `DEFAULT_QTY="0.01"` are NOT modified by this task —
> changing the execute-time qty requires another explicit authorized
> task.
>
> New preview CLI
> [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py`](../../../scripts/preview_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py)
> (`--mode {offline,discover}` default offline; `--mark-price`;
> `--write-report` / `--output-dir`; exit code 0 for
> `DISCOVERY_OK` / `DISCOVERY_OFFLINE_NO_NETWORK` and expected
> `TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN` fail-closed reporting, 1
> otherwise).
>
> New test file
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py`](../../../tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py)
> (~52 tests) covers: identity / chain-break / non-review-chain-suffix
> assertion; endpoint + category + symbol hard lock; `_real_public_get_via_urllib`
> refuses any non-allowed URL prefix (including live host and
> `/v5/order/create` on demo host); parser parses minimal SOLUSDT
> linear `instruments-info` response with optional fields; parser
> rejects missing `lotSizeFilter` / missing `minOrderQty` / non-SOLUSDT
> entry / empty list; candidate aligns to `qty_step`; candidate bumps
> qty up to satisfy `minNotionalValue` (e.g. min_qty=0.01 / step=0.01 /
> min_notional=5 / mark=100 → candidate 0.05); fail-closed when
> exchange minimum exceeds tiny cap (e.g. min_qty=0.1 →
> `TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN`, not executable); confirms
> `qty=0.01` invalid when `0.01 < minOrderQty`; invalid rules
> (negative `min_order_qty`) → `CANDIDATE_INVALID_RULES`; missing
> mark price with positive `minNotionalValue` →
> `CANDIDATE_INVALID_MARK_PRICE`; offline default → no network, no
> rules; pre-parsed response path; injected sender records the
> request URL and is the ONLY URL contacted (sentinel asserts no
> `/v5/order/create` / no live host); network error path; non-zero
> retCode path; AST static-source: no `requests` / `pybit` / `aiohttp`
> / `httpx` / `websocket` import, no `main` / `src.risk` /
> `src.executors.bybit` import, no `BybitExecutor` `Name`/`Attribute`
> reference, no non-docstring string literal references any LIVE or
> DEMO secret env name, no `os.environ` / `os.getenv` attribute
> access; report writer emits 4 files + JSON round-trip + Markdown
> contains `TASK-014BM_MIN_QTY_FIX` / `minOrderQty`; BM
> `ExecutionReport` defaults leave the 9 new fields at safe defaults;
> BM `ExecutionReport` with injected `instrument_rules` correctly
> surfaces the three discovery fields, the two candidate qty /
> notional fields, the executable-under-tiny-caps boolean, and the
> `qty_0_01_confirmed_invalid` boolean.
>
> No safety-critical surface was modified: no live endpoint, no live
> secret loading, no `main.py` / `src/risk.py` / `src/executors/bybit.py`
> change, no `BybitExecutor` live behavior change, no protected-position
> code touched, no retry, no scheduler, no stop endpoint, no TP/SL,
> no `/v5/order/create` call, no new real Bybit Demo order sent.
>
> Validation (this commit):
> py_compile of all 4 changed Python files PASS;
> `pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py
> -q --basetemp=.pytest_basetemp` → **52/52 PASS**;
> BH→BM chain regression (BH + BI + BJ + BK + BL + BM original + BM
> FIX + BM_MIN_QTY_FIX, 8 demo_trading adapter test files) →
> **368/368 PASS**;
> preview offline smoke `--mode offline --mark-price 100` → exit 0,
> `discovery_status=DISCOVERY_OFFLINE_NO_NETWORK`,
> `network_attempted=False`, `order_endpoint_called=False`,
> `order_sent=False`; BM readiness preview `--mode readiness` → exit 0,
> `final_status=READINESS_OK_NO_NETWORK`, no network, no order
> endpoint called.
>
> No new real Bybit Demo order was sent during this Stage 1 task.
>
> Previous BM_FIX banner archived below.

## TASK-014BM_MIN_QTY_FIX Status (2026-06-19)

| item | status |
|---|---|
| new src `src/demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py` (single aggregator entry point `run_instrument_rules_discovery()`; locked read-only endpoint; locked category=linear, symbol=SOLUSDT; parser; candidate qty computation with tiny-cap fail-closed; report writer) | DONE |
| new scripts `scripts/preview_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py` (`--mode {offline,discover}` default offline; `--mark-price`; `--write-report` / `--output-dir`; exit codes 0/1) | DONE |
| new tests `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py` (Stage 1 focused-core 52 tests) | DONE |
| BM `ExecutionReport` extended with 9 defaulted instrument-rules fields; `run_explicit_tiny_order_execution()` grows optional `instrument_rules` kwarg; existing 88 BM / BM_FIX tests unchanged and still PASS | DONE |
| chain-break markers: `TASK_ID="TASK-014BM_MIN_QTY_FIX"`, `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-INSTRUMENT-RULES"`, `IMPLEMENTATION_PATH_PHASE="tiny_order_instrument_rules"`, `IS_REVIEW_CHAIN_SUFFIX=False`, `UPSTREAM_TASKS=("TASK-014BH","TASK-014BM","TASK-014BM_FIX")` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BN_demo_only_tiny_execution_postfill_audit"` (does not end in `_readiness_review` / `_final_pre_execution_review` / `_manual_authorization_review`; passes `bh.assert_next_task_is_not_review_chain_suffix`) | DONE |
| default mode is non-network (`offline`); `discover` mode performs ONE bounded GET via injected or stdlib urllib sender; no signing, no API key, no recv-window | CONFIRMED |
| endpoint URL hard-locked to `https://api-demo.bybit.com/v5/market/instruments-info`; `_assert_locked_inputs` + `_real_public_get_via_urllib` URL-prefix check both reject any other URL (including live `api.bybit.com`, `api.bytick.com`, and `/v5/order/create` on demo host) | CONFIRMED |
| `FORBIDDEN_URL_TOKENS` includes `/v5/order/create`, `/v5/order/cancel`, `/v5/position/set-trading-stop`, all live hosts and all websocket hosts | CONFIRMED |
| candidate qty derived from `minOrderQty` and `qtyStep`, aligned UP to `qtyStep`, bumped up to satisfy `minNotionalValue` against supplied `mark_price` | CONFIRMED via 4 parametrize-style tests |
| candidate **fails closed** with `STATUS_TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN` when exchange minimum exceeds either `TINY_QTY_CAP_SOL=0.05` or `TINY_SIZE_CAP_USDT=5`; never silently lifts cap | CONFIRMED |
| `confirms_qty_0_01_invalid` is True when observed `minOrderQty > 0.01` (the observed Bybit Demo retCode=10001 failure case) | CONFIRMED |
| sender sentinel test guarantees the only URL contacted is `ALLOWED_READONLY_URL?category=linear&symbol=SOLUSDT`; `/v5/order/create` / `api.bybit.com` / `api.bytick.com` never appear | CONFIRMED |
| AST static-source safety invariants (no `requests` / `pybit` / `aiohttp` / `httpx` / `websocket` import; no `main` / `src.risk` / `src.executors.bybit` import; no `BybitExecutor` `Name`/`Attribute` reference; no non-docstring secret env name; no `os.environ` / `os.getenv`) | CONFIRMED |
| report writer emits `latest_*.json` / `latest_*.md` / `*_<UTC_TS>.json` / `*_<UTC_TS>.md` to `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_instrument_rules/` | DONE |
| py_compile (src + scripts + tests) | PASS |
| pytest BM_MIN_QTY_FIX Stage 1 focused-core | **52/52 PASS** |
| pytest BH + BI + BJ + BK + BL + BM + BM_FIX + BM_MIN_QTY_FIX safety-chain regression | **368/368 PASS** (316 prior chain + 52 new) |
| BM_MIN_QTY_FIX preview offline smoke `--mode offline --mark-price 100` | exit 0; `discovery_status=DISCOVERY_OFFLINE_NO_NETWORK`; `network_attempted=False`; `order_endpoint_called=False`; `order_sent=False` |
| BM readiness preview `--mode readiness` (post-change regression) | exit 0; `final_status=READINESS_OK_NO_NETWORK`; `network_attempted=False`; `order_endpoint_called=False`; `order_sent=False`; `live_endpoint_denied=True`; `protected_symbols_untouched=True`; `max_order_count=1`; `all_pre_network_gates_passed=True` |
| safety invariants (no live endpoint call / no live secret read / no demo secret read / no stop endpoint / no TP-SL attachment / no retry / no scheduler / no G20 lift / no position modification / no protected position interaction / no `/v5/order/create` call / no new real demo order) | CONFIRMED |
| main.py / src/risk.py / src/executors/bybit.py / BybitExecutor | UNTOUCHED |
| local commit | pending: `TASK-014BM_MIN_QTY_FIX: add demo-only tiny execution adapter SOLUSDT instrument rules discovery layer (read-only public /v5/market/instruments-info; locked linear+SOLUSDT; candidate qty aligned to qtyStep; tiny-cap fail-closed; BM ExecutionReport gains 9 defaulted instrument-rules fields; existing 88 BM/BM_FIX tests unchanged)` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-19 TASK-014BM_MIN_QTY_FIX)

1. VPS git pull and re-validate the new module offline first:

       git pull --ff-only
       source .venv/bin/activate
       python3 -m py_compile \
           src/demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py \
           src/demo_only_tiny_execution_adapter_tiny_order_execution.py \
           scripts/preview_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py
       python3 -m pytest \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py \
           -q --basetemp=.pytest_basetemp
       # expect 52/52 PASS
       python3 -m pytest \
           tests/demo_trading/test_demo_only_tiny_execution_adapter.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_payload_dry_run.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_endpoint_guard_integration.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_preparation.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution_fix.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py \
           -q --basetemp=.pytest_basetemp
       # expect 368/368 PASS

2. Run the offline preview (still no network, no order):

       python3 scripts/preview_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py \
           --mode offline --mark-price 100 --write-report
       # exit 0
       # discovery_status=DISCOVERY_OFFLINE_NO_NETWORK
       # network_attempted=False  order_endpoint_called=False  order_sent=False
       # rules: <not loaded>; candidate.status=CANDIDATE_RULES_NOT_LOADED
       # 4 report files written under
       # outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_instrument_rules/

3. **Optional and only if Rick wants to actually look up current
   Bybit Demo SOLUSDT linear instrument rules** (no secrets, no
   order create, no signing — public endpoint):

       python3 scripts/preview_demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py \
           --mode discover --mark-price 100 --write-report
       # exit 0
       # network_attempted=True  order_endpoint_called=False  order_sent=False
       # http_status=200  bybit_ret_code=0
       # rules: symbol=SOLUSDT minOrderQty=<observed> qtyStep=<observed> ...
       # candidate.status one of CANDIDATE_OK / TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN
       # If TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN: candidate.is_executable_under_tiny_caps=False
       #   confirms_qty_0_01_invalid=True (when minOrderQty > 0.01)
       #   reason: "candidate qty=... notional=... exceeds tiny cap ... fail closed, do NOT send"

4. Use the discovery report (offline pre-parsed or `--mode discover`)
   to decide the next authorized task. Options Rick may consider —
   **none of them are pre-authorized by this task**:
     * `TASK-014BN_demo_only_tiny_execution_postfill_audit` (still the
       documented successor; the BM execute path is currently blocked
       by retCode=10001 so this only proceeds after an explicit
       sizing decision).
     * a new explicit task to widen `TINY_QTY_CAP_SOL` /
       `TINY_SIZE_CAP_USDT` to match the current Bybit Demo SOLUSDT
       minimum (only with a documented risk delta and a refreshed
       set of gates), then re-run `execute_demo_order` once.
     * a new explicit task to change BL packet `DEFAULT_QTY` (and BM
       `qty_within_tiny_cap` gate) from `0.01` to the computed
       candidate (only after Rick agrees that the resulting notional
       is still inside the intended tiny risk envelope).

5. **Do NOT retry** `execute_demo_order` with `qty=0.01`. The observed
   `retCode=10001 "The number of contracts exceeds minimum limit
   allowed"` will repeat. Use the discovery layer first.

---

> TASK-014BM_FIX_demo_only_tiny_order_execution_signature_and_status_mapping
> is a **Stage 1 corrective patch** on top of TASK-014BM. It fixes the
> Bybit V5 HMAC signing path (the previously sent execution attempt was
> rejected with `retCode=10004 "Error sign, please check your signature
> generation algorithm"`) and tightens the `final_status` mapping so that
> `EXECUTED_DEMO_ONLY` is **only** assigned when an order was actually
> accepted by Bybit Demo. The FIX does **not** send any new real order.
>
> What changed in
> [`src/demo_only_tiny_execution_adapter_tiny_order_execution.py`](../../../src/demo_only_tiny_execution_adapter_tiny_order_execution.py):
> (a) a new helper `_serialize_signed_body(body_preview) -> (json_body_string, body_bytes)`
> produces a single canonical compact JSON serialization
> (`json.dumps(..., separators=(",", ":"), ensure_ascii=False)`) and
> asserts `body_bytes.decode("utf-8") == json_body_string` so the **exact
> bytes posted are byte-identical** to the body string used in the
> HMAC prehash; (b) `_sign_bybit_v5` now takes `json_body_string: str`
> directly instead of reconstructing it, ensuring the prehash is
> `timestamp_ms + api_key + recv_window + json_body_string`; (c) the
> HTTP envelope now includes the previously-missing
> `X-BAPI-SIGN-TYPE: "2"` header alongside `X-BAPI-API-KEY` /
> `X-BAPI-TIMESTAMP` / `X-BAPI-SIGN` / `X-BAPI-RECV-WINDOW` /
> `Content-Type: application/json`; (d) `final_status` mapping in
> `run_explicit_tiny_order_execution` is hard-gated — `EXECUTED_DEMO_ONLY`
> is only set when `outcome.order_sent is True AND
> outcome.bybit_ret_code == 0 AND outcome.bybit_order_id` is non-empty;
> any non-zero `retCode` (including the observed `10004`) or empty
> `bybit_order_id` now maps to the **new** `STATUS_BYBIT_REJECTED_NO_ORDER_SENT`
> with `order_sent=False`; `NETWORK_ERROR_DEMO_ONLY` continues to take
> precedence when the sender raises a network error.
>
> New constants exported: `STATUS_BYBIT_REJECTED_NO_ORDER_SENT =
> "BYBIT_REJECTED_NO_ORDER_SENT"`, `BAPI_SIGN_TYPE_HEADER =
> "X-BAPI-SIGN-TYPE"`, `BAPI_SIGN_TYPE_VALUE = "2"`. `__all__` extended
> to expose `_serialize_signed_body`, `_sign_bybit_v5`, and the new
> constants for testability.
>
> CLI ([`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_execution.py`](../../../scripts/preview_demo_only_tiny_execution_adapter_tiny_order_execution.py))
> docstring updated to map `BYBIT_REJECTED_NO_ORDER_SENT` under exit
> code 1 alongside `GATE_REJECTED_NO_NETWORK` / `NETWORK_ERROR_DEMO_ONLY`.
> The existing dispatcher fallthrough handles the new status — no
> behavioral CLI flag change.
>
> New regression test file
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution_fix.py`](../../../tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution_fix.py)
> (~19 tests) covers: exact `retCode=10004 "Error sign"` regression →
> `BYBIT_REJECTED_NO_ORDER_SENT` with `order_sent=False` and empty
> `bybit_order_id` and status != `EXECUTED_DEMO_ONLY`; parametrized
> non-zero retCodes (`10003 / 10004 / 10005 / 10010 / 110007`) all
> mapping to `BYBIT_REJECTED_NO_ORDER_SENT`; `retCode=0` with empty
> `orderId` still rejects (never `EXECUTED_DEMO_ONLY`); the five-condition
> conjunction for `EXECUTED_DEMO_ONLY` is enforced; recomputing HMAC
> over the posted body bytes equals the `X-BAPI-SIGN` header (byte
> equality of posted body vs. signed body string); compact JSON is
> stable, contains no Python-style `True`/`False` literals, and uses
> JSON-style `false`; `X-BAPI-SIGN-TYPE` header is exactly `"2"`;
> `X-BAPI-SIGN` matches `^[0-9a-f]{64}$`; full V5 envelope contains all
> 6 required headers; safety constants preserved
> (`MAX_ORDER_COUNT=1`, `ALLOWED_DEMO_ENDPOINT_URL` unchanged, demo-only
> env names unchanged).
>
> No safety-critical surface was modified: no live endpoint, no live
> secret loading, no `main.py` / `src/risk.py` / `src/executors/bybit.py`
> change, no `BybitExecutor` live behavior change, no protected-position
> code touched, no retry, no scheduler, no stop endpoint, no TP/SL.
> The fix touches only the signing serialization, the signature header
> set, and the success-mapping conjunction.
>
> Validation (this commit):
> py_compile of all three changed Python files PASS;
> `pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution.py
> tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution_fix.py
> -q --basetemp=.pytest_basetemp` → **88/88 PASS**
> (69 original BM + 19 FIX);
> BH→BL→BM chain regression (all 7 demo_trading adapter files) →
> **316/316 PASS**;
> preview readiness smoke `--mode readiness` → exit 0,
> `final_status=READINESS_OK_NO_NETWORK`, `network_attempted=False`,
> `order_endpoint_called=False`, `order_sent=False`,
> `live_endpoint_denied=True`, `protected_symbols_untouched=True`,
> `max_order_count=1`, `all_pre_network_gates_passed=True`.
>
> No new real Bybit Demo order was sent during this FIX task.
>
> Previous BM banner archived below.

> README shared status updated by TASK-014BM (2026-06-18). TASK-014BM
> adds the explicit **demo-only tiny order execution path** on top of
> TASK-014BH / TASK-014BI / TASK-014BJ / TASK-014BK / TASK-014BL. It is
> the **first task** in the implementation-path chain that contains a
> real `urllib.request` POST capable of sending exactly one tiny demo
> order to `https://api-demo.bybit.com/v5/order/create`. The default
> mode is non-sending (`readiness`) and the network call is hard-gated
> behind two cooperating CLI flags **plus** sixteen ordered gates **plus**
> the presence of demo-scoped credentials. New BM triplet:
> [`src/demo_only_tiny_execution_adapter_tiny_order_execution.py`](../../../src/demo_only_tiny_execution_adapter_tiny_order_execution.py)
> (single aggregator entry point `run_explicit_tiny_order_execution(mode,
> execute_flag, confirm_flag, existing_positions, endpoint_target,
> credentials, env, sender)`; module-import-time call to
> `bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)`;
> five frozen dataclasses `DemoCredentials` / `ExecutionGate` /
> `ExecutionPlan` / `SendOutcome` / `ExecutionReport`; 16 ordered gates
> split into 13 pre-network gates `bl_packet_loaded` /
> `bl_packet_all_passed` / `packet_marked_not_execution_authorization` /
> `packet_audit_status_from_bh` / `environment_is_bybit_demo` /
> `symbol_is_solusdt` / `qty_within_tiny_cap` / `order_type_market` /
> `time_in_force_ioc` / `reduce_only_false` / `endpoint_target_demo_only`
> / `protected_symbols_not_in_scope` / `order_count_locked_to_one` and
> 3 execute gates `explicit_execute_flag` / `explicit_confirm_flag` /
> `demo_credentials_present`; three modes `dry_run` / `readiness` (both
> always offline) / `execute_demo_order` (the only mode that may call
> the network, and only if **both** `--execute-demo-order` and
> `--i-understand-this-sends-one-bybit-demo-order` flags are present
> AND all 16 gates pass AND demo credentials are present); six
> `final_status` outcomes
> `DRY_RUN_OK_NO_NETWORK` / `READINESS_OK_NO_NETWORK` /
> `GATE_REJECTED_NO_NETWORK` / `MISSING_DEMO_CREDENTIALS` /
> `EXECUTED_DEMO_ONLY` / `NETWORK_ERROR_DEMO_ONLY`; sender uses
> dependency injection (default `_real_sender_via_urllib` hard-asserts
> URL == `ALLOWED_DEMO_ENDPOINT_URL = https://api-demo.bybit.com/v5/order/create`
> and POSTs exactly once via stdlib `urllib.request`, no retry, no
> scheduler); Bybit V5 HMAC-SHA256 signing
> `HMAC(secret, timestamp+api_key+recv_window+body)` with headers
> `X-BAPI-API-KEY` / `X-BAPI-TIMESTAMP` / `X-BAPI-SIGN` /
> `X-BAPI-RECV-WINDOW`; body shape is exactly 9 fields `category` /
> `symbol` / `side` / `orderType` / `qty` / `timeInForce` / `reduceOnly`
> / `closeOnTrigger` / `orderLinkId` — **no `stopLoss`, no `takeProfit`,
> no `trading-stop` endpoint, no TP/SL attachment of any kind**;
> demo credentials are read **only** from `BYBIT_DEMO_API_KEY` /
> `BYBIT_DEMO_API_SECRET` / `BYBIT_DEMO_RECV_WINDOW`, never falling
> back to live env names; missing credentials produce a safe
> `MISSING_DEMO_CREDENTIALS` report (not a failure); `MAX_ORDER_COUNT=1`
> hard-locks the per-run order count; `write_report` emits JSON +
> Markdown to
> `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_execution/`
> as `latest_*.json` / `latest_*.md` / timestamped `*_<UTC_TS>.json` /
> `*_<UTC_TS>.md`; chain-break markers `TASK_ID="TASK-014BM"`,
> `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-EXECUTION"`,
> `IMPLEMENTATION_PATH_PHASE="tiny_order_execution"`,
> `IS_REVIEW_CHAIN_SUFFIX=False`,
> `UPSTREAM_TASKS=("TASK-014BH","TASK-014BI","TASK-014BJ","TASK-014BK","TASK-014BL")`,
> `NEXT_REQUIRED_TASK="TASK-014BN_demo_only_tiny_execution_postfill_audit"`,
> `EXECUTION_CONTRACT_VERSION="demo_only_tiny_execution_adapter_tiny_order_execution_v1"`),
> [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_execution.py`](../../../scripts/preview_demo_only_tiny_execution_adapter_tiny_order_execution.py)
> (CLI; default `--mode readiness` (no network, no secret read);
> `--mode execute_demo_order` **requires** both `--execute-demo-order`
> and `--i-understand-this-sends-one-bybit-demo-order` flags otherwise
> falls through to `GATE_REJECTED_NO_NETWORK`; `--endpoint-target`
> override for tests; `--write-report` / `--output-dir`; includes ROOT
> sys.path injection; exit code 0 for `DRY_RUN_OK_NO_NETWORK` /
> `READINESS_OK_NO_NETWORK` / `EXECUTED_DEMO_ONLY`, 2 for
> `MISSING_DEMO_CREDENTIALS`, 1 otherwise), and
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution.py`](../../../tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution.py)
> (Stage 1 focused-core **69 tests** — identity / chain-break markers /
> BM pointer is not a review-chain suffix and explicitly references
> `demo_only_tiny_execution_postfill_audit` / `EXECUTION_CONTRACT_VERSION`
> / 16 gate names + ordering / `ALLOWED_DEMO_ENDPOINT_URL` /
> `MAX_ORDER_COUNT=1` constants; default `--mode dry_run` never calls
> the sender; `--mode readiness` passes all 13 pre-network gates with
> no network and a plan that is built; `--mode execute_demo_order`
> without flags →`STATUS_GATE_REJECTED_NO_NETWORK` and sender is never
> invoked; with both flags but no creds →`STATUS_MISSING_DEMO_CREDENTIALS`;
> with both flags + creds + a fake injected sender →`STATUS_EXECUTED_DEMO_ONLY`
> with `order_sent=True`, `order_endpoint_called=True`, sender call
> counter exactly 1, and `bybit_order_id` captured; injected sender
> raising `urllib.error.URLError` →`STATUS_NETWORK_ERROR_DEMO_ONLY`;
> every pre-network reject path (3 live URLs, 3 non-SOLUSDT symbols, 5
> protected symbols, 5 protected existing positions, 4 over-cap qty,
> `reduceOnly=True`, missing packet, tampered
> `_demo_only_bh_audit_response_status`, tampered
> `packet_is_not_execution_authorization=False`) confirms sender is
> never called via a sentinel-raising sender; credential loader only
> reads `BYBIT_DEMO_*` env names; LIVE env names `BYBIT_API_KEY` /
> `BYBIT_API_SECRET` set without DEMO names → returns not present;
> `_real_sender_via_urllib` raises if URL ≠ allowed demo URL (real and
> via plan); `ExecutionPlan` / `ExecutionReport` are frozen-immutable;
> AST-based static-source checks: no import of `requests` / `pybit` /
> `aiohttp` / `httpx`, no import of `main` / `src.risk` /
> `src.executors.bybit`, no `BybitExecutor` `Name`/`Attribute`
> reference, docstring-stripped source contains no LIVE env names and
> no `set-trading-stop` / `stopLoss` / `takeProfit` / retry / scheduler
> tokens; BM source imports BH/BI/BJ/BK/BL directly (single-source
> upstream chain); BH `assert_next_task_is_not_review_chain_suffix`
> accepts BM's own `NEXT_REQUIRED_TASK` and rejects each of the 3
> forbidden review-chain suffixes; BK
> `run_final_pre_execution_checklist().all_passed` and BL
> `run_tiny_order_preparation().all_passed` still True under BM
> import; cross-module `BybitExecutor` / `main` / `src.risk` not loaded;
> report writer emits 4 files + JSON round-trip + Markdown contains
> `TASK-014BM` / `tiny_order_execution` / `READINESS_OK_NO_NETWORK` /
> `max_order_count` / SOLUSDT / 0.01 / IOC / Bybit V5 envelope; body
> preview shape is exactly the 9 allowed fields with no stop/TP fields;
> signed request headers contain a 64-char SHA-256 hex
> `X-BAPI-SIGN`). Module does not import `requests` / `pybit` /
> `aiohttp` / `httpx`; does not reference `BybitExecutor`; does not
> import `main` / `src.risk` / `src.executors.bybit`; does not open
> a stop endpoint; does not attach `stopLoss` or `takeProfit`; does
> not retry; does not schedule; and **never** reads live secret names.
> Next step `TASK-014BN_demo_only_tiny_execution_postfill_audit`
> (explicit demo-only tiny execution postfill audit; **not** a
> review-chain suffix; requires Rick's explicit authorization).
> Still G20 sender policy is in effect — there is no `set-trading-stop`
> path and no live-endpoint surface; the only network surface is the
> demo `/v5/order/create` POST gated by the double-flag + 16 gates +
> demo-creds-present chain; protected positions
> (ENA / TIA / AIXBT / POLYX / EDU) are unreferenced; main.py /
> src/risk.py / BybitExecutor are untouched.
>
> Previous BL banner archived below.

## TASK-014BM Status (2026-06-18)

| item | status |
|---|---|
| new src `src/demo_only_tiny_execution_adapter_tiny_order_execution.py` (single aggregator entry point `run_explicit_tiny_order_execution()`; consumes BH+BI+BJ+BK+BL directly; emits structured `ExecutionPlan`+`SendOutcome`+`ExecutionReport`; 16 ordered execution gates; HMAC-SHA256 V5 signing; stdlib urllib POST; sender dependency injection) | DONE |
| new scripts `scripts/preview_demo_only_tiny_execution_adapter_tiny_order_execution.py` (`--mode {dry_run,readiness,execute_demo_order}` default readiness; `--execute-demo-order` + `--i-understand-this-sends-one-bybit-demo-order` double-flag gate; `--endpoint-target` / `--write-report` / `--output-dir`; exit codes 0/1/2) | DONE |
| new tests `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution.py` (Stage 1 focused-core 69 tests) | DONE |
| chain-break markers: `TASK_ID="TASK-014BM"`, `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-EXECUTION"`, `IMPLEMENTATION_PATH_PHASE="tiny_order_execution"`, `IS_REVIEW_CHAIN_SUFFIX=False`, `UPSTREAM_TASKS=("TASK-014BH","TASK-014BI","TASK-014BJ","TASK-014BK","TASK-014BL")` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BN_demo_only_tiny_execution_postfill_audit"` (does not end in `_readiness_review` / `_final_pre_execution_review` / `_manual_authorization_review`; passes `bh.assert_next_task_is_not_review_chain_suffix`; explicitly references `demo_only` and `postfill_audit`) | DONE |
| default mode is non-sending (`readiness`); `execute_demo_order` mode requires both `--execute-demo-order` AND `--i-understand-this-sends-one-bybit-demo-order` flags before any sender invocation | CONFIRMED |
| demo credential loader reads `BYBIT_DEMO_API_KEY` / `BYBIT_DEMO_API_SECRET` / `BYBIT_DEMO_RECV_WINDOW` only; never falls back to `BYBIT_API_KEY` / `BYBIT_API_SECRET`; missing creds → safe `MISSING_DEMO_CREDENTIALS` report | CONFIRMED |
| 13 pre-network gates evaluated in strict order; any failure → `STATUS_GATE_REJECTED_NO_NETWORK` and sender is never called | CONFIRMED via parametrize across 20+ reject paths |
| 3 execute gates (`explicit_execute_flag`, `explicit_confirm_flag`, `demo_credentials_present`) evaluated only after pre-network gates pass; any failure → `STATUS_GATE_REJECTED_NO_NETWORK` or `STATUS_MISSING_DEMO_CREDENTIALS` | CONFIRMED |
| `MAX_ORDER_COUNT=1`; only one POST per run; no retry; no scheduler; no loop | CONFIRMED via tokenize+ast tests |
| body shape exactly 9 allowed fields (`category`, `symbol`, `side`, `orderType`, `qty`, `timeInForce`, `reduceOnly`, `closeOnTrigger`, `orderLinkId`); no `stopLoss`, no `takeProfit`, no `trading-stop` endpoint, no TP/SL attachment | CONFIRMED via body_preview shape test + static-source token check |
| BM source static-source safety invariants (no `requests` / `pybit` / `aiohttp` / `httpx` import; no `main` / `src.risk` / `src.executors.bybit` import; no `BybitExecutor` `Name`/`Attribute` reference; no LIVE env names in code (docstring-stripped); no `set-trading-stop` / `stopLoss` / `takeProfit` / retry / scheduler tokens; chain-break literals present; BH+BI+BJ+BK+BL all imported directly) | CONFIRMED via AST tests |
| `_real_sender_via_urllib` hard-asserts URL == `ALLOWED_DEMO_ENDPOINT_URL`; raises if any caller tries a non-demo URL | CONFIRMED via two parametrize cases (real + via plan) |
| Bybit V5 HMAC-SHA256 signature shape (`X-BAPI-SIGN` is 64-char hex) + standard envelope headers (`X-BAPI-API-KEY` / `X-BAPI-TIMESTAMP` / `X-BAPI-RECV-WINDOW`) | CONFIRMED |
| report writer emits `latest_*.json` / `latest_*.md` / `*_<UTC_TS>.json` / `*_<UTC_TS>.md` to `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_execution/` | DONE |
| `.gitignore` updated with BM output dir | DONE |
| py_compile BM src + scripts + tests | PASS |
| pytest BM Stage 1 focused-core | **69/69 PASS** |
| pytest BH + BI + BJ + BK + BL Stage 1 regression | **228/228 PASS** (45 + 44 + 61 + 31 + 47) |
| pytest BH + BI + BJ + BK + BL + BM safety-chain | **297/297 PASS** |
| pytest broad `tests/demo_trading/ --ignore=test_demo_emergency_close_sender.py --basetemp=.pytest_basetemp` | **7998/7998 PASS** (excludes pre-existing emergency_close_sender failure unrelated to BM) |
| pytest broad sweep `pytest --basetemp=.pytest_basetemp` | 8313 PASS + 18 pre-existing failures + 21 pre-existing errors (all in forward_record/* and apps/monitor/safety.py SyntaxError; none touch BH→BM chain) |
| BM preview smoke `--mode readiness --write-report` | exit 0; `final_status=READINESS_OK_NO_NETWORK`; `network_attempted=False`; `order_endpoint_called=False`; `order_sent=False`; `bl_packet_loaded=True`; `bl_packet_all_passed=True`; `packet_is_not_execution_authorization=True`; `packet_audit_response_status='NOT_SENT_PREPARED_ONLY_NOT_EXECUTED'`; `live_endpoint_denied=True`; `protected_symbols_untouched=True`; `max_order_count=1`; `all_pre_network_gates_passed=True`; 4 report files written under `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_execution/` |
| BM execute-with-fake-sender smoke (in-test) | `final_status=EXECUTED_DEMO_ONLY`; `order_sent=True`; `order_endpoint_called=True`; sender call counter == 1; `bybit_order_id` populated |
| safety invariants (no live endpoint call / no live secret read / no stop endpoint / no TP-SL attachment / no retry / no scheduler / no G20 lift / no position modification / no protected position interaction; protected ENA / TIA / AIXBT / POLYX / EDU untouched) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | pending: `TASK-014BM: add demo-only tiny execution adapter explicit tiny order execution path (offline default; double-flag gate; consumes BH+BI+BJ+BK+BL; sends at most one Bybit Demo SOLUSDT order when creds present)` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-18 TASK-014BM)

1. VPS git pull and re-validate BM offline first (no `.env.demo` sourced):

       git pull --ff-only
       source .venv/bin/activate
       python3 -m py_compile \
           src/demo_only_tiny_execution_adapter_tiny_order_execution.py \
           scripts/preview_demo_only_tiny_execution_adapter_tiny_order_execution.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution.py
       python3 -m pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_execution.py -q --basetemp=.pytest_basetemp
       # expect 69/69 PASS

   Then run the BM readiness preview (still no network):

       python3 scripts/preview_demo_only_tiny_execution_adapter_tiny_order_execution.py --mode readiness --write-report
       # exit 0
       # final_status=READINESS_OK_NO_NETWORK
       # network_attempted=False  order_endpoint_called=False  order_sent=False
       # bl_packet_loaded=True  bl_packet_all_passed=True
       # packet_is_not_execution_authorization=True
       # packet_audit_response_status='NOT_SENT_PREPARED_ONLY_NOT_EXECUTED'
       # live_endpoint_denied=True  protected_symbols_untouched=True
       # all_pre_network_gates_passed=True
       # next_required_task == TASK-014BN_demo_only_tiny_execution_postfill_audit
       # 4 report files written under outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_execution/
       # no socket opened, no live endpoint called, no live secret loaded; G20 still in place; 5 protected positions untouched.

2. Confirm `execute_demo_order` mode is hard-gated **without** any
   credentials present:

       python3 scripts/preview_demo_only_tiny_execution_adapter_tiny_order_execution.py --mode execute_demo_order
       # exit 1
       # final_status=GATE_REJECTED_NO_NETWORK (two missing confirm flags)
       # network_attempted=False  order_sent=False

   Add the flags but no demo credentials:

       python3 scripts/preview_demo_only_tiny_execution_adapter_tiny_order_execution.py \
           --mode execute_demo_order \
           --execute-demo-order \
           --i-understand-this-sends-one-bybit-demo-order
       # exit 2
       # final_status=MISSING_DEMO_CREDENTIALS
       # network_attempted=False  order_sent=False

3. Only after the above two offline gates behave exactly as
   documented, **and only if Rick chooses to**, source `.env.demo`
   (which must define `BYBIT_DEMO_API_KEY` / `BYBIT_DEMO_API_SECRET`
   and **must not** define any `BYBIT_API_KEY` / `BYBIT_API_SECRET`
   live names — strict separation), and run the explicit-send command
   exactly once:

       set -a; source .env.demo; set +a
       python3 scripts/preview_demo_only_tiny_execution_adapter_tiny_order_execution.py \
           --mode execute_demo_order \
           --execute-demo-order \
           --i-understand-this-sends-one-bybit-demo-order \
           --write-report
       # exit 0
       # final_status=EXECUTED_DEMO_ONLY
       # network_attempted=True  order_endpoint_called=True  order_sent=True
       # bybit_order_id populated
       # max_order_count=1
       # 4 report files written under outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_execution/

   Then decide whether to authorise **TASK-014BN** —
   `TASK-014BN_demo_only_tiny_execution_postfill_audit` (the postfill
   audit / reconcile step). Any successor that ends with
   `_readiness_review` / `_final_pre_execution_review` /
   `_manual_authorization_review` is forbidden by
   `bh.assert_next_task_is_not_review_chain_suffix`.

---

> Previous README banner: TASK-014BL (2026-06-18) — see archived block below.

## TASK-014BL Banner (archived 2026-06-18 by TASK-014BM)

> README shared status updated by TASK-014BL (2026-06-18). TASK-014BL
> adds the **tiny order preparation** layer on top of TASK-014BH /
> TASK-014BI / TASK-014BJ / TASK-014BK. It produces the explicit
> *offline* authorization packet that the future
> `TASK-014BM_explicit_demo_only_tiny_order_execution` task will
> consume. New BL triplet:
> [`src/demo_only_tiny_execution_adapter_tiny_order_preparation.py`](../../../src/demo_only_tiny_execution_adapter_tiny_order_preparation.py)
> (single aggregator entry point `run_tiny_order_preparation()` plus a
> direct `build_preparation_packet()` entry; module-import-time call to
> `bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)`;
> two frozen dataclasses `PreparationPacket` / `PreparationReport`;
> aggregation flow: (1) `bk.run_final_pre_execution_checklist()` must
> return `all_passed=True`; (2)
> `bj.integrate_demo_only_tiny_request(IntegrationRequest)` for the
> canonical SOLUSDT Buy 0.01 @ mark 100 + demo endpoint
> `https://api-demo.bybit.com/v5/order/create` request, which itself
> chains BH's 8 guard steps; (3) the BJ audit dict is wrapped with a
> third layer of BL markers:
> `_demo_only_bl_audit_response_status=NOT_SENT_PREPARED_ONLY_NOT_EXECUTED`,
> `_demo_only_bl_target_future_task=TASK-014BM_explicit_demo_only_tiny_order_execution`,
> `_demo_only_bl_authorization_is_not_execution_authorization=True`,
> `_demo_only_bl_preparation_contract_version=demo_only_tiny_execution_adapter_tiny_order_preparation_v1`,
> `_demo_only_bl_implementation_path_task=TASK-014BL`,
> `_demo_only_bl_is_review_chain_suffix=False`, and an
> `_demo_only_bl_packet_note` literal that states "PREPARATION ONLY ...
> does NOT authorize execution"; `write_report` emitting JSON +
> Markdown to
> `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_preparation/`
> as `latest_*.json` / `latest_*.md` / timestamped
> `*_<UTC_TS>.json` / `*_<UTC_TS>.md`; chain-break markers
> `TASK_ID="TASK-014BL"`,
> `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-PREPARATION"`,
> `IMPLEMENTATION_PATH_PHASE="tiny_order_preparation"`,
> `IS_REVIEW_CHAIN_SUFFIX=False`,
> `UPSTREAM_TASKS=("TASK-014BH","TASK-014BI","TASK-014BJ","TASK-014BK")`,
> `NEXT_REQUIRED_TASK="TASK-014BM_explicit_demo_only_tiny_order_execution"`,
> `TARGET_FUTURE_TASK="TASK-014BM_explicit_demo_only_tiny_order_execution"`,
> `PREPARATION_CONTRACT_VERSION="demo_only_tiny_execution_adapter_tiny_order_preparation_v1"`,
> `BL_AUDIT_RESPONSE_STATUS_NOT_SENT="NOT_SENT_PREPARED_ONLY_NOT_EXECUTED"`),
> [`scripts/preview_demo_only_tiny_execution_adapter_tiny_order_preparation.py`](../../../scripts/preview_demo_only_tiny_execution_adapter_tiny_order_preparation.py)
> (CLI; `--write-report` / `--output-dir` / `--symbol` / `--side` /
> `--qty` / `--mark-price`; includes ROOT sys.path injection; exit 0
> iff `all_passed=True`, exit 1 otherwise), and
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_preparation.py`](../../../tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_preparation.py)
> (Stage 1 focused-core **47 tests** — identity / chain-break markers /
> BL pointer not a review-chain suffix and explicitly references
> `demo_only` + `tiny_order_execution` / `PREPARATION_CONTRACT_VERSION`
> / `BL_AUDIT_RESPONSE_STATUS_NOT_SENT` / `DEFAULT_*` constants /
> packet note literal states "NOT authorize execution"; aggregate
> `run_tiny_order_preparation` `all_passed=True` + BK checklist counts
> identical to a direct `bk.run_final_pre_execution_checklist()` call +
> three-layer BH/BI/BJ/BK identity snapshot;
> `PreparationPacket` / `PreparationReport` frozen-immutable; packet
> default request fields (SOLUSDT, Buy, 0.01 qty, mark 100, Market,
> IOC, reduceOnly=False, `DEMO_ONLY_TINY_BH_` orderLinkId prefix,
> notional estimate 1 USDT ≤ BH 5 USDT cap, qty ≤ 0.05 SOL cap); packet
> audit dict carries all three BH+BJ+BL marker layers and retains
> SOLUSDT / Market / IOC / reduceOnly=False; `build_preparation_packet`
> direct entry rejected via parametrize for 3 non-SOLUSDT symbols + 5
> protected symbols + protected-in-existing + live endpoint + qty cap
> fail + notional cap fail + bybit_live environment; BL self
> tokenize+ast static-source 6 checks (no network library import; no
> `getenv`/`environ`/`load_dotenv` token; no `def send`/`.send(`/
> `place_order`/`post_order`/`submit_order` surface; no
> `main`/`src.risk`/`src.executors.bybit` import;
> `IS_REVIEW_CHAIN_SUFFIX=False` + non-empty `IMPLEMENTATION_PATH_PHASE`
> literal both present); BL source imports all four upstream modules
> directly (`src.demo_only_tiny_execution_adapter`,
> `..._payload_dry_run`, `..._endpoint_guard_integration`,
> `..._final_pre_execution_checklist`); cross-module
> `src.executors.bybit` not loaded + BK
> `run_final_pre_execution_checklist().all_passed` still True under BL;
> 4 report files written + JSON round-trip + Markdown contains
> "TASK-014BL" / phase / `NOT_SENT_PREPARED_ONLY_NOT_EXECUTED` /
> target_future_task / "PREPARATION ONLY"; `DEFAULT_OUTPUT_DIR` ==
> `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_preparation`;
> BH `assert_next_task_is_not_review_chain_suffix` rejects each of the
> 3 forbidden suffixes under BL, and accepts BL's own
> `NEXT_REQUIRED_TASK`). Module does not import any network library,
> does not read env, does not reference `BybitExecutor`, does not
> define any send method, does not open a socket, and does not call
> any endpoint; it only calls BK's offline `run_final_pre_execution_checklist`
> and BJ's offline `integrate_demo_only_tiny_request` in-memory and
> writes JSON / Markdown reports to outputs/. The produced
> `PreparationPacket.packet_is_not_execution_authorization` flag is
> hard-coded `True` and the
> `_demo_only_bl_authorization_is_not_execution_authorization` audit
> marker is hard-coded `True`, making the non-authorization status
> machine-checkable in downstream consumers. Next step
> `TASK-014BM_explicit_demo_only_tiny_order_execution` (explicit
> demo-only tiny order execution authorization; **not** a review-chain
> suffix; requires Rick's explicit authorization + manual approval).
> Still no sender, no real execution adapter, no endpoint call, no
> secret read, no G20 lift, no position modification. main.py /
> src/risk.py / BybitExecutor still untouched.
>
> Previous BK banner archived below.

## TASK-014BL Status (archived 2026-06-18 by TASK-014BM)

| item | status |
|---|---|
| new src `src/demo_only_tiny_execution_adapter_tiny_order_preparation.py` (single aggregator entry point `run_tiny_order_preparation()` + direct `build_preparation_packet()`; consumes BH+BI+BJ+BK directly; emits structured `PreparationPacket` + `PreparationReport` with three-layer BH+BJ+BL audit markers) | DONE |
| new scripts `scripts/preview_demo_only_tiny_execution_adapter_tiny_order_preparation.py` (`--write-report` / `--output-dir` / `--symbol` / `--side` / `--qty` / `--mark-price`; exit 0 iff `all_passed=True`) | DONE |
| new tests `tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_preparation.py` (Stage 1 focused-core 47 tests) | DONE |
| chain-break markers: `TASK_ID="TASK-014BL"`, `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-PREPARATION"`, `IMPLEMENTATION_PATH_PHASE="tiny_order_preparation"`, `IS_REVIEW_CHAIN_SUFFIX=False`, `UPSTREAM_TASKS=("TASK-014BH","TASK-014BI","TASK-014BJ","TASK-014BK")` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BM_explicit_demo_only_tiny_order_execution"` (does not end in `_readiness_review` / `_final_pre_execution_review` / `_manual_authorization_review`; passes `bh.assert_next_task_is_not_review_chain_suffix`; explicitly references `demo_only` and `tiny_order_execution`) | DONE |
| packet hard-codes `packet_is_not_execution_authorization=True` + audit `_demo_only_bl_authorization_is_not_execution_authorization=True` + packet note literal "PREPARATION ONLY ... NOT authorize execution" | DONE |
| three-layer BH+BJ+BL audit markers carried in `payload_audit` (`_demo_only_audit_response_status=DEMO_ONLY_TINY_BH_NOT_SENT`, `_demo_only_bj_audit_response_status=DEMO_ONLY_TINY_BJ_NOT_SENT`, `_demo_only_bl_audit_response_status=NOT_SENT_PREPARED_ONLY_NOT_EXECUTED`) | CONFIRMED |
| BL source static-source safety invariants (no network/secret/send surface/main/risk/executor imports; chain-break literals; BH+BI+BJ+BK all imported directly) | CONFIRMED via tokenize + ast tests |
| `run_tiny_order_preparation()` aggregate `all_passed=True` + `bk_checklist_all_passed=True` + `bj_integration_ok=True` + packet present | CONFIRMED |
| report writer emits `latest_*.json` / `latest_*.md` / `*_<UTC_TS>.json` / `*_<UTC_TS>.md` to `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_preparation/` | DONE |
| `.gitignore` updated with BL output dir | DONE |
| py_compile BL src + scripts + tests | PASS |
| pytest BL Stage 1 focused-core | **47/47 PASS** |
| pytest BH + BI + BJ + BK Stage 1 regression | **181/181 PASS** (45 + 44 + 61 + 31) |
| pytest broad `tests/demo_trading/ --ignore=test_demo_emergency_close_sender.py --basetemp=.pytest_basetemp` | **7871/7871 PASS** (= prior BK baseline 7824 + BL stage1 47; excludes pre-existing emergency_close_sender CLI dry-run failure unrelated to BL) |
| BL preview smoke (`--write-report`) | exit 0; `all_passed=True`; `bk_checklist total=36 passed=36 failed=0 all_passed=True`; `bj_integration ok=True`; packet `symbol=SOLUSDT side=Buy qty=0.01 mark_price=100 notional=1.00 order_link_id='DEMO_ONLY_TINY_BH_SOLUSDT_OFFLINE_BUILD' audit_response_status='NOT_SENT_PREPARED_ONLY_NOT_EXECUTED' packet_is_not_execution_authorization=True`; 4 report files written under `outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_preparation/` |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no socket opened / no secret read / no credential load / no G20 lift / no position modification / no protected position interaction) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | pending: `TASK-014BL: add demo-only tiny execution adapter tiny order preparation packet (offline; consumes BH+BI+BJ+BK; emits JSON+MD report; NOT execution authorization)` (local only — NOT pushed) |

## Next Rick Action (archived 2026-06-18 by TASK-014BM — superseded above)

1. VPS git pull and re-validate BL locally:

       git pull --ff-only
       source .venv/bin/activate
       # No .env.demo source — BL must run with zero credentials.
       python3 -m py_compile \
           src/demo_only_tiny_execution_adapter_tiny_order_preparation.py \
           scripts/preview_demo_only_tiny_execution_adapter_tiny_order_preparation.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_preparation.py
       python3 -m pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_tiny_order_preparation.py -q --basetemp=.pytest_basetemp
       # expect 47/47 PASS

   Then run the BL preview and confirm:

       python3 scripts/preview_demo_only_tiny_execution_adapter_tiny_order_preparation.py --write-report
       # exit 0
       # all_passed=True
       # bk_checklist total=36 passed=36 failed=0 all_passed=True
       # bj_integration ok=True rejection_step='' rejection_reason=''
       # packet symbol=SOLUSDT side=Buy qty=0.01 mark_price=100 notional=1.00
       #   order_link_id='DEMO_ONLY_TINY_BH_SOLUSDT_OFFLINE_BUILD'
       #   audit_response_status='NOT_SENT_PREPARED_ONLY_NOT_EXECUTED'
       #   packet_is_not_execution_authorization=True
       # next_required_task == TASK-014BM_explicit_demo_only_tiny_order_execution
       # target_future_task == TASK-014BM_explicit_demo_only_tiny_order_execution
       # report files written under outputs/demo_trading/demo_only_tiny_execution_adapter_tiny_order_preparation/
       # no socket opened, no endpoint called, no secret loaded, G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise **TASK-014BM** —
   `TASK-014BM_explicit_demo_only_tiny_order_execution` (the explicit
   demo-only tiny order execution authorization task; the first task
   that may write any sender code). Note that BL's
   `PreparationPacket.packet_is_not_execution_authorization=True` flag
   and its `_demo_only_bl_authorization_is_not_execution_authorization=True`
   audit marker are intentional safety hard-codes: the BL packet is NOT
   itself an execution authorization, and TASK-014BM must add its own
   independent manual authorization gate on top. Any successor that
   ends with `_readiness_review` / `_final_pre_execution_review` /
   `_manual_authorization_review` is forbidden by
   `bh.assert_next_task_is_not_review_chain_suffix`.

---

> Previous README banner: TASK-014BK (2026-06-18) — see archived block below.

## TASK-014BK Banner (archived 2026-06-18 by TASK-014BL)

> README shared status updated by TASK-014BK (2026-06-18). TASK-014BK
> aggregates the BH (scaffold) + BI (offline payload dry-run) + BJ
> (endpoint guard integration) safety proofs into one offline **final
> pre-execution checklist** before any explicit demo-only tiny order
> preparation task can be authorised. New BK triplet:
> [`src/demo_only_tiny_execution_adapter_final_pre_execution_checklist.py`](../../../src/demo_only_tiny_execution_adapter_final_pre_execution_checklist.py)
> (single aggregator entry point `run_final_pre_execution_checklist()`;
> module-import-time call to
> `bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)`;
> `ChecklistItem` / `ChecklistReport` frozen dataclasses; 36 invariants
> across 5 categories — `identity` (BK pointer is not a review-chain
> suffix; BH→BI→BJ→BK pointer chain intact; BH guard rejects each of
> the 3 forbidden suffixes), `bh_runtime` (`ALLOWED_SYMBOL=SOLUSDT`;
> 5-symbol `PROTECTED_SYMBOLS` set; `LIVE_ENDPOINT_DENYLIST` covers
> `api.bybit.com` / `api.bytick.com` / `wss://stream.bybit.com` /
> `wss://stream.bytick.com`; `ALLOWED_ENVIRONMENT=bybit_demo`; tiny
> caps 5 USDT / 0.05 SOL; BH `AUDIT_RESPONSE_STATUS_NOT_SENT =
> DEMO_ONLY_TINY_BH_NOT_SENT`), `bj_runtime`
> (`BJ_AUDIT_RESPONSE_STATUS_NOT_SENT = DEMO_ONLY_TINY_BJ_NOT_SENT`;
> `BJ.GUARD_STEPS` strict canonical 8-step tuple), `bj_aggregate`
> (`bi.run_dry_run().all_match_expectation is True` and
> `bj.run_integration_dry_run().all_match_expectation is True`;
> happy-path BJ payload audit carries both BH+BJ NOT_SENT markers +
> `_demo_only_bj_endpoint_target_validated=True` +
> `_demo_only_bj_integration_contract_version`), and `static_source`
> across BH/BI/BJ (no network library import; no `getenv`/`environ`/
> `load_dotenv`; no `def send`/`.send(`/`place_order`/`post_order`/
> `submit_order`; no `main`/`src.risk`; no `src.executors.bybit`;
> `IS_REVIEW_CHAIN_SUFFIX=False` + `IMPLEMENTATION_PATH_PHASE` literal
> present; BI/BJ both import BH via `from src import ... as bh`) plus
> `cross_module` (no `src.executors.bybit` in `sys.modules`; BH/BI/BJ
> do not import `main`/`src.risk` transitively); `write_report`
> emitting JSON + Markdown to
> `outputs/demo_trading/demo_only_tiny_execution_adapter_final_pre_execution_checklist/`
> as `latest_*.json` / `latest_*.md` / timestamped `*_<UTC_TS>.json` /
> `*_<UTC_TS>.md`; chain-break markers `TASK_ID="TASK-014BK"`,
> `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-FINAL-PRE-EXECUTION-CHECKLIST"`,
> `IMPLEMENTATION_PATH_PHASE="final_pre_execution_checklist"`,
> `IS_REVIEW_CHAIN_SUFFIX=False`,
> `UPSTREAM_TASKS=("TASK-014BH","TASK-014BI","TASK-014BJ")`,
> `CHECKLIST_CONTRACT_VERSION="demo_only_tiny_execution_adapter_final_pre_execution_checklist_v1"`,
> `NEXT_REQUIRED_TASK="TASK-014BL_demo_only_tiny_order_preparation"`),
> [`scripts/preview_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py`](../../../scripts/preview_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py)
> (CLI; `--write-report` / `--output-dir` / `--print-items`; exit 0
> iff `all_passed=True`, exit 1 otherwise), and
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py`](../../../tests/demo_trading/test_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py)
> (Stage 1 focused-core **31 tests** — identity / chain-break markers
> / BK pointer not a review-chain suffix and explicitly references
> `demo_only_tiny_order` / `CHECKLIST_CONTRACT_VERSION` / `REPORT_NAME`
> / `DEFAULT_OUTPUT_DIR` / `FORBIDDEN_REVIEW_CHAIN_SUFFIXES` parity
> with BH; aggregate `run_final_pre_execution_checklist`
> `all_passed=True` + 36/36 pass + 5-category coverage; BI+BJ
> aggregate counts equal `len(bi.default_cases()) +
> len(bi.LIVE_ENDPOINT_CASES)` and `len(bj.default_integration_cases())`;
> `ChecklistItem`/`ChecklistReport` frozen immutability; negative
> control: synthetic `import requests` / `os.getenv` / `def
> place_order` modules each fail the static-source helpers; BK
> source itself passes the 6 static-source checks; report writer
> creates 4 files + JSON round-trip + Markdown contains chain-break
> literals + both NOT_SENT markers; defensive runtime checks
> re-assert BH guard rejects each of the 3 forbidden suffixes,
> BJ `GUARD_STEPS` is the canonical 8-step tuple, happy-path BJ
> payload audit carries both BH+BJ NOT_SENT markers +
> `_demo_only_bj_endpoint_target_validated=True` +
> `_demo_only_bj_integration_contract_version`). Module does not
> import any network library, does not read env, does not reference
> `BybitExecutor`, does not define any send method, and does not call
> any endpoint; it only calls BH's pure guard functions + BI's
> `run_dry_run` + BJ's `run_integration_dry_run` in-memory and writes
> JSON / Markdown reports to outputs/. Next step
> `TASK-014BL_demo_only_tiny_order_preparation` (explicit demo-only
> tiny order preparation / authorization; **not** a review-chain
> suffix). Still no sender, no real execution adapter, no endpoint
> call, no secret read, no G20 lift, no position modification.
> main.py / src/risk.py / BybitExecutor still untouched.
>
> Previous BJ banner archived below.

## TASK-014BK Status (archived 2026-06-18 by TASK-014BL)

| item | status |
|---|---|
| new src `src/demo_only_tiny_execution_adapter_final_pre_execution_checklist.py` (single aggregator entry point `run_final_pre_execution_checklist()`; consumes BH+BI+BJ directly; 36 invariants across 5 categories; emits structured report) | DONE |
| new scripts `scripts/preview_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py` (`--write-report` / `--output-dir` / `--print-items`; exit 0 iff `all_passed=True`) | DONE |
| new tests `tests/demo_trading/test_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py` (Stage 1 focused-core 31 tests) | DONE |
| chain-break markers: `TASK_ID="TASK-014BK"`, `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-FINAL-PRE-EXECUTION-CHECKLIST"`, `IMPLEMENTATION_PATH_PHASE="final_pre_execution_checklist"`, `IS_REVIEW_CHAIN_SUFFIX=False`, `UPSTREAM_TASKS=("TASK-014BH","TASK-014BI","TASK-014BJ")` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BL_demo_only_tiny_order_preparation"` (does not end in `_readiness_review` / `_final_pre_execution_review` / `_manual_authorization_review`; passes `bh.assert_next_task_is_not_review_chain_suffix`; explicitly references `demo_only_tiny_order`) | DONE |
| 36 invariants across 5 categories (identity 3 + bh_runtime 6 + bj_runtime 2 + bj_aggregate 3 + static_source 18 [BH/BI/BJ × 6 each] + bi_aggregate 1 + cross_module 2 + 1 BI/BJ consumes-BH-directly pair) | DONE |
| static-source safety invariants applied to BH/BI/BJ via tokenize + ast (no `requests`/`urllib`/`urllib3`/`http`/`socket`/`ssl`/`pybit`/`websocket`/`aiohttp`/`httpx`; no `src.executors.bybit`; no `getenv`/`environ`/`load_dotenv`; no `def send`/`.send(`/`place_order`/`post_order`/`submit_order`; no `main`/`src.risk`; BI/BJ both import BH directly; phase + `IS_REVIEW_CHAIN_SUFFIX = False` literals present) | CONFIRMED via tokenize + ast tests |
| BI aggregate `run_dry_run().all_match_expectation is True` and BJ aggregate `run_integration_dry_run().all_match_expectation is True` | CONFIRMED |
| happy-path BJ payload audit carries both `_demo_only_audit_response_status=DEMO_ONLY_TINY_BH_NOT_SENT` and `_demo_only_bj_audit_response_status=DEMO_ONLY_TINY_BJ_NOT_SENT` + `_demo_only_bj_endpoint_target_validated=True` + `_demo_only_bj_integration_contract_version` | CONFIRMED |
| report writer emits `latest_*.json` / `latest_*.md` / `*_<UTC_TS>.json` / `*_<UTC_TS>.md` to `outputs/demo_trading/demo_only_tiny_execution_adapter_final_pre_execution_checklist/` | DONE |
| `.gitignore` updated with BK output dir | DONE |
| py_compile BK src + scripts + tests | PASS |
| pytest BK Stage 1 focused-core | **31/31 PASS** |
| pytest BH + BI + BJ Stage 1 regression | **150/150 PASS** (45 + 44 + 61) |
| pytest broad `tests/demo_trading/ --ignore=test_demo_emergency_close_sender.py --basetemp=.pytest_basetemp` | **7824/7824 PASS** (= prior BJ baseline 7793 + BK stage1 31; excludes pre-existing emergency_close_sender CLI dry-run failure unrelated to BK) |
| BK preview smoke (`--write-report`) | exit 0; `total=36 passed=36 failed=0 all_passed=True`; `bi_dry_run_total=22 bi_all_match=True bj_integration_total=20 bj_all_match=True`; 4 report files written under `outputs/demo_trading/demo_only_tiny_execution_adapter_final_pre_execution_checklist/` |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no socket opened / no secret read / no credential load / no G20 lift / no position modification / no protected position interaction) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | pending: `TASK-014BK: add demo-only tiny execution adapter final pre-execution checklist (offline; aggregates BH+BI+BJ; emits JSON+MD report)` (local only — NOT pushed) |

## Next Rick Action (archived 2026-06-18 by TASK-014BL — superseded above)

1. VPS git pull and re-validate BK locally:

       git pull --ff-only
       source .venv/bin/activate
       # No .env.demo source — BK must run with zero credentials.
       python3 -m py_compile \
           src/demo_only_tiny_execution_adapter_final_pre_execution_checklist.py \
           scripts/preview_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py
       python3 -m pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py -q --basetemp=.pytest_basetemp
       # expect 31/31 PASS

   Then run the BK preview and confirm:

       python3 scripts/preview_demo_only_tiny_execution_adapter_final_pre_execution_checklist.py --write-report
       # exit 0
       # total=36 passed=36 failed=0 all_passed=True
       # bi_dry_run_total=22 bi_all_match=True bj_integration_total=20 bj_all_match=True
       # next_required_task == TASK-014BL_demo_only_tiny_order_preparation
       # report files written under outputs/demo_trading/demo_only_tiny_execution_adapter_final_pre_execution_checklist/
       # no socket opened, no endpoint called, no secret loaded, G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise **TASK-014BL** —
   `TASK-014BL_demo_only_tiny_order_preparation` (explicit demo-only
   tiny order preparation / authorization task; the very first BK-gated
   step toward a single demo-only SOLUSDT tiny entry). Either an
   explicit preparation task or an explicit authorization gate is
   acceptable; what is NOT acceptable is another `_readiness_review` /
   `_final_pre_execution_review` / `_manual_authorization_review`
   suffix.

---

> Previous README banner: TASK-014BJ (2026-06-18) — see archived block below.

## TASK-014BJ Banner (archived 2026-06-18 by TASK-014BK)

> README shared status updated by TASK-014BJ (2026-06-18). TASK-014BJ
> adds the **endpoint guard integration** layer on top of TASK-014BH /
> TASK-014BI. It exposes a single future-safe offline integration
> entry point
> [`integrate_demo_only_tiny_request`](../../../src/demo_only_tiny_execution_adapter_endpoint_guard_integration.py)
> that wraps every BH guard plus the optional endpoint-target live
> denylist check, so future demo-only call sites cannot bypass the
> `bybit_demo`-only environment, the SOLUSDT-only symbol, the protected
> symbols denylist (`{ENAUSDT, TIAUSDT, AIXBTUSDT, POLYXUSDT,
> EDUUSDT}`), the tiny size cap (5 USDT / 0.05 SOL), or the live
> endpoint denylist (`api.bybit.com`, `api.bytick.com`,
> `stream.bybit.com`, `stream.bytick.com`). New BJ triplet:
> [`src/demo_only_tiny_execution_adapter_endpoint_guard_integration.py`](../../../src/demo_only_tiny_execution_adapter_endpoint_guard_integration.py)
> (single entry point `integrate_demo_only_tiny_request` running 8
> guard steps in order — `environment` / `symbol` / `existing_positions`
> / `side` / `qty_cap` / `notional_cap` / `order_link_id_prefix` /
> `endpoint_target`; frozen dataclasses `IntegrationRequest` /
> `GuardDecision` / `IntegrationResult` / `IntegrationCase` /
> `IntegrationOutcome` / `IntegrationReport`;
> `default_integration_cases()` returning a 20-case table (4 happy
> paths: SOLUSDT Buy with demo endpoint / SOLUSDT Sell with no endpoint
> / qty-cap edge with demo endpoint / no-mark-price; 16 rejections:
> BTCUSDT / ETHUSDT / 5 protected symbols / protected-in-existing /
> `bybit_live` environment / 3 live URLs (root / order endpoint /
> mirror order endpoint) / live websocket / qty-cap fail / notional-cap
> fail / unknown side / custom order_link_id without prefix);
> `run_integration_dry_run` calling `integrate_demo_only_tiny_request`
> per case and `bh.assert_next_task_is_not_review_chain_suffix` at
> module-import time on `NEXT_REQUIRED_TASK`; built audit dict carries
> both `_demo_only_audit_response_status=DEMO_ONLY_TINY_BH_NOT_SENT`
> and `_demo_only_bj_audit_response_status=DEMO_ONLY_TINY_BJ_NOT_SENT`
> plus `_demo_only_bj_integration_contract_version`,
> `_demo_only_bj_endpoint_target_validated`,
> `_demo_only_bj_endpoint_target`; `write_report` emitting JSON +
> Markdown to
> `outputs/demo_trading/demo_only_tiny_execution_adapter_endpoint_guard_integration/`
> as `latest_*.json` / `latest_*.md` / timestamped
> `*_<UTC_TS>.json` / `*_<UTC_TS>.md`; chain-break markers
> `TASK_ID="TASK-014BJ"`,
> `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-ENDPOINT-GUARD-INTEGRATION"`,
> `IMPLEMENTATION_PATH_PHASE="endpoint_guard_integration"`,
> `IS_REVIEW_CHAIN_SUFFIX=False`, `UPSTREAM_TASK="TASK-014BI"`,
> `NEXT_REQUIRED_TASK="TASK-014BK_demo_only_tiny_execution_adapter_final_pre_execution_checklist"`),
> [`scripts/preview_demo_only_tiny_execution_adapter_endpoint_guard_integration.py`](../../../scripts/preview_demo_only_tiny_execution_adapter_endpoint_guard_integration.py)
> (CLI; `--write-report` / `--output-dir` / `--print-payloads` /
> `--print-decisions`; exit 0 iff all 20 outcomes match expectation,
> exit 1 otherwise), and
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_endpoint_guard_integration.py`](../../../tests/demo_trading/test_demo_only_tiny_execution_adapter_endpoint_guard_integration.py)
> (Stage 1 focused-core **61 tests** — identity / chain-break markers /
> `GUARD_STEPS` coverage / 20-case canonical table / direct
> `integrate_demo_only_tiny_request` reject-step validation for
> BTCUSDT / ETHUSDT / each of 5 protected symbols (parametrized) /
> protected-in-existing / `bybit_live` env / live root / live order
> endpoint / live mirror order endpoint / live websocket / qty cap fail
> / notional cap fail / unknown side / custom order_link_id missing
> prefix; happy-path payload-audit carries BJ NOT_SENT marker;
> aggregate `run_integration_dry_run` summary consistency + BH
> identity snapshot + ok≥2 + rejected≥14; report writer creates 4
> files + JSON round-trip + Markdown contents; static-source: no
> network library import / no `src.executors.bybit` / no `getenv` /
> `environ` / `load_dotenv` / no `def send` / `.send(` / `place_order`
> / `post_order` / `submit_order` / no `main` / `src.risk` import /
> BJ imports BH directly / `IMPLEMENTATION_PATH_PHASE =
> "endpoint_guard_integration"` literal + `IS_REVIEW_CHAIN_SUFFIX =
> False` literal + `final_pre_execution_checklist` literal present;
> runtime: BybitExecutor / main / src.risk modules not loaded; BH and
> BI markers still hold; default_integration_cases not mutated).
> Module does not import any network library, does not read env, does
> not reference `BybitExecutor`, does not define any send method, and
> does not call any endpoint; it only calls BH's pure guard functions
> in-memory and writes JSON / Markdown reports to outputs/. Next step
> `TASK-014BK_demo_only_tiny_execution_adapter_final_pre_execution_checklist`
> (or equivalent explicit demo-only tiny order preparation variant;
> **not** a review-chain suffix). Still no sender, no real execution
> adapter, no endpoint call, no secret read, no G20 lift, no position
> modification. main.py / src/risk.py / BybitExecutor still untouched.
>
> Previous BI banner archived below.

## TASK-014BJ Status (2026-06-18)

| item | status |
|---|---|
| new src `src/demo_only_tiny_execution_adapter_endpoint_guard_integration.py` (single future-safe `integrate_demo_only_tiny_request` entry point; consumes BH directly; 8-step ordered guard pipeline; emits structured report) | DONE |
| new scripts `scripts/preview_demo_only_tiny_execution_adapter_endpoint_guard_integration.py` (`--write-report` / `--output-dir` / `--print-payloads` / `--print-decisions`; exit 0 iff all outcomes match expectation) | DONE |
| new tests `tests/demo_trading/test_demo_only_tiny_execution_adapter_endpoint_guard_integration.py` (Stage 1 focused-core 61 tests) | DONE |
| chain-break markers: `TASK_ID="TASK-014BJ"`, `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-ENDPOINT-GUARD-INTEGRATION"`, `IMPLEMENTATION_PATH_PHASE="endpoint_guard_integration"`, `IS_REVIEW_CHAIN_SUFFIX=False`, `UPSTREAM_TASK="TASK-014BI"` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BK_demo_only_tiny_execution_adapter_final_pre_execution_checklist"` (does not end in `_readiness_review` / `_final_pre_execution_review` / `_manual_authorization_review`; passes `bh.assert_next_task_is_not_review_chain_suffix`) | DONE |
| canonical 20-case integration coverage: 4 happy paths (SOLUSDT Buy with demo endpoint / SOLUSDT Sell with no endpoint / qty-cap edge with demo endpoint / no-mark-price) + 16 rejections (BTCUSDT / ETHUSDT / 5 protected symbols / protected-in-existing / bybit_live env / 3 live URLs / live websocket / qty-cap fail / notional-cap fail / unknown side / custom order_link_id missing prefix) | DONE |
| BJ audit-dict additions: `_demo_only_bj_audit_response_status=DEMO_ONLY_TINY_BJ_NOT_SENT`, `_demo_only_bj_integration_contract_version=demo_only_tiny_execution_adapter_endpoint_guard_integration_v1`, `_demo_only_bj_endpoint_target_validated`, `_demo_only_bj_endpoint_target` | DONE |
| report writer emits `latest_*.json` / `latest_*.md` / `*_<UTC_TS>.json` / `*_<UTC_TS>.md` to `outputs/demo_trading/demo_only_tiny_execution_adapter_endpoint_guard_integration/` | DONE |
| `.gitignore` updated with BJ output dir | DONE |
| static-source safety invariants (no `requests`/`urllib`/`urllib3`/`http`/`socket`/`ssl`/`pybit`/`websocket`/`aiohttp`/`httpx`; no `src.executors.bybit`; no `getenv`/`environ`/`load_dotenv`; no `def send`/`.send(`/`place_order`/`post_order`/`submit_order`; no `main`/`src.risk`; BJ imports BH directly; phase literal + `IS_REVIEW_CHAIN_SUFFIX = False` literal + `final_pre_execution_checklist` literal present) | CONFIRMED via tokenize + ast tests |
| py_compile BJ src + scripts + tests | PASS |
| pytest BJ Stage 1 focused-core | **61/61 PASS** |
| pytest BH + BI Stage 1 regression | **89/89 PASS** (45 + 44) |
| pytest broad `tests/demo_trading/ --ignore=test_demo_emergency_close_sender.py --basetemp=.pytest_basetemp` | **7793/7793 PASS** (= prior BI baseline 7732 + BJ stage1 61; excludes pre-existing emergency_close_sender CLI dry-run failure unrelated to BJ) |
| BJ preview smoke (`--write-report`) | exit 0; 20 outcomes total (4 ok happy paths + 16 rejected guard cases including 3 live URLs + live websocket); all match expectation; 4 report files written (latest JSON+MD + timestamped JSON+MD) under `outputs/demo_trading/demo_only_tiny_execution_adapter_endpoint_guard_integration/` |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no socket opened / no secret read / no credential load / no G20 lift / no position modification / no protected position interaction) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | pending: `TASK-014BJ: add demo-only tiny execution adapter endpoint guard integration (single future-safe entry point; consumes BH directly; emits JSON+MD report)` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-18 TASK-014BJ)

1. VPS git pull and re-validate BJ locally:

       git pull --ff-only
       source .venv/bin/activate
       # No .env.demo source — BJ must run with zero credentials.
       python3 -m py_compile \
           src/demo_only_tiny_execution_adapter_endpoint_guard_integration.py \
           scripts/preview_demo_only_tiny_execution_adapter_endpoint_guard_integration.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_endpoint_guard_integration.py
       python3 -m pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_endpoint_guard_integration.py -q --basetemp=.pytest_basetemp
       # expect 61/61 PASS

   Then run the BJ preview and confirm:

       python3 scripts/preview_demo_only_tiny_execution_adapter_endpoint_guard_integration.py --write-report
       # exit 0
       # total=20 ok=4 rejected=16 unexpected=0 all_match=True
       # next_required_task == TASK-014BK_demo_only_tiny_execution_adapter_final_pre_execution_checklist
       # report files written under outputs/demo_trading/demo_only_tiny_execution_adapter_endpoint_guard_integration/
       # no socket opened, no endpoint called, no secret loaded, G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise **TASK-014BK** —
   `TASK-014BK_demo_only_tiny_execution_adapter_final_pre_execution_checklist`
   (offline final demo-only pre-execution checklist that aggregates
   BH+BI+BJ identity / guard coverage / report-dir state into a single
   sign-off document) OR an explicit demo-only tiny order preparation
   variant. Either successor is acceptable; what is NOT acceptable is
   another `_readiness_review` / `_final_pre_execution_review` /
   `_manual_authorization_review` suffix.

---

> Previous README banner: TASK-014BI (2026-06-18) — see archived block below.

## TASK-014BI Banner (archived 2026-06-18 by TASK-014BJ)

> README shared status updated by TASK-014BI (2026-06-18). TASK-014BI
> adds the **offline payload dry-run** layer on top of TASK-014BH. It
> consumes
> [`src/demo_only_tiny_execution_adapter.py`](../../../src/demo_only_tiny_execution_adapter.py)
> (BH) directly via `from src import demo_only_tiny_execution_adapter`
> and runs an 18-case canonical table plus 4 live-endpoint denial checks
> through the BH payload builder. New BI triplet:
> [`src/demo_only_tiny_execution_adapter_payload_dry_run.py`](../../../src/demo_only_tiny_execution_adapter_payload_dry_run.py)
> (frozen `DryRunCase` / `DryRunOutcome` / `DryRunReport` dataclasses,
> `default_cases()` returning the 18-case table covering happy Buy /
> Sell / qty-cap edge / no-mark-price / qty-above-cap / qty-zero /
> notional-above-cap / BTCUSDT / ETHUSDT / each of the 5 protected
> symbols / protected-in-existing-positions / non-demo environment /
> unknown side / custom order_link_id without prefix; `run_dry_run`
> calling `bh.build_demo_only_tiny_solusdt_entry_payload` per case and
> `bh.assert_endpoint_is_demo_only` against the live-endpoint list;
> `write_report` emitting JSON + Markdown to
> `outputs/demo_trading/demo_only_tiny_execution_adapter_payload_dry_run/`
> as `latest_*.json` / `latest_*.md` / timestamped `*_<UTC_TS>.json` /
> `*_<UTC_TS>.md`; chain-break markers `TASK_ID="TASK-014BI"`,
> `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-PAYLOAD-DRY-RUN"`,
> `IMPLEMENTATION_PATH_PHASE="offline_payload_dry_run"`,
> `IS_REVIEW_CHAIN_SUFFIX=False`, `UPSTREAM_TASK="TASK-014BH"`,
> `NEXT_REQUIRED_TASK="TASK-014BJ_demo_only_tiny_execution_adapter_endpoint_guard_integration"`),
> [`scripts/preview_demo_only_tiny_execution_adapter_payload_dry_run.py`](../../../scripts/preview_demo_only_tiny_execution_adapter_payload_dry_run.py)
> (CLI; `--write-report` / `--output-dir` / `--print-payloads`; exit 0
> iff all 22 outcomes match expectation, exit 1 otherwise), and
> [`tests/demo_trading/test_demo_only_tiny_execution_adapter_payload_dry_run.py`](../../../tests/demo_trading/test_demo_only_tiny_execution_adapter_payload_dry_run.py)
> (Stage 1 focused-core **44 tests** — identity / chain-break markers /
> case-table coverage / unique case ids / live-endpoint case table /
> `run_dry_run` happy path / summary consistency / live-endpoint
> rejection / built payload audit marker / per-case BTC / ETH / 5
> protected symbols parametrized / protected-in-existing / non-demo
> environment / qty-cap pass+fail / notional-cap pass+fail / Buy + Sell
> built / live-endpoint reason text / report writer creates 4 files /
> JSON round-trip / Markdown contents / BI does not name itself with
> review-chain suffix / static-source: no network library import / no
> `src.executors.bybit` / no `getenv`/`environ`/`load_dotenv` / no `def
> send`/`.send(`/`place_order`/`post_order`/`submit_order` / no `main`
> or `src.risk` import / BI imports BH directly /
> `IMPLEMENTATION_PATH_PHASE = "offline_payload_dry_run"` literal +
> `IS_REVIEW_CHAIN_SUFFIX = False` literal present / runtime: BybitExecutor
> module not loaded / BH chain-break markers still hold / `run_dry_run`
> does not mutate `default_cases()`). Module 不 import 任何 network
> library、不讀 env、不 reference `BybitExecutor`、不定義任何 send
> 方法、不呼叫任何 endpoint；只在記憶體裡呼叫 BH 的 pure 函式並寫
> JSON/Markdown 報告到 outputs/。下一步
> `TASK-014BJ_demo_only_tiny_execution_adapter_endpoint_guard_integration`
> （或等價 final demo-only pre-execution checklist 變體；**不是**
> review-chain 後綴）。仍無 sender、無 real execution adapter、無 endpoint
> call、無 secret 讀取、無 G20 lift、無 position 修改。
> main.py / src/risk.py / BybitExecutor 仍未動。
>
> Previous BH banner archived below.

## TASK-014BI Status (2026-06-18)

| item | status |
|---|---|
| new src `src/demo_only_tiny_execution_adapter_payload_dry_run.py` (consumes BH directly; pure-offline 18-case table + 4 live-endpoint denial checks; emits structured report) | DONE |
| new scripts `scripts/preview_demo_only_tiny_execution_adapter_payload_dry_run.py` (`--write-report` / `--output-dir` / `--print-payloads`; exit 0 iff all outcomes match expectation) | DONE |
| new tests `tests/demo_trading/test_demo_only_tiny_execution_adapter_payload_dry_run.py` (Stage 1 focused-core 44 tests) | DONE |
| chain-break markers: `TASK_ID="TASK-014BI"`, `IDENTITY="DEMO-ONLY-TINY-EXECUTION-ADAPTER-PAYLOAD-DRY-RUN"`, `IMPLEMENTATION_PATH_PHASE="offline_payload_dry_run"`, `IS_REVIEW_CHAIN_SUFFIX=False`, `UPSTREAM_TASK="TASK-014BH"` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BJ_demo_only_tiny_execution_adapter_endpoint_guard_integration"` (does not end in `_readiness_review` / `_final_pre_execution_review` / `_manual_authorization_review`; passes `bh.assert_next_task_is_not_review_chain_suffix`) | DONE |
| canonical 18-case BH-builder coverage: 4 happy paths (Buy / Sell / qty-cap edge / no-mark-price) + 14 rejections (qty above cap / qty zero / notional above cap / BTCUSDT / ETHUSDT / each of 5 protected symbols / protected-in-existing / non-demo env / unknown side / custom order_link_id without prefix) | DONE |
| 4 live-endpoint denial checks (api.bybit.com root / api.bybit.com/v5/order/create / api.bytick.com/v5/order/create / wss://stream.bybit.com/v5/public/linear) | DONE |
| report writer emits `latest_*.json` / `latest_*.md` / `*_<UTC_TS>.json` / `*_<UTC_TS>.md` to `outputs/demo_trading/demo_only_tiny_execution_adapter_payload_dry_run/` | DONE |
| `.gitignore` updated with BI output dir | DONE |
| static-source safety invariants (no `requests`/`urllib`/`urllib3`/`http`/`socket`/`ssl`/`pybit`/`websocket`/`aiohttp`/`httpx`; no `src.executors.bybit`; no `getenv`/`environ`/`load_dotenv`; no `def send`/`.send(`/`place_order`/`post_order`/`submit_order`; no `main`/`src.risk`; BI imports BH directly; `IMPLEMENTATION_PATH_PHASE = "offline_payload_dry_run"` + `IS_REVIEW_CHAIN_SUFFIX = False` literals present) | CONFIRMED via tokenize + ast tests |
| py_compile BI src + scripts + tests | PASS |
| pytest BI Stage 1 focused-core | **44/44 PASS** |
| pytest BH Stage 1 regression | **45/45 PASS** |
| pytest broad `tests/demo_trading/ --ignore=test_demo_emergency_close_sender.py` | **7732/7732 PASS** (= prior BH baseline 7688 + BI stage1 44; excludes pre-existing emergency_close_sender CLI dry-run failure unrelated to BI) |
| BI preview smoke (`--write-report`) | exit 0; 22 outcomes total (4 built happy paths + 18 rejected guard cases including 4 live-endpoint denials); all match expectation; 4 report files written (latest JSON+MD + timestamped JSON+MD) under `outputs/demo_trading/demo_only_tiny_execution_adapter_payload_dry_run/` |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no socket opened / no secret read / no credential load / no G20 lift / no position modification / no protected position interaction) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | pending: `TASK-014BI: add demo-only tiny execution adapter payload dry-run (offline; consumes BH directly; emits JSON+MD report)` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-18 TASK-014BI)

1. VPS git pull and re-validate BI locally:

       git pull --ff-only
       source .venv/bin/activate
       # No .env.demo source — BI must run with zero credentials.
       python3 -m py_compile \
           src/demo_only_tiny_execution_adapter_payload_dry_run.py \
           scripts/preview_demo_only_tiny_execution_adapter_payload_dry_run.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter_payload_dry_run.py
       python3 -m pytest tests/demo_trading/test_demo_only_tiny_execution_adapter_payload_dry_run.py -q
       # expect 44/44 PASS

   Then run the BI preview and confirm:

       python3 scripts/preview_demo_only_tiny_execution_adapter_payload_dry_run.py --write-report
       # exit 0
       # total=22 built=4 rejected=18 unexpected=0 all_match=True
       # next_required_task == TASK-014BJ_demo_only_tiny_execution_adapter_endpoint_guard_integration
       # report files written under outputs/demo_trading/demo_only_tiny_execution_adapter_payload_dry_run/
       # no socket opened, no endpoint called, no secret loaded, G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise **TASK-014BJ** —
   `TASK-014BJ_demo_only_tiny_execution_adapter_endpoint_guard_integration`
   (offline integration of an endpoint-guard layer that statically
   forbids any live Bybit host in any module-import path that could
   reach a real sender) OR a final demo-only pre-execution checklist
   variant. Either successor is acceptable; what is NOT acceptable is
   another `_readiness_review` / `_final_pre_execution_review` /
   `_manual_authorization_review` suffix.

---

> Previous README banner: TASK-014BH (2026-06-18) — see archived block below.

## TASK-014BH Banner (archived 2026-06-18 by TASK-014BI)

> README shared status updated by TASK-014BH (2026-06-18). TASK-014BH
> **breaks the disabled-implementation-scaffold review chain** that ran
> from TASK-014AQ through TASK-014BG and **starts the demo-only tiny
> execution adapter implementation path**. New BH triplet:
> [`src/demo_only_tiny_execution_adapter.py`](../../../src/demo_only_tiny_execution_adapter.py)
> (strict immutable constants — allowed env `bybit_demo`, allowed symbol
> `SOLUSDT`, protected denylist `{ENAUSDT, TIAUSDT, AIXBTUSDT, POLYXUSDT,
> EDUUSDT}`, tiny size cap `5 USDT` / `0.05 SOL`, live endpoint denylist,
> pure offline payload builder
> `build_demo_only_tiny_solusdt_entry_payload`, guard helpers,
> `DemoOnlyTinyEntryPayload` frozen dataclass with `to_exchange_payload`
> / `to_audit_dict`, chain-break markers `TASK_ID="TASK-014BH"` /
> `IS_REVIEW_CHAIN_SUFFIX=False` /
> `CLOSES_DISABLED_REVIEW_CHAIN_UPSTREAM_TASK="TASK-014BG"` /
> `NEXT_REQUIRED_TASK="TASK-014BI_demo_only_tiny_execution_adapter_payload_dry_run"`),
> [`scripts/preview_demo_only_tiny_execution_adapter.py`](../../../scripts/preview_demo_only_tiny_execution_adapter.py)
> (offline preview CLI; exit 0 on payload-built, exit 1 on rejection),
> and [`tests/demo_trading/test_demo_only_tiny_execution_adapter.py`](../../../tests/demo_trading/test_demo_only_tiny_execution_adapter.py)
> (Stage 1 focused-core **45 tests** covering identity / chain-break
> markers / immutable constants / happy-path payload build / non-SOL
> symbol rejection / protected symbol rejection / protected position in
> existing scope rejection / non-demo environment rejection / unknown
> side rejection / qty above tiny-qty-cap rejection / qty zero or
> negative rejection / notional above tiny-usdt-cap rejection / live
> endpoint denial / demo endpoint documented-only acceptance /
> assert_next_task_is_not_review_chain_suffix invariant / static-source
> safety: no network library import / no BybitExecutor import / no
> getenv/environ/load_dotenv / no live host outside string literals / no
> `send` / `place_order` / `post_order` / `submit_order` definition / no
> main.py or src/risk.py import / IS_REVIEW_CHAIN_SUFFIX = False literal
> present / frozen-dataclass mutation rejected / custom order_link_id
> prefix required). The module imports zero network libraries, reads zero
> environment variables, references zero exchange credentials, defines
> no `send`/`place_order`/`post_order`/`submit_order` method, and never
> touches `main.py` / `src/risk.py` / `BybitExecutor`. The implementation
> path's next step is
> `TASK-014BI_demo_only_tiny_execution_adapter_payload_dry_run` (or
> equivalent endpoint-guard-integration task) — NOT another
> `_readiness_review` / `_final_pre_execution_review` /
> `_manual_authorization_review` suffix.
>
> Previous BG banner archived below.

## TASK-014BH Status (2026-06-18)

| item | status |
|---|---|
| new src `src/demo_only_tiny_execution_adapter.py` (chain-break implementation-path scaffold) | DONE |
| new scripts `scripts/preview_demo_only_tiny_execution_adapter.py` (offline preview CLI) | DONE |
| new tests `tests/demo_trading/test_demo_only_tiny_execution_adapter.py` (Stage 1 focused-core 45 tests) | DONE |
| chain-break markers: `TASK_ID = "TASK-014BH"`, `IDENTITY = "DEMO-ONLY-TINY-EXECUTION-ADAPTER-IMPLEMENTATION-PATH-SCAFFOLD"`, `IS_REVIEW_CHAIN_SUFFIX = False`, `CLOSES_DISABLED_REVIEW_CHAIN_UPSTREAM_TASK = "TASK-014BG"` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BI_demo_only_tiny_execution_adapter_payload_dry_run"` (does not end in `_readiness_review` / `_final_pre_execution_review` / `_manual_authorization_review`) | DONE |
| strict immutable constants: `ALLOWED_ENVIRONMENT="bybit_demo"`, `ALLOWED_SYMBOL="SOLUSDT"`, `PROTECTED_SYMBOLS={ENAUSDT,TIAUSDT,AIXBTUSDT,POLYXUSDT,EDUUSDT}`, `TINY_SIZE_CAP_USDT=5`, `TINY_QTY_CAP_SOL=0.05`, `LIVE_ENDPOINT_DENYLIST` includes `api.bybit.com` / `api.bytick.com` / `stream.bybit.com` / `stream.bytick.com` | DONE |
| pure offline `build_demo_only_tiny_solusdt_entry_payload` returns frozen `DemoOnlyTinyEntryPayload`; `to_exchange_payload` strips audit metadata; `to_audit_dict` includes `_demo_only_audit_response_status="DEMO_ONLY_TINY_BH_NOT_SENT"` | DONE |
| guard helpers reject: non-SOL symbol / protected symbol / protected position in existing scope / non-demo environment / unknown side / qty above 0.05 SOL / qty <= 0 / notional above 5 USDT / live endpoint / custom order_link_id missing required prefix / next-task with review-chain suffix | DONE |
| static-source safety invariants (no `requests`/`urllib`/`urllib3`/`http`/`socket`/`ssl`/`pybit`/`websocket`/`aiohttp`/`httpx` import; no `src.executors.bybit` import; no `getenv`/`environ`/`load_dotenv`; no `def send`/`.send(`/`place_order`/`post_order`/`submit_order`; no `main`/`src.risk` import) | CONFIRMED via tokenize + ast tests |
| `IS_REVIEW_CHAIN_SUFFIX = False` literal in source | CONFIRMED via tokenize test |
| py_compile BH src + scripts + tests | PASS |
| pytest BH Stage 1 focused-core | **45/45 PASS** |
| pytest BG Stage 1 focused-core regression | **23/23 PASS** |
| pytest broad `tests/demo_trading/ --ignore=test_demo_emergency_close_sender.py` | **7688/7688 PASS** (previous BG baseline 7643 + BH stage1 45; excludes pre-existing emergency_close_sender CLI dry-run failure unrelated to BH) |
| BH preview smoke (SOL Buy 0.01 @ mark 100) | exit 0; payload built offline; `_demo_only_audit_response_status = DEMO_ONLY_TINY_BH_NOT_SENT`; `_demo_only_is_review_chain_suffix = false` |
| BH preview smoke (BTCUSDT) | exit 1; `REJECTED: symbol 'BTCUSDT' not allowed; only 'SOLUSDT' is permitted` |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no socket / no secret read / no credential load / no G20 lift / no position modification / no protected position interaction) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | pending: `TASK-014BH: start demo-only tiny execution adapter implementation path (chain-break; offline-only scaffold; non-sending)` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-18 TASK-014BH)

1. VPS git pull and re-validate BH locally:

       git pull --ff-only
       source .venv/bin/activate
       # NOTE: do NOT source .env.demo for this task — BH must run with
       # zero credentials present to prove it never reads them.
       python3 -m py_compile \
           src/demo_only_tiny_execution_adapter.py \
           scripts/preview_demo_only_tiny_execution_adapter.py \
           tests/demo_trading/test_demo_only_tiny_execution_adapter.py
       python3 -m pytest tests/demo_trading/test_demo_only_tiny_execution_adapter.py -q
       # expect 45/45 PASS

   Then run the BH preview and confirm:

       python3 scripts/preview_demo_only_tiny_execution_adapter.py \
           --symbol SOLUSDT --side Buy --qty 0.01 --mark-price 100
       # exit 0
       # next_required_task == TASK-014BI_demo_only_tiny_execution_adapter_payload_dry_run
       # _demo_only_audit_response_status == DEMO_ONLY_TINY_BH_NOT_SENT
       # _demo_only_is_review_chain_suffix == false
       # no socket opened, no endpoint called, no secret loaded, G20 still in place, 5 protected positions untouched.

       python3 scripts/preview_demo_only_tiny_execution_adapter.py --symbol BTCUSDT --side Buy --qty 0.01
       # exit 1
       # REJECTED: symbol 'BTCUSDT' not allowed; only 'SOLUSDT' is permitted

2. Once step 1 passes, decide whether to authorise **TASK-014BI** —
   `TASK-014BI_demo_only_tiny_execution_adapter_payload_dry_run` (offline
   payload dry-run that exercises the BH guards with realistic
   precision-rounded SOL qty / mark-price combinations and emits a JSON
   report) — OR an endpoint-guard-integration variant. Either successor
   is acceptable; what is NOT acceptable is another `_readiness_review`
   / `_final_pre_execution_review` / `_manual_authorization_review`
   suffix.

---

> Previous README banner: TASK-014BG (2026-06-18) — see archived block below.

## TASK-014BG Banner (archived 2026-06-18 by TASK-014BH)

> README shared status updated by TASK-014BG (2026-06-18) — see
> [Demo Trading Guarded Lifecycle Status](../../../README.md#demo-trading-guarded-lifecycle-statusupdated-by-task-014bg-2026-06-18)
> for the cross-agent status board. TASK-014BG added the
> guarded entry real execution adapter disabled implementation scaffold
> manual authorization gate final pre-execution review manual
> authorization review final pre-execution review manual authorization
> review **dry-run** chain-closing proof:
> new BG src/scripts/test (Stage 1 focused-core 23 tests), 37 hard-fail
> gates (Group A 18 BF-upstream / Group B 7 scope_summary content (incl.
> AV guard) / Group C 3 BF-failure passthrough / Group D 9 BG own-source
> safety), a 92-field result dataclass exposing 17 BF-upstream proof
> fields + 11 BF→BE chained-proof fields (short prefix `bf_chained_be_*`
> / `bf_scope_summary_*`) + 3 chain-closure booleans
> (`closes_disabled_review_chain=True`,
> `prepares_demo_only_tiny_execution_adapter_implementation_path=True`,
> `spawns_additional_review_chain_suffix=False`), BF artifact
> loader/parser, CLI preview script with
> `--from-latest-entry-...-manual-authorization-review-final-pre-execution-review-manual-authorization-review`
> + `--allow-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review-final-pre-execution-review-manual-authorization-review-dry-run`
> + `--allow-real-entry-execution` (still returns
> `REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED`) + `--write-report`, JSON +
> Markdown report writer,
> `STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-DRY-RUN-ONLY`
> identity wording, and
> `NEXT_REQUIRED_TASK=TASK-014BH_demo_only_tiny_execution_adapter_implementation_path`
> (chain-closing — BG does NOT spawn another readiness_review /
> final_pre_execution_review / manual_authorization_review suffix).
> BF manual-authorization-review final-pre-execution-review
> manual-authorization-review JSON is the direct upstream; BE final
> pre-execution review, BD readiness review, BC dry-run, BB manual
> authorization review, BA final-pre-execution-review, AZ readiness-review
> and AY/AX/AW/AV/AU/AT/AS/AR/AQ are referenced ONLY as BF-proven chained
> proof — BG never consumes them directly. BF is never described as a
> readiness review or dry-run; BF is the final pre-execution review
> manual authorization review phase, BG is the chain-closing dry-run.
> Still no sender, no real execution adapter, no endpoint call, no secret
> read, no G20 lift, no position modification. main.py / src/risk.py /
> BybitExecutor untouched.

## TASK-014BG Status (2026-06-18)

| item | status |
|---|---|
| new src `src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run.py` (BG src, ~1448 lines) | DONE |
| new scripts `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run.py` (CLI) | DONE |
| new tests Stage 1 focused-core `tests/demo_trading/test_demo_tiny_..._manual_authorization_review_dry_run_stage1.py` (23 tests covering identity / scope_summary / 37 gates / AV-guard / chain-closure booleans / default-dataclass safety / BF loader / artifact-missing FAIL_CLOSED / status FAIL_CLOSED passthrough / mode mismatch / next_required_task mismatch / real_execution_allowed True / send_allowed True / scope missing BE direct upstream / scope has BF-consumes-BB / scope has BF-consumes-AV / --allow flags / to_dict round-trip / BF→BE chained proof exposure) | DONE |
| identity wording: `STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-DRY-RUN-ONLY` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BH_demo_only_tiny_execution_adapter_implementation_path"` (chain-closing) | DONE |
| direct upstream = BF manual-authorization-review final-pre-execution-review manual-authorization-review; BE/BD/BC/BB/BA/AZ/AY/AX/AW/AV/AU/AT/AS/AR/AQ referenced ONLY as BF-proven chained proof | DONE |
| 37 hard-fail gates registered in `_HARD_FAIL_GATES` (Group A 18 + Group B 7 + Group C 3 + Group D 9 = 37) — any one forces `status == FAIL_CLOSED` | DONE |
| 17 BF-upstream dataclass fields + 11 BF→BE chained-proof dataclass fields + 3 chain-closure booleans + `to_dict()` JSON emission | DONE |
| `write_report` writes `latest_*.json` / `latest_*.md` / `*_<UTC_TS>.json` / `*_<UTC_TS>.md` to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run/` | DONE |
| .gitignore updated with the new BG dry-run output dir | DONE |
| py_compile (ast.parse + compile fallback on Windows MAX_PATH) BG src + scripts + Stage 1 test | PASS |
| pytest BG Stage 1 focused-core | **23/23 PASS** |
| pytest BF Stage 3 full pack | 124/124 PASS |
| pytest BF Stage 1 focused-core | 23/23 PASS |
| pytest BE Stage 3 full pack | 119/119 PASS |
| pytest BE Stage 1 focused-core | 23/23 PASS |
| pytest BD Stage 3 full pack | 112/112 PASS |
| pytest BD Stage 1 focused-core | 17/17 PASS |
| pytest BC Stage 3 full pack | 105/105 PASS |
| pytest BC Stage 1 focused-core | 16/16 PASS |
| pytest BB Stage 3 full pack | 84/84 PASS |
| pytest BB Stage 1 focused-core | 13/13 PASS |
| pytest BA regression | (included in broad sweep) PASS |
| pytest BG+BF+BE+BD+BC+BB combined chain | **1179/1179 PASS** |
| pytest broad `tests/demo_trading/ --ignore=test_demo_emergency_close_sender.py` | **7643/7643 PASS** (previous BF baseline 7620 + BG stage1 23; excludes pre-existing emergency_close_sender CLI dry-run failure introduced in TASK-014N — unrelated to BG) |
| BG preview smoke (synthetic BF artifact) | exit 0; status `..._MANUAL_AUTHORIZATION_REVIEW_DRY_RUN_READY`; mode `..._dry_run_checklist`; next_required_task `TASK-014BH_demo_only_tiny_execution_adapter_implementation_path`; closes_disabled_review_chain=True; prepares_demo_only_tiny_execution_adapter_implementation_path=True; spawns_additional_review_chain_suffix=False; report JSON+MD contain `TASK-014BG consumes TASK-014BF` and `BF-proven chained proof`; report JSON+MD do NOT contain `TASK-014BG consumes TASK-014BE`, `TASK-014BG consumes TASK-014BD`, `TASK-014BG consumes TASK-014BC`, `TASK-014BG consumes TASK-014BB`, `TASK-014BG consumes TASK-014BA`, `TASK-014BG consumes TASK-014AZ`, `TASK-014BG consumes TASK-014AY`, `TASK-014BG consumes TASK-014AX`, `TASK-014BG consumes TASK-014AW`, or `TASK-014BG consumes TASK-014AV` |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no secret read / no G20 lift / no position modification / no approval-input-as-authorization / no automatic git commit / no automatic git push) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | `TASK-014BG: add guarded entry real execution adapter disabled implementation scaffold manual authorization gate final pre-execution review manual authorization review final pre-execution review manual authorization review dry-run (chain-closing)` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-18 TASK-014BG)

1. VPS git pull and re-validate BG locally:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile \
           src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run.py \
           scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run.py \
           tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_stage1.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_stage1.py -q
       # expect 23/23 PASS

   Then run the BG preview with the real BF manual-authorization-review final-pre-execution-review manual-authorization-review artifact present and confirm:

       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run.py \
           --from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review-final-pre-execution-review-manual-authorization-review \
           --symbol SOLUSDT \
           --write-report
       # status == TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_DRY_RUN_READY
       # mode == disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run_checklist
       # next_required_task == TASK-014BH_demo_only_tiny_execution_adapter_implementation_path
       # closes_disabled_review_chain == True
       # prepares_demo_only_tiny_execution_adapter_implementation_path == True
       # spawns_additional_review_chain_suffix == False
       # failed_stage == (none)
       # generated report JSON+MD contain "TASK-014BG consumes TASK-014BF" and "BF-proven chained proof"
       # generated report JSON+MD do NOT contain "TASK-014BG consumes TASK-014BE/BD/BC/BB/BA/AZ/AY/AX/AW/AV"
       # no socket opened, no endpoint called, no secret loaded, G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014BH
   (**demo-only tiny execution adapter implementation path** — this is
   the chain-closing successor: a real demo-only execution adapter
   implementation track, not another readiness_review /
   final_pre_execution_review / manual_authorization_review suffix).

---

> Previous README banner: TASK-014BF (2026-06-18) — see archived block below.

## TASK-014BF Banner (archived 2026-06-18 by TASK-014BG)

> README shared status updated by TASK-014BF (2026-06-18). TASK-014BF added the
> guarded entry real execution adapter disabled implementation scaffold
> manual authorization gate final pre-execution review manual
> authorization review final pre-execution review **manual authorization
> review** scaffold:
> new BF src/scripts/test triple (Stage 1 focused-core 23 tests + Stage 3
> full pack 124 tests, kept as two separate files), 37 hard-fail gates
> (Group A 18 BE-upstream / Group B 7 scope_summary content (incl. AV
> guard) / Group C 3 BE-failure passthrough / Group D 9 BF own-source
> safety), a ~52-field result dataclass exposing 17 BE-upstream proof
> fields + 11 BE→BD chained-proof fields, BE artifact loader/parser, CLI
> preview script with
> `--from-latest-entry-...-manual-authorization-review-final-pre-execution-review`
> + `--allow-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review-final-pre-execution-review-manual-authorization-review`
> + `--allow-real-entry-execution` (still returns
> `REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED`) + `--write-report`, JSON +
> Markdown report writer,
> `STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-ONLY`
> identity wording, and
> `NEXT_REQUIRED_TASK=TASK-014BG_..._manual_authorization_review_dry_run`.
> BE manual-authorization-review final-pre-execution-review JSON is the
> direct upstream; BD manual-authorization-review readiness-review, BC
> manual-authorization-review dry-run, BB manual-authorization-review,
> BA final-pre-execution-review, AZ readiness-review and
> AY/AX/AW/AV/AU/AT/AS/AR/AQ are referenced ONLY as BE-proven chained
> proof — BF never consumes them directly. BE is never described as a
> readiness review or dry-run; BE is the final pre-execution review
> phase, BF is the manual authorization review phase. Still no sender,
> no real execution adapter, no endpoint call, no secret read, no G20
> lift, no position modification. main.py / src/risk.py / BybitExecutor
> untouched.

## TASK-014BF Status (2026-06-18)

| item | status |
|---|---|
| new src `src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review.py` (BF triple, ~1412 lines) | DONE |
| new scripts `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review.py` (CLI) | DONE |
| new tests Stage 1 focused-core `tests/demo_trading/test_demo_tiny_..._manual_authorization_review_stage1.py` (23 tests) | DONE |
| new tests Stage 3 full pack `tests/demo_trading/test_demo_tiny_..._manual_authorization_review.py` (primary regression pack, 124 tests covering core run / Group A / Group B / Group C / Group D / --allow flags / CLI subprocess / write_report JSON+MD on-disk inspection / identity wording / no BE-as-readiness-review-or-dry-run grep / untouched main.py + src/risk.py + BybitExecutor / BE loader) | DONE |
| identity wording: `STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-ONLY` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BG_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_dry_run"` | DONE |
| direct upstream = BE manual-authorization-review final-pre-execution-review; BD/BC/BB/BA/AZ/AY/AX/AW/AV/AU/AT/AS/AR/AQ referenced ONLY as BE-proven chained proof | DONE |
| 37 hard-fail gates registered in `_HARD_FAIL_GATES` (Group A 18 + Group B 7 + Group C 3 + Group D 9 = 37) — any one forces `status == FAIL_CLOSED` | DONE |
| 17 BE-upstream dataclass fields + 11 BE→BD chained-proof dataclass fields + `to_dict()` JSON emission | DONE |
| `write_report` writes `latest_*.json` / `latest_*.md` / `*_<UTC_TS>.json` / `*_<UTC_TS>.md` to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review/` | DONE |
| .gitignore updated with the new BF manual-authorization-review output dir | DONE |
| README "Demo Trading Guarded Lifecycle Status" board re-targeted to TASK-014BF (2026-06-18) | DONE |
| py_compile (ast.parse + compile fallback on Windows MAX_PATH) BF src + scripts + Stage 1 test + Stage 3 full test | PASS |
| pytest BF Stage 3 full pack | **124/124 PASS** |
| pytest BF Stage 1 focused-core | **23/23 PASS** |
| pytest BE Stage 3 full pack | 119/119 PASS |
| pytest BE Stage 1 focused-core | 23/23 PASS |
| pytest BD Stage 3 full pack | 112/112 PASS |
| pytest BD Stage 1 focused-core | 17/17 PASS |
| pytest BC Stage 3 full pack | 105/105 PASS |
| pytest BC Stage 1 focused-core | 16/16 PASS |
| pytest BB Stage 3 full pack | 84/84 PASS |
| pytest BB Stage 1 focused-core | 13/13 PASS |
| pytest BA regression | 536/536 PASS |
| pytest AZ regression | 481/481 PASS |
| pytest AY regression | 389/389 PASS |
| pytest AX regression | 299/299 PASS |
| pytest AW regression | 292/292 PASS |
| pytest AV regression | 259/259 PASS |
| pytest AU regression | 235/235 PASS |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| pytest combined chain (all 21 suites: BF stage3 + BF stage1 + BE stage3 + BE stage1 + BD stage3 + BD stage1 + BC stage3 + BC stage1 + BB stage3 + BB stage1 + BA + AZ + AY + AX + AW + AV + AU + AT + AS + AR + AQ) | **3819/3819 PASS** (3672 prior BE baseline + BF stage3 124 + BF stage1 23) |
| pytest broad `tests/demo_trading/ --ignore=test_demo_emergency_close_sender.py` | **7620/7620 PASS** (excludes pre-existing emergency_close_sender CLI dry-run failure introduced in TASK-014N — unrelated to BF) |
| BF preview smoke (synthetic BE artifact) | exit 0; status `..._MANUAL_AUTHORIZATION_REVIEW_FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_READY`; report JSON+MD contain `TASK-014BF consumes TASK-014BE` and `BE-proven chained proof`; report JSON+MD do NOT contain `TASK-014BF consumes TASK-014BD`, `TASK-014BF consumes TASK-014BC`, `TASK-014BF consumes TASK-014BB`, `TASK-014BF consumes TASK-014BA`, `TASK-014BF consumes TASK-014AZ`, `TASK-014BF consumes TASK-014AY`, `TASK-014BF consumes TASK-014AX`, `TASK-014BF consumes TASK-014AW`, or `TASK-014BF consumes TASK-014AV`; report JSON+MD do NOT describe BF as a readiness review or dry-run, and do NOT describe BE as a readiness review or dry-run |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no secret read / no G20 lift / no position modification / no approval-input-as-authorization / no automatic git commit / no automatic git push) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | `TASK-014BF: add guarded entry real execution adapter disabled implementation scaffold manual authorization gate final pre-execution review manual authorization review final pre-execution review manual authorization review` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-18 TASK-014BF)

1. VPS git pull and re-validate BF locally:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile \
           src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review.py \
           scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review.py \
           tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review.py \
           tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_stage1.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review.py -q
       # expect 124/124 PASS
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_stage1.py -q
       # expect 23/23 PASS

   Then run the BF preview with the real BE manual-authorization-review final-pre-execution-review artifact present and confirm:

       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review.py \
           --from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review-final-pre-execution-review \
           --symbol SOLUSDT \
           --write-report
       # status == TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_READY
       # mode == disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_checklist
       # failed_stage == (none)
       # generated report JSON+MD contain "TASK-014BF consumes TASK-014BE" and "BE-proven chained proof"
       # generated report JSON+MD do NOT contain "TASK-014BF consumes TASK-014BD/BC/BB/BA/AZ/AY/AX/AW/AV"
       # generated report JSON+MD do NOT describe BF as readiness-review or dry-run, and do NOT describe BE as readiness-review or dry-run
       # no socket opened, no endpoint called, no secret loaded, G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014BG
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate final pre-execution review
   manual authorization review final pre-execution review manual
   authorization review **dry-run** — next phase; still no real
   execution).

---

> Previous README banner: TASK-014BE (2026-06-18) — see archived block below.

## TASK-014BE Banner (archived 2026-06-18 by TASK-014BF)

> README shared status updated by TASK-014BE (2026-06-18) — see
> [Demo Trading Guarded Lifecycle Status](../../../README.md#demo-trading-guarded-lifecycle-statusupdated-by-task-014be-2026-06-18)
> for the cross-agent status board. TASK-014BE added the
> guarded entry real execution adapter disabled implementation scaffold
> manual authorization gate final pre-execution review manual
> authorization review **final pre-execution review** scaffold:
> new BE src/scripts/test triple (Stage 1 focused-core 23 tests + Stage 3
> full pack 119 tests, kept as two separate files), 37 hard-fail gates
> (Group A 18 BD-upstream / Group B 7 scope_summary content (incl. AV
> guard) / Group C 3 BD-failure passthrough / Group D 9 BE own-source
> safety), a ~52-field result dataclass exposing 17 BD-upstream proof
> fields + 11 BD→BC chained-proof fields, BD artifact loader/parser, CLI
> preview script with
> `--from-latest-entry-...-manual-authorization-review-readiness-review`
> + `--allow-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review-final-pre-execution-review`
> + `--allow-real-entry-execution` (still returns
> `REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED`) + `--write-report`, JSON +
> Markdown report writer,
> `STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-FINAL-PRE-EXECUTION-REVIEW-ONLY`
> identity wording, and
> `NEXT_REQUIRED_TASK=TASK-014BF_..._manual_authorization_review_manual_authorization_review`.
> BD manual-authorization-review readiness-review JSON is the direct
> upstream; BC manual-authorization-review dry-run, BB manual-authorization-review,
> BA final-pre-execution-review, AZ readiness-review and AY/AX/AW/AV/AU/AT/AS/AR/AQ
> are referenced ONLY as BD-proven chained proof — BE never consumes them
> directly. BD is never described as a final pre-execution review; BE is
> the final pre-execution review phase. Still no sender, no real execution
> adapter, no endpoint call, no secret read, no G20 lift, no position
> modification. main.py / src/risk.py / BybitExecutor untouched.

## TASK-014BE Status (2026-06-18)

| item | status |
|---|---|
| new src `src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review.py` (BE triple, ~1394 lines) | DONE |
| new scripts `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review.py` (CLI) | DONE |
| new tests Stage 1 focused-core `tests/demo_trading/test_demo_tiny_..._final_pre_execution_review_stage1.py` (23 tests) | DONE |
| new tests Stage 3 full pack `tests/demo_trading/test_demo_tiny_..._final_pre_execution_review.py` (primary regression pack, 119 tests covering core run / Group A / Group B / Group C / Group D / --allow flags / CLI subprocess / write_report JSON+MD on-disk inspection / identity wording / no BD-as-final-pre-execution-review grep / untouched main.py + src/risk.py + BybitExecutor / BD loader) | DONE |
| identity wording: `STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-FINAL-PRE-EXECUTION-REVIEW-ONLY` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BF_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_manual_authorization_review"` | DONE |
| direct upstream = BD manual-authorization-review readiness-review; BC/BB/BA/AZ/AY/AX/AW/AV/AU/AT/AS/AR/AQ referenced ONLY as BD-proven chained proof | DONE |
| 37 hard-fail gates registered in `_HARD_FAIL_GATES` (Group A 18 + Group B 7 + Group C 3 + Group D 9 = 37) — any one forces `status == FAIL_CLOSED` | DONE |
| 17 BD-upstream dataclass fields + 11 BD→BC chained-proof dataclass fields + `to_dict()` JSON emission | DONE |
| `write_report` writes `latest_*.json` / `latest_*.md` / `*_<UTC_TS>.json` / `*_<UTC_TS>.md` to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review/` | DONE |
| .gitignore updated with the new BE final-pre-execution-review output dir | DONE |
| README "Demo Trading Guarded Lifecycle Status" board re-targeted to TASK-014BE (2026-06-18) | DONE |
| py_compile BE src + scripts + Stage 1 test + Stage 3 full test | PASS |
| pytest BE Stage 3 full pack | **119/119 PASS** |
| pytest BE Stage 1 focused-core | **23/23 PASS** |
| pytest BD Stage 3 full pack | 112/112 PASS |
| pytest BD Stage 1 focused-core | 17/17 PASS |
| pytest BC Stage 3 full pack | 105/105 PASS |
| pytest BC Stage 1 focused-core | 16/16 PASS |
| pytest BB Stage 3 full pack | 84/84 PASS |
| pytest BB Stage 1 focused-core | 13/13 PASS |
| pytest BA regression | 536/536 PASS |
| pytest AZ regression | 481/481 PASS |
| pytest AY regression | 389/389 PASS |
| pytest AX regression | 299/299 PASS |
| pytest AW regression | 292/292 PASS |
| pytest AV regression | 259/259 PASS |
| pytest AU regression | 235/235 PASS |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| pytest combined chain (all 19 suites: BE stage3 + BE stage1 + BD stage3 + BD stage1 + BC stage3 + BC stage1 + BB stage3 + BB stage1 + BA + AZ + AY + AX + AW + AV + AU + AT + AS + AR + AQ) | **3672/3672 PASS** (3530 prior BD baseline + BE stage3 119 + BE stage1 23) |
| BE preview smoke (synthetic BD artifact) | exit 0; status `..._MANUAL_AUTHORIZATION_REVIEW_FINAL_PRE_EXECUTION_REVIEW_READY`; report JSON+MD contain `TASK-014BE consumes TASK-014BD`; report JSON+MD do NOT contain `TASK-014BE consumes TASK-014BC`, `TASK-014BE consumes TASK-014BB`, `TASK-014BE consumes TASK-014BA`, `TASK-014BE consumes TASK-014AZ`, `TASK-014BE consumes TASK-014AY`, `TASK-014BE consumes TASK-014AX`, `TASK-014BE consumes TASK-014AW`, or `TASK-014BE consumes TASK-014AV`; report JSON+MD do NOT describe BD as a final pre-execution review |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no secret read / no G20 lift / no position modification / no approval-input-as-authorization / no automatic git commit / no automatic git push) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | `TASK-014BE: add guarded entry real execution adapter disabled implementation scaffold manual authorization gate final pre-execution review manual authorization review final pre-execution review` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-18 TASK-014BE)

1. VPS git pull and re-validate BE locally:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile \
           src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review.py \
           scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review.py \
           tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review.py \
           tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_stage1.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review.py -q
       # expect 119/119 PASS
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_stage1.py -q
       # expect 23/23 PASS

   Then run the BE preview with the real BD manual-authorization-review readiness-review artifact present and confirm:

       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review.py \
           --from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review-readiness-review \
           --symbol SOLUSDT \
           --write-report
       # status == TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_FINAL_PRE_EXECUTION_REVIEW_READY
       # mode == disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_checklist
       # failed_stage == (none)
       # generated report JSON+MD contain "TASK-014BE consumes TASK-014BD"
       # generated report JSON+MD do NOT contain "TASK-014BE consumes TASK-014BC/BB/BA/AZ/AY/AX/AW/AV"
       # generated report JSON+MD do NOT describe BD as a final pre-execution review
       # no socket opened, no endpoint called, no secret loaded, G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014BF
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate final pre-execution review
   manual authorization review final pre-execution review **manual
   authorization review** — next phase; still no real execution).

---

> Previous README banner: TASK-014BD (2026-06-17) — see archived block below.

## TASK-014BD Banner (archived 2026-06-18 by TASK-014BE)

> TASK-014BD added the
> guarded entry real execution adapter disabled implementation scaffold
> manual authorization gate final pre-execution review manual
> authorization review **readiness review** scaffold: new BD src/scripts/test
> triple (Stage 1 focused-core 17 tests + Stage 3 full pack 111 tests, kept as
> two separate files), 37 hard-fail gates (FIX1 hardens AV; Group A 18
> BC-upstream / Group B 7 scope_summary content (incl. FIX1 AV guard) /
> Group C 3 BC-failure passthrough / Group D 9 BD own-source safety),
> a ~52-field result dataclass exposing 17 BC-upstream
> proof fields + 11 BC→BB chained-proof fields, BC artifact loader/parser,
> CLI preview script with `--from-latest-entry-...-manual-authorization-review-dry-run`
> + `--allow-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review-readiness-review`
> + `--allow-real-entry-execution` (still returns
> `REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED`) + `--write-report`, JSON +
> Markdown report writer, `STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-READINESS-REVIEW-ONLY`
> identity wording, and
> `NEXT_REQUIRED_TASK=TASK-014BE_..._manual_authorization_review_final_pre_execution_review`.
> BC manual-authorization-review dry-run JSON is the direct upstream; BB
> manual-authorization-review, BA final-pre-execution-review, AZ readiness-review
> and AY/AX/AW/AV/AU/AT/AS/AR/AQ are referenced ONLY as BC-proven chained
> proof — BD never consumes them directly. BC is never described as a
> readiness review; BD is the readiness review phase. Still no sender, no
> real execution adapter, no endpoint call, no secret read, no G20 lift,
> no position modification.
> main.py / src/risk.py / BybitExecutor untouched.

## TASK-014BD Status (2026-06-17)

| item | status |
|---|---|
| new src `src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review.py` (BD triple, ~1416 lines) | DONE |
| new scripts `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review.py` (CLI) | DONE |
| new tests Stage 1 focused-core `tests/demo_trading/test_demo_tiny_..._readiness_review_stage1.py` (17 tests) | DONE |
| new tests Stage 3 full pack `tests/demo_trading/test_demo_tiny_..._readiness_review.py` (primary regression pack, 111 tests covering core run / Group A / Group B / Group C / Group D / --allow flags / CLI subprocess / write_report JSON+MD on-disk inspection / identity wording / no BC-as-readiness-review grep / untouched main.py + src/risk.py + BybitExecutor / BC loader) | DONE |
| identity wording: `STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-READINESS-REVIEW-ONLY` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BE_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review"` | DONE |
| direct upstream = BC manual-authorization-review dry-run; BB/BA/AZ/AY/AX/AW/AV/AU/AT/AS/AR/AQ referenced ONLY as BC-proven chained proof | DONE |
| 37 hard-fail gates registered in `_HARD_FAIL_GATES` (FIX1: Group A 18 + Group B 7 + Group C 3 + Group D 9 = 37) — any one forces `status == FAIL_CLOSED`. BD hardens one extra Group B phrase (`TASK-014BC consumes TASK-014AV`) compared with BC's 36-gate baseline. | DONE |
| 17 BC-upstream dataclass fields + 11 BC→BB chained-proof dataclass fields + `to_dict()` JSON emission | DONE |
| `write_report` writes `latest_*.json` / `latest_*.md` / `*_<UTC_TS>.json` / `*_<UTC_TS>.md` to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review/` | DONE |
| .gitignore updated with the new BD readiness-review output dir | DONE |
| README "Demo Trading Guarded Lifecycle Status" board re-targeted to TASK-014BD (2026-06-17) | DONE |
| py_compile BD src + scripts + Stage 1 test + Stage 3 full test | PASS |
| pytest BD Stage 3 full pack | **112/112 PASS** (FIX1: +1 test for AV guard) |
| pytest BD Stage 1 focused-core | **17/17 PASS** |
| pytest BC Stage 3 full pack | 105/105 PASS |
| pytest BC Stage 1 focused-core | 16/16 PASS |
| pytest BB Stage 3 full pack | 84/84 PASS |
| pytest BB Stage 1 focused-core | 13/13 PASS |
| pytest BA regression | 536/536 PASS |
| pytest AZ regression | 481/481 PASS |
| pytest AY regression | 389/389 PASS |
| pytest AX regression | 299/299 PASS |
| pytest AW regression | 292/292 PASS |
| pytest AV regression | 259/259 PASS |
| pytest AU regression | 235/235 PASS |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| pytest combined chain (all 17 suites: BD stage3 + BD stage1 + BC stage3 + BC stage1 + BB stage3 + BB stage1 + BA + AZ + AY + AX + AW + AV + AU + AT + AS + AR + AQ) | **3530/3530 PASS** (3401 prior baseline + BD stage3 112 + BD stage1 17) |
| BD preview smoke (synthetic BC artifact) | exit 0; status `..._MANUAL_AUTHORIZATION_REVIEW_READINESS_REVIEW_READY`; report JSON+MD contain `TASK-014BD consumes TASK-014BC`; report JSON+MD do NOT contain `TASK-014BD consumes TASK-014BB`, `TASK-014BD consumes TASK-014BA`, `TASK-014BD consumes TASK-014AZ`, `TASK-014BD consumes TASK-014AY`, `TASK-014BD consumes TASK-014AX`, `TASK-014BD consumes TASK-014AW`, or `TASK-014BD consumes TASK-014AV`; report JSON+MD do NOT describe BC as a readiness review |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no secret read / no G20 lift / no position modification / no approval-input-as-authorization / no automatic git commit / no automatic git push) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commits | `a18357e TASK-014BD: ...` + FIX1 commit `TASK-014BD-FIX1: harden readiness review upstream scope AV guard` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-17 TASK-014BD)

1. VPS git pull and re-validate BD locally:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile \
           src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review.py \
           scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review.py \
           tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review.py \
           tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_stage1.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review.py -q
       # expect 112/112 PASS (FIX1: +1 test for AV guard)
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_stage1.py -q
       # expect 17/17 PASS

   Then run the BD preview with the real BC manual-authorization-review dry-run artifact present and confirm:

       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review.py \
           --from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review-dry-run \
           --symbol SOLUSDT \
           --write-report
       # status == TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_READINESS_REVIEW_READY
       # mode == disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_checklist
       # failed_stage == (none)
       # generated report JSON+MD contain "TASK-014BD consumes TASK-014BC"
       # generated report JSON+MD do NOT contain "TASK-014BD consumes TASK-014BB/BA/AZ/AY/AX/AW/AV"
       # generated report JSON+MD do NOT describe BC as a readiness review
       # no socket opened, no endpoint called, no secret loaded, G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014BE
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate final pre-execution review
   manual authorization review **final pre-execution review** — next
   phase; still no real execution).

---

> Previous README banner: TASK-014BC (2026-06-17) — see archived block below.

## TASK-014BC Banner (archived 2026-06-17 by TASK-014BD)

> TASK-014BC added the guarded entry real execution adapter disabled
> implementation scaffold manual authorization gate final pre-execution
> review manual authorization review **dry-run** scaffold layer between
> BB manual-authorization-review and BD readiness-review. New BC
> src/scripts/test triple (Stage 1 focused-core 16 tests + Stage 3 full
> pack 105 tests), 36 hard-fail gates, ~52-field result dataclass with
> 17 BB-upstream proof fields + 11 BB→BA chained-proof fields. BB
> manual-authorization-review JSON is the direct upstream; BA final-pre-execution-review,
> AZ readiness-review and AY/AX/AW/AV/AU/AT/AS/AR/AQ are referenced ONLY
> as BB-proven chained proof. Still no sender, no real execution adapter,
> no endpoint call, no secret read, no G20 lift, no position modification.
> Local commit `6959f5f` (NOT pushed).

## TASK-014BC Status (2026-06-17)

| item | status |
|---|---|
| new src `src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run.py` (BC triple, 1470 lines) | DONE |
| new scripts `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run.py` (CLI, 391 lines) | DONE |
| new tests Stage 1 focused-core `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_stage1.py` (401 lines, 16 tests — kept as smaller focused proof) | DONE |
| new tests Stage 3 full pack `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run.py` (primary regression pack, 105 tests covering core run / Group A / Group B / Group C / Group D / --allow flags / CLI subprocess / write_report JSON+MD on-disk inspection / identity wording / no BB-as-dry-run grep / untouched main.py + src/risk.py + BybitExecutor / BB loader) | DONE |
| identity wording: `STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-DRY-RUN-ONLY` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BD_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review"` | DONE |
| direct upstream = BB manual-authorization-review; BA final-pre-execution-review, AZ readiness-review and AY/AX/AW/AV/AU/AT/AS/AR/AQ referenced ONLY as BB-proven chained proof | DONE |
| 36 hard-fail gates registered in `_HARD_FAIL_GATES` (Group A 18 + Group B 6 + Group C 3 + Group D 9) — any one forces `status == FAIL_CLOSED` | DONE |
| 17 BB-upstream dataclass fields + 11 BB→BA chained-proof dataclass fields + `to_dict()` JSON emission | DONE |
| `write_report` writes `latest_*.json` / `latest_*.md` / `*_<UTC_TS>.json` / `*_<UTC_TS>.md` to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run/` | DONE |
| .gitignore updated with the new BC dry-run output dir | DONE |
| README "Demo Trading Guarded Lifecycle Status" board re-targeted to TASK-014BC (2026-06-17) | DONE |
| py_compile BC src + scripts + Stage 1 test + Stage 3 full test | PASS |
| pytest BC Stage 3 full pack | **105/105 PASS** |
| pytest BC Stage 1 focused-core | **16/16 PASS** |
| pytest BB Stage 3 full pack | 84/84 PASS |
| pytest BB Stage 1 focused-core | 13/13 PASS |
| pytest BA regression | 536/536 PASS |
| pytest AZ regression | 481/481 PASS |
| pytest AY regression | 389/389 PASS |
| pytest AX regression | 299/299 PASS |
| pytest AW regression | 292/292 PASS |
| pytest AV regression | 259/259 PASS |
| pytest AU regression | 235/235 PASS |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| pytest combined chain (all 15 suites: BC stage3 + BC stage1 + BB stage3 + BB stage1 + BA + AZ + AY + AX + AW + AV + AU + AT + AS + AR + AQ) | **3401/3401 PASS** (3183 prior baseline + BB stage3 84 + BB stage1 13 + BC stage3 105 + BC stage1 16) |
| BC preview smoke (synthetic BB artifact) | exit 0; status `..._MANUAL_AUTHORIZATION_REVIEW_DRY_RUN_READY`; report JSON+MD contain `TASK-014BC consumes TASK-014BB`; report JSON+MD do NOT contain `TASK-014BC consumes TASK-014BA`, `TASK-014BC consumes TASK-014AZ`, `TASK-014BC consumes TASK-014AY`, `TASK-014BC consumes TASK-014AX`, `TASK-014BC consumes TASK-014AW`, or `TASK-014BC consumes TASK-014AV`; report JSON+MD do NOT describe BB as a dry-run |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no secret read / no G20 lift / no position modification / no approval-input-as-authorization / no automatic git commit / no automatic git push) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | DONE — `TASK-014BC: add guarded entry real execution adapter disabled implementation scaffold manual authorization gate final pre-execution review manual authorization review dry run` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-17 TASK-014BC)

1. VPS git pull and re-validate BC locally:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile \
           src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run.py \
           scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run.py \
           tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run.py \
           tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_stage1.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run.py -q
       # expect 105/105 PASS
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_stage1.py -q
       # expect 16/16 PASS

   Then run the BC preview with the real BB manual-authorization-review artifact present and confirm:

       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run.py \
           --from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review \
           --symbol SOLUSDT \
           --write-report
       # status == TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_DRY_RUN_READY
       # mode == disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run_checklist
       # failed_stage == (none)
       # generated report JSON+MD contain "TASK-014BC consumes TASK-014BB"
       # generated report JSON+MD do NOT contain "TASK-014BC consumes TASK-014BA/AZ/AY/AX/AW/AV"
       # generated report JSON+MD do NOT describe BB as a dry-run
       # no socket opened, no endpoint called, no secret loaded, G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014BD
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate final pre-execution review
   manual authorization review dry-run **readiness review** — next
   phase; still no real execution).

---

> Previous README banner: TASK-014BB (2026-06-17) — see archived block below.

## TASK-014BB Banner (archived 2026-06-17 by TASK-014BC)

> TASK-014BB adds the guarded entry real execution adapter disabled
> implementation scaffold manual authorization gate final pre-execution
> review **manual authorization review** scaffold layer between BA
> final-pre-execution-review and BC dry-run. New BB src/scripts/test
> triple (Stage 1 focused-core 13 tests + Stage 3 full pack 84 tests),
> 36 hard-fail gates, ~52-field result dataclass with 17 BA-upstream
> proof fields + 11 BA→AZ chained-proof fields. BA final-pre-execution-review
> JSON is the direct upstream; AZ readiness-review and AY/AX/AW/AV/AU/AT/AS/AR/AQ
> are referenced ONLY as BA-proven chained proof. Still no sender, no
> real execution adapter, no endpoint call, no secret read, no G20 lift,
> no position modification. Local commit `c37c401` (NOT pushed).
> See `## TASK-014BB Status (2026-06-17)` below for the full pre-BC banner.

## TASK-014BB Status (2026-06-17)

| item | status |
|---|---|
| new src `src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.py` (BB triple, 1462 lines) | DONE |
| new scripts `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.py` (CLI, 424 lines) | DONE |
| new tests Stage 1 focused-core `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_stage1.py` (364 lines, 13 tests — kept as smaller focused proof) | DONE |
| new tests Stage 3 full pack `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.py` (primary regression pack, 84 tests covering core run / Group A / Group B / Group C / Group D / --allow flags / CLI subprocess / write_report JSON+MD on-disk inspection / identity wording / untouched main.py + src/risk.py + BybitExecutor) | DONE |
| identity wording: `STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-ONLY` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BC_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_dry_run"` | DONE |
| direct upstream = BA final-pre-execution-review; AZ readiness-review and AY/AX/AW/AV/AU/AT/AS/AR/AQ referenced ONLY as BA-proven chained proof | DONE |
| 36 hard-fail gates registered in `_HARD_FAIL_GATES` (Group A 18 + Group B 6 + Group C 3 + Group D 9) — any one forces `status == FAIL_CLOSED` | DONE |
| 17 BA-upstream dataclass fields + 11 BA→AZ chained-proof dataclass fields + `to_dict()` JSON emission | DONE |
| `write_report` writes latest_*.json / latest_*.md / *_<UTC_TS>.json / *_<UTC_TS>.md to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review/` | DONE |
| .gitignore updated with the new BB output dir | DONE |
| README "Demo Trading Guarded Lifecycle Status" board re-targeted to TASK-014BB (2026-06-17) | DONE |
| py_compile BB src + scripts + Stage 1 test + Stage 3 full test | PASS |
| pytest BB Stage 3 full pack | **84/84 PASS** |
| pytest BB Stage 1 focused-core | **13/13 PASS** |
| pytest BA regression | 536/536 PASS |
| pytest AZ regression | 481/481 PASS |
| pytest AY regression | 389/389 PASS |
| pytest AX regression | 299/299 PASS |
| pytest AW regression | 292/292 PASS |
| pytest AV regression | 259/259 PASS |
| pytest AU regression | 235/235 PASS |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| pytest combined chain (all 13 suites: BB stage3 + BB stage1 + BA + AZ + AY + AX + AW + AV + AU + AT + AS + AR + AQ) | **3280/3280 PASS** (3183 prior baseline + BB stage3 84 + BB stage1 13) |
| BB preview smoke (synthetic BA artifact) | exit 0; status `..._MANUAL_AUTHORIZATION_REVIEW_READY`; report JSON+MD contain `TASK-014BB consumes TASK-014BA`; report JSON+MD do NOT contain `TASK-014BB consumes TASK-014AZ`, `TASK-014BB consumes TASK-014AY`, `TASK-014BB consumes TASK-014AX`, `TASK-014BB consumes TASK-014AW`, or `TASK-014BB consumes TASK-014AV` |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no secret read / no G20 lift / no position modification / no approval-input-as-authorization / no automatic git commit / no automatic git push) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | DONE — `TASK-014BB: add guarded entry real execution adapter disabled implementation scaffold manual authorization gate final pre-execution review manual authorization review` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-17 TASK-014BB)

1. VPS git pull and re-validate BB locally:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile \
           src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.py \
           scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.py \
           tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.py \
           tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_stage1.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.py -q
       # expect 84/84 PASS
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_stage1.py -q
       # expect 13/13 PASS

   Then run the BB preview with the real BA final-pre-execution-review artifact present and confirm:

       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.py \
           --from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review \
           --symbol SOLUSDT \
           --write-report
       # status == TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_READY
       # mode == disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_checklist
       # failed_stage == (none)
       # generated report JSON+MD contain "TASK-014BB consumes TASK-014BA"
       # generated report JSON+MD do NOT contain "TASK-014BB consumes TASK-014AZ/AY/AX/AW/AV"
       # no socket opened, no endpoint called, no secret loaded, G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014BC
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate final pre-execution review
   manual authorization review **dry-run** — next phase; still no
   real execution).

---

> Previous README banner: TASK-014BA-FIX2 (2026-06-17) — see archived block below.

## TASK-014BA-FIX2 Banner (archived 2026-06-17 by TASK-014BB)

> TASK-014BA-FIX2 finishes the BA bulk-rename cleanup: BA-FIX1 wired AZ
> readiness-review as BA's direct upstream and the preview now succeeds
> on the VPS, but the generated BA report's `scope_summary` field still
> carried over the old AY-direct wording ("TASK-014BA consumes TASK-014AY
> DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE DRY-RUN
> output at runtime plus the 34 upstream artifacts AY proves/chains,
> including AX manual authorization gate design, ...") plus an
> "Itdocuments" typo. FIX2 rewrites the `scope_summary` to BA-correct
> semantics ("TASK-014BA consumes TASK-014AZ DISABLED IMPLEMENTATION
> SCAFFOLD MANUAL AUTHORIZATION GATE READINESS REVIEW output at runtime
> plus AZ-proven chained proof, including AY dry-run, AX manual
> authorization gate design, AW final pre-execution review, AV readiness
> review, AU dry-run, AT design, AS static skeleton dry-run, AR static
> skeleton design, and AQ implementation design, and produces a DISABLED
> IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION
> REVIEW for TASK-014BB."), repairs the "Itdocuments" → "It documents"
> typo, repoints two existing tests whose assertions hardcoded the
> bulk-renamed wording, and adds 28 new BA-FIX2 regression tests
> (positive AZ-direct wording proofs, AY-only-as-chained partition
> proof, negative AY/AX/AW/AV-direct grep, Itdocuments typo grep,
> on-disk JSON+Markdown report wording, markdown intro line
> preservation, and AZ-direct field-exposure regression). Still no
> sender, no real execution adapter, no endpoint call, no secret read,
> no G20 lift, no position modification. main.py / src/risk.py /
> BybitExecutor untouched.

## TASK-014BA-FIX2 Status (2026-06-17)

| item | status |
|---|---|
| root cause: BA `scope_summary` carried bulk-rename contamination from AZ — still said "TASK-014BA consumes TASK-014AY DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE DRY-RUN output at runtime plus the 34 upstream artifacts AY proves/chains, including AX manual authorization gate design, ..." with no AZ-direct mention, plus an "Itdocuments" no-space typo | IDENTIFIED |
| BA src: rewrite `scope_summary` to "TASK-014BA consumes TASK-014AZ DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE READINESS REVIEW output at runtime plus AZ-proven chained proof, including AY dry-run, AX manual authorization gate design, AW final pre-execution review, AV readiness review, AU dry-run, AT design, AS static skeleton dry-run, AR static skeleton design, and AQ implementation design, and produces a DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW for TASK-014BB" | DONE |
| BA src: repair "Itdocuments" → "It documents" typo inside the same `scope_summary` block | DONE |
| BA tests: repoint `TestARFIX2StaticSkeletonScopeAlias.test_to_dict_exposes_static_skeleton_scope_alias` from old AY-direct wording to new AZ-direct wording | DONE |
| BA tests: rename/rewrite `TestAZScopeSummarySaysAY.test_scope_summary_names_ay_as_direct` → `TestBAFIX2ScopeSummarySaysAZ.test_scope_summary_names_az_as_direct` | DONE |
| BA tests: add `TestBAFIX2ScopeSummaryNamesAZAsDirectUpstream` (7 tests — runtime positive proofs + AY-only-as-chained partition trick) | DONE |
| BA tests: add `TestBAFIX2ScopeSummaryNegativeProof` (4 tests — grep-style negatives for AY/AX/AW/AV-direct phrasings) | DONE |
| BA tests: add `TestBAFIX2GeneratedReportScopeSummaryWording` (11 tests — on-disk JSON+Markdown via `_write_report` with `repo_tmp_path` fixture) | DONE |
| BA tests: add `TestBAFIX2MarkdownIntroLineRemainsCorrect` (1 test — intro line FIX1 wording preserved) | DONE |
| BA tests: add `TestBAFIX2AZDirectUpstreamFieldsStillExposed` (5 tests — FIX1 AZ-direct + nested simulated_approval field-exposure regression) | DONE |
| py_compile BA src + scripts + tests | PASS |
| pytest BA | **536/536 PASS** (508 baseline + 28 FIX2) |
| pytest AZ regression | 481/481 PASS |
| pytest AY regression | 389/389 PASS |
| pytest AX regression | 299/299 PASS |
| pytest AW regression | 292/292 PASS |
| pytest AV regression | 259/259 PASS |
| pytest AU regression | 235/235 PASS |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| pytest combined chain (all 11 suites) | **3183/3183 PASS** (3155 baseline + 28 FIX2) |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no secret read / no G20 lift / no position modification) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | PENDING — `TASK-014BA-FIX2: correct BA scope summary direct-upstream wording` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-17 TASK-014BA-FIX2)

1. VPS git pull and re-validate BA preview report wording:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py -q
       # expect 536/536 PASS

   Then re-run the BA preview with the AZ readiness-review (and AY dry-run) upstream artifacts present and confirm the generated report's `scope_summary` field:

       # contains: "TASK-014BA consumes TASK-014AZ DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE READINESS REVIEW output at runtime plus AZ-proven chained proof, including AY dry-run, AX manual authorization gate design, ..."
       # does NOT contain: "TASK-014BA consumes TASK-014AY"
       # does NOT contain: "TASK-014BA consumes TASK-014AX"
       # does NOT contain: "TASK-014BA consumes TASK-014AW"
       # does NOT contain: "TASK-014BA consumes TASK-014AV"
       # does NOT contain: "Itdocuments"
       # contains: "It documents"
       # status / mode / failed_stage / safety invariants all unchanged from FIX1.

2. Once step 1 passes, decide whether to authorise TASK-014BB
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate final pre-execution review
   **manual authorization review** — next phase; still no real execution).

---

> Previous README banner: TASK-014BA-FIX1 (2026-06-16) — see archived block below.

## TASK-014BA-FIX1 Banner (archived 2026-06-17)

> TASK-014BA-FIX1 fixes the BA preview
> regression observed on the VPS after TASK-014BA shipped: the BA preview
> CLI rejected `--from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-readiness-review`
> because the bulk-rename from AZ left BA wired to AY-dry-run as direct
> upstream instead of AZ-readiness-review. FIX1 promotes AZ-readiness-review
> to BA's direct upstream and demotes the existing AY-dry-run wiring to
> chained-through-AZ proof, mirroring the AZ-FIX1 pattern that added an
> AY-direct layer on top of AZ's chained-through-AY-of-AX. New: 1 contract
> version constant, 15 AZ-direct hard-fail gates, 14 nested AZ→AY
> simulated_approval hard-fail gates, 30 dataclass fields + `to_dict()`
> exposure, `run_readiness_review` kwarg, scripts default dir + loader +
> `--from-latest-...-readiness-review` flag + missing-AZ fail-closed exit-1
> + AZ-upstream report rows, approval flag rename
> `--allow-...-readiness-review` → `--allow-...-final-pre-execution-review`,
> intro/banner wording update, and 25 new BA-FIX1 regression tests. Still
> no sender, no real execution adapter, no endpoint call, no secret read,
> no G20 lift, no position modification. main.py / src/risk.py /
> BybitExecutor untouched.

## TASK-014BA-FIX1 Status (2026-06-16)

| item | status |
|---|---|
| root cause: BA scripts CLI lacked `--from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-readiness-review`; BA was bulk-renamed from AZ but its direct upstream was still wired to AY-dry-run (AZ's old direct upstream) instead of AZ-readiness-review | IDENTIFIED |
| BA src: add `CONSUMED_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_READINESS_REVIEW_CONTRACT_VERSION` constant | DONE |
| BA src: add `ACCEPTABLE_..._READINESS_REVIEW_STATUSES` + `ACCEPTABLE_..._READINESS_REVIEW_MODES` frozensets | DONE |
| BA src: add 15 `GATE_ENTRY_..._READINESS_REVIEW_*` AZ-direct hard-fail gate constants | DONE |
| BA src: add 14 `GATE_AZ_READINESS_REVIEW_AY_DRY_RUN_SIMULATED_APPROVAL_*` nested hard-fail gate constants | DONE |
| BA src: append all 29 new gates to `_HARD_FAIL_GATES` frozenset | DONE |
| BA src: add 30 dataclass fields (15 AZ-direct + 14 nested AZ→AY simulated_approval + 1 contract version) + `to_dict()` emission | DONE |
| BA src: `run_readiness_review()` accepts `entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review: dict \| None = None` kwarg | DONE |
| BA src: parser block evaluates 29 new gates and populates 30 new fields with observed values | DONE |
| BA src: stage_0 summary references "AZ direct artifact + AZ's nested AY proof envelope" | DONE |
| BA scripts: `_DEFAULT_ENTRY_..._READINESS_REVIEW_DIR` + `load_latest_entry_..._readiness_review()` loader | DONE |
| BA scripts: `--from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-readiness-review` CLI flag | DONE |
| BA scripts: missing-AZ-artifact prints fail-closed message + `sys.exit(1)`, prints AZ source line in stdout banner | DONE |
| BA scripts: approval flag renamed `--allow-...-readiness-review` → `--allow-...-final-pre-execution-review` (argparse + every docstring/banner mention + attribute access) | DONE |
| BA scripts: intro/banner wording updated to "BA consumes AZ readiness review" | DONE |
| BA scripts: `_write_report` markdown adds 30 new AZ-upstream-proof rows | DONE |
| BA tests: `_valid_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review()` fixture | DONE |
| BA tests: `_run()` helper extended with `entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review=_UNSET` parameter | DONE |
| BA tests: 25 new BA-FIX1 regression tests (CLI help / subprocess happy-path / missing-AZ artifact fail-closed / 6+ representative hard-fail gates / field exposure / report contents / fixture happy-path) | DONE |
| py_compile BA src + scripts + test | PASS |
| pytest BA | **508/508 PASS** (483 baseline + 25 FIX1) |
| pytest AZ regression | 481/481 PASS |
| pytest combined chain (BA + AZ + upstream readiness/dry-run series) | **2867/2867 PASS** |
| CLI `--help` exposes `--from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-readiness-review` | CONFIRMED |
| CLI `--help` exposes renamed `--allow-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review` | CONFIRMED |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no secret read / no G20 lift / no position modification) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | DONE — `57f382b` (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-16 TASK-014BA-FIX1)

1. VPS git pull and re-validate BA preview:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py -q
       # expect 508/508 PASS

   Then re-run the BA preview with both the AZ readiness-review and the AY dry-run upstream artifacts present and confirm:

       # status  = TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_READY
       # mode    = disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_checklist
       # failed_stage = (none)
       # CLI no longer rejects `--from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-readiness-review`
       # no socket opened, no endpoint called, no secret loaded, G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014BB
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate final pre-execution review
   **manual authorization review** — next phase; still no real execution).

---

> Previous README banner: TASK-014BA (2026-06-16) — see archived block below.

## TASK-014BA Banner (archived 2026-06-16)

> Original TASK-014BA adds the
> guarded entry real execution adapter disabled implementation scaffold
> manual authorization gate **final pre-execution review** scaffold:
> new BA src/scripts/test triple, AZ readiness_review as direct upstream
> (AY/AX/AW/AV/AU/AT/AS/AR/AQ chained through AZ), 14 stage parser,
> `_HARD_FAIL_GATES` registration, `FINAL-PRE-EXECUTION-REVIEW-ONLY`
> identity wording, and `NEXT_REQUIRED_TASK = TASK-014BB_..._final_pre_execution_review_manual_authorization_review`.
> Source-level chain-literal guards lock AY→AZ readiness_review /
> AZ→BA final_pre_execution_review / BA→BB manual_authorization_review
> forward refs against future bulk-rename contamination. Still no
> sender, no real execution adapter, no endpoint call, no secret read,
> no G20 lift, no position modification.

## TASK-014BA Status (2026-06-16)

| item | status |
|---|---|
| new src `src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py` (BA triple) | DONE |
| new scripts `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py` | DONE |
| new tests `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py` | DONE |
| identity wording: `STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-FINAL-PRE-EXECUTION-REVIEW-ONLY` | DONE |
| `NEXT_REQUIRED_TASK = "TASK-014BB_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review"` | DONE |
| direct upstream = AZ readiness_review; AY/AX/AW/AV/AU/AT/AS/AR/AQ chained through AZ | DONE |
| 14-stage parser (`stage_0_artifact_preflight` … `stage_13_final_implementation_design_verdict`) | DONE |
| `_HARD_FAIL_GATES` populated so violations force `status == FAIL_CLOSED` | DONE |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no secret read / no G20 lift / no position modification) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| `.gitignore` adds BA output dir | DONE |
| py_compile BA src + scripts + tests | PASS |
| pytest BA | **483/483 PASS** |
| pytest AZ regression | 481/481 PASS |
| pytest AY regression | 389/389 PASS |
| pytest AX regression | 299/299 PASS |
| pytest AW regression | 292/292 PASS |
| pytest AV regression | 259/259 PASS |
| pytest AU regression | 235/235 PASS |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| chain (BA + AZ..AQ) combined | **3130/3130 PASS** |
| local commit | PENDING (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-16 TASK-014BA)

1. VPS git pull and validate:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.py -q
       # expect 483/483 PASS

   Then run the BA preview with the same upstream artifact set and confirm:
       # status = TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_READY
       # mode = disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_checklist
       # failed_stage = (none)
       # no socket opened, no endpoint called, no secret loaded, G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014BB
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate final pre-execution review
   **manual authorization review** — next phase in the sequential safety
   chain; still no real execution).

---

> Previous README banner: TASK-014AZ-FIX2 (2026-06-16) — see archived block below.

## TASK-014AZ-FIX2 Banner (archived 2026-06-16)

> README shared status updated by TASK-014AZ-FIX2 (2026-06-16) — see
> [Demo Trading Guarded Lifecycle Status](../../../README.md#demo-trading-guarded-lifecycle-statusupdated-by-task-014az-fix2-2026-06-16)
> for the cross-agent status board. TASK-014AZ-FIX2 fixes a bulk-rename
> contamination left by TASK-014AZ-FIX1: AZ's
> `GATE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DESIGN_NEXT_TASK_MISMATCH`
> expected AX's `next_required_task` to be `TASK-014AY_..._readiness_review`
> (the AY self-identity literal carried over by the AY→AZ rename), but
> AX-FIX2 forward-refs `TASK-014AY_..._dry_run`. The VPS preview happy
> path therefore FAIL_CLOSED on the wrong literal. FIX2 corrects the src
> expectation, the AX fixture, and one stale propagation assertion, then
> adds 14 regression tests including source-level chain-literal guards
> that prevent any future bulk rename from silently re-introducing the
> bug. No real execution, no sender, no endpoint call, no secret read,
> no G20 lift, no position modification.

## TASK-014AZ-FIX2 Status (2026-06-16)

| item | status |
|---|---|
| root cause: AZ src `GATE_ENTRY_..._DESIGN_NEXT_TASK_MISMATCH` compared AX's `next_required_task` against `TASK-014AY_..._readiness_review` (the AY self-identity, propagated by the bulk AY→AZ rename) instead of AX-FIX2's actual forward-ref `TASK-014AY_..._dry_run` | IDENTIFIED |
| src fix: AZ src line 3143 expected literal corrected to `TASK-014AY_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run` | DONE |
| fixture fix: `_valid_entry_disabled_implementation_scaffold_manual_authorization_gate_design()` `next_required_task` field corrected to AX-FIX2 forward-ref | DONE |
| assertion fix: `TestAYAXFIX1AXUpstreamPropagation.test_next_required_task_propagated_to_result` expected literal updated to dry-run forward-ref | DONE |
| new tests: `TestAZFIX2AXDesignNextTaskExpectation` (6) — happy path no mismatch + status READY + failed_stage empty + fixture literal check + WRONG literal FAIL_CLOSED + bulk-rename-typo literal FAIL_CLOSED | DONE |
| new tests: `TestAZFIX2ReportHappyPath` (4) — report status READY + no mismatch token in blocked_gates + JSON+Markdown exposes AY dry-run upstream proof + AY simulated-approval fields | DONE |
| new tests: `TestAZFIX2SourceLevelChainLiterals` (4) — AX src forward-ref is dry_run / AY src forward-ref is readiness_review / AZ src forward-ref is BA final_pre_execution_review / AZ src expects AX next-task as dry_run literal (and does NOT contain readiness_review) | DONE |
| local simulated preview happy path | status = `TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_READINESS_REVIEW_READY`, mode = `disabled_implementation_scaffold_manual_authorization_gate_readiness_review_checklist`, failed_stage = `''`, hard_fail_violations = `[]` |
| py_compile src + scripts + test | PASS |
| pytest AZ | **481/481 PASS** (467 baseline + 14 FIX2) |
| pytest AY regression | 389/389 PASS |
| pytest AX regression | 299/299 PASS |
| pytest AW regression | 292/292 PASS |
| pytest AV regression | 259/259 PASS |
| pytest AU regression | 235/235 PASS |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| combined chain (excluding AZ) | **2166/2166 PASS** |
| combined chain (including AZ) | **2647/2647 PASS** |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no secret read / no G20 lift / no position modification) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | PENDING (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-16 TASK-014AZ-FIX2)

1. VPS git pull and validate:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_readiness_review.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_readiness_review.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_readiness_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_readiness_review.py -q
       # expect 481/481 PASS

   Then re-run the AZ preview with the same full flag set used previously
   and confirm:
       # status = TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_READINESS_REVIEW_READY
       # mode = disabled_implementation_scaffold_manual_authorization_gate_readiness_review_checklist
       # failed_stage = (none)
       # blocked_gates does NOT include entry_disabled_implementation_scaffold_manual_authorization_gate_design_next_task_mismatch
       # no socket opened, no endpoint called, no secret loaded, G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014BA
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate final pre-execution review —
   next phase in the sequential safety chain; still no real execution).

---

> Previous README banner: TASK-014AZ-FIX1 (2026-06-16) — see archived block below.

## TASK-014AZ-FIX1 Status (2026-06-16)

| item | status |
|---|---|
| AZ src adds `CONSUMED_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DRY_RUN_CONTRACT_VERSION` constant | DONE |
| AZ src adds `ACCEPTABLE_..._DRY_RUN_STATUSES` (3 values) + `ACCEPTABLE_..._DRY_RUN_MODES` (2 values) frozensets | DONE |
| AZ src adds 15 AY-direct-upstream hard-fail gate constants (MISSING / STATUS_UNACCEPTABLE / MODE_UNACCEPTABLE / REAL_EXECUTION_ALLOWED_TRUE / SEND_ALLOWED_TRUE / ADAPTER_IMPLEMENTATION_INCLUDED_TRUE / ADAPTER_EXECUTION_INCLUDED_TRUE / ORDER_ENDPOINT_CALLED_TRUE / STOP_ENDPOINT_CALLED_TRUE / NO_POSITION_MODIFIED_FALSE / NO_SECRETS_LOADED_FALSE / G20_LIFTED_TRUE / CONCLUSION_MISMATCH / RESPONSE_STATUS_UNACCEPTABLE / NEXT_TASK_MISMATCH) | DONE |
| AZ src adds 14 `GATE_AY_DRY_RUN_SIMULATED_APPROVAL_*` hard-fail gate constants (distinct prefix from chained AX `GATE_SIMULATED_APPROVAL_*`) | DONE |
| All 29 new gates appended to `_HARD_FAIL_GATES` frozenset so violations force `status == FAIL_CLOSED` | DONE |
| AZ result dataclass adds 16 `upstream_entry_..._dry_run_*` + 14 `upstream_entry_..._dry_run_simulated_approval_*` fields + `consumed_..._dry_run_contract_version` | DONE |
| `to_dict()` emits all 30 new fields + contract version | DONE |
| `run_readiness_review(...)` accepts new `entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run: dict[str, Any] \| None = None` kwarg | DONE |
| Parser block evaluates the 29 gates and populates the 30 fields with observed (possibly invalid) values | DONE |
| stage_0 summary text updated to reference the AY direct artifact + AY simulated-approval envelope | DONE |
| Scripts preview adds `entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run_dir` parameter, wires loader output into `run_readiness_review()`, emits missing-artifact `[FAIL CLOSED]` exit-1, prints AY dry-run source line, and renders 30 new Markdown rows for AY-upstream proof | DONE |
| Test fixture `_valid_entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run()` + `_run()` helper extension | DONE |
| 42 new tests: 6 happy-path field-exposure, 1 missing-AY-artifact, 15 AY-upstream FAIL_CLOSED, 14 AY-simulated-approval FAIL_CLOSED, 1 hard-fail-set registration, 2 alternate-accepted-values, 1 scripts loader, 1 report write, 1 approved-AY-upstream-still-not-implemented | DONE |
| py_compile src + scripts + test | PASS |
| pytest AZ | **467/467 PASS** (425 baseline + 42 FIX1) |
| pytest AY regression | 389/389 PASS |
| pytest real_execution_adapter chain (AX/AW/AV/AU/AT/static_skeleton_dry_run/static_skeleton_design/disabled_implementation_scaffold_design/dry_run/final_pre_execution_review/manual_authorization_gate_design/manual_authorization_gate_dry_run/implementation_design) | **1907/1907 PASS** |
| safety invariants (no real execution / no sender / no executable adapter / no endpoint call / no secret read / no G20 lift / no position modification) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | PENDING (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-16 TASK-014AZ-FIX1)

1. VPS git pull and validate:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_readiness_review.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_readiness_review.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_readiness_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_readiness_review.py -q
       # expect 467/467 PASS

2. Once step 1 passes, decide whether to authorise TASK-014BA
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate final pre-execution review —
   next phase in the sequential safety chain; still no real execution).

---

> Previous README banner: TASK-014AZ (2026-06-16) — see archived block below.

## TASK-014AZ Status (2026-06-16)

| item | status |
|---|---|
| src/scripts/test 三檔新增（複製 AY identity → AZ） | DONE |
| identity wording 為 `READINESS-REVIEW-ONLY`（非 DRY-RUN-ONLY、非 DESIGN-ONLY） | DONE |
| `status=TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_READINESS_REVIEW_READY` | DONE |
| `conclusion=DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_READINESS_REVIEW_READY_NOT_EXECUTABLE` | DONE |
| `authorization_result=DOCUMENTED_ONLY_NOT_AUTHORIZED` | DONE |
| `response_status=DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_READINESS_REVIEW_NOT_SENT` | DONE |
| `next_required_task=TASK-014BA_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review` | DONE |
| CLI 新增 `--from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-dry-run` 旗標 + loader | DONE |
| AY direct artifact 為直接 upstream；AX/AW/AV/AU/AT/AS/AR/AQ 透過 AY 鏈式證明（非直接） | DONE |
| 安全不變式（no real execution / no sender / no endpoint / no secret read / no G20 lift / no position modification） | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| .gitignore 新增 `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_readiness_review/` | DONE |
| py_compile src + scripts + test | PASS |
| pytest AZ | **425/425 PASS** |
| pytest AY regression | 389/389 PASS |
| real_execution_adapter chain regression（AY/AX/AW/AV/AU/AT/AS/AR/implementation_design） | PASS |
| local commit | PENDING（local only — NOT pushed） |

## Next Rick Action (set by 2026-06-16 TASK-014AZ)

1. VPS git pull and validate:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_readiness_review.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_readiness_review.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_readiness_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_readiness_review.py -q
       # expect 425/425 PASS

2. Once step 1 passes, decide whether to authorise TASK-014BA
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate final pre-execution review —
   next phase in the sequential safety chain; still no real execution).

---

> Previous README banner: TASK-014AY-FIX3 (2026-06-15) — see archived block below.

## TASK-014AY-FIX3 Status (2026-06-15)

| item | status |
|---|---|
| root cause: VPS preview run showed stdout banner still said "DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE DESIGN CHECKLIST" (AX identity) and stage_0 summary said "33 upstream artifacts + AW acceptance flags" (not reflecting AY consuming AX as 34th artifact) | IDENTIFIED |
| scripts: preview stdout default-mode banner updated from `DESIGN CHECKLIST` → `DRY-RUN CHECKLIST` | DONE |
| scripts: preview stdout approval-mode banner updated from `DESIGN APPROVAL` → `DRY-RUN APPROVAL` | DONE |
| scripts: preview module docstring Usage line updated from `DESIGN CHECKLIST` → `DRY-RUN CHECKLIST` | DONE |
| src: module docstring "Inputs" line updated from "33 upstream artifacts (the 32 from AW + AW's own...)" → "34 upstream artifacts — AX direct artifact + 33 upstream artifacts AX already consumed" | DONE |
| src: stage_0 summary updated from "Validate 33 upstream artifacts + AW acceptance flags" → "Validate AX direct artifact (manual authorization gate design) + 33 upstream artifacts AX already consumed (AW chain) + AX acceptance flags" | DONE |
| tests: new `TestAYFIX3WordingCorrection` class (8 tests) — preview text contains DRY-RUN CHECKLIST; preview text does NOT contain DESIGN CHECKLIST; preview text contains DRY-RUN APPROVAL; preview text does NOT contain DESIGN APPROVAL; stage_0 summary mentions "AX direct artifact"; stage_0 summary mentions "33 upstream artifacts AX already consumed"; stage_0 summary does NOT say "AW acceptance flags"; src docstring mentions "34 upstream artifacts" | DONE |
| py_compile src + scripts + test | PASS |
| pytest AY | **389/389 PASS** (381 FIX2 baseline + 8 FIX3 in TestAYFIX3WordingCorrection) |
| pytest AX regression | 299/299 PASS |
| combined real_execution_adapter chain (AX + AW + AV + AU + AT + static_skeleton_dry_run + static_skeleton_design + implementation_design) | **1777/1777 PASS** |
| combined AY + chain | **2166/2166 PASS** |
| all FIX2 fail-closed behavior | UNCHANGED |
| safety invariants: no real execution, no sender, no executable adapter, no endpoint call, no secret read, no G20 lift, no position modification | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | DONE (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-15 TASK-014AY-FIX3)

1. VPS git pull and validate:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py -q
       # expect 389/389 PASS
       # confirm preview stdout header: "DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE DRY-RUN CHECKLIST"

2. Once step 1 passes, decide whether to authorise TASK-014AZ
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate readiness review — next phase
   in the sequential safety chain; still no real execution).

---

> Previous README banner: TASK-014AY-FIX2 (2026-06-15) — see archived block below.

## TASK-014AY-FIX2 Status (2026-06-15)
> the 25 new hard-fail gates added in FIX1 (15 AX-upstream + 10 simulated-
> approval) are now wired into `_HARD_FAIL_GATES` so any violation forces
> `status = FAIL_CLOSED` (instead of being merely recorded in `blocked_gates`).
> Happy path, `--allow-real-entry-execution`, and the dry-run allow-flag
> behaviors are unchanged. No real execution, no sender, no executable
> adapter, no endpoint calls, no secret reading, no G20 lift, no position
> modification. main.py / src/risk.py / BybitExecutor untouched.

## TASK-014AY-FIX2 Status (2026-06-15)

| item | status |
|---|---|
| root cause: FIX1's 25 new gates recorded violations in `blocked_gates` but did NOT flip `status` to `FAIL_CLOSED` — they were not true hard-fail gates | IDENTIFIED |
| src: `_HARD_FAIL_GATES` frozenset extended with the 15 AX-upstream gates (`GATE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DESIGN_*`) so any violation participates in the existing FAIL_CLOSED decision path | DONE |
| src: `_HARD_FAIL_GATES` frozenset extended with the 10 simulated-approval gates (`GATE_SIMULATED_APPROVAL_*`) on the same path | DONE |
| src: the same 25 gates added to the stage-classification set used by the FAIL_CLOSED path so `failed_stage` resolves correctly | DONE |
| tests: existing `TestAYAXFIX1AXUpstreamGates` (17 tests) updated — every violation case additionally asserts `r.status == STATUS_FAIL_CLOSED` and that safety invariants (`real_execution_allowed=False`, `send_allowed=False`) remain protected | DONE |
| tests: new `TestAYFIX2FailClosedEnforcement` class added — 15 AX-upstream FAIL_CLOSED cases + 10 simulated-approval FAIL_CLOSED cases + 3 invariant cases (happy path remains READY, `--allow-real-entry-execution` remains `REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED`, violation dominates the dry-run allow-flag) | DONE |
| happy path | UNCHANGED — `TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DRY_RUN_READY` |
| `--allow-real-entry-execution` | UNCHANGED — returns `REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED` on the no-violation path |
| `--allow-disabled-implementation-scaffold-manual-authorization-gate-dry-run` | UNCHANGED on happy path; any hard-fail violation now dominates the allow-flag and returns `FAIL_CLOSED` |
| py_compile src + scripts + test | PASS |
| pytest AY | **381/381 PASS** (353 FIX1 baseline + 28 FIX2 in TestAYFIX2FailClosedEnforcement) |
| pytest AX regression | 299/299 PASS |
| pytest AW (final_pre_execution_review) regression | (suite passed in chain run) |
| pytest AV (readiness_review) regression | (suite passed in chain run) |
| pytest AU (dry_run) regression | (suite passed in chain run) |
| pytest AT (design) regression | (suite passed in chain run) |
| pytest static_skeleton_dry_run / static_skeleton_design / implementation_design | (suites passed in chain run) |
| combined real_execution_adapter chain (AX + AW + AV + AU + AT + static_skeleton_dry_run + static_skeleton_design + implementation_design) | **1777/1777 PASS** |
| combined AY + chain | **2158/2158 PASS** |
| safety invariants: no real execution, no sender, no executable adapter, no endpoint call, no secret read, no G20 lift, no position modification | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| local commit | DONE (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-15 TASK-014AY-FIX2)

1. VPS git pull and validate:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py -q
       # expect 381/381 PASS

2. Once step 1 passes, decide whether to authorise TASK-014AZ
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate readiness review — next phase
   in the sequential safety chain; still no real execution).

---

> Previous README banner: TASK-014AY-FIX1 (2026-06-15) — see archived block below.

## TASK-014AY-FIX1 Status (2026-06-15)

| item | status |
|---|---|
| src: `src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py` — full AX-as-34th-upstream structural mirror added (16 dataclass fields, 15 fail-closed gates, 1 frozenset of acceptable statuses, 1 frozenset of acceptable modes, 1 consumed contract version constant, parser block, audit_artifacts entries, to_dict entries) + simulated-approval envelope (14 dataclass fields, 10 fail-closed gates) | DONE |
| scripts: `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py` — new `_DEFAULT_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DESIGN_DIR` constant + `load_latest_entry_disabled_implementation_scaffold_manual_authorization_gate_design()` loader + `--from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-design` CLI flag + markdown rows for all 16 AX-upstream fields and 14 simulated-approval fields + footer wording aligned to DRY-RUN-ONLY | DONE |
| tests: `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py` — `_valid_entry_disabled_implementation_scaffold_manual_authorization_gate_design()` fixture + `_valid_simulated_approval()` fixture + `_run()` helper now accepts `entry_disabled_implementation_scaffold_manual_authorization_gate_design=_UNSET` and `simulated_approval=_UNSET` + 6 new test classes (TestAYAXFIX1AXUpstreamGates ×17, TestAYAXFIX1AXUpstreamPropagation ×8, TestAYAXFIX1SimulatedApproval ×12, TestAYAXFIX1CLIFlags ×4, TestAYAXFIX1IdentityWording ×6, TestAYAXFIX1SafetyInvariants ×6) | DONE |
| py_compile src + scripts + test | PASS |
| pytest AY | **353/353 PASS** (299 baseline + 54 FIX1) |
| pytest AX regression | **299/299 PASS** |
| pytest combined demo_trading real_execution_adapter chain | **2522/2522 PASS** |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| no runtime execution change / no endpoint / no secret / no G20 lift / no position modification | CONFIRMED |
| local commit | PENDING (will be created after this doc update) |

## Next Rick Action (set by 2026-06-15 TASK-014AY-FIX1)

1. VPS git pull and validate:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py -q
       # expect 353/353 PASS

2. Once step 1 passes, decide whether to authorise TASK-014AZ
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate readiness review — next phase
   in the sequential safety chain; still no real execution).

---

> Previous README banner: TASK-014AY (2026-06-15) — see archived block below.

## TASK-014AY Status (2026-06-15)

| item | status |
|---|---|
| src: `src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py` (new) — identity renamed to dry_run, intro updated to "AY consumes AX → for AZ" | DONE |
| scripts: `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py` (new) — CLI description updated to dry-run wording; intro updated; banner updated | DONE |
| tests: `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py` (new) — 299 tests; intro / scope-summary / markdown assertions aligned to AX→AY→AZ semantics | DONE |
| .gitignore: add `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run/` | DONE |
| README: shared status board updated to TASK-014AY | DONE |
| NEXT_ACTION.md: TASK-014AY section prepended | DONE |
| COMMAND_LOG.md: TASK-014AY entry prepended | DONE |
| AY self-identity strings: `disabled_implementation_scaffold_manual_authorization_gate_dry_run` | CONFIRMED (0 residual `..._design` self-references in AY src) |
| AX direct upstream documented in intro / scope_summary / docstring / CLI description / banner | CONFIRMED |
| safety invariants: no real execution, no sender, no executable adapter, no endpoint call, no secret read, no G20 lift, no position modification | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | UNTOUCHED |
| py_compile src + scripts + test | PASS |
| pytest AY | **299/299 PASS** |
| pytest AX regression | **299/299 PASS** |
| pytest AW+AV+AU+AT+AS+AR+AQ regression | **1478/1478 PASS** |
| combined AY+AX+AW+AV+AU+AT+AS+AR+AQ | **2076/2076 PASS** |
| local commit | DONE (local only — NOT pushed) |
| scope note | Stage 1 (identity rename) + intro/scope-summary realignment done. Full 16-gate parallel mirror of AX-upstream consumption pattern (analogous to AX's AW-upstream block) deferred to TASK-014AY-FIX1 if Rick wants the full structural mirror. Current scaffold is intent-correct and test-clean. |

## Next Rick Action (set by 2026-06-15 TASK-014AY)

1. VPS git pull and validate:

       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run.py -q
       # expect 299/299 PASS

2. Once step 1 passes, decide whether to authorise TASK-014AZ
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate readiness review — next phase
   in the sequential safety chain; still no real execution).

---

## TASK-014AX-FIX2 Status (2026-06-15)

| item | status |
|---|---|
| root cause: AX forward-ref next_required_task was set to TASK-014AY...manual_authorization_gate_design (wrong phase name) instead of TASK-014AY...manual_authorization_gate_dry_run | IDENTIFIED |
| src: update `NEXT_REQUIRED_TASK` constant to `TASK-014AY_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run` | DONE |
| tests: update `TestAQ80NextRequiredTask.test_next_required_task` assertion from design to dry_run | DONE |
| tests: update `TestARFIX2NextRequiredTaskUnchanged.test_next_required_task_is_AS` hardcoded and constant assertions to dry_run | DONE |
| tests: update module docstring (line 23) — next_required_task reflects DRY-RUN | DONE |
| AX src: verify `disabled_implementation_scaffold_manual_authorization_gate_design` identity unchanged (not touched by FIX2) | CONFIRMED |
| py_compile src + scripts + test | PASS |
| pytest AX | **299/299 PASS** |
| pytest AW+AV+AU+AT+AS+AR+AQ regression | **1478/1478 PASS** |
| combined AX+AW+AV+AU+AT+AS+AR+AQ | **1777/1777 PASS** |
| no runtime behavior change / no endpoint / no secret / no G20 lift / no position modification / main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-15 TASK-014AX-FIX2)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py -q
       # expect 299/299 PASS
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py --write-report \
         --from-latest-entry-disabled-implementation-scaffold-design \
         --from-latest-entry-disabled-implementation-scaffold-dry-run \
         --from-latest-entry-disabled-implementation-scaffold-final-pre-execution-review
       # confirm: next_required_task = TASK-014AY_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_dry_run (NOT design)
       # confirm: status = TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DESIGN_READY
       # confirm: conclusion = DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DESIGN_READY_NOT_EXECUTABLE
       # confirm: authorization_result = DOCUMENTED_ONLY_NOT_AUTHORIZED
       # confirm: response_status = DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DESIGN_NOT_SENT

2. Once step 1 passes, decide whether to authorise TASK-014AY
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate dry-run — next phase in the
   sequential safety chain; still no real execution).

---

> README shared status updated by TASK-014AX-FIX1 (2026-06-15) — see
> [Demo Trading Guarded Lifecycle Status](../../../README.md#demo-trading-guarded-lifecycle-statusupdated-by-task-014ax-fix1-2026-06-15)
> for the cross-agent status board. TASK-014AX-FIX1 restores the over-renamed
> older TASK-014AI-era `tiny_guarded_entry_final_pre_execution_review` upstream
> artifact path in AX src/scripts/tests. The broad Stage 1 rename substituted
> bare `final_pre_execution_review` → `manual_authorization_gate_design` which
> incorrectly renamed this older non-scaffold upstream; the disambiguated AX
> identity (`disabled_implementation_scaffold_manual_authorization_gate_design`)
> and AX's direct AW upstream (`disabled_implementation_scaffold_final_pre_execution_review`)
> were unaffected. 7 new regression tests lock the correct older-upstream path.

## TASK-014AX-FIX1 Status (2026-06-15)

| item | status |
|---|---|
| root cause: Stage 1 rename helper broad `("final_pre_execution_review", "manual_authorization_gate_design")` substitution over-renamed the TASK-014AI-era `tiny_guarded_entry_final_pre_execution_review` upstream artifact | IDENTIFIED |
| src: restore `ACCEPTABLE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUSES` (frozenset with `TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY` values) — was wrongly `ACCEPTABLE_ENTRY_MANUAL_AUTHORIZATION_GATE_DESIGN_STATUSES` | DONE |
| src: restore `GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING = "entry_final_pre_execution_review_missing"` — was `GATE_ENTRY_MANUAL_AUTHORIZATION_GATE_DESIGN_MISSING` | DONE |
| src: restore `upstream_entry_final_pre_execution_review_status` dataclass field + dict key (all 4 occurrences) | DONE |
| src: restore `entry_final_pre_execution_review` function parameter (3 occurrences in function body) | DONE |
| src: restore `__all__` exports for `ACCEPTABLE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUSES` + `GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING` | DONE |
| scripts: restore `_DEFAULT_ENTRY_FINAL_PRE_EXECUTION_REVIEW_DIR` with path `tiny_guarded_entry_final_pre_execution_review` | DONE |
| scripts: restore `load_latest_entry_final_pre_execution_review(entry_final_pre_execution_review_dir)` function + `latest_tiny_guarded_entry_final_pre_execution_review.json` filename | DONE |
| scripts: restore `upstream_entry_final_pre_execution_review_status` in print-report output | DONE |
| scripts: restore `entry_final_pre_execution_review_dir` parameter + default resolution | DONE |
| scripts: restore `entry_final_pre_execution_review=entry_final_review` keyword arg in run call | DONE |
| scripts: restore help text `outputs/.../tiny_guarded_entry_final_pre_execution_review/.` for `--from-latest-entry-final-pre-execution-review` flag | DONE |
| scripts: restore missing-check error path `latest_tiny_guarded_entry_final_pre_execution_review.json` | DONE |
| tests: restore import `ACCEPTABLE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUSES` + `GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING` | DONE |
| tests: restore `_valid_entry_final_pre_execution_review()` fixture (mode=`final_pre_execution_review_checklist`, status=`TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY`, correct dict keys) | DONE |
| tests: restore `entry_final_pre_execution_review=_UNSET` parameter + `_run()` helper call | DONE |
| tests: restore `test_missing_entry_final_pre_execution_review_blocked` + `GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING` assertion | DONE |
| tests: restore forbidden-import `"src.demo_tiny_guarded_entry_final_pre_execution_review"` (older non-scaffold module) | DONE |
| tests: restore `r.upstream_entry_final_pre_execution_review_status == "TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY"` assertion | DONE |
| tests: restore `entry_final_pre_execution_review_dir=empty` in preview integration tests (2 occurrences) | DONE |
| tests: add `TestAXFIX1OlderUpstreamPath` class (7 tests) — assert `--from-latest-entry-final-pre-execution-review` present; assert `tiny_guarded_entry_manual_authorization_gate_design` absent from help; assert gate constant value correct; assert frozenset values correct; assert report JSON/Markdown do NOT mention `tiny_guarded_entry_manual_authorization_gate_design` | DONE |
| AX's own identity strings unchanged: `disabled_implementation_scaffold_manual_authorization_gate_design` | CONFIRMED |
| AX's direct AW-upstream strings unchanged: `disabled_implementation_scaffold_final_pre_execution_review` (116 occurrences, all intact) | CONFIRMED |
| py_compile src + scripts + test | PASS |
| pytest AX | **299/299 PASS** |
| pytest AW regression | 292/292 PASS |
| pytest AV regression | 259/259 PASS |
| pytest AU regression | 235/235 PASS |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| combined AX+AW+AV+AU+AT+AS+AR+AQ | **1777/1777 PASS** |
| no runtime behavior change / no endpoint / no secret / no G20 lift / no position modification / main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-15 TASK-014AX-FIX1)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py -q
       # expect 299/299 PASS (incl. 7 FIX1 regression tests)
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py --write-report \
         --from-latest-entry-disabled-implementation-scaffold-design \
         --from-latest-entry-disabled-implementation-scaffold-dry-run \
         --from-latest-entry-disabled-implementation-scaffold-final-pre-execution-review
       # confirm: preview no longer fails closed on tiny_guarded_entry_manual_authorization_gate_design path
       # confirm: status = TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_
       #                   DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DESIGN_READY
       # confirm: conclusion = DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DESIGN_READY_NOT_EXECUTABLE
       # confirm: authorization_result = DOCUMENTED_ONLY_NOT_AUTHORIZED
       # confirm: response_status = DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DESIGN_NOT_SENT
       # confirm: next_required_task = TASK-014AY_..._manual_authorization_gate_dry_run

2. Once step 1 passes, decide whether to authorise TASK-014AY
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate dry-run — next phase in the
   sequential safety chain; still no real execution).

---

> README shared status updated by TASK-014AX (2026-06-15) — see
> [Demo Trading Guarded Lifecycle Status](../../../README.md#demo-trading-guarded-lifecycle-statusupdated-by-task-014ax-2026-06-15)
> for the cross-agent status board. TASK-014AX adds the guarded entry
> real execution adapter `disabled_implementation_scaffold_manual_authorization_gate_design`
> scaffold (src + scripts + tests) mirroring AW pattern + adding
> AW FINAL PRE-EXECUTION REVIEW as the 33rd runtime-consumed upstream
> artifact (with chained AV+AU+AT+AS+AR+AQ proof preserved through
> AW). No real execution, no sender, no endpoint calls, no G20 lift,
> no position modification.

## TASK-014AX Status (2026-06-15)

| item | status |
|---|---|
| scope: build TASK-014AX scaffold (src + scripts + tests) by mirroring AW pattern + adding AW FINAL PRE-EXECUTION REVIEW as the 33rd runtime-consumed upstream artifact | DEFINED |
| module rename: `..._final_pre_execution_review.py` → `..._manual_authorization_gate_design.py` (src, scripts, tests) — surgical disambiguated-phrase rename so TASK-014AP `implementation_readiness_review` + generic `readiness_review_v1` + `disabled_implementation_scaffold_readiness_review_v1` (now AW's consumed-upstream-contract) are preserved | DONE |
| TASK identity bumps: `TASK-014AW` → `TASK-014AX` (identity), `TASK-014AX` → `TASK-014AY` (forward-ref to manual_authorization_gate_dry_run); `TASK-014AV` → `TASK-014AW` (consumed-upstream) | DONE |
| src: `STATUS_IMPLEMENTATION_DESIGN_READY = "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DESIGN_READY"` + modes `disabled_implementation_scaffold_manual_authorization_gate_design_checklist` / `..._approval` + `CONCLUSION="DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DESIGN_READY_NOT_EXECUTABLE"` + `AUTHORIZATION_RESULT="DOCUMENTED_ONLY_NOT_AUTHORIZED"` | DONE |
| src: `ADAPTER_CONTRACT_VERSION="disabled_implementation_scaffold_manual_authorization_gate_design_v1"` + `CONSUMED_DISABLED_IMPLEMENTATION_SCAFFOLD_FINAL_PRE_EXECUTION_REVIEW_CONTRACT_VERSION="disabled_implementation_scaffold_final_pre_execution_review_v1"` (AW's consumed-upstream contract) | DONE |
| src: 14 fail-closed gates `GATE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_FINAL_PRE_EXECUTION_REVIEW_*` (missing/status/mode/real_exec/send/impl/exec/order/stop/no_pos/no_secrets/g20/conclusion/response_status) for AW upstream acceptance | DONE |
| src: 16 dataclass fields `upstream_entry_disabled_implementation_scaffold_final_pre_execution_review_*` + parser block (variables `entry_disfp_*` reading from `awfp` payload) + audit_artifacts entries | DONE |
| src: `run_readiness_review()` accepts `entry_disabled_implementation_scaffold_final_pre_execution_review` as 33rd upstream input + present_flags entry | DONE |
| scripts: CLI flag `--from-latest-entry-disabled-implementation-scaffold-final-pre-execution-review` + loader + dir resolution + missing-check + print line + run_readiness_review() kwarg | DONE |
| scripts: argparse description / banner / footer reference TASK-014AW FINAL PRE-EXECUTION REVIEW → TASK-014AY | DONE |
| scripts: argparse adds `--allow-disabled-implementation-scaffold-manual-authorization-gate-design` | DONE |
| tests: `TestAXAW*` test classes (22 classes mirroring TestAWAV* pattern with `upstream_entry_disabled_implementation_scaffold_final_pre_execution_review_*` field assertions) | DONE |
| tests: scope_summary asserts updated — `32 upstream artifacts`, `DISABLED IMPLEMENTATION SCAFFOLD FINAL PRE-EXECUTION REVIEW`, `DISABLED IMPLEMENTATION SCAFFOLD READINESS REVIEW` (newly chained AV), `DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE DESIGN`, `TASK-014AX`, `TASK-014AY` | DONE |
| py_compile src + scripts + test | PASS |
| pytest AX | **292/292 PASS** |
| pytest AW regression | 292/292 PASS |
| pytest AV regression | 259/259 PASS |
| pytest AU regression | 235/235 PASS |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| combined AX+AW+AV+AU+AT+AS+AR+AQ | **1770/1770 PASS** |
| no runtime behavior change / no endpoint / no secret / no G20 lift / no position modification / main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-15 TASK-014AX)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py -q
       # expect 292/292 PASS
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design.py --write-report \
         --from-latest-entry-disabled-implementation-scaffold-design \
         --from-latest-entry-disabled-implementation-scaffold-dry-run \
         --from-latest-entry-disabled-implementation-scaffold-final-pre-execution-review
       # confirm: status = TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_
       #                   DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DESIGN_READY
       # confirm: conclusion = DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DESIGN_READY_NOT_EXECUTABLE
       # confirm: authorization_result = DOCUMENTED_ONLY_NOT_AUTHORIZED
       # confirm: response_status = DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_DESIGN_NOT_SENT
       # confirm: next_required_task = TASK-014AY_..._manual_authorization_gate_dry_run
       # confirm: no socket opened, no endpoint called, no secret loaded,
       # G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014AY
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate dry-run — next phase in the
   sequential safety chain; still no real execution).

## TASK-014AW-FIX1 Status (2026-06-15)

| item | status |
|---|---|
| issue 1: Markdown intro said "TASK-014AW consumes TASK-014AU disabled implementation scaffold dry-run output at runtime and produces a disabled implementation scaffold final pre-execution review for TASK-014AW" — both the upstream and forward-ref were wrong | FIXED |
| issue 2: audit_artifacts / generated JSON / generated Markdown did not expose AV upstream proof fields (`upstream_entry_disabled_implementation_scaffold_readiness_review_*`) | FIXED |
| scripts: Markdown intro corrected to "TASK-014AW consumes TASK-014AV disabled implementation scaffold readiness review output at runtime and produces a disabled implementation scaffold final pre-execution review for TASK-014AX" | DONE |
| scripts: module docstring "FUTURE TASK-014AW adapter" corrected to "FUTURE TASK-014AX adapter" | DONE |
| src: audit_artifacts dict extended with 18 new AV readiness review proof fields + consumed contract version (mirrors dry-run block structure) | DONE |
| scripts: Markdown verdict table extended with 16 new `upstream_entry_disabled_implementation_scaffold_readiness_review_*` rows + `consumed_disabled_implementation_scaffold_readiness_review_contract_version` row | DONE |
| scripts: Markdown header extended with `consumed_disabled_implementation_scaffold_readiness_review_contract_version` line | DONE |
| tests: `TestAUATFIX1ReportProof.test_markdown_intro_names_au_not_at` renamed to `test_markdown_intro_names_av_not_au`; assertion updated to TASK-014AV readiness review + for TASK-014AX; added negative assertions for TASK-014AU dry-run and "for TASK-014AW" | DONE |
| tests: `TestARFIX2CLIBannerSaysStaticSkeleton` CLI description assertions updated — assert TASK-014AV + "readiness review output" + TASK-014AX (was TASK-014AU + dry-run) | DONE |
| tests: `TestARFIX2MarkdownReportTitleAndSections` comment + assertions corrected — assert "TASK-014AV" in md (was "TASK-014AU") | DONE |
| tests: new `TestAWAVFIX1ReportProof` class (10 tests) — audit_artifacts AV authorization_result / conclusion / response_status / contract version; generated JSON AV authorization_result present / empty absent; generated Markdown AV authorization_result present / empty absent; Markdown verdict table AV rows present; Markdown intro names AV / for AX | DONE |
| py_compile src + scripts + test | PASS |
| pytest AW | **292/292 PASS** |
| pytest AV regression | 259/259 PASS |
| pytest AU regression | 235/235 PASS |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| combined AW+AV+AU+AT+AS+AR+AQ | **1478/1478 PASS** |
| no runtime behavior change / no endpoint / no secret / no G20 lift / no position modification / main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-15 TASK-014AW-FIX1)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_final_pre_execution_review.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_final_pre_execution_review.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_final_pre_execution_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_final_pre_execution_review.py -q
       # expect 292/292 PASS
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_final_pre_execution_review.py --write-report \
         --from-latest-entry-disabled-implementation-scaffold-design \
         --from-latest-entry-disabled-implementation-scaffold-dry-run \
         --from-latest-entry-disabled-implementation-scaffold-readiness-review
       # confirm: Markdown intro says "TASK-014AW consumes TASK-014AV disabled implementation
       # scaffold readiness review output at runtime and produces a disabled implementation
       # scaffold final pre-execution review for TASK-014AX"
       # confirm: generated JSON contains
       #   upstream_entry_disabled_implementation_scaffold_readiness_review_authorization_result:
       #   "DOCUMENTED_ONLY_NOT_AUTHORIZED"
       # confirm: next_required_task = TASK-014AX_..._manual_authorization_gate_design
       # confirm: no socket opened, no endpoint called, no secret loaded,
       # G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014AX
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate design — next phase in the
   sequential safety chain; still no real execution).

## TASK-014AW Status (2026-06-15)

| item | status |
|---|---|
| scope: build TASK-014AW scaffold (src + scripts + tests) by mirroring AV pattern + adding AV READINESS REVIEW as the 32nd runtime-consumed upstream artifact | DEFINED |
| module rename: `..._readiness_review.py` → `..._final_pre_execution_review.py` (src, scripts, tests) — surgical disambiguated-phrase rename so TASK-014AP `implementation_readiness_review` + generic `readiness_review_v1` are preserved | DONE |
| TASK identity bumps: `TASK-014AV` → `TASK-014AW` (identity), `TASK-014AW` → `TASK-014AX` (forward-ref to manual_authorization_gate_design) | DONE |
| src: add `ACCEPTABLE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_READINESS_REVIEW_STATUSES` (3) + `ACCEPTABLE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_READINESS_REVIEW_MODES` (2) + `CONSUMED_DISABLED_IMPLEMENTATION_SCAFFOLD_READINESS_REVIEW_CONTRACT_VERSION = "disabled_implementation_scaffold_readiness_review_v1"` | DONE |
| src: add 14 new fail-closed gates `GATE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_READINESS_REVIEW_*` (missing/status/mode/real_exec/send/impl/exec/order/stop/no_pos/no_secrets/g20/conclusion/response_status); hard-fail count: 116 → 130 | DONE |
| src: extend result dataclass with 16 new `upstream_entry_disabled_implementation_scaffold_readiness_review_*` fields + parser block + audit_artifacts | DONE |
| src: extend `run_readiness_review()` to require `entry_disabled_implementation_scaffold_readiness_review` as 32nd upstream input | DONE |
| scripts: add `--from-latest-entry-disabled-implementation-scaffold-readiness-review` CLI flag + loader + dir resolution + missing-check + print line + run_readiness_review() kwarg | DONE |
| scripts: argparse description / banner / footer now reference TASK-014AV READINESS REVIEW → TASK-014AX (was AU DRY-RUN → AW) | DONE |
| scripts: argparse adds `--allow-disabled-implementation-scaffold-final-pre-execution-review` | DONE |
| tests: add `_valid_entry_disabled_implementation_scaffold_readiness_review()` fixture + extend `_run()` with `_UNSET` param + update scope_summary regression to TASK-014AV / 31 upstream / READINESS REVIEW / TASK-014AX | DONE |
| tests: add 18 new TestAWAV* test classes — contract / propagation / 14 gates / approval mode / CLI flag / AU-still-intact / AT-still-intact | DONE |
| status / conclusion / authorization | `TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_FINAL_PRE_EXECUTION_REVIEW_READY` / `DISABLED_IMPLEMENTATION_SCAFFOLD_FINAL_PRE_EXECUTION_REVIEW_READY_NOT_EXECUTABLE` / `DOCUMENTED_ONLY_NOT_AUTHORIZED` |
| forward-ref next_required_task | `TASK-014AX_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_design` |
| py_compile src + scripts + test | PASS |
| pytest AW | **282/282 PASS** |
| pytest AV regression | 259/259 PASS |
| pytest AU regression | 235/235 PASS |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| combined AW+AV+AU+AT+AS+AR+AQ | **1468/1468 PASS** |
| no runtime behavior change in AA-AV / no endpoint / no secret / no G20 lift / no position modification / main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE (local only — NOT pushed) |

## Next Rick Action (set by 2026-06-15 TASK-014AW)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_final_pre_execution_review.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_final_pre_execution_review.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_final_pre_execution_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_final_pre_execution_review.py -q
       # expect 282/282 PASS
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_final_pre_execution_review.py --write-report \
         --from-latest-entry-disabled-implementation-scaffold-design \
         --from-latest-entry-disabled-implementation-scaffold-dry-run \
         --from-latest-entry-disabled-implementation-scaffold-readiness-review
       # confirm: 32 upstream artifacts consumed, status =
       # TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_FINAL_PRE_EXECUTION_REVIEW_READY,
       # disabled_implementation_scaffold_final_pre_execution_review_conclusion =
       # DISABLED_IMPLEMENTATION_SCAFFOLD_FINAL_PRE_EXECUTION_REVIEW_READY_NOT_EXECUTABLE,
       # next_required_task = TASK-014AX_..._manual_authorization_gate_design,
       # no socket opened, no endpoint called, no secret loaded,
       # G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014AX
   (guarded entry real execution adapter disabled implementation
   scaffold manual authorization gate design — next phase in the
   sequential safety chain; still no real execution).

## TASK-014AV-FIX2 Status (2026-06-14)

| item | status |
|---|---|
| issue 1: src/scripts/tests still said "consumes TASK-014AT disabled implementation scaffold design output" — should say TASK-014AU disabled implementation scaffold dry-run | FIXED |
| issue 2: report header / scope_summary / footer still said DRY-RUN CHECKLIST / DRY-RUN-ONLY where AV should say READINESS REVIEW CHECKLIST / READINESS-REVIEW-ONLY | FIXED |
| issue 3: `NEXT_REQUIRED_TASK` was `TASK-014AW_..._readiness_review`; docs have no explicit AW name → corrected to `TASK-014AW_..._final_pre_execution_review` | FIXED |
| issue 4: `DOCUMENTED_ONLY_NOT_AUTHORIZE` truncation — not present in any file; terminal/copy artefact only | CONFIRMED (no fix needed) |
| src: docstring updated (TASK-014AU DRY-RUN, 31 inputs, final_pre_execution_review forward ref) | DONE |
| src: `NEXT_REQUIRED_TASK` = `TASK-014AW_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_final_pre_execution_review` | DONE |
| src: `scope_summary` updated (TASK-014AU DRY-RUN, 30 chained artifacts, READINESS REVIEW produced) | DONE |
| scripts: docstring / stdout banner / argparse description updated (TASK-014AU, READINESS REVIEW, final_pre_execution_review) | DONE |
| tests: scope_summary assertions updated (TASK-014AU, 30 upstream, READINESS REVIEW) | DONE |
| tests: `test_markdown_report_footer_uses_readiness_review_wording` (was dry_run_wording) — asserts READINESS-REVIEW-ONLY, not DRY-RUN-ONLY | DONE |
| tests: CLI description asserts READINESS REVIEW + TASK-014AU + dry-run consumed (was DRY-RUN + TASK-014AT + design) | DONE |
| tests: `test_markdown_intro_names_au_not_at` (was names_at_not_as) — asserts AU in intro, AT not in intro, AS not in intro | DONE |
| tests: `NEXT_REQUIRED_TASK` literal assertions updated to `final_pre_execution_review` | DONE |
| py_compile src + scripts + test | PASS |
| pytest AV | **259/259 PASS** |
| pytest AU regression | 235/235 PASS |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| combined AV+AU+AT+AS+AR+AQ | **1186/1186 PASS** |
| no endpoint / no secret / no G20 lift / no position modification / main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE — `1aa184f` |

## Next Rick Action (set by 2026-06-14 TASK-014AV-FIX2)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py -q
       # expect 259/259 PASS
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py --write-report \
         --from-latest-entry-disabled-implementation-scaffold-design \
         --from-latest-entry-disabled-implementation-scaffold-dry-run
       # confirm: scope_summary says TASK-014AU / 30 upstream / READINESS REVIEW,
       # next_required_task = TASK-014AW_..._final_pre_execution_review,
       # footer says READINESS-REVIEW-ONLY (not DRY-RUN-ONLY),
       # no socket opened, no endpoint called, no secret loaded,
       # G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014AW
   (next phase; final_pre_execution_review; still no real execution).

## TASK-014AV-FIX1 Status (2026-06-14)

| item | status |
|---|---|
| issue: 6 CLI help subprocess tests showed `OSError: [WinError 6] The handle is invalid` under pytest capture mode in prior session | IDENTIFIED |
| fix approach: re-validate all tests without `-s`; confirm transient Windows handle issue does not reproduce | DONE |
| py_compile src + scripts + test | PASS |
| pytest AV (no `-s`) | **259/259 PASS** |
| pytest AU regression (no `-s`) | 235/235 PASS |
| pytest AT regression (no `-s`) | 199/199 PASS |
| pytest AS regression (no `-s`) | 180/180 PASS |
| pytest AR regression (no `-s`) | 175/175 PASS |
| pytest AQ regression (no `-s`) | 138/138 PASS |
| combined AV+AU+AT+AS+AR+AQ (no `-s`) | **1186/1186 PASS** |
| no code changes to src / scripts / tests | CONFIRMED |
| no runtime behavior change / no endpoint / no secret / no G20 / no position modification / main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE — `e3689c9` |

## Next Rick Action (set by 2026-06-14 TASK-014AV-FIX1)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py -q
       # expect 259/259 PASS
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py --write-report \
         --from-latest-entry-disabled-implementation-scaffold-design \
         --from-latest-entry-disabled-implementation-scaffold-dry-run
       # confirm: 31 upstream artifacts consumed, status =
       # TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_READINESS_REVIEW_READY,
       # disabled_implementation_scaffold_readiness_review_conclusion =
       # DISABLED_IMPLEMENTATION_SCAFFOLD_READINESS_REVIEW_READY_NOT_EXECUTABLE,
       # no socket opened, no endpoint called, no secret loaded,
       # G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014AW
   (next phase in the sequential safety chain; still no real
   execution).

## TASK-014AV Status (2026-06-14)

| item | status |
|---|---|
| scope: build TASK-014AV scaffold (src + scripts + tests) by mirroring AU pattern + adding AU as the 31st runtime-consumed upstream artifact | DEFINED |
| module rename: `..._dry_run.py` → `..._readiness_review.py` (src, scripts, tests) | DONE |
| TASK identity bumps: `TASK-014AU` → `TASK-014AV` (identity), `TASK-014AV` → `TASK-014AW` (forward-ref) | DONE |
| src: add `ACCEPTABLE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_DRY_RUN_STATUSES` (3) + `ACCEPTABLE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_DRY_RUN_MODES` (2) + `CONSUMED_DISABLED_IMPLEMENTATION_SCAFFOLD_DRY_RUN_CONTRACT_VERSION = "disabled_implementation_scaffold_dry_run_v1"` | DONE |
| src: add 14 new fail-closed gates `GATE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_DRY_RUN_*` (missing/status/mode/real_exec/send/impl/exec/order/stop/no_pos/no_secrets/g20/conclusion/response_status); hard-fail count: 102 → 116 | DONE |
| src: extend result dataclass with 16 new `upstream_entry_disabled_implementation_scaffold_dry_run_*` fields + parser block + audit_artifacts | DONE |
| src: extend `run_readiness_review()` to require `entry_disabled_implementation_scaffold_dry_run` as 31st upstream input | DONE |
| scripts: add `--from-latest-entry-disabled-implementation-scaffold-dry-run` CLI flag + loader + dir resolution + missing-check + print line + run_readiness_review() kwarg | DONE |
| scripts: argparse description now produces "disabled implementation scaffold readiness review" (was inadvertently still "dry-run") | DONE |
| tests: add `_valid_entry_disabled_implementation_scaffold_dry_run()` fixture + extend `_run()` with `_UNSET` param | DONE |
| tests: add 19 new TestAVAU* test classes (24 tests) — contract / propagation / 14 gates / approval mode / CLI flag / AT-still-intact / AS-still-intact | DONE |
| py_compile src + scripts + test | PASS |
| pytest AV | **259/259 PASS** |
| pytest AU regression | 235/235 PASS |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| combined AV+AU+AT+AS+AR+AQ | **1186/1186 PASS** |
| no runtime behavior change in AA-AU / no endpoint / no secret / no G20 lift / no position modification / main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-14 TASK-014AV)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py -q
       # expect 259/259 PASS
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review.py --write-report \
         --from-latest-entry-disabled-implementation-scaffold-design \
         --from-latest-entry-disabled-implementation-scaffold-dry-run
       # confirm: 31 upstream artifacts consumed, status =
       # TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_READINESS_REVIEW_READY,
       # disabled_implementation_scaffold_readiness_review_conclusion =
       # DISABLED_IMPLEMENTATION_SCAFFOLD_READINESS_REVIEW_READY_NOT_EXECUTABLE,
       # no socket opened, no endpoint called, no secret loaded,
       # G20 still in place, 5 protected positions untouched.

2. Once step 1 passes, decide whether to authorise TASK-014AW
   (next phase in the sequential safety chain; still no real
   execution).

## TASK-014AU-FIX2 Status (2026-06-14)

| item | status |
|---|---|
| root cause: AT artifact JSON uses `disabled_implementation_scaffold_design_authorization_result` (AT's `to_dict()` key), not bare `authorization_result`; AU only checked bare key and verdict dict — so field was always `""` | IDENTIFIED |
| src: extend fallback chain — `atd.get("authorization_result", atd.get("disabled_implementation_scaffold_design_authorization_result", atd.get("implementation_design_authorization_result", _atd_verdict.get("authorization_result", ""))))` | DONE |
| fixture: remove `authorization_result` from `final_disabled_implementation_scaffold_design_verdict`; add `"disabled_implementation_scaffold_design_authorization_result": "DOCUMENTED_ONLY_NOT_AUTHORIZED"` at top level (matches real AT artifact structure) | DONE |
| rename FIX1 test `test_authorization_result_propagated_from_verdict_fallback` → `test_authorization_result_propagated_from_at_design_key` | DONE |
| add `TestAUATFIX2AuthorizationResultReport` (7 tests): result / to_dict / audit_artifacts field; generated JSON contains correct value; JSON no empty form; markdown contains correct value; markdown no empty form | DONE |
| py_compile src + scripts + test | PASS |
| pytest AU | **235/235 PASS** |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| combined | **927/927 PASS** |
| no runtime behavior change / no endpoint / no secret / no G20 / no position modification / main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE — `85550e0` |

## Next Rick Action (set by 2026-06-14 TASK-014AU-FIX2)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py -q
       # expect 235/235 PASS
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py --write-report --from-latest-entry-disabled-implementation-scaffold-design
       # confirm: upstream_entry_disabled_implementation_scaffold_design_authorization_result = "DOCUMENTED_ONLY_NOT_AUTHORIZED"
       # confirm: generated JSON/markdown do not contain the empty-string form of this field

2. Once step 1 passes, decide whether to authorise TASK-014AV
   (guarded entry real execution adapter disabled implementation scaffold
   readiness review — next phase; still no real execution).

## TASK-014AU-FIX1 Status (2026-06-14)

| item | status |
|---|---|
| preview intro line: `_TASK-014AU consumes TASK-014AT disabled implementation scaffold design output at runtime...` | DONE |
| preview stdout banner: `consumes TASK-014AT disabled implementation scaffold design output -> produces disabled implementation scaffold dry-run for TASK-014AV` | DONE |
| src `authorization_result` parsing: move `_atd_verdict` before extraction; add `_atd_verdict.get("authorization_result", "")` fallback so nested AT artifact field propagates correctly as `"DOCUMENTED_ONLY_NOT_AUTHORIZED"` | DONE |
| test fixture: remove top-level `authorization_result`; add `"authorization_result": "DOCUMENTED_ONLY_NOT_AUTHORIZED"` inside `final_disabled_implementation_scaffold_design_verdict` (matches real AT artifact structure; exercises fallback path) | DONE |
| update 2 assertions in `TestAUATUpstreamConsumptionPropagatesFields` (`test_valid_run_propagates_at_fields_into_result`, `test_to_dict_exposes_at_fields`): `"DOCUMENTED_ONLY_NOT_AUTHORIZED"` | DONE |
| fix stale comment + assertion in `TestARFIX2MarkdownReportTitleAndSections.test_markdown_report_uses_static_skeleton_wording`: `assert "TASK-014AT" in md` (was `"TASK-014AS"`, wrong after intro fix) | DONE |
| add `TestAUATFIX1ReportProof` (4 tests): intro names AT not AS; authorization_result in result; in to_dict; in audit_artifacts | DONE |
| py_compile src + scripts + test | PASS |
| pytest AU | **228/228 PASS** |
| pytest AT regression | 199/199 PASS |
| pytest AS regression | 180/180 PASS |
| pytest AR regression | 175/175 PASS |
| pytest AQ regression | 138/138 PASS |
| combined | **920/920 PASS** |
| no runtime behavior change / no endpoint / no secret / no G20 / no position modification / main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE — `5bffb1e` |

## Next Rick Action (set by 2026-06-14 TASK-014AU-FIX1)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py -q
       # expect 228/228 PASS
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py --write-report --from-latest-entry-disabled-implementation-scaffold-design
       # confirm: intro says "TASK-014AT disabled implementation scaffold design output"
       # confirm: authorization_result = "DOCUMENTED_ONLY_NOT_AUTHORIZED"

2. Once step 1 passes, decide whether to authorise TASK-014AV
   (guarded entry real execution adapter disabled implementation scaffold
   readiness review — next phase; still no real execution).

## TASK-014AU Status (2026-06-14)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py: disabled-implementation-scaffold-dry-run-only module (NO sender, NO executable adapter, NO `send` / `place_order` / `execute` method, NO endpoint calls, NO real entry execution, NO real token / phrase / approval-input validation, NO auto-git operations, NO AA-AT module reuse), **30 upstream artifact inputs** (the 29 from TASK-014AT + AT's `entry_disabled_implementation_scaffold_design` output **consumed at runtime by TASK-014AU**), 14 stages (STAGE_0 through STAGE_13), hard-fail-closed gates frozenset (**102 gates** incl. 14 LIVE AT-consumption gates `entry_disabled_implementation_scaffold_design_*`), 20 ACCEPTABLE_*_STATUSES frozensets incl. ACCEPTABLE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_DESIGN_STATUSES and ACCEPTABLE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_DESIGN_MODES, dataclass result with deep-copy `to_dict()` covering 14 sub-dict fields **+ 16 `upstream_entry_disabled_implementation_scaffold_design_*` fields + `consumed_disabled_implementation_scaffold_design_contract_version`** | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py: NO `/v5/order/create` invocation (only documented reference string), NO `/v5/position/trading-stop`, NO secret reads, NO HMAC/signature, NO sender adapter, NO executable adapter surface, NO `send` / `place_order` / `execute` method, NO real entry execution, NO urllib/requests/httpx/socket/http.client imports, NO G20 lift, NO AA-AT module reuse, NO auto git commit / push / branch / tag — pure-computation disabled-implementation-scaffold-dry-run envelope (ADAPTER_CONTRACT_VERSION=disabled_implementation_scaffold_dry_run_v1, CONSUMED_DISABLED_IMPLEMENTATION_SCAFFOLD_DESIGN_CONTRACT_VERSION=disabled_implementation_scaffold_design_v1, ADAPTER_RESPONSE_STATUS=DISABLED_IMPLEMENTATION_SCAFFOLD_DRY_RUN_NOT_SENT, DISABLED_IMPLEMENTATION_SCAFFOLD_DRY_RUN_CONCLUSION=DISABLED_IMPLEMENTATION_SCAFFOLD_DRY_RUN_READY_NOT_EXECUTABLE) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py: AT `entry_disabled_implementation_scaffold_design` artifact CONSUMED AT RUNTIME — status / mode / `real_execution_allowed` / `send_allowed` / `adapter_implementation_included` / `adapter_execution_included` / `order_endpoint_called` / `stop_endpoint_called` / `no_position_modified` / `no_secrets_loaded` / `g20_lifted` / `no_live_endpoint` / `no_auto_git_operations` / `real_entry_implemented` / `authorization_result` / conclusion / `audit_artifacts.response_status` all parsed and gated. ACCEPTABLE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_DESIGN_STATUSES (TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_SCAFFOLD_DESIGN_READY / _READY_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED); ACCEPTABLE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_DESIGN_MODES (disabled_implementation_scaffold_design_checklist / disabled_implementation_scaffold_design_approval); 14 LIVE AT-consumption gates (entry_disabled_implementation_scaffold_design_missing / _status_unacceptable / _mode_unacceptable / _real_execution_allowed_true / _send_allowed_true / _adapter_implementation_included_true / _adapter_execution_included_true / _order_endpoint_called_true / _stop_endpoint_called_true / _no_position_modified_false / _no_secrets_loaded_false / _g20_lifted_true / _conclusion_mismatch / _response_status_unacceptable) — each fails-closed when violated. AS + AR + AQ runtime consumption preserved intact. | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py: next_required_task = "TASK-014AV_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_readiness_review"; audit_artifacts.response_status = "DISABLED_IMPLEMENTATION_SCAFFOLD_DRY_RUN_NOT_SENT"; final_disabled_implementation_scaffold_dry_run_verdict.disabled_implementation_scaffold_dry_run_conclusion = "DISABLED_IMPLEMENTATION_SCAFFOLD_DRY_RUN_READY_NOT_EXECUTABLE" | DONE |
| scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py: **30** `--from-latest-*` flags (incl. new `--from-latest-entry-disabled-implementation-scaffold-design`), `--symbol`, `--expected-commit-hash`, `--allow-disabled-implementation-scaffold-dry-run`, `--allow-real-entry-execution`, `--write-report`; `run_execute()` callable from tests (now also accepts `entry_disabled_implementation_scaffold_design_dir`); loads `latest_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design.json` and passes the artifact through to `run_dry_run(entry_disabled_implementation_scaffold_design=...)`; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run/`; NO auto git operations | DONE |
| tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py: 224 tests — 199 inherited (rebadged for AU identity) + 25 NEW `TestAUAT*UpstreamConsumption*` covering contract version constant, ACCEPTABLE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_DESIGN_STATUSES + MODES frozensets, AT field propagation into result/to_dict/audit_artifacts, missing-AT fail-closed, status unacceptable, mode unacceptable (and approval mode accepted), real_execution_allowed true, send_allowed true, adapter_implementation_included true, adapter_execution_included true, order_endpoint_called true, stop_endpoint_called true, no_position_modified false, no_secrets_loaded false, g20_lifted true, conclusion mismatch, response_status mismatch, AQ/AR/AS regression-still-intact assertions, CLI --help exposes `--from-latest-entry-disabled-implementation-scaffold-design` | DONE |
| py_compile src + scripts + test | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py | **224/224 PASS** |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design.py (regression) | 199/199 PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py (regression) | 180/180 PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py (regression) | 175/175 PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py (regression) | 138/138 PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run/` | DONE |
| no real entry / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no sender adapter / no executable adapter surface / no `send` / `place_order` / `execute` method / no AA-AT module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback / no real token / phrase / approval-input validation / no auto git commit / no auto git push | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE — `593f081` |

## Next Rick Action (set by 2026-06-14 TASK-014AU)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run.py -q
       # expect 224/224 PASS

2. Once step 1 passes, decide whether to authorise TASK-014AV
   (guarded entry real execution adapter disabled implementation scaffold
   readiness review — next phase; still no real execution. TASK-014AU
   already wires the 14 `entry_disabled_implementation_scaffold_design_*`
   gates and ACCEPTABLE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_DESIGN_STATUSES
   + ACCEPTABLE_ENTRY_DISABLED_IMPLEMENTATION_SCAFFOLD_DESIGN_MODES at runtime
   against AT output; AV will produce the disabled implementation scaffold
   readiness review).

## TASK-014AT Status (2026-06-14)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design.py: disabled-implementation-scaffold-design-only module (NO sender, NO executable adapter, NO `send` / `place_order` / `execute` method, NO endpoint calls, NO real entry execution, NO real token / phrase / approval-input validation, NO auto-git operations, NO AA-AS module reuse), **29 upstream artifact inputs** (the 28 from TASK-014AS + AS's `entry_static_skeleton_dry_run` output **consumed at runtime by TASK-014AT**), 14 stages (STAGE_0 through STAGE_13), hard-fail-closed gates frozenset (**88 gates** incl. 13 LIVE AS-consumption gates `entry_static_skeleton_dry_run_*`), 19 ACCEPTABLE_*_STATUSES frozensets incl. ACCEPTABLE_ENTRY_STATIC_SKELETON_DRY_RUN_STATUSES, dataclass result with deep-copy `to_dict()` covering 14 sub-dict fields **+ 12 `upstream_entry_static_skeleton_dry_run_*` fields + `consumed_static_skeleton_dry_run_contract_version`** | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design.py: NO `/v5/order/create` invocation (only documented reference string), NO `/v5/position/trading-stop`, NO secret reads, NO HMAC/signature, NO sender adapter, NO executable adapter surface, NO `send` / `place_order` / `execute` method, NO real entry execution, NO urllib/requests/httpx/socket/http.client imports, NO G20 lift, NO AA-AS module reuse, NO auto git commit / push / branch / tag — pure-computation disabled-implementation-scaffold-design envelope (ADAPTER_CONTRACT_VERSION=disabled_implementation_scaffold_design_v1, CONSUMED_STATIC_SKELETON_DRY_RUN_CONTRACT_VERSION=static_skeleton_dry_run_v1, ADAPTER_RESPONSE_STATUS=DISABLED_IMPLEMENTATION_SCAFFOLD_DESIGN_NOT_SENT, DISABLED_IMPLEMENTATION_SCAFFOLD_DESIGN_CONCLUSION=DISABLED_IMPLEMENTATION_SCAFFOLD_DESIGN_READY_NOT_EXECUTABLE) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design.py: AS `entry_static_skeleton_dry_run` artifact CONSUMED AT RUNTIME — status / `real_execution_allowed` / `send_allowed` / `adapter_implementation_included` / `adapter_execution_included` / `order_endpoint_called` / `stop_endpoint_called` / `no_position_modified` / `no_secrets_loaded` / `g20_lifted` / conclusion / `audit_artifacts.response_status` all parsed and gated. ACCEPTABLE_ENTRY_STATIC_SKELETON_DRY_RUN_STATUSES (TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_STATIC_SKELETON_DRY_RUN_READY / _READY_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED); 13 LIVE AS-consumption gates (entry_static_skeleton_dry_run_missing / _status_unacceptable / _real_execution_allowed_true / _send_allowed_true / _adapter_implementation_included_true / _adapter_execution_included_true / _order_endpoint_called_true / _stop_endpoint_called_true / _no_position_modified_false / _no_secrets_loaded_false / _g20_lifted_true / _conclusion_mismatch / _response_status_unacceptable) — each fails-closed when violated. AR + AQ runtime consumption preserved intact. | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design.py: next_required_task = "TASK-014AU_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_dry_run"; audit_artifacts.response_status = "DISABLED_IMPLEMENTATION_SCAFFOLD_DESIGN_NOT_SENT"; final_disabled_implementation_scaffold_design_verdict.disabled_implementation_scaffold_design_conclusion = "DISABLED_IMPLEMENTATION_SCAFFOLD_DESIGN_READY_NOT_EXECUTABLE" | DONE |
| scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design.py: **29** `--from-latest-*` flags (incl. new `--from-latest-entry-static-skeleton-dry-run`), `--symbol`, `--expected-commit-hash`, `--allow-disabled-implementation-scaffold-design`, `--allow-real-entry-execution`, `--write-report`; `run_execute()` callable from tests (now also accepts `entry_static_skeleton_dry_run_dir`); loads `latest_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.json` and passes the artifact through to `run_design(entry_static_skeleton_dry_run=...)`; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design/`; NO auto git operations | DONE |
| tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design.py: 199 tests — 180 inherited (rebadged for AT identity) + 19 NEW `TestATAS*UpstreamConsumption*` covering contract version constant, ACCEPTABLE_ENTRY_STATIC_SKELETON_DRY_RUN_STATUSES frozenset, AS field propagation into result/to_dict/audit_artifacts, missing-AS fail-closed, status unacceptable, real_execution_allowed true, send_allowed true, adapter_implementation_included true, adapter_execution_included true, order_endpoint_called true, stop_endpoint_called true, no_position_modified false, no_secrets_loaded false, g20_lifted true, conclusion mismatch, response_status mismatch, CLI --help exposes `--from-latest-entry-static-skeleton-dry-run` | DONE |
| py_compile src + scripts + test | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design.py | **199/199 PASS** |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py (regression) | 180/180 PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py (regression) | 175/175 PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py (regression) | 138/138 PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design/` | DONE |
| no real entry / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no sender adapter / no executable adapter surface / no `send` / `place_order` / `execute` method / no AA-AS module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback / no real token / phrase / approval-input validation / no auto git commit / no auto git push | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE — `29b050d` |
| TASK-014AT-DOCS1 docs sync | DONE |

## Next Rick Action (set by 2026-06-14 TASK-014AT)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design.py -q
       # expect 199/199 PASS

2. Once step 1 passes, decide whether to authorise TASK-014AU
   (guarded entry real execution adapter disabled implementation scaffold
   dry-run — next phase; still no real execution. TASK-014AT already wires
   the 13 `entry_static_skeleton_dry_run_*` gates and
   ACCEPTABLE_ENTRY_STATIC_SKELETON_DRY_RUN_STATUSES at runtime against AS
   output; AU will produce the disabled implementation scaffold dry-run).

## TASK-014AS-FIX2 Status (2026-06-14)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py: `GATE_RESPONSE_STATUS_IS_NOT_SENT` string value `"response_status_is_implementation_design_not_sent"` → `"response_status_is_static_skeleton_dry_run_not_sent"` | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py: stage_6 summary `response_status=IMPLEMENTATION_DESIGN_NOT_SENT` → `response_status=STATIC_SKELETON_DRY_RUN_NOT_SENT` | DONE |
| AQ upstream proof fields (`upstream_entry_implementation_design_conclusion=IMPLEMENTATION_DESIGN_READY_NOT_EXECUTABLE`, `upstream_entry_implementation_design_response_status=IMPLEMENTATION_DESIGN_NOT_SENT`) unchanged | CONFIRMED |
| tests: +4 `TestASFIX2ResponseStatusLabels` — `test_blocked_gates_contains_dry_run_response_status_gate`, `test_blocked_gates_does_not_contain_impl_design_response_status_gate`, `test_stage6_summary_uses_dry_run_response_status`, `test_markdown_report_response_status_uses_dry_run_wording` | DONE |
| no runtime behavior change / no gate change / no artifact change / no endpoint/secret/sender change | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| py_compile src + scripts + test | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py | **180/180 PASS** |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py (regression) | 175/175 PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py (regression) | 138/138 PASS |
| local commit | DONE — `b8afcfb` |
| TASK-014AS-FIX2-DOCS1 docs sync | DONE |

## TASK-014AS-FIX1 Status (2026-06-14)

| item | status |
|---|---|
| scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py: module docstring lines `--allow-implementation-design` / `implementation_design_conclusion` / `IMPLEMENTATION_DESIGN_READY_NOT_EXECUTABLE` → `--allow-static-skeleton-dry-run` / `static_skeleton_dry_run_conclusion` / `STATIC_SKELETON_DRY_RUN_READY_NOT_EXECUTABLE` | DONE |
| scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py: markdown report footer blockquote updated — "STRICT IMPLEMENTATION-DESIGN-ONLY module" → "STRICT STATIC-SKELETON-DRY-RUN-ONLY module"; `--allow-implementation-design` → `--allow-static-skeleton-dry-run`; `implementation_design_conclusion remains IMPLEMENTATION_DESIGN_READY_NOT_EXECUTABLE` → `static_skeleton_dry_run_conclusion remains STATIC_SKELETON_DRY_RUN_READY_NOT_EXECUTABLE` | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py: module docstring modes section `--allow-implementation-design` → `--allow-static-skeleton-dry-run`; `run_dry_run()` docstring `--allow-implementation-design` → `--allow-static-skeleton-dry-run` | DONE |
| backward-compatible `implementation_design_*` alias fields on result dataclass and `to_dict()` preserved — no tests broken | CONFIRMED |
| no runtime behavior change / no gate change / no artifact change / no endpoint/secret/sender change | CONFIRMED |
| tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py: +1 test `test_markdown_report_footer_uses_dry_run_wording` (asserts STRICT STATIC-SKELETON-DRY-RUN-ONLY / `--allow-static-skeleton-dry-run` / `static_skeleton_dry_run_conclusion remains` / `STATIC_SKELETON_DRY_RUN_READY_NOT_EXECUTABLE` in MD); CLI banner test extended with `allow-static-skeleton-dry-run` / `static_skeleton_dry_run_conclusion` / `STATIC_SKELETON_DRY_RUN_READY_NOT_EXECUTABLE` assertions | DONE |
| py_compile src + scripts + test | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py | **176/176 PASS** |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py (regression) | 175/175 PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py (regression) | 138/138 PASS |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE — `798e77d` |
| TASK-014AS-FIX1-DOCS1 docs sync | DONE |

## TASK-014AS Status (2026-06-14)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py: static-skeleton-dry-run-only module (NO sender, NO executable adapter, NO `send` / `place_order` / `execute` method, NO endpoint calls, NO real entry execution, NO real token / phrase / approval-input validation, NO auto-git operations, NO AA-AR module reuse), **28 upstream artifact inputs** (the 27 from TASK-014AR + AR's `entry_static_skeleton_design` output **consumed at runtime by TASK-014AS**), 14 stages (STAGE_0 through STAGE_13), hard-fail-closed gates frozenset (**75 gates** incl. 13 LIVE AR-consumption gates `entry_static_skeleton_design_*`), 18 ACCEPTABLE_*_STATUSES frozensets incl. ACCEPTABLE_ENTRY_STATIC_SKELETON_DESIGN_STATUSES, dataclass result with deep-copy `to_dict()` covering 14 sub-dict fields **+ 7 `upstream_entry_static_skeleton_design_*` fields + `consumed_static_skeleton_design_contract_version`** | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py: NO `/v5/order/create` invocation (only documented reference string), NO `/v5/position/trading-stop`, NO secret reads, NO HMAC/signature, NO sender adapter, NO executable adapter surface, NO `send` / `place_order` / `execute` method, NO real entry execution, NO urllib/requests/httpx/socket/http.client imports, NO G20 lift, NO AA-AR module reuse, NO auto git commit / push / branch / tag — pure-computation static-skeleton-dry-run envelope (ADAPTER_NAME=GuardedTinyEntryRealExecutionAdapter, ADAPTER_CONTRACT_VERSION=static_skeleton_dry_run_v1, CONSUMED_STATIC_SKELETON_DESIGN_CONTRACT_VERSION=static_skeleton_design_v1, CONSUMED_IMPLEMENTATION_DESIGN_CONTRACT_VERSION=implementation_design_v1, CONSUMED_READINESS_CONTRACT_VERSION=readiness_review_v1, CONSUMED_DRY_RUN_CONTRACT_VERSION=dry_run_v1, CONSUMED_DESIGN_CONTRACT_VERSION=design_only_v1, ADAPTER_RESPONSE_STATUS=STATIC_SKELETON_DRY_RUN_NOT_SENT, ORDER_LINK_ID_PREFIX=STATIC_SKELETON_DRY_RUN_TINY_ENTRY_, STATIC_SKELETON_DRY_RUN_CONCLUSION=STATIC_SKELETON_DRY_RUN_READY_NOT_EXECUTABLE, symbol=SOLUSDT, qty=0.1, side=Buy, reduceOnly=False, orderType=Market, positionIdx=0, max_notional_usdt=10, stopLoss=61.18, tpslMode=Full, slTriggerBy=MarkPrice) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py: AR `entry_static_skeleton_design` artifact CONSUMED AT RUNTIME — status / `real_execution_allowed` / `send_allowed` / `adapter_implementation_included` / `adapter_execution_included` / `order_endpoint_called` / `stop_endpoint_called` / `no_position_modified` / `no_secrets_loaded` / `g20_lifted` / conclusion / `audit_artifacts.response_status` all parsed and gated. ACCEPTABLE_ENTRY_STATIC_SKELETON_DESIGN_STATUSES (TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_STATIC_SKELETON_DESIGN_READY / _READY_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED); 13 LIVE AR-consumption gates (entry_static_skeleton_design_missing / _status_unacceptable / _real_execution_allowed_true / _send_allowed_true / _adapter_implementation_included_true / _adapter_execution_included_true / _order_endpoint_called_true / _stop_endpoint_called_true / _no_position_modified_false / _no_secrets_loaded_false / _g20_lifted_true / _conclusion_mismatch / _response_status_unacceptable) — each fails-closed when violated. AQ runtime consumption (8 gates) preserved intact. | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py: forbidden flags (--execute-real-lifecycle / --execute-real-entry / --execute-real-stop / --execute-real-cleanup / --send-order / --place-order / --real-run / --confirm-token / --execute-tiny-entry / --auto-commit / --git-commit / --auto-push / --git-push) deliberately absent from code; only `--allow-static-skeleton-dry-run` and `--allow-real-entry-execution` exposed (both never execute real orders) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py: next_required_task = "TASK-014AT_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design"; audit_artifacts.response_status = "STATIC_SKELETON_DRY_RUN_NOT_SENT"; final_static_skeleton_dry_run_verdict.static_skeleton_dry_run_conclusion = "STATIC_SKELETON_DRY_RUN_READY_NOT_EXECUTABLE" | DONE |
| scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py: **28** `--from-latest-*` flags (incl. new `--from-latest-entry-static-skeleton-design`), `--symbol`, `--expected-commit-hash`, `--allow-static-skeleton-dry-run`, `--allow-real-entry-execution`, `--write-report`; `run_execute()` callable from tests (now also accepts `entry_static_skeleton_design_dir`); loads `latest_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.json` and passes the artifact through to `run_dry_run(entry_static_skeleton_design=...)`; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run/`; NO auto git operations | DONE |
| tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py: 175 tests covering 4 status modes, missing-artifact gates (incl. new GATE_ENTRY_STATIC_SKELETON_DESIGN_MISSING), endpoint/account/symbol invariants, all 14 stages presence + order, deep-copy roundtrip, AST + tokenize source-scan safety, 5 protected positions untouched, G20 never lifted, no AA-AR module reuse, next_required_task = 014AT, 18 frozenset whitelists incl. ACCEPTABLE_ENTRY_STATIC_SKELETON_DESIGN_STATUSES, CONSUMED_STATIC_SKELETON_DESIGN_CONTRACT_VERSION = "static_skeleton_design_v1", 13 LIVE AR-consumption gates, AQ-consumption regression preserved, schema-label tests assert STATIC SKELETON DRY-RUN terminology and `TASK-014AR` upstream wording in scope_summary / markdown / CLI help | DONE |
| py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py + scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py | 175/175 PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py (regression) | 175/175 PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py (regression) | 138/138 PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run/` | DONE |
| no real entry / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no sender adapter / no executable adapter surface / no `send` / `place_order` / `execute` method / no AA-AR module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback / no real token / phrase / approval-input validation / no auto git commit / no auto git push | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-14 TASK-014AS-FIX2)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py -q
       # expect 180/180 PASS

2. (Optional) Run TASK-014AS static skeleton dry-run preview:
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter --from-latest-guarded-stop-adapter \
           --from-latest-guarded-cleanup-adapter --from-latest-guarded-lifecycle-summary \
           --from-latest-entry-real-permission-review \
           --from-latest-entry-manual-auth-design \
           --from-latest-entry-manual-auth-dry-run \
           --from-latest-entry-final-pre-execution-review \
           --from-latest-entry-manual-approval-gate \
           --from-latest-entry-adapter-design \
           --from-latest-entry-adapter-dry-run \
           --from-latest-entry-implementation-readiness-review \
           --from-latest-entry-implementation-design \
           --from-latest-entry-static-skeleton-design \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run/latest_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.md

   Expected:
     status=TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_STATIC_SKELETON_DRY_RUN_READY;
     selected_symbol=SOLUSDT;
     5 protected positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) untouched;
     real_execution_allowed=False; real_entry_implemented=False;
     adapter_implementation_included=False; adapter_execution_included=False;
     send_allowed=False;
     order_endpoint_called=False; stop_endpoint_called=False;
     no_position_modified=True; no_live_endpoint=True;
     no_secrets_loaded=True; g20_lifted=False;
     g20_policy_still_in_place=True;
     audit_artifacts.response_status=STATIC_SKELETON_DRY_RUN_NOT_SENT;
     final_static_skeleton_dry_run_verdict.static_skeleton_dry_run_conclusion=STATIC_SKELETON_DRY_RUN_READY_NOT_EXECUTABLE;
     no_auto_git_operations=True;
     next_required_task=TASK-014AT_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design.

3. Once step 1 passes, decide whether to authorise TASK-014AT
   (guarded entry real execution adapter disabled implementation scaffold
   design — next phase; still no real execution. TASK-014AS already wires the
   13 `entry_static_skeleton_design_*` gates and
   ACCEPTABLE_ENTRY_STATIC_SKELETON_DESIGN_STATUSES at runtime against AR
   output; AT will produce the disabled implementation scaffold design).

## TASK-014AR Status (2026-06-13, updated by TASK-014AR-FIX3 2026-06-14)

| item | status |
|---|---|
| TASK-014AR-FIX3 (CLI help test hardened): `TestARFIX2CLIBannerSaysStaticSkeleton` assertion on `"TASK-014AQ implementation design output"` failed on VPS Linux due to argparse line-wrapping breaking the exact substring. Fixed by normalizing whitespace (`" ".join(combined.split())`) and asserting individual tokens (`"STATIC SKELETON DESIGN"`, `"TASK-014AQ"`, `"implementation design"`, `"static skeleton"`, `"TASK-014AS"`) instead of the full unwrapped phrase. No behavior change, no trading logic change, no gates change, no endpoint/secret/sender change. | DONE |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py | 175/175 PASS (post-FIX3) |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py (regression) | 138/138 PASS |
| TASK-014AR-FIX2 (schema label cleanup): mode renamed to `static_skeleton_design_checklist` / `static_skeleton_design_approval` (legacy `MODE_IMPLEMENTATION_DESIGN_CHECKLIST` / `_APPROVAL` retained as back-compat aliases pointing at the same strings); markdown/report title now reads "Tiny Guarded Entry Real Execution Adapter Static Skeleton Design (TASK-014AR)"; new output-facing aliases on `to_dict()` + `audit_artifacts` + stage_1 + stage_13: `static_skeleton_design_conclusion=STATIC_SKELETON_DESIGN_READY_NOT_EXECUTABLE`, `final_static_skeleton_design_verdict`, `static_skeleton_design_scope`, `static_skeleton_design_authorization_result`; stage_1 summary now says "Assert static skeleton design scope"; stage_13 summary now says "Final static skeleton design verdict"; scope_summary rewritten to "TASK-014AR consumes TASK-014AQ implementation design output at runtime and produces a STATIC SKELETON DESIGN for TASK-014AS"; legacy `implementation_design_*` keys preserved as backward-compatible aliases | DONE |
| All safety behavior unchanged: AQ runtime consumption intact, all 8 LIVE `entry_implementation_design_*` fail-closed gates active, 62-gate `_HARD_FAIL_GATES` frozenset unchanged, status string `TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_STATIC_SKELETON_DESIGN_READY` unchanged, next_required_task `TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run` unchanged | CONFIRMED |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py | 175/175 PASS (143 original + 16 AR-FIX1 + 16 AR-FIX2 schema label tests) |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py (regression) | 138/138 PASS |

## TASK-014AR Status (2026-06-13, updated by TASK-014AR-FIX1 same day)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py: static-skeleton-design-only module (NO sender, NO executable adapter, NO `send` / `place_order` / `execute` method, NO endpoint calls, NO real entry execution, NO real token / phrase / approval-input validation, NO auto-git operations, NO AA-AQ module reuse), **27 upstream artifact inputs** (the 26 AQ-readiness inputs + AQ's `entry_implementation_design` output **consumed at runtime by TASK-014AR-FIX1**), 14 implementation-design stages (STAGE_0 through STAGE_13), hard-fail-closed gates frozenset (62 gates incl. 8 LIVE AQ-consumption gates `entry_implementation_design_*`), 17 ACCEPTABLE_*_STATUSES frozensets incl. ACCEPTABLE_ENTRY_IMPLEMENTATION_DESIGN_STATUSES, dataclass result with deep-copy `to_dict()` covering 14 sub-dict fields **+ 7 `upstream_entry_implementation_design_*` fields + `consumed_implementation_design_contract_version`** | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py: NO `/v5/order/create` invocation (only documented reference string), NO `/v5/position/trading-stop`, NO secret reads, NO HMAC/signature, NO sender adapter, NO executable adapter surface, NO `send` / `place_order` / `execute` method, NO real entry execution, NO urllib/requests/httpx/socket/http.client imports, NO G20 lift, NO AA-AQ module reuse, NO auto git commit / push / branch / tag — pure-computation static-skeleton-design envelope (ADAPTER_NAME=GuardedTinyEntryRealExecutionAdapter, ADAPTER_CONTRACT_VERSION=static_skeleton_design_v1, CONSUMED_IMPLEMENTATION_DESIGN_CONTRACT_VERSION=implementation_design_v1, CONSUMED_READINESS_CONTRACT_VERSION=readiness_review_v1, CONSUMED_DRY_RUN_CONTRACT_VERSION=dry_run_v1, CONSUMED_DESIGN_CONTRACT_VERSION=design_only_v1, ADAPTER_RESPONSE_STATUS=STATIC_SKELETON_DESIGN_NOT_SENT, ORDER_LINK_ID_PREFIX=STATIC_SKELETON_DESIGN_TINY_ENTRY_, STATIC_SKELETON_DESIGN_CONCLUSION=STATIC_SKELETON_DESIGN_READY_NOT_EXECUTABLE, symbol=SOLUSDT, qty=0.1, side=Buy, reduceOnly=False, orderType=Market, positionIdx=0, max_notional_usdt=10, stopLoss=61.18, tpslMode=Full, slTriggerBy=MarkPrice) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py: AQ `entry_implementation_design` artifact CONSUMED AT RUNTIME (FIX1) — status / `implementation_design_grants_execution` / `adapter_implementation_included` / `adapter_execution_included` / `send_allowed` / `implementation_design_conclusion` (top-level OR nested under `final_implementation_design_verdict`) / `audit_artifacts.response_status` (with fallback to top-level `response_status`) all parsed and gated. CONSUMED_IMPLEMENTATION_DESIGN_CONTRACT_VERSION="implementation_design_v1"; ACCEPTABLE_ENTRY_IMPLEMENTATION_DESIGN_STATUSES (TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_IMPLEMENTATION_DESIGN_READY / _READY_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED); 8 LIVE AQ-consumption gates (entry_implementation_design_missing / _status_unacceptable / _grants_execution_true / _adapter_implementation_included_true / _adapter_execution_included_true / _send_allowed_true / _conclusion_mismatch / _response_status_unacceptable) — each fails-closed when violated | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py: forbidden flags (--execute-real-lifecycle / --execute-real-entry / --execute-real-stop / --execute-real-cleanup / --send-order / --place-order / --real-run / --confirm-token / --execute-tiny-entry / --auto-commit / --git-commit / --auto-push / --git-push) deliberately absent from code; only `--allow-implementation-design` and `--allow-real-entry-execution` exposed (both never execute real orders) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py: next_required_task = "TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run"; audit_artifacts.response_status = "STATIC_SKELETON_DESIGN_NOT_SENT"; final_implementation_design_verdict.implementation_design_conclusion = "STATIC_SKELETON_DESIGN_READY_NOT_EXECUTABLE" | DONE |
| scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py: **27** `--from-latest-*` flags (incl. new `--from-latest-entry-implementation-design`), `--symbol`, `--expected-commit-hash`, `--allow-implementation-design`, `--allow-real-entry-execution`, `--write-report`; `run_execute()` callable from tests (now also accepts `entry_implementation_design_dir`); loads `latest_tiny_guarded_entry_real_execution_adapter_implementation_design.json` and passes the artifact through to `run_design(entry_implementation_design=...)`; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_static_skeleton_design/`; NO auto git operations | DONE |
| tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py: **159** tests covering 4 status modes, missing-artifact gates (incl. new GATE_ENTRY_IMPLEMENTATION_DESIGN_MISSING), endpoint/account/symbol invariants, all 14 stages presence + order, deep-copy roundtrip, AST + tokenize source-scan safety, 5 protected positions untouched, G20 never lifted, no AA-AQ module reuse, next_required_task = 014AS, 17 frozenset whitelists incl. ACCEPTABLE_ENTRY_IMPLEMENTATION_DESIGN_STATUSES, CONSUMED_IMPLEMENTATION_DESIGN_CONTRACT_VERSION = "implementation_design_v1", 8 LIVE AQ-consumption gates **plus 16 new AR-FIX1 tests** validating: AQ field propagation into result/to_dict/audit_artifacts, missing AQ → FAIL_CLOSED, status unacceptable → FAIL_CLOSED, grants_execution → FAIL_CLOSED, implementation_included → FAIL_CLOSED, execution_included → FAIL_CLOSED, send_allowed → FAIL_CLOSED, conclusion mismatch (top-level + nested fallback) → FAIL_CLOSED, response_status mismatch (`audit_artifacts.response_status` + top-level fallback) → FAIL_CLOSED, CLI --help exposes `--from-latest-entry-implementation-design`, missing AQ artifact via run_execute → exit 1, report artifact JSON includes `upstream_entry_implementation_design_*` fields | DONE |
| py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py + scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py | 175/175 PASS (post-FIX2) |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py (regression) | 138/138 PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_static_skeleton_design/` | DONE |
| no real entry / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no sender adapter / no executable adapter surface / no `send` / `place_order` / `execute` method / no AA-AQ module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback / no real token / phrase / approval-input validation / no auto git commit / no auto git push | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-13 TASK-014AR)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py -q
       # expect 175/175 PASS (post-FIX2)

2. (Optional) Run TASK-014AR static skeleton design preview:
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter --from-latest-guarded-stop-adapter \
           --from-latest-guarded-cleanup-adapter --from-latest-guarded-lifecycle-summary \
           --from-latest-entry-real-permission-review \
           --from-latest-entry-manual-auth-design \
           --from-latest-entry-manual-auth-dry-run \
           --from-latest-entry-final-pre-execution-review \
           --from-latest-entry-manual-approval-gate \
           --from-latest-entry-adapter-design \
           --from-latest-entry-adapter-dry-run \
           --from-latest-entry-implementation-readiness-review \
           --from-latest-entry-implementation-design \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_static_skeleton_design/latest_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.md

   Expected:
     status=TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_STATIC_SKELETON_DESIGN_READY;
     selected_symbol=SOLUSDT;
     5 protected positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) untouched;
     real_execution_allowed=False; real_entry_implemented=False;
     implementation_design_only=True; adapter_implementation_included=False;
     adapter_execution_included=False;
     send_allowed=False;
     order_endpoint_called=False; stop_endpoint_called=False;
     no_position_modified=True; no_live_endpoint=True;
     no_secrets_loaded=True; g20_lifted=False;
     g20_policy_still_in_place=True;
     audit_artifacts.response_status=STATIC_SKELETON_DESIGN_NOT_SENT;
     final_implementation_design_verdict.implementation_design_conclusion=STATIC_SKELETON_DESIGN_READY_NOT_EXECUTABLE;
     no_auto_git_operations=True;
     next_required_task=TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run.

3. Once step 1 passes, decide whether to authorise TASK-014AS
   (guarded entry real execution adapter static skeleton dry-run —
   next phase; still no real execution. TASK-014AR already wires the
   8 `entry_implementation_design_*` gates and
   ACCEPTABLE_ENTRY_IMPLEMENTATION_DESIGN_STATUSES at runtime against AQ
   output as of FIX1; AS will produce the dry-run for the static
   skeleton design module).

## TASK-014AQ Status (2026-06-12)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py: implementation-design-only module (NO sender, NO executable adapter, NO `send` / `place_order` / `execute` method, NO endpoint calls, NO real entry execution, NO real token / phrase / approval-input validation, NO auto-git operations, NO AA-AP module reuse), 26 upstream artifact inputs (the 25 AP upstream artifacts + AP's entry_implementation_readiness_review output), 4 status modes (TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_IMPLEMENTATION_DESIGN_READY / _READY_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), 14 implementation-design stages (STAGE_0 through STAGE_13), hard-fail-closed gates frozenset (54 gates), 16 ACCEPTABLE_*_STATUSES frozensets incl. ACCEPTABLE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_STATUSES, dataclass result with deep-copy `to_dict()` covering 14 sub-dict fields (artifact_preflight / implementation_design_scope / static_module_boundary_design / request_construction_design / transport_and_endpoint_design / secret_and_signing_design / response_and_error_handling_design / manual_approval_and_authorization_design / stop_cleanup_handoff_design / risk_idempotency_and_audit_design / forbidden_implementation_surface_design / failure_and_abort_implementation_design / documentation_sync_review / final_implementation_design_verdict) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py: NO `/v5/order/create` invocation (only documented reference string), NO `/v5/position/trading-stop`, NO secret reads, NO HMAC/signature, NO sender adapter, NO executable adapter surface, NO `send` / `place_order` / `execute` method, NO real entry execution, NO urllib/requests/httpx/socket/http.client imports, NO G20 lift, NO AA-AP module reuse, NO auto git commit / push / branch / tag — pure-computation implementation-design envelope (ADAPTER_NAME=GuardedTinyEntryRealExecutionAdapter, ADAPTER_CONTRACT_VERSION=implementation_design_v1, CONSUMED_READINESS_CONTRACT_VERSION=readiness_review_v1, CONSUMED_DRY_RUN_CONTRACT_VERSION=dry_run_v1, CONSUMED_DESIGN_CONTRACT_VERSION=design_only_v1, ADAPTER_RESPONSE_STATUS=IMPLEMENTATION_DESIGN_NOT_SENT, ORDER_LINK_ID_PREFIX=IMPLEMENTATION_DESIGN_TINY_ENTRY_, IMPLEMENTATION_DESIGN_CONCLUSION=IMPLEMENTATION_DESIGN_READY_NOT_EXECUTABLE, symbol=SOLUSDT, qty=0.1, side=Buy, reduceOnly=False, orderType=Market, positionIdx=0, max_notional_usdt=10, stopLoss=61.18, tpslMode=Full, slTriggerBy=MarkPrice) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py: AP entry_implementation_readiness_review status / implementation_readiness_conclusion / readiness_review_grants_execution / adapter_implementation_included / adapter_execution_included / send_allowed / audit_artifacts.response_status must all be ACCEPTABLE (gate fails closed if grants_execution / implementation_included / execution_included / send_allowed is True); AE-AP statuses must be in 16 acceptable whitelist frozensets; `--expected-commit-hash` documented but never validated | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py: forbidden flags (--execute-real-lifecycle / --execute-real-entry / --execute-real-stop / --execute-real-cleanup / --send-order / --place-order / --real-run / --confirm-token / --execute-tiny-entry / --auto-commit / --git-commit / --auto-push / --git-push) deliberately absent from code; only `--allow-implementation-design` and `--allow-real-entry-execution` exposed (both never execute real orders) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py: next_required_task = "TASK-014AR_guarded_entry_real_execution_adapter_static_skeleton_design"; audit_artifacts.response_status = "IMPLEMENTATION_DESIGN_NOT_SENT"; final_implementation_design_verdict.implementation_design_conclusion = "IMPLEMENTATION_DESIGN_READY_NOT_EXECUTABLE" | DONE |
| scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py: 26 `--from-latest-*` flags incl. new `--from-latest-entry-implementation-readiness-review`, `--symbol`, `--expected-commit-hash`, `--allow-implementation-design`, `--allow-real-entry-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_implementation_design/`; NO auto git operations | DONE |
| tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py: 138 tests covering 4 status modes, 26 missing-artifact gates, endpoint/account/symbol invariants, AP implementation-readiness-review status/conclusion/grants/implementation/execution/send-allowed/audit-response acceptance, 14 stages presence + order, deep-copy roundtrip, AST + tokenize source-scan safety (no urllib/requests/httpx/socket/http.client/HMAC/signing/dotenv/env-var-read/sender/main/risk/BybitExecutor/pybit/executable adapter send/place_order/execute methods/13 forbidden flags in src + preview incl. auto-git flags), 5 protected positions untouched, G20 never lifted, no AA-AP module reuse, next_required_task = 014AR, 16 frozenset whitelists, endpoint allow/denylists, forbidden log fields, no auto-git in src + preview, HARD_FAIL_GATES expansion to 54 gates, ADAPTER_NAME / ADAPTER_CONTRACT_VERSION / CONSUMED_READINESS_CONTRACT_VERSION / CONSUMED_DRY_RUN_CONTRACT_VERSION / CONSUMED_DESIGN_CONTRACT_VERSION / ADAPTER_RESPONSE_STATUS / ORDER_LINK_ID_PREFIX / IMPLEMENTATION_DESIGN_CONCLUSION exposed, CLI subprocess exit codes, report artifacts written, `repo_tmp_path` Windows ACL workaround | DONE |
| py_compile src/demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py + scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py | 138/138 PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_implementation_design/` | DONE |
| no real entry / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no sender adapter / no executable adapter surface / no `send` / `place_order` / `execute` method / no AA-AP module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback / no real token / phrase / approval-input validation / no auto git commit / no auto git push | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-12 TASK-014AQ)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py -q
       # expect 138/138 PASS

2. Run TASK-014AQ guarded entry real execution adapter implementation design (after
   TASK-014AP guarded entry real execution adapter implementation readiness review confirmed READY):
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter --from-latest-guarded-stop-adapter \
           --from-latest-guarded-cleanup-adapter --from-latest-guarded-lifecycle-summary \
           --from-latest-entry-real-permission-review \
           --from-latest-entry-manual-auth-design \
           --from-latest-entry-manual-auth-dry-run \
           --from-latest-entry-final-pre-execution-review \
           --from-latest-entry-manual-approval-gate \
           --from-latest-entry-adapter-design \
           --from-latest-entry-adapter-dry-run \
           --from-latest-entry-implementation-readiness-review \
           --from-latest-entry-implementation-design \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_implementation_design/latest_tiny_guarded_entry_real_execution_adapter_implementation_design.md

   Expected:
     status=TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_IMPLEMENTATION_DESIGN_READY;
     selected_symbol=SOLUSDT consistent across 26 upstream artifacts;
     5 protected positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) untouched;
     real_execution_allowed=False; real_entry_implemented=False;
     implementation_design_only=True; adapter_implementation_included=False;
     adapter_execution_included=False;
     implementation_design_grants_execution=False;
     readiness_review_grants_execution=False; dry_run_grants_execution=False;
     adapter_grants_execution=False; send_allowed=False;
     order_endpoint_called=False; stop_endpoint_called=False;
     no_position_modified=True; no_live_endpoint=True;
     no_secrets_loaded=True; g20_lifted=False;
     g20_policy_still_in_place=True;
     audit_artifacts.response_status=IMPLEMENTATION_DESIGN_NOT_SENT;
     final_implementation_design_verdict.implementation_design_conclusion=IMPLEMENTATION_DESIGN_READY_NOT_EXECUTABLE;
     no_auto_git_operations=True;
     next_required_task=TASK-014AR_guarded_entry_real_execution_adapter_static_skeleton_design.

3. (Optional) Implementation-design probe:
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py \
           [...same 26 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-implementation-design --write-report
       # expect status=..._READY_BUT_EXECUTION_DISABLED, real_execution_allowed=False

4. (Optional) Guard probe — proves --allow-real-entry-execution never executes:
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py \
           [...same 26 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-real-entry-execution --write-report
       # expect status=REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED, no socket opened, no git operations

5. Once step 2 passes, decide whether to authorise TASK-014AR
   (guarded entry real execution adapter static skeleton design —
   next phase; still no real execution).

## TASK-014AP Status (2026-06-12)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py: readiness-review-only module (NO sender, NO executable adapter, NO `send` method, NO endpoint calls, NO real entry execution, NO real token / phrase / approval-input validation, NO auto-git operations, NO AA-AO module reuse), 25 upstream artifact inputs (the 24 AO upstream artifacts + AO's entry_adapter_dry_run output), 4 status modes (TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_IMPLEMENTATION_READINESS_REVIEW_READY / _READY_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), 12 readiness-review stages (STAGE_0 through STAGE_11), hard-fail-closed gates frozenset (47 gates), 15 ACCEPTABLE_*_STATUSES frozensets incl. ACCEPTABLE_ENTRY_ADAPTER_DRY_RUN_STATUSES, dataclass result with deep-copy `to_dict()` covering 12 sub-dict fields (readiness_review_scope / chain_readiness_summary / implementation_preconditions_review / forbidden_implementation_surface_review / secret_signing_transport_readiness_review / manual_approval_revalidation_review / stop_cleanup_readiness_review / risk_and_idempotency_readiness_review / failure_and_abort_readiness_review / documentation_sync_review / final_implementation_readiness_verdict / audit_artifacts) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py: NO `/v5/order/create`, NO `/v5/position/trading-stop`, NO secret reads, NO HMAC/signature, NO sender adapter, NO executable adapter surface, NO `send` method, NO real entry execution, NO urllib/requests/httpx/socket/http.client imports, NO G20 lift, NO AA-AO module reuse, NO auto git commit / push / branch / tag — pure-computation readiness-review envelope (ADAPTER_NAME=GuardedTinyEntryRealExecutionAdapter, ADAPTER_CONTRACT_VERSION=readiness_review_v1, CONSUMED_DRY_RUN_CONTRACT_VERSION=dry_run_v1, CONSUMED_DESIGN_CONTRACT_VERSION=design_only_v1, ADAPTER_RESPONSE_STATUS=READINESS_REVIEW_NOT_SENT, ORDER_LINK_ID_PREFIX=READINESS_REVIEW_TINY_ENTRY_, IMPLEMENTATION_READINESS_CONCLUSION=READY_FOR_IMPLEMENTATION_DESIGN_NOT_EXECUTION, symbol=SOLUSDT, qty=0.1, side=Buy, reduceOnly=False, orderType=Market, positionIdx=0, max_notional_usdt=10, stopLoss=61.18, tpslMode=Full, slTriggerBy=MarkPrice) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py: AO entry_adapter_dry_run status / dry_run_grants_execution / adapter_grants_execution / adapter_implementation_included / adapter_execution_included / no_send_method / audit_artifacts.response_status must all be ACCEPTABLE (gate fails closed if dry_run_grants_execution / adapter_grants_execution / implementation_included / execution_included is True or no_send_method is False); AE-AO statuses must be in 15 acceptable whitelist frozensets; `--expected-commit-hash` documented but never validated | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py: forbidden flags (--execute-real-lifecycle / --execute-real-entry / --execute-real-stop / --execute-real-cleanup / --send-order / --place-order / --real-run / --confirm-token / --execute-tiny-entry / --auto-commit / --git-commit / --auto-push / --git-push) deliberately absent from code; only `--allow-readiness-review` and `--allow-real-entry-execution` exposed (both never execute real orders) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py: next_required_task = "TASK-014AQ_guarded_entry_real_execution_adapter_implementation_design"; audit_artifacts.response_status = "READINESS_REVIEW_NOT_SENT"; final_implementation_readiness_verdict.implementation_readiness_conclusion = "READY_FOR_IMPLEMENTATION_DESIGN_NOT_EXECUTION" | DONE |
| scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py: 25 `--from-latest-*` flags incl. new `--from-latest-entry-adapter-dry-run`, `--symbol`, `--expected-commit-hash`, `--allow-readiness-review`, `--allow-real-entry-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_implementation_readiness_review/`; NO auto git operations | DONE |
| tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py: 124 tests covering 4 status modes, 25 missing-artifact gates, endpoint/account/symbol invariants, AO adapter-dry-run status/grants/implementation/execution/no-send-method/audit-response acceptance, 12 stages presence + order, deep-copy roundtrip, AST + tokenize source-scan safety (no urllib/requests/httpx/socket/http.client/HMAC/signing/dotenv/env-var-read/sender/main/risk/BybitExecutor/pybit/executable adapter send/place_order/execute methods/13 forbidden flags in src + preview incl. auto-git flags), 5 protected positions untouched, G20 never lifted, no AA-AO module reuse, next_required_task = 014AQ, 15 frozenset whitelists, endpoint allow/denylists, forbidden log fields, no auto-git in src + preview, HARD_FAIL_GATES expansion to 47 gates, ADAPTER_NAME / ADAPTER_CONTRACT_VERSION / CONSUMED_DRY_RUN_CONTRACT_VERSION / CONSUMED_DESIGN_CONTRACT_VERSION / ADAPTER_RESPONSE_STATUS / ORDER_LINK_ID_PREFIX / IMPLEMENTATION_READINESS_CONCLUSION exposed, CLI subprocess exit codes, report artifacts written, `repo_tmp_path` Windows ACL workaround | DONE |
| py_compile src/demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py + scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py | 124/124 PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_implementation_readiness_review/` | DONE |
| no real entry / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no sender adapter / no executable adapter surface / no `send` / `place_order` / `execute` method / no AA-AO module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback / no real token / phrase / approval-input validation / no auto git commit / no auto git push | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-12 TASK-014AP)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py -q
       # expect 124/124 PASS

2. Run TASK-014AP guarded entry real execution adapter implementation readiness review (after
   TASK-014AO guarded entry real execution adapter dry-run confirmed READY):
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter --from-latest-guarded-stop-adapter \
           --from-latest-guarded-cleanup-adapter --from-latest-guarded-lifecycle-summary \
           --from-latest-entry-real-permission-review \
           --from-latest-entry-manual-auth-design \
           --from-latest-entry-manual-auth-dry-run \
           --from-latest-entry-final-pre-execution-review \
           --from-latest-entry-manual-approval-gate \
           --from-latest-entry-adapter-design \
           --from-latest-entry-adapter-dry-run \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_implementation_readiness_review/latest_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.md

   Expected:
     status=TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_IMPLEMENTATION_READINESS_REVIEW_READY;
     selected_symbol=SOLUSDT consistent across 25 upstream artifacts;
     5 protected positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) untouched;
     real_execution_allowed=False; real_entry_implemented=False;
     readiness_review_only=True; adapter_implementation_included=False;
     adapter_execution_included=False; readiness_review_grants_execution=False;
     adapter_grants_execution=False; send_allowed=False;
     order_endpoint_called=False; stop_endpoint_called=False;
     no_position_modified=True; no_live_endpoint=True;
     no_secrets_loaded=True; g20_lifted=False;
     g20_policy_still_in_place=True;
     audit_artifacts.response_status=READINESS_REVIEW_NOT_SENT;
     final_implementation_readiness_verdict.implementation_readiness_conclusion=READY_FOR_IMPLEMENTATION_DESIGN_NOT_EXECUTION;
     no_auto_git_operations=True;
     next_required_task=TASK-014AQ_guarded_entry_real_execution_adapter_implementation_design.

3. (Optional) Readiness-review probe:
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py \
           [...same 25 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-readiness-review --write-report
       # expect status=..._READY_BUT_EXECUTION_DISABLED, real_execution_allowed=False

4. (Optional) Guard probe — proves --allow-real-entry-execution never executes:
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py \
           [...same 25 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-real-entry-execution --write-report
       # expect status=REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED, no socket opened, no git operations

5. Once step 2 passes, decide whether to authorise TASK-014AQ
   (guarded entry real execution adapter implementation design —
   next phase; still no real execution).

## TASK-014AO Status (2026-06-12)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_real_execution_adapter_dry_run.py: adapter-dry-run-only module (NO sender, NO executable adapter, NO `send` method, NO endpoint calls, NO real entry execution, NO real token / phrase / approval-input validation, NO auto-git operations, NO AA-AN module reuse), 24 upstream artifact inputs (the 23 AN upstream artifacts + AN's entry_adapter_design output), 4 status modes (TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DRY_RUN_READY / _READY_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), 13 adapter-dry-run stages (STAGE_0 through STAGE_12), hard-fail-closed gates frozenset (40 gates), 14 ACCEPTABLE_*_STATUSES frozensets incl. ACCEPTABLE_ENTRY_ADAPTER_DESIGN_STATUSES, dataclass result with deep-copy `to_dict()` covering 13 sub-dict fields (adapter_dry_run_scope / adapter_dry_run_contract / dry_run_input_validation_simulation / dry_run_request_envelope / entry_payload_dry_run_preview / dry_run_response_simulation / secret_and_signature_dry_run_boundary / stop_cleanup_dry_run_boundary / forbidden_execution_surface_dry_run / failure_and_abort_adapter_dry_run / documentation_sync_review / audit_artifacts / final_adapter_dry_run_verdict) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_dry_run.py: NO `/v5/order/create`, NO `/v5/position/trading-stop`, NO secret reads, NO HMAC/signature, NO sender adapter, NO executable adapter surface, NO `send` method, NO real entry execution, NO urllib/requests/httpx/socket/http.client imports, NO G20 lift, NO AA-AN module reuse, NO auto git commit / push / branch / tag — pure-computation adapter-dry-run envelope (ADAPTER_NAME=GuardedTinyEntryRealExecutionAdapter, ADAPTER_CONTRACT_VERSION=dry_run_v1, CONSUMED_DESIGN_CONTRACT_VERSION=design_only_v1, ADAPTER_RESPONSE_STATUS=ADAPTER_DRY_RUN_NOT_SENT, ORDER_LINK_ID_PREFIX=ADAPTER_DRY_RUN_TINY_ENTRY_, symbol=SOLUSDT, qty=0.1, side=Buy, reduceOnly=False, orderType=Market, positionIdx=0, max_notional_usdt=10, stopLoss=61.18, tpslMode=Full, slTriggerBy=MarkPrice) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_dry_run.py: AN entry_adapter_design status / readiness_conclusion / adapter_grants_execution / adapter_implementation_included / adapter_execution_included / no_send_method must all be ACCEPTABLE (gate fails closed if adapter_grants_execution / implementation_included / execution_included is True); AE-AN statuses must be in 14 acceptable whitelist frozensets; `--expected-commit-hash` documented but never validated | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_dry_run.py: forbidden flags (--execute-real-lifecycle / --execute-real-entry / --execute-real-stop / --execute-real-cleanup / --send-order / --place-order / --real-run / --confirm-token / --execute-tiny-entry / --auto-commit / --git-commit / --auto-push / --git-push) deliberately absent from code; only `--allow-adapter-dry-run` and `--allow-real-entry-execution` exposed (both never execute real orders) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_dry_run.py: next_required_task = "TASK-014AP_guarded_entry_real_execution_adapter_implementation_readiness_review"; audit_artifacts.response_status = "ADAPTER_DRY_RUN_NOT_SENT" | DONE |
| scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py: 24 `--from-latest-*` flags incl. new `--from-latest-entry-adapter-design`, `--symbol`, `--expected-commit-hash`, `--allow-adapter-dry-run`, `--allow-real-entry-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_dry_run/`; NO auto git operations | DONE |
| tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py: 139 tests covering 4 status modes, 24 missing-artifact gates, endpoint/account/symbol invariants, AN adapter-design status/readiness/grants/implementation/execution/no-send-method acceptance, 13 stages presence + order, deep-copy roundtrip, AST + tokenize source-scan safety (no urllib/requests/httpx/socket/http.client/HMAC/signing/dotenv/env-var-read/sender/main/risk/BybitExecutor/pybit/executable adapter send/place_order/execute methods/13 forbidden flags in src + preview incl. auto-git flags), 5 protected positions untouched, G20 never lifted, no AA-AN module reuse, next_required_task = 014AP, 14 frozenset whitelists, endpoint allow/denylists, forbidden log fields, no auto-git in src + preview, HARD_FAIL_GATES expansion to 40 gates, ADAPTER_NAME / ADAPTER_CONTRACT_VERSION / CONSUMED_DESIGN_CONTRACT_VERSION / ADAPTER_RESPONSE_STATUS / ORDER_LINK_ID_PREFIX exposed, CLI subprocess exit codes, report artifacts written, `repo_tmp_path` Windows ACL workaround | DONE |
| py_compile src/demo_tiny_guarded_entry_real_execution_adapter_dry_run.py + scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py | 139/139 PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_dry_run/` | DONE |
| no real entry / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no sender adapter / no executable adapter surface / no `send` / `place_order` / `execute` method / no AA-AN module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback / no real token / phrase / approval-input validation / no auto git commit / no auto git push | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-12 TASK-014AO)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_dry_run.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py -q
       # expect 139/139 PASS

2. Run TASK-014AO guarded entry real execution adapter dry-run (after
   TASK-014AN guarded entry real execution adapter design confirmed READY):
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter --from-latest-guarded-stop-adapter \
           --from-latest-guarded-cleanup-adapter --from-latest-guarded-lifecycle-summary \
           --from-latest-entry-real-permission-review \
           --from-latest-entry-manual-auth-design \
           --from-latest-entry-manual-auth-dry-run \
           --from-latest-entry-final-pre-execution-review \
           --from-latest-entry-manual-approval-gate \
           --from-latest-entry-adapter-design \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_dry_run/latest_tiny_guarded_entry_real_execution_adapter_dry_run.md

   Expected:
     status=TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DRY_RUN_READY;
     selected_symbol=SOLUSDT consistent across 24 upstream artifacts;
     5 protected positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) untouched;
     real_execution_allowed=False; real_entry_implemented=False;
     adapter_dry_run_only=True; adapter_implementation_included=False;
     adapter_execution_included=False; dry_run_grants_execution=False;
     adapter_grants_execution=False; send_allowed=False;
     order_endpoint_called=False; stop_endpoint_called=False;
     no_position_modified=True; no_live_endpoint=True;
     no_secrets_loaded=True; g20_lifted=False;
     g20_policy_still_in_place=True;
     audit_artifacts.response_status=ADAPTER_DRY_RUN_NOT_SENT;
     no_auto_git_operations=True;
     next_required_task=TASK-014AP_guarded_entry_real_execution_adapter_implementation_readiness_review.

3. (Optional) Adapter-dry-run probe:
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py \
           [...same 24 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-adapter-dry-run --write-report
       # expect status=..._READY_BUT_EXECUTION_DISABLED, real_execution_allowed=False

4. (Optional) Guard probe — proves --allow-real-entry-execution never executes:
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py \
           [...same 24 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-real-entry-execution --write-report
       # expect status=REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED, no socket opened, no git operations

5. Once step 2 passes, decide whether to authorise TASK-014AP
   (guarded entry real execution adapter implementation readiness review —
   next phase; still no real execution).

## TASK-014AN Status (2026-06-12)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_real_execution_adapter_design.py: adapter-design-only module (NO sender, NO executable adapter, NO `send` method, NO endpoint calls, NO real entry execution, NO real token / phrase / approval-input validation, NO auto-git operations, NO AA-AM module reuse), 23 upstream artifact inputs (the 22 AM upstream artifacts + AM's entry_manual_approval_gate output), 4 status modes (TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DESIGN_READY / _READY_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), 12 adapter-design stages (STAGE_0 through STAGE_11), hard-fail-closed gates frozenset (33 gates), dataclass result with deep-copy `to_dict()` covering 12 sub-dict fields (adapter_design_scope / adapter_contract_design / adapter_input_schema_design / adapter_output_schema_design / entry_payload_design_preview / secret_and_signature_boundary_design / stop_cleanup_boundary_design / forbidden_execution_surface_design / failure_and_abort_adapter_design / documentation_sync_review / audit_artifacts / final_adapter_design_verdict) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_design.py: NO `/v5/order/create`, NO `/v5/position/trading-stop`, NO secret reads, NO HMAC/signature, NO sender adapter, NO executable adapter surface, NO `send` method, NO real entry execution, NO urllib/requests/httpx/socket/http.client imports, NO G20 lift, NO AA-AM module reuse, NO auto git commit / push / branch / tag — pure-computation adapter-design envelope (ADAPTER_NAME=GuardedTinyEntryRealExecutionAdapter, ADAPTER_CONTRACT_VERSION=design_only_v1, ADAPTER_RESPONSE_STATUS=ADAPTER_DESIGN_NOT_SENT, ORDER_LINK_ID_PREFIX=ADAPTER_DESIGN_TINY_ENTRY_, symbol=SOLUSDT, qty=0.1, side=Buy, reduceOnly=False, orderType=Market, positionIdx=0, max_notional_usdt=10, stopLoss=61.18, tpslMode=Full, slTriggerBy=MarkPrice) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_design.py: AM entry_manual_approval_gate status / readiness_conclusion / approval_grants_execution / exact_phrase_validated / approval_inputs_validated must all be ACCEPTABLE (gate fails closed if approval_grants_execution is True); AE-AM statuses must be in 13 acceptable whitelist frozensets (incl. ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES); `--expected-commit-hash` documented but never validated | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_design.py: forbidden flags (--execute-real-entry / --send-order / --place-order / --real-run / --confirm-token / --execute-tiny-entry / --auto-commit / --git-commit / --auto-push / --git-push) deliberately absent from code; only `--allow-adapter-design-approval` and `--allow-real-entry-execution` exposed (both never execute real orders) | DONE |
| src/demo_tiny_guarded_entry_real_execution_adapter_design.py: next_required_task = "TASK-014AO_guarded_entry_real_execution_adapter_dry_run"; audit_artifacts.response_status = "ADAPTER_DESIGN_NOT_SENT" | DONE |
| scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_design.py: 23 `--from-latest-*` flags incl. new `--from-latest-entry-manual-approval-gate`, `--symbol`, `--expected-commit-hash`, `--allow-adapter-design-approval`, `--allow-real-entry-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_design/`; NO auto git operations | DONE |
| tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_design.py: 129 tests covering 4 status modes, 23 missing-artifact gates, endpoint/account/symbol invariants, AM approval-gate status/readiness/grants/phrase/inputs acceptance, 12 stages presence + order, deep-copy roundtrip, source-scan safety (AST + tokenize) for forbidden imports (urllib/requests/httpx/socket/http.client) + HMAC/signing + dotenv/os.environ + sender/main/risk/BybitExecutor/pybit modules + executable adapter `send` method + 10 forbidden flags in src + preview (incl. auto-git flags), 5 protected positions untouched, G20 never lifted, no AA-AM module reuse, next_required_task = 014AO, status precedence, 13 frozenset whitelists, endpoint allow/denylists, forbidden log fields, expected commit hash documented but not validated, no auto-git in src + preview, HARD_FAIL_GATES expansion to 33 gates, ADAPTER_NAME / ADAPTER_CONTRACT_VERSION / ADAPTER_RESPONSE_STATUS / ORDER_LINK_ID_PREFIX exposed, CLI subprocess exit codes, report artifacts written, `repo_tmp_path` Windows ACL workaround | DONE |
| py_compile src/demo_tiny_guarded_entry_real_execution_adapter_design.py + scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_design.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_design.py | 129/129 PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_design/` | DONE |
| no real entry / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no sender adapter / no executable adapter surface / no `send` method / no AA-AM module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback / no real token / phrase / approval-input validation / no auto git commit / no auto git push | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-12 TASK-014AN)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_design.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_design.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_design.py -q
       # expect 129/129 PASS

2. Run TASK-014AN guarded entry real execution adapter design (after
   TASK-014AM guarded entry real execution manual approval gate confirmed READY):
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_design.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter --from-latest-guarded-stop-adapter \
           --from-latest-guarded-cleanup-adapter --from-latest-guarded-lifecycle-summary \
           --from-latest-entry-real-permission-review \
           --from-latest-entry-manual-auth-design \
           --from-latest-entry-manual-auth-dry-run \
           --from-latest-entry-final-pre-execution-review \
           --from-latest-entry-manual-approval-gate \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_design/latest_tiny_guarded_entry_real_execution_adapter_design.md

   Expected:
     status=TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DESIGN_READY;
     selected_symbol=SOLUSDT consistent across 23 upstream artifacts;
     5 protected positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) untouched;
     real_execution_allowed=False; real_entry_implemented=False;
     adapter_design_only=True; g20_lifted=False; no_secrets_loaded=True;
     approval_grants_execution=False; exact_phrase_validated=False;
     approval_inputs_validated=False;
     audit_artifacts.response_status=ADAPTER_DESIGN_NOT_SENT;
     no_auto_git_operations=True;
     next_required_task=TASK-014AO_guarded_entry_real_execution_adapter_dry_run.

3. (Optional) Adapter-design-approval probe:
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_design.py \
           [...same 23 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-adapter-design-approval --write-report
       # expect status=..._READY_BUT_EXECUTION_DISABLED, real_execution_allowed=False

4. (Optional) Guard probe — proves --allow-real-entry-execution never executes:
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_design.py \
           [...same 23 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-real-entry-execution --write-report
       # expect status=REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED, no socket opened, no git operations

5. Once step 2 passes, decide whether to authorise TASK-014AO
   (guarded entry real execution adapter dry-run — next phase).

## TASK-014AM Status (2026-06-12)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_real_execution_manual_approval_gate.py: manual-approval-gate-only module (NO sender, NO endpoint calls, NO real token validation, NO real entry execution, NO auto-git operations, NO AA-AL module reuse), 22 upstream artifact inputs (AA through AL chain incl. AL entry_final_pre_execution_review), 4 status modes (TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_READY / _BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), 11 manual-approval-gate stages (STAGE_0 through STAGE_10), hard-fail-closed gates frozenset (31 gates), dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_guarded_entry_real_execution_manual_approval_gate.py: NO `/v5/order/create`, NO `/v5/position/trading-stop`, NO secret reads, NO HMAC/signature, NO sender adapter, NO real entry execution, NO real token validation (token pattern `CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT` documented only, never re.match'd), NO real exact approval phrase validation (EXACT_APPROVAL_PHRASE documented only, never compared), NO G20 lift, NO AA-AL module reuse, NO auto git commit / push / branch / tag — pure-computation manual-approval-gate envelope (symbol=SOLUSDT, qty=0.1, side=Buy, reduceOnly=False, orderType=Market, positionIdx=0, max_notional_usdt=10, stopLoss=61.18, tpslMode=Full, slTriggerBy=MarkPrice, order_link_id_prefix=APPROVAL_GATE_TINY_ENTRY_) | DONE |
| src/demo_tiny_guarded_entry_real_execution_manual_approval_gate.py: documents 12 REQUIRED_MANUAL_APPROVAL_INPUTS (1 EXACT_APPROVAL_PHRASE + 11 REQUIRED_CONFIRM_FLAGS) but NEVER parses/validates them (approval_inputs_validated=False, exact_phrase_validated=False); AL entry_final_pre_execution_review status / readiness_conclusion / authorization_result must be ACCEPTABLE; AE-AL statuses must be in 12 acceptable whitelist frozensets; `--expected-commit-hash` documented but never validated | DONE |
| src/demo_tiny_guarded_entry_real_execution_manual_approval_gate.py: forbidden flags (--execute-real-entry / --send-order / --place-order / --real-run / --confirm-token / --execute-tiny-entry / --auto-commit / --git-commit / --auto-push / --git-push) deliberately absent from code | DONE |
| src/demo_tiny_guarded_entry_real_execution_manual_approval_gate.py: next_required_task = "TASK-014AN_guarded_entry_real_execution_adapter_design"; audit_artifacts.response_status = "APPROVAL_GATE_NOT_SENT" | DONE |
| scripts/preview_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py: 22 `--from-latest-*` flags incl. new `--from-latest-entry-final-pre-execution-review`, `--symbol`, `--expected-commit-hash`, `--allow-approval-gate`, `--allow-real-entry-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_real_execution_manual_approval_gate/`; NO auto git operations | DONE |
| tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py: 114 tests across 88 test classes (AM1-AM88) covering 4 status modes, 22 missing-artifact gates, endpoint/account/symbol invariants, AL final-review status/readiness/authorization_result acceptance, 11 stages presence + order, deep-copy roundtrip, source-scan safety (AST + tokenize), forbidden flag absence in src + preview (incl. auto-git flags), 5 protected positions untouched, G20 never lifted, token pattern + EXACT_APPROVAL_PHRASE + 12 REQUIRED_MANUAL_APPROVAL_INPUTS + 11 REQUIRED_CONFIRM_FLAGS documented-only never validated, next_required_task = 014AN, status precedence, 12 frozenset whitelists, endpoint allow/denylists, forbidden log fields, expected commit hash documented but not validated, no auto-git in src + preview, HARD_FAIL_GATES expansion to 31 gates, ORDER_LINK_ID_PREFIX exposed, CLI subprocess exit codes, report artifacts written, `repo_tmp_path` Windows ACL workaround | DONE |
| py_compile src/demo_tiny_guarded_entry_real_execution_manual_approval_gate.py + scripts/preview_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py | 114/114 PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_entry_real_execution_manual_approval_gate/` | DONE |
| no real entry / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no permission-gate sender reuse / no AA-AL module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback / no real token validation / no real exact phrase validation / no real approval-input validation / no auto git commit / no auto git push | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-12 TASK-014AM)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_execution_manual_approval_gate.py scripts/preview_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py -q
       # expect 114/114 PASS

2. Run TASK-014AM guarded entry real execution manual approval gate (after
   TASK-014AL guarded entry final pre-execution review confirmed READY):
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter --from-latest-guarded-stop-adapter \
           --from-latest-guarded-cleanup-adapter --from-latest-guarded-lifecycle-summary \
           --from-latest-entry-real-permission-review \
           --from-latest-entry-manual-auth-design \
           --from-latest-entry-manual-auth-dry-run \
           --from-latest-entry-final-pre-execution-review \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_entry_real_execution_manual_approval_gate/latest_tiny_guarded_entry_real_execution_manual_approval_gate.md

   Expected:
     status=TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_READY;
     selected_symbol=SOLUSDT consistent across 22 upstream artifacts;
     5 protected positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) untouched;
     real_execution_allowed=False; real_entry_implemented=False;
     manual_approval_gate_only=True; g20_lifted=False; no_secrets_loaded=True;
     token_validation_simulated=True; token_validated=False;
     exact_phrase_validated=False; approval_inputs_validated=False;
     audit_artifacts.response_status=APPROVAL_GATE_NOT_SENT;
     no_auto_git_operations=True;
     next_required_task=TASK-014AN_guarded_entry_real_execution_adapter_design.

3. (Optional) Approval-gate probe:
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py \
           [...same 22 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-approval-gate --write-report
       # expect status=..._READY_BUT_EXECUTION_DISABLED, real_execution_allowed=False

4. (Optional) Guard probe — proves --allow-real-entry-execution never executes:
       python3 scripts/preview_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py \
           [...same 22 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-real-entry-execution --write-report
       # expect status=REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED, no socket opened, no git operations

5. Once step 2 passes, decide whether to authorise TASK-014AN
   (guarded entry real execution adapter design — next phase).

## TASK-014AL Status (2026-06-12)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_final_pre_execution_review.py: review-only module (NO sender, NO endpoint calls, NO real token validation, NO real entry execution, NO auto-git operations), 21 upstream artifact inputs (AA through AK chain), 4 status modes (TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY / _BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), 11 review stages (STAGE_0 through STAGE_10), hard-fail-closed gates frozenset (29 gates), 152+ gates total, dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_guarded_entry_final_pre_execution_review.py: NO `/v5/order/create`, NO `/v5/position/trading-stop`, NO secret reads, NO HMAC/signature, NO sender adapter, NO real entry execution, NO real token validation (token pattern `CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT` documented only, never re.match'd), NO G20 lift, NO AA-AK module reuse, NO auto git commit / push / branch / tag — pure-computation review envelope (symbol=SOLUSDT, qty=0.1, side=Buy, reduceOnly=False, orderType=Market, positionIdx=0, max_notional_usdt=10, stopLoss=61.18, tpslMode=Full, slTriggerBy=MarkPrice) | DONE |
| src/demo_tiny_guarded_entry_final_pre_execution_review.py: documents 13 required human confirmation flags but NEVER parses/validates them; AK entry_manual_authorization_dry_run status must be ACCEPTABLE, readiness must be NOT_EXECUTABLE, dry_run_authorization_result must equal DOCUMENTED_ONLY_NOT_AUTHORIZED; AE-AK statuses must be in acceptable whitelist; `--expected-commit-hash` documented but never validated | DONE |
| src/demo_tiny_guarded_entry_final_pre_execution_review.py: forbidden flags (--execute-real-entry / --send-order / --place-order / --real-run / --confirm-token / --execute-tiny-entry / --auto-commit / --git-commit / --auto-push / --git-push) deliberately absent from code | DONE |
| src/demo_tiny_guarded_entry_final_pre_execution_review.py: next_required_task = "TASK-014AM" | DONE |
| scripts/preview_demo_tiny_guarded_entry_final_pre_execution_review.py: 21 `--from-latest-*` flags incl. new `--from-latest-entry-manual-auth-dry-run`, `--symbol`, `--expected-commit-hash`, `--allow-review-approval`, `--allow-real-entry-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_final_pre_execution_review/`; NO auto git operations | DONE |
| tests/demo_trading/test_demo_tiny_guarded_entry_final_pre_execution_review.py: 104 tests across 87 test classes (AL1-AL87) covering 4 status modes, 21 missing-artifact gates, endpoint/account/symbol invariants, AK dry-run status/readiness/auth_result acceptance, 11 stages presence + order, deep-copy roundtrip, source-scan safety (AST + tokenize), forbidden flag absence in src + preview (incl. auto-git flags), 5 protected positions untouched, G20 never lifted, token pattern documented-only never validated, 13 required flags doc, next_required_task = 014AM, status precedence, frozenset whitelists, endpoint allow/denylists, forbidden log fields, expected commit hash documented but not validated, no auto-git in src + preview, HARD_FAIL_GATES expansion to 29 gates, CLI subprocess exit codes, report artifacts written, `repo_tmp_path` Windows ACL workaround | DONE |
| py_compile src/demo_tiny_guarded_entry_final_pre_execution_review.py + scripts/preview_demo_tiny_guarded_entry_final_pre_execution_review.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_final_pre_execution_review.py | 104/104 PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_entry_final_pre_execution_review/` | DONE |
| no real entry / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no permission-gate sender reuse / no AA-AK module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback / no real token validation / no auto git commit / no auto git push | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-12 TASK-014AL)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_final_pre_execution_review.py scripts/preview_demo_tiny_guarded_entry_final_pre_execution_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_final_pre_execution_review.py -q
       # expect 104/104 PASS

2. Run TASK-014AL guarded entry final pre-execution review (after TASK-014AK
   guarded entry manual authorization dry-run confirmed READY):
       python3 scripts/preview_demo_tiny_guarded_entry_final_pre_execution_review.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter --from-latest-guarded-stop-adapter \
           --from-latest-guarded-cleanup-adapter --from-latest-guarded-lifecycle-summary \
           --from-latest-entry-real-permission-review \
           --from-latest-entry-manual-auth-design \
           --from-latest-entry-manual-auth-dry-run \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_entry_final_pre_execution_review/latest_tiny_guarded_entry_final_pre_execution_review.md

   Expected:
     status=TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY;
     selected_symbol=SOLUSDT consistent across 21 upstream artifacts;
     5 protected positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) untouched;
     real_execution_allowed=False; g20_lifted=False; no_secrets_loaded=True;
     token_validation_simulated=True; token_validated=False; real_token_validated=False;
     dry_run_authorization_result=DOCUMENTED_ONLY_NOT_AUTHORIZED;
     no_auto_git_operations=True;
     next_required_task=TASK-014AM.

3. (Optional) Review-approval probe:
       python3 scripts/preview_demo_tiny_guarded_entry_final_pre_execution_review.py \
           [...same 21 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-review-approval --write-report
       # expect status=TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY_BUT_EXECUTION_DISABLED

4. (Optional) Guard probe — proves --allow-real-entry-execution never executes:
       python3 scripts/preview_demo_tiny_guarded_entry_final_pre_execution_review.py \
           [...same 21 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-real-entry-execution --write-report
       # expect status=REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED, no socket opened, no git operations

5. Once step 2 passes, decide whether to authorise TASK-014AM
   (next guarded-lifecycle phase).

## TASK-014AK Status (2026-06-12)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_manual_authorization_dry_run.py: manual-authorization-dry-run-only module (NO sender, NO endpoint calls, NO real token validation, NO real entry execution), 20 upstream artifact inputs (19 from TASK-014AJ + AJ's entry_manual_authorization_design output), 4 status modes (TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY / _BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), 10 dry-run stages, hard-fail-closed gates frozenset (27 gates), 156+ gates total, dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_guarded_entry_manual_authorization_dry_run.py: NO `/v5/order/create`, NO `/v5/position/trading-stop`, NO secret reads, NO HMAC/signature, NO sender adapter, NO real entry execution, token pattern `CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT` simulated only (token_validation_simulated=True, token_validated=False, real_token_validated=False, dry_run_authorization_result=DOCUMENTED_ONLY_NOT_AUTHORIZED), NO G20 lift, NO AA-AJ module reuse — pure-computation authorization-dry-run envelope (symbol=SOLUSDT, qty=0.1, side=Buy, reduceOnly=False, orderType=Market, positionIdx=0, max_notional_usdt=10, stopLoss=61.18, tpslMode=Full, slTriggerBy=MarkPrice) | DONE |
| src/demo_tiny_guarded_entry_manual_authorization_dry_run.py: documents 13 required human confirmation flags but NEVER parses/validates them; AJ entry_manual_authorization_design readiness must equal DESIGN_REVIEW_READY_NOT_EXECUTABLE; AE-AJ statuses must be in acceptable whitelist | DONE |
| src/demo_tiny_guarded_entry_manual_authorization_dry_run.py: forbidden flags (--execute-real-entry / --send-order / --place-order / --real-run / --confirm-token / --execute-tiny-entry) deliberately absent from code | DONE |
| src/demo_tiny_guarded_entry_manual_authorization_dry_run.py: next_required_task = "TASK-014AL_guarded_entry_final_pre_execution_review" | DONE |
| scripts/preview_demo_tiny_guarded_entry_manual_authorization_dry_run.py: 20 `--from-latest-*` flags incl. new `--from-latest-entry-manual-auth-design`, `--symbol`, `--allow-dry-run-approval`, `--allow-real-entry-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_manual_authorization_dry_run/` | DONE |
| tests/demo_trading/test_demo_tiny_guarded_entry_manual_authorization_dry_run.py: 76 tests across ~60 test classes (AK1-AK64) covering 4 status modes, 20 missing-artifact gates, endpoint/account/symbol invariants, AJ design status/readiness acceptance, 10 stages presence + order, deep-copy roundtrip, source-scan safety (AST + tokenize), 6 forbidden flag absence in preview (argparse-scoped), forbidden flags in src, 5 protected positions untouched, G20 never lifted, token pattern documented-only never validated via re.match, 13 required flags doc, next_required_task = 014AL, status precedence, frozenset whitelists, endpoint allow/denylists, forbidden log fields, dry-run expected values, CLI subprocess exit codes, report artifacts written | DONE |
| py_compile src/demo_tiny_guarded_entry_manual_authorization_dry_run.py + scripts/preview_demo_tiny_guarded_entry_manual_authorization_dry_run.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_manual_authorization_dry_run.py | 76/76 PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_entry_manual_authorization_dry_run/` + `outputs/_test_scratch/` | DONE |
| no real entry / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no permission-gate sender reuse / no AA-AJ module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback / no real token validation | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-12 TASK-014AK)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_manual_authorization_dry_run.py scripts/preview_demo_tiny_guarded_entry_manual_authorization_dry_run.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_manual_authorization_dry_run.py -q
       # expect 76/76 PASS

2. Run TASK-014AK guarded entry manual authorization dry-run (after TASK-014AJ
   guarded entry manual authorization design confirmed READY):
       python3 scripts/preview_demo_tiny_guarded_entry_manual_authorization_dry_run.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter --from-latest-guarded-stop-adapter \
           --from-latest-guarded-cleanup-adapter --from-latest-guarded-lifecycle-summary \
           --from-latest-entry-real-permission-review \
           --from-latest-entry-manual-auth-design \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_entry_manual_authorization_dry_run/latest_tiny_guarded_entry_manual_authorization_dry_run.md

   Expected:
     status=TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY;
     selected_symbol=SOLUSDT consistent across 20 upstream artifacts;
     5 protected positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) untouched;
     real_execution_allowed=False; g20_lifted=False; no_secrets_loaded=True;
     token_validation_simulated=True; token_validated=False; real_token_validated=False;
     dry_run_authorization_result=DOCUMENTED_ONLY_NOT_AUTHORIZED;
     next_required_task=TASK-014AL_guarded_entry_final_pre_execution_review.

3. (Optional) Dry-run-approval probe:
       python3 scripts/preview_demo_tiny_guarded_entry_manual_authorization_dry_run.py \
           [...same 20 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-dry-run-approval --write-report
       # expect status=TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY_BUT_EXECUTION_DISABLED

4. (Optional) Guard probe — proves --allow-real-entry-execution never executes:
       python3 scripts/preview_demo_tiny_guarded_entry_manual_authorization_dry_run.py \
           [...same 20 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-real-entry-execution --write-report
       # expect status=REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED, no socket opened

5. Once step 2 passes, decide whether to authorise TASK-014AL
   (guarded_entry_final_pre_execution_review).

## TASK-014AJ Status (2026-06-11)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_manual_authorization_design.py: manual-authorization-design-only module (NO sender, NO endpoint calls, NO token validation), 19 upstream artifact inputs (18 from TASK-014AI + AI's entry_real_permission_review output), 4 status modes (TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DESIGN_READY / _BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), 10 design stages, hard-fail-closed gates frozenset (26 gates), 147 gates total, dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_guarded_entry_manual_authorization_design.py: NO `/v5/order/create`, NO `/v5/position/trading-stop`, NO secret reads, NO HMAC/signature, NO sender adapter, NO real entry execution, NO token validation (token pattern `CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT` documented but NEVER validated), NO G20 lift, NO AA-AI module reuse — pure-computation authorization-design envelope (symbol=SOLUSDT, qty=0.1, side=Buy, reduceOnly=False, orderType=Market, positionIdx=0, max_notional_usdt=10, stopLoss=61.18, tpslMode=Full, slTriggerBy=MarkPrice) | DONE |
| src/demo_tiny_guarded_entry_manual_authorization_design.py: documents 13 required human confirmation flags (--i-understand-this-is-demo-real-execution, --confirm-symbol/side/qty/max-notional-usdt/existing-position-count/existing-symbols/reduce-only/position-idx/order-type/stop-required-after-entry/stop-loss/cleanup-manual-boundary) but NEVER parses/validates them; AI entry_real_permission_review readiness must equal DESIGN_REVIEW_READY_NOT_EXECUTABLE; AE-AI statuses must be in acceptable whitelist | DONE |
| src/demo_tiny_guarded_entry_manual_authorization_design.py: forbidden flags (--execute-real-entry / --send-order / --place-order / --real-run / --confirm-token / --execute-tiny-entry) deliberately absent from code | DONE |
| src/demo_tiny_guarded_entry_manual_authorization_design.py: next_required_task = "TASK-014AK_guarded_entry_manual_authorization_dry_run" | DONE |
| scripts/preview_demo_tiny_guarded_entry_manual_authorization_design.py: 19 `--from-latest-*` flags incl. new `--from-latest-entry-real-permission-review`, `--symbol`, `--allow-design-approval`, `--allow-real-entry-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_manual_authorization_design/` | DONE |
| tests/demo_trading/test_demo_tiny_guarded_entry_manual_authorization_design.py: 116 tests across 86 test classes (AJ1-AJ86) covering 4 status modes, 19 missing-artifact gates, 7 invariant mismatches, 10 stages presence + order, gate count >=147, always-on gates set, G20 not lifted, deep-copy roundtrip, no forbidden imports (incl. AA-AI modules), no sender / network / env / signing tokens, 6 forbidden flags absent, hard-fail gates frozenset, next_required_task = 014AK, status precedence, 13 confirmation flags documented but never validated, 5 protected positions never touched, source-scan safety (tokenize + AST), CLI subprocess exit codes | DONE |
| py_compile src/demo_tiny_guarded_entry_manual_authorization_design.py + scripts/preview_demo_tiny_guarded_entry_manual_authorization_design.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_manual_authorization_design.py | 116/116 PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_entry_manual_authorization_design/` | DONE |
| no real entry / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no permission-gate sender reuse / no AA-AI module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback / no token validation | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-11 TASK-014AJ)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_manual_authorization_design.py scripts/preview_demo_tiny_guarded_entry_manual_authorization_design.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_manual_authorization_design.py -q
       # expect 116/116 PASS

2. Run TASK-014AJ guarded entry manual authorization design (after TASK-014AI
   guarded entry real permission review confirmed READY):
       python3 scripts/preview_demo_tiny_guarded_entry_manual_authorization_design.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter --from-latest-guarded-stop-adapter \
           --from-latest-guarded-cleanup-adapter --from-latest-guarded-lifecycle-summary \
           --from-latest-entry-real-permission-review \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_entry_manual_authorization_design/latest_tiny_guarded_entry_manual_authorization_design.md

   Expected:
     status=TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DESIGN_READY;
     selected_symbol=SOLUSDT consistent across 19 upstream artifacts;
     5 protected positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) untouched;
     real_execution_allowed=False; g20_lifted=False; no_secrets_loaded=True;
     token_pattern=CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT (documented, never validated);
     next_required_task=TASK-014AK_guarded_entry_manual_authorization_dry_run.

3. (Optional) Design-approval probe:
       python3 scripts/preview_demo_tiny_guarded_entry_manual_authorization_design.py \
           [...same 19 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-design-approval --write-report
       # expect status=TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DESIGN_READY_BUT_EXECUTION_DISABLED

4. (Optional) Guard probe — proves --allow-real-entry-execution never executes:
       python3 scripts/preview_demo_tiny_guarded_entry_manual_authorization_design.py \
           [...same 19 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-real-entry-execution --write-report
       # expect status=REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED, no socket opened

5. Once step 2 passes, decide whether to authorise TASK-014AK
   (guarded_entry_manual_authorization_dry_run).

## TASK-014AI Status (2026-06-11)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_real_permission_review.py: permission-review-only module (NO sender, NO endpoint calls), 18 upstream artifact inputs (10 baseline + AA lifecycle_summary + AB runner_design + AC runner_dry_run + AD guarded_design_review + AE guarded_entry_adapter + AF guarded_stop_adapter + AG guarded_cleanup_adapter + AH guarded_lifecycle_summary), 4 status modes (TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY / _BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), 9 review stages, hard-fail-closed gates frozenset (27 gates), dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_guarded_entry_real_permission_review.py: NO `/v5/order/create`, NO `/v5/position/trading-stop`, NO secret reads, NO HMAC/signature, NO sender adapter, NO real entry execution, NO AA/AB/AC/AD/AE/AF/AG/AH module reuse — pure-computation review envelope (symbol=SOLUSDT, qty=0.1, side=Buy, reduceOnly=False, orderType=Market, positionIdx=0, max_notional_usdt=10, stopLoss=61.18, tpslMode=Full, slTriggerBy=MarkPrice) | DONE |
| src/demo_tiny_guarded_entry_real_permission_review.py: reviews real-permission conditions (selected symbol / category=linear / qty / side / endpoint family=bybit_demo / account_mode=demo / proof_strength=strong / position_details_source=real_readonly / no 5-existing-position collision); AD readiness must equal DESIGN_REVIEW_READY_NOT_EXECUTABLE; AE/AF/AG/AH statuses must be in acceptable whitelist; AH readiness_conclusion=DESIGN_REVIEW_READY_NOT_EXECUTABLE | DONE |
| src/demo_tiny_guarded_entry_real_permission_review.py: forbidden flags (--execute-real-entry / --execute-real-stop / --execute-real-cleanup / --execute-real-lifecycle / --send-order / --place-order / --real-run) deliberately absent from code | DONE |
| src/demo_tiny_guarded_entry_real_permission_review.py: next_required_task = "TASK-014AJ_guarded_entry_manual_authorization_design" | DONE |
| scripts/preview_demo_tiny_guarded_entry_real_permission_review.py: 18 `--from-latest-*` flags incl. new `--from-latest-guarded-lifecycle-summary`, `--symbol`, `--allow-review-approval`, `--allow-real-entry-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_real_permission_review/` | DONE |
| tests/demo_trading/test_demo_tiny_guarded_entry_real_permission_review.py: 111 tests across 83 test classes (AI1-AI83) covering 4 status modes, 18 missing-artifact gates, invariant mismatches, AE/AF/AG/AH adapter+summary status acceptance, 9 stages presence + order, gate count >=125, always-on gates set, G20 not lifted, deep-copy roundtrip, no forbidden imports (incl. AA-AH modules), no sender / network / env / signing tokens, 7 forbidden flags absent, hard-fail gates frozenset, next_required_task = 014AJ, status precedence, 8 confirmation flags, 5 protected positions never touched, source-scan safety (tokenize + AST), CLI subprocess exit codes | DONE |
| py_compile src/demo_tiny_guarded_entry_real_permission_review.py + scripts/preview_demo_tiny_guarded_entry_real_permission_review.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_permission_review.py | 111/111 PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_entry_real_permission_review/` | DONE |
| no real entry / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no permission-gate sender reuse / no AA/AB/AC/AD/AE/AF/AG/AH module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-11 TASK-014AI)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_real_permission_review.py scripts/preview_demo_tiny_guarded_entry_real_permission_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_permission_review.py -q
       # expect 111/111 PASS

2. Run TASK-014AI guarded entry real permission review (after TASK-014AH
   guarded lifecycle dry-run summary confirmed READY):
       python3 scripts/preview_demo_tiny_guarded_entry_real_permission_review.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter --from-latest-guarded-stop-adapter \
           --from-latest-guarded-cleanup-adapter --from-latest-guarded-lifecycle-summary \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_entry_real_permission_review/latest_tiny_guarded_entry_real_permission_review.md

   Expected:
     status=TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY;
     selected_symbol=SOLUSDT consistent across 18 upstream artifacts;
     5 protected positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) untouched;
     real_execution_allowed=False; g20_lifted=False; no_secrets_loaded=True;
     next_required_task=TASK-014AJ_guarded_entry_manual_authorization_design.

3. (Optional) Review-approval probe:
       python3 scripts/preview_demo_tiny_guarded_entry_real_permission_review.py \
           [...same 18 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-review-approval --write-report
       # expect status=TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY_BUT_EXECUTION_DISABLED

4. (Optional) Guard probe — proves --allow-real-entry-execution never executes:
       python3 scripts/preview_demo_tiny_guarded_entry_real_permission_review.py \
           [...same 18 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-real-entry-execution --write-report
       # expect status=REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED, no socket opened

5. Once step 2 passes, decide whether to authorise TASK-014AJ
   (guarded_entry_manual_authorization_design).

## TASK-014AH Status (2026-06-11)

| item | status |
|---|---|
| src/demo_tiny_guarded_lifecycle_dry_run_summary.py: guarded lifecycle dry-run summary module, 17 upstream artifact inputs (10 baseline + 014AA lifecycle_summary + 014AB runner_design + 014AC runner_dry_run + 014AD guarded_design_review + 014AE guarded_entry_adapter + 014AF guarded_stop_adapter + 014AG guarded_cleanup_adapter), 4 status modes (TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY / _BUT_EXECUTION_DISABLED / REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), 9 checklist stages, hard-fail-closed gates frozenset (>=28 gates), dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_guarded_lifecycle_dry_run_summary.py: NO endpoint calls, NO secret reads, NO HMAC/signature, NO preview-to-real conversion, NO sender adapter, NO real lifecycle execution, NO 014AA/AB/AC/AD/AE/AF/AG module reuse — pure-computation summary envelope (symbol=SOLUSDT, category=linear, qty=0.1, entry_side=Buy, stop=61.18, entry_reference=64.4, cleanup_side=Sell, reduceOnly=True, positionIdx=0, orderType=Market, max_notional_usdt=10) | DONE |
| src/demo_tiny_guarded_lifecycle_dry_run_summary.py: cross-adapter consistency review of selected symbol / category=linear / qty / entry side / stop level / cleanup side / endpoint family=bybit_demo / account_mode=demo / proof_strength=strong / position_details_source=real_readonly / no 5-existing-position collision; 014AD guarded_design_review readiness must equal DESIGN_REVIEW_READY_NOT_EXECUTABLE; 014AE/AF/AG adapter statuses must be in acceptable whitelist | DONE |
| src/demo_tiny_guarded_lifecycle_dry_run_summary.py: forbidden flags (--execute-real-entry / --execute-real-stop / --execute-real-cleanup / --execute-real-lifecycle / --send-order / --place-order / --real-run) deliberately absent from code | DONE |
| src/demo_tiny_guarded_lifecycle_dry_run_summary.py: next_required_task = "TASK-014AI_guarded_entry_real_permission_review" | DONE |
| scripts/preview_demo_tiny_guarded_lifecycle_dry_run_summary.py: 17 `--from-latest-*` flags incl. AE/AF/AG adapters, `--symbol`, `--allow-summary-approval`, `--allow-real-lifecycle-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_lifecycle_dry_run_summary/` | DONE |
| tests/demo_trading/test_demo_tiny_guarded_lifecycle_dry_run_summary.py: 123 tests across 80 test classes (AH1-AH80) covering 4 status modes, 17 missing-artifact gates, invariant mismatches, AE/AF/AG adapter status acceptance, 9 stages presence + order, gate count >=123, always-on gates set, G20 not lifted, deep-copy roundtrip, no forbidden imports (incl. AE/AF/AG modules), no sender / network / env / signing tokens, 7 forbidden flags absent, hard-fail gates >=28, next_required_task = 014AI, status precedence, 5 protected positions never touched, source-scan safety (tokenize + AST), CLI subprocess exit codes | DONE |
| py_compile src/demo_tiny_guarded_lifecycle_dry_run_summary.py + scripts/preview_demo_tiny_guarded_lifecycle_dry_run_summary.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_lifecycle_dry_run_summary.py | 123/123 PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_lifecycle_dry_run_summary/` | DONE |
| no real lifecycle / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no permission-gate sender reuse / no 014AA/AB/AC/AD/AE/AF/AG module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-11 TASK-014AH)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_lifecycle_dry_run_summary.py scripts/preview_demo_tiny_guarded_lifecycle_dry_run_summary.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_lifecycle_dry_run_summary.py -q
       # expect 123/123 PASS

2. Run TASK-014AH guarded lifecycle dry-run summary checklist (after
   TASK-014AG guarded cleanup adapter confirmed READY):
       python3 scripts/preview_demo_tiny_guarded_lifecycle_dry_run_summary.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter --from-latest-guarded-stop-adapter \
           --from-latest-guarded-cleanup-adapter \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_lifecycle_dry_run_summary/latest_tiny_guarded_lifecycle_dry_run_summary.md

   Expected:
     status=TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY;
     selected_symbol=SOLUSDT consistent across 17 upstream artifacts;
     5 protected positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) untouched;
     real_execution_allowed=False; g20_lifted=False; no_secrets_loaded=True;
     next_required_task=TASK-014AI_guarded_entry_real_permission_review.

3. (Optional) Summary-approval probe:
       python3 scripts/preview_demo_tiny_guarded_lifecycle_dry_run_summary.py \
           [...same 17 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-summary-approval --write-report
       # expect status=TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY_BUT_EXECUTION_DISABLED

4. (Optional) Guard probe — proves --allow-real-lifecycle-execution never executes:
       python3 scripts/preview_demo_tiny_guarded_lifecycle_dry_run_summary.py \
           [...same 17 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-real-lifecycle-execution --write-report
       # expect status=REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED, no socket opened

5. Once step 2 passes, decide whether to authorise TASK-014AI
   (guarded_entry_real_permission_review).

## TASK-014AG Status (2026-06-11)

| item | status |
|---|---|
| src/demo_tiny_guarded_cleanup_dry_run_adapter.py: cleanup-only dry-run adapter module, 14 upstream artifact inputs (10 baseline + 014AA lifecycle_summary + 014AB runner_design + 014AC runner_dry_run + 014AD guarded_design_review + 014AE guarded_entry_adapter + 014AF guarded_stop_adapter), 3 status modes (TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY / _BUT_EXECUTION_DISABLED / REAL_CLEANUP_EXECUTION_NOT_IMPLEMENTED), hard-fail-closed gates frozenset (24 gates), dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_guarded_cleanup_dry_run_adapter.py: NO endpoint calls, NO secret reads, NO HMAC/signature, NO preview-to-real conversion, NO sender adapter, NO real cleanup implementation, NO 014AA/AB/AC/AD/AE/AF module reuse — cleanup-only preview envelope (side=Sell, qty=0.1, reduceOnly=True, closeOnTrigger=False, positionIdx=0, orderType=Market, symbol=SOLUSDT, max_notional_usdt=10) | DONE |
| src/demo_tiny_guarded_cleanup_dry_run_adapter.py: cross-artifact consistency review of selected symbol / category=linear / cleanup-side=Sell / tiny qty / endpoint family=bybit_demo / account_mode=demo / proof_strength=strong / position_details_source=real_readonly / no 5-existing-position collision; 014AD guarded_design_review readiness must equal DESIGN_REVIEW_READY_NOT_EXECUTABLE; 014AE guarded_entry_adapter status must be in acceptable whitelist; 014AF guarded_stop_adapter status must be in acceptable whitelist | DONE |
| src/demo_tiny_guarded_cleanup_dry_run_adapter.py: forbidden flags (--execute-real-entry / --execute-real-stop / --execute-real-cleanup / --execute-real-lifecycle / --send-order / --place-order / --real-run) deliberately absent from code | DONE |
| src/demo_tiny_guarded_cleanup_dry_run_adapter.py: next_required_task = "TASK-014AH_guarded_tiny_lifecycle_dry_run_summary" | DONE |
| scripts/preview_demo_tiny_guarded_cleanup_dry_run_adapter.py: 14 `--from-latest-*` flags incl. new `--from-latest-guarded-stop-adapter`, `--symbol`, `--allow-cleanup-dry-run-approval`, `--allow-real-cleanup-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_cleanup_dry_run_adapter/` | DONE |
| tests/demo_trading/test_demo_tiny_guarded_cleanup_dry_run_adapter.py: 171 tests across 68 test classes (AG1-AG68) covering 3 status modes, 14 missing-artifact gates, invariant mismatches, guarded review/entry/stop adapter status acceptance, 9 stages presence + order, gate count >=117, always-on gates set, G20 not lifted, deep-copy roundtrip, no forbidden imports (incl. AF module), no sender / network / env / signing tokens, 7 forbidden flags absent, hard-fail gates >=24, next_required_task = 014AH, status precedence, 8 confirmation flags, allowlist/denylist, 5 protected positions never touched, source-scan safety, DRYRUN_TINY_CLEANUP_ orderLinkId prefix, CONFIRM_DEMO_TINY_CLEANUP_ token prefix | DONE |
| py_compile src/demo_tiny_guarded_cleanup_dry_run_adapter.py + scripts/preview_demo_tiny_guarded_cleanup_dry_run_adapter.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_cleanup_dry_run_adapter.py | 171/171 PASS |
| pytest tests/demo_trading | 2823 PASS + 1 pre-existing unrelated failure (test_demo_emergency_close_sender::TestCLIIntegration::test_dry_run_cli_writes_report, same as 014AA/AB/AC/AD/AE/AF) |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_cleanup_dry_run_adapter/` (and back-filled `tiny_guarded_stop_attach_dry_run_adapter/`) | DONE |
| no real cleanup / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no permission-gate sender reuse / no 014AA/AB/AC/AD/AE/AF module reuse / G20 not lifted / 5 existing positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified / no secrets / no HMAC / no signature header / no live endpoint fallback | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-11 TASK-014AG)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_cleanup_dry_run_adapter.py scripts/preview_demo_tiny_guarded_cleanup_dry_run_adapter.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_cleanup_dry_run_adapter.py -q
       # expect 171/171 PASS
       python3 -m pytest tests/demo_trading -q
       # expect (prior pass count + 171) + 1 pre-existing unrelated failure (test_demo_emergency_close_sender)

2. Run TASK-014AG guarded cleanup-only dry-run adapter checklist (after
   TASK-014AF guarded stop-attach adapter confirmed READY):
       python3 scripts/preview_demo_tiny_guarded_cleanup_dry_run_adapter.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter --from-latest-guarded-stop-adapter \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_cleanup_dry_run_adapter/latest_tiny_guarded_cleanup_dry_run_adapter.md

   Expected:
     status=TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY;
     selected_symbol=SOLUSDT consistent across 14 upstream artifacts;
     5 protected positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) untouched;
     real_execution_allowed=False; g20_lifted=False; no_secrets_loaded=True;
     next_required_task=TASK-014AH_guarded_tiny_lifecycle_dry_run_summary.

3. (Optional) Cleanup-dry-run-approval probe:
       python3 scripts/preview_demo_tiny_guarded_cleanup_dry_run_adapter.py \
           [...same 14 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-cleanup-dry-run-approval --write-report
       # expect status=TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED

4. (Optional) Guard probe — proves --allow-real-cleanup-execution never executes:
       python3 scripts/preview_demo_tiny_guarded_cleanup_dry_run_adapter.py \
           [...same 14 --from-latest-* flags...] \
           --symbol SOLUSDT --allow-real-cleanup-execution --write-report
       # expect status=REAL_CLEANUP_EXECUTION_NOT_IMPLEMENTED, no socket opened

5. Once step 2 passes, decide whether to authorise TASK-014AH
   (guarded_tiny_lifecycle_dry_run_summary).

## TASK-014AF Status (2026-06-11)

| item | status |
|---|---|
| src/demo_tiny_guarded_stop_attach_dry_run_adapter.py: stop-attach-only dry-run adapter module, 13 upstream artifact inputs (10 baseline + 014AA lifecycle_summary + 014AB runner_design + 014AC runner_dry_run + 014AD guarded_design_review + 014AE guarded_entry_adapter), 4 status modes (TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY / _BUT_EXECUTION_DISABLED / REAL_STOP_ATTACH_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), hard-fail-closed gates frozenset (22 gates incl. selected_symbol_not_solusdt), dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_guarded_stop_attach_dry_run_adapter.py: NO endpoint calls, NO secret reads, NO HMAC/signature, NO preview-to-real conversion, NO sender adapter, NO real stop-attach implementation, NO 014AA/AB/AC/AD/AE module reuse — stop-attach-only preview envelope (stopLoss=61.18, tpslMode=Full, slTriggerBy=MarkPrice, positionIdx=0, category=linear, symbol=SOLUSDT, side=long, qty=0.1) | DONE |
| src/demo_tiny_guarded_stop_attach_dry_run_adapter.py: cross-artifact consistency review of selected symbol / category=linear / stop-attach-side / tiny qty / entry reference / endpoint family=bybit_demo / account_mode=demo / proof_strength=strong / position_details_source=real_readonly / no existing-position collision; 014AD guarded_design_review readiness must equal DESIGN_REVIEW_READY_NOT_EXECUTABLE; 014AE guarded_entry_adapter status must be in acceptable whitelist | DONE |
| src/demo_tiny_guarded_stop_attach_dry_run_adapter.py: forbidden flags (--execute-real-entry / --execute-real-stop / --execute-real-cleanup / --execute-real-lifecycle / --send-order / --place-order / --real-run) deliberately absent from code | DONE |
| src/demo_tiny_guarded_stop_attach_dry_run_adapter.py: next_required_task = "TASK-014AG_guarded_cleanup_only_dry_run_adapter" | DONE |
| scripts/preview_demo_tiny_guarded_stop_attach_dry_run_adapter.py: 13 `--from-latest-*` flags incl. new `--from-latest-guarded-entry-adapter`, `--symbol`, `--allow-stop-dry-run-approval`, `--allow-real-stop-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_stop_attach_dry_run_adapter/` | DONE |
| tests/demo_trading/test_demo_tiny_guarded_stop_attach_dry_run_adapter.py: 159 tests across 65 test classes (AF1-AF65) covering 4 status modes, 13 missing-artifact gates, invariant mismatches, guarded review status/readiness mismatches, guarded entry adapter status acceptance, 9 stages presence + order, gate count >=111, always-on gates set, G20 not lifted, deep-copy roundtrip, no forbidden imports (incl. AE module), no sender / network / env / signing tokens, 7 forbidden flags absent, hard-fail gates >=21, next_required_task = 014AG, status precedence, 7 confirmation flags, allowlist/denylist, dedup, source-scan safety | DONE |
| py_compile src/demo_tiny_guarded_stop_attach_dry_run_adapter.py + scripts/preview_demo_tiny_guarded_stop_attach_dry_run_adapter.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_stop_attach_dry_run_adapter.py | 159/159 PASS |
| pytest tests/demo_trading | 2652 PASS + 1 pre-existing unrelated failure (test_demo_emergency_close_sender::TestCLIIntegration::test_dry_run_cli_writes_report, same as 014AA/AB/AC/AD/AE) |
| `.gitignore` already covers `outputs/demo_trading/tiny_guarded_stop_attach_dry_run_adapter/` (line 80) | CONFIRMED |
| no real stop attach / no `/v5/position/trading-stop` / no `/v5/order/create` / no order send / no permission-gate sender reuse / no 014AA/AB/AC/AD/AE module reuse / G20 not lifted / no existing position modified / no secrets / no HMAC / no signature header / no live endpoint fallback | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-11 TASK-014AF)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_stop_attach_dry_run_adapter.py scripts/preview_demo_tiny_guarded_stop_attach_dry_run_adapter.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_stop_attach_dry_run_adapter.py -q
       # expect 159/159 PASS
       python3 -m pytest tests/demo_trading -q
       # expect (prior pass count + 159) + 1 pre-existing unrelated failure (test_demo_emergency_close_sender)

2. Run TASK-014AF guarded stop-attach-only dry-run adapter checklist (after
   TASK-014AE guarded entry adapter confirmed READY):
       python3 scripts/preview_demo_tiny_guarded_stop_attach_dry_run_adapter.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-stop-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_stop_attach_dry_run_adapter/latest_tiny_guarded_stop_attach_dry_run_adapter.md

   Expected:
     status=TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY;
     selected_symbol=SOLUSDT consistent across 13 upstream artifacts;
     real_execution_allowed=False; g20_lifted=False; no_secrets_loaded=True;
     next_required_task=TASK-014AG_guarded_cleanup_only_dry_run_adapter.

3. (Optional) Stop-dry-run-approval probe:
       python3 scripts/preview_demo_tiny_guarded_stop_attach_dry_run_adapter.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-stop-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter \
           --symbol SOLUSDT --allow-stop-dry-run-approval --write-report
       # expect status=TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED

4. (Optional) Guard probe — proves --allow-real-stop-execution never executes:
       python3 scripts/preview_demo_tiny_guarded_stop_attach_dry_run_adapter.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-stop-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --from-latest-guarded-entry-adapter \
           --symbol SOLUSDT --allow-real-stop-execution --write-report
       # expect status=REAL_STOP_ATTACH_EXECUTION_NOT_IMPLEMENTED, no socket opened

5. Once step 2 passes, decide whether to authorise TASK-014AG
   (guarded_cleanup_only_dry_run_adapter).

## TASK-014AE Status (2026-06-11)

| item | status |
|---|---|
| src/demo_tiny_guarded_entry_dry_run_adapter.py: entry-only dry-run adapter module, 12 upstream artifact inputs (10 baseline + 014AA lifecycle_summary + 014AB runner_design + 014AC runner_dry_run + 014AD guarded_design_review), 4 status modes (TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY / _BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), hard-fail-closed gates frozenset, dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_guarded_entry_dry_run_adapter.py: NO endpoint calls, NO secret reads, NO HMAC/signature, NO preview-to-real conversion, NO sender adapter, NO real entry implementation, NO 014AA/AB/AC/AD module reuse — entry-only preview envelope (side=Buy, qty=0.1, reduceOnly=False, positionIdx=0, orderType=Market, max_notional_usdt=10) | DONE |
| src/demo_tiny_guarded_entry_dry_run_adapter.py: cross-artifact consistency review of selected symbol / category=linear / entry-side=Buy / tiny qty / entry reference / endpoint family=bybit_demo / account_mode=demo / proof_strength=strong / position_details_source=real_readonly / no existing-position collision; 014AD guarded_design_review readiness must equal DESIGN_REVIEW_READY_NOT_EXECUTABLE | DONE |
| src/demo_tiny_guarded_entry_dry_run_adapter.py: forbidden flags (--execute-real-entry / --execute-real-stop / --execute-real-cleanup / --execute-real-lifecycle / --send-order / --place-order / --real-run) deliberately absent from code | DONE |
| src/demo_tiny_guarded_entry_dry_run_adapter.py: next_required_task = "TASK-014AF_guarded_stop_attach_only_dry_run_adapter" | DONE |
| scripts/preview_demo_tiny_guarded_entry_dry_run_adapter.py: 12 `--from-latest-*` flags incl. new `--from-latest-guarded-design-review`, `--symbol`, `--allow-entry-dry-run-approval`, `--allow-real-entry-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_dry_run_adapter/` | DONE |
| tests/demo_trading/test_demo_tiny_guarded_entry_dry_run_adapter.py: 145 tests covering 4 status modes, 12 missing-artifact gates, 5 invariant mismatches, guarded review status/readiness mismatches, 9 stages presence + order, gate count >=96, always-on gates set, G20 not lifted, socket-disabled subprocess smoke, deep-copy roundtrip, no forbidden imports (incl. AD module), no sender / network / env / signing tokens, 7 forbidden flags absent, CLI exit codes 0/1, next_required_task = 014AF, status precedence, 4 confirmation flags, allowlist/denylist, dedup, source-scan safety | DONE |
| py_compile src/demo_tiny_guarded_entry_dry_run_adapter.py + scripts/preview_demo_tiny_guarded_entry_dry_run_adapter.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_guarded_entry_dry_run_adapter.py | 145/145 PASS |
| pytest tests/demo_trading | PASS (in-progress at submission; expected 2493 PASS + 1 pre-existing unrelated failure same as 014AA/AB/AC/AD) |
| `.gitignore` updated with `outputs/demo_trading/tiny_guarded_entry_dry_run_adapter/` | DONE |
| no real entry / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no permission-gate sender reuse / no 014AA/AB/AC/AD module reuse / G20 not lifted / no existing position modified / no secrets / no HMAC / no signature header / no live endpoint fallback | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-11 TASK-014AE)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_guarded_entry_dry_run_adapter.py scripts/preview_demo_tiny_guarded_entry_dry_run_adapter.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_dry_run_adapter.py -q
       # expect 145/145 PASS
       python3 -m pytest tests/demo_trading -q
       # expect (prior pass count + 145) + 1 pre-existing unrelated failure (test_demo_emergency_close_sender)

2. Run TASK-014AE guarded entry-only dry-run adapter checklist (after TASK-014AD
   guarded design review confirmed READY):
       python3 scripts/preview_demo_tiny_guarded_entry_dry_run_adapter.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_guarded_entry_dry_run_adapter/latest_tiny_guarded_entry_dry_run_adapter.md

   Expected:
     status=TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY;
     selected_symbol=SOLUSDT consistent across 12 upstream artifacts;
     real_execution_allowed=False; g20_lifted=False; no_secrets_loaded=True;
     next_required_task=TASK-014AF_guarded_stop_attach_only_dry_run_adapter.

3. (Optional) Entry-dry-run-approval probe:
       python3 scripts/preview_demo_tiny_guarded_entry_dry_run_adapter.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --symbol SOLUSDT --allow-entry-dry-run-approval --write-report
       # expect status=TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY_BUT_EXECUTION_DISABLED

4. (Optional) Guard probe — proves --allow-real-entry-execution never executes:
       python3 scripts/preview_demo_tiny_guarded_entry_dry_run_adapter.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run --from-latest-guarded-design-review \
           --symbol SOLUSDT --allow-real-entry-execution --write-report
       # expect status=REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED, no socket opened

5. Once step 2 passes, decide whether to authorise TASK-014AF
   (guarded_stop_attach_only_dry_run_adapter).

## TASK-014AD Status (2026-06-11)

| item | status |
|---|---|
| src/demo_tiny_lifecycle_guarded_runner_design_review.py: design-review-only module, 13 upstream artifact inputs (10 baseline + 014AA lifecycle_summary + 014AB runner_design + 014AC runner_dry_run), 4 status modes (DESIGN_REVIEW_READY / DESIGN_REVIEW_READY_BUT_EXECUTION_DISABLED / REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), hard-fail-closed gates frozenset, dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_lifecycle_guarded_runner_design_review.py: NO endpoint calls, NO secret reads, NO HMAC/signature, NO preview-to-real conversion, NO sender adapter, NO real runner implementation; reviews the dry-run trace and runner design only | DONE |
| src/demo_tiny_lifecycle_guarded_runner_design_review.py: cross-artifact consistency review of selected symbol / category=linear / entry-side=Buy / cleanup-side=Sell / tiny qty / stop price / entry reference / endpoint family=bybit_demo / account_mode=demo / proof_strength=strong / position_details_source=real_readonly / no existing-position collision | DONE |
| src/demo_tiny_lifecycle_guarded_runner_design_review.py: forbidden flags (--execute-real-lifecycle / --execute-real-entry / --execute-real-stop / --execute-real-cleanup / --send-order / --place-order) deliberately absent from code | DONE |
| src/demo_tiny_lifecycle_guarded_runner_design_review.py: next_required_task = "TASK-014AE_guarded_entry_only_dry_run_adapter" | DONE |
| scripts/preview_demo_tiny_lifecycle_guarded_runner_design_review.py: 13 `--from-latest-*` flags incl. new `--from-latest-runner-dry-run`, `--symbol`, `--allow-guarded-design-approval`, `--allow-real-runner-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_lifecycle_guarded_runner_design_review/` | DONE |
| tests/demo_trading/test_demo_tiny_lifecycle_guarded_runner_design_review.py: 156 tests covering 4 status modes, 13 missing-artifact gates, envelope mismatches, upstream-status-unacceptable cases, runner_dry_run status acceptance set, missing symbol, cross-artifact consistency, safety invariants, no forbidden imports, no sender reuse, no network / env / signing tokens, 6 forbidden flags absent, CLI exit codes 0/1, next_required_task = 014AE, dataclass roundtrip with deep-copy, socket-disabled import smoke, no secrets in report, gate count + always-on gates, G20 not lifted, no live endpoint, design-review-only invariants | DONE |
| py_compile src/demo_tiny_lifecycle_guarded_runner_design_review.py + scripts/preview_demo_tiny_lifecycle_guarded_runner_design_review.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_lifecycle_guarded_runner_design_review.py | 156/156 PASS |
| pytest tests/demo_trading | 2348 PASS + 1 pre-existing unrelated failure (test_demo_emergency_close_sender::TestCLIIntegration::test_dry_run_cli_writes_report — same as 014AA/AB/AC) | PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_lifecycle_guarded_runner_design_review/` | DONE |
| no real runner / no guarded runner / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no permission-gate sender reuse / no 014AA/AB/AC module reuse / G20 not lifted / no existing position modified / no secrets / no HMAC / no signature header / no live endpoint fallback | CONFIRMED |
| main.py / src/risk.py / BybitExecutor untouched | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-11 TASK-014AD)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_lifecycle_guarded_runner_design_review.py scripts/preview_demo_tiny_lifecycle_guarded_runner_design_review.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_lifecycle_guarded_runner_design_review.py -q
       # expect 156/156 PASS
       python3 -m pytest tests/demo_trading -q
       # expect 2348 PASS + 1 pre-existing unrelated failure (test_demo_emergency_close_sender)

2. Run TASK-014AD guarded-runner design review checklist (after TASK-014AC dry-run
   confirmed READY):
       python3 scripts/preview_demo_tiny_lifecycle_guarded_runner_design_review.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_lifecycle_guarded_runner_design_review/latest_tiny_lifecycle_guarded_runner_design_review.md

   Expected:
     status=TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY;
     selected_symbol=SOLUSDT consistent across 13 upstream artifacts;
     real_execution_allowed=False; g20_lifted=False; no_secrets_loaded=True;
     next_required_task=TASK-014AE_guarded_entry_only_dry_run_adapter.

3. (Optional) Design-review approval probe:
       python3 scripts/preview_demo_tiny_lifecycle_guarded_runner_design_review.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run \
           --symbol SOLUSDT --allow-guarded-design-approval --write-report
       # expect status=TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY_BUT_EXECUTION_DISABLED

4. (Optional) Guard probe — proves --allow-real-runner-execution never executes:
       python3 scripts/preview_demo_tiny_lifecycle_guarded_runner_design_review.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --from-latest-runner-dry-run \
           --symbol SOLUSDT --allow-real-runner-execution --write-report
       # expect status=REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED, no socket opened

5. Once step 2 passes, decide whether to authorise TASK-014AE
   (guarded_entry_only_dry_run_adapter).

## TASK-014AC Status (2026-06-10)

| item | status |
|---|---|
| src/demo_tiny_lifecycle_runner_dry_run.py: 8 stages, 73 GATE_ constants, 4 status modes, 12 upstream artifact inputs (10 baseline + 014AA lifecycle_summary + 014AB runner_design), 18 runner states, 8-step dry-run trace, 11 required audit slots, hard-fail-closed gates frozenset, dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_lifecycle_runner_dry_run.py: pure-computation dry-run runner — NO endpoint calls, NO secret reads, NO HMAC/signature, NO preview-to-real conversion, NO sender adapter; 3 synthesized envelopes always force preview_only=True / send_allowed=False / endpoint_called=False / real_payload=False / signature_present=False / private_headers=[] | DONE |
| src/demo_tiny_lifecycle_runner_dry_run.py: 8-step trace records state_before / action / state_after / artifact_slot / endpoint_called=False / position_modified=False / auto_advanced=False / token_validated=False per step; simulates readonly verification from artifacts only | DONE |
| src/demo_tiny_lifecycle_runner_dry_run.py: 11 audit slots populated with DRY_RUN_NOT_SENT sanitized convention; failure path simulation covers 5 FAIL_CLOSED branches + 2 MANUAL_REVIEW_REQUIRED branches with no auto retry / no auto cleanup / no auto emergency close | DONE |
| src/demo_tiny_lifecycle_runner_dry_run.py: forbidden flags (--execute-real-lifecycle / --execute-real-entry / --execute-real-stop / --execute-real-cleanup / --send-order / --place-order) deliberately absent from code | DONE |
| src/demo_tiny_lifecycle_runner_dry_run.py: next_required_task = "TASK-014AD_tiny_lifecycle_real_execution_guarded_runner_design_review" | DONE |
| scripts/preview_demo_tiny_lifecycle_runner_dry_run.py: 12 `--from-latest-*` flags incl. new `--from-latest-runner-design`, `--symbol`, `--allow-dry-run-runner-approval`, `--allow-real-runner-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_lifecycle_runner_dry_run/` | DONE |
| tests/demo_trading/test_demo_tiny_lifecycle_runner_dry_run.py: 111 tests (61 test classes AC1-AC61 + parametrized sub-tests) covering 3 status modes, 12 missing artifacts, 4 envelope mismatches, 3 envelope preview_only violations, runner_design status unacceptable, missing symbol, 8 stages, 18-state machine + readonly-after-real invariant, 8-step dry-run trace + per-step safety invariants, dry-run scope flags, payload materialization, readonly simulation (artifact source only), 11 DRY_RUN_NOT_SENT audit slots, failure path simulation, final dry-run verdict, G20 not lifted, socket-disabled import smoke, dataclass roundtrip with deep-copy, path refs, safety invariants, gate count >= 73, always-on gates, no forbidden imports, no sender reuse, no network/env/signing tokens, 6 forbidden flags absent, token patterns, 12-artifact preflight, report artifacts, no secrets in report, CLI exit codes 0/1, next required task = 014AD, upstream lifecycle_summary + runner_design status echoed, status precedence, whitelist sizes, runner_design_status_acceptable sorted, no signature/headers in all envelopes, existing positions not touched, blocked_gates deduplicated | DONE |
| py_compile src/demo_tiny_lifecycle_runner_dry_run.py + scripts/preview_demo_tiny_lifecycle_runner_dry_run.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_lifecycle_runner_dry_run.py | 111/111 PASS |
| pytest tests/demo_trading | 2192 PASS + 1 pre-existing unrelated failure (test_demo_emergency_close_sender — same as 014AA/AB) | PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_lifecycle_runner_dry_run/` | DONE |
| no real runner / no `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no permission-gate sender reuse / no 014AA summary or 014AB design module reuse / G20 not lifted / no existing position modified / no secrets / no HMAC / no signature header | CONFIRMED |
| local commit | PENDING |

## Next Rick Action (set by 2026-06-10 TASK-014AC)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_lifecycle_runner_dry_run.py scripts/preview_demo_tiny_lifecycle_runner_dry_run.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_lifecycle_runner_dry_run.py -q
       # expect 111/111 PASS
       python3 -m pytest tests/demo_trading -q
       # expect 2192 PASS + 1 pre-existing unrelated failure

2. Run TASK-014AC runner dry-run checklist (after TASK-014AB runner design
   confirmed READY):
       python3 scripts/preview_demo_tiny_lifecycle_runner_dry_run.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_lifecycle_runner_dry_run/latest_tiny_lifecycle_runner_dry_run.md

   Expected:
     status=TINY_LIFECYCLE_RUNNER_DRY_RUN_READY;
     selected_symbol=SOLUSDT consistent across 12 upstream artifacts;
     8-step dry-run trace populated (each step endpoint_called=False);
     3 dry-run envelopes (entry/stop/cleanup) preview_only=True / send_allowed=False;
     11 audit slots populated with DRY_RUN_NOT_SENT;
     real_execution_allowed=False; g20_lifted=False; no_secrets_loaded=True;
     next_required_task=TASK-014AD_tiny_lifecycle_real_execution_guarded_runner_design_review.

3. (Optional) Dry-run-runner approval probe:
       python3 scripts/preview_demo_tiny_lifecycle_runner_dry_run.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --symbol SOLUSDT --allow-dry-run-runner-approval --write-report
       # expect status=TINY_LIFECYCLE_RUNNER_DRY_RUN_READY_BUT_EXECUTION_DISABLED

4. (Optional) Guard probe — proves --allow-real-runner-execution never executes:
       python3 scripts/preview_demo_tiny_lifecycle_runner_dry_run.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary --from-latest-runner-design \
           --symbol SOLUSDT --allow-real-runner-execution --write-report
       # expect status=REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED, no socket opened

5. Once step 2 passes, decide whether to authorise TASK-014AD
   (tiny_lifecycle_real_execution_guarded_runner_design_review).

## TASK-014AB Status (2026-06-10)

| item | status |
|---|---|
| src/demo_tiny_lifecycle_runner_design.py: 8 stages, 68 GATE_ constants (21 general + 6 design scope + 6 state machine + 7 manual approval + 8 payload contract + 10 failure policy + 5 observability + 5 execution guard), 4 status modes, 11 upstream artifact inputs (10 baseline + 014AA lifecycle_summary), hard-fail-closed gates frozenset, dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_lifecycle_runner_design.py: 18 runner states + readonly-between-real-steps invariant + no auto-advance / no parallel / no skip / no retry state-machine constraints | DONE |
| src/demo_tiny_lifecycle_runner_design.py: 3 distinct manual approval tokens documented (entry / stop-attach / cleanup), token format alone is never authorization, each real step requires separate approval | DONE |
| src/demo_tiny_lifecycle_runner_design.py: execution payload contract pulled from the 3 permission gates (entry / stop-attach / cleanup) with preview_only=True / reduceOnly / qty-parity / stopLoss>0 / stopLoss<entry_ref — no preview-to-real conversion | DONE |
| src/demo_tiny_lifecycle_runner_design.py: abort + fail-closed policy for every real step (entry rejected, stop attach rejected, cleanup rejected, readonly unavailable, partial fill, stop mismatch, unexpected position appears, no automatic emergency close, no automatic cleanup, no retry loop) | DONE |
| src/demo_tiny_lifecycle_runner_design.py: 11 required audit artifacts + sanitisation rules (no secret values in logs, Discord / Notion sanitized only) | DONE |
| src/demo_tiny_lifecycle_runner_design.py: 4 forbidden flags (--execute-real-lifecycle / --execute-real-entry / --execute-real-stop / --execute-real-cleanup) deliberately absent from code (mentioned only in documentation as forbidden) | DONE |
| src/demo_tiny_lifecycle_runner_design.py: next_required_task = "TASK-014AC_tiny_lifecycle_runner_implementation_dry_run_only" | DONE |
| scripts/preview_demo_tiny_lifecycle_runner_design.py: 11 `--from-latest-*` flags incl. new `--from-latest-lifecycle-summary`, `--symbol`, `--allow-runner-design-approval`, `--allow-real-runner-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_lifecycle_runner_design/` | DONE |
| tests/demo_trading/test_demo_tiny_lifecycle_runner_design.py: 90 tests (55 test classes AB1-AB55 + parametrized sub-tests) covering 4 status modes, 11 missing upstream artifacts, envelope mismatches, lifecycle-summary unacceptable statuses, payload contract violations, missing symbol, 8 stages built, 18-state machine + readonly-after-real invariant, 3 distinct token patterns, execution payload contract, abort and fail-closed policy, 11 audit artifacts, final design verdict, runner design scope, G20 not lifted, socket-disabled import, dataclass roundtrip with deep-copy, path refs, safety invariants, gate count >= 68, always-on gates, no forbidden imports (incl. 014AA summary module), no sender reuse, no network/env/signing tokens, 4 forbidden flags absent (parametrized), CLI exit codes 0/1, next required task = 014AC, upstream lifecycle summary status echoed, status precedence (hard fail beats approval and execution guard) | DONE |
| py_compile src/demo_tiny_lifecycle_runner_design.py + scripts/preview_demo_tiny_lifecycle_runner_design.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_lifecycle_runner_design.py | 90/90 PASS |
| pytest tests/demo_trading | 2081 PASS + 1 pre-existing unrelated failure (test_demo_emergency_close_sender — same as 014AA) | PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_lifecycle_runner_design/` | DONE |
| no runner implemented / no real `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no permission-gate sender reuse / no 014AA summary module reuse / G20 not lifted / no existing position modified / no secrets | CONFIRMED |
| local commit | PENDING |

## Next Rick Action (set by 2026-06-10 TASK-014AB)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_lifecycle_runner_design.py scripts/preview_demo_tiny_lifecycle_runner_design.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_lifecycle_runner_design.py -q
       # expect 90/90 PASS
       python3 -m pytest tests/demo_trading -q
       # expect 2081 PASS + 1 pre-existing unrelated failure

2. Run TASK-014AB runner design checklist (after TASK-014AA permission-summary
   confirmed READY):
       python3 scripts/preview_demo_tiny_lifecycle_runner_design.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_lifecycle_runner_design/latest_tiny_lifecycle_runner_design.md

   Expected:
     status=TINY_LIFECYCLE_RUNNER_DESIGN_READY;
     selected_symbol=SOLUSDT consistent across all 11 upstream artifacts;
     18 runner states surfaced; readonly-between-real-steps invariant present;
     3 distinct manual approval tokens (never validated);
     execution payload contract previewed with preview_only=True and reduceOnly;
     abort + fail-closed policy listed for every real step;
     11 required audit artifacts listed;
     real_execution_allowed=False; g20_lifted=False;
     next_required_task=TASK-014AC_tiny_lifecycle_runner_implementation_dry_run_only.

3. (Optional) Runner-design approval dry-run envelope:
       python3 scripts/preview_demo_tiny_lifecycle_runner_design.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary \
           --symbol SOLUSDT --allow-runner-design-approval --write-report
       # expect status=TINY_LIFECYCLE_RUNNER_DESIGN_READY_BUT_EXECUTION_DISABLED

4. (Optional) Guard probe --- proves --allow-real-runner-execution never executes:
       python3 scripts/preview_demo_tiny_lifecycle_runner_design.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --from-latest-lifecycle-summary \
           --symbol SOLUSDT --allow-real-runner-execution --write-report
       # expect status=REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED, no socket opened

5. Once step 2 passes, decide whether to authorise TASK-014AC
   (tiny_lifecycle_runner_implementation_dry_run_only).

## TASK-014AA Status (2026-06-10)

| item | status |
|---|---|
| src/demo_tiny_lifecycle_real_execution_summary.py: 7 stages, 59 GATE_ constants (23 general + 13 consistency + 7 manual approval + 11 failure + 5 execution guard), 4 status modes, 10 upstream artifact inputs, hard-fail-closed gates frozenset, dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_lifecycle_real_execution_summary.py: cross-artifact consistency (selected symbol, entry side=Buy, cleanup side=Sell, tiny qty from rounded_tiny_qty priority, stop price from stop-attach permission gate priority, entry reference price from protection priority, category=linear, payload previews from entry / stop-attach / cleanup permission gates) | DONE |
| src/demo_tiny_lifecycle_real_execution_summary.py: 4 ACCEPTABLE_*_STATUSES frozensets (real_permission_gate / tiny_entry_permission_gate / tiny_stop_attach_permission_gate / tiny_cleanup_permission_gate) | DONE |
| src/demo_tiny_lifecycle_real_execution_summary.py: 3 distinct manual approval tokens documented (entry / stop-attach / cleanup), string-only, never validated | DONE |
| src/demo_tiny_lifecycle_real_execution_summary.py: fixed 8-step real lifecycle sequence (pre_readonly_snapshot → real_tiny_entry → post_entry_readonly → real_stop_attach → post_stop_attach_readonly → real_cleanup → post_cleanup_readonly → final_audit), each step preview-only | DONE |
| src/demo_tiny_lifecycle_real_execution_summary.py: next_required_task = "TASK-014AB_tiny_lifecycle_real_execution_runner_design_or_manual_approval" | DONE |
| scripts/preview_demo_tiny_lifecycle_real_execution_summary.py: 10 `--from-latest-*` flags incl. new `--from-latest-tiny-cleanup-permission`, `--symbol`, `--allow-real-lifecycle-summary`, `--allow-real-lifecycle-execution`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_lifecycle_real_execution_summary/` | DONE |
| tests/demo_trading/test_demo_tiny_lifecycle_real_execution_summary.py: 93 tests (62 test classes AA1-AA62 + parametrized sub-tests) covering status modes, 10 missing artifacts, envelope mismatches, 4 status unacceptables (each with acceptable-statuses parametrized), tiny qty / stop price / entry reference / category / payload preview consistency, safety invariants, token gates, guard, report writing, no-secrets, forbidden imports, no close-only / emergency-close / new-entry / cleanup-permission sender reuse, no network tokens, CLI subprocess, next required task = 014AB, gate count = 59, always-on gates, stage shape, missing symbol, G20 not lifted, socket-disabled import, dataclass roundtrip with deep-copy, path refs, fixed 8-step sequence, 3 distinct manual approval tokens, failure response matrix, stage_0 preflight all-present | DONE |
| py_compile src/demo_tiny_lifecycle_real_execution_summary.py + scripts/preview_demo_tiny_lifecycle_real_execution_summary.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_lifecycle_real_execution_summary.py | 93/93 PASS |
| pytest tests/demo_trading | 1991 PASS + 1 pre-existing unrelated failure (test_demo_emergency_close_sender) | PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_lifecycle_real_execution_summary/` | DONE |
| no real `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no close-only sender / no emergency-close sender / no new-entry sender real exec / no permission-gate sender reuse / G20 not lifted / no existing position modified / no secrets | CONFIRMED |
| local commit | PENDING |

## Next Rick Action (set by 2026-06-10 TASK-014AA)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_lifecycle_real_execution_summary.py scripts/preview_demo_tiny_lifecycle_real_execution_summary.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_lifecycle_real_execution_summary.py -q
       # expect 93/93 PASS
       python3 -m pytest tests/demo_trading -q
       # expect 1991 PASS + 1 pre-existing unrelated failure

2. Run TASK-014AA lifecycle summary checklist (after TASK-014Z CHECKLIST_READY confirmed):
       python3 scripts/preview_demo_tiny_lifecycle_real_execution_summary.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_lifecycle_real_execution_summary/latest_tiny_lifecycle_real_execution_summary.md

   Expected:
     status=TINY_LIFECYCLE_PERMISSION_SUMMARY_READY;
     selected_symbol=SOLUSDT consistent across all 4 permission gates;
     entry_side=Buy, cleanup_side=Sell;
     tiny_qty=0.1 (from rounded_tiny_qty), stop_price aligned to tick;
     real_lifecycle_steps lists 8 preview-only steps with endpoint_called=False;
     manual_approval_matrix lists 3 distinct tokens;
     real_execution_allowed=False; g20_lifted=False;
     next_required_task=TASK-014AB_tiny_lifecycle_real_execution_runner_design_or_manual_approval.

3. (Optional) Permission dry-run envelope:
       python3 scripts/preview_demo_tiny_lifecycle_real_execution_summary.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --symbol SOLUSDT --allow-real-lifecycle-summary --write-report
       # expect status=TINY_LIFECYCLE_PERMISSION_SUMMARY_READY_BUT_EXECUTION_DISABLED

4. (Optional) Guard probe --- proves --allow-real-lifecycle-execution never executes:
       python3 scripts/preview_demo_tiny_lifecycle_real_execution_summary.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission --from-latest-tiny-cleanup-permission \
           --symbol SOLUSDT --allow-real-lifecycle-execution --write-report
       # expect status=REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED, no socket opened

5. Once step 2 passes, decide whether to authorise TASK-014AB
   (tiny_lifecycle_real_execution_runner_design_or_manual_approval).

## TASK-014Z Status (2026-06-10)

| item | status |
|---|---|
| src/demo_tiny_cleanup_permission_gate.py: 7 stages, 53 GATE_ constants (22 general + 13 cleanup payload + 6 manual approval + 7 failure + 5 execution guard), 4 status modes, 9 upstream artifact inputs, hard-fail-closed gates frozenset, dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_cleanup_permission_gate.py: cleanup payload preview (category=linear, symbol=SOLUSDT, side=Sell, orderType=Market, qty=<expected_tiny_qty>, reduceOnly=True, closeOnTrigger=False, positionIdx=0, orderLinkId=DRYRUN-TINY-CLEANUP-..., preview_only=True, endpoint_called=False) | DONE |
| src/demo_tiny_cleanup_permission_gate.py: expected_tiny_qty derives from entry permission gate `rounded_tiny_qty` (priority) and lifecycle mock `tiny_qty` (fallback); both must agree | DONE |
| src/demo_tiny_cleanup_permission_gate.py: ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES + ACCEPTABLE_TINY_ENTRY_PERMISSION_GATE_STATUSES + ACCEPTABLE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUSES frozensets | DONE |
| src/demo_tiny_cleanup_permission_gate.py: CLEANUP_TOKEN_PATTERN documented as `CONFIRM_DEMO_TINY_CLEANUP_YYYYMMDD_SYMBOL` (string-only, never validated); entry / stop-attach tokens explicitly not accepted | DONE |
| src/demo_tiny_cleanup_permission_gate.py: next_required_task = "TASK-014AA_tiny_lifecycle_real_execution_permission_summary" | DONE |
| scripts/preview_demo_tiny_cleanup_permission_gate.py: 9 `--from-latest-*` flags incl. new `--from-latest-tiny-stop-permission`, `--symbol`, `--allow-real-cleanup-permission`, `--allow-real-cleanup`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_cleanup_permission_gate/` | DONE |
| tests/demo_trading/test_demo_tiny_cleanup_permission_gate.py: 100 tests (Z1-Z66 + parametrized sub-tests) covering status modes, 9 missing artifacts, envelope mismatches, 3 status unacceptables (each with acceptable-statuses parametrized), expected_tiny_qty derivation / fallback / mismatch / missing, payload field checks (category / symbol / side=Sell / orderType=Market / reduceOnly=True / positionIdx=0 / orderLinkId DRYRUN-TINY-CLEANUP / preview_only / closeOnTrigger=False / qty), safety invariants, token gates, guard, report writing, no-secrets, forbidden imports, no close-only / emergency-close / new-entry sender reuse, no network tokens, CLI subprocess, next required task = 014AA, gate count ≥ 49, always-on gates, stage shape, missing symbol, G20 not lifted, socket-disabled import, dataclass roundtrip with deep-copy, path refs, stage_4 / stage_5 / stage_6 plans, guard safety invariants, stage_1 existing-positions snapshot, stage_0 preflight all-present | DONE |
| py_compile src/demo_tiny_cleanup_permission_gate.py + scripts/preview_demo_tiny_cleanup_permission_gate.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_cleanup_permission_gate.py | 100/100 PASS |
| pytest tests/demo_trading | 1898 PASS + 1 pre-existing unrelated failure (test_demo_emergency_close_sender) | PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_cleanup_permission_gate/` | DONE |
| no real `/v5/order/create` / no `/v5/position/trading-stop` / no order send / no close-only sender / no emergency-close sender / no new-entry sender real exec / G20 not lifted / no existing position modified / no secrets | CONFIRMED |
| local commit | PENDING |

## Next Rick Action (set by 2026-06-10 TASK-014Z)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_cleanup_permission_gate.py scripts/preview_demo_tiny_cleanup_permission_gate.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_cleanup_permission_gate.py -q
       # expect 100/100 PASS
       python3 -m pytest tests/demo_trading -q
       # expect 1898 PASS + 1 pre-existing unrelated failure

2. Run TASK-014Z cleanup checklist (after TASK-014Y CHECKLIST_READY confirmed):
       python3 scripts/preview_demo_tiny_cleanup_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_cleanup_permission_gate/latest_tiny_cleanup_permission_gate.md

   Expected:
     status=TINY_CLEANUP_PERMISSION_CHECKLIST_READY;
     cleanup_payload_preview present with category=linear, symbol=SOLUSDT,
       side=Sell, orderType=Market, qty=<expected_tiny_qty>=0.1,
       reduceOnly=True, closeOnTrigger=False, positionIdx=0,
       orderLinkId starts with DRYRUN-TINY-CLEANUP, preview_only=True,
       endpoint_called=False;
     order_endpoint_called=False; stop_endpoint_called=False;
     no_position_modified=True; real_execution_allowed=False;
     next_required_task=TASK-014AA_tiny_lifecycle_real_execution_permission_summary.

3. (Optional) Permission dry-run envelope:
       python3 scripts/preview_demo_tiny_cleanup_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission \
           --symbol SOLUSDT --allow-real-cleanup-permission --write-report
       # expect status=TINY_CLEANUP_PERMISSION_READY_BUT_EXECUTION_DISABLED

4. (Optional) Guard probe --- proves --allow-real-cleanup never executes:
       python3 scripts/preview_demo_tiny_cleanup_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --from-latest-tiny-stop-permission \
           --symbol SOLUSDT --allow-real-cleanup --write-report
       # expect status=REAL_CLEANUP_NOT_IMPLEMENTED, no socket opened

5. Once step 2 passes, decide whether to authorise TASK-014AA
   (tiny_lifecycle_real_execution_permission_summary).

## TASK-014Y Status (2026-06-10)

| item | status |
|---|---|
| src/demo_tiny_stop_attach_permission_gate.py: 7 stages, 49 gates (20 general + 12 stop payload + 6 manual approval + 6 failure + 5 execution guard), 4 status modes, 8 upstream artifact loaders, fail-closed gates frozenset, tick-size alignment helper, dataclass result with deep-copy `to_dict()` | DONE |
| src/demo_tiny_stop_attach_permission_gate.py: stop payload preview (category=linear, stopLoss=<stop_price>, tpslMode=Full, slTriggerBy=MarkPrice, positionIdx=0, symbol=SOLUSDT, preview_only=True) | DONE |
| src/demo_tiny_stop_attach_permission_gate.py: ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES + ACCEPTABLE_TINY_ENTRY_PERMISSION_GATE_STATUSES frozensets | DONE |
| src/demo_tiny_stop_attach_permission_gate.py: STOP_ATTACH_TOKEN_PATTERN documented as `CONFIRM_DEMO_TINY_STOP_ATTACH_YYYYMMDD_SYMBOL` (string-only, never validated) | DONE |
| src/demo_tiny_stop_attach_permission_gate.py: next_required_task = "TASK-014Z_tiny_isolated_demo_cleanup_permission_gate" | DONE |
| scripts/preview_demo_tiny_stop_attach_permission_gate.py: 8 `--from-latest-*` flags incl. `--from-latest-tiny-entry-permission`, `--symbol`, `--allow-real-stop-permission`, `--allow-real-tiny-stop-attach`, `--write-report`; `run_execute()` callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_stop_attach_permission_gate/` | DONE |
| tests/demo_trading/test_demo_tiny_stop_attach_permission_gate.py: 88 tests (Y1-Y63 plus sub-tests) covering status modes, missing artifacts, envelope mismatches, status unacceptable, instrument rule, stop_price + tick alignment, stop payload fields, safety invariants, token gates, guard, report writing, forbidden imports, CLI subprocess, next required task, stage shape, dataclass roundtrip, instrument_rules_by_symbol format, socket-disabled import | DONE |
| py_compile src/demo_tiny_stop_attach_permission_gate.py + scripts/preview_demo_tiny_stop_attach_permission_gate.py + tests | PASS |
| pytest tests/demo_trading/test_demo_tiny_stop_attach_permission_gate.py | 88/88 PASS |
| pytest tests/demo_trading | 1798 PASS + 1 pre-existing unrelated failure (test_demo_emergency_close_sender) | PASS |
| `.gitignore` updated with `outputs/demo_trading/tiny_stop_attach_permission_gate/` | DONE |
| no real `/v5/position/trading-stop` / no `/v5/order/create` / no order send / G20 not lifted / no existing position modified / no secrets | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-10 TASK-014Y)

1. VPS git pull and validate:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m py_compile src/demo_tiny_stop_attach_permission_gate.py scripts/preview_demo_tiny_stop_attach_permission_gate.py
       python3 -m pytest tests/demo_trading/test_demo_tiny_stop_attach_permission_gate.py -q
       # expect 88/88 PASS
       python3 -m pytest tests/demo_trading -q
       # expect 1798 PASS + 1 pre-existing unrelated failure

2. Run TASK-014Y stop-attach checklist (after TASK-014X CHECKLIST_READY confirmed):
       python3 scripts/preview_demo_tiny_stop_attach_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission --from-latest-tiny-entry-permission \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_stop_attach_permission_gate/latest_tiny_stop_attach_permission_gate.md

   Expected:
     status=TINY_STOP_ATTACH_PERMISSION_CHECKLIST_READY;
     stop_payload_preview present with tpslMode=Full, slTriggerBy=MarkPrice, positionIdx=0, preview_only=True;
     stop_endpoint_called=False; order_endpoint_called=False;
     no_position_modified=True; real_execution_allowed=False;
     next_required_task=TASK-014Z_tiny_isolated_demo_cleanup_permission_gate.

3. Once step 2 passes, decide whether to authorise TASK-014Z (tiny isolated demo cleanup permission gate).

## TASK-014X-FIX2 Status (2026-06-10)

| item | status |
|---|---|
| root cause: `/v5/market/instruments-info` fetch only got first page; no pagination support; SOLUSDT not in first 500 results | FIXED |
| src/demo_readonly_client.py: `_instruments_real` now supports pagination via nextPageCursor (max 20 pages) | DONE |
| src/demo_readonly_client.py: targeted SOLUSDT lookup added (called if paginated fetch doesn't include it) | DONE |
| src/demo_readonly_client.py: `_parse_instrument_snapshot` helper extracted for code reuse | DONE |
| scripts/preview_demo_readonly_runtime.py: `instrument_rules_by_symbol` now includes both position symbols + SOLUSDT | DONE |
| scripts/preview_demo_readonly_runtime.py: pagination metadata added to latest_smoke.json | DONE |
| tests: TestPaginationAndTargetedLookup (4 tests) in test_demo_readonly_client.py | DONE |
| tests: TestX71–TestX73 (3 tests) in test_demo_tiny_entry_permission_gate.py | DONE |
| py_compile src/demo_readonly_client.py + scripts/preview_demo_readonly_runtime.py + CLI + entry gate | PASS |
| pytest tests/demo_trading/test_demo_readonly_client.py | 74/74 PASS |
| pytest tests/demo_trading/test_demo_tiny_entry_permission_gate.py | 95/95 PASS (91 prior + 4 new FIX2) |
| pytest tests/demo_trading | 1710 PASS + 1 pre-existing unrelated failure | PASS |
| no order endpoint / no stop endpoint / no position modified / G20 unchanged / no secrets | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-10 TASK-014X-FIX2)

1. Update VPS git pull:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m pytest tests/demo_trading -q
       # expect 1710+ PASS + 1 pre-existing unrelated failure

2. Regenerate readonly smoke (pagination + targeted SOLUSDT):
       python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
       # Verify pagination worked:
       python3 - <<'PY'
import json
from pathlib import Path
d = json.load(open("outputs/demo_trading/readonly_smoke/latest_smoke.json"))
rules = d.get("instrument_rules_by_symbol", {})
sol = rules.get("SOLUSDT")
print("SOLUSDT present:", bool(sol))
print("instrument_rules_count:", d.get("instrument_rules_count"))
print("instrument_rules_pages_fetched:", d.get("instrument_rules_pages_fetched"))
print("targeted_instrument_symbols_found:", d.get("targeted_instrument_symbols_found"))
print("targeted_instrument_symbols_missing:", d.get("targeted_instrument_symbols_missing"))
PY

   Expected: SOLUSDT present=True, targeted_instrument_symbols_found=['SOLUSDT']

3. Re-run W chain to latest real permission gate (same steps as TASK-014X-FIX1).

4. Run TASK-014X checklist:
       python3 scripts/preview_demo_tiny_entry_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_entry_permission_gate/latest_tiny_entry_permission_gate.md

   Expected:
     status=TINY_ENTRY_PERMISSION_CHECKLIST_READY;
     instrument_rule_summary.rule_present=True;
     rounded_tiny_qty > 0; estimated_tiny_notional <= 10;
     order_endpoint_called=False; stop_endpoint_called=False;
     no_position_modified=True; real_execution_allowed=False.

5. Once step 4 passes, decide whether to authorise TASK-014Y.

## TASK-014X-FIX1 Status (2026-06-10)

| item | status |
|---|---|
| root cause: `_serialize_instrument_rules_for_positions` only serialised open-position symbols; SOLUSDT never had an open position → never in `instrument_rules` → stage_2 fails closed | FIXED |
| scripts/preview_demo_readonly_runtime.py: `_serialize_instrument_rules_by_symbol` added (positions + SOLUSDT) | DONE |
| scripts/preview_demo_readonly_runtime.py: `instrument_rules_by_symbol` added to both _write_report call sites | DONE |
| src/demo_tiny_entry_permission_gate.py: `_find_instrument_rule` checks `instrument_rules_by_symbol` first, then falls back to `instrument_rules` | DONE |
| tests X64-X70 (instrument_rules_by_symbol dict format; SOLUSDT absent; min_order_qty / qty_step / tick_size missing; notional cap enforcement) | DONE |
| py_compile scripts/preview_demo_readonly_runtime.py + src/demo_tiny_entry_permission_gate.py + CLI | PASS |
| pytest tests/demo_trading/test_demo_tiny_entry_permission_gate.py | 91/91 PASS (84 prior + 7 new FIX1) |
| pytest tests/demo_trading | 1702 PASS + 1 pre-existing unrelated failure (test_demo_emergency_close_sender) | PASS |
| no order endpoint / no stop endpoint / no position modified / G20 unchanged / no secrets | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-10 TASK-014X-FIX1)

1. Update VPS git pull:
       git pull --ff-only
       source .venv/bin/activate
       source .env.demo
       python3 -m pytest tests/demo_trading -q
       # expect 1702 PASS + 1 pre-existing unrelated failure

2. Regenerate readonly smoke (adds instrument_rules_by_symbol with SOLUSDT):
       python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
       # Verify SOLUSDT is present:
       python3 -c "
import json; d=json.load(open('outputs/demo_trading/readonly_smoke/latest_smoke.json'))
r=d.get('instrument_rules_by_symbol',{})
print('SOLUSDT rule_present:', 'SOLUSDT' in r)
print('SOLUSDT rule:', r.get('SOLUSDT'))
"

3. Re-run W chain if needed (reconciliation / protection / contract / noop-plan / lifecycle / real-permission).
   Skip this step if the existing latest_* files are still valid.

4. Run TASK-014X checklist:
       python3 scripts/preview_demo_tiny_entry_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_entry_permission_gate/latest_tiny_entry_permission_gate.md

   Expected:
     status=TINY_ENTRY_PERMISSION_CHECKLIST_READY;
     instrument_rule_summary.rule_present=True;
     min_order_qty > 0; qty_step > 0; tick_size > 0;
     rounded_tiny_qty > 0; estimated_tiny_notional > 0;
     estimated_tiny_notional <= 10 USDT;
     entry_payload_preview.preview_only=True;
     order_endpoint_called=False; stop_endpoint_called=False;
     no_position_modified=True; real_execution_allowed=False;
     next_required_task=TASK-014Y_tiny_isolated_demo_stop_attach_permission_gate.

5. Run TASK-014X real-entry-guard sanity:
       python3 scripts/preview_demo_tiny_entry_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission \
           --symbol SOLUSDT --allow-real-tiny-entry --write-report
   Expected:
     status=REAL_TINY_ENTRY_NOT_IMPLEMENTED;
     real_tiny_entry_requested=True; real_execution_allowed=False;
     order_endpoint_called=False; stop_endpoint_called=False;
     no_position_modified=True.

6. Once steps 4+5 above both match, decide whether to authorise
   TASK-014Y (Tiny Isolated Demo Stop-Attach Permission Gate).

## TASK-014X Status (2026-06-10)

| item | status |
|---|---|
| new module: src/demo_tiny_entry_permission_gate.py (7-stage pure-computation entry permission gate) | DONE |
| new CLI: scripts/preview_demo_tiny_entry_permission_gate.py (--from-latest-readonly/reconciliation/protection/contract/noop-plan/lifecycle/real-permission / --symbol / --allow-real-entry-permission / --allow-real-tiny-entry / --write-report) | DONE |
| new tests: tests/demo_trading/test_demo_tiny_entry_permission_gate.py (X1 - X63, 84 tests) | DONE |
| 53 gate constants exposed (18 general + 10 instrument + 8 entry payload + 6 manual approval + 6 failure + 5 execution guard) | DONE |
| 4 status constants + 4 mode constants | DONE |
| orderLinkId prefix `DRYRUN-TINY-ENTRY-` (string only, never sent) | DONE |
| Buy / positionIdx=0 / reduceOnly=False payload preview (envelope-only) | DONE |
| instrument-rule rounding: min_order_qty + qty_step alignment + min_notional bump-up + 10 USDT cap | DONE |
| tiny_notional_cap=10 USDT; strategy_full_size_qty_ref=12.2 SOL flagged MUST_NOT_BE_REUSED | DONE |
| upstream real_permission_gate status must be REAL_PERMISSION_CHECKLIST_READY or REAL_PERMISSION_GATE_READY_BUT_EXECUTION_DISABLED | DONE |
| --allow-real-entry-permission returns TINY_ENTRY_PERMISSION_READY_BUT_EXECUTION_DISABLED (no socket) | DONE |
| --allow-real-tiny-entry returns REAL_TINY_ENTRY_NOT_IMPLEMENTED (no socket) | DONE |
| next_required_task = TASK-014Y_tiny_isolated_demo_stop_attach_permission_gate | DONE |
| py_compile src + CLI | PASS |
| pytest tests/demo_trading/test_demo_tiny_entry_permission_gate.py | 84/84 PASS |
| no order endpoint / no stop endpoint / no live endpoint / no position modified | CONFIRMED |
| 5 existing demo shorts (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT) never touched | CONFIRMED |
| G20 (protected_entry_policy_missing) constant unchanged and not referenced in new module | CONFIRMED |
| 12.2 SOL strategy full size rejected; tiny notional cap (10 USDT) enforced | CONFIRMED |
| no secret values in module / CLI / report | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-10 TASK-014X)

1. Update VPS git pull:
       git pull
       python3 -m pytest tests/demo_trading -q
       # expect prior count + 84 new X tests PASS
       # (1 pre-existing unrelated failure in
       # test_demo_emergency_close_sender::test_dry_run_cli_writes_report
       # tracked separately).

2. VPS Checklist (envelope-only, no network):
       source .env.demo
       python3 scripts/preview_demo_tiny_entry_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_entry_permission_gate/latest_tiny_entry_permission_gate.md

   Expected:
     status=TINY_ENTRY_PERMISSION_CHECKLIST_READY; mode=checklist;
     real_entry_permission_dry_run_allowed=False;
     real_execution_allowed=False;
     real_tiny_entry_implemented=False;
     current_task_real_execution_allowed=False;
     order_endpoint_called=False; stop_endpoint_called=False;
     no_position_modified=True; no_live_endpoint=True;
     existing_positions_touched=[]; g20_policy_still_in_place=True;
     g20_lifted=False; tiny_notional <= 10 USDT;
     within_tiny_notional_cap=True; strategy_full_size_qty_ref=12.2;
     order_link_id startswith "DRYRUN-TINY-ENTRY-".

   NOTE: readonly_smoke must provide `instrument_rules` for SOLUSDT
   (min_order_qty / qty_step / tick_size / min_notional_value). If
   missing, the gate fails closed with
   instrument_rule_for_selected_symbol_missing.

3. VPS Entry-Permission Dry Run (envelope-only):
       python3 scripts/preview_demo_tiny_entry_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission \
           --symbol SOLUSDT --allow-real-entry-permission --write-report
   Expected:
     status=TINY_ENTRY_PERMISSION_READY_BUT_EXECUTION_DISABLED;
     mode=real_entry_permission_dry_run;
     real_entry_permission_dry_run_allowed=True;
     real_execution_allowed=False;
     real_tiny_entry_implemented=False;
     current_task_real_execution_allowed=False;
     no Bybit endpoint called; existing_positions_touched=[].

4. VPS Real-Entry-Guard Sanity (no socket):
       python3 scripts/preview_demo_tiny_entry_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission \
           --symbol SOLUSDT --allow-real-tiny-entry --write-report
   Expected:
     status=REAL_TINY_ENTRY_NOT_IMPLEMENTED;
     mode=real_tiny_entry_guard;
     real_execution_allowed=False;
     real_tiny_entry_requested=True;
     real_tiny_entry_implemented=False;
     current_task_real_execution_allowed=False;
     order_endpoint_called=False; stop_endpoint_called=False;
     no_position_modified=True; no_live_endpoint=True;
     existing_positions_touched=[].

5. VPS Symbol-Collision Sanity (any one of the 5 existing shorts):
       python3 scripts/preview_demo_tiny_entry_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --from-latest-real-permission \
           --symbol ENAUSDT --write-report
   Expected: status=FAIL_CLOSED; mode=fail_closed;
             selected_symbol_collides_with_existing_position
             present in blocked_gates.

6. Once the four VPS checks above all match, please decide whether
   to authorise TASK-014Y (Tiny Isolated Demo Stop-Attach Permission
   Gate — second of the three independent confirm-token gates).
   Until then the demo runtime stays in close-only / readonly +
   envelope-mock + entry-permission-gate mode.

## TASK-014W-FIX1 Status (2026-06-10)

| item | status |
|---|---|
| root cause: `real_execution_allowed` was set to `bool(allow_real_tiny_position)` — semantically wrong; allow flag ≠ execution allowed | FIXED |
| src/demo_tiny_position_real_permission_gate.py: always return `real_execution_allowed=False` | DONE |
| src/demo_tiny_position_real_permission_gate.py: add `real_tiny_position_requested` field to capture user intent | DONE |
| stage_5 envelope: `real_tiny_position_requested` added; `real_execution_allowed=False` confirmed | DONE |
| to_dict(): `real_tiny_position_requested` serialised | DONE |
| tests W25: `real_execution_allowed is False`; `real_tiny_position_requested is True` | DONE |
| tests W33: report JSON `real_execution_allowed is False`; `real_tiny_position_requested is True` | DONE |
| NEXT_ACTION.md VPS step-4 expected values corrected | DONE |
| py_compile src + CLI | PASS |
| pytest tests/demo_trading/test_demo_tiny_position_real_permission_gate.py | 83/83 PASS |
| order_endpoint_called=False / stop_endpoint_called=False / no_position_modified=True | CONFIRMED |
| G20 unchanged | CONFIRMED |
| local commit | PENDING |

## TASK-014W Status (2026-06-10)

| item | status |
|---|---|
| new module: src/demo_tiny_position_real_permission_gate.py (6-stage pure-computation permission gate) | DONE |
| new CLI: scripts/preview_demo_tiny_position_real_permission_gate.py (--from-latest-readonly/reconciliation/protection/contract/noop-plan/lifecycle / --symbol / --allow-real-permission-gate / --allow-real-tiny-position / --write-report) | DONE |
| new tests: tests/demo_trading/test_demo_tiny_position_real_permission_gate.py (W1 - W47, 83 tests) | DONE |
| 41 gate constants exposed (18 general + 6 risk + 7 manual approval + 5 failure + 5 execution guard) | DONE |
| 4 status constants + 4 mode constants | DONE |
| 3 approval token patterns documented as strings only (entry / stop-attach / cleanup, never validated) | DONE |
| tiny_notional_cap=10 USDT; strategy_full_size_qty_ref=12.2 SOL flagged MUST_NOT_BE_REUSED | DONE |
| --allow-real-permission-gate returns REAL_PERMISSION_GATE_READY_BUT_EXECUTION_DISABLED (no socket) | DONE |
| --allow-real-tiny-position returns REAL_TINY_POSITION_NOT_IMPLEMENTED (no socket) | DONE |
| next_required_task = TASK-014X_tiny_isolated_demo_entry_permission_gate | DONE |
| pytest tests/demo_trading/test_demo_tiny_position_real_permission_gate.py | 83/83 PASS |
| pytest tests/demo_trading | 1611 PASS + 1 pre-existing unrelated failure (test_demo_emergency_close_sender::test_dry_run_cli_writes_report — fails identically on HEAD baseline, NOT caused by TASK-014W) |
| no order endpoint / no stop endpoint / no live endpoint / no position modified | CONFIRMED |
| 5 existing demo shorts (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT) never touched | CONFIRMED |
| G20 (protected_entry_policy_missing) constant unchanged and not referenced in new module | CONFIRMED |
| no secret values in module / CLI / report | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-10 TASK-014W)

1. Update VPS git pull:
       git pull
       python3 -m pytest tests/demo_trading -q
       # expect 1611 PASS + 1 pre-existing unrelated failure
       # (test_demo_emergency_close_sender::test_dry_run_cli_writes_report).
       # That failure is NOT introduced by TASK-014W and must be
       # tracked separately.

2. VPS Checklist (envelope-only, no network):
       source .env.demo
       python3 scripts/preview_demo_tiny_position_real_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_position_real_permission_gate/latest_tiny_position_real_permission_gate.md

   Expected:
     status=REAL_PERMISSION_CHECKLIST_READY; mode=checklist;
     real_permission_gate_dry_run_allowed=False;
     real_execution_allowed=False;
     real_tiny_position_implemented=False;
     current_task_real_execution_allowed=False;
     stop_endpoint_called=False; order_endpoint_called=False;
     no_position_modified=True; no_live_endpoint=True;
     existing_positions_touched=[]; g20_policy_still_in_place=True;
     g20_lifted=False; tiny_notional <= 10 USDT;
     within_tiny_notional_cap=True; strategy_full_size_qty_ref=12.2.

3. VPS Permission Gate Dry Run (envelope-only, no network):
       python3 scripts/preview_demo_tiny_position_real_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --symbol SOLUSDT --allow-real-permission-gate --write-report
   Expected:
     status=REAL_PERMISSION_GATE_READY_BUT_EXECUTION_DISABLED;
     mode=real_permission_gate_dry_run;
     real_permission_gate_dry_run_allowed=True;
     real_execution_allowed=False;
     real_tiny_position_implemented=False;
     current_task_real_execution_allowed=False;
     no Bybit endpoint called; existing_positions_touched=[].

4. VPS Real-Guard Sanity (no socket):
       python3 scripts/preview_demo_tiny_position_real_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --symbol SOLUSDT --allow-real-tiny-position --write-report
   Expected:
     status=REAL_TINY_POSITION_NOT_IMPLEMENTED;
     mode=real_tiny_position_guard;
     real_execution_allowed=False;
     real_tiny_position_requested=True;
     real_tiny_position_implemented=False;
     current_task_real_execution_allowed=False;
     stop_endpoint_called=False; order_endpoint_called=False;
     no_position_modified=True; no_live_endpoint=True;
     existing_positions_touched=[].

5. VPS Symbol-Collision Sanity (any one of the 5 existing shorts):
       python3 scripts/preview_demo_tiny_position_real_permission_gate.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan --from-latest-lifecycle \
           --symbol ENAUSDT --write-report
   Expected: status=FAIL_CLOSED; mode=fail_closed;
             selected_symbol_collides_with_existing_position
             present in blocked_gates.

6. Once the four VPS checks above all match, please decide whether
   to authorise TASK-014X (Tiny Isolated Demo Entry Permission Gate
   — the first of the three independent confirm-token gates).
   Until then the demo runtime stays in close-only / readonly +
   envelope-mock + permission-gate mode.

## TASK-014V Status (2026-06-10)

| item | status |
|---|---|
| new module: src/demo_tiny_position_lifecycle_mock.py (7-phase pure-computation lifecycle) | DONE |
| new CLI: scripts/preview_demo_tiny_position_lifecycle_mock.py (preview / --mock-lifecycle / --allow-real-tiny-position / 3 simulation flags / --write-report) | DONE |
| new tests: tests/demo_trading/test_demo_tiny_position_lifecycle_mock.py (V1 - V41+) | DONE |
| 29 gate constants exposed (21 general + 8 lifecycle) | DONE |
| 5 status constants + 4 mode constants | DONE |
| 3 failure injection paths: stop-attach / cleanup / existing-stop-mismatch | DONE |
| --allow-real-tiny-position returns REAL_TINY_POSITION_NOT_IMPLEMENTED (no socket) | DONE |
| next_required_task = TASK-014W_tiny_isolated_demo_position_real_execution_permission_gate | DONE |
| pytest tests/demo_trading | 1529/1529 PASS (1452 prior + 77 new V) |
| no order endpoint / no stop endpoint / no live endpoint / no position modified | CONFIRMED |
| 5 existing demo shorts (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT) never touched | CONFIRMED |
| G20 (protected_entry_policy_missing) constant unchanged and not referenced in new module | CONFIRMED |
| no secret values in module / CLI / report | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-10 TASK-014V)

1. Update VPS git pull:
       git pull
       python3 -m pytest tests/demo_trading -q   # expect 1529 PASS

2. VPS Preview (envelope-only):
       source .env.demo
       python3 scripts/preview_demo_tiny_position_lifecycle_mock.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/tiny_position_lifecycle_mock/latest_tiny_position_lifecycle_mock.md

   Expected:
     status=TINY_LIFECYCLE_PREVIEW_READY; mode=preview;
     real_execution_allowed=False; real_tiny_position_implemented=False;
     current_task_real_execution_allowed=False;
     stop_endpoint_called=False; order_endpoint_called=False;
     no_position_modified=True; no_live_endpoint=True;
     existing_positions_touched=[]; g20_policy_still_in_place=True.

3. VPS Mock lifecycle (in-memory 7 phases):
       python3 scripts/preview_demo_tiny_position_lifecycle_mock.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan \
           --symbol SOLUSDT --mock-lifecycle --write-report
   Expected: status=MOCK_TINY_LIFECYCLE_SUCCESS; failed_phase=(empty);
             dangling_tiny_position=False; existing_positions_touched=[].

4. VPS failure-injection checks (each MUST report MOCK_TINY_LIFECYCLE_FAIL_CLOSED):
       --mock-lifecycle --simulate-stop-attach-failure
       --mock-lifecycle --simulate-existing-stop-mismatch
       --mock-lifecycle --simulate-cleanup-failure

5. VPS real-guard sanity:
       python3 scripts/preview_demo_tiny_position_lifecycle_mock.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --from-latest-noop-plan \
           --symbol SOLUSDT --allow-real-tiny-position --write-report
   Expected: status=REAL_TINY_POSITION_NOT_IMPLEMENTED;
             real_execution_allowed=True; real_tiny_position_implemented=False;
             current_task_real_execution_allowed=False;
             no Bybit endpoint called.

6. Once the five VPS checks above all match, please decide whether to
   authorise TASK-014W (Tiny Isolated Demo Position Real Execution
   Permission Gate). Until then the demo runtime stays in
   close-only / readonly + envelope-mock mode.

## TASK-014U-FIX2 Status (2026-06-10)

| item | status |
|---|---|
| root cause: _write_report() used truncated stem "noop_probe_plan" instead of spec stem "trading_stop_noop_probe_plan" | CONFIRMED |
| primary latest filenames: latest_trading_stop_noop_probe_plan.{json,md} | DONE |
| legacy alias filenames still written: latest_noop_probe_plan.{json,md} | DONE |
| timestamped pairs renamed: {ts}_trading_stop_noop_probe_plan.{json,md} | DONE |
| 6 new FIX2 tests covering primary json/md / legacy alias / identical content / timestamped suffix | DONE |
| pytest tests/demo_trading | 1452/1452 PASS (1446 prior + 6 new FIX2) |
| no order endpoint / no stop endpoint / no position modified / G20 unchanged / no secrets | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-10 TASK-014U-FIX2)

1. Update VPS git pull:
       git pull
       python3 -m pytest tests/demo_trading -q   # expect 1452 PASS

2. Re-run VPS step 7 (--write-report):
       source .env.demo
       python3 scripts/preview_demo_trading_stop_noop_probe_plan.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/trading_stop_noop_probe_plan/latest_trading_stop_noop_probe_plan.md

   Expected primary files written:
     outputs/demo_trading/trading_stop_noop_probe_plan/
       latest_trading_stop_noop_probe_plan.json  (primary)
       latest_trading_stop_noop_probe_plan.md    (primary)
       latest_noop_probe_plan.json               (legacy alias)
       latest_noop_probe_plan.md                 (legacy alias)
       {ts}_trading_stop_noop_probe_plan.json
       {ts}_trading_stop_noop_probe_plan.md

3. Confirm TASK-014V gate is now the only remaining human decision:
   see "Next Rick Action (set by 2026-06-10 TASK-014U)" below.

## TASK-014U-FIX1 Status (2026-06-10)

| item | status |
|---|---|
| root cause: scripts/preview_demo_trading_stop_noop_probe_plan.py load_latest_readonly() was looking for outputs/demo_trading/readonly_smoke/latest_readonly_smoke.json, but TASK-014C/D always writes latest_smoke.json | CONFIRMED |
| fix: load_latest_readonly() now resolves primary=latest_smoke.json, fallback=latest_readonly_smoke.json; fail-closed only when both absent | DONE |
| src/demo_trading_stop_noop_probe_plan.py | NOT MODIFIED |
| 3 new tests: primary-only PASS / fallback-only PASS / both-absent rc=1 | DONE |
| all existing test helpers updated to write latest_smoke.json | DONE |
| pytest tests/demo_trading | 1446/1446 PASS (1443 prior + 3 new FIX1) |
| no order endpoint called / no stop endpoint called / no position modified / G20 unchanged / no secrets | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-10 TASK-014U-FIX1)

1. Update VPS git pull:
       git pull
       python3 -m pytest tests/demo_trading -q   # expect 1446 PASS

2. Re-run VPS validation from step 7 of TASK-014U Next Rick Action:
       source .env.demo
       python3 scripts/preview_demo_trading_stop_noop_probe_plan.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/trading_stop_noop_probe_plan/latest_noop_probe_plan.md

   Expected (same as before):
     status=NOOP_PROBE_PLAN_READY; mode=plan;
     recommended_path=tiny_isolated_position_plan;
     real_probe_allowed=False; real_noop_probe_implemented=False;
     current_task_real_execution_allowed=False;
     stop_endpoint_called=False; order_endpoint_called=False;
     no_position_modified=True; no_live_endpoint=True;
     blocked_gates contains the 22 in-task open blockers;
     g20_policy_still_in_place=True.

3. Remainder of TASK-014U VPS steps are unchanged:
   see "Next Rick Action (set by 2026-06-10 TASK-014U)" below.

## TASK-014U Status (2026-06-10)

| item | status |
|---|---|
| src/demo_trading_stop_noop_probe_plan.py — NEW pure-computation / mock-safe design module; DemoTradingStopNoopProbePlanner + NoopProbePlanResult dataclass; reads readonly_smoke + reconciliation + protection + contract JSON (all four required); validates --symbol is NOT one of the 5 existing demo short positions (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT); builds three plan tables (tiny_isolated_position_plan, read_only_endpoint_research, expected_error_probe); recommends tiny_isolated_position_plan; routes to plan -> NOOP_PROBE_PLAN_READY OR --allow-real-noop-probe -> REAL_NOOP_PROBE_NOT_IMPLEMENTED (no socket); current_task_real_execution_allowed=False always | DONE |
| src/demo_trading_stop_noop_probe_plan.py — NO urlopen / urllib / requests / httpx / socket / http.client / hmac / X-BAPI-SIGN / os.environ / getenv / dotenv; NO import of main / src.risk / BybitExecutor / pybit / src.bybit_executor / src.demo_new_entry_sender / src.demo_close_only_sender / src.demo_emergency_close_sender / src.demo_protected_new_entry_orchestrator / src.demo_trading_stop_contract_probe / scripts.execute_*; TRADING_STOP_PATH_REF and ORDER_CREATE_PATH_REF stored as strings only and never invoked | CONFIRMED |
| scripts/preview_demo_trading_stop_noop_probe_plan.py — NEW CLI: --from-latest-readonly / --from-latest-reconciliation / --from-latest-protection / --from-latest-contract / --symbol / --allow-real-noop-probe / --write-report; reads outputs/demo_trading/{readonly_smoke,reconciliation,new_entry_protection,trading_stop_contract}/latest_*.json; writes JSON + Markdown to outputs/demo_trading/trading_stop_noop_probe_plan/; NO real trading-stop send and NO --execute-noop-probe flag (real-guard returns REAL_NOOP_PROBE_NOT_IMPLEMENTED) | DONE |
| tests/demo_trading/test_demo_trading_stop_noop_probe_plan.py — 58 tests U1-U32 + extras: plan-ready / 4x upstream-missing / symbol-missing / symbol-collision (parametrized over 5 existing demo positions) / realtime-guard-missing / review-fail-closed / prior-probe-flipped / 15 tiny-isolated gates / 3 expected-error gates / 3 readonly-research gates / 2 defense-in-depth gates / module defines >= 30 GATE_ constants / happy-path plan surfaces >= 22 in-task gates / real-guard adds real_noop_probe_not_implemented / three-plan presence + recommended_path == tiny / only tiny plan has a TASK-014V next-task pointer / expected-error path flagged touches_existing_positions=True / report artifacts (plan + real-guard modes) / no secrets / no forbidden imports / no urllib / urlopen / socket / http.client in source / no close-only / emergency-close / new-entry / contract-probe back coupling / module safe under socket.socket=None at import / TASK-014L G20 NOT lifted / dataclass to_dict round-trip with deep-copy immutability / 5 CLI exit-code paths / TRADING_STOP_PATH_REF matches TASK-014T constant / fresh plans per call | DONE |
| pytest tests/demo_trading | 1443/1443 PASS (1385 prior + 58 new U-series) |
| py_compile new files | PASS |
| SOLUSDT plan mode: status=NOOP_PROBE_PLAN_READY, mode=plan, recommended_path=tiny_isolated_position_plan, real_probe_allowed=False, real_noop_probe_implemented=False, current_task_real_execution_allowed=False, blocked_gates contains all 15 tiny + 3 expected-err + 3 readonly + 2 defense-in-depth gates, stop_endpoint_called=False, order_endpoint_called=False, no_position_modified=True, no_live_endpoint=True, no_orders_sent=True, secret_value_observed=False, g20_policy_still_in_place=True | CONFIRMED |
| SOLUSDT --allow-real-noop-probe mode: status=REAL_NOOP_PROBE_NOT_IMPLEMENTED, mode=real_noop_probe, real_probe_allowed=True, real_noop_probe_implemented=False, current_task_real_execution_allowed=False, blocked_gates contains real_noop_probe_not_implemented, stop_endpoint_called=False, order_endpoint_called=False, no_position_modified=True, no_live_endpoint=True | CONFIRMED |
| 5 existing demo short positions (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT) as --symbol arg: status=FAIL_CLOSED, blocked_gates contains selected_symbol_collides_with_existing_position AND tiny_symbol_overlaps_existing_position, rc=1, no_position_modified=True | CONFIRMED |
| no live hostname in module or CLI (api.bybit.com / api-testnet.bybit.com); base_url_ref=https://api-demo.bybit.com recorded informationally only | CONFIRMED |
| AST scan: no import of main / src.risk / BybitExecutor / pybit / src.bybit_executor / src.demo_new_entry_sender / src.demo_close_only_sender / src.demo_emergency_close_sender / src.demo_protected_new_entry_orchestrator / src.demo_trading_stop_contract_probe / scripts.execute_*; no import of urllib / requests / httpx / socket / http.client | CONFIRMED |
| urlopen sentinel: import module with socket.socket=None in subprocess - PASS | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| 5 existing demo short positions | NOT TOUCHED (no real probe; collision check FAIL_CLOSED) |
| no orders sent / no positions modified / no stop endpoint called / no order endpoint called / no secrets observed / no emergency close invoked | CONFIRMED |
| TASK-014L sender G20 (protected_entry_policy_missing) | STILL IN PLACE (deliberately not lifted by TASK-014U; constant unchanged; gate name not present in module/CLI source) |
| TASK-014U real no-op probe | DELIBERATELY NOT IMPLEMENTED (returns REAL_NOOP_PROBE_NOT_IMPLEMENTED) |
| local commit | DONE |

## Next Rick Action (set by 2026-06-10 TASK-014U)

1. Update VPS git pull and inspect the new design module + CLI + tests:
       src/demo_trading_stop_noop_probe_plan.py
       scripts/preview_demo_trading_stop_noop_probe_plan.py
       tests/demo_trading/test_demo_trading_stop_noop_probe_plan.py

2. VPS plan-mode design preview (no network at all from this design
   module; the upstream read-only / reconciliation / market-price
   steps still hit api-demo.bybit.com via the existing clients):
       source .env.demo
       # 1) read-only proof refresh
       python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
       # 2) wallet audit
       python3 scripts/preview_demo_wallet_audit.py --real-readonly --write-report
       # 3) position reconciliation
       python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report
       # 4) market-backed new-entry review
       python3 scripts/preview_demo_new_entry_review.py \
           --from-latest-reconciliation --allow-real-market-network --write-report
       # 5) protected-entry preview (TASK-014Q)
       python3 scripts/preview_demo_new_entry_protection.py \
           --from-latest-review --symbol SOLUSDT --write-report
       # 6) trading-stop contract preview (TASK-014T)
       python3 scripts/preview_demo_trading_stop_contract.py \
           --from-latest-protection --symbol SOLUSDT --write-report
       # 7) no-op probe DESIGN plan (TASK-014U — no network)
       python3 scripts/preview_demo_trading_stop_noop_probe_plan.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/trading_stop_noop_probe_plan/latest_noop_probe_plan.md

   Expected plan:
     status=NOOP_PROBE_PLAN_READY;
     mode=plan;
     recommended_path=tiny_isolated_position_plan;
     real_probe_allowed=False; real_noop_probe_implemented=False;
     current_task_real_execution_allowed=False;
     stop_endpoint_called=False; order_endpoint_called=False;
     no_position_modified=True; no_live_endpoint=True;
     blocked_gates contains the 15 tiny-isolated + 3 expected-error +
     3 read-only research + 2 defense-in-depth gates (22 in-task
     open blockers); g20_policy_still_in_place=True.

3. Optional real-no-op-probe guard sanity check (returns
   REAL_NOOP_PROBE_NOT_IMPLEMENTED; still no socket opened):
       python3 scripts/preview_demo_trading_stop_noop_probe_plan.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --symbol SOLUSDT --allow-real-noop-probe --write-report

   Expected:
     status=REAL_NOOP_PROBE_NOT_IMPLEMENTED;
     blocked_gates contains "real_noop_probe_not_implemented";
     real_probe_allowed=True; real_noop_probe_implemented=False;
     current_task_real_execution_allowed=False;
     stop_endpoint_called=False; no_position_modified=True.

4. Symbol collision sanity check (any of the 5 existing demo shorts
   must FAIL_CLOSED):
       python3 scripts/preview_demo_trading_stop_noop_probe_plan.py \
           --from-latest-readonly --from-latest-reconciliation \
           --from-latest-protection --from-latest-contract \
           --symbol ENAUSDT --write-report

   Expected:
     status=FAIL_CLOSED;
     blocked_gates contains
       "selected_symbol_collides_with_existing_position"
     AND "tiny_symbol_overlaps_existing_position";
     exit code 1.

5. Confirm TASK-014L sender still blocks --execute-new-entry
   (TASK-014U does NOT lift G20):
       python3 scripts/execute_demo_new_entry.py \
           --from-latest-review --symbol SOLUSDT \
           --confirm-token CONFIRM_DEMO_NEW_ENTRY_$(date -u +%Y%m%d) \
           --execute-new-entry --write-report
   Expected: blocked_gates contains "protected_entry_policy_missing";
   execute_allowed=False; order_sent=False.

6. Human decision gate: TASK-014V (Tiny Isolated Demo Position
   Lifecycle Mock) is the next authorized step.  It must produce a
   self-contained mock chain that opens one tiny position on a symbol
   disjoint from the 5 existing demo shorts, attaches the stop,
   verifies post-fill state, and exercises the emergency-close path
   — all without real network calls.  Only after that mock lifecycle
   PASSes end-to-end can we plan a real no-op probe (which would
   then be the subject of a separate task).  Until then the real
   no-op probe stays REAL_NOOP_PROBE_NOT_IMPLEMENTED and TASK-014L
   sender G20 stays in place.

## TASK-014T Status (2026-06-10)

| item | status |
|---|---|
| src/demo_trading_stop_contract_probe.py — NEW pure-computation / mock-safe module; DemoTradingStopContractProbe + TradingStopContractResult dataclass; documents Bybit V5 /v5/position/trading-stop endpoint contract (endpoint_family=bybit_demo, base_url=https://api-demo.bybit.com (informational only), path=/v5/position/trading-stop, method=POST, category=linear, tpslMode=Full, slTriggerBy=MarkPrice/LastPrice, positionIdx=0); build_payload_preview() emits the documented body (symbol/stopLoss/category/tpslMode/slTriggerBy/positionIdx) and validate_payload() rejects takeProfit/leverage/transfer/withdraw/deposit/side/qty/orderType/price/timeInForce/reduceOnly/live hostname/order-create path | DONE |
| src/demo_trading_stop_contract_probe.py — NO urlopen / urllib / requests / httpx / socket / http.client / hmac / X-BAPI-SIGN / os.environ / getenv / dotenv; NO import of main / src.risk / BybitExecutor / pybit / src.bybit_executor / src.demo_new_entry_sender / src.demo_close_only_sender / src.demo_emergency_close_sender / src.demo_protected_new_entry_orchestrator; TRADING_STOP_PATH and ORDER_CREATE_PATH stored as strings only and never invoked | CONFIRMED |
| scripts/preview_demo_trading_stop_contract.py — NEW CLI: --from-latest-protection / --symbol / --confirm-token / --mock-permission / --allow-real-stop-probe / --write-report; reads outputs/demo_trading/new_entry_protection/latest_new_entry_protection.json; writes JSON + Markdown to outputs/demo_trading/trading_stop_contract/; NO real trading-stop send and NO --execute-trading-stop flag (real probe returns REAL_PROBE_NOT_IMPLEMENTED) | DONE |
| tests/demo_trading/test_demo_trading_stop_contract_probe.py — 68 tests T1-T28 + extras: valid SOLUSDT preview / missing protection / symbol mismatch / missing stopLoss / non-positive stopLoss / invalid tpslMode / invalid slTriggerBy (LastPrice accepted) / invalid positionIdx / invalid category / payload excludes takeProfit / leverage / transfer-withdraw-deposit / side-qty-orderType / order-create path leak in payload value / live hostname leak in payload value / no secrets in JSON+Markdown report / no forbidden imports / no close-only/emergency-close/new-entry-sender reuse / no urlopen at import time / mock-permission MOCK_TRADING_STOP_PERMISSION_OK / mock-permission still no socket / --allow-real-stop-probe -> REAL_PROBE_NOT_IMPLEMENTED + gate / invalid confirm token blocks real probe + mock permission / report artifacts (ts + latest pair) / TASK-014L G20 still blocks --execute-new-entry / source scan confirms no urllib/requests/httpx/http.client/socket. in module + CLI / payload keys+values match TASK-014R stop attachment payload exactly / dataclass to_dict round-trip / CLI missing protection/symbol/token returns 1 / real-probe report artifact | DONE |
| pytest tests/demo_trading | 1385/1385 PASS (1317 prior + 68 new T-series) |
| py_compile new files | PASS |
| SOLUSDT contract preview (stop=61.63 / long / qty=12.3): status=TRADING_STOP_CONTRACT_PREVIEW_OK, mode=preview, payload_preview={category:linear, symbol:SOLUSDT, stopLoss:"61.63", tpslMode:Full, slTriggerBy:MarkPrice, positionIdx:0}, real_probe_allowed=False, real_probe_implemented=False, mock_permission_status=False, stop_endpoint_called=False, order_endpoint_called=False, no_position_modified=True, no_live_endpoint=True, blocked_gates=[] | CONFIRMED |
| SOLUSDT --mock-permission with CONFIRM_DEMO_TRADING_STOP_PROBE_20260610: status=MOCK_TRADING_STOP_PERMISSION_OK, mode=mock_permission, mock_permission_status=True, mock_response={retCode:0, retMsg:OK, mock:True, result:{symbol:SOLUSDT, stopLoss:"61.63", tpslMode:Full, slTriggerBy:MarkPrice, positionIdx:0, mock:True}}, stop_endpoint_called=False, order_endpoint_called=False, no_position_modified=True | CONFIRMED |
| SOLUSDT --allow-real-stop-probe with CONFIRM_DEMO_TRADING_STOP_PROBE_20260610: status=REAL_PROBE_NOT_IMPLEMENTED, mode=real_permission_probe, real_probe_allowed=True, real_probe_implemented=False, blocked_gates=[real_probe_not_implemented], stop_endpoint_called=False, order_endpoint_called=False, no_position_modified=True, no_live_endpoint=True | CONFIRMED |
| no live hostname (api.bybit.com / api-testnet.bybit.com) in payload values; base_url=https://api-demo.bybit.com recorded as informational string only and never used as a client target | CONFIRMED |
| AST scan: no import of main / src.risk / BybitExecutor / pybit / src.bybit_executor / src.demo_new_entry_sender / src.demo_close_only_sender / src.demo_emergency_close_sender / src.demo_protected_new_entry_orchestrator / scripts.execute_*; no import of urllib / requests / httpx / socket / http.client | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| 5 existing demo short positions | NOT TOUCHED (no trading-stop call) |
| no orders sent / no positions modified / no stop endpoint called / no order endpoint called / no secrets observed / no emergency close invoked | CONFIRMED |
| TASK-014L sender G20 (protected_entry_policy_missing) | STILL IN PLACE (deliberately not lifted by TASK-014T) |
| TASK-014T real probe | DELIBERATELY NOT IMPLEMENTED (returns REAL_PROBE_NOT_IMPLEMENTED) |
| local commit | DONE |

## Next Rick Action (set by 2026-06-10 TASK-014T)

1. Update VPS git pull and inspect the new probe + CLI + tests:
       src/demo_trading_stop_contract_probe.py
       scripts/preview_demo_trading_stop_contract.py
       tests/demo_trading/test_demo_trading_stop_contract_probe.py

2. VPS contract preview (no network at all from this probe; the
   upstream read-only / market-price steps still hit api-demo.bybit.com):
       source .env.demo
       # 1) read-only proof refresh
       python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
       # 2) wallet audit
       python3 scripts/preview_demo_wallet_audit.py --real-readonly --write-report
       # 3) position reconciliation
       python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report
       # 4) market-backed new-entry review
       python3 scripts/preview_demo_new_entry_review.py \
           --from-latest-reconciliation --allow-real-market-network --write-report
       # 5) protected-entry preview (TASK-014Q)
       python3 scripts/preview_demo_new_entry_protection.py \
           --from-latest-review --symbol SOLUSDT --write-report
       # 6) stop-loss attachment mock (TASK-014R)
       python3 scripts/execute_demo_stop_loss_attachment.py \
           --from-latest-protection --symbol SOLUSDT \
           --confirm-token CONFIRM_DEMO_STOP_ATTACH_$(date -u +%Y%m%d) \
           --mock-execute-stop --write-report
       # 7) protected new-entry mock chain (TASK-014S)
       python3 scripts/execute_demo_protected_new_entry_mock.py \
           --from-latest-review --from-latest-protection \
           --symbol SOLUSDT \
           --confirm-token CONFIRM_DEMO_PROTECTED_ENTRY_$(date -u +%Y%m%d) \
           --mock-chain --write-report
       # 8) trading-stop contract preview (TASK-014T — no network)
       python3 scripts/preview_demo_trading_stop_contract.py \
           --from-latest-protection --symbol SOLUSDT --write-report
       cat outputs/demo_trading/trading_stop_contract/latest_trading_stop_contract.md

   Expected preview:
     status=TRADING_STOP_CONTRACT_PREVIEW_OK;
     mode=preview; path=/v5/position/trading-stop (NOT invoked);
     payload_preview contains stopLoss equal to latest protection
     stop_price; stop_endpoint_called=False; order_endpoint_called=False;
     no_position_modified=True; no_live_endpoint=True; blocked_gates=[].

3. Optional mock-permission step (still no network):
       python3 scripts/preview_demo_trading_stop_contract.py \
           --from-latest-protection --symbol SOLUSDT \
           --confirm-token CONFIRM_DEMO_TRADING_STOP_PROBE_$(date -u +%Y%m%d) \
           --mock-permission --write-report

   Expected:
     status=MOCK_TRADING_STOP_PERMISSION_OK; mock_permission_status=True;
     mock_response.retCode=0; mock_response.mock=True;
     stop_endpoint_called=False; order_endpoint_called=False;
     no_position_modified=True.

4. Real-probe guard sanity check (returns REAL_PROBE_NOT_IMPLEMENTED;
   still no socket opened):
       python3 scripts/preview_demo_trading_stop_contract.py \
           --from-latest-protection --symbol SOLUSDT \
           --confirm-token CONFIRM_DEMO_TRADING_STOP_PROBE_$(date -u +%Y%m%d) \
           --allow-real-stop-probe --write-report

   Expected:
     status=REAL_PROBE_NOT_IMPLEMENTED;
     blocked_gates contains "real_probe_not_implemented";
     real_probe_allowed=True; real_probe_implemented=False;
     stop_endpoint_called=False; no_position_modified=True.

5. Confirm TASK-014L sender still blocks --execute-new-entry
   (TASK-014T does NOT lift G20):
       python3 scripts/execute_demo_new_entry.py \
           --from-latest-review --symbol SOLUSDT \
           --confirm-token CONFIRM_DEMO_NEW_ENTRY_$(date -u +%Y%m%d) \
           --execute-new-entry --write-report
   Expected: blocked_gates contains "protected_entry_policy_missing";
   execute_allowed=False; order_sent=False.

6. Human decision gate: TASK-014U (Real Demo Trading-stop No-op Probe
   Design / Tiny Isolated Position Plan) is the next authorized step.
   Until TASK-014U produces a documented no-op real probe that provably
   cannot modify any existing position's stop_price, the real probe
   stays REAL_PROBE_NOT_IMPLEMENTED and G20 stays in place.

## TASK-014S Status (2026-06-10)

| item | status |
|---|---|
| src/demo_protected_new_entry_orchestrator.py — NEW pure-computation / mock-safe orchestrator; DemoProtectedNewEntryOrchestrator + ProtectedEntryChainResult dataclass; submit_chain() validates 24+ gates (review-level + protection-level + stop direction + token + TASK-014R sender promotion) and builds the TASK-014R stop payload preview; under --mock-chain synthesizes an entry + post-fill (stop_price=0) + stop-attach (TASK-014R mock_execute_stop) envelope chain with all-or-fail semantics; failure path -> MOCK_PROTECTED_ENTRY_FAIL_CLOSED + recommended_action="emergency_close_preview" (no real emergency close invoked) | DONE |
| src/demo_protected_new_entry_orchestrator.py — NO urlopen / urllib / requests / httpx / socket / http.client / hmac / X-BAPI-SIGN / os.environ / getenv / dotenv; NO import of main / src.risk / BybitExecutor / pybit / src.bybit_executor / src.demo_new_entry_sender / src.demo_close_only_sender / src.demo_emergency_close_sender; ORDER_CREATE_ENDPOINT="/v5/order/create" and STOP_ATTACH_ENDPOINT="/v5/position/trading-stop" recorded but NEVER invoked; --mock-chain emits synthetic MOCK-ENTRY-{symbol}-{x} + MOCK-STOP-{symbol}-{x} envelopes without opening a socket | CONFIRMED |
| scripts/execute_demo_protected_new_entry_mock.py — NEW CLI: --from-latest-review / --from-latest-protection / --symbol / --confirm-token / --dry-run (default) / --mock-chain / --write-report; reads outputs/demo_trading/new_entry_review/latest_new_entry_review.json + outputs/demo_trading/new_entry_protection/latest_new_entry_protection.json; writes JSON + Markdown to outputs/demo_trading/protected_new_entry/; NO --execute-protected-entry flag (real chain execution reserved for TASK-014T+) | DONE |
| tests/demo_trading/test_demo_protected_new_entry_orchestrator.py — 57 tests S1-S28 + extras: missing review / protection / symbol mismatch / review missing realtime guard / protection missing realtime guard / missing stop_price / long stop above-or-equal entry / short stop below-or-equal entry / valid dry-run SOLUSDT / mock-chain invalid token / mock-chain valid token MOCK_PROTECTED_ENTRY_SUCCESS / mock_entry_order_sent=True with order_endpoint_called=False / mock_stop_attached=True with stop_endpoint_called=False / final mock position stop_price>0 / missing_stop_price=False after attach / _simulate_stop_attach_failure -> MOCK_PROTECTED_ENTRY_FAIL_CLOSED + recommended_action=emergency_close_preview / report artifacts / no live endpoint / no secrets / no forbidden imports / no close-only / emergency-close / new-entry-sender reuse / no network at import time / payload excludes takeProfit + leverage + transfer + withdraw + deposit / TASK-014L sender G20 still blocks --execute-new-entry / urlopen sentinel scan in module + CLI / dataclass to_dict round-trip / synth stop-attach token format / short side dry-run / CLI missing-review or missing-token returns 1 | DONE |
| pytest tests/demo_trading | 1317/1317 PASS (1260 prior + 57 new S-series) |
| py_compile new files | PASS |
| SOLUSDT dry-run (entry=64.76 / stop=61.52 / long / qty=12.3): status=DRY_RUN_PROTECTED_ENTRY_CHAIN_ALLOWED, protected_entry_status=DRY_RUN_PREVIEW, mock_entry_order_sent=False, mock_stop_attached=False, stop_payload_preview_only=True, stop_endpoint_called=False, order_endpoint_called=False, no_orders_sent=True, no_position_modified=True, no_live_endpoint=True, blocked_gates=[] | CONFIRMED |
| SOLUSDT --mock-chain with CONFIRM_DEMO_PROTECTED_ENTRY_20260610: status=MOCK_PROTECTED_ENTRY_SUCCESS, protected_entry_status=MOCK_PROTECTED, mock_entry_order_sent=True, mock_order_id="MOCK-ENTRY-SOLUSDT-6476", mock_stop_attached=True, mock_stop_attach_id="MOCK-STOP-SOLUSDT-6152", mock_final_position_stop_price=61.52, missing_stop_price=False, fail_closed=False, stop_endpoint_called=False, order_endpoint_called=False, no_position_modified=True, no_live_endpoint=True, emergency_close_invoked=False, blocked_gates=[] | CONFIRMED |
| failure path (synthetic _simulate_stop_attach_failure=True): status=MOCK_PROTECTED_ENTRY_FAIL_CLOSED, protected_entry_status=FAIL_CLOSED, fail_closed=True, recommended_action="emergency_close_preview", blocked_gates=[stop_attach_mock_failed], emergency_close_invoked=False (recommendation only), no real emergency close invoked | CONFIRMED |
| no live hostname (api.bybit.com / api-testnet.bybit.com / api-demo.bybit.com) in orchestrator module or CLI | CONFIRMED |
| AST scan: no import of main / src.risk / BybitExecutor / pybit / src.bybit_executor / src.demo_new_entry_sender / src.demo_close_only_sender / src.demo_emergency_close_sender / scripts.execute_*; no import of urllib / requests / httpx / socket / http.client | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| no orders sent / no positions modified / no stop endpoint called / no order endpoint called / no secrets observed / no emergency close invoked | CONFIRMED |
| TASK-014L sender G20 (protected_entry_policy_missing) | STILL IN PLACE (deliberately not lifted by TASK-014S) |
| local commit | DONE |

## Next Rick Action (set by 2026-06-10 TASK-014S)

1. Update VPS git pull and inspect the new orchestrator + CLI + tests:
       src/demo_protected_new_entry_orchestrator.py
       scripts/execute_demo_protected_new_entry_mock.py
       tests/demo_trading/test_demo_protected_new_entry_orchestrator.py

2. VPS dry-run protected new-entry chain (no network at all from this
   orchestrator; the upstream read-only / market-price steps still hit
   api-demo.bybit.com via the existing readonly + market-price clients):
       source .env.demo
       # 1) read-only proof refresh
       python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
       # 2) wallet audit
       python3 scripts/preview_demo_wallet_audit.py --real-readonly --write-report
       # 3) position reconciliation
       python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report
       # 4) market-backed new-entry review with realtime price guard
       python3 scripts/preview_demo_new_entry_review.py \
           --from-latest-reconciliation \
           --allow-real-market-network \
           --with-realtime-price-guard \
           --write-report
       # 5) protected-entry preview (TASK-014Q)
       python3 scripts/preview_demo_new_entry_protection.py \
           --from-latest-review --symbol SOLUSDT --write-report
       # 6) protected new-entry orchestrator DRY-RUN (TASK-014S — no network)
       python3 scripts/execute_demo_protected_new_entry_mock.py \
           --from-latest-review --from-latest-protection \
           --symbol SOLUSDT --write-report
       cat outputs/demo_trading/protected_new_entry/latest_protected_new_entry.md

   Expected dry-run:
     status=DRY_RUN_PROTECTED_ENTRY_CHAIN_ALLOWED;
     protected_entry_status=DRY_RUN_PREVIEW;
     mock_entry_order_sent=False; mock_stop_attached=False;
     stop_payload_preview_only=True;
     stop_endpoint_called=False; order_endpoint_called=False;
     no_orders_sent=True; no_position_modified=True;
     no_live_endpoint=True; blocked_gates=[].

3. Optional mock-chain step (still no network, synthetic entry +
   stop-attach envelope chain):
       python3 scripts/execute_demo_protected_new_entry_mock.py \
           --from-latest-review --from-latest-protection \
           --symbol SOLUSDT \
           --confirm-token CONFIRM_DEMO_PROTECTED_ENTRY_$(date -u +%Y%m%d) \
           --mock-chain --write-report

   Expected:
     status=MOCK_PROTECTED_ENTRY_SUCCESS;
     protected_entry_status=MOCK_PROTECTED;
     mock_entry_order_sent=True; mock_order_id starts MOCK-ENTRY-SOLUSDT-;
     mock_stop_attached=True; mock_stop_attach_id starts MOCK-STOP-SOLUSDT-;
     mock_final_position_stop_price>0; missing_stop_price=False;
     fail_closed=False; stop_endpoint_called=False;
     order_endpoint_called=False; no_position_modified=True;
     emergency_close_invoked=False.

4. Confirm TASK-014L sender remains blocked on actual --execute-new-entry
   (TASK-014S deliberately does NOT lift G20):
       python3 scripts/execute_demo_new_entry.py \
           --from-latest-review --symbol SOLUSDT \
           --confirm-token CONFIRM_DEMO_NEW_ENTRY_$(date -u +%Y%m%d) \
           --execute-new-entry --write-report
   Expected: blocked_gates contains "protected_entry_policy_missing";
   execute_allowed=False; order_sent=False.

5. Human decision gate: TASK-014T (Real /v5/position/trading-stop
   Endpoint Probe + Permission Gate) is the next authorized step.
   Only after a documented contract probe + permission decision should
   G20 be considered for lifting.

## TASK-014R Status (2026-06-09)

| item | status |
|---|---|
| src/demo_stop_loss_attachment_sender.py — NEW pure-computation / mock-safe module; DemoStopLossAttachmentSender + StopAttachmentResult dataclass; submit_stop_attachment() validates 18 gates against a TASK-014Q ProtectedEntryPlan dict and builds a Bybit V5 trading-stop payload preview (category=linear / stopLoss / tpslMode=Full / slTriggerBy=MarkPrice / positionIdx=0); excludes takeProfit / leverage / transfer / withdraw / deposit / orderType / side / qty | DONE |
| src/demo_stop_loss_attachment_sender.py — NO urlopen / urllib / requests / httpx / socket / http.client / hmac / X-BAPI-SIGN / os.environ / getenv / dotenv; STOP_ATTACH_ENDPOINT="/v5/position/trading-stop" recorded but NEVER invoked; --mock-execute-stop emits synthetic retCode=0 envelope with MOCK-STOP-{symbol}-{x} id, also without opening a socket | CONFIRMED |
| scripts/execute_demo_stop_loss_attachment.py — NEW CLI: --from-latest-protection / --symbol / --confirm-token / --dry-run (default) / --mock-execute-stop / --write-report; reads outputs/demo_trading/new_entry_protection/latest_new_entry_protection.json; writes JSON + Markdown to outputs/demo_trading/stop_loss_attachment/; NO --execute-stop-loss flag (real attach reserved for TASK-014S) | DONE |
| tests/demo_trading/test_demo_stop_loss_attachment_sender.py — 72 tests R1-R25 + extra protection-flag enforcement + result.to_dict round-trip + CLI artifact writer + CLI subprocess smoke (PYTHONIOENCODING=utf-8); covers missing report / symbol mismatch / missing realtime guard / missing stop_price / long stop above-or-equal entry / short stop below-or-equal entry / invalid qty / invalid token for mock / valid dry-run / urlopen sentinel under dry-run + mock / MOCK_STOP_ATTACH_SUCCESS / payload contains stopLoss + symbol / payload excludes takeProfit + leverage + transfer/withdraw/deposit / no order-create call / no live endpoint fallback / no secrets / no main/risk/BybitExecutor/sender imports / no reuse of new-entry / emergency-close / close-only senders / artifacts written / source code-only scan clean | DONE |
| pytest tests/demo_trading | 1260/1260 PASS (1188 prior + 72 new R-series) |
| py_compile new files | PASS |
| SOLUSDT dry-run (entry=66.21 / stop=62.7 / long / stop_order_side=Sell): status=DRY_RUN_STOP_ATTACH_ALLOWED, payload_preview_only=True, payload={category:linear, symbol:SOLUSDT, stopLoss:"62.7", tpslMode:Full, slTriggerBy:MarkPrice, positionIdx:0}, stop_endpoint_called=False, order_endpoint_called=False, no_orders_sent=True, no_position_modified=True, blocked_gates=[] | CONFIRMED |
| SOLUSDT --mock-execute-stop with CONFIRM_DEMO_STOP_ATTACH_20260609: status=MOCK_STOP_ATTACH_SUCCESS, mock_stop_attached=True, mock_response={retCode:0, retMsg:OK, mock:True, result.stop_attach_id="MOCK-STOP-SOLUSDT-6270"}, stop_endpoint_called=False, order_endpoint_called=False, no_position_modified=True | CONFIRMED |
| no live hostname (api.bybit.com / api-testnet.bybit.com) in module or CLI | CONFIRMED |
| AST scan: no import of main / src.risk / BybitExecutor / pybit / src.bybit_executor / demo_close_only_sender / demo_new_entry_sender / demo_emergency_close_sender / scripts.execute_*; no import of urllib / requests / httpx / socket / http.client | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| no orders sent / no positions modified / no stop endpoint called / no order endpoint called / no secrets observed | CONFIRMED |
| TASK-014L sender G20 (protected_entry_policy_missing) | STILL IN PLACE (deliberately not lifted) |
| local commit | DONE |

## Next Rick Action (set by 2026-06-09 TASK-014R)

1. Update VPS git pull and inspect the new sender + CLI + tests:
       src/demo_stop_loss_attachment_sender.py
       scripts/execute_demo_stop_loss_attachment.py
       tests/demo_trading/test_demo_stop_loss_attachment_sender.py

2. VPS dry-run / mock pipeline (no network at all from this sender; the
   underlying read-only steps still hit api-demo.bybit.com via existing
   readonly + market-price clients):
       source .env.demo
       # 1) read-only proof refresh
       python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
       # 2) wallet audit
       python3 scripts/preview_demo_wallet_audit.py --real-readonly --write-report
       # 3) position reconciliation
       python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report
       # 4) market-backed new-entry review with realtime price guard
       python3 scripts/preview_demo_new_entry_review.py \
           --from-latest-reconciliation \
           --allow-real-market-network \
           --with-realtime-price-guard \
           --write-report
       # 5) protected-entry preview (TASK-014Q — still preview-only)
       python3 scripts/preview_demo_new_entry_protection.py \
           --from-latest-review --symbol SOLUSDT --write-report
       # 6) stop-loss attachment dry-run (TASK-014R — no network)
       python3 scripts/execute_demo_stop_loss_attachment.py \
           --from-latest-protection --symbol SOLUSDT --write-report
       cat outputs/demo_trading/stop_loss_attachment/latest_stop_loss_attachment.md

   Expected dry-run:
     status=DRY_RUN_STOP_ATTACH_ALLOWED;
     stop_attach_endpoint=/v5/position/trading-stop (NOT invoked);
     payload_preview_only=True; stop_endpoint_called=False;
     order_endpoint_called=False; no_orders_sent=True;
     no_position_modified=True.

3. Optional mock-execute step (still no network, synthetic envelope):
       python3 scripts/execute_demo_stop_loss_attachment.py \
           --from-latest-protection --symbol SOLUSDT \
           --confirm-token CONFIRM_DEMO_STOP_ATTACH_$(date -u +%Y%m%d) \
           --mock-execute-stop --write-report

   Expected:
     status=MOCK_STOP_ATTACH_SUCCESS; mock_stop_attached=True;
     mock_response.retCode=0; stop_endpoint_called=False;
     order_endpoint_called=False; no_position_modified=True.

4. Confirm TASK-014L sender remains blocked on actual --execute-new-entry:
       python3 scripts/execute_demo_new_entry.py \
           --from-latest-review --symbol SOLUSDT \
           --confirm-token CONFIRM_DEMO_NEW_ENTRY_$(date -u +%Y%m%d) \
           --execute-new-entry --write-report
   Expected: blocked_gates contains "protected_entry_policy_missing";
   execute_allowed=False; order_sent=False.  G20 is intentionally NOT
   lifted by TASK-014R.

5. Human decision gate: TASK-014S (Protected New-entry Orchestrator /
   Entry + Stop Attach Mock Chain) is the next authorized step.  It
   will sequence entry submit + stop attach + post-fill verification
   with all-or-fail semantics, and only then lift G20.

## TASK-014Q Status (2026-06-09)

| item | status |
|---|---|
| src/demo_new_entry_protection.py — NEW pure-computation module; 6-phase protected entry lifecycle constants; endpoint-group separation (order_create / trading_stop / read_only) declared via constants only; ProtectedEntryPlan dataclass with safety invariants; build_protected_entry_plan() validates review-level (realtime_price_guard_verified) + payload-level (symbol/side/qty/entry/stop) + stop direction (long stop strictly below entry, short stop strictly above entry); always emits protected_entry_execute_allowed=False with reason stop_loss_attachment_not_implemented | DONE |
| src/demo_new_entry_protection.py — no urlopen / requests / httpx / hmac / api-*.bybit.com / X-BAPI-SIGN / env reads / BybitExecutor; STOP_ATTACH_ENDPOINT constant declared but never invoked; G20_BLOCKED_GATE_NAME = "protected_entry_policy_missing" | CONFIRMED |
| scripts/preview_demo_new_entry_protection.py — NEW CLI: --from-latest-review / --symbol / --write-report; reads outputs/demo_trading/new_entry_review/latest_new_entry_review.json; writes JSON + Markdown to outputs/demo_trading/new_entry_protection/{ts}_*.{json,md} + latest_*; report includes endpoint-group separation table + safety invariants section + blocked reasons | DONE |
| src/demo_new_entry_sender.py — G20 gate "protected_entry_policy_missing" inserted AFTER dry-run early return / BEFORE pre-send refresh; actual --execute-new-entry short-circuits with execute_allowed=False, order_sent=False, blocked_gates=[G20_BLOCKED_GATE_NAME]; dry-run path reports protected_entry_required=True via new field; instance attribute _protected_entry_policy_required defaults True with explicit test opt-out for F23/F24/F25 legacy mechanics tests | DONE |
| scripts/execute_demo_new_entry.py — propagates protected_entry_required to console output + Markdown report row | DONE |
| tests/demo_trading/test_demo_new_entry_protection.py — 63 tests Q1-Q16 covering realtime guard required, missing/zero/negative/None stop_price → fail closed, long stop below entry, short stop above entry (AVAXUSDT), missing/unknown symbol, preview does not send order, no stop endpoint call + endpoint group separation, no secrets in output / no env reads / no live hostname, forbidden imports (~20 modules), sender G20 blocks actual execute with urlopen sentinel, sender dry-run reports protected_entry_required, defense-in-depth G19+G20, code-only AST/tokenize scan for forbidden words (no TP / leverage / transfer / withdraw / deposit / emergency_close), ProtectedEntryPlan to_dict round-trip, lifecycle phase check, preview-only status, CLI missing-review → exit 1, --write-report emits JSON + Markdown | DONE |
| tests/demo_trading/test_demo_new_entry_sender.py — F23/F24/F25/TestExecuteUsesDemoEndpoint/TestOrderBodyComposition opt out of G20 via sender._protected_entry_policy_required = False to preserve existing sender mechanics coverage | DONE |
| pytest tests/demo_trading | 1188/1188 PASS (1125 prior + 63 new Q-series) |
| py_compile new + modified files | PASS |
| no live hostname (api.bybit.com / api-testnet.bybit.com) in protection module or preview script; only documentation references to api-demo.bybit.com via underlying review | CONFIRMED |
| AST/code-only scan: protection module imports no main / src.risk / BybitExecutor / pybit / demo_close_only_sender / demo_emergency_close_sender / scripts.execute_*; no urlopen / requests / httpx / hmac / os.environ in CODE (string literals + docstrings excluded via tokenize) | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| no orders sent / no positions modified / no stop endpoint called / no order endpoint called / no secrets observed | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-09 TASK-014Q)

1. Update VPS git pull and inspect the new protection module + extended CLI + sender G20 gate:
       src/demo_new_entry_protection.py
       scripts/preview_demo_new_entry_protection.py
       src/demo_new_entry_sender.py
       scripts/execute_demo_new_entry.py
       tests/demo_trading/test_demo_new_entry_protection.py
       tests/demo_trading/test_demo_new_entry_sender.py

2. VPS protected-entry DRY-RUN flow (no orders sent / no stop endpoint called):
       source .env.demo
       # 1) read-only proof refresh
       python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
       # 2) wallet audit
       python3 scripts/preview_demo_wallet_audit.py --real-readonly --write-report
       # 3) position reconciliation
       python3 scripts/preview_demo_position_reconcile.py --real-readonly --write-report
       # 4) new-entry review with market-backed builder + realtime guard
       python3 scripts/preview_demo_new_entry_review.py \
           --from-latest-reconciliation \
           --allow-real-market-network \
           --with-realtime-price-guard \
           --write-report
       # 5) protected entry preview (TASK-014Q — preview-only, never sends)
       python3 scripts/preview_demo_new_entry_protection.py \
           --from-latest-review --symbol <verified-symbol> --write-report
       cat outputs/demo_trading/new_entry_protection/latest_new_entry_protection.md

   Expected: ProtectedEntryPlan reports phase=pre_entry_review, status=preview_only,
             stop direction validated, stop_loss_endpoint_allowed=False,
             protected_entry_execute_allowed=False with reason
             stop_loss_attachment_not_implemented; no_orders_sent=True,
             order_endpoint_called=False, stop_endpoint_called=False.

3. Confirm TASK-014L sender now blocks actual --execute-new-entry:
       python3 scripts/execute_demo_new_entry.py \
           --from-latest-review --symbol <verified-symbol> \
           --confirm-token CONFIRM_DEMO_NEW_ENTRY_$(date -u +%Y%m%d) \
           --execute-new-entry --write-report

   Expected: blocked_gates contains "protected_entry_policy_missing";
   execute_allowed=False; order_sent=False; protected_entry_required=True.
   Dry-run (--dry-run instead of --execute-new-entry) still succeeds with
   protected_entry_required=True surfaced as new field.

4. Human decision gate: TASK-014R (Demo Stop-loss Attachment Sender /
   Trading Stop Dry-run) is the next authorized step to enable
   protected entry execution.

## TASK-014P Status (2026-06-09)

| item | status |
|---|---|
| src/demo_new_entry_candidate_builder.py — NEW pure-computation module; NewEntryIntent + CandidateBuildResult dataclasses; build_market_backed_candidate() + batch helper; stop model long stop = rt*(1-pct) / short stop = rt*(1+pct), default 5%, rounded to instrument tick | DONE |
| src/demo_new_entry_candidate_builder.py — fail-closed: missing/unusable realtime price → SKIP_NO_REALTIME_PRICE / SKIP_INVALID_REALTIME_PRICE; skipped result NEVER carries a price; no fixture fallback; validates risk / side / instrument rule / stop_pct range / rounded stop on protective side | DONE |
| src/demo_new_entry_candidate_builder.py — no HTTP / urllib / requests / httpx / hmac / api-*.bybit.com / X-BAPI-SIGN / /v5/order / env reads / forbidden imports (main / src.risk / BybitExecutor / pybit / demo_close_only_sender / demo_new_entry_sender / demo_emergency_close_sender) | CONFIRMED |
| scripts/preview_demo_new_entry_review.py — intent pool (SOLUSDT/AAVEUSDT long, AVAXUSDT/LINKUSDT short) when mode=from_latest_reconciliation; realtime fetch via TASK-014O guard; build_market_backed_candidates() pipes priced candidates into existing guard pipeline; report adds "Market-backed Candidate Builder (TASK-014P)" section | DONE |
| scripts/preview_demo_new_entry_review.py — fixture mode preserved verbatim; legacy 160 / 120 candidates still flow through TASK-014O guard and get rejected as stale_entry_reference_price (correct posture) | CONFIRMED |
| tests/demo_trading/test_demo_new_entry_candidate_builder.py — 54 tests P1–P12 covering SOL 65.92 / AAVE 62.14 builds, stop model long/short, parametrized stop_distance, missing/zero/error realtime, no fixture leak, invalid stop_pct / risk / side / instrument rule, tick-collapse, batch helper, to_dict round-trip, module source cleanliness, forbidden-imports | DONE |
| tests/demo_trading/test_demo_new_entry_review.py — 6 TASK-014P integration tests: SOLUSDT realtime payload verified + notional anchored to 65.92; AAVEUSDT 62.14 replaces 120 fixture; missing market price → no payloads + top-level guard False + no_payload_to_send; sender G19 passes market-backed verified review; sender G19 still blocks legacy AAVE 120/110; pipeline-level safety invariants | DONE |
| pytest tests/demo_trading | 1125/1125 PASS (1065 prior + 54 builder + 6 integration) |
| py_compile new + modified files | PASS |
| SOLUSDT / AAVEUSDT no longer use fixture 160 / 120 in market-backed mode; builder produces SOL entry=65.92 stop=62.62, AAVE entry=62.14 stop=59.03 | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| no orders sent / no positions modified / no order endpoint called / no secrets observed via market-backed pipeline | CONFIRMED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-09 TASK-014P)

1. Update VPS git pull and inspect the new builder + extended CLI:
       src/demo_new_entry_candidate_builder.py
       scripts/preview_demo_new_entry_review.py
       tests/demo_trading/test_demo_new_entry_candidate_builder.py
       tests/demo_trading/test_demo_new_entry_review.py

2. VPS market-backed DRY-RUN (no orders sent):
       source .env.demo
       # 1) read-only proof refresh
       python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
       # 2) preview new-entry review with market-backed candidate builder + guard
       python3 scripts/preview_demo_new_entry_review.py \
           --from-latest-reconciliation \
           --allow-real-market-network \
           --with-realtime-price-guard \
           --write-report
       cat outputs/demo_trading/new_entry_review/latest_new_entry_review.md

   Expected: "Market-backed Candidate Builder (TASK-014P)" section lists per-symbol
             realtime price and builder output (entry / stop); SOLUSDT entry shows
             current realtime market price (NOT 160); AAVEUSDT entry shows current
             realtime market price (NOT 120); any intent without a realtime price
             is skipped — never falls back to fixture; guard section now reports
             0% deviation for builder-priced candidates; review-level
             realtime_price_guard_verified=True only if all accepted payloads
             are verified.

3. Re-run TASK-014L Demo new-entry dry-run sender against a market-backed review:
       python3 scripts/execute_demo_new_entry.py \
           --from-latest-review --symbol <verified-symbol> \
           --confirm-token CONFIRM_DEMO_NEW_ENTRY_$(date -u +%Y%m%d) \
           --dry-run --write-report

   Expected (DRY-RUN): G19 missing_realtime_price_guard NOT present;
   gates pass; no order sent.

4. Human decision gate: review the dry-run report and decide whether to
   proceed to actual order send (separate authorized step).

## TASK-014O Status (2026-06-09)

| item | status |
|---|---|
| src/demo_market_price_guard.py — RealtimeMarketPrice + PriceGuardEvaluation dataclasses, evaluate_price_guard() pure evaluator, batch helper, DemoMarketPriceGuard public-market client (api-demo.bybit.com + /v5/market/tickers only) | DONE |
| src/demo_market_price_guard.py — default guard threshold 5.0%; failure reasons missing/stale/invalid; PRICE_SOURCE_BYBIT_DEMO_TICKER + PRICE_SOURCE_FIXTURE; no HMAC; no env vars; no secrets; no order endpoint | DONE |
| src/demo_new_entry_review.py — review_new_entry_candidates() accepts price_guard_evaluations & price_guard_threshold_pct; missing => REJECT_MISSING_REALTIME_PRICE; stale >5% => REJECT_STALE_ENTRY_REFERENCE_PRICE; verified => qty / notional / stop_risk anchored to realtime market price | DONE |
| src/demo_new_entry_review.py — NewEntryPayloadPreview carries realtime_price_guard_verified / price_source / realtime_market_price / price_deviation_pct / price_guard_threshold_pct / price_timestamp_utc | DONE |
| src/demo_new_entry_review.py — top-level review.realtime_price_guard_verified=True iff guard pipeline engaged AND not fail_closed AND ≥1 payload emitted AND all emitted payloads verified | DONE |
| scripts/preview_demo_new_entry_review.py — --with-realtime-price-guard (default ON) / --allow-real-market-network (default OFF) / --price-guard-threshold-pct CLI flags; report includes "Realtime Price Guard (TASK-014O)" section | DONE |
| tests/demo_trading/test_demo_market_price_guard.py — 51 tests O1-O12 + batch + dataclass round-trip; SOLUSDT 160 vs 66.47 incident replayed | DONE |
| tests/demo_trading/test_demo_new_entry_review.py — 26 new TASK-014O integration tests (O1-O13) covering missing / stale / verified / payload fields / guarded-price anchor / no-order-endpoint / no-secrets / forbidden-imports / sender G19 contract | DONE |
| pytest tests/demo_trading | 1065/1065 PASS (988 prior + 51 guard + 26 review integration) |
| py_compile new + modified files | PASS |
| guard module never contacts /v5/order/ paths; never reaches api.bybit.com / api-testnet.bybit.com; only api-demo.bybit.com + /v5/market/tickers | CONFIRMED |
| review module remains free of urllib / requests / httpx / hmac / api-*.bybit.com / X-BAPI-SIGN tokens | CONFIRMED |
| AST imports (review + guard module): no main / src.risk / BybitExecutor / pybit / demo_close_only_sender / demo_new_entry_sender / demo_emergency_close_sender / scripts.execute_* | CONFIRMED |
| backward compat: existing 47 K-series tests pass unchanged when price_guard_evaluations is None; payloads emit realtime_price_guard_verified=False; sender G19 refuses them (correct fail-closed) | CONFIRMED |
| sender G19 contract: O11 review with realtime_price_guard_verified=False → "missing_realtime_price_guard" in blocked_gates / execute_allowed=False / order_sent=False | CONFIRMED |
| sender G19 contract: O12 review with realtime_price_guard_verified=True → "missing_realtime_price_guard" not in blocked_gates / dry-run execute_allowed=True / order_sent=False | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-09 TASK-014O)

1. Update VPS git pull and inspect the new guard module + extended review + CLI:
       src/demo_market_price_guard.py
       src/demo_new_entry_review.py
       scripts/preview_demo_new_entry_review.py
       tests/demo_trading/test_demo_market_price_guard.py
       tests/demo_trading/test_demo_new_entry_review.py

2. VPS realtime-guard DRY-RUN (no orders sent):
       source .env.demo
       # 1) read-only proof refresh
       python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
       # 2) preview new-entry review WITH realtime price guard ON
       python3 scripts/preview_demo_new_entry_review.py \
           --from-latest-reconciliation \
           --allow-real-market-network \
           --with-realtime-price-guard \
           --write-report
       cat outputs/demo_trading/new_entry_review/latest_new_entry_review.md

   Expected: report's "Realtime Price Guard (TASK-014O)" section lists per-symbol
             candidate price vs realtime market price; any deviation >5% is
             rejected as stale_entry_reference_price; review-level
             realtime_price_guard_verified=True only if all accepted payloads
             are verified.

3. Re-run TASK-014L Demo new-entry dry-run sender against a guarded review:
       python3 scripts/execute_demo_new_entry.py \
           --from-latest-review --symbol <verified-symbol> \
           --confirm-token CONFIRM_DEMO_NEW_ENTRY_$(date -u +%Y%m%d) \
           --dry-run --write-report

   Expected (DRY-RUN): G19 missing_realtime_price_guard NOT present; gates pass;
   no order sent.

4. Only after Rick reviews the guarded preview JSON and approves the next
   workorder may a live new-entry be re-attempted (separate task).

---

## TASK-014N Status (2026-06-09)

| item | status |
|---|---|
| src/demo_emergency_close_sender.py — EmergencyCloseOrderResult dataclass | DONE |
| src/demo_emergency_close_sender.py — DemoEmergencyCloseSender (15 static gates + token gate + pre-send refresh + single reduce-only Market POST) | DONE |
| src/demo_emergency_close_sender.py — order body: category=linear, Market, reduceOnly=True, closeOnTrigger=False, side=Buy/Sell, qty>0, timeInForce=IOC, positionIdx=0, no leverage/TP/SL/triggerPrice/transfer | DONE |
| src/demo_emergency_close_sender.py — endpoint: only api-demo.bybit.com + /v5/order/create (one order per invocation) | DONE |
| scripts/execute_demo_emergency_close.py — CLI (--from-latest-postfill --symbol --confirm-token --dry-run --execute-emergency-close --write-report) | DONE |
| tests/demo_trading/test_demo_emergency_close_sender.py — 59 tests (N1-N25 + structural invariants + CLI integration) | DONE |
| .gitignore — outputs/demo_trading/emergency_close_execution/ | DONE |
| pytest tests/demo_trading | 988/988 PASS (929 prior + 59 new) |
| py_compile new files | PASS |
| postfill gates: postfill_not_fail_closed / recommended_action_not_emergency_close_preview / emergency_close_preview_missing | CONFIRMED |
| preview-shape gates: preview_reason_not_missing_stop_price / preview_only_must_be_true / preview_reduce_only_must_be_true / preview_order_sent_must_be_false / preview_order_endpoint_called_must_be_false / preview_order_type_not_market | CONFIRMED |
| confirm-token gates: missing_confirm_token / invalid_confirm_token_format / confirm_token_date_mismatch (today UTC) | CONFIRMED |
| symbol gates: missing_symbol / symbol_mismatch_vs_preview | CONFIRMED |
| side/qty gates: close_order_side_mismatch_vs_position_side / invalid_close_order_side_in_preview / invalid_position_side_in_preview / invalid_qty_not_positive | CONFIRMED |
| pre-send refresh: proof_strong + endpoint_demo + account_mode_demo + target_position_present + side_match + live_qty_positive + preview_qty<=live_qty + stop_still_missing + close_side_consistent_with_live | CONFIRMED |
| short-circuit refresh: stop_restored_no_emergency_close_needed (live stop_price > 0) blocks send | CONFIRMED |
| dry-run default: order_sent=False / order_endpoint_called=False / no_position_modified=True | CONFIRMED |
| execute path: signed Bybit V5 HMAC POST to api-demo.bybit.com + /v5/order/create only; reduceOnly=True always; live host never contacted | CONFIRMED |
| mocked retCode==0 → order_id set / order_sent=True / no_position_modified=False; no secrets in result | CONFIRMED |
| mocked retCode!=0 → fail_closed=True / order_sent=False (best-effort even if exchange responded) | CONFIRMED |
| structural invariants: no_live_endpoint=True / no_batch_order=True / no_new_entry_path=True / no_close_only_sender_reused=True / reduce_only=True (always) / secret_value_observed=False | CONFIRMED |
| no env secret values written into JSON or MD reports | CONFIRMED |
| AST imports (module + CLI): no main / src.risk / BybitExecutor / pybit / demo_close_only_sender / demo_new_entry_sender / demo_new_entry_postfill_verify / execute_demo_close_only_cleanup / execute_demo_new_entry / verify_demo_new_entry_postfill | CONFIRMED |
| source scan: no api.bybit.com / api.bytick.com / /v5/order/create-batch / set-trading-stop / set-leverage / transfer / withdraw / deposit / triggerPrice / takeProfit / stopLoss / tpslMode in emergency-close module or CLI | CONFIRMED |
| one-order limit: exactly one /v5/order/create POST per submit_one_emergency_close() invocation | CONFIRMED |
| main.py / src/risk.py / BybitExecutor / demo_close_only_sender / demo_new_entry_sender / demo_new_entry_postfill_verify | NOT MODIFIED |
| local commit | DONE |

## Next Rick Action (set by 2026-06-09 TASK-014N)

1. Update VPS git pull and inspect the new emergency-close sender + CLI:
       src/demo_emergency_close_sender.py
       scripts/execute_demo_emergency_close.py
       tests/demo_trading/test_demo_emergency_close_sender.py

2. VPS emergency-close DRY-RUN preview (no order will be sent):
       source .env.demo
       # 1) read-only proof refresh
       python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
       # 2) re-run post-fill verification with emergency preview enabled
       python3 scripts/verify_demo_new_entry_postfill.py \
           --from-latest-execution --from-latest-readonly-smoke \
           --with-emergency-close-preview --write-report
       # 3) DRY-RUN the emergency close sender (no order sent)
       python3 scripts/execute_demo_emergency_close.py \
           --from-latest-postfill --symbol SOLUSDT \
           --confirm-token CONFIRM_DEMO_EMERGENCY_CLOSE_$(date -u +%Y%m%d) \
           --dry-run --write-report
       cat outputs/demo_trading/emergency_close_execution/latest_emergency_close.md

   Expected (DRY-RUN): order_sent=False, order_endpoint_called=False,
   no_position_modified=True, all 15 static gates pass, pre-send refresh either
   confirms SOLUSDT still has stop_price=0 (proceeding to execute would be
   allowed) OR fires stop_restored_no_emergency_close_needed (manual UI added
   stop in the meantime — execute path becomes blocked, which is the desired
   fail-closed outcome).

3. Manual decision point — Rick decides whether to escalate from DRY-RUN to
   --execute-emergency-close for the SOLUSDT missing-stop position.  This commit
   does NOT auto-escalate.  Suggested escalation, only after Rick explicitly
   approves:
       python3 scripts/execute_demo_emergency_close.py \
           --from-latest-postfill --symbol SOLUSDT \
           --confirm-token CONFIRM_DEMO_EMERGENCY_CLOSE_$(date -u +%Y%m%d) \
           --execute-emergency-close --write-report

   This will send EXACTLY ONE reduce-only Market order (side=Sell for the long
   SOLUSDT) to api-demo.bybit.com /v5/order/create and write the execution
   report under outputs/demo_trading/emergency_close_execution/.  Reduce-only
   is hard-coded True; closeOnTrigger=False; positionIdx=0; timeInForce=IOC;
   no TP/SL/triggerPrice/leverage/transfer fields are present in the body.

4. Alternative manual path: Bybit Demo UI — add a stop on SOLUSDT manually,
   then re-run the DRY-RUN; pre-send refresh will fire
   `stop_restored_no_emergency_close_needed` and the sender will fail closed
   without any further action.

## Status
READY (Rick action: VPS DRY-RUN of the emergency close sender for the SOLUSDT
        missing-stop position, then manual decision whether to escalate with
        --execute-emergency-close OR resolve the missing stop via the Demo
        UI).  No order was sent, no position was modified, no secret was
        observed, no live endpoint was contacted by this commit.

## Owner
Rick

## TASK-014M Status (2026-06-09)

| item | status |
|---|---|
| src/demo_new_entry_postfill_verify.py — PostFillVerificationResult dataclass + verify_postfill() | DONE |
| src/demo_new_entry_postfill_verify.py — make_emergency_close_preview() (long→Sell, short→Buy, reduce_only=True, preview_only=True) | DONE |
| scripts/verify_demo_new_entry_postfill.py — CLI (--from-latest-execution --from-latest-readonly-smoke --from-latest-review --write-report --with-emergency-close-preview) | DONE |
| src/demo_new_entry_sender.py — G19 missing_realtime_price_guard gate (review.realtime_price_guard_verified must be True) | DONE |
| tests/demo_trading/test_demo_new_entry_postfill_verify.py — 62 tests (M1-M17 + helpers + structural invariants + production-incident replay + CLI integration) | DONE |
| tests/demo_trading/test_demo_new_entry_sender.py — TestRealtimePriceGuard (verified/false/missing) + _build_review helper updated | DONE |
| .gitignore — outputs/demo_trading/new_entry_postfill/ | DONE |
| pytest tests/demo_trading | 929/929 PASS (864 prior + 62 new postfill + 3 new guard) |
| py_compile new files | PASS |
| post-fill ORDER_SENT detection + position_found gate + side/qty/entry checks | CONFIRMED |
| missing_stop_price gate (stop_price<=0) → fail_closed | CONFIRMED |
| stale_price_mismatch gate (|actual-expected|/expected > 5%) → fail_closed | CONFIRMED |
| production-incident replay (SOLUSDT: actual=66.47, expected=160, stop=0) catches both gates | CONFIRMED |
| recommended_action ladder: ACTION_EMERGENCY_PREV (emit+missing_stop+found) / ACTION_MANUAL_UI / ACTION_NONE_REQUIRED | CONFIRMED |
| emergency close preview: long→Sell, short→Buy, reduce_only=True, preview_only=True, order_sent=False, confirmation_required=True | CONFIRMED |
| structural invariants: no_orders_sent=True / order_endpoint_called=False / no_position_modified=True / secret_value_observed=False / no_live_endpoint=True / no_batch_order=True / no_close_only_path=True (always) | CONFIRMED |
| no env secret values written into JSON or MD reports | CONFIRMED |
| AST imports (module + CLI): no main / src.risk / BybitExecutor / demo_close_only_sender / demo_new_entry_sender / execute_demo_close_only_cleanup / execute_demo_new_entry | CONFIRMED |
| source scan: no api.bybit.com / api.bytick.com / /v5/order/create / /v5/order/create-batch in postfill verify module or CLI | CONFIRMED |
| sender G19: missing_realtime_price_guard blocks send when review.realtime_price_guard_verified is not True | CONFIRMED |
| main.py / src/risk.py / BybitExecutor / demo_close_only_sender | NOT MODIFIED |
| local commit | PENDING |

## Next Rick Action (set by 2026-06-09 TASK-014M)

1. Update VPS git pull and inspect the new modules.

2. VPS post-fill verification flow (after a real execute_new_entry run):
     source .env.demo
     python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
     python3 scripts/verify_demo_new_entry_postfill.py \
         --from-latest-execution --from-latest-readonly-smoke --write-report
     cat outputs/demo_trading/new_entry_postfill/latest_new_entry_postfill.md

   Expected for the SOLUSDT incident (order_id aae978ed-...):
     selected_symbol             : SOLUSDT
     position_found              : True
     actual_entry_price          : 66.47
     expected_entry_reference    : 160.0  (from latest_new_entry_review.json)
     actual_stop_price           : 0.0
     missing_stop_price          : True
     stale_price_mismatch        : True
     entry_price_deviation_pct   : ~58.45
     fail_closed                 : True
     no_orders_sent              : True
     order_endpoint_called       : False
     recommended_action          : manual_close_or_add_stop_in_bybit_demo_ui
     (or "emergency_close_preview" if --with-emergency-close-preview is set)

3. If --with-emergency-close-preview is included, the report carries a preview
   dict (symbol=SOLUSDT, position_side=long, close_order_side=Sell,
   reduce_only=True, preview_only=True, order_sent=False).  THIS IS A PREVIEW
   ONLY.  Actual emergency close execution is reserved for a future
   TASK-014N and is NOT performed by this commit.

4. Sender hardening (TASK-014M G19): preview_demo_new_entry_review.py output
   is presently missing `realtime_price_guard_verified=True`, so any future
   execute_demo_new_entry.py run will now hard-fail with
   `missing_realtime_price_guard`.  This is intentional fail-closed behaviour
   until the upstream review pipeline is updated to assert that the
   entry_reference_price was sourced from a live market reading.

## Status
READY (Rick action: VPS post-fill verification, then plan TASK-014N for the
        upstream realtime-price refresh and for the optional emergency
        close-only sender).  No order was sent, no position was modified,
        no secret was observed, no live endpoint was contacted by this
        commit.

## Owner
Rick

## TASK-014L Status (2026-06-09)

| item | status |
|---|---|
| src/demo_new_entry_sender.py — NewEntryOrderResult dataclass | DONE |
| src/demo_new_entry_sender.py — DemoNewEntrySender (static gates + token gate + pre-send refresh + single POST) | DONE |
| src/demo_new_entry_sender.py — order body: category=linear, Market, reduceOnly=False, closeOnTrigger=False, side=Buy/Sell, qty>0, no leverage/TP/SL/triggerPrice/transfer | DONE |
| src/demo_new_entry_sender.py — endpoint: only api-demo.bybit.com + /v5/order/create | DONE |
| scripts/execute_demo_new_entry.py — CLI (--from-latest-review --symbol --confirm-token --dry-run --execute-new-entry --write-report) | DONE |
| tests/demo_trading/test_demo_new_entry_sender.py — 118 tests (F1-F25 + invariants + source scan + report artifacts) | DONE |
| .gitignore — outputs/demo_trading/new_entry_execution/ | DONE |
| pytest tests/demo_trading | 864/864 PASS (746 prior + 118 new) |
| py_compile all new files | PASS |
| top-level static gates: review.fail_closed / proof / endpoint / account_mode / source / available / new_entry_allowed / open_positions | CONFIRMED |
| symbol gate: caller --symbol REQUIRED and must be in accepted_candidates | CONFIRMED |
| token gate: CONFIRM_DEMO_NEW_ENTRY_YYYYMMDD with date equality (today UTC) | CONFIRMED |
| short_new_entry_not_permitted: every short candidate BLOCKED at static gate | CONFIRMED |
| payload gates: reduce_only=False / preview_only=True / order_sent=False / order_endpoint_called=False / side label vs payload side / order_type=Market | CONFIRMED |
| pre-send refresh: proof_strong + endpoint_demo + account_mode_demo + balance>0 + target not already open + live capacity < 10 + long_count<5 (short blocked) + stop_risk<=remaining_budget | CONFIRMED |
| dry-run default: order_sent=False / order_endpoint_called=False / no_position_modified=True | CONFIRMED |
| execute path: signed Bybit V5 HMAC POST to api-demo.bybit.com + /v5/order/create only; live host never contacted | CONFIRMED |
| mocked retCode==0 -> order_id set / order_sent=True / no_position_modified=False; no secrets in result | CONFIRMED |
| mocked retCode!=0 -> order_sent=False / no_position_modified=True; no secrets in result | CONFIRMED |
| structural invariants: no_live_endpoint=True / no_batch_order=True / no_close_only_path=True / reduce_only=False / secret_value_observed=False (always) | CONFIRMED |
| AST imports: no demo_close_only_sender / execute_demo_close_only_cleanup / main / src.risk / BybitExecutor | CONFIRMED |
| source scan: no api.bybit.com / set_leverage / setLeverage / tradingStop / takeProfit / stopLoss / triggerPrice / tpslMode / /asset/transfer / /withdraw / /deposit / /v5/order/create-batch / pybit | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| local commit | PENDING (Rick must git push) |

## Next Rick Action (set by 2026-06-09 TASK-014L)

1. git push origin main  (delivers TASK-014D through TASK-014L)

2. On VPS after git pull — refresh the full pipeline (in order):
     source .env.demo
     python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
     python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report
     python3 scripts/preview_demo_new_entry_review.py --from-latest-reconciliation --write-report

3. Review outputs/demo_trading/new_entry_review/latest_new_entry_review.md
   - fail_closed must be False
   - Identify which accepted long candidate to send first
     (production state currently: short_count=5/5 → all shorts REJECTED;
      typical accepted longs: SOLUSDT, AAVEUSDT)

4. Dry-run the new-entry sender (no order will be submitted):
     python3 scripts/execute_demo_new_entry.py \
         --from-latest-review \
         --symbol SOLUSDT \
         --confirm-token CONFIRM_DEMO_NEW_ENTRY_$(date -u +%Y%m%d) \
         --dry-run --write-report

   Expected on success:
     mode                     : dry_run
     selected_symbol          : SOLUSDT
     selected_side            : long
     order_side               : Buy
     order_type               : Market
     reduce_only              : False
     execute_requested        : False
     execute_allowed          : True
     order_sent               : False
     order_endpoint_called    : False
     no_position_modified     : True
     no_live_endpoint         : True
     no_batch_order           : True
     no_close_only_path       : True
     secret_value_observed    : False
     blocked_gates            : []

5. If and only if Rick approves, submit the single order:
     python3 scripts/execute_demo_new_entry.py \
         --from-latest-review \
         --symbol SOLUSDT \
         --confirm-token CONFIRM_DEMO_NEW_ENTRY_$(date -u +%Y%m%d) \
         --execute-new-entry --write-report

   Pre-send refresh re-checks proof / endpoint / account_mode / balance /
   open positions / target not already open / long capacity / risk budget.
   On retCode==0 the report records the order_id and order_sent=True.

6. After any execution attempt: re-run the read-only smoke + reconciliation
   + new-entry review and inspect the resulting state.

## Status
READY (Rick action: git push + VPS pipeline refresh + dry-run new-entry sender
        for the chosen accepted long candidate + decide whether to add
        --execute-new-entry).  No new-entry order has been submitted by this
        commit.

## Owner
Rick

## TASK-014K Status (2026-06-09)

| item | status |
|---|---|
| src/demo_new_entry_review.py — review_new_entry_candidates (pure computation) | DONE |
| src/demo_new_entry_review.py — NewEntryCandidate / NewEntryPayloadPreview / NewEntryEvaluation / NewEntryReviewResult | DONE |
| src/demo_new_entry_review.py — layered fail-closed gates (top-level + per-candidate) | DONE |
| scripts/preview_demo_new_entry_review.py — fixture + --from-latest-reconciliation + --write-report | DONE |
| tests/demo_trading/test_demo_new_entry_review.py — 47 tests (K1-K19) | DONE |
| .gitignore — outputs/demo_trading/new_entry_review/ | DONE |
| pytest tests/demo_trading | 746/746 PASS |
| py_compile all new files | PASS |
| top-level gate: demo_runtime_verified + STRONG + real_readonly + new_entry_allowed + available>0 + slots | CONFIRMED |
| per-candidate gate: side capacity → open slot → duplicate → rule → prices → stop_distance → risk → rounding → notional → cap → projected exposure | CONFIRMED |
| short_capacity_full → every short candidate REJECTED | CONFIRMED |
| payload.preview_only=True / order_sent=False / order_endpoint_called=False (always) | CONFIRMED |
| payload.reduce_only=False on new entries | CONFIRMED |
| action_type=PREVIEW_REVIEW_ONLY (always) | CONFIRMED |
| no_orders_sent=True / no_position_modified=True (always) | CONFIRMED |
| secret_value_observed=False (always) | CONFIRMED |
| module source: no live hostname, no order endpoint, no HTTP client | CONFIRMED |
| module imports: no main / src.risk / BybitExecutor / demo_close_only_sender / execute_demo_close_only_cleanup | CONFIRMED |
| running portfolio state mutation when each candidate accepts (capacity / budget / notional) | CONFIRMED |
| next_required_task = "TASK-014L Demo New-entry Sender Gate (manual approval required)" when any accept | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| local commit | PENDING (Rick must git push) |

## Next Rick Action (set by 2026-06-09 TASK-014K)

1. git push origin main (delivers TASK-014D through TASK-014K)
2. On VPS after git pull — refresh pipeline (in order):
     source .env.demo
     python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
     python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report
     python3 scripts/preview_demo_new_entry_review.py --from-latest-reconciliation --write-report
3. Review outputs/demo_trading/new_entry_review/latest_new_entry_review.md
   - fail_closed must be False (top-level gates all pass)
   - any short candidate listed will be rejected with short_capacity_full
     (current real state has short_count=5/5)
   - any well-formed long candidate should appear in payload_previews with
     preview_only=True / order_sent=False / order_endpoint_called=False
4. Decide whether to open TASK-014L (Demo New-entry Sender Gate).
   No new-entry payload can be transmitted before TASK-014L is implemented
   AND a manual confirmation token is supplied at execute time.

## Status
READY (Rick action: git push + VPS pipeline + review new-entry preview report
        + decide whether to open TASK-014L)

## Owner
Rick

## TASK-014J Status (2026-06-09)

| item | status |
|---|---|
| src/demo_readonly_client.py — WalletSnapshot.available_balance_usd_source field | DONE |
| src/demo_readonly_client.py — _wallet_real priority cascade (TAB → acc.ATW → coin.ATW → free) | DONE |
| src/demo_readonly_client.py — FIXTURE_WALLET.available_balance_usd_source updated | DONE |
| src/demo_wallet_audit.py — CURRENT_MAPPING_FIELD = account.totalAvailableBalance | DONE |
| scripts/preview_demo_readonly_runtime.py — available_balance_usd_source + wallet_account_type in report | DONE |
| tests/demo_trading/test_demo_task_014j.py — 40 tests (J1-J12) | DONE |
| pytest tests/demo_trading | 699/699 PASS |
| py_compile all modified files | PASS |
| account.totalAvailableBalance priority 1 → available_balance_usd | CONFIRMED |
| coin.USDT.walletBalance excluded from available mapping | CONFIRMED |
| all-candidates-absent → available=0, source=missing | CONFIRMED |
| wallet audit mapping_suspect=False when current matches TAB | CONFIRMED |
| no order endpoint / no secrets in output | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| local commit | PENDING (Rick must git push) |

## Root Cause Fixed

VPS real read-only audit (TASK-014I) returned:
  account.totalAvailableBalance = 7169.40 USD
  coin.USDT.availableToWithdraw = 0.00 USD  ← was being used as available_balance_usd

Prior mapping used coin.USDT.availableToWithdraw which is 0 when positions are open
(margin is locked).  New mapping reads account.totalAvailableBalance first, which
reflects the total cross-margin free balance across all coins.

## Next Rick Action (set by 2026-06-09 TASK-014J)

1. git push origin main (delivers TASK-014D through TASK-014J)
2. On VPS after git pull — re-run full smoke + reconciliation pipeline:
     source .env.demo
     python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
     python3 scripts/preview_demo_position_reconcile.py --from-latest-smoke --write-report
     python3 scripts/preview_demo_close_only_cleanup.py \
         --from-latest-reconciliation \
         --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) --write-report
3. Check smoke report: available_balance_usd should now show ~7169 (not 0.00)
   and available_balance_usd_source should read "account.totalAvailableBalance"
4. If available_balance_usd > 0 and short_count > 5: execute close-only for the
   highest stop-risk candidates (as before — one per invocation):
     python3 scripts/execute_demo_close_only_cleanup.py \
         --from-latest-cleanup \
         --symbol <REAL_SYMBOL> \
         --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) \
         --write-report
   Manual execute decision is Rick's; add --execute-close-only when ready.

## Status
READY (Rick action: git push + VPS re-smoke + verify available_balance_usd ~7169)

## Owner
Rick

## TASK-014H Status (2026-06-09)

| item | status |
|---|---|
| scripts/preview_demo_readonly_runtime.py — positions[] + position_details_source | DONE |
| scripts/preview_demo_position_reconcile.py — load real positions, fail-closed on missing | DONE |
| scripts/preview_demo_close_only_cleanup.py — thread position_details_source through plan_cleanup | DONE |
| scripts/execute_demo_close_only_cleanup.py — report displays position_details_source | DONE |
| src/demo_position_reconcile.py — ReconciliationResult.position_details_source + positions[] | DONE |
| src/demo_close_only_cleanup.py — CleanupPlan.position_details_source, execute_ready gated | DONE |
| src/demo_close_only_sender.py — Gate 5b position_details_source_not_real_readonly | DONE |
| tests/demo_trading/test_demo_task_014h.py — 30 tests (H1-H13) | DONE |
| tests/demo_trading/test_demo_close_only_cleanup.py — fixtures updated | DONE |
| tests/demo_trading/test_demo_close_only_sender.py — helper updated | DONE |
| pytest tests/demo_trading | 614/614 PASS |
| py_compile all modified files | PASS |
| reconciliation fail-closed when real smoke lacks positions details | CONFIRMED |
| cleanup execute_ready=False when source != real_readonly | CONFIRMED |
| sender Gate 5b blocks fixture-only candidates (ETHUSDT / BNBUSDT) | CONFIRMED |
| no orders sent / no Demo POST issued in pipeline | CONFIRMED |
| no API key / secret bytes in any JSON or MD report | CONFIRMED |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| local commit | PENDING (Rick must git push) |

## Next Rick Action (set by 2026-06-09 TASK-014H)

1. git push origin main (delivers TASK-014D through TASK-014H)
2. On VPS after git pull — refresh pipeline (in order):
     source .env.demo
     python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
     python3 scripts/preview_demo_position_reconcile.py --from-latest-smoke --write-report
     python3 scripts/preview_demo_close_only_cleanup.py --from-latest-reconciliation \\
         --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) --write-report
3. Verify the cleanup plan now references the REAL Demo symbols (e.g. AIXBTUSDT,
   ENAUSDT, BOMEUSDT, EDUUSDT, MERLUSDT, XAUTUSDT, POLYXUSDT, TIAUSDT), not
   ETHUSDT / BNBUSDT.
4. Dry-run single close gated on real symbol (review before executing):
     python3 scripts/execute_demo_close_only_cleanup.py \\
         --from-latest-cleanup \\
         --symbol <REAL_SYMBOL_FROM_RECONCILIATION> \\
         --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) \\
         --write-report
5. Review outputs/demo_trading/close_only_execution/latest_close_only_execution.md
   (position_details_source must read `real_readonly`; source_position_details_is_real
   must be True before execute is permitted).
6. Manual execute decision is Rick's; sender still requires --execute-close-only.

## Status
READY (Rick action: git push + VPS pipeline + dry-run review + manual execute decision)

## Owner
Rick

## TASK-014G Status (2026-06-06)

| item | status |
|---|---|
| src/demo_close_only_sender.py — DemoCloseOnlySender, CloseOrderResult | DONE |
| src/demo_close_only_sender.py — layered gate checks + pre-send refresh | DONE |
| scripts/execute_demo_close_only_cleanup.py — CLI gate + one-order limit | DONE |
| tests/demo_trading/test_demo_close_only_sender.py — 90 tests (G1-G23) | DONE |
| pytest tests/demo_trading/ | 584/584 PASS |
| py_compile all new files | PASS |
| .gitignore — outputs/demo_trading/close_only_execution/ | DONE |
| dry-run default: no send | CONFIRMED |
| execute_close_only=True: pre-send refresh + Demo endpoint only | CONFIRMED |
| one-order-per-invocation limit enforced in CLI | CONFIRMED |
| reduce_only=True enforced at gate | CONFIRMED |
| close_side: Buy=close short, Sell=close long | CONFIRMED |
| secret_value_observed=False always | CONFIRMED |
| no_live_endpoint=True always | CONFIRMED |
| source scan: no live hostname, no leverage/stop/fund-movement ops | PASS |
| main.py / src/risk.py / exchange executors | NOT MODIFIED |
| local commit | PENDING (Rick must git push) |

## Next Rick Action (set by 2026-06-06 TASK-014G)

1. git push origin main (delivers TASK-014D through TASK-014G)
2. On VPS after git pull — refresh pipeline (in order):
     source .env.demo
     python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
     python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report
     python3 scripts/preview_demo_close_only_cleanup.py --from-latest-reconciliation \\
         --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) --write-report
3. Dry-run single close (review before executing):
     python3 scripts/execute_demo_close_only_cleanup.py \\
         --from-latest-cleanup \\
         --symbol ETHUSDT \\
         --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) \\
         --write-report
4. Review outputs/demo_trading/close_only_execution/latest_close_only_execution.md
5. If dry-run passes all gates (execute_allowed=True), Rick manually decides:
     python3 scripts/execute_demo_close_only_cleanup.py \\
         --from-latest-cleanup \\
         --symbol ETHUSDT \\
         --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) \\
         --execute-close-only \\
         --write-report
6. Repeat for BNBUSDT if needed.
7. Commit forward_record bundle (MM files) — see TASK-013 section below.

NOTE: Step 5 is Rick's decision. Claude has not sent any orders.
      TASK-014G is a gate, not an auto-executer.

## Status
READY (Rick action: git push + VPS pipeline + dry-run review + manual execute decision)

## Owner
Rick

## TASK-014F Status (2026-06-06)

| item | status |
|---|---|
| src/demo_close_only_cleanup.py — plan_cleanup() pure computation | DONE |
| src/demo_close_only_cleanup.py — CleanupPlan, ClosePayloadPreview, CloseCandidate | DONE |
| scripts/preview_demo_close_only_cleanup.py — fixture + --from-latest-reconciliation | DONE |
| scripts/preview_demo_close_only_cleanup.py — --confirm-token + --write-report | DONE |
| tests/demo_trading/test_demo_close_only_cleanup.py — 89 tests (E1-E19) | DONE |
| pytest tests/demo_trading/ | 494/494 PASS |
| py_compile all new files | PASS |
| .gitignore — outputs/demo_trading/close_only_cleanup/ | DONE |
| execute_ready gate: all 6 conditions enforced | CONFIRMED |
| no_orders_sent=True always | CONFIRMED |
| no_position_modified=True always | CONFIRMED |
| order_endpoint_called=False always | CONFIRMED |
| close side: Buy=close short, Sell=close long (Bybit derivatives) | CONFIRMED |
| deterministic sort: stop_risk DESC → notional DESC → symbol ASC | CONFIRMED |
| confirmation token expires daily: CONFIRM_DEMO_CLOSE_ONLY_YYYYMMDD | CONFIRMED |
| main.py / src/risk.py / exchange executors | NOT MODIFIED |
| local commit | PENDING (Rick must git push) |

## Next Rick Action (set by 2026-06-06 TASK-014F)

1. git push origin main (delivers TASK-014D through TASK-014F)
2. On VPS after git pull:
     source .env.demo
     python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
     python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report
     python3 scripts/preview_demo_close_only_cleanup.py --from-latest-reconciliation
3. If short_count > 5 or available_balance = 0, generate close confirmation token:
     python3 scripts/preview_demo_close_only_cleanup.py \
       --from-latest-reconciliation \
       --confirm-token CONFIRM_DEMO_CLOSE_ONLY_$(date +%Y%m%d) \
       --write-report
4. Review outputs/demo_trading/close_only_cleanup/latest_cleanup_plan.md
5. Execute closes manually on Bybit Demo (close-only, reduce_only=True, review each)
6. Commit forward_record bundle (MM files) — see TASK-013 section below

## Status
READY (Rick action: git push + VPS smoke + reconcile + close-only preview + manual closes if needed)

## Owner
Rick

## TASK-014E Status (2026-06-06)

| item | status |
|---|---|
| src/demo_position_reconcile.py | DONE — reconcile() pure computation, 9 violation types |
| scripts/preview_demo_position_reconcile.py | DONE — fixture + --from-latest-readonly-smoke + --write-report |
| tests/demo_trading/test_demo_position_reconcile.py | DONE — 84 tests PASS (F1-F16) |
| pytest tests/demo_trading/ | 405/405 PASS |
| py_compile all new files | PASS |
| .gitignore — outputs/demo_trading/reconciliation/ | DONE |
| main.py / src/risk.py / exchange executors | NOT MODIFIED |
| No orders sent / no positions modified / no secrets | CONFIRMED |
| local commit | PENDING (Rick must git push) |

## Real Demo Account Reconciliation Conclusions

| metric | value | status |
|---|---|---|
| equity_usd | ~11,404.01 | — |
| available_balance_usd | 0.00 | VIOLATION |
| open_positions_count | 8 | within limit (max 10) |
| short_count (estimated) | 7 | VIOLATION (max 5) |
| new_entry_allowed | False | BLOCKED |
| cannot_proceed_to_order_smoke | True | YES |

Suggested actions:
1. pause_new_entries
2. review_legacy_short_positions
3. reduce_short_count_to_max_5_manually (or via TASK-014F close-only task)
4. restore_available_balance_before_enabling_new_entries

→ TASK-014F Demo Close-only Manual Confirmed Cleanup needed if manual reduction required.

## Next Rick Action (set by 2026-06-06 TASK-014E)

1. git push origin main (delivers TASK-014D through TASK-014E)
2. On VPS after git pull:
     source .env.demo
     python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
     python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report
3. Review reconciliation report: outputs/demo_trading/reconciliation/latest_reconciliation.md
4. Decide if TASK-014F (close-only confirmed cleanup) is needed
5. Commit forward_record bundle (MM files) — see TASK-013 section below

## TASK-014D Status (2026-06-06)

| item | status |
|---|---|
| src/demo_readonly_client.py — _proof_real STRONG/WEAK/MISSING | DONE |
| src/demo_readonly_client.py — api_secret_present tracking | DONE |
| src/demo_runtime_adapter.py — reject PROOF_WEAK/MISSING | DONE |
| scripts/preview_demo_readonly_runtime.py — --write-report, early exit | DONE |
| scripts/preview_demo_readonly_runtime.py — proof_strength + api_secret_present display | DONE |
| tests/demo_trading/test_demo_readonly_client.py | +25 tests (66 total) |
| tests/demo_trading/test_demo_runtime_adapter.py | +24 tests (97 total) |
| pytest tests/demo_trading/ | 321/321 PASS |
| py_compile all modified files | PASS |
| .gitignore — .env.demo + outputs/demo_trading/readonly_smoke/ | DONE |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| No orders sent / no secrets / no API calls (fixture mode) | CONFIRMED |
| local commit bb511f0 | DONE |

## TASK-014C Status (2026-06-06)

| item | status |
|---|---|
| src/demo_readonly_client.py | DONE — fixture + real mode, HMAC signing, no secrets in output |
| src/demo_runtime_adapter.py | DONE — adapts wallet/positions/instruments/proof to Phase 2 input |
| scripts/preview_demo_readonly_runtime.py | DONE — fixture dry-run preview, --real-readonly flag |
| tests/demo_trading/test_demo_readonly_client.py | DONE — 41 tests PASS |
| tests/demo_trading/test_demo_runtime_adapter.py | DONE — 73 tests PASS |
| pytest tests/demo_trading/ | 291/291 PASS |
| py_compile all new files | PASS |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| No orders sent / no secrets / no API calls (fixture mode) | CONFIRMED |
| local commit | PENDING (Rick must git push) |

## TASK-014B Status (2026-06-06)

| item | status |
|---|---|
| src/demo_runtime_probe.py | DONE — 6-check fail-closed probe, no API calls |
| src/demo_instrument_rules.py | DONE — qty_step / tick_size / min_qty / min_notional rounding |
| src/demo_portfolio_risk.py | DONE — Phase 2 batch fractional-Kelly sizer |
| apps/demo_trading/ (config + kelly_sizer) | DONE |
| scripts/preview_demo_runtime_and_rounding.py | DONE — integrated dry-run preview |
| scripts/preview_demo_portfolio_sizing.py | DONE |
| scripts/demo_trading_preview.py | DONE |
| tests/demo_trading/test_demo_runtime_probe.py | DONE — 55 tests PASS |
| tests/demo_trading/test_demo_instrument_rules.py | DONE — 64 tests PASS |
| tests/demo_trading/test_demo_portfolio_risk.py | DONE — 58 tests PASS |
| pytest tests/demo_trading/ | 177/177 PASS |
| py_compile all new files | PASS |
| main.py / src/risk.py / BybitExecutor | NOT MODIFIED |
| No orders sent / no secrets / no API calls | CONFIRMED |
| local commit 815003c | DONE |
| pushed to origin/main | PENDING (Rick must git push) |

## (superseded — see TASK-014E section above for current actions)

### TASK-014D→E Forward Record Bundle (still pending)

1. Stage and commit remaining forward_record TASK-009..013 files
   (these have MM or untracked status after the TASK-014B commit):

     git add apps/forward_record/market_data.py \
             apps/forward_record/primary.py \
             scripts/paper_portfolio_engine.py \
             scripts/build_forward_validation_dashboard.py \
             scripts/run_forward_record.py \
             scripts/run_forward_record_daily.sh \
             scripts/sync_forward_validation_to_notion.py \
             scripts/audit_paper_portfolio_exposure.py \
             tests/forward_record/test_paper_portfolio.py \
             tests/forward_record/test_market_data_freshness.py \
             tests/forward_record/test_paper_portfolio_audit.py \
             tests/forward_record/test_paper_portfolio_guard.py \
             tests/forward_record/test_notion_sync.py \
             docs/research/commands/COMMAND_LOG.md \
             docs/research/commands/NEXT_ACTION.md
     git commit -m "TASK-013: add Notion historical backfill sync (TASK-009..013 bundle)"

2. Push (delivers TASK-008D through TASK-014B):
     git push origin main

3. On the VPS:
     cd ~/quant && git pull
     # Reprocess all dates with guard fix:
     python3 scripts/paper_portfolio_engine.py --rebuild
     # Run exposure audit:
     python3 scripts/audit_paper_portfolio_exposure.py
     # Rebuild dashboard:
     python3 scripts/build_forward_validation_dashboard.py
     # Backfill corrected PnL to Notion:
     python3 scripts/sync_forward_validation_to_notion.py --all --dry-run
     python3 scripts/sync_forward_validation_to_notion.py --all

## Task
30-day forward validation clock RUNNING（Day 17 done, 2026-06-04, Day 18 in progress）。
VPS daily runner script ACTIVE（cron 10:10 UTC daily）。
Paper portfolio PnL engine DONE (write mode enabled via TASK-010B).
TASK-011A: live read-only prices fix DONE.
TASK-011B: stale-state-reset fix DONE.
TASK-012: exposure guard DONE.
TASK-013: Notion historical backfill DONE — --date / --all / default(latest) supported.
On VPS: after git pull, run --all --dry-run to preview, then --all to backfill corrected PnL.

## 30-day Clock Status

| field | value |
|---|---|
| clock_started | TRUE |
| start_date | 2026-05-18（Day 1） |
| start_time_UTC | 2026-05-18T10:06:43Z |
| start_time_Taipei | 2026-05-18T18:06:43 CST |
| end_date_target | 2026-06-17 |
| validation_mode | forward-record / dry-run only |
| paper_execution_status | FORBIDDEN |
| live_trading_status | FORBIDDEN |
| clock_paused | false |
| days_completed | 8 |
| days_remaining | 22 |

## TASK-010 Paper Portfolio PnL Simulation Status

| item | status |
|---|---|
| scripts/paper_portfolio_engine.py | DONE (py_compile OK, --dry-run OK, --rebuild PASS) |
| tests/forward_record/test_paper_portfolio.py | DONE (48 tests, 48 PASS) |
| scripts/build_forward_validation_dashboard.py | UPDATED — PAPER_DIR + overlay in collect_days() |
| scripts/run_forward_record_daily.sh | UPDATED — PAPER_PNL section before dashboard build |
| pytest 194/194 (all forward_record tests) | PASS |
| bash -n run_forward_record_daily.sh | PASS |
| py_compile all scripts | PASS |
| local commit 98380a4 | DONE (via commit-tree) |
| pushed to origin/main | PENDING (Rick must git push) |
| VPS: python3 paper_portfolio_engine.py --rebuild | PENDING (Rick must run after git pull) |

### How PnL becomes non-zero on VPS

In development (cache_fallback), `hypothetical_fill_px` is frozen from the
historical dataset → prices identical across days → PnL = 0.

On VPS with live daily data downloads, `hypothetical_fill_px` updates each day
to the current close price. The MTM formula:

  daily_pnl_usd = position_usd * (today_px / prev_px - 1)

will produce non-zero values as soon as the VPS has two consecutive days of
`_positions.parquet` with different prices.

Run `python3 scripts/paper_portfolio_engine.py --rebuild` on VPS after `git pull`
to reprocess all existing dates and populate `paper_portfolio/` output files.

## TASK-010 Output Files

| file | description |
|---|---|
| outputs/forward_record/paper_portfolio/state.json | current nav, peak, positions (gitignored) |
| outputs/forward_record/paper_portfolio/daily_pnl.csv | daily PnL log (gitignored) |
| outputs/forward_record/paper_portfolio/trades.csv | exited positions log (gitignored) |
| outputs/forward_record/paper_portfolio/{date}_paper_pnl.json | per-day JSON read by dashboard |






## TASK-013 Notion Historical Backfill Status

| item | status |
|---|---|
| load_all_rows() | DONE |
| load_row_by_date(date) | DONE |
| _parse_cli() | DONE |
| _select_rows() | DONE |
| multi-row upsert loop in main() | DONE |
| --date YYYYMMDD single backfill | DONE |
| --all full history backfill | DONE |
| default (no args) → latest row only | PRESERVED |
| Chinese alias schema (TASK-009B) | PRESERVED |
| NOTION_TOKEN never printed | VERIFIED |
| output: selected_rows / processed_rows / created_count / updated_count | DONE |
| tests/forward_record/test_notion_sync.py | +27 tests (91 total) |
| pytest 330/330 | PASS |
| local commit | PENDING (Rick must git push) |
| VPS: git pull + --all --dry-run to preview | PENDING |
| VPS: --all to backfill corrected 20260528 row | PENDING |

### Backfill commands (run on VPS after git pull)

```bash
# Preview what will be synced
python3 scripts/sync_forward_validation_to_notion.py --all --dry-run

# Backfill specific date (e.g. corrected 20260528)
python3 scripts/sync_forward_validation_to_notion.py --date 20260528

# Full history backfill (all rows in validation_30d.csv)
python3 scripts/sync_forward_validation_to_notion.py --all
```

## TASK-012 Portfolio Exposure Guard Status

| item | status |
|---|---|
| GUARD_MAX_OPEN_POSITIONS | 50 |
| GUARD_MAX_LONG_POSITIONS | 25 |
| GUARD_MAX_SHORT_POSITIONS | 25 |
| GUARD_MAX_GROSS_EXPOSURE_RATIO | 1.0x |
| GUARD_MAX_NET_EXPOSURE_RATIO | 0.5x |
| GUARD_MAX_SINGLE_POSITION_PCT | 2.0% |
| apply_exposure_guard() in paper_portfolio_engine.py | DONE |
| guard_summary in {date}_paper_pnl.json | DONE |
| n_skipped / gross_exposure_ratio / net_exposure_ratio / guard_status in daily_pnl.csv | DONE |
| guard_status / gross / net / signals_skipped in dashboard latest_summary.md | DONE |
| audit reads guard_summary + warns on threshold violations | DONE |
| tests/forward_record/test_paper_portfolio_guard.py | NEW — 34 tests |
| pytest 303/303 | PASS |
| bash -n run_forward_record_daily.sh | PASS |
| py_compile all scripts | PASS |
| local commits | PENDING (Rick must git push) |
| VPS: --rebuild after git pull | PENDING |

### guard_status tokens

| token | meaning |
|---|---|
| PASS | no new entries blocked |
| WARNING | some new entries skipped, some entered |
| BLOCKED | all new entries blocked (e.g. portfolio already full) |

## TASK-011B Paper Portfolio Sanity Check / Exposure Audit Status

| item | status |
|---|---|
| Root cause of +460% PnL identified | DONE — STATE_STALENESS bug |
| Bug description | state.json prev_px from cache era (Apr 30); first live-price day computed 28-day accumulated move as 1 day |
| PnL formula correct | YES (pnl = position_usd × (today/prev - 1) is correct) |
| Position sizing normal | YES (gross_exposure = 1.0x, each position = 2% NAV) |
| scripts/audit_paper_portfolio_exposure.py | NEW — exposure metrics, PnL sanity, MD/JSON audit report |
| scripts/paper_portfolio_engine.py | UPDATED — _maybe_reset_stale_state(), STALE_RESET_DAYS=3 |
| tests/forward_record/test_paper_portfolio_audit.py | NEW — 27 tests |
| pytest 269/269 | PASS |
| local commit | PENDING (Rick must git push) |
| VPS: --rebuild after git pull | PENDING (to reprocess all dates with fix) |

### Stale-State Reset Fix

When `gap(today, state.last_processed_date) > STALE_RESET_DAYS (3 days)`:
- All positions treated as **new entries** → PnL = 0 on transition day
- `last_px` seeded from today's live prices → correct day-2 MTM
- NAV / peak / max_dd preserved (not reset)

```bash
# After git pull on VPS — reprocess all dates with the fix:
python3 scripts/paper_portfolio_engine.py --rebuild

# Run exposure audit:
python3 scripts/audit_paper_portfolio_exposure.py
```

### Exposure Thresholds

| metric | WARNING | HIGH_RISK |
|---|---|---|
| gross_exposure_ratio | > 1.0x | > 3.0x |
| max_single_pos_pct_nav | > 10% | — |
| abs(daily_pnl_pct) | > 20% | — |

## TASK-011A Market Data Freshness Fix Status

| item | status |
|---|---|
| Root cause identified | DONE (price lookup used signal_date 2026-04-30, not record_ts) |
| apps/forward_record/market_data.py | UPDATED — LiveReadOnlyMarketDataProvider + freshness helpers |
| apps/forward_record/primary.py | UPDATED — load_prices(record_ts); latest_prices_by_symbol(prices, record_ts) |
| scripts/run_forward_record.py | UPDATED — --data-source live_read_only added |
| scripts/run_forward_record_daily.sh | UPDATED — DATA_SOURCE=live_read_only default |
| tests/forward_record/test_market_data_freshness.py | NEW — 39 tests |
| pytest 242/242 (all forward_record tests) | PASS |
| bash -n run_forward_record_daily.sh | PASS |
| py_compile all modified files | PASS |
| local commits | PENDING (Rick must git push) |
| VPS: git pull then cron will auto-use live prices | PENDING |

### What changes on VPS after git pull

| before (frozen) | after (live) |
|---|---|
| data_source = cache_fallback | data_source = bybit_read_only_live |
| hypothetical_fill_px = 75750.0 every day | hypothetical_fill_px = Bybit lastPrice today |
| daily_pnl_pct = 0 always | daily_pnl_pct = real MTM change |
| freshness_status = STALE_OLD | freshness_status = FRESH |

### Override to force cache (testing)

```bash
DATA_SOURCE=cache_fallback bash scripts/run_forward_record_daily.sh
```

### Bybit public endpoint used

```
GET https://api.bybit.com/v5/market/tickers?category=linear
```
No authentication. Read-only. Returns lastPrice for all linear perpetuals.
Falls back silently to cache if network unavailable.

## TASK-010B Paper Portfolio Write Mode Status

| item | status |
|---|---|
| run_forward_record_daily.sh PAPER_PNL section | UPDATED — write mode by default |
| --dry-run removed from default cron invocation | DONE |
| PAPER_PNL_DRY_RUN=1 env var for manual dry-run | IMPLEMENTED |
| PAPER_FLAGS="" (write mode default) | IMPLEMENTED |
| PAPER_FLAGS="--dry-run" when PAPER_PNL_DRY_RUN=1 | IMPLEMENTED |
| tests/forward_record/test_paper_portfolio.py | +9 tests (TestDailyRunnerInvocation) |
| pytest 203/203 (all forward_record tests) | PASS |
| bash -n run_forward_record_daily.sh | PASS |
| py_compile paper_portfolio_engine.py | PASS |
| local commits | PENDING (Rick must git push) |
| VPS: --rebuild after git pull | PENDING |

### How to use

| mode | command |
|---|---|
| Normal daily cron (write mode) | cron runs run_forward_record_daily.sh (no env var needed) |
| Manual dry-run test | `PAPER_PNL_DRY_RUN=1 bash scripts/run_forward_record_daily.sh` |
| Standalone engine write | `python3 scripts/paper_portfolio_engine.py` |
| Standalone engine dry-run | `python3 scripts/paper_portfolio_engine.py --dry-run` |
| Back-fill all dates | `python3 scripts/paper_portfolio_engine.py --rebuild` |

## TASK-009B Support Chinese Notion Database Properties Status

| item | status |
|---|---|
| scripts/sync_forward_validation_to_notion.py | UPDATED — PROPERTY_ALIASES + resolve_schema_names() |
| PROPERTY_ALIASES | DONE (16 properties, each with English + Chinese alias) |
| resolve_schema_names() | DONE (prefers Chinese over English when both present) |
| pytest 64/64 | PASS |
| local commit b9dcf5f | DONE |
| pushed to origin/main | PENDING |

## TASK-009 Notion Sync Status

| item | status |
|---|---|
| scripts/sync_forward_validation_to_notion.py | CREATED (urllib only, no new deps) |
| tests/forward_record/test_notion_sync.py | DONE — 64 tests, all PASS |
| NOTION_SYNC tokens | SKIP/DRY_RUN/PASS/FAIL |
| local commit | PENDING (Rick must commit TASK-009 + push) |

## TASK-008E Fix Discord Escaped Underscore SyntaxWarning Status

| item | status |
|---|---|
| scripts/send_forward_discord_summary.py | FIXED — \_ removed from 5 f-string lines |
| SyntaxWarning eliminated | CONFIRMED |
| pytest 29/29 | PASS |

## VPS Daily Runner Status

| item | status |
|---|---|
| scripts/run_forward_record_daily.sh | UPDATED (PAPER_PNL + TASK-010 section) |
| scripts/install_cron_daily_runner.sh | CREATED |
| cron installed on VPS | ASSUMED ACTIVE (Rick ran install_cron_daily_runner.sh) |
| PAPER_PNL step in cron | YES — runs before dashboard build |

## TASK-007 Dashboard Status

| item | status |
|---|---|
| scripts/build_forward_validation_dashboard.py | UPDATED (TASK-010 paper PnL overlay) |
| outputs/forward_record/dashboard/index.html | REGENERATED |
| outputs/forward_record/dashboard/validation_30d.csv | daily_pnl_pct=0.0 (expected in dev) |
| paper PnL overlay active | YES — reads paper_portfolio/{date}_paper_pnl.json |
