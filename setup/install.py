"""Install GroundWork into the current project for Devin or Codex, without their plugin systems.

Works on Linux, macOS, Windows and WSL. Run it from the root of the project you want GroundWork in:

    git clone -q --depth 1 https://github.com/Hemanthkaruturi/GroundWork.git .groundwork-install
    python3 .groundwork-install/setup/install.py        (on Windows: py -3 or python)
    python3 .groundwork-install/setup/install.py --codex    (for Codex)

For Devin, it installs into the project's .devin/ folder:
    .devin/groundwork/          the engine, templates and STANDARD.md
    .devin/skills/<name>/       one Devin project skill per GroundWork skill and command
    .devin/hooks.v1.json        the GroundWork hooks (other hooks in the file are kept)
    .devin/groundwork-version   which GroundWork version and commit was installed
For Codex (--codex):
    .codex/groundwork/          the engine, templates and STANDARD.md
    .agents/skills/<name>/      one Codex project skill per GroundWork skill and command
    .codex/hooks.json           the GroundWork hooks (other hooks in the file are kept)
    .codex/groundwork-version   which GroundWork version and commit was installed
A clone in .groundwork-install/ is deleted afterwards, whether or not the install worked.
Running it again updates an existing install. With --uninstall, it removes GroundWork from the folder's .devin/
(or, with --codex, from .codex/ and .agents/skills/).
"""

import datetime
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

if sys.version_info < (3, 10):  # noqa: UP036 -- friendly exit for users on older Python
    sys.exit(
        f"error: GroundWork needs Python 3.10 or newer; this is Python {sys.version.split()[0]}."
    )

SRC_ROOT = Path(__file__).resolve().parents[1]
PLUGIN = SRC_ROOT / "plugins" / "groundwork-specflow"
TARGET = Path.cwd().resolve()
CLONE_DIR = ".groundwork-install"  # the temporary clone the README prompt makes
MARKER = ".groundwork-installed"  # marks a skill folder this script owns
UTF8 = {"encoding": "utf-8"}


class Host:
    """Where one agent harness keeps project skills and hooks, and how it names commands."""

    def __init__(self, name, folder, skills, hooks, wrapped, prefix, env):
        self.name = name  # "Devin" or "Codex"
        self.folder = folder  # the harness's project folder: .devin or .codex
        self.home = f"{folder}/groundwork"
        self.engine = f"{self.home}/engine/groundwork.py"
        self.skills = skills  # project skills folder
        self.hooks = hooks  # project hooks file
        self.wrapped = (
            wrapped  # hooks under a top-level "hooks" key (Codex) or not (Devin)
        )
        self.prefix = prefix  # how the user types a command: /approve or $approve
        self.env = env  # the harness's project-dir variable, if it sets one


DEVIN = Host(
    "Devin",
    ".devin",
    ".devin/skills",
    ".devin/hooks.v1.json",
    False,
    "/",
    "DEVIN_PROJECT_DIR",
)
CODEX = Host("Codex", ".codex", ".agents/skills", ".codex/hooks.json", True, "$", None)
HOST = CODEX if "--codex" in sys.argv[1:] else DEVIN
ENGINE = HOST.engine


def fail(message: str) -> None:
    sys.exit(f"error: {message}")


def read(path: Path) -> str:
    return path.read_text(**UTF8)


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def rmtree(path: Path) -> None:
    """Delete a folder, including a git clone's read-only files on Windows."""

    def make_writable(func, p, *_):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=make_writable)
    else:
        shutil.rmtree(path, onerror=make_writable)


# What every hook runs. Python finds the engine itself: in DEVIN_PROJECT_DIR (or the working directory) or the
# nearest folder above it with .devin/groundwork, since Devin may run hooks from a subfolder. If there is no engine,
# it warns and exits 0, so a broken install can't block every prompt, including the one that reinstalls it.
# Single quotes only, and no $, %, ` or !, so the same text works in bash, sh, cmd and PowerShell.
# Codex sets no project-dir variable and may also start in a subfolder, so it relies on the working directory.
LAUNCHER = (
    "import os,sys,runpy;from pathlib import Path as P;"
    "d=P({start}).resolve();"
    "e=next((x/'{engine}' for x in (d,*d.parents) "
    "if (x/'{engine}').is_file()),None);"
    "e or sys.exit(print('groundwork: engine not found in {home}, so its hooks are off. "
    "Paste the GroundWork install prompt again to fix it.',file=sys.stderr));"
    "sys.path.insert(0,str(e.parent));sys.argv=[str(e),'{sub}'];runpy.run_path(str(e),run_name='__main__')"
)


def hook_command(cmd: str) -> str:
    """The plugin's hook command, rewritten to run the project copy of the engine through LAUNCHER.

    The fallbacks cover machines with only `python` (many Windows installs) or only the `py` launcher."""
    sub = cmd.split('groundwork.py" ', 1)[1].split()[0]  # session-context, gate, ...
    start = (
        f"os.environ.get('{HOST.env}') or os.getcwd()" if HOST.env else "os.getcwd()"
    )
    code = (
        LAUNCHER.replace("{start}", start)
        .replace("{engine}", HOST.engine)
        .replace("{home}", HOST.home)
        .replace("{sub}", sub)
    )
    return " || ".join(f'{py} -c "{code}"' for py in ("python3", "python", "py -3"))


