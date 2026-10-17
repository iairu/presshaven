-- test_suspicious_patterns.lua - the generic Layer-1 list (pattern_rules.SUSPICIOUS_PATTERNS)
-- together with the Layer-2 checks of analyze_uri_patterns().
--
-- The shop's own traffic must score 0 (it once scored +65 on a WooCommerce
-- Store API call because "." and "-" acted as wildcards), and real attack
-- syntax and known CVE parameters must still match.
--
-- Usage:
--   cd ids/reverse_proxy_enhanced/lua/tests
--   lua test_suspicious_patterns.lua

package.path = "../?.lua;" .. package.path
local rules = require "pattern_rules"
local LIST = rules.SUSPICIOUS_PATTERNS

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

local function score(uri)
    return rules.analyze_uri_patterns(uri, LIST, 1000)
end

local function has(uri, name)
    for _, p in ipairs(score(uri).patterns) do
        if p == name then return true end
    end
    return false
end

print("== the shop's own requests score 0 ==")
do
    local clean = {
        -- WooCommerce Store API, as the Segmentation Validation page and the shop's blocks call it
        "/wp-json/wc/store/v1/products?per_page=100&slug=barista-apron,ceramic-pour-over-dripper,"
            .. "coffee-lover-gift-box,pour-over-starter-kit,stainless-milk-pitcher",
        "/wp-json/wc/store/v1/cart",
        "/wp-json/wc/store/v1/products?page=2",          -- "page" is a parameter here, but see below
        "/wp-content/uploads/2026/10/pour-over-starter-kit-300x300.jpg",
        "/wp-content/uploads/2019/01/hoodie-with-zipper-2-14-300x300.jpg",
        "/wp-includes/css/dist/base-styles/admin-schemes.min.css?ver=7.1.2",
        "/product/glass-french-press/",
        "/product-category/coffee/?orderby=price",
        "/?s=gold+mug",
        "/?s=seven+events",
        "/?s=sleepy+owl+tools",
        "/?add-to-cart=136&quantity=1",
        "/shipping-returns/",
        "/wp-login.php?redirect_to=https://localhost/wp-admin/&reauth=1",
    }
    for _, uri in ipairs(clean) do
        local r = score(uri)
        if uri:find("?page=", 1, true) then
            -- a top-level ?page= is still a page-inclusion signal on its own; only
            -- per_page= and friends must not match it
            check("only page= matches: " .. uri, #r.patterns == 1 and r.patterns[1] == "page=")
        else
            check("scores 0: " .. uri:sub(1, 70) .. "  [" .. table.concat(r.patterns, ",") .. "]",
                  r.score == 0)
        end
    end
end

print("== what used to match by accident no longer does ==")
do
    check("per_page= is not the page= parameter", not has("/x?per_page=100", "page="))
    check("'starter' is not a .tar file", not has("/pour-over-starter-kit/", ".tar"))
    check("'gold' is not a .old file", not has("/product/gold-mug/", ".old"))
    check("store/v1...=100 is not OR 1=1", not has("/wp-json/wc/store/v1/products?per_page=100", "or.*1.*=.*1"))
    check("/admin-schemes.css is not an /admin probe", not has("/css/admin-schemes.css", "/admin"))
    check("'alerts' is not alert(", not has("/?s=price+alerts", "alert"))
    check("'tools' is not ;ls", score("/a;b/tools").score == 0)
end

print("== attack syntax still matches ==")
do
    check("UNION SELECT", has("/?id=1'%20UNION%20SELECT%20user_login,user_pass%20FROM%20wp_users--", "union.*select"))
    check("OR '1'='1", has("/?s=1'%20OR%20'1'='1", "or.*1.*=.*1"))
    check("OR 1=1", has("/?id=1 or 1=1", "or.*1.*=.*1"))
    check("SLEEP(", has("/?s=1'%20AND%20SLEEP(1)--", "sleep"))
    check("BENCHMARK(", has("/?s=benchmark(1000000,md5(1))", "benchmark"))
    check("alert(", has("/?s=<script>alert(1)</script>", "alert"))
    check("<script", has("/?s=<script>", "<script"))
    check(";ls", has("/?cmd=x;ls -la", ";ls"))
    check("|nc", has("/?x=a|nc 10.0.0.1 4444", "|nc"))
    check("../ traversal", has("/?file=../../etc/passwd", "../"))
    check(".tar at the end of a path", has("/backup.tar", ".tar"))
    check(".tar.gz", has("/site.tar.gz", ".gz"))
    check(".env", has("/.env", ".env"))
    check(".sql in a segment", has("/dump.sql/", ".sql"))
    check("/admin probe", has("/admin", "/admin"))
    check("/admin/ probe", has("/admin/login", "/admin"))
    check("?page= parameter", has("/?page=advanced-form-integration-log", "page="))
    check("&page= parameter", has("/?x=1&page=../x", "page="))
    check("?author= enumeration", has("/?author=1", "author="))
end

print("== known CVE parameters (several never matched before) ==")
do
    check("CVE-2025-2266 cwmpUpdateOptions (mixed case)",
          has("/?action=cwmpUpdateOptions&option=default_role&value=administrator", "cwmpupdateoptions"))
    check("CVE-2025-4403 dnd-wc-upload-file", has("/?action=dnd-wc-upload-file&name=shell.php", "dnd-wc-upload-file"))
    check("CVE-2024-50508 file[path]", has("/?action=wordpress_file_upload&file[path]=../x", "file[path]"))
    check("CVE-2025-47577 mwb_wgm_preview_mail", has("/?action=mwb_wgm_preview_mail&attachment=shell.php", "mwb_wgm_preview_mail"))
    check("CVE-2024-2387 integration_id", has("/?page=afi&integration_id=1", "integration_id="))
    check("wp-config- backups", has("/wp-config-backup.php", "wp-config-"))
end

print("== SQLi presets keep enough score to divert on the URI alone ==")
do
    local presets = {
        "/wp-admin/admin-ajax.php?action=um_get_members&directory_id=1'%20UNION%20SELECT%20user_login,user_pass%20FROM%20wp_users--%20-",
        "/wp-content/plugins/wp-automatic/inc/csv.php?q=1'%20UNION%20SELECT%20user_login,user_pass%20FROM%20wp_users--%20-",
        "/?page=advanced-form-integration-log&integration_id=1'%20UNION%20SELECT%20user_login,user_pass%20FROM%20wp_users--%20-",
    }
    for _, uri in ipairs(presets) do
        check(">= 80: " .. uri:sub(1, 60), score(uri).score >= 80)
    end
end

print(string.format("%d passed, %d failed", passed, failed))
os.exit(failed == 0 and 0 or 1)
