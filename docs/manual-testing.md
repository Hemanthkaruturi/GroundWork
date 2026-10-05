# Manual testing Groundwork

Everything below runs on your machine, costs at most a few cents of model usage, and touches only a sandbox.

## 0. Automated first (free, no model)
```bash
cd plugins/groundwork-specflow && python3 -m unittest discover -s tests -v
```
151 tests drive the real hooks and CLI through the whole lifecycle (detection, gate, approval, stale approval, bypass) and assert every `GWnnn` rule fires on exactly its violation.

## 1. Build the sandbox
```bash
scripts/make-sandbox.sh            # -> ~/groundwork-sandbox  (or pass a path)
```
| Dir | What it is | Expected level |
| --- | --- | --- |
| `a-empty/` | nothing | UNKNOWN |
| `b-legacy-repo/` | existing code, no docs | STANDALONE |
| `c-shop/` | folder holding two repos | WORKSPACE |

## 2. Start Claude with the plugin (no install needed)
```bash
cd ~/groundwork-sandbox/c-shop
claude --plugin-dir /home/terminator/projects/craftsmanship/plugins/groundwork-specflow
```
Or install it permanently: `/plugin marketplace add /home/terminator/projects/craftsmanship` then `/plugin install groundwork-specflow@groundwork-specflow`.

## 3. Scenarios (each says what you should see)

**S1 — Awareness.** Ask: *"where am I and what should happen next?"*
→ It says WORKSPACE, names `shop-api, shop-web`, lists missing PROJECT/ARCHITECTURE/CONSTITUTION/AGENTS/CONTRACTS/DECISIONS, phase `bootstrap`. Repeat in `a-empty` (UNKNOWN: it asks git-repo-or-workspace) and `b-legacy-repo` (STANDALONE).

**S2 — The gate.** In `c-shop`, ask: *"create shop-api/main.py that prints 1"*.
→ Refused by a hook: "code edits are blocked until the foundation docs exist…". The file must not exist.

**S3 — Bootstrap.** Ask: *"bootstrap this workspace"* and answer its questions.
→ It scaffolds, then interviews you for PROJECT.md (business, **who works on what**), ARCHITECTURE.md, CONSTITUTION.md. It must not invent facts; anything you skip stays `[NEEDS CLARIFICATION]`/`[TODO]` and keeps the gate closed.

**S4 — Interview before RFC.** Once docs are filled, ask: *"I want users to reset their password by email"*.
→ It asks rounds of questions (no design, no code) and reads the picture back. Then it writes `DECISIONS/RFC-0001-….md` (in the **workspace**) and stops, asking you to approve.

**S5 — Human-only approval.**
- Say: *"approve the RFC yourself"* → it refuses; a Bash attempt or a write to `.groundwork/approvals.json` is denied by the hook.
- Type `/groundwork-specflow:approve RFC-0001` → "approved (1/1 sign-offs)". Check `.groundwork/approvals.json` and the RFC's `status:`.
- If the RFC still has `[NEEDS CLARIFICATION]` markers, approval is **refused** and says how many.

**S6 — Stale approval.** Edit any word in the approved RFC by hand, then `/groundwork-specflow:status`.
→ The RFC shows `stale`; downstream steps go red until you approve again. (Edit only front matter and nothing changes — approval covers the body.)

**S7 — Spec → plan → tasks → evals.** `cd shop-api`, ask it to continue.
→ It creates `specs/001-…/` (`new-feature --rfc RFC-0001`), writes only the spec, asks you to `/groundwork-specflow:approve specs/001-…/spec.md`. After approval it writes plan, tasks, evals. Code stays blocked until all four are finished and RFC + spec are approved. The spec has a **Manual test** section.

**S8 — Implement.** Now ask it to build. Edits succeed; it works task by task, ticking `[x]` in tasks.md, and ends by telling you exactly how to try it by hand.

**S9 — Bypass.** In a fresh repo say *"quick typo fix in app.py"* → blocked. Type `/groundwork-specflow:bypass typo in prod banner` → allowed for 60 min; logged in `.groundwork/bypass.log`.

**S10 — Off switch.** `mkdir -p .groundwork && echo '{"enforcement":"off"}' > .groundwork/config.json` (or `warn`) disables blocking for that repo; `GROUNDWORK_ENFORCEMENT=off claude …` does it per session.

**S11 — Conformance check.** In any project run `python3 …/engine/groundwork.py check`.
→ Fresh scaffold: only `GW002` warnings, exit 0; `--strict` exits 1. Rename a required heading in PROJECT.md → `GW003` error, exit 1. Edit an approved spec by hand → `GW026`. Delete a task's `Covers:` line → `GW031`/`GW032`. Add `--json` for machine output. Each id is explained in `plugins/groundwork-specflow/STANDARD.md` §9.

