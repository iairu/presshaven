"""Query logic for the Forensics Analysis page (Qt-free): building a line
matcher from a plain-text or regular-expression query, the time-range
choices mapped to `docker compose logs --since`, search history and saved
searches, and plain-text / JSON-lines export of results."""
from __future__ import annotations

import json
import re
from typing import Callable

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# (label, `docker compose logs --since` value or None for no limit)
TIME_RANGES: list[tuple[str, str | None]] = [
    ("Any time", None), ("Last 5 minutes", "5m"), ("Last 15 minutes", "15m"), ("Last hour", "1h"),
    ("Last 6 hours", "6h"), ("Last 24 hours", "24h"), ("Last 7 days", "168h"),
]

HISTORY_LIMIT = 20
SAVED_LIMIT = 50


class QueryError(ValueError):
    """The query can't be used (empty, or an invalid regular expression)."""


def compile_matcher(query: str, regex: bool = False, case_sensitive: bool = False) -> Callable[[str], bool]:
    """A function line -> bool. Plain mode is a substring test; regex mode
    uses re.search. Raises QueryError for an empty query or a bad pattern."""
    if not query:
        raise QueryError("Enter something to search for.")
    if regex:
        try:
            pattern = re.compile(query, 0 if case_sensitive else re.IGNORECASE)
        except re.error as e:
            raise QueryError(f"Invalid regular expression: {e}")
        return lambda line: pattern.search(line) is not None
    if case_sensitive:
        return lambda line: query in line
    needle = query.lower()
    return lambda line: needle in line.lower()


def since_args(since: str | None) -> list[str]:
    return ["--since", since] if since else []


def push_history(history: list[str], query: str, limit: int = HISTORY_LIMIT) -> list[str]:
    """`history` with `query` moved/added to the front (most recent first),
    de-duplicated and capped. Blank queries are ignored."""
    query = query.strip()
    if not query:
        return list(history)
    return ([query] + [h for h in history if h != query])[:limit]


def save_search(saved: list[dict], name: str, query: str, regex: bool, case_sensitive: bool,
                since: str | None) -> list[dict]:
    """`saved` with a named search added, replacing one of the same name."""
    name = name.strip()
    if not name or not query:
        raise QueryError("A saved search needs a name and a query.")
    entry = {"name": name, "query": query, "regex": bool(regex), "case": bool(case_sensitive), "since": since}
    return ([entry] + [s for s in saved if s.get("name") != name])[:SAVED_LIMIT]


def delete_search(saved: list[dict], name: str) -> list[dict]:
    return [s for s in saved if s.get("name") != name]


def clean_line(line: str) -> str:
    return ANSI_RE.sub("", line)


def export_text(lines: list[str]) -> str:
    """Plain text, one result per line, colour codes removed."""
    return "\n".join(clean_line(l) for l in lines) + ("\n" if lines else "")


_PREFIX = re.compile(r"^\[(?P<target>[^\]]*)\]\s?(?P<rest>.*)$")


def export_jsonl(lines: list[str]) -> str:
    """JSON lines: {"target", "line"} per result, for loading into other tools."""
    out = []
    for l in lines:
        clean = clean_line(l)
        m = _PREFIX.match(clean)
        out.append(json.dumps({"target": m.group("target"), "line": m.group("rest")} if m
                              else {"target": "", "line": clean}, ensure_ascii=False))
    return "\n".join(out) + ("\n" if out else "")
