# docs/archive

Frozen historical logs from the 2026-H1 development cycle.

## Contents

| File | Original Location | Lines |
|---|---|---|
| COMMAND_LOG_2026H1.md | docs/research/commands/COMMAND_LOG.md | 11,016 |
| NEXT_ACTION_HISTORY_2026H1.md | docs/research/commands/NEXT_ACTION.md | 10,001 |
| CLAUDE_REVIEW_LOG_2026H1.md | docs/research/CLAUDE_REVIEW_LOG.md | 1,951 |

## Rules

- These files are **frozen**. Do not append new entries.
- Do not load these files during normal AI sessions. They are too large
  (~23,000 lines total) and contain only completed task history.
- Use `git log` and `git blame` for ordinary development history.
- If you need to reference a specific historical task decision, search the
  relevant archive file by task ID.
- New task tracking goes through `docs/CURRENT_STATE.md` and conversation
  context, not through append-only logs.
