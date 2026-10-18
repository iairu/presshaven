"""What each honeypot pool's own containers saw and changed during a Pool test
run: the requests that reached its eshop (from the Apache access log, told
apart by each test window's User-Agent tag), files written inside that eshop,
and how far its database's statement counters moved.

In the database proxy layer (core/honeypot_layer.py) a pool is a database
only: one production_eshop serves every pool, so there is no per-pool access
log or filesystem. There each database's MySQL general query log (turned on
for the run, see enable_query_log) tells the windows apart instead: WordPress
opens one MySQL connection per request, and a window's request looks up its
WooCommerce session by the key in that window's cookie, so every statement on
a connection that names a window's session key is that window's
(attribution_sql). Files are then checked once, on the shared filesystem.

Different windows run different patterns, so each pool's evidence should be its
owner's pattern and nobody else's -- that is what the Pool test report shows.
The parsers are pure (unit tested); the collectors shell out through the
project's compose Target, so they work for a remote edge host too.
"""
from __future__ import annotations

import re
import time
import shlex
from dataclasses import dataclass, field

from core import honeypot_layer
from core.docker_ctl import Target
from core.proc import run_checked

# Counters whose growth means "this database was used".
DB_COUNTERS = ("Questions", "Com_select", "Com_insert", "Com_update", "Com_delete")

# Window tag the Segmentation Validation page puts in each frame's User-Agent ("PoolTest/A").
_WINDOW_RE = re.compile(r"PoolTest/([A-Z])")
_LOG_RE = re.compile(
    r'^(\S+) \S+ \S+ \[[^\]]+\] "(\S+) (\S+)[^"]*" (\d{3}) \S+ "[^"]*" "([^"]*)"')
_ASSET_RE = re.compile(r"\.(css|js|png|jpe?g|gif|svg|ico|woff2?|ttf|map)(\?|$)", re.I)

# Paths written by Apache/WordPress on every run; never worth reporting.
_FILE_NOISE = ("/tmp/", "/proc/", "/sys/", "/run/", "/dev/")


class PoolEvidenceError(Exception):
    pass


@dataclass
class Hit:
    window: str          # "A", "B", ...
    method: str
    path: str
    status: int


@dataclass
class WindowQueries:
    """One window's traffic in one database's query log (database layer)."""
    window: str          # "A", "B", ...
    requests: int        # MySQL connections, i.e. WordPress requests
    queries: int
    writes: int          # INSERT / UPDATE / DELETE / REPLACE
    suspicious: int      # statements carrying SQL-injection markers
    examples: list[str] = field(default_factory=list)


@dataclass
class ContainerEvidence:
    pool: int
    hits: list[Hit] = field(default_factory=list)
    # Database layer: the windows the database's query log attributes to it,
    # and how many other connections it had (content sync, cron, visitors
    # outside the test); None when the log was not read.
    db_windows: list[WindowQueries] = field(default_factory=list)
    db_other_requests: int | None = None
    files_changed: list[str] = field(default_factory=list)
    db_delta: dict[str, int] | None = None   # None: no baseline (pool built mid-run)
    # db_delta minus the pool's own background (healthchecks, WP cron, content
    # sync) at the rate measured while no window was on it; None: not measured.
    db_attack: dict[str, int] | None = None
    error: str = ""

    def windows(self) -> list[str]:
        return sorted({h.window for h in self.hits} | {q.window for q in self.db_windows})

    def notable(self, limit: int = 8) -> list[Hit]:
        """Distinct non-asset requests, in the order they arrived."""
        seen, out = set(), []
        for h in self.hits:
            key = (h.window, h.method, h.path)
            if key in seen or _ASSET_RE.search(h.path):
                continue
            seen.add(key)
            out.append(h)
        return out[:limit]


