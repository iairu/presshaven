# Production Hardening

This page describes security hardening recommendations for production deployment.

## Network Hardening

*   Place honeypot behind a TLS-terminating reverse proxy with valid certificates.
*   Restrict inbound access to the honeypot backend to trusted proxies only.
*   Enable firewall rules limiting SIEM/Kibana access to authorized hosts.
*   Isolate the honeypot network segment from production backend networks.

## Authentication & Access Control

*   Use strong, unique admin credentials for WordPress and SIEM interfaces.
*   Enable multi-factor authentication where supported.
*   Rotate API keys and credentials for Kibana/Elasticsearch.
*   Apply least-privilege access for dashboard operators and analysts.

## Lua Pipeline Hardening

From `init.lua` configuration:

### IP Whitelisting

`_G.config.threat.ip_whitelist` contains CIDR ranges or exact IPs that receive a negative reputation score (−20) and are never diverted to the honeypot. Should include:

*   Operator's admin IP
*   Tailscale tunnel range (`100.64.0.0/10`, `fd7a:115c:a1e0::/48`)
*   University/lab network used for testing (`10.0.0.0/8`)
*   Loopback (`127.0.0.1/32`, `::1/128`)

Whitelisting is implemented via `ip_rules.in_any()` — real bit-level CIDR matching including non-octet-aligned prefixes and IPv4-mapped IPv6 clients.

### Session Cookie Security

The session cookie is named `SERVERID` (mimics an ordinary HAProxy stickiness cookie to reveal nothing in DevTools). It is signed with an HMAC key (`SESSION_SIGNING_KEY`). When the key comes from the env var, a bad signature is scored as tampering (+50 via `session.tamper_score`). When unset, a random key is generated at startup, so cookies issued before a restart stop verifying (sessions recovered by fingerprint instead).

### Threat Decay Configuration

*   `THREAT_DECAY_ENABLED=false` turns threat decay OFF entirely — half-life of 0 makes every decay path return the stored peak unchanged, so a session's/IP's risk score persists indefinitely once earned.
*   `DECAY_OFFENSE_SLOWDOWN` (default 0.75): each offense multiplies the half-life by `(1 + this)`, e.g., 0.75 → 1 offense = 1.75x slower decay, 4 = 4x.
*   `PERMAFLAG_OFFENSES` (default 5): at/above this many offenses the score stops decaying entirely.
*   `PERMAFLAG_SCORE` (default 100): a single request whose score reaches this also permaflags on its own.

### AbuseIPDB Configuration

*   `ABUSEIPDB_API_KEY` — when nil or placeholder, `abuseipdb_client` disables itself (bulk feed, on-demand checks, report-back all become no-ops).
*   `ABUSEIPDB_CONFIDENCE_MINIMUM` (default 90) — AbuseIPDB confidence score threshold for bulk `/blacklist` feed imports.
*   `ABUSEIPDB_DAILY_CHECK_LIMIT` (default 1000) — Free-tier daily cap on on-demand `/check` calls.
*   `ABUSEIPDB_BLACKLIST_ENABLED` (default false) — Bulk blacklist pull is opt-in; defaults OFF to preserve quota.
*   `ABUSEIPDB_BLACKLIST_REFRESH_HOURS` (default 24) — Minimum age before a fresh `/blacklist` call is allowed.

### Internal Test Secret

`INTERNAL_TEST_SECRET` gates the `X-Route-Target` / `X-Risk-Score` response headers. When set, headers are only emitted for requests carrying a matching `X-Internal-Test-Auth` header; when unset/empty, headers are never emitted (fail closed, not fail open). This prevents handing a blind pentest the routing/risk-score oracle for free (see `BLIND_PENTEST_PROTOCOL.md` §8.2).

## Logging & Monitoring

*   Ship structured logs to the SIEM with appropriate retention.
*   Forward Suricata alerts to the SIEM in real time.
*   Enable audit logging for administrative actions.
*   Monitor `_G.utils.log_security_event()` output in Nginx error logs via Vector.

## Runtime Hardening

*   Keep WordPress, plugins, and themes updated.
*   Disable XML-RPC amplification vectors where feasible.
*   Rate-limit login and REST API endpoints.
*   Monitor file upload directories for suspicious activity.
*   Regularly review `threat_intel` shared dict for poisoned entries (see `core/redis_inspect.py`'s `is_local_ip`/`_UNPOISON_SCRIPT`).
