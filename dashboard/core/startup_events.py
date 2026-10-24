"""Qt-free pieces of the Services start/stop report (core/services_report.py),
kept apart so they are unit tested without PyQt: turning successive
`docker compose ps -a` snapshots into events, grouping them into numbered
markers, listing what a finished start or stop should warn about, and the
chart arithmetic (round axis ticks, sample gaps, a dominating series)."""
from __future__ import annotations

import math
import re

from core.container_status import classify, STOPPED
from core.log_error_match import _ANSI_RE, _PREFIX_RE, is_error_log_line


def detect_events(prev: dict, cur: dict, elapsed: float, events: list,
                  operation: str = "start") -> None:
    """Append human-readable transition events by diffing per-service status
    (container_status.classify() states from `docker compose ps -a`).

    `up` creates every container first and starts each one only once its
    depends_on conditions hold, so a container first seen as "created" is
    reported as created, and as "started" only when it really runs. A
    one-shot job is reported "finished" when ps shows it exited 0; its later
    disappearance (the Services page removes finished jobs after `up`) is
    "removed", not "stopped", so neither distorts how long the job ran.

    During a stop (``operation="stop"``) `down` stops each container and then
    removes it. A running container seen exited is "stopped" (not "finished",
    which is one-shot-job wording), and one that is gone is "removed" -- or
    "stopped and removed" when ps never caught it in between."""
    def add(label):
        if not events or events[-1][1] != label:
            events.append((round(elapsed, 1), label))
    running = ("starting", "running", "healthy", "unhealthy")
    stop = operation == "stop"
    for svc, st in cur.items():
        was = prev.get(svc)
        if st == was:
            continue
        if stop and st in ("exited_ok", "exited_bad") and was in running:
            add(f"{svc} stopped" if st == "exited_ok" else f"{svc} stopped (non-zero exit)")
        elif was is None and st == "created":
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
            if was in ("exited_ok", "exited_bad", "created"):
                add(f"{svc} removed")
            else:
                add(f"{svc} stopped and removed" if stop else f"{svc} stopped")


# How detect_events words each state, so a marker's events can be grouped
# by what happened ("healthy: a, b, c") instead of repeating the verb.
# Longer wordings first: "x stopped and removed" must not match "removed".
EVENT_STATES = ("running, health pending", "stopped (non-zero exit)", "stopped and removed",
                "exited (error)", "created", "started", "finished", "healthy", "unhealthy",
                "removed", "stopped")


def event_state(label: str) -> tuple[str, str]:
    """'es01 stopped and removed' -> ('es01', 'stopped and removed')."""
    state = next((st for st in EVENT_STATES if label.endswith(" " + st)), "")
    return (label[: -len(state) - 1] if state else label), state


# Events within this many seconds of a marker's FIRST event share its number.
# `ps` runs every ~1.5 s (plus the ~0.5-1 s the call itself takes), so in
# practice one marker is the changes seen in one status check. Measured from
# the first event, not chained event to event: chaining merged a whole start
# phase (one change per check) into a single marker many seconds wide.
MARKER_WINDOW_S = 1.5


def event_markers(events: list, window: float = MARKER_WINDOW_S) -> list[tuple[int, float, float, list[str]]]:
    """Group ``events`` ((elapsed, label), ...) into numbered markers:
    ``(number, first_t, last_t, labels)``. A marker opens at an event and
    takes in every later event at most ``window`` seconds after that first
    one, so no marker spans more than ``window``."""
    out: list[tuple[int, float, float, list[str]]] = []
    for t, label in sorted(events, key=lambda e: e[0]):
        if out and t - out[-1][1] <= window + 1e-9:
            n, t0, _t1, labels = out[-1]
            out[-1] = (n, t0, t, labels + [label])
        else:
            out.append((len(out) + 1, t, t, [label]))
    return out


