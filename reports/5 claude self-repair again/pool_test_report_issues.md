# Issues: pool_test_report.pdf

Segmentation Validation report, target `ids (local)`, 10 windows (3 delayed), 9:49 run, 26 pages.
Generated 2026-10-17 08:29. Verdict: EXCLUSIVE.

## Observed during the run

1. **ERR_NETWORK_CHANGED while pools are added; a refresh fixes it.**
   - Windows land on Chromium's error page whenever pool_manager builds a pool. Each build creates containers and their veth interfaces over about a minute, and Chromium cancels requests in flight on every interface change.
   - The current retry (3 tries, 0.8 s apart, in `_load_all` / `_load_one`) is much shorter than one build's interface churn. A load can fail on all attempts while a pool is still coming up.
   - Pages left on the error page are only fixed by the next scripted navigation, or by hand.
   - Fix direction:
     - Back off longer (e.g. up to ~10–15 s in total).
     - Before each step, detect windows sitting on an error page (`chrome-error://`, or `loadFinished(false)` remembered per window) and reload them.
     - Have the report count how many loads failed and needed a retry.

2. **After the forced scale-down, most windows show 502 Bad Gateway instead of being reassigned to a remaining pool.**
   - Likely cause (`ids/reverse_proxy_enhanced/lua/pool_router.lua`):
     - Every nginx worker caches session → pool in `ngx.shared.honeypot_routes` for `LOCAL_CACHE_TTL = 300` s. pool_manager's release deletes `honeypot_pool_session:<sid>` in Redis, but nothing clears these cached entries.
     - `get_or_assign_pool()` returns the cached pool through `find_healthy_pool()`, which only checks health status, not whether the pool is still in the ready list (`pool_ids()`).
     - `pool_router_rules.is_health_status_healthy()` treats a missing status, or one not updated for more than 60 s, as **healthy**.
     - So a removed pool counts as healthy, and the request is proxied to a container that no longer exists, which returns 502.
   - Fix direction:
     - Treat a cached pool that isn't in `pool_ids()` as a cache miss.
     - Have the removal clear the cached route, or publish a "pool removed" generation the workers check.
     - Treat a pool missing from the ready list as unhealthy rather than optimistic.

2b. **vector_outbound (most of all) and suricata_ids keep using a lot of CPU after the run ends, and reverse_proxy keeps logging.**
   - The windows never stop sending requests. The pasted reverse_proxy log is from 06:32:20 UTC (08:32 local), three minutes after the report finished (08:29). In it, windows B, D, H, I and J each fetch `GET /wp-json/wc/store/v1/cart` in the same second.
   - That is the page's own refresh timer: `_poll` (every 3 s) → `refresh_decisions()` → `_refresh_cart_labels()` runs a cart request (`_CART_JS`) in every window that is on an `http` page.
     - After the forced scale-down the windows are left on the shop (the reassignment step loads it), so this goes on for as long as the page is open: ~3 requests per second from 10 windows.
     - Clearing their cookies afterwards doesn't help: fingerprint recovery brings the old flagged sessions back (e.g. `a26db334…` = User J, risk 100, route honeypot), so they are re-bound to the remaining pools.
     - This also keeps those pools busy, so idle scale-down never fires.
   - **The volume is multiplied by logging.**
     - Each request produces ~10 `info` lines in reverse_proxy (`[REQUEST START]`, `[SESSION] Updating…`, `[HEADER_FILTER] …` twice, separators, the access line).
     - nginx.conf logs at `info` **twice**: `error_log /var/log/nginx/error.log info;` and `error_log /dev/stdout info;`.
     - vector_outbound reads both: the stdout copy through `docker_logs` and the file through `nginx_error_in`. Every line is parsed, tagged and shipped twice, which explains vector_outbound's CPU.
     - Suricata inspects the same steady stream on the bridge.
   - **"Errors here and there":** none of the pasted lines is at error level. But everything nginx writes at `info` goes to `error.log`, and vector tags all of it as `nginx_error`, so routine request traces show up as nginx errors in the SIEM.
     - Real error lines may be among them, e.g. the 502s from item 2; grep `[error]`/`[crit]` to check.
     - The pasted lines also contain no error words, so they don't add to the red badge.
   - Fix direction:
     - Stop the cart and decision polling once a report finishes, or when windows are on `about:blank`. Leave the windows on `about:blank` after the export, as the scale-down step already does before it reloads them.
     - Make `refresh_decisions()` read Redis only, without requests from the windows. Or poll carts only when asked: a "Refresh carts" button, or reading carts only after a step.
     - Lower nginx's default to `notice`/`warn` with an opt-in debug level. Drop one of the two `error_log` targets (or have vector read only one).
     - Don't label `info` lines from `error.log` as errors in vector.

## Data / correctness

3. **The report says the post-scale-down reassignment succeeded (the 502s above).** Page 9 ("Reassignment after removal"):
   - 6 of 7 windows are listed as "production (fresh session)", all with a green **reassigned** badge, and the closing sentence says every window "was moved to a surviving pool or given a fresh session".
   - `_forced_scaledown()` writes "production (fresh session)" whenever `d.pool is None`. It never checks whether the session actually changed, nor the HTTP status or title of the page that loaded. So the report cannot see the 502s from (2).
   - It should record:
     - the status of that load (or the page title / error page),
     - whether the session id changed,
     - where the window really ended up,
     and flag a 502 as stranded.

