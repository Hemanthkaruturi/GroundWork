---
id: {{id}}
title: {{title}}
status: open
severity: medium
classification: unclassified
violates: []
amends: []
rfc:
regression_test:
reported_by:
owner:
fixed_by:
author: {{author}}
created: {{date}}
---

# Bug {{id}} — {{title}}

<!-- status: open -> diagnosed (diagnosis done; code edits allowed) -> fixed (regression test exists and passes) -> closed.
classification: code-bug (spec is right, code is wrong: list the violated requirements in `violates` as ID@feature,
e.g. FR-2@001-widgets or AC-1@api/003-x — several allowed, across features) | spec-gap (the spec is silent or wrong: list the specs in
`amends`, edit and re-approve them, and add a line for this bug in their "Changes" section) | design-flaw (the RFC decision was wrong:
set `rfc` to a new or amending APPROVED RFC). `regression_test` is the path of the test that fails before the fix and passes after. -->

## 1. Report
**Expected:** [TODO]
**Actual:** [TODO]
**Reported by / when / where seen:** [TODO]

## 2. Reproduction
[TODO: exact steps or a failing command; minimal input; environment]

## 3. Diagnosis
[TODO: the root cause, in the code, with file:line — not the symptom]

## 4. Classification
[TODO: code-bug | spec-gap | design-flaw — why. Which requirement(s) of which feature(s) are violated or missing; which RFC decision, if any]

## 5. Fix plan
[TODO: the smallest change that fixes the root cause; files; what could regress; other features that depend on this behaviour]

## 6. Regression test
[TODO: the test that fails now and passes after the fix; where it lives]

## 7. Verification
_Filled after the fix: how it was verified by hand and by test; docs updated (ARCHITECTURE/AGENTS/CONTRACTS) or unchanged._
