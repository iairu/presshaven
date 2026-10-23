# Single-Host Dashboard IDs (Edge)

This section lists the Kibana dashboard IDs for the single-host environment.

**All Dashboards (consolidated):**
*   `dashboard-ids-alerts`
*   `dashboard-web-threat-overview`
*   `dashboard-threat-decisions`
*   `dashboard-session-analysis`
*   `dashboard-attack-patterns`
*   `dashboard-threat-intel`

## SIEM Single-Host Context

All dashboards are consolidated under a single SIEM instance. This configuration handles the full lifecycle of the dashboards, relying on the `build_dashboards.py` script for creation and `export_dashboards.py` for distribution/backup.

## Single-Host Notes

*   Simplifies deployment by running honeypot, detection, and SIEM components on one host.
*   Suitable for evaluation, lab environments, and small-scale deployments.
*   May require additional tuning for resource constraints and performance.

## Deployment Architecture

In a single-host deployment, all components (reverse proxy, Nginx Lua pipeline, Suricata, Kibana/Elasticsearch, Redis) run on the same host. The routing pipeline (`pattern_analyzer`, `router`, `pool_router`) diverts suspicious traffic to local honeypot pools, while security events are logged locally and visualized via Kibana on the same host.


## Single-Host Notes

- Simplifies deployment by running honeypot, detection, and SIEM components on one host.
- Suitable for evaluation, lab environments, and small-scale deployments.
- May require additional tuning for resource constraints and performance.