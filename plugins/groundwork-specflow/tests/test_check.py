"""`groundwork check`: a conforming project is clean; each rule fires on its own violation."""

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_flow import Base, ca, fill, git_init


def check(cwd, *extra):
    r = ca(cwd, "check", "--json", *extra)
    return (
        r.returncode,
        {f["id"] for f in json.loads(r.stdout)["findings"]},
        json.loads(r.stdout)["findings"],
    )


class CheckBase(Base):
    """A workspace with one repo and one fully written, fully approved feature."""

    def setUp(self):
        super().setUp()
        self.ws, self.api = self.root / "ws", self.root / "ws" / "api"
        git_init(self.api)
        (self.ws / "PROJECT.md").write_text(
            "# marker", encoding="utf-8"
        )  # makes ws a workspace for the repo scaffold
        ca(self.api, "scaffold")
        (self.ws / "PROJECT.md").unlink()
        ca(self.ws, "scaffold")
        for d in (self.ws, self.api):
            for f in d.glob("*.md"):
                fill(f)
        created = ca(self.ws, "new-rfc", "widgets")
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        self.rfc = Path(created.stdout.strip())
        fill(self.rfc)
        (self.ws / "DECISIONS" / "README.md").write_text(
            "| RFC-0001 | Widgets | approved | |\n", encoding="utf-8"
        )
        ca(self.api, "new-feature", "widgets", "--rfc", "RFC-0001")
        self.fdir = self.api / "specs" / "001-widgets"
        # people: a real directory, and named requester/owner (owner defaults to the git identity, which isn't listed)
        pm = self.ws / "PROJECT.md"
        pm.write_text(
            pm.read_text(encoding="utf-8").replace(
                "| filled | filled | filled | filled |",
                "| Lead Person | Tech lead | everything | lead@example.com |\n| Dev Two | Backend dev | api | dev2@example.com |",
            ),
            encoding="utf-8",
        )
        for ref in ("RFC-0001", "001-widgets"):
            cwd = self.ws if ref.startswith("RFC") else self.api
            ca(cwd, "record", "requested", "--ref", ref, "--who", "Lead Person")
            ca(cwd, "record", "owner", "--ref", ref, "--who", "Lead Person")
        for f in self.fdir.glob("*.md"):
            fill(f)
        ca(self.ws, "approve", "RFC-0001", "--as", "lead")
        ca(self.api, "approve", str(self.fdir / "spec.md"), "--as", "lead")
        assert (
            ca(self.api, "plan-sync").returncode == 0
        )  # plan/tasks/evals pinned to the approved spec
        for cwd in (self.ws, self.api):
            confirmed = ca(cwd, "confirm")
            self.assertEqual(
                confirmed.returncode, 0, confirmed.stdout + confirmed.stderr
            )

    def edit(self, path, fn):
        p = Path(path)
        p.write_text(fn(p.read_text(encoding="utf-8")), encoding="utf-8")

    def assertFires(self, rule, *extra):
        code, ids, _ = check(self.ws, *extra)
        self.assertIn(rule, ids)
        return code


class Conformance(CheckBase):
    def test_conforming_project_is_clean(self):
        code, ids, items = check(self.ws, "--strict")
        self.assertEqual((code, ids), (0, set()), items)

    def test_scaffold_is_warnings_only(self):
        git_init(self.root / "fresh")
        ca(self.root / "fresh", "scaffold")
        code, ids, _ = check(self.root / "fresh")
        self.assertEqual((code, ids), (0, {"GW002"}))
        self.assertEqual(check(self.root / "fresh", "--strict")[0], 1)

    def test_check_from_repo_level_works_too(self):
        self.assertEqual(check(self.api)[0], 0)


