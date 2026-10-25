-- test_body_guard_rules.lua - Standalone unit tests
--
-- Runs under a plain `lua` interpreter (no OpenResty/ngx required), since
-- body_guard_rules.lua has no ngx.* dependency by design.
--
-- Usage:
--   cd ids/reverse_proxy_enhanced/lua/tests
--   lua test_body_guard_rules.lua

package.path = "../?.lua;" .. package.path
local rules = require "body_guard_rules"

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

-- Build a multipart body from { {name=, filename=, value=}, ... }
local function multipart(boundary, parts, eol)
    eol = eol or "\r\n"
    local out = {}
    for _, p in ipairs(parts) do
        out[#out + 1] = "--" .. boundary .. eol
        local cd = 'Content-Disposition: form-data; name="' .. p.name .. '"'
        if p.filename then cd = cd .. '; filename="' .. p.filename .. '"' end
        out[#out + 1] = cd .. eol
        if p.filename then out[#out + 1] = "Content-Type: application/octet-stream" .. eol end
        out[#out + 1] = eol .. (p.value or "") .. eol
    end
    out[#out + 1] = "--" .. boundary .. "--" .. eol
    return table.concat(out)
end

local B = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
local CT = "multipart/form-data; boundary=" .. B

local function inspect_mp(parts, ct, eol)
    local body = multipart(B, parts, eol)
    return rules.inspect({ content_type = ct or CT, body = body, body_size = #body })
end

print("== check_content_encoding() ==")
do
    check("absent passes", rules.check_content_encoding(nil) == nil)
    check("identity passes", rules.check_content_encoding(" Identity ") == nil)
    check("br flagged", rules.check_content_encoding("br") == "request_content_encoding")
    check("gzip flagged", rules.check_content_encoding("gzip") == "request_content_encoding")
    check("repeated header flagged", rules.check_content_encoding({ "identity", "br" }) == "content_encoding_repeated")
end

print("== parse_boundary() ==")
do
    check("browser boundary", rules.parse_boundary(CT) == B)
    check("quoted boundary", rules.parse_boundary('multipart/form-data; boundary="a b"') == "a b")
    check("curl boundary", rules.parse_boundary("multipart/form-data; boundary=------------------------d74496d66958873e")
        == "------------------------d74496d66958873e")
    local _, r = rules.parse_boundary("multipart/form-data")
    check("missing boundary flagged", r == "multipart_without_boundary")
    _, r = rules.parse_boundary("multipart/form-data; boundary=a; boundary=b")
    check("repeated boundary flagged", r == "multipart_boundary_repeated")
    _, r = rules.parse_boundary("multipart/form-data; boundary=" .. string.rep("x", 71))
    check("71-char boundary flagged", r == "multipart_boundary_invalid")
    _, r = rules.parse_boundary("multipart/form-data; boundary=ab\1cd")
    check("control byte in boundary flagged", r == "multipart_boundary_invalid")
end

print("== check_field_name() ==")
do
    check("plain name passes", rules.check_field_name("billing_email") == nil)
    check("WooCommerce variation name passes", rules.check_field_name("variable_regular_price[0]") == nil)
    check("attribute array passes", rules.check_field_name("attribute_values[0][]") == nil)
    check("8 levels pass", rules.check_field_name("a" .. string.rep("[x]", 8)) == nil)
    check("9 levels flagged", rules.check_field_name("a" .. string.rep("[x]", 9)) == "field_nesting_too_deep")
    check("upload-progress name flagged", rules.check_field_name("PHP_SESSION_UPLOAD_PROGRESS") == "upload_progress_field")
    check("upload-progress with dot mangling flagged", rules.check_field_name("PHP.SESSION UPLOAD.PROGRESS") == "upload_progress_field")
    check("PHPSESSID flagged", rules.check_field_name("phpsessid") == "upload_progress_field")
    check("NUL in name flagged", rules.check_field_name("a\0b") == "control_bytes_in_name")
    check("very long name flagged", rules.check_field_name(string.rep("a", 300)) == "field_name_too_long")
end

print("== check_filename() ==")
do
    check("photo passes", rules.check_filename("photo 1.jpg") == nil)
    check("php open tag flagged", rules.check_filename("x<?php system($_GET[1]);?>.jpg") == "php_code_in_filename")
    check("short echo tag flagged", rules.check_filename("<?=`id`?>.png") == "php_code_in_filename")
    check("serialized object flagged", rules.check_filename('a|O:8:"stdClass":0:{}') == "serialized_object_in_filename")
end

print("== header_params() ==")
do
    local h = '\r\nContent-Disposition: form-data; name="a"; filename="b.txt"'
    local names = rules._header_params(h, "name")
    check("name does not match tail of filename", #names == 1 and names[1] == "a")
    check("filename found", rules._header_params(h, "filename")[1] == "b.txt")
    local two = rules._header_params('\r\nContent-Disposition: form-data; name="ok"; name="PHP_SESSION_UPLOAD_PROGRESS"', "name")
    check("both of two name= params returned", #two == 2)
    check("bare and single-quoted values", rules._header_params("; name=bare; NAME='sq'", "name")[2] == "sq")
end

print("== inspect(): multipart ==")
do
    local media = inspect_mp({
        { name = "name", value = "photo.jpg" },
        { name = "action", value = "upload-attachment" },
        { name = "_wpnonce", value = "abc123" },
        { name = "async-upload", filename = "photo.jpg", value = "\255\216\255\224binary" },
    })
    check("WordPress media upload passes", media.action == "pass")

    local lf = inspect_mp({ { name = "a", value = "1" } }, nil, "\n")
    check("bare-LF multipart passes", lf.action == "pass")

    local prog = inspect_mp({
        { name = "PHP_SESSION_UPLOAD_PROGRESS", value = "x" },
        { name = "file", filename = "a.bin", value = "zz" },
    })
    check("upload-progress part quarantined", prog.action == "quarantine" and prog.reason == "upload_progress_field")

    local deep = inspect_mp({ { name = "a" .. string.rep("[a]", 40), value = "1" } })
    check("deeply nested part quarantined", deep.action == "quarantine" and deep.reason == "field_nesting_too_deep")

    local fname = inspect_mp({ { name = "f", filename = "<?php phpinfo();?>", value = "" } })
    check("php in filename quarantined", fname.action == "quarantine" and fname.reason == "php_code_in_filename")

    local many = {}
    for i = 1, 1201 do many[i] = { name = "f" .. i, value = "1" } end
    local r = inspect_mp(many)
    check("1201 parts quarantined", r.action == "quarantine" and r.reason == "too_many_parts")

    local bad = "--" .. B .. "\r\nContent-Disposition: form-data; name=\"a\""
    r = rules.inspect({ content_type = CT, body = bad, body_size = #bad })
    check("unterminated part header quarantined", r.action == "quarantine" and r.reason == "unterminated_part_header")

    r = rules.inspect({ content_type = "multipart/form-data", body = "x", body_size = 1 })
    check("multipart without boundary quarantined", r.action == "quarantine")

    r = rules.inspect({ content_type = CT, body = nil, body_size = 17 * 1024 * 1024 })
    check("oversized multipart quarantined", r.action == "quarantine" and r.reason == "body_too_large_to_inspect")

    r = rules.inspect({ content_type = "Multipart/Form-Data; boundary=" .. B,
                        body = multipart(B, { { name = "phpsessid", value = "1" } }), body_size = 100 })
    check("content-type case doesn't evade", r.action == "quarantine")
end

print("== inspect(): urlencoded, query, encoding ==")
do
    local body = "billing_email=a%40b.c&payment_method=stripe&woocommerce-process-checkout-nonce=abc"
    local r = rules.inspect({ content_type = "application/x-www-form-urlencoded; charset=UTF-8", body = body, body_size = #body })
    check("checkout post passes", r.action == "pass")

    body = "a" .. string.rep("%5Bx%5D", 20) .. "=1"
    r = rules.inspect({ content_type = "application/x-www-form-urlencoded", body = body, body_size = #body })
    check("percent-encoded nesting quarantined", r.action == "quarantine" and r.reason == "field_nesting_too_deep")

    r = rules.inspect({ query = "s=coffee&paged=2" })
    check("normal query passes", r.action == "pass")
    r = rules.inspect({ query = "x" .. string.rep("[a]", 20) .. "=1" })
    check("nested query quarantined and stripped", r.action == "quarantine" and r.strip_query == true
        and r.reason == "query_field_nesting_too_deep")

    r = rules.inspect({ content_type = "application/json", content_encoding = "br", body = "\27\0", body_size = 2 })
    check("brotli body quarantined", r.action == "quarantine" and r.reason == "request_content_encoding")

    r = rules.inspect({ content_type = "application/json", body = '{"a":1}', body_size = 7 })
    check("JSON body passes (PHP doesn't parse it into $_POST)", r.action == "pass")

    r = rules.inspect({})
    check("bodyless GET passes", r.action == "pass")
end

print(string.format("\n%d passed, %d failed", passed, failed))
if failed > 0 then os.exit(1) end
