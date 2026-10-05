# GroundWork

**Coding agents write code fast. GroundWork makes sure they write the right code, the way your team agreed, and that people can always see why.**

GroundWork is a plugin for Claude Code and Devin. It makes the agent follow a shared, written plan: standard documents first, humans approve the important steps, and only then code. It is free and open source (MIT). The rules are enforced by the tool itself, not by asking nicely.

**This is the base document for GroundWork.** It lists every feature, with a real example for each. Marketing material (slides, posts, one-pagers) should be built from it. Examples marked *(real output)* were produced by running the tool on the sample product described in section 5. Examples marked *(illustration)* show what a person or the agent writes or sees, and were not printed by the tool.

**At a glance**

| | |
| --- | --- |
| 17 skills | one for each step of the path, plus resume, refresh, bugs, ownership, code layout and plain writing |
| 6 hooks | the gate before edits and shell commands, session awareness, reminders, reply length |
| 56 numbered rules | checked with no AI and no network, on a laptop, in a git hook and in CI |
| 184 automated tests | the whole lifecycle, and every rule has a test that breaks exactly that rule |
| 2 coding agents | Claude Code, and Devin (CLI and Desktop), from the same plugin |
| 3 platforms | Linux, macOS and Windows, tested on Python 3.10 and 3.12 |
| 0 network calls | it runs on your machine, collects nothing and sends nothing |

---

## Feature index

Every feature, in one line, with where to see it.

| Feature | What it does for you | See |
| --- | --- | --- |
| **Path from idea to code** | Interview, RFC, spec, plan, tasks, evals, code, handover, in that order, with no skipping | §3 |
| **The gate** | Blocks code edits, including shell tricks, until the earlier steps are approved | 5.3 |
| **Human-only approval** | Only a person can approve, recorded against the exact text, with sign-offs and staleness | 5.4, 5.21 |
| **Interview with clickable options** | The agent asks questions as choices, labels each answer, challenges clashes, reads it back | 5.5, 5.19 |
| **Nothing is guessed** | Unknowns become visible markers that block approval | 5.6 |
| **Amendments** | A plan that finds a spec problem must show evidence, let you choose, log the change, and get re-approval | 5.7, 5.24 |
| **Workspaces and repos** | Product-level truth in one place, each repo owns its own craft | 5.1, 5.18 |
| **Constitution and guardrails** | Non-negotiable rules, checked in every RFC, spec and plan | 5.20 |
| **Cross-repo RFCs and contracts** | A change that crosses repos needs a versioned contract and more than one sign-off | 5.21, 5.22 |
| **Evals and traceability** | Every requirement has a task, every acceptance criterion has a test scenario, written before code | 5.23 |
| **Feature and RFC relationships** | depends on, builds against, extends, amends, supersedes, with cycle and clash detection | 5.10, 5.25 |
| **Bug lifecycle** | A bug is a broken requirement: record, diagnose, classify, cite the requirement, test first, prove, close | 5.9 |
| **Resume anywhere** | A work board, notes, and files that survive closed sessions and hand-offs | 5.8 |
| **Handover** | A standard pack so the next person or agent continues without guessing | 5.26 |
| **Ownership and accountability** | Who requested, owns, built, deployed and supports every item, and whom to call | 5.11 |
| **Documents that stay true** | Freshness tracking flags stale documents, including the workspace ones | 5.12 |
| **Onboarding existing projects** | `init` gathers evidence, `doctor` shows how far the project is from the standard | 5.14, 5.18 |
| **Enforcement dial and emergency bypass** | Block, warn or off, and a logged 60-minute bypass for real emergencies | 5.27 |
| **Git hook and CI** | The same check on every commit and every pull request | 5.2, 5.13, 5.28 |
| **Short, plain replies** | Answer first, about 150 words, nothing important lost | 5.15 |
| **Other skills can't skip the process** | A design skill is a tool for the build step, not a shortcut | 5.16 |
| **Sensible defaults** | Python projects use `uv`, never `pip` | 5.17 |
| **Claude Code and Devin** | One plugin, the same gate and documents, in either agent | 5.29, §11 |
| **Private and cross-platform** | Runs locally, no telemetry, works on Linux, macOS and Windows | §8, §10 |
| **Easy to install and update** | Two commands to install, auto-update or one command to update | §11 |

---

## 1. The problem

Coding agents multiply speed. They multiply inconsistency just as fast.

| What happens today | Why it hurts |
| --- | --- |
| The agent starts coding from a one-line request | It builds the wrong thing, fast |
| Each session decides its own way of working | Two agents, two designs, one product |
| Requirements live in chat | Closed the session? The reasoning is gone |
| Nobody records who asked for what | An incident happens and no one knows whom to call |
| Docs are written once and rot | New people and new agents trust wrong information |
| Rules live in someone's head | The agent breaks a team rule it never heard about |
| A change in one repo quietly breaks another | Two teams find out in production |
| Long, chatty answers | People skim, miss the caveat, decide badly |

An agent is a craftsman who never sat in the design review. Everything it needs must be written down.

## 2. The idea

**Standardize the system. Preserve the craftsmanship.**

Fix *where* things live, *what* each document contains, and *who* approves. Leave the actual engineering choices to people and agents. Every project then looks and behaves the same, so anyone can move between projects and pick up work.

## 3. How it works

```
 idea ──▶ interview ──▶ RFC ──▶ [you approve] ──▶ spec ──▶ [you approve]
                                                              │
   handover ◀── implement ◀── evals ◀── tasks ◀── plan ◀──────┘
```

1. **Interview.** The agent asks you questions (as clickable options, not walls of text) until the request is clear. Each answer is labelled: confirmed, tension, open decision, doc update, or out of scope.
2. **RFC.** The answers become a short decision document, with a read-back of what is settled and what is not. You review and approve it. A change that crosses repos also needs a contract and more than one sign-off.
3. **Spec.** What to build and why, with numbered requirements, acceptance criteria and a manual test. You approve it.
4. **Plan, tasks, evals.** How to build it, in small steps that each cite a requirement, and how we'll know it's right, written before any code.
5. **Implement.** One task at a time, with the repo's checks green after each. Documents stay in sync with the code.
6. **Handover.** So the next person, or agent, can continue without guessing.

**The agent cannot skip a step.** Hooks block code edits until the earlier steps are done. This covers the editor tools and shell tricks like `cat > file <<EOF`. Only a human can approve. If someone edits an approved document, the approval becomes stale.

## 4. What you get

### Structure everyone shares
- **Two levels, plus standalone.** A *workspace* holds the product-level truth (project brief, architecture, rules, contracts, decisions). Each *repo* holds its own code, specs and internals. A single repo with no workspace above it is *standalone* and carries both sets of documents. The agent always knows which level it is on, and a directory that is neither is *unknown*: nothing may be built there.
- **Standard documents:** `PROJECT`, `ARCHITECTURE`, `CONSTITUTION` (the non-negotiable rules), `AGENTS`, RFCs, contracts, specs, plans, tasks, evals, bug records, handovers.
- **A written standard** (`STANDARD.md`) with 56 numbered rules. `groundwork check` verifies them with no AI and no network, so it runs the same on a laptop, in a git hook and in CI.

