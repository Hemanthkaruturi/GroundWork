# The Groundwork Standard

**Version 0.7.0** · the specification that `groundwork check` enforces and the templates implement.

Everything a team or an agent needs to know to work "the Groundwork way" is here. If two
projects follow the same version of this document, a person or an agent moving between them
finds the same files in the same places, with the same sections, in the same order, and the
same meaning for every state. That sameness is the point.

Keywords MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119. Every MUST is a numbered
rule (`GWnnn`, §9) that `groundwork check` can verify without a model.

---

## 1. Principles

1. **Write it down before you build it.** The agent is a craftsman who never sat in the design review; anything it needs must exist as a document.
2. **Humans decide; agents draft.** Agents write documents and code. Only a human approves.
3. **Structure is fixed, content is free.** The standard fixes *where* things live and *what sections exist*. It never dictates what a team decides.
4. **Never guess.** An unknown is written down as a marker, and blocks progress until answered.
5. **Every artifact has a reader.** One page beats ten. Docs live beside the code and change in the same change.

## 2. Levels

| Level | Definition | Detected as |
| --- | --- | --- |
| **workspace** | The folder above the repositories of one application. Owns product-level truth and cross-repo boundaries. | Contains child git repositories, or declares itself (`.groundwork/config.json` `"level": "workspace"`), or holds `PROJECT.md` above a repo |
| **repo** | A git repository with application code, inside a workspace. Owns its own craft. | Git root with a workspace above it |
| **standalone** | A git repository with no workspace. Carries both sets of documents. | Git root, no workspace |
| **unknown** | Neither. Nothing may be built here. | — |

A repo reads *upward*. Anything two repos must agree on is decided in the workspace first (§5),
then built in each repo against it. A change that needs another repo is never a quiet edit there.

## 3. Layout

```
<workspace>/                      <repo>/  (also at standalone root)
  PROJECT.md                        ARCHITECTURE.md
  ARCHITECTURE.md                   AGENTS.md, CODEMAP.md (generated, §5g)
  CONSTITUTION.md                   specs/NNN-slug/{spec,plan,tasks,evals,handover}.md  (+ log.md, append-only notes)
  AGENTS.md                         bugs/NNN-slug.md   (one record per defect)
  CONTRACTS/
  DECISIONS/RFC-NNNN-slug.md        .groundwork/       (approvals.json, freshness.json, config.json)
  DECISIONS/README.md  (index)
  DECISIONS/handovers/RFC-NNNN.md  (cross-repo handover)
  .groundwork/  (approvals.json, freshness.json, config.json)
```

| Level | Required (MUST exist and be finished) |
| --- | --- |
| workspace | `PROJECT.md`, `ARCHITECTURE.md`, `CONSTITUTION.md`, `AGENTS.md`, `CONTRACTS/`, `DECISIONS/` |
| repo | `ARCHITECTURE.md`, `AGENTS.md` (and the workspace above satisfies its own list) |
| standalone | `PROJECT.md`, `ARCHITECTURE.md`, `CONSTITUTION.md`, `AGENTS.md`, `DECISIONS/` |

