# Observability / SIEM Dashboards

This document outlines the mechanisms for managing, building, and accessing Honeypot dashboards within the observability/SIEM system.

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

## Key Artifacts

*   **`siem/kibana/build_dashboards.py`**: Script for generating and managing dashboard configuration.
*   **`siem/kibana/export_dashboards.py`**: Script for synchronizing live Kibana state to disk.
*   **`dashboard/core/kibana_timeline.py`**: Defines the structure and payload for the request timeline visualization.
*   **`dashboard/ui/kibana_timeline_capture.py`**: Handles the client-side workflow for live dashboard capture.