# Glossary

This page contains definitions of key terms and concepts used in this documentation.

## Core Concepts

*   **Honeypot**: Decoy system designed to attract and engage attackers. The reverse proxy diverts suspicious requests to isolated honeypot pool instances running fake WordPress environments.
*   **IDS**: Intrusion Detection System — Suricata network IDS, which generates `eve.json` alerts parsed by `suruicata_rules.lua`.
*   **SIEM**: Security Information and Event Management platform — Elasticsearch/Kibana stack for log ingestion and visualization.
*   **CVE**: Common Vulnerabilities and Exposures identifier — used to name specific seeded vulnerability patterns in `vulnerability_rules.lua`.
*   **WSTG**: OWASP Web Security Testing Guide — category system used to classify detection patterns (e.g., WSTG-INPV-01 directory traversal, WSTG-INPV-05 SQL injection).

## Detection Terms

*   **SID**: Suricata rule identifier — allocated in `suricata.md` (e.g., 1000001-1000016 for CVE-specific rules, 1000017-1000025 for general WordPress attack patterns).
*   **Risk Score**: Accumulated threat score (0–100) computed by `pattern_analyzer.analyze_request()` from URI patterns, headers, CVE matches, IP reputation, automation detection, and prompt-injection probes.
*   **Honeypot Threshold**: Minimum risk score (default 80) that triggers honeypot routing (router.lua Stage 3).
*   **Decay**: Exponential reduction of stored risk scores over time since the last suspicious signal, implemented by `decay_policy.lua` and `router_rules.decayed_score()` / `suruicata_rules.decayed_score()`.
*   **Permaflag**: A state where a session's or IP's score stops decaying entirely — triggered by `permaflag_offenses` (default 5) or a single request scoring `permaflag_score` (default 100).
*   **Offense**: A counter bumped once per recorded attack signal on a session or IP, used by `decay_policy.lua` to slow decay and trigger permaflag.
*   **Honeytoken**: Fake high-value artefact (API key, credential, internal path) planted in honeypot responses — detection of its use outside the honeypot signals confirmed compromise (`honeytoken_handler.lua`).
*   **GDPR Signature**: Privacy-preserving one-way hash of browser characteristics used as a second identifier alongside the session cookie (`gdpr_rules.lua`).

## Architecture Terms

*   **Pure Module**: Lua module with no `ngx.*` dependency, plain-`lua`-interpreter testable (all `*_rules.lua` files).
*   **Adapter Module**: Lua module that performs I/O (Redis, shared dict, logging) and delegates decisions to pure modules (e.g., `pattern_analyzer.lua`, `router.lua`).
*   **Pool**: Isolated honeypot environment (`honeypot_eshop_N` + `honeypot_database_N`) assigned per user session (`pool_router.lua`).
*   **Escalation**: Gradual increase in response to repeated suspicious signals — e.g., admin access attempts escalate from warning (production) to honeypot routing after 3 attempts.
*   **Sticky Routing**: Once a session is marked `honeypot_bound`, all subsequent requests from that session are locked to the same honeypot pool.

## Scoring Terms

*   **Stage 6**: IP reputation gate in `router.lua` — diverts IPs scoring >50 on the address's own reputation (Suricata alerts, AbuseIPDB).
*   **Shared Address**: A public IP address shared by multiple sessions (carrier-grade NAT) — detected via `shared_ip_rules.is_shared()` when `shared_ip_sessions` distinct sessions are active within `shared_ip_window`.
*   **IP Reputation Cap**: Maximum score an address's own reputation can contribute per request on shared addresses (default 10, so it can never divert anyone on its own).
*   **Decision Trace**: Flat strings logged to Nginx's security access log by `router_rules.decision_trace()`, parsed by Vector into Kibana fields (request_score, decayed_score, offenses, decay_state, uri_class, patterns).

## Operations Terms

*   **Hardening**: Security posture improvements for production deployment.
*   **Runbook**: Operational troubleshooting and response procedures.
*   **Blind Pentest**: Simulated attacker assessment where the tester has no prior knowledge of the system's internals.
*   **Internal Test Secret**: Shared secret (`INTERNAL_TEST_SECRET`) gating diagnostic response headers to prevent exposing routing oracles.
