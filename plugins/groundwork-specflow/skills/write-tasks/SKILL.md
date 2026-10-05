---
name: write-tasks
description: Break the plan into small, verifiable tasks in tasks.md. Use after plan.md is complete.
---

# Write the tasks

Fill `specs/<active>/tasks.md`.

- One task = one reviewable change, ordered so checks are green after each.
- Every task has **Files**, a verifiable **Done when**, and **Covers: FR-n** (the traceability link).
- Mark `[P]` only for tasks on disjoint files.
- Tests for an AC come before or with the code that satisfies it.
- Keep the closing verification tasks: `groundwork.py verify` passes (T900); every FR is covered by a completed task;
  the spec's manual test was run by hand.

If tasks reveal a problem in the spec or plan, use the discovery protocol in the **write-plan** skill (ask, amend with a logged reason, re-approve, re-verify) — never edit upstream documents silently.

Remove every `[TODO…]`, run `groundwork.py plan-sync`, then continue to **write-evals**.

Finally run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" check` and fix every error it reports for this document before asking the user to review.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
