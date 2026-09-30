---
name: write-rfc
description: Turn a completed interview into an RFC document in DECISIONS/ and request human review. Use after the interview skill, before any spec.
---

# Write the RFC

## How to ask the user anything (mandatory)
**Every question to the user goes through the `AskUserQuestion` tool. Never write questions in your reply text, and never end a reply with a list of questions.** The user answers by selecting, not by typing paragraphs.
- Up to 4 questions per call, each with 2–4 concrete options that *you* derived from context (the code, the docs, common practice). Put your recommended option first and label it "(Recommended)". The tool adds "Type something" and "Chat about this" itself.
- One short `header` per question (≤12 chars); the question is ONE sentence. Each option: a label of at most 5 words and a description of what happens if chosen (at most 15 words); your recommendation first with its reason. Use `multiSelect` when choices are not mutually exclusive.
- Ask, wait for the answers, write them into the document immediately, then ask the next round. Repeat until nothing is unknown. Do not batch everything into one giant list or stop and hand the questions back.
- Options are proposals, not facts: record what the user *selected or typed*, nothing more. If they choose "Chat about this", discuss, then ask again.
- If `AskUserQuestion` is not loaded yet, load it first with `ToolSearch` query `select:AskUserQuestion`, then call it. Only if the tool truly does not exist in this session (e.g. non-interactive `-p` mode) may you fall back to plain text, and then ask at most one short round, numbered.
- Confirmations count as questions too ("Is this PROJECT.md right?" → ask with options: Looks right / Change something).

An RFC records **a decision** — the need, the proposal, the alternatives and the objections — so
that the people it touches can sign it. It is the input to the spec.

1. Confirm the interview is complete (the user said "yes, that's it"). If not, go back to **interview**.
2. Create it (or open the draft the interview already created — never start a second one): `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" new-rfc <short-slug> --title "<title>"`
   (creates `DECISIONS/RFC-000N-slug.md` at the workspace, or the repo if standalone).
3. Fill every section from the interview. §3 is the Q&A log. Be concrete about behaviour; leave code out.
4. **Classification.** If the change crosses a repo boundary, set `classification: api`, fill §8
   (use **write-contract**) and set `signoffs_required` to the number of leads it touches. Otherwise `internal`.
4b. If it replaces an earlier decision set `supersedes: [RFC-000N]`; if it merely relates, `related_rfcs: [...]`. State in §7 which existing features it extends, amends or depends on.
5. Check it against CONSTITUTION.md and fill the constitution check in §7. If it conflicts, say so in the RFC.
6. Anything still unknown stays an unresolved marker in §10 — never guess. Approval is blocked while any remain.
7. Add a row to `DECISIONS/README.md` (state: draft).
8. Tell the user the file path, summarise it in five lines, and ask them to review it and run
   `/groundwork-specflow:approve RFC-000N`. **Stop.** Do not start the spec until it is approved.

If the user requests changes, edit the RFC; the earlier approval (if any) goes stale automatically and
must be given again.

Finally run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" check` and fix every error it reports for this document before asking the user to review.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
