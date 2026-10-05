---
name: bypass
description: Temporarily lift the implementation gate for an emergency or tiny fix (logged). Usage - /groundwork-specflow:bypass <reason>
argument-hint: <reason>
triggers: ["user"]
---
The groundwork UserPromptSubmit hook executes this for the user; its result is in your context under "[groundwork bypass]". Report it in one line, remind the user it is logged in .groundwork/bypass.log and lasts 60 minutes, and that any behaviour change still needs the spec updated afterwards.

If there is no "[groundwork bypass]" result in your context, the hook did not run. Do not run the bypass command yourself. Tell the user to run this in their own terminal, from the project folder, using the engine path from the groundwork session context:

`python3 <engine path>/groundwork.py bypass $ARGUMENTS`
