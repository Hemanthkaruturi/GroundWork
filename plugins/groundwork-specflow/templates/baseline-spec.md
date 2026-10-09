---
id: {{id}}
title: {{title}}
status: draft
origin: baseline
observed_at: {{date}}
source_revision:
created: {{date}}
author: {{author}}
owner:
support: []
extends: []
depends_on: []
builds_against: []
amends: []
---

# Baseline: {{title}}

<!-- A BASELINE describes behaviour that already exists. It is history, not a plan: no RFC, no tasks.
Observation comes from the code and tests; intent comes from the user or reliable existing documents.
Write what the system DOES today, in domain language. A guarantee the user confirms but the code currently
breaks goes under Known discrepancies with a bug reference — never describe a defect as the requirement.
"Historical rationale unknown" is valid text; unknown EXPECTED behaviour is a [NEEDS CLARIFICATION] marker. -->

## 1. Problem
[TODO: what problem this capability solves today, for whom]

## 2. Users and context
[TODO]

## 3. User stories
- **US-1**: As a [TODO], I [TODO] so that [TODO].

## 4. Functional requirements
- **FR-1**: [TODO: the system does … (observed and confirmed as intended)]

## 5. Non-functional requirements
- **NFR-1**: [TODO: or "none observed"]

## 6. Acceptance criteria
- **AC-1**: Given [TODO], when [TODO], then [TODO]. (covers FR-1)

## 7. Failure behaviour
[TODO: what a user or consumer sees today when it goes wrong]

## 8. Manual test
<!-- How a human sees this working today: exact commands / clicks / expected output. -->
1. [TODO]

## 9. Out of scope
[TODO: accepted limitations; what belongs to future work]

## 10. Constitution check
[TODO: principle → how the existing behaviour complies, or where it does not]

## Intent and rationale
<!-- The interview record for this baseline. Effect: Confirmed, Tension, Open decision, Doc update, Out of scope. -->
| # | Question | Answer | Source / person | Effect |
| --- | --- | --- | --- | --- |
| 1 | [TODO] | [TODO] | [TODO] | [TODO] |

## Known discrepancies
<!-- Confirmed guarantees the code currently breaks. `- [ ]` open, `- [x]` resolved. Each names a bug record. -->
_None known._

## Evidence
<!-- One row per FR / NFR / AC. Verification: inspected · executed/passed · executed/failed · not verified. -->
| Requirement | Implementation (paths, symbols) | Tests / observations | Verification | Observed |
| --- | --- | --- | --- | --- |
| FR-1 | [TODO] | [TODO] | [TODO] | {{date}} |

## Changes
_None yet._
