"""ADRs (after a built RFC, or retrospective for a choice found in existing code) and decision leads (§4, §5j)."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import CheckBase, check
from test_flow import ENV, Base, ca, fill, git_init

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))


def fm(path):
    import groundwork_core as C

    return C.split_fm(Path(path).read_text(encoding="utf-8"))[0]


class Adrs(CheckBase):
    def test_retrospective_adr_is_recorded_and_indexed(self):
        out = ca(
            self.ws,
            "new-adr",
            "integer-money",
            "--title",
            "Money is integers",
            "--retrospective",
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        p = self.ws / "DECISIONS" / "ADR-0001-integer-money.md"
        self.assertTrue(p.is_file())
        meta = fm(p)
        self.assertEqual(meta["status"], "recorded")
        self.assertEqual(meta["origin"], "baseline")
        self.assertEqual(meta["decided_at"], "unknown")
        self.assertEqual(meta["rationale_source"], "unknown")
        self.assertNotIn("rfc: RFC", p.read_text(encoding="utf-8"))
        self.assertIn(
            "| ADR-0001 | Money is integers | recorded |",
            (self.ws / "DECISIONS" / "README.md").read_text(encoding="utf-8"),
        )
        # unfinished: a warning only; a second ADR gets the next number
        _, ids, _ = check(self.ws)
        self.assertIn("GW018", ids)
        self.assertNotIn("GW017", ids)
        self.assertNotIn("GW019", ids)
        ca(
            self.ws,
            "new-adr",
            "vertex",
            "--retrospective",
            "--source",
            "docs/why-vertex.md",
        )
        p2 = self.ws / "DECISIONS" / "ADR-0002-vertex.md"
        self.assertEqual(fm(p2)["rationale_source"], "documented")
        self.assertEqual(fm(p2)["source"], "docs/why-vertex.md")
        # a retrospective ADR has no RFC; from a repo it lands in the workspace
        self.assertNotEqual(
            ca(
                self.ws, "new-adr", "x", "--retrospective", "--rfc", "RFC-0001"
            ).returncode,
            0,
        )
        ca(self.api, "new-adr", "from-repo", "--retrospective")
        self.assertTrue((self.ws / "DECISIONS" / "ADR-0003-from-repo.md").is_file())

    def test_rationale_source_must_be_labelled_honestly(self):
        ca(self.ws, "new-adr", "integer-money", "--retrospective")
        p = self.ws / "DECISIONS" / "ADR-0001-integer-money.md"
        fill(p)
        # `fill` left '**Source:** filled': not one of the three honest labels
        _, ids, items = check(self.ws)
        self.assertIn("GW019", ids)
        self.assertTrue(
            any("none of" in f["message"] for f in items if f["id"] == "GW019"), items
        )
        self.edit(
            p,
            lambda t: t.replace(
                "**Source:** filled", "**Source:** historical rationale unknown"
            ),
        )
        _, ids, items = check(self.ws, "--strict")
        self.assertEqual(ids & {"GW017", "GW018", "GW019"}, set(), items)
        # a label that contradicts the front matter, or a commit subject dressed up as a reason, is refused
        self.edit(
            p,
            lambda t: t.replace(
                "**Source:** historical rationale unknown",
                "**Source:** documented in docs/money.md",
            ),
        )
        _, ids, items = check(self.ws)
        self.assertTrue(
            any(
                "rationale_source is 'unknown'" in f["message"]
                for f in items
                if f["id"] == "GW019"
            ),
            items,
        )
        import groundwork_core as C

        p.write_text(
            C.set_fm(
                p.read_text(encoding="utf-8"),
                {"rationale_source": "documented", "source": ""},
            ),
            encoding="utf-8",
        )
        self.assertTrue(
            any("name the document" in f["message"] for f in check(self.ws)[2])
        )
        self.edit(
            p,
            lambda t: t.replace(
                "**Source:** documented in docs/money.md",
                "**Source:** because the team wanted it",
            ),
        )
        self.assertIn("GW019", check(self.ws)[1])
        self.edit(
            p,
            lambda t: t.replace(
                "**Source:** because the team wanted it",
                "**Source:** retrospective explanation by Lead Person, 2026-10-09",
            ),
        )
        p.write_text(
            C.set_fm(
                p.read_text(encoding="utf-8"), {"rationale_source": "retrospective"}
            ),
            encoding="utf-8",
        )
        self.assertNotIn("GW019", check(self.ws)[1])

    def test_metadata_rules_and_rfc_adr(self):
        out = ca(
            self.ws,
            "new-adr",
            "widgets-built",
            "--title",
            "Widgets built",
            "--rfc",
            "RFC-0001",
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        p = self.ws / "DECISIONS" / "ADR-0001-widgets-built.md"
        meta = fm(p)
        self.assertEqual(meta["status"], "proposed")
        self.assertEqual(meta["rfc"], "RFC-0001")
        self.assertNotIn("origin", meta)
        self.assertEqual(meta["source"], "DECISIONS/RFC-0001-widgets.md")
        import groundwork_core as C

        p.write_text(
            C.set_fm(
                p.read_text(encoding="utf-8"),
                {"status": "done", "rfc": "RFC-0099", "supersedes": "[ADR-0042]"},
            ),
            encoding="utf-8",
        )
        _, _, items = check(self.ws)
        msgs = [f["message"] for f in items if f["id"] == "GW017"]
        self.assertTrue(any("status" in m for m in msgs), msgs)
        self.assertTrue(any("RFC-0099" in m for m in msgs), msgs)
        self.assertTrue(any("ADR-0042" in m for m in msgs), msgs)
        self.assertNotEqual(
            ca(self.ws, "new-adr", "y", "--rfc", "RFC-0099").returncode, 0
        )
        # a hand-written ADR without front matter is left alone
        (self.ws / "DECISIONS" / "ADR-0007-old.md").write_text(
            "# Old decision\nfree text\n", encoding="utf-8"
        )
        self.assertFalse(any("ADR-0007" in f["path"] for f in check(self.ws)[2]))


class AdrHardening(CheckBase):
    """The gaps found in review: blank counts, label placement and format, blank or contradictory
    metadata, child-repo visibility, RFC claims, and prose mentions counted as index rows."""

    def test_blank_signoff_count_keeps_the_gate_closed(self):
        import groundwork_core as C
        from test_flow import denied

        code = self.api / "src" / "x.py"
        self.rfc.write_text(
            C.set_fm(self.rfc.read_text(encoding="utf-8"), {"signoffs_required": "2"}),
            encoding="utf-8",
        )
        self.assertTrue(denied(self.api, code)[0])
        self.rfc.write_text(
            C.set_fm(self.rfc.read_text(encoding="utf-8"), {"signoffs_required": ""}),
            encoding="utf-8",
        )
        d, why = denied(self.api, code)
        self.assertTrue(d, why)
        self.assertIn("in-review", why)
        self.assertNotEqual(
            ca(self.ws, "approve", "RFC-0001", "--as", "lead").returncode, 0
        )
        self.assertIn("GW010", check(self.ws)[1])
        # a contract with a blank count is a finding too
        ca(self.ws, "new-contract", "api-http", "--as-built")
        cp = self.ws / "CONTRACTS" / "api-http.md"
        cp.write_text(
            C.set_fm(cp.read_text(encoding="utf-8"), {"signoffs_required": ""}),
            encoding="utf-8",
        )
        self.assertTrue(
            any(
                f["id"] == "GW045" and "signoffs_required" in f["message"]
                for f in check(self.ws)[2]
            )
        )

    def adr(self):
        ca(self.ws, "new-adr", "integer-money", "--retrospective")
        p = self.ws / "DECISIONS" / "ADR-0001-integer-money.md"
        fill(p)
        self.edit(
            p,
            lambda t: t.replace(
                "**Source:** filled", "**Source:** historical rationale unknown"
            ),
        )
        self.assertNotIn("GW019", check(self.ws)[1])
        return p

    def test_label_must_open_section_3_and_be_complete(self):
        p = self.adr()
        # the label in §1 while §3 has none: refused
        self.edit(
            p,
            lambda t: t.replace(
                "**Source:** historical rationale unknown\n", ""
            ).replace(
                "## 1. Context\n",
                "## 1. Context\n**Source:** historical rationale unknown\n",
            ),
        )
        self.assertTrue(
            any(
                "must begin" in f["message"]
                for f in check(self.ws)[2]
                if f["id"] == "GW019"
            )
        )
        self.edit(
            p,
            lambda t: t.replace(
                "## 1. Context\n**Source:** historical rationale unknown\n",
                "## 1. Context\n",
            ),
        )
        # a label after other prose in §3: refused; first content line: accepted
        self.edit(
            p,
            lambda t: t.replace(
                "## 3. Rationale\n",
                "## 3. Rationale\nsome prose first\n**Source:** historical rationale unknown\n",
            ),
        )
        self.assertIn("GW019", check(self.ws)[1])
        self.edit(
            p,
            lambda t: t.replace(
                "## 3. Rationale\nsome prose first\n**Source:** historical rationale unknown\n",
                "## 3. Rationale\n**Source:** historical rationale unknown\n",
            ),
        )
        self.assertNotIn("GW019", check(self.ws)[1])
        # a retrospective explanation needs a person and a date
        import groundwork_core as C

        p.write_text(
            C.set_fm(
                p.read_text(encoding="utf-8"), {"rationale_source": "retrospective"}
            ),
            encoding="utf-8",
        )
        self.edit(
            p,
            lambda t: t.replace(
                "**Source:** historical rationale unknown",
                "**Source:** retrospective explanation by Alice",
            ),
        )
        self.assertTrue(
            any(
                "none of" in f["message"]
                for f in check(self.ws)[2]
                if f["id"] == "GW019"
            )
        )
        self.edit(p, lambda t: t.replace("by Alice", "by Alice, 2026-10-09"))
        self.assertNotIn("GW019", check(self.ws)[1])

    def test_blank_or_contradictory_metadata_is_reported(self):
        p = self.adr()
        import groundwork_core as C

        p.write_text(
            C.set_fm(
                p.read_text(encoding="utf-8"),
                {"id": "", "status": "", "rationale_source": ""},
            ),
            encoding="utf-8",
        )
        msgs = [f["message"] for f in check(self.ws)[2] if f["id"] == "GW017"]
        for field in ("id", "status", "rationale_source"):
            self.assertTrue(any(f"blank: {field}" in m for m in msgs), msgs)
        p.write_text(
            C.set_fm(
                p.read_text(encoding="utf-8"),
                {
                    "id": "ADR-0001",
                    "status": "recorded",
                    "rationale_source": "unknown",
                    "rfc": "RFC-0001",
                },
            ),
            encoding="utf-8",
        )
        self.assertTrue(
            any(
                "no RFC behind it" in m
                for m in [f["message"] for f in check(self.ws)[2] if f["id"] == "GW017"]
            )
        )
        p.write_text(
            C.set_fm(p.read_text(encoding="utf-8"), {"rfc": ""}), encoding="utf-8"
        )
        self.assertNotIn("GW017", check(self.ws)[1])

    def test_child_repo_sees_workspace_adr_findings(self):
        p = self.adr()
        self.edit(
            p,
            lambda t: t.replace(
                "**Source:** historical rationale unknown",
                "**Source:** because we felt like it",
            ),
        )
        self.assertIn("GW019", check(self.api)[1])

    def test_rfc_backed_adr_needs_an_approved_rfc_and_claims_no_date(self):
        ca(self.ws, "new-rfc", "later", "--title", "Later")
        out = ca(self.ws, "new-adr", "later-built", "--rfc", "RFC-0002")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("not approved", out.stderr)
        self.assertFalse(list((self.ws / "DECISIONS").glob("ADR-*")))
        out = ca(self.ws, "new-adr", "widgets-built", "--rfc", "RFC-0001")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(
            fm(self.ws / "DECISIONS" / "ADR-0001-widgets-built.md")["decided_at"],
            "unknown",
        )
        self.assertNotIn(
            "approved", out.stdout.split("\n")[0]
        )  # the path line makes no claim

    def test_creation_inserts_a_row_even_when_prose_mentions_the_id(self):
        idx = self.ws / "DECISIONS" / "README.md"
        idx.write_text(
            idx.read_text(encoding="utf-8") + "\nADR-0001 will be indexed later.\n",
            encoding="utf-8",
        )
        ca(self.ws, "new-adr", "integer-money", "--retrospective")
        self.assertIn(
            "| ADR-0001 | Integer Money | recorded |", idx.read_text(encoding="utf-8")
        )
        self.assertFalse(
            any("not listed" in f["message"] for f in check(self.ws)[2])
        )  # GW018 may still say "unfinished"; the index row is there

    def test_rationale_source_is_required(self):
        p = self.adr()
        import groundwork_baseline as BL

        p.write_text(
            BL._remove_fm_keys(p.read_text(encoding="utf-8"), {"rationale_source"}),
            encoding="utf-8",
        )
        self.assertTrue(
            any(
                f["id"] == "GW017" and "missing: rationale_source" in f["message"]
                for f in check(self.ws)[2]
            )
        )

    def test_index_needs_a_table_row_not_a_mention(self):
        p = self.adr()
        idx = self.ws / "DECISIONS" / "README.md"
        self.edit(
            idx,
            lambda t: (
                "\n".join(
                    ln for ln in t.splitlines() if not ln.startswith("| ADR-0001")
                )
                + "\n\nADR-0001 will be indexed later.\n"
            ),
        )
        self.assertIn("GW018", check(self.ws)[1])
        self.edit(
            idx,
            lambda t: (
                "\n".join(
                    ln for ln in t.splitlines() if not ln.startswith("| RFC-0001")
                )
                + "\nRFC-0001 is mentioned here.\n"
            ),
        )
        self.assertIn("GW014", check(self.ws)[1])
        del p


class DecisionLeads(Base):
    def test_leads_are_topics_with_their_source(self):
        r = self.root / "r"
        git_init(r)
        (r / "app").mkdir()
        (r / "app" / "config.py").write_text(
            "RERANK = False  # off by default because the offline benchmark found it n.s.\nX = 1\n",
            encoding="utf-8",
        )
        (r / "docs").mkdir()
        (r / "docs" / "RETRIEVAL_BENCHMARK_FINDINGS.md").write_text(
            "# Findings\n", encoding="utf-8"
        )
        (r / "docs" / "howto.md").write_text("# How to\n", encoding="utf-8")
        (r / "README.md").write_text("# r\n", encoding="utf-8")
        g = {**ENV, "GIT_COMMITTER_NAME": "Ann", "GIT_COMMITTER_EMAIL": "a@b.c"}
        subprocess.run(["git", "-C", str(r), "add", "-A"], env=g, check=True)
        subprocess.run(
            ["git", "-C", str(r), "commit", "-qm", "Move generation to Vertex"],
            env=g,
            check=True,
        )
        (r / "app" / "x.py").write_text("y = 2\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(r), "add", "-A"], env=g, check=True)
        subprocess.run(
            ["git", "-C", str(r), "commit", "-qm", "Fix typo"], env=g, check=True
        )
        out = ca(r, "init")
        d = json.loads(
            (r / ".groundwork" / "discovery.json").read_text(encoding="utf-8")
        )
        leads = d["decision_leads"]
        self.assertEqual(leads["docs"], ["docs/RETRIEVAL_BENCHMARK_FINDINGS.md"])
        self.assertEqual(leads["comments"][0]["file"], "app/config.py")
        self.assertIn("because", leads["comments"][0]["text"])
        self.assertEqual(
            [c["subject"] for c in leads["commits"]], ["Move generation to Vertex"]
        )
        self.assertIn("a reason needs a document or a person", out.stdout)


if __name__ == "__main__":
    unittest.main()
