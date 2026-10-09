"""Contracts with named reviewers, and the richer discovery that feeds baselines and contracts (§5j, §9)."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import CheckBase, check
from test_flow import Base, ca, denied, fill, git_init

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))


class Contracts(CheckBase):
    def contract(self, as_built=True):
        out = ca(
            self.api,
            "new-contract",
            "api-http",
            "--title",
            "API over HTTP",
            "--provider",
            "api",
            "--consumers",
            "web,mobile",
            *(["--as-built"] if as_built else []),
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        p = self.ws / "CONTRACTS" / "api-http.md"
        self.assertTrue(p.is_file(), out.stdout)
        return p

    def test_new_contract_lands_in_the_workspace_with_front_matter(self):
        p = self.contract()
        import groundwork_core as C

        meta = C.split_fm(p.read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["id"], "api-http")
        self.assertEqual(meta["provider"], "api")
        self.assertEqual(meta["consumers"], ["web", "mobile"])
        self.assertEqual(meta["version"], "1.0.0")
        self.assertEqual(meta["origin"], "baseline")
        self.assertEqual(meta["signoffs_required"], "2")
        self.assertNotEqual(
            ca(self.api, "new-contract", "api-http").returncode, 0
        )  # no second file
        planned = ca(self.ws, "new-contract", "api-events", "--provider", "api").stdout
        self.assertIn("Planned contract", planned)
        self.assertNotIn(
            "origin",
            C.split_fm(
                (self.ws / "CONTRACTS" / "api-events.md").read_text(encoding="utf-8")
            )[0],
        )
        # unfinished: one warning, nothing else; a hand-written contract is left alone
        (self.ws / "CONTRACTS" / "legacy-notes.md").write_text(
            "# Old contract\nfree text\n", encoding="utf-8"
        )
        _, ids, items = check(self.ws)
        self.assertIn("GW046", ids)
        self.assertEqual(ids & {"GW045", "GW047"}, set(), items)
        self.assertFalse(any("legacy-notes" in f["path"] for f in items))

    def test_named_reviewers_warn_until_they_sign(self):
        p = self.contract()
        fill(p)
        import groundwork_core as C

        # no reviewers named: warning
        _, ids, items = check(self.ws)
        self.assertIn("GW047", ids)
        self.assertTrue(
            any(
                "no provider_reviewer" in f["message"]
                for f in items
                if f["id"] == "GW047"
            )
        )
        p.write_text(
            C.set_fm(
                p.read_text(encoding="utf-8"),
                {"provider_reviewer": "Lead Person", "consumer_reviewers": "[Dev Two]"},
            ),
            encoding="utf-8",
        )
        _, ids, _ = check(self.ws)
        self.assertNotIn(
            "GW047", ids
        )  # named, nobody signed yet: nothing to warn about
        self.assertIn("awaiting sign-off (0/2)", ca(self.ws, "board").stdout)
        # one signer who is not a named reviewer: still in review, and the gap is named
        self.assertEqual(
            ca(self.ws, "approve", str(p), "--as", "someone").returncode, 0
        )
        _, ids, items = check(self.ws)
        self.assertIn("GW047", ids)
        msg = next(f["message"] for f in items if f["id"] == "GW047")
        self.assertIn("Lead Person", msg)
        self.assertIn("Dev Two", msg)
        self.assertIn(
            "not yet signed by Lead Person, Dev Two", ca(self.ws, "board").stdout
        )
        # both named reviewers sign (contact email resolves through the people table): clean, approved
        ca(self.ws, "approve", str(p), "--as", "lead@example.com")
        _, ids, items = check(self.ws)
        self.assertIn(
            "GW047", ids
        )  # Dev Two still missing, although the count (2) is reached
        self.assertIn(
            "approved by count, but not by named reviewer(s) Dev Two",
            ca(self.ws, "board").stdout,
        )
        ca(self.ws, "approve", str(p), "--as", "dev2@example.com")
        _, ids, items = check(self.ws, "--strict")
        self.assertEqual(ids & {"GW045", "GW046", "GW047"}, set(), items)
        self.assertNotIn("CONTRACTS/api-http.md", ca(self.ws, "board").stdout)
        ctx = ca(
            self.api, "session-context", stdin=json.dumps({"cwd": str(self.api)})
        ).stdout
        self.assertNotIn("CONTRACTS/api-http.md", ctx)  # no longer awaiting anyone

    def test_metadata_and_shape_rules(self):
        p = self.contract()
        fill(p)
        import groundwork_core as C

        p.write_text(
            C.set_fm(p.read_text(encoding="utf-8"), {"version": "2026-10-09"}),
            encoding="utf-8",
        )
        _, _, items = check(self.ws)
        self.assertTrue(
            any(f["id"] == "GW045" and "semver" in f["message"] for f in items)
        )
        p.write_text(
            C.set_fm(
                p.read_text(encoding="utf-8"), {"version": "1.0.0", "id": "other"}
            ),
            encoding="utf-8",
        )
        self.assertTrue(
            any(
                f["id"] == "GW045" and "file name" in f["message"]
                for f in check(self.ws)[2]
            )
        )
        p.write_text(
            C.set_fm(p.read_text(encoding="utf-8"), {"id": "api-http"}),
            encoding="utf-8",
        )
        self.edit(
            p,
            lambda t: t.replace("## 4. Errors and failure semantics", "## 4. Failures"),
        )
        self.assertTrue(
            any(
                f["id"] == "GW046" and "4. Errors" in f["message"]
                for f in check(self.ws)[2]
            )
        )
        self.edit(
            p,
            lambda t: t.replace("## 4. Failures", "## 4. Errors and failure semantics"),
        )
        self.edit(
            p,
            lambda t: (
                t.split("## 7. Evidence")[0]
                + "## 7. Evidence\n\n## Changes\n_None yet._\n"
            ),
        )
        self.assertTrue(
            any(
                f["id"] == "GW046" and "Evidence" in f["message"]
                for f in check(self.ws)[2]
            )
        )

    def test_standalone_repo_gets_its_own_contracts_folder(self):
        r = self.root / "solo"
        git_init(r)
        out = ca(r, "new-contract", "solo-api", "--as-built")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue((r / "CONTRACTS" / "solo-api.md").is_file())


class ContractHardening(CheckBase):
    """The five gaps found in review: linked destinations, malformed metadata, child-repo visibility,
    incomplete reviewer assignments."""

    def test_linked_contracts_dir_is_refused(self):
        outside = self.root / "elsewhere"
        outside.mkdir()
        import shutil

        shutil.rmtree(self.ws / "CONTRACTS")
        (self.ws / "CONTRACTS").symlink_to(outside, target_is_directory=True)
        out = ca(self.ws, "new-contract", "api-http", "--as-built")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("symlinked", out.stderr)
        self.assertEqual(list(outside.iterdir()), [])

    def test_malformed_metadata_is_a_finding_not_a_crash(self):
        p = Contracts.contract(self)
        fill(p)
        import groundwork_core as C

        p.write_text(
            C.set_fm(p.read_text(encoding="utf-8"), {"signoffs_required": "many"}),
            encoding="utf-8",
        )
        out = ca(self.ws, "check", "--json")
        self.assertEqual(
            out.returncode, 1, out.stderr
        )  # an error finding, not a traceback
        items = json.loads(out.stdout)["findings"]
        self.assertTrue(
            any(
                f["id"] == "GW045" and "signoffs_required" in f["message"]
                for f in items
            ),
            items,
        )
        self.assertIn(
            "whole number", ca(self.ws, "approve", str(p), "--as", "lead").stderr
        )
        self.assertEqual(ca(self.ws, "status").returncode, 0)
        p.write_text(
            C.set_fm(
                p.read_text(encoding="utf-8"), {"signoffs_required": "2", "id": ""}
            ),
            encoding="utf-8",
        )
        items = check(self.ws)[2]
        self.assertTrue(
            any(f["id"] == "GW045" and "blank: id" in f["message"] for f in items),
            items,
        )

    def test_child_repo_sees_workspace_contracts(self):
        p = Contracts.contract(self)
        fill(p)
        import groundwork_core as C

        p.write_text(
            C.set_fm(
                p.read_text(encoding="utf-8"),
                {"provider_reviewer": "Lead Person", "consumer_reviewers": "[Dev Two]"},
            ),
            encoding="utf-8",
        )
        ca(self.ws, "approve", str(p), "--as", "someone")
        board = ca(self.api, "board").stdout
        self.assertIn("workspace/CONTRACTS/api-http.md", board)
        ctx = ca(
            self.api, "session-context", stdin=json.dumps({"cwd": str(self.api)})
        ).stdout
        self.assertIn("workspace/CONTRACTS/api-http.md", ctx)
        _, ids, _ = check(self.api)
        self.assertIn("GW047", ids)  # reported from the repo's own check too

    def test_incomplete_reviewer_assignment_stays_pending(self):
        p = Contracts.contract(self)
        fill(p)
        import groundwork_core as C

        # nobody named, two approvals: approved by count, still pending and still warned
        ca(self.ws, "approve", str(p), "--as", "a@example.com")
        ca(self.ws, "approve", str(p), "--as", "b@example.com")
        _, ids, items = check(self.ws)
        self.assertIn("GW047", ids)
        self.assertTrue(
            any(
                "approved by count only" in f["message"]
                for f in items
                if f["id"] == "GW047"
            )
        )
        self.assertIn(
            "reviewers incomplete: no provider_reviewer / consumer_reviewers named",
            ca(self.ws, "board").stdout,
        )
        # provider named only: the missing consumer side is called out
        p.write_text(
            C.set_fm(
                p.read_text(encoding="utf-8"), {"provider_reviewer": "Lead Person"}
            ),
            encoding="utf-8",
        )
        _, ids, items = check(self.ws)
        msg = next(f["message"] for f in items if f["id"] == "GW047")
        self.assertIn("consumer_reviewers", msg)
        self.assertNotIn("provider_reviewer", msg)
        self.assertIn("no consumer_reviewers named", ca(self.ws, "board").stdout)


class MalformedSignoffCount(CheckBase):
    """A malformed `signoffs_required` can never be satisfied: an existing record with fewer
    signatures must not become sufficient, and the code-edit gate must stay closed."""

    def test_existing_record_never_becomes_sufficient(self):
        import groundwork_core as C

        code = self.api / "src" / "x.py"
        self.assertFalse(denied(self.api, code)[0])  # RFC and spec approved: open
        # require two signatures: the single existing one is now in review, gate closed
        self.rfc.write_text(
            C.set_fm(self.rfc.read_text(encoding="utf-8"), {"signoffs_required": "2"}),
            encoding="utf-8",
        )
        d, why = denied(self.api, code)
        self.assertTrue(d)
        self.assertIn("in-review", why)
        # change only the count to nonsense: still not approved, still closed, no crash
        self.rfc.write_text(
            C.set_fm(
                self.rfc.read_text(encoding="utf-8"), {"signoffs_required": "many"}
            ),
            encoding="utf-8",
        )
        d, why = denied(self.api, code)
        self.assertTrue(d, why)
        self.assertIn("in-review", why)
        self.assertIn(
            "invalid",
            ca(self.ws, "status").stdout + ca(self.api, "status").stdout + why,
        )
        out = ca(self.ws, "check", "--json")
        self.assertIn("GW010", {f["id"] for f in json.loads(out.stdout)["findings"]})
        self.assertNotEqual(
            ca(self.ws, "approve", "RFC-0001", "--as", "lead").returncode, 0
        )
        self.assertEqual(ca(self.ws, "board").returncode, 0)
        # the same on a spec: its record exists, its claim of approval is now reported, gate closed
        self.rfc.write_text(
            C.set_fm(self.rfc.read_text(encoding="utf-8"), {"signoffs_required": "1"}),
            encoding="utf-8",
        )
        self.assertFalse(denied(self.api, code)[0])
        sp = self.fdir / "spec.md"
        sp.write_text(
            C.set_fm(sp.read_text(encoding="utf-8"), {"signoffs_required": "0"}),
            encoding="utf-8",
        )
        self.assertTrue(denied(self.api, code)[0])
        self.assertIn("GW026", check(self.ws)[1])


class DiscoveryHardening(Base):
    def test_linked_parent_directory_is_not_read(self):
        r = self.root / "r"
        git_init(r)
        outside = self.root / "outside" / "memory"
        outside.mkdir(parents=True)
        (outside / "constitution.md").write_text(
            "- Never ship on Fridays.\n", encoding="utf-8"
        )
        (r / ".specify").symlink_to(self.root / "outside", target_is_directory=True)
        (r / "README.md").write_text("- Always write tests.\n", encoding="utf-8")
        ca(r, "init")
        d = json.loads(
            (r / ".groundwork" / "discovery.json").read_text(encoding="utf-8")
        )
        texts = [c["text"] for c in d["rules"]["candidates"]]
        self.assertFalse(any("Fridays" in t for t in texts), texts)
        self.assertTrue(any("Always write tests" in t for t in texts))
        self.assertIsNone(d["adoptable"]["constitution"])


ROUTES_PY = """from fastapi import APIRouter
router = APIRouter(prefix="/v1")

