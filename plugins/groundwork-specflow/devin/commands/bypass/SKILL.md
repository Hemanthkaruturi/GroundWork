---
name: bypass
description: Temporarily lift the implementation gate for an emergency or tiny fix (logged). Usage - /groundwork-specflow:bypass <reason>
argument-hint: <reason>
triggers: ["user"]
---
The groundwork UserPromptSubmit hook executes this for the user; its result is in your context under "[groundwork bypass]". Report it in one line, remind the user it is logged in .groundwork/bypass.log and lasts 60 minutes, and that any behaviour change still needs the spec updated afterwards. A bypass lifts only the code-edit gate; it never approves an RFC or spec. If the result lists a "Next step" for a document waiting on sign-offs, tell the user exactly that step: the remaining signers run /groundwork-specflow:approve <doc>, or, if they are the only reviewer, they ask you to lower `signoffs_required` in that document's front matter and then run /groundwork-specflow:approve <doc> again.

If there is no "[groundwork bypass]" result in your context, the hook did not run. Do not run the bypass command yourself. Tell the user to run this in their own terminal, from the project folder, using the engine path from the groundwork session context:

`python3 <engine path>/groundwork.py bypass $ARGUMENTS`
