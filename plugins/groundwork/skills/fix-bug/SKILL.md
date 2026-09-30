---
name: fix-bug
description: The lifecycle for fixing a defect — reproduce, find the root cause, tie it to the requirement(s) or RFC it violates (possibly across several specs), classify it (code-bug / spec-gap / design-flaw), write a regression test first, fix, verify, refresh docs. Use whenever the user reports something broken, wrong, or "not working as expected" in existing behaviour.
---

# Fix a bug

A bug is a **violated or missing requirement**. Code edits for a fix are blocked until the bug record is *diagnosed*: complete, classified, tied to real approved specs (or RFC), and naming a regression test. That is what stops "fixes" that silently change behaviour.

## Ask questions the right way
Every question to the user goes through the `AskUserQuestion` tool (load with `ToolSearch select:AskUserQuestion` if needed): selectable options, up to 4 per round, recommendation first. Never put questions in reply text.

## Is it a bug at all?
Existing behaviour that the spec says should work differently, or does not work at all → bug. New or changed behaviour the user *wants* → not a bug: that is a feature/extension (interview skill). If unsure, ask (Bug / Change request).

## Steps
0. **Ask who reported it** (picker: people from PROJECT.md / a customer / "Someone else") and pass `--reported-by "<name>"` to `new-bug`. After the fix: `groundwork.py record fixed --ref bugs/NNN-slug --via claude-code`.
1. **Record it.** `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" new-bug <short-slug> --title "<what is wrong>"` (in the repo that has the bug). It creates `bugs/NNN-slug.md` and makes it active.
2. **Report + Reproduction (§1–2).** Reproduce it **for real** — run it; never assume. Exact steps, minimal input. Cannot reproduce → ask the user for what is missing; do not guess.
3. **Diagnosis (§3).** The root cause with `file:line`, not the symptom. Read the code path; use a debugger or logging rather than theory.
4. **Find the requirement (§4).** Search the specs for what *should* happen: `grep -rn "FR-\|AC-" specs/`, across every repo the behaviour touches. Run `groundwork.py deps <feature>` to see extensions/dependents that share the behaviour.
   Then classify — exactly one:
   - **code-bug** — a requirement states the expected behaviour and the code violates it. Set `classification: code-bug` and list **every** violated requirement in `violates: [FR-2@001-widgets, AC-1@api/003-x]` (several, across features, is normal). Each must exist in an *approved* spec.
   - **spec-gap** — the spec is silent, ambiguous or wrong. Edit each spec to say what is right, add a dated line naming this bug under that spec's `## Changes` section (create it after the required sections), list the specs in `amends: [...]`, then **ask the user to re-approve** each (`/groundwork:approve <spec>`). The fix waits for that.
   - **design-flaw** — the RFC's decision itself is wrong. Write a new (or amending) RFC (write-rfc skill; `supersedes:`/`related_rfcs:`), set `rfc:` to it, get it approved, then amend specs as needed.
   - **Requirements from different specs/RFCs contradict each other** → never pick a winner yourself. Ask the user which is right (`AskUserQuestion`), then treat it as spec-gap or design-flaw for the one that was wrong.
5. **Fix plan (§5)** — the smallest change that removes the root cause; what could regress; which downstream features (`deps`) need re-checking. **Regression test (§6)** — the test that fails now and passes after; set `regression_test: <path>` (relative to the repo).
   When §1–6 have no open markers and the classification requirements are met, set `status: diagnosed`. The gate then opens; if it still refuses, its message names the unmet requirement — do that, don't route around it.
6. **Test first.** Write the regression test, run it, and watch it fail *for the right reason*. Then fix. Use the repo's normal test command (AGENTS.md).
7. **Verify.** The regression test passes; the whole suite passes; repeat the original reproduction by hand. Fill **§7 Verification** (what you ran, what you saw, docs updated/unchanged). Run the **refresh** skill if the fix changed anything the foundation docs describe. Set `status: fixed`; run `groundwork.py check`.
8. **Close.** Tell the user exactly how to verify by hand; when they are satisfied set `status: closed`. If, midway, the fix turns out to be a real feature or a large redesign, stop, write a `note`, and switch to the interview/RFC path.

Emergencies: only the user can lift the gate (`/groundwork:bypass <reason>`); afterwards write the bug record retroactively so the reason and the regression test exist.

## Write for the reader
Replies and documents are short, plain and decision-first: answer/decision in the first line, about 150 words, short sentences, everyday words, no bare IDs or jargon (say what they mean), no re-telling of steps. See the **plain-writing** skill.
