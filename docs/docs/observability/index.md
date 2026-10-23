# Observability

This section covers how the honeypot system provides observability into attacker activities.

## Observability Layers

The honeypot system exposes observability through several complementary layers:

- **Log Ingestion**: Structured logs from the reverse proxy, Lua engines, and Suricata are centralized for SIEM consumption via Nginx error logs and Vector forwarding to Elasticsearch/Kibana.
- **SIEM Dashboards**: High-level operational views of IDS alerts, threat overview, and web traffic (managed by `siem/kibana/build_dashboards.py`).
- **Kibana Visualizations**: Interactive dashboards and pattern report timelines (`dashboard/core/kibana_timeline.py`, `dashboard/ui/kibana_timeline_capture.py`).
- **Alerting & Reporting**: AbuseIPDB reporting and reputation-based alerting (`abuseipdb_rules.lua`, `abuseipdb_client.lua`).

## Logging Architecture (from `init.lua`)

### Shared Dictionaries

The four `lua_shared_dict` zones declared in `nginx.conf` and shared across ALL worker processes:

| Dictionary | Size | Purpose |
| :--- | :--- | :--- |
| `sessions` | 10 MB | Worker-local cache of session JSON blobs. Reduces Redis round-trips on hot paths. |
| `threat_intel` | 10 MB | Threat-intelligence data: flagged IPs, flagged user-agents, and backend health-check results. |
| `rate_limit` | 10 MB | Per-IP request-rate counters for botnet detection. |
| `honeypot_routes` | 1 MB | Per-IP pool assignments cached locally for 5 min. |

### Security Event Logging

`_G.utils.log_security_event(event_type, details)` appends structured JSON security events to the Nginx error log. Vector (configured in `vector.yaml` as `nginx_error_in` source) reads these and forwards to Elasticsearch.

**Important implementation detail**: Empty Lua tables are tagged with `cjson.empty_array_mt` so they encode as `[]` rather than `{}`. This prevents Elasticsearch mapping conflicts where the first event's empty field locks the mapping as `object`, silently dropping later events whose same field contains array contents.

Events logged include:
- `cve_pattern_detected` — CVE pattern matched in URI/args/headers
- `high_risk_request` — Score > 70
- `routing_to_honeypot` — Request diverted to honeypot pool
- `session_compromised` — Session marked compromised
- `suspicious_upload` — Suspicious file upload detected
- `honeytoken_used` — Injected honeytoken value detected in inbound request
- `admin_access` — Admin area access attempt

## Suricata Log Ingestion

`suruicata_rules.lua` and `init_worker.lua` handle Suricata `eve.json` log ingestion:

*   `init_worker.lua` runs `parse_suricata_logs()` every 30 seconds.
*   Alerts are extracted via `suruicata_rules.extract_alert()` and written to `threat_intel` shared dict as `threat_ips`.
*   Private IPs (RFC1918/loopback) are filtered at ingestion time via `suruicata_rules.is_private_ip()`.
*   Scores are decayed at read time via `suruicata_rules.decayed_score()` using `score_decay_half_life_seconds`.

<div class="grid cards" markdown>

-   :material-chart-bar:{ .lg .middle } **[SIEM & Log Pipeline](siem.md)**
    
    ---
    
    How logs are processed and analyzed using SIEM tools.

-   :material-chart-areaspline:{ .lg .middle } **[Kibana Dashboards](kibana.md)**
    
    ---
    
    Visual dashboards for monitoring honeypot activity.

</div>
