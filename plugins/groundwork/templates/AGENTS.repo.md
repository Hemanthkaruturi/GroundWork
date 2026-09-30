# AGENTS.md — {{name}}

Instructions for coding agents in this repository.

## Read before you write anything
1. The workspace above, if any: `PROJECT.md`, `ARCHITECTURE.md`, `CONSTITUTION.md`, `CONTRACTS/` ({{workspace}}).
2. `ARCHITECTURE.md` in this repo — the internals of this service.
3. The spec for the feature you are touching: `specs/NNN-slug/`.

## Commands
**If this project uses Python: use `uv` — never `pip`.** `uv add <pkg>` / `uv add --dev <pkg>` to add dependencies, `uv sync` to install,
`uv run <cmd>` to run anything (tests, linters, the app), commit `uv.lock` and never edit it by hand; no `python -m venv`, no `pip install`.

[TODO: setup, run, test, lint/typecheck — exact commands, and which one must pass before "done"]

## Conventions
[TODO: language/style rules, folder layout, error handling, anything an agent gets wrong without being told]

## Process (enforced by the groundwork plugin)
Interview → RFC → human approval → spec → plan → tasks → evals → implement → handover.
Change behaviour ⇒ change the spec in the same change. Do not commit or push unless asked.
