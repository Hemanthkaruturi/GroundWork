# Plan: baseline existing repositories with evidence and an interview

**Status:** development proposal · **Author:** Hemanth Karuturi, drafted with Claude, revised with Codex, review points folded in by Claude · **Date:** 2026-10-09

## Decisions taken in this revision

The first draft left five questions open. This revision settles them:

1. **Approval.** Baseline specs need human approval before bugs or relations can cite them. Bulk
   approval is one human command with several paths, recorded per document.
2. **When baselines are written.** Offered as a normal bootstrap step with explicit deferral, and
   written lazily when a feature or bug touches undocumented behaviour.
3. **Evidence-derived artefacts.** Constitution candidates and as-built contracts are in scope.
   Decisions (ADRs) stay optional and can be dropped without weakening the rest.
4. **Marker name.** `origin: baseline`, with `origin: imported` for unclassified legacy documents.
5. **Status display.** `status:` is not overloaded; the approvals record stays authoritative.

## The decision

Existing-repository bootstrap must establish references for future work, not stop at foundation
documents. GroundWork will inventory the active capabilities, investigate their implementation,
interview the user about purpose and intent, and create a manageable initial set of baseline
specs. It will also propose constitution rules and contracts from evidence. Remaining capabilities
stay visible as deferred coverage and are documented when touched.

Repositories with legacy specs use the same investigation and interview, but import and reconcile
what exists rather than replace it. Importing a document does not mean its requirements are
implemented, its behaviour is intentional, or its text is approved. These are separate facts.

This document defines the proposed development scope and acceptance criteria. Commands and fields
below are additions to implement, not capabilities already available. Human approval remains
required; this proposal does not approve documents or authorize changes to the example repos.

## 1. Problem and verified examples

The normal pipeline needs requirements that later features can extend or amend, and that bugs can
cite. Foundation documents alone do not provide that behavioural reference. Repeatedly reading
code also cannot establish why a capability exists or which accidental behaviours should change.

### 1a. No GroundWork specs: legaldb

`/home/terminator/projects/legaldb` has no `specs/` directory. It does have substantial source
material: README, `docs/SEARCH_ENGINE_ARCHITECTURE_2026_07_04.md`, research and build findings,
implementation in `app/`, `agent/`, `src/` and `jobs/`, and tests and evaluation tooling.

Candidate capabilities, subject to investigation and user confirmation:

| Capability | Starting evidence |
| --- | --- |
| Case search and lookup | `app/main.py`, retrieval/router modules, search architecture and evaluation reports |
| Case details | Case-detail endpoint, response/card modules, database schema |
| Grounded legal answers | `agent/legal_agent.py`, `/ask`, README and answer evaluation tooling |
| API access and billing | `app/billing/`, endpoint dependencies, pricing and cost-control docs |
| Judgment ingestion and embeddings | `src/cli/`, extraction/database modules, `jobs/`, associated tests |
| Usage analytics | `app/analytics/`, tracking/admin endpoints, README |

These are an inventory proposal, not six automatically approved specs. The README distinguishes
current execution surfaces from legacy ones. Discovery must preserve that distinction rather than
turn every historical folder or roadmap item into a current capability.

There is also useful rationale in code comments: `app/config.py` explains why search reranking is
disabled by default using measured results. The interview should confirm whether that rationale
still governs the product, not ask the user to reconstruct information already documented.

### 1b. Legacy specs: llm-gateway

`/home/terminator/projects/SignalFarming/llm-gateway` has 14 legacy spec-kit specs, a constitution in
`.specify/memory/constitution.md`, foundation documents and `.groundwork` metadata. Read-only
`groundwork.py check` on 2026-10-09 reported 14 GW020 errors: 13 directories lack `evals.md`;
009 also lacks `plan.md` and `tasks.md`.

It is not established that all 14 documents describe completed work:

- 009, 011, 012 and 013 are labelled Draft; 014 is labelled In progress.
- Several task lists have unchecked items. This may reflect missing work or outdated records;
  neither interpretation should be assumed.
- The legacy headings differ from GroundWork's template. None has the required Manual test
  section; several have Resolved decisions and Open questions in its place.
- An Approved label records accepted intent, not evidence that every requirement was implemented.

The current checker stops early on missing companion files, so removing GW020 can expose other
issues. The acceptance target is correct classification and useful references, not forcing all
14 errors to zero by declaring every document completed.

## 2. Design principles and settled defaults

1. **Interview during investigation.** Alternate reading evidence and asking focused questions.
   Do not postpone all questions until a final "Looks right" confirmation.
2. **Separate observation from intent.** Code establishes observed behaviour; the user or reliable
   existing documentation establishes purpose, constraints and expected guarantees.
