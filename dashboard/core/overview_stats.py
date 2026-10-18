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
from dataclasses import dataclass

from core.colors import GREEN, GREY, ORANGE, RED
from core.container_status import (
    classify, summarize, CREATED, DOWN, EXITED_BAD, EXITED_OK, HEALTHY, RUNNING, STARTING, UNHEALTHY,
)

# Per-project operational states, worst-last.
OFFLINE, STOPPED, STARTING_UP, OPERATIONAL, DEGRADED = (
    "offline", "stopped", "starting", "operational", "degraded")

# A container whose process is genuinely up right now (vs. a one-shot job
# that exited cleanly, which is "done", not "running").
_RUNNING_STATES = (HEALTHY, RUNNING, STARTING, UNHEALTHY)

_STATE_COLOR = {OPERATIONAL: GREEN, STARTING_UP: ORANGE, DEGRADED: RED,
                STOPPED: ORANGE, OFFLINE: GREY}


@dataclass(frozen=True)
class ProjectHealth:
    project: str
    label: str
    state: str
    running: int      # containers with a live process
    total: int

    @property
    def color(self) -> str:
        return _STATE_COLOR[self.state]

    @property
    def up(self) -> bool:
        return self.state in (OPERATIONAL, STARTING_UP)

    @property
    def text(self) -> str:
        if self.state == OFFLINE:
            return "not running"
        if self.state == STOPPED:
            return f"stopped ({self.total} container(s) not running)"
        if self.state == DEGRADED:
            return f"{self.running}/{self.total} running, problems detected"
        if self.state == STARTING_UP:
            return f"starting ({self.running}/{self.total})"
        return f"all {self.total} up"


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


def project_health(results: dict, project: str, label: str = "") -> ProjectHealth:
    """Operational state of a whole project. Unlike summarize(), a stack
    with containers that have ALL exited counts as "stopped", not "up" --
    an exited-0 long-running service is not operational just because its
    exit code was clean (that leniency is only right for one-shot jobs,
    which never make up a whole stack)."""
    containers = project_containers(results, project)
    statuses = [classify(c) for c in containers]
    running = sum(1 for s in statuses if s in _RUNNING_STATES)
    if not containers:
        state = OFFLINE
    elif any(s in (UNHEALTHY, EXITED_BAD) for s in statuses):
        state = DEGRADED
    elif running == 0:
        # Containers exist but none have a live process (all exited/created).
        state = STOPPED
    elif any(s in (STARTING, CREATED) for s in statuses):
        state = STARTING_UP
    else:
        state = OPERATIONAL
    return ProjectHealth(project, label or project, state, running, len(containers))


def system_summary(healths: list[ProjectHealth]) -> tuple[str, str, str]:
    """(headline, color, caption) across every stack. "Operational" ONLY
    when every stack is up -- a stack being down names which one, so the
    chip can never read green while the honeypot (or the SIEM) is off."""
    if not healths:
        return "Idle", GREY, "no containers running"
    caption = " · ".join(f"{h.label.split()[0].lower()} {_short(h.state)}" for h in healths)
    if any(h.state == DEGRADED for h in healths):
        return "Degraded", RED, caption
    down = [h for h in healths if h.state in (OFFLINE, STOPPED)]
    up = [h for h in healths if h.up]
    if down and up:
        names = " and ".join(h.label.split()[0] for h in down)
        return f"{names} down", RED if any(h.project == "edge" for h in down) else ORANGE, caption
    if down and not up:
        return "Offline", GREY, caption
    if any(h.state == STARTING_UP for h in healths):
        return "Starting", ORANGE, caption
    return "Operational", GREEN, caption


def _short(state: str) -> str:
    return {OPERATIONAL: "up", STARTING_UP: "starting", DEGRADED: "degraded",
            STOPPED: "stopped", OFFLINE: "down"}[state]


# Fallback decay half-life when the detector's own setting isn't plumbed
# through to the Overview page -- matches SCORE_DECAY_HALF_LIFE_SECONDS'
# documented default (core/detection_policy.py).
DEFAULT_HALF_LIFE_SECONDS = 300


def posture_score(events: list[dict], half_life: float = DEFAULT_HALF_LIFE_SECONDS,
                  now: float | None = None) -> int | None:
    """A decayed "current risk" from the persisted notable-event history,
    instead of whatever the single most recent request happened to score.

    Each event that carries a numeric score contributes that score decayed
    by its age -- peak * 0.5**(elapsed / half_life), the same exponential
    half-life the detector itself uses (core/detection_policy.decayed) -- and
    the posture is the strongest surviving contribution. So a score of 100
    from a honeypot routing fades back toward 0 over the following minutes
    unless fresh high-scoring activity keeps it up. Returns None when the
    history holds no scored event yet."""
    now = time.time() if now is None else now
    best: float | None = None
    for e in events:
        s = e.get("score")
        # Guard against bools (a subclass of int) and missing/None scores;
        # routing/signal context lines carry no score and don't contribute.
        if not isinstance(s, (int, float)) or isinstance(s, bool):
            continue
        elapsed = max(0.0, now - e.get("timestamp", 0))
        decayed = s * (0.5 ** (elapsed / half_life)) if half_life > 0 else float(s)
        if best is None or decayed > best:
            best = decayed
    return None if best is None else max(0, round(best))


def unique_diverted_ips(sessions) -> int:
    """How many distinct source IPs are currently routed to a honeypot --
    i.e. how many real attackers are being diverted right now, from the
    live session store (session_view.SessionSummary.diverted), rather than
    how many diversion *events* have been logged over time. `sessions` is a
    list of SessionSummary (anything with `.ip` and a `.diverted` flag)."""
    return len({s.ip for s in sessions if getattr(s, "diverted", False) and s.ip})


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
