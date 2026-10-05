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

## Where code lives
**Read `CODEMAP.md` before searching the code.** It lists every code folder and what it holds, where outside systems (LLMs,
databases, APIs) are called, where settings are read, and the entry files and tests. After adding, moving or removing a
folder, run `groundwork.py codemap` and describe any new folder in its Holds column.
`groundwork.py layout` shows the layout decision: the GroundWork standard folders, or "keep" — the repo's own structure,
where new code goes next to code of the same kind and copies its patterns.

## Conventions
[TODO: language/style rules, folder layout, error handling, anything an agent gets wrong without being told]

## Code quality
Each repo records its toolchain (`groundwork.py quality`). Run `groundwork.py verify` after every change and fix what fails;
never weaken a rule, add an ignore or skip a test to make it pass. `quality init` or `quality keep` fills this section with
the repo's commands and the coding rules every agent follows.

## Process (enforced by the groundwork plugin)
Interview → RFC → human approval → spec → plan → tasks → evals → implement → handover.
Change behaviour ⇒ change the spec in the same change. Do not commit or push unless asked.
