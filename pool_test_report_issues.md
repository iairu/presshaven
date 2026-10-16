# Issues found in `pool_test_report.pdf`

Report generated 2026-10-16 09:05:49, target `ids (local)`, 10 windows (3 delayed), 8 browser-data clearings, run 7:11.
The run started at 06:58:35Z. All times below are run times (m:ss since that start) unless marked Z.

Sources: the PDF itself, plus pool_manager's event log (`honeypot_pool:events` in Redis, still present after the stack restart). Each point says whether it was **confirmed** from the event log or registry, or **inferred** from the PDF alone.

---

## 1. Session redirection

### 1.1 A diverted attacker escaped back to production by clearing its browser data — high
- Window E was diverted at 1:20 (session `410a41ed…`, borrowed pool 1).
- At 1:27 it cleared all site data (cookies, localStorage, sessionStorage). The clearing table records "no session afterwards".
- From 1:49 its traffic arrived as a **new** session (`da5dbf51…`) and was served by **production** until about 6:00. Only its second exploit (step 14) diverted it again.
- So a client the IDS had already flagged spent about 4 minutes on the real shop, with the same User-Agent tag, Accept-Language and IP.
- Passive-fingerprint recovery (`session_handler.request_fingerprint`) should have matched it back to `410a41ed…`. The recovery window is 900 s, so that wasn't the limit.
- Recovery is also inconsistent within the run:

  | Time | Window | Outcome |
  |---|---|---|
  | 0:29 | I | session recovered |
  | 0:55 | F | session recovered |
  | 1:17 | F | **fresh** session |
  | 1:27 | E | **lost** session |
  | 4:26 | E | session recovered |

  Both failures fall inside the 1:04–2:31 window when two pools were being built in parallel.
- **Inferred, cause not determined.** The proxy logs from the run were lost when reverse_proxy restarted.
- Candidates, all from the fingerprint fields: the fingerprint is re-bound on *every* request (`bind_fingerprint_to_session`). A sub-request whose `Accept-Encoding`, protocol version or TLS parameters differ (XHR, Store API cart read, prefetch) would move the pointer to a fingerprint the next navigation doesn't produce.
- **Suggested:**
  - Log the fingerprint source fields on bind and on a recovery miss.
  - Consider a sticky "diverted" flag keyed by the stable parts (UA + Accept-Language + IP) for sessions that are honeypot-bound, so a bound attacker can't return to production by clearing cookies.

### 1.2 A new pool went to an abandoned session while a live one waited — high (confirmed)
- Event log at 07:00:47Z (2:12): `handoff pool 5 → session 410a41ed…`. That is E's session from 1.1, which no browser was using any more.
- Window G (`b6e0f2d8…`) had been waiting for its own pool since 1:54. It only got pool 7 at 3:33: pool_manager measured 99 s, while pool 5 would have meant about 18 s.
- **Cause:** the handoff picks the oldest entry of `honeypot_pool:waiting`, and `prune_waiting()` only drops entries whose assignment key is gone. That key has a 24 h TTL, so a session whose client vanished keeps its place in the queue.
- **Suggested:**
  - Skip or prune waiting sessions that haven't sent a request recently (e.g. > 60 s; the session record has a last-activity time). Or have the router refresh the waiting score on each request and treat stale scores as gone.

### 1.3 Window E ended up holding two pools
- **Confirmed** from the registry and events:
  - E's abandoned session `410a41ed…` owns pool 5.
  - E's new session `da5dbf51…` was round-robined into F's pool 6 at the resource limit.
- One attacker therefore consumed one pool and shared another, and pushed I onto a shared pool (1.2 / 2.2).

---

## 2. Resource delegation

### 2.1 The resource budget stops scaling at a quarter of real memory use — medium
- `POOL_MAX_MEMORY_MB=12288` was reached at 8 pools (2:44), because each pool is charged its container limits: 1536 MB / 1.5 CPU.
- Measured use of all honeypot containers at that point (Figure 5):

  | Pools | Measured memory | Per pool |
  |---|---|---|
  | 8 | 3,357 MB | ~420 MB |
  | 4 | 1,736 MB | ~430 MB |

