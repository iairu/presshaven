#!/bin/bash
# =============================================================================
# test_container_firewall_isolation.sh
#
# PURPOSE:
#   Pre-deploy test of the container firewall design, on a throwaway copy of
#   the topology -- nothing of the real stack is touched, and no credential
#   is used. It builds images/container_firewall/ and starts:
#
#     pfwtest_hp   internal network (like honeypot_network)
#       pfw-edge      alias reverse_proxy   (also on pfwtest_prod)
#       pfw-hp-fw     the honeypot firewall, alias honeypot_eshop_1
#       pfw-hp-wp     the REAL hardened WordPress image in pfw-hp-fw's
#                     namespace (php -S stub server, no database settings)
#       pfw-hpdb-fw   the honeypot_database firewall, alias honeypot_database_1
#       pfw-hpdb-db   its database (a 3306 stand-in) in pfw-hpdb-fw's namespace
#       pfw-hp-db2    alias honeypot_database_2 (another pool's database)
#       pfw-hp-other  alias honeypot_eshop_2   (another pool)
#     pfwtest_prod normal network (like production_network)
#       pfw-pr-fw     the production firewall, alias production_eshop
#       pfw-pr-wp     WordPress image in pfw-pr-fw's namespace
#       pfw-pr-db     alias production_database
#       pfw-pr-backup alias backup_service (listening on 22)
#
#   Stand-ins are python http.server listeners. Every container is labelled
#   pfwtest.pool (never honeypot.pool: pool_manager destroys those) and is
#   removed on exit.
#
# THIS SCRIPT VERIFIES:
#   Honeypot profile: the edge gets in; the pool reaches its own database
#   and nothing else (no internet, DNS, edge, other pools, Docker host);
#   other containers cannot connect in; WordPress cannot touch the firewall;
#   a WordPress restart keeps the rules; a firewall restart fails closed.
#   Honeypot database profile: the pool reaches it; from it nothing at all
#   (edge, other pools, Docker host, internet); a firewall restart fails
#   closed. Both honeypot profiles: locked (cannot be switched off or opened
#   up), no forwarding, IPv6 enforced.
#   Production profile: the edge gets in; the shop reaches its database
#   and the internet on 443 only; backups unreachable; only the edge in.
#
# USAGE:
#   cd ids/testing && ./test_container_firewall_isolation.sh
#
# EXIT CODES:
#   0 all passed, 1 a check failed, 2 docker missing / setup failed.
# =============================================================================

set -u

source "$(dirname "$0")/lib/scenario_common.sh"
source "$(dirname "$0")/lib/instance_checks.sh"

require_docker

EDGE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FW_IMAGE="presshaven/container-firewall:pfwtest"
WP_IMAGE="${WP_IMAGE:-presshaven/wordpress:7.1.3-php8.4-hardened}"
STUB_IMAGE="${STUB_IMAGE:-python:3.15.1-alpine3.24}"
LABEL="pfwtest.pool=1"
WP_CAPS="--cap-add CHOWN --cap-add DAC_OVERRIDE --cap-add FOWNER --cap-add SETGID --cap-add SETUID --cap-add NET_BIND_SERVICE --cap-add KILL"

cleanup() {
    docker ps -aq --filter "label=pfwtest.pool" | xargs -r docker rm -f >/dev/null 2>&1
    docker network rm pfwtest_hp pfwtest_prod >/dev/null 2>&1
    docker volume rm pfwtest_rules >/dev/null 2>&1
    true
}
trap cleanup EXIT
cleanup

die() { printf "${RED}SETUP FAILED: %s${NC}\n" "$1" >&2; exit 2; }

# A python listener on <port> answering to <alias> on <network>.
stub() {  # stub <name> <network> <alias> <port>
    docker run -d --name "$1" --label "${LABEL}" --network "$2" --network-alias "$3" \
        "${STUB_IMAGE}" python -m http.server "$4" >/dev/null || die "start $1"
}

# A firewall sidecar, healthy (its ruleset enforced).
firewall() {  # firewall <prefix> <network> <alias> <profile> [extra env...]
    _p=$1 _net=$2 _alias=$3 _profile=$4; shift 4
    docker run -d --name "${_p}-fw" --label "${LABEL}" --network "${_net}" --network-alias "${_alias}" \
        -e FIREWALL_PROFILE="${_profile}" -e FIREWALL_LAYER=default "$@" \
        -v pfwtest_rules:/var/lib/container-firewall --init --read-only --tmpfs /run \
        --security-opt no-new-privileges:true --cap-drop ALL --cap-add NET_ADMIN \
        --memory 64m --pids-limit 50 "${FW_IMAGE}" >/dev/null || die "start ${_p}-fw"
    for _ in $(seq 1 30); do
        docker exec "${_p}-fw" container-firewall health >/dev/null 2>&1 && break
        sleep 1
    done
    docker exec "${_p}-fw" container-firewall health >/dev/null 2>&1 || die "${_p}-fw never became healthy: $(docker logs --tail 5 "${_p}-fw" 2>&1)"
}

