"""Exercise the published hook configuration, including paths containing spaces.

Hook commands run through a shell, as Claude Code runs them, so the python3-or-python fallback is exercised too.
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from test_flow import ENV, Base, git_init

PLUGIN = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("sh"), "hook commands run through a POSIX shell")
class Packaging(Base):
    def test_configured_hooks_keep_normal_permissions_and_block_unapproved_edits(self):
        repo = self.root / "project with spaces"
        git_init(repo)
        config = json.loads((PLUGIN / "hooks/hooks.json").read_text())
        for event, entries in config["hooks"].items():
            for entry in entries:
                for handler in entry["hooks"]:
                    with self.subTest(event=event, matcher=entry.get("matcher")):
                        command = handler["command"]
                        self.assertNotIn("args", handler)
                        self.assertIn("python3 ", command)
                        self.assertIn(
                            "|| python ", command
                        )  # fallback when python3 is absent
                        env = {**ENV, "CLAUDE_PLUGIN_ROOT": PLUGIN.as_posix()}
                        sub = command.split("||")[0].split()[-1]
                        payload = {
                            "cwd": str(repo),
                            "tool_input": {
                                "file_path": str(repo / "app.py"),
                                "command": "echo code > app.py",
                                "skill": "another-plugin:design",
                            },
                        }
                        result = subprocess.run(
                            ["sh", "-c", command],
                            cwd=repo,
                            input=json.dumps(payload),
                            capture_output=True,
                            text=True,
                            env=env,
                            check=False,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        output = (
                            json.loads(result.stdout) if result.stdout.strip() else {}
                        )
                        decision = output.get("hookSpecificOutput", {}).get(
                            "permissionDecision"
                        )
                        self.assertNotEqual(decision, "allow")
                        if sub in ("gate", "gate-bash"):
                            self.assertEqual(decision, "deny")
                            # Project documents remain editable through the same handler.
                            payload["tool_input"] = {
                                "file_path": str(repo / "ARCHITECTURE.md"),
                                "command": "cat ARCHITECTURE.md",
                            }
                            result = subprocess.run(
                                ["sh", "-c", command],
                                cwd=repo,
                                input=json.dumps(payload),
                                capture_output=True,
                                text=True,
                                env=env,
                                check=False,
                            )
                            self.assertEqual(result.returncode, 0, result.stderr)
                            self.assertEqual(result.stdout.strip(), "")
                        else:
                            self.assertIsNone(decision)
