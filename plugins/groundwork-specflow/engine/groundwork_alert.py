"""Get the person's attention when the agent is waiting on them at one of GroundWork's gates.

One call plays a sound, shows a desktop notification and, optionally, speaks a short phrase. Each
platform does this differently, so `plan()` picks a backend and returns the commands without running
them; `fire()` runs them detached so a hook never waits on audio.

Alerts are a per-person choice, off until the person turns them on (`groundwork.py alerts on`). The
setting lives in ~/.groundwork/settings.json, so it follows the person across every project. The voice
comes with alerts unless the person turns just the voice off (`groundwork.py alerts voice off`). The hooks call `notify()`, which does nothing while alerts are off.

    python3 groundwork_alert.py decision            # blocking: an approval or a choice is needed
    python3 groundwork_alert.py question --voice    # blocking, and say it out loud
    python3 groundwork_alert.py done --dry-run      # show what would run, run nothing

Backends, tried in order: Windows (native or from WSL, via PowerShell), macOS, Linux desktop, and
finally the terminal bell. Over SSH only the bell is used: a sound on the remote machine helps no one.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from xml.sax.saxutils import escape

KINDS = {  # kind: (blocking?, title, message, spoken)
    "decision": (
        True,
        "GroundWork needs your decision",
        "A document is waiting for your approval.",
        "GroundWork needs your attention.",
    ),
    "question": (
        True,
        "GroundWork has questions",
        "The agent is waiting for your answers.",
        "GroundWork has a question for you.",
    ),
    "done": (
        False,
        "GroundWork finished",
        "The work is ready for you to review.",
        "GroundWork is done.",
    ),
}
DEFAULT_COOLDOWN = 20  # seconds; one interview should not ring for every question

WIN_MEDIA = "C:\\Windows\\Media\\"
WIN_SOUNDS = {True: "Windows Exclamation.wav", False: "Windows Notify Calendar.wav"}
MAC_SOUNDS = {True: "Glass", False: "Hero"}
LINUX_SOUNDS = {True: "dialog-warning", False: "complete"}
FREEDESKTOP = Path("/usr/share/sounds/freedesktop/stereo")
# PowerShell's own app id; lets a script raise a toast without registering an app.
PS_APP_ID = (
    r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
)
WSL_POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"


def is_wsl(env=None) -> bool:
    env = os.environ if env is None else env
    if env.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def powershell(wsl: bool) -> str | None:
    exe = shutil.which("powershell.exe") or shutil.which("powershell")
    if not exe and wsl and Path(WSL_POWERSHELL).exists():
        exe = WSL_POWERSHELL
    return exe


def _ps_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def windows_script(blocking: bool, title: str, message: str, spoken: str | None) -> str:
    toast = (
        '<toast><visual><binding template="ToastGeneric">'
        f"<text>{escape(title)}</text><text>{escape(message)}</text>"
        '</binding></visual><audio silent="true"/></toast>'
    )
    lines = [
        "$ErrorActionPreference = 'SilentlyContinue'",
        "$ProgressPreference = 'SilentlyContinue'",
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null",
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null",
        "$x = New-Object Windows.Data.Xml.Dom.XmlDocument",
        f"$x.LoadXml({_ps_quote(toast)})",
        "$t = New-Object Windows.UI.Notifications.ToastNotification $x",
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier({_ps_quote(PS_APP_ID)}).Show($t)",
        f"(New-Object Media.SoundPlayer {_ps_quote(WIN_MEDIA + WIN_SOUNDS[blocking])}).PlaySync()",
    ]
    if spoken:
        lines += [
            "Add-Type -AssemblyName System.Speech",
            f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak({_ps_quote(spoken)})",
        ]
    return "\n".join(lines)


def _linux_sound(blocking: bool) -> list[str] | None:
    name = LINUX_SOUNDS[blocking]
    oga = FREEDESKTOP / f"{name}.oga"
    for player in ("pw-play", "paplay"):
        if shutil.which(player) and oga.exists():
            return [player, str(oga)]
    if shutil.which("canberra-gtk-play"):
        return ["canberra-gtk-play", "-i", name]
    return None


def plan(kind: str, message: str | None = None, voice: bool = False, env=None) -> dict:
    """Which backend to use and the commands it would run. Pure apart from looking around."""
    env = os.environ if env is None else env
    blocking, title, default_message, spoken = KINDS[kind]
    message = message or default_message
    spoken = spoken if voice else None
    wsl = sys.platform.startswith("linux") and is_wsl(env)
    remote = bool(env.get("SSH_CONNECTION") or env.get("SSH_TTY")) and not wsl

    if not remote and (sys.platform == "win32" or wsl):
        exe = powershell(wsl)
        if exe:
            script = windows_script(blocking, title, message, spoken)
            encoded = base64.b64encode(script.encode("utf-16-le")).decode()
            argv = [exe, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
            return {
                "backend": "wsl" if wsl else "windows",
                "commands": [argv],
                "script": script,
            }

    if not remote and sys.platform == "darwin":
        notify = (
            f"display notification {json.dumps(message)} with title {json.dumps(title)}"
        )
        cmds = [
            ["osascript", "-e", notify],
            ["afplay", f"/System/Library/Sounds/{MAC_SOUNDS[blocking]}.aiff"],
        ]
        if spoken:
            cmds.append(["say", spoken])
        return {"backend": "macos", "commands": cmds}

    has_display = env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")
    if not remote and sys.platform.startswith("linux") and has_display:
        cmds = []
        if shutil.which("notify-send"):
            urgency = "critical" if blocking else "normal"
            cmds.append(
                ["notify-send", "-a", "GroundWork", "-u", urgency, title, message]
            )
        sound = _linux_sound(blocking)
        if sound:
            cmds.append(sound)
        if spoken:
            for speaker in ("spd-say", "espeak-ng", "espeak"):
                if shutil.which(speaker):
                    cmds.append([speaker, spoken])
                    break
        if cmds:
            return {"backend": "linux", "commands": cmds}

    return {"backend": "bell", "commands": []}


def user_dir() -> Path:
    return Path(os.environ.get("GROUNDWORK_USER_DIR") or Path.home() / ".groundwork")


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def enabled() -> bool:
    return _load(user_dir() / "settings.json").get("alerts") is True


def voice_enabled() -> bool:
    return _load(user_dir() / "settings.json").get("voice", True) is not False


def _set(key: str, on: bool) -> Path:
    path = user_dir() / "settings.json"
    data = _load(path)
    data[key] = on
    _save(path, data)
    return path


def set_enabled(on: bool) -> Path:
    return _set("alerts", on)


def set_voice(on: bool) -> Path:
    return _set("voice", on)


def first_time(kind: str, key: str) -> bool:
    """True once per distinct key, so the same waiting document does not ring on every turn."""
    path = user_dir() / "alert-state.json"
    seen = _load(path)
    if seen.get(kind) == key:
        return False
    seen[kind] = key
    try:
        _save(path, seen)
    except OSError:
        pass
    return True


def notify(kind: str, message: str | None = None) -> bool:
    """The hooks' entry point: alert if the person turned alerts on, spoken unless voice is off. Never raises."""
    try:
        if not enabled() or cooling_down(kind, DEFAULT_COOLDOWN):
            return False
        fire(plan(kind, message, voice=voice_enabled()))
        return True
    except Exception:  # noqa: BLE001 - a failed alert must never break the agent's turn
        return False


