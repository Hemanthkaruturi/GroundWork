"""One owner per fact (STANDARD.md §4): a downstream document cites its upstream, it does not copy it.

`shared_units` finds sentences that appear in both a document and the document that owns them
(spec vs RFC, plan/tasks/evals vs spec, an ADR vs its RFC). It is a plain text comparison, no model:
front matter, HTML comments, code blocks, headings and table rules are ignored, markdown decoration is
stripped, and only sentences of at least MIN_WORDS words count, so a short pointer such as
"As RFC-0001 §9." never fires.
"""

from __future__ import annotations

import re

MIN_WORDS = 8

_FM = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_CODE = re.compile(r"```.*?```", re.DOTALL)
_LEAD = re.compile(r"^\s*(?:[-*+]|\d+[.)]|\|)\s*")
_MARK = re.compile(r"[*_`>|]")
_SPLIT = re.compile(r"(?<=[.!?])\s+")
_LABEL = re.compile(r"^[A-Za-z][A-Za-z0-9 /-]{0,30}:\s+")
_CITE = re.compile(
    r"\s*\((?:covers |see |as |rfc|spec|§|fr-|ac-|nfr-)[^)]*\)\s*$", re.IGNORECASE
)


def units(text: str) -> list[str]:
    """The sentences of a document, normalised, long enough to be worth comparing."""
    text = _CODE.sub("", _COMMENT.sub("", _FM.sub("", text)))
    out: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        if re.fullmatch(r"\s*\|?[\s|:-]*\|?\s*", line):
            continue  # a table rule or an empty line
        for cell in line.split(" | ") if "|" in line else [line]:
            cell = _LEAD.sub("", cell)
            for s in _SPLIT.split(cell):
                s = _normalise(s)
                if len(s.split()) >= MIN_WORDS:
                    out.append(s)
    return out


def _normalise(s: str) -> str:
    """Lower-case words only: no markdown, no leading label ("Done means:"), no trailing citation."""
    s = _MARK.sub("", s)
    s = _LABEL.sub("", s)
    s = _CITE.sub("", s)
    s = re.sub(r"[.!?;,]+$", "", s.strip())
    return re.sub(r"\s+", " ", s).strip().lower()


def shared_units(owner_text: str, copy_text: str) -> list[str]:
    """Sentences of `copy_text` that `owner_text` already states, in the copy's order, each once."""
    owned = set(units(owner_text))
    seen: set[str] = set()
    hits: list[str] = []
    for u in units(copy_text):
        if u in owned and u not in seen:
            seen.add(u)
            hits.append(u)
    return hits


def describe(hits: list[str], owner: str) -> str:
    first = hits[0]
    if len(first) > 70:
        first = first[:67].rstrip() + "…"
    n = len(hits)
    return f"{n} sentence{'s' if n != 1 else ''} repeat{'' if n != 1 else 's'} text {owner} owns; first: “{first}”"
