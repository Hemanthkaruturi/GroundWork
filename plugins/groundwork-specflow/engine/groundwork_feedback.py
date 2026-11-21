"""Feedback about GroundWork itself, ready to send as a GitHub issue that the person files themselves.

GroundWork never sends anything. It writes a draft to ~/.groundwork/feedback/ (outside every project, so it is
never committed) and prints a link to GroundWork's issue form with every field filled in. The person reads the
draft, opens the link and presses Submit, or does nothing. Their own work may live on GitLab or anywhere else;
the link only needs a browser.

The report holds no project details, by construction rather than by trust:
- the facts GroundWork adds itself come from a fixed list (version, harness, OS, Python, the GroundWork
  command, check code, and for a crash the engine's own file and line numbers, never the error message);
- the free text the agent writes is scrubbed against what GroundWork knows is private here (project, repo and
  workspace paths and names, the git identity, people in PROJECT.md, feature, RFC and bug names)
  and against general shapes (emails, URLs, paths, code file names, keys, IP addresses, code blocks). Git remote URLs are
  never read (they can hold credentials); a remote's name usually matches the folder name, which is scrubbed.

    groundwork.py feedback --title T --happened TEXT [--expected TEXT] [--where W] [--user-words TEXT]
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import platform
import re
import socket
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, urlencode

import groundwork_alert as A
import groundwork_core as C
import groundwork_host as G
import groundwork_secrets as S

REPO_URL = "https://github.com/Hemanthkaruturi/GroundWork"
FORM = (
    "groundwork-feedback.yml"  # .github/ISSUE_TEMPLATE/ in GroundWork's own repository
)
MAX_URL = 7500  # browsers and GitHub cope with ~8k; leave room
MAX_FIELD = 1500
HOSTS = {"claude": "Claude Code", "codex": "Codex", "devin": "Devin"}

# GroundWork's own vocabulary: never treated as a private name, even if a project happens to use it.
OWN_WORDS = {
    "groundwork",
    "specflow",
    "project",
    "architecture",
    "constitution",
    "agents",
    "contracts",
    "decisions",
    "specs",
    "spec",
    "plan",
    "tasks",
    "evals",
    "handover",
    "rfc",
    "adr",
    "bug",
    "bugs",
    "feature",
    "workspace",
    "repo",
    "approve",
    "bypass",
    "change",
    "status",
    "check",
    "doctor",
    "board",
    "engine",
    "skills",
    "hooks",
    "templates",
    "commands",
    "main",
    "master",
    "src",
    "app",
    "home",
    "user",
    "users",
    "projects",
    "code",
    "work",
    "test",
    "tests",
    "docs",
}
OWN_PATH = re.compile(
    r"^(?:\$\{?CLAUDE_PLUGIN_ROOT\}?|<engine path>|engine|skills|templates|hooks|commands|\.groundwork|"
    r"\.claude-plugin|\.devin-plugin|\.codex/groundwork|\.devin/groundwork)(?:/|$)"
)
OWN_FILE = re.compile(
    r"^(?:groundwork(?:_[a-z]+)?\.py|plugin\.json|hooks\.json|config\.json|approvals\.json|bypass\.json)$"
)

CODE_EXT = (
    "py|pyi|js|jsx|mjs|cjs|ts|tsx|go|rs|java|kt|kts|scala|rb|php|cs|fs|c|h|cc|cpp|hpp|m|mm|swift|dart|lua|"
    "sh|bash|zsh|ps1|sql|vue|svelte|html|css|scss|json|yaml|yml|toml|ini|env|tf|proto|graphql|ex|exs|erl|clj|r"
)
# (kind, pattern, placeholder). Whole tokens that may contain names go before the known names; paths and files
# after them, so a known project root is caught as a path before the generic shape sees it.
FIRST = 5  # code, key, email, url, ip address
SHAPES = [
    ("code", re.compile(r"```.*?(?:```|\Z)", re.DOTALL), "<code removed>"),
    ("key", re.compile("|".join(p.pattern for _, p in S.KEY_PATTERNS)), "<key>"),
    ("email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "<email>"),
    (
        "url",
        re.compile(r"\b(?:https?|ssh|git|ftp)://[^\s)>\]]+|\bgit@[\w.-]+:[^\s)>\]]+"),
        "<url>",
    ),
    ("ip address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<ip>"),
    (
        "path",
        re.compile(r"(?<![\w$}])(?:[A-Za-z]:[\\/]|\\\\|~[\\/]|/)[^\s`'\"<>|,;)\]]+"),
        "<path>",
    ),
    (  # relative: a file in a folder (`src/app.py`), or two folders deep (`apps/web/billing`)
        "path",
        re.compile(
            r"(?<![\w/.$}<-])(?:(?:[\w.-]+[\\/])+[\w-]+\.[A-Za-z0-9]{1,8}\b|(?:[\w.-]+[\\/]){2,}[\w.-]+)"
        ),
        "<path>",
    ),
    (
        "file name",
        re.compile(rf"(?<![\w/.<-])[\w-]+\.(?:{CODE_EXT})\b", re.IGNORECASE),
        "<file>",
    ),
    ("commit", re.compile(r"\b[0-9a-f]{12,40}\b"), "<commit>"),
]


@dataclass
class Scrubbed:
    text: str
    removed: dict[str, int] = field(default_factory=dict)

    def add(self, kind: str, n: int) -> None:
        if n:
            self.removed[kind] = self.removed.get(kind, 0) + n


# --- what is private here -------------------------------------------------------------


def _git(args: list[str], cwd: Path | None) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _title(p: Path) -> str:
    """The first `# ` heading of a document, or of a folder's first document (spec.md, bug.md …)."""
    if p.is_dir():
        docs = sorted(p.glob("*.md"), key=lambda d: d.name != "spec.md")
        if not docs:
            return ""
        p = docs[0]
    try:
        with p.open(encoding="utf-8") as f:
            for line in f.read(4000).splitlines():
                if line.startswith("# "):
                    return line[2:].strip()
    except OSError:
        pass
    return ""


