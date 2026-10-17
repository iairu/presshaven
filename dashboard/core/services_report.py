"""Start/Stop-with-graph-export for the Workloads page.

While the user starts or stops a stack, this samples -- in the background --
overall host CPU/RAM (from /proc, local or over SSH) plus per-container CPU and
memory (cgroup files, or docker stats), on threads of their own, watches
`docker compose ps` for major events (containers appearing, going
healthy/unhealthy, stopping, being removed) and draws the target's tiles of the
Global Visualization page at a few stages (before / coming up / settled) from
that same `ps` result. It then renders a single PDF, in the same bundled
Baskerville face as the pattern report, with:

  * an overall system CPU % + RAM % chart,
  * per-container CPU and memory charts,
  * a dashed vertical line on every chart for each major event,
  * a callout placing the largest host CPU peak among the event markers,
  * warnings (failed / killed containers, error-word log lines),
  * the tile snapshots showing the stack change state.

The worker (a QThread) only MEASURES; the Services panel runs the actual
`docker compose up -d` / `down` alongside it. Screenshots must be taken on the
GUI thread, so -- like core.pattern_report -- the worker emits a request and
blocks on an event until the GUI thread hands back a PNG path.
"""
from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

from PyQt6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QImage, QPen, QPolygonF, QTextDocument
from PyQt6.QtPrintSupport import QPrinter

from core import resource_stats as rs
from core.container_status import classify, start_settled
from core.startup_events import (MARKER_WINDOW_S, chart_groups, detect_events as _detect_events,
                                  dominant_series, event_markers, event_state, fmt_tick, nice_axis,
                                  nice_step, peak_context, sample_gaps, split_at_gaps, start_warnings,
                                  stop_warnings)
from core.docker_ctl import Target
from core.pattern_report_pdf import _report_font_family, _FONT_CSS_STACK, _esc
from core import diagrams, report_pagination, vector_figures
from core.vector_figures import VectorFigure
from core import report_stats as st

SAMPLE_INTERVAL_S = 2.0
# When the fast cgroup sampler is available (local host), sample resources this
# often (sub-second) for a dense usage curve, and only do the heavier
# `docker compose ps` status/event check this often (it's ~0.5s per call).
# Sampling runs on threads of its own, so a slow `ps` or a screenshot never
# leaves a hole in the curves.
FAST_SAMPLE_INTERVAL_S = 0.25
# Host /proc over SSH costs a round trip per read.
REMOTE_HOST_INTERVAL_S = 1.0
STATUS_CHECK_INTERVAL_S = 1.5
# A safety cap, not the normal end of a start recording: that is
# container_status.start_settled(). It has to outlast the slowest legitimate
# start -- on a first boot the three honeypot MySQL pools initialise one after
# another for minutes (their healthchecks allow a 420s start_period), and
# `up -d` may build images first. The old 150s cap cut recordings off while
# the databases were still coming up.
START_MAX_SECONDS = 900.0
STOP_MAX_SECONDS = 90.0
# Keep sampling at least this long after the stack first looks settled, to
# catch the post-startup tail (background jobs, first healthchecks)...
SETTLE_TAIL_S = 8.0
# ...and then until every container has been quiet (mean CPU below
# QUIET_CPU_PCT over the last QUIET_WINDOW_S), for at most QUIET_MAX_EXTRA_S
# more: a WordPress still warming its caches after its healthcheck passed
# used to be cut off mid-climb.
QUIET_WINDOW_S = 10.0
QUIET_CPU_PCT = 30.0
QUIET_MAX_EXTRA_S = 120.0

_SYS_CPU_COLOR = "#1565c0"
# Categorical slots in fixed order: blue, orange, green, red, purple, brown,
# pink, cyan. Slots 5-8 are also drawn dashed, so neighbours in hue (blue /
# cyan, orange / red) differ in line style too. A chart never holds more
# than 8 series.
_CATEGORICAL = ("#1f6fd1", "#f28e2b", "#2ca02c", "#d62728", "#8a5cc2", "#8c564b",
                "#e377c2", "#17a2b8")
_SYS_RAM_COLOR = "#e08a00"


@dataclass
class ServicesReport:
    started_at: str = ""              # local wall-clock time of t = 0 (the command's launch)
    generated_at: str = ""            # when the PDF was rendered
    target_label: str = ""
    project: str = ""                 # "edge" | "siem"
    operation: str = "start"          # "start" | "stop"
    duration_s: float = 0.0
    exit_code: int | None = None      # the compose command's exit code
    hit_time_cap: bool = False        # stopped by START/STOP_MAX_SECONDS, not by settling
    # (elapsed_s, cpu_pct, ram_pct) for the whole host:
    sys_samples: list = field(default_factory=list)
    # (elapsed_s, {service: (cpu_pct | None, mem_bytes)}); cpu is None on a
    # container's first sample, which has no previous reading to diff against:
    container_samples: list = field(default_factory=list)
    # (elapsed_s, label):
    events: list = field(default_factory=list)
    # (caption, png_path, elapsed_s | None):
    stage_shots: list = field(default_factory=list)
    # Where per-container CPU/memory came from (cgroup files or docker stats).
    resource_source: str = ""
    host_interval_s: float = FAST_SAMPLE_INTERVAL_S
    container_interval_s: float = FAST_SAMPLE_INTERVAL_S
    cpu_count: int = 0
    host_mem_bytes: int = 0
    # {service: bytes}, for containers with a memory limit:
    mem_limits: dict = field(default_factory=dict)
    # (service, what is wrong): start_warnings() / stop_warnings().
    warnings: list = field(default_factory=list)
    # {service: count}: the red error badges already on this target's tiles
    # when the "before" screenshot was taken (lines logged before t = 0).
    badges_before: dict = field(default_factory=dict)
    # Running containers without a healthcheck once the start settled: their
    # last event is "started", there is no "healthy" to wait for.
    no_healthcheck: list = field(default_factory=list)
    # Start only: True once every container went quiet before the recording
    # ended, False if it stopped with containers still busy (busy_at_end).
    quiet: bool | None = None
    busy_at_end: list = field(default_factory=list)   # (service, mean cpu %)
    # Stop only: stop events moved back to the moment the container's cgroup
    # disappeared (its processes exited) rather than when ps noticed.
    stops_backdated: bool = False


# ---- host /proc sampling (works local or over SSH via Target.build_shell) ----

def _read_system(target: Target) -> tuple[int, int, int, int, int] | None:
    """(cpu_total_jiffies, cpu_idle_jiffies, mem_total_kb, mem_avail_kb,
    cpu_count) from the host's /proc, or None if unavailable."""
    argv, cwd = target.build_shell("cat /proc/stat /proc/meminfo")
    try:
        res = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=10)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if res.returncode != 0:
        return None
    cpu_total = cpu_idle = 0
    mem_total = mem_avail = 0
    ncpu = 0
    for line in res.stdout.splitlines():
        if line.startswith("cpu ") and cpu_total == 0:
            parts = line.split()[1:]
            nums = [int(p) for p in parts if p.isdigit()]
            if len(nums) >= 5:
                cpu_total = sum(nums)
                cpu_idle = nums[3] + nums[4]  # idle + iowait
        elif line.startswith("cpu") and line[3:4].isdigit():
            ncpu += 1
        elif line.startswith("MemTotal:"):
            mem_total = int(line.split()[1])
        elif line.startswith("MemAvailable:"):
            mem_avail = int(line.split()[1])
    if cpu_total == 0 or mem_total == 0:
        return None
    return cpu_total, cpu_idle, mem_total, mem_avail, ncpu


