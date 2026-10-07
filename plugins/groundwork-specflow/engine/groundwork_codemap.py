"""CODEMAP.md — where each kind of code lives in this repo, generated from the code itself (STANDARD.md §5g).

Every repo has one, whatever its layout decision: agents read it instead of searching the whole codebase.
The engine writes the facts (folders, their role, where outside systems are called, where settings are read,
wiring and tests). People and agents write only the "Holds" column and the Notes section; both survive
regeneration. A hash of the facts is embedded so `check` can tell when the map no longer matches the code.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path, PurePosixPath

import groundwork_core as C
import groundwork_layout as L

FILE = "CODEMAP.md"
MAX_DEPTH = 4
MAX_ROWS = 80
TODO = "[TODO: what this folder holds]"
STAMP = re.compile(r"<!-- groundwork:codemap facts=([0-9a-f]{12}) -->")

CATEGORY = {
    "llm": {
        "openai",
        "anthropic",
        "google.generativeai",
        "google.genai",
        "cohere",
        "mistralai",
        "litellm",
        "groq",
        "langchain",
        "langchain_core",
        "langchain_openai",
        "langchain_anthropic",
        "llama_index",
        "ollama",
        "@anthropic-ai/sdk",
        "@google/generative-ai",
        "@google/genai",
        "cohere-ai",
        "@mistralai/mistralai",
        "@langchain",
        "ai",
        "@ai-sdk",
        "github.com/sashabaranov/go-openai",
        "github.com/anthropics/anthropic-sdk-go",
        "github.com/openai/openai-go",
    },
    "database": {
        "psycopg",
        "psycopg2",
        "asyncpg",
        "pymysql",
        "MySQLdb",
        "mysql",
        "sqlite3",
        "sqlalchemy",
        "sqlmodel",
        "pymongo",
        "motor",
        "cassandra",
        "neo4j",
        "pg",
        "postgres",
        "mysql2",
        "mongodb",
        "mongoose",
        "@prisma/client",
        "typeorm",
        "sequelize",
        "knex",
        "drizzle-orm",
        "better-sqlite3",
        "database/sql",
        "github.com/jackc/pgx",
        "github.com/lib/pq",
        "github.com/go-sql-driver/mysql",
        "gorm.io",
        "go.mongodb.org",
    },
    "cache": {
        "redis",
        "aioredis",
        "ioredis",
        "github.com/redis/go-redis",
        "github.com/go-redis/redis",
    },
    "search / vectors": {
        "elasticsearch",
        "opensearchpy",
        "pinecone",
        "qdrant_client",
        "chromadb",
        "weaviate",
        "@elastic/elasticsearch",
        "@pinecone-database/pinecone",
        "@qdrant/js-client-rest",
    },
    "http": {
        "requests",
        "httpx",
        "aiohttp",
        "urllib3",
        "urllib.request",
        "http.client",
        "websockets",
        "grpc",
        "axios",
        "node-fetch",
        "got",
        "undici",
        "ky",
        "superagent",
        "graphql-request",
        "@apollo/client",
        "socket.io-client",
        "net/http",
        "fetch",
    },
    "cloud": {
        "boto3",
        "botocore",
        "aiobotocore",
        "google.cloud",
        "azure",
        "firebase_admin",
        "supabase",
        "aws-sdk",
        "@aws-sdk",
        "@google-cloud",
        "@azure",
        "firebase",
        "firebase-admin",
        "@supabase/supabase-js",
        "github.com/aws/aws-sdk-go",
        "cloud.google.com/go",
        "github.com/Azure/azure-sdk-for-go",
    },
    "queue": {
        "kafka",
        "confluent_kafka",
        "aiokafka",
        "pika",
        "aio_pika",
        "nats",
        "kafkajs",
        "amqplib",
        "bullmq",
        "github.com/segmentio/kafka-go",
        "github.com/rabbitmq/amqp091-go",
        "github.com/nats-io",
    },
    "email / messaging": {
        "smtplib",
        "sendgrid",
        "twilio",
        "slack_sdk",
        "nodemailer",
        "@sendgrid",
        "@slack/web-api",
        "net/smtp",
    },
    "payments": {"stripe", "github.com/stripe"},
    "files / remote shell": {"paramiko", "ftplib"},
}


def category(lib: str) -> str:
    return next((c for c, libs in CATEGORY.items() if lib in libs), "other")


def _folder(rel: str) -> str:
    parts = PurePosixPath(rel).parts[:-1]
    return "/".join(parts[:MAX_DEPTH]) or "."


def facts(repo: Path) -> dict:
    """Everything the map states, computed from the code. No model, no network."""
    lay = L.load(repo)
    standard = lay is not None and lay.mode == "standard" and not lay.problems
    files = L.code_files(
        repo, L.Layout("keep")
    )  # the whole repo: tests, scripts and legacy folders belong on the map too
    folders: dict[str, dict] = defaultdict(lambda: {"files": 0, "roles": set()})
    systems: dict[tuple[str, str], set[str]] = defaultdict(set)
    env, wiring, tests = set(), [], defaultdict(int)
    langs: dict[str, int] = defaultdict(int)
    for rel in sorted(set(files)):
        lg = L.lang(rel)
        langs[{"py": "Python", "go": "Go"}.get(lg, "JavaScript/TypeScript")] += 1
        if L.is_test(rel):
            tests[_folder(rel)] += 1
            continue
        f = folders[_folder(rel)]
        f["files"] += 1
        if standard:
            role = (
                "wiring"
                if L.is_wiring(lay, rel)
                else "not yet migrated"
                if L.is_legacy(lay, rel)
                else L.layer_of(lay, rel) or "no role"
            )
        else:
            stem = PurePosixPath(rel).stem
            role = (
                "entry / wiring"
                if stem in L.WIRING_STEMS - {"__init__", "mod"} and rel.count("/") <= 2
                else ""
            )
        if role in ("wiring", "entry / wiring"):
            wiring.append(rel)
        if role:
            f["roles"].add(role)
        try:
            text = L._strip_comments(
                (repo / rel).read_text(encoding="utf-8", errors="replace")[:300_000], lg
            )
        except OSError:
            continue
        for spec, _line, level in L.imports(text, lg):
            ext = None if level else L.external(spec, lg)
            if ext:
                systems[(category(ext[0]), ext[0])].add(rel)
        if lg == "js" and L.JS_FETCH.search(text):
            systems[("http", "fetch")].add(rel)
        if L.ENV_READ[lg].search(text):
            env.add(rel)
    rows = [
        {"folder": k, "role": ", ".join(sorted(v["roles"])) or "", "files": v["files"]}
        for k, v in sorted(folders.items())
    ][:MAX_ROWS]
    return {
        "layout": (
            "not decided"
            if lay is None
            else "keep (own structure)"
            if lay.mode == "keep"
            else "invalid"
            if lay.problems
            else f"standard ({lay.profile} profile, root {lay.root})"
        ),
        "languages": dict(sorted(langs.items(), key=lambda x: -x[1])),
        "folders": rows,
        "systems": [
            {"kind": k, "library": lib, "files": sorted(fs)}
            for (k, lib), fs in sorted(systems.items())
        ],
        "settings": sorted(env),
        "wiring": sorted(wiring)[:20],
        "tests": [{"folder": k, "files": n} for k, n in sorted(tests.items())],
    }


def fingerprint(f: dict) -> str:
    """What makes the map wrong when it changes: folders and roles, where outside systems and settings live.
    File counts are left out so adding a file to an existing folder does not age the map."""
    key = {
        "layout": f["layout"],
        "folders": [(r["folder"], r["role"]) for r in f["folders"]],
        "systems": sorted(
            {
                (s["kind"], s["library"], _folder(x))
                for s in f["systems"]
                for x in s["files"]
            }
        ),
        "settings": sorted({_folder(x) for x in f["settings"]}),
        "wiring": f["wiring"],
        "tests": [t["folder"] for t in f["tests"]],
    }
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:12]


def _kept(text: str) -> tuple[dict[str, str], str]:
    """The human-written parts of an existing map: the Holds cell of each folder, and the Notes section."""
    holds = {}
    sec = re.search(r"^## Folders\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    for ln in (sec.group(1) if sec else "").splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0].startswith("`"):
            holds[cells[0].strip("`")] = cells[3]
    m = re.search(r"^## Notes\n(.*)\Z", text, re.MULTILINE | re.DOTALL)
    return holds, (m.group(1).strip() if m else "")


def render(repo: Path, f: dict, previous: str = "") -> str:
    holds, notes = _kept(previous)
    lay = L.load(repo)
    out = [
        f"# Code map — {repo.name}",
        "",
        f"<!-- groundwork:codemap facts={fingerprint(f)} -->",
        (
            "<!-- Generated by `groundwork.py codemap` from the code. Edit only the Holds column and the Notes section: "
            "they are kept when the map is regenerated. Regenerate after adding, moving or removing folders. -->"
        ),
        "",
        "Read this before searching the code: it says where each kind of code lives.",
        "",
        f"**Layout:** {f['layout']}",
    ]
    if lay is not None and lay.mode == "keep":
        out.append(
            "New code goes next to existing code of the same kind and copies its patterns."
        )
    elif lay is not None and lay.mode == "standard" and not lay.problems:
        out.append(
            "New code goes in its role folder; `groundwork.py layout` shows the rules."
        )
    out.append(
        "**Languages:** "
        + (
            ", ".join(f"{k} ({v} files)" for k, v in f["languages"].items())
            or "no code yet"
        )
    )
    out += [
        "",
        "## Folders",
        "",
        "| Folder | Role | Code files | Holds |",
        "| --- | --- | --- | --- |",
    ]
    for r in f["folders"]:
        default = (
            L.SHORT.get(r["role"], "")
            if lay is not None and lay.mode == "standard"
            else ""
        ) or TODO
        out.append(
            f"| `{r['folder']}` | {r['role'] or '—'} | {r['files']} | {holds.get(r['folder']) or default} |"
        )
    if not f["folders"]:
        out.append("| — | — | 0 | no code yet |")
    out += ["", "## Outside systems (where they are called)", ""]
    if f["systems"]:
        out += ["| Kind | Library | Called from |", "| --- | --- | --- |"]
        for s in f["systems"]:
            shown = ", ".join(f"`{x}`" for x in s["files"][:5]) + (
                f" (+{len(s['files']) - 5} more)" if len(s["files"]) > 5 else ""
            )
            out.append(f"| {s['kind']} | {s['library']} | {shown} |")
    else:
        out.append("None found.")
    out += ["", "## Settings (where environment variables are read)", ""]
    out += [f"- `{x}`" for x in f["settings"]] or ["None found."]
    import groundwork_secrets as S

    out += ["", S.summary(repo)]
    out += ["", "## Entry and wiring files", ""]
    out += [f"- `{x}`" for x in f["wiring"]] or ["None found."]
    out += ["", "## Tests", ""]
    out += [f"- `{t['folder']}` ({t['files']} files)" for t in f["tests"]] or [
        "None found."
    ]
    out += [
        "",
        "## Notes",
        "",
        notes or "_Conventions an agent should know about this structure (optional)._",
        "",
    ]
    return "\n".join(out)


def path(repo: Path) -> Path:
    return C._find_ci(repo, FILE) or repo / FILE


def write(repo: Path) -> Path:
    p = path(repo)
    prev = p.read_text(encoding="utf-8") if p.is_file() else ""
    p.write_text(render(repo, facts(repo), prev), encoding="utf-8")
    return p


def state(repo: Path) -> tuple[str, str]:
    """(status, detail): missing | unfinished | outdated | current."""
    p = C._find_ci(repo, FILE)
    if p is None:
        return "missing", ""
    text = p.read_text(encoding="utf-8")
    m = STAMP.search(text)
    if not m or m.group(1) != fingerprint(facts(repo)):
        return "outdated", ""
    n = text.count(TODO)
    if n:
        return "unfinished", f"{n} folder(s) not described"
    return "current", ""
