"""groundwork core: where am I, what exists, what is approved, what comes next.

Pure standard library. Nothing here talks to the network or to a model; every rule the
plugin enforces is decided by code in this file, so it can be tested without an agent.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

STANDARD_VERSION = "0.8.0"  # the version of STANDARD.md this code implements

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = PLUGIN_ROOT / "templates"

# --- what every level must have -------------------------------------------------------

FOUNDATION = {
    "workspace": {
        "files": ["PROJECT.md", "ARCHITECTURE.md", "CONSTITUTION.md", "AGENTS.md"],
        "dirs": ["CONTRACTS", "DECISIONS"],
    },
    "repo": {"files": ["ARCHITECTURE.md", "AGENTS.md"], "dirs": []},
    "standalone": {
        "files": ["PROJECT.md", "ARCHITECTURE.md", "CONSTITUTION.md", "AGENTS.md"],
        "dirs": ["DECISIONS"],
    },
}

# Paths (relative to their owning root) that are documentation, not code. Editing these is
# how the process itself is carried out, so the implementation gate lets them through.
DOC_GLOBS = [
    "*.md",
    "*.mdx",
    ".groundwork/*",
    "specs/*",
    "bugs/*",
    "DECISIONS/*",
    "CONTRACTS/*",
    "docs/*",
    ".gitignore",
    "LICENSE*",
    ".claude/*",
]

PLACEHOLDER = re.compile(r"\[TODO\b|\[NEEDS CLARIFICATION", re.IGNORECASE)
SKIP_DIRS = {"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build"}


# --- context detection ----------------------------------------------------------------


@dataclass
class Ctx:
    level: str  # workspace | repo | standalone | unknown
    root: Path  # the directory this level is anchored at
    workspace: Path | None = None  # workspace root when level is repo/workspace
    repo: Path | None = None  # repo root when level is repo/standalone
    note: str = ""
    config: dict = field(default_factory=dict)

    @property
    def rfc_home(self) -> Path:
        return self.workspace or self.repo or self.root

    @property
    def enforcement(self) -> str:
        return os.environ.get("GROUNDWORK_ENFORCEMENT") or self.config.get(
            "enforcement", "block"
        )


def _exists(p: Path) -> bool:
    """Path.exists() that treats unreadable places (permission denied, e.g. /tmp) as absent."""
    try:
        return p.exists()
    except OSError:
        return False


def _isdir(p: Path) -> bool:
    try:
        return p.is_dir()
    except OSError:
        return False


def _existing(p: Path) -> Path:
    p = p.resolve()
    while not _exists(p) and p != p.parent:
        p = p.parent
    return p if _isdir(p) else p.parent


def find_git_root(start: Path) -> Path | None:
    p = _existing(start)
    for d in [p, *p.parents]:
        if _exists(d / ".git"):
            return d
    return None


def child_repos(d: Path) -> list[Path]:
    try:
        kids = sorted(d.iterdir())
    except OSError:
        return []
    return [
        k
        for k in kids
        if _isdir(k)
        and k.name not in SKIP_DIRS
        and not k.name.startswith(".")
        and _exists(k / ".git")
    ]


def read_config(root: Path) -> dict:
    try:
        return json.loads(
            (root / ".groundwork" / "config.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return {}


def _is_workspace_root(d: Path) -> bool:
    """A directory is a workspace if it says so, or if it plainly holds several repos."""
    if read_config(d).get("level") == "workspace":
        return True
    return bool(child_repos(d))


def _find_workspace_above(repo: Path) -> Path | None:
    """A repo belongs to a workspace only when an ancestor explicitly claims to be one.

    Merely being a sibling of other repos proves nothing (``~/projects`` is full of
    unrelated repos), so we require PROJECT.md or a config marker above.
    """
    for d in repo.parents:
        if read_config(d).get("level") == "workspace" or _exists(d / "PROJECT.md"):
            return d
        if d == Path.home() or d == d.parent:
            break
    return None


def detect(path: Path | str, session_cwd: Path | str | None = None) -> Ctx:
    """Classify ``path``. ``session_cwd`` is where the agent was started: if that is a
    workspace holding ``path``'s repo, the repo is a repo *of that workspace* even before
    PROJECT.md exists (otherwise the session and the gate would disagree)."""
    start = _existing(Path(path))
    git = find_git_root(start)
    if git:
        cfg = read_config(git)
        if cfg.get("level") == "workspace" or child_repos(git):
            return Ctx("workspace", git, workspace=git, config=cfg)
        ws = _find_workspace_above(git)
        if ws is None and session_cwd:
            s = detect(session_cwd)
            if (
                s.level == "workspace"
                and s.workspace != git
                and _within(git, s.workspace)
            ):
                ws = s.workspace
        if ws:
            return Ctx("repo", git, workspace=ws, repo=git, config=cfg)
        return Ctx("standalone", git, repo=git, config=cfg)
    # not inside any git repo
    for d in [start, *start.parents]:
        if (
            read_config(d).get("level") == "workspace"
            or _exists(d / "PROJECT.md")
            or (d == start and child_repos(d))
        ):
            return Ctx("workspace", d, workspace=d, config=read_config(d))
        if d == Path.home() or d == d.parent:
            break
    return Ctx("unknown", start, note="not a git repository and holds no repositories")


# --- front matter ---------------------------------------------------------------------

FM = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)


def split_fm(text: str) -> tuple[dict, str]:
    m = FM.match(text)
    if not m:
        return {}, text
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "#")):
            k, v = line.split(":", 1)
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                meta[k.strip()] = [x.strip() for x in v[1:-1].split(",") if x.strip()]
            else:
                meta[k.strip()] = v
    return meta, text[m.end() :]


def set_fm(text: str, updates: dict) -> str:
    m = FM.match(text)
    if not m:
        raise ValueError("document has no front matter")
    lines = m.group(1).splitlines()
    for k, v in updates.items():
        new = f"{k}: {v}"
        for i, line in enumerate(lines):
            if line.startswith(f"{k}:"):
                lines[i] = new
                break
        else:
            lines.append(new)
    return "---\n" + "\n".join(lines) + "\n---\n" + text[m.end() :]


def body_hash(text: str) -> str:
    _, body = split_fm(text)
    return hashlib.sha256(body.strip().encode()).hexdigest()


# --- approvals ------------------------------------------------------------------------


def owner_root(path: Path, ctx: Ctx) -> Path:
    """The root whose ``.groundwork/approvals.json`` vouches for ``path``."""
    path = path.resolve()
    if ctx.repo and _within(path, ctx.repo):
        return ctx.repo
    if ctx.workspace and _within(path, ctx.workspace):
        return ctx.workspace
    return ctx.root


def _within(p: Path, root: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _approvals_file(root: Path) -> Path:
    return root / ".groundwork" / "approvals.json"


def load_approvals(root: Path) -> dict:
    try:
        return json.loads(_approvals_file(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def signer() -> str:
    for cmd in (["git", "config", "user.email"], ["git", "config", "user.name"]):
        try:
            out = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=5,
                check=False,
            ).stdout.strip()
            if out:
                return out
        except (OSError, subprocess.SubprocessError):
            pass
    return os.environ.get("USER", "unknown")


def signoffs_needed(meta: dict) -> int | None:
    """`signoffs_required` as a count, or None when malformed. A malformed count can never be
    satisfied: the document stays unapproved (whatever record exists) until a person fixes it, and
    `check` reports the value. It must never fall back to a smaller number."""
    v = str(meta.get("signoffs_required", "1") or "1").strip()
    return int(v) if v.isdigit() and int(v) > 0 else None


def signoffs_label(st: DocState) -> str:
    """'1/2' for display, or '1/? (signoffs_required invalid)'."""
    n = len(set(st.signers))
    return f"{n}/{st.needed}" if st.needed else f"{n}/? (signoffs_required invalid)"


@dataclass
class DocState:
    path: Path
    exists: bool
    status: str  # missing | draft | in-review | approved | stale
    signers: list[str]
    needed: int
    placeholders: int
    meta: dict

    @property
    def approved(self) -> bool:
        return self.status == "approved"


def doc_state(path: Path, ctx: Ctx) -> DocState:
    path = Path(path)
    if not path.is_file():
        return DocState(path, False, "missing", [], 1, 0, {})
    text = path.read_text(encoding="utf-8")
    meta, body = split_fm(text)
    needed = signoffs_needed(meta)
    root = owner_root(path, ctx)
    rel = str(path.resolve().relative_to(root.resolve()))
    rec = load_approvals(root).get(rel)
    signers = [s["who"] for s in rec["signers"]] if rec else []
    placeholders = len(PLACEHOLDER.findall(body))
    if rec and rec.get("hash") == body_hash(text):
        # a malformed count (needed is None) is never satisfied, whatever the record holds
        status = (
            "approved"
            if needed is not None and len(set(signers)) >= needed
            else "in-review"
        )
    elif rec:
        status, signers = "stale", []  # edited since it was approved
    else:
        status = "draft"
    return DocState(path, True, status, signers, needed or 0, placeholders, meta)


def changes_count(text: str) -> int:
    """Entries in a spec's '## Changes' section (dated lines saying what changed and why)."""
    m = re.search(r"^## Changes\b(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return len(re.findall(r"^\s*[-*] ", m.group(1), re.MULTILINE)) if m else 0


def approve_preflight(path: Path, ctx: Ctx) -> str | None:
    """Why ``path`` cannot be approved right now, or None. Behavioural content is judged from the
    body only; the front matter supplies the metadata that belongs there (origin, owner, id)."""
    path = Path(path).resolve()
    if not path.is_file():
        return f"no such document: {path}"
    text = path.read_text(encoding="utf-8")
    meta, _ = split_fm(text)
    if not meta:
        return f"{path.name} has no front matter; it is not a governed document"
    sr = str(meta.get("signoffs_required", "1") or "1").strip()
    if not sr.isdigit() or int(sr) < 1:
        return f"{path.name}: signoffs_required must be a whole number (now '{sr}')"
    st = doc_state(path, ctx)
    if st.placeholders:
        return (
            f"{path.name} still has {st.placeholders} [TODO]/[NEEDS CLARIFICATION] "
            "marker(s). Resolve them before approval."
        )
    if path.name == "spec.md":
        if is_imported(meta):
            return (
                f"{path.parent.name} is an imported legacy document ({adoption_state(meta) or 'pending'}); "
                "it cannot be approved as a behavioural reference until it is classified "
                "(groundwork.py adopt-specs --classify baseline|planned|archived)."
            )
        if is_baseline(meta):
            import groundwork_baseline as BL

            bad = BL.approval_problems(path.parent, meta, text)
            if bad:
                return f"{path.parent.name}: " + "; ".join(bad)
    root = owner_root(path, ctx)
    rel = str(path.relative_to(root.resolve()))
    rec = load_approvals(root).get(rel)
    # A spec that was approved and then changed may be re-approved only with the change explained.
    if (
        rec
        and rec.get("hash") != body_hash(text)
        and path.name == "spec.md"
        and changes_count(text) <= rec.get("changes", 0)
    ):
        return (
            "this spec was approved before and has changed since. Record what changed and why as a dated line under "
            "'## Changes' (after the required sections), e.g. '- 2026-09-30: FR-6 now means the exact, unrounded payment "
            "(found while planning; user chose this reading)', then approve again."
        )
    return None


def approve(path: Path, ctx: Ctx, who: str | None = None) -> DocState:
    path = Path(path).resolve()
    why = approve_preflight(path, ctx)
    if why:
        raise SystemExit(why)
    text = path.read_text(encoding="utf-8")
    meta, _ = split_fm(text)
    root = owner_root(path, ctx)
    rel = str(path.relative_to(root.resolve()))
    store = load_approvals(root)
    h = body_hash(text)
    rec = store.get(rel)
    if not rec or rec.get("hash") != h:
        rec = {"hash": h, "signers": [], "changes": changes_count(text)}
    who = who or signer()
    if who not in [s["who"] for s in rec["signers"]]:
        rec["signers"].append({"who": who, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    store[rel] = rec
    f = _approvals_file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")
    needed = signoffs_needed(meta)
    done = needed is not None and len({s["who"] for s in rec["signers"]}) >= needed
    path.write_text(
        set_fm(
            text,
            {
                "status": "approved" if done else "in-review",
                "approved_by": "[" + ", ".join(s["who"] for s in rec["signers"]) + "]",
            },
        ),
        encoding="utf-8",
    )
    if path.name == "spec.md" and ctx.repo:
        import groundwork_baseline as BL

        if BL.load_caps(
            ctx
        ):  # the capability table shows approval state: keep the view current
            BL.write_index(ctx)
    return doc_state(path, ctx)


# --- foundation -----------------------------------------------------------------------


def foundation_gaps(ctx: Ctx) -> tuple[list[str], list[str]]:
    """(missing, unfinished) foundation items, as names relative to their level's root.

    A repo inside a workspace answers for the workspace's foundation too — the repo reads
    upward, so the product-level docs must exist before anything is built in it.
    """
    missing, unfinished = _gaps_at(
        ctx.level, ctx.workspace if ctx.level == "workspace" else ctx.repo, ""
    )
    if ctx.level == "repo" and ctx.workspace:
        m, u = _gaps_at("workspace", ctx.workspace, "workspace/")
        missing, unfinished = m + missing, u + unfinished
    return missing, unfinished


def _gaps_at(level: str, base: Path | None, prefix: str) -> tuple[list[str], list[str]]:
    spec = FOUNDATION.get(level)
    if not spec or base is None:
        return [], []
    missing, unfinished = [], []
    for f in spec["files"]:
        p = _find_ci(base, f)
        if p is None:
            missing.append(prefix + f)
        elif PLACEHOLDER.search(p.read_text(encoding="utf-8")):
            unfinished.append(prefix + f)
    for d in spec["dirs"]:
        if not (base / d).is_dir():
            missing.append(prefix + d + "/")
    return missing, unfinished


def _find_ci(base: Path, name: str) -> Path | None:
    try:
        for c in base.iterdir():
            if c.name.lower() == name.lower() and c.is_file():
                return c
    except OSError:
        pass
    return None


# --- features -------------------------------------------------------------------------


def rfcs(ctx: Ctx) -> list[DocState]:
    d = ctx.rfc_home / "DECISIONS"
    if not d.is_dir():
        return []
    return [doc_state(p, ctx) for p in sorted(d.glob("RFC-*.md"))]


def find_rfc(ctx: Ctx, ref: str) -> Path | None:
    d = ctx.rfc_home / "DECISIONS"
    m = re.match(r"(?:RFC-)?0*(\d+)", ref or "", re.IGNORECASE)
    if not m or not d.is_dir():
        return None
    for p in d.glob("RFC-*.md"):
        if int(re.match(r"RFC-0*(\d+)", p.name).group(1)) == int(m.group(1)):
            return p
    return None


def active_slug(ctx: Ctx) -> str | None:
    if not ctx.repo:
        return None
    try:
        return (ctx.repo / ".groundwork" / "active").read_text(
            encoding="utf-8"
        ).strip() or None
    except OSError:
        return None


def feature_dirs(ctx: Ctx) -> list[Path]:
    s = (ctx.repo or ctx.root) / "specs"
    return sorted(p for p in s.iterdir() if p.is_dir()) if s.is_dir() else []


@dataclass
class Step:
    key: str
    ok: bool
    detail: str


def list_of(meta: dict, key: str) -> list[str]:
    v = meta.get(key, [])
    return [x for x in (v if isinstance(v, list) else [v]) if x]


# --- origin: planned feature, baseline (existing behaviour), or imported legacy document (§5j) ----

ORIGINS = {"baseline", "imported"}
ADOPTION_STATES = {"pending", "archived"}


def origin(meta: dict) -> str:
    """'' (a planned feature), 'baseline' (documents behaviour that existed before GroundWork) or
    'imported' (a legacy document awaiting classification, or archived)."""
    return str(meta.get("origin", "") or "").strip()


def is_baseline(meta: dict) -> bool:
    return origin(meta) == "baseline"


def is_imported(meta: dict) -> bool:
    return origin(meta) == "imported"


def adoption_state(meta: dict) -> str:
    return str(meta.get("adoption_state", "") or "").strip()


def spec_meta(fdir: Path) -> dict:
    sp = fdir / "spec.md"
    if not sp.is_file():
        return {}
    return split_fm(sp.read_text(encoding="utf-8"))[0]


DISCREPANCY_OPEN = re.compile(r"^\s*- \[ \]\s*(.*)$", re.MULTILINE)


def open_discrepancies(text: str) -> list[str]:
    """Open entries ('- [ ] …') of a baseline's '## Known discrepancies' section."""
    m = re.search(
        r"^## Known discrepancies\b(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL
    )
    if not m:
        return []
    return [x.strip()[:80] for x in DISCREPANCY_OPEN.findall(m.group(1))]


def reference_problem(rc: Ctx, fdir: Path) -> str | None:
    """Why a baseline or imported feature cannot be cited (by a relation or a bug), or None.
    Planned features keep their own rules; this only judges the two adopted origins."""
    meta = spec_meta(fdir)
    if is_imported(meta):
        st = adoption_state(meta) or "pending"
        return f"imported legacy document ({st}); classify it first (adopt-specs --classify)"
    if is_baseline(meta):
        st = doc_state(fdir / "spec.md", rc)
        if st.status == "stale":
            return "baseline edited after approval; it must be re-approved"
        if not st.approved:
            return f"baseline is {st.status}, not approved"
        import groundwork_baseline as BL

        problems = BL.approval_problems(
            fdir, meta, (fdir / "spec.md").read_text(encoding="utf-8")
        )
        if problems:
            return "baseline is invalid: " + "; ".join(problems)
    return None


def resolve_feature(ctx: Ctx, ref: str) -> tuple[Ctx | None, Path | None]:
    """'NNN-slug' (this repo) or 'repo/NNN-slug' (a sibling repo in the workspace) -> (ctx, feature dir)."""
    ref = ref.strip()
    rctx: Ctx | None = ctx
    if "/" in ref:
        repo, ref = ref.split("/", 1)
        base = ctx.workspace
        rctx = (
            detect(base / repo, base)
            if base and (base / repo / ".git").exists()
            else None
        )
    if rctx is None or not rctx.repo:
        return None, None
    fdir = rctx.repo / "specs" / ref
    return (rctx, fdir) if fdir.is_dir() else (None, None)


def feature_implemented(rctx: Ctx, fdir: Path) -> tuple[bool, str]:
    """Is this feature built? A planned feature: every task ticked. A baseline describes behaviour
    that already exists, so it counts once a human has approved it (nothing to tick). An imported
    document counts for nothing until classified."""
    meta = spec_meta(fdir)
    if is_baseline(meta):
        why = reference_problem(rctx, fdir)
        return (why is None), ("baseline, approved" if why is None else why)
    if is_imported(meta):
        return False, reference_problem(rctx, fdir) or "imported"
    done, total = task_counts(rctx, fdir.name)
    return (total > 0 and done == total), f"tasks {done}/{total}"


def dependency_problems(ctx: Ctx, spec: DocState) -> list[str]:
    bad = []
    for ref in list_of(spec.meta, "depends_on"):
        rc, fd = resolve_feature(ctx, ref)
        if fd is None:
            bad.append(f"{ref} (does not exist)")
        else:
            ok, prog = feature_implemented(rc, fd)
            if not ok:
                bad.append(f"{ref} (not yet implemented, {prog})")
    for ref in list_of(spec.meta, "builds_against"):
        rc, fd = resolve_feature(ctx, ref)
        if fd is None:
            bad.append(f"{ref} (does not exist)")
            continue
        tmeta = spec_meta(fd)
        if origin(tmeta):
            # a baseline's interface is the behaviour that already exists: an approved baseline
            # is the agreed contract; nothing is fabricated to stand in for a plan
            why = reference_problem(rc, fd)
            if why:
                bad.append(f"{ref} ({why})")
            continue
        sp, pl = doc_state(fd / "spec.md", rc), doc_state(fd / "plan.md", rc)
        if not sp.approved or not pl.exists or pl.placeholders:
            bad.append(
                f"{ref} (spec not approved or plan not finished — needed to build against it)"
            )
    return bad


def dependency_warnings(ctx: Ctx, spec: DocState) -> list[str]:
    """Non-blocking: a dependency is an approved baseline that carries open known discrepancies.
    It still satisfies the dependency (a ticked task list proves no more), but the reader should know."""
    out = []
    for key in ("depends_on", "builds_against"):
        for ref in list_of(spec.meta, key):
            _rc, fd = resolve_feature(ctx, ref)
            if fd is None or not is_baseline(spec_meta(fd)):
                continue
            opened = open_discrepancies((fd / "spec.md").read_text(encoding="utf-8"))
            if opened:
                out.append(
                    f"{ref} is a baseline with {len(opened)} open known discrepanc{'y' if len(opened) == 1 else 'ies'}: "
                    + "; ".join(opened[:3])
                )
    return out


def feature_steps(ctx: Ctx, slug: str) -> list[Step]:
    fdir = ctx.repo / "specs" / slug
    steps: list[Step] = []
    spec = doc_state(fdir / "spec.md", ctx)
    if is_imported(spec.meta):
        st = adoption_state(spec.meta) or "pending"
        if st == "archived":
            return [
                Step(
                    "classify",
                    True,
                    "archived legacy reference: never cited, never built",
                )
            ]
        return [
            Step(
                "classify",
                False,
                f"imported legacy spec ({st}): a reference awaiting classification, not work to build",
            )
        ]
    if is_baseline(spec.meta):
        # a baseline is never all-green: it documents what exists and is not an implementation target
        steps.append(
            Step(
                "spec",
                spec.approved,
                f"baseline spec.md is {spec.status}"
                + (
                    f", {spec.placeholders} unresolved marker(s)"
                    if spec.placeholders
                    else ""
                ),
            )
        )
        steps.append(
            Step(
                "baseline",
                False,
                "a baseline documents existing behaviour; it is not an implementation target",
            )
        )
        return steps
    ref = spec.meta.get("rfc", "")
    rfc_path = find_rfc(ctx, ref)
    if rfc_path is None:
        steps.append(
            Step(
                "rfc", False, f"spec cites RFC '{ref or '(none)'}' which does not exist"
            )
        )
    else:
        r = doc_state(rfc_path, ctx)
        steps.append(
            Step(
                "rfc",
                r.approved,
                f"{rfc_path.name} is {r.status}"
                + (
                    f" ({signoffs_label(r)} sign-offs)"
                    if r.status == "in-review"
                    else ""
                ),
            )
        )
    steps.append(
        Step(
            "spec",
            spec.approved,
            f"spec.md is {spec.status}"
            + (
                f", {spec.placeholders} unresolved marker(s)"
                if spec.placeholders
                else ""
            ),
        )
    )
    for name in ("plan", "tasks", "evals"):
        s = doc_state(fdir / f"{name}.md", ctx)
        ok = s.exists and s.placeholders == 0
        steps.append(
            Step(
                name,
                ok,
                f"{name}.md "
                + (
                    "missing"
                    if not s.exists
                    else f"has {s.placeholders} unresolved marker(s)"
                    if s.placeholders
                    else "complete"
                ),
            )
        )
    shash = (
        body_hash((fdir / "spec.md").read_text(encoding="utf-8"))
        if (fdir / "spec.md").is_file()
        else ""
    )
    stale_docs = []
    for name in ("plan", "tasks", "evals"):
        f = fdir / f"{name}.md"
        pinned = (
            split_fm(f.read_text(encoding="utf-8"))[0].get("spec_version", "")
            if f.is_file()
            else ""
        )
        if pinned and pinned != shash:
            stale_docs.append(f"{name}.md")
    steps.append(
        Step(
            "sync",
            not stale_docs,
            "plan/tasks/evals match the approved spec"
            if not stale_docs
            else ", ".join(stale_docs)
            + " were written against an earlier version of the spec",
        )
    )
    bad = dependency_problems(ctx, spec)
    steps.append(
        Step(
            "deps",
            not bad,
            "dependencies ready" if not bad else "waiting on " + "; ".join(bad),
        )
    )
    return steps


def task_counts(ctx: Ctx, slug: str) -> tuple[int, int]:
    p = ctx.repo / "specs" / slug / "tasks.md"
    if not p.is_file():
        return 0, 0
    t = p.read_text(encoding="utf-8")
    done = len(re.findall(r"^\s*- \[x\]", t, re.MULTILINE | re.IGNORECASE))
    return done, done + len(re.findall(r"^\s*- \[[ ~]\]", t, re.MULTILINE))


INSTRUCTIONS = {
    "rfc": "RFC not approved. Ask the user to review it, then to run /groundwork-specflow:approve <path>.",
    "spec": "Write/finish spec.md with the write-spec skill, resolve every [NEEDS CLARIFICATION], "
    "then ask the user to run /groundwork-specflow:approve on it.",
    "plan": "Write plan.md with the write-plan skill.",
    "tasks": "Write tasks.md with the write-tasks skill.",
    "evals": "Write evals.md with the write-evals skill.",
    "sync": "The spec changed after the plan/tasks/evals were written. Re-read them against the CURRENT spec, fix what no longer "
    "matches (and say so to the user), then run `groundwork.py plan-sync`.",
    "deps": "Finish (resume) the features it depends on first. If they can proceed in parallel against an approved "
    "contract, ask the user and move them from depends_on to builds_against.",
    "classify": "Investigate and interview (baseline skill), then classify it: groundwork.py adopt-specs --classify "
    "baseline|planned|archived <slug>. Until then it cannot be cited or built against.",
    "baseline": "New behaviour needs its own feature (interview skill → RFC → spec) that extends or amends this "
    "baseline; a defect in it is a bug (fix-bug skill). Clear the active feature: this one cannot be built.",
}


def next_step(ctx: Ctx) -> tuple[str, str]:
    """(phase, instruction) — the single most useful thing to do next."""
    if ctx.level == "unknown":
        return "classify", (
            "This directory is neither a git repository nor a workspace. Ask the user "
            "which it should be: `git init` (a repo) or a workspace that will hold repos."
        )
    missing, unfinished = foundation_gaps(ctx)
    if missing or unfinished:
        return "bootstrap", (
            "Foundation docs are incomplete ("
            + ", ".join(missing + unfinished)
            + "). Use the bootstrap skill before anything else (it starts with `groundwork.py init`)."
        )
    if ctx.level == "workspace":
        pend = [r for r in rfcs(ctx) if not r.approved]
        if pend:
            return (
                "rfc",
                f"{pend[0].path.name} is {pend[0].status}. Finish it, or get it approved.",
            )
        return "idle", (
            "Workspace is ready. For new work: interview skill, then write-rfc. "
            "Code is written inside a repo, not here."
        )
    import groundwork_bugs as B

    bug = B.active_bug(ctx)
    if bug:
        b = B.bug_state(ctx, bug)
        if b.status not in ("closed",):
            return "bug", f"[bug {bug}] {b.next}"
    slug = active_slug(ctx)
    if not slug:
        import groundwork_board as W

        items = W.collect(ctx)
        if items:
            top = "; ".join(f"{i.label} — {i.state}" for i in items[:3])
            return "resume", (
                f"{len(items)} item(s) in flight: {top}. If the user's request continues one, use the "
                "resume skill (groundwork.py board); otherwise start new work with the interview skill."
            )
        import groundwork_baseline as BL

        review = BL.review_summary(ctx)
        return "idle", (
            "Nothing in flight. If the user wants to build something, start with the interview skill "
            "(then write-rfc); if they report a bug, use the fix-bug skill."
            + (
                f" Documentation awaiting review (baseline skill): {review}."
                if review
                else ""
            )
        )
    if not (ctx.repo / "specs" / slug).is_dir():
        return (
            "idle",
            f"Active feature '{slug}' has no specs/{slug}/ directory. Clear or recreate it.",
        )
    if origin(spec_meta(ctx.repo / "specs" / slug)):
        key = (
            "baseline"
            if is_baseline(spec_meta(ctx.repo / "specs" / slug))
            else "classify"
        )
        return key, (
            f"[{slug}] is {'a baseline' if key == 'baseline' else 'an imported legacy spec'}, not an "
            f"implementation target; clear .groundwork/active. " + INSTRUCTIONS[key]
        )
    for st in feature_steps(ctx, slug):
        if not st.ok:
            return st.key, f"[{slug}] {st.detail}. " + INSTRUCTIONS[st.key]
    done, total = task_counts(ctx, slug)
    if total and done == total:
        return (
            "handover",
            f"[{slug}] all {total} tasks done. Verify against evals.md, run the refresh skill, then write specs/{slug}/handover.md (and the workspace DECISIONS/handovers/ file if the RFC is cross-repo).",
        )
    return (
        "implement",
        f"[{slug}] approved and planned. Work one task at a time ({done}/{total} done).",
    )


# --- the implementation gate ----------------------------------------------------------


def is_doc_path(path: Path, root: Path) -> bool:
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return False
    # fnmatch's '*' crosses '/', so "specs/*" covers everything below specs/.
    return any(
        fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(Path(rel).name, g) for g in DOC_GLOBS
    )


def bypass_active(root: Path) -> dict | None:
    try:
        b = json.loads(
            (root / ".groundwork" / "bypass.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    return b if b.get("until", 0) > time.time() else None


def gate_code_edit(
    path: Path, session_cwd: Path | str | None = None
) -> tuple[bool, str]:
    """May this file be written? Returns (allowed, reason-if-denied)."""
    ctx = detect(path, session_cwd)
    if ctx.enforcement == "off":
        return True, ""
    if ctx.level == "unknown":
        return False, (
            "groundwork-specflow: this directory is neither a git repository nor a workspace. "
            "Ask the user whether to `git init` here (a repo) or to make it a workspace, "
            "then run the bootstrap skill. Do not write code yet."
        )
    if ctx.level == "workspace":
        return (
            True,
            "",
        )  # code lives in the repos; a repo inside resolves as its own context
    root = ctx.repo
    if is_doc_path(path, root):
        return True, ""
    reason = _why_blocked(ctx)
    if reason is None:
        return True, ""
    import groundwork_bugs as B

    bug = B.active_bug(ctx)
    if bug and B.bug_state(ctx, bug).ready:
        return True, ""
    if bug and not active_slug(ctx):
        # a bug is the work in hand: say what THAT needs, not the generic "no active feature" text
        reason = f"bug '{bug}' does not yet allow edits: {B.bug_state(ctx, bug).next}. Approval and bypass are human acts."
    elif bug:
        reason += f" (The active bug '{bug}' does not yet allow edits: {B.bug_state(ctx, bug).next})"
    b = bypass_active(root)
    if b:
        return True, ""
    if ctx.enforcement == "warn":
        return True, ""
    return False, "groundwork-specflow: " + reason


def _why_blocked(ctx: Ctx) -> str | None:
    missing, unfinished = foundation_gaps(ctx)
    if missing or unfinished:
        return (
            "code edits are blocked until the foundation docs exist and are filled in "
            f"(missing: {', '.join(missing) or 'none'}; unfinished: {', '.join(unfinished) or 'none'}). "
            "Use the bootstrap skill. If this is a genuine emergency the USER can run "
            "/groundwork-specflow:bypass <reason>."
        )
    slug = active_slug(ctx)
    if not slug:
        return (
            "no active feature and no diagnosed bug, so there is no approved spec to build against. New work: interview "
            "the user (interview skill), RFC → approval → spec → plan → tasks → evals. A bug: the fix-bug skill (diagnose, "
            "classify, cite the violated requirements, name a regression test). Resuming: the resume skill. "
            "For a tiny emergency the USER can run /groundwork-specflow:bypass <reason>."
        )
    if (ctx.repo / "specs" / slug).is_dir() and origin(
        spec_meta(ctx.repo / "specs" / slug)
    ):
        return (
            f"'{slug}' is a baseline or imported legacy spec: documentation of existing behaviour, never an "
            "implementation target. New behaviour needs its own feature (interview skill); a defect needs the "
            "fix-bug skill. Clear .groundwork/active."
        )
    for st in (
        feature_steps(ctx, slug)
        if (ctx.repo / "specs" / slug).is_dir()
        else [Step("spec", False, f"specs/{slug}/ does not exist")]
    ):
        if not st.ok:
            return (
                f"feature '{slug}' is not ready to build: {st.detail}. "
                f"{INSTRUCTIONS.get(st.key, '')} Approval is a human act (/groundwork-specflow:approve); "
                "you cannot approve documents yourself."
            )
    return None


PROTECTED_PATH = re.compile(r"(^|/)\.groundwork/(approvals|bypass)\.json$")
PROTECTED_CMD = re.compile(
    r"\.groundwork/(approvals|bypass)\.json|groundwork\.py[\"']?\s+[\"']?(approve|bypass)|groundwork_core\.py"
)


def is_protected_path(path: Path) -> bool:
    return bool(PROTECTED_PATH.search(path.as_posix()))


_PROTECTED_WORD = re.compile(
    r"approvals\.json|bypass\.json|groundwork_core|groundwork\.py|groundwork[/\\]engine"
)
_SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
_INTERPRETERS = re.compile(
    r"^(python[\d.]*|node|nodejs|ruby|perl|php|deno|bun|pwsh|powershell)$"
)
_ASSIGN = re.compile(r"^([A-Za-z_]\w*)=(.*)$")
_SCRIPT_READ_LIMIT = 200_000


def _expand_vars(tok: str, env: dict[str, str]) -> str:
    return re.sub(
        r"\$(?:\{(\w+)\}|(\w+))",
        lambda m: env.get(m.group(1) or m.group(2), m.group(0)),
        tok,
    )


def _glob_hits_protected(tok: str) -> bool:
    """`.groundwork/appr*.json`, `.groundwork/?ypass.json`: a glob that could expand to a protected file."""
    if not re.search(r"[*?\[]", tok) or ".groundwork" not in tok.replace("\\", "/"):
        return False
    leaf = tok.replace("\\", "/").rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(n, leaf) for n in ("approvals.json", "bypass.json"))


def _script_is_protected(word: str, cwd: Path | None) -> bool:
    """A script the agent could have written that itself calls approve/bypass (`bash x.sh`, `python3 x.py`)."""
    if cwd is None or not word or word.startswith(("-", "$")):
        return False
    p = Path(word).expanduser()
    p = p if p.is_absolute() else cwd / p
    try:
        if p.is_file() and p.stat().st_size <= _SCRIPT_READ_LIMIT:
            return bool(
                PROTECTED_CMD.search(p.read_text(encoding="utf-8", errors="ignore"))
            )
    except OSError:
        pass
    return False


def is_protected_command(cmd: str, cwd: Path | None = None, _depth: int = 0) -> bool:
    """Would this shell command touch approvals/bypass records or run the human-only engine commands?

    Token-based, so quoting tricks (`gro""undwork.py`), variables set in the same command (`E=groundwork.py; python3 $E
    approve`), `bash -c '...'`/`eval`, inline interpreter code, globs and scripts that call approve are all seen. Static
    analysis cannot prove an arbitrary shell command safe (string building at runtime, encoded payloads), so when a
    command pipes a decoder into a shell, or evals something we cannot read, it is refused as well.
    """
    if PROTECTED_CMD.search(cmd):
        return True
    if _depth > 3:  # nested bash -c / eval chains this deep: refuse
        return True
    stripped, bodies = _strip_heredocs(cmd)
    if (
        PROTECTED_CMD.search(bodies)
        or _PROTECTED_WORD.search(bodies)
        and re.search(r"\b(approve|bypass)\b", bodies)
    ):
        return True
    env: dict[str, str] = {}
    for argv in _simple_commands(stripped):
        words = []
        for t in argv:
            m = _ASSIGN.match(t) if not words else None
            if m:
                env[m.group(1)] = _expand_vars(m.group(2), env)
            else:
                words.append(_expand_vars(t, env))
        if not words:
            continue
        joined = " ".join(words)
        if PROTECTED_CMD.search(joined) or any(_glob_hits_protected(w) for w in words):
            return True
        name = Path(words[0]).name
        base = [Path(w).name for w in words]
        if any(b in ("groundwork.py", "groundwork_core.py") for b in base):
            sub = base.index("groundwork.py") if "groundwork.py" in base else None
            if sub is None or any(w in ("approve", "bypass") for w in words[sub + 1 :]):
                return True
        if name == "eval" or (name in _SHELLS and "-c" in words):
            payload = (
                " ".join(words[1:])
                if name == "eval"
                else words[words.index("-c") + 1 :][0]
                if words.index("-c") + 1 < len(words)
                else ""
            )
            if is_protected_command(payload, cwd, _depth + 1):
                return True
        if (
            name in _SHELLS | {"source", "."}
            and len(words) > 1
            and _script_is_protected(words[1], cwd)
        ):
            return True
        if _INTERPRETERS.match(name):
            if any(
                w in ("-c", "-e", "-r", "-E", "--eval", "--command")
                or w.startswith("-c")
                for w in words[1:]
            ) and _PROTECTED_WORD.search(joined):
                return True
            script = next((w for w in words[1:] if not w.startswith("-")), "")
            if _script_is_protected(script, cwd):
                return True
        elif words[0].startswith(("./", "/")) and _script_is_protected(words[0], cwd):
            return True
    # a decoder piped into a shell hides its payload from us
    return bool(
        re.search(
            r"\b(base64|xxd|openssl\s+enc|rev)\b[^|;&]*\|[^;&]*\b(sh|bash|zsh|dash|python3?|eval)\b",
            stripped,
        )
    )


# --- scaffolding ----------------------------------------------------------------------


def render(template: str, **vars: str) -> str:
    t = (TEMPLATES / template).read_text(encoding="utf-8")
    for k, v in vars.items():
        t = t.replace("{{" + k + "}}", v)
    return t


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def next_number(names: list[str], pattern: str) -> int:
    nums = [int(m.group(1)) for n in names if (m := re.match(pattern, n))]
    return max(nums, default=0) + 1


def write_config(root: Path, **updates) -> dict:
    """Merge ``updates`` into ``<root>/.groundwork/config.json`` and return the result."""
    cfg = read_config(root)
    cfg.update(updates)
    f = root / ".groundwork" / "config.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return cfg


# --- shell writes ---------------------------------------------------------------------
# The Write/Edit tools are not the only way to change code: `cat > f <<EOF`, `sed -i`, `tee`, `cp`,
# `python - <<EOF ... open(f, "w")` all do. This is best-effort static analysis of a shell command:
# it finds the files the command would write, so they can go through the same gate. It cannot see
# everything (a script that writes files when run is opaque), and it says so in the docs.

import shlex

IGNORED_TARGETS = re.compile(
    r"(^|/)(node_modules|__pycache__|\.venv|venv|dist|build|target|coverage|\.git|\.pytest_cache|\.mypy_cache|"
    r"\.ruff_cache|\.next|\.cache)(/|$)|\.(log|tmp|out|pyc|lock)$|^/dev/|^/proc/"
)
_INLINE_WRITE = re.compile(
    r"write_text\(|write_bytes\(|\bopen\([^)]*['\"][wax]b?\+?['\"]|writeFileSync|writeFile\(|"
    r"appendFile|fs\.write|Set-Content|File\.write|\.write\("
)
_OPAQUE = ("patch", "git apply")


def _simple_commands(cmd: str) -> list[list[str]]:
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        toks = list(lex)
    except ValueError:
        return []
    cmds, cur = [], []
    for t in toks:
        if t and set(t) <= set(";&|"):
            if cur:
                cmds.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


def _strip_heredocs(cmd: str) -> tuple[str, str]:
    """Remove heredoc bodies (they hold file *contents*, full of '>' and quotes). Returns (command, bodies)."""
    out, bodies, lines, i = [], [], cmd.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = re.search(r"<<-?\s*(['\"]?)([A-Za-z_][\w]*)\1", line)
        i += 1
        if m:
            tag = m.group(2)
            while i < len(lines) and lines[i].strip() != tag:
                bodies.append(lines[i])
                i += 1
            i += 1
    return "\n".join(out), "\n".join(bodies)


def shell_write_targets(cmd: str, cwd: Path) -> tuple[list[Path], bool]:
    """(files a shell command would write, whether it also writes somewhere unknowable)."""
    stripped, bodies = _strip_heredocs(cmd)
    targets: list[str] = []
    opaque = bool(
        _INLINE_WRITE.search(bodies) or _INLINE_WRITE.search(stripped)
    ) and bool(re.search(r"\b(python3?|node|ruby|perl|php|deno|bun)\b", stripped))
    here = cwd
    for argv in _simple_commands(stripped):
        # redirections: '>' '>>' '>|' and the '2>' forms (shlex splits digits off as their own token)
        i = 0
        while i < len(argv):
            t = argv[i]
            if t in (">", ">>", ">|") and i + 1 < len(argv):
                targets.append((here, argv[i + 1]))
            i += 1
        words = [
            w
            for j, w in enumerate(argv)
            if not (
                w in (">", ">>", ">|", "<", "<<", "<<<", ">&", "2>", "&>")
                or (j and argv[j - 1] in (">", ">>", ">|", "<", "<<", "<<<", ">&"))
            )
        ]
        if not words:
            continue
        name, args = Path(words[0]).name, words[1:]
        opts = [a for a in args if a.startswith("-")]
        pos = [a for a in args if not a.startswith("-")]
        if name == "cd" and pos:
            here = (here / pos[0]) if not Path(pos[0]).is_absolute() else Path(pos[0])
        elif name == "tee":
            targets += [(here, a) for a in pos]
        elif name in ("sed", "gsed") and any(
            re.match(r"-[A-Za-z]*i|--in-place", o) for o in opts
        ):
            files = (
                pos
                if any(
                    o.startswith(("-e", "-f", "--expression", "--file")) for o in opts
                )
                else pos[1:]
            )
            targets += [(here, a) for a in files]
        elif name == "perl" and any(re.match(r"-[A-Za-z]*i", o) for o in opts):
            targets += [(here, a) for a in pos[1:] if not a.startswith("s/")]
        elif name in ("cp", "mv", "install", "rsync") and len(pos) >= 2:
            targets.append((here, pos[-1]))
        elif name == "dd":
            targets += [(here, a[3:]) for a in args if a.startswith("of=")]
        elif name in ("curl", "wget"):
            for j, a in enumerate(args):
                if a in ("-o", "-O", "--output", "--output-document") and j + 1 < len(
                    args
                ):
                    targets.append((here, args[j + 1]))
        elif name in ("patch",) or (name == "git" and pos[:1] == ["apply"]):
            opaque = True
    resolved = []
    for base, t in targets:
        if not t or t.startswith("&") or t == "-":
            continue
        p = Path(t).expanduser()
        resolved.append(p if p.is_absolute() else base / p)
    return resolved, opaque


def gate_shell_command(cmd: str, cwd: Path) -> tuple[bool, str]:
    """May this shell command run, given what it writes? (allowed, reason-if-denied)"""
    session = detect(cwd)
    if session.enforcement == "off":
        return True, ""
    root = session.repo or session.workspace or session.root
    targets, opaque = shell_write_targets(cmd, cwd)
    check: list[Path] = []
    rroot = root.resolve()
    for p in targets:
        p = Path(os.path.normpath(p))
        try:
            rel = p.resolve().relative_to(rroot)
        except ValueError:
            continue  # outside the project: not ours to gate
        if not IGNORED_TARGETS.search(rel.as_posix()):
            check.append(p)
    if opaque:
        check.append(
            Path(root) / "__shell_write__.code"
        )  # unknown target: judged as a code write at the root
    for p in check:
        ok, why = gate_code_edit(p, cwd)
        if not ok:
            what = (
                "an inline script/patch that writes files"
                if p.name == "__shell_write__.code"
                else str(p)
            )
            return False, (
                why + f" — blocked because this shell command writes {what}. "
                "The shell is gated exactly like the Write/Edit tools; do not route around the gate."
            )
    return True, ""
