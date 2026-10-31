-- pattern_rules.lua - Pure scoring rules used by pattern_analyzer.lua
--
-- PURPOSE:
--   Holds the actual pattern-matching / scoring logic that used to live
--   directly inside pattern_analyzer.lua's functions, factored out so it has
--   no ngx.* dependency and no reliance on _G.config/_G.utils being set up.
--   Every function here takes plain Lua values (strings, tables) as
--   arguments and returns plain Lua tables -- nothing here reads a request
--   header off ngx.req, touches a shared dict, or writes a log line.
--   pattern_analyzer.lua is the adapter: it pulls config out of _G.config,
--   pulls request context out of ngx.var/ngx.req, calls into this module for
--   the actual scoring decision, and does all the I/O (ngx.log,
--   log_security_event, Redis/shared-dict reads for IP reputation and
--   automation timing).
--
--   This mirrors prompt_injection_filter.lua's existing "no ngx.* dependency
--   by design" convention so the same kind of plain-`lua`-interpreter unit
--   tests are possible here -- see tests/test_pattern_rules.lua.
--
-- WHY THIS SPLIT: a pure core is testable without spinning up OpenResty, and
-- makes it obvious at a glance which functions can silently depend on
-- request-scoped globals (ngx.var.*) and which can't -- several bugs found
-- earlier in this codebase (e.g. sophistication_analyzer's lost UA field)
-- came from exactly that kind of implicit, easy-to-miss dependency.

local pattern_utils = require "lua_pattern_utils"

local _M = {}

-- Re-exported for backward compatibility with anything already calling
-- pattern_rules.url_decode() directly (e.g. existing tests); the actual
-- implementation now lives in lua_pattern_utils.lua, shared with
-- router_rules.lua/vulnerability_rules.lua/upload_rules.lua instead of each
-- keeping its own copy.
local url_decode = pattern_utils.url_decode
_M.url_decode = url_decode

-- Re-exported for the same reason: pattern_analyzer.lua's install.php
-- not-yet-installed fast path needs the exact same matcher router_rules.lua
-- uses, so the two can never quietly disagree (see lua_pattern_utils.lua's
-- own comment on this function).
_M.is_install_wizard_uri = pattern_utils.is_install_wizard_uri

-- ---------------------------------------------------------------------------
-- is_static_asset(uri, static_asset_patterns)
--
-- Query-string-stripping kept in sync with router_rules.is_static_asset
-- (the two used to disagree here -- router.lua's stripped "?query" before
-- matching, this one didn't, so "style.css?v=123" was classified as static
-- by one and not the other).
--
-- @param uri                     string       Raw request URI.
-- @param static_asset_patterns   table|nil    List of Lua patterns (from
--                                              _G.config.threat.static_asset_patterns).
-- @return boolean
-- ---------------------------------------------------------------------------
function _M.is_static_asset(uri, static_asset_patterns)
    if not uri then
        return false
    end

    local uri_lower = string.lower(uri)
    local uri_path = uri_lower:match("^([^?]+)") or uri_lower

    if static_asset_patterns then
        for _, pattern in ipairs(static_asset_patterns) do
            if string.find(uri_path, pattern) then
                return true
            end
        end
    end

    return false
end

-- ---------------------------------------------------------------------------
-- Generic Layer-1 signatures (init.lua: threat.suspicious_patterns). A match
-- adds +15. Each entry says HOW it matches, because a bare Lua pattern was
-- the source of both false positives and false negatives:
--   * "." is any character, so ".tar" matched "s-tar-ter-kit" and ".old"
--     matched "g-old"; "page=" matched "per_page=" and "or.*1.*=.*1" matched
--     "st-or-e/v1/products?per_page=100" -- a normal WooCommerce Store API
--     call scored +65, one step short of being diverted;
--   * "-" and "[" are pattern operators, so "dnd-wc-upload-file",
--     "file[path]" and "wp-config-" never matched, and "cwmpUpdateOptions"
--     never met the lower-cased URI.
-- Kinds:
--   plain(s)   -- the literal text anywhere in the URI (lower case);
--   ext(e)     -- a file extension at the end of a path segment;
--   param(n)   -- a query parameter NAME (after "?" or "&");
--   segment(s) -- a whole path segment ("/admin", not "/admin-schemes.css");
--   pat(p)     -- a real Lua pattern, for syntax that needs one.
-- Recon tokens that never matched because of the "-" bug ("/wp-admin/",
-- "/wp-content/", "/wp-includes/", "/wp-login", "wp-login.php") are left out
-- rather than switched on: every admin-ajax, plugin and login request of a
-- normal visitor would start scoring. Same for "redirect_to=", which
-- WordPress puts on every login link.
-- ---------------------------------------------------------------------------
local function plain(s) return { kind = "plain", match = s, name = s } end
local function ext(e) return { kind = "ext", match = e, name = e } end
local function param(n) return { kind = "param", match = n, name = n .. "=" } end
local function segment(s) return { kind = "segment", match = s, name = s } end
local function pat(p, name) return { kind = "pattern", match = p, name = name } end

_M.SUSPICIOUS_PATTERNS = {
    -- WSTG-INPV-01: Directory traversal
    plain("../"), plain("..\\"),

    -- WSTG-INPV-05: SQL injection (real syntax, word boundaries)
    pat("union[^%a].-select[^%a]", "union.*select"),
    pat("['\"%s%)]or%s+['\"]?%w+['\"]?%s*=%s*['\"]?%w", "or.*1.*=.*1"),
    pat("select[^%a].-[^%a]from[^%a]", "select.*from"),
    pat("drop[^%a]+table[^%a]", "drop.*table"),
    pat("insert[^%a]+into[^%a]", "insert.*into"),
    pat("sleep%s*%(", "sleep"),
    pat("benchmark%s*%(", "benchmark"),

    -- WSTG-INPV-02: XSS
    plain("<script"), plain("javascript:"), plain("onerror="), plain("onload="),
    pat("alert%s*%(", "alert"),

    -- WSTG-INPV-12: Command injection
    pat(";%s*cat[%s%+]", ";cat"), pat(";%s*ls[%s%+;&|]", ";ls"), pat(";%s*ls$", ";ls"),
    pat("|%s*nc[%s%+]", "|nc"), pat("&&%s*curl[%s%+]", "&&curl"),

    -- WSTG-INPV-11: File inclusion
    plain("php://"), plain("file://"), plain("data://"),

    -- WSTG-CONF: Sensitive file access
    plain("wp-config.php"), plain("wp-config-"),
    ext(".env"), ext(".bak"), ext(".old"), ext(".backup"), ext(".sql"),
    ext(".tar"), ext(".gz"), ext(".zip"), ext(".htaccess"), ext(".htpasswd"),
    segment("/backup"), plain("readme.html"), plain("install.php"),
    plain("setup-config.php"), plain("phpinfo"), plain("crossdomain.xml"),

    -- WSTG-INFO: Reconnaissance probes
    segment("/admin"), segment("/administrator"), segment("/phpmyadmin"), plain("xmlrpc.php"),

    -- WSTG-IDNT: User enumeration
    param("author"), plain("/wp-json/wp/v2/users"), param("rest_route"),

    -- WSTG-AUTHZ: Privilege escalation (known CVE parameters)
    plain("wcal_action=checkout_link"),   -- CVE-2023-2986
    param("integration_id"),              -- CVE-2024-2387
    plain("cwmpupdateoptions"),           -- CVE-2025-2266
    plain("mwb_wgm_preview_mail"),        -- CVE-2025-47577
    plain("dnd-wc-upload-file"),          -- CVE-2025-4403
    plain("pc_added_uploaded_image"),     -- CVE-2025-10142
    plain("file[path]"),                  -- CVE-2024-50508

    -- WSTG-INPV: Other injection (parameter names)
    param("cmd"), param("template"), param("page"), param("file"), param("redirect"),

    -- WSTG-INPV-15: HTTP splitting
    plain("%0d%0a"),

    -- WSTG-AUTHZ: IDOR parameters
    param("user_id"), param("customer_id"), param("order_id"), param("post_id"),
    plain("context=edit"),

    -- WSTG-ATHN: Authentication attacks
    plain("action=lostpassword"), plain("action=register"),

    -- WSTG-CONF: Cloud / storage
    plain("s3-backup"),

    -- =======================================================================
    -- OWASP CRS-derived generic signatures. These broaden Layer 1 beyond the
    -- WordPress/CVE specifics above to the generic attack classes the ModSecurity
    -- Core Rule Set guards (LFI/RFI, RCE, PHP/Java injection, SSTI, SSRF, XXE,
    -- NoSQL, and deeper SQLi/XSS). All are generic (kind=generic, so enabled by
    -- default) and add +15 on a match. URI-only tokens are chosen to keep false
    -- positives on normal shop traffic low; the edge whitelist bypasses these
    -- for legitimate paths.
    -- =======================================================================

    -- WSTG-INPV-11 / CRS 930: Local File Inclusion (sensitive OS files)
    plain("etc/passwd"), plain("etc/shadow"), plain("etc/hosts"),
    plain("proc/self/environ"), plain("win.ini"), plain("boot.ini"),

    -- WSTG-INPV-11 / CRS 931: Remote File Inclusion (PHP stream wrappers)
    plain("expect://"), plain("zip://"), plain("phar://"), plain("glob://"),

    -- WSTG-INPV-12 / CRS 932: Remote Command Execution (commands and operators)
    pat(";%s*id[%s%+;&|$]", "cmd-id"), pat(";%s*id$", "cmd-id-eol"),
    pat(";%s*whoami", "cmd-whoami"),
    pat(";%s*uname", "cmd-uname"), pat("&&%s*wget[%s%+]", "cmd-wget"),
    plain("/bin/bash"), plain("/bin/sh"), pat("nc%s+%-e", "cmd-nc-exec"),
    pat("bash%s+%-i", "cmd-bash-reverse"), pat("python%s+%-c", "cmd-python"),
    pat("perl%s+%-e", "cmd-perl"), pat("%$%(%s*%a", "cmd-subshell"),

    -- WSTG-INPV-11 / CRS 933: PHP injection (dangerous functions, directives)
    pat("base64_decode%s*%(", "php-base64-decode"), pat("system%s*%(", "php-system"),
    pat("exec%s*%(", "php-exec"), pat("passthru%s*%(", "php-passthru"),
    pat("shell_exec%s*%(", "php-shell-exec"), pat("proc_open%s*%(", "php-proc-open"),
    pat("call_user_func", "php-call-user-func"),
    plain("allow_url_include"), plain("auto_prepend_file"),

    -- WSTG-INPV-12 / CRS 944: Java attacks (Log4Shell JNDI, OGNL, runtime exec)
    plain("jndi:ldap"), plain("jndi:rmi"), plain("jndi:dns"),
    pat("%${jndi", "jndi-lookup"), plain("runtime.exec"), plain("java.lang.runtime"),
    plain("getruntime"),

    -- WSTG-INPV-18 / CRS: Server-Side Template Injection
    pat("%${{", "ssti-dollar-braces"), pat("{{%s*%d", "ssti-mustache-expr"),
    pat("<%%=", "ssti-erb"),

    -- WSTG-INPV-19 / CRS 934: SSRF, cloud metadata and prototype pollution
    plain("169.254.169.254"), plain("latest/meta-data"),
    plain("metadata.google.internal"), plain("__proto__"), plain("constructor.prototype"),

    -- WSTG-INPV-07: XML external entity (XXE)
    plain("<!entity"), plain("<!doctype"),

    -- WSTG-INPV-06: NoSQL injection operators
    plain("[$ne]"), plain("[$gt]"), plain("[$where]"),

    -- WSTG-INPV-05 / CRS 942: SQL injection (deeper signatures)
    plain("information_schema"), pat("load_file%s*%(", "sql-load-file"),
    pat("into%s+outfile", "sql-into-outfile"), pat("extractvalue%s*%(", "sql-extractvalue"),
    pat("updatexml%s*%(", "sql-updatexml"), pat("waitfor%s+delay", "sql-waitfor-delay"),
    pat("pg_sleep%s*%(", "sql-pg-sleep"), pat("group_concat%s*%(", "sql-group-concat"),
    pat("'%s+and%s+", "sql-and-condition"), pat("'%s+or%s+'?%d", "sql-or-numeric"),

    -- WSTG-INPV-02 / CRS 941: Cross-site scripting (deeper signatures)
    plain("onmouseover="), plain("onfocus="), plain("onclick="), plain("<iframe"),
    plain("<svg"), plain("document.cookie"), plain("fromcharcode"),
    plain("vbscript:"), pat("expression%s*%(", "xss-css-expression"),

    -- WSTG-INPV-15 / CRS 921: HTTP response splitting / CRLF (lone CR or LF)
    pat("%%0a", "crlf-lf"), pat("%%0d", "crlf-cr"),
}

-- ---------------------------------------------------------------------------
-- Trusted callback / redirect domains (WSTG-INPV-19: SSRF; open redirect).
--
-- A WooCommerce shop legitimately puts absolute http(s):// URLs in its own
-- request URIs: payment-gateway return/notify callbacks and OAuth redirect
-- URIs. A blanket "=http://" or "://" generic signature would false-positive
-- on every one of those, so instead we allow callbacks only to a curated set
-- of known bank / payment-gateway providers plus the shop's own host (added
-- at runtime from WP_SITE_URL and the TRUSTED_CALLBACK_DOMAINS env var, see
-- init.lua). An absolute URL pointing anywhere else -- the shape of an RFI,
-- open-redirect or SSRF payload -- is then a strong suspicious signal.
--
-- Each entry is a registrable domain; a host matches when it equals the entry
-- or is a subdomain of it (see host_is_trusted). Keep lower-case, no scheme.
_M.TRUSTED_CALLBACK_DOMAINS = {
    -- Slovak banks and payment gateways
    "tatrabanka.sk", "slsp.sk", "vub.sk", "csob.sk", "postovabanka.sk",
    "365.bank", "mbank.sk", "unicreditbank.sk", "primabanka.sk",
    "gpwebpay.com", "trustpay.eu", "comgate.cz", "gopay.com", "besteron.com",
    -- Czech banks and payment gateways
    "csas.cz", "csob.cz", "kb.cz", "moneta.cz", "rb.cz", "fio.cz",
    "airbank.cz", "unicreditbank.cz", "payu.cz", "thepay.cz", "gopay.cz",
    -- European / global payment providers
    "paypal.com", "stripe.com", "adyen.com", "klarna.com", "mollie.com",
    "braintreegateway.com", "skrill.com", "trustly.com", "sofort.com",
    "checkout.com", "worldpay.com", "globalpayments.com", "nets.eu",
    "wise.com", "revolut.com",
}

