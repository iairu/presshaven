# WordPress / WooCommerce Layer

`production_eshop_files/` is a **real** WordPress + WooCommerce install with a custom
`omega-storefront` theme and mu-plugins, served on the production path. Three honeypot
pool instances mirror production's fingerprint (same DB name, same theme/plugins) so a
diverted user sees a consistent fake environment once their IP is bound by
[`pool_router`](pooling.md).

The code is fully git-tracked, so a fresh clone already has the entire WordPress
codebase — but the databases start empty and are filled by the
[seed jobs](seeding.md).

!!! note "Pristine core for diffing"
    `ids/scripts/fetch_pristine_wordpress.sh` downloads a stock WordPress core of the
    same version into the gitignored `production_eshop_files_fresh_for_diff/`, so you
    can diff the running site against vanilla. It used to be committed (81 MB of stock
    files).

## File sync, not drift

`init_setup`'s WordPress file-copy step uses **`rsync -a`** and re-runs on every
`docker compose up`, replacing an old one-shot `tar` copy that skipped once a
destination had any content (which silently let pool volumes drift from source).

The sync deliberately does **not** use `--delete`: it's one-directional add/update, so
files that exist only in a pool's volume — attacker-uploaded webshells under
`wp-content/uploads`, other forensic artifacts — are **left untouched**. Verified by
planting a file in a pool, re-running `init_setup`, and confirming it survived. Files
retired from production are removed from pools explicitly in `init_setup` instead.

Database data directories keep the old one-shot skip-if-populated behavior — that's
live, mutable MySQL state where always-resync would be actively wrong.

## Plugin roster

Installed directly via WP core's `activate_plugin()`/`ZipArchive` against
`wp-load.php`:

| Plugin | Slug | Production | Honeypot pools |
|---|---|---|---|
| Cart Abandonment Recovery for WooCommerce | `woo-cart-abandonment-recovery` | <span class="chip ok">active</span> | <span class="chip ok">active</span> |
| WPify Woo (CZ/SK features) | `wpify-woo` | <span class="chip ok">active</span> | <span class="chip ok">active</span> |
| HubSpot All-In-One Marketing | `leadin` | <span class="chip ok">active</span> | <span class="chip ok">active</span> |
| Elementor | `elementor` | <span class="chip ok">active</span> | <span class="chip ok">active</span> |
| WP Mail SMTP | `wp-mail-smtp` | <span class="chip ok">active</span> | <span class="chip ok">active</span> |
| Cloudflare (official) | `cloudflare` | <span class="chip ok">active</span> | <span class="chip ok">active</span> |
| Two-Factor (official) | `two-factor` | <span class="chip ok">active</span> | <span class="chip warn">installed, inactive</span> |
| Wordfence Security | `wordfence` | <span class="chip ok">active</span> | <span class="chip warn">installed, inactive</span> |
| Stripe gateway | `woocommerce-gateway-stripe` | <span class="chip ok">active</span> | <span class="chip ok">active</span> |
| WP REST API (standalone) | `rest-api` | <span class="chip warn">installed, inactive</span> | <span class="chip warn">installed, inactive</span> |

### Why Wordfence & Two-Factor are inactive on pools

Both are **defensive/blocking** plugins — Wordfence's firewall and login-attempt
limiting, Two-Factor's mandatory second login step. Activating either would work
directly against the honeypot's purpose of staying **genuinely exploitable**.

The plugin *files* are still synced to the pools (so a user enumerating installed
plugins via `readme.txt`/asset paths sees the same fingerprint as production), but
each pool's own `active_plugins` DB option leaves them off. This is the same reasoning
`init_setup` applies by stripping `production-hardening.php` from pool files.

!!! info "Not configured — deliberately not fabricated"
    Cloudflare (API token + zone), Wordfence (license), HubSpot/`leadin` (account),
    WP Mail SMTP (an SMTP provider) and Elementor Pro all need real credentials. They
    run on free-tier defaults and show a normal "connect your account" admin notice
    until configured.

## WP-CLI works (and the bug that hid it)

An earlier writeup claimed `wp-cli` couldn't be used and blamed a WooCommerce/PHP 8.1
gap. The **real** cause was a bug in `production-hardening.php`'s `rest_endpoints`
filter: a first fix checked `is_array($handler)`, which let WordPress core's per-route
`'schema'` entry (a plain 2-element callable) through, and the code then wrote a
`permission_callback` key into it — turning a valid 2-element callable into an invalid
3-element array (`array must have exactly two members`).

Fixed by checking for a `callback` key specifically
(`! is_array($handler) || ! isset($handler['callback'])`), which distinguishes a real
per-HTTP-method handler from the `'schema'` entry. Verified end-to-end:
`wp core install`, `wp plugin activate woocommerce` and every subsequent `wp` command
work with the hardening filter fully active (`/wp/v2/users` still auth-gated). This is
what [`scripts/seed_wordpress_db.sh`](seeding.md) is built on.

## Hardening (production only)

Production gets XML-RPC disablement, hotlink protection, version-fingerprint
stripping, backup automation and container capability limits — all of which the
honeypot pools deliberately lack. The full pass, including the bugs found applying it,
is on the [Production Hardening](../operations/hardening.md) page.
