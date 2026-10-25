-- body_guard_rules.lua - Pure request-body structure checks used by body_guard.lua
--
-- Same split as the other _rules.lua modules: no ngx.* dependency, plain-`lua`
-- testable (tests/test_body_guard_rules.lua). body_guard.lua is the adapter:
-- it reads the buffered body, calls these, and quarantines the request.
--
-- Why this exists: PHP2Shell (CVE-2026-109618 / -109619, "Black October")
-- fires inside PHP's own request-body parser, before WordPress or any plugin
-- runs, so nothing that looks at URLs or application behaviour can stop it.
-- These checks describe what a legitimate storefront body looks like and
-- flag the shapes that stress PHP's parser instead -- independent of the CVE,
-- so the next parser bug of the same kind is covered too.
--
-- Every check errs towards "quarantine" on anything PHP might read
-- differently from us (odd boundaries, part headers without an end), since a
-- parser differential is exactly how a body guard gets evaded.

local _M = {}

_M.DEFAULT_LIMITS = {
    -- PHP stops building $_POST at max_input_vars (1000); more parts than
    -- that are never legitimate, and product edit screens stay well below.
    max_parts = 1200,
    max_name_len = 256,
    -- PHP's own max_input_nesting_level is lowered to 16 in the WordPress
    -- image; 8 is still several times what any shop form sends.
    max_depth = 8,
    -- Bodies the guard won't read in full. Apache rejects anything over
    -- 16M (LimitRequestBody), so nothing legitimate is larger anyway.
    max_scan_bytes = 16 * 1024 * 1024,
}

-- Field names that only matter to PHP's session upload-progress feature,
-- which WordPress never uses: the CVE-2026-109619 path.
local POISON_NAMES = {
    php_session_upload_progress = true,
    phpsessid = true,
}

-- ---------------------------------------------------------------------------
-- check_content_encoding(value) -> reason | nil
--
-- Browsers never compress request bodies, and nothing behind this proxy is
-- meant to decompress one: a compressed body is either a decompression
-- exploit (Node2Shell / CVE-2026-111497 for Brotli) or a decompression bomb.
-- ---------------------------------------------------------------------------
function _M.check_content_encoding(value)
    if value == nil then return nil end
    if type(value) == "table" then return "content_encoding_repeated" end
    local v = string.lower(value):gsub("^%s+", ""):gsub("%s+$", "")
    if v == "" or v == "identity" then return nil end
    return "request_content_encoding"
end

-- ---------------------------------------------------------------------------
-- parse_boundary(content_type) -> boundary | nil, reason | nil
--
-- RFC 2046 boundaries are 1-70 characters from a fixed set. Anything else,
-- or more than one boundary parameter, is a body PHP and this module might
-- split differently -- so it's reported rather than guessed at.
-- ---------------------------------------------------------------------------
function _M.parse_boundary(content_type)
    local ct = content_type or ""
    local lower = string.lower(ct)
    local first = string.find(lower, "boundary%s*=")
    if not first then return nil, "multipart_without_boundary" end
    if string.find(lower, "boundary%s*=", first + 1) then
        return nil, "multipart_boundary_repeated"
    end
    local _, eq_end = string.find(lower, "boundary%s*=%s*", first)
    local rest = string.sub(ct, eq_end + 1)
    local value = string.match(rest, '^"([^"]*)"') or string.match(rest, "^([^;,%s]*)")
    if not value or value == "" then return nil, "multipart_without_boundary" end
    if #value > 70 or string.find(value, "[^%w'()+_,%-./:=? ]") then
        return nil, "multipart_boundary_invalid"
    end
    return value, nil
end

-- Number of "[" in a (decoded) field name: PHP's array nesting depth.
local function depth(name)
    local _, n = string.gsub(name, "%[", "")
    return n
end

-- ---------------------------------------------------------------------------
-- check_field_name(name, limits) -> reason | nil
-- ---------------------------------------------------------------------------
function _M.check_field_name(name, limits)
    limits = limits or _M.DEFAULT_LIMITS
    local base = string.lower(string.match(name, "^[^%[]*") or "")
    -- PHP turns spaces and dots in field names into underscores.
    base = string.gsub(base, "[ %.]", "_")
    if POISON_NAMES[base] then return "upload_progress_field" end
    if #name > limits.max_name_len then return "field_name_too_long" end
    if depth(name) > limits.max_depth then return "field_nesting_too_deep" end
    if string.find(name, "[%z\1-\31\127]") then return "control_bytes_in_name" end
    return nil
end

-- ---------------------------------------------------------------------------
-- check_filename(filename) -> reason | nil
-- ---------------------------------------------------------------------------
function _M.check_filename(filename)
    local f = string.lower(filename)
    if string.find(f, "<?php", 1, true) or string.find(f, "<?=", 1, true) then
        return "php_code_in_filename"
    end
    -- A PHP serialized object (O:<len>:"Class") in a name field.
    if string.find(filename, "|O:", 1, true) or string.find(filename, "^O:%d+:\"") then
        return "serialized_object_in_filename"
    end
    if string.find(filename, "[%z\1-\31\127]") then return "control_bytes_in_filename" end
    return nil
end

