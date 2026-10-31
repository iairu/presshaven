# instance_checks.sh -- shared helpers for test_production_instance.sh and
# test_honeypot_instance.sh, sourced after scenario_common.sh:
#
#     source "$(dirname "$0")/lib/scenario_common.sh"
#     source "$(dirname "$0")/lib/instance_checks.sh"
#
# Every check runs against the LIVE stack through `docker inspect` and
# `docker exec`; nothing is started, changed or written. Probes inside the
# WordPress containers use PHP (always there), and every "blocked" probe exits
# 0 only when the connection FAILS -- so a broken probe (missing tool,
# quoting) is a FAIL, never a false "blocked".

PROJECT="${COMPOSE_PROJECT:-honeypot-ids-system-v1}"

PASS=0
FAIL=0
SKIP=0
TOTAL=0

pass() { PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1)); printf "  ${GREEN}[PASS]${NC} %s\n" "$1"; }
fail() { FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); printf "  ${RED}[FAIL]${NC} %s\n" "$1"; }
skip() { SKIP=$((SKIP + 1)); TOTAL=$((TOTAL + 1)); printf "  ${YELLOW}[SKIP]${NC} %s\n" "$1"; }
warn() { printf "  ${YELLOW}[WARN]${NC} %s\n" "$1"; }

require_docker() {
    if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
        printf "${RED}ERROR: docker is not available.${NC}\n" >&2
        exit 2
    fi
}

# Container ID of a running service: a compose service of $PROJECT, or a
# container of exactly that name (pool_manager's runtime pools).
cid() {
    _id=$(docker ps -q --filter "label=com.docker.compose.project=${PROJECT}" \
                       --filter "label=com.docker.compose.service=$1" | head -1)
    [ -n "${_id}" ] || _id=$(docker ps -q --filter "name=^/$1\$" | head -1)
    printf "%s" "${_id}"
}

# inspect <service> <go-template>
inspect() { docker inspect -f "$2" "$(cid "$1")" 2>/dev/null; }

# run_in <service> <shell command>: run inside, quietly; returns its exit code.
run_in() { docker exec "$(cid "$1")" sh -c "$2" >/dev/null 2>&1; }

# PHP probe sources (run with `run_in`).
php_connects() { printf "php -r 'exit(@fsockopen(\"%s\", %s, \$e, \$m, 3) ? 0 : 1);'" "$1" "$2"; }
php_blocked()  { printf "php -r 'exit(@fsockopen(\"%s\", %s, \$e, \$m, 3) ? 1 : 0);'" "$1" "$2"; }
php_no_dns()   { printf "php -r 'exit(gethostbyname(\"%s\") === \"%s\" ? 0 : 1);'" "$1" "$1"; }

# --- assertions ----------------------------------------------------------------

# check_running <service>: running, and healthy when it has a healthcheck.
check_running() {
    if [ -z "$(cid "$1")" ]; then
        fail "$1 is running (not found)"
        return 1
    fi
    _h=$(inspect "$1" '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}')
    case "${_h}" in
        healthy|none) pass "$1 is running${_h:+ (health: ${_h})}" ;;
        *)            fail "$1 is running but health is '${_h}'" ;;
    esac
}

# check_in <service> <description> <command>: command succeeds inside.
check_in() {
    [ -n "$(cid "$1")" ] || { skip "$2 -- $1 not running"; return 0; }
    if run_in "$1" "$3"; then pass "$2"; else fail "$2"; fi
}

# check_inspect <service> <description> <go-template> <expected>
check_inspect() {
    [ -n "$(cid "$1")" ] || { skip "$2 -- $1 not running"; return 0; }
    _got=$(inspect "$1" "$3")
    if [ "${_got}" = "$4" ]; then pass "$2"; else fail "$2 (got '${_got}', want '$4')"; fi
}

