"""Code quality (STANDARD.md §5i): one recorded toolchain per repo, run by one command, the same for every agent.

A repo records one decision in `.groundwork/config.json` → `"quality"`:

  {"mode": "standard", "commands": {...}, "fix": {...}}   GroundWork's default tools and shipped configs
  {"mode": "keep",     "commands": {...}}                 the repo's own tools, recorded as they are

`commands` maps each step (format, lint, types, test) to a list of shell commands that pass or fail;
`fix` maps steps to commands that repair what they can (`verify --fix`). `groundwork.py verify` runs them.
The plugin runs these commands only when someone invokes `verify`; hooks never execute project tools.

Checks (warnings; GW120 is an error):
  GW120  the `quality` entry is malformed
  GW121  standard: a language in the repo has no config for its standard tools
  GW122  a step every repo needs (lint, test) has no command
  GW123  standard: a code file is longer than `max_file_lines` (default 400)
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import groundwork_core as C
import groundwork_layout as L

STEPS = ["format", "lint", "types", "test"]
REQUIRED_STEPS = ["lint", "test"]
MODES = {"standard", "keep"}
MAX_FILE_LINES = 400
QDIR = C.TEMPLATES / "quality"

# language -> (config files that satisfy it, files GroundWork writes, dev-dependency install line)
TOOLCHAIN = {
    "python": {"configs": ["ruff.toml", ".ruff.toml", "pyproject.toml:[tool.ruff"],
               "types_configs": ["mypy.ini", ".mypy.ini", "pyproject.toml:[tool.mypy", "setup.cfg:[mypy", "pyrightconfig.json",
                                 "pyproject.toml:[tool.pyright"],
               "writes": {"ruff.toml": "ruff.toml", "mypy.ini": "mypy.ini"},
               "install": "uv add --dev ruff mypy pytest"},
    "javascript": {"configs": ["eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", "eslint.config.ts",
                               ".eslintrc.json", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc", "biome.json"],
                   "types_configs": [],
                   "writes": {"eslint.config.mjs": "eslint.config.mjs", ".prettierrc.json": "prettierrc.json"},
                   "install": "npm install --save-dev eslint @eslint/js typescript-eslint eslint-config-prettier prettier"},
    "go": {"configs": [".golangci.yml", ".golangci.yaml", ".golangci.toml", ".golangci.json"],
           "types_configs": [],
           "writes": {".golangci.yml": "golangci.yml"},
           "install": "install golangci-lint v2 (https://golangci-lint.run/welcome/install/)"},
}
PRETTIER_CONFIGS = [".prettierrc", ".prettierrc.json", ".prettierrc.js", ".prettierrc.cjs", ".prettierrc.mjs",
                    "prettier.config.js", "prettier.config.mjs", ".prettierrc.yaml", ".prettierrc.yml", "biome.json"]


@dataclass
class Finding:
    rule: str
    path: str
    message: str
    hint: str = ""


@dataclass
class Quality:
    mode: str
    commands: dict[str, list[str]]
    fix: dict[str, list[str]]
    max_file_lines: int = MAX_FILE_LINES
    problems: list[str] | None = None


def _cmds(v) -> list[str]:
    if isinstance(v, str):
        return [v] if v.strip() else []
    return [x for x in v if isinstance(x, str) and x.strip()] if isinstance(v, list) else []


def load(repo: Path, cfg: dict | None = None) -> Quality | None:
    raw = (cfg if cfg is not None else C.read_config(repo)).get("quality")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return Quality("standard", {}, {}, problems=['"quality" must be an object, e.g. {"mode": "keep", "commands": {...}}'])
    probs = []
    mode = raw.get("mode", "standard")
    if mode not in MODES:
        probs.append(f'unknown quality mode "{mode}" (use "standard" or "keep")')
    cmds, fix = raw.get("commands") or {}, raw.get("fix") or {}
    for name, d in (("commands", cmds), ("fix", fix)):
        if not isinstance(d, dict):
            probs.append(f'"{name}" must map a step ({", ".join(STEPS)}) to a command or a list of commands')
        else:
            probs += [f'unknown step "{k}" in "{name}" (use {", ".join(STEPS)})' for k in d if k not in STEPS]
    limit = raw.get("max_file_lines", MAX_FILE_LINES)
    if not isinstance(limit, int) or limit < 50:
        probs.append('"max_file_lines" must be a whole number of at least 50')
        limit = MAX_FILE_LINES
    as_map = lambda d: {k: _cmds(v) for k, v in d.items() if k in STEPS} if isinstance(d, dict) else {}  # noqa: E731
    return Quality(mode if mode in MODES else "standard", as_map(cmds), as_map(fix), limit, probs or None)


# --- what the repo contains ---------------------------------------------------------------

def languages(repo: Path) -> dict[str, int]:
    counts: Counter = Counter()
    ts = False
    for rel in L.code_files(repo, L.Layout("keep"), limit=3000):
        lg = L.lang(rel)
        counts[{"py": "python", "go": "go"}.get(lg, "javascript")] += 1
        ts = ts or PurePosixPath(rel).suffix in (".ts", ".tsx", ".mts", ".cts")
    if (repo / "pyproject.toml").is_file() and not counts["python"]:
        counts["python"] = 0
    out = dict(counts.most_common())
    if ts:
        out["typescript"] = 1
    return out


def _has(repo: Path, spec: str) -> bool:
    name, _, marker = spec.partition(":")
    p = repo / name
    if not p.is_file():
        return False
    if not marker:
        return True
    try:
        return marker in p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def configured(repo: Path, lang: str) -> bool:
    return any(_has(repo, s) for s in TOOLCHAIN[lang]["configs"])


def _uses_uv(repo: Path) -> bool:
    return (repo / "uv.lock").is_file() or _has(repo, "pyproject.toml:[tool.uv")


def standard_commands(repo: Path, langs: dict[str, int]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    cmds: dict[str, list[str]] = {s: [] for s in STEPS}
    fix: dict[str, list[str]] = {"format": [], "lint": []}
    lay = L.load(repo)
    py_root = lay.root if lay is not None and lay.mode == "standard" and not lay.problems else "."
    if "python" in langs:
        cmds["format"].append("uv run ruff format --check .")
        cmds["lint"].append("uv run ruff check .")
        cmds["types"].append(f"uv run mypy {py_root}")
        cmds["test"].append("uv run pytest")
        fix["format"].append("uv run ruff format .")
        fix["lint"].append("uv run ruff check --fix .")
    if "javascript" in langs:
        cmds["format"].append("npx prettier --check .")
        cmds["lint"].append("npx eslint .")
        if "typescript" in langs or (repo / "tsconfig.json").is_file():
            cmds["types"].append("npx tsc --noEmit")
        cmds["test"].append("npm test" if "test" in _scripts(repo) else "npx vitest run")
        fix["format"].append("npx prettier --write .")
        fix["lint"].append("npx eslint --fix .")
    if "go" in langs:
        cmds["format"].append("golangci-lint fmt --diff")
        cmds["lint"].append("golangci-lint run")
        cmds["types"].append("go vet ./...")
        cmds["test"].append("go test ./...")
        fix["format"].append("golangci-lint fmt")
        fix["lint"].append("golangci-lint run --fix")
    return {k: v for k, v in cmds.items() if v}, {k: v for k, v in fix.items() if v}


def _scripts(repo: Path) -> dict[str, str]:
    try:
        return json.loads((repo / "package.json").read_text(encoding="utf-8")).get("scripts") or {}
    except (OSError, ValueError, AttributeError):
        return {}


def _make_targets(repo: Path) -> set[str]:
    try:
        return set(re.findall(r"^([A-Za-z][\w-]*):(?!=)", (repo / "Makefile").read_text(encoding="utf-8"), re.M))
    except OSError:
        return set()


def detect_existing(repo: Path) -> dict[str, list[str]]:
    """The repo's own check commands, as far as its files show them (evidence for `quality keep`)."""
    found: dict[str, list[str]] = {s: [] for s in STEPS}
    make = _make_targets(repo)
    for step, names in (("format", ["fmt-check", "format-check", "check-format", "fmt", "format"]),
                        ("lint", ["lint"]), ("types", ["typecheck", "type-check", "types", "mypy"]), ("test", ["test"])):
        hit = next((n for n in names if n in make), None)
        if hit:
            found[step].append(f"make {hit}")
    scripts = _scripts(repo)
    for step, names in (("format", ["format:check", "fmt:check", "prettier:check", "check:format"]), ("lint", ["lint"]),
                        ("types", ["typecheck", "type-check", "types", "tsc", "check-types"]), ("test", ["test"])):
        hit = next((n for n in names if n in scripts), None)
        if hit and not found[step]:
            found[step].append("npm test" if hit == "test" else f"npm run {hit}")
    langs = languages(repo)
    if "python" in langs:
        run = "uv run " if _uses_uv(repo) else "python -m "
        py = {"format": [("ruff.toml", "ruff format --check ."), ("pyproject.toml:[tool.ruff", "ruff format --check ."),
                         ("pyproject.toml:[tool.black", "black --check .")],
              "lint": [("ruff.toml", "ruff check ."), (".ruff.toml", "ruff check ."), ("pyproject.toml:[tool.ruff", "ruff check ."),
                       (".flake8", "flake8"), ("setup.cfg:[flake8", "flake8"), (".pylintrc", "pylint ."),
                       ("pyproject.toml:[tool.pylint", "pylint .")],
              "types": [("mypy.ini", "mypy ."), ("pyproject.toml:[tool.mypy", "mypy ."), ("setup.cfg:[mypy", "mypy ."),
                        ("pyrightconfig.json", "pyright"), ("pyproject.toml:[tool.pyright", "pyright")],
              "test": [("pytest.ini", "pytest"), ("pyproject.toml:[tool.pytest", "pytest"), ("setup.cfg:[tool:pytest", "pytest"),
                       ("tox.ini", "pytest")]}
        for step, options in py.items():
            hit = next((c for spec, c in options if _has(repo, spec)), None)
            if hit and not found[step]:
                found[step].append(run + hit)
        if not found["test"] and any((repo / d).is_dir() for d in ("tests", "test")):
            found["test"].append(run + "pytest")
    if "go" in langs:
        if not found["lint"] and configured(repo, "go"):
            found["lint"].append("golangci-lint run")
        found["types"] = found["types"] or ["go vet ./..."]
        found["test"] = found["test"] or ["go test ./..."]
    return {k: v for k, v in found.items() if v}


