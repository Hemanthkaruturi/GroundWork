---
name: bootstrap
description: Create or complete the foundation documents (PROJECT.md, ARCHITECTURE.md, CONSTITUTION.md, AGENTS.md, CONTRACTS/, DECISIONS/) for the current workspace or repo. Use when the session context says foundation docs are missing or unfinished, or when starting a new project.
---

# Bootstrap the foundation

## How to ask the user anything (mandatory)
**Every question to the user goes through the `AskUserQuestion` tool. Never write questions in your reply text, and never end a reply with a list of questions.** The user answers by selecting, not by typing paragraphs.
- Up to 4 questions per call, each with 2–4 concrete options that *you* derived from context (the code, the docs, common practice). Put your recommended option first and label it "(Recommended)". The tool adds "Type something" and "Chat about this" itself.
- One short `header` per question (≤12 chars); the question is ONE sentence. Each option: a label of at most 5 words and a description of what happens if chosen (at most 15 words); your recommendation first with its reason. Use `multiSelect` when choices are not mutually exclusive.
- Ask, wait for the answers, write them into the document immediately, then ask the next round. Repeat until nothing is unknown. Do not batch everything into one giant list or stop and hand the questions back.
- Options are proposals, not facts: record what the user *selected or typed*, nothing more. If they choose "Chat about this", discuss, then ask again.
- If `AskUserQuestion` is not loaded yet, load it first with `ToolSearch` query `select:AskUserQuestion`, then call it. Only if the tool truly does not exist in this session (e.g. non-interactive `-p` mode) may you fall back to plain text, and then ask at most one short round, numbered.
- Confirmations count as questions too ("Is this PROJECT.md right?" → ask with options: Looks right / Change something).

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" status`. If the level is **unknown**, stop and ask
   the user: is this a repo (`git init`) or a workspace holding several repos (`groundwork.py mark-workspace`)?
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" init` (add `--dry-run` first if the project already has documents).
   It creates only what is missing, records the standard version, and writes **`.groundwork/discovery.json`**: evidence about the existing
   codebase (languages, manifests and their scripts/dependencies, entry points, tests, CI/infra, existing docs, git history and top contributors).
   **Read it before asking anything** — never ask what the evidence already answers, and never present evidence as a decision.
   - Existing foundation documents that lack required sections: ask (`AskUserQuestion`) whether to add the missing sections, then run `init --retrofit`
     (additive; it never rewrites your text).
   - `adoptable.adr_dir` → ask to bring those ADRs into `DECISIONS/` (keep content; name `ADR-NNNN-slug.md`; list them in `DECISIONS/README.md`).
   - `adoptable.constitution` / existing rules → offer to base `CONSTITUTION.md` on them.
   - `adoptable.agent_instructions` (`CLAUDE.md`, `.cursorrules`) → fold the still-true conventions into `AGENTS.md`; never delete the originals.
   - `git.top_authors` are *candidates* for "who works on what": offer them as options and let the user confirm roles; never assert ownership.
3. Fill the files **with the user**, one document at a time. The rule that matters most: **never invent
   business facts.** Ask (with `AskUserQuestion`, a round at a time); then write what they said.

**Keep the template's headings and order** (a reader must find "Who works on what" in the same place in every project); replace each `[TODO]` with the user's words, or leave it as a `[NEEDS CLARIFICATION: …]` if they haven't said.

## PROJECT.md — business, not technical
Ask: what is this, for whom, what pain does it remove, what does success look like, what is in/out of
scope, who are the stakeholders, **who works on what and how to reach them**, what are the repos, what words
have special meaning (glossary). If the user says "you decide", propose a draft and mark it for their confirmation.

## ARCHITECTURE.md — technical, high level
- **Existing code:** explore first (manifests, entry points, CI, Dockerfiles, infra files) and draft from
  evidence; ask the user only about what the code cannot tell you (why, where it deploys, who owns what).
- **New project:** ask about stack, data stores, deployment target and pipeline, environments, auth,
  integrations. Record decisions as decisions.
- Workspace level: how the repos fit together and how data flows between them. Repo level: this service's internals.

## CONSTITUTION.md — few rules, checkable
Draft 3–7 principles and the guardrails ("never…") *from what the user has told you*; propose, don't impose.
Each rule must be something a reviewer could check in a diff.
**Existing code: start from evidence.** `discovery.json` → `rules.candidates` lists rule-shaped lines harvested from the README, AGENTS.md, CLAUDE.md, CONTRIBUTING, an existing constitution and docs (each with its source and line), `rules.ci_gates` the commands CI already runs, and `rules.conflicts` pairs that look contradictory. Offer them with `AskUserQuestion` (multi-select, grouped: principles · guardrails · quality gates), the CI gates as the default quality gates, and ask which should govern future work and why. Classify what the user keeps: an accepted constraint goes in; a temporary workaround or a preference does not. An incidental coding pattern is not a rule because it exists. Keep the original constitution file; say what was narrowed or replaced. In a repo inside a workspace, the workspace's CONSTITUTION owns the cross-repo rules.

## Code layout (once per repo)
Use the **code-layout** skill. `discovery.json` → `layout` shows whether the repo already has code, a guessed profile and root.
- **Existing code:** ask (`AskUserQuestion`) whether to migrate the code to the GroundWork standard layout or keep the current structure:
  **Keep current structure (Recommended)** — nothing moves; new code follows existing patterns · **Migrate to standard** — standard folders; existing code moves as planned work.
  Keep → `groundwork.py layout keep`, and describe the existing folders in ARCHITECTURE.md → *Code map*. Migrate → `groundwork.py layout init --profile <p> --root <dir>`, then `layout map` / `--legacy`. **Never move existing code during bootstrap.**
