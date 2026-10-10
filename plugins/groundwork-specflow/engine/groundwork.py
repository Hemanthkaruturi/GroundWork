"""groundwork — command line and hook entry point for the groundwork plugin.

Hooks:      groundwork.py session-context | prompt-reminder | gate | gate-bash     (JSON on stdin; Claude Code or Devin)
Onboarding:  groundwork.py init [--as repo|workspace] [--retrofit] [--dry-run] | doctor [--json]
Anyone/CI:  groundwork.py check [--strict] [--json] | fresh [--json] | hooks install|uninstall|status
Agents:     groundwork.py confirm [doc ...]   (after updating docs to match reality) | confirm --baseline <slug ...>
Humans:     groundwork.py status | approve <doc> | bypass <reason>
People:     groundwork.py who <feature|RFC|bug> | who --person NAME | who --all | record <event> --ref R ...
Resume:     groundwork.py board [--all] [--json] | note <text> | deps <feature|RFC> | new-bug <slug> | activate-bug <slug>
Agents:     groundwork.py scaffold | new-rfc <slug> | new-feature <slug> --rfc N | activate <slug>
Baselines:  groundwork.py adopt-specs [--dry-run] [slug ...] | adopt-specs --classify baseline|planned|archived <slug ...>
Decisions:  groundwork.py new-adr <slug> [--title T] [--rfc RFC-000N | --retrospective [--source PATH] [--decided-at DATE]]
Contracts:  groundwork.py new-contract <provider-topic> [--title T] [--provider P] [--consumers a,b] [--as-built]
            groundwork.py new-baseline <slug> [--title T] [--capability C] | capability set|link|unlink ... | capabilities
Quality:    groundwork.py verify [--fix] [--step S] | quality [show|init [--create]|keep|set step=CMD|ignore]
Code:       groundwork.py codemap [--check] | layout [--json] | layout init --profile P [--root R] [--create] | layout keep | layout map role=path [--legacy P]
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
import groundwork_alert as A
import groundwork_baseline as BL
import groundwork_board as W
import groundwork_brevity as V
import groundwork_bugs as B
import groundwork_check as K
import groundwork_codemap as M
import groundwork_contracts as CT
import groundwork_core as C
import groundwork_decisions as AD
import groundwork_discover as D
import groundwork_doctor as X
import groundwork_fresh as F
import groundwork_hooks as H
import groundwork_host as G
import groundwork_layout as L
import groundwork_people as P
import groundwork_quality as Q
import groundwork_relations as R
import groundwork_secrets as S

TRIAGE = (
    "Before changing any file, triage the request: a defect -> fix-bug skill; new or changed behaviour OR LOOK "
    "(UI redesign, restyle, copy) -> interview -> RFC -> approval -> spec -> plan -> tasks -> evals; continuing earlier work -> "
    "resume skill. Other skills/plugins (frontend-design, etc.) are craft tools used INSIDE the implement step after the "
    "spec is approved - they never replace or skip this path, and the shell is gated like the Write tool."
)

BREVITY = (
    "Write for a busy reader: answer or decision first, then at most a few short bullets. Short sentences, everyday words, "
    "no jargon or bare IDs (say what FR-6 or GW026 MEANS). About 150 words unless asked for more. Never re-tell the steps you took. "
    "Ask with the picker; give your recommendation and what each option leads to. Long content goes in a file - summarise it in 5 lines. "
    "SHORT MUST NOT MEAN LESS TRUE: always keep the decision needed, anything that failed or was skipped, what you did NOT verify, "
    "risks and side effects, every file/setting changed, assumptions, blockers and the user's next step."
)

RULES = """\
groundwork is active. These rules are enforced by hooks, not suggestions:
0. COMMUNICATION (applies to every reply): BREVITY_TEXT
1. Know your level. WORKSPACE = the folder above the repos (PROJECT.md, ARCHITECTURE.md, CONSTITUTION.md, CONTRACTS/, DECISIONS/). REPO = where application code lives (ARCHITECTURE.md, AGENTS.md, specs/). A repo with no workspace above it is STANDALONE and carries both sets.
2. Foundation first: no PROJECT.md / ARCHITECTURE.md => write them (bootstrap skill) before any other work. Never invent business facts — ask the user.
3. To build something: interview the user (interview skill) until nothing is ambiguous -> RFC -> HUMAN approval -> spec -> plan -> tasks -> evals -> implement. Never skip forward.
4. You cannot approve documents. Only the user can, with /groundwork-specflow:approve <file>. Editing an approved document makes the approval stale.
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
18. CODE LAYOUT: each repo records ONE decision (code-layout skill). STANDARD: code goes in fixed role folders: core (business logic, no I/O), connectors/<system> (the ONLY code that talks to LLMs, databases, HTTP APIs, queues, email), entrypoints (thin http/cli/workers), config (the only env/secret reads), and a wiring file that plugs connectors into core; core never imports connectors; no utils/helpers/common folders. KEEP: the user chose to keep the repo's own structure, so put new code where similar code already lives, copy its patterns, and never create layout folders or move existing code. An existing repo with no decision yet: ASK the user (migrate or keep) before writing code; never migrate without being asked. EVERY repo has CODEMAP.md (where each kind of code lives): read it before searching the code; after adding, moving or removing a folder run `groundwork.py codemap` and describe new folders in its Holds column.
19. CREDENTIALS: code reads secrets ONLY from environment variables - never write a key, token or password into a file. Locally they come from `.env`, which must be git-ignored and never committed; every variable name goes in `.env.example` with no real value. Load `.env` in ONE place (config/ or the wiring file): Python `load_dotenv()` from python-dotenv (`uv add python-dotenv`), Node `--env-file=.env` or `dotenv`, Go `godotenv`; never let it override variables the platform already set. Front-end code never holds secrets (it ships to the browser); libraries never load `.env`. In a repo that keeps its own structure, keep its existing way of loading settings - only the safety rules apply.
20. CODE QUALITY: each repo records ONE toolchain decision (code-quality skill): GroundWork's standard tools, or KEEP its own. After every task run `groundwork.py verify` (format, lint, types, tests) and fix what fails before marking it done; never weaken a rule, add an ignore or skip a test to get green. The coding rules are in AGENTS.md -> Code quality. An existing repo with no decision: ASK before adding or changing any tool config - a new formatter rewrites every file.
21. ALERTS: if the user asks to turn alerts on or off, run `groundwork.py alerts on` (or `off`); for just the spoken voice (sound and notification stay), run `groundwork.py alerts voice off` (or `on`). It is their own setting, kept for every project; never change it unasked.
22. EXISTING BEHAVIOUR: a spec with `origin: baseline` documents what already exists (baseline skill) — history, not work: no RFC, no tasks, never in flight. A feature that changes existing behaviour `extends`/`amends` the baseline; a bug with no requirement to cite gets a bounded baseline first. `origin: imported` is a legacy document awaiting classification — a reference, never an approved requirement. If the context lists DOCUMENTATION REVIEW items, they wait for a person, not for code.
23. CONSTITUTION: CONSTITUTION.md (the repo's, and the workspace's above it) binds every reply, document and code edit, in every step — planning, tasks, evals, implementing and bug fixing, not only the RFC. Its guardrails are listed below at session start; read the file before a plan, a fix plan or code. Never work around a rule: a conflict is raised to the user as an amendment proposal. The RFC's §7 records the check once; other documents cite it.
Use `python3 ${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py status` (or `board`) any time you are unsure where you are."""
RULES = RULES.replace("BREVITY_TEXT", BREVITY)


def out(obj: dict) -> None:
    print(json.dumps(obj))


def hook_input() -> dict:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return {}
    log = os.environ.get(
        "GROUNDWORK_HOOK_LOG"
    )  # opt-in diagnostics: what did the harness actually send?
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
        lines.append(
            "You are in a repo inside a workspace: read the workspace's PROJECT.md, "
            "ARCHITECTURE.md, CONSTITUTION.md and CONTRACTS/ for the whole product."
        )
    rails = C.guardrails(ctx)
    if rails:
        shown = rails[: C.GUARDRAIL_LINES]
        lines.append(
            "CONSTITUTION GUARDRAILS (bind every reply, document and code edit; never work around one — propose an amendment):"
        )
        lines += ["  - " + g for g in shown]
        if len(rails) > len(shown):
            lines.append(
                f"  … {len(rails) - len(shown)} more in CONSTITUTION.md — read it before any plan or code."
            )
    missing, unfinished = C.foundation_gaps(ctx)
    if missing:
        lines.append("MISSING: " + ", ".join(missing))
    if unfinished:
        lines.append(
            "UNFINISHED (unresolved [TODO]/[NEEDS CLARIFICATION] markers): "
            + ", ".join(unfinished)
        )
    rf = C.rfcs(ctx) if ctx.level != "unknown" else []
    if rf:
        lines.append("RFCs: " + "; ".join(f"{r.path.stem} [{r.status}]" for r in rf))
    slug = C.active_slug(ctx)
    if slug:
        lines.append(f"Active feature: specs/{slug}")
    if ctx.level in ("repo", "standalone"):
        cm, why = M.state(ctx.repo)
        lines.append(
            {
                "current": "CODE MAP: CODEMAP.md lists where each kind of code lives - read it before searching the code.",
                "unfinished": f"CODE MAP: CODEMAP.md - read it before searching the code; {why}: fill its Holds column.",
                "outdated": "CODE MAP: CODEMAP.md no longer matches the code - run `groundwork.py codemap`, then fill any new Holds cells.",
                "missing": "CODE MAP MISSING: run `groundwork.py codemap` to generate CODEMAP.md, then fill its Holds column.",
            }[cm]
        )
        for row in M.brief(ctx.repo):
            lines.append("  - " + row)
        lines.append(Q.summary(Q.load(ctx.repo, ctx.config), L.has_code(ctx.repo)))
        lay = L.load(ctx.repo, ctx.config)
        if lay is not None:
            lines.append(L.summary(lay))
        elif L.has_code(ctx.repo):
            lines.append(
                "CODE LAYOUT NOT DECIDED: this repo has code but no layout decision. Before writing code, use the "
                "code-layout skill to ask the user: migrate to the standard layout, or keep the current structure."
            )
        else:
            lines.append(
                "CODE LAYOUT NOT DECIDED: new repo - set up the standard layout with the code-layout skill "
                "(groundwork.py layout init --profile <service|cli|web|library> --create)."
            )
    if ctx.level != "unknown":
        lines.append(
            "You are working on behalf of: "
            + P.whoami(ctx)
            + " — record their name, never the agent's, as the responsible person."
        )
    flight = W.collect(ctx) if ctx.level != "unknown" else []
    if flight:
        lines.append(
            "IN FLIGHT (resume with the resume skill; full list: groundwork.py board):"
        )
        for w in flight[:5]:
            lines.append(
                f"  - [{w.kind}] {w.label} — {w.state} ({w.age()})"
                + (" ← active" if w.active else "")
                + (f"; blocked by {'; '.join(w.blocked_by)}" if w.blocked_by else "")
                + (f"; last note: {w.note}" if w.note else "")
            )
    lines += BL.review_lines(ctx) if ctx.level != "unknown" else []
    stale = F.stale_lines(ctx) if ctx.level != "unknown" else []
    if stale:
        lines.append("DOCS MAY BE STALE (use the refresh skill): " + " | ".join(stale))
    phase, ins = C.next_step(ctx)
    lines.append(f"PHASE: {phase}\nNEXT: {ins}")
    lines.append(f"Enforcement: {ctx.enforcement}")
    return "\n".join(lines)


def cmd_session_context(_a) -> None:
    inp = hook_input()
    ctx = C.detect(G.cwd(inp))
    out(
        G.context(
            inp,
            "SessionStart",
            G.adapt_rules(RULES, G.name(inp)) + "\n\n" + describe(ctx),
        )
    )


HUMAN_CMD = re.compile(
    r"^\s*/(?:groundwork-specflow:)?(approve|bypass)\b\s*(.*)$", re.DOTALL
)


def run_human_action(name: str, argstr: str, cwd: str) -> str:
    """Approve/bypass, run from the UserPromptSubmit hook so only a typed prompt can trigger them."""
    os.chdir(cwd)
    try:
        args = shlex.split(argstr)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            if name == "approve":
                if not args:
                    raise SystemExit(
                        "Usage: /groundwork-specflow:approve <path to document | RFC-NNNN> [more paths …]"
                    )
                who = None
                if "--as" in args:
                    i = args.index("--as")
                    who = args[i + 1]
                    del args[i : i + 2]
                cmd_approve(argparse.Namespace(docs=args, who=who))
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
        res = run_human_action(m.group(1), m.group(2), G.cwd(inp))
        out(
            G.context(
                inp,
                "UserPromptSubmit",
                f"[groundwork {m.group(1)}] The user's command was already executed by the hook. "
                f"Result: {res}\nReport this result to the user in one or two lines. Run nothing yourself.",
            )
        )
        return
    ctx = C.detect(G.cwd(inp))
    phase, ins = C.next_step(ctx)
    stale = F.stale_lines(ctx) if ctx.level != "unknown" else []
    note = (
        (
            " Foundation docs may be stale ("
            + "; ".join(stale)[:300]
            + ") — before finishing, run the refresh skill."
        )
        if stale
        else ""
    )
    out(
        G.context(
            inp,
            "UserPromptSubmit",
            f"[groundwork] level={ctx.level} phase={phase}. {ins}{note} {TRIAGE} {BREVITY}",
        )
    )


def deny(full: dict, reason: str) -> None:
    out(G.deny(full, reason))


def cmd_gate(_a) -> None:
    full = hook_input()
    paths, understood = G.edit_targets(full)
    if not understood:
        if (
            full.get("tool_name") in G.DEVIN_EDIT_TOOLS
        ):  # fail closed: an unread target must not slip past the gate
            deny(
                full,
                f"groundwork-specflow: could not tell which file {G.describe_input(full)} would write, so the edit "
                "is held. Use the write or edit tool with a file path, or ask the user for /groundwork-specflow:bypass.",
            )
        return
    for path in paths:
        if C.is_protected_path(path):
            return deny(
                full,
                "groundwork-specflow: approval records are written only by the user's /groundwork-specflow:approve command.",
            )
        ok, reason = C.gate_code_edit(path, G.session_cwd(full))
        if not ok:
            return deny(full, reason)


def cmd_stop_brevity(_a) -> None:
    """Optional (`"brevity": "enforce"`): send an over-long reply back to be rewritten, once."""
    full = hook_input()
    if full.get("stop_hook_active"):
        return
    ctx = C.detect(G.cwd(full))
    mode = os.environ.get("GROUNDWORK_BREVITY") or ctx.config.get("brevity", "guide")
    if mode != "enforce":
        return
    limit = int(ctx.config.get("max_reply_words", V.DEFAULT_REPLY_WORDS))
    tp = full.get("transcript_path")
    # The harness hands over the final message itself; the transcript may not have it written yet, so it is only a fallback.
    text = full.get("last_assistant_message") or (
        V.last_reply_text(Path(tp)) if tp else ""
    )
    n = V.reply_words(text)
    if n > limit:
        saved = V.save_full_reply(ctx.repo or ctx.workspace or ctx.root, text)
        out(
            {
                "decision": "block",
                "reason": V.SHORTEN.format(n=n, limit=limit, saved=saved),
            }
        )


def awaiting_approval(ctx: C.Ctx) -> C.DocState | None:
    """The finished document now waiting only on the person's /approve, if any."""
    if ctx.level == "unknown":
        return None
    slug = C.active_slug(ctx) if ctx.level != "workspace" else None
    if slug:
        spec = C.doc_state(ctx.repo / "specs" / slug / "spec.md", ctx)
        rfc = C.find_rfc(ctx, spec.meta.get("rfc", ""))
        docs = ([C.doc_state(rfc, ctx)] if rfc else []) + [spec]
    else:
        docs = C.rfcs(ctx)
    for d in docs:
        if not d.approved:
            return d if d.exists and not d.placeholders else None
    return None