3. **Start small, make omissions visible.** Inventory active capabilities and baseline a selected
   initial set. No fixed target of 5–12 specs; scope depends on the repository.
4. **Import is not completion.** Preserve legacy source and classify before treating it as baseline.
5. **Approval is human and content-bound.** Review conversation is not an approval record. Bulk
   approval records an independent approval for each document.
6. **Keep normal feature discipline.** Baselines exempt retrospective work from RFC/tasks requirements;
   they do not exempt new implementation from the normal pipeline.
7. **Do not canonize defects.** Known problems remain discrepancies, not desirable requirements.
8. **Preserve provenance and detect drift.** Evidence includes relevant sources, tests, observations
   and review date; scoped source changes trigger review.
9. **Do not invent history.** Missing historical rationale is allowed when expected behaviour is clear.
   Uncertainty about expected behaviour remains blocking for the affected requirements.

## 3. Existing-repository bootstrap and interview

### 3a. Sequence

1. Detect workspace/repo/standalone ownership and run existing discovery. Inspect foundation docs,
   legacy specs, contracts and decisions before drafting duplicates.
2. Identify entry points, supported workflows, consumers and current versus legacy surfaces.
   Propose a capability inventory and ask the user to correct the boundaries and lifecycle labels.
3. Establish project purpose, users, scope and priorities with the user. Draft or complete foundation
   documents using evidence and confirmed answers, respecting their owning root.
4. Propose initial baseline coverage. Prioritize core workflows and paths where failure causes cost,
   data loss, isolation failures or downstream breakage. Allow explicit deferral, including all
   baselines for now, but show the uncovered capabilities at the end.
5. For each selected capability, investigate, interview, reconcile and draft as described below.
   Reuse overlapping legacy specs and documents rather than create another source of truth.
6. Propose constitution rules and consumed contracts. Record optional decisions only where useful.
7. Present concise read-backs, resolve behaviour-blocking questions and request human approval.
8. Confirm foundation freshness, report baseline review/coverage state and offer existing hook setup.
   Foundation confirmation must not imply baseline approval or complete behavioural coverage.

Existing layout/toolchain choices remain separate; bootstrap does not move or reformat code.
Inventory, interview and document drafting must be resumable between sessions.
In a non-interactive session, persist the evidence and outstanding questions for the next session;
do not infer answers, confirm intent or approve anything because the user is unavailable.

### 3b. Interview method

For a capability, read relevant code, tests and docs first. Present a short evidence-backed account
of what happens today, then ask about what the evidence cannot settle. Use the host's supported
question tool and its limits; selectable options are concrete proposals, never pre-confirmed facts.

| Topic | Questions to settle | Destination |
| --- | --- | --- |
| Purpose | Whose problem does this solve? What outcome matters? | PROJECT and baseline Problem/Users |
| Rationale | Why this approach? Which cost, latency, operational or integration constraints mattered? | Baseline rationale; ARCHITECTURE or ADR where appropriate |
| Intent | Is this behaviour deliberate, temporary, a workaround or a defect? | Requirements and Known discrepancies |
| Preservation | What must future changes keep working, including failures and isolation? | FR/NFR/AC and contract guarantees |
| Direction | Which limitations are accepted; which belong to future work? | Out of scope and capability inventory |
| Ownership | Who can confirm expectations and support this capability? | Owner/support and PROJECT people table |

Example: "Code and measurements show search reranking is off by default. Should it remain off
until a new evaluation passes, or is the current default temporary for another reason?" The agent
must not silently promote a measured implementation choice into a permanent constitution rule.

Persist answers after every round in the baseline's `## Intent and rationale` table, including
question, answer, source/person and effect: Confirmed, Tension, Open decision, Doc update or Out of
scope. Log broad project answers in the relevant foundation document. For a pending legacy import,
answers may be staged in the capability record's `interview_notes` while the body is untouched;
they must be moved into the spec body before the document is classified as baseline, because only
the body is covered by approval (see §5a).

If the user corrects the observed behaviour, investigate the discrepancy before finalizing the
spec. If docs, tests and code disagree, show the conflict and ask what expectation should govern.
Do not pick whichever source makes onboarding easier.

### 3c. Unknowns and review

`Historical rationale unknown` is valid text when nobody knows why a choice was made. Record
whether the user confirms preserving its behaviour going forward. Lack of a historical story must
not prevent approving otherwise clear behavioural requirements.

Use `[NEEDS CLARIFICATION: …]` for unresolved expected behaviour, scope or commitments. Such markers
continue to prevent approval. A capability can instead be narrowed to its settled behaviour;
unsettled scope stays explicitly deferred, with no requirement claimed for it.

Read-back must cover purpose, observed behaviour, intended guarantees, accepted limitations,
known discrepancies and coverage gaps. "Is this how it behaves today?" alone is insufficient.

