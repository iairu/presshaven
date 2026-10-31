#!/bin/bash
# replicate_content_to_honeypot.sh - Periodically mirrors production's
# content (pages, posts, products, and the taxonomy/media metadata that
# renders them) into each honeypot pool database, so a honeypot never
# silently goes stale relative to the real site.
#
# Run by the `honeypot_content_sync` service (docker-compose.yml) in a
# `while true` loop, once every REPLICATION_INTERVAL_SECONDS.
#
# WHAT GETS REPLICATED (deliberately a strict allow-list, not "everything"):
#   wp_posts        - post_type IN (page, post, product, product_variation,
#                      attachment), post_status IN (publish, inherit)
#   wp_postmeta     - scoped to the post IDs above (prices, SKUs, attachment
#                      metadata / _thumbnail_id, ...)
#   wp_term_relationships - scoped to the post IDs above (category/tag/
#                      product_cat assignments)
#   wp_terms, wp_term_taxonomy - copied in full each cycle (small reference
#                      tables; REPLACE INTO, not scoped -- see below)
#   wp_wc_product_meta_lookup  - scoped to the product IDs above, only if the
#                      table exists (WooCommerce-version-dependent)
#
# NEVER REPLICATED, ON PURPOSE: wp_users, wp_usermeta, or any WooCommerce
# order/customer/payment table (wp_wc_orders*, wp_woocommerce_order_*,
# wp_wc_customer_lookup, wp_woocommerce_payment_tokens*, wp_woocommerce_api_keys,
# wp_woocommerce_sessions, ...). Real customer/order data must never reach a
# honeypot database -- this is the same principle
# honeypot_database_migrations/01_clean-honeypot-data.sql already enforces
# for the one-time initial seed; this script must not reintroduce it on an
# ongoing basis. The table list above is an allow-list, not a "copy
# everything except" list, specifically so a schema change on production
# can't accidentally start leaking a new sensitive table here.
#
# ZERO-DOWNTIME / NON-DESTRUCTIVE APPLY STRATEGY:
#   Never DROP/recreate a table (that's what would actually cause visible
#   downtime on a honeypot pool's live DB, mid-user-session). Instead:
#     - wp_posts/wp_postmeta/wp_term_relationships/wp_wc_product_meta_lookup:
#       DELETE rows scoped to the EXACT production ID set, then INSERT fresh
#       copies of those same rows, all in one short transaction. Scoped
#       deletes mean anything a user added (their own posts, uploaded-
#       shell metadata, unrelated rows) is never touched -- same "never
#       destroy evidence" principle docker-compose.yml's init_setup already
#       documents for its file-sync step.
#     - wp_terms/wp_term_taxonomy: REPLACE INTO the full current production
#       content, no delete/scoping -- same non-destructive add/update-only
#       pattern init_setup's sync_files() already uses for files.
#   The production-side read uses --single-transaction so it never locks
#   production tables either.
#
# PATTERN GATING (coordinates with pool_router.lua's is_pool_healthy()):
#   Around each pool's own apply step, this script sets/clears a short-TTL
#   Redis flag (honeypot_pool_replicating:<N>). init_worker.lua mirrors that
#   into the shared dict pool_router.lua's is_pool_healthy() already reads,
#   so a pool mid-replication is transparently skipped for NEW user
#   assignments (via the existing unhealthy-pool failover path) and
#   already-bound users on that pool are transparently served by another
#   pool for the few seconds the sync takes -- no new blocking logic, no
#   dropped connections. See pool_router.lua for the other half of this.
#
# Pools are replicated ONE AT A TIME, never concurrently, so at least 2 of 3
# pools are always fully available throughout every cycle.

set -eu

MYSQL_USER="production_user"
MYSQL_DATABASE="production_database"
PROD_HOST="production_database"

# Pools 1-3 are fixed in docker-compose.yml; pool_manager adds more at runtime
# and lists every healthy pool in Redis (honeypot_pool:ready). POOL_NUMS is
# re-read each cycle by refresh_pool_nums() below; this is the fallback.
POOL_NUMS="1 2 3"