def _slug_words(name: str) -> list[str]:
    """`003-billing-export` -> the slug itself and its words as a phrase: `billing-export`, `billing export`."""
    bare = re.sub(r"^(?:RFC-|ADR-)?\d+[-_]", "", Path(name).stem, flags=re.IGNORECASE)
    return [name, Path(name).stem, bare, bare.replace("-", " ").replace("_", " ")]


# Words too common to be a company or product name, when a project's own name is split into words.
COMMON_WORDS = {
    "the", "and", "for", "with", "api", "web", "app", "apps", "service", "services", "server", "client",
    "core", "lib", "libs", "common", "shared", "frontend", "backend", "platform", "new", "old", "data",
}  # fmt: skip


def _words(name: str) -> set[str]:
    """`Acme Ledger — acme-billing` -> {Acme, Ledger, acme, billing}: a company or product name also appears alone."""
    return {
        w
        for w in re.split(r"[^\w]+|_", name or "")
        if len(w) >= 3 and not w.isdigit() and w.lower() not in COMMON_WORDS
    }


def _add_project_terms(ctx: C.Ctx, terms: dict[str, set[str]]) -> None:
    """People, features, RFCs, bugs and repos. Each source on its own: one broken document must not
    stop the others being read, nor stop the person giving feedback."""
    import groundwork_bugs as B
    import groundwork_people as P

    with contextlib.suppress(Exception):
        for person in P.people(ctx):
            terms["person"] |= {person.name, *re.split(r"[\s,;<>()]+", person.contact)}
    names = terms["project name"]
    # Repos and the project itself carry company and product names: their single words count too.
    # Feature, RFC and bug names are mostly ordinary words ("invoice export"), so only the whole name counts.
    with contextlib.suppress(Exception):
        for repo in C.child_repos(ctx.root):
            names |= {repo.name} | _words(repo.name)
    with contextlib.suppress(Exception):
        t = _title(C._find_ci(ctx.workspace or ctx.repo or ctx.root, "PROJECT.md"))
        names |= {t} | _words(t)
    sources = (
        lambda: C.feature_dirs(ctx),
        lambda: [d.path for d in C.rfcs(ctx)],
        lambda: sorted(B.bugs_dir(ctx).iterdir()),
    )
    for source in sources:
        with contextlib.suppress(Exception):
            for p in source():
                names |= set(_slug_words(p.name))
                t = _title(p)
                if t:
                    names.add(re.sub(r"^(?:RFC|ADR)-\d+[:\s—-]*", "", t))


