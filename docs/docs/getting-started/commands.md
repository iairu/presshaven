# Command Cheat Sheet

All commands run from `ids/` unless noted. The [dashboard](dashboard.md) does most of
these through a GUI.

## Lifecycle

```bash
# Start (edge stack)
docker compose up -d --build

# Restart after a minor config/code change
docker compose down && docker compose up -d

# Enable log shipping to the SIEM host (Vector is gated behind a compose profile —
# a plain `up` does NOT start it)
docker compose --profile elk up -d
```

!!! warning "nginx.conf is baked in at build time"
    `reverse_proxy_enhanced/lua/*.lua` is **bind-mounted live**, but historically
    `nginx.conf` was `COPY`'d into the image at build time (now fixed to a live
    bind-mount — see [Known Issues §9.3](../reference/known-issues.md)). On an older
    build, a plain `restart` silently will **not** pick up `nginx.conf` edits — use
    `--build`:

    ```bash
    docker compose up -d --build reverse_proxy
    # or, explicitly:
    docker compose stop reverse_proxy && docker compose build reverse_proxy && docker compose up -d reverse_proxy
    ```

    A Lua *code* change takes effect on reload, but OpenResty caches `require`d Lua
    modules per worker, so force a reload inside the container with `kill -HUP 1`
    (the proxy runs OpenResty as PID 1 with `daemon off`, so `nginx -s reload`
    cannot find a pid file).

## Redis state

```bash
# Flush ALL Redis state (sessions, threat_ips, pool assignments, rate limits)
docker compose exec -T session_store redis-cli \
  -a "$(grep REDIS_PASSWORD .env | cut -d= -f2)" FLUSHALL

# Audit the live keyspace against the documented schema
./scripts/redis_key_audit.sh
```

See [State — Redis & ngx.shared](../engine/state.md) for the full schema.

## Honeypot layer

```bash
docker compose up -d --remove-orphans                                   # WordPress proxy level (default)
docker compose -f docker-compose.db-proxy.yml up -d --remove-orphans    # database proxy level
```

## Demo storefront

```bash
# Reset production + all 3 honeypot pools to a clean seeded state,
# then re-sync pools immediately
FORCE_RESEED=1 docker compose up production_db_seed && docker compose restart honeypot_content_sync
```

See [Seeding the Storefront](../engine/seeding.md).

## Backups

```bash
# List / label / delete / export / import backup_service's backups
./backups/manage_backups.sh list
```

See [Backups](../engine/backups.md).

## Testing

```bash
export INTERNAL_TEST_SECRET=$(grep INTERNAL_TEST_SECRET .env | cut -d= -f2)
./testing/scenario_01_thm_woocommerce.sh

# Live production-hardening checks (XML-RPC, hotlink, versions, backups, caps)
./scripts/hardening_audit.sh
```

```bash
# Lua unit tests (484 across 17 suites, plain Lua 5.1 interpreter)
cd reverse_proxy_enhanced/lua/tests && ./run_all.sh

# Dashboard core tests (Qt-free)
cd dashboard && python3 -m unittest discover -s tests
```

## Full purge (destructive)

!!! danger "This removes **all** containers on the machine"
    ```bash
    docker stop $(docker ps -a -q) ; docker rm -f $(docker ps -a -q) ; docker rmi $(docker images -q)
    docker system prune -a --volumes --force
    docker compose up -d
    ```
    The dashboard's **Purge** button scopes `docker compose down -v` to one project
    and always confirms first — prefer it.

## Suricata

```bash
# Validate rules
docker exec suricata_ids suricata -T -c /etc/suricata/suricata.yaml -S /var/lib/suricata/rules/local.rules

# Hot-reload rules without restarting
docker exec suricata_ids suricatasc -c reload-rules
```

See [Suricata Network IDS](../detection/suricata.md).
