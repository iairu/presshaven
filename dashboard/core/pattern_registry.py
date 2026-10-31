"""Pattern-plugin registry: the user-editable overlay on the catalogue.

``patterns/patterns.json`` is *generated* from the Lua rules, the Suricata
rules and the Attack Simulation presets and must not be hand-edited (see
``patterns/README.md``).  The registry is the one *mutable* layer the
dashboard owns on top of it:

* which catalogue patterns are **enabled** (default: the catalogue's own
  ``enabled`` flag -- generic attacks and detection signals on, CVE patterns
  off; see ``core.patterns.DEFAULT_DISABLED_KINDS``),
* **field edits** the user has made to a generated pattern (name, severity,
  description, ...), kept as a small override rather than touching the
  generated file, and
* brand-new **custom** patterns that have no generator source yet.

It is a small, stable JSON file (``patterns/registry.json``) keyed on the
catalogue's stable ``id``, so the same enable/disable decisions can later be
read by the reverse-proxy and Suricata rule exporters -- the whole point of
"patterns as plugins".  The module is deliberately Qt-free: the UI only calls
these methods and renders the resulting dictionaries.
"""
from __future__ import annotations

import dataclasses
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from core.pattern_catalog import PatternCatalog
from core.patterns import default_enabled
from core.paths import REPO_ROOT

REGISTRY_PATH = REPO_ROOT / "patterns" / "registry.json"
REGISTRY_FORMAT = "honeypot-ids-pattern-registry"
REGISTRY_VERSION = 1

# Fields a user may edit on a generated pattern through the UI. Everything
# else (sources, signatures, suricata, detection path, ...) comes from the
# generator and is read-only in the dashboard.
EDITABLE_FIELDS = (
    "name", "category", "category_label", "severity", "kind", "kind_label",
    "component", "surface", "description", "trigger", "notes", "enabled",
)

_SEVERITIES = ("critical", "high", "medium", "low", "info")


def slugify(text: str) -> str:
    """A stable, lower-kebab id fragment for a user-supplied name."""
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return slug or "pattern"


