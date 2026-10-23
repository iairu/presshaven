# Pool test report – issues (round 4)

Report: `pool_test_report.pdf`, generated 2026-10-17 11:45:53, 10 windows (3 delayed), 37 pages.
This run came after all the round-3 fixes. Its overall result is EXCLUSIVE: every window ended on a pool of its own, reassignment after the scale-down worked for all 7 windows, and every cart stayed intact until its window cleared its cookies.

## 1. A delayed window was diverted by the tamper test before its own attack

- User H is a delayed window: it should stay on production until step 12. The random tamper schedule, however, gave it three tamperings in a row:
  - step 3: cleared cookies
  - step 4: hijack attempt, rejected, +50
  - step 5: forged cookie, rejected, +50
- The two rejected forgeries brought H's score to 100. The router diverted it at step 5, and it borrowed pool 3 from 0:51 (Figure 2, case A table).
- The knock-on effects:
  - H was not on production when it attacked in step 12.
  - The pre-build for the delayed windows only reached "2 of 3 free", because H already had pool 5.
  - Step 11 reads "while its pool is built …" under H, I and J.
- The test's assumption breaks. A window should get at most one rejected cookie forgery, so that tampering alone cannot push it over the threshold.

## 2. A diversion caused by tamper score is credited to an attack the window hadn't sent yet

- From step 5 to step 11, H's routing badge says "why: score over the threshold, from its CVE-2025-2266 request". H sends CVE-2025-2266 only in step 12.
- The cause was the score from the rejected forgeries, so it should say so, for example "from its rejected forged cookies".

## 3. Step tables split their screenshot row onto the next page

- On several pages the second table of a step loses its screenshot row to the next page, leaving the rest of the page blank with only the table's column lines:
  - step 5 F–J (p. 19)
  - step 7 A–E (p. 21)
  - step 12 F–J (p. 29)
- Keep-together does not move such a table whole. It measures the table from its top to the bottom of its last row, and that span includes the gap Qt left at the page break. The measured height is therefore over the 60 % limit, and the table is treated as too tall to move.

## 4. The pattern table splits a row across pages, and its narrow columns break IDs

- The "Patterns run per window" table is built in chunks of 10 rows. Its last row (J, CVE-2024-1071) is split across pages 13 and 14, and "SQL injection 1" ends up alone on the next page.
- The Pattern column wraps IDs mid-number ("CVE-2024-2795 / 6", "CVE-2022-073 / 9"). The "diverted after 1" badge wraps too, with the "1" on its own line.

## 5. Figure 2 lists every removed pool twice

- Under "Pools built / removed", pools 4–10 each have a build row. Then pools 10…4 get seven more rows, each holding only a tiny brown removal tick near 7:35.
- A removal should be marked on the row of the build it ends. Only a pool not built during the run should get a row of its own.

## 6. An attack page cut off by a network change stays an error page, and its cart is lost

- Step 6: User D's attack page failed with "Your connection was interrupted" (ERR_NETWORK_CHANGED). This happened while pools 4 and 5 were being built.
  - The request did reach the honeypot: pool 1 logged D's csv.php request with a 404.
  - Since round 3, an attack is never retried, so the step screenshot is Chrome's error page.
  - The cart read timed out twice, so the cart is "unreadable" and the cart grid shows "?" for D at step 6.
- A connection error (unlike an HTTP error answer) means the browser never got the page. One more try is harmless: a honeypot sees the same request twice. With that try the page loads, and the cart is read from it as usual.

## Status

| # | Issue | Status | Commit |
|---|-------|--------|--------|
| 1 | Delayed window diverted by tampering | Fixed: tamper events go to different windows first, and no window forges its cookie twice. The pre-build outcome is stated once, in the step text. | 38130115, 0911d01d |
| 2 | Tamper-score diversion credited to a later pattern | Fixed: the badge names the rejected forged cookie(s) until the window has sent its pattern. | b2977a7f |
| 3 | Step tables split before the screenshot row | Fixed: a table's height is measured without the page-break gap, so it moves whole. | 97e649bf |
| 4 | Pattern table row split, IDs wrapped | Fixed: chunks of 6 rows; Pattern, Routing and Pool cells don't wrap. | 417a3b0a |
| 5 | Figure 2 lists every removed pool twice | Fixed: a removal is marked on its pool's build row. | 77e46e62 |
| 6 | Attack page cut off by a network change | Fixed: an attack is retried once after a connection error, never after an HTTP error answer. | 0de0c162 |
