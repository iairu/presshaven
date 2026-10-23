# Pool test report – issues (round 6)

Report: `pool_test_report.pdf`, generated 2026-10-17 16:40:29, 10 windows of which **7 delayed**, 26 pages.

The overall result is EXCLUSIVE:
- Every window ended on a pool of its own, with no borrowing (case A) and no sharing at the limit (case B). Round-robin reuse assignments: 0.
- All 7 reassignments after the scale-down worked.
- The carts stayed intact.

The previous round's fixes show up correctly:
- The clean-up line now reads "leaving 3 pool(s): 1, 2, 3".
- CPU reads "1.8 % → 0.0 % of all 20 CPUs (37 % → 0 % of one CPU)".
- Figure 2 has one row per pool.
- The failed loads are broken down by step.

## 1. Every step screenshot is a 236 × 94 px strip showing only the shop's header

- In this run, every screenshot in Step by step (pages 13–20) is a thin strip: the green shipping banner and the Fernhill logo bar, nothing else. Last run's were full pages, about 120 × 300 px in the PDF.
- The embedded images are 236 × 94 px, so the browser views on screen were that size when they were grabbed.
- The worst case is step 11 ("Every window opens its cart"): the screenshot of the cart page shows none of the cart. The cart check then rests only on the cart text read through the Store API.
- The cause: the views' size follows the dashboard window. The ten frames sit in two splitter rows with `stretch=1`, and nothing sets a minimum while an export runs. A shorter dashboard window, or a splitter dragged down, gives header-only screenshots without any warning.
- Fix: while an export runs, give every view a minimum size (for example 360 × 640, scrolling the page if it doesn't fit), or render the screenshots at a fixed size independent of the window. If a grab comes out much smaller than that, the report should say so.

## 2. All 21 failed page loads come from browsing during the 7-pool pre-build

- The summary row: "21 page load(s) did not succeed at the first attempt (28 failed attempt(s)) … 21 of the 21 ran while a pool was being built or removed. By step: Pools pre-built for 7 delayed window(s) 21."
- The step 7 pre-build waits 185 s while 7 pools are built two at a time. Meanwhile every window keeps browsing (each one's cell lists about 10 pages), straight into the network-interface churn (ERR_NETWORK_CHANGED) of 7 builds.
- All the loads succeeded on retry, so nothing is broken. But the browsing produces most of the retries, and the load on the shop and pools, for no test value: no routing changes during this step.
- Options:
  - browse less often while the pre-build waits (for example one page per window per minute);
  - or skip the browsing between pool registrations;
  - or keep it and say in the report that these failures are expected for this step.

## 3. Minor: the pre-build starts late, and the run spends 3 minutes waiting

- The delayed-window count is known when the run starts, but the pre-build of 7 pools is only requested at step 7 (1:17), once A–C have attacked.
- Building two at a time, the pools were ready at 4:22. Pool 4 (a spare) had started at 0:45 and finished at 1:33 without the pre-build.
- Requesting the reserve at the start of the run (or as soon as the immediate windows are diverted) would overlap the builds with steps 3–6 and take up to about 1:15 off the run.
- The report's "Why it is slow" note (POOL_FAST_CLONE, POOL_PARALLEL_BUILDS) covers the build speed, but not this ordering.

## 4. Minor: "resource limit reached" is drawn in red although it is what the pre-build was asked for

- Figure 2 and Figure 5 mark "resource limit reached" at 3:30 with a red dashed line, and the summary says "limit first reached at 3:30".
- 3 compose pools + 7 pre-built = 10 = POOL_MAX: the pre-build was asked to fill the pool up to its maximum, so reaching it is the expected outcome, not a warning.
- The label could say so ("pool limit reached (10 of POOL_MAX=10), as planned by the pre-build"), or be drawn in a neutral colour when the limit is reached by the requested reserve and nobody was turned away (case B not observed).
