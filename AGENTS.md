# Agent Project Instructions

Codex must read `docs/research/commands/NEXT_ACTION.md` at the start of every project session.

## Codex Rules

- Only execute the task specified in `NEXT_ACTION.md` or Rick's latest direct chat instruction.
- If `NEXT_ACTION.md` status is not `READY`, do not start task work unless Rick explicitly authorizes it in the current chat.
- Do not use old TASK-002 artifacts or architecture:
  - `output/crypto_cost_stress.csv`
  - `scripts/crypto_cost_stress.py`
- Do not independently clear `BLOCKED` status.
- Do not independently mark tasks `DONE`.
- Complete implementation tasks by moving them to `REVIEW` when appropriate, not `DONE`.
- After completing an authorized task, update `docs/research/commands/COMMAND_LOG.md`.

## Red Lines

- Do not modify strategy signals unless explicitly authorized.
- Do not modify ranking unless explicitly authorized.
- Do not modify universe selection unless explicitly authorized.
- Do not modify data-quality policy unless explicitly authorized.
- Do not modify immutable run outputs, including run008, unless explicitly authorized.
- Do not modify raw data unless explicitly authorized.

## Primary Registry Files

- `docs/research/commands/NEXT_ACTION.md`
- `docs/research/commands/CODEX_COMMANDS.md`
- `docs/research/commands/COMMAND_LOG.md`
- `docs/research/CODEX_TASK_QUEUE.md`
- `docs/research/CLAUDE_REVIEW_QUEUE.md`
