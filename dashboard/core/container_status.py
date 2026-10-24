"""Interpreting `docker compose ps --format json` container records.

One vocabulary for "what state is this container in", shared by the
Workloads page's per-target summary and the Health diagram's per-node
coloring, so the two can never disagree about e.g. whether a cleanly
exited one-shot job counts as "up".
"""
from __future__ import annotations

from core.colors import GREEN, GREY, ORANGE, RED

# classify() results, in rough severity order.
HEALTHY, STARTING, RUNNING, UNHEALTHY, EXITED_OK, EXITED_BAD, STOPPED, CREATED, DOWN = (
    "healthy", "starting", "running", "unhealthy", "exited_ok", "exited_bad", "stopped", "created", "down",
)

# Run-once ("one-shot") jobs: the services whose healthy terminal state IS a
# clean exit -- they do their work and stop on purpose, and every service that
# needs them waits on `condition: service_completed_successfully` (which is
# exactly how this set is derived: grep the compose files for it). For any
# service NOT listed here a clean exit means it is OFF, not "done" -- it is a
# long-running service (database, web server, honeypot, proxy, log shipper,
# ...) that is supposed to stay up. classify() reports those as STOPPED rather
# than EXITED_OK so a stopped-but-required service never reads as "completed"
# and is never counted toward "up". Keep in sync with the compose files:
#   ids:  ids/docker-compose.yml, ids/docker-compose.db-proxy.yml
#   siem: siem/docker/docker-compose.yml
RUN_ONCE_SERVICES = frozenset({
    "init_setup", "honeypot_db_migration", "production_db_seed",  # ids
    "init-password", "kibana_dashboards_setup",                   # siem
})


def exit_code_ok(container: dict) -> bool:
    return str(container.get("ExitCode", "0")) in ("0", "")


def is_run_once(container: dict | None) -> bool:
    """True for a one-shot job whose clean exit is its finished state (see
    RUN_ONCE_SERVICES). A record without a Service name is treated as
    long-running -- the safe default, so an unexplained clean exit reads as
    STOPPED (off) rather than silently counting as "done"."""
    if not container:
        return False
    return container.get("Service", "") in RUN_ONCE_SERVICES


def finished_ok(containers: list[dict]) -> list[dict]:
    """One-shot jobs that have exited successfully (safe to clean up). A
    running container also reports ExitCode 0, so State must say exited; a job
    that failed is left out so its container and logs stay inspectable."""
    return [c for c in containers if c.get("State") == "exited" and exit_code_ok(c)]


def classify(container: dict | None) -> str:
    if container is None:
        return DOWN
    state = container.get("State", "")
    health = container.get("Health", "")
    if state == "running":
        if health == "unhealthy":
            return UNHEALTHY
        if health == "healthy":
            return HEALTHY
        # Still inside its healthcheck's start_period (the MySQL pools take
        # minutes on a first boot while they initialise their data dir).
        # Kept apart from RUNNING, which means "no healthcheck at all", so a
        # database that is still coming up doesn't read as settled.
        if health == STARTING:
            return STARTING
        return RUNNING
    if state == "exited":
        if not exit_code_ok(container):
            return EXITED_BAD
        # A clean exit is the finished state of a one-shot job, but "off" for
        # a long-running service that is supposed to stay up (see
        # RUN_ONCE_SERVICES) -- the latter must not read as "completed".
        return EXITED_OK if is_run_once(container) else STOPPED
    if state == "created":
        # `docker compose up` creates every container in the dependency
        # graph up front, then starts them in order -- if that process gets
        # interrupted partway (closed terminal/app, killed mid-command),
        # whatever hasn't started yet is left here indefinitely; it does
        # NOT self-heal, and is otherwise indistinguishable from "down"
        # (not created at all), which reads as "not started on purpose"
        # -- very different from "up got interrupted, re-run it."
        return CREATED
    return DOWN


