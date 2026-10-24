#!/bin/sh
# update_wordpress.sh - Check for and apply WordPress core + WooCommerce
# upgrades, driven by the dashboard's "WordPress Update" page.
#
# RUN BY: the same four one-shot wp-cli seed services as seed_wordpress_db.sh
# (production_db_seed + honeypot_db_seed_1/2/3 -- see docker-compose.yml),
# invoked on demand as `docker compose run --rm --no-deps <service>
# sh /update_wordpress.sh <mode>`. Which WordPress instance it touches is
# decided entirely by that service's /var/www/html mount and WORDPRESS_DB_*
# env (identical arrangement to the seed script), not by this script.
#
# MODES:
#   --check
#       Emit a single JSON object on stdout describing installed vs. latest
#       versions of WordPress core and WooCommerce and whether an update is
#       available. All diagnostics go to stderr so stdout is clean JSON the
#       dashboard (core/wp_update.py) can parse. Read-only -- downloads
#       nothing, changes nothing.
#
#   --apply   (run against PRODUCTION only)
#       Download + install the newest WordPress core and WooCommerce plugin
#       files INTO /var/www/html (for production that bind-mount is the
#       git-tracked production_eshop_files/ tree), run the WordPress core DB
#       migration, then the WooCommerce DB migration. init_setup's rsync then
#       mirrors the updated files into every pool volume; each pool is brought
#       to the new schema with --apply-db-only below.
#
#   --apply-db-only   (run against each honeypot POOL after the file re-sync)
#       Run ONLY the WordPress core + WooCommerce DB migrations against this
#       instance's database. The new plugin/core FILES are expected to already
#       be present (init_setup rsynced them from production), so nothing is
#       downloaded -- this just advances the schema to match.
#
# WHY THE FILE/DB SPLIT: a pool's files live in a named volume that init_setup
# already keeps in lockstep with production_eshop_files/ (one-directional rsync
# every boot). Re-downloading core into every pool would be wasteful and could
# even diverge a pool from production if wordpress.org served a different build
# between runs. Updating production's files once and rsyncing is both faster and
# guarantees every instance runs byte-identical code; only the per-database
# migration has to run separately, because each pool has its own database.
#
# NETWORK: --check and --apply reach api.wordpress.org / downloads.wordpress.org.
# On an air-gapped demo stack those calls fail; the script degrades gracefully
# (--check reports "up to date / could not reach wordpress.org" rather than
# erroring; --apply logs the failure and exits non-zero so the dashboard can
# surface it and clear maintenance). --apply-db-only needs no network.
set -u

MODE="${1:-}"

# --allow-root + --path: identical rationale to seed_wordpress_db.sh -- the
# official wordpress:cli image runs as root and wp-cli refuses by default.
WP="wp --allow-root --path=/var/www/html"

now_iso() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
# All human-readable logging goes to STDERR; --check keeps stdout pure JSON.
log() { echo "[UPDATE] $(now_iso) $*" >&2; }

# Run a command, stream its combined output to stderr with a prefix, and return
# the COMMAND's own exit status. A bare `cmd | while read ...` can't do this:
# a POSIX pipeline's status is the last stage's (the while loop), which is
# almost always 0, so wp-cli failures would be silently treated as success.
run_logged() {
    _prefix="$1"; shift
    _tmp="$(mktemp 2>/dev/null || echo /tmp/wp_update_$$.log)"
    "$@" >"$_tmp" 2>&1
    _rc=$?
    while IFS= read -r _l; do log "  ${_prefix}: $_l"; done < "$_tmp"
    rm -f "$_tmp"
    return "$_rc"
}

cd /var/www/html 2>/dev/null || { log "ERROR: /var/www/html not present"; exit 1; }

if ! $WP core is-installed 2>/dev/null; then
    log "ERROR: WordPress is not installed in this instance -- nothing to update."
    # Still emit valid JSON for --check so the dashboard can show the reason.
    if [ "$MODE" = "--check" ]; then
        printf '{"ok":false,"error":"wordpress-not-installed"}\n'
        exit 0
    fi
    exit 1
