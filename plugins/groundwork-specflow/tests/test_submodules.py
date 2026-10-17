"""The workspace in git, with its repos as submodules (`groundwork.py submodules`)."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_flow import CA, ENV, Base, git_init

# local file remotes are refused by default since git 2.38.1; allow them in this sandbox only
G = {
    **ENV,
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "protocol.file.allow",
    "GIT_CONFIG_VALUE_0": "always",
}


def git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        env=G,
        capture_output=True,
        text=True,
        check=False,
    )


def commit(repo, name="a", text="x"):
    (Path(repo) / name).write_text(text, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-qm", f"edit {name}")


def run(cwd, *args):
    return subprocess.run(
        [sys.executable, str(CA), *args],
        cwd=cwd,
        env=G,
        capture_output=True,
        text=True,
        check=False,
    )


class Submodules(Base):
    def setUp(self):
        super().setUp()
        self.ws = self.root / "ws"
        self.remotes = self.root / "remotes"
        for name in ("api", "web"):
            git_init(self.ws / name)
            commit(self.ws / name)
            git(self.root, "init", "-q", "--bare", str(self.remotes / f"{name}.git"))
            git(
                self.ws / name,
                "remote",
                "add",
                "origin",
                str(self.remotes / f"{name}.git"),
            )
            git(self.ws / name, "push", "-q", "origin", "HEAD")
        self.assertEqual(run(self.ws, "mark-workspace").returncode, 0)

    def config(self):
        return json.loads((self.ws / ".groundwork" / "config.json").read_text())

    def test_undecided_is_reported_until_the_user_chooses(self):
        self.assertIn("NOT DECIDED", run(self.ws, "status").stdout)
        self.assertIn("submodules init", run(self.ws, "mark-workspace").stdout)
        r = run(self.ws, "submodules", "skip")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.config()["workspace_git"], "none")
        self.assertIn("not tracked", run(self.ws, "status").stdout)
        self.assertFalse((self.ws / ".git").exists())

    def test_dry_run_changes_nothing(self):
        r = run(self.ws, "submodules", "init", "--dry-run")
        self.assertIn("submodule api", r.stdout)
        self.assertFalse((self.ws / ".git").exists())
        self.assertNotIn("workspace_git", self.config())

    def test_init_adopts_the_clones_in_place(self):
        before = git(self.ws / "api", "rev-parse", "HEAD").stdout
        r = run(self.ws, "submodules", "init")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.ws / ".git").is_dir())
        mods = (self.ws / ".gitmodules").read_text()
        self.assertIn("path = api", mods)
        self.assertIn("path = web", mods)
        self.assertEqual(git(self.ws / "api", "rev-parse", "HEAD").stdout, before)
        self.assertIn(".env", (self.ws / ".gitignore").read_text())
        self.assertEqual(
            git(self.ws, "config", "push.recurseSubmodules").stdout.strip(), "check"
        )
        self.assertEqual(self.config()["workspace_git"], "submodules")
        self.assertNotIn("GW006", run(self.ws, "check").stdout)
        # still a repo of the workspace, seen from inside the submodule
        self.assertIn("Level: REPO", run(self.ws / "api", "status").stdout)
        # a second run is a no-op
        self.assertIn("nothing", run(self.ws, "submodules", "init").stdout)

    def test_a_repo_without_a_clean_remote_is_skipped_and_flagged(self):
        git_init(self.ws / "lib")
        commit(self.ws / "lib")
        git_init(self.ws / "empty")
        git(self.ws / "empty", "remote", "add", "origin", str(self.remotes / "e.git"))
        git_init(self.ws / "tok")
        commit(self.ws / "tok")
        git(
            self.ws / "tok",
            "remote",
            "add",
            "origin",
            "https://me:s3cret@example.com/tok.git",
        )
        r = run(self.ws, "submodules", "init")
        self.assertIn("skipped lib", r.stdout)
        self.assertIn("skipped tok", r.stdout)
        self.assertIn("skipped empty: no commit yet", r.stdout)
        mods = (self.ws / ".gitmodules").read_text()
        self.assertNotIn("s3cret", mods)
        out = run(self.ws, "check").stdout
        self.assertIn("GW006", out)
        self.assertIn("lib", out)
        self.assertIn("tok", out)

    def test_moved_and_unpushed_pointers_are_reported(self):
        run(self.ws, "submodules", "init")
        git(self.ws, "commit", "-qm", "workspace")
        commit(self.ws / "api", "b")
        out = run(self.ws, "submodules").stdout
        self.assertIn("commit the pointer here", out)
        self.assertIn("on no remote branch", out)

    def test_a_fresh_clone_is_a_workspace_and_names_missing_checkouts(self):
        # a workspace found only by its child repos: the clone has none checked out, so init records the level
        (self.ws / ".groundwork" / "config.json").write_text("{}", encoding="utf-8")
        run(self.ws, "submodules", "init")
        git(self.ws, "add", ".gitignore", ".groundwork")
        git(self.ws, "commit", "-qm", "workspace")
        clone = self.root / "clone"
        git(
            self.root, "clone", "-q", str(self.ws), str(clone)
        )  # no --recurse-submodules
        self.assertIn("Level: WORKSPACE", run(clone, "status").stdout)
        out = run(clone, "check").stdout
        self.assertIn("GW006", out)
        self.assertIn("not checked out", out)
        git(clone, "submodule", "update", "--init", "-q")
        self.assertNotIn("GW006", run(clone, "check").stdout)
        self.assertIn("Level: REPO", run(clone / "api", "status").stdout)
