# Detection

This section covers how the honeypot system detects and identifies attackers.

## Detection Pipeline Overview

The honeypot detection pipeline ingests attacker traffic and produces actionable detection signals through a layered chain, implemented as a series of pure Lua modules (no `ngx.*` dependency, unit-testable under a plain Lua interpreter) driving an adapter half that performs I/O:

1. **Traffic Capture** - Nginx reverse proxy forwards HTTP requests; `pattern_analyzer.analyze_request()` runs once per non-static request from `nginx.conf`'s `access_by_lua_block`.
2. **Lua Pattern Matching** - `pattern_rules.lua` and `vulnerability_rules.lua` match request URIs, headers, and arguments against seeded CVE exploit patterns and generic attack signatures.
3. **Suricata Correlation** - `suricata_rules.lua` parses `eve.json` alerts into structured records and converts them into risk-score deltas and human-readable reason strings.
4. **Risk Scoring** - `pattern_analyzer.lua` accumulates scores across URI patterns, headers, CVE matches, IP reputation, automation detection, and prompt-injection probes; `router.lua` accumulates onto a decaying session base.
5. **Routing Decision** - `router.lua`'s 11-stage decision pipeline diverts high-risk requests to isolated honeypot pool instances.
6. **Reporting** - `abuseipdb_rules.lua` gates external AbuseIPDB reporting and enriches comments with matched CVEs.

## Coverage Areas

The system distinguishes between:

- **Direct CVE detections** via plugin-specific and generic vulnerability patterns (`vulnerability_rules.lua`, `pattern_rules.analyze_cve_patterns()`).
- **Generic attack patterns** such as SQL injection, XSS, command injection, path traversal, file inclusion, deserialization, template injection, and code injection (`pattern_rules.SUSPICIOUS_PATTERNS`, Layer 2 specific checks).
- **Network IDS detections** via Suricata signatures aligned to OWASP WSTG categories (`suricata_rules.extract_alert()`, `build_reason()`).
- **Behavioral signals** including brute force, scanning, automation, and anomaly detection (`pattern_analyzer.detect_automation()`, `session_rules.analyze_session_anomalies()`).
- **Sophistication classification** - `sophistication_analyzer.lua` heuristically classifies traffic as scripted / ai_assisted / manual / unknown based on inter-request timing, User-Agent, browser fingerprint headers, and payload precision.

## Detection Stages (from `pattern_analyzer.lua`)

| Stage | Analyser | WSTG Mapping | Score Impact |
| :--- | :--- | :--- | :--- |
| Stage 1 | URI pattern analysis | WSTG-INPV, WSTG-CONF, WSTG-INFO | +15 base per generic pattern; +5..+80 per specific check |
| Stage 2 | Header analysis | WSTG-ATHN, WSTG-AUTHZ, CVE headers | +50 for flagged UA; +50 for CVE-2023-28121 header; +10 missing UA |
| Stage 3 | CVE pattern matching | WSTG-AUTHZ, WSTG-INPV | +40 per CVE matched |
| Stage 4 | IP reputation + request rate | — | +variable (threat_intel); +20 high request rate |
| Stage 5 | Request method analysis | WSTG-INPV | +10 OPTIONS/TRACE/CONNECT; +15 method override |
| Stage 6 | Automation detection | WSTG-INFO, WSTG-ATHN | +5..+30 per tool signature; +15 rapid-request streak |
| Stage 6b | WordPress AJAX upload analysis | WSTG-INPV-10 | Variable (upload_rules analysis) |
| Stage 7 | Prompt-injection probe | — | +prompt_injection_filter risk_score / 2 |

## Thresholds and Scaling

- **Honeypot threshold (default 80)**: Requests meeting or exceeding this score are diverted to honeypot pools (router.lua Stage 3). Raised from 50 to 80 after tuning to eliminate false positives on aggressive but legitimate REST API clients.
- **Max risk score**: Hard cap of 100 on accumulated scores.
- **IP reputation cap**: Default 10 per request on shared (NAT) addresses; nothing once `shared_ip_sessions` distinct sessions are active within `shared_ip_window`.
- **Decay half-life**: Default 300s; scaled by offense count via `decay_policy.lua`; permaflag after `permaflag_offenses` (default 5) or a single request scoring `permaflag_score` (default 100).

<div class="grid cards" markdown>

-   :material-target:{ .lg .middle } **[Detection Capabilities](capabilities.md)**
    
    ---
    
    What the system can detect and how it identifies malicious activity.

-   :material-security:{ .lg .middle } **[Seeded CVEs](cves.md)**
    
    ---
    
    The specific CVEs that have been seeded into the honeypot to attract attackers.

-   :material-network:{ .lg .middle } **[Suricata Network IDS](suricata.md)**
    
    ---
    
    Network-based detection using Suricata intrusion detection system.

-   :material-chart-line:{ .lg .middle } **[Advanced Signals](advanced.md)**
    
    ---
    
    Advanced behavioral analysis and anomaly detection signals.

</div>
