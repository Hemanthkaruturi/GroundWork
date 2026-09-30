---
name: ownership
description: Record and look up who is responsible for what — who requested a feature, who owns it, who implemented it, who deployed it, who supports it — and whom to contact about any feature, including ones a change depends on or affects. Use when the user asks "who owns/built/deployed/supports X", "whom do I contact", "who asked for this", before changing behaviour other features rely on, when finishing or handing over work, and after a deployment.
---

# Ownership: who is responsible, and whom to contact

Every RFC, feature and bug has **human** owners on record. The responsible person is always a human (the git identity of the person running you) — never the agent. Record the agent only as `--via claude-code`.

## Ask questions the right way
Every question to the user goes through the `AskUserQuestion` tool (load with `ToolSearch select:AskUserQuestion` if needed): selectable options, up to 4 per round, recommendation first. Options for "who" come from the people table in PROJECT.md ("Who works on what"); always include "Someone else" (then add them to that table — a name nobody can contact is not useful).

## Look up
- `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" who <NNN-slug | repo/NNN-slug | RFC-000N | bugs/NNN-slug>` — requester, owner, author, who approved (and when), implementer(s), support, latest deployment per environment (who, version, when), commits naming it, the history, and **the owners of every feature it depends on or that depends on it**, with contacts.
- `groundwork.py who --person "<name or email>"` — everything a person is responsible for. `groundwork.py who --all` — the team map.
- Answer the user with names **and contacts**. If a role is `(not recorded)`, say so and offer to record it.

## Record (always with the human's identity)
| When | Command |
| --- | --- |
| New work is requested (interview) | RFC front matter is set by `new-rfc --requested-by "<name>"`; also add `request_source:` (ticket / email / meeting) |
| Ownership changes hands | `groundwork.py record handover --ref <ref> --who "<new owner>"` |
| You finish implementing | `groundwork.py record implemented --ref <feature> --via claude-code` (by = the git identity) |
| Support is assigned (at handover / release) | `groundwork.py record support --ref <feature> --who "A,B"` |
| A deployment happens | `groundwork.py record deployed --ref <feature> --env prod --version 1.4.0 [--by "<who ran it>"]` — CI should call this itself |
| A bug is reported / fixed | `new-bug ... --reported-by "<name>"`; `groundwork.py record fixed --ref bugs/NNN-slug` |

## Before you change something other people own
Run `groundwork.py who <feature>` and `groundwork.py deps <feature>`. If your change affects a feature owned by someone else, tell the user **who** that is and how to reach them, and ask (picker) whether to notify them before proceeding.
Commit messages for feature work should carry a trailer `Refs: <NNN-slug>` so `who` can list the people who touched it.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
