"""Qt-free helpers for the Live Events page (ui/page_live_events.py):
severity levels derived from the parser's colours, the view filters, and
plain-text/CSV export of the visible rows."""
from __future__ import annotations

import calendar
import csv
import io
import re
import time

from core.pattern_log_parser import (
    COLOR_HIGH, COLOR_INFO, COLOR_LOW, COLOR_MED, LineBuffer, parse_line,
)

SEVERITY_ORDER = ["info", "low", "medium", "high"]
_COLOR_TO_SEVERITY = {COLOR_INFO: "info", COLOR_LOW: "low", COLOR_MED: "medium", COLOR_HIGH: "high"}

# View filters offered on the page: id -> label.
FILTERS = {
    "all": "All events",
    "medium": "Medium and above",
    "high": "High severity only",
    "diversions": "Honeypot diversions",
    "outcomes": "Per-request outcomes",
}


def severity(color: str) -> str:
    return _COLOR_TO_SEVERITY.get(color, "info")


def severity_rank(color: str) -> int:
    return SEVERITY_ORDER.index(severity(color))


def matches(filter_id: str, kind: str, label: str, color: str, text: str = "") -> bool:
    """Whether an event passes the view filter `filter_id` and the free-text
    `text` (case-insensitive substring of label+detail, passed pre-joined
    by the caller as `label` plus detail in `text`)."""
    if filter_id == "medium" and severity_rank(color) < SEVERITY_ORDER.index("medium"):
        return False
    if filter_id == "high" and severity(color) != "high":
        return False
    if filter_id == "diversions" and "HONEYPOT" not in label.upper():
        return False
    if filter_id == "outcomes" and kind != "outcome":
        return False
    return True


def text_matches(needle: str, *fields: str) -> bool:
    needle = needle.strip().lower()
    return not needle or any(needle in f.lower() for f in fields)


def format_time(ts: int) -> str:
    return time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "--:--:--"


_RFC3339_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})")


def rfc3339_to_epoch(ts: str | None) -> int:
    """Epoch seconds from a `docker compose logs --timestamps` RFC3339
    string (always UTC/Z here), 0 when it's missing or unparseable."""
    if not ts:
        return 0
    m = _RFC3339_RE.match(ts)
    if not m:
        return 0
    return calendar.timegm(tuple(int(g) for g in m.groups()) + (0, 0, 0))


def parse_backfill(text: str) -> list[tuple[int, object]]:
    """Parse a `docker compose logs --timestamps reverse_proxy` tail into
    (epoch, PatternEvent) rows, oldest first, so a freshly-opened feed is
    not blank. Lines the parser doesn't recognise are skipped; each event's
    own log timestamp is used (0 when absent)."""
    buffer = LineBuffer()
    rows: list[tuple[int, object]] = []
    for line in buffer.feed(text + "\n"):
        event = parse_line(line)
        if event is not None:
            rows.append((rfc3339_to_epoch(event.timestamp), event))
    return rows


def to_csv(rows: list[tuple[int, str, str, str, str]]) -> str:
    """rows: (timestamp, severity, kind, label, detail)."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["time", "severity", "kind", "label", "detail"])
    for ts, sev, kind, label, detail in rows:
        iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)) if ts else ""
        writer.writerow([iso, sev, kind, label, detail])
    return out.getvalue()