def is_ready(container: dict | None) -> bool:
    """True once a container is done starting: a one-shot job that exited
    cleanly, or a running container that either has no healthcheck or has
    already passed one. A container classify() calls STARTING is not
    ready yet -- that gap is exactly what a restart progress bar needs to
    show."""
    if container is None:
        return False
    state = container.get("State")
    if state == "exited":
        # Only a one-shot job that exited cleanly is "done". A long-running
        # service sitting at exited/0 is off, not ready -- a restart that
        # lands it here hasn't actually brought it back up.
        return exit_code_ok(container) and is_run_once(container)
    return state == "running" and container.get("Health", "") in ("", HEALTHY)


def start_settled(containers: list[dict], up_exit_code: int | None) -> bool:
    """True once a `docker compose up -d` has nothing left in flight.

    `up -d` itself only exits after every depends_on condition it had to
    wait for was met (or failed), so its exit is the first requirement --
    before that, `ps` can show a subset that already looks ready while
    later services are still waiting on their dependencies. After it,
    every container must have left its transitional states (created,
    health "starting"): an unhealthy or crashed container counts as
    settled too, because waiting longer won't change it and the report
    should show it rather than run into its time cap.

    `up_exit_code` is None while `up -d` is still running. A non-zero exit
    (a dependency failed, so its dependents stay "created" for good) is
    settled straight away for the same reason."""
    if up_exit_code is None:
        return False
    if up_exit_code != 0:
        return True
    if not containers:
        return False
    return all(classify(c) not in (CREATED, STARTING, DOWN) for c in containers)


def status_detail(container: dict | None) -> str:
    if container is None:
        return "not created / never started"
    return container.get("Status", container.get("State", "unknown"))


def summarize(containers: list[dict]) -> tuple[str, str]:
    """(summary_text, color) for a whole target's container list.

    A container mid-Start legitimately passes through State=created and
    Health=starting; neither gets alarming wording (an earlier "created but
    never started -- re-run Start" message was an alarming false positive
    during a normal in-progress Start), they simply don't count as up.
    Only genuine run-once jobs (init_setup, the migrations/seed jobs; see
    RUN_ONCE_SERVICES) end in exited/0 as their successful terminal state, so
    only they count toward "up" as "completed". A long-running service sitting
    at exited/0 is OFF, not done (classify() -> STOPPED): it does NOT count as
    up, so a mostly-stopped stack can never read "all N up" just because the
    stopped containers happen to carry a clean exit code."""
    if not containers:
        return "not running / unreachable", GREY

    counts = {}
    for c in containers:
        status = classify(c)
        counts[status] = counts.get(status, 0) + 1
    total = len(containers)
    healthy = counts.get(HEALTHY, 0)
    unhealthy = counts.get(UNHEALTHY, 0)
    exited_bad = counts.get(EXITED_BAD, 0)
    exited_ok = counts.get(EXITED_OK, 0)
    starting = counts.get(STARTING, 0)
    stopped = counts.get(STOPPED, 0)
    up = healthy + counts.get(RUNNING, 0) + unhealthy + exited_ok

    if unhealthy or exited_bad:
        extra = f", {stopped} stopped" if stopped else ""
        return f"{up}/{total} up ({unhealthy} unhealthy, {exited_bad} exited with error{extra})", RED
    if up == total:
        details = []
        if healthy:
            details.append(f"{healthy} healthy")
        if exited_ok:
            details.append(f"{exited_ok} completed")
        detail = f" ({', '.join(details)})" if details else ""
        return f"all {total} up{detail}", GREEN
    waiting = []
    if starting:
        waiting.append(f"{starting} starting")
    if stopped:
        waiting.append(f"{stopped} stopped")
    detail = f" ({', '.join(waiting)})" if waiting else ""
    if up > 0:
        return f"{up}/{total} up{detail}", ORANGE
    return f"0/{total} up{detail}", GREY
