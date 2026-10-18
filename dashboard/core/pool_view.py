"""Qt-free interpretation of the honeypot pool registry for the standing
Pool Scaling page (ui/page_pool_scaling.py): how many pools exist, how much
of the resource budget they use, which one each session count sits on, why
growth stopped, and a readable tail of pool_manager's event log. The raw
data comes from core/redis_inspect.pool_snapshot(); the keys it reads are
documented in ids/images/pool_manager/manager.py."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

STATIC_POOLS = 3      # pools 1-3 come from docker-compose.yml; the rest are built at runtime


@dataclass
class PoolRow:
    number: int
    owners: int
    free: bool
    static: bool
    idle_seconds: int | None      # since the router last sent it a request
    healthy: bool | None          # database layer only; None = not reported


@dataclass
class PoolOverview:
    manager_alive: bool = False
    pools: int = 0
    ready: int = 0
    free: int = 0
    waiting: int = 0
    building: list[int] = field(default_factory=list)
    mem_used_mb: int = 0
    mem_max_mb: int = 0
    cpu_used: float = 0.0
    cpu_max: float = 0.0
    max_pools: int = 0
    room: int = 0
    capped_reason: str = ""
    scaledown_pending: bool = False
    idle_timeout: int = 0
    rows: list[PoolRow] = field(default_factory=list)
    events: list[tuple[int, str]] = field(default_factory=list)   # (epoch, text), newest last

    @property
    def mem_fraction(self) -> float:
        return min(1.0, self.mem_used_mb / self.mem_max_mb) if self.mem_max_mb else 0.0

    @property
    def state(self) -> str:
        """One word: why the pool count is what it is."""
        if not self.manager_alive:
            return "manager offline"
        if self.capped_reason:
            return "capped"
        if self.building:
            return "scaling up"
        if self.waiting:
            return "sessions waiting"
        return "steady"


def _as_list(value) -> list:
    return value if isinstance(value, list) else []     # cjson encodes empty tables as {}


def _pairs(flat) -> dict[str, str]:
    flat = _as_list(flat)
    return {str(flat[i]): str(flat[i + 1]) for i in range(0, len(flat) - 1, 2)}


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def describe_event(e: dict) -> str:
    kind = e.get("type", "?")
    pool = e.get("pool")
    if kind == "build":
        secs = e.get("seconds")
        return f"pool {pool} built" + (f" in {secs:.0f}s" if isinstance(secs, (int, float)) else "")
    if kind == "build_start":
        return f"building pool {pool}" + (f" ({e['reason']})" if e.get("reason") else "")
    if kind == "handoff":
        wait = e.get("waited")
        return f"session moved to its own pool {pool}" + (f" after {wait:.0f}s" if isinstance(wait, (int, float)) else "")
    if kind == "scaledown":
        return f"pool {pool} removed (idle {_num(e.get('idle')):.0f}s)"
    if kind == "scaledown_done":
        return f"scale-down finished, {len(_as_list(e.get('removed')))} pool(s) removed"
    if kind == "released":
        return f"pool {pool} released ({e.get('reason', '')})".replace(" ()", "")
    if kind == "capped":
        return f"resource limit reached: {e.get('reason', '')}"
    if kind == "uncapped":
        return "resource limit cleared, scaling resumes"
    if kind == "dropped_waiting":
        return f"{len(_as_list(e.get('sessions')))} waiting session(s) now share pools"
    if kind == "pool_health":
        return f"pool {pool} database {'healthy' if e.get('healthy') else 'unhealthy'}"
    return kind


def parse_snapshot(text: str, now: float | None = None) -> PoolOverview:
    """PoolOverview from pool_snapshot()'s JSON; an unparseable or empty
    snapshot gives an empty (manager offline) overview."""
    try:
        snap = json.loads(text)
    except (TypeError, ValueError):
        return PoolOverview()
    if not isinstance(snap, dict):
        return PoolOverview()
    try:
        status = json.loads(snap.get("status") or "{}")
    except ValueError:
        status = {}
    if not isinstance(status, dict):
        status = {}
    now = float(snap.get("now") or time.time()) if now is None else now

    ready = sorted(int(n) for n in _as_list(snap.get("ready")) if str(n).isdigit())
    free = {int(n) for n in _as_list(snap.get("free")) if str(n).isdigit()}
    owners = snap.get("owners") if isinstance(snap.get("owners"), dict) else {}
    last_seen = _pairs(snap.get("last_seen"))
    health = _pairs(snap.get("health"))

    rows = []
    for n in ready:
        seen = _num(last_seen.get(str(n)), 0)
        h = None
        if str(n) in health:
            try:
                h = bool(json.loads(health[str(n)]).get("healthy"))
            except (ValueError, AttributeError):
                h = None
        rows.append(PoolRow(n, int(_num(owners.get(str(n)), 0)), n in free, n <= STATIC_POOLS,
                            int(max(0, now - seen)) if seen else None, h))

    events = []
    for raw in _as_list(snap.get("events")):
        try:
            e = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if isinstance(e, dict) and e.get("type") != "pool_health":     # health blips drown the log
            events.append((int(_num(e.get("at"))), describe_event(e)))

    pools = int(_num(status.get("pools"), len(ready)))
    mem_per, cpu_per = _num(status.get("mem_per_pool")), _num(status.get("cpus_per_pool"))
    capped = str(status.get("capped") or snap.get("capped") or "").strip()
    return PoolOverview(
        manager_alive=bool(status),
        pools=pools, ready=len(ready), free=len(free),
        waiting=int(_num(snap.get("waiting"))),
        building=sorted(int(n) for n in (status.get("building") or {}) if str(n).isdigit()),
        mem_used_mb=int(pools * mem_per), mem_max_mb=int(_num(status.get("max_memory_mb"))),
        cpu_used=round(pools * cpu_per, 2), cpu_max=_num(status.get("max_cpus")),
        max_pools=int(_num(status.get("max_pools"))), room=int(_num(status.get("room"))),
        capped_reason=capped, scaledown_pending=bool(snap.get("scaledown")),
        idle_timeout=int(_num(status.get("idle_timeout"))),
        rows=rows, events=events)
