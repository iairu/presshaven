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
