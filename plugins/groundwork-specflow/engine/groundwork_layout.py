"""Code layout — the same folders, with the same meaning, in every repo that adopts it (STANDARD.md §5f).

A repo records one decision in `.groundwork/config.json` under `"layout"`:

  {"mode": "keep"}                                  the repo keeps its own structure; nothing here applies
  {"mode": "standard", "profile": "service", "root": "src/shop",
   "folders": {"connectors": ["src/shop/clients"]},  existing folders mapped to a role (optional)
   "wiring": ["src/shop/app.py"],                   files that may import everything (optional, added to defaults)
   "legacy": ["src/shop/old"]}                      not yet migrated; exempt until moved (optional)

The checks are static (imports, env reads, folder names), need no model, and only ever warn (GW101–GW107);
`check --strict` makes them binding. A malformed `layout` entry is an error (GW100).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import groundwork_core as C

# --- the vocabulary ---------------------------------------------------------------------

PURPOSE = {
    "core": "business rules and use cases. Pure code: no network, database, SDKs or env vars. "
            "It defines the interfaces it needs (e.g. core/ports.py) and connectors implement them",
    "connectors": "the only code that talks to the outside world, one folder per external system named by its "
                  "role (llm/, database/, email/, payments/); the vendor goes inside (llm/anthropic.py). "
                  "Timeouts, retries and logging of external calls live here",
    "entrypoints": "how the app is called (http/, cli/, workers/, jobs/). Thin: parse input, call core, format the reply",
    "config": "the only place that reads environment variables, settings files and secrets",
    "prompts": "LLM prompt texts and templates, kept out of code",
    "pages": "routes and screens: compose components and call core",
    "components": "reusable UI pieces: render what they are given; no data fetching",
}

SHORT = {
    "core": "business logic, no I/O",
    "connectors": "the only code that talks to outside systems (LLMs, databases, HTTP APIs, queues, email), one folder per system",
    "entrypoints": "thin http/cli/worker handlers",
    "config": "the only place that reads env vars and secrets",
    "prompts": "LLM prompt texts",
    "pages": "routes and screens",
    "components": "reusable UI, no data fetching",
}

# layer -> layers it may import (it may always import itself). Wiring files may import anything.
PROFILES: dict[str, dict] = {
    "service": {"about": "an API, web backend or background worker",
                "imports": {"core": ["prompts"], "connectors": ["core", "config", "prompts"],
                            "entrypoints": ["core", "config"], "config": [], "prompts": []},
                "required": ["core", "entrypoints"], "env_layers": ["config"]},
    "cli": {"about": "a command-line tool",
            "imports": {"core": ["prompts"], "connectors": ["core", "config", "prompts"],
                        "entrypoints": ["core", "config"], "config": [], "prompts": []},
            "required": ["core", "entrypoints"], "env_layers": ["config"]},
    "web": {"about": "a browser front end (React, Vue, Svelte, Angular, Next.js …)",
            "imports": {"pages": ["components", "core", "config"], "components": ["core"],
                        "core": ["connectors", "config", "prompts"], "connectors": ["config"],
                        "config": [], "prompts": []},
            "required": ["pages", "components", "core"], "env_layers": ["config"]},
    "library": {"about": "a package other code imports; it takes settings as arguments",
                "imports": {"core": ["prompts"], "connectors": ["core", "prompts"], "prompts": []},
                "required": ["core"], "env_layers": []},
}
MODES = {"standard", "keep"}

# Names that say nothing about what a folder or file holds.
VAGUE = {"utils", "util", "helpers", "helper", "misc", "common", "shared", "stuff", "lib_utils", "tools_misc"}

CODE_EXT = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".go", ".vue", ".svelte"}
TEST_DIRS = {"tests", "test", "__tests__", "__mocks__", "testdata", "fixtures", "e2e", "cypress"}
TEST_FILE = re.compile(r"(^test_.*\.py|.*_test\.(py|go)|.*\.(test|spec)\.[cm]?[jt]sx?|conftest\.py)$")
WIRING_STEMS = {"app", "main", "__main__", "__init__", "index", "wiring", "container", "bootstrap", "server", "cli", "mod"}

# Libraries that reach outside the process. Allowed only in connectors (and, for servers, entrypoints).
EXTERNAL_PY = {
    "openai", "anthropic", "google.generativeai", "google.genai", "cohere", "mistralai", "litellm", "groq",
    "langchain", "langchain_core", "langchain_openai", "langchain_anthropic", "llama_index", "ollama",
    "requests", "httpx", "aiohttp", "urllib3", "urllib.request", "http.client", "websockets", "grpc",
    "boto3", "botocore", "aiobotocore", "google.cloud", "azure", "firebase_admin", "supabase",
    "psycopg", "psycopg2", "asyncpg", "pymysql", "MySQLdb", "mysql", "sqlite3", "sqlalchemy", "sqlmodel",
    "pymongo", "motor", "redis", "aioredis", "elasticsearch", "opensearchpy", "cassandra", "neo4j",
    "pinecone", "qdrant_client", "chromadb", "weaviate",
    "kafka", "confluent_kafka", "aiokafka", "pika", "aio_pika", "nats",
    "smtplib", "sendgrid", "twilio", "stripe", "slack_sdk", "paramiko", "ftplib",
}
EXTERNAL_JS = {
    "openai", "@anthropic-ai/sdk", "@google/generative-ai", "@google/genai", "cohere-ai", "@mistralai/mistralai",
    "langchain", "@langchain/*", "ai", "@ai-sdk/*", "ollama",
    "axios", "node-fetch", "got", "undici", "ky", "superagent", "graphql-request", "@apollo/client", "socket.io-client",
    "aws-sdk", "@aws-sdk/*", "@google-cloud/*", "@azure/*", "firebase", "firebase/*", "firebase-admin",
    "@supabase/supabase-js",
    "pg", "postgres", "mysql", "mysql2", "mongodb", "mongoose", "redis", "ioredis", "@prisma/client", "typeorm",
    "sequelize", "knex", "drizzle-orm", "drizzle-orm/*", "better-sqlite3", "sqlite3", "@elastic/elasticsearch",
    "@pinecone-database/pinecone", "@qdrant/js-client-rest", "chromadb",
    "kafkajs", "amqplib", "nats", "bullmq",
    "nodemailer", "@sendgrid/*", "twilio", "stripe", "@slack/web-api",
}
EXTERNAL_GO = {
    "database/sql", "net/smtp", "github.com/jackc/pgx/*", "github.com/lib/pq", "github.com/go-sql-driver/mysql",
    "gorm.io/*", "go.mongodb.org/*", "github.com/redis/go-redis/*", "github.com/go-redis/redis/*",
    "github.com/aws/aws-sdk-go*", "cloud.google.com/go/*", "github.com/Azure/azure-sdk-for-go/*",
    "github.com/sashabaranov/go-openai", "github.com/anthropics/anthropic-sdk-go*", "github.com/openai/openai-go*",
    "github.com/segmentio/kafka-go", "github.com/rabbitmq/amqp091-go", "github.com/nats-io/*", "github.com/stripe/*",
}
SERVER_SIDE = {"net/http", "net/http/*"}          # clients and servers alike: connectors or entrypoints

ENV_READ = {
    "py": re.compile(r"\bos\.environ\b|\bos\.getenv\s*\(|\bload_dotenv\s*\(|\bdotenv_values\s*\(|^\s*from\s+os\s+import\s+[^\n]*\b(environ|getenv)\b", re.M),
    "js": re.compile(r"""\bprocess\.env\b|\bimport\.meta\.env\b|\bDeno\.env\b|\bBun\.env\b|\bdotenv\.config\s*\(|['"]dotenv/config['"]"""),
    "go": re.compile(r"\bos\.(Getenv|LookupEnv|Environ)\s*\(|\bgodotenv\.(Load|Overload|Read)\s*\("),
}
JS_FETCH = re.compile(r"(?<![\w.$])(fetch|XMLHttpRequest|WebSocket|EventSource)\s*\(|new\s+(XMLHttpRequest|WebSocket|EventSource)\b")

