"""The workspace in git: its repos are git submodules (STANDARD.md §3a).

The workspace repository holds the shared documents and a pointer to one commit of each repo.
Each repo keeps its own history, branches and remote. Registering a repo moves no file and
rewrites no history: ``git submodule add`` adopts the clone already in place.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import groundwork_core as C

KEY = "workspace_git"  # .groundwork/config.json: "submodules" | "none"
CREDENTIAL = re.compile(r"^[a-z][a-z0-9+.-]*://[^/@\s]*:[^/@\s]*@", re.IGNORECASE)
ROOT_IGNORE = ".env\n.env.*\n!.env.example\n"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _out(cwd: Path, *args: str) -> str:
    r = _git(cwd, *args)
    return r.stdout.strip() if r.returncode == 0 else ""


def is_git(ws: Path) -> bool:
    return C._exists(ws / ".git")


def registered(ws: Path) -> dict[str, str]:
    """``.gitmodules``: path → url."""
    if not C._exists(ws / ".gitmodules"):
        return {}
    paths, urls = {}, {}
    for line in _out(
        ws,
        "config",
        "-f",
        ".gitmodules",
        "--get-regexp",
        r"^submodule\..*\.(path|url)$",
    ).splitlines():
        key, _, val = line.partition(" ")
        name, field = key[len("submodule.") :].rsplit(".", 1)
        (paths if field == "path" else urls)[name] = val
    return {p: urls.get(n, "") for n, p in paths.items()}


def recorded(ws: Path) -> dict[str, str]:
    """Paths the workspace index records as a commit pointer (mode 160000): path → sha."""
    out = {}
    for line in _out(ws, "ls-files", "-s").splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if parts and parts[0] == "160000":
            out[path] = parts[1]
    return out


def origin(repo: Path) -> str:
    return _out(repo, "remote", "get-url", "origin")


@dataclass
class Row:
    name: str
    state: str  # submodule | unregistered | no-commit | no-remote | credential-url | not-checked-out
    url: str = ""
    note: str = ""


def survey(ws: Path) -> list[Row]:
    reg = registered(ws) if is_git(ws) else {}
    ptr = recorded(ws) if is_git(ws) else {}
    rows = []
    for kid in C.child_repos(ws):
        name = kid.name
        if name in reg:
            rows.append(Row(name, "submodule", reg[name], _pointer_note(ws, kid, ptr)))
            continue
        url = origin(kid)
        if not _out(kid, "rev-parse", "--verify", "-q", "HEAD"):
            rows.append(
                Row(name, "no-commit", url, "no commit yet (make a first commit)")
            )
        elif not url:
            rows.append(
                Row(
                    name,
                    "no-remote",
                    note="push it to a remote first (git remote add origin <url>)",
                )
            )
        elif CREDENTIAL.match(url):
            rows.append(
                Row(
                    name,
                    "credential-url",
                    note="origin URL holds a password or token; use SSH or a clean HTTPS URL",
                )
            )
        else:
            rows.append(Row(name, "unregistered", url))
    for path, url in sorted(reg.items()):
        if not C._exists(ws / path / ".git"):
            rows.append(
                Row(path, "not-checked-out", url, "run: git submodule update --init")
            )
    return rows


def _pointer_note(ws: Path, repo: Path, ptr: dict[str, str]) -> str:
    head = _out(repo, "rev-parse", "HEAD")
    sha = ptr.get(repo.name, "")
    notes = []
    if _out(repo, "status", "--porcelain"):
        notes.append("uncommitted changes (commit them in the repo)")
    if head and sha and head != sha:
        notes.append(
            f"moved to {head[:7]} (workspace records {sha[:7]}): commit the pointer here"
        )
    if (
        head
        and _out(repo, "remote")
        and not _out(repo, "branch", "-r", "--contains", head)
    ):
        notes.append(f"{head[:7]} is on no remote branch (push the repo first)")
    return "; ".join(notes)


def decision(ws: Path) -> str:
    """'submodules', 'none', or '' (not decided yet)."""
    v = C.read_config(ws).get(KEY, "")
    return (
        v if v in ("submodules", "none") else ("submodules" if registered(ws) else "")
    )


def summary(ws: Path) -> str:
    """One line for the session context and status."""
    d = decision(ws)
    if d == "none":
        return "Workspace git: not tracked (the user chose plain folders)."
    if not d:
        return (
            "Workspace git: NOT DECIDED. Ask the user whether to track the workspace in git with its repos "
            "as submodules (bootstrap skill → Workspace in git)."
        )
    rows = survey(ws)
    subs = [r.name for r in rows if r.state == "submodule"]
    other = [f"{r.name} ({r.state})" for r in rows if r.state != "submodule"]
    line = "Workspace git: submodules (" + (", ".join(subs) or "none yet") + ")"
    if other:
        line += "; not registered: " + ", ".join(other) + " (groundwork.py submodules)"
    return line + ". Commit code inside each repo; commit docs and moved pointers here."


def init(ws: Path, dry: bool = False) -> list[str]:
    """Make ``ws`` a git repository and register every child repo with a clean remote as a submodule."""
    notes = []
    if not is_git(ws):
        notes.append("git init (the workspace becomes a repository)")
        if not dry:
            r = _git(ws, "init", "-q")
            if r.returncode:
                raise SystemExit(r.stderr.strip() or "git init failed")
    gi = ws / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.is_file() else ""
    if ".env" not in text.split():
        notes.append(".gitignore: .env (local secrets never reach git)")
        if not dry:
            gi.write_text(
                (text.rstrip("\n") + "\n" if text else "") + ROOT_IGNORE,
                encoding="utf-8",
            )
    for row in survey(ws):
        if row.state == "unregistered":
            notes.append(f"submodule {row.name} ← {row.url}")
            if not dry:
                r = _git(ws, "submodule", "add", "--", row.url, row.name)
                if r.returncode:
                    notes[-1] += (
                        f"  FAILED: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'git error'}"
                    )
        elif row.state != "submodule":
            notes.append(f"skipped {row.name}: {row.note}")
    if not dry:
        # refuse to push a workspace whose pointers name commits the repos have not pushed
        _git(ws, "config", "push.recurseSubmodules", "check")
        C.write_config(ws, level="workspace", **{KEY: "submodules"})
    return notes


def problems(ws: Path) -> list[tuple[Path, str, str]]:
    """GW006 findings: (path, message, hint) for a workspace that is in git."""
    if not is_git(ws) or decision(ws) == "none":
        return []
    out = []
    for row in survey(ws):
        if row.state == "not-checked-out":
            out.append(
                (
                    ws / row.name,
                    "submodule is not checked out",
                    "git submodule update --init",
                )
            )
        elif row.state != "submodule":
            out.append(
                (
                    ws / row.name,
                    "repo is not a submodule of the workspace repository",
                    row.note or "groundwork.py submodules init",
                )
            )
    return out