def write_configs(repo: Path, langs: dict[str, int]) -> list[str]:
    """Write GroundWork's shipped tool configs for each language that has none. Never overwrites."""
    made = []
    for lang in ("python", "javascript", "go"):
        if lang not in langs:
            continue
        tc = TOOLCHAIN[lang]
        for dest, src in tc["writes"].items():
            if dest == "ruff.toml" and configured(repo, "python"):
                continue
            if dest == "mypy.ini" and any(_has(repo, s) for s in tc["types_configs"]):
                continue
            if dest == "eslint.config.mjs" and configured(repo, "javascript"):
                continue
            if dest == ".prettierrc.json" and any((repo / n).is_file() for n in PRETTIER_CONFIGS):
                continue
            if dest == ".golangci.yml" and configured(repo, "go"):
                continue
            if not (repo / dest).exists():
                shutil.copyfile(QDIR / src, repo / dest)
                made.append(dest)
    if not (repo / ".editorconfig").exists():
        shutil.copyfile(QDIR / "editorconfig", repo / ".editorconfig")
        made.append(".editorconfig")
    return made


def effective(repo: Path, q: Quality) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """The commands verify runs. Standard: the defaults for the languages present now, with recorded steps overriding them.
    Keep: exactly what was recorded."""
    if q.mode == "keep":
        return dict(q.commands), dict(q.fix)
    cmds, fix = standard_commands(repo, languages(repo))
    return {**cmds, **{k: v for k, v in q.commands.items() if v}}, {**fix, **{k: v for k, v in q.fix.items() if v}}


