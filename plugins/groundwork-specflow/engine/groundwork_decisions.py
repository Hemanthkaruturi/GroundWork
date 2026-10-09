"""ADRs — the outcome of a decision, kept in DECISIONS/ next to the RFCs (STANDARD.md §4, §5j).

Two kinds. After an approved RFC is built, an ADR records what was decided (`rfc:` set). In an adopted
codebase a choice may be found with no RFC behind it: a RETROSPECTIVE ADR (`origin: baseline`,
`status: recorded`) keeps it, and says plainly where its reasons come from — a document, a person
explaining it now, or nowhere. A commit subject or a folder name is a topic lead, never proof of the
reason, the approver or the date. Nothing here is written in bulk: a person picks each one.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import groundwork_core as C

FIELDS = ["id", "title", "status", "created", "rationale_source"]
STATUSES = {"proposed", "accepted", "superseded", "recorded"}
RATIONALE_SOURCES = {"documented", "retrospective", "unknown"}
SECTIONS = ["Context", "Decision", "Rationale", "Consequences", "Evidence"]
SOURCE_LABEL = re.compile(r"^\*\*Source:\*\*\s*(.+?)\s*$")
LABEL_FOR = {  # the complete label, nothing less
    "documented": re.compile(r"^documented in\s+\S+.*$", re.IGNORECASE),
    "retrospective": re.compile(
        r"^retrospective explanation by\s+\S.*?,\s*\d{4}-\d{2}-\d{2}\.?$", re.IGNORECASE
    ),
    "unknown": re.compile(r"^historical rationale unknown\.?$", re.IGNORECASE),
}


def section(text: str, n: int) -> str | None:
    m = re.search(rf"^## {n}\.[^\n]*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return m.group(1) if m else None


def _content_lines(body: str) -> list[str]:
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    return [ln.strip() for ln in body.splitlines() if ln.strip()]


def indexed(index_text: str, doc_id: str) -> bool:
    """Listed in DECISIONS/README.md means a table row, not a mention in prose."""
    return bool(re.search(rf"^\|\s*{re.escape(doc_id)}\s*\|", index_text, re.MULTILINE))


def home(ctx: C.Ctx) -> Path:
    return ctx.rfc_home / "DECISIONS"


def paths(ctx: C.Ctx) -> list[Path]:
    d = home(ctx)
    return sorted(d.glob("ADR-*.md")) if d.is_dir() else []


def find(ctx: C.Ctx, ref: str) -> Path | None:
    m = re.match(r"(?:ADR-)?0*(\d+)$", (ref or "").strip(), re.IGNORECASE)
    if not m:
        return None
    for p in paths(ctx):
        n = re.match(r"ADR-0*(\d+)", p.name)
        if n and int(n.group(1)) == int(m.group(1)):
            return p
    return None


def new_adr(
    ctx: C.Ctx,
    slug: str,
    title: str | None,
    retrospective: bool,
    rfc: str | None,
    source: str | None,
    decided_at: str | None,
) -> Path:
    if ctx.level == "unknown":
        raise SystemExit("Not in a repo or workspace.")
    d = home(ctx)
    import groundwork_baseline as BL

    for target in (d, d / "README.md"):
        problem = BL.path_problem_under(ctx.rfc_home, target)
        if problem:
            raise SystemExit(problem)
    d.mkdir(parents=True, exist_ok=True)
    clean = C.slugify(slug)
    if not clean:
        raise SystemExit("give a slug (letters, digits, hyphens)")
    rfc_path = None
    if rfc:
        rfc_path = C.find_rfc(ctx, rfc)
        if rfc_path is None:
            raise SystemExit(f"RFC '{rfc}' not found in {d}")
        rst = C.doc_state(rfc_path, ctx)
        if not rst.approved:
            raise SystemExit(
                f"{rfc_path.name} is {rst.status}, not approved: an ADR records the outcome of an approved RFC"
            )
    if retrospective and rfc_path is not None:
        raise SystemExit(
            "a retrospective ADR has no RFC behind it; drop --rfc or --retrospective"
        )
    n = C.next_number([p.name for p in d.glob("ADR-*.md")], r"ADR-0*(\d+)")
    aid = f"ADR-{n:04d}"
    p = d / f"{aid}-{clean}.md"
    if p.exists() or p.is_symlink():
        raise SystemExit(f"{p} already exists")
    rationale_source = (
        ("documented" if source else "unknown") if retrospective else "documented"
    )
    p.write_text(
        C.render(
            "ADR.md",
            id=aid,
            title=title or clean.replace("-", " ").title(),
            status="recorded" if retrospective else "proposed",
            origin="baseline" if retrospective else "",
            rfc=(rfc_path.stem.split("-")[0] + "-" + rfc_path.stem.split("-")[1])
            if rfc_path
            else "",
            decided_at=decided_at or "unknown",  # a date only when a document states it
            rationale_source=rationale_source,
            source=source or (f"DECISIONS/{rfc_path.name}" if rfc_path else ""),
            author=C.signer(),
            date=time.strftime("%F"),
        ),
        encoding="utf-8",
    )
    if not retrospective:
        p.write_text(
            BL._remove_fm_keys(p.read_text(encoding="utf-8"), {"origin"}),
            encoding="utf-8",
        )
    index = d / "README.md"
    if not index.is_file():
        index.write_text(
            C.render("DECISIONS-index.md", name=ctx.rfc_home.name), encoding="utf-8"
        )
    row = f"| {aid} | {title or clean.replace('-', ' ').title()} | {'recorded' if retrospective else 'proposed'} | {'retrospective' if retrospective else ''} |\n"
    text = index.read_text(encoding="utf-8")
    if not indexed(text, aid):  # the same test `check` applies: a row, not a mention
        index.write_text(text.rstrip("\n") + "\n" + row, encoding="utf-8")
    return p


def metadata_problems(ctx: C.Ctx, path: Path, meta: dict) -> list[str]:
    bad = [f"front matter missing: {f}" for f in FIELDS if f not in meta]
    bad += [
        f"front matter blank: {f}"
        for f in FIELDS
        if f in meta and not str(meta.get(f) or "").strip()
    ]
    if meta.get("id") and not path.name.startswith(meta["id"] + "-"):
        bad.append(f"id '{meta['id']}' does not match the file name")
    st = str(meta.get("status", "") or "").strip()
    if st and st not in STATUSES:
        bad.append(f"status must be one of {sorted(STATUSES)} (now '{st}')")
    rs = str(meta.get("rationale_source", "") or "").strip()
    if rs and rs not in RATIONALE_SOURCES:
        bad.append(
            f"rationale_source must be one of {sorted(RATIONALE_SOURCES)} (now '{rs}')"
        )
    o = C.origin(meta)
    if o and o != "baseline":
        bad.append(
            f"origin '{o}' is not valid for an ADR (a retrospective one uses 'baseline')"
        )
    if o == "baseline" and st and st != "recorded":
        bad.append("a retrospective ADR (origin: baseline) has status: recorded")
    if st == "recorded" and o != "baseline":
        bad.append("status: recorded is for a retrospective ADR (origin: baseline)")
    rfc_ref = str(meta.get("rfc") or "").strip()
    if o == "baseline" and rfc_ref:
        bad.append(
            "a retrospective ADR has no RFC behind it; drop `rfc` or the baseline origin"
        )
    if rfc_ref and C.find_rfc(ctx, rfc_ref) is None:
        bad.append(f"rfc '{rfc_ref}' does not exist")
    for ref in C.list_of(meta, "supersedes"):
        if find(ctx, ref) is None and C.find_rfc(ctx, ref) is None:
            bad.append(f"supersedes: {ref} does not exist")
    return bad


def rationale_problems(meta: dict, text: str) -> list[str]:
    """A finished ADR says, first thing in §3, where its reasons come from — with the complete label —
    and the label matches the front matter."""
    bad = []
    rs = str(meta.get("rationale_source", "") or "").strip()
    body = section(text, 3)
    first = _content_lines(body or "")
    m = SOURCE_LABEL.match(first[0]) if first else None
    if body is None or not m:
        bad.append(
            "§3 Rationale must begin with a '**Source:**' line (documented in <path or commit> | "
            "retrospective explanation by <person>, <YYYY-MM-DD> | historical rationale unknown)"
        )
        return bad
    label = m.group(1)
    kind = next((k for k, rx in LABEL_FOR.items() if rx.match(label)), None)
    if kind is None:
        bad.append(
            f"'**Source:** {label}' is none of: documented in <path or commit> · "
            "retrospective explanation by <person>, <YYYY-MM-DD> · historical rationale unknown"
        )
    elif rs and kind != rs:
        bad.append(f"rationale_source is '{rs}' but §3 says '{label}'")
    if kind == "documented" and not str(meta.get("source", "") or "").strip():
        bad.append("rationale is documented: name the document or commit in `source`")
    return bad