def parse_status(text: str) -> dict[str, int]:
    """`SHOW GLOBAL STATUS` rows ("name<TAB>value") -> {name: int}."""
    out = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) == 2 and parts[1].strip().isdigit():
            out[parts[0].strip()] = int(parts[1])
    return out


def parse_access_log(text: str) -> list[Hit]:
    """Requests in an Apache combined log that came from a Pool test window."""
    hits = []
    for line in text.splitlines():
        m = _LOG_RE.match(line.strip())
        if not m:
            continue
        w = _WINDOW_RE.search(m.group(5))
        if w:
            hits.append(Hit(w.group(1), m.group(2), m.group(3), int(m.group(4))))
    return hits


def filter_files(paths: list[str]) -> list[str]:
    return [p for p in (x.strip() for x in paths) if p and not p.startswith(_FILE_NOISE)]


def db_delta(before: dict[str, int] | None, after: dict[str, int]) -> dict[str, int] | None:
    if before is None:
        return None
    return {k: after.get(k, 0) - before.get(k, 0) for k in DB_COUNTERS}


def without_background(delta: dict[str, int] | None, base: dict[str, int] | None,
                       idle: dict[str, int] | None, idle_s: float, total_s: float) -> dict[str, int] | None:
    """`delta` (counters over total_s seconds) minus the pool's background:
    its rate while idle (base -> idle over idle_s seconds, no window on it)
    times total_s. A pool's own healthchecks, WP cron and content sync run
    thousands of queries even when nobody visits, which swamped what the
    user caused. None when the idle rate was not measured."""
    if delta is None or base is None or idle is None or idle_s < 5:
        return None
    out = {}
    for k in DB_COUNTERS:
        rate = max(0, idle.get(k, 0) - base.get(k, 0)) / idle_s
        out[k] = max(0, round(delta.get(k, 0) - rate * total_s))
    return out


# ---- query log attribution (database layer, pure) ----

# A WooCommerce session key as it appears in the cookie and in SQL: "t_" plus
# ~30 hex digits for a guest (the test windows). A short one (a logged-in
# user's id, "42") would match unrelated statements, and anything else is
# never interpolated into SQL.
_SESSION_KEY_RE = re.compile(r"^[A-Za-z0-9_]{8,64}$")
_WC_COOKIE_PREFIX = "wp_woocommerce_session_"
_SINCE_SQL_RE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(\.\d{1,6})?$")
# Statements with these in them carry an SQL-injection payload (MySQL regexp,
# matched case-insensitively).
_SUSPICIOUS_SQL = ("union[[:space:]]+(all[[:space:]]+)?select|sleep[[:space:]]*[(]|"
                   "benchmark[[:space:]]*[(]|information_schema|load_file|"
                   "into[[:space:]]+(out|dump)file|or[[:space:]]+1[[:space:]]*=[[:space:]]*1")
_WRITE_SQL = "^[[:space:]]*(insert|update|delete|replace)[[:space:]]"
# Writes every request makes; not worth showing as an example.
_ROUTINE_WRITES = ("woocommerce_sessions", "_transient", "actionscheduler", "wc_admin")


def wc_session_key(cookie_name: str, cookie_value: str) -> str:
    """The session key in a WooCommerce session cookie
    ("wp_woocommerce_session_<hash>" = "<key>||<expiry>||<expiring>||<hash>",
    the bars possibly URL-encoded); "" for any other cookie."""
    if not cookie_name.startswith(_WC_COOKIE_PREFIX):
        return ""
    key = cookie_value.replace("%7C", "|").replace("%7c", "|").split("||", 1)[0]
    return key if _SESSION_KEY_RE.match(key) else ""


def _like(key: str) -> str:
    return "'%" + key.replace("_", "\\_") + "%'"


