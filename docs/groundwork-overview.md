# Groundwork

**Coding agents write code fast. Groundwork makes sure they write the right code, the way your team agreed, and that people can always see why.**

Groundwork is a plugin for Claude Code. It makes the agent follow a shared, written plan: standard documents first, humans approve the important steps, and only then code. It is open source. The rules are enforced by the tool itself, not by asking nicely.

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

1. **Interview.** The agent asks you questions (as clickable options, not walls of text) until the request is clear.
2. **RFC.** The answers become a short decision document. You review and approve it.
3. **Spec.** What to build and why, with numbered requirements and a manual test. You approve it.
4. **Plan, tasks, evals.** How to build it, in small steps, and how we'll know it's right, written before any code.
5. **Implement.** One task at a time. Documents stay in sync with the code.
6. **Handover.** So the next person, or agent, can continue without guessing.

**The agent cannot skip a step.** Hooks block code edits until the earlier steps are done. This covers the editor tools and shell tricks like `cat > file <<EOF`. Only a human can approve. If someone edits an approved document, the approval becomes stale.

## 4. What you get

### Structure everyone shares
- **Two levels.** A *workspace* holds the product-level truth (project brief, architecture, rules, contracts, decisions). Each *repo* holds its own code, specs and internals. The agent always knows which level it is on.
- **Standard documents:** `PROJECT`, `ARCHITECTURE`, `CONSTITUTION` (the non-negotiable rules), `AGENTS`, RFCs, specs, plans, tasks, evals, bug records, handovers.
- **A written standard** (`STANDARD.md`) with 46 numbered rules. `groundwork check` verifies them with no AI and no network, so it runs the same on a laptop, in a git hook and in CI.

### Humans stay in control
- **Approval is human-only.** Recorded against the exact document text, with who and when.
- **Nothing is guessed.** Unknowns become visible markers that block approval.
- **Changes go up only through an amendment.** If planning finds a problem in the spec, the agent shows the evidence, *you* pick the reading, the spec gets a dated "what changed and why" line, you re-approve, and the plan is re-checked against the new spec.

### Work survives closed sessions
- **A work board** lists everything in flight, with its next step and last note: RFCs mid-interview, specs without plans, half-built features, open bugs.
- **Resume anywhere.** New session, new teammate, new agent: it picks up exactly where work stopped, without re-asking answers.

### Real projects are messy, so it handles them
- **Bug lifecycle.** A bug is a broken requirement. The fix is blocked until the bug is classified (code wrong, spec wrong, or decision wrong), tied to the exact requirements it violates (across several specs if needed), and given a regression test.
- **Feature relationships.** Each feature is independent, or says how it relates: *depends on*, *builds against* (parallel), *extends*, *amends*. Cycles and clashes are flagged.
- **Existing projects.** `groundwork init` reads a codebase and gathers evidence (stack, tests, CI, contributors). The agent drafts documents from facts and only asks what code can't tell. `groundwork doctor` shows how far a project is from the standard and what to do next.

### Accountability
- For every RFC, feature and bug: **who requested it, who owns it, who implemented it, who deployed it (per environment and version), who supports it.**
- `groundwork who <feature>` answers "whom do I call?" in one screen, including the owners of every feature it depends on or affects.
- Deployments are recorded by CI. History is an append-only file in the repo.

### Documents that stay true
- **Freshness tracking.** Docs record what they were derived from. If the stack, the repos or a teammate's architecture changes, the affected docs are flagged as stale, including workspace docs when a repo changes.
- **Git hook.** Optional pre-commit check that blocks commits which break the standard.

### Replies people actually read
- Agents are told to answer first, in about 150 words, in plain words, with no bare jargon.
- **Short never means less.** Decisions needed, failures, unverified items, risks, changed files and next steps must always survive. In strict mode, an over-long reply is saved in full, rewritten short, and linked. Nothing is lost.

### Sensible defaults
- Python projects use `uv`, never `pip`.
- Other skills (like a frontend design skill) are treated as tools for the build step. They can't skip the process.

## 5. See each feature in action

One sample product is used throughout. **ShopFront** is a workspace called `shop` with two repos, `shop-api` and `shop-web`. The team: **Priya** (product owner), **Ravi** (backend lead), **Meena** (frontend lead), **Sam** (DevOps). Everything below is real output from the tool, lightly trimmed. The picker example (5.5) is an illustration of what appears on screen.

### 5.1 The agent always knows where it is
`groundwork init` in the empty workspace, then `groundwork doctor`:
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
After the documents are filled in and confirmed, the same command says `Stage 3/5: Current`, and the next step is "install the git hook".

### 5.2 Standard documents, checked by a tool
Someone renames a required heading. `groundwork check` (also runs in CI and as a git hook):
```
ERROR   GW003  PROJECT.md: missing required section(s): Who works on what
         → keep the template's headings; see STANDARD.md §4
ERROR   GW032  shop-api/specs/001-product-search/tasks.md: FR-2 is not covered by any task
warning GW023  shop-api/specs/001-product-search/spec.md: FR-2 is not proven by any acceptance criterion
```
The second and third lines are traceability: every requirement needs a task and a test scenario.