RFCs live in the workspace `DECISIONS/` (in the repo's own `DECISIONS/` when standalone). Specs
live in the repo that builds them. File names are case-insensitive on lookup; the canonical
spelling is as shown.

## 4. Documents and their required sections

A document is **unfinished** while it contains `[TODO…]` or `[NEEDS CLARIFICATION…]`. Unfinished
documents cannot be approved. Section names below are matched case-insensitively as prefixes, so
`## 8. Cross-repo contract (only if …)` satisfies "Cross-repo contract".

**PROJECT.md** — business, not technical; who works on what. `##` sections: *What this is · Who it is for · Why now / what success looks like · Scope · Who works on what · Stakeholders and decision makers · Repositories in this product · Glossary*.

**ARCHITECTURE.md** — *Overview · Components and repositories · Data flow · Tech stack and tools · Deployment and environments · Boundaries and contracts · Cross-cutting concerns · Local development*.

**CONSTITUTION.md** — the non-negotiable rules; every RFC and spec is checked against it. *Principles · Guardrails · Quality gates · Amendments*.

**AGENTS.md** — instructions for agents: what to read first, exact commands, conventions. Free-form, but MUST be finished.

**RFC** (`DECISIONS/RFC-NNNN-slug.md`) — records a decision. Front matter: `id, title, status, classification (internal|api), signoffs_required, author, created`. Numbered `##` sections, in order: *1 Summary · 2 The need · 3 Interview record · 4 Proposal · 5 Alternatives considered · 6 Risks and objections · 7 Impact · 8 Cross-repo contract · 9 Out of scope · 10 Open questions*.
An `api` RFC (one that crosses a repository boundary) MUST fill §8 and MUST require at least two sign-offs — one for every lead it touches.

**Spec** (`specs/NNN-slug/spec.md`) — *what and why*, never *how*. Front matter: `id` (= directory name), `rfc`, `title`, `status`, `created`, `author`, the ownership roles (§5e), and the relations `extends`, `depends_on`, `builds_against`, `amends` (§5c). An amended spec gains a `## Changes` section after the required ones. Numbered sections: *1 Problem · 2 Users and context · 3 User stories · 4 Functional requirements · 5 Non-functional requirements · 6 Acceptance criteria · 7 Failure behaviour · 8 Manual test · 9 Out of scope · 10 Constitution check*.

**Plan** (`plan.md`) — *how*. Numbered: *1 Approach · 2 Affected modules and files · 3 Data model and migrations · 4 Interfaces and contracts · 5 Failure modes and edge cases · 6 Test strategy · 7 Rollout and rollback · 8 Constitution check*.

**Tasks** (`tasks.md`) — closing tasks `T900+` include T903, the docs-refresh check. Each task `- [ ] **T001** — title` followed by `**Files:**`, `**Done when:**`, `**Covers:** FR-n`. Verification tasks are numbered `T900+` and need no `Covers`.

**Evals** (`evals.md`) — written *before* the code: scenarios with input, expected result, the requirement covered, how it is checked.

**Contracts** (`CONTRACTS/*.md`) — provider, consumers, semver version, every operation with shapes and a real example, failure semantics, compatibility rules. A shipped contract is never changed in a breaking way in place.

**Handover** — two files, never a repo-root one. `specs/NNN-slug/handover.md` (repo-local: what changed · done / in progress / deferred · contracts used · known limits · how to run, test, deploy · next three actions). `DECISIONS/handovers/RFC-NNNN.md` in the workspace, for an `api` RFC only (why and rejected alternatives · repos and their spec handovers · deploy order across repos · contract state). Each fact has one owner; the spec handover links to the RFC handover. Committed with the last task; once deployed, durable facts fold into ARCHITECTURE.md / CONTRACTS / the RFC and the handover is closed or deleted.

## 5. The path (never skip forward)

```
interview → RFC → [approve] → spec → [approve] → plan → tasks → evals → implement → handover
```

1. **Interview.** Before any RFC, the agent questions the human until the picture is unambiguous, and records the exchange in RFC §3.
2. **RFC.** Decides. Classified `internal` or `api`. Filed in `DECISIONS/` and indexed in `DECISIONS/README.md`.
3. **Spec.** Descends from exactly one approved RFC (`rfc:` front matter). One spec per repo touched.
4. **Plan, tasks, evals.** Complete before code. Evals are written *before* implementation.
5. **Implement.** One task at a time; checks green after each; docs updated in the same change.
6. **Handover.** So the next engineer or agent continues without reverse-engineering decisions.

A change of behaviour changes the spec in the same change. A bug is a violated spec; if none covers it, the spec has a gap.

## 5a. Freshness — documents must keep matching reality

A foundation document (`PROJECT`, `ARCHITECTURE`, `CONSTITUTION`, `AGENTS`) is *confirmed* when someone records, in
`.groundwork/freshness.json` (committed), that it matches reality **together with a snapshot of what it is derived from**.
Later the current snapshot is compared with the baseline; each difference is a reason the document may be stale.

| Document | Derived from (snapshot) |
| --- | --- |
| repo `ARCHITECTURE.md` | manifests, Dockerfiles/compose, CI, infra (`*.tf`, `k8s/`, `helm/`), migrations, API schemas; top-level folders; the code layout decision (standalone: approved RFCs) |
| repo `AGENTS.md` | manifests, `Makefile`/task runners, CI — the things that define commands |
| workspace `ARCHITECTURE.md` | the set of repos, each repo's `ARCHITECTURE.md`, `CONTRACTS/*`, approved RFCs |
| workspace `PROJECT.md`, `AGENTS.md` | the set of repos |
| any document | age — not confirmed for more than `freshness_days` (default 90) |

- Snapshots are content hashes, not git history, so drift is detected with no commits, after rebases, in shallow CI clones, and when a teammate changed the repo by hand without any agent.
- A repo's work can make its **workspace's** documents stale; repo sessions therefore report both.
- Staleness never blocks work by itself (GW050 is a warning); `check --strict` in CI is what makes it binding.
- Updating a document and running `confirm` is the refresh. Only verified documents may be confirmed, and never one with unresolved markers.
- Finishing a feature (task T903) and any handover REQUIRE a refresh first.

## 5a″. Communication: short, plain, decision-first

People must be able to read what agents write and decide from it. Agents MUST write replies and documents for a busy reader:

- **Replies:** the answer or the decision needed comes first; about 150 words unless more is asked for; short sentences and everyday words; no bare identifiers or jargon (say what `FR-6` or `GW026` *means*); no retelling of the steps taken — say what changed, what was verified, what was not, and what happens next. Anything long goes into a file, with a five-line summary in the reply.
- **Short never means less.** Cut repetition, narration of steps, and background the reader already has — never these: the decision the user must make; anything that failed or was skipped; what was *not* verified or is uncertain; risks and side effects; every file or setting changed; assumptions; blockers; what the user must do next. Detail that does not fit moves to a linked file (`Full detail: <path>`); it is never dropped. Documents are likewise split or linked, never stripped of a requirement, decision or caveat to meet a budget.
- **Questions** are asked with the selectable picker, never as a list in text: one sentence, 2–4 options, each with a label of at most five words and a description of what happens if chosen (at most fifteen), the recommendation first with its reason.
- **Approval requests** state in three lines what the document decides, what is being signed, and the one thing most worth checking.
- **Documents** lead with the decision or requirement. Soft budgets, checked by `groundwork check` (words of prose; front matter, comments, code and tables excluded): spec 1200 · RFC 1800 · plan 1200 · bug 700 · PROJECT 900 · ARCHITECTURE 1600 · CONSTITUTION 700 · AGENTS 900 · HANDOVER 900 (GW090), and sentences averaging at most 26 words (GW091). Both are warnings; `"brevity": "off"` disables them.
- **Enforcement of replies (optional):** with `"brevity": "enforce"` in `.groundwork/config.json`, a Stop hook counts the words of prose in the agent's reply (code blocks and tables excluded) and, if it exceeds `max_reply_words` (default 220), sends it back once to be rewritten shorter and plainer. **Nothing is lost:** the original is first saved to `.groundwork/replies/<timestamp>.md` (git-ignored), the rewrite is told the must-keep list above, and it ends with a link to the full text. Default is `guide`: the rules are stated at session start and on every prompt.

## 5a′. Documents flow downstream

`RFC → spec → plan → tasks → evals → code`. A downstream document MUST NOT change an upstream one silently. Planning and coding legitimately discover problems upstream; they travel up only through an **explicit amendment**:

1. state the evidence; classify it (*wording* · *ambiguity/contradiction* · *new scope or a different decision*, which goes back to the RFC);
2. **the human chooses** which reading is right (the agent presents the options; it does not pick and edit);
3. the upstream document is amended and a dated line recording **what changed and why** is added under its `## Changes` section (after the required sections) — a previously approved spec MAY NOT be re-approved without a new such line;
4. the human re-approves it; everything downstream is provisional until then;
5. downstream documents are re-verified against the *current* spec and pinned to it: `plan.md`, `tasks.md` and `evals.md` carry `spec_version` (a hash of the approved spec body), set by `groundwork.py plan-sync`. If the spec changes afterwards, code edits stay blocked (and GW037 fails) until they are re-verified and re-pinned.

A doubt that cannot be resolved immediately is written into the document as `[NEEDS CLARIFICATION: …]` — never left as a remark in conversation.

## 5b. Resuming work

Work in flight MUST be recoverable from files alone — never from an agent's or a person's memory.

- **Persist as you go.** During the interview the RFC draft is created after the first round and every question and answer is recorded in its §3 immediately. A closed session therefore loses nothing.
- **The board.** `groundwork.py board` derives everything in flight — RFCs being drafted, in review, or approved with no spec yet; features and the first unmet step of their pipeline; open bugs — with the single next action, the last note, and what blocks it. Active work sorts first, then the most recently touched. The session start injects it.
- **Notes.** `groundwork.py note "<text>"` appends a dated line to the active feature's `log.md` (else the repo's `.groundwork/journal.md`): where work stopped, the next action, open questions. `log.md` is append-only and committed.
- **Resume, don't restart.** A resuming session reads the notes and the item's documents, does not redo finished steps, and does not re-ask what the RFC's §3 already records.

