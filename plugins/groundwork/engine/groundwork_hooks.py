"""Install `groundwork check` as a git pre-commit (and optionally pre-push) hook.

The hook is a small POSIX shell script. It never replaces someone else's hook: an existing one is
renamed ``<hook>.groundwork-orig`` and called first; ``uninstall`` puts it back.
"""
from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path

import groundwork_core as C

MARKER = "# groundwork-hook v1"

SCRIPT = """#!/bin/sh
{marker}
# Installed by `groundwork.py hooks install`. Runs the Groundwork conformance check.
# Skip once:  git {verb} --no-verify     or     GROUNDWORK_SKIP=1 git {verb} ...
[ "$GROUNDWORK_SKIP" = "1" ] && exit 0
ROOT=$(git rev-parse --show-toplevel) || exit 0
ORIG="$0.groundwork-orig"
if [ -x "$ORIG" ]; then "$ORIG" "$@" || exit $?; fi
GW="$ROOT/.groundwork/engine/groundwork.py"
[ -f "$GW" ] || GW="{engine}"
if [ ! -f "$GW" ]; then
  echo "groundwork: engine not found ($GW); skipping check. Vendor it: groundwork.py hooks install --vendor" >&2
  exit 0
fi
PY=$(command -v python3 || command -v python) || {{ echo "groundwork: python not found; skipping check" >&2; exit 0; }}
"$PY" "$GW" check --hook {strict}"$ROOT" || {{
  echo >&2
  echo "groundwork: {verb} blocked. Fix the findings above, or bypass once with --no-verify." >&2
  exit 1
}}
"""


def hooks_dir(repo: Path) -> Path:
    out = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-path", "hooks"],
                         capture_output=True, text=True, check=True).stdout.strip()
    p = Path(out)
    return p if p.is_absolute() else repo / p


def target_repos(ctx: C.Ctx) -> list[Path]:
    if ctx.level == "workspace":
        repos = C.child_repos(ctx.workspace)
        if (ctx.workspace / ".git").exists():
            repos.insert(0, ctx.workspace)
        return repos
    if ctx.repo:
        return [ctx.repo]
    return []


def _ours(p: Path) -> bool:
    try:
        return MARKER in p.read_text()
    except OSError:
        return False


def vendor(repo: Path) -> Path:
    dest = repo / ".groundwork" / "engine"
    dest.mkdir(parents=True, exist_ok=True)
    src = C.PLUGIN_ROOT / "engine"
    for f in sorted(src.glob("*.py")):          # everything: a new module must never be forgotten
        shutil.copy2(f, dest / f.name)
    for f in dest.glob("*.py"):                 # drop modules that no longer exist upstream
        if not (src / f.name).exists():
            f.unlink()
    # a vendored engine's PLUGIN_ROOT is .groundwork/, so templates and the standard live beside engine/
    shutil.copytree(C.TEMPLATES, dest.parent / "templates", dirs_exist_ok=True)
    shutil.copy2(C.PLUGIN_ROOT / "STANDARD.md", dest.parent / "STANDARD.md")
    return dest


def install(repo: Path, strict: bool = False, pre_push: bool = False, vendored: bool = False) -> list[str]:
    d = hooks_dir(repo)
    d.mkdir(parents=True, exist_ok=True)
    notes = []
    if vendored:
        vendor(repo)
        notes.append("vendored engine into .groundwork/engine/ (commit it so teammates and CI can use it)")
    for name, verb in (("pre-commit", "commit"), ("pre-push", "push")):
        path = d / name
        if name == "pre-push" and not pre_push:
            continue
        if path.exists() and not _ours(path):
            orig = d / f"{name}.groundwork-orig"
            if orig.exists():
                raise SystemExit(f"{orig} already exists; resolve by hand")
            path.rename(orig)
            notes.append(f"kept your existing {name} hook (chained first)")
        path.write_text(SCRIPT.format(marker=MARKER, verb=verb, strict="--strict " if strict else "",
                                      engine=str(C.PLUGIN_ROOT / "engine" / "groundwork.py")))
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        notes.append(f"installed {name}" + (" (strict: warnings also block)" if strict else ""))
    return notes


def uninstall(repo: Path) -> list[str]:
    d = hooks_dir(repo)
    notes = []
    for name in ("pre-commit", "pre-push"):
        path, orig = d / name, d / f"{name}.groundwork-orig"
        if path.exists() and _ours(path):
            path.unlink()
            notes.append(f"removed {name}")
            if orig.exists():
                orig.rename(path)
                notes.append(f"restored your original {name}")
    return notes or ["no groundwork hooks installed"]


def status(repo: Path) -> str:
    d = hooks_dir(repo)
    found = []
    for name in ("pre-commit", "pre-push"):
        p = d / name
        if p.exists() and _ours(p):
            found.append(name + (" [strict]" if "--strict" in p.read_text() else ""))
    v = " + vendored engine" if (repo / ".groundwork" / "engine" / "groundwork.py").exists() else ""
    return (", ".join(found) or "not installed") + v
