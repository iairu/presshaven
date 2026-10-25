<p align="center">
  <img src="dashboard/resources/app_icon.svg" alt="PressHaven logo" width="96" height="96">
</p>

<h1 align="center">PressHaven <img src="https://img.shields.io/badge/-alpha-00ff41?style=flat-square&labelColor=000000" alt="alpha" align="top"></h1>
<p align="center">
  <strong>Security platform for WordPress and WooCommerce</strong><br>
  <a href="https://presshaven.io">presshaven.io</a> · <a href="https://github.com/presshaven/presshaven">github.com/presshaven/presshaven</a>
</p>
<p align="center">
  <em>Improving Honeypot Tool Efficiency by Increasing Interaction Level</em>
</p>

---

A WordPress/WooCommerce shop behind an OpenResty (Nginx + Lua) reverse proxy that scores every
request in real time and quietly diverts suspicious sessions to isolated honeypot copies of the shop,
while real customers never notice. Suricata watches the network, Redis holds session and routing
state, and logs can ship to a separate SIEM host (Elasticsearch + Kibana) over mTLS.

The system ships as two Docker Compose stacks:

- **`ids/`**: the reverse proxy, shop, honeypot pools, Redis, Suricata and Vector.
- **`siem/`**: Elasticsearch, Kibana and the Vector aggregator.

