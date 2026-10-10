---
name: implement
description: Implement the active feature task by task, keeping docs in sync and giving the user a manual test. Use when spec, plan, tasks and evals are complete and the gate allows code.
---

# Implement

`python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" status` must show every pipeline step ticked. If a hook denies an edit, do the
step it names; do not try to route around it (shell redirects, other tools) — that is a violation.

- **Other skills are tools, not a shortcut.** Design/frontend/testing skills (e.g. `frontend-design`) may be used here, in this step, to *realise the approved spec* — every choice must trace to a requirement in it. If such a skill was loaded before the spec was approved, stop and triage: it does not exempt you from the interview → RFC → spec path, and writing files by shell is gated like the Write tool.
- Respect relationships: `groundwork.py deps <feature>` shows what this depends on (must be implemented) and what depends on it. Changing behaviour other features rely on means updating and re-approving the affected specs first.
- Work **one task at a time**: mark it `[~]`, do it, run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" verify` (format, lint, types, tests; `--fix` repairs formatting first), verify "Done when",
  mark it `[x]`. Never mark done with a failing or skipped check; report failures with their output. Never weaken a lint rule, add an ignore or skip a test to get green.
- Follow the coding rules in AGENTS.md → *Code quality* (the **code-quality** skill explains them): reuse before writing, smallest change, no swallowed errors, validate input at entry points, dependencies only via the package manager, comments say why.
- **Python: use `uv` for everything** — `uv add`/`uv add --dev` to add packages, `uv sync`, `uv run <cmd>`; never `pip install`, `python -m pip`,
  `python -m venv` or hand-edited `uv.lock`. (Legacy `requirements.txt` project you weren't asked to migrate: `uv pip`.)
- Follow ARCHITECTURE.md, CONSTITUTION.md and the pinned contract. Use the repo's existing patterns and vocabulary.
- **Put each file where the code layout says** (`groundwork.py layout`, **code-layout** skill). Standard layout: no SDK, network, database or env access outside `connectors/` and `config/`; core never imports connectors; no `utils`/`helpers`/`common` folders. Repo that keeps its own structure: put new code where the same kind of code already lives, copy its patterns, and never restructure or move existing code. `check --strict` reports layout breaks. **Credentials:** read them only from environment variables, never write one into a file; a new variable goes into `.env.example` (name only) in the same change. The session start lists the map (folder: what it holds; outside systems and where they are called): go to the folder it names instead of searching the repo, and open `CODEMAP.md` for entry points, settings and tests. If the context says the map is MISSING or out of date, run `groundwork.py codemap` before the first edit; after adding, moving or removing a folder or calling a new outside system, run `groundwork.py codemap` and describe new folders in its Holds column, in the same change.
- If reality contradicts the spec or plan, **stop** and use the discovery protocol in the **write-plan** skill: state the evidence, ask the user which reading is right (picker), amend the upstream document with a dated `## Changes` line saying what changed and why, get it re-approved, re-verify the downstream documents, `groundwork.py plan-sync` — then continue. Never leave a spec doubt as a chat footnote and never decide it yourself.
  Behaviour change ⇒ spec change in the same change.
- Update ARCHITECTURE.md / CONTRACTS/ / AGENTS.md in the same change if you altered what they describe, then run `groundwork.py confirm <doc>`.
  Run `groundwork.py fresh` before you finish; if it reports stale documents, use the **refresh** skill. A feature that `amends` or
  `extends` a baseline, or touches files a baseline's Evidence table cites, shows that baseline as REVIEW: update its Evidence rows
  (and its requirements, re-approved, if behaviour changed), then `groundwork.py confirm --baseline <slug>`.
- Before declaring done, run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" check --strict` and fix every finding: it verifies the documents
  conform to the standard and that every FR has a task and every AC an evaluation.
- Any question for the user (a spec/plan contradiction, a choice) goes through `AskUserQuestion`, never as prose.
- Don't commit or push unless asked.

## Always end with a manual test
When done (or at each meaningful milestone) tell the user, concretely: what to run, what to click/curl,
what output to expect, and how to see a failure case. Use/extend the spec's §8. Say plainly what you verified
and what you did not.

When the feature's tasks are done record it: `groundwork.py record implemented --ref <feature> --via claude-code` (the person is the git identity of the human you work for). Commit messages carry `Refs: <NNN-slug>` so `groundwork.py who` can list everyone who touched it.
Before you stop for any reason, leave a trail: `groundwork.py note "<where I stopped; next action>"`. Then continue with **handover**.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