_STOP_STATES = ("stopped", "stopped and removed", "stopped (non-zero exit)")


class ServicesReportWorker(QThread):
    progress = pyqtSignal(str, int, int)       # message, current, total (per-mille)
    health_shot_request = pyqtSignal(str)      # caption/key -> GUI grabs Global Visualization page
    finished_ok = pyqtSignal(object)           # ServicesReport
    failed = pyqtSignal(str)
    # Emitted once the idle "before" shot is taken and sampling is primed; the
    # Services panel launches the compose command on it, so t=0 is that launch.
    ready_to_run = pyqtSignal()

    def __init__(self, target: Target, operation: str, parent=None):
        super().__init__(parent)
        self._target = target
        self._operation = "stop" if operation == "stop" else "start"
        self._max_seconds = STOP_MAX_SECONDS if self._operation == "stop" else START_MAX_SECONDS
        self._cancel = False
        self._shot_event = threading.Event()
        self._shot_result: dict[str, str] = {}
        self._shot_badges: dict[str, dict] = {}
        # The `docker compose ps -a` result a requested screenshot must show
        # (read by the GUI thread in its health_shot_request handler), so the
        # picture matches the state the report logged, not whatever the
        # dashboard's own status poller fetched last.
        self.shot_containers: list[dict] = []
        # Set by the Services panel when the underlying `docker compose up/down`
        # process exits, so a stop is recorded until the command actually
        # finishes rather than guessing from `ps` going empty.
        self._op_done = threading.Event()
        self._op_exit_code: int | None = None
        # Shared with the sampling threads.
        self._lock = threading.Lock()
        self._last_seen: dict[str, float] = {}   # service -> elapsed of its latest sample
        self._cgroup_failed = False              # running containers, but no cgroup files found
        self._mem_limits: dict[str, int] = {}

    def cancel(self) -> None:
        self._cancel = True

    def notify_operation_finished(self, exit_code: int) -> None:
        """Called (GUI thread) when the compose command for this export exits.
        For a start that's `up -d`, which returns once every depends_on
        condition it waited on was met; for a stop it's `down`."""
        self._op_exit_code = exit_code
        self._op_done.set()

    def provide_health_shot(self, key: str, path: str, badges: dict | None = None) -> None:
        """Called on the GUI thread with the grabbed Health-page PNG path and
        the error-badge counts shown on this target's tiles."""
        self._shot_result[key] = path
        self._shot_badges[key] = dict(badges or {})
        self._shot_event.set()

    def _grab_health(self, key: str, containers: list[dict]) -> str:
        if self._cancel:
            return ""
        self.shot_containers = list(containers)
        self._shot_event.clear()
        self._shot_result.pop(key, None)
        self.health_shot_request.emit(key)
        self._shot_event.wait(timeout=20)
        return self._shot_result.get(key, "")

    def _ps(self, expect_some: bool = False) -> list[dict]:
        """`docker compose ps -a`. ps() returns [] on any failure too, and
        during a `down` it can fail transiently, which used to log every
        container as stopped and then started again. So when containers were
        there last time (``expect_some``), an empty answer is re-checked
        before it is believed."""
        containers = self._target.ps()
        for _ in range(2):
            if containers or not expect_some or self._cancel:
                break
            time.sleep(0.5)
            containers = self._target.ps()
        return containers

    @staticmethod
    def _status_of(containers: list[dict]) -> dict:
        status = {}
        for c in containers:
            svc = c.get("Service") or c.get("Name") or ""
            if svc:
                status[svc] = classify(c)
        return status

    def _logs_since(self, seconds: float) -> str:
        """`docker compose logs` written in the last ``seconds`` (best effort)."""
        try:
            argv, cwd = self._target.build("logs", "--no-color", "--since", f"{int(seconds)}s")
            res = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=60)
            return res.stdout if res.returncode == 0 else ""
        except (subprocess.TimeoutExpired, OSError):
            return ""

    def _follow_logs(self):
        """Stream `docker compose logs -f` from now on, for a stop: `down`
        removes the containers, and their logs with them, before the
        recording ends. Returns (process, lines) or (None, [])."""
        lines: list[str] = []
        try:
            argv, cwd = self._target.build("logs", "-f", "--no-color", "--since", "1s")
            proc = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                    text=True, errors="replace")
        except OSError:
            return None, lines

        def pump():
            for line in proc.stdout:
                lines.append(line)
        threading.Thread(target=pump, daemon=True).start()
        return proc, lines

    def _host_warnings(self) -> list[tuple[str, str]]:
        """Host kernel settings this stack needs (core/host_settings.py)."""
        from core import host_settings
        return [("host", p.text() + " Fix: " + host_settings.fix_commands([p]).replace("\n", "; "))
                for p in host_settings.target_problems(self._target) or []]

    def _use_stats(self, sampler) -> bool:
        """docker stats instead of cgroup files: a remote target, a docker
        whose PIDs aren't on this host, or cgroup files that couldn't be found."""
        return self._target.is_remote or sampler.foreign or self._cgroup_failed

    # -- sampling threads --

    def _host_loop(self, data: ServicesReport, start: float, prev_cpu, stop: threading.Event) -> None:
        interval = data.host_interval_s
        while not stop.is_set():
            t0 = time.time()
            sysread = _read_system(self._target)
            if sysread:
                ct, ci, mt, ma, _n = sysread
                if prev_cpu is not None and ct > prev_cpu[0]:
                    cpu_pct = max(0.0, min(100.0, 100.0 * (1.0 - (ci - prev_cpu[1]) / (ct - prev_cpu[0]))))
                    ram_pct = 100.0 * (1.0 - ma / mt) if mt else 0.0
                    with self._lock:
                        data.sys_samples.append((round(t0 - start, 2), round(cpu_pct, 1),
                                                 round(ram_pct, 1)))
                prev_cpu = (ct, ci)
            stop.wait(max(0.0, interval - (time.time() - t0)))

    def _container_loop(self, data: ServicesReport, sampler, start: float,
                        stop: threading.Event) -> None:
        prev_snap: dict = {}
        while not stop.is_set():
            t0 = time.time()
            if self._use_stats(sampler):
                try:
                    live = rs.collect_live(self._target)
                except Exception:  # noqa: BLE001 -- best-effort
                    live = []
                # Only containers that really run: a created (not yet
                # started) one has no stats, and plotting it as 0 drew a
                # ramp from its creation to its first real sample.
                snap = {r.service: (r.cpu_percent, r.mem_used_bytes) for r in live
                        if r.state == "running"}
                limits = {r.service: r.mem_limit_bytes for r in live
                          if r.state == "running" and r.mem_limit_bytes
                          and (not data.host_mem_bytes or r.mem_limit_bytes < 0.95 * data.host_mem_bytes)}
                interval = SAMPLE_INTERVAL_S
            else:
                with self._lock:
                    rows = sampler.sample() if sampler.available else []
                # A container's first cgroup reading has no CPU delta yet.
                snap = {svc: (cpu if svc in prev_snap else None, mem) for svc, cpu, mem in rows}
                limits = {}
                interval = FAST_SAMPLE_INTERVAL_S
            elapsed = round(t0 - start, 2)
            with self._lock:
                if snap:
                    data.container_samples.append((elapsed, snap))
                for svc in snap:
                    self._last_seen[svc] = elapsed
                self._mem_limits.update(limits)
            prev_snap = snap
            stop.wait(max(0.0, interval - (time.time() - t0)))

    def _backdate_stops(self, events: list, first_new: int, elapsed: float) -> bool:
        """During a stop, `ps` only notices a container once Docker has
        removed it, up to a couple of seconds after its processes exited --
        which is when its cgroup (and its chart line) disappeared. Move such
        "stopped" events back to just after the container's last sample.
        Only with cgroup sampling: docker stats is too coarse to say."""
        moved = False
        with self._lock:
            for i in range(first_new, len(events)):
                t, label = events[i]
                svc, state = event_state(label)
                last = self._last_seen.get(svc)
                if state in _STOP_STATES and last is not None and last + 0.5 < t:
                    events[i] = (round(min(elapsed, last + FAST_SAMPLE_INTERVAL_S), 1), label)
                    moved = True
        return moved

    def _quiet(self, data: ServicesReport, now_elapsed: float) -> tuple[bool, list]:
        """Is every container's mean CPU over the last QUIET_WINDOW_S below
        QUIET_CPU_PCT? Returns (quiet, [(service, mean), ...] of the busy ones)."""
        lo = now_elapsed - QUIET_WINDOW_S
        vals: dict[str, list[float]] = {}
        with self._lock:
            for t, snap in data.container_samples:
                if t < lo:
                    continue
                for svc, (cpu, _mem) in snap.items():
                    if cpu is not None:
                        vals.setdefault(svc, []).append(cpu)
        busy = sorted(((svc, sum(v) / len(v)) for svc, v in vals.items()
                       if v and sum(v) / len(v) >= QUIET_CPU_PCT), key=lambda kv: -kv[1])
        return not busy, busy

    def run(self) -> None:
        try:
            self._run()
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"Services graph export failed: {e}")

    def _run(self) -> None:
        op = self._operation
        data = ServicesReport(target_label=self._target.label, project=self._target.project,
                              operation=op)
        if self._target.is_remote:
            data.host_interval_s = REMOTE_HOST_INTERVAL_S

        ps = self._ps()
        data.stage_shots.append(("Before: stack idle / not yet changed",
                                 self._grab_health("before", ps), None))
        data.badges_before = self._shot_badges.get("before", {})

        # Fast (sub-second) per-container sampling from cgroups on a local
        # host; falls back to ~2s docker-stats sampling for a remote target.
        # The sampler is refreshed on every status check below, so a start
        # from a stopped stack picks containers up as soon as they run.
        sampler = rs.FastSampler(self._target)
        if sampler.available:
            sampler.sample()  # prime CPU% delta baseline
            self._mem_limits.update(sampler.mem_limits())
        # Baseline status before the operation, so the first check only
        # logs real changes (a stop used to open with a "started" event for
        # every container that was already running).
        prev_status = self._status_of(ps)
        prime = _read_system(self._target)
        prev_cpu = (prime[0], prime[1]) if prime else None
        if prime:
            data.host_mem_bytes, data.cpu_count = prime[2] * 1024, prime[4]
        follower, stop_logs = self._follow_logs() if op == "stop" else (None, [])
        exit_codes: dict[str, int] = {}

        # The recording clock starts here, when the operation is launched --
        # not at thread start, so a slow "before" screenshot or sampler setup
        # can't push every sample (and event) to a late elapsed time.
        self.ready_to_run.emit()
        start = time.time()
        data.started_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")
        stop_sampling = threading.Event()
        threads = [threading.Thread(target=self._host_loop, args=(data, start, prev_cpu, stop_sampling),
                                    daemon=True),
                   threading.Thread(target=self._container_loop, args=(data, sampler, start, stop_sampling),
                                    daemon=True)]
        for th in threads:
            th.start()

        captured_mid = captured_end = False
        settled_at: float | None = None
        last_status_check = -1e9
        try:
            while not self._cancel:
                elapsed = time.time() - start
                if elapsed > self._max_seconds:
                    data.hit_time_cap = True
                    break
                self.progress.emit(
                    f"Recording {op} ({int(elapsed)}s)",
                    int(min(0.95, elapsed / self._max_seconds) * 1000), 1000)

                if op == "stop" and self._op_done.is_set():
                    # `down` exited: one last look, then the final shot.
                    ps = self._ps()
                    status = self._status_of(ps)
                    n = len(data.events)
                    _detect_events(prev_status, status, time.time() - start, data.events, op)
                    if self._backdate_stops(data.events, n, time.time() - start):
                        data.stops_backdated = True
                    data.stage_shots.append(("Stopped: down command finished",
                                             self._grab_health("end", ps),
                                             round(time.time() - start, 1)))
                    captured_end = True
                    data.exit_code = self._op_exit_code
                    break

                if time.time() - last_status_check >= STATUS_CHECK_INTERVAL_S:
                    last_status_check = time.time()
                    check_t = time.time() - start
                    ps = self._ps(expect_some=bool(prev_status))
                    status = self._status_of(ps)
                    n = len(data.events)
                    _detect_events(prev_status, status, check_t, data.events, op)
                    was_status, prev_status = prev_status, status
                    with self._lock:
                        sampler.refresh(ps)
                        if sampler.available:
                            self._mem_limits.update(sampler.mem_limits())
                    if (not self._use_stats(sampler) and not sampler.available
                            and any(c.get("State") == "running" for c in ps)):
                        self._cgroup_failed = True

                    if op == "start":
                        if not captured_mid and status:
                            data.stage_shots.append(("Starting: containers coming up",
                                                     self._grab_health("mid", ps), round(check_t, 1)))
                            captured_mid = True
                        # Settled = `up -d` has exited AND nothing is still
                        # created/health-starting. Checking only that every
                        # container in `ps` looked ready ended the recording
                        # while services further down the dependency chain
                        # hadn't even been started yet.
                        if settled_at is None and start_settled(
                                ps, self._op_exit_code if self._op_done.is_set() else None):
                            settled_at = time.time()
                            data.exit_code = self._op_exit_code
                            data.no_healthcheck = sorted(
                                c.get("Service", "") for c in ps if classify(c) == "running")
                            all_healthy = all(classify(c) in ("healthy", "running", "exited_ok")
                                              for c in ps)
                            caption = ("All containers healthy" if all_healthy
                                       else "Start finished (some containers not healthy)")
                            data.stage_shots.append((caption, self._grab_health("end", ps),
                                                     round(time.time() - start, 1)))
                            captured_end = True
                        if settled_at is not None and time.time() - settled_at > SETTLE_TAIL_S:
                            quiet, busy = self._quiet(data, time.time() - start)
                            if quiet:
                                data.quiet = True
                                break
                            if time.time() - settled_at > SETTLE_TAIL_S + QUIET_MAX_EXTRA_S:
                                data.quiet, data.busy_at_end = False, busy
                                break
                    else:  # stop
                        for c in ps:
                            if classify(c) == "exited_bad":
                                try:
                                    exit_codes[c.get("Service", "?")] = int(c.get("ExitCode"))
                                except (TypeError, ValueError):
                                    pass
                        if self._backdate_stops(data.events, n, check_t):
                            data.stops_backdated = True
                        if not captured_mid and status != was_status:
                            data.stage_shots.append(("Stopping: containers going down",
                                                     self._grab_health("mid", ps), round(check_t, 1)))
                            captured_mid = True

                time.sleep(0.1)
        finally:
            stop_sampling.set()
            for th in threads:
                th.join(timeout=15)
            if follower is not None:
                follower.terminate()
                try:
                    follower.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    follower.kill()

        # Best-effort final shot if we never captured an end state.
        if not captured_end:
            ps = self._ps()
            data.stage_shots.append(("Final state", self._grab_health("end", ps),
                                     round(time.time() - start, 1)))

        data.duration_s = round(time.time() - start, 1)
        data.events.sort(key=lambda e: e[0])
        data.mem_limits = dict(self._mem_limits)
        if self._use_stats(sampler):
            data.container_interval_s = SAMPLE_INTERVAL_S
        if op == "start":
            data.warnings = start_warnings(self._ps(), self._logs_since(data.duration_s + 15))
        else:
            data.warnings = stop_warnings(exit_codes, "".join(stop_logs))
        data.warnings += self._host_warnings()
        if data.warnings:
            data.stage_shots = [
                (f"{cap} — but {len(data.warnings)} warning(s), see Warnings"
                 if cap == "All containers healthy" else cap, path, t)
                for cap, path, t in data.stage_shots]
        data.resource_source = rs.describe_sampling(sampler, FAST_SAMPLE_INTERVAL_S)
        if self._cgroup_failed and not sampler.foreign and not self._target.is_remote:
            data.resource_source = ("read with docker stats (~2 s per sample): the containers' "
                                    "cgroup files could not be found")
        # Drop stages whose grab failed (empty path) so the PDF has no blanks.
        data.stage_shots = [s for s in data.stage_shots if s[1]]
        self.finished_ok.emit(data)


