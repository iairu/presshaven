"""Qt-free mapping of the PDF export's 0..1 progress fraction to named stages,
so the Attack Simulation page can show a staged overview of the export instead
of one undifferentiated bar.

The stage boundaries mirror the phase fractions ReportWorker.run()
(core/pattern_report.py) emits via _emit(): threat decay 0.00-0.20, session
restoration 0.20-0.28, per-pattern sections 0.28-0.88, threat increase
0.88-0.99, and the pool-state read + PDF render that finish it off
(0.99-1.00). If those fractions change there, update these to match -- the
test (tests/test_report_progress.py) pins them to the same numbers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Stage:
    key: str
    title: str
    start: float   # inclusive overall-fraction where this stage begins
    end: float     # exclusive overall-fraction where the next stage begins


STAGES: list[Stage] = [
    Stage("decay", "Threat decay baseline", 0.00, 0.20),
    Stage("restore", "Session restoration", 0.20, 0.28),
    Stage("patterns", "Pattern tests", 0.28, 0.88),
    Stage("increase", "Threat increase", 0.88, 0.99),
    Stage("finalize", "Finalize & render", 0.99, 1.00),
]


def stage_index_for_fraction(fraction: float) -> int:
    """Which stage an overall 0..1 progress fraction is currently in."""
    frac = max(0.0, min(1.0, fraction))
    for i, s in enumerate(STAGES):
        if frac < s.end:
            return i
    return len(STAGES) - 1   # frac == 1.0 lands in the final stage


def stage_fraction(fraction: float, index: int) -> float:
    """Progress 0..1 WITHIN stage `index` for an overall fraction (so each
    stage's own sub-bar fills from empty to full across its slice)."""
    s = STAGES[index]
    span = s.end - s.start
    if span <= 0:
        return 1.0
    return max(0.0, min(1.0, (fraction - s.start) / span))
