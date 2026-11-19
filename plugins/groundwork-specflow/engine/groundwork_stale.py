"""What changed in a document since it was approved.

An approval keeps only a hash of the approved body, so the approved text is found in git history:
the newest committed version of the file whose body hashes the same. Nothing is guessed when it
isn't there (approved, then edited before any commit)."""

from __future__ import annotations

import difflib
import re
import subprocess
from pathlib import Path

import groundwork_core as C

MAX_COMMITS = 200
MAX_LINES = 8
SECTION = re.compile(r"^#{2,3} ", re.MULTILINE)


def _git(cwd: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def approved_version(path: Path, want: str) -> tuple[str, str] | None:
    """(short commit, text) of the newest committed version whose body hash is ``want``."""
    top = _git(path.parent, "rev-parse", "--show-toplevel")
    if not top:
        return None
    root = Path(top.strip()).resolve()
    try:
        rel = path.resolve().relative_to(root).as_posix()
    except ValueError:
        return None
    log = _git(root, "log", f"-n{MAX_COMMITS}", "--format=%h", "--", rel)
    for commit in (log or "").split():
        text = _git(root, "show", f"{commit}:{rel}")
        if text is None:
            continue
        text = text.replace("\r\n", "\n")
        if C.body_hash(text) == want:
            return commit, text
    return None


def _sections(body: str) -> list[tuple[str, list[str]]]:
    """(heading, lines) per section; text before the first heading is '(top)'."""
    out: list[tuple[str, list[str]]] = [("(top)", [])]
    for line in body.strip().splitlines():
        if SECTION.match(line):
            out.append((line.lstrip("#").strip(), []))
        else:
            out[-1][1].append(line)
    return out


def _clip(line: str) -> str:
    line = line.strip()
    return line if len(line) <= 100 else line[:97] + "..."


def describe_change(old: str, new: str) -> list[str]:
    """Section-by-section summary of body changes, with the changed lines themselves."""
    before = dict(_sections(C.split_fm(old)[1]))
    after = _sections(C.split_fm(new)[1])
    out: list[str] = []
    shown = 0
    for head, lines in after:
        if head not in before:
            out.append(f"section added: {head}")
            continue
        old_lines = before.pop(head)
        if old_lines == lines:
            continue
        diff = [
            d
            for d in difflib.unified_diff(old_lines, lines, lineterm="", n=0)
            if d[:1] in "+-" and not d.startswith(("+++", "---"))
        ]
        diff = [d for d in diff if d[1:].strip()]
        if not diff:
            out.append(f"{head}: blank lines only")
            continue
        added = sum(d.startswith("+") for d in diff)
        removed = len(diff) - added
        out.append(f"{head}: +{added} -{removed} line(s)")
        for d in diff:
            if shown >= MAX_LINES:
                break
            out.append(f"    {d[0]} {_clip(d[1:])}")
            shown += 1
    out.extend(f"section removed: {h}" for h in before if h != "(top)" or before[h])
    if shown >= MAX_LINES:
        out.append("    ... (git diff shows the rest)")
    return out


def explain(path: Path, ctx: C.Ctx) -> list[str]:
    """Lines saying what changed in a stale document since its approval."""
    root = C.owner_root(path, ctx)
    rel = path.resolve().relative_to(root.resolve()).as_posix()
    rec = C.load_approvals(root).get(rel)
    if not rec:
        return []
    found = approved_version(path, rec.get("hash", ""))
    if not found:
        return [
            (
                "the approved version was never committed, so what changed can't be shown; "
                "ask the user rather than guessing"
            )
        ]
    commit, old = found
    lines = describe_change(old, path.read_text(encoding="utf-8"))
    head = f"changed since the approved version (commit {commit}):"
    return [head, *lines] if lines else [head + " no visible body change"]


def stale_docs(ctx: C.Ctx) -> list[Path]:
    """Every document with an approval record whose text has changed since."""
    out = []
    for root in dict.fromkeys(r for r in (ctx.repo, ctx.workspace) if r):
        for rel in C.load_approvals(root):
            p = root / rel
            if p.is_file() and C.doc_state(p, ctx).status == "stale":
                out.append(p)
    return out