# ---- rendering ----

def _event_markers(events: list) -> list[tuple[int, float, float, list[str]]]:
    """See startup_events.event_markers(): each marker is drawn on the graphs
    as one short numbered tag, and the event key spells out what it covers,
    so labels never sit on top of the data lines."""
    return event_markers(events)


def _summarize_events(labels: list[str]) -> str:
    """'a healthy', 'b healthy', 'c started' -> 'healthy: a, b; started: c'.

    ``labels`` are in time order. A service's event joins the earlier group of
    its state only when that service has no event in a group after it, so
    "x started" is never listed after "x finished"; a "running, health
    pending" followed by healthy / unhealthy within the marker is left out
    (it read "healthy: x; running, health pending: x")."""
    events = [event_state(label) for label in labels]
    settled = {svc for svc, state in events if state in ("healthy", "unhealthy")}
    groups: list[tuple[str, list[str]]] = []
    for svc, state in events:
        if state == "running, health pending" and svc in settled:
            continue
        target = None
        for k in range(len(groups) - 1, -1, -1):
            if groups[k][0] == state:
                target = k
                break
            if svc in groups[k][1]:
                break           # this service already has a later event
        if target is None:
            groups.append((state, [svc]))
        else:
            groups[target][1].append(svc)
    return "; ".join(f"{state}: {', '.join(svcs)}" if state else ", ".join(svcs)
                     for state, svcs in groups)


