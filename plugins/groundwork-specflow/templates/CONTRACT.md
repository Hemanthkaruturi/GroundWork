---
id: {{id}}
title: {{title}}
provider: {{provider}}
consumers: [{{consumers}}]
version: 1.0.0
status: draft
origin: {{origin}}
observed_at: {{date}}
source_revision:
provider_reviewer:
consumer_reviewers: []
signoffs_required: 2
author: {{author}}
created: {{date}}
---

# Contract: {{title}}

<!-- What the provider promises its consumers, versioned (semver). `origin: baseline` means AS-BUILT: it
describes the surface as observed in the provider's code and docs, not a new design; `observed_at` says when.
Name the humans who review it: `provider_reviewer` and `consumer_reviewers`. Approval counts distinct
signers only; whether both sides really reviewed is a human procedure, and `check` warns when a named
reviewer has not signed. A shipped contract is never changed in a breaking way in place: add a version. -->

## 1. Provider and consumers
[TODO: who serves this, who calls it, and where each consumer's copy of the contract lives]

## 2. Version and changelog
**Version:** 1.0.0
- 1.0.0 ({{date}}): [TODO: first recorded version — as observed, or as agreed]

## 3. Operations
<!-- One subsection per operation: request and response shapes, and at least one REAL example each. -->
### [TODO: METHOD /path or event name]
**Request:** [TODO]
**Response:** [TODO]
**Example:** [TODO: captured from the running provider, or marked unverified]

## 4. Errors and failure semantics
[TODO: codes, retries, idempotency keys, timeouts, what a consumer must do on each]

## 5. Auth and tenancy
[TODO: how a consumer authenticates; what scopes what]

## 6. Compatibility rules
[TODO: what counts as breaking → new version; what may change in place]

## 7. Evidence
<!-- As-built only. Where each claim was observed (provider files, docs, consumer code or tests) and what was NOT verified. -->
| Claim | Provider evidence | Consumer evidence | Verification | Observed |
| --- | --- | --- | --- | --- |
| [TODO] | [TODO] | [TODO: or "not accessible"] | [TODO: inspected / executed / not verified] | {{date}} |

## Changes
_None yet._