REDIS_HOST="${REDIS_HOST:-session_store}"
REPLICATION_INTERVAL_SECONDS="${REPLICATION_INTERVAL_SECONDS:-300}"

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

log() {
    echo "[content-sync $(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

# Pool number -> that pool's own DB user password (never production's
# MYSQL_PASSWORD, which only reads production -- see docker-compose.yml).
pool_password() {
    # One-shot mode (see the bottom of this file): pool_manager passes the new
    # pool's password directly; it is not registered anywhere yet.
    if [ -n "${POOL_DB_PASSWORD:-}" ]; then
        echo "$POOL_DB_PASSWORD"
        return
    fi
    case "$1" in
        1) echo "$MYSQL_PASSWORD_POOL_1" ;;
        2) echo "$MYSQL_PASSWORD_POOL_2" ;;
        3) echo "$MYSQL_PASSWORD_POOL_3" ;;
        # Runtime pools get a random password from pool_manager, kept in Redis.
        *) redis-cli -h "$REDIS_HOST" -a "$REDIS_PASSWORD" GET "honeypot_pool:pw:$1" 2>/dev/null ;;
    esac
}

pool_host() {
    echo "honeypot_database_$1"
}

# Replicate to every pool pool_manager reports ready; keep the previous list if
# Redis can't be reached this cycle.
refresh_pool_nums() {
    local nums
    nums=$(redis-cli -h "$REDIS_HOST" -a "$REDIS_PASSWORD" SMEMBERS honeypot_pool:ready 2>/dev/null \
           | grep -E '^[0-9]+$' | sort -n | tr '\n' ' ')
    if [ -n "$nums" ]; then
        POOL_NUMS="$nums"
    fi
}

# Deliberately never fatal (the caller does NOT need `|| true`): losing this
# flag for one cycle only means pool_router.lua's is_pool_healthy() keeps
# treating the pool as healthy during its replication window (its documented
# default for missing data) -- a missed optimization, not a correctness
# problem -- and must never be allowed to abort the whole sync cycle over a
# transient Redis hiccup.
# --no-auth-warning deliberately omitted: this container's `yum install
# redis` (see images/content_sync/Dockerfile) pulls in whatever redis-cli happens to be
# in this EL7-based image's default repos -- redis-cli 3.2.12, from 2016,
# predating --no-auth-warning (added in Redis 5.0). Confirmed live that an
# unrecognized flag is a FATAL parse error for redis-cli, not a warning --
# every single invocation of both functions below was silently failing
# ("Unrecognized option or bad number of args for: '--no-auth-warning'"),
# meaning this pattern-gating mechanism had never actually run, on any
# cycle, since this flag was added. The "using a password on the command
# line" warning this flag exists to suppress is harmless log noise by
# comparison -- 2>/dev/null on both calls hides it without needing the
# flag at all (and works on any redis-cli version).
redis_set_replicating() {
    redis-cli -h "$REDIS_HOST" -a "$REDIS_PASSWORD" \
        SET "honeypot_pool_replicating:$1" 1 EX 30 >/dev/null 2>/dev/null \
        || log "pool $1: could not set replicating flag in Redis (continuing without it)"
}

redis_clear_replicating() {
    redis-cli -h "$REDIS_HOST" -a "$REDIS_PASSWORD" \
        DEL "honeypot_pool_replicating:$1" >/dev/null 2>/dev/null \
        || log "pool $1: could not clear replicating flag in Redis (will self-expire via its 30s TTL)"
}

# --default-character-set=binary on BOTH the dump and the restore (below) is
# load-bearing, not cosmetic. Some postmeta rows hold PHP-serialized blobs
# (e.g. WooCommerce's _product_attributes), whose strings are byte-length
# prefixed: s:16:"Ethiopia · Guji". Without a pinned charset the dump/restore
# pipe round-trips through the client's default connection charset and
# re-encodes multibyte bytes (· = C2 B7 -> C3 82 C2 B7), so the stored byte
# count no longer matches the s:16: prefix and PHP's unserialize() fails. On a
# product that means get_variation_attributes() returns nothing, no variation
# dropdowns render, and "Add to cart" is blocked. binary transfers the stored
# bytes verbatim, keeping the prefix valid.
prod_mysql() {
    mysql -h "$PROD_HOST" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" --default-character-set=binary -N "$@"
}

