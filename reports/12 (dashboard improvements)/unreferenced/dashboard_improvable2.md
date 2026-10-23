# Dashboard — improvable functionality (round 2)

Things that **already exist and work** after the first improvement pass,
but could be meaningfully better. (Absent or compute-but-can't-act-on
functionality lives in `dashboard_missing2.md`.) Ordered roughly by
effort-to-value. Several items carry over from the original
`dashboard_improvable.md` and are now **more acute** because the sidebar
grew from 13 to 20 pages — those are marked *(carried over, now worse)*.

---

## 1. A code comment now contradicts the code it sits next to

`ui/main_window.py:186-188` still says of the security feed:

> *"No page currently displays this (see ui/security_feed.py); kept running
> since the underlying data collection is independently useful…"*

That is **false now.** The Overview page consumes the feed directly — it is
constructed with it (`ui/main_window.py:200`
`OverviewPage(state, self.security_feed)`) and its own docstring says *"this
page is finally its consumer."* A maintainer reading `main_window.py` is
told the feed powers nothing, right above the line that wires it to the
landing page. One stale comment, but it actively misleads. (Low effort.)

## 2. `Ctrl+1..9` reaches only 9 of 20 pages *(carried over, now worse)*

`_build_shortcuts` still binds `NAV_ORDER[:9]` (`ui/main_window.py:736`).
When this was first noted it was 9 of 13; after round 1 it's **9 of 20** —
eleven pages, including everything in Manage and Reporting and half of
Threat Operations, have no number shortcut. The `Ctrl+K` palette (added in
round 1) now covers all of them, so the number shortcuts are arguably
redundant — but if kept, they should land on a deliberately chosen set of
"most-used" pages, not `NAV_ORDER[:9]` by list position.

## 3. `Ctrl+R` is a silent no-op on the seven newest pages

`_on_refresh_shortcut` (`ui/main_window.py:754`) handles only `kibana`,
`patterns`, `log_search`, `redis`, `backups`, `certificates`. None of the
round-1 pages are in it: Overview, Live Events, Log Pipeline, Attacker
Sessions, Network IDS, Detection Policy, Pool Scaling. Most of those
auto-refresh on their own `QTimer`, so `Ctrl+R` doing nothing is harmless
there — but on **Detection Policy** (which has an explicit Reload) and
**Overview** (whose time-based cards drift) a user who presses Ctrl+R gets
silence. Either route Ctrl+R to each page's own refresh/reload, or show a
visible "nothing to refresh here" instead of nothing.

## 4. The README's "## Pages" section documents a different app *(carried over, now worse)*

`dashboard/README.md:41` onward still lists the **old flat sidebar**
(Services, Health, Certificates, Log Search, Settings, Learn) with the old
names and omits **every page added since** — all four round-1 Monitor/Threat
pages, Overview, the command palette, and the whole `NAV_GROUPS` structure
(Overview / Monitor / Threat Operations / Manage / Reporting). A newcomer
reading the README to learn the app learns a 6-page app that no longer
exists. The gap is now 14 pages wide. High clarity payoff, low effort.

## 5. No persistent system-status chip in the header *(carried over)*

The header bar (`_build_header_bar`, `ui/main_window.py:428`) still shows
only breadcrumb / title / subtitle. The Overview page now has the health
math (`core/overview_stats.system_summary`), but you must **navigate to
Overview** to see it. A small always-visible chip in the header
("Operational" / "Edge down" / current score), reusing exactly that
function, would give situational awareness from any of the 20 pages without
switching away from what you're doing.

## 6. Export affordance is inconsistent across the evidence tables

Live Events exports CSV (`ui/page_live_events.py:179`); the adjacent
evidence tables — Attacker Sessions, Network IDS alerts, Pool Scaling
events — have no export at all (see `dashboard_missing2.md` #6). Even
before adding the missing exporters, the three that exist and the one that
doesn't should at least behave consistently (same button, same CSV helper
in `core/`).

## 7. Many independent per-page poll timers; polling pauses only on page-hide *(carried over, evolved)*

Round 1 added a live `QTimer` to each of Live Events, Log Pipeline (15 s),
Attacker Sessions (6 s), Network IDS (8 s) and Pool Scaling (5 s), each
independently hitting Redis / docker exec / SSH on its own cadence, on top
of the shared `StatusPoller`. They correctly stop on `hideEvent`, but **not**
when the whole window is minimized or loses focus — so a backgrounded app
keeps issuing SSH round-trips. Consider pausing live refresh when the
window isn't visible, a single shared cadence, and/or a global "pause live
updates" control. (The original improvable #5 — "wired but wasted" feed —
is now resolved; this is its successor concern.)

## 8. Overview's time-based cards drift while the page stays open

"Honeypot diversions (1h)", "Notable events (1h)" and the "last event …
ago" caption are recomputed only on `showEvent` and on a new event
(`ui/page_overview.py:233` `_refresh_counts`). Sit on the Overview page for
ten minutes with no new events and the "1h" windows and the "ago" caption
quietly go stale. A low-frequency tick (e.g. every 30–60 s while visible)
would keep them honest.

## 9. Nav rail is still text-only with SOC-abstract labels *(carried over)*

The rail (`_build_nav_rail`, `ui/main_window.py:355`) is still a plain-text
`QListWidget` with no icons, now **20 entries across 5 groups** — even
slower to scan than when this was first raised at 13. The labels remain SOC
abstractions ("Global Visualization", "Pool State Store") while the hover
guides speak plainly; for the student audience a glyph per entry and/or a
one-line caption (or labels matching the guide wording) would cut the
recognition cost.

## 10. Reporting is still PDF-only, export-only, no in-app preview *(carried over)*

`ui/page_extras.py` still produces only Baskerville **PDFs**
(`:49`, `:56`) that you open externally; the "preview" is a list of what
*will* be included, not the rendered output. HTML/Markdown export, a
rendered in-app preview, and per-section selection would make it a report
*builder* rather than a one-shot button.

## 11. Font scaling / diagram keyboard access *(carried over)*

Still no app-level font/zoom setting, and the group headers are a fixed
7.5 pt (`ui/main_window.py:394`). The Global Visualization diagram is
mouse-driven (click/wheel-zoom) with no evident keyboard traversal. For a
teaching tool on varied hardware, an app zoom and keyboard access to the
diagram would help accessibility.

---

### Quick reference

| # | Improvement | Key location |
|---|-------------|--------------|
| 1 | Fix stale "no page displays the feed" comment | `ui/main_window.py:186-188` vs `:200` |
| 2 | Ctrl+1..9 reaches 9 of 20 pages | `ui/main_window.py:736` |
| 3 | Ctrl+R no-op on the 7 newest pages | `ui/main_window.py:754` |
| 4 | README documents the old 6-page sidebar | `dashboard/README.md:41` |
| 5 | Persistent status chip in header | `ui/main_window.py:428` + `core/overview_stats.py` |
| 6 | Consistent export across evidence tables | `ui/page_live_events.py:179` |
| 7 | Pause live timers off-screen; shared cadence | `page_pipeline/sessions/suricata/pool_scaling` timers |
| 8 | Refresh Overview time-based cards on a tick | `ui/page_overview.py:233` |
| 9 | Nav icons + plainer labels (20 entries) | `ui/main_window.py:355,394` |
| 10 | Report preview / formats / sections | `ui/page_extras.py:49` |
| 11 | Font scaling + keyboard diagram | `ui/main_window.py:394`, `ui/health_diagram.py` |
