---
name: write-contract
description: Write or update a cross-repo contract in the workspace's CONTRACTS/ folder (shapes, examples, failure semantics, version). Use when an RFC is classified api or a change alters what one repo promises another.
---

# Write a contract

## How to ask the user anything (mandatory)
**Every question to the user goes through the `AskUserQuestion` tool. Never write questions in your reply text, and never end a reply with a list of questions.** The user answers by selecting, not by typing paragraphs.
- Up to 4 questions per call, each with 2–4 concrete options that *you* derived from context (the code, the docs, common practice). Put your recommended option first and label it "(Recommended)". The tool adds "Type something" and "Chat about this" itself.
- One short `header` per question (≤12 chars); the question is ONE sentence. Each option: a label of at most 5 words and a description of what happens if chosen (at most 15 words); your recommendation first with its reason. Use `multiSelect` when choices are not mutually exclusive.
- Ask, wait for the answers, write them into the document immediately, then ask the next round. Repeat until nothing is unknown. Do not batch everything into one giant list or stop and hand the questions back.
- Options are proposals, not facts: record what the user *selected or typed*, nothing more. If they choose "Chat about this", discuss, then ask again.
- If `AskUserQuestion` is not loaded yet, load it first with `ToolSearch` query `select:AskUserQuestion`, then call it. Only if the tool truly does not exist in this session (e.g. non-interactive `-p` mode) may you fall back to plain text, and then ask at most one short round, numbered.
- Confirmations count as questions too ("Is this PROJECT.md right?" → ask with options: Looks right / Change something).

Contracts live in the **workspace** `CONTRACTS/<provider>-<topic>.md` (versioned), never only in code.
Both the provider's and consumer's leads sign the RFC §8 that produces it.

Each contract states: provider and consumers; **version** (semver) and changelog; every operation with request and
response **shapes**; at least one **real example** request/response per operation; **error and failure
semantics** (codes, retries, idempotency, timeouts); auth/tenancy; compatibility rules (what counts as breaking →
new version, never a silent change).

Consumers pin it: the repo records `contract.lock` with the version it honours. A shipped contract is never
edited in place in a breaking way — add a version.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