prod_mysqldump() {
    # --no-tablespaces: without it, mysqldump also tries to dump tablespace
    # metadata up front, which needs the PROCESS privilege -- production_user
    # doesn't have (and doesn't need) it for anything else this script does.
    # Confirmed live: every cycle was failing with "Access denied; you need
    # (at least one of) the PROCESS privilege(s) ... when trying to dump
    # tablespaces" before this, immediately aborting prod_mysqldump() with no
    # actual table data ever dumped.
    mysqldump -h "$PROD_HOST" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" \
        --default-character-set=binary \
        --single-transaction --no-create-info --skip-add-drop-table \
        --skip-triggers --skip-add-locks --skip-comments --compact \
        --no-tablespaces "$@"
}

# ---------------------------------------------------------------------------
# Site & WooCommerce SETTINGS replicated alongside content (wp_options).
#
# So that an operator editing the real shop (store address, currency, tax &
# catalog display, theme customizer) sees those changes in every honeypot pool
# too -- not just pages/posts/products -- a curated set of presentational
# option rows is mirrored as well. This is an ALLOW-LIST, not "everything
# except": only the exact option_names below (plus theme_mods_*) are ever
# copied. A payment gateway's own settings row (woocommerce_stripe_settings,
# woocommerce_bacs_settings, ...) holds live API keys / bank details and is
# deliberately NOT listed, so it never reaches a honeypot.
#
# SETTINGS_DENY_RE is defence-in-depth on top of the explicit list: even if a
# listed name ever began carrying a secret, any option_name matching
# api/key/secret/token/salt/password/smtp/stripe/paypal/license/_transient etc.
# is dropped. wp_users/wp_usermeta and every order/customer/payment table stay
# excluded exactly as before -- they are never dumped at all.
SETTINGS_ALLOW="option_name IN (\
'blogname','blogdescription','show_on_front','page_on_front','page_for_posts',\
'posts_per_page','date_format','time_format','start_of_week','timezone_string',\
'template','stylesheet',\
'woocommerce_demo_store','woocommerce_demo_store_notice',\
'woocommerce_currency','woocommerce_currency_pos','woocommerce_price_thousand_sep',\
'woocommerce_price_decimal_sep','woocommerce_price_num_decimals',\
'woocommerce_weight_unit','woocommerce_dimension_unit',\
'woocommerce_store_address','woocommerce_store_address_2','woocommerce_store_city',\
'woocommerce_store_postcode','woocommerce_default_country',\
'woocommerce_shop_page_id','woocommerce_cart_page_id','woocommerce_checkout_page_id',\
'woocommerce_myaccount_page_id','woocommerce_terms_page_id',\
'woocommerce_catalog_columns','woocommerce_catalog_rows',\
'woocommerce_enable_reviews','woocommerce_shop_page_display','woocommerce_category_archive_display',\
'woocommerce_calc_taxes','woocommerce_prices_include_tax','woocommerce_tax_based_on',\
'woocommerce_default_customer_address','woocommerce_tax_display_shop',\
'woocommerce_tax_display_cart','woocommerce_tax_total_display') \
OR option_name LIKE 'theme_mods_%'"
SETTINGS_DENY_RE='(secret|token|api[_-]?key|_key$|passwd|password|salt|nonce|_auth|smtp|mailserver|stripe|paypal|ppcp|_gateway|payment|_license|client_id|client_secret|access_token|refresh_token|private|_transient)'

