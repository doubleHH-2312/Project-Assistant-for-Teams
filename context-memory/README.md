# Context Memory

This directory is the concise operational memory for coding agents working on the
Project Assistant Tool. It is committed to Git and must never contain credentials,
private tokens, confidential customer data, or long raw logs.

## Read order

1. Repository `AGENTS.md`.
2. This file.
3. `current-handoff.md`.
4. `progress.md`.
5. Relevant decisions and risks.
6. Durable technical documentation linked from these files.

## Update rules

- Mark a task `IN_PROGRESS` before changing application code.
- Record exact verification commands and results before marking a task `DONE`.
- Keep `decisions.md` append-only; supersede decisions instead of rewriting history.
- Refresh `current-handoff.md` at the end of every implementation session.
- Keep entries brief and link to `docs/` for durable architecture, API, and runbooks.

## Boundary with `docs/`

`context-memory/` answers “where are we and what happens next?”. `docs/` answers
“how is the system designed and operated?”. Do not duplicate full specifications.

