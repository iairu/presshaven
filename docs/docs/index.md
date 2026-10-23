---
title: Honeypot IDS System
hide:
  - navigation
---

# Honeypot IDS System

<p style="font-size:1.1rem; margin-top:-0.4rem;">
<em>Zlepšenie efektivity honeypot nástroja pomocou zvýšenia úrovne interakcie</em><br>
<strong>Improving Honeypot Tool Efficiency by Increasing Interaction Level</strong>
</p>

A WordPress/WooCommerce storefront that **looks and behaves like a real shop** — but
sits behind an OpenResty (Nginx + Lua) reverse proxy that **scores every request in
real time** and transparently diverts suspicious sessions into one of several
isolated, full-fidelity **honeypot clones**. Legitimate customers never notice;
attackers get a convincing, exploitable target while every move is recorded.

!!! abstract "At a glance"
    - **High interaction, not low.** The decoy is a complete WordPress site with
      WooCommerce, Elementor, a real catalog and seeded, publicly-exploitable CVEs —
      not a canned banner.
    - **Per-attacker isolation.** Each hostile IP gets its own honeypot *pool*
      (WordPress container + database), so one attacker can never see or wreck
      another's environment, and their session state (cart, uploads) persists.
    - **Elastic pools.** New pools are cloned from a pre-built template in roughly
      MySQL's start time instead of a ~44 s from-scratch rebuild, and scale down
      when idle.
    - **Full telemetry.** Lua request scoring + Suricata network IDS + Redis session
      state, optionally shipped over mTLS to a separate Elasticsearch/Kibana SIEM.
    - **A desktop control panel.** A PyQt6 dashboard runs, watches, heals and
      visualizes both halves of the system — no hand-typed `docker compose`.

This is a master's thesis project for the **Institute of Computer Engineering and
Applied Informatics, FIIT STU** (field: *Combined security solutions*).

---

## Start here

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Getting Started**

    ---

    Bring the stack up, fire your first attack, and watch it get diverted — in
    about five minutes.

    [:octicons-arrow-right-24: Installation & setup](getting-started/installation.md)

-   :material-sitemap:{ .lg .middle } **Architecture**

    ---

    Two hosts, two compose projects, one request pipeline. How a request travels
    from the proxy to a verdict.

    [:octicons-arrow-right-24: The two-host split](architecture/two-host-split.md)

-   :material-bee:{ .lg .middle } **Honeypot Engine**

    ---

    The WordPress layer, pool scaling, per-IP stickiness, seeding, backups and the
    Redis state behind it all.

    [:octicons-arrow-right-24: How pooling works](engine/pooling.md)

-   :material-radar:{ .lg .middle } **Detection**

    ---

    What trips the detector: generic attack patterns, 14+ seeded CVEs, Suricata
    network alerts, sophistication classification, and honeytoken signals.

    [:octicons-arrow-right-24: Detection capabilities](detection/capabilities.md)

-   :material-chart-box:{ .lg .middle } **Observability**

    ---

    The Vector → Elasticsearch → Kibana pipeline and the six dashboards built on
    top of it.

    [:octicons-arrow-right-24: SIEM & log pipeline](observability/siem.md)

-   :material-cog:{ .lg .middle } **Operations**

    ---

    Deployment topologies, production hardening, troubleshooting runbooks, and
    operational procedures.

    [:octicons-arrow-right-24: Operations overview](operations/index.md)

-   :material-test-tube:{ .lg .middle } **Testing**

    ---

    Unit/integration test suite, blind pentest evaluation protocol, and scenario
    testing framework.

    [:octicons-arrow-right-24: Testing overview](testing/index.md)

-   :material-book-open-variant:{ .lg .middle } **Reference**

    ---

    Glossary, known issues, roadmap, changelog, literature, and the complete
    function reference.

    [:octicons-arrow-right-24: Reference index](reference/index.md)

</div>

---

## How it works, in short

```mermaid
flowchart LR
    U[Visitor or attacker] -->|HTTPS| RP[reverse_proxy<br/>OpenResty + Lua]
    RP -->|clean<|end|> PROD[(production_eshop<br/>the real shop)]
    RP -->|suspicious| HP[(honeypot pool N<br/>eshop + database)]
    RP -.->|scores, sessions| REDIS[(Redis<br/>session_store)]
    SUR[Suricata IDS<br/>host network tap] -.->|alerts| REDIS
    RP -->|logs| VEC[vector_outbound]
    SUR -->|eve.json / fast.log| VEC
    VEC ==>|mTLS :6000| SIEM{{SIEM host<br/>Vector → Elasticsearch → Kibana}}
```