def attribution_sql(keys: dict[str, str], since: str) -> tuple[str, str, str] | None:
    """(per-window totals, example statements, all connections) queries for
    one database's mysql.general_log, or None when no key is usable. `keys`
    maps WooCommerce session key -> window letter; `since` is the database's
    own NOW(6) at the start of the run ("" = the whole log, for a database
    built during the run with the log on). The reading user's connections
    (root) are left out: their SQL names the keys too."""
    keys = {k: w for k, w in keys.items() if _SESSION_KEY_RE.match(k) and re.match(r"^[A-Z]$", w)}
    if not keys or (since and not _SINCE_SQL_RE.match(since)):
        return None
    when = f"event_time >= '{since}' AND " if since else ""
    arg = "CONVERT(argument USING utf8)"
    case = " ".join(f"WHEN {arg} LIKE {_like(k)} THEN '{w}'" for k, w in keys.items())
    match = " OR ".join(f"{arg} LIKE {_like(k)}" for k in keys)
    owners = (f"SELECT thread_id, MIN(CASE {case} END) AS w FROM mysql.general_log "
              f"WHERE {when}user_host NOT LIKE '%[root] @%' AND ({match}) GROUP BY thread_id")
    garg = "CONVERT(g.argument USING utf8)"
    query = "g.command_type = 'Query'"
    totals = (f"SELECT m.w, COUNT(DISTINCT g.thread_id), SUM({query}), "
              f"SUM({query} AND {garg} REGEXP '{_WRITE_SQL}'), "
              f"SUM({query} AND {garg} REGEXP '{_SUSPICIOUS_SQL}') "
              f"FROM mysql.general_log g JOIN ({owners}) m ON m.thread_id = g.thread_id "
              f"WHERE {when.replace('event_time', 'g.event_time')}1 GROUP BY m.w")
    examples = (f"SELECT m.w, {garg} REGEXP '{_SUSPICIOUS_SQL}' AS susp, "
                f"REPLACE(REPLACE(LEFT({garg}, 160), '\\n', ' '), '\\t', ' ') AS stmt "
                f"FROM mysql.general_log g JOIN ({owners}) m ON m.thread_id = g.thread_id "
                f"WHERE {when.replace('event_time', 'g.event_time')}{query} AND "
                f"({garg} REGEXP '{_WRITE_SQL}' OR {garg} REGEXP '{_SUSPICIOUS_SQL}') "
                "GROUP BY m.w, susp, stmt LIMIT 400")
    connections = (f"SELECT COUNT(DISTINCT thread_id) FROM mysql.general_log WHERE {when}"
                   "command_type = 'Connect' AND user_host NOT LIKE '%[root] @%'")
    return totals, examples, connections


def parse_attribution(totals: str, examples: str, connections: str,
                      per_window: int = 4) -> tuple[list[WindowQueries], int | None]:
    """WindowQueries per window from the attribution_sql() answers (mysql -N
    -B output), and the database's connections no window accounts for. A
    window's examples put SQL-injection statements first and skip the writes
    every request makes (session, transients)."""
    out: dict[str, WindowQueries] = {}
    for line in totals.splitlines():
        parts = line.split("\t")
        if len(parts) == 5 and re.match(r"^[A-Z]$", parts[0]) and all(
                p.strip().isdigit() for p in parts[1:]):
            out[parts[0]] = WindowQueries(parts[0], *(int(p) for p in parts[1:]))
    picked: dict[str, list[tuple[int, str]]] = {}
    for line in examples.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3 or parts[0] not in out:
            continue
        susp, stmt = parts[1].strip() == "1", " ".join(parts[2].split())
        if not susp and any(r in stmt for r in _ROUTINE_WRITES):
            continue
        picked.setdefault(parts[0], []).append((0 if susp else 1, stmt))
    for w, items in picked.items():
        out[w].examples = [stmt for _p, stmt in sorted(items)[:per_window]]
    total = connections.strip().splitlines()[-1].strip() if connections.strip() else ""
    other = (max(0, int(total) - sum(q.requests for q in out.values()))
             if total.isdigit() else None)
    return sorted(out.values(), key=lambda q: q.window), other


