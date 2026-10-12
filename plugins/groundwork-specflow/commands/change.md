---
description: Open a standalone change that belongs to no RFC or feature, such as upgrading a package (logged in specs/changes.md, lifts the code gate for 60 minutes). Usage - /groundwork-specflow:change <what to change>
argument-hint: <what to change>
disable-model-invocation: true
---
The groundwork UserPromptSubmit hook has already opened this change for the user; its result is in your context under "[groundwork change]". Report it in one line, then make the change in this same turn: it needs no interview or RFC. Before editing, check it really belongs to no feature: if it would alter behaviour a spec describes, stop and tell the user it belongs to that feature. When done, record it: `python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" change --standalone "<what you did>" --files <paths> --via claude-code`. If the result says REFUSED, explain why.

If there is no "[groundwork change]" result in your context, the hook did not run, and GroundWork's other hooks are probably off too. Run nothing yourself: opening a change is a human act. Tell the user, and give them this command to run in their own terminal, from the project folder:

`python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" bypass --change $ARGUMENTS`

Then they tell you to continue: a command run outside this chat does not start your turn.

If the session context also has no "groundwork is active" message, follow "Check the hooks are running" in the workflow skill.