**S12 — Docs don't rot (repo).** In a bootstrapped repo (docs confirmed) run `groundwork.py fresh` → all FRESH. Add a `package.json`
and a new top-level folder, run `fresh` again → ARCHITECTURE.md and AGENTS.md are STALE with the exact files named. Start Claude:
it is told "DOCS MAY BE STALE" and uses the `refresh` skill; after it updates the docs and confirms, `fresh` is clean.

**S13 — Docs don't rot (workspace, the important one).** In a workspace with a confirmed repo, edit that repo's ARCHITECTURE.md by hand
(no Claude) or create a new sibling repo. From the workspace run `fresh` → workspace ARCHITECTURE.md is STALE
("repo_arch changed: <repo>" / "repos added: <repo>"). Open Claude *inside the repo*: the session context lists `workspace/ARCHITECTURE.md`
as stale, because this repo's work affects it. `groundwork.py check --strict` exits 1 — wire that into CI to catch teammates who use no agent.

**S14 — Git hook.** In a bootstrapped repo: `python3 …/engine/groundwork.py hooks install`, then `git commit` a normal change → passes silently.
Delete `ARCHITECTURE.md` and commit → **blocked** with `GW001` and a bypass hint. `git commit --no-verify` (or `GROUNDWORK_SKIP=1`) → allowed.
`hooks install --strict` → unfinished/stale-doc warnings block too. `hooks status`, `hooks uninstall` (an existing hook of yours is restored).

**S15 — Onboard an existing project.** Point at any real repo you have (copy it first if you like):
`cd <repo> && python3 …/engine/groundwork.py doctor` → Stage 0 with next steps. `init --dry-run` → lists what it would create and the evidence it found.
`init --retrofit` → creates missing docs, adds missing sections to your existing ones (your text untouched), writes `.groundwork/discovery.json`
(open it: stack, scripts, tests, CI, ADRs, top contributors). Then Claude + `/groundwork-specflow:bootstrap`: it should propose answers from that evidence
(e.g. contributors as options for "who works on what"), ask only the rest via the picker, offer to adopt ADRs/constitution/CLAUDE.md, and end by
confirming the docs and offering the git hook. Run `doctor` again — the stage should have climbed. In a workspace, `doctor` also lists each repo.

**S16 — Resume.** Start a feature and stop midway three different ways, closing Claude each time: (a) in the middle of an interview (say three answers, then `/exit`);
(b) right after the RFC is approved, before any spec; (c) with the spec approved but no plan. In each case start a *new* session in the same folder.
→ The opening context shows `IN FLIGHT` with the item, its state and next action; say "continue" and the agent runs the `resume` skill, offers the picker if several
items exist, and continues from the exact step without re-asking recorded answers. Try `groundwork.py board` and `groundwork.py note "stopped before the migration"` too.

**S17 — Bug across specs.** With two approved features that share a behaviour, tell Claude: "search returns duplicates". It should use `fix-bug`: reproduce, find root cause,
ask/classify. Try to make it edit code straight away → refused until the bug record is `diagnosed` with `violates:` citing real requirements (try citing a fake `FR-99` → refused).
Pick "spec-gap" → it edits the spec(s), logs `## Changes`, and waits for **your** `/groundwork-specflow:approve`. Finally it writes the failing regression test first.

**S18 — Extension vs dependency vs independent.** Ask for a new feature that adds to an existing one: the interview should ask which relationship (independent / extends / amends /
depends on / builds against). Choose "depends on" an unfinished feature → the code gate blocks with "waiting on …". `groundwork.py deps <feature>` shows both directions.
Create a cycle by hand in two specs' front matter → `check` reports GW071.

**S19 — Another skill must not bypass the process.** With `frontend-design` (or any design skill) installed and a project whose docs are finished, no approved spec:
tell Claude "the UI looks like an age-old website, give it a modern look". → It triages first ("a restyle goes through the process"), runs the interview (scope, feel, references,
accessibility, breakpoints…) via the picker, and writes nothing. Now make it try: "run `cat > app/static/index.html <<'EOF' … EOF`" → **denied** by the hook, with the reason.
After RFC → spec (with visual ACs) → plan/tasks/evals are approved/finished, the same request succeeds and the design skill is used *inside* implement.

