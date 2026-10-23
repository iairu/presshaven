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

## Pattern Report Timeline Dashboard

A dedicated pattern report timeline dashboard (`pattern-report-request-timeline-dashboard`) is used in embed mode to capture screenshots of request timelines for specific patterns.

**Capture workflow** (`dashboard/core/kibana_timeline.py`, `dashboard/ui/kibana_timeline_capture.py`):

1. Automates a login process (via autologin script if configured) to access Kibana.
2. Imports the necessary saved objects using the Kibana API.
3. Loads the specific timeline dashboard in **embed mode** for a given time window.
4. Waits for a rendering signal (checking for a "render complete" flag in the visualization) before capturing a screenshot of the panel for the specific pattern.

## Dashboard Python Module Reference

| Module | Purpose | Key Functions |
| :--- | :--- | :--- |
| `siem/kibana/build_dashboards.py` | Generates dashboard objects and visualizations into NDJSON; can interact with live Kibana via Saved Objects API | `_dashboard()`, dashboard registration as `("dashboard", did, body)` objects |
| `siem/kibana/export_dashboards.py` | Exports live dashboard objects from Kibana to local NDJSON file | Exports by dashboard ID list: `dashboard-ids-alerts`, `dashboard-web-threat-overview`, `dashboard-threat-decisions`, `dashboard-session-analysis`, `dashboard-attack-patterns`, `dashboard-threat-intel` |
| `dashboard/core/kibana_timeline.py` | Defines structure and payload for request timeline visualization | `DASHBOARD_ID = "pattern-report-request-timeline-dashboard"`, `_dashboard_body()`, import-ready NDJSON string generation |
| `dashboard/ui/kibana_timeline_capture.py` | Client-side workflow for live dashboard capture | Autologin, Kibana API import, embed-mode loading, render-complete signal detection, screenshot capture |

## Honest Assessment

**Strengths:**
- Offline generation is idempotent and doesn't require a live Kibana instance.
- Export workflow preserves manual panel edits made in the live Kibana UI.
- Timeline capture enables per-pattern visual evidence collection.

**Limitations & Improvement Opportunities:**
- Dashboard generation and export are separate scripts with potential drift — the `test_kibana_dashboards.py` test exists specifically to catch this.
- The timeline capture workflow depends on Kibana auth setup (autologin scripts) which may be fragile.
- Dashboard layout is defined in Python code, not as editable JSON — changes require code edits and re-generation.
- No automated dashboard health monitoring — stale dashboards require manual re-generation.
- The `pattern-report-request-timeline-dashboard` is a separate, independently-managed artifact that must be imported before the first data capture.

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
