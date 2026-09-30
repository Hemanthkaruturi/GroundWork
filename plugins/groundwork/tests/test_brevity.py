"""Short, plain writing: measured in documents, optionally enforced on chat replies."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
ENGINE = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENGINE))
import groundwork_brevity as V  # noqa: E402
from test_check import CheckBase, check  # noqa: E402
from test_flow import ca, hook  # noqa: E402


def transcript(path, turns):
    rows = []
    for role, content in turns:
        rows.append({"type": role, "message": {"role": role, "content": content}})
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


TEXT = lambda s: [{"type": "text", "text": s}]   # noqa: E731
LONG = " ".join(["word"] * 400)


class Measure(unittest.TestCase):
    def test_prose_excludes_front_matter_comments_code_tables_headings(self):
        doc = "---\nid: x\n---\n# Title\n<!-- hidden hidden hidden -->\n```\ncode code code\n```\n| a | b |\n| - | - |\nOne two three.\n"
        self.assertEqual(V.words(doc), 3)

    def test_average_sentence_length(self):
        short = "This is a short one. " * 8
        long = ("This sentence goes on and on with many extra words that make it hard to follow for a busy reader who "
                "wants to decide quickly without reading every single clause of it twice over. ") * 8
        self.assertLess(V.avg_sentence(short), 10)
        self.assertGreater(V.avg_sentence(long), V.MAX_AVG_SENTENCE)

    def test_last_reply_counts_only_since_the_last_real_user_message(self):
        t = transcript(Path(tempfile.mkdtemp()) / "t.jsonl", [
            ("user", TEXT("first question")), ("assistant", TEXT(LONG)),
            ("user", TEXT("second question")),
            ("assistant", [{"type": "tool_use", "name": "Bash", "input": {}}]),
            ("user", [{"type": "tool_result", "content": "ok"}]),                 # a tool result is not a new user turn
            ("assistant", TEXT("short answer part one.")), ("assistant", TEXT("part two."))])
        text = V.last_reply_text(t)
        self.assertNotIn("word word", text)
        self.assertEqual(V.reply_words(text), 6)


class Docs(CheckBase):
    def test_conforming_fixture_has_no_brevity_findings(self):
        self.assertFalse({"GW090", "GW091"} & check(self.ws)[1])

    def test_over_budget_spec_warns_and_is_not_an_error(self):
        p = self.fdir / "spec.md"
        p.write_text(p.read_text() + "\n" + ("A plain and simple sentence. " * 300) + "\n")
        code, ids, items = check(self.ws)
        self.assertIn("GW090", ids)
        self.assertNotIn("GW091", ids)
        self.assertEqual([i for i in items if i["id"] == "GW090"][0]["severity"], "warning")

    def test_long_sentences_warn(self):
        p = self.ws / "ARCHITECTURE.md"
        p.write_text(p.read_text() + "\n" + ("This sentence keeps going and going with many extra words so that a busy reader who only "
                                             "wants the point has to work far too hard to find it. " * 8) + "\n")
        self.assertIn("GW091", check(self.ws)[1])

    def test_brevity_off_silences_it(self):
        p = self.ws / "ARCHITECTURE.md"
        p.write_text(p.read_text() + "\n" + ("Long sentence " * 40 + ". ") * 8)
        cfg = self.ws / ".groundwork" / "config.json"
        cfg.write_text(json.dumps({"level": "workspace", "standard": "0.5.0", "brevity": "off"}))
        self.assertFalse({"GW090", "GW091"} & check(self.ws)[1])

    def test_unfinished_documents_are_not_judged(self):
        p = self.fdir / "plan.md"
        p.write_text(p.read_text() + "\n[TODO: more]\n" + ("Sentence. " * 3000))
        self.assertNotIn("GW090", check(self.ws)[1])


class Reminders(CheckBase):
    def test_the_rule_is_in_the_session_context_and_in_every_prompt(self):
        ctx = hook(self.api, "session-context", {})["additionalContext"]
        self.assertIn("COMMUNICATION", ctx); self.assertIn("answer or decision first", ctx)
        rem = hook(self.api, "prompt-reminder", {})["additionalContext"]
        self.assertIn("busy reader", rem)


class StopHook(CheckBase):
    def run_stop(self, reply, mode="enforce", **extra):
        t = transcript(self.root / "t.jsonl", [("user", TEXT("do it")), ("assistant", TEXT(reply))])
        (self.api / ".groundwork" / "config.json").write_text(json.dumps({"standard": "0.5.0", "brevity": mode, **extra.pop("cfg", {})}))
        payload = {"cwd": str(self.api), "transcript_path": str(t), **extra}
        r = ca(self.api, "stop-brevity", stdin=json.dumps(payload))
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else None

    def test_long_reply_is_sent_back_once(self):
        out = self.run_stop(LONG)
        self.assertEqual(out["decision"], "block")
        self.assertIn("Rewrite the reply now", out["reason"]); self.assertIn("400", out["reason"])
        self.assertIsNone(self.run_stop(LONG, stop_hook_active=True))     # never loops

    def test_shortening_is_lossless_the_original_is_saved_and_the_must_keep_list_is_stated(self):
        out = self.run_stop(LONG)
        saved = sorted((self.api / ".groundwork" / "replies").glob("*.md"))
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].read_text().strip(), LONG)                 # the full original, untouched
        self.assertIn(str(saved[0]), out["reason"])
        for must in ("did NOT verify", "failed or was skipped", "risks and side effects", "every file or setting", "assumptions", "Full detail:"):
            self.assertIn(must, out["reason"])
        self.assertIn("replies/", (self.api / ".groundwork" / ".gitignore").read_text())

    def test_the_must_keep_rule_is_in_the_session_rules_and_every_prompt(self):
        ctx = hook(self.api, "session-context", {})["additionalContext"]
        rem = hook(self.api, "prompt-reminder", {})["additionalContext"]
        for text in (ctx, rem):
            self.assertIn("SHORT MUST NOT MEAN LESS TRUE", text)
            self.assertIn("did NOT verify", text)

    def test_uses_the_final_message_from_the_harness_when_the_transcript_is_behind(self):
        (self.api / ".groundwork" / "config.json").write_text(json.dumps({"standard": "0.5.0", "brevity": "enforce"}))
        stale = transcript(self.root / "old.jsonl", [("user", TEXT("hi")), ("assistant", TEXT("ok"))])   # last reply not written yet
        r = ca(self.api, "stop-brevity", stdin=json.dumps({"cwd": str(self.api), "transcript_path": str(stale),
                                                           "last_assistant_message": LONG, "stop_hook_active": False}))
        self.assertEqual(json.loads(r.stdout)["decision"], "block")
        r = ca(self.api, "stop-brevity", stdin=json.dumps({"cwd": str(self.api), "last_assistant_message": "Done."}))
        self.assertEqual(r.stdout.strip(), "")

    def test_short_reply_and_other_modes_pass(self):
        self.assertIsNone(self.run_stop("Done. Tests pass."))
        self.assertIsNone(self.run_stop(LONG, mode="guide"))
        self.assertIsNone(self.run_stop(LONG, mode="off"))

    def test_code_and_tables_do_not_count(self):
        reply = "Here is the change.\n```python\n" + "x = 1\n" * 500 + "```\n| a | b |\n" * 50
        self.assertIsNone(self.run_stop(reply))

    def test_threshold_is_configurable(self):
        self.assertIsNone(self.run_stop(LONG, cfg={"max_reply_words": 1000}))
        self.assertIsNotNone(self.run_stop("word " * 60, cfg={"max_reply_words": 50}))


if __name__ == "__main__":
    unittest.main()