def _alert_key(path: Path) -> str:
    return f"{path.resolve()}:{C.body_hash(path.read_text(encoding='utf-8'))}"


def cmd_alert_stop(_a) -> None:
    """At the end of a turn, alert (once per document version) if the agent now waits at a gate."""
    full = hook_input()
    if not A.enabled():
        return
    ctx = C.detect(G.cwd(full))
    where = (ctx.repo or ctx.workspace or ctx.root).name
    doc = awaiting_approval(ctx)
    if doc:
        if A.first_time("decision", _alert_key(doc.path)):
            A.notify(
                "decision", f"[{where}] {doc.path.name} is ready for your approval."
            )
        return
    slug = C.active_slug(ctx) if ctx.level != "workspace" else None
    handover = ctx.repo / "specs" / slug / "handover.md" if slug else None
    if handover and handover.is_file() and A.first_time("done", _alert_key(handover)):
        A.notify("done", f"[{where}] {slug} is built. The handover is ready.")


def cmd_alert_question(_a) -> None:
    """The agent is about to ask the person something; it cannot go on until they answer."""
    full = hook_input()
    if A.enabled():
        where = Path(G.cwd(full)).name
        A.notify("question", f"[{where}] The agent is waiting for your answers.")


def cmd_alerts(a) -> None:
    if a.state == "voice":
        if a.value not in ("on", "off"):
            raise SystemExit("Usage: groundwork.py alerts voice on|off")
        path = A.set_voice(a.value == "on")
        note = (
            ""
            if A.enabled()
            else " Alerts themselves are off; `alerts on` turns them on."
        )
        print(f"Voice is {a.value} for you in every project (saved in {path}).{note}")
        return
    voice = A.voice_enabled()
    if a.state in ("on", "off"):
        path = A.set_enabled(a.state == "on")
        print(f"Alerts are {a.state} for you in every project (saved in {path}).")
        if a.state == "on":
            A.fire(A.plan("done", "Alerts are on.", voice=voice))
            heard = "a sound and a voice" if voice else "a sound (voice is off)"
            print(f"You should hear {heard} now; if not, run `alerts test`.")
        return
    if a.state == "test":
        steps = A.plan("decision", "This is a test alert.", voice=voice)
        print(f"Playing a test alert ({steps['backend']}).")
        A.fire(steps, wait=True)
        return
    print(
        f"Alerts are {'on' if A.enabled() else 'off'}, voice is {'on' if voice else 'off'}."
    )