-- True when `host` equals `domain` or is a subdomain of it. A suffix match on
-- a "." boundary so "notevil.com" does not match "evil.com" and
-- "paypal.com.attacker.tld" does not match "paypal.com".
local function host_matches_domain(host, domain)
    if host == domain then
        return true
    end
    return #host > #domain
        and host:sub(-(#domain + 1)) == "." .. domain
end

local function host_is_trusted(host, trusted)
    if not trusted then
        return false
    end
    for _, domain in ipairs(trusted) do
        if host_matches_domain(host, domain) then
            return true
        end
    end
    return false
end

-- ---------------------------------------------------------------------------
-- untrusted_callback_host(uri, trusted)
--
-- Scan the (decoded) URI for absolute http/https/ftp/ftps URLs and return the
-- first host that is not in the trusted-callback allowlist, or nil when every
-- absolute URL points at a trusted provider (or there are none). Userinfo and
-- port are stripped so classic bypasses -- http://paypal.com@evil.tld and
-- http://evil.tld:443/ -- are judged on the real host (evil.tld).
--
-- @param uri      string      Request URI (raw or decoded; decoded internally).
-- @param trusted  table|nil   List of registrable domains (TRUSTED_CALLBACK_DOMAINS).
-- @return string|nil  The first untrusted host, or nil.
-- ---------------------------------------------------------------------------
function _M.untrusted_callback_host(uri, trusted)
    -- No allowlist configured -> the check is disabled (treat nothing as an
    -- untrusted callback). An empty table, by contrast, trusts no external host.
    if not uri or not trusted then
        return nil
    end
    local decoded = string.lower(url_decode(uri))
    for scheme, authority in decoded:gmatch("(%a[%w%+%.%-]*)://([^/?#%s]+)") do
        if scheme == "http" or scheme == "https"
            or scheme == "ftp" or scheme == "ftps" then
            -- Strip userinfo (anything up to and including the last '@') and
            -- the port, then a trailing dot (an absolute-root FQDN).
            local hostport = authority:match("@([^@]*)$") or authority
            local host = (hostport:match("^([^:]+)") or hostport):gsub("%.$", "")
            if host ~= "" and not host_is_trusted(host, trusted) then
                return host
            end
        end
    end
    return nil
end

-- Whether one generic entry matches a lower-cased URI (see SUSPICIOUS_PATTERNS).
-- A plain string entry is a Lua pattern, as the list used to be.
local function generic_match(entry, u)
    if type(entry) == "string" then
        return string.find(u, entry) ~= nil
    end
    local kind, m = entry.kind, entry.match
    if kind == "plain" then
        return string.find(u, m, 1, true) ~= nil
    end
    local path = u:match("^[^?#]*") or u
    if kind == "ext" then
        local e = pattern_utils.escape_pattern(m)
        return string.find(path, e .. "$") ~= nil or string.find(path, e .. "/") ~= nil
    elseif kind == "segment" then
        local s = pattern_utils.escape_pattern(m)
        return string.find(path, s .. "$") ~= nil or string.find(path, s .. "/") ~= nil
    elseif kind == "param" then
        return string.find(u, "[?&]" .. pattern_utils.escape_pattern(m) .. "=") ~= nil
    end
    return string.find(u, m) ~= nil
end

-- ---------------------------------------------------------------------------
-- analyze_uri_patterns(uri, suspicious_patterns)
--
-- Scores the raw request URI string against two layers of patterns: the
-- caller-supplied generic list (Layer 1, e.g. _G.config.threat.suspicious_patterns)
-- and a fixed, finer-grained table with individual scores and OWASP WSTG
-- mappings (Layer 2, unchanged from the original pattern_analyzer.lua).
--
-- @param uri                  string
-- @param suspicious_patterns  table|nil  Generic entries (see SUSPICIOUS_PATTERNS;
--                             a plain string is a Lua pattern).
-- @param max_score            number|nil Clamp the returned score to this
--                             (the caller passes _G.config.threat.max_risk_score).
--                             The overall request score is capped at that max
--                             anyway, so a single URI signal contributing more
--                             than the max (e.g. author_enum 80 + several
--                             generic hits => "+110") is meaningless and just
--                             misleads a log/report reader -- clamp it so the
--                             "+N" never exceeds the score it can actually add.
-- @return table  { score, patterns[] }
-- ---------------------------------------------------------------------------
function _M.analyze_uri_patterns(uri, suspicious_patterns, max_score)
    local result = {
        score = 0,
        patterns = {}
    }

    if not uri then
        return result
    end

    local uri_lower = string.lower(uri)
    local uri_decoded = url_decode(uri)
    local uri_lower_decoded = string.lower(uri_decoded)

    -- Layer 1: generic suspicious patterns supplied by the caller.
    if suspicious_patterns then
        for _, entry in ipairs(suspicious_patterns) do
            if generic_match(entry, uri_lower_decoded) or generic_match(entry, uri_lower) then
                result.score = result.score + 15
                table.insert(result.patterns, type(entry) == "table" and entry.name or entry)
            end
        end
    end

    -- Layer 2: finer-grained checks with per-pattern scores and OWASP mapping.
    -- Scores reflect severity: path traversal/RCE > SQLi > XSS > recon probes.
    local specific_checks = {
        -- WSTG-INPV-01: Path Traversal
        {pattern = "%.%./",    score = 20, name = "directory_traversal"},
        {pattern = "%%2e%%2e/", score = 20, name = "encoded_directory_traversal"},

        -- WSTG-INPV-05: SQL Injection
        {pattern = "union[^%a].-select[^%a]", score = 25, name = "sql_union"},
        {pattern = "['\"%s%)]or%s+['\"]?%w+['\"]?%s*=%s*['\"]?%w", score = 20, name = "sql_or_condition"},
        {pattern = "'%s*or%s",        score = 20, name = "sql_quote_or"},
        {pattern = "select[^%a].-[^%a]from[^%a]", score = 15, name = "sql_select"},
        {pattern = "drop[^%a]+table[^%a]", score = 30, name = "sql_drop"},
        {pattern = "insert[^%a]+into[^%a]", score = 20, name = "sql_insert"},

        -- WSTG-INPV-02: Reflected / Stored XSS
        {pattern = "<script",    score = 25, name = "xss_script"},
        {pattern = "javascript:", score = 20, name = "xss_javascript"},
        {pattern = "onerror=",   score = 20, name = "xss_onerror"},
        {pattern = "onload=",    score = 15, name = "xss_onload"},
        {pattern = "alert%s*%(", score = 15, name = "xss_alert"},

        -- WSTG-INPV-12: Command Injection
        {pattern = ";%s*cat[%s%+]", score = 25, name = "cmd_cat"},
        {pattern = ";%s*ls[%s%+;&|]", score = 20, name = "cmd_ls"},
        {pattern = "|%s*nc[%s%+]", score = 30, name = "cmd_netcat"},
        {pattern = "&&%s*curl[%s%+]", score = 25, name = "cmd_curl"},
        {pattern = "`.*`",      score = 20, name = "cmd_backticks"},

        -- WSTG-INPV-11: Local/Remote File Inclusion
        {pattern = "php://",  score = 25, name = "php_wrapper"},
        {pattern = "file://", score = 20, name = "file_wrapper"},
        {pattern = "data://", score = 20, name = "data_wrapper"},

        -- WSTG-CONF-05 / WordPress-specific: Sensitive file and endpoint access.
        {pattern = "/wp%-config%.php",        score = 30, name = "wp_config_access"},
        {pattern = "/wp%-admin/install%.php",  score = 25, name = "wp_install_access"},
        {pattern = "wp%-admin.*user%-new%.php", score = 20, name = "wp_user_creation"},
        {pattern = "xmlrpc%.php",              score = 15, name = "wp_xmlrpc"},
        {pattern = "wp%-config%.php%.bak", score = 80, name = "wp_config_bak"},
        {pattern = "wp%-config%-",         score = 30, name = "wp_config_variant"},
        {pattern = "%.bak$",               score = 20, name = "bak_file"},
        {pattern = "%.old$",               score = 20, name = "old_file"},
        {pattern = "backup%.zip",          score = 25, name = "backup_zip"},
        {pattern = "wp%-backup",           score = 25, name = "wp_backup"},
        {pattern = "phpinfo%.php",         score = 30, name = "phpinfo_file"},
        {pattern = "%.htaccess",           score = 25, name = "htaccess_file"},
        {pattern = "install%.php",         score = 30, name = "install_php"},
        {pattern = "etc/passwd",           score = 30, name = "etc_passwd"},
        {pattern = "%%3[cC]script",        score = 25, name = "enc_script"},
        {pattern = "system%.listMethods",  score = 25, name = "xmlrpc_methods"},
        {pattern = "multicall",            score = 25, name = "xmlrpc_multicall"},
        {pattern = "admin%-post%.php",     score = 20, name = "admin_post"},
        {pattern = "author=%d+",           score = 80, name = "author_enum"},

        -- WSTG-INFO-02 / WSTG-INFO-03: Reconnaissance probes.
        {pattern = "/admin[/?#]",   score =  5, name = "admin_scan"},
        {pattern = "/admin$",       score =  5, name = "admin_scan"},
        {pattern = "/administrator[/?#]", score = 5, name = "administrator_scan"},
        {pattern = "/phpmyadmin",   score = 10, name = "phpmyadmin_scan"},
        {pattern = "/backup[/?#%.]", score = 10, name = "backup_scan"},
        {pattern = "/backup$",      score = 10, name = "backup_scan"},
        {pattern = "/%.env",        score = 20, name = "env_file_scan"},

        -- WSTG-IDNT: WordPress user enumeration via REST API
        {pattern = "/wp%-json/wp/v2/users", score = 25, name = "wp_user_enumeration"},
        {pattern = "rest_route=.*/wp/v2/users", score = 25, name = "wp_user_enumeration_rest"}
    }

    for _, check in ipairs(specific_checks) do
        if string.find(uri_lower_decoded, check.pattern) or string.find(uri_lower, check.pattern) then
            result.score = result.score + check.score
            table.insert(result.patterns, check.name)
        end
    end

    -- WSTG-INPV-05 / WSTG-INPV-02: URL encoding evasion detection.
    if string.find(uri, "%%[0-9a-fA-F][0-9a-fA-F]") then
        result.score = result.score + 10
        table.insert(result.patterns, "url_encoding_detected")
    end

    -- WSTG-INPV-04: HTTP Parameter Pollution.
    local param_count = 0
    for _ in string.gmatch(uri, "[&?]") do
        param_count = param_count + 1
    end

    if param_count > 20 then
        result.score = result.score + 15
        table.insert(result.patterns, "excessive_parameters")
    end

    -- NOTE: An absolute callback/redirect URL to an untrusted host (WSTG-INPV-19:
    -- RFI / open-redirect / SSRF) is deliberately NOT scored here. A score would
    -- feed honeypot routing, and such a URL can be planted in a link and sent to
    -- an innocent visitor to get THEM diverted and mislabelled. It is instead
    -- blocked outright at the edge (nginx.conf access phase, via
    -- _M.untrusted_callback_host) with a 403, touching neither the request score
    -- nor the session's reputation. See _M.TRUSTED_CALLBACK_DOMAINS.

    -- Clamp to the max score this signal can actually contribute (see @param
    -- max_score). Purely corrects the reported "+N" -- the request total is
    -- min(sum, max_risk_score) regardless, so this never changes routing.
    if max_score and result.score > max_score then
        result.score = max_score
    end

    return result
end

-- ---------------------------------------------------------------------------
-- analyze_headers(headers, request_method)
--
-- @param headers         table       Request headers (e.g. ngx.req.get_headers()).
-- @param request_method  string|nil  HTTP method of the current request.
-- @return table  { score, suspicious_headers[] }
-- ---------------------------------------------------------------------------
function _M.analyze_headers(headers, request_method)
    local result = {
        score = 0,
        suspicious_headers = {}
    }

    if not headers then
        return result
    end

    -- WSTG-INFO-02: Security tool fingerprinting via User-Agent.
    local user_agent = headers["User-Agent"] or headers["user-agent"] or ""
    local ua_lower = string.lower(user_agent)

    local flagged_uas = {
        "sqlmap", "nmap", "masscan", "zap", "acunetix", "nikto", "dirb",
        "gobuster", "wpscan", "whatweb", "nuclei", "burpsuite", "havij", "pangolin"
    }

    for _, ua in ipairs(flagged_uas) do
        if string.find(ua_lower, ua) then
            result.score = result.score + 50
            table.insert(result.suspicious_headers, "flagged_user_agent: " .. ua)
            break
        end
    end

    -- Missing User-Agent: legitimate browsers always send one.
    if user_agent == "" or not user_agent then
        result.score = result.score + 10
        table.insert(result.suspicious_headers, "missing_user_agent")
    end

    -- WSTG-AUTHZ: CVE-2023-28121 pattern header (WooCommerce Payments).
    if headers["X-WCPAY-PLATFORM-CHECKOUT-USER"] then
        result.score = result.score + 50
        table.insert(result.suspicious_headers, "cve_2023_28121_header")
    end

    -- WSTG-ATHN-04: Missing Referer on POST requests.
    if request_method == "POST" then
        local referer = headers["Referer"] or headers["referer"]
        if not referer then
            result.score = result.score + 5
            table.insert(result.suspicious_headers, "missing_referer_on_post")
        end
    end

    -- WSTG-ATHN-01: HTTP Basic Authentication probe.
    local auth = headers["Authorization"] or headers["authorization"]
    if auth then
        if string.find(string.lower(auth), "basic") then
            result.score = result.score + 5
            table.insert(result.suspicious_headers, "basic_auth_attempt")
        end
    end

    return result
end

-- ---------------------------------------------------------------------------
-- analyze_cve_patterns(uri, headers, query_params, cve_patterns, max_score, per_match)
--
-- Checks the request URI, query string, and all headers against a CVE
-- pattern dictionary. Pure: does NOT log -- the caller (pattern_analyzer.lua)
-- logs a cve_pattern_detected security event for each match, since logging
-- is I/O.
--
-- @param uri            string
-- @param headers        table|nil
-- @param query_params   string|nil   e.g. ngx.var.args
-- @param cve_patterns   table        Map of CVE ID -> Lua pattern (from
--                                    _G.config.vulnerability.cve_patterns).
-- @param max_score      number|nil   Clamp for the returned score.
-- @param per_match      number|nil   Points per matched CVE (default 40;
--                                    the edge policy's targets.target_score).
-- @return table  { score, cves[] }
-- ---------------------------------------------------------------------------
function _M.analyze_cve_patterns(uri, headers, query_params, cve_patterns, max_score, per_match)
    local result = {
        score = 0,
        cves = {}
    }

    if not uri or not cve_patterns then
        return result
    end

    local uri_lower = string.lower(uri)
    query_params = query_params or ""

    for cve, pattern in pairs(cve_patterns) do
        local found = false
        local pattern_lower = string.lower(pattern)

        if string.find(uri_lower, pattern_lower) then
            found = true
        end

        if not found and query_params ~= "" and string.find(string.lower(query_params), pattern_lower) then
            found = true
        end

        if not found and headers then
            for header_name, header_value in pairs(headers) do
                if string.find(string.lower(header_name), pattern_lower) or
                   string.find(string.lower(header_value or ""), pattern_lower) then
                    found = true
                    break
                end
            end
        end

        if found then
            result.score = result.score + (per_match or 40)
            table.insert(result.cves, cve)
        end
    end

    -- Clamp to the max score this signal can actually add (the request total
    -- is capped at max_risk_score anyway) so a multi-CVE match no longer
    -- reports a meaningless "+120" the score can never reach. cves[] is left
    -- intact -- the count of distinct CVEs is still reported truthfully.
    if max_score and result.score > max_score then
        result.score = max_score
    end

    return result
end

-- ---------------------------------------------------------------------------
-- analyze_request_method(method, method_override_header)
--
-- @param method                   string|nil  e.g. ngx.var.request_method
-- @param method_override_header  string|nil  e.g. ngx.var.http_x_http_method_override
-- @return table  { score }
-- ---------------------------------------------------------------------------
function _M.analyze_request_method(method, method_override_header)
    local result = { score = 0 }

    if method == "OPTIONS" or method == "TRACE" or method == "CONNECT" then
        result.score = result.score + 10
    end

    if method_override_header then
        result.score = result.score + 15
    end

    return result
end

-- ---------------------------------------------------------------------------
-- score_automation_user_agent(user_agent)
--
-- Pure User-Agent-string half of the original detect_automation(): matches
-- known automation-tool fingerprints. The other half (rapid-request timing,
-- which needs the shared `sessions` dict) stays in pattern_analyzer.lua's
-- detect_automation() as I/O.
--
-- @param user_agent  string|nil
-- @return table  { score, detected, tool }
-- ---------------------------------------------------------------------------
function _M.score_automation_user_agent(user_agent)
    local result = {
        score = 0,
        detected = false,
        tool = nil
    }

    local ua_lower = string.lower(user_agent or "")

    local automation_tools = {
        {pattern = "curl", name = "curl", score = 5},
        {pattern = "wget", name = "wget", score = 5},
        {pattern = "python%-requests", name = "python-requests", score = 10},
        {pattern = "go%-http%-client", name = "go-http-client", score = 10},
        {pattern = "apache%-httpclient", name = "apache-httpclient", score = 10},
        {pattern = "okhttp", name = "okhttp", score = 10},
        {pattern = "bot", name = "generic-bot", score = 15},
        {pattern = "crawler", name = "crawler", score = 10},
        {pattern = "scanner", name = "scanner", score = 20},
        {pattern = "wpscan", name = "wpscan", score = 30}
    }

    for _, tool in ipairs(automation_tools) do
        if string.find(ua_lower, tool.pattern) then
            result.score = result.score + tool.score
            result.detected = true
            result.tool = tool.name
            break
        end
    end

    return result
end

return _M
