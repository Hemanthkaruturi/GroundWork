"""End-to-end tests: drive groundwork.py exactly as the hooks and slash commands do."""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CA = Path(__file__).resolve().parents[1] / "engine" / "groundwork.py"
ENV = {
    **os.environ,
    "HOME": "/nonexistent-home",
    "USERPROFILE": "/nonexistent-home",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
}
ENV.pop("GROUNDWORK_ENFORCEMENT", None)
for _k in (
    "GROUNDWORK_HOST",
    "DEVIN_PROJECT_DIR",
    "DEVIN_PLUGIN_ROOT",
    "CLAUDE_PROJECT_DIR",
    "PLUGIN_ROOT",
):  # tests pick the harness themselves
    ENV.pop(_k, None)


def ca(cwd, *args, stdin=None):
    return subprocess.run(
        [sys.executable, str(CA), *args],
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=ENV,
        check=False,
    )


def git_init(p):
    Path(p).mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(p)], check=True, env=ENV)


def hook(cwd, event_cmd, tool_input):
    r = ca(
        cwd, event_cmd, stdin=json.dumps({"cwd": str(cwd), "tool_input": tool_input})
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None


SESSION_HOOKS = ("session-context", "session-rules-1", "session-rules-2")


def session(cwd):
    """Everything the SessionStart hooks tell the agent, in hooks.json order."""
    return "\n\n".join(hook(cwd, h, {})["additionalContext"] for h in SESSION_HOOKS)


def denied(cwd, path):
    o = hook(cwd, "gate", {"file_path": str(path)})
    return bool(o and o.get("permissionDecision") == "deny"), (o or {}).get(
        "permissionDecisionReason", ""
    )


def fill(path):
    """Simulate the agent finishing a document: strip every unresolved marker."""
    t = Path(path).read_text(encoding="utf-8")
    Path(path).write_text(
        re.sub(r"\[(TODO|NEEDS CLARIFICATION)[^\]]*\]", "filled", t), encoding="utf-8"
    )


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()


class ConstitutionAwareness(Base):
    """The guardrails themselves reach the agent at every session start, from the repo and the workspace."""

    def test_guardrails_shown_from_repo_and_workspace(self):
        ws, api = self.root / "ws", self.root / "ws" / "api"
        git_init(api)
        (ws / "PROJECT.md").write_text(
            "# marker", encoding="utf-8"
        )  # makes ws a workspace
        (ws / "CONSTITUTION.md").write_text(
            "# C\n\n## Principles\n1. x\n\n## Guardrails (things that must never happen)\n"
            "- No secrets, keys or provider credentials in any repository.\n"
            "- [TODO: an unfinished rule]\n\n## Quality gates\n- tests pass\n\n## Amendments\n_None._\n",
            encoding="utf-8",
        )
        (api / "CONSTITUTION.md").write_text(
            "# C\n\n## Guardrails\n* Card numbers are never stored or logged.\n\n## Quality gates\n- x\n",
            encoding="utf-8",
        )
        ctx = session(api)
        self.assertIn("CONSTITUTION GUARDRAILS", ctx)
        self.assertIn(
            "[workspace] No secrets, keys or provider credentials in any repository.",
            ctx,
        )
        self.assertIn("[repo] Card numbers are never stored or logged.", ctx)
        self.assertNotIn("unfinished rule", ctx)
        self.assertIn("23. CONSTITUTION", ctx)

    def test_no_guardrails_no_block(self):
        git_init(self.root / "r")
        ctx = hook(self.root / "r", "session-context", {})["additionalContext"]
        self.assertNotIn("CONSTITUTION GUARDRAILS", ctx)


class EnginePath(Base):
    """${CLAUDE_PLUGIN_ROOT} is not set in the agent's shell, so the agent is told the literal engine path."""

    ENGINE = CA.as_posix()

    def setUp(self):
        super().setUp()
        git_init(self.root / "r")
        self.repo = self.root / "r"

    def test_session_rules_carry_the_quoted_literal_path(self):
        ctx = session(self.repo)
        self.assertIn(f"`${{CLAUDE_PLUGIN_ROOT}}` ({CA.parents[1].as_posix()}) is not set", ctx)
        self.assertIn(f'python3 "{self.ENGINE}" status', ctx)
        self.assertIn(f'python3 "{self.ENGINE}" <command>', ctx)
        self.assertNotIn(f"python3 {self.ENGINE}", ctx)  # never unquoted: paths can hold spaces
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py status", ctx)

    def test_every_prompt_names_the_current_engine(self):
        rem = hook(self.repo, "prompt-reminder", {})["additionalContext"]
        self.assertIn(f'Engine: `python3 "{self.ENGINE}" <command>`', rem)

    def test_engine_note_leads_the_session_context(self):
        # Claude Code shows only the first 2,000 characters of a context over 10,000.
        ctx = hook(self.repo, "session-context", {})["additionalContext"]
        self.assertTrue(ctx.startswith("ENGINE: "))
        self.assertLess(ctx.index(f'python3 "{self.ENGINE}" <command>'), 2000)

    def test_every_session_part_fits_the_context_cap(self):
        # Over 10,000 characters Claude Code shows the model only a file path and a 2,000-character preview.
        for host in ("", "codex", "devin"):
            env = {**ENV, "GROUNDWORK_HOST": host} if host else ENV
            for h in SESSION_HOOKS:
                with self.subTest(host=host or "claude", hook=h):
                    r = subprocess.run(
                        [sys.executable, str(CA), h],
                        cwd=self.repo,
                        input=json.dumps({"cwd": str(self.repo)}),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        env=env,
                        check=True,
                    )
                    ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
                    self.assertLess(len(ctx), 10_000)

    def test_long_project_state_is_cut_to_fit(self):
        sys.path.insert(0, str(CA.parent))
        import groundwork as GW

        old = GW.describe
        GW.describe = lambda ctx: "Level: STANDALONE\n" + "IN FLIGHT: x\n" * 2000
        try:
            from unittest.mock import patch
            import io

            with patch("sys.stdin", io.StringIO(json.dumps({"cwd": str(self.repo)}))), patch(
                "sys.stdout", new_callable=io.StringIO
            ) as so:
                GW.cmd_session_context(None)
            ctx = json.loads(so.getvalue())["hookSpecificOutput"]["additionalContext"]
        finally:
            GW.describe = old
        self.assertLessEqual(len(ctx), 10_000)
        self.assertTrue(ctx.startswith("ENGINE: "))
        self.assertIn("groundwork.py status` for the rest", ctx)

    def test_session_hooks_are_registered_in_order(self):
        cfg = json.loads((CA.parents[1] / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        subs = [h["command"].split("||")[0].split()[-1] for g in cfg["hooks"]["SessionStart"] for h in g["hooks"]]
        self.assertEqual(subs, list(SESSION_HOOKS))

    def test_approve_turn_names_the_engine(self):
        r = ca(self.repo, "prompt-reminder", stdin=json.dumps({"cwd": str(self.repo), "prompt": "/approve x"}))
        self.assertEqual(r.returncode, 0, r.stderr)
        ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("[groundwork approve]", ctx)
        self.assertIn(f'Engine: `python3 "{self.ENGINE}" <command>`', ctx)

    def test_groundwork_skills_get_no_craft_tool_notice(self):
        for name in ("groundwork-specflow:refresh", "frontend-design"):
            with self.subTest(name=name):
                o = hook(self.repo, "skill-notice", {"skill": name})
                self.assertEqual(o is None, name.startswith("groundwork-specflow:"))

    def test_project_installed_skills_are_recognised_by_marker(self):
        sys.path.insert(0, str(CA.parent))
        import groundwork_host as G

        devin = self.root / "p" / ".devin"
        (devin / "skills" / "bootstrap").mkdir(parents=True)
        (devin / "skills" / "bootstrap" / G.INSTALLED_MARKER).write_text("", encoding="utf-8")
        (devin / "skills" / "mine").mkdir()
        old = G.PLUGIN_ROOT
        G.PLUGIN_ROOT = devin / "groundwork"
        try:
            self.assertTrue(G.is_groundwork_skill("bootstrap"))
            self.assertFalse(G.is_groundwork_skill("mine"))
            self.assertFalse(G.is_groundwork_skill("../skills/bootstrap"))
        finally:
            G.PLUGIN_ROOT = old

class Detection(Base):
    def level(self, p):
        o = hook(p, "session-context", {})
        return re.search(r"Level: (\w+)", o["additionalContext"]).group(1)

    def test_plain_dir_is_unknown_and_code_is_blocked(self):
        self.assertEqual(self.level(self.root), "UNKNOWN")
        d, why = denied(self.root, self.root / "app.py")
        self.assertTrue(d)
        self.assertIn("neither a git repository nor a workspace", why)

    def test_git_repo_alone_is_standalone(self):
        git_init(self.root / "r")
        self.assertEqual(self.level(self.root / "r"), "STANDALONE")

    def test_dir_holding_repos_is_workspace(self):
        git_init(self.root / "ws" / "api")
        git_init(self.root / "ws" / "web")
        self.assertEqual(self.level(self.root / "ws"), "WORKSPACE")

    def test_repo_under_project_md_is_repo_level(self):
        git_init(self.root / "ws" / "api")
        (self.root / "ws" / "PROJECT.md").write_text("# p", encoding="utf-8")
        self.assertEqual(self.level(self.root / "ws" / "api"), "REPO")

    def test_gate_agrees_with_session_workspace_before_project_md_exists(self):
        git_init(self.root / "shop" / "api")
        git_init(self.root / "shop" / "web")
        f = self.root / "shop" / "api" / "m.py"
        o = hook(self.root / "shop", "gate", {"file_path": str(f)})
        self.assertIn("workspace/PROJECT.md", o["permissionDecisionReason"])
        self.assertIn("workspace/CONTRACTS/", o["permissionDecisionReason"])

    def test_sibling_repos_without_project_md_are_not_a_workspace(self):
        git_init(self.root / "projects" / "a")
        git_init(self.root / "projects" / "b")
        self.assertEqual(self.level(self.root / "projects" / "a"), "STANDALONE")


class Unreadable(Base):
    @unittest.skipIf(
        os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
        "needs POSIX permissions and a non-root user",
    )
    def test_unreadable_folder_does_not_crash_the_gate(self):
        # editing a file in a place like /tmp, whose subfolders we cannot read, must still give an answer
        locked = self.root / "locked"
        locked.mkdir()
        (locked / "inner").mkdir()
        locked.chmod(0)
        self.addCleanup(locked.chmod, 0o700)
        r = ca(
            self.root,
            "gate",
            stdin=json.dumps(
                {
                    "cwd": str(self.root),
                    "tool_input": {"file_path": str(self.root / "app.py")},
                }
            ),
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)


class Lifecycle(Base):
    def setUp(self):
        super().setUp()
        self.ws = self.root / "ws"
        self.api = self.ws / "api"
        git_init(self.api)
        (self.ws / "PROJECT.md").write_text(
            "# ws", encoding="utf-8"
        )  # marks the workspace

    def test_full_path(self):
        code = self.api / "src" / "app.py"
        # 1. foundation missing -> blocked, and it says bootstrap
        d, why = denied(self.api, code)
        self.assertTrue(d)
        self.assertIn("foundation", why)
        # docs are always writable
        self.assertFalse(denied(self.api, self.api / "ARCHITECTURE.md")[0])

        # 2. scaffold repo + workspace foundations; unfinished ([TODO]) still blocks
        self.assertEqual(ca(self.api, "scaffold").returncode, 0)
        (self.ws / "PROJECT.md").unlink()
        self.assertEqual(ca(self.ws, "scaffold").returncode, 0)
        self.assertTrue(
            all(
                (self.ws / f).exists()
                for f in [
                    "PROJECT.md",
                    "ARCHITECTURE.md",
                    "CONSTITUTION.md",
                    "AGENTS.md",
                ]
            )
        )
        self.assertTrue(
            (self.ws / "CONTRACTS").is_dir()
            and (self.ws / "DECISIONS" / "README.md").exists()
        )
        self.assertIn("unfinished", denied(self.api, code)[1])
        for f in ["ARCHITECTURE.md", "AGENTS.md"]:
            fill(self.api / f)
        self.assertIn(
            "workspace/PROJECT.md", denied(self.api, code)[1]
        )  # repo answers for workspace too
        for f in ["PROJECT.md", "ARCHITECTURE.md", "CONSTITUTION.md", "AGENTS.md"]:
            fill(self.ws / f)
        d, why = denied(self.api, code)
        self.assertTrue(d)
        self.assertIn("no active feature", why)

        # 3. RFC in the WORKSPACE; agent cannot approve
        p = ca(
            self.ws, "new-rfc", "add-widgets", "--title", "Add widgets"
        ).stdout.strip()
        rfc = Path(p)
        self.assertEqual(rfc.parent, self.ws / "DECISIONS")
        r = ca(self.ws, "approve", str(rfc))
        self.assertNotEqual(r.returncode, 0)  # markers block approval
        self.assertIn("marker", r.stderr + r.stdout)
        fill(rfc)
        # forged frontmatter is worthless
        rfc.write_text(
            rfc.read_text(encoding="utf-8").replace(
                "status: draft", "status: approved"
            ),
            encoding="utf-8",
        )
        r = ca(self.api, "new-feature", "widgets", "--rfc", "RFC-0001")
        self.assertEqual(r.returncode, 0, r.stderr)
        st = ca(self.api, "status").stdout
        self.assertIn(
            "RFC-0001-add-widgets.md is draft", st
        )  # real state, not the forged text
        # the agent may not touch approval records or run approve via Bash
        self.assertTrue(
            denied(self.api, self.api / ".groundwork" / "approvals.json")[0]
        )
        b = hook(
            self.api, "gate-bash", {"command": "python3 x/groundwork.py approve foo"}
        )
        self.assertEqual(b["permissionDecision"], "deny")
        b = hook(
            self.api, "gate-bash", {"command": "echo '{}' > .groundwork/approvals.json"}
        )
        self.assertEqual(b["permissionDecision"], "deny")
        self.assertIsNone(hook(self.api, "gate-bash", {"command": "pytest -q"}))
        # quoted engine paths (how the skills invoke it) must be denied too
        for cmd in [
            'python3 "/x/engine/groundwork.py" approve RFC-0001',
            "python3 '/x/engine/groundwork.py' bypass x",
            'python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" approve RFC-0001',
            'python3 "/x/engine/groundwork.py" "approve" RFC-0001',
        ]:
            b = hook(self.api, "gate-bash", {"command": cmd})
            self.assertEqual(b["permissionDecision"], "deny", cmd)

        # 4. human approves RFC; spec still not -> still blocked
        self.assertEqual(
            ca(self.ws, "approve", "RFC-0001", "--as", "lead").returncode, 0
        )
        self.assertIn(
            "RFC-0001-add-widgets.md is approved", ca(self.api, "status").stdout
        )
        d, why = denied(self.api, code)
        self.assertTrue(d)
        self.assertIn("spec.md", why)

        # 5. spec approved, plan/tasks/evals unfinished -> blocked on plan
        spec = self.api / "specs" / "001-widgets" / "spec.md"
        fill(spec)
        self.assertEqual(
            ca(self.api, "approve", str(spec), "--as", "lead").returncode, 0
        )
        d, why = denied(self.api, code)
        self.assertTrue(d)
        self.assertIn("plan.md", why)
        for n in ("plan", "tasks", "evals"):
            fill(self.api / "specs" / "001-widgets" / f"{n}.md")

        # 6. everything ready -> code allowed
        self.assertFalse(denied(self.api, code)[0])
        self.assertIn("implement", ca(self.api, "status").stdout)

        # 7. editing the approved spec makes approval stale -> blocked again
        spec.write_text(
            spec.read_text(encoding="utf-8") + "\nA new requirement.\n",
            encoding="utf-8",
        )
        d, why = denied(self.api, code)
        self.assertTrue(d)
        self.assertIn("stale", why)

    def test_multi_signoff_rfc(self):
        ca(self.ws, "scaffold")
        rfc = Path(ca(self.ws, "new-rfc", "x").stdout.strip())
        fill(rfc)
        rfc.write_text(
            rfc.read_text(encoding="utf-8").replace(
                "signoffs_required: 1", "signoffs_required: 2"
            ),
            encoding="utf-8",
        )
        out = ca(self.ws, "approve", str(rfc), "--as", "a").stdout
        self.assertIn("in-review", out)
        self.assertIn("signoffs_required: 2", out)  # tells the user how to move on
        self.assertIn(
            "in-review", ca(self.ws, "approve", str(rfc), "--as", "a").stdout
        )  # same person twice
        out = ca(self.ws, "bypass", "solo", "owner").stdout
        self.assertIn("does not approve", out)
        self.assertIn(f"Next step for {rfc.name}", out)
        self.assertIn("approved", ca(self.ws, "approve", str(rfc), "--as", "b").stdout)

    def test_api_rfc_hint_never_suggests_fewer_than_two_signoffs(self):
        ca(self.ws, "scaffold")
        rfc = Path(ca(self.ws, "new-rfc", "x").stdout.strip())
        fill(rfc)

        def front(old, new):
            rfc.write_text(
                rfc.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8"
            )

        front("classification: internal", "classification: api")
        front("signoffs_required: 1", "signoffs_required: 2")
        out = ca(self.ws, "approve", str(rfc), "--as", "a").stdout
        self.assertIn("1 more sign-off(s) needed", out)
        self.assertNotIn("lower `signoffs_required", out)
        self.assertIn("cannot be lowered", out)
        front("signoffs_required: 2", "signoffs_required: 3")
        out = ca(self.ws, "approve", str(rfc), "--as", "a").stdout
        self.assertIn("to 2 in its front matter", out)  # down to the api minimum, not 1

    def test_bypass_is_logged_and_expires_into_gate(self):
        ca(self.api, "scaffold")
        ca(self.ws, "scaffold")
        code = self.api / "x.py"
        self.assertTrue(denied(self.api, code)[0])
        r = ca(self.api, "bypass", "prod", "is", "down")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(denied(self.api, code)[0])
        self.assertIn(
            "prod is down",
            (self.api / ".groundwork" / "bypass.log").read_text(encoding="utf-8"),
        )
        b = json.loads(
            (self.api / ".groundwork" / "bypass.json").read_text(encoding="utf-8")
        )
        b["until"] = 1
        (self.api / ".groundwork" / "bypass.json").write_text(
            json.dumps(b), encoding="utf-8"
        )
        self.assertTrue(denied(self.api, code)[0])

    def test_enforcement_off_and_warn(self):
        ca(self.api, "scaffold")
        for mode, blocked in (("off", False), ("warn", False), ("block", True)):
            cfg = self.api / ".groundwork" / "config.json"
            cfg.write_text(json.dumps({"enforcement": mode}), encoding="utf-8")
            self.assertEqual(denied(self.api, self.api / "x.py")[0], blocked, mode)

    def test_workspace_level_code_is_not_gated_but_prompt_reminder_works(self):
        git_init(self.ws / "web")
        o = hook(self.ws, "prompt-reminder", {})
        self.assertIn("level=workspace", o["additionalContext"])
        self.assertFalse(denied(self.ws, self.ws / "notes.txt")[0])


if __name__ == "__main__":
    unittest.main()