def _fmt_t(t: float) -> str:
    """Elapsed seconds with one decimal: whole seconds made markers 1.6 s
    apart read as '17 s' and '18 s'."""
    return f"{t:.1f}"


def _max_gap(interval: float) -> float:
    """Longest spacing still drawn as a connected line: a few missed ticks."""
    return max(1.0, 4 * interval)


def _legend_layout(fm: QFontMetrics, items: list[str], width: float) -> list[tuple[int, float, int]]:
    """(item index, x, row) for legend entries wrapped into ``width``."""
    out, x, row = [], 0.0, 0
    for i, text in enumerate(items):
        w = 26 + fm.horizontalAdvance(text) + 18
        if x > 0 and x + w > width:
            x, row = 0.0, row + 1
        out.append((i, x, row))
        x += w
    return out


def _ts_chart(series: dict, colors: dict, events: list, y_label: str,
              family: str, t_end: float, max_gap: float, y_max: float | None = None,
              annotate_peak: str | None = None, styles: dict | None = None,
              unit: str = "", legend_names: dict | None = None) -> VectorFigure:
    """A multi-series time-series chart with a dashed red vertical line per
    event marker (see _event_markers). Each marker's number sits on white in a
    band above the plot, on its own row when tags would overlap -- the same
    layout the pattern report uses -- and the event key below the host chart
    says what each number means.

    ``series`` maps name -> [(t, value), ...]; ``colors`` name -> QColor;
    ``styles`` name -> Qt.PenStyle. Every chart in a report gets the same
    ``t_end`` (the recorded window), so markers line up down the page. A
    line is broken wherever samples are more than ``max_gap`` apart (nothing
    was measured there), and a series that ends before the window does gets
    a small cross at its last sample. The legend, with each series' peak,
    is drawn under the axis."""
    styles = styles or {}
    legend_names = legend_names or {}
    W = 900
    ml, mr = 64, 20
    plot_w = W - ml - mr

    all_vals = [v for pts in series.values() for _t, v in pts]
    span = max(t_end, 1.0)
    if y_max is not None:
        ymax, ystep = y_max, nice_step(y_max, 4)
    else:
        ymax, ystep = nice_axis(max(all_vals + [1.0]), 4)

    def X(t):
        return ml + (t / span) * plot_w

    markers = [m for m in _event_markers(events) if 0 <= m[1] <= span]
    tag_font = QFont(family, 8)
    fm = QFontMetrics(tag_font)
    row_h = fm.height() + 3
    rows_end: list[float] = []
    placed = []  # (x, left, width, row, number)
    for n, t0, _t1, _labels in markers:
        x = X(t0)
        w = fm.horizontalAdvance(str(n)) + 8
        left = min(max(x - w / 2, 2), W - 2 - w)
        row = next((r for r, end in enumerate(rows_end) if left > end + 2), None)
        if row is None:
            rows_end.append(left + w)
            row = len(rows_end) - 1
        else:
            rows_end[row] = left + w
        placed.append((x, left, w, row, n))

    legend_font = QFont(family, 9)
    lfm = QFontMetrics(legend_font)
    names = [n for n in series if series[n]]
    peak_fmt = (lambda v: f"{v:.0f}{unit}") if unit else (lambda v: f"{v:.0f}")
    legend_items = [f"{legend_names.get(n, n)} (peak {peak_fmt(max(v for _t, v in series[n]))})"
                    for n in names]
    legend = _legend_layout(lfm, legend_items, plot_w)
    legend_rows = (max(r for _i, _x, r in legend) + 1) if legend else 0
    legend_h = legend_rows * (lfm.height() + 4)

    band_top = 22
    mt = band_top + len(rows_end) * row_h + 6
    plot_h = 228
    axis_h = 30
    H = mt + plot_h + axis_h + legend_h + 8
    img, p = vector_figures.new_figure(W, H)

    def Y(v):
        return mt + (1 - min(max(v, 0.0), ymax) / ymax) * plot_h

    p.setFont(QFont(family, 9))
    k = 0
    while k * ystep <= ymax + 1e-9:
        v = k * ystep
        y = Y(v)
        p.setPen(QPen(QColor("#e6e6e6"), 1))
        p.drawLine(QPointF(ml, y), QPointF(ml + plot_w, y))
        p.setPen(QColor("#333333"))
        p.drawText(QRectF(0, y - 8, ml - 8, 16), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                   fmt_tick(v, ystep))
        k += 1
    tstep = nice_step(span, 8)
    k = 0
    while k * tstep <= span + 1e-9:
        t = k * tstep
        x = X(t)
        p.setPen(QPen(QColor("#999999"), 1))
        p.drawLine(QPointF(x, mt + plot_h), QPointF(x, mt + plot_h + 4))
        p.setPen(QColor("#333333"))
        p.drawText(QRectF(x - 30, mt + plot_h + 5, 60, 16), int(Qt.AlignmentFlag.AlignHCenter),
                   fmt_tick(t, tstep) + "s")
        k += 1
    p.setPen(QPen(QColor("#333333"), 2))
    p.drawLine(QPointF(ml, mt), QPointF(ml, mt + plot_h))
    p.drawLine(QPointF(ml, mt + plot_h), QPointF(ml + plot_w, mt + plot_h))
    p.setPen(QColor("#111111"))
    p.drawText(6, 14, y_label)

    for name, pts in series.items():
        if not pts:
            continue
        pen = QPen(colors.get(name, QColor("#333333")), 2.5)
        pen.setStyle(styles.get(name, Qt.PenStyle.SolidLine))
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for seg in split_at_gaps(pts, max_gap):
            if len(seg) == 1:
                t, v = seg[0]
                p.setBrush(colors.get(name, QColor("#333333")))
                p.drawEllipse(QPointF(X(t), Y(v)), 2.5, 2.5)
                p.setBrush(Qt.BrushStyle.NoBrush)
                continue
            p.drawPolyline(QPolygonF([QPointF(X(t), Y(v)) for t, v in seg]))
        t_last, v_last = pts[-1]
        if t_last < span - max_gap:
            # The container stopped (or a one-shot job exited) here.
            cx, cy = X(t_last), Y(v_last)
            cross = QPen(colors.get(name, QColor("#333333")), 2)
            p.setPen(cross)
            p.drawLine(QPointF(cx - 4, cy - 4), QPointF(cx + 4, cy + 4))
            p.drawLine(QPointF(cx - 4, cy + 4), QPointF(cx + 4, cy - 4))

    # Marker lines over the data (thin and dashed, so they stay red and
    # visible where a line runs steeply through them). A marker at 0 s would
    # sit on the y-axis and read as part of it: it keeps only its tag.
    for x, _left, _w, row, _n in placed:
        if x - ml < 4:
            continue
        # 2 px with long dashes: a hairline dash shrinks below a device pixel
        # in a PDF viewer and blends to grey, which read as a black line.
        pen = QPen(QColor("#d32f2f"), 2.0)
        pen.setDashPattern([3.0, 2.0])
        p.setPen(pen)
        p.drawLine(QPointF(x, band_top + row * row_h + row_h), QPointF(x, mt + plot_h))

    # Explain the largest peak of ``annotate_peak`` (the host chart's CPU):
    # where it sits relative to the event markers.
    peak_pts = series.get(annotate_peak, []) if annotate_peak else []
    if peak_pts:
        tp, vp = max(peak_pts, key=lambda tv: tv[1])
        x, y = X(tp), Y(vp)
        p.setBrush(QColor("#111111"))
        p.setPen(QPen(QColor("#111111"), 2))
        p.drawEllipse(QPointF(x, y), 4, 4)
        p.setBrush(Qt.BrushStyle.NoBrush)
        where = peak_context(tp, markers, peak_pts[0][0])
        note = f"{annotate_peak.split()[0]} peak {vp:.0f}% at {_fmt_t(tp)} s, {where}"
        p.setFont(QFont(family, 8))
        nfm = QFontMetrics(QFont(family, 8))
        nw = nfm.horizontalAdvance(note) + 8
        bx = x + 8 if x + 8 + nw <= W - mr else max(ml + 2, x - 8 - nw)
        box = QRectF(bx, max(mt + 2, y - nfm.height() - 6), nw, nfm.height() + 2)
        p.fillRect(box, QColor("#ffffff"))
        p.setPen(QColor("#111111"))
        p.drawText(box, int(Qt.AlignmentFlag.AlignCenter), note)

    # Marker tags last, on white, above everything else.
    p.setFont(tag_font)
    for _x, left, w, row, n in placed:
        box = QRectF(left, band_top + row * row_h, w, row_h - 1)
        p.fillRect(box, QColor("#ffffff"))
        p.setPen(QPen(QColor("#c62828"), 1))
        p.drawRect(box)
        p.setPen(QColor("#c62828"))
        p.drawText(box, int(Qt.AlignmentFlag.AlignCenter), str(n))

    # Legend: swatch line (in the series' own style) + name + peak.
    p.setFont(legend_font)
    ly0 = mt + plot_h + axis_h
    for i, lx, row in legend:
        name = names[i]
        y = ly0 + row * (lfm.height() + 4) + lfm.height() / 2
        pen = QPen(colors.get(name, QColor("#333333")), 3)
        pen.setStyle(styles.get(name, Qt.PenStyle.SolidLine))
        p.setPen(pen)
        p.drawLine(QPointF(ml + lx, y), QPointF(ml + lx + 20, y))
        p.setPen(QColor("#333333"))
        p.drawText(QPointF(ml + lx + 26, y + lfm.ascent() / 2 - 1), legend_items[i])

    p.end()
    return img