## 5c. Relationships between features

Every feature is **independent** or declares its relations in spec front matter (`NNN-slug`, or `repo/NNN-slug` across repos of a workspace):

| Field | Meaning | Effect |
| --- | --- | --- |
| `depends_on` | cannot be built until the other is *implemented* | code edits are blocked until then (GW074 if violated) |
| `builds_against` | may be built in parallel once the other's spec is approved and its plan finished (an agreed contract) | blocked until that holds, and again if the base spec goes stale |
| `extends` | adds to an existing feature; the spec covers only the delta | the base must exist (GW070) |
| `amends` | changes behaviour an existing spec defines | the amended spec MUST record it under a dated `## Changes` section naming this feature, and be re-approved (GW072) |

RFCs may `supersede` or be `related_rfcs` to earlier RFCs; a superseded RFC leaves the board. Relations MUST resolve (GW070/GW015) and MUST NOT form a cycle (GW071). Two unfinished features that modify the same base are flagged (GW073). `groundwork.py deps <feature|RFC>` shows what a feature needs and **who is affected** if it changes — consult it before changing behaviour others rely on. The interview MUST ask which relationship the new work has.

## 5d. Bugs

A bug is a **violated or missing requirement**. Each defect gets a record `bugs/NNN-slug.md` with front matter (`id, title, status, severity, classification, violates, amends, rfc, regression_test, author, created`) and numbered sections *1 Report · 2 Reproduction · 3 Diagnosis · 4 Classification · 5 Fix plan · 6 Regression test · 7 Verification*. Status runs `open → diagnosed → fixed → closed`.