1. Every non-static request passes through the proxy's `access_by_lua_block`.
2. [`pattern_analyzer`](architecture/request-pipeline.md) scores it (0–100+) against
   SQLi/XSS/traversal patterns, CVE signatures, IP reputation and automation
   fingerprints.
3. [`router.decide_route()`](architecture/request-pipeline.md) runs an 11-stage,
   first-match-wins decision: clean traffic stays on production; anything suspicious
   is pinned to a honeypot pool.
4. [`pool_router`](engine/pooling.md) hands that IP its own isolated pool and keeps it
   for 24 h, so the attacker sees a consistent, stateful fake world.
5. Everything is logged — locally for the dashboard, and optionally shipped to the
   [SIEM](observability/siem.md).

!!! tip "The proxy has no tarpit"
    It never holds a request back. Production and honeypot routes have **identical
    proxy latency**, so an attacker cannot tell them apart by response time. An
    earlier per-route slowdown was removed for exactly that reason.

---

## The two halves

| | Directory | Role | Compose project |
|---|---|---|---|
| **Edge host** | `ids/` | The honeypot itself: reverse proxy, WordPress (production + honeypot pools), Redis, Suricata, local Vector shipper | `honeypot-ids-system-v1` |
| **SIEM host** | `siem/` | Log storage/analysis: Elasticsearch, Kibana, Vector aggregator | directory-named |

These are **two independent systems on two hosts**, connected only by a narrow,
authenticated, outbound-only mTLS channel. That separation is a
[deliberate security boundary](architecture/two-host-split.md), not an accident — a
honeypot compromise must never be one hop from the data describing it.

---

## Detection at a glance

The detection pipeline is a multi-layered system built on a **pure/adapter split**
— all core logic lives in `*_rules.lua` modules with zero `ngx.*` dependencies,
making them unit-testable under a plain Lua interpreter:

| Layer | Module | What it detects |
| :--- | :--- | :--- |
| URI/argument patterns | `pattern_rules.lua` | SQLi, XSS, command injection, traversal, file inclusion, sensitive file access, recon probes |
| CVE matching | `vulnerability_rules.lua` | 14+ seeded CVEs (WooCommerce Payments, Gift Voucher, CWMP, Bricks Builder, etc.) |
| Network IDS | `suricata_rules.lua` | Suricata `eve.json` alerts — severity-graded scoring (severity 1 → +50) |
| Header analysis | `pattern_rules.lua` | Flagged user-agents (+50), missing UA (+10), CVE-specific headers (+50) |
| IP reputation | `pattern_analyzer.lua` | Suricata alerts + AbuseIPDB, with shared-address (NAT) protection |
| Automation | `pattern_analyzer.lua` | UA fingerprinting + rapid-request timing streaks (3+ within 0.5s) |
| Upload analysis | `upload_rules.lua` | Dangerous extensions, bypass techniques, CVE-specific endpoints, polyglot files |
| Admin access | `admin_rules.lua` | Brute-force scoring, credential stuffing, direct file access, user enumeration |
| Session anomalies | `session_rules.lua` | IP/UA change, flagged agents, rapid requests |
| Sophistication | `sophistication_analyzer.lua` | Scripted / ai_assisted / manual / unknown classification |
| Honeytokens | `honeytoken_handler.lua` | Injected fake credentials detected in inbound requests |
| GDPR identity | `gdpr_rules.lua` | Privacy-preserving consent-gated second identifier |

---

## Operations & deployment

The system supports two deployment topologies:

- **[Two-host](operations/two-host.md)** — Edge host (reverse proxy, honeypot, Suricata) + SIEM host (Elasticsearch, Kibana). Dashboards split by functional domain: operational view (IDS alerts, web threat overview) vs strategic view (threat decisions, session analysis, attack patterns, threat intelligence).
- **[Single-host](operations/single-host.md)** — All components on one host. Suitable for evaluation, labs, and small-scale deployments.

**Production hardening** covers TLS, firewall rules, authentication, session cookie signing, threat decay configuration, AbuseIPDB setup, and the internal test secret gating.

**Runbooks** cover service restart, incident response, Suricata troubleshooting, Kibana dashboard staleness, timeline capture failures, same-host testing caveats, session recovery, and false-positive tuning.

