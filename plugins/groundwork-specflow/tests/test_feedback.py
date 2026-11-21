"""Feedback about GroundWork: a local draft and a pre-filled issue link, with no project details in either."""

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).parent))
ENGINE = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENGINE))
import groundwork as GW
import groundwork_core as C
import groundwork_feedback as FB
import groundwork_host as G
from test_flow import CA, ENV

REPO = Path(__file__).resolve().parents[3]

# Planted in the project; none of it may reach the draft or the link.
PRIVATE = [
    "acme-billing",
    "Jane Rivera",
    "Jane",
    "Rivera",
    "jane@acme.io",
    "Omar Haddad",
    "omar.h@acme.io",
    "invoice-export",
    "Invoice export to SAP",
    "ledger-sync",
    "Ledger sync",
    "Acme",  # a word of the project's own name, used alone
    "rounding-drift",
    "sap_client.py",
    "src/billing",
    "sk-ant-abcdefghijklmnopqrstuvwxyz123",
    "gitlab.acme.io",
    "10.0.0.12",
    "3f9a2b1c4d5e6f7a",
    "def secret",
]

PROJECT_MD = """\
# Acme Ledger

## Who works on what

| Person | Role | Owns | Contact |
| --- | --- | --- | --- |
| Jane Rivera | lead | billing | jane@acme.io |
| Omar Haddad | dev | sync | omar.h@acme.io |
"""


def make_project(root: Path) -> Path:
    proj = root / "acme-billing"
    for d in ("specs/003-invoice-export", "DECISIONS", "bugs/rounding-drift"):
        (proj / d).mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(proj)], check=True, env=ENV)
    subprocess.run(
        ["git", "-C", str(proj), "config", "user.name", "Jane Rivera"], check=True
    )
    subprocess.run(
        ["git", "-C", str(proj), "config", "user.email", "jane@acme.io"], check=True
    )
    (proj / "PROJECT.md").write_text(PROJECT_MD, encoding="utf-8")
    (proj / "specs/003-invoice-export/spec.md").write_text(
        "# Invoice export to SAP\n", encoding="utf-8"
    )
    (proj / "DECISIONS/RFC-0002-ledger-sync.md").write_text(
        "# RFC-0002: Ledger sync\n", encoding="utf-8"
    )
    return proj


LEAKY = {
    "title": "approve refused the invoice-export spec for Jane",
    "happened": (
        "Running approve on {proj}/specs/003-invoice-export/spec.md said stale though src/billing/sap_client.py "
        "was untouched. Jane Rivera (jane@acme.io) and omar.h@acme.io saw key sk-ant-abcdefghijklmnopqrstuvwxyz123 "
        "and https://gitlab.acme.io/acme/acme-billing/-/issues/4 on 10.0.0.12 at commit 3f9a2b1c4d5e6f7a. "
        "Ledger sync and rounding-drift too.\n```py\ndef secret(): pass\n```"
    ),
    "expected": "/groundwork-specflow:approve accepts it; engine/groundwork_core.py and/or the gate (GW092) agree",
    "where": "approve, GW092",
    "user_words": "This blocked me twice in Invoice export to SAP work, Omar Haddad and the Acme team agree",
}


