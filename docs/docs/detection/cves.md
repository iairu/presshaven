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
