"""groundwork doctor — how far is this project from the standard, and what to do next.

Read-only. It reuses `check` (conformance), `fresh` (drift) and the hook/CI state, and turns them into
a stage on a ladder plus an ordered list of next steps.
"""
from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import groundwork_check as K
import groundwork_core as C
import groundwork_fresh as F
import groundwork_hooks as H

STAGES = ["Not started", "Scaffolded", "Documented", "Current", "Guarded", "Practicing"]
STAGE_HELP = {
    0: "required foundation documents are missing",
    1: "documents exist but still have unresolved markers",
    2: "documents are finished and conform to the standard",
    3: "documents are confirmed against reality and not stale",
    4: "the standard is enforced automatically (git hook or CI)",
    5: "the RFC → spec path is in use",
}
CI_FILES = [".gitlab-ci.yml", "Jenkinsfile", ".circleci/config.yml", "azure-pipelines.yml", "bitbucket-pipelines.yml"]


@dataclass
class Item:
    area: str
    status: str              # ok | warn | fail | info
    label: str
    detail: str = ""
    fix: str = ""


@dataclass
class Diagnosis:
    name: str
    level: str
    root: str
    items: list[Item] = field(default_factory=list)
    stage: int = 0
    children: list["Diagnosis"] = field(default_factory=list)

    @property
    def stage_name(self) -> str:
        return STAGES[self.stage]

    def next_steps(self, limit: int = 6) -> list[str]:
        steps, seen = [], set()
        for it in sorted(self.items, key=lambda i: {"fail": 0, "warn": 1}.get(i.status, 9)):
            if it.status in ("fail", "warn") and it.fix and it.fix not in seen:
                seen.add(it.fix)
                steps.append(f"{it.fix}   ({it.label})")
        for c in self.children:
            steps += [f"[{c.name}] {s}" for s in c.next_steps(3)]
        return steps[:limit]


def _ci_runs_groundwork(base: Path) -> str | None:
    cands = [*(base / ".github" / "workflows").glob("*")] if (base / ".github" / "workflows").is_dir() else []
    cands += [base / f for f in CI_FILES]
    for p in cands:
        try:
            if "groundwork" in p.read_text(encoding="utf-8").lower():
                return p.relative_to(base).as_posix()
        except OSError:
            pass
    return None


def diagnose_ctx(ctx: C.Ctx, ws_children: bool = True) -> Diagnosis:
    base = ctx.workspace if ctx.level == "workspace" else (ctx.repo or ctx.root)
    d = Diagnosis(base.name, ctx.level, str(base))
    add = lambda *a, **k: d.items.append(Item(*a, **k))   # noqa: E731

    if ctx.level == "unknown":
        add("Level", "fail", "Not a git repository or workspace", ctx.note,
            "groundwork.py init --as repo   (or: --as workspace)")
        return d
    add("Level", "info", ctx.level.upper(), f"root {base}" + (f"; workspace above: {ctx.workspace}" if ctx.level == "repo" else ""))

    # foundation
    missing, unfinished = C._gaps_at(ctx.level, base, "")
    spec = C.FOUNDATION[ctx.level]
    for name in spec["files"] + [x + "/" for x in spec["dirs"]]:
        if name in missing:
            add("Foundation", "fail", f"{name} missing", fix="groundwork.py init")
        elif name in unfinished:
            add("Foundation", "warn", f"{name} unfinished", "has [TODO]/[NEEDS CLARIFICATION] markers",
                "fill it in with the bootstrap skill (/groundwork:bootstrap)")
        else:
            add("Foundation", "ok", f"{name}")

    # conformance and freshness (reuse the checker)
    rep = K.Report(base)
    K.check_version(ctx, rep)
    K.check_foundation(ctx, rep)
    K.check_freshness(ctx, rep)
    if ctx.level == "workspace":
        K.check_rfcs(ctx, rep)
    else:
        if ctx.level == "standalone":
            K.check_rfcs(ctx, rep)
        K.check_features(ctx, rep)
    errs = [f for f in rep.items if f.severity == "error" and f.id not in ("GW001",)]
    for f in errs:
        add("Conformance", "fail", f"{f.id} {f.path}", f.message, f.hint or "groundwork.py check")
    if errs:
        pass
    elif missing or unfinished:
        add("Conformance", "info", "not judged until the documents are finished")
    else:
        add("Conformance", "ok", "documents conform to the standard")
    for f in rep.items:
        if f.id == "GW004":
            add("Standard", "warn", "no standard version recorded", fix="groundwork.py init")
        elif f.id in ("GW050", "GW051"):
            add("Freshness", "warn", f"{f.path}: " + ("never confirmed" if f.id == "GW051" else "may be stale"),
                f.message, "refresh skill (/groundwork:refresh) then: groundwork.py confirm")
    if not any(f.id in ("GW050", "GW051") for f in rep.items) and not unfinished and not missing:
        add("Freshness", "ok", "documents confirmed and current")

    # process
    features = [] if ctx.level == "workspace" else C.feature_dirs(ctx)
    rf = C.rfcs(ctx) if ctx.level != "unknown" else []
    approved = [r for r in rf if r.approved]
    if ctx.level in ("workspace", "standalone"):
        add("Process", "info", f"{len(rf)} RFC(s), {len(approved)} approved")
    for f in features:
        try:
            steps = C.feature_steps(ctx, f.name)
            first_bad = next((s for s in steps if not s.ok), None)
            done, total = C.task_counts(ctx, f.name)
            add("Process", "info", f"specs/{f.name}", (f"next: {first_bad.key} — {first_bad.detail}" if first_bad
                                                        else f"ready; tasks {done}/{total}"))
        except Exception:  # noqa: BLE001 — a malformed feature must not break the report
            add("Process", "warn", f"specs/{f.name}", "could not be read", "groundwork.py check")
    if not features and ctx.level != "workspace":
        add("Process", "info", "no features specced yet", fix="")

    # people & accountability
    import groundwork_people as PP  # noqa: PLC0415
    ppl = PP.people(ctx)
    if ctx.level != "repo" or ctx.workspace:
        if ppl:
            add("People", "ok", f"{len(ppl)} people listed with contacts in PROJECT.md")
        else:
            add("People", "warn", "no people listed under 'Who works on what' in PROJECT.md",
                "nobody can be contacted about anything", "fill PROJECT.md's people table (bootstrap skill)")
    owned = [i for i in (features if features else []) if (i / "spec.md").is_file()]
    unowned = [i.name for i in owned if not str(C.split_fm((i / "spec.md").read_text(encoding="utf-8"))[0].get("owner", "")).strip()]
    if unowned:
        add("People", "warn", f"{len(unowned)} feature(s) without an owner: {', '.join(unowned[:4])}",
            fix="groundwork.py record owner --ref <feature> --who <name>")
    elif owned:
        add("People", "ok", "every feature has an owner")

    # guardrails
    if ctx.level in ("repo", "standalone") or (ctx.level == "workspace" and (base / ".git").exists()):
        try:
            hs = H.status(base)
        except Exception:  # noqa: BLE001
            hs = "not installed"
        if "pre-commit" in hs:
            add("Guardrails", "ok", "git hook: " + hs)
        else:
            add("Guardrails", "warn", "no git hook", "commits are not checked automatically",
                "groundwork.py hooks install [--vendor]")
    ci = _ci_runs_groundwork(base)
    add("Guardrails", "ok" if ci else "info", "CI runs groundwork check" if ci else "no CI step runs groundwork check",
        ci or "add: python3 <engine>/groundwork.py check --strict",
        "" if ci else "")
    mode = ctx.enforcement
    add("Guardrails", "warn" if mode == "off" else "info", f"enforcement: {mode}",
        "the agent gate and hooks are disabled" if mode == "off" else "",
        "set enforcement to block in .groundwork/config.json" if mode == "off" else "")

    # environment
    if sys.version_info < (3, 10):
        add("Environment", "fail", f"Python {sys.version_info.major}.{sys.version_info.minor} < 3.10", fix="use Python 3.10+")
    if not shutil.which("git"):
        add("Environment", "fail", "git not found", fix="install git")

    d.stage = _stage(d, missing, unfinished, features, approved)
    if ctx.level == "workspace" and ws_children:
        for kid in C.child_repos(ctx.workspace):
            d.children.append(diagnose_ctx(C.detect(kid, ctx.workspace), ws_children=False))
    return d