def cmd_skill_notice(_a) -> None:
    """When any non-groundwork skill loads, remind the agent it is a craft tool inside the process."""
    full = hook_input()
    name = G.skill_name(full)
    if not name or name.startswith("groundwork-specflow:"):
        return
    ctx = C.detect(G.cwd(full))
    if ctx.level == "unknown":
        return
    phase, _ins = C.next_step(ctx)
    out(
        G.context(
            full,
            "PreToolUse",
            f"[groundwork] You are loading '{name}', which is not a groundwork skill: treat it as a craft tool for the IMPLEMENT step only. "
            f"Current phase: {phase}. Unless the phase is 'implement' (approved RFC/spec, finished plan, tasks and evals), do NOT start building with it: "
            f"triage the request first (defect -> fix-bug; new/changed behaviour or look -> interview -> RFC -> spec; continuing -> resume). "
            f"Design choices it suggests belong in the spec as testable requirements before any file is written. Writing files by shell is gated like the Write tool.",
        )
    )


def cmd_gate_bash(_a) -> None:
    """Parse the proposed tool command for write targets; never execute it.

    This hook emits only a denial or no output. It does not run the submitted
    command, dump the process environment, or send hook input over the network.
    """
    full = hook_input()
    cmd = full.get("tool_input", {}).get("command", "")
    cwd = Path(G.cwd(full))
    if C.is_protected_command(cmd, cwd):
        return deny(
            full,
            "groundwork-specflow: approvals and bypasses are human acts. Ask the user to run "
            "/groundwork-specflow:approve or /groundwork-specflow:bypass themselves.",
        )
    ok, reason = C.gate_shell_command(cmd, cwd)
    if not ok:
        deny(full, reason)


def cmd_status(a) -> None:
    ctx = C.detect(Path(a.path or Path.cwd()))
    print(describe(ctx))
    slug = C.active_slug(ctx)
    if slug and (ctx.repo / "specs" / slug).is_dir():
        print(f"\nPipeline for specs/{slug}:")
        for st in C.feature_steps(ctx, slug):
            print(f"  [{'x' if st.ok else ' '}] {st.key:<6} {st.detail}")
        d, t = C.task_counts(ctx, slug)
        print(f"  tasks: {d}/{t} done")


def _resolve_doc(ref: str) -> Path:
    p = Path(ref).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    if not p.is_file() and ref.upper().startswith("RFC"):
        ctx0 = C.detect(Path.cwd())
        p = C.find_rfc(ctx0, ref) or p
    return p


def cmd_approve(a) -> None:
    """One or several documents. Every one is preflighted first; if any fails, none is recorded —
    each approval is still hashed and recorded on its own document."""
    refs = list(getattr(a, "docs", None) or [a.doc])
    paths, seen, problems = [], set(), []
    for ref in refs:
        p = _resolve_doc(ref)
        try:
            key = p.resolve()
        except OSError:
            key = p
        if key in seen:
            problems.append(f"{ref}: given twice")
            continue
        seen.add(key)
        paths.append(p)
        why = C.approve_preflight(p, C.detect(p))
        if why:
            problems.append(f"{p.name if p.is_file() else ref}: {why}")
    if problems:
        raise SystemExit(
            ("nothing approved — " if len(refs) > 1 else "") + "\n".join(problems)
        )
    for p in paths:
        ctx = C.detect(p)
        st = C.approve(p, ctx, a.who)
        print(
            f"{p.name if len(paths) == 1 else p.parent.name + '/' + p.name}: {st.status} "
            f"({C.signoffs_label(st)} sign-offs: {', '.join(st.signers)})"
        )
        if st.status == "in-review":
            print(signoff_help(p, st))
        note = _unreviewed_baseline_note(p, ctx)
        if note:
            print(note)


def _unreviewed_baseline_note(p: Path, ctx: C.Ctx) -> str:
    """Approval and source review are separate records; say so when a baseline has only the first."""
    if p.name != "spec.md" or not ctx.repo or not C.is_baseline(C.spec_meta(p.parent)):
        return ""
    import groundwork_fresh as F

    if F.load(ctx).get(F.BASELINE_NS + p.parent.name):
        return ""
    return (
        f"Note: the sources of {p.parent.name} were never reviewed. Compare it with the files its Evidence "
        f"table cites, then run: groundwork.py confirm --baseline {p.parent.name}"
    )


def signoff_help(p: Path, st: C.DocState) -> str:
    """How the user moves a document that is waiting on sign-offs forward."""
    if not st.needed:
        return (
            f"Next step for {p.name}: its `signoffs_required` is not a whole number, so no count of sign-offs "
            "can satisfy it. Set it to the number of reviewers (1 or more) and approve again."
        )
    left = st.needed - len(set(st.signers))
    floor = C.min_signoffs(st.meta)
    lower_to = max(len(set(st.signers)), floor)
    if lower_to < st.needed:
        alternative = (
            f", or, if you are the only reviewer, lower `signoffs_required: {st.needed}` to {lower_to} in its "
            f"front matter and run /groundwork-specflow:approve {p.name} again (existing sign-offs still count)"
        )
    else:
        alternative = (
            f"; an api RFC needs every lead it touches, at least {floor}, so the count cannot be lowered"
            if floor > 1
            else ""
        )
    return (
        f"Next step for {p.name}: {left} more sign-off(s) needed. Each remaining signer runs "
        f"/groundwork-specflow:approve {p.name}{alternative}. A bypass does not replace sign-offs."
    )