# ---- collectors (docker / compose) ----

def _run_container(target: Target, service: str, compose_args: tuple[str, ...],
                   docker_cmd: str, timeout: float, what: str) -> str:
    """Run against a pool container: through compose for the pools declared in
    the compose file, else straight through docker. Pools pool_manager built at
    runtime are plain containers named like the service (honeypot_eshop_4) and
    unknown to compose ("service ... is not running")."""
    argv, cwd = target.build(*compose_args)
    try:
        return run_checked(argv, error=PoolEvidenceError, cwd=cwd, timeout=timeout,
                           what=what).stdout
    except PoolEvidenceError as compose_error:
        argv, cwd = target.build_shell(docker_cmd)
        try:
            return run_checked(argv, error=PoolEvidenceError, cwd=cwd, timeout=timeout,
                               what=what).stdout
        except PoolEvidenceError:
            raise compose_error from None


def _exec(target: Target, service: str, command: str, timeout: float = 30.0) -> str:
    return _run_container(
        target, service, ("exec", "-T", service, "sh", "-c", command),
        f"docker exec {shlex.quote(service)} sh -c {shlex.quote(command)}",
        timeout, f"docker exec {service}")


def _logs(target: Target, service: str, since: str, timeout: float = 30.0) -> str:
    """The container's log since `since`. `docker compose logs` does not fail
    for a service it does not know -- it prints nothing and exits 0 -- so an
    empty answer is retried through plain docker, which knows the runtime
    pools (and fails for compose-named ones, keeping the empty answer)."""
    out = _run_container(
        target, service, ("logs", "--no-log-prefix", "--since", since, service),
        f"docker logs --since {shlex.quote(since)} {shlex.quote(service)} 2>&1",
        timeout, "docker logs")
    if out.strip():
        return out
    argv, cwd = target.build_shell(
        f"docker logs --since {shlex.quote(since)} {shlex.quote(service)} 2>&1")
    try:
        return run_checked(argv, error=PoolEvidenceError, cwd=cwd, timeout=timeout,
                           what="docker logs").stdout
    except PoolEvidenceError:
        return out


_STATUS_CMD = ("mysql -uroot -p\"$MYSQL_ROOT_PASSWORD\" -N -e \"SHOW GLOBAL STATUS WHERE "
               "Variable_name IN (" + ",".join(f"'{c}'" for c in DB_COUNTERS) + ")\" 2>/dev/null")


def _database_layer(database: bool | None) -> bool:
    return honeypot_layer.is_database() if database is None else database


def db_service(pool: int, database: bool | None = None) -> str:
    """The pool's MySQL container: honeypot_database_N, except pool 1 of the
    database layer, which is the compose service `honeypot_database`."""
    return "honeypot_database" if _database_layer(database) and pool == 1 else f"honeypot_database_{pool}"


def db_status(target: Target, pool: int, database: bool | None = None) -> dict[str, int] | None:
    try:
        return parse_status(_exec(target, db_service(pool, database), _STATUS_CMD))
    except PoolEvidenceError:
        return None


def _mysql(target: Target, pool: int, sql: str, database: bool | None = None,
           timeout: float = 60.0) -> str:
    """Run `sql` as root in the pool's database; its rows tab-separated."""
    return _exec(target, db_service(pool, database),
                 "mysql -uroot -p\"$MYSQL_ROOT_PASSWORD\" -N -B -e " + shlex.quote(sql)
                 + " 2>/dev/null", timeout=timeout)


def enable_query_log(target: Target, pool: int, database: bool | None = None) -> str | None:
    """Turn the database's general query log on (log_output=TABLE) and return
    its clock (NOW(6)) right after, the time attribution_sql() reads from;
    None when it could not be turned on."""
    try:
        got = _mysql(target, pool, "SET GLOBAL log_output='TABLE'; SET GLOBAL general_log='ON'; "
                     "SELECT NOW(6)", database).strip().splitlines()
    except PoolEvidenceError:
        return None
    return got[-1].strip() if got and _SINCE_SQL_RE.match(got[-1].strip()) else None


