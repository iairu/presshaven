# Getting Started

New here? This section takes you from a fresh clone to a running honeypot you can
attack and watch.

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **[Installation & Setup](installation.md)**

    ---

    Prerequisites, the two-host run order, first-time `.env` setup, and the one
    host kernel tweak Redis needs.

-   :material-flash:{ .lg .middle } **[First Attack in 5 Minutes](quickstart.md)**

    ---

    Bring the stack up, send a clean request, then a scanner request, and watch the
    routing decision flip.

-   :material-monitor-dashboard:{ .lg .middle } **[The Dashboard](dashboard.md)**

    ---

    The PyQt6 control panel: wizard, Start/Stop, the live health diagram, logs,
    certs, and the Learn tab.

-   :material-console:{ .lg .middle } **[Command Cheat Sheet](commands.md)**

    ---

    Every common `docker compose` and maintenance command in one place.

</div>

## Two ways to run it

1. **The dashboard** (recommended for newcomers) — `cd dashboard && ./run.sh`.
   A GUI wizard sets up both `.env` files, starts/stops each project (local or
   remote over SSH), and shows a live health diagram. See [The Dashboard](dashboard.md).
2. **Plain `docker compose`** — the classic path, documented throughout the
   [Command Cheat Sheet](commands.md) and [Installation](installation.md).

!!! info "The SIEM is optional for local dev"
    The edge stack (`ids/`) runs standalone. You only need the SIEM half (`siem/`)
    if you want shipped logs to land in Elasticsearch/Kibana. See
    [Observability](../observability/index.md).
