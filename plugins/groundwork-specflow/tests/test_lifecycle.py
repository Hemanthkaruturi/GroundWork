"""Resume, feature relationships, and the bug lifecycle."""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import CheckBase, check  # noqa: E402
from test_flow import ca, denied, fill, git_init, hook  # noqa: E402


def board(cwd, *a):
    return json.loads(ca(cwd, "board", "--json", *a).stdout)


def by_ref(items, ref):
    return next(i for i in items if i["ref"] == ref)


def finish(fdir, ws, api, approve=True):
    for f in fdir.glob("*.md"):
        fill(f)
    if approve:
        ca(api, "approve", str(fdir / "spec.md"), "--as", "lead")


class Resume(CheckBase):
    """The fixture leaves: RFC-0001 approved, 001-widgets fully built-ready (nothing implemented)."""

    def test_board_shows_every_stage_across_the_workspace(self):
        ca(self.ws, "new-rfc", "drafty")                                   # RFC-0002: just started
        rfc3 = Path(ca(self.ws, "new-rfc", "approved-nospec").stdout.strip()); fill(rfc3)
        ca(self.ws, "approve", "RFC-0003", "--as", "lead")                  # approved, no spec anywhere
        ca(self.api, "new-feature", "half", "--rfc", "RFC-0001")           # spec scaffolded, nothing written
        items = board(self.ws)
        self.assertIn("drafting", by_ref(items, "RFC-0002")["state"])
        self.assertEqual(by_ref(items, "RFC-0003")["state"], "approved — no spec yet")
        self.assertEqual(by_ref(items, "RFC-0003")["skill"], "write-spec")
        half = by_ref(items, "api/002-half")
        self.assertIn("spec.md is draft", half["state"]); self.assertEqual(half["skill"], "write-spec")
        widgets = by_ref(items, "api/001-widgets")
        self.assertIn("building", widgets["state"])
        self.assertNotIn("RFC-0001", [i["ref"] for i in items])            # approved and has a spec: not itself in flight

    def test_session_context_lists_in_flight_and_next_step_says_resume(self):
        ca(self.api, "new-feature", "half", "--rfc", "RFC-0001")
        (self.api / ".groundwork" / "active").unlink()                    # a fresh session: nothing active
        ctx = hook(self.api, "session-context", {})["additionalContext"]
        self.assertIn("IN FLIGHT", ctx); self.assertIn("002-half", ctx)
        self.assertIn("resume skill", ctx)

    def test_interview_progress_survives_in_the_rfc_draft(self):
        rfc = Path(ca(self.ws, "new-rfc", "login").stdout.strip())
        rfc.write_text(rfc.read_text(encoding="utf-8").replace("| 1 | [TODO] | [TODO] |", "| 1 | Who logs in? | Buyers |\n| 2 | Which IdP? | Google |"), encoding="utf-8")
        w = by_ref(board(self.ws), "RFC-0002")
        self.assertIn("2 interview answer(s)", w["state"])

    def test_note_is_shown_on_resume(self):
        r = ca(self.api, "note", "stopped", "before", "the", "migration")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("stopped before the migration", by_ref(board(self.api), "001-widgets")["note"])
        self.assertIn("last note: ", hook(self.api, "session-context", {})["additionalContext"])

    def test_activate_switches_and_active_sorts_first(self):
        ca(self.api, "new-feature", "half", "--rfc", "RFC-0001")           # this one is active now
        items = board(self.api)
        self.assertTrue(items[0]["active"]); self.assertEqual(items[0]["ref"], "002-half")
        ca(self.api, "activate", "001-widgets")
        self.assertEqual(board(self.api)[0]["ref"], "001-widgets")

    def test_superseded_rfc_leaves_the_board(self):
        old = Path(ca(self.ws, "new-rfc", "old-way").stdout.strip()); fill(old)
        ca(self.ws, "approve", "RFC-0002", "--as", "lead")                 # approved, no spec: shows as in flight
        self.assertIn("RFC-0002", [i["ref"] for i in board(self.ws)])
        new = Path(ca(self.ws, "new-rfc", "new-way").stdout.strip()); fill(new)
        new.write_text(new.read_text(encoding="utf-8").replace("supersedes: []", "supersedes: [RFC-0002]"), encoding="utf-8")
        ca(self.ws, "approve", "RFC-0003", "--as", "lead")
        refs = [i["ref"] for i in board(self.ws)]
        self.assertNotIn("RFC-0002", refs)                                  # superseded: no longer waiting for a spec
        self.assertIn("RFC-0003", refs)
        self.assertIn("RFC-0002", [i["ref"] for i in board(self.ws, "--all")])


