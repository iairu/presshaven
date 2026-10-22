# Lua Module Map

The request-handling Lua code follows a deliberate **pipeline + ports-and-adapters**
pattern (chosen over MVC for a codebase this size — understandable structure,
testable without a running nginx/Redis stack):

- a **`*_rules.lua`** module holds **pure decision logic** with *zero*
  `ngx.*` / `_G.*` dependency, unit-testable with a plain `lua` interpreter;
- the original **`*.lua`** file is a **thin adapter** that pulls config/request
  context and does all Redis/nginx I/O.

## Cores and adapters

| Adapter | Pure core | Tests | Responsibility |
|---|---|---:|---|
| `pattern_analyzer.lua` | `pattern_rules.lua` | 37 | Request scoring |
| `router.lua` | `router_rules.lua` | 29 | Routing predicates |
| `vulnerability_handler.lua` | `vulnerability_rules.lua` | 16 | CVE + exploit-kit pattern matching |
| `upload_handler.lua` | `upload_rules.lua` | 32 | File-upload risk scoring |
| `session_handler.lua` | `session_rules.lua` | 21 | Session anomaly detection + honeypot-routing eligibility |
| `admin_handler.lua` | `admin_rules.lua` | 37 | Login/brute-force scoring, admin-pattern detection, ajax-action matching, credential-stuffing scoring |
| `honeytoken_handler.lua` | `honeytoken_rules.lua` | 9 | Token-in-corpus matching |
| `abuseipdb_client.lua` | `abuseipdb_rules.lua` | 14 | Report-eligibility + category mapping |
| — | `prompt_injection_filter.lua` | 20 | OWASP LLM01-style detection (pure by design — the original model for this pattern) |
| — | `sophistication_analyzer.lua` | 26 | User classification (one `ngx.time()` stub) |
| `init.lua` `is_ip_whitelisted` | `ip_rules.lua` | 35 | IPv4/IPv6 CIDR matching |
| `router.lua` `decide_route()` | — (stubbed) | 46 | The full staged routing pipeline, run against in-memory stubs |
| — | `lua_pattern_utils.lua` | 9 | Shared `url_decode`/`escape_pattern`, deduplicated from 3 copies |

!!! success "484 unit tests across 17 suites, all passing"
    Run locally with `ids/reverse_proxy_enhanced/lua/tests/run_all.sh` (a plain
    Lua 5.1 interpreter); CI runs them on every push and PR via
    `.github/workflows/tests.yml`.

## Why `decide_route()` stays impure

Its 10-stage pipeline interleaves session mutation with Redis/AbuseIPDB I/O too
deeply to extract without risking a bug in the single most consequential function in
the system. Only its self-contained predicates (`is_static_asset`, `is_admin_access`,
`is_rapid_automation`, `is_suspicious_upload`, `is_vulnerable_plugin_access`) were
moved out; the whole function is instead covered by 46 tests that stub `ngx`,
`_G.config`/`_G.utils`, `pool_router` and `session_handler`.

`pool_router.lua` is the one module confirmed to need **no** split — it's 100% Redis
I/O with no pattern-matching, so no pure core exists to extract.

## Bugs the tests surfaced

Writing these tests surfaced **six real, previously-invisible bugs**, all fixed and
verified live:

1. `sophistication_analyzer.lua`'s `signals` audit list was silently empty on any
   session under 3 requests (an `ipairs`-over-a-leading-`nil`-hole gotcha).
2. `router.lua`'s `assign_honeypot_pool()` clobbered session data (lost
   `user_agent`) before the sophistication classifier saw it.
3. `pattern_analyzer.lua`'s `high_request_rate` IP-reputation signal was permanently
   dead — the counter it read was never written by anything.
4. **`router.lua` Stage 5 never matched a single hyphenated plugin slug** — every
   seeded vulnerable plugin except `cwmp` — because plugin names were concatenated
   unescaped into Lua patterns (`-` is a magic character there). Masked by an
   overlapping nginx-level regex `location` block.
5. **A live HTTP 500**: any POST to `/wp-admin/admin-ajax.php` with a non-empty,
   upload-looking query string crashed (`%2e%2e%2f` read as invalid Lua pattern
   backreferences). Fixed and verified with a real before/after request.
6. That crash masked a **second**: `red:get('threat_ips') or '{}'` doesn't handle
   Redis's `ngx.null` sentinel (truthy in Lua), so `cjson.decode` failed on any
   fresh/flushed Redis — present in four places across `admin_handler.lua`,
   `upload_handler.lua` and `vulnerability_handler.lua`.

## Known duplication (not yet fused)

- Two near-identical `header_filter_by_lua_block`s in `nginx.conf`
  (`[HEADER_FILTER]` server-level and `[LOCATION / HEADER]` location-level).
- Three modules (`session_handler.lua`, `pattern_rules.lua`,
  `sophistication_analyzer.lua`) each independently interpret the same User-Agent
  string — a shared UA-classification utility would remove the repetition.

One concrete code-level fuse already done: `lua_pattern_utils.lua` consolidated
`url_decode`/`escape_pattern` from three drifted copies, and `session_handler.lua`'s
own third copy of the static-asset check now calls `router_rules.is_static_asset()`.

See [the request pipeline](request-pipeline.md) for how these modules compose at
runtime.