# check_joins_firewall <wordpress service> <firewall service>: WordPress has no
# network of its own; it lives in the firewall's network namespace.
check_joins_firewall() {
    _fw=$(cid "$2")
    [ -n "$(cid "$1")" ] && [ -n "${_fw}" ] \
        || { fail "$1 runs in the network namespace of $2 (one of them is not running)"; return 0; }
    _mode=$(inspect "$1" '{{.HostConfig.NetworkMode}}')
    case "${_mode}" in
        "container:${_fw}"*) pass "$1 runs in the network namespace of $2" ;;
        *)                   fail "$1 runs in the network namespace of $2 (NetworkMode '${_mode}')" ;;
    esac
}

# check_firewall_enforcing <firewall service> <profile>
check_firewall_enforcing() {
    check_in "$1" "$1 enforces the '$2' ruleset (hooked, saved = enforced, enabled)" \
        "container-firewall status | php -r '\$s = json_decode(stream_get_contents(STDIN), true); exit(\$s[\"profile\"] === \"$2\" && \$s[\"hooked\"] && \$s[\"fingerprint\"] === \$s[\"enforced_fingerprint\"] && \$s[\"document\"][\"enabled\"] ? 0 : 1);'"
}

# check_firewall_hardened <firewall service>
check_firewall_hardened() {
    # compose stores NET_ADMIN, docker run / the Docker SDK CAP_NET_ADMIN.
    check_inspect "$1" "$1 holds NET_ADMIN only" \
        '{{range $i, $c := .HostConfig.CapAdd}}{{if $i}},{{end}}{{if eq $c "CAP_NET_ADMIN"}}NET_ADMIN{{else}}{{$c}}{{end}}{{end}}' 'NET_ADMIN'
    check_inspect "$1" "$1 drops every other capability" '{{json .HostConfig.CapDrop}}' '["ALL"]'
    check_inspect "$1" "$1 has a read-only root filesystem" '{{.HostConfig.ReadonlyRootfs}}' 'true'
    check_inspect "$1" "$1 is not privileged" '{{.HostConfig.Privileged}}' 'false'
}

# check_wordpress_contained <wordpress service>: nothing in it can change the
# firewall -- not even root.
check_wordpress_contained() {
    # Capability bits: NET_ADMIN 12, NET_RAW 13, SYS_ADMIN 21, SYS_PTRACE 19.
    check_in "$1" "$1: no NET_ADMIN / NET_RAW / SYS_ADMIN / SYS_PTRACE in PID 1's bounding set" \
        "php -r 'preg_match(\"/CapBnd:\\s*(\\w+)/\", file_get_contents(\"/proc/1/status\"), \$m); \$c = hexdec(\$m[1]); exit(\$c & (1 << 12 | 1 << 13 | 1 << 21 | 1 << 19) ? 1 : 0);'"
    check_in "$1" "$1: no_new_privs set on PID 1 (setuid binaries gain nothing)" \
        "grep -q '^NoNewPrivs:[[:space:]]*1' /proc/1/status"
    check_in "$1" "$1: no iptables / nft binary" \
        "! command -v iptables && ! command -v iptables-legacy && ! command -v nft"
    check_in "$1" "$1: firewall rules and processes are invisible" \
        "[ ! -e /var/lib/container-firewal[l] ] && ! grep -qs 'container-firewal[l]' /proc/[0-9]*/cmdline"
    check_in "$1" "$1: cannot reconfigure interfaces even as root (a no-op ip link change fails, or ip is absent)" \
        "! ip link set lo up 2>/dev/null"
    check_inspect "$1" "$1 is not privileged" '{{.HostConfig.Privileged}}' 'false'
    check_inspect "$1" "$1 drops every capability not re-added" '{{json .HostConfig.CapDrop}}' '["ALL"]'
    check_inspect "$1" "$1 runs with no-new-privileges" \
        '{{range .HostConfig.SecurityOpt}}{{if eq . "no-new-privileges:true" "no-new-privileges"}}yes{{end}}{{end}}' 'yes'
    _pids=$(inspect "$1" '{{.HostConfig.PidsLimit}}')
    _mem=$(inspect "$1" '{{.HostConfig.Memory}}')
    if [ "${_pids:-0}" -gt 0 ] 2>/dev/null && [ "${_mem:-0}" -gt 0 ] 2>/dev/null; then
        pass "$1 is resource-limited (pids ${_pids}, memory $((_mem / 1048576)) MB)"
    else
        fail "$1 is resource-limited (pids '${_pids}', memory '${_mem}')"
    fi
}

