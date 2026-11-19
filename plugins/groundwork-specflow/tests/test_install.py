"""setup/install.py: the project install for Codex (--codex) and Devin, without either plugin system."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_flow import ENV, Base, git_init

INSTALL = Path(__file__).resolve().parents[3] / "setup" / "install.py"
PATCH = "*** Begin Patch\n*** Add File: {}\n+x\n*** End Patch\n"


def install(project, *args):
    r = subprocess.run(
        [sys.executable, str(INSTALL), *args],
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=ENV,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def run_hook(project, hooks, event, sub, payload, cwd=None, env=None):
    """Run one installed hook command the way the harness does: through the shell, payload on stdin."""
    command = next(
        h["command"]
        for g in hooks[event]
        for h in g["hooks"]
        if f"'{sub}'" in h["command"]
    )
    r = subprocess.run(
        command,
        shell=True,
        cwd=cwd or project,
        input=json.dumps({"cwd": str(cwd or project), **payload}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**ENV, **(env or {})},
        check=False,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout.strip() else None


class CodexInstall(Base):
    def setUp(self):
        super().setUp()
        self.p = self.root / "proj"
        git_init(self.p)
        (self.p / ".codex").mkdir()
        (self.p / ".codex" / "hooks.json").write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": [
                            {"hooks": [{"type": "command", "command": "echo mine"}]}
                        ]
                    }
                }
            )
        )
        self.out = install(self.p, "--codex")
        self.hooks = json.loads((self.p / ".codex" / "hooks.json").read_text())["hooks"]

    def test_layout_and_version(self):
        self.assertTrue(
            (self.p / ".codex" / "groundwork" / "engine" / "groundwork.py").is_file()
        )
        self.assertTrue(
            (self.p / ".agents" / "skills" / "bootstrap" / "SKILL.md").is_file()
        )
        self.assertIn(
            "version=", (self.p / ".codex" / "groundwork-version").read_text()
        )
        self.assertFalse((self.p / ".devin").exists())
        self.assertIn("/hooks", self.out)
        self.assertIn("$bootstrap", self.out)

    def test_skills_are_worded_for_a_codex_project(self):
        for skill in (self.p / ".agents" / "skills").glob("*/SKILL.md"):
            text = skill.read_text()
            with self.subTest(skill=skill.parent.name):
                self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", text)
                self.assertNotIn("/groundwork-specflow:", text)
                self.assertNotIn("$ARGUMENTS", text)
                self.assertNotIn("triggers:", text)
        self.assertIn(
            "$approve",
            (self.p / ".agents" / "skills" / "approve" / "SKILL.md").read_text(),
        )

    def test_commands_are_user_only(self):
        for cmd in ("approve", "bypass", "change", "status"):
            policy = self.p / ".agents" / "skills" / cmd / "agents" / "openai.yaml"
            self.assertIn("allow_implicit_invocation: false", policy.read_text())
        self.assertFalse(
            (self.p / ".agents" / "skills" / "bootstrap" / "agents").exists()
        )

    def test_hooks_merge_with_the_users_own(self):
        stop = [h["command"] for g in self.hooks["Stop"] for h in g["hooks"]]
        self.assertIn("echo mine", stop)
        self.assertTrue(any(".codex/groundwork/engine" in c for c in stop))
        install(self.p, "--codex")  # an update replaces ours and keeps theirs
        again = json.loads((self.p / ".codex" / "hooks.json").read_text())["hooks"]
        self.assertEqual(again, self.hooks)

    def test_hooks_run_as_codex_from_a_subfolder(self):
        sub = self.p / "src"
        sub.mkdir()
        o = run_hook(
            self.p,
            self.hooks,
            "SessionStart",
            "session-rules-2",
            {"hook_event_name": "SessionStart", "source": "startup"},
            cwd=sub,
        )
        ctx = o["hookSpecificOutput"]["additionalContext"]
        self.assertIn("HOST: Codex", ctx)
        self.assertIn("`$approve <doc>`", ctx)
        self.assertNotIn("source-command", ctx)
        o = run_hook(
            self.p,
            self.hooks,
            "PreToolUse",
            "gate",
            {
                "hook_event_name": "PreToolUse",
                "turn_id": "t",
                "tool_name": "apply_patch",
                "tool_input": {"command": PATCH.format("app.py")},
            },
        )
        reason = o["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("$bypass", reason)

    def test_uninstall_keeps_the_users_hooks(self):
        install(self.p, "--codex", "--uninstall")
        left = json.loads((self.p / ".codex" / "hooks.json").read_text())
        self.assertEqual(
            left,
            {
                "hooks": {
                    "Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]
                }
            },
        )
        self.assertFalse((self.p / ".codex" / "groundwork").exists())
        self.assertEqual(list((self.p / ".agents" / "skills").iterdir()), [])

    def test_a_skill_of_the_users_own_blocks_the_install(self):
        other = self.root / "other"
        git_init(other)
        (other / ".agents" / "skills" / "status").mkdir(parents=True)
        r = subprocess.run(
            [sys.executable, str(INSTALL), "--codex"],
            cwd=other,
            capture_output=True,
            text=True,
            env=ENV,
            check=False,
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(".agents/skills/ already has status", r.stderr)
        self.assertFalse((other / ".codex").exists())


class DevinInstallUnchanged(Base):
    def test_devin_install_still_lands_in_dot_devin(self):
        p = self.root / "proj"
        git_init(p)
        install(p)
        hooks = json.loads((p / ".devin" / "hooks.v1.json").read_text())
        self.assertIn("SessionStart", hooks)  # top-level events, no "hooks" key
        self.assertIn(
            "/approve", (p / ".devin" / "skills" / "approve" / "SKILL.md").read_text()
        )
        self.assertFalse((p / ".codex").exists() or (p / ".agents").exists())
        o = run_hook(
            p,
            hooks,
            "SessionStart",
            "session-rules-2",
            {"hook_event_name": "SessionStart"},
            env={"DEVIN_PROJECT_DIR": str(p)},
        )
        self.assertIn("HOST: Devin", o["hookSpecificOutput"]["additionalContext"])

    def test_devin_install_speaks_devin_commands_everywhere(self):
        # A live run saw /groundwork-specflow:<name> in denials, reminders, init output and written templates.
        p = self.root / "proj"
        git_init(p)
        install(p)
        hooks = json.loads((p / ".devin" / "hooks.v1.json").read_text())
        env = {"DEVIN_PROJECT_DIR": str(p)}
        deny = run_hook(
            p,
            hooks,
            "PreToolUse",
            "gate",
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "write",
                "tool_input": {"file_path": str(p / "app.py")},
            },
            env=env,
        )
        rem = run_hook(
            p, hooks, "UserPromptSubmit", "prompt-reminder", {"prompt": "hi"}, env=env
        )
        engine = p / ".devin" / "groundwork" / "engine" / "groundwork.py"
        init = subprocess.run(
            [sys.executable, str(engine), "init"],
            cwd=p,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**ENV, **env},
            check=False,
        )
        texts = [json.dumps(deny), json.dumps(rem), init.stdout + init.stderr]
        texts += [f.read_text(encoding="utf-8") for f in p.glob("*.md")]
        for t in texts:
            self.assertNotIn("/groundwork-specflow:", t)
        self.assertIn("/bypass", json.dumps(deny))

    def test_installed_engine_ignores_its_bytecode(self):
        p = self.root / "proj"
        git_init(p)
        install(p)
        self.assertIn(
            "__pycache__/", (p / ".devin" / "groundwork" / ".gitignore").read_text()
        )


if __name__ == "__main__":
    unittest.main()