# A firewall sidecar + WordPress in its namespace.
pair() {  # pair <prefix> <network> <alias> <profile> [extra env...]
    firewall "$@"
    _p=$1
    docker run -d --name "${_p}-wp" --label "${LABEL}" --network "container:${_p}-fw" \
        --security-opt no-new-privileges:true --cap-drop ALL ${WP_CAPS} --memory 256m --pids-limit 100 \
        --entrypoint php "${WP_IMAGE}" -S 0.0.0.0:80 -t /tmp >/dev/null || die "start ${_p}-wp"
}

# check_edge_gets <host>: pfw-edge gets an HTTP answer from <host>:80.
check_edge_gets() {
    check_in pfw-edge "the edge reaches $1:80" "wget -q -T 5 -O /dev/null http://$1/ || wget -T 5 -O /dev/null http://$1/ 2>&1 | grep -q 'HTTP/'"
}
# check_stub_blocked <from> <host> <port>: a stand-in cannot connect.
check_stub_blocked() {
    check_in "$1" "$1 cannot open $2:$3 (only the edge may)" \
        "python -c 'import socket,sys; s=socket.socket(); s.settimeout(4); sys.exit(0 if s.connect_ex((\"$2\", $3)) else 1)'"
}

# ---------------------------------------------------------------------------
banner "Setup – throwaway topology"
# ---------------------------------------------------------------------------
docker image inspect "${WP_IMAGE}" >/dev/null 2>&1 || die "${WP_IMAGE} not built (docker compose build production_eshop)"
docker image inspect "${STUB_IMAGE}" >/dev/null 2>&1 || docker pull -q "${STUB_IMAGE}" >/dev/null || die "pull ${STUB_IMAGE}"
docker build -q -t "${FW_IMAGE}" "${EDGE_DIR}/images/container_firewall" >/dev/null || die "build the firewall image"
docker network create --internal --label "${LABEL}" pfwtest_hp >/dev/null || die "create pfwtest_hp"
docker network create --label "${LABEL}" pfwtest_prod >/dev/null || die "create pfwtest_prod"
docker volume create --label "${LABEL}" pfwtest_rules >/dev/null || die "create pfwtest_rules"

docker run -d --name pfw-edge --label "${LABEL}" --network pfwtest_hp --network-alias reverse_proxy \
    "${STUB_IMAGE}" python -m http.server 80 >/dev/null || die "start pfw-edge"
docker network connect --alias reverse_proxy pfwtest_prod pfw-edge || die "connect pfw-edge"
stub pfw-hp-db2 pfwtest_hp honeypot_database_2 3306
stub pfw-hp-other pfwtest_hp honeypot_eshop_2 80
stub pfw-pr-db pfwtest_prod production_database 3306
stub pfw-pr-backup pfwtest_prod backup_service 22
firewall pfw-hpdb pfwtest_hp honeypot_database_1 honeypot_database
docker run -d --name pfw-hpdb-db --label "${LABEL}" --network container:pfw-hpdb-fw \
    --security-opt no-new-privileges:true --cap-drop ALL \
    "${STUB_IMAGE}" python -m http.server 3306 >/dev/null || die "start pfw-hpdb-db"
pair pfw-hp pfwtest_hp honeypot_eshop_1 honeypot -e FIREWALL_DB_HOST=honeypot_database_1:3306
pair pfw-pr pfwtest_prod production_eshop production
sleep 2
pass "throwaway topology up (firewall image built from images/container_firewall/)"
HP_GW=$(docker network inspect -f '{{range .IPAM.Config}}{{.Gateway}}{{end}}' pfwtest_hp)

# ---------------------------------------------------------------------------
banner "Honeypot profile – the way in stays open"
# ---------------------------------------------------------------------------
check_firewall_enforcing pfw-hp-fw honeypot
check_edge_gets honeypot_eshop_1
check_connects pfw-hp-wp honeypot_database_1 3306 "its own database"

