---
name: resume
description: Pick up unfinished work in a new session — an RFC mid-interview, an approved RFC with no spec, a spec without a plan, a half-built feature, an open bug, or work blocked by another feature. Use at the start of a session when the context lists IN FLIGHT items, whenever the user says "continue", "where were we", "resume", or asks for something that may continue existing work.
---

# Resume unfinished work

State lives in files, not in anyone's memory. Any session — yours, a teammate's, another agent's — can resume any work.

## Ask questions the right way
Every question to the user goes through the `AskUserQuestion` tool (load it with `ToolSearch select:AskUserQuestion` if needed): selectable options, up to 4 per round, your recommendation first. Never put questions in reply text.

## Steps
1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" board` (add `--all` to include finished work). Each item shows its state, the single next action, the last note, and what blocks it.
   Nothing in flight → there is nothing to resume: use the **interview** skill for new work or **fix-bug** for a defect.
   A DOCUMENTATION REVIEW list (imports awaiting classification, baselines awaiting approval or needing source review, deferred capabilities) is not work in flight: it waits for a person. Offer the **baseline** skill (or **refresh** for source review) for it; never activate a baseline or an import (`activate` refuses).
2. Choose the target:
   - The user's message clearly names or continues one item → that one; say which.
   - Otherwise ask (`AskUserQuestion`): the active item first (Recommended), then the next most recent, up to three, plus "Something new".
   - The chosen item is **blocked** (blocked by another feature) → say so and offer to resume the blocker first.
3. Activate it: feature → `groundwork.py activate <NNN-slug>` (in its repo); bug → `groundwork.py activate-bug <NNN-slug>`; RFC → nothing to activate.
4. Re-orient before touching anything: read `log.md` (the notes), the item's documents (RFC / spec / plan / tasks / bug record), `groundwork.py deps <ref>` for what it depends on and what depends on it,
   and `git status` / `git log -5` for the code's real state. **Do not redo finished steps and do not re-ask what is already recorded** — the RFC's §3 interview record holds every answer given so far.
5. Continue with the skill the board names, from exactly where it stopped:
   `drafting` → interview / write-rfc · `in review` → ask the user to approve · `approved — no spec yet` → write-spec (in each repo the RFC touches) · `spec.md is draft` → write-spec ·
   `plan/tasks/evals` → write-plan / write-tasks / write-evals · `building` → implement · bug → fix-bug.
6. **When you stop** — the user says they're leaving, the context is running out, or you are handing over — write down where you are:
   `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" note "<where I stopped; the very next action; any open question>"`. One or two lines. This is what the next session reads first.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
