"""Qt-free pieces of the Services start-up report (core/services_report.py),
kept apart so they are unit tested without PyQt: turning successive
`docker compose ps -a` snapshots into start-up events, and listing what a
finished start should warn about."""
from __future__ import annotations

from core.container_status import classify
from core.log_error_match import _ANSI_RE, _PREFIX_RE, is_error_log_line


def detect_events(prev: dict, cur: dict, elapsed: float, events: list) -> None:
    """Append human-readable transition events by diffing per-service status
    (container_status.classify() states from `docker compose ps -a`).

    `up` creates every container first and starts each one only once its
    depends_on conditions hold, so a container first seen as "created" is
    reported as created, and as "started" only when it really runs. A
    one-shot job is reported "finished" when ps shows it exited 0; its later
    disappearance (the Services page removes finished jobs after `up`) is
    "removed", not "stopped", so neither distorts how long the job ran."""
    def add(label):
        if not events or events[-1][1] != label:
            events.append((round(elapsed, 1), label))
    running = ("starting", "running", "healthy", "unhealthy")
    for svc, st in cur.items():
        was = prev.get(svc)
        if st == was:
            continue
        if was is None and st == "created":
            add(f"{svc} created")
        elif st == "starting":
            add(f"{svc} running, health pending")
        elif st in ("running",) and was in (None, "created", "exited_ok", "exited_bad", "down"):
            add(f"{svc} started")
        elif st == "healthy":
            add(f"{svc} healthy")
        elif st == "unhealthy":
            add(f"{svc} unhealthy")
        elif st == "exited_ok":
            add(f"{svc} finished")
        elif st == "exited_bad":
            add(f"{svc} exited (error)")
        elif was is None and st in running:
            add(f"{svc} started")
    for svc, was in prev.items():
        if svc not in cur:
            add(f"{svc} removed" if was in ("exited_ok", "exited_bad", "created") else f"{svc} stopped")


def start_warnings(ps: list[dict], log_text: str, max_examples: int = 1) -> list[tuple[str, str]]:
    """What a finished start should flag, from `docker compose ps -a` and the
    logs written during it: containers that exited with an error, were never
    started or are unhealthy, and services with error lines -- the same
    lines that put a red badge on their tile in the Global Visualization
    page, so the report says what the badge only hints at."""
    out: list[tuple[str, str]] = []
    for c in ps:
        svc = c.get("Service") or c.get("Name") or "?"
        state = classify(c)
        if state == "exited_bad":
            out.append((svc, f"exited with code {c.get('ExitCode')}"))
        elif state == "created":
            out.append((svc, "created but never started"))
        elif state == "unhealthy":
            out.append((svc, "unhealthy"))
    counts: dict[str, int] = {}
    examples: dict[str, list[str]] = {}
    for raw in log_text.splitlines():
        plain = _ANSI_RE.sub("", raw)
        m = _PREFIX_RE.match(plain)
        if not m or not is_error_log_line(raw):
            continue
        svc = m.group("service")
        counts[svc] = counts.get(svc, 0) + 1
        if len(examples.setdefault(svc, [])) < max_examples:
            examples[svc].append(m.group("message").strip()[:220])
    for svc in sorted(counts, key=lambda k: -counts[k]):
        out.append((svc, f"{counts[svc]} error line(s) in its log, e.g. "
                         + " / ".join(f"\u201c{e}\u201d" for e in examples[svc])))
    return out


# Per-container charts: past this many services one chart becomes unreadable,
# so they are split into role groups, one chart pair per group.
MAX_SERIES_PER_CHART = 8

_GROUPS = (  # (title, test) in display order; the first match wins
    ("One-shot jobs", lambda s: any(k in s for k in ("init", "seed", "migration", "setup",
                                                      "password"))),
    ("Databases", lambda s: "database" in s or s in ("es01",)),
    ("Shops", lambda s: "eshop" in s),
)


def chart_groups(services: list[str]) -> list[tuple[str, list[str]]]:
    """[(title, services)] for the per-container charts: one group with
    everything while that fits MAX_SERIES_PER_CHART, else role groups
    (one-shot jobs, databases, shops, then edge & monitoring), each split
    again into chunks of MAX_SERIES_PER_CHART if needed."""
    services = sorted(services)
    if len(services) <= MAX_SERIES_PER_CHART:
        return [("", services)]
    buckets: dict[str, list[str]] = {}
    for svc in services:
        title = next((t for t, test in _GROUPS if test(svc)), "Edge & monitoring")
        buckets.setdefault(title, []).append(svc)
    out = []
    for title in [t for t, _ in _GROUPS] + ["Edge & monitoring"]:
        members = buckets.get(title, [])
        for i in range(0, len(members), MAX_SERIES_PER_CHART):
            part = members[i:i + MAX_SERIES_PER_CHART]
            suffix = f" ({i // MAX_SERIES_PER_CHART + 1})" if len(members) > MAX_SERIES_PER_CHART else ""
            out.append((title + suffix, part))
    return out
