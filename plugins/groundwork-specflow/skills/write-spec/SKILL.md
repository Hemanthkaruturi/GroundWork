---
name: write-spec
description: Create and fill the spec (what and why, numbered FR/NFR/AC, manual test) for a feature in a repo from an approved RFC. Use after the RFC is approved.
---

# Write the spec

## How to ask the user anything (mandatory)
**Every question to the user goes through the `AskUserQuestion` tool. Never write questions in your reply text, and never end a reply with a list of questions.** The user answers by selecting, not by typing paragraphs.
- Up to 4 questions per call, each with 2–4 concrete options that *you* derived from context (the code, the docs, common practice). Put your recommended option first and label it "(Recommended)". The tool adds "Type something" and "Chat about this" itself.
- One short `header` per question (≤12 chars); the question is ONE sentence. Each option: a label of at most 5 words and a description of what happens if chosen (at most 15 words); your recommendation first with its reason. Use `multiSelect` when choices are not mutually exclusive.
- Ask, wait for the answers, write them into the document immediately, then ask the next round. Repeat until nothing is unknown. Do not batch everything into one giant list or stop and hand the questions back.
- Options are proposals, not facts: record what the user *selected or typed*, nothing more. If they choose "Chat about this", discuss, then ask again.
- If `AskUserQuestion` is not loaded yet, load it first with `ToolSearch` query `select:AskUserQuestion`, then call it. Only if the tool truly does not exist in this session (e.g. non-interactive `-p` mode) may you fall back to plain text, and then ask at most one short round, numbered.
- Confirmations count as questions too ("Is this PROJECT.md right?" → ask with options: Looks right / Change something).

Precondition: the RFC is **approved** (`groundwork.py status` shows it). If not, stop and say so.

1. `cd` into the repo that will build it. Create: `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" new-feature <slug> --rfc RFC-000N`
   Declare relationships from the interview: `--extends X`, `--amends X`, `--depends-on X`, `--builds-against X` (comma-separated `NNN-slug` or `repo/NNN-slug`; none = independent).
   — this creates `specs/NNN-slug/{spec,plan,tasks,evals}.md` and makes it the active feature.
2. Read the RFC first: §2 (the need), §3 (every interview answer, and the read-back), §4 (the decided behaviour) and §9 (the boundary). The spec is derived from them: one FR for each behaviour the proposal commits to, each interview answer labelled *Confirmed* turned into the requirement it implies, and at least one AC per FR. Nothing in the spec may go beyond what the RFC decided; a behaviour the RFC never settled is a `[NEEDS CLARIFICATION]` marker or an amendment to the RFC, never an invention. Then read CONSTITUTION.md (repo and workspace): its guardrails bound what a requirement may ask for, and its quality gates say what "done" means. Fill **spec.md** only. Describe **what and why** in domain language: no class names, table schemas or library choices.
2b. **UI / visual changes are specified, not improvised.** Turn the interview's look-and-feel answers into checkable requirements: design tokens (colours, type scale, spacing), named screens/states covered (empty, loading, error), contrast ratios, responsive breakpoints, keyboard/focus behaviour, and what stays unchanged. Each becomes an FR/AC, and the Manual test lists the pages to open with what to see at each breakpoint. Design skills (e.g. frontend-design) come later, in the implement step, to realise exactly these requirements.
3. Number everything: `FR-n` (must…), `NFR-n`, `AC-n` (Given/When/Then, each citing the FR it proves).
4. **Manual test (§8) is mandatory:** exact steps a human can run to see it working, and what they should see.
5. **Cite the RFC; never copy it** (one owner per fact, STANDARD §4; `check` warns with GW092 when a sentence is repeated). §1 is one or two lines naming this repo's share of RFC §2. §9 lists only what this repo leaves out beyond RFC §9, else "As RFC-000N §9." Do not re-tell the need, the alternatives or the risks. A spec that will not fit on a page is usually two features.
6. Unknowns → `[NEEDS CLARIFICATION: …]`; ask the user; resolve; never guess.
7. The RFC's §7 holds the constitution check; the spec has none. If a requirement touches a rule the RFC did not consider, that is a discovery (the protocol in **write-plan**): say so, ask, and amend the RFC — never add a check section here.
7b. If the spec **amends** another feature: edit that spec now, add a dated line naming this feature under its `## Changes` section (after the required sections), and ask the user to re-approve it too. An extension specifies only its delta. When the target is a **baseline** (existing behaviour), also update its requirement text and state in this spec what must be preserved; the baseline must be approved and unchanged, or the relation is refused (GW076).
8. Ask the user to review and run `/groundwork-specflow:approve <path to spec.md>`. **Stop** until approved.

Finally run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" check` and fix every error it reports for this document before asking the user to review.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
