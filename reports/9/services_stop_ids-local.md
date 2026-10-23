# Services stop report (ids, local) – issues

Report: `services_stop_ids-local.pdf`, generated 2026-10-17 12:35:09, 7 pages; recorded window 24 s, compose exit code 0.

## 1. Five containers ignore SIGTERM and are killed after Docker's 10 s grace period

- backup_service, honeypot_content_sync, pool_manager and log_capper all stop at exactly 10.5 s (marker 3). The stop started at about 0.5 s, so that is Docker's 10 s stop timeout: they were SIGKILLed, not stopped.
- session_store goes last, at 21.3 s: about 10 s after `down` reached it, so it was killed too.
- The causes, in `ids/docker-compose.yml`:
  - backup_service, log_capper: `sh -c "… while true; do … sleep …"` runs as PID 1, and PID 1 ignores SIGTERM unless it installs a handler.
  - session_store: `sh -c "… redis-server …"` without `exec`, so `sh` is PID 1 and Redis never receives the signal. Redis is killed instead of shutting down cleanly.
  - honeypot_content_sync: `bash /replicate_content_to_honeypot.sh` as PID 1. Same problem.
  - pool_manager: Python as PID 1 with no SIGTERM handler. The kernel ignores the default action for PID 1.
- The fix is `init: true` on these services (tini forwards the signal and reaps children), plus `exec redis-server`. That should shorten `down` from 24 s to about 5 s.

## 2. The report says nothing had to be killed

- The report says: "No warnings: no container exited with an error or had to be killed". The five containers in item 1 were killed.
- Compose removes the containers, so their exit codes (137) are gone by the time `ps` is read.
- The report could flag a container that stops 9.5–11 s after the stop began, as "stopped only at the end of the 10 s grace period (killed)". It could also read the exit code with `docker inspect` while the container still exists, in the "stopped" state, before it is removed.

## 3. The "Before" badge on reverse_proxy (161) is the same false positive

- The note says: "Before the stop the Global Visualization page already showed red error badges on: reverse_proxy (161)." These are the prewarm `[info] … 0 failed` lines described in the start report's item 1, not errors.
- With nginx's level tag trusted, that note goes away.
