---
id: {{id}}
spec: spec.md
spec_version:
created: {{date}}
---

# Plan: {{title}}

<!-- HOW. Cite the spec's requirement ids (FR-n, NFR-n) for every decision. The spec owns what the
user sees; this file owns the mechanism. Never restate a requirement, an acceptance criterion or the
spec's failure behaviour: cite its id. The RFC owns the constitution check. -->

## 1. Approach
[TODO]

## 2. Affected modules and files
<!-- Name each file's role folder from `groundwork.py layout` (core / connectors/<system> / entrypoints / config / wiring),
     or, when the repo keeps its own structure, the existing folder that already holds that kind of code. -->
[TODO]

## 3. Data model and migrations
[TODO or "none"]

## 4. Interfaces and contracts
[TODO: endpoints/events/functions; reference CONTRACTS/ version if cross-repo]

## 5. Failure modes and edge cases
[TODO: what the code does when each thing fails — the user-visible outcome is spec §7; cite it]

## 6. Test strategy
[TODO: tools, test layers, and what cannot be automated — the scenarios themselves are evals.md]

## 7. Rollout and rollback
[TODO]
