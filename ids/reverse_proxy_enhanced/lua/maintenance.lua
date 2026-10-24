-- maintenance.lua - Pure helpers for the scheduled-maintenance gate
--
-- PURPOSE:
--   The WordPress Update dashboard page takes the whole site offline for the
--   few minutes a core/WooCommerce upgrade runs (update production -> re-sync
--   files to the pools -> migrate each pool's DB). During that window every
--   request -- production and honeypot alike -- must be met with a friendly
--   503 "scheduled maintenance" page instead of a half-upgraded store or a
--   file/DB-schema mismatch that would look nothing like a real site.
--
--   The dashboard signals this by SET-ing a Redis key (honeypot_maintenance)
--   with a TTL; init_worker.lua's mirror timer copies that key into the
--   `threat_intel` shared dict (same "no Redis on the hot path" convention as
--   the pool-replication flags), and nginx.conf's access_by_lua_block reads
--   the shared-dict value at the very top of the pipeline and, when set,
--   serves the page built here.
--
--   Like router_rules.lua / pattern_rules.lua this module has NO ngx.* or
--   _G.* dependency so it is testable under a plain `lua` interpreter
--   (see tests/test_maintenance.lua). The ngx glue (reading the shared dict,
--   setting status/headers, ngx.say/ngx.exit) stays in nginx.conf.
--
-- FAIL-SAFE:
--   The Redis key is written with an expiry (see MAINTENANCE_TTL in the
--   dashboard's core/wp_update.py). If the dashboard dies mid-update and never
--   clears the key, Redis drops it when the TTL lapses and the mirror timer
--   then publishes "0", so the site comes back on its own rather than being
--   wedged offline forever. should_serve_maintenance() therefore only ever
--   has to answer "is the mirrored flag currently truthy".

local _M = {}

-- Retry-After seconds advertised to clients (and well-behaved crawlers) while
-- maintenance is on. Kept comfortably above a normal update's wall time so a
-- client that honours it backs off until the upgrade is realistically done.
_M.RETRY_AFTER = 120

-- Decide whether the maintenance page should be served, given the raw value
-- read from the shared dict (a string "1"/"0", or nil when the key was never
-- set / already reclaimed). Only an explicit "1" counts as "on": any nil,
-- empty, or "0" is treated as off so a missing/expired flag fails OPEN (site
-- stays up), never closed.
function _M.should_serve_maintenance(flag_value)
    return flag_value == "1"
end

-- Self-contained 503 body. No external assets (the upgrade may be rewriting
-- wp-content out from under us, and a honeypot pool must not have to serve a
-- stylesheet for this), inline CSS only, dark-mode aware, and deliberately
-- generic -- it names no software and leaks nothing about the stack, matching
-- the deception posture of the rest of the edge.
function _M.page_html(retry_after)
    retry_after = tonumber(retry_after) or _M.RETRY_AFTER
    local minutes = math.max(1, math.ceil(retry_after / 60))
    return table.concat({
        "<!doctype html>",
        "<html lang=\"en\"><head><meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        "<title>Scheduled maintenance</title>",
        "<meta http-equiv=\"refresh\" content=\"" .. retry_after .. "\">",
        "<style>",
        ":root{color-scheme:light dark}",
        "*{box-sizing:border-box}",
        "body{margin:0;min-height:100vh;display:flex;align-items:center;",
        "justify-content:center;font-family:-apple-system,BlinkMacSystemFont,",
        "'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#f4f5f7;",
        "color:#1f2430;padding:24px}",
        "@media(prefers-color-scheme:dark){body{background:#13151a;color:#e6e8ec}",
        ".card{background:#1c1f26!important;box-shadow:none!important;",
        "border:1px solid #2a2e37!important}}",
        ".card{background:#fff;max-width:28rem;width:100%;border-radius:14px;",
        "padding:40px 32px;box-shadow:0 10px 30px rgba(0,0,0,.08);text-align:center}",
        "h1{margin:0 0 12px;font-size:1.4rem}",
        "p{margin:0 0 10px;line-height:1.55;opacity:.85}",
        ".dot{display:inline-block;width:10px;height:10px;border-radius:50%;",
        "background:#e8a33d;margin-bottom:20px;",
        "box-shadow:0 0 0 0 rgba(232,163,61,.5);animation:pulse 1.8s infinite}",
        "@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(232,163,61,.5)}",
        "70%{box-shadow:0 0 0 12px rgba(232,163,61,0)}",
        "100%{box-shadow:0 0 0 0 rgba(232,163,61,0)}}",
        "</style></head><body><div class=\"card\">",
        "<span class=\"dot\"></span>",
        "<h1>We&rsquo;ll be right back</h1>",
        "<p>The store is briefly offline for scheduled maintenance.</p>",
        "<p>Please check back in about " .. minutes ..
            (minutes == 1 and " minute." or " minutes."),
        "</p></div></body></html>",
    }, "\n")
end

return _M
