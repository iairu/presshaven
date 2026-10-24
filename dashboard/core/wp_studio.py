"""Qt-free logic for the WordPress Studio page.

The Studio page embeds the real WordPress wp-admin panel (pointed at
production) and, on demand, fans an editor's changes out to every honeypot
pool. This module holds the parts of that worth testing without Qt or Docker:

  * which pools a propagation targets (ready pools, with a fixed fallback),
  * the exact `docker compose` command that mirrors production into one pool,
  * the headers/URL the embedded browser uses to stay pinned to production,
  * the human-readable policy (what propagates, what never does) shown in the
    page's info panel.

The propagation itself reuses the honeypot_content_sync service's existing
replication script in its `--once N` single-pool mode, so the dashboard runs
the exact same allow-listed, denylisted sync the periodic loop runs -- there
is no second copy of the "what is safe to copy" policy to drift out of sync.
"""
from __future__ import annotations

from dataclasses import dataclass

# The honeypot_content_sync service mounts the replication script at this path
# (see ids/docker-compose.yml). Running it with `--once N` syncs one pool now.
CONTENT_SYNC_SERVICE = "honeypot_content_sync"
REPLICATE_SCRIPT = "/replicate_content_to_honeypot.sh"

# Headers the embedded admin browser presents so nginx force-routes it to
# production and never diverts a live editing session into a honeypot. The
# auth header carries the edge's INTERNAL_TEST_SECRET; the backend header asks
# for production. Both must be present AND the secret must match server-side,
# so this is fail-closed -- see nginx.conf's studio-passthrough early return
# and router_rules.is_studio_passthrough.
STUDIO_BACKEND_HEADER = "X-Studio-Backend"
STUDIO_BACKEND_VALUE = "production"
INTERNAL_TEST_HEADER = "X-Internal-Test-Auth"

# Pools 1..STATIC_POOLS are declared in docker-compose.yml; mirrors
# core.pool_view.STATIC_POOLS. Used as the fallback target set when Redis
# cannot be reached to enumerate the ready pools.
STATIC_POOLS = 3

# What an editor's changes carry to production AND every pool, and what is
# never copied. Shown verbatim in the page's info panel; kept in step with the
# replication script's allow-list / denylist (SETTINGS_ALLOW / SETTINGS_DENY_RE
# and the scoped content dumps in build_sync_sql).
PROPAGATES = (
    "Pages and posts",
    "WooCommerce products, variations and prices",
    "Product categories, tags and attributes",
    "Media / attachment metadata",
    "Safe site & store settings (address, currency, tax & catalog display, theme customizer)",
)
NEVER_PROPAGATES = (
    "User accounts and passwords",
    "Orders, customers and carts",
    "Payment-gateway & SMTP settings (API keys, secrets, tokens)",
    "WooCommerce API keys and licence keys",
    "Any option whose name matches api / key / secret / token / salt / password / …",
)


@dataclass(frozen=True)
class PropagationStep:
    """One pool to push to, with the label the progress UI shows for it."""
    pool: int
    label: str


def studio_url(host: str) -> str:
    """The production wp-admin URL the embedded browser opens. `host` is the
    edge's public host (no scheme); HTTPS is assumed (self-signed is accepted
    by the browser widget)."""
    host = (host or "").strip().rstrip("/")
    # Tolerate a caller that passes a full URL already.
    if host.startswith("http://") or host.startswith("https://"):
        base = host
    else:
        base = f"https://{host}"
    return f"{base}/wp-admin/"


def studio_headers(secret: str | None) -> dict[str, str]:
    """The headers the embedded browser injects so nginx keeps it on
    production. The backend header is always sent; the auth header only when a
    secret is configured. Without the secret nginx fails closed and the admin
    panel is routed normally (and may be diverted), which the page warns about
    rather than silently sending an empty secret."""
    headers = {STUDIO_BACKEND_HEADER: STUDIO_BACKEND_VALUE}
    secret = (secret or "").strip()
    if secret:
        headers[INTERNAL_TEST_HEADER] = secret
    return headers


def ready_pools(remote, *, timeout: float = 10.0) -> list[int]:
    """The pools a propagation targets: every pool the router reports ready,
    ascending. Falls back to the compose-declared pools 1..STATIC_POOLS when
    Redis cannot be reached or reports none ready, so propagation still targets
    the fixed pools instead of silently doing nothing."""
    pools: list[int] = []
    try:
        from core import redis_inspect
        state = redis_inspect.pool_state(remote, timeout=timeout)
        pools = sorted({int(n) for n in state.get("ready", []) if int(n) >= 1})
    except Exception:
        pools = []
    if not pools:
        pools = list(range(1, STATIC_POOLS + 1))
    return pools


def propagation_steps(pools) -> list[PropagationStep]:
    """One PropagationStep per pool, in the given order."""
    return [PropagationStep(int(p), f"Honeypot pool {int(p)}") for p in pools]


def sync_argv(target, pool: int) -> tuple[list[str], str | None]:
    """(argv, cwd) that mirrors production content + settings into one pool
    immediately, via the same script the periodic sync runs. Built from the
    target's compose plumbing, so it works locally or over SSH and follows the
    active honeypot layer."""
    return target.build(
        "exec", "-T", CONTENT_SYNC_SERVICE,
        "bash", REPLICATE_SCRIPT, "--once", str(int(pool)),
    )
