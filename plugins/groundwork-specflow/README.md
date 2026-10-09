# GroundWork

GroundWork is a plugin for Claude Code (and Devin) that makes a coding agent work from a shared, written plan instead of improvising. Before any code is written, the agent interviews you, drafts a short decision document (an RFC), and waits for your approval. Only then does it write a spec, plan, tasks and evals, build in small steps, and hand over cleanly. Hooks block code edits until the earlier steps are approved, and only a human can approve.

## What it adds to Claude Code

- **Skills** for each step: bootstrap, interview, RFC, spec, plan, tasks, evals, implement, handover, resume, bug fixing, ownership, code layout, code quality, baseline (existing behaviour and legacy specs) and plain writing.
- **Commands you type:** `/groundwork-specflow:approve`, `/groundwork-specflow:bypass` (emergencies, logged) and `/groundwork-specflow:status`.
- **Hooks** that run at session start, on each prompt, before file edits and shell commands, and at the end of a reply.
- **A local command-line engine** (`engine/groundwork.py`) that checks projects against the written standard (`STANDARD.md`).

## What the hooks do

All hooks run the explicit path `${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py` with one sub-command each (using `python3`, or `python` if `python3` isn't available) (`session-context`, `prompt-reminder`, `stop-brevity`, `alert-stop`, `gate`, `skill-notice`, `gate-bash`, `alert-question`).

- **`gate`** (before Write, Edit, MultiEdit and NotebookEdit) and **`gate-bash`** (before Bash) can only **deny** a tool call, with a plain-language reason, when the project's approved documents don't yet allow code changes. They never return "allow", so they can't approve anything or widen permissions. If nothing needs blocking they print nothing and Claude Code's normal permission flow applies.
- **`skill-notice`** (before the Skill tool) only adds a short reminder to Claude's context. It doesn't approve or deny.
- **`session-context`** and **`prompt-reminder`** add context such as work in flight. They don't change permissions.
- **`stop-brevity`** runs when Claude finishes a reply. Only in the optional strict brevity mode, if the reply is over the word limit, it asks Claude once to rewrite it shorter (the full original is saved under `.groundwork/replies/`). It doesn't touch permissions.
- **`alert-stop`** (when Claude finishes a reply) and **`alert-question`** (before the AskUserQuestion tool) do nothing unless you turned alerts on. When on, they play a sound, show a desktop notification and speak a short phrase when the agent waits for you: a finished RFC or spec ready for approval, a question, or a handover. Each document version is announced once. They print nothing and don't touch permissions. Ask the agent to "turn alerts on" (or "turn off the voice", which keeps the sound and notification), or run `groundwork.py alerts on|off|status|test` and `groundwork.py alerts voice on|off`. The setting is yours, in `~/.groundwork/settings.json`, and applies to every project.
- Devin (CLI and Desktop) loads this same `hooks/hooks.json`. The matchers also name Devin's tools: `write`, `edit`, `apply_patch` and `notebook_edit` go to `gate`, and `exec` goes to `gate-bash`. In Devin, `skill-notice` runs after the `skill` tool. The engine sees which tool is calling (Devin sets `DEVIN_PROJECT_DIR`) and answers in that tool's format. On Devin, a denial is `{"decision": "block"}`, and an edit whose target file can't be worked out is held rather than let through. Devin cloud sessions don't run plugin hooks.
- Enforcement can be turned down per project (`warn` or `off` in `.groundwork/config.json`).

## What it runs, reads and sends

- It runs a local Python 3 script, `engine/groundwork.py`, using only the standard library. There are no dependencies to install.
- The Bash hook parses the proposed tool command as text to identify file writes. It never executes that command, dumps the process environment, or transmits hook input. Download commands mentioned in the standard are examples of writes to check, not commands the plugin runs.
- `groundwork.py verify` runs the repo's own recorded check commands (formatter, linter, type checker, tests), and only when a person, an agent or CI runs it. No hook ever runs project tools. `quality init --create` copies GroundWork's tool configs into the repo, and never overwrites one.
- `groundwork check` looks for key-shaped text in files that can be committed, to catch credentials pasted into code. It reports only the file, the line and the kind of key, never the text, and it never opens `.env` files. `init` adds `.env` to `.gitignore` if it is missing, and says so.
- Discovery and freshness scans skip common secret files (`.env*`, keys, credential files, Terraform variables/state) and file symlinks.
- It reads and writes files inside your project: the documents it manages, plus a `.groundwork/` folder for approvals, notes and freshness records. Only if you turn alerts on does it also keep two small files in `~/.groundwork/`.
- With alerts on, it starts your operating system's own notification, sound and speech tools (PowerShell on Windows and WSL; `osascript`, `afplay` and `say` on macOS; `notify-send`, a sound player and `spd-say` or `espeak` on Linux). Over SSH it only rings the terminal bell.
- It runs `git` to read your repository and, to record who approved or owns something, your local git identity (`git config user.name` and `user.email`) or the `USER` variable. That identity stays in your project files. It is never sent anywhere.
- It does not read Git remote URLs, which can contain embedded credentials. It makes no network requests. It has no MCP servers and no telemetry, and it never uses, stores or sends credentials or tokens.

## Install

**From Anthropic's plugin directory.** Open [Customize](https://claude.ai/customize/plugins) in claude.ai or the Claude desktop app, go to the **Plugins** tab, choose **Discover**, search for **groundwork-specflow** (listed "from Anthropic Directory") and select **Add**. (This is the Plugins page, not the Connectors directory, which won't list it.) In Claude Code, sign in with the same claude.ai account (`/login`, Claude Code v2.1.273 or later). The plugin syncs the next time you start Claude Code, where it appears as `groundwork-specflow@synced`. Run `/reload-plugins` when prompted. Directory sync does not work with an API key or `ANTHROPIC_AUTH_TOKEN`.

**From this repository.** Use this if you don't sign in with a claude.ai account:

```
/plugin marketplace add Hemanthkaruturi/GroundWork
/plugin install groundwork-specflow@groundwork-specflow
```

Use one route or the other. If both are present, Claude Code loads the marketplace copy and ignores the synced one.

Then run `/groundwork-specflow:bootstrap` in your project.

## Update

Directory installs update themselves: new versions sync each time you start Claude Code, then run `/reload-plugins`. For a repository install, run `/plugin`, open **Marketplaces**, select `groundwork-specflow`, and choose **Enable auto-update**. To update by hand, run `/plugin marketplace update groundwork-specflow` in Claude Code, then `claude plugin update groundwork-specflow@groundwork-specflow` in a terminal, and restart Claude Code.

## Requirements

Claude Code, Python 3.10 or newer (found as `python3` or `python` on PATH), and git. No configuration is needed on any platform.

## Privacy

GroundWork runs locally, collects no data and makes no network requests. See the [Privacy Policy](https://github.com/Hemanthkaruturi/GroundWork/blob/main/PRIVACY.md).

## License

MIT.

## Upgrading from the original listing

The marketplace and plugin identifier changed from `groundwork` to `groundwork-specflow` to distinguish this plugin from the Groundbook connector. Existing users should uninstall `groundwork@groundwork`, remove the old `groundwork` marketplace, then follow the install commands above. Commands now start with `/groundwork-specflow:`. Your project's `.groundwork/` records and documents continue to work.
