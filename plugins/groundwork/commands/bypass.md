---
description: Temporarily lift the implementation gate for an emergency or tiny fix (logged). Usage - /groundwork:bypass <reason>
argument-hint: <reason>
disable-model-invocation: true
---
The groundwork UserPromptSubmit hook has already executed this for the user; its result is in your context under "[groundwork bypass]". Report it in one line, remind the user it is logged in .groundwork/bypass.log and lasts 60 minutes, and that any behaviour change still needs the spec updated afterwards. Run nothing yourself.