| `classification` | Means | Required before code edits |
| --- | --- | --- |
| `code-bug` | a requirement states the right behaviour; the code violates it | `violates: [FR-n@feature, AC-n@repo/feature, …]` — every one must exist in an **approved, non-stale** spec (several specs is normal) |
| `spec-gap` | the spec is silent, ambiguous or wrong | `amends: [feature, …]`; each spec edited, logged under `## Changes` with this bug's id, and **re-approved** |
| `design-flaw` | the RFC decision itself was wrong | `rfc:` set to a new or amending RFC that is **approved** |

Requirements from different specs that contradict each other are never resolved by the agent: the human decides which is wrong, and it is treated as `spec-gap` or `design-flaw`. Code edits are allowed only while the bug is `diagnosed` (sections 1–6 finished, classification satisfied, `regression_test` named). The regression test is written first and MUST fail before the fix; `fixed`/`closed` require it to exist and §7 to be filled. Fixes that turn out to be new behaviour become features through the ordinary path.

## 5e. Ownership and accountability

For every RFC, feature and bug the project MUST be able to say **whom to contact**. Responsible persons are always **humans** (the git identity of whoever is running the work); an agent is recorded only as `via`.

| Where | What |
| --- | --- |
| `PROJECT.md` → *Who works on what* | the directory: `Person | Role | Owns / ask them about | Contact` |
| Spec / RFC front matter | current responsibility: `requested_by`, `owner`, `implemented_by`, `support` (RFC also `request_source`); bugs: `reported_by`, `owner`, `fixed_by` |
| `.groundwork/ledger.jsonl` (committed, append-only) | history: `created`, `requested`, `owner`, `implemented`, `deployed` (`env`, `version`), `support`, `handover`, `reported`, `fixed` — each with who, when and optional `via` |
| `.groundwork/approvals.json` | who approved which version of a document, and when |

- Created RFCs, features and bugs are owned by their creator; the interview records who **requested** the work and where the request came from.
- `groundwork.py record <event> --ref <ref> …` writes the ledger and the front matter; **CI records deployments** (`record deployed --env prod --version $TAG --by "$ACTOR"`).
- `groundwork.py who <ref>` shows the chain of people and, for a feature, **the owners of everything it depends on or that depends on it**, with contacts; `who --person X` lists what someone is responsible for; `who --all` is the team map.
- Names in roles SHOULD appear in the people table (GW081); approved RFCs/specs SHOULD have a requester and owner (GW080); implemented features SHOULD record an implementer (GW082) and a support contact (GW083). Changing a role does not affect an approval (approvals cover the document body).
- A change that affects a feature owned by someone else MUST prompt the agent to tell the user who that is.