class Relations(CheckBase):
    def feature(self, slug, **rel):
        args = ["new-feature", slug, "--rfc", "RFC-0001"]
        for k, v in rel.items():
            args += ["--" + k.replace("_", "-"), v]
        self.assertEqual(ca(self.api, *args).returncode, 0)
        return self.api / "specs" / sorted(p.name for p in (self.api / "specs").iterdir())[-1]

    def build_ready(self, fdir):
        finish(fdir, self.ws, self.api)

    def code(self):
        return self.api / "src" / "x.py"

    def test_depends_on_blocks_code_until_dependency_is_implemented(self):
        f2 = self.feature("second", depends_on="001-widgets")
        self.build_ready(f2)
        d, why = denied(self.api, self.code())
        self.assertTrue(d); self.assertIn("waiting on 001-widgets", why); self.assertIn("not yet implemented", why)
        t = self.fdir / "tasks.md"
        t.write_text(re.sub(r"- \[ \]", "- [x]", t.read_text(encoding="utf-8")), encoding="utf-8")          # 001 implemented
        self.assertFalse(denied(self.api, self.code())[0])

    def test_builds_against_needs_only_approved_spec_and_finished_plan(self):
        f2 = self.feature("second", builds_against="001-widgets")
        self.build_ready(f2)
        self.assertFalse(denied(self.api, self.code())[0])                # 001 is approved with a finished plan
        self.edit(self.fdir / "spec.md", lambda t: t + "\nchange\n")      # stale approval on the base
        self.assertTrue(denied(self.api, self.code())[0])

    def test_cross_repo_dependency(self):
        git_init(self.ws / "web"); ca(self.ws / "web", "scaffold")
        web = self.ws / "web"
        for f in web.glob("*.md"):
            fill(f)
        ca(web, "confirm")
        ca(web, "new-feature", "ui", "--rfc", "RFC-0001", "--depends-on", "api/001-widgets")
        wf = web / "specs" / "001-ui"
        finish(wf, self.ws, web)
        d, why = denied(web, web / "src" / "ui.js")
        self.assertTrue(d); self.assertIn("api/001-widgets", why)
        t = self.fdir / "tasks.md"; t.write_text(re.sub(r"- \[ \]", "- [x]", t.read_text(encoding="utf-8")), encoding="utf-8")
        self.assertFalse(denied(web, web / "src" / "ui.js")[0])

    def test_deps_command_shows_relations_and_downstream(self):
        self.feature("second", extends="001-widgets", amends="001-widgets")
        out = ca(self.api, "deps", "001-widgets").stdout
        self.assertIn("002-second", out); self.assertIn("extends", out)
        self.assertIn("amends", ca(self.api, "deps", "002-second").stdout)
        self.feature("loner")
        self.assertIn("independent", ca(self.api, "deps", "003-loner").stdout)
        self.assertIn("nothing depends on it", ca(self.api, "deps", "003-loner").stdout)
        self.assertIn("RFC-0001", ca(self.api, "deps", "RFC-0001").stdout)
        self.assertIn("001-widgets", ca(self.api, "deps", "RFC-0001").stdout)

    def test_unresolvable_relation_and_cycle(self):
        self.feature("second", depends_on="009-nope")
        self.assertIn("GW070", check(self.ws)[1])
        # cycle 001 <-> 002
        self.edit(self.fdir / "spec.md", lambda t: t.replace("depends_on: []", "depends_on: [002-second]"))
        self.edit(self.api / "specs" / "002-second" / "spec.md", lambda t: t.replace("depends_on: [009-nope]", "depends_on: [001-widgets]"))
        self.assertIn("GW071", check(self.ws)[1])

    def test_amends_requires_changes_entry_in_the_base_spec(self):
        f2 = self.feature("second", amends="001-widgets")
        self.build_ready(f2)
        self.assertIn("GW072", check(self.ws)[1])
        base = self.fdir / "spec.md"
        base.write_text(base.read_text(encoding="utf-8").rstrip() + "\n\n## Changes\n- 2026-09-30: 002-second changes FR-1 (widgets now optional)\n", encoding="utf-8")
        ca(self.api, "approve", str(base), "--as", "lead")               # re-approval after the amendment
        self.assertNotIn("GW072", check(self.ws)[1])

    def test_concurrent_modification_of_one_base_is_flagged(self):
        self.feature("second", extends="001-widgets"); self.feature("third", extends="001-widgets")
        self.assertIn("GW073", check(self.ws)[1])

    def test_independent_features_have_no_findings(self):
        self.feature("indep")
        ids = check(self.ws)[1]
        self.assertFalse({"GW070", "GW071", "GW072", "GW073", "GW074"} & ids)

    def test_started_before_dependency_is_an_error(self):
        f2 = self.feature("second", depends_on="001-widgets")
        self.build_ready(f2)
        t = f2 / "tasks.md"; t.write_text(t.read_text(encoding="utf-8").replace("- [ ] **T001**", "- [x] **T001**"), encoding="utf-8")
        self.assertIn("GW074", check(self.ws)[1])

    def test_rfc_supersedes_must_exist(self):
        rfc = self.rfc
        rfc.write_text(rfc.read_text(encoding="utf-8").replace("supersedes: []", "supersedes: [RFC-0099]"), encoding="utf-8")
        self.assertIn("GW015", check(self.ws)[1])


