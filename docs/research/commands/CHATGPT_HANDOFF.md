# ChatGPT Handoff

This file is the stable handoff point for ChatGPT advisor sessions.

## Startup

Read these files before giving project advice:

1. `docs/research/commands/NEXT_ACTION.md`
2. `docs/research/commands/COMMAND_LOG.md`
3. `docs/research/CODEX_TASK_QUEUE.md`
4. `docs/research/CLAUDE_REVIEW_QUEUE.md`
5. Relevant workorder or context packet named by `NEXT_ACTION.md`

## Advisor Rules

- If `NEXT_ACTION.md` status is not `READY`, advise only on decision framing, risk, or next-command wording.
- Do not assume old output files are official unless `NEXT_ACTION.md` or the task queue names them as official.
- For TASK-002, ignore `output/crypto_cost_stress.csv` and old `scripts/crypto_cost_stress.py` outputs.
- Distinguish clearly between verified facts from files and recommendations.
- Do not request agents to modify strategy, ranking, universe, data-quality policy, immutable run outputs, or raw data unless the active workorder explicitly allows it.

## Handoff Template

Use this shape when preparing the next command:

```text
Status:
Owner:
Task:
Canonical inputs:
Allowed actions:
Forbidden actions:
Expected outputs:
Review route:
```
