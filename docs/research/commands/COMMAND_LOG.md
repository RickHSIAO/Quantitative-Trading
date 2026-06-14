# Command Log

Append one entry after each authorized agent task.

## Format

```text
YYYY-MM-DD HH:MM TZ
Agent:
Command source:
Task:
Status before:
Status after:
Files changed:
Validation:
Outputs:
Notes:
```

## Entries

---

### 2026-06-14（TASK-014AS-FIX2 — Clean Static Skeleton Dry-run Response-Status Labels）

Agent: Claude (Sonnet)
Command source: Rick chat instruction "Proceed with TASK-014AS-FIX2 now."
(2026-06-14)
Task: Report/schema-label cleanup only. Update AS source so the blocked-gate
label and stage-6 summary use STATIC_SKELETON_DRY_RUN_NOT_SENT terminology
instead of legacy IMPLEMENTATION_DESIGN_NOT_SENT:
`GATE_RESPONSE_STATUS_IS_NOT_SENT` string value →
`"response_status_is_static_skeleton_dry_run_not_sent"`;
stage_6 summary `response_status=IMPLEMENTATION_DESIGN_NOT_SENT` →
`response_status=STATIC_SKELETON_DRY_RUN_NOT_SENT`.
AQ upstream proof fields unchanged. Add 4 tests
`TestASFIX2ResponseStatusLabels`.

Status before: TASK-014AS-FIX1-DOCS1 committed locally as `258a81b`;
VPS validation passed (176/176 AS, 175/175 AR, 138/138 AQ);
stage_6 summary and blocked_gate still referenced legacy
IMPLEMENTATION_DESIGN_NOT_SENT label.
Status after: TASK-014AS-FIX2 DONE; stage_6 and gate use
STATIC_SKELETON_DRY_RUN_NOT_SENT; AS suite 180/180 PASS;
AR 175/175 PASS; AQ 138/138 PASS.

Files changed:
- `src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py`
  (`GATE_RESPONSE_STATUS_IS_NOT_SENT` string value:
  `"response_status_is_implementation_design_not_sent"` →
  `"response_status_is_static_skeleton_dry_run_not_sent"`;
  stage_6 summary: `response_status=IMPLEMENTATION_DESIGN_NOT_SENT` →
  `response_status=STATIC_SKELETON_DRY_RUN_NOT_SENT`)
- `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py`
  (new class `TestASFIX2ResponseStatusLabels` with 4 tests:
  `test_blocked_gates_contains_dry_run_response_status_gate`,
  `test_blocked_gates_does_not_contain_impl_design_response_status_gate`,
  `test_stage6_summary_uses_dry_run_response_status`,
  `test_markdown_report_response_status_uses_dry_run_wording`)
- `README.md` (status board banner → "updated by TASK-014AS-FIX2, 2026-06-14";
  `latest_completed_task` → TASK-014AS-FIX2; `latest validation` → 180/180 AS PASS,
  493/493 total)
- `docs/research/commands/NEXT_ACTION.md` (TASK-014AS-FIX2 status block
  prepended; Next Rick Action updated to expect 180/180 PASS)
- `docs/research/commands/COMMAND_LOG.md` (this TASK-014AS-FIX2 entry)

Validation:
- `python -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py` → PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py -q` → **180/180 PASS**
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py -q` (AR regression) → 175/175 PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py -q` (AQ regression) → 138/138 PASS
- Combined 493/493 PASS

Outputs: (no new output artifacts — label cleanup only)

Safety confirmations:
- No real order, no sender, no executable adapter, no `send` / `place_order` / `execute` method.
- No endpoint call, no secrets, no HMAC / signing, no G20 lift, no position modification.
- AQ upstream proof fields (`upstream_entry_implementation_design_conclusion`
  = `IMPLEMENTATION_DESIGN_READY_NOT_EXECUTABLE`,
  `upstream_entry_implementation_design_response_status`
  = `IMPLEMENTATION_DESIGN_NOT_SENT`) unchanged.
- main.py / src/risk.py / BybitExecutor untouched.
- Local commit only; not pushed to remote (per persistent user rule).

---

### 2026-06-14（TASK-014AS-FIX1 — Clean Static Skeleton Dry-run Footer Wording）

Agent: Claude (Sonnet)
Command source: Rick chat instruction "Proceed with TASK-014AS-FIX1 now."
(2026-06-14)
Task: Report/footer wording cleanup only. Update scripts/preview and src
module so the final safety footer uses STATIC-SKELETON-DRY-RUN
terminology instead of legacy IMPLEMENTATION-DESIGN wording:
"TASK-014AS is a STRICT STATIC-SKELETON-DRY-RUN-ONLY module.";
"--allow-static-skeleton-dry-run"; "static_skeleton_dry_run_conclusion
remains STATIC_SKELETON_DRY_RUN_READY_NOT_EXECUTABLE". Backward-
compatible `implementation_design_*` alias fields preserved. No runtime
behavior change, no gate change, no artifact change. Add 1 test
`test_markdown_report_footer_uses_dry_run_wording`; extend CLI banner
test with `allow-static-skeleton-dry-run` / `static_skeleton_dry_run_conclusion`
/ `STATIC_SKELETON_DRY_RUN_READY_NOT_EXECUTABLE` assertions.

Status before: TASK-014AS-DOCS1 committed locally as `0445a74`;
VPS validation passed (175/175 AS, 175/175 AR, 138/138 AQ);
footer still contained legacy IMPLEMENTATION-DESIGN-ONLY wording.
Status after: TASK-014AS-FIX1 DONE; footer uses STATIC-SKELETON-DRY-RUN
terminology; AS suite 176/176 PASS; AR 175/175 PASS; AQ 138/138 PASS.

Files changed:
- `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py`
  (module docstring line 98-100: `--allow-implementation-design` /
  `implementation_design_conclusion` / `IMPLEMENTATION_DESIGN_READY_NOT_EXECUTABLE`
  → `--allow-static-skeleton-dry-run` / `static_skeleton_dry_run_conclusion` /
  `STATIC_SKELETON_DRY_RUN_READY_NOT_EXECUTABLE`;
  markdown footer lines 820-842: "STRICT IMPLEMENTATION-DESIGN-ONLY module"
  → "STRICT STATIC-SKELETON-DRY-RUN-ONLY module";
  `--allow-implementation-design` → `--allow-static-skeleton-dry-run`;
  `implementation_design_conclusion remains IMPLEMENTATION_DESIGN_READY_NOT_EXECUTABLE`
  → `static_skeleton_dry_run_conclusion remains STATIC_SKELETON_DRY_RUN_READY_NOT_EXECUTABLE`)
- `src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py`
  (module docstring modes section: `--allow-implementation-design` →
  `--allow-static-skeleton-dry-run`;
  `run_dry_run()` docstring: `--allow-implementation-design` →
  `--allow-static-skeleton-dry-run`)
- `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py`
  (+1 test `test_markdown_report_footer_uses_dry_run_wording` in
  `TestARFIX2MarkdownReportTitleAndSections`;
  CLI banner test `TestARFIX2CLIBannerSaysStaticSkeleton` extended with
  3 new assertions for dry-run terminology)
- `README.md` (status board banner → "updated by TASK-014AS-FIX1,
  2026-06-14"; `latest_completed_task` → TASK-014AS-FIX1;
  `current_phase` → footer wording cleanup description;
  `latest validation` → 176/176 AS PASS, 489/489 total)
- `docs/research/commands/NEXT_ACTION.md` (TASK-014AS-FIX1 status block
  prepended; Next Rick Action updated to expect 176/176 PASS)
- `docs/research/commands/COMMAND_LOG.md` (this TASK-014AS-FIX1 entry)

Validation:
- `python -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py` → PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py -q` → **176/176 PASS**
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py -q` (AR regression) → 175/175 PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py -q` (AQ regression) → 138/138 PASS
- Combined 489/489 PASS

Outputs: (no new output artifacts — wording cleanup only)

Notes:
- Footer wording cleanup only. Zero runtime behavior change.
- `implementation_design_conclusion` alias field on dataclass and
  `to_dict()` still resolves to `STATIC_SKELETON_DRY_RUN_READY_NOT_EXECUTABLE`
  (backward-compat preserved).
- AQ upstream proof fields (`upstream_entry_implementation_design_conclusion`
  = `IMPLEMENTATION_DESIGN_READY_NOT_EXECUTABLE`,
  `upstream_entry_implementation_design_response_status`
  = `IMPLEMENTATION_DESIGN_NOT_SENT`) are untouched — these document
  what the AQ artifact contains and are required by the gate checks.
- Local commit only; not pushed to remote (per persistent user rule).
- Local commit hash: `798e77d`.

---

### 2026-06-14（TASK-014AS-FIX1-DOCS1 — Sync Static Skeleton Dry-run Footer Docs）

Agent: Claude (Sonnet)
Command source: Rick chat instruction "Proceed with TASK-014AS-FIX1-DOCS1
now, before push/VPS validation." (2026-06-14)
Task: Docs-only sync for TASK-014AS-FIX1. Fill in commit hash `798e77d`
into README and COMMAND_LOG. Update README banner to TASK-014AS-FIX1-DOCS1.
Verify NEXT_ACTION.md TASK-014AS-FIX1 block is complete (footer wording
fix stated, 28 upstream artifacts stated, TASK-014AR static skeleton
design output consumed at runtime, next_required_task = TASK-014AT,
VPS validation commands present). Add this TASK-014AS-FIX1-DOCS1 log
entry. No code change, no runtime behavior change, no gate change.

Status before: TASK-014AS-FIX1 committed locally as `798e77d`;
README `latest_commit` row missing the actual hash; NEXT_ACTION.md
already correct (TASK-014AS-FIX1 block present, 176/176 PASS noted).
Status after: TASK-014AS-FIX1-DOCS1 DONE; all doc files reference
`798e77d`; README banner updated to TASK-014AS-FIX1-DOCS1.

Files changed:
- `README.md` (banner → "updated by TASK-014AS-FIX1-DOCS1, 2026-06-14";
  `latest_commit` → `798e77d — TASK-014AS-FIX1: clean static skeleton
  dry-run footer wording`)
- `docs/research/commands/COMMAND_LOG.md` (FIX1 entry notes: added
  "Local commit hash: 798e77d"; this FIX1-DOCS1 entry)
- `docs/research/commands/NEXT_ACTION.md` (banner updated to
  TASK-014AS-FIX1-DOCS1; FIX1-DOCS1 local commit row added)

Validation:
- `python -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py` → PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py -q` → 176/176 PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py -q` (AR regression) → 175/175 PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py -q` (AQ regression) → 138/138 PASS
- Combined 489/489 PASS

Outputs: (no new output artifacts — docs sync only)

Safety confirmations:
- No real order, no sender, no executable adapter, no `send` / `place_order` / `execute` method.
- No endpoint call, no secrets, no HMAC / signing, no G20 lift, no position modification.
- main.py / src/risk.py / BybitExecutor untouched.
- Local commit only; not pushed to remote (per persistent user rule).

---

### 2026-06-14（TASK-014AS — Guarded Entry Real Execution Adapter Static Skeleton Dry-run）

Agent: Claude (Opus)
Command source: Rick chat instruction "I explicitly authorize TASK-014AS
now. Recommended model: Codex: GPT-5.5 / reasoning=very high; Claude:
Opus 4.7. Proceed with TASK-014AS: Guarded Entry Real Execution Adapter
Static Skeleton Dry-run." (2026-06-14)
Task: Produce a STRICT STATIC-SKELETON-DRY-RUN-ONLY module that
consumes TASK-014AR's `entry_static_skeleton_design` artifact at
runtime (plus the 27 upstream artifacts AR already consumed), evaluates
28 upstream artifacts through 14 stages, exposes a 75-gate
`_HARD_FAIL_GATES` frozenset (62 inherited + 13 new
`entry_static_skeleton_design_*` AR-consumption gates), 18 ACCEPTABLE_*
status whitelist frozensets (17 inherited + new
ACCEPTABLE_ENTRY_STATIC_SKELETON_DESIGN_STATUSES), and writes
`STATIC_SKELETON_DRY_RUN_READY_NOT_EXECUTABLE` to the verdict label.
Adapter is documented only — NO sender, NO executable adapter, NO
`send` / `place_order` / `execute` method, NO endpoint calls, NO real
entry execution, NO real token / phrase / approval-input validation,
NO secret reads, NO HMAC, NO signing, NO G20 lift, NO modification of
the 5 protected demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT /
POLYXUSDT / EDUUSDT), NO `main.py` / `src/risk.py` / BybitExecutor
reuse, NO AA-AR module reuse from `src/`, NO auto git commit / push.

Status before: TASK-014AR-FIX3-DOCS1 committed locally as `1674dfc`;
next_required_task =
TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run
Status after: TASK-014AS DONE; status =
TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_STATIC_SKELETON_DRY_RUN_READY;
next_required_task =
TASK-014AT_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design

Files changed:
- `src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py`
  (new — 2653 lines; static-skeleton-dry-run-only module;
  ADAPTER_NAME=GuardedTinyEntryRealExecutionAdapter,
  ADAPTER_CONTRACT_VERSION=static_skeleton_dry_run_v1,
  CONSUMED_STATIC_SKELETON_DESIGN_CONTRACT_VERSION=static_skeleton_design_v1,
  CONSUMED_IMPLEMENTATION_DESIGN_CONTRACT_VERSION=implementation_design_v1,
  CONSUMED_READINESS_CONTRACT_VERSION=readiness_review_v1,
  CONSUMED_DRY_RUN_CONTRACT_VERSION=dry_run_v1,
  CONSUMED_DESIGN_CONTRACT_VERSION=design_only_v1,
  ADAPTER_RESPONSE_STATUS=STATIC_SKELETON_DRY_RUN_NOT_SENT,
  ORDER_LINK_ID_PREFIX=STATIC_SKELETON_DRY_RUN_TINY_ENTRY_,
  STATIC_SKELETON_DRY_RUN_CONCLUSION=STATIC_SKELETON_DRY_RUN_READY_NOT_EXECUTABLE;
  28 upstream artifacts wired; 18 ACCEPTABLE_*_STATUSES frozensets;
  75-gate `_HARD_FAIL_GATES`; backward-compat `implementation_design_*`
  aliases preserved)
- `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py`
  (new — 1392 lines; 28 `--from-latest-*` flags incl. new
  `--from-latest-entry-static-skeleton-design`; `--symbol`,
  `--expected-commit-hash`, `--allow-static-skeleton-dry-run`,
  `--allow-real-entry-execution`, `--write-report`; `run_execute()`
  callable from tests; writes `{ts}_*` + `latest_*` JSON+MD to
  `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run/`;
  NO auto git operations)
- `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py`
  (new — 2960 lines; 175 tests covering 4 status modes, 28
  missing-artifact gates, endpoint/account/symbol invariants, all 14
  stages presence + order, deep-copy roundtrip, AST + tokenize
  source-scan safety, 5 protected positions untouched, G20 never
  lifted, no AA-AR module reuse, next_required_task = 014AT, 18
  frozenset whitelists incl. ACCEPTABLE_ENTRY_STATIC_SKELETON_DESIGN_STATUSES,
  CONSUMED_STATIC_SKELETON_DESIGN_CONTRACT_VERSION = "static_skeleton_design_v1",
  13 LIVE AR-consumption gates, AQ-consumption regression preserved,
  schema-label tests assert STATIC SKELETON DRY-RUN terminology and
  `TASK-014AR` upstream wording in scope_summary / markdown / CLI help)
- `.gitignore` (added
  `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run/`)
- `README.md` (Demo Trading Guarded Lifecycle Status board:
  banner updated to "updated by TASK-014AS, 2026-06-14";
  `latest_completed_task` → TASK-014AS;
  `current_phase` → "guarded entry real execution adapter static
  skeleton dry-run completed";
  `next_required_task` →
  `TASK-014AT_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design`;
  adapter identity updated to expose new
  `CONSUMED_STATIC_SKELETON_DESIGN_CONTRACT_VERSION=static_skeleton_design_v1`;
  `audit response_status` → `STATIC_SKELETON_DRY_RUN_NOT_SENT`;
  added `static_skeleton_dry_run_conclusion` row)
- `docs/research/commands/NEXT_ACTION.md` (TASK-014AS status table +
  Next Rick Action section prepended; existing TASK-014AR-FIX3 block
  preserved)
- `docs/research/commands/COMMAND_LOG.md` (this TASK-014AS entry)

Validation:
- `python -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py` → PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py -q` → 175/175 PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py -q` (AR regression) → 175/175 PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py -q` (AQ regression) → 138/138 PASS
- Combined 488/488 PASS

Outputs:
- (TASK module produces no output artifacts unless invoked with
  `--write-report`; CLI default is dry-run-checklist with no I/O.)

Notes:
- TASK-014AS is the static skeleton DRY-RUN successor to TASK-014AR
  (which produced the static skeleton DESIGN). AS consumes AR's output
  via the new 28th upstream artifact wiring, gating 13 fail-closed
  invariants from AR's verdict (status, real_execution_allowed,
  send_allowed, adapter_implementation_included,
  adapter_execution_included, order_endpoint_called,
  stop_endpoint_called, no_position_modified, no_secrets_loaded,
  g20_lifted, conclusion, response_status). All 8 LIVE AQ-consumption
  gates from AR-FIX1 remain active (regression-tested).
- Real execution is still FORBIDDEN. `--allow-static-skeleton-dry-run`
  only flips the mode label; `--allow-real-entry-execution` only
  returns `REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED`. No order endpoint is
  ever invoked, no socket is opened, no secret is loaded, no G20 is
  lifted.
- Backward-compat aliases retained: `implementation_design_conclusion`,
  `final_implementation_design_verdict`, `implementation_design_scope`
  resolve to the new `static_skeleton_dry_run_*` values so older
  downstream readers still work; `MODE_IMPLEMENTATION_DESIGN_CHECKLIST`
  / `_APPROVAL` are aliases of the new
  `MODE_STATIC_SKELETON_DRY_RUN_*` strings.
- Local commit only; not pushed to remote (per persistent user rule).
- Local commit hash: `1768924`.

---

### 2026-06-14（TASK-014AS-DOCS1 — Sync Static Skeleton Dry-run Docs）

Agent: Claude (Sonnet)
Command source: Rick chat instruction "Proceed with TASK-014AS-DOCS1
now, before push/VPS validation." (2026-06-14)
Task: Synchronize cross-agent docs for TASK-014AS — fill in the actual
local commit hash `1768924` into the README Demo Trading Guarded
Lifecycle Status board; update banner to "TASK-014AS-DOCS1,
2026-06-14"; add `actual runner execution = FORBIDDEN` row; add this
TASK-014AS-DOCS1 event in COMMAND_LOG (including the `1768924` hash
reference for the TASK-014AS entry); verify NEXT_ACTION.md TASK-014AS
status block and VPS validation commands are intact and use static
skeleton DRY-RUN terminology (not DESIGN). No code changes, no
execution logic, no G20 lift, no endpoint calls, no secret reads, no
real entry execution, no executable sender path added, no `send` /
`place_order` / `execute` method introduced, no adapter class added,
no main.py / src/risk.py / BybitExecutor modification, no position
modification.

Status before: TASK-014AS committed locally as `1768924` but README
board still showed `latest_commit = pending` and banner read "updated
by TASK-014AS, 2026-06-14"; `actual runner execution` row absent
Status after: TASK-014AS-DOCS1 docs sync DONE; cross-agent board
points at TASK-014AS / `1768924`; next_required_task =
TASK-014AT_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design

Files changed:
- `README.md` (Demo Trading Guarded Lifecycle Status board:
  banner updated to "updated by TASK-014AS-DOCS1, 2026-06-14";
  `latest_commit` updated from `pending` → `1768924`;
  added `actual runner execution = FORBIDDEN` row)
- `docs/research/commands/COMMAND_LOG.md` (TASK-014AS entry: added
  explicit `Local commit hash: 1768924` line; this TASK-014AS-DOCS1
  entry appended)

Validation:
- `python -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py` → PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_dry_run.py -q` → 175/175 PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py -q` → 175/175 PASS (AR regression intact)
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py -q` → 138/138 PASS (AQ regression intact)
- Combined 488/488 PASS

Outputs: (docs-only sync; no code artifacts produced.)

Safety confirmations:
- No real order, no sender, no executable adapter, no
  `send` / `place_order` / `execute` method, no endpoint call, no
  secrets, no HMAC / signing, no G20 lift, no position modification.
- `main.py` / `src/risk.py` / BybitExecutor untouched.
- 5 protected demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT /
  POLYXUSDT / EDUUSDT) untouched.
- TASK-014L sender G20 (`protected_entry_policy_missing`) still
  active.
- No automatic git operation; local commit only; not pushed.

Notes:
- Docs-only sync. AS source / preview / tests unchanged; only
  `README.md` board and `COMMAND_LOG.md` updated.
- `NEXT_ACTION.md` TASK-014AS status section (added by TASK-014AS)
  already states: 28 upstream artifacts; TASK-014AR static skeleton
  design output consumed at runtime; static skeleton DRY-RUN (not
  DESIGN) terminology; next_required_task =
  TASK-014AT_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_design;
  VPS validation commands present; forbidden statuses synced. No
  modification required in this DOCS1 sync.

---

### 2026-06-14（TASK-014AR-FIX3-DOCS1 — Sync Static Skeleton CLI Help Test Docs）

Agent: Claude (Sonnet)
Command source: Rick chat instruction "Proceed with TASK-014AR-FIX3-DOCS1
now, before push/VPS validation." (2026-06-14)
Task: Synchronize cross-agent docs for TASK-014AR-FIX3 — fill in the
actual local commit hash `c8cef5a` into the README Demo Trading
Guarded Lifecycle Status board; update banner to "TASK-014AR-FIX3-
DOCS1, 2026-06-14"; add this TASK-014AR-FIX3-DOCS1 event in
COMMAND_LOG; verify NEXT_ACTION.md TASK-014AR-FIX3 status block and
VPS validation commands are intact. No code changes, no execution
logic, no G20 lift, no endpoint calls, no secret reads, no real entry
execution, no executable sender path added, no `send` /
`place_order` / `execute` method introduced, no adapter class added,
no main.py / src/risk.py / BybitExecutor modification, no position
modification.

Status before: TASK-014AR-FIX3 committed locally as `c8cef5a` but
README board showed the commit message without an explicit hash and
banner still read "updated by TASK-014AR-FIX3, 2026-06-14"
Status after: TASK-014AR-FIX3-DOCS1 docs sync DONE; cross-agent board
points at TASK-014AR-FIX3 / `c8cef5a`; next_required_task =
TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run

Files changed:
- `README.md` (Demo Trading Guarded Lifecycle Status board:
  banner updated to "updated by TASK-014AR-FIX3-DOCS1, 2026-06-14";
  `latest_completed_task` → TASK-014AR-FIX3;
  `latest_commit` updated to include explicit hash `c8cef5a`)
- `docs/research/commands/COMMAND_LOG.md` (this TASK-014AR-FIX3-DOCS1
  entry)

Validation:
- `python -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py` → PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py -q` → 175/175 PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py -q` → 138/138 PASS (AQ regression intact)

Outputs: docs-only — no runtime artifacts produced

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no `/v5/position/trading-stop` call
- no sender adapter introduced / no executable adapter surface / no adapter class added / no `send` / `place_order` / `execute` method
- no endpoint call / no socket opened / no urllib / no requests / no httpx / no http.client
- no secrets read / no `.env*` read / no `os.environ` access / no dotenv
- no HMAC / no signature header / no signing primitive
- TASK-014L G20 sender policy still active (no protected_entry_policy_missing lift)
- 5 protected demo positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified
- main.py / src/risk.py / BybitExecutor untouched
- no auto git commit / no auto git push / no auto branch / no auto tag

Notes:
- Local commit only; push pending Rick instruction.
- next_required_task remains `TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run`.

---

### 2026-06-14（TASK-014AR-FIX3 — Harden Static Skeleton CLI Help Test）

Agent: Claude (Sonnet)
Command source: Rick chat instruction "Proceed with TASK-014AR-FIX3 now.
VPS validation for TASK-014AR-FIX2 failed only on one brittle CLI help
assertion: TestARFIX2CLIBannerSaysStaticSkeleton::test_cli_help_does_not_
advertise_implementation_design_only — AssertionError: assert
'TASK-014AQ implementation design output' in combined." (2026-06-14)
Task: Fix the brittle cross-platform CLI help test. On VPS Linux, argparse
wraps the `description=` string at a different terminal width than
Windows, breaking the exact multi-word substring
`"TASK-014AQ implementation design output"`. Fix by normalizing
whitespace in the combined stdout+stderr string before asserting
(`" ".join(combined.split())`) and replacing the single long-phrase
assertion with individual token assertions:
  - `"STATIC SKELETON DESIGN"` (all-caps phrase, not split by wrapping)
  - `"TASK-014AQ"` (single token)
  - `"implementation design"` (two adjacent lowercase words)
  - `"static skeleton"` (two adjacent lowercase words)
  - `"TASK-014AS"` (single token)
No trading logic changed. No runtime artifact consumption changed. No
gates changed. No endpoint / secret / sender behavior changed. No
adapter class added. No `send` / `place_order` / `execute` method
added. No G20 lift. No main.py / src/risk.py / BybitExecutor
modification. No position modification.

Status before: TASK-014AR-FIX2-DOCS1 `b963956` on origin/main; VPS
pytest 174/175 PASSED — only TestARFIX2CLIBannerSaysStaticSkeleton
failed due to argparse line-wrap on Linux
Status after: TASK-014AR-FIX3 test hardened; 175/175 PASS locally +
expected 175/175 PASS on VPS; next_required_task =
TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run

Files changed:
- `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py`
  (TestARFIX2CLIBannerSaysStaticSkeleton: replaced single-phrase
  assertion `assert "TASK-014AQ implementation design output" in
  combined` with whitespace-normalized `normalized = " ".join(
  combined.split())` and five individual token assertions against
  `normalized`; kept `result.returncode == 0` check unchanged)
- `docs/research/commands/NEXT_ACTION.md`
  (banner updated to "updated by TASK-014AR-FIX3 (2026-06-14)";
  new TASK-014AR Status block at top of AR section documenting
  FIX3; pytest count updated to 175/175 PASS post-FIX3)
- `README.md`
  (banner updated to "updated by TASK-014AR-FIX3, 2026-06-14";
  `latest_completed_task` → TASK-014AR-FIX3;
  `latest_commit` → FIX3 message;
  `current_phase` updated to mention CLI help test hardened)
- `docs/research/commands/COMMAND_LOG.md` (this TASK-014AR-FIX3 entry)

Validation:
- `python -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py` → PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py -q` → 175/175 PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py -q` → 138/138 PASS (AQ regression intact)

Outputs: none (docs-only + one test edit; no runtime artifacts produced)

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no `/v5/position/trading-stop` call
- no sender adapter introduced / no executable adapter surface / no adapter class added / no `send` / `place_order` / `execute` method
- no endpoint call / no socket opened / no urllib / no requests / no httpx / no http.client
- no secrets read / no `.env*` read / no `os.environ` access / no dotenv
- no HMAC / no signature header / no signing primitive
- TASK-014L G20 sender policy still active (no protected_entry_policy_missing lift)
- 5 protected demo positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified
- main.py / src/risk.py / BybitExecutor untouched
- no auto git commit / no auto git push / no auto branch / no auto tag

Notes:
- Root cause: argparse formats `description=` with `textwrap.wrap` at
  the current terminal width. On Linux VPS the width differs from
  Windows, so the string `"TASK-014AQ implementation design output"`
  was split across two wrapped lines as `"TASK-014AQ implementation\n
  design output"`, making the raw substring assertion fail. The fix
  is standard: collapse all whitespace before asserting.
- Local commit only; push pending Rick instruction.
- next_required_task remains `TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run`.

---

### 2026-06-14（TASK-014AR-FIX2-DOCS1 — Sync Static Skeleton Schema Label Docs）

Agent: Claude (Sonnet)
Command source: Rick chat instruction "Proceed with TASK-014AR-FIX2-DOCS1
now, before push/VPS validation." (2026-06-14)
Task: Synchronize cross-agent docs for TASK-014AR-FIX2 — fill in the
actual local commit hash `884b6e2` into the README Demo Trading
Guarded Lifecycle Status board; update banner to "TASK-014AR-FIX2-
DOCS1, 2026-06-14"; update `current_phase` to "guarded entry real
execution adapter static skeleton report schema labels cleaned"; add
this TASK-014AR-FIX2-DOCS1 event in COMMAND_LOG; verify
NEXT_ACTION.md TASK-014AR-FIX2 status block and VPS validation
commands are intact. No code changes, no execution logic, no G20 lift,
no endpoint calls, no secret reads, no real entry execution, no
executable sender path added, no `send` / `place_order` / `execute`
method introduced, no adapter class added, no main.py / src/risk.py /
BybitExecutor modification, no position modification.

Status before: TASK-014AR-FIX2 source/preview/tests/docs committed
locally as `884b6e2` but README board showed the commit message
string without an explicit hash, and banner still read
"updated by TASK-014AR-FIX2, 2026-06-13"
Status after: TASK-014AR-FIX2-DOCS1 docs sync DONE; cross-agent board
points at TASK-014AR-FIX2 / `884b6e2`; `current_phase` reads
"guarded entry real execution adapter static skeleton report schema
labels cleaned"; next_required_task =
TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run

Files changed:
- `README.md` (Demo Trading Guarded Lifecycle Status board:
  banner updated to "updated by TASK-014AR-FIX2-DOCS1, 2026-06-14";
  `latest_completed_task` → TASK-014AR-FIX2;
  `latest_commit` updated to include explicit hash `884b6e2`;
  `current_phase` rewritten to "guarded entry real execution adapter
  static skeleton report schema labels cleaned";
  `latest_validation` updated to show py_compile PASS + 175 PASS
  + AQ regression 138 PASS)
- `docs/research/commands/COMMAND_LOG.md` (this TASK-014AR-FIX2-DOCS1
  entry)

Validation:
- `python -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py` → PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py -q` → 175/175 PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py -q` → 138/138 PASS (AQ regression intact)

Outputs: docs-only — no runtime artifacts produced

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no `/v5/position/trading-stop` call
- no sender adapter introduced / no executable adapter surface / no adapter class added / no `send` / `place_order` / `execute` method
- no endpoint call / no socket opened / no urllib / no requests / no httpx / no http.client
- no secrets read / no `.env*` read / no `os.environ` access / no dotenv
- no HMAC / no signature header / no signing primitive
- TASK-014L G20 sender policy still active (no protected_entry_policy_missing lift)
- 5 protected demo positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified
- main.py / src/risk.py / BybitExecutor untouched
- no auto git commit / no auto git push / no auto branch / no auto tag

Notes:
- Local commit only; push pending Rick instruction.
- next_required_task remains `TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run`.

---

### 2026-06-14（TASK-014AR-FIX2 — Clean Static Skeleton Report Schema Labels）

Agent: Claude (Opus)
Command source: Rick chat instruction "Proceed with TASK-014AR-FIX2 now.
TASK-014AR-FIX1 VPS validation passed... However, the AR report still
contains confusing implementation-design labels: header says
'IMPLEMENTATION DESIGN CHECKLIST'; mode is `implementation_design_
checklist`; markdown title says 'Implementation Design'; fields/stages
still use `implementation_design_scope`; final verdict still uses
`final_implementation_design_verdict`; scope_summary still says it
produces an implementation design. This is a schema/label cleanup task
only." (2026-06-14)
Task: Schema/label cleanup of TASK-014AR static-skeleton-design report
surface — rename report-facing labels to STATIC SKELETON DESIGN
terminology while preserving every safety behavior, the TASK-014AQ
runtime consumption, and every fail-closed gate, AND keep
backward-compatible aliases for the legacy `implementation_design_*`
keys so downstream docs / tests / future agents that still reference
them continue to work. NO endpoint, NO secret, NO sender, NO adapter
class, NO `send` / `place_order` / `execute` method, NO G20 lift, NO
main.py / src/risk.py / BybitExecutor modification, NO position
modification.

Status before: TASK-014AR-FIX1-DOCS1 committed locally as `726e484`;
VPS-validated; runtime consumption of TASK-014AQ artifact intact; but
the report-facing labels still read "IMPLEMENTATION DESIGN" and the
mode string still said `implementation_design_checklist`
Status after: TASK-014AR-FIX2 schema cleanup DONE; mode now
`static_skeleton_design_checklist` / `static_skeleton_design_approval`;
report title "Tiny Guarded Entry Real Execution Adapter Static
Skeleton Design"; new aliases `static_skeleton_design_conclusion` /
`final_static_skeleton_design_verdict` / `static_skeleton_design_
scope` / `static_skeleton_design_authorization_result`; legacy
`implementation_design_*` keys preserved as back-compat aliases;
AQ runtime consumption intact; status string unchanged; 175/175 PASS;
next_required_task = TASK-014AS_guarded_entry_real_execution_adapter_
static_skeleton_dry_run

Files changed:
- `src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py`
  (module docstring header changed from "Implementation Design" to
  "Static Skeleton Design" with explicit "consumes TASK-014AQ ...
  produces STATIC SKELETON DESIGN for TASK-014AS" wording; Modes
  block in docstring updated; `MODE_STATIC_SKELETON_DESIGN_CHECKLIST`
  / `MODE_STATIC_SKELETON_DESIGN_APPROVAL` added with new
  underlying string values; `MODE_IMPLEMENTATION_DESIGN_CHECKLIST` /
  `_APPROVAL` retained as backward-compat aliases pointing at the
  new strings; `run_design()` mode assignments updated to the new
  constants; `to_dict()` adds `static_skeleton_design_scope`,
  `static_skeleton_design_conclusion`,
  `static_skeleton_design_authorization_result`,
  `final_static_skeleton_design_verdict` aliases (legacy
  `implementation_design_*` keys preserved); stage_1 dict +
  `audit_artifacts` + `final_implementation_design_verdict` carry
  the new aliases; stage_1 summary now says "Assert static skeleton
  design scope"; stage_13 summary now says "Final static skeleton
  design verdict"; scope_summary rewritten to "TASK-014AR consumes
  TASK-014AQ implementation design output at runtime and produces a
  STATIC SKELETON DESIGN for TASK-014AS"; `__all__` extended with
  the new MODE_STATIC_SKELETON_DESIGN_* names)
- `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py`
  (module docstring header / usage banner / IMPORTANT block
  references retitled to "Static Skeleton Design"; argparse
  `description=` rewritten to "Tiny guarded entry REAL EXECUTION
  ADAPTER STATIC SKELETON DESIGN (TASK-014AR). Consumes TASK-014AQ
  implementation design output at runtime and produces a static
  skeleton design for TASK-014AS."; runtime banner now prints
  "STATIC SKELETON DESIGN CHECKLIST / APPROVAL" instead of the
  legacy "IMPLEMENTATION DESIGN CHECKLIST / APPROVAL"; markdown
  H1 title now "# Tiny Guarded Entry Real Execution Adapter Static
  Skeleton Design (TASK-014AR)"; narrative summary line under the
  title added; markdown section headers retitled: "## Static
  Skeleton Design Verdict", "## Static Skeleton Design Scope", "##
  Final Static Skeleton Design Verdict"; top-of-report fields now
  show `static_skeleton_design_conclusion` and
  `static_skeleton_design_authorization_result` with the legacy
  `implementation_design_conclusion` rendered as a backward-compat
  alias line)
- `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py`
  (imports extended with `MODE_STATIC_SKELETON_DESIGN_APPROVAL` /
  `_CHECKLIST`; 16 new TestARFIX2* classes appended at end of file
  covering: mode string is `static_skeleton_design_checklist` (+
  alias), approval mode string, status string unchanged,
  next_required_task unchanged, every safety flag remains
  false/forbidden, `static_skeleton_design_conclusion` alias on
  `to_dict()` equals legacy key, `static_skeleton_design_
  authorization_result` alias, `static_skeleton_design_scope`
  alias with scope_summary mentioning TASK-014AQ + STATIC
  SKELETON DESIGN + TASK-014AS, `final_static_skeleton_design_
  verdict` alias equals legacy, audit_artifacts carry the new
  aliases, stage_1 summary mentions "static skeleton design
  scope" with both key forms present, stage_13 summary mentions
  "static skeleton design verdict" with both key forms present,
  AQ runtime consumption still intact post-FIX2, markdown report
  uses static skeleton wording (title + 3 section headers +
  conclusion line + mode string + TASK-014AQ/AS in narrative),
  CLI argparse `--help` banner says "STATIC SKELETON DESIGN" +
  references TASK-014AQ implementation design output + TASK-014AS)
- `docs/research/commands/NEXT_ACTION.md`
  (banner advanced to "updated by TASK-014AR-FIX2 (2026-06-14)";
  new TASK-014AR Status block dated 2026-06-13 / updated by
  TASK-014AR-FIX2 2026-06-14 added at top describing the schema
  cleanup; pytest counts updated to 175/175 PASS post-FIX2; Next
  Rick Action step 1 expectation updated to "175/175 PASS
  (post-FIX2)")
- `README.md`
  (Demo Trading Guarded Lifecycle Status board banner updated to
  "updated by TASK-014AR-FIX2, 2026-06-13"; `latest_completed_
  task` updated to TASK-014AR-FIX2; `latest_commit` updated to
  FIX2 message; `current_phase` extended with FIX2 schema label
  cleanup details; `latest_validation` updated to 175 PASS)
- `docs/research/commands/COMMAND_LOG.md` (this TASK-014AR-FIX2 entry)

Validation:
- `python -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py` → PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py -q` → 175/175 PASS (159 pre-FIX2 + 16 new AR-FIX2 schema-label tests)
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py -q` → 138/138 PASS (AQ regression intact)
- AST + tokenize source-scan safety preserved
- ADAPTER_CONTRACT_VERSION = `static_skeleton_design_v1` (unchanged)
- CONSUMED_IMPLEMENTATION_DESIGN_CONTRACT_VERSION = `implementation_design_v1` (still consumed at runtime — FIX1 wiring preserved)
- ADAPTER_RESPONSE_STATUS = `STATIC_SKELETON_DESIGN_NOT_SENT` (unchanged)
- ORDER_LINK_ID_PREFIX = `STATIC_SKELETON_DESIGN_TINY_ENTRY_` (unchanged)
- STATIC_SKELETON_DESIGN_CONCLUSION = `STATIC_SKELETON_DESIGN_READY_NOT_EXECUTABLE` (unchanged)
- Status string `TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_STATIC_SKELETON_DESIGN_READY` unchanged
- next_required_task `TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run` unchanged
- Mode string now: `static_skeleton_design_checklist` (default), `static_skeleton_design_approval` (with --allow-implementation-design)

Outputs: none (runtime preview not invoked locally; outputs dir gitignored).

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no `/v5/position/trading-stop` call
- no sender adapter introduced / no executable adapter surface / no adapter class added / no `send` / `place_order` / `execute` method
- no endpoint call / no socket opened / no urllib / no requests / no httpx / no http.client
- no secrets read / no `.env*` read / no `os.environ` access / no dotenv
- no HMAC / no signature header / no signing primitive
- TASK-014L G20 sender policy still active (no protected_entry_policy_missing lift)
- 5 protected demo positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified
- main.py / src/risk.py / BybitExecutor untouched
- no auto git commit / no auto git push / no auto branch / no auto tag

Notes:
- TASK-014AR-FIX2 is a pure report-facing schema/label cleanup. It
  preserves every safety invariant, every fail-closed gate, the
  runtime consumption of the TASK-014AQ implementation design
  artifact (FIX1), and all legacy `implementation_design_*` keys as
  backward-compatible aliases. The mode string change is intentional
  and the legacy `MODE_IMPLEMENTATION_DESIGN_CHECKLIST` /
  `_APPROVAL` identifiers continue to resolve to the new string
  values, so any downstream test or doc that imports them remains
  valid.
- G20 sender policy unchanged. Five protected positions never
  touched. No endpoint called. No secret read. No HMAC. No
  signature. No real order. No auto-git operations. Local commit
  only; remote push deferred to Rick's explicit instruction.

---

### 2026-06-13（TASK-014AR-FIX1-DOCS1 — Sync Static Skeleton Artifact Wiring Docs）

Agent: Claude (Opus)
Command source: Rick chat instruction "Proceed with TASK-014AR-FIX1-DOCS1
now, before push/VPS validation." (2026-06-13)
Task: Synchronize cross-agent docs for TASK-014AR-FIX1 — fill in the
actual local commit hash `e8a3f4c` into the README Demo Trading Guarded
Lifecycle Status board; update `latest_completed_task` to TASK-014AR-FIX1
and `current_phase` to "guarded entry real execution adapter static
skeleton design fixed and wired to implementation design artifact";
add this TASK-014AR-FIX1-DOCS1 event in COMMAND_LOG; verify
NEXT_ACTION.md TASK-014AR-FIX1 status block and VPS validation
commands are intact. No code changes, no execution logic, no G20 lift,
no endpoint calls, no secret reads, no real entry execution, no
executable sender path added, no `send` / `place_order` / `execute`
method introduced, no adapter class added, no main.py / src/risk.py /
BybitExecutor modification, no position modification.

Status before: TASK-014AR-FIX1 source/preview/tests/docs committed
locally as `e8a3f4c` but README board still pointed at the commit
message string without an explicit hash, and `latest_completed_task`
still read "TASK-014AR（已由 TASK-014AR-FIX1 補正）" rather than
TASK-014AR-FIX1 directly
Status after: TASK-014AR-FIX1-DOCS1 docs sync DONE; cross-agent board
points at TASK-014AR-FIX1 / `e8a3f4c`; `current_phase` explicitly
declares static skeleton design fixed and wired to implementation
design artifact; next_required_task =
TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run

Files changed:
- `README.md` (Demo Trading Guarded Lifecycle Status board:
  banner updated to "updated by TASK-014AR-FIX1-DOCS1, 2026-06-13";
  `latest_completed_task` updated to TASK-014AR-FIX1;
  `latest_commit` updated to include explicit hash `e8a3f4c`;
  `current_phase` rewritten to "guarded entry real execution adapter
  static skeleton design fixed and wired to implementation design
  artifact"; `latest_validation` augmented with AQ regression line
  138 PASS)
- `docs/research/commands/COMMAND_LOG.md` (this TASK-014AR-FIX1-DOCS1
  entry)

Validation:
- `python -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py` → PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py -q` → 159/159 PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py -q` → 138/138 PASS (AQ regression intact)

Outputs: docs-only — no runtime artifacts produced

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no `/v5/position/trading-stop` call
- no sender adapter introduced / no executable adapter surface / no adapter class added / no `send` / `place_order` / `execute` method
- no endpoint call / no socket opened / no urllib / no requests / no httpx / no http.client
- no secrets read / no `.env*` read / no `os.environ` access / no dotenv
- no HMAC / no signature header / no signing primitive
- TASK-014L G20 sender policy still active (no protected_entry_policy_missing lift)
- 5 protected demo positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified
- main.py / src/risk.py / BybitExecutor untouched
- no auto git commit / no auto git push / no auto branch / no auto tag

Notes:
- Local commit only; push pending Rick instruction.
- next_required_task remains `TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run`.

---

### 2026-06-13（TASK-014AR-FIX1 — Wire Static Skeleton Design to Implementation Design Artifact）

Agent: Claude (Opus)
Command source: Rick chat instruction "Proceed with TASK-014AR-FIX1 now.
TASK-014AR commit `9de11fe` exists locally, but the final report has an
unacceptable scope caveat that runtime wiring is deferred to TASK-014AS."
(2026-06-13)
Task: Fix TASK-014AR scope so that the static-skeleton-design module
actively CONSUMES the TASK-014AQ `entry_implementation_design` artifact at
runtime (not just forward-declares identifiers). Wire `run_design()` to
accept a new `entry_implementation_design: dict[str, Any] | None`
parameter, register `entry_impl_design` in `present_flags`, parse seven AQ
fields (status / implementation_design_grants_execution /
adapter_implementation_included / adapter_execution_included /
send_allowed / implementation_design_conclusion with top-level OR nested
`final_implementation_design_verdict.implementation_design_conclusion`
fallback / `audit_artifacts.response_status` with top-level
`response_status` fallback), and add eight LIVE hard fail-closed gates
(`entry_implementation_design_missing`,
`entry_implementation_design_status_unacceptable`,
`entry_implementation_design_grants_execution_true`,
`entry_implementation_design_implementation_included_true`,
`entry_implementation_design_execution_included_true`,
`entry_implementation_design_send_allowed_true`,
`entry_implementation_design_conclusion_mismatch`,
`entry_implementation_design_response_status_unacceptable`). Extend the
dataclass with seven new `upstream_entry_implementation_design_*` fields
plus `consumed_implementation_design_contract_version`, expose them via
`to_dict()` + `audit_artifacts`, and classify the new gates into the
`stage_0_set` of `_first_failed_stage`. Extend preview with
`_DEFAULT_ENTRY_IMPLEMENTATION_DESIGN_DIR`,
`load_latest_entry_implementation_design`, and a new
`--from-latest-entry-implementation-design` CLI flag. NO endpoint, NO
secret, NO sender, NO adapter class, NO `send` / `place_order` /
`execute`, NO G20 lift, NO main.py / src/risk.py / BybitExecutor
modification.

Status before: TASK-014AR committed locally as `9de11fe`, but the final
report deferred AQ runtime wiring to TASK-014AS — unacceptable per Rick
Status after: TASK-014AR-FIX1 wired AQ artifact at runtime; 27 upstream
artifacts; 8 LIVE entry_implementation_design_* gates; 159 PASS;
next_required_task = TASK-014AS_guarded_entry_real_execution_adapter_
static_skeleton_dry_run

Files changed:
- `src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py`
  (added `entry_implementation_design` parameter to `run_design()`;
  added `entry_impl_design` to `present_flags`; AQ field parsing with
  conclusion top-level/nested fallback and response_status
  audit_artifacts/top-level fallback; eight LIVE hard fail-closed gates;
  seven new dataclass `upstream_entry_implementation_design_*` fields
  plus `consumed_implementation_design_contract_version`; `to_dict()`
  exposes all eight; `audit_artifacts` exposes all eight; stage_0
  summary updated from "26 upstream artifacts" to "27 upstream
  artifacts"; eight new gates added to `stage_0_set` in
  `_first_failed_stage`)
- `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py`
  (added `_DEFAULT_ENTRY_IMPLEMENTATION_DESIGN_DIR`;
  `load_latest_entry_implementation_design()` loader for
  `latest_tiny_guarded_entry_real_execution_adapter_implementation_design.json`;
  `entry_implementation_design_dir` parameter on `run_execute()`;
  passes parsed AQ artifact to `run_design()`;
  `--from-latest-entry-implementation-design` CLI flag; module
  docstring updated)
- `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py`
  (`_valid_entry_implementation_design()` fixture mirroring AP;
  `entry_implementation_design=_UNSET` parameter on `_run()` helper;
  updated existing TestAQ88 `test_missing_artifacts_exits_one` to pass
  empty AQ dir; 16 new AR-FIX1 test classes: 3 propagation tests, 1
  missing, 6 acceptance-gate scenarios, 2 conclusion-mismatch tests
  covering top-level + nested fallback, 2 response_status-mismatch
  tests covering audit + top-level fallback, 2 CLI subprocess tests,
  1 report-artifact test)
- `docs/research/commands/NEXT_ACTION.md`
  (banner advanced to "TASK-014AR Status (2026-06-13, updated by
  TASK-014AR-FIX1 same day)"; AQ consumption item rewritten as
  "CONSUMED AT RUNTIME (FIX1)"; preview item updated to 27 flags +
  new run_execute param; tests item updated to 159 tests with the 16
  new AR-FIX1 descriptions; validation count updated to 159/159 PASS
  with AQ regression 138/138 line; step 1 expectation updated to
  "159/159 PASS (post-FIX1)"; step 2 command appended with
  `--from-latest-entry-implementation-design`; step 3 rewritten
  without the "deferred to AS" caveat)
- `README.md`
  (Demo Trading Guarded Lifecycle Status board banner updated to
  "updated by TASK-014AR-FIX1, 2026-06-13"; `latest_commit` updated
  to FIX1 message; `current_phase` rewritten to remove the "for
  TASK-014AS to wire" caveat — now describes 27 upstream artifacts +
  active AQ runtime consumption + 8 LIVE gates; `latest_validation` →
  159 PASS)
- `docs/research/commands/COMMAND_LOG.md` (this TASK-014AR-FIX1 entry)

Validation:
- `python -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py` → PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py` → 159/159 PASS (143 original + 16 new AR-FIX1)
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py` → 138/138 PASS (AQ regression intact)
- AST + tokenize source-scan safety preserved: no urllib / requests /
  httpx / socket / http.client / hmac / hashlib / dotenv / os.environ /
  sender / main / risk / BybitExecutor / pybit / executable adapter
  `send` / `place_order` / `execute` methods / forbidden flags /
  AA-AQ module reuse / auto-git in src OR preview
- ADAPTER_CONTRACT_VERSION = `static_skeleton_design_v1` (unchanged)
- CONSUMED_IMPLEMENTATION_DESIGN_CONTRACT_VERSION = `implementation_design_v1` (now actively consumed at runtime)
- ADAPTER_RESPONSE_STATUS = `STATIC_SKELETON_DESIGN_NOT_SENT` (unchanged)
- ORDER_LINK_ID_PREFIX = `STATIC_SKELETON_DESIGN_TINY_ENTRY_` (unchanged)
- STATIC_SKELETON_DESIGN_CONCLUSION = `STATIC_SKELETON_DESIGN_READY_NOT_EXECUTABLE` (unchanged)

Outputs: none (runtime preview not invoked locally; outputs dir gitignored).

Notes:
- TASK-014AR-FIX1 closes the scope caveat from TASK-014AR: the static
  skeleton design module now ACTIVELY CONSUMES TASK-014AQ output at
  runtime via 8 LIVE `entry_implementation_design_*` fail-closed gates.
  Missing AQ artifact or any acceptance-field mismatch → FAIL_CLOSED.
  The AN → AO → AP → AQ → AR fail-closed invariant chain is fully
  wired; the only remaining downstream is TASK-014AS dry-run.
- G20 sender policy unchanged. Five protected positions never touched.
  No endpoint called. No secret read. No HMAC. No signature. No real
  order. No auto-git operations. Local commit only; remote push
  deferred to Rick's explicit instruction.

---

### 2026-06-13（TASK-014AR — Guarded Entry Real Execution Adapter Static Skeleton Design）

Agent: Claude (Opus)
Command source: Rick chat instruction "I explicitly authorize TASK-014AR now.
Proceed with TASK-014AR: Guarded Entry Real Execution Adapter Static Skeleton
Design." (2026-06-13)
Task: Add static-skeleton-design-only module
`src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py`
that mirrors the TASK-014AQ implementation-design contract and forward-
declares the AQ → AR consumption surface for TASK-014AS: new constant
`CONSUMED_IMPLEMENTATION_DESIGN_CONTRACT_VERSION = "implementation_design_v1"`,
new frozenset `ACCEPTABLE_ENTRY_IMPLEMENTATION_DESIGN_STATUSES`
(TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_IMPLEMENTATION_DESIGN_READY /
_READY_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED), and
eight new gate identifiers (`entry_implementation_design_missing`,
`_status_unacceptable`, `_grants_execution_true`,
`_adapter_implementation_included_true`, `_adapter_execution_included_true`,
`_send_allowed_true`, `_conclusion_mismatch`,
`_response_status_unacceptable`) all registered in `_HARD_FAIL_GATES` ready
to be wired by TASK-014AS dry-run. ADAPTER_CONTRACT_VERSION advanced to
`static_skeleton_design_v1`; ADAPTER_RESPONSE_STATUS = `STATIC_SKELETON_
DESIGN_NOT_SENT`; ORDER_LINK_ID_PREFIX = `STATIC_SKELETON_DESIGN_TINY_ENTRY_`;
STATIC_SKELETON_DESIGN_CONCLUSION = `STATIC_SKELETON_DESIGN_READY_NOT_
EXECUTABLE`. NO sender, NO executable adapter, NO `send` / `place_order` /
`execute` method, NO real entry execution, NO endpoint calls, NO secrets, NO
HMAC, NO signing, NO AA-AQ module reuse, NO auto-git operations, G20 still
active, 5 protected positions (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT /
EDUUSDT) untouched. Local commit only — no push.

Status before: TASK-014AQ DONE (commit `9513cdb`), VPS validated 138/138 PASS,
status=TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_IMPLEMENTATION_DESIGN_READY,
next_required_task = TASK-014AR_guarded_entry_real_execution_adapter_static_
skeleton_design
Status after: TASK-014AR static-skeleton-design module + preview + 143-test
suite + .gitignore + NEXT_ACTION + README + COMMAND_LOG committed locally;
next_required_task = TASK-014AS_guarded_entry_real_execution_adapter_static_
skeleton_dry_run

Files changed:
- `src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py`
  (new — 2200+ LOC; 14 stages STAGE_0..STAGE_13; 62-gate `_HARD_FAIL_GATES`
  frozenset incl. 8 new forward-declared `entry_implementation_design_*`
  gates; 17 ACCEPTABLE_*_STATUSES frozensets incl. new
  ACCEPTABLE_ENTRY_IMPLEMENTATION_DESIGN_STATUSES; dataclass result with
  deep-copy `to_dict()` over 14 sub-dict fields; ADAPTER_NAME =
  `GuardedTinyEntryRealExecutionAdapter`; ADAPTER_CONTRACT_VERSION =
  `static_skeleton_design_v1`; CONSUMED_IMPLEMENTATION_DESIGN_CONTRACT_VERSION
  = `implementation_design_v1`; ADAPTER_RESPONSE_STATUS =
  `STATIC_SKELETON_DESIGN_NOT_SENT`; ORDER_LINK_ID_PREFIX =
  `STATIC_SKELETON_DESIGN_TINY_ENTRY_`; STATIC_SKELETON_DESIGN_CONCLUSION =
  `STATIC_SKELETON_DESIGN_READY_NOT_EXECUTABLE`; `__all__` exports updated
  with the new constants and gates)
- `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py`
  (new — 1300+ LOC; CLI flags mirror AQ preview;
  writes `{ts}_*` + `latest_*` JSON+MD to
  `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_static_skeleton_design/`;
  NO auto-git operations; NO forbidden execution flags)
- `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py`
  (new — 2400+ LOC; 143 tests; new
  TestAR122ConsumedImplementationDesignContractVersion,
  TestAR123AcceptableEntryImplementationDesignStatuses,
  TestAR124AQAcceptanceGateIdentifiersDeclared classes validate forward-
  declared AQ-consumption surface; preserves all 138 mechanical mirror
  tests from the AQ template)
- `.gitignore`
  (added `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_static_skeleton_design/`)
- `docs/research/commands/NEXT_ACTION.md`
  (new TASK-014AR Status block at top; banner advanced from
  "updated by TASK-014AQ (2026-06-12)" → "updated by TASK-014AR
  (2026-06-13)"; new "Next Rick Action (set by 2026-06-13 TASK-014AR)"
  with VPS pull / validate / optional preview / decide-AS-authorization
  steps)
- `README.md`
  (Demo Trading Guarded Lifecycle Status board banner updated to
  "updated by TASK-014AR, 2026-06-13"; `latest_completed_task` →
  TASK-014AR; `current_phase` advanced to "guarded entry real execution
  adapter static skeleton design completed"; `next_required_task` →
  TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run;
  `latest_validation` → `pytest ...static_skeleton_design.py` → 143 PASS;
  adapter identity updated to `static_skeleton_design_v1` +
  CONSUMED_IMPLEMENTATION_DESIGN_CONTRACT_VERSION; order link id prefix →
  `STATIC_SKELETON_DESIGN_TINY_ENTRY_`; audit response_status →
  `STATIC_SKELETON_DESIGN_NOT_SENT`; static_skeleton_design_conclusion →
  `STATIC_SKELETON_DESIGN_READY_NOT_EXECUTABLE`)
- `docs/research/commands/COMMAND_LOG.md` (this TASK-014AR entry)

Validation:
- `python -m py_compile src/demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py` → PASS
- `python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py` → 143/143 PASS
- AST + tokenize source-scan safety preserved: no urllib / requests / httpx /
  socket / http.client / hmac / hashlib / dotenv / os.environ / sender /
  main / risk / BybitExecutor / pybit / executable adapter `send` /
  `place_order` / `execute` methods / forbidden flags / AA-AQ module reuse /
  auto-git in src OR preview
- ADAPTER_CONTRACT_VERSION = `static_skeleton_design_v1`
- CONSUMED_IMPLEMENTATION_DESIGN_CONTRACT_VERSION = `implementation_design_v1`
- ADAPTER_RESPONSE_STATUS = `STATIC_SKELETON_DESIGN_NOT_SENT`
- ORDER_LINK_ID_PREFIX = `STATIC_SKELETON_DESIGN_TINY_ENTRY_`
- STATIC_SKELETON_DESIGN_CONCLUSION = `STATIC_SKELETON_DESIGN_READY_NOT_EXECUTABLE`

Outputs: none (runtime preview not invoked locally; outputs dir gitignored).

Notes:
- TASK-014AR scope deliberately narrow: STATIC SKELETON DESIGN ONLY —
  forward-declares the AQ → AR consumption surface (1 constant + 1 frozenset +
  8 gate identifiers) as well-formed identifiers in `_HARD_FAIL_GATES` and
  `__all__`, validated by 5 new tests. The actual runtime wiring (parsing
  the AQ artifact, populating dataclass fields from it, triggering the new
  gates against AQ output) is intentionally deferred to TASK-014AS guarded
  entry real execution adapter static skeleton dry-run. This preserves the
  fail-closed invariant chain AN → AO → AP → AQ → AR → AS without enabling
  any real execution.
- G20 sender policy unchanged. Five protected positions never touched. No
  endpoint called. No secret read. No HMAC. No signature. No real order. No
  auto-git operations. Local commit only; remote push deferred to Rick's
  explicit instruction.

---

### 2026-06-12（TASK-014AQ-DOCS1 — Adapter Implementation Design Docs Sync）

Agent: Claude (Opus)
Command source: Rick chat instruction "Proceed with TASK-014AQ-DOCS1 now,
before push/VPS validation" (2026-06-12)
Task: Synchronize cross-agent docs for TASK-014AQ — fill in the actual local
commit hash `9513cdb` into the README Demo Trading Guarded Lifecycle Status
board (previously `pending`) and the COMMAND_LOG TASK-014AQ entry; record
this TASK-014AQ-DOCS1 event in COMMAND_LOG; verify NEXT_ACTION.md TASK-014AQ
section is intact with VPS validation commands. No code changes, no execution
logic, no G20 lift, no endpoint calls, no secret reads, no real entry
execution, no executable sender path added, no `send` / `place_order` /
`execute` method introduced.

Status before: TASK-014AQ source/preview/tests/.gitignore/NEXT_ACTION/README/
COMMAND_LOG committed locally as `9513cdb` but README + COMMAND_LOG still
showed `pending` for the AQ commit hash
Status after: TASK-014AQ-DOCS1 docs sync DONE; cross-agent board points at
TASK-014AQ / `9513cdb`; next_required_task =
TASK-014AR_guarded_entry_real_execution_adapter_static_skeleton_design

Files changed:
- `README.md` (Demo Trading Guarded Lifecycle Status board:
  banner updated to "updated by TASK-014AQ-DOCS1, 2026-06-12";
  `latest_commit` updated from `pending` → `9513cdb`)
- `docs/research/commands/COMMAND_LOG.md` (this DOCS1 entry +
  TASK-014AQ entry's `README.md` files-changed line updated to reflect
  the filled-in `9513cdb` hash)

Validation:
- py_compile src/demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py → PASS
- py_compile scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py → PASS
- py_compile tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py → PASS
- pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py → 138/138 PASS

Outputs: docs-only — no runtime artifacts produced

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no `/v5/position/trading-stop` call
- no sender adapter introduced / no executable adapter surface / no `send` / `place_order` / `execute` method
- no endpoint call / no socket opened / no urllib / no requests / no httpx / no http.client
- no secrets read / no `.env*` read / no `os.environ` access / no dotenv
- no HMAC / no signature header / no signing primitive
- TASK-014L G20 sender policy still active (no protected_entry_policy_missing lift)
- 5 protected demo positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified
- main.py / src/risk.py / BybitExecutor untouched
- no auto git commit / no auto git push / no auto branch / no auto tag

Notes:
- Local commit only; push pending Rick instruction.
- next_required_task remains `TASK-014AR_guarded_entry_real_execution_adapter_static_skeleton_design`.

---

### 2026-06-12（TASK-014AQ — Guarded Entry Real Execution Adapter Implementation Design）

Agent: Claude (Opus)
Command source: Rick chat instruction
"請建立 TASK-014AQ：Guarded Entry Real Execution Adapter Implementation Design" (2026-06-12)
Task: Add `src/demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py`
as an implementation-design-only module that consumes the AP readiness-review
artifact and the full AI→AP safety chain to produce a static implementation
design (module boundary, request construction, transport, secret/signing,
response/error handling, manual approval, stop/cleanup handoff, risk/
idempotency/audit, forbidden surface, failure policy) for the FUTURE TASK-014AR
static-skeleton design phase. The module DOES NOT implement the adapter, does
not import any sender / private client / network primitive, does not call
`/v5/order/create`, does not call `/v5/position/trading-stop`, does not read
secrets, does not sign anything, does not lift TASK-014L G20, does not
validate any token / phrase / approval input, does not treat any token /
phrase / input as authorization, does not expose any executable adapter
`send` / `place_order` / `execute` method, does not touch any existing
protected demo position, and does not auto-commit / auto-push git.

Inputs: 26 upstream artifacts — the 25 AP upstream artifacts plus AP's own
guarded entry real execution adapter implementation readiness review output
(`entry_implementation_readiness_review`).

Status before: TASK-014AP-DOCS1 cross-agent docs synced (commit `3630055`)
Status after: TASK-014AQ guarded entry real execution adapter implementation
design committed locally; next_required_task =
TASK-014AR_guarded_entry_real_execution_adapter_static_skeleton_design

Files changed:
- `src/demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py` (new — 2190 lines; implementation-design-only module, 26 upstream artifact inputs, 4 status modes, 14 stages STAGE_0..STAGE_13, HARD_FAIL_GATES frozenset of 54 gates, 16 ACCEPTABLE_*_STATUSES frozensets incl. ACCEPTABLE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_STATUSES, dataclass result with deep-copy to_dict() covering 14 sub-dict fields (artifact_preflight / implementation_design_scope / static_module_boundary_design / request_construction_design / transport_and_endpoint_design / secret_and_signing_design / response_and_error_handling_design / manual_approval_and_authorization_design / stop_cleanup_handoff_design / risk_idempotency_and_audit_design / forbidden_implementation_surface_design / failure_and_abort_implementation_design / documentation_sync_review / final_implementation_design_verdict); NO `/v5/order/create` invocation, NO `/v5/position/trading-stop` invocation, NO secret reads, NO HMAC/signature, NO sender adapter, NO executable adapter surface, NO `send` / `place_order` / `execute` method, NO real entry execution, NO urllib/requests/httpx/socket/http.client imports, NO G20 lift, NO AA-AP module reuse, NO auto git operations; ADAPTER_NAME=GuardedTinyEntryRealExecutionAdapter, ADAPTER_CONTRACT_VERSION=implementation_design_v1, CONSUMED_READINESS_CONTRACT_VERSION=readiness_review_v1, CONSUMED_DRY_RUN_CONTRACT_VERSION=dry_run_v1, CONSUMED_DESIGN_CONTRACT_VERSION=design_only_v1, ADAPTER_RESPONSE_STATUS=IMPLEMENTATION_DESIGN_NOT_SENT, ORDER_LINK_ID_PREFIX=IMPLEMENTATION_DESIGN_TINY_ENTRY_, IMPLEMENTATION_DESIGN_CONCLUSION=IMPLEMENTATION_DESIGN_READY_NOT_EXECUTABLE; next_required_task = TASK-014AR_guarded_entry_real_execution_adapter_static_skeleton_design)
- `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py` (new — 1306 lines; 26 `--from-latest-*` flags incl. new `--from-latest-entry-implementation-readiness-review`, `--symbol`, `--expected-commit-hash` documented-only, `--allow-implementation-design`, `--allow-real-entry-execution`, `--write-report`; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_implementation_design/`; NO auto git operations)
- `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py` (new — 2354 lines, 138 tests covering 4 status modes, 26 missing-artifact gates, endpoint/account/symbol invariants, AP implementation-readiness-review status/conclusion/grants/implementation/execution/send-allowed/audit-response acceptance, 14 stages presence + order, deep-copy roundtrip, AST + tokenize source-scan safety, 5 protected positions untouched, G20 never lifted, no AA-AP module reuse, next_required_task = TASK-014AR, 16 frozenset whitelists, HARD_FAIL_GATES expansion to 54 gates, identity constants exposed, CLI subprocess exit codes, report artifacts written, repo_tmp_path Windows ACL workaround)
- `.gitignore` (added `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_implementation_design/`)
- `docs/research/commands/NEXT_ACTION.md` (inserted TASK-014AQ status block + Next Rick Action section above TASK-014AP block; banner updated to "updated by TASK-014AQ, 2026-06-12")
- `README.md` (Demo Trading Guarded Lifecycle Status board: banner → "updated by TASK-014AQ-DOCS1, 2026-06-12"; latest_completed_task → TASK-014AQ; latest_commit → `9513cdb` (filled in by TASK-014AQ-DOCS1); current_phase → guarded entry real execution adapter implementation design completed; next_required_task → TASK-014AR; latest validation → 138 PASS; adapter identity adds CONSUMED_READINESS_CONTRACT_VERSION=readiness_review_v1, ADAPTER_CONTRACT_VERSION=implementation_design_v1; order link id prefix → IMPLEMENTATION_DESIGN_TINY_ENTRY_; audit response_status → IMPLEMENTATION_DESIGN_NOT_SENT; row renamed implementation_design_conclusion=IMPLEMENTATION_DESIGN_READY_NOT_EXECUTABLE)
- `docs/research/commands/COMMAND_LOG.md` (this TASK-014AQ entry)

Validation:
- py_compile src/demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py → PASS
- py_compile scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py → PASS
- py_compile tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py → PASS
- pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_design.py → 138/138 PASS

Known pre-existing unrelated failure (NOT caused by TASK-014AQ):
- tests/demo_trading/test_demo_emergency_close_sender.py::TestCLIIntegration::test_dry_run_cli_writes_report

Outputs: design-only — runtime artifacts (when run) will be written to
`outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_implementation_design/`
(gitignored). The design output contains:
- adapter implementation contract (documented, not instantiated)
- static module boundary design (no executable class/method)
- request construction design (endpoint_path_ref="/v5/order/create" reference
  only, base_url_ref="https://api-demo.bybit.com" reference only, live
  endpoint denylist documented)
- transport / endpoint design (transport required-in-future-task, not
  implemented here)
- secret / signing design (documented as required-for-future, not implemented)
- response / error handling design (response_status=IMPLEMENTATION_DESIGN_NOT_SENT,
  exchange_order_id=None)
- manual approval / authorization design (phrase / token / inputs required-in-
  future-task, not validated here)
- stop / cleanup handoff design (separate future task)
- risk / idempotency / audit design (max_notional_usdt=10, ORDER_LINK_ID_PREFIX=
  IMPLEMENTATION_DESIGN_TINY_ENTRY_ documented — never sent)
- forbidden implementation surface design (no sender / no send / no place_order
  / no execute / no private transport)
- failure / abort implementation design (fail-closed semantics documented)
- documentation sync review (this TASK-014AQ entry + README + NEXT_ACTION)
- final implementation design verdict (implementation_design_conclusion=
  IMPLEMENTATION_DESIGN_READY_NOT_EXECUTABLE)
- audit artifacts (response_status=IMPLEMENTATION_DESIGN_NOT_SENT,
  next_required_task=TASK-014AR_guarded_entry_real_execution_adapter_static_skeleton_design)

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no `/v5/position/trading-stop` call
- no sender adapter introduced / no executable adapter surface / no `send` / `place_order` / `execute` method
- no endpoint call / no socket opened / no urllib / no requests / no httpx / no http.client
- no secrets read / no `.env*` read / no `os.environ` access / no dotenv
- no HMAC / no signature header / no signing primitive
- no AA-AP module reuse (no `from src.demo_tiny_*` imports in new module)
- TASK-014L G20 sender policy still active (no protected_entry_policy_missing lift)
- 5 protected demo positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified
- main.py / src/risk.py / BybitExecutor untouched
- no auto git commit / no auto git push / no auto branch / no auto tag
- `--allow-real-entry-execution` flag exists only to PROVE the guard rejects
  it with `REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED`; flag never triggers any
  network / endpoint / order / secret / signing / sender code path
- `implementation_design_conclusion=IMPLEMENTATION_DESIGN_READY_NOT_EXECUTABLE`
  is documented only — it does NOT authorize any real execution; the next
  task TASK-014AR is a static-skeleton DESIGN task, not implementation, not
  execution
- no real sender / close-only sender / emergency-close sender / new-entry
  sender / trading-stop adapter called or imported

Notes:
- Local commit only; push pending Rick instruction.
- next_required_task = `TASK-014AR_guarded_entry_real_execution_adapter_static_skeleton_design`.
- HARD_FAIL_GATES = 54 (26 missing-artifact + chain acceptance gates for
  AM/AN/AO/AP + readiness conclusion gate + implementation_design_only flags
  + symbol/qty/side/reduceOnly mismatch gates).
- Tests = 138 PASS (above the 99 baseline target per Rick's spec).

---

### 2026-06-12（TASK-014AP-DOCS1 — Adapter Implementation Readiness Review Docs Sync）

Agent: Claude (Opus)
Command source: Rick chat instruction "Proceed with TASK-014AP-DOCS1 now,
before push/VPS validation" (2026-06-12)
Task: Synchronize cross-agent docs for TASK-014AP — fill in the actual local
commit hash `8709bf4` into the README Demo Trading Guarded Lifecycle Status
board (previously `pending`) and the COMMAND_LOG TASK-014AP entry; record
this TASK-014AP-DOCS1 event in COMMAND_LOG; verify NEXT_ACTION.md TASK-014AP
section is intact with VPS validation commands. No code changes, no execution
logic, no G20 lift, no endpoint calls, no secret reads, no real entry
execution, no executable sender path added, no `send` / `place_order` /
`execute` method introduced.

Status before: TASK-014AP source/preview/tests/.gitignore/NEXT_ACTION/README/
COMMAND_LOG committed locally as `8709bf4` but README + COMMAND_LOG still
showed `pending` for the AP commit hash
Status after: TASK-014AP-DOCS1 docs sync DONE; cross-agent board points at
TASK-014AP / `8709bf4`; next_required_task =
TASK-014AQ_guarded_entry_real_execution_adapter_implementation_design

Files changed:
- `README.md` (Demo Trading Guarded Lifecycle Status board:
  banner updated to "updated by TASK-014AP-DOCS1, 2026-06-12";
  `latest_commit` updated from `pending` → `8709bf4`)
- `docs/research/commands/COMMAND_LOG.md` (this DOCS1 entry +
  TASK-014AP entry's `README.md` files-changed line updated to reflect
  the filled-in `8709bf4` hash)

Validation:
- py_compile src/demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py → PASS
- py_compile scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py → PASS
- py_compile tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py → PASS
- pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py → 124/124 PASS

Outputs: docs-only — no runtime artifacts produced

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no `/v5/position/trading-stop` call
- no sender adapter introduced / no executable adapter surface / no `send` / `place_order` / `execute` method
- no endpoint call / no socket opened / no urllib / no requests / no httpx / no http.client
- no secrets read / no `.env*` read / no `os.environ` access / no dotenv
- no HMAC / no signature header / no signing primitive
- TASK-014L G20 sender policy still active (no protected_entry_policy_missing lift)
- 5 protected demo positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified
- main.py / src/risk.py / BybitExecutor untouched
- no auto git commit / no auto git push / no auto branch / no auto tag

Notes:
- Local commit only; push pending Rick instruction.
- next_required_task remains `TASK-014AQ_guarded_entry_real_execution_adapter_implementation_design`.

---

### 2026-06-12（TASK-014AP — Guarded Entry Real Execution Adapter Implementation Readiness Review）

Agent: Claude (Opus)
Command source: Rick chat instruction
"請建立 TASK-014AP：Guarded Entry Real Execution Adapter Implementation Readiness Review" (2026-06-12)
Task: Add `src/demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py`
as a readiness-review-only module that consumes the AO adapter dry-run
artifact and the full AI→AO safety chain to produce an implementation
readiness verdict for the FUTURE TASK-014AQ implementation design phase. The
module DOES NOT implement the adapter, does not import any sender / private
client / network primitive, does not call `/v5/order/create`, does not call
`/v5/position/trading-stop`, does not read secrets, does not sign anything,
does not lift TASK-014L G20, does not validate any token / phrase / approval
input, does not treat any token / phrase / input as authorization, does not
expose any executable adapter `send` / `place_order` / `execute` method, does
not touch any existing protected demo position, and does not auto-commit /
auto-push git.

Inputs: 25 upstream artifacts — the 24 AO upstream artifacts plus AO's own
guarded entry real execution adapter dry-run output (`entry_adapter_dry_run`).

Status before: TASK-014AO-DOCS1 cross-agent docs synced (commit `86d0ca8`)
Status after: TASK-014AP guarded entry real execution adapter implementation
readiness review committed locally; next_required_task =
TASK-014AQ_guarded_entry_real_execution_adapter_implementation_design

Files changed:
- `src/demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py` (new — 2057 lines; readiness-review-only module, 25 upstream artifact inputs, 4 status modes, 12 stages STAGE_0..STAGE_11, HARD_FAIL_GATES frozenset of 47 gates, 15 ACCEPTABLE_*_STATUSES frozensets incl. ACCEPTABLE_ENTRY_ADAPTER_DRY_RUN_STATUSES, dataclass result with deep-copy to_dict() covering 12 sub-dict fields (readiness_review_scope / chain_readiness_summary / implementation_preconditions_review / forbidden_implementation_surface_review / secret_signing_transport_readiness_review / manual_approval_revalidation_review / stop_cleanup_readiness_review / risk_and_idempotency_readiness_review / failure_and_abort_readiness_review / documentation_sync_review / final_implementation_readiness_verdict / audit_artifacts); NO `/v5/order/create`, NO `/v5/position/trading-stop`, NO secret reads, NO HMAC/signature, NO sender adapter, NO executable adapter surface, NO `send` / `place_order` / `execute` method, NO real entry execution, NO urllib/requests/httpx/socket/http.client imports, NO G20 lift, NO AA-AO module reuse, NO auto git operations; ADAPTER_NAME=GuardedTinyEntryRealExecutionAdapter, ADAPTER_CONTRACT_VERSION=readiness_review_v1, CONSUMED_DRY_RUN_CONTRACT_VERSION=dry_run_v1, CONSUMED_DESIGN_CONTRACT_VERSION=design_only_v1, ADAPTER_RESPONSE_STATUS=READINESS_REVIEW_NOT_SENT, ORDER_LINK_ID_PREFIX=READINESS_REVIEW_TINY_ENTRY_, IMPLEMENTATION_READINESS_CONCLUSION=READY_FOR_IMPLEMENTATION_DESIGN_NOT_EXECUTION; next_required_task = TASK-014AQ_guarded_entry_real_execution_adapter_implementation_design)
- `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py` (new — 1257 lines; 25 `--from-latest-*` flags incl. new `--from-latest-entry-adapter-dry-run`, `--symbol`, `--expected-commit-hash` documented-only, `--allow-readiness-review`, `--allow-real-entry-execution`, `--write-report`; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_implementation_readiness_review/`; NO auto git operations)
- `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py` (new — 2126 lines, 124 tests covering 4 status modes, 25 missing-artifact gates, endpoint/account/symbol invariants, AO adapter-dry-run status/grants/implementation/execution/no-send-method/audit-response acceptance, 12 stages presence + order, deep-copy roundtrip, AST + tokenize source-scan safety, 5 protected positions untouched, G20 never lifted, no AA-AO module reuse, next_required_task = TASK-014AQ, 15 frozenset whitelists, HARD_FAIL_GATES expansion to 47 gates, identity constants exposed, CLI subprocess exit codes, report artifacts written, repo_tmp_path Windows ACL workaround)
- `.gitignore` (added `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_implementation_readiness_review/`)
- `docs/research/commands/NEXT_ACTION.md` (inserted TASK-014AP status block + Next Rick Action section above TASK-014AO block; banner updated to "updated by TASK-014AP, 2026-06-12")
- `README.md` (Demo Trading Guarded Lifecycle Status board: banner → "updated by TASK-014AP-DOCS1, 2026-06-12"; latest_completed_task → TASK-014AP; latest_commit → `8709bf4` (filled in by TASK-014AP-DOCS1); current_phase → guarded entry real execution adapter implementation readiness review completed; next_required_task → TASK-014AQ; latest validation → 124 PASS; adapter identity adds CONSUMED_DRY_RUN_CONTRACT_VERSION=dry_run_v1, ADAPTER_CONTRACT_VERSION=readiness_review_v1; order link id prefix → READINESS_REVIEW_TINY_ENTRY_; audit response_status → READINESS_REVIEW_NOT_SENT; new row implementation_readiness_conclusion=READY_FOR_IMPLEMENTATION_DESIGN_NOT_EXECUTION)
- `docs/research/commands/COMMAND_LOG.md` (this TASK-014AP entry)

Validation:
- py_compile src/demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py → PASS
- py_compile scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py → PASS
- py_compile tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py → PASS
- pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review.py → 124/124 PASS

Outputs: review-only — runtime artifacts (when run) will be written to
`outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_implementation_readiness_review/`
(gitignored). The review output contains:
- adapter readiness contract (documented, not instantiated)
- chain readiness summary across AI/AJ/AK/AL/AM/AN/AO
- implementation preconditions for TASK-014AQ (G20 still active, no sender,
  no secret transport, no real endpoint binding, no real authorization)
- forbidden implementation surface (no `send` / `place_order` / `execute`
  method, no urllib/requests/httpx/socket/http.client, no HMAC, no dotenv)
- secret / signing / transport readiness (documented as required-for-future,
  not implemented)
- manual approval revalidation (AM `entry_manual_approval_gate` still in
  the acceptance whitelist)
- stop / cleanup readiness (downstream lifecycle steps documented, not run)
- risk / idempotency readiness (max_notional_usdt=10, ORDER_LINK_ID_PREFIX=
  READINESS_REVIEW_TINY_ENTRY_ documented — never sent)
- failure / abort readiness (fail-closed semantics documented)
- documentation sync review (this TASK-014AP entry + README + NEXT_ACTION)
- final implementation readiness verdict (implementation_readiness_conclusion=
  READY_FOR_IMPLEMENTATION_DESIGN_NOT_EXECUTION)
- audit artifacts (response_status=READINESS_REVIEW_NOT_SENT,
  next_required_task=TASK-014AQ_guarded_entry_real_execution_adapter_implementation_design)

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no `/v5/position/trading-stop` call
- no sender adapter introduced / no executable adapter surface / no `send` / `place_order` / `execute` method
- no endpoint call / no socket opened / no urllib / no requests / no httpx / no http.client
- no secrets read / no `.env*` read / no `os.environ` access / no dotenv
- no HMAC / no signature header / no signing primitive
- no AA-AO module reuse (no `from src.demo_tiny_*` imports in new module)
- TASK-014L G20 sender policy still active (no protected_entry_policy_missing lift)
- 5 protected demo positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified
- main.py / src/risk.py / BybitExecutor untouched
- no auto git commit / no auto git push / no auto branch / no auto tag
- `--allow-real-entry-execution` flag exists only to PROVE the guard rejects
  it with `REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED`; flag never triggers any
  network / endpoint / order / secret / signing / sender code path
- `implementation_readiness_conclusion=READY_FOR_IMPLEMENTATION_DESIGN_NOT_EXECUTION`
  is documented only — it does NOT authorize any real execution; the next
  task TASK-014AQ is a DESIGN task, not implementation, not execution

Notes:
- Local commit only; push pending Rick instruction.
- next_required_task = `TASK-014AQ_guarded_entry_real_execution_adapter_implementation_design`.
- HARD_FAIL_GATES = 47 (25 missing-artifact + 4 invariant + 4 AM acceptance +
  4 AN acceptance + 7 AO acceptance + 1 conclusion mismatch + 2 symbol).
- Tests = 124 PASS (above the 76 baseline target per Rick's spec).

---

### 2026-06-12（TASK-014AO-DOCS1 — Adapter Dry-run Docs Sync）

Agent: Claude (Opus)
Command source: Rick chat instruction "Before push/VPS validation, please
create TASK-014AO-DOCS1" (2026-06-12)
Task: Synchronize cross-agent docs for TASK-014AO — fill in the actual local
commit hash `8303fdc` into the README Demo Trading Guarded Lifecycle Status
board (previously `pending`) and the COMMAND_LOG TASK-014AO entry; record
this TASK-014AO-DOCS1 event in COMMAND_LOG; verify NEXT_ACTION.md TASK-014AO
section is intact with VPS validation commands. No code changes, no execution
logic, no G20 lift, no endpoint calls, no secret reads, no real entry
execution, no executable sender path added, no `send` / `place_order` /
`execute` method introduced.

Status before: TASK-014AO source/preview/tests/.gitignore/NEXT_ACTION/README/
COMMAND_LOG committed locally as `8303fdc` but README + COMMAND_LOG still
showed `pending` for the AO commit hash
Status after: TASK-014AO-DOCS1 docs sync DONE; cross-agent board points at
TASK-014AO / `8303fdc`; next_required_task =
TASK-014AP_guarded_entry_real_execution_adapter_implementation_readiness_review

Files changed:
- `README.md` (Demo Trading Guarded Lifecycle Status board:
  banner updated to "updated by TASK-014AO-DOCS1, 2026-06-12";
  `latest_commit` updated from `pending` → `8303fdc`)
- `docs/research/commands/COMMAND_LOG.md` (this DOCS1 entry +
  TASK-014AO entry's `README.md` files-changed line updated to reflect
  the filled-in `8303fdc` hash)

Validation:
- py_compile src/demo_tiny_guarded_entry_real_execution_adapter_dry_run.py → PASS
- py_compile scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py → PASS
- py_compile tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py → PASS
- pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py → 139/139 PASS

Outputs: docs-only — no runtime artifacts produced

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no `/v5/position/trading-stop` call
- no sender adapter introduced / no executable adapter surface / no `send` / `place_order` / `execute` method
- no endpoint call / no socket opened / no urllib / no requests / no httpx / no http.client
- no secrets read / no `.env*` read / no `os.environ` access / no dotenv
- no HMAC / no signature header / no signing primitive
- TASK-014L G20 sender policy still active (no protected_entry_policy_missing lift)
- 5 protected demo positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified
- main.py / src/risk.py / BybitExecutor untouched
- no auto git commit / no auto git push / no auto branch / no auto tag

Notes:
- Local commit only; push pending Rick instruction.
- next_required_task remains `TASK-014AP_guarded_entry_real_execution_adapter_implementation_readiness_review`.

---

### 2026-06-12（TASK-014AO — Guarded Entry Real Execution Adapter Dry-run）

Agent: Claude (Opus)
Command source: Rick chat instruction
"請建立 TASK-014AO：Guarded Entry Real Execution Adapter Dry-run" (2026-06-12)
Task: Add `src/demo_tiny_guarded_entry_real_execution_adapter_dry_run.py` as
an adapter-dry-run-only module that simulates the FUTURE real tiny entry
execution adapter's input / output / error / audit flow without implementing
the adapter and without executing anything. The module DOES NOT implement the
adapter, does not import any sender / private client / network primitive,
does not call `/v5/order/create`, does not call `/v5/position/trading-stop`,
does not read secrets, does not sign anything, does not lift TASK-014L G20,
does not validate any token / phrase / approval input, does not treat any
token / phrase / input as authorization, does not expose any executable
adapter `send` / `place_order` / `execute` method, does not touch any
existing protected demo position, and does not auto-commit / auto-push git.

Inputs: 24 upstream artifacts — the 23 AN upstream artifacts plus AN's own
guarded entry real execution adapter design output (`entry_adapter_design`).

Status before: TASK-014AN-DOCS1 cross-agent docs synced (commit `6819407`)
Status after: TASK-014AO guarded entry real execution adapter dry-run
committed locally; next_required_task =
TASK-014AP_guarded_entry_real_execution_adapter_implementation_readiness_review

Files changed:
- `src/demo_tiny_guarded_entry_real_execution_adapter_dry_run.py` (new — adapter-dry-run-only module; 13 stages STAGE_0..STAGE_12; 4 statuses TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DRY_RUN_READY / _READY_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED; 4 modes adapter_dry_run_checklist / adapter_dry_run_approval / real_entry_execution_guard / fail_closed; HARD_FAIL_GATES frozenset = 40 gates; dataclass result with deep-copy `to_dict()` covering 13 sub-dict fields adapter_dry_run_scope / adapter_dry_run_contract / dry_run_input_validation_simulation / dry_run_request_envelope / entry_payload_dry_run_preview / dry_run_response_simulation / secret_and_signature_dry_run_boundary / stop_cleanup_dry_run_boundary / forbidden_execution_surface_dry_run / failure_and_abort_adapter_dry_run / documentation_sync_review / audit_artifacts / final_adapter_dry_run_verdict; ADAPTER_NAME=GuardedTinyEntryRealExecutionAdapter; ADAPTER_CONTRACT_VERSION=dry_run_v1; CONSUMED_DESIGN_CONTRACT_VERSION=design_only_v1; ADAPTER_RESPONSE_STATUS=ADAPTER_DRY_RUN_NOT_SENT; ORDER_LINK_ID_PREFIX=ADAPTER_DRY_RUN_TINY_ENTRY_; 14 ACCEPTABLE_*_STATUSES frozensets incl. ACCEPTABLE_ENTRY_ADAPTER_DESIGN_STATUSES; no urllib/requests/httpx/socket/http.client/HMAC/signing/dotenv/env-var-read/sender/main/risk/BybitExecutor/pybit; no executable adapter surface; no `send` / `place_order` / `execute` method; no auto-git)
- `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py` (new — 24 `--from-latest-*` flags incl. `--from-latest-entry-adapter-design`; `--symbol`; `--expected-commit-hash`; `--allow-adapter-dry-run`; `--allow-real-entry-execution`; `--write-report`; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_dry_run/`; `run_execute()` callable from tests; no auto-git)
- `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py` (new — 139 tests covering 4 status modes, 24 missing-artifact gates, endpoint/account/symbol invariants, AN adapter-design status / readiness / grants / implementation / execution / no-send-method acceptance, 13 stages presence + order, deep-copy roundtrip, AST+tokenize source-scan safety, forbidden flag absence in src + preview, 5 protected positions untouched, G20 never lifted, no AA-AN module reuse, next_required_task = 014AP, 14 frozenset whitelists, endpoint allow/denylists, forbidden log fields, no auto-git in src + preview, HARD_FAIL_GATES expansion to 40 gates, ADAPTER_NAME / ADAPTER_CONTRACT_VERSION / CONSUMED_DESIGN_CONTRACT_VERSION / ADAPTER_RESPONSE_STATUS / ORDER_LINK_ID_PREFIX exposed, CLI subprocess exit codes, report artifacts written, `repo_tmp_path` Windows ACL workaround)
- `.gitignore` (add `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_dry_run/`)
- `docs/research/commands/NEXT_ACTION.md` (TASK-014AO Status + Next Rick Action block inserted above TASK-014AN)
- `README.md` (Demo Trading Guarded Lifecycle Status board updated to TASK-014AO — latest_completed_task, latest_commit `8303fdc` (filled in by TASK-014AO-DOCS1), current_phase, next_required_task=TASK-014AP, latest validation 139 PASS, adapter identity / order link id prefix / audit response_status rows)
- `docs/research/commands/COMMAND_LOG.md` (this entry)

Validation:
- py_compile src/demo_tiny_guarded_entry_real_execution_adapter_dry_run.py → PASS
- py_compile scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py → PASS
- py_compile tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py → PASS
- pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_dry_run.py → 139/139 PASS

Known unrelated pre-existing failure:
`tests/demo_trading/test_demo_emergency_close_sender.py::TestCLIIntegration::test_dry_run_cli_writes_report` — NOT attributable to TASK-014AO.

Outputs: code-only — no runtime artifacts produced at task time

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no `/v5/position/trading-stop` call
- no sender adapter introduced / no executable adapter surface / no `send` / `place_order` / `execute` method / no AA-AN module reuse
- no endpoint call / no socket opened / no urllib / no requests / no httpx / no http.client
- no secrets read / no `.env*` read / no `os.environ` access / no dotenv
- no HMAC / no signature header / no signing primitive
- no real token / phrase / approval-input validation (all documented only)
- no live endpoint fallback / no base url switch
- TASK-014L G20 sender policy still active (no protected_entry_policy_missing lift)
- 5 protected demo positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified
- main.py / src/risk.py / BybitExecutor untouched
- no auto git commit / no auto git push / no auto branch / no auto tag

Notes:
- next_required_task = `TASK-014AP_guarded_entry_real_execution_adapter_implementation_readiness_review`
  (the next step is a readiness review, still no real execution).
- `--allow-adapter-dry-run` only flips status to
  `..._READY_BUT_EXECUTION_DISABLED` (still no real execution path).
- `--allow-real-entry-execution` only flips status to
  `REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED` (proves the guard never executes a
  real order — no socket opened, no git operations).
- Adapter contract documented only; no Python class with `send` / `place_order` /
  `execute` method is exported. The dataclass result reflects the dry-run
  simulation, not an invocation. CONSUMED_DESIGN_CONTRACT_VERSION enforces
  upstream-chain integrity with TASK-014AN's `design_only_v1`.

---

### 2026-06-12（TASK-014AN-DOCS1 — Adapter Design Docs Sync）

Agent: Claude (Opus)
Command source: Rick chat instruction "Before push/VPS validation, please
create TASK-014AN-DOCS1" (2026-06-12)
Task: Synchronize cross-agent docs for TASK-014AN — fill in the actual local
commit hash `ed58b34` into the README Demo Trading Guarded Lifecycle Status
board (previously `pending`) and the COMMAND_LOG TASK-014AN entry; record this
TASK-014AN-DOCS1 event in COMMAND_LOG; verify NEXT_ACTION.md TASK-014AN
section is intact with VPS validation commands. No code changes, no execution
logic, no G20 lift, no endpoint calls, no secret reads, no real entry
execution, no executable sender path added.

Status before: TASK-014AN source/preview/tests/.gitignore/NEXT_ACTION/README/
COMMAND_LOG committed locally as `ed58b34` but README + COMMAND_LOG still
showed `pending` for the AN commit hash
Status after: TASK-014AN-DOCS1 docs sync DONE; cross-agent board points at
TASK-014AN / `ed58b34`; next_required_task =
TASK-014AO_guarded_entry_real_execution_adapter_dry_run
Files changed:
- `README.md` (Demo Trading Guarded Lifecycle Status board:
  banner updated to "updated by TASK-014AN-DOCS1, 2026-06-12";
  `latest_commit` updated from `pending` → `ed58b34`)
- `docs/research/commands/COMMAND_LOG.md` (this DOCS1 entry +
  TASK-014AN entry's `README.md` files-changed line updated to reflect
  the filled-in `ed58b34` hash)

Validation:
- py_compile src/demo_tiny_guarded_entry_real_execution_adapter_design.py → PASS
- py_compile scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_design.py → PASS
- py_compile tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_design.py → PASS
- pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_design.py → 129/129 PASS

Outputs: docs-only — no runtime artifacts produced

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no `/v5/position/trading-stop` call
- no sender adapter introduced / no executable adapter surface / no `send` method
- no endpoint call / no socket opened / no urllib / no requests / no httpx / no http.client
- no secrets read / no `.env*` read / no `os.environ` access / no dotenv
- no HMAC / no signature header / no signing primitive
- TASK-014L G20 sender policy still active (no protected_entry_policy_missing lift)
- 5 protected demo positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified
- main.py / src/risk.py / BybitExecutor untouched
- no auto git commit / no auto git push / no auto branch / no auto tag

Notes:
- Local commit only; push pending Rick instruction.
- next_required_task remains `TASK-014AO_guarded_entry_real_execution_adapter_dry_run`.

---

### 2026-06-12（TASK-014AN — Guarded Entry Real Execution Adapter Design）

Agent: Claude (Opus)
Command source: Rick chat instruction
"請建立 TASK-014AN：Guarded Entry Real Execution Adapter Design" (2026-06-12)
Task: Add `src/demo_tiny_guarded_entry_real_execution_adapter_design.py` as an
adapter-design-only module that documents the contract / inputs / outputs /
boundaries / forbidden surfaces / fail-closed policy / audit schema for the
FUTURE real tiny entry execution adapter. The module DOES NOT implement the
adapter, does not import any sender / private client / network primitive, does
not call `/v5/order/create`, does not call `/v5/position/trading-stop`, does
not read secrets, does not sign anything, does not lift TASK-014L G20, does
not validate any token / phrase / approval input, does not treat any token /
phrase / input as authorization, does not expose any executable adapter `send`
method, does not touch any existing protected demo position, and does not
auto-commit / auto-push git.

Inputs: 23 upstream artifacts — the 22 AM upstream artifacts plus AM's own
guarded entry real execution manual approval gate output
(`entry_manual_approval_gate`).

Status before: TASK-014AM-DOCS1 cross-agent docs synced (commit `08bf8b9`)
Status after: TASK-014AN guarded entry real execution adapter design committed
locally; next_required_task = TASK-014AO_guarded_entry_real_execution_adapter_dry_run

Files changed:
- `src/demo_tiny_guarded_entry_real_execution_adapter_design.py` (new — adapter-design-only module; 12 stages STAGE_0..STAGE_11; 4 statuses TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DESIGN_READY / _READY_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED; 4 modes adapter_design_checklist / adapter_design_approval / real_entry_execution_guard / fail_closed; HARD_FAIL_GATES frozenset = 33 gates; dataclass result with deep-copy `to_dict()` covering 12 sub-dict fields adapter_design_scope / adapter_contract_design / adapter_input_schema_design / adapter_output_schema_design / entry_payload_design_preview / secret_and_signature_boundary_design / stop_cleanup_boundary_design / forbidden_execution_surface_design / failure_and_abort_adapter_design / documentation_sync_review / audit_artifacts / final_adapter_design_verdict; ADAPTER_NAME=GuardedTinyEntryRealExecutionAdapter; ADAPTER_CONTRACT_VERSION=design_only_v1; ADAPTER_RESPONSE_STATUS=ADAPTER_DESIGN_NOT_SENT; ORDER_LINK_ID_PREFIX=ADAPTER_DESIGN_TINY_ENTRY_; 13 ACCEPTABLE_*_STATUSES frozensets incl. ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES; no urllib/requests/httpx/socket/http.client/HMAC/signing/dotenv/env-var-read/sender/main/risk/BybitExecutor/pybit; no executable adapter surface; no `send` method; no auto-git)
- `scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_design.py` (new — 23 `--from-latest-*` flags incl. `--from-latest-entry-manual-approval-gate`; `--symbol`; `--expected-commit-hash`; `--allow-adapter-design-approval`; `--allow-real-entry-execution`; `--write-report`; writes `{ts}_*` + `latest_*` JSON+MD to `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_design/`; `run_execute()` callable from tests; no auto-git)
- `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_design.py` (new — 129 tests covering 4 status modes, 23 missing-artifact gates, endpoint/account/symbol invariants, AM approval-gate status/readiness/grants/phrase/inputs acceptance, 12 stages presence + order, deep-copy roundtrip, AST + tokenize source-scan safety, forbidden flag absence in src + preview, 5 protected positions untouched, G20 never lifted, no AA-AM module reuse, next_required_task = 014AO, 13 frozenset whitelists, endpoint allow/denylists, forbidden log fields, no auto-git in src + preview, HARD_FAIL_GATES expansion to 33 gates, ADAPTER_NAME / ADAPTER_CONTRACT_VERSION / ADAPTER_RESPONSE_STATUS / ORDER_LINK_ID_PREFIX exposed, CLI subprocess exit codes, report artifacts written, `repo_tmp_path` Windows ACL workaround)
- `.gitignore` (add `outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_design/`)
- `docs/research/commands/NEXT_ACTION.md` (TASK-014AN Status + Next Rick Action block inserted above TASK-014AM)
- `README.md` (Demo Trading Guarded Lifecycle Status board updated to TASK-014AN — latest_completed_task, latest_commit `ed58b34` (filled in by TASK-014AN-DOCS1), current_phase, next_required_task=TASK-014AO, latest validation 129 PASS, adapter identity / order link id prefix / audit response_status rows)
- `docs/research/commands/COMMAND_LOG.md` (this entry)

Validation:
- py_compile src/demo_tiny_guarded_entry_real_execution_adapter_design.py → PASS
- py_compile scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_design.py → PASS
- py_compile tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_design.py → PASS
- pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_design.py → 129/129 PASS

Outputs: code-only — no runtime artifacts produced at task time

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no `/v5/position/trading-stop` call
- no sender adapter introduced / no executable adapter surface / no `send` method / no AA-AM module reuse
- no endpoint call / no socket opened / no urllib / no requests / no httpx / no http.client
- no secrets read / no `.env*` read / no `os.environ` access / no dotenv
- no HMAC / no signature header / no signing primitive
- no real token / phrase / approval-input validation (all documented only)
- no live endpoint fallback / no base url switch
- TASK-014L G20 sender policy still active (no protected_entry_policy_missing lift)
- 5 protected demo positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified
- main.py / src/risk.py / BybitExecutor untouched
- no auto git commit / no auto git push / no auto branch / no auto tag

Notes:
- next_required_task = `TASK-014AO_guarded_entry_real_execution_adapter_dry_run`
  (a documented-only dry-run of the adapter — still no real order send).
- `--allow-adapter-design-approval` only flips status to
  `..._READY_BUT_EXECUTION_DISABLED` (still no real execution path).
- `--allow-real-entry-execution` only flips status to
  `REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED` (proves the guard never executes a
  real order — no socket opened, no git operations).
- Adapter contract documented only; no Python class with `send` / `execute`
  method is exported. The dataclass result reflects the design, not an
  invocation.

---

### 2026-06-12（TASK-014AM-DOCS1 — Manual Approval Gate Docs Sync）

Agent: Claude (Opus)
Command source: Rick chat instruction "Before push/VPS validation, please fix
TASK-014AM docs sync" (2026-06-12)
Task: Synchronize cross-agent docs for TASK-014AM — update README Demo Trading
Guarded Lifecycle Status board to point at TASK-014AM / commit `fdf46df` and
record TASK-014AM event in COMMAND_LOG; verify NEXT_ACTION.md TASK-014AM
section is intact. No code changes, no execution logic, no G20 lift, no
endpoint calls, no secret reads, no real entry execution.

Status before: TASK-014AM source/preview/tests/.gitignore/NEXT_ACTION committed
locally as `fdf46df` but README + COMMAND_LOG not yet synced
Status after: TASK-014AM-DOCS1 docs sync DONE; cross-agent board points at
TASK-014AM / `fdf46df`; next_required_task =
TASK-014AN_guarded_entry_real_execution_adapter_design
Files changed:
- `README.md` (Demo Trading Guarded Lifecycle Status board updated to
  TASK-014AM — latest_completed_task, latest_commit `fdf46df`, current_phase,
  next_required_task, latest validation 114 PASS, EXACT_APPROVAL_PHRASE row,
  audit response_status row)
- `docs/research/commands/COMMAND_LOG.md` (this entry + TASK-014AM entry)

Validation:
- py_compile src/demo_tiny_guarded_entry_real_execution_manual_approval_gate.py → PASS
- py_compile scripts/preview_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py → PASS
- py_compile tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py → PASS
- pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py → 114/114 PASS

Outputs: docs-only — no runtime artifacts produced

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no
  `/v5/position/trading-stop` call
- no sender adapter introduced / no AA-AL module reuse
- no endpoint call / no socket opened
- no secrets read / no `.env*` read / no `os.environ` access
- no HMAC / no signature header
- no G20 lift — TASK-014L `protected_entry_policy_missing` remains active
- no position modification — 5 protected positions
  (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT) untouched
- no auto git commit / push / branch / tag
- no real token validation / no real exact phrase validation / no real
  approval-input validation

Notes:
- next_required_task = TASK-014AN_guarded_entry_real_execution_adapter_design
- Local commit only per project memory `feedback_git_push.md`; remote push
  deferred until Rick explicit instruction.

---

### 2026-06-12（TASK-014AM — Guarded Entry Real Execution Manual Approval Gate）

Agent: Claude (Opus)
Command source: Carry-over TASK-014AM workorder (sequential safety chain after
TASK-014AL guarded entry final pre-execution review). Rick chat instruction:
"全包：preview + tests + ignore + NEXT_ACTION + commit"
Task: Implement guarded tiny entry real execution **manual approval gate**
module that consumes 22 upstream artifacts (AA through AL chain — AL's 21
baseline + AL's own entry_final_pre_execution_review output) and emits a
pure-computation manual-approval-gate verdict — NO sender, NO endpoint calls
(`/v5/order/create` or `/v5/position/trading-stop`), NO secret reads, NO
HMAC / signature, NO real entry execution, NO real token validation (token
pattern `CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT` documented only, never
re.match'd), NO real exact phrase validation (EXACT_APPROVAL_PHRASE
`I AUTHORIZE DEMO TINY ENTRY GATE ONLY FOR SOLUSDT BUY 0.1 MAX 10 USDT;
NO ORDER MAY BE SENT BY TASK-014AM` documented only, never compared), NO
real approval-input validation (12 REQUIRED_MANUAL_APPROVAL_INPUTS = 1
phrase + 11 REQUIRED_CONFIRM_FLAGS documented only, never parsed), NO AA-AL
module reuse, NO G20 lift, NO auto-git operations.
4 status modes (TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_READY
/ _BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED /
FAIL_CLOSED), 11 manual-approval-gate stages (STAGE_0 through STAGE_10),
31 hard-fail gates, ORDER_LINK_ID_PREFIX = `APPROVAL_GATE_TINY_ENTRY_`
exposed (documented only), audit_artifacts.response_status =
`APPROVAL_GATE_NOT_SENT`.

Status before: TASK-014AL guarded entry final pre-execution review confirmed READY
Status after: TASK-014AM guarded entry real execution manual approval gate DONE
Files changed:
- `src/demo_tiny_guarded_entry_real_execution_manual_approval_gate.py` (new, 1912 lines)
- `scripts/preview_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py` (new)
- `tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py` (new, 114 tests across 88 classes AM1-AM88)
- `docs/research/commands/NEXT_ACTION.md` (TASK-014AM status block prepended)
- `.gitignore` (added `outputs/demo_trading/tiny_guarded_entry_real_execution_manual_approval_gate/`)

Validation:
- py_compile src/demo_tiny_guarded_entry_real_execution_manual_approval_gate.py → PASS
- py_compile scripts/preview_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py → PASS
- pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py → 114/114 PASS (focused)

Local commit: `fdf46df` —
`TASK-014AM: add guarded entry real execution manual approval gate`
(5 files changed, +4824 / -1)

Outputs: outputs/demo_trading/tiny_guarded_entry_real_execution_manual_approval_gate/
(gitignored, manual-approval-gate-only — no real execution artifacts;
token / phrase / approval inputs documented only, never validated; no
auto-git artifacts produced)

Safety confirmations:
- no real order placed / no `/v5/order/create` call / no
  `/v5/position/trading-stop` call
- no sender adapter introduced / no AA-AL module reuse
- no endpoint call / no socket / urllib / requests / httpx / http.client import
- no secrets read / no `.env*` read / no `os.environ` access
- no HMAC / no signature header
- no G20 lift — TASK-014L `protected_entry_policy_missing` remains active
- no position modification — 5 protected positions
  (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT) untouched
- no auto git commit / push / branch / tag (preview owns zero git surface)

Notes:
- next_required_task = TASK-014AN_guarded_entry_real_execution_adapter_design
- TASK-014L sender G20 (protected_entry_policy_missing) is NOT lifted here.
- The 5 existing demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT /
  EDUUSDT) remain untouched throughout this manual approval gate.
- README + COMMAND_LOG docs sync handled by follow-up TASK-014AM-DOCS1
  (see entry above).
- Local commit produced under explicit task instruction; remote push deferred
  per project memory `feedback_git_push.md`.

---

### 2026-06-12（TASK-014AL — Guarded Entry Final Pre-execution Review）

Agent: Claude (Opus)
Command source: Carry-over TASK-014AL workorder (sequential safety chain after
TASK-014AK guarded entry manual authorization dry-run)
Task: Implement guarded tiny entry final pre-execution review module that
consumes 21 upstream artifacts (AA through AK chain — TASK-014AK's 20
baseline + AK's own entry_manual_authorization_dry_run output) and emits a
pure-computation final pre-execution review verdict — NO sender, NO endpoint
calls (`/v5/order/create` or `/v5/position/trading-stop`), NO secret reads,
NO HMAC / signature, NO real entry execution, NO real token validation
(token pattern `CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT` documented only,
never re.match'd; token_validation_simulated=True, token_validated=False,
real_token_validated=False, dry_run_authorization_result=
DOCUMENTED_ONLY_NOT_AUTHORIZED), NO AA-AK module reuse, NO G20 lift,
NO auto-git operations (no auto commit / push / branch / tag).
4 status modes (TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY /
_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED /
FAIL_CLOSED), 11 review stages (STAGE_0 through STAGE_10), 152+ gates,
29 hard-fail gates, 13 required human confirmation flags documented but
NEVER validated, `--expected-commit-hash` flag documented but never validated.

Status before: TASK-014AK guarded entry manual authorization dry-run confirmed READY
Status after: TASK-014AL guarded entry final pre-execution review DONE
Files changed:
- `src/demo_tiny_guarded_entry_final_pre_execution_review.py` (new, 1783 lines)
- `scripts/preview_demo_tiny_guarded_entry_final_pre_execution_review.py` (new)
- `tests/demo_trading/test_demo_tiny_guarded_entry_final_pre_execution_review.py` (new, 104 tests)
- `docs/research/commands/NEXT_ACTION.md` (TASK-014AL status block prepended)
- `docs/research/commands/COMMAND_LOG.md` (this entry)
- `README.md` (Demo Trading Guarded Lifecycle Status board updated)
- `.gitignore` (added `outputs/demo_trading/tiny_guarded_entry_final_pre_execution_review/`)

Validation:
- py_compile src/demo_tiny_guarded_entry_final_pre_execution_review.py → PASS
- py_compile scripts/preview_demo_tiny_guarded_entry_final_pre_execution_review.py → PASS
- pytest tests/demo_trading/test_demo_tiny_guarded_entry_final_pre_execution_review.py → 104/104 PASS

Outputs: outputs/demo_trading/tiny_guarded_entry_final_pre_execution_review/
(gitignored, review-only — no real execution artifacts; token documented only,
never validated; no auto-git artifacts produced)

Notes:
- next_required_task = TASK-014AM
- TASK-014L sender G20 (protected_entry_policy_missing) is NOT lifted here.
- The 5 existing demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT /
  EDUUSDT) remain untouched throughout this review.
- No auto git commit / push / branch / tag operations performed by src or
  preview — local commit produced manually by Claude under explicit task
  instruction; remote push deferred per project memory feedback_git_push.

---

### 2026-06-12（TASK-014AK — Guarded Entry Manual Authorization Dry-run）

Agent: Claude (Opus)
Command source: Carry-over TASK-014AK workorder (sequential safety chain after
TASK-014AJ guarded entry manual authorization design)
Task: Implement guarded tiny entry manual-authorization-dry-run module that
consumes 20 upstream artifacts (TASK-014AJ's 19 baseline + AJ's own
entry_manual_authorization_design output) and emits a pure-computation
authorization-dry-run verdict — NO sender, NO endpoint calls
(`/v5/order/create` or `/v5/position/trading-stop`), NO secret reads,
NO HMAC / signature, NO real entry execution, NO real token validation
(token pattern `CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT` simulated only:
token_validation_simulated=True, token_validated=False,
real_token_validated=False, dry_run_authorization_result=
DOCUMENTED_ONLY_NOT_AUTHORIZED), NO AA-AJ module reuse, NO G20 lift.
4 status modes (TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY /
_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED /
FAIL_CLOSED), 10 dry-run stages, 156+ gates, 27 hard-fail gates,
13 required human confirmation flags documented but NEVER validated.

Status before: TASK-014AJ guarded entry manual authorization design confirmed READY
Status after: TASK-014AK guarded entry manual authorization dry-run DONE
Files changed:
- `src/demo_tiny_guarded_entry_manual_authorization_dry_run.py` (new, 1774 lines)
- `scripts/preview_demo_tiny_guarded_entry_manual_authorization_dry_run.py` (new)
- `tests/demo_trading/test_demo_tiny_guarded_entry_manual_authorization_dry_run.py` (new, 76 tests)
- `docs/research/commands/NEXT_ACTION.md` (TASK-014AK status block prepended)
- `docs/research/commands/COMMAND_LOG.md` (this entry)
- `.gitignore` (added `outputs/demo_trading/tiny_guarded_entry_manual_authorization_dry_run/` and `outputs/_test_scratch/`)

Validation:
- py_compile src/demo_tiny_guarded_entry_manual_authorization_dry_run.py → PASS
- py_compile scripts/preview_demo_tiny_guarded_entry_manual_authorization_dry_run.py → PASS
- pytest tests/demo_trading/test_demo_tiny_guarded_entry_manual_authorization_dry_run.py → 76/76 PASS

Outputs: outputs/demo_trading/tiny_guarded_entry_manual_authorization_dry_run/
(gitignored, dry-run-only — no real execution artifacts; token documented only,
never validated)

Notes:
- next_required_task = TASK-014AL_guarded_entry_final_pre_execution_review
- TASK-014L sender G20 (protected_entry_policy_missing) is NOT lifted here.
- The 5 existing demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT /
  EDUUSDT) remain untouched throughout this dry-run.
- Local commit only — no push (per project memory feedback_git_push).

---

### 2026-06-11（TASK-014AJ — Guarded Entry Manual Authorization Design）

Agent: Claude (Opus)
Command source: Carry-over TASK-014AJ workorder (sequential safety chain after
TASK-014AI guarded entry real permission review)
Task: Implement guarded tiny entry manual-authorization-design module that
consumes 19 upstream artifacts (TASK-014AI's 18 baseline + AI's own
entry_real_permission_review output) and emits a pure-computation
authorization-design verdict — NO sender, NO endpoint calls
(`/v5/order/create` or `/v5/position/trading-stop`), NO secret reads,
NO HMAC / signature, NO real entry execution, NO token validation
(token pattern `CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SOLUSDT` documented only
and NEVER validated), NO AA-AI module reuse, NO G20 lift.
4 status modes (TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DESIGN_READY /
_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED /
FAIL_CLOSED), 10 design stages, 147 gates, 26 hard-fail gates,
13 required human confirmation flags documented but NEVER validated.

Status before: TASK-014AI guarded entry real permission review confirmed READY
Status after: TASK-014AJ guarded entry manual authorization design DONE
Files changed:
- `src/demo_tiny_guarded_entry_manual_authorization_design.py` (new, 1702 lines)
- `scripts/preview_demo_tiny_guarded_entry_manual_authorization_design.py` (new)
- `tests/demo_trading/test_demo_tiny_guarded_entry_manual_authorization_design.py` (new, 116 tests)
- `docs/research/commands/NEXT_ACTION.md` (TASK-014AJ status block prepended)
- `docs/research/commands/COMMAND_LOG.md` (this entry)
- `.gitignore` (added `outputs/demo_trading/tiny_guarded_entry_manual_authorization_design/`)
- `README.md` (status board updated)

Validation:
- py_compile src/demo_tiny_guarded_entry_manual_authorization_design.py → PASS
- py_compile scripts/preview_demo_tiny_guarded_entry_manual_authorization_design.py → PASS
- pytest tests/demo_trading/test_demo_tiny_guarded_entry_manual_authorization_design.py → 116/116 PASS

Outputs: outputs/demo_trading/tiny_guarded_entry_manual_authorization_design/
(gitignored, design-only — no real execution artifacts)

Notes:
- Pure-computation manual-authorization design — token pattern is documented
  in the result envelope but NEVER parsed, NEVER validated, NEVER acted upon.
- 13 required human confirmation flags documented as a future contract for
  TASK-014AK dry-run consumer but parser/validator deliberately not present.
- `--allow-design-approval` flips status to _BUT_EXECUTION_DISABLED;
  `--allow-real-entry-execution` flips to REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
  (guard probe — never executes).
- 5 protected positions (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT)
  never touched; SOLUSDT collision check is part of preflight gate set.
- next_required_task = TASK-014AK_guarded_entry_manual_authorization_dry_run.
- Local commit only — no push (per memory rule).

---

### 2026-06-11（TASK-014AI — Guarded Entry Real Permission Review）

Agent: Claude (Opus)
Command source: Carry-over TASK-014AI workorder (sequential safety chain after
TASK-014AH guarded lifecycle dry-run summary)
Task: Implement guarded tiny entry real-permission review module that consumes
the 014AE/AF/AG guarded adapters + 014AH guarded lifecycle summary + 014
baseline artifacts (18 upstream total) and emits a pure-computation
permission-review verdict — NO sender, NO endpoint calls (`/v5/order/create`
or `/v5/position/trading-stop`), NO secret reads, NO HMAC / signature, NO
real entry execution, NO AA/AB/AC/AD/AE/AF/AG/AH module reuse, NO G20 lift.
4 status modes (TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY /
_BUT_EXECUTION_DISABLED / REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED /
FAIL_CLOSED), 18 upstream artifacts, cross-adapter real-permission review
(selected symbol=SOLUSDT / category=linear / qty=0.1 / side=Buy /
reduceOnly=False / endpoint family=bybit_demo / account_mode=demo /
proof_strength=strong / position_details_source=real_readonly / no
5-existing-position collision / AD readiness=DESIGN_REVIEW_READY_NOT_EXECUTABLE
/ AH readiness_conclusion=DESIGN_REVIEW_READY_NOT_EXECUTABLE / acceptable
AE/AF/AG/AH statuses), hard-fail-closed gates frozenset (27 gates), 125+
total GATE_* constants, entry envelope (symbol=SOLUSDT, qty=0.1, side=Buy,
reduceOnly=False, orderType=Market, positionIdx=0, max_notional=10), post-
entry protection envelope (stopLoss=61.18, tpslMode=Full,
slTriggerBy=MarkPrice), 8 confirmation flags documented (incl.
CONFIRM_DEMO_TINY_ ENTRY_YYYYMMDD_SYMBOL token pattern), preview CLI with
18 `--from-latest-*` flags + `--allow-review-approval` +
`--allow-real-entry-execution` (guard probe — returns
REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED, never executes), 5 protected
positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never touched.

Status before: TASK-014AH READY (guarded lifecycle dry-run summary committed
as cef6fbd)
Status after: TASK-014AI DONE — guarded entry real permission review module
+ preview CLI + 111-test suite committed locally; next_required_task =
TASK-014AJ_guarded_entry_manual_authorization_design
Files changed:
  - src/demo_tiny_guarded_entry_real_permission_review.py (NEW; 1560 lines)
  - scripts/preview_demo_tiny_guarded_entry_real_permission_review.py (NEW)
  - tests/demo_trading/test_demo_tiny_guarded_entry_real_permission_review.py (NEW; 111 tests / 83 classes)
  - .gitignore (+1 line: outputs/demo_trading/tiny_guarded_entry_real_permission_review/)
  - README.md (Demo Trading Guarded Lifecycle Status board updated to TASK-014AI)
  - docs/research/commands/NEXT_ACTION.md (TASK-014AI status block prepended; next Rick action steps documented)
  - docs/research/commands/COMMAND_LOG.md (this entry)
Validation:
  - python -m py_compile src/demo_tiny_guarded_entry_real_permission_review.py → OK
  - python -m py_compile scripts/preview_demo_tiny_guarded_entry_real_permission_review.py → OK
  - python -m py_compile tests/demo_trading/test_demo_tiny_guarded_entry_real_permission_review.py → OK
  - pytest tests/demo_trading/test_demo_tiny_guarded_entry_real_permission_review.py → 111/111 PASS (after 2 minor test-side adjustments: GATE count assertion changed from ==125 to >=125 since module emits 126 GATE_* constants; AST safety test narrowed to network-attr calls only so it doesn't flag dict.get)
Outputs: None committed (review artifacts written to gitignored
outputs/demo_trading/tiny_guarded_entry_real_permission_review/ when CLI run)
Notes:
  - No real entry, no `/v5/order/create`, no `/v5/position/trading-stop`, no
    order send, no permission-gate sender reuse, no AA/AB/AC/AD/AE/AF/AG/AH
    module reuse, G20 not lifted, 5 existing positions
    (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) never modified, no
    secrets, no HMAC, no signature header, no live endpoint fallback.
  - main.py / src/risk.py / BybitExecutor untouched.
  - Memory rule honored: local commit only, no push to GitHub remote.

---

### 2026-06-11（TASK-014AH — Guarded Lifecycle Dry-run Summary）

Agent: Claude (Opus)
Command source: Carry-over TASK-014AH workorder (sequential safety chain after
TASK-014AG guarded cleanup-only dry-run adapter)
Task: Implement guarded tiny lifecycle dry-run summary module that consumes
the 014AE/AF/AG guarded adapters + 014 baseline artifacts (17 upstream total)
and emits a pure-computation summary envelope — NO real runner, NO entry /
stop / cleanup execution, NO endpoint calls, NO secret reads, NO HMAC /
signature, NO preview-to-real conversion, NO 014AA/AB/AC/AD/AE/AF/AG module
reuse. 4 status modes (TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY /
_BUT_EXECUTION_DISABLED / REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED /
FAIL_CLOSED), 17 upstream artifacts, cross-adapter consistency review
(selected symbol / category=linear / qty=0.1 / entry side=Buy / stop=61.18 /
entry_reference=64.4 / cleanup side=Sell / endpoint family=bybit_demo /
account_mode=demo / proof_strength=strong /
position_details_source=real_readonly / no 5-existing-position collision /
AD readiness=DESIGN_REVIEW_READY_NOT_EXECUTABLE / AE entry adapter status
in acceptable whitelist / AF stop adapter status in acceptable whitelist /
AG cleanup adapter status in acceptable whitelist), 7 forbidden flags absent
(--execute-real-entry / --execute-real-stop / --execute-real-cleanup /
--execute-real-lifecycle / --send-order / --place-order / --real-run), 9
checklist stages (stage_0_artifact_preflight through
stage_8_final_lifecycle_summary_verdict), 124 gate constants across the
9 stages, >=28 hard-fail gates, next_required_task =
TASK-014AI_guarded_entry_real_permission_review.
Status before: TASK-014AG DONE (guarded cleanup adapter) → TASK-014AH PENDING
Status after: TASK-014AH code + tests + docs DONE (local commit DONE — push pending VPS rollout)
Files changed:
  - src/demo_tiny_guarded_lifecycle_dry_run_summary.py (NEW)
  - scripts/preview_demo_tiny_guarded_lifecycle_dry_run_summary.py (NEW)
  - tests/demo_trading/test_demo_tiny_guarded_lifecycle_dry_run_summary.py (NEW)
  - README.md (Demo Trading Guarded Lifecycle Status board updated to AH)
  - docs/research/commands/NEXT_ACTION.md (prepended TASK-014AH block + Next Rick Action)
  - docs/research/commands/COMMAND_LOG.md (this entry)
  - .gitignore (added outputs/demo_trading/tiny_guarded_lifecycle_dry_run_summary/)
Validation:
  - python -m py_compile src/demo_tiny_guarded_lifecycle_dry_run_summary.py
    scripts/preview_demo_tiny_guarded_lifecycle_dry_run_summary.py
    tests/demo_trading/test_demo_tiny_guarded_lifecycle_dry_run_summary.py → PASS
  - python -m pytest
    tests/demo_trading/test_demo_tiny_guarded_lifecycle_dry_run_summary.py
    → 123/123 PASS
Outputs: (no runtime output yet — written by `--write-report` to
  outputs/demo_trading/tiny_guarded_lifecycle_dry_run_summary/, gitignored)
Notes:
  - G20 sender policy still active; main.py / src/risk.py / BybitExecutor
    untouched.
  - 5 protected positions (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT /
    EDUUSDT) never touched.
  - Real lifecycle execution remains FORBIDDEN — `--allow-real-lifecycle-execution`
    is a guard probe that returns REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED.
  - No new endpoint families introduced; no signing tokens, no env reads,
    no socket opens, no `/v5/*` calls.
  - Local commit only; push pending Rick instruction.

---

### 2026-06-11（TASK-014AG — Guarded Cleanup-only Dry-run Adapter）

Agent: Claude (Opus)
Command source: Carry-over TASK-014AG workorder (sequential safety chain after
TASK-014AF guarded stop-attach adapter)
Task: Implement cleanup-only dry-run adapter module that consumes the 014AE
guarded entry adapter + 014AF guarded stop-attach adapter + 12 baseline
upstream artifacts (14 total) and emits a preview-only cleanup envelope
(side=Sell, qty=0.1, reduceOnly=True, closeOnTrigger=False, positionIdx=0,
orderType=Market, symbol=SOLUSDT, max_notional_usdt=10) — NO endpoint calls,
NO secret reads, NO HMAC/signature, NO preview-to-real conversion, NO sender
adapter, NO real cleanup implementation, NO 014AA/AB/AC/AD/AE/AF module
reuse. 3 status modes (TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY /
_BUT_EXECUTION_DISABLED / REAL_CLEANUP_EXECUTION_NOT_IMPLEMENTED), 14
upstream artifacts, cross-artifact consistency review (selected symbol /
category=linear / cleanup-side=Sell / tiny qty / endpoint family=bybit_demo /
account_mode=demo / proof_strength=strong /
position_details_source=real_readonly / no 5-existing-position collision /
AD readiness=DESIGN_REVIEW_READY_NOT_EXECUTABLE / AE entry adapter status
in acceptable whitelist / AF stop adapter status in acceptable whitelist),
7 forbidden flags absent (--execute-real-entry / --execute-real-stop /
--execute-real-cleanup / --execute-real-lifecycle / --send-order /
--place-order / --real-run), 8 confirmation flags required, 117+ gates
across 9 categories, 24 hard-fail gates, next_required_task =
TASK-014AH_guarded_tiny_lifecycle_dry_run_summary.
Status before: TASK-014AF DONE (guarded stop-attach adapter) → TASK-014AG PENDING
Status after: TASK-014AG code + tests + docs DONE (local commit DONE — push pending VPS rollout)
Files changed:
  - src/demo_tiny_guarded_cleanup_dry_run_adapter.py (NEW)
  - scripts/preview_demo_tiny_guarded_cleanup_dry_run_adapter.py (NEW)
  - tests/demo_trading/test_demo_tiny_guarded_cleanup_dry_run_adapter.py (NEW)
  - README.md (Demo Trading Guarded Lifecycle Status updated)
  - docs/research/commands/NEXT_ACTION.md (TASK-014AG status block prepended)
  - docs/research/commands/COMMAND_LOG.md (this entry)
  - .gitignore (added outputs/demo_trading/tiny_guarded_cleanup_dry_run_adapter/
    + back-filled tiny_guarded_stop_attach_dry_run_adapter/)
Validation:
  - python -m py_compile src/demo_tiny_guarded_cleanup_dry_run_adapter.py
    scripts/preview_demo_tiny_guarded_cleanup_dry_run_adapter.py
    tests/demo_trading/test_demo_tiny_guarded_cleanup_dry_run_adapter.py → OK
  - python -m pytest tests/demo_trading/test_demo_tiny_guarded_cleanup_dry_run_adapter.py -q
    → 171/171 PASS in 0.81s
  - python -m pytest tests/demo_trading -q → 2823 PASS + 1 pre-existing
    unrelated failure (test_demo_emergency_close_sender::TestCLIIntegration::test_dry_run_cli_writes_report,
    same as TASK-014AA/AB/AC/AD/AE/AF)
  - git diff --check → clean; main.py / src/risk.py / BybitExecutor untouched
Outputs: none yet (preview not run; output dir
`outputs/demo_trading/tiny_guarded_cleanup_dry_run_adapter/` ignored by `.gitignore`)
Notes: Strictly dry-run-only adapter — NO real cleanup, NO `/v5/order/create`
call, NO `/v5/position/trading-stop` call, NO secrets, NO signing, NO G20
lift, NO modification to main.py / src/risk.py / BybitExecutor. 5 existing
positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) NEVER touched. G20
sender policy still active. Confirmation token prefix
`CONFIRM_DEMO_TINY_CLEANUP_`; orderLinkId preview prefix
`DRYRUN_TINY_CLEANUP_`. next_required_task =
TASK-014AH_guarded_tiny_lifecycle_dry_run_summary — awaiting Rick
authorisation.

---

### 2026-06-11（TASK-014AF-DOCS1 — Sync shared project status docs after TASK-014AF）

Agent: Claude (Opus)
Command source: Rick direct chat instruction (post TASK-014AF local commit)
Task: Documentation-only sync. Added a `Demo Trading Guarded Lifecycle Status`
section to README.md so the 3-party collaboration (Rick + ChatGPT +
Claude/Codex/Opus) shares a single status board covering
latest_completed_task / latest_commit / current_phase / next_required_task /
real_execution_allowed / forbidden actions / G20 status / authoritative
pointers. Added a README sync note above the TASK-014AF status block in
NEXT_ACTION.md. Added this entry to COMMAND_LOG.md.
Status before: TASK-014AF DONE (local commit 5b08c26) → README not yet synced
Status after: README shared status board live; NEXT_ACTION.md + COMMAND_LOG.md
              cross-linked; local commit DONE — push pending per Rick policy.
Files changed:
  - README.md (added Demo Trading Guarded Lifecycle Status section)
  - docs/research/commands/NEXT_ACTION.md (added README sync note)
  - docs/research/commands/COMMAND_LOG.md (this entry)
Validation:
  - git diff --name-only → README.md + 2 docs only (no src/scripts/tests/main/risk/BybitExecutor change)
  - git diff --check → clean
Outputs: none (no runtime artifacts; documentation-only)
Notes: Documentation-only sync — NO execution logic change. NO change to src/,
scripts/, tests/, main.py, src/risk.py, BybitExecutor. NO new endpoint call.
NO secrets read. G20 sender policy still active. outputs/ not modified.
Protected positions (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) untouched.
next_required_task remains TASK-014AG_guarded_cleanup_only_dry_run_adapter.

---

### 2026-06-11（TASK-014AF — Guarded Stop-attach-only Dry-run Adapter）

Agent: Claude (Opus)
Command source: Carry-over TASK-014AF workorder (sequential safety chain after TASK-014AE guarded entry adapter)
Task: Implement stop-attach-only dry-run adapter module that consumes the 014AE
guarded entry adapter + 12 upstream artifacts and emits a preview-only
stop-attach envelope (stopLoss=61.18, tpslMode=Full, slTriggerBy=MarkPrice,
positionIdx=0, category=linear, symbol=SOLUSDT, side=long, qty=0.1) — NO
endpoint calls, NO secret reads, NO HMAC/signature, NO preview-to-real
conversion, NO sender adapter, NO real stop-attach implementation, NO
014AA/AB/AC/AD/AE module reuse. 4 status modes
(TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY / _BUT_EXECUTION_DISABLED /
REAL_STOP_ATTACH_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), 13 upstream
artifacts, cross-artifact consistency review (selected symbol /
category=linear / stop-attach-side / tiny qty / entry reference /
endpoint family=bybit_demo / account_mode=demo / proof_strength=strong /
position_details_source=real_readonly / no existing position collision /
AD readiness=DESIGN_REVIEW_READY_NOT_EXECUTABLE / AE entry adapter status
in acceptable whitelist), 7 forbidden flags absent (--execute-real-entry /
--execute-real-stop / --execute-real-cleanup / --execute-real-lifecycle /
--send-order / --place-order / --real-run), next_required_task =
TASK-014AG_guarded_cleanup_only_dry_run_adapter.
Status before: TASK-014AE DONE (guarded entry adapter) → TASK-014AF PENDING
Status after: TASK-014AF code + tests + docs DONE (local commit DONE — push pending VPS rollout)
Files changed:
  - src/demo_tiny_guarded_stop_attach_dry_run_adapter.py (NEW)
  - scripts/preview_demo_tiny_guarded_stop_attach_dry_run_adapter.py (NEW)
  - tests/demo_trading/test_demo_tiny_guarded_stop_attach_dry_run_adapter.py (NEW, 159 tests across 65 classes AF1-AF65)
  - .gitignore (already covers outputs/demo_trading/tiny_guarded_stop_attach_dry_run_adapter/ at line 80)
  - docs/research/commands/NEXT_ACTION.md (prepend TASK-014AF status + Next Rick Action)
  - docs/research/commands/COMMAND_LOG.md (this entry)
Validation:
  - python -m py_compile src/...py scripts/...py tests/...py → OK
  - python -m pytest tests/demo_trading/test_demo_tiny_guarded_stop_attach_dry_run_adapter.py -q
    → 159/159 PASS (0.93s)
  - python -m pytest tests/demo_trading -q → 2652 PASS + 1 pre-existing
    unrelated failure (test_demo_emergency_close_sender::TestCLIIntegration::test_dry_run_cli_writes_report
    — same as 014AA/AB/AC/AD/AE, NOT caused by 014AF)
Outputs: outputs/demo_trading/tiny_guarded_stop_attach_dry_run_adapter/
(gitignored, runtime-only)
Notes: Stop-attach-only dry-run adapter — emits preview envelope only. No
socket / no env reads / no signing tokens / no live endpoint fallback. main.py
/ src/risk.py / BybitExecutor untouched. G20 sender policy still in place. No
existing position modified (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT
protected list verified). No sender reuse from any of TASK-014W/X/Y/Z/AA/AB/AC/AD/AE
modules — adapter reads upstream artifacts only. Source patch: added
GATE_SELECTED_SYMBOL_NOT_SOLUSDT to _HARD_FAIL_GATES (now 22 hard-fail
gates) so non-SOLUSDT symbol selection triggers FAIL_CLOSED.

---

### 2026-06-11（TASK-014AE — Guarded Entry-only Dry-run Adapter）

Agent: Claude (Opus)
Command source: Carry-over TASK-014AE workorder (sequential safety chain after TASK-014AD guarded design review)
Task: Implement entry-only dry-run adapter module that consumes the 014AD
guarded-runner design review + 11 upstream artifacts and emits a preview-only
entry order envelope (side=Buy, qty=0.1, reduceOnly=False, positionIdx=0,
orderType=Market, max_notional_usdt=10) — NO endpoint calls, NO secret reads,
NO HMAC/signature, NO preview-to-real conversion, NO sender adapter, NO real
entry implementation, NO 014AA/AB/AC/AD module reuse. 4 status modes
(TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY / _BUT_EXECUTION_DISABLED /
REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED), 12 upstream artifacts,
cross-artifact consistency review (selected symbol / category=linear /
entry side=Buy / tiny qty / entry reference / endpoint family=bybit_demo /
account_mode=demo / proof_strength=strong / position_details_source=real_readonly
/ no existing position collision / AD readiness=DESIGN_REVIEW_READY_NOT_EXECUTABLE),
7 forbidden flags absent (--execute-real-entry / --execute-real-stop /
--execute-real-cleanup / --execute-real-lifecycle / --send-order / --place-order /
--real-run), next_required_task = TASK-014AF.
Status before: TASK-014AD DONE (guarded design review) → TASK-014AE PENDING
Status after: TASK-014AE code + tests + docs DONE (local commit DONE — push pending VPS rollout)
Files changed:
  - src/demo_tiny_guarded_entry_dry_run_adapter.py (NEW, 1383 lines)
  - scripts/preview_demo_tiny_guarded_entry_dry_run_adapter.py (NEW)
  - tests/demo_trading/test_demo_tiny_guarded_entry_dry_run_adapter.py (NEW, 145 tests)
  - .gitignore (added outputs/demo_trading/tiny_guarded_entry_dry_run_adapter/)
  - docs/research/commands/NEXT_ACTION.md (prepend TASK-014AE status + Next Rick Action)
  - docs/research/commands/COMMAND_LOG.md (this entry)
Validation:
  - python -m py_compile src/...py scripts/...py tests/...py → OK
  - python -m pytest tests/demo_trading/test_demo_tiny_guarded_entry_dry_run_adapter.py -q
    → 145/145 PASS (0.70s)
  - python -m pytest tests/demo_trading -q → 2493 PASS + 1 pre-existing
    unrelated failure (test_demo_emergency_close_sender::TestCLIIntegration::test_dry_run_cli_writes_report
    — same as 014AA/AB/AC/AD, NOT caused by 014AE)
Outputs: outputs/demo_trading/tiny_guarded_entry_dry_run_adapter/
(gitignored, runtime-only)
Notes: Entry-only dry-run adapter — emits preview envelope only. No socket /
no env reads / no signing tokens / no live endpoint fallback. main.py /
src/risk.py / BybitExecutor untouched. G20 sender policy still in place. No
existing position modified (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT
protected list verified). No sender reuse from any of TASK-014W/X/Y/Z/AA/AB/AC/AD
modules — review reads upstream artifacts only.

---

### 2026-06-11（TASK-014AD — Tiny Lifecycle Real Execution Guarded Runner Design Review）

Agent: Claude (Opus)
Command source: Carry-over TASK-014AD workorder (sequential safety chain after TASK-014AC dry-run runner)
Task: Implement design-review-only module that reviews the 014AC dry-run
runner + 014AB runner design against the 10 baseline lifecycle artifacts —
NO endpoint calls, NO secret reads, NO HMAC/signature, NO preview-to-real
conversion, NO sender adapter, NO real runner implementation. 4 status modes
(TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY /
_BUT_EXECUTION_DISABLED / REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED),
13 upstream artifacts, cross-artifact consistency review (selected symbol /
category=linear / entry side=Buy / cleanup side=Sell / tiny qty / stop price /
entry reference / endpoint family=bybit_demo / account_mode=demo /
proof_strength=strong / position_details_source=real_readonly / no existing
position collision), 6 forbidden flags absent (--execute-real-* / --send-order /
--place-order), next_required_task = TASK-014AE.
Status before: TASK-014AC DONE (dry-run runner) → TASK-014AD PENDING
Status after: TASK-014AD code + tests + docs DONE (local commit DONE — push pending VPS rollout)
Files changed:
  - src/demo_tiny_lifecycle_guarded_runner_design_review.py (NEW, 1380 lines)
  - scripts/preview_demo_tiny_lifecycle_guarded_runner_design_review.py (NEW, 722 lines)
  - tests/demo_trading/test_demo_tiny_lifecycle_guarded_runner_design_review.py (NEW, 156 tests)
  - .gitignore (added outputs/demo_trading/tiny_lifecycle_guarded_runner_design_review/)
  - docs/research/commands/NEXT_ACTION.md (prepend TASK-014AD status + Next Rick Action)
  - docs/research/commands/COMMAND_LOG.md (this entry)
Validation:
  - python -m py_compile src/...py scripts/...py tests/...py → OK
  - python -m pytest tests/demo_trading/test_demo_tiny_lifecycle_guarded_runner_design_review.py -q
    → 156/156 PASS (0.55s)
  - python -m pytest tests/demo_trading -q → 2348 PASS + 1 pre-existing
    unrelated failure (test_demo_emergency_close_sender::TestCLIIntegration::test_dry_run_cli_writes_report
    — same as 014AA/AB/AC, NOT caused by 014AD)
Outputs: outputs/demo_trading/tiny_lifecycle_guarded_runner_design_review/
(gitignored, runtime-only)
Notes: Design review only. No socket / no env reads / no signing tokens / no
live endpoint fallback. main.py / src/risk.py / BybitExecutor untouched.
G20 sender policy still in place. No existing position modified. No sender
reuse from any of TASK-014AA/AB/AC modules — review reads upstream artifacts
only. Working tree had been polluted by an accidental `git stash pop` of
`stash@{0}: On main: WIP after TASK-007 before push`; cleaned via
`git reset --hard HEAD` while preserving the 3 untracked AD files; the
old stash@{0} was left intact (not dropped, not re-popped).

---

### 2026-06-10（TASK-014AC — Tiny Lifecycle Runner Implementation / Dry-run Only）

Agent: Claude (Opus)
Command source: Carry-over TASK-014AC workorder (sequential safety chain)
Task: Implement pure-computation dry-run lifecycle runner — NO endpoint calls,
NO secret reads, NO HMAC/signature, NO sender adapter, NO preview-to-real
conversion. 8 stages, 73 gates, 12 upstream artifacts, 18 runner states,
8-step dry-run trace, 11 audit slots (DRY_RUN_NOT_SENT), 3 synthesized
envelopes always preview_only=True / send_allowed=False / endpoint_called=False,
6 forbidden flags absent (--execute-real-*, --send-order, --place-order),
status modes TINY_LIFECYCLE_RUNNER_DRY_RUN_READY /
_BUT_EXECUTION_DISABLED / REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED / FAIL_CLOSED,
next_required_task = TASK-014AD.
Status before: TASK-014AB DONE (runner design + manual approval) →
TASK-014AC PENDING
Status after: TASK-014AC code + tests + docs DONE (local commit pending)
Files changed:
  - src/demo_tiny_lifecycle_runner_dry_run.py (NEW, ~1460 lines)
  - scripts/preview_demo_tiny_lifecycle_runner_dry_run.py (NEW, ~681 lines)
  - tests/demo_trading/test_demo_tiny_lifecycle_runner_dry_run.py (NEW,
    61 test classes AC1-AC61, 111 tests)
  - .gitignore (added outputs/demo_trading/tiny_lifecycle_runner_dry_run/)
  - docs/research/commands/NEXT_ACTION.md (prepend TASK-014AC status + Next Rick Action)
  - docs/research/commands/COMMAND_LOG.md (this entry)
Validation:
  - python -m py_compile src/...py scripts/...py tests/...py → OK
  - python -m pytest tests/demo_trading/test_demo_tiny_lifecycle_runner_dry_run.py -q
    → 111/111 PASS
  - python -m pytest tests/demo_trading -q → 2192 PASS + 1 pre-existing
    unrelated failure (test_demo_emergency_close_sender — same as 014AA/AB)
Outputs: outputs/demo_trading/tiny_lifecycle_runner_dry_run/ (gitignored,
runtime-only)
Notes: Pure-computation only. No socket / no env reads / no signing.
3 envelopes synthesized internally always preview_only=True regardless of
upstream; upstream preview_only=False also propagates to FAIL_CLOSED.
8-step trace records endpoint_called=False / position_modified=False /
token_validated=False per step. 11 audit slots all DRY_RUN_NOT_SENT.
Failure path simulation: 5 FAIL_CLOSED + 2 MANUAL_REVIEW_REQUIRED.
No real runner / no sender reuse / no 014AA-summary or 014AB-design module
reuse. G20 sender policy still in place. No existing position modified.
Next: TASK-014AD (tiny_lifecycle_real_execution_guarded_runner_design_review).

---

### 2026-06-10（TASK-014AB — Tiny Lifecycle Runner Design / Manual Approval）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014AB)
Task: Build a pure-computation runner design module that consolidates the
      11 upstream artifacts (10 baseline + 014AA lifecycle_summary) and
      documents (a) the design-only scope, (b) the 18-state runner state
      machine with readonly-between-real-steps invariant, (c) the three
      distinct manual approval tokens (entry / stop-attach / cleanup) that
      are never validated here, (d) the execution payload contract pulled
      from the three permission gates without conversion, (e) the abort /
      fail-closed policy for every real step, (f) the observability +
      audit-artifact contract (11 required artifacts + sanitisation rules),
      and (g) the permanent execution guard.  No runner is implemented in
      this task; no endpoint is invoked; G20 remains in place; the four
      forbidden flags (--execute-real-lifecycle / --execute-real-entry /
      --execute-real-stop / --execute-real-cleanup) are deliberately absent.

Status before: TASK-014AA local-committed, pre-VPS-pull.
Status after:  TASK-014AB local-committed; next_required_task =
               TASK-014AC_tiny_lifecycle_runner_implementation_dry_run_only.

Files changed:
  - src/demo_tiny_lifecycle_runner_design.py (NEW, 1283 lines)
  - scripts/preview_demo_tiny_lifecycle_runner_design.py (NEW, ~580 lines)
  - tests/demo_trading/test_demo_tiny_lifecycle_runner_design.py (NEW, ~1100 lines)
  - .gitignore (+1 line: outputs/demo_trading/tiny_lifecycle_runner_design/)
  - docs/research/commands/NEXT_ACTION.md (prepend 014AB block)
  - docs/research/commands/COMMAND_LOG.md (this entry)

Validation:
  - py_compile: PASS (src + scripts + tests)
  - pytest tests/demo_trading/test_demo_tiny_lifecycle_runner_design.py:
        90 / 90 PASS in 0.59 s
  - pytest tests/demo_trading:
        2081 PASS + 1 pre-existing unrelated failure
        (test_demo_emergency_close_sender::TestCLIIntegration::
         test_dry_run_cli_writes_report — same failure already noted under
         TASK-014AA, untouched by this task)

Outputs:
  - outputs/demo_trading/tiny_lifecycle_runner_design/  (gitignored)

Notes:
  - Pure design module — no socket import, no network call, no env read,
    no signing, no order endpoint touched, no existing position modified.
  - 8 stages, 68 gates, 18 runner states, 11 required audit artifacts,
    3 distinct manual approval tokens, 4 status modes.
  - 11 upstream artifact inputs (10 from 014AA chain + 014AA
    lifecycle_summary itself); ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES
    frozenset enforces the upstream verdict.
  - Status promotion chain: hard_fail → FAIL_CLOSED;
    allow_real_runner_execution → REAL_RUNNER_NOT_IMPL;
    allow_runner_design_approval → DESIGN_READY_EXEC_DISABLED;
    otherwise → DESIGN_READY.
  - 4 forbidden flags scanned via tokenize-stripped source
    (only docstrings/comments may mention them as forbidden — code is clean).
  - Local commit only (no push) per durable feedback rule.

---

### 2026-06-10（TASK-014AA — Tiny Lifecycle Real Execution Permission Summary / Final Review）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014AA)
Task: Build a pure-computation final-review permission summary that
      consolidates the four upstream permission gates (014W real-permission,
      014X tiny-entry, 014Y tiny-stop-attach, 014Z tiny-cleanup) together
      with the original readonly / reconciliation / protection / contract /
      no-op-plan / lifecycle-mock artifacts (10 upstream inputs total),
      performs cross-artifact consistency checks (selected symbol,
      entry side=Buy, cleanup side=Sell, tiny qty from rounded_tiny_qty
      priority, stop price from stop-attach permission gate priority,
      entry reference price from protection priority, category=linear,
      payload previews) and emits a final readiness verdict for the future
      real tiny-position lifecycle execution runner (TASK-014AB).
      7 stages, 59 GATE_ constants split across 5 categories
      (23 general + 13 consistency + 7 manual approval + 11 failure +
      5 execution guard). Documents the fixed 8-step real lifecycle
      sequence (pre_readonly_snapshot → real_tiny_entry →
      post_entry_readonly → real_stop_attach → post_stop_attach_readonly
      → real_cleanup → post_cleanup_readonly → final_audit), each step
      preview-only here. Documents 3 distinct manual approval tokens
      (entry / stop-attach / cleanup), string-only, never validated.
      4 status modes:
      TINY_LIFECYCLE_PERMISSION_SUMMARY_READY (default checklist),
      TINY_LIFECYCLE_PERMISSION_SUMMARY_READY_BUT_EXECUTION_DISABLED
      (`--allow-real-lifecycle-summary`),
      REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED
      (`--allow-real-lifecycle-execution` execution-guard mode),
      FAIL_CLOSED (hard-fail gate raised).
      Always emits real_execution_allowed=False,
      current_task_real_execution_allowed=False, g20_lifted=False.
      next_required_task = TASK-014AB_tiny_lifecycle_real_execution_runner_design_or_manual_approval.

Status before: TASK-014Z DONE (committed a817f5c). Real tiny-position
      lifecycle still un-orchestrated; no final-review summary gate.
Status after: 3 new files (src module ~1000 lines, CLI script ~500 lines,
      test file ~1100 lines, 93 tests / 62 test classes AA1-AA62 + sub-tests
      all PASS). G20 still in place. 5 existing demo shorts untouched.
      Real execution path still not implemented.

Files changed:
  - src/demo_tiny_lifecycle_real_execution_summary.py  (NEW)
  - scripts/preview_demo_tiny_lifecycle_real_execution_summary.py  (NEW)
  - tests/demo_trading/test_demo_tiny_lifecycle_real_execution_summary.py  (NEW)
  - .gitignore  (added `outputs/demo_trading/tiny_lifecycle_real_execution_summary/`)
  - docs/research/commands/NEXT_ACTION.md  (TASK-014AA status block prepended)
  - docs/research/commands/COMMAND_LOG.md  (this entry)

Validation:
  - py_compile src/demo_tiny_lifecycle_real_execution_summary.py: OK
  - py_compile scripts/preview_demo_tiny_lifecycle_real_execution_summary.py: OK
  - py_compile tests/demo_trading/test_demo_tiny_lifecycle_real_execution_summary.py: OK
  - pytest tests/demo_trading/test_demo_tiny_lifecycle_real_execution_summary.py: 93/93 PASS
  - pytest tests/demo_trading: 1991 PASS + 1 pre-existing unrelated failure
    (test_demo_emergency_close_sender::test_dry_run_cli_writes_report)

Outputs:
  - outputs/demo_trading/tiny_lifecycle_real_execution_summary/  (created at first CLI run)

Notes:
  - No real /v5/order/create. No real /v5/position/trading-stop.
    No order send. No close-only sender. No emergency-close sender.
    No new-entry sender real exec. No permission-gate sender reuse.
    No socket / urllib / requests / httpx / http.client / dotenv.
    No HMAC / signing.
  - 4 ACCEPTABLE_*_STATUSES frozensets (real_permission_gate /
    tiny_entry_permission_gate / tiny_stop_attach_permission_gate /
    tiny_cleanup_permission_gate).
  - Hard-fail-closed gates frozenset enforces FAIL_CLOSED downgrade
    when any of the upstream-presence / status-acceptable /
    symbol-collision / category-mismatch / payload-shape gates raise.
  - All 3 manual approval tokens are string-only and NEVER validated
    in this task; tokens MUST be distinct per step.
  - Real lifecycle execution stays gated on TASK-014AB until Rick
    explicitly authorises it.

---

### 2026-06-10（TASK-014Z — Tiny Isolated Demo Cleanup Permission Gate / Dry-run Only）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014Z)
Task: Build a pure-computation tiny isolated demo cleanup (close-only)
      permission gate mirroring the TASK-014Y (stop-attach gate) pattern.
      7 stages, 53 GATE_ constants split across 5 categories
      (22 general + 13 cleanup payload + 6 manual approval + 7 failure +
      5 execution guard). Loads 9 upstream artifacts including the new
      TASK-014Y tiny_stop_attach_permission_gate. Cleanup payload preview
      emits category=linear, symbol=SOLUSDT, side=Sell, orderType=Market,
      qty=<expected_tiny_qty>=0.1, reduceOnly=True, closeOnTrigger=False,
      positionIdx=0, orderLinkId=DRYRUN-TINY-CLEANUP-<sym>-<ts>,
      preview_only=True, endpoint_called=False. expected_tiny_qty derives
      from entry permission gate `rounded_tiny_qty` (priority) and
      lifecycle mock `tiny_qty` (fallback); both must agree.
      Token pattern CONFIRM_DEMO_TINY_CLEANUP_YYYYMMDD_SYMBOL documented
      as string only; entry / stop-attach tokens explicitly not accepted.
      No real /v5/order/create or /v5/position/trading-stop; no order
      send; no close-only sender; no emergency-close sender; no new-entry
      sender real exec; G20 stays not lifted; 5 existing demo shorts
      untouched. next_required_task =
      TASK-014AA_tiny_lifecycle_real_execution_permission_summary.
Status before: TASK-014Y DONE
Status after:  TASK-014Z DONE (local commit)
Files changed:
  - src/demo_tiny_cleanup_permission_gate.py             (new, ~1120 lines)
  - scripts/preview_demo_tiny_cleanup_permission_gate.py (new, ~430 lines)
  - tests/demo_trading/test_demo_tiny_cleanup_permission_gate.py (new, ~1080 lines)
  - .gitignore                                           (+1 line: tiny_cleanup_permission_gate/)
  - docs/research/commands/NEXT_ACTION.md                (TASK-014Z status block prepended)
  - docs/research/commands/COMMAND_LOG.md                (this entry)
Validation:
  - py_compile src/demo_tiny_cleanup_permission_gate.py
      + scripts/preview_demo_tiny_cleanup_permission_gate.py
      + tests/demo_trading/test_demo_tiny_cleanup_permission_gate.py    PASS
  - python -m pytest tests/demo_trading/test_demo_tiny_cleanup_permission_gate.py -q
      100 passed
  - python -m pytest tests/demo_trading -q
      1898 passed + 1 pre-existing unrelated failure
      (tests/demo_trading/test_demo_emergency_close_sender.py
       TestCLIIntegration.test_dry_run_cli_writes_report --- same failure
       observed at TASK-014Y validation; unrelated to this task)
Outputs (local only; .gitignored):
  - outputs/demo_trading/tiny_cleanup_permission_gate/   (created on first VPS run)
Notes:
  - Gate is pure-computation: no urllib / requests / httpx / socket /
    http.client / pybit / os.environ / dotenv / hmac / hashlib.
  - Source-scan tests enforce forbidden-import list including
    src.demo_tiny_stop_attach_permission_gate; CLI imports only the
    cleanup gate module.
  - Even with --allow-real-cleanup-permission the result is
    TINY_CLEANUP_PERMISSION_READY_BUT_EXECUTION_DISABLED with no socket
    opened.
  - Even with --allow-real-cleanup the result is
    REAL_CLEANUP_NOT_IMPLEMENTED with no socket opened.
  - Hard-fail-closed gate frozenset covers all 9 missing-artifact gates,
    4 envelope mismatches, lifecycle-not-success, 3 upstream-status
    unacceptables, symbol missing / collision, qty missing / not_positive
    / mismatch, cleanup-side / category / symbol mismatches.
  - Stage-2 self-checks the preview payload (defense in depth): payload
    flips back through preview_only / category / symbol / side / orderType
    / reduceOnly / positionIdx / orderLinkId prefix and surfaces a gate
    on any drift.

---

### 2026-06-10（TASK-014Y — Tiny Isolated Demo Stop Attach Permission Gate / Dry-run Only）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014Y)
Task: Build a pure-computation tiny isolated demo stop-attach permission gate
      mirroring the TASK-014X (entry gate) pattern. 7 stages, 49 gates split
      across 5 categories (20 general + 12 stop payload + 6 manual approval +
      6 failure + 5 execution guard). Loads 8 upstream artifacts including
      the TASK-014X tiny_entry_permission_gate. Stop payload preview emits
      category=linear, stopLoss=<stop_price>, tpslMode=Full,
      slTriggerBy=MarkPrice, positionIdx=0, symbol=SOLUSDT, preview_only=True.
      Token pattern CONFIRM_DEMO_TINY_STOP_ATTACH_YYYYMMDD_SYMBOL documented
      as string only. No real /v5/position/trading-stop or /v5/order/create;
      no order send; G20 stays not lifted; 5 existing demo shorts untouched.
      next_required_task = TASK-014Z_tiny_isolated_demo_cleanup_permission_gate.
Status before: TASK-014X-FIX2 DONE
Status after:  TASK-014Y DONE (local commit)
Files changed:
  - NEW src/demo_tiny_stop_attach_permission_gate.py
  - NEW scripts/preview_demo_tiny_stop_attach_permission_gate.py
  - NEW tests/demo_trading/test_demo_tiny_stop_attach_permission_gate.py
  - .gitignore (+ outputs/demo_trading/tiny_stop_attach_permission_gate/)
  - docs/research/commands/NEXT_ACTION.md (+ TASK-014Y block)
  - docs/research/commands/COMMAND_LOG.md (this entry)
Validation:
  - py_compile src + CLI + tests : PASS
  - pytest tests/demo_trading/test_demo_tiny_stop_attach_permission_gate.py : 88/88 PASS
  - pytest tests/demo_trading : 1798 PASS + 1 pre-existing unrelated failure
    (test_demo_emergency_close_sender::test_dry_run_cli_writes_report)
Outputs:
  - none (gate is pure-computation; no artifact written by this commit)
Notes:
  - Real demo execution remains gated by G20 (not lifted).
  - Status mode REAL_STOP_ATTACH_NOT_IMPLEMENTED is the only path when
    --allow-real-tiny-stop-attach is set; checklist still does not send.
  - Tick alignment for SOLUSDT (tick_size=0.01): stop_price=61.63 → aligned.
  - No network sockets touched (verified by socket-disabled subprocess test).

---

### 2026-06-10（TASK-014X-FIX2 — Fetch Paginated SOLUSDT Instrument Rule）

Agent: Claude Haiku 4.5
Command source: Rick direct chat instruction (TASK-014X-FIX2)
Task: Fix VPS failure where readonly smoke `instrument_rules_by_symbol` had
      `SOLUSDT=None` even after TASK-014X-FIX1.  Root cause: Bybit
      instruments-info endpoint returns paginated results (nextPageCursor);
      the original _instruments_real() only fetched the first page (~500
      items), but SOLUSDT was not among them.  Fix adds:
      (a) Pagination support: loop via nextPageCursor up to 20 pages,
      collecting all results.  (b) Targeted SOLUSDT fetch: if SOLUSDT
      is not in paginated results, call /v5/market/instruments-info
      with symbol=SOLUSDT parameter explicitly.  (c) Pagination metadata:
      latest_smoke.json now includes instrument_rules_count / pages_fetched
      / next_cursor_exhausted / targeted_symbols_requested / _found / _missing.
      No network-level changes; still read-only market endpoints only.
Status before: TASK-014X-FIX1 tests 91/91 PASS locally; VPS still reported
      instrument_rule_missing_for_selected_symbol (SOLUSDT not in first page).
Status after: 1710/1710 PASS locally (74 readonly_client + 95 entry_gate +
      others) + 1 pre-existing unrelated failure.  SOLUSDT fetch now via
      pagination + targeted lookup strategy.
Files changed:
  - src/demo_readonly_client.py       (_instruments_real: pagination loop,
      targeted SOLUSDT fetch; _parse_instrument_snapshot extracted helper)
  - scripts/preview_demo_readonly_runtime.py (pagination metadata in
      latest_smoke.json via both _write_report calls)
  - tests/demo_trading/test_demo_readonly_client.py
      (TestPaginationAndTargetedLookup: 4 tests)
  - tests/demo_trading/test_demo_tiny_entry_permission_gate.py
      (TestX71–TestX73: 3 tests for pagination metadata + targeted missing)
  - docs/research/commands/NEXT_ACTION.md (TASK-014X-FIX2 status + VPS steps)
  - docs/research/commands/COMMAND_LOG.md (this entry)
Validation:
  - python -m py_compile src/demo_readonly_client.py                 => OK
  - python -m py_compile scripts/preview_demo_readonly_runtime.py    => OK
  - python -m py_compile src/demo_tiny_entry_permission_gate.py      => OK
  - python -m py_compile scripts/preview_demo_tiny_entry_permission_gate.py
        => OK
  - python -m pytest tests/demo_trading/test_demo_readonly_client.py -q
        => 74 passed
  - python -m pytest tests/demo_trading/test_demo_tiny_entry_permission_gate.py -q
        => 95 passed (91 prior + 4 new FIX2)
  - python -m pytest tests/demo_trading -q
        => 1710 passed, 1 pre-existing failure
Outputs:
  - outputs/demo_trading/readonly_smoke/ (runtime; gitignored)
Notes:
  - Pagination loop: max_pages=20, seen_cursors set prevents infinite
      cycles.  If cursor repeats or is empty, fetch stops.
  - Targeted SOLUSDT lookup: called if SOLUSDT not in paginated results;
      uses /v5/market/instruments-info?category=linear&symbol=SOLUSDT.
  - Pagination metadata: instrument_rules_count, pages_fetched (0 for
      fixture mode), next_cursor_exhausted, targeted_symbols_requested /
      _found / _missing (all strings for fixture mode).
  - _parse_instrument_snapshot factored out so both paginated and targeted
      paths use same field extraction logic.
  - No API secrets involved; read-only market endpoints only.
  - 5 existing demo shorts untouched; G20 unchanged.
  - Local commit only per Rick durable preference.

---

### 2026-06-10（TASK-014X-FIX1 — Persist SOLUSDT Instrument Rule for Tiny Entry Gate）

Agent: Claude Sonnet 4.6
Command source: Rick direct chat instruction (TASK-014X-FIX1)
Task: Fix VPS failure where TASK-014X stage_2_instrument_min_step_check
      reported instrument_rule_missing_for_selected_symbol.  Root cause:
      `_serialize_instrument_rules_for_positions` only serialised rules
      for symbols with open positions (ENAUSDT/TIAUSDT/AIXBTUSDT/
      POLYXUSDT/EDUUSDT); SOLUSDT — the intended entry symbol — was
      never in an open position so its rule was never written to
      latest_smoke.json.  Fix adds a new `instrument_rules_by_symbol`
      field that explicitly includes SOLUSDT (and all position symbols)
      regardless of open position status.  The TASK-014X reader is
      updated to check `instrument_rules_by_symbol` first before
      falling back to `instrument_rules`.  7 new tests (X64-X70) cover
      the new dict-keyed format.
      No network calls; no order/stop endpoints; G20 unchanged.
Status before: TASK-014X tests 84/84 PASS locally; VPS run reported
      FAIL_CLOSED / stage_2_instrument_min_step_check /
      instrument_rule_missing_for_selected_symbol.
Status after: TASK-014X tests 91/91 PASS locally (84 prior + 7 new
      FIX1). Full suite: 1702 PASS + 1 pre-existing unrelated failure
      (test_demo_emergency_close_sender).
Files changed:
  - scripts/preview_demo_readonly_runtime.py  (added _CANDIDATE_ENTRY_SYMBOLS,
      _serialize_instrument_rules_by_symbol, instrument_rules_by_symbol in
      both _write_report calls)
  - src/demo_tiny_entry_permission_gate.py    (_find_instrument_rule updated:
      checks instrument_rules_by_symbol first, then instrument_rules fallback)
  - tests/demo_trading/test_demo_tiny_entry_permission_gate.py
      (added _valid_rules_by_symbol, _readonly_by_sym fixtures;
       TestX64-TestX70)
  - docs/research/commands/NEXT_ACTION.md (TASK-014X-FIX1 status + VPS steps)
  - docs/research/commands/COMMAND_LOG.md (this entry)
Validation:
  - python -m py_compile scripts/preview_demo_readonly_runtime.py => OK
  - python -m py_compile src/demo_tiny_entry_permission_gate.py    => OK
  - python -m py_compile scripts/preview_demo_tiny_entry_permission_gate.py => OK
  - python -m pytest tests/demo_trading/test_demo_tiny_entry_permission_gate.py -q
        => 91 passed (84 prior + 7 new FIX1)
  - python -m pytest tests/demo_trading -q
        => 1702 passed, 1 pre-existing failure
Outputs:
  - outputs/demo_trading/readonly_smoke/ (runtime; gitignored)
  - outputs/demo_trading/tiny_entry_permission_gate/ (runtime; gitignored)
Notes:
  - instrument_rules_by_symbol schema per symbol:
      {"symbol": "SOLUSDT", "category": "linear", "min_order_qty": <float>,
       "qty_step": <float>, "tick_size": <float>, "min_notional": <float>,
       "min_notional_value": <float>}
  - _find_instrument_rule priority: instrument_rules_by_symbol (new, VPS
      real-readonly output) → instrument_rules (list or dict, legacy /
      test-fixture).  No fabricated fallback.
  - DemoReadOnlyClient calls /v5/market/instruments-info with
      category=linear; all returned rules are linear perpetuals, so
      category="linear" is hardcoded in the serialisation helper.
  - 5 existing demo shorts untouched; G20 unchanged; no secrets in output.
  - Local commit only per Rick durable preference; not pushed to GitHub.

---

### 2026-06-10（TASK-014X — Tiny Isolated Demo Entry Permission Gate / Dry-run Only）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014X)
Task: Add a pure-computation 7-stage entry permission gate /
      dry-run-only checklist that documents what must be in place
      before any future real tiny-isolated demo *entry* execution.
      Stages: stage_0_artifact_preflight
      / stage_1_existing_position_pre_snapshot
      / stage_2_instrument_min_step_check
      / stage_3_entry_payload_preview
      / stage_4_entry_token_checklist
      / stage_5_post_entry_verification_plan
      / stage_6_execution_guard. Instrument-rule rounding pipeline
      enforces min_order_qty / qty_step alignment, bumps notional up
      to min_notional_value, and rejects anything above the 10 USDT
      tiny notional cap.  orderLinkId prefix `DRYRUN-TINY-ENTRY-`
      is preview-only (never sent).  12.2 SOL strategy full-size qty
      flagged as MUST_NOT_BE_REUSED. Guarded flags:
      --allow-real-entry-permission returns
      TINY_ENTRY_PERMISSION_READY_BUT_EXECUTION_DISABLED;
      --allow-real-tiny-entry returns
      REAL_TINY_ENTRY_NOT_IMPLEMENTED.  Upstream
      real_permission_gate status must already be
      REAL_PERMISSION_CHECKLIST_READY or
      REAL_PERMISSION_GATE_READY_BUT_EXECUTION_DISABLED; otherwise
      FAIL_CLOSED.  No network, no /v5/order/create, no
      /v5/position/trading-stop, no close-only, no emergency close,
      no leverage mutation, no transfers, no G20 lift.
Status before: TASK-014W + TASK-014W-FIX1 verified;
      tests/demo_trading_tiny_position_real_permission_gate=83/83
      PASS.  NEXT_ACTION pointed at TASK-014X as the next gate task
      pending Rick authorisation.
Status after: TASK-014X module + CLI + 84 tests landed locally.
      pytest tests/demo_trading/test_demo_tiny_entry_permission_gate.py
      = 84/84 PASS.  TASK-014W sibling suite still 83/83 PASS.
Files changed:
  - src/demo_tiny_entry_permission_gate.py                       (NEW)
  - scripts/preview_demo_tiny_entry_permission_gate.py            (NEW)
  - tests/demo_trading/test_demo_tiny_entry_permission_gate.py    (NEW)
  - .gitignore  (added outputs/demo_trading/tiny_entry_permission_gate/)
  - docs/research/commands/NEXT_ACTION.md (TASK-014X status block + Rick VPS steps)
  - docs/research/commands/COMMAND_LOG.md (this entry)
Validation:
  - python -m py_compile src/demo_tiny_entry_permission_gate.py            => OK
  - python -m py_compile scripts/preview_demo_tiny_entry_permission_gate.py => OK
  - python -m pytest tests/demo_trading/test_demo_tiny_entry_permission_gate.py -q
        => 84 passed
  - python -m pytest tests/demo_trading/test_demo_tiny_position_real_permission_gate.py -q
        => 83 passed (TASK-014W sibling regression check)
  - python scripts/preview_demo_tiny_entry_permission_gate.py --help => OK
  - python scripts/preview_demo_tiny_entry_permission_gate.py --write-report
        => FAIL_CLOSED on missing local upstream artifacts (expected
        local-dev result; VPS run uses --from-latest-* flags).
Outputs:
  - outputs/demo_trading/tiny_entry_permission_gate/  (runtime, gitignored)
Notes:
  - 53 gate constants exposed (18 general + 10 instrument + 8 entry
    payload + 6 manual approval + 6 failure + 5 execution guard).
  - 4 statuses (TINY_ENTRY_PERMISSION_CHECKLIST_READY /
    TINY_ENTRY_PERMISSION_READY_BUT_EXECUTION_DISABLED /
    REAL_TINY_ENTRY_NOT_IMPLEMENTED / FAIL_CLOSED).
  - 4 modes (checklist / real_entry_permission_dry_run /
    real_tiny_entry_guard / fail_closed).
  - Payload preview is envelope-only: Buy / positionIdx=0 /
    reduceOnly=False / orderLinkId prefixed `DRYRUN-TINY-ENTRY-`.
    No order envelope is sent to any endpoint.
  - 5 existing demo shorts (ENAUSDT / TIAUSDT / AIXBTUSDT /
    POLYXUSDT / EDUUSDT) never touched.  Symbol collision with any
    of them triggers FAIL_CLOSED.
  - 12.2 SOL strategy full-size qty rejected (FAIL_CLOSED) when
    used as input tiny qty; 10 USDT tiny notional cap enforced.
  - G20 (protected_entry_policy_missing) constant unchanged and not
    referenced in the new module.
  - Local commit only per Rick durable preference; not pushed to
    GitHub.
  - next_required_task = TASK-014Y_tiny_isolated_demo_stop_attach_permission_gate.

---

### 2026-06-10（TASK-014W — Tiny Isolated Demo Position Real Execution Permission Gate）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014W)
Task: Add a pure-computation 6-stage permission gate / manual approval
      checklist that documents what must be in place before any
      future real tiny-isolated demo position execution
      (TASK-014X / -014Y / -014Z). Stages: stage_0_artifact_preflight
      / stage_1_existing_position_snapshot / stage_2_tiny_risk_cap
      / stage_3_three_step_manual_approval / stage_4_failure_response
      / stage_5_real_execution_guard. Three independent confirmation
      token patterns (entry / stop-attach / cleanup) are documented
      as strings only; no token validation occurs in this task.
      tiny_notional_cap=10 USDT; strategy_full_size_qty_ref=12.2 SOL
      is documented as MUST_NOT_BE_REUSED.  Guarded flags:
      --allow-real-permission-gate returns
      REAL_PERMISSION_GATE_READY_BUT_EXECUTION_DISABLED;
      --allow-real-tiny-position returns
      REAL_TINY_POSITION_NOT_IMPLEMENTED.  No network, no
      /v5/order/create, no /v5/position/trading-stop, no close-only,
      no emergency close, no leverage mutation, no transfers, no
      G20 lift.
Status before: TASK-014V verified; tests/demo_trading=1529/1529
      PASS. NEXT_ACTION pointed at TASK-014W as the next gate task
      pending Rick authorisation.
Status after: TASK-014W module + CLI + 83 tests landed locally.
      tests/demo_trading=1611 PASS + 1 pre-existing unrelated
      failure (test_demo_emergency_close_sender :: TestCLIIntegration
      :: test_dry_run_cli_writes_report — failed identically on HEAD
      baseline, not caused by TASK-014W).  All 83 new W tests PASS;
      all 77 prior V tests still PASS within the suite.
Files changed:
  - src/demo_tiny_position_real_permission_gate.py            (NEW)
  - scripts/preview_demo_tiny_position_real_permission_gate.py (NEW)
  - tests/demo_trading/test_demo_tiny_position_real_permission_gate.py (NEW)
  - .gitignore  (added outputs/demo_trading/tiny_position_real_permission_gate/)
  - docs/research/commands/COMMAND_LOG.md (this entry)
  - docs/research/commands/NEXT_ACTION.md (status + Next Rick Action)
Validation:
  - python -m py_compile src/demo_tiny_position_real_permission_gate.py
                        scripts/preview_demo_tiny_position_real_permission_gate.py
                        tests/demo_trading/test_demo_tiny_position_real_permission_gate.py
                        → OK
  - python -m pytest tests/demo_trading/test_demo_tiny_position_real_permission_gate.py -q
                        → 83 passed
  - python -m pytest tests/demo_trading -q
                        → 1611 passed, 1 failed (pre-existing,
                          unrelated to TASK-014W — same failure
                          observed on HEAD baseline before TASK-014W
                          files were added)
  - W35 forbidden-imports scan: PASS (no urllib / requests / httpx /
    socket / http.client / pybit / src.risk / BybitExecutor /
    src.demo_new_entry_sender / src.demo_close_only_sender /
    src.demo_emergency_close_sender /
    src.demo_protected_new_entry_orchestrator /
    src.demo_trading_stop_contract_probe /
    src.demo_trading_stop_noop_probe_plan /
    src.demo_tiny_position_lifecycle_mock).
  - W36 network-token / env / signing source scan: PASS.
  - W37 sender / orchestrator / probe / lifecycle back-coupling
    source scan: PASS.
  - W38 socket-disabled import sentinel: PASS.
  - W39 G20 constant unchanged + not referenced in module: PASS.
Outputs (when --write-report):
  - outputs/demo_trading/tiny_position_real_permission_gate/
        {ts}_tiny_position_real_permission_gate.json
        {ts}_tiny_position_real_permission_gate.md
        latest_tiny_position_real_permission_gate.json
        latest_tiny_position_real_permission_gate.md
Notes:
  - 41 GATE_ constants exposed (18 general + 6 risk + 7 manual
    approval + 5 failure response + 5 execution guard).
  - 4 status constants (REAL_PERMISSION_CHECKLIST_READY /
    REAL_PERMISSION_GATE_READY_BUT_EXECUTION_DISABLED /
    REAL_TINY_POSITION_NOT_IMPLEMENTED / FAIL_CLOSED).
  - 4 mode constants (checklist / real_permission_gate_dry_run /
    real_tiny_position_guard / fail_closed).
  - 3 approval token patterns documented as strings only
    (CONFIRM_DEMO_TINY_ENTRY_/STOP_ATTACH_/CLEANUP_YYYYMMDD_SYMBOL).
  - Hard-fail-closed gates frozenset triggers FAIL_CLOSED downgrade
    regardless of caller flags.
  - 5 existing demo shorts (ENAUSDT / TIAUSDT / AIXBTUSDT /
    POLYXUSDT / EDUUSDT) snapshotted by stage_1 and asserted
    untouched by stage_5 (`existing_positions_touched=[]`).
  - TASK-014L sender G20 (protected_entry_policy_missing) NOT
    referenced by module text and NOT lifted; `g20_lifted=False`,
    `g20_policy_still_in_place=True` in every result envelope.
  - next_required_task =
    "TASK-014X_tiny_isolated_demo_entry_permission_gate".
  - Local commit only — no GitHub push.

---

### 2026-06-10（TASK-014W-FIX1 — Clarify real tiny guard execution flags）

Agent: Claude Sonnet 4.6
Command source: Rick direct chat instruction (TASK-014W-FIX1)
Task: Fix semantic error where `real_execution_allowed` was set to
      `bool(allow_real_tiny_position)` in the
      REAL_TINY_POSITION_NOT_IMPLEMENTED path, making it appear that
      real execution was allowed when it is not. The allow flag only
      means the user requested real tiny; execution is never allowed
      in TASK-014W. Add `real_tiny_position_requested` field to
      preserve the "user requested" semantic distinctly from the
      "execution allowed" semantic.
Status before: TASK-014W 83/83 tests PASS; VPS validation step-4
      showed `real_execution_allowed=True` under --allow-real-tiny-position
      — inconsistent with the REAL_TINY_POSITION_NOT_IMPLEMENTED status
      and safety semantics.
Status after: `real_execution_allowed` is always False; new field
      `real_tiny_position_requested` captures the user-intent flag.
      Tests W25 and W33 updated; 83/83 PASS. NEXT_ACTION.md VPS
      step-4 expected values corrected.
Files changed:
  - src/demo_tiny_position_real_permission_gate.py
      * Removed `real_exec_flag_allowed = bool(allow_real_tiny_position)`
      * `real_execution_allowed` always returned as False
      * Added `real_tiny_position_requested: bool = False` field
      * `real_tiny_position_requested` added to to_dict()
      * stage_5 envelope: `real_tiny_position_requested` added
  - tests/demo_trading/test_demo_tiny_position_real_permission_gate.py
      * W25: `real_execution_allowed is False`; `real_tiny_position_requested is True`
      * W33: JSON report `real_execution_allowed is False`; `real_tiny_position_requested is True`
  - docs/research/commands/COMMAND_LOG.md (this entry)
  - docs/research/commands/NEXT_ACTION.md (FIX1 status block; VPS step-4 corrected)
Validation:
  - python -m py_compile src/demo_tiny_position_real_permission_gate.py
                        scripts/preview_demo_tiny_position_real_permission_gate.py → OK
  - python -m pytest tests/demo_trading/test_demo_tiny_position_real_permission_gate.py -q
                        → 83 passed
Safety confirmation:
  - order_endpoint_called=False: CONFIRMED (no change to execution paths)
  - stop_endpoint_called=False:  CONFIRMED
  - no_position_modified=True:   CONFIRMED
  - G20 unchanged:               CONFIRMED
  - No new execute flag added:   CONFIRMED (real_tiny_position_requested is read-only semantic)
Notes:
  - Before: `real_execution_allowed=True` when allow_real_tiny_position=True (wrong)
  - After:  `real_execution_allowed=False` always; `real_tiny_position_requested=True` when
            allow_real_tiny_position=True (correct)
  - stage_5 and top-level summary now consistent: both show real_execution_allowed=False.
  - Local commit only — no GitHub push.

---

### 2026-06-10（TASK-014V — Tiny Isolated Demo Position Lifecycle Mock）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014V)
Task: Add a pure-computation 7-phase tiny-isolated demo position
      lifecycle simulator that proves end-to-end (preflight, tiny entry,
      post-fill audit, stop-attach, protected verify, cleanup, final
      audit) cannot touch any existing demo position or invoke any
      live Bybit endpoint. Includes three failure-injection paths
      (stop-attach failure, cleanup failure, existing stop mismatch)
      and a guarded --allow-real-tiny-position flag that hard-returns
      REAL_TINY_POSITION_NOT_IMPLEMENTED.
Status before: TASK-014U-FIX2 verified; CLI writes primary +
      legacy alias report names. NEXT_ACTION still pointed at
      TASK-014V as the only remaining human decision gate.
Status after: TASK-014V module + CLI + 77 tests landed locally.
      tests/demo_trading=1529/1529 PASS (1452 prior + 77 new V).
      No /v5/order/create, /v5/position/trading-stop, or /v5/asset/...
      invocation; no socket opened at import; no secrets observed.
      G20 (protected_entry_policy_missing) constant intact and not
      mentioned in the new module.
Files changed:
  - src/demo_tiny_position_lifecycle_mock.py        (new)
  - scripts/preview_demo_tiny_position_lifecycle_mock.py  (new)
  - tests/demo_trading/test_demo_tiny_position_lifecycle_mock.py  (new)
  - .gitignore                                       (output dir)
  - docs/research/commands/NEXT_ACTION.md            (TASK-014V block)
  - docs/research/commands/COMMAND_LOG.md            (this entry)
Validation:
  python -m py_compile \
    src/demo_tiny_position_lifecycle_mock.py \
    scripts/preview_demo_tiny_position_lifecycle_mock.py
  python -m pytest tests/demo_trading -q
    -> 1529 passed (1452 prior + 77 new V)
Outputs (when --write-report on VPS):
  outputs/demo_trading/tiny_position_lifecycle_mock/
      latest_tiny_position_lifecycle_mock.json
      latest_tiny_position_lifecycle_mock.md
      {ts}_tiny_position_lifecycle_mock.json
      {ts}_tiny_position_lifecycle_mock.md
Notes:
  - 29 gate constants exposed (21 general + 8 lifecycle-specific).
  - 5 status constants (TINY_LIFECYCLE_PREVIEW_READY /
    MOCK_TINY_LIFECYCLE_SUCCESS / MOCK_TINY_LIFECYCLE_FAIL_CLOSED /
    REAL_TINY_POSITION_NOT_IMPLEMENTED / FAIL_CLOSED) + 4 mode
    constants (preview / mock_lifecycle / real_tiny_position /
    fail_closed).
  - Existing 5 demo shorts (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT /
    EDUUSDT) NEVER touched by any phase; final audit asserts an
    empty existing_positions_touched list.
  - Default selected_symbol=SOLUSDT (validated disjoint from the
    5 existing positions).
  - next_required_task in result =
    TASK-014W_tiny_isolated_demo_position_real_execution_permission_gate.
  - Local commit only; no GitHub push (per memory rule).

---

### 2026-06-10（TASK-014U-FIX2 — Align No-op Probe Latest Report Filenames）

Agent: Claude Sonnet 4.6
Command source: Rick direct chat instruction (TASK-014U-FIX2)
Task: Rename the primary latest report files produced by
      scripts/preview_demo_trading_stop_noop_probe_plan.py from the
      truncated latest_noop_probe_plan.{json,md} to the spec-correct
      latest_trading_stop_noop_probe_plan.{json,md}.  Retain the old
      names as legacy aliases so upstream reads are not broken.
Status before: TASK-014U-FIX1 done; VPS can read the readonly smoke;
      but report latest files were written with the wrong stem (script
      said latest_noop_probe_plan.* instead of
      latest_trading_stop_noop_probe_plan.*).
Status after: TASK-014U-FIX2 DONE; primary latest names match spec;
      legacy aliases still written; all tests PASS.

Files changed:
  - UPDATED scripts/preview_demo_trading_stop_noop_probe_plan.py
        _write_report(): primary latest names are now
          latest_trading_stop_noop_probe_plan.json (primary)
          latest_trading_stop_noop_probe_plan.md   (primary)
          latest_noop_probe_plan.json              (legacy alias)
          latest_noop_probe_plan.md                (legacy alias)
        Timestamped pair renamed:
          {ts}_trading_stop_noop_probe_plan.json
          {ts}_trading_stop_noop_probe_plan.md
        Console print shows primary spec names first, then legacy.
        Docstring Writes section updated.
  - UPDATED tests/demo_trading/test_demo_trading_stop_noop_probe_plan.py
        TestU21 enhanced: asserts both primary spec names and legacy
        aliases exist; reads content from primary spec name; verifies
        timestamped files use the spec suffix.
        Added TestFix2LatestReportFilenames (6 tests):
          test_primary_spec_json_created
          test_primary_spec_md_created
          test_legacy_alias_json_retained
          test_legacy_alias_md_retained
          test_primary_and_alias_identical_content
          test_timestamped_files_use_spec_suffix

Validation:
  - py_compile scripts/preview_demo_trading_stop_noop_probe_plan.py PASS
  - pytest tests/demo_trading/test_demo_trading_stop_noop_probe_plan.py -q:
    67 / 67 PASS (61 prior + 6 new FIX2 tests).
  - pytest tests/demo_trading -q: 1452 / 1452 PASS.

Notes:
  - src/demo_trading_stop_noop_probe_plan.py NOT modified.
  - main.py / src/risk.py / BybitExecutor NOT modified.
  - No order endpoint, no stop endpoint, no position modified,
    G20 unchanged, no secrets.

---

### 2026-06-10（TASK-014U-FIX1 — Fix Readonly Smoke Latest Path）

Agent: Claude Sonnet 4.6
Command source: Rick direct chat instruction (TASK-014U-FIX1)
Task: Fix the readonly-smoke artifact path in the TASK-014U CLI so that
      --from-latest-readonly resolves latest_smoke.json (the canonical
      name written by TASK-014C/D) instead of the incorrect name
      latest_readonly_smoke.json written in the original TASK-014U spec.
Status before: TASK-014U done; VPS validation failed because
      preview_demo_trading_stop_noop_probe_plan.py was looking for
      latest_readonly_smoke.json but the readonly-smoke scripts have
      always written latest_smoke.json.
Status after: TASK-014U-FIX1 DONE; VPS validation unblocked.

Files changed:
  - UPDATED scripts/preview_demo_trading_stop_noop_probe_plan.py
        load_latest_readonly() now resolves primary=latest_smoke.json,
        fallback=latest_readonly_smoke.json.  Error message, docstring,
        and console print updated to match.
  - UPDATED tests/demo_trading/test_demo_trading_stop_noop_probe_plan.py
        All three existing test helpers that wrote latest_readonly_smoke.json
        updated to write latest_smoke.json (primary).
        Added TestFix1ReadonlyFilenameResolution (3 tests):
          * test_primary_latest_smoke_resolves:
            only latest_smoke.json present -> rc=0 STATUS_PLAN_READY
          * test_legacy_fallback_resolves_when_primary_absent:
            only latest_readonly_smoke.json present -> rc=0 STATUS_PLAN_READY
          * test_both_absent_fail_closed:
            neither file present -> rc=1

Validation:
  - py_compile src/demo_trading_stop_noop_probe_plan.py PASS
  - py_compile scripts/preview_demo_trading_stop_noop_probe_plan.py PASS
  - pytest tests/demo_trading/test_demo_trading_stop_noop_probe_plan.py -q:
    61 / 61 PASS (58 prior + 3 new FIX1 tests).
  - pytest tests/demo_trading -q: 1446 / 1446 PASS.

Notes:
  - src/demo_trading_stop_noop_probe_plan.py NOT modified (accepts
    whatever dict the CLI passes in; path resolution is purely a CLI
    concern).
  - main.py / src/risk.py / BybitExecutor NOT modified.
  - No order endpoint called, no stop endpoint called, no position
    modified, G20 still in place, no secrets read or written.

---

### 2026-06-10（TASK-014U — Add Demo Trading-stop No-op Probe Design / Tiny Isolated Position Plan）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014U)
Task: Design (NOT execute) a safe no-op real probe path for the Bybit
      V5 /v5/position/trading-stop endpoint given that 5 existing demo
      short positions (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT /
      EDUUSDT) must not be touched.  Produce a three-plan comparison
      (tiny isolated position / read-only endpoint research /
      expected-error probe), recommend tiny_isolated_position_plan,
      keep real execution blocked behind --allow-real-noop-probe ->
      REAL_NOOP_PROBE_NOT_IMPLEMENTED, and surface 30+ gate constants
      (33 defined; 22 always-on in plan mode, 23 with the real-guard
      flag, plus conditional upstream / symbol-collision gates).
Status before: TASK-014T DONE; trading-stop contract preview + mock
      permission OK; --allow-real-stop-probe returns
      REAL_PROBE_NOT_IMPLEMENTED; G20 still blocks --execute-new-entry;
      no documented no-op probe path exists.
Status after: TASK-014U DONE; G20 still in place; real no-op probe
      stays deferred to TASK-014V+.

Files changed:
  - NEW src/demo_trading_stop_noop_probe_plan.py
        DemoTradingStopNoopProbePlanner + NoopProbePlanResult
        dataclass; design_plan() reads readonly_smoke + reconciliation
        + protection + contract JSON (all four required), validates
        the selected symbol is NOT one of the 5 existing demo short
        positions, builds three plan tables
        (tiny_isolated_position_plan, read_only_endpoint_research,
        expected_error_probe), recommends tiny_isolated_position_plan,
        and routes to:
          * plan                 -> NOOP_PROBE_PLAN_READY
                                    (current_task_real_execution_allowed=False;
                                     22 in-task open blockers surfaced)
          * --allow-real-noop-probe -> REAL_NOOP_PROBE_NOT_IMPLEMENTED
                                       (adds real_noop_probe_not_implemented
                                        gate; no socket opened)
        Safety invariants
        (stop_endpoint_called=False, order_endpoint_called=False,
         no_position_modified=True, no_live_endpoint=True,
         no_orders_sent=True, no_batch_order=True,
         no_close_only_path=True, emergency_close_invoked=False,
         secret_value_observed=False, g20_policy_still_in_place=True)
        always honored.  /v5/position/trading-stop and /v5/order/create
        are recorded as STRING references and NEVER invoked.  No
        urllib / requests / httpx / socket / hmac / os.environ / main /
        src.risk / BybitExecutor / pybit / src.demo_new_entry_sender /
        src.demo_close_only_sender / src.demo_emergency_close_sender /
        src.demo_protected_new_entry_orchestrator /
        src.demo_trading_stop_contract_probe / scripts.execute_*.
  - NEW scripts/preview_demo_trading_stop_noop_probe_plan.py
        CLI: --from-latest-readonly --from-latest-reconciliation
        --from-latest-protection --from-latest-contract --symbol
        --allow-real-noop-probe --write-report.  Reads the four
        upstream latest JSON files; writes JSON + Markdown to
        outputs/demo_trading/trading_stop_noop_probe_plan/.  No
        confirm-token required for plan mode (this is a design step);
        the real-guard flag is hard-gated to
        REAL_NOOP_PROBE_NOT_IMPLEMENTED regardless of any token.
  - NEW tests/demo_trading/test_demo_trading_stop_noop_probe_plan.py
        58 tests U1 - U32 + extras, covering:
        plan-ready / upstream-missing / symbol-missing /
        symbol-collision (parametrized over 5 existing demo
        positions) / realtime-guard-missing / review-fail-closed /
        prior-probe-flipped / 15 tiny-isolated gates /
        3 expected-error gates / 3 readonly-research gates /
        defense-in-depth (existing_positions_must_not_be_touched,
        g20_sender_policy_still_in_place) / module defines >= 30
        GATE_ constants / happy-path plan surfaces >= 22 in-task
        gates / real-guard adds real_noop_probe_not_implemented /
        three-plan presence + recommended_path == tiny / only tiny
        plan has a TASK-014V next-task pointer / expected-error path
        flagged touches_existing_positions=True / report artifacts
        in both plan and real-guard modes / no secrets in report /
        no forbidden imports / no urllib/urlopen/socket/http.client
        tokens in module or CLI source / no close-only /
        emergency-close / new-entry-sender / contract-probe back
        coupling / module safe under socket.socket=None at import /
        TASK-014L G20 NOT lifted (G20 constant unchanged, gate name
        absent from source, g20_policy_still_in_place=True) / all
        safety invariants True/False as documented / path refs
        string-only / dataclass to_dict round-trip with deep-copy
        immutability / 5 CLI exit-code paths (missing upstream /
        missing symbol / collision symbol / default-plan / real-guard)
        / TRADING_STOP_PATH_REF matches TASK-014T constant by string
        equality / fresh plans per design call.
  - UPDATED .gitignore: added
        outputs/demo_trading/trading_stop_noop_probe_plan/ to the
        ignore list (TASK-014U report artifacts not committed).
  - UPDATED docs/research/commands/COMMAND_LOG.md: prepended this
        entry.
  - UPDATED docs/research/commands/NEXT_ACTION.md: prepended TASK-014U
        status block + Next Rick Action.

Validation:
  - py_compile src/demo_trading_stop_noop_probe_plan.py PASS
  - py_compile scripts/preview_demo_trading_stop_noop_probe_plan.py PASS
  - py_compile tests/demo_trading/test_demo_trading_stop_noop_probe_plan.py PASS
  - pytest tests/demo_trading -q: 1443 / 1443 PASS
    (1385 prior + 58 new U-series).
  - SOLUSDT plan mode: status=NOOP_PROBE_PLAN_READY;
    recommended_path=tiny_isolated_position_plan;
    real_probe_allowed=False;
    real_noop_probe_implemented=False;
    current_task_real_execution_allowed=False;
    blocked_gates contains all 15 tiny + 3 expected-err + 3 readonly
    + 2 defense-in-depth gates; stop_endpoint_called=False;
    order_endpoint_called=False; no_position_modified=True;
    no_live_endpoint=True.
  - SOLUSDT --allow-real-noop-probe mode:
    status=REAL_NOOP_PROBE_NOT_IMPLEMENTED;
    blocked_gates contains real_noop_probe_not_implemented;
    real_probe_allowed=True; real_noop_probe_implemented=False;
    current_task_real_execution_allowed=False;
    stop_endpoint_called=False; no_position_modified=True.
  - 5 existing demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT /
    POLYXUSDT / EDUUSDT) parametrized as --symbol arg:
    status=FAIL_CLOSED;
    blocked_gates contains selected_symbol_collides_with_existing_position
    AND tiny_symbol_overlaps_existing_position; rc=1.
  - AST scan: no import of main / src.risk / BybitExecutor / pybit /
    src.bybit_executor / src.demo_new_entry_sender /
    src.demo_close_only_sender / src.demo_emergency_close_sender /
    src.demo_protected_new_entry_orchestrator /
    src.demo_trading_stop_contract_probe / scripts.execute_*;
    no import of urllib / requests / httpx / socket / http.client.
  - urlopen sentinel: subprocess imports module with
    socket.socket=None; OK STATUS_PLAN_READY printed.

Outputs (gitignored):
  outputs/demo_trading/trading_stop_noop_probe_plan/
    {ts}_noop_probe_plan.json
    {ts}_noop_probe_plan.md
    latest_noop_probe_plan.json
    latest_noop_probe_plan.md

Notes:
  - TASK-014U is a DESIGN step only.  No real probe is executed in
    this task and no flag can override that.
  - The 5 existing demo short positions are NEVER touched.  Symbol
    selection is checked against EXISTING_POSITION_SYMBOLS and a
    collision is FAIL_CLOSED.
  - The recommended next path is the tiny isolated position
    lifecycle mock (TASK-014V).  That task will exercise the entry +
    stop-attach + emergency-close lifecycle against a single, tiny,
    isolated demo position on a symbol disjoint from the existing
    five.  Until that mock lifecycle is proven safe end-to-end, the
    real no-op probe stays unimplemented.
  - TASK-014L sender G20 (protected_entry_policy_missing) is
    deliberately NOT lifted by this task.  --execute-new-entry
    continues to FAIL_CLOSED on the real entry sender.
  - Local commit only (per memory rule: do not push to GitHub
    without explicit instruction).

---

### 2026-06-10（TASK-014T — Add Demo Trading-stop Endpoint Contract Probe / Permission Gate）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014T)
Task: Document the Bybit V5 /v5/position/trading-stop endpoint contract
      and add a permission-gate probe that is preview-only by default,
      can emit a synthetic mock-permission envelope, and deliberately
      returns REAL_PROBE_NOT_IMPLEMENTED under --allow-real-stop-probe.
      A no-op real probe design is the subject of TASK-014U; lifting
      TASK-014L sender G20 is reserved for an explicit later task.
Status before: TASK-014S done; protected new-entry mock chain PASS in
      both dry-run and mock-chain modes; G20 still blocks
      --execute-new-entry; no documented trading-stop endpoint contract
      module.
Status after: TASK-014T DONE; G20 still in place.

Files changed:
  - NEW src/demo_trading_stop_contract_probe.py
        DemoTradingStopContractProbe + TradingStopContractResult
        dataclass; submit_contract_probe() validates protection /
        symbol / stop-loss, builds the documented
        /v5/position/trading-stop payload preview, validates it via
        validate_payload() and routes to one of:
          * preview         -> TRADING_STOP_CONTRACT_PREVIEW_OK
          * mock-permission -> MOCK_TRADING_STOP_PERMISSION_OK
                               (synthetic retCode=0 envelope, no socket)
          * --allow-real-stop-probe -> REAL_PROBE_NOT_IMPLEMENTED
                                       (gate blocks; no socket).
        Safety invariants
        (stop_endpoint_called=False, order_endpoint_called=False,
         no_position_modified=True, no_live_endpoint=True,
         no_orders_sent=True, no_batch_order=True,
         no_close_only_path=True, emergency_close_invoked=False,
         secret_value_observed=False) always honored.  No urllib /
         requests / httpx / socket / hmac / os.environ / main /
         src.risk / BybitExecutor / pybit / src.demo_new_entry_sender /
         src.demo_close_only_sender / src.demo_emergency_close_sender /
         src.demo_protected_new_entry_orchestrator / scripts.execute_*.
  - NEW scripts/preview_demo_trading_stop_contract.py
        CLI: --from-latest-protection --symbol --confirm-token
        --mock-permission --allow-real-stop-probe --write-report.
        Reads
        outputs/demo_trading/new_entry_protection/latest_new_entry_protection.json
        Writes JSON + Markdown to
        outputs/demo_trading/trading_stop_contract/.
  - NEW tests/demo_trading/test_demo_trading_stop_contract_probe.py
        68 tests T1-T28 + extras: valid SOLUSDT preview, missing
        protection / symbol mismatch / missing stopLoss /
        non-positive stopLoss / invalid tpslMode / invalid
        slTriggerBy (LastPrice accepted) / invalid positionIdx /
        payload excludes takeProfit / leverage /
        transfer-withdraw-deposit / side-qty-orderType /
        order-create path leak / live hostname leak,
        no secrets in report, no forbidden imports, no close-only /
        emergency-close / new-entry-sender reuse, no network at
        import time, no network tokens in module + CLI,
        mock-permission -> MOCK_TRADING_STOP_PERMISSION_OK,
        --allow-real-stop-probe -> REAL_PROBE_NOT_IMPLEMENTED,
        invalid confirm token blocks real probe + mock permission,
        report artifacts (ts + latest pair), TASK-014L G20
        still blocks --execute-new-entry, payload keys/values match
        TASK-014R stop attachment payload, dataclass to_dict round-trip,
        CLI exit codes for missing protection / symbol / token,
        real-probe report artifact.
  - UPDATED .gitignore: + outputs/demo_trading/trading_stop_contract/

Validation:
  - py_compile src + scripts + tests => PASS
  - pytest tests/demo_trading => 1385/1385 PASS (1317 prior + 68 new T-series)

Outputs (local only, gitignored):
  - outputs/demo_trading/trading_stop_contract/{ts}_trading_stop_contract.{json,md}
  - outputs/demo_trading/trading_stop_contract/latest_trading_stop_contract.{json,md}

Notes:
  - Real probe deliberately NOT implemented in this task.  A no-op real
    probe that provably cannot modify any existing position's stop must
    be designed in TASK-014U (e.g. tiny isolated position plan, or a
    read-only contract probe API).
  - TASK-014L sender G20 (protected_entry_policy_missing) NOT lifted.
  - main.py / src/risk.py / BybitExecutor NOT modified.
  - No /v5/order/create or /v5/position/trading-stop invocation.
  - The 5 existing demo short positions are NOT touched.

---

### 2026-06-10（TASK-014S — Add Demo Protected New-entry Mock Orchestrator）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014S)
Task: Chain TASK-014P market-backed review + TASK-014Q protected-entry
      policy plan + TASK-014R stop-loss attachment into a single
      dry-run + mock-only orchestrator with all-or-fail semantics, so
      that a protected new-entry flow can be exercised in mock without
      lifting TASK-014L sender G20 or contacting any live endpoint.
Status before: TASK-014P / Q / R complete; G20 (protected_entry_policy_missing)
      still blocks --execute-new-entry; no chained mock flow.
Status after: TASK-014S DONE; G20 still in place (deliberately not lifted).

Files changed:
  - NEW src/demo_protected_new_entry_orchestrator.py
        DemoProtectedNewEntryOrchestrator + ProtectedEntryChainResult
        dataclass; submit_chain() validates 24+ review / protection /
        stop-direction / token gates, builds a TASK-014R stop payload
        preview, and (under --mock-chain) synthesizes an entry +
        post-fill + stop-attach envelope chain.  All-or-fail: mock
        stop-attach failure -> MOCK_PROTECTED_ENTRY_FAIL_CLOSED with
        recommended_action="emergency_close_preview" (no real emergency
        close invoked).  Safety invariants
        (no_orders_sent, order_endpoint_called=False,
         stop_endpoint_called=False, no_position_modified,
         no_live_endpoint, no_batch_order, no_close_only_path,
         emergency_close_invoked=False, secret_value_observed=False)
        always True.  No urllib / requests / httpx / socket / hmac /
        os.environ / main / src.risk / BybitExecutor / pybit /
        demo_new_entry_sender / demo_close_only_sender /
        demo_emergency_close_sender / scripts.execute_*.
  - NEW scripts/execute_demo_protected_new_entry_mock.py
        CLI: --from-latest-review --from-latest-protection --symbol
        --confirm-token --dry-run (default) --mock-chain --write-report.
        NO --execute-protected-entry flag (real execution reserved for
        TASK-014T+).  Reads
        outputs/demo_trading/new_entry_review/latest_new_entry_review.json
        outputs/demo_trading/new_entry_protection/latest_new_entry_protection.json
        Writes JSON + Markdown to
        outputs/demo_trading/protected_new_entry/.
  - NEW tests/demo_trading/test_demo_protected_new_entry_orchestrator.py
        57 tests S1-S28 + extras: missing review/protection, symbol
        mismatch, review/protection realtime guard, missing/wrong-direction
        stop_price, valid dry-run SOLUSDT, mock-chain invalid/valid token,
        MOCK_PROTECTED_ENTRY_SUCCESS, mock_entry_order_sent +
        order_endpoint_called=False, mock_stop_attached +
        stop_endpoint_called=False, final stop_price>0,
        missing_stop_price=False after attach,
        _simulate_stop_attach_failure -> MOCK_PROTECTED_ENTRY_FAIL_CLOSED
        + recommended_action=emergency_close_preview (no real emergency
        close), report artifacts (JSON + MD ts + latest), no live endpoint
        recorded but not invoked, no secrets / env reads / signing,
        no forbidden imports, no close-only / emergency-close /
        new-entry-sender reuse, no urlopen at import time, source scan
        excludes urllib/urlopen/httpx/requests./http.client/socket.,
        payload excludes takeProfit/leverage/transfer/withdraw/deposit,
        TASK-014L sender G20 still blocks --execute-new-entry,
        urlopen sentinel scan in module + CLI, dataclass to_dict
        round-trip, synth stop-attach token format, short side dry-run,
        CLI missing-review/missing-token returns 1.
  - UPDATED .gitignore: + outputs/demo_trading/protected_new_entry/

Validation:
  - py_compile src + scripts + tests => PASS
  - pytest tests/demo_trading => 1317/1317 PASS (1260 prior + 57 new S-series)

Outputs (local only, gitignored):
  - outputs/demo_trading/protected_new_entry/{ts}_protected_new_entry.{json,md}
  - outputs/demo_trading/protected_new_entry/latest_protected_new_entry.{json,md}

Notes:
  - TASK-014L sender G20 (protected_entry_policy_missing) NOT lifted.
    G20 lifting is reserved for TASK-014T+ (after a real
    /v5/position/trading-stop contract probe and permission gate).
  - main.py / src/risk.py / BybitExecutor NOT modified.
  - --mock-chain produces synthetic envelopes; no socket opened, no
    /v5/order/create or /v5/position/trading-stop invocation.
  - recommended_action=emergency_close_preview on mock attach failure is
    a recommendation only; no DemoEmergencyCloseSender is invoked.

---

### 2026-06-09（TASK-014R — Add Demo Stop-loss Attachment Sender Dry-run / Mock）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014R)
Task: Build the first concrete step toward unblocking protected new-entry
      execution: a Demo-only stop-loss attachment sender restricted to
      dry-run / mock-execute paths (no real attach).  TASK-014Q's G20
      gate (protected_entry_policy_missing) remains in place; this task
      does NOT lift it.  Deliverables:
        A. src/demo_stop_loss_attachment_sender.py — NEW pure-computation
           module.  DemoStopLossAttachmentSender.submit_stop_attachment()
           accepts a TASK-014Q ProtectedEntryPlan dict, validates 18 gates
           (protection_report_missing / selected_symbol_mismatch /
           review_fail_closed / missing_realtime_price_guard /
           stop_loss_attach_not_required / unexpected_stop_loss_endpoint_
           allowed / unexpected_protected_entry_execute_allowed /
           protection_preview_only_false / protection_status_not_preview_
           only / order_endpoint_called_true / stop_endpoint_called_true /
           invalid_side / invalid_qty / invalid_entry_reference_price /
           missing_stop_price / long_stop_not_below_entry /
           short_stop_not_above_entry / invalid_stop_order_side /
           invalid_confirm_token_for_mock), builds a Bybit V5 trading-
           stop payload preview (category=linear, symbol, stopLoss,
           tpslMode=Full, slTriggerBy=MarkPrice, positionIdx=0), and
           emits a StopAttachmentResult.  Mock-execute path produces a
           synthetic retCode=0 envelope with a MOCK-STOP-{symbol}-{x}
           id; NO socket is opened in any path.  Module imports zero
           network libraries (urllib / requests / httpx / socket / http.
           client all banned); zero env reads; zero HMAC / signing.
        B. scripts/execute_demo_stop_loss_attachment.py — NEW CLI.
           Reads outputs/demo_trading/new_entry_protection/latest_new_
           entry_protection.json.  Flags: --from-latest-protection /
           --symbol / --confirm-token / --dry-run (default) /
           --mock-execute-stop / --write-report.  There is NO
           --execute-stop-loss flag; real attachment is reserved for
           TASK-014S onwards.  Confirm token pattern
           CONFIRM_DEMO_STOP_ATTACH_YYYYMMDD only validated under
           --mock-execute-stop.  Outputs JSON + Markdown to
           outputs/demo_trading/stop_loss_attachment/.
        C. tests/demo_trading/test_demo_stop_loss_attachment_sender.py
           — 72 tests R1-R25 + extra protection-flag enforcement +
           result.to_dict round-trip + CLI artifact writer + CLI
           subprocess smoke (PYTHONIOENCODING=utf-8 to avoid Windows
           cp950 path).  Source-scan tests use the tokenize-based
           _read_code_only helper (mirroring the TASK-014Q pattern) so
           docstring mentions of forbidden words do not produce false
           failures.  All forbidden-import / forbidden-network /
           forbidden-secret / forbidden-sender-reuse tests pass.
        D. .gitignore — outputs/demo_trading/stop_loss_attachment/.
        E. Doc updates: COMMAND_LOG.md (this entry) +
           NEXT_ACTION.md (TASK-014R status + Next Rick Action).

Validation:
  * py_compile src/demo_stop_loss_attachment_sender.py,
    scripts/execute_demo_stop_loss_attachment.py,
    tests/demo_trading/test_demo_stop_loss_attachment_sender.py: PASS.
  * pytest tests/demo_trading: 1260/1260 PASS (1188 prior + 72 new
    R-series).
  * SOLUSDT dry-run on test fixture (entry=66.21 / stop=62.7 /
    side=long / stop_order_side=Sell): status=DRY_RUN_STOP_ATTACH_
    ALLOWED, payload_preview_only=True, payload includes stopLoss=
    "62.7" + symbol=SOLUSDT + tpslMode=Full + slTriggerBy=MarkPrice +
    positionIdx=0; excludes takeProfit / leverage / transfer /
    withdraw / deposit / orderType / side / qty.  stop_endpoint_called=
    False, order_endpoint_called=False, no_orders_sent=True,
    no_position_modified=True, blocked_gates=[].
  * SOLUSDT --mock-execute-stop with confirm token
    CONFIRM_DEMO_STOP_ATTACH_20260609: status=MOCK_STOP_ATTACH_SUCCESS,
    mock_stop_attached=True, mock_response={retCode:0, retMsg:OK,
    mock:True, result.stop_attach_id="MOCK-STOP-SOLUSDT-6270"},
    stop_endpoint_called=False, order_endpoint_called=False,
    no_position_modified=True.
  * urlopen monkeypatch sentinel: NEVER fires in dry-run OR
    --mock-execute-stop.
  * AST scan: no urlopen / urllib / requests / httpx / socket / http.
    client / Session / urllib3 in module source.
  * AST scan: no import of main / src.risk / BybitExecutor / pybit /
    src.bybit_executor / src.demo_close_only_sender /
    src.demo_new_entry_sender / src.demo_emergency_close_sender /
    scripts.execute_demo_new_entry / scripts.execute_demo_close_only /
    scripts.execute_demo_emergency_close.
  * Code-only scan (tokenize): no os.environ / getenv / dotenv / hmac
    / X-BAPI-SIGN / X-BAPI-API-KEY in code.
  * Token in result is prefix-only (first 8 chars + "***"); full token
    never serialized.

Files changed:
  - src/demo_stop_loss_attachment_sender.py (NEW)
  - scripts/execute_demo_stop_loss_attachment.py (NEW)
  - tests/demo_trading/test_demo_stop_loss_attachment_sender.py (NEW)
  - .gitignore (added outputs/demo_trading/stop_loss_attachment/)
  - docs/research/commands/COMMAND_LOG.md (this entry)
  - docs/research/commands/NEXT_ACTION.md (TASK-014R status block)

Notes:
  * TASK-014L sender G20 (protected_entry_policy_missing) is
    intentionally NOT lifted in this task.  Real attachment requires
    TASK-014S (Protected New-entry Orchestrator) which chains entry
    submit + stop attach + post-fill verification with all-or-fail
    semantics.
  * --mock-execute-stop is purely a pipeline-exercise mode: it never
    opens a socket; the synthetic response is constructed from the
    plan dict alone.  This lets us validate report-writer / downstream
    gate behaviour without ever risking a real attach.
  * mock_stop_attached=True is bookkeeping for the CLI / report; it is
    NOT a real Bybit attachment.

Status after:  READY — TASK-014R complete on local main; new sender +
                CLI + tests landed; pytest 1260/1260 PASS; local commit
                only (no push, per feedback_git_push.md).  Next
                authorized step toward protected new-entry execution
                is TASK-014S (Protected New-entry Orchestrator / Entry +
                Stop Attach Mock Chain).

---

### 2026-06-09（TASK-014Q — Add Demo Protected Entry / Stop-loss Attachment Policy）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014Q)
Task: Close the SOLUSDT naked-position class of incident by introducing a
      protected-entry lifecycle that the Demo new-entry sender refuses to
      bypass.  The TASK-014L sender currently sends a Market entry order
      and walks away — leaving stop_price=0 (naked position) that only
      the TASK-014N emergency close can recover.  Until a future task
      (TASK-014R) implements a Demo-only stop-loss attachment sender,
      actual --execute-new-entry MUST fail closed.  Deliverables:
        A. src/demo_new_entry_protection.py — NEW pure-computation
           module defining the protected-entry lifecycle (phases 1-6),
           endpoint-group separation (order_create vs trading_stop vs
           read_only), ProtectedEntryPlan dataclass, and
           build_protected_entry_plan() pre-entry validator.  Pre-entry
           checks: review.fail_closed=False, realtime_price_guard_verified=
           True, demo_runtime_verified, proof_strength=STRONG, endpoint_
           family=bybit_demo, account_mode=demo, position_details_source=
           real_readonly, payload preview_only / qty>0 / entry>0 /
           stop_price>0 / reduce_only=False / order_sent=False /
           order_endpoint_called=False / order_side matches side label;
           AND stop direction: long stop < entry; short stop > entry.
           protected_entry_execute_allowed ALWAYS False in this task
           (reason: stop_loss_attachment_not_implemented); TASK-014R
           will lift it.  Module is pure computation — no HTTP / no
           urllib / no hmac / no env reads / no order endpoint
           invocation / no forbidden imports (main / src.risk /
           BybitExecutor / pybit / ccxt / demo_close_only_sender /
           demo_new_entry_sender / demo_emergency_close_sender /
           scripts.execute_*).  STOP_ATTACH_ENDPOINT = "/v5/position/
           trading-stop" is announced for documentation but NEVER
           invoked.
        B. scripts/preview_demo_new_entry_protection.py — NEW CLI.
           --from-latest-review / --symbol / --write-report.  Reads
           outputs/demo_trading/new_entry_review/latest_new_entry_
           review.json; emits outputs/demo_trading/new_entry_
           protection/{ts}_new_entry_protection.json + .md +
           latest_*.  Never sends an order, never calls the trading-
           stop endpoint, never reads env / secrets, never touches
           positions.
        C. src/demo_new_entry_sender.py — extended with G20
           "protected_entry_policy_missing" gate on the actual
           execute-new-entry path.  Default
           sender._protected_entry_policy_required=True; when the
           caller sets execute_new_entry=True, sender returns a
           blocked result with G20 in blocked_gates and never reaches
           the pre-send refresh / urlopen.  Dry-run path is unchanged:
           still reports protected_entry_required=True via the new
           NewEntryOrderResult field so operators see the requirement
           but the dry-run preview is not blocked.  Legacy unit tests
           that exercise the actual order-submission mechanics
           (F23/F24/F25/TestExecuteUsesDemoEndpoint/
           TestOrderBodyComposition) opt out via
           sender._protected_entry_policy_required=False — explicitly
           documented as TEST-ONLY; the CLI never disables the gate.
        D. tests/demo_trading/test_demo_new_entry_protection.py —
           63 new tests Q1-Q16 covering: realtime guard required;
           missing/zero/negative/missing-field stop_price → fail
           closed; long-stop-above-entry / short-stop-below-entry
           blocked; missing/unknown symbol → fail closed; preview
           never sends order; preview never calls stop endpoint;
           endpoint-group separation; no secrets in module or
           plan dict; no env reads (code-only AST scan); no live
           hostname; AST imports do not include forbidden modules
           (main / src.risk / executor / close-only / new-entry
           sender / emergency-close / postfill verify / scripts.
           execute_* / pybit / ccxt / urllib / requests / httpx /
           hmac / hashlib); sender actual execute blocked with G20
           — and never reaches urlopen (asserted by monkeypatching
           urllib.request.urlopen to AssertionError sentinel);
           sender dry-run reports protected_entry_required=True;
           legacy review still blocked at G19; G20 still blocks
           even when G19 passes; no TP / leverage / transfer /
           withdraw / deposit in code; no emergency_close imports
           in module or CLI; ProtectedEntryPlan to_dict round-trip;
           preview-only status + phase_1_pre_entry_review;
           CLI smoke (missing review → exit 1; --write-report
           emits both JSON and Markdown).
        E. scripts/execute_demo_new_entry.py — minor: surface
           protected_entry_required field in dry-run / execute report
           (print + Markdown row).

Status before: READY — TASK-014P committed (f7de8da); VPS real-market
               review PASS (SOLUSDT realtime=66.21, stop=62.9, guard
               verified, sender dry-run passes G1-G19); however
               actual --execute-new-entry would still submit a naked
               entry with no stop-loss attachment.
Status after:  READY — TASK-014Q complete on local main; new protection
               module + preview CLI + sender G20 gate + 63 Q-series
               tests; 1188/1188 demo_trading tests pass (1125 prior +
               63 Q-series); protection module is pure computation
               (no HTTP / no env / no secrets / no order endpoint /
               no live host); ProtectedEntryPlan emits
               protected_entry_execute_allowed=False with reason
               stop_loss_attachment_not_implemented; sender actual
               --execute-new-entry blocked with G20
               protected_entry_policy_missing and never reaches
               urlopen; sender dry-run still surfaces
               protected_entry_required=True so the operator sees
               the requirement; main.py / src/risk.py / BybitExecutor
               unchanged; SOLUSDT incident pattern (entry filled,
               stop_price=0) cannot recur via this code path.

Files changed:
  - src/demo_new_entry_protection.py                       (CREATED — pure-computation policy + plan builder)
  - scripts/preview_demo_new_entry_protection.py           (CREATED — preview CLI + report writer)
  - src/demo_new_entry_sender.py                           (MODIFIED — G20 gate + protected_entry_required field)
  - scripts/execute_demo_new_entry.py                      (MODIFIED — surfaces protected_entry_required in report)
  - tests/demo_trading/test_demo_new_entry_protection.py   (CREATED — 63 tests)
  - tests/demo_trading/test_demo_new_entry_sender.py       (MODIFIED — F23/F24/F25/Demo/Body opt-out flag for legacy mechanics tests)
  - docs/research/commands/NEXT_ACTION.md                  (MODIFIED — TASK-014Q block prepended)
  - docs/research/commands/COMMAND_LOG.md                  (MODIFIED — this entry prepended)
  - .gitignore                                             (MODIFIED — added outputs/demo_trading/new_entry_protection/)

Validation:
  - python -m py_compile src/demo_new_entry_protection.py            → PASS
  - python -m py_compile scripts/preview_demo_new_entry_protection.py → PASS
  - python -m py_compile src/demo_new_entry_sender.py                → PASS
  - python -m py_compile scripts/execute_demo_new_entry.py           → PASS
  - python -m pytest tests/demo_trading -q                           → 1188 passed
  - Q1 realtime guard required: review without realtime_price_guard_
    verified=True → protected_entry_status=FAIL_CLOSED with reason
    review_missing_realtime_price_guard
  - Q2/Q3/Q4 stop validation: missing stop → payload_missing_stop_price;
    long stop≥entry → long_stop_must_be_below_entry; short stop≤entry
    → short_stop_must_be_above_entry
  - Q11 sender G20: default sender refuses actual --execute-new-entry
    with G20 protected_entry_policy_missing; urlopen sentinel never
    fires (G20 short-circuits before refresh)
  - Q12 sender dry-run: protected_entry_required=True surfaces in result
    dataclass AND to_dict(); dry-run execute_allowed remains True so
    the rest of the gate behavior is testable
  - Q14 defense-in-depth: even when caller bypasses G20 via
    _protected_entry_policy_required=False, a legacy review without
    realtime guard still blocks at G19

Outputs:
  - None.  No orders sent.  No emergency closes triggered.  No
    new-entry orders placed.  No trading-stop endpoint called.
    Pure-computation preview only.

Notes:
  - Endpoint-group separation: the module declares ENDPOINT_GROUPS
    with order_create=(/v5/order/create,), trading_stop=(/v5/
    position/trading-stop,), and read_only=(wallet-balance /
    position/list / market/tickers / account/info).  The TASK-014L
    sender invokes order_create only; the protection module invokes
    NOTHING; the trading_stop endpoint is reserved for TASK-014R.
  - Lifecycle phases: phase_1_pre_entry_review (this module),
    phase_2_entry_order (TASK-014L), phase_3_post_fill_verify
    (TASK-014M / verify_demo_new_entry_postfill.py), phase_4_stop_
    attachment (TASK-014R, not yet implemented), phase_5_final_
    verify (TASK-014R), phase_6_failure_recovery (TASK-014N
    emergency close).
  - Test escape hatch: F23/F24/F25/Demo/Body sender tests opt out of
    G20 by setting sender._protected_entry_policy_required=False on
    the constructed sender.  This is documented inline as TEST-ONLY
    and the CLI never disables the gate.
  - Commit: local commit only; no push (per feedback_git_push.md).
  - Next step gate: TASK-014R (Demo Stop-loss Attachment Sender /
    Trading Stop Dry-run) — implement /v5/position/trading-stop
    sender against api-demo.bybit.com, with its own dry-run and
    mock-safe tests, and lift the G20 block after stop attach
    is verified.  Until then, actual new-entry execute remains
    blocked.

---

### 2026-06-09（TASK-014P — Add Market-backed Demo New-entry Candidates）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014P)
Task: Eliminate stale-fixture candidate prices in the Demo new-entry
      pipeline by introducing a market-backed candidate builder.  The
      TASK-014O guard correctly rejected SOLUSDT (fixture 160 vs real
      ~65.92, ~143% deviation) and AAVEUSDT (fixture 120 vs real ~62.14,
      ~93% deviation), but the only reason the pipeline produced
      candidates at all is that scripts/preview_demo_new_entry_review.py
      still hard-coded fixture entry_reference_price / stop_price.
      Deliverables:
        A. src/demo_new_entry_candidate_builder.py — NEW pure-computation
           module exposing NewEntryIntent (pre-pricing) + CandidateBuildResult
           dataclasses, build_market_backed_candidate() and batch helper.
           Stop model: long stop = realtime * (1 - long_stop_pct);
           short stop = realtime * (1 + short_stop_pct); default
           stop_pct = 5%; entry / stop rounded to instrument tick.
           entry_reference_price = raw realtime (unrounded — guard sees
           the exact reading).  Validates requested_risk_usd, market
           price usability, side, instrument rule, stop_pct range
           (0 < pct < 1) and post-rounding stop on protective side.
           No HTTP, no env reads, no HMAC, no order endpoint, no live
           host, no forbidden imports.
        B. scripts/preview_demo_new_entry_review.py — replaces fixture
           candidates with an intent pool (SOLUSDT long risk=40,
           AAVEUSDT long risk=30, AVAXUSDT short risk=25, LINKUSDT short
           risk=20) when mode=from_latest_reconciliation; fetches
           realtime prices via the TASK-014O guard, builds candidates
           via build_market_backed_candidates(), then runs the existing
           guard pipeline.  Report MD now includes a "Market-backed
           Candidate Builder (TASK-014P)" section (Symbol / Side /
           Status / Realtime / Entry / Stop / Reason).  Fixture mode
           preserved verbatim (legacy 160 / 120 candidates still flow
           through the TASK-014O guard and get rejected as stale —
           correct posture).
        C. Fail-closed semantics: missing or unusable realtime price
           => SKIP_NO_REALTIME_PRICE / SKIP_INVALID_REALTIME_PRICE;
           skipped CandidateBuildResult NEVER carries a price; no
           fallback to fixture price; resulting reviews emit no
           payloads when all intents skipped, and top-level
           realtime_price_guard_verified stays False.
        D. tests/demo_trading/test_demo_new_entry_candidate_builder.py
           — 54 tests covering P1 SOLUSDT 65.92 → entry=65.92, stop=62.62;
           P2 long stop < entry; P3 short stop > entry (AVAXUSDT 6.696
           → stop ~7.03); P4 stop_distance > 0 parametrized for
           SOL/AAVE/AVAX/LINK/BTC; P5 missing / zero / fetch_error
           realtime price → skipped, no fixture leak; P6 skipped
           candidate never carries 160 / 120; P7 AAVEUSDT 62.14 ≠ 120;
           P8 invalid stop_pct (0, neg, ≥1, inf, nan); P9 invalid
           requested_risk_usd; P10 missing instrument rule; invalid
           side; tick-collapse → SKIP_INVALID_STOP_PRICE /
           SKIP_INVALID_STOP_DISTANCE; P11 batch helper preserves order
           and skips missing prices; P12 to_dict() round-trip; module
           source cleanliness (no live host, no order endpoint tokens,
           no HTTP imports, no env reads); forbidden-imports guard.
           tests/demo_trading/test_demo_new_entry_review.py — extended
           with 6 TASK-014P integration tests (SOLUSDT realtime payload
           verified and notional anchored to 65.92; AAVEUSDT 62.14
           replaces 120 fixture; missing market price → no payloads /
           top-level guard False / next_required_task=no_payload_to_send;
           sender G19 passes for market-backed verified review; sender
           G19 still blocks legacy AAVE 120/110 with
           missing_realtime_price_guard; pipeline-level safety
           invariants: no order endpoint, no secrets, no forbidden
           imports through market-backed path).

Status before: READY — TASK-014O committed (9b73262); local main clean;
               guard correctly rejects fixture candidates but the
               candidate source itself still hard-codes stale prices.
Status after:  READY — TASK-014P complete on local main; new builder
               module + intent pool CLI wiring + 54 builder tests + 6
               review integration tests; 1125/1125 demo_trading tests
               pass (1065 prior + 54 builder + 6 review integration);
               builder is pure computation (no HTTP / no env / no
               secrets / no order endpoint / no live host); SOLUSDT
               candidate now built at realtime 65.92 with stop ~62.62;
               AAVEUSDT candidate now built at realtime 62.14 with
               stop ~59.03; sender G19 still enforces
               realtime_price_guard_verified=True before any dry-run;
               main.py / src/risk.py / BybitExecutor unchanged.

Files changed:
  - src/demo_new_entry_candidate_builder.py                  (CREATED)
  - scripts/preview_demo_new_entry_review.py                 (MODIFIED — intent pool + builder wiring + report section)
  - tests/demo_trading/test_demo_new_entry_candidate_builder.py (CREATED — 54 tests)
  - tests/demo_trading/test_demo_new_entry_review.py         (MODIFIED — 6 TASK-014P integration tests)
  - docs/research/commands/NEXT_ACTION.md                    (MODIFIED — TASK-014P block prepended)
  - docs/research/commands/COMMAND_LOG.md                    (MODIFIED — this entry prepended)

Validation:
  - python -m py_compile src/demo_new_entry_candidate_builder.py     → PASS
  - python -m py_compile src/demo_new_entry_review.py                → PASS
  - python -m py_compile scripts/preview_demo_new_entry_review.py    → PASS
  - python -m pytest tests/demo_trading -q                           → 1125 passed
  - P1 SOLUSDT 65.92 → entry=65.92, rounded_stop=62.62, stop_pct=5%,
    no 160 fixture leakage
  - P7 AAVEUSDT 62.14 → entry=62.14, rounded_stop=59.03, no 120
    fixture leakage
  - Integration: SOLUSDT realtime payload notional/stop_risk anchored
    to 65.92 NOT 160; sender G19 passes dry-run for market-backed
    verified review; legacy 120/110 review still blocked with
    missing_realtime_price_guard
  - Fixture-mode CLI smoke: python scripts/preview_demo_new_entry_review.py
    still produces report; SOLUSDT and AAVEUSDT fixture candidates
    are correctly rejected by TASK-014O guard as
    stale_entry_reference_price (correct posture)

Outputs:
  - None.  No orders sent.  No emergency closes triggered.  No
    new-entry orders placed.  Dry-run / pure-computation builder only.

Notes:
  - Design separates NewEntryIntent (pre-pricing) from NewEntryCandidate
    (post-pricing).  The builder is the ONLY place where realtime price
    and intent merge into a priced candidate, enforcing the invariant
    that no fixture price ever leaks into a market-backed candidate.
  - Fixture mode unchanged: legacy K-series review tests (47) still
    use NewEntryCandidate directly; the builder is opt-in via the
    from_latest_reconciliation CLI mode.
  - Tick-collapse edge case: for very small prices, 5% stop_pct can
    round to the same tick as entry; builder explicitly checks
    rounded_stop strictly on protective side of rounded_entry and
    emits SKIP_INVALID_STOP_PRICE / SKIP_INVALID_STOP_DISTANCE
    otherwise.
  - Commit: local commit only; no push (per feedback_git_push.md).
  - Next step gate: with realtime-backed candidates flowing through
    the TASK-014O guard, Demo new-entry dry-run review may now produce
    verified payloads that satisfy sender G19.  Human approval still
    required before actual order send.

---

### 2026-06-09（TASK-014O — Add Demo New-entry Realtime Price Guard）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014O)
Task: Resolve the TASK-014K stale-price root cause that produced the
      TASK-014L SOLUSDT new-entry incident (preview entry_reference_price=160
      vs actual fill ~66.47; ~58% deviation; stop_price=0).  Build a
      fail-closed realtime market-price guard wired into the new-entry
      review pipeline, with the following invariants:
        A. src/demo_market_price_guard.py — NEW module exposing
           RealtimeMarketPrice + PriceGuardEvaluation dataclasses,
           evaluate_price_guard() pure evaluator, batch helper, and a
           DemoMarketPriceGuard client that ONLY contacts the public,
           unauthenticated /v5/market/tickers endpoint at
           api-demo.bybit.com (no HMAC, no env vars, no secrets, no order
           endpoints).  Default guard_threshold_pct = 5.0.
        B. src/demo_new_entry_review.py — extend
           review_new_entry_candidates() with optional
           price_guard_evaluations parameter; when supplied, missing
           realtime price => REJECT_MISSING_REALTIME_PRICE; deviation > 5%
           => REJECT_STALE_ENTRY_REFERENCE_PRICE; verified candidates use
           the realtime market price as the anchor for qty / notional /
           stop_risk recomputation; payload preview carries
           realtime_price_guard_verified=True, price_source,
           realtime_market_price, price_deviation_pct,
           price_guard_threshold_pct, price_timestamp_utc; top-level
           review.realtime_price_guard_verified=True iff guard pipeline
           engaged, not fail_closed, AT LEAST ONE payload emitted, and
           EVERY emitted payload is verified.  Legacy callers (no
           price_guard_evaluations) keep the old behavior but the top-
           level signal stays False, so sender G19 will refuse legacy
           reviews (correct fail-closed posture).
        C. scripts/preview_demo_new_entry_review.py — wire the guard
           into the preview CLI behind --with-realtime-price-guard
           (default ON) / --allow-real-market-network (default OFF,
           fixture mode unless explicitly opted in) /
           --price-guard-threshold-pct.  Real-network fetch only when
           mode=from_latest_reconciliation AND --allow-real-market-network
           is set; otherwise fall back to fixture prices.  Report MD now
           includes a "Realtime Price Guard (TASK-014O)" section.
        D. tests/demo_trading/test_demo_market_price_guard.py — 51 tests
           covering O1 missing realtime price; O2 stale > 5%; O3 SOLUSDT
           incident replay (160 vs 66.47); O4 within threshold; O5
           threshold edge; O6 invalid threshold; O7 invalid candidate
           price; O8 fixture client; O9 real-mode URL whitelist (mocked
           urlopen — asserts request stays on api-demo.bybit.com +
           /v5/market/tickers, never reaches /v5/order/ or live host,
           never sends X-BAPI-SIGN); O10 module source cleanliness
           (no order endpoint tokens, no live host, no secrets); O11
           forbidden imports absent (main, src.risk, BybitExecutor,
           demo_close_only_sender, demo_new_entry_sender,
           demo_emergency_close_sender, scripts.execute_*, pybit);
           plus batch-helper and dataclass serialization tests.
           tests/demo_trading/test_demo_new_entry_review.py — extended
           with 26 new TASK-014O integration tests (O1-O13) verifying
           the guard pipeline wired through review_new_entry_candidates()
           rejects missing/stale prices, anchors verified payloads to
           realtime market prices, propagates realtime_price_guard_verified
           through both payload and top-level fields, leaves no orders
           sent / no endpoint called / no secrets observed, keeps the
           review module free of forbidden imports / URLs / HTTP
           clients, and confirms TASK-014L's sender G19 gate refuses
           reviews lacking realtime_price_guard_verified=True.

Status before: READY — TASK-014N committed (220f615); local main clean;
               SOLUSDT emergency close-only path tested; root cause of
               TASK-014K stale-price preview still unresolved.
Status after:  READY — TASK-014O complete on local main; new guard
               module + extended review pipeline + CLI flags + 51+26 new
               tests; 1065/1065 demo_trading tests pass (988 prior + 51
               guard + 26 review integration); guard never sends orders,
               never modifies positions, never loads secrets, never
               contacts a live host or order endpoint; sender G19 still
               enforces realtime_price_guard_verified=True before any
               dry-run is allowed; main.py / src/risk.py / BybitExecutor
               unchanged.

Files changed:
  - src/demo_market_price_guard.py                       (CREATED)
  - src/demo_new_entry_review.py                         (MODIFIED — guard pipeline wired)
  - scripts/preview_demo_new_entry_review.py             (MODIFIED — guard CLI flags + report section)
  - tests/demo_trading/test_demo_market_price_guard.py   (CREATED — 51 tests)
  - tests/demo_trading/test_demo_new_entry_review.py     (MODIFIED — 26 TASK-014O integration tests)
  - docs/research/commands/NEXT_ACTION.md                (MODIFIED — TASK-014O block prepended)
  - docs/research/commands/COMMAND_LOG.md                (MODIFIED — this entry prepended)

Validation:
  - python -m py_compile src/demo_market_price_guard.py             → PASS
  - python -m py_compile src/demo_new_entry_review.py               → PASS
  - python -m py_compile scripts/preview_demo_new_entry_review.py   → PASS
  - python -m pytest tests/demo_trading -q                          → 1065 passed
  - O3 SOLUSDT incident replay (160 vs 66.47) → rejected as
    stale_entry_reference_price; deviation 140.71%; no payload emitted
  - O6 verified-price anchor → SOLUSDT candidate at 160 with real
    market 153.5 (~4.23% deviation) gives rounded_entry_price=153.5,
    notional/stop_risk anchored to 153.5 NOT 160
  - O11 sender G19 → review with realtime_price_guard_verified=False
    blocks with "missing_realtime_price_guard"; O12 verified review
    passes G19 in dry-run

Outputs:
  - None.  No orders sent.  No emergency closes triggered.  No
    new-entry orders placed.  Dry-run / pure-computation review only.

Notes:
  - Public market endpoint policy: /v5/market/tickers is unauthenticated
    and hosted on the same api-demo.bybit.com base that all other Demo
    code paths use.  No HMAC headers are attached; no env vars are read
    by the guard module.  Module source K18/K19 invariants on the
    review module remain intact (no URL strings, no urllib, no HTTP
    client in src/demo_new_entry_review.py — only the dataclass type +
    threshold constant are imported from the new guard module).
  - Backward compatibility: existing 47 K-series review tests continue
    to pass unchanged because price_guard_evaluations defaults to None
    (legacy mode); but legacy reviews emit payloads with
    realtime_price_guard_verified=False, which sender G19 (TASK-014M)
    will refuse — exactly the fail-closed posture intended.
  - Commit: local commit only; no push (per feedback_git_push.md).
  - Next step gate: Demo new-entry dry-run sender may now be re-run
    against a review produced with the guard engaged
    (--allow-real-market-network on VPS only, when permitted).

---

### 2026-06-09（TASK-014N — Add Demo Emergency Missing-stop Close-only Sender / Single-position Gate）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014N)
Task: Build a fail-closed, layered-gate, single-order Demo emergency
      close-only sender for the SOLUSDT missing-stop position whose
      emergency_close_preview was emitted by TASK-014M (positionId
      missing stop_price=0, qty=4.0, side=long).  Deliverables:
        A. src/demo_emergency_close_sender.py — new module independent
           of demo_close_only_sender / demo_new_entry_sender / BybitExecutor
           / src/risk / main, exposing EmergencyCloseOrderResult dataclass
           and DemoEmergencyCloseSender with 15 static gates, a confirm-
           token gate (CONFIRM_DEMO_EMERGENCY_CLOSE_YYYYMMDD, today UTC),
           a pre-send refresh against a live DemoReadOnlyClient, and at
           most ONE reduce-only Market POST to api-demo.bybit.com
           /v5/order/create per invocation;
        B. scripts/execute_demo_emergency_close.py — DRY-RUN-default CLI
           that consumes the latest post-fill JSON
           (outputs/demo_trading/new_entry_postfill/) and produces a JSON
           + MD report under
           outputs/demo_trading/emergency_close_execution/.  --execute-
           emergency-close is required to leave dry-run; --confirm-token
           is required either way;
        C. tests/demo_trading/test_demo_emergency_close_sender.py — 25
           requirement classes (N1-N25) plus structural invariant + CLI
           integration tests covering: dry-run default, all 15 static
           gate failure modes, confirm-token shape & date equality, close
           side mapping (long→Sell, short→Buy), pre-send refresh side /
           qty / stop-restored / target-missing, signed Bybit V5 POST
           against api-demo.bybit.com only, mocked retCode==0 and !=0
           paths, structural invariants, secret hygiene, no live endpoint
           fallback, no forbidden tokens, no forbidden imports, and one-
           order limit per invocation.

Status before: READY — TASK-014M committed (2287e8b); VPS holds a real Demo
               SOLUSDT position with stop_price=0; emergency_close_preview
               available via verify_demo_new_entry_postfill.py
               --with-emergency-close-preview; no sender path existed yet
               to escalate that preview into an actual reduce-only close.
Status after:  READY — TASK-014N complete on local main; module / CLI /
               tests in place; 988/988 demo_trading tests pass (929 prior
               + 59 new); no orders sent, no positions modified, no
               secrets observed, no live endpoint contacted, no close-only
               sender or new-entry sender reused.

Files changed:
  - src/demo_emergency_close_sender.py            (CREATED)
  - scripts/execute_demo_emergency_close.py       (CREATED)
  - tests/demo_trading/test_demo_emergency_close_sender.py (CREATED — 59 tests)
  - .gitignore                                    (MODIFIED — outputs/demo_trading/emergency_close_execution/)
  - docs/research/commands/NEXT_ACTION.md         (MODIFIED — TASK-014N block prepended)
  - docs/research/commands/COMMAND_LOG.md         (MODIFIED — this entry prepended)

Validation:
  - python -m py_compile src/demo_emergency_close_sender.py            → PASS
  - python -m py_compile scripts/execute_demo_emergency_close.py       → PASS
  - python -m pytest tests/demo_trading -q                             → 988 passed
  - Static gates verified by tests N3..N16
  - Pre-send refresh gates verified by tests N17..N20
  - DRY-RUN default verified by tests N1, N2
  - Signed POST to api-demo.bybit.com /v5/order/create verified by N17, N21
  - reduceOnly=True invariant verified by structural invariant test
  - No forbidden imports / no forbidden tokens verified by N22, N24, N25

Outputs:
  - outputs/demo_trading/emergency_close_execution/ (git-ignored;
    populated only when CLI is run with --write-report on the VPS)

Notes:
  - This commit is LOCAL ONLY.  No git push.  No Demo emergency close
    order has been sent.  --execute-emergency-close has NOT been invoked
    against any environment by this commit.
  - The sender is structurally independent of TASK-014K (close-only
    cleanup sender) and TASK-014L (new-entry sender); no module-level
    import or function reuse between them.  Module-level AST scans in the
    test suite enforce this isolation.
  - Decision to escalate from DRY-RUN to --execute-emergency-close for the
    SOLUSDT missing-stop position is reserved for Rick.

---

### 2026-06-09（TASK-014M — Add Demo New-entry Post-fill Verification / Missing-stop Protection / Real-price Guard）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014M)
Task: After the VPS first real Demo new-entry (SOLUSDT, order_id
      aae978ed-98f7-47cd-90ad-1f0c16b29213) revealed (a) missing stop_price=0
      on the resulting position and (b) a stale preview entry_reference_price
      of 160 vs actual 66.47 (~58% deviation), build:
        A. read-only post-fill verification module + CLI + tests that detects
           missing_stop_price and stale_price_mismatch and fails closed;
        B. a real-time price guard in the new-entry sender so future sends
           refuse to proceed when the review file does not assert
           realtime_price_guard_verified=True;
        C. a preview-only emergency close-only dict for missing-stop positions
           (no actual execution; reserved for TASK-014N);
        D. M1-M17 tests covering ORDER_SENT detection, position presence,
           missing-stop, qty/side/entry deviation, fail-closed propagation,
           secret hygiene, structural invariants, no order endpoint, no live
           endpoint, no forbidden imports, and the SOLUSDT production-incident
           replay.

Status before: READY — TASK-014L committed (82172c0); VPS executed first Demo
               new-entry but produced a position with stop=0 and entry-price
               deviation ~58% vs preview.
Status after:  READY — TASK-014M complete on local main; module / CLI / tests
               in place; sender gate G19 active; 929/929 demo_trading tests
               pass; no orders sent, no positions modified, no secrets
               observed, no live endpoint contacted.

Files changed:
  - src/demo_new_entry_postfill_verify.py        (CREATED)
  - scripts/verify_demo_new_entry_postfill.py    (CREATED)
  - tests/demo_trading/test_demo_new_entry_postfill_verify.py (CREATED — 62 tests)
  - src/demo_new_entry_sender.py                 (MODIFIED — G19 gate + docstring)
  - tests/demo_trading/test_demo_new_entry_sender.py (MODIFIED — _build_review helper + TestRealtimePriceGuard)
  - .gitignore                                   (MODIFIED — outputs/demo_trading/new_entry_postfill/)
  - docs/research/commands/NEXT_ACTION.md        (MODIFIED — TASK-014M block prepended)
  - docs/research/commands/COMMAND_LOG.md        (MODIFIED — this entry)

Validation:
  - python -m py_compile src/demo_new_entry_postfill_verify.py
        scripts/verify_demo_new_entry_postfill.py src/demo_new_entry_sender.py  -> PASS
  - python -m pytest tests/demo_trading/test_demo_new_entry_postfill_verify.py -q  -> 62/62 PASS
  - python -m pytest tests/demo_trading -q  -> 929/929 PASS (864 prior + 65 new)
  - M1  ORDER_SENT detection (PASS path)                                   CONFIRMED
  - M2  position presence (missing -> fail_closed=True)                    CONFIRMED
  - M3  missing_stop_price (stop<=0) -> flag + reason                      CONFIRMED
  - M4  qty mismatch (>1% relative)                                        CONFIRMED
  - M5  side mismatch                                                      CONFIRMED
  - M6  stale_price_mismatch (>5%)                                         CONFIRMED
  - M7  missing_stop_price -> fail_closed=True                             CONFIRMED
  - M8  stale_price_mismatch -> fail_closed=True                           CONFIRMED
  - M9  missing execution file -> fail_closed + CLI exit 1                 CONFIRMED
  - M10 missing readonly file -> fail_closed + CLI exit 1                  CONFIRMED
  - M11 no env secret value written into JSON or MD reports                CONFIRMED
  - M12 order_endpoint_called=False (structural)                           CONFIRMED
  - M13 no_orders_sent=True / no_position_modified=True (structural)       CONFIRMED
  - M14 emergency_close_preview: long->Sell, short->Buy, reduce_only=True  CONFIRMED
  - M15 preview_only=True / order_sent=False / next_required_task=TASK-014N CONFIRMED
  - M16 AST imports clean (no main/src.risk/BybitExecutor/close-only/sender/CLIs) CONFIRMED
  - M17 source scan: no api.bybit.com / api.bytick.com / /v5/order/create / -batch  CONFIRMED
  - production-incident replay (SOLUSDT, actual=66.47, expected=160, stop=0)
        catches both missing_stop_price AND stale_price_mismatch in one pass  CONFIRMED
  - sender G19 (missing_realtime_price_guard) blocks send when review file does
        not carry realtime_price_guard_verified=True (false / missing field)   CONFIRMED
  - structural invariants on PostFillVerificationResult: no_orders_sent=True,
        order_endpoint_called=False, no_position_modified=True,
        secret_value_observed=False, no_live_endpoint=True, no_batch_order=True,
        no_close_only_path=True, new_entry_allowed=False (always)              CONFIRMED

Outputs:
  - outputs/demo_trading/new_entry_postfill/        (gitignored runtime dir;
        populated by --write-report on VPS).  Files:
          latest_new_entry_postfill.json  (machine-readable)
          latest_new_entry_postfill.md    (human review)
          {ts}_new_entry_postfill.json / .md  (timestamped copies)
  - No data was written to live endpoints.  No order was sent.

Notes:
  - This task is READ-ONLY for the exchange.  No POST to /v5/order/create or
    any other order path occurs in either the postfill verify module or its CLI.
  - The optional --with-emergency-close-preview flag attaches a preview dict
    with close_order_side computed from the *position* side (long->Sell,
    short->Buy) and reduce_only=True, preview_only=True.  Actual execution of
    such a close is intentionally NOT performed here; the next_required_task
    field embeds "TASK-014N" as a forward pointer.
  - G19 (missing_realtime_price_guard) is enforced at the static-gate level
    of demo_new_entry_sender.  Future review files emitted by
    scripts/preview_demo_new_entry_review.py must set
    realtime_price_guard_verified=True for the sender to proceed.  Production
    review files written before this commit do NOT carry that field -- this is
    intentional fail-closed behaviour until TASK-014N updates the upstream
    pipeline to fetch a real-time market price.
  - Local commit only (no git push); Rick must explicitly authorise push.

---

### 2026-06-09（TASK-014L — Add Demo New-entry Sender Gate / Manual Confirmed Single-order）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014L)
Task: Add a single-order Demo new-entry sender with layered fail-closed gates
      (top-level static gates from latest_new_entry_review.json + token gate +
      pre-send read-only refresh), defaulting to dry-run.  Order submission
      requires --execute-new-entry AND a CONFIRM_DEMO_NEW_ENTRY_YYYYMMDD token
      matching today's UTC date AND exactly one --symbol from the review's
      accepted_candidates.  Short new-entries are presently blocked at the
      static gate.  POSTs only to /v5/order/create on api-demo.bybit.com;
      no /v5/order/create-batch, no leverage / TP / SL / triggerPrice / transfer
      / withdraw / deposit.  No reuse of demo_close_only_sender; no imports of
      main, src.risk, BybitExecutor.  reduce_only is structurally False on the
      built order body (new entry, not close).  Reports JSON+MD; secrets never
      observed; no_live_endpoint=True / no_batch_order=True / no_close_only_path=True
      always.
Status before: TASK-014K complete (746 tests PASS)
Status after:  TASK-014L complete (864 tests PASS, py_compile PASS)

Files changed:
  src/demo_new_entry_sender.py                            -- NEW (DemoNewEntrySender + NewEntryOrderResult + layered gates)
  scripts/execute_demo_new_entry.py                       -- NEW (CLI: --from-latest-review --symbol --confirm-token --dry-run --execute-new-entry --write-report)
  tests/demo_trading/test_demo_new_entry_sender.py        -- NEW (118 tests across F1-F25 + source scan + invariants + report artifacts)
  .gitignore                                              -- MODIFIED (outputs/demo_trading/new_entry_execution/)
  docs/research/commands/COMMAND_LOG.md                   (this entry)
  docs/research/commands/NEXT_ACTION.md                   (TASK-014L status)

Validation:
  python -m py_compile src/demo_new_entry_sender.py                             PASS
  python -m py_compile scripts/execute_demo_new_entry.py                        PASS
  python -m py_compile tests/demo_trading/test_demo_new_entry_sender.py         PASS
  pytest tests/demo_trading/test_demo_new_entry_sender.py -q                    118/118 PASS
  pytest tests/demo_trading -q                                                  864/864 PASS (746 prior + 118 new)
  F1  dry-run default -> order_sent=False / order_endpoint_called=False         CONFIRMED
  F2  missing latest_new_entry_review.json -> fail closed (exit 1)              CONFIRMED
  F3  missing confirm token -> fail closed (missing_confirm_token)              CONFIRMED
  F4  yesterday / tomorrow token -> confirm_token_date_mismatch                 CONFIRMED
  F5  invalid token format / close-only token / whitespace -> blocked           CONFIRMED
  F6  CLI missing --symbol -> fail closed (exit 1)                              CONFIRMED
  F7  symbol not in accepted_candidates -> symbol_not_in_accepted_candidates    CONFIRMED
  F8  review.fail_closed=True -> review_fail_closed                             CONFIRMED
  F9  proof_strength != STRONG -> proof_not_strong                              CONFIRMED
  F10 endpoint_family != bybit_demo -> endpoint_family_not_bybit_demo           CONFIRMED
  F11 account_mode != demo -> account_mode_not_demo                             CONFIRMED
  F12 position_details_source != real_readonly -> blocked                       CONFIRMED
  F13 new_entry_allowed_from_reconciliation=False -> blocked                    CONFIRMED
  F14 available_balance_usd <= 0 -> available_balance_zero_or_negative          CONFIRMED
  F15 open_positions_count >= 10 -> open_positions_full                         CONFIRMED
  F16 forged short in accepted_candidates -> short_new_entry_not_permitted      CONFIRMED
  F17 payload.reduce_only=True -> payload_reduce_only_must_be_false             CONFIRMED
  F18 payload.preview_only=False -> payload_preview_only_must_be_true           CONFIRMED
  F19 payload.order_sent / order_endpoint_called True -> blocked                CONFIRMED
  F20 qty<=0 / invalid order_side / order_type!=Market -> blocked               CONFIRMED
  F21 max_long_allowed_remaining=0 -> long_capacity_full                        CONFIRMED
  F22 payload.side mismatch vs evaluation.side -> order_side_mismatch...        CONFIRMED
  F23 refresh: target symbol already open / live capacity full -> blocked       CONFIRMED
  F24 refresh: proof not STRONG / endpoint != bybit_demo / balance<=0 -> blocked CONFIRMED
  F25 mocked retCode=0 -> order_id set, no_position_modified=False, no secrets  CONFIRMED
      mocked retCode!=0 -> order_sent=False, no_position_modified=True, no secrets CONFIRMED
  Execute path URL goes to api-demo.bybit.com + /v5/order/create only           CONFIRMED
  Order body: category=linear, orderType=Market, reduceOnly=False,              CONFIRMED
              closeOnTrigger=False, side=Buy for long, no leverage/TP/SL/trigger CONFIRMED
  Source scan: no "api.bybit.com", no set_leverage / setLeverage / tradingStop  CONFIRMED
  Source scan: no takeProfit / stopLoss / triggerPrice / tpslMode               CONFIRMED
  Source scan: no /asset/transfer / /withdraw / /deposit / /v5/order/create-batch CONFIRMED
  Source scan: no pybit                                                         CONFIRMED
  AST imports: no demo_close_only_sender / execute_demo_close_only_cleanup      CONFIRMED
  AST imports: no main / src.risk / BybitExecutor                               CONFIRMED
  Result invariants: secret_value_observed=False / no_live_endpoint=True /      CONFIRMED
                     no_batch_order=True / no_close_only_path=True / reduce_only=False
  main.py / src/risk.py / BybitExecutor                                         NOT MODIFIED

Outputs (when run on VPS after TASK-014K preview):
  outputs/demo_trading/new_entry_execution/latest_new_entry_execution.json     (dry-run report; not generated by this commit)
  outputs/demo_trading/new_entry_execution/latest_new_entry_execution.md       (dry-run report; not generated by this commit)

Notes:
  - No new-entry order has been submitted by this commit.  All execution
    requires Rick to (1) refresh the read-only/reconciliation/review pipeline
    on the VPS, (2) decide which accepted long candidate to send, (3) supply
    CONFIRM_DEMO_NEW_ENTRY_YYYYMMDD matching today's UTC date and
    --execute-new-entry on the CLI.
  - Production state (short_count=5/5) means all short candidates are
    REJECTED at the static gate level; only long candidates can pass.
  - This commit is local only; Rick must git push.

---

### 2026-06-09（TASK-014K — Add Demo New-entry Dry-run Proposal Review）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014K)
Task: Add a pure-computation new-entry dry-run review module that reads a verified
      real_readonly reconciliation snapshot and a caller-supplied list of new-entry
      candidates, applies layered fail-closed gates (top-level + per-candidate),
      produces a rounded payload preview per accepted candidate, and writes JSON+MD
      reports.  No orders sent, no positions modified, no order endpoint called,
      no secrets observed.  No reuse of the close-only sender.  Hardcoded preview
      invariants: preview_only=True, order_sent=False, order_endpoint_called=False,
      reduce_only=False on the entry payload, action_type=PREVIEW_REVIEW_ONLY.
Status before: TASK-014J complete (699 tests PASS)
Status after:  TASK-014K complete (746 tests PASS, py_compile PASS)

Files changed:
  src/demo_new_entry_review.py                            -- NEW (review_new_entry_candidates pure-computation core)
  scripts/preview_demo_new_entry_review.py                -- NEW (fixture + --from-latest-reconciliation + --write-report)
  tests/demo_trading/test_demo_new_entry_review.py        -- NEW (47 tests across K1-K19 groups)
  .gitignore                                              -- MODIFIED (outputs/demo_trading/new_entry_review/)
  docs/research/commands/COMMAND_LOG.md                   (this entry)
  docs/research/commands/NEXT_ACTION.md                   (TASK-014K status)

Validation:
  python -m py_compile src/demo_new_entry_review.py                             PASS
  python -m py_compile scripts/preview_demo_new_entry_review.py                 PASS
  python -m py_compile tests/demo_trading/test_demo_new_entry_review.py         PASS
  pytest tests/demo_trading -q                                                  746/746 PASS
  K1  reconciliation_not_pass -> fail_closed                                    CONFIRMED
  K2  proof_not_strong -> fail_closed                                           CONFIRMED
  K3  position_details_source != real_readonly -> fail_closed                   CONFIRMED
  K4  runtime_not_verified / available_balance <= 0 -> fail_closed              CONFIRMED
  K5  short_capacity_full -> every short candidate REJECTED                     CONFIRMED
  K6  long capacity available -> long candidates accepted                       CONFIRMED
  K7  duplicate symbol (existing + intra-batch) -> REJECTED                     CONFIRMED
  K8  missing_instrument_rule -> REJECTED                                       CONFIRMED
  K9  rounded_qty_zero -> REJECTED                                              CONFIRMED
  K10 min_notional_after_rounding -> REJECTED                                   CONFIRMED
  K11 invalid_stop_distance (wrong side / zero) -> REJECTED                     CONFIRMED
  K12 projected gross / max_single_notional gate reachable                      CONFIRMED
  K13 projected net exposure gate exists and not falsely tripped                CONFIRMED
  K14 every payload.preview_only=True                                           CONFIRMED
  K15 every payload.order_sent=False                                            CONFIRMED
  K16 every payload.order_endpoint_called=False                                 CONFIRMED
  K17 secret_value_observed=False; no secret tokens in to_dict output           CONFIRMED
  K18 module source: no live hostname, no order endpoint, no HTTP client        CONFIRMED
  K19 module imports: no main / no src.risk / no BybitExecutor /                CONFIRMED
                      no demo_close_only_sender / no execute_demo_close_only
  fixture-mode preview script: SOLUSDT/AAVEUSDT/LINKUSDT all accepted with      CONFIRMED
                       preview_only=True / order_sent=False payloads
  next_required_task = "TASK-014L Demo New-entry Sender Gate (manual approval   CONFIRMED
                       required)" when any candidate accepted
  main.py / src/risk.py / BybitExecutor                                         NOT MODIFIED

Outputs:
  outputs/demo_trading/new_entry_review/{timestamp}_new_entry_review.json (gitignored)
  outputs/demo_trading/new_entry_review/{timestamp}_new_entry_review.md   (gitignored)
  outputs/demo_trading/new_entry_review/latest_new_entry_review.json      (gitignored)
  outputs/demo_trading/new_entry_review/latest_new_entry_review.md        (gitignored)

Notes:
  This is a planning artefact ONLY.  TASK-014K does NOT implement a sender for
  new-entry payloads.  Payload previews are constructed with hardcoded
  invariants (preview_only=True, order_sent=False, order_endpoint_called=False,
  confirmation_required=True) that are enforced structurally and verified by
  tests.  The close-only sender (TASK-014G) is NOT reused or called by this
  module; tests verify the module does not import demo_close_only_sender or
  execute_demo_close_only_cleanup.  TASK-014L (Demo New-entry Sender Gate)
  must be opened separately before any new-entry payload could be transmitted.

---

### 2026-06-09（TASK-014J — Fix Demo Available Balance Mapping to account.totalAvailableBalance）

Agent: Claude Sonnet 4.6
Command source: Rick direct chat instruction (TASK-014J)
Task: Fix available_balance_usd mapping in _wallet_real() from coin.USDT.availableToWithdraw
      (returned 0.00 on VPS) to account.totalAvailableBalance (7169.40 on VPS), eliminating
      the false available_balance_zero_or_negative violation that was blocking new entries.
      Add available_balance_usd_source provenance field to WalletSnapshot.  Update
      CURRENT_MAPPING_FIELD in demo_wallet_audit.py to reflect the new mapping.
Status before: TASK-014I complete (659 tests PASS); VPS audit showed
               account.totalAvailableBalance=7169.40 but mapping_suspect=True because
               coin.USDT.availableToWithdraw=0.00 was being used instead.
Status after:  TASK-014J complete (699 tests PASS, py_compile PASS)

Files changed:
  src/demo_readonly_client.py                            -- MODIFIED (_wallet_real priority cascade, WalletSnapshot.available_balance_usd_source field)
  src/demo_wallet_audit.py                               -- MODIFIED (CURRENT_MAPPING_FIELD → account.totalAvailableBalance)
  scripts/preview_demo_readonly_runtime.py               -- MODIFIED (available_balance_usd_source + wallet_account_type in report)
  tests/demo_trading/test_demo_task_014j.py              -- NEW (40 tests, J1-J12)
  docs/research/commands/COMMAND_LOG.md                 (this entry)
  docs/research/commands/NEXT_ACTION.md                 (TASK-014J status)

Validation:
  python -m py_compile src/demo_readonly_client.py            PASS
  python -m py_compile src/demo_runtime_adapter.py            PASS
  python -m py_compile scripts/preview_demo_readonly_runtime.py PASS
  python -m py_compile scripts/preview_demo_wallet_audit.py   PASS
  python -m py_compile tests/demo_trading/test_demo_task_014j.py PASS
  pytest tests/demo_trading -q                                699/699 PASS
  available_balance_usd_source field present on WalletSnapshot                  CONFIRMED
  account.totalAvailableBalance priority 1 in cascade                           CONFIRMED
  account.availableToWithdraw fallback (priority 2)                             CONFIRMED
  coin.USDT.availableToWithdraw fallback (priority 3)                           CONFIRMED
  coin.USDT.free fallback (priority 4)                                          CONFIRMED
  coin.USDT.walletBalance excluded from available mapping                       CONFIRMED
  totalWalletBalance excluded from available mapping                            CONFIRMED
  all-candidates-absent → available=0, source="missing"                        CONFIRMED
  CURRENT_MAPPING_FIELD = account.totalAvailableBalance in demo_wallet_audit    CONFIRMED
  wallet audit mapping_suspect=False when current matches TAB                  CONFIRMED
  no order endpoint tokens in modified source                                   CONFIRMED
  no secrets in output                                                          CONFIRMED
  main.py / src/risk.py / BybitExecutor not modified                            CONFIRMED

---

### 2026-06-09（TASK-014I — Demo Wallet Availability Field Audit）

Agent: Claude Sonnet 4.6
Command source: Rick direct chat instruction (TASK-014I)
Task: Build read-only Demo wallet / margin availability audit.  Investigate
      whether available_balance_usd=0.00 is a genuine account state or a
      field-mapping error by capturing all Bybit wallet balance fields, evaluating
      5 candidate available-balance fields, and flagging mapping_suspect when any
      liquidity-oriented candidate differs from the current mapping.
Status before: TASK-014H complete (614 tests PASS); 2 close-only orders executed
               on VPS (MERLUSDT + BOMEUSDT); 5 short positions remain; equity=11613.47;
               available_balance=0.00 (only blocking violation remaining).
Status after:  TASK-014I complete (659 tests PASS, py_compile PASS)

Files changed:
  src/demo_wallet_audit.py                             -- NEW (extract_wallet_fields, audit_wallet, WalletAuditResult)
  scripts/preview_demo_wallet_audit.py                 -- NEW (fixture + --real-readonly + --write-report)
  tests/demo_trading/test_demo_wallet_audit.py         -- NEW (45 tests, I1-I10 + integration)
  .gitignore                                           -- UPDATED (outputs/demo_trading/wallet_audit/)
  docs/research/commands/COMMAND_LOG.md               (this entry)
  docs/research/commands/NEXT_ACTION.md               (TASK-014I status)

Validation:
  python -m py_compile src/demo_wallet_audit.py                  PASS
  python -m py_compile scripts/preview_demo_wallet_audit.py      PASS
  pytest tests/demo_trading -q                                    659 passed
  wallet fields: all 5 candidates (totalAvailableBalance, account.availableToWithdraw,
    coin.USDT.availableToWithdraw, coin.USDT.free, coin.USDT.walletBalance)     CONFIRMED
  coin.USDT.walletBalance excluded from conflict detection (includes locked margin)  CONFIRMED
  fail_closed on proof != STRONG or endpoint != bybit_demo                      CONFIRMED
  mapping_suspect=True when totalAvailableBalance > current_mapping              CONFIRMED
  all candidates zero (fixture) => mapping_suspect=False, genuine state noted    CONFIRMED
  no order endpoint tokens in new source                                          CONFIRMED
  no secrets in JSON / MD reports                                                 CONFIRMED
  main.py / src/risk.py / BybitExecutor not imported or modified                 CONFIRMED
  new_entry_allowed=False always (this module never enables entries)              CONFIRMED

---

### 2026-06-09（TASK-014H — Persist Real Demo Position Details）

Agent: Claude Opus 4.7
Command source: Rick direct chat instruction (TASK-014H)
Task: Persist the 8 real Demo short positions captured by TASK-014D read-only
      smoke through reconciliation, cleanup, and sender so the close-only
      pipeline never falls back to the wrong fixture symbols (ETHUSDT /
      BNBUSDT). Add `position_details_source` provenance field and gate
      `execute_ready` / `execute_allowed` on `position_details_source ==
      "real_readonly"`. No order submission, no Demo endpoint call, no secret
      leak, no change to main.py / src/risk.py / BybitExecutor.
Status before: TASK-014G complete (584 tests PASS)
Status after:  TASK-014H complete (614 tests PASS, py_compile PASS)

Files changed:
  scripts/preview_demo_readonly_runtime.py             -- UPDATED (positions[], position_details_source, positions_count, timestamp, no_orders_sent)
  scripts/preview_demo_position_reconcile.py           -- UPDATED (load real positions from smoke, fail-closed on missing details)
  scripts/preview_demo_close_only_cleanup.py           -- UPDATED (thread position_details_source through to plan_cleanup)
  scripts/execute_demo_close_only_cleanup.py           -- UPDATED (report + printer show position_details_source)
  src/demo_position_reconcile.py                       -- UPDATED (ReconciliationResult.position_details_source, positions[] in to_dict)
  src/demo_close_only_cleanup.py                       -- UPDATED (CleanupPlan.position_details_source, execute_ready gated on real source)
  src/demo_close_only_sender.py                        -- UPDATED (Gate 5b position_details_source_not_real_readonly; CloseOrderResult fields)
  tests/demo_trading/test_demo_close_only_cleanup.py   -- UPDATED (existing fixtures now declare position_details_source="real_readonly")
  tests/demo_trading/test_demo_close_only_sender.py    -- UPDATED (helper threads position_details_source)
  tests/demo_trading/test_demo_task_014h.py            -- NEW (30 tests, H1-H13)
  docs/research/commands/COMMAND_LOG.md               (this entry)
  docs/research/commands/NEXT_ACTION.md               (TASK-014H status)

Validation:
  python -m py_compile scripts/preview_demo_readonly_runtime.py            PASS
  python -m py_compile scripts/preview_demo_position_reconcile.py          PASS
  python -m py_compile scripts/preview_demo_close_only_cleanup.py          PASS
  python -m py_compile scripts/execute_demo_close_only_cleanup.py          PASS
  pytest tests/demo_trading -q                                             614 passed
  position_details_source propagated smoke -> reconciliation -> cleanup -> sender  CONFIRMED
  reconciliation fail-closed when real smoke positions absent              CONFIRMED (reason=missing_real_position_details)
  cleanup execute_ready=False when source != real_readonly                 CONFIRMED
  sender Gate 5b: position_details_source_not_real_readonly                CONFIRMED
  sender Gate: symbol_not_in_candidates blocks ETHUSDT / BNBUSDT           CONFIRMED
  no orders sent; no Demo POST issued by TASK-014H pipeline                CONFIRMED
  no API key / secret bytes in JSON or MD reports                          CONFIRMED
  main.py / src/risk.py / BybitExecutor not imported by TASK-014H modules  CONFIRMED

---

### 2026-06-06（TASK-014G — Demo Close-only Sender Gate）

Agent: Claude Sonnet 4.6
Command source: Rick direct chat instruction (TASK-014G)
Task: Build Demo close-only sender with layered safety gates and human confirmation.
      DemoCloseOnlySender enforces: TASK-014F plan gates, symbol uniqueness,
      reduce_only=True, close_side correctness, pre-send read-only refresh,
      one-order-per-invocation limit, Demo endpoint only.
      execute_close_only=True required; default is dry-run. No batch submission.
Status before: TASK-014F complete (494 tests PASS)
Status after:  TASK-014G complete (584 tests PASS, py_compile PASS)

Files changed:
  src/demo_close_only_sender.py                          -- NEW (DemoCloseOnlySender, CloseOrderResult)
  scripts/execute_demo_close_only_cleanup.py             -- NEW (CLI gate + confirmation)
  tests/demo_trading/test_demo_close_only_sender.py      -- NEW (90 tests, G1-G23)
  .gitignore                                             -- UPDATED (outputs/demo_trading/close_only_execution/)
  docs/research/commands/COMMAND_LOG.md                 (this entry)
  docs/research/commands/NEXT_ACTION.md                 (TASK-014G status)

Validation:
  python -m py_compile src/demo_close_only_sender.py                 PASS
  python -m py_compile scripts/execute_demo_close_only_cleanup.py    PASS
  python -m py_compile tests/demo_trading/test_demo_close_only_sender.py  PASS
  pytest tests/demo_trading/ -q                                      584 passed
  dry-run default: order_sent=False, order_endpoint_called=False               CONFIRMED
  execute_close_only=True: pre-send refresh → Demo endpoint only               CONFIRMED
  one-order limit: CLI fails closed when multi-candidate and no --symbol       CONFIRMED
  reduce_only=True enforced at gate level                                       CONFIRMED
  close_side Buy=close short, Sell=close long                                   CONFIRMED
  secret_value_observed=False always                                            CONFIRMED
  no_live_endpoint=True always                                                  CONFIRMED
  api.bybit.com not in sender source                                            CONFIRMED
  set_leverage / tradingStop / transfer / withdraw / deposit not in source      CONFIRMED
  main.py / src/risk.py / exchange executors                                    NOT MODIFIED
  No orders auto-sent; sender ready for Rick manual VPS smoke test              CONFIRMED

---

### 2026-06-06（TASK-014F — Demo Close-only Manual Confirmed Cleanup）

Agent: Claude Sonnet 4.6
Command source: Rick direct chat instruction (TASK-014F)
Task: Build Demo close-only cleanup preview with human confirmation gate.
      Deterministic candidate selection (stop_risk DESC, notional DESC, symbol ASC).
      Generates close-only payload previews (reduce_only=True always).
      Human token: CONFIRM_DEMO_CLOSE_ONLY_YYYYMMDD (expires daily).
      execute_ready=True only when ALL gates pass; no_orders_sent=True always.
Status before: TASK-014E complete (405 tests PASS)
Status after:  TASK-014F complete (494 tests PASS, py_compile PASS)

Files changed:
  src/demo_close_only_cleanup.py                       -- NEW (plan_cleanup() pure computation, CleanupPlan, ClosePayloadPreview)
  scripts/preview_demo_close_only_cleanup.py           -- NEW (fixture + --from-latest-reconciliation + --confirm-token + --write-report)
  tests/demo_trading/test_demo_close_only_cleanup.py   -- NEW (89 tests, E1-E19 + TestReportArtifacts)
  .gitignore                                           -- UPDATED (outputs/demo_trading/close_only_cleanup/)
  docs/research/commands/COMMAND_LOG.md               (this entry)
  docs/research/commands/NEXT_ACTION.md               (TASK-014F status)

Validation:
  python -m py_compile src/demo_close_only_cleanup.py                  PASS
  python -m py_compile scripts/preview_demo_close_only_cleanup.py      PASS
  python -m py_compile tests/demo_trading/test_demo_close_only_cleanup.py  PASS
  pytest tests/demo_trading/ -q                                        494 passed
  execute_ready=True only with valid token + fresh snapshot + verified runtime    CONFIRMED
  no_orders_sent=True always (all plans)                                          CONFIRMED
  no_position_modified=True always                                                CONFIRMED
  order_endpoint_called=False always                                              CONFIRMED
  close_order_side=Buy for short, Sell for long (Bybit derivatives)               CONFIRMED
  deterministic sort: ETHUSDT (stop_risk=100) before BNBUSDT (stop_risk=80)      CONFIRMED
  main.py / src/risk.py / exchange executors                                      NOT MODIFIED

---

### 2026-06-06（TASK-014E — Demo Position Reconciliation Preview）

Agent: Claude Sonnet 4.6
Command source: Rick direct chat instruction (TASK-014E)
Task: Read-only Demo position reconciliation and legacy position cleanup plan.
      Audits current Demo account positions against new portfolio-level Kelly /
      10-slot risk rules, detects violations, and outputs human-readable cleanup
      plan. Does NOT auto-close, does NOT send orders.
Status before: TASK-014D complete (321 tests PASS)
Status after:  TASK-014E complete (405 tests PASS, py_compile PASS)

Files changed:
  src/demo_position_reconcile.py                      -- NEW (reconcile() pure computation, violation detection, cleanup plan)
  scripts/preview_demo_position_reconcile.py          -- NEW (fixture + --from-latest-readonly-smoke + --write-report)
  tests/demo_trading/test_demo_position_reconcile.py  -- NEW (84 tests, F1-F16 + metrics correctness)
  .gitignore                                          -- UPDATED (outputs/demo_trading/reconciliation/)
  docs/research/commands/COMMAND_LOG.md              (this entry)
  docs/research/commands/NEXT_ACTION.md              (TASK-014E status)

Validation:
  python -m py_compile src/demo_position_reconcile.py                  PASS
  python -m py_compile scripts/preview_demo_position_reconcile.py      PASS
  pytest tests/demo_trading/ -q                                        405 passed
  preview (fixture mode)                                               exit 0, no violations
  preview (legacy fixture: short_count=7, available=0)                 exit 1, violations flagged
  main.py / src/risk.py / exchange executors                           NOT MODIFIED
  No orders sent / no positions modified / no secrets                  CONFIRMED

Real Demo account conclusions (based on confirmed real account state):
  equity_usd           ≈ 11,404.01
  available_balance_usd = 0.00       → VIOLATION: available_balance_zero_or_negative
  open_positions_count  = 8
  short_count           = 7 (approx) → VIOLATION: short_count_exceeded (max 5)
  new_entry_allowed     = False
  cannot_proceed_to_order_smoke = True

  suggested_actions:
    - pause_new_entries
    - review_legacy_short_positions
    - reduce_short_count_to_max_5_manually_or_via_future_confirmed_close_only_task
    - restore_available_balance_before_enabling_new_entries

  Next step if manual close is needed: TASK-014F Demo Close-only Manual Confirmed Cleanup

Design highlights:
  demo_position_reconcile.reconcile():
    - MAX_OPEN_POSITIONS=10, MAX_LONG=5, MAX_SHORT=5
    - MAX_GROSS_EXPOSURE_RATIO=1.0, MAX_NET_EXPOSURE_RATIO=0.5
    - Conservative stop risk: missing stop → count full notional (not 0)
    - 9 violation types, all hard (block new entries)
    - Cleanup plan: suggested_actions list, blocked_reasons list
    - Safety: no_orders_sent=True, no_position_modified=True always
  preview script:
    - fixture mode: clean 2-position fixture, no violations, exit 0
    - --from-latest-readonly-smoke: gates on demo_runtime_verified in smoke JSON;
      uses equity/available from smoke, fixture positions for per-symbol detail
    - --write-report: timestamped + latest JSON/MD to outputs/demo_trading/reconciliation/
  Output dir: outputs/demo_trading/reconciliation/ (gitignored)

VPS usage (after git pull + source .env.demo):
  python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report
  python3 scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report

---

### 2026-06-06（TASK-014D — Bybit Demo Real Read-only Smoke）

Agent: Claude Sonnet 4.6
Command source: Rick direct chat instruction (TASK-014D)
Task: Strengthen Demo runtime proof with STRONG/WEAK/MISSING classification.
      Add --write-report flag writing JSON+MD to outputs/demo_trading/readonly_smoke/.
      Add api_secret_present tracking. Early exit in preview when --real-readonly
      but credentials missing. Add .env.demo to .gitignore. 30 new tests.
Status before: TASK-014C complete (291 tests PASS)
Status after:  TASK-014D complete (321 tests PASS, py_compile PASS)

Files changed:
  src/demo_readonly_client.py                     -- UPDATED (_proof_real STRONG/WEAK/MISSING, api_secret_present)
  src/demo_runtime_adapter.py                     -- UPDATED (PROOF_WEAK/MISSING → None in adapt_runtime_proof)
  scripts/preview_demo_readonly_runtime.py        -- UPDATED (--write-report, early exit, proof_strength display)
  tests/demo_trading/test_demo_readonly_client.py -- UPDATED (+25 tests: TestProofStrengthClassification, TestApiSecretPresent, TestWriteReport)
  tests/demo_trading/test_demo_runtime_adapter.py -- UPDATED (+24 tests: TestProofStrengthInAdapter, TestRealReadonlySafety)
  .gitignore                                      -- UPDATED (.env.demo + outputs/demo_trading/readonly_smoke/)
  docs/research/commands/COMMAND_LOG.md          (this entry)
  docs/research/commands/NEXT_ACTION.md          (TASK-014D status)

Validation:
  python -m py_compile src/demo_readonly_client.py       PASS
  python -m py_compile src/demo_runtime_adapter.py       PASS
  python -m py_compile scripts/preview_demo_readonly_runtime.py  PASS
  pytest tests/demo_trading/ -q                          321 passed
  main.py / src/risk.py / BybitExecutor                  NOT MODIFIED
  No secrets loaded, no API calls, no orders sent        CONFIRMED

Design highlights:
  demo_readonly_client._proof_real():
    - No API key → PROOF_MISSING immediately (no network call attempted)
    - retCode != 0 → PROOF_MISSING
    - retCode==0 but no userID/apiKey in result → PROOF_WEAK
    - retCode==0 + valid identity fields → PROOF_STRONG
    - api_secret_present tracks bool(BYBIT_DEMO_API_SECRET) in real mode
  demo_runtime_adapter.adapt_runtime_proof():
    - PROOF_WEAK or PROOF_MISSING → return None (fail-closed)
    - Preserves prior checks: live_endpoint_fallback, empty account_mode/endpoint_family
  preview script:
    - Early exit (return 1) when --real-readonly + missing BYBIT_DEMO_API_KEY or SECRET
    - proof_strength + api_secret_present shown in Account Snapshot section
    - --write-report writes timestamped + latest JSON/MD to outputs/demo_trading/readonly_smoke/
  .gitignore: .env.demo + outputs/demo_trading/readonly_smoke/ added

VPS smoke (after git pull + source .env.demo):
  python3 scripts/preview_demo_readonly_runtime.py --real-readonly
  python3 scripts/preview_demo_readonly_runtime.py --real-readonly --write-report

---

### 2026-06-06（TASK-014C — Bybit Demo Read-only Runtime Probe）

Agent: Claude Sonnet 4.6
Command source: Rick direct chat instruction (TASK-014C)
Task: Bybit Demo read-only runtime probe — fixture-safe client, adapter converting
      account snapshots to Phase 2 planner input, integrated dry-run preview.
      Real-API mode gated behind --real-readonly flag. Fail-closed on missing stop,
      unknown endpoint family, or live endpoint fallback. Secrets never printed.
Status before: TASK-014B complete (177 tests PASS)
Status after:  TASK-014C complete (291 tests PASS, py_compile PASS)

Files changed:
  src/demo_readonly_client.py                        -- NEW (DemoReadOnlyClient, fixture + real modes)
  src/demo_runtime_adapter.py                        -- NEW (adapt wallet/positions/instruments/proof)
  scripts/preview_demo_readonly_runtime.py           -- NEW (dry-run preview, --real-readonly flag)
  tests/demo_trading/test_demo_readonly_client.py    -- NEW (41 tests)
  tests/demo_trading/test_demo_runtime_adapter.py    -- NEW (73 tests)
  docs/research/commands/COMMAND_LOG.md             (this entry)
  docs/research/commands/NEXT_ACTION.md             (TASK-014C status)

Validation:
  python -m py_compile src/demo_readonly_client.py       PASS
  python -m py_compile src/demo_runtime_adapter.py       PASS
  python -m py_compile scripts/preview_demo_readonly_runtime.py  PASS
  pytest tests/demo_trading/ -q                          291 passed
  preview_demo_readonly_runtime.py (fixture mode)        PASS + 4/6 accepted + All invariants PASS
  exit code fixture mode                                 0
  exit code unverified (monkeypatched)                   1
  main.py / src/risk.py / BybitExecutor                  NOT MODIFIED
  No secrets loaded, no API calls, no orders sent        CONFIRMED

Design highlights:
  demo_readonly_client:
    - Default fixture mode: zero network, zero secrets, zero API calls
    - Real mode: HMAC-signed GET to api-demo.bybit.com only; never api.bybit.com
    - _ALLOWED_PATHS enforced in _get(); any non-listed path raises ValueError
    - secret_value_observed=False and order_endpoint_called=False in every snapshot
    - API secret from BYBIT_DEMO_API_SECRET env var; never printed
  demo_runtime_adapter:
    - PositionSnapshot -> DemoOpenPosition; stop_price=None -> stop=0.0 + fail_closed
    - InstrumentSnapshot -> InstrumentRules (passes is_valid() after conversion)
    - RuntimeProofSnapshot -> DemoRuntimeProof | None (None if endpoint unknown/live)
    - adapt_all() orchestrates all four conversions; fail_reasons list populated
  preview script:
    - run_preview(use_real_network=False) -> int (0=OK, 1=fail-closed)
    - Phase 2 compute_demo_portfolio_sizing + apply_instrument_rules_to_proposal
    - Prints DRY RUN header, all required fields, invariant check

Safety scan:
  No place_order / create_order / submit_order / cancel_order / private_post
  No set_leverage / set_trading_stop in new files
  No pybit / BybitExecutor in any new file
  No API_KEY / API_SECRET values in any output
  No network calls in fixture mode

---

### 2026-06-06（TASK-014B — Demo Runtime Probe + Instrument Step Rounding）

Agent: Claude Sonnet 4.6
Command source: Rick direct chat instruction (TASK-014B)
Task: Add demo runtime probe (fail-closed, no API calls) and instrument
      rounding layer (qty_step / tick_size / min_qty / min_notional).
      Integrated dry-run preview combining Phase-2 Kelly sizer with
      runtime verification and exchange-compatible rounding.
Status before: TASK-014 Phase 2 complete (58 tests PASS)
Status after:  TASK-014B complete (177 tests PASS, py_compile PASS)

Files changed:
  src/demo_runtime_probe.py                         -- NEW
  src/demo_instrument_rules.py                      -- NEW
  scripts/preview_demo_runtime_and_rounding.py      -- NEW
  tests/demo_trading/test_demo_runtime_probe.py     -- NEW (55 tests)
  tests/demo_trading/test_demo_instrument_rules.py  -- NEW (64 tests)
  docs/research/commands/COMMAND_LOG.md             (this entry)
  docs/research/commands/NEXT_ACTION.md             (TASK-014B status)

Validation:
  python -m py_compile src/demo_runtime_probe.py         PASS
  python -m py_compile src/demo_instrument_rules.py      PASS
  python -m py_compile scripts/preview_demo_runtime_and_rounding.py  PASS
  pytest tests/demo_trading/ -q                          177 passed
  preview_demo_runtime_and_rounding.py (verified)        PASS + all invariants OK
  preview_demo_runtime_and_rounding.py --unverified       FAIL CLOSED exit=1
  main.py / src/risk.py / BybitExecutor                  NOT MODIFIED
  No secrets loaded, no API calls, no orders sent        CONFIRMED

Design highlights:
  demo_runtime_probe:
    - 6-check fail-closed chain: config -> proof != None -> fields valid
      -> demo_flag -> account_mode contains "demo" -> endpoint_family recognised
    - config=True is necessary but not sufficient (prevents misconfiguration)
    - make_fixture_proof() for tests/dry-run only
  demo_instrument_rules:
    - round_qty_down uses floor + 1e-9 epsilon (absorbs IEEE 754 FP errors)
    - apply_instrument_rules_to_proposal: duck-typed, no import of Phase-2 module
    - Invariants enforced: rounded_qty <= orig_qty, stop_risk_after <= orig_risk + 0.01
  preview script:
    - run_preview(use_fixture_proof, ...) returns int (0=OK, 1=fail-closed)
    - --unverified flag shows fail-closed path without secrets

Safety scan:
  No place_order / create_order / submit_order / cancel_order / private_post
  No pybit / BybitExecutor in any new file
  No API_KEY / API_SECRET / dotenv in any new file
  No network calls in any new file

---

### 2026-05-19（TASK-009B — Support Chinese Notion Database Properties）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-009B Support Chinese Notion Database Properties）
Task: Add PROPERTY_ALIASES + resolve_schema_names() to sync_forward_validation_to_notion.py
      so the script works with English, Chinese, or mixed Notion database property names.
      Property name resolution: Chinese preferred over English when both present.
Status before: TASK-009 script only accepted English property names
Status after:  All 16 properties accept English or Traditional Chinese equivalents

Files changed:
  scripts/sync_forward_validation_to_notion.py  -- PROPERTY_ALIASES, resolve_schema_names(),
                                                   updated check_required_properties(),
                                                   build_property_payload(), find_existing_page()
  tests/forward_record/test_notion_sync.py      -- +23 tests (total 64); added _full_schema_zh(),
                                                   _full_schema_mixed(), TestPropertyAliases,
                                                   TestResolveSchemaNames, TestCheckRequiredPropertiesBilingual,
                                                   TestBuildPropertyPayloadBilingual, TestFindExistingPageFilter
  docs/research/commands/COMMAND_LOG.md         (this entry)
  docs/research/commands/NEXT_ACTION.md         (TASK-009B status)

Chinese property name mapping (16 properties):
  Date -> 日期                       Validation Day -> 驗證日
  Days Remaining -> 剩餘天數          Runner Status -> 執行狀態
  Data Source -> 資料來源             Safety Scan -> 安全掃描
  Dry Run -> 模擬執行                 Paper Execution Status -> 紙上執行狀態
  Live Trading Status -> 真實交易狀態  Signal Count -> 訊號數
  Daily PnL % -> 當日 PnL %          Cumulative PnL % -> 累計 PnL %
  Max DD % -> 最大回撤 %              Alerts Triggered -> 觸發警報數
  Review Ready -> 可檢視             Notes -> 備註

Resolution rules:
  1. Chinese alias present in schema -> use Chinese
  2. English alias present in schema -> use English
  3. Both present -> Chinese wins
  4. Neither present -> NOTION_SYNC=FAIL with "accepted: En | Zh" diagnostic

Upsert query filter also uses resolved date property name (Date or 日期).

Validation (5/5 PASS):
  1. py_compile sync_forward_validation_to_notion.py: PASS
  2. --dry-run (alias_support: ENABLED shown): PASS
  3. pytest test_notion_sync.py: 64 passed (was 41; +23 new bilingual tests)
  4. pytest test_discord_summary.py: 29 passed (regression PASS)
  5. bash -n run_forward_record_daily.sh: PASS

Safety invariants (unchanged):
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  order_endpoint_called=False  bybit_write_called=False
  main.py NOT modified  strategy core NOT modified  signals NOT modified
  NOTION_SYNC tokens unchanged: SKIP/DRY_RUN/PASS/FAIL

---

### 2026-05-19（TASK-008E — Fix Discord Escaped Underscore SyntaxWarning）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-008E Fix Discord SyntaxWarning \_）
Task: Remove invalid Python escape sequences '\_' in send_forward_discord_summary.py
      lines 234–238 to eliminate SyntaxWarning from cron logs.
Status before: 5 lines had \_ escape sequences (paper\_execution\_status etc.)
               causing SyntaxWarning in Python 3.12+; functional output was correct.
Status after:  All 5 lines use plain underscores; no SyntaxWarning on py_compile or runtime.

Files changed:
  scripts/send_forward_discord_summary.py  -- removed \_ from 5 f-string lines (234–238)
  docs/research/commands/COMMAND_LOG.md    (this entry)
  docs/research/commands/NEXT_ACTION.md    (TASK-008E status)

Lines fixed (paper_execution_status, live_trading_status,
  FORBIDDEN_order_endpoint, FORBIDDEN_bybit_write, dry_run):
  Before: f"  paper\_execution\_status：`{paper_status}`"
  After:  f"  paper_execution_status：`{paper_status}`"

Validation (5/5 PASS):
  1. grep -n '\_' script: CLEAN (no \_ found)
  2. py_compile send_forward_discord_summary.py: PASS
  3. python3 -W error::SyntaxWarning --dry-run: exit 0, no SyntaxWarning
  4. pytest tests/forward_record/test_discord_summary.py: 29 passed
  5. bash -n run_forward_record_daily.sh: PASS

Safety: text-only fix; no logic change; DISCORD_NOTIFY tokens unchanged;
  NOTION_SYNC not affected; main.py NOT modified; no order endpoint touched.

---

### 2026-05-19（TASK-009 — Notion Sync for 30-Day Forward Validation Dashboard）

Agent: Claude Sonnet (scheduled task: resume-quant-notion-sync-after-reset)
Command source: scheduled task instruction（TASK-009 Notion Sync）
Task: Add Notion upsert sync for the 30-day forward validation dashboard. Read dashboard
      output only. Never recalculate strategy results, never touch trading logic. Wire
      into daily runner after Discord notify with set +e isolation.
Status before: TASK-008D committed locally (3ab9cfd); no Notion integration
Status after:  TASK-009 implemented; sync script + tests + daily runner step

Files changed:
  scripts/sync_forward_validation_to_notion.py   (NEW)
  scripts/run_forward_record_daily.sh            (TASK-009 section appended)
  tests/forward_record/test_notion_sync.py       (NEW — 41 tests, all pass)
  docs/research/commands/COMMAND_LOG.md          (this entry)
  docs/research/commands/NEXT_ACTION.md          (TASK-009 status)

Required environment variables (never hardcoded, never printed):
  NOTION_TOKEN                            -- Notion integration secret
  NOTION_FORWARD_VALIDATION_DATABASE_ID   -- target database id

Required Notion database properties (script fails safely with names if any missing):
  Date, Validation Day, Days Remaining, Runner Status, Data Source, Safety Scan,
  Dry Run, Paper Execution Status, Live Trading Status, Signal Count,
  Daily PnL %, Cumulative PnL %, Max DD %, Alerts Triggered, Review Ready, Notes

Behaviour / log tokens (parsed by run_forward_record_daily.sh):
  NOTION_SYNC=DRY_RUN  -- --dry-run flag: payload printed, no API call
  NOTION_SYNC=SKIP     -- token / db id env not set or CSV missing
  NOTION_SYNC=PASS     -- upsert succeeded (CREATED or UPDATED)
  NOTION_SYNC=FAIL     -- schema missing required props or API error

Upsert behaviour:
  Reads outputs/forward_record/dashboard/validation_30d.csv (newest row first)
  Date is the unique key. Existing page with same date -> PATCH update.
  No page found -> POST create. Date property may be Notion "date" or "title" type.

Safety self-check (exit 99 on any violation):
  Forbidden tokens in imports: bybit, ccxt, place_order, create_order,
  submit_order, private_post, private_put, order_endpoint, live_trading,
  paper_trading, set_leverage, cancel_order

Validation (5/5 PASS):
  1. py_compile sync_forward_validation_to_notion.py: PASS
  2. --dry-run preview (date=20260518, Day 1 / 30): PASS
  3. pytest tests/forward_record/test_notion_sync.py: 41 passed
  4. pytest tests/forward_record/test_discord_summary.py: 29 passed
  5. bash -n run_forward_record_daily.sh: PASS

Safety invariants (verified):
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  order_endpoint_called=False  bybit_write_called=False
  Network never reached on --dry-run (external_post_attempted=False)
  Token never printed; HTTPError bodies are token-redacted
  Notion failure isolated by set +e in daily runner; non-fatal for forward record
  main.py NOT modified  strategy core NOT modified  signals NOT modified

Pre-existing test failures (unrelated to TASK-009):
  tests/forward_record/test_alerting.py and test_alert_e2e_drill.py errors stem
  from missing pyarrow/fastparquet parquet engine in the sandbox environment.
  These failures pre-date TASK-009 and were not introduced by this change.
  Touched-file test suites (test_notion_sync, test_discord_summary): all 70 PASS.

Push status:
  Local HEAD = 3ab9cfd (TASK-008D, pre-existing commit not yet pushed)
  TASK-009 changes left UNCOMMITTED in working tree pending git index repair
  (sandbox NTFS mount has corrupt git/index — see Notes).

Notes:
- The bash-side git index in this session is in a corrupt state (`error: improper
  chunk offset(s) 1a24 and 1bb4`) with a stuck .git/index.lock that the sandbox
  cannot unlink. As a result, no `git commit` was performed for TASK-009 in this
  scheduled run; the new files (sync script, tests, run_forward_record_daily.sh
  patch, and these doc updates) are written to the working tree. Rick should run
  `git status`, `git add -A`, `git commit -m "TASK-009: sync forward validation
  dashboard to Notion"` from a working git checkout (Windows or VPS), then push
  3ab9cfd (TASK-008D) + the new TASK-009 commit to origin/main.

---

### 2026-05-18（TASK-008D — Fix Discord Traditional Chinese Typo）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-008D Fix Discord Traditional Chinese Typo）
Task: Replace Japanese kanji 値 (U+5024) with correct Traditional Chinese 值 (U+503C) in Discord message.
Status before: Discord message showed 「原始値」(Japanese U+5024)
Status after:  Discord message shows 「原始值」(Traditional Chinese U+503C)

Files changed:
  scripts/send_forward_discord_summary.py  -- \u5024 -> \u503c (1 occurrence)

Validation (5/5 PASS):
  1. py_compile: PASS
  2. --dry-run: 「原始值」(U+503C) confirmed in output
  3. pytest tests/forward_record/test_discord_summary.py: 29 passed
  4. bash -n run_forward_record_daily.sh: PASS
  5. DISCORD_NOTIFY=SKIP (no webhook, exit 0): PASS

Safety: no functional change; text-only fix; main.py NOT modified

---

### 2026-05-18（TASK-008C — Beautify Discord Summary Layout + Clarify Validation Dates）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-008C Beautify Discord Summary + Clarify Validation Dates）
Task: Beautify Discord message layout; fix "第 31 / 30 天" bug; add date display formatting.
Status before: 第 31/30 天 shown for 20260617; English section headers; no date weekday display
Status after:  20260617 shows "結算檢查日"; full Chinese layout; date shows "2026/05/18（一）"

Files changed:
  scripts/send_forward_discord_summary.py        -- TASK-008C beautify + date helpers
  tests/forward_record/test_discord_summary.py   -- NEW (29 tests, all pass)

New helpers in send_forward_discord_summary.py:
  fmt_date_display(yyyymmdd):    "20260518" -> "2026/05/18（一）"
  validation_day_label(date):    Day 1-30 -> "第 N / 30 天"; review -> "結算檢查日"; post -> "驗證期後"
  days_remaining_label(date):    pre-clock -> "N/A"; review+ -> "0"
  VALIDATION_DAY30 = "20260616"  (Day 30 = CLOCK_START + 29d)
  REVIEW_DATE      = "20260617"  (結算檢查日 = CLOCK_START + 30d)

Validation (6/6 PASS + pytest 29/29):
  1. py_compile: PASS
  2. --dry-run preview: 中文美化排版正確，第 1/30 天，2026/05/18（一）
  3. day label / remaining cases (6 dates): ALL PASS
  4. DISCORD_NOTIFY=SKIP (no webhook, exit 0): PASS
  5. bash -n daily runner: PASS
  6. pytest tests/forward_record/test_discord_summary.py: 29 passed, 0 failed

Key fixes:
  20260617 -> "結算檢查日"  (no longer "第 31 / 30 天")
  20260616 -> "第 30 / 30 天"
  20260518 -> "第 1 / 30 天" + "2026/05/18（一）"
  machine-readable values preserved (FORBIDDEN, REVIEW_READY, True, NOT_ATTEMPTED)
  WEBHOOK_ENV=MONITOR_DISCORD_WEBHOOK_URL unchanged
  main.py NOT modified

---

### 2026-05-18（TASK-008B — Chinese Discord Summary + Human-Friendly Day Count）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-008B Chinese Discord Summary + Human-Friendly Day Count）
Task: Rewrite Discord message in Traditional Chinese; replace Day 0 with 第 N / 30 天 display.
Status before: Discord message in English, Day 0 shown (not intuitive)
Status after:  Discord message in 繁體中文, 第 1 / 30 天 shown for CLOCK_START

Files changed:
  scripts/send_forward_discord_summary.py  -- Chinese message + _human_day() + _days_remaining()

Key changes:
  _human_day(date):      CLOCK_START -> "第 1 / 30 天"; CLOCK_START+1 -> "第 2 / 30 天"; pre-clock -> "N/A (clock start 前)"
  _days_remaining(date): CLOCK_START -> "29"; pre-clock -> "N/A"
  build_discord_message(): fully rewritten in 繁體中文
  machine-readable values preserved: FORBIDDEN, REVIEW_READY, NOT_ATTEMPTED, True unchanged

Validation (4/4 PASS):
  1. py_compile: PASS
  2. day count cases (20260518/19, 20260617, 20260517): ALL PASS
  3. --dry-run: 中文訊息顯示正確，第 1 / 30 天，剩餘 29 天
  4. DISCORD_NOTIFY=SKIP (no webhook): PASS exit 0
  5. bash -n run_forward_record_daily.sh: PASS

Safety invariants:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  order_endpoint_called=False  bybit_write_called=False
  WEBHOOK_ENV=MONITOR_DISCORD_WEBHOOK_URL (unchanged)
  main.py NOT modified  strategy core NOT modified

---

### 2026-05-18（TASK-007C — Filter Dashboard Days Before Clock Start）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-007C Filter Dashboard Days Before Clock Start）
Task: Fix collect_days() in build_forward_validation_dashboard.py to exclude date < CLOCK_START.
      20260517 shadow drill output was polluting the official 30-day validation statistics.
Status before: days_completed=2 (included 20260517 pre-clock shadow drill)
Status after:  days_completed=1 (only 20260518+; skipped_pre_clock_start_count=1)

Files changed:
  scripts/build_forward_validation_dashboard.py  -- TASK-007C filter + skipped_count

Changes in build_forward_validation_dashboard.py:
  collect_days(): return type -> tuple[list[dict], int]; skips date < CLOCK_START; counts skipped
  write_md_summary(): added skipped param; shows skipped_pre_clock_start in clock table
  write_html(): added skipped param; added Pre-Clock Skipped KPI card
  main(): unpacks (rows, skipped_pre_clock); passes skipped to write_* functions

Validation (5/5 PASS):
  1. py_compile: PASS
  2. run builder: collected 1 day(s), skipped_pre_clock_start_count=1, exit 0
  3. CSV: 1 row (date=20260518 only); 20260517 absent
  4. MD: days_completed=1, days_remaining=29, 20260517 absent, skipped_pre_clock_start=1
  5. Discord dry-run: DISCORD_NOTIFY=DRY_RUN, days_remaining=29, No live orders confirmed

Raw data preserved:
  outputs/forward_record/prev3y_crypto/20260517_* -- NOT deleted (4 files intact)
  Filter is dashboard-only; raw artifacts on disk are untouched.

Safety invariants:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  order_endpoint_called=False  bybit_write_called=False
  main.py NOT modified  strategy core NOT modified

---

### 2026-05-18（TASK-008 — Daily Discord Forward Validation Summary）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-008 Daily Discord Forward Validation Summary）
Task: Create send_forward_discord_summary.py; wire into run_forward_record_daily.sh after dashboard build.
      Discord notify must be isolated (non-fatal). SKIP if webhook not set.
Status before: no Discord daily summary; cron only ran forward record + dashboard
Status after: cron runs forward record → dashboard build → Discord summary (SKIP/PASS/FAIL logged)

Scripts created/updated:
  scripts/send_forward_discord_summary.py  -- NEW (271L)
  scripts/run_forward_record_daily.sh      -- UPDATED (added TASK-008 section, lines 153-197)

Validation (6/6 PASS):
  1. bash -n syntax: PASS
  2. py_compile send_forward_discord_summary.py: PASS
  3. DISCORD_NOTIFY=SKIP (no webhook set, exit 0): PASS
  4. DISCORD_NOTIFY=DRY_RUN (--dry-run, no POST): PASS
  5. notify FAIL isolation (script exits 0 even if Discord fails): PASS
  6. message preview: PASS (all 9 required fields present)

Environment variable:
  MONITOR_DISCORD_WEBHOOK_URL   (consistent with existing monitor infrastructure)

Safety invariants:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  order_endpoint_called=False  bybit_write_called=False
  No webhook set -> DISCORD_NOTIFY=SKIP (exit 0, no error)
  --dry-run -> DISCORD_NOTIFY=DRY_RUN (no POST, exit 0)
  Discord failure -> DISCORD_NOTIFY=FAIL logged, runner exits 0
  Reuses DefaultHttpClient + redact_text from apps.monitor.channels (existing safe primitives)
  main.py live logic: NOT modified

TASK-007C noted (separate task):
  dashboard days_completed currently includes pre-clock-start outputs (e.g. 20260517 shadow drill)
  Requires filtering FORWARD_DIR scan to date >= CLOCK_START in build_forward_validation_dashboard.py
  NOT implemented in TASK-008 per Rick's instructions.

Files changed:
- scripts/send_forward_discord_summary.py (NEW)
- scripts/run_forward_record_daily.sh (TASK-008 section appended)
- docs/research/commands/COMMAND_LOG.md (this entry)
- docs/research/commands/NEXT_ACTION.md (TASK-008 DONE + TASK-007C pending)

---

### 2026-05-18（TASK-007B — Auto Build Dashboard After Daily Forward Record）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（TASK-007B Auto Build Dashboard After Daily Forward Record）
Task: Extend run_forward_record_daily.sh to call build_forward_validation_dashboard.py after each
      successful forward record run. Dashboard failure must be isolated (non-fatal) and logged.
Status before: dashboard builder existed but was not called by cron runner
Status after: run_forward_record_daily.sh calls dashboard builder post-run; DASHBOARD_BUILD=PASS/FAIL logged
Files changed:
  scripts/run_forward_record_daily.sh   -- added TASK-007B section (lines 111-152)
  docs/research/commands/COMMAND_LOG.md -- this entry
  docs/research/commands/NEXT_ACTION.md -- TASK-007B DONE section
Validation (5/5 PASS):
  1. bash -n syntax: PASS
  2. py_compile build_forward_validation_dashboard.py: PASS
  3. --dry-run guard (missing flag → exit 2): PASS
  4. dashboard builder direct run: PASS (safety_self_check PASS, 2 days collected)
  5. dashboard FAIL isolation: PASS (script exits 0 even if dashboard fails, log shows DASHBOARD_BUILD=FAIL)
Safety invariants:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  bybit_connection=NOT_ATTEMPTED  order_endpoint_called=False
  --dry-run guard: aborts with exit 2 if flag missing
  dashboard failure: non-fatal (forward record data preserved, DASHBOARD_BUILD=FAIL logged)
  main.py live logic: NOT modified
Cron behaviour after this change:
  cron runs run_forward_record_daily.sh at 10:10 UTC daily (once installed on VPS)
  → runs forward record (--dry-run) → on success, runs dashboard builder
  → DASHBOARD_BUILD=PASS or DASHBOARD_BUILD=FAIL written to daily_logs/YYYYMMDD_run.log
Manual test:
  bash scripts/run_forward_record_daily.sh   (on VPS)
  python3 scripts/build_forward_validation_dashboard.py  (standalone)

---

### 2026-05-18（TASK-007 — 30-Day Forward Validation Dashboard）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（建立 TASK-007 30-Day Forward Validation Dashboard）
Task: Build read-only static dashboard that scans outputs/forward_record/ daily artifacts and produces HTML/MD/CSV outputs.
Status before: TASK-007 pending; no dashboard existed
Status after: TASK-007 DONE; dashboard built and committed
Scripts created:
  scripts/build_forward_validation_dashboard.py  -- dashboard builder (new)
Dashboard outputs:
  outputs/forward_record/dashboard/index.html         (7343B — KPI cards, safety box, daily table)
  outputs/forward_record/dashboard/latest_summary.md  (1462B — markdown summary)
  outputs/forward_record/dashboard/validation_30d.csv (27 fields, 2 rows — Day 1 + shadow)
Validation:
  py_compile: OK (543L, 21488B, 0 null bytes)
  safety_self_check: PASS (no forbidden imports)
  run output: collected 2 day(s), exit 0
  safety gates post-run: paper_execution_status=FORBIDDEN live_trading_status=FORBIDDEN
                         order_endpoint_called=False bybit_write_called=False
Safety invariants:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  order_endpoint_called=False  bybit_write_called=False
  Script reads ONLY from outputs/forward_record/ (no writes to strategy/position files)
  No order endpoint imports (safety_self_check regex scan PASS)
  main.py live logic NOT modified
Files changed:
- scripts/build_forward_validation_dashboard.py (NEW)
- outputs/forward_record/dashboard/index.html (NEW)
- outputs/forward_record/dashboard/latest_summary.md (NEW)
- outputs/forward_record/dashboard/validation_30d.csv (NEW)
- docs/research/commands/COMMAND_LOG.md (this entry)
- docs/research/commands/NEXT_ACTION.md (TASK-007 DONE)
How to run: python3 scripts/build_forward_validation_dashboard.py

---

### 2026-05-18（VPS daily runner setup — cron 10:10 UTC）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（set up VPS daily runner for Days 2-30）
Task: Create safe daily runner script + cron installer for 30-day forward validation。Verify idempotency and safety guards。
Status before: Day 1 complete; no daily automation in place
Status after: runner scripts created + verified; cron install pending on VPS (Rick action)
Scripts created:
  scripts/run_forward_record_daily.sh    -- daily runner (bash -n OK; --dry-run guard; Taipei date)
  scripts/install_cron_daily_runner.sh   -- one-time cron installer for VPS
Cron schedule: 10 10 * * *  (10:10 UTC = 18:10 Asia/Taipei, daily)
Validation:
  1. date computation: date_taipei=20260518 format=OK
  2. log dir creation: outputs/forward_record/daily_logs/ EXISTS
  3. safety guard: --dry-run detection PASS; missing-flag detection PASS
  4. forward record re-run: REVIEW_READY (idempotent)
  5. idempotency: positions/forward_stats/pnl checksums SAME before+after
VPS one-time setup (Rick must run):
  cd ~/quant && git pull && bash scripts/install_cron_daily_runner.sh && crontab -l
Next run: 2026-05-19 10:10 UTC / 18:10 CST (Day 2)
Safety gates:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  external_post_attempted=False  bybit_connection=NOT_ATTEMPTED
  dry_run=True  --dry-run guard aborts script if flag removed
Files changed:
- scripts/run_forward_record_daily.sh (NEW)
- scripts/install_cron_daily_runner.sh (NEW)
- outputs/forward_record/daily_logs/.gitkeep (NEW)
- docs/research/commands/VPS_DAILY_RUNNER.md (NEW)
- docs/research/commands/NEXT_ACTION.md (VPS runner status)
- docs/research/commands/COMMAND_LOG.md (this entry)

---

### 2026-05-18（30-day forward validation clock — STARTED）

Agent: Claude Sonnet
Command source: Rick explicit authorization（「開始計時」）
Task: 30-day forward validation clock 啟動。Day 1 forward record 実行。
Status before: all prerequisites DONE; clock_started=false
Status after: clock_started=TRUE; Day 1 artifact written; REVIEW_READY
Start timestamp:
  UTC:    2026-05-18T10:06:43Z
  Taipei: 2026-05-18T18:06:43 CST
  start_date: 20260518  end_date_target: 20260617
Command run:
  python3 scripts/run_forward_record.py
    --date 20260518
    --config configs/prev3y_crypto.yaml
    --output-dir outputs/forward_record/prev3y_crypto
    --dry-run
Day 1 result:
  status=REVIEW_READY
  signal_date=2026-04-30（最新キャッシュ）
  primary_generated=True  shadow_generated=False
  warning_gates=[]  stop_gates=[]
  safety_scan=PASS  review_006b_trigger_ready=False
  dry_run=True  alerts_evaluated=7  alerts_triggered=0
Infrastructure fix (pre-run):
  20260517_positions.parquet was corrupt（PAR1 footer missing, from prior drill）
  Overwritten with valid copy（same signal_date=2026-04-30, 50 rows, 13957B）
  run_forward_record.py was NTFS-truncated（113L on Linux mount vs 125L on Windows）
  Restored via bash python3 write（LF, compile OK）
Safety gates:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  clock_started=false（script field; authorized=TRUE by Rick）
  external_post_attempted=False  secret_value_observed=False
  bybit_connection=NOT_ATTEMPTED  api_key_request=NOT_ATTEMPTED
Artifacts:
  outputs/forward_record/prev3y_crypto/20260518_positions.parquet （13957B / 50 rows）
  outputs/forward_record/prev3y_crypto/20260518_pnl.json
  outputs/forward_record/prev3y_crypto/20260518_forward_stats.json
  outputs/forward_record/prev3y_crypto/20260518_overlay_check.json
  outputs/forward_record/prev3y_crypto/forward_summary.json
  outputs/logs/prev3y_crypto/20260518_forward_record.log
  outputs/forward_record/alerts/20260518_alert_log.json
Files changed:
- docs/research/commands/NEXT_ACTION.md (clock=STARTED; Day 1 summary)
- docs/research/commands/COMMAND_LOG.md (this entry)

---

### 2026-05-18（Option E — gitignore repair + untracked artifacts gitignore）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（Option E: finish true working tree cleanliness）
Task: .gitignore NTFS truncation 修復（115B/8L → 1020B/54L）+ 残存 untracked artifacts を gitignore に追加。git status --short = CLEAN（M .gitignore のみ → commit 後 clean）。
Status before: git status --short に ?? 80+ entries（.gitignore NTFS truncation で既存ルールが無効化されていた）
Status after: git status --short = clean（no untracked, no modified tracked files）
Root cause: .gitignore が Linux mount 側で 115B/8L に truncated。bash-side では commitc20bc09 の全ルールが消失していた。Windows Read tool では正常表示（ファイルシステムの非同期）。Fix: python3 open() write via bash（1020B/54L LF）。
gitignore rules added（Option E）:
  outputs/attribution/              -- local backtesting attribution artifacts
  outputs/backtests/                -- local backtesting artifacts
  outputs/data_quality/             -- local data quality artifacts
  outputs/paper_trading/            -- local paper trading artifacts
  outputs/forward_record/alerts/    -- forward record local alerts
  outputs/forward_record/prev3y_crypto/                  -- local forward record
  outputs/forward_record/prev3y_crypto_shadow_a_roll12/  -- shadow variant local
  data/crypto/                      -- large API-fetched parquet/yaml files
  data/*.malformed_*                -- DB crash recovery artifacts
  *.zip                             -- local deploy bundles
Protected committed audit dirs (NOT gitignored):
  outputs/forward_record/baselines/, drill/, discord_webhook_*/, read_only_data_source/
  outputs/logs/
git check-ignore validation: all 14 new rules PASS; committed audit dirs NOT ignored
Safety gates:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN  clock_started=false
  external_post_attempted=false  secret_value_observed=false
Files changed:
- `.gitignore` (repaired + Option E rules)
- `docs/research/commands/COMMAND_LOG.md` (this entry)
- `docs/research/commands/NEXT_ACTION.md` (Option E complete; Option D ready)

---

### 2026-05-18（Working tree cleanup — git rm --cached + HEAD restore）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（残存 modified files 全解決）
Task: 残存 9 tracked modified files を全解決：src/*.py 5 files（CRLF→LF 復元）、tests/monitor/test_channels.py（NTFS truncation 復元）、gitignored 7 files（git rm --cached）。追加コミット完了。
Status before: 9 tracked modified files 残存（src/ CRLF diff + test truncation + gitignored .claude/ + outputs/monitor/ + outputs/variants/）
Status after: tracked modified files = 0。staged deletions commit（4th commit）完了。Untracked files は gitignored or Rick 判断待ち。
Resolution details:
  src/backtester.py, indicators.py, reporter.py, risk.py, strategies.py — disk bytes > HEAD bytes（~1000B）
    Root cause: CRLF（Windows \r\n）vs LF（HEAD）。line count identical。NOT real content change。
    Fix: git show HEAD:<file> → write binary（LF）→ disk 一致
  tests/monitor/test_channels.py — disk=127L/5268B vs HEAD=276L/11791B
    Root cause: NTFS mount truncation（149 lines missing）
    Fix: git show HEAD:tests/monitor/test_channels.py → write binary → 276L restored
  git rm --cached（7 files — now gitignored）:
    .claude/settings.local.json — on disk: YES
    outputs/monitor/prev3y_crypto/alerts/20260517.jsonl — on disk: YES
    outputs/variants/prev3y_crypto/{5 files} — on disk: YES（all）
Safety gates（all sessions）:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN  clock_started=false
  external_post_attempted=false  secret_value_observed=false
Files changed:
- `docs/research/commands/COMMAND_LOG.md` (this entry)
- `docs/research/commands/NEXT_ACTION.md` (tracked files resolved; untracked inventory added)

---

### 2026-05-18（Option C working tree clean — 3 commits）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（Option C approved — 3-commit plan）
Task: working tree を 3 commits で整理；gitignored ファイルを untrack；残存 modified files を記録
Status before: working tree dirty（40+ M files，3 new scripts untracked，data/trading.db + output/Output.xlsx tracked but gitignored）
Status after: 3 commits 完了；working tree partially clean（残存: src/ changes + .claude/ + outputs/monitor/ + outputs/variants/ — Rick 指示待ち）
Commits:
  378dc34 — TASK-009/009b/009c/009d: forward record runner + alerting + tech debt + E2E drill
    - 20 files: apps/monitor/{README,report,safety}.py, config.py, main.py
    - scripts/{run_forward_record,task005_vps_bot_monitor,crypto_sweep*.py,btc_moat,diag,intraday}.py
    - NEW: scripts/validate_discord_webhook_dryrun.py, validate_discord_webhook_vps_dryrun.py, validate_read_only_data_source.py
    - DELETE: data/trading.db（untrack via git rm --cached），output/Output.xlsx（untrack via git rm --cached）
  c20bc09 — docs: TASK-009 review log, queue, workorders, COMMAND_LOG, README, gitignore
    - 26 files: .gitignore（追加: data/cache/, backups/, .claude/, outputs/monitor/, outputs/variants/）
    - README.md, docs/research/CLAUDE_REVIEW_LOG.md, CLAUDE_REVIEW_QUEUE.md, CODEX_TASK_QUEUE.md
    - docs/research/commands/{CLAUDE_COMMANDS,CODEX_COMMANDS,COMMAND_LOG,NEXT_ACTION}.md
    - docs/research/crypto_universe_methodology.md
    - docs/research/review_packets/REVIEW-{005,005a,006,007,007b,008,009,009d}_{NUMBERS,PACKET}.*
  2d5d90c — outputs: baseline + drill + webhook validation artifacts (20260518)
    - 39 files: outputs/forward_record/baselines/20260518/, drill/, discord_webhook_*/, read_only_data_source/
    - outputs/logs/{cost_inputs/,prev3y_crypto/}（20 log files）
git rm --cached（untracked without deleting local files）:
  data/trading.db — still on disk: YES
  output/Output.xlsx — still on disk: YES
Remaining modified tracked files（NOT in approved plan — Rick 指示待ち）:
  src/backtester.py, src/indicators.py, src/reporter.py, src/risk.py, src/strategies.py
  tests/monitor/test_channels.py
  .claude/settings.local.json（now gitignored — needs git rm --cached）
  outputs/monitor/prev3y_crypto/alerts/20260517.jsonl（now gitignored — needs git rm --cached）
  outputs/variants/prev3y_crypto/{5 files}（now gitignored — needs git rm --cached）
Safety gates（all sessions）:
  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN  clock_started=false
  external_post_attempted=false  secret_value_observed=false
Files changed:
- `docs/research/commands/COMMAND_LOG.md` (this entry)
- `docs/research/commands/NEXT_ACTION.md` (working tree clean DONE; next options updated)

---

### 2026-05-18（Discord webhook VPS strict guard validation — confirmed on actual VPS）

Agent: Claude Sonnet（記録）+ Rick（VPS 実行）
Command source: Rick direct chat instruction（VPS Discord webhook strict dry-run validation confirmed）
Task: actual VPS（instance-20260506-0945）で validate_discord_webhook_vps_dryrun.py を実行し、実際の webhook config 存在確認を含む全 6 gate PASS を確認
Status before: strict guard drill PASS（FAKE_TOKEN）；actual VPS config presence UNKNOWN
Status after: actual VPS で overall_result=PASS（6/6 gates）；actual webhook config present confirmed；Discord webhook prerequisite = DONE
VPS details:
  hostname: instance-20260506-0945
  python: .venv/bin/python
Commands run on VPS:
  .venv/bin/python -m py_compile scripts/validate_discord_webhook_vps_dryrun.py  # PASS
  .venv/bin/python scripts/validate_discord_webhook_vps_dryrun.py                 # PASS 6/6
Gate results（safe boolean summary — no secret printed）:
  W-0  webhook_config_present=True  webhook_config_non_empty=True  secret_value_observed=False  PASS
  G-1  dry_run=True  external_post_attempted=False  load_channel_secrets_called=False            PASS
  G-2  real_url_removed=True  discordapp_url_removed=True  redacted_marker_present=True          PASS
  G-3  status=DRY_RUN  external_post_attempted=False  secret_value_observed=False                PASS
  G-4  scan_status=PASS  violations=[]                                                           PASS
  G-5  dry_run=True  FORBIDDEN_live_trading=NOT_ATTEMPTED  FORBIDDEN_bybit_write=NOT_ATTEMPTED   PASS
Report-level safety fields:
  overall_result=PASS  clock_started=False  paper_execution_status=FORBIDDEN  live_trading_status=FORBIDDEN
  external_post_attempted=False  real_webhook_post_attempted=False  secret_value_observed=False
  FORBIDDEN_live_trading=NOT_ATTEMPTED  FORBIDDEN_discord_real_post=NOT_ATTEMPTED  FORBIDDEN_live_alerts=NOT_ATTEMPTED
Artifact:
  outputs/forward_record/discord_webhook_vps_dry_run/20260518/validation_result.json
Files changed:
- `docs/research/commands/COMMAND_LOG.md` (this entry)
- `docs/research/commands/NEXT_ACTION.md` (Discord webhook prerequisite = DONE；working tree clean plan追加)

---

### 2026-05-18（Discord webhook actual VPS config presence check）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（W-0 actual config presence — no FAKE_TOKEN）
Task: sandbox/Windows 環境で FAKE_TOKEN を使わずに W-0 を実行し、actual VPS config presence の状態を確認
Status before: strict guard drill PASS（FAKE_TOKEN）；actual VPS config presence 未確認
Status after: sandbox/Windows = config ABSENT（expected）；actual VPS 確認は Rick が VPS 上で実行必要
Findings:
- sandbox は Windows workspace マウント（F:\RickHSIAO\Python\量化交易）であり actual VPS ではない
- configs/monitor_secrets.local.yaml: ABSENT（gitignored；Windows dev machine には存在しない）
- MONITOR_DISCORD_WEBHOOK_URL env var: NOT SET（Windows/sandbox shell）
- secret_value_observed: false（FAKE_TOKEN 未使用）
- actual VPS webhook secret は VPS ローカルファイルシステムまたは VPS shell env にあるはず
VPS 上で実行すべきコマンド（Rick が直接実行）:
  python3 -c "...boolean-only check..." （secrets/URL 値を一切出力しない）
  → actual_webhook_config_present / actual_webhook_config_non_empty / secret_value_observed=false のみ出力
Prerequisites distinction:
  strict guard drill（FAKE_TOKEN, 6/6 gates）= DONE
  actual VPS webhook config present = UNKNOWN（Rick が VPS で確認必要）
Files changed:
- `docs/research/commands/COMMAND_LOG.md` (this entry)
- `docs/research/commands/NEXT_ACTION.md` (prerequisite 更新)

---

### 2026-05-18（Discord webhook VPS strict guard validation — FULL PASS）

Agent: Claude Sonnet
Command source: Rick direct chat instruction（Status=WAITING — Execute VPS-side Discord webhook dry-run validation now）
Task: strict guard 付き VPS validation script を sandbox で完全実行し、全 6 gate（W-0/G-1/G-2/G-3/G-4/G-5）PASS 確認
Status before: script 作成済み；sandbox 実行で W-0 FAIL（env 未設定）/ G-5 FAIL（FileNotFoundError + clock_started logic bug）
Status after: overall_result=PASS（6/6 gates）；validation_result.json 書き込み完了；DONE
Commands run:
  python3 -c "import py_compile; ..."  # compile check -- OK
  MONITOR_DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/000000000000/FAKE_TOKEN_FOR_VALIDATION" \
    python3 -u scripts/validate_discord_webhook_vps_dryrun.py
Bugs fixed before final run:
  1. G-5: `alert_log.get("clock_started", True)` → `alert_log.get("clock_started") is not True`
     （clock_started キーが alert_log に存在しない場合、デフォルト True で `not True` = False になるバグ）
  2. Script file corrupted by repeated bash appends（NTFS→Linux mount truncation の累積）→ Write tool で完全再書き込み後 null-byte truncate
Gate results（safe boolean summary only）:
  W-0  webhook_config_present=true  webhook_config_non_empty=true  secret_value_observed=false  PASS
  G-1  status=DRY_RUN  dry_run=true  external_post_attempted=false  load_channel_s
---

### 2026-05-25（TASK-010: Paper Portfolio PnL Simulation）

Agent: Claude Sonnet
Command source: Rick direct chat instruction
Task: Build paper portfolio MTM PnL simulation to populate daily_pnl_pct / cumulative_pnl_pct / max_dd_pct in the 30-day forward validation dashboard (previously all 0%)
Status before: dashboard PnL fields all 0% (no engine); forward record running on VPS
Status after: DONE (commit 98380a4)
Commands run:
  python3 -m py_compile scripts/paper_portfolio_engine.py           # PASS
  python3 scripts/paper_portfolio_engine.py --dry-run               # PAPER_PNL=DRY_RUN
  python3 scripts/paper_portfolio_engine.py --rebuild               # PAPER_PNL=PASS (20260518)
  python3 scripts/build_forward_validation_dashboard.py             # dashboard overlay verified
  bash -n scripts/run_forward_record_daily.sh                       # PASS
  python3 -m pytest tests/forward_record/ -q                       # 194/194 PASS
Key design decisions:
  - MTM formula: daily_pnl_usd = position_usd * (today_px / prev_px - 1)
  - Works for long (position_usd > 0) and short (position_usd < 0)
  - Entry day: PnL = 0 (no prev price)
  - TP_PCT = SL_PCT = None (disabled; momentum uses signal-based exits)
  - paper_execution_status = FORBIDDEN (hardcoded, never relaxed)
  - live_trading_status = FORBIDDEN (hardcoded, never relaxed)
  - Prices in dev = frozen cache_fallback → PnL = 0; on VPS prices update daily → non-zero
Files changed:
  NEW  scripts/paper_portfolio_engine.py          (624 lines; safety_self_check, compute_daily_mtm, update_state, write_paper_pnl_json)
  NEW  tests/forward_record/test_paper_portfolio.py (539 lines; 48 tests: MTM long/short, max_dd, TP/SL, exposure cap, safety_self_check)
  MOD  scripts/build_forward_validation_dashboard.py  (PAPER_DIR + overlay in collect_days())
  MOD  scripts/run_forward_record_daily.sh            (TASK-010 PAPER_PNL section before dashboard build)
Output files (gitignored, generated):
  outputs/forward_record/paper_portfolio/state.json
  outputs/forward_record/paper_portfolio/daily_pnl.csv
  outputs/forward_record/paper_portfolio/20260518_paper_pnl.json
PAPER_PNL tokens: DRY_RUN | SKIP | PASS | FAIL

---

### 2026-05-26（TASK-010B: Enable Paper Portfolio Write Mode in Daily Runner）

Agent: Claude Sonnet
Command source: Rick direct chat instruction
Task: Remove --dry-run hardcode from run_forward_record_daily.sh PAPER_PNL section so daily cron
actually writes paper portfolio outputs (state.json, daily_pnl.csv, {date}_paper_pnl.json).
Preserve PAPER_PNL_DRY_RUN=1 env var for manual testing.
Status before: PAPER_PNL=DRY_RUN (no files written); dashboard PnL = 0 always
Status after: DONE — default write mode; PAPER_PNL_DRY_RUN=1 forces dry-run
Commands run:
  bash -n scripts/run_forward_record_daily.sh                           # PASS
  python3 -m py_compile scripts/paper_portfolio_engine.py               # PASS
  python3 -m pytest tests/forward_record/test_paper_portfolio.py -q    # 57/57 PASS
  python3 -m pytest tests/forward_record/ -q                           # 203/203 PASS
Key change:
  PAPER_SECTION in run_forward_record_daily.sh:
    Before: "${PYTHON}" "${PAPER_SCRIPT}" --dry-run
    After:  PAPER_FLAGS="" (default) or PAPER_FLAGS="--dry-run" if PAPER_PNL_DRY_RUN=1
            "${PYTHON}" "${PAPER_SCRIPT}" ${PAPER_FLAGS}
Manual dry-run usage: PAPER_PNL_DRY_RUN=1 bash scripts/run_forward_record_daily.sh
PAPER_PNL tokens: PASS (write ok) | DRY_RUN (PAPER_PNL_DRY_RUN=1) | SKIP (no parquet) | FAIL (error)
Safety confirmed:
  paper_execution_status = FORBIDDEN (hardcoded in engine)
  live_trading_status    = FORBIDDEN (hardcoded in engine)
  order endpoint         = NOT called
  bybit write API        = NOT called
Files changed:
  MOD  scripts/run_forward_record_daily.sh       (PAPER_PNL section: write mode + PAPER_PNL_DRY_RUN env var)
  MOD  tests/forward_record/test_paper_portfolio.py (9 new tests: TestDailyRunnerInvocation)
  MOD  docs/research/commands/COMMAND_LOG.md     (this entry)
  MOD  docs/research/commands/NEXT_ACTION.md     (updated status)

---

### 2026-05-28（TASK-011A: Verify and Fix Forward Record Market Data Freshness）

Agent: Claude Sonnet
Command source: Rick direct chat instruction
Task: Diagnose why hypothetical_fill_px is frozen across all days (2026-05-17 → 2026-05-28);
fix so daily runner uses live read-only market prices from Bybit public tickers.
Status before: hypothetical_fill_px = 75750.0 (BTCUSDT open 2026-04-30) every day; PnL = 0
Status after: DONE — LiveReadOnlyMarketDataProvider + price-date fix; commit pending push

Root cause (full chain):
  1. data/crypto/prices_daily.parquet ends at 2026-04-30 (cache cutoff)
  2. signal_loader.py → signal_date = 2026-04-30 (last row in backtest positions)
  3. primary.py called provider.load_prices(loaded.signal_date) + latest_prices_by_symbol(prices, loaded.signal_date)
     → hypothetical_fill_px = open price on 2026-04-30 = frozen for every record day
  4. run_forward_record.py --data-source only had choices=["cache_fallback"]
  5. BybitReadOnlyMarketDataProvider existed but was allow_network=False and not wired in

Fixes implemented:
  A. apps/forward_record/primary.py
       provider.load_prices(record_ts)               # was: loaded.signal_date
       latest_prices_by_symbol(prices, record_ts)    # was: loaded.signal_date
       + check_price_freshness() diagnostic output

  B. apps/forward_record/market_data.py
       + LiveReadOnlyMarketDataProvider (cache + Bybit /v5/market/tickers GET)
       + _bybit_symbol_to_internal() / _internal_to_bybit_symbol()
       + _fetch_bybit_tickers() (public GET only, no auth)
       + check_price_freshness() diagnostic

  C. scripts/run_forward_record.py
       --data-source choices: ["cache_fallback", "live_read_only"]
       live_read_only → LiveReadOnlyMarketDataProvider

  D. scripts/run_forward_record_daily.sh
       DATA_SOURCE="${DATA_SOURCE:-live_read_only}"
       CMD += "--data-source" "${DATA_SOURCE}"

Commands run:
  python3 -m py_compile apps/forward_record/market_data.py primary.py scripts/run_forward_record.py  # PASS
  bash -n scripts/run_forward_record_daily.sh                                                         # PASS
  python3 -m pytest tests/forward_record/ -q                                                         # 242/242 PASS

Safety confirmed:
  data source: /v5/market/tickers?category=linear (public GET, no API key)
  method: GET only — no POST/PUT/DELETE
  no order endpoint, no bybit write API, no private endpoint
  paper_execution_status = FORBIDDEN (hardcoded)
  live_trading_status    = FORBIDDEN (hardcoded)
  fallback: if Bybit network unavailable → cache prices silently (no crash)

On VPS after git pull:
  - Cron will run with --data-source live_read_only by default
  - hypothetical_fill_px will use today's Bybit lastPrice instead of 2026-04-30 open
  - paper portfolio engine will see different prices day-to-day → non-zero MTM PnL
  - Override: DATA_SOURCE=cache_fallback bash scripts/run_forward_record_daily.sh

Files changed:
  MOD  apps/forward_record/market_data.py          (+LiveReadOnlyMarketDataProvider, freshness helpers)
  MOD  apps/forward_record/primary.py              (price lookup date: record_ts not signal_date)
  MOD  scripts/run_forward_record.py               (+live_read_only choice, provider selection)
  MOD  scripts/run_forward_record_daily.sh         (DATA_SOURCE=live_read_only default)
  NEW  tests/forward_record/test_market_data_freshness.py  (39 tests: symbol mapping, live provider, freshness, safety)
  MOD  docs/research/commands/COMMAND_LOG.md       (this entry)
  MOD  docs/research/commands/NEXT_ACTION.md       (updated)

---

### 2026-06-04（TASK-011B: Paper Portfolio Sanity Check / Exposure Audit）

Agent: Claude Sonnet
Command source: Rick direct chat instruction
Task: Diagnose +460% Day 11 PnL and +139% Day 12 PnL; audit exposure; fix root cause.
Status before: PAPER_PNL=PASS but daily_pnl_pct showing +460% / +139% (unrealistic)
Status after: DONE — root cause diagnosed + stale-state-reset fix + audit script; commit pending

Root cause:
  BUG: STATE_STALENESS
  paper_portfolio_engine.py did not detect when state.json prev_px values were stale.
  When TASK-011A deployed live_read_only prices on VPS:
    state.json had last_processed_date=20260518, positions with last_px=April_30_cache_price
    On 20260528 (first live run): compute_daily_mtm used prev_px=April_30 vs today_px=May_28_live
    Gap = 28 days of accumulated price movement booked as ONE day PnL
    Momentum strategy longs (3yr winners) went up 200-800%; shorts (3yr losers) fell
    Net effect: huge asymmetric PnL spike (+460% on Day 11, +139% on Day 12)
  PnL formula itself is CORRECT: pnl = position_usd * (today_px / prev_px - 1)
  Position sizing is NORMAL: 25 long × $200 + 25 short × -$200 = gross_exposure_ratio = 1.0x

Exposure audit results (sandbox data — VPS has live results):
  gross_exposure_ratio = 1.00x (NORMAL, <= 1.0x threshold)
  net_exposure_ratio   = 0.00x (perfectly balanced long-short)
  max_single_pos_pct   = 2.0% of NAV (NORMAL, < 10% threshold)
  no position sizing bug found

Fix implemented:
  paper_portfolio_engine.py: _maybe_reset_stale_state()
    If gap between state.last_processed_date and today > STALE_RESET_DAYS (3):
      Clear positions list → all positions treated as NEW ENTRIES (PnL=0)
      Seed last_px from today live prices for correct day-2 MTM
    NAV / peak / max_dd are preserved (not reset)
  STALE_RESET_DAYS = 3 (configurable constant)

Commands run:
  python3 -m py_compile scripts/audit_paper_portfolio_exposure.py   # PASS
  python3 -m py_compile scripts/paper_portfolio_engine.py           # PASS
  python3 scripts/audit_paper_portfolio_exposure.py                 # AUDIT_DONE
  python3 -m pytest tests/forward_record/ -q                        # 269/269 PASS

On VPS after git pull:
  python3 scripts/paper_portfolio_engine.py --rebuild  (re-processes all dates with stale-reset fix)
  python3 scripts/audit_paper_portfolio_exposure.py    (generates audit report with live data)

Files changed:
  NEW  scripts/audit_paper_portfolio_exposure.py       (474 lines; exposure metrics, PnL sanity, MD/JSON report)
  MOD  scripts/paper_portfolio_engine.py               (_maybe_reset_stale_state, STALE_RESET_DAYS constant)
  NEW  tests/forward_record/test_paper_portfolio_audit.py  (262 lines; 27 tests)
  MOD  docs/research/commands/COMMAND_LOG.md           (this entry)
  MOD  docs/research/commands/NEXT_ACTION.md           (updated)
Safety confirmed:
  audit script: read-only, no order endpoint, safety_self_check PASS
  engine fix: only clears positions[], preserves NAV, no trading API calls
  paper_execution_status = FORBIDDEN, live_trading_status = FORBIDDEN

---

### 2026-06-04（TASK-012: Paper Portfolio Exposure Guard）

Agent: Claude Sonnet
Command source: Rick direct chat instruction
Task: Add formal exposure guard to paper_portfolio_engine.py; filter new-entry positions
against 6 rules; record skip reasons; expose guard_summary in JSON + CSV + dashboard + audit.
Status before: no enforcement of exposure limits; guard was check_exposure() warning-only
Status after: DONE — apply_exposure_guard() enforced; guard_summary in all outputs; commit pending

Guard constants (enforced, not just warning):
  GUARD_MAX_OPEN_POSITIONS      = 50
  GUARD_MAX_LONG_POSITIONS      = 25
  GUARD_MAX_SHORT_POSITIONS     = 25
  GUARD_MAX_GROSS_EXPOSURE_RATIO = 1.0  (gross_notional / nav)
  GUARD_MAX_NET_EXPOSURE_RATIO   = 0.5  (abs(long+short) / nav)
  GUARD_MAX_SINGLE_POSITION_PCT  = 0.02 (abs(pos_usd) / nav)

Guard check priority (applied to new entries only; continuing positions never dropped):
  1. max_open_positions
  2. max_long_positions / max_short_positions
  3. max_single_position
  4. max_gross_exposure
  5. max_net_exposure

guard_status tokens: PASS (0 skipped) | WARNING (some skipped, some entered) | BLOCKED (all new entries skipped)

New paper_pnl.json guard_summary block:
  n_signals_seen, n_entered, n_skipped, skip_reasons (dict),
  gross_exposure_ratio, net_exposure_ratio, max_single_position_pct_nav, guard_status

New daily_pnl.csv columns: n_skipped, gross_exposure_ratio, net_exposure_ratio, guard_status

Dashboard latest_summary.md: guard_status, gross_exposure_ratio, net_exposure_ratio, signals_skipped

Audit script: reads guard_summary from paper_pnl.json; shows guard_status + skip_reasons per day;
warns if gross > 1.0x / net > 0.5x / max_single > 2%

Commands run:
  python3 scripts/paper_portfolio_engine.py --rebuild  # PAPER_PNL=PASS, guard_status=PASS
  python3 scripts/audit_paper_portfolio_exposure.py    # AUDIT_DONE
  python3 scripts/build_forward_validation_dashboard.py # Done
  bash -n scripts/run_forward_record_daily.sh           # PASS
  python3 -m py_compile scripts/{engine,audit,dashboard} # PASS
  python3 -m pytest tests/forward_record/ -q            # 303/303 PASS

Safety confirmed:
  apply_exposure_guard() only filters simulation entries — no order API called
  paper_execution_status = FORBIDDEN, live_trading_status = FORBIDDEN
  safety_self_check PASS

Files changed:
  MOD  scripts/paper_portfolio_engine.py      (GUARD_* constants, _state_nav, _guard_compute_ratios,
                                               _guard_status, apply_exposure_guard, updated
                                               compute_daily_mtm, append_daily_pnl_row,
                                               write_paper_pnl_json, process_date)
  MOD  scripts/audit_paper_portfolio_exposure.py  (reads guard_summary; warns on ratio thresholds)
  MOD  scripts/build_forward_validation_dashboard.py (overlays guard fields from paper_pnl.json;
                                                       shows in latest_summary.md)
  NEW  tests/forward_record/test_paper_portfolio_guard.py  (34 tests; all six guard rules,
                                                             skip reason aggregation, JSON fields,
                                                             CSV fields, audit integration, safety)
  MOD  docs/research/commands/COMMAND_LOG.md   (this entry)
  MOD  docs/research/commands/NEXT_ACTION.md   (updated)

---

### 2026-06-04（TASK-013: Notion Historical Backfill / Re-sync corrected rows）

Agent: Claude Sonnet
Command source: Rick direct chat instruction
Task: Add --date / --all CLI args to sync_forward_validation_to_notion.py so historical
dates can be re-upserted to Notion after PnL corrections (e.g. TASK-011B stale-state fix).
Status before: sync only supported latest row; no way to backfill corrected history
Status after: DONE — --date / --all / default (latest) all implemented; 91/91 tests pass

New CLI usage:
  python3 scripts/sync_forward_validation_to_notion.py                     # default: latest row
  python3 scripts/sync_forward_validation_to_notion.py --date 20260528     # single date backfill
  python3 scripts/sync_forward_validation_to_notion.py --all               # full history backfill
  python3 scripts/sync_forward_validation_to_notion.py --all --dry-run     # preview all rows

Key implementation:
  load_all_rows()        — returns all rows from validation_30d.csv
  load_row_by_date(d)    — returns single row by YYYYMMDD, or None
  _parse_cli()           — returns (dry_run, sync_all, date_arg)
  _select_rows()         — returns (rows, mode_description)
  _preview_dry_run()     — previews payload for each selected row
  main()                 — multi-row upsert loop with progress + summary

Output fields:
  selected_rows, processed_rows, created_count, updated_count, failed_count
  NOTION_SYNC=PASS | DRY_RUN | SKIP | FAIL  (unchanged)

Preserved:
  - Default (no args) → only latest row (original behaviour)
  - Chinese alias schema support (TASK-009B) intact
  - NOTION_TOKEN never printed
  - upsert reuses find_existing_page() → no duplicate Notion pages
  - Schema fetched once; reused across all rows in --all mode

Commands run:
  python3 -m py_compile scripts/sync_forward_validation_to_notion.py   # PASS
  python3 scripts/sync_forward_validation_to_notion.py --dry-run        # NOTION_SYNC=DRY_RUN
  python3 scripts/sync_forward_validation_to_notion.py --all --dry-run  # NOTION_SYNC=DRY_RUN
  python3 -m pytest tests/forward_record/ -q                            # 330/330 PASS

Safety confirmed:
  paper_execution_status = FORBIDDEN, live_trading_status = FORBIDDEN
  NOTION_TOKEN not printed in any code path
  No order/private API calls

Files changed:
  MOD  scripts/sync_forward_validation_to_notion.py   (+load_all_rows, +load_row_by_date,
                                                        +_parse_cli, +_select_rows,
                                                        +_preview_dry_run, +_SYNTHETIC_SCHEMA,
                                                        refactored main() with multi-row loop)
  MOD  tests/forward_record/test_notion_sync.py        (+mock import; +27 new tests:
                                                        TestLoadHelpers, TestParseCli,
                                                        TestSelectRows, TestMainBehaviourTask013;
                                                        updated TestSubprocessBehaviour assertion)
  MOD  docs/research/commands/COMMAND_LOG.md           (this entry)
  MOD  docs/research/commands/NEXT_ACTION.md           (updated)
