"""How features relate: depends_on, builds_against, extends, amends — and who is affected by a change.

Relations live in spec front matter (values are `NNN-slug` in the same repo or `repo/NNN-slug` in a
sibling repo of the workspace). Everything here is read from files; nothing is remembered.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import groundwork_bugs as B
import groundwork_core as C

KINDS = ["depends_on", "builds_against", "extends", "amends"]
Node = tuple[str, str]      # (repo name, feature slug)


@dataclass
class Edge:
    src: Node
    kind: str
    raw: str
    dst: Node | None        # None when the reference does not resolve


def contexts(ctx: C.Ctx) -> list[C.Ctx]:
    if ctx.level == "workspace":
        return [C.detect(k, ctx.workspace) for k in C.child_repos(ctx.workspace)]
    if ctx.level == "repo" and ctx.workspace:
        return [C.detect(k, ctx.workspace) for k in C.child_repos(ctx.workspace)]   # siblings matter for cross-repo refs
    return [ctx] if ctx.level in ("repo", "standalone") else []


def edges(ctx: C.Ctx) -> list[Edge]:
    out = []
    for rc in contexts(ctx):
        for fdir in C.feature_dirs(rc):
            sp = fdir / "spec.md"
            if not sp.is_file():
                continue
            meta, _ = C.split_fm(sp.read_text(encoding="utf-8"))
            for kind in KINDS:
                for raw in C.list_of(meta, kind):
                    trc, tfd = C.resolve_feature(rc, raw)
                    out.append(Edge((rc.repo.name, fdir.name), kind, raw, (trc.repo.name, tfd.name) if tfd else None))
    return out


def node_of(ctx: C.Ctx, ref: str) -> Node | None:
    if "/" not in ref and ctx.repo:
        return (ctx.repo.name, ref)
    repo, _, slug = ref.partition("/")
    return (repo, slug)


def find_cycles(es: list[Edge]) -> list[list[Node]]:
    graph: dict[Node, list[Node]] = {}
    for e in es:
        if e.dst and e.kind in ("depends_on", "builds_against", "extends"):
            graph.setdefault(e.src, []).append(e.dst)
    cycles, seen = [], set()

    def dfs(n: Node, path: list[Node]) -> None:
        if n in path:
            cyc = path[path.index(n):] + [n]
            key = frozenset(cyc)
            if key not in seen:
                seen.add(key); cycles.append(cyc)
            return
        for m in graph.get(n, []):
            dfs(m, path + [n])

    for n in list(graph):
        dfs(n, [])
    return cycles


def fmt(n: Node) -> str:
    return f"{n[0]}/{n[1]}"


def downstream(ctx: C.Ctx, target: Node) -> dict[str, list[str]]:
    """Who is affected if `target` (a feature) changes."""
    res: dict[str, list[str]] = {"features": [], "bugs": []}
    for e in edges(ctx):
        if e.dst == target:
            res["features"].append(f"{fmt(e.src)}  ({e.kind})")
    for rc in contexts(ctx):
        for bp in B.bug_paths(rc):
            meta, _ = C.split_fm(bp.read_text(encoding="utf-8"))
            hits = [r for r in C.list_of(meta, "violates") if node_of(rc, r.partition("@")[2].strip()) == target]
            hits += [a for a in C.list_of(meta, "amends") if node_of(rc, a) == target]
            if hits:
                res["bugs"].append(f"{rc.repo.name}/bugs/{bp.stem}  ({meta.get('status', '?')})")
    return res


def describe(ctx: C.Ctx, ref: str) -> str:
    rfc = re.match(r"(?i)rfc-?\d+", ref)
    lines = []
    if rfc:
        p = C.find_rfc(ctx, ref)
        if not p:
            return f"No such RFC: {ref}"
        rid = C.split_fm(p.read_text(encoding="utf-8"))[0].get("id", p.stem)
        lines.append(f"{rid}: specs built from it")
        for rc in contexts(ctx):
            for fdir in C.feature_dirs(rc):
                m, _ = C.split_fm((fdir / "spec.md").read_text(encoding="utf-8")) if (fdir / "spec.md").is_file() else ({}, "")
                if m.get("rfc") == rid:
                    lines.append(f"  - {rc.repo.name}/{fdir.name}")
        for r in C.rfcs(ctx):
            if rid in C.list_of(r.meta, "supersedes") or rid in C.list_of(r.meta, "related_rfcs"):
                lines.append(f"  - {r.path.stem}  (RFC that supersedes/relates to it)")
        return "\n".join(lines)
    node = node_of(ctx, ref) or ("", "")
    if not ctx.repo and "/" not in ref:
        return "Give a feature as repo/NNN-slug."
    mine = [e for e in edges(ctx) if e.src == node]
    lines.append(f"{fmt(node)}")
    for e in mine:
        rc = ctx if "/" not in e.raw else ctx
        state = "MISSING" if e.dst is None else ""
        if e.dst:
            for c in contexts(ctx):
                if c.repo.name == e.dst[0]:
                    ok, prog = C.feature_implemented(c, c.repo / "specs" / e.dst[1])
                    state = "implemented" if ok else f"not implemented ({prog})"
        lines.append(f"  {e.kind:<15} {e.raw}  [{state}]")
    if not mine:
        lines.append("  (independent: no declared relations)")
    d = downstream(ctx, node)
    lines.append("  affects (downstream):")
    for k in ("features", "bugs"):
        for x in d[k]:
            lines.append(f"    - {x}")
    if not d["features"] and not d["bugs"]:
        lines.append("    (nothing depends on it)")
    return "\n".join(lines)
