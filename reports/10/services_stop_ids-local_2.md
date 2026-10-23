# Services stop report (ids, local) – issues, round 2

Report: `services_stop_ids-local.pdf`, generated 2026-10-17 16:40:52, 7 pages; recorded window 8 s, compose exit code 0.

No new issues. The previous round's fixes work:
- **Nothing is killed any more.** backup_service, honeypot_content_sync, pool_manager, log_capper and vector_outbound stop at 0.5 s, and session_store and suricata_ids at 2.0 s. Last time five containers sat out the 10 s grace period and were killed.
- **The stop is three times faster.** `down` finished at 8.2 s, down from 24 s, and the whole stack was gone by 5.8 s.
- **No false badge before the stop.** reverse_proxy's tile has no red badge in the "Before" screenshot (it showed 161 last time).
- **The exit codes were read.** "No warnings: no container … had to be killed" is now backed by the die events, which reported no 137.
