# Dashboard — missing functionality

Gaps where functionality a honeypot/SIEM operations console would be
expected to have is **absent entirely**, or is **wired up in the code but
never surfaced in the UI**. Ordered roughly by impact.

Scope: the PyQt6 dashboard in `dashboard/`. Sidebar today (see
`ui/main_window.py` `NAV_GROUPS`):

- **Monitor** — Global Visualization, Workload Telemetry, SIEM Analytics, Forensics Analysis
- **Threat Operations** — Attack Simulation, Segmentation Validation, Pool State Store
- **Manage** — Workloads, PKI & Certificates, Backup & Recovery, Connectors & Config
- **Reporting** — Reporting, Knowledge Base

---

## 1. No Overview / home / SOC summary page — *and the data for it is already being collected and thrown away*

This is the single clearest gap. There is **no landing page** — the app
opens straight onto a control page (`state.last_page`, or Knowledge Base on
first run). Every operations console opens on a summary.

More tellingly, the plumbing for exactly such a page already exists and
feeds nothing:

- `ui/security_feed.py` runs an **app-lifetime background tail** of
  `reverse_proxy`'s logs, parses it, and persists notable events (honeypot
  diversions, CVE / high-severity signals, missing dependencies) to
  `AppState.security_events` across restarts (`core/state.py:70-75`).
- It exposes `event_added`, `score_changed`, `recent_events()` and
  `latest_score`, and its own docstring says it *"Powers the Overview
  page's 'current score' and 'recent security events' list"*
  (`ui/security_feed.py:9`).
- **That Overview page does not exist.** `ui/main_window.py:168-172`
  admits it directly: *"No page currently displays this … kept running
  since the underlying data collection is independently useful."*
- Verified: nothing connects `event_added` / `score_changed`; nothing
  calls `recent_events()` / `latest_score` (grep across `ui/` and `core/`
  returns only `main_window.py` instantiating/starting/stopping the feed).

So a continuous log tail is burning a QProcess for the whole session and
writing a capped 200-event history to disk that the user can never see.

**What's missing:** an Overview page (the natural first entry under a new
top group, or the top of Monitor) showing current risk score, a live
"recent security events" list from the feed, counts of containers up/down
across both stacks, honeypot diversions in the last N minutes, and
pool/scaling state at a glance. It would make the already-collected data
useful and give the sidebar a home.

## 2. No native live alert / event feed (independent of Kibana)

Right now "what is attacking me right now" is visible only via:

- the **embedded Kibana browser** (SIEM Analytics) — requires the SIEM
  stack and QtWebEngine to be healthy; the page even has a fallback banner
  for when Kibana's container is down (`ui/page_kibana.py`), i.e. the
  analytics simply vanish when the SIEM is unavailable;
- a **transient log tail** on the Attack Simulation page, only while that
  page is open;
- the **collected-but-undisplayed** security feed (item 1).

There is no always-available, in-app stream of security events (honeypot
diversions, high-severity hits, Suricata criticals) that survives the SIEM
being down. For a honeypot console this is arguably the primary view.

## 3. No per-session / per-attacker drill-down

`ARCHITECTURE.md:111` states plainly that session-analysis and
attack-pattern views are **"Not built"**, because that data "currently
lives only in Redis (`session:*`), not Elasticsearch."

The dashboard has the raw material: the Pool State Store page
(`ui/page_redis.py`) lists Redis keys (`session:*`, `threat_ips`,
`suricata_alerts`, …) and draws a `threat_ips` bar chart. But there is no
view that assembles one attacker/session into a story: who (IP /
fingerprint / cookie), from where, which patterns/CVEs they tried, how the
score climbed over time, when and to which honeypot pool they were
diverted. That synthesis is the core analyst task a honeypot exists to
support, and it isn't anywhere — not in the dashboard, not in Kibana.

## 4. No Suricata-native surface

Suricata is a first-class IDS layer in this project (eve.json / fast.log,
feeds IP reputation — `core/learning.py:153-160`). Yet the dashboard has
**no Suricata page**: no recent fast.log alerts, no signature/ruleset
listing, no enabled-rules view, no per-alert detail, no rule
enable/disable. Suricata output is reachable only inside embedded Kibana
("IDS Alerts (Suricata)" bookmark) or by grepping its container logs on
Forensics Analysis. The network-IDS half of a "honeypot **IDS**" has no
dedicated control/observation surface.

