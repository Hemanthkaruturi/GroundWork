# Privacy Policy

**GroundWork (`groundwork-specflow`)** is a Claude Code plugin that also runs in Devin. This page says what it does with data. Last updated: 2026-10-05.

## Short version

GroundWork runs entirely on your machine. It collects no data, sends nothing over the network, and has no accounts, analytics or telemetry. The author of the plugin never receives any of your data.

## What it reads

- The files in your project, to check documents against the written standard.
- To catch credentials written into code by mistake, `groundwork check` looks for key-shaped text (for example an API key prefix or a private key header) in files that are, or could be, committed. It reports only the file, the line and the kind of key. It never prints, stores or sends the matched text, and it never opens `.env` files.
- Your local git identity (`git config user.name` and `user.email`, or the `USER` environment variable) and git history, to record who requested, approved, owns or deployed something.

## What it stores

GroundWork writes plain files inside your own project, under your control:

- The documents it manages (project brief, architecture, RFCs, specs, plans, tasks, evals, bug records, handovers).
- A `.groundwork/` folder with approval records, ownership history, work notes and freshness snapshots. These contain names and email addresses of people you list or who approve work.
- Optionally, saved full-length replies in `.groundwork/replies/` (strict brevity mode only), and a local diagnostic log if you set `GROUNDWORK_HOOK_LOG`.

These files live in your repository. You decide whether to commit or share them, and you can delete them at any time.

If you turn on attention alerts (`groundwork.py alerts on`), two small files are kept outside any project, in `~/.groundwork/`: `settings.json` (alerts on or off, voice on or off) and `alert-state.json` (which document version was last announced, so the same one does not ring twice). A desktop notification and a spoken phrase are produced by your own operating system's tools. Nothing leaves your machine.

## What it sends

Nothing. The plugin makes no network requests, runs no MCP servers or connectors, and never uses, stores or transmits credentials or tokens. The key check above only notices them, so you can remove them. Claude Code itself, and your use of Claude, are covered by [Anthropic's privacy policy](https://www.anthropic.com/legal/privacy). If you use it in Devin, Devin itself is covered by Cognition's privacy policy.

## Retention and children

The author retains no data, because none is received. The plugin is a developer tool and is not directed at children under 18.

## Changes and contact

If this policy changes, the change will appear in this file's history. Questions or concerns: open an issue at https://github.com/Hemanthkaruturi/GroundWork/issues.