def _event_key_html(events: list) -> str:
    """Key for the numbered event markers on every graph in the report."""
    markers = _event_markers(events)
    if not markers:
        return ""
    rows = "".join(
        f'<tr><td align="center" style="color:#c62828;"><b>{n}</b></td>'
        f'<td nowrap>{_fmt_t(t0)} s' + (f'&ndash;{_fmt_t(t1)} s' if t1 > t0 else '') + '</td>'
        f'<td>{_esc(_summarize_events(labels))}</td></tr>'
        for n, t0, t1, labels in markers)
    return ('<h4 style="color:#222;">Event key (marker numbers on all graphs)</h4>'
            '<table width="100%" cellspacing="0" cellpadding="3" border="1" '
            'style="border-collapse:collapse; color:#444; font-size:9pt;">'
            '<thead><tr><th width="10%" nowrap>Marker</th><th width="17%" nowrap>Elapsed</th>'
            '<th width="73%" align="left">What happened</th></tr></thead>' + rows + '</table>')


# Load levels whose share of the recording the host table reports.
_LEVELS_PCT = (50.0, 80.0)


def _host_stats_html(sys_samples: list) -> str:
    """Host CPU and RAM over the recorded window: mean and SD, the 95th
    percentile and peak, how far the peak sits from normal, and the chance a
    random moment of the window was at or above each load level.

    No confidence interval of the mean here: the window IS the whole run, and
    a single start/stop can't say how the next one would differ."""
    rows = []
    for idx, name in ((1, "Host CPU"), (2, "Host RAM used")):
        vals = [smp[idx] for smp in sys_samples]
        s = st.summarize(vals)
        if s is None:
            continue
        rows.append((f"{name}, mean &plusmn; SD", f"{s.mean:.1f}% &plusmn; {s.sd:.1f}",
                     f"average over {s.n} samples; the SD is the typical swing around it"))
        rows.append((f"{name}, 95th percentile / peak", f"{s.p95:.1f}% / {s.max:.1f}%",
                     "95% of the time usage was at or below the first figure"))
        if s.sd > 0:
            z = (s.max - s.mean) / s.sd
            rows.append((f"{name}, how unusual the peak is", f"{z:.1f} SD above the mean",
                         "more than ~3 SD is a rare spike rather than normal fluctuation"))
        for level in _LEVELS_PCT:
            share = st.exceedance(vals, level)
            rows.append((f"{name}, P(&ge;{level:.0f}%)", st.fmt_pct(share, 1),
                         "chance a random moment of this recording was at least this busy"))
    return st.stats_table_html(rows, "Probability metrics: host")