## 5f. Code layout

Documents have fixed places; so can code. Each repo (and standalone) records **one decision** in `.groundwork/config.json` → `"layout"`, made by a human:

| `mode` | Meaning |
| --- | --- |
| `standard` | Code lives in the role folders of a **profile** (below), under a recorded `root` (`src/<app>`, `src`, `internal`, `.`). |
| `keep` | The repo keeps its own structure. New code goes where code of the same kind already lives and copies its patterns; agents MUST NOT create layout folders or move existing code. No layout rule applies. |

An existing codebase is never migrated without being asked: on first onboarding the agent asks *migrate or keep*. A new repo starts `standard`. A workspace holds no code; each repo decides for itself.

**Roles.** `core` — business rules and use cases; no network, database, SDK or environment access; it defines the interfaces it needs. `connectors` — the only code that talks to outside systems (LLMs, databases, HTTP APIs, queues, email, cloud SDKs), one sub-folder per system named by role (`llm/`, `database/`), the vendor inside. `entrypoints` — HTTP routes, CLI commands, workers; parse, call core, reply. `config` — the only code that reads environment variables and secrets. `prompts` — prompt texts. `pages`/`components` — screens and UI pieces (web). **Wiring** files (`app.*`, `main.*`, `index.*`, `__init__.*` … directly in `root`, `cmd/`, and any listed in `wiring`) build connectors from config and hand them to core; they may import anything.

| Profile | Required | May import (a role may always import itself) |
| --- | --- | --- |
| `service`, `cli` | core, entrypoints | core → prompts · connectors → core, config, prompts · entrypoints → core, config |
| `web` | pages, components, core | pages → components, core, config · components → core · core → connectors, config, prompts · connectors → config |
| `library` | core | connectors → core, prompts · core → prompts; environment reads are not allowed anywhere |

**Adopting it in an existing repo** (`mode: standard` on old code): `folders` maps existing folders to a role (they count as that role, alongside the standard folder where new code goes); `legacy` lists folders not yet migrated, which are exempt. Moving code is ordinary planned work (RFC/spec, tasks), never a side effect.

The checks are static (imports in Python, JavaScript/TypeScript and Go; environment reads; folder names) and need no model. Tests (`tests/`, `test_*.py`, `*.test.ts`, `*_test.go` …) are exempt. `groundwork.py layout` prints the map; `layout init|keep|map` records the decision. The session start tells the agent the map, or that the repo keeps its own structure.

## 5g. Code map

Every repo and standalone has **`CODEMAP.md`**, whatever its layout decision: it tells people and agents where each kind of code lives, so nobody searches the whole codebase.

- `groundwork.py codemap` generates it from the code: each code folder (to four levels), its role (standard layout) and file count; the outside systems called and from where; where environment variables are read; entry and wiring files; test folders. `init` and `scaffold` create it; `layout init|keep|map` refresh it.
- Humans and agents write only the **Holds** column (one line per folder: what it holds) and the **Notes** section. Both survive regeneration.
- A fingerprint of the facts is embedded. When folders, roles, outside calls or settings locations change, the map is out of date (GW109); adding a file to a known folder does not age it. Regenerate, then describe any new folder (GW108 until done).

## 5h. Credentials

Code reads secrets (API keys, tokens, passwords, connection strings) **only from environment variables**. Locally they come from a **`.env`** file; in production the platform sets them (CI variables, Kubernetes secrets, a secrets manager), and the code does not change.

**Every repo, whatever its layout decision:**
- `.env` and `.env.*` are git-ignored; `.env.example` is not. `init` adds the lines when they are missing and says so (GW110).
- A `.env` file is never committed. One that is counts as leaked: remove it from git and rotate every credential it held (GW111, an error).
- No key, token or private key is written into a file that can be committed (GW113). The check names the file, the line and the kind of key, never the value, and never opens `.env`.

**Repos on the standard layout (§5f):**
- `.env` is loaded in one place, `config/` or the wiring file, and never overrides a variable that is already set: Python `load_dotenv()` (python-dotenv, added with `uv add`), Node `--env-file=.env` or `dotenv`, Go `godotenv`. Loading it anywhere else is an environment read outside config (GW105).
- `.env.example` is committed and lists every variable the code reads, with no real values (GW112). `layout init --create` writes it.
- Front ends hold no secrets: everything a browser app reads is shipped to every visitor (GW114). Libraries never load `.env`; they take settings as arguments.

