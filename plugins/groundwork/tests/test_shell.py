"""The shell is gated like the Write tool: `cat > f <<EOF`, sed -i, tee, cp, inline scripts."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import CheckBase  # noqa: E402
from test_flow import hook  # noqa: E402

HEREDOC = "cat > app/static/index.html <<'EOF'\n<!doctype html>\n<div class=\"layout\"><aside>x > y</aside></div>\nEOF"


class ShellGate(CheckBase):
    def blocked(self, cmd, cwd=None):
        o = hook(cwd or self.api, "gate-bash", {"command": cmd})
        return bool(o and o.get("permissionDecision") == "deny"), (o or {}).get("permissionDecisionReason", "")

    def close_gate(self):
        (self.api / ".groundwork" / "active").unlink()          # no active feature: code edits must be refused

    def test_the_screenshot_case_heredoc_write_is_blocked_without_an_approved_spec(self):
        self.close_gate()
        b, why = self.blocked(HEREDOC)
        self.assertTrue(b); self.assertIn("shell command writes", why); self.assertIn("index.html", why)

    def test_same_command_is_fine_when_the_feature_is_ready(self):
        self.assertFalse(self.blocked(HEREDOC)[0])

    def test_all_the_ways_of_writing_code(self):
        self.close_gate()
        for cmd in ["echo 1 > src/app.py", "echo 1 >> src/app.py", "printf x | tee src/app.py", "sed -i 's/a/b/' src/app.py",
                    "sed -i -e 's/a/b/' src/app.py", "cp tmp.py src/app.py", "mv tmp.py src/app.py",
                    "cd src && echo 1 > app.py", "python3 - <<'P'\nopen('x.py','w').write('1')\nP",
                    "python3 -c \"from pathlib import Path; Path('x.py').write_text('1')\"", "node -e \"require('fs').writeFileSync('a.js','1')\"",
                    "git apply fix.diff", "patch -p1 < fix.diff", "curl -o src/lib.js https://example.com/x.js",
                    "dd if=a of=src/app.py", "cat <<'EOF' > src/app.py\nprint(1)\nEOF"]:
            self.assertTrue(self.blocked(cmd)[0], cmd)

    def test_ordinary_commands_are_never_blocked(self):
        self.close_gate()
        for cmd in ["ls -la", "git status", "pytest -q 2>&1 | tail -5", "uv run pytest > out.log", "ls > /dev/null",
                    "echo \"a > b\"", "cat src/app.py | grep x", "python3 -m unittest", "npm test", "uv add requests",
                    "echo hi > /tmp/x.py", "grep -rn 'x > y' src", "git diff > /tmp/p.diff", "mkdir -p build && ls",
                    "sed 's/a/b/' src/app.py", "python3 script.py", "find . -name '*.py' | wc -l"]:
            self.assertFalse(self.blocked(cmd)[0], cmd)

    def test_documents_and_ignored_paths_are_allowed(self):
        self.close_gate()
        for cmd in ["cat <<'EOF' > README.md\n<b>x</b> > y\nEOF", "echo x >> ARCHITECTURE.md", "echo x > docs/notes.md",
                    "echo x > specs/001-widgets/log.md", "echo 1 > node_modules/x/index.js", "cp a.pyc __pycache__/a.pyc",
                    "echo x > .groundwork/journal.md"]:
            self.assertFalse(self.blocked(cmd)[0], cmd)

    def test_writes_outside_the_project_are_not_ours_to_gate(self):
        self.close_gate()
        self.assertFalse(self.blocked("cp src/app.py /tmp/backup.py")[0])
        self.assertFalse(self.blocked(f"echo 1 > {self.root}/elsewhere.py")[0])

    def test_enforcement_modes_and_bypass_apply_to_the_shell_too(self):
        self.close_gate()
        cfg = self.api / ".groundwork" / "config.json"
        for mode, blocked in (("warn", False), ("off", False), ("block", True)):
            cfg.write_text(json.dumps({"standard": "0.5.0", "enforcement": mode}))
            self.assertEqual(self.blocked(HEREDOC)[0], blocked, mode)
        from test_flow import ca
        ca(self.api, "bypass", "hotfix")
        cfg.write_text(json.dumps({"standard": "0.5.0"}))
        self.assertFalse(self.blocked(HEREDOC)[0])

    def test_workspace_session_gates_writes_into_a_child_repo(self):
        self.close_gate()
        b, why = self.blocked("echo 1 > api/src/app.py", cwd=self.ws)
        self.assertTrue(b)

    def test_bug_gate_also_governs_the_shell(self):
        from test_flow import ca
        self.close_gate()
        self.assertTrue(self.blocked("echo 1 > src/fix.py")[0])
        ca(self.api, "new-bug", "crash")                         # open bug: still no edits
        self.assertTrue(self.blocked("echo 1 > src/fix.py")[0])

    def test_protected_commands_still_denied(self):
        self.assertTrue(self.blocked("python3 x/groundwork.py approve foo")[0])
        self.assertTrue(self.blocked("echo '{}' > .groundwork/approvals.json")[0])


if __name__ == "__main__":
    unittest.main()
