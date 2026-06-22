"""TASK-014BY -- offline strategy-selection diagnostic and challenger-design package.

Read-only, deterministic, offline analysis of the completed 30-day Forward
Validation artifacts and existing OOS/reference artifacts. It never modifies the
active V1 strategy logic, never mutates the running Pilot state, never sends a
Bybit order, and never calls Bybit / Notion / Discord. It reuses the repository's
canonical metric implementations (src/metrics/performance.py) rather than
duplicating financial formulas, and it never fabricates unavailable data.
"""

TASK_ID = "TASK-014BY"
