# Primary Literature

This page lists academic and technical literature related to the system.

## Academic References

*   **Honeypot-based intrusion detection literature** — Foundational concepts for honeypot systems, deception technology, and intrusion detection.
*   **Intrusion detection and deception taxonomy** — Classification frameworks for honeypot types (low-interaction, high-interaction, hybrid) and detection methodologies.
*   **OWASP Web Security Testing Guide (WSTG) v4.2** — The category system used throughout the detection pipeline to classify attack patterns (WSTG-INPV, WSTG-ATHN, WSTG-AUTHZ, WSTG-CONF, WSTG-INFO, WSTG-IDNT, WSTG-SESS).
*   **COUNTERARGUMENTS.md Q7** — Documentation on the deliberate choice of explainable rule-based detection over black-box ML in `sophistication_analyzer.lua`.

## Technical References

*   **Suricata rule documentation** — Suricata IDS configuration, rule syntax, and `eve.json` log format used by `suruicata_rules.lua`.
*   **AbuseIPDB category mapping** — AbuseIPDB report category IDs (15=Hacking, 21=Web App Attack, 18=Brute-Force, 19=Bad Web Bot) referenced in `abuseipdb_rules.REASON_CATEGORIES`.
*   **Kibana saved objects API** — Used by `build_dashboards.py` and `export_dashboards.py` for dashboard import/export.
*   **Lua pattern syntax** — Lua pattern matching documentation relevant to `pattern_rules.lua`, `vulnerability_rules.lua`, and the hyphen-escaping bug fix via `lua_pattern_utils.escape_pattern()`.
*   **OpenResty / Nginx Lua** — Runtime environment for the honeypot's reverse proxy and detection pipeline.
*   **Redis Lua scripting** — Atomic pool assignment via `EVAL` in `pool_router_rules.ASSIGN_SCRIPT`.

## Related Work

*   **Honeypot platforms and IDS/SIEM integration** — Comparative studies of honeypot platforms (Dionaea, Cowrie, etc.) and their SIEM integration approaches.
*   **Threat intelligence sharing** — AbuseIPDB, MISP, and other threat intelligence platforms integrated via `abuseipdb_client.lua`.
*   **Session management and deception** — Techniques for session tracking, fingerprinting, and honeypot pool isolation.
*   **GDPR and privacy-preserving security** — Consent-gated identity and one-way signature approaches documented in `gdpr_rules.lua`.
*   **Honeytoken / CanaryToken research** — Academic literature on honeytoken injection and detection strategies implemented in `honeytoken_handler.lua`.