A repo that keeps its own structure keeps its own way of loading settings; only the three safety rules apply.

## 5i. Code quality

Code comes out the same whoever writes it, and whichever agent, because quality is checked by **tools the repo commits**, not by memory. Each repo records one decision in `.groundwork/config.json` → `"quality"`:

| `mode` | Meaning |
| --- | --- |
| `standard` | GroundWork's toolchain. Python (via `uv`): `ruff format`, `ruff check`, `mypy` (strict), `pytest`. JS/TS: `prettier`, `eslint` with `typescript-eslint` strict, `tsc --noEmit`, `npm test`/`vitest`. Go: `golangci-lint fmt`, `golangci-lint run`, `go vet`, `go test`. The configs ship with GroundWork (`quality init --create` writes them and never overwrites one), and the commands follow the languages present. |
| `keep` | The repo's own tools, recorded as they are (`quality keep` reads Makefile targets, package.json scripts and tool configs). No config is added and no file is reformatted. |

An existing repo is asked before any tool config is added, because a new formatter rewrites every file; adopting the standard makes the reformat its own change. `commands` (and optional `fix`) entries override single steps.

- **`groundwork.py verify`** runs format check, lint, types and tests, and exits 1 if any fails (`--fix` runs the formatter and lint autofix first; `--step` runs one). It runs only when invoked by a person, an agent or CI; no hook executes project tools. A task is done only when verify passes (T900). A rule is never weakened, ignored or skipped to make it pass; a justified suppression names the rule and the reason on the same line.
- **The coding rules** every agent follows are written into AGENTS.md → *Code quality* by `quality init`/`keep`, so agents without the plugin read them too: reuse before writing; smallest change that meets the spec; never swallow errors; validate input at entry points; dependencies only via the package manager; comments say why; domain names; tests that test behaviour and mock only connectors; the project's logger and no secrets in logs; small files.

## 6. Identifiers and traceability

- Requirements are numbered in the spec: `**FR-n**`, `**NFR-n**`, acceptance criteria `**AC-n**`, stories `**US-n**`. IDs are unique within a spec and never reused.
- Every AC MUST cite the requirement it proves (`(covers FR-1)`).
- Every FR MUST be covered by at least one task (`**Covers:**`), and every AC MUST appear in `evals.md`.
- Tasks and ACs MUST NOT cite a requirement that does not exist.

## 7. Approval

- Approval is a **human act**, recorded in `.groundwork/approvals.json` as a hash of the document body plus the signers.
- A document's approval is valid only while its body is unchanged. Editing it makes the approval **stale** and it must be given again. The `status:` line in the front matter is a courtesy display; the record is the truth.
- A document with `signoffs_required: N` is approved when N distinct people have approved the same body.
- A document MUST NOT be approved while unfinished.
- An agent MUST NOT create, edit or run anything that produces an approval record.
- The gate applies to every route by which code is written, not only the editor tools: shell redirections and heredocs, `tee`, `sed -i`, `cp`/`mv`, downloads saved to files, `patch`/`git apply` and inline interpreter scripts that write files are judged exactly like a Write. These are proposed agent tool commands that the gate parses for write targets; the plugin never executes them. (A script *file* that writes files when run is opaque to static analysis and is not covered.)
- Other skills and plugins are craft tools for the implement step and do not exempt any part of the path: a request to change how something *looks* is a change request like any other.
- Implementation MUST NOT begin (no task marked `[~]` or `[x]`) until the spec is approved, and the spec may be approved only under an approved RFC.

**States:** `draft` (no approval) · `in-review` (some but not all sign-offs) · `approved` · `stale` (edited since approval).

## 8. Tunable vs fixed

| Fixed by the standard (MUST NOT change) | Tunable by a team (via `.groundwork/config.json`) |
| --- | --- |
| Level model, layout, required files (§3) | `enforcement`: `block` (default) · `warn` · `off` |
| Section names and order (§4) | Extra sections *added after* the required ones |
| The path and its order (§5) | Extra content in `AGENTS.md`, `CONSTITUTION.md` |
| ID formats and traceability (§6) | `signoffs_required` per RFC (never below 2 for `api`) |
| Approval semantics (§7); freshness semantics (§5a) | Who the humans are |
| Rule ids and meanings (§9) | — |

