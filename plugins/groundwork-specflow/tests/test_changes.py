"""Feature change logs (issue #8): changes to a built feature are recorded in its changes.md."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import CheckBase, check
from test_flow import CA, ENV, ca, denied, hook


def hook_ctx(cwd, prompt):
    r = ca(
        cwd,
        "prompt-reminder",
        stdin=json.dumps({"cwd": str(cwd), "prompt": prompt}),
    )
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def commit_all(repo):
    for args in (["add", "-A"], ["commit", "-q", "-m", "built"]):
        subprocess.run(
            ["git", "-c", "user.email=t@example.com", "-c", "user.name=T", *args],
            cwd=repo,
            check=True,
            env=ENV,
        )


class ChangeLog(CheckBase):
    def build(self):
        (self.api / "app.py").write_text("x = 1\n", encoding="utf-8")
        (self.fdir / "handover.md").write_text("# Handover\nDone.\n", encoding="utf-8")
        commit_all(self.api)

    def test_change_appends_a_row_with_who_what_and_ref(self):
        r = ca(
            self.api,
            "change",
            "Moved",
            "app.py | into src",
            "--requested-by",
            "Lead Person",
            "--files",
            "src/app.py",
            "--via",
            "devin",
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = (self.fdir / "changes.md").read_text(encoding="utf-8")
        row = text.strip().splitlines()[-1]
        self.assertIn("| Lead Person |", row)
        self.assertIn("(via devin)", row)
        self.assertIn("Moved app.py \\| into src", row)
        self.assertIn("`src/app.py`", row)
        self.assertIn("RFC-0001 · 001-widgets", row)
        ca(self.api, "change", "Renamed x", "--requested-by", "Dev Two")
        text = (self.fdir / "changes.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("| When |"), 1)
        self.assertIn("Renamed x", text.strip().splitlines()[-1])

    def test_change_needs_a_requester(self):
        r = ca(self.api, "change", "Moved a file")
        self.assertNotEqual(r.returncode, 0)

    def test_code_changed_after_the_build_warns_until_recorded(self):
        self.build()
        self.assertNotIn("GW093", check(self.ws)[1])
        (self.api / "app.py").write_text("x = 2\n", encoding="utf-8")
        _, ids, items = check(self.ws)
        self.assertIn("GW093", ids)
        self.assertTrue(
            any(f["id"] == "GW093" and "app.py" in f["message"] for f in items)
        )
        ca(self.api, "change", "x is 2", "--requested-by", "Lead Person")
        self.assertNotIn("GW093", check(self.ws)[1])

    def test_documents_alone_do_not_warn(self):
        self.build()
        (self.fdir / "log.md").write_text("# Log\n- note\n", encoding="utf-8")
        self.assertNotIn("GW093", check(self.ws)[1])

    def test_rules_tell_the_agent_to_read_and_record(self):
        r = ca(self.api, "session-context", stdin="{}")
        self.assertIn("changes.md", r.stdout)
        self.assertIn("groundwork.py change", r.stdout)


class StandaloneChange(CheckBase):
    """A change that belongs to no RFC or feature, such as upgrading a package."""

    def setUp(self):
        super().setUp()
        (self.api / ".groundwork" / "active").unlink(missing_ok=True)
        self.log = self.api / "specs" / "changes.md"

    def prompt(self, text):
        return hook_ctx(self.api, text)

    def test_typed_change_opens_the_gate_and_a_pending_row(self):
        self.assertTrue(denied(self.api, self.api / "pyproject.toml")[0])
        ctx = self.prompt("/groundwork-specflow:change Upgrade requests to 2.32")
        self.assertIn("[groundwork change]", ctx)
        self.assertIn("--standalone", ctx)
        self.assertFalse(denied(self.api, self.api / "pyproject.toml")[0])
        row = self.log.read_text(encoding="utf-8").strip().splitlines()[-1]
        self.assertIn("| pending | Upgrade requests to 2.32 |", row)
        self.assertIn("| standalone |", row)
        r = ca(
            self.api,
            "change",
            "--standalone",
            "Bumped requests",
            "--files",
            "pyproject.toml",
            "uv.lock",
            "--via",
            "devin",
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        row = self.log.read_text(encoding="utf-8").strip().splitlines()[-1]
        self.assertNotIn("pending", row)
        self.assertIn("(via devin)", row)
        self.assertIn("Upgrade requests to 2.32; done: Bumped requests", row)
        self.assertIn("`pyproject.toml`, `uv.lock`", row)

    def test_an_empty_change_is_refused(self):
        self.assertIn("REFUSED", self.prompt("/groundwork-specflow:change"))
        self.assertTrue(denied(self.api, self.api / "pyproject.toml")[0])

    def test_standalone_without_a_pending_row_needs_a_requester(self):
        r = ca(self.api, "change", "--standalone", "Bumped requests")
        self.assertNotEqual(r.returncode, 0)
        r = ca(
            self.api,
            "change",
            "--standalone",
            "Bumped requests",
            "--requested-by",
            "Dev Two",
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("| Dev Two |", self.log.read_text(encoding="utf-8"))

    def test_the_agent_cannot_open_one_from_the_shell(self):
        o = hook(
            self.api,
            "gate-bash",
            {"command": f'python3 "{CA}" bypass --change Upgrade requests'},
        )
        self.assertEqual(o["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
