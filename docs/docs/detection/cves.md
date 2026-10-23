# Supported CVE Detections

This document lists the Computer Vulnerabilities and Exposures (CVEs) that are actively detected and tracked by the honeypot logic within the system, sourced from Lua pattern matching and Suricata alert analysis.

## 1. Direct CVE Matches (via `vulnerability_rules.lua`)

The following CVEs are explicitly matched via URI/argument pattern analysis in the vulnerability rules.

| CVE ID | Description | Severity | Plugin | Attack Vector |
| :--- | :--- | :--- | :--- | :--- |
| **CVE-2023-28121** | WooCommerce Payments unauthorized admin access via header manipulation. | HIGH | `woocommerce-payments` | `header_manipulation` |
| **CVE-2023-2986** | Abandoned Cart Lite exploitation using hardcoded encryption key. | HIGH | `abandoned-cart-lite` | `encryption_bypass` |
| **CVE-2025-4403** | Drag and Drop file upload with user-controlled file type. | CRITICAL | `drag-and-drop-multiple-file-upload` | `file_upload_bypass` |
| **CVE-2025-2266** | Unauthenticated WordPress options update allowing admin privilege escalation. | CRITICAL | `cwmp` | `privilege_escalation` |
| **CVE-2025-47577** | Gift Voucher plugin unauthenticated file upload leading to RCE. | CRITICAL | `gift-voucher` | `file_upload_rce` |
| **CVE-2024-8425** | Gift Voucher File Upload RCE. | CRITICAL | `gift-voucher` | `file_upload_rce` |
| **CVE-2024-2387** | Advanced Form Integration SQL injection via `integration_id` parameter. | HIGH | `advanced-form-integration` | `sql_injection` |
| **CVE-2025-10142** | PagSeguro Connect file path traversal vulnerability. | HIGH | `pagseguro-connect-woocommerce` | `path_traversal` |
| **CVE-2024-50508** | WordPress file upload directory traversal and sensitive file access. | HIGH | `wp-file-upload` | `directory_traversal` |
| **GENERIC-WP-001** | WordPress configuration file access attempt. | CRITICAL | `wordpress-core` | `sensitive_file_access` |
| **GENERIC-WP-002** | WordPress installation file access attempt. | HIGH | `wordpress-core` | `installation_abuse` |
| **GENERIC-WP-003** | WordPress user enumeration attempt. | MEDIUM | `wordpress-core` | `information_disclosure` |
| **GENERIC-WP-004** | WordPress XMLRPC endpoint access (potential brute force). | MEDIUM | `wordpress-core` | `xmlrpc_abuse` |

## 2. Suricata Alert-Based Detections

The system leverages Suricata alerts to detect potential exploits and threat activity. When an alert is generated, it is processed (via `suricata_rules.lua`) and used to generate a descriptive reason string, which is then mapped to an AbuseIPDB category.

*   **Detection Mechanism:** Suricata signature matching on network traffic.
*   **Source of Information:** Suricata JSON alerts are parsed to extract `src_ip`, `signature`, `severity`, and `category`.
*   **Reputation Scoring:** Alerts contribute to the IP reputation score, with severity levels mapped to score deltas (`severity_to_score`).

## 3. AbuseIPDB Reportability Mapping (via `abuseipdb_rules.lua`)

The honeypot logic determines if an IP should be reported to AbuseIPDB based on the detection signal.

**Reportable Categories:**
The following honeypot reasons are configured to be reportable to AbuseIPDB, and the report comment will be enriched with detected CVEs.

| Honeypot Reason | AbuseIPDB Categories | Description |
| :--- | :--- | :--- |
| `cve_pattern_match` | 15, 21 | CVE pattern detected via URL/argument matching. |
| `vulnerable_plugin_access` | 15, 21 | Access detected on plugins known to have specific CVEs. |
| `multiple_admin_attempts` | 18 | Indicators of brute-force attempts. |
| `rapid_automation_detected` | 19 | Signatures of malicious bots. |
| `suspicious_file_upload` | 21 | File upload vector anomalies. |
| `suricata_confirmed_alert` | 15, 21 | An IP confirmed via Suricata alert. |

**Report Comment Format:**
The detailed report comment generated for an IP will include specific CVE identifiers if they are found in the detection logic:
`Honeypot detection: [Honeypot Reason] (CVEs: [List of Matched CVEs])`

## Detection Coverage Summary

The current detection logic provides coverage for **14+ seeded CVEs** across multiple exploit vectors, including authentication bypass, privilege escalation, SQL injection, path traversal, and remote code execution vectors.

### CVE Detection Details (from `vulnerability_rules.lua`)

`vulnerability_rules.detect_vulnerability_pattern(uri, args, wcpay_checkout_user_header)` returns `{ cve, severity, description, plugin, attack_vector }` for each matched pattern:

