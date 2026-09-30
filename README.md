# Groundwork

An open-source plugin that makes coding agents work from a shared, written plan instead of
improvising. Agents multiply implementation speed *and* inconsistency; Groundwork
supplies the missing system: standard documents, a mandatory path from idea to code, and
human approval at the points that matter. Humans can read the documents to understand the
project; agents get all the context before they write a line.

**Standardize the system. Preserve the craftsmanship.**

Full overview for presenting: [`docs/groundwork-overview.md`](docs/groundwork-overview.md).

## The standard

[`plugins/groundwork/STANDARD.md`](plugins/groundwork/STANDARD.md) is the specification: levels, layout, the required
sections of every document, the path from idea to code, approval semantics, and a catalogue of numbered rules
(`GW001`…). Projects that follow the same version look and behave the same to any person or agent.
`groundwork check` verifies conformance with no model and no network, so it runs identically on a laptop, in a
git hook and in CI:

```bash
python3 plugins/groundwork/engine/groundwork.py check --strict
```

```yaml
# .github/workflows/groundwork.yml
on: [pull_request]
jobs:
  groundwork:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 path/to/groundwork/plugins/groundwork/engine/groundwork.py check --strict
```

## Resume, bugs, and how features relate
- **Close the laptop, come back tomorrow, hand it to a teammate.** Everything in flight is derived from files: `groundwork.py board` (also injected at session start)
  lists RFCs mid-interview, approved RFCs waiting for a spec, features stuck at plan/tasks/evals, half-built work and open bugs, each with its next action,
  last note (`groundwork.py note "…"`) and blockers. The `resume` skill picks one with the selectable picker and continues exactly there. The interview writes the RFC draft
  after round one, so even a half-finished interview survives.
