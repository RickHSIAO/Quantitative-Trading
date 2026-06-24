# Agent Project Instructions

## Session Startup

Read `docs/CURRENT_STATE.md` at the start of every project session.
Archived logs in `docs/archive/` and `.local/PROJECT_UPDATES.md` are
historical only — do not load by default; read only when explicitly requested.

## Codex Rules

- Only execute the task specified by Rick's latest direct chat instruction.
- Do not independently clear `BLOCKED` status.
- Do not independently mark tasks `DONE`.
- Complete implementation tasks by moving them to `REVIEW` when appropriate.

## Red Lines

- Do not modify strategy signals unless explicitly authorized.
- Do not modify ranking unless explicitly authorized.
- Do not modify universe selection unless explicitly authorized.
- Do not modify data-quality policy unless explicitly authorized.
- Do not modify immutable run outputs, including run008, unless explicitly authorized.
- Do not modify raw data unless explicitly authorized.

## Primary Registry Files

- `docs/CURRENT_STATE.md`
- `docs/research/commands/CLAUDE_COMMANDS.md`
- `docs/research/CODEX_TASK_QUEUE.md`
- `docs/research/CLAUDE_REVIEW_QUEUE.md`