def private_terms(ctx: C.Ctx | None) -> dict[str, set[str]]:
    """Every name GroundWork can see that identifies this person, their company or their project."""
    terms: dict[str, set[str]] = {"path": set(), "project name": set(), "person": set()}
    home = Path.home()
    places = [home, Path.cwd()]
    if ctx:
        places += [p for p in (ctx.root, ctx.workspace, ctx.repo) if p]
    for p in places:
        try:
            p = p.resolve()
        except OSError:
            pass
        terms["path"] |= {str(p), p.as_posix()}
        if p != home:
            terms["project name"] |= {p.name} | _words(p.name)
    terms["person"] |= {
        home.name,
        os.environ.get("USER", ""),
        os.environ.get("USERNAME", ""),
    }
    try:
        terms["project name"].add(socket.gethostname())
    except OSError:
        pass
    repo = (ctx.repo or ctx.root) if ctx else None
    for key in ("user.name", "user.email"):
        terms["person"].add(_git(["config", key], repo))
    if ctx:
        _add_project_terms(ctx, terms)
    people = terms[
        "person"
    ]  # "Jane Rivera" is also "Jane" and "Rivera"; "jane.r@x" is also "jane.r"
    people |= {
        part
        for t in list(people)
        for part in re.split(r"[\s@]+", t)[: 1 if "@" in t else None]
    }
    return {
        kind: {
            t.strip()
            for t in ts
            if t and len(t.strip()) >= 3 and t.strip().lower() not in OWN_WORDS
        }
        for kind, ts in terms.items()
    }


# --- scrubbing --------------------------------------------------------------------------


def _shape_sub(kind: str, pat: re.Pattern, ph: str, out: Scrubbed) -> None:
    def repl(m: re.Match) -> str:
        s = m.group(0)
        if kind == "path" and (
            OWN_PATH.match(s) or s.startswith("/groundwork-specflow:")
        ):
            return s
        if kind == "path" and re.fullmatch(
            r"/[a-z-]+", s
        ):  # a slash command such as /approve
            return s
        if kind == "file name" and OWN_FILE.match(s):
            return s
        if kind == "url" and s.startswith(REPO_URL):
            return s
        out.add(kind, 1)
        return ph

    out.text = pat.sub(repl, out.text)


def scrub(text: str, terms: dict[str, set[str]] | None = None) -> Scrubbed:
    out = Scrubbed(text or "")
    for kind, pat, ph in SHAPES[:FIRST]:
        _shape_sub(kind, pat, ph, out)
    if terms:  # longest first, so `/home/ann/shop` goes before `shop`
        flat = sorted(
            ((t, kind) for kind, ts in terms.items() for t in ts),
            key=lambda x: -len(x[0]),
        )
        for t, kind in flat:
            pat = re.compile(r"(?<![\w])" + re.escape(t) + r"(?![\w])", re.IGNORECASE)
            out.text, n = pat.subn(f"<{kind.split()[-1]}>", out.text)
            out.add(kind, n)
    for kind, pat, ph in SHAPES[FIRST:]:
        _shape_sub(kind, pat, ph, out)
    # `<path>/specs/<name>/spec.md` once a known root and a slug were replaced: one placeholder is enough
    out.text = re.sub(
        r"(?:<(?:name|person)>)?<path>(?:<(?:path|name|person|file)>|[\\/\w.-])*",
        "<path>",
        out.text,
    )
    return out


