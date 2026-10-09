"""Facts about an existing codebase, gathered without a model.

`groundwork.py init` writes these to `.groundwork/discovery.json` so the agent drafts PROJECT.md /
ARCHITECTURE.md / AGENTS.md from evidence instead of guesses. Everything here is *evidence*:
where a fact came from is always recorded, and nothing is presented as a decision.
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

import groundwork_fresh as F
from groundwork_core import PLACEHOLDER as C_PLACEHOLDER
from groundwork_core import SKIP_DIRS as C_SKIP

LANGS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".swift": "Swift",
    ".c": "C",
    ".cpp": "C++",
    ".scala": "Scala",
    ".sh": "Shell",
    ".sql": "SQL",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".html": "HTML",
    ".css": "CSS",
}
ENTRY_CANDIDATES = [
    "main.py",
    "app.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "index.js",
    "server.js",
    "app.js",
    "main.js",
    "index.ts",
    "main.ts",
    "server.ts",
    "main.go",
    "cmd",
    "src/main.py",
    "src/app.py",
    "src/index.js",
    "src/index.ts",
    "src/main.ts",
    "src/main.rs",
    "src/lib.rs",
    "src/main/java",
    "app/main.py",
    "src/app/main.py",
]
DOC_CANDIDATES = [
    "README.md",
    "README.rst",
    "README",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "docs",
    "doc",
    "ARCHITECTURE.md",
    "PROJECT.md",
    "CLAUDE.md",
    "AGENTS.md",
    ".cursorrules",
]
ADR_DIRS = [
    "docs/adr",
    "docs/adrs",
    "doc/adr",
    "adr",
    "docs/decisions",
    "docs/architecture/decisions",
]
TEST_DIRS = ["tests", "test", "__tests__", "spec", "e2e", "cypress"]


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _safe(repo: Path, rel: str) -> bool:
    """A regular file under the repo, with no symlink anywhere on its path."""
    import groundwork_baseline as BL

    p = repo / rel
    return p.is_file() and BL.path_problem_under(repo, p) is None


def _read(p: Path, limit: int = 200_000) -> str:
    if p.is_symlink():
        return ""
    try:
        return p.read_text(errors="replace", encoding="utf-8")[:limit]
    except OSError:
        return ""


def _package_json(p: Path) -> dict:
    try:
        j = json.loads(_read(p))
    except ValueError:
        return {}
    return {
        "name": j.get("name"),
        "scripts": sorted((j.get("scripts") or {}).keys()),
        "dependencies": sorted((j.get("dependencies") or {}).keys())[:20],
        "devDependencies": sorted((j.get("devDependencies") or {}).keys())[:15],
        "engines": j.get("engines"),
    }


def _pyproject(p: Path) -> dict:
    text = _read(p)
    try:
        import tomllib

        j = tomllib.loads(text)
        proj = j.get("project", {})
        return {
            "name": proj.get("name"),
            "requires-python": proj.get("requires-python"),
            "dependencies": [
                re.split(r"[<>=!~\[; ]", d)[0] for d in proj.get("dependencies", [])
            ][:20],
            "scripts": sorted((proj.get("scripts") or {}).keys()),
            "tools": sorted((j.get("tool") or {}).keys()),
        }
    except Exception:  # noqa: BLE001 — old Python or malformed file: fall back to a hint
        m = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
        return {"name": m.group(1) if m else None}


def _requirements(p: Path) -> dict:
    lines = [
        ln.strip()
        for ln in _read(p).splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    return {"packages": [re.split(r"[<>=!~\[; ]", ln)[0] for ln in lines][:25]}


def _manifest_facts(repo: Path, rel: str) -> dict:
    p, name = repo / rel, Path(rel).name
    if name == "package.json":
        return _package_json(p)
    if name == "pyproject.toml":
        return _pyproject(p)
    if name.startswith("requirements") and name.endswith(".txt"):
        return _requirements(p)
    if name == "go.mod":
        m = re.search(r"^module\s+(\S+)", _read(p), re.MULTILINE)
        return {"module": m.group(1) if m else None}
    if name == "Cargo.toml":
        m = re.search(r'^name\s*=\s*"([^"]+)"', _read(p), re.MULTILINE)
        return {"name": m.group(1) if m else None}
    if name == "Makefile":
        return {
            "targets": sorted(
                set(re.findall(r"^([A-Za-z][\w-]*):(?!=)", _read(p), re.MULTILINE))
            )[:25]
        }
    return {}


# --- surfaces, rules and capability candidates (STANDARD.md §5j; evidence only) ----------
# Regex detection of common frameworks. It finds what it can and SAYS what it cannot see
# (dynamic registration, mounted routers): a starting signal for the baseline interview, never
# proof of a consumer or of complete coverage.

CODE_EXT = {
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".go",
    ".java",
    ".kt",
    ".rb",
    ".php",
    ".cs",
}
ROUTE_PATTERNS = [
    # decorator-style (FastAPI, Flask, Sanic, Litestar): @router.get("/path")
    r'@[\w.]+\.(get|post|put|patch|delete|route|api_route|websocket)\(\s*["\']([^"\']+)',
    # Express / Koa / Hono / Fastify: app.get("/path", …) router.post('/path'
    r'(?<![@.\w])(?:app|router|server|fastify)\.(get|post|put|patch|delete|all)\(\s*["\'`]([^"\'`]+)',
    # Go net/http, chi, gin, echo: HandleFunc("/path", …) r.GET("/path", …)
    r'\.(HandleFunc|Handle|GET|POST|PUT|PATCH|DELETE|Get|Post|Put|Patch|Delete)\(\s*"([^"]+)"',
    # Spring: @GetMapping("/path") @RequestMapping(value = "/path")
    r'@(Get|Post|Put|Patch|Delete|Request)Mapping\(\s*(?:value\s*=\s*)?"([^"]+)"',
    # NestJS: @Get('path')
    r"@(Get|Post|Put|Patch|Delete)\(\s*['\"]([^'\"]*)",
    # Rails routes.rb: get 'path', resources :things
    r"^\s*(get|post|put|patch|delete|resources|resource|namespace)\s+['\":]([\w/:-]+)",
]
MOUNT_PATTERNS = [
    r'APIRouter\(\s*prefix\s*=\s*["\']([^"\']+)',
    r'include_router\([^)]*prefix\s*=\s*["\']([^"\']+)',
    r'Blueprint\([^)]*url_prefix\s*=\s*["\']([^"\']+)',
    r'register_blueprint\([^)]*url_prefix\s*=\s*["\']([^"\']+)',
    r'\bapp\.use\(\s*["\'`]([^"\'`]+)["\'`]\s*,',
    r'\.(?:Mount|Route|Group)\(\s*"([^"]+)"',
]
DYNAMIC_PATTERNS = [
    r"add_api_route\(",
    r"add_url_rule\(",
    r"\.add_route\(",
    r"routes\.MapRoute",
    r"\binclude_router\([^)]*\)",
    r"\bapp\.use\(\s*[A-Za-z_]",
]
CLI_PATTERNS = [
    r'@[\w.]+\.command\(\s*(?:name\s*=\s*)?["\']([\w:-]+)["\']',  # typer/click with a name
    r"@[\w.]+\.command\(\s*\)\s*\n\s*(?:async\s+)?def\s+(\w+)",  # typer/click, function name
    r'add_parser\(\s*["\']([\w:-]+)',  # argparse subcommands
    r'Use:\s*"([\w:-]+)',  # cobra
    r'\.command\(\s*["\']([\w:-]+)',  # commander / yargs
]
SCHEMA_GLOBS = [
    "openapi.*",
    "swagger.*",
    "*/openapi.*",
    "*/swagger.*",
    "*.proto",
    "*/*.proto",
    "*/*/*.proto",
    "*.graphql",
    "*.graphqls",
    "*/*.graphql",
    "*/*/*.graphql",
    "asyncapi.*",
    "*/asyncapi.*",
    "*.avsc",
    "*/*.avsc",
    "schemas/*",
    "schema/*",
]
API_DOC_GLOBS = [
    "API.md",
    "docs/api*.md",
    "docs/*/api*.md",
    "docs/integrations/*",
    "docs/integration/*",
    "docs/*contract*",
    "docs/*/*contract*",
    "CONTRACTS/*.md",
]
RULE_SOURCES = [
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    ".cursorrules",
    "CONSTITUTION.md",
    ".specify/memory/constitution.md",
]
NEGATIVE = re.compile(r"\b(never|not|don't|no)\b", re.IGNORECASE)
GATE_TOOLS = re.compile(
    r"\b(make|npm|pnpm|yarn|pytest|ruff|mypy|pyright|go (?:test|vet)|golangci-lint|cargo|eslint|tsc|prettier|black|flake8|phpunit|rspec|bundle exec|dotnet test|mvn|gradle|uv run)\b"
)
WORKER_DIRS = {
    "workers",
    "worker",
    "jobs",
    "job",
    "tasks",
    "consumers",
    "cron",
    "schedulers",
}
MAX_CODE_FILES = 1500
MAX_RULE_FILES = 40
TEST_FILE = r"(^|/)(tests?|__tests__|spec|e2e|cypress)/|(^|/)(test_[^/]+\.py|[^/]+_test\.(py|go)|[^/]+\.(test|spec)\.[jt]sx?)$"
RULE_BULLET = re.compile(
    r"^\s*(?:[-*]\s+|\d+[.)]\s+)(?:\*\*)?(never|always|do not|don't|must not|must|no |only )",
    re.IGNORECASE,
)
RULE_SENTENCE = re.compile(r"^\s*(?:\*\*)?(Never|Always|Do not|Don't|Must not)\b")


def _path_prefix(path: str) -> str:
    segs = [s for s in path.split("/") if s and not s.startswith(("{", ":", "<", "*"))]
    if not segs:
        return "/"
    if re.fullmatch(r"(v\d+|api|rest)", segs[0], re.IGNORECASE) and len(segs) > 1:
        return "/" + "/".join(segs[:2])
    return "/" + segs[0]


def _surface(repo: Path, files: list) -> dict:
    http_files, cli_files, limits = [], [], set()
    prefixes: Counter = Counter()
    scanned = 0
    for rel, p in files:
        if Path(rel).suffix.lower() not in CODE_EXT and Path(rel).name != "routes.rb":
            continue
        if re.search(TEST_FILE, rel):
            continue  # a test's HTTP calls are not the provider's routes
        scanned += 1
        if scanned > MAX_CODE_FILES:
            limits.add(f"code scan stopped after {MAX_CODE_FILES} files")
            break
        text = _read(p, 300_000)
        if not text:
            continue
        paths: list[str] = []
        ops = 0
        seen_at: set[int] = set()
        for pat in ROUTE_PATTERNS:
            for m in re.finditer(pat, text, re.MULTILINE):
                if m.start() in seen_at:
                    continue  # two patterns matched the same declaration
                seen_at.add(m.start())
                ops += 1
                route = m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1)
                if len(paths) < 12 and route not in paths:
                    paths.append(route)
        mounts = [m.group(1) for pat in MOUNT_PATTERNS for m in re.finditer(pat, text)]
        if mounts or any(re.search(pat, text) for pat in DYNAMIC_PATTERNS):
            limits.add(
                "routes are also registered dynamically or mounted under prefixes; paths may combine at mount time"
            )
        if ops or mounts:
            http_files.append(
                {
                    "file": rel,
                    "operations": ops,
                    "paths": paths,
                    "mounts": sorted(set(mounts))[:6],
                }
            )
            for route in paths:
                prefixes[_path_prefix(route)] += 1
        cmds: list[str] = []
        for pat in CLI_PATTERNS:
            cmds += [m.group(1) for m in re.finditer(pat, text, re.MULTILINE)]
        cmds = [c for c in dict.fromkeys(cmds) if c not in ("main", "cli", "app")]
        if cmds:
            cli_files.append({"file": rel, "commands": cmds[:20]})
    http_files.sort(key=lambda x: -x["operations"])
    schemas = sorted(
        rel for rel, _ in files if any(fnmatch.fnmatch(rel, g) for g in SCHEMA_GLOBS)
    )[:20]
    api_docs = sorted(
        rel for rel, _ in files if any(fnmatch.fnmatch(rel, g) for g in API_DOC_GLOBS)
    )[:20]
    return {
        "http": {
            "files": http_files[:30],
            "prefixes": dict(prefixes.most_common(20)),
            "limits": sorted(limits),
        },
        "cli": {
            "files": cli_files[:20],
            "commands": sorted({c for f in cli_files for c in f["commands"]})[:40],
        },
        "schemas": schemas,
        "api_docs": api_docs,
    }


def _rules(repo: Path, files: list) -> dict:
    sources = [s for s in RULE_SOURCES if _safe(repo, s)]
    sources += [
        rel
        for rel, _ in files
        if rel.startswith("docs/") and rel.endswith(".md") and rel not in sources
    ][:MAX_RULE_FILES]
    cands: list[dict] = []
    seen: set[str] = set()
    for rel in sources:
        for i, ln in enumerate(_read(repo / rel, 200_000).splitlines(), 1):
            if not (RULE_BULLET.match(ln) or RULE_SENTENCE.match(ln)):
                continue
            if C_PLACEHOLDER.search(ln):
                continue  # a template's own example, not a rule the project wrote
            text = re.sub(r"[*`_>]", "", ln).strip(" -*0123456789.)")
            text = re.sub(r"\s+", " ", text)[:200]
            key = re.sub(r"[^a-z0-9 ]", "", text.lower())
            if len(key) < 12 or key in seen:
                continue
            seen.add(key)
            cands.append({"text": text, "source": rel, "line": i})
            if len(cands) >= 40:
                break
        if len(cands) >= 40:
            break
    # possible conflicts: nearly the same words, opposite polarity
    conflicts = []

    def words(c):
        return {
            w
            for w in re.findall(r"[a-z]{4,}", c["text"].lower())
            if w not in {"never", "always", "must", "only", "dont"}
        }

    for i, a in enumerate(cands):
        for b in cands[i + 1 :]:
            wa, wb = words(a), words(b)
            if not wa or not wb:
                continue
            j = len(wa & wb) / len(wa | wb)
            if j >= 0.5 and bool(NEGATIVE.search(a["text"])) != bool(
                NEGATIVE.search(b["text"])
            ):
                conflicts.append(
                    {
                        "a": f"{a['source']}:{a['line']}",
                        "b": f"{b['source']}:{b['line']}",
                    }
                )
    gates: list[dict] = []
    ci_files = [
        rel
        for rel, _ in files
        if rel.startswith(".github/workflows/")
        or Path(rel).name in (".gitlab-ci.yml", "Jenkinsfile")
    ]
    for rel in ci_files[:10]:
        block_indent = (
            None  # inside a `run: |` block scalar: every indented line is a command
        )
        for ln in _read(repo / rel, 100_000).splitlines():
            indent = len(ln) - len(ln.lstrip())
            if block_indent is not None:
                if ln.strip() and indent > block_indent:
                    if GATE_TOOLS.search(ln) and len(gates) < 20:
                        gates.append({"file": rel, "command": ln.strip()[:120]})
                    continue
                block_indent = None
            m = re.match(r"\s*(?:-\s*)?run:\s*(.*)$", ln)
            if not m:
                continue
            cmd = m.group(1).strip()
            if cmd in ("|", ">", "|-", ">-", ""):
                block_indent = indent
            elif GATE_TOOLS.search(cmd) and len(gates) < 20:
                gates.append({"file": rel, "command": cmd[:120]})
    return {
        "candidates": cands,
        "sources": sources[:12],
        "conflicts": conflicts[:10],
        "ci_gates": gates,
    }


def _capability_candidates(repo: Path, surface: dict, files: list) -> list[dict]:
    out: list[dict] = []
    http = surface["http"]
    for prefix, n in http["prefixes"].items():
        slug = re.sub(r"[^a-z0-9]+", "-", prefix.lower()).strip("-") or "root"
        evidence = sorted(
            {
                f["file"]
                for f in http["files"]
                if any(_path_prefix(x) == prefix for x in f["paths"])
            }
        )[:5]
        legacy = bool(re.search(r"(legacy|old|deprecated|v0)", prefix, re.IGNORECASE))
        out.append(
            {
                "slug": slug,
                "title": prefix,
                "kind": "http",
                "evidence": evidence,
                "operations": n,
                "suggested_lifecycle": "legacy" if legacy else "active",
                "uncertainty": "derived from a route prefix; business boundary and consumers unconfirmed",
            }
        )
    for f in surface["cli"]["files"]:
        slug = "cli-" + re.sub(r"[^a-z0-9]+", "-", Path(f["file"]).stem.lower()).strip(
            "-"
        )
        out.append(
            {
                "slug": slug,
                "title": f"CLI: {', '.join(f['commands'][:5])}"
                + (" …" if len(f["commands"]) > 5 else ""),
                "kind": "cli",
                "evidence": [f["file"]],
                "operations": len(f["commands"]),
                "suggested_lifecycle": "active",
                "uncertainty": "derived from command definitions; grouping unconfirmed",
            }
        )
    seen_workers: set[str] = set()
    for rel, _ in files:
        parts = Path(rel).parts
        if (
            len(parts) >= 2
            and Path(rel).suffix.lower() in CODE_EXT
            and any(d in WORKER_DIRS for d in parts[:-1])
        ):
            stem = Path(rel).stem
            if stem.startswith(("__", "test")) or stem in seen_workers:
                continue
            seen_workers.add(stem)
            out.append(
                {
                    "slug": "worker-"
                    + re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-"),
                    "title": f"Background work: {stem}",
                    "kind": "worker",
                    "evidence": [rel],
                    "operations": 1,
                    "suggested_lifecycle": "uncertain",
                    "uncertainty": "a file in a worker/job folder; may be scheduled, queued or dead code",
                }
            )
    return out[:25]


DECISION_DOC = re.compile(
    r"(decision|adr|rationale|research|findings|benchmark|architecture|design|why)",
    re.IGNORECASE,
)
RATIONALE_COMMENT = re.compile(
    r"(?:#|//|/\*|\*|<!--)\s*(.*\b(?:because|we chose|chosen|rationale|decided|deliberately|instead of|rather than|trade-?off|on purpose)\b.*)",
    re.IGNORECASE,
)
DECISION_SUBJECT = re.compile(
    r"^(move|switch|replace|adopt|drop|remove|migrate|use|pin|choose|stop|introduce|put|settle|prefer)\b.*",
    re.IGNORECASE,
)


def _decision_leads(repo: Path, files: list) -> dict:
    """Topic leads for retrospective ADRs. A lead is a place to look, never a decision: only a
    document or a person can supply the reason; a commit subject proves neither reason nor date."""
    docs = sorted(
        rel
        for rel, _ in files
        if rel.lower().endswith((".md", ".rst", ".txt"))
        and (rel.startswith(("docs/", "doc/")) or "/" not in rel)
        and DECISION_DOC.search(Path(rel).stem)
        and Path(rel).name.upper()
        not in (
            "README.MD",
            "ARCHITECTURE.MD",
            "PROJECT.MD",
            "AGENTS.MD",
            "CONSTITUTION.MD",
            "CODEMAP.MD",
        )
    )[:20]
    comments: list[dict] = []
    scanned = 0
    for rel, p in files:
        if Path(rel).suffix.lower() not in CODE_EXT or re.search(TEST_FILE, rel):
            continue
        scanned += 1
        if scanned > MAX_CODE_FILES:
            break
        for i, ln in enumerate(_read(p, 300_000).splitlines(), 1):
            m = RATIONALE_COMMENT.search(ln)
            if m and len(comments) < 20:
                comments.append(
                    {"file": rel, "line": i, "text": m.group(1).strip(" *-/#")[:160]}
                )
        if len(comments) >= 20:
            break
    commits = []
    for ln in _git(repo, "log", "--no-merges", "--format=%as\t%s", "-60").splitlines():
        date, _, subject = ln.partition("\t")
        if DECISION_SUBJECT.match(subject) and len(commits) < 15:
            commits.append({"date": date, "subject": subject[:120]})
    return {
        "docs": docs,
        "comments": comments,
        "commits": commits,
        "note": "leads suggest a topic; the reason comes only from a document or a person, and a commit date is not a decision date",
    }


def _legacy_specs(repo: Path) -> list[dict]:
    import groundwork_baseline as BL
    import groundwork_core as C

    try:
        cands = BL.candidates(C.Ctx("standalone", repo, repo=repo))
    except SystemExit:
        return []
    return [
        {k: (str(v) if k == "path" else v) for k, v in c.items() if k != "foreign_keys"}
        for c in cands
    ][:40]


def discover(repo: Path) -> dict:
    repo = repo.resolve()
    files = list(F._walk(repo))
    ext = Counter(
        LANGS[Path(rel).suffix.lower()]
        for rel, _ in files
        if Path(rel).suffix.lower() in LANGS
    )
    infra = [
        rel
        for rel, _ in files
        if F._matches(rel, F.MANIFESTS | F.INFRA_NAMES, F.INFRA_GLOBS)
    ]
    manifests = {
        rel: _manifest_facts(repo, rel)
        for rel in infra
        if Path(rel).name in F.MANIFESTS and rel.count("/") <= 2
    }
    tests = [d for d in TEST_DIRS if (repo / d).is_dir()]
    test_files = sum(
        1
        for rel, _ in files
        if re.search(
            r"(^|/)(test_[^/]+\.py|[^/]+_test\.(py|go)|[^/]+\.(test|spec)\.[jt]sx?)$",
            rel,
        )
    )
    docs = [d for d in DOC_CANDIDATES if (repo / d).exists()]
    adr = next((d for d in ADR_DIRS if (repo / d).is_dir()), None)
    specs = repo / "specs"
    constitution = next(
        (
            c
            for c in (
                ".specify/memory/constitution.md",
                "constitution.md",
                "CONSTITUTION.md",
            )
            if _safe(repo, c)
        ),
        None,
    )
    py_signals = {
        "uv.lock": "uv",
        "poetry.lock": "poetry",
        "Pipfile": "pipenv",
        "Pipfile.lock": "pipenv",
        "environment.yml": "conda",
        "requirements.txt": "pip",
    }
    has_py = "Python" in ext
    pyproj = _read(repo / "pyproject.toml") if _safe(repo, "pyproject.toml") else ""
    uses_uv = (repo / "uv.lock").exists() or "[tool.uv" in pyproj
    other = sorted(
        {m for f, m in py_signals.items() if m != "uv" and (repo / f).exists()}
        | ({"poetry"} if "[tool.poetry" in pyproj else set())
    )
    authors = []
    for ln in _git(repo, "shortlog", "-sne", "--no-merges", "HEAD").splitlines()[:8]:
        m = re.match(r"\s*(\d+)\s+(.*?)\s*(<[^>]*>)?$", ln)
        if m:
            authors.append({"commits": int(m.group(1)), "name": m.group(2)})
    readme = next(
        (d for d in ("README.md", "README.rst", "README") if (repo / d).is_file()), None
    )
    surface = _surface(repo, files)
    rules = _rules(repo, files)
    legacy = _legacy_specs(repo)
    subjects = [
        s
        for s in _git(repo, "log", "--no-merges", "--format=%s", "-30").splitlines()
        if s
    ]
    return {
        "path": str(repo),
        "name": repo.name,
        "languages": dict(ext.most_common(6)),
        "file_count": len(files),
        "top_level_dirs": F.toplevel(repo),
        "manifests": manifests,
        "infrastructure": sorted(
            rel for rel in infra if Path(rel).name not in F.MANIFESTS
        )[:30],
        "entry_points": [e for e in ENTRY_CANDIDATES if (repo / e).exists()],
        "python": {
            "present": has_py or bool(pyproj),
            "uses_uv": uses_uv,
            "other_managers": other if (has_py or pyproj) else [],
        },
        "tests": {"dirs": tests, "test_files": test_files},
        "existing_docs": docs,
        "readme_head": _read(repo / readme, 1500).strip()
        if readme and _safe(repo, readme)
        else "",
        "adoptable": {
            "adr_dir": adr,
            "constitution": constitution,
            "specs_dir": bool(specs.is_dir() and any(specs.iterdir())),
            "specs": legacy,
            "agent_instructions": [
                f
                for f in ("CLAUDE.md", ".cursorrules", "AGENTS.md")
                if (repo / f).exists()
            ],
        },
        "layout": _layout(repo),
        # Do not read remote URLs: HTTPS remotes can embed passwords or tokens.
        "git": {
            "commits": int(_git(repo, "rev-list", "--count", "HEAD") or 0),
            "first_commit": _git(repo, "log", "--reverse", "--format=%as", "-1")
            or None,
            "last_commit": _git(repo, "log", "-1", "--format=%as") or None,
            "top_authors": authors,
            "recent_subjects": subjects,
        },
        "surface": surface,
        "rules": rules,
        "capability_candidates": _capability_candidates(repo, surface, files),
        "decision_leads": _decision_leads(repo, files),
        "scan": {
            "max_files": 3000,
            "files_seen": len(files),
            "truncated": len(files) >= 3000,
            "excluded": sorted(C_SKIP)
            + ["dot-files", "secret-shaped files", "symlinks"],
            "unsupported": surface["http"]["limits"]
            + [
                "regex detection: no semantic analysis; unlisted frameworks are not seen"
            ],
        },
    }


def _layout(repo: Path) -> dict:
    import groundwork_layout as L

    lay = L.load(repo)
    return {"decided": lay.mode if lay else None, **L.suggest(repo)}


def summarize(d: dict) -> str:
    langs = (
        ", ".join(f"{k} ({v})" for k, v in d["languages"].items())
        or "no source files yet"
    )
    lines = [
        f"  languages:    {langs}",
        f"  manifests:    {', '.join(d['manifests']) or 'none'}",
        f"  infra/CI:     {', '.join(d['infrastructure'][:6]) or 'none'}",
        f"  entry points: {', '.join(d['entry_points']) or 'none found'}",
        f"  tests:        {d['tests']['test_files']} test file(s)"
        + (f" in {', '.join(d['tests']['dirs'])}" if d["tests"]["dirs"] else ""),
        f"  docs found:   {', '.join(d['existing_docs']) or 'none'}",
    ]
    py = d["python"]
    if py["present"]:
        lines.append(
            "  python:       "
            + ("uses uv" if py["uses_uv"] else "uv not in use")
            + (
                f"; other managers found: {', '.join(py['other_managers'])} (ask before migrating)"
                if py["other_managers"]
                else ""
            )
        )
    a = d["adoptable"]
    for k, label in (
        ("adr_dir", "ADRs to adopt into DECISIONS/"),
        ("constitution", "constitution to adopt"),
    ):
        if a[k]:
            lines.append(f"  adoptable:    {label}: {a[k]}")
    if a["specs_dir"]:
        lines.append(
            "  adoptable:    existing specs/ directory (check numbering & sections against the standard)"
        )
    if a["agent_instructions"]:
        lines.append(
            f"  adoptable:    existing agent instructions: {', '.join(a['agent_instructions'])}"
        )
    sf = d.get("surface") or {}
    if sf:
        http, cli = sf.get("http", {}), sf.get("cli", {})
        ops = sum(f["operations"] for f in http.get("files", []))
        bits = []
        if ops:
            bits.append(
                f"{ops} HTTP route(s) in {len(http['files'])} file(s), prefixes "
                + ", ".join(list(http.get("prefixes", {}))[:5])
            )
        if cli.get("commands"):
            bits.append(f"{len(cli['commands'])} CLI command(s)")
        if sf.get("schemas"):
            bits.append("schemas: " + ", ".join(sf["schemas"][:3]))
        if sf.get("api_docs"):
            bits.append("API docs: " + ", ".join(sf["api_docs"][:3]))
        if bits:
            lines.append("  surface:      " + "; ".join(bits))
        if http.get("limits"):
            lines.append("  surface note: " + "; ".join(http["limits"]))
    rl = d.get("rules") or {}
    if rl.get("candidates"):
        lines.append(
            f"  rules:        {len(rl['candidates'])} candidate rule(s) from {', '.join(rl['sources'][:4])}"
            + (
                f"; {len(rl['ci_gates'])} CI gate command(s)"
                if rl.get("ci_gates")
                else ""
            )
            + (
                f"; {len(rl['conflicts'])} possible conflict(s)"
                if rl.get("conflicts")
                else ""
            )
        )
    dl = d.get("decision_leads") or {}
    if dl.get("docs") or dl.get("comments") or dl.get("commits"):
        lines.append(
            f"  decisions:    leads only — {len(dl.get('docs', []))} doc(s), {len(dl.get('comments', []))} code comment(s), "
            f"{len(dl.get('commits', []))} commit subject(s); a reason needs a document or a person"
        )
    if d.get("capability_candidates"):
        lines.append(
            f"  capabilities: {len(d['capability_candidates'])} candidate(s) from routes, commands and workers (unconfirmed)"
        )
    if (d.get("adoptable") or {}).get("specs"):
        lines.append(
            f"  legacy specs: {len(d['adoptable']['specs'])} spec director{'y' if len(d['adoptable']['specs']) == 1 else 'ies'} without GroundWork metadata (adopt-specs --dry-run)"
        )
    lay = d.get("layout") or {}
    if lay.get("decided"):
        lines.append(f"  code layout:  decided ({lay['decided']})")
    elif lay.get("has_code"):
        lines.append(
            f"  code layout:  not decided; looks like a {lay['profile_guess']} rooted at {lay['root_guess']} "
            "(ask: migrate to the standard layout, or keep the current structure)"
        )
    g = d["git"]
    if g["commits"]:
        who = ", ".join(f"{x['name']} ({x['commits']})" for x in g["top_authors"][:3])
        lines.append(
            f"  git:          {g['commits']} commits, {g['first_commit']} → {g['last_commit']}; top: {who}"
        )
    return "\n".join(lines)