## 5. No alerting / notification policy

The only alerting in the app is a **hardcoded** system-tray balloon when a
container transitions into `unhealthy` / `exited_bad`
(`ui/main_window.py:59` `_NOTIFY_ON_STATUSES`, `_notify_new_problems`).
There is:

- no way to get notified on **security** events (a CVE hit, a high-severity
  diversion, a Suricata critical) — only on container health;
- no configurable thresholds or rules;
- no external notification channel (email / webhook / Slack / desktop
  beyond the single balloon).

A security console that can't alert on security events is a real gap.

## 6. No detection-policy editor as a first-class surface

Tuning the detector is central to the teaching story — the Knowledge Base
and page guides repeatedly send the user to `SCORE_DECAY_HALF_LIFE_SECONDS`,
`THREAT_DECAY_ENABLED`, the honeypot threshold (80), etc.
(`core/learning.py:69-78`, `:332-337`). But the only way to change any of
it is **hand-editing raw `.env` text** on the Connectors & Config page.

There is no structured "Detection policy" page that surfaces the knobs that
matter — score threshold, decay half-life, decay on/off, per-signal weights
— with labels and explanations, and writes them back. The learning content
describes a UI that isn't there.

## 7. No always-on pool / scaling dashboard

`pool_manager` logs rich build / hand-over / resource-limit events to
`honeypot_pool:events` (`ARCHITECTURE.md:61`), and the Segmentation
Validation page consumes them — but **only during a test run**. There is no
standing view of live pool state: how many pools are ready, how many
sessions each owns, how much of the memory/CPU budget is used, whether the
system is `capped`. Outside running a full pool test or reading raw Redis
keys, the scaling behaviour that is a headline feature of this honeypot is
invisible.

## 8. No edge→SIEM delivery-health indicator

The whole architecture hinges on one narrow channel: the edge
`vector_outbound` shipper pushing to the SIEM `vector_inbound` aggregator
over mTLS (`ARCHITECTURE.md:10`, `:88`). Whether logs are **actually being
delivered** ("Healthcheck passed." vs. TLS/retry failures) is invisible in
the dashboard — Global Visualization shows the container up/down, not
whether the pipe is flowing. Given that two previously-shipping-silently
bugs in exactly this channel are documented (`ARCHITECTURE.md:90-94`), a
"logs flowing to SIEM: yes/no + last delivery" indicator is a meaningful
missing safety check.

## 9. Forensics Analysis has no export, time-range, or structured search

The Forensics Analysis page (`ui/page_log_search.py`) is substring grep
across containers. Missing versus what "forensics" implies:

- no **export** of the matching result set to a file (per-container log
  export exists on Workloads/Global Visualization via `ui/log_export.py`,
  but not for search results);
- no **time-range** filter;
- no **regex** / structured-field search (it matches ANSI-stripped
  substrings only);
- no **saved searches** / history.

## 10. No in-app command palette / quick page switcher

13 pages across 4 groups, reachable by click, `Ctrl+1..9` (first 9 only —
see `dashboard_improvable.md`), or the View menu. There is no
`Ctrl+K`-style quick switcher / command palette, which is the norm for a
console with this many surfaces.

---

### Quick reference — where each gap lives

| # | Gap | Key evidence |
|---|-----|--------------|
| 1 | Overview page (data already collected) | `ui/security_feed.py:9`, `ui/main_window.py:168-172`, `core/state.py:70-75` |
| 2 | Native live alert feed | `ui/page_kibana.py` (Kibana-only), `ui/page_patterns.py` (transient) |
| 3 | Session/attacker drill-down | `ARCHITECTURE.md:111`, `ui/page_redis.py` |
| 4 | Suricata-native page | `core/learning.py:153-160`, Kibana bookmark only |
| 5 | Alerting policy | `ui/main_window.py:59`, `_notify_new_problems` |
| 6 | Detection-policy editor | `core/learning.py:332-337`, raw `.env` only |
| 7 | Live pool/scaling view | `ARCHITECTURE.md:61`, test-run-only |
| 8 | Shipper delivery health | `ARCHITECTURE.md:88-94` |
| 9 | Forensics export/time/regex | `ui/page_log_search.py` |
| 10 | Command palette | `ui/main_window.py` `_build_shortcuts` |