# --- the report ---------------------------------------------------------------------


def version() -> str:
    try:
        return json.loads(
            (C.PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )["version"]
    except (OSError, ValueError, KeyError):
        pass
    try:  # setup/install.py copies only the engine and writes this file next to it
        text = (C.PLUGIN_ROOT.parent / "groundwork-version").read_text(encoding="utf-8")
        m = re.search(r"^version=(\S+)", text, re.MULTILINE)
        return m.group(1) if m else "unknown"
    except OSError:
        return "unknown"


def environment() -> str:
    osname = platform.system() or sys.platform
    if osname == "Linux" and A.is_wsl():
        osname = "Linux (WSL)"
    return f"{osname} {platform.machine()}, Python {platform.python_version()}".strip()


FIELDS = (  # issue form field id, heading in the draft
    ("version", "GroundWork version"),
    ("platform", "Agent"),
    ("environment", "System"),
    ("where", "Where in GroundWork"),
    ("what-happened", "What happened"),
    ("expected", "What was expected"),
    ("user-words", "In the user's own words"),
    ("details", "Details"),
)


@dataclass
class Report:
    title: str
    fields: dict[str, str]
    removed: dict[str, int]

    def fingerprint(self) -> str:
        key = "|".join(self.fields.get(k, "") for k in ("version", "where", "details"))
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]

    def markdown(self) -> str:
        lines = [f"# {self.title}", ""]
        for fid, head in FIELDS:
            if self.fields.get(fid):
                lines += [f"## {head}", "", self.fields[fid], ""]
        lines += [f"<!-- groundwork-feedback {self.fingerprint()} -->", ""]
        return "\n".join(lines)

    def url(self) -> str:
        fields = {k: v for k, v in self.fields.items() if v}
        shortened = False
        while True:
            params = {"template": FORM, "title": self.title, **fields}
            url = f"{REPO_URL}/issues/new?" + urlencode(params, quote_via=quote)
            if len(url) <= MAX_URL:
                return url
            longest = max(fields, key=lambda k: len(fields[k]))
            if len(fields[longest]) < 200:
                return f"{REPO_URL}/issues/new?" + urlencode(
                    {"template": FORM, "title": self.title}, quote_via=quote
                )
            note = (
                ""
                if shortened
                else " … (shortened; the full text is in the draft file)"
            )
            fields[longest] = (
                fields[longest][: len(fields[longest]) * 2 // 3].rstrip() + note
            )
            shortened = True


def _clip(s: str) -> str:
    s = (s or "").strip()
    return s if len(s) <= MAX_FIELD else s[:MAX_FIELD].rstrip() + " …"


def build(
    title: str,
    happened: str,
    expected: str = "",
    where: str = "",
    user_words: str = "",
    details: str = "",
    host: str | None = None,
    ctx: C.Ctx | None = None,
) -> Report:
    try:
        terms = private_terms(ctx)
    except Exception:  # noqa: BLE001 -- shapes still apply
        terms = {}
    removed: dict[str, int] = {}

    def clean(s: str) -> str:
        r = scrub(_clip(s), terms)
        for k, n in r.removed.items():
            removed[k] = removed.get(k, 0) + n
        return r.text

    host = host or G.name()
    if (
        host == "claude" and G.BOOTSTRAPPED
    ):  # a .devin/ project install; Devin's shell sets no Devin variables
        host = "devin"
    fields = {
        "version": version(),
        "platform": HOSTS.get(host, host),
        "environment": environment(),
        "where": clean(where),
        "what-happened": clean(happened),
        "expected": clean(expected),
        "user-words": clean(user_words),
        "details": clean(details),
    }
    t = clean(title)[:100] or "GroundWork did not work as expected"
    return Report(f"[feedback] {t}", fields, removed)


def feedback_dirs() -> list[Path]:
    """~/.groundwork/feedback, else the system temp folder: Codex's default sandbox cannot write to home.
    Never a folder inside the project, so a draft is never committed."""
    return [
        A.user_dir() / "feedback",
        Path(tempfile.gettempdir()) / "groundwork-feedback",
    ]


def save(rep: Report, name: str | None = None) -> Path:
    name = name or time.strftime("%Y-%m-%d-%H%M%S") + ".md"
    text = rep.markdown() + f"\nSend it: {rep.url()}\n"
    for d in feedback_dirs():
        try:
            d.mkdir(parents=True, exist_ok=True)
            (d / name).write_text(text, encoding="utf-8")
            return d / name
        except OSError:
            continue
    raise OSError("no writable folder for the feedback draft")


def removed_line(removed: dict[str, int]) -> str:
    if not removed:
        return "Nothing private was found in the text."
    bits = ", ".join(
        f"{n} {k}{'s' if n > 1 else ''}" for k, n in sorted(removed.items())
    )
    return f"Removed before saving: {bits} (shown as placeholders such as <path>)."


def announce(rep: Report, path: Path | None) -> str:
    where = (
        path or "not saved (no writable folder); the link below holds the whole report"
    )
    return (
        f"Feedback draft for GroundWork, with no project details: {where}\n"
        f"{removed_line(rep.removed)}\n"
        "Read it first. To send it, open this link: GitHub shows the form already filled in, and nothing is "
        "sent until you press Submit there.\n"
        f"{rep.url()}"
    )


# --- GroundWork noticing its own failure --------------------------------------------------


def crash_report(exc: BaseException, cmd: str) -> Report:
    """Only the exception's type and the engine's own frames: the message can quote the person's files."""
    engine = Path(__file__).resolve().parent
    frames = []
    for fr in traceback.extract_tb(exc.__traceback__):
        try:
            p = Path(fr.filename).resolve()
        except OSError:
            continue
        if p.parent == engine:
            frames.append(f"{p.name}:{fr.lineno} in {fr.name}")
    kind = type(exc).__name__
    details = f"{kind}\n" + "\n".join(f"- {f}" for f in frames[-8:])
    hook = cmd in G_HOOKS
    return build(
        title=f"{kind} in `{cmd}`",
        happened=f"GroundWork stopped with an internal error ({kind}) while running "
        f"`{cmd}`{' (a hook)' if hook else ''}.",
        expected=f"`{cmd}` completes without an internal error.",
        where=f"`groundwork.py {cmd}`" + (" hook" if hook else ""),
        details=details,
    )


G_HOOKS: tuple[
    str, ...
] = ()  # set by groundwork.py, which owns the list of hook commands


def on_crash(exc: BaseException, cmd: str, stream=None) -> None:
    """Called from main() for an unexpected exception. Writes the draft, tells the person, never raises."""
    stream = stream or sys.stderr
    try:
        rep = crash_report(exc, cmd)
        name = f"crash-{rep.fingerprint()}.md"
        seen = any((d / name).exists() for d in feedback_dirs())
        path = save(rep, name)
        if seen:
            stream.write(
                f"\n[groundwork] Internal error again; the feedback draft for it is still at {path}\n"
            )
        else:
            stream.write(
                "\n[groundwork] GroundWork hit an internal error; this is a problem in GroundWork, not in your "
                "project. A feedback report was prepared. Agent: tell the user about it once, briefly.\n"
                + announce(rep, path)
                + "\n"
            )
    except Exception:  # noqa: BLE001, S110 -- reporting must never hide the original error
        pass
