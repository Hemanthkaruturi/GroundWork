---
name: groundwork-feedback
description: Prepare feedback about GroundWork itself (the plugin, not the user's project) as a private draft and a pre-filled GitHub issue link the user can send. Use when the user asks to give feedback on GroundWork or says GroundWork is not working as expected, when GroundWork reports an internal error, or when GroundWork's own behaviour is clearly wrong (a hook blocks work the approved documents allow, a check flags something that is not there, instructions contradict each other).
---

# Feedback about GroundWork

This is about **GroundWork**, not the user's code. A defect in their project goes to the **fix-bug** skill.

Nothing is sent by you or by GroundWork. The engine saves a draft in `~/.groundwork/feedback/` (outside the project) and prints a link to GroundWork's GitHub issue form with every field filled in. The user reads it, opens the link and presses Submit, or ignores it.

## When to offer it
- **GroundWork reported an internal error** (a `[groundwork] GroundWork hit an internal error` message with a draft and a link). The draft is already written. Tell the user once, in one or two lines: GroundWork failed, here is the draft and the link if they want to report it. Don't prepare a second one, and don't stop your work over it.
- **You see GroundWork misbehave** in a way you can describe concretely: a gate blocks an edit the approved documents allow, a check reports something that is not true, the session rules contradict a skill, a command fails. Prepare the draft as below, then tell the user in one or two lines that a feedback draft and link are ready if they want to send it. Offer once per problem, never in the middle of a question you are asking them.
- **The user asks** to give feedback, or says GroundWork is getting in their way. Always prepare it.

Not feedback: GroundWork working as designed (an unapproved spec blocking code is the point), or problems in the user's own project or tools.

## Write it
Describe only **GroundWork's behaviour**, as if to someone who will never see this project:
- What GroundWork did and what it should have done. Name the GroundWork command, hook, skill or check code (`approve`, `gate`, the interview skill, `GW092`).
- **No project details at all:** no file or folder names, paths, code, document text, feature, RFC or bug names, product or company names, people, URLs, branch names or error messages that quote the project. Say "a spec", "a code file", "a feature" instead.
- Short: a title of one line, then a few sentences each for what happened and what was expected.

If the user gave their own words (with the command, or in the chat), pass them as `--user-words` exactly as written. The engine scrubs them like everything else. If they asked for feedback without saying what went wrong, ask them in one short question what bothered them, and offer the problems you noticed in this session as options.

Run:

`python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" feedback --platform <claude|codex|devin> --title "…" --happened "…" --expected "…" --where "…" [--user-words "…"]`

`--platform` is the agent you are: the engine cannot always tell from a shell.

## Hand it over
Show the user the draft file's contents and the link exactly as printed, and say:
- what the engine removed (its "Removed before saving" line);
- that the link opens GitHub with the form filled in, they can edit anything there, and nothing is sent until they press Submit;
- that GitHub shows the issue publicly under their GitHub account.

If they want changes, run the command again with the new text. Never open the link, submit the issue or call any GitHub API yourself: sending it is their choice.