# Fewer samples than this and a row's statistics describe a moment, not a run.
_FEW_SAMPLES = 10


def _container_stats_html(container_samples: list, svcs: list, mem_limits: dict) -> str:
    """One row per container: how many samples (and over how long) the row
    rests on, mean CPU and SD, 95th percentile and peak CPU, the share of its
    samples above 50% CPU, mean and peak memory. Then a note for containers
    that sat at their memory limit."""
    rows = []
    few = False
    limit_notes = []
    for svc in svcs:
        times = [t for t, snap in container_samples if svc in snap]
        cpu_vals = [snap[svc][0] for _, snap in container_samples
                    if svc in snap and snap[svc][0] is not None]
        mem_vals = [snap[svc][1] / 1048576.0 for _, snap in container_samples if svc in snap]
        cpu = st.summarize(cpu_vals)
        mem = st.summarize(mem_vals)
        if mem is None:
            continue
        mark = ""
        if len(times) < _FEW_SAMPLES:
            mark, few = "*", True
        cpu_cells = (f'<td>{cpu.mean:.1f}% &plusmn; {cpu.sd:.1f}</td>'
                     f'<td>{cpu.p95:.1f}% / {cpu.max:.1f}%</td>'
                     f'<td>{st.fmt_pct(st.exceedance(cpu_vals, 50.0), 1)}</td>'
                     if cpu is not None else '<td>&ndash;</td><td>&ndash;</td><td>&ndash;</td>')
        rows.append(
            '<tr>'
            f'<td nowrap>{_esc(svc)}{mark}</td>'
            f'<td nowrap>{len(times)} / {max(times) - min(times):.1f} s</td>'
            + cpu_cells +
            f'<td>{mem.mean:.0f} &plusmn; {mem.sd:.0f}</td>'
            f'<td>{mem.max:.0f}</td>'
            '</tr>')
        limit = mem_limits.get(svc)
        if limit:
            lim_mib = limit / 1048576.0
            at = sum(1 for v in mem_vals if v >= 0.97 * lim_mib) / len(mem_vals)
            if at >= 0.2:
                limit_notes.append(f'<b>{_esc(svc)}</b> sat at or near its {lim_mib:.0f} MiB memory '
                                   f'limit for {at * 100:.0f}% of its samples')
    if not rows:
        return ""
    notes = []
    if few:
        notes.append(f'* fewer than {_FEW_SAMPLES} samples (the container ran only briefly while '
                     'recorded): its figures describe a moment, not the whole run.')
    if limit_notes:
        notes.append('; '.join(limit_notes) + '. The cgroup memory figure includes the page cache, '
                     'so a database or Elasticsearch filling its limit is normally cached files '
                     '(released under pressure), not a leak.')
    return ('<table width="100%" cellspacing="0" cellpadding="3" border="1" '
            'style="border-collapse:collapse; font-size:8pt; margin-top:4px; color:#333;">'
            '<thead><tr style="background-color:#eef3f8;"><th align="left" colspan="7">'
            'Probability metrics: per container</th></tr>'
            # Explicit widths: Qt ignores nowrap and otherwise squeezed the
            # name column until it broke container names mid-word.
            '<tr><th align="left" width="27%">Container</th><th align="left" width="13%">Samples / over</th>'
            '<th align="left" width="13%">CPU mean &plusmn; SD</th>'
            '<th align="left" width="13%">CPU p95 / peak</th><th align="left" width="10%">P(CPU &ge; 50%)</th>'
            '<th align="left" width="14%">Mem MiB mean &plusmn; SD</th>'
            '<th align="left" width="10%">Mem MiB peak</th></tr></thead>' + "".join(rows) + '</table>'
            '<p style="color:#666; font-size:9pt;">Each row covers only the samples taken while '
            'that container was running (count and the time between its first and last one). '
            'P(CPU &ge; 50%) is the share of those samples at half a core or more, i.e. the chance of '
            'catching it that busy at a random moment of its run. A peak far above the p95 means a '
            'short burst (typically start-up work or a first healthcheck) rather than '
            'sustained load.' + "".join(f' {n}' for n in notes) + '</p>')


def _badges_html(data: ServicesReport) -> str:
    """The error badges a "before" screenshot already shows, and why the
    badge numbers differ from the Warnings counts."""
    if not data.badges_before:
        badge_note = ""
    else:
        listed = ", ".join(f"{_esc(svc)} ({n})" for svc, n in
                           sorted(data.badges_before.items(), key=lambda kv: -kv[1]))
        badge_note = (f'Before the {data.operation} the Global Visualization page already showed '
                      f'red error badges on: {listed}. Those lines were logged before this recording '
                      'and are not counted below. ')
    return ('<p style="color:#555; font-size:9pt;">' + badge_note +
            'A tile\'s red badge counts every log line with an error word ("error", "fail&hellip;", '
            '"fault&hellip;", whatever its level) since the dashboard\'s log tail last started, '
            'including the 50 lines of scrollback it replays, and it keeps counting after the report '
            'ends; the Warnings here count only the lines logged during the recording. So the two '
            'numbers can differ, and a line logged after a screenshot shows up in a later one.</p>')


