"""Ownership: who requested / owns / implemented / deployed / supports — and whom to contact."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import CheckBase, check  # noqa: E402
from test_flow import ca, hook  # noqa: E402


def who(cwd, *a):
    r = ca(cwd, "who", *a)
    return r.stdout + r.stderr


class Ownership(CheckBase):
    def test_who_shows_the_whole_chain_with_contacts(self):
        ca(self.api, "record", "implemented", "--ref", "001-widgets", "--by", "dev2@example.com", "--via", "claude-code")
        ca(self.api, "record", "support", "--ref", "001-widgets", "--who", "Dev Two")
        ca(self.api, "record", "deployed", "--ref", "001-widgets", "--env", "prod", "--version", "1.4.0", "--by", "lead@example.com")
        out = who(self.api, "001-widgets")
        self.assertIn("Requested by", out); self.assertIn("Lead Person (Tech lead) — lead@example.com", out)
        self.assertRegex(out, r"Implemented by\s+Dev Two \(Backend dev\) — dev2@example.com")
        self.assertRegex(out, r"Support\s+Dev Two")
        self.assertIn("prod", out); self.assertIn("1.4.0", out)
        self.assertIn("Approved", out); self.assertIn("lead", out)
        self.assertIn("via claude-code", out)

    def test_latest_deployment_per_environment(self):
        for env, ver in (("staging", "1.3"), ("prod", "1.3"), ("prod", "1.4")):
            ca(self.api, "record", "deployed", "--ref", "001-widgets", "--env", env, "--version", ver, "--by", "lead@example.com")
        out = who(self.api, "001-widgets")
        self.assertIn("Deployed → prod", out); self.assertIn("1.4", out.split("Deployed → prod")[1].splitlines()[0])
        self.assertIn("Deployed → staging", out)

    def test_deployed_needs_env_and_version(self):
        r = ca(self.api, "record", "deployed", "--ref", "001-widgets")
        self.assertNotEqual(r.returncode, 0); self.assertIn("--env", r.stderr)

    def test_owners_of_related_features_are_shown(self):
        ca(self.api, "new-feature", "second", "--rfc", "RFC-0001", "--depends-on", "001-widgets")
        ca(self.api, "record", "owner", "--ref", "002-second", "--who", "Dev Two")
        out = who(self.api, "001-widgets")
        self.assertIn("affects api/002-second", out); self.assertIn("Dev Two (Backend dev)", out)
        out2 = who(self.api, "002-second")
        self.assertIn("depends on api/001-widgets", out2); self.assertIn("Lead Person", out2)

    def test_creation_sets_owner_to_the_git_identity_and_ledger(self):
        ca(self.api, "new-feature", "third", "--rfc", "RFC-0001")
        meta = (self.api / "specs" / "002-third" / "spec.md").read_text(encoding="utf-8")
        self.assertNotIn("owner:\n", meta)
        self.assertIn("requested_by: Lead Person", meta)                     # inherited from the RFC
        ledger = (self.api / ".groundwork" / "ledger.jsonl").read_text(encoding="utf-8")
        self.assertIn('"event": "created"', ledger)

    def test_person_reverse_lookup_and_team_map(self):
        ca(self.api, "record", "implemented", "--ref", "001-widgets", "--by", "dev2@example.com")
        out = who(self.ws, "--person", "dev2@example.com")
        self.assertIn("Dev Two", out); self.assertIn("implemented_by", out)
        lead = who(self.ws, "--person", "Lead")
        self.assertIn("RFC-0001", lead); self.assertIn("owner", lead)
        table = who(self.ws, "--all")
        self.assertIn("001-widgets", table); self.assertIn("Lead Person", table)

    def test_bug_roles(self):
        (self.api / ".groundwork" / "active").unlink()
        ca(self.api, "new-bug", "crash", "--reported-by", "Lead Person")
        ca(self.api, "record", "fixed", "--ref", "bugs/001-crash", "--by", "dev2@example.com")
        out = who(self.api, "bugs/001-crash")
        self.assertIn("Reported by", out); self.assertIn("Lead Person", out); self.assertIn("Fixed by", out); self.assertIn("Dev Two", out)

    def test_handover_changes_the_owner_and_keeps_history(self):
        ca(self.api, "record", "handover", "--ref", "001-widgets", "--who", "Dev Two", "--by", "lead@example.com")
        out = who(self.api, "001-widgets")
        self.assertRegex(out, r"Owner\s+Dev Two")
        self.assertIn("handover", out)

    def test_session_context_says_who_you_are(self):
        ctx = hook(self.api, "session-context", {})["additionalContext"]
        self.assertIn("You are working on behalf of", ctx)

    def test_unknown_reference(self):
        self.assertIn("No feature", who(self.api, "999-nope"))


class OwnershipChecks(CheckBase):
    def test_conforming_fixture_is_clean_but_finished_work_needs_implementer_and_support(self):
        self.assertEqual(check(self.ws, "--strict")[0], 0)
        t = self.fdir / "tasks.md"
        t.write_text(t.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        ids = check(self.ws)[1]
        self.assertTrue({"GW082", "GW083"} <= ids)
        ca(self.api, "record", "implemented", "--ref", "001-widgets", "--by", "dev2@example.com")
        ca(self.api, "record", "support", "--ref", "001-widgets", "--who", "Dev Two")
        self.assertFalse({"GW082", "GW083"} & check(self.ws)[1])

    def test_approved_without_requester_or_owner(self):
        self.edit(self.fdir / "spec.md", lambda t: t.replace("requested_by: Lead Person\n", "requested_by:\n"))
        self.assertIn("GW080", check(self.ws)[1])

    def test_unknown_person_is_flagged(self):
        ca(self.api, "record", "support", "--ref", "001-widgets", "--who", "Mystery Guest")
        self.assertIn("GW081", check(self.ws)[1])

    def test_role_changes_do_not_invalidate_approval(self):
        ca(self.api, "record", "owner", "--ref", "001-widgets", "--who", "Dev Two")
        self.assertIn("approved", who(self.api, "001-widgets").split("Approved")[1].splitlines()[0])

    def test_doctor_flags_missing_people_table(self):
        pm = self.ws / "PROJECT.md"
        pm.write_text(pm.read_text(encoding="utf-8").replace("| Lead Person | Tech lead | everything | lead@example.com |\n| Dev Two | Backend dev | api | dev2@example.com |", ""), encoding="utf-8")
        d = json.loads(ca(self.ws, "doctor", "--json").stdout)
        self.assertTrue(any(i["area"] == "People" and i["status"] == "warn" for i in d["items"]))


if __name__ == "__main__":
    unittest.main()
