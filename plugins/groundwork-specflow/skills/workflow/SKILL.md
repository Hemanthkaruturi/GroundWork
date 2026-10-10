---
name: workflow
description: The groundwork operating model — workspace vs repo levels, the document pipeline (interview → RFC → approval → spec → plan → tasks → evals → implement → handover) and who may do what. Read this when unsure where you are or what comes next.
---

# The groundwork workflow

Coding agents multiply speed *and* inconsistency. The cure is a shared system, written down
before code: every agent gets the same product brief, architecture, constitution, contract and spec.

## Check the hooks are running
The rules are enforced by hooks. If this session's context has no message starting "groundwork is active",
the hooks are not running and nothing is enforced. Tell the user that before anything else. In Codex, plugin hooks
run only after the user trusts them: they type `/hooks`, trust the groundwork-specflow hooks, and start a new session.
Elsewhere, ask them to check that the plugin is installed and enabled.

## Know your level first
Run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" status`. It tells you which you are in:

| Level | What it is | Owns |
| --- | --- | --- |
| **workspace** | The folder *above* the repos, holding everything for one application | PROJECT.md, ARCHITECTURE.md, CONSTITUTION.md, AGENTS.md, CONTRACTS/, DECISIONS/ (RFCs + ADRs) |
| **repo** | A git repo with application code, inside a workspace | ARCHITECTURE.md (internals), AGENTS.md, specs/ (each with handover.md) |
| **standalone** | A repo with no workspace above it | Both sets |
| **unknown** | Neither | Ask the user: `git init`, or make it a workspace |

A repo reads *upward* to its workspace. Anything two repos must agree on is settled in the
workspace (RFC → CONTRACTS/) before either repo builds it. Never make a quiet cross-repo edit.

## The pipeline (never skip forward)
1. **bootstrap** — PROJECT.md, ARCHITECTURE.md, CONSTITUTION.md, AGENTS.md exist and are real.
2. **interview** — question the user until the picture is unambiguous.
3. **write-rfc** — the interview becomes an RFC. **Human approves** (`/groundwork-specflow:approve`).
4. **write-spec** — what and why, numbered FR/NFR/AC. **Human approves.**
5. **write-plan** → 6. **write-tasks** → 7. **write-evals** (before code).
8. **implement** — one task at a time, checks green after each, update docs in the same change.
9. **refresh** — whenever reality drifts from the foundation docs (`groundwork.py fresh`), and always before handover.
10. **handover** — spec handover.md per repo, plus one workspace DECISIONS/handovers/ file per cross-repo RFC, so the next engineer (or agent) can continue cold.

Alongside the path, not a step of it: **baseline** — specs with `origin: baseline` describe behaviour that existed before GroundWork (no RFC, no tasks, never in flight; approved by a human, then extendable, amendable and citable by bugs). Legacy specs imported by `adopt-specs` are `origin: imported` references until a person classifies them. The session context lists both under DOCUMENTATION REVIEW, never under IN FLIGHT. A baseline's cited source files are snapshotted by `groundwork.py confirm --baseline <slug>`; when one changes, `fresh` and the context say "source review needed" (refresh skill), separate from approval.

## Resume, bugs, and relationships
- **Resuming** any unfinished work (a closed session, another person, another agent): the **resume** skill reads `groundwork.py board` — everything in flight, its next action, last note, blockers.
- **Bugs**: the **fix-bug** skill. A bug is a violated requirement; the fix is gated on citing which (across specs if needed), a classification (code-bug / spec-gap / design-flaw), and a regression test.
- **Relationships**: every feature is independent, or declares `extends` / `amends` / `depends_on` / `builds_against`. `groundwork.py deps <feature|RFC>` shows what it needs and who it affects. Pause with `groundwork.py note`.

## Where does this project stand?
`groundwork.py doctor` reports the project's stage (Not started → Scaffolded → Documented → Current → Guarded → Practicing) and the exact next steps.
`groundwork.py init` onboards a new or existing project. Use both freely; they are read-only or additive.

## The standard
The exact shape of every document is specified in `${CLAUDE_PLUGIN_ROOT}/STANDARD.md`. `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" check`
verifies it (rule ids GWnnn) and works without any agent; run it after writing or changing documents.

## Other skills and plugins
Design, frontend, testing and similar skills are craft tools that belong to **implement**. They never replace triage, the interview, the RFC or the spec — a request such as "make the UI look modern" is a change request (look and feel is a requirement). The shell is gated exactly like the Write tool, so `cat > file <<EOF` will not get around it.

## Documents flow downstream; discoveries flow upstream only through an amendment
RFC → spec → plan → tasks → evals → code. A downstream document never changes an upstream one silently. When planning or coding finds a problem upstream: say what you found, ask the user which reading is right (picker), amend the upstream document with a dated `## Changes` line (what changed and why), have the human re-approve, re-verify everything downstream, then `groundwork.py plan-sync`. Doubts you cannot resolve are `[NEEDS CLARIFICATION]` markers in the document, never chat footnotes.

## Ownership
Every RFC, feature and bug has human requester/owner/implementer/deployer/support on record — see the **ownership** skill and `groundwork.py who <ref>`.

## Communication
Answer first, short and plain (see the **plain-writing** skill). The user must be able to decide from your first lines. `"brevity": "enforce"` in `.groundwork/config.json` makes over-long replies get rewritten automatically.

## Hard rules
- **Ask only with the `AskUserQuestion` tool** (selectable options, ≤4 questions per round, your recommendation first). Never put questions in reply text or finish a reply with a list of questions.
- You cannot approve. Only the user can. Editing an approved doc makes the approval stale.
- Never guess: write an unresolved marker `[NEEDS CLARIFICATION: question]` and ask.
- Every artifact has a reader. One page beats ten. Docs live with the code and change with it.
- Whenever you build something, give the user a way to test it by hand.
- Hooks will refuse code edits when a prerequisite is missing; read the refusal and do the named step
  — do not look for a way around it.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
