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

## Detection Function Reference

The following functions are the core detection entry points, documented from their Lua comments:

### `pattern_analyzer.lua` (Adapter)

| Function | Signature | Description |
| :--- | :--- | :--- |
| `analyze_request(uri, headers, remote_ip)` | Returns `pattern_result` | Entry point called once per non-static request from `nginx.conf`'s `access_by_lua_block`. Runs every sub-analyser in sequence, accumulates scores into a single `pattern_result` table, sets `.suspicious` when total reaches/exceeds `honeypot_threshold`. |
| `check_ip_reputation(ip, actor)` | Returns `{score, reason, shared, raw_score}` | The address's own reputation (Suricata alerts, AbuseIPDB). Limited on shared (NAT) addresses — at most `ip_reputation_cap` per request, nothing once `shared_ip_sessions` distinct sessions active within `shared_ip_window`. |
| `track_address_sessions(ip, actor)` | Returns `count` | Records `actor` as active on `ip` and returns how many distinct sessions were active within `shared_ip_window`. |
| `session_request_rate_high(actor)` | Returns `boolean` | More than 10 requests/second sustained within this session's current 60s window. Per session, so one flooding client doesn't raise the score of everyone behind the same NAT address. |
| `detect_automation(headers, uri)` | Returns `{score, detected, tool}` | User-Agent fingerprint matching (pure, from `pattern_rules`) plus rapid-request timing check (I/O, shared `sessions` dict). Requires 3+ consecutive requests within 0.5s to flag automation (not a single close pair). |
| `is_static_asset(uri)` | Returns `boolean` | Delegates to `pattern_rules.is_static_asset()` — query-string-stripping, matches suffixes and path prefixes. |

### `vulnerability_rules.lua` (Pure)

| Function | Signature | Description |
| :--- | :--- | :--- |
| `detect_vulnerability_pattern(uri, args, wcpay_checkout_user_header)` | Returns `{cve, severity, description, plugin, attack_vector}` or nil | Pure CVE/exploit-kit pattern matching. No `ngx.*` dependency, plain-Lua testable. |
| `is_vulnerable_plugin_request(uri)` | Returns `boolean, plugin_slug` | Checks if URI accesses a known-vulnerable plugin directory. |
| `detect_exploit_kit_patterns(headers, uri, args)` | Returns `{suspicious, kit_type, confidence, indicators}` | Matches User-Agent against known frameworks (metasploit, wpscan, sqlmap, etc.) and automation indicators (`/../../../`, `union+select`, etc.). |

### `suricata_rules.lua` (Pure)

| Function | Signature | Description |
| :--- | :--- | :--- |
| `is_alert_line(line)` | Returns `boolean` | Cheap pre-check — substring search for `"event_type":"alert"` to skip full JSON decode on non-alert lines. Cannot throw on malformed/partial lines. |
| `extract_alert(decoded)` | Returns alert record or nil | Extracts `{timestamp, src_ip, src_port, dest_ip, dest_port, signature, signature_id, category, severity}` from decoded eve.json. Returns nil for non-alert or malformed events. |
| `severity_to_score(severity)` | Returns `integer` | Maps Suricata severity (1=high → +50, 2=medium → +25, default → +10) to score delta. |
| `next_score(previous_score, severity)` | Returns `integer` | Applies delta to running score, capped at MAX_SCORE (100). Never decreases on its own. |
| `decayed_score(entry, current_time, half_life_seconds, cfg)` | Returns `number` | Time-decayed view of a `threat_ips[ip]` entry's stored `raw_score`. Escalation-aware: repeat offenders decay slower; permaflagged IPs never decay. |
| `build_reason(alert)` | Returns `string` | Builds human-readable reason: `"suricata: " .. alert.signature`. |
| `is_private_ip(ip)` | Returns `boolean` | Filters RFC1918/loopback addresses so container-internal hops never pollute `threat_ips`. |

### `abuseipdb_rules.lua` (Pure)

| Function | Signature | Description |
| :--- | :--- | :--- |
| `is_reportable_reason(reason)` | Returns `boolean` | Whether a routing reason is confident enough to justify AbuseIPDB reporting. |
| `get_categories(reason)` | Returns `table|nil` | AbuseIPDB category ID list for a reason, or nil if not reportable. |
| `build_report_comment(reason, details)` | Returns `string` | Builds report comment: `"Honeypot detection: " .. reason .. " (CVEs: ...)"`. |

### `router.lua` (Adapter)

| Function | Signature | Description |
| :--- | :--- | :--- |
| `decide_route(session_data, pattern_result, remote_ip, session_id)` | Returns `routing_decision` | Core routing function. 11-stage pipeline. Returns `{target, upstream, update_session, session_data, trace}`. |
| `apply_routing_decision(decision)` | Returns `decision` | Sets `ngx.var.route_decision`, `ngx.var.backend_upstream`, `X-DB-Target` header, and honeypot-specific headers. |
| `is_static_asset(uri)` | Returns `boolean` | Delegates to `router_rules.is_static_asset()`. |
| `is_vulnerable_plugin_access(uri)` | Returns `boolean` | Delegates to `router_rules.is_vulnerable_plugin_access()`. |
| `is_admin_access(uri)` | Returns `boolean` | Delegates to `router_rules.is_admin_access()`. |
| `is_rapid_automation(session_data, pattern_result)` | Returns `boolean` | Delegates to `router_rules.is_rapid_automation()`. |
| `is_suspicious_upload()` | Returns `boolean` | Delegates to `router_rules.is_suspicious_upload()`. |

