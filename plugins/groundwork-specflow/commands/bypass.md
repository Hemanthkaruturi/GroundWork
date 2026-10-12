---
description: Temporarily lift the implementation gate for an emergency or tiny fix (logged). Usage - /groundwork-specflow:bypass <reason>
argument-hint: <reason>
disable-model-invocation: true
---
The groundwork UserPromptSubmit hook has already executed this for the user; its result is in your context under "[groundwork bypass]". Report it in one line, remind the user it is logged in .groundwork/bypass.log and lasts 60 minutes, and that any behaviour change still needs the spec updated afterwards. A bypass lifts only the code-edit gate; it never approves an RFC or spec. If the result lists a "Next step" for a document waiting on sign-offs, tell the user exactly that step: the remaining signers run /groundwork-specflow:approve <doc>, or, if they are the only reviewer, they ask you to lower `signoffs_required` in that document's front matter and then run /groundwork-specflow:approve <doc> again.

If there is no "[groundwork bypass]" result in your context, the hook did not run, and GroundWork's other hooks are probably off too. Run nothing yourself: bypass is a human act. Tell the user, and give them this command to run in their own terminal, from the project folder:

`python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" bypass $ARGUMENTS`

If the session context also has no "groundwork is active" message, follow "Check the hooks are running" in the workflow skill.
