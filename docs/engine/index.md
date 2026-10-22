# Honeypot Engine

The honeypot is a **complete, high-interaction WordPress/WooCommerce site** — not a
banner. This section covers the application layer, how attackers are isolated into
elastic pools, how the demo store is seeded, how backups work, and the Redis/shared
state behind it all.

<div class="grid cards" markdown>

-   :material-wordpress:{ .lg .middle } **[WordPress / WooCommerce Layer](wordpress.md)**

    ---

    The real shop: theme, plugin roster, hardening on production vs. deliberate
    exploitability on the pools.

-   :material-layers-triple:{ .lg .middle } **[Honeypot Layers](layers.md)**

    ---

    WordPress proxy level vs. database proxy level — what each can and can't contain.

-   :material-arrow-expand-all:{ .lg .middle } **[Pool Scaling & Assignment](pooling.md)**

    ---

    Per-IP sticky pools, template-clone scaling in ~MySQL start time, hand-off to
    waiting sessions, resource caps and scale-down.

-   :material-sprout:{ .lg .middle } **[Seeding the Storefront](seeding.md)**

    ---

    The Fernhill Coffee Roasters demo store, the one-shot seed jobs, and why it's
    WP-CLI scripts not a committed SQL dump.

-   :material-backup-restore:{ .lg .middle } **[Backups](backups.md)**

    ---

    `backup_service`'s nightly dumps and the label/delete/export/import lifecycle.

-   :material-database:{ .lg .middle } **[State — Redis & ngx.shared](state.md)**

    ---

    The two key-value stores, the full key schema, and the subtle bugs tracing it
    surfaced.

</div>

## The core promise

Once an attacker's IP is flagged, [`pool_router`](pooling.md) pins it to **its own**
honeypot pool — a dedicated WordPress container plus its own database — for 24 hours.
That gives the attacker a **consistent, stateful, isolated** fake world: their cart,
uploaded webshells and other artifacts persist, and they can never see or damage
another attacker's environment or the real shop.
