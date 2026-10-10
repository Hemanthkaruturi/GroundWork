"""`groundwork init` and `groundwork doctor`."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "engine"))
import groundwork_core as C
from test_check import CheckBase
from test_flow import ENV, Base, ca, git_init

G = {
    **ENV,
    "GIT_COMMITTER_NAME": "Ann",
    "GIT_COMMITTER_EMAIL": "a@b.c",
    "GIT_AUTHOR_NAME": "Ann",
    "GIT_AUTHOR_EMAIL": "a@b.c",
}


def doctor(cwd):
    return json.loads(ca(cwd, "doctor", "--json").stdout)


class Init(Base):
    def test_discovery_never_reads_remote_credentials_or_secret_files(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
        import groundwork_discover as D
        import groundwork_fresh as F

        r = self.root / "r"
        git_init(r)
        subprocess.run(
            [
                "git",
                "-C",
                str(r),
                "remote",
                "add",
                "origin",
                "https://user:private-token@example.com/project.git",
            ],
            env=G,
            check=True,
        )
        infra = r / "infra"
        infra.mkdir()
        for name in (
            ".env",
            ".env.local",
            "credentials.json",
            "secrets.yaml",
            "server.key",
            "terraform.tfvars",
            "terraform.tfstate",
        ):
            (infra / name).write_text("private-token", encoding="utf-8")
        (infra / "main.tf").write_text("# infrastructure", encoding="utf-8")
        with (
            patch.object(D, "_git", wraps=D._git) as git,
            patch.object(F, "_file_hash", wraps=F._file_hash) as hashed,
        ):
            facts = D.discover(r)
            signals = F.signals(r, F.MANIFESTS | F.INFRA_NAMES, F.INFRA_GLOBS)
        self.assertFalse(any("remote" in call.args[1:] for call in git.call_args_list))
        self.assertEqual(list(signals), ["infra/main.tf"])
        self.assertEqual(
            [call.args[0].name for call in hashed.call_args_list], ["main.tf"]
        )
        self.assertNotIn("private-token", json.dumps(facts))
        self.assertNotIn("remote", facts["git"])

    def test_unknown_dir_is_refused_with_options(self):
        r = ca(self.root, "init")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--as repo", r.stderr)
        self.assertFalse((self.root / "PROJECT.md").exists())

    def test_as_repo_does_git_init_and_scaffolds(self):
        self.assertEqual(ca(self.root, "init", "--as", "repo").returncode, 0)
        self.assertTrue(
            (self.root / ".git").exists() and (self.root / "PROJECT.md").exists()
        )
        self.assertEqual(
            json.loads(
                (self.root / ".groundwork" / "config.json").read_text(encoding="utf-8")
            )["standard"],
            C.STANDARD_VERSION,
        )

    def test_as_workspace_marks_it(self):
        self.assertEqual(ca(self.root, "init", "--as", "workspace").returncode, 0)
        self.assertEqual(
            json.loads(
                (self.root / ".groundwork" / "config.json").read_text(encoding="utf-8")
            )["level"],
            "workspace",
        )
        self.assertTrue((self.root / "CONTRACTS").is_dir())

    def test_dry_run_writes_nothing(self):
        git_init(self.root / "r")
        out = ca(self.root / "r", "init", "--dry-run").stdout
        self.assertIn("would create PROJECT.md", out)
        self.assertEqual([p.name for p in (self.root / "r").iterdir()], [".git"])

    def test_is_idempotent_and_never_overwrites(self):
        git_init(self.root / "r")
        r = self.root / "r"
        ca(r, "init")
        (r / "PROJECT.md").write_text("# mine\n", encoding="utf-8")
        out = ca(r, "init").stdout
        self.assertIn("nothing (foundation already present)", out)
        self.assertEqual((r / "PROJECT.md").read_text(encoding="utf-8"), "# mine\n")

    def test_workspace_init_covers_child_repos(self):
        git_init(self.root / "ws" / "api")
        git_init(self.root / "ws" / "web")
        ca(self.root / "ws", "init")
        for repo in ("api", "web"):
            self.assertTrue(
                (self.root / "ws" / repo / "ARCHITECTURE.md").exists(), repo
            )
        self.assertTrue((self.root / "ws" / "PROJECT.md").exists())

    def test_retrofit_is_additive(self):
        git_init(self.root / "r")
        r = self.root / "r"
        (r / "ARCHITECTURE.md").write_text(
            "# Old\n\n## Overview\nOur real overview.\n", encoding="utf-8"
        )
        ca(r, "init", "--retrofit")
        t = (r / "ARCHITECTURE.md").read_text(encoding="utf-8")
        self.assertIn("Our real overview.", t)
        self.assertIn("## Data flow", t)
        self.assertEqual(t.count("## Overview"), 1)
        self.assertIn(
            "GW002",
            [f["id"] for f in json.loads(ca(r, "check", "--json").stdout)["findings"]],
        )

    def test_discovery_records_evidence_and_only_preexisting_docs(self):
        r = self.root / "r"
        git_init(r)
        (r / "src").mkdir()
        (r / "src" / "main.py").write_text("print(1)\n", encoding="utf-8")
        (r / "package.json").write_text(
            '{"name":"demo","scripts":{"test":"jest"},"dependencies":{"express":"4"}}',
            encoding="utf-8",
        )
        (r / "README.md").write_text("# Demo\nA demo.\n", encoding="utf-8")
        (r / "docs" / "adr").mkdir(parents=True)
        (r / "tests").mkdir()
        (r / "tests" / "test_a.py").write_text("", encoding="utf-8")
        (r / ".github" / "workflows").mkdir(parents=True)
        (r / ".github" / "workflows" / "ci.yml").write_text(
            "on: push", encoding="utf-8"
        )
        subprocess.run(["git", "-C", str(r), "add", "-A"], env=G, check=True)
        subprocess.run(["git", "-C", str(r), "commit", "-qm", "x"], env=G, check=True)
        ca(r, "init")
        d = json.loads(
            (r / ".groundwork" / "discovery.json").read_text(encoding="utf-8")
        )
        self.assertIn("Python", d["languages"])
        self.assertEqual(d["manifests"]["package.json"]["scripts"], ["test"])
        self.assertIn("src/main.py", d["entry_points"])
        self.assertEqual(d["adoptable"]["adr_dir"], "docs/adr")
        self.assertIn(".github/workflows/ci.yml", d["infrastructure"])
        self.assertEqual(d["git"]["top_authors"][0]["name"], "Ann")
        self.assertIn("README.md", d["existing_docs"])
        self.assertNotIn(
            "PROJECT.md", d["existing_docs"]
        )  # created by init, not pre-existing
        self.assertEqual(d["adoptable"]["agent_instructions"], [])
        self.assertIn(
            "discovery.json",
            (r / ".groundwork" / ".gitignore").read_text(encoding="utf-8"),
        )


class Doctor(CheckBase):
    def test_conforming_but_unguarded_is_stage_3_then_hook_makes_4(self):
        d = doctor(self.ws)
        self.assertEqual(d["stage"], 3, d)
        self.assertTrue(
            any("no git hook" in i["label"] for i in d["items"]) or d["repos"]
        )
        ca(self.ws, "hooks", "install")
        self.assertGreaterEqual(doctor(self.api)["stage"], 4)

    def test_process_in_use_reaches_stage_5(self):
        ca(self.api, "hooks", "install")
        self.assertEqual(doctor(self.api)["stage"], 5)  # approved RFC + a feature exist

    def test_fresh_scaffold_stage_and_next_steps(self):
        git_init(self.root / "n")
        ca(self.root / "n", "scaffold")
        d = doctor(self.root / "n")
        self.assertEqual((d["stage"], d["stage_name"]), (1, "Scaffolded"))
        self.assertTrue(any("bootstrap" in s for s in d["next_steps"]))

    def test_empty_project_is_stage_0(self):
        git_init(self.root / "n")
        d = doctor(self.root / "n")
        self.assertEqual(d["stage"], 0)
        self.assertTrue(any("init" in s for s in d["next_steps"]))

    def test_unknown_dir(self):
        d = doctor(self.root)
        self.assertEqual(d["stage"], 0)
        self.assertTrue(any("--as repo" in s for s in d["next_steps"]))

    def test_workspace_rolls_up_weakest_repo(self):
        git_init(self.ws / "web")  # a repo with nothing
        d = doctor(self.ws)
        self.assertEqual(d["stage"], 0)
        names = {r["name"]: r["stage"] for r in d["repos"]}
        self.assertEqual(names["web"], 0)
        self.assertGreaterEqual(names["api"], 3)
        self.assertTrue(any(s.startswith("[web]") for s in d["next_steps"]))

    def test_stale_docs_hold_stage_at_2(self):
        (self.api / "package.json").write_text("{}", encoding="utf-8")
        self.assertEqual(doctor(self.api)["stage"], 2)

    def test_text_report_renders(self):
        out = ca(self.api, "doctor").stdout
        self.assertIn("Stage", out)
        self.assertIn("Foundation", out)
        self.assertEqual(ca(self.api, "doctor").returncode, 0)

    def test_enforcement_off_is_flagged(self):
        (self.api / ".groundwork" / "config.json").write_text(
            '{"standard":"0.5.0","enforcement":"off"}', encoding="utf-8"
        )
        self.assertTrue(
            any("enforcement: off" in i["label"] for i in doctor(self.api)["items"])
        )


if __name__ == "__main__":
    unittest.main()


class UvPolicy(Base):
    def test_rule_is_injected_at_session_start(self):
        from test_flow import hook

        ctx = hook(self.root, "session-context", {})["additionalContext"]
        self.assertIn("ALWAYS use `uv`, never pip", ctx)
        self.assertIn("uv add", ctx)

    def test_templates_carry_the_rule(self):
        t = Path(__file__).resolve().parents[1] / "templates"
        for f in ("AGENTS.repo.md", "AGENTS.workspace.md"):
            self.assertIn("uv", (t / f).read_text(encoding="utf-8"))
            self.assertNotIn("pip install <", (t / f).read_text(encoding="utf-8"))

    def test_skills_carry_the_rule(self):
        s = Path(__file__).resolve().parents[1] / "skills"
        for n in ("bootstrap", "implement"):
            self.assertIn("uv", (s / n / "SKILL.md").read_text(encoding="utf-8"))

    def test_discovery_flags_other_python_managers(self):
        r = self.root / "r"
        git_init(r)
        (r / "app.py").write_text("print(1)\n", encoding="utf-8")
        (r / "requirements.txt").write_text("flask\n", encoding="utf-8")
        (r / "poetry.lock").write_text("", encoding="utf-8")
        ca(r, "init")
        py = json.loads(
            (r / ".groundwork" / "discovery.json").read_text(encoding="utf-8")
        )["python"]
        self.assertEqual(
            (py["present"], py["uses_uv"], py["other_managers"]),
            (True, False, ["pip", "poetry"]),
        )
        (r / "uv.lock").write_text("", encoding="utf-8")
        ca(r, "init")
        self.assertTrue(
            json.loads(
                (r / ".groundwork" / "discovery.json").read_text(encoding="utf-8")
            )["python"]["uses_uv"]
        )

    def test_non_python_project_has_no_python_noise(self):
        r = self.root / "js"
        git_init(r)
        (r / "index.js").write_text("1", encoding="utf-8")
        ca(r, "init")
        self.assertFalse(
            json.loads(
                (r / ".groundwork" / "discovery.json").read_text(encoding="utf-8")
            )["python"]["present"]
        )
