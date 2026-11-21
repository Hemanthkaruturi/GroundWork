---
name: send-feedback
description: Give feedback about GroundWork itself. The agent writes a draft with no project details and a pre-filled GitHub issue link; you review it and decide whether to send it. Usage - /groundwork-specflow:send-feedback [your own words]
argument-hint: [what went wrong with GroundWork, in your words]
triggers: ["user"]
---
Follow the groundwork-feedback skill. The user asked for this, so prepare the draft now. Pass anything they wrote with the command as `--user-words`, unchanged; if they wrote nothing, ask what went wrong.
