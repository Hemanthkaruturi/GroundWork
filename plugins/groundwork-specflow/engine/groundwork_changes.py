"""Change logs. specs/NNN-slug/changes.md records every change made to a feature after it was built; specs/changes.md
records standalone changes that belong to no feature (upgrading a package, a CI tweak).

A small change needs no new RFC, but it must not be lost: each one gets a row saying who asked, who made it, what
changed, when, and which document it belongs to. Behaviour changes still amend the spec (its `## Changes` section and
re-approval); these logs record what happened to the code. A standalone change is opened by a person with
/groundwork-specflow:change <what>, which lifts the code gate like a bypass and writes a pending row; the agent completes
that row with `groundwork.py change --standalone` when the work is done."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

import groundwork_core as C

COLUMNS = """
| When | Requested by | Implemented by | What changed | Files | Ref |
|---|---|---|---|---|---|
"""
HEADER = (
    """\
# Changes

> Append-only. One row per change made to this feature after it was built: who asked, who made it, what changed,
> when, and the document it belongs to. Read this file, the RFC and the spec before changing the feature's code.
> Behaviour changes also amend the spec (`## Changes`) and need re-approval. Add rows with `groundwork.py change`.
"""
    + COLUMNS
)
STANDALONE_HEADER = (
    """\
# Standalone changes

> Append-only. Changes that belong to no RFC or feature, such as upgrading a package. A person opens each one with
> /groundwork-specflow:change <what>; the agent completes its row with `groundwork.py change --standalone`. A change to
> what a spec describes is not standalone: it belongs to that feature.
"""
    + COLUMNS
)
STANDALONE = "standalone"
PENDING = "pending"

ROW = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\|", re.MULTILINE)


def path(ctx: C.Ctx, slug: str | None) -> Path:
    """A feature's change log, or the repo's standalone one when slug is None."""
    specs = (ctx.repo or ctx.root) / "specs"
    return specs / slug / "changes.md" if slug else specs / "changes.md"


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|") or "—"


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(_cell(c) for c in cells) + " |\n"


def _by(via: str | None) -> str:
    return C.signer() + (f" (via {via})" if via else "")


def _files(files: list[str]) -> str:
    return ", ".join(f"`{f}`" for f in files)


def default_ref(ctx: C.Ctx, slug: str) -> str:
    rfc = str(C.spec_meta(ctx.repo / "specs" / slug).get("rfc", "") or "").strip()
    return f"{rfc} · {slug}" if rfc else slug


def _open(target: Path, header: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(header, encoding="utf-8")


def add(
    ctx: C.Ctx,
    slug: str,
    what: str,
    requested_by: str,
    files: list[str],
    ref: str | None,
    via: str | None,
) -> Path:
    target = path(ctx, slug)
    if not target.parent.is_dir():
        raise SystemExit(f"specs/{slug}/ does not exist.")
    if not what.strip() or not requested_by.strip():
        raise SystemExit("A change needs what changed and who requested it.")
    _open(target, HEADER)
    row = [time.strftime("%F %H:%M"), requested_by, _by(via), what, _files(files)]
    with target.open("a", encoding="utf-8") as f:
        f.write(_row([*row, ref or default_ref(ctx, slug)]))
    return target


def request_standalone(ctx: C.Ctx, what: str) -> Path:
    """The person's /change: a pending row, requested by them, for the agent to complete."""
    target = path(ctx, None)
    _open(target, STANDALONE_HEADER)
    row = [time.strftime("%F %H:%M"), C.signer(), PENDING, what, "", STANDALONE]
    with target.open("a", encoding="utf-8") as f:
        f.write(_row(row))
    return target


def complete_standalone(
    ctx: C.Ctx,
    what: str,
    requested_by: str | None,
    files: list[str],
    ref: str | None,
    via: str | None,
) -> Path:
    """Fill in the newest pending standalone row, or add a finished row when none is pending."""
    target = path(ctx, None)
    lines = (
        target.read_text(encoding="utf-8").splitlines(keepends=True)
        if target.is_file()
        else []
    )
    for i in range(len(lines) - 1, -1, -1):
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", lines[i].strip())[1:-1]]
        if len(cells) == 6 and ROW.match(lines[i]) and cells[2] == PENDING:
            done = what.strip()
            cells[2] = _by(via)
            if done:
                cells[3] += f"; done: {done}"
            cells[4] = _files(files) or cells[4]
            cells[5] = ref or cells[5]
            lines[i] = "| " + " | ".join(c or "—" for c in cells) + " |\n"
            target.write_text("".join(lines), encoding="utf-8")
            return target
    if not what.strip() or not (requested_by or "").strip():
        raise SystemExit(
            "No standalone change is pending. A person opens one with /groundwork-specflow:change <what>; "
            "to record one after the fact, give what changed and --requested-by <person>."
        )
    _open(target, STANDALONE_HEADER)
    row = [time.strftime("%F %H:%M"), requested_by, _by(via), what, _files(files)]
    with target.open("a", encoding="utf-8") as f:
        f.write(_row([*row, ref or STANDALONE]))
    return target


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _changed_at(root: Path, rel: str) -> float:
    """When a path last changed: its mtime if it differs from HEAD, else its last commit."""
    if _git(root, "status", "--porcelain", "--", rel).strip():
        try:
            return (root / rel).stat().st_mtime
        except OSError:
            return time.time()
    out = _git(root, "log", "-1", "--format=%ct", "--", rel).strip()
    return float(out) if out.isdigit() else 0.0


def code_changed_at(root: Path) -> tuple[float, str]:
    """The newest change to code (anything that is not a document), committed or not, and which file."""
    newest, which = 0.0, ""
    for line in _git(
        root, "status", "--porcelain", "--untracked-files=all"
    ).splitlines():
        rel = line[3:].split(" -> ")[-1].strip().strip('"')
        if not rel or C.is_doc_path(root / rel, root):
            continue
        try:
            t = (root / rel).stat().st_mtime
        except OSError:
            t = time.time()  # deleted
        if t > newest:
            newest, which = t, rel
    log = _git(root, "log", "-20", "--format=@%ct", "--name-only")
    stamp = 0.0
    for line in log.splitlines():
        if line.startswith("@"):
            stamp = float(line[1:]) if line[1:].isdigit() else 0.0
        elif line.strip() and stamp > newest and not C.is_doc_path(root / line, root):
            newest, which = stamp, line.strip()
    return newest, which


def unrecorded(ctx: C.Ctx) -> tuple[str, str] | None:
    """(slug, file) when code changed after the active feature was built and its changes.md records nothing since."""
    if not ctx.repo or not (ctx.repo / ".git").exists():
        return None
    import groundwork_bugs as B

    slug = C.active_slug(ctx)
    if not slug or B.active_bug(ctx):
        return None
    fdir = ctx.repo / "specs" / slug
    if not (fdir / "handover.md").is_file() or C.origin(C.spec_meta(fdir)):
        return None
    since = _changed_at(ctx.repo, f"specs/{slug}/handover.md")
    log = path(ctx, slug)
    if log.is_file() and ROW.search(log.read_text(encoding="utf-8")):
        since = max(since, _changed_at(ctx.repo, f"specs/{slug}/changes.md"))
    t, which = code_changed_at(ctx.repo)
    return (slug, which) if t > since else None
