# Dashboard — missing functionality (round 2)

A fresh gap analysis after the first round. Every item from the original
`dashboard_missing.md` (Overview, Live Events, Attacker Sessions, Network
IDS, alerting, Detection Policy, Pool Scaling, edge→SIEM delivery,
Forensics export/regex, command palette) is now **built** — the sidebar
has grown from 13 to 20 pages. That changes the picture: the biggest
remaining gaps are no longer "there is no page for X" but "the app now
*computes* a critical signal and still can't **alert, record, or trend**
on it." Ordered roughly by impact.

Scope: the PyQt6 dashboard in `dashboard/`. Sidebar today
(`ui/main_window.py` `NAV_GROUPS`): **Overview** · **Monitor** (Live
Events, Log Pipeline, Global Visualization, Workload Telemetry, SIEM
Analytics, Forensics Analysis) · **Threat Operations** (Attack Simulation,
Attacker Sessions, Network IDS, Detection Policy, Pool Scaling, Segmentation
Validation, Pool State Store) · **Manage** (Workloads, PKI & Certificates,
Backup & Recovery, Connectors & Config) · **Reporting** (Reporting,
Knowledge Base).

Baseline when this was written: `340 tests OK`, smoke `pages: 20 nav: 20`.

---

## 1. Alerting ignores the health signals the app now computes

The first round added a configurable alert policy
(`ui/page_settings.py:110` alerts tab; `core/alert_policy.py`) — but it is
wired to **exactly one source**: parsed reverse-proxy pattern events
(`ui/main_window.py:595` `_on_security_event`, fed only by
`security_feed.event_parsed`). Container health has its own separate,
hardcoded path (`_notify_new_problems`, `ui/main_window.py:577`).

Everything *else* the dashboard now measures raises **no notification at
all** — you only find out by having the right page open:

- **Edge→SIEM delivery FAILING** — the Log Pipeline page computes
  `sh.FAILING` / `sh.STOPPED` and the honeypot-doc count going flat
  (`ui/page_pipeline.py:156`), the single most important "is my data
  actually reaching the SIEM" check, and it fires nothing.
- **Pool capped** — Pool Scaling computes the `capped` state and
  `capped_reason` (`core/pool_view.py`, `ui/page_pool_scaling.py:167`);
  silent.
- **Suricata critical alerts** — the Network IDS page tallies
  critical/high severities (`ui/page_suricata.py`); silent.

A security console that can alert on an XSS string in a URL but not on
"logs have stopped reaching the SIEM" is alerting on the wrong tier. These
three signals should feed the same policy/tray/webhook path, with their own
severities and throttles.

## 2. No alert history / audit trail

Alerts are **fire-and-forget**: `_deliver_alert` (`ui/main_window.py:607`)
shows a tray balloon and/or POSTs a webhook and then discards everything.
A grep for any alert log/history store returns nothing. Consequences:

- An operator cannot answer "what alerted overnight, and when?" — the
  balloons are gone and nothing lists them.
- Webhook delivery outcomes are only surfaced as a transient, throttled
  tray warning (`_on_webhook_result`, `ui/main_window.py:627`); there is no
  record of which alerts were delivered vs. dropped.
- The persisted `security_events` history (`core/state.py`) records *proxy
  events*, not *alert decisions* — so even the data that is kept isn't the
  audit trail.

A small persisted, in-app **Alert log** (timestamp · severity · what ·
delivery result), reviewable and exportable, is the natural companion to
the policy editor that already exists.

## 3. No IP-reputation management surface

The honeypot's `threat_ips` reputation table is shown in several places but
is **read-only everywhere**: a bar chart on Pool State Store
(`ui/page_redis.py`), a per-session reputation panel on Attacker Sessions
(`ui/page_sessions.py:208`). The *only* mutation anywhere is the coarse
"Unpoison host IP" on Attack Simulation (`ui/page_patterns.py`), meant for
resetting your own test host.

Missing for an operator:

- a first-class **IP reputation view** (every IP, score, age, TTL, why it
  was flagged) that you can sort and search;
- **manual block / unblock** of a single IP;
- an **allowlist** of known-good sources (your own scanner, monitoring,
  CI) so they never get diverted — there is no allowlist concept at all.

This is core honeypot-operator functionality; today the reputation table
can only be observed, never curated.

## 4. No historical trend / time-series for security posture

The native surfaces added in round 1 are all **"now" views**: Overview
shows the *current* score and a flat event list (`ui/page_overview.py`),
Live Events is a live stream (`ui/page_live_events.py`), and Workload
Telemetry graphs are a ~5-minute in-RAM `deque` lost on page switch
(`ui/page_resources.py`). There is **no native "score / attacks over the
last hours/days" chart** — that history lives only in Kibana.

