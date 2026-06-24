# Claude Project Instructions

## Session Startup

Read only:

1. `docs/CURRENT_STATE.md`
2. `docs/ARCHITECTURE.md` — when the task involves architecture
3. `docs/TRADING_SAFETY.md` — when the task involves trading or execution safety
4. Files directly relevant to the requested code change

## Historical Context

- `docs/archive/` contains frozen 2026-H1 historical logs — do not load by default
- `.local/PROJECT_UPDATES.md` is local-only historical context (gitignored);
  read only when explicitly requested or for historical investigation
- Use `git log` / `git blame` for ordinary development history
- Do not write giant final reports into the local update log

## Task Rules

- Only run the task Rick specifies in the current chat
- Final review uses Opus; queue updates and drafts use Sonnet
- Do not mark tasks `DONE` without an explicit review verdict
- Do not update README, CURRENT_STATE, or CHANGELOG unless the task changes their stated truth

## Red Lines

- Do not modify strategy signals, ranking, universe, data-quality policy,
  immutable run outputs, or raw data unless the active workorder explicitly
  allows it