# check_connects / check_blocked <service> <host> <port> [why]
check_connects() { check_in "$1" "$1 can open $2:$3${4:+ ($4)}" "$(php_connects "$2" "$3")"; }
check_blocked()  { check_in "$1" "$1 cannot open $2:$3${4:+ ($4)}" "$(php_blocked "$2" "$3")"; }

# check_edge_reaches <host>: reverse_proxy gets an HTTP answer from <host>:80
# (any status: the edge's own probes and diverted sessions need the socket).
check_edge_reaches() {
    check_in reverse_proxy "reverse_proxy reaches $1:80 (the way in)" \
        "curl -s -o /dev/null --max-time 10 -w '%{http_code}' http://$1/ | grep -qv '^000\$'"
}

# check_mysql_hardened <database service>
check_mysql_hardened() {
    check_inspect "$1" "$1 drops every capability not re-added" '{{json .HostConfig.CapDrop}}' '["ALL"]'
    check_inspect "$1" "$1 runs with no-new-privileges" \
        '{{range .HostConfig.SecurityOpt}}{{if eq . "no-new-privileges:true" "no-new-privileges"}}yes{{end}}{{end}}' 'yes'
    check_inspect "$1" "$1 publishes no ports on the host" '{{len .HostConfig.PortBindings}}' '0'
    _pids=$(inspect "$1" '{{.HostConfig.PidsLimit}}')
    _mem=$(inspect "$1" '{{.HostConfig.Memory}}')
    if [ "${_pids:-0}" -gt 0 ] 2>/dev/null && [ "${_mem:-0}" -gt 0 ] 2>/dev/null; then
        pass "$1 is resource-limited (pids ${_pids}, memory $((_mem / 1048576)) MB)"
    else
        fail "$1 is resource-limited (pids '${_pids}', memory '${_mem}')"
    fi
}

# check_networks <service> <expected networks, space-separated, short names>
check_networks() {
    [ -n "$(cid "$1")" ] || { skip "$1 networks -- not running"; return 0; }
    _got=$(inspect "$1" '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' \
           | tr ' ' '\n' | sed "s/^${PROJECT}_//" | grep . | sort | tr '\n' ' ')
    _want=$(printf "%s\n" $2 | sort | tr '\n' ' ')
    if [ "${_got}" = "${_want}" ]; then pass "$1 is on: ${_want}"; else fail "$1 is on '${_got}', want '${_want}'"; fi
}

report() {
    banner "$1 – Final Report"
    printf "Total checks : %d\n" "${TOTAL}"
    printf "${GREEN}Passed       : %d${NC}\n" "${PASS}"
    printf "${YELLOW}Skipped      : %d${NC}\n" "${SKIP}"
    if [ "${FAIL}" -gt 0 ]; then printf "${RED}Failed       : %d${NC}\n" "${FAIL}"; else printf "Failed       : 0\n"; fi
    printf "\n"
    if [ "${FAIL}" -eq 0 ]; then
        printf "${GREEN}PASSED – %s${NC}\n" "$2"
        exit 0
    fi
    printf "${RED}FAILED – %d check(s) not satisfied.${NC}\n" "${FAIL}"
    exit 1
}