That is self-defeating: the whole point of building native alert/event
surfaces was to stay useful when the SIEM (or QtWebEngine) is down, yet the
moment you ask "is this worse than an hour ago?" you're back in Kibana. A
score sparkline and an events-per-interval histogram, from the already
persisted `security_events`, would make the native surfaces answer the
question they imply.

## 5. No triage / acknowledgement workflow

Attacker Sessions, Network IDS alerts and Live Events are all **read /
stream** views. Nothing can be marked reviewed, handled or ignored, and
there is no "new since I last looked" concept — every refresh re-presents
everything as equally fresh. For a console meant to be watched over a
session, there is no workflow state at all: an analyst can't record that
they triaged a session, mute a noisy signature, or flag one attacker to
come back to. Even a lightweight per-session/per-alert "acknowledged" flag
(persisted in `state`) and a "N new" badge would turn these from log
viewers into an operations surface.

## 6. Forensics / evidence export is inconsistent and incomplete

Round 1 gave Forensics Analysis export and Live Events a CSV export
(`ui/page_live_events.py:179`), but the other evidence-bearing tables
**can't export at all**: Attacker Sessions (the session table, a session's
story + timeline), Network IDS (the alert set), and Pool Scaling (the event
log) have no export affordance. For pages whose stated job is forensic
analysis and incident evidence, "I found it but I can't get it out of the
app" is a real gap — and the inconsistency (one page exports, three
adjacent ones don't) is its own usability problem.

---

### Quick reference — where each gap lives

| # | Gap | Key evidence |
|---|-----|--------------|
| 1 | Alerting ignores pipeline / pool / Suricata health | `ui/main_window.py:595,577`; `ui/page_pipeline.py:156`; `ui/page_pool_scaling.py:167` |
| 2 | No alert history / audit trail | `ui/main_window.py:607,627`; no store (grep) |
| 3 | No IP-reputation management (block/unblock/allowlist) | `ui/page_redis.py`, `ui/page_sessions.py:208`, `ui/page_patterns.py` |
| 4 | No security-posture trend / time-series | `ui/page_overview.py`, `ui/page_resources.py` (5-min RAM) |
| 5 | No triage / acknowledgement state | `ui/page_sessions.py`, `ui/page_suricata.py`, `ui/page_live_events.py` |
| 6 | Export missing on Sessions / Suricata / Pool Scaling | `ui/page_live_events.py:179` (only exporter) |

---

## 7. Additional tasks added by user


- count request number in SIEM properly (background requests (additional fetch requests etc) and user requests (the actual navigation done by an user) separation within all kibana dashboards)

- workload telemetry in dashboard only starts showing workload when the page opens but we need workload history of past 300s as well to actually have useful data by the time the page opens

- repurpose the reporting page: direct the user onto pages that have pdf export options instead of the options that are on the page right now

- have "current risk score" be calculated differently than just assigning the attacker's score in overview page with time decay etc.

- add "unique ip diversions" into overview page instead of just "honeypot diversions", also add "used/available/preparing pool count" into the overview page, have the overview page stats auto-refresh

- on workloads page have the "stack view" as default and also have the "honeypot layer" dropdown disabled while the services are up with a note next to it (requires services to be down first for reconfiguration)

- show the ctrl+k search button in top right corner of the app at all times

---

## Implementation notes (added by Claude)

Context gathered for each task, plus the concrete plan and the files each
touches. One commit per task. Baseline before starting: `340 tests OK`,
smoke `pages: 20 nav: 20`. (venv python: `./venv/bin/python`.)

### A. Separate user-navigation from background requests in Kibana
- **Where:** this is the SIEM subsystem, not the PyQt app. The dashboards
  are generated by `siem/kibana/build_dashboards.py` →
  `siem/kibana/saved_objects/honeypot-dashboards.ndjson`, and
  `tests/test_kibana_dashboards.py` asserts the committed NDJSON equals a
  fresh build, so the builder is the source of truth and the NDJSON must be
  regenerated in the same commit.
- **Signal available:** the SIEM Vector parses a `uri` field from the
  nginx `security` access log (`siem/vector/vector.yaml:51`
  `(?P<uri>\S+)`). There is **no** `Sec-Fetch-Dest`/content-type field, so
  navigation-vs-background has to be derived from the request itself.
