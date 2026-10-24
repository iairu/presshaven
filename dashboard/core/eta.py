"""Estimated-time-remaining for a long export, Qt-free so it is unit-testable.

Both report exports (Attack Simulation, Segmentation Validation) report
progress as a fraction of the whole run, but they only emit it at phase/step
boundaries -- several seconds, sometimes minutes, apart. An ETA that only
moved on those emissions would sit frozen between them. So the tracker keeps
the last (elapsed, fraction) anchor and extrapolates a live countdown for any
later moment, which a 1 s UI timer queries so the figure ticks down smoothly
and re-anchors whenever real progress arrives.

The estimate is a plain linear extrapolation (the first `fraction` of the work
took `elapsed`, so the rest takes the same rate). That is only ever a rough
guide -- a run with very uneven phases (the pool scale-up wait can take
anywhere from seconds to minutes) will swing -- which is why the UI labels it
as an estimate.
"""
from __future__ import annotations


def remaining_seconds(elapsed: float, fraction: float) -> float | None:
    """Seconds still to go if `fraction` (0..1) of the work took `elapsed`
    seconds. None when it cannot be estimated yet (no time or no progress
    recorded); 0.0 once complete."""
    if elapsed <= 0 or fraction <= 0:
        return None
    if fraction >= 1.0:
        return 0.0
    return elapsed * (1.0 - fraction) / fraction


def format_eta(seconds: float | None) -> str:
    """A short human label for the remaining time, e.g. "~2:30" or "~1:05:00".
    None (not estimable yet) reads as "estimating…"."""
    if seconds is None:
        return "estimating…"
    total = max(0, int(round(seconds)))
    m, s = divmod(total, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"~{h}:{m:02d}:{s:02d}"
    return f"~{m}:{s:02d}"


class EtaTracker:
    """Remembers the last progress anchor and extrapolates a live countdown
    from it. `update(elapsed, fraction)` is called on each real progress
    emission; `remaining_at(elapsed)` is called as often as the UI likes (e.g.
    once a second) and counts the last estimate down by the time since that
    anchor, so the figure keeps moving between emissions without ever going
    below zero."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._anchor_elapsed = 0.0
        self._remaining: float | None = None

    def update(self, elapsed: float, fraction: float) -> None:
        self._anchor_elapsed = elapsed
        self._remaining = remaining_seconds(elapsed, fraction)

    def remaining_at(self, elapsed: float) -> float | None:
        """The remaining estimate as of `elapsed` seconds into the run: the
        last anchor counted down by however long has passed since it, floored
        at zero. None while nothing is estimable yet."""
        if self._remaining is None:
            return None
        return max(0.0, self._remaining - (elapsed - self._anchor_elapsed))
