"""Container firewall: the iptables rulesets of the WordPress containers'
network namespaces, edited by the Container Firewall page.

Each WordPress container lives in the network namespace of a small firewall
container (production_eshop -> production_eshop_net, honeypot_eshop_N ->
honeypot_eshop_N_net, runtime pools likewise) that holds the rules and applies
them (ids/images/container_firewall/container-firewall.php, re-checked every
5 s). WordPress itself has no NET_ADMIN and cannot see or change them, so even
root inside a compromised container cannot open its own way out.

Three profiles, one ruleset each:
  production        -- production_eshop: the edge in, the database and the
                       public internet on 443 out
  honeypot          -- every honeypot pool: the edge in (the attacker's way
                       in), the pool's own database out, nothing else -- no
                       internet, no production, no host, no other pool
                       (honeypot_network is also an internal network: no
                       route off the host at all)
  honeypot_database -- every honeypot database (honeypot_database_N, the
                       db-proxy layer's honeypot_database): MySQL in from
                       honeypot_network, nothing out

The two honeypot profiles are LOCKED (LOCKED_OUTBOUND, enforced again by the
firewall itself): attackers get into those containers, so their firewall
cannot be switched off and they can never be given an outbound peer past the
pool's own database. Every firewall also drops all forwarded packets, so no
namespace on two networks can be used as a router between them.

Only NEW connections are filtered -- loopback and established traffic always
pass -- so each rule names who may OPEN a connection. Everything else is
dropped (inbound) or rejected (outbound).

The built-in rules come from the image's default ruleset per profile
(images/container_firewall/<profile>.json), so the dashboard and a firewall
that was never configured agree on them. patterns/container_firewall_<profile>
.json keeps only the dashboard's deviations from those defaults (per-rule
on/off and the master switch) plus custom rules. "Apply" sends the full
document to one of the profile's firewalls with `docker compose exec <fw>
container-firewall apply`; it validates it with the same rules as
validate_rule() below, enforces it and saves it in the container_firewall_rules
volume, where the profile's other firewalls (the other pools) pick it up."""
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

IMAGE_DIR = EDGE_DIR / "images" / "container_firewall"
TOOL = "container-firewall"
SETTINGS_FORMAT = "container-firewall-settings"
SETTINGS_VERSION = 1
DOCUMENT_VERSION = 1

DIRECTIONS = ("inbound", "outbound")
PROTOS = ("tcp", "udp", "tcp/udp")
PEER_KEYWORDS = ("any", "internet", "local-subnets", "db-host")
LAYERS = ("default", "db-proxy")
MAX_RULES = 64
MAX_PORTS = 15
EDGE_PEER = "reverse_proxy"
# Locked profiles => the outbound peers (tcp only) they may have; mirrors
# LOCKED_OUTBOUND in container-firewall.php.
LOCKED_OUTBOUND = {"honeypot": ("db-host",), "honeypot_database": ()}


@dataclass(frozen=True)
class Profile:
    name: str
    title: str
    service: str        # the firewall the dashboard execs into
    protects: str       # what it protects, for messages
    layers: tuple[str, ...]  # honeypot layers in which its containers exist
    db_proxy_service: str | None = None  # the firewall to exec into in the db-proxy layer, if other

    def service_for(self, layer: str) -> str:
        return self.db_proxy_service if layer == "db-proxy" and self.db_proxy_service else self.service

    @property
    def locked(self) -> bool:
        return self.name in LOCKED_OUTBOUND

    @property
    def settings_path(self) -> Path:
        return REPO_ROOT / "patterns" / f"container_firewall_{self.name}.json"

    @property
    def defaults_path(self) -> Path:
        return IMAGE_DIR / f"{self.name}.json"


