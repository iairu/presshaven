"""Production firewall: the iptables ruleset of production_eshop's own network
namespace, edited by the Production Firewall page.

The container applies it itself (ids/images/wordpress_hardened/
production-firewall.php, run at start, re-applied when a peer's IP changes).
Only NEW connections are filtered -- loopback and established traffic always
pass -- so each rule names who may OPEN a connection: inbound, the edge to
Apache's port 80; outbound, PHP to the database, the internet on 443, ...
Everything else is dropped (inbound) or rejected (outbound).

The built-in rules come from the image's default ruleset
(production-firewall.default.json), so the dashboard and a container that was
never configured agree on them. patterns/production_firewall.json keeps only
the dashboard's deviations from those defaults (per-rule on/off and the master
switch) plus custom rules. "Apply" sends the full document to the container
with `docker compose exec production_eshop production-firewall apply`; the
container validates it with the same rules as validate_rule() below, enforces
it and saves it in its production_firewall_state volume."""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from core import honeypot_layer
from core.docker_ctl import Target
from core.paths import EDGE_DIR, REPO_ROOT
from core.proc import run_checked
from core.state import RemoteConfig

SETTINGS_PATH = REPO_ROOT / "patterns" / "production_firewall.json"
DEFAULT_RULESET_PATH = EDGE_DIR / "images" / "wordpress_hardened" / "production-firewall.default.json"
SETTINGS_FORMAT = "production-firewall-settings"
SETTINGS_VERSION = 1
DOCUMENT_VERSION = 1
SERVICE = "production_eshop"

DIRECTIONS = ("inbound", "outbound")
PROTOS = ("tcp", "udp", "tcp/udp")
PEER_KEYWORDS = ("any", "internet", "local-subnets")
LAYERS = ("default", "db-proxy")
MAX_RULES = 64
MAX_PORTS = 15
EDGE_PEER = "reverse_proxy"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
_CIDR_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?$")
_PORT_RE = re.compile(r"^(\d{1,5})(?:-(\d{1,5}))?$")


class FirewallError(Exception):
    pass


def active_layer() -> str:
    """The firewall's name for the dashboard's selected honeypot layer."""
    return "db-proxy" if honeypot_layer.is_database() else "default"


# -- validation (mirrors production-firewall.php validate()) -------------------

def is_cidr(text: str) -> bool:
    if not _CIDR_RE.match(text):
        return False
    try:
        ipaddress.IPv4Network(text, strict=False)
    except ValueError:
        return False
    return True