def ring_bell() -> bool:
    """Hooks have their stdout captured, so the bell goes straight to the terminal."""
    try:
        with open("/dev/tty", "w") as tty:
            tty.write("\a")
        return True
    except OSError:
        return False


def _cooldown_file() -> Path:
    uid = os.getuid() if hasattr(os, "getuid") else os.environ.get("USERNAME", "user")
    return Path(tempfile.gettempdir()) / f"groundwork-alert-{uid}.json"


def cooling_down(kind: str, seconds: float, now: float | None = None) -> bool:
    """True if this kind fired recently; otherwise records that it fires now."""
    now = time.time() if now is None else now
    path = _cooldown_file()
    try:
        last = json.loads(path.read_text())
    except (OSError, ValueError):
        last = {}
    if now - last.get(kind, 0) < seconds:
        return True
    last[kind] = now
    try:
        path.write_text(json.dumps(last))
    except OSError:
        pass
    return False


def fire(steps: dict, wait: bool = False) -> None:
    cmds = steps["commands"]
    if not cmds:
        ring_bell()
        return
    if len(cmds) == 1:
        argv = cmds[0]
    else:  # several steps run one after another (POSIX backends only)
        argv = ["sh", "-c", "; ".join(shlex.join(c) for c in cmds)]
    quiet = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL}
    if wait:
        subprocess.run(argv, check=False, **quiet)
    elif sys.platform == "win32":
        subprocess.Popen(argv, creationflags=subprocess.DETACHED_PROCESS, **quiet)
    else:
        subprocess.Popen(
            argv, start_new_session=True, stderr=subprocess.DEVNULL, **quiet
        )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Alert the person that the agent needs them."
    )
    ap.add_argument("kind", choices=sorted(KINDS))
    ap.add_argument("--message", help="notification text (default depends on kind)")
    ap.add_argument("--voice", action="store_true", help="also speak a short phrase")
    ap.add_argument("--cooldown", type=float, default=DEFAULT_COOLDOWN, help="seconds")
    ap.add_argument("--force", action="store_true", help="ignore the cooldown")
    ap.add_argument(
        "--wait", action="store_true", help="run in the foreground (testing)"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="print the plan, run nothing"
    )
    args = ap.parse_args(argv)

    steps = plan(args.kind, args.message, args.voice)
    if args.dry_run:
        print(f"backend: {steps['backend']}")
        for cmd in steps["commands"]:
            print("  " + shlex.join(c if len(c) < 80 else c[:77] + "..." for c in cmd))
        if "script" in steps:
            print("powershell script:\n" + steps["script"])
        return 0
    if not args.force and cooling_down(args.kind, args.cooldown):
        return 0
    fire(steps, wait=args.wait)
    return 0


if __name__ == "__main__":
    sys.exit(main())