# check_inbound_dropped <from service> <to host> <port>: a container other than
# the edge cannot open a connection to <to host> (the firewall's inbound
# rules). The probe tool is checked first, so a missing tool fails.
check_inbound_dropped() {
    _desc="$1 cannot open $2:$3 (only the edge may)"
    if run_in "$1" "command -v bash && command -v timeout"; then
        check_in "$1" "${_desc}" "! timeout 4 bash -c '</dev/tcp/$2/$3' 2>/dev/null"
    elif run_in "$1" "command -v nc && command -v timeout"; then
        check_in "$1" "${_desc}" "! timeout 4 nc -z -w 3 $2 $3"
    else
        skip "${_desc} -- no probe tool in $1"
    fi
}

# check_tcp_blocked <from> <host> <port> [what]: <from> cannot open <host>:<port>,
# for containers without php (MySQL: bash; the test stand-ins: python). A
# name that does not resolve counts as blocked only with bash.
check_tcp_blocked() {
    _desc="$1 cannot open $2:$3${4:+ ($4)}"
    if run_in "$1" "command -v bash && command -v timeout"; then
        check_in "$1" "${_desc}" "! timeout 4 bash -c '</dev/tcp/$2/$3' 2>/dev/null"
    elif run_in "$1" "command -v python3"; then
        check_in "$1" "${_desc}" "python3 -c 'import socket,sys; s=socket.socket(); s.settimeout(4); sys.exit(1 if s.connect_ex((\"$2\", $3)) == 0 else 0)'"
    else
        skip "${_desc} -- no probe tool in $1"
    fi
}

# check_firewall_locked <firewall>: a honeypot profile cannot be switched off
# or opened up -- `container-firewall apply` refuses the default ruleset with
# enabled=false, and with an extra outbound rule to the edge, for that reason
# (the message is checked). Rejected before anything is enforced or saved, so
# this changes nothing.
check_firewall_locked() {
    _mod='$d = json_decode(stream_get_contents(STDIN), true);'
    # An image without the lock would ACCEPT these documents (switching a live
    # pool's firewall off), so they are only tried on one that has it.
    if ! run_in "$1" "grep -q LOCKED_OUTBOUND \$(command -v container-firewall)"; then
        fail "$1 runs a firewall image with locked honeypot profiles (rebuild images/container_firewall)"
        return 1
    fi
    check_in "$1" "$1 refuses to be switched off (locked profile)" \
        "container-firewall apply --b64 \$(container-firewall default | php -r '${_mod} \$d[\"enabled\"] = false; echo base64_encode(json_encode(\$d));') 2>&1 | grep -q 'cannot be switched off'"
    check_in "$1" "$1 refuses an outbound rule to the edge (locked profile)" \
        "container-firewall apply --b64 \$(container-firewall default | php -r '${_mod} \$d[\"outbound\"][] = [\"id\" => \"escape\", \"enabled\" => true, \"peer\" => \"reverse_proxy\", \"proto\" => \"tcp\", \"ports\" => \"80\", \"label\" => \"x\"]; echo base64_encode(json_encode(\$d));') 2>&1 | grep -q 'outbound/escape: a honeyp'"
    check_in "$1" "$1 drops every forwarded packet (FW_FWD hooked into FORWARD, v4 and v6)" \
        "iptables -S FORWARD | grep -q -- '-j FW_FWD' && iptables -S FW_FWD | grep -q -- '-j DROP' && ip6tables -S FORWARD | grep -q -- '-j FW_FWD'"
    check_in "$1" "$1 enforces IPv6 too" \
        "container-firewall status | php -r '\$s = json_decode(stream_get_contents(STDIN), true); exit(\$s[\"ipv6\"] === true ? 0 : 1);'"
}

# Gateway (the Docker host's bridge address) of a project network.
network_gateway() {
    docker network inspect -f '{{range .IPAM.Config}}{{.Gateway}} {{end}}' "${PROJECT}_$1" 2>/dev/null | awk '{print $1}'
}
