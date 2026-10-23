# Issues: services_stop_edge-local.pdf

Service shutdown report, target `ids (local)`, 26 s window, 7 pages.

## Data / correctness

1. **The "Stopped: down command finished" screenshot still shows `session_store` up (green).** But the event log has `session_store stopped` at 23 s, and the screenshot was taken at ids uptime 30m 48s, ~29 s after "Before". The page is stale, or the capture is taken before the final refresh.
2. **The "Stopping" screenshot looks the same as "Before".** It was taken at ids uptime 30m 30s, ~11 s in. By then `vector_outbound`, `honeypot_eshop_1/2/3`, `reverse_proxy` and `suricata_ids` had already stopped (markers 1–3), but every tile is still green/blue.
3. **Errors are shown in screenshots but not reported.** There is no Warnings / "No warnings" banner (the start reports have one). The "Before" screenshot shows red error badges on `reverse_proxy` (4-digit count) and `honeypot_content_sync`, but the report never mentions them.
4. **Host sampling is very sparse.** There are only 27 samples in 26 s:
   - No host data from 0 s to ~3.5 s.
   - Then one straight line from ~3.5 s to ~8.5 s.
   So the busiest part of the shutdown is essentially unmeasured, despite the "every 0.25 s" claim (which applies to cgroups, but the container lines are equally sparse).
5. **The CPU peak label is misleading.** "CPU peak 57% @ 3s (near marker 1)": marker 1 is at 5 s, so the peak comes *before* any event. It is actually the first sample, at the start of the recording.
6. **Container lines end ~1.5–2 s before their "stopped" event**, e.g.:
   - `honeypot_eshop_2/3` end at ~6 s but stop at 10 s.
   - `production_eshop` ends at ~13.5 s but stops at 15 s.
   - All databases end at ~14.5 s, but `honeypot_database_1/2` stop at 16 s and `production_database` at 18 s.
   - `vector_outbound` ends at ~3.5 s but stops at 5 s.
   Either the event timestamps lag (Docker reports "stopped" only after the stop timeout) or sampling stops as soon as a container starts stopping. Either way it should be explained or aligned.
7. **One database is reported differently from the others.** `honeypot_database_3` is reported as "finished" at 15 s and "removed" at 16 s, while the other databases are "stopped". "Finished" is one-shot-job wording, and it isn't clear why only this one database is treated that way.
8. **"removed" events are missing.** `compose down` removes every container, but only `honeypot_database_3` gets a "removed" event.
9. **The time axis ends before the window does.** It ends at 23 s (marker 8 sits on the right edge), but the recorded window is 26 s.
10. **The 1.5 s grouping rule is broken.** Markers 5 (15 s) and 6 (16 s) are 1 s apart but have separate numbers.
11. **Stats from a few samples are shown without a sample count.** `suricata_ids` 256 % ± 82 and `vector_outbound` 242 % ± 78 with P(CPU≥50%) = 100 % come from only ~2–4 samples each, and `honeypot_eshop_2/3` 0.0 % ± 0.0 from the same few points. Add sample counts.

## Charts / readability

12. **Axis ticks are odd numbers.** X ticks are 5/9/14/18/23 s. Y ticks are 3/6/9/12, 52/105/157/210, 6/11/17/22, 66/131/197/262, 88/176/263/351, 224/447/671/894.
13. **Edge & monitoring charts:**
   - `suricata_ids` and `vector_outbound` (~300 % CPU, 700–900 MiB) set the scale.
   - The other 6 services (`backup_service`, `honeypot_content_sync`, `log_capper`, `pool_manager`, `session_store`, `reverse_proxy`) overlap along the 0 line.
14. **Lines just stop when a container stops.** There is no drop to 0 or end marker, so it's hard to see the moment of shutdown (e.g. shops memory, edge memory).
15. **Similar colours:** `suricata_ids` (indigo) vs `backup_service` (blue), and `vector_outbound` (red) vs `honeypot_content_sync` (orange-red).

## Layout / typesetting

16. **Container names break mid-word in the per-container table**, e.g. `honeypot_datab|ase_1`, `honeypot_esho|p_1`, `vector_outboun|d`.
17. **A table row splits across pages:** `honeypot_database_2` (page 4 → 5).
18. **Paragraph and heading breaks:**
   - The sentence "Grouped by role, one CPU and one memory chart per group…" splits across pages 2 → 3.
   - "1. Overall system (host)" is orphaned at the bottom of page 1.
   - "Stopping: containers going down" is orphaned at the bottom of page 5.
19. **Global Visualization screenshots are too small to read.**
20. **Section 4 "Event log" repeats the Event key** in a larger font and a narrower table.
21. **Figure 1 doesn't match the charts.** It includes the SIEM box, which isn't part of this target, and it lacks boxes for `pool_manager`, `backup_service`, `log_capper` and `honeypot_content_sync`, which are charted.
22. **Naming is inconsistent.** The file is named `edge-local` but the report says "Target: ids (local)".