### 5.3 The gate: no code before an approved spec
The agent tries to write `src/search.py` while the spec is still a draft:
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

### 5.4 Only a human approves
The agent tries to approve its own RFC:
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
Instead of a wall of questions in text, the agent shows a picker (illustration):
```
[Results]  How many results per page?
 ❯ 1. 20 per page (Recommended)   Fits a phone screen without scrolling.
   2. 50 per page                 Fewer taps, but slower on mobile.
   3. Infinite scroll             Smoother to use, harder to test.
   4. Type something
```
Every answer is written into the RFC as it goes, so a closed session loses nothing.

### 5.6 Nothing is guessed
A spec that still has open questions cannot be approved:
```
spec.md still has 14 [TODO]/[NEEDS CLARIFICATION] marker(s). Resolve them before approval.
```

### 5.7 A plan finds a problem in the spec
While planning, the agent notices "rounded" in FR-2 is ambiguous. It shows the evidence and asks Priya which reading she wants (picker). Priya says "nearest cent". Then:
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
Next morning, the new session starts with this already in the agent's context:
```
IN FLIGHT:
  - [feature] 001-search-box — spec.md is draft, 14 unresolved marker(s) ← active;
    last note: Paused: waiting for the search API contract details ... Question for Ravi: max query length?
```
She says "continue". The `resume` skill picks up at the spec and asks Ravi's question first. A teammate, or another agent, can do the same.

### 5.9 Fixing a bug without breaking the rules
Priya reports "search crashes on empty query". The agent opens a bug record. It cannot touch code yet:
```
DENIED: bug '001-empty-query-crash' does not yet allow edits: sections 1–6 still have 8
unresolved marker(s) (use the fix-bug skill).
```
The agent diagnoses it as a *code bug* and cites the requirement it violates. A made-up requirement is refused:
```
DENIED: bug '001-empty-query-crash' does not yet allow edits: violates FR-9@001-product-search:
no such requirement in that spec.
```
With the real requirement (FR-1) and a named regression test, editing is allowed. If the spec was wrong instead, the bug is classified as a *spec gap*, and the spec must be amended and re-approved first.

### 5.10 Features that depend on each other
`shop-web/001-search-box` needs the search API. It says so in its spec (`depends_on: [shop-api/001-product-search]`). Until the API is done:
```
DENIED: feature '001-search-box' is not ready to build: waiting on shop-api/001-product-search
(not yet implemented, tasks 0/5).
```
Ravi, working on the API, checks who he affects:
```
> groundwork.py deps shop-api/001-product-search
  affects (downstream):
    - shop-web/001-search-box  (depends_on)
```

### 5.11 Who is responsible, and whom to call
An incident in production. Anyone can run one command:
```
> groundwork.py who shop-api/001-product-search
  Requested by        Priya Nair (Product owner) — priya@shop.example
  Owner               Priya Nair (Product owner) — priya@shop.example
  Approved            approved: Priya Nair 2026-09-29
  Implemented by      Ravi Kumar (Backend lead) — ravi@shop.example
  Support             Sam Ortiz (DevOps) — sam@shop.example
  Deployed → staging  1.0.0 by Sam Ortiz (DevOps) — sam@shop.example on 2026-09-29
  Deployed → prod     1.0.1 by Sam Ortiz (DevOps) — sam@shop.example on 2026-09-29

  People to talk to before changing it
    affects shop-web/001-search-box  (depends_on) — owner: Meena Iyer (Frontend lead) — meena@shop.example
```
Deployments are recorded by CI with one line: `groundwork.py record deployed --ref 001-product-search --env prod --version 1.0.1 --by "$ACTOR"`.
Other views: `who --person meena@shop.example` lists everything Meena is responsible for, and `who --all` prints the team map:
```
ITEM                         OWNER        REQUESTED BY   IMPLEMENTED BY   SUPPORT
RFC-0001-product-search      Ravi Kumar   Priya Nair     -                -
shop-api/001-product-search  Priya Nair   Priya Nair     Ravi Kumar       Sam Ortiz
shop-web/001-search-box      Meena Iyer   Priya Nair     -                -
```

### 5.12 Documents that don't rot
A teammate adds `package.json` to `shop-api` without any agent. `groundwork fresh`:
```
STALE       ARCHITECTURE.md
            - rfcs added: RFC-0001-product-search
```
and `groundwork check` names the affected repo documents (`shop-api/ARCHITECTURE.md`, `shop-api/AGENTS.md`: "signals added: package.json"). The workspace `ARCHITECTURE.md` is flagged too, because a new approved decision exists. The `refresh` skill updates only what changed.

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
`groundwork init --dry-run` in a project that already has code, and nothing is written:
```
[legacy] standalone: would create PROJECT.md, ARCHITECTURE.md, CONSTITUTION.md, AGENTS.md, DECISIONS/
  languages:    Python (2)
  manifests:    requirements.txt
  entry points: src/app.py
  tests:        1 test file(s) in tests
  python:       uv not in use; other managers found: pip (ask before migrating)
```
The agent then drafts the documents from this evidence and asks only what code cannot tell.

