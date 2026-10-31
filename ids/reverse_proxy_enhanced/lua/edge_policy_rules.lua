-- edge_policy_rules.lua - Pure helpers for the dashboard-managed edge policy
--
-- PURPOSE:
--   Two dashboard pages own the URL policy of the edge:
--
--   * Legitimate URL whitelist -- every known-legitimate WordPress/WooCommerce
--     endpoint, each one enabled or disabled. A request whose path is NOT on
--     the enabled whitelist earns the "unlisted_endpoint" signal
--     (whitelist.unlisted_score points, 0 = inventory only). The whitelist
--     only ever ADDS a signal for unknown paths; it never subtracts from or
--     skips any other check, so whitelisting a path can't be used to launder
--     a payload past detection (a SQLi on "/" still scores like before).
--
--   * Honeypot target URLs -- the CVE pattern registry (cve_patterns in
--     init.lua) plus the vulnerable plugin directories they live in. Each
--     target can be disabled (its CVE pattern stops matching / its plugin
--     path stops being a target), and targets.mode picks what a hit does:
--       "direct" -- divert to the honeypot at once, scoring bypassed
--                   (the behaviour before this policy existed)
--       "score"  -- add targets.target_score to the request's risk score
--                   and let the normal threshold decide
--
--   The dashboard SETs the policy as one JSON document in Redis
--   (honeypot_edge_policy, no TTL); init_worker.lua's mirror timer copies it
--   into the threat_intel shared dict and edge_policy.lua decodes it once per
--   worker per change. This module only validates/normalises the decoded
--   table and answers the matching questions, so it has NO ngx.* / _G.*
--   dependency and runs under a plain `lua` interpreter
--   (tests/test_edge_policy_rules.lua).
--
-- FAIL-SAFE:
--   A missing, unparseable or partial policy normalises to DEFAULTS, which
--   reproduce the pre-policy behaviour exactly: every target enabled, direct
--   diversion, no whitelist signal.

local _M = {}

_M.MODES = { direct = true, score = true }
_M.MATCH_TYPES = { exact = true, prefix = true }
_M.MAX_SCORE = 100

_M.DEFAULTS = {
    version = 0,
    targets = {
        mode = "direct",
        target_score = 40,
        disabled_cves = {},
        disabled_plugins = {},
    },
    whitelist = {
        unlisted_score = 0,
        entries = {},
    },
}

local function clamp_score(value, default)
    local n = tonumber(value)
    if not n then return default end
    n = math.floor(n + 0.5)
    if n < 0 then return 0 end
    if n > _M.MAX_SCORE then return _M.MAX_SCORE end
    return n
end

-- A list of strings -> set { [value] = true }; anything else is skipped.
local function to_set(list)
    local set = {}
    if type(list) ~= "table" then return set end
    for _, v in ipairs(list) do
        if type(v) == "string" and v ~= "" then set[v] = true end
    end
    return set
end

-- Lower-cased, percent-decoded path with no query string and no repeated or
-- dot segments, so "/WP-LOGIN.php", "//wp-login.php" and "/x/../wp-login.php"
-- all compare equal to "/wp-login.php". A path that tries to climb above the
-- root normalises to "/.." (it can never match a whitelist entry).
function _M.request_path(uri)
    if type(uri) ~= "string" or uri == "" then return "/" end
    local path = uri:match("^[^?#]*") or ""
    path = path:gsub("%%(%x%x)", function(h) return string.char(tonumber(h, 16)) end)
    path = path:lower():gsub("\\", "/")
    local trailing = path:sub(-1) == "/"
    local out = {}
    for segment in path:gmatch("[^/]+") do
        if segment == ".." then
            if #out == 0 then return "/.." end
            out[#out] = nil
        elseif segment ~= "." then
            out[#out + 1] = segment
        end
    end
    local normalised = "/" .. table.concat(out, "/")
    if trailing and #out > 0 then normalised = normalised .. "/" end
    return normalised
end

-- One whitelist entry -> { id, match, path } or nil when it is unusable.
local function normalise_entry(entry)
    if type(entry) ~= "table" then return nil end
    local path = entry.path
    if type(path) ~= "string" or path:sub(1, 1) ~= "/" then return nil end
    local match = _M.MATCH_TYPES[entry.match] and entry.match or "exact"
    local id = (type(entry.id) == "string" and entry.id ~= "") and entry.id or path
    -- Entries are compared against request_path(), so normalise them the
    -- same way (keeping a prefix entry's trailing slash, which is what makes
    -- "/wp-admin/" not also match "/wp-adminer.php").
    local normalised = _M.request_path(path)
    if match == "prefix" and path:sub(-1) == "/" and normalised:sub(-1) ~= "/" then
        normalised = normalised .. "/"
    end
    return { id = id, match = match, path = normalised }
end

-- Decoded JSON (or nil) -> a complete policy table. Never errors.
function _M.normalise(raw)
    local d = _M.DEFAULTS
    local policy = {
        version = d.version,
        targets = {
            mode = d.targets.mode,
            target_score = d.targets.target_score,
            disabled_cves = {},
            disabled_plugins = {},
        },
        whitelist = { unlisted_score = d.whitelist.unlisted_score, entries = {} },
    }
    if type(raw) ~= "table" then return policy end

    policy.version = tonumber(raw.version) or d.version

    local t = raw.targets
    if type(t) == "table" then
        if _M.MODES[t.mode] then policy.targets.mode = t.mode end
        policy.targets.target_score = clamp_score(t.target_score, d.targets.target_score)
        policy.targets.disabled_cves = to_set(t.disabled_cves)
        policy.targets.disabled_plugins = to_set(t.disabled_plugins)
    end

    local w = raw.whitelist
    if type(w) == "table" then
        policy.whitelist.unlisted_score = clamp_score(w.unlisted_score, d.whitelist.unlisted_score)
        if type(w.entries) == "table" then
            for _, entry in ipairs(w.entries) do
                local e = normalise_entry(entry)
                if e then policy.whitelist.entries[#policy.whitelist.entries + 1] = e end
            end
        end
    end
    return policy
end

-- The id of the first whitelist entry that covers `path` (already passed
-- through request_path), or nil. "exact" compares the whole path, ignoring a
-- trailing slash; "prefix" matches the entry itself and anything below it.
function _M.whitelist_match(path, entries)
    if type(path) ~= "string" then return nil end
    local bare = (path ~= "/" and path:sub(-1) == "/") and path:sub(1, -2) or path
    for _, e in ipairs(entries or {}) do
        if e.match == "exact" then
            local want = (e.path ~= "/" and e.path:sub(-1) == "/") and e.path:sub(1, -2) or e.path
            if bare == want then return e.id end
        elseif path:sub(1, #e.path) == e.path then
            return e.id
        elseif e.path:sub(-1) == "/" and bare == e.path:sub(1, -2) then
            -- "/shop" is covered by the prefix "/shop/"
            return e.id
        end
    end
    return nil
end

-- cve_patterns (CVE id -> Lua pattern) minus the disabled ids. Returns a new
-- table; the config table itself is never modified.
function _M.filter_cve_patterns(cve_patterns, disabled)
    local out = {}
    for cve, pattern in pairs(cve_patterns or {}) do
        if not (disabled and disabled[cve]) then out[cve] = pattern end
    end
    return out
end

-- Vulnerable plugin directory list minus the disabled ones, order kept.
function _M.filter_plugins(plugins, disabled)
    local out = {}
    for _, plugin in ipairs(plugins or {}) do
        if not (disabled and disabled[plugin]) then out[#out + 1] = plugin end
    end
    return out
end

return _M
