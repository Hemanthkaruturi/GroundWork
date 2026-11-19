"""Issues found in live runs with small models (2026-11-19): each test pins one fix."""

import json
import re
import sys
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_check import CheckBase
from test_flow import Base, ca, denied, hook
from test_quality import write


def phase(cwd):
    rem = hook(cwd, "prompt-reminder", {})["additionalContext"]
    return re.search(r"phase=(\w+)", rem).group(1)


class FeatureDone(CheckBase):
    def finish_tasks(self):
        t = self.fdir / "tasks.md"
        t.write_text(
            t.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8"
        )

    def test_handover_written_ends_the_handover_phase(self):
        self.finish_tasks()
        self.assertEqual(phase(self.api), "handover")
        (self.fdir / "handover.md").write_text("# Handover\nDone.\n", encoding="utf-8")
        self.assertEqual(phase(self.api), "done")

    def test_unfinished_handover_keeps_the_handover_phase(self):
        self.finish_tasks()
        (self.fdir / "handover.md").write_text(
            "# Handover\n[TODO: risks]\n", encoding="utf-8"
        )
        self.assertEqual(phase(self.api), "handover")


class PlanSyncAnyFeature(CheckBase):
    def test_names_a_feature_other_than_the_active_one(self):
        (self.api / ".groundwork" / "active").write_text(
            "999-other\n", encoding="utf-8"
        )
        for arg in ("001-widgets", "specs/001-widgets"):
            r = ca(self.api, "plan-sync", arg)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("specs/001-widgets: pinned", r.stdout)
            self.assertIn("plan.md", r.stdout)

    def test_unknown_feature_is_refused(self):
        r = ca(self.api, "plan-sync", "042-nope")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("specs/042-nope/spec.md", r.stderr)


class RecordFixed(CheckBase):
    def test_record_fixed_moves_a_diagnosed_bug_to_fixed(self):
        (self.api / ".groundwork" / "active").unlink()
        ca(self.api, "new-bug", "crash", "--reported-by", "Lead Person")
        bug = self.api / "bugs" / "001-crash.md"
        bug.write_text(
            re.sub(
                r"(?m)^status: \w+",
                "status: diagnosed",
                bug.read_text(encoding="utf-8"),
            ),
            encoding="utf-8",
        )
        r = ca(self.api, "record", "fixed", "--ref", "bugs/001-crash")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("bug status diagnosed -> fixed", r.stdout)
        self.assertRegex(bug.read_text(encoding="utf-8"), r"(?m)^status: fixed")

    def test_closed_bug_stays_closed(self):
        (self.api / ".groundwork" / "active").unlink()
        ca(self.api, "new-bug", "crash", "--reported-by", "Lead Person")
        bug = self.api / "bugs" / "001-crash.md"
        bug.write_text(
            re.sub(
                r"(?m)^status: \w+", "status: closed", bug.read_text(encoding="utf-8")
            ),
            encoding="utf-8",
        )
        r = ca(self.api, "record", "fixed", "--ref", "bugs/001-crash")
        self.assertNotIn("status", r.stdout)
        self.assertRegex(bug.read_text(encoding="utf-8"), r"(?m)^status: closed")


class AcceptanceCitations(CheckBase):
    def test_citation_on_a_wrapped_line_counts(self):
        spec = self.fdir / "spec.md"
        text = spec.read_text(encoding="utf-8")
        m = re.search(r"(?m)^- \*\*AC-1\*\*.*$", text)
        self.assertIsNotNone(m, "fixture spec has no AC-1 bullet")
        spec.write_text(
            text.replace(
                m.group(0),
                "- **AC-1** Given a widget, when listed,\n  then it shows (covers FR-1).",
            ),
            encoding="utf-8",
        )
        self.assertNotIn("AC-1 does not cite", ca(self.api, "check").stdout)

    def test_missing_citation_says_how_to_write_it(self):
        spec = self.fdir / "spec.md"
        text = spec.read_text(encoding="utf-8")
        m = re.search(r"(?m)^- \*\*AC-1\*\*.*$", text)
        spec.write_text(
            text.replace(m.group(0), "- **AC-1** Given a widget, then it shows."),
            encoding="utf-8",
        )
        out = ca(self.api, "check").stdout
        self.assertIn("AC-1 does not cite", out)
        self.assertIn("- **AC-1** (FR-1) Given", out)