@router.get("/runs")
def list_runs(): ...

@router.post("/runs/{run_id}/close")
def close_run(run_id: str): ...

@router.get("/legacy/export")
def export(): ...
"""
SERVER_JS = """const app = express();
app.get('/health', (req, res) => res.send('ok'));
app.post('/orders', create);
app.use('/admin', adminRouter);
"""
CLI_PY = """import typer
app = typer.Typer()

@app.command()
def issue(): ...

@app.command("revoke-key")
def revoke(): ...
"""
TEST_PY = """def test_calls():
    api.get("/v1/not-a-route")
    app.get("/also-not")
"""
README = """# Demo

- Never store a provider key outside the gateway.
- Always run `make check` before pushing.
- No floats for money.
Some prose that says do not worry, this is not a rule.
1. Must not read secrets from files.
"""
CI = """jobs:
  check:
    steps:
      - run: make check
      - run: echo hello
      - run: |
          uv run pytest -q
"""


class Discovery(Base):
    def test_surfaces_rules_candidates_and_limits(self):
        r = self.root / "r"
        git_init(r)
        (r / "app").mkdir()
        (r / "app" / "routes.py").write_text(ROUTES_PY, encoding="utf-8")
        (r / "app" / "server.js").write_text(SERVER_JS, encoding="utf-8")
        (r / "app" / "cli.py").write_text(CLI_PY, encoding="utf-8")
        (r / "tests").mkdir()
        (r / "tests" / "test_api.py").write_text(TEST_PY, encoding="utf-8")
        (r / "jobs").mkdir()
        (r / "jobs" / "nightly_rebill.py").write_text(
            "def run(): ...\n", encoding="utf-8"
        )
        (r / "README.md").write_text(README, encoding="utf-8")
        (r / "docs").mkdir()
        (r / "docs" / "api.md").write_text("# API\n", encoding="utf-8")
        (r / "openapi.yaml").write_text("openapi: 3.0.0\n", encoding="utf-8")
        (r / ".github" / "workflows").mkdir(parents=True)
        (r / ".github" / "workflows" / "ci.yml").write_text(CI, encoding="utf-8")
        (r / "specs" / "001-old").mkdir(parents=True)
        (r / "specs" / "001-old" / "spec.md").write_text(
            "# Spec: Old\n\n**Status:** Draft\n", encoding="utf-8"
        )
        out = ca(r, "init")
        self.assertEqual(out.returncode, 0, out.stderr)
        d = json.loads(
            (r / ".groundwork" / "discovery.json").read_text(encoding="utf-8")
        )
        http = d["surface"]["http"]
        files = {f["file"]: f for f in http["files"]}
        self.assertIn("app/routes.py", files)
        self.assertIn("app/server.js", files)
        self.assertNotIn("tests/test_api.py", files)  # a test's calls are not routes
        self.assertEqual(files["app/routes.py"]["operations"], 3)
        self.assertEqual(files["app/routes.py"]["mounts"], ["/v1"])
        self.assertIn("/runs", http["prefixes"])
        self.assertIn("/orders", http["prefixes"])
        self.assertTrue(
            any("mounted" in x for x in http["limits"])
        )  # app.use(...) → prefixes combine
        self.assertEqual(d["surface"]["cli"]["commands"], ["issue", "revoke-key"])
        self.assertEqual(d["surface"]["schemas"], ["openapi.yaml"])
        self.assertEqual(d["surface"]["api_docs"], ["docs/api.md"])
        texts = [c["text"] for c in d["rules"]["candidates"]]
        self.assertTrue(
            any(t.startswith("Never store a provider key") for t in texts), texts
        )
        self.assertTrue(any(t.startswith("No floats") for t in texts))
        self.assertTrue(any(t.startswith("Must not read secrets") for t in texts))
        self.assertFalse(
            any("do not worry" in t for t in texts)
        )  # mid-sentence prose is not a rule
        self.assertEqual(
            [g["command"] for g in d["rules"]["ci_gates"]],
            ["make check", "uv run pytest -q"],
        )
        kinds = {(c["slug"], c["kind"]) for c in d["capability_candidates"]}
        self.assertIn(("runs", "http"), kinds)
        self.assertIn(("legacy", "http"), kinds)
        self.assertEqual(
            next(c for c in d["capability_candidates"] if c["slug"] == "legacy")[
                "suggested_lifecycle"
            ],
            "legacy",
        )
        self.assertIn(("cli-cli", "cli"), kinds)
        self.assertIn(("worker-nightly-rebill", "worker"), kinds)
        self.assertEqual(d["adoptable"]["specs"][0]["slug"], "001-old")
        self.assertEqual(d["adoptable"]["specs"][0]["original_status"], "Draft")
        self.assertTrue(d["adoptable"]["specs_dir"])  # old key kept
        self.assertIn("files_seen", d["scan"])
        self.assertTrue(any("regex" in u for u in d["scan"]["unsupported"]))
        text = out.stdout
        self.assertIn("HTTP route(s)", text)
        self.assertIn("candidate rule(s)", text)
        self.assertIn("legacy specs: 1 spec directory", text)

    def test_quiet_repo_has_empty_surfaces_and_no_noise(self):
        r = self.root / "q"
        git_init(r)
        (r / "lib.py").write_text("x = 1\n", encoding="utf-8")
        ca(r, "init")
        d = json.loads(
            (r / ".groundwork" / "discovery.json").read_text(encoding="utf-8")
        )
        self.assertEqual(d["surface"]["http"]["files"], [])
        self.assertEqual(d["rules"]["candidates"], [])
        self.assertEqual(d["capability_candidates"], [])
        self.assertEqual(d["adoptable"]["specs"], [])


if __name__ == "__main__":
    unittest.main()
