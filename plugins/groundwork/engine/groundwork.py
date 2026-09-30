#!/usr/bin/env python3
"""groundwork — command line and hook entry point for the groundwork plugin.

Hooks:      groundwork.py session-context | prompt-reminder | gate | gate-bash     (JSON on stdin)
Onboarding:  groundwork.py init [--as repo|workspace] [--retrofit] [--dry-run] | doctor [--json]
Anyone/CI:  groundwork.py check [--strict] [--json] | fresh [--json] | hooks install|uninstall|status
Agents:     groundwork.py confirm [doc ...]   (after updating docs to match reality)
Humans:     groundwork.py status | approve <doc> | bypass <reason>
People:     groundwork.py who <feature|RFC|bug> | who --person NAME | who --all | record <event> --ref R ...
Resume:     groundwork.py board [--all] [--json] | note <text> | deps <feature|RFC> | new-bug <slug> | activate-bug <slug>
Agents:     groundwork.py scaffold | new-rfc <slug> | new-feature <slug> --rfc N | activate <slug>
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import groundwork_board as W  # noqa: E402
import groundwork_brevity as V  # noqa: E402
import groundwork_bugs as B  # noqa: E402
import groundwork_check as K  # noqa: E402
import groundwork_core as C  # noqa: E402
import groundwork_discover as D  # noqa: E402
import groundwork_doctor as X  # noqa: E402
import groundwork_fresh as F  # noqa: E402
import groundwork_hooks as H  # noqa: E402
import groundwork_people as P  # noqa: E402
import groundwork_relations as R  # noqa: E402

TRIAGE = ("Before changing any file, triage the request: a defect -> fix-bug skill; new or changed behaviour OR LOOK "
          "(UI redesign, restyle, copy) -> interview -> RFC -> approval -> spec -> plan -> tasks -> evals; continuing earlier work -> "
          "resume skill. Other skills/plugins (frontend-design, etc.) are craft tools used INSIDE the implement step after the "
          "spec is approved - they never replace or skip this path, and the shell is gated like the Write tool.")

BREVITY = ("Write for a busy reader: answer or decision first, then at most a few short bullets. Short sentences, everyday words, "
           "no jargon or bare IDs (say what FR-6 or GW026 MEANS). About 150 words unless asked for more. Never re-tell the steps you took. "
           "Ask with the picker; give your recommendation and what each option leads to. Long content goes in a file - summarise it in 5 lines. "
           "SHORT MUST NOT MEAN LESS TRUE: always keep the decision needed, anything that failed or was skipped, what you did NOT verify, "
           "risks and side effects, every file/setting changed, assumptions, blockers and the user's next step.")

RULES = """\
groundwork is active. These rules are enforced by hooks, not suggestions:
0. COMMUNICATION (applies to every reply): BREVITY_TEXT
1. Know your level. WORKSPACE = the folder above the repos (PROJECT.md, ARCHITECTURE.md, CONSTITUTION.md, CONTRACTS/, DECISIONS/). REPO = where application code lives (ARCHITECTURE.md, AGENTS.md, specs/). A repo with no workspace above it is STANDALONE and carries both sets.
2. Foundation first: no PROJECT.md / ARCHITECTURE.md => write them (bootstrap skill) before any other work. Never invent business facts — ask the user.
3. To build something: interview the user (interview skill) until nothing is ambiguous -> RFC -> HUMAN approval -> spec -> plan -> tasks -> evals -> implement. Never skip forward.
4. You cannot approve documents. Only the user can, with /groundwork:approve <file>. Editing an approved document makes the approval stale.
5. Unknowns become [NEEDS CLARIFICATION: ...] in the document. Never guess. Unresolved markers block approval.
6. Change behaviour => change the spec in the same change. Bug => find the spec it violates.
7. Document shape is fixed by STANDARD.md; `groundwork.py check` verifies it. Run it after writing documents and fix every error.
8. ASK ONLY WITH THE `AskUserQuestion` TOOL: options the user selects, up to 4 questions per round, your recommendation first. If the tool is not loaded, load it with ToolSearch `select:AskUserQuestion`. Never put questions in reply text or end a reply with a list of questions; ask, write down the answer, ask the next round.
9. Foundation docs must keep matching reality. When you change what they describe (stack, commands, components, repos, contracts), update them IN THE SAME CHANGE and run `groundwork.py confirm <doc>`. If the context says DOCS MAY BE STALE, use the refresh skill before finishing.
10. Python: ALWAYS use `uv`, never pip/pip3/`python -m pip`/virtualenv/poetry commands. Install with `uv add <pkg>` (`uv add --dev` for dev tools), sync with `uv sync`, run with `uv run <cmd>`, create envs implicitly via uv (never `python -m venv`); commit `uv.lock`; never edit `uv.lock` by hand. Use `uv pip` only for a legacy `requirements.txt` project you were not asked to migrate. If the project uses another Python manager, ask before migrating; do not switch silently.
11. RESUME: state is in files. If the context lists IN FLIGHT work, use the resume skill; record where you stop with `groundwork.py note`. During an interview write the RFC draft after the first round and record every answer in §3 as you go.
12. BUGS: a defect is a violated requirement — use the fix-bug skill (reproduce, root cause, classify code-bug/spec-gap/design-flaw, cite the violated FR/AC across specs, regression test first). Never patch behaviour without it.
13. RELATIONS: every feature is independent or declares extends/amends/depends_on/builds_against; check `groundwork.py deps` before changing behaviour others rely on; an amended spec needs a dated `## Changes` entry and re-approval.
14. OTHER SKILLS DO NOT EXEMPT YOU. Design, frontend, testing and similar skills/plugins are craft tools for the implement step. A request like 'make the UI modern' is a change request: interview (look and feel, references, accessibility, scope) -> RFC -> spec with testable visual requirements -> plan -> tasks -> evals -> only then use the design skill to build what the spec says. Writing files through the shell (cat > f <<EOF, sed -i, tee, cp, inline scripts) is gated exactly like the Write tool.
15. OWNERSHIP: every RFC, feature and bug has a human requester, owner, implementer(s), deployer and support contact — recorded in front matter and the ledger. Ask who requested new work (interview), record `implemented` when you finish (`groundwork.py record implemented --ref <feature> --via claude-code`), and use `groundwork.py who <ref>` to find whom to contact about any feature (including those yours depends on or affects). Responsible persons are HUMANS (the git identity), never the agent.
16. UPSTREAM CHANGES: a plan/tasks/code never edits the spec silently. Found a spec problem? State the evidence, ask which reading is right (picker), amend the spec with a dated `## Changes` line (what and why), have the human re-approve, re-verify downstream, run `groundwork.py plan-sync`. Unresolved doubts are [NEEDS CLARIFICATION] markers, never chat footnotes.
17. Always tell the user how to test what you built by hand, and write it into the spec's manual-test section.
Use `python3 ${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py status` (or `board`) any time you are unsure where you are."""
RULES = RULES.replace("BREVITY_TEXT", BREVITY)


def out(obj: dict) -> None:
    print(json.dumps(obj))


def hook_input() -> dict:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return {}
    log = os.environ.get("GROUNDWORK_HOOK_LOG")        # opt-in diagnostics: what did the harness actually send?
    if log:
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"argv": sys.argv[1:], "input": data}) + "\n")
    return data


def describe(ctx: C.Ctx) -> str:
    lines = [f"Level: {ctx.level.upper()}" + (f" — {ctx.note}" if ctx.note else "")]
    if ctx.workspace:
        lines.append(f"Workspace root: {ctx.workspace}")
    if ctx.repo:
        lines.append(f"Repo root: {ctx.repo}")
    if ctx.level == "workspace":
        kids = C.child_repos(ctx.workspace)
        lines.append("Repos here: " + (", ".join(k.name for k in kids) or "(none yet)"))
    if ctx.level == "repo":
        lines.append("You are in a repo inside a workspace: read the workspace's PROJECT.md, "
                     "ARCHITECTURE.md, CONSTITUTION.md and CONTRACTS/ for the whole product.")
    missing, unfinished = C.foundation_gaps(ctx)
    if missing:
        lines.append("MISSING: " + ", ".join(missing))
    if unfinished:
        lines.append("UNFINISHED (unresolved [TODO]/[NEEDS CLARIFICATION] markers): " + ", ".join(unfinished))
    rf = C.rfcs(ctx) if ctx.level != "unknown" else []
    if rf:
        lines.append("RFCs: " + "; ".join(f"{r.path.stem} [{r.status}]" for r in rf))
    slug = C.active_slug(ctx)
    if slug:
        lines.append(f"Active feature: specs/{slug}")
    if ctx.level != "unknown":
        lines.append("You are working on behalf of: " + P.whoami(ctx) + " — record their name, never the agent's, as the responsible person.")
    flight = W.collect(ctx) if ctx.level != "unknown" else []
    if flight:
        lines.append("IN FLIGHT (resume with the resume skill; full list: groundwork.py board):")
        for w in flight[:5]:
            lines.append(f"  - [{w.kind}] {w.label} — {w.state} ({w.age()})" + (" ← active" if w.active else "")
                         + (f"; blocked by {'; '.join(w.blocked_by)}" if w.blocked_by else "")
                         + (f"; last note: {w.note}" if w.note else ""))
    stale = F.stale_lines(ctx) if ctx.level != "unknown" else []
    if stale:
        lines.append("DOCS MAY BE STALE (use the refresh skill): " + " | ".join(stale))
    phase, ins = C.next_step(ctx)
    lines.append(f"PHASE: {phase}\nNEXT: {ins}")
    lines.append(f"Enforcement: {ctx.enforcement}")
    return "\n".join(lines)


def cmd_session_context(_a) -> None:
    inp = hook_input()
    ctx = C.detect(inp.get("cwd") or Path.cwd())
    out({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                "additionalContext": RULES + "\n\n" + describe(ctx)}})


HUMAN_CMD = re.compile(r"^\s*/(?:groundwork:)?(approve|bypass)\b\s*(.*)$", re.S)


def run_human_action(name: str, argstr: str, cwd: str) -> str:
    """Approve/bypass, run from the UserPromptSubmit hook so only a typed prompt can trigger them."""
    os.chdir(cwd)
    try:
        args = shlex.split(argstr)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            if name == "approve":
                if not args:
                    raise SystemExit("Usage: /groundwork:approve <path to document | RFC-NNNN>")
                who = None
                if "--as" in args:
                    i = args.index("--as"); who = args[i + 1]; del args[i:i + 2]
                cmd_approve(argparse.Namespace(doc=args[0], who=who))
            else:
                cmd_bypass(argparse.Namespace(reason=" ".join(args), minutes=60))
        return buf.getvalue().strip()
    except SystemExit as e:
        return f"REFUSED: {e}" if str(e) else "REFUSED"
    except Exception as e:  # noqa: BLE001 — report anything to the human rather than crash the hook
        return f"ERROR: {e}"


def cmd_prompt_reminder(_a) -> None:
    inp = hook_input()
    m = HUMAN_CMD.match(inp.get("prompt", ""))
    if m:
        res = run_human_action(m.group(1), m.group(2), inp.get("cwd") or os.getcwd())
        out({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext":
             f"[groundwork {m.group(1)}] The user's command was already executed by the hook. "
             f"Result: {res}\nReport this result to the user in one or two lines. Run nothing yourself."}})
        return
    ctx = C.detect(inp.get("cwd") or Path.cwd())
    phase, ins = C.next_step(ctx)
    stale = F.stale_lines(ctx) if ctx.level != "unknown" else []
    note = (" Foundation docs may be stale (" + "; ".join(stale)[:300] + ") — before finishing, run the refresh skill.") if stale else ""
    out({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                "additionalContext": f"[groundwork] level={ctx.level} phase={phase}. {ins}{note} {TRIAGE} {BREVITY}"}})


def deny(reason: str) -> None:
    out({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                "permissionDecisionReason": reason}})


def cmd_gate(_a) -> None:
    full = hook_input()
    inp = full.get("tool_input", {})
    raw = inp.get("file_path") or inp.get("notebook_path")
    if not raw:
        return
    path = Path(raw)
    if C.is_protected_path(path):
        return deny("groundwork: approval records are written only by the user's /groundwork:approve command.")
    ok, reason = C.gate_code_edit(path, full.get("cwd"))
    if not ok:
        deny(reason)


def cmd_stop_brevity(_a) -> None:
    """Optional (`"brevity": "enforce"`): send an over-long reply back to be rewritten, once."""
    full = hook_input()
    if full.get("stop_hook_active"):
        return
    ctx = C.detect(full.get("cwd") or Path.cwd())
    mode = os.environ.get("GROUNDWORK_BREVITY") or ctx.config.get("brevity", "guide")
    if mode != "enforce":
        return
    limit = int(ctx.config.get("max_reply_words", V.DEFAULT_REPLY_WORDS))
    tp = full.get("transcript_path")
    # The harness hands over the final message itself; the transcript may not have it written yet, so it is only a fallback.
    text = full.get("last_assistant_message") or (V.last_reply_text(Path(tp)) if tp else "")
    n = V.reply_words(text)
    if n > limit:
        saved = V.save_full_reply(ctx.repo or ctx.workspace or ctx.root, text)
        out({"decision": "block", "reason": V.SHORTEN.format(n=n, limit=limit, saved=saved)})


def cmd_skill_notice(_a) -> None:
    """When any non-groundwork skill loads, remind the agent it is a craft tool inside the process."""
    full = hook_input()
    name = str(full.get("tool_input", {}).get("skill", ""))
    if not name or name.startswith("groundwork:"):
        return
    ctx = C.detect(full.get("cwd") or Path.cwd())
    if ctx.level == "unknown":
        return
    phase, ins = C.next_step(ctx)
    out({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext":
         f"[groundwork] You are loading '{name}', which is not a groundwork skill: treat it as a craft tool for the IMPLEMENT step only. "
         f"Current phase: {phase}. Unless the phase is 'implement' (approved RFC/spec, finished plan, tasks and evals), do NOT start building with it: "
         f"triage the request first (defect -> fix-bug; new/changed behaviour or look -> interview -> RFC -> spec; continuing -> resume). "
         f"Design choices it suggests belong in the spec as testable requirements before any file is written. Writing files by shell is gated like the Write tool."}})


def cmd_gate_bash(_a) -> None:
    full = hook_input()
    cmd = full.get("tool_input", {}).get("command", "")
    if C.is_protected_command(cmd):
        return deny("groundwork: approvals and bypasses are human acts. Ask the user to run "
                    "/groundwork:approve or /groundwork:bypass themselves.")
    ok, reason = C.gate_shell_command(cmd, Path(full.get("cwd") or os.getcwd()))
    if not ok:
        deny(reason)


def cmd_status(a) -> None:
    ctx = C.detect(Path(a.path or Path.cwd()))
    print(describe(ctx))
    slug = C.active_slug(ctx)
    if slug and (ctx.repo / "specs" / slug).is_dir():
        print("\nPipeline for specs/%s:" % slug)
        for st in C.feature_steps(ctx, slug):
            print(f"  [{'x' if st.ok else ' '}] {st.key:<6} {st.detail}")
        d, t = C.task_counts(ctx, slug)
        print(f"  tasks: {d}/{t} done")


def cmd_approve(a) -> None:
    p = Path(a.doc).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    if not p.is_file() and a.doc.upper().startswith("RFC"):
        ctx0 = C.detect(Path.cwd())
        p = C.find_rfc(ctx0, a.doc) or p
    ctx = C.detect(p)
    st = C.approve(p, ctx, a.who)
    print(f"{p.name}: {st.status} ({len(set(st.signers))}/{st.needed} sign-offs: {', '.join(st.signers)})")
    if st.status == "in-review":
        print("More sign-offs are required; each signer runs /groundwork:approve.")


def cmd_bypass(a) -> None:
    ctx = C.detect(Path.cwd())
    root = ctx.repo or ctx.root
    if not a.reason.strip():
        raise SystemExit("A bypass needs a reason: /groundwork:bypass <why>")
    f = root / ".groundwork" / "bypass.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    until = time.time() + a.minutes * 60
    f.write_text(json.dumps({"reason": a.reason, "by": C.signer(), "until": until}) + "\n", encoding="utf-8")
    with (root / ".groundwork" / "bypass.log").open("a", encoding="utf-8") as log:
        log.write(f"{time.strftime('%F %T')} {C.signer()} {a.minutes}min: {a.reason}\n")
    print(f"Gate bypassed for {a.minutes} minutes in {root}. Logged to .groundwork/bypass.log.")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GITIGNORE = "active\nbypass.json\nbypass.log\ndiscovery.json\n"


def scaffold_at(ctx: C.Ctx, dry: bool = False) -> list[str]:
    """Create whatever foundation is missing for ``ctx``'s level. Returns what was (or would be) created."""
    base = ctx.workspace if ctx.level == "workspace" else ctx.repo
    spec = C.FOUNDATION[ctx.level]
    made = []
    for f in spec["files"]:
        if C._find_ci(base, f) is None:
            made.append(f)
            if not dry:
                tpl = {"AGENTS.md": "AGENTS.repo.md" if ctx.level == "repo" else "AGENTS.workspace.md"}.get(f, f)
                _write(base / f, C.render(tpl, name=base.name, date=time.strftime("%F"),
                                          workspace=str(ctx.workspace or "")))
    for d in spec["dirs"]:
        if not (base / d).is_dir():
            made.append(d + "/")
            if not dry:
                (base / d).mkdir(parents=True)
                if d == "DECISIONS":
                    _write(base / d / "README.md", C.render("DECISIONS-index.md", name=base.name))
                else:
                    (base / d / ".gitkeep").touch()
    if not dry:
        gi = base / ".groundwork" / ".gitignore"
        if not gi.exists():
            _write(gi, GITIGNORE)
        elif "discovery.json" not in gi.read_text(encoding="utf-8"):
            gi.write_text(gi.read_text(encoding="utf-8").rstrip("\n") + "\ndiscovery.json\n", encoding="utf-8")
        if "standard" not in C.read_config(base):
            C.write_config(base, standard=C.STANDARD_VERSION)
    return made