## 4. Capability inventory and evidence

### 4a. Persistent coverage index

Maintain a capability table in `specs/README.md`, **generated by the engine the way `CODEMAP.md`
is generated**: engine-owned columns are rewritten on every run, one free-text column (Notes) is
preserved, and existing prose outside the table is left alone. The table is a view, not a second
source of truth. Use stable capability slugs and explicit spec links, not a folder-to-spec heuristic.

Each row shows capability, lifecycle (active/legacy/retired/planned/uncertain), coverage
(baselined/deferred/import-review), linked spec(s), approval state, review state, relevant source
paths, confirmed purpose or rationale link, the next question/action, and the preserved Notes.

**Data model.** Capability records live in `.groundwork/capabilities.json` (committed; not in the
`.groundwork/.gitignore` list), one entry per slug:

```json
{
  "case-search": {
    "title": "Case search and lookup",
    "lifecycle": "active",
    "lifecycle_confirmed": {"by": "<person>", "at": "2026-10-09"},
    "suggested_lifecycle": "active",
    "sources": ["app/retrieval.py", "app/router.py", "tests/test_search.py"],
    "rationale_ref": "docs/RETRIEVAL_BENCHMARK_FINDINGS_2026_07_04.md",
    "specs": [],
    "next_action": "baseline interview not started",
    "interview_notes": []
  }
}
```

`specs` is empty while deferred and holds one or more `NNN-slug` entries when linked: a mixed
legacy document split into a baseline and a planned feature links both, and a capability spanning
two baselines links both. Linking is **additive and idempotent**: it appends a slug that is not
already present and never replaces an existing one; `capability unlink <cap> <spec>` is the only
way to remove one. Discovery writes only `suggested_lifecycle` and may add to `sources`; everything
else is written by the baseline skill through `groundwork.py capability set|link|unlink`. Linking
happens three ways: `new-baseline <slug> --capability <cap>` links on creation; `adopt-specs
--classify baseline|planned <slug> --capability <cap>` links a classified import; `capability link
<cap> <spec>` for the rest.

**Coverage with several linked specs.** Coverage is computed per linked spec from its
`origin`/`adoption_state` and shown as the weakest state, with a count: `baselined` only when every
linked spec is an approved baseline; `partial (1 baselined, 1 planned)` when at least one is and
others are planned or pending; `import-review` when any linked spec is a pending import and none
is baselined; `deferred` when `specs` is empty. The table shows every linked spec with its own
state so the reader can see which one is holding coverage back.

**Derived columns.** Coverage comes from the linked specs as above. Approval
state comes from the approval records via `doc_state`, never from front matter. Review state comes
from the freshness snapshots (slice 2; shown as "not tracked" before then). `groundwork.py
capabilities` regenerates the table, preserving Notes; `check` warns when the table is older than
the records it is built from. Discovery may suggest a lifecycle with its evidence; only the
user-confirmed one is authoritative.

Document boundaries follow business capabilities. One route group can support several capabilities;
a single capability can span routes, a worker and CLI. Do not require exhaustive documentation to
finish bootstrap. Never present deferred coverage as complete coverage.

### 4b. Requirement-level evidence

Each new baseline has an `## Evidence` table mapping FR/NFR/AC IDs to:

- implementation paths and relevant symbols; line numbers may be added but are not stable IDs;
- test paths/cases, existing evaluation reports or manual observations;
- verification state: inspected, executed/passed, executed/failed or not verified;
- observation/review date and source revision if available.

Tests inspected are not tests passed. A documented manual procedure is not an observed result.
Do not run paid-provider calls, deployment operations or mutating production checks merely to
complete discovery. Follow existing repository test instructions and report verification limits.
Evidence can cite existing research/rationale instead of asking the user to repeat it.

For baseline approval, every claimed requirement needs traceable evidence or an explicit gap
accepted in the read-back. Evidence gaps produce warnings; unknown expected behaviour blocks
approval. A confirmed guarantee may currently fail: record it in Known discrepancies with a bug
reference instead of claiming the implementation satisfies it.

## 5. Baseline model and engine semantics

### 5a. Metadata

Keep `origin: baseline` as the discriminator for reconciled existing behaviour. Absent `origin`
means the normal planned-feature pipeline. Introduce `origin: imported` only for legacy documents
awaiting classification or retained as archived references. Reject unsupported origin values.

```yaml
---
id: 003-metered-model-gateway
title: Metered Model Gateway
status: draft
origin: baseline
adopted_from: spec-kit       # omitted for a newly reconstructed baseline
adopted_status: Approved     # original label, preserved verbatim; not approval or completion
adopted_at: 2026-10-09
observed_at: 2026-10-09
source_revision: <commit>    # optional; content snapshots also work without git
owner: <confirmed human>
support: []
extends: []
depends_on: []
builds_against: []
amends: []
---
```

