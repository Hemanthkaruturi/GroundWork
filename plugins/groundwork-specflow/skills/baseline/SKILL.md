---
name: baseline
description: Document behaviour that already exists as baseline specs (origin: baseline), and classify legacy specs brought in by adopt-specs. Use during bootstrap of an existing repo, when the context lists DOCUMENTATION REVIEW items, when a feature touches behaviour no spec covers, or when a bug has no requirement to cite.
---

# Baseline existing behaviour

A **baseline** is a spec for what the system already does. It is history, not work: no RFC, no tasks, never in flight. Once a person approves it, a feature can `extend` or `amend` it and a bug can cite its requirements. An **imported** spec (`origin: imported`) is a legacy document brought in by `adopt-specs`; it is a reference, not an approved requirement, until a person classifies it.

Two rules above all: **observation comes from code and tests; intent comes from the user or reliable existing documents.** And **never canonise a defect**: a guarantee the user confirms but the code breaks goes under *Known discrepancies* with a bug reference.

## How to ask the user anything (mandatory)
**Every question to the user goes through the `AskUserQuestion` tool. Never write questions in your reply text, and never end a reply with a list of questions.** The user answers by selecting, not by typing paragraphs.
- Up to 4 questions per call, each with 2–4 concrete options that *you* derived from context (the code, the docs, common practice). Put your recommended option first and label it "(Recommended)". The tool adds "Type something" and "Chat about this" itself.
- One short `header` per question (≤12 chars); the question is ONE sentence. Each option: a label of at most 5 words and a description of what happens if chosen (at most 15 words); your recommendation first with its reason. Use `multiSelect` when choices are not mutually exclusive.
- Ask, wait for the answers, write them into the document immediately, then ask the next round. Repeat until nothing is unknown. Do not batch everything into one giant list or stop and hand the questions back.
- Options are proposals, not facts: record what the user *selected or typed*, nothing more. If they choose "Chat about this", discuss, then ask again.
- If `AskUserQuestion` is not loaded yet, load it first with `ToolSearch` query `select:AskUserQuestion`, then call it. Only if the tool truly does not exist in this session (e.g. non-interactive `-p` mode) may you fall back to plain text, and then ask at most one short round, numbered.
- Confirmations count as questions too ("Is this PROJECT.md right?" → ask with options: Looks right / Change something).

In a non-interactive session: persist the evidence and the open questions (`groundwork.py capability set <cap> next_action="…"`, `groundwork.py note`), and stop. Never infer answers, confirm intent or approve anything because the user is unavailable.

## Modes
- **Bootstrap** (an existing repo): steps 1–6, for the capabilities the user selects now. Everything else is recorded as deferred.
- **Lazy** (from the interview or fix-bug skill): the touched behaviour has no usable baseline → do steps 3–6 for *that capability only*, get it approved, then resume the feature or bug. Do not audit the whole repo. While in this substep you may edit the baseline spec and the capability index; everything else stays confined to the RFC draft or bug record.
- **Legacy specs** (the context lists imports awaiting classification): step 2, then step 3 per document.

## 1. Inventory the capabilities (bootstrap)
Read `.groundwork/discovery.json`, `CODEMAP.md`, the README and existing docs. `discovery.json` → `capability_candidates` already clusters what the code shows: one candidate per route prefix (`surface.http`), per CLI command file (`surface.cli`) and per worker or job file, each with its evidence files, a *suggested* lifecycle and a note on what is unconfirmed; `scan.unsupported` says what the regex scan cannot see (dynamic routes, mounted prefixes, unlisted frameworks). Treat them as a starting list, not as the inventory: merge route groups into business capabilities, split what the code lumps together, and add what the scan missed. Identify entry points, supported workflows, consumers, and **current versus legacy surfaces** (a README often says which; never turn a historical folder or a roadmap item into a current capability).
Propose a capability list with `AskUserQuestion` (multi-select): business capabilities, not route groups; one capability can span routes, a worker and a CLI. Ask the user to correct boundaries and the lifecycle label of each (active · legacy · retired · planned · uncertain). Record every confirmed capability:
`python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" capability set <cap> title="…" lifecycle=active sources=path/a.py,path/b.py rationale_ref=docs/x.md`
Then ask which to baseline **now**. Recommend core workflows and paths where failure costs money, loses data, breaks isolation or breaks a consumer. "None for now" is a valid answer; the deferred ones stay visible in `specs/README.md` and in the session context.

## 2. Legacy specs: import, then classify
`python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" adopt-specs --dry-run` lists every spec directory without GroundWork metadata: title, original status, companions, task counts, markers, section gaps. Then `adopt-specs` (all) or `adopt-specs <slug …>` imports them as `origin: imported`, `adoption_state: pending` — bodies untouched, nothing approved. Tell the user which ones the original tool did **not** mark finished; an "Approved" label records accepted intent, not that every requirement was implemented.
For each import, after step 3, classify with the user (picker):
- **baseline** — implemented behaviour, worth keeping as the reference: `adopt-specs --classify baseline <slug> --capability <cap>`. Then reconcile the body (step 4): append the sections a baseline needs; legacy headings may stay.
- **planned** — unfinished work to continue through the normal path: `adopt-specs --classify planned <slug> --capability <cap>`; its missing RFC is an explicit migration step, never an invented historical decision.
- **archived** — keep as a reference, never cite: `adopt-specs --classify archived <slug>`.
- **mixed** — split: the implemented scope becomes a baseline, the rest a planned feature or archive. Preserve requirement ids and links where you can; do not copy unfinished promises into a baseline.
Add `--dry-run` to preview a classification without changing the spec or its capability links. Adoption reports symlinked inputs instead of following them; resolve these with the user before importing.