| CVE ID | Severity | Description | Plugin | Attack Vector | Match Condition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CVE-2023-28121** | HIGH | WooCommerce Payments unauthorized admin access via header manipulation | `woocommerce-payments` | header_manipulation | URI contains `wp-json/wp/v2/users` AND `X-WCPAY-PLATFORM-CHECKOUT-USER` header present |
| **CVE-2023-2986** | HIGH | Abandoned Cart Lite exploitation using hardcoded encryption key | `abandoned-cart-lite` | encryption_bypass | URI/args contain `wcal_action=checkout_link` AND `validate=` |
| **CVE-2025-4403** | CRITICAL | Drag and Drop file upload with user-controlled file type | `drag-and-drop-multiple-file-upload` | file_upload_bypass | URI/args contain `dnd_codedropz_upload` AND `supported_type` |
| **CVE-2025-2266** | CRITICAL | Unauthenticated WordPress options update allowing admin privilege escalation | `cwmp` | privilege_escalation | URI/args contain `cwmpupdateoptions` |
| **CVE-2025-47577** | CRITICAL | Gift Voucher plugin unauthenticated file upload leading to RCE | `gift-voucher` | file_upload_rce | URI/args contain `mwb_wgm_preview_mail` |
| **CVE-2024-8425** | CRITICAL | Gift Voucher File Upload RCE | `gift-voucher` | file_upload_rce | URI/args contain `mwb_wgm_preview_mail` |
| **CVE-2024-2387** | HIGH | Advanced Form Integration SQL injection via `integration_id` parameter | `advanced-form-integration` | sql_injection | URI contains `advanced-form-integration-log` AND args contain `integration_id` with `'` / `union` / `select` |
| **CVE-2025-10142** | HIGH | PagSeguro Connect file path traversal vulnerability | `pagseguro-connect-woocommerce` | path_traversal | URI/args contain `pc_added_uploaded_image` AND `file[path]` |
| **CVE-2024-50508** | HIGH | WordPress file upload directory traversal and sensitive file access | `wp-file-upload` | directory_traversal | URI/args contain `file[path]` AND (`../` or `/etc/`) |
| **GENERIC-WP-001** | CRITICAL | WordPress configuration file access attempt | `wordpress-core` | sensitive_file_access | URI contains `wp-config.php` |
| **GENERIC-WP-002** | HIGH | WordPress installation file access attempt | `wordpress-core` | installation_abuse | URI contains `wp-admin/install.php` or `wp-admin/setup-config.php` |
| **GENERIC-WP-003** | MEDIUM | WordPress user enumeration attempt | `wordpress-core` | information_disclosure | URI contains `wp-json/wp/v2/users` OR `rest_route=.*/wp/v2/users` OR `author=<digits>` |
| **GENERIC-WP-004** | MEDIUM | WordPress XMLRPC endpoint access (potential brute force) | `wordpress-core` | xmlrpc_abuse | URI contains `xmlrpc.php` |

### Suricata Alert-Based Detections

The system leverages Suricata alerts to detect potential exploits and threat activity. When an alert is generated, it is processed (via `suricata_rules.lua`) and used to generate a descriptive reason string, which is then mapped to an AbuseIPDB category.

*   **Detection Mechanism:** Suricata signature matching on network traffic.
*   **Source of Information:** Suricata JSON alerts are parsed to extract `src_ip`, `signature`, `severity`, and `category`.
*   **Reputation Scoring:** Alerts contribute to the IP reputation score, with severity levels mapped to score deltas (`severity_to_score`): severity 1 → +50, severity 2 → +25, default → +10. Max score capped at 100.
*   **Why eve.json (not fast.log):** The previous fast.log regex parser had 8 capture groups destructured into 7 variables — Lua silently drops excess captures, shifting every field after `priority` by one position. `src_ip` received classification text instead of a real IP. eve.json is structured JSON with named fields, eliminating this bug class.
*   **Private IP filtering:** `is_private_ip()` filters RFC1918/loopback alerts at ingestion time so container-internal hops never pollute `threat_ips`.
*   **Decay:** `decayed_score()` applies exponential decay at READ time based on `score_decay_half_life_seconds`, offense count, and permaflag thresholds (see `decay_policy.lua`).

## AbuseIPDB Reportability Mapping (via `abuseipdb_rules.lua`)

The honeypot logic determines if an IP should be reported to AbuseIPDB based on the detection signal.

**Reportable Categories:**
The following honeypot reasons are configured to be reportable to AbuseIPDB, and the report comment will be enriched with detected CVEs.

| Honeypot Reason | AbuseIPDB Categories | Description |
| :--- | :--- | :--- |
| `cve_pattern_match` | 15, 21 | CVE pattern detected via URL/argument matching. |
| `vulnerable_plugin_access` | 15, 21 | Access detected on plugins known to have specific CVEs. |
| `multiple_admin_attempts` | 18 | Indicators of brute-force attempts. |
| `rapid_automation_detected` | 19 | Signatures of malicious bots. |
| `suspicious_file_upload` | 21 | File upload vector anomalies. |
| `suricata_confirmed_alert` | 15, 21 | An IP confirmed via Suricata alert. |

**Report Comment Format:**
`Honeypot detection: [Honeypot Reason] (CVEs: [List of Matched CVEs])`

### Adding a New CVE Detection

To extend the honeypot detection coverage with a newly discovered or seeded CVE:

1. Add the corresponding exploit pattern to `vulnerability_rules.lua` (returns `{cve, severity, description, plugin, attack_vector}`).
2. Add the CVE pattern to `_G.config.vulnerability.cve_patterns` in `init.lua`.
3. Allocate a new or reuse a Suricata SID in `suricata_rules.lua` if network-level detection is needed.
4. Update the AbuseIPDB reportability mapping in `abuseipdb_rules.lua` if the new reason should be externally reportable.
5. Document the new CVE in this file, the Suricata rules, and the advanced detection logic.

