---
name: refresh
description: Bring the foundation documents (PROJECT.md, ARCHITECTURE.md, AGENTS.md, CONSTITUTION.md — in the repo and in the workspace above it) back in line with reality after things changed, then confirm them. Use when the session says DOCS MAY BE STALE, when `groundwork.py fresh` reports stale/unconfirmed documents, when a feature is finished, or before ending any session that changed the stack, commands, components, repos or contracts.
---

# Refresh the foundation documents

Documents rot silently. This is how they are kept true — by anyone: you, a teammate, or another agent.

## Ask questions the right way
Every question to the user goes through the `AskUserQuestion` tool (load it with `ToolSearch select:AskUserQuestion` if needed) — selectable options, up to 4 per round, your recommendation first. Never put questions in reply text.

## Steps
1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" fresh`. It lists each document as FRESH, STALE, UNCONFIRMED or EDITED, with the reasons
   (e.g. "signals changed: package.json", "repos added: billing", "repo_arch changed: api", "not reviewed for 120 days").
   In a repo it also shows the workspace's documents, because work in this repo can make them stale.
2. For each stale/unconfirmed document, find **what actually changed** — read the named files and their diffs (`git log -p`/`git diff` on them;
   a snapshot has no history, so compare with the document's claims). Don't rewrite from scratch: edit only the sections the change touches,
   keep the standard's headings and order (STANDARD.md §4), and keep the document short.
3. Update by level:
   - **repo `ARCHITECTURE.md`** — components, stack, data flow, deployment, local development; the *why* is the user's, so ask if the code can't tell you.
   - **repo `AGENTS.md`** — exact commands; run each one to verify it still works.
   - **workspace `ARCHITECTURE.md`** — repos and how they connect; read each child repo's `ARCHITECTURE.md`, new RFCs in `DECISIONS/`, and `CONTRACTS/`.
   - **workspace `PROJECT.md`** — repos list, who works on what, scope; you cannot see people or business changes in code, so **ask the user**
     ("Anyone joined/left/changed ownership?", "Scope changed?" — options: No change / Yes, let me tell you).
   - **`CONSTITUTION.md`** — never edit on your own; if reality violates a principle, tell the user and propose an amendment.
4. Unknowns stay as `[NEEDS CLARIFICATION: …]` — but a document carrying markers cannot be confirmed, so resolve them by asking.
5. Run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" confirm <doc> [<doc> …]` for each document you brought up to date. This records the new baseline
   (commit the change to `.groundwork/freshness.json` with the doc). Only confirm what you have actually verified.
6. If you changed **workspace** documents from inside a repo session, say so: they belong to the whole product, and the user (or a teammate) should review that change.
7. Run `groundwork.py fresh` again (expect FRESH) and `groundwork.py check`. Report to the user in a few lines what changed in which document and why.

## When *not* to confirm
If nothing is wrong, but the document is simply old ("not reviewed for N days"), read it against the code once; if it is still true, confirm it as is — that is a legitimate refresh.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