# ---------------------------------------------------------------------------
banner "Honeypot profile – no gateway out"
# ---------------------------------------------------------------------------
check_blocked pfw-hp-wp 1.1.1.1 443 "internet HTTPS"
check_blocked pfw-hp-wp 1.1.1.1 80 "internet HTTP"
check_in pfw-hp-wp "pfw-hp-wp cannot resolve internet names" "$(php_no_dns example.com)"
check_blocked pfw-hp-wp reverse_proxy 80 "the edge"
check_blocked pfw-hp-wp honeypot_database_2 3306 "another pool's database"
check_blocked pfw-hp-wp honeypot_eshop_2 80 "another pool"
check_blocked pfw-hp-wp "${HP_GW}" 2375 "Docker host API on the gateway"
check_blocked pfw-hp-wp "${HP_GW}" 22 "Docker host SSH on the gateway"

# ---------------------------------------------------------------------------
banner "Honeypot profile – only the edge gets in"
# ---------------------------------------------------------------------------
check_stub_blocked pfw-hp-other honeypot_eshop_1 80
check_stub_blocked pfw-hp-db2 honeypot_eshop_1 80

# ---------------------------------------------------------------------------
banner "Honeypot profile – WordPress cannot touch the firewall"
# ---------------------------------------------------------------------------
check_wordpress_contained pfw-hp-wp
check_firewall_hardened pfw-hp-fw
check_firewall_locked pfw-hp-fw
check_in pfw-hp-wp "even root in WordPress cannot write the firewall's files (none visible)" \
    "! ls /var/lib/container-firewal[l] /usr/local/bin/container-firewal[l] 2>/dev/null | grep -q ."

# ---------------------------------------------------------------------------
banner "Honeypot profile – restarts"
# ---------------------------------------------------------------------------
docker restart -t 2 pfw-hp-wp >/dev/null
sleep 2
check_connects pfw-hp-wp honeypot_database_1 3306 "after a WordPress restart"
check_blocked pfw-hp-wp honeypot_database_2 3306 "after a WordPress restart"
docker restart -t 2 pfw-hp-fw >/dev/null
sleep 3
check_in pfw-hp-wp "after a firewall restart WordPress is cut off (fails closed, no interface but lo)" \
    "! grep -qv '^ *lo:\\|^Inter\\|^ face' /proc/net/dev"

# ---------------------------------------------------------------------------
banner "Honeypot database profile – a dead end"
# ---------------------------------------------------------------------------
check_firewall_enforcing pfw-hpdb-fw honeypot_database
check_firewall_hardened pfw-hpdb-fw
check_firewall_locked pfw-hpdb-fw
check_tcp_blocked pfw-hpdb-db reverse_proxy 80 "the edge"
check_tcp_blocked pfw-hpdb-db honeypot_eshop_1 80 "its own pool's WordPress"
check_tcp_blocked pfw-hpdb-db honeypot_eshop_2 80 "another pool"
check_tcp_blocked pfw-hpdb-db honeypot_database_2 3306 "another pool's database"
check_tcp_blocked pfw-hpdb-db "${HP_GW}" 2375 "Docker host API on the gateway"
check_tcp_blocked pfw-hpdb-db "${HP_GW}" 22 "Docker host SSH on the gateway"
check_tcp_blocked pfw-hpdb-db 1.1.1.1 443 "internet HTTPS"
docker restart -t 2 pfw-hpdb-fw >/dev/null
sleep 3
check_in pfw-hpdb-db "after a firewall restart the database is cut off (fails closed, no interface but lo)" \
    "! grep -qv '^ *lo:\\|^Inter\\|^ face' /proc/net/dev"

# ---------------------------------------------------------------------------
banner "Production profile"
# ---------------------------------------------------------------------------
check_firewall_enforcing pfw-pr-fw production
check_edge_gets production_eshop
check_connects pfw-pr-wp production_database 3306 "its database"
check_blocked pfw-pr-wp backup_service 22 "backups"
check_blocked pfw-pr-wp 1.1.1.1 4444 "an attacker's listener"
check_blocked pfw-pr-wp reverse_proxy 443 "the edge's TLS port"
check_stub_blocked pfw-pr-backup production_eshop 80
check_stub_blocked pfw-pr-db production_eshop 80
check_wordpress_contained pfw-pr-wp
if run_in pfw-pr-wp "$(php_connects 1.1.1.1 443)"; then
    pass "pfw-pr-wp can open 1.1.1.1:443 (internet-https rule)"
else
    warn "pfw-pr-wp cannot open 1.1.1.1:443 -- no internet on this host?"
fi

report "Container Firewall Isolation (throwaway topology)" "the firewall design holds; safe to deploy."