def _stage(d: Diagnosis, missing, unfinished, features, approved) -> int:
    if missing:
        return 0
    if unfinished:
        return 1
    if any(i.area in ("Conformance", "Standard") and i.status in ("fail", "warn") for i in d.items):
        return 1
    if any(i.area == "Freshness" and i.status == "warn" for i in d.items):
        return 2
    guarded = any(i.area == "Guardrails" and i.status == "ok" for i in d.items)
    if not guarded:
        return 3
    if approved or features:
        return 5
    return 4


def overall_stage(d: Diagnosis) -> int:
    return min([d.stage, *(c.stage for c in d.children)])


def diagnose(path: Path) -> Diagnosis:
    return diagnose_ctx(C.detect(path))


ICON = {"ok": "✔", "warn": "!", "fail": "✘", "info": "·"}


def render(d: Diagnosis) -> str:
    out = [f"Groundwork doctor — {d.name} ({d.level})", ""]
    st = overall_stage(d)
    bar = "".join(("●" if i <= st else "○") for i in range(len(STAGES)))
    out.append(f"Stage {st}/{len(STAGES) - 1}: {STAGES[st]}  {bar}")
    out.append(f"  {STAGE_HELP[st]}" + (f" — next stage needs: {STAGE_HELP[st + 1]}" if st + 1 < len(STAGES) else ""))
    area = None
    for it in d.items:
        if it.area != area:
            area = it.area
            out += ["", area]
        out.append(f"  {ICON[it.status]} {it.label}" + (f" — {it.detail}" if it.detail else ""))
    for c in d.children:
        out += ["", f"Repo {c.name}: stage {c.stage} ({c.stage_name})"]
        for it in c.items:
            if it.status in ("fail", "warn"):
                out.append(f"  {ICON[it.status]} {it.label}" + (f" — {it.detail}" if it.detail else ""))
    steps = d.next_steps()
    if steps:
        out += ["", "Next steps"] + [f"  {i}. {s}" for i, s in enumerate(steps, 1)]
    else:
        out += ["", "Nothing to fix."]
    return "\n".join(out)


def to_json(d: Diagnosis) -> dict:
    return {"name": d.name, "level": d.level, "stage": overall_stage(d), "stage_name": STAGES[overall_stage(d)],
            "items": [vars(i) for i in d.items], "next_steps": d.next_steps(),
            "repos": [to_json(c) for c in d.children]}
