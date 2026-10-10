---
name: write-evals
description: Write evals.md — the scenarios, edge cases and unplanned cases that prove the feature is right — before any code. Use after tasks.md.
---

# Write the evaluations

Fill `specs/<active>/evals.md` **before implementing**. This is the answer to "what did the user picture?"

- One row per scenario: concrete input, concrete expected value, the AC/FR it covers, and *how it is checked* (automated test
  file/name, or the step of the spec's Manual test, "spec §8 step 3"). Cite the AC; never paste its sentence (`check` warns with GW092). The row adds the values the AC leaves abstract.
- Cover: the happy path; each AC; boundaries (empty, one, many, huge); bad input; permissions/tenancy;
  repetition and concurrency; the failure behaviour promised in the spec; the "scenario catalogue" of odd
  real-world inputs.
- Every AC must appear at least once. If an AC cannot be checked, the AC is badly written — fix the spec.
- **Guardrail scenarios.** Read CONSTITUTION.md (repo and workspace). For every guardrail this feature could break (a secret in a log, a cross-tenant read, a direct provider call, an unbounded fan-out…) add a row that proves it still holds, with "Covers" naming the guardrail. These are tests, not a restatement of the constitution: the RFC's §7 already records the check.

If writing an evaluation exposes an unspecified case, use the discovery protocol in the **write-plan** skill; do not paper over it.

Remove every `[TODO…]` and run `groundwork.py plan-sync`. Then tell the user the spec, plan, tasks and evals are ready and that implementation may begin.

Finally run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" check` and fix every error it reports for this document before asking the user to review.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
