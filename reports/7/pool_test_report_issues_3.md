# Issues: pool_test_report.pdf (third run)

Segmentation Validation report, target `ids (local)`, 10 windows (3 delayed), 9:21 run, 36 pages.
Generated 2026-10-17 10:38:37, after every fix from `pool_test_report_issues_2.md`.
Verdict: EXCLUSIVE, with two findings about extra windows seen on pools 2 and 3.

What now works:
- **Clean run statistics:** the post-scale-down reassignment no longer pollutes them (no fake "still
  borrowing").
- **Clean-up:** the test cleaned up the pools the reassignment check started (second scale-down,
  3 pools left).
- **Reassignment:** all seven reassigned windows got HTTP 200 with their own session.
- **Tamper testing:** two hijack attempts, each claiming a diverted session, were both rejected.
- **Pre-build count:** it adds up (2 built + 1 spare already free).
- **Pool registry:** it now sits before the scale-down.
- **Layout:** no table rows split across pages.

## Data / correctness

1. **The retry logic treats an HTTP error response as a failed load and repeats the request.**
   - The 12 loads listed as "never loaded" are all pattern (attack) requests that the honeypot answered
     with a 4xx status: the 404 and 400 rows in the evidence section. The attack requests that got
     200/301 are not in the list.
   - QtWebEngine reports a page with an HTTP error status as `loadFinished(False)`, the same signal as a
     network failure. So `_load_all()` retried each of them 4 more times, and `_recover_error_pages()`
     sent it again before the next step.
   - The proxy's access log confirms this: the step-3 pattern request appears 67 times around 08:29:41,
     and each window's second-pattern request about 16 times around 08:35–08:37.
   - Effect:
     - Every 4xx pattern is sent to the honeypot many times instead of once, inflating its risk score,
       its request count and the evidence counters.
     - "60 failed attempts / 12 never loaded" in the summary is wrong: nothing failed at the network
       level.
     - The step tables put "⚠ page failed to load: screenshot and cart are from the error page" on
       windows whose screenshot is the honeypot's genuine 404 page (step 3, step 14).
   - Fix:
     - Tell a server answer from a network failure. QtWebEngine's `loadingChanged(QWebEngineLoadingInfo)`
       gives `errorDomain()`: `HttpStatusCodeDomain` means the server answered, so count the load as done.
       Only `ConnectionErrorDomain` / `InternalErrorDomain` (e.g. `ERR_NETWORK_CHANGED`) should be retried.
     - Never retry, or reload before the next step, a pattern request at all; the pattern step has its
       own attempt logic (`MAX_ATTEMPTS`).

2. **Pools 2 and 3 "also served" windows E and B.**
   - **Result findings:** "Pool 2 (owned by window B) also served window(s) E, which neither borrowed nor
     shares it" and "Pool 3 (owned by window C) also served window(s) B".
   - **Evidence:** pool 2 received window E's diverting pattern request (a 400), and pool 3 lists window B
     among the windows seen.
   - **Likely cause for E:** a short round-robin borrow that the window's routing samples never caught.
     E's diverting request landed on borrowed pool 2, and pool_manager handed E its own pool 5 before
     the next routing read.
     - The registry agrees: "Round-robin reuse assignments so far: 4", but case A lists only 3 borrows
       (D, F, G).
     - pool_manager's event log has a handoff for that session, with the borrowed pool and the wait.
   - **Window B on pool 3:** B diverted at step 4, while pools 2 and 3 were both free spares. Its repeated
     pattern requests (item 1) may have gone to pool 3 first. Needs a look at the pool-3 evidence and the
     handoff log after item 1 is fixed.
   - Fix:
     - Build case A from pool_manager's handoff events as well, not only from the sampled routing, so
       short borrows are counted.
     - Accept a window seen on a pool it borrowed per those events.
     - Re-check after item 1: repeated requests make extra visits more likely.

3. **Run time and figures include the clean-up after the scale-down.**
   - "Run time 9:21", but the forced scale-down was requested at 7:51. The extra 1½ minutes is the new
     clean-up (waiting for the builds the reassignment check started, then the second scale-down).
   - Figures 2 and 5 extend to 9:21. Figure 5's "Pools ready" line rises again to about 5 at the end
     (the clean-up's builds), although the text says 3 pools were left.
   - Fix: end the run's duration and figure axes at the scale-down's completion. Report the clean-up as
     its own short phase, or leave it out of the figures and mention it only in the scale-down table.

4. **Figure 2 shows a cookie clearing as a dip to production.**
   - User A's row goes pool 1 → grey (production) → pool 1 around its second clearing (step 10, ~4:03).
     The routing read just after the clearing found no session cookie and was classified "production".
   - The window kept its session and pool (the tamper table says so), so the grey gap is misleading.
   - Fix: classify a sample without a session (cookies just cleared) as "no session". Draw it as a gap
     or a hatched segment, not production.

5. **Cart-page screenshots still don't show the items.**
   - The block cart now renders (no 429s, so item 9 of the last round is fixed): the "Add coupons" panel
     is visible.
   - Windows B, D and E have items (the cart grid and the step table show them), but their screenshots
     show only the "Cart" heading and the totals panel.
   - The item list is probably still loading its line items (images, product data) when the shot is
     taken, or sits outside the captured viewport.
   - Fix: also wait for `.wc-block-cart-items__row` (or `.wc-block-cart-item__product`) when the cart
     isn't empty. Check whether the window's viewport is tall enough to show the rows; if not, scroll
     to them before the grab.

6. **The "why" under each diversion rarely tells anything.**
   - Almost every diverted window shows "why: score over the threshold", including windows diverted by
     a CVE pattern. A single pattern request scores 100, and the router checks the score before the CVE
     match, so `honeypot_reason` records the score.
   - Only G and H show "CVE pattern match".
   - The reason is accurate per the router, but it says less than it seems. Either:
     - show the matched pattern(s) from the session record instead, or
     - note in the step-section text that a score-based reason doesn't mean no CVE matched.

## Layout / typesetting

7. **The "never loaded" table spills onto page 6, leaving that page 55% empty.** It goes away once
   item 1 is fixed (the list would be empty or short). If any real failures remain, shorten the Page
   column, e.g. path only and truncated, so the table stays compact.

8. **Blank white screenshots in step 14.** Windows answered with a 400 and an almost empty body show an
   empty white frame. After item 1 the warning goes away, but the cell could say "HTTP 400 (empty page)"
   instead of an unexplained blank image. `_page_status()` already reads the status.
