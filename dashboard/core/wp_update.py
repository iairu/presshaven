"""Qt-free logic for the WordPress Update page.

The Update page checks whether a newer WordPress core / WooCommerce is
available and, when the operator asks, upgrades every instance behind a
site-wide maintenance page. This module holds the parts worth testing without
Qt or Docker:

  * parsing the `--check` JSON the update script prints,
  * the exact `docker compose run` commands for each stage of an update,
  * which pools get a database migration,
  * the ordered update plan and the human-readable policy/downtime copy the
    page shows.

UPDATE MODEL (confirmed with the operator -- "update production, re-sync to
pools"):

  1. Maintenance ON  -- a Redis flag the edge turns into a 503 page for all
     traffic (see core.redis_inspect.set_maintenance + lua/maintenance.lua).
  2. Update PRODUCTION -- download newest core + WooCommerce files into
     production_eshop_files/ and migrate production's database
     (update_wordpress.sh --apply via the production_db_seed service).
  3. Re-sync FILES to pools -- re-run init_setup, whose rsync mirrors the
     updated production files into every pool volume.
  4. Migrate each static pool's DATABASE -- update_wordpress.sh --apply-db-only
     via honeypot_db_seed_1/2/3 (files are already in place from step 3).
  5. Maintenance OFF.

ARCHITECTURE LIMITATION (surfaced in the page copy): only the static pools
1..STATIC_POOLS have a dedicated wp-cli seed service, so only they get an
in-place DB migration here. Dynamic pools (N > STATIC_POOLS) are built on
demand by pool_manager, which rsyncs production's (now-updated) files and
clones a freshly-migrated database at build time -- so they inherit the new
version automatically on their next rebuild rather than being migrated live.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

# Mounted into every wp-cli seed service (see ids/docker-compose.yml).
UPDATE_SCRIPT = "/update_wordpress.sh"

# The one-shot wp-cli services the update runs through. Each already has the
# right /var/www/html mount + WORDPRESS_DB_* env for its instance.
PRODUCTION_SEED_SERVICE = "production_db_seed"
INIT_SETUP_SERVICE = "init_setup"

# Static pools 1..STATIC_POOLS each have a honeypot_db_seed_<n> service; these
# are the pools whose database this page migrates in place. Mirrors
# core.wp_studio.STATIC_POOLS / docker-compose.yml.
STATIC_POOLS = 3

# How long the maintenance flag is allowed to stay on. It is the fail-safe
# cap: if the dashboard dies mid-update the Redis key expires after this and
# the site self-recovers. Sized well above a realistic update (core +
# WooCommerce download, four DB migrations, a file rsync) so a slow-but-healthy
# run is never cut short, yet short enough that a wedged run doesn't strand the
# site offline for long.
MAINTENANCE_TTL = 1800  # 30 minutes

# The edge mirrors the Redis maintenance flag into its shared dict on a 5s
# timer (init_worker.lua), so the page waits at least this long after turning
# maintenance on before touching production -- otherwise the first requests of
# the update window could still slip through to a half-upgraded store.
MAINTENANCE_GRACE_S = 7

# Shown in the page's info panel.
DOWNTIME_NOTICE = (
    "While the update runs, every visitor -- production and honeypot alike -- "
    "sees a “scheduled maintenance” page instead of the store. Expect "
    "a few minutes of downtime: the new core and WooCommerce are downloaded "
    "once into production, then mirrored to the pools, and each database is "
    "migrated. The site comes back automatically when the update finishes (and "
    "on its own if the update is interrupted, via the maintenance flag's TTL)."
)

WHAT_UPDATES = (
    "WordPress core (files + database schema) on production and pools 1–%d" % STATIC_POOLS,
    "WooCommerce plugin (files + database schema) on the same instances",
    "Updated files are rsynced from production to every pool volume",
)

POOL_LIMITATION = (
    "Dynamic pools (beyond pool %d) are rebuilt on demand from production, so "
    "they pick up the new version automatically the next time they are built "
    "— they are not migrated live here." % STATIC_POOLS
)

# The db-proxy layer's wp-content/db.php drop-in is what binds each request to
# the production or honeypot database; it must survive the upgrade. The update
# script snapshots and restores it around the core/plugin file update (see
# ids/scripts/update_wordpress.sh PRESERVE_FILES), so an upgrade can never drop
# the router. Shown so the operator knows the two-database routing is kept.
DROPIN_NOTE = (
    "The database-router drop-in (wp-content/db.php) is snapshotted before the "
    "upgrade and restored byte-for-byte afterwards, so the production/honeypot "
    "database routing is always preserved."
)


@dataclass(frozen=True)
class ComponentStatus:
    """Installed vs. latest for one component (WordPress or WooCommerce)."""
    name: str
    installed: str
    latest: str
    update_available: bool


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    wordpress: ComponentStatus | None = None
    woocommerce: ComponentStatus | None = None
    errors: tuple[str, ...] = ()
    error: str | None = None  # set when ok is False (e.g. not installed)

    @property
    def any_update_available(self) -> bool:
        return bool(
            (self.wordpress and self.wordpress.update_available)
            or (self.woocommerce and self.woocommerce.update_available)
        )

    @property
    def components(self) -> tuple[ComponentStatus, ...]:
        return tuple(c for c in (self.wordpress, self.woocommerce) if c is not None)


def _extract_json(stdout: str) -> dict:
    """The update script prints one JSON object to stdout (diagnostics go to
    stderr), but be defensive: scan lines for the last one that parses as a
    JSON object, so a stray banner never breaks parsing."""
    text = (stdout or "").strip()
    if not text:
        raise ValueError("empty --check output")
    # Fast path: the whole thing is the JSON object.
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    return obj
            except (json.JSONDecodeError, ValueError):
                continue
    raise ValueError("no JSON object found in --check output")


def _component(name: str, blob) -> ComponentStatus | None:
    if not isinstance(blob, dict):
        return None
    installed = str(blob.get("installed", "") or "")
    latest = str(blob.get("latest", "") or installed)
    avail = bool(blob.get("update_available", False))
    return ComponentStatus(name=name, installed=installed, latest=latest, update_available=avail)


def parse_check(stdout: str) -> CheckResult:
    """Parse the update script's `--check` JSON into a CheckResult. Raises
    ValueError if stdout holds no parseable JSON object (the caller surfaces
    that as an error)."""
    obj = _extract_json(stdout)
    if not obj.get("ok", False):
        return CheckResult(ok=False, error=str(obj.get("error") or "check failed"))
    errors_raw = obj.get("errors", "")
    errors = tuple(e for e in str(errors_raw).split(";") if e) if errors_raw else ()
    return CheckResult(
        ok=True,
        wordpress=_component("WordPress", obj.get("wordpress")),
        woocommerce=_component("WooCommerce", obj.get("woocommerce")),
        errors=errors,
    )


# --- docker compose command builders --------------------------------------
#
# All run through `docker compose run --rm --no-deps <service> ...`:
#   * run (not exec): the seed services are one-shot (they exit after seeding),
#     so there is no running container to exec into -- run starts a fresh one.
#   * --rm: don't leave the throwaway container around afterwards.
#   * --no-deps: do NOT start the service's depends_on chain (db, migration,
#     init_setup). Those are already up when the stack is running; starting
#     them again would be wrong and slow. (init_setup itself is run WITHOUT
#     --no-deps-relevant deps -- it has none -- so its builder omits it for
#     clarity below.)

def check_argv(target, service: str = PRODUCTION_SEED_SERVICE) -> tuple[list[str], str | None]:
    """(argv, cwd) that prints the --check JSON for `service`'s instance.
    Defaults to production; pass a honeypot_db_seed_<n> to check a pool."""
    return target.build("run", "--rm", "--no-deps", service, "sh", UPDATE_SCRIPT, "--check")


def apply_production_argv(target) -> tuple[list[str], str | None]:
    """(argv, cwd) that downloads + installs the newest core/WooCommerce into
    production and migrates production's database."""
    return target.build(
        "run", "--rm", "--no-deps", PRODUCTION_SEED_SERVICE, "sh", UPDATE_SCRIPT, "--apply",
    )


