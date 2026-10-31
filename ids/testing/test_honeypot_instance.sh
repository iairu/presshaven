#!/bin/bash
# =============================================================================
# test_honeypot_instance.sh
#
# PURPOSE:
#   Setup + hardening test of every LIVE honeypot pool -- compose pools 1-3
#   and pool_manager's runtime pools alike: honeypot_eshop_N (WordPress), its
#   firewall sidecar honeypot_eshop_N_net, honeypot_database_N and its
#   firewall sidecar honeypot_database_N_net.
#
#   A pool is built to be broken INTO: the edge must keep reaching it, and
#   its WordPress stays as attackable as ever. What it must never become is a
#   gateway: from inside a hijacked pool there is no internet, no edge, no
#   production, no other pool, no Docker host -- only the pool's own
#   database, and from that database nothing at all. Everything is read
#   through `docker inspect` / `docker exec`; nothing is changed (the lock
#   checks hand the firewall documents it must refuse, and only when its
#   image has the lock).
#
# THIS SCRIPT VERIFIES (per pool):
#   Phase 1 - Setup: running and healthy, WordPress in its firewall's network
#             namespace, serving pages, reaching its own database; the edge
#             reaches it and its attack surface is still there.
#   Phase 2 - Containment: no capability, binary or view that could change
#             the firewall -- not even as root -- and a minimal sidecar
#             enforcing the honeypot ruleset, locked.
#   Phase 3 - No gateway: every way out is closed.
#   Phase 4 - Ingress: only the edge may connect to a pool.
#   Phase 5 - The pool's database: hardened, inside its own locked
#             firewall, and no way out of it.
#   And once: honeypot_network is an internal network (no route out), and
#   the containers bridging it to other networks never forward packets.
#
# USAGE:
#   cd ids/testing && ./test_honeypot_instance.sh
#   POOLS="1 4" ./test_honeypot_instance.sh     # only these pools
#
# EXIT CODES:
#   0  All checks passed.
#   1  One or more checks failed.
#   2  docker missing.
# =============================================================================

set -u

source "$(dirname "$0")/lib/scenario_common.sh"
source "$(dirname "$0")/lib/instance_checks.sh"

require_docker

# Running pools: compose (<project>-honeypot_eshop_N-1) and runtime (honeypot_eshop_N).
discover_pools() {
    docker ps --format '{{.Names}}' \
        | sed -nE "s/^(${PROJECT}-)?honeypot_eshop_([0-9]+)(-[0-9]+)?\$/\2/p" | sort -un | tr '\n' ' '
}
POOLS="${POOLS:-$(discover_pools)}"

# ---------------------------------------------------------------------------
banner "honeypot_network"
# ---------------------------------------------------------------------------
_internal=$(docker network inspect -f '{{.Internal}}' "${PROJECT}_honeypot_network" 2>/dev/null)
case "${_internal}" in
    true)  pass "honeypot_network is internal (no route out of the host)" ;;
    false) fail "honeypot_network is NOT internal -- recreate it: docker compose down && docker compose up -d" ;;
    *)     fail "honeypot_network exists (${PROJECT}_honeypot_network not found)" ;;
esac
GW=$(network_gateway honeypot_network)
for s in reverse_proxy honeypot_content_sync; do
    check_in "$s" "$s never routes between its networks (net.ipv4.ip_forward=0)" \
        "grep -qx 0 /proc/sys/net/ipv4/ip_forward"
done

# check_database_dead_end <database> <its firewall>
check_database_dead_end() {
    check_mysql_hardened "$1"
    check_joins_firewall "$1" "$2"
    check_inspect "$1" "$1 has no network of its own" '{{len .NetworkSettings.Networks}}' '0'
    check_networks "$2" "honeypot_network"
    check_firewall_enforcing "$2" honeypot_database
    check_firewall_hardened "$2"
    check_firewall_locked "$2"
    check_tcp_blocked "$1" 1.1.1.1 443 "internet HTTPS"
    check_tcp_blocked "$1" reverse_proxy 80 "the edge"
    check_tcp_blocked "$1" production_eshop 80 "production WordPress"
    check_tcp_blocked "$1" production_database 3306 "production database"
    check_tcp_blocked "$1" session_store 6379 "edge session store"
    check_tcp_blocked "$1" backup_service 22 "backups"
    if [ -n "${GW}" ]; then
        check_tcp_blocked "$1" "${GW}" 2375 "Docker host API on the bridge gateway"
        check_tcp_blocked "$1" "${GW}" 22 "Docker host SSH on the bridge gateway"
    fi
}

if [ -z "${POOLS// /}" ]; then
    if [ -n "$(cid honeypot_database)" ]; then
        banner "Database proxy layer – honeypot_database"
        check_running honeypot_database
        check_database_dead_end honeypot_database honeypot_database_net
        report "Honeypot Instance" "database proxy layer: no pool containers; the pool database is a dead end."
    fi
    fail "at least one honeypot pool is running (none found)"
    report "Honeypot Instance" ""
fi

