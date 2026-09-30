"""End-to-end tests: drive groundwork.py exactly as the hooks and slash commands do."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CA = Path(__file__).resolve().parents[1] / "engine" / "groundwork.py"
ENV = {**os.environ, "HOME": "/nonexistent-home", "GIT_CONFIG_GLOBAL": "/dev/null",
       "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com"}
ENV.pop("GROUNDWORK_ENFORCEMENT", None)


def ca(cwd, *args, stdin=None):
    return subprocess.run([sys.executable, str(CA), *args], cwd=cwd, input=stdin,
                          capture_output=True, text=True, env=ENV)


def git_init(p):
    Path(p).mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(p)], check=True, env=ENV)


def hook(cwd, event_cmd, tool_input):
    r = ca(cwd, event_cmd, stdin=json.dumps({"cwd": str(cwd), "tool_input": tool_input}))
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None


def denied(cwd, path):
    o = hook(cwd, "gate", {"file_path": str(path)})
    return bool(o and o.get("permissionDecision") == "deny"), (o or {}).get("permissionDecisionReason", "")


def fill(path):
    """Simulate the agent finishing a document: strip every unresolved marker."""
    t = Path(path).read_text()
    Path(path).write_text(re.sub(r"\[(TODO|NEEDS CLARIFICATION)[^\]]*\]", "filled", t))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()


class Detection(Base):
    def level(self, p):
        o = hook(p, "session-context", {})
        return re.search(r"Level: (\w+)", o["additionalContext"]).group(1)

    def test_plain_dir_is_unknown_and_code_is_blocked(self):
        self.assertEqual(self.level(self.root), "UNKNOWN")
        d, why = denied(self.root, self.root / "app.py")
        self.assertTrue(d)
        self.assertIn("neither a git repository nor a workspace", why)

    def test_git_repo_alone_is_standalone(self):
        git_init(self.root / "r")
        self.assertEqual(self.level(self.root / "r"), "STANDALONE")

    def test_dir_holding_repos_is_workspace(self):
        git_init(self.root / "ws" / "api"); git_init(self.root / "ws" / "web")
        self.assertEqual(self.level(self.root / "ws"), "WORKSPACE")

    def test_repo_under_project_md_is_repo_level(self):
        git_init(self.root / "ws" / "api")
        (self.root / "ws" / "PROJECT.md").write_text("# p")
        self.assertEqual(self.level(self.root / "ws" / "api"), "REPO")

    def test_gate_agrees_with_session_workspace_before_project_md_exists(self):
        git_init(self.root / "shop" / "api"); git_init(self.root / "shop" / "web")
        f = self.root / "shop" / "api" / "m.py"
        o = hook(self.root / "shop", "gate", {"file_path": str(f)})
        self.assertIn("workspace/PROJECT.md", o["permissionDecisionReason"])
        self.assertIn("workspace/CONTRACTS/", o["permissionDecisionReason"])

    def test_sibling_repos_without_project_md_are_not_a_workspace(self):
        git_init(self.root / "projects" / "a"); git_init(self.root / "projects" / "b")
        self.assertEqual(self.level(self.root / "projects" / "a"), "STANDALONE")


class Lifecycle(Base):
    def setUp(self):
        super().setUp()
        self.ws = self.root / "ws"
        self.api = self.ws / "api"
        git_init(self.api)
        (self.ws / "PROJECT.md").write_text("# ws")   # marks the workspace

    def test_full_path(self):
        code = self.api / "src" / "app.py"
        # 1. foundation missing -> blocked, and it says bootstrap
        d, why = denied(self.api, code)
        self.assertTrue(d); self.assertIn("foundation", why)
        # docs are always writable
        self.assertFalse(denied(self.api, self.api / "ARCHITECTURE.md")[0])

        # 2. scaffold repo + workspace foundations; unfinished ([TODO]) still blocks
        self.assertEqual(ca(self.api, "scaffold").returncode, 0)
        (self.ws / "PROJECT.md").unlink()
        self.assertEqual(ca(self.ws, "scaffold").returncode, 0)
        self.assertTrue(all((self.ws / f).exists() for f in
                            ["PROJECT.md", "ARCHITECTURE.md", "CONSTITUTION.md", "AGENTS.md"]))
        self.assertTrue((self.ws / "CONTRACTS").is_dir() and (self.ws / "DECISIONS" / "README.md").exists())
        self.assertIn("unfinished", denied(self.api, code)[1])
        for f in ["ARCHITECTURE.md", "AGENTS.md"]:
            fill(self.api / f)
        self.assertIn("workspace/PROJECT.md", denied(self.api, code)[1])   # repo answers for workspace too
        for f in ["PROJECT.md", "ARCHITECTURE.md", "CONSTITUTION.md", "AGENTS.md"]:
            fill(self.ws / f)
        d, why = denied(self.api, code)
        self.assertTrue(d); self.assertIn("no active feature", why)

        # 3. RFC in the WORKSPACE; agent cannot approve
        p = ca(self.ws, "new-rfc", "add-widgets", "--title", "Add widgets").stdout.strip()
        rfc = Path(p)
        self.assertEqual(rfc.parent, self.ws / "DECISIONS")
        r = ca(self.ws, "approve", str(rfc))
        self.assertNotEqual(r.returncode, 0)                       # markers block approval
        self.assertIn("marker", r.stderr + r.stdout)
        fill(rfc)
        # forged frontmatter is worthless
        rfc.write_text(rfc.read_text().replace("status: draft", "status: approved"))
        r = ca(self.api, "new-feature", "widgets", "--rfc", "RFC-0001")
        self.assertEqual(r.returncode, 0, r.stderr)
        st = ca(self.api, "status").stdout
        self.assertIn("RFC-0001-add-widgets.md is draft", st)         # real state, not the forged text
        # the agent may not touch approval records or run approve via Bash
        self.assertTrue(denied(self.api, self.api / ".groundwork" / "approvals.json")[0])
        b = hook(self.api, "gate-bash", {"command": "python3 x/groundwork.py approve foo"})
        self.assertEqual(b["permissionDecision"], "deny")
        b = hook(self.api, "gate-bash", {"command": "echo '{}' > .groundwork/approvals.json"})
        self.assertEqual(b["permissionDecision"], "deny")
        self.assertIsNone(hook(self.api, "gate-bash", {"command": "pytest -q"}))

        # 4. human approves RFC; spec still not -> still blocked
        self.assertEqual(ca(self.ws, "approve", "RFC-0001", "--as", "lead").returncode, 0)
        self.assertIn("RFC-0001-add-widgets.md is approved", ca(self.api, "status").stdout)
        d, why = denied(self.api, code)
        self.assertTrue(d); self.assertIn("spec.md", why)

        # 5. spec approved, plan/tasks/evals unfinished -> blocked on plan
        spec = self.api / "specs" / "001-widgets" / "spec.md"
        fill(spec)
        self.assertEqual(ca(self.api, "approve", str(spec), "--as", "lead").returncode, 0)
        d, why = denied(self.api, code)
        self.assertTrue(d); self.assertIn("plan.md", why)
        for n in ("plan", "tasks", "evals"):
            fill(self.api / "specs" / "001-widgets" / f"{n}.md")

        # 6. everything ready -> code allowed
        self.assertFalse(denied(self.api, code)[0])
        self.assertIn("implement", ca(self.api, "status").stdout)

        # 7. editing the approved spec makes approval stale -> blocked again
        spec.write_text(spec.read_text() + "\nA new requirement.\n")
        d, why = denied(self.api, code)
        self.assertTrue(d); self.assertIn("stale", why)

    def test_multi_signoff_rfc(self):
        ca(self.ws, "scaffold")
        rfc = Path(ca(self.ws, "new-rfc", "x").stdout.strip())
        fill(rfc)
        rfc.write_text(rfc.read_text().replace("signoffs_required: 1", "signoffs_required: 2"))
        self.assertIn("in-review", ca(self.ws, "approve", str(rfc), "--as", "a").stdout)
        self.assertIn("in-review", ca(self.ws, "approve", str(rfc), "--as", "a").stdout)  # same person twice
        self.assertIn("approved", ca(self.ws, "approve", str(rfc), "--as", "b").stdout)

    def test_bypass_is_logged_and_expires_into_gate(self):
        ca(self.api, "scaffold"); ca(self.ws, "scaffold")
        code = self.api / "x.py"
        self.assertTrue(denied(self.api, code)[0])
        r = ca(self.api, "bypass", "prod", "is", "down")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(denied(self.api, code)[0])
        self.assertIn("prod is down", (self.api / ".groundwork" / "bypass.log").read_text())
        b = json.loads((self.api / ".groundwork" / "bypass.json").read_text()); b["until"] = 1
        (self.api / ".groundwork" / "bypass.json").write_text(json.dumps(b))
        self.assertTrue(denied(self.api, code)[0])

    def test_enforcement_off_and_warn(self):
        ca(self.api, "scaffold")
        for mode, blocked in (("off", False), ("warn", False), ("block", True)):
            cfg = self.api / ".groundwork" / "config.json"
            cfg.write_text(json.dumps({"enforcement": mode}))
            self.assertEqual(denied(self.api, self.api / "x.py")[0], blocked, mode)

    def test_workspace_level_code_is_not_gated_but_prompt_reminder_works(self):
        git_init(self.ws / "web")
        o = hook(self.ws, "prompt-reminder", {})
        self.assertIn("level=workspace", o["additionalContext"])
        self.assertFalse(denied(self.ws, self.ws / "notes.txt")[0])


if __name__ == "__main__":
    unittest.main()
