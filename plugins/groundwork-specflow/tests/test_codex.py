"""Codex compatibility: Codex's hook payloads (`turn_id`, `apply_patch` with a `command` body, `Bash`) and PLUGIN_ROOT."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import CheckBase
from test_flow import CA, ENV, Base, git_init

PLUGIN = Path(__file__).resolve().parents[1]


def codex(project, sub, payload):
    """Run a hook the way Codex does: `cwd` and `turn_id` in the payload, PLUGIN_ROOT and CLAUDE_PLUGIN_ROOT set."""
    env = {**ENV, "PLUGIN_ROOT": str(PLUGIN), "CLAUDE_PLUGIN_ROOT": str(PLUGIN)}
    full = {"cwd": str(project), "session_id": "s", "model": "m", **payload}
    r = subprocess.run(
        [sys.executable, str(CA), sub],
        cwd=project,
        input=json.dumps(full),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout.strip() else None


def denied(o):
    return bool(o) and o["hookSpecificOutput"]["permissionDecision"] == "deny"


def tool(name, inp):
    return {
        "hook_event_name": "PreToolUse",
        "turn_id": "t",
        "tool_name": name,
        "tool_use_id": "u",
        "tool_input": inp,
    }


PATCH = "*** Begin Patch\n*** Add File: {}\n+x\n*** End Patch\n"


class CodexGates(Base):
    def setUp(self):
        super().setUp()
        self.repo = self.root / "repo"
        git_init(self.repo)

    def test_apply_patch_is_gated_and_denied_in_codex_format(self):
        o = codex(
            self.repo, "gate", tool("apply_patch", {"command": PATCH.format("app.py")})
        )
        self.assertTrue(denied(o), o)
        self.assertNotIn("decision", o)
        self.assertIsNone(
            codex(
                self.repo,
                "gate",
                tool("apply_patch", {"command": PATCH.format("ARCHITECTURE.md")}),
            )
        )

    def test_a_multi_file_patch_names_the_held_file(self):
        patch = (
            "*** Begin Patch\n*** Update File: ARCHITECTURE.md\n@@\n-a\n+b\n"
            "*** Add File: pyproject.toml\n+[project]\n*** End Patch\n"
        )
        o = codex(self.repo, "gate", tool("apply_patch", {"command": patch}))
        reason = o["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("also writes", reason)
        self.assertIn("pyproject.toml", reason)
        self.assertNotIn(
            "also writes",
            codex(
                self.repo,
                "gate",
                tool("apply_patch", {"command": PATCH.format("app.py")}),
            )["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_messages_name_the_codex_commands_not_slash_commands(self):
        o = codex(
            self.repo, "gate", tool("apply_patch", {"command": PATCH.format("app.py")})
        )
        reason = o["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("$source-command-bypass", reason)
        self.assertNotIn("/groundwork-specflow:", reason)
        ctx = codex(
            self.repo,
            "session-context",
            {"hook_event_name": "SessionStart", "source": "startup"},
        )
        rules = ctx["hookSpecificOutput"]["additionalContext"].split("HOST: Codex")[0]
        self.assertNotIn("/groundwork-specflow:", rules)

    def test_shell_writes_and_human_acts_are_blocked(self):
        for cmd in (
            "echo code > app.py",
            "python3 x/groundwork.py approve RFC-0001",
            ["bash", "-lc", "python3 x/groundwork.py approve RFC-0001"],
        ):
            with self.subTest(cmd=cmd):
                self.assertTrue(
                    denied(
                        codex(self.repo, "gate-bash", tool("Bash", {"command": cmd}))
                    )
                )
        self.assertIsNone(
            codex(self.repo, "gate-bash", tool("Bash", {"command": "git status"}))
        )

    def test_unexpected_shell_input_does_not_crash_the_gate(self):
        for inp in ({"command": None}, {"command": 7}, "echo hi", {}):
            with self.subTest(inp=inp):
                codex(self.repo, "gate-bash", tool("Bash", inp))

    def test_session_context_is_worded_for_codex(self):
        o = codex(
            self.repo,
            "session-context",
            {"hook_event_name": "SessionStart", "source": "startup"},
        )
        ctx = o["hookSpecificOutput"]["additionalContext"]
        self.assertIn("HOST: Codex", ctx)
        self.assertNotIn("HOST: Devin", ctx)
        rules = ctx.split("HOST: Codex")[0]
        for claude_only in (
            "ToolSearch",
            "AskUserQuestion",
            "--via claude-code",
            "${CLAUDE_PLUGIN_ROOT}",
        ):
            self.assertNotIn(claude_only, rules)
        self.assertIn("--via codex", rules)
        self.assertIn("$source-command-approve", ctx)
        self.assertIn((PLUGIN / "engine" / "groundwork.py").as_posix(), ctx)


class CodexApprove(CheckBase):
    def test_typed_codex_skill_mention_runs_from_the_prompt_hook(self):
        for prompt in (
            f"$source-command-approve {self.rfc.stem}",
            f"$groundwork-specflow:source-command-approve {self.rfc.stem}",
            f"/groundwork-specflow:approve {self.rfc.stem}",
        ):
            with self.subTest(prompt=prompt):
                o = codex(
                    self.ws,
                    "prompt-reminder",
                    {
                        "hook_event_name": "UserPromptSubmit",
                        "turn_id": "t",
                        "prompt": prompt,
                    },
                )
                self.assertIn(
                    "[groundwork approve]", o["hookSpecificOutput"]["additionalContext"]
                )

    def test_a_mention_mid_sentence_is_not_a_human_act(self):
        o = codex(
            self.ws,
            "prompt-reminder",
            {
                "hook_event_name": "UserPromptSubmit",
                "turn_id": "t",
                "prompt": f"please $source-command-approve {self.rfc.stem}",
            },
        )
        self.assertNotIn(
            "[groundwork approve]", o["hookSpecificOutput"]["additionalContext"]
        )


class CodexCommandNames(unittest.TestCase):
    def test_slash_commands_become_codex_skill_mentions(self):
        sys.path.insert(0, str(PLUGIN / "engine"))
        import groundwork_host as G

        self.assertEqual(
            G.codex_commands(
                "/groundwork-specflow:approve x, /groundwork-specflow:bypass y, "
                "/groundwork-specflow:status, /groundwork-specflow:bootstrap"
            ),
            "$source-command-approve x, $source-command-bypass y, "
            "$groundwork-specflow:source-command-status, $groundwork-specflow:bootstrap",
        )


if __name__ == "__main__":
    unittest.main()
