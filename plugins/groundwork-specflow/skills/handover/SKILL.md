---
name: handover
description: Write the handover for a finished or paused feature so the next engineer or agent can continue without reverse-engineering decisions. Use when all tasks are done, or work is being paused or transferred.
---

# Hand over the system, not the code

First run the **refresh** skill: the foundation documents must match what you are handing over, and any baseline whose sources this work changed must be reviewed (`groundwork.py confirm --baseline <slug>`).

## Where it goes (never a repo-root file)
One root file fits one piece of work and collides with the next. Use two places, each with one job:

| Scope | File | Holds |
| --- | --- | --- |
| This repo's spec | `specs/NNN-slug/handover.md` (`${CLAUDE_PLUGIN_ROOT}/templates/HANDOVER.md`) | Files touched, state, how to run/test/deploy, known limits, next actions — repo-local facts only |
| A cross-repo (`api`) RFC | workspace `DECISIONS/handovers/RFC-NNNN.md` (`${CLAUDE_PLUGIN_ROOT}/templates/HANDOVER-RFC.md`) | Why, rejected alternatives, deploy order, contract state, table of repos and their spec handovers |

Rules:
- **One owner per fact.** Rationale, rejected alternatives and deploy order live only in the RFC handover (or the RFC). A spec handover links to it; it never restates it. If the two disagree, the RFC handover wins — fix the other.
- **Internal RFC (one repo):** only the spec handover; set its *Cross-repo handover* line to "none".
- **Lasting facts go elsewhere.** Architecture → ARCHITECTURE.md; shapes and examples → `CONTRACTS/`; decisions → the RFC record (turn approved RFCs into ADR notes if built). Link, don't copy.
- **Part of done.** The handover is committed in the same PR as the last task, so it merges with the work and is not stranded on a branch.
- **Lifecycle.** When the work is deployed everywhere, fold what is durable into the homes above, then set `Status: closed` (or delete the file). A stale handover is worse than none.
- **Legacy.** If a repo-root `HANDOVER.md` already exists, move it into the right spec folder; do not add a second root file.

## Fill it from what is true, verified
Fill **Ownership and support** from the record (`groundwork.py who <feature>`), ask the user (picker) for anything missing — who supports it, how to escalate — and record it (`groundwork.py record support --ref <feature> --who "..."`). Also update the spec's status.

Test: could a new engineer continue without asking why each major decision was made? If not, write the missing reason — in the RFC handover if cross-repo, otherwise in the spec handover.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