def peak_context(tp: float, markers: list, first_sample_t: float | None = None,
                 near_s: float = 1.5) -> str:
    """Where a peak at ``tp`` sits relative to the event markers, in words:
    'at marker 3', 'between markers 6 and 7', 'before marker 1', '4 s after
    marker 8'. The first sample of a recording is said to be so: its value
    covers the moment the command was launched, before any event."""
    first = first_sample_t is not None and abs(tp - first_sample_t) < 1e-6
    suffix = " (the first sample of the recording)" if first else ""
    if not markers:
        return "no logged event" + suffix
    for n, t0, t1, _labels in markers:
        if t0 - near_s <= tp <= t1 + near_s:
            return f"at marker {n}" + suffix
    if tp < markers[0][1]:
        return f"before marker {markers[0][0]}" + suffix
    for (n0, _a, t1, _l0), (n1, t0, _b, _l1) in zip(markers, markers[1:]):
        if t1 < tp < t0:
            return f"between markers {n0} and {n1}" + suffix
    n, _t0, t1, _labels = markers[-1]
    return f"{tp - t1:.0f} s after marker {n}" + suffix


# The level a log line declares for itself: Kibana's "[ts][WARN ][ctx]",
# "level=warn", "[warn]", " WARN " and the like. Only used to word a
# warning; which lines count is still is_error_log_line(), the badge's test.
_LEVEL_RE = re.compile(r"(?<![A-Za-z])(TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|ERR|FATAL|CRIT(?:ICAL)?|"
                       r"PANIC)(?![A-Za-z])", re.IGNORECASE)


def _line_level(message: str) -> str:
    m = _LEVEL_RE.search(message[:80])
    if not m:
        return ""
    level = m.group(1).upper()
    return {"WARNING": "WARN", "ERR": "ERROR", "CRITICAL": "CRIT"}.get(level, level)


def log_warnings(log_text: str, max_examples: int = 1) -> list[tuple[str, str]]:
    """Services with log lines the Global Visualization page's red badge
    counts (log_error_match.is_error_log_line(): an "error", "fail..." or
    "fault..." word), worded by the level each line declares, so a WARN line
    that merely mentions an error is not called an error line."""
    counts: dict[str, int] = {}
    levels: dict[str, dict[str, int]] = {}
    examples: dict[str, list[str]] = {}
    for raw in log_text.splitlines():
        plain = _ANSI_RE.sub("", raw)
        m = _PREFIX_RE.match(plain)
        if not m or not is_error_log_line(raw):
            continue
        svc = m.group("service")
        msg = m.group("message").strip()
        counts[svc] = counts.get(svc, 0) + 1
        lvl = _line_level(msg)
        levels.setdefault(svc, {})[lvl] = levels.get(svc, {}).get(lvl, 0) + 1
        if len(examples.setdefault(svc, [])) < max_examples:
            examples[svc].append(msg[:220])
    out = []
    for svc in sorted(counts, key=lambda k: -counts[k]):
        by_level = levels[svc]
        if set(by_level) <= {"WARN"}:
            what = f"{counts[svc]} WARN line(s) mentioning an error"
        elif set(by_level) <= {"ERROR", "FATAL", "CRIT", "PANIC"}:
            what = f"{counts[svc]} error line(s)"
        else:
            parts = [f"{n} {lvl}" for lvl, n in sorted(by_level.items(), key=lambda kv: -kv[1]) if lvl]
            unlevelled = by_level.get("", 0)
            if unlevelled:
                parts.append(f"{unlevelled} without a level")
            what = f"{counts[svc]} line(s) with an error word ({', '.join(parts)})"
        out.append((svc, what + " in its log, e.g. "
                    + " / ".join(f"\u201c{e}\u201d" for e in examples[svc])))
    return out


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
        elif state == STOPPED:
            # Clean exit, but a long-running service -- it is off, not "done".
            out.append((svc, "exited (code 0) though it should stay running"))
        elif state == "created":
            out.append((svc, "created but never started"))
        elif state == "unhealthy":
            out.append((svc, "unhealthy"))
    return out + log_warnings(log_text, max_examples)


