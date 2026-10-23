# Changelog

This page contains the history of changes to the system.

## Unreleased

*   Documentation expansion for detection, observability, operations, testing, and reference sections — enriched with Lua code comments and architecture details.

## Historical

### Detection Pipeline
*   `pattern_analyzer.lua` split into pure `pattern_rules.lua` + adapter. Pure core unit-testable under plain Lua interpreter.
*   `suruicata_rules.lua` migrated from `fast.log` regex parsing to structured `eve.json` JSON parsing (fixing the 8-capture-group-into-7-variables bug).
*   `vulnerability_rules.lua` extracted from `vulnerability_handler.lua` for pure CVE pattern matching.
*   `abuseipdb_rules.lua` extracted from `abuseipdb_client.lua` for pure report-eligibility logic.
*   `router_rules.lua` extracted from `router.lua` for pure routing predicates.
*   `upload_rules.lua` extracted from `upload_handler.lua` for pure upload pattern analysis.
*   `admin_rules.lua` extracted from `admin_handler.lua` for pure admin-access decision logic.
*   `session_rules.lua` extracted from `session_handler.lua` for pure session anomaly detection.
*   `decay_policy.lua` extracted as shared escalation-aware decay module.
*   `lua_pattern_utils.lua` promoted from duplicated copies in `pattern_rules.lua`, `router_rules.lua`, `vulnerability_rules.lua`, `upload_rules.lua` (fixing hyphen-escaping bug).
*   `sophistication_analyzer.lua` added for scripted/ai_assisted/manual/unknown classification.
*   `honeytoken_handler.lua` added for honeytoken injection and detection.
*   `gdpr_rules.lua` / `gdpr_handler.lua` added for consent-gated privacy-preserving identity.

### Routing & Pooling
*   `router.lua` decision pipeline with 11 stages (static, install wizard, sticky honeypot, risk threshold, CVE match, vulnerable plugin, IP reputation, admin attempts, accumulated suspicious, rapid automation, suspicious upload).
*   `pool_router.lua` implemented with exclusive assignment, spare provisioning, scale-up, reuse at resource limit.
*   Score accumulation added — session's decaying suspicion history folded into each request's score before threshold comparison (fixing session score laundering bug).
*   Decay system added — `decay_policy.lua` with offense-scaled half-life and permaflag thresholds.

### Security Fixes
*   `admin-ajax.php` excluded from `is_admin_access()` — fixed false-positive escalation of normal shoppers.
*   `is_vulnerable_plugin_request()` hyphen-escaping bug fixed via `lua_pattern_utils.escape_pattern()`.
*   `ngx.null` sentinel crash fixed — established `if not raw or raw == ngx.null then` idiom.
*   Empty Lua tables tagged with `cjson.empty_array_mt` in `_G.utils.log_security_event()` to prevent Elasticsearch mapping conflicts.
*   Suricata private IP filtering added — `is_private_ip()` filters RFC1918/loopback at ingestion time.

### Observability
*   Kibana dashboard NDJSON generation via `build_dashboards.py`.
*   Pattern report timeline dashboard for embed-mode screenshot capture.
*   Vector `nginx_error_in` source for security event forwarding to Elasticsearch.

## Versioning

Changes are tracked with semantic versioning for engine, detection, and dashboard components.
