# Claude Project Instructions

Claude must read `docs/research/commands/NEXT_ACTION.md` at the start of every project session.

## Command Registry Rules

- If `NEXT_ACTION.md` status is not `READY`, do not execute tasks independently.
- Only run the task explicitly named in `NEXT_ACTION.md`, unless Rick gives a newer direct chat instruction.
- Final review uses Opus.
- Queue updates, summaries, readiness checks, and draft reviews use Sonnet.
- Do not mark tasks `DONE` without an explicit review verdict that allows it.
- Keep task red lines intact. Do not modify strategy signals, ranking, universe, data-quality policy, immutable run outputs, or raw data unless the active workorder explicitly allows it.

## Primary Registry Files

- `docs/research/commands/NEXT_ACTION.md`
- `docs/research/commands/CLAUDE_COMMANDS.md`
- `docs/research/commands/COMMAND_LOG.md`
- `docs/research/CODEX_TASK_QUEUE.md`
- `docs/research/CLAUDE_REVIEW_QUEUE.md`