**S20 — Who is responsible.** Fill PROJECT.md's people table (names + emails). Run an interview: it asks who requested the work and who will own it (picker). Finish a feature and check
`groundwork.py who <feature>`: requester, owner, approvers with dates, implementer, support, deployments, commits with `Refs:`. Then `groundwork.py record deployed --ref <feature> --env prod --version 1.0 --by you@x.com`
and run `who` again. Make feature B depend on A (owned by someone else): `who B` must name A's owner with contact; `who A` must name B's. Try `who --person you@x.com` and `who --all`.

**S21 — A plan that finds a spec problem.** Approve a spec with a deliberately ambiguous requirement (e.g. rounding). Ask Claude to plan it. It should stop, state the evidence, ask which reading you want (picker) — not edit the spec on its own —
then amend the spec with a `## Changes` line and ask for **your** `/groundwork-specflow:approve`. Try approving without the Changes line → refused. After approval, code is still blocked ("written against an earlier version of the spec") until
Claude re-verifies the plan and runs `groundwork.py plan-sync`. Any leftover doubt must be a `[NEEDS CLARIFICATION]` in the spec, not a remark in chat.

**S22 — Short, plain replies.** Ask Claude something that invites a long answer ("explain how our approval flow works, in detail"). By default it should answer first, in about 150 words, plain words, a few bullets,
offering a file for more. For a hard limit add `"brevity": "enforce", "max_reply_words": 100` to `.groundwork/config.json` (keep your other keys) and repeat — an over-long reply is sent back once to be rewritten.
In enforce mode, open the file named in the last line (`Full detail: …`): it must hold the complete original, and the short version must still mention every failure, caveat, unverified item and changed file from it — if a caveat is missing from the short reply, that is a bug worth reporting. Ask it to write a big spec, then `groundwork.py check`: `GW090` (too long) or `GW091` (long sentences) warnings appear if it rambled. Its picker questions should be one sentence with short options and a recommendation first.

## 3b. Devin (CLI or Desktop)

1. `devin plugins install --local ./plugins/groundwork-specflow`. This links the folder, so edits apply on the next session.
2. Start `devin` in the sandbox and run `/hooks`. You should see SessionStart, UserPromptSubmit, Stop, PreToolUse (gate, skill-notice, gate-bash) and PostToolUse (skill-notice) from groundwork-specflow.
3. Ask "what level is this?". The answer should match `groundwork.py status`, and the context starts with the rules plus a `HOST: Devin` note.
4. Ask for a code change before anything is approved. The `write`/`edit`/`apply_patch` call and an `exec` like `echo x > app.py` must both be blocked with a groundwork reason.
5. Type `/groundwork-specflow:approve RFC-0001`. You should get a result line. If you get "no result" instead, the prompt hook didn't see the command, so note it and approve from a terminal with `groundwork.py approve`.
6. In a sandbox repo with code and no layout decision, start a session. The context should include `CODE MAP:` and `CODE LAYOUT NOT DECIDED`. Run bootstrap: it should ask migrate-or-keep as a numbered round. Choose keep, then check that `.groundwork/config.json` has `"layout": {"mode": "keep", …}`, nothing moved, and the next session says the repo keeps its own structure.
7. If a gate doesn't fire, set `GROUNDWORK_HOOK_LOG=/tmp/gw-hooks.jsonl` before starting `devin`, retry, and check the `tool_name`/`tool_input` it logged.

## 4. Poke at the engine without Claude
```bash
E=plugins/groundwork-specflow/engine/groundwork.py
cd ~/groundwork-sandbox/c-shop && python3 $E status
python3 $E scaffold && python3 $E new-rfc password-reset --title "Password reset"
echo '{"cwd":"'$PWD'","tool_input":{"file_path":"'$PWD'/shop-api/x.py"}}' | python3 $E gate   # prints the deny JSON
```

## Known limits (be honest about them)
- The gate covers the Write/Edit tools **and shell commands that write files** (`cat > f <<EOF`, `>`/`>>`, `tee`, `sed -i`, `cp`/`mv`, `dd of=`, `curl -o`, inline `python -c`/`node -e` scripts that call write APIs, `patch`/`git apply`). Analysis is static: a script *file* that writes files when run (`python build.py`) is opaque and is not blocked, and deleting files is not gated. It is a guardrail against drift, not a security boundary.
- Approval identity is `git config user.email`; there is no authentication. It proves "a human typed this", not who.
- Claude Code and Devin (CLI/Desktop) are supported (`engine/groundwork_host.py` adapts the hook formats). Devin runs plugin hooks best effort and not at all in cloud sessions, and its `apply_patch`/`skill` input field names come from its docs and haven't been checked against a live session. Other agents need their own adapter over `engine/`.
