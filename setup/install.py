"""Install GroundWork into the current project for Devin, without Devin's plugin system.

Works on Linux, macOS, Windows and WSL. Run it from the root of the project you want GroundWork in:

    git clone -q --depth 1 https://github.com/Hemanthkaruturi/GroundWork.git .groundwork-install
    python3 .groundwork-install/setup/install.py        (on Windows: py -3 or python)

It installs into the project's .devin/ folder:
    .devin/groundwork/          the engine, templates and STANDARD.md
    .devin/skills/<name>/       one Devin project skill per GroundWork skill and command
    .devin/hooks.v1.json        the GroundWork hooks (other hooks in the file are kept)
    .devin/groundwork-version   which GroundWork version and commit was installed
A clone in .groundwork-install/ is deleted afterwards, whether or not the install worked.
Running it again updates an existing install.
"""
import datetime
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit(f"error: GroundWork needs Python 3.10 or newer; this is Python {sys.version.split()[0]}.")

SRC_ROOT = Path(__file__).resolve().parents[1]
PLUGIN = SRC_ROOT / "plugins" / "groundwork-specflow"
TARGET = Path.cwd().resolve()
CLONE_DIR = ".groundwork-install"                # the temporary clone the README prompt makes
MARKER = ".groundwork-installed"                 # marks a skill folder this script owns
ENGINE = ".devin/groundwork/engine/groundwork.py"
UTF8 = {"encoding": "utf-8"}


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


def hook_command(cmd: str) -> str:
    """The plugin's hook command, pointed at the project copy of the engine.

    The path is relative to the project root, where Devin runs project hooks, so the command needs no shell
    variables and reads the same in sh, cmd and PowerShell. The fallbacks cover machines that only have
    `python` (many Windows installs) or only the `py` launcher."""
    sub = cmd.split("groundwork.py\" ", 1)[1].split()[0]       # session-context, gate, ...
    return f"python3 {ENGINE} {sub} || python {ENGINE} {sub} || py -3 {ENGINE} {sub}"