def parse_ports(text) -> list[tuple[int, int]]:
    """'80', '465,587', '8000-8100' -> [(lo, hi), ...]. Raises ValueError."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("ports are required")
    out, weight = [], 0
    for part in text.replace(" ", "").split(","):
        m = _PORT_RE.match(part)
        lo = int(m.group(1)) if m else 0
        hi = int(m.group(2) or lo) if m else 0
        if not m or lo < 1 or hi > 65535 or lo > hi:
            raise ValueError(f'bad port "{part}"')
        out.append((lo, hi))
        weight += 1 if lo == hi else 2
    if weight > MAX_PORTS:
        raise ValueError(f"at most {MAX_PORTS} ports per rule (a range counts as two)")
    return out


def normalise_ports(text: str) -> str:
    return ",".join(str(lo) if lo == hi else f"{lo}-{hi}" for lo, hi in parse_ports(text))


def validate_peer(peer, direction: str) -> None:
    # An address-shaped peer must be a valid address, never a "hostname".
    if not isinstance(peer, str) or not (peer in PEER_KEYWORDS or is_cidr(peer) or (
            _HOST_RE.match(peer) and not re.match(r"^[\d./]+$", peer))):
        raise ValueError("peer must be a container name, an IPv4 address/CIDR, any, local-subnets or internet")
    if peer == "internet" and direction == "inbound":
        raise ValueError("internet is outbound only (inbound traffic always comes through the edge)")


def validate_rule(rule: dict, direction: str) -> None:
    """Raises ValueError with the first problem of one document rule."""
    if not isinstance(rule.get("id"), str) or not _ID_RE.match(rule["id"]):
        raise ValueError("id must be 1-48 of a-z 0-9 -")
    if not isinstance(rule.get("enabled"), bool):
        raise ValueError("enabled must be true or false")
    validate_peer(rule.get("peer"), direction)
    if rule.get("proto") not in PROTOS:
        raise ValueError("proto must be tcp, udp or tcp/udp")
    parse_ports(rule.get("ports"))
    label = rule.get("label", "")
    if not isinstance(label, str) or len(label) > 200:
        raise ValueError("label must be text of at most 200 characters")
    if "layer" in rule and rule["layer"] not in LAYERS:
        raise ValueError("layer must be default or db-proxy")


def validate_document(doc) -> list[str]:
    if not isinstance(doc, dict):
        return ["ruleset must be a JSON object"]
    errors = []
    if doc.get("version") != DOCUMENT_VERSION:
        errors.append(f"version must be {DOCUMENT_VERSION}")
    if not isinstance(doc.get("enabled"), bool):
        errors.append("enabled must be true or false")
    for direction in DIRECTIONS:
        rules = doc.get(direction)
        if not isinstance(rules, list):
            errors.append(f"{direction} must be a list")
            continue
        if len(rules) > MAX_RULES:
            errors.append(f"{direction}: at most {MAX_RULES} rules")
        seen = set()
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                errors.append(f"{direction}[{i}]: must be an object")
                continue
            try:
                validate_rule(rule, direction)
            except ValueError as e:
                errors.append(f"{direction}[{i}]: {e}")
            if rule.get("id") in seen:
                errors.append(f"{direction}[{i}]: duplicate id {rule.get('id')}")
            seen.add(rule.get("id"))
    return errors


# -- rules and settings ---------------------------------------------------------

@dataclass
class FirewallRule:
    direction: str
    id: str
    enabled: bool
    peer: str
    proto: str
    ports: str
    label: str = ""
    layer: str | None = None
    custom: bool = False

    @property
    def key(self) -> str:
        return f"{self.direction}/{self.id}"

    def active_in(self, layer: str) -> bool:
        return self.enabled and (self.layer is None or self.layer == layer)

    def to_document(self) -> dict:
        out = {"id": self.id, "enabled": self.enabled, "peer": self.peer, "proto": self.proto,
               "ports": self.ports, "label": self.label}
        if self.layer:
            out["layer"] = self.layer
        return out


def load_default_ruleset(path: Path | str = DEFAULT_RULESET_PATH) -> dict:
    """The image's default ruleset. Raises FirewallError when it is missing or
    invalid -- it ships with the repo, so that is a broken checkout."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise FirewallError(f"Cannot read the default ruleset {path}: {e}")
    errors = validate_document(doc)
    if errors:
        raise FirewallError(f"The default ruleset {path} is invalid: {'; '.join(errors)}")
    return doc


def default_rules(path: Path | str = DEFAULT_RULESET_PATH) -> list[FirewallRule]:
    doc = load_default_ruleset(path)
    return [FirewallRule(direction, r["id"], r["enabled"], r["peer"], r["proto"], r["ports"],
                         r.get("label", ""), r.get("layer"))
            for direction in DIRECTIONS for r in doc[direction]]


