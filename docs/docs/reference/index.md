# Reference

This section contains reference materials for the honeypot system.

## Reference Categories

- **Glossary**: Definitions of key terms used throughout the documentation.
- **Known Issues & Corrections**: Documented issues and workarounds.
- **Roadmap**: Future development plans.
- **Changelog**: History of changes.
- **Primary Literature**: Academic and technical literature.

## Architecture Reference

The honeypot system is built on a layered architecture:

### Pure/Adapter Split

All detection logic follows a pure/adapter split pattern:

*   **Pure modules** (`*_rules.lua`): No `ngx.*` dependency, no `_G.config`/`_G.utils` reliance, plain-`lua`-interpreter testable. Contain the actual pattern-matching/scoring decisions.
*   **Adapter modules** (`*_handler.lua`, `pattern_analyzer.lua`, `router.lua`): Pull config from `_G.config`, pull request context from `ngx.var/ngx.req`, perform all I/O (Redis, shared dict, logging), orchestrate the pure modules.

This split is what makes the core logic unit-testable without spinning up OpenResty.

### Pure Modules

| Module | Purpose | Key Functions |
| :--- | :--- | :--- |
| `pattern_rules.lua` | URI/header/CVE pattern scoring | `analyze_uri_patterns`, `analyze_headers`, `analyze_cve_patterns`, `score_automation_user_agent` |
| `vulnerability_rules.lua` | CVE/exploit-kit pattern matching | `detect_vulnerability_pattern`, `is_vulnerable_plugin_request`, `detect_exploit_kit_patterns` |
| `suricata_rules.lua` | eve.json alert parsing/scoring | `extract_alert`, `severity_to_score`, `decayed_score`, `build_reason` |
| `abuseipdb_rules.lua` | Report eligibility logic | `is_reportable_reason`, `get_categories`, `build_report_comment` |
| `router_rules.lua` | Routing predicates | `is_static_asset`, `is_vulnerable_plugin_access`, `is_admin_access`, `is_rapid_automation`, `decayed_score`, `decision_trace` |
| `upload_rules.lua` | File-upload pattern analysis | `is_file_upload`, `analyze_content_type`, `analyze_upload_parameters`, `should_block_upload` |
| `admin_rules.lua` | Admin-access decision logic | `is_login_attempt`, `analyze_admin_patterns`, `score_brute_force_attempts`, `score_login_credential_stuffing` |
| `session_rules.lua` | Session anomaly detection | `analyze_session_anomalies`, `should_route_to_honeypot` |
| `decay_policy.lua` | Escalation-aware decay | `half_life_multiplier`, `is_permaflagged`, `decay` |
| `lua_pattern_utils.lua` | Shared string helpers | `url_decode`, `escape_pattern`, `is_install_wizard_uri` |
| `ip_rules.lua` | IPv4/IPv6 CIDR matching | `parse`, `in_cidr`, `in_any` |
| `honeytoken_rules.lua` | Token-in-corpus matching | `find_token_in_corpus` |
| `gdpr_rules.lua` | Consent-gated identity | `is_timestamp_fresh`, `canonical_characteristics`, `validate` |
| `shared_ip_rules.lua` | Shared-address policy | `is_shared`, `contribution`, `track` |
| `pool_router_rules.lua` | Pool routing logic | `ASSIGN_SCRIPT`, `find_healthy_pool`, `proxy_target_for_pool` |
| `session_identity_rules.lua` | Session cookie identity | `sign`, `verify`, `fingerprint_source` |

### Shared Dictionaries

| Dictionary | Size | Purpose |
| :--- | :--- | :--- |
| `sessions` | 10 MB | Worker-local session cache |
| `threat_intel` | 10 MB | Threat intelligence + health checks |
| `rate_limit` | 10 MB | Rate counters |
| `honeypot_routes` | 1 MB | Pool assignment cache |

<div class="grid cards" markdown>

-   :material-book:{ .lg .middle } **[Glossary](glossary.md)**
    
    ---
    
    Definitions of key terms and concepts used in this documentation.

-   :material-alert:{ .lg .middle } **[Known Issues & Corrections](known-issues.md)**
    
    ---
    
    Known issues and their corrections or workarounds.

-   :material-road-variant:{ .lg .middle } **[Roadmap](roadmap.md)**
    
    ---
    
    Future development plans and roadmap for the system.

-   :material-file-document:{ .lg .middle } **[Changelog](changelog.md)**
    
    ---
    
    History of changes to the system.

-   :material-library-books:{ .lg .middle } **[Primary Literature](literature.md)**
    
    ---
    
    Academic and technical literature related to the system.

</div>
