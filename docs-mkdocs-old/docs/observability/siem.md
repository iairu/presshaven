# Observability / SIEM Dashboards

This document outlines the mechanisms for managing, building, and accessing Honeypot dashboards within the observability/SIEM system.

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

## Dashboard Management

Honeypot dashboards are managed through a combination of offline generation and live Kibana interactions.

### 1. Dashboard Building and Export

*   **Offline Building**: The `siem/kibana/build_dashboards.py` script is used to generate the dashboard objects and visualizations into a local NDJSON file (`saved_objects/honeypot-dashboards.ndjson`). This process is idempotent and can be run offline.
*   **Live Kibana Interaction**: The same script can interact with a live Kibana instance via its Saved Objects API (using environment variables like `KIBANA_URL`, `ELASTIC_USERNAME`, `ELASTIC_PASSWORD`) to create or overwrite objects in real-time.
*   **Exporting Live Changes**: The `siem/kibana/export_dashboards.py` script allows for exporting live dashboard objects from Kibana to the local `saved_objects/honeypot-dashboards.ndjson` file. This is primarily used after manually editing a panel in the live Kibana interface to preserve those changes offline.

### 2. Timeline Visualization

A key component is the pattern report time-series panel, which visualizes requests captured by the reverse proxy:
*   **Data Source**: This panel relies on data created by the dashboard objects managed by `siem/kibana/build_dashboards.py`.
*   **Architecture**: This visualization is designed to exist independently of the main Honeypot dashboards. It is imported by the main dashboard application on the SIEM Analytics page before the first data capture.
*   **Real-time Capture**: The client-side component (`dashboard/ui/kibana_timeline_capture.py`) handles the capture process:
    *   It automates a login process (via an autologin script if configured) to access Kibana.
    *   It imports the necessary saved objects using the Kibana API.
    *   It loads the specific timeline dashboard in **embed mode** for a given time window.
    *   It waits for a rendering signal (checking for a "render complete" flag in the visualization) before capturing a screenshot of the panel for the specific pattern.

## Data Flow Architecture

```
Client Request
    ↓
Nginx access_by_lua_block
    ↓
pattern_analyzer.analyze_request()  →  security events → Nginx error log → Vector → Elasticsearch
    ↓
router.decide_route()  →  routing decision → honeypot pool or production
    ↓
session_handler.update_session()  →  Redis session_store
    ↓
Suricata eve.json → init_worker.lua parse_suricata_logs() → threat_intel shared dict → pattern_analyzer.check_ip_reputation()
    ↓
abuseipdb_client.report_ip_async()  →  AbuseIPDB (for reportable reasons)
```

## Vector Configuration

Vector (`vector.yaml`) is configured with `nginx_error_in` source to read Nginx error logs containing `SECURITY_EVENT:` JSON entries. These are forwarded to Elasticsearch for Kibana visualization. The pipeline works around the Docker labels mapping-conflict bug by tagging empty-table values to encode as `[]` at the source in `_G.utils.log_security_event()`.

## Key Artifacts

*   **`siem/kibana/build_dashboards.py`**: Script for generating and managing dashboard configuration.
*   **`siem/kibana/export_dashboards.py`**: Script for synchronizing live Kibana state to disk.
*   **`dashboard/core/kibana_timeline.py`**: Defines the structure and payload for the request timeline visualization.
*   **`dashboard/ui/kibana_timeline_capture.py`**: Handles the client-side workflow for live dashboard capture.
