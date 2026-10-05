---
name: approve
description: Approve an RFC or spec (human sign-off, recorded against the document's content). Usage - /groundwork-specflow:approve <path | RFC-0001>
argument-hint: <document path | RFC-NNNN>
triggers: ["user"]
---
The groundwork UserPromptSubmit hook executes this approval for the user; its result is in your context under "[groundwork approve]". Report that result in one or two lines. If it says REFUSED, explain why and what must change first. Do not edit documents to work around a refusal.

If there is no "[groundwork approve]" result in your context, the hook did not run. Do not approve anything yourself and do not run the approve command: approval is a human act and the shell gate blocks it. Tell the user to run this in their own terminal, from the project folder, using the engine path from the groundwork session context:

`python3 <engine path>/groundwork.py approve $ARGUMENTS`
