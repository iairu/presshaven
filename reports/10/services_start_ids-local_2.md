# Services start report (ids, local) – issues, round 2

Report: `services_start_ids-local.pdf`, generated 2026-10-17 16:31:23, 9 pages; recorded window 58 s, compose exit code 0.

The fixes from the previous round held:
- No false warning: reverse_proxy's `[info] … 0 failed` line no longer counts, and the report says "No warnings".
- The prewarm noise is gone: reverse_proxy logged nothing the badge counts.
- The event key is listed in time order (marker 4: "started … ; finished: honeypot_db_seed_1, _2, _3"; the seeds' "started" is in marker 3).
- All containers were healthy at 19.2 s, and host CPU peaked at 35 % (47 % last time).

## 1. Four of the six one-shot jobs are still missing from Figure 1, the charts and the table

- Figure 1's One-shot jobs box, both One-shot jobs charts and the per-container table show only honeypot_db_seed_1 and production_db_seed. The event log shows six jobs:

  | Job | Event log | Seen running by `ps`? |
  |-----|-----------|-----------------------|
  | init_setup | created 4.8 s, finished 6.3 s | no ("started" event missing) |
  | honeypot_db_migration | created 4.8 s, finished 9.4 s | no ("started" event missing) |
  | honeypot_db_seed_2 | started 10.9 s, finished 12.5 s | yes, once |
  | honeypot_db_seed_3 | started 10.9 s, finished 12.5 s | yes, once |

- The previous fix (keeping `docker inspect`'s output when one container of the batch is gone) only helps a job that is still running when `inspect` runs after the status check.
- These jobs run about 1 s (seed_1 gave 4 samples over 0.8 s), while `docker compose ps` is checked only every ~1.5 s, and the call itself takes time. A job that starts and ends between two checks is never seen running. A job that is seen once (seeds 2 and 3) has likely exited by the time `inspect` returns its PID (PID 0, skipped).
- So the report silently leaves out the very containers Figure 1 says it lists. The event key also never shows init_setup or the migration starting.
- Fix: follow `docker events` (`start` and `die`) for the project during the recording. Resolve a container's cgroup the moment it starts (the event carries its id), and take its "started" and "finished" times from the events rather than from the 1.5 s poll. A job that still slips through should be listed in Figure 1 as "ran too briefly to sample" instead of disappearing.

## 2. Observation: production_eshop still sits at about one core for 30 s after it is healthy

- The Shops CPU chart again shows production_eshop oscillating between about 80 % and 125 % from about 18 s to 48 s, with a period under a second.
- The prewarm logging is gone now, so its logging was not the cause. The work itself could be: 20 workers × 20 HEAD requests to `/robots.txt`, and WordPress handles each one with a full PHP bootstrap. First requests, WP cron and healthchecks are the other candidates.
- Not a report bug. If it matters, measure it once with the proxy's prewarm disabled.
