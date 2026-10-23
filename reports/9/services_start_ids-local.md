# Services start report (ids, local) – issues

Report: `services_start_ids-local.pdf`, generated 2026-10-17 12:22:41, 10 pages; recorded window 58 s, compose exit code 0.
The start itself was clean. All containers came up healthy by 17.1 s, every one-shot job finished with code 0, and host CPU peaked at 47 %.

## 1. A false-positive warning: reverse_proxy's INFO lines count as errors

- The Warnings table lists reverse_proxy with "160 line(s) with an error word (160 INFO)". The example line is nginx's own `[info]` line `[PREWARM] Pre-warming complete for production_eshop [production_backend]: 20 successful, 0 failed`.
- The only error word is the "failed" in "0 failed": nothing went wrong.
- As a result, section 3's last screenshot is captioned "All containers healthy — but 1 warning(s)", while no tile there carries a red badge.
- The cause is in `core/log_error_match.py`. It trusts Kibana's declared level (INFO and below never count) but not nginx's `[info]` / `[notice]` / `[debug]` tags, so the plain keyword scan matches "failed".
- The same lines raise the "reverse_proxy (161)" badge that the stop report mentions.

## 2. reverse_proxy logs the prewarm line about 4 times a second

- 160 INFO lines in the ~40 s reverse_proxy ran during the recording (started at 17.1 s) means the prewarm runs continuously, not once at start-up.
- It also logs every pass at info level.
- This is log noise for Vector and Suricata to ship and the log capper to trim, and it keeps the badge counter climbing.
- A prewarm only needs logging when something failed, or once per backend after start-up.

## 3. honeypot_db_migration is missing from Figure 1, the charts and the per-container table

- The event log shows honeypot_db_migration created at 1.5 s, started at 7.8 s and finished at 9.4 s.
- Its tile also appears in both section 3 screenshots.
- It is still absent from Figure 1's One-shot jobs box, both One-shot jobs charts, and the per-container probability table.
- The other one-shot jobs ran for about as long (init_setup 1.6 s, the seeds about 1.5 s) and were all sampled. Figure 1 claims to list "exactly the containers those charts plot", so the job silently drops out of the report.

## 4. Event key lists a marker's events by kind, not in the order they happened

- Marker 4 (6.3–7.8 s) reads "healthy: … session_store, suricata_ids; running, health pending: session_store, suricata_ids". Both containers went pending at 6.3 s and healthy at 7.8 s, but the key lists healthy first.
- Marker 5 lists "finished: … honeypot_db_seed_1, _2, _3 …; started: honeypot_db_seed_1, _2, _3": the seeds' finish comes before their start.
- Within a marker, the event types should follow the order of their first event (and a container's pending state could be left out once it went healthy in the same marker).

## 5. Observation: production_eshop sits at about one core for 30 s after it is healthy

- The Shops CPU chart shows production_eshop oscillating between about 80 % and 125 % from 18 s to 48 s, with a regular period of under a second.
- After that, the three honeypot eshops are busy from 40 s to 50 s, which produces the host CPU peak of 47 % at 47 s.
- The timing matches reverse_proxy's prewarm (item 2) or the first healthchecks and WP cron. This is not a report bug, but worth checking together with item 2.