PY_IMPORT = re.compile(r"^\s*import\s+([\w.]+(?:\s+as\s+\w+)?(?:\s*,\s*[\w.]+(?:\s+as\s+\w+)?)*)", re.M)
PY_FROM = re.compile(r"^\s*from\s+(\.*)([\w.]*)\s+import\s+\(?\s*([\w*][\w\s,]*)", re.M)
JS_IMPORT = re.compile(r"""(?:^|[^\w$.])(?:from|import|require)\s*\(?\s*['"]([^'"\n]+)['"]""", re.M)
GO_BLOCK = re.compile(r"^import\s*\((.*?)\)", re.M | re.S)
GO_SINGLE = re.compile(r'^import\s+(?:[\w.]+\s+)?"([^"]+)"', re.M)
GO_PATH = re.compile(r'"([^"]+)"')


def lang(path: str) -> str | None:
    ext = PurePosixPath(path).suffix.lower()
    if ext == ".py":
        return "py"
    if ext == ".go":
        return "go"
    return "js" if ext in CODE_EXT else None


# --- configuration --------------------------------------------------------------------

@dataclass
class Layout:
    mode: str
    profile: str = ""
    root: str = "."
    folders: dict[str, list[str]] = field(default_factory=dict)   # effective layer -> repo-relative paths
    wiring: list[str] = field(default_factory=list)
    legacy: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def layers(self) -> list[str]:
        return list(PROFILES[self.profile]["imports"]) if self.profile in PROFILES else []


