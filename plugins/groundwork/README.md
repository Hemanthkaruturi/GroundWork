# GroundWork

GroundWork is a plugin for Claude Code that makes a coding agent work from a shared, written plan instead of improvising. Before any code is written, the agent interviews you, drafts a short decision document (an RFC), and waits for your approval. Only then does it write a spec, plan, tasks and evals, build in small steps, and hand over cleanly. Hooks block code edits until the earlier steps are approved, and only a human can approve.

## What it adds to Claude Code

- **Skills** for each step: bootstrap, interview, RFC, spec, plan, tasks, evals, implement, handover, resume, bug fixing, ownership and plain writing.
- **Commands you type:** `/groundwork:approve`, `/groundwork:bypass` (emergencies, logged) and `/groundwork:status`.
- **Hooks** that run at session start, on each prompt, before file edits and shell commands, and at the end of a reply.
- **A local command-line engine** (`engine/groundwork.py`) that checks projects against the written standard (`STANDARD.md`).

## What the hooks do

All hooks run `engine/groundwork.py` with one sub-command each (`session-context`, `prompt-reminder`, `stop-brevity`, `gate`, `skill-notice`, `gate-bash`).

- **`gate`** (before Write, Edit, MultiEdit and NotebookEdit) and **`gate-bash`** (before Bash) can only **deny** a tool call, with a plain-language reason, when the project's approved documents don't yet allow code changes. They never return "allow", so they can't approve anything or widen permissions. If nothing needs blocking they print nothing and Claude Code's normal permission flow applies.
- **`skill-notice`** (before the Skill tool) only adds a short reminder to Claude's context. It doesn't approve or deny.
- **`session-context`** and **`prompt-reminder`** add context such as work in flight. They don't change permissions.
- **`stop-brevity`** runs when Claude finishes a reply. Only in the optional strict brevity mode, if the reply is over the word limit, it asks Claude once to rewrite it shorter (the full original is saved under `.groundwork/replies/`). It doesn't touch permissions.
- Enforcement can be turned down per project (`warn` or `off` in `.groundwork/config.json`).

## What it runs, reads and sends

- It runs a local Python 3 script, `engine/groundwork.py`, using only the standard library. There are no dependencies to install.
- It reads and writes files inside your project: the documents it manages, plus a `.groundwork/` folder for approvals, notes and freshness records.
- It runs `git` to read your repository and, to record who approved or owns something, your local git identity (`git config user.name` and `user.email`) or the `USER` variable. That identity stays in your project files. It is never sent anywhere.
- It makes no network requests. It has no MCP servers, no telemetry, and reads no credentials or tokens.

## Install

```
/plugin marketplace add Hemanthkaruturi/GroundWork
/plugin install groundwork@groundwork
```

Then run `/groundwork:bootstrap` in your project.

## Requirements

Claude Code, Python 3.10 or newer, and git. It runs on Linux, macOS and Windows.

## License

MIT.
