"""Freshness: documents must notice when reality moves, at repo level and — crucially — workspace level."""

import json
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import CheckBase, check
from test_flow import ca, fill, git_init, hook


def fresh(cwd):
    r = ca(cwd, "fresh", "--json")
    return {d["doc"]: d for d in json.loads(r.stdout)}


class Freshness(CheckBase):
    def test_confirmed_project_is_fresh(self):
        for cwd in (self.ws, self.api):
            self.assertTrue(
                all(d["status"] == "fresh" for d in fresh(cwd).values()), fresh(cwd)
            )
        self.assertEqual(check(self.ws, "--strict")[0], 0)

    def test_repo_change_makes_repo_architecture_stale_until_confirmed(self):
        (self.api / "package.json").write_text('{"name":"api"}', encoding="utf-8")
        (self.api / "billing").mkdir()
        f = fresh(self.api)["ARCHITECTURE.md"]
        self.assertEqual(f["status"], "stale")
        self.assertTrue(any("package.json" in r for r in f["reasons"]), f)
        self.assertTrue(any("billing" in r for r in f["reasons"]), f)
        code, ids, _ = check(self.api)
        self.assertIn("GW050", ids)
        self.assertEqual(code, 0)  # warning...
        self.assertEqual(check(self.api, "--strict")[0], 1)  # ...that CI can make fatal
        # AGENTS.md documents commands: a manifest change touches it too
        self.assertEqual(fresh(self.api)["AGENTS.md"]["status"], "stale")
        self.assertEqual(ca(self.api, "confirm").returncode, 0)
        self.assertTrue(all(d["status"] == "fresh" for d in fresh(self.api).values()))

    def test_groundwork_own_folders_do_not_make_architecture_stale(self):
        (self.api / "bugs").mkdir()
        (self.api / "bugs" / "x.md").write_text("x", encoding="utf-8")
        ca(
            self.api, "new-feature", "another", "--rfc", "RFC-0001"
        )  # creates specs/002-...
        f = fresh(self.api)["ARCHITECTURE.md"]
        self.assertFalse(any("toplevel" in r for r in f["reasons"]), f)

    def test_old_baselines_that_listed_specs_are_not_flagged(self):
        fp = self.api / ".groundwork" / "freshness.json"
        data = json.loads(fp.read_text(encoding="utf-8"))
        data["ARCHITECTURE.md"]["snapshot"]["toplevel"] = sorted(
            data["ARCHITECTURE.md"]["snapshot"]["toplevel"] + ["specs"]
        )
        fp.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(fresh(self.api)["ARCHITECTURE.md"]["status"], "fresh")

    def test_teammate_changes_repo_docs_workspace_notices_without_any_agent(self):
        # someone edits the repo's architecture by hand and commits; the plugin never ran
        self.edit(
            self.api / "ARCHITECTURE.md",
            lambda t: t + "\nWe now use a message queue.\n",
        )
        ws = fresh(self.ws)["ARCHITECTURE.md"]
        self.assertEqual(ws["status"], "stale")
        self.assertTrue(any("repo_arch changed: api" in r for r in ws["reasons"]), ws)
        _, ids, _items = check(self.ws)
        self.assertIn("GW050", ids)

    def test_new_repo_makes_workspace_project_and_architecture_stale(self):
        git_init(self.ws / "web")
        f = fresh(self.ws)
        for doc in ("PROJECT.md", "ARCHITECTURE.md", "AGENTS.md"):
            self.assertEqual(f[doc]["status"], "stale", doc)
            self.assertTrue(
                any("repos added: web" in r for r in f[doc]["reasons"]), f[doc]
            )

    def test_repo_session_sees_workspace_staleness_in_context(self):
        git_init(self.ws / "web")
        o = hook(self.api, "session-context", {})["additionalContext"]
        self.assertIn("DOCS MAY BE STALE", o)
        self.assertIn("workspace/ARCHITECTURE.md", o)
        r = hook(self.api, "prompt-reminder", {})["additionalContext"]
        self.assertIn("may be stale", r)

    def test_new_approved_rfc_makes_workspace_architecture_stale(self):
        rfc2 = Path(ca(self.ws, "new-rfc", "queue").stdout.strip())
        fill(rfc2)
        ca(self.ws, "approve", "RFC-0002", "--as", "lead")
        f = fresh(self.ws)["ARCHITECTURE.md"]
        self.assertTrue(any("rfcs added: RFC-0002" in r for r in f["reasons"]), f)

    def test_age_makes_any_document_stale(self):
        p = self.ws / ".groundwork" / "freshness.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["PROJECT.md"]["epoch"] = int(time.time()) - 200 * 86400
        p.write_text(json.dumps(data), encoding="utf-8")
        f = fresh(self.ws)["PROJECT.md"]
        self.assertEqual(f["status"], "stale")
        self.assertTrue(any("not reviewed for" in r for r in f["reasons"]))
        (self.ws / ".groundwork" / "config.json").write_text(
            json.dumps({"level": "workspace", "freshness_days": 400}), encoding="utf-8"
        )
        self.assertEqual(fresh(self.ws)["PROJECT.md"]["status"], "fresh")

    def test_finished_but_never_confirmed_is_flagged(self):
        (self.api / ".groundwork" / "freshness.json").unlink()
        self.assertEqual(fresh(self.api)["ARCHITECTURE.md"]["status"], "unconfirmed")
        self.assertIn("GW051", check(self.api)[1])

    def test_cannot_confirm_an_unfinished_document(self):
        self.edit(
            self.api / "ARCHITECTURE.md",
            lambda t: t + "\n[NEEDS CLARIFICATION: where does it deploy?]\n",
        )
        r = ca(self.api, "confirm", "ARCHITECTURE.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("markers", r.stderr + r.stdout)

    def test_edit_without_drift_needs_no_warning(self):
        self.edit(self.api / "AGENTS.md", lambda t: t + "\nA clarifying note.\n")
        self.assertEqual(fresh(self.api)["AGENTS.md"]["status"], "edited")
        self.assertNotIn("GW050", check(self.api)[1])


if __name__ == "__main__":
    unittest.main()