`status` remains a courtesy lifecycle label; approval records are authoritative. Do not overload
it with `baseline`, or use `adopted_status` to satisfy approval. Preserve known original authors
and dates; never invent an author from git ownership or import time.
The import-only `adoption_state` enum is `pending` or `archived`; classification as baseline or
planned removes it. Imported documents cannot be approved as behavioural references until classified.

New baselines use the ten standard spec sections, written for existing behaviour, followed by
`## Intent and rationale`, `## Known discrepancies`, `## Evidence` and `## Changes`.
Baseline approval preflight validates numbered requirements and AC references, verification guidance,
owner, evidence and the intent read-back. **Approval-critical behavioural content must reside in
the spec body; preflight also validates required metadata.** Approval hashes only the body, so an
index note or capability record can change while the approval stays valid, and nothing outside the
document may satisfy a behavioural requirement. Front matter is still read by preflight for what
belongs there: `id` matching the directory, `origin` and `adoption_state` (a pending or archived
import is rejected), `owner`, and the relation keys. For
reconciled legacy documents the verification guidance, intent read-back, known discrepancies and
evidence are appended to the body as sections, under the standard names, without renumbering the
legacy headings. Unresolved expected behaviour remains blocking; explicitly accepted evidence gaps
remain warnings.

### 5b. Behaviour matrix

| Concern | Baseline treatment |
| --- | --- |
| RFC lineage (GW021) | No retrospective RFC required. ID/directory consistency still enforced. |
| Companion documents (GW020) | Only `spec.md` required. Never manufacture completed tasks. |
| Plan/evals | Optional. If present as governed companions, check them; all reads must handle absence. |
| Imported plan/tasks/evals | Preserve as historical evidence until explicitly reconciled; do not impose new planned-work checks or derive completion from them. |
| Sections/manual test (GW022/GW024) | Newly authored baselines follow the template. Reconciled imports may retain legacy headings with warnings; numbered requirements, AC and verification guidance remain necessary for usable references. |
| Requirement validation (GW023) | Keep ID uniqueness, reference validity and FR/AC checks; do not short-circuit these when legacy headings differ. |
| Work-before-approval (GW034) | Existing historical tasks do not imply a process violation. New code changes still need normal feature/bug authorization. |
| Approval | Unapproved, approved and edited-after-approval states remain distinct. Baseline helpers must never return all workflow steps successful unconditionally. |
| Implementation | Baseline means existing capability, not proof that every AC passes. Known discrepancies remain visible. |
| Dependencies | An approved, non-stale baseline with no blocking unknowns satisfies `depends_on` without tasks. An open entry in Known discrepancies produces a **warning naming the discrepancy**, not a block: today a planned feature satisfies `depends_on` when its tasks are ticked, which proves nothing about acceptance criteria either, and a baseline must not be held to a stricter bar than the features it supports. |
| Length (GW090) | Unchanged. The prose counter already skips table rows, headings and quotes, so the Intent and Evidence tables cost nothing. Keep the existing budget; revisit only with evidence from real baselines that the prose in Known discrepancies pushes them over. |
| `builds_against` | A usable baseline needs a reviewed interface/contract reference rather than a fabricated plan. Normal planned-feature rules remain unchanged. |
| Owners/history (GW080–083) | Keep confirmed owner and support accountability. Skip invented historical implementer; report unresolved support through capability/project ownership. |
| Process maturity | Baselines alone do not establish that the team practices the planned-feature pipeline. |

`extends`, `amends`, `depends_on`, `builds_against` and bug `violates` references must reject
unapproved, approval-stale and imported-pending/archived targets. A source-review-needed target is
accepted with a warning (the review is a signal, not proof that a requirement changed). A baseline
with unresolved known discrepancies is accepted as a dependency with a warning that names them;
the engine does not infer requirement-level readiness in either direction.

### 5c. Board, status, active work and freshness

Approved current baselines do not appear as implementation work in flight. `board --all` and
search/dependency views retain them. Status, doctor **and the session-start context** (the
`session-context` hook, built by `describe` in `groundwork.py`) show a separate documentation-review
summary: awaiting interview/classification, awaiting approval, approval stale, or source review
needed, plus deferred capabilities. Pending imports must not disappear from view, and must stop
appearing under IN FLIGHT, which is what agents read first.

`new-baseline` must not replace the active feature/bug. Explicitly selecting a baseline must show
its documentation actions and refuse to treat it as an implementation target.

Extend freshness snapshots to baseline evidence paths, using content hashes and existing scan
exclusions. Store reviewed snapshots in the existing committed freshness record with a baseline
namespace; do not hash the entire repo per spec or require git history. Missing evidence files
also trigger review. Code drift is a review signal, not proof a requirement changed.

