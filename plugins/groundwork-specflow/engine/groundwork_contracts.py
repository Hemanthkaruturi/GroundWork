"""Contracts with named reviewers (STANDARD.md §4, §5j).

A contract lives in the workspace's `CONTRACTS/` (the repo's own when standalone). GroundWork-created
contracts carry front matter: provider, consumers, semver version, `signoffs_required` (counted by the
ordinary approval machinery) and the humans expected to review it: `provider_reviewer` and
`consumer_reviewers`. The engine counts distinct signers and knows nothing about roles, so it only
*warns* when a named reviewer has not signed; whether both sides really reviewed is a human procedure.
An as-built contract (`origin: baseline`) describes a surface as observed, with an Evidence section.
Contracts without front matter (written by hand before GroundWork) are left alone.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import groundwork_core as C
import groundwork_people as PP

FIELDS = [
    "id",
    "title",
    "provider",
    "consumers",
    "version",
    "status",
    "signoffs_required",
]
SECTIONS = [
    "Provider and consumers",
    "Version and changelog",
    "Operations",
    "Errors and failure semantics",
    "Auth and tenancy",
    "Compatibility rules",
]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def home(ctx: C.Ctx) -> Path:
    return ctx.rfc_home / "CONTRACTS"


def paths(ctx: C.Ctx) -> list[Path]:
    d = home(ctx)
    return sorted(p for p in d.glob("*.md") if p.is_file()) if d.is_dir() else []


def governed(path: Path) -> dict | None:
    """Front matter of a GroundWork contract (any of its fields present, even blank), or None for a
    hand-written one. A blanked id does not make a contract disappear from validation."""
    meta, _ = C.split_fm(path.read_text(encoding="utf-8"))
    return meta if meta and any(f in meta for f in FIELDS) else None


def new_contract(
    ctx: C.Ctx,
    slug: str,
    title: str | None,
    provider: str | None,
    consumers: list[str],
    as_built: bool,
) -> Path:
    if ctx.level == "unknown":
        raise SystemExit("Not in a repo or workspace.")
    if ctx.level == "repo":
        # contracts are product-level: they belong to the workspace above
        pass
    d = home(ctx)
    clean = C.slugify(slug)
    if not clean:
        raise SystemExit("give a slug such as <provider>-<topic>")
    p = d / f"{clean}.md"
    import groundwork_baseline as BL

    for target in (d, p):  # every component, including a linked CONTRACTS/ itself
        problem = BL.path_problem_under(ctx.rfc_home, target)
        if problem:
            raise SystemExit(problem)
    if p.exists() or p.is_symlink():
        raise SystemExit(
            f"{p} already exists; add a version to it instead of a second file"
        )
    d.mkdir(parents=True, exist_ok=True)
    p.write_text(
        C.render(
            "CONTRACT.md",
            id=clean,
            title=title or clean.replace("-", " ").title(),
            provider=provider or (ctx.repo.name if ctx.repo else "[TODO: provider]"),
            consumers=", ".join(consumers),
            origin="baseline" if as_built else "planned",
            date=time.strftime("%F"),
            author=C.signer(),
        ),
        encoding="utf-8",
    )
    if not as_built:
        # a planned contract has no origin; it descends from an api RFC
        import groundwork_baseline as BL

        p.write_text(
            BL._remove_fm_keys(
                p.read_text(encoding="utf-8"),
                {"origin", "observed_at", "source_revision"},
            ),
            encoding="utf-8",
        )
    return p


def named_reviewers(meta: dict) -> list[str]:
    out = []
    pr = str(meta.get("provider_reviewer", "") or "").strip()
    if pr:
        out.append(pr)
    out += [c for c in C.list_of(meta, "consumer_reviewers") if c]
    return out


def _same(ppl: list, a: str, b: str) -> bool:
    if a.strip().lower() == b.strip().lower():
        return True
    pa, pb = PP.resolve(ppl, a), PP.resolve(ppl, b)
    return pa is not None and pa is pb


def assignment_gaps(meta: dict) -> list[str]:
    """Reviewer roles nobody is named for. Both sides must be named before sign-offs can mean anything."""
    gaps = []
    if not str(meta.get("provider_reviewer", "") or "").strip():
        gaps.append("provider_reviewer")
    if not [c for c in C.list_of(meta, "consumer_reviewers") if c]:
        gaps.append("consumer_reviewers")
    return gaps


def reviewer_gaps(ctx: C.Ctx, path: Path, meta: dict) -> tuple[list[str], str]:
    """(named reviewers who have not signed, why) for a contract with sign-offs recorded."""
    st = C.doc_state(path, ctx)
    named = named_reviewers(meta)
    if not named:
        return (
            [],
            "no provider_reviewer / consumer_reviewers named; sign-offs cannot show that both sides reviewed",
        )
    if not st.signers:
        return named, "no sign-off yet"
    ppl = PP.people(ctx)
    unsigned = [n for n in named if not any(_same(ppl, n, s) for s in st.signers)]
    return unsigned, (
        "signed by " + ", ".join(sorted(set(st.signers)))
    ) if unsigned else ""


def metadata_problems(path: Path, meta: dict) -> list[str]:
    bad = [f"front matter missing: {f}" for f in FIELDS if f not in meta]
    bad += [
        f"front matter blank: {f}"
        for f in ("id", "title", "provider", "version")
        if f in meta and not str(meta.get(f) or "").strip()
    ]
    if meta.get("id") and meta["id"] != path.stem:
        bad.append(f"id '{meta['id']}' does not match the file name")
    v = str(meta.get("version", "") or "")
    if v and not SEMVER.match(v):
        bad.append(
            f"version '{v}' is not semver (the date goes in observed_at, never in the version)"
        )
    o = C.origin(meta)
    if o and o != "baseline":
        bad.append(
            f"origin '{o}' is not valid for a contract (as-built contracts use 'baseline')"
        )
    sr = str(meta.get("signoffs_required", "2") or "2").strip()
    if not sr.isdigit() or int(sr) < 2:
        bad.append(
            f"signoffs_required must be a whole number of at least 2 (now '{sr}')"
        )
    return bad


def review_items(ctx: C.Ctx) -> list[tuple[str, str]]:
    """Contracts that still wait for a named human: (label, state)."""
    out = []
    for p in paths(ctx):
        meta = governed(p)
        if not meta:
            continue
        st = C.doc_state(p, ctx)
        if st.placeholders:
            continue  # unfinished: the author's, not a reviewer's
        label = "CONTRACTS/" + p.name
        if st.status == "stale":
            out.append((label, "contract — edited after sign-off; re-approve"))
            continue
        gaps = assignment_gaps(meta)
        if gaps:
            # nobody named for a side: pending whatever the count says
            out.append(
                (
                    label,
                    f"contract — reviewers incomplete: no {' / '.join(gaps)} named"
                    + f" ({C.signoffs_label(st)} sign-offs)",
                )
            )
            continue
        unsigned, _why = reviewer_gaps(ctx, p, meta)
        if not st.approved:
            out.append(
                (
                    label,
                    f"contract — awaiting sign-off ({C.signoffs_label(st)})"
                    + (
                        f"; not yet signed by {', '.join(unsigned)}"
                        if unsigned and st.signers
                        else ""
                    ),
                )
            )
        elif unsigned:
            out.append(
                (
                    label,
                    f"contract — approved by count, but not by named reviewer(s) {', '.join(unsigned)}",
                )
            )
    return out
