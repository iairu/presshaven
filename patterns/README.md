# Pattern catalogue

`patterns.json` is the single, generated list of everything the edge stack can
detect. Both front ends read it:

- the PyQt **Pattern Database** page (`dashboard/ui/page_pattern_database.py`),
- the Astro docs page at `/docs/detection/patterns`.

Do not edit `patterns.json` by hand. Change a rule source or the generator, then
run:

```bash
python3 tools/generate_pattern_catalog.py
```

`--check` compares the checked-in file with what the sources would generate and
exits non-zero when it is stale (the generation date is ignored):

```bash
python3 tools/generate_pattern_catalog.py --check
```

## Sources

The generator reads:

| Source | What it contributes |
| --- | --- |
| `ids/reverse_proxy_enhanced/lua/pattern_rules.lua` | Layer 1/2 generic signatures, header rules, upload rules, automation/method heuristics |
| `ids/reverse_proxy_enhanced/lua/init.lua` | CVE patterns |
| `ids/reverse_proxy_enhanced/lua/vulnerability_rules.lua` | Narrower plugin-path CVE checks |
| `ids/reverse_proxy_enhanced/lua/upload_rules.lua` | Upload-specific rules |
| `ids/suricata_rules/local.rules` | SIDs, messages, classes, WSTG comments |
| `dashboard/core/patterns.py` | Attack Simulation presets |
| `dashboard/core/learning.py` | CVE lessons (attack class, OWASP, ATT&CK, defence) |

Patterns that describe the same concept in different layers are merged into one
record. The record keeps every source, signature, Suricata SID and preset that
contributed to it, so the detail panel can show the whole detection path.

## Stable IDs

The `id` is the future plugin key: deep links (`?pattern=<id>`), exports,
enable/disable controls and edit operations all use it. Treat IDs as stable;
add `aliases` (for example a CVE ID or a Suricata SID) instead of renaming an
existing record.

## Schema

Each entry has:

- identity: `id`, `name`, `aliases`, `kind`, `kind_label`, `category`,
  `category_label`, `severity`, `component`, `plugin`, `surface`
- explanation: `description`, `trigger`, `trigger_type`, `score`,
  `score_note`, `detection`, `notes`
- mappings: `wstg`, `owasp`, `mitre`, `cve`, `attack_vector`, `tags`
- evidence: `sources`, `signatures`, `suricata`, `preset`, `lesson`
- state: `reportable`, `enabled`

Top-level keys are `version`, `generated`, `source_files`, `sources`, `kinds`,
`categories`, `counts` and `patterns`.

## Registry (the mutable overlay)

`patterns.json` is generated and read-only. The *mutable* layer lives beside it
in `patterns/registry.json`, owned by `dashboard/core/pattern_registry.py`:

- **overrides** — per-id field changes on a generated pattern (`enabled`
  included), so disabling or editing a pattern never touches the generated
  file. Enabling a pattern again prunes the override, so the file only records
  real deviations.
- **custom** — full records for patterns the user authored in the Pattern
  Database page (`kind`/`category`/`severity`/… filled out to the catalogue
  shape by `normalise_custom`).

`load_catalog(registry)` returns the generated catalogue with the registry
folded in; that merged catalogue is what the dashboard shows. The Pattern
Database page is the editor: a per-row checkbox enables/disables, and
per-pattern and bulk actions add, edit, duplicate, remove, revert and export.

A pattern switched **off** here is dropped from the Attack Simulation battery
and the Segmentation Validation preset list (`active_presets()` /
`disabled_preset_cves()`), so "off in the database" means off everywhere it
runs. For the **CVE patterns** the same switch also reaches the live edge,
through the edge policy below; the Suricata exporter does not read it yet.

A missing or corrupt `registry.json` loads as an empty registry (every pattern
enabled, nothing custom): deleting the file is a clean reset.

## Edge policy (URL whitelist + honeypot targets)

Two dashboard pages decide what the reverse proxy does with a request's URL.
Their settings live in `patterns/edge_policy.json`, owned by
`dashboard/core/edge_policy.py`:

- **URL Whitelist**: every legitimate WordPress / WooCommerce path of the
  shop (`exact` or `prefix` match), each one enabled or disabled, plus custom
  paths. The defaults are WordPress core, WooCommerce, the asset trees and
  the seeded pages and journal posts (`ids/eshop_seed/pages.php`,
  `journal.php`). `/xmlrpc.php` is off by default. A request whose path is
  not on the enabled whitelist gets the `unlisted_endpoint` signal, worth
  `unlisted_score` points (dashboard default 10, 0 = inventory only).
  The whitelist only ever **adds** evidence. It never lowers a score or
  skips a check, so a payload on a whitelisted path is still caught.
- **Honeypot Targets**: every `cve` pattern of the catalogue, with the
  vulnerable plugin directory it ships in. That directory comes from the
  comments on `vulnerability.plugins` in `init.lua`, because it can differ
  from the catalogue's plugin slug. The row checkbox is the registry's
  `enabled` flag, the same switch as the Pattern Database page. A plugin
  directory stops being a target once all of its CVEs are disabled. `mode`
  sets what a target hit does:
  - `direct` (auto-send) diverts to a honeypot at once, with scoring
    bypassed.
  - `score` adds `target_score` per CVE match and per plugin-path hit, and
    the honeypot threshold decides.

**Apply to edge** (on either page) SETs a single JSON document in the edge's
Redis under `honeypot_edge_policy`, with no TTL:

```json
{"version": 1,
 "targets": {"mode": "direct", "target_score": 40,
             "disabled_cves": ["CVE-2024-25600"], "disabled_plugins": ["bricks"]},
 "whitelist": {"unlisted_score": 10,
               "entries": [{"id": "shop", "match": "prefix", "path": "/shop/"}]}}
```

From there, the edge picks the policy up like this:

1. `init_worker.lua` mirrors the key into the `threat_intel` shared dict
   every 5 s.
2. `lua/edge_policy.lua` decodes it once per worker per change.
3. `lua/edge_policy_rules.lua` validates it.
4. `router.lua` Stage 1c applies the target mode, and `pattern_analyzer.lua`
   adds the score-mode and whitelist signals.

No restart is needed. If the key is missing or can't be used, the edge falls
back to the pre-policy behaviour: every target enabled, direct diversion and
no whitelist signal. "Flush threat state" keeps the key, but a full Redis
FLUSHALL deletes it. Use **Check edge** on either page to see whether the
edge is running the saved policy.
