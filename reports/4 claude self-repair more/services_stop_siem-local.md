# Issues: services_stop_siem-local.pdf

Service shutdown report, target `siem (local)`, 12 s window, 5 pages.

## Data / correctness

1. **The "Stopped: down command finished" screenshot still shows `es01` and `vector_inbound` up (green).** But the event log has them stopped at 8 s and 7 s, and the screenshot was taken at siem uptime 32m 19s, 12 s after "Before". The page is stale, or the capture is taken too early.
2. **The "Stopping" screenshot looks the same as "Before".** It was taken at uptime 32m 11s, ~4 s in. It still shows `kibana` up and `kibana_dashboards_setup` present, although both were stopped/removed at 2 s (marker 1).
3. **Errors are shown in screenshots but not reported.** There is no Warnings / "No warnings" banner, although the "Before" screenshot shows a red error badge on `kibana`.
4. **"removed" events are missing.** `compose down` removes every container, but only `kibana_dashboards_setup` gets a "removed" event. `kibana`, `vector_inbound` and `es01` only get "stopped".
5. **The time axis ends before the window does.** It ends at 8 s (marker 3 sits on the right edge), but the recorded window is 12 s.
6. **Host sampling is very sparse.** There are only 14 samples in 12 s, and no host data for the first ~1.5 s. es01 CPU has long straight segments (e.g. ~2.2 s → ~4.2 s) between samples.
7. **The CPU peak label doesn't match the plot.** It says "CPU peak 12% @ 6s (near marker 2)", but the dot is plotted at ~6.8 s on the axis.
8. **Container lines end before their "stopped" event.** `vector_inbound` ends at ~5.3 s but is stopped at 7 s.
9. **The 1.5 s grouping rule is broken.** Markers 2 (7 s) and 3 (8 s) are 1 s apart but have separate numbers.
10. **es01 memory is flat at exactly 3072 MiB** (3 GiB) for most of the window, which looks like it is pinned at its memory limit. Its peak in the start report was 2135 MiB. Worth stating or checking.
11. **Per-container stats lack sample counts.** `kibana` 580 ± 0 MiB / 4.7 % CPU comes from only ~2 samples (its line ends at ~1.7 s).

## Charts / readability

12. **The x-axis labels are confusing.** They read 0s, 2s, 3s, 5s, 7s, 8s: a 1.6 s step rounded to whole seconds, so the gaps look uneven. Y ticks are also odd (42/84/126/168).
13. **es01 dominates the memory chart.** `kibana` and `vector_inbound` are short flat lines near the bottom.

## Layout / typesetting

14. **Orphaned headings:**
   - "1. Overall system (host)" at the bottom of page 1.
   - "Before: stack idle / not yet changed" at the bottom of page 3.
   - "Stopped: down command finished" at the bottom of page 4.
15. **The `ids (local)` "no containers found" tile renders differently** (narrower, text clipped) in the "Stopped" screenshot than in the other two.
16. **The Event key table has odd column widths.** The Marker and Elapsed columns are very wide.
17. **Global Visualization screenshots are too small to read.**
18. **Section 4 "Event log" repeats the Event key** in a larger font and a narrower table.
19. **Figure 1 shows the whole architecture**, but only the SIEM box is relevant to this target.
