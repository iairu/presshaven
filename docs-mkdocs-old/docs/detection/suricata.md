# Suricata Rules for WordPress Vulnerability Detection and Honeypot Traffic Analysis

This file contains Suricata rules specifically designed to detect attack patterns targeting the WooCommerce honeypot, organized by CVE and OWASP Web Security Testing Guide (WSTG) categories.

## OWASP WSTG Category Index:
*   **WSTG-INFO** – Information Gathering (sids 1000017-1000020, 1000049)
*   **WSTG-CONF** – Configuration Management (sids 1000019-1000020)
*   **WSTG-IDNT** – Identity Management (sids 1000018)
*   **WSTG-ATHN** – Authentication Testing (sids 1000017)
*   **WSTG-AUTHZ** – Authorization / Access Control (sids 1000001-1000008)
*   **WSTG-INPV** – Input Validation (all sub-cats)(sids 1000011-1000016, 1000026-1000041)
    *   **WSTG-INPV-01** Directory Traversal (sids 1000036-1000038)
    *   **WSTG-INPV-02** XSS (sids 1000030-1000032)
    *   **WSTG-INPV-05** SQL Injection (sids 1000011-1000013, 1000026-1000029)
    *   **WSTG-INPV-10** File Upload (sids 1000005-1000006, 1000009-1000010, 1000014-1000016)
    *   **WSTG-INPV-11** Local/Remote File Inclusion (sids 1000039-1000041)
    *   **WSTG-INPV-12** Command Injection (sids 1000033-1000035)
*   **WSTG-SESS** – Session Management (sids 1000017: brute-force implies session steal)

## CVE Coverage:
*   **CVE-2023-28121** WooCommerce Payments unauth admin (sids 1000001-1000002)
*   **CVE-2023-2986** Abandoned Cart hardcoded key (sids 1000003-1000004)
*   **CVE-2025-4403** DnD file upload type bypass (sids 1000005-1000006)
*   **CVE-2025-2266** CWMP unauthenticated options update (sids 1000007-1000008)
*   **CVE-2025-47577** Gift Voucher file upload RCE (sids 1000009-1000010)
*   **CVE-2024-8425** Gift Voucher alternate vector (sid 1000010)
*   **CVE-2024-2387** AFI SQL injection (sids 1000011-1000013)
*   **CVE-2025-10142** PagSeguro path traversal (sids 1000014-1000015)
*   **CVE-2024-50508** WP File Upload path traversal (sids 1000015-1000016)

## SID Allocation Summary:
*   **1000001-1000016**: CVE-specific detection rules
*   **1000017-1000025**: General WordPress attack patterns + plugin detection
*   **1000026-1000029**: SQL injection generic patterns (WSTG-INPV-05)
*   **1000030-1000032**: XSS patterns (WSTG-INPV-02)
*   **1000033-1000035**: Command injection (WSTG-INPV-12)
*   **1000036-1000038**: Directory traversal (WSTG-INPV-01)
*   **1000039-1000041**: File inclusion wrappers (WSTG-INPV-11)
*   **1000042-1000048**: Malicious user-agent strings (WSTG-INFO-02)
*   **1000049**: Version fingerprinting probe (WSTG-INFO-02)

## General Attack Patterns:
*   **WordPress Admin Brute Force Attempt** (SID 1000017)
*   **WordPress User Enumeration** (SID 1000018)
*   **WordPress Config File Access Attempt** (SID 1000019)
*   **WordPress Backup File Access** (SID 1000020)

## Plugin-Specific Detection (Activity Monitoring):
*   **WooCommerce Payments Plugin Access** (SID 1000021)
*   **Abandoned Cart Lite Plugin Access** (SID 1000022)
*   **Drag Drop File Upload Plugin Access** (SID 1000023)
*   **CWMP Plugin Access** (SID 1000024)
*   **Gift Voucher Plugin Access** (SID 1000025)

## SQL Injection Detection (Generic Patterns):
*   **SQL Injection - Union Select** (SID 1000026)
*   **SQL Injection - Information Schema** (SID 1000027)
*   **SQL Injection - MySQL Functions** (SID 1000028)
*   **SQL Injection - Time Delay** (SID 1000029)

## XSS Detection (Generic Patterns):
*   **XSS Script Tag** (SID 1000030)
*   **XSS JavaScript Event** (SID 1000031)
*   **XSS JavaScript Protocol** (SID 1000032)

## Command Injection Detection (Generic Patterns):
*   **Command Injection - System Commands** (SID 1000033)
*   **Command Injection - Pipe Commands** (SID 1000034)
*   **Command Injection - Backticks** (SID 1000035)

## Directory Traversal Detection (Generic Patterns):
*   **Directory Traversal - Dot Dot Slash** (SID 1000036)
*   **Directory Traversal - URL Encoded** (SID 1000037)
*   **Directory Traversal - Double Encoded** (SID 1000038)

## File Inclusion Detection (PHP Stream Wrapper Abuse):
*   **PHP Wrapper Usage** (SID 1000039)
*   **Data URI Scheme** (SID 1000040)
*   **File URI Scheme** (SID 1000041)

