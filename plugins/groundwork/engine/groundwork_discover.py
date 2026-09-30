"""Facts about an existing codebase, gathered without a model.

`groundwork.py init` writes these to `.groundwork/discovery.json` so the agent drafts PROJECT.md /
ARCHITECTURE.md / AGENTS.md from evidence instead of guesses. Everything here is *evidence*:
where a fact came from is always recorded, and nothing is presented as a decision.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

import groundwork_core as C
import groundwork_fresh as F

LANGS = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
         ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby", ".php": "PHP",
         ".cs": "C#", ".swift": "Swift", ".c": "C", ".cpp": "C++", ".scala": "Scala", ".sh": "Shell",
         ".sql": "SQL", ".vue": "Vue", ".svelte": "Svelte", ".html": "HTML", ".css": "CSS"}
ENTRY_CANDIDATES = ["main.py", "app.py", "manage.py", "wsgi.py", "asgi.py", "index.js", "server.js", "app.js",
                    "main.js", "index.ts", "main.ts", "server.ts", "main.go", "cmd", "src/main.py", "src/app.py",
                    "src/index.js", "src/index.ts", "src/main.ts", "src/main.rs", "src/lib.rs",
                    "src/main/java", "app/main.py", "src/app/main.py"]
DOC_CANDIDATES = ["README.md", "README.rst", "README", "CONTRIBUTING.md", "CHANGELOG.md", "docs", "doc",
                  "ARCHITECTURE.md", "PROJECT.md", "CLAUDE.md", "AGENTS.md", ".cursorrules"]
ADR_DIRS = ["docs/adr", "docs/adrs", "doc/adr", "adr", "docs/decisions", "docs/architecture/decisions"]
TEST_DIRS = ["tests", "test", "__tests__", "spec", "e2e", "cypress"]


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                              timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _read(p: Path, limit: int = 200_000) -> str:
    try:
        return p.read_text(errors="replace", encoding="utf-8")[:limit]
    except OSError:
        return ""


def _package_json(p: Path) -> dict:
    try:
        j = json.loads(_read(p))
    except ValueError:
        return {}
    return {"name": j.get("name"), "scripts": sorted((j.get("scripts") or {}).keys()),
            "dependencies": sorted((j.get("dependencies") or {}).keys())[:20],
            "devDependencies": sorted((j.get("devDependencies") or {}).keys())[:15],
            "engines": j.get("engines")}


def _pyproject(p: Path) -> dict:
    text = _read(p)
    try:
        import tomllib
        j = tomllib.loads(text)
        proj = j.get("project", {})
        return {"name": proj.get("name"), "requires-python": proj.get("requires-python"),
                "dependencies": [re.split(r"[<>=!~\[; ]", d)[0] for d in proj.get("dependencies", [])][:20],
                "scripts": sorted((proj.get("scripts") or {}).keys()), "tools": sorted((j.get("tool") or {}).keys())}
    except Exception:  # noqa: BLE001 — old Python or malformed file: fall back to a hint
        m = re.search(r'^name\s*=\s*"([^"]+)"', text, re.M)
        return {"name": m.group(1) if m else None}


def _requirements(p: Path) -> dict:
    lines = [ln.strip() for ln in _read(p).splitlines() if ln.strip() and not ln.startswith("#")]
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
        m = re.search(r"^module\s+(\S+)", _read(p), re.M)
        return {"module": m.group(1) if m else None}
    if name == "Cargo.toml":
        m = re.search(r'^name\s*=\s*"([^"]+)"', _read(p), re.M)
        return {"name": m.group(1) if m else None}
    if name == "Makefile":
        return {"targets": sorted(set(re.findall(r"^([A-Za-z][\w-]*):(?!=)", _read(p), re.M)))[:25]}
    return {}


def discover(repo: Path) -> dict:
    repo = repo.resolve()
    files = list(F._walk(repo))
    ext = Counter(LANGS[Path(rel).suffix.lower()] for rel, _ in files if Path(rel).suffix.lower() in LANGS)
    infra = [rel for rel, _ in files if F._matches(rel, F.MANIFESTS | F.INFRA_NAMES, F.INFRA_GLOBS)]
    manifests = {rel: _manifest_facts(repo, rel) for rel in infra
                 if Path(rel).name in F.MANIFESTS and rel.count("/") <= 2}
    tests = [d for d in TEST_DIRS if (repo / d).is_dir()]
    test_files = sum(1 for rel, _ in files if re.search(r"(^|/)(test_[^/]+\.py|[^/]+_test\.(py|go)|[^/]+\.(test|spec)\.[jt]sx?)$", rel))
    docs = [d for d in DOC_CANDIDATES if (repo / d).exists()]
    adr = next((d for d in ADR_DIRS if (repo / d).is_dir()), None)
    specs = repo / "specs"
    constitution = next((c for c in (".specify/memory/constitution.md", "constitution.md", "CONSTITUTION.md")
                         if (repo / c).is_file()), None)
    py_signals = {"uv.lock": "uv", "poetry.lock": "poetry", "Pipfile": "pipenv", "Pipfile.lock": "pipenv",
                  "environment.yml": "conda", "requirements.txt": "pip"}
    has_py = "Python" in ext
    pyproj = _read(repo / "pyproject.toml")
    uses_uv = (repo / "uv.lock").exists() or "[tool.uv" in pyproj
    other = sorted({m for f, m in py_signals.items() if m != "uv" and (repo / f).exists()}
                   | ({"poetry"} if "[tool.poetry" in pyproj else set()))
    authors = []
    for ln in _git(repo, "shortlog", "-sne", "--no-merges", "HEAD").splitlines()[:8]:
        m = re.match(r"\s*(\d+)\s+(.*?)\s*(<[^>]*>)?$", ln)
        if m:
            authors.append({"commits": int(m.group(1)), "name": m.group(2)})
    readme = next((d for d in ("README.md", "README.rst", "README") if (repo / d).is_file()), None)
    return {
        "path": str(repo), "name": repo.name,
        "languages": dict(ext.most_common(6)),
        "file_count": len(files),
        "top_level_dirs": F.toplevel(repo),
        "manifests": manifests,
        "infrastructure": sorted(rel for rel in infra if Path(rel).name not in F.MANIFESTS)[:30],
        "entry_points": [e for e in ENTRY_CANDIDATES if (repo / e).exists()],
        "python": {"present": has_py or bool(pyproj), "uses_uv": uses_uv,
                   "other_managers": other if (has_py or pyproj) else []},
        "tests": {"dirs": tests, "test_files": test_files},
        "existing_docs": docs,
        "readme_head": _read(repo / readme, 1500).strip() if readme else "",
        "adoptable": {"adr_dir": adr, "constitution": constitution,
                      "specs_dir": bool(specs.is_dir() and any(specs.iterdir())),
                      "agent_instructions": [f for f in ("CLAUDE.md", ".cursorrules", "AGENTS.md")
                                             if (repo / f).exists()]},
        "git": {"remote": _git(repo, "remote", "get-url", "origin") or None,
                "commits": int(_git(repo, "rev-list", "--count", "HEAD") or 0),
                "first_commit": _git(repo, "log", "--reverse", "--format=%as", "-1") or None,
                "last_commit": _git(repo, "log", "-1", "--format=%as") or None,
                "top_authors": authors},
    }


def summarize(d: dict) -> str:
    langs = ", ".join(f"{k} ({v})" for k, v in d["languages"].items()) or "no source files yet"
    lines = [f"  languages:    {langs}",
             f"  manifests:    {', '.join(d['manifests']) or 'none'}",
             f"  infra/CI:     {', '.join(d['infrastructure'][:6]) or 'none'}",
             f"  entry points: {', '.join(d['entry_points']) or 'none found'}",
             f"  tests:        {d['tests']['test_files']} test file(s)" + (f" in {', '.join(d['tests']['dirs'])}" if d['tests']['dirs'] else ""),
             f"  docs found:   {', '.join(d['existing_docs']) or 'none'}"]
    py = d["python"]
    if py["present"]:
        lines.append("  python:       " + ("uses uv" if py["uses_uv"] else "uv not in use")
                     + (f"; other managers found: {', '.join(py['other_managers'])} (ask before migrating)" if py["other_managers"] else ""))
    a = d["adoptable"]
    for k, label in (("adr_dir", "ADRs to adopt into DECISIONS/"), ("constitution", "constitution to adopt")):
        if a[k]:
            lines.append(f"  adoptable:    {label}: {a[k]}")
    if a["specs_dir"]:
        lines.append("  adoptable:    existing specs/ directory (check numbering & sections against the standard)")
    if a["agent_instructions"]:
        lines.append(f"  adoptable:    existing agent instructions: {', '.join(a['agent_instructions'])}")
    g = d["git"]
    if g["commits"]:
        who = ", ".join(f"{x['name']} ({x['commits']})" for x in g["top_authors"][:3])
        lines.append(f"  git:          {g['commits']} commits, {g['first_commit']} → {g['last_commit']}; top: {who}")
    return "\n".join(lines)
