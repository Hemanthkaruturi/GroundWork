---
name: code-quality
description: Record and follow the repo's code quality toolchain (GroundWork's standard formatter, linter, type checker and test runner, or the repo's own tools) and the coding rules every agent follows. Use when onboarding a repo (the session context says QUALITY NOT DECIDED), before marking a task done, when `groundwork.py verify` fails, or when `check` reports quality findings.
---

# Code quality

The same code comes out whoever writes it, and whichever agent, because quality is **checked by tools the repo commits**, not by memory or taste. Every repo records one decision in `.groundwork/config.json` → `"quality"`. `groundwork.py quality` shows it, and `groundwork.py verify` runs it.

| Decision | Meaning |
| --- | --- |
| `standard` | GroundWork's toolchain and shipped configs (below). Commands follow the languages in the repo automatically. |
| `keep` | The repo's own tools, recorded as they are. **Never add a formatter or linter config, and never reformat files.** |
| none yet | Ask the user (below) before adding or changing any tool config. |

## How to ask the user anything (mandatory)
**Every question to the user goes through the `AskUserQuestion` tool. Never write questions in your reply text, and never end a reply with a list of questions.** The user answers by selecting, not by typing paragraphs.
- Up to 4 questions per call, each with 2–4 concrete options that *you* derived from context (the code, the docs, common practice). Put your recommended option first and label it "(Recommended)". The tool adds "Type something" and "Chat about this" itself.
- One short `header` per question (≤12 chars); the question is ONE sentence. Each option: a label of at most 5 words and a description of what happens if chosen (at most 15 words); your recommendation first with its reason.
- If `AskUserQuestion` is not loaded yet, load it first with `ToolSearch` query `select:AskUserQuestion`, then call it. Only if the tool truly does not exist in this session may you fall back to plain text, and then ask at most one short round, numbered.

## Making the decision (once per repo)
Run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" quality`. With no decision it shows the commands the repo's files already define (Makefile, package.json scripts, tool configs).

- **New repo:** `groundwork.py quality init --create`. It records the decision, writes the shipped configs for each language present (never overwriting one), adds `.editorconfig`, and prints the install command. Run that install (`uv add --dev ruff mypy pytest`, `npm install --save-dev …`).
- **Existing repo:** ask: *"Should this repo adopt GroundWork's standard code quality tools, or keep its own?"* **Keep own tools (Recommended)**: nothing is reformatted, and its commands are recorded. **Adopt standard**: shipped configs are added, and the formatter rewrites files once.
  - Keep → `groundwork.py quality keep`. Show the user the commands it found, and correct any with `groundwork.py quality set test="…"`.
  - Adopt → `groundwork.py quality init --create`, install the tools, then run `groundwork.py verify --fix`. **Commit the reformat as its own change**, with no other edits, so reviews stay readable. Remaining lint findings are fixed as planned work.
- Change a recorded decision only when the user asks (`--force`).

Both `init` and `keep` write the *Code quality* section of AGENTS.md. Agents without this plugin read that file too, so they follow the same commands and rules.

## The standard toolchain

| Language | Format | Lint | Types | Test |
| --- | --- | --- | --- | --- |
| Python (via `uv`) | `ruff format` | `ruff check` (bugs, security, blind except, print, commented-out code) | `mypy` (strict) | `pytest` |
| JS / TS | `prettier` | `eslint` + `typescript-eslint` strict (no `any`, no empty catch, `===`) | `tsc --noEmit` | `npm test`, or `vitest run` |
| Go | `golangci-lint fmt` (gofmt, goimports) | `golangci-lint run` (errorlint, gosec, revive …) | `go vet` | `go test ./...` |

## verify — after every task
`groundwork.py verify` runs format check, lint, types and tests, and prints PASS/FAIL with the end of each failure. `verify --fix` runs the formatter and lint autofix first; `--step test` runs one step.
- A task is done only when verify passes. Report failures with their output, never "should pass".
- **Never make it green by weakening it:** no new `# noqa`, `# type: ignore`, `eslint-disable`, `//nolint`, `@ts-ignore` or skipped test. The one exception is a rule that is genuinely wrong for that line: then the suppression carries the specific rule and the reason on the same line, and you tell the user.
- Don't edit tool configs to silence findings. Changing a team rule is a decision for the user.

## Python: ruff format and ruff check on every file you touch
Many teams run `ruff format --check` and `ruff check` in CI on all Python code, so Python you write must pass both **whatever the decision above**.
- After editing Python, run `ruff format <changed .py files>`, then `ruff check --fix <changed .py files>`, then fix what remains by hand. Both must pass before the task is done.
- Ruff picks up the repo's own config (`pyproject.toml`, `ruff.toml`). With none, its defaults apply; do not add a config just to silence findings.
- If `ruff` is not installed, run it as `uvx ruff …` or `pipx run ruff …`. Do not add it as a dependency without asking.
- In a `keep` repo, format only the files you changed. Never reformat the whole repo as part of a task.
- Before committing, run `ruff format --check .` and `ruff check .` on the repo and report any failure with its output.

## The coding rules
These are the mistakes coding agents make most, from research on AI-written code: duplication, over-engineering, swallowed errors, missing input validation, invented packages. AGENTS.md carries the short version.

1. **Reuse before writing.** Find where similar code lives (`CODEMAP.md`), and search for an existing function before writing one. Extend it instead of copying it. Never paste a block you could call.
2. **Smallest change that meets the spec.** No speculative abstractions, options, layers or "future-proofing". An interface with one implementation is only for core's ports.
3. **Never swallow errors.** No empty `catch`, no `except Exception: pass`, no catching only to log. Core raises clear domain errors, and entry points turn them into responses. Catch only what you can handle.
4. **Validate input where it enters**: routes, commands, consumers. Parameterised SQL only. Never build shell commands, paths or queries from user input.
5. **Dependencies only via the package manager** (`uv add`, `npm install`, `go get`), after checking the package exists, is maintained and is the one you meant. Prefer the standard library and what the repo already uses. Lockfiles are never hand-edited.
6. **Comments say why, never what.** No narration, no commented-out code, and no TODO without a tracked item. Docstrings only on public functions.
7. **Names come from the domain**: the PROJECT.md glossary and the names already in the code. No `Manager`, `Helper`, `Util`, `Data`, `Info` names.
8. **Tests test behaviour** through public functions. Mock only connectors to outside systems. A test must fail when the code is wrong. A bug fix starts with a failing regression test.
9. **Log through the project's logger**, never `print` in core code. Never log secrets or personal data.
10. **Keep files small** (`check` warns over 400 lines, `max_file_lines` in config) and functions short. Split by responsibility.

In a repo that keeps its own tools, rules 1–9 still apply to new code, written in the repo's existing style.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