- **Plan:** in `siem/vector/vector.yaml`, for `log_type == nginx_security`
  add a derived `request_kind` field — `"asset"` when `uri` matches a
  static-asset extension (`.js .mjs .css .map .png .jpg .jpeg .gif .svg
  .ico .webp .avif .woff .woff2 .ttf .eot`) or a known background endpoint
  (`admin-ajax.php`, `wp-cron.php`, `/favicon.ico`), else `"navigation"`.
  Then in `build_dashboards.py`: rename "Total Requests" to **User Requests
  (navigation)** filtered to `request_kind:"navigation"`, add a
  **Background Requests** metric and a **navigation vs background** pie, and
  regenerate the NDJSON. Caveat: can't be exercised against a live ES here;
  validated via the dashboards unit test (fresh-build == committed) + any
  Vector VRL tests.

### B. Pre-warm Workload Telemetry history (~300 s) before the page opens
- **Now:** `ui/page_resources.py` polls only between `showEvent` and
  `hideEvent` (`_start_worker`/`_stop_worker`), into a per-metric
  `deque(maxlen=HISTORY_POINTS=150)` (~5 min at 2 s). Open the page cold →
  empty graphs that fill over the next 5 min.
- **Plan:** keep a lightweight app-lifetime sampler for the default target
  so ~300 s of history already exists on first open. Reuse the existing
  `_StatsWorker`; have MainWindow own a background collector (like the
  security feed) and hand its ring buffer to the page, or have the page
  start its worker at construction and keep it running (bounded by the same
  deque). Prefer the smaller change: start collecting at app start for the
  active edge+siem targets, seed the page's deques on first show.

### C. Repurpose the Reporting page as an export hub
- **Now:** `ui/page_extras.py` offers three thesis-flavoured PDFs
  (implementation chapter, architecture, CVE matrix).
- **Other PDF exports already in the app:** Attack Simulation
  (`ui/page_patterns.py`), Segmentation Validation (`ui/page_pool_test.py`),
  Workloads start/stop resource PDFs (`ui/page_services.py`), Kibana
  timeline capture (`ui/page_kibana.py`).
- **Plan:** turn Reporting into a directory that *routes* to each page that
  can export a PDF (via `open_page_requested`, the same signal the Overview
  and Knowledge Base pages use), with a one-line description of what each
  produces. Keep the thesis/architecture/CVE exports here (they have no
  other home) but present everything as one "where to get each report" hub.

### D. Compute Overview "current risk score" as a decayed aggregate
- **Now:** `ui/page_overview.py` shows `feed.latest_score` — literally the
  last scored request, so it swings to whatever just hit and ignores decay.
- **Plan:** compute a posture score in `core/overview_stats.py` (Qt-free,
  unit-tested) from the persisted `security_events` using the same
  half-life decay model the detector uses (`core/detection_policy.py`
  `SCORE_DECAY_HALF_LIFE_SECONDS`): decay each notable event's contribution
  by age and combine (max-of-decayed, or sum capped at 100). Keep the live
  `latest_score` as a secondary caption ("latest request: N").

### E. Overview: unique-IP diversions, pool counts, auto-refresh
- **unique IP diversions:** `security_events` diversion entries carry a
  detail string; add `unique_diversion_ips()` to `core/overview_stats.py`
  (parse the IP out of the event) and show a "Unique attackers diverted"
  card instead of / alongside raw diversions.
- **pool counts:** reuse `core/pool_view.parse_snapshot` +
  `redis_inspect.pool_snapshot` (already used by Pool Scaling) to show
  used / available / preparing pools (`PoolOverview.ready/free/building`).
  Fetch off-thread via `Job`, same pattern as Pool Scaling.
- **auto-refresh:** add a `QTimer` (while visible) that re-runs
  `_refresh_counts`, the pool fetch, and re-applies the last status — so the
  "(1h)" windows and "… ago" captions stop drifting (also covers
  improvable2 #8).

### F. Workloads: stack view default; lock honeypot-layer while up
- **Now:** `ui/page_services.py` `_tab_view = True` (tab view default); the
  layer `QComboBox` is always enabled and `_on_layer_selected` prompts to
  recreate when the stack is running.
- **Plan:** default `_tab_view = False` (stack view), fix the toggle
  button's initial label accordingly. Disable `layer_combo` whenever any
  edge target is running (derive from `apply_status`/`_last_status`) and
  show a note ("stop the ids stack to reconfigure the layer") next to it;
  re-enable when the edge stack is down.

### G. Always-visible Ctrl+K command-palette button
- **Now:** the palette is reachable by `Ctrl+K` and View → Command palette
  only. The header bar (`_build_header_bar`, `ui/main_window.py:428`) has a
  crumb row with room on the right.
- **Plan:** add a small "⌘K Search" button to the right of the header's
  crumb row, wired to `_show_palette`, present on every page.