### 5.15 Short, plain replies that lose nothing
Asked to explain a hash map, the agent first wrote 404 words. In strict mode the tool saves that text, sends it back, and the agent rewrites it:
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
Asked "the UI looks like an old website, give it a modern look", with a design skill installed, the agent answered:
> A restyle goes through the project's process (interview, then RFC, spec, plan and so on) before any code changes. I'll start with the interview skill.

It then asked about scope, look and feel, accessibility and screen sizes, and left the file untouched. The design skill comes in later, to build what the approved spec says.

### 5.17 Python projects use `uv`
Asked to add the `requests` library, the agent ran `uv add requests`, not `pip install`. On an existing project that uses pip, it asks before migrating (see 5.14).

## 6. How it helps

| If you are… | You get… |
| --- | --- |
| **A developer** | Clear specs before you code. Fewer rework loops. Know who to call. Pick up a colleague's half-done work. |
| **A tech lead** | Consistent structure across repos and agents. Decisions recorded with reasons. A check that runs in CI. |
| **A product owner** | The agent must ask before it builds. Written requirements you can approve. Traceability from request to release. |
| **Support / on-call** | One command to find the owner, implementer, deployer and support contact. |
| **A new joiner** | Read the project brief and architecture. Handover packs. No archaeology. |
| **Everyone** | Short, plain answers that don't hide the caveat. |

## 7. A 5-minute demo

1. **Awareness.** Start Claude in an empty workspace. Ask "where am I?" It names the level and what's missing.
2. **The gate.** Ask it to create a code file. It is refused and told what to do first.
3. **Bootstrap.** It interviews you with clickable choices and writes the project docs, without inventing facts.
4. **Request a feature.** It asks its questions, writes an RFC, and stops for your approval. Try to get it to approve for itself: it refuses.
5. **The shell trick.** Ask it to write a file with a shell heredoc. Denied.
6. **A plan finds a problem.** It shows the evidence and lets you choose. The spec gets a logged change and needs your re-approval.
7. **Close the session, open a new one.** It shows what's in flight and resumes.
8. **Ask "who owns this?"** One screen with names and contacts.
9. **`groundwork doctor`.** The project's stage and next steps.

The step-by-step version is in `docs/manual-testing.md`.

## 8. What's inside

- **16 skills:** workflow, bootstrap, interview, write-rfc, write-spec, write-plan, write-tasks, write-evals, write-contract, implement, handover, refresh, resume, fix-bug, ownership, plain-writing.
- **Hooks:** session start (awareness and in-flight work), every prompt (triage and style reminder), before edits and shell commands (the gate), when another skill loads, and at reply end (optional length limit).
- **Commands you type:** `/groundwork-specflow:approve`, `/groundwork-specflow:bypass` (emergencies, logged), `/groundwork-specflow:status`.
- **A command-line engine** (`groundwork.py`): `init`, `doctor`, `check`, `fresh`, `confirm`, `board`, `note`, `who`, `record`, `deps`, `hooks`, and more. Pure Python, no dependencies, no Claude needed.
- **Quality:** about 150 automated tests cover the whole lifecycle. Every numbered rule has a test that breaks exactly that rule.

## 9. Honest limits

- It guards against drift. It is **not a security boundary.** A script file that writes files when run can't be seen by the shell check.
- Approval proves "a human typed this", not who they are.
- Some checks are judgment calls by the agent (is this a bug or a change request? did the short reply keep every caveat?). The saved originals make mistakes recoverable.
- Today it works with **Claude Code**. The engine is agent-neutral, so other agents can get a thin adapter.
- It adds steps. That is the point, but tiny fixes need the human-run bypass.

## 10. Questions you may get

**Doesn't this slow us down?** The interview and RFC take minutes. They replace rework. For emergencies, a human can lift the gate for an hour, and it is logged.

**Can the agent cheat?** It can't approve, can't edit approval records, and shell writes are gated. It can still make mistakes of judgment, which is why humans approve the RFC and spec.

**Do we have to use it on every project?** No. Turn enforcement down to `warn` or `off` per repo, and adopt it gradually. `init` and `doctor` are made for existing projects.

**What if a teammate doesn't use the plugin?** Commit the small check engine into the repo. Their git hook and your CI enforce the same standard.

**Why files, not a database?** Files live with the code, review in pull requests, and any person or agent can read them.

## 11. Get started

```bash
# try it without installing
cd your-project
claude --plugin-dir /path/to/craftsmanship/plugins/groundwork-specflow

# existing project? see where it stands
python3 /path/to/craftsmanship/plugins/groundwork-specflow/engine/groundwork.py doctor
python3 /path/to/craftsmanship/plugins/groundwork-specflow/engine/groundwork.py init --dry-run
```

Then run `/groundwork-specflow:bootstrap` in Claude. Full reference: `plugins/groundwork-specflow/STANDARD.md`. Hands-on scenarios: `docs/manual-testing.md`.

## 12. Where it goes next

- Hooks that install themselves for every teammate on clone, and ready-made CI templates.
- Adapters so other coding agents follow the same standard.
- Contract version pinning between repos.
- A dashboard view of the work board and ownership map.