### Humans stay in control
- **Approval is human-only.** Recorded against the exact document text, with who and when. An RFC can require several sign-offs, and a cross-repo one always needs at least two.
- **Nothing is guessed.** Unknowns become visible markers that block approval.
- **Changes go up only through an amendment.** If planning finds a problem in the spec, the agent shows the evidence, *you* pick the reading, the spec gets a dated "what changed and why" line, you re-approve, and the plan is re-checked against the new spec.
- **A dial, not a wall.** Enforcement can be `block`, `warn` or `off` per repo, and a human can lift the gate for an hour in an emergency. Every bypass is logged.

### Rules the team agreed, written down and checked
- **A constitution.** Principles, guardrails ("never…"), quality gates and amendments. Every RFC, spec and plan has a mandatory *Constitution check* section, so a change that breaks a rule has to say so.
- **Checkable rules.** The best guardrails come with a command that fails when the rule is broken, so the agent finds out at once.

### Changes that cross repos
- **Cross-repo RFCs.** An RFC that crosses a repo boundary is classified `api`. It must include a contract and needs at least two sign-offs, one for every lead it touches.
- **Contracts.** Versioned documents in the workspace: what one repo promises another, with real examples, failure behaviour and compatibility rules. A shipped contract is never changed in a breaking way in place.

### Proof before code
- **Traceability.** Requirements are numbered. Every requirement is covered by a task. Every acceptance criterion appears in the evals. The tool refuses to call a feature complete otherwise.
- **Evals first.** The evals (scenarios, edge cases and the odd real-world inputs nobody wrote down) are written before the code, so "done" is defined in advance.
- **Every task says how it is verified.** Each task lists its files, what "done when" means, and which requirement it covers.

### Work survives closed sessions
- **A work board** lists everything in flight, with its next step and last note: RFCs mid-interview, specs without plans, half-built features, open bugs.
- **Notes and resume.** New session, new teammate, new agent: it picks up exactly where work stopped, without re-asking answers.
- **Handover pack.** A standard document for finished or paused work: what was touched, what is done and what is deferred, decisions and rejected alternatives, contracts with examples, known limits, how to run and deploy, who supports it, and the next three actions.

### Real projects are messy, so it handles them
- **Bug lifecycle.** A bug is a broken requirement. Each bug gets a record that moves from *open* to *diagnosed*, *fixed* and *closed*. The fix is blocked until the bug is reproduced, classified (code wrong, spec wrong, or decision wrong), tied to the exact requirements it violates (across several specs if needed), and given a regression test that fails first. It can't be called fixed until that test exists and the verification is written down.
- **Feature relationships.** Each feature is independent, or says how it relates: *depends on*, *builds against* (parallel), *extends*, *amends*. RFCs can *supersede* or relate to earlier RFCs. Cycles, missing targets and clashes are flagged.
- **Existing projects.** `groundwork init` reads a codebase and gathers evidence (stack, tests, CI, contributors). The agent drafts documents from facts and only asks what code can't tell. `groundwork doctor` shows how far a project is from the standard and what to do next.

### Accountability
- For every RFC, feature and bug: **who requested it, who owns it, who implemented it, who deployed it (per environment and version), who supports it.**
- `groundwork who <feature>` answers "whom do I call?" in one screen, including the owners of every feature it depends on or affects.
- Deployments are recorded by CI. History is an append-only file in the repo. The responsible person is always a human.

### Documents that stay true
- **Freshness tracking.** Docs record what they were derived from. If the stack, the repos, a contract or a teammate's architecture changes, the affected docs are flagged as stale, including workspace docs when a repo changes.
- **Git hook.** Optional pre-commit (and pre-push) check that blocks commits which break the standard. It can be copied into the repo so teammates without the plugin and CI use the same check.

### Replies people actually read
- Agents are told to answer first, in about 150 words, in plain words, with no bare jargon.
- **Short never means less.** Decisions needed, failures, unverified items, risks, changed files and next steps must always survive. In strict mode, an over-long reply is saved in full, rewritten short, and linked. Nothing is lost.
- Documents have word budgets and a sentence-length check, as warnings.

### Sensible defaults
- Python projects use `uv`, never `pip`.
- Other skills (like a frontend design skill) are treated as tools for the build step. They can't skip the process.

### Private, portable and easy to keep current
- Runs entirely on your machine. No network requests, no telemetry, no accounts. It reads your local git name and email only to record who did what, and keeps that in your own project files.
- Works on Linux, macOS and Windows. It needs Python 3.10 or newer and git, and nothing else.
- Works in **Claude Code** and in **Devin** (CLI and Desktop). Both agents run the same hooks, skills and engine, so a team can mix them on one project.
- Two commands to install. Auto-update, or one command to update.

## 5. See each feature in action

One sample product is used throughout. **ShopFront** is a workspace called `shop` with two repos, `shop-api` and `shop-web`. The team: **Priya** (product owner), **Ravi** (backend lead), **Meena** (frontend lead), **Sam** (DevOps). Blocks marked *(real output)* were printed by the tool and only lightly trimmed (long file paths are shortened, and where a block shows several findings they may come from separate runs). Blocks marked *(illustration)* show what a person or the agent writes or sees, and were not printed by the tool.

| Theme | Examples |
| --- | --- |
| Getting started | 5.1 awareness · 5.14 existing projects · 5.18 the doctor ladder |
| Control | 5.3 the gate · 5.4 human-only approval · 5.6 nothing guessed · 5.27 enforcement and bypass |
| Interview and decisions | 5.5 the picker · 5.19 labelled answers and read-back · 5.7 and 5.24 amendments |
| Rules and contracts | 5.20 the constitution · 5.21 cross-repo RFC · 5.22 contracts |
| Proof | 5.2 the standard checked · 5.23 evals and traceability |
| Relationships | 5.10 dependencies · 5.25 relations in full |
| Work and people | 5.8 resume · 5.9 bugs · 5.11 who · 5.26 handover |
| Keeping it true | 5.12 freshness · 5.13 and 5.28 git hook and CI |
| Style and defaults | 5.15 short replies · 5.16 other skills · 5.17 `uv` |
| Agents | 5.29 running in Devin |

### 5.1 The agent always knows where it is
`groundwork init` in the empty workspace, then `groundwork doctor` *(real output)*:
```
[shop]     workspace: created PROJECT.md, ARCHITECTURE.md, CONSTITUTION.md, AGENTS.md, CONTRACTS/, DECISIONS/
[shop-api] repo: created ARCHITECTURE.md, AGENTS.md
[shop-web] repo: created ARCHITECTURE.md, AGENTS.md

Stage 1/5: Scaffolded  ●●○○○○
  documents exist but still have unresolved markers
People
  ! no people listed under 'Who works on what' in PROJECT.md — nobody can be contacted about anything
Next steps
  1. fill it in with the bootstrap skill (/groundwork-specflow:bootstrap)
```
After the documents are filled in and confirmed, the same command says `Stage 3/5: Current`, and the next step is "install the git hook" (see 5.18).

