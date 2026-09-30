# AGENTS.md — workspace of {{name}}

Instructions for coding agents. Humans: read PROJECT.md first.

## Read before you write anything
1. `PROJECT.md` — what we build and why, and who to ask.
2. `ARCHITECTURE.md` — the boxes and their names.
3. `CONSTITUTION.md` — non-negotiable rules.
4. `CONTRACTS/` — what each repo promises the others.
5. `DECISIONS/` — RFCs (proposals, approved or not) and the ADRs they left behind.

## Tooling defaults
- Python repos use `uv` (`uv add`, `uv sync`, `uv run`) — never `pip`. Each repo commits its own `uv.lock`.

## Working across repos
- This is the **workspace**: it owns boundaries. Each repo owns its craft.
- Stay in the repo you were asked about. A change that needs another repo is a conversation,
  not a quiet cross-repo edit — say what the other repo needs and let the user decide.
- Anything two repos must agree on is settled here first (RFC, then CONTRACTS/), then built
  in each repo against a pinned contract version.

## Process (enforced by the groundwork plugin)
Interview → RFC → human approval → spec → plan → tasks → evals → implement → handover.
You cannot approve documents; only the user can, with `/groundwork-specflow:approve`.

## Repositories
[TODO: name — path — purpose, one per line]