`layout` (§5f) is a team decision recorded once per repo; only the human changes it. Optional `freshness_days`, `brevity` (`guide` | `enforce` | `off`), `max_reply_words`. `"standard": "<version>"` SHOULD be recorded in `.groundwork/config.json` (GW004 warns if not; `scaffold` writes it). Implementations refuse a
project whose **major** version differs from their own. Minor versions add checks or optional
sections; they never invalidate a conforming project.

### Tooling defaults (fixed)

- **Python projects use `uv`** — `uv add`, `uv sync`, `uv run`; never `pip`, `python -m pip` or `python -m venv`. `uv.lock` is committed and never
  edited by hand. This is stated to agents at every session start and in the generated `AGENTS.md`. When onboarding finds another Python
  manager (pip requirements, poetry, pipenv, conda), the agent asks before migrating; it never switches silently.

## 9. Rule catalogue

`groundwork check` reports one finding per violation. **E** = error (exit 1), **W** = warning (exit 1 only under `--strict`).

| Id | Sev | Rule |
| --- | --- | --- |
| GW001 | E | A required file or directory for the level is missing (§3) |
| GW002 | W | A foundation document is unfinished |
| GW003 | E | A finished foundation document lacks a required section (§4) |
| GW004 | W | No `standard` version recorded |
| GW005 | E | The project's standard has a different major version |
| GW010 | E | RFC front matter missing, wrong id, bad classification or sign-off count |
| GW011 | E | A finished RFC lacks a required numbered section, or they are out of order |
| GW012 | E | An `api` RFC lacks a §8 contract or requires fewer than 2 sign-offs |
| GW013 | E | An RFC claims `approved` but its approval is invalid (stale or forged) |
| GW014 | W | An RFC is not listed in `DECISIONS/README.md` |
| GW020 | E | A feature directory is not `NNN-slug` or lacks one of spec/plan/tasks/evals |
| GW021 | E | A spec's `rfc` does not exist, its `id` mismatches the directory, or it is approved under an unapproved RFC |
| GW022 | E | A finished spec lacks a required section |
| GW023 | E/W | Requirement ids duplicated, missing, unknown, or an AC that cites nothing (E); an FR proven by no AC (W) |
| GW024 | E | A finished spec's Manual test is empty |
| GW025 | W | A document of a feature is unfinished |
| GW026 | E | A spec claims `approved` but its approval is invalid |
| GW030 | E | A finished plan lacks a required section |
| GW031 | E | A task lacks Files / Done when / Covers, cites an unknown requirement, duplicates an id, or there are no implementation tasks |
| GW032 | E | An FR is covered by no task |
| GW033 | E | An AC has no evaluation scenario |
| GW034 | E | Tasks are started while the spec is not approved |
| GW035 | W | No verification tasks (`T900+`) |
| GW050 | W | A finished foundation document may be stale: its snapshot, or its age, differs from the confirmed baseline (§5a) |
| GW051 | W | A finished foundation document was never confirmed |
| GW015 | E | An RFC's `supersedes`/`related_rfcs` names an RFC that does not exist |
| GW060 | E | Bug record: bad front matter, id/file mismatch, or unknown status |
| GW061 | E | A finished bug record lacks a required section |
| GW062 | E | A diagnosed bug does not meet its classification's requirements (§5d) or names no regression test |
| GW063 | E | A fixed/closed bug: regression test missing, or §7 Verification empty |
| GW064 | W | An open bug record is unfinished |
| GW065 | E | A bug claiming `diagnosed` or later still has unresolved markers |
| GW070 | E | A feature relation does not resolve to a feature |
| GW071 | E | Relations form a cycle |
| GW072 | E | An amended spec does not record the amendment under `## Changes` |
| GW073 | W | Several unfinished features modify the same base at once |
| GW074 | E | Implementation started while `depends_on`/`builds_against` are not ready |
| GW036 | W | A finished plan/tasks/evals is not pinned to a spec version (`plan-sync`) |
| GW037 | E | A finished plan/tasks/evals was written against an earlier version of the spec |
| GW038 | W | Every task is done but the spec has no finished `handover.md` |
| GW039 | W | A repo-root `HANDOVER.md` exists (move it into its spec folder) |
| GW080 | W | An approved RFC or spec has no `requested_by` or no `owner` |
| GW081 | W | A person named in a role is not listed in PROJECT.md's people table |
| GW082 | W | An implemented feature has no `implemented_by` |
| GW083 | W | An implemented feature has no `support` contact |
| GW090 | W | A finished document exceeds its word budget (§5a″) |
| GW091 | W | A finished document's sentences average more than 26 words |
| GW040 | W | An approval record points at a file that no longer exists |
| GW100 | E | The `layout` entry is malformed: unknown mode or profile, a role the profile lacks, or a path outside the repo (§5f) |
| GW101 | W | A folder the profile requires does not exist |
| GW102 | W | A role imports a role the profile does not allow (e.g. core → connectors) |
| GW103 | W | A library or call that reaches an outside system (SDK, HTTP, database, `fetch`) is used outside connectors |
| GW104 | W | Code sits in no role folder (not mapped, not wiring, not legacy) |
| GW105 | W | Environment variables are read outside config (anywhere, in a library) |
| GW106 | W | A folder or file is named `utils`, `helpers`, `common`, `misc`, `shared` or similar |
| GW107 | W | Connector code sits directly in `connectors/` instead of `connectors/<system>/` |
| GW108 | W | A repo has no `CODEMAP.md`, or a folder in it is not described (§5g) |
| GW109 | W | `CODEMAP.md` no longer matches the code |
| GW110 | W | `.env` is not git-ignored (§5h) |
| GW111 | E | A `.env` file is committed to git |
| GW112 | W | Standard layout: no `.env.example`, or a variable the code reads is not listed in it |
| GW113 | W | A file that can be committed contains something that looks like a real key, token or private key |
| GW114 | W | Web profile: front-end code reads a secret-looking environment variable |
| GW120 | E | The `quality` entry is malformed: unknown mode or step, or a bad `max_file_lines` (§5i) |
| GW121 | W | Standard toolchain: a language in the repo has no config for its standard tools |
| GW122 | W | No `lint` or no `test` command, so `verify` cannot check it |
| GW123 | W | Standard toolchain: a code file is longer than `max_file_lines` (default 400; tests exempt) |

