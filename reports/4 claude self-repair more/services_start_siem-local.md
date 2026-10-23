# Issues: services_start_siem-local.pdf

Service start-up report, target `siem (local)`, 52 s window, 5 pages.

## Data / correctness

1. **The "All containers healthy — but 1 warning(s)" screenshot is not all healthy.** It was taken at siem uptime 43 s (marker 6). `kibana` is still light green (health pending) and `kibana_dashboards_setup` is orange (created, never started). The capture fires too early.
2. **A WARN line is reported as an error.** The Warnings table says "kibana 1 error line(s)", but the quoted line is `[WARN ] … Error executing alerting telemetry task`. It is a WARN-level line that only matched on the word "Error". Either respect the log level or reword it as "warning/error line".
3. **The error count doesn't match the badge.** The Warnings text says the same error lines put a red badge on the tile. But the kibana tile has no badge in any of this report's screenshots, while the edge report screenshots (taken minutes later) show a kibana badge with a double-digit count. So "1 error line" and the badge count disagree.
4. **`init-password` is missing from the charts.** It ran from 22 s to 24 s and appears in the events and screenshots, but it is missing from the per-container charts, legend and stats table.
5. **The 1.5 s grouping rule is broken.** Markers 6 (43 s) and 7 (44 s) are 1 s apart but have separate numbers.
6. **There is no host data for the first ~2.5 s.** The host and container lines start at marker 2. The host RAM line is also flat from ~2.5 s to 7 s and then steps up, which looks like a held value or a gap rather than real samples.
7. **Sample gaps are drawn as straight lines.** For example, host CPU at 43–47 s and es01 CPU at ~23–24 s and ~42–46 s. These gaps happen exactly when the host is busiest, but the text claims sampling every 0.25 s.
8. **"Generated" is really the start time.** "Generated: 10:52:25" is the start of the recording: the kibana log line quoted is from 08:53:12 UTC = 10:53:12 local, which comes *after* "Generated". Also, the warning timestamp is in UTC while the header is in local time, and neither is labelled.
9. **Per-container stats lack sample counts.** `kibana` P(CPU≥50%) = 75.4 % is only over its own lifetime (24–52 s). Add sample counts or active duration.

## Charts / readability

10. **Axis ticks are odd numbers.** Y ticks are 217/433/650/867 and 534/1067/1601/2135. X ticks are 10/20/31/41/51 s.
11. **es01 dominates the shared CPU and memory charts.** `vector_inbound` and `kibana_dashboards_setup` sit flat along the 0 line and can't be seen.
12. **The marker 1 line at 0 s** is drawn solid and dark on top of the y-axis, so it looks like part of the axis.

## Layout / typesetting

13. **The container name breaks mid-word in the per-container table** (`kibana_dashboa|rds_setup`).
14. **Orphaned headings:** "Before: stack idle / not yet changed" (bottom of page 3) and "All containers healthy — but 1 warning(s)" (bottom of page 4). In both cases the screenshot is on the next page.
15. **The Event key table has odd column widths.** The Marker and Elapsed columns are very wide compared with the edge report's table.
16. **Global Visualization screenshots are too small to read.**
17. **Section 4 "Event log" repeats the Event key** in a larger font and a narrower table.
18. **Figure 1 shows the whole architecture** (reverse proxy, eshops, DBs, Suricata…), but only the SIEM box is relevant to this target. Yet the text says "the per-container graphs below track each box in it".
