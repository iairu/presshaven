# Issues found in `services_start_siem-local.pdf` and `services_start_edge-local.pdf`

Two start-up recordings:

| Report | Recorded window | Recording started | Compose exit code |
|---|---|---|---|
| SIEM | 65 s | 08:53:39 local (06:53:39Z) | 0 |
| Edge (ids) | 108 s | 08:54:56 local (06:54:56Z) | 0 |

Times like "54 s" are elapsed times in the respective report.

Sources: the two PDFs, plus the containers' current logs, Redis and Elasticsearch. The edge containers in the report are still the ones running now (created 08:55:03 local), so their logs cover this start.

## Status (2026-10-16)

| # | Status |
|---|---|
| A.1 | **Fixed.** The local edge now ships to the local SIEM: `ids/.env` has `ELK_ENABLED=true` and `VECTOR_HOST=host.docker.internal`, and the SIEM's CA and `vector-agent` cert were copied to `ids/vector/certs/`. 5,000 documents arrived within 5 s, with no shipper errors. In code, a whole-stack Start of the edge scales `vector_outbound` to 0 while shipping isn't configured (`core/docker_ctl.py`). |
| A.2 | **Fixed** earlier (stricter Kibana healthcheck, an import job that waits, retries and verifies, failed jobs kept visible). The report side is covered by B.4. |
| A.3 | **Fixed.** pool_manager counts compose pools that are still starting as on their way, so it no longer builds a spare before they come up. A broken compose pool still lets spares be built. |
| A.4 | **Fixed.** `KIBANA_MEM_LIMIT` is now 2 GiB (`.env`, `.env.example`, compose default). It takes effect when Kibana is next recreated. |
| A.5 | **Fixed on this machine** (`/etc/sysctl.d/99-redis-overcommit.conf`, `vm.overcommit_memory=1`). The dashboard now checks this, plus Elasticsearch's `vm.max_map_count`, on every host that runs a stack. It shows a banner with the fix commands, and the start report lists them under Warnings (`core/host_settings.py`). |
| B.1, B.2 | **Fixed.** Events now read created / started / finished / removed / stopped (`core/startup_events.py`). |
| B.3 | **Fixed.** The callout uses the CPU series only and says "CPU peak". |
| B.4 | **Fixed.** A Warnings section lists failed or unstarted containers, services with error lines, and missing host settings. The final screenshot's caption mentions the warnings. |
| B.5 | **Fixed.** Above 8 containers, the charts are split by role, with up to 8 fixed-order colours per chart. |
| B.6 | **Fixed.** The services report uses a glossary of only the metrics it prints. |
| B.7 | **Fixed.** The report says when the first seconds were spent building images. |

Only issues **not** already in `pool_test_report_issues.md` are listed. Where an issue is the root cause of one listed there, that's noted.

---

## A. Problems in the stack that these start-ups expose

### A.1 The edge ships no logs to the SIEM; Vector drops them — high (confirmed)
- **Symptom in the report:** in the edge report's "All containers healthy" screenshot, the `vector_outbound` tile has a red "contains error/fail/fault" badge (13).
- **Logs:**
  - `vector_outbound` has logged 178 DNS failures since it started, still about 4 a minute (19 in the last 5 min): `error trying to connect: dns error: failed to lookup address information: No address associated with hostname`.
  - Then `Retries exhausted; dropping the request` and `Events dropped intentional=false count=1000`.
- **Elasticsearch:** the local SIEM holds **0** `honeypot-*` documents. The Kibana dashboards exist (seeded), but every panel is empty.
- **Cause:**
  - `ids/.env` still has the placeholder `VECTOR_HOST=your-siem-vm.example.com`, with `ELK_ENABLED=false`.
  - `vector_outbound` should therefore not run. It is `profiles: [elk]`, and `scripts/docker-compose-up.sh` deliberately leaves that profile off. But the dashboard always passes `--profile '*'` (`core/docker_ctl.py`), so a Start from the dashboard always launches it.
  - `vector/vector.yaml` has no `ELK_ENABLED` gate of its own.