class QualityTopUp(Base):
    def setUp(self):
        super().setUp()
        from test_flow import git_init

        self.repo = self.root / "r"
        git_init(self.repo)
        ca(self.repo, "init")

    def test_empty_repo_says_configs_come_later_and_top_up_needs_no_force(self):
        r = ca(self.repo, "quality", "init", "--create")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("No code yet", r.stdout)
        write(self.repo, "src/a.py", "x = 1\n")
        again = ca(self.repo, "quality", "init", "--create")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("Kept: GroundWork standard toolchain", again.stdout)
        self.assertTrue(
            (self.repo / "ruff.toml").is_file()
            or (self.repo / "pyproject.toml").is_file()
        )

    def test_switching_from_keep_still_needs_force(self):
        ca(self.repo, "quality", "keep")
        r = ca(self.repo, "quality", "init", "--create")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--force", r.stderr)


class GateSaysAllEditsAreHeld(Base):
    def test_denial_tells_the_agent_not_to_try_other_files(self):
        from test_flow import git_init

        git_init(self.root / "r")
        d, why = denied(self.root / "r", self.root / "r" / "app.py")
        self.assertTrue(d)
        self.assertIn("holds every code edit", why)


class EmptyGitFolderIsNotARepo(Base):
    def test_codex_sandbox_mount_target_is_ignored(self):
        # Codex's sandbox creates an empty `.git` folder in its writable roots (e.g. /tmp) while a command runs.
        from test_flow import git_init

        (self.root / ".git").mkdir()
        git_init(self.root / "api")
        ws = self.root / "ws"
        ws.mkdir()
        self.assertIn(
            "Level: UNKNOWN", hook(ws, "session-context", {})["additionalContext"]
        )
        self.assertIn(
            "Level: STANDALONE",
            hook(self.root / "api", "session-context", {})["additionalContext"],
        )

    def test_git_file_still_marks_a_worktree(self):
        wt = self.root / "wt"
        wt.mkdir()
        (wt / ".git").write_text(
            "gitdir: /somewhere/.git/worktrees/wt\n", encoding="utf-8"
        )
        self.assertIn(
            "Level: STANDALONE", hook(wt, "session-context", {})["additionalContext"]
        )


