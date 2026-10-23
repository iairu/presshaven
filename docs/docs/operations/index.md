# Operations

This section covers operational aspects of running the honeypot system.

## Operational Domains

- **Deployment**: Two-host and single-host topologies.
- **Monitoring**: Observability, dashboards, alerting.
- **Hardening**: Production security recommendations.
- **Runbooks**: Troubleshooting and incident procedures.
- **Routing & Pooling**: Router decision pipeline, honeypot pool assignment, session management.

## Routing Decision Pipeline (from `router.lua`)

`router.lua` makes the final routing decision for every inbound HTTP request: forward to the production WordPress instance (`production_backend`) or divert to an isolated honeypot pool instance (`honeypot_backend_N`).

### Decision Pipeline (evaluated in order; first match wins)

| Stage | Condition | Route | Reason |
| :--- | :--- | :--- | :--- |
| 1 | Static asset | Production | CSS/JS/images, no attack surface |
| 1b | install.php on not-yet-installed WordPress | Production | Legitimate setup wizard |
| 2 | Session already honeypot_bound | Honeypot | Sticky honeypot (same pool via Redis) |
| 3 | Risk score ≥ honeypot_threshold | Honeypot | High risk (WSTG-INPV catch-all) |
| 4 | CVE pattern matched | Honeypot | CVE pattern detected |
| 5 | Vulnerable plugin URI | Honeypot | Direct plugin endpoint access |
| 6 | Bad IP reputation (>50) | Honeypot | Known flagged IP from threat_intel |
| 7 | Multiple admin-access attempts (≥3) | Honeypot | WSTG-ATHN-04 |
| 8 | Accumulated suspicious activities (≥5) | Honeypot | Cumulative suspicious signals |
| 9 | Rapid automation detected | Honeypot | WSTG-INFO-02 (if score ≥ 40) |
| 10 | Suspicious file upload | Honeypot | WSTG-INPV-10 |
| 11 | Default | Production | — |

### Pooling Integration

When a request is routed to the honeypot, `pool_router.lua` determines which specific pool instance the attacking IP should be sent to. Once assigned, the IP always hits the same pool so the user sees a consistent fake environment. The assigned pool number is stored in the session under `session_data.honeypot_pool`.

### No Tarpit

The proxy never holds a request back. An earlier tarpit (apply_botnet_slowdown) slept 0.5–3s for hostile or automated clients, which let a user tell the honeypot from production by latency. Every visitor, on either route, gets the same proxy latency.

### Score Accumulation

Router.lua folds the session's own decaying suspicion history into each request's fresh score before any stage compares against the threshold. A new signal (fresh score > 10) accumulates onto the session's decayed base rather than being judged alone, capped at `max_risk_score`. A negligible/clean request (fresh score ≤ 10) neither adds to nor resets the running total.

### Honeypot Pool Assignment (from `pool_router.lua`)

Each user **session** (not IP address) is permanently assigned to a specific honeypot pool instance (`honeypot_eshop_N` + `honeypot_database_N`). This gives every user their own isolated WordPress environment so their actions cannot cross-contaminate other user sessions.

**Architecture:**
*   Pools are numbered 1..N. Pools 1-3 are declared in `docker-compose.yml`; further pools are created at runtime by the `pool_manager` container.
*   **Exclusive assignment**: A new user session is handed a free ready pool that no other session owns (atomic Redis EVAL via `pool_router_rules.ASSIGN_SCRIPT`).
*   **Spare provisioning**: Every assignment queues a wake-up on `honeypot_pool:provision`; `pool_manager` builds an additional pool pair so one is ready for the next user.
*   **Scale-up**: If no pool is free but `pool_manager` may still grow, the session borrows a ready pool round-robin and joins `honeypot_pool:waiting`.
*   **Reuse at resource limit**: Once `pool_manager` has capped growth, a new session is assigned to an existing ready pool in strict round-robin order and shares it for good.
*   **TTL**: Session→pool mapping lives in Redis with a 24-hour TTL.
*   **Health fallbacks**: If a pool is unhealthy, the router transparently falls back to the next healthy pool without changing the stored assignment.

### GDPR Consent-Gated Identity (from `gdpr_rules.lua`)

A second, privacy-preserving identifier runs alongside the signed SERVERID session cookie. The reverse proxy serves a consent banner and RSA public key. Only if the visitor agrees does the browser build a tiny payload from its characteristics plus a timestamp, RSA-OAEP-encrypt it into a `gdpr_token`, and send it as a cookie on every request. The private key never leaves the proxy. The proxy decrypts in memory only long enough to check timestamp freshness and strip the timestamp, hashing the REST into a one-way `gdpr_signature`. Only the signature is stored (only when bound to a honeypot), with TTL as the binding's expiry.

### Configuration Reference (from `init.lua`)

| Config Section | Key | Default | Description |
| :--- | :--- | :--- | :--- |
| `threat` | `honeypot_threshold` | 80 | Minimum total score triggering honeypot routing |
| `threat` | `max_risk_score` | 100 | Hard cap on accumulated score |
| `threat` | `ip_reputation_cap` | 10 | Max reputation contribution per request on shared addresses |
| `threat` | `score_decay_half_life_seconds` | 300 | Half-life for score decay |
| `session` | `max_idle_time` | 3600 | Session TTL in seconds |
| `session` | `tamper_score` | 50 | Risk score added for tampered session cookies |
| `abuseipdb` | `confidence_minimum` | 90 | AbuseIPDB confidence threshold for bulk feed |
| `abuseipdb` | `daily_check_limit` | 1000 | Free-tier daily cap on on-demand checks |

<div class="grid cards" markdown>

-   :material-host:{ .lg .middle } **[Running on Two Hosts](two-host.md)**
    
    ---
    
    How to run the system across two separate hosts.

-   :material-test-tube:{ .lg .middle } **[Single-Host Testing](single-host.md)**
    
    ---
    
    How to test the system on a single host environment.

-   :material-shield:{ .lg .middle } **[Production Hardening](hardening.md)**
    
    ---
    
    Security hardening recommendations for production deployment.

-   :material-file-document:{ .lg .middle } **[Troubleshooting & Runbooks](runbooks.md)**
    
    ---
    
    Troubleshooting guides and operational runbooks.

</div>