@dataclass
class FirewallSettings:
    """``overrides`` maps a built-in rule key ("inbound/edge-http") to its
    enabled flag when it differs from the default; ``custom_rules`` are
    user-added rules (document fields plus "direction")."""

    enabled: bool = True
    overrides: dict[str, bool] = field(default_factory=dict)
    custom_rules: list[dict] = field(default_factory=list)
    path: Path = SETTINGS_PATH
    defaults_path: Path = DEFAULT_RULESET_PATH

    @classmethod
    def load(cls, path: Path | str = SETTINGS_PATH,
             defaults_path: Path | str = DEFAULT_RULESET_PATH) -> "FirewallSettings":
        """A missing or unparseable file gives the defaults, never an error."""
        settings = cls(path=Path(path), defaults_path=Path(defaults_path))
        try:
            raw = json.loads(settings.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return settings
        if not isinstance(raw, dict):
            return settings
        if isinstance(raw.get("enabled"), bool):
            settings.enabled = raw["enabled"]
        if isinstance(raw.get("overrides"), dict):
            settings.overrides = {str(k): bool(v) for k, v in raw["overrides"].items()}
        for rule in raw.get("custom") or []:
            try:
                settings.add_custom(rule["direction"], rule["peer"], rule["proto"], rule["ports"],
                                    rule.get("label", ""), enabled=bool(rule.get("enabled", True)))
            except (KeyError, TypeError, ValueError):
                continue
        return settings

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"format": SETTINGS_FORMAT, "version": SETTINGS_VERSION, "enabled": self.enabled,
                   "overrides": self.overrides, "custom": self.custom_rules}
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _defaults(self) -> list[FirewallRule]:
        return default_rules(self.defaults_path)

    def rules(self) -> list[FirewallRule]:
        out = []
        for r in self._defaults():
            r.enabled = self.overrides.get(r.key, r.enabled)
            out.append(r)
        for c in self.custom_rules:
            out.append(FirewallRule(c["direction"], c["id"], bool(c.get("enabled", True)), c["peer"],
                                    c["proto"], c["ports"], c.get("label", ""), custom=True))
        return out

    def set_enabled(self, key: str, enabled: bool) -> None:
        for c in self.custom_rules:
            if f"{c['direction']}/{c['id']}" == key:
                c["enabled"] = bool(enabled)
                return
        defaults = {r.key: r.enabled for r in self._defaults()}
        if key not in defaults:
            return
        if bool(enabled) == defaults[key]:
            self.overrides.pop(key, None)
        else:
            self.overrides[key] = bool(enabled)

    def add_custom(self, direction: str, peer: str, proto: str, ports: str, label: str = "",
                   enabled: bool = True) -> dict:
        """Validate and add a user rule. Raises ValueError on a bad field, a
        duplicate of an existing rule or a full direction."""
        if direction not in DIRECTIONS:
            raise ValueError(f"direction must be one of {', '.join(DIRECTIONS)}")
        peer = (peer or "").strip()
        validate_peer(peer, direction)
        if proto not in PROTOS:
            raise ValueError("proto must be tcp, udp or tcp/udp")
        ports = normalise_ports(ports)
        label = (label or "").strip()
        if len(label) > 200:
            raise ValueError("label must be at most 200 characters")
        existing = [r for r in self.rules() if r.direction == direction]
        for r in existing:
            if (r.peer, r.proto, normalise_ports(r.ports)) == (peer, proto, ports):
                raise ValueError(f"{direction} {peer} {proto} {ports} is already a rule ({r.id})")
        if len(existing) >= MAX_RULES:
            raise ValueError(f"at most {MAX_RULES} {direction} rules")
        taken = {r.id for r in existing}
        base = ("custom-" + re.sub(r"[^a-z0-9]+", "-", f"{peer}-{ports}".lower()).strip("-"))[:44].rstrip("-")
        rule_id, n = base, 2
        while rule_id in taken:
            rule_id, n = f"{base}-{n}", n + 1
        record = {"direction": direction, "id": rule_id, "enabled": bool(enabled), "peer": peer,
                  "proto": proto, "ports": ports, "label": label}
        self.custom_rules.append(record)
        return record

    def remove_custom(self, key: str) -> bool:
        before = len(self.custom_rules)
        self.custom_rules = [c for c in self.custom_rules if f"{c['direction']}/{c['id']}" != key]
        return len(self.custom_rules) != before

    def reset(self) -> None:
        """Back to the built-in defaults (master switch on); custom rules are kept."""
        self.enabled = True
        self.overrides = {}


# -- document -------------------------------------------------------------------

def build_document(settings: FirewallSettings) -> dict:
    """The ruleset document production-firewall expects. Disabled rules are
    included (they cost nothing and keep the page's rows stable)."""
    doc = {"version": DOCUMENT_VERSION, "enabled": settings.enabled, "inbound": [], "outbound": []}
    for r in settings.rules():
        doc[r.direction].append(r.to_document())
    return doc


def encode_document(doc: dict) -> str:
    return base64.b64encode(json.dumps(doc, ensure_ascii=False).encode("utf-8")).decode("ascii")


def fingerprint(doc: dict) -> str:
    """sha256 of the canonical JSON; production-firewall.php fingerprint()
    computes the same, so a status can say whether this is what it enforces."""
    canonical = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _covers(ports: str, port: int) -> bool:
    try:
        return any(lo <= port <= hi for lo, hi in parse_ports(ports))
    except ValueError:
        return False


