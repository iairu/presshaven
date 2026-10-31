"""Edge URL policy: the legitimate-URL whitelist and the honeypot targets.

Two dashboard pages own what the reverse proxy does with a request's URL
before (and besides) scoring it:

* **URL Whitelist** -- every legitimate WordPress / WooCommerce endpoint of
  the shop, each one enabled or disabled. A request to a path that is not on
  the enabled whitelist earns the edge's ``unlisted_endpoint`` signal
  (``unlisted_score`` points). The whitelist only ever *adds* a signal for
  unknown paths: it never lowers a score or skips a check, so whitelisting a
  path cannot launder a payload past detection.

* **Honeypot Targets** -- the CVE patterns of the pattern registry (catalogue
  patterns of kind ``cve``) and the vulnerable plugin directories they live
  in. Enable/disable is the registry's own ``enabled`` flag (one switch,
  shared with the Pattern Database page and Attack Simulation). ``mode``
  picks what a hit does: ``direct`` diverts to a honeypot at once with
  scoring bypassed, ``score`` adds ``target_score`` and lets the threshold
  decide.

The dashboard-side settings live in ``patterns/edge_policy.json``; the edge
receives one JSON document in Redis (``honeypot_edge_policy``, see
``core.redis_inspect.set_edge_policy``), which init_worker.lua mirrors into a
shared dict every 5 s. The Lua side (lua/edge_policy_rules.lua) validates it
again and falls back to the pre-policy behaviour on anything unusable.

Qt-free, like the other ``core`` modules.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from core.paths import EDGE_DIR, REPO_ROOT

POLICY_PATH = REPO_ROOT / "patterns" / "edge_policy.json"
POLICY_FORMAT = "honeypot-ids-edge-policy"
POLICY_VERSION = 1

INIT_LUA = EDGE_DIR / "reverse_proxy_enhanced" / "lua" / "init.lua"
ESHOP_SEED_DIR = EDGE_DIR / "eshop_seed"

MODES = ("direct", "score")
MATCH_TYPES = ("exact", "prefix")
MAX_SCORE = 100
DEFAULT_MODE = "direct"
DEFAULT_TARGET_SCORE = 40
DEFAULT_UNLISTED_SCORE = 10
MAX_PATH_LENGTH = 512


@dataclass(frozen=True)
class WhitelistEntry:
    id: str
    path: str
    match: str          # "exact" | "prefix"
    label: str
    group: str
    enabled: bool = True
    custom: bool = False


# (id, path, match, label, group, enabled by default). Paths are what a
# shopper's browser legitimately requests on the production shop (WordPress
# core, WooCommerce, the seeded pages). Static assets never reach the
# whitelist check (the edge skips them before scoring), so asset trees are
# listed only for completeness of the inventory.
_BUILTIN: tuple[tuple[str, str, str, str, str, bool], ...] = (
    ("home", "/", "exact", "Front page (and ?s= search, ?p= links)", "WordPress core", True),
    ("wp-login", "/wp-login.php", "exact", "Login, lost password, logout", "WordPress core", True),
    ("wp-admin", "/wp-admin/", "prefix", "Admin area (incl. admin-ajax.php)", "WordPress core", True),
    ("wp-json", "/wp-json/", "prefix", "REST API (block editor, WooCommerce blocks)", "WordPress core", True),
    ("wp-cron", "/wp-cron.php", "exact", "WP-Cron loopback", "WordPress core", True),
    ("wp-comments-post", "/wp-comments-post.php", "exact", "Comment form submit", "WordPress core", True),
    ("xmlrpc", "/xmlrpc.php", "exact", "XML-RPC (unused by the shop; brute-force magnet)", "WordPress core", False),
    ("feed", "/feed/", "prefix", "RSS feed", "WordPress core", True),
    ("comments-feed", "/comments/feed/", "prefix", "Comments feed", "WordPress core", True),
    ("sitemap", "/wp-sitemap.xml", "exact", "Sitemap index", "WordPress core", True),
    ("sitemap-parts", "/wp-sitemap-", "prefix", "Sitemap parts", "WordPress core", True),
    ("robots", "/robots.txt", "exact", "robots.txt", "WordPress core", True),
    ("favicon", "/favicon.ico", "exact", "Favicon", "WordPress core", True),
    ("category", "/category/", "prefix", "Post category archives", "WordPress core", True),
    ("tag", "/tag/", "prefix", "Post tag archives", "WordPress core", True),
    ("author", "/author/", "prefix", "Author archives", "WordPress core", True),
    ("paged", "/page/", "prefix", "Paginated front page", "WordPress core", True),
    ("wp-includes", "/wp-includes/", "prefix", "Core scripts and styles", "Assets", True),
    ("uploads", "/wp-content/uploads/", "prefix", "Media library", "Assets", True),
    ("theme", "/wp-content/themes/omega-storefront/", "prefix", "Shop theme", "Assets", True),
    ("woocommerce-assets", "/wp-content/plugins/woocommerce/", "prefix", "WooCommerce assets", "Assets", True),
    ("shop", "/shop/", "prefix", "Shop catalogue", "WooCommerce", True),
    ("product", "/product/", "prefix", "Product pages", "WooCommerce", True),
    ("product-category", "/product-category/", "prefix", "Product categories", "WooCommerce", True),
    ("product-tag", "/product-tag/", "prefix", "Product tags", "WooCommerce", True),
    ("cart", "/cart/", "prefix", "Cart", "WooCommerce", True),
    ("checkout", "/checkout/", "prefix", "Checkout and order-received", "WooCommerce", True),
    ("my-account", "/my-account/", "prefix", "Customer account", "WooCommerce", True),
)


def _seeded_slugs() -> list[tuple[str, str]]:
    """(slug, group) of the pages and journal posts the shop is seeded with
    (ids/eshop_seed/pages.php, journal.php). Permalinks are /%postname%/,
    so each one is served at /<slug>/. Missing files just yield nothing."""
    out: list[tuple[str, str]] = []
    for name, group, pattern in (
        ("pages.php", "Shop pages", r"^\s*'([a-z0-9-]+)'\s*=>\s*\[\s*'title'"),
        ("journal.php", "Journal posts", r"'slug'\s*=>\s*'([a-z0-9-]+)'"),
    ):
        try:
            text = (ESHOP_SEED_DIR / name).read_text(encoding="utf-8")
        except OSError:
            continue
        for slug in re.findall(pattern, text, flags=re.MULTILINE):
            if slug != "home":  # the front page is "/"
                out.append((slug, group))
    return out


def default_whitelist() -> list[WhitelistEntry]:
    entries = [WhitelistEntry(i, p, m, label, group, enabled)
               for i, p, m, label, group, enabled in _BUILTIN]
    taken = {e.id for e in entries}
    for slug, group in _seeded_slugs():
        entry_id = f"page-{slug}"
        if entry_id not in taken:
            taken.add(entry_id)
            entries.append(WhitelistEntry(entry_id, f"/{slug}/", "prefix", slug, group))
    return entries


def normalise_path(raw: str) -> str:
    """What the edge compares against (mirrors edge_policy_rules.request_path
    for entries): lower-case, percent-decoded, no query/fragment, no repeated
    or dot segments, a trailing slash kept. Raises ValueError for a path the
    edge could never match."""
    path = (raw or "").strip()
    if not path.startswith("/"):
        raise ValueError("path must start with '/'")
    if len(path) > MAX_PATH_LENGTH:
        raise ValueError(f"path is longer than {MAX_PATH_LENGTH} characters")
    if any(c in path for c in "?#") or re.search(r"\s", path):
        raise ValueError("path must not contain a query string, fragment or whitespace")
    path = unquote(path).lower().replace("\\", "/")
    trailing = path.endswith("/")
    parts: list[str] = []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if not parts:
                raise ValueError("path climbs above the site root")
            parts.pop()
        else:
            parts.append(segment)
    out = "/" + "/".join(parts)
    if trailing and parts:
        out += "/"
    return out


@dataclass
class EdgePolicySettings:
    """The dashboard-owned settings. ``whitelist_overrides`` maps a built-in
    entry id to its enabled flag when it differs from the default;
    ``custom_entries`` are user-added paths."""

    mode: str = DEFAULT_MODE
    target_score: int = DEFAULT_TARGET_SCORE
    unlisted_score: int = DEFAULT_UNLISTED_SCORE
    whitelist_overrides: dict[str, bool] = field(default_factory=dict)
    custom_entries: list[dict] = field(default_factory=list)
    path: Path = POLICY_PATH

    # -- persistence -------------------------------------------------------
    @classmethod
    def load(cls, path: Path | str = POLICY_PATH) -> "EdgePolicySettings":
        """A missing or unparseable file gives the defaults, never an error."""
        path = Path(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(path=path)
        if not isinstance(raw, dict):
            return cls(path=path)
        targets = raw.get("targets") if isinstance(raw.get("targets"), dict) else {}
        whitelist = raw.get("whitelist") if isinstance(raw.get("whitelist"), dict) else {}
        settings = cls(path=path)
        if targets.get("mode") in MODES:
            settings.mode = targets["mode"]
        settings.target_score = _clamp(targets.get("target_score"), DEFAULT_TARGET_SCORE)
        settings.unlisted_score = _clamp(whitelist.get("unlisted_score"), DEFAULT_UNLISTED_SCORE)
        overrides = whitelist.get("overrides") or {}
        if isinstance(overrides, dict):
            settings.whitelist_overrides = {str(k): bool(v) for k, v in overrides.items()}
        for entry in whitelist.get("custom") or []:
            try:
                settings.add_custom(entry.get("path", ""), entry.get("match", "exact"),
                                    entry.get("label", ""), enabled=bool(entry.get("enabled", True)))
            except (AttributeError, ValueError):
                continue
        return settings

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": POLICY_FORMAT,
            "version": POLICY_VERSION,
            "targets": {"mode": self.mode, "target_score": self.target_score},
            "whitelist": {
                "unlisted_score": self.unlisted_score,
                "overrides": self.whitelist_overrides,
                "custom": self.custom_entries,
            },
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")

    # -- whitelist ---------------------------------------------------------
    def whitelist_entries(self) -> list[WhitelistEntry]:
        out = []
        for e in default_whitelist():
            enabled = self.whitelist_overrides.get(e.id, e.enabled)
            out.append(WhitelistEntry(e.id, e.path, e.match, e.label, e.group, enabled))
        for c in self.custom_entries:
            out.append(WhitelistEntry(c["id"], c["path"], c["match"], c.get("label") or c["path"],
                                      "Custom", bool(c.get("enabled", True)), custom=True))
        return out

    def set_whitelist_enabled(self, entry_id: str, enabled: bool) -> None:
        for c in self.custom_entries:
            if c["id"] == entry_id:
                c["enabled"] = bool(enabled)
                return
        defaults = {e.id: e.enabled for e in default_whitelist()}
        if entry_id not in defaults:
            return
        if bool(enabled) == defaults[entry_id]:
            self.whitelist_overrides.pop(entry_id, None)
        else:
            self.whitelist_overrides[entry_id] = bool(enabled)

    def add_custom(self, path: str, match: str = "exact", label: str = "",
                   enabled: bool = True) -> dict:
        """Validate and add a user path. Raises ValueError on a bad path or a
        duplicate of an existing entry."""
        if match not in MATCH_TYPES:
            raise ValueError(f"match must be one of {', '.join(MATCH_TYPES)}")
        normalised = normalise_path(path)
        for e in self.whitelist_entries():
            if e.path == normalised and e.match == match:
                raise ValueError(f"{normalised} ({match}) is already on the whitelist")
        taken = {e.id for e in self.whitelist_entries()}
        base = "custom-" + (re.sub(r"[^a-z0-9]+", "-", normalised).strip("-") or "root")
        entry_id, n = base, 2
        while entry_id in taken:
            entry_id, n = f"{base}-{n}", n + 1
        record = {"id": entry_id, "path": normalised, "match": match,
                  "label": (label or "").strip(), "enabled": bool(enabled)}
        self.custom_entries.append(record)
        return record

    def remove_custom(self, entry_id: str) -> bool:
        before = len(self.custom_entries)
        self.custom_entries = [c for c in self.custom_entries if c["id"] != entry_id]
        return len(self.custom_entries) != before

    def reset_whitelist(self) -> None:
        """Back to the built-in defaults; custom entries are kept."""
        self.whitelist_overrides = {}


def _clamp(value, default: int) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(0, min(MAX_SCORE, n))


# ---------------------------------------------------------------------------
# honeypot targets
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class HoneypotTarget:
    pattern_id: str
    cve: str
    name: str
    severity: str
    plugin_dir: str        # vulnerable plugin directory on the honeypots, "" if none
    trigger: str
    trigger_type: str
    sample_request: str    # "METHOD path" of the Attack Simulation preset
    enabled: bool
    edge_enforced: bool    # has a cve_patterns entry the edge matches on


def plugin_dirs_by_cve(init_lua: Path = INIT_LUA) -> dict[str, str]:
    """CVE id -> vulnerable plugin directory, read from the comments on
    init.lua's vulnerability.plugins list (``"bricks", -- CVE-2024-25600``).
    These are the directory names the edge matches in
    /wp-content/plugins/<dir>/, which can differ from the catalogue's plugin
    slug (abandoned-cart-lite vs woocommerce-abandoned-cart)."""
    try:
        text = init_lua.read_text(encoding="utf-8")
    except OSError:
        return {}
    block = re.search(r"\bplugins\s*=\s*\{(.*?)\}", text, flags=re.DOTALL)
    if not block:
        return {}
    out: dict[str, str] = {}
    for line in block.group(1).splitlines():
        m = re.match(r'\s*"([^"]+)"\s*,?\s*--\s*(.*)$', line)
        if m:
            for cve in re.findall(r"CVE-\d{4}-\d+", m.group(2)):
                out[cve] = m.group(1)
    return out


def edge_cve_ids(init_lua: Path = INIT_LUA) -> set[str]:
    """CVE ids with a cve_patterns entry in init.lua."""
    try:
        text = init_lua.read_text(encoding="utf-8")
    except OSError:
        return set()
    block = re.search(r"\bcve_patterns\s*=\s*\{(.*?)\n\s*\}", text, flags=re.DOTALL)
    return set(re.findall(r'\["(CVE-\d{4}-\d+)"\]', block.group(1))) if block else set()


def honeypot_targets(catalog=None, init_lua: Path = INIT_LUA) -> list[HoneypotTarget]:
    """Every CVE pattern of the effective catalogue (registry applied), in
    catalogue order."""
    if catalog is None:
        from core.pattern_registry import load_catalog
        catalog = load_catalog()
    dirs = plugin_dirs_by_cve(init_lua)
    enforced = edge_cve_ids(init_lua)
    out = []
    for p in catalog.patterns:
        if p.get("kind") != "cve" or not p.get("cve"):
            continue
        preset = p.get("preset") or {}
        sample = f"{preset.get('method', 'GET')} {preset['path']}" if preset.get("path") else ""
        out.append(HoneypotTarget(
            pattern_id=p["id"], cve=p["cve"], name=p.get("name", p["cve"]),
            severity=p.get("severity", ""), plugin_dir=dirs.get(p["cve"], ""),
            trigger=p.get("trigger", ""), trigger_type=p.get("trigger_type", ""),
            sample_request=sample, enabled=bool(p.get("enabled", True)),
            edge_enforced=p["cve"] in enforced,
        ))
    return out


def disabled_plugin_dirs(targets: list[HoneypotTarget], init_lua: Path = INIT_LUA) -> list[str]:
    """Plugin directories whose CVE targets are ALL disabled. A directory
    that hosts two CVEs (gift-voucher) stays a target while either is on."""
    enabled_by_cve = {t.cve: t.enabled for t in targets}
    by_dir: dict[str, list[bool]] = {}
    for cve, plugin_dir in plugin_dirs_by_cve(init_lua).items():
        by_dir.setdefault(plugin_dir, []).append(enabled_by_cve.get(cve, True))
    return sorted(d for d, flags in by_dir.items() if not any(flags))


# ---------------------------------------------------------------------------
# the document the edge reads
# ---------------------------------------------------------------------------
def build_payload(settings: EdgePolicySettings, targets: list[HoneypotTarget] | None = None,
                  init_lua: Path = INIT_LUA) -> dict:
    if targets is None:
        targets = honeypot_targets(init_lua=init_lua)
    return {
        "version": POLICY_VERSION,
        "targets": {
            "mode": settings.mode,
            "target_score": settings.target_score,
            "disabled_cves": sorted(t.cve for t in targets if not t.enabled),
            "disabled_plugins": disabled_plugin_dirs(targets, init_lua),
        },
        "whitelist": {
            "unlisted_score": settings.unlisted_score,
            "entries": [{"id": e.id, "match": e.match, "path": e.path}
                        for e in settings.whitelist_entries() if e.enabled],
        },
    }


def encode_payload(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)
