"""groundwork check — does this project conform to the Groundwork standard?

Each rule has a stable id (GWnnn) documented in STANDARD.md. The checker is deterministic and
needs no model, so the same result appears on a laptop, in a git hook and in CI.

Documents that still contain [TODO]/[NEEDS CLARIFICATION] markers are *unfinished*: they get one
warning (GW002/GW025) and are otherwise skipped, because a scaffold cannot yet be judged on shape.
Finished documents are held to the standard in full.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

import groundwork_brevity as V
import groundwork_bugs as B
import groundwork_core as C
import groundwork_fresh as F
import groundwork_people as PP
import groundwork_relations as R

# --- the shape of every governed document (STANDARD.md §4) ----------------------------

FOUNDATION_SECTIONS = {   # keys: upper-case stem + ".md"; matching is case-insensitive
    "PROJECT.md": ["What this is", "Who it is for", "Why now", "Scope", "Who works on what",
                   "Stakeholders and decision makers", "Repositories in this product", "Glossary"],
    "ARCHITECTURE.md": ["Overview", "Components and repositories", "Data flow", "Tech stack and tools",
                        "Deployment and environments", "Boundaries and contracts",
                        "Cross-cutting concerns", "Local development"],
    "CONSTITUTION.md": ["Principles", "Guardrails", "Quality gates", "Amendments"],
}
RFC_SECTIONS = ["Summary", "The need", "Interview record", "Proposal", "Alternatives considered",
                "Risks and objections", "Impact", "Cross-repo contract", "Out of scope", "Open questions"]
SPEC_SECTIONS = ["Problem", "Users and context", "User stories", "Functional requirements",
                 "Non-functional requirements", "Acceptance criteria", "Failure behaviour",
                 "Manual test", "Out of scope", "Constitution check"]
PLAN_SECTIONS = ["Approach", "Affected modules and files", "Data model and migrations",
                 "Interfaces and contracts", "Failure modes and edge cases", "Test strategy",
                 "Rollout and rollback", "Constitution check"]
RFC_FIELDS = ["id", "title", "status", "classification", "signoffs_required", "author", "created"]
CLASSIFICATIONS = {"internal", "api"}


@dataclass
class Finding:
    id: str
    severity: str        # error | warning
    path: str
    message: str
    hint: str = ""


class Report:
    def __init__(self, base: Path):
        self.base = base
        self.items: list[Finding] = []

    def add(self, id: str, sev: str, path: Path | str, msg: str, hint: str = "") -> None:
        p = Path(path)
        try:
            p = p.resolve().relative_to(self.base.resolve())
        except ValueError:
            pass
        self.items.append(Finding(id, sev, str(p), msg, hint))

    def err(self, id, path, msg, hint=""): self.add(id, "error", path, msg, hint)
    def warn(self, id, path, msg, hint=""): self.add(id, "warning", path, msg, hint)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.items if f.severity == "error"]


# --- helpers --------------------------------------------------------------------------

def _norm(s: str) -> str:
    s = re.sub(r"`[^`]*`", "", s)
    s = re.sub(r"\(.*?\)", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def headings(text: str, numbered: bool) -> list[tuple[int | None, str]]:
    out = []
    for m in re.finditer(r"^## (?:(\d+)\.\s*)?(.+?)\s*$", text, re.M):
        if numbered and m.group(1) is None:
            continue
        out.append((int(m.group(1)) if m.group(1) else None, _norm(m.group(2))))
    return out


def missing_sections(text: str, required: list[str], numbered: bool) -> list[str]:
    """Required sections absent, or present but out of the standard order."""
    have = headings(text, numbered)
    bad = []
    for i, name in enumerate(required, 1):
        want = _norm(name)
        ok = any(h.startswith(want) and (not numbered or n == i) for n, h in have)
        if not ok:
            bad.append(f"{i}. {name}" if numbered else name)
    return bad


def section_body(text: str, n: int) -> str:
    m = re.search(rf"^## {n}\.[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


# --- checks ---------------------------------------------------------------------------

def check_version(ctx: C.Ctx, r: Report) -> None:
    base = ctx.workspace if ctx.level == "workspace" else ctx.repo
    cfg = C.read_config(base)
    v = cfg.get("standard")
    cfg_path = base / ".groundwork" / "config.json"
    if not v:
        r.warn("GW004", cfg_path, "no standard version recorded",
               f'add "standard": "{C.STANDARD_VERSION}" to .groundwork/config.json')
    elif str(v).split(".")[0] != C.STANDARD_VERSION.split(".")[0]:
        r.err("GW005", cfg_path, f"project follows standard {v}; this Groundwork implements "
              f"{C.STANDARD_VERSION} (different major version)", "upgrade the plugin or migrate the project")


def check_foundation(ctx: C.Ctx, r: Report) -> None:
    base = ctx.workspace if ctx.level == "workspace" else ctx.repo
    missing, unfinished = C._gaps_at(ctx.level, base, "")
    for m in missing:
        r.err("GW001", base / m, "required foundation item is missing", "run: groundwork.py scaffold")
    for u in unfinished:
        r.warn("GW002", base / u, "foundation document is unfinished (contains [TODO] or [NEEDS CLARIFICATION] markers)")
    spec = C.FOUNDATION[ctx.level]
    for f in spec["files"]:
        p = C._find_ci(base, f)
        key = f.upper().removesuffix(".MD") + ".md"
        if p is None or key not in FOUNDATION_SECTIONS or f in unfinished:
            continue
        miss = missing_sections(p.read_text(), FOUNDATION_SECTIONS[key], numbered=False)
        if miss:
            r.err("GW003", p, "missing required section(s): " + "; ".join(miss),
                  "keep the template's headings; see STANDARD.md §4")


def check_freshness(ctx: C.Ctx, r: Report) -> None:
    base = ctx.workspace if ctx.level == "workspace" else ctx.repo
    for d in F.assess(ctx):
        path = C._find_ci(base, d.doc) or base / d.doc
        if d.status == "unconfirmed":
            r.warn("GW051", path, "never confirmed against reality", "run: groundwork.py confirm " + d.doc)
        elif d.status == "stale":
            r.warn("GW050", path, "may be stale — " + "; ".join(d.reasons),
                   "update the document (refresh skill), then: groundwork.py confirm " + d.doc)


def _approval_claims(r: Report, st: C.DocState, rule: str) -> None:
    claimed = st.meta.get("status") == "approved"
    if claimed and not st.approved:
        why = "edited after approval" if st.status == "stale" else "no approval record exists"
        r.err(rule, st.path, f"front matter says approved but the approval is invalid ({why})",
              "a human must run /groundwork:approve again")


def check_rfcs(ctx: C.Ctx, r: Report) -> None:
    d = ctx.rfc_home / "DECISIONS"
    if not d.is_dir():
        return
    index = (d / "README.md").read_text() if (d / "README.md").is_file() else ""
    for st in C.rfcs(ctx):
        p, meta = st.path, st.meta
        text = p.read_text()
        if st.placeholders:
            r.warn("GW025", p, f"RFC is unfinished ({st.placeholders} unresolved marker(s))")
        miss = [f for f in RFC_FIELDS if f not in meta]
        if miss:
            r.err("GW010", p, "front matter missing: " + ", ".join(miss)); continue
        if not p.name.startswith(meta["id"] + "-"):
            r.err("GW010", p, f"id '{meta['id']}' does not match the filename")
        if meta["classification"] not in CLASSIFICATIONS:
            r.err("GW010", p, f"classification must be one of {sorted(CLASSIFICATIONS)}")
        if not re.fullmatch(r"\d+", str(meta["signoffs_required"])):
            r.err("GW010", p, "signoffs_required must be a whole number")
        _approval_claims(r, st, "GW013")
        for key in ("supersedes", "related_rfcs"):
            for ref in C.list_of(meta, key):
                if C.find_rfc(ctx, ref) is None:
                    r.err("GW015", p, f"{key}: {ref} does not exist")
        if meta["id"] not in index:
            r.warn("GW014", p, "not listed in DECISIONS/README.md")
        if st.placeholders:
            continue
        miss = missing_sections(text, RFC_SECTIONS, numbered=True)
        if miss:
            r.err("GW011", p, "missing/misordered section(s): " + "; ".join(miss))
        if meta["classification"] == "api":
            body = strip_comments(section_body(text, 8))
            if not body or body.lower().startswith("n/a"):
                r.err("GW012", p, "api RFC has no cross-repo contract in §8")
            if str(meta["signoffs_required"]).isdigit() and int(meta["signoffs_required"]) < 2:
                r.err("GW012", p, "api RFC needs signoffs_required >= 2 (every lead it touches)")


def _ids(text: str, kind: str) -> list[str]:
    return re.findall(rf"\*\*({kind}-\d+)\*\*", text)


def check_features(ctx: C.Ctx, r: Report) -> None:
    for fdir in C.feature_dirs(ctx):
        if not re.fullmatch(r"\d{3}-[a-z0-9]+(-[a-z0-9]+)*", fdir.name):
            r.err("GW020", fdir, "feature directory must be NNN-slug (lowercase, hyphens)"); continue
        absent = [n for n in ("spec", "plan", "tasks", "evals") if not (fdir / f"{n}.md").is_file()]
        if absent:
            r.err("GW020", fdir, "missing: " + ", ".join(n + ".md" for n in absent)); continue
        spec = C.doc_state(fdir / "spec.md", ctx)
        _feature(ctx, r, fdir, spec)


def _feature(ctx: C.Ctx, r: Report, fdir: Path, spec: C.DocState) -> None:
    stext = (fdir / "spec.md").read_text()
    ref = spec.meta.get("rfc", "")
    rfc_path = C.find_rfc(ctx, ref)
    if rfc_path is None:
        r.err("GW021", fdir / "spec.md", f"cites RFC '{ref or '(none)'}' which does not exist",
              "every spec descends from an RFC")
    elif spec.approved and not C.doc_state(rfc_path, ctx).approved:
        r.err("GW021", fdir / "spec.md", f"spec is approved but {rfc_path.name} is not")
    if spec.meta.get("id") != fdir.name:
        r.err("GW021", fdir / "spec.md", f"front matter id '{spec.meta.get('id')}' != directory '{fdir.name}'")
    _approval_claims(r, spec, "GW026")

    # work must not start before the spec is approved
    ttext = (fdir / "tasks.md").read_text()
    started = re.search(r"^\s*- \[[x~]\]", ttext, re.M | re.I)
    if started and not spec.approved:
        r.err("GW034", fdir / "tasks.md", f"tasks are started but spec is {spec.status}",
              "the spec must be approved before implementation")

    for name in ("plan", "tasks", "evals"):
        s = C.doc_state(fdir / f"{name}.md", ctx)
        if s.placeholders:
            r.warn("GW025", s.path, f"{name}.md is unfinished ({s.placeholders} unresolved marker(s))")
    if spec.placeholders:
        r.warn("GW025", spec.path, f"spec is unfinished ({spec.placeholders} unresolved marker(s))")
        return

    miss = missing_sections(stext, SPEC_SECTIONS, numbered=True)
    if miss:
        r.err("GW022", fdir / "spec.md", "missing/misordered section(s): " + "; ".join(miss)); return
    if not strip_comments(section_body(stext, 8)):
        r.err("GW024", fdir / "spec.md", "Manual test section is empty",
              "say exactly how a human verifies this by hand")
    frs, nfrs, acs = _ids(stext, "FR"), _ids(stext, "NFR"), _ids(stext, "AC")
    for kind, ids in (("FR", frs), ("NFR", nfrs), ("AC", acs), ("US", _ids(stext, "US"))):
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            r.err("GW023", fdir / "spec.md", "duplicate id(s): " + ", ".join(sorted(dup)))
    if not frs:
        r.err("GW023", fdir / "spec.md", "no numbered functional requirements (**FR-1**)")
    if not acs:
        r.err("GW023", fdir / "spec.md", "no numbered acceptance criteria (**AC-1**)")
    known = set(frs) | set(nfrs)
    proven: set[str] = set()
    for m in re.finditer(r"^- \*\*(AC-\d+)\*\*(.*)$", stext, re.M):
        refs = set(re.findall(r"\b(N?FR-\d+)\b", m.group(2)))
        if not refs:
            r.err("GW023", fdir / "spec.md", f"{m.group(1)} does not cite the requirement it proves")
        for x in refs - known:
            r.err("GW023", fdir / "spec.md", f"{m.group(1)} cites unknown {x}")
        proven |= refs
    for fr in frs:
        if fr not in proven:
            r.warn("GW023", fdir / "spec.md", f"{fr} is not proven by any acceptance criterion")

    shash = C.body_hash(stext)
    for name in ("plan", "tasks", "evals"):
        f = fdir / f"{name}.md"
        if C.doc_state(f, ctx).placeholders:
            continue
        pinned = C.split_fm(f.read_text())[0].get("spec_version", "")
        if not pinned:
            r.warn("GW036", f, f"{name}.md is not pinned to a spec version", "groundwork.py plan-sync")
        elif pinned != shash:
            r.err("GW037", f, f"{name}.md was written against an earlier version of the spec (the spec changed since)",
                  "re-verify it against the current spec, then: groundwork.py plan-sync")
    ptext = (fdir / "plan.md").read_text()
    if not C.doc_state(fdir / "plan.md", ctx).placeholders:
        miss = missing_sections(ptext, PLAN_SECTIONS, numbered=True)
        if miss:
            r.err("GW030", fdir / "plan.md", "missing/misordered section(s): " + "; ".join(miss))

    if not C.doc_state(fdir / "tasks.md", ctx).placeholders:
        _tasks(r, fdir, ttext, frs, known)
    etext = (fdir / "evals.md").read_text()
    if not C.doc_state(fdir / "evals.md", ctx).placeholders:
        for ac in acs:
            if not re.search(rf"\b{ac}\b", etext):
                r.err("GW033", fdir / "evals.md", f"{ac} has no evaluation scenario")


def _tasks(r: Report, fdir: Path, text: str, frs: list[str], known: set[str]) -> None:
    blocks = re.split(r"(?m)^(?=- \[[ x~]\] \*\*T\d+\*\*)", text)[1:]
    covered: set[str] = set()
    ids: list[str] = []
    for b in blocks:
        tid = re.search(r"\*\*(T\d+)\*\*", b).group(1)
        ids.append(tid)
        if int(tid[1:]) >= 900:
            continue
        for field in ("Files", "Done when", "Covers"):
            if not re.search(rf"\*\*{field}:\*\*\s*\S", b):
                r.err("GW031", fdir / "tasks.md", f"{tid} has no '{field}'")
        cov = re.search(r"\*\*Covers:\*\*\s*(.+)", b)
        refs = set(re.findall(r"\b(N?FR-\d+)\b", cov.group(1))) if cov else set()
        for x in refs - known:
            r.err("GW031", fdir / "tasks.md", f"{tid} covers unknown {x}")
        covered |= refs
    if not any(int(t[1:]) < 900 for t in ids):
        r.err("GW031", fdir / "tasks.md", "no implementation tasks")
    dup = {t for t in ids if ids.count(t) > 1}
    if dup:
        r.err("GW031", fdir / "tasks.md", "duplicate task id(s): " + ", ".join(sorted(dup)))
    for fr in frs:
        if fr not in covered:
            r.err("GW032", fdir / "tasks.md", f"{fr} is not covered by any task")
    if not any(int(t[1:]) >= 900 for t in ids):
        r.warn("GW035", fdir / "tasks.md", "no verification tasks (T900+)")


def check_relations(ctx: C.Ctx, r: Report, workspace_wide: bool) -> None:
    es = R.edges(ctx)
    mine = [e for e in es if workspace_wide or (ctx.repo and e.src[0] == ctx.repo.name)]
    for e in mine:
        rc = next((c for c in R.contexts(ctx) if c.repo.name == e.src[0]), ctx)
        spec = rc.repo / "specs" / e.src[1] / "spec.md"
        if e.dst is None:
            r.err("GW070", spec, f"{e.kind}: '{e.raw}' does not resolve to a feature",
                  "use NNN-slug (this repo) or repo/NNN-slug (a sibling repo)")
    for cyc in R.find_cycles(es):
        if workspace_wide or (ctx.repo and cyc[0][0] == ctx.repo.name):
            r.err("GW071", ctx.repo / "specs" if ctx.repo else ctx.root, "dependency cycle: " + " → ".join(R.fmt(n) for n in cyc))
    for e in mine:
        if e.dst is None:
            continue
        rc = next((c for c in R.contexts(ctx) if c.repo.name == e.src[0]), ctx)
        sdir = rc.repo / "specs" / e.src[1]
        src_spec = C.doc_state(sdir / "spec.md", rc)
        trc = next((c for c in R.contexts(ctx) if c.repo.name == e.dst[0]), None)
        if e.kind == "amends" and src_spec.approved and trc:
            text = (trc.repo / "specs" / e.dst[1] / "spec.md").read_text()
            ch = re.search(r"^## Changes\b(.*?)(?=^## |\Z)", text, re.M | re.S)
            if not ch or e.src[1] not in ch.group(1):
                r.err("GW072", trc.repo / "specs" / e.dst[1] / "spec.md",
                      f"amended by {R.fmt(e.src)} but its '## Changes' section does not record it",
                      "add a dated line naming the amending feature, then get the spec re-approved")
        if e.kind in ("depends_on", "builds_against"):
            started = re.search(r"^\s*- \[[x~]\]", (sdir / "tasks.md").read_text(), re.M | re.I) if (sdir / "tasks.md").is_file() else None
            if started and C.dependency_problems(rc, src_spec):
                r.err("GW074", sdir / "tasks.md", "implementation started while dependencies are not ready: "
                      + "; ".join(C.dependency_problems(rc, src_spec)))
    by_target: dict = {}
    for e in es:
        if e.kind in ("amends", "extends") and e.dst:
            rc = next((c for c in R.contexts(ctx) if c.repo.name == e.src[0]), ctx)
            if not C.feature_implemented(rc, rc.repo / "specs" / e.src[1])[0]:
                by_target.setdefault(e.dst, set()).add(e.src)
    for dst, srcs in by_target.items():
        if len(srcs) > 1:
            r.warn("GW073", ctx.repo / "specs" if ctx.repo else ctx.root,
                   f"{', '.join(sorted(R.fmt(x) for x in srcs))} all modify {R.fmt(dst)} at once — sequence them or merge")


def check_bugs(ctx: C.Ctx, r: Report) -> None:
    for bp in B.bug_paths(ctx):
        st = B.bug_state(ctx, bp.stem)
        for p in st.problems:
            if st.status == "open" and p.rule in ("GW062", "GW065"):
                continue                     # still being diagnosed: not yet claiming anything
            if p.rule == "GW064":
                r.warn("GW064", bp, p.msg)
            else:
                r.err(p.rule, bp, p.msg)


def check_ownership(ctx: C.Ctx, r: Report) -> None:
    """GW080-GW083: every approved RFC/spec has a requester and owner; people named are findable; finished work has an implementer and support."""
    ppl = PP.people(ctx)
    items = []
    if ctx.level != "repo":
        items += [(st.path, st.meta, st.approved, "rfc") for st in C.rfcs(ctx)]
    if ctx.level in ("repo", "standalone"):
        for fdir in C.feature_dirs(ctx):
            sp = fdir / "spec.md"
            if sp.is_file():
                st = C.doc_state(sp, ctx)
                items.append((sp, st.meta, st.approved, "feature"))
    for path, meta, approved, kind in items:
        if approved:
            for role in ("requested_by", "owner"):
                if not str(meta.get(role, "")).strip():
                    r.warn("GW080", path, f"approved {kind} has no `{role}`",
                           f"groundwork.py record {'requested' if role == 'requested_by' else 'owner'} --ref <ref> --who <name>")
        for role in ("requested_by", "owner", "implemented_by", "support"):
            for name in C.list_of(meta, role):
                if ppl and PP.resolve(ppl, name) is None:
                    r.warn("GW081", path, f"`{role}`: '{name}' is not listed under 'Who works on what' in PROJECT.md")
        if kind == "feature":
            fdir = path.parent
            done, total = C.task_counts(ctx, fdir.name)
            if total and done == total:
                if not C.list_of(meta, "implemented_by"):
                    r.warn("GW082", path, "implemented (all tasks done) but `implemented_by` is empty",
                           f"groundwork.py record implemented --ref {fdir.name}")
                if not C.list_of(meta, "support"):
                    r.warn("GW083", path, "implemented but nobody is recorded as `support`",
                           f"groundwork.py record support --ref {fdir.name} --who <name>")


def check_brevity(ctx: C.Ctx, r: Report) -> None:
    """GW090/GW091: documents people must read should be short and in short sentences."""
    if ctx.config.get("brevity") == "off":
        return
    base = ctx.workspace if ctx.level == "workspace" else ctx.repo
    docs: list[tuple[Path, str | None]] = []
    for f in C.FOUNDATION[ctx.level]["files"]:
        p = C._find_ci(base, f)
        if p:
            docs.append((p, p.stem.lower()))
    if ctx.level in ("workspace", "standalone"):
        docs += [(st.path, "rfc") for st in C.rfcs(ctx)]
    if ctx.level in ("repo", "standalone"):
        for fdir in C.feature_dirs(ctx):
            docs += [(fdir / "spec.md", "spec"), (fdir / "plan.md", "plan")]
        docs += [(bp, "bug") for bp in B.bug_paths(ctx)]
    for path, kind in docs:
        if not path.is_file():
            continue
        text = path.read_text()
        if C.PLACEHOLDER.search(C.split_fm(text)[1]):
            continue                                              # unfinished: judged when finished
        budget = V.DOC_BUDGETS.get(kind or "")
        n = V.words(text)
        if budget and n > budget:
            r.warn("GW090", path, f"{n} words of prose; the budget for this kind of document is {budget}",
                   "never delete a requirement, decision or caveat to fit: split it (a long spec is usually two features), or move background and detail to a linked file")
        avg = V.avg_sentence(text)
        if avg > V.MAX_AVG_SENTENCE:
            r.warn("GW091", path, f"sentences average {avg:.0f} words (limit {V.MAX_AVG_SENTENCE})",
                   "use shorter sentences and everyday words")


def check_approval_records(ctx: C.Ctx, r: Report) -> None:
    for root in {ctx.repo, ctx.workspace} - {None}:
        for rel in C.load_approvals(root):
            if not (root / rel).is_file():
                r.warn("GW040", root / rel, "approval record points at a file that no longer exists")


# --- entry points ---------------------------------------------------------------------

def check_ctx(ctx: C.Ctx, r: Report, seen: set[Path]) -> None:
    root = ctx.root.resolve()
    if root in seen or ctx.level == "unknown":
        if ctx.level == "unknown":
            r.err("GW001", ctx.root, "not a git repository and not a workspace",
                  "git init, or: groundwork.py mark-workspace")
        return
    seen.add(root)
    check_version(ctx, r)
    check_foundation(ctx, r)
    check_freshness(ctx, r)
    check_ownership(ctx, r)
    check_brevity(ctx, r)
    check_approval_records(ctx, r)
    if ctx.level == "workspace":
        check_rfcs(ctx, r)
        check_relations(ctx, r, True)
        for kid in C.child_repos(ctx.workspace):
            check_ctx(C.detect(kid, ctx.workspace), r, seen)
    else:
        if ctx.level == "standalone":
            check_rfcs(ctx, r)
        check_features(ctx, r)
        check_bugs(ctx, r)
        if not (ctx.workspace and ctx.workspace.resolve() in seen):     # a workspace check already did the whole graph
            check_relations(ctx, r, False)


def run(path: Path) -> Report:
    ctx = C.detect(path)
    base = ctx.workspace or ctx.repo or ctx.root
    r = Report(base)
    check_ctx(ctx, r, set())
    return r


def render_text(r: Report, strict: bool) -> str:
    if not r.items:
        return "groundwork check: conforms to standard " + C.STANDARD_VERSION + " — no findings."
    lines = []
    for f in sorted(r.items, key=lambda f: (f.severity != "error", f.path, f.id)):
        tag = "ERROR  " if f.severity == "error" else "warning"
        lines.append(f"{tag} {f.id}  {f.path}: {f.message}" + (f"\n         → {f.hint}" if f.hint else ""))
    e = len(r.errors)
    w = len(r.items) - e
    lines.append(f"\n{e} error(s), {w} warning(s)" + (" (warnings fail under --strict)" if w and not strict else ""))
    return "\n".join(lines)


def render_json(r: Report) -> str:
    return json.dumps({"standard": C.STANDARD_VERSION, "findings": [asdict(f) for f in r.items]}, indent=2)
