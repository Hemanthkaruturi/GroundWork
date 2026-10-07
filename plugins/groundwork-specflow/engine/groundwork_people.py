"""Who is responsible for what — and whom to contact.

Three sources, all in the repository:
  * the people table in PROJECT.md ("Who works on what": Person | Role | Owns / ask them about | Contact)
  * current responsibility in front matter: requested_by, owner, implemented_by, support (spec / RFC),
    reported_by, owner, fixed_by (bug)
  * an append-only ledger (.groundwork/ledger.jsonl) of events: who requested, owns, implemented, deployed
    (environment + version), supports, handed over. CI can append deploy events.
Approvals are read from the approval records, not duplicated.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import groundwork_bugs as B
import groundwork_core as C
import groundwork_relations as R

EVENTS = {
    "requested",
    "owner",
    "implemented",
    "deployed",
    "support",
    "handover",
    "reported",
    "fixed",
}
LIST_ROLES = {"implemented_by", "support"}


@dataclass
class Person:
    name: str
    role: str = ""
    owns: str = ""
    contact: str = ""

    def label(self) -> str:
        bits = [self.name] + ([f"({self.role})"] if self.role else [])
        return " ".join(bits) + (f" — {self.contact}" if self.contact else "")


# --- the people table -----------------------------------------------------------------


def people_home(ctx: C.Ctx) -> Path | None:
    base = ctx.workspace or ctx.repo
    return C._find_ci(base, "PROJECT.md") if base else None


def people(ctx: C.Ctx) -> list[Person]:
    p = people_home(ctx)
    if not p:
        return []
    m = re.search(
        r"^## Who works on what[^\n]*\n(.*?)(?=^## |\Z)",
        p.read_text(encoding="utf-8"),
        re.MULTILINE | re.DOTALL,
    )
    if not m:
        return []
    rows = [ln for ln in m.group(1).splitlines() if ln.strip().startswith("|")]
    if len(rows) < 3:
        return []
    head = [c.strip().lower() for c in rows[0].strip().strip("|").split("|")]

    def col(*names: str) -> int | None:
        return next((i for i, h in enumerate(head) if any(n in h for n in names)), None)

    ci = {
        "name": col("person", "name"),
        "role": col("role"),
        "owns": col("owns", "ask"),
        "contact": col("contact"),
    }
    out = []
    for r in rows[2:]:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if any(C.PLACEHOLDER.search(c) for c in cells) or not any(cells):
            continue
        get = lambda k, cells=cells: (
            cells[ci[k]] if ci[k] is not None and ci[k] < len(cells) else ""
        )
        if get("name"):
            out.append(Person(get("name"), get("role"), get("owns"), get("contact")))
    return out


def resolve(ppl: list[Person], s: str) -> Person | None:
    s0 = (s or "").strip().lower()
    if not s0:
        return None
    for p in ppl:
        if p.name.lower() == s0:
            return p
    for p in ppl:
        toks = re.split(r"[\s,;<>()]+", p.contact.lower())
        if s0 in toks or (len(s0) >= 4 and s0 in p.contact.lower()):
            return p
    hits = [
        p for p in ppl if p.name.lower().startswith(s0) or s0 in p.name.lower().split()
    ]
    return hits[0] if len(hits) == 1 and len(s0) >= 3 else None


def show(ppl: list[Person], s: str) -> str:
    if not s:
        return "(not recorded)"
    p = resolve(ppl, s)
    return p.label() if p else f"{s} (not listed in PROJECT.md)"


def whoami(ctx: C.Ctx) -> str:
    me = C.signer()
    p = resolve(people(ctx), me)
    return (
        f"{me} → {p.label()}"
        if p
        else f"{me} (not listed in PROJECT.md 'Who works on what')"
    )


# --- refs -----------------------------------------------------------------------------


def locate(ctx: C.Ctx, ref: str) -> tuple[str, C.Ctx, Path] | None:
    """(kind, owning ctx, document) for a feature / RFC / bug reference."""
    ref = ref.strip()
    if re.match(r"(?i)rfc-?\d+", ref):
        p = C.find_rfc(ctx, ref)
        return ("rfc", ctx, p) if p else None
    repo_part, _, rest = ref.partition("/")
    if rest.startswith("bugs/") or ref.startswith("bugs/"):
        slug = ref.split("bugs/")[-1]
        rc = (
            ctx
            if ref.startswith("bugs/")
            else (
                C.detect(ctx.workspace / repo_part, ctx.workspace)
                if ctx.workspace
                else None
            )
        )
        if rc and rc.repo and (rc.repo / "bugs" / f"{slug}.md").is_file():
            return "bug", rc, rc.repo / "bugs" / f"{slug}.md"
        return None
    rc, fdir = C.resolve_feature(ctx, ref)
    return ("feature", rc, fdir / "spec.md") if fdir else None


def ledger_file(kind: str, owner: C.Ctx) -> Path:
    root = owner.rfc_home if kind == "rfc" else (owner.repo or owner.root)
    return root / ".groundwork" / "ledger.jsonl"


def key_of(kind: str, doc: Path) -> str:
    return (
        doc.stem
        if kind == "rfc"
        else (f"bugs/{doc.stem}" if kind == "bug" else doc.parent.name)
    )


def read_ledger(kind: str, owner: C.Ctx, key: str) -> list[dict]:
    f = ledger_file(kind, owner)
    out = []
    try:
        for ln in f.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(ln)
            except ValueError:
                continue
            if e.get("ref") == key or (
                kind == "rfc"
                and e.get("ref") == key.split("-")[0] + "-" + key.split("-")[1]
            ):
                out.append(e)
    except OSError:
        pass
    return out


def set_role(
    doc: Path, role: str, value: str | list[str], append: bool = False
) -> None:
    text = doc.read_text(encoding="utf-8")
    meta, _ = C.split_fm(text)
    if role in LIST_ROLES:
        cur = C.list_of(meta, role) if append else []
        new = cur + [
            v for v in (value if isinstance(value, list) else [value]) if v not in cur
        ]
        rendered = "[" + ", ".join(new) + "]"
    else:
        rendered = value if isinstance(value, str) else ", ".join(value)
    doc.write_text(C.set_fm(text, {role: rendered}), encoding="utf-8")


ROLE_FOR_EVENT = {
    "requested": "requested_by",
    "owner": "owner",
    "implemented": "implemented_by",
    "support": "support",
    "handover": "owner",
    "reported": "reported_by",
    "fixed": "fixed_by",
}


def record(
    ctx: C.Ctx,
    event: str,
    ref: str,
    by: str | None = None,
    via: str | None = None,
    who: list[str] | None = None,
    env: str | None = None,
    version: str | None = None,
    text: str = "",
) -> dict:
    if event not in EVENTS:
        raise SystemExit(f"unknown event '{event}'; one of {sorted(EVENTS)}")
    loc = locate(ctx, ref)
    if not loc:
        raise SystemExit(
            f"cannot find '{ref}' (feature NNN-slug, repo/NNN-slug, RFC-000N or bugs/NNN-slug)"
        )
    kind, owner, doc = loc
    if event == "deployed" and not (env and version):
        raise SystemExit(
            "deployed needs --env and --version (e.g. --env prod --version 1.4.0)"
        )
    if event in ("requested", "owner", "support", "handover", "reported") and not who:
        raise SystemExit(f"{event} needs --who <name[,name]>")
    by = by or C.signer()
    e = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "event": event,
        "ref": key_of(kind, doc),
        "by": by,
    }
    for k, v in (
        ("via", via),
        ("env", env),
        ("version", version),
        ("who", who),
        ("text", text or None),
    ):
        if v:
            e[k] = v
    f = ledger_file(kind, owner)
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(e) + "\n")
    role = ROLE_FOR_EVENT.get(event)
    if role:
        val = (
            who
            if event in ("requested", "owner", "support", "handover", "reported")
            else [by]
        )
        if role == "support":
            set_role(doc, role, val or [])
        elif role in LIST_ROLES:
            set_role(doc, role, val, append=True)
        else:
            set_role(doc, role, ", ".join(val) if isinstance(val, list) else val)
    return e


def auto_created(
    ctx: C.Ctx, kind: str, doc: Path, requested_by: str | None = None
) -> None:
    """Called when an RFC / feature / bug is created: owner = whoever ran it, plus a ledger line."""
    owner_ctx = ctx
    me = C.signer()
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "event": "created",
        "ref": key_of(kind, doc),
        "by": me,
    }
    f = ledger_file(kind, owner_ctx)
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    set_role(doc, "owner", me)
    if requested_by:
        set_role(doc, "requested_by", requested_by)


# --- rendering ------------------------------------------------------------------------


def _git_contributors(repo: Path, slug: str) -> list[tuple[str, int]]:
    try:
        out = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "log",
                "--format=%an <%ae>",
                f"--grep={slug}",
                "-i",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        ).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return []
    counts: dict[str, int] = {}
    for a in out:
        counts[a] = counts.get(a, 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])[:5]


def _approvals(kind: str, owner: C.Ctx, doc: Path) -> str:
    st = C.doc_state(doc, owner)
    rec = C.load_approvals(C.owner_root(doc, owner)).get(
        str(doc.resolve().relative_to(C.owner_root(doc, owner).resolve()))
    )
    if not rec:
        return f"not approved ({st.status})"
    who = ", ".join(s["who"] + " " + s["at"][:10] for s in rec["signers"])
    return f"{st.status}: {who}" + (
        "  [STALE — edited since]" if st.status == "stale" else ""
    )


def describe(ctx: C.Ctx, ref: str) -> str:
    loc = locate(ctx, ref)
    if not loc:
        return f"No feature, RFC or bug matches '{ref}'."
    kind, owner, doc = loc
    ppl = people(ctx)
    meta, _ = C.split_fm(doc.read_text(encoding="utf-8"))
    key = key_of(kind, doc)
    events = read_ledger(kind, owner, key)
    lines = [f"{key}  [{kind}]  {meta.get('title', '')}".rstrip(), ""]
    rows: list[tuple[str, str]] = []
    row = lambda k, v: rows.append((k, v))
    if kind == "bug":
        row("Reported by", show(ppl, meta.get("reported_by", "")))
        row("Owner", show(ppl, meta.get("owner", "")))
        row("Fixed by", show(ppl, meta.get("fixed_by", "")))
    else:
        row("Requested by", show(ppl, meta.get("requested_by", "")))
        row("Owner", show(ppl, meta.get("owner", "")))
        row("Author", show(ppl, meta.get("author", "")))
        row("Approved", _approvals(kind, owner, doc))
        if kind == "feature":
            impl = C.list_of(meta, "implemented_by")
            row(
                "Implemented by",
                "; ".join(show(ppl, x) for x in impl) if impl else "(not recorded)",
            )
            sup = C.list_of(meta, "support")
            row(
                "Support",
                "; ".join(show(ppl, x) for x in sup) if sup else "(not recorded)",
            )
            dep = [e for e in events if e["event"] == "deployed"]
            if dep:
                latest: dict[str, dict] = {}
                for e in dep:
                    latest[e.get("env", "?")] = e
                for env, e in latest.items():
                    row(
                        f"Deployed → {env}",
                        f"{e.get('version', '?')} by {show(ppl, e['by'])} on {e['ts'][:10]}",
                    )
            else:
                row("Deployed", "(no deployment recorded)")
            cont = _git_contributors(owner.repo, key.split("/")[-1])
            if cont:
                row("Commits naming it", ", ".join(f"{a} ×{n}" for a, n in cont))
    width = max([16] + [len(k) + 2 for k, _ in rows])
    lines += [f"  {k:<{width}}{v}" for k, v in rows]
    if events:
        lines += ["", "  History"]
        for e in events[-12:]:
            extra = " ".join(f"{k}={e[k]}" for k in ("env", "version") if e.get(k))
            who = f" → {', '.join(e['who'])}" if e.get("who") else ""
            via = f" (via {e['via']})" if e.get("via") else ""
            lines.append(
                f"    {e['ts'][:16]}  {e['event']:<11} {show(ppl, e['by'])}{via}{who} {extra}".rstrip()
            )
    if kind == "feature":
        node = (owner.repo.name, doc.parent.name)
        mine = [e for e in R.edges(ctx) if e.src == node and e.dst]
        down = R.downstream(ctx, node)
        lines += ["", "  People to talk to before changing it"]
        seen = False
        for e in mine:
            _trc, tfd = C.resolve_feature(
                owner,
                f"{e.dst[0]}/{e.dst[1]}" if e.dst[0] != owner.repo.name else e.dst[1],
            )
            if tfd:
                m2, _ = C.split_fm((tfd / "spec.md").read_text(encoding="utf-8"))
                lines.append(
                    f"    it {e.kind.replace('_', ' ')} {e.dst[0]}/{e.dst[1]} — owner: {show(ppl, m2.get('owner', ''))}"
                )
                seen = True
        for item in down["features"]:
            tref = item.split("  (")[0]
            _trc, tfd = C.resolve_feature(owner, tref)
            if tfd:
                m2, _ = C.split_fm((tfd / "spec.md").read_text(encoding="utf-8"))
                lines.append(
                    f"    affects {item} — owner: {show(ppl, m2.get('owner', ''))}"
                )
                seen = True
        if not seen:
            lines.append("    (independent: no related features)")
    return "\n".join(lines)


def person_items(ctx: C.Ctx, who: str) -> str:
    ppl = people(ctx)
    p = resolve(ppl, who)
    target = p.name if p else who
    lines = [(p.label() if p else f"{who} (not listed in PROJECT.md)"), ""]
    if p and p.owns:
        lines.append(f"  listed as owning/knowing: {p.owns}")
    found = 0
    for kind, ref, meta in _all_items(ctx):
        roles = [
            r
            for r in (
                "requested_by",
                "owner",
                "implemented_by",
                "support",
                "reported_by",
                "fixed_by",
            )
            if any(
                resolve(ppl, x) == p if p else x.lower() == target.lower()
                for x in C.list_of(meta, r)
            )
        ]
        if roles:
            lines.append(f"  {ref:<32} {', '.join(roles)}")
            found += 1
    return "\n".join(
        lines
        + ([] if found else ["  (no features, RFCs or bugs recorded for this person)"])
    )


def _all_items(ctx: C.Ctx):
    for r in C.rfcs(ctx):
        yield "rfc", r.path.stem, r.meta
    for rc in R.contexts(ctx):
        for fdir in C.feature_dirs(rc):
            if (fdir / "spec.md").is_file():
                yield (
                    "feature",
                    f"{rc.repo.name}/{fdir.name}",
                    C.split_fm((fdir / "spec.md").read_text(encoding="utf-8"))[0],
                )
        for bp in B.bug_paths(rc):
            yield (
                "bug",
                f"{rc.repo.name}/bugs/{bp.stem}",
                C.split_fm(bp.read_text(encoding="utf-8"))[0],
            )


def table(ctx: C.Ctx) -> str:
    ppl = people(ctx)
    lines = [
        f"{'ITEM':<34}{'OWNER':<18}{'REQUESTED BY':<18}{'IMPLEMENTED BY':<18}SUPPORT"
    ]
    short = lambda s: (resolve(ppl, s).name if resolve(ppl, s) else s) if s else "-"
    for kind, ref, meta in _all_items(ctx):
        impl = ",".join(short(x) for x in C.list_of(meta, "implemented_by")) or "-"
        sup = ",".join(short(x) for x in C.list_of(meta, "support")) or "-"
        lines.append(
            f"{ref:<34}{short(meta.get('owner', '')):<18}{short(meta.get('requested_by', meta.get('reported_by', ''))):<18}{impl:<18}{sup}"
        )
    return "\n".join(lines)
