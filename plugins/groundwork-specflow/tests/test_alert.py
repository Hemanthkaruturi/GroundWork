"""Attention alerts: the right backend per platform, and no repeat ringing inside the cooldown."""

import base64
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
ENGINE = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENGINE))
import groundwork as GW
import groundwork_alert as A
import groundwork_core as C
from test_flow import ca, fill, git_init, hook


def which(*present):
    return lambda name: f"/usr/bin/{name}" if name in present else None


class Plan(unittest.TestCase):
    def test_wsl_uses_windows_powershell_with_toast_sound_and_voice(self):
        with (
            mock.patch.object(A.sys, "platform", "linux"),
            mock.patch.object(A.shutil, "which", which("powershell.exe")),
        ):
            steps = A.plan("decision", voice=True, env={"WSL_DISTRO_NAME": "Ubuntu"})
        self.assertEqual(steps["backend"], "wsl")
        (argv,) = steps["commands"]
        script = base64.b64decode(argv[-1]).decode("utf-16-le")
        self.assertEqual(script, steps["script"])
        self.assertIn("ToastNotification", script)
        self.assertIn("Windows Exclamation.wav", script)
        self.assertIn("SpeechSynthesizer", script)

    def test_done_uses_a_different_sound_and_stays_quiet_without_voice(self):
        script = A.windows_script(False, "t", "m", None)
        self.assertIn(A.WIN_SOUNDS[False], script)
        self.assertNotIn("SpeechSynthesizer", script)

    def test_text_is_escaped_for_xml_and_powershell(self):
        script = A.windows_script(True, "it's <ok>", "a & b", None)
        self.assertIn("it''s &lt;ok&gt;", script)
        self.assertIn("a &amp; b", script)

    def test_macos(self):
        with mock.patch.object(A.sys, "platform", "darwin"):
            steps = A.plan("done", voice=True, env={})
        self.assertEqual(steps["backend"], "macos")
        self.assertEqual(
            [c[0] for c in steps["commands"]], ["osascript", "afplay", "say"]
        )

    def test_linux_desktop(self):
        with (
            mock.patch.object(A.sys, "platform", "linux"),
            mock.patch.object(A, "is_wsl", lambda env: False),
            mock.patch.object(
                A.shutil, "which", which("notify-send", "canberra-gtk-play")
            ),
        ):
            steps = A.plan("question", env={"DISPLAY": ":0"})
        self.assertEqual(steps["backend"], "linux")
        self.assertIn("critical", steps["commands"][0])
        self.assertEqual(steps["commands"][1][0], "canberra-gtk-play")

    def test_ssh_and_headless_fall_back_to_the_bell(self):
        with (
            mock.patch.object(A.sys, "platform", "darwin"),
            mock.patch.object(A, "is_wsl", lambda env: False),
        ):
            self.assertEqual(
                A.plan("done", env={"SSH_CONNECTION": "x"})["backend"], "bell"
            )
        with (
            mock.patch.object(A.sys, "platform", "linux"),
            mock.patch.object(A, "is_wsl", lambda env: False),
        ):
            self.assertEqual(A.plan("done", env={})["backend"], "bell")


class Cooldown(unittest.TestCase):
    def test_second_alert_inside_the_window_is_skipped_per_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            with mock.patch.object(A, "_cooldown_file", lambda: state):
                self.assertFalse(A.cooling_down("question", 20, now=100))
                self.assertTrue(A.cooling_down("question", 20, now=110))
                self.assertFalse(A.cooling_down("done", 20, now=110))
                self.assertFalse(A.cooling_down("question", 20, now=121))


