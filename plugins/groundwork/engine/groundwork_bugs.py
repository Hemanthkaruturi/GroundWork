"""Bug lifecycle: a bug is a violated (or missing) requirement, and the fix is gated on saying which.

A bug record lives at bugs/NNN-slug.md. Editing code for a bug is allowed only once the record is
*diagnosed*: complete, classified, and tied to the requirements/RFC it concerns, with a named
regression test. The tie-in is checked mechanically against the (approved, non-stale) specs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import groundwork_core as C

SECTIONS = ["Report", "Reproduction", "Diagnosis", "Classification", "Fix plan", "Regression test", "Verification"]
CLASSES = {"code-bug", "spec-gap", "design-flaw"}
STATUSES = ["open", "diagnosed", "fixed", "closed"]
FIELDS = ["id", "title", "status", "severity", "classification", "violates", "amends", "rfc",
          "regression_test", "author", "created"]


@dataclass
class Problem:
    rule: str
    severity: str
    msg: str


@dataclass
class BugState:
    slug: str
    path: Path
    status: str = "?"
    classification: str = "?"
    title: str = ""
    problems: list[Problem] = field(default_factory=list)
    unfinished: int = 0

    @property
    def ready(self) -> bool:
        return self.status == "diagnosed" and not [p for p in self.problems if p.severity == "error"]

    @property
    def next(self) -> str:
        errs = [p.msg for p in self.problems if p.severity == "error"]
        if self.status == "closed":
            return "closed"
        if self.status == "fixed":
            return errs[0] if errs else "fixed — verify (§7), then set status: closed"
        if errs:
            return errs[0] + " (use the fix-bug skill)"
        if self.status == "open":
            return "diagnosis complete: set `status: diagnosed`, then fix"
        return "diagnosed — write the regression test first, then the fix; on success set status: fixed"


def bugs_dir(ctx: C.Ctx) -> Path:
    return (ctx.repo or ctx.root) / "bugs"


def bug_paths(ctx: C.Ctx) -> list[Path]:
    d = bugs_dir(ctx)
    return sorted(d.glob("*.md")) if d.is_dir() else []


def active_bug(ctx: C.Ctx) -> str | None:
    if not ctx.repo:
        return None
    try:
        slug = (ctx.repo / ".groundwork" / "active-bug").read_text().strip()
    except OSError:
        return None
    return slug if slug and (bugs_dir(ctx) / f"{slug}.md").is_file() else None


def _section_text(text: str, n: int) -> str:
    m = re.search(rf"^## {n}\.[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def _requirement_refs(meta: dict) -> list[tuple[str, str]]:
    out = []
    for item in C.list_of(meta, "violates"):
        rid, _, feat = item.partition("@")
        out.append((rid.strip(), feat.strip()))
    return out


def bug_state(ctx: C.Ctx, slug: str) -> BugState:
    path = bugs_dir(ctx) / f"{slug}.md"
    st = BugState(slug, path)
    add = lambda rule, sev, msg: st.problems.append(Problem(rule, sev, msg))   # noqa: E731
    if not path.is_file():
        add("GW060", "error", f"bugs/{slug}.md does not exist")
        return st
    text = path.read_text()
    meta, _ = C.split_fm(text)
    st.status, st.classification = meta.get("status", "?"), meta.get("classification", "?")
    st.title = meta.get("title", slug)
    miss = [f for f in FIELDS if f not in meta]
    if miss:
        add("GW060", "error", "front matter missing: " + ", ".join(miss))
        return st
    if meta["id"] != slug:
        add("GW060", "error", f"id '{meta['id']}' does not match the file name '{slug}'")
    if st.status not in STATUSES:
        add("GW060", "error", f"status must be one of {STATUSES}")
        return st
    body_all = C.split_fm(text)[1]
    body_pre = body_all.split("\n## 7.")[0]           # §7 is filled after the fix
    st.unfinished = len(C.PLACEHOLDER.findall(body_pre))
    if st.unfinished:
        # blocks the gate either way; `check` reports GW064 (still open) as a warning, GW065 (claims diagnosed) as an error
        add("GW064" if st.status == "open" else "GW065", "error",
            f"sections 1–6 still have {st.unfinished} unresolved marker(s)")
    else:
        from groundwork_check import missing_sections  # noqa: PLC0415
        m = missing_sections(text, SECTIONS, numbered=True)
        if m:
            add("GW061", "error", "missing/misordered section(s): " + "; ".join(m))
    # classification requirements — checked whenever the bug claims to be diagnosed or later,
    # and reported as the next step while open so the agent knows what to supply
    cls = st.classification
    if cls not in CLASSES:
        add("GW062", "error", f"classification must be one of {sorted(CLASSES)} (now '{cls}')")
    elif cls == "code-bug":
        refs = _requirement_refs(meta)
        if not refs:
            add("GW062", "error", "code-bug must list the violated requirements in `violates` (e.g. FR-2@001-widgets); "
                                  "if no requirement covers this, it is a spec-gap")
        for rid, feat in refs:
            rc, fd = C.resolve_feature(ctx, feat)
            if fd is None:
                add("GW062", "error", f"violates {rid}@{feat}: that feature does not exist")
                continue
            sp = C.doc_state(fd / "spec.md", rc)
            if not sp.approved:
                add("GW062", "error", f"violates {rid}@{feat}: that spec is {sp.status}, not approved")
            elif f"**{rid}**" not in (fd / "spec.md").read_text():
                add("GW062", "error", f"violates {rid}@{feat}: no such requirement in that spec")
    elif cls == "spec-gap":
        amends = C.list_of(meta, "amends")
        if not amends:
            add("GW062", "error", "spec-gap must list the specs to amend in `amends`")
        for feat in amends:
            rc, fd = C.resolve_feature(ctx, feat)
            if fd is None:
                add("GW062", "error", f"amends {feat}: that feature does not exist")
                continue
            sp = C.doc_state(fd / "spec.md", rc)
            changes = re.search(r"^## Changes\b(.*?)(?=^## |\Z)", (fd / "spec.md").read_text(), re.M | re.S)
            if not changes or slug not in changes.group(1):
                add("GW062", "error", f"amends {feat}: amend its spec first — add a line for '{slug}' under '## Changes'")
            elif not sp.approved:
                add("GW062", "error", f"amends {feat}: the amended spec is {sp.status}; the user must re-approve it")
    elif cls == "design-flaw":
        rp = C.find_rfc(ctx, meta.get("rfc", ""))
        if rp is None:
            add("GW062", "error", "design-flaw needs `rfc:` set to a new or amending RFC (write it with the write-rfc skill)")
        elif not C.doc_state(rp, ctx).approved:
            add("GW062", "error", f"{rp.name} is {C.doc_state(rp, ctx).status}; the user must approve it before the fix")
    if not (meta.get("regression_test") or "").strip() and st.status in ("diagnosed", "fixed", "closed"):
        add("GW062", "error", "name the regression test in `regression_test:` (path relative to the repo)")
    if st.status in ("fixed", "closed"):
        rt = (meta.get("regression_test") or "").strip()
        if rt and not (ctx.repo / rt.split("::")[0]).exists():
            add("GW063", "error", f"regression_test '{rt}' does not exist")
        if not re.sub(r"^_.*_$", "", _section_text(text, 7).strip(), flags=re.S).strip():
            add("GW063", "error", "§7 Verification is empty")
    return st


def new_bug(ctx: C.Ctx, slug: str, title: str | None) -> Path:
    import time  # noqa: PLC0415
    d = bugs_dir(ctx)
    d.mkdir(parents=True, exist_ok=True)
    n = C.next_number([p.name for p in d.glob("*.md")], r"(\d+)-")
    bid = f"{n:03d}-{C.slugify(slug)}"
    p = d / f"{bid}.md"
    p.write_text(C.render("bug.md", id=bid, title=title or slug.replace("-", " ").title(),
                          date=time.strftime("%F"), author=C.signer()))
    (ctx.repo / ".groundwork").mkdir(exist_ok=True)
    (ctx.repo / ".groundwork" / "active-bug").write_text(bid + "\n")
    return p