def stop_warnings(exit_codes: dict[str, int], log_text: str,
                  max_examples: int = 1) -> list[tuple[str, str]]:
    """What a finished stop should flag: containers that exited non-zero while
    `down` stopped them (``exit_codes``, seen in ps between stop and removal)
    and services that logged error lines while shutting down. 137 is SIGKILL:
    the container ignored SIGTERM for the whole stop timeout; 143 is a process
    that SIGTERM ended (under init: true it is passed on as that exit code),
    which is a clean stop."""
    out: list[tuple[str, str]] = []
    for svc, code in sorted(exit_codes.items()):
        if code == 143:
            continue
        if code == 137:
            out.append((svc, "did not stop within the stop timeout and was killed (exit code 137)"))
        elif code:
            out.append((svc, f"exited with code {code} while stopping"))
    return out + log_warnings(log_text, max_examples)


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


# ---- chart arithmetic ----

def nice_step(span: float, max_ticks: int = 5) -> float:
    """The smallest 1/2/2.5/5 x 10^k step that covers ``span`` in at most
    ``max_ticks`` steps, so axis labels read 0, 50, 100 ... not 0, 128, 257."""
    if span <= 0:
        return 1.0
    raw = span / max_ticks
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if m * mag >= raw - 1e-12:
            return m * mag
    return 10 * mag


def nice_axis(vmax: float, max_ticks: int = 5) -> tuple[float, float]:
    """(top, step): an axis from 0 to ``top`` (a multiple of a nice step,
    at or above ``vmax``)."""
    step = nice_step(vmax, max_ticks)
    top = max(step, math.ceil(vmax / step - 1e-9) * step)
    return top, step


def fmt_tick(v: float, step: float) -> str:
    """A tick label with as many decimals as the step needs (2.5 -> '2.5')."""
    if step >= 1 and abs(v - round(v)) < 1e-9:
        return f"{v:.0f}"
    decimals = max(1, -math.floor(math.log10(step)) if step < 1 else 1)
    return f"{v:.{decimals}f}".rstrip("0").rstrip(".")


def split_at_gaps(pts: list[tuple[float, float]], max_gap: float) -> list[list[tuple[float, float]]]:
    """Cut a (t, v) series where consecutive samples are more than
    ``max_gap`` apart, so a chart never draws a straight line across a
    stretch that was not measured."""
    segments: list[list[tuple[float, float]]] = []
    for pt in pts:
        if segments and pt[0] - segments[-1][-1][0] <= max_gap:
            segments[-1].append(pt)
        else:
            segments.append([pt])
    return segments


def sample_gaps(times: list[float], max_gap: float) -> list[tuple[float, float]]:
    """(start, end) of every stretch longer than ``max_gap`` without a sample."""
    ts = sorted(times)
    return [(a, b) for a, b in zip(ts, ts[1:]) if b - a > max_gap]


# A series whose peak is this many times every other series' peak gets a
# chart of its own; on a shared scale the rest would be flat lines at 0.
DOMINANCE_RATIO = 4.0


def dominant_series(peaks: dict[str, float], ratio: float = DOMINANCE_RATIO) -> list[str]:
    """Names (largest first) whose peaks dwarf everything else's: the
    shortest list such that the smallest of them is at least ``ratio``
    times the largest of the rest. [] when no such split exists, there is
    only one series, or the rest are all ~0 anyway (nothing to reveal)."""
    order = sorted(peaks, key=lambda k: -peaks[k])
    for i in range(1, len(order)):
        top, rest = peaks[order[i - 1]], peaks[order[i]]
        if rest <= 0:
            return []
        if top >= ratio * rest:
            return order[:i] if i <= len(order) // 2 else []
    return []
