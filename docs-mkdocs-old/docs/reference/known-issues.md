# Known Issues & Corrections

This page lists known issues and their corrections or workarounds.

## Known Issues

*   **Issue**: Dashboard generation drift between offline and live states.
    *   **Workaround**: Re-run `build_dashboards.py --ndjson` or `export_dashboards.py`.

*   **Issue**: Timeline capture requires Kibana auth setup.
    *   **Workaround**: Configure autologin scripts or manual login.

*   **Issue**: Suricata same-host (loopback) testing misattributes `src_ip`.
    *   **Description**: Suricata runs with `network_mode: host` and interface `"any"`, so it sees every hop of a request. In same-host test setups, the alert's `src_ip` may be a container-internal address that never correlates with nginx's `remote_addr`. This means Stage 6 IP reputation gating never fires locally from Suricata alerts. For genuine external traffic (Docker DNAT-based port publishing preserves source IP), this is expected to work but has NOT been verified against genuine external traffic.
    *   **Workaround**: `suruicata_rules.is_private_ip()` filters RFC1918/loopback `src_ip` values at ingestion time so they never pollute `threat_ips`.

*   **Issue**: Fast.log regex parsing bug (historical).
    *   **Description**: The previous fast.log parser had 8 capture groups destructured into 7 local variables — Lua silently drops excess captures, shifting every field after `priority` by one position. `src_ip` received classification text instead of a real IP. This was confirmed live and fixed by switching to structured `eve.json`.
    *   **Workaround**: Use `suruicata_rules.extract_alert()` on decoded `eve.json` objects instead of regex-parsing `fast.log`.

*   **Issue**: `admin-ajax.php` false positives (historical).
    *   **Description**: The original `upload_rules` analysis blanket-flagged every `admin-ajax.php` request regardless of actual signal, and `router_rules.is_admin_access()` treated it as admin area access. Since `admin-ajax.php` is WordPress's public AJAX gateway (hit constantly by WooCommerce frontend JS), this escalated normal shoppers to the honeypot after 3 product-page views.
    *   **Workaround**: `admin-ajax.php` is now excluded from `is_admin_access()` and gets dedicated, appropriately-scoped analysis (pattern_analyzer Stage 6b, upload_handler, CVE action-name checks).

*   **Issue**: Session score laundering (historical).
    *   **Description**: A single clean request (e.g., just loading `/`) fully reset a session that had JUST triggered a CVE match, letting a user alternate "run pattern" / "visit homepage" to re-run every pattern against production from a clean slate.
    *   **Workaround**: `router.lua` now folds the session's decaying suspicion history into each request's score before threshold comparison. A clean request (fresh score ≤ 10) neither adds to nor resets the running total.

*   **Issue**: `is_vulnerable_plugin_request()` hyphen-escaping bug (historical).
    *   **Description**: Concatenating an un-escaped plugin slug straight into a pattern silently broke the match for every hyphenated slug, since Lua reads `-` as its lazy-repetition magic character. Only `cwmp` (no hyphen) matched.
    *   **Workaround**: `lua_pattern_utils.escape_pattern()` escapes Lua pattern magic characters; both `vulnerability_rules.lua` and `router_rules.lua` use it.

*   **Issue**: `ngx.null` sentinel crash (historical).
    *   **Description**: `red:get(key)` returns the `ngx.null` userdata sentinel (NOT Lua nil) for a missing key, so `x or "{}"` and `if x then` don't catch an absent key — `cjson.decode()` crashed with "string expected, got userdata" on a fresh/flushed Redis.
    *   **Workaround**: Established `if not raw or raw == ngx.null then` idiom used throughout the codebase (e.g., `threat_intel.load()`, `admin_handler.should_block_admin_access()`).

## Corrections

*   Corrections to documentation should be recorded here with issue references and resolution notes.

## Reporting

New known issues should be added with severity, affected versions, and workarounds.
