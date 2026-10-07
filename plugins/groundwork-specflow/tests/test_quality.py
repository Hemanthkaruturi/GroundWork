"""Code quality (STANDARD.md §5i): one recorded toolchain per repo, run by `verify`, the same for every agent."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import check
from test_flow import Base, ca, git_init, hook

PY = f'"{sys.executable}"'


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def rules(cwd, *ids):
    _, _, items = check(cwd)
    return [f for f in items if f["id"] in ids]


class Decision(Base):
    def setUp(self):
        super().setUp()
        self.repo = self.root / "repo"
        git_init(self.repo)

    def cfg(self):
        return json.loads(
            (self.repo / ".groundwork" / "config.json").read_text(encoding="utf-8")
        )["quality"]

    def context(self):
        return hook(self.repo, "session-context", {})["additionalContext"]

    def test_undecided_repo_with_code_is_asked_and_not_checked(self):
        write(self.repo, "app/a.py", "x = 1\n")
        ca(self.repo, "init")
        self.assertEqual(rules(self.repo, "GW120", "GW121", "GW122", "GW123"), [])
        self.assertIn("QUALITY NOT DECIDED", self.context())
        self.assertIn("ask the user whether to adopt", ca(self.repo, "quality").stdout)

    def test_keep_records_existing_commands_and_touches_no_config(self):
        write(self.repo, "app/a.py", "x = 1\n")
        write(self.repo, "Makefile", "lint:\n\tflake8\ntest:\n\tpytest\n")
        ca(self.repo, "init")
        before = sorted(p.name for p in self.repo.iterdir())
        r = ca(self.repo, "quality", "keep")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            self.cfg()["commands"], {"lint": ["make lint"], "test": ["make test"]}
        )
        self.assertEqual(
            sorted(p.name for p in self.repo.iterdir()), before
        )  # no tool config added
        agents = (self.repo / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(agents.count("## Code quality"), 1)
        self.assertIn("- lint: `make lint`", agents)
        self.assertIn("Reuse before writing", agents)
        self.assertIn("own tools, kept by choice", self.context())
        again = ca(self.repo, "quality", "init")
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("--force", again.stderr)

    def test_standard_writes_configs_without_overwriting(self):
        write(self.repo, "src/a.py", "x = 1\n")
        write(self.repo, "src/b.ts", "export const b = 1\n")
        write(
            self.repo,
            "pyproject.toml",
            '[project]\nname = "a"\n\n[tool.ruff]\nline-length = 88\n',
        )
        ca(self.repo, "init")
        r = ca(self.repo, "quality", "init", "--create")
        self.assertEqual(r.returncode, 0, r.stderr)
        for made in (
            "mypy.ini",
            "eslint.config.mjs",
            ".prettierrc.json",
            ".editorconfig",
        ):
            self.assertTrue((self.repo / made).is_file(), made)
        self.assertFalse(
            (self.repo / "ruff.toml").exists()
        )  # [tool.ruff] already there
        self.assertIn("uv add --dev ruff mypy pytest", r.stdout)
        shown = ca(self.repo, "quality").stdout
        for cmd in (
            "uv run ruff check .",
            "npx eslint .",
            "npx tsc --noEmit",
            "uv run pytest",
        ):
            self.assertIn(cmd, shown)
        self.assertEqual(rules(self.repo, "GW121", "GW122"), [])

    def test_standard_commands_follow_the_languages_present(self):
        ca(self.repo, "init")
        ca(self.repo, "quality", "init")
        self.assertNotIn("go test", ca(self.repo, "quality").stdout)
        write(self.repo, "go.mod", "module example.com/x\n")
        write(self.repo, "main.go", "package main\n")
        self.assertIn("go test ./...", ca(self.repo, "quality").stdout)
        self.assertEqual(
            [f["message"] for f in rules(self.repo, "GW121")],
            ["go code has no config for its standard tools"],
        )

    def test_invalid_entry_is_an_error(self):
        write(
            self.repo,
            ".groundwork/config.json",
            json.dumps({"quality": {"mode": "lax", "commands": {"style": "x"}}}),
        )
        found = rules(self.repo, "GW120")
        self.assertEqual(len(found), 2)
        self.assertEqual({f["severity"] for f in found}, {"error"})


class Verify(Base):
    def setUp(self):
        super().setUp()
        self.repo = self.root / "repo"
        git_init(self.repo)
        write(self.repo, "app/a.py", "x = 1\n")
        ca(self.repo, "init")
        ca(self.repo, "quality", "keep")

    def test_verify_runs_each_step_and_fails_on_any_failure(self):
        r = ca(
            self.repo,
            "quality",
            "set",
            f'lint={PY} -c "print(1)"',
            f"test={PY} -c \"import sys; print('2 tests failed'); sys.exit(3)\"",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        v = ca(self.repo, "verify")
        self.assertEqual(v.returncode, 1)
        self.assertIn("PASS  lint", v.stdout)
        self.assertIn("FAIL  test", v.stdout)
        self.assertIn("2 tests failed", v.stdout)  # the failure's output is shown
        self.assertEqual(ca(self.repo, "verify", "--step", "lint").returncode, 0)

    def test_fix_commands_run_first(self):
        ca(
            self.repo,
            "quality",
            "set",
            f"format={PY} -c \"import pathlib,sys; sys.exit(0 if pathlib.Path('fixed').exists() else 1)\"",
            f'lint={PY} -c "print(1)"',
            f'test={PY} -c "print(1)"',
        )
        r = ca(
            self.repo,
            "quality",
            "set",
            f"format={PY} -c \"import pathlib; pathlib.Path('fixed').touch()\"",
            "--fix",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(ca(self.repo, "verify").returncode, 1)
        self.assertEqual(ca(self.repo, "verify", "--fix").returncode, 0)

    def test_missing_required_steps_are_reported(self):
        ca(self.repo, "quality", "set", "test=")
        msgs = [f["message"] for f in rules(self.repo, "GW122")]
        self.assertEqual(
            sorted(msgs),
            [
                'no "lint" command recorded, so verify cannot check it',
                'no "test" command recorded, so verify cannot check it',
            ],
        )


class FileSize(Base):
    def test_long_files_warn_only_on_the_standard_toolchain(self):
        repo = self.root / "repo"
        git_init(repo)
        write(repo, "src/big.py", "x = 1\n" * 450)
        write(repo, "tests/test_big.py", "x = 1\n" * 450)
        ca(repo, "init")
        ca(repo, "quality", "keep")
        self.assertEqual(rules(repo, "GW123"), [])
        ca(repo, "quality", "init", "--force")
        self.assertEqual(
            [f["path"] for f in rules(repo, "GW123")], ["src/big.py"]
        )  # tests exempt
        cfg = json.loads(
            (repo / ".groundwork" / "config.json").read_text(encoding="utf-8")
        )
        cfg["quality"]["max_file_lines"] = 500
        write(repo, ".groundwork/config.json", json.dumps(cfg))
        self.assertEqual(rules(repo, "GW123"), [])


if __name__ == "__main__":
    unittest.main()