### 5.2 Standard documents, checked by a tool
Someone renames a required heading. `groundwork check` (also runs in CI and as a git hook) *(real output)*:
```
ERROR   GW003  PROJECT.md: missing required section(s): Who works on what
         → keep the template's headings; see STANDARD.md §4
ERROR   GW032  shop-api/specs/001-product-search/tasks.md: FR-2 is not covered by any task
warning GW023  shop-api/specs/001-product-search/spec.md: FR-2 is not proven by any acceptance criterion
```
The second and third lines are traceability: every requirement needs a task and a test scenario (see 5.23).

### 5.3 The gate: no code before an approved spec
The agent tries to write `src/search.py` while the spec is still a draft *(real output)*:
```
DENIED: feature '001-product-search' is not ready to build: spec.md is draft, 14 unresolved
marker(s). Write/finish spec.md with the write-spec skill ... Approval is a human act;
you cannot approve documents yourself.
```
It tries the shell instead (`cat > src/search.py <<'EOF' ...`). Same answer, with one extra line:
```
— blocked because this shell command writes src/search.py. The shell is gated exactly like
the Write/Edit tools; do not route around the gate.
```
The gate covers redirections, heredocs, `tee`, `sed -i`, `cp` and `mv`, downloads saved to files, `patch` and `git apply`, and inline scripts that write files.

### 5.4 Only a human approves
The agent tries to approve its own RFC *(real output)*:
```
DENIED: approvals and bypasses are human acts. Ask the user to run
/groundwork-specflow:approve or /groundwork-specflow:bypass themselves.
```
Priya types the command herself:
```
> /groundwork-specflow:approve RFC-0001
RFC-0001-product-search.md: approved (1/1 sign-offs: Priya Nair)
```
If anyone edits the RFC afterwards, its status becomes `stale` and it must be approved again.

### 5.5 Interview with clickable options
Instead of a wall of questions in text, the agent shows a picker *(illustration)*:
```
[Results]  How many results per page?
 ❯ 1. 20 per page (Recommended)   Fits a phone screen without scrolling.
   2. 50 per page                 Fewer taps, but slower on mobile.
   3. Infinite scroll             Smoother to use, harder to test.
   4. Type something
```
Every answer is written into the RFC as it goes, so a closed session loses nothing.

### 5.6 Nothing is guessed
A spec that still has open questions cannot be approved *(real output)*:
```
spec.md still has 14 [TODO]/[NEEDS CLARIFICATION] marker(s). Resolve them before approval.
```

### 5.7 A plan finds a problem in the spec
While planning, the agent notices "rounded" in FR-2 is ambiguous. It shows the evidence and asks Priya which reading she wants (picker). Priya says "nearest cent". Then *(real output)*:
```
> /groundwork-specflow:approve specs/001-product-search/spec.md
this spec was approved before and has changed since. Record what changed and why as a dated
line under '## Changes' ... then approve again.
```
The agent adds the reason to the spec:
```
## Changes
- 2026-09-30: FR-2 now says "nearest cent" (found while planning: "rounded" was ambiguous; Priya chose cents)
```
Priya re-approves. Code is still blocked until the plan is re-checked against the new spec:
```
DENIED: plan.md, tasks.md, evals.md were written against an earlier version of the spec.
Re-read them against the CURRENT spec, fix what no longer matches ..., then run `groundwork.py plan-sync`.
```

### 5.8 Close the laptop, come back tomorrow
Meena stops in the middle of the web feature and leaves a note:
```
groundwork.py note "Paused: waiting for the search API contract details. Next: write the spec.
                    Question for Ravi: max query length?"
```
Next morning, the new session starts with this already in the agent's context *(real output)*:
```
IN FLIGHT:
  - [feature] 001-search-box — spec.md is draft, 14 unresolved marker(s) ← active;
    last note: Paused: waiting for the search API contract details ... Question for Ravi: max query length?
```
She says "continue". The `resume` skill picks up at the spec and asks Ravi's question first. A teammate, or another agent, can do the same. The board lists every kind of item, with its next step:
```
IN FLIGHT (active first, then most recently touched)
 1. [feature] shop-api/001-product-search — building — tasks 0/7  (just now)  ← active
      next: continue the next unchecked task (implement skill)
      owner: priya@shop.example
 2. [rfc] RFC-0002 Search-v2 — drafting — 0 interview answer(s) recorded, 18 open marker(s)  (just now)
      next: continue the interview / finish the RFC (interview, write-rfc skills)
      owner: priya@shop.example
```

### 5.9 Bugs: a bug is a broken requirement
Priya reports "search crashes on an empty query". The first question is whether this is a bug at all. If the approved spec says it should work and it doesn't, it is a bug. If Priya wants behaviour nobody specified, it is a change request and goes through the interview and RFC instead. When the agent can't tell, it asks.

Every bug follows the same path. The status sits in the bug record, and the gate reads it:
```
 report ──▶ open ──────▶ diagnosed ──────▶ fixed ──────────▶ closed
            code blocked   code allowed:     regression test    the reporter
                           test first,       exists and         checked it
                           then the fix      verification       by hand
                                             is written down
```

**1. Record it.** The agent asks who reported it and opens a record in the repo that has the bug *(real output)*:
```
> groundwork.py new-bug empty-query-crash --title "Search crashes on an empty query" --reported-by "Priya Nair"
shop-api/bugs/001-empty-query-crash.md
Active bug set to 001-empty-query-crash. Follow the fix-bug skill.
```
The record has seven fixed sections: *Report* (expected and actual), *Reproduction*, *Diagnosis* (the root cause with `file:line`, not the symptom), *Classification*, *Fix plan* (the smallest change, and what could regress), *Regression test* and *Verification*. Its front matter holds the status, severity, classification, the requirements it violates, the regression test, and who reported, owns and fixed it.

**2. No code until it is diagnosed.** The agent reproduces the bug by actually running it, never by assuming. Until the record is complete, code edits are refused *(real output)*:
```
DENIED: bug '001-empty-query-crash' does not yet allow edits: sections 1–6 still have 8
unresolved marker(s) (use the fix-bug skill).
```
The bug is on the work board, so a new session or a teammate can pick it up *(real output)*:
```
 1. [bug] shop-api/bug 001-empty-query-crash — open (unclassified)  (just now)  ← active
      next: sections 1–6 still have 8 unresolved marker(s) (use the fix-bug skill)
      owner: ravi@shop.example
```

**3. Classify it, and name the requirement.** Every bug is exactly one of three kinds, and each has a requirement the tool checks:

| Kind | What went wrong | What must be true before the fix |
| --- | --- | --- |
| **code-bug** | The spec is right, the code is wrong | `violates:` lists every broken requirement, e.g. `[FR-1@001-product-search, AC-2@shop-web/001-search-box]`. Each one must exist in an approved spec |
| **spec-gap** | The spec is silent, unclear or wrong | Each spec in `amends:` has a dated `## Changes` line naming the bug, and a human has approved it again |
| **design-flaw** | The RFC's decision was wrong | `rfc:` points to a new or amending RFC that a human has approved |

Each requirement is checked against the real documents *(real output, one line per attempt)*:
```
DENIED: ... violates FR-9@001-product-search: no such requirement in that spec
DENIED: ... amends 001-product-search: amend its spec first — add a line for '001-empty-query-crash' under '## Changes'
DENIED: ... amends 001-product-search: the amended spec is stale; the user must re-approve it
DENIED: ... design-flaw needs `rfc:` set to a new or amending RFC (write it with the write-rfc skill)
```
If two specs or RFCs disagree about what is right, the agent never picks a winner. It asks, then treats the wrong one as a spec gap or a design flaw. Amending a spec for a spec gap works like any other amendment (5.7, 5.24): the plan, tasks and evals built on it must be re-checked too.

