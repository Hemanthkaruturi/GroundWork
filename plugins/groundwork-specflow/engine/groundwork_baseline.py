"""Baselines, imported legacy specs and the capability index (STANDARD.md §5j).

A **baseline** (`origin: baseline`) is a spec that describes behaviour which existed before GroundWork:
history, not work. It descends from no RFC, needs no plan/tasks/evals, is never in flight, and once a
human approves it a feature can `extend` or `amend` it and a bug can cite its requirements.

An **imported** spec (`origin: imported`) is a legacy document (spec-kit or hand-written) that
`adopt-specs` brought under GroundWork's metadata without touching its body. It is `pending` until a
person classifies it as baseline, planned or archived; until then it is a reference, not a requirement.

The **capability index** (`.groundwork/capabilities.json`, rendered into `specs/README.md`) records what
the repo does, which capability has a spec, and what is still deferred. The table is generated the way
CODEMAP.md is: engine-owned columns are rewritten, the Notes column is kept.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

import groundwork_core as C

CAPS_REL = Path(".groundwork") / "capabilities.json"
INDEX_REL = Path("specs") / "README.md"
BASELINE_SECTIONS = ["Intent and rationale", "Known discrepancies", "Evidence"]
LIFECYCLES = ["active", "legacy", "retired", "planned", "uncertain"]
CLASSIFICATIONS = ["baseline", "planned", "archived"]
CAP_FIELDS = (
    "title",
    "lifecycle",
    "suggested_lifecycle",
    "sources",
    "rationale_ref",
    "next_action",
)
LIST_FIELDS = {"sources", "specs", "interview_notes"}
STAMP = re.compile(r"<!-- groundwork:capabilities facts=([0-9a-f]{12}) -->")
BLOCK = re.compile(
    r"<!-- groundwork:capabilities start -->.*?<!-- groundwork:capabilities end -->\n?",
    re.DOTALL,
)
DIR_RE = re.compile(r"\d{3}-[a-z0-9]+(-[a-z0-9]+)*")
TITLE_RE = re.compile(r"^#\s+(?:Spec:\s*)?(.+?)\s*$", re.MULTILINE)
DONE_STATUSES = {"implemented", "done", "shipped", "complete", "completed", "released"}
FINISHED_LABELS = DONE_STATUSES | {"approved"}


def _field(text: str, name: str) -> str:
    m = re.search(rf"^\*\*{name}:\*\*\s*(.+?)\s*$", text, re.MULTILINE | re.IGNORECASE)
    v = m.group(1).strip() if m else ""
    return "" if v in ("—", "-", "–", "n/a", "N/A") else v


def _repos(ctx: C.Ctx) -> list[C.Ctx]:
    if ctx.level == "workspace":
        return [C.detect(k, ctx.workspace) for k in C.child_repos(ctx.workspace)]
    return [ctx] if ctx.level in ("repo", "standalone") else []


def today() -> str:
    return time.strftime("%F")


# --- front matter editing (byte-preserving for the body) -------------------------------


def _remove_fm_keys(text: str, keys: set[str]) -> str:
    m = C.FM.match(text)
    if not m:
        return text
    lines = [
        ln
        for ln in m.group(1).splitlines()
        if not any(ln.startswith(k + ":") for k in keys)
    ]
    return "---\n" + "\n".join(lines) + "\n---\n" + text[m.end() :]


def _add_fm(text: str, fields: dict) -> str:
    """Add front matter keys. With no block: prepend one (the body stays byte-identical).
    With an existing block: add only the keys that are absent; existing keys are never changed."""
    m = C.FM.match(text)
    if not m:
        block = "\n".join(f"{k}: {v}".rstrip() for k, v in fields.items())
        return "---\n" + block + "\n---\n" + text
    present = {ln.split(":", 1)[0] for ln in m.group(1).splitlines() if ":" in ln}
    add = {k: v for k, v in fields.items() if k not in present}
    return C.set_fm(text, add) if add else text


# --- legacy documents: inventory, import, classification -------------------------------


def candidate_info(rc: C.Ctx, fdir: Path) -> dict | None:
    """Facts about a spec directory that has no GroundWork lineage (no `origin`, no `rfc`)."""
    sp = fdir / "spec.md"
    if not sp.is_file():
        return None
    raw = sp.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    meta, body = C.split_fm(text)
    if "origin" in meta or "rfc" in meta:
        return None  # already a GroundWork document
    from groundwork_check import SPEC_SECTIONS, missing_sections

    problem = ""
    if text.startswith("---") and not meta:
        problem = "front matter block cannot be parsed"
    elif meta.get("id") and meta.get("id") != fdir.name:
        problem = f"front matter id '{meta.get('id')}' differs from the directory name"
    title = (
        meta.get("title")
        or (TITLE_RE.search(body).group(1) if TITLE_RE.search(body) else "")
        or fdir.name
    )
    done, total = C.task_counts(rc, fdir.name)
    return {
        "slug": fdir.name,
        "path": sp,
        "name_ok": bool(DIR_RE.fullmatch(fdir.name)),
        "title": title.strip(),
        "original_status": str(meta.get("status") or _field(body, "Status")),
        "created": str(meta.get("created") or _field(body, "Created")),
        "owner": str(meta.get("owner") or _field(body, "Owner")),
        "has_fm": bool(meta),
        "foreign_keys": sorted(meta),
        "problem": problem,
        "companions": [
            n for n in ("plan.md", "tasks.md", "evals.md") if (fdir / n).is_file()
        ],
        "headings": [
            h for _, h in __import__("groundwork_check").headings(text, False)
        ],
        "missing_sections": missing_sections(text, SPEC_SECTIONS, numbered=True),
        "markers": len(C.PLACEHOLDER.findall(body)),
        "tasks": [done, total],
    }


def candidates(rc: C.Ctx) -> list[dict]:
    out = []
    for fdir in C.feature_dirs(rc):
        info = candidate_info(rc, fdir)
        if info:
            out.append(info)
    return out


def _finished_label(status: str) -> bool:
    return status.strip().lower() in FINISHED_LABELS


def import_specs(rc: C.Ctx, slugs: list[str] | None, dry: bool) -> dict:
    """Bring legacy spec directories under GroundWork metadata as `origin: imported` / `pending`.
    Bodies are byte-preserved; existing front matter keys are never changed; rerunning is a no-op."""
    rep: dict = {"imported": [], "review": [], "not_found": [], "unfinished": []}
    cands = candidates(rc)
    wanted = set(slugs or [])
    found = {c["slug"] for c in cands}
    rep["not_found"] = sorted(wanted - found)
    provenance = "spec-kit" if (rc.repo / ".specify").is_dir() else "unknown"
    for c in cands:
        if wanted and c["slug"] not in wanted:
            continue
        if not c["name_ok"]:
            rep["review"].append(
                f"{c['slug']}: directory is not NNN-slug (lowercase, hyphens); rename it by hand, then rerun"
            )
            continue
        if c["problem"]:
            rep["review"].append(
                f"{c['slug']}: {c['problem']}; fix it by hand, then rerun"
            )
            continue
        fields: dict[str, str] = {
            "id": c["slug"],
            "title": c["title"],
            "status": "draft",
            "origin": "imported",
            "adoption_state": "pending",
            "adopted_from": provenance,
            "adopted_status": c["original_status"] or "unknown",
            "adopted_at": today(),
        }
        if c["created"]:
            fields["created"] = c["created"]
        if c["owner"]:
            fields["author"] = c["owner"]
        fields["historical_companions"] = "[" + ", ".join(c["companions"]) + "]"
        for k in (
            "owner",
            "support",
            "extends",
            "depends_on",
            "builds_against",
            "amends",
        ):
            fields[k] = "" if k == "owner" else "[]"
        if not c["original_status"] or not _finished_label(c["original_status"]):
            rep["unfinished"].append(
                f"{c['slug']}: original status '{c['original_status'] or 'none'}'"
                + (f", tasks {c['tasks'][0]}/{c['tasks'][1]}" if c["tasks"][1] else "")
            )
        rep["imported"].append(c["slug"])
        if dry:
            continue
        p: Path = c["path"]
        raw = p.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        new = _add_fm(text, fields)
        p.write_text(new, encoding="utf-8")
        cap_link(rc, cap_slug_for(c["slug"]), c["slug"], title=c["title"], create=True)
        cap_set(
            rc,
            cap_slug_for(c["slug"]),
            next_action="classify the imported spec (baseline skill)",
        )
    if not dry and rep["imported"]:
        write_index(rc)
    return rep


def cap_slug_for(spec_slug: str) -> str:
    return re.sub(r"^\d{3}-", "", spec_slug)


def classify(rc: C.Ctx, kind: str, slugs: list[str]) -> list[str]:
    if kind not in CLASSIFICATIONS:
        raise SystemExit(f"--classify must be one of {CLASSIFICATIONS}")
    if not slugs:
        raise SystemExit("name the spec directories to classify (NNN-slug …)")
    out = []
    for slug in slugs:
        fdir = rc.repo / "specs" / slug
        sp = fdir / "spec.md"
        if not sp.is_file():
            raise SystemExit(f"specs/{slug}/spec.md does not exist")
        text = sp.read_text(encoding="utf-8")
        meta, _ = C.split_fm(text)
        if not C.is_imported(meta) and not (kind == "archived" and C.is_baseline(meta)):
            raise SystemExit(
                f"{slug} is not an imported document (origin '{C.origin(meta) or 'planned'}'); "
                "only imports are classified"
            )
        if kind == "baseline":
            text = _remove_fm_keys(text, {"adoption_state"})
            upd = {"origin": "baseline"}
            if not meta.get("observed_at"):
                upd["observed_at"] = today()
            text = C.set_fm(text, upd)
            nxt = "review the baseline with the user, then approve it"
        elif kind == "planned":
            text = _remove_fm_keys(text, {"origin", "adoption_state"})
            if "rfc" not in meta:
                text = C.set_fm(text, {"rfc": ""})
            nxt = "planned work: write or cite its RFC, then plan, tasks and evals"
        else:
            text = C.set_fm(text, {"origin": "imported", "adoption_state": "archived"})
            nxt = "archived reference; nothing to do"
        sp.write_text(text, encoding="utf-8")
        cap_set(rc, cap_slug_for(slug), next_action=nxt)
        out.append(f"{slug}: {kind}")
    write_index(rc)
    return out


# --- validation of a baseline (check + approval preflight) -----------------------------


def _section(text: str, name: str) -> str | None:
    m = re.search(
        rf"^## (?:\d+\.\s*)?{re.escape(name)}\b[^\n]*\n(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    return m.group(1) if m else None


def historical(meta: dict) -> set[str]:
    return set(C.list_of(meta, "historical_companions"))


def metadata_problems(fdir: Path, meta: dict) -> list[str]:
    """Front-matter facts that are wrong whatever the body says (GW027)."""
    bad = []
    o = C.origin(meta)
    if o and o not in C.ORIGINS:
        bad.append(f"origin must be one of {sorted(C.ORIGINS)} (now '{o}')")
    st = C.adoption_state(meta)
    if st and st not in C.ADOPTION_STATES:
        bad.append(
            f"adoption_state must be one of {sorted(C.ADOPTION_STATES)} (now '{st}')"
        )
    if st and o != "imported":
        bad.append("adoption_state is only for origin: imported")
    if o == "imported" and not st:
        bad.append("an imported document needs adoption_state: pending or archived")
    if (
        o == "baseline"
        and (fdir / "tasks.md").is_file()
        and "tasks.md" not in historical(meta)
    ):
        bad.append(
            "a baseline has no tasks: list tasks.md under historical_companions (an imported record) or remove it"
        )
    return bad


def content_problems(meta: dict, text: str) -> list[str]:
    """What a finished baseline body must carry to be a usable reference (GW029 errors)."""
    bad = []
    from groundwork_check import strip_comments

    for name in BASELINE_SECTIONS:
        sec = _section(text, name)
        if sec is None:
            bad.append(f"missing '## {name}' section")
        elif not strip_comments(sec).strip():
            bad.append(f"'## {name}' is empty")
    mt = _section(text, "Manual test")
    if mt is None or not strip_comments(mt).strip():
        bad.append(
            "no verification guidance: a non-empty 'Manual test' section is required"
        )
    return bad


def evidence_gaps(text: str) -> list[str]:
    """Requirement ids with no row in the Evidence table (GW029 warnings)."""
    ev = _section(text, "Evidence") or ""
    ids = re.findall(r"^- \*\*((?:N?FR|AC)-\d+)\*\*", text, re.MULTILINE)
    return [i for i in dict.fromkeys(ids) if not re.search(rf"\b{i}\b", ev)]


def citation_problems(text: str) -> list[str]:
    """Every AC must cite a requirement that exists (the same facts GW023 reports)."""
    known = set(re.findall(r"^- \*\*(N?FR-\d+)\*\*", text, re.MULTILINE))
    bad = []
    for m in re.finditer(r"^- \*\*(AC-\d+)\*\*(.*)$", text, re.MULTILINE):
        refs = set(re.findall(r"\b(N?FR-\d+)\b", m.group(2)))
        if not refs:
            bad.append(
                f"{m.group(1)} does not cite the requirement it proves (add '(covers FR-n)')"
            )
        for x in sorted(refs - known):
            bad.append(f"{m.group(1)} cites unknown {x}")
    return bad


def approval_problems(fdir: Path, meta: dict, text: str) -> list[str]:
    bad = metadata_problems(fdir, meta)
    if not str(meta.get("owner", "")).strip():
        bad.append("owner is empty (a confirmed human must own the baseline)")
    bad += content_problems(meta, text)
    if not re.search(r"^- \*\*FR-\d+\*\*", text, re.MULTILINE):
        bad.append("no numbered functional requirements (**FR-1**)")
    if not re.search(r"^- \*\*AC-\d+\*\*", text, re.MULTILINE):
        bad.append("no numbered acceptance criteria (**AC-1**)")
    bad += citation_problems(text)[:5]
    return bad


# --- creating a baseline ------------------------------------------------------------------


def new_baseline(
    rc: C.Ctx, slug: str, title: str | None, capability: str | None
) -> Path:
    specs = rc.repo / "specs"
    specs.mkdir(exist_ok=True)
    clean = C.slugify(slug)
    if not clean:
        raise SystemExit("give a slug (letters, digits, hyphens)")
    for p in specs.iterdir():
        if p.is_dir() and re.sub(r"^\d{3}-", "", p.name) == clean:
            raise SystemExit(
                f"specs/{p.name} already exists; extend or amend it instead"
            )
    n = C.next_number([p.name for p in specs.iterdir()], r"(\d+)-")
    name = f"{n:03d}-{clean}"
    fdir = specs / name
    fdir.mkdir()
    ttl = title or clean.replace("-", " ").title()
    (fdir / "spec.md").write_text(
        C.render(
            "baseline-spec.md",
            id=name,
            title=ttl,
            date=today(),
            author=C.signer(),
        ),
        encoding="utf-8",
    )
    cap = capability or clean
    cap_link(rc, cap, name, title=ttl, create=True)
    cap_set(
        rc,
        cap,
        next_action="investigate, interview, fill the baseline, then ask for approval",
    )
    write_index(rc)
    return fdir


# --- capability records -------------------------------------------------------------------


def caps_file(rc: C.Ctx) -> Path:
    return (rc.repo or rc.root) / CAPS_REL


def load_caps(rc: C.Ctx) -> dict:
    try:
        d = json.loads(caps_file(rc).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_caps(rc: C.Ctx, data: dict) -> None:
    f = caps_file(rc)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        json.dumps(dict(sorted(data.items())), indent=2) + "\n", encoding="utf-8"
    )


def _blank(title: str) -> dict:
    return {
        "title": title,
        "lifecycle": "uncertain",
        "lifecycle_confirmed": None,
        "suggested_lifecycle": "",
        "sources": [],
        "rationale_ref": "",
        "specs": [],
        "next_action": "",
        "interview_notes": [],
    }


def cap_set(rc: C.Ctx, cap: str, create: bool = True, **fields) -> dict:
    cap = C.slugify(cap)
    data = load_caps(rc)
    if cap not in data:
        if not create:
            raise SystemExit(
                f"no capability '{cap}' (groundwork.py capability set {cap} title=…)"
            )
        data[cap] = _blank(fields.get("title") or cap.replace("-", " ").title())
    rec = data[cap]
    for k, v in fields.items():
        if k not in CAP_FIELDS and k != "lifecycle_confirmed_by":
            raise SystemExit(
                f"unknown capability field '{k}' (one of {', '.join(CAP_FIELDS)})"
            )
        if k == "lifecycle":
            if v not in LIFECYCLES:
                raise SystemExit(f"lifecycle must be one of {LIFECYCLES}")
            rec["lifecycle"] = v
            rec["lifecycle_confirmed"] = {"by": C.signer(), "at": today()}
        elif k == "lifecycle_confirmed_by":
            rec["lifecycle_confirmed"] = {"by": v, "at": today()}
        elif k in LIST_FIELDS:
            items = (
                v
                if isinstance(v, list)
                else [x.strip() for x in str(v).split(",") if x.strip()]
            )
            rec[k] = list(dict.fromkeys(rec.get(k, []) + items))
        else:
            rec[k] = v
    save_caps(rc, data)
    return rec


def cap_link(
    rc: C.Ctx, cap: str, spec: str, title: str | None = None, create: bool = False
) -> dict:
    """Additive and idempotent: a slug already linked is not added twice; other links stay."""
    cap = C.slugify(cap)
    data = load_caps(rc)
    if cap not in data:
        if not create:
            raise SystemExit(
                f"no capability '{cap}'; create it with: groundwork.py capability set {cap} title=…"
            )
        data[cap] = _blank(title or cap.replace("-", " ").title())
    if spec not in data[cap]["specs"]:
        data[cap]["specs"].append(spec)
    save_caps(rc, data)
    return data[cap]


def cap_unlink(rc: C.Ctx, cap: str, spec: str) -> dict:
    cap = C.slugify(cap)
    data = load_caps(rc)
    if cap not in data:
        raise SystemExit(f"no capability '{cap}'")
    data[cap]["specs"] = [s for s in data[cap]["specs"] if s != spec]
    save_caps(rc, data)
    return data[cap]


# --- derived views ----------------------------------------------------------------------


def spec_state(rc: C.Ctx, slug: str) -> tuple[str, str]:
    """(kind, approval) for a linked spec: kind is baseline | pending | archived | planned | missing."""
    fdir = rc.repo / "specs" / slug
    if not (fdir / "spec.md").is_file():
        return "missing", "—"
    meta = C.spec_meta(fdir)
    st = C.doc_state(fdir / "spec.md", rc)
    if C.is_imported(meta):
        return (C.adoption_state(meta) or "pending"), "not approvable"
    if C.is_baseline(meta):
        return "baseline", st.status
    return "planned", st.status


def coverage(rc: C.Ctx, specs: list[str]) -> str:
    if not specs:
        return "deferred"
    kinds = [spec_state(rc, s) for s in specs]
    base_ok = sum(1 for k, a in kinds if k == "baseline" and a == "approved")
    if base_ok == len(kinds):
        return "baselined"
    counts: dict[str, int] = {}
    for k, a in kinds:
        label = (
            "baselined"
            if (k == "baseline" and a == "approved")
            else ("baseline unapproved" if k == "baseline" else k)
        )
        counts[label] = counts.get(label, 0) + 1
    if base_ok:
        return "partial (" + ", ".join(f"{n} {lab}" for lab, n in counts.items()) + ")"
    if any(k == "pending" for k, _ in kinds):
        return "import-review"
    return "uncovered (" + ", ".join(f"{n} {lab}" for lab, n in counts.items()) + ")"


def rows(rc: C.Ctx) -> list[dict]:
    out = []
    for cap, rec in sorted(load_caps(rc).items()):
        specs = rec.get("specs", [])
        out.append(
            {
                "cap": cap,
                "title": rec.get("title", cap),
                "lifecycle": rec.get("lifecycle", "uncertain")
                + ("" if rec.get("lifecycle_confirmed") else " (unconfirmed)"),
                "coverage": coverage(rc, specs),
                "specs": [f"{s} ({spec_state(rc, s)[0]})" for s in specs],
                "approval": ", ".join(spec_state(rc, s)[1] for s in specs) or "—",
                "review": "not tracked",
                "sources": rec.get("sources", []),
                "rationale": rec.get("rationale_ref", ""),
                "next": rec.get("next_action", ""),
            }
        )
    return out


def fingerprint(rs: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rs, sort_keys=True).encode()).hexdigest()[:12]


def _kept_notes(text: str) -> dict[str, str]:
    notes = {}
    for ln in text.splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 10 and cells[0].startswith("`"):
            notes[cells[0].strip("`")] = cells[9]
    return notes


def render_block(rc: C.Ctx, previous: str = "") -> str:
    rs = rows(rc)
    notes = _kept_notes(previous)
    out = [
        "<!-- groundwork:capabilities start -->",
        f"<!-- groundwork:capabilities facts={fingerprint(rs)} -->",
        "## Capabilities",
        "",
        (
            "Generated by `groundwork.py capabilities` from `.groundwork/capabilities.json` and the specs. "
            "Edit only the Notes column; it is kept when the table is regenerated. Deferred rows are "
            "capabilities nobody has documented yet; they are not covered."
        ),
        "",
        "| Capability | Lifecycle | Coverage | Specs | Approval | Review | Sources | Rationale | Next action | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in rs:
        out.append(
            "| "
            + " | ".join(
                [
                    f"`{r['cap']}`",
                    r["lifecycle"],
                    r["coverage"],
                    ", ".join(r["specs"]) or "—",
                    r["approval"],
                    r["review"],
                    ", ".join(f"`{s}`" for s in r["sources"][:4]) or "—",
                    r["rationale"] or "—",
                    r["next"] or "—",
                    notes.get(r["cap"], ""),
                ]
            )
            + " |"
        )
    if not rs:
        out.append("| — | — | — | — | — | — | — | — | — | |")
    out.append("<!-- groundwork:capabilities end -->")
    return "\n".join(out) + "\n"


def index_path(rc: C.Ctx) -> Path:
    return rc.repo / INDEX_REL


def write_index(rc: C.Ctx) -> Path:
    p = index_path(rc)
    prev = p.read_text(encoding="utf-8") if p.is_file() else ""
    block = render_block(rc, prev)
    if BLOCK.search(prev):
        new = BLOCK.sub(lambda _m: block, prev)
    elif prev:
        new = prev.rstrip("\n") + "\n\n" + block
    else:
        new = (
            "# Specs\n\nOne directory per feature: `NNN-slug/`. Planned features carry spec, plan, "
            "tasks and evals; baselines (existing behaviour) carry a spec only.\n\n"
            + block
        )
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(new, encoding="utf-8")
    return p


def index_state(rc: C.Ctx) -> tuple[str, str]:
    """(status, detail): none (nothing to index) | missing | outdated | current."""
    if not load_caps(rc):
        return "none", ""
    p = index_path(rc)
    if not p.is_file():
        return "missing", ""
    m = STAMP.search(p.read_text(encoding="utf-8"))
    if not m or m.group(1) != fingerprint(rows(rc)):
        return "outdated", "capabilities or spec states changed since it was generated"
    return "current", ""


def review_items(ctx: C.Ctx) -> list[tuple[str, str]]:
    """Documentation awaiting a person: (label, state). Never implementation work."""
    out = []
    prefix = ctx.level == "workspace"
    for rc in _repos(ctx):
        name = f"{rc.repo.name}/" if prefix else ""
        for fdir in C.feature_dirs(rc):
            meta = C.spec_meta(fdir)
            if C.is_imported(meta):
                st = C.adoption_state(meta) or "pending"
                if st == "pending":
                    out.append((name + fdir.name, "imported — awaiting classification"))
            elif C.is_baseline(meta):
                d = C.doc_state(fdir / "spec.md", rc)
                if d.placeholders:
                    out.append(
                        (
                            name + fdir.name,
                            f"baseline — {d.placeholders} unresolved marker(s)",
                        )
                    )
                elif d.status == "stale":
                    out.append(
                        (
                            name + fdir.name,
                            "baseline — edited after approval; re-approve",
                        )
                    )
                elif not d.approved:
                    out.append((name + fdir.name, "baseline — awaiting approval"))
        for cap, rec in sorted(load_caps(rc).items()):
            if not rec.get("specs") and rec.get("lifecycle") in ("active", "uncertain"):
                out.append((name + cap, "capability deferred — no spec yet"))
    return out


def review_summary(ctx: C.Ctx) -> str:
    items = review_items(ctx)
    if not items:
        return ""
    counts: dict[str, int] = {}
    for _, state in items:
        key = state.split(" — ")[0] + (
            " awaiting classification"
            if "classification" in state
            else " awaiting approval"
            if "awaiting approval" in state
            else " stale"
            if "re-approve" in state
            else " deferred"
            if "deferred" in state
            else " unfinished"
        )
        counts[key] = counts.get(key, 0) + 1
    return ", ".join(f"{n} {k}" for k, n in counts.items())


def review_lines(ctx: C.Ctx, limit: int = 6) -> list[str]:
    items = review_items(ctx)
    if not items:
        return []
    lines = [
        "DOCUMENTATION REVIEW (references, not work to build; baseline skill): "
        + review_summary(ctx)
    ]
    for label, state in items[:limit]:
        lines.append(f"  - {label} — {state}")
    if len(items) > limit:
        lines.append(f"  … {len(items) - limit} more (groundwork.py board --all)")
    return lines
