"""Host (kernel) settings the stacks need but cannot set themselves.

Some settings are not namespaced per container, so docker compose's
`sysctls:` can't set them: they have to be changed on the machine that runs
the stack (this one, or a remote server). Every setting here has been seen to
matter on a real deployment:

  vm.overcommit_memory = 1   edge stack, session_store (Redis). Without it
                             Redis warns at start that a background save may
                             fail; a failed save makes Redis refuse writes
                             (sessions, threat state, the pool registry).
  vm.max_map_count >= 262144 SIEM stack, es01 (Elasticsearch). Its index files
                             are memory-mapped; below this it can fail to
                             start or fail under load.

read_values() reads them from a target (locally or over SSH), problems()
compares them with what the target's project needs and says how to fix it.
Qt-free; ui/host_settings_banner.py shows the result.
"""
from __future__ import annotations

from dataclasses import dataclass

# File in /etc/sysctl.d/ the fix commands write, so it survives a reboot
# (read by systemd-sysctl at boot; WSL2 too when systemd is enabled).
SYSCTL_FILE = "/etc/sysctl.d/99-honeypot-ids.conf"


@dataclass(frozen=True)
class HostSetting:
    key: str                  # sysctl name, e.g. "vm.overcommit_memory"
    projects: tuple[str, ...]  # which stacks need it ("edge", "siem")
    minimum: int              # required value (or lower bound when at_least)
    at_least: bool            # True: value >= minimum; False: value == minimum
    why: str

    @property
    def proc_path(self) -> str:
        return "/proc/sys/" + self.key.replace(".", "/")

    def ok(self, value: int) -> bool:
        return value >= self.minimum if self.at_least else value == self.minimum

    def wanted(self) -> str:
        return f">= {self.minimum}" if self.at_least else f"= {self.minimum}"


SETTINGS = (
    HostSetting("vm.overcommit_memory", ("edge",), 1, False,
                "Redis (session_store) needs it: without it a background save can fail, "
                "and Redis then refuses writes (sessions, threat state, pool registry)."),
    HostSetting("vm.max_map_count", ("siem",), 262144, True,
                "Elasticsearch (es01) memory-maps its index files; below this it can fail "
                "to start or fail under load."),
)


@dataclass
class Problem:
    setting: HostSetting
    value: int | None         # None: could not be read

    def text(self) -> str:
        now = "unreadable" if self.value is None else str(self.value)
        return f"{self.setting.key} is {now}, needs {self.setting.wanted()}. {self.setting.why}"


def read_command() -> str:
    """One shell line printing `<key>=<value>` per setting (works over SSH)."""
    return "; ".join(f"echo {s.key}=$(cat {s.proc_path} 2>/dev/null)" for s in SETTINGS)


def parse_values(output: str) -> dict[str, int | None]:
    out: dict[str, int | None] = {s.key: None for s in SETTINGS}
    for line in output.splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key in out:
            value = value.strip()
            out[key] = int(value) if value.lstrip("-").isdigit() else None
    return out


def problems(project: str, values: dict[str, int | None]) -> list[Problem]:
    """The settings `project` needs that are missing or wrong in `values`."""
    out = []
    for s in SETTINGS:
        if project not in s.projects:
            continue
        v = values.get(s.key)
        if v is None or not s.ok(v):
            out.append(Problem(s, v))
    return out


def fix_commands(found: list[Problem]) -> str:
    """Shell lines that fix `found` now and keep it fixed after a reboot."""
    if not found:
        return ""
    target = {}
    for p in found:
        s = p.setting
        target[s.key] = s.minimum if not s.at_least else max(s.minimum, p.value or 0)
    lines = [f"sudo sysctl -w {k}={v}" for k, v in target.items()]
    body = "\\n".join(f"{k} = {v}" for k, v in target.items())
    lines.append(f"printf '{body}\\n' | sudo tee -a {SYSCTL_FILE} >/dev/null")
    return "\n".join(lines)


def read_values(target, timeout: float = 10.0) -> dict[str, int | None] | None:
    """The settings as `target` (core.docker_ctl.Target) sees them, or None
    when the host can't be reached."""
    import subprocess
    argv, cwd = target.build_shell(read_command())
    try:
        res = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if res.returncode != 0:
        return None
    return parse_values(res.stdout)


def target_problems(target, timeout: float = 10.0) -> list[Problem] | None:
    """problems() for one target, or None when its host can't be reached."""
    values = read_values(target, timeout=timeout)
    return None if values is None else problems(target.project, values)
