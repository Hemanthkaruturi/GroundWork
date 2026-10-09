"""Baselines, imported legacy specs and the capability index (STANDARD.md §5j)."""

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import CheckBase, check
from test_flow import Base, ca, denied, fill, git_init

LEGACY_SPEC = """# Spec: Clients and Tenants

**ID:** 001-clients-and-tenants
**Status:** {status}
**Owner:** —
**Created:** 2026-08-12

## 1. Problem

The gateway has nobody to charge.

## 2. Users and context

- A calling application.

## 3. User stories

- **US-1**: As a client, I want a key, so that I can call.

## 4. Functional requirements

- **FR-1**: A client authenticates with a key.

## 5. Non-functional requirements

- **NFR-1**: Verification is one indexed lookup.

## 6. Acceptance criteria

- **AC-1**: Given a valid key, when a call arrives, then it is attributed to the client. (covers FR-1)

## 7. Out of scope

Credits.

## 8. Resolved decisions

None.

## 9. Open questions

None.

## 10. Constitution check

Complies.
"""

LEGACY_TASKS = """# Tasks

- [x] **T001** — Add typer.
  - **Files:** pyproject.toml
  - **Done when:** installed
  - **Covers:** FR-1
- [ ] **T002** — Later.
  - **Files:** x
  - **Done when:** y
  - **Covers:** FR-1
"""

BASELINE_TAIL = """## Intent and rationale
| # | Question | Answer | Source / person | Effect |
| --- | --- | --- | --- | --- |
| 1 | Deliberate? | Yes | Lead Person | Confirmed |

## Known discrepancies
_None known._

## Evidence
| Requirement | Implementation (paths, symbols) | Tests / observations | Verification | Observed |
| --- | --- | --- | --- | --- |
| FR-1 | src/auth.py | tests/test_auth.py | inspected | 2026-10-09 |
| NFR-1 | src/auth.py | tests/test_auth.py | inspected | 2026-10-09 |
| AC-1 | src/auth.py | tests/test_auth.py | executed/passed | 2026-10-09 |

## Changes
_None yet._
"""


def legacy_repo(root, status="Approved", with_tasks=True):
    """A standalone repo with one spec-kit style spec and no GroundWork lineage on it."""
    r = root / "legacy"
    git_init(r)
    (r / ".specify").mkdir()
    d = r / "specs" / "001-clients-and-tenants"
    d.mkdir(parents=True)
    (d / "spec.md").write_text(LEGACY_SPEC.format(status=status), encoding="utf-8")
    (d / "plan.md").write_text("# Plan\n\nFour tables.\n", encoding="utf-8")
    if with_tasks:
        (d / "tasks.md").write_text(LEGACY_TASKS, encoding="utf-8")
    return r


def fm(path):
    import groundwork_core as C

    return C.split_fm(Path(path).read_text(encoding="utf-8"))[0]


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))


