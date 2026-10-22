# Installation & Setup

## Prerequisites

- **Docker** and the **Docker Compose** plugin.
- A Linux host. The project is developed on Arch Linux / WSL2 and deployed on
  Debian/Ubuntu VMs; any host with a modern Docker works.
- For the dashboard: **Python 3** (it builds its own virtualenv on first run).
- Helpful CLI tools: `curl`, `wget`, `zip`, `unzip`, `git`, `jq`.

=== "Debian / Ubuntu"

    ```bash
    sudo apt install docker docker-compose curl wget zip unzip git jq
    ```

=== "Arch Linux"

    ```bash
    sudo pacman -S docker docker-compose curl wget zip unzip git jq
    ```

!!! warning "Host prerequisite: memory overcommit for Redis"
    `session_store` (Redis) logs `WARNING Memory overcommit must be enabled!` on
    every fresh host. `vm.overcommit_memory` is a host-wide kernel parameter —
    Linux does not namespace it, so a container cannot set it for itself. Apply it
    **once per host**:

    ```bash
    sudo sysctl vm.overcommit_memory=1                               # effective now
    echo 'vm.overcommit_memory = 1' | sudo tee -a /etc/sysctl.conf   # persists
    ```

    See [Known Issues §9.4](../reference/known-issues.md) for why.

---

## Two-host run order

The system spans **two separate hosts/VMs**, each its own independent
`docker-compose.yml` project (`ids/` and `siem/`) with no shared files or
networks. See [the two-host split](../architecture/two-host-split.md) for *why*.

```bash
# 1. On the SIEM VM first:
cd siem/certs/root-ca && ./gen_elk_certs.sh && cd ../../docker
cp .env.example .env && vi .env   # set real passwords; .env is gitignored
sudo docker compose up
# wait for http://<siem-vm-ip>:5601/app/home#/ to be reachable

# 2. Then on the main/edge VM:
cd ids
sudo docker compose up
```

The full two-host procedure (certificate copy, `VECTOR_HOST`, SANs) is on the
[Running on Two Hosts](../operations/two-host.md) page. To run **both halves on
one machine** for testing, see [Single-Host Testing](../operations/single-host.md).

---

## First-time setup (edge / local dev)

```bash
cd ids
cp .env.example .env
vi .env    # set real passwords, or generate them:
sed -i "s/change_this_user_password_in_production/$(openssl rand -base64 32)/" .env
sed -i "s/change_this_redis_password_in_production/$(openssl rand -base64 32)/" .env
sed -i "s/change_this_internal_test_secret/$(openssl rand -hex 24)/" .env

docker compose up -d --build
```

!!! danger "`.env` holds real secrets"
    `.env` files are gitignored and contain real passwords. Never commit or print
    them. The dashboard's export bundle also contains plaintext secrets — store it
    securely.

!!! note "No `deploy.sh` / `test_system.sh`"
    Despite references in long-removed docs, there is **no** `deploy.sh`,
    `test_system.sh`, or `test_sql_routing.sh` in this repository. Use
    `docker compose` directly.

---

## Access points (local dev)

| URL / stream | What it is |
|---|---|
| `https://localhost/` | The main site, with intelligent production ↔ honeypot routing (self-signed cert, auto-generated on `init_setup`). |
| `X-Route-Target` response header | The routing decision — **only** returned when the request carries a matching `X-Internal-Test-Auth` header (see [Testing](../testing/index.md)); it used to leak to every client until it was fixed. |
| `docker compose logs -f reverse_proxy` | The single most useful log stream: every request logs its risk score, routing decision and triggering stage. |
| `tail -f ids/suricata_logs/fast.log` / `eve.json` | Suricata IDS alerts. |

---

## Choosing the honeypot layer

The edge stack can deceive attackers at one of two layers — pick it on the
dashboard's Services page, or by the compose file you bring up:

```bash
docker compose up -d --remove-orphans                                   # WordPress proxy level (default)
docker compose -f docker-compose.db-proxy.yml up -d --remove-orphans    # database proxy level
```

See [Honeypot Layers](../engine/layers.md) for the trade-offs.

---

## Where things live

```text
ids/
├── reverse_proxy_enhanced/lua/   # the thesis contribution — the detection pipeline
├── reverse_proxy_enhanced/nginx.conf
├── production_eshop_files/       # real WordPress + WooCommerce + omega-storefront theme
├── eshop_seed/                   # the Fernhill Coffee Roasters demo store generator
├── testing/                      # scenario_01-09.sh + BLIND_PENTEST_PROTOCOL.md
├── docker-compose.yml            # 18 services (see Architecture)
├── suricata_config/, suricata_rules/, suricata_logs/
├── vector/                       # local log shipper (Vector, mTLS out to SIEM)
├── scripts/                      # audits, seeding, replication, backups
├── ssl_certificates/             # gitignored; regenerate on fresh clone
└── .env / .env.example

siem/          # SEPARATE compose project — SIEM backend, own host
dashboard/     # PyQt6 GUI control panel for both projects (local + remote)
ARCHITECTURE.md
docs/          # this knowledge base
```

Next: [fire your first attack](quickstart.md).
