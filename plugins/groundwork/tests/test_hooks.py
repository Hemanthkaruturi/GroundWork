"""Git hook installer: real `git commit`s against real hooks."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import CheckBase  # noqa: E402
from test_flow import ENV, ca  # noqa: E402

GENV = {**ENV, "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}


def commit(repo, msg="c", env=None, *extra):
    (Path(repo) / "f.txt").write_text(msg + str(os.urandom(4).hex()))
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=GENV)
    return subprocess.run(["git", "-C", str(repo), "commit", "-qm", msg, *extra], capture_output=True,
                          text=True, env={**GENV, **(env or {})})


class Hooks(CheckBase):
    def test_conforming_commit_passes_and_error_blocks(self):
        self.assertEqual(ca(self.api, "hooks", "install").returncode, 0)
        self.assertEqual(commit(self.api).returncode, 0)
        self.edit(self.fdir / "spec.md", lambda t: t.replace("## 8. Manual test", "## 8. How to try"))
        # (that edit also makes the approval stale - a definite error)
        r = commit(self.api)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("GW02", r.stdout + r.stderr)
        self.assertIn("blocked", r.stdout + r.stderr)

    def test_bypasses(self):
        ca(self.api, "hooks", "install")
        (self.api / "ARCHITECTURE.md").unlink()                      # GW001 error
        self.assertNotEqual(commit(self.api).returncode, 0)
        self.assertEqual(commit(self.api, "n", None, "--no-verify").returncode, 0)
        self.assertEqual(commit(self.api, "s", {"GROUNDWORK_SKIP": "1"}).returncode, 0)

    def test_warnings_block_only_when_strict(self):
        self.edit(self.api / "AGENTS.md", lambda t: t + "\n[NEEDS CLARIFICATION: how do we test?]\n")  # warning only
        ca(self.api, "hooks", "install")
        self.assertEqual(commit(self.api).returncode, 0)
        ca(self.api, "hooks", "install", "--strict")
        r = commit(self.api)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("GW002", r.stdout + r.stderr)

    def test_enforcement_setting_is_respected(self):
        (self.api / "ARCHITECTURE.md").unlink()
        ca(self.api, "hooks", "install")
        cfg = self.api / ".groundwork" / "config.json"
        for mode, ok in (("warn", True), ("off", True), ("block", False)):
            cfg.write_text('{"standard": "0.5.0", "enforcement": "%s"}' % mode)
            self.assertEqual(commit(self.api, mode).returncode == 0, ok, mode)

    def test_existing_hook_is_chained_and_restored(self):
        hooks = self.api / ".git" / "hooks"
        (hooks / "pre-commit").write_text("#!/bin/sh\necho theirs >&2\nexit 7\n")
        (hooks / "pre-commit").chmod(0o755)
        out = ca(self.api, "hooks", "install").stdout
        self.assertIn("kept your existing pre-commit", out)
        r = commit(self.api)
        self.assertNotEqual(r.returncode, 0)                        # their hook still gets to block
        self.assertIn("theirs", r.stderr + r.stdout)
        ca(self.api, "hooks", "uninstall")
        self.assertIn("theirs", (hooks / "pre-commit").read_text())
        self.assertFalse((hooks / "pre-commit.groundwork-orig").exists())

    def test_install_is_idempotent_and_uninstall_clean(self):
        ca(self.api, "hooks", "install"); ca(self.api, "hooks", "install")
        self.assertFalse((self.api / ".git" / "hooks" / "pre-commit.groundwork-orig").exists())
        self.assertIn("pre-commit", ca(self.api, "hooks", "status").stdout)
        ca(self.api, "hooks", "uninstall")
        self.assertIn("not installed", ca(self.api, "hooks", "status").stdout)
        self.assertEqual(commit(self.api).returncode, 0)

    def test_pre_push_option(self):
        ca(self.api, "hooks", "install", "--pre-push")
        self.assertTrue((self.api / ".git" / "hooks" / "pre-push").exists())

    def test_vendored_engine_works_without_the_plugin(self):
        ca(self.api, "hooks", "install", "--vendor")
        eng = self.api / ".groundwork" / "engine" / "groundwork.py"
        self.assertTrue(eng.exists())
        r = subprocess.run([sys.executable, str(eng), "check", "--strict"], cwd=self.api,
                           capture_output=True, text=True, env=ENV)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # the vendored copy is a full engine: it can onboard and diagnose too
        for cmd in (["doctor"], ["init", "--dry-run"]):
            r = subprocess.run([sys.executable, str(eng), *cmd], cwd=self.api, capture_output=True, text=True, env=ENV)
            self.assertEqual(r.returncode, 0, cmd and (r.stdout + r.stderr))
        # the hook prefers the vendored copy even if the plugin path is gone
        hook = (self.api / ".git" / "hooks" / "pre-commit").read_text()
        (self.api / ".git" / "hooks" / "pre-commit").write_text(
            hook.replace(str(Path(__file__).resolve().parents[1] / "engine" / "groundwork.py"), "/gone/groundwork.py"))
        self.assertEqual(commit(self.api).returncode, 0)

    def test_workspace_install_covers_every_repo(self):
        from test_flow import git_init
        git_init(self.ws / "web")
        out = ca(self.ws, "hooks", "install").stdout
        self.assertIn("api:", out); self.assertIn("web:", out)
        self.assertTrue((self.ws / "web" / ".git" / "hooks" / "pre-commit").exists())

    def test_no_git_repo_is_a_clear_error(self):
        r = ca(self.root, "hooks", "install")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("No git repository", r.stderr)


if __name__ == "__main__":
    unittest.main()