`confirm --baseline <slug>` records source review after the agent compares changes with the
requirements and reports its conclusion. It does not grant document approval. If requirements
change, normal human re-approval is still required. Bootstrap/new-baseline establish the initial
snapshot only after the draft's evidence paths are filled and reviewed; creating an empty scaffold
cannot confirm its sources. Refresh/resume surface later review needs. Unrelated file changes do
not stale a baseline.

## 6. Safe adoption of legacy specs

### 6a. Commands and classification

Proposed command contract:

- `adopt-specs --dry-run`: inventory candidates, original metadata, companion files, section gaps,
  unresolved markers and task counts. No writes or approval changes. Run at a workspace, it fans out
  to child repos the way `init` does; run in a repo, it covers that repo only.
- `adopt-specs [<slug> ...]`: import selected candidates, or all discovered candidates if no slugs
  are supplied, as `origin: imported`, `adoption_state: pending`. Add metadata and coverage entries;
  preserve body bytes. Never mark them implemented.
- `adopt-specs --classify baseline <slug> ...`: after investigation/interview and reconciliation,
  change origin to baseline and record source evidence; approval is still a separate human action.
- `adopt-specs --classify planned <slug> ...`: remove import-only state and apply the normal feature
  pipeline. A missing RFC is an explicit migration action, not a fabricated historical decision.
- `adopt-specs --classify archived <slug> ...`: retain origin imported, state archived, and original
  body/metadata. Keep discoverable but not usable as an approved behaviour/dependency reference.

Pending/archived imports receive import-specific validation and review warnings rather than
normal missing-RFC/tasks errors. They cannot satisfy implementation gates or relations. Normal
planned features are never exempted merely because `adopted_from` exists.

Mixed documents require user-guided reconciliation: isolate implemented scope as baseline, retain
planned scope in a separate normal feature or archive, preserve source links and requirement IDs
where possible, and review every changed relation. Do not copy unfinished promises into a baseline.

### 6b. Preservation and repeatability

Import reads title, status, dates and known people from existing metadata/body. Preserve foreign
front matter and unknown keys; never prepend a second YAML block. Ambiguous or incompatible front
matter is reported for manual review, not silently overwritten. `.specify/` suggests provenance
but does not prove that every document was authored by spec-kit.

Import is byte-preserving for bodies, idempotent, scoped to regular in-repo files and non-destructive.
Report nonstandard directory names without renaming; report collisions. Preserve existing relation
metadata. Reclassification only changes relevant metadata/index entries. Reconciliation edits to
body, manual guidance or evidence are separate, reviewable changes explained to the user.

The first import scan creates no approval records, no fabricated RFC/plan/tasks/evals and no active
implementation target. Rerunning it does not duplicate entries or reset already classified work.

## 7. Constitution, contracts and decisions

### 7a. Constitution

Harvest candidate rules and CI gates from current README, AGENTS, CLAUDE, CONTRIBUTING, existing
constitutions, relevant docs and workflow files. Include source and enforcement evidence where
available. Deduplicate and surface conflicts, including workspace/repo differences.

Ask which rules should govern future work and why. Classify accepted constraints, temporary
workarounds and preferences separately. Existing architecture and incidental coding patterns do
not automatically become constitution rules. Preserve the original constitution and explain any
replacement or narrowing; respect workspace ownership.

### 7b. As-built contracts

Inventory HTTP, CLI, events, files, library interfaces and schemas that others actually consume.
Route discovery is only a starting signal, not proof of a consumer or full contract coverage.

Read existing contracts first. Compare provider implementation with accessible consumer code/tests
and docs; if consumer evidence is unavailable, mark that verification limit. Draft only the
relevant consumed surface with shapes, examples, errors, auth/tenancy, retries/idempotency,
timeouts and compatibility rules. Examples from docs remain unverified until checked.

Contracts belong in workspace `CONTRACTS/`, or standalone `CONTRACTS/` when there is no workspace.
Add standalone discovery/scaffolding support for this path when needed. Preserve an existing
version. If none exists, propose initial `version: 1.0.0` with separate `observed_at` and source
revision fields; the date is never embedded in the semver value.

An as-built contract has `origin: baseline` and names its reviewers in front matter:
`provider_reviewer` and `consumer_reviewers`. **No new sign-off machinery is needed for counting:**
`doc_state` already reads `signoffs_required` from any document's front matter and `approve`
accepts any path, so a contract with `signoffs_required: 2` is approved by two humans with the
existing command. **What the engine does not do:** it counts distinct signer names and knows
nothing about roles, so two signers do not prove that a provider and a consumer both reviewed.
Provider/consumer confirmation is therefore a human review procedure in the write-contract skill,
not an engine-enforced guarantee. A warning-level check (slice 3) reports a contract whose signers
do not include every named reviewer; it never blocks. No RFC is invented for past work. If evidence
or a named reviewer is missing, display the contract as pending and do not present it as a mutual
commitment.
`contract.lock` is mentioned today only in the write-contract skill text; the engine neither writes
nor checks it. Pins, if implemented, are added after acceptance, not silently on discovery. Future
contract changes follow the normal RFC/signoff/versioning process.