for N in ${POOLS}; do
    WP="honeypot_eshop_${N}"
    FW="${WP}_net"
    DB="honeypot_database_${N}"
    DB_FW="${DB}_net"

    # -----------------------------------------------------------------------
    banner "Pool ${N} – Phase 1: setup"
    # -----------------------------------------------------------------------
    for s in "${FW}" "${WP}" "${DB_FW}" "${DB}"; do check_running "$s"; done
    check_joins_firewall "${WP}" "${FW}"
    check_inspect "${WP}" "${WP} has no network of its own" '{{len .NetworkSettings.Networks}}' '0'
    check_networks "${FW}" "honeypot_network"
    check_in "${FW}" "${FW} answers to the name ${WP} on honeypot_network" \
        "php -r 'exit(gethostbyname(\"${WP}\") !== \"${WP}\" ? 0 : 1);'"
    check_in "${WP}" "${WP} serves WordPress on localhost" "curl -sf -o /dev/null --max-time 10 http://localhost/"
    check_in "${WP}" "${WP} is configured for its own database ${DB}" \
        "printenv WORDPRESS_DB_HOST | grep -q '^${DB}\\(:3306\\)\\?\$'"
    check_connects "${WP}" "${DB}" 3306 "its own database"
    check_edge_reaches "${WP}"
    check_in reverse_proxy "attack surface kept: the edge gets wp-login.php from ${WP} (200)" \
        "curl -s -o /dev/null --max-time 10 -w '%{http_code}' http://${WP}/wp-login.php | grep -qx 200"

    # -----------------------------------------------------------------------
    banner "Pool ${N} – Phase 2: containment"
    # -----------------------------------------------------------------------
    check_wordpress_contained "${WP}"
    check_in "${WP}" "${WP} holds no production or root database credential" \
        "! printenv | grep -q '^\\(MYSQL_ROOT_PASSWORD\\|HONEYPOT_DB_PASSWORD\\|WORDPRESS_AUTH_KEY\\)='"
    check_firewall_enforcing "${FW}" honeypot
    check_firewall_hardened "${FW}"
    check_firewall_locked "${FW}"
    check_in "${FW}" "${FW} resolved db-host to ${DB} only" \
        "container-firewall status | php -r '\$s = json_decode(stream_get_contents(STDIN), true); \$ip = gethostbynamel(\"${DB}\"); exit(!empty(\$s[\"resolved\"][\"db-host\"]) && \$ip && !array_diff(\$s[\"resolved\"][\"db-host\"], \$ip) ? 0 : 1);'"

    # -----------------------------------------------------------------------
    banner "Pool ${N} – Phase 3: no gateway out"
    # -----------------------------------------------------------------------
    check_blocked "${WP}" 1.1.1.1 443 "internet HTTPS"
    check_blocked "${WP}" 1.1.1.1 80 "internet HTTP"
    check_blocked "${WP}" 8.8.8.8 53 "external DNS over TCP"
    check_in "${WP}" "${WP} cannot resolve internet names (example.com)" "$(php_no_dns example.com)"
    check_blocked "${WP}" reverse_proxy 80 "the edge -- and through it production"
    check_blocked "${WP}" reverse_proxy 443 "the edge's TLS port"
    check_blocked "${WP}" production_eshop 80 "production WordPress"
    check_blocked "${WP}" production_database 3306 "production database"
    check_blocked "${WP}" backup_service 22 "backups"
    check_blocked "${WP}" session_store 6379 "edge session store"
    if [ -n "${GW}" ]; then
        check_blocked "${WP}" "${GW}" 2375 "Docker host API on the bridge gateway"
        check_blocked "${WP}" "${GW}" 22 "Docker host SSH on the bridge gateway"
        check_blocked "${WP}" "${GW}" 80 "Docker host web ports on the bridge gateway"
    fi
    for M in ${POOLS}; do
        [ "${M}" = "${N}" ] && continue
        check_blocked "${WP}" "honeypot_eshop_${M}" 80 "another pool"
        check_blocked "${WP}" "honeypot_database_${M}" 3306 "another pool's database"
    done

    # -----------------------------------------------------------------------
    banner "Pool ${N} – Phase 4: ingress (only the edge)"
    # -----------------------------------------------------------------------
    for M in ${POOLS}; do
        [ "${M}" = "${N}" ] && continue
        check_inbound_dropped "honeypot_database_${M}" "${WP}" 80
        break  # one foreign container on honeypot_network is enough
    done
    check_inbound_dropped "${DB}" "${WP}" 80

    # -----------------------------------------------------------------------
    banner "Pool ${N} – Phase 5: its database, a dead end"
    # -----------------------------------------------------------------------
    check_database_dead_end "${DB}" "${DB_FW}"
    check_tcp_blocked "${DB}" "${WP}" 80 "its own pool's WordPress"
    for M in ${POOLS}; do
        [ "${M}" = "${N}" ] && continue
        check_tcp_blocked "${DB}" "honeypot_eshop_${M}" 80 "another pool"
        check_tcp_blocked "${DB}" "honeypot_database_${M}" 3306 "another pool's database"
    done
done

report "Honeypot Instance" "every pool reachable from the edge, and a dead end from inside."