## Malicious User Agents – Security Tool Fingerprinting:
*   **Malicious User Agent - SQLMap** (SID 1000042)
*   **Malicious User Agent - Nikto** (SID 1000043)
*   **Malicious User Agent - Nmap** (SID 1000044)
*   **Malicious User Agent - WPScan** (SID 1000045)
*   **Malicious User Agent - Gobuster** (SID 1000046)
*   **Malicious User Agent - Dirb** (SID 1000047)
*   **Malicious User Agent - Burp Suite** (SID 1000048)

## Scanning and Reconnaissance – Version Fingerprinting Probes:
*   **WordPress Version Detection** (SID 1000049)
*   **WordPress Theme Detection** (SID 1000050)
*   **WordPress Plugin Enumeration** (SID 1000051)
*   **Admin Panel Discovery** (SID 1000052)

## Suspicious File Uploads:
*   **Suspicious PHP File Upload** (SID 1000053)
*   **Executable File Upload Attempt** (SID 1000054)
*   **Script File Upload Attempt** (SID 1000055)

## Rate Limiting and DoS Detection:
*   **High Rate HTTP Requests** (SID 1000056)
*   **WordPress Login Brute Force** (SID 1000057)

## Honeypot Specific Rules:
*   **Honeypot Trigger - Multiple Vulnerability Attempts** (SID 1000058)
*   **Honeypot Trigger - Automated Tool Detection** (SID 1000059)
*   **Honeypot Trigger - Rapid Vulnerability Scanning** (SID 1000060)

## Session Management Integration Rules:
*   **Session Anomaly - IP Change** (SID 1000061)
*   **Session Anomaly - User Agent Change** (SID 1000062)
*   **Suspicious Session Cookie Manipulation** (SID 1000063)

## Zero-Day and Generic Attack Patterns:
*   **Generic Code Injection Attempt** (SID 1000064)
*   **Generic Deserialization Attack** (SID 1000065)
*   **Generic Template Injection** (SID 1000066)

## API Abuse Detection:
*   **WordPress REST API Abuse** (SID 1000067)
*   **XMLRPC Amplification Attack** (SID 1000068)

## Custom Malware and Backdoor Detection:
*   **PHP Webshell Detection** (SID 1000069)
*   **Encoded PHP Payload** (SID 1000070)

## Rule Management and Maintenance

*   **SID Allocation**: SIDs are version-controlled in the Suricata rules file and follow a structured allocation scheme (CVE-specific, generic attack patterns, behavioral, honeypot triggers).
*   **Testing**: New rules should be validated against the Suricata test framework and the honeypot integration tests before deployment.
*   **Correlation**: Rule updates must keep the `suricata_rules.lua` correlation logic in sync with new SID-to-reason mappings.

## Suricata Integration Details (from `suruicata_rules.lua`)

### Module Purpose
`suruicata_rules.lua` holds the pure, testable pieces of the Suricata alert pipeline: parsing one `eve.json` line into an alert record (or nil for non-alert event types — flow, netflow, http, dns, tls — interleaved in the same file), and turning an alert into a risk-score delta and a human-readable reason string.

### Parsing Functions

| Function | Purpose |
| :--- | :--- |
| `is_alert_line(line)` | Cheap pre-check — substring search for `"event_type":"alert"` to skip full JSON decode on the vast majority of non-alert lines. Cannot throw on malformed/partial lines. |
| `extract_alert(decoded)` | Extracts `{timestamp, src_ip, src_port, dest_ip, dest_port, signature, signature_id, category, severity}` from a decoded eve.json event object. Returns nil for anything that isn't a well-formed alert event. |
| `severity_to_score(severity)` | Maps Suricata severity (1=high → +50, 2=medium → +25, default → +10) to score delta. |
| `next_score(previous_score, severity)` | Applies delta to running score, capped at MAX_SCORE (100). Never decreases on its own. |
| `decayed_score(entry, current_time, half_life_seconds, cfg)` | Time-decayed view of a `threat_ips[ip]` entry's stored `raw_score`. Escalation-aware: repeat offenders decay slower; permaflagged IPs never decay. |
| `build_reason(alert)` | Builds human-readable reason string: `"suricata: " .. alert.signature`. |

### Severity → Score Mapping

| Suricata Severity | Score Delta | Description |
| :--- | :--- | :--- |
| 1 | +50 | High severity (standard Suricata/Snort convention) |
| 2 | +25 | Medium severity |
| 3/unknown | +10 | Low or missing severity |

### Known Caveats

*   **Same-host (loopback) testing:** Suricata runs with `network_mode: host` and interface `"any"`, so it sees every hop of a request, not just the client→nginx leg. In same-host test setups, Suricata's `src_ip` for an alert may be a different internal address than what nginx logs as `remote_addr`, so the two never correlate locally. For genuine external traffic (Docker DNAT-based port publishing preserves source IP), this is expected to work correctly but has NOT been verified against genuine external traffic.
*   **Private IP filtering:** `is_private_ip()` filters RFC1918/loopback `src_ip` values at ingestion time so they never pollute `threat_ips` — by construction, an alert whose `src_ip` is RFC1918/loopback is never the address `router.lua`'s `remote_ip` could equal for a real request.