class Scrubbing(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.proj = make_project(self.root)
        self.ctx = C.detect(self.proj)
        cwd = os.getcwd()
        os.chdir(self.proj)
        self.addCleanup(os.chdir, cwd)

    def build(self):
        args = {k: v.format(proj=self.proj) for k, v in LEAKY.items()}
        return FB.build(host="codex", ctx=self.ctx, **args)

    def assertClean(self, text):
        low = text.lower()
        for p in PRIVATE + [str(self.proj), self.proj.as_posix()]:
            self.assertNotIn(p.lower(), low, p)

    def test_nothing_planted_reaches_the_draft_or_the_link(self):
        rep = self.build()
        self.assertClean(rep.title + rep.markdown())
        query = parse_qs(urlparse(rep.url()).query)
        self.assertClean(json.dumps(query))
        for kind in (
            "path",
            "person",
            "project name",
            "email",
            "url",
            "key",
            "code",
            "ip address",
            "commit",
        ):
            self.assertIn(kind, rep.removed)

    def test_groundwork_vocabulary_survives(self):
        rep = self.build()
        self.assertIn("/groundwork-specflow:approve", rep.fields["expected"])
        self.assertIn("engine/groundwork_core.py", rep.fields["expected"])
        self.assertIn("and/or", rep.fields["expected"])
        self.assertEqual(rep.fields["where"], "approve, GW092")
        self.assertEqual(rep.fields["platform"], "Codex")
        self.assertTrue(rep.title.startswith("[feedback] approve refused"))

    def test_link_prefills_the_issue_form_and_stays_short(self):
        long = (
            "the gate blocked an edit — again. " * 100
        )  # each field is clipped; together they are too long
        rep = FB.build(
            title="t",
            happened=long,
            expected=long,
            user_words=long,
            details=long,
            ctx=self.ctx,
        )
        url = rep.url()
        self.assertLessEqual(len(url), FB.MAX_URL)
        q = parse_qs(urlparse(url).query)
        self.assertEqual(q["template"], [FB.FORM])
        self.assertTrue(any("shortened" in v[0] for v in q.values()))
        self.assertNotIn("shortened", rep.markdown())  # the draft keeps the full text
        self.assertTrue(url.startswith(FB.REPO_URL + "/issues/new?"))

    def test_shapes_without_any_context(self):
        r = FB.scrub(r"see C:\Users\ann\shop\app.ts and ~/shop/x and ann@x.org", None)
        self.assertNotIn("ann", r.text)
        self.assertNotIn("app.ts", r.text)


class Command(unittest.TestCase):
    def test_cli_writes_the_draft_outside_the_project_and_prints_the_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            proj = make_project(root)
            env = {**ENV, "GROUNDWORK_USER_DIR": str(root / "gwhome")}
            args = [
                a
                for k, v in LEAKY.items()
                for a in (f"--{k.replace('_', '-')}", v.format(proj=proj))
            ]
            r = subprocess.run(
                [sys.executable, str(CA), "feedback", *args, "--json"],
                cwd=proj,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                check=False,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)
            draft = Path(out["draft"])
            self.assertTrue(draft.is_file())
            self.assertEqual(draft.parent, root / "gwhome" / "feedback")
            text = draft.read_text(encoding="utf-8")
            for p in PRIVATE:
                self.assertNotIn(p.lower(), (text + r.stdout).lower(), p)
            self.assertFalse((proj / ".groundwork" / "feedback").exists())


class Fallback(unittest.TestCase):
    def test_unwritable_home_falls_back_to_the_temp_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocked = Path(tmp) / "file-not-dir"
            blocked.write_text(
                "x", encoding="utf-8"
            )  # mkdir under a file fails, as in Codex's sandbox
            temp = Path(tmp) / "temp"
            temp.mkdir()
            with (
                mock.patch.dict(os.environ, {"GROUNDWORK_USER_DIR": str(blocked)}),
                mock.patch.object(FB.tempfile, "gettempdir", return_value=str(temp)),
            ):
                path = FB.save(FB.build(title="t", happened="h"))
            self.assertEqual(path.parent, temp / "groundwork-feedback")
            self.assertIn(FB.REPO_URL, path.read_text(encoding="utf-8"))


class Crash(unittest.TestCase):
    def test_internal_error_prepares_a_draft_without_the_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)

            def boom(a):
                raise KeyError("/home/jane/acme-billing/specs/secret.md")

            err = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"GROUNDWORK_USER_DIR": str(home)}),
                mock.patch.object(GW, "cmd_board", boom),
                mock.patch.object(sys, "argv", ["groundwork.py", "board"]),
                redirect_stderr(err),
                self.assertRaises(KeyError),
            ):
                GW.main()
            (draft,) = (home / "feedback").glob("crash-*.md")
            text = draft.read_text(encoding="utf-8")
            self.assertIn("KeyError", text)
            self.assertIn("groundwork.py:", text)
            self.assertNotIn("jane", text.lower())
            self.assertNotIn("secret.md", text)
            self.assertIn(FB.REPO_URL, err.getvalue())
            self.assertIn("internal error", err.getvalue())

            err2 = io.StringIO()  # the same failure again: one short line, same draft
            with (
                mock.patch.dict(os.environ, {"GROUNDWORK_USER_DIR": str(home)}),
                mock.patch.object(GW, "cmd_board", boom),
                mock.patch.object(sys, "argv", ["groundwork.py", "board"]),
                redirect_stderr(err2),
                self.assertRaises(KeyError),
            ):
                GW.main()
            self.assertEqual(len(list((home / "feedback").glob("crash-*.md"))), 1)
            self.assertIn("again", err2.getvalue())

    def test_user_errors_are_not_reported_as_crashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.dict(os.environ, {"GROUNDWORK_USER_DIR": tmp}),
                mock.patch.object(
                    sys, "argv", ["groundwork.py", "record", "nope", "--ref", "x"]
                ),
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                GW.main()
            self.assertFalse((Path(tmp) / "feedback").exists())


class Wiring(unittest.TestCase):
    def test_issue_form_ids_match_the_report_fields(self):
        form = (REPO / ".github" / "ISSUE_TEMPLATE" / FB.FORM).read_text(
            encoding="utf-8"
        )
        ids = set(re.findall(r"^\s+id: ([\w-]+)$", form, re.MULTILINE))
        self.assertTrue({fid for fid, _ in FB.FIELDS} <= ids, ids)

    def test_codex_names_the_command_as_a_skill_mention(self):
        self.assertEqual(
            G.codex_commands("/groundwork-specflow:send-feedback"),
            "$groundwork-specflow:source-command-send-feedback",
        )

    def test_a_devin_project_install_reports_devin(self):
        with (
            mock.patch.object(G, "BOOTSTRAPPED", True),
            mock.patch.object(G, "name", return_value="claude"),
        ):
            self.assertEqual(
                FB.build(title="t", happened="h").fields["platform"], "Devin"
            )

    def test_version_comes_from_the_manifest(self):
        manifest = json.loads(
            (ENGINE.parent / ".claude-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(FB.version(), manifest["version"])


if __name__ == "__main__":
    unittest.main()
