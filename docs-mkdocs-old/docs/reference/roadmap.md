# Roadmap

This page describes future development plans and roadmap for the system.

## Near-Term

*   Additional CVE seeding and detection coverage — expand `vulnerability_rules.lua` and `_G.config.vulnerability.cve_patterns` with newly published WordPress plugin vulnerabilities.
*   Enhanced behavioral analytics — extend `sophistication_analyzer.lua` with additional signals and finer-grained confidence thresholds.
*   Dashboard feature improvements — new panel types and improved Kibana visualizations for threat decay and session analysis.
*   `pattern_rules` generic pattern refinement — reduce false positives on legitimate REST API clients (WooCommerce mobile app, Stripe webhooks).

## Mid-Term

*   Automated threat intelligence feed integration — expand AbuseIPDB bulk feed usage and integrate additional threat feeds beyond `abuseipdb_client.lua`.
*   Expanded reporting and alerting automation — webhook-based alerts, Slack/PagerDuty integration for high-risk events.
*   Pool manager auto-scaling improvements — better resource budget management in `pool_router.lua` and `pool_manager`.
*   GDPR consent-gated identity enhancements — additional browser characteristics in `gdpr_rules.canonical_characteristics()`.

## Long-Term

*   ML-based anomaly detection — the codebase deliberately uses explainable rule-based detection (`sophistication_analyzer.lua` header comment references COUNTERARGUMENTS.md Q7 on the deliberate choice of explainable rule-based detection over black-box ML). Future work may explore hybrid approaches.
*   Multi-environment scaling and multi-tenant support — extend pool routing for multi-host, multi-tenant deployments.
*   Honeytoken expansion — additional honeytoken types beyond the current five (HT-APIKEY, HT-DBCREDS, HT-ADMINPW, HT-S3URL, HT-JWTKEY) in `honeytoken_handler.lua`.
*   Automated `eve.json` correlation verification for genuine external traffic (currently unverified for same-host testing caveat).
