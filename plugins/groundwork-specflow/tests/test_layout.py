"""Code layout (STANDARD.md §5f): one decision per repo — standard role folders, or keep the repo's own structure."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import CheckBase, check
from test_flow import Base, ca, git_init, hook


def layout_ids(cwd):
    _, _, findings = check(cwd)
    findings = [
        f
        for f in findings
        if f["id"].startswith("GW10") and f["id"] not in ("GW108", "GW109")
    ]
    return {f["id"] for f in findings}, findings


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def context(cwd):
    return hook(cwd, "session-context", {})["additionalContext"]


class Decision(Base):
    def setUp(self):
        super().setUp()
        self.repo = self.root / "repo"
        git_init(self.repo)

    def cfg(self):
        return json.loads(
            (self.repo / ".groundwork" / "config.json").read_text(encoding="utf-8")
        )["layout"]

    def test_existing_code_without_a_decision_asks_and_is_not_checked(self):
        write(
            self.repo, "lib/orders.py", "import requests\nimport os\nos.environ['X']\n"
        )
        self.assertEqual(layout_ids(self.repo)[0], set())  # undecided: nothing imposed
        self.assertIn("CODE LAYOUT NOT DECIDED", context(self.repo))
        self.assertIn("migrate", context(self.repo))
        shown = ca(self.repo, "layout").stdout
        self.assertIn("ask the user whether to migrate", shown)
        self.assertIn("groundwork.py layout keep", shown)

    def test_keep_records_the_choice_moves_nothing_and_checks_nothing(self):
        write(
            self.repo,
            "lib/utils/orders.py",
            "import requests\nimport os\nos.getenv('X')\n",
        )
        r = ca(self.repo, "layout", "keep")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cfg()["mode"], "keep")
        self.assertFalse((self.repo / "core").exists())
        self.assertEqual(layout_ids(self.repo)[0], set())
        ctx = context(self.repo)
        self.assertIn("KEEPS ITS OWN STRUCTURE", ctx)
        self.assertIn("copy its patterns", ctx)
        again = ca(self.repo, "layout", "init", "--profile", "service")
        self.assertNotEqual(
            again.returncode, 0
        )  # a recorded decision is not silently changed
        self.assertIn("--force", again.stderr)
        self.assertEqual(self.cfg()["mode"], "keep")

    def test_init_create_makes_the_folders_with_readmes(self):
        r = ca(
            self.repo,
            "layout",
            "init",
            "--profile",
            "service",
            "--root",
            "src/shop",
            "--create",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        for layer in ("core", "connectors", "entrypoints", "config", "prompts"):
            self.assertTrue(
                (self.repo / "src/shop" / layer / "README.md").is_file(), layer
            )
        self.assertEqual(self.cfg()["profile"], "service")
        self.assertEqual(layout_ids(self.repo)[0], set())
        self.assertIn(
            "CODE LAYOUT (service profile, root src/shop)", context(self.repo)
        )

    def test_invalid_layout_is_an_error(self):
        write(
            self.repo,
            ".groundwork/config.json",
            json.dumps({"layout": {"mode": "standard", "profile": "spaceship"}}),
        )
        ids, findings = layout_ids(self.repo)
        self.assertIn("GW100", ids)
        self.assertEqual(
            next(f for f in findings if f["id"] == "GW100")["severity"], "error"
        )
        write(
            self.repo,
            ".groundwork/config.json",
            json.dumps(
                {"layout": {"mode": "standard", "profile": "service", "root": "../x"}}
            ),
        )
        self.assertIn("GW100", layout_ids(self.repo)[0])


class StandardRules(Base):
    def setUp(self):
        super().setUp()
        self.repo = self.root / "repo"
        git_init(self.repo)

    def init(self, profile, root, *extra):
        r = ca(
            self.repo,
            "layout",
            "init",
            "--profile",
            profile,
            "--root",
            root,
            "--create",
            *extra,
        )
        self.assertEqual(r.returncode, 0, r.stderr)

    def messages(self, rule):
        return [
            f["path"] + " " + f["message"]
            for f in layout_ids(self.repo)[1]
            if f["id"] == rule
        ]

    def test_python_service(self):
        self.init("service", "src/shop")
        write(self.repo, "src/shop/__init__.py", "")
        write(
            self.repo,
            "src/shop/core/orders.py",
            "import os\nfrom shop.connectors.database import Store\nfrom ..connectors.llm import ask\nimport openai\n"
            "# os.environ in a comment is fine\n",
        )
        write(self.repo, "src/shop/core/pricing.py", "TOKEN = os.environ['T']\n")
        write(self.repo, "src/shop/connectors/claude.py", "import anthropic\n")
        write(
            self.repo,
            "src/shop/connectors/llm/anthropic.py",
            "import anthropic\nfrom shop.core import orders\n",
        )
        write(
            self.repo,
            "src/shop/config/settings.py",
            "import os\nKEY = os.getenv('KEY')\n",
        )
        write(
            self.repo,
            "src/shop/entrypoints/http/routes.py",
            "from shop.core.orders import x\n",
        )
        write(
            self.repo,
            "src/shop/app.py",
            "import os\nimport anthropic\nfrom shop.connectors.llm.anthropic import C\n",
        )
        write(self.repo, "src/shop/helpers/strings.py", "x = 1\n")
        write(self.repo, "src/shop/services/legacy.py", "import requests\n")
        write(
            self.repo,
            "tests/test_orders.py",
            "import requests\nimport os\nos.environ\n",
        )
        self.assertEqual(
            len(self.messages("GW102")), 1
        )  # core → connectors (once per target role)
        self.assertIn("src/shop/core/orders.py", self.messages("GW102")[0])
        self.assertEqual(
            [m.split()[0] for m in self.messages("GW103")], ["src/shop/core/orders.py"]
        )
        self.assertEqual(
            [m.split()[0] for m in self.messages("GW105")], ["src/shop/core/pricing.py"]
        )
        self.assertEqual(
            [m.split()[0] for m in self.messages("GW106")], ["src/shop/helpers"]
        )
        self.assertEqual(
            [m.split()[0] for m in self.messages("GW107")],
            ["src/shop/connectors/claude.py"],
        )
        self.assertEqual(
            sorted(m.split()[0] for m in self.messages("GW104")),
            ["src/shop/helpers", "src/shop/services"],
        )

    def test_mapping_and_legacy_adopt_an_existing_repo(self):
        write(self.repo, "src/shop/clients/llm/openai_client.py", "import openai\n")
        write(
            self.repo,
            "src/shop/old/everything.py",
            "import requests\nimport os\nos.environ\n",
        )
        write(self.repo, "src/shop/__init__.py", "")
        self.init("service", "src/shop")
        self.assertIn("GW104", layout_ids(self.repo)[0])
        r = ca(
            self.repo,
            "layout",
            "map",
            "connectors=src/shop/clients",
            "--legacy",
            "src/shop/old",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(layout_ids(self.repo)[0], set())
        write(
            self.repo,
            "src/shop/core/orders.py",
            "from shop.clients.llm.openai_client import x\n",
        )
        self.assertEqual(
            len(self.messages("GW102")), 1
        )  # a mapped folder carries its role's rules

    def test_web_profile(self):
        write(self.repo, "package.json", '{"dependencies": {"react": "18"}}')
        self.init("web", "src")
        write(
            self.repo,
            "src/components/Card.tsx",
            "import { api } from '../connectors/api/client'\nimport axios from \"axios\"\n"
            "const k = process.env.KEY\nexport const C = () => fetch('/x')\n",
        )
        write(
            self.repo,
            "src/connectors/api/client.ts",
            "export const api = () => fetch('/a')\n",
        )
        write(
            self.repo,
            "src/core/cart.ts",
            "import { api } from '@/connectors/api/client'\n",
        )
        write(
            self.repo,
            "src/pages/Home.tsx",
            "import { Card } from '../components/Card'\nimport { cart } from '@/core/cart'\n",
        )
        write(
            self.repo,
            "src/components/Card.test.tsx",
            "import axios from 'axios'\nfetch('/x')\n",
        )
        _ids, findings = layout_ids(self.repo)
        bad = {(f["id"], f["path"]) for f in findings}
        self.assertEqual(
            bad,
            {
                ("GW102", "src/components/Card.tsx"),
                ("GW103", "src/components/Card.tsx"),
                ("GW105", "src/components/Card.tsx"),
            },
        )

    def test_go_and_library(self):
        write(self.repo, "go.mod", "module example.com/svc\n")
        self.init("service", "internal")
        write(
            self.repo,
            "internal/core/x.go",
            'package core\nimport (\n  "fmt"\n  db "example.com/svc/internal/connectors/database"\n)\n',
        )
        write(
            self.repo,
            "cmd/svc/main.go",
            'package main\nimport "example.com/svc/internal/connectors/database"\nvar _ = os.Getenv("X")\n',
        )
        self.assertEqual(
            [m.split()[0] for m in self.messages("GW102")], ["internal/core/x.go"]
        )
        self.assertEqual(self.messages("GW105"), [])  # wiring may read settings
        lib = self.root / "lib"
        git_init(lib)
        r = ca(
            lib, "layout", "init", "--profile", "library", "--root", "mylib", "--create"
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        write(lib, "mylib/core/client.py", "import os\nos.getenv('X')\n")
        _, _, findings = check(lib)
        self.assertIn("GW105", {f["id"] for f in findings})

    def test_missing_required_folder(self):
        r = ca(self.repo, "layout", "init", "--profile", "service", "--root", "src")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("GW101", layout_ids(self.repo)[0])


class CodeMap(Base):
    """Every repo gets CODEMAP.md, whatever its layout decision; it is generated from the code and kept current."""

    def setUp(self):
        super().setUp()
        self.repo = self.root / "repo"
        git_init(self.repo)
        write(self.repo, "lib/billing/invoice.py", "import stripe\n")
        write(self.repo, "lib/store/db.py", "import psycopg\n")
        write(self.repo, "lib/settings.py", "import os\nKEY = os.getenv('KEY')\n")
        write(self.repo, "main.py", "from lib.billing import invoice\n")
        write(self.repo, "tests/test_invoice.py", "import requests\n")

    def ids(self):
        return {f["id"] for f in check(self.repo)[2]}

    def text(self):
        return (self.repo / "CODEMAP.md").read_text(encoding="utf-8")

    def test_init_writes_the_map_even_without_a_layout_decision(self):
        r = ca(self.repo, "init")
        self.assertEqual(r.returncode, 0, r.stderr)
        t = self.text()
        for fact in (
            "`lib/billing`",
            "`lib/store`",
            "| payments | stripe | `lib/billing/invoice.py` |",
            "| database | psycopg |",
            "- `lib/settings.py`",
            "- `main.py`",
            "- `tests` (1 files)",
            "**Layout:** not decided",
        ):
            self.assertIn(fact, t)
        self.assertIn("GW108", self.ids())  # Holds column still to describe
        self.assertIn("CODEMAP.md", context(self.repo))

    def test_descriptions_survive_regeneration_and_changes_age_the_map(self):
        ca(self.repo, "layout", "keep")
        self.assertIn("**Layout:** keep (own structure)", self.text())
        filled = self.text().replace(
            "| `lib/billing` | — | 1 | [TODO: what this folder holds] |",
            "| `lib/billing` | — | 1 | billing rules |",
        )
        filled = filled.replace(
            "_Conventions an agent should know about this structure (optional)._",
            "Money is in cents.",
        )
        (self.repo / "CODEMAP.md").write_text(filled, encoding="utf-8")
        rest = self.text().replace("[TODO: what this folder holds]", "described")
        (self.repo / "CODEMAP.md").write_text(rest, encoding="utf-8")
        self.assertFalse({"GW108", "GW109"} & self.ids())
        write(
            self.repo, "lib/billing/refund.py", "x = 1\n"
        )  # a file in a known folder: still current
        self.assertFalse({"GW108", "GW109"} & self.ids())
        write(
            self.repo, "lib/email/send.py", "import smtplib\n"
        )  # a new folder and outside call: outdated
        self.assertIn("GW109", self.ids())
        self.assertEqual(ca(self.repo, "codemap", "--check").returncode, 1)
        ca(self.repo, "codemap")
        t = self.text()
        self.assertIn("| `lib/billing` | — | 2 | billing rules |", t)
        self.assertIn("Money is in cents.", t)
        self.assertIn("`lib/email`", t)
        self.assertIn("GW108", self.ids())  # only the new folder needs describing
        self.assertNotIn("GW109", self.ids())

    def test_standard_layout_fills_roles(self):
        ca(
            self.repo,
            "layout",
            "init",
            "--profile",
            "service",
            "--root",
            "lib",
            "--create",
        )
        t = self.text()
        self.assertIn("**Layout:** standard (service profile, root lib)", t)
        self.assertIn("| `lib/billing` | no role |", t)
        self.assertIn("- `tests` (1 files)", t)  # outside the code root, still mapped

    def test_missing_map_is_reported(self):
        self.assertIn("GW108", self.ids())

    def test_session_start_shows_the_map_in_brief(self):
        ca(self.repo, "init")
        filled = self.text().replace(
            "| `lib/billing` | — | 1 | [TODO: what this folder holds] |",
            "| `lib/billing` | — | 1 | invoices and refunds |",
        )
        (self.repo / "CODEMAP.md").write_text(filled, encoding="utf-8")
        ctx = context(self.repo)
        self.assertIn("  - `lib/billing`: invoices and refunds", ctx)
        self.assertIn("  - `lib/store`: (not described yet)", ctx)
        self.assertIn("  - payments via stripe: `lib/billing/invoice.py`", ctx)
        self.assertIn("  - database via psycopg:", ctx)

    def test_starting_work_writes_a_missing_map(self):
        self.assertFalse((self.repo / "CODEMAP.md").exists())
        r = ca(self.repo, "new-bug", "oops", "--title", "Oops")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("code map → CODEMAP.md", r.stdout)
        self.assertTrue((self.repo / "CODEMAP.md").exists())
        self.assertIn("`lib/billing`", self.text())
        # an existing map is left alone
        (self.repo / "CODEMAP.md").write_text("# mine\n", encoding="utf-8")
        r = ca(self.repo, "new-bug", "again", "--title", "Again")
        self.assertNotIn("code map →", r.stdout)
        self.assertEqual(self.text(), "# mine\n")


class Strictness(CheckBase):
    """Layout findings are warnings: they fail `check` only under --strict."""

    def test_warnings_fail_only_under_strict(self):
        r = ca(
            self.api,
            "layout",
            "init",
            "--profile",
            "service",
            "--root",
            "src",
            "--create",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        ca(self.api, "confirm")
        write(self.api, "src/core/orders.py", "import requests\n")
        code, ids, _ = check(self.ws)
        self.assertIn("GW103", ids)
        self.assertEqual(code, 0)
        code, _, _ = check(self.ws, "--strict")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
