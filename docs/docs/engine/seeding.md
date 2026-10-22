# Seeding the Storefront

A fresh clone already has the entire WordPress **codebase** (it's git-tracked), but
`production_database` and all three `honeypot_database_N` start with **zero tables** —
nothing had ever run `wp core install`. The seed jobs fix that.

!!! info "This was the real cause of a recurring error"
    The recurring `WordPress database error: Table '...wp_options' doesn't exist` was
    not an Elementor bug — it was WordPress core failing on the very first option
    read, on *any* request, because no database had a schema. It recurred on a clock
    because `wp_install_state.lua`'s 30 s health probe hits `wp-admin/install.php`
    every cycle.

## The Fernhill Coffee Roasters demo store

Everything the storefront shows is **generated, not scraped**: the brand, farms and
reviewers are invented, and product photography is procedural illustration. It lives
in `ids/eshop_seed/`:

| Path | What |
|---|---|
| `catalog.py` | Single source of truth: categories, 26 products, copy, variations, reviews |
| `art.py`, `build_assets.py` | QPainter illustration engine and renderer |
| `catalog.json`, `products/`, `site/` | Rendered output (committed; a fresh clone never rebuilds) |
| `pages.php`, `journal.php` | Static pages and journal posts |

Rebuild after editing `catalog.py`:

```bash
QT_QPA_PLATFORM=offscreen ../../dashboard/venv/bin/python build_assets.py
cp site/* ../production_eshop_files/wp-content/themes/omega-storefront/assets/fernhill/img/
```

`scripts/seed_storefront_content.php` authors it into WordPress (production only;
mounted at `/eshop_seed` in the production seed container). It's version-gated — bump
`FH_CATALOG_VERSION` in that file to re-author an existing install, then
`docker compose run --rm production_db_seed`.

## The seed jobs

`scripts/seed_wordpress_db.sh` is run once per database by a one-shot
`wordpress:cli-php8.1` service — `production_db_seed` and `honeypot_db_seed_1/2/3`.
Each eshop `depends_on` its seed job with
`condition: service_completed_successfully`, so **no eshop can ever serve requests (or
be health-probed) against a schemaless database**.

The script:

- runs `wp core install`;
- activates the theme + WooCommerce + Elementor (deliberately **not** every installed
  plugin — activating Wordfence/etc. would work against the honeypot's purpose, and
  pre-auth plugin CVEs target the PHP file path regardless of "active" status);
- **production only**: imports WooCommerce's official sample catalog
  (`sample_products.xml`, ~18 products) and authors two Elementor pages (home + About
  Us) via `scripts/seed_elementor_pages.sh`.

It's **idempotent** (bails if already installed); pass `FORCE_RESEED=1` to wipe and
rebuild:

```bash
FORCE_RESEED=1 docker compose up production_db_seed && docker compose restart honeypot_content_sync
```

(Also available as the dashboard Backups page's "Reset demo store" button.)

!!! question "Why not a committed SQL dump / git-lfs binary?"
    GitHub's free LFS tier is only 1 GB storage / 1 GB bandwidth **per month**, total.
    A real WordPress file-archive backup is already 143–232 MB *per generation*, and a
    WooCommerce+Elementor DB dump adds more. A few KB of plain-text, `git diff`-able
    WP-CLI commands rebuild the same state deterministically from already-committed
    code, and need no regeneration when demo content changes.

## Replication to the pools

Honeypot pools need the same seed for a subtler reason:
`honeypot_content_sync`'s replication (`scripts/replicate_content_to_honeypot.sh`)
does a **scoped `DELETE`+`INSERT` into existing tables** — it mirrors content rows, it
never creates schema. Without the seed jobs first, every cycle would fail
(`Table '...wp_postmeta' doesn't exist`).

`honeypot_content_sync` therefore `depends_on` all four seed services completing, so
its first cycle has both a real source (production) and real destinations (all three
pools). It copies **posts, postmeta, terms and attachments** — *not* options,
comments, nav-menu items or term meta. So the storefront keeps to that: reviews live
in postmeta (`_fh_reviews`), navigation is built in code, and site/store settings come
from option filters in `wp-content/mu-plugins/fernhill-storefront.php`.

!!! warning "Pools never delete rows"
    After changing the catalog, clear a pool's old products first (or reseed), then
    restart `honeypot_content_sync` to mirror the new ones immediately.

Honeypot pools set `IMPORT_SAMPLE_CONTENT=0` (no independent sample import, no
Elementor authoring) — a pool is meant to have content **identical** to production,
mirrored by `honeypot_content_sync`. `WP_SITE_URL` is deliberately identical across
all four, matching `pool_router.lua`'s premise that a user sees the same public
fingerprint regardless of which pool they land on.

## Status is always visible

The triggering command's echoed progress streams live into whichever panel ran it
(the dashboard's Backups page, or your terminal), and the Health page's "Content sync
activity" panel parses `honeypot_content_sync`'s own per-pool `starting`/`complete`/
`failed` log lines — so a stuck or failing pool is visible immediately, not silently
assumed to have worked.