def _rel(p: str) -> str:
    s = PurePosixPath(str(p).replace("\\", "/").strip())
    parts = [x for x in s.parts if x not in ("", ".")]
    return "/".join(parts) or "."


def _under(path: str, prefix: str) -> bool:
    return prefix == "." or path == prefix or path.startswith(prefix.rstrip("/") + "/")


def _paths(v) -> list[str]:
    return [v] if isinstance(v, str) else [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


def load(repo: Path, cfg: dict | None = None) -> Layout | None:
    """The repo's layout decision, or None when it has not been made yet."""
    raw = (cfg if cfg is not None else C.read_config(repo)).get("layout")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return Layout("standard", problems=['"layout" must be an object, e.g. {"mode": "keep"}'])
    mode = raw.get("mode", "standard")
    if mode not in MODES:
        return Layout("standard", problems=[f'unknown layout mode "{mode}" (use "standard" or "keep")'])
    if mode == "keep":
        return Layout("keep")
    lay = Layout("standard", str(raw.get("profile", "")), _rel(raw.get("root", ".")))
    if lay.profile not in PROFILES:
        lay.problems.append(f'unknown profile "{lay.profile}" (use one of: {", ".join(PROFILES)})')
        return lay
    for p in [lay.root, *(x for v in (raw.get("folders") or {}).values() for x in _paths(v)),
              *_paths(raw.get("wiring")), *_paths(raw.get("legacy"))]:
        if p.startswith("/") or ".." in PurePosixPath(p).parts or re.match(r"^[A-Za-z]:", p):
            lay.problems.append(f'path "{p}" must be relative to the repo and stay inside it')
    folders = raw.get("folders") or {}
    if not isinstance(folders, dict):
        lay.problems.append('"folders" must map a role to a path or a list of paths')
        folders = {}
    for k in folders:
        if k not in lay.layers:
            lay.problems.append(f'"{k}" is not a folder role of the {lay.profile} profile ({", ".join(lay.layers)})')
    for layer in lay.layers:
        home = _rel(f"{lay.root}/{layer}")             # where new code goes; mapped folders are existing code in that role
        lay.folders[layer] = [home, *(m for m in (_rel(x) for x in _paths(folders.get(layer))) if m != home)]
    lay.wiring = [_rel(x) for x in _paths(raw.get("wiring"))]
    lay.legacy = [_rel(x) for x in _paths(raw.get("legacy"))]
    return lay


def layer_of(lay: Layout, rel: str) -> str | None:
    best, n = None, -1
    for layer, paths in lay.folders.items():
        for p in paths:
            if _under(rel, p) and len(p) > n:
                best, n = layer, len(p)
    return best


def is_wiring(lay: Layout, rel: str) -> bool:
    if any(_under(rel, w) for w in lay.wiring):
        return True
    p = PurePosixPath(rel)
    parent = p.parent.as_posix() if p.parent.as_posix() != "" else "."
    if parent == lay.root and p.stem in WIRING_STEMS:
        return True
    return "cmd" in p.parts[:-1] and (p.parts.index("cmd") == 0 or _under(rel, _rel(f"{lay.root}/cmd")))


def is_legacy(lay: Layout, rel: str) -> bool:
    return any(_under(rel, x) for x in lay.legacy)


def is_test(rel: str) -> bool:
    p = PurePosixPath(rel)
    return bool(TEST_FILE.match(p.name)) or any(x in TEST_DIRS for x in p.parts[:-1])


# --- scanning -------------------------------------------------------------------------

def _scan_roots(lay: Layout) -> list[str]:
    roots = sorted({lay.root, *(p for ps in lay.folders.values() for p in ps), *lay.wiring})
    return [r for r in roots if not any(o != r and _under(r, o) for o in roots)]


def code_files(repo: Path, lay: Layout, limit: int = 5000) -> list[str]:
    out: list[str] = []
    for top in _scan_roots(lay):
        base = repo / top
        if base.is_file():
            out.append(top)
            continue
        if not base.is_dir():
            continue
        for d, dirs, files in os.walk(base):
            rd = _rel(Path(d).relative_to(repo).as_posix())
            dirs[:] = sorted(x for x in dirs if x not in C.SKIP_DIRS and not x.startswith(".")
                             and x not in {"specs", "bugs", "DECISIONS", "CONTRACTS", "docs", "target", "coverage"}
                             and not is_legacy(lay, _rel(f"{rd}/{x}")))
            for f in sorted(files):
                rel = _rel(f"{rd}/{f}")
                if lang(rel) and not (Path(d) / f).is_symlink():
                    out.append(rel)
                    if len(out) >= limit:
                        return out
    return sorted(set(out))


def _strip_comments(text: str, lg: str) -> str:
    if lg == "py":
        return re.sub(r"^\s*#.*$", "", text, flags=re.M)
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"^\s*//.*$", "", text, flags=re.M)


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def imports(text: str, lg: str) -> list[tuple[str, int, int]]:
    """(spec, line, relative-level) for each import. Python relative imports carry their dot count."""
    out: list[tuple[str, int, int]] = []
    if lg == "py":
        for m in PY_IMPORT.finditer(text):
            for part in m.group(1).split(","):
                out.append((part.split(" as ")[0].strip(), _line(text, m.start()), 0))
        for m in PY_FROM.finditer(text):
            dots, mod = len(m.group(1)), m.group(2)
            if dots and not mod:                     # from . import a, b  → each name is a module candidate
                for name in re.split(r"[\s,]+", m.group(3)):
                    if name and name != "*":
                        out.append((name, _line(text, m.start()), dots))
            else:
                out.append((mod, _line(text, m.start()), dots))
    elif lg == "js":
        for m in JS_IMPORT.finditer(text):
            out.append((m.group(1), _line(text, m.start(1)), 0))
    else:
        for b in GO_BLOCK.finditer(text):
            for m in GO_PATH.finditer(b.group(1)):
                out.append((m.group(1), _line(text, b.start(1) + m.start()), 0))
        for m in GO_SINGLE.finditer(text):
            out.append((m.group(1), _line(text, m.start()), 0))
    return out