def cmd_bypass(a) -> None:
    ctx = C.detect(Path.cwd())
    root = ctx.repo or ctx.root
    if not a.reason.strip():
        raise SystemExit("A bypass needs a reason: /groundwork-specflow:bypass <why>")
    f = root / ".groundwork" / "bypass.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    until = time.time() + a.minutes * 60
    f.write_text(
        json.dumps({"reason": a.reason, "by": C.signer(), "until": until}) + "\n",
        encoding="utf-8",
    )
    with (root / ".groundwork" / "bypass.log").open("a", encoding="utf-8") as log:
        log.write(f"{time.strftime('%F %T')} {C.signer()} {a.minutes}min: {a.reason}\n")
    print(
        f"Gate bypassed for {a.minutes} minutes in {root}. Logged to .groundwork/bypass.log."
    )
    print(
        "This lifts the code-edit gate only: it does not approve RFCs or specs, and it ends after "
        f"{a.minutes} minutes. Update the spec afterwards for any behaviour change."
    )
    slug = C.active_slug(ctx)
    spec = [C.doc_state(ctx.repo / "specs" / slug / "spec.md", ctx)] if slug else []
    for st in C.rfcs(ctx) + spec:
        if st.status == "in-review":
            print(signoff_help(st.path, st))


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
                tpl = {
                    "AGENTS.md": "AGENTS.repo.md"
                    if ctx.level == "repo"
                    else "AGENTS.workspace.md"
                }.get(f, f)
                _write(
                    base / f,
                    C.render(
                        tpl,
                        name=base.name,
                        date=time.strftime("%F"),
                        workspace=str(ctx.workspace or ""),
                    ),
                )
    for d in spec["dirs"]:
        if not (base / d).is_dir():
            made.append(d + "/")
            if not dry:
                (base / d).mkdir(parents=True)
                if d == "DECISIONS":
                    _write(
                        base / d / "README.md",
                        C.render("DECISIONS-index.md", name=base.name),
                    )
                else:
                    (base / d / ".gitkeep").touch()
    if (
        ctx.level in ("repo", "standalone") and not M.path(base).is_file()
    ):  # every repo has a code map
        made.append(M.FILE)
        if not dry:
            M.write(base)
    if ctx.level in ("repo", "standalone") and not S.env_ignored(
        base
    ):  # local secrets never reach git
        made.append(".gitignore entry for .env")
        if not dry:
            S.ensure_ignored(base)
    if not dry:
        gi = base / ".groundwork" / ".gitignore"
        if not gi.exists():
            _write(gi, GITIGNORE)
        elif "discovery.json" not in gi.read_text(encoding="utf-8"):
            gi.write_text(
                gi.read_text(encoding="utf-8").rstrip("\n") + "\ndiscovery.json\n",
                encoding="utf-8",
            )
        if "standard" not in C.read_config(base):
            C.write_config(base, standard=C.STANDARD_VERSION)
    return made