class Setting(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = mock.patch.dict(os.environ, {"GROUNDWORK_USER_DIR": tmp.name})
        env.start()
        self.addCleanup(env.stop)

    def test_off_until_turned_on_and_kept_per_person(self):
        self.assertFalse(A.enabled())
        with (
            mock.patch.object(A, "fire") as fire,
            mock.patch.object(A, "plan", wraps=A.plan) as plan,
        ):
            self.assertFalse(A.notify("decision"))
            fire.assert_not_called()
            path = A.set_enabled(True)
            self.assertTrue(A.enabled())
            self.assertEqual(path.parent, Path(os.environ["GROUNDWORK_USER_DIR"]))
            with mock.patch.object(A, "cooling_down", lambda *a: False):
                self.assertTrue(A.notify("decision", "x"))
        fire.assert_called_once()
        self.assertTrue(plan.call_args.kwargs["voice"])  # voice comes with alerts
        A.set_enabled(False)
        self.assertFalse(A.enabled())

    def test_voice_can_be_turned_off_while_alerts_stay_on(self):
        A.set_enabled(True)
        self.assertTrue(A.voice_enabled())  # on by default with alerts
        A.set_voice(False)
        self.assertTrue(A.enabled())
        with (
            mock.patch.object(A, "fire") as fire,
            mock.patch.object(A, "plan", wraps=A.plan) as plan,
            mock.patch.object(A, "cooling_down", lambda *a: False),
        ):
            self.assertTrue(A.notify("question"))
        fire.assert_called_once()
        self.assertFalse(plan.call_args.kwargs["voice"])
        A.set_voice(True)
        self.assertTrue(A.voice_enabled())

    def test_voice_command(self):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            GW.cmd_alerts(mock.Mock(state="voice", value="off"))
            GW.cmd_alerts(mock.Mock(state="status", value=None))
        self.assertIn("Voice is off", out.getvalue())
        self.assertIn("Alerts are off, voice is off.", out.getvalue())
        with self.assertRaises(SystemExit):
            GW.cmd_alerts(mock.Mock(state="voice", value=None))

    def test_same_key_alerts_once(self):
        self.assertTrue(A.first_time("decision", "rfc:v1"))
        self.assertFalse(A.first_time("decision", "rfc:v1"))
        self.assertTrue(A.first_time("decision", "rfc:v2"))


class Gates(unittest.TestCase):
    """The hooks ring at GroundWork's own gates: a finished document waiting for approval, a question, a handover."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ws = Path(tmp.name).resolve() / "ws"
        git_init(self.ws / "api")
        self.assertEqual(ca(self.ws, "mark-workspace").returncode, 0)
        self.assertEqual(ca(self.ws, "scaffold").returncode, 0)
        for f in ["PROJECT.md", "ARCHITECTURE.md", "CONSTITUTION.md", "AGENTS.md"]:
            fill(self.ws / f)
        env = mock.patch.dict(os.environ, {"GROUNDWORK_USER_DIR": tmp.name + "/user"})
        env.start()
        self.addCleanup(env.stop)

    def stop(self, cwd):
        payload = io.StringIO(json.dumps({"cwd": str(cwd)}))
        with mock.patch.object(A, "notify") as notify, mock.patch("sys.stdin", payload):
            GW.cmd_alert_stop(None)
        return [c.args for c in notify.call_args_list]

    def test_a_finished_rfc_rings_once_and_again_after_it_changes(self):
        rfc = Path(ca(self.ws, "new-rfc", "add-widgets", "--title", "W").stdout.strip())
        self.assertIsNone(GW.awaiting_approval(C.detect(self.ws)))  # still has markers
        fill(rfc)
        self.assertEqual(GW.awaiting_approval(C.detect(self.ws)).path, rfc)
        self.assertEqual(self.stop(self.ws), [])  # alerts are off
        A.set_enabled(True)
        (call,) = self.stop(self.ws)
        self.assertEqual(call[0], "decision")
        self.assertIn(rfc.name, call[1])
        self.assertEqual(self.stop(self.ws), [])  # same version: no repeat
        rfc.write_text(rfc.read_text(encoding="utf-8") + "\nmore\n", encoding="utf-8")
        self.assertEqual(len(self.stop(self.ws)), 1)

    def test_a_written_handover_rings_done_once(self):
        api = self.ws / "api"
        (api / ".groundwork").mkdir()
        (api / ".groundwork" / "active").write_text("widgets", encoding="utf-8")
        (api / "specs" / "widgets").mkdir(parents=True)
        A.set_enabled(True)
        with mock.patch.object(GW, "awaiting_approval", lambda ctx: None):
            self.assertEqual(self.stop(api), [])
            (api / "specs" / "widgets" / "handover.md").write_text("# done")
            (call,) = self.stop(api)
            self.assertEqual(self.stop(api), [])
        self.assertEqual(call[0], "done")
        self.assertIn("widgets", call[1])

    def test_question_hook_only_when_on(self):
        with mock.patch.object(A, "notify") as notify:
            for on in (False, True):
                A.set_enabled(on)
                with mock.patch(
                    "sys.stdin", io.StringIO(json.dumps({"cwd": str(self.ws)}))
                ):
                    GW.cmd_alert_question(None)
        notify.assert_called_once()
        self.assertEqual(notify.call_args.args[0], "question")

    def test_hooks_are_silent_and_allowed_when_alerts_are_off(self):
        self.assertIsNone(hook(self.ws, "alert-stop", {}))
        self.assertIsNone(hook(self.ws, "alert-question", {}))

    def test_the_agent_may_turn_alerts_on_through_the_shell(self):
        cmd = 'python3 "${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py" alerts on'
        self.assertIsNone(hook(self.ws, "gate-bash", {"command": cmd}))
        r = ca(self.ws, "alerts", "status")
        self.assertIn("off", r.stdout)  # the hooks' HOME has no settings: off


if __name__ == "__main__":
    unittest.main()
