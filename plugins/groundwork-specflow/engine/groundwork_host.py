"""Which agent harness is calling the hooks, and how to talk back to it.

One hooks/hooks.json serves Claude Code and Devin (CLI and Desktop); Devin loads a Claude plugin's hooks/hooks.json
as-is. The harnesses differ in their tool names, in the fields they send, and in how a hook denies a tool call.
This module hides those differences so the hook handlers in groundwork.py stay harness-neutral.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from groundwork_core import PLUGIN_ROOT

# Devin's built-in tool names (docs.devin.ai/cli/extensibility/hooks/lifecycle-hooks). Claude's are capitalised.
DEVIN_EDIT_TOOLS = {"write", "edit", "apply_patch", "notebook_edit"}
DEVIN_TOOLS = DEVIN_EDIT_TOOLS | {"exec", "skill", "read", "notebook_read", "grep", "glob", "get_output",
                                  "write_to_process", "kill_shell", "webfetch", "todo_write", "exit_plan_mode"}

PATH_KEYS = ("file_path", "notebook_path", "path", "filePath", "file", "target_file", "filename")
SKILL_KEYS = ("skill", "name", "skill_name")
PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+?)\s*$|^\*\*\* Move to: (.+?)\s*$|^\+\+\+ (?:b/)?(.+?)\s*$", re.M)


def name(full: dict | None = None) -> str:
    """'devin' or 'claude'. A tool name in the payload decides; otherwise Devin's hook environment does."""
    forced = os.environ.get("GROUNDWORK_HOST", "").strip().lower()
    if forced in ("claude", "devin"):
        return forced
    tool = str((full or {}).get("tool_name", ""))
    if tool:
        return "devin" if tool in DEVIN_TOOLS else "claude"
    return "devin" if os.environ.get("DEVIN_PLUGIN_ROOT") or os.environ.get("DEVIN_PROJECT_DIR") else "claude"


def cwd(full: dict) -> str:
    """The session's working directory. Devin sends no `cwd`; it sets DEVIN_PROJECT_DIR instead."""
    return (full.get("cwd") or os.environ.get("DEVIN_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR")
            or os.getcwd())


def session_cwd(full: dict) -> str | None:
    """The harness-reported working directory only, with no fallback to this process's own."""
    return full.get("cwd") or os.environ.get("DEVIN_PROJECT_DIR")


def deny(full: dict, reason: str) -> dict:
    if name(full) == "devin":
        return {"decision": "block", "reason": reason}
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def context(full: dict, default_event: str, text: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": full.get("hook_event_name") or default_event, "additionalContext": text}}


def patch_targets(text: str) -> list[str]:
    """Files named in an apply_patch body (`*** Update File: x`) or a unified diff (`+++ b/x`)."""
    hits = [next(g for g in m.groups() if g) for m in PATCH_FILE.finditer(text)]
    return [h for h in hits if h != "/dev/null"]


def edit_targets(full: dict) -> tuple[list[Path], bool]:
    """(files the tool call would write, whether the input shape was understood)."""
    inp = full.get("tool_input") or {}
    if not isinstance(inp, dict):
        inp = {"input": inp}
    raw = [inp[k] for k in PATH_KEYS if isinstance(inp.get(k), str) and inp[k].strip()]
    if not raw:
        for v in inp.values():
            if isinstance(v, str) and "\n" in v:
                raw += patch_targets(v)
    base = Path(cwd(full))
    paths = [p if p.is_absolute() else base / p for p in (Path(r.strip()) for r in raw)]
    return paths, bool(paths)


def skill_name(full: dict) -> str:
    inp = full.get("tool_input") or {}
    return next((str(inp[k]) for k in SKILL_KEYS if isinstance(inp, dict) and inp.get(k)), "")


DEVIN_NOTE = """\
HOST: Devin. The groundwork skills were written for Claude Code; read them with these substitutions:
- `${{CLAUDE_PLUGIN_ROOT}}` means {root} — use that literal path in commands, e.g. `python3 "{engine}" status`.
- There is no AskUserQuestion or ToolSearch tool here. Wherever a skill says AskUserQuestion or "picker", ask ONE round: each question with a short numbered list of options, your recommendation first and marked (Recommended), then end your turn and wait. Never bury questions inside a long reply.
- Write/Edit/MultiEdit mean write, edit and apply_patch; Bash means exec. The gates apply to all of them.
- Record your work with `--via devin`, not `--via claude-code`.
- Approval and bypass are human acts: the user types /groundwork-specflow:approve <doc> or /groundwork-specflow:bypass <reason>. If that reports no result, the user runs `python3 "{engine}" approve <doc>` in their own terminal. Never run it yourself."""

ASK_RULE_CLAUDE = ("8. ASK ONLY WITH THE `AskUserQuestion` TOOL: options the user selects, up to 4 questions per round, your recommendation first. "
                   "If the tool is not loaded, load it with ToolSearch `select:AskUserQuestion`. Never put questions in reply text or end "
                   "a reply with a list of questions; ask, write down the answer, ask the next round.")
ASK_RULE_DEVIN = ("8. ASK IN ROUNDS: up to 4 questions per round, each with a short numbered list of options, your recommendation first "
                  "and marked (Recommended). Make the round the whole reply, end your turn and wait; write down the answers, then ask the "
                  "next round. Never scatter questions through a longer reply.")


# setup/install.py puts the engine in <project>/.devin/groundwork and the skills in .devin/skills, with no plugin.
BOOTSTRAPPED = PLUGIN_ROOT.parent.name == ".devin"
BOOTSTRAP_NOTE = ("- GroundWork is installed in this project's .devin/ folder, not as a plugin, so its commands have no prefix: "
                  "/approve, /bypass, /status, /bootstrap. Where a message says /groundwork-specflow:<name>, tell the user /<name>.")


def adapt_rules(rules: str, host: str) -> str:
    """The session rules, worded for the harness that will read them."""
    if host != "devin":
        return rules
    engine = (PLUGIN_ROOT / "engine" / "groundwork.py").as_posix()
    rules = rules.replace(ASK_RULE_CLAUDE, ASK_RULE_DEVIN).replace("--via claude-code", "--via devin")
    rules = rules.replace("${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py", engine)
    note = DEVIN_NOTE.format(root=PLUGIN_ROOT.as_posix(), engine=engine)
    if BOOTSTRAPPED:
        rules, note = rules.replace("/groundwork-specflow:", "/"), note.replace("/groundwork-specflow:", "/") + "\n" + BOOTSTRAP_NOTE
    return rules + "\n" + note


def describe_input(full: dict) -> str:
    inp = full.get("tool_input")
    keys = sorted(inp) if isinstance(inp, dict) else [type(inp).__name__]
    return f"tool '{full.get('tool_name', '?')}' with input keys {json.dumps(keys)}"
