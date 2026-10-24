-- test_maintenance.lua - Standalone unit tests for maintenance.lua
--
-- Runs under a plain `lua` interpreter (no OpenResty/ngx required), since
-- maintenance.lua has no ngx.* or _G.* dependency by design.
--
-- Usage:
--   cd ids/reverse_proxy_enhanced/lua/tests
--   lua test_maintenance.lua

package.path = "../?.lua;" .. package.path
local maint = require "maintenance"

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

print("== should_serve_maintenance() ==")
do
    check("flag '1' -> on", maint.should_serve_maintenance("1") == true)
    check("flag '0' -> off (fails open)", maint.should_serve_maintenance("0") == false)
    check("nil flag -> off (expired/never set fails open)",
          maint.should_serve_maintenance(nil) == false)
    check("empty flag -> off", maint.should_serve_maintenance("") == false)
    check("other value -> off", maint.should_serve_maintenance("true") == false)
end

print("== page_html() ==")
do
    local html = maint.page_html(120)
    check("returns a doctype document", html:find("<!doctype html>", 1, true) ~= nil)
    check("has a refresh meta with the retry value",
          html:find("content=\"120\"", 1, true) ~= nil)
    check("mentions minutes to wait", html:find("2 minutes", 1, true) ~= nil)
    check("names no software (deception posture)",
          html:lower():find("wordpress", 1, true) == nil and
          html:lower():find("woocommerce", 1, true) == nil)

    local defaulted = maint.page_html(nil)
    check("nil retry falls back to RETRY_AFTER",
          defaulted:find("content=\"" .. maint.RETRY_AFTER .. "\"", 1, true) ~= nil)

    local shortish = maint.page_html(30)
    check("sub-minute retry rounds up to '1 minute' (singular)",
          shortish:find("1 minute.", 1, true) ~= nil and
          shortish:find("1 minutes", 1, true) == nil)

    local nonNumeric = maint.page_html("banana")
    check("non-numeric retry falls back without erroring",
          nonNumeric:find("content=\"" .. maint.RETRY_AFTER .. "\"", 1, true) ~= nil)
end

print(string.format("%d passed, %d failed", passed, failed))
os.exit(failed == 0 and 0 or 1)
