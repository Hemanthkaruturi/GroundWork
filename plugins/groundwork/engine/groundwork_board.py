"""The work board: everything in flight, derived from files — so any session can resume any work.

Nothing here is remembered by an agent. RFCs being interviewed, approved RFCs with no spec yet, features
part-way through spec → plan → tasks → evals → build, and open bugs are all read from disk, ordered by
when they were last touched, each with the single next action.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import groundwork_bugs as B
import groundwork_core as C

SKILL_FOR = {"rfc": "write-rfc", "spec": "write-spec", "plan": "write-plan", "tasks": "write-tasks",
             "evals": "write-evals", "implement": "implement", "handover": "handover", "deps": "resume",
             "bug": "fix-bug"}


@dataclass
class Work:
    kind: str                # rfc | feature | bug
    ref: str                 # RFC-0001 | repo/001-slug | repo/bugs/001-slug
    label: str
    state: str
    next: str
    skill: str
    mtime: float = 0.0
    active: bool = False
    note: str = ""
    blocked_by: list[str] = field(default_factory=list)
    repo: str = ""
    owner: str = ""

    def age(self) -> str:
        d = time.time() - self.mtime
        return "just now" if d < 90 else f"{int(d // 60)}m ago" if d < 5400 else \
            f"{int(d // 3600)}h ago" if d < 172800 else f"{int(d // 86400)}d ago"


def _newest(p: Path) -> float:
    try:
        files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
        return max((f.stat().st_mtime for f in files), default=0.0)
    except OSError:
        return 0.0


def last_note(path: Path) -> str:
    try:
        lines = [ln for ln in (path / "log.md").read_text(encoding="utf-8").splitlines() if ln.startswith("- ")]
        return lines[-1][2:] if lines else ""
    except OSError:
        return ""


def _contexts(ctx: C.Ctx) -> list[C.Ctx]:
    if ctx.level == "workspace":
        return [C.detect(k, ctx.workspace) for k in C.child_repos(ctx.workspace)]
    return [ctx] if ctx.level in ("repo", "standalone") else []


def interview_rows(text: str) -> int:
    sec = re.search(r"^## 3\.[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    rows = [ln for ln in (sec.group(1).splitlines() if sec else []) if ln.startswith("|")]
    rows = [r for r in rows[2:] if not C.PLACEHOLDER.search(r)]
    return len(rows)


def collect(ctx: C.Ctx, include_done: bool = False) -> list[Work]:
    if ctx.level == "unknown":
        return []
    out: list[Work] = []
    repos = _contexts(ctx)
    prefix = ctx.level == "workspace"
    # every spec's RFC citation, for "does this RFC have a spec yet?"
    cited: dict[str, list[str]] = {}
    for rc in repos:
        for fdir in C.feature_dirs(rc):
            m, _ = C.split_fm((fdir / "spec.md").read_text(encoding="utf-8")) if (fdir / "spec.md").is_file() else ({}, "")
            if m.get("rfc"):
                cited.setdefault(m["rfc"], []).append(f"{rc.repo.name}/{fdir.name}" if prefix else fdir.name)
    rf = C.rfcs(ctx) if ctx.level != "unknown" else []
    superseded = {x for r in rf if r.approved for x in C.list_of(r.meta, "supersedes")}
    for r in rf:
        rid = r.meta.get("id") or r.path.stem
        if rid in superseded and not include_done:
            continue
        text = r.path.read_text(encoding="utf-8")
        n = interview_rows(text)
        if not r.approved:
            state = ("stale — edited after approval; needs re-approval" if r.status == "stale" else
                     f"in review ({len(set(r.signers))}/{r.needed} sign-offs)" if r.status == "in-review" else
                     f"drafting — {n} interview answer(s) recorded, {r.placeholders} open marker(s)")
            nxt = ("ask the user to review and run /groundwork:approve " + rid) if r.status in ("in-review", "stale") or (
                r.placeholders == 0) else "continue the interview / finish the RFC (interview, write-rfc skills)"
            out.append(Work("rfc", rid, f"{rid} {r.meta.get('title', '')}".strip(), state, nxt,
                            "write-rfc" if r.placeholders else "resume", _newest(r.path), owner=str(r.meta.get("owner", ""))))
        elif not cited.get(rid):
            out.append(Work("rfc", rid, f"{rid} {r.meta.get('title', '')}".strip(), "approved — no spec yet",
                            "write the spec in each repo the RFC touches (write-spec skill)", "write-spec", _newest(r.path),
                            owner=str(r.meta.get("owner", ""))))
        elif include_done:
            out.append(Work("rfc", rid, f"{rid} {r.meta.get('title', '')}".strip(), "approved, specs: " + ", ".join(cited[rid]),
                            "", "", _newest(r.path)))
    for rc in repos:
        rname = rc.repo.name
        act = C.active_slug(rc)
        for fdir in C.feature_dirs(rc):
            if not (fdir / "spec.md").is_file():
                continue
            steps = C.feature_steps(rc, fdir.name)
            done, total = C.task_counts(rc, fdir.name)
            bad = next((s for s in steps if not s.ok), None)
            spec = C.doc_state(fdir / "spec.md", rc)
            blocked = C.dependency_problems(rc, spec)
            if bad:
                phase, state = bad.key, bad.detail
                nxt = C.INSTRUCTIONS.get(bad.key, "")
            elif total and done == total:
                if not include_done:
                    continue
                phase, state, nxt = "done", f"implemented ({done}/{total})", ""
            else:
                phase, state = "implement", f"building — tasks {done}/{total}"
                nxt = "continue the next unchecked task (implement skill)"
            out.append(Work("feature", f"{rname}/{fdir.name}" if prefix else fdir.name,
                            f"{rname}/{fdir.name}" if prefix else fdir.name, state, nxt, SKILL_FOR.get(phase, "resume"),
                            _newest(fdir), active=(act == fdir.name), note=last_note(fdir), blocked_by=blocked, repo=rname,
                            owner=str(spec.meta.get("owner", ""))))
        abug = B.active_bug(rc)
        for bp in B.bug_paths(rc):
            b = B.bug_state(rc, bp.stem)
            if b.status == "closed" and not include_done:
                continue
            out.append(Work("bug", f"{rname}/bugs/{bp.stem}" if prefix else f"bugs/{bp.stem}",
                            (f"{rname}/" if prefix else "") + f"bug {bp.stem}", f"{b.status} ({b.classification})",
                            b.next, "fix-bug", _newest(bp), active=(abug == bp.stem), repo=rname,
                            owner=str(C.split_fm(bp.read_text(encoding="utf-8"))[0].get("owner", ""))))
    out.sort(key=lambda w: (not w.active, -w.mtime))
    return out


def render(items: list[Work]) -> str:
    if not items:
        return "Nothing in flight."
    lines = ["IN FLIGHT (active first, then most recently touched)"]
    for i, w in enumerate(items, 1):
        lines.append(f"{i:>2}. [{w.kind}] {w.label} — {w.state}  ({w.age()}){'  ← active' if w.active else ''}")
        if w.next:
            lines.append(f"      next: {w.next}")
        if w.blocked_by:
            lines.append(f"      blocked by: {'; '.join(w.blocked_by)}")
        if w.owner:
            lines.append(f"      owner: {w.owner}")
        if w.note:
            lines.append(f"      last note: {w.note}")
    return "\n".join(lines)


def to_json(items: list[Work]) -> str:
    return json.dumps([{**w.__dict__} for w in items], indent=2)


def add_note(ctx: C.Ctx, text: str) -> Path:
    """Append a dated line to the active feature's log.md, else the active bug's, else the journal."""
    stamp = time.strftime("%F %H:%M")
    line = f"- {stamp} ({C.signer()}): {text.strip()}\n"
    if ctx.repo and C.active_slug(ctx) and (ctx.repo / "specs" / C.active_slug(ctx)).is_dir():
        target = ctx.repo / "specs" / C.active_slug(ctx) / "log.md"
    else:
        target = (ctx.workspace if ctx.level == "workspace" else (ctx.repo or ctx.root)) / ".groundwork" / "journal.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() and target.name == "log.md":
        target.write_text("# Log\n\n> Append-only. Where work stopped, decisions taken on the way, what to do next.\n\n", encoding="utf-8")
    with target.open("a", encoding="utf-8") as f:
        f.write(line)
    return target
