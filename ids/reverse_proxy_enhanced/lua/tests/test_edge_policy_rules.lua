-- test_edge_policy_rules.lua - Unit tests for edge_policy_rules.lua
--
-- Usage:
--   cd ids/reverse_proxy_enhanced/lua/tests
--   lua test_edge_policy_rules.lua

package.path = "../?.lua;" .. package.path

local rules = require "edge_policy_rules"

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

print("== normalise() ==")
do
    local p = rules.normalise(nil)
    check("missing policy -> direct mode", p.targets.mode == "direct")
    check("missing policy -> target score 40", p.targets.target_score == 40)
    check("missing policy -> no whitelist signal", p.whitelist.unlisted_score == 0)
    check("missing policy -> nothing disabled", next(p.targets.disabled_cves) == nil
          and next(p.targets.disabled_plugins) == nil)

    p = rules.normalise("not a table")
    check("non-table policy -> defaults", p.targets.mode == "direct")

    p = rules.normalise({
        version = 3,
        targets = { mode = "score", target_score = 25, disabled_cves = { "CVE-1", 7, "" },
                    disabled_plugins = { "bricks" } },
        whitelist = { unlisted_score = 10, entries = {
            { id = "home", match = "exact", path = "/" },
            { id = "admin", match = "prefix", path = "/WP-Admin/" },
            { id = "bad", match = "exact", path = "no-slash" },
            "junk",
        } },
    })
    check("version kept", p.version == 3)
    check("score mode kept", p.targets.mode == "score")
    check("target score kept", p.targets.target_score == 25)
    check("disabled CVE set built", p.targets.disabled_cves["CVE-1"] == true)
    check("non-string disabled ids dropped", p.targets.disabled_cves[7] == nil and p.targets.disabled_cves[""] == nil)
    check("disabled plugin set built", p.targets.disabled_plugins.bricks == true)
    check("unusable entries dropped", #p.whitelist.entries == 2)
    check("entry path lower-cased, prefix slash kept", p.whitelist.entries[2].path == "/wp-admin/")

    p = rules.normalise({ targets = { mode = "yolo", target_score = 500 },
                          whitelist = { unlisted_score = -4 } })
    check("unknown mode falls back to direct", p.targets.mode == "direct")
    check("scores clamped to 0..100", p.targets.target_score == 100 and p.whitelist.unlisted_score == 0)
end

print("== request_path() ==")
do
    check("query string dropped", rules.request_path("/shop/?orderby=price") == "/shop/")
    check("lower-cased", rules.request_path("/WP-LOGIN.PHP") == "/wp-login.php")
    check("percent-decoded", rules.request_path("/wp%2Dlogin.php") == "/wp-login.php")
    check("repeated slashes collapsed", rules.request_path("//wp-login.php") == "/wp-login.php")
    check("dot segments resolved", rules.request_path("/shop/../wp-login.php") == "/wp-login.php")
    check("climbing above root never matches", rules.request_path("/../../etc/passwd") == "/..")
    check("encoded traversal resolved too", rules.request_path("/shop/%2e%2e/wp-config.php") == "/wp-config.php")
    check("empty uri -> root", rules.request_path("") == "/" and rules.request_path(nil) == "/")
end

print("== whitelist_match() ==")
do
    local entries = rules.normalise({ whitelist = { entries = {
        { id = "home", match = "exact", path = "/" },
        { id = "login", match = "exact", path = "/wp-login.php" },
        { id = "shop", match = "prefix", path = "/shop/" },
        { id = "admin", match = "prefix", path = "/wp-admin/" },
    } } }).whitelist.entries
    local function m(uri) return rules.whitelist_match(rules.request_path(uri), entries) end
    check("root matches exact /", m("/?s=hoodie") == "home")
    check("exact path", m("/wp-login.php?action=lostpassword") == "login")
    check("exact ignores a trailing slash", m("/wp-login.php/") == "login")
    check("exact does not match below it", m("/wp-login.php/x") == nil)
    check("prefix matches below it", m("/shop/page/2/") == "shop")
    check("prefix matches its bare form", m("/shop") == "shop")
    check("prefix respects segment boundary", m("/wp-adminer.php") == nil)
    check("unknown path is unlisted", m("/.env") == nil)
    check("traversal out of a prefix is unlisted", m("/shop/../.env") == nil)
end

print("== filter_cve_patterns() / filter_plugins() ==")
do
    local cves = { ["CVE-1"] = "a", ["CVE-2"] = "b" }
    local out = rules.filter_cve_patterns(cves, { ["CVE-1"] = true })
    check("disabled CVE removed", out["CVE-1"] == nil and out["CVE-2"] == "b")
    check("config table untouched", cves["CVE-1"] == "a")
    check("nil disabled set keeps all", rules.filter_cve_patterns(cves, nil)["CVE-1"] == "a")

    local plugins = rules.filter_plugins({ "a", "b", "c" }, { b = true })
    check("disabled plugin removed, order kept", #plugins == 2 and plugins[1] == "a" and plugins[2] == "c")
end

print(string.format("%d passed, %d failed", passed, failed))
os.exit(failed == 0 and 0 or 1)
