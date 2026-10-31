"""Secret hygiene for the ids .env: bulk-generate weak/placeholder secrets,
back up and restore the file, and list settings that are still placeholders.

The generation rules live in ids/scripts/generate_secrets.py (the same script
an operator can run on a host without the dashboard); this module loads it
rather than keeping a second copy. Nothing here returns or logs a secret
value: callers get key names only.
"""
from __future__ import annotations

import importlib.util
import re
import shutil
from functools import lru_cache
from pathlib import Path

from core.docker_ctl import siem_shipping
from core.env_file import EnvFile
from core.paths import EDGE_DIR

GENERATOR = EDGE_DIR / "scripts" / "generate_secrets.py"
BACKUP_GLOB = ".env.bak.*"
_PLACEHOLDER_HOST = re.compile(r"example\.(com|org|net)$|^your[-_]", re.I)


@lru_cache(maxsize=1)
def _generator():
    spec = importlib.util.spec_from_file_location("ids_generate_secrets", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _values(env: EnvFile) -> dict[str, str]:
    return {k: env.get(k) for k in env.keys()}


def _example_values(example: Path) -> dict[str, str]:
    return _values(EnvFile.load(example)) if example.exists() else {}


def secret_plan(env: EnvFile, example: Path) -> dict[str, str]:
    """{key: new value} for every secret in `env` that is missing, a
    placeholder, the .env.example value or too short ("" = clear a
    placeholder external credential). Does not touch `env`."""
    return _generator().plan(_values(env), _example_values(example))


def weak_secrets(env: EnvFile, example: Path) -> list[str]:
    """Names of the secrets secret_plan() would replace (without generating
    the expensive GDPR key just to name it)."""
    gen = _generator()
    cur, ex = _values(env), _example_values(example)
    names = []
    for key, min_len in [*((k, 32) for k in gen.HEX32), *((k, 16) for k in gen.ADMIN),
                         ("GDPR_PRIVATE_KEY", 1000)]:
        v = cur.get(key, "")
        if not v or len(v) < min_len or gen.PLACEHOLDER.search(v) or (ex.get(key) and v == ex[key]):
            names.append(key)
    names += [k for k in gen.EXTERNAL
              if cur.get(k) and (gen.PLACEHOLDER.search(cur[k]) or cur[k] == ex.get(k))]
    return names


def config_warnings(env: EnvFile, example: Path) -> list[str]:
    """Human-readable problems in `env` that would break or weaken a deploy.
    Names keys only, never values."""
    warnings = []
    weak = weak_secrets(env, example)
    if weak:
        warnings.append("Placeholder, missing or weak secrets: " + ", ".join(weak)
                        + " (use \"Generate weak secrets\").")
    elk_on = env.get("ELK_ENABLED", "false").strip().strip("\"'").lower() in {"1", "true", "yes", "on"}
    if elk_on:
        shipping, why = siem_shipping(env)
        if not shipping:
            warnings.append(f"ELK_ENABLED is true but {why}: logs cannot be shipped.")
        es_host = env.get("ELASTICSEARCH_HOST", "").strip().strip("\"'")
        if not es_host or _PLACEHOLDER_HOST.search(es_host):
            warnings.append("ELK_ENABLED is true but ELASTICSEARCH_HOST is a placeholder: "
                            "set it to the SIEM host, or set ELK_ENABLED=false.")
    ex = _example_values(example)
    for key in ("WP_ADMIN_EMAIL", "HONEYPOT_WP_ADMIN_EMAIL"):
        if key not in env.keys():
            continue
        v = env.get(key).strip().strip("\"'")
        if not v or v == ex.get(key) or re.search(r"@example\.(com|org|net)$", v, re.I):
            warnings.append(f"{key} is still a placeholder: set a real address "
                            "(WordPress sends admin and password-reset mail there).")
    return warnings


def backup(env_path: Path) -> Path:
    """Copy env_path to .env.bak.<timestamp> (0600); returns the copy."""
    return _generator().backup(env_path)


def list_backups(env_path: Path) -> list[Path]:
    """Backups next to env_path, newest first."""
    return sorted(env_path.parent.glob(BACKUP_GLOB), key=lambda p: p.name, reverse=True)


def restore(env_path: Path, backup_path: Path) -> Path | None:
    """Put backup_path back as env_path (0600). The current file is backed
    up first, so a restore can itself be undone; returns that backup (None
    if there was no current file)."""
    if backup_path.parent.resolve() != env_path.parent.resolve() or \
            not backup_path.name.startswith(".env.bak."):
        raise ValueError(f"{backup_path} is not a backup of {env_path}")
    previous = backup(env_path) if env_path.exists() else None
    shutil.copy2(backup_path, env_path)
    env_path.chmod(0o600)
    return previous