4. **Flagged attackers walk back to production with a clean slate after the scale-down.**
   - A window that had been diverted (score 100) comes back as a fresh, zero-score session on production. Even where the session was kept, it is routed to production.
   - The forced scale-down releases the sessions, which deletes their assignments; in normal operation idle scale-down does the same.
   - The verdict stays **EXCLUSIVE**, and nothing says a diverted attacker escaped the honeypot.
   - Either:
     - the risk state should survive a release, so a returning flagged session is re-diverted to a surviving pool (round-robin), or
     - the report should state this as a finding rather than as success.

5. **Window A had score 65 before it attacked.** Step 2 ("Every window fills its cart") shows `User A: PRODUCTION, no pool, score 65`; every other window has 0.
   - Window A is the one that runs the product-ID lookup (`product_ids_js`, a synchronous Store API request with `per_page=100&slug=…`), plus the new retry and reload around it.
   - The test's own setup request is being scored as suspicious, close to the diversion threshold. A window could be diverted before its attack.
   - Either make the lookup look like normal browsing (e.g. read the IDs from product pages), or run it outside the windows, then reset the score before step 3.

6. **Storage clearings tested nothing.**
   - 3 of the 4 clearings were "cleared its localStorage and sessionStorage" with **0 storage entries** removed: the shop stores nothing there, so these are no-ops reported as "kept its session".
   - This run had no `forge_storage` event at all, so it only had 2 forgeries.
   - Either:
     - seed some storage first, so clearing has an effect, or
     - drop the storage-only variant and weight the schedule towards cookie clearing and forgeries,
     and say "nothing to clear" when the count is 0.

7. **A recovered session doesn't get its cart back.** User J cleared its cookies before step 6. The fingerprint recovered its session ("kept its session"), but its cart stays empty for the rest of the run, because the cart lives only in the `fh_cart` cookie. That is expected under the current design, but worth deciding on: the server could restore the cart for a recovered session.

8. **The forgery hijacked a production session.** User G forged its cookie to claim User D's session while D was still on production (score 0). A hijack attempt is more telling when it claims a **diverted** session (a pool owner): that is the session an attacker would want, and success would show as a pool change. Prefer, or at least sometimes pick, a diverted target.

9. **Tamper scoring changes the run.** Both forgeries were scored +50 (stable signing key):
   - User G sat at score 50 on production from step 5 until its attack.
   - User E was already on pool 7.
   - This is valid behaviour, but the report should mention it under the windows' scores. Otherwise an unexplained "score 50" appears in steps 5–8.

10. **Pre-build counts.** "Pre-build for the delayed windows: 3 pool(s) ready after 100 s", but only pools 9 and 10 were built as "reserve". The third was spare pool 8, built earlier. The table should say "2 built + 1 spare", or the timing should cover only what was built.

11. **Scale-down summary.** "10 → 3 pool(s)" while the text says pools above the spare count (1) are removed. The 3 left are the compose-declared pools 1–3 ("only freed, never removed"). State that next to the numbers, so 3 ≠ 1 doesn't look like a bug.

12. **Pattern table order.** In the first-pattern block, window J comes before window I (pattern rows are in run order). Sort by window, or label the order.

## Charts / readability

13. **Figure 5 axes have odd ticks**: memory 0 / 8,387 / 16,775 MB, CPU 0 / 7 / 15 %, pools 0 / 6 / 12. Use round steps, like the fix in the services report (`startup_events.nice_axis`).

14. **Figure 2 step numbers bunch together.** Steps 1–10 all sit in the first ~2 minutes and overlap ("1 2", "3 4", "5 6 7").

## Layout / typesetting

15. **The 10-window step tables are wider than the page.** Every "Step N" table (pages 13–22) cuts off User J's column at the right edge ("Use", "Browse the sho", "PROD UCTI N", "no poo"), along with its screenshot and cart. With 10 windows, split the table into two rows of 5, or shrink the columns.

16. **Badges break mid-word.** "PRODUCTION" wraps as PROD / UCTIO / N and "HONEYPOT" as HONE / YPOT in every step table; "on production" wraps as "producti on" in the cart table. Use a shorter label (PROD / HP), or a smaller font in narrow columns.

17. **The cart persistence table is unreadable at 10 windows** (pages 9–12): the step column wraps ("windo ws", "CVE-2 024-2 387") and the table runs four pages. Consider a compact grid (✓ / ◆ / ✗ with the pool number) and a short legend.

18. **The tamper table has very long rows.**
    - The "cleared its cookies" row lists all 10 cookie names, including `wp_woocommerce_session_86a9106ae65537651a8e456835b316ab`, and spreads over two pages.
    - The Tampering and Before step columns break words ("sessionStora ge", "CVE-2024-2 7956").
    - Show only the session-relevant cookie names, or a count with SERVERID first, and widen those columns.

19. **Action cells are long.** "First forged its session cookie … (rejected (bad_signature, scored +50 as tampering); kept its session, served by production); then looks at the FAQ" fills a whole narrow step-table cell. Use a short marker in the step table (e.g. "◆ forged → rejected") and leave the detail to the tamper table.

20. **The Windows table on page 2 splits** after User D (row "PoolTest/D" continues on page 3). The pagination pass from the services report (`core/report_pagination.keep_together`) isn't used here yet. The same applies to headings and figure captions across this report (e.g. Figure 2's caption is split across pages 5 → 6).
