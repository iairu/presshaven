# Dashboard — improvable functionality

Things that **already exist and work**, but could be meaningfully better.
(Functionality that is absent or collected-but-unshown lives in
`dashboard_missing.md`.) Ordered roughly by effort-to-value.

---

## 1. The README is stale and misdescribes the sidebar

`dashboard/README.md` documents an **older flat sidebar** that no longer
matches the app:

- Its "Pages" section lists only *Services, Health, Certificates, Log
  Search, Settings, Learn* and omits Resources, Redis, Backups, Kibana,
  Patterns, Pool test, and Extras entirely.
- It uses the **old page names**, not the current labels in
  `ui/main_window.py` `PAGE_LABELS` (Workloads, Global Visualization,
  Workload Telemetry, PKI & Certificates, Pool State Store, Backup &
  Recovery, SIEM Analytics, Attack Simulation, Segmentation Validation,
  Forensics Analysis, Reporting, Connectors & Config, Knowledge Base).
- It never mentions the four `NAV_GROUPS` (Monitor / Threat Operations /
  Manage / Reporting) that the rail is now organised around.
- The "Layout" file list is missing most of today's `ui/` and `core/`
  modules.

Anyone reading the README to learn the app is learning a different app.
Low effort, high clarity payoff.

## 2. Sidebar labels are abstract; no icons; student audience

The rail is a **text-only** `QListWidget` (`_build_nav_rail`,
`ui/main_window.py:309` — verified: no `setIcon` anywhere). Two issues:

- **No icons.** 13 entries in 4 groups scan slowly as a plain text list; a
  small glyph per entry (and per group) would speed recognition a lot.