**4. Regression test first, then the fix.** When the diagnosis is complete the agent sets `status: diagnosed`, but the gate stays shut until the record names its regression test *(real output)*:
```
DENIED: bug '001-empty-query-crash' does not yet allow edits: name the regression test in
`regression_test:` (path relative to the repo) (use the fix-bug skill).
```
With `regression_test: tests/test_search.py::test_empty_query` set, the gate opens. The agent writes the test, runs it and watches it fail for the right reason, and only then fixes the code. A bug that turns out to be a real feature or a redesign stops here: the agent leaves a note and switches to the interview and RFC path.

**5. "Fixed" has to be proven.** Setting `status: fixed` without the test file or a written verification fails the check *(real output)*:
```
ERROR   GW063  shop-api/bugs/001-empty-query-crash.md: regression_test 'tests/test_search.py::test_empty_query' does not exist
ERROR   GW063  shop-api/bugs/001-empty-query-crash.md: §7 Verification is empty
```
*Verification* says what was run, what was seen, and whether the documents changed. If the fix changed something the foundation documents describe, the agent refreshes them first (5.12).

**6. Close it, and keep the record.** The agent tells Priya how to check the fix by hand. When she is satisfied, the status becomes `closed` and the bug leaves the board. Who did what is recorded like any other work *(real output)*:
```
> groundwork.py record fixed --ref bugs/001-empty-query-crash --via claude-code
recorded fixed on bugs/001-empty-query-crash by ravi@shop.example

> groundwork.py who bugs/001-empty-query-crash
bugs/001-empty-query-crash  [bug]  Search crashes on an empty query
  Reported by     Priya Nair (Product owner) — priya@shop.example
  Owner           Ravi Kumar (Backend lead) — ravi@shop.example
  Fixed by        Ravi Kumar (Backend lead) — ravi@shop.example
```

**Several bugs at once.** Each bug has its own record and number. `groundwork.py activate-bug <NNN-slug>` switches which one the gate is checking.

**Emergencies.** If production is on fire, only a human can lift the gate, for an hour and logged (5.27). Afterwards the agent writes the bug record anyway, so the reason and the regression test exist.

**What `check` enforces on bug records**

| Rule | Level | Fails when |
| --- | --- | --- |
| GW060 | error | front matter is wrong, the id doesn't match the file name, or the status is unknown |
| GW061 | error | a completed record is missing a section |
| GW062 | error | a diagnosed bug doesn't meet its kind's requirement (table above), or names no regression test |
| GW063 | error | a fixed or closed bug's regression test doesn't exist, or *Verification* is empty |
| GW064 | warning | an open bug record is still unfinished |
| GW065 | error | a bug claims `diagnosed` or later but still has unresolved markers |

### 5.10 Features that depend on each other
`shop-web/001-search-box` needs the search API. It says so in its spec (`depends_on: [shop-api/001-product-search]`). Until the API is done *(real output)*:
```
DENIED: feature '001-search-box' is not ready to build: waiting on shop-api/001-product-search
(not yet implemented, tasks 0/7). Finish (resume) the features it depends on first. If they can proceed
in parallel against an approved contract, ask the user and move them from depends_on to builds_against.
```
Ravi, working on the API, checks who he affects:
```
> groundwork.py deps shop-api/001-product-search
shop-api/001-product-search
  (independent: no declared relations)
  affects (downstream):
    - shop-web/001-search-box  (depends_on)
```
The same command from the other side shows what a feature needs:
```
> groundwork.py deps shop-web/001-search-box
shop-web/001-search-box
  depends_on      shop-api/001-product-search  [not implemented (tasks 0/7)]
```
Once the API feature is built, the web feature's gate opens. See 5.25 for all four relations.

### 5.11 Who is responsible, and whom to call
An incident in production. Anyone can run one command *(real output)*:
```
> groundwork.py who shop-api/001-product-search
  Requested by        Priya Nair (Product owner) — priya@shop.example
  Owner               Priya Nair (Product owner) — priya@shop.example
  Approved            approved: Priya Nair 2026-09-30
  Implemented by      Ravi Kumar (Backend lead) — ravi@shop.example
  Support             Sam Ortiz (DevOps) — sam@shop.example
  Deployed → staging  1.0.0 by Sam Ortiz (DevOps) — sam@shop.example on 2026-09-30
  Deployed → prod     1.0.1 by Sam Ortiz (DevOps) — sam@shop.example on 2026-09-30

  People to talk to before changing it
    affects shop-web/001-search-box  (depends_on) — owner: Meena Iyer (Frontend lead) — meena@shop.example
```
Deployments are recorded by CI with one line: `groundwork.py record deployed --ref 001-product-search --env prod --version 1.0.1 --by "$ACTOR"`.
Other views: `who --person meena@shop.example` lists everything Meena is responsible for, and `who --all` prints the team map:
```
ITEM                         OWNER        REQUESTED BY   IMPLEMENTED BY   SUPPORT
RFC-0001-product-search      Priya Nair   Priya Nair     -                -
shop-api/001-product-search  Priya Nair   Priya Nair     Ravi Kumar       Sam Ortiz
shop-web/001-search-box      Meena Iyer   Priya Nair     -                -
```

### 5.12 Documents that don't rot
A teammate adds `package.json` and a `src/` folder to `shop-api` without any agent. `groundwork fresh` *(real output)*:
```
STALE       ARCHITECTURE.md
            - signals added: package.json
            - toplevel added: src
STALE       AGENTS.md
            - signals added: package.json
FRESH       workspace/PROJECT.md
STALE       workspace/ARCHITECTURE.md
            - contracts added: shop-search-api.md
            - rfcs added: RFC-0001-product-search
FRESH       workspace/CONSTITUTION.md
FRESH       workspace/AGENTS.md
Update what changed (refresh skill), then run: groundwork.py confirm <doc>
```
`groundwork check` names the same documents. The workspace `ARCHITECTURE.md` is flagged too, because a new approved decision and a new contract exist. The `refresh` skill updates only what changed, and `confirm` records the new baseline. Finishing a feature and any handover require a refresh first.

### 5.13 A git hook that enforces it
```
> groundwork.py hooks install
shop-api: installed pre-commit

> git commit -m "x"        # after deleting ARCHITECTURE.md
ERROR   GW001  shop-api/ARCHITECTURE.md: required foundation item is missing
2 error(s), 2 warning(s)
groundwork-specflow: commit blocked. Fix the findings above, or bypass once with --no-verify.
```

### 5.14 Adding it to an existing project
`groundwork init --dry-run` in a project that already has code, and nothing is written *(real output)*:
```
[legacy] standalone: would create PROJECT.md, ARCHITECTURE.md, CONSTITUTION.md, AGENTS.md, DECISIONS/
  languages:    Python (2)
  manifests:    requirements.txt
  entry points: src/app.py
  tests:        1 test file(s) in tests
  python:       uv not in use; other managers found: pip (ask before migrating)
```
The agent then drafts the documents from this evidence and asks only what code cannot tell. It can adopt an existing constitution, ADRs and `CLAUDE.md`. `init --retrofit` adds missing sections to existing documents without touching your text.