class ChangeHookNamesTheHost(Base):
    def test_change_on_codex_records_via_codex(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
        import groundwork as GW

        text = GW.after_human_action("change", "OPENED", str(self.root), "codex")
        self.assertIn("--via codex", text)
        self.assertNotIn("claude-code", text)


class ApproveIgnoresAnUnrelatedBug(CheckBase):
    def test_next_step_after_approving_a_spec_is_the_feature_not_the_bug(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
        import groundwork as GW

        active = (self.api / ".groundwork" / "active").read_text(encoding="utf-8")
        ca(self.api, "new-bug", "crash", "--reported-by", "Lead Person")
        (self.api / ".groundwork" / "active").write_text(active, encoding="utf-8")
        self.assertEqual(phase(self.api), "bug")
        text = GW.after_human_action(
            "approve", "spec.md: approved (1/1 sign-offs)", str(self.api)
        )
        self.assertNotIn("phase=bug", text)
        self.assertIn("is also open", text)


class WindowsPaths(CheckBase):
    """CI on Windows: approval keys were written with backslashes, and approve arguments lost theirs."""

    def test_an_approval_recorded_with_backslashes_still_counts(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
        import groundwork_core as C

        rfc = next((self.ws / "DECISIONS").glob("RFC-*.md"))
        f = self.ws / ".groundwork" / "approvals.json"
        store = json.loads(f.read_text(encoding="utf-8"))
        rel = rfc.relative_to(self.ws).as_posix()
        self.assertIn(rel, store)
        store[rel.replace("/", "\\")] = store.pop(rel)
        f.write_text(json.dumps(store), encoding="utf-8")
        ctx = C.detect(self.ws)
        self.assertEqual(C.doc_state(rfc, ctx).status, "approved")

    def test_windows_arguments_keep_their_backslashes(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
        import groundwork as GW

        with unittest.mock.patch.object(GW.os, "name", "nt"):
            self.assertEqual(
                GW.split_args(r'C:\w\spec.md "C:\My Docs\x.md" RFC-0001'),
                [r"C:\w\spec.md", r"C:\My Docs\x.md", "RFC-0001"],
            )


class AmendingRfcIsCarriedByTheSpec(CheckBase):
    def test_rfc_named_in_a_specs_changes_is_not_waiting_for_a_spec(self):
        created = ca(self.ws, "new-rfc", "archive")
        rfc = Path(created.stdout.strip())
        from test_flow import fill

        fill(rfc)
        rid = re.search(r"RFC-\d{4}", rfc.name).group(0)
        approved = ca(self.ws, "approve", rid, "--as", "lead")
        self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
        before = ca(self.ws, "board").stdout
        self.assertTrue(
            any(rid in line and "no spec yet" in line for line in before.splitlines()),
            before,
        )
        spec = self.fdir / "spec.md"
        spec.write_text(
            spec.read_text(encoding="utf-8")
            + f"\n## Changes\n- 2026-11-19: archive habits, following {rid}.\n",
            encoding="utf-8",
        )
        after = ca(self.ws, "board").stdout
        self.assertFalse(
            any(rid in line and "no spec yet" in line for line in after.splitlines()),
            after,
        )


class StandaloneAgentsTemplate(Base):
    def test_standalone_repo_gets_the_repo_agents_file(self):
        from test_flow import git_init

        r = self.root / "r"
        git_init(r)
        ca(r, "init")
        agents = (r / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("CODEMAP.md", agents)
        self.assertNotIn("workspace of", agents)


class ConfigFilesAreNotCode(Base):
    def test_bootstrap_may_write_project_config(self):
        from test_flow import git_init

        r = self.root / "r"
        git_init(r)
        for name in (".env.example", "ruff.toml", "mypy.ini"):
            self.assertFalse(denied(r, r / name)[0], name)
        for name in ("app.py", "pyproject.toml"):  # a dependency change is a /change
            self.assertTrue(denied(r, r / name)[0], name)


class QuestionAlertMatchesEveryHost(unittest.TestCase):
    def test_matcher_covers_claude_devin_and_codex_question_tools(self):
        cfg = json.loads(
            (Path(__file__).resolve().parents[1] / "hooks" / "hooks.json").read_text(
                encoding="utf-8"
            )
        )
        m = next(
            e["matcher"]
            for e in cfg["hooks"]["PreToolUse"]
            if "alert-question" in e["hooks"][0]["command"]
        )
        for tool in (
            "AskUserQuestion",
            "ask_user_question",
            "request_user_input",
            "request_user_input_async",
        ):
            self.assertRegex(tool, m)
        self.assertNotRegex("Bash", m)


class ResumeKeepsRulesOnce(Base):
    def test_resume_resends_state_but_not_the_rules(self):
        from test_flow import git_init

        r = self.root / "r"
        git_init(r)

        def run(h, source):
            out = ca(r, h, stdin=json.dumps({"cwd": str(r), "source": source})).stdout
            return (
                json.loads(out)["hookSpecificOutput"]["additionalContext"]
                if out.strip()
                else None
            )

        for h in ("session-rules-1", "session-rules-2"):
            self.assertIsNone(run(h, "resume"), h)
            self.assertIsNotNone(
                run(h, "compact"), h
            )  # a compacted conversation lost them
            self.assertIsNotNone(run(h, "startup"), h)
        state = run("session-context", "resume")
        self.assertIn("Level: STANDALONE", state)
        self.assertIn("given when this conversation started", state)


if __name__ == "__main__":
    unittest.main()