def resync_files_argv(target) -> tuple[list[str], str | None]:
    """(argv, cwd) that re-runs init_setup, whose rsync mirrors the updated
    production files into every pool volume. init_setup has no depends_on and
    its DB-copy / cert-gen steps are no-ops once provisioned, so this is a
    safe, idempotent file re-sync."""
    return target.build("run", "--rm", "--no-deps", INIT_SETUP_SERVICE)


def pool_seed_service(pool: int) -> str:
    """The wp-cli seed service name for a static pool."""
    return f"honeypot_db_seed_{int(pool)}"


def pool_db_update_argv(target, pool: int) -> tuple[list[str], str | None]:
    """(argv, cwd) that migrates one static pool's database (files already
    rsynced). Only valid for pools 1..STATIC_POOLS."""
    return target.build(
        "run", "--rm", "--no-deps", pool_seed_service(pool),
        "sh", UPDATE_SCRIPT, "--apply-db-only",
    )


def updatable_pools() -> list[int]:
    """Static pools whose database this page migrates in place."""
    return list(range(1, STATIC_POOLS + 1))


@dataclass(frozen=True)
class UpdateStep:
    """One stage of the staged progress UI, with a coarse weight used only to
    apportion the progress bar (production download dominates wall time)."""
    key: str
    label: str
    weight: float = 1.0


def update_steps(pools: list[int] | None = None) -> list[UpdateStep]:
    """The ordered update plan the page runs and shows progress for. `pools` is
    the static pools to migrate (defaults to updatable_pools())."""
    if pools is None:
        pools = updatable_pools()
    steps = [
        UpdateStep("maintenance_on", "Enabling maintenance page", 0.5),
        UpdateStep("production", "Updating production (WordPress core + WooCommerce)", 4.0),
        UpdateStep("resync", "Re-syncing updated files to honeypot pools", 2.0),
    ]
    for p in pools:
        steps.append(UpdateStep(f"pool_{p}", f"Migrating honeypot pool {p} database", 1.0))
    steps.append(UpdateStep("maintenance_off", "Disabling maintenance page", 0.5))
    return steps
