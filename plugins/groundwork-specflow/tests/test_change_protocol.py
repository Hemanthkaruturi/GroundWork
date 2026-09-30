"""Discoveries flow upstream only through an explicit, logged, re-approved amendment; downstream is then re-verified."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import CheckBase, check  # noqa: E402
from test_flow import ca, denied  # noqa: E402


class ChangeProtocol(CheckBase):
    def code(self):
        return self.api / "src" / "x.py"

    def amend_spec(self, note=None, text="\nFR-1 now means exact, unrounded.\n"):
        p = self.fdir / "spec.md"
        body = p.read_text(encoding="utf-8") + text
        if note:
            if not re.search(r"^## Changes\b", body, re.M):
                body = body.rstrip() + "\n\n## Changes\n"
            body = body.rstrip() + f"\n- 2026-09-30: {note}\n"
        p.write_text(body, encoding="utf-8")
        return p

    def test_first_approval_needs_no_changelog(self):
        self.assertFalse(re.search(r"^## Changes\b", (self.fdir / "spec.md").read_text(encoding="utf-8"), re.M))
        self.assertFalse(denied(self.api, self.code())[0])

    def test_reapproval_without_explanation_is_refused(self):
        p = self.amend_spec()
        r = ca(self.api, "approve", str(p), "--as", "lead")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("## Changes", r.stderr + r.stdout)
        self.assertIn("what changed and why", r.stderr + r.stdout)

    def test_reapproval_with_explanation_is_accepted_and_each_change_needs_its_own_line(self):
        p = self.amend_spec("FR-1 means the exact, unrounded payment (found while planning; user chose this reading)")
        self.assertEqual(ca(self.api, "approve", str(p), "--as", "lead").returncode, 0)
        p.write_text(p.read_text(encoding="utf-8") + "\nAnother tweak.\n", encoding="utf-8")                       # changed again, no new line
        self.assertNotEqual(ca(self.api, "approve", str(p), "--as", "lead").returncode, 0)
        p.write_text(p.read_text(encoding="utf-8").rstrip() + "\n- 2026-10-01: clarified the empty-result case\n", encoding="utf-8")
        self.assertEqual(ca(self.api, "approve", str(p), "--as", "lead").returncode, 0)

    def test_after_the_spec_changes_downstream_must_be_reverified_before_code(self):
        self.assertFalse(denied(self.api, self.code())[0])
        p = self.amend_spec("FR-1 reworded (found while planning)")
        ca(self.api, "approve", str(p), "--as", "lead")                           # human re-approved
        d, why = denied(self.api, self.code())
        self.assertTrue(d)
        self.assertIn("earlier version of the spec", why); self.assertIn("plan-sync", why)
        self.assertEqual(ca(self.api, "plan-sync").returncode, 0)
        self.assertFalse(denied(self.api, self.code())[0])

    def test_check_reports_pinned_to_old_spec_as_error_and_unpinned_as_warning(self):
        p = self.amend_spec("reworded")
        ca(self.api, "approve", str(p), "--as", "lead")
        code, ids, _ = check(self.ws)
        self.assertIn("GW037", ids); self.assertEqual(code, 1)
        ca(self.api, "plan-sync")
        self.assertNotIn("GW037", check(self.ws)[1])
        pl = self.fdir / "plan.md"
        pl.write_text(re.sub(r"^spec_version:.*$", "spec_version:", pl.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")      # unpin it
        self.assertIn("GW036", check(self.ws)[1])

    def test_plan_sync_refuses_an_unapproved_spec(self):
        self.amend_spec("reworded")                                              # edited, not re-approved
        r = ca(self.api, "plan-sync")
        self.assertNotEqual(r.returncode, 0); self.assertIn("APPROVED", r.stderr + r.stdout)

    def test_status_shows_the_sync_step(self):
        p = self.amend_spec("reworded"); ca(self.api, "approve", str(p), "--as", "lead")
        self.assertIn("earlier version of the spec", ca(self.api, "status").stdout)


if __name__ == "__main__":
    unittest.main()
