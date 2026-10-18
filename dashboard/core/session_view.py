"""Qt-free model of one proxy session for the Sessions drill-down page
(ui/page_sessions.py): parses the `session:<id>` JSON, joins it with the
session's honeypot pool assignment and its IP's threat_ips reputation, and
turns `suspicious_activities` into a timeline. Fetching is in
core/redis_inspect.list_sessions(); this module only interprets the data."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

HONEYPOT_THRESHOLD = 80   # init.lua honeypot_threshold default (see Knowledge Base glossary)


@dataclass
class TimelineEntry:
    timestamp: int
    uri: str
    score: int | None
    detail: str


@dataclass
class SessionSummary:
    session_id: str
    ip: str = ""
    user_agent: str = ""
    risk_score: int = 0
    request_count: int = 0
    created_at: int = 0
    last_activity: int = 0
    route: str = "production"
    honeypot_bound: bool = False
    compromised: bool = False
    pool: str = ""                      # honeypot_pool_session:<id> value, "" when none
    first_uri: str = ""
    ip_reputation: dict = field(default_factory=dict)   # threat_ips[ip]
    timeline: list[TimelineEntry] = field(default_factory=list)

    @property
    def diverted(self) -> bool:
        return bool(self.honeypot_bound or self.pool or self.route == "honeypot")

    @property
    def duration(self) -> int:
        return max(0, self.last_activity - self.created_at)

    @property
    def verdict(self) -> str:
        if self.compromised:
            return "compromised"
        if self.diverted:
            return "diverted"
        if self.risk_score >= HONEYPOT_THRESHOLD:
            return "over threshold"
        if self.risk_score >= 40 or self.timeline:
            return "suspicious"
        return "benign"


def _int(value, default=0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_timeline(activities) -> list[TimelineEntry]:
    """suspicious_activities, oldest first. Entries come in two shapes:
    scoring hits (uri/risk_score/patterns) and session_compromised markers
    (activity/reason). Anything malformed is skipped."""
    out: list[TimelineEntry] = []
    if not isinstance(activities, list):
        return out
    for a in activities:
        if not isinstance(a, dict):
            continue
        patterns = a.get("patterns")
        if isinstance(patterns, list):
            detail = ", ".join(str(p) for p in patterns)
        elif isinstance(patterns, dict):
            detail = ", ".join(str(k) for k in patterns)
        else:
            detail = str(a.get("reason") or a.get("activity") or "")
        score = a.get("risk_score")
        out.append(TimelineEntry(_int(a.get("timestamp")), str(a.get("uri", "")),
                                 None if score is None else _int(score), detail))
    return sorted(out, key=lambda e: e.timestamp)


def parse_session(session_json: str, pool: str = "", threat_ips: dict | None = None,
                  session_id: str = "") -> SessionSummary | None:
    """None when the JSON isn't a session object."""
    try:
        data = json.loads(session_json)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    ip = str(data.get("ip_address", ""))
    rep = (threat_ips or {}).get(ip)
    return SessionSummary(
        session_id=str(data.get("id") or session_id),
        ip=ip,
        user_agent=str(data.get("user_agent", "")),
        risk_score=_int(data.get("risk_score")),
        request_count=_int(data.get("request_count")),
        created_at=_int(data.get("created_at")),
        last_activity=_int(data.get("last_activity")),
        route=str(data.get("route_preference", "production")),
        honeypot_bound=bool(data.get("honeypot_bound")),
        compromised=bool(data.get("compromised")),
        pool=pool.strip(),
        first_uri=str(meta.get("first_uri", "")),
        ip_reputation=rep if isinstance(rep, dict) else {},
        timeline=parse_timeline(data.get("suspicious_activities")),
    )


def parse_snapshot(text: str) -> list[SessionSummary]:
    """The JSON list list_sessions() gets back from redis: [{"session": <json
    string>, "pool": str, "id": str}, ...] plus a {"threat_ips": {...}}
    wrapper. Sorted riskiest, then most recent, first."""
    try:
        snap = json.loads(text)
    except (TypeError, ValueError):
        return []
    if not isinstance(snap, dict):
        return []
    threat = snap.get("threat_ips")
    if isinstance(threat, str):
        try:
            threat = json.loads(threat)
        except ValueError:
            threat = {}
    if not isinstance(threat, dict):
        threat = {}
    rows = snap.get("sessions")
    if not isinstance(rows, list):     # cjson encodes an empty Lua table as {}
        return []
    sessions = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        s = parse_session(row.get("session", ""), str(row.get("pool", "")), threat, str(row.get("id", "")))
        if s is not None:
            sessions.append(s)
    return sorted(sessions, key=lambda s: (-s.risk_score, -s.last_activity))


def narrative(s: SessionSummary) -> str:
    """A short plain-language story of the session, for the detail pane."""
    parts = [f"Session {s.session_id[:12]} from {s.ip or 'unknown IP'} made {s.request_count} request(s)"
             f" over {s.duration}s and reached risk score {s.risk_score}/100."]
    if s.timeline:
        first = s.timeline[0]
        parts.append(f"The first suspicious request was {first.uri or 'unknown'}"
                     f"{f' (score {first.score})' if first.score is not None else ''}.")
        parts.append(f"{len(s.timeline)} suspicious request(s) in total.")
    if s.pool:
        parts.append(f"It is bound to honeypot pool {s.pool}.")
    elif s.diverted:
        parts.append("It was routed to the honeypot.")
    else:
        parts.append("It is still routed to production.")
    rep = s.ip_reputation.get("reason")
    if rep and rep != "clean":
        parts.append(f"The IP's reputation entry says: {rep}.")
    return " ".join(parts)