def _reaches(rule: dict, peers: tuple[str, ...], port: int, layer: str) -> bool:
    return (rule["enabled"] and rule.get("layer", layer) == layer and rule["proto"] != "udp"
            and _covers(rule["ports"], port) and (rule["peer"] in peers or is_cidr(rule["peer"])))


def lockout_warnings(doc: dict, layer: str) -> list[str]:
    """What this ruleset would break, in plain words (empty = nothing obvious).
    A CIDR peer counts as reaching (the dashboard cannot know the subnet)."""
    if not doc["enabled"]:
        return ["The firewall is switched off: production accepts and opens connections to and from anything."]
    out = []
    if not any(_reaches(r, (EDGE_PEER, "any", "local-subnets"), 80, layer) for r in doc["inbound"]):
        out.append("No enabled inbound rule lets reverse_proxy open tcp/80: the edge cannot reach the shop "
                   "and every visitor gets a 502.")
    if not any(_reaches(r, ("production_database", "any", "local-subnets"), 3306, layer)
               for r in doc["outbound"]):
        out.append("No enabled outbound rule reaches production_database on tcp/3306: WordPress loses its "
                   "database.")
    if layer == "db-proxy" and not any(
            _reaches(r, ("local-subnets", "any"), 3306, layer) or r["peer"].startswith("honeypot_database")
            for r in doc["outbound"] if r["enabled"]):
        out.append("Database proxy layer: no enabled outbound rule reaches the honeypot pool databases, so "
                   "diverted sessions get a database error.")
    return out


# -- container ------------------------------------------------------------------

@dataclass
class FirewallStatus:
    """What `production-firewall status` reported."""
    source: str  # "saved" (applied from the dashboard) | "default" (never configured)
    layer: str
    hooked: bool | None  # None = could not read the live chains
    document: dict
    fingerprint: str
    enforced_fingerprint: str | None
    applied_at: str | None
    resolved: dict[str, list[str]]
    ipv6: bool | None
    counters: dict[str, dict[str, dict[str, int]]]

    @property
    def enforced(self) -> bool:
        """The chains are hooked and running the saved document."""
        return bool(self.hooked) and self.enforced_fingerprint == self.fingerprint

    def hits(self, direction: str, rule_id: str) -> int | None:
        entry = self.counters.get("in" if direction == "inbound" else "out", {}).get(rule_id)
        return entry.get("packets") if entry else None

    @classmethod
    def parse(cls, text: str) -> "FirewallStatus":
        try:
            raw = json.loads(text)
            return cls(
                source=raw["source"], layer=raw["layer"], hooked=raw["hooked"], document=raw["document"],
                fingerprint=raw["fingerprint"], enforced_fingerprint=raw.get("enforced_fingerprint"),
                applied_at=raw.get("applied_at"), resolved=dict(raw.get("resolved") or {}),
                ipv6=raw.get("ipv6"), counters={k: dict(v) for k, v in (raw.get("counters") or {}).items()},
            )
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise FirewallError(f"Unreadable status from production-firewall: {e}")


def _exec(remote: RemoteConfig | None, *args: str, timeout: float = 30.0) -> str:
    argv, cwd = Target(project="edge", remote=remote).build("exec", "-T", SERVICE, "production-firewall", *args)
    result = run_checked(argv, error=FirewallError, cwd=cwd, timeout=timeout, what="production-firewall")
    return result.stdout


def get_status(remote: RemoteConfig | None) -> FirewallStatus:
    try:
        return FirewallStatus.parse(_exec(remote, "status"))
    except FirewallError as e:
        if any(m in str(e) for m in ("executable file not found", "production-firewall: not found",
                                      "exited with code 127")):
            raise FirewallError("production_eshop runs an image without production-firewall: rebuild it "
                                "(docker compose build production_eshop && docker compose up -d production_eshop).")
        raise


def apply_document(remote: RemoteConfig | None, doc: dict) -> None:
    errors = validate_document(doc)
    if errors:
        raise FirewallError("Invalid ruleset: " + "; ".join(errors))
    _exec(remote, "apply", "--b64", encode_document(doc))
