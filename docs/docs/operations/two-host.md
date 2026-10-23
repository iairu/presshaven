# Two-Host Dashboard IDs (Edge)

This section lists the Kibana dashboard IDs split for the two-host environment.

**Alerts & Overview Dashboards:**
*   `dashboard-ids-alerts`
*   `dashboard-web-threat-overview`

**Threat Intelligence & Analysis Dashboards:**
*   `dashboard-threat-decisions`
*   `dashboard-session-analysis`
*   `dashboard-attack-patterns`
*   `dashboard-threat-intel`

## SIEM Two-Host Split

The dashboards are split based on functional domain:

1.  **Operational View:** Focuses on real-time alerts and web traffic overview (`dashboard-ids-alerts`, `dashboard-web-threat-overview`).
2.  **Strategic View:** Focuses on deep threat analysis, decision-making, and intelligence (`dashboard-threat-decisions`, `dashboard-session-analysis`, `dashboard-attack-patterns`, `dashboard-threat-intel`).

## Two-Host Topology Notes

*   **Edge Host**: Typically runs the reverse proxy, honeypot backend, and dashboard/monitoring components. The edge host runs the Nginx Lua pipeline (`pattern_analyzer`, `router`, `pool_router`) and generates security events forwarded to the SIEM.
*   **SIEM Host**: Typically runs Kibana/Elasticsearch and consumes logs from the edge host via Vector.
*   Dashboard IDs are partitioned by functional domain to align with the split responsibilities.

## Deployment Architecture (from `router.lua` and `pool_router.lua`)

The two-host split follows the deception layer design:

1.  **Edge host** receives all client traffic, runs the Nginx Lua routing pipeline, and diverts suspicious requests to local honeypot pool instances.
2.  **Security events** (`SECURITY_EVENT:` JSON in Nginx error log) are shipped by Vector to the SIEM host's Elasticsearch.
3.  **Suricata** on the edge host writes `eve.json` alerts, ingested by `init_worker.lua` into the `threat_intel` shared dict.
4.  **Kibana dashboards** on the SIEM host visualize the forwarded events and Suricata alerts.
