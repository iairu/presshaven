# Issues: pool_test_report.pdf (second run)

Segmentation Validation report, target `ids (local)`, 10 windows (3 delayed), 8:25 run, 33 pages.
Generated 2026-10-17 09:32:33, after the fixes from `pool_test_report_issues.md`, but before the
Suricata feedback-loop fix (`5685ef56`) and the healthcheck change (`c94ab883`).
Verdict: EXCLUSIVE.

What now works: every pool's evidence shows only its own window, there is no 502 after the
scale-down, the reassignment table records HTTP 200 with the same session for all seven
windows, both cookie forgeries were rejected, the step tables fit the page, and the cart grid is
one page.

## Data / correctness

1. **The reassignment check after the scale-down leaks into the run's statistics.**
   - At 8:24, after the forced scale-down, the reassignment step sends the windows back to the
     shop. The flagged sessions find no free pool, so the router puts them on a surviving pool as
     "borrowed (waiting)", and pool_manager starts building pools for them.
   - Those post-run samples are counted as if they were part of the test:
     - **Result:** three findings, "User H/I/J borrowed pool 1/2/3 although pools had been
       pre-built for the delayed windows". This is false: H, I and J got pools 8, 10 and 9 at
       once in step 12 (see the step table and Figure 2).
     - **Summary row "Round-robin while not scaled yet (case A)":** "4 window(s) borrowed a pool".
     - **Section A table:** User F/H/I/J "borrowed from 8:24 until end of run, still waiting".
     - **Figure 4:** four "still borrowing … at the end" rows.
   - In the actual run nobody borrowed: D–G took free pools 4–7, and H–J took pre-built ones.
   - Fix: end the run's sample window at the scale-down request. Treat the reassignment check's
     reads as their own observation, used only by the reassignment table.

2. **The scale-down rebuilds pools, and the report shows them as failed builds.**
   - The same reassignment check makes pool_manager build pools 4 and 5 for the "waiting"
     sessions (seen live: built at 07:33:20 UTC, about 50 s after the report was saved).
   - In the report:
     - **Build table:** "4 / 5, waiting session, 8:19, — – failed: -", with no reason.
     - **Summary row:** "3 built, 2 still building".
     - **Figure 2:** faint build outlines for pools 4 and 5 at the right edge.
   - Nothing failed; the export just ended first. The run also leaves these freshly built pools
     behind (about 1.4 GB, plus two more spares) until the 30-minute idle timeout. That was the
     load after the run reported earlier.
   - Fix:
     - After the reassignment check, release the windows' sessions again, wait for any builds it
       started, and run a second forced scale-down.
     - In the report, don't call a build that was still running at export time "failed": say
       "still building at export" (or leave out builds started after the scale-down request).

3. **Failed page loads are high and not traceable.**
   - "92 failed attempt(s), retried with back-off; 17 still failed after every retry."
   - That is with only 5 pool builds during the run (pools 4–7 already existed), so far more
     than one burst of `ERR_NETWORK_CHANGED` per build. The Suricata/Vector feedback loop that
     was running then (Docker networking under heavy load) is a likely contributor; this needs a
     rerun with that fix.
   - The report doesn't say which steps or windows were affected, or whether any step's data
     (routing read, cart read, screenshot) came from an error page.
   - The counters look off too:
     - "fixed by reloading before the next step" never appears, so `load_recovered` is 0.
     - `_recover_error_pages()` → `_load_one()` adds to `load_failures` and `load_unrecovered`
       again on every failed reload, so one bad load can be counted several times.
   - Fix:
     - Count per load, not per attempt; record (step, window, url, final outcome).
     - List the unrecovered loads by step and window.
     - Mark step cells whose screenshot or cart came from an error page.

4. **The pre-build numbers don't add up.**
   - "3 free pool(s) ready after 81 s: 2 built for it, 0 spare(s) already free" (2 + 0 ≠ 3).
   - The third was spare pool 8, which was still building when the pre-build was requested
     (started 3:55, ready about 5:01), so it was neither "built for it" nor "already free".
   - Fix: count spares that were building at the start separately ("1 spare that finished
     meanwhile").

5. **This run had no hijack attempt.**
   - Both cookie forgeries were `forge_cookie`, each claiming an invented session id. The schedule
     guarantees "a cookie forgery", and `hijack_cookie` (claiming a real, ideally diverted,
     session) is just one of the options.
   - The hijack is the more meaningful check. With two or more windows, guarantee at least one
     hijack, scheduled after some window has been diverted.

6. **A diversion below the threshold isn't explained.**
   - Step 9: User G is on honeypot pool 7 with score 55, while the threshold is 80 (later 94).
     Window I likewise needed 2 attempts.
   - The router diverts on a CVE match or a sticky session regardless of score, but the report
     doesn't say why.
   - `Decision.reason` is read from Redis but never shown. Put the routing reason under the
     decision badge (e.g. "CVE match", "score ≥ 80").

7. **Scores drop from 100 to 94 without explanation.**
   - G and H show score 94 for several steps after being diverted, while every other diverted
     window shows 100.
   - This is the score decay (`SCORE_DECAY_HALF_LIFE_SECONDS`) or a lower first score, but it reads
     like an inconsistency. Explain it once next to the step tables, or show the peak score.

8. **"Pool registry at export time" is really the state before the scale-down.**
   - The last page shows 10 ready pools, growth capped and one owner per pool. The scale-down
     section shows the same registry going 10 → 3.
   - The section reads the state before the scale-down. Rename it ("before the scale-down"), or
     add the state after it.

9. **The cart-page screenshots in step 15 show an empty cart.**
   - All ten "Opens the cart page" screenshots show only the "Cart" heading. The WooCommerce
     cart block hadn't rendered yet when the shot was taken.
   - The cart grid (read through the Store API) is correct, but the screenshots don't back it up.
   - Wait for the cart block (or a fixed delay after `loadFinished`) before grabbing that step.

10. **Clearing rows show storage counts that mean nothing.**
    - "cleared site data: 9 cookie(s) (…), 0 storage entries": the shop keeps nothing in browser
      storage, so the count is always 0.
    - Leave the storage count out when it's 0, or say "no site storage to clear".

## Layout / typesetting

11. **Tables taller than 60% of a page still split mid-row.** In the tamper table (pages 3 → 4),
    User B's forged-cookie row breaks after "SERVERID =", and the rest of the row continues on the
    next page. Same in the pattern table (pages 11 → 12): "WP Automatic SQL | injection". The
    page-break pass only moves whole tables up to 60% of a page; taller ones split anywhere, even
    inside a row. Options: split long tables into chunks (e.g. a new table every N rows), or allow
    whole-table moves up to ~90% of a page for tables that fit on one page.

12. **Half-empty page 5.** The scaling summary table sits alone on page 5 and Figure 2 starts on
    page 6, leaving about 55% of page 5 blank. The figure and its long caption are kept together
    on purpose; the blank space could go if the caption may run onto the next page after the
    figure, or if the figure is shrunk to fit.

13. **"Scale-down" heading with one line at a page bottom.** Page 8 ends with "Scale-down" and the
    first line of its 5-line paragraph; the rest continues on page 9. The heading rule keeps a
    heading with only the first line of the next block, and the short-paragraph rule covers 4
    lines at most. Keep a heading with at least 2–3 lines of the paragraph that follows it.

14. **The last page holds only "Pool registry at export time"** (4 lines). Minor; it would fit
    after the evidence section if item 8's renamed section moved next to the scale-down section,
    where it belongs anyway.