### `sophistication_analyzer.lua`

| Function | Signature | Description |
| :--- | :--- | :--- |
| `classify_session(session_data, pattern_result, headers)` | Returns `{classification, confidence, scores, signals, timing_samples}` | Heuristically classifies traffic as scripted/ai_assisted/manual/unknown. Deterministic, fully inspectable weighted rule set. Every contributing signal returned in `signals` list for auditability. |

### `honeytoken_handler.lua` (Adapter)

| Function | Signature | Description |
| :--- | :--- | :--- |
| `analyze_request_for_tokens()` | Returns `detection_result` or nil | Scans inbound request for known honeytoken values (Authorization header, URI, POST body). Returns `{token_id, type, severity, use_count}` if found. |
| `record_token_use(token_id, value)` | Returns `integer` | Records token use in Redis, increments `use_count`. |
| `build_html_injection(pool_num)` | Returns `string|nil` | Injects honeytoken hints into HTML response body as hidden comment. |
| `build_api_credential_injection()` | Returns `table` | Builds fake WooCommerce API credential response fragment. |
| `build_config_leak_injection()` | Returns `string` | Builds fake wp-config.php snippet for honeypot config-file leak responses. |
| `get_token_stats()` | Returns `table` | Retrieves usage statistics for all known honeytokens from Redis. |

### `pool_router.lua` (Adapter)

| Function | Signature | Description |
| :--- | :--- | :--- |
| `get_or_assign_pool(owner)` | Returns `integer` | Retrieves existing session→pool assignment or creates new one via atomic Redis EVAL. |
| `get_upstream_for_pool(pool_num)` | Returns `string` | Returns nginx upstream name (`honeypot_backend_N` or `honeypot_eshop_N` for runtime pools). |
| `refresh_assignment_ttl(owner)` | Returns `boolean` | Extends TTL of session's pool assignment without changing pool number. |
| `get_pool_assignment(owner)` | Returns `integer|nil` | Look up current pool assignment without creating a new one. |
| `get_pool_stats()` | Returns `table` | Collects runtime statistics for all pools. |
| `refresh_pool_list()` | Returns `boolean` | Mirrors `honeypot_pool:ready` from Redis into shared dict. |

### `gdpr_rules.lua` (Pure)

| Function | Signature | Description |
| :--- | :--- | :--- |
| `is_timestamp_fresh(ts, now, window)` | Returns `boolean` | Whether a payload timestamp is inside the freshness window (symmetric around `now`). |
| `canonical_characteristics(payload)` | Returns `string|nil` | Canonical string of identifying characteristics with timestamp keys removed and remaining keys sorted. |
| `validate(payload, now, window)` | Returns `string|nil, string` | Validates decoded payload and returns canonical characteristics string or rejection status. |

### `ip_rules.lua` (Pure)

| Function | Signature | Description |
| :--- | :--- | :--- |
| `parse(s)` | Returns `byte array|nil` | Parses IPv4/IPv6 address into byte array (4 bytes IPv4, 16 bytes IPv6). Normalizes IPv4-mapped IPv6 to IPv4 form. |
| `in_cidr(ip, cidr)` | Returns `boolean` | True if `ip` falls inside `cidr` range. Families never cross-match. |
| `in_any(ip, ranges)` | Returns `boolean` | True if `ip` matches any entry in `ranges`. |

### `session_handler.lua` (Adapter)

| Function | Signature | Description |
| :--- | :--- | :--- |
| `create_session(ip_address, user_agent, initial_route, provided_session_id)` | Returns `session_data` | Creates new session with UUID (CSPRNG), stores in Redis with TTL, caches locally, binds fingerprint. |
| `get_session(session_id)` | Returns `session_data|nil` | Retrieves session from local cache first, falls back to Redis. |
| `update_session(session_id, updates)` | Returns `boolean` | Applies updates, increments request count (non-static only), stores in Redis and local cache. |
| `mark_compromised(session_id, reason)` | Returns `boolean` | Marks session compromised, binds to honeypot, logs security event, stores in Redis set. |
| `request_fingerprint()` | Returns `string|nil` | Computes passive fingerprint from TLS ClientHello, HTTP version, User-Agent, Accept headers, and optionally IP. |
| `analyze_session_anomalies(session_data)` | Returns `table` | Detects IP change, UA change, flagged UA, rapid requests. |

### `admin_handler.lua` (Adapter)