Unfinished documents are reported once (GW002/GW025) and otherwise skipped: a scaffold cannot
yet be judged on shape. A finished document is held to the standard in full.

## 10. Conformance

```bash
python3 <plugin>/engine/groundwork.py check            # exit 1 on any error
python3 <plugin>/engine/groundwork.py check --strict   # warnings fail too — use on protected branches
python3 <plugin>/engine/groundwork.py check --json     # machine-readable
```

### Onboarding and health

- `groundwork.py init [--as repo|workspace] [--retrofit] [--dry-run]` classifies the directory, creates only the missing required
  files, records `"standard"`, and writes `.groundwork/discovery.json` — evidence about an existing codebase (stack, manifests, entry
  points, tests, CI/infra, existing docs and ADRs, top contributors) for an agent to draft from. It is idempotent and never overwrites;
  `--retrofit` additively appends missing required sections to existing documents. In a workspace it covers every repo under it.
- `groundwork.py doctor [--json]` is read-only. It places the project on a ladder — **0 Not started** (required docs missing) ·
  **1 Scaffolded** (unfinished, or non-conforming) · **2 Documented** (finished, conforming) · **3 Current** (confirmed, not stale) ·
  **4 Guarded** (git hook or CI enforces the standard) · **5 Practicing** (the RFC → spec path is in use) — and lists ordered next steps.
  A workspace's stage is that of its weakest repo.

### Git hooks

`groundwork.py hooks install [--strict] [--pre-push] [--vendor]` installs `check` as a git `pre-commit` (and optionally `pre-push`) hook.
Errors block; warnings block only with `--strict`. `enforcement: warn|off` in `.groundwork/config.json` is honoured; `--no-verify` or
`GROUNDWORK_SKIP=1` bypasses once. An existing hook is chained, not replaced. Hooks live in `.git/` and are not shared by git, so
`--vendor` copies the engine into `.groundwork/engine/` (commit it): every teammate can then run
`python3 .groundwork/engine/groundwork.py hooks install`, and CI can run the same copy. `hooks uninstall` restores what was there.

`check` needs only Python 3.10+ (tested on 3.12) and the project — no model, no network, no Claude Code — so it
is the same on a laptop, in a git hook and in CI, for humans and for any agent.

A project **conforms to Groundwork 0.7** when `check --strict` reports no findings.

## 11. Changing the standard

The standard is versioned semver. A rule is added, changed or removed only by a change to this
file, made through an RFC in this repository, with the implementing code and tests in the same
change. Rule ids are never reused.
