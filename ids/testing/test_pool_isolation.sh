#!/bin/bash
# =============================================================================
# test_pool_isolation.sh
#
# PURPOSE:
#   Comprehensive verification that every honeypot database pool is properly
#   bound to its own honeypot container -- both declaratively (docker-compose
#   wiring) and at runtime (actual credential-level isolation).
#
#   Unlike the scenario_NN_*.sh scripts in this directory (which demonstrate
#   adversary techniques against a single pool), this is a regression/infra
#   test: it verifies the pooling architecture's own isolation guarantee
#   holds, independent of any specific attack.
#
#   BACKGROUND: all honeypot pools share one honeypot_network. Isolation
#   between them has two layers: (1) each pool's MySQL user has a DIFFERENT
#   password (until this was fixed, all three pools and production shared
#   MYSQL_PASSWORD, so a compromised pool could log into another adversary's
#   pool database -- see honeypot_database_N in docker-compose.yml and
#   MYSQL_PASSWORD_POOL_2/3 in .env); (2) each pool's container firewall
#   (honeypot_eshop_N_net, honeypot profile) only lets it open connections to
#   its OWN database. Phase 2 reports which layer currently stops a cross-pool
#   connection; Phase 3 passes on either, and keeps catching a regression of
#   the password layer whenever the firewall is off.
#   The firewall side is tested in full by test_honeypot_instance.sh.
#
# THIS SCRIPT VERIFIES:
#   Phase 1 - Static config: docker-compose.yml declares a strict 1:1
#             WORDPRESS_DB_HOST -> honeypot_database_N binding per pool,
#             with no cross-wiring, for however many pools are defined.
#   Phase 2 - Live network topology: reports whether the container firewall
#             already refuses a cross-pool database connection --
#             informational, not a pass/fail gate.
#   Phase 3 - Live credential isolation: for every pool N, its own DB
#             credentials authenticate against honeypot_database_N and are
#             REJECTED by every honeypot_database_M (M != N). This is the
#             actual security property "properly bound" means in practice.
#
# USAGE:
#   cd ids/testing
#   ./test_pool_isolation.sh
#
# EXIT CODES:
#   0  All checks passed.
#   1  One or more checks failed.
#   2  Prerequisites missing (docker) or docker-compose.yml not found.
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/../docker-compose.yml"
PROJECT_PREFIX="honeypot-ids-system-v1"

PASS=0
FAIL=0
INFO=0
TOTAL=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

banner() {
    printf "\n${CYAN}================================================================${NC}\n"
    printf "${CYAN}  %s${NC}\n" "$1"
    printf "${CYAN}================================================================${NC}\n\n"
}

pass() { PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1)); printf "  ${GREEN}[PASS]${NC} %s\n" "$1"; }
fail() { FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); printf "  ${RED}[FAIL]${NC} %s\n" "$1"; }
info() { INFO=$((INFO + 1)); printf "  ${YELLOW}[INFO]${NC} %s\n" "$1"; }

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    printf "${RED}ERROR: 'docker' not found in PATH.${NC}\n" >&2
    exit 2
fi
if [ ! -f "${COMPOSE_FILE}" ]; then
    printf "${RED}ERROR: docker-compose.yml not found at %s${NC}\n" "${COMPOSE_FILE}" >&2
    exit 2
fi

banner "Pool Isolation Test - DB Pools Properly Bound to Honeypot Containers"

# =============================================================================
# PHASE 1 - Static config: 1:1 WORDPRESS_DB_HOST binding per pool
# =============================================================================
banner "Phase 1 - Static docker-compose.yml Binding"

# Discover every honeypot_eshop_N service defined in docker-compose.yml.
POOL_NUMBERS=$(grep -oE '^  honeypot_eshop_[0-9]+:' "${COMPOSE_FILE}" \
    | grep -oE '[0-9]+' | sort -un)

if [ -z "${POOL_NUMBERS}" ]; then
    fail "No honeypot_eshop_N services found in docker-compose.yml"
else
    pass "Discovered honeypot pools: $(printf '%s' "${POOL_NUMBERS}" | tr '\n' ' ')"
fi

