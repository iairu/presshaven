-- test_edge_policy.lua - Tests for edge_policy.lua (the ngx glue): the
-- Redis -> shared dict mirror and the per-worker decoded cache, against
-- in-memory stubs of ngx.shared, a Redis connection and cjson.
--
-- Usage:
--   cd ids/reverse_proxy_enhanced/lua/tests
--   lua test_edge_policy.lua

package.path = "../?.lua;" .. package.path

local SCORE_POLICY = '{"targets":{"mode":"score"}}'
package.loaded["cjson"] = {
    decode = function(s)
        if s ~= SCORE_POLICY then error("bad json") end
        return { targets = { mode = "score", disabled_plugins = { "bricks" },
                             disabled_cves = { "CVE-2024-25600" } } }
    end,
}

local store = {}
local dict = {
    set = function(_, k, v) store[k] = v end,
    delete = function(_, k) store[k] = nil end,
    get = function(_, k) return store[k] end,
}
ngx = { null = {}, WARN = 5, ERR = 4, log = function() end, shared = { threat_intel = dict } }
_G.config = { vulnerability = { plugins = { "bricks", "cwmp" },
                                cve_patterns = { ["CVE-2024-25600"] = "render_element" } } }

local ep = require "edge_policy"

local passed, failed = 0, 0
local function check(name, condition)
    if condition then
        passed = passed + 1
        print("  [PASS] " .. name)
    else
        failed = failed + 1
        print("  [FAIL] " .. name)
    end
end
local function red(value, err) return { get = function() return value, err end } end

print("== mirror() + get() ==")
check("no policy -> defaults", ep.get().targets.mode == "direct" and #ep.plugins() == 2)

ep.mirror(red(SCORE_POLICY), dict)
check("policy copied into the shared dict", store[ep.DICT_KEY] == SCORE_POLICY)
check("decoded mode picked up", ep.get().targets.mode == "score")
check("disabled plugin filtered", #ep.plugins() == 1 and ep.plugins()[1] == "cwmp")
check("disabled CVE filtered", next(ep.cve_patterns()) == nil)
check("config tables untouched", #_G.config.vulnerability.plugins == 2)

ep.mirror(red(nil, "timeout"), dict)
check("Redis error keeps the last copy", ep.get().targets.mode == "score")

ep.mirror(red(ngx.null), dict)
check("deleted key -> shared dict cleared", store[ep.DICT_KEY] == nil)
check("deleted key -> defaults", ep.get().targets.mode == "direct" and #ep.plugins() == 2)

ep.mirror(red("{garbage"), dict)
check("unparseable policy -> defaults", ep.get().targets.mode == "direct")

print(string.format("%d passed, %d failed", passed, failed))
os.exit(failed == 0 and 0 or 1)