def cmd_scaffold(_a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level == "unknown":
        raise SystemExit("Not in a repo or workspace. `git init` first, or mark a workspace with "
                         "`groundwork.py mark-workspace`.")
    made = scaffold_at(ctx)
    print("Created: " + (", ".join(made) or "nothing (all present)") +
          "\nEvery new file contains [TODO] markers. Fill them with the user (bootstrap skill).")


def retrofit_at(ctx: C.Ctx, dry: bool = False) -> list[str]:
    """Additively append any required-but-missing sections to existing foundation docs. Never rewrites."""
    base = ctx.workspace if ctx.level == "workspace" else ctx.repo
    done = []
    for f in C.FOUNDATION[ctx.level]["files"]:
        key = f.upper().removesuffix(".MD") + ".md"
        p = C._find_ci(base, f)
        if p is None or key not in K.FOUNDATION_SECTIONS:
            continue
        text = p.read_text(encoding="utf-8")
        missing = K.missing_sections(text, K.FOUNDATION_SECTIONS[key], numbered=False)
        if not missing:
            continue
        tpl = [m.group(1).strip() for m in __import__("re").finditer(r"^## (.+)$", (C.TEMPLATES / key).read_text(encoding="utf-8"), __import__("re").M)]
        add = ""
        for name in missing:
            full = next((h for h in tpl if K._norm(h).startswith(K._norm(name))), name)
            add += f"\n## {full}\n[TODO: this required section was added by `groundwork.py init --retrofit`; fill it in]\n"
        done.append(f"{p.name}: +{', '.join(missing)}")
        if not dry:
            p.write_text(text.rstrip("\n") + "\n" + add, encoding="utf-8")
    return done


def cmd_init(a) -> None:
    cwd = Path.cwd()
    ctx = C.detect(cwd)
    if ctx.level == "unknown":
        if a.as_ == "repo":
            if not a.dry_run:
                subprocess.run(["git", "init", "-q"], cwd=cwd, check=True)
            print("git init (this directory is now a repo)" if not a.dry_run else "would: git init")
        elif a.as_ == "workspace":
            if not a.dry_run:
                C.write_config(cwd, level="workspace", standard=C.STANDARD_VERSION)
            print("marked as a workspace" if not a.dry_run else "would: mark this directory as a workspace")
        else:
            raise SystemExit("This directory is neither a git repository nor a workspace.\n"
                             "  groundwork.py init --as repo        # git init here\n"
                             "  groundwork.py init --as workspace   # it will hold several repos (clone/create them inside)")
        ctx = C.detect(cwd) if not a.dry_run else C.Ctx("repo" if a.as_ == "repo" else "workspace", cwd,
                                                          repo=cwd if a.as_ == "repo" else None,
                                                          workspace=cwd if a.as_ == "workspace" else None)
    targets = [ctx]
    if ctx.level == "workspace":
        targets += [C.detect(k, ctx.workspace) for k in C.child_repos(ctx.workspace)]
    verb = "would create" if a.dry_run else "created"
    for t in targets:
        base = t.workspace if t.level == "workspace" else t.repo
        d = D.discover(base) if t.level != "workspace" else None   # BEFORE scaffolding: only pre-existing things count
        made = scaffold_at(t, a.dry_run)
        print(f"\n[{base.name}] {t.level}: {verb} " + (", ".join(made) or "nothing (foundation already present)"))
        if a.retrofit:
            r = retrofit_at(t, a.dry_run)
            print(f"[{base.name}] retrofit: " + ("; ".join(r) if r else "existing documents already have every required section"))
        if t.level != "workspace":
            if not a.dry_run:
                _write(base / ".groundwork" / "discovery.json", json.dumps(d, indent=2) + "\n")
            print(f"[{base.name}] evidence gathered{'' if a.dry_run else ' → .groundwork/discovery.json'}:")
            print(D.summarize(d))
        if t.level == "repo" and t.workspace:
            gaps = C._gaps_at("workspace", t.workspace, "")[0]
            if gaps:
                print(f"[{base.name}] note: the workspace above lacks {', '.join(gaps)} — run init there too")
    print("\nNext:")
    print("  1. Start Claude Code with the plugin and run /groundwork:bootstrap — it drafts the documents from the evidence above")
    print("     and asks you only what code cannot tell (purpose, people, decisions).")
    print("  2. groundwork.py doctor      # see how far the project is from the standard")
    if not a.dry_run:
        print()
        print(X.render(X.diagnose(cwd)))


def cmd_doctor(a) -> None:
    d = X.diagnose(Path(a.path or Path.cwd()))
    print(json.dumps(X.to_json(d), indent=2) if a.json else X.render(d))


def cmd_mark_workspace(_a) -> None:
    root = Path.cwd()
    C.write_config(root, level="workspace", standard=C.read_config(root).get("standard", C.STANDARD_VERSION))
    print(f"{root} is now a workspace.")


def cmd_new_rfc(a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level == "unknown":
        raise SystemExit("Not in a repo or workspace.")
    d = ctx.rfc_home / "DECISIONS"
    d.mkdir(exist_ok=True)
    n = C.next_number([p.name for p in d.glob("RFC-*.md")], r"RFC-0*(\d+)")
    slug = C.slugify(a.slug)
    p = d / f"RFC-{n:04d}-{slug}.md"
    _write(p, C.render("RFC.md", id=f"RFC-{n:04d}", title=a.title or slug.replace("-", " ").title(),
                       date=time.strftime("%F"), author=C.signer()))
    P.auto_created(ctx, "rfc", p, a.requested_by)
    print(p)


def cmd_new_feature(a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level not in ("repo", "standalone"):
        raise SystemExit("Features are specced inside a repo. cd into one.")
    rfc = C.find_rfc(ctx, a.rfc)
    if not rfc:
        raise SystemExit(f"RFC '{a.rfc}' not found in {ctx.rfc_home / 'DECISIONS'}")
    specs = ctx.repo / "specs"
    specs.mkdir(exist_ok=True)
    n = C.next_number([p.name for p in specs.iterdir()], r"(\d+)-")
    slug = f"{n:03d}-{C.slugify(a.slug)}"
    fdir = specs / slug
    fdir.mkdir()
    v = dict(id=slug, rfc=rfc.stem.split("-")[0] + "-" + rfc.stem.split("-")[1],
             title=a.slug.replace("-", " ").title(), date=time.strftime("%F"), author=C.signer())
    for name in ("spec", "plan", "tasks", "evals"):
        _write(fdir / f"{name}.md", C.render(f"{name}.md", **v))
    rel = {k: "[" + ", ".join(x.strip() for x in (getattr(a, k) or "").split(",") if x.strip()) + "]"
           for k in ("extends", "depends_on", "builds_against", "amends")}
    if any(val != "[]" for val in rel.values()):
        sp = fdir / "spec.md"
        sp.write_text(C.set_fm(sp.read_text(encoding="utf-8"), rel), encoding="utf-8")
    rmeta, _ = C.split_fm(rfc.read_text(encoding="utf-8"))
    P.auto_created(ctx, "feature", fdir / "spec.md", getattr(a, "requested_by", None) or rmeta.get("requested_by") or None)
    _write(ctx.repo / ".groundwork" / "active", slug + "\n")
    print(f"{fdir}\nActive feature set to {slug}. Owner: {C.signer()}.")


def cmd_check(a) -> None:
    path = Path(a.path or Path.cwd())
    if a.hook:                      # called from a git hook: honour the enforcement setting
        mode = C.detect(path).enforcement
        if mode == "off":
            return
    r = K.run(path)
    if a.hook and not r.items:
        return
    print(K.render_json(r) if a.json else K.render_text(r, a.strict))
    if a.hook and mode == "warn":
        return
    if r.errors or (a.strict and r.items):
        sys.exit(1)


def cmd_hooks(a) -> None:
    ctx = C.detect(Path.cwd())
    repos = H.target_repos(ctx)
    if not repos:
        raise SystemExit("No git repository here (or in this workspace) to install hooks into.")
    for repo in repos:
        if a.action == "install":
            notes = H.install(repo, strict=a.strict, pre_push=a.pre_push, vendored=a.vendor)
        elif a.action == "uninstall":
            notes = H.uninstall(repo)
        else:
            notes = [H.status(repo)]
        print(f"{repo.name}: " + "; ".join(notes))


def cmd_fresh(a) -> None:
    ctx = C.detect(Path(a.path or Path.cwd()))
    rows = F.assess_with_parent(ctx)
    if a.json:
        print(json.dumps([{"doc": d.doc, "status": d.status, "reasons": d.reasons} for d in rows], indent=2))
        return
    if not rows:
        print("Nothing to assess at this level.")
    for d in rows:
        print(f"{d.status.upper():<11} {d.doc}")
        for why in d.reasons:
            print(f"            - {why}")
    if any(d.status in ("stale", "unconfirmed") for d in rows):
        print("\nUpdate what changed (refresh skill), then run: groundwork.py confirm <doc>")


def cmd_confirm(a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level == "unknown":
        raise SystemExit("Not in a repo or workspace.")
    done = F.confirm(ctx, a.docs or None)
    print("Confirmed as matching reality: " + ", ".join(done))


def cmd_board(a) -> None:
    ctx = C.detect(Path(a.path or Path.cwd()))
    items = W.collect(ctx, include_done=a.all)
    print(W.to_json(items) if a.json else W.render(items))


def cmd_note(a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level == "unknown":
        raise SystemExit("Not in a repo or workspace.")
    print("noted in " + str(W.add_note(ctx, " ".join(a.text))))


def cmd_deps(a) -> None:
    ctx = C.detect(Path.cwd())
    ref = a.ref or C.active_slug(ctx)
    if not ref:
        raise SystemExit("Give a feature (NNN-slug or repo/NNN-slug) or an RFC id, or activate a feature first.")
    print(R.describe(ctx, ref))


def cmd_record(a) -> None:
    ctx = C.detect(Path.cwd())
    who = [w.strip() for w in a.who.split(",") if w.strip()] if a.who else None
    e = P.record(ctx, a.event, a.ref, by=a.by, via=a.via, who=who, env=a.env, version=a.version, text=a.text or "")
    print(f"recorded {e['event']} on {e['ref']} by {e['by']}" + (f" → {', '.join(who)}" if who else "")
          + (f" ({e['env']} {e['version']})" if e.get("env") else ""))


def cmd_who(a) -> None:
    ctx = C.detect(Path(a.path or Path.cwd()))
    if a.all:
        print(P.table(ctx))
    elif a.person:
        print(P.person_items(ctx, a.person))
    else:
        ref = a.ref or C.active_slug(ctx)
        if not ref:
            raise SystemExit("Give a feature (NNN-slug / repo/NNN-slug), RFC-000N or bugs/NNN-slug; or --person NAME; or --all.")
        print(P.describe(ctx, ref))


def cmd_new_bug(a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level not in ("repo", "standalone"):
        raise SystemExit("Bugs are recorded inside a repo. cd into the repo that has the bug.")
    p = B.new_bug(ctx, a.slug, a.title)
    P.auto_created(ctx, "bug", p, None)
    if a.reported_by:
        P.set_role(p, "reported_by", a.reported_by)
    print(f"{p}\nActive bug set to {p.stem}. Follow the fix-bug skill.")


def cmd_activate_bug(a) -> None:
    ctx = C.detect(Path.cwd())
    if not ctx.repo or not (ctx.repo / "bugs" / f"{a.slug}.md").is_file():
        raise SystemExit(f"bugs/{a.slug}.md does not exist")
    _write(ctx.repo / ".groundwork" / "active-bug", a.slug + "\n")
    print(f"Active bug: {a.slug}")


def cmd_plan_sync(_a) -> None:
    ctx = C.detect(Path.cwd())
    slug = C.active_slug(ctx)
    if not ctx.repo or not slug:
        raise SystemExit("No active feature (groundwork.py activate <NNN-slug>).")
    fdir = ctx.repo / "specs" / slug
    spec = C.doc_state(fdir / "spec.md", ctx)
    if not spec.approved:
        raise SystemExit(f"spec.md is {spec.status}; plan/tasks/evals can only be synced to an APPROVED spec.")
    h = C.body_hash((fdir / "spec.md").read_text(encoding="utf-8"))
    done = []
    for name in ("plan", "tasks", "evals"):
        f = fdir / f"{name}.md"
        if f.is_file() and not C.PLACEHOLDER.search(f.read_text(encoding="utf-8")):
            f.write_text(C.set_fm(f.read_text(encoding="utf-8"), {"spec_version": h}), encoding="utf-8")
            done.append(name + ".md")
    print("Pinned to the current approved spec: " + (", ".join(done) or "nothing (no finished documents yet)"))


def cmd_activate(a) -> None:
    ctx = C.detect(Path.cwd())
    if not ctx.repo:
        raise SystemExit("Not in a repo.")
    if not (ctx.repo / "specs" / a.slug).is_dir():
        raise SystemExit(f"specs/{a.slug} does not exist")
    _write(ctx.repo / ".groundwork" / "active", a.slug + "\n")
    print(f"Active feature: {a.slug}")


def main() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):      # Windows defaults to a legacy code page
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass
    ap = argparse.ArgumentParser(prog="groundwork")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n, fn in (("session-context", cmd_session_context), ("prompt-reminder", cmd_prompt_reminder),
                  ("gate", cmd_gate), ("gate-bash", cmd_gate_bash), ("skill-notice", cmd_skill_notice), ("stop-brevity", cmd_stop_brevity), ("scaffold", cmd_scaffold),
                  ("mark-workspace", cmd_mark_workspace)):
        sub.add_parser(n).set_defaults(fn=fn)
    p = sub.add_parser("status"); p.add_argument("path", nargs="?"); p.set_defaults(fn=cmd_status)
    p = sub.add_parser("approve"); p.add_argument("doc"); p.add_argument("--as", dest="who"); p.set_defaults(fn=cmd_approve)
    p = sub.add_parser("bypass"); p.add_argument("reason", nargs="+"); p.add_argument("--minutes", type=int, default=60)
    p.set_defaults(fn=lambda a: cmd_bypass(argparse.Namespace(reason=" ".join(a.reason), minutes=a.minutes)))
    p = sub.add_parser("new-rfc"); p.add_argument("slug"); p.add_argument("--title"); p.add_argument("--requested-by"); p.set_defaults(fn=cmd_new_rfc)
    p = sub.add_parser("new-feature"); p.add_argument("slug"); p.add_argument("--rfc", required=True); p.add_argument("--requested-by")
    for k in ("extends", "depends-on", "builds-against", "amends"):
        p.add_argument("--" + k, help="comma-separated NNN-slug or repo/NNN-slug")
    p.set_defaults(fn=cmd_new_feature)
    p = sub.add_parser("hooks"); p.add_argument("action", choices=["install", "uninstall", "status"])
    p.add_argument("--strict", action="store_true", help="warnings (unfinished/stale docs) also block")
    p.add_argument("--pre-push", action="store_true", help="also install a pre-push hook")
    p.add_argument("--vendor", action="store_true", help="copy the engine into .groundwork/engine/ so teammates/CI need no plugin")
    p.set_defaults(fn=cmd_hooks)
    p = sub.add_parser("check"); p.add_argument("path", nargs="?"); p.add_argument("--json", action="store_true")
    p.add_argument("--hook", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--strict", action="store_true", help="warnings (unfinished docs) also fail"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("init", help="onboard this project: classify, scaffold, gather evidence")
    p.add_argument("--as", dest="as_", choices=["repo", "workspace"], help="for a directory that is neither yet")
    p.add_argument("--retrofit", action="store_true", help="append missing required sections to existing foundation docs")
    p.add_argument("--dry-run", action="store_true"); p.set_defaults(fn=cmd_init)
    p = sub.add_parser("doctor", help="how far is this project from the standard?")
    p.add_argument("path", nargs="?"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_doctor)
    p = sub.add_parser("fresh"); p.add_argument("path", nargs="?"); p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_fresh)
    p = sub.add_parser("confirm"); p.add_argument("docs", nargs="*"); p.set_defaults(fn=cmd_confirm)
    p = sub.add_parser("board", help="everything in flight, for resuming"); p.add_argument("path", nargs="?")
    p.add_argument("--all", action="store_true", help="include finished work"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_board)
    p = sub.add_parser("note", help="record where work stopped"); p.add_argument("text", nargs="+"); p.set_defaults(fn=cmd_note)
    p = sub.add_parser("deps", help="relations and downstream impact of a feature or RFC"); p.add_argument("ref", nargs="?"); p.set_defaults(fn=cmd_deps)
    p = sub.add_parser("impact"); p.add_argument("ref", nargs="?"); p.set_defaults(fn=cmd_deps)
    p = sub.add_parser("record", help="record who did what: requested/owner/implemented/deployed/support/handover/reported/fixed")
    p.add_argument("event", choices=sorted(P.EVENTS)); p.add_argument("--ref", required=True)
    p.add_argument("--by", help="the person (default: git identity; CI passes its actor)"); p.add_argument("--via", help="tool used, e.g. claude-code")
    p.add_argument("--who", help="comma-separated people the event assigns"); p.add_argument("--env"); p.add_argument("--version"); p.add_argument("--text")
    p.set_defaults(fn=cmd_record)
    p = sub.add_parser("who", help="who requested / owns / implemented / deployed / supports it — and whom to contact")
    p.add_argument("ref", nargs="?"); p.add_argument("--person"); p.add_argument("--all", action="store_true"); p.add_argument("--path")
    p.set_defaults(fn=cmd_who)
    p = sub.add_parser("new-bug"); p.add_argument("slug"); p.add_argument("--title"); p.add_argument("--reported-by"); p.set_defaults(fn=cmd_new_bug)
    p = sub.add_parser("activate-bug"); p.add_argument("slug"); p.set_defaults(fn=cmd_activate_bug)
    p = sub.add_parser("plan-sync", help="record that plan/tasks/evals match the current approved spec"); p.set_defaults(fn=cmd_plan_sync)
    p = sub.add_parser("activate"); p.add_argument("slug"); p.set_defaults(fn=cmd_activate)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