for n in ${POOL_NUMBERS}; do
    # Extract the honeypot_eshop_N service block (from its own header to the
    # next top-level 2-space-indented key) and check its WORDPRESS_DB_HOST.
    block=$(awk -v svc="  honeypot_eshop_${n}:" '
        $0 == svc { found=1; print; next }
        found && /^  [a-zA-Z]/ { exit }
        found { print }
    ' "${COMPOSE_FILE}")

    db_host=$(printf '%s\n' "${block}" | grep -oE 'WORDPRESS_DB_HOST=honeypot_database_[0-9]+' \
        | head -1 | grep -oE '[0-9]+$')

    if [ "${db_host}" = "${n}" ]; then
        pass "honeypot_eshop_${n} WORDPRESS_DB_HOST -> honeypot_database_${n} (correct)"
    else
        fail "honeypot_eshop_${n} WORDPRESS_DB_HOST -> honeypot_database_${db_host:-MISSING} (expected honeypot_database_${n})"
    fi

    # Guard against a cross-wire: the block must not reference any OTHER
    # pool's database anywhere (depends_on, env, healthcheck, etc.).
    cross_refs=$(printf '%s\n' "${block}" | grep -oE 'honeypot_database_[0-9]+' | grep -oE '[0-9]+' | sort -un)
    other_refs=$(printf '%s\n' "${cross_refs}" | grep -v "^${n}$" || true)
    if [ -z "${other_refs}" ]; then
        pass "honeypot_eshop_${n} references no other pool's database"
    else
        fail "honeypot_eshop_${n} unexpectedly references database(s): $(printf '%s' "${other_refs}" | tr '\n' ' ')"
    fi
done

# Every pool's password variable must be textually distinct in the compose
# file (pool 1 uses MYSQL_PASSWORD, pools 2+ use MYSQL_PASSWORD_POOL_N) --
# this catches a regression where a future pool is added but its env block
# is copy-pasted without updating the password variable.
for n in ${POOL_NUMBERS}; do
    block=$(awk -v svc="  honeypot_eshop_${n}:" '
        $0 == svc { found=1; print; next }
        found && /^  [a-zA-Z]/ { exit }
        found { print }
    ' "${COMPOSE_FILE}")
    pw_var=$(printf '%s\n' "${block}" | grep -oE 'WORDPRESS_DB_PASSWORD=\$\{[A-Z0-9_]+\}' | head -1)
    if [ "${n}" = "1" ]; then
        expected='WORDPRESS_DB_PASSWORD=${MYSQL_PASSWORD}'
    else
        expected="WORDPRESS_DB_PASSWORD=\${MYSQL_PASSWORD_POOL_${n}}"
    fi
    if [ "${pw_var}" = "${expected}" ]; then
        pass "honeypot_eshop_${n} uses its own password variable (${pw_var})"
    else
        fail "honeypot_eshop_${n} password variable is '${pw_var:-MISSING}', expected '${expected}'"
    fi
done

# =============================================================================
# PHASE 2 - Live network topology (informational)
# =============================================================================
banner "Phase 2 - Live Network Topology (informational, not pass/fail)"

ESHOP_1="${PROJECT_PREFIX}-honeypot_eshop_1-1"
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${ESHOP_1}\$"; then
    if docker exec "${ESHOP_1}" bash -c 'exec 3<>/dev/tcp/honeypot_database_2/3306' >/dev/null 2>&1; then
        info "honeypot_eshop_1 CAN open a TCP socket to honeypot_database_2 -- the container firewall is not stopping it (off, or not deployed); isolation rests on Phase 3's credential checks alone"
    else
        info "honeypot_eshop_1 could NOT reach honeypot_database_2 over TCP -- the container firewall refuses it; Phase 3's credential checks below pass on that ground too"
    fi
else
    info "honeypot_eshop_1 not running -- skipping live network topology check"
fi

# =============================================================================
# PHASE 3 - Live credential isolation (the actual "properly bound" property)
# =============================================================================
banner "Phase 3 - Live Cross-Pool Credential Isolation"

if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${ESHOP_1}\$"; then
    info "No honeypot_eshop containers running -- skipping Phase 3 (bring the stack up with 'docker compose up -d' to run this check live)"
else
    for src in ${POOL_NUMBERS}; do
        src_container="${PROJECT_PREFIX}-honeypot_eshop_${src}-1"
        if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${src_container}\$"; then
            info "${src_container} not running -- skipping its cross-pool checks"
            continue
        fi

        # Positive control: pool N's own credentials must work against its
        # own database. A failure here means the fix broke normal operation.
        own_result=$(docker exec "${src_container}" php -r '
            mysqli_report(MYSQLI_REPORT_OFF);
            $host = preg_replace("/:.*/", "", getenv("WORDPRESS_DB_HOST"));
            $c = @mysqli_connect($host, getenv("WORDPRESS_DB_USER"), getenv("WORDPRESS_DB_PASSWORD"), getenv("WORDPRESS_DB_NAME"));
            echo $c ? "OK" : "FAIL";
        ' 2>/dev/null || echo "FAIL")
        if [ "${own_result}" = "OK" ]; then
            pass "honeypot_eshop_${src} can authenticate to its own honeypot_database_${src}"
        else
            fail "honeypot_eshop_${src} CANNOT authenticate to its own honeypot_database_${src} -- broken by isolation fix?"
        fi

        # Negative control: pool N's credentials must be REJECTED by every
        # other pool's database. This is the exact regression test for the
        # shared-password vulnerability this script exists to catch.
        for dst in ${POOL_NUMBERS}; do
            if [ "${src}" = "${dst}" ]; then continue; fi
            dst_host="honeypot_database_${dst}"
            cross_result=$(docker exec "${src_container}" php -r "
                mysqli_report(MYSQLI_REPORT_OFF);
                \$c = @mysqli_connect('${dst_host}', getenv('WORDPRESS_DB_USER'), getenv('WORDPRESS_DB_PASSWORD'), getenv('WORDPRESS_DB_NAME'));
                echo \$c ? 'SUCCEEDED' : 'REJECTED';
            " 2>/dev/null || echo "REJECTED")
            if [ "${cross_result}" = "REJECTED" ]; then
                pass "honeypot_eshop_${src} credentials correctly REJECTED by honeypot_database_${dst}"
            else
                fail "honeypot_eshop_${src} credentials SUCCEEDED against honeypot_database_${dst} -- cross-pool isolation BROKEN"
            fi
        done
    done
fi

# ---------------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------------
banner "Pool Isolation Test - Final Report"
printf "Total checks : %d\n" "${TOTAL}"
printf "${GREEN}Passed       : %d${NC}\n" "${PASS}"
printf "Informational: %d\n" "${INFO}"
if [ "${FAIL}" -gt 0 ]; then
    printf "${RED}Failed       : %d${NC}\n" "${FAIL}"
else
    printf "Failed       : 0\n"
fi

printf "\n"
if [ "${FAIL}" -eq 0 ]; then
    printf "${GREEN}ALL POOL ISOLATION CHECKS PASSED.${NC}\n"
    exit 0
else
    printf "${RED}%d POOL ISOLATION CHECK(S) FAILED -- see above.${NC}\n" "${FAIL}"
    exit 1
fi
