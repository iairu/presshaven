"""Qt-free summary math for the Overview page (ui/page_overview.py).

Turns the two live data sources the dashboard already has -- the status
poller's per-target `docker compose ps` results and the security feed's
persisted notable-event history (core/state.security_events) -- into the
handful of numbers a landing page shows at a glance. Kept here, with no Qt
imports, so the counting is unit-testable headless (tests/
test_overview_stats.py) the same way every other core module is.
"""
from __future__ import annotations

import time

from core.colors import GREEN, GREY, ORANGE, RED
from core.container_status import classify, summarize, HEALTHY, RUNNING, UNHEALTHY, EXITED_OK

# Severity ranking of the semantic colors, so the worst project drives the
# overall health chip.
_SEVERITY = {GREEN: 0, GREY: 1, ORANGE: 2, RED: 3}


def project_containers(results: dict, project: str) -> list[dict]:
    """Every container for `project` across its local and remote targets.

    `results` is StatusPoller's dict keyed by Target.key ("edge-local",
    "edge-remote", "siem-local", ...); a project's targets are exactly the
    keys that start with "<project>-"."""
    containers: list[dict] = []
    for key, target_containers in results.items():
        if key.split("-", 1)[0] == project:
            containers.extend(target_containers)
    return containers


def project_summary(results: dict, project: str) -> tuple[str, str, int, int]:
    """(summary_text, color, up, total) for a whole project -- the same
    vocabulary ui/page_services.py shows per target, aggregated across
    local+remote so the Overview shows one line per stack."""
    containers = project_containers(results, project)
    text, color = summarize(containers)
    up = sum(1 for c in containers if classify(c) in (HEALTHY, RUNNING, UNHEALTHY, EXITED_OK))
    return text, color, up, len(containers)


def overall_color(colors: list[str]) -> str:
    """The worst (most severe) of several status colors -- for a single
    "system health" chip summarising every stack at once."""
    if not colors:
        return GREY
    return max(colors, key=lambda c: _SEVERITY.get(c, 1))


def is_diversion(event: dict) -> bool:
    """A recorded event that represents a session being routed to a
    honeypot (vs. a CVE/high-severity signal or a dependency warning).
    The security feed only keeps COLOR_HIGH events, so "HONEYPOT" in the
    label is the reliable marker of a diversion among them."""
    return "HONEYPOT" in (event.get("label", "") or "").upper()


def count_since(events: list[dict], since_ts: float, predicate=None) -> int:
    """How many events are at or after `since_ts` (and match `predicate`,
    if given). `events` are core/state.security_events dicts, each with a
    unix "timestamp"."""
    n = 0
    for e in events:
        if e.get("timestamp", 0) >= since_ts and (predicate is None or predicate(e)):
            n += 1
    return n


def event_window_counts(events: list[dict], window_seconds: int = 3600,
                        now: float | None = None) -> dict:
    """Counts over the last `window_seconds`: total notable events and how
    many of them were honeypot diversions, plus the all-time totals and the
    most recent event's timestamp (None when the history is empty)."""
    now = time.time() if now is None else now
    since = now - window_seconds
    last_ts = max((e.get("timestamp", 0) for e in events), default=0) or None
    return {
        "window_total": count_since(events, since),
        "window_diversions": count_since(events, since, is_diversion),
        "total": len(events),
        "total_diversions": sum(1 for e in events if is_diversion(e)),
        "last_timestamp": last_ts,
    }
