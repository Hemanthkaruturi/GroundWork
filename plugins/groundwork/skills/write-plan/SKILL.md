---
name: write-plan
description: Write plan.md (how) for the active feature, citing the spec's requirement ids. Use after the spec is approved.
---

# Write the plan

## How to ask the user anything (mandatory)
**Every question to the user goes through the `AskUserQuestion` tool. Never write questions in your reply text, and never end a reply with a list of questions.** The user answers by selecting, not by typing paragraphs.
- Up to 4 questions per call, each with 2–4 concrete options that *you* derived from context (the code, the docs, common practice). Put your recommended option first and label it "(Recommended)". The tool adds "Type something" and "Chat about this" itself.
- One short `header` per question (≤12 chars); the question is ONE sentence. Each option: a label of at most 5 words and a description of what happens if chosen (at most 15 words); your recommendation first with its reason. Use `multiSelect` when choices are not mutually exclusive.
- Ask, wait for the answers, write them into the document immediately, then ask the next round. Repeat until nothing is unknown. Do not batch everything into one giant list or stop and hand the questions back.
- Options are proposals, not facts: record what the user *selected or typed*, nothing more. If they choose "Chat about this", discuss, then ask again.
- If `AskUserQuestion` is not loaded yet, load it first with `ToolSearch` query `select:AskUserQuestion`, then call it. Only if the tool truly does not exist in this session (e.g. non-interactive `-p` mode) may you fall back to plain text, and then ask at most one short round, numbered.
- Confirmations count as questions too ("Is this PROJECT.md right?" → ask with options: Looks right / Change something).

Precondition: spec.md is approved. Read the spec, the repo's ARCHITECTURE.md and the code you will touch.

Fill `specs/<active>/plan.md`. (Python projects: dependencies and commands in the plan use `uv`, never pip.) It is the **how**: modules and files, data model and migrations, interfaces
(pin the CONTRACTS/ version if cross-repo), failure modes, test strategy (which layer proves which AC), rollout and
rollback, constitution check.

- Cite `FR-n`/`NFR-n` next to every decision. A decision with no requirement behind it is scope creep.
- Follow the patterns already in the repo; say where you deliberately depart and why.
- Anything you cannot decide alone: `[NEEDS CLARIFICATION: …]` and ask.
- If the plan reveals the spec is wrong or incomplete, fix the spec (it will need re-approval) — never diverge silently.


## When planning reveals a problem with the spec (the discovery protocol)
The spec is **upstream** of the plan: **a plan never changes a spec on its own.** If, while planning, you find an ambiguity, contradiction, impossibility or gap in the spec, **stop planning that part** and follow this:
1. **Say what you found**, with the evidence (the numbers, the two clauses that clash, the case nobody specified).
2. **Classify it:** *wording* (same meaning, clearer words) · *ambiguity or contradiction* (two readings are possible) · *new scope or a different decision* (the RFC's decision would change → RFC path, not a spec tweak).
3. **Ask the user which reading is right** — via the picker, with each reading as an option and what it implies. **Do not pick the reading yourself and edit the spec to match.** Every doubt you cannot resolve stays in the spec as `[NEEDS CLARIFICATION: …]` (which blocks approval) — **never as a footnote in chat**.
4. **Only then amend the spec** to say exactly what the user chose, and add a dated line under its `## Changes` section (after the required sections) recording *what changed and why* ("found while planning: …; user chose …"). Re-approval is refused without that line.
5. Tell the user the spec needs re-approval (`/groundwork:approve <spec>`). Until they do, treat everything downstream as **provisional**.
6. After re-approval: re-read the plan, tasks and evals against the *current* spec, fix what no longer matches (tell the user what you changed), then run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" plan-sync`. Code stays blocked until you do — the plan is pinned to the spec version it was written for.

Remove every `[TODO…]` you resolved. When plan.md is finished and the spec is approved, run `groundwork.py plan-sync` to pin it to that spec version, then continue to **write-tasks**.

Finally run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" check` and fix every error it reports for this document before asking the user to review.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
