# Detection Advanced Logic Overview

This document summarizes the detection logic extracted from the core Lua modules used for vulnerability and threat intelligence processing.

## 1. Vulnerability Pattern Detection (`vulnerability_rules.lua`)

This module is responsible for direct pattern matching against URI requests to identify known vulnerability patterns or exploit kit signatures.

**Key Logic:**
*   Uses `lua_pattern_utils.escape_pattern` for safe pattern matching.
*   The core function `detect_vulnerability_pattern(uri, args, wcpay_checkout_user_header)` analyzes request URIs to flag potential vulnerabilities.

**Relevance:** This forms the basis for identifying direct exploit attempts or known vulnerable endpoints.

## 2. Threat Alert Processing (`suricata_rules.lua`)

This module processes raw threat intelligence (specifically `eve.json` alerts) to derive a risk score and a human-readable reason string.

**Key Logic:**
*   **Parsing:** It parses `eve.json` lines (for flow, netflow, http, dns, tls events) into structured alert records.
*   **Risk Scoring & Gating:** It connects incoming alerts to IP reputation checks (`pattern_analyzer.check_ip_reputation`) and is used in the honeypot diversion logic in `router.lua` Stage 6 ("IP reputation").
*   **Output:** Generates a final risk-score, delta, and a detailed reason string for each event.

**Relevance:** This module translates raw network security alerts into actionable internal risk signals.

## 3. AbuseIPDB Reporting Logic (`abuseipdb_rules.lua`)

This module governs the deterministic decision-making process for reporting detected IP addresses to the AbuseIPDB service. It acts as a whitelist for reportability.

**Key Logic:**
*   **Category Mapping:** Maintains a whitelist (`_M.REASON_CATEGORIES`) that maps specific routing reasons (e.g., `cve_pattern_match`, `suricata_confirmed_alert`, `multiple_admin_attempts`) to specific AbuseIPDB category IDs.
*   **Reportability Check:** A function `_M.is_reportable_reason(reason)` checks if a given reason is in the whitelist.
*   **Comment Generation:** It constructs a detailed report comment, including any associated CVEs found during the detection phase by concatenating matched CVEs.

**Relevance:** Ensures that only high-confidence, logic-driven signals (combining CVEs, Suricata alerts, and IP reputation hits) lead to external reporting.

## Risk Scoring Model

The internal risk scoring pipeline:

1. Computes a base risk score from the detection signal (e.g., CVE pattern match, Suricata severity).
2. Applies IP reputation checks and deltas.
3. Generates a final risk score, delta, and human-readable reason string.
4. Feeds into the diversion/router logic for handling malicious traffic.

## Scoring Architecture Details

### `pattern_analyzer.lua` Scoring Summary

From the module header comment:

| Signal | Score Impact |
| :--- | :--- |
| Static asset requests | 0 (always skipped) |
| Matching a suspicious pattern | +15 base, +5..+30 for specific checks |
| Matching a CVE pattern | +40 per CVE matched |
| Flagged user-agent string | +50 |
| Bad IP reputation | +variable (from threat_intel dict) |
| High per-IP request rate | +20 (rate_limit shared dict, >10 req/s) |
| Missing user-agent | +10 |
| CVE-specific header present | +50 |
| Automated tool signature | +5..+30 |
| Prompt-injection pattern hit | +(prompt_injection_filter risk_score / 2) |
| Honeypot threshold (default) | 80 (configurable in init.lua) |

### `decay_policy.lua` — Escalation-Aware Decay

Shared by the two risk-score decay paths:

*   `router_rules.decayed_score()` — per-SESSION suspicion decay
*   `suricata_rules.decayed_score()` — per-IP reputation (`threat_ips`) decay

**How decay works:**

*   Each offense multiplies the half-life by `(1 + decay_offense_slowdown)` — a repeat offender's score fades progressively more slowly.
*   Past `permaflag_offenses` offenses, OR once the stored peak has ever reached `permaflag_score`, decay stops entirely (permaflag).
*   Default: `decay_offense_slowdown = 0.75`, `permaflag_offenses = 5`, `permaflag_score = 100`.

**Default config values (from `init.lua`):**

| Config Key | Default | Description |
| :--- | :--- | :--- |
| `honeypot_threshold` | 80 | Minimum total score triggering honeypot routing |
| `max_risk_score` | 100 | Hard cap on accumulated score |
| `ip_reputation_cap` | 10 | Max reputation contribution per request on shared addresses |
| `shared_ip_sessions` | 2 | Distinct sessions on an address before it's considered shared |
| `shared_ip_window` | 3600 | Window (seconds) for shared-address detection |
| `score_decay_half_life_seconds` | 300 | Half-life for score decay |
| `decay_offense_slowdown` | 0.75 | Half-life multiplier per offense |
| `permaflag_offenses` | 5 | Offenses at/above this → score never decays |
| `permaflag_score` | 100 | Score at/above this → permaflag immediately |

## Extending Advanced Detection

New advanced signals can be added by extending the Lua modules and updating the correlation logic in `suricata_rules.lua`. All pure modules (`*_rules.lua`) are unit-testable under a plain Lua interpreter without OpenResty.