# --- checks ---------------------------------------------------------------------------------

def assess(repo: Path, cfg: dict | None = None) -> list[Finding]:
    q = load(repo, cfg)
    if q is None:
        return []
    if q.problems:
        return [Finding("GW120", ".groundwork/config.json", p, 'fix the "quality" entry; see STANDARD.md §5i') for p in q.problems]
    out: list[Finding] = []
    langs = languages(repo)
    if q.mode == "standard":
        for lang in ("python", "javascript", "go"):
            if lang in langs and not configured(repo, lang):
                out.append(Finding("GW121", ".", f"{lang} code has no config for its standard tools",
                                   "run: groundwork.py quality init --create (writes the shipped configs; never overwrites)"))
    if langs:
        cmds, _ = effective(repo, q)
        for step in REQUIRED_STEPS:
            if not cmds.get(step):
                out.append(Finding("GW122", ".groundwork/config.json", f'no "{step}" command recorded, so verify cannot check it',
                                   f'groundwork.py quality set {step}="<command that passes or fails>"'))
    if q.mode == "standard":
        for rel in L.code_files(repo, L.Layout("keep")):
            if L.is_test(rel):
                continue
            try:
                n = (repo / rel).read_text(encoding="utf-8", errors="replace").count("\n")
            except OSError:
                continue
            if n > q.max_file_lines:
                out.append(Finding("GW123", rel, f"{n} lines (limit {q.max_file_lines}); long files hide duplication and mix jobs",
                                   "split it by responsibility, next to the code it serves"))
    return out