### 5.15 Short, plain replies that lose nothing
Asked to explain a hash map, the agent first wrote 404 words. In strict mode the tool saves that text, sends it back, and the agent rewrites it *(real output)*:
```
A hash map turns a key into an array position, so lookups take about constant time.

- Collisions: two keys can share a slot. Fix it with a small list per slot, or by probing nearby slots.
- Resizing: when the map gets full, it allocates a bigger array and re-places every entry.
- Common bug: changing a key after inserting it. Its hash changes, so the entry can't be found.
- Unsure: the exact resize thresholds in each language. I didn't verify them.

I changed no files.
Full detail: .groundwork/replies/20260929-205927.md
```
92 words. The caveat, the risk and "I changed no files" survived. The full original is one click away.

### 5.16 Other skills can't skip the process
Asked "the UI looks like an old website, give it a modern look", with a design skill installed, the agent answered *(real output)*:
> A restyle goes through the project's process (interview, then RFC, spec, plan and so on) before any code changes. I'll start with the interview skill.

It then asked about scope, look and feel, accessibility and screen sizes, and left the file untouched. The design skill comes in later, to build what the approved spec says.

### 5.17 Python projects use `uv`
Asked to add the `requests` library, the agent ran `uv add requests`, not `pip install` *(real output)*. On an existing project that uses pip, it asks before migrating (see 5.14).

### 5.18 How far along is a project? The doctor ladder
`groundwork doctor` places a project on a six-step ladder and lists the next steps: *Not started, Scaffolded, Documented, Current, Guarded, Practicing*. In a workspace, the stage is that of its weakest repo. Once ShopFront's documents are finished and confirmed *(real output)*:
```
Groundwork doctor — shop (workspace)

Stage 3/5: Current  ●●●●○○
  documents are confirmed against reality and not stale — next stage needs: the standard is enforced automatically (git hook or CI)

Foundation
  ✔ PROJECT.md
  ✔ ARCHITECTURE.md
  ✔ CONSTITUTION.md
  ✔ AGENTS.md
  ✔ CONTRACTS/
  ✔ DECISIONS/
Conformance
  ✔ documents conform to the standard
People
  ✔ 4 people listed with contacts in PROJECT.md

Repo shop-api: stage 3 (Current)
  ! no git hook — commits are not checked automatically

Next steps
  1. [shop-api] groundwork.py hooks install [--vendor]   (no git hook)
  2. [shop-web] groundwork.py hooks install [--vendor]   (no git hook)
```
After the hook is installed in `shop-api`, the same command in that repo says *(real output)*:
```
Stage 4/5: Guarded  ●●●●●○
  the standard is enforced automatically (git hook or CI) — next stage needs: the RFC → spec path is in use
```
Stage 5 (*Practicing*) arrives when the RFC to spec path is in real use.

### 5.19 The interview record: labelled answers and a read-back
Each answer in the RFC's interview record carries an effect label, so the reader sees what is settled and what is not. At the end the agent writes a read-back, and the user confirms it *(illustration: part of a finished RFC)*:
```
## 3. Interview record
| # | Question                              | Answer                                     | Effect       |
| 1 | Who searches, and on what device?     | Shoppers, mostly on phones                 | Confirmed    |
| 3 | Should typos still match?             | Not in the first version                   | Out of scope |
| 5 | The web team wants prices as decimals | Clashes with the rule "money is whole cents" | Tension    |
| 7 | Add a display note to the constitution? | Decide later                             | Doc update   |

### Read-back
- Confirmed: search by name, results show name/price/photo, prices in cents from the API.
- Tensions: decimal prices asked for by web clash with the cents rule; resolved: the API stays in cents.
- Open decisions: None.
- Docs to update after approval: ARCHITECTURE.md (add the search component).
```
The five labels are **Confirmed**, **Tension**, **Open decision**, **Doc update** and **Out of scope**. An open decision goes into the RFC's open questions, which block approval. When an answer clashes with an earlier one, a document or the constitution, the agent must say so and ask which way to go. It never smooths it over. While interviewing, the only file it changes is the RFC draft.

### 5.20 The constitution: rules the whole team agreed
`CONSTITUTION.md` holds *Principles*, *Guardrails* (things that must never happen), *Quality gates* and *Amendments*. Every RFC, spec and plan has a mandatory **Constitution check** section, where the change says how it complies, or says that it does not *(illustration)*:
```
## Guardrails (things that must never happen)
- Card numbers are never stored or logged. Payments go through the payment provider only.
- All calls to a language model go through `get_llm_response` in `shop_api/llm/client.py`.
  No other file imports a model SDK.

## Quality gates (what "done" means)
- `uv run pytest` and `uv run ruff check` pass.
- `grep -rn "import anthropic\|import openai" shop_api | grep -v llm/client.py` finds nothing.
```
The tool checks that the section exists in every plan *(real output)*:
```
ERROR   GW030  shop-api/specs/001-product-search/plan.md: missing/misordered section(s): 8. Constitution check
```
**How the rule is upheld:** the agent reads the constitution during the interview and checks each RFC, spec and plan against it, and the implement step tells it to follow it. The tool checks that the check was done, not that the reasoning is right. To make a rule hold hard, write it as something a reviewer can check in a diff, and put the command that proves it in the quality gates and in `AGENTS.md`. The agent runs the repo's checks and may not mark a task done while one fails. Changing the constitution is always deliberate: the agent proposes an amendment, and never edits it on its own.

### 5.21 A change across repos: a cross-repo RFC needs a contract and two sign-offs
Search touches `shop-api` and `shop-web`, so the RFC is classified `api`. If it has no contract, or asks for only one sign-off, the check refuses it *(real output)*:
```
ERROR   GW012  DECISIONS/RFC-0001-product-search.md: api RFC has no cross-repo contract in §8
ERROR   GW012  DECISIONS/RFC-0001-product-search.md: api RFC needs signoffs_required >= 2 (every lead it touches)
2 error(s), 0 warning(s)
```
With the contract written and two sign-offs required, Priya approves first *(real output)*:
```
> /groundwork-specflow:approve RFC-0001
RFC-0001-product-search.md: in-review (1/2 sign-offs: Priya Nair)
More sign-offs are required; each signer runs /groundwork-specflow:approve.
```
The status shows it waiting, and that the new contract makes a foundation document stale:
```
RFCs: RFC-0001-product-search [in-review]
IN FLIGHT (resume with the resume skill; full list: groundwork.py board):
  - [rfc] RFC-0001 Product-search — in review (1/2 sign-offs) (just now)
DOCS MAY BE STALE (use the refresh skill): ARCHITECTURE.md: contracts added: shop-search-api.md
PHASE: rfc
NEXT: RFC-0001-product-search.md is in-review. Finish it, or get it approved.
```
Ravi, the backend lead, approves second:
```
RFC-0001-product-search.md: approved (2/2 sign-offs: Priya Nair, Ravi Kumar)
```
A spec can only be approved under an approved RFC.