- **Every feature is independent, or says how it relates:** `depends_on` (needs the other implemented), `builds_against` (parallel once the other's spec is approved and plan finished),
  `extends` (only the delta), `amends` (changes existing behaviour → the old spec gets a dated `## Changes` entry and must be re-approved). Cross-repo works (`repo/NNN-slug`).
  Cycles, unresolved links and concurrent edits to the same base are flagged; `groundwork.py deps <feature|RFC>` shows what a change affects.
- **Bugs have a lifecycle** (`fix-bug` skill, `bugs/NNN-slug.md`): reproduce → root cause → classify as `code-bug` (cite the violated FR/AC — across as many specs as apply),
  `spec-gap` (amend + re-approve the spec) or `design-flaw` (new approved RFC) → regression test first → fix → verify → close. The code gate stays shut until the diagnosis is real.

## Short, plain replies
Long replies don't get read, and decisions made on unread text are bad decisions. Groundwork tells the agent — at session start and on every prompt — to lead with the answer or the decision, keep to about
150 words, use short sentences and everyday words, explain IDs instead of citing them bare, and ask with the picker (label ≤ 5 words, what-happens ≤ 15, recommendation first). Documents get soft
size budgets and a sentence-length check in `groundwork check`. For a hard limit set `"brevity": "enforce"` in `.groundwork/config.json`: an over-long reply is sent back once to be rewritten
(`max_reply_words`, default 220; code and tables don't count). **Shorter never means less:** the rules name what must always survive (decisions needed, failures and skipped work, what wasn't verified, risks, every changed file, assumptions, blockers, your next step), and when a reply is shortened the full original is saved to `.groundwork/replies/` and linked, so nothing is dropped. The `plain-writing` skill holds the full style guide.

## Who is responsible — and whom to contact
Every RFC, feature and bug records the **humans** behind it: who requested it (and where the request came from), who owns it, who implemented it, who deployed it (per environment, with version), and who supports it.
`groundwork.py who <feature>` answers "whom do I call?" in one screen — including the owners of every feature it depends on or that depends on it, so before you change something
that affects a colleague's work you know exactly who they are. `who --person NAME` lists what someone is responsible for; `who --all` is the team map. Contacts live in PROJECT.md's people table;
history lives in an append-only, committed ledger. Deployments are recorded by CI:
```yaml
      - run: python3 .groundwork/engine/groundwork.py record deployed --ref 001-widgets --env prod --version "$TAG" --by "$GITHUB_ACTOR"
```

## Changes flow up only through an explicit amendment
Planning can discover that a spec is ambiguous — that is valuable. But a plan never edits a spec on its own: the agent states the evidence, **you** choose the reading, the spec gets a dated
`## Changes` line saying what changed and why (re-approval is refused without one), you re-approve, and the plan/tasks/evals are re-verified and re-pinned to the new spec (`plan-sync`). Until then code stays blocked.

## Onboarding an existing project
```bash
python3 plugins/groundwork/engine/groundwork.py init --dry-run     # see what it would do
python3 plugins/groundwork/engine/groundwork.py init --retrofit    # scaffold + add missing sections to your existing docs
python3 plugins/groundwork/engine/groundwork.py doctor             # where do we stand, and what next?
```
`init` never overwrites. It gathers evidence about the codebase (stack, scripts, tests, CI, existing docs/ADRs, contributors) into
`.groundwork/discovery.json`; `/groundwork:bootstrap` then drafts the documents from facts and asks only what code cannot tell.
`doctor` places the project on a ladder — *Not started → Scaffolded → Documented → Current → Guarded → Practicing* — with the next steps.

## Git hooks
```bash
python3 plugins/groundwork/engine/groundwork.py hooks install            # pre-commit: errors block
python3 plugins/groundwork/engine/groundwork.py hooks install --strict --pre-push --vendor
```
Run in a workspace it installs into every repo under it. `--vendor` copies the small engine into `.groundwork/engine/` so a
teammate without the plugin runs `python3 .groundwork/engine/groundwork.py hooks install` and gets the same check. Existing hooks are
chained and restored on `hooks uninstall`; `--no-verify` bypasses once.

## Documents that don't rot
Foundation docs are written once, so they drift. Groundwork records a **baseline snapshot** when a doc is confirmed
(`groundwork.py confirm`) and compares it later (`groundwork.py fresh`): changed manifests/infra/migrations, new top-level
folders, new or removed repos, a repo's `ARCHITECTURE.md` edited by a teammate, new contracts or RFCs, or plain age.
A repo session also sees when *workspace* docs went stale because of its work; the `refresh` skill updates only what changed,
asks the user about what code can't tell (people, scope, the *why*), then confirms. `check --strict` in CI catches drift
introduced by anyone, agent or not.

## What v0.1 does (Claude Code plugin `groundwork`)

| Principle | How the plugin enforces it |
| --- | --- |
| Two levels: **workspace** above, **repo** below | `engine/groundwork_core.py` detects workspace / repo / standalone / unknown from the filesystem; every session starts with that fact injected, and a repo answers for its workspace's docs too |
| PROJECT.md, ARCHITECTURE.md, CONSTITUTION.md, AGENTS.md, CONTRACTS/, DECISIONS/ | `bootstrap` skill + templates; code edits are **denied** while any is missing or still holds `[TODO]` |
| Interview → RFC → review → spec → plan → tasks → evals → code | one skill per step; a PreToolUse hook denies code edits until RFC ✔ approved, spec ✔ approved, plan/tasks/evals complete |
| Humans approve, agents cannot | `/groundwork:approve` is executed by a UserPromptSubmit hook (only typed prompts reach it); approval stores a hash of the document body, so any later edit makes it **stale**; agent writes to approval records are denied |
| Never guess | unresolved `[NEEDS CLARIFICATION]` / `[TODO]` markers block approval and the gate |
| RFC for cross-repo decisions | `classification: api` + `signoffs_required: N` (every lead signs) + `write-contract` into `CONTRACTS/` |
| Handover pack | `handover` skill + template |
| Testable by hand | spec template has a mandatory **Manual test** section; `implement` ends by telling you how to try it |

**The shell is gated too.** `cat > f <<EOF`, `sed -i`, `tee`, `cp`, `curl -o`, `patch`/`git apply` and inline scripts that write files go through the same gate as the Write tool. Other skills and plugins (`frontend-design`, …) are craft tools for the *implement* step: every prompt carries a triage reminder, and loading a non-Groundwork skill injects a notice — a "make it look modern" request is a change request (interview → RFC → spec), not a free-hand redesign.

Escape hatches, deliberately human-only: `/groundwork:bypass <reason>` (60 min, logged) and
`.groundwork/config.json` `{"enforcement":"warn|off"}`.

## Try it
```bash
python3 -m unittest discover -s plugins/groundwork/tests   # 151 tests, no model (~3 min)
scripts/make-sandbox.sh && cd ~/groundwork-sandbox/c-shop
claude --plugin-dir /home/terminator/projects/craftsmanship/plugins/groundwork
```
Full scenarios with expected results: [`docs/manual-testing.md`](docs/manual-testing.md).

## Tooling defaults
Python projects use **`uv`** (`uv add`, `uv sync`, `uv run`), never `pip`: it is in the rules every session starts with, in the generated `AGENTS.md`,
and in the bootstrap/implement skills. Onboarding detects pip/poetry/pipenv/conda and asks before migrating.

## Fewer permission prompts (optional)
Groundwork's own commands are read-mostly, so you may allow them once in `.claude/settings.json`
(or user settings). Approving/bypassing is never runnable by the agent regardless of this list:
```json
{ "permissions": { "allow": [
  "Bash(python3 */groundwork/engine/groundwork.py status*)",
  "Bash(python3 */groundwork/engine/groundwork.py check*)",
  "Bash(python3 */groundwork/engine/groundwork.py scaffold*)",
  "Bash(python3 */groundwork/engine/groundwork.py new-*)"
] } }
```
(Skills deliberately do not declare `allowed-tools`: that makes the skill call itself need approval.)

## Layout
```
.claude-plugin/marketplace.json     install via /plugin marketplace add <this dir>
plugins/groundwork/
  hooks/hooks.json                  SessionStart, UserPromptSubmit, PreToolUse
  engine/groundwork_core.py, groundwork.py          all rules; stdlib only, no Claude dependency
  skills/                           workflow, bootstrap, interview, write-{rfc,spec,plan,tasks,evals,contract}, implement, handover
  commands/                         approve, bypass, status
  templates/                        every document the process produces
  STANDARD.md                       the specification (rule ids GWnnn)
  engine/groundwork_fresh.py        freshness baselines and drift detection
  engine/groundwork_discover.py     evidence gathering for `init`
  engine/groundwork_doctor.py       `doctor` — stage and next steps
  engine/groundwork_people.py       ownership: roles, ledger, `who`
  engine/groundwork_brevity.py      word budgets, reply limit (Stop hook)
  engine/groundwork_board.py        work board: everything in flight, for resume
  engine/groundwork_relations.py    feature dependency graph and impact
  engine/groundwork_bugs.py         bug lifecycle and its gate
  engine/groundwork_hooks.py        git pre-commit / pre-push installer
  engine/groundwork_check.py        `groundwork check` — the conformance checker
  tests/                            lifecycle + one test per rule
```
`engine/` is agent-neutral by design so other coding agents can get a thin adapter later.

## Next iterations (suggested)
1. Run it on a real project and tighten the skills' wording from what the agent actually does.
3. Contract pinning (`contract.lock`) checks; RFC/ADR index kept up to date automatically.
4. Adapters for other agents (AGENTS.md-based + git hooks / CI check).

## License

[MIT](LICENSE)
