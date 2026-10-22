# Honeypot Layers

The edge stack can deceive attackers at one of **two layers**. Pick it on the
dashboard's Services page ("Honeypot layer"), or with the compose file you pass.

| Layer | Compose file | What gets switched per suspicious session |
|---|---|---|
| **WordPress proxy level** <span class="chip ok">default</span> | `docker-compose.yml` | The whole backend: the proxy routes to separate honeypot WordPress containers (pools). |
| **Database proxy level** | `docker-compose.db-proxy.yml` | Only the database: one `production_eshop` serves everything, and `wp-content/db.php` connects it to the production or a honeypot database per request. |

```bash
docker compose up -d --remove-orphans                                   # WordPress proxy level
docker compose -f docker-compose.db-proxy.yml up -d --remove-orphans    # database proxy level
```

Both layers share the same compose project name, `.env` and data. Switching with
`--remove-orphans` replaces the services that differ and removes the other layer's
extras. The honeypot database volume is the exception: the database layer uses
`honeypot_database_proxy_data`.

## WordPress proxy level (default, recommended)

Suspicious sessions are routed to **separate honeypot WordPress containers** — each a
full WordPress + database pool. This is the high-interaction design the rest of this
knowledge base describes: it can contain file uploads, path traversal and RCE because
the attacker is on a genuinely separate, disposable container.

See [Pool Scaling & Assignment](pooling.md).

## Database proxy level

One `production_eshop` serves everyone; a `wp-content/db.php` drop-in switches it
between the production and a honeypot database per request, keyed by the
`X-Honeypot-DB` header the proxy sets (and always overwrites, so a client can't forge
it). `db.php` accepts only a plain positive integer, mapping it to `honeypot_database_N`.

### What it can't isolate

Because the filesystem and PHP runtime are **shared**, this layer **cannot contain**:

- file uploads,
- path traversal,
- config disclosure,
- RCE.

Those reach the shared filesystem/PHP, not the switched database. In this layer the
dashboard's Patterns page **greys out** those presets. (See `ids/db_proxy/COVERAGE.md`.)

### One honeypot database per user

The honeypot database is a **pool**, just like the WordPress-layer pods:

- `honeypot_database` is pool 1; each new IP is assigned a free ready database
  exclusively (atomic Redis assignment in `pool_router.lua`).
- Every assignment wakes `pool_manager` (`POOL_MODE=database`), which clones another
  database from production, scrubs it, and registers it as the next spare.
  `POOL_SPARES` unowned databases are kept ready; `POOL_MAX` caps the total.
- With no spare ready, the router reuses existing databases round-robin (two users
  then share one).
- `pool_manager` publishes each ready database's container health in
  `honeypot_pool:health`; `lua/init_worker.lua` copies that into the proxy's health
  cache every 5 s and serves a session from another ready database while its own is
  down, moving it back once healthy (the assignment itself never changes).
- All honeypot databases use production's credentials; isolation is the separate
  database **host**.

### Files that belong to this layer

The `ids/db_proxy/` folder holds whole-file replacements at the same relative paths as
the defaults; `docker-compose.db-proxy.yml` bind-mounts each over the shared version
(`nginx.conf` with no pool upstreams, `proxy_params` setting `X-Honeypot-Backend`,
`health_check.lua`/`init_worker.lua` with `POOL_COUNT=0`, the content-replication
script, and a clone-tolerant migration). Two files can't be overlaid (Docker would
create empty placeholders) so they live in the shared tree and do nothing unless
`HONEYPOT_LAYER=database`: `wp-content/db.php` and
`mu-plugins/honeypot-db-backend-header.php`.

!!! tip "When changing a shared original"
    If you edit a shared original like `init_worker.lua`, check whether the
    `db_proxy/` copy needs the same change.