### 5.22 Contracts: what one repo promises another
Contracts live in the workspace's `CONTRACTS/` folder, are versioned, and are the reason two teams do not break each other. The contract that the RFC above produced *(illustration)*:
```
# Contract: Product search API
Provider: shop-api · Consumers: shop-web · Version: 1.0.0

## Operation: search products
GET /v1/search?q=<text>

Response 200
{ "results": [ { "id": "p-101", "name": "Blue Mug", "price_cents": 999, "photo_url": "https://cdn.shop.example/p-101.jpg" } ] }

## Failure semantics
- q missing or empty: 400 {"error": "query_required"}. Not retried.
- Search unavailable: 503 {"error": "search_unavailable"}. Safe to retry after 2 seconds.

## Compatibility
Adding a response field is compatible. Removing or renaming a field, or changing price_cents
to another unit, is breaking and needs version 2.0.0.
```
Every contract states its provider and consumers, its semantic version and changelog, every operation with request and response shapes, at least one real example each, failure semantics, and what counts as breaking. A shipped contract is never changed in a breaking way in place: a new version is added. Consumers record which version they honour, and the plan names the contract version it builds against. (Automatic checks that a repo still honours the version it pinned are on the roadmap.)

### 5.23 Proof before code: evals and traceability
Requirements, tasks and evals are numbered and linked, so nothing is built without a reason and nothing is claimed without proof *(illustration: the ShopFront evals)*:
```
| ID | Scenario     | Input                          | Expected                 | Covers | How checked           |
| E1 | Happy path   | search "mug"                   | "Blue Mug" listed        | AC-1   | test_matches_by_name  |
| E2 | Price format | product at $9.99               | price_cents is 999       | AC-2   | test_price_in_cents   |
| E3 | Empty search | q=                             | 400 query_required       | AC-3   | test_empty_query      |
| E4 | Speed        | 10,000 products, search "mug"  | answers in under 300 ms  | NFR-1  | test_search_speed     |
```
The evals are written before the code. Each task lists its **Files**, what **Done when** means, and which requirement it **Covers**. Every requirement must be covered, and the tool refuses gaps (each line below is from a separate run) *(real output)*:
```
ERROR   GW033  shop-api/specs/001-product-search/evals.md: AC-2 has no evaluation scenario
ERROR   GW032  shop-api/specs/001-product-search/tasks.md: FR-2 is not covered by any task
ERROR   GW031  shop-api/specs/001-product-search/tasks.md: T003 has no 'Covers'
```
Three closing verification tasks are always kept: the full checks pass, every requirement maps to a completed task, and the spec's manual test was run by hand. A refresh of the foundation documents is part of finishing.

### 5.24 A spec edited after approval turns everything downstream red
Someone changes "300 ms" to "200 ms" in an approved spec. The approval is invalid, and the plan, tasks and evals are flagged, because they were written against the old text *(real output)*:
```
ERROR   GW026  shop-api/specs/001-product-search/spec.md: front matter says approved but the approval is invalid (edited after approval)
         → a human must run /groundwork-specflow:approve again
ERROR   GW037  shop-api/specs/001-product-search/plan.md: plan.md was written against an earlier version of the spec (the spec changed since)
         → re-verify it against the current spec, then: groundwork.py plan-sync
```
The agent's next code edit is refused *(real output)*:
```
DENIED: feature '001-product-search' is not ready to build: spec.md is stale. Write/finish spec.md with the write-spec skill,
resolve every [NEEDS CLARIFICATION], then ask the user to run /groundwork-specflow:approve on it.
Approval is a human act (/groundwork-specflow:approve); you cannot approve documents yourself.
```

### 5.25 Relations in full: depends on, builds against, extends, amends, supersedes
Every feature is independent, or declares how it relates to another:

| Relation | Meaning | Effect |
| --- | --- | --- |
| `depends_on` | cannot be built until the other is implemented | code edits are blocked until then |
| `builds_against` | can be built in parallel once the other's spec is approved and its plan finished | blocked until that holds |
| `extends` | adds to an existing feature; the spec covers only the new part | the base must exist |
| `amends` | changes behaviour another spec defines | that spec must log the change and be re-approved |

An RFC can `supersede` an earlier one, or be related to it. A superseded RFC leaves the board *(real output)*:
```
> groundwork.py deps RFC-0001
RFC-0001: specs built from it
  - shop-api/001-product-search
  - RFC-0002-search-v2  (RFC that supersedes/relates to it)
```
The tool catches broken references and loops (from two separate runs) *(real output)*:
```
ERROR   GW015  DECISIONS/RFC-0002-search-v2.md: supersedes: RFC-0042 does not exist
ERROR   GW071  .: dependency cycle: shop-api/001-product-search → shop-web/001-search-box → shop-api/001-product-search
```
The interview always asks which relationship new work has, so it is never left implicit. Two unfinished features that change the same base are flagged as a warning.

### 5.26 Handover: the system, not just the code
When a feature is finished, or work is paused or passed on, the agent writes a handover from what is true and verified. Never a repo-root file: one root file fits only one piece of work. There are two places, each with one job. The spec's own `specs/001-product-search/handover.md` holds repo-local facts. A cross-repo (`api`) RFC also gets one workspace `DECISIONS/handovers/RFC-0001.md` for the why, rejected alternatives and deploy order. Each fact has one owner; the spec handover links to the RFC handover instead of repeating it. It is committed with the last task, and once deployed everywhere the durable facts fold into ARCHITECTURE.md, the contracts and the RFC, and the handover is closed or deleted. First the agent refreshes the foundation documents, so the handover matches reality *(illustration: the spec handover's sections)*:
```
# Handover — Product search
## What this repo changed
## State: done / in progress / deliberately deferred
## Contracts used or provided
## Known limitations and edge cases
## How to run, test and deploy
## Ownership and support
   Owner · Requested by · Implemented by · Deployed by · Support (first contact, escalation, hours)
## Next three recommended actions
```
The test: could a new engineer continue without asking why each major decision was made? If not, the missing reason is written down. Ownership moves with it *(real output)*:
```
> groundwork.py record handover --ref 001-product-search --who "Meena Iyer"
recorded handover on 001-product-search by priya@shop.example → Meena Iyer

> groundwork.py who shop-api/001-product-search
  Owner               Meena Iyer (Frontend lead) — meena@shop.example
  Implemented by      Ravi Kumar (Backend lead) — ravi@shop.example
  History
    2026-09-30T14:07  created     Priya Nair (Product owner) — priya@shop.example
    2026-09-30T14:08  implemented Ravi Kumar (Backend lead) — ravi@shop.example (via claude-code)
    2026-09-30T14:08  handover    Priya Nair (Product owner) — priya@shop.example → Meena Iyer
```

### 5.27 Enforcement dial and emergency bypass
Enforcement is `block` by default. A repo can set `warn` (the gate never blocks; problems still show in `check`) or `off` in `.groundwork/config.json`, or a single session can turn it off with an environment variable. For a real emergency, a human can lift the gate for an hour *(real output)*:
```
> /groundwork-specflow:bypass typo in prod banner
Gate bypassed for 60 minutes in shop-api. Logged to .groundwork/bypass.log.
```
The log says who and why:
```
2026-09-30 14:08:06 priya@shop.example 60min: typo in prod banner
```
The agent cannot run the bypass itself. Any behaviour change still needs the spec updated afterwards.

