# Privacy Policy

**GroundWork (`groundwork-specflow`)** is a Claude Code plugin. This page says what it does with data. Last updated: 2026-09-30.

## Short version

GroundWork runs entirely on your machine. It collects no data, sends nothing over the network, and has no accounts, analytics or telemetry. The author of the plugin never receives any of your data.

## What it reads

- The files in your project, to check documents against the written standard.
- Your local git identity (`git config user.name` and `user.email`, or the `USER` environment variable) and git history, to record who requested, approved, owns or deployed something.

## What it stores

GroundWork writes plain files inside your own project, under your control:

- The documents it manages (project brief, architecture, RFCs, specs, plans, tasks, evals, bug records, handovers).
- A `.groundwork/` folder with approval records, ownership history, work notes and freshness snapshots. These contain names and email addresses of people you list or who approve work.
- Optionally, saved full-length replies in `.groundwork/replies/` (strict brevity mode only), and a local diagnostic log if you set `GROUNDWORK_HOOK_LOG`.

These files live in your repository. You decide whether to commit or share them, and you can delete them at any time.

## What it sends

Nothing. The plugin makes no network requests, runs no MCP servers or connectors, and reads no credentials or tokens. Claude Code itself, and your use of Claude, are covered by [Anthropic's privacy policy](https://www.anthropic.com/legal/privacy).

## Retention and children

The author retains no data, because none is received. The plugin is a developer tool and is not directed at children under 18.

## Changes and contact

If this policy changes, the change will appear in this file's history. Questions or concerns: open an issue at https://github.com/Hemanthkaruturi/GroundWork/issues.
