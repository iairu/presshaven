# Pool test report – issues (round 5)

Report: `pool_test_report.pdf`, generated 2026-10-17 12:31:13, 10 windows (3 delayed), 34 pages.
This run came after the round-4 fixes. The overall result is EXCLUSIVE:
- Every window ended on a pool of its own.
- All 7 reassignments after the scale-down worked.
- Every cart stayed intact until its window cleared its cookies.

The round-4 fixes held:
- The 9 tamper events hit 9 different windows, and each cookie forgery went to a different window.
- No delayed window was diverted early, and the pre-build reached 3 of 3.
- Figure 2 has one row per pool.
- No step table split before its screenshot row.
- The pattern table no longer wraps IDs.
- No step screenshot is an error page.

## 1. Two step screenshots are solid black

- Step 14 (second pattern): the screenshots of User G and User J are black rectangles.
- Both opened CVE-2024-1071 (`admin-ajax.php?action=um_get_members…`) and got HTTP 400.
- Users A and D opened the same request in the same step. Their screenshots show the white near-empty page (WordPress answers `0`), as do User E's in step 7 and User F's in step 14.
- So the page is fine, but the capture was taken before the view had painted anything. Pages with almost no content finish loading before the first frame, so the grab returns the black backing store.
- The capture should wait for a painted frame (for example a `requestAnimationFrame` round-trip, or a retry when the image is uniformly black).

## 2. The clean-up after the reassignment check leaves 4 pools, not 3

- Scale-down table, "After the reassignment check": "pool_manager started building pool(s) 4, 5 … The test released those sessions again and removed what was built for them (second scale-down), leaving 4 pool(s): 1, 2, 3, 4."
- The previous run ended on pools 1, 2, 3. Pools 1–3 are compose-declared and free, and the spare count is 1, so pool 4 is one pool more than is needed.
- Possibly pool 4 was not yet "building" or "ready" when the clean-up looked: it was starting or registering, so it was missed by the wait loop and by the second scale-down, and registered afterwards.
- The clean-up should wait until no pool is building or starting, then check that the final pool list equals the list from before the reassignment check. The report should flag it when they differ, instead of stating it as done.

## 3. "CPU in use 0 % → 0 %" rounds the pool CPU away

- In the scale-down table, the CPU row reads "0 % → 0 % of all 20 CPUs". Figure 5 shows the pool containers at about 1–3 % of all CPUs before the scale-down, with a spike of about 10 % during it.
- The row divides the pools' CPU (a few % of one core when idle) by 20 and rounds to a whole number, which gives 0.
- It should show one decimal (for example "0.4 % → 0.1 %"), or give the figure in % of one CPU when it is below 1 % of the host.

## 4. Failed page loads nearly tripled (28, up from 10)

- The summary row reads: "28 page load(s) did not succeed at the first attempt (28 failed attempt(s)), retried with back-off; every one loaded in the end."
- None of them is visible in the step tables (no "page failed to load" note). The report gives no breakdown of when, or in which step, they happened. The summary only blames ERR_NETWORK_CHANGED during pool builds and removals.
- With 28 failures, it would help to see them grouped by step and phase (pool build or scale-down), so a real problem can be told apart from Docker's interface churn.
- The report could list the failures per step, as the load log already records them.