- So scaling stopped with about 3.4 GB actually in use out of a 12 GB budget. `POOL_MAX` (10) was never reached.
- CPU peaked around 175 % of one CPU, and only while pools were being built.
- **Suggested:** either budget on measured usage (docker stats) with the limits as a ceiling, or document that the budget is reservation-based and size it accordingly. At the current per-pool cost, 10 windows with their own pools need about 16.5 GB.

### 2.2 One of the 8 budgeted pools was wasted for the rest of the run — medium (confirmed)
- Pool 5 (see 1.2) served a dead session.
- After the limit, delayed window I was assigned to pool 5 round-robin. I therefore shares a pool with a session no browser uses: effectively its own pool, but the registry counts 2 owners and the pool can't be reclaimed.

### 2.3 The forced scale-down left that pool running — medium (confirmed)
- `released` events at 07:05:25Z cover only the windows' **current** session ids. `410a41ed…` was never released.
- Pool 5 therefore stayed: "Pools 8 → 4 (… → 1, 2, 3, 5)". It will only go after `POOL_IDLE_TIMEOUT_SECONDS` (30 min).
- **Suggested:** release every session id a window had during the run (they are in the samples and the clearing table), not just the last one.

### 2.4 The "wait for pools" feature couldn't do anything in this configuration — low
- 7 immediate windows plus the spare already used all 8 budgeted pools, so the pre-build request for the 3 delayed windows found the limit reached. The report says: "1 of 3 ready after 10 s (growth capped)".
- Only H got a pre-built (spare) pool; I and J went round-robin. The scenario "delayed windows get their own pool" was never exercised.
- **Suggested:** have the page warn when `windows + spare > room` before starting the run, or size the budget for the run.

### 2.5 Build parallelism delayed G's build — low (confirmed)
- G started waiting at 1:54, but pool 7's build only started at 2:13: pools 5 and 6 held both `POOL_PARALLEL_BUILDS=2` slots until pool 5 finished at 2:12.
- Combined with 1.2, the pool built for G reached it at 3:33.

### 2.6 The run didn't start from the baseline 3 pools — low
- Figure 5 shows 4 pools running at 0:00: pool 4, a runtime pool left over from before the run.
- D took it, so the scale-up numbers are offset by one pool compared with a clean start.

---

## 3. Accuracy of the report's own data

### 3.1 Case B lists H, which was never shared — medium
- "B. Resource limit reached" lists **Attacker H, pool 8, shares with a session outside the test**.
- The registry at export time says pool 8 had **1 owner**: H got the free spare exclusively.
- The rule "diverted while capped ⇒ round-robin" ignores that a free pool can still exist when growth is capped. The summary's "4 window(s) share a pool for good" should be 3 (E, I, J).

### 3.2 E's case A outcome is wrong — medium
- Case A says E "limit reached: stays shared (case B)" after borrowing pool 1 from 1:26 to 1:49.
- In fact E lost its session at 1:27 (1.1), while the limit was only reached at 2:44.
- The timeline merges E's two sessions into one row: `sid_of` keeps the window's last session id. As a result:
  - case B says E has shared pool 6 "since 1:26", but it was diverted into pool 6 around 6:00 with a different session;
  - E's borrowing is matched against a hand-off that went to its old session.
- **Suggested:** build timelines and cases per session, and show a window's session change as its own event.