## 3. Investigate and interview, per capability
Read the code, tests and docs for the capability first. Then present a short evidence-backed account of what happens today and ask about what the evidence cannot settle, a round at a time:

| Topic | Settle | Goes to |
| --- | --- | --- |
| Purpose | whose problem, what outcome matters | §1–2 (and PROJECT.md if broader) |
| Rationale | why this approach; which cost, latency, operational or integration constraints mattered | Intent and rationale (ARCHITECTURE, or a retrospective ADR via `new-adr --retrospective` when the choice is broader than one capability) |
| Intent | is this behaviour deliberate, temporary, a workaround or a defect | FR/AC or Known discrepancies |
| Preservation | what future changes must keep working, including failures and isolation | FR/NFR/AC |
| Direction | which limitations are accepted; which belong to future work | §9 Out of scope; capability lifecycle |
| Ownership | who confirms expectations and supports it | `owner`, `support`, PROJECT.md people table |

Existing rationale in code comments or docs counts as a source: confirm it still governs instead of asking the user to reconstruct it. Record every answer immediately in the spec's *Intent and rationale* table with its effect (Confirmed · Tension · Open decision · Doc update · Out of scope). Before a spec exists, or while an imported body must remain untouched, stage the answers in the capability record:
`groundwork.py capability set <cap> 'interview_notes=[{"question":"Why this approach?","answer":"Cost and latency","source":"Confirmed reviewer","effect":"Confirmed"}]'`
The argument is a JSON array of entries with `question`, `answer`, `source` and `effect`; repeated entries are kept once and later rounds append without replacing earlier answers. Read `.groundwork/capabilities.json` when resuming. Move the staged answers into the spec body before approval; capability notes do not satisfy approval requirements.
If the user corrects your observation, investigate the discrepancy before writing the requirement. If docs, tests and code disagree, show the conflict and ask which expectation governs; never pick the one that makes onboarding easier.

## 4. Draft the baseline
New capability: `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" new-baseline <slug> --title "…" --capability <cap>` creates `specs/NNN-slug/spec.md` from the baseline template (spec only; the active feature is unchanged). Fill the nine sections for **what exists today**, in domain language, then:
- **Known discrepancies**: `- [ ] **D1** — <guarantee> — observed: … — bug: bugs/NNN-slug` for each confirmed guarantee the code breaks (record the bug with `new-bug` if none exists). `_None known._` otherwise.
- **Evidence**: one row per FR/NFR/AC — implementation paths and symbols, tests or observations, verification state (`inspected` · `executed/passed` · `executed/failed` · `not verified`), date. *Inspected is not passed.* Run the repo's normal tests where cheap and safe; never make paid provider calls, deploy, or mutate production to complete a row. Say what you did not verify.
- `Historical rationale unknown` is valid text when nobody knows why. Unknown **expected behaviour** is `[NEEDS CLARIFICATION: …]` and blocks approval; narrow the baseline to settled behaviour and leave the rest explicitly deferred rather than claim it.
Reconciled import: keep the body, append `## Manual test` (if absent), `## Intent and rationale`, `## Known discrepancies`, `## Evidence` and `## Changes` after the existing sections. Approval-critical behavioural content must be **inside the spec body**; required metadata such as the owner stays in front matter. A note in the capability index is not covered by the approval.
Record the owner: `groundwork.py record owner --ref <NNN-slug> --who "<name>"`. Run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" check` and fix every error on the document.
**Record the source review.** Once the Evidence table names real files and you have compared the baseline with them: `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" confirm --baseline <NNN-slug>`. It snapshots only the files the Evidence table cites (not the whole repo), so a later change to one of them flags the baseline for review. It records nothing about approval, and it refuses an unfinished baseline, evidence with no allowed existing file, or a scan over 300 files (cite narrower paths). Missing or excluded citations remain review warnings after confirmation; they cannot become CURRENT until resolved.

## 5. Read back, then ask for approval
Read back purpose, observed behaviour, intended guarantees, accepted limitations, known discrepancies and coverage gaps (picker: Looks right / Change something). "Is this how it behaves today?" alone is not enough. Then ask the user to run `/groundwork-specflow:approve specs/NNN-a/spec.md specs/NNN-b/spec.md …` — one command, several paths, each recorded separately; if any fails its check, none is recorded. **You cannot approve.** Only an approved, unchanged baseline can be cited by a feature or a bug.

## 6. Finish
`python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" capabilities` regenerates the table in `specs/README.md`. Report: which capabilities are baselined, which are deferred, which imports are still pending. Deferred coverage is never presented as coverage. Foundation confirmation (`groundwork.py confirm`) does not imply baseline approval.

## Later: keeping baselines true
A feature that changes existing behaviour **amends** the baseline: update its requirement text, add a dated `## Changes` line naming the feature, get it re-approved, update the Evidence rows with the implementation. An **extension** specifies only its delta plus what it must preserve. A bug fix refreshes the discrepancy (`- [x]`) and the evidence. Nothing here edits code: a baseline never repairs anything, passes a test or grants an approval.
**Source drift.** `groundwork.py fresh` lists each baseline as CURRENT, REVIEW (a cited file changed or disappeared) or UNREVIEWED; the session context shows "source review needed" and `check` warns (GW052). Drift is a signal, not proof a requirement changed: read the changed files against the FR/AC. Unchanged behaviour → update the Evidence rows (date, verification) where needed; any body edit needs a dated Changes entry and human re-approval, then `confirm --baseline <slug>`. Changed behaviour → amend the spec with a dated `## Changes` line, ask the user to re-approve, then `confirm --baseline`. A feature that relates to a baseline under review is accepted with a warning (GW077), never blocked.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
