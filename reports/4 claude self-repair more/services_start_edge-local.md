# Issues: services_start_edge-local.pdf

Service start-up report, target `ids (local)`, 92 s window, 10 pages.

## Data / correctness

1. **The "All containers healthy" screenshot is not all healthy.** It was taken at ids uptime 1m 17s (~77 s), before markers 10–11. In it `backup_service`, `reverse_proxy` and `vector_outbound` are still orange (created, never started) and `production_eshop` is light green (health pending). The capture fires too early, or the caption is wrong.
2. **The banner contradicts the screenshot.** The banner says "no service logged an error line during the start", but the same screenshot shows red error badges on `honeypot_db_seed_1/2/3` and `production_db_seed`. Either the badge counter or the warning collector is wrong, or they use different rules.
3. **Memory lines ramp up before the container exists.** Memory lines are drawn as a straight ramp from 0 at marker 1 (7 s, "created") to the first real sample. This makes it look like memory grows while the container hasn't even started:
   - One-shot memory: seeds/migration ramp from 7 s to ~33 s (they only started at 31–33 s).
   - Databases memory: ramp from 7 s to ~18 s.
   - Shops memory: honeypot eshops ramp from 7 s to ~53 s; `production_eshop` ramps from 7 s to ~80 s.
   - Edge memory: `reverse_proxy` and `vector_outbound` ramp from 7 s to ~82 s, even though they only started at 82 s.
   Fix: don't plot points before a container's first real sample, and don't interpolate across that gap.
4. **Sample gaps are drawn as straight lines.**
   - Host CPU has a long straight segment around 7–15 s (during `up --build`).
   - `init_setup` CPU drops in one straight line from 513 % at 7 s to 0 at ~12 s.
   The text claims sampling every 0.25 s, but these gaps are clearly much longer. Break the line at gaps, or mark them.
5. **The 1.5 s grouping rule is broken.** The text says "events within 1.5 s of each other share one number", but:
   - Markers 2 (17 s) and 3 (18 s) are separate.
   - Marker 4 (20–22 s) and marker 5 (23–25 s) are separate even though only ~1 s apart.
   - Markers 4 and 5 each span 2 s (chained clustering), which is also more than 1.5 s.
6. **The CPU peak label points at the wrong marker.** "CPU peak 34% @ 46s (near marker 8)": marker 8 is at 51 s, 5 s away. The peak sits in the middle of the seed phase (markers 6–8), so "near marker 8" is misleading.
7. **The window ends before the stack settles.**
   - `production_eshop` CPU is still 80–125 % at 91 s, and its memory is still climbing (297 MiB).
   - Honeypot eshop memory is still rising too.
   - `reverse_proxy` / `backup_service` / `vector_outbound` started at 82 s and never get a "healthy"/settled event, yet the report says "No warnings".
   The recording should continue until steady state, or the report should say it stopped early.
8. **Per-container stats hide how many samples they use.** For example, `init_setup` P(CPU≥50%) is 62.5 % from ~8 samples, and `backup_service` shows 0.0 % ± 0.0 / 0–1 MiB from only a few samples after 82 s. Add a sample count or active duration per row.
9. **Some marker lines are drawn dark grey/black instead of red** (e.g. the lines at ~17 s and ~23 s on several charts), but the text says "dashed red vertical line".
10. **Charts use different time axes.** The one-shot charts run 0–84 s, while every other chart runs 0–91 s, so markers don't line up vertically across the page.
11. **"Generated" is really the start time.** "Generated: 10:53:31" looks like the recording start time (the file mtime is 10:55), not the time the report was generated. Rename the label or fix the value.

## Charts / readability

12. **Axis ticks are odd numbers.** Y ticks are things like 128/257/385/513, 77/153/230/307, 27/53/80/106, 31/63/94/125, 74/149/223/297, 7/15/22/30, 40/80/121/161. X ticks are 18/36/55/73/91 s. Use round steps.
13. **One-shot CPU chart:** `init_setup`'s 513 % spike sets the y-scale, which flattens the seed lines. The >100 % (multi-core) values aren't explained anywhere.
14. **Similar colours:**
   - `production_db_seed` (dark green) vs `honeypot_db_seed_2` (teal green).
   - `suricata_ids` (indigo) vs `backup_service` (blue).
   - `vector_outbound` (red) vs `honeypot_content_sync` (orange-red).
   - `honeypot_db_migration` (blue) is almost invisible along the 0 line.
15. **Edge memory chart:** `log_capper`, `backup_service` and `honeypot_content_sync` overlap along the 0 line and can't be told apart.
16. **The host chart legend** sits far below the chart, separated by a large blank gap.

## Layout / typesetting

17. **Container names break mid-word in the per-container table**, e.g. `honeypot_datab|ase_1`, `honeypot_conte|nt_sync`, `vector_outboun|d`, `production_esh|op`. The first column is too narrow.
18. **Table rows split across pages:**
   - The host-metrics row "Host RAM used, how unusual the peak is" (page 2 → 3).
   - The per-container row `honeypot_database_1` (page 5 → 6).
19. **Orphaned headings:**
   - "1. Overall system (host)" at the bottom of page 1.
   - "Databases" at the bottom of page 3.
   - "Before: stack idle / not yet changed" at the bottom of page 6.
   - "All containers healthy" at the bottom of page 7.
   In each case the content is on the next page.
20. **Global Visualization screenshots are too small to read** at print size (tile labels and uptimes are tiny).
21. **Section 4 "Event log" repeats the Event key.** It uses a larger font, and the table is only ~⅔ page wide, which doesn't match the other tables. Consider dropping it or moving it to an appendix.
22. **Figure 1 doesn't match the charts.** The text says "the per-container graphs below track each box in it", but the SIEM box (ES/Kibana) isn't charted for this target. Also `pool_manager`, `backup_service`, `log_capper` and `honeypot_content_sync` are charted but have no box in the figure.
23. **Naming is inconsistent.** The file is named `edge-local` but the report says "Target: ids (local)".