def install() -> str:
    devin = TARGET / HOST.folder
    home = TARGET / HOST.home
    skills = TARGET / HOST.skills

    sources = sorted((PLUGIN / "skills").iterdir()) + sorted(
        (PLUGIN / "devin" / "commands").iterdir()
    )
    taken = [
        s.name
        for s in sources
        if (skills / s.name).exists() and not (skills / s.name / MARKER).exists()
    ]
    if taken:
        fail(
            f"{HOST.skills}/ already has {', '.join(taken)}, not installed by GroundWork. "
            "Rename or remove them, then run this again. Nothing was changed."
        )

    if (
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=TARGET,
            capture_output=True,
            check=False,
        ).returncode
        != 0
    ):
        print("Not a git repository yet; running git init.")
        subprocess.run(["git", "init", "-q"], cwd=TARGET, check=True)

    # 1. The engine, templates and standard. Replaced wholesale on update.
    if home.exists():
        rmtree(home)
    home.mkdir(parents=True)
    shutil.copytree(
        PLUGIN / "engine", home / "engine", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copytree(PLUGIN / "templates", home / "templates")
    shutil.copy2(PLUGIN / "STANDARD.md", home / "STANDARD.md")

    # 2. Skills and commands as project skills. Paths point at the engine copy, and commands are /approve
    #    (Devin) or $approve (Codex) rather than /groundwork-specflow:approve and so on.
    for old in skills.glob(f"*/{MARKER}"):  # drop skills an earlier version installed
        rmtree(old.parent)
    commands = {c.name for c in (PLUGIN / "devin" / "commands").iterdir()}
    for src in sources:
        dest = skills / src.name
        dest.mkdir(parents=True)
        for f in src.iterdir():
            write(dest / f.name, skill_text(read(f)))
        if HOST is CODEX and src.name in commands:
            # Approve, bypass and status are the user's to type: Codex must not pick them on its own.
            (dest / "agents").mkdir()
            write(
                dest / "agents" / "openai.yaml",
                "policy:\n  allow_implicit_invocation: false\n",
            )
        write(
            dest / MARKER,
            "Installed by GroundWork's setup/install.py. Running it again replaces this folder.\n",
        )

    # 3. Hooks. Same hooks as the plugin, in the project format: event names at the top level for Devin,
    #    under a "hooks" key for Codex.
    ours = json.loads(read(PLUGIN / "hooks" / "hooks.json"))["hooks"]
    for groups in ours.values():
        for group in groups:
            for hook in group["hooks"]:
                hook["command"] = hook_command(hook["command"])
    hooks_file = TARGET / HOST.hooks
    whole = json.loads(read(hooks_file)) if hooks_file.exists() else {}
    config = whole.setdefault("hooks", {}) if HOST.wrapped else whole

    def mine(group: dict) -> bool:
        return any(ENGINE in h.get("command", "") for h in group.get("hooks", []))

    for event in list(config):
        config[event] = [g for g in config[event] if not mine(g)]
        if not config[event]:
            del config[event]
    for event, groups in ours.items():
        config.setdefault(event, []).extend(groups)
    write(hooks_file, json.dumps(whole, indent=2) + "\n")

    # 4. Undo the earlier Devin bootstrap layout: a plugin copy under .devin/skills listed in requiredPlugins.
    if HOST is DEVIN:
        undo_devin_bootstrap(devin, skills)

    # 5. Version record.
    version = json.loads(read(PLUGIN / ".claude-plugin" / "plugin.json"))["version"]
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=SRC_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    write(
        devin / "groundwork-version",
        "# Written by GroundWork's setup/install.py. Run it again to update.\n"
        "source=https://github.com/Hemanthkaruturi/GroundWork.git\n"
        f"version={version}\ncommit={sha or 'unknown'}\ninstalled={datetime.datetime.now().astimezone().date().isoformat()}\n",
    )
    print(
        f"Installed {len(sources)} skills into {HOST.skills}/ and the hooks into {HOST.hooks}."
    )
    return version


def skill_text(text: str) -> str:
    """A plugin skill's text, rewritten for a project install."""
    text = text.replace("${CLAUDE_PLUGIN_ROOT}", HOST.home).replace(
        "/groundwork-specflow:", HOST.prefix
    )
    if HOST is CODEX:
        # Devin-only front matter, and Devin's argument placeholder, which Codex does not fill in.
        text = "".join(
            ln
            for ln in text.splitlines(keepends=True)
            if not ln.startswith("triggers:")
        )
        text = text.replace("$ARGUMENTS", "<what the user typed after the command>")
    return text


def undo_devin_bootstrap(devin: Path, skills: Path) -> None:
    legacy = skills / "groundwork-specflow"
    if (legacy / "engine" / "groundwork.py").exists():
        rmtree(legacy)
    cfg_file = devin / "config.json"
    if cfg_file.exists():
        cfg = json.loads(read(cfg_file))
        required = cfg.get("requiredPlugins")
        if (
            isinstance(required, list)
            and ".devin/skills/groundwork-specflow" in required
        ):
            cfg["requiredPlugins"] = [
                p for p in required if p != ".devin/skills/groundwork-specflow"
            ]
            write(cfg_file, json.dumps(cfg, indent=2) + "\n")
    (devin / "groundwork-README.md").unlink(missing_ok=True)


def uninstall() -> None:
    """Remove what install() added to this folder, keeping everything else."""
    devin = TARGET / HOST.folder
    removed = 0
    for path in [
        TARGET / HOST.home,
        *(m.parent for m in (TARGET / HOST.skills).glob(f"*/{MARKER}")),
    ]:
        if path.exists():
            rmtree(path)
            removed += 1
    hooks_file = TARGET / HOST.hooks
    if hooks_file.exists():
        whole = json.loads(read(hooks_file))
        config = whole.get("hooks", {}) if HOST.wrapped else whole
        for event in list(config):
            config[event] = [
                g
                for g in config[event]
                if not any(ENGINE in h.get("command", "") for h in g.get("hooks", []))
            ]
            if not config[event]:
                del config[event]
        if HOST.wrapped and not config:
            whole.pop("hooks", None)
        if whole:
            write(hooks_file, json.dumps(whole, indent=2) + "\n")
        else:
            hooks_file.unlink()
        removed += 1
    (devin / "groundwork-version").unlink(missing_ok=True)
    where = TARGET if HOST is CODEX else devin
    print(
        f"GroundWork removed from {where}."
        if removed
        else f"GroundWork is not installed in {where}."
    )


def check() -> None:
    """Run the session-start hook exactly as the hooks file says, in this platform's shell, the way the harness will."""
    config = json.loads(read(TARGET / HOST.hooks))
    if HOST.wrapped:
        config = config["hooks"]
    command = next(
        h["command"]
        for g in config["SessionStart"]
        for h in g["hooks"]
        if ENGINE in h["command"]
    )
    run = subprocess.run(
        command,
        shell=True,
        cwd=TARGET,
        input='{"hook_event_name": "SessionStart"}',
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, HOST.env: str(TARGET)} if HOST.env else dict(os.environ),
        check=False,
    )
    if run.returncode != 0 or "groundwork is active" not in run.stdout:
        output = "\n".join((run.stdout + run.stderr).strip().splitlines()[:20])
        fail(
            f"GroundWork was copied into {HOST.folder}/, but its session-start hook did not run correctly:\n{output}"
        )


