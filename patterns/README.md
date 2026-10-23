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

The `enabled` field is already present and defaults to `true`, but the UI
controls that would change it are deliberately disabled scaffolding until the
pattern-plugin registry exists. Export and copy actions are functional today.