def _warnings_html(data: ServicesReport) -> str:
    """Near the top, so a start or stop that "succeeded" (compose exit 0,
    health checks green) but had a failing job, a killed container or a
    service logging errors says so in words, not only as a badge in a
    screenshot."""
    during = "start" if data.operation == "start" else "shutdown"
    if not data.warnings:
        failed = ("no container failed or was left unstarted" if data.operation == "start"
                  else "no container exited with an error or had to be killed")
        return (f'<p style="color:#2e7d32;"><b>No warnings:</b> {failed}, and no service logged '
                f'a line with an error word during the {during}.</p>' + _badges_html(data))
    rows = "".join(f'<tr><td nowrap><b>{_esc(svc)}</b></td><td>{_esc(what)}</td></tr>'
                   for svc, what in data.warnings)
    source = ("<i>docker compose ps -a</i> after the start settled and the logs written during it"
              if data.operation == "start" else
              "<i>docker compose ps -a</i> while <i>down</i> ran and the logs streamed during it")
    return ('<h2 style="color:#c62828;">Warnings</h2>'
            f'<p style="color:#555;">Found from {source}, using the same test as the red error '
            'badges on the Global Visualization page. Timestamps inside quoted log lines are the '
            'service\'s own, usually UTC.</p>'
            '<table width="100%" cellspacing="0" cellpadding="4" border="1" '
            'style="border-collapse:collapse; color:#333;"><thead><tr><th align="left">Service</th>'
            '<th align="left">Problem</th></tr></thead>' + rows + '</table>' + _badges_html(data))


def _gap_note(times: list[float], max_gap: float, what: str) -> str:
    gaps = sample_gaps(times, max_gap)
    if not gaps:
        return ""
    a, b = max(gaps, key=lambda g: g[1] - g[0])
    return (f' {what} has {len(gaps)} stretch(es) longer than {max_gap:g} s without a sample '
            f'(the longest {b - a:.1f} s, from {_fmt_t(a)} s to {_fmt_t(b)} s); its lines are '
            'broken there rather than drawn straight across.')


def _chart_sets(members: list[str], cpu_series: dict, mem_series: dict):
    """[(heading suffix, metric, {name: pts})] for one chart group: a CPU and
    a memory chart, each split in two when one or two containers dwarf the
    rest (startup_events.dominant_series), so the others aren't flat lines."""
    out = []
    for metric, series in (("cpu", cpu_series), ("mem", mem_series)):
        peaks = {s: max((v for _t, v in pts), default=0.0) for s, pts in series.items() if pts}
        dom = dominant_series(peaks)
        if dom:
            out.append((", ".join(dom), metric, {s: series[s] for s in members if s in dom}))
            out.append(("the others", metric, {s: series[s] for s in members if s not in dom}))
        else:
            out.append(("", metric, series))
    return out


def render_services_pdf(data: ServicesReport, out_path: str) -> None:
    from PyQt6.QtGui import QPageSize, QPageLayout
    printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(out_path)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    build_services_document(data, QSizeF(printer.pageRect(QPrinter.Unit.DevicePixel).size())).print(printer)