def _go_module(repo: Path) -> str | None:
    try:
        m = re.search(r"^module\s+(\S+)", (repo / "go.mod").read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def target_path(repo: Path, lay: Layout, src: str, spec: str, lg: str, level: int, gomod: str | None) -> str | None:
    """The repo-relative path an internal import points at, or None for a third-party import."""
    here = PurePosixPath(src).parent
    if lg == "py":
        if level:
            base = here
            for _ in range(level - 1):
                base = base.parent
            return _rel(f"{base.as_posix()}/{spec.replace('.', '/')}")
        mod = spec.replace(".", "/")
        root = PurePosixPath(lay.root)
        for base in (root.parent.as_posix(), lay.root, "src", "."):
            cand = _rel(f"{base}/{mod}")
            first = _rel(f"{base}/{mod.split('/')[0]}")
            if first != "." and ((repo / first).is_dir() or (repo / f"{first}.py").is_file()) and layer_of(lay, cand):
                return cand
        return None
    if lg == "js":
        if spec.startswith("."):
            return _rel(os.path.normpath(f"{here.as_posix()}/{spec}").replace("\\", "/"))
        for alias in ("@/", "~/", "#/", "$lib/", "src/"):
            if spec.startswith(alias):
                rest = spec[len(alias):]
                return _rel(f"{'src' if alias == 'src/' else lay.root}/{rest}")
        cand = _rel(f"{lay.root}/{spec}")
        return cand if (repo / _rel(f"{lay.root}/{spec.split('/')[0]}")).is_dir() and layer_of(lay, cand) else None
    if gomod and (spec == gomod or spec.startswith(gomod + "/")):
        return _rel(spec[len(gomod):].lstrip("/") or ".")
    return None


def _match(spec: str, names: set[str]) -> str | None:
    """`name` matches itself and its sub-paths; `name*` matches any spec starting with `name`."""
    for n in sorted(names, key=len, reverse=True):
        if n.endswith("*"):
            if spec.startswith(n[:-1]) or spec == n[:-2]:
                return n[:-1].rstrip("/")
        elif spec == n or spec.startswith(n + "/"):
            return n
    return None


def external(spec: str, lg: str) -> tuple[str, set[str]] | None:
    """(library, layers allowed to use it) when `spec` reaches outside the process."""
    if lg == "py":
        hit = next((n for n in sorted(EXTERNAL_PY, key=len, reverse=True)
                    if spec == n or spec.startswith(n + ".")), None)
        return (hit, {"connectors", "entrypoints"} if hit == "grpc" else {"connectors"}) if hit else None
    if lg == "js":
        if spec.startswith((".", "node:")):
            return None
        hit = _match(spec, EXTERNAL_JS)
        return (hit, {"connectors"}) if hit else None
    if _match(spec, SERVER_SIDE):
        return ("net/http", {"connectors", "entrypoints"})
    hit = _match(spec, EXTERNAL_GO)
    return (hit, {"connectors"}) if hit else None


@dataclass
class Finding:
    rule: str
    path: str
    message: str
    hint: str = ""


def assess(repo: Path, cfg: dict | None = None) -> list[Finding]:
    """Everything that breaks the declared layout. Empty when no layout is declared or the repo keeps its own."""
    lay = load(repo, cfg)
    if lay is None or lay.mode == "keep":
        return []
    if lay.problems:
        return [Finding("GW100", ".groundwork/config.json", p, "fix the \"layout\" entry; see STANDARD.md §5f")
                for p in lay.problems]
    prof = PROFILES[lay.profile]
    out: list[Finding] = []
    for layer in prof["required"]:
        if not any((repo / p).is_dir() for p in lay.folders[layer]):
            out.append(Finding("GW101", lay.folders[layer][0], f"the {lay.profile} profile needs a {layer}/ folder ({SHORT[layer]})",
                               "groundwork.py layout init --create, or map an existing folder: groundwork.py layout map "
                               f"{layer}=<path>"))
    files = code_files(repo, lay)
    gomod = _go_module(repo)
    outside: dict[str, int] = {}
    seen_dirs: set[str] = set()
    for rel in files:
        if is_legacy(lay, rel):
            continue
        p = PurePosixPath(rel)
        for i, part in enumerate(p.parts[:-1]):
            d = "/".join(p.parts[:i + 1])
            if part.lower() in VAGUE and d not in seen_dirs and _under(d, lay.root):
                seen_dirs.add(d)
                out.append(Finding("GW106", d, f'folder name "{part}" says nothing about what it holds',
                                   "move each file next to the code it serves, or name the folder for its job"))
        if p.stem.lower() in VAGUE:
            out.append(Finding("GW106", rel, f'file name "{p.name}" says nothing about what it holds',
                               "split it into files named for what they do"))
        if is_test(rel):
            continue
        wiring = is_wiring(lay, rel)
        layer = layer_of(lay, rel)
        if not wiring and layer is None:
            inner = rel if lay.root == "." else rel[len(lay.root) + 1:] if _under(rel, lay.root) else None
            key = _rel(f"{lay.root}/{inner.split('/')[0]}") if inner else rel
            outside[key] = outside.get(key, 0) + 1
            continue
        if wiring:
            continue
        if layer == "connectors" and not wiring:
            home = next(c for c in lay.folders["connectors"] if _under(rel, c))
            if p.parent.as_posix() == home and p.stem not in ("__init__", "index", "mod", "ports", "base"):
                out.append(Finding("GW107", rel, "connector code sits directly in the connectors folder",
                                   f"give each external system its own folder: {home}/<system>/ (e.g. llm/, database/)"))
        lg = lang(rel)
        try:
            raw = (repo / rel).read_text(encoding="utf-8", errors="replace")[:300_000]
        except OSError:
            continue
        text = _strip_comments(raw, lg)
        allowed = set(prof["imports"].get(layer, [])) | {layer}
        flagged: set[str] = set()
        for spec, line, level in imports(text, lg):
            ext = external(spec, lg) if not level else None
            if ext:
                lib, ok = ext
                if layer not in ok and lib not in flagged:
                    flagged.add(lib)
                    out.append(Finding("GW103", rel, f"line {line}: {layer}/ uses {lib}, which talks to an outside system",
                                       f"move that call into {lay.folders['connectors'][0]}/<system>/ behind an interface core defines"
                                       if "connectors" in lay.folders else "libraries take such clients as arguments"))
                continue
            tgt = target_path(repo, lay, rel, spec, lg, level, gomod)
            if not tgt or is_legacy(lay, tgt):
                continue
            tl = layer_of(lay, tgt)
            if tl and tl not in allowed and tl not in flagged:
                flagged.add(tl)
                out.append(Finding("GW102", rel, f"line {line}: {layer}/ imports {tl}/ ({spec}), which the {lay.profile} profile forbids",
                                   f"{layer}/ may import: {', '.join(sorted(allowed - {layer})) or 'nothing outside itself'}. "
                                   + ("Define an interface in core and let the wiring file plug the connector in" if tl == "connectors" else
                                      "Move the shared piece to the layer both may use")))
        if lg == "js" and layer not in ("connectors",) and (m := JS_FETCH.search(text)):
            out.append(Finding("GW103", rel, f"line {_line(text, m.start())}: {layer}/ calls the network directly ({m.group(0).strip('( ')})",
                               "put the call in a connector and call that"))
        m = ENV_READ[lg].search(text)
        if m and layer not in prof["env_layers"]:
            out.append(Finding("GW105", rel, f"line {_line(text, m.start())}: {layer}/ reads environment variables",
                               "read settings once in config/ and pass them in" if prof["env_layers"]
                               else "a library takes its settings as arguments; it never reads the environment"))
    for key, n in sorted(outside.items()):
        out.append(Finding("GW104", key, f"{n} code file(s) belong to no folder role of the layout",
                           f"move them into a role folder, map the folder (groundwork.py layout map <role>={key}), "
                           f"or mark it not yet migrated (groundwork.py layout map --legacy {key})"))
    return out


# --- suggestions for an existing codebase -----------------------------------------------

ROLE_GUESS = {
    "core": {"core", "domain", "services", "service", "usecases", "use_cases", "business", "logic", "features", "model", "models"},
    "connectors": {"connectors", "clients", "client", "integrations", "adapters", "gateways", "gateway", "db", "database",
                   "repositories", "repository", "repos", "infra", "infrastructure", "external", "providers", "storage",
                   "persistence", "dao", "llm", "api_clients", "services_external"},
    "entrypoints": {"entrypoints", "api", "routes", "routers", "handlers", "controllers", "cli", "commands", "cmd",
                    "workers", "jobs", "http", "server", "endpoints", "views"},
    "config": {"config", "settings", "conf", "configuration", "env"},
    "prompts": {"prompts"},
    "pages": {"pages", "app", "screens", "routes", "views"},
    "components": {"components", "ui", "widgets"},
}
WEB_DEPS = {"react", "vue", "svelte", "@angular/core", "next", "nuxt", "solid-js", "preact", "@sveltejs/kit"}
SERVER_DEPS = {"express", "fastify", "koa", "@nestjs/core", "hono", "fastapi", "flask", "django", "starlette",
               "aiohttp", "sanic", "tornado", "litestar", "github.com/gin-gonic/gin", "github.com/labstack/echo"}
CLI_DEPS = {"click", "typer", "commander", "yargs", "github.com/spf13/cobra", "argparse"}


def guess_root(repo: Path) -> str:
    src = repo / "src"
    if src.is_dir():
        pkgs = [d for d in src.iterdir() if d.is_dir() and (d / "__init__.py").is_file()]
        return f"src/{pkgs[0].name}" if len(pkgs) == 1 else "src"
    if (repo / "go.mod").is_file() and (repo / "internal").is_dir():
        return "internal"
    pkgs = [d for d in repo.iterdir() if d.is_dir() and (d / "__init__.py").is_file() and d.name not in TEST_DIRS]
    if len(pkgs) == 1:
        return pkgs[0].name
    return "src" if (repo / "package.json").is_file() else "."


def guess_profile(repo: Path) -> str:
    text = ""
    for f in ("package.json", "pyproject.toml", "requirements.txt", "go.mod", "setup.cfg"):
        try:
            text += "\n" + (repo / f).read_text(encoding="utf-8", errors="replace")[:100_000].lower() + "\n"
        except OSError:
            pass
    has = lambda deps: any(re.search(rf'["\'\s/]{re.escape(d.lower())}["\'\s=<>~^@\[]', text) for d in deps)  # noqa: E731
    if has(WEB_DEPS) and not has(SERVER_DEPS - {"aiohttp"}):
        return "web"
    if has(SERVER_DEPS) or (repo / "Dockerfile").is_file():
        return "service"
    if has(CLI_DEPS) or '"bin"' in text or "[project.scripts]" in text:
        return "cli"
    return "library" if text else "service"


def has_code(repo: Path, limit: int = 4000) -> bool:
    n = 0
    for d, dirs, files in os.walk(repo):
        dirs[:] = [x for x in dirs if x not in C.SKIP_DIRS and not x.startswith(".") and x not in {"specs", "bugs", "docs"}]
        for f in files:
            n += 1
            if lang(f) and not is_test(f):
                return True
            if n > limit:
                return False
    return False


def suggest(repo: Path) -> dict:
    """Evidence for the layout question: is there code, what might it be, which folders look like which role."""
    root = guess_root(repo)
    profile = guess_profile(repo)
    base = repo / root
    roles = PROFILES[profile]["imports"]
    folders: dict[str, str] = {}
    if base.is_dir():
        for d in sorted(base.iterdir()):
            if d.is_dir() and d.name not in C.SKIP_DIRS and not d.name.startswith("."):
                role = next((r for r in roles if d.name.lower() in ROLE_GUESS.get(r, set())), None)
                folders[_rel(f"{root}/{d.name}")] = role or "?"
    return {"has_code": has_code(repo), "profile_guess": profile, "root_guess": root, "folders": folders}


# --- writing the decision ---------------------------------------------------------------

def readme(layer: str, profile: str) -> str:
    may = PROFILES[profile]["imports"].get(layer, [])
    return (f"# {layer}/\n\n{PURPOSE[layer]}.\n\n"
            f"May import: {', '.join(may + ['itself']) if may else 'only itself'}.\n\n"
            "Part of the GroundWork code layout (STANDARD.md §5f). Run `groundwork.py layout` for the whole map.\n")


def summary(lay: Layout | None) -> str:
    """One paragraph for an agent's session start: where code goes, or that the repo keeps its own structure."""
    if lay is None:
        return ""
    if lay.mode == "keep":
        return ("CODE LAYOUT: this repo KEEPS ITS OWN STRUCTURE (the user chose not to migrate). Put new code where the "
                "existing code of the same kind lives and copy its patterns and naming. Do not create GroundWork layout "
                "folders (core/, connectors/, entrypoints/ …) and do not move or restructure existing code unless the user "
                "asks for a migration (then: code-layout skill).")
    if lay.problems:
        return "CODE LAYOUT: the \"layout\" entry in .groundwork/config.json is invalid — " + "; ".join(lay.problems)
    imp = PROFILES[lay.profile]["imports"]
    parts = [f"{lay.folders[l][0]}/ = {SHORT[l]}" for l in imp]
    rule = "; ".join(f"{l} may import {', '.join(imp[l]) or 'nothing else'}" for l in imp if l != "prompts")
    legacy = (f" Not yet migrated (leave alone unless a task moves it): {', '.join(lay.legacy)}." if lay.legacy else "")
    return (f"CODE LAYOUT ({lay.profile} profile, root {lay.root}): " + " | ".join(parts) + ". "
            f"Dependency rule: {rule}; wiring files (app/main) may import everything. Never create utils/helpers/common/misc "
            "folders. Put every new file in its role folder; full map: groundwork.py layout." + legacy)


def render(repo: Path) -> str:
    lay = load(repo)
    if lay is None:
        s = suggest(repo)
        lines = ["No code layout decision recorded for this repo."]
        if s["has_code"]:
            lines.append("It already has code: ask the user whether to migrate it to the standard layout or keep its structure.")
            lines.append(f"  keep:     groundwork.py layout keep")
            lines.append(f"  migrate:  groundwork.py layout init --profile {s['profile_guess']} --root {s['root_guess']}  "
                         "(then map existing folders; moving code is planned work)")
            if s["folders"]:
                lines.append("Existing folders and the role they look like (a guess, not a decision):")
                lines += [f"  {d:<32} {r}" for d, r in s["folders"].items()]
        else:
            lines.append(f"New code: groundwork.py layout init --profile {s['profile_guess']} --root {s['root_guess']} --create")
        return "\n".join(lines)
    if lay.mode == "keep":
        return "This repo keeps its own structure (layout mode: keep). New code follows the existing patterns."
    if lay.problems:
        return "Invalid layout entry:\n" + "\n".join("  " + p for p in lay.problems)
    imp = PROFILES[lay.profile]["imports"]
    lines = [f"Profile: {lay.profile} — {PROFILES[lay.profile]['about']}", f"Root:    {lay.root}", ""]
    for l in imp:
        where = ", ".join(lay.folders[l])
        mark = "" if any((repo / p).is_dir() for p in lay.folders[l]) else "   (not created yet)"
        lines.append(f"  {where + '/':<34} {PURPOSE[l]}{mark}")
        lines.append(f"  {'':<34} may import: {', '.join(imp[l]) or 'nothing outside itself'}")
    lines.append(f"\n  wiring: app/main files in {lay.root}" + (f", {', '.join(lay.wiring)}" if lay.wiring else "")
                 + " — the only code that may import everything (it plugs connectors into core)")
    if lay.legacy:
        lines.append("  not yet migrated (exempt from checks): " + ", ".join(lay.legacy))
    return "\n".join(lines)


def write(repo: Path, layout: dict) -> dict:
    return C.write_config(repo, layout=layout)


def create_folders(repo: Path, lay: Layout) -> list[str]:
    made = []
    for layer in lay.layers:
        d = repo / lay.folders[layer][0]
        if not d.exists():
            d.mkdir(parents=True)
            made.append(lay.folders[layer][0] + "/")
        r = d / "README.md"
        if not r.exists() and not any(d.iterdir()):
            r.write_text(readme(layer, lay.profile), encoding="utf-8")
    return made


def as_json(lay: Layout | None) -> str:
    if lay is None:
        return "null"
    return json.dumps({"mode": lay.mode, "profile": lay.profile, "root": lay.root, "folders": lay.folders,
                       "wiring": lay.wiring, "legacy": lay.legacy, "problems": lay.problems}, indent=2)