---

## Testing

The codebase follows a **pure/adapter split** — all `*_rules.lua` modules are unit-testable under a plain Lua interpreter without OpenResty:

| Test File | Module | Coverage |
| :--- | :--- | :--- |
| `test_pattern_rules.lua` | URI/header/CVE/automation scoring | Full |
| `test_router_rules.lua` | Routing predicates, decay, decision trace | Full |
| `test_vulnerability_rules.lua` | CVE pattern matching, exploit kit detection | Full |
| `test_suricata_rules.lua` | Alert parsing, severity scoring, decay | Full |
| `test_abuseipdb_rules.lua` | Report eligibility, categories, comments | Full |
| `test_lua_pattern_utils.lua` | URL decode, pattern escape, install wizard URI | Full |
| `test_decay_policy.lua` | Escalation-aware decay, permaflag | Full |
| `test_ip_rules.lua` | IPv4/IPv6 CIDR matching | Full |
| `test_upload_rules.lua` | Content type, parameters, endpoints, bypass | Full |
| `test_admin_rules.lua` | Login, patterns, brute force, credential stuffing | Full |
| `test_session_rules.lua` | Anomalies, honeypot routing | Full |
| `test_session_identity_rules.lua` | Cookie signing, fingerprinting, rejections | Full |
| `test_honeytoken_rules.lua` | Token-in-corpus matching | Full |
| `test_prompt_injection_filter.lua` | Prompt injection detection | Full |
| `test_pool_router_rules.lua` | Pool assignment, health, parsing | Full |
| `test_router_decide_route.lua` | Routing decision pipeline | Full |
| `test_gdpr_rules.lua` | Timestamp, canonical chars, validation | Full |
| `test_pool_assignment.lua` | Pool assignment lifecycle | Full |

Plus dashboard tests (`test_kibana_dashboards.py`, `test_host_settings.py`, `test_overview_stats.py`, `test_learning.py`) and scenario scripts.

**Blind pentest evaluation** follows a documented protocol with `INTERNAL_TEST_SECRET` gating to prevent exposing routing/risk-score oracles.

---

## Complete page index

### Getting Started
- [Installation & setup](getting-started/installation.md)
- [Quickstart](getting-started/quickstart.md)
- [Commands](getting-started/commands.md)
- [Dashboard](getting-started/dashboard.md)

### Architecture
- [Architecture overview](architecture/index.md)
- [Services](architecture/services.md)
- [Request pipeline](architecture/request-pipeline.md)
- [Two-host split](architecture/two-host-split.md)
- [Lua modules](architecture/lua-modules.md)

### Engine
- [Engine overview](engine/index.md)
- [WordPress](engine/wordpress.md)
- [Pooling](engine/pooling.md)
- [Seeding](engine/seeding.md)
- [Backups](engine/backups.md)
- [Layers](engine/layers.md)

### Detection
- [Detection overview](detection/index.md)
- [Detection capabilities](detection/capabilities.md)
- [Seeded CVEs](detection/cves.md)
- [Suricata network IDS](detection/suricata.md)
- [Advanced signals](detection/advanced.md)

### Observability
- [Observability overview](observability/index.md)
- [SIEM & log pipeline](observability/siem.md)
- [Kibana dashboards](observability/kibana.md)

### Operations
- [Operations overview](operations/index.md)
- [Two-host deployment](operations/two-host.md)
- [Single-host deployment](operations/single-host.md)
- [Production hardening](operations/hardening.md)
- [Troubleshooting & runbooks](operations/runbooks.md)

### Testing
- [Testing overview](testing/index.md)
- [Blind pentest evaluation](testing/blind-pentest.md)

### Reference
- [Reference overview](reference/index.md)
- [Glossary](reference/glossary.md)
- [Known issues & corrections](reference/known-issues.md)
- [Roadmap](reference/roadmap.md)
- [Changelog](reference/changelog.md)
- [Primary literature](reference/literature.md)

---

!!! note "About this knowledge base"
    Every page here is derived from the running system and current source, not copied
    forward from older docs. The single long-form
    [Technical Manual](MANUAL.md) remains the canonical reference; this site
    reorganizes and expands it into a navigable, cross-linked knowledge base.
    Function-level documentation is extracted directly from Lua module comments
    and Python dashboard code, including all known caveats and limitations.