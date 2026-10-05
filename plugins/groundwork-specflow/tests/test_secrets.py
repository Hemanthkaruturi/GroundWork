"""Credentials (STANDARD.md §5h): secrets come from the environment; `.env` stays out of git; no keys in files."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import check  # noqa: E402
from test_flow import ENV, Base, ca, git_init  # noqa: E402

# Built at run time so this repository never contains a real-looking key.
FAKE_ANTHROPIC = "sk-" + "ant-" + "api03" + "x" * 40
FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def findings(cwd, *rules):
    code, _, items = check(cwd)
    return code, [f for f in items if f["id"] in rules]


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=ENV)


class Safety(Base):
    def setUp(self):
        super().setUp()
        self.repo = self.root / "repo"
        git_init(self.repo)

    def test_init_ignores_env_but_keeps_the_example_committable(self):
        write(self.repo, ".gitignore", "node_modules/\n")
        self.assertEqual([f["id"] for f in findings(self.repo, "GW110")[1]], ["GW110"])
        r = ca(self.repo, "init")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(".gitignore entry for .env", r.stdout)
        gi = (self.repo / ".gitignore").read_text(encoding="utf-8")
        self.assertTrue(gi.startswith("node_modules/\n"))                  # the user's lines are kept
        self.assertEqual(git(self.repo, "check-ignore", "-q", ".env").returncode, 0)
        self.assertEqual(git(self.repo, "check-ignore", "-q", ".env.local").returncode, 0)
        self.assertEqual(git(self.repo, "check-ignore", "-q", ".env.example").returncode, 1)
        self.assertEqual(findings(self.repo, "GW110")[1], [])
        ca(self.repo, "init")
        self.assertEqual((self.repo / ".gitignore").read_text(encoding="utf-8"), gi)   # idempotent

    def test_a_committed_env_file_is_an_error_and_its_value_is_never_shown(self):
        ca(self.repo, "init")
        write(self.repo, ".env", f"ANTHROPIC_API_KEY={FAKE_ANTHROPIC}\n")
        self.assertEqual(findings(self.repo, "GW111", "GW113")[1], [])     # ignored and never opened: fine
        git(self.repo, "add", "-f", ".env")
        r = ca(self.repo, "check", "--json")
        found = [f for f in json.loads(r.stdout)["findings"] if f["id"] == "GW111"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["severity"], "error")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn(FAKE_ANTHROPIC, r.stdout)

    def test_pasted_keys_are_reported_by_file_and_line_only(self):
        ca(self.repo, "init")
        write(self.repo, "src/client.py", f"import anthropic\n\nKEY = '{FAKE_ANTHROPIC}'\n")
        write(self.repo, "deploy/settings.yaml", f"aws:\n  key: {FAKE_AWS}\n")
        write(self.repo, "notes/ignored.txt", f"{FAKE_AWS}\n")
        write(self.repo, ".gitignore", (self.repo / ".gitignore").read_text(encoding="utf-8") + "notes/\n")
        r = ca(self.repo, "check", "--json")
        got = {(f["path"], f["message"]) for f in json.loads(r.stdout)["findings"] if f["id"] == "GW113"}
        self.assertEqual(got, {("src/client.py", "line 3: looks like an Anthropic API key written into the file"),
                               ("deploy/settings.yaml", "line 2: looks like an AWS access key id written into the file")})
        self.assertNotIn(FAKE_ANTHROPIC, r.stdout)
        self.assertNotIn(FAKE_AWS, r.stdout)

    def test_keep_repos_get_only_the_safety_rules(self):
        ca(self.repo, "init")
        ca(self.repo, "layout", "keep")
        write(self.repo, "app/settings.py", "import os\nDB = os.environ['DATABASE_URL']\n")
        write(self.repo, "app/llm.py", f"TOKEN = '{FAKE_ANTHROPIC}'\n")
        ids = {f["id"] for f in findings(self.repo, "GW110", "GW111", "GW112", "GW113", "GW114")[1]}
        self.assertEqual(ids, {"GW113"})                                  # no .env.example demanded of its pattern


class StandardRepos(Base):
    def setUp(self):
        super().setUp()
        self.repo = self.root / "repo"
        git_init(self.repo)
        ca(self.repo, "init")

    def test_env_example_lists_every_variable_the_code_reads(self):
        write(self.repo, "src/config/settings.py",
              "import os\nfrom dotenv import load_dotenv\nload_dotenv()\nDB = os.environ['DATABASE_URL']\nKEY = os.getenv('LLM_API_KEY')\n")
        r = ca(self.repo, "layout", "init", "--profile", "service", "--root", "src", "--create")
        self.assertEqual(r.returncode, 0, r.stderr)
        example = (self.repo / ".env.example").read_text(encoding="utf-8")
        self.assertIn("DATABASE_URL=\n", example)
        self.assertIn("LLM_API_KEY=\n", example)
        self.assertEqual(findings(self.repo, "GW112", "GW105")[1], [])    # dotenv loaded in config/: allowed
        write(self.repo, "src/config/mail.py", "import os\nSMTP = os.getenv('SMTP_PASSWORD')\n")
        msgs = [f["message"] for f in findings(self.repo, "GW112")[1]]
        self.assertEqual(len(msgs), 1)
        self.assertIn("SMTP_PASSWORD", msgs[0])
        write(self.repo, "src/core/orders.py", "from dotenv import load_dotenv\nload_dotenv()\n")
        self.assertEqual([f["path"] for f in findings(self.repo, "GW105")[1]], ["src/core/orders.py"])

    def test_front_ends_hold_no_secrets(self):
        write(self.repo, "package.json", '{"dependencies": {"react": "18"}}')
        ca(self.repo, "layout", "init", "--profile", "web", "--root", "src", "--create")
        write(self.repo, "src/config/env.ts",
              "export const pk = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY\nexport const s = import.meta.env.VITE_API_SECRET\n")
        write(self.repo, "src/core/boot.ts", "import 'dotenv/config'\n")
        got = [(f["id"], f["path"]) for f in findings(self.repo, "GW114", "GW105")[1]]
        self.assertEqual(sorted(got), [("GW105", "src/core/boot.ts"), ("GW114", "src/config/env.ts")])

    def test_code_map_states_where_secrets_come_from(self):
        ca(self.repo, "codemap")
        self.assertIn("Secrets: read from environment variables; locally from `.env` (git-ignored)",
                      (self.repo / "CODEMAP.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