def cmd_scaffold(_a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level == "unknown":
        raise SystemExit(
            "Not in a repo or workspace. `git init` first, or mark a workspace with "
            "`groundwork.py mark-workspace`."
        )
    made = scaffold_at(ctx)
    print(
        "Created: "
        + (", ".join(made) or "nothing (all present)")
        + "\nEvery new file contains [TODO] markers. Fill them with the user (bootstrap skill)."
    )


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
        tpl = [
            m.group(1).strip()
            for m in __import__("re").finditer(
                r"^## (.+)$",
                (C.TEMPLATES / key).read_text(encoding="utf-8"),
                __import__("re").M,
            )
        ]
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
            print(
                "git init (this directory is now a repo)"
                if not a.dry_run
                else "would: git init"
            )
        elif a.as_ == "workspace":
            if not a.dry_run:
                C.write_config(cwd, level="workspace", standard=C.STANDARD_VERSION)
            print(
                "marked as a workspace"
                if not a.dry_run
                else "would: mark this directory as a workspace"
            )
        else:
            raise SystemExit(
                "This directory is neither a git repository nor a workspace.\n"
                "  groundwork.py init --as repo        # git init here\n"
                "  groundwork.py init --as workspace   # it will hold several repos (clone/create them inside)"
            )
        ctx = (
            C.detect(cwd)
            if not a.dry_run
            else C.Ctx(
                "repo" if a.as_ == "repo" else "workspace",
                cwd,
                repo=cwd if a.as_ == "repo" else None,
                workspace=cwd if a.as_ == "workspace" else None,
            )
        )
    targets = [ctx]
    if ctx.level == "workspace":
        targets += [C.detect(k, ctx.workspace) for k in C.child_repos(ctx.workspace)]
    verb = "would create" if a.dry_run else "created"
    for t in targets:
        base = t.workspace if t.level == "workspace" else t.repo
        d = (
            D.discover(base) if t.level != "workspace" else None
        )  # BEFORE scaffolding: only pre-existing things count
        made = scaffold_at(t, a.dry_run)
        print(
            f"\n[{base.name}] {t.level}: {verb} "
            + (", ".join(made) or "nothing (foundation already present)")
        )
        if a.retrofit:
            r = retrofit_at(t, a.dry_run)
            print(
                f"[{base.name}] retrofit: "
                + (
                    "; ".join(r)
                    if r
                    else "existing documents already have every required section"
                )
            )
        if t.level != "workspace":
            if not a.dry_run:
                _write(
                    base / ".groundwork" / "discovery.json",
                    json.dumps(d, indent=2) + "\n",
                )
                M.write(base)  # refresh: scaffold only creates a missing one
                print(
                    f"[{base.name}] code map → {M.FILE}: {M.state(base)[0]} (describe each folder in its Holds column)"
                )
            print(
                f"[{base.name}] evidence gathered{'' if a.dry_run else ' → .groundwork/discovery.json'}:"
            )
            print(D.summarize(d))
        if t.level == "repo" and t.workspace:
            gaps = C._gaps_at("workspace", t.workspace, "")[0]
            if gaps:
                print(
                    f"[{base.name}] note: the workspace above lacks {', '.join(gaps)} — run init there too"
                )
    print("\nNext:")
    print(
        "  1. Start Claude Code with the plugin and run /groundwork-specflow:bootstrap — it drafts the documents from the evidence above"
    )
    print("     and asks you only what code cannot tell (purpose, people, decisions).")
    print(
        "  2. groundwork.py doctor      # see how far the project is from the standard"
    )
    if not a.dry_run:
        print()
        print(X.render(X.diagnose(cwd)))


def cmd_layout(a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level not in ("repo", "standalone"):
        raise SystemExit(
            "The code layout is recorded per repo. Run this inside a repository"
            + (" (the workspace holds no code)." if ctx.level == "workspace" else ".")
        )
    repo, current = ctx.repo, L.load(ctx.repo)
    raw = (
        ctx.config.get("layout") if isinstance(ctx.config.get("layout"), dict) else None
    )
    decided = {"decided_by": C.signer(), "decided": time.strftime("%Y-%m-%d")}
    if a.action == "show":
        print(L.as_json(current) if a.json else L.render(repo))
        return
    if a.action == "ignore":
        print(
            "Added GroundWork's documents to .prettierignore."
            if Q.ensure_prettier_ignore(repo)
            else ".prettierignore already excludes GroundWork's documents."
        )
        return
    if a.action in ("init", "keep") and current is not None and not a.force:
        raise SystemExit(
            f"This repo already recorded its layout decision (mode: {current.mode}). "
            "Change it only if the user asked to: add --force."
        )
    if a.action == "keep":
        L.write(repo, {"mode": "keep", **decided})
        print(
            "Recorded: this repo keeps its own structure. New code follows the existing patterns; nothing is moved."
        )
        print(
            f"Code map updated: {M.write(repo).name} — describe each folder in its Holds column."
        )
        return
    if a.action == "init":
        if not a.profile:
            raise SystemExit(
                "--profile is required: "
                + ", ".join(f"{k} ({v['about']})" for k, v in L.PROFILES.items())
            )
        layout = {
            "mode": "standard",
            "profile": a.profile,
            "root": a.root or L.guess_root(repo),
            **decided,
        }
        lay = L.load(repo, {"layout": layout})
        if lay.problems:
            raise SystemExit("; ".join(lay.problems))
        L.write(repo, layout)
        made = L.create_folders(repo, lay) if a.create else []
        if a.create and a.profile != "library" and S.example_names(repo)[0] is None:
            (repo / ".env.example").write_text(
                S.example_stub(sorted(S.read_names(repo, lay))), encoding="utf-8"
            )
            made.append(".env.example")
        print(
            f"Recorded: standard layout, {a.profile} profile, root {layout['root']}."
            + (f" Created: {', '.join(made)}." if made else "")
            + (
                ""
                if a.create
                else " Folders are not created (add --create); map existing ones with: groundwork.py layout map role=path."
            )
        )
        print("\n" + L.render(repo))
        print(f"\nCode map updated: {M.write(repo).name}")
        return
    # map: add role=path mappings, legacy and wiring paths to a standard layout
    if current is None or current.mode != "standard":
        raise SystemExit(
            "`layout map` needs a standard layout: run `groundwork.py layout init --profile ...` first."
        )
    layout = dict(raw)
    folders = {k: L._paths(v) for k, v in (layout.get("folders") or {}).items()}
    for item in a.assign:
        role, sep, path = item.partition("=")
        if not sep or not path:
            raise SystemExit(f"expected role=path, got {item!r}")
        folders.setdefault(role, [])
        if L._rel(path) not in folders[role]:
            folders[role].append(L._rel(path))
    if folders:
        layout["folders"] = folders
    for key, extra in (("legacy", a.legacy), ("wiring", a.wiring)):
        if extra:
            layout[key] = sorted(
                set(L._paths(layout.get(key))) | {L._rel(x) for x in extra}
            )
    lay = L.load(repo, {"layout": layout})
    if lay.problems:
        raise SystemExit("; ".join(lay.problems))
    L.write(repo, layout)
    print(L.render(repo))
    print(f"\nCode map updated: {M.write(repo).name}")


def cmd_codemap(a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level not in ("repo", "standalone"):
        raise SystemExit(
            "The code map is per repo. Run this inside a repository"
            + (" (the workspace holds no code)." if ctx.level == "workspace" else ".")
        )
    if a.check:
        st, why = M.state(ctx.repo)
        print(f"{M.FILE}: {st}" + (f" ({why})" if why else ""))
        raise SystemExit(0 if st == "current" else 1)
    p = M.write(ctx.repo)
    st, why = M.state(ctx.repo)
    print(
        f"Wrote {p.name}."
        + (f" {why}: describe them in the Holds column." if st == "unfinished" else "")
    )


def _repo_ctx(what: str) -> C.Ctx:
    ctx = C.detect(Path.cwd())
    if ctx.level not in ("repo", "standalone"):
        raise SystemExit(
            f"The {what} is per repo. Run this inside a repository"
            + (" (the workspace holds no code)." if ctx.level == "workspace" else ".")
        )
    return ctx


def cmd_quality(a) -> None:
    ctx = _repo_ctx("code quality toolchain")
    repo, current = ctx.repo, Q.load(ctx.repo)
    raw = (
        ctx.config.get("quality") if isinstance(ctx.config.get("quality"), dict) else {}
    )
    decided = {"decided_by": C.signer(), "decided": time.strftime("%Y-%m-%d")}
    langs = Q.languages(repo)
    if a.action == "show":
        if current is None:
            found = Q.detect_existing(repo)
            print("No code quality decision recorded for this repo.")
            if L.has_code(repo):
                print(
                    "It already has code: ask the user whether to adopt the standard toolchain or keep the repo's own tools."
                )
                print(
                    "  keep:   groundwork.py quality keep      (records the commands below; changes no file)"
                )
                print(
                    "  adopt:  groundwork.py quality init --create   (adds configs; the formatter will rewrite files)"
                )
                print("Commands the repo's files show (evidence, not a decision):")
                print(
                    "\n".join(f"  {s:<7} {' · '.join(c)}" for s, c in found.items())
                    or "  none found"
                )
            else:
                print("New code: groundwork.py quality init --create")
            return
        if current.problems:
            raise SystemExit("Invalid quality entry: " + "; ".join(current.problems))
        cmds, fix = Q.effective(repo, current)
        print(
            f"Mode: {current.mode} ({'GroundWork standard toolchain' if current.mode == 'standard' else 'own tools, kept by choice'})"
        )
        print("Languages: " + (", ".join(langs) or "no code yet"))
        for s in Q.STEPS:
            print(
                f"  {s:<7} "
                + (" · ".join(cmds.get(s, [])) or "—")
                + (f"   (fix: {' · '.join(fix[s])})" if fix.get(s) else "")
            )
        return
    if a.action == "ignore":
        print(
            "Added GroundWork's documents to .prettierignore."
            if Q.ensure_prettier_ignore(repo)
            else ".prettierignore already excludes GroundWork's documents."
        )
        return
    if a.action in ("init", "keep") and current is not None and not a.force:
        raise SystemExit(
            f"This repo already recorded its quality decision (mode: {current.mode}). "
            "Change it only if the user asked to: add --force."
        )
    if a.action == "init":
        entry = {"mode": "standard", **decided}
        C.write_config(repo, quality=entry)
        made = Q.write_configs(repo, langs) if a.create else []
        q = Q.load(repo)
        agents = Q.ensure_agents_section(repo, q)
        print(
            "Recorded: GroundWork standard toolchain."
            + (f" Created: {', '.join(made)}." if made else "")
        )
        installs = [
            Q.install_line(repo, x)
            for x in ("python", "javascript", "go")
            if x in langs
        ]
        if installs:
            print("Install the tools: " + " ; ".join(installs))
        if agents:
            print(
                "AGENTS.md: Code quality section written (commands and coding rules for every agent)."
            )
        return
    if a.action == "keep":
        found = Q.detect_existing(repo)
        C.write_config(repo, quality={"mode": "keep", "commands": found, **decided})
        Q.ensure_agents_section(repo, Q.load(repo))
        print(
            "Recorded: this repo keeps its own tools. No config file was added or changed."
        )
        print(
            "Commands recorded: "
            + (
                "; ".join(f"{s}: {' · '.join(c)}" for s, c in found.items())
                or "none found"
            )
            + '. Check them with the user; correct with: groundwork.py quality set step="command"'
        )
        return
    # set: step=command (repeat a step to give several commands; step= clears it)
    if current is None:
        raise SystemExit(
            "Record a decision first: groundwork.py quality init  (standard) or  quality keep  (own tools)."
        )
    if not a.assign:
        raise SystemExit(
            'nothing to set: give step="command" pairs (flags such as --fix go after them)'
        )
    entry = dict(raw)
    key = "fix" if a.fix else "commands"
    table = {k: Q._cmds(v) for k, v in (entry.get(key) or {}).items()}
    seen: set[str] = set()
    for item in a.assign:
        step, sep, cmd = item.partition("=")
        if not sep or step not in Q.STEPS:
            raise SystemExit(
                f"expected step=command with step one of {', '.join(Q.STEPS)}; got {item!r}"
            )
        if step not in seen:
            table[step], seen = [], seen | {step}
        if cmd.strip():
            table[step].append(cmd.strip())
    entry[key] = {k: v for k, v in table.items() if v}
    C.write_config(repo, quality=entry)
    Q.ensure_agents_section(repo, Q.load(repo))
    a.action = "show"
    cmd_quality(a)


def cmd_verify(a) -> None:
    ctx = _repo_ctx("verify command")
    q = Q.load(ctx.repo)
    if q is None:
        raise SystemExit(
            "No code quality decision recorded: groundwork.py quality init  (standard) or  quality keep  (own tools)."
        )
    if q.problems:
        raise SystemExit("Invalid quality entry: " + "; ".join(q.problems))
    results = Q.verify(ctx.repo, a.step or None, a.fix)
    if not results:
        print(
            "Nothing to verify yet: no code, or no commands recorded (groundwork.py quality set step=CMD)."
        )
        return
    for r in results:
        print(
            f"{'PASS' if r.ok else 'FAIL'}  {r.step:<7} {r.command}  ({r.seconds:.1f}s)"
        )
        if not r.ok and r.tail:
            print("\n".join("        " + ln for ln in r.tail.splitlines()))
    bad = [r for r in results if not r.ok]
    print(
        f"\nverify: {len(results) - len(bad)} passed, {len(bad)} failed"
        + (" — fix them; never weaken a rule to pass." if bad else "")
    )
    raise SystemExit(1 if bad else 0)


def cmd_doctor(a) -> None:
    d = X.diagnose(Path(a.path or Path.cwd()))
    print(json.dumps(X.to_json(d), indent=2) if a.json else X.render(d))


def cmd_mark_workspace(_a) -> None:
    root = Path.cwd()
    C.write_config(
        root,
        level="workspace",
        standard=C.read_config(root).get("standard", C.STANDARD_VERSION),
    )
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
    _write(
        p,
        C.render(
            "RFC.md",
            id=f"RFC-{n:04d}",
            title=a.title or slug.replace("-", " ").title(),
            date=time.strftime("%F"),
            author=C.signer(),
        ),
    )
    P.auto_created(ctx, "rfc", p, a.requested_by)
    print(p)


def cmd_new_feature(a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level not in ("repo", "standalone"):
        raise SystemExit("Features are specced inside a repo. cd into one.")
    rfc = C.find_rfc(ctx, a.rfc)
    if not rfc:
        raise SystemExit(f"RFC '{a.rfc}' not found in {ctx.rfc_home / 'DECISIONS'}")
    if M.ensure(ctx.repo):
        print(f"code map → {M.FILE} (describe each folder in its Holds column)")
    specs = ctx.repo / "specs"
    specs.mkdir(exist_ok=True)
    n = C.next_number([p.name for p in specs.iterdir()], r"(\d+)-")
    slug = f"{n:03d}-{C.slugify(a.slug)}"
    fdir = specs / slug
    fdir.mkdir()
    v = {
        "id": slug,
        "rfc": rfc.stem.split("-")[0] + "-" + rfc.stem.split("-")[1],
        "title": a.slug.replace("-", " ").title(),
        "date": time.strftime("%F"),
        "author": C.signer(),
    }
    for name in ("spec", "plan", "tasks", "evals"):
        _write(fdir / f"{name}.md", C.render(f"{name}.md", **v))
    rel = {
        k: "["
        + ", ".join(x.strip() for x in (getattr(a, k) or "").split(",") if x.strip())
        + "]"
        for k in ("extends", "depends_on", "builds_against", "amends")
    }
    if any(val != "[]" for val in rel.values()):
        sp = fdir / "spec.md"
        sp.write_text(C.set_fm(sp.read_text(encoding="utf-8"), rel), encoding="utf-8")
    rmeta, _ = C.split_fm(rfc.read_text(encoding="utf-8"))
    P.auto_created(
        ctx,
        "feature",
        fdir / "spec.md",
        getattr(a, "requested_by", None) or rmeta.get("requested_by") or None,
    )
    _write(ctx.repo / ".groundwork" / "active", slug + "\n")
    print(f"{fdir}\nActive feature set to {slug}. Owner: {C.signer()}.")


def cmd_check(a) -> None:
    path = Path(a.path or Path.cwd())
    if a.hook:  # called from a git hook: honour the enforcement setting
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
        raise SystemExit(
            "No git repository here (or in this workspace) to install hooks into."
        )
    for repo in repos:
        if a.action == "install":
            notes = H.install(
                repo, strict=a.strict, pre_push=a.pre_push, vendored=a.vendor
            )
        elif a.action == "uninstall":
            notes = H.uninstall(repo)
        else:
            notes = [H.status(repo)]
        print(f"{repo.name}: " + "; ".join(notes))


def cmd_fresh(a) -> None:
    ctx = C.detect(Path(a.path or Path.cwd()))
    rows = F.assess_with_parent(ctx)
    bases = F.assess_baselines(ctx) if ctx.level in ("repo", "standalone") else []
    if a.json:
        print(
            json.dumps(
                [{"doc": d.doc, "status": d.status, "reasons": d.reasons} for d in rows]
                + [
                    {
                        "doc": "baseline:" + b.slug,
                        "status": b.status,
                        "reasons": b.reasons,
                    }
                    for b in bases
                ],
                indent=2,
            )
        )
        return
    if not rows and not bases:
        print("Nothing to assess at this level.")
    for d in rows:
        print(f"{d.status.upper():<11} {d.doc}")
        for why in d.reasons:
            print(f"            - {why}")
    for b in bases:
        print(f"{b.status.upper():<11} baseline specs/{b.slug}")
        for why in b.reasons:
            print(f"            - {why}")
    if any(d.status in ("stale", "unconfirmed") for d in rows):
        print(
            "\nUpdate what changed (refresh skill), then run: groundwork.py confirm <doc>"
        )
    if any(b.status in ("review", "unreviewed") for b in bases):
        print(
            "\nBaselines: read the changed files against the requirements (refresh skill); amend and re-approve "
            "if behaviour changed; then run: groundwork.py confirm --baseline <slug>"
        )


def cmd_confirm(a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level == "unknown":
        raise SystemExit("Not in a repo or workspace.")
    if a.baseline:
        if not a.docs:
            raise SystemExit(
                "confirm --baseline needs the baseline slug(s): NNN-slug …"
            )
        rc = _repo_only("a baseline source review")
        done = F.confirm_baseline(rc, a.docs)
        if BL.load_caps(rc):
            BL.write_index(rc)
        print(
            "Source review recorded for: "
            + ", ".join(done)
            + "\nThis records that the baseline was compared with the files its Evidence table names. "
            "It is not an approval: if requirements changed, the user must /groundwork-specflow:approve again."
        )
        for slug in done:
            review = F.baseline_review(rc, slug)
            if review.status == "review":
                print(f"{slug}: review still needed — " + "; ".join(review.reasons))
        return
    done = F.confirm(ctx, a.docs or None)
    print("Confirmed as matching reality: " + ", ".join(done))


def cmd_board(a) -> None:
    ctx = C.detect(Path(a.path or Path.cwd()))
    items = W.collect(ctx, include_done=a.all)
    print(W.to_json(items) if a.json else W.render(items, BL.review_lines(ctx)))


def _repo_only(what: str) -> C.Ctx:
    ctx = C.detect(Path.cwd())
    if ctx.level not in ("repo", "standalone"):
        raise SystemExit(f"{what} happens inside a repo. cd into one.")
    return ctx


def cmd_adopt_specs(a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level == "unknown":
        raise SystemExit("Not in a repo or workspace.")
    if a.classify:
        rc = _repo_only("classification")
        for line in BL.classify(
            rc, a.classify, a.slugs, dry=a.dry_run, capability=a.capability
        ):
            print(line)
        print(
            (
                "Dry run: nothing changed. "
                if a.dry_run
                else "Classification changes metadata and capability links only. "
            )
            + "A baseline still needs the user's review and "
            "/groundwork-specflow:approve; planned work needs its RFC, plan, tasks and evals."
        )
        return
    if a.capability:
        raise SystemExit(
            "--capability requires --classify; import first, then link the classified spec"
        )
    targets = (
        [C.detect(k, ctx.workspace) for k in C.child_repos(ctx.workspace)]
        if ctx.level == "workspace"
        else [ctx]
    )
    verb = "would import" if a.dry_run else "imported"
    for rc in targets:
        rep = BL.import_specs(rc, a.slugs or None, a.dry_run)
        print(
            f"[{rc.repo.name}] {verb}: "
            + (
                ", ".join(rep["imported"])
                or "nothing (no legacy specs without GroundWork metadata)"
            )
        )
        if a.dry_run:
            for c in BL.candidates(rc):
                if a.slugs and c["slug"] not in a.slugs:
                    continue
                print(
                    f"  - {c['slug']}: '{c['title']}' status={c['original_status'] or '?'} "
                    f"companions={','.join(c['companions']) or 'none'} tasks={c['tasks'][0]}/{c['tasks'][1]} "
                    f"markers={c['markers']} sections differing from the standard={len(c['missing_sections'])}"
                    + (f" PROBLEM: {c['problem']}" if c["problem"] else "")
                    + ("" if c["name_ok"] else " PROBLEM: directory is not NNN-slug")
                )
        for line in rep["review"]:
            print(f"  needs a person: {line}")
        for s in rep["not_found"]:
            print(f"  not found (or already governed): {s}")
        if rep["unfinished"]:
            print(
                "  not marked finished in the original — history or work in flight? the user decides:"
            )
            for line in rep["unfinished"]:
                print(f"    - {line}")
    print(
        "\nImported documents are `origin: imported`, `adoption_state: pending`: references, not approved "
        "requirements. Next: the baseline skill investigates each, then "
        "`groundwork.py adopt-specs --classify baseline|planned|archived <slug>`."
    )


def cmd_new_adr(a) -> None:
    ctx = C.detect(Path.cwd())
    p = AD.new_adr(ctx, a.slug, a.title, a.retrospective, a.rfc, a.source, a.decided_at)
    print(
        f"{p}\n"
        + (
            "Retrospective ADR (status recorded): fill §1–5 only as far as the evidence supports; §3 starts with "
            "'**Source:** documented in …' / 'retrospective explanation by …, <date>' / 'historical rationale unknown'."
            if a.retrospective
            else "ADR from an approved RFC: record the outcome; the RFC keeps the interview and alternatives."
        )
    )


def cmd_new_contract(a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level == "repo":
        print(
            f"note: contracts are product-level; writing it in the workspace's CONTRACTS/ ({ctx.workspace})"
        )
    consumers = [c.strip() for c in (a.consumers or "").split(",") if c.strip()]
    p = CT.new_contract(ctx, a.slug, a.title, a.provider, consumers, a.as_built)
    print(
        f"{p}\n"
        + (
            "As-built contract (origin: baseline): fill it from the provider's code and docs, cite the evidence, "
            "name provider_reviewer and consumer_reviewers, then each reviewer approves it."
            if a.as_built
            else "Planned contract: fill it from the api RFC's §8, name the reviewers, then each reviewer approves it."
        )
    )


def cmd_new_baseline(a) -> None:
    rc = _repo_only("a baseline")
    fdir = BL.new_baseline(rc, a.slug, a.title, a.capability)
    P.auto_created(rc, "feature", fdir / "spec.md", None)
    print(
        f"{fdir}\nBaseline created (spec.md only). Owner: {C.signer()}. Active work unchanged: a baseline "
        "is documentation of existing behaviour, not an implementation target."
    )


def cmd_capability(a) -> None:
    rc = _repo_only("capabilities")
    if a.action == "set":
        fields = {}
        for item in a.args:
            if "=" not in item:
                raise SystemExit(f"set takes field=value pairs, not '{item}'")
            k, v = item.split("=", 1)
            fields[k.strip()] = v.strip()
        rec = BL.cap_set(rc, a.cap, **fields)
    elif a.action == "link":
        if len(a.args) != 1:
            raise SystemExit("usage: capability link <cap> <NNN-slug>")
        if not (rc.repo / "specs" / a.args[0] / "spec.md").is_file():
            raise SystemExit(f"specs/{a.args[0]}/spec.md does not exist")
        rec = BL.cap_link(rc, a.cap, a.args[0], create=True)
    else:
        if len(a.args) != 1:
            raise SystemExit("usage: capability unlink <cap> <NNN-slug>")
        rec = BL.cap_unlink(rc, a.cap, a.args[0])
    BL.write_index(rc)
    print(json.dumps({C.slugify(a.cap): rec}, indent=2))


def cmd_capabilities(a) -> None:
    rc = _repo_only("the capability table")
    p = BL.write_index(rc)
    st, _ = BL.index_state(rc)
    print(
        f"{p} ({st}); {len(BL.load_caps(rc))} capabilit{'y' if len(BL.load_caps(rc)) == 1 else 'ies'}"
    )


def cmd_note(a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level == "unknown":
        raise SystemExit("Not in a repo or workspace.")
    print("noted in " + str(W.add_note(ctx, " ".join(a.text))))


def cmd_deps(a) -> None:
    ctx = C.detect(Path.cwd())
    ref = a.ref or C.active_slug(ctx)
    if not ref:
        raise SystemExit(
            "Give a feature (NNN-slug or repo/NNN-slug) or an RFC id, or activate a feature first."
        )
    print(R.describe(ctx, ref))


def cmd_record(a) -> None:
    ctx = C.detect(Path.cwd())
    who = [w.strip() for w in a.who.split(",") if w.strip()] if a.who else None
    e = P.record(
        ctx,
        a.event,
        a.ref,
        by=a.by,
        via=a.via,
        who=who,
        env=a.env,
        version=a.version,
        text=a.text or "",
    )
    print(
        f"recorded {e['event']} on {e['ref']} by {e['by']}"
        + (f" → {', '.join(who)}" if who else "")
        + (f" ({e['env']} {e['version']})" if e.get("env") else "")
    )


def cmd_who(a) -> None:
    ctx = C.detect(Path(a.path or Path.cwd()))
    if a.all:
        print(P.table(ctx))
    elif a.person:
        print(P.person_items(ctx, a.person))
    else:
        ref = a.ref or C.active_slug(ctx)
        if not ref:
            raise SystemExit(
                "Give a feature (NNN-slug / repo/NNN-slug), RFC-000N or bugs/NNN-slug; or --person NAME; or --all."
            )
        print(P.describe(ctx, ref))


def cmd_new_bug(a) -> None:
    ctx = C.detect(Path.cwd())
    if ctx.level not in ("repo", "standalone"):
        raise SystemExit(
            "Bugs are recorded inside a repo. cd into the repo that has the bug."
        )
    if M.ensure(ctx.repo):
        print(f"code map → {M.FILE} (describe each folder in its Holds column)")
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
        raise SystemExit(
            f"spec.md is {spec.status}; plan/tasks/evals can only be synced to an APPROVED spec."
        )
    h = C.body_hash((fdir / "spec.md").read_text(encoding="utf-8"))
    done = []
    for name in ("plan", "tasks", "evals"):
        f = fdir / f"{name}.md"
        if f.is_file() and not C.PLACEHOLDER.search(f.read_text(encoding="utf-8")):
            f.write_text(
                C.set_fm(f.read_text(encoding="utf-8"), {"spec_version": h}),
                encoding="utf-8",
            )
            done.append(name + ".md")
    print(
        "Pinned to the current approved spec: "
        + (", ".join(done) or "nothing (no finished documents yet)")
    )


def cmd_activate(a) -> None:
    ctx = C.detect(Path.cwd())
    if not ctx.repo:
        raise SystemExit("Not in a repo.")
    if not (ctx.repo / "specs" / a.slug).is_dir():
        raise SystemExit(f"specs/{a.slug} does not exist")
    meta = C.spec_meta(ctx.repo / "specs" / a.slug)
    if C.origin(meta):
        st = C.feature_steps(ctx, a.slug)[0]
        raise SystemExit(
            f"specs/{a.slug} is {'a baseline' if C.is_baseline(meta) else 'an imported legacy spec'}: "
            f"{st.detail}. It cannot be the active implementation target. "
            + C.INSTRUCTIONS.get(st.key if not st.ok else "baseline", "")
        )
    if M.ensure(ctx.repo):
        print(f"code map → {M.FILE} (describe each folder in its Holds column)")
    _write(ctx.repo / ".groundwork" / "active", a.slug + "\n")
    print(f"Active feature: {a.slug}")


def main() -> None:
    for stream in (
        sys.stdin,
        sys.stdout,
        sys.stderr,
    ):  # Windows defaults to a legacy code page
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass
    ap = argparse.ArgumentParser(prog="groundwork")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n, fn in (
        ("session-context", cmd_session_context),
        ("prompt-reminder", cmd_prompt_reminder),
        ("gate", cmd_gate),
        ("gate-bash", cmd_gate_bash),
        ("skill-notice", cmd_skill_notice),
        ("stop-brevity", cmd_stop_brevity),
        ("alert-stop", cmd_alert_stop),
        ("alert-question", cmd_alert_question),
        ("scaffold", cmd_scaffold),
        ("mark-workspace", cmd_mark_workspace),
    ):
        sub.add_parser(n).set_defaults(fn=fn)
    p = sub.add_parser("status")
    p.add_argument("path", nargs="?")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("approve")
    p.add_argument(
        "docs",
        nargs="+",
        help="one or more documents; all are checked before any is recorded",
    )
    p.add_argument("--as", dest="who")
    p.set_defaults(fn=cmd_approve)
    p = sub.add_parser(
        "adopt-specs",
        help="bring legacy spec directories under GroundWork metadata (origin: imported), or classify them",
    )
    p.add_argument(
        "slugs", nargs="*", help="NNN-slug directories (default: every candidate)"
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--classify", choices=BL.CLASSIFICATIONS)
    p.add_argument(
        "--capability",
        help="capability to link when classifying (existing links are kept)",
    )
    p.set_defaults(fn=cmd_adopt_specs)
    p = sub.add_parser(
        "new-adr",
        help="an ADR in DECISIONS/: after a built RFC (--rfc), or retrospective for a choice found in existing code",
    )
    p.add_argument("slug")
    p.add_argument("--title")
    p.add_argument("--rfc", help="the approved RFC this records the outcome of")
    p.add_argument(
        "--retrospective",
        action="store_true",
        help="a decision found in the codebase, no RFC",
    )
    p.add_argument(
        "--source",
        help="document or commit that states the reason (sets rationale_source: documented)",
    )
    p.add_argument(
        "--decided-at", dest="decided_at", help="date, only when a document states it"
    )
    p.set_defaults(fn=cmd_new_adr)
    p = sub.add_parser(
        "new-contract",
        help="a contract in CONTRACTS/ with named provider/consumer reviewers (--as-built: observed, not designed)",
    )
    p.add_argument("slug", help="<provider>-<topic>")
    p.add_argument("--title")
    p.add_argument("--provider")
    p.add_argument("--consumers", help="comma-separated repo or system names")
    p.add_argument("--as-built", dest="as_built", action="store_true")
    p.set_defaults(fn=cmd_new_contract)
    p = sub.add_parser(
        "new-baseline", help="a spec for behaviour that already exists (spec.md only)"
    )
    p.add_argument("slug")
    p.add_argument("--title")
    p.add_argument(
        "--capability", help="capability slug to link (default: the spec's own slug)"
    )
    p.set_defaults(fn=cmd_new_baseline)
    p = sub.add_parser(
        "capability",
        help="capability records: set field=value …, link <spec>, unlink <spec>",
    )
    p.add_argument("action", choices=["set", "link", "unlink"])
    p.add_argument("cap")
    p.add_argument("args", nargs="*")
    p.set_defaults(fn=cmd_capability)
    p = sub.add_parser(
        "capabilities",
        help="regenerate the capability table in specs/README.md (Notes kept)",
    )
    p.set_defaults(fn=cmd_capabilities)
    p = sub.add_parser("bypass")
    p.add_argument("reason", nargs="+")
    p.add_argument("--minutes", type=int, default=60)
    p.set_defaults(
        fn=lambda a: cmd_bypass(
            argparse.Namespace(reason=" ".join(a.reason), minutes=a.minutes)
        )
    )
    p = sub.add_parser("new-rfc")
    p.add_argument("slug")
    p.add_argument("--title")
    p.add_argument("--requested-by")
    p.set_defaults(fn=cmd_new_rfc)
    p = sub.add_parser("new-feature")
    p.add_argument("slug")
    p.add_argument("--rfc", required=True)
    p.add_argument("--requested-by")
    for k in ("extends", "depends-on", "builds-against", "amends"):
        p.add_argument("--" + k, help="comma-separated NNN-slug or repo/NNN-slug")
    p.set_defaults(fn=cmd_new_feature)
    p = sub.add_parser("hooks")
    p.add_argument("action", choices=["install", "uninstall", "status"])
    p.add_argument(
        "--strict",
        action="store_true",
        help="warnings (unfinished/stale docs) also block",
    )
    p.add_argument(
        "--pre-push", action="store_true", help="also install a pre-push hook"
    )
    p.add_argument(
        "--vendor",
        action="store_true",
        help="copy the engine into .groundwork/engine/ so teammates/CI need no plugin",
    )
    p.set_defaults(fn=cmd_hooks)
    p = sub.add_parser("check")
    p.add_argument("path", nargs="?")
    p.add_argument("--json", action="store_true")
    p.add_argument("--hook", action="store_true", help=argparse.SUPPRESS)
    p.add_argument(
        "--strict", action="store_true", help="warnings (unfinished docs) also fail"
    )
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser(
        "init", help="onboard this project: classify, scaffold, gather evidence"
    )
    p.add_argument(
        "--as",
        dest="as_",
        choices=["repo", "workspace"],
        help="for a directory that is neither yet",
    )
    p.add_argument(
        "--retrofit",
        action="store_true",
        help="append missing required sections to existing foundation docs",
    )
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_init)
    p = sub.add_parser(
        "quality",
        help="the repo's code quality toolchain: show, init (standard), keep (own tools), set, ignore (keep prettier off GroundWork's documents)",
    )
    p.add_argument(
        "action",
        nargs="?",
        default="show",
        choices=["show", "init", "keep", "set", "ignore"],
    )
    p.add_argument(
        "assign", nargs="*", help='set: step="command", e.g. test="uv run pytest -q"'
    )
    p.add_argument("--create", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument(
        "--fix",
        action="store_true",
        help="set: record fix commands instead of check commands",
    )
    p.set_defaults(fn=cmd_quality)
    p = sub.add_parser(
        "verify",
        help="run the repo's format, lint, type and test commands; exit 1 if any fails",
    )
    p.add_argument(
        "--fix",
        action="store_true",
        help="run the fix commands first (formatter, lint autofix)",
    )
    p.add_argument("--step", action="append", choices=Q.STEPS)
    p.set_defaults(fn=cmd_verify)
    p = sub.add_parser(
        "codemap",
        help="write CODEMAP.md: where each kind of code lives (kept: Holds column, Notes)",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="exit 1 unless the map is current and finished",
    )
    p.set_defaults(fn=cmd_codemap)
    p = sub.add_parser(
        "layout",
        help="the repo's code layout: show, init (standard), keep (own structure), map",
    )
    p.add_argument(
        "action", nargs="?", default="show", choices=["show", "init", "keep", "map"]
    )
    p.add_argument(
        "assign", nargs="*", help="map: role=path, e.g. connectors=src/app/clients"
    )
    p.add_argument("--profile", choices=sorted(L.PROFILES))
    p.add_argument("--root")
    p.add_argument("--create", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--legacy", action="append", default=[])
    p.add_argument("--wiring", action="append", default=[])
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_layout)
    p = sub.add_parser("doctor", help="how far is this project from the standard?")
    p.add_argument("path", nargs="?")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_doctor)
    p = sub.add_parser("fresh")
    p.add_argument("path", nargs="?")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_fresh)
    p = sub.add_parser("confirm")
    p.add_argument(
        "docs", nargs="*", help="foundation docs, or baseline slugs with --baseline"
    )
    p.add_argument(
        "--baseline",
        action="store_true",
        help="record a source review of the named baseline(s): snapshots the files their Evidence tables cite",
    )
    p.set_defaults(fn=cmd_confirm)
    p = sub.add_parser("board", help="everything in flight, for resuming")
    p.add_argument("path", nargs="?")
    p.add_argument("--all", action="store_true", help="include finished work")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_board)
    p = sub.add_parser("note", help="record where work stopped")
    p.add_argument("text", nargs="+")
    p.set_defaults(fn=cmd_note)
    p = sub.add_parser(
        "deps", help="relations and downstream impact of a feature or RFC"
    )
    p.add_argument("ref", nargs="?")
    p.set_defaults(fn=cmd_deps)
    p = sub.add_parser("impact")
    p.add_argument("ref", nargs="?")
    p.set_defaults(fn=cmd_deps)
    p = sub.add_parser(
        "record",
        help="record who did what: requested/owner/implemented/deployed/support/handover/reported/fixed",
    )
    p.add_argument("event", choices=sorted(P.EVENTS))
    p.add_argument("--ref", required=True)
    p.add_argument(
        "--by", help="the person (default: git identity; CI passes its actor)"
    )
    p.add_argument("--via", help="tool used, e.g. claude-code")
    p.add_argument("--who", help="comma-separated people the event assigns")
    p.add_argument("--env")
    p.add_argument("--version")
    p.add_argument("--text")
    p.set_defaults(fn=cmd_record)
    p = sub.add_parser(
        "who",
        help="who requested / owns / implemented / deployed / supports it — and whom to contact",
    )
    p.add_argument("ref", nargs="?")
    p.add_argument("--person")
    p.add_argument("--all", action="store_true")
    p.add_argument("--path")
    p.set_defaults(fn=cmd_who)
    p = sub.add_parser("new-bug")
    p.add_argument("slug")
    p.add_argument("--title")
    p.add_argument("--reported-by")
    p.set_defaults(fn=cmd_new_bug)
    p = sub.add_parser("activate-bug")
    p.add_argument("slug")
    p.set_defaults(fn=cmd_activate_bug)
    p = sub.add_parser(
        "plan-sync", help="record that plan/tasks/evals match the current approved spec"
    )
    p.set_defaults(fn=cmd_plan_sync)
    p = sub.add_parser(
        "alerts", help="sound and voice when the agent waits for you (your own setting)"
    )
    p.add_argument("state", nargs="?", choices=["on", "off", "status", "test", "voice"])
    p.add_argument("value", nargs="?", choices=["on", "off"], help="with `voice`")
    p.set_defaults(fn=cmd_alerts)
    p = sub.add_parser("activate")
    p.add_argument("slug")
    p.set_defaults(fn=cmd_activate)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
