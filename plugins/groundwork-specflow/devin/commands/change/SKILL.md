---
name: change
description: Open a standalone change that belongs to no RFC or feature, such as upgrading a package (logged in specs/changes.md, lifts the code gate for 60 minutes). Usage - /groundwork-specflow:change <what to change>
argument-hint: <what to change>
triggers: ["user"]
---
The groundwork UserPromptSubmit hook opens this change for the user; its result is in your context under "[groundwork change]". Report it in one line, then make the change in this same turn: it needs no interview or RFC. Before editing, check it really belongs to no feature: if it would alter behaviour a spec describes, stop and tell the user it belongs to that feature. When done, record it: `python3 <engine path>/groundwork.py change --standalone "<what you did>" --files <paths> --via devin`. If the result says REFUSED, explain why.

If there is no "[groundwork change]" result in your context, the hook did not run. Do not open the change yourself and do not run the bypass command. Tell the user to run this in their own terminal, from the project folder, using the engine path from the groundwork session context:

`python3 <engine path>/groundwork.py bypass --change $ARGUMENTS`

Then they tell you to continue: a command run outside this chat, including a `!` command, does not start your turn.
