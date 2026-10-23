# Testing

This section covers how to test and validate the honeypot system.

## Testing Layers

- **Unit / Integration Tests**: Lua module logic, dashboard generation, timeline capture. Pure Lua modules (`*_rules.lua`) are testable under a plain Lua interpreter without OpenResty. Test files live in `ids/reverse_proxy_enhanced/lua/tests/` and `dashboard/tests/`.
- **Functional Testing**: End-to-end honeypot interaction and detection validation.
- **Blind Pentest Evaluation**: Simulated attacker assessments with internal-test secret gating.

## Unit Test Coverage

The codebase follows a pure/adapter split: `*_rules.lua` modules contain zero `ngx.*` dependencies and are unit-testable under a plain `lua` interpreter. Adapter modules (`*_handler.lua`, `pattern_analyzer.lua`, `router.lua`) perform I/O.

| Test File | Module Under Test | Coverage |
| :--- | :--- | :--- |
| `test_pattern_rules.lua` | `pattern_rules.lua` | URI pattern matching, header analysis, CVE patterns, automation UA scoring, static asset detection |
| `test_router_rules.lua` | `router_rules.lua` | Static asset detection, vulnerable plugin access, admin access, rapid automation, suspicious upload, decayed score, decision trace |
| `test_vulnerability_rules.lua` | `vulnerability_rules.lua` | CVE pattern detection, vulnerable plugin request detection, exploit kit pattern detection (incl. hyphen-escaping bug fix) |
| `test_suricata_rules.lua` | `suricata_rules.lua` | Alert line detection, alert extraction, severity-to-score, next_score, decayed_score, build_reason |
| `test_abuseipdb_rules.lua` | `abuseipdb_rules.lua` | Reportability check, category lookup, report comment generation |
| `test_lua_pattern_utils.lua` | `lua_pattern_utils.lua` | URL decoding, pattern escaping (hyphen bug fix), install wizard URI detection |
| `test_decay_policy.lua` | `decay_policy.lua` | Half-life multiplier, permaflag detection, escalation-aware decay |
| `test_ip_rules.lua` | `ip_rules.lua` | IPv4/IPv6 CIDR matching, IPv4-mapped IPv6 normalization |
| `test_upload_rules.lua` | `upload_rules.lua` | Content type analysis, upload parameters, endpoint analysis, bypass techniques, should_block_upload |
| `test_admin_rules.lua` | `admin_rules.lua` | Login attempt detection, admin pattern analysis, brute force scoring, credential stuffing scoring |
| `test_session_rules.lua` | `session_rules.lua` | Session anomaly detection, honeypot routing decisions |
| `test_session_identity_rules.lua` | `session_identity_rules.lua` | Session cookie signing/verification, fingerprinting, rejection records |
| `test_honeytoken_rules.lua` | `honeytoken_rules.lua` | Token-in-corpus matching |
| `test_prompt_injection_filter.lua` | `prompt_injection_filter.lua` | Prompt injection pattern detection |
| `test_pool_router_rules.lua` | `pool_router_rules.lua` | Pool assignment, health status, pool list parsing |
| `test_router_decide_route.lua` | `router.lua` | Routing decision pipeline integration |
| `test_gdpr_rules.lua` | `gdpr_rules.lua` | Timestamp freshness, canonical characteristics, payload validation |
| `test_pool_assignment.lua` | `pool_router.lua` | Pool assignment lifecycle |

## Dashboard Tests

*   `dashboard/tests/test_kibana_dashboards.py` — Validates NDJSON dashboard integrity against `build_dashboards.py` output.
*   `dashboard/tests/test_host_settings.py` — Host settings validation.
*   `dashboard/tests/test_overview_stats.py` — Overview stats validation.
*   `dashboard/tests/test_learning.py` — Learning page validation.

## Internal Test Secret

The `INTERNAL_TEST_SECRET` env var gates the `X-Route-Target` and `X-Risk-Score` response headers. When set, headers are only emitted for requests carrying a matching `X-Internal-Test-Auth` header; when unset/empty, headers are never emitted (fail closed). This allows `testing/scenario_*.sh` scripts to externally verify routing decisions without exposing the oracle to real users or blind pentests (see `BLIND_PENTEST_PROTOCOL.md` §8.2).

## Running Tests

```bash
# Lua unit tests (plain Lua interpreter, no OpenResty needed)
cd ids/reverse_proxy_enhanced/lua && lua tests/test_<module>.lua

# Dashboard tests
cd dashboard && python3 -m unittest discover -s tests -v

# Scenario tests
bash testing/scenario_*.sh
```

<div class="grid cards" markdown>

-   :material-test-tube:{ .lg .middle } **[Blind Pentest Evaluation](blind-pentest.md)**
    
    ---
    
    How to perform blind penetration testing evaluation of the honeypot.

</div>

## Honest Assessment

### Advantages
- **Pure/adapter split**: 18 pure Lua modules unit-testable under a plain Lua interpreter without OpenResty.
- **Comprehensive coverage**: Every `*_rules.lua` module has a corresponding test file.
- **Dashboard validation**: `test_kibana_dashboards.py` catches NDJSON drift between offline and live states.
- **Blind pentest protocol**: `INTERNAL_TEST_SECRET` gating prevents exposing routing/risk-score oracles.

### Limitations & Improvement Opportunities
- **No end-to-end integration tests**: Tests cover pure modules and dashboard integrity, but not the full Nginx → Lua → Redis → WordPress pipeline.
- **Blind pentest requires manual setup**: Scenario scripts and `INTERNAL_TEST_SECRET` configuration are manual steps.
- **No automated regression testing**: Test suite must be run manually; no CI/CD integration documented.
- **Sophistication classifier not tested**: `sophistication_analyzer.lua` has no dedicated test file.
- **Honeytoken handler not tested**: `honeytoken_handler.lua` has no dedicated test file (only `honeytoken_rules.lua` is tested).
