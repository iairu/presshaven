-- body_guard.lua - Request body guard (PHP2Shell / Node2Shell interim layer)
--
-- Runs from the 443 server's rewrite_by_lua_block, i.e. before the main
-- access_by_lua_block and for EVERY location (static assets, wp-json, the
-- vulnerable-plugin fast path, admin-ajax) -- none of them define their own
-- rewrite_by_lua, so the server-level one is always inherited. That matters:
-- a request for a nonexistent .css is still rewritten to index.php by
-- WordPress behind us, and PHP parses its body like any other.
--
-- On a body shape body_guard_rules.lua flags, the request is QUARANTINED,
-- not rejected: the body and its framing headers are dropped, the method
-- becomes GET, and the request continues through normal routing. The
-- backend never sees the hostile bytes, and the attacker gets an ordinary
-- page instead of a 4xx that tells them the guard exists and what it
-- matched. The bytes are kept as a sha256 in the security event for the SIEM.
--
-- Config: _G.config.body_guard (init.lua), BODY_GUARD_MODE env var.

local rules = require "body_guard_rules"

local _M = {}

-- Read the buffered request body: in memory if it fit
-- client_body_buffer_size, else from nginx's temp file. Returns
-- (data|nil, size). data is nil when the body is larger than max_bytes.
local function read_body(max_bytes)
    ngx.req.read_body()
    local data = ngx.req.get_body_data()
    if data then return data, #data end
    local path = ngx.req.get_body_file()
    if not path then return nil, 0 end
    local f, err = io.open(path, "rb")
    if not f then
        ngx.log(ngx.ERR, "[BODY_GUARD] cannot open body file ", path, ": ", err)
        return nil, tonumber(ngx.var.http_content_length) or max_bytes + 1
    end
    local size = f:seek("end")
    if size > max_bytes then
        f:close()
        return nil, size
    end
    f:seek("set", 0)
    data = f:read("*a")
    f:close()
    return data, size
end

local function sha256_hex(data)
    if not data or data == "" then return nil end
    local sha256 = require("resty.sha256"):new()
    sha256:update(data)
    return require("resty.string").to_hex(sha256:final())
end

-- Drop the body and everything that frames it, so the backend parses nothing.
local function strip_body()
    ngx.req.set_method(ngx.HTTP_GET)
    ngx.req.clear_header("Content-Type")
    ngx.req.clear_header("Content-Encoding")
    ngx.req.clear_header("Transfer-Encoding")
    ngx.req.set_body_data("")
end

-- Content-Encoding and query-string findings are weaker evidence (a
-- misbehaving client library can send either); parser-shaped bodies are
-- not something any browser or shop integration produces.
local function score_for(cfg, verdict)
    if verdict.reason == "request_content_encoding" or verdict.strip_query then
        return cfg.soft_score
    end
    return cfg.score
end

local function run(cfg)
    local headers = ngx.req.get_headers()
    local method = ngx.req.get_method()
    local data, size = read_body(cfg.limits.max_scan_bytes)
    local req = {
        content_type = headers["content-type"],
        content_encoding = headers["content-encoding"],
        body = data,
        body_size = size,
        query = ngx.var.args,
    }
    local verdict = rules.inspect(req, cfg.limits)
    if verdict.action ~= "quarantine" then return end

    -- inspect() reports the query string first and stops there; check the
    -- body on its own too, so a bad query can't shadow a bad body.
    local body_verdict
    if verdict.strip_query then
        req.query = nil
        body_verdict = rules.inspect(req, cfg.limits)
        if body_verdict.action ~= "quarantine" then body_verdict = nil end
    else
        body_verdict, verdict = verdict, nil
    end

    local score = math.max(verdict and score_for(cfg, verdict) or 0,
                           body_verdict and score_for(cfg, body_verdict) or 0)
    local reason = (body_verdict or verdict).reason
    if verdict and body_verdict then reason = verdict.reason .. "+" .. body_verdict.reason end
    local enforce = cfg.mode == "enforce"

    if enforce then
        if verdict then ngx.req.set_uri_args({}) end
        if body_verdict then strip_body() end
        ngx.ctx.body_guard = { reason = reason, score = score }
    end

    _G.utils.log_security_event("parser_exploit_quarantined", {
        ip = ngx.var.remote_addr,
        uri = ngx.var.uri,
        method = method,
        reason = reason,
        mode = cfg.mode,
        score = enforce and score or 0,
        body_bytes = size,
        body_sha256 = sha256_hex(data),
        content_type = string.sub(headers["content-type"] or "", 1, 120),
    })
    ngx.log(ngx.WARN, "[BODY_GUARD] ", enforce and "quarantined" or "observed (not enforced)",
        " reason=", reason, " ip=", ngx.var.remote_addr, " uri=", ngx.var.uri,
        " bytes=", size)
end

-- Entry point. Fails open: a bug here must not take the shop down, so any
-- error is logged and the request continues untouched -- the PHP-side
-- mitigations in images/wordpress_hardened still apply behind us.
function _M.check()
    local cfg = _G.config and _G.config.body_guard
    if not cfg or cfg.mode == "off" then return end
    local ok, err = pcall(run, cfg)
    if not ok then
        ngx.log(ngx.ERR, "[BODY_GUARD] check failed, passing request through: ", err)
    end
end

return _M
