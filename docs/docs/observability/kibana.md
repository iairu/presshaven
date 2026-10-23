# Kibana Dashboards

This page describes the visual dashboards for monitoring honeypot activity.

## Dashboard Registry

The following Honeypot dashboards are managed by `siem/kibana/build_dashboards.py`:

| Dashboard ID | Title | Purpose |
| :--- | :--- | :--- |
| `dashboard-ids-alerts` | Honeypot: IDS Alerts (Suricata) | Real-time IDS alert triage. |
| `dashboard-web-threat-overview` | Honeypot: Web Traffic & Threat Overview | Aggregate web threat posture. |
| `dashboard-threat-decisions` | Honeypot: Threat Decisions & Decay | Decisioning logic and threat decay. |
| `dashboard-session-analysis` | Honeypot: Session Analysis | Session-level attacker behavior. |
| `dashboard-attack-patterns` | Honeypot: Attack Patterns | Pattern-based attack analysis. |
| `dashboard-threat-intel` | Honeypot: Threat Intelligence | Threat intelligence integrations. |

Each dashboard is built via `_dashboard(dash_id, title, description, layout)` and registered as `("dashboard", did, body)` objects in the NDJSON output file `saved_objects/honeypot-dashboards.ndjson`.

## Key Visualizations

- **IDS Alerts Dashboard**: Suricata alerts mapped to risk scores and abuse categories. Displays alerts parsed by `suruicata_rules.extract_alert()` with severity-graded scoring.
- **Web Threat Overview**: Cross-dashboard threat posture summary combining CVE matches, pattern detections, and reputation scores.
- **Threat Decisions**: Decision automation and threat decay visualization — shows `decay_policy.lua` escalation-aware decay and permaflag states.
- **Session Analysis**: Session stitching and attacker lifecycle — displays session anomaly data from `session_rules.analyze_session_anomalies()` and sophistication classifications from `sophistication_analyzer.classify_session()`.
- **Attack Patterns**: Recurring attack patterns — shows WSTG category coverage from `pattern_rules.SUSPICIOUS_PATTERNS` and CVE matches from `vulnerability_rules.detect_vulnerability_pattern()`.
- **Threat Intelligence**: Intel feeds and reputation context — displays AbuseIPDB reportability mapping and threat_ips data from `init.lua` seed entries and runtime Suricata ingestion.

## Pattern Report Timeline

A dedicated pattern report timeline dashboard (`pattern-report-request-timeline-dashboard`) is used in embed mode to capture screenshots of request timelines for specific patterns.

**Capture workflow** (`dashboard/core/kibana_timeline.py`, `dashboard/ui/kibana_timeline_capture.py`):

1. Automates a login process (via autologin script if configured) to access Kibana.
2. Imports the necessary saved objects using the Kibana API.
3. Loads the specific timeline dashboard in **embed mode** for a given time window.
4. Waits for a rendering signal (checking for a "render complete" flag in the visualization) before capturing a screenshot of the panel for the specific pattern.

## Dashboard Management

Honeypot dashboards are managed through a combination of offline generation and live Kibana interactions:

*   **Offline Building**: `siem/kibana/build_dashboards.py` generates dashboard objects and visualizations into a local NDJSON file. Idempotent, can be run offline.
*   **Live Kibana Interaction**: Same script can interact with a live Kibana instance via Saved Objects API (using `KIBANA_URL`, `ELASTIC_USERNAME`, `ELASTIC_PASSWORD` env vars).
*   **Exporting Live Changes**: `siem/kibana/export_dashboards.py` exports live dashboard objects from Kibana to the local NDJSON file. Used after manually editing panels in the live Kibana interface to preserve changes offline.

## Key Artifacts

*   `siem/kibana/build_dashboards.py` — Script for generating and managing dashboard configuration.
*   `siem/kibana/export_dashboards.py` — Script for synchronizing live Kibana state to disk.
*   `dashboard/core/kibana_timeline.py` — Defines the structure and payload for the request timeline visualization.
*   `dashboard/ui/kibana_timeline_capture.py` — Handles the client-side workflow for live dashboard capture.
