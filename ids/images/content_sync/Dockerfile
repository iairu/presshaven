# honeypot_content_sync runs on mysql:8.4 purely for its mysql/mysqldump
# client tools; redis-cli (for the honeypot_pool_replicating:<N> flag, see
# scripts/replicate_content_to_honeypot.sh) is added here once at build
# time (Oracle Linux 9 AppStream, via microdnf) instead of on every
# container start.
#
# Deliberately non-fatal: without redis-cli the script still replicates, it
# only skips the flag, so a failed install must not block the whole stack
# from building. Rebuild to retry: `docker compose build --pull honeypot_content_sync`.
FROM mysql:8.4.13
RUN (microdnf install -y redis && microdnf clean all) \
    || echo 'WARNING: failed to install redis-cli -- replication flag gating will be skipped'
