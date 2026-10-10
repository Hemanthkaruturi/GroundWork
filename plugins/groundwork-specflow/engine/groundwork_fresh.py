"""Freshness: do the foundation documents still describe reality?

A document is *confirmed* when someone (or an agent, after updating it) records a baseline:
a snapshot of the things the document is derived from. Later, the current snapshot is compared
with the baseline. Differences are the reasons the document may be stale.

Snapshots are content hashes, not git history, so this works with no commits, after rebases,
in shallow CI clones, and for teammates who never ran an agent. The baseline file is committed.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import groundwork_core as C

DEFAULT_MAX_AGE_DAYS = 90

MANIFESTS = {
    "package.json",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Gemfile",
    "composer.json",
    "requirements.txt",
    "Makefile",
    "justfile",
    "Taskfile.yml",
}
INFRA_NAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yaml",
    "serverless.yml",
    ".gitlab-ci.yml",
    "Jenkinsfile",
    "openapi.yaml",
    "openapi.yml",
    "openapi.json",
    "swagger.json",
    "schema.prisma",
    "schema.graphql",
}
INFRA_GLOBS = [
    "Dockerfile.*",
    "requirements*.txt",
    "*.tf",
    "docker-compose.*.yml",
    ".github/workflows/*",
    "k8s/*",
    "helm/*",
    "migrations/*",
    "alembic/versions/*",
    "db/migrate/*",
    "infra/*",
    "deploy/*",
    "terraform/*",
]
# what changes the *commands* documented in AGENTS.md
COMMAND_NAMES = MANIFESTS | {".gitlab-ci.yml", "Jenkinsfile"}
COMMAND_GLOBS = [".github/workflows/*"]

MANAGED_DIRS = {
    "specs",
    "bugs",
    "DECISIONS",
    "CONTRACTS",
}  # Groundwork's own folders say nothing about the architecture

TRACKED = {
    "workspace": ["PROJECT.md", "ARCHITECTURE.md", "CONSTITUTION.md", "AGENTS.md"],
    "repo": ["ARCHITECTURE.md", "AGENTS.md"],
    "standalone": ["PROJECT.md", "ARCHITECTURE.md", "CONSTITUTION.md", "AGENTS.md"],
}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def _file_hash(p: Path) -> str:
    if p.is_symlink():
        return "?"
    try:
        return _sha(p.read_bytes())
    except OSError:
        return "?"


def _matches(rel: str, names: set[str], globs: list[str]) -> bool:
    return Path(rel).name in names or any(fnmatch.fnmatch(rel, g) for g in globs)


def _excluded_dir(name: str) -> bool:
    return (
        name in C.SKIP_DIRS
        or name in {".groundwork", "specs"}
        or (name.startswith(".") and name != ".github")
    )


def _excluded_file(name: str) -> bool:
    return (name.startswith(".") and name != ".gitlab-ci.yml") or any(
        fnmatch.fnmatch(name.lower(), pattern)
        for pattern in (
            "*.pem",
            "*.key",
            "*.p12",
            "*.pfx",
            "*.tfvars",
            "*.tfvars.json",
            "*.tfstate",
            "*.tfstate.*",
            "credentials*",
            "secrets*",
        )
    )


def _walk(root: Path, max_files: int = 3000):
    n = 0
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(
            x for x in dirs if not _excluded_dir(x) and not Path(d, x).is_symlink()
        )
        for f in sorted(files):
            # Infrastructure directories can contain local secrets alongside manifests.
            # Never open those files or follow file links out of the project.
            if _excluded_file(f) or Path(d, f).is_symlink():
                continue
            n += 1
            if n > max_files:
                return
            p = Path(d) / f
            yield p.relative_to(root).as_posix(), p


def signals(repo: Path, names: set[str], globs: list[str]) -> dict[str, str]:
    return {rel: _file_hash(p) for rel, p in _walk(repo) if _matches(rel, names, globs)}


def toplevel(repo: Path) -> list[str]:
    try:
        return sorted(
            k.name
            for k in repo.iterdir()
            if k.is_dir()
            and k.name not in C.SKIP_DIRS
            and k.name not in MANAGED_DIRS
            and not k.name.startswith(".")
        )
    except OSError:
        return []


def approved_rfcs(ctx: C.Ctx) -> list[str]:
    return sorted(r.path.stem for r in C.rfcs(ctx) if r.approved)


def snapshot(ctx: C.Ctx, doc: str) -> dict:
    """What `doc` (a foundation file name) is derived from, right now."""
    key = doc.upper()
    if ctx.level == "workspace":
        kids = C.child_repos(ctx.workspace)
        if key == "ARCHITECTURE.MD":
            return {
                "repos": sorted(k.name for k in kids),
                "repo_arch": {
                    k.name: _file_hash(C._find_ci(k, "ARCHITECTURE.md") or k / "-")
                    for k in kids
                },
                "contracts": {
                    p.name: _file_hash(p)
                    for p in sorted((ctx.workspace / "CONTRACTS").glob("*.md"))
                }
                if (ctx.workspace / "CONTRACTS").is_dir()
                else {},
                "rfcs": approved_rfcs(ctx),
            }
        if key in ("PROJECT.MD", "AGENTS.MD"):
            return {"repos": sorted(k.name for k in kids)}
        return {}
    repo = ctx.repo
    if key == "ARCHITECTURE.MD":
        lay = C.read_config(repo).get("layout")
        return {
            "signals": signals(repo, MANIFESTS | INFRA_NAMES, INFRA_GLOBS),
            "toplevel": toplevel(repo),
            **({"rfcs": approved_rfcs(ctx)} if ctx.level == "standalone" else {}),
            **(
                {
                    "layout": {
                        k: json.dumps(v, sort_keys=True)
                        for k, v in lay.items()
                        if k not in ("decided", "decided_by")
                    }
                }
                if isinstance(lay, dict)
                else {}
            ),
        }
    if key == "AGENTS.MD":
        return {"signals": signals(repo, COMMAND_NAMES, COMMAND_GLOBS)}
    return {}


def diff_snapshots(old: dict, new: dict) -> list[str]:
    reasons: list[str] = []
    for k in sorted(set(old) | set(new)):
        o, n = old.get(k), new.get(k)
        if o == n:
            continue
        if isinstance(o, dict) or isinstance(n, dict):
            o, n = o or {}, n or {}
            add, rem = sorted(set(n) - set(o)), sorted(set(o) - set(n))
            chg = sorted(x for x in set(o) & set(n) if o[x] != n[x])
            for label, items in (("added", add), ("removed", rem), ("changed", chg)):
                if items:
                    reasons.append(
                        f"{k} {label}: "
                        + ", ".join(items[:5])
                        + (f" (+{len(items) - 5} more)" if len(items) > 5 else "")
                    )
        else:
            o, n = list(o or []), list(n or [])
            add, rem = sorted(set(n) - set(o)), sorted(set(o) - set(n))
            if add:
                reasons.append(f"{k} added: " + ", ".join(add[:5]))
            if rem:
                reasons.append(f"{k} removed: " + ", ".join(rem[:5]))
    return reasons


# --- baseline store -------------------------------------------------------------------


def _base(ctx: C.Ctx) -> Path:
    return ctx.workspace if ctx.level == "workspace" else ctx.repo


def load(ctx: C.Ctx) -> dict:
    import groundwork_baseline as BL

    BL._require_safe_paths(ctx, _base(ctx) / ".groundwork" / "freshness.json")
    try:
        return json.loads(
            (_base(ctx) / ".groundwork" / "freshness.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return {}


def _save(ctx: C.Ctx, data: dict) -> None:
    import groundwork_baseline as BL

    f = _base(ctx) / ".groundwork" / "freshness.json"
    BL._require_safe_paths(ctx, f)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def max_age_days(ctx: C.Ctx) -> int:
    return int(ctx.config.get("freshness_days", DEFAULT_MAX_AGE_DAYS))


def confirm(
    ctx: C.Ctx, docs: list[str] | None = None, who: str | None = None
) -> list[str]:
    """Record that the named foundation docs currently match reality."""
    base = _base(ctx)
    data = load(ctx)
    done = []
    for name in docs or TRACKED.get(ctx.level, []):
        p = C._find_ci(base, name)
        if p is None:
            raise SystemExit(f"{name} does not exist")
        if C.PLACEHOLDER.search(p.read_text(encoding="utf-8")):
            raise SystemExit(
                f"{p.name} still has [TODO]/[NEEDS CLARIFICATION] markers; finish it before confirming"
            )
        data[p.name] = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "epoch": int(time.time()),
            "by": who or C.signer(),
            "hash": _file_hash(p),
            "snapshot": snapshot(ctx, p.name),
        }
        done.append(p.name)
    _save(ctx, data)
    return done


@dataclass
class DocFreshness:
    doc: str
    status: str  # fresh | stale | unconfirmed | edited | unfinished
    reasons: list[str] = field(default_factory=list)


def assess(ctx: C.Ctx) -> list[DocFreshness]:
    if ctx.level not in TRACKED:
        return []
    base, data, out = _base(ctx), load(ctx), []
    for name in TRACKED[ctx.level]:
        p = C._find_ci(base, name)
        if p is None:
            continue
        if C.PLACEHOLDER.search(p.read_text(encoding="utf-8")):
            out.append(DocFreshness(p.name, "unfinished"))
            continue
        rec = data.get(p.name)
        if not rec:
            out.append(
                DocFreshness(
                    p.name,
                    "unconfirmed",
                    ["never confirmed against reality (run: groundwork.py confirm)"],
                )
            )
            continue
        old_snap = dict(rec.get("snapshot", {}))
        if (
            "toplevel" in old_snap
        ):  # baselines written before Groundwork's own folders were excluded
            old_snap["toplevel"] = [
                x for x in old_snap["toplevel"] if x not in MANAGED_DIRS
            ]
        reasons = diff_snapshots(old_snap, snapshot(ctx, p.name))
        age = (time.time() - rec.get("epoch", 0)) / 86400
        if age > max_age_days(ctx):
            reasons.append(
                f"not reviewed for {int(age)} days (limit {max_age_days(ctx)})"
            )
        edited = rec.get("hash") != _file_hash(p)
        if reasons:
            if edited:
                reasons.append(
                    "the document was edited since the last confirm — if it now reflects "
                    "reality, run: groundwork.py confirm " + p.name
                )
            out.append(DocFreshness(p.name, "stale", reasons))
        else:
            out.append(
                DocFreshness(
                    p.name,
                    "edited" if edited else "fresh",
                    ["edited since last confirm; run confirm to record it"]
                    if edited
                    else [],
                )
            )
    return out


def stale_summary(ctx: C.Ctx) -> list[str]:
    return [
        f"{d.doc}: " + "; ".join(d.reasons[:3])
        for d in assess(ctx)
        if d.status in ("stale", "unconfirmed")
    ]


def assess_with_parent(ctx: C.Ctx) -> list[DocFreshness]:
    """Own documents, plus — for a repo — the workspace's, which this repo's work can make stale."""
    out = assess(ctx)
    if ctx.level == "repo" and ctx.workspace:
        for d in assess(C.detect(ctx.workspace)):
            out.append(DocFreshness("workspace/" + d.doc, d.status, d.reasons))
    return out


def stale_lines(ctx: C.Ctx) -> list[str]:
    return [
        f"{d.doc}: " + "; ".join(d.reasons[:3])
        for d in assess_with_parent(ctx)
        if d.status in ("stale", "unconfirmed")
    ]


# --- baseline source review (STANDARD.md §5j) --------------------------------------------
# A baseline cites the files it was observed from (its Evidence table). Those files, and only
# those, are snapshotted when a person reviews the baseline against its sources. A later change
# to one of them is a *review signal*: the baseline may still be right, but someone must look.
# Approval is a separate record (approvals.json) and is never touched here.

BASELINE_NS = "baseline:"
MAX_EVIDENCE_FILES = 300
# Brackets, parentheses, @, + and $ appear in framework route files: app/[id]/page.tsx,
# app/(site)/layout.tsx, routes/+page.svelte, routes/$id.tsx.
_PATH_TOKEN = re.compile(r"(?:[A-Za-z]:)?[A-Za-z0-9_./@+$()\[\]-]+")
_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
# A token without a slash is a file only with one of these extensions (or if it exists), so
# symbols such as `Math.floor` or `res.cookies.set` are not taken for missing files.
_EXTENSIONS = """py pyi ts tsx js jsx mjs cjs json jsonc md mdx rst txt yml yaml toml ini cfg conf
env lock go mod sum rs java kt kts scala rb php cs fs swift m c h cc cpp hpp sql sh bash zsh ps1 css
scss sass less html htm svelte vue astro xml gradle proto graphql gql tf hcl ex exs erl dart lua r
ipynb csv tsv svg prisma sol zig"""
FILE_EXTENSIONS = frozenset(_EXTENSIONS.split())


def _trim(tok: str) -> str:
    tok = tok.rstrip(".")
    if tok.startswith("(") and tok.find(")") == len(tok) - 1:
        tok = tok[1:-1]  # (src/a.ts) in prose
    while tok.startswith("(") and tok.count("(") > tok.count(")"):
        tok = tok[1:]
    while tok.endswith(")") and tok.count(")") > tok.count("("):
        tok = tok[:-1]
    return tok.rstrip(".")


def _looks_like_path(tok: str, dir_hint: bool, repo: Path | None) -> bool:
    if not tok or tok.startswith("http"):
        return False
    if repo is not None and not tok.startswith("/") and (repo / tok).exists():
        return True
    if dir_hint:
        return True
    ext = tok.rsplit("/", 1)[-1].rpartition(".")[2]
    return "." in tok.rsplit("/", 1)[-1] and ext.lower() in FILE_EXTENSIONS


def evidence_tokens(text: str, repo: Path | None = None) -> list[str]:
    """Path-like tokens from the Evidence table's implementation and test columns.

    A token counts when it exists in ``repo``, ends with ``/`` (a directory) or ends in a file
    extension. Route URLs (`/api/me`), status lists (`401/400/503`) and symbols are prose."""
    m = re.search(
        r"^## Evidence\b[^\n]*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL
    )
    if not m:
        return []
    out: list[str] = []
    for ln in m.group(1).splitlines():
        if not ln.strip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0].startswith("---") or cells[0] == "Requirement":
            continue
        for cell in cells[1:3]:
            cell = _MD_LINK.sub(r"\1 \2", cell).replace("`", " ")
            for tok in _PATH_TOKEN.findall(cell):
                tok = _trim(tok)
                dir_hint = tok.endswith("/")
                tok = tok.rstrip("/")
                if _looks_like_path(tok, dir_hint, repo) and tok not in out:
                    out.append(tok)
    return out


def baseline_snapshot(repo: Path, text: str) -> dict:
    """Bounded source hashes and explicit gaps; excluded files and links are never read."""
    import groundwork_baseline as BL

    files: dict[str, str] = {}
    missing: list[str] = []
    skipped: list[str] = []
    truncated: list[str] = []
    root = repo.resolve()
    ctx = C.Ctx("standalone", root, repo=root)
    for tok in evidence_tokens(text, root):
        p = root / tok
        if BL.path_problem(ctx, p):
            skipped.append(tok)
            continue
        parts = p.relative_to(root).parts
        directory = p.is_dir()
        if any(
            _excluded_dir(part) for part in (parts if directory else parts[:-1])
        ) or (not directory and _excluded_file(p.name)):
            skipped.append(tok)
            continue
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            if rel not in files and len(files) >= MAX_EVIDENCE_FILES:
                truncated.append(tok)
            else:
                files[rel] = _file_hash(p)
        elif directory:
            n = 0
            for _, f in _walk(p, MAX_EVIDENCE_FILES + 1):
                n += 1
                rel = f.relative_to(root).as_posix()
                if rel not in files and len(files) >= MAX_EVIDENCE_FILES:
                    truncated.append(tok)
                    break
                files[rel] = _file_hash(f)
            if n == 0:
                missing.append(tok)
        else:
            missing.append(tok)
    return {
        "sources": files,
        "missing": sorted(set(missing)),
        "skipped": sorted(set(skipped)),
        "truncated": sorted(set(truncated)),
    }


def _evidence_problems(snap: dict) -> list[str]:
    reasons = []
    for key, label in (
        ("missing", "unresolved evidence paths"),
        ("skipped", "excluded or unsafe evidence paths (not read)"),
        (
            "truncated",
            f"evidence scan exceeds {MAX_EVIDENCE_FILES} files; cite narrower paths",
        ),
    ):
        if snap.get(key):
            reasons.append(label + ": " + ", ".join(snap[key][:5]))
    return reasons


def confirm_baseline(ctx: C.Ctx, slugs: list[str], who: str | None = None) -> list[str]:
    """Record that a person compared the baseline with its cited sources. Not an approval."""
    if not ctx.repo:
        raise SystemExit("baselines live in a repo; cd into one")
    import groundwork_baseline as BL

    data, done = load(ctx), []
    for slug in slugs:
        if not BL.DIR_RE.fullmatch(slug):
            raise SystemExit(f"invalid baseline slug '{slug}': expected NNN-slug")
        fdir = ctx.repo / "specs" / slug
        sp = fdir / "spec.md"
        BL._require_safe_paths(ctx, sp)
        if not sp.is_file():
            raise SystemExit(f"specs/{slug}/spec.md does not exist")
        text = sp.read_text(encoding="utf-8")
        meta, _ = C.split_fm(text)
        if not C.is_baseline(meta):
            raise SystemExit(
                f"{slug} is not a baseline (origin '{C.origin(meta) or 'planned'}')"
            )
        if C.PLACEHOLDER.search(text):
            raise SystemExit(
                f"{slug} still has [TODO]/[NEEDS CLARIFICATION] markers; an empty scaffold cannot confirm its sources"
            )
        snap = baseline_snapshot(ctx.repo, text)
        if snap["truncated"]:
            raise SystemExit(f"{slug}: " + "; ".join(_evidence_problems(snap)))
        if not snap["sources"]:
            raise SystemExit(
                f"{slug}: the Evidence table names no file that exists in this repo; fill it before reviewing"
                + (
                    f" (unresolved: {', '.join(snap['missing'][:4])})"
                    if snap["missing"]
                    else ""
                )
            )
        data[BASELINE_NS + slug] = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "epoch": int(time.time()),
            "by": who or C.signer(),
            "spec_hash": C.body_hash(text),
            "snapshot": snap,
        }
        done.append(slug)
    _save(ctx, data)
    return done


@dataclass
class BaselineReview:
    slug: str
    status: str  # current | review | unreviewed | unfinished | no-evidence
    reasons: list[str] = field(default_factory=list)
    at: str = ""


def baseline_review(ctx: C.Ctx, slug: str) -> BaselineReview:
    import groundwork_baseline as BL

    fdir = ctx.repo / "specs" / slug
    BL._require_safe_paths(ctx, fdir / "spec.md")
    text = (fdir / "spec.md").read_text(encoding="utf-8")
    if C.PLACEHOLDER.search(text):
        return BaselineReview(slug, "unfinished")
    rec = load(ctx).get(BASELINE_NS + slug)
    now = baseline_snapshot(ctx.repo, text)
    gaps = _evidence_problems(now)
    if gaps and not rec:
        return BaselineReview(slug, "review", ["sources never reviewed", *gaps])
    if not rec:
        if not now["sources"]:
            return BaselineReview(
                slug, "no-evidence", ["the Evidence table names no existing file"]
            )
        return BaselineReview(
            slug,
            "unreviewed",
            [
                "sources never reviewed (run: groundwork.py confirm --baseline "
                + slug
                + ")"
            ],
        )
    old = rec.get("snapshot", {})
    reasons = diff_snapshots(
        {"sources": old.get("sources", {})}, {"sources": now["sources"]}
    )
    if rec.get("spec_hash") != C.body_hash(text):
        reasons.append(
            "baseline body changed since source review; compare its requirements with the sources again"
        )
    reasons.extend(gaps)
    if reasons:
        return BaselineReview(slug, "review", reasons, rec.get("at", ""))
    return BaselineReview(slug, "current", [], rec.get("at", ""))


def assess_baselines(ctx: C.Ctx) -> list[BaselineReview]:
    if not ctx.repo:
        return []
    out = []
    for fdir in C.feature_dirs(ctx):
        if C.is_baseline(C.spec_meta(fdir)):
            out.append(baseline_review(ctx, fdir.name))
    return out