def build_services_document(data: ServicesReport, page_size: QSizeF) -> QTextDocument:
    """The report as a paginated QTextDocument of ``page_size`` pages."""
    family = _report_font_family()
    data.generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    doc = QTextDocument()
    doc.setDefaultFont(QFont(family, 11))
    doc.setPageSize(page_size)
    text_w = int(doc.pageSize().width() - 2 * doc.documentMargin()) - 4

    t_end = max(data.duration_s, max((t for t, _ in data.events), default=0.0), 1.0)
    cmax_gap = _max_gap(data.container_interval_s)
    hmax_gap = _max_gap(data.host_interval_s)
    stop = data.operation == "stop"

    op_word = "start-up" if data.operation == "start" else "shutdown"
    parts: list[str] = [f'<div style="font-family: {_FONT_CSS_STACK};">']
    parts.append(f'<h1 style="color:#222;">Service {op_word} report</h1>')
    parts.append('<table width="100%" style="color:#555;"><tr><td>'
                 f'Target: <b>{_esc(data.target_label)}</b><br/>'
                 f'Recording started (t = 0): {_esc(data.started_at)}<br/>'
                 f'Report generated: {_esc(data.generated_at)}<br/>'
                 f'Operation: <b>{_esc(data.operation)}</b> &nbsp;&middot;&nbsp; '
                 f'Recorded window: {data.duration_s:.0f}s'
                 + (f' &nbsp;&middot;&nbsp; compose exit code: <b>{data.exit_code}</b>'
                    if data.exit_code is not None else '')
                 + '</td></tr></table><hr/>')
    if data.hit_time_cap:
        parts.append('<p style="color:#b35900;"><b>Recording hit its time limit</b> '
                     f'({data.duration_s:.0f}s) before the stack settled, so the charts end '
                     'while containers were still changing state.</p>')
    if data.quiet is False and data.busy_at_end:
        busy = ", ".join(f"{_esc(s)} ({v:.0f}% CPU)" for s, v in data.busy_at_end)
        parts.append('<p style="color:#b35900;"><b>Stopped before the stack went quiet:</b> every '
                     f'container was up, but {QUIET_MAX_EXTRA_S + SETTLE_TAIL_S:.0f}s later {busy} '
                     f'still averaged {QUIET_CPU_PCT:.0f}% CPU or more over the last '
                     f'{QUIET_WINDOW_S:.0f}s, so the charts end while it was still warming up.</p>')
    parts.append(_warnings_html(data))

    if stop:
        what = ('a container stopped or removed (<i>down</i> stops each container, then removes '
                'it)')
    else:
        what = ('a container created, started, going healthy or unhealthy, or a one-shot job '
                'finishing or being removed')
    parts.append('<p style="color:#555;">Resource usage recorded while the stack was '
                 f'{"brought up" if not stop else "taken down"}. Each dashed red vertical line '
                 f'marks an event ({what}), numbered in a band above the graph. Container states '
                 f'come from <i>docker compose ps</i>, checked every ~{STATUS_CHECK_INTERVAL_S:g}s, '
                 'so event times are good to about a second. Events up to '
                 f'{MARKER_WINDOW_S:g}s after the first event of a number share it (in practice, the '
                 'changes seen in one status check); the event key under the host graph lists what '
                 'each number covers, with its time to a tenth of a second. '
                 'The largest host CPU peak is called out with where it falls among the markers. '
                 '<b>Figure 1</b> lists the containers of this stack, grouped as in the '
                 'per-container graphs of section 2.</p>')
    sampling = (f'Host CPU and RAM were read from /proc every {data.host_interval_s:g}s'
                + (f', per-container CPU and memory were {_esc(data.resource_source)}'
                   if data.resource_source else '') + '. ')
    sampling += ('A line is broken wherever no sample was taken for longer than a few sampling '
                 'intervals, rather than drawn straight across, and a &times; marks where a '
                 'container\'s line ends before the window does (it stopped, was removed, or a '
                 'one-shot job exited). A container\'s line starts at its first sample, once it is '
                 'really running.')
    sampling += _gap_note([t for t, _c, _r in data.sys_samples], hmax_gap, "The host series")
    if stop and data.stops_backdated:
        sampling += (' A container\'s stop time is when its cgroup disappeared (its processes '
                     'exited), right after its line ends; <i>ps</i> only notices once Docker has '
                     'also removed it, up to a couple of seconds later.')
    parts.append(f'<p style="color:#555;">{sampling}</p>')
    first = min((t for t, _ in data.events), default=None)
    if data.operation == "start" and first is not None and first >= 3:
        parts.append(f'<p style="color:#555;">No container changed state in the first '
                     f'{first:.0f}s: docker compose was building or checking the locally '
                     'built images first (<i>up --build</i>).</p>')
    if data.no_healthcheck:
        parts.append('<p style="color:#555;">Without a healthcheck, '
                     + ", ".join(_esc(s) for s in data.no_healthcheck)
                     + ' never get a &ldquo;healthy&rdquo; event: &ldquo;started&rdquo; is their '
                     'last state, so a late &ldquo;started&rdquo; marker is that container being '
                     'ready, not a missing event.</p>')
    parts.append(st.SPREAD_GLOSSARY_HTML)

    svcs = sorted({s for _, snap in data.container_samples for s in snap})
    groups = chart_groups(svcs) if svcs else []
    if groups:
        stack = data.target_label
        caption = ("Containers of " + stack + " grouped as in the per-container charts in section 2: "
                   "each box lists exactly the containers those charts plot.")
        if data.project == "edge":
            caption += (" The SIEM (Elasticsearch, Kibana) is a separate stack with its own report; "
                        "here it only receives logs from vector_outbound.")
        elif data.project == "siem":
            caption += (" The ids stack (reverse proxy, eshops, databases, Suricata) is a separate "
                        "target with its own report; it ships its logs here via vector_inbound.")
        parts.append(diagrams.figure_html(
            doc, diagrams.stack_services_diagram(f"Services: {stack}", groups, family),
            "svc-arch", 1, caption, width=text_w))

    # 1. overall system chart
    parts.append('<h2 style="color:#222;">1. Overall system (host)</h2>')
    if data.sys_samples:
        sys_series = {
            "CPU %": [(t, cpu) for t, cpu, _ in data.sys_samples],
            "RAM %": [(t, ram) for t, _, ram in data.sys_samples],
        }
        colors = {"CPU %": QColor(_SYS_CPU_COLOR), "RAM %": QColor(_SYS_RAM_COLOR)}
        img = _ts_chart(sys_series, colors, data.events, "host CPU % / RAM % used",
                        family, t_end, hmax_gap, y_max=100.0, annotate_peak="CPU %", unit="%",
                        legend_names={"CPU %": "host CPU", "RAM %": "host RAM used"})
        vector_figures.add_figure(doc, "svc://sys", img)
        # Every image in a paragraph of its own: right after a heading, Qt
        # otherwise puts the <img> into the heading's block, as a second line
        # that can land on the next page without it.
        parts.append(f'<p><img src="svc://sys" width="{text_w}"/></p>')
        parts.append(_event_key_html(data.events))
        parts.append(_host_stats_html(data.sys_samples))
    else:
        parts.append('<p style="color:#c62828;">Host CPU/RAM was not available on this target.</p>')

    # 2. per-container charts (CPU, memory)
    parts.append('<h2 style="color:#222;">2. Per-container</h2>')
    if data.container_samples:
        cores = (f' This host has {data.cpu_count} cores, so the ceiling is '
                 f'{data.cpu_count * 100}%.' if data.cpu_count else '')
        parts.append('<p style="color:#666666;">Container CPU is in % of one core: 100% is one '
                     'core fully busy, so a multi-threaded container goes above 100%.' + cores +
                     (' Grouped by role, one CPU and one memory chart per group, so every line in a '
                      'chart has a colour of its own; when one or two containers dwarf the rest, '
                      'they get a chart of their own and the others are drawn on their own scale.'
                      if len(groups) > 1 else
                      ' When one or two containers dwarf the rest, they get a chart of their own '
                      'and the others are drawn on their own scale.')
                     + '</p>')
        fig = 0
        for title, members in groups:
            # Fixed categorical order per group (never cycled within one chart),
            # kept across the group's split charts.
            cmap = {s: QColor(_CATEGORICAL[i % len(_CATEGORICAL)]) for i, s in enumerate(members)}
            smap = {s: (Qt.PenStyle.SolidLine if i % len(_CATEGORICAL) < 4 else Qt.PenStyle.DashLine)
                    for i, s in enumerate(members)}
            cpu_series = {s: [(t, snap[s][0]) for t, snap in data.container_samples
                              if s in snap and snap[s][0] is not None] for s in members}
            mem_series = {s: [(t, snap[s][1] / 1048576.0) for t, snap in data.container_samples
                              if s in snap] for s in members}
            if title:
                parts.append(f'<h3 style="color:#222;">{_esc(title)}</h3>')
            prefix = f"{title}: " if title else ""
            for which, metric, series in _chart_sets(members, cpu_series, mem_series):
                label = f"{prefix}container {'CPU %' if metric == 'cpu' else 'memory (MiB)'}"
                if which:
                    label += f", {which}"
                img = _ts_chart(series, cmap, data.events, label, family, t_end, cmax_gap,
                                styles=smap, unit="%" if metric == "cpu" else " MiB")
                vector_figures.add_figure(doc, f"svc://c{fig}", img)
                parts.append(f'<p><img src="svc://c{fig}" width="{text_w}"/></p>')
                fig += 1
        parts.append(_container_stats_html(data.container_samples, svcs, data.mem_limits))
    else:
        parts.append('<p style="color:#666;">No per-container samples were captured.</p>')

    # 3. health page screenshots
    parts.append('<h2 style="color:#222;">3. Global Visualization page as the stack changes state</h2>')
    if data.stage_shots:
        parts.append('<p style="color:#555;">Only this target\'s tiles, drawn from the same '
                     '<i>docker compose ps</i> result the report logged at that moment, so tile '
                     'colours and the event log agree. Badges are explained under Warnings.</p>')
        for i, (caption, path, t) in enumerate(data.stage_shots):
            img = QImage(path)
            if img.isNull():
                continue
            doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl(f"svc://shot{i}"), img)
            when = f" (at {_fmt_t(t)} s)" if t is not None else " (before t = 0)"
            parts.append(f'<h4 style="color:#555;">{_esc(caption)}{when}</h4>')
            # Snapshots are rendered at 2x (HealthDiagram.render_group()): never
            # wider than their natural size, never wider than the text.
            width = min(text_w, img.width() // 2)
            parts.append(f'<p><img src="svc://shot{i}" width="{width}"/></p>')
    else:
        parts.append('<p style="color:#666;">No Health-page screenshots were captured.</p>')

    # Appendix: every event on its own row, with exact times.
    if data.events:
        markers = _event_markers(data.events)
        rows = "".join(
            f'<tr><td align="center">{next(n for n, t0, t1, _l in markers if t0 <= t <= t1)}</td>'
            f'<td nowrap>{_fmt_t(t)} s</td><td>{_esc(lab)}</td></tr>'
            for t, lab in sorted(data.events, key=lambda e: e[0]))
        parts.append('<h2 style="color:#222;">Appendix: event log</h2>'
                     '<p style="color:#555; font-size:9pt;">The events behind the event key, one per '
                     'row.</p>'
                     '<table width="100%" cellspacing="0" cellpadding="3" border="1" '
                     'style="border-collapse:collapse; color:#444; font-size:9pt;">'
                     '<thead><tr><th width="10%" nowrap>Marker</th><th width="17%" nowrap>Elapsed</th>'
                     '<th width="73%" align="left">Event</th></tr></thead>' + rows + '</table>')
    else:
        parts.append('<p style="color:#666;">No container transitions were observed.</p>')

    parts.append('</div>')
    doc.setHtml("<body>" + "".join(parts) + "</body>")
    vector_figures.embed_figures(doc)
    report_pagination.keep_together(doc)
    return doc