@dataclass
class PatternRegistry:
    """The mutable overlay. ``overrides`` maps a catalogue id to the subset of
    fields the user changed on that generated pattern (``enabled`` included);
    ``custom`` holds full records for patterns the user authored here."""

    overrides: dict[str, dict] = field(default_factory=dict)
    custom: list[dict] = field(default_factory=list)
    path: Path = REGISTRY_PATH

    # -- persistence -------------------------------------------------------
    @classmethod
    def load(cls, path: Path | str = REGISTRY_PATH) -> "PatternRegistry":
        """Read the registry; a missing or unparseable file is an empty
        registry (catalogue defaults, nothing custom), never an error --
        the dashboard must open even if someone deletes the file."""
        path = Path(path)
        if not path.exists():
            return cls(path=path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls(path=path)
        if not isinstance(raw, dict):
            return cls(path=path)
        overrides = raw.get("overrides") or {}
        custom = raw.get("custom") or []
        return cls(
            overrides={k: dict(v) for k, v in overrides.items() if isinstance(v, dict)},
            custom=[dict(c) for c in custom if isinstance(c, dict) and c.get("id")],
            path=path,
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": REGISTRY_FORMAT,
            "version": REGISTRY_VERSION,
            "overrides": self.overrides,
            "custom": self.custom,
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")

    # -- lookups -----------------------------------------------------------
    def _custom_index(self, pattern_id: str) -> int:
        for i, record in enumerate(self.custom):
            if record.get("id") == pattern_id:
                return i
        return -1

    def is_custom(self, pattern_id: str) -> bool:
        return self._custom_index(pattern_id) >= 0

    def is_edited(self, pattern_id: str) -> bool:
        return bool(self.overrides.get(pattern_id))

    def is_enabled(self, pattern_id: str, default: bool = True) -> bool:
        idx = self._custom_index(pattern_id)
        if idx >= 0:
            return bool(self.custom[idx].get("enabled", True))
        return bool(self.overrides.get(pattern_id, {}).get("enabled", default))

    # -- enable / disable --------------------------------------------------
    def set_enabled(self, pattern_id: str, enabled: bool, default: bool = True) -> None:
        """``default`` is the pattern's catalogue state (``default_enabled``
        of the merged record): the override only records a deviation from it."""
        idx = self._custom_index(pattern_id)
        if idx >= 0:
            self.custom[idx]["enabled"] = bool(enabled)
            return
        if bool(enabled) == bool(default):
            # Back to the catalogue default: drop the key, and the whole
            # override entry when nothing else is left, so the file only ever
            # records real deviations.
            self._drop_enabled(pattern_id)
        else:
            self.overrides.setdefault(pattern_id, {})["enabled"] = bool(enabled)

    def set_many_enabled(self, pattern_ids, enabled: bool,
                         defaults: dict[str, bool] | None = None) -> None:
        defaults = defaults or {}
        for pattern_id in pattern_ids:
            self.set_enabled(pattern_id, enabled, defaults.get(pattern_id, True))

    def reset_enabled(self, pattern_ids=None) -> None:
        """Return generated patterns (all, or ``pattern_ids``) to their
        catalogue enabled state. Custom patterns have no default and keep
        theirs."""
        for pattern_id in list(self.overrides if pattern_ids is None else pattern_ids):
            self._drop_enabled(pattern_id)

    def _drop_enabled(self, pattern_id: str) -> None:
        entry = self.overrides.get(pattern_id)
        if entry is not None:
            entry.pop("enabled", None)
            if not entry:
                self.overrides.pop(pattern_id, None)

    # -- edit --------------------------------------------------------------
    def override(self, pattern_id: str, fields: dict) -> None:
        """Merge edited fields onto a generated pattern. Editing a *custom*
        pattern updates its record directly instead."""
        clean = {k: v for k, v in fields.items() if k in EDITABLE_FIELDS}
        idx = self._custom_index(pattern_id)
        if idx >= 0:
            self.custom[idx].update(clean)
            return
        entry = self.overrides.setdefault(pattern_id, {})
        entry.update(clean)
        if not entry:
            self.overrides.pop(pattern_id, None)

    def clear_override(self, pattern_id: str) -> None:
        """Revert a generated pattern to its catalogue values (no-op for a
        custom pattern -- there is nothing to revert to)."""
        self.overrides.pop(pattern_id, None)

    # -- custom patterns ---------------------------------------------------
    def add_custom(self, record: dict) -> dict:
        record = normalise_custom(record, existing_ids=self.all_ids())
        self.custom.append(record)
        return record

    def update_custom(self, record: dict) -> None:
        idx = self._custom_index(record.get("id", ""))
        if idx >= 0:
            self.custom[idx] = {**self.custom[idx], **record}

    def remove(self, pattern_id: str) -> bool:
        """Delete a custom pattern, or drop the overrides on a generated one
        (which then returns to its catalogue form). Returns True if anything
        changed."""
        idx = self._custom_index(pattern_id)
        if idx >= 0:
            self.custom.pop(idx)
            return True
        if pattern_id in self.overrides:
            self.overrides.pop(pattern_id, None)
            return True
        return False

    def all_ids(self) -> set[str]:
        return {c.get("id", "") for c in self.custom} | set(self.overrides)

    # -- merged view -------------------------------------------------------
    def apply(self, base_patterns: list[dict]) -> list[dict]:
        """The effective pattern list: every generated pattern with its
        override merged in, followed by the custom patterns, in a stable
        order. Records are copies -- callers never mutate the catalogue."""
        out: list[dict] = []
        for pattern in base_patterns:
            merged = dict(pattern)
            merged.setdefault("enabled", default_enabled(pattern.get("kind", "")))
            merged["default_enabled"] = merged["enabled"]
            override = self.overrides.get(pattern.get("id", ""))
            if override:
                merged.update({k: v for k, v in override.items() if k in EDITABLE_FIELDS})
            out.append(merged)
        for record in self.custom:
            out.append({**record, "default_enabled": bool(record.get("enabled", True))})
        return out


def normalise_custom(record: dict, existing_ids: set[str] | None = None) -> dict:
    """Fill a user-authored pattern out to the catalogue shape so the rest of
    the app (table, detail panel, export, search) treats it like any other
    entry. Guarantees a unique, slug id and the fields every consumer reads."""
    existing_ids = existing_ids or set()
    pattern_id = (record.get("id") or "").strip()
    if not pattern_id:
        base = slugify(record.get("name", "pattern"))
        pattern_id = base
        n = 2
        while pattern_id in existing_ids:
            pattern_id = f"{base}-{n}"
            n += 1
    kind = record.get("kind") or "generic"
    category = record.get("category") or "custom"
    severity = (record.get("severity") or "medium").lower()
    if severity not in _SEVERITIES:
        severity = "medium"
    out = {
        "id": pattern_id,
        "aliases": list(record.get("aliases", [])),
        "name": (record.get("name") or pattern_id).strip(),
        "kind": kind,
        "kind_label": record.get("kind_label") or kind.replace("-", " ").title(),
        "category": category,
        "category_label": record.get("category_label") or category.replace("-", " ").title(),
        "severity": severity,
        "component": record.get("component") or "custom",
        "plugin": record.get("plugin", ""),
        "surface": record.get("surface") or "backend",
        "description": (record.get("description") or "").strip(),
        "trigger": record.get("trigger", ""),
        "trigger_type": record.get("trigger_type", ""),
        "score": record.get("score"),
        "score_note": record.get("score_note", ""),
        "wstg": list(record.get("wstg", [])),
        "owasp": record.get("owasp", ""),
        "mitre": record.get("mitre", ""),
        "cve": record.get("cve", ""),
        "attack_vector": record.get("attack_vector", ""),
        "detection": list(record.get("detection", [])),
        "sources": record.get("sources") or [{
            "key": "custom", "label": "Custom pattern",
            "module": "patterns/registry.json",
            "detail": "User-authored via the Pattern Database page.",
        }],
        "signatures": list(record.get("signatures", [])),
        "suricata": list(record.get("suricata", [])),
        "preset": record.get("preset"),
        "lesson": record.get("lesson"),
        "reportable": bool(record.get("reportable", True)),
        "enabled": bool(record.get("enabled", True)),
        "tags": list(record.get("tags", [])),
        "notes": record.get("notes", ""),
    }
    return out


# ---------------------------------------------------------------------------
# effective catalogue + preset filtering (what the rest of the dashboard reads)
# ---------------------------------------------------------------------------
def load_catalog(registry: PatternRegistry | None = None,
                 base: PatternCatalog | None = None) -> PatternCatalog:
    """The catalogue the UI actually shows: the generated catalogue with the
    registry's overrides and custom patterns folded in. ``sources``/``kinds``/
    ``categories`` label maps are kept from the base; ``by_id``/``counts`` are
    recomputed so a disabled or custom pattern is reflected everywhere."""
    base = base or PatternCatalog.load()
    registry = registry if registry is not None else PatternRegistry.load()
    patterns = registry.apply(base.patterns)
    sources = dict(base.sources)
    sources.setdefault("custom", {
        "label": "Custom pattern", "module": "patterns/registry.json",
        "detail": "User-authored via the Pattern Database page.",
    })
    kinds = dict(base.kinds)
    categories = dict(base.categories)
    for pattern in patterns:
        kinds.setdefault(pattern.get("kind", ""), pattern.get("kind_label", ""))
        categories.setdefault(pattern.get("category", ""), pattern.get("category_label", ""))
    counts = {
        "total": len(patterns),
        "cves": sum(1 for p in patterns if p.get("kind") == "cve"),
        "suricata_sids": len({r["sid"] for p in patterns for r in p.get("suricata", [])}),
        "enabled": sum(1 for p in patterns if p.get("enabled", True)),
        "disabled": sum(1 for p in patterns if not p.get("enabled", True)),
        "custom": len(registry.custom),
    }
    return dataclasses.replace(
        base,
        patterns=patterns,
        by_id={p["id"]: p for p in patterns},
        sources=sources,
        kinds={k: v for k, v in kinds.items() if k},
        categories={k: v for k, v in categories.items() if k},
        counts=counts,
    )


def disabled_preset_cves(registry: PatternRegistry | None = None,
                         catalog: PatternCatalog | None = None) -> set[str]:
    """CVE ids whose catalogue pattern the user has disabled. The Attack
    Simulation and Segmentation Validation pages drop these presets so a
    pattern switched off in the database is switched off everywhere it runs."""
    catalog = catalog or load_catalog(registry)
    return {p.get("cve") for p in catalog.patterns
            if p.get("cve") and not p.get("enabled", True)}


def active_presets(presets=None, registry: PatternRegistry | None = None,
                   catalog: PatternCatalog | None = None):
    """``presets`` (default: the full Attack Simulation battery) minus every
    preset whose catalogue pattern is disabled. A preset with no catalogue
    counterpart is always kept -- disabling only ever removes, never adds."""
    if presets is None:
        from core.patterns import PATTERN_PRESETS
        presets = PATTERN_PRESETS
    disabled = disabled_preset_cves(registry, catalog)
    return [p for p in presets if getattr(p, "cve", "") not in disabled]
