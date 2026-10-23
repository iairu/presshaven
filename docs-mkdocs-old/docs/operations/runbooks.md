# Troubleshooting & Runbooks

This page contains troubleshooting guides and operational runbooks.

## Service Restart Runbook

1. Stop the affected service.
2. Clear stale state (queues, caches) if applicable.
3. Start the service.
4. Verify health endpoints and logs.
5. Confirm dashboards are operational.

## Incident Response Runbook

*   **Detect**: IDS alerts, high-risk IPs, reportable events.
*   **Triage**: Correlate with session and pattern data from `pattern_analyzer` and `router.lua` decision traces.
*   **Contain**: Apply rate limits / block lists via IP whitelist or AbuseIPDB reporting.
*   **Recover**: Review logs and adjust rules.

## Common Issues

### Suricata not producing alerts
Check rule reload and `eve.json` pipeline. `suruicata_rules.extract_alert()` returns nil for anything that isn't a well-formed alert event — verify `eve.json` lines contain `"event_type":"alert"`.

### Kibana dashboards stale
Re-run `build_dashboards.py` or `export_dashboards.py` to synchronize dashboard state.

### Timeline capture failures
Verify Kibana auth and embed configuration. `dashboard/ui/kibana_timeline_capture.py` automates login, imports saved objects, loads the timeline dashboard in embed mode, and waits for the render-complete flag.

### IP reputation not gating (same-host testing)
Suricata runs with `network_mode: host` and interface `"any"` — in same-host test setups, Suricata's `src_ip` may be a container-internal address that never correlates with nginx's `remote_addr`. Filter out private IPs via `suruicata_rules.is_private_ip()`. For genuine external traffic, Docker DNAT-based port publishing preserves source IP.

### Fast.log vs eve.json bug
Do not regex-parse `fast.log` — the previous version had 8 capture groups destructured into 7 variables, shifting every field after `priority` by one position. `src_ip` received classification text instead of a real IP. Use structured `eve.json` instead.

### Session not recovering after cookie clear
The passive fingerprint → session binding (`fp_session:<fingerprint>` in Redis) recovers sessions for clients that cleared cookies. Fingerprint is built from TLS ClientHello, HTTP version, User-Agent, Accept-Language/-Encoding, and optionally IP. Check `session_handler.request_fingerprint()` and `bind_fingerprint_to_session()`.

### Decay not aging out flagged IPs
Check `score_decay_half_life_seconds` — if 0 (THREAT_DECAY_ENABLED=false), decay returns the stored peak unchanged. Also check `permaflag_offenses` and `permaflag_score` thresholds in `decay_policy.lua`.

### false positives on legitimate traffic
The honeypot threshold was raised from 50 to 80 after tuning to eliminate false positives on aggressive but legitimate REST API clients (WooCommerce mobile app, Stripe webhooks). Consider raising `ip_reputation_cap` above 50 only if clients don't share addresses.

## Escalation

Escalate to repository maintainers with logs, dashboard state, and alert context.