def disable_query_log(target: Target, pools: list[int], database: bool | None = None) -> None:
    """Turn the general query log off again (best effort: a pool may be gone)."""
    for pool in pools:
        try:
            _mysql(target, pool, "SET GLOBAL general_log='OFF'", database, timeout=20.0)
        except PoolEvidenceError:
            pass


_SINCE_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
_DATE_CMD = "date -u +%Y-%m-%dT%H:%M:%SZ"


def _clock(target: Target, service: str) -> str:
    """The container's UTC time, ISO formatted; "" when unreadable."""
    try:
        got = _exec(target, service, _DATE_CMD).strip()
    except PoolEvidenceError:
        return ""
    return got if _SINCE_RE.match(got) else ""   # interpolated into shell commands


def take_baseline(target: Target, pools: list[int], database: bool | None = None) -> dict:
    """Start time (read from a pool's own container, so its clock is the one
    the logs and file times use) and each existing pool's DB counters. In the
    database layer also turns each database's query log on (enable_query_log)
    and reads the shared eshop's clock for its file check."""
    database = _database_layer(database)
    since = ""
    for pool in pools:
        since = _clock(target, db_service(pool, True) if database else f"honeypot_eshop_{pool}")
        if since:
            break
    now = time.time()
    baseline = {"since": since, "db": {p: db_status(target, p, database) for p in pools},
                "pool_since": {}, "db_at": {p: now for p in pools}, "database": database}
    if database:
        baseline["qlog"] = {p: enable_query_log(target, p, True) for p in pools}
        baseline["shared_since"] = _clock(target, "production_eshop")
    return baseline


def mark_idle(target: Target, baseline: dict) -> None:
    """Second DB snapshot of the pools that were up at the start, taken while
    every window is still on production: the counters between the baseline and
    this are the pools' own background (see without_background())."""
    now = time.time()
    baseline["idle"] = {p: (db_status(target, p, baseline.get("database")), now)
                        for p, b in baseline.get("db", {}).items() if b is not None}


def extend_baseline(target: Target, baseline: dict, pools: list[int]) -> None:
    """Baseline for pools that came up during the run (built by pool_manager
    for windows that attack later): their DB counters and start time, taken
    before any test window reaches them, so their evidence covers the
    windows' traffic only and not the pool's own build. A database layer pool
    built during the run already has its query log on from its build (see
    QUERY_LOG_KEY in pool_manager): it is read whole ("" = no start time), so
    a window handed the pool before this ran is still counted."""
    database = bool(baseline.get("database"))
    tried = baseline.setdefault("tried", set())
    for pool in pools:
        if baseline.setdefault("db", {}).get(pool) is not None or pool in tried:
            continue
        tried.add(pool)
        got = _clock(target, db_service(pool, True) if database else f"honeypot_eshop_{pool}")
        if not got:
            continue
        baseline["db"][pool] = db_status(target, pool, database)
        baseline.setdefault("pool_since", {})[pool] = got
        if database:
            baseline.setdefault("qlog", {})[pool] = "" if enable_query_log(target, pool, True) else None
        if not baseline.get("since"):
            baseline["since"] = got


def query_log_windows(target: Target, pool: int, since: str, keys: dict[str, str]
                      ) -> tuple[list[WindowQueries], int | None]:
    """The windows a database's query log attributes to it (attribution_sql),
    and its other connections."""
    queries = attribution_sql(keys, since)
    if queries is None:
        return [], None
    return parse_attribution(*(_mysql(target, pool, q, True, timeout=120.0) for q in queries))


def collect(target: Target, pools: list[int], baseline: dict,
            wc_keys: dict[str, str] | None = None) -> list[ContainerEvidence]:
    """Each pool's evidence. `wc_keys` (WooCommerce session key -> window
    letter, every key a window held during the run) attributes the database
    layer's query logs."""
    database = bool(baseline.get("database"))
    out = []
    for pool in pools:
        since = baseline.get("pool_since", {}).get(pool) or baseline.get("since", "")
        ev = ContainerEvidence(pool)
        try:
            if not since:
                ev.error = "Could not read the start time from the pool containers."
            elif database:
                qsince = baseline.get("qlog", {}).get(pool)
                if qsince is not None and wc_keys:
                    ev.db_windows, ev.db_other_requests = query_log_windows(
                        target, pool, qsince, wc_keys)
            else:
                log = _logs(target, f"honeypot_eshop_{pool}", since)
                ev.hits = parse_access_log(log)
                files = _exec(target, f"honeypot_eshop_{pool}",
                              "find / -xdev \\( -path /proc -o -path /sys -o -path /run -o -path /dev \\) "
                              f"-prune -o -type f -newermt '{since}' -print 2>/dev/null | head -60")
                ev.files_changed = filter_files(files.splitlines())
            after = db_status(target, pool, database)
            base = baseline.get("db", {}).get(pool)
            ev.db_delta = db_delta(base, after) if after else None
            idle, idle_at = baseline.get("idle", {}).get(pool, (None, 0.0))
            base_at = baseline.get("db_at", {}).get(pool)
            if base_at and idle_at:
                ev.db_attack = without_background(ev.db_delta, base, idle,
                                                  idle_at - base_at, time.time() - base_at)
        except PoolEvidenceError as e:
            ev.error = str(e)
        out.append(ev)
    return out


def shared_files_changed(target: Target, since: str) -> list[str] | None:
    """Database layer: files written in the one WordPress filesystem every
    pool shares (production_eshop) since `since`. Anything a diverted
    window's request wrote there is production's too -- the gap that layer
    cannot close (ids/db_proxy/COVERAGE.md). None when unreadable."""
    if not _SINCE_RE.match(since or ""):
        return None
    try:
        files = _exec(target, "production_eshop",
                      f"find /var/www/html -type f -newermt '{since}' -print 2>/dev/null | head -60")
    except PoolEvidenceError:
        return None
    return filter_files(files.splitlines())


def response_realism(evidence: list[ContainerEvidence]) -> tuple[int, int, list[str]]:
    """(non-asset requests the honeypot pools answered, how many got a 4xx,
    a few example 4xx paths). A 404/400 on a pattern's own endpoint tells the
    user the targeted plugin is not installed, which weakens the decoy and
    yields little interaction to record -- so a high share here is a
    deception-fidelity signal, not a routing problem."""
    total = four = 0
    examples: list[str] = []
    for ev in evidence:
        for h in ev.notable(limit=1000):
            if h.method != "GET" and h.method != "POST":
                continue
            total += 1
            if 400 <= h.status < 500:
                four += 1
                if len(examples) < 4 and h.path not in examples:
                    examples.append(f"{h.path[:70]} \u2192 {h.status}")
    return total, four, examples


def cross_traffic(evidence: list[ContainerEvidence], owners: dict[int, str],
                  expected: dict[int, set[str]] | None = None) -> list[str]:
    """Findings for pools that served a window other than their owner.
    `expected` (pool -> window letters) lists traffic the run explains -- a
    window that borrowed the pool while its own was built, or shares it at
    the resource limit -- which is the design, not a leak, so it is left out."""
    out = []
    for ev in evidence:
        owner = owners.get(ev.pool)
        allowed = (expected or {}).get(ev.pool, set())
        others = [w for w in ev.windows() if owner and w != owner and w not in allowed]
        if others:
            out.append(f"Pool {ev.pool} (owned by window {owner}) also served window(s) "
                       f"{', '.join(others)}, which neither borrowed nor shares it.")
    return out
