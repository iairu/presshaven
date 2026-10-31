#!/bin/bash
# =============================================================================
# test_production_instance.sh
#
# PURPOSE:
#   Setup + hardening test of the LIVE production instance: production_eshop
#   (WordPress), its firewall sidecar production_eshop_net, and
#   production_database. Everything is read through `docker inspect` and
#   `docker exec`; nothing is changed.
#
#   The HTTP side of production hardening (XML-RPC off, version strings
#   stripped, sensitive files, directory listing, ...) is scenario_05's job;
#   the declared compose config is test_stack_hardening.py's. This script
#   checks what is actually running.
#
# THIS SCRIPT VERIFIES:
#   Phase 1 - Setup: the containers run and are healthy, WordPress lives in
#             its firewall's network namespace, serves pages, reaches its
#             database, and the edge reaches it.
#   Phase 2 - WordPress containment: no capability, binary or view that
#             could change the firewall -- not even as root.
#   Phase 3 - Firewall: enforcing the production ruleset; the sidecar
#             itself minimal.
#   Phase 4 - Egress: production cannot open connections nothing needs
#             (backups, honeypots, odd internet ports).
#   Phase 5 - Ingress: only the edge may connect to Apache.
#   Phase 6 - Database: hardened, private, credentials kept apart.
#
# USAGE:
#   cd ids/testing && ./test_production_instance.sh
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

WP=production_eshop
FW=production_eshop_net
DB=production_database
LAYER=$(docker exec "$(cid "${FW}")" printenv FIREWALL_LAYER 2>/dev/null || echo default)

# ---------------------------------------------------------------------------
banner "Phase 1 – Production setup (layer: ${LAYER})"
# ---------------------------------------------------------------------------
for s in "${FW}" "${WP}" "${DB}" reverse_proxy; do check_running "$s"; done
check_joins_firewall "${WP}" "${FW}"
check_inspect "${WP}" "${WP} has no network of its own" '{{len .NetworkSettings.Networks}}' '0'
if [ "${LAYER}" = "db-proxy" ]; then
    check_networks "${FW}" "production_network honeypot_network monitoring_network"
else
    check_networks "${FW}" "production_network"
fi
check_networks "${DB}" "production_network"
check_in "${WP}" "${WP} serves WordPress on localhost" "curl -sf -o /dev/null --max-time 10 http://localhost/"
check_connects "${WP}" "${DB}" 3306 "its database"
if [ "${LAYER}" = "db-proxy" ]; then
    check_connects "${WP}" honeypot_database 3306 "db-proxy layer: serves the pool databases"
fi
check_edge_reaches "${WP}"

# ---------------------------------------------------------------------------
banner "Phase 2 – WordPress containment"
# ---------------------------------------------------------------------------
check_wordpress_contained "${WP}"
check_in "${WP}" "${WP} holds no database root password" "! printenv MYSQL_ROOT_PASSWORD"

# ---------------------------------------------------------------------------
banner "Phase 3 – Production firewall"
# ---------------------------------------------------------------------------
check_firewall_enforcing "${FW}" production
check_firewall_hardened "${FW}"
check_in "${FW}" "${FW} resolved the edge (reverse_proxy) for the inbound rule" \
    "container-firewall status | php -r '\$s = json_decode(stream_get_contents(STDIN), true); exit(empty(\$s[\"resolved\"][\"reverse_proxy\"]) ? 1 : 0);'"

# ---------------------------------------------------------------------------
banner "Phase 4 – Egress (where production may connect)"
# ---------------------------------------------------------------------------
check_blocked "${WP}" backup_service 22 "backups"
check_blocked "${WP}" session_store 6379 "edge session store"
check_blocked "${WP}" reverse_proxy 443 "the edge's own TLS port"
check_blocked "${WP}" 1.1.1.1 4444 "an attacker's listener: no rule for that port"
check_blocked "${WP}" 1.1.1.1 22 "outbound SSH"
if [ "${LAYER}" = "default" ]; then
    check_blocked "${WP}" honeypot_database_1 3306 "honeypot pool database"
    check_blocked "${WP}" honeypot_eshop_1 80 "honeypot pool"
fi
_gw=$(network_gateway production_network)
[ -n "${_gw}" ] && check_blocked "${WP}" "${_gw}" 2375 "Docker host API on the bridge gateway"
[ -n "${_gw}" ] && check_blocked "${WP}" "${_gw}" 22 "Docker host SSH on the bridge gateway"
if run_in "${WP}" "$(php_connects 1.1.1.1 443)"; then
    pass "${WP} can open 1.1.1.1:443 (internet-https rule: updates, payment APIs)"
else
    warn "${WP} cannot open 1.1.1.1:443 -- no internet here, or the internet-https rule is off"
fi

# ---------------------------------------------------------------------------
banner "Phase 5 – Ingress (who may connect to production)"
# ---------------------------------------------------------------------------
check_inbound_dropped backup_service "${WP}" 80
check_inbound_dropped "${DB}" "${WP}" 80

# ---------------------------------------------------------------------------
banner "Phase 6 – Production database"
# ---------------------------------------------------------------------------
check_mysql_hardened "${DB}"
check_in "${DB}" "${DB} only accepts the shop's own user from the network (no remote root)" \
    "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -N -e \"SELECT COUNT(*) FROM mysql.user WHERE user='root' AND host NOT IN ('localhost','127.0.0.1','::1')\" 2>/dev/null | grep -qx 0"
if run_in "${WP}" "printenv WORDPRESS_DB_PASSWORD | grep -q '^change_this'"; then
    warn "production's database password is still the .env template placeholder"
fi

report "Production Instance" "production instance set up and hardened."
