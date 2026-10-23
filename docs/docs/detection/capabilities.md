# Detection Capabilities

This page describes the detection capabilities of the honeypot system.

## Capability Summary

The system provides detection coverage across multiple analytical layers, implemented across `pattern_rules.lua`, `vulnerability_rules.lua`, `suricata_rules.lua`, `abuseipdb_rules.lua`, `session_rules.lua`, `upload_rules.lua`, `admin_rules.lua`, and `sophistication_analyzer.lua`.

| Capability | Technique | Module | Description |
| :--- | :--- | :--- | :--- |
| **Direct CVE Matching** | Lua URI/argument/header patterns | `vulnerability_rules.lua` | Exact matching of seeded CVE exploit signatures; returns `{cve, severity, description, plugin, attack_vector}`. |
| **Generic Attack Patterns** | Lua pattern signatures | `pattern_rules.lua` | Heuristic coverage for SQLi, XSS, command injection, traversal, upload abuse, sensitive file access, reconnaissance probes. |
| **Network IDS** | Suricata `eve.json` alert parsing | `suricata_rules.lua` | Alert-based detection correlated via `suricata_rules`; severity-graded scoring (severity 1 → +50, severity 2 → +25, default → +10). |
| **Behavioral Signals** | Brute force, automation, anomalies | `session_rules.lua`, `pattern_analyzer.lua` | Session anomaly detection (IP/UA change, flagged UA, rapid requests); automation detection via UA fingerprint and timing streaks. |
| **Reportability** | AbuseIPDB mapping | `abuseipdb_rules.lua` | Deterministic gating (`is_reportable_reason()`) and comment enrichment with matched CVEs. |
| **Sophistication Classification** | Weighted rule set | `sophistication_analyzer.lua` | Classifies traffic as scripted / ai_assisted / manual / unknown using timing, UA, headers, and payload precision. |
| **Honeytoken Detection** | Token corpus scanning | `honeytoken_handler.lua`, `honeytoken_rules.lua` | Detects when injected fake credentials/API keys appear in inbound requests (high-confidence compromise signal). |

## Detection Techniques

### Pattern Matching
- **Generic patterns**: Layer 1 entries in `pattern_rules.SUSPICIOUS_PATTERNS` — each entry declares how it matches (`plain`, `ext`, `param`, `segment`, `pat`) so dots, dashes, and brackets are never silently treated as wildcards. Matches add +15 per entry.
- **Specific checks**: Layer 2 in `pattern_rules.analyze_uri_patterns()` with per-pattern scores (e.g., directory traversal +20, SQL drop +30, wp-config.bak +80) and OWASP WSTG mappings.
- **URL encoding evasion**: +10 when percent-encoding is detected in the URI.
- **HTTP Parameter Pollution**: +15 when more than 20 parameters are present.

### Header Analysis
- **Flagged User-Agents**: +50 for known automation/scanner tools (sqlmap, nmap, masscan, zap, acunetix, nikto, dirb, gobuster, wpscan, whatweb, nuclei, burpsuite, havij, pangolin).
- **Missing User-Agent**: +10 — legitimate browsers always send one.
- **CVE-2023-28121 header**: +50 when `X-WCPAY-PLATFORM-CHECKOUT-USER` is present (WooCommerce Payments header-based auth bypass).
- **Missing Referer on POST**: +5 (WSTG-ATHN-04).
- **HTTP Basic Authentication probe**: +5.

### CVE Pattern Matching
`pattern_rules.analyze_cve_patterns()` checks URI, query string, and headers against `_G.config.vulnerability.cve_patterns`. Each match scores +40. CVE patterns documented in `init.lua` include:

