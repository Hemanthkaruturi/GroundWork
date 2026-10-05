"""Credentials (STANDARD.md §5h): code reads secrets from environment variables; locally they come from `.env`.

Safety rules hold in every repo, whatever its layout decision:
  GW110  `.env` is not git-ignored                         (warning; `init` fixes it)
  GW111  a `.env` file is committed to git                 (error: it is a leak, not a style issue)
  GW113  something that looks like a real key is in a file that can be committed (warning)
Repos on the standard layout also keep the variable names documented, and front ends hold no secrets:
  GW112  a variable the code reads is missing from `.env.example`
  GW114  front-end code reads a secret-looking variable (it would ship to the browser)

Nothing here ever prints a secret: findings name the file, the line and the kind of key, never the value.
`.env` files themselves are never opened.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import groundwork_core as C
import groundwork_layout as L

EXAMPLES = {".env.example", ".env.sample", ".env.template", ".env.dist", ".env.defaults"}
IGNORE_BLOCK = "\n# Local secrets (GroundWork): never commit them; list the names in .env.example\n.env\n.env.*\n!.env.example\n"

KEY_PATTERNS = [
    ("an Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("an OpenAI API key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}")),
    ("an AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("a GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("a Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("a Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("a Stripe live key", re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{20,}")),
    ("a private key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY(?: BLOCK)?-----")),
]
SCAN_EXT = L.CODE_EXT | {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf", ".properties", ".xml",
                         ".tf", ".sh", ".ps1", ".rb", ".java", ".kt", ".cs", ".php", ".rs", ".swift", ".scala",
                         ".ipynb", ".md", ".txt", ".example", ".sample", ".template"}
SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "uv.lock", "poetry.lock", "Cargo.lock", "go.sum"}

ENV_NAME = {
    "py": re.compile(r"""\b(?:os\.)?(?:environ\s*\[\s*|environ\.get\s*\(\s*|getenv\s*\(\s*)['"]([A-Za-z_][A-Za-z0-9_]*)['"]"""),
    "js": re.compile(r"""\b(?:process\.env|import\.meta\.env|Bun\.env)(?:\.([A-Za-z_][A-Za-z0-9_]*)|\[\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]\s*\])"""),
    "go": re.compile(r"""\bos\.(?:Getenv|LookupEnv)\s*\(\s*"([A-Za-z_][A-Za-z0-9_]*)"\s*\)"""),
}
SECRET_NAME = re.compile(r"SECRET|PASSWORD|PASSWD|PRIVATE|TOKEN|CREDENTIAL|API_KEY$|ACCESS_KEY", re.I)
PUBLIC_NAME = re.compile(r"PUBLIC|PUBLISHABLE|ANON", re.I)
BUILTIN_VARS = {"NODE_ENV", "MODE", "DEV", "PROD", "SSR", "BASE_URL", "PATH", "HOME", "PWD", "CI", "PORT", "HOST",
                "HOSTNAME", "TZ", "LANG", "USER", "SHELL", "TERM", "TMPDIR", "DEBUG"}


@dataclass
class Finding:
    rule: str
    path: str
    message: str
    hint: str = ""


def _git(repo: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=20)
        return r.returncode, r.stdout
    except (OSError, subprocess.SubprocessError):
        return 128, ""


def is_env_file(name: str) -> bool:
    n = PurePosixPath(name).name
    return (n == ".env" or n.startswith(".env.")) and n not in EXAMPLES


def env_ignored(repo: Path) -> bool | None:
    """Would git ignore a `.env` at the repo root? None when git cannot tell."""
    code, _ = _git(repo, "check-ignore", "-q", "--no-index", ".env")
    if code in (0, 1):
        return code == 0
    gi = repo / ".gitignore"
    try:
        lines = [ln.strip() for ln in gi.read_text(encoding="utf-8").splitlines()]
    except OSError:
        return False
    return any(ln in (".env", "/.env", ".env*", "*.env", ".env.*") for ln in lines) and "!.env" not in lines


def ensure_ignored(repo: Path) -> bool:
    """Make git ignore `.env` files (keeping `.env.example` committable). True when the .gitignore was changed."""
    if env_ignored(repo):
        return False
    gi = repo / ".gitignore"
    old = gi.read_text(encoding="utf-8") if gi.is_file() else ""
    gi.write_text(old.rstrip("\n") + "\n" + IGNORE_BLOCK if old.strip() else IGNORE_BLOCK.lstrip("\n"), encoding="utf-8")
    return True


def committed_env_files(repo: Path) -> list[str]:
    code, out = _git(repo, "ls-files", "-z")
    if code != 0:
        return []
    return sorted(p for p in out.split("\0") if p and is_env_file(p))


def committable_files(repo: Path, limit: int = 8000) -> list[str]:
    """Files that are, or could be, committed: tracked plus untracked-but-not-ignored."""
    code, out = _git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if code == 0:
        files = [p for p in out.split("\0") if p]
    else:                                                  # not a git checkout: walk it, skipping hidden folders
        files = []
        for d, dirs, names in os.walk(repo):
            dirs[:] = [x for x in dirs if x not in C.SKIP_DIRS and not x.startswith(".")]
            files += [Path(d, n).relative_to(repo).as_posix() for n in names]
    keep = []
    for rel in files:
        p = PurePosixPath(rel)
        if any(part in C.SKIP_DIRS for part in p.parts[:-1]) or p.name in SKIP_NAMES or is_env_file(p.name):
            continue
        if p.suffix.lower() in SCAN_EXT or p.name in EXAMPLES:
            keep.append(rel)
        if len(keep) >= limit:
            break
    return keep


def pasted_keys(repo: Path) -> list[Finding]:
    out: list[Finding] = []
    for rel in committable_files(repo):
        p = repo / rel
        if p.is_symlink():
            continue
        try:
            if p.stat().st_size > 1_000_000:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for kind, rx in KEY_PATTERNS:
            m = rx.search(text)
            if m:
                out.append(Finding("GW113", rel, f"line {text.count(chr(10), 0, m.start()) + 1}: looks like {kind} written into the file",
                                   "move it to .env (git-ignored), read it from the environment in config/, and rotate the key: "
                                   "anything committed must be treated as leaked"))
                break
    return out


def example_names(repo: Path) -> tuple[Path | None, set[str]]:
    for n in sorted(EXAMPLES):
        p = repo / n
        if p.is_file():
            names = set(re.findall(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", p.read_text(encoding="utf-8", errors="replace"), re.M))
            return p, names
    return None, set()


def read_names(repo: Path, lay: L.Layout) -> dict[str, tuple[str, int, str | None]]:
    """Every literal environment variable name the code reads: name -> (file, line, role)."""
    found: dict[str, tuple[str, int, str | None]] = {}
    for rel in L.code_files(repo, lay):
        if L.is_test(rel) or L.is_legacy(lay, rel):
            continue
        lg = L.lang(rel)
        try:
            text = L._strip_comments((repo / rel).read_text(encoding="utf-8", errors="replace")[:300_000], lg)
        except OSError:
            continue
        for m in ENV_NAME[lg].finditer(text):
            name = next(g for g in m.groups() if g)
            if name not in BUILTIN_VARS and name not in found:
                found[name] = (rel, text.count("\n", 0, m.start()) + 1, L.layer_of(lay, rel))
    return found


def assess(repo: Path, cfg: dict | None = None) -> list[Finding]:
    out: list[Finding] = []
    for rel in committed_env_files(repo):
        out.append(Finding("GW111", rel, "a .env file is committed to git: every secret in it must be treated as leaked",
                           f"git rm --cached {rel}, make sure .gitignore ignores it, then rotate every credential it held"))
    if not env_ignored(repo):
        out.append(Finding("GW110", ".gitignore", ".env is not git-ignored, so local secrets can be committed by accident",
                           "run: groundwork.py init (it adds the lines), or add .env and .env.* (with !.env.example) to .gitignore"))
    out += pasted_keys(repo)
    lay = L.load(repo, cfg)
    if lay is None or lay.mode != "standard" or lay.problems:
        return out
    names = read_names(repo, lay)
    if lay.profile == "web":
        for name, (rel, line, role) in sorted(names.items()):
            if SECRET_NAME.search(name) and not PUBLIC_NAME.search(name):
                out.append(Finding("GW114", rel, f"line {line}: front-end code reads {name}; anything a browser app reads is shipped to every visitor",
                                   "keep secrets on a server and call it; front ends get only public values"))
    if lay.profile == "library" or not names:
        return out
    ex, listed = example_names(repo)
    missing = sorted(set(names) - listed)
    if ex is None:
        out.append(Finding("GW112", ".env.example", f"the code reads {len(names)} environment variable(s) but there is no .env.example",
                           "create .env.example with every name and no real values: " + ", ".join(sorted(names)[:8])))
    elif missing:
        out.append(Finding("GW112", ex.name, "variables the code reads are not listed: " + ", ".join(missing[:8])
                           + (f" (+{len(missing) - 8} more)" if len(missing) > 8 else ""),
                           "add each name with an empty or placeholder value; never a real secret"))
    return out


def example_stub(names: list[str] | None = None) -> str:
    body = "".join(f"{n}=\n" for n in names or [])
    return ("# Every environment variable this app reads, with NO real values. Commit this file.\n"
            "# Copy it to .env (git-ignored) and fill in real values locally; in production the platform sets them.\n" + body)


def summary(repo: Path) -> str:
    ex, _ = example_names(repo)
    ignored = env_ignored(repo)
    return ("Secrets: read from environment variables; locally from `.env` ("
            + ("git-ignored" if ignored else "NOT git-ignored") + ")"
            + (f"; names listed in `{ex.name}`" if ex else "") + ".")