fi

# ---------------------------------------------------------------------------
# PRESERVE_FILES -- custom files under wp-content that are NOT part of the
# WordPress distribution and MUST survive a core update.
#
# wp-content/db.php is the db-proxy layer's database-router drop-in (see
# production_eshop_files/wp-content/db.php): WordPress loads it before anything
# else and it binds $wpdb to the production OR the honeypot database per the
# proxy's X-Honeypot-Backend decision. Lose it and the whole single-eshop /
# two-database honeynet topology silently collapses back to one database --
# every request would hit production, including an adversary's.
#
# WordPress's own core updater already skips wp-content when it copies new
# files (wp-admin/includes/update-core.php: $skip = array('wp-content', ...),
# and it only ever READS db.php, for a MySQL-version compat check), so under
# current WordPress these files are safe. snapshot_preserved/restore_preserved
# make that a GUARANTEE independent of WordPress internals: we copy each file
# aside before the update and, afterwards, restore it byte-for-byte if the
# update removed or changed it. Space-separated, paths relative to
# /var/www/html.
#
# Only applied on --apply (production): --apply-db-only touches no files, and
# the pools' own copies arrive via init_setup's rsync from this very tree, so
# restoring here is what keeps the pools correct too.
PRESERVE_FILES="wp-content/db.php"
PRESERVE_DIR=""

snapshot_preserved() {
    PRESERVE_DIR="$(mktemp -d 2>/dev/null || echo /tmp/wp_preserve_$$)"
    mkdir -p "$PRESERVE_DIR"
    for rel in $PRESERVE_FILES; do
        if [ -f "/var/www/html/$rel" ]; then
            mkdir -p "$PRESERVE_DIR/$(dirname "$rel")"
            cp -p "/var/www/html/$rel" "$PRESERVE_DIR/$rel" \
                && log "  Snapshotted drop-in before update: $rel"
        else
            log "  Note: $rel not present before update -- nothing to preserve."
        fi
    done
}

# Restore any preserved file the update dropped or altered. Returns 0 always:
# a restore means the guarantee held, not that the update failed.
restore_preserved() {
    [ -n "$PRESERVE_DIR" ] || return 0
    for rel in $PRESERVE_FILES; do
        saved="$PRESERVE_DIR/$rel"
        live="/var/www/html/$rel"
        [ -f "$saved" ] || continue
        if [ ! -f "$live" ]; then
            log "  WARNING: the update removed $rel -- restoring the preserved drop-in."
            mkdir -p "$(dirname "$live")"
            cp -p "$saved" "$live"
        elif ! cmp -s "$saved" "$live"; then
            log "  WARNING: the update modified $rel -- restoring the preserved drop-in."
            cp -p "$saved" "$live"
        else
            log "  Verified preserved (unchanged by the update): $rel"
        fi
    done
    rm -rf "$PRESERVE_DIR"
    PRESERVE_DIR=""
}

# Resolve the first administrator id once; WooCommerce's `wp wc update` wants a
# user context. Best-effort -- an empty value just means we omit --user.
admin_id() {
    $WP user list --role=administrator --field=ID --format=ids 2>/dev/null \
        | tr ' ' '\n' | grep -E '^[0-9]+$' | head -n1
}

# Run the WooCommerce database migration. Prefer the official `wp wc update`
# (registered by WooCommerce's own CLI); fall back to invoking the updater
# directly via `wp eval` on an older/newer WC where the command name differs.
wc_db_update() {
    uid="$(admin_id)"
    if [ -n "$uid" ]; then
        run_logged "wc" $WP wc update --user="$uid" && return 0
    else
        run_logged "wc" $WP wc update && return 0
    fi
    log "  'wp wc update' unavailable or failed -- trying WC_Install::update() via eval."
    run_logged "wc-eval" $WP eval 'if (class_exists("WC_Install")) { WC_Install::update(); WC_Install::update_db_version(); echo "WC_Install::update() ran\n"; } else { echo "WC_Install missing\n"; }'
}

