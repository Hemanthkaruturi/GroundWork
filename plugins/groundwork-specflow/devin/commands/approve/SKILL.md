---
name: approve
description: Approve one or more RFCs or specs (human sign-off, recorded against each document's content). Usage - /groundwork-specflow:approve <path | RFC-0001> [more paths]
argument-hint: <document path | RFC-NNNN> [more paths …]
triggers: ["user"]
---
The groundwork UserPromptSubmit hook executes this approval for the user; its result is in your context under "[groundwork approve]". Report that result in one line, then do what it says next: once a document is approved, carry on with the next step in this same turn rather than waiting for the user to say continue. If it says REFUSED, explain why and what must change first. Do not edit documents to work around a refusal.

If there is no "[groundwork approve]" result in your context, the hook did not run. Do not approve anything yourself and do not run the approve command: approval is a human act and the shell gate blocks it. Tell the user to run this in their own terminal, from the project folder, using the engine path from the groundwork session context:

`python3 <engine path>/groundwork.py approve $ARGUMENTS`

Then they tell you to continue: an approval run outside this chat, including a `!` command, does not start your turn.