# --- verify -----------------------------------------------------------------------------------

@dataclass
class StepResult:
    step: str
    command: str
    ok: bool
    seconds: float
    tail: str


def run(repo: Path, cmd: str, timeout: int = 1800) -> tuple[bool, str, float]:
    t0 = time.time()
    try:
        r = subprocess.run(cmd, shell=True, cwd=repo, capture_output=True, text=True, encoding="utf-8",  # noqa: S602 — the repo's own recorded command
                           errors="replace", timeout=timeout)
        ok, text = r.returncode == 0, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        ok, text = False, f"timed out after {timeout}s"
    except OSError as e:
        ok, text = False, str(e)
    return ok, "\n".join(text.strip().splitlines()[-40:]), time.time() - t0


def verify(repo: Path, steps: list[str] | None = None, fix: bool = False) -> list[StepResult]:
    q = load(repo)
    if q is None or q.problems:
        return []
    results = []
    cmds, fixes = effective(repo, q)
    if fix:
        for step in STEPS:
            for cmd in fixes.get(step, []):
                run(repo, cmd)
    for step in steps or STEPS:
        for cmd in cmds.get(step, []):
            ok, tail, secs = run(repo, cmd)
            results.append(StepResult(step, cmd, ok, secs, tail))
    return results


def agents_section(commands: dict[str, list[str]]) -> str:
    cmds = "\n".join(f"- {s}: `{'` · `'.join(commands[s])}`" for s in STEPS if commands.get(s)) or "- (none yet: they appear when code is added)"
    return ("\n## Code quality\n"
            "Run `groundwork.py verify` after every change (it runs the commands below) and fix what fails. Never weaken a rule,\n"
            "add an ignore comment or skip a test to make it pass; an ignore needs a reason on the same line.\n\n"
            f"{cmds}\n\n"
            "1. Reuse before writing: look in CODEMAP.md and search for an existing function first. Never copy-paste a block.\n"
            "2. Make the smallest change that meets the spec. No speculative abstractions, options or layers.\n"
            "3. Never swallow errors (no empty catch, no blind `except Exception`). Handle them at the entry point.\n"
            "4. Validate input where it enters (routes, commands, consumers). Parameterised SQL only; no shell built from input.\n"
            "5. Add a dependency only with the package manager, after checking it exists and is maintained; prefer what is already used.\n"
            "6. Comments say why, never what. No commented-out code; no TODO without a tracked item.\n"
            "7. Names come from the domain (PROJECT.md glossary); no Manager/Helper/Util names.\n"
            "8. Test behaviour through public functions; mock only connectors to outside systems. A test must fail when the code is wrong.\n"
            "9. Log through the project's logger, never print in core code, and never log secrets or personal data.\n"
            "10. Keep files under the size limit and functions short; split by responsibility.\n")


def ensure_agents_section(repo: Path, q: Quality) -> bool:
    """Add or refresh the Code quality section of AGENTS.md, so agents without the plugin follow it too."""
    p = C._find_ci(repo, "AGENTS.md")
    if p is None:
        return False
    text = p.read_text(encoding="utf-8")
    section = agents_section(effective(repo, q)[0])
    m = re.search(r"\n## Code quality\n.*?(?=\n## |\Z)", text, re.S)
    new = text[:m.start()] + section.rstrip("\n") + "\n" + text[m.end():] if m else text.rstrip("\n") + "\n" + section
    if new != text:
        p.write_text(new, encoding="utf-8")
        return True
    return False


def summary(q: Quality | None, has_code: bool) -> str:
    if q is None:
        return ("QUALITY NOT DECIDED: before writing code, use the code-quality skill to ask the user whether to adopt "
                "GroundWork's standard toolchain or keep this repo's own tools." if has_code else
                "QUALITY NOT DECIDED: new repo - set up the standard toolchain with the code-quality skill (groundwork.py quality init --create).")
    if q.problems:
        return 'QUALITY: the "quality" entry in .groundwork/config.json is invalid - ' + "; ".join(q.problems)
    how = "GroundWork standard toolchain" if q.mode == "standard" else "own tools, kept by choice"
    return (f"QUALITY ({how}): after every task run `groundwork.py verify` (format, lint, types, tests) and fix what fails. "
            "Never weaken a rule, add an ignore or skip a test to pass. Coding rules: AGENTS.md -> Code quality, code-quality skill.")