### 7c. Decisions

Offer a short optional list based on explicit docs, code commentary or git history. Record original
rationale only when supported, or retrospective user explanation labelled as such. Commit subjects
suggest a topic; they do not prove the reason, approval or decision date. No bulk invented ADRs.

## 8. Later features and bugs

### 8a. Features

Search the capability index, related specs/contracts and code before choosing Independent.
If the touched active behaviour lacks a usable baseline, enter a bounded baseline interview and
approval step, then resume the feature interview. Create only the missing relevant scope, not a
full repository audit.

Amendment must update the baseline requirement text, add a dated Changes entry naming the new
feature, obtain re-approval and update evidence/regression coverage alongside implementation.
Extension specs describe the delta and preservation requirements. A relationship label alone does
not document the changed behaviour.

Resolve the current interview skill's "only edit the RFC draft" restriction explicitly: a baseline
substep may edit its spec, capability index and freshness record; other feature-interview edits
remain confined to the RFC. Record the pause/resume point there. Foundation updates follow the
existing approval sequence, except during bootstrap itself.

### 8b. Bugs

When a bug has no requirement to cite, reproduce and investigate first. Establish expected behaviour
from existing docs/tests and user confirmation, then create a bounded baseline or amend one.
Record the broken observation as a discrepancy, with its intended guarantee and bug reference.

- A pre-existing approved guarantee that code violates remains a code-bug.
- Missing, ambiguous or incorrect expectations remain a spec-gap until clarified and approved;
  creating a baseline must not retroactively claim an approved requirement existed before diagnosis.
- A wrong design decision follows the normal design-flaw/RFC path.

Baseline creation does not repair code, pass tests or grant approval. Regression tests must fail
for the diagnosed reason before the fix and pass afterward. Refresh the evidence/discrepancy state
when fixed; outstanding problems are not erased to make adoption appear complete.

## 9. Discovery additions and bounds

Evidence only in `.groundwork/discovery.json`; persistent decisions/coverage live in governed docs.

| Key | Contents |
| --- | --- |
| `surface.http` | Route locations, detectable operations/prefixes and detection limits |
| `surface.cli` | Detectable commands and source locations |
| `surface.schemas` | OpenAPI/proto/GraphQL and consumed file/event/schema candidates |
| `surface.api_docs` | API/integration docs and existing contract locations |
| `capability_candidates` | Evidence-backed clusters, suggested lifecycle and uncertainty; not confirmed scope |
| `rules` | Candidate lines, sources, possible conflicts and CI gate commands |
| `adoptable.specs` | Per candidate: path, metadata shape, original status, companion files, headings, task counts, markers |
| `git.recent_subjects` | Last 30 non-merge subjects as optional decision leads |
| `scan` | Limits, skipped/unsupported patterns and truncation notices |

Keep existing discovery keys for compatibility, including `adoptable.specs_dir`. Use bounded scans,
existing secret/generated/vendor exclusions, no execution/import of repository code, and no
out-of-root symlink traversal. Framework detection must disclose unsupported/dynamic routing.
Start with supported repository patterns; do not promise complete semantic analysis from regexes.

## 10. Implementation map and delivery order

### Engine and commands

| File/module | Work |
| --- | --- |
| `groundwork_core.py` | Baseline/import predicates, usable-reference checks, dependency and active-work semantics; keep approval distinct from implementation |
| New `groundwork_baseline.py` | Import/classification, baseline creation, coverage-index updates and baseline validation helpers |
| `groundwork_check.py` | Origin-aware validation, optional companion reads, legacy headings without skipped FR/AC validation, import review warnings, relation checks, stale capability table warning; GW090 unchanged |
| `groundwork_board.py` | Separate documentation review from implementation work; retain baseline/archive discovery under `--all` |
| `groundwork_doctor.py` | Coverage/import/baseline review summary; exclude baseline-only activity from process maturity |
| `groundwork_discover.py` | Bounded evidence discovery and richer summaries |
| `groundwork_fresh.py` | Scoped baseline snapshots, source-review reasons and explicit baseline confirmation |
| `groundwork_relations.py`, `groundwork_bugs.py` | Approved/current baseline references and conservative handling of discrepancies |
| `groundwork.py` | `adopt-specs` (workspace fan-out), `new-baseline`, `capability set|link|unlink`, `capabilities` (regenerate the table), baseline confirm; multi-path approve with all-path preflight before writing records; `describe` / `cmd_session_context` gain the documentation-review summary and stop listing baselines and pending imports as IN FLIGHT; `run_human_action` parses several paths for `/approve` |
| `groundwork_codemap.py` pattern | Reuse the generate-and-preserve-one-column approach for the `specs/README.md` capability table |
| Host hooks and command adapters | Preserve human-only approval and baseline documentation gates across supported hosts; support multi-path approve end to end |