You can run both on one host or split them across two. The PyQt6 dashboard in `dashboard/` is the
recommended way to configure, deploy and operate either shape. This README follows the
[Getting Started](https://presshaven.io/docs/getting-started) guide on the docs site.

## Choose a path

| Path | What it does |
|---|---|
| **[Dashboard](#dashboard-setup)** (recommended) | Upload the project over SSH, edit `.env`, start and stop stacks, tail logs, open a container shell, run scenarios and export reports. Handles local and remote targets. |
| **[Manual Docker Compose](#manual-setup)** | Copy `.env.example`, set passwords, and bring up the edge stack directly. The SIEM stack is optional and can be added later. |

## Prerequisites

### Docker and system packages

Every host that runs a stack needs Docker with the Compose plugin. The machine that runs the
dashboard also needs `python3` with the `venv` module. For a remote target you also need an SSH key
that can log in, and `rsync` on both machines. The dashboard checks for docker, Compose, ssh and rsync
at startup and shows the matching command below in a banner if one is missing.

| Distribution | Install command |
|---|---|
| Arch / Manjaro | `sudo pacman -S --needed docker docker-compose openssh rsync` |
| Ubuntu / Debian / Mint / Pop!_OS | `sudo apt install docker.io docker-compose-v2 openssh-client rsync` |
| Fedora / RHEL / CentOS / Rocky / Alma | `sudo dnf install docker docker-compose-plugin openssh-clients rsync` |
| openSUSE | `sudo zypper install docker docker-compose openssh rsync` |
| Other | Follow [docs.docker.com/engine/install](https://docs.docker.com/engine/install/). |

The scenario scripts and the commands in this README also use `git`, `curl` and `jq`. Then let your
user run Docker:

```bash
sudo systemctl enable --now docker.service
sudo usermod -aG docker "$USER"    # log out and back in afterwards
docker compose version             # confirms the Compose plugin
```

### Kernel settings

Without the first setting, Redis logs a memory-overcommit warning on every start. Elasticsearch needs
the larger mmap limit on the SIEM host. No container can set these itself, so set them on each host.
The dashboard's host-settings banner checks every host in use, including remote ones over SSH.

```bash
echo 'vm.overcommit_memory = 1' | sudo tee /etc/sysctl.d/99-honeypot.conf
echo 'vm.max_map_count = 262144' | sudo tee -a /etc/sysctl.d/99-honeypot.conf
sudo sysctl --system
```

### Python environment for the dashboard

You normally don't need to do anything here. On its first run, `./run.sh` creates `dashboard/venv/`,
installs PyQt6, and shows a progress window while it installs the rest of `requirements.txt`. To set
the environment up by hand instead (for example on a headless build machine):

```bash
cd dashboard
python3 -m venv venv
./venv/bin/python3 -m pip install -r requirements.txt
```

The dashboard uses PyQt6 WebEngine, which needs the usual Qt/Chromium libraries (on Arch: `nss`,
`alsa-lib`, `mesa`, `libxkbcommon-x11`, `libxcomposite`, `libxdamage`, `libxrandr`, `libxtst`,
`xcb-util-cursor`).

## Dashboard setup

```bash
cd dashboard
./run.sh
```

The first launch creates the venv (see above) and then opens the setup wizard. The wizard's steps are
**Welcome → Remote hosts (optional) → Edge .env → SIEM .env → Certificates (optional) → Done**.

1. **Welcome**: shows a warning if docker, Compose, ssh or rsync is missing.
2. **Remote hosts**: mark `ids` and/or `siem` as remote and enter each one's SSH host, port, user, key
   and remote path. Leave both unticked to run everything on this machine.
3. **Edge .env / SIEM .env**: fill in each project's `.env`. A local file starts from `.env.example`.
   A remote file is fetched over SSH and saved back to the remote. Use *Generate* for the secrets (see
   [the minimum values](#minimum-env-values-to-change)).
4. **Certificates**: *Generate all certificates now* creates the SIEM CA and service certificates and
   the edge nginx certificate. Do this before the first start.

You can run the wizard again from *Connectors & Config → Re-run setup wizard*. It keeps the values
already in the `.env` files. For remote targets, copy the code to the host once from
*Connectors & Config*: run *Test connection*, then *Upload entire project…* (`rsync`, which skips
backups, logs and volumes). After that, *Upload .env to remote…* pushes configuration changes alone.

### First run walkthrough

1. **Clear the banners.** Apply any commands shown in the dependency or host-settings banner above the
   pages.
2. **Start the SIEM, then the edge.** On *Workloads*, start `siem` and then `ids`. The progress bar
   counts one-shot jobs that exit with 0 as up. The first `ids` start seeds the shop and builds the
   initial pools, which takes a few minutes. The Honeypot layer dropdown on this page chooses between
   the two [deception layers](https://presshaven.io/docs/engine/layers); keep the default for a first run.
3. **Check the topology.** On *Global Visualization*, every node should be green (healthy, running or
   exited-ok). A red **!N** badge shows error lines in that container's log.
4. **Check log shipping.** *Log Pipeline* should report that the edge shipper is delivering to the
   SIEM's `vector_inbound`.
5. **Send a clean request, then an attack.** On *Attack Simulation*, browse the shop (it should route
   to production), then pick the CVE-2024-27956 preset and press *Run pattern (curl)*. The Pattern
   analyzer tab shows each signal and the HONEYPOT decision. *Live Events* shows the same decision
   without needing the SIEM.
6. **Follow the session.** *Adversary Sessions* and *Pool State Store* show its score and pool.
   *SIEM Analytics* opens Kibana, logged in automatically, at the Attack Patterns dashboard.
7. **Clean up.** *Unpoison host IP* clears the reputation your own test runs built up for your host,
   so later visits are not diverted.

> [!TIP]
> Press <kbd>F1</kbd> on any page for its guide, or <kbd>Ctrl</kbd>+<kbd>K</kbd> to jump to a page by
> name. The *Knowledge Base* page has eight guided labs that cover the steps above and more. The
> [Dashboard Guide](https://presshaven.io/docs/getting-started/dashboard) describes every page.

## Manual setup

The edge stack is enough for a first run. The shop is published at `https://localhost/` with a
self-signed certificate, so expect a browser warning. The commands below bring up the default
reverse-proxy deception layer (a separate decoy backend per session); see
[Honeypot Layers](https://presshaven.io/docs/engine/layers) for the lighter database-proxy alternative
and how to choose between them.

```bash
cd ids
cp .env.example .env
$EDITOR .env                       # set real passwords first

docker compose up -d --build
docker compose ps
docker compose logs -f reverse_proxy
```

### Minimum .env values to change

| Variable | Purpose |
|---|---|
| `MYSQL_ROOT_PASSWORD` | Root password for the production and honeypot databases. |
| `MYSQL_PASSWORD` | Application user password for the production database. |
| `MYSQL_PASSWORD_POOL_2`, `MYSQL_PASSWORD_POOL_3` | Per-pool database passwords. They must differ from the production password and from each other; pool isolation depends on this. |
| `REDIS_PASSWORD` | Password for the Redis session store. |
| `SESSION_SIGNING_KEY` | HMAC key for the signed `SERVERID` session cookie. |
| `INTERNAL_TEST_SECRET` | Gates the diagnostic `X-Route-Target` and `X-Risk-Score` headers. Leave unset in production so they fail closed. |

> [!WARNING]
> Never commit a filled `.env`. The uploaded copy on a remote host contains database, Redis and
> signing credentials, so restrict its permissions and rotate values if a host is rebuilt or shared.

### Optional SIEM stack

```bash
cd siem/certs/root-ca && ./gen_elk_certs.sh
cd ../../docker
cp .env.example .env
docker compose up -d
```

Running both stacks on one host is supported for evaluation. The
[two-host](https://presshaven.io/docs/operations/two-host) and
[single-host](https://presshaven.io/docs/operations/single-host) pages describe the differences, and
[SIEM & log pipeline](https://presshaven.io/docs/observability/siem) covers the data path.

## Verify the stack

Work outward from the containers to the detection pipeline:

1. **Containers are healthy.** `docker compose ps` should show the proxy, production shop, pool
   manager, Redis, Suricata, Vector and the database services running. The first start also seeds the
   shop and builds the initial pools, which takes a few minutes.
2. **The shop responds.** Open `https://localhost/` and browse a product. A clean request should stay
   on production.
3. **A scenario is detected.** Run one of the scenario scripts, for example
   `bash testing/scenario_02_owasp_wstg.sh` from `ids/`. With the internal test secret configured, the
   response headers show the route and risk score.
4. **A pool was assigned.** Inspect Redis for the session and pool keys, or use the dashboard's Pool
   State Store, Adversary Sessions and Pool Scaling pages.
5. **Events reached the SIEM.** With the SIEM stack running, refresh the Kibana dashboards. Security
   events arrive through Vector; Suricata alerts arrive through `eve.json` ingestion.

> [!TIP]
> Set `INTERNAL_TEST_SECRET` and send a matching `X-Internal-Test-Auth` header to receive
> `X-Route-Target` and `X-Risk-Score`. Without the secret, the headers are never emitted, so a blind
> pentest does not get the routing oracle for free.

## Command cheat sheet

Run from the repository root:

| Task | Command |
|---|---|
| Start the edge stack | `cd ids && docker compose up -d` |
| Rebuild after changes | `cd ids && docker compose up -d --build` |
| Follow proxy logs | `cd ids && docker compose logs -f reverse_proxy` |
| Open a Redis shell | `cd ids && docker compose exec session_store redis-cli -a "$(grep ^REDIS_PASSWORD= .env \| cut -d= -f2-)" --no-auth-warning` |
| Run all scenarios | `cd ids && bash testing/run_all_scenarios.sh` |
| Run Lua unit tests | `ids/reverse_proxy_enhanced/lua/tests/run_all.sh` |
| Run dashboard tests | `cd dashboard && python3 -m unittest discover -s tests -v` |
| Regenerate Kibana objects | `python3 siem/kibana/build_dashboards.py --ndjson` |
| Export live dashboards | `python3 siem/kibana/export_dashboards.py` |

## How it works, in short

Every request is scored in Lua (patterns, CVE signatures, rate, session history, IP reputation, with
decay over time). Sessions are identified by a signed cookie with a fingerprint fallback, not by IP.
Past a threshold a session is bound to its own honeypot pool and stays there, and shopping carts
follow it, so the diversion is invisible. The honeypot can sit at the proxy layer (separate shop
containers, default) or at the database layer (one shop, two databases).

## Repository layout

```
ids/          honeypot stack: proxy + Lua scoring, shop, pools, Redis, Suricata, Vector, tests
siem/         SIEM stack (Elasticsearch, Kibana, Vector aggregator); runs on its own host
dashboard/    PyQt6 control, management and test dashboard
docs-astro/   source of the documentation site at presshaven.io
patterns/     attack pattern catalogue shared by the dashboard and the docs
ARCHITECTURE.md   the two-host split and data flow
```

## Where to go next

| Resource | Contents |
|---|---|
| [Documentation site](https://presshaven.io/docs) | Architecture, honeypot engine, detection, observability, operations, testing and reference |
| [Dashboard Guide](https://presshaven.io/docs/getting-started/dashboard) | Every dashboard page, its shortcuts, remote targets and troubleshooting |
| [Architecture](https://presshaven.io/docs/architecture) | The request pipeline and the pure/adapter split, worth reading before changing detection code |
| [Detection](https://presshaven.io/docs/detection) | How scores are accumulated, capped and decayed, and which stages can force a route |
| [Runbooks](https://presshaven.io/docs/operations/runbooks) | Troubleshooting procedures to keep open while running your first scenarios |
| [`dashboard/README.md`](dashboard/README.md) | Dashboard pages, remote targets, settings and state |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Why `ids/` and `siem/` are separate hosts, data flow, single-host testing |
| [`siem/README.md`](siem/README.md) | SIEM stack setup and the committed Kibana dashboards |
| [`ids/eshop_seed/README.md`](ids/eshop_seed/README.md) | The Fernhill demo store's catalog, images and seeding |
| [`ids/db_proxy/README.md`](ids/db_proxy/README.md) | Files used only by the database-proxy honeypot layer |
| [`ids/testing/`](ids/testing) | Attack scenarios and the blind-pentest protocol |

The primary literature is listed on the [Literature](https://presshaven.io/docs/reference/literature)
page.

## License

Copyright (C) 2025–2026 Ondrej Špánik

PressHaven is free software: you can redistribute it and/or modify it under the terms of the
[GNU General Public License](LICENSE) as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version. This matches the licensing of the software it
is built on: WordPress (GPLv2 or later) and WooCommerce (GPLv3). PressHaven is distributed WITHOUT ANY
WARRANTY; see the license for details.

The bundled WordPress core, WooCommerce, themes and plugins in `ids/production_eshop_files/` keep
their own licenses and copyright notices (see each component's `license.txt` / `readme.txt`).
