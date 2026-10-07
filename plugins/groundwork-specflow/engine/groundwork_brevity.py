"""Plain, short writing: measure it, and (optionally) insist on it.

Documents get soft size budgets and a sentence-length check (`groundwork check`). Chat replies can be
held to a word budget by a Stop hook when `"brevity": "enforce"` is set in .groundwork/config.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_REPLY_WORDS = 220
DOC_BUDGETS = {  # words of prose (front matter, comments, code, tables excluded)
    "spec": 1200,
    "rfc": 1800,
    "plan": 1200,
    "bug": 700,
    "project": 900,
    "architecture": 1600,
    "constitution": 700,
    "agents": 900,
    "handover": 900,
}
MAX_AVG_SENTENCE = 26  # words


def prose(text: str) -> str:
    """The part of a document a person actually reads as sentences."""
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", "x", text)
    lines = [
        ln for ln in text.splitlines() if not ln.lstrip().startswith(("|", "#", ">"))
    ]
    text = "\n".join(lines)
    text = re.sub(r"\[[^\]]*\]\([^)]*\)", "link", text)
    return re.sub(r"https?://\S+", "url", text)


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", prose(text)))


def avg_sentence(text: str) -> float:
    body = prose(text)
    sentences = [
        s
        for s in re.split(r"(?<=[.!?])\s+|\n\s*[-*]\s+|\n{2,}", body)
        if len(s.split()) >= 4
    ]
    if len(sentences) < 5:
        return 0.0
    return sum(len(s.split()) for s in sentences) / len(sentences)


def budget_for(path: Path, kind: str | None = None) -> int | None:
    name = (kind or path.stem).lower()
    if name.startswith("rfc-"):
        name = "rfc"
    if path.parent.parent.name == "specs" or path.parent.name.startswith(
        tuple("0123456789")
    ):
        name = {"spec": "spec", "plan": "plan"}.get(name, name)
    if path.parent.name == "bugs":
        name = "bug"
    return DOC_BUDGETS.get(name)


# --- chat replies ---------------------------------------------------------------------


def last_reply_text(transcript: Path) -> str:
    """All assistant text since the last real user message."""
    try:
        rows = [
            json.loads(ln)
            for ln in transcript.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
    except (OSError, ValueError):
        return ""
    texts: list[str] = []
    for r in rows:
        msg = r.get("message") or {}
        role = msg.get("role") or r.get("type")
        content = msg.get("content")
        if role == "user":
            is_tool_result = isinstance(content, list) and any(
                isinstance(c, dict) and c.get("type") == "tool_result" for c in content
            )
            if not is_tool_result:
                texts = []
        elif role == "assistant" and isinstance(content, list):
            texts += [
                c.get("text", "")
                for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            ]
    return "\n".join(texts)


def reply_words(text: str) -> int:
    return words(text.replace("#", ""))  # headings inside a reply are prose too


MUST_KEEP = (
    "Shorter must never mean less true. Every one of these survives, in one line each if need be: the decision the user must make; "
    "anything that failed or was skipped; what you did NOT verify or are unsure of; risks and side effects (what could break, "
    "what changed outside the ask); every file or setting you changed; assumptions you made; blockers; what the user must do next."
)

SHORTEN = (
    "Your last reply was about {n} words; the limit here is {limit}. The full text is saved at {saved}. Rewrite the reply now, "
    "shorter and plainer, WITHOUT losing information: cut only repetition, narration of steps, and background the reader already "
    "knows. "
    + MUST_KEEP
    + " Answer or decision first; short sentences; everyday words; explain any ID or term in a few words "
    "instead of citing it bare; ask questions with the picker, not as a list. End with one line: 'Full detail: {saved}'. Do not add new work."
)


def save_full_reply(root: Path, text: str) -> Path:
    """Keep the original, so shortening can never lose anything."""
    import time

    d = root / ".groundwork" / "replies"
    d.mkdir(parents=True, exist_ok=True)
    gi = d.parent / ".gitignore"
    if gi.exists() and "replies/" not in gi.read_text(encoding="utf-8"):
        gi.write_text(
            gi.read_text(encoding="utf-8").rstrip("\n") + "\nreplies/\n",
            encoding="utf-8",
        )
    p = d / (time.strftime("%Y%m%d-%H%M%S") + ".md")
    p.write_text(text.rstrip() + "\n", encoding="utf-8")
    return p