def main() -> None:
    if not (PLUGIN / "engine" / "groundwork.py").exists():
        fail(
            f"{SRC_ROOT} is not a GroundWork checkout (no plugins/groundwork-specflow/engine/groundwork.py)."
        )
    if TARGET == SRC_ROOT or SRC_ROOT in TARGET.parents:
        fail("run this from your project's root, not from inside the GroundWork clone.")
    temporary = SRC_ROOT == TARGET / CLONE_DIR
    try:
        if "--uninstall" in sys.argv[1:]:
            uninstall()
            return
        if TARGET == Path.home().resolve():
            fail(
                f"this is your home folder ({TARGET}), not a project. Its {HOST.folder}/ folder holds {HOST.name}'s "
                f"settings for every project. Open {HOST.name} in your project's folder and run the install there."
            )
        version = install()
        check()
    finally:
        if temporary:
            rmtree(SRC_ROOT)
    print()
    if HOST is CODEX:
        print(
            f"GroundWork {version} is installed in .codex/ and .agents/skills/ and checked: its session-start hook runs."
        )
        print(
            "Codex runs project hooks only in a trusted project, and only after you trust the hooks themselves."
        )
        print(
            "Next: open codex in this project, trust the project if asked, type /hooks and trust the GroundWork"
        )
        print(
            "hooks, then start a new session and type $bootstrap. That sets GroundWork up for the project: it runs"
        )
        print("groundwork init and writes the project documents with you.")
        print(
            "To share GroundWork with your team, commit the .codex/ and .agents/ folders."
        )
        if plugin_installed():
            print()
            print(
                "Warning: GroundWork is also installed as a Codex plugin, so its hooks would run twice. Use one or"
            )
            print(
                "the other: `codex plugin remove groundwork-specflow@<marketplace>` removes the plugin."
            )
        return
    print(
        f"GroundWork {version} is installed in .devin/ and checked: its session-start hook runs."
    )
    print(
        "It loads when a Devin session starts, so it takes effect from the next session in this project."
    )
    print(
        "Next: open a new Devin session in this project and type /bootstrap. That sets GroundWork up for the"
    )
    print("project: it runs groundwork init and writes the project documents with you.")
    print("To share GroundWork with your team, commit the .devin/ folder.")


def plugin_installed() -> bool:
    """Is the GroundWork plugin also enabled in this user's Codex config?"""
    cfg = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"
    try:
        return '[plugins."groundwork-specflow@' in read(cfg)
    except OSError:
        return False


if __name__ == "__main__":
    main()