New `new-baseline <slug> --title "…"` allocates the next free feature ID, creates only `spec.md`,
updates the coverage index and leaves active work unchanged. Refuse collisions. Multi-path approve
preflights resolution, duplicate paths, placeholders and baseline validation for all documents;
if any fails, record none. Approval still hashes and records each document independently.

Historical companions need explicit treatment: classify existing companions during adoption and
record them in baseline metadata as `historical_companions: [plan.md, tasks.md]` as appropriate.
Their presence never creates a new task obligation. Newly added plan/evals without this marker
are governed optional companions; require normal structure/version pins. Missing historical files
produce review warnings, not an exception or invented replacement.

### Skills, standard and packaging

- New `baseline/SKILL.md` and `templates/baseline-spec.md`: full investigation/interview/read-back,
  provenance, discrepancy and evidence procedure, bootstrap and lazy modes.
- `bootstrap`: baseline inventory and initial coverage are normal existing-repo steps, not a hidden
  optional afterthought; permit explicit user deferral and report it.
- `interview`, `write-spec`, `fix-bug`, `implement`, `refresh`, `resume`, `handover`: references,
  bounded baseline substeps, regression preservation, drift review and final evidence updates.
- `write-contract`: retrospective contract ownership/review without a fictional RFC.
- `workflow`, approval skill/commands for supported hosts: describe baseline versus planned work,
  documentation review and multi-document human approval.
- `STANDARD.md` and engine standard version: 0.8.0, including metadata, lifecycle, rules, ownership,
  contracts, approval and migration. Allocate new validation rule IDs after checking the catalogue.
- Update plugin release version separately, packaged skills/templates/commands and any vendored
  engine generation; standard 0.8.0 is not the plugin's release version.
- README, overview, manual-testing docs and sandbox fixtures: explain both adoption paths.

### Delivery slices

The risk with a plan this size is that nothing ships. Slice 1 is therefore the smallest set that
makes both example repos usable, and each later slice is optional on its own.

1. **Ship first, usable on its own:** origin states (`baseline`, `imported` with pending/archived),
   `adopt-specs` import and `--classify`, companion safety and `historical_companions`, check,
   board, doctor and session-context changes, multi-path approve with preflight, the baseline
   template with `observed_at` and the Evidence table, the generated capability table, and the
   baseline skill in both bootstrap and lazy modes. **Not in this slice:** baseline freshness,
   richer discovery, contracts, decisions. Existing planned-feature behaviour must stay unchanged.
2. **Baseline freshness:** scoped evidence snapshots, source-review reasons, `confirm --baseline`.
   Slice 1 already records `observed_at` and evidence paths, so this needs no migration.
3. **Discovery and shared boundaries:** `surface.*`, `rules`, `capability_candidates`, and
   retrospective contracts using the existing sign-off machinery.
4. **Decisions (7c):** optional; drop if time is short.
5. **Documentation and release:** complete the standard, host adapters, packaging and worked
   examples. Docs and tests for each slice ship with that slice, not here.

Do not estimate this as a four-day metadata change: interview, lifecycle, adoption and host support
are separate work with separate acceptance checks. Detailed estimates follow implementation design.
The skill sections of this plan (§3, §8) should be turned into numbered steps when the SKILL.md
files are written; the "must" style here is for the engine and the standard.

## 11. Required automated checks

