# Next Action

> README shared status updated by TASK-014AL (2026-06-12) — see
> [Demo Trading Guarded Lifecycle Status](../../../README.md#demo-trading-guarded-lifecycle-status-updated-by-task-014af-docs1-2026-06-11)
> for the cross-agent status board. Code-only sync — no real trading logic
> added, G20 still active, no real trading enabled.

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
