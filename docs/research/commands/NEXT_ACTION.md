# Next Action

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
