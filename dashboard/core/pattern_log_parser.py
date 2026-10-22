"""Parses reverse_proxy log lines into structured pattern-analyzer events,
for ui/page_patterns.py's colored score badge and diagram tab.

Regex-based against the actual ngx.log() message formats in
pattern_analyzer.lua, router.lua, and nginx.conf's header_filter_by_lua
blocks -- if one of those message strings changes, the corresponding
pattern here needs updating to match (there's no shared source of truth,
same tradeoff as core/patterns.py's presets vs. init.lua's cve_patterns).

Recognized line shapes (roughly highest-value/most-specific first, since
parse_line() checks in this order and returns on the first match):
  - "[LOCATION / HEADER] route_decision='X' risk_score='N'" -- nginx.conf,
    fired on EVERY request exactly once, most reliable per-request outcome
    summary. Drives the score badge.
  - "[FINAL DECISION] (emoji) ROUTING TO (HONEYPOT|PRODUCTION) | Score: N
    [| Reason: ...]" -- nginx.conf, router.lua's own outcome record.
  - "[PATTERN ANALYZER] (emoji) FINAL SCORE: N/M (verdict)" -- pattern_analyzer.lua.
  - "[ROUTING] (emoji) <reason text> (HONEYPOT|PRODUCTION) ..." -- router.lua's
    per-stage routing decisions (Stage 3-10).
  - "[PATTERN ANALYZER] ... Known threat IP detected: IP | Reason: X" --
    informational context for the "Bad IP reputation" signal that follows.
  - "[PATTERN ANALYZER] (emoji) <label> (+N) [| detail]" -- individual
    scoring signals (URI patterns, headers, CVE match, automation, etc.).
  - "[GDPR] Received gdpr_signature=<hex> | Session: <id>" -- nginx.conf,
    the consent-gated one-way signature derived for a request that carried a
    valid consent token (see lua/gdpr_handler.lua / ids/GDPR.md). Shown as its
    own "gdpr" card so the received signature is visible in the Attack
    Simulation page's Pattern analyzer view, not just the raw log.
Anything else returns None (not every log line is pattern-analyzer-relevant
-- SESSION DEBUG, HEALTH, docker_logs source noise, etc. are deliberately
not shown in the diagram).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from core.colors import BLUE, GREEN, ORANGE, RED
from core.line_buffer import LineBuffer  # noqa: F401 -- re-exported for existing importers

# Diagram/badge color palette -- reused across both.
COLOR_LOW = GREEN    # benign / production / small score delta
COLOR_MED = ORANGE   # elevated / medium score delta
COLOR_HIGH = RED     # honeypot / suspicious / large score delta
COLOR_INFO = BLUE    # informational context, not a score itself

# The risk score's actual maximum (init.lua's max_risk_score). The proxy's
# log lines print the score against the honeypot_threshold (e.g. "Score: 100/80"),
# which reads as if 80 were the ceiling -- but scores go up to 100. Displayed
# fractions are normalized to this max so the denominator is the real maximum,
# not the routing threshold (which the colour bands already convey).
SCORE_MAX = 100

# Rewrites a "Score: <n>/<m>" fraction inside a free-text log segment so its
# denominator is SCORE_MAX rather than whatever threshold the proxy logged.
_SCORE_FRACTION_RE = re.compile(r"(Score:\s*-?\d+)\s*/\s*\d+")


def _normalize_score_max(text: str) -> str:
    return _SCORE_FRACTION_RE.sub(rf"\1/{SCORE_MAX}", text)


@dataclass(frozen=True)
class PatternEvent:
    kind: str  # "outcome" | "final_score" | "routing" | "signal" | "info"
    label: str
    detail: str
    color: str
    score: int | None = None  # populated for "outcome"/"final_score" events
    # Original log timestamp (RFC3339, e.g. "2026-08-07T10:32:37.684747138Z"),
    # populated only when the tailing command was run with `docker compose
    # logs --timestamps` (ui/page_patterns.py's pattern_log tail; NOT
    # ui/security_feed.py's, which doesn't need per-event timestamps for its
    # own purposes) -- None otherwise. See _DOCKER_TIMESTAMP_RE below.
    timestamp: str | None = None


# `docker compose logs --timestamps` prefixes EVERY line with
# "<service-name>  | <RFC3339-nano timestamp>Z " regardless of whether the
# underlying app prints its own timestamp -- confirmed live against this
# repo's own reverse_proxy container. Stripped off (and captured) before the
# rest of parse_line's matching, which all runs against the ORIGINAL nginx
# log message shape either way.
#
# The (?:\x1b\[[0-9;]*m)* right before the timestamp digits matters: every
# `docker compose logs` call in this app goes through Target.build(), which
# always adds --ansi always (see core/docker_ctl.py's _global_flags -- needed
# so colorized log output survives QProcess's non-TTY pipe). Confirmed live
# (piped through `cat -v`) that this wraps the "<service> | " prefix in a
# color escape and puts a SEPARATE reset escape (\x1b[0m) directly in front
# of the timestamp itself: "...reverse_proxy-1  | \x1b[0m2026-08-09T...".
# Without skipping that reset code here, the regex never matched at all --
# every single event's timestamp came back None, not just some -- which is
# why "Copy selected" on the Pattern analyzer tab always showed "unknown
# time" instead of the real log timestamp.
_DOCKER_TIMESTAMP_RE = re.compile(
    r"^\S+\s*\|\s*(?:\x1b\[[0-9;]*m)*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\s*"
)

# The proxy logged "[THREAT ANALYZER]" and "threat_score='N'" before the
# rename to pattern analyzer / risk score; both spellings still parse so
# older log tails and exported logs keep working.
_ANALYZER_TAG = r"\[(?:PATTERN|THREAT) ANALYZER\]"

_HEADER_SUMMARY_RE = re.compile(r"\[LOCATION / HEADER\] route_decision='(\w+)' (?:risk|threat)_score='(-?\d+)'")
# Score:\s*(-?\d+)/(\d+) -- both the score AND the honeypot_threshold it's
# being compared against (nginx.conf now logs "Score: N/80" on both
# branches, matching every other score line in this pipeline). Requiring
# the "/(\d+)" here is also what keeps this regex from ever mis-parsing a
# score again the way it silently did before pattern_analyzer.lua/router.lua
# started rounding+capping every score to a clean integer: a raw float like
# "84.484160391042" left the old (-?\d+)-only pattern matching just "84"
# and dumping the leftover ".484160391042" into the "rest" group, which
# showed up as literal garbage text next to "Final decision: HONEYPOT" in
# the dashboard.
_FINAL_DECISION_RE = re.compile(
    r"\[FINAL DECISION\].*ROUTING TO (HONEYPOT|PRODUCTION)\s*\|\s*Score:\s*(-?\d+)/(\d+)(.*)$"
)
_FINAL_SCORE_RE = re.compile(_ANALYZER_TAG + r".*FINAL SCORE:\s*(-?\d+)/(\d+)\s*\(([^)]+)\)")
_ROUTING_RE = re.compile(r"\[ROUTING\]\s*(.+?)\s*(HONEYPOT|PRODUCTION)\b(.*)$")
_KNOWN_THREAT_RE = re.compile(_ANALYZER_TAG + r".*Known threat IP detected:\s*(\S+)\s*\|\s*Reason:\s*(.+)$")
# nginx.conf's per-request "[GDPR] Received gdpr_signature=<hex> | Session: ..."
# -- the one-way consent signature derived for this request. The trailing
# "| Session: ..." (and nginx's own ", client: ..." context, already stripped
# in _parse_line_body) is dropped so only the signature itself is shown.
_GDPR_SIGNATURE_RE = re.compile(r"\[GDPR\]\s*Received gdpr_signature=(\S+)")
_SIGNAL_RE = re.compile(_ANALYZER_TAG + r"\s*(?:[^\x00-\x7f]+\s*)?(.+?)\s*\(\+(\d+)\)(.*)$")

_EMOJI_PREFIX_RE = re.compile(r"^[^\x00-\x7f\s]+\s*")


def _strip_emoji(text: str) -> str:
    return _EMOJI_PREFIX_RE.sub("", text).strip()


def _strip_seps(text: str) -> str:
    return text.strip(" |->→")  # trailing "| ", "-", "->", or a stray arrow


def _signal_color(delta: int) -> str:
    if delta >= 30:
        return COLOR_HIGH
    if delta >= 10:
        return COLOR_MED
    return COLOR_LOW


def parse_line(line: str) -> PatternEvent | None:
    line = line.strip()
    if not line:
        return None

    timestamp = None
    m_ts = _DOCKER_TIMESTAMP_RE.match(line)
    if m_ts:
        timestamp = m_ts.group(1)
        line = line[m_ts.end():]

    event = _parse_line_body(line)
    if event is None:
        return None
    return replace(event, timestamp=timestamp) if timestamp else event


def _parse_line_body(line: str) -> PatternEvent | None:
    # nginx appends ", client: <ip>, server: ..., request: ...\" ..." to
    # EVERY log line (its own context, not part of the Lua message) --
    # strip it before matching so extracted "detail" text doesn't carry it.
    line = line.split(", client:")[0]

    m = _HEADER_SUMMARY_RE.search(line)
    if m:
        decision, score_str = m.group(1), m.group(2)
        try:
            score = int(score_str)
        except ValueError:
            score = 0
        color = COLOR_HIGH if decision == "honeypot" else COLOR_LOW
        return PatternEvent("outcome", f"Routed to {decision.upper()}", f"Score: {score}", color, score)

    m = _FINAL_DECISION_RE.search(line)
    if m:
        target, score_str, threshold, rest = m.group(1), m.group(2), m.group(3), m.group(4)
        try:
            score = int(score_str)
        except ValueError:
            score = 0
        color = COLOR_HIGH if target == "HONEYPOT" else COLOR_LOW
        detail = f"Score: {score}/{SCORE_MAX}"
        rest_clean = _normalize_score_max(_strip_seps(rest))
        if rest_clean:
            detail += f" | {rest_clean}"
        return PatternEvent("outcome", f"Final decision: {target}", detail, color, score)

    m = _FINAL_SCORE_RE.search(line)
    if m:
        score_str, threshold, verdict = m.group(1), m.group(2), m.group(3)
        try:
            score = int(score_str)
        except ValueError:
            score = 0
        verdict_lower = verdict.lower()
        if "suspicious" in verdict_lower:
            color = COLOR_HIGH
        elif "elevated" in verdict_lower:
            color = COLOR_MED
        else:
            color = COLOR_LOW
        return PatternEvent("final_score", f"Final score: {score}/{SCORE_MAX}", verdict, color, score)

    m = _ROUTING_RE.search(line)
    if m:
        label, target, rest = m.group(1), m.group(2), m.group(3)
        color = COLOR_HIGH if target == "HONEYPOT" else COLOR_LOW
        return PatternEvent("routing", _strip_seps(_strip_emoji(label)),
                           _normalize_score_max(_strip_seps(rest)), color)

    m = _KNOWN_THREAT_RE.search(line)
    if m:
        ip, reason = m.group(1), m.group(2)
        return PatternEvent("info", f"Known threat IP: {ip}", reason.strip(), COLOR_INFO)

    m = _GDPR_SIGNATURE_RE.search(line)
    if m:
        return PatternEvent("gdpr", "GDPR signature received", m.group(1), COLOR_INFO)

    m = _SIGNAL_RE.search(line)
    if m:
        label, delta_str, rest = m.group(1), m.group(2), m.group(3)
        delta = int(delta_str)
        clean_label = _strip_seps(_strip_emoji(label))
        return PatternEvent("signal", f"{clean_label} (+{delta})", _strip_seps(rest), _signal_color(delta))

    return None
