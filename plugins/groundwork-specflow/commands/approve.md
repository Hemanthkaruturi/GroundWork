---
description: Approve one or more RFCs or specs (human sign-off, recorded against each document's content). Usage - /groundwork-specflow:approve <path | RFC-0001> [more paths]
argument-hint: <document path | RFC-NNNN> [more paths …]
disable-model-invocation: true
---
The groundwork UserPromptSubmit hook has already executed this approval for the user; its result is in your context under "[groundwork approve]". Report that result in one line, then do what it says next: once a document is approved, carry on with the next step in this same turn rather than waiting for the user to say continue. If it says REFUSED, explain why and what must change first. Do not edit documents to work around a refusal.

If there is no "[groundwork approve]" result in your context, the hook did not run, and GroundWork's other hooks are probably off too. Run nothing yourself: approve is a human act. Tell the user, and give them this command to run in their own terminal, from the project folder:

`python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" approve $ARGUMENTS`

Then they tell you to continue: an approval run outside this chat does not start your turn.

If the session context also has no "groundwork is active" message, follow "Check the hooks are running" in the workflow skill.
