---
name: interview
description: Interview the user about what they want built until the picture is complete and unambiguous, before any RFC, spec or code. Use whenever the user asks for a new feature, change, or project.
---

# Interview before you write anything

## How to ask the user anything (mandatory)
**Every question to the user goes through the `AskUserQuestion` tool. Never write questions in your reply text, and never end a reply with a list of questions.** The user answers by selecting, not by typing paragraphs.
- Up to 4 questions per call, each with 2–4 concrete options that *you* derived from context (the code, the docs, common practice). Put your recommended option first and label it "(Recommended)". The tool adds "Type something" and "Chat about this" itself.
- One short `header` per question (≤12 chars); the question is ONE sentence. Each option: a label of at most 5 words and a description of what happens if chosen (at most 15 words); your recommendation first with its reason. Use `multiSelect` when choices are not mutually exclusive.
- Ask, wait for the answers, write them into the document immediately, then ask the next round. Repeat until nothing is unknown. Do not batch everything into one giant list or stop and hand the questions back.
- Options are proposals, not facts: record what the user *selected or typed*, nothing more. If they choose "Chat about this", discuss, then ask again.
- If `AskUserQuestion` is not loaded yet, load it first with `ToolSearch` query `select:AskUserQuestion`, then call it. Only if the tool truly does not exist in this session (e.g. non-interactive `-p` mode) may you fall back to plain text, and then ask at most one short round, numbered.
- Confirmations count as questions too ("Is this PROJECT.md right?" → ask with options: Looks right / Change something).

The user's first sentence is never the whole requirement. Your job is to find what is *missing*.
Do **not** start designing, writing an RFC or touching code until the interview is done.

## Before anything else: what kind of request is this?
- **A defect in existing behaviour** ("X is broken", "it should do Y but does Z") → stop; use the **fix-bug** skill.
- **Continues something in flight** (the context lists IN FLIGHT items) → use the **resume** skill.
- **New or changed behaviour** → continue below.

## Persist as you go (so a closed session loses nothing)
After the **first** round of answers, create the RFC (`groundwork.py new-rfc <slug>`) and record every question and answer in its §3 table immediately after each round.
The RFC draft *is* the interview's memory: a new session resumes from it (the **resume** skill reads it).

## Method
1. Read PROJECT.md, ARCHITECTURE.md, CONSTITUTION.md (workspace and repo) and skim related code/specs, so
   you never ask something the documents already answer.
2. Restate the request in one sentence and ask the user to correct it.
3. Ask in **rounds of 3–6 questions**, most consequential first, using `AskUserQuestion` (always — see above). Follow the answers: each round should be shaped by the last.
4. Keep a running Q&A log (you will paste it into the RFC's §3).
5. Stop only when you could hand the RFC to a stranger and they would build the right thing. Then read the
   picture back to the user, in your own words, and get an explicit "yes, that's it".

## Ownership (always ask — it decides whom to contact later)
With the picker (options from PROJECT.md's people table, plus "Someone else"): **who requested this** (and where the request came from: ticket, email, meeting — record it as `request_source` in the RFC), **who will own it** (default: the person you are talking to), and — if already known — **who will support it after release**. Record with `groundwork.py record requested|owner|support --ref <ref> --who "<name>"`; new RFCs/features already set the owner to the git identity. The responsible person is always a human.

## Relationship to existing work (always ask — it changes the process)
Search the existing specs and RFCs first (`groundwork.py board --all`, `groundwork.py deps <feature>`, grep `specs/` in every repo the change may touch), then ask, with the candidates as options:
- **Independent** — a new capability touching nothing that exists. No relations.
- **Extends** feature X — adds to it; the spec covers only the delta.
- **Amends** feature X — changes behaviour X already specifies (X's spec must be edited, logged under `## Changes`, and re-approved).
- **Depends on** feature X — cannot be built until X is implemented; or **builds against** X — can proceed in parallel once X's spec is approved and its plan finished (an agreed contract).
- **Supersedes** an earlier RFC — the decision itself is being replaced.
Record the answer in RFC §7 (Impact) and it becomes the spec's front matter (`extends`, `amends`, `depends_on`, `builds_against`).

## What to probe (skip only what is truly irrelevant)
- **Who / why:** which user, what they do today, what pain, why now, what happens if we do nothing.
- **Done:** the observable outcome they would accept; how they would demonstrate it.
- **Scope:** what is explicitly *out*; smallest useful version vs. later.
- **Behaviour:** the happy path step by step; inputs, outputs, formats; empty/huge/duplicate/concurrent cases.
- **Failure:** what the user sees when it breaks; what must never happen; data loss, cost, abuse.
- **Boundaries:** which repos/services it touches; who consumes it; contract changes; who must sign off.
- **Constraints:** performance, security, privacy, compliance, budget, deadlines, tech the team has ruled in/out.
- **Look and feel / UX (any UI change, including "make it look modern")** — this is a change request, not a free-hand design task. Ask (with the picker): which screens/flows are in scope; the feel wanted (offer 3–4 concrete directions with a one-line description each, and "show me references"); brand constraints (colours, fonts, logo); light/dark; density; accessibility target (e.g. WCAG AA contrast, keyboard use); responsive targets (phone/tablet/desktop); what must NOT change; how the user will judge "better" (before/after screenshots, a checklist). Their answers become testable requirements in the spec.
- **Existing behaviour** it changes or must not break; migration of existing data.
- **Verification:** how a human would test it by hand; which real inputs to try.
- **People:** who decides, who reviews, who to ask.

## Do not
- Ask questions whose answer is in the repo. Ask one giant list. Offer your assumptions as facts.
- Fill gaps with guesses — carry unknowns forward as `[NEEDS CLARIFICATION: …]`.

When finished, proceed to the **write-rfc** skill.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
