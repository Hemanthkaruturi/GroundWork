---
name: write-evals
description: Write evals.md — the scenarios, edge cases and unplanned cases that prove the feature is right — before any code. Use after tasks.md.
---

# Write the evaluations

Fill `specs/<active>/evals.md` **before implementing**. This is the answer to "what did the user picture?"

- One row per scenario: input, expected result, the AC/FR it covers, and *how it is checked* (automated test
  file/name, or exact manual steps).
- Cover: the happy path; each AC; boundaries (empty, one, many, huge); bad input; permissions/tenancy;
  repetition and concurrency; the failure behaviour promised in the spec; the "scenario catalogue" of odd
  real-world inputs.
- Every AC must appear at least once. If an AC cannot be checked, the AC is badly written — fix the spec.

If writing an evaluation exposes an unspecified case, use the discovery protocol in the **write-plan** skill; do not paper over it.

Remove every `[TODO…]` and run `groundwork.py plan-sync`. Then tell the user the spec, plan, tasks and evals are ready and that implementation may begin.

Finally run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" check` and fix every error it reports for this document before asking the user to review.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