case "$MODE" in
    --check)
        errors=""
        add_error() { errors="${errors}${errors:+;}$1"; }

        wp_installed="$($WP core version 2>/dev/null)"
        # check-update lists only versions NEWER than installed; empty when
        # current OR when wordpress.org is unreachable (we can't tell the two
        # apart from exit status alone, so a failed call just reports "current").
        wp_latest="$($WP core check-update --field=version --format=csv 2>/dev/null \
            | grep -vi '^version$' | grep -E '^[0-9]' | sort -V | tail -n1)"
        if [ -z "$wp_latest" ]; then
            wp_latest="$wp_installed"
        fi

        wc_installed="$($WP plugin get woocommerce --field=version 2>/dev/null)"
        wc_status="$($WP plugin list --name=woocommerce --field=update --format=csv 2>/dev/null \
            | grep -vi '^update$' | head -n1)"
        wc_latest="$($WP plugin list --name=woocommerce --field=update_version --format=csv 2>/dev/null \
            | grep -vi '^update_version$' | grep -E '^[0-9]' | head -n1)"
        if [ -z "$wc_latest" ] || [ "$wc_status" != "available" ]; then
            wc_latest="$wc_installed"
        fi

        wp_avail=false
        [ -n "$wp_latest" ] && [ "$wp_latest" != "$wp_installed" ] && wp_avail=true
        wc_avail=false
        [ -n "$wc_latest" ] && [ "$wc_latest" != "$wc_installed" ] && wc_avail=true

        [ -n "$wp_installed" ] || add_error "could-not-read-core-version"
        [ -n "$wc_installed" ] || add_error "woocommerce-not-found"

        printf '{"ok":true,"wordpress":{"installed":"%s","latest":"%s","update_available":%s},"woocommerce":{"installed":"%s","latest":"%s","update_available":%s},"errors":"%s"}\n' \
            "$wp_installed" "$wp_latest" "$wp_avail" \
            "$wc_installed" "$wc_latest" "$wc_avail" \
            "$errors"
        exit 0
        ;;

    --apply)
        rc=0
        # Snapshot the db-proxy drop-in (and any other custom wp-content file)
        # before the update touches any files -- see PRESERVE_FILES.
        snapshot_preserved
        log "Updating WordPress core files + database (production)..."
        if ! run_logged "core" $WP core update; then
            log "  ERROR: 'wp core update' failed (wordpress.org unreachable?)."
            rc=1
        fi

        log "Updating WooCommerce plugin files..."
        if ! run_logged "wc-plugin" $WP plugin update woocommerce; then
            log "  ERROR: 'wp plugin update woocommerce' failed (download.wordpress.org unreachable?)."
            rc=1
        fi

        # All file-touching steps are done: guarantee the drop-ins survived
        # BEFORE the DB migrations run (so db.php is intact for anything that
        # loads WordPress thereafter).
        restore_preserved

        log "Running WordPress core DB migration..."
        run_logged "core-db" $WP core update-db || rc=1
        log "Running WooCommerce DB migration..."
        wc_db_update || rc=1

        if [ "$rc" -eq 0 ]; then
            log "Production update complete. Installed: WP $($WP core version 2>/dev/null), WooCommerce $($WP plugin get woocommerce --field=version 2>/dev/null)."
        else
            log "Production update finished WITH ERRORS (see above)."
        fi
        exit "$rc"
        ;;

    --apply-db-only)
        rc=0
        log "Running WordPress core DB migration (pool -- files already synced)..."
        run_logged "core-db" $WP core update-db || rc=1
        log "Running WooCommerce DB migration (pool)..."
        wc_db_update || rc=1
        if [ "$rc" -eq 0 ]; then
            log "Pool DB migration complete. Installed: WP $($WP core version 2>/dev/null), WooCommerce $($WP plugin get woocommerce --field=version 2>/dev/null)."
        else
            log "Pool DB migration finished WITH ERRORS (see above)."
        fi
        exit "$rc"
        ;;

    *)
        log "Usage: update_wordpress.sh --check | --apply | --apply-db-only"
        exit 2
        ;;
esac