- **Suggested:**
  - To use the local SIEM, point `VECTOR_HOST` at an address the edge containers can reach. On one machine that is the host gateway, e.g. `host.docker.internal` via `extra_hosts: host-gateway`, since the SIEM publishes port 6000. Set `ELK_ENABLED=true` and install the Vector client certificates.
  - Otherwise have the dashboard leave the `elk` profile out of `up` while `ELK_ENABLED` is false or `VECTOR_HOST` is still the placeholder. It can keep `--profile '*'` for `down`/purge.
  - Surface "Vector is dropping events" in the dashboard, not only as a badge.

### A.2 This SIEM start never seeded the Kibana dashboards — high (fixed, uncommitted)
- **Symptom in the SIEM report:**
  - At marker 5 (54 s), `kibana` turns healthy and `kibana_dashboards_setup` stops in the same 1.5-second bucket, so the import job ran for at most a moment.
  - The final screenshot shows that job's tile in orange with an error badge (12).
  - The report still reads "compose exit code: 0 … All containers healthy".
- **This is the start whose missing dashboards were diagnosed earlier:**
  - Kibana's healthcheck accepted the `200 OK` that its temporary *preboot* server returns.
  - The import hit that server and got 503.
  - `curl` without `--fail` exited 0.
  - The dashboard's post-`up` cleanup then deleted the container.
- **Fixed in the working tree:** `siem/docker/docker-compose.yml` (stricter healthcheck, a waiting, retrying, verifying import job) and `dashboard/ui/page_services.py` (failed one-shot jobs are kept). Verified on the live SIEM; not committed.
- **Still open, report side:** the services report should call out a one-shot job that exited non-zero, ran implausibly briefly, or logged errors. Here the dashboard's own badge saw it, but the report text says nothing (see B.4).

### A.3 pool_manager builds a "spare" pool before the compose pools exist — medium (confirmed)
- **Root cause of the leftover pool 4** in pool_test_report_issues.md §2.6.
- **Event log:** `06:55:26Z build_start pool 4 reason=spare`, then `06:56:26Z build pool 4 … 60 s ok`. In the edge report that runs from about 30 s to about 90 s.
- pools 1–3 come from compose and only become healthy at 69 s (marker 7). Before that, pool_manager's first loops see zero ready/free pools and build a runtime spare to meet `POOL_SPARES=1`.
- Once pools 1–3 register, that spare isn't needed. It still takes 1 of the 8 budgeted pools (1536 MB / 1.5 CPU reserved) and adds a 60 s build during the busiest part of the start. It also shows up later as an unexplained 4th pool.
- The services report can't show it: it only tracks compose containers, and runtime pools carry no compose labels. So it is invisible in the per-container charts and the event log.
- **Suggested:**
  - Don't build spares until the compose-declared pools have been adopted. For example, count a static pool that exists but isn't healthy yet as in-flight, or wait for `static_pool_up()` on all of them.
  - Have the services report also list `honeypot.pool`-labelled containers.

### A.4 Kibana runs at its 1 GiB memory limit — low/medium
- SIEM report, per-container memory: `kibana` climbs steadily and sits at **exactly 1024 MiB** (its peak) from about 52 s, just under `KIBANA_MEM_LIMIT=1073741824`.
- Kibana 8.17 commonly needs more than that, and a container pinned at its cgroup limit risks garbage-collection thrash or an OOM kill. Its slow start (healthy only at 54 s) may partly come from this.
- **Not confirmed:** the current Kibana container is a later one (it was recreated while testing the A.2 fix), so whether it was OOM-killed then can't be checked.
- **Suggested:** raise `KIBANA_MEM_LIMIT` to 2 GiB, or set `NODE_OPTIONS=--max-old-space-size` below the limit so Node's heap fits inside it.

