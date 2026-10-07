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


def _walk(root: Path, max_files: int = 3000):
    n = 0
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(
            x
            for x in dirs
            if x not in C.SKIP_DIRS
            and x not in {".groundwork", "specs"}
            and not (x.startswith(".") and x != ".github")
        )
        for f in sorted(files):
            # Infrastructure directories can contain local secrets alongside manifests.
            # Never open those files or follow file links out of the project.
            if (f.startswith(".") and f != ".gitlab-ci.yml") or Path(d, f).is_symlink():
                continue
            if any(
                fnmatch.fnmatch(f.lower(), pattern)
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
            ):
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
    try:
        return json.loads(
            (_base(ctx) / ".groundwork" / "freshness.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return {}


def _save(ctx: C.Ctx, data: dict) -> None:
    f = _base(ctx) / ".groundwork" / "freshness.json"
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