PRODUCTION = Profile("production", "Production", "production_eshop_net", "production_eshop", LAYERS)
# Applied through pool 1's firewall; pools 2-3 and the runtime pools read the
# same saved file within 5 s. The database proxy layer has no pool WordPress
# containers (production_eshop serves the honeypot databases itself).
HONEYPOT = Profile("honeypot", "Honeypot pools", "honeypot_eshop_1_net", "every honeypot pool", ("default",))
# Applied through pool 1's database firewall (default layer) or the single
# honeypot database's (db-proxy layer); the others follow within 5 s.
HONEYPOT_DATABASE = Profile("honeypot_database", "Honeypot databases", "honeypot_database_1_net",
                            "every honeypot database", LAYERS, db_proxy_service="honeypot_database_net")
PROFILES = {p.name: p for p in (PRODUCTION, HONEYPOT, HONEYPOT_DATABASE)}

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
_CIDR_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?$")
_PORT_RE = re.compile(r"^(\d{1,5})(?:-(\d{1,5}))?$")


class FirewallError(Exception):
    pass


def active_layer() -> str:
    """The firewall's name for the dashboard's selected honeypot layer."""
    return "db-proxy" if honeypot_layer.is_database() else "default"


# -- validation (mirrors container-firewall.php validate()) --------------------

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
        raise ValueError("peer must be a container name, an IPv4 address/CIDR, any, local-subnets, db-host or internet")
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


def validate_locked_rule(profile_name: str, direction: str, peer: str, proto: str) -> None:
    """Raises ValueError when a locked profile may not have this rule."""
    if direction != "outbound" or profile_name not in LOCKED_OUTBOUND:
        return
    allowed = LOCKED_OUTBOUND[profile_name]
    if not allowed:
        raise ValueError(f"a {profile_name} container opens no connections at all")
    if peer not in allowed or proto != "tcp":
        raise ValueError(f"a {profile_name} container may only open tcp to {', '.join(allowed)}")


def validate_document(doc, profile_name: str | None = None) -> list[str]:
    """Every problem of a ruleset document; with a locked profile's name,
    also what that profile may never have (as container-firewall.php)."""
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
    if not errors and profile_name in LOCKED_OUTBOUND:
        if not doc["enabled"]:
            errors.append(f"the {profile_name} firewall cannot be switched off (attackers get into these "
                          "containers)")
        for rule in doc["outbound"]:
            try:
                validate_locked_rule(profile_name, "outbound", rule["peer"], rule["proto"])
            except ValueError as e:
                errors.append(f"outbound/{rule['id']}: {e}")
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


