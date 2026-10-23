"""Ranking for the Ctrl+K command palette (Qt-free): each command has a
title, an optional group and extra keywords; a query is matched against
them with a small fuzzy scorer (prefix > word start > substring >
in-order letters) and results are ordered best first."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    id: str            # "page:overview", "action:wizard" ...
    title: str
    group: str = ""
    keywords: str = ""   # extra searchable words (a page's one-line summary, synonyms)
    icon: str = ""       # optional page id for a UI icon (core stays Qt-free)


def _subsequence(needle: str, hay: str) -> bool:
    it = iter(hay)
    return all(ch in it for ch in needle)


def score(query: str, text: str, fuzzy: bool = True) -> int | None:
    """Higher is better; None when `text` doesn't match. Case-insensitive.
    `fuzzy` enables the in-order-letters fallback -- for short titles only;
    on long keyword text it matches almost anything."""
    q, t = query.lower().strip(), text.lower()
    if not q:
        return 0
    if t == q:
        return 100
    if t.startswith(q):
        return 90
    if any(w.startswith(q) for w in t.replace("-", " ").replace("&", " ").split()):
        return 75
    if q in t:
        return 60
    if fuzzy and _subsequence(q.replace(" ", ""), t.replace(" ", "")):
        return 30
    return None


def rank(query: str, commands: list[Command]) -> list[Command]:
    """Commands matching `query`, best first. A title match always beats a
    group/keyword match; ties keep the original order. An empty query
    returns everything unchanged."""
    if not query.strip():
        return list(commands)
    scored = []
    for i, c in enumerate(commands):
        title = score(query, c.title)
        other = max((s for s in (score(query, c.group, fuzzy=False), score(query, c.keywords, fuzzy=False))
                     if s is not None),
                    default=None)
        if title is None and other is None:
            continue
        # Title matches are lifted above any group/keyword-only match.
        best = (1000 + title) if title is not None else other
        scored.append((-best, i, c))
    return [c for _s, _i, c in sorted(scored, key=lambda x: (x[0], x[1]))]
