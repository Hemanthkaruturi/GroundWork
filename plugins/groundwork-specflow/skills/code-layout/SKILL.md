---
name: code-layout
description: Decide and follow where code lives in a repo — the GroundWork standard layout (core / connectors / entrypoints / config / wiring) or the repo's own existing structure. Use when onboarding a repo (the session context says CODE LAYOUT NOT DECIDED), before writing new files, when the user asks to migrate a repo's structure, or when `groundwork.py check` reports layout findings.
---

# Code layout

Every repo records **one decision** in `.groundwork/config.json` → `"layout"`. `groundwork.py layout` shows it.

| Decision | What it means for you |
| --- | --- |
| `standard` | Code goes in fixed role folders (below). `groundwork.py check` warns when it doesn't. |
| `keep` | The user chose to keep the repo's own structure. **Put new code where similar code already lives and copy its patterns, naming and style.** Never create `core/`, `connectors/` etc., never move or restructure existing code, never suggest migrating again unless the user asks. |
| none yet | Ask the user (below) before writing any code. |

## How to ask the user anything (mandatory)
**Every question to the user goes through the `AskUserQuestion` tool. Never write questions in your reply text, and never end a reply with a list of questions.** The user answers by selecting, not by typing paragraphs.
- Up to 4 questions per call, each with 2–4 concrete options that *you* derived from context (the code, the docs, common practice). Put your recommended option first and label it "(Recommended)". The tool adds "Type something" and "Chat about this" itself.
- One short `header` per question (≤12 chars); the question is ONE sentence. Each option: a label of at most 5 words and a description of what happens if chosen (at most 15 words); your recommendation first with its reason.
- If `AskUserQuestion` is not loaded yet, load it first with `ToolSearch` query `select:AskUserQuestion`, then call it. Only if the tool truly does not exist in this session may you fall back to plain text, and then ask at most one short round, numbered.

## Making the decision (once per repo)
Run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" layout` — with no decision it shows whether the repo has code, a guessed profile and root, and which existing folders look like which role. In a workspace, decide **per repo** (run it inside each repo).

**New repo (no code yet):** ask only the profile (`service` · `cli` · `web` · `library`, your guess first), then
`groundwork.py layout init --profile <p> [--root <dir>] --create`. It records the decision and creates the folders, each with a one-paragraph README.

**Existing repo with code:** ask first, never assume:
> "Should this repo's code move to the GroundWork standard layout, or keep its current structure?"
> **Keep current structure (Recommended)** — nothing moves; new code follows the existing patterns. · **Migrate to standard** — new code uses the standard folders; existing code moves gradually as planned work.

Recommend *keep* unless the user has said they want the standard here; a half-migrated repo confuses people.
- **Keep** → `groundwork.py layout keep`. Then fill the **Holds** column of `CODEMAP.md` (below) so agents find things without searching, and follow the existing structure.
- **Migrate** → ask the profile, then `groundwork.py layout init --profile <p> --root <dir>` (add `--create` for the new folders). Then map what already fits a role and mark the rest as not yet migrated:
  `groundwork.py layout map connectors=src/app/clients core=src/app/services --legacy src/app/old`. Mapped folders count as that role; legacy folders are exempt from checks.
  **Moving existing code is a code change:** it goes through the normal path (an RFC/spec for the migration, tasks that move one folder at a time, tests green after each). Never move code as a side effect of another feature.

Only change a recorded decision when the user asks (`--force`).

## The standard layout

```
<root>/                      (src/<app>/, src/, internal/ for Go — recorded as "root")
  core/          business rules and use cases. NO network, database, SDKs, files-as-storage or env vars.
    <area>/      group by business area (billing/, orders/), not by file type
    ports.py     the interfaces core needs ("an LLM", "an order store"), e.g. typing.Protocol / TS interface / Go interface
  connectors/    the ONLY code that talks to the outside world
    llm/         one folder per external system, named by ROLE, not vendor …
    database/    … the vendor goes inside: llm/anthropic.py, database/postgres.py
    email/
  entrypoints/   how the app is called: http/, cli/, workers/, jobs/. Thin: parse input → call core → format output
  config/        the only place that reads env vars, settings files and secrets
  prompts/       LLM prompt texts/templates (not code)
  app.py|main.*  WIRING: builds the connectors from config and hands them to core. The only file that imports everything.
tests/           mirrors the same folders; core tests need no network or database
```

| Profile | Folders (required in bold) | May import |
| --- | --- | --- |
| `service` (API, worker) / `cli` | **core**, connectors, **entrypoints**, config, prompts | core → prompts · connectors → core, config, prompts · entrypoints → core, config |
| `web` (browser UI) | **pages**, **components**, **core**, connectors, config | pages → components, core, config · components → core · core → connectors, config · connectors → config |
| `library` | **core**, connectors | connectors → core. A library never reads env vars: it takes settings as arguments. |

## Where does this code go?

| I am writing… | It goes in |
| --- | --- |
| A rule, calculation, decision, use case | `core/<area>/` |
| A call to an LLM, database, HTTP API, queue, email, payment, cloud SDK | `connectors/<system>/`, behind an interface defined in `core/ports` |
| An HTTP route, CLI command, queue consumer, cron job | `entrypoints/<kind>/` — and it only calls core |
| Reading `os.environ` / `process.env` / a secret | `config/` — pass the values in |
| A prompt | `prompts/` |
| Creating clients and passing them to core | the wiring file (`app.py`, `main.ts`, `cmd/<name>/main.go`) |
| A UI piece / a screen (web) | `components/` / `pages/` |
| "A helper used everywhere" | next to the code that uses it, named for what it does. Never `utils/`, `helpers/`, `common/`, `misc/`, `shared/`. |

**Connector rules:** one folder per external system; the connector converts vendor types and errors into core's own types (no SDK object ever reaches core); timeouts, retries, rate limits and logging of calls live here. Swapping a vendor touches only `connectors/<system>/` and the wiring file.

## The code map — every repo, whatever the decision
`CODEMAP.md` at the repo root is generated from the code (`groundwork.py codemap`; `init` creates it). It lists each code folder with its role and file count, the outside systems called and from where, where settings are read, the entry/wiring files and the tests.
- **Read it before searching the code.** It tells you where the code you need lives.
- You write only the **Holds** column (one plain line per folder: what it holds) and **Notes** (conventions worth knowing). Both survive regeneration. Describe from what the code shows; ask the user only what the code can't tell.
- After adding, moving or removing a folder, or calling a new outside system, run `groundwork.py codemap` and describe any new folder. `check` warns while the map is missing, undescribed or out of date.

## The check
`groundwork.py check` reports, as warnings (they fail only under `--strict`):
- a required folder is missing;
- a folder imports one it may not;
- an external-system library or `fetch` is used outside connectors;
- code sits in no role folder;
- env vars are read outside config;
- a folder or file has a vague name (`utils`, `helpers` and the like);
- connector code sits loose in `connectors/`.

A malformed `layout` entry is an error. Fix a finding by moving the code to the right folder, or, for existing code in a migrating repo, by mapping or marking the folder legacy. In a `keep` repo nothing is checked.

In **write-plan**, §2 *Affected modules and files* names each file's role folder (standard) or the existing folder it follows (keep).

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
