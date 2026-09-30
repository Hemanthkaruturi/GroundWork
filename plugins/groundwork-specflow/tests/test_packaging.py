"""Exercise the published hook configuration, including paths containing spaces."""
import json
import subprocess
from pathlib import Path

from test_flow import Base, ENV, git_init


PLUGIN = Path(__file__).resolve().parents[1]


class Packaging(Base):
    def test_configured_hooks_keep_normal_permissions_and_block_unapproved_edits(self):
        repo = self.root / "project with spaces"
        git_init(repo)
        config = json.loads((PLUGIN / "hooks/hooks.json").read_text())
        for event, entries in config["hooks"].items():
            for entry in entries:
                for handler in entry["hooks"]:
                    with self.subTest(event=event, matcher=entry.get("matcher")):
                        args = [arg.replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN))
                                for arg in handler["args"]]
                        payload = {"cwd": str(repo), "tool_input": {
                            "file_path": str(repo / "app.py"), "command": "echo code > app.py",
                            "skill": "another-plugin:design"}}
                        result = subprocess.run([handler["command"], *args], cwd=repo,
                                                input=json.dumps(payload), capture_output=True,
                                                text=True, env=ENV)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        output = json.loads(result.stdout) if result.stdout.strip() else {}
                        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
                        self.assertNotEqual(decision, "allow")
                        if args[-1] in ("gate", "gate-bash"):
                            self.assertEqual(decision, "deny")
                            # Project documents remain editable through the same handler.
                            payload["tool_input"] = {"file_path": str(repo / "ARCHITECTURE.md"),
                                                     "command": "cat ARCHITECTURE.md"}
                            result = subprocess.run([handler["command"], *args], cwd=repo,
                                                    input=json.dumps(payload), capture_output=True,
                                                    text=True, env=ENV)
                            self.assertEqual(result.returncode, 0, result.stderr)
                            self.assertEqual(result.stdout.strip(), "")
                        else:
                            self.assertIsNone(decision)