class Import(Base):
    def test_dry_run_inventories_and_writes_nothing(self):
        r = legacy_repo(self.root, status="Draft")
        before = {p: p.read_bytes() for p in r.rglob("*") if p.is_file()}
        out = ca(r, "adopt-specs", "--dry-run")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("would import: 001-clients-and-tenants", out.stdout)
        self.assertIn("status=Draft", out.stdout)
        self.assertIn("tasks=1/2", out.stdout)
        self.assertIn("not marked finished", out.stdout)
        self.assertEqual(
            before, {p: p.read_bytes() for p in r.rglob("*") if p.is_file()}
        )
        self.assertFalse((r / ".groundwork" / "capabilities.json").exists())
        self.assertFalse((r / ".groundwork" / "approvals.json").exists())

    def test_import_adds_front_matter_only_and_is_idempotent(self):
        r = legacy_repo(self.root)
        sp = r / "specs" / "001-clients-and-tenants" / "spec.md"
        body = sp.read_bytes()
        self.assertEqual(ca(r, "adopt-specs").returncode, 0)
        text = sp.read_text(encoding="utf-8")
        meta = fm(sp)
        self.assertEqual(meta["origin"], "imported")
        self.assertEqual(meta["adoption_state"], "pending")
        self.assertEqual(meta["adopted_from"], "spec-kit")
        self.assertEqual(meta["adopted_status"], "Approved")
        self.assertEqual(meta["created"], "2026-08-12")
        self.assertEqual(meta["id"], "001-clients-and-tenants")
        self.assertEqual(meta["title"], "Clients and Tenants")
        self.assertEqual(meta["historical_companions"], ["plan.md", "tasks.md"])
        self.assertNotIn("author", meta)  # the original owner was "—": never invented
        self.assertTrue(text.endswith(body.decode()))  # body bytes untouched
        self.assertFalse(
            (r / "specs" / "001-clients-and-tenants" / "evals.md").exists()
        )
        self.assertFalse((r / ".groundwork" / "approvals.json").exists())
        self.assertFalse((r / ".groundwork" / "active").exists())
        # a capability row links it, and the table is generated
        caps = json.loads(
            (r / ".groundwork" / "capabilities.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            caps["clients-and-tenants"]["specs"], ["001-clients-and-tenants"]
        )
        self.assertIn(
            "import-review", (r / "specs" / "README.md").read_text(encoding="utf-8")
        )
        # rerun: nothing changes
        snap = {
            p: p.read_bytes()
            for p in r.rglob("*")
            if p.is_file() and ".git/" not in str(p)
        }
        out = ca(r, "adopt-specs")
        self.assertIn("nothing", out.stdout)
        self.assertEqual(
            snap,
            {
                p: p.read_bytes()
                for p in r.rglob("*")
                if p.is_file() and ".git/" not in str(p)
            },
        )

    def test_foreign_front_matter_is_preserved_or_reported(self):
        r = legacy_repo(self.root)
        sp = r / "specs" / "001-clients-and-tenants" / "spec.md"
        sp.write_text(
            "---\ntool: other\nstatus: Done\n---\n" + LEGACY_SPEC.format(status="x"),
            encoding="utf-8",
        )
        ca(r, "adopt-specs")
        meta = fm(sp)
        self.assertEqual(meta["tool"], "other")  # unknown key kept
        self.assertEqual(meta["status"], "Done")  # existing key never changed
        self.assertEqual(meta["adopted_status"], "Done")
        self.assertEqual(meta["origin"], "imported")
        self.assertEqual(
            sp.read_text(encoding="utf-8").count("\n---\n"), 1
        )  # no second block
        # an id that contradicts the directory is reported, not overwritten
        d2 = r / "specs" / "002-other"
        d2.mkdir()
        (d2 / "spec.md").write_text(
            "---\nid: 002-else\n---\n# Spec: Other\n", encoding="utf-8"
        )
        out = ca(r, "adopt-specs")
        self.assertIn("needs a person: 002-other", out.stdout)
        self.assertNotIn("origin", fm(d2 / "spec.md"))

    def test_nonstandard_directory_is_reported_not_renamed(self):
        r = legacy_repo(self.root)
        d = r / "specs" / "Widgets_Old"
        d.mkdir()
        (d / "spec.md").write_text("# Spec: Old\n", encoding="utf-8")
        out = ca(r, "adopt-specs")
        self.assertIn("Widgets_Old: directory is not NNN-slug", out.stdout)
        self.assertTrue(d.is_dir())

    def test_pending_import_is_a_reference_not_work(self):
        r = legacy_repo(self.root)
        ca(r, "scaffold")
        for f in r.glob("*.md"):
            fill(f)
        ca(r, "adopt-specs")
        code, ids, items = check(r)
        self.assertNotIn("GW020", ids)
        self.assertNotIn("GW021", ids)
        self.assertNotIn("GW090", ids)
        self.assertIn("GW028", ids)
        self.assertEqual(code, 0, items)
        # never in flight; visible under --all and in the review summary
        self.assertNotIn("001-clients", ca(r, "board").stdout.split("DOCUMENTATION")[0])
        self.assertIn("awaiting classification", ca(r, "board").stdout)
        self.assertIn(
            "[import] 001-clients-and-tenants", ca(r, "board", "--all").stdout
        )
        ctx = ca(r, "session-context", stdin=json.dumps({"cwd": str(r)})).stdout.split(
            "Level:"
        )[1]
        self.assertNotIn("IN FLIGHT", ctx)
        self.assertIn("DOCUMENTATION REVIEW", ctx)
        self.assertIn("awaiting classification", ctx)
        # cannot be activated, approved, or cited
        self.assertNotEqual(ca(r, "activate", "001-clients-and-tenants").returncode, 0)
        a = ca(r, "approve", "specs/001-clients-and-tenants/spec.md")
        self.assertNotEqual(a.returncode, 0)
        self.assertIn("classified", a.stderr)
        self.assertFalse((r / ".groundwork" / "approvals.json").exists())

    def test_classify_baseline_planned_archived(self):
        r = legacy_repo(self.root)
        ca(r, "adopt-specs")
        sp = r / "specs" / "001-clients-and-tenants" / "spec.md"
        self.assertNotEqual(
            ca(
                r, "adopt-specs", "--classify", "bogus", "001-clients-and-tenants"
            ).returncode,
            0,
        )
        out = ca(r, "adopt-specs", "--classify", "baseline", "001-clients-and-tenants")
        self.assertEqual(out.returncode, 0, out.stderr)
        meta = fm(sp)
        self.assertEqual(meta["origin"], "baseline")
        self.assertNotIn("adoption_state", meta)
        self.assertTrue(meta["observed_at"])
        self.assertEqual(meta["adopted_status"], "Approved")  # provenance kept
        # only imports are classified
        self.assertNotEqual(
            ca(
                r, "adopt-specs", "--classify", "planned", "001-clients-and-tenants"
            ).returncode,
            0,
        )
        # archive from baseline is allowed; planned from an import removes the import state
        ca(r, "adopt-specs", "--classify", "archived", "001-clients-and-tenants")
        self.assertEqual(fm(sp)["adoption_state"], "archived")
        self.assertEqual(check(r)[1] & {"GW028", "GW020", "GW021"}, set())
        ca(r, "adopt-specs", "--classify", "planned", "001-clients-and-tenants")
        meta = fm(sp)
        self.assertNotIn("origin", meta)
        self.assertIn("rfc", meta)
        self.assertIn(
            "GW020", check(r)[1]
        )  # a planned feature is held to the normal rules again

    def test_workspace_import_covers_child_repos(self):
        ws = self.root / "ws"
        r = legacy_repo(ws)
        (ws / "PROJECT.md").write_text("# ws\n", encoding="utf-8")
        out = ca(ws, "adopt-specs", "--dry-run")
        self.assertIn(f"[{r.name}] would import: 001-clients-and-tenants", out.stdout)

    def test_init_points_at_legacy_specs(self):
        r = legacy_repo(self.root)
        out = ca(r, "init", "--dry-run").stdout
        self.assertIn("legacy specs: 1 spec directory", out)


class BaselineRules(CheckBase):
    """CheckBase holds a workspace `ws`, a repo `api` with an approved planned feature 001-widgets."""

    def baseline(self, slug="auth", finished=True, approve=True, adopted=False):
        out = ca(self.api, "new-baseline", slug, "--title", "Auth")
        self.assertEqual(out.returncode, 0, out.stderr)
        fdir = Path(out.stdout.splitlines()[0].strip())
        sp = fdir / "spec.md"
        if finished:
            fill(sp)
            text = sp.read_text(encoding="utf-8")
            # a filled template: give the ids real evidence rows and a manual test
            text = re.sub(r"## Intent and rationale.*", "", text, flags=re.DOTALL)
            sp.write_text(text.rstrip() + "\n\n" + BASELINE_TAIL, encoding="utf-8")
            ca(self.api, "record", "owner", "--ref", fdir.name, "--who", "Lead Person")
        if adopted:
            import groundwork_core as C

            sp.write_text(
                C.set_fm(sp.read_text(encoding="utf-8"), {"adopted_from": "spec-kit"}),
                encoding="utf-8",
            )
        if approve:
            a = ca(self.api, "approve", str(sp), "--as", "lead")
            self.assertEqual(a.returncode, 0, a.stderr)
        return fdir

    def test_new_baseline_creates_spec_only_and_keeps_active_work(self):
        active_before = (self.api / ".groundwork" / "active").read_text(
            encoding="utf-8"
        )
        fdir = self.baseline(finished=False, approve=False)
        self.assertEqual(sorted(p.name for p in fdir.iterdir()), ["spec.md"])
        self.assertEqual(fdir.name, "002-auth")
        self.assertEqual(
            (self.api / ".groundwork" / "active").read_text(encoding="utf-8"),
            active_before,
        )
        self.assertEqual(fm(fdir / "spec.md")["origin"], "baseline")
        self.assertNotEqual(
            ca(self.api, "new-baseline", "auth").returncode, 0
        )  # collision refused
        self.assertNotEqual(ca(self.api, "activate", "002-auth").returncode, 0)
        caps = json.loads(
            (self.api / ".groundwork" / "capabilities.json").read_text(encoding="utf-8")
        )
        self.assertEqual(caps["auth"]["specs"], ["002-auth"])
        # unfinished: one warning, never GW020 for missing companions; a planned feature is untouched
        code, ids, items = check(self.ws)
        self.assertNotIn("GW020", ids)
        self.assertIn("GW025", ids)
        self.assertEqual(code, 0, items)

    def test_finished_approved_baseline_is_clean_and_not_in_flight(self):
        fdir = self.baseline()
        code, ids, items = check(self.ws, "--strict")
        self.assertEqual((code, ids), (0, set()), items)
        board = ca(self.api, "board").stdout
        self.assertNotIn("002-auth", board)
        self.assertIn("[baseline] 002-auth", ca(self.api, "board", "--all").stdout)
        ctx = ca(
            self.api, "session-context", stdin=json.dumps({"cwd": str(self.api)})
        ).stdout
        self.assertNotIn(
            "002-auth", ctx.split("PHASE:")[0].replace("DOCUMENTATION REVIEW", "")
        )
        # doctor: documentation line, and baselines do not establish stage 5 on their own
        d = json.loads(ca(self.api, "doctor", "--json").stdout)
        self.assertTrue(any(i["area"] == "Documentation" for i in d["items"]))
        del fdir

    def test_baseline_only_repo_is_not_practicing(self):
        # remove the planned feature: only the baseline remains
        import shutil

        shutil.rmtree(self.fdir)
        (self.api / ".groundwork" / "active").unlink()
        self.rfc.unlink()  # no RFC → spec path is not in use; only the baseline remains
        self.baseline()
        ca(self.api, "hooks", "install")
        d = json.loads(ca(self.api, "doctor", "--json").stdout)
        self.assertLess(d["stage"], 5, d["items"])

    def test_metadata_rules(self):
        fdir = self.baseline(approve=False)
        sp = fdir / "spec.md"
        import groundwork_core as C

        sp.write_text(
            C.set_fm(sp.read_text(encoding="utf-8"), {"origin": "legacy"}),
            encoding="utf-8",
        )
        self.assertFires("GW027")
        sp.write_text(
            C.set_fm(
                sp.read_text(encoding="utf-8"),
                {"origin": "baseline", "adoption_state": "pending"},
            ),
            encoding="utf-8",
        )
        self.assertFires("GW027")
        import groundwork_baseline as BL

        sp.write_text(
            C.set_fm(
                BL._remove_fm_keys(sp.read_text(encoding="utf-8"), {"adoption_state"}),
                {"origin": "imported"},
            ),
            encoding="utf-8",
        )
        self.assertIn(
            "adoption_state", ca(self.api, "check").stdout
        )  # imported needs a state
        # a tasks.md in a baseline must be historical
        sp.write_text(
            C.set_fm(
                BL._remove_fm_keys(sp.read_text(encoding="utf-8"), {"adoption_state"}),
                {"origin": "baseline"},
            ),
            encoding="utf-8",
        )
        (fdir / "tasks.md").write_text(LEGACY_TASKS, encoding="utf-8")
        self.assertFires("GW027")
        sp.write_text(
            C.set_fm(
                sp.read_text(encoding="utf-8"),
                {"historical_companions": "[tasks.md, plan.md]"},
            ),
            encoding="utf-8",
        )
        _, ids, _ = check(self.ws)
        self.assertNotIn("GW027", ids)
        self.assertIn("GW028", ids)  # plan.md listed but missing
        self.assertNotIn(
            "GW034", ids
        )  # historical ticked tasks are not a process violation

    def test_content_rules(self):
        fdir = self.baseline(approve=False)
        sp = fdir / "spec.md"
        self.edit(
            sp,
            lambda t: t.replace(
                "## Known discrepancies\n_None known._", "## Known discrepancies\n"
            ),
        )
        self.assertFires("GW029")
        self.edit(
            sp,
            lambda t: t.replace(
                "## Known discrepancies\n", "## Known discrepancies\n_None known._\n"
            ).replace(
                "| NFR-1 | src/auth.py | tests/test_auth.py | inspected | 2026-10-09 |\n",
                "",
            ),
        )
        _, ids, items = check(self.ws)
        self.assertIn("GW029", ids)
        self.assertTrue(
            any(f["severity"] == "warning" and "NFR-1" in f["message"] for f in items),
            items,
        )
        # an authored baseline must keep the standard sections (error); a reconciled import only warns
        self.edit(
            sp,
            lambda t: t.replace("## 7. Failure behaviour", "## 7. Resolved decisions"),
        )
        _, _, items = check(self.ws)
        self.assertTrue(
            any(f["id"] == "GW022" and f["severity"] == "error" for f in items)
        )
        import groundwork_core as C

        sp.write_text(
            C.set_fm(sp.read_text(encoding="utf-8"), {"adopted_from": "spec-kit"}),
            encoding="utf-8",
        )
        _, _, items = check(self.ws)
        self.assertTrue(
            any(f["id"] == "GW022" and f["severity"] == "warning" for f in items)
        )
        self.assertFalse(
            any(f["id"] == "GW022" and f["severity"] == "error" for f in items)
        )
        self.assertNotIn("GW021", {f["id"] for f in items})  # no RFC needed
        # an AC that cites nothing blocks approval too (the body must be a usable reference)
        self.edit(sp, lambda t: t.replace("(covers FR-1)", ""))
        ca(self.api, "record", "owner", "--ref", fdir.name, "--who", "Lead Person")
        a = ca(self.api, "approve", str(sp), "--as", "lead")
        self.assertNotEqual(a.returncode, 0)
        self.assertIn("does not cite", a.stderr)

    def test_approval_preflight_reads_body_and_required_metadata_only(self):
        fdir = self.baseline(approve=False)
        sp = fdir / "spec.md"
        # owner lives in front matter and is required
        ca(self.api, "record", "owner", "--ref", fdir.name, "--who", "")
        import groundwork_core as C

        sp.write_text(
            C.set_fm(sp.read_text(encoding="utf-8"), {"owner": ""}), encoding="utf-8"
        )
        a = ca(self.api, "approve", str(sp))
        self.assertNotEqual(a.returncode, 0)
        self.assertIn("owner", a.stderr)
        sp.write_text(
            C.set_fm(sp.read_text(encoding="utf-8"), {"owner": "Lead Person"}),
            encoding="utf-8",
        )
        # evidence outside the body (a capability note) changes nothing for approval
        ca(self.api, "capability", "set", "auth", "next_action=whatever")
        self.assertEqual(ca(self.api, "approve", str(sp), "--as", "lead").returncode, 0)
        ca(self.api, "capability", "set", "auth", "next_action=changed later")
        self.assertIn("approved", ca(self.api, "status").stdout.lower())
        self.assertEqual(check(self.ws)[1] & {"GW026", "GW076"}, set())

    def test_relations_to_baselines(self):
        fdir = self.baseline(approve=False)
        import groundwork_core as C

        spec = self.fdir / "spec.md"
        spec.write_text(
            C.set_fm(spec.read_text(encoding="utf-8"), {"depends_on": "[002-auth]"}),
            encoding="utf-8",
        )
        # unapproved baseline: relation refused, dependency not satisfied
        code, ids, items = check(self.ws)
        self.assertIn("GW076", ids)
        self.assertIn("002-auth", ca(self.api, "deps", "001-widgets").stdout)
        self.assertIn("not approved", ca(self.api, "deps", "001-widgets").stdout)
        # approve the baseline: satisfied without any tasks
        ca(self.api, "record", "owner", "--ref", "002-auth", "--who", "Lead Person")
        self.assertEqual(
            ca(self.api, "approve", str(fdir / "spec.md"), "--as", "lead").returncode, 0
        )
        code, ids, items = check(self.ws)
        self.assertNotIn("GW076", ids)
        self.assertNotIn("GW074", ids)
        self.assertIn("[implemented]", ca(self.api, "deps", "001-widgets").stdout)
        # an open discrepancy warns by name but does not block
        self.edit(
            fdir / "spec.md",
            lambda t: t.replace(
                "_None known._", "- [ ] **D1** — key rotation fails — bug: bugs/001-x"
            ),
        )
        self.edit(
            fdir / "spec.md",
            lambda t: t.replace(
                "## Changes\n_None yet._", "## Changes\n- 2026-10-09: D1 recorded"
            ),
        )
        ca(self.api, "approve", str(fdir / "spec.md"), "--as", "lead")
        code, ids, items = check(self.ws)
        self.assertIn("GW075", ids)
        self.assertNotIn("GW076", ids)
        self.assertTrue(
            any("key rotation" in f["message"] for f in items if f["id"] == "GW075")
        )
        self.assertEqual(code, 0, items)
        # edited after approval: refused again
        self.edit(fdir / "spec.md", lambda t: t + "\nmore\n")
        self.assertIn("GW076", check(self.ws)[1])

    def test_bug_cannot_cite_pending_import_but_can_cite_approved_baseline(self):
        fdir = self.baseline()
        ca(self.api, "new-bug", "rotation", "--title", "rotation fails")
        bp = self.api / "bugs" / "001-rotation.md"
        import groundwork_core as C

        fill(bp)
        bp.write_text(
            C.set_fm(
                bp.read_text(encoding="utf-8"),
                {
                    "classification": "code-bug",
                    "violates": "[FR-1@002-auth]",
                    "status": "diagnosed",
                    "regression_test": "tests/test_rotation.py",
                },
            ),
            encoding="utf-8",
        )
        self.assertNotIn(
            "002-auth", ca(self.api, "check").stdout
        )  # no GW062 about the target
        self.assertFalse(
            denied(self.api, self.api / "src" / "x.py")[0]
        )  # the fix may proceed
        # a pending import cannot be cited
        d = self.api / "specs" / "003-legacy"
        d.mkdir()
        (d / "spec.md").write_text(
            LEGACY_SPEC.format(status="Approved"), encoding="utf-8"
        )
        ca(self.api, "adopt-specs", "003-legacy")
        bp.write_text(
            C.set_fm(bp.read_text(encoding="utf-8"), {"violates": "[FR-1@003-legacy]"}),
            encoding="utf-8",
        )
        out = ca(self.api, "check").stdout
        self.assertIn("classify it first", out)
        del fdir

    def test_amending_a_baseline_follows_the_normal_path(self):
        fdir = self.baseline()
        import groundwork_core as C

        spec = self.fdir / "spec.md"
        spec.write_text(
            C.set_fm(spec.read_text(encoding="utf-8"), {"amends": "[002-auth]"}),
            encoding="utf-8",
        )
        ca(self.api, "approve", str(spec), "--as", "lead")
        self.assertIn(
            "GW072", check(self.ws)[1]
        )  # the baseline must record the amendment
        self.edit(
            fdir / "spec.md",
            lambda t: t.replace(
                "## Changes\n_None yet._",
                "## Changes\n- 2026-10-09: amended by 001-widgets",
            ),
        )
        self.assertIn("GW076", check(self.ws)[1])  # edited → stale → re-approve
        ca(self.api, "approve", str(fdir / "spec.md"), "--as", "lead")
        self.assertEqual(check(self.ws)[1] & {"GW072", "GW076"}, set())


class MultiApprove(CheckBase):
    def test_all_or_nothing(self):
        a = ca(self.api, "new-baseline", "auth", "--title", "Auth")
        b = ca(self.api, "new-baseline", "billing", "--title", "Billing")
        fa, fb = Path(a.stdout.splitlines()[0]), Path(b.stdout.splitlines()[0])
        for f in (fa, fb):
            sp = f / "spec.md"
            fill(sp)
            text = sp.read_text(encoding="utf-8")
            text = re.sub(
                r"## Intent and rationale.*", "", text, flags=re.DOTALL
            ).rstrip()
            sp.write_text(text + "\n\n" + BASELINE_TAIL, encoding="utf-8")
            ca(self.api, "record", "owner", "--ref", f.name, "--who", "Lead Person")
        (fb / "spec.md").write_text(
            (fb / "spec.md").read_text(encoding="utf-8")
            + "\n[NEEDS CLARIFICATION: x]\n",
            encoding="utf-8",
        )
        before = (self.api / ".groundwork" / "approvals.json").read_text(
            encoding="utf-8"
        )
        out = ca(
            self.api,
            "approve",
            str(fa / "spec.md"),
            str(fb / "spec.md"),
            "--as",
            "lead",
        )
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("nothing approved", out.stderr)
        self.assertEqual(
            before,
            (self.api / ".groundwork" / "approvals.json").read_text(encoding="utf-8"),
        )
        # duplicates refused; then both recorded independently
        self.assertIn(
            "given twice",
            ca(self.api, "approve", str(fa / "spec.md"), str(fa / "spec.md")).stderr,
        )
        fill(fb / "spec.md")
        out = ca(
            self.api,
            "approve",
            str(fa / "spec.md"),
            str(fb / "spec.md"),
            "--as",
            "lead",
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        rec = json.loads(
            (self.api / ".groundwork" / "approvals.json").read_text(encoding="utf-8")
        )
        self.assertIn("specs/002-auth/spec.md", rec)
        self.assertIn("specs/003-billing/spec.md", rec)
        self.assertNotEqual(
            rec["specs/002-auth/spec.md"]["hash"],
            rec["specs/003-billing/spec.md"]["hash"],
        )

    def test_slash_command_takes_several_paths(self):
        out = ca(
            self.api,
            "prompt-reminder",
            stdin=json.dumps(
                {
                    "cwd": str(self.api),
                    "prompt": "/groundwork-specflow:approve RFC-0001 specs/001-widgets/spec.md --as lead",
                }
            ),
        )
        self.assertIn("RFC-0001", out.stdout)
        self.assertIn("approved", out.stdout)


class Capabilities(CheckBase):
    def test_records_table_and_links(self):
        ca(
            self.api,
            "capability",
            "set",
            "search",
            "title=Case search",
            "lifecycle=active",
            "sources=app/retrieval.py,app/router.py",
        )
        caps = json.loads(
            (self.api / ".groundwork" / "capabilities.json").read_text(encoding="utf-8")
        )
        self.assertEqual(caps["search"]["lifecycle"], "active")
        self.assertTrue(caps["search"]["lifecycle_confirmed"])
        self.assertEqual(
            caps["search"]["sources"], ["app/retrieval.py", "app/router.py"]
        )
        self.assertEqual(caps["search"]["specs"], [])
        self.assertNotEqual(
            ca(self.api, "capability", "set", "search", "lifecycle=bogus").returncode, 0
        )
        readme = self.api / "specs" / "README.md"
        text = readme.read_text(encoding="utf-8")
        self.assertIn("| `search` | active | deferred |", text)
        # deferred capabilities are a review item, never in flight
        self.assertIn("capability deferred", ca(self.api, "board").stdout)
        self.assertNotIn(
            "search", ca(self.api, "board").stdout.split("DOCUMENTATION")[0]
        )
        # notes survive regeneration; prose outside the block survives too
        row = next(ln for ln in text.splitlines() if ln.startswith("| `search` |"))
        self.assertTrue(row.endswith("| — | — |  |"), row)
        readme.write_text(
            "# My specs\n\nSome prose.\n\n"
            + text.replace(row, row[: -len("|  |")] + "| keep me |"),
            encoding="utf-8",
        )
        ca(self.api, "capabilities")
        text = readme.read_text(encoding="utf-8")
        self.assertIn("Some prose.", text)
        self.assertIn("keep me", text)
        self.assertEqual(text.count("groundwork:capabilities start"), 1)
        # linking is additive and idempotent; coverage shows the weakest state with counts
        ca(self.api, "new-baseline", "auth", "--title", "Auth")
        ca(self.api, "capability", "link", "search", "001-widgets")
        ca(self.api, "capability", "link", "search", "002-auth")
        ca(self.api, "capability", "link", "search", "002-auth")
        caps = json.loads(
            (self.api / ".groundwork" / "capabilities.json").read_text(encoding="utf-8")
        )
        self.assertEqual(caps["search"]["specs"], ["001-widgets", "002-auth"])
        self.assertIn(
            "uncovered (1 planned, 1 baseline unapproved)",
            readme.read_text(encoding="utf-8"),
        )
        ca(self.api, "capability", "unlink", "search", "001-widgets")
        self.assertEqual(
            json.loads(
                (self.api / ".groundwork" / "capabilities.json").read_text(
                    encoding="utf-8"
                )
            )["search"]["specs"],
            ["002-auth"],
        )
        # a stale table warns; regenerating clears it
        readme.write_text(
            readme.read_text(encoding="utf-8").replace("facts=", "facts=0"),
            encoding="utf-8",
        )
        self.assertIn("GW041", check(self.ws)[1])
        ca(self.api, "capabilities")
        self.assertNotIn("GW041", check(self.ws)[1])

    def test_planned_feature_gate_is_unchanged(self):
        # a baseline in the repo changes nothing for the planned feature's gate
        ca(self.api, "new-baseline", "auth")
        self.assertFalse(denied(self.api, self.api / "src" / "x.py")[0])
        # a hand-edited active pointer at a baseline (or an archived import) never opens the gate
        (self.api / ".groundwork" / "active").write_text("002-auth\n", encoding="utf-8")
        d, why = denied(self.api, self.api / "src" / "x.py")
        self.assertTrue(d)
        self.assertIn("never an implementation target", why)
        self.assertIn("not an implementation target", ca(self.api, "status").stdout)
        d3 = self.api / "specs" / "003-old"
        d3.mkdir()
        (d3 / "spec.md").write_text(
            LEGACY_SPEC.format(status="Approved"), encoding="utf-8"
        )
        ca(self.api, "adopt-specs", "003-old")
        ca(self.api, "adopt-specs", "--classify", "archived", "003-old")
        (self.api / ".groundwork" / "active").write_text("003-old\n", encoding="utf-8")
        self.assertTrue(denied(self.api, self.api / "src" / "x.py")[0])
        self.assertNotIn(
            "003-old", ca(self.api, "board").stdout
        )  # archived: neither in flight nor awaiting review


if __name__ == "__main__":
    unittest.main()