# ---------------------------------------------------------------------------
# build_sync_sql: read production's current content ID set once, dump it,
# and write one complete apply script (delete-scoped + fresh inserts) to
# $WORKDIR/content_sync.sql. Re-used unmodified across all three pools, since
# production's content is read once per cycle, not once per pool.
#
# Returns 1 (nothing written) if production currently has no matching
# content -- avoids ever emitting "WHERE id IN ()", which is invalid SQL --
# and 2 if dumping production's content failed (the script is incomplete).
# ---------------------------------------------------------------------------
build_sync_sql() {
    local ids table_exists sql_file="$WORKDIR/content_sync.sql"

    # group_concat_max_len: MySQL's default (1024 bytes) silently truncates
    # the list after ~200 IDs -- the catalog's variations and attachments
    # alone are more -- so most of the content was never mirrored.
    ids=$(prod_mysql "$MYSQL_DATABASE" -e \
        "SET SESSION group_concat_max_len = 16777216; SELECT GROUP_CONCAT(ID) FROM wp_posts WHERE post_type IN ('page','post','product','product_variation','attachment') AND post_status IN ('publish','inherit')")

    if [ -z "$ids" ] || [ "$ids" = "NULL" ]; then
        log "production has no page/post/product/attachment content yet -- skipping this cycle"
        return 1
    fi

    table_exists=$(prod_mysql "$MYSQL_DATABASE" -e \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$MYSQL_DATABASE' AND table_name='wp_wc_product_meta_lookup'")

    {
        echo "SET FOREIGN_KEY_CHECKS=0;"
        echo "START TRANSACTION;"
        echo "DELETE FROM wp_postmeta WHERE post_id IN ($ids);"
        echo "DELETE FROM wp_term_relationships WHERE object_id IN ($ids);"
        if [ "$table_exists" = "1" ]; then
            echo "DELETE FROM wp_wc_product_meta_lookup WHERE product_id IN ($ids);"
        fi
        echo "DELETE FROM wp_posts WHERE ID IN ($ids);"
    } > "$sql_file"

    # Parents before children: wp_posts rows must exist before wp_postmeta /
    # wp_term_relationships rows that reference them are inserted.
    #
    # --replace (REPLACE INTO, not plain INSERT): the honeypot pool is seeded
    # with fixed-ID dummy rows by 01_clean-honeypot-data.sql (e.g. wp_postmeta
    # meta_id 100-104, the dummy product's meta). Those meta_ids overlap
    # production's real meta_id space, but the scoped DELETEs above only remove
    # rows by post_id/object_id/ID -- a dummy row whose OWN primary key
    # collides with a production row's primary key (while sitting on a
    # different post) is not deleted, so a plain INSERT of production's row
    # failed with "Duplicate entry '100' for key 'PRIMARY'" (confirmed live).
    # REPLACE deletes any row with the same primary key first, so the sync is
    # idempotent regardless of the pool's pre-existing dummy data, and the
    # honeypot content still ends up an exact mirror of production.
    #
    # Each dump returns 2 on failure: set -e does not apply inside a function
    # called from `if !` or `||`, so a failed dump used to leave a script
    # that DELETEs the content and re-inserts only part of it.
    prod_mysqldump --replace --where="ID IN ($ids)" "$MYSQL_DATABASE" wp_posts >> "$sql_file" || return 2
    prod_mysqldump --replace --where="post_id IN ($ids)" "$MYSQL_DATABASE" wp_postmeta >> "$sql_file" || return 2
    prod_mysqldump --replace --where="object_id IN ($ids)" "$MYSQL_DATABASE" wp_term_relationships >> "$sql_file" || return 2
    if [ "$table_exists" = "1" ]; then
        prod_mysqldump --replace --where="product_id IN ($ids)" "$MYSQL_DATABASE" wp_wc_product_meta_lookup >> "$sql_file" || return 2
    fi

    # Small reference tables: full add/update-only refresh, no prior DELETE
    # (mirrors init_setup's sync_files() non-destructive philosophy).
    prod_mysqldump --replace "$MYSQL_DATABASE" wp_terms wp_term_taxonomy >> "$sql_file" || return 2

    # Settings (wp_options): allow-listed presentational rows only, with the
    # defensive denylist on top. REPLACE INTO without a prior DELETE -- the
    # option_name column is UNIQUE, so each row updates in place and a pool's
    # own honeypot-only options are never removed (same non-destructive apply
    # as wp_terms above). See SETTINGS_ALLOW / SETTINGS_DENY_RE above.
    # _utf8mb4: the connection charset is binary (see prod_mysql), so a bare
    # literal is a binary string, and MySQL 8's ICU regex refuses to match a
    # binary pattern against a utf8mb4 column (ERROR 3995) -- confirmed live
    # after the 5.7 -> 8.4 upgrade, every cycle failed here.
    prod_mysqldump --replace \
        --where="($SETTINGS_ALLOW) AND option_name NOT REGEXP _utf8mb4'$SETTINGS_DENY_RE'" \
        "$MYSQL_DATABASE" wp_options >> "$sql_file" || return 2

    {
        echo "COMMIT;"
        echo "SET FOREIGN_KEY_CHECKS=1;"
    } >> "$sql_file"

    local id_count
    id_count=$(echo "$ids" | tr ',' '\n' | wc -l)
    log "built sync script covering $id_count production content item(s)"
    return 0
}

# Pool databases are where attackers end up: a client of one never sends
# local files (--local-infile=0), so a rogue server there cannot read this
# container's environment -- production's and Redis's passwords.
replicate_to_pool() {
    local pool_num="$1" db_host db_pass
    db_host=$(pool_host "$pool_num")
    db_pass=$(pool_password "$pool_num")

    log "pool $pool_num ($db_host): replication starting"
    redis_set_replicating "$pool_num"

    if mysql --local-infile=0 -h "$db_host" -u"$MYSQL_USER" -p"$db_pass" --default-character-set=binary "$MYSQL_DATABASE" < "$WORKDIR/content_sync.sql"; then
        log "pool $pool_num ($db_host): replication complete"
    else
        log "pool $pool_num ($db_host): replication FAILED -- pool DB left as-is, will retry next cycle"
    fi

    redis_clear_replicating "$pool_num"
}

sync_cycle() {
    refresh_pool_nums
    local rc=0
    build_sync_sql || rc=$?
    if [ "$rc" -ne 0 ]; then
        [ "$rc" -eq 2 ] && log "dumping production's content failed -- skipping this cycle"
        return 0
    fi

    for pool_num in $POOL_NUMS; do
        replicate_to_pool "$pool_num"
        # Small stagger between pools -- no correctness requirement, just
        # avoids piling all three pools' DB load onto the exact same instant.
        sleep 2
    done
}

# One-shot: `replicate_content_to_honeypot.sh --once N` mirrors production's
# content into pool N a single time and exits non-zero if that failed. Used by
# pool_manager while it builds a pool, BEFORE the pool is registered as ready:
# its database starts from the install-time snapshot of production, so without
# this a new pool would serve a stale catalog (and a diverted visitor's cart,
# rebuilt from product IDs, would come up empty) until the next cycle above.
if [ "${1:-}" = "--once" ] && [ -n "${2:-}" ]; then
    rc=0
    build_sync_sql || rc=$?
    if [ "$rc" -eq 2 ]; then
        log "pool $2: dumping production's content failed"
        exit 1
    fi
    if [ "$rc" -ne 0 ]; then
        exit 0      # production has no content yet: nothing to mirror
    fi
    db_host=$(pool_host "$2")
    if mysql --local-infile=0 -h "$db_host" -u"$MYSQL_USER" -p"$(pool_password "$2")" --default-character-set=binary "$MYSQL_DATABASE" \
            < "$WORKDIR/content_sync.sql"; then
        log "pool $2 ($db_host): initial content replication complete"
        exit 0
    fi
    log "pool $2 ($db_host): initial content replication FAILED"
    exit 1
fi

log "honeypot content sync starting -- interval ${REPLICATION_INTERVAL_SECONDS}s"

while true; do
    sync_cycle || log "sync cycle failed, will retry next interval"
    sleep "$REPLICATION_INTERVAL_SECONDS"
done