### A.5 Redis warns that background saves may fail — low
- The edge report's final screenshot shows an error badge (11) on `session_store`.
- The only line in its log matching error/fail/fault is Redis's start-up warning: `Memory overcommit must be enabled! Without it, a background save or replication may fail…`.
- If a background save (RDB snapshot to disk) fails, Redis stops accepting writes (`stop-writes-on-bgsave-error`). That would hit sessions, threat state and the pool registry at once.
- **Suggested:** set `vm.overcommit_memory=1` in the WSL2 VM, e.g. with a `[boot] command=sysctl -w vm.overcommit_memory=1` entry in `/etc/wsl.conf`.

---

## B. Accuracy of the services start-up reports

### B.1 "started" events mean "created", not "started"
- **SIEM:** the event log has `kibana started` and `kibana_dashboards_setup started` at **0 s**, but neither can start before its dependencies:
  - `kibana` waits for `es01` to be healthy (24 s) and only reports "running" at 26 s;
  - the setup job waits for `kibana` healthy (54 s).
- **Edge:** all 22 services "started" at 6 s, although every one of them waits for `init_setup` to complete.
- So the "started" markers show compose creating the containers, and the start-up order the figures appear to show is wrong.
- **Suggested:** take `State.StartedAt` from `docker inspect`, or emit "created" separately.

### B.2 "stopped" times of one-shot jobs are when the container was removed, not when it exited
- **SIEM:** `init-password stopped` at **54 s**. But `kibana`, which only starts once init-password has *completed*, was already running at 26 s.
- **Edge:** `init_setup` and all the seed and migration jobs "stopped" at **99 s**, in one batch. Yet the databases gated on `init_setup` were running at 26 s, and `init_setup`'s CPU trace ends at about 25 s.
- The events were apparently recorded when the containers disappeared, i.e. when the post-`up` cleanup removed them after compose exited. So no job duration in these reports can be trusted, which is also why A.2 didn't stand out.
- **Suggested:** use `State.FinishedAt` (and `ExitCode`) of each one-shot job, and show each job's run as a bar.

### B.3 The edge "peak" callout marks the RAM peak and calls it the CPU peak
- The edge host chart's callout says "peak 63% @ 108s (transient, no logged event)". The edge report's own table gives the host **CPU** peak as 40.6 %; 63.0 % is the **RAM** peak.
- `services_report._ts_chart` takes `max()` over all series of the host chart (CPU and RAM), while its comment and the report's intro say "the largest CPU peak".
- In the SIEM report it happens to be right (CPU 81 % > RAM 48.5 %).

### B.4 "All containers healthy" is shown over containers that are failing
- That snapshot is taken once every health check passes, but its tiles show:
  - `kibana_dashboards_setup` orange with an error badge (SIEM), while the job had failed (A.2);
  - `vector_outbound` with an error badge (edge), while it was dropping every event (A.1).
- The heading only considers health checks, and nothing in the report text mentions the badges.
- **Suggested:** list containers with error lines, non-zero exits or unexpected states under the snapshot, and add a short "warnings" section near the top of the report.

### B.5 The edge per-container chart can't be read
- 22 series share one CPU chart and one memory chart, and the colours repeat (several greens and pinks in the legend), so most lines can't be told apart.
- **Suggested:** small multiples per group (databases, eshops, seed jobs, edge services), or the top 5 by peak plus "other".

### B.6 The intro explains metrics the reports don't contain
- Both reports open with an explanation of 95 % confidence intervals and p-values. Neither report shows a CI or a p-value: only mean ± SD, p95, peak and P(≥x).
- Drop that paragraph when no CI or p-value is printed.

### B.7 Small gaps in the edge recording
- The first 6 s have no event: compose was building and checking local images (`up --build`).
- Labelling that span "building images" would explain why the first containers appear only at 6 s.
