---
name: handover
description: Write HANDOVER.md for a finished or paused feature so the next engineer or agent can continue without reverse-engineering decisions. Use when all tasks are done, or work is being paused or transferred.
---

# Hand over the system, not the code

Copy `templates/HANDOVER.md` from the plugin (`${CLAUDE_PLUGIN_ROOT}/templates/HANDOVER.md`) to the repo root
(or update the existing one) and fill it from what is *true*, verified:

architecture/dependency map · done / in progress / deliberately deferred · decisions taken and alternatives
rejected · contracts with example requests and responses · known limitations and edge cases · how to run, test and
deploy · the next three recommended actions.

Fill the **Ownership and support** section from the record (`groundwork.py who <feature>`), ask the user (picker) for anything missing — who supports it, how to escalate — and record it (`groundwork.py record support --ref <feature> --who "..."`).

First run the **refresh** skill: the foundation documents must match what you are handing over.

Test: could a new engineer continue without asking why each major decision was made? If not, write the missing
reason. Also update DECISIONS/ (turn approved RFCs into ADR notes if built) and the spec's status.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
