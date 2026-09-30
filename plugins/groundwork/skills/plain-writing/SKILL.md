---
name: plain-writing
description: How to write replies and documents that a busy person actually reads and can decide from — short, plain, decision-first. Use for every reply to the user, every question, every summary, and whenever writing or revising an RFC, spec, plan, bug or handover.
---

# Write for the reader

The reader is busy and smart, and new to this exact problem. Success is not "I covered everything"; it is **"they understood and could decide."**

## Short is not less: what must always survive
Cut **repetition, narration of your steps, and background the reader already has**. Never cut:
- the **decision** the user must make, and what each option leads to;
- anything that **failed, was skipped, or was only partly done**;
- what you **did not verify**, and anything you are **unsure** of;
- **risks and side effects**: what could break, and anything changed beyond what was asked;
- **every file or setting you changed**;
- **assumptions** you made, and **blockers**;
- **what the user must do next**.
If it all cannot fit, the reply carries the essentials and a line `Full detail: <file>` — the detail is moved, never dropped. A reply that is short but hides a caveat is worse than a long one.

## Replies in chat
1. **First line: the answer or the decision you need.** Not what you did, not background.
2. **About 150 words** unless the user asked for more. Long content goes in a file; give a 5-line summary and the path.
3. **Short sentences (under ~20 words), everyday words.** Say "use" not "utilise", "start" not "initiate". One idea per sentence.
4. **No bare IDs or jargon.** "FR-6" or "GW026" mean nothing to a reader: say what it *means* ("the rule about rounding", "the spec was edited after approval") and add the ID only in brackets if useful.
5. **Don't re-tell the story.** Skip "first I…, then I…". Say what changed, what you verified, what you did not, and what happens next.
6. **At most 5 bullets**, each one line. A wall of bullets is a wall of text.
7. **Never end with a list of questions in text.** Use the `AskUserQuestion` picker.

## Asking for a decision (the picker)
- The question is one sentence; add one line of context only if the reader can't decide without it.
- 2–4 options. Each: a **label of at most 5 words** and a description of **what happens if chosen, in at most 15 words**. Put your recommendation first, marked "(Recommended)", with the reason in that description.
- Never offer options you would not defend. Say the trade-off in plain terms (cost, risk, time, what becomes harder later).

## Approval requests
Say in three lines what the document decides, what the user is being asked to sign, and the one thing most worth checking. Then the command. Do not paste the document.

## Documents
- Lead with the decision or requirement; background after, and only what the reader needs.
- Sentences short, headings plain, tables for facts, bullets for lists. Define a term once, where it first appears.
- Never delete a requirement, decision or caveat to meet a budget: split the document (a long spec is usually two features) or move background to a linked file.
- Respect the budgets (`groundwork.py check` warns when a document is too long or its sentences too long): spec ≈ 1200 words, RFC ≈ 1800, plan ≈ 1200, bug ≈ 700. A spec that will not fit is usually two features.
- Concrete beats abstract: an example input and output is worth a paragraph.

## Before you send
Read your first two lines. Would someone who reads *only* those know what to do? If not, rewrite them.