### 3.3 Pool 5 drawn as exclusive although it has 2 owners — medium
- Figure 1 and the verdict count only test windows, so pool 5 is drawn green ("belongs to that window alone") with "Attacker I • 2 owner(s) in Redis" written inside it.
- The verdict lists only pools 4 and 6 as shared.
- **Suggested:** a pool whose Redis owner count is above the number of windows on it is shared too, and should say with whom (here: E's abandoned session).

### 3.4 Wrong pool owners, and designed borrowing flagged as cross-traffic — medium
- Evidence and the cross-traffic findings say "Pool 4 (owned by window J) also served window(s) D". D owned pool 4 first; J was round-robined onto it. The owner map (`{f.pool: f.label[-1]}`) keeps the **last** window, not the first owner.
- "Pool 1 also served E", "Pool 2 also served F" and "Pool 3 also served G" are the designed case-A borrowing. "Pool 6 also served E" is case B.
- All of these appear among the Result findings as if they were leaks.
- **Suggested:** mark cross-traffic that the borrow/shared cases explain as expected, and keep the findings for unexplained traffic.

### 3.5 Window-measured borrow times run 4–18 s late — low
- Figure 4's caption says "as seen by the window (2 s resolution)". During attack steps, routing is only read once each step settles, so the first borrowed sample is late:

  | Window | Assigned (event log) | Report's "From" | Manager's wait | Report's wait |
  |---|---|---|---|---|
  | F | 1:31 | 1:49 | 63 s | 48 s |
  | G | 1:54 | 2:02 | 99 s | 95 s |

- **Suggested:** compute borrow waits from the hand-off event (waiting since = `at − waited`) and use the window samples only as a cross-check. Also fix the caption.

### 3.6 A spare is credited with building pool 6 — low (confirmed)
- Pool 6 (started 1:23) is labelled "spare", but it was started because E's session began waiting at 1:20.
- `reconcile()` counts the in-flight pool 5 (itself a spare) as covering the waiter.
- Figure 3 and the build table therefore show 3 of 4 builds as spares, when they were built on demand.

### 3.7 The clearing summary leaves one clearing out — low
- "8 clearing(s): 6 kept their session, 1 got a fresh one" adds up to 7. The eighth (E at 1:27, "no session afterwards") isn't counted, although it is the one that mattered (1.1).

### 3.8 Six cart reads timed out during the pool builds — low
- "Cart could not be read": windows 2 and 10 in step 6, 8 in step 7, and 7, 8 and 10 in step 8. All fall between 1:00 and 1:50, when two pools were being built at once.
- That fits the 6 s synchronous Store API read timing out under host contention.
- They appear among the Result findings like real problems.
- **Suggested:** retry once with a longer timeout, and report these as "not measured" rather than as findings.

### 3.9 Page-load latency can't support conclusions — low
- Samples: borrowed n=5, shared n=7. All 10 windows load at once on one machine, so the times include QtWebEngine rendering contention.
- Production's median (3.34 s) is higher than own-pool (2.61 s). The likely reason is that production loads include the cold first loads and the add-to-cart redirects.
- If a real gap remains after controlling for that, it would be a timing tell between production and honeypot.
- **Suggested:** time only identical requests (e.g. the same product page), sequentially per window, and repeat them per state.

### 3.10 "Pools running" counts pools still being built — low
- Figure 5's pool count rises when a pool's first container starts (pool 5 at 1:04), not when it becomes ready (2:12). The panel should be labelled "pools with containers" or count only registered pools.

### 3.11 Database activity isn't attacker activity — low
- Pools that received about 33 requests show around 11,000 queries.
- Healthchecks (a WordPress page load every 30 s per pool), WP cron and content sync dominate the MySQL `Com_*` counters, so "Database activity" says nothing about what the attacker did.
- **Suggested:** subtract a per-pool idle rate, or show queries in the attacker's request windows only.

---

## 4. Test coverage / deception fidelity

### 4.1 The upload-RCE presets don't upload anything
- B's (`CVE-2025-47577`) and H's (`dnd-wc-upload-file … shell.php`) exploits are GET probes that returned 404.
- "Files changed: no files written" for every pool is therefore expected, and doesn't show that the honeypot contained an upload. File-write capture wasn't exercised in this run.

### 4.2 Most exploit endpoints answer 404/400 inside the honeypot
- 404: A (`advanced-form-integration`), D (`wp-automatic/inc/csv.php`), B.
- 400: E, F and G's `admin-ajax` actions.
- Every exploit still diverted, so routing worked. But an attacker learns from these responses that the targeted plugin isn't installed, which weakens the deception and yields little attacker interaction to record.
- **Suggested:** check whether production answers the same. If the honeypot pools are meant to look vulnerable, they need the plugins, or decoy endpoints that respond plausibly.

### 4.3 Cosmetic
- The exploit list in the header puts "J: GENERIC-XSS-001" before "I: GENERIC-SQLI-001": I needed 2 attempts, and the list follows completion order.