- **New repo:** ask the profile (service · cli · web · library), then `groundwork.py layout init --profile <p> --create`.
- **Workspace:** decide per repo (run it inside each repo).
- **Code quality toolchain (once per repo):** use the **code-quality** skill. Existing code: ask whether to adopt GroundWork's standard tools or keep the repo's own (**Keep own tools (Recommended)** — nothing reformatted; `groundwork.py quality keep` records its commands · **Adopt standard** — `quality init --create`; the formatter will rewrite files, so do it as its own change). New repo: `groundwork.py quality init --create`, then install the tools it names. Either way AGENTS.md gets a *Code quality* section.
- **Credentials:** `init` makes `.env` git-ignored. If `check` reports a committed `.env` or a key written into a file, tell the user plainly that it must be removed **and rotated**. Don't fix it silently.
- **Code map, always:** `init` writes `CODEMAP.md` from the code. Fill its **Holds** column (one line per folder, from what the code shows) and add notes. Run `groundwork.py codemap` again after the layout decision.

## Existing behaviour: baselines, legacy specs, deferred capabilities (existing code only)
An existing repo has behaviour nobody specified. This is a normal bootstrap step, not an afterthought — use the **baseline** skill:
- **Legacy specs** (`init` printed "legacy specs: N …", or `specs/` holds documents with no GroundWork front matter): `groundwork.py adopt-specs --dry-run`, then `adopt-specs`. They come in as `origin: imported`, pending — references, nothing approved. Tell the user which ones the original tool did not mark finished. Classify each with the user (baseline · planned · archived · split).
- **No specs:** propose a capability inventory from `discovery.json`, `CODEMAP.md`, the README and docs (business capabilities, current vs legacy surfaces), record it with `groundwork.py capability set …`, and ask which to baseline **now** (recommend core workflows and paths where failure costs money, loses data or breaks a consumer). "None for now" is allowed; the deferred ones stay visible in `specs/README.md`.
- For each selected capability: investigate, interview, draft the baseline (`new-baseline`), read it back, and ask the user to approve (several paths in one `/groundwork-specflow:approve`). Never canonise a defect: a confirmed guarantee the code breaks is a *Known discrepancy* with a bug reference.
- End with `groundwork.py capabilities` and say plainly what is baselined, what is deferred and what is still pending classification. Confirming the foundation docs does not approve any baseline.

## Contracts another repo already depends on (existing code only)
`discovery.json` → `surface.http` (route files, prefixes, mounted routers), `surface.schemas` (OpenAPI, proto, GraphQL) and `surface.api_docs` (API or integration docs) show what this repo *serves*. A route is not a consumer: only when the workspace ARCHITECTURE.md, an integration doc or a sibling repo's code names a consumer is there a boundary to write down. Then use the **write-contract** skill in as-built mode (`groundwork.py new-contract <provider>-<topic> --as-built --provider <repo> --consumers <a,b>`), draft only the consumed surface from the provider's code and docs, cite the evidence, name `provider_reviewer` and `consumer_reviewers`, and ask each to approve. Until every named reviewer has signed, say the contract is pending; never present it as a mutual commitment.

## Decisions found in the code (existing code only, optional)
`discovery.json` → `decision_leads` lists places to look: docs whose names suggest a decision or research, code comments that give a reason ("because", "instead of", "deliberately"), and commit subjects with a decision verb. **A lead is a topic, not a decision.** Offer at most five with `AskUserQuestion` (multi-select, plus "None"); never write ADRs in bulk. For each the user keeps, ask where the reason comes from (picker): **a document** (name it: `--source docs/x.md`) · **the user explains it now** (a retrospective explanation, labelled with their name and today's date) · **nobody knows** (`historical rationale unknown`, which is a valid answer). Then `groundwork.py new-adr <slug> --title "…" --retrospective [--source <path>]` and fill §1–5 only as far as the evidence supports; §3 starts with the `**Source:**` label. A commit subject never supplies the reason, the approver or the decision date (`decided_at: unknown` unless a document states it). `check` refuses a finished ADR without that label (GW019).

## AGENTS.md
**Python projects use `uv`, never pip.** Write the commands as `uv sync`, `uv run pytest` etc. (verify each by running it). If `discovery.json` shows
`python.other_managers` (pip requirements, poetry, pipenv), do **not** migrate silently: ask (`AskUserQuestion`: Migrate to uv (Recommended) / Keep current for now)
and record the answer in AGENTS.md.

Exact commands to set up, run, test and lint — verify each by running it. Conventions an agent gets wrong
without being told. Keep its *Where code lives* section pointing at `CODEMAP.md`.

## Finish
When every document is finished and the user has read PROJECT.md and ARCHITECTURE.md, run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" confirm` — it records the baseline that later detects drift.
Then ask the user (via `AskUserQuestion`) whether to install the git hook that runs the conformance check on every commit:
**Yes — errors block commits (Recommended)** / Yes, strict (warnings block too) / Yes, and vendor the engine so teammates and CI need no plugin / No. If yes, run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" hooks install [--strict] [--vendor]`.
Remove every `[TODO…]` you resolved. If something is genuinely unknown, leave the marker and tell the user
— the gate will keep blocking code until it is answered, which is intended. Then tell the user what you wrote
and ask them to read PROJECT.md and ARCHITECTURE.md; humans must be able to understand the system from these.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