| CVE ID | Plugin | Attack Vector | Pattern |
| :--- | :--- | :--- | :--- |
| CVE-2023-28121 | woocommerce-payments | header_manipulation | `X-WCPAY-PLATFORM-CHECKOUT-USER` |
| CVE-2023-2986 | abandoned-cart-lite | encryption_bypass | `wcal_action=checkout_link` |
| CVE-2025-4403 | drag-and-drop-multiple-file-upload | file_upload_bypass | `dnd-wc-upload-file` |
| CVE-2025-2266 | cwmp | privilege_escalation | `cwmpUpdateOptions` |
| CVE-2025-47577 / CVE-2024-8425 | gift-voucher | file_upload_rce | `mwb_wgm_preview_mail` |
| CVE-2024-2387 | advanced-form-integration | sql_injection | `integration_id.*'` |
| CVE-2025-10142 | pagseguro-connect-woocommerce | path_traversal | `pc_added_uploaded_image` |
| CVE-2024-50508 | wp-file-upload | directory_traversal | `file%[path%]` |
| CVE-2024-25600 | bricks | rce | `bricks/v1/render_element` |
| CVE-2024-27956 | wp-automatic | sql_injection | `wp-automatic/inc/csv.php` |
| CVE-2024-1071 | ultimate-member | sql_injection | `um_get_members` |
| CVE-2022-0739 | bookingpress-appointment-booking | sql_injection | `bookingpress_front_get_category_services` |
| CVE-2024-2879 | layerslider | sql_injection | `ls_get_popup_markup` |

Generic WordPress patterns (GENERIC-WP-001 through GENERIC-WP-004) cover wp-config.php access, installation file access, user enumeration, and XMLRPC abuse.

### Exploit Kit Detection
`vulnerability_rules.detect_exploit_kit_patterns()` matches User-Agent signatures against known frameworks (metasploit, msfconsole, wpscan, sqlmap, burpsuite, nikto) with confidence scores (75-95). Automation indicators (`/../../../`, `union+select`, `script>alert`, `%3cscript%3e`, `eval%28`, `base64_decode`) add +10 each, capped at 95.

### Suricata Integration
`suruicata_rules.extract_alert()` pulls `timestamp`, `src_ip`, `signature`, `signature_id`, `category`, `severity` from decoded `eve.json` alert objects. `suricata_rules.severity_to_score()` maps Suricata severity (1=high → +50, 2=medium → +25, 3/unknown → +10). `suricata_rules.build_reason()` produces strings like `"suricata: CVE-2023-28121 WooCommerce Payments Unauthorized Admin Access Attempt"` for router.lua Stage 6 and AbuseIPDB reporting.

### Upload Analysis
`upload_rules.lua` analyzes content type (disguised scripts, unusual executable types), upload parameters (dangerous extensions, bypass techniques, directory traversal, suspicious destinations), upload endpoints (CVE-specific action names, theme/plugin editor, file manager), and User-Agent (automation tools, non-browser UAs). `upload_rules.should_block_upload()` blocks at risk_score ≥ 70 or multiple critical factors.

### Admin Access Analysis
`admin_rules.lua` detects direct admin file access (+20), user enumeration via REST API (+25), plugin/theme enumeration (+15), automated admin tools (+35), and suspicious admin action parameters (+20 each). Brute-force scoring: 3+ attempts → +25, 5+ → +50, 10+ → +80, plus +30 rapid succession bonus.

### Session Anomaly Detection
`session_rules.analyze_session_anomalies()` detects IP change, User-Agent change, flagged User-Agent, and rapid requests (< 1s gap with >5 requests).

### Sophistication Classification
`sophistication_analyzer.classify_session()` combines four signal families:
1. **Inter-request timing regularity** — sub-second pacing → scripted; regular interval → scripted; LLM-loop pacing → ai_assisted; irregular → manual.
2. **User-Agent category** — known scanner tools → scripted; known AI-agent HTTP clients → ai_assisted; real browser → manual.
3. **Browser fingerprint headers** — presence of sec-fetch-* etc. → manual; absence → split between scripted and ai_assisted.
4. **Payload precision** — pattern spray (≥6 patterns) → scripted; surgical CVE match → manual/ai_assisted.

Output includes `classification`, `confidence` (0..1), raw scores, and human-readable `signals` for auditability in ELK/session logs.

## Extending Detection

To add a new detection capability:

1. Add the pattern to the appropriate pure module (`pattern_rules.lua`, `vulnerability_rules.lua`, `upload_rules.lua`, `admin_rules.lua`).
2. Wire the adapter half (`pattern_analyzer.lua`, `vulnerability_handler.lua`, `upload_handler.lua`, `admin_handler.lua`) to call it and log results via `_G.utils.log_security_event()`.
3. Update `abuseipdb_rules.lua` if the new reason should be externally reportable.
4. Document the new pattern in `detection/cves.md` (for CVEs) or `detection/suricata.md` (for Suricata rules).