def load_default_ruleset(path: Path | str = PRODUCTION.defaults_path) -> dict:
    """The image's default ruleset. Raises FirewallError when it is missing or
    invalid -- it ships with the repo, so that is a broken checkout."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise FirewallError(f"Cannot read the default ruleset {path}: {e}")
    errors = validate_document(doc, Path(path).stem)
    if errors:
        raise FirewallError(f"The default ruleset {path} is invalid: {'; '.join(errors)}")
    return doc


def default_rules(path: Path | str = PRODUCTION.defaults_path) -> list[FirewallRule]:
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
    path: Path = PRODUCTION.settings_path
    defaults_path: Path = PRODUCTION.defaults_path

    @property
    def profile_name(self) -> str:
        return self.defaults_path.stem  # images/container_firewall/<profile>.json

    @property
    def locked(self) -> bool:
        return self.profile_name in LOCKED_OUTBOUND

    @classmethod
    def for_profile(cls, profile: Profile) -> "FirewallSettings":
        return cls.load(profile.settings_path, profile.defaults_path)

    @classmethod
    def load(cls, path: Path | str = PRODUCTION.settings_path,
             defaults_path: Path | str = PRODUCTION.defaults_path) -> "FirewallSettings":
        """A missing or unparseable file gives the defaults, never an error.
        A locked profile always loads switched on, without the custom rules it
        may not have."""
        settings = cls(path=Path(path), defaults_path=Path(defaults_path))
        try:
            raw = json.loads(settings.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return settings
        if not isinstance(raw, dict):
            return settings
        if isinstance(raw.get("enabled"), bool) and not settings.locked:
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
        validate_locked_rule(self.profile_name, direction, peer, proto)
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
    """The ruleset document container-firewall expects. Disabled rules are
    included (they cost nothing and keep the page's rows stable)."""
    doc = {"version": DOCUMENT_VERSION, "enabled": settings.enabled or settings.locked,
           "inbound": [], "outbound": []}
    for r in settings.rules():
        doc[r.direction].append(r.to_document())
    return doc


def encode_document(doc: dict) -> str:
    return base64.b64encode(json.dumps(doc, ensure_ascii=False).encode("utf-8")).decode("ascii")


def fingerprint(doc: dict) -> str:
    """sha256 of the canonical JSON; container-firewall.php fingerprint()
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


def lockout_warnings(doc: dict, layer: str, profile: Profile = PRODUCTION) -> list[str]:
    """What this ruleset would break or open, in plain words (empty = nothing
    obvious). A CIDR peer counts as reaching (the dashboard cannot know the
    subnet)."""
    if profile is HONEYPOT:
        return _honeypot_warnings(doc, layer)
    if profile is HONEYPOT_DATABASE:
        if not any(_reaches(r, ("local-subnets", "any"), 3306, layer) for r in doc["inbound"]):
            return ["No enabled inbound rule lets honeypot_network open tcp/3306: the pools (and the seed, "
                    "migration and content-sync jobs) lose their databases."]
        return []
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


def _honeypot_warnings(doc: dict, layer: str) -> list[str]:
    # Locked (LOCKED_OUTBOUND): it cannot be off or reach past db-host, so
    # only what it would break is left to warn about.
    out = []
    if not any(_reaches(r, (EDGE_PEER, "any", "local-subnets"), 80, layer) for r in doc["inbound"]):
        out.append("No enabled inbound rule lets reverse_proxy open tcp/80: the edge cannot reach the pools, "
                   "so diverted sessions get a 502 instead of the honeypot.")
    if not any(_reaches(r, ("db-host",), 3306, layer) for r in doc["outbound"]):
        out.append("No enabled outbound rule reaches db-host on tcp/3306: the pools lose their databases.")
    return out


# -- container ------------------------------------------------------------------

@dataclass
class FirewallStatus:
    """What `container-firewall status` reported."""
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
    profile: str = "production"

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
                profile=raw.get("profile", "production"),
            )
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise FirewallError(f"Unreadable status from {TOOL}: {e}")


def _exec(remote: RemoteConfig | None, profile: Profile, *args: str, timeout: float = 30.0) -> str:
    argv, cwd = Target(project="edge", remote=remote).build(
        "exec", "-T", profile.service_for(active_layer()), TOOL, *args)
    result = run_checked(argv, error=FirewallError, cwd=cwd, timeout=timeout, what=TOOL)
    return result.stdout


def _explain(e: FirewallError, profile: Profile) -> FirewallError:
    text = str(e)
    if any(m in text for m in ("no such service", "is not running", "No such container")):
        return FirewallError(
            f"{profile.service_for(active_layer())} (the firewall of {profile.protects}) is not running. Deploy it: "
            f"docker compose build {PRODUCTION.service} && docker compose up -d -- this recreates "
            f"{profile.protects} inside it.")
    return e


def get_status(remote: RemoteConfig | None, profile: Profile = PRODUCTION) -> FirewallStatus:
    try:
        return FirewallStatus.parse(_exec(remote, profile, "status"))
    except FirewallError as e:
        raise _explain(e, profile) from None


def apply_document(remote: RemoteConfig | None, doc: dict, profile: Profile = PRODUCTION) -> None:
    errors = validate_document(doc, profile.name)
    if errors:
        raise FirewallError("Invalid ruleset: " + "; ".join(errors))
    try:
        _exec(remote, profile, "apply", "--b64", encode_document(doc))
    except FirewallError as e:
        raise _explain(e, profile) from None
