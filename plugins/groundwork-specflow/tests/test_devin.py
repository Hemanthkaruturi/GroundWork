"""Devin compatibility: Devin's hook payloads (lower-case tool names, no `cwd`, DEVIN_PROJECT_DIR) and its manifest."""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import CheckBase
from test_flow import CA, ENV, Base, git_init

PLUGIN = Path(__file__).resolve().parents[1]


def devin(project, sub, payload):
    """Run a hook the way Devin does: no `cwd` in the payload, project dir in the environment, cwd elsewhere."""
    env = {**ENV, "DEVIN_PROJECT_DIR": str(project), "DEVIN_PLUGIN_ROOT": str(PLUGIN)}
    r = subprocess.run(
        [sys.executable, str(CA), sub],
        cwd=PLUGIN,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout.strip() else None


def blocked(o):
    return bool(o) and o.get("decision") == "block"


class DevinGates(Base):
    def setUp(self):
        super().setUp()
        self.repo = self.root / "repo"
        git_init(self.repo)

    def test_code_edits_are_blocked_in_devin_format(self):
        for tool, inp in (
            ("write", {"file_path": str(self.repo / "app.py"), "content": "x"}),
            ("edit", {"path": "app.py", "old_string": "a", "new_string": "b"}),
            ("notebook_edit", {"notebook_path": "nb.ipynb"}),
        ):
            with self.subTest(tool=tool):
                o = devin(
                    self.repo,
                    "gate",
                    {
                        "hook_event_name": "PreToolUse",
                        "tool_name": tool,
                        "tool_input": inp,
                    },
                )
                self.assertTrue(blocked(o), o)
                self.assertNotIn("hookSpecificOutput", o)
                self.assertTrue(o["reason"].startswith("groundwork-specflow"))

    def test_documents_stay_editable(self):
        o = devin(
            self.repo,
            "gate",
            {"tool_name": "write", "tool_input": {"file_path": "ARCHITECTURE.md"}},
        )
        self.assertIsNone(o)

    def test_apply_patch_targets_are_gated(self):
        doc_only = (
            "*** Begin Patch\n*** Add File: ARCHITECTURE.md\n+# A\n*** End Patch\n"
        )
        self.assertIsNone(
            devin(
                self.repo,
                "gate",
                {"tool_name": "apply_patch", "tool_input": {"patch": doc_only}},
            )
        )
        sneaky = doc_only.replace(
            "*** End Patch", "*** Update File: src/app.py\n@@\n-a\n+b\n*** End Patch"
        )
        self.assertTrue(
            blocked(
                devin(
                    self.repo,
                    "gate",
                    {"tool_name": "apply_patch", "tool_input": {"input": sneaky}},
                )
            )
        )
        diff = "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-a\n+b\n"
        self.assertTrue(
            blocked(
                devin(
                    self.repo,
                    "gate",
                    {"tool_name": "apply_patch", "tool_input": {"diff": diff}},
                )
            )
        )

    def test_unreadable_edit_input_fails_closed(self):
        o = devin(
            self.repo, "gate", {"tool_name": "edit", "tool_input": {"something": 1}}
        )
        self.assertTrue(blocked(o))
        self.assertIn("something", o["reason"])

    def test_shell_writes_and_human_acts_are_blocked(self):
        for cmd in ("echo code > app.py", "python3 x/groundwork.py approve RFC-0001"):
            with self.subTest(cmd=cmd):
                self.assertTrue(
                    blocked(
                        devin(
                            self.repo,
                            "gate-bash",
                            {"tool_name": "exec", "tool_input": {"command": cmd}},
                        )
                    )
                )
        self.assertIsNone(
            devin(
                self.repo,
                "gate-bash",
                {"tool_name": "exec", "tool_input": {"command": "git status"}},
            )
        )

    def test_session_context_is_worded_for_devin(self):
        o = devin(
            self.repo,
            "session-context",
            {"hook_event_name": "SessionStart", "source": "startup"},
        )
        ctx = o["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(o["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn(
            "Level: STANDALONE", ctx
        )  # found the project via DEVIN_PROJECT_DIR
        self.assertIn("HOST: Devin", ctx)
        rules = ctx.split("HOST: Devin")[0]
        for claude_only in (
            "ToolSearch",
            "AskUserQuestion",
            "--via claude-code",
            "${CLAUDE_PLUGIN_ROOT}",
            "Never put questions in reply text",
        ):
            self.assertNotIn(claude_only, rules)
        self.assertIn((PLUGIN / "engine" / "groundwork.py").as_posix(), ctx)

    def test_skill_notice_arrives_after_the_call(self):
        o = devin(
            self.repo,
            "skill-notice",
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "skill",
                "tool_input": {"name": "frontend-design"},
            },
        )
        self.assertEqual(o["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertIn("frontend-design", o["hookSpecificOutput"]["additionalContext"])


class DevinApprove(CheckBase):
    def test_typed_approve_runs_from_the_prompt_hook(self):
        o = devin(
            self.ws,
            "prompt-reminder",
            {
                "hook_event_name": "UserPromptSubmit",
                "prompt": f"/groundwork-specflow:approve {self.rfc.stem}",
            },
        )
        self.assertIn(
            "[groundwork approve]", o["hookSpecificOutput"]["additionalContext"]
        )


class ClaudeUnchanged(Base):
    def test_claude_payload_keeps_claude_output(self):
        git_init(self.root / "r")
        r = subprocess.run(
            [sys.executable, str(CA), "gate"],
            cwd=self.root,
            capture_output=True,
            text=True,
            input=json.dumps(
                {
                    "cwd": str(self.root / "r"),
                    "tool_name": "Write",
                    "tool_input": {"file_path": str(self.root / "r" / "a.py")},
                }
            ),
            env=ENV,
            check=False,
        )
        self.assertEqual(
            json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        r = subprocess.run(
            [sys.executable, str(CA), "session-context"],
            cwd=self.root / "r",
            capture_output=True,
            text=True,
            input="{}",
            env=ENV,
            check=False,
        )
        self.assertNotIn("HOST: Devin", r.stdout)
        self.assertIn("AskUserQuestion", r.stdout)


class DevinPackaging(unittest.TestCase):
    def test_manifest_matches_claude_manifest(self):
        claude = json.loads(
            (PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        dev = json.loads(
            (PLUGIN / ".devin-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        for k in ("name", "version", "description", "license", "repository"):
            self.assertEqual(dev[k], claude[k], k)
        for d in dev["skills"]:
            self.assertTrue((PLUGIN / d).is_dir(), d)

    def test_devin_command_skills_are_user_only_and_mirror_claude_commands(self):
        for cmd in (PLUGIN / "commands").glob("*.md"):
            skill = PLUGIN / "devin" / "commands" / cmd.stem / "SKILL.md"
            self.assertTrue(skill.exists(), skill)
            front = skill.read_text(encoding="utf-8").split("---")[1]
            self.assertIn(f"name: {cmd.stem}", front)
            if "disable-model-invocation: true" in cmd.read_text(encoding="utf-8"):
                self.assertIn('triggers: ["user"]', front)

    def test_hook_matchers_cover_both_harnesses(self):
        cfg = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))[
            "hooks"
        ]

        def subs_for(event, tool):
            return {
                h["command"].split("||")[0].split()[-1]
                for e in cfg.get(event, [])
                if re.search(e.get("matcher", ""), tool)
                for h in e["hooks"]
            }

        for tool in (
            "Write",
            "Edit",
            "MultiEdit",
            "NotebookEdit",
            "write",
            "edit",
            "apply_patch",
            "notebook_edit",
        ):
            self.assertEqual(subs_for("PreToolUse", tool), {"gate"}, tool)
        for tool in ("Bash", "exec"):
            self.assertEqual(subs_for("PreToolUse", tool), {"gate-bash"}, tool)
        for tool in ("mcp__fs__edit_file", "read", "Read", "get_output"):
            self.assertEqual(subs_for("PreToolUse", tool), set(), tool)
        self.assertEqual(subs_for("PreToolUse", "Skill"), {"skill-notice"})
        self.assertEqual(subs_for("PostToolUse", "skill"), {"skill-notice"})
        self.assertEqual(subs_for("PostToolUse", "Skill"), set())
        for event in (
            "SessionStart",
            "UserPromptSubmit",
            "Stop",
        ):  # Devin runs non-tool hooks only without a matcher
            self.assertTrue(all(not e.get("matcher") for e in cfg[event]), event)


if __name__ == "__main__":
    unittest.main()
