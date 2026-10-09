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

## Creating one
`python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" new-contract <provider>-<topic> --title "…" --provider <repo> --consumers <a,b>` writes `CONTRACTS/<provider>-<topic>.md` in the workspace (a standalone repo gets its own `CONTRACTS/`). Its front matter carries `version` (semver; the date never goes in it), `signoffs_required: 2`, and the humans who review it: `provider_reviewer` and `consumer_reviewers`. Fill them with the picker from PROJECT.md's people table.

## As-built contracts (a surface others already consume)
Add `--as-built`: the contract gets `origin: baseline` and `observed_at`, and describes the surface **as it is**, not as designed. Read any existing contract or integration doc first (`discovery.json` → `surface.api_docs`, `surface.schemas`). Draft only the consumed surface: operations with shapes and real examples, errors, retries and idempotency, timeouts, auth and tenancy, compatibility rules. Compare the provider's code with the consumer's code or tests when they are in the workspace; when they are not, write that limit down. An example copied from a doc is *unverified* until you ran it. Fill `## 7. Evidence` (claim · provider evidence · consumer evidence · verification · date). Preserve an existing version number; propose `1.0.0` only when none exists.

## Review and sign-off
Approval counts distinct signers (`signoffs_required`) and knows nothing about roles. Whether the provider and the consumer both reviewed is a **human procedure**: ask each named reviewer to run `/groundwork-specflow:approve CONTRACTS/<file>` themselves. `check` warns (GW047) while a named reviewer has not signed, and the session context lists the contract under DOCUMENTATION REVIEW; until then say it is *pending* and never present it as a mutual commitment. Future changes go through an `api` RFC, a new version and the same sign-offs.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
