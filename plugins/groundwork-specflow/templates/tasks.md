---
id: {{id}}
spec: spec.md
spec_version:
plan: plan.md
created: {{date}}
---

# Tasks: {{title}}

> One task = one reviewable change, ordered so the suite stays green after each.
> `[P]` marks tasks on disjoint files. Legend: `[ ]` not started · `[~]` in progress · `[x]` done.
> Mark a task `[x]` only after its "done when" is verified.
> "Done when" names the proof — the eval ids and the command that runs them — never the behaviour again (the spec owns that).

- [ ] **T001** — [TODO]
  - **Files:** [TODO]
  - **Done when:** [TODO: e.g. "E1, E4 pass (`npm test`)"]
  - **Covers:** FR-1

## Verification
- [ ] **T900** — `groundwork.py verify` passes (format, lint, types, tests)
- [ ] **T901** — every FR in the spec maps to at least one completed task
- [ ] **T902** — the spec's manual-test section was run by hand and matches
- [ ] **T903** — foundation docs (ARCHITECTURE/AGENTS/CONTRACTS/PROJECT) updated or explicitly unchanged; `groundwork.py fresh` is clean