-- All values of `param=` in a part header (quoted, single-quoted or bare).
-- Every occurrence is returned: PHP and this module must not disagree about
-- which of two `name=` parameters counts.
local function header_params(header, param)
    local values = {}
    local lower = string.lower(header)
    local pat = "()" .. param .. "%s*=%s*()"
    for start, vpos in string.gmatch(lower, pat) do
        local prev = start > 1 and string.sub(lower, start - 1, start - 1) or ";"
        -- "name" must not match the tail of "filename" (or any other word).
        if not string.find(prev, "[%w_%-*]") then
            local q = string.sub(header, vpos, vpos)
            local value
            if q == '"' or q == "'" then
                value = string.match(header, "^" .. q .. "([^" .. q .. "]*)", vpos)
            else
                value = string.match(header, "^([^;%s]*)", vpos)
            end
            values[#values + 1] = value or ""
        end
    end
    return values
end
_M._header_params = header_params

-- ---------------------------------------------------------------------------
-- scan_multipart(body, boundary, limits) -> { action, reason, parts }
--
-- action is "pass" or "quarantine". Only part HEADERS are inspected; file
-- contents are never interpreted. The boundary is searched for anywhere (not
-- only at line starts): a well-formed body never contains it outside a
-- delimiter, so this can only over-count on bodies that are malformed anyway.
-- ---------------------------------------------------------------------------
function _M.scan_multipart(body, boundary, limits)
    limits = limits or _M.DEFAULT_LIMITS
    local delim = "--" .. boundary
    local parts, pos = 0, 1
    while true do
        local s, e = string.find(body, delim, pos, true)
        if not s then break end
        -- Closing delimiter: "--boundary--"
        if string.sub(body, e + 1, e + 2) == "--" then break end
        parts = parts + 1
        if parts > limits.max_parts then
            return { action = "quarantine", reason = "too_many_parts", parts = parts }
        end
        -- PHP accepts both CRLF and bare LF line endings in part headers.
        local h1 = string.find(body, "\r\n\r\n", e + 1, true)
        local h2 = string.find(body, "\n\n", e + 1, true)
        local hdr_end, sep_len
        if h1 and (not h2 or h1 <= h2) then hdr_end, sep_len = h1, 4
        elseif h2 then hdr_end, sep_len = h2, 2 end
        if not hdr_end then
            return { action = "quarantine", reason = "unterminated_part_header", parts = parts }
        end
        local header = string.sub(body, e + 1, hdr_end - 1)
        if string.find(header, "%z") then
            return { action = "quarantine", reason = "control_bytes_in_part_header", parts = parts }
        end
        for _, name in ipairs(header_params(header, "name")) do
            local reason = _M.check_field_name(name, limits)
            if reason then return { action = "quarantine", reason = reason, parts = parts } end
        end
        for _, fname in ipairs(header_params(header, "filename")) do
            local reason = _M.check_filename(fname)
            if reason then return { action = "quarantine", reason = reason, parts = parts } end
        end
        pos = hdr_end + sep_len
    end
    return { action = "pass", reason = nil, parts = parts }
end

-- Percent-decode only the characters that matter for a field name's shape.
local function decode_name(name)
    name = string.gsub(name, "+", " ")
    return (string.gsub(name, "%%(%x%x)", function(h)
        return string.char(tonumber(h, 16))
    end))
end

-- ---------------------------------------------------------------------------
-- scan_urlencoded(data, limits) -> { action, reason, fields }
--
-- For application/x-www-form-urlencoded bodies and query strings: PHP builds
-- the same nested arrays from these as from multipart field names.
-- ---------------------------------------------------------------------------
function _M.scan_urlencoded(data, limits)
    limits = limits or _M.DEFAULT_LIMITS
    local fields = 0
    for pair in string.gmatch(data or "", "[^&;]+") do
        fields = fields + 1
        if fields > limits.max_parts then
            return { action = "quarantine", reason = "too_many_fields", fields = fields }
        end
        local name = decode_name(string.match(pair, "^[^=]*"))
        local reason = _M.check_field_name(name, limits)
        if reason then return { action = "quarantine", reason = reason, fields = fields } end
    end
    return { action = "pass", reason = nil, fields = fields }
end

-- ---------------------------------------------------------------------------
-- body_kind(content_type) -> "multipart" | "urlencoded" | nil
-- ---------------------------------------------------------------------------
function _M.body_kind(content_type)
    local ct = string.lower(content_type or "")
    if string.find(ct, "^%s*multipart/") then return "multipart" end
    if string.find(ct, "^%s*application/x%-www%-form%-urlencoded") then return "urlencoded" end
    return nil
end

-- ---------------------------------------------------------------------------
-- inspect(req, limits) -> verdict
--
-- req = { content_type, content_encoding, body, body_size, query }
-- body may be nil when the request has none or it wasn't read; body_size is
-- the full size even if body is nil (too large to scan).
-- verdict = { action = "pass"|"quarantine", reason, strip_query = bool }
-- ---------------------------------------------------------------------------
function _M.inspect(req, limits)
    limits = limits or _M.DEFAULT_LIMITS

    local q = req.query and req.query ~= "" and _M.scan_urlencoded(req.query, limits)
    if q and q.action == "quarantine" then
        return { action = "quarantine", reason = "query_" .. q.reason, strip_query = true }
    end

    local enc = _M.check_content_encoding(req.content_encoding)
    if enc then return { action = "quarantine", reason = enc } end

    local kind = _M.body_kind(req.content_type)
    if not kind or (req.body_size or 0) == 0 then
        return { action = "pass" }
    end
    if req.body_size > limits.max_scan_bytes or not req.body then
        return { action = "quarantine", reason = "body_too_large_to_inspect" }
    end

    if kind == "multipart" then
        local boundary, reason = _M.parse_boundary(req.content_type)
        if not boundary then return { action = "quarantine", reason = reason } end
        local r = _M.scan_multipart(req.body, boundary, limits)
        return { action = r.action, reason = r.reason }
    end
    local r = _M.scan_urlencoded(req.body, limits)
    return { action = r.action, reason = r.reason }
end

return _M