| Area | Acceptance checks |
| --- | --- |
| Baseline model/check | Spec-only baseline never crashes; new template enforced; legacy headings still validate IDs/AC; optional governed companions checked; historical companions preserved; invalid origins rejected; approval preflight takes behavioural content only from the spec body and required metadata only from its front matter, so a change to a capability record can neither satisfy nor invalidate an approval |
| Approval/relations | Unapproved, edited-after-approval and imported (pending/archived) targets cannot satisfy relations/bug citations; a source-review-needed target is accepted with a warning; approval distinct from source confirm; multi-path preflight failure records nothing |
| Capability index | Records round-trip through `capabilities.json`; regeneration preserves Notes; approval and review columns come from records and snapshots, never front matter; linking via each of the three paths is additive and idempotent (a second link keeps the first, a repeated link adds nothing); coverage shows the weakest linked state with counts; `check` warns on a stale table |
| Board/doctor/active | Baselines absent from implementation queue and from the session-start IN FLIGHT list, visible in review and `--all`; pending imports visible; active feature/bug unchanged; baseline-only docs do not establish practicing stage; `adopt-specs` at a workspace covers child repos |
| Discovery | Active/legacy candidates retain evidence; scans bounded, unsupported patterns/truncation visible; no secrets or out-of-root links read; old keys preserved |
| Import | Body bytes unchanged; dry run writes nothing; idempotent; foreign metadata preserved or conflict reported; drafts not auto-completed; mixed scope/collisions/nonstandard names handled explicitly |
| Freshness | Related source/test changes or deletions trigger review; unrelated files do not; works without git; source confirmation cannot approve changed requirements |
| Feature lifecycle | Amendment edits/logs/re-approves baseline; extension preserves guarantees; an approved baseline satisfies `depends_on`, an open discrepancy warns by name, an unapproved or pending import blocks; ordinary planned work retains all existing gates |
| Bug lifecycle | Missing expectation does not become fictional historical approval; intended guarantee differs from broken observation; regression fails before fix and passes after |
| Contracts/hosts | Standalone/workspace ownership correct; versions preserved and dates separate; signoffs and human-only multi-path approvals work in supported hosts |
| Packaging | New modules/skills/template/adapters packaged; standard and plugin version tests updated independently |

Extend existing onboarding, check, flow, lifecycle, freshness, hooks, shell, people, change-protocol
and packaging suites; add focused baseline tests as needed. Test behaviour, not just metadata fields.

## 12. Manual acceptance and definition of done

Use disposable sandbox repositories; never mutate llm-gateway or legaldb as an automated acceptance
step. Real repos are read-only evidence sources unless their user explicitly requests adoption.
Add sandbox fixtures for (a) active code with no specs, (b) mixed legacy specs, and (c) a standalone
consumed API. Legacy fixtures include completed, draft, partially implemented and archived examples.

Each step is labelled with the delivery slice (§10) that makes it possible. A slice is done when
its labelled steps pass; steps labelled for a later slice are not part of an earlier slice's
definition of done.

### No-spec path, based on legaldb

1. *(slice 1, capability candidates from existing discovery; slice 3 improves them)* Bootstrap
   discovers search, billing and answer capabilities, distinguishing legacy/planned work.
2. *(slice 1)* The agent explains evidence and interviews about purpose, constraints, known defects
   and what must be preserved. It persists answers and resumes correctly after a session interruption.
3. *(slice 1)* Select search and billing initially; remaining active capabilities are explicitly
   deferred and visible in the capability table.
4. *(slice 1 for baselines and constitution candidates; slice 3 for the contract)* Draft/review
   baselines and constitution candidates; confirm an API consumer and draft a contract if
   applicable. Unknown historical rationale does not block clear expected behaviour.
5. *(slice 1)* Human approves selected baselines in one command. Status shows coverage and no
   fabricated implementation tasks.
6. *(slice 1)* Request a search change. Interview selects an amendment/extension, records
   preservation requirements and follows the normal RFC/spec approval path.
7. *(slice 1 for the Changes entry and evidence update; slice 2 for source-review state)*
   Implement in the sandbox; verify the relevant baseline changes, Changes entry, evidence and
   regression coverage are updated. Source-review state returns current after review.
8. *(slice 1)* Request a change touching a deferred capability. A bounded baseline interview
   happens first, without restarting the full bootstrap or replacing the active feature.

### Legacy-spec path, based on llm-gateway

All five steps are slice 1.

1. `adopt-specs --dry-run` reports candidates and their actual labels, tasks and section gaps;
   filesystem and approval records remain unchanged.
2. Import preserves bodies and metadata, marks candidates pending and displays the review queue.
   Draft/Approved labels never declare completion automatically.
3. Reconcile one implemented capability into a baseline, retain one ongoing feature as planned,
   and archive or split another with the user's agreement.
4. Approve the baseline manually. It becomes usable as a reference and stays visible under
   `board --all`; ongoing work remains visible and receives its genuine migration actions.
5. Re-run import/check/status. No duplicate content or exceptions; errors/warnings reflect real
   unresolved items. Do not require zero errors for unresolved planned work.

### Definition of done, by slice

- **Slice 1:** both paths work end to end for their slice-1 steps, normal planned-feature gates
  remain intact, user answers survive sessions, approval depends only on the document itself, deferred and
  uncertain coverage is visible, no production code moves and no historical approvals are invented.
- **Slice 2:** source review is recorded separately from approval, related source changes trigger
  review, unrelated changes do not, and no-spec step 7 passes in full.
- **Slice 3:** discovery candidates improve step 1, and a shared contract receives explicit human
  provider/consumer review with the engine warning on missing named reviewers (step 4).
- **Overall:** future work updates the references it relies on.