- **Label indirection.** The labels are SOC-flavoured abstractions
  ("Global Visualization", "Pool State Store", "Attack Simulation") while
  the hover tooltips/guides speak plainly ("Topology map…", "Inspect the
  proxy's live state store…"). For the stated cybersecurity-**student**
  audience (`core/learning.py:3`) the gap between the label and what the
  page actually is adds a translation step. Consider a one-line caption
  under each label, or labels that match the guide wording.

## 3. `Ctrl+1..9` covers only 9 of 13 pages

`_build_shortcuts` binds `NAV_ORDER[:9]` (`ui/main_window.py:583`). The
last four pages have **no shortcut at all**: **Backup & Recovery,
Connectors & Config, Reporting, Knowledge Base**. Either move to a two-key
scheme, or group so the 9 shortcuts land on the most-used pages
deliberately rather than by list position.

## 4. No persistent system-status chip in the header

The header bar (`_build_header_bar`, `ui/main_window.py:382`) shows only
breadcrumb / title / subtitle. From most pages there is **no always-visible
indicator** of overall health (containers up/down, current score, SIEM
reachable). The tray fires balloons, but only on container state changes
and only if a tray exists. A small persistent status chip in the header
would give situational awareness without switching to Global Visualization.
(Closely tied to the Overview gap in `dashboard_missing.md` #1.)

## 5. The security feed runs for the whole session and shows nothing

`SecurityEventFeed` tails `reverse_proxy` logs for the app's entire
lifetime and persists events, but nothing renders them (see
`dashboard_missing.md` #1). Until an Overview page consumes it, this is
**pure overhead** — a background QProcess and repeated `state.save()`
writes for data no user can read. Either surface it or gate it. Right now
it is the clearest "wired but wasted" code path in the app.

## 6. Workload Telemetry graphs are in-memory only and per-container only

`ui/page_resources.py`:

- History is a bounded `deque(maxlen=HISTORY_POINTS)` — **~5 minutes**
  (`HISTORY_POINTS = 150` at 2 s, `:31`) held in RAM, polled **only while
  the page is visible** and **lost on page switch / app restart**. You
  cannot look back at the resource impact of an attack after the fact —
  which undercuts the page's own stated purpose (annotating graphs with
  attack-simulation markers, `core/learning.py:278-283`).
- There is **no host-level aggregate** line (total CPU/RAM across the
  stack), only per-container series plus an average.

Persisting samples to disk (even a rolling file) and adding a host total
would make the attack-cost story durable and legible.

## 7. SIEM Analytics has no native fallback when Kibana is down

The page is entirely an embedded browser onto Kibana
(`ui/page_kibana.py`); when Kibana's container is down it shows an
explanatory banner and nothing else. A handful of headline numbers (total
alerts, total requests, top source IPs, production-vs-honeypot split) could
be queried **directly from Elasticsearch** and shown natively, so the
analytics surface degrades gracefully instead of going blank whenever
Kibana (or QtWebEngine) is unhealthy.

## 8. Pool State Store is read-only and shows raw blobs

`ui/page_redis.py` lists keys with type/ttl/size and a `threat_ips` bar
chart — good, but:

- Session values are shown as **raw stored blobs**; decoding them into
  readable fields (score, owner IP, bound pool, fingerprint) would turn
  inspection into understanding — exactly the learning goal in the page
  guide (`core/learning.py:290-294`).
- It is **read-only**. For a teaching tool, letting a student delete/reset
  a single key (e.g. clear one session's score) from here — with
  confirmation — would make the "the proxy's memory is just data" lesson
  hands-on. (The Attack Simulation page already has a coarse "Unpoison host
  IP"; a targeted version belongs here.)
- Only a single `threat_ips` snapshot is charted; no score-over-time, no
  TTL countdown.

## 9. Reporting is export-only, PDF-only, no in-app preview

`ui/page_extras.py` previews *what will be included* but produces a PDF you
then open externally. Consider an in-app preview of the rendered output,
and/or HTML/Markdown export options, and per-section selection, so the page
is a report **builder**, not just a one-shot button.

## 10. `Ctrl+R` refresh and `Ctrl+F` find are partial / implicit

- `_on_refresh_shortcut` (`ui/main_window.py:601`) refreshes only kibana /
  patterns / log_search / redis / backups / certificates; on any other
  page `Ctrl+R` silently does nothing. A no-op-with-reason (or a visible
  "nothing to refresh here") would be clearer than silence.
- `Ctrl+F` always jumps to Forensics Analysis (`_on_find_shortcut`). That's
  a reasonable global "find", but it means there is no in-page find on,
  e.g., the Pool State Store table or a log console, where a user might
  expect it.

## 11. Nav rail collapses to nothing, not to icons

Below 900px wide the whole rail hides behind the `☰` toggle
(`NARROW_WIDTH`, `resizeEvent`). A mid-width **icon-only mini-rail** (if
icons are added per #2) would keep navigation one click away on narrower
windows instead of all-or-nothing.

## 12. Accessibility / sizing

- Group headers are **7.5 pt bold** (`_build_nav_rail`,
  `ui/main_window.py:349`) — small, and fixed; no app-level zoom / font
  scaling.
- The Global Visualization diagram appears to be mouse-driven (click
  nodes); keyboard traversal of nodes isn't evident. For a teaching tool
  used on varied hardware, a font-scale setting and keyboard access to the
  diagram would help.

---

### Quick reference

| # | Improvement | Key location |
|---|-------------|--------------|
| 1 | README matches current sidebar | `dashboard/README.md` vs `ui/main_window.py` `PAGE_LABELS`/`NAV_GROUPS` |
| 2 | Nav icons + plainer labels | `ui/main_window.py:309` |
| 3 | Shortcuts for all 13 pages | `ui/main_window.py:583` |
| 4 | Persistent status chip in header | `ui/main_window.py:382` |
| 5 | Surface (or gate) the security feed | `ui/security_feed.py`, `main_window.py:168` |
| 6 | Persist + aggregate telemetry | `ui/page_resources.py:31` |
| 7 | Native ES fallback for SIEM page | `ui/page_kibana.py` |
| 8 | Decode/edit Redis, score-over-time | `ui/page_redis.py` |
| 9 | Report preview / formats / sections | `ui/page_extras.py` |
| 10 | Complete Ctrl+R / in-page find | `ui/main_window.py:601` |
| 11 | Icon mini-rail at mid width | `ui/main_window.py` `resizeEvent` |
| 12 | Font scaling + keyboard diagram | `ui/main_window.py:349`, `ui/page_health.py` |