class Rules(CheckBase):
    def test_gw001_missing_foundation(self):
        (self.ws / "CONSTITUTION.md").unlink()
        self.assertEqual(self.assertFires("GW001"), 1)

    def test_gw003_missing_section(self):
        self.edit(
            self.ws / "PROJECT.md",
            lambda t: t.replace("## Who works on what", "## Team"),
        )
        self.assertFires("GW003")

    def test_gw005_major_version_mismatch(self):
        (self.api / ".groundwork" / "config.json").write_text(
            '{"standard": "9.0"}', encoding="utf-8"
        )
        self.assertFires("GW005")

    def test_gw010_rfc_frontmatter(self):
        self.edit(self.rfc, lambda t: t.replace("classification: internal\n", ""))
        self.assertFires("GW010")

    def test_gw011_rfc_section_missing_or_misordered(self):
        self.edit(
            self.rfc,
            lambda t: t.replace("## 5. Alternatives considered", "## 5. Thoughts"),
        )
        self.assertFires("GW011")

    def test_gw012_api_rfc_needs_contract_and_two_signoffs(self):
        self.edit(
            self.rfc,
            lambda t: t.replace("classification: internal", "classification: api"),
        )
        _, ids, _items = check(self.ws)
        self.assertIn("GW012", ids)

    def test_gw013_forged_or_stale_rfc_approval(self):
        self.edit(self.rfc, lambda t: t + "\nA sneaky late change.\n")
        self.assertFires("GW013")

    def test_gw014_rfc_not_indexed(self):
        (self.ws / "DECISIONS" / "README.md").write_text("empty\n", encoding="utf-8")
        self.assertFires("GW014")

    def test_gw020_feature_shape(self):
        (self.fdir / "evals.md").unlink()
        self.assertFires("GW020")

    def test_gw021_spec_cites_missing_rfc(self):
        self.edit(
            self.fdir / "spec.md", lambda t: t.replace("rfc: RFC-0001", "rfc: RFC-0042")
        )
        self.assertFires("GW021")

    def test_gw022_spec_section(self):
        self.edit(
            self.fdir / "spec.md",
            lambda t: t.replace("## 8. Manual test", "## 8. How to try"),
        )
        self.assertFires("GW022")

    def test_gw023_ac_must_cite_a_requirement(self):
        self.edit(self.fdir / "spec.md", lambda t: t.replace("(covers FR-1)", ""))
        self.assertFires("GW023")

    def test_gw024_empty_manual_test(self):
        self.edit(
            self.fdir / "spec.md",
            lambda t: re.sub(
                r"(## 8\. Manual test\n).*?(\n## 9)", r"\1\2", t, flags=re.DOTALL
            ),
        )
        self.assertFires("GW024")

    def test_gw026_spec_edited_after_approval(self):
        self.edit(self.fdir / "spec.md", lambda t: t + "\nnew rule\n")
        self.assertFires("GW026")

    def test_gw030_plan_section(self):
        self.edit(
            self.fdir / "plan.md",
            lambda t: t.replace("## 6. Test strategy", "## 6. Tests"),
        )
        self.assertFires("GW030")

    def test_gw031_task_needs_fields_and_known_refs(self):
        self.edit(
            self.fdir / "tasks.md",
            lambda t: t.replace("**Covers:** FR-1", "**Covers:** FR-9"),
        )
        self.assertFires("GW031")

    def test_gw032_fr_without_task(self):
        self.edit(
            self.fdir / "spec.md",
            lambda t: t.replace("## 5.", "- **FR-2**: another must.\n\n## 5.", 1),
        )
        self.assertFires("GW032")

    def test_gw092_spec_repeats_rfc_sentence(self):
        need = "A researcher opens the page, types a question, and presses run before any field is suggested."
        self.edit(
            self.rfc,
            lambda t: t.replace(
                "## 3. Interview record", need + "\n\n## 3. Interview record"
            ),
        )
        ca(self.ws, "approve", "RFC-0001", "--as", "lead")
        self.assertNotIn("GW092", check(self.ws)[1])
        self.edit(
            self.fdir / "spec.md",
            lambda t: t.replace(
                "## 2. Users and context",
                need + " (RFC-0001 §2)\n\n## 2. Users and context",
            ),
        )
        _, ids, items = check(self.ws)
        self.assertIn("GW092", ids)
        self.assertTrue(
            any(
                f["id"] == "GW092"
                and f["path"].endswith("spec.md")
                and "RFC-0001" in f["message"]
                for f in items
            )
        )
        # a pointer is not a copy
        self.edit(
            self.fdir / "spec.md",
            lambda t: t.replace(need + " (RFC-0001 §2)", "As RFC-0001 §2."),
        )
        self.assertNotIn("GW092", check(self.ws)[1])

    def test_gw092_plan_repeats_spec_and_adr_repeats_rfc(self):
        rule = "The server must refuse any upload larger than one megabyte with a clear message."
        self.edit(
            self.fdir / "spec.md", lambda t: t.replace("## 5.", rule + "\n\n## 5.", 1)
        )
        self.edit(
            self.fdir / "plan.md", lambda t: t.replace("## 2.", rule + "\n\n## 2.", 1)
        )
        _, _, items = check(self.ws)
        self.assertTrue(
            any(f["id"] == "GW092" and f["path"].endswith("plan.md") for f in items)
        )
        why = "We chose a styled tooltip because the native one is slow, unstyled and absent on touch."
        self.edit(self.rfc, lambda t: t.replace("## 6.", why + "\n\n## 6.", 1))
        ca(self.ws, "approve", "RFC-0001", "--as", "lead")
        made = ca(
            self.ws, "new-adr", "tooltip", "--title", "Tooltip", "--rfc", "RFC-0001"
        )
        self.assertEqual(made.returncode, 0, made.stdout + made.stderr)
        adr = Path(made.stdout.strip().splitlines()[0])
        fill(adr)
        self.edit(adr, lambda t: t.replace("## 4.", why + "\n\n## 4.", 1))
        _, _, items = check(self.ws)
        self.assertTrue(
            any(f["id"] == "GW092" and f["path"].endswith(adr.name) for f in items),
            items,
        )

    def test_gw033_ac_without_eval(self):
        self.edit(self.fdir / "evals.md", lambda t: t.replace("AC-1", "AC-x"))
        self.assertFires("GW033")

    def test_gw034_work_before_approval(self):
        ca(self.api, "new-feature", "second", "--rfc", "RFC-0001")
        f2 = self.api / "specs" / "002-second"
        self.edit(
            f2 / "tasks.md", lambda t: t.replace("- [ ] **T001**", "- [x] **T001**")
        )
        self.assertFires("GW034")

    def test_gw040_dangling_approval_record(self):
        (self.rfc).rename(self.ws / "DECISIONS" / "moved.md")
        self.assertFires("GW040")


if __name__ == "__main__":
    unittest.main()