class Bugs(CheckBase):
    def new_bug(self, slug="crash", **kw):
        p = Path(ca(self.api, "new-bug", slug, "--title", "It crashes").stdout.split("\n")[0])
        return p

    def diagnose(self, p, classification, **front):
        t = p.read_text(encoding="utf-8")
        t = t.replace("classification: unclassified", f"classification: {classification}")
        for k, v in front.items():
            t = re.sub(rf"^{k}:.*$", f"{k}: {v}", t, flags=re.M)
        t = t.replace("status: open", "status: diagnosed")
        t = re.sub(r"\[TODO[^\]]*\]", "done", t)
        p.write_text(t, encoding="utf-8")

    def code(self):
        return self.api / "src" / "fix.py"

    def test_bug_record_is_created_and_active_but_edits_stay_blocked_until_diagnosed(self):
        (self.api / ".groundwork" / "active").unlink()
        p = self.new_bug()
        self.assertTrue(p.exists() and p.parent.name == "bugs")
        d, why = denied(self.api, self.code())
        self.assertTrue(d); self.assertIn("bug", why)
        self.assertIn("bug", by_ref(board(self.api), "bugs/001-crash")["kind"])

    def test_code_bug_must_cite_real_approved_requirements(self):
        (self.api / ".groundwork" / "active").unlink()
        p = self.new_bug()
        self.diagnose(p, "code-bug")                                       # no violates yet
        self.assertTrue(denied(self.api, self.code())[0])
        self.diagnose(p, "code-bug", violates="[FR-1@009-nope]")           # unknown feature
        self.assertTrue(denied(self.api, self.code())[0])
        self.diagnose(p, "code-bug", violates="[FR-99@001-widgets]")       # no such requirement
        self.assertIn("no such requirement", denied(self.api, self.code())[1])
        self.diagnose(p, "code-bug", violates="[FR-1@001-widgets, AC-1@001-widgets]", regression_test="tests/test_fix.py")
        self.assertFalse(denied(self.api, self.code())[0])                 # several requirements, valid

    def test_code_bug_against_an_unapproved_or_stale_spec_is_refused(self):
        (self.api / ".groundwork" / "active").unlink()
        p = self.new_bug()
        self.diagnose(p, "code-bug", violates="[FR-1@001-widgets]", regression_test="tests/t.py")
        self.assertFalse(denied(self.api, self.code())[0])
        self.edit(self.fdir / "spec.md", lambda t: t + "\nedited\n")       # spec no longer approved
        d, why = denied(self.api, self.code())
        self.assertTrue(d); self.assertIn("not approved", why)

    def test_spec_gap_requires_amended_and_reapproved_spec(self):
        (self.api / ".groundwork" / "active").unlink()
        p = self.new_bug("gap")
        bid = p.stem
        self.diagnose(p, "spec-gap", amends="[001-widgets]", regression_test="tests/t.py")
        d, why = denied(self.api, self.code())
        self.assertTrue(d); self.assertIn("Changes", why)
        base = self.fdir / "spec.md"
        base.write_text(base.read_text(encoding="utf-8").rstrip() + f"\n\n## Changes\n- 2026-09-30: {bid} — FR-1 now covers empty input\n", encoding="utf-8")
        d, why = denied(self.api, self.code())
        self.assertTrue(d); self.assertIn("re-approve", why)               # amended but the human hasn't re-approved
        ca(self.api, "approve", str(base), "--as", "lead")
        self.assertFalse(denied(self.api, self.code())[0])

    def test_design_flaw_requires_an_approved_rfc(self):
        (self.api / ".groundwork" / "active").unlink()
        p = self.new_bug("flaw")
        rfc2 = Path(ca(self.ws, "new-rfc", "rethink").stdout.strip())
        self.diagnose(p, "design-flaw", rfc="RFC-0002", regression_test="tests/t.py")
        self.assertTrue(denied(self.api, self.code())[0])
        fill(rfc2); ca(self.ws, "approve", "RFC-0002", "--as", "lead")
        self.assertFalse(denied(self.api, self.code())[0])

    def test_unclassified_or_missing_regression_test_blocks(self):
        (self.api / ".groundwork" / "active").unlink()
        p = self.new_bug()
        self.diagnose(p, "code-bug", violates="[FR-1@001-widgets]")        # no regression_test named
        self.assertIn("regression", denied(self.api, self.code())[1])

    def test_fixed_needs_the_regression_test_to_exist_and_verification(self):
        p = self.new_bug()
        self.diagnose(p, "code-bug", violates="[FR-1@001-widgets]", regression_test="tests/test_fix.py")
        p.write_text(p.read_text(encoding="utf-8").replace("status: diagnosed", "status: fixed"), encoding="utf-8")
        self.assertIn("GW063", check(self.ws)[1])                          # test file missing and §7 still empty
        (self.api / "tests").mkdir(); (self.api / "tests" / "test_fix.py").write_text("", encoding="utf-8")
        self.assertIn("GW063", check(self.ws)[1])                          # test exists, §7 still empty
        p.write_text(re.sub(r"## 7\. Verification\n.*", "## 7. Verification\nVerified by hand; suite green; docs unchanged.\n",
                            p.read_text(encoding="utf-8"), flags=re.S), encoding="utf-8")
        self.assertNotIn("GW063", check(self.ws)[1])

    def test_open_bug_is_not_an_error_but_diagnosed_with_gaps_is(self):
        p = self.new_bug()
        self.assertEqual(check(self.ws)[0], 0)
        self.assertIn("GW064", check(self.ws)[1])
        p.write_text(p.read_text(encoding="utf-8").replace("status: open", "status: diagnosed"), encoding="utf-8")
        code, ids, _ = check(self.ws)
        self.assertIn("GW065", ids); self.assertEqual(code, 1)

    def test_closed_bug_leaves_the_board(self):
        p = self.new_bug()
        self.assertIn("bugs/001-crash", [i["ref"] for i in board(self.api)])
        p.write_text(p.read_text(encoding="utf-8").replace("status: open", "status: closed"), encoding="utf-8")
        self.assertNotIn("bugs/001-crash", [i["ref"] for i in board(self.api)])


if __name__ == "__main__":
    unittest.main()
