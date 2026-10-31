-- edge_policy.lua - ngx glue for the dashboard-managed edge policy
--
-- Reads the policy JSON that init_worker.lua's mirror timer copies from Redis
-- (honeypot_edge_policy) into the threat_intel shared dict, and keeps the
-- decoded, normalised result per worker until the raw text changes, so the
-- hot path does one shared-dict GET and a string compare per request. The
-- rules themselves live in edge_policy_rules.lua (pure, unit-tested).
--
-- Outside nginx (the plain-lua test suites) there is no ngx.shared, and
-- get() returns the defaults -- the pre-policy behaviour.

local rules = require "edge_policy_rules"

local _M = {}

_M.REDIS_KEY = "honeypot_edge_policy"
_M.DICT_KEY = "edge_policy"

local cached_raw = false   -- false = nothing decoded yet (nil is "no policy")
local cached = nil         -- { policy, cve_patterns, plugins }

local function build(raw)
    local decoded = nil
    if raw then
        local ok, cjson = pcall(require, "cjson")
        if ok then
            local okd, value = pcall(cjson.decode, raw)
            if okd then
                decoded = value
            elseif ngx and ngx.log then
                ngx.log(ngx.ERR, "[EDGE POLICY] Unparseable policy in shared dict, using defaults: ", value)
            end
        end
    end
    local policy = rules.normalise(decoded)
    local vuln = (_G.config and _G.config.vulnerability) or {}
    return {
        policy = policy,
        cve_patterns = rules.filter_cve_patterns(vuln.cve_patterns, policy.targets.disabled_cves),
        plugins = rules.filter_plugins(vuln.plugins, policy.targets.disabled_plugins),
    }
end

local function current()
    local raw = nil
    local dict = ngx and ngx.shared and ngx.shared.threat_intel
    if dict then raw = dict:get(_M.DICT_KEY) end
    if cached == nil or raw ~= cached_raw then
        cached = build(raw)
        cached_raw = raw
    end
    return cached
end

-- The normalised policy table (see edge_policy_rules.normalise).
function _M.get()
    return current().policy
end

-- init.lua's cve_patterns without the targets the dashboard disabled.
function _M.cve_patterns()
    return current().cve_patterns
end

-- init.lua's vulnerable plugin directories without the disabled ones.
function _M.plugins()
    return current().plugins
end

-- Mirror step for init_worker.lua's 5 s timer: copy the Redis document into
-- the shared dict (or drop it when the key is gone, falling back to the
-- defaults). A failed read keeps the last copy, so a Redis hiccup doesn't
-- silently revert the edge to the defaults. `red` is an open connection
-- from _G.redis_pool.
function _M.mirror(red, dict)
    if not red or not dict then return end
    local raw, err = red:get(_M.REDIS_KEY)
    if raw == ngx.null then
        dict:delete(_M.DICT_KEY)
    elseif type(raw) == "string" then
        dict:set(_M.DICT_KEY, raw)
    elseif err then
        ngx.log(ngx.WARN, "[EDGE POLICY] Could not read ", _M.REDIS_KEY, ", keeping the last copy: ", err)
    end
end

return _M