| Function | Signature | Description |
| :--- | :--- | :--- |
| `process_admin_request(remote_ip, uri, actor)` | Returns `score, pattern_name` | Scores admin-area request. Per-session (not per-IP) counters. Whitelisted IPs bypass. |
| `check_brute_force_attempts(ip)` | Returns `integer` | Scores brute-force attempts within 5-min window (3+ → +25, 5+ → +50, 10+ → +80, +30 rapid succession). |
| `analyze_admin_patterns(uri, user_agent, method)` | Returns `{suspicious, reason, score}` | Detects direct admin file access, user enumeration, plugin enumeration, automated tools, suspicious action params. |
| `should_block_admin_access(ip)` | Returns `boolean` | True if IP reputation score ≥ 70 or brute-force score ≥ 80. |

### `upload_handler.lua` (Adapter)

| Function | Signature | Description |
| :--- | :--- | :--- |
| `analyze_upload(headers, args)` | Returns `{is_suspicious, risk_score, risk_factors, upload_type}` | Full upload analysis — content type, parameters, endpoints, user agent, bypass techniques. |
| `should_block_upload(analysis)` | Returns `boolean, reason` | Blocks at risk_score ≥ 70 or multiple critical factors or dangerous combination. |

### `vulnerability_handler.lua` (Adapter)

| Function | Signature | Description |
| :--- | :--- | :--- |
| `log_vulnerable_access(remote_ip, uri)` | — | Logs vulnerability access event, stores in Redis lists, updates threat intel. |
| `update_threat_intel_for_vulnerability(ip, vulnerability)` | — | Updates threat intel score based on CVE severity (CRITICAL +40, HIGH +30, MEDIUM +20, LOW +10). |
| `generate_vulnerability_report(ip)` | Returns `table` | Generates per-IP vulnerability report (total attempts, unique CVEs, severity breakdown, plugin targets, attack vectors, timeline). |

### `threat_intel.lua` (Adapter)

| Function | Signature | Description |
| :--- | :--- | :--- |
| `load(red)` | Returns `table` | Decodes threat_ips from Redis, tolerating missing key (nil or ngx.null) and undecodable JSON. |
| `ensure(threats, ip, extra_defaults)` | Returns `entry` | Returns threats[ip], creating clean default entry if absent. |
| `persist(red, threats)` | Returns `string` | Persists threats to Redis AND mirrors into shared-memory dict. |

### `init.lua` (Configuration)

Key configuration sections and their defaults:

| Section | Key | Default | Description |
| :--- | :--- | :--- | :--- |
| `redis` | `host` | `session_store` | Docker service name |
| `redis` | `timeout` | 2000ms | Connect/send timeout |
| `redis` | `read_timeout` | 5000ms | Reply timeout (looser, for host scheduling stalls) |
| `session` | `cookie_name` | `SERVERID` | Mimics HAProxy stickiness cookie |
| `session` | `max_idle_time` | 3600s | Session TTL |
| `session` | `signing_key_stable` | from env | Whether key came from `SESSION_SIGNING_KEY` |
| `session` | `recovery_uses_ip` | true | Include IP in passive fingerprint |
| `session` | `recovery_window` | 900s | Fingerprint→session binding TTL |
| `session` | `tamper_score` | 50 | Score added for tampered cookies |
| `gdpr` | `enabled` | true | GDPR subsystem toggle |
| `gdpr` | `timestamp_window` | 300s | Token freshness window |
| `gdpr` | `binding_ttl` | 3600s | Honeypot→signature binding TTL (prolonged on match) |
| `threat` | `honeypot_threshold` | 80 | Minimum score for honeypot routing |
| `threat` | `max_risk_score` | 100 | Hard cap on accumulated score |
| `threat` | `ip_reputation_cap` | 10 | Max reputation contribution on shared addresses |
| `threat` | `shared_ip_sessions` | 2 | Distinct sessions before address is "shared" |
| `threat` | `shared_ip_window` | 3600s | Window for shared-address detection |
| `threat` | `score_decay_half_life_seconds` | 300s | Half-life for score decay (0 = decay disabled) |
| `threat` | `decay_offense_slowdown` | 0.75 | Half-life multiplier per offense |
| `threat` | `permaflag_offenses` | 5 | Offenses at/above this → no decay |
| `threat` | `permaflag_score` | 100 | Score at/above this → permaflag |
| `abuseipdb` | `api_key` | from env | When nil/placeholder, client disables itself |
| `abuseipdb` | `confidence_minimum` | 90 | Bulk feed confidence threshold |
| `abuseipdb` | `daily_check_limit` | 1000 | Free-tier daily cap on on-demand checks |
| `abuseipdb` | `blacklist_enabled` | false | Bulk blacklist pull opt-in |
| `abuseipdb` | `blacklist_refresh_hours` | 24 | Minimum age before fresh blacklist call |
| `internal_test_secret` | — | from env | Gates diagnostic headers (fail closed when unset) |

## Configuration Guide

All values can be overridden at deploy time via environment variables injected through `docker-compose.yml`. Password fields (`REDIS_PASSWORD`, `ABUSEIPDB_API_KEY`, `GDPR_PRIVATE_KEY`) MUST be set via env vars; never hardcode secrets.