def install() -> str:
    devin = TARGET / ".devin"
    home = devin / "groundwork"
    skills = devin / "skills"

    sources = sorted((PLUGIN / "skills").iterdir()) + sorted((PLUGIN / "devin" / "commands").iterdir())
    taken = [s.name for s in sources if (skills / s.name).exists() and not (skills / s.name / MARKER).exists()]
    if taken:
        fail(f".devin/skills/ already has {', '.join(taken)}, not installed by GroundWork. "
             "Rename or remove them, then run this again. Nothing was changed.")

    if subprocess.run(["git", "rev-parse", "--git-dir"], cwd=TARGET, capture_output=True).returncode != 0:
        print("Not a git repository yet; running git init.")
        subprocess.run(["git", "init", "-q"], cwd=TARGET, check=True)

    # 1. The engine, templates and standard. Replaced wholesale on update.
    if home.exists():
        rmtree(home)
    home.mkdir(parents=True)
    shutil.copytree(PLUGIN / "engine", home / "engine", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(PLUGIN / "templates", home / "templates")
    shutil.copy2(PLUGIN / "STANDARD.md", home / "STANDARD.md")

    # 2. Skills and commands as Devin project skills. Paths point at .devin/groundwork, and commands
    #    are /approve, /bypass and /status rather than /groundwork-specflow:approve and so on.
    for old in skills.glob(f"*/{MARKER}"):          # drop skills an earlier version installed
        rmtree(old.parent)
    for src in sources:
        dest = skills / src.name
        dest.mkdir(parents=True)
        for f in src.iterdir():
            write(dest / f.name, read(f).replace("${CLAUDE_PLUGIN_ROOT}", ".devin/groundwork")
                                        .replace("/groundwork-specflow:", "/"))
        write(dest / MARKER, "Installed by GroundWork's setup/install.py. Running it again replaces this folder.\n")

    # 3. Hooks. Same hooks as the plugin, in Devin's project format (event names at the top level).
    ours = json.loads(read(PLUGIN / "hooks" / "hooks.json"))["hooks"]
    for groups in ours.values():
        for group in groups:
            for hook in group["hooks"]:
                hook["command"] = hook_command(hook["command"])
    hooks_file = devin / "hooks.v1.json"
    config = json.loads(read(hooks_file)) if hooks_file.exists() else {}
    def mine(group: dict) -> bool:
        return any(ENGINE in h.get("command", "") for h in group.get("hooks", []))
    for event in list(config):
        config[event] = [g for g in config[event] if not mine(g)]
        if not config[event]:
            del config[event]
    for event, groups in ours.items():
        config.setdefault(event, []).extend(groups)
    write(hooks_file, json.dumps(config, indent=2) + "\n")

    # 4. Undo the earlier bootstrap layout: a plugin copy under .devin/skills listed in requiredPlugins.
    legacy = skills / "groundwork-specflow"
    if (legacy / "engine" / "groundwork.py").exists():
        rmtree(legacy)
    cfg_file = devin / "config.json"
    if cfg_file.exists():
        cfg = json.loads(read(cfg_file))
        required = cfg.get("requiredPlugins")
        if isinstance(required, list) and ".devin/skills/groundwork-specflow" in required:
            cfg["requiredPlugins"] = [p for p in required if p != ".devin/skills/groundwork-specflow"]
            write(cfg_file, json.dumps(cfg, indent=2) + "\n")
    (devin / "groundwork-README.md").unlink(missing_ok=True)

    # 5. Version record.
    version = json.loads(read(PLUGIN / ".claude-plugin" / "plugin.json"))["version"]
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=SRC_ROOT, capture_output=True, text=True).stdout.strip()
    write(devin / "groundwork-version",
          "# Written by GroundWork's setup/install.py. Run it again to update.\n"
          "source=https://github.com/Hemanthkaruturi/GroundWork.git\n"
          f"version={version}\ncommit={sha or 'unknown'}\ninstalled={datetime.date.today().isoformat()}\n")
    print(f"Installed {len(sources)} skills and the hooks into .devin/.")
    return version


def check() -> None:
    """Run the session-start hook exactly as hooks.v1.json says, in this platform's shell, the way Devin will."""
    config = json.loads(read(TARGET / ".devin" / "hooks.v1.json"))
    command = next(h["command"] for g in config["SessionStart"] for h in g["hooks"] if ENGINE in h["command"])
    run = subprocess.run(command, shell=True, cwd=TARGET, input='{"hook_event_name": "SessionStart"}',
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         env={**os.environ, "DEVIN_PROJECT_DIR": str(TARGET)})
    if run.returncode != 0 or "groundwork is active" not in run.stdout:
        output = "\n".join((run.stdout + run.stderr).strip().splitlines()[:20])
        fail(f"GroundWork was copied into .devin/, but its session-start hook did not run correctly:\n{output}")


def main() -> None:
    if not (PLUGIN / "engine" / "groundwork.py").exists():
        fail(f"{SRC_ROOT} is not a GroundWork checkout (no plugins/groundwork-specflow/engine/groundwork.py).")
    if TARGET == SRC_ROOT or SRC_ROOT in TARGET.parents:
        fail("run this from your project's root, not from inside the GroundWork clone.")
    temporary = SRC_ROOT == TARGET / CLONE_DIR
    try:
        version = install()
        check()
    finally:
        if temporary:
            rmtree(SRC_ROOT)
    print()
    print(f"GroundWork {version} is installed in .devin/ and checked: its session-start hook runs.")
    print("It loads when a Devin session starts, so it takes effect from the next session in this project.")
    print("In that session, GroundWork leads the way. If the project documents don't exist yet, "
          "it starts by writing them with you.")
    print("To share GroundWork with your team, commit the .devin/ folder.")


if __name__ == "__main__":
    main()