### 5.28 Git hooks and CI, for people who do not use the plugin
Hooks live in `.git/` and are not shared by git, so the tool can copy its check engine into the repo *(real output)*:
```
> groundwork.py hooks install --vendor --pre-push --strict
shop-api: vendored engine into .groundwork/engine/ (commit it so teammates and CI can use it);
installed pre-commit (strict: warnings also block); installed pre-push (strict: warnings also block)

> groundwork.py hooks status
shop-api: pre-commit [strict], pre-push [strict] + vendored engine
```
After committing `.groundwork/engine/`, every teammate can run `python3 .groundwork/engine/groundwork.py hooks install`, with no plugin. An existing hook of theirs is chained and restored on uninstall. The same copy runs in CI *(illustration)*:
```yaml
# .github/workflows/groundwork.yml
on: [pull_request]
jobs:
  groundwork:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 .groundwork/engine/groundwork.py check --strict
```
`check --strict` treats warnings as failures, so a stale document or a missing owner fails the pull request. `check --json` gives machine-readable output.

### 5.29 Running in Devin
The same plugin runs in Devin's CLI and Desktop app. Devin loads its hooks, skills and engine unchanged, so the gate, approvals, the board and every document work as in Claude Code. The engine sees which agent is calling and answers in that agent's format. Devin edits files with `write`, `edit` and `apply_patch` and runs shell commands with `exec`, and all four are gated. A patch is read file by file, so one allowed document cannot carry a code change past the gate *(real output, from Devin's hook interface)*:
```
{"decision": "block", "reason": "groundwork-specflow: bug '001-empty-query-crash' does not yet allow edits:
 sections 1–6 still have 8 unresolved marker(s) (use the fix-bug skill). Approval and bypass are human acts."}
```
Devin has no clickable picker, so on Devin the session rules ask for questions in rounds instead *(real output)*:
```
8. ASK IN ROUNDS: up to 4 questions per round, each with a short numbered list of options, your recommendation
first and marked (Recommended). Make the round the whole reply, end your turn and wait; write down the answers,
then ask the next round.
```
Approval stays human: the user types `/groundwork-specflow:approve`, and Devin's agent is refused if it tries to run approve itself. Work is recorded `--via devin`, so `who` shows which agent built what.

**Differences to know about.** Devin cloud sessions don't run plugin hooks. There, the skills guide the agent, but nothing blocks a code edit. Devin also runs plugin hooks "best effort": a hook that fails is skipped rather than stopping the session. The git hook and CI check (5.28) close that gap, because they check every commit whichever agent made it.

**Without Devin's plugin system.** Some companies turn Devin plugins off, and then no plugin install loads. For that case, Devin can install GroundWork into the project itself (§11). `setup/install.py` puts the engine in `.devin/groundwork/`, each skill and command in `.devin/skills/`, and the hooks in `.devin/hooks.v1.json`. These are Devin's project skills and hooks, not a plugin. The gate, approvals and documents work the same, and commands have no prefix: `/approve`, `/bypass`, `/status`. The script checks its own install by running the session-start hook the way Devin will. It runs on Linux, macOS, Windows and WSL. Committing `.devin/` gives the whole team GroundWork. That this works while plugins are turned off hasn't been confirmed yet.

## 6. How it helps

| If you are… | You get… |
| --- | --- |
| **A developer** | Clear specs before you code. Fewer rework loops. Know who to call. Pick up a colleague's half-done work. A contract when your change touches another repo. |
| **A tech lead** | Consistent structure across repos and agents. Decisions recorded with reasons. Team rules written in a constitution and checked in every change. A check that runs in CI. |
| **A product owner** | The agent must ask before it builds. Written requirements you can approve. Traceability from request to release. |
| **Support / on-call** | One command to find the owner, implementer, deployer and support contact. |
| **A new joiner** | Read the project brief and architecture. Handover packs. No archaeology. |
| **A team of several repos** | Contracts and sign-offs for changes that cross repos. Dependencies that block the right work at the right time. |
| **Everyone** | Short, plain answers that don't hide the caveat. |

## 7. A 5-minute demo

1. **Awareness.** Start Claude in an empty workspace. Ask "where am I?" It names the level and what's missing.
2. **The gate.** Ask it to create a code file. It is refused and told what to do first.
3. **Bootstrap.** It interviews you with clickable choices and writes the project docs, without inventing facts.
4. **Request a feature.** It asks its questions, labels your answers, writes an RFC with a read-back, and stops for your approval. Try to get it to approve for itself: it refuses.
5. **The shell trick.** Ask it to write a file with a shell heredoc. Denied.
6. **A plan finds a problem.** It shows the evidence and lets you choose. The spec gets a logged change and needs your re-approval.
7. **A rule of the team.** Add a guardrail to the constitution. Watch it show up in the RFC's Constitution check.
8. **Close the session, open a new one.** It shows what's in flight and resumes.
9. **Ask "who owns this?"** One screen with names and contacts.
10. **`groundwork doctor`.** The project's stage and next steps.

The step-by-step version is in `docs/manual-testing.md`.

## 8. What's inside

**17 skills**

| Skill | What it does |
| --- | --- |
| `workflow` | Tells the agent where it is and which step comes next |
| `bootstrap` | Creates and finishes the foundation documents, from evidence, without inventing facts |
| `interview` | Asks until the picture is complete; labels answers; challenges clashes; reads back |
| `write-rfc` | Turns the interview into a decision document and asks for approval |
| `write-spec` | Writes what and why, with numbered requirements and a manual test |
| `write-plan` | Writes how, citing requirements; runs the discovery protocol when the spec is wrong |
| `write-tasks` | Breaks the plan into small, verifiable tasks that each cover a requirement |
| `write-evals` | Writes the scenarios and edge cases that prove it, before code |
| `write-contract` | Writes a versioned cross-repo contract with examples and failure behaviour |
| `implement` | Builds one task at a time, checks green after each, ends with a manual test |
| `handover` | Writes the handover pack for finished or paused work |
| `resume` | Picks up unfinished work from the board, the notes and the documents |
| `refresh` | Brings stale foundation documents back in line with reality |
| `fix-bug` | Runs the bug lifecycle: diagnose, classify, cite, test first, fix |
| `ownership` | Records and looks up who requested, owns, built, deployed and supports |
| `code-layout` | Records each repo's choice (standard code folders, or keep its own structure), says where each kind of code goes, and keeps `CODEMAP.md` current |
| `plain-writing` | Keeps replies and documents short, plain and decision-first |

**6 hooks:** session start (awareness and in-flight work), every prompt (triage and style reminder), before edits and before shell commands (the gate, which can only deny and never approves anything), when another skill loads, and at reply end (optional length limit). The same hook file serves Claude Code and Devin. Its matchers name both agents' tools.

**Commands you type:** `/groundwork-specflow:approve`, `/groundwork-specflow:bypass` (emergencies, logged), `/groundwork-specflow:status`. They are the same in Claude Code and Devin. In Devin, only the user can run them. In a Devin project installed without the plugin system (5.29), they have no prefix: `/approve`, `/bypass`, `/status`.

**A command-line engine** (`groundwork.py`), pure Python with no dependencies and no Claude needed:

| Command | Purpose |
| --- | --- |
| `init`, `doctor` | onboard a project; show its stage and next steps |
| `check`, `check --strict`, `check --json` | verify the 56 rules |
| `status`, `board`, `note`, `activate` | where things stand, what is in flight, where work stopped |
| `new-rfc`, `new-feature`, `new-bug`, `activate-bug`, `plan-sync` | create documents; switch the active bug; pin the plan to the approved spec |
| `approve`, `bypass` | human sign-off and the emergency bypass |
| `deps`, `who`, `record` | relations, responsibility, and recording who did what |
| `fresh`, `confirm` | detect stale documents; record a verified baseline |
| `hooks install`, `hooks status`, `hooks uninstall` | manage the git hook, with `--vendor`, `--pre-push`, `--strict` |
| `layout`, `layout init`, `layout keep`, `layout map` | show or record the repo's code layout: standard folders, or keep the existing structure |
| `codemap`, `codemap --check` | write `CODEMAP.md` (where each kind of code lives) from the code; check it is current |

**Quality:** 184 automated tests cover the whole lifecycle, on Linux, macOS and Windows, on Python 3.10 and 3.12. Every numbered rule has a test that breaks exactly that rule.

**Privacy:** it runs locally, makes no network requests, has no telemetry, and reads no credentials. See `PRIVACY.md`.

## 9. Honest limits

- It guards against drift. It is **not a security boundary.** A script file that writes files when run can't be seen by the shell check.
- Approval proves "a human typed this", not who they are.
- Some checks are judgment calls by the agent (is this a bug or a change request? did the short reply keep every caveat? does this change follow the constitution?). The tool checks that the constitution check was done, not that the reasoning is right. Rules written as a command that fails when broken are enforced for real. The saved originals make mistakes recoverable.
- Contracts are documents: the tool does not yet verify that a repo still honours the contract version it pinned.
- It works with **Claude Code** and **Devin** (CLI and Desktop; Devin cloud sessions get the skills but no hook enforcement). The engine is agent-neutral, so other agents can get a thin adapter.
- It adds steps. That is the point, but tiny fixes need the human-run bypass.

## 10. Questions you may get

**Doesn't this slow us down?** The interview and RFC take minutes. They replace rework. For emergencies, a human can lift the gate for an hour, and it is logged.

**Can the agent cheat?** It can't approve, can't edit approval records, and shell writes are gated. It can still make mistakes of judgment, which is why humans approve the RFC and spec.

**Will it follow our team's rules?** Put them in the constitution. The agent checks every RFC, spec and plan against it. For rules that must never be broken, add a command that fails when the rule is broken, and make it part of the repo's checks.

**Do we have to use it on every project?** No. Turn enforcement down to `warn` or `off` per repo, and adopt it gradually. `init` and `doctor` are made for existing projects.

**What if a teammate doesn't use the plugin?** Commit the small check engine into the repo. Their git hook and your CI enforce the same standard.

**Does it work on Windows and macOS?** Yes. It runs on Linux, macOS and Windows. It needs Python 3.10 or newer (as `python3` or `python`) and git.

**Does it send our code or data anywhere?** No. It makes no network requests and has no telemetry. It reads your local git name and email to record who did what, and keeps that in your own project files.

**Does it work with Devin?** Yes, in the Devin CLI and Desktop app, with the same gate and documents. Devin cloud sessions get the skills but no hook enforcement, so add the git hook or the CI check there (5.28, 5.29). If your company has turned Devin plugins off, let Devin install GroundWork into the project instead (§11).

**Why files, not a database?** Files live with the code, review in pull requests, and any person or agent can read them.

## 11. Get started

Inside Claude Code, run these two commands. Wait for "Successfully added marketplace" before the second:

```
/plugin marketplace add Hemanthkaruturi/GroundWork
/plugin install groundwork-specflow@groundwork-specflow
```

Then open Claude Code in your project and run `/groundwork-specflow:bootstrap`. It explains where it is, interviews you with clickable choices, and writes your project documents without inventing facts. From then on, describe a feature or a bug the way you normally would. The agent starts with questions, writes the RFC, and stops for your approval, which you give with `/groundwork-specflow:approve`.

**To keep it up to date:** run `/plugin`, open **Marketplaces**, select `groundwork-specflow`, and choose **Enable auto-update**. Or update by hand: `/plugin marketplace update groundwork-specflow` in Claude Code, then `claude plugin update groundwork-specflow@groundwork-specflow` in a terminal, and restart.

**Installed it before it was renamed?** It used to be called `groundwork`. If updating fails with `Plugin "groundwork" not found`, run `/plugin install groundwork-specflow@groundwork` once.

**Using Devin?** Let Devin install it. Open Devin in your project and paste this prompt:

```
Install GroundWork into this project. From this project's root, run these two commands, one after the other, exactly as written. They work in any shell, on Linux, macOS, Windows and WSL:

git clone -q --depth 1 https://github.com/Hemanthkaruturi/GroundWork.git .groundwork-install
python3 .groundwork-install/setup/install.py

If `python3` isn't found or opens the Microsoft Store message (common on Windows), run the second command with `py -3` instead, or `python`. If a .groundwork-install folder is already there from an earlier attempt, delete it first. The installer deletes it when it finishes.

Do every step yourself; don't ask me to run anything. If a command fails, show me its error and stop there. Don't try to install GroundWork another way. If it succeeds, tell me that GroundWork is installed, and that to start using it I should open a new Devin session in this project and type /bootstrap there. That sets GroundWork up for this project (it runs groundwork init and writes the project documents with me).
```

This installs GroundWork into the project's `.devin/` folder, without Devin's plugin system (5.29). Then open a new Devin session in the project and type `/bootstrap`. It runs `groundwork init` and writes the project documents with you. Commit `.devin/` to share it with your team. To update, paste the same prompt again.

Or install it as a plugin, for you in every project, then start a new session:

```
devin plugins install Hemanthkaruturi/GroundWork#plugins/groundwork-specflow
```

To install the plugin for one project instead, add it to `.devin/config.json` at the repository root. Devin installs it when the project is opened. This form, with the `#plugins/groundwork-specflow` path inside `requiredPlugins`, hasn't been tested in Devin yet.

```json
{
  "requiredPlugins": ["Hemanthkaruturi/GroundWork#plugins/groundwork-specflow"]
}
```

As a plugin, commands start with `/groundwork-specflow:`. To update: `devin plugins update groundwork-specflow`. Use one install or the other, not both.

**Existing project?** See where it stands without changing anything: `python3 <plugin>/engine/groundwork.py doctor` and `init --dry-run`.

Full reference: `plugins/groundwork-specflow/STANDARD.md`. Hands-on scenarios: `docs/manual-testing.md`.

## 12. Where it goes next

- Hooks that install themselves for every teammate on clone, and ready-made CI templates.
- Adapters for more coding agents, beyond Claude Code and Devin.
- Hook enforcement in Devin cloud sessions, once Devin runs plugin hooks there.
- Automatic checks that each repo still honours the contract version it pinned.
- A dashboard view of the work board and ownership map.
