import base64
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import container_firewall as pfw  # noqa: E402

PHP_TOOL = pfw.IMAGE_DIR / "container-firewall.php"


class ValidationTests(unittest.TestCase):
    def test_ports(self):
        self.assertEqual(pfw.parse_ports("80"), [(80, 80)])
        self.assertEqual(pfw.normalise_ports(" 465, 587 "), "465,587")
        self.assertEqual(pfw.normalise_ports("8000-8100"), "8000-8100")
        for bad in ("", "0", "70000", "90-80", "http", "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16",
                    "1-2,3-4,5-6,7-8,9-10,11-12,13-14,15-16"):
            with self.assertRaises(ValueError, msg=bad):
                pfw.parse_ports(bad)

    def test_peers(self):
        for ok in ("reverse_proxy", "honeypot_database_2", "10.0.0.0/8", "172.20.0.5", "any", "local-subnets"):
            pfw.validate_peer(ok, "inbound")
        pfw.validate_peer("internet", "outbound")
        for bad in ("internet", "999.1.1.1", "10.0.0.0/33", "-x", "a b", "a;rm"):
            with self.assertRaises(ValueError, msg=bad):
                pfw.validate_peer(bad, "inbound")

    def test_default_ruleset_is_valid_and_reaches_edge_and_db(self):
        doc = pfw.load_default_ruleset()
        self.assertEqual(pfw.validate_document(doc), [])
        self.assertEqual(pfw.lockout_warnings(doc, "default"), [])
        self.assertEqual(pfw.lockout_warnings(doc, "db-proxy"), [])

    def test_honeypot_default_only_reaches_own_database(self):
        doc = pfw.load_default_ruleset(pfw.HONEYPOT.defaults_path)
        self.assertEqual(pfw.validate_document(doc), [])
        self.assertEqual(pfw.lockout_warnings(doc, "default", pfw.HONEYPOT), [])
        self.assertEqual([(r["peer"], r["ports"]) for r in doc["outbound"] if r["enabled"]],
                         [("db-host", "3306")])
        self.assertEqual([(r["peer"], r["ports"]) for r in doc["inbound"] if r["enabled"]],
                         [("reverse_proxy", "80")])

    def test_honeypot_database_default_opens_nothing(self):
        doc = pfw.load_default_ruleset(pfw.HONEYPOT_DATABASE.defaults_path)
        self.assertEqual(pfw.validate_document(doc, "honeypot_database"), [])
        self.assertEqual(pfw.lockout_warnings(doc, "default", pfw.HONEYPOT_DATABASE), [])
        self.assertEqual(doc["outbound"], [])
        self.assertEqual([(r["peer"], r["proto"], r["ports"]) for r in doc["inbound"] if r["enabled"]],
                         [("local-subnets", "tcp", "3306")])

    def test_profiles(self):
        self.assertEqual(set(pfw.PROFILES), {"production", "honeypot", "honeypot_database"})
        for profile in pfw.PROFILES.values():
            self.assertTrue(profile.defaults_path.is_file(), profile.defaults_path)
            for layer in profile.layers:
                self.assertTrue(profile.service_for(layer).endswith("_net"))
        self.assertEqual(len({p.settings_path for p in pfw.PROFILES.values()}), 3)
        self.assertNotIn("db-proxy", pfw.HONEYPOT.layers)
        self.assertEqual(pfw.HONEYPOT_DATABASE.service_for("default"), "honeypot_database_1_net")
        self.assertEqual(pfw.HONEYPOT_DATABASE.service_for("db-proxy"), "honeypot_database_net")
        self.assertEqual({p.name for p in pfw.PROFILES.values() if p.locked}, {"honeypot", "honeypot_database"})

    def test_php_tool_mirrors_limits(self):
        # The container validates the same document; keep the limits in step.
        php = PHP_TOOL.read_text(encoding="utf-8")
        self.assertIn(f"const MAX_RULES = {pfw.MAX_RULES};", php)
        self.assertIn(f"const MAX_PORTS = {pfw.MAX_PORTS};", php)
        self.assertIn("'/^[a-z0-9][a-z0-9-]{0,47}$/'", php)
        self.assertEqual(re.search(r"const PEER_KEYWORDS = \[(.*?)\];", php).group(1),
                         ", ".join(f"'{k}'" for k in pfw.PEER_KEYWORDS))
        self.assertEqual(re.search(r"const PROFILES = \[(.*?)\];", php).group(1),
                         ", ".join(f"'{k}'" for k in pfw.PROFILES))
        locked = re.search(r"const LOCKED_OUTBOUND = \[(.*?)\];", php).group(1)
        self.assertEqual(locked, ", ".join(
            f"'{k}' => [{', '.join(repr(p) for p in v)}]" for k, v in pfw.LOCKED_OUTBOUND.items()))


class LockedProfileTests(unittest.TestCase):
    """Attackers get into honeypot containers: no ruleset may switch their
    firewall off or give them a way out past the pool's own database."""

    def settings(self, profile):
        return pfw.FirewallSettings.load(Path(tempfile.mkdtemp()) / "s.json", profile.defaults_path)

    def test_cannot_be_switched_off(self):
        for profile in (pfw.HONEYPOT, pfw.HONEYPOT_DATABASE):
            doc = pfw.load_default_ruleset(profile.defaults_path)
            doc["enabled"] = False
            self.assertIn("cannot be switched off", " ".join(pfw.validate_document(doc, profile.name)))
            with self.assertRaises(pfw.FirewallError):
                pfw.apply_document(None, doc, profile)
            # Even a settings file saying "off" builds an enforcing document.
            s = self.settings(profile)
            s.path.write_text(json.dumps({"enabled": False}), encoding="utf-8")
            again = pfw.FirewallSettings.load(s.path, profile.defaults_path)
            self.assertTrue(again.enabled)
            again.enabled = False
            self.assertTrue(pfw.build_document(again)["enabled"])

    def test_pool_outbound_only_db_host(self):
        s = self.settings(pfw.HONEYPOT)
        for peer, proto in (("internet", "tcp"), ("reverse_proxy", "tcp"), ("local-subnets", "tcp"),
                            ("any", "tcp"), ("honeypot_database_2", "tcp"), ("10.9.0.0/16", "udp"),
                            ("db-host", "udp"), ("session_store", "tcp")):
            with self.assertRaises(ValueError, msg=peer):
                s.add_custom("outbound", peer, proto, "1")
        s.add_custom("outbound", "db-host", "tcp", "33060")  # its own database: allowed
        s.add_custom("inbound", "local-subnets", "tcp", "8080")  # inbound opens no way out
        self.assertEqual(pfw.validate_document(pfw.build_document(s), "honeypot"), [])

    def test_database_opens_nothing(self):
        s = self.settings(pfw.HONEYPOT_DATABASE)
        with self.assertRaises(ValueError):
            s.add_custom("outbound", "db-host", "tcp", "3306")
        doc = pfw.build_document(s)
        doc["outbound"].append({"id": "x", "enabled": False, "peer": "any", "proto": "tcp", "ports": "1",
                                "label": ""})
        self.assertIn("opens no connections", " ".join(pfw.validate_document(doc, "honeypot_database")))

    def test_escape_rules_in_a_saved_file_are_dropped(self):
        s = self.settings(pfw.HONEYPOT)
        s.path.write_text(json.dumps({"custom": [
            {"direction": "outbound", "peer": "reverse_proxy", "proto": "tcp", "ports": "80"},
            {"direction": "outbound", "peer": "db-host", "proto": "tcp", "ports": "33060"}]}), encoding="utf-8")
        again = pfw.FirewallSettings.load(s.path, pfw.HONEYPOT.defaults_path)
        self.assertEqual([c["peer"] for c in again.custom_rules], ["db-host"])

    def test_production_is_not_locked(self):
        s = pfw.FirewallSettings(path=Path(tempfile.mkdtemp()) / "p.json")
        s.add_custom("outbound", "internet", "tcp", "8443")
        s.enabled = False
        self.assertEqual(pfw.validate_document(pfw.build_document(s), "production"), [])


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "container_firewall.json"

    def load(self):
        return pfw.FirewallSettings.load(self.tmp)

    def test_defaults(self):
        s = self.load()
        by_key = {r.key: r for r in s.rules()}
        self.assertTrue(s.enabled)
        self.assertTrue(by_key["inbound/edge-http"].enabled)
        self.assertFalse(by_key["outbound/internet-http"].enabled)
        self.assertEqual(by_key["outbound/honeypot-databases"].layer, "db-proxy")
        self.assertFalse(by_key["outbound/honeypot-databases"].active_in("default"))

    def test_toggle_records_only_deviations(self):
        s = self.load()
        s.set_enabled("outbound/smtp", True)
        s.set_enabled("inbound/edge-http", True)  # already the default
        self.assertEqual(s.overrides, {"outbound/smtp": True})
        s.set_enabled("outbound/smtp", False)
        self.assertEqual(s.overrides, {})

    def test_custom_rules_round_trip(self):
        s = self.load()
        s.enabled = False
        rec = s.add_custom("outbound", "smtp.example.net", "tcp", "587", "Mail relay")
        s.save()
        again = self.load()
        self.assertFalse(again.enabled)
        custom = [r for r in again.rules() if r.custom]
        self.assertEqual([(r.key, r.peer, r.ports) for r in custom],
                         [(f"outbound/{rec['id']}", "smtp.example.net", "587")])
        self.assertTrue(again.remove_custom(f"outbound/{rec['id']}"))
        self.assertEqual([r for r in again.rules() if r.custom], [])

    def test_duplicate_and_bad_custom_rejected(self):
        s = self.load()
        with self.assertRaises(ValueError):
            s.add_custom("inbound", "reverse_proxy", "tcp", "80")  # = edge-http
        with self.assertRaises(ValueError):
            s.add_custom("inbound", "internet", "tcp", "22")
        with self.assertRaises(ValueError):
            s.add_custom("outbound", "x", "icmp", "1")
        with self.assertRaises(ValueError):
            s.add_custom("sideways", "x", "tcp", "1")

    def test_unparseable_file_gives_defaults(self):
        self.tmp.write_text("{nope", encoding="utf-8")
        self.assertTrue(self.load().enabled)
        self.tmp.write_text(json.dumps({"enabled": "no", "custom": [{"direction": "inbound", "peer": "internet",
                                                                     "proto": "tcp", "ports": "1"}]}))
        s = self.load()
        self.assertTrue(s.enabled)
        self.assertEqual(s.custom_rules, [])


class DocumentTests(unittest.TestCase):
    def settings(self):
        return pfw.FirewallSettings(path=Path(tempfile.mkdtemp()) / "p.json")

    def test_document_is_valid_and_encodes(self):
        s = self.settings()
        s.add_custom("outbound", "10.1.0.0/16", "tcp/udp", "53", "Internal DNS")
        doc = pfw.build_document(s)
        self.assertEqual(pfw.validate_document(doc), [])
        self.assertEqual(json.loads(base64.b64decode(pfw.encode_document(doc))), doc)
        self.assertEqual(doc["outbound"][-1]["peer"], "10.1.0.0/16")
        self.assertNotIn("layer", doc["inbound"][0])

    def test_fingerprint_ignores_key_order(self):
        doc = pfw.build_document(self.settings())
        shuffled = json.loads(json.dumps(doc, sort_keys=True))
        self.assertEqual(pfw.fingerprint(doc), pfw.fingerprint(shuffled))
        doc["enabled"] = False
        self.assertNotEqual(pfw.fingerprint(doc), pfw.fingerprint(shuffled))

    def test_lockout_warnings(self):
        s = self.settings()
        s.set_enabled("inbound/edge-http", False)
        s.set_enabled("outbound/database", False)
        warnings = pfw.lockout_warnings(pfw.build_document(s), "default")
        self.assertEqual(len(warnings), 2)
        s.set_enabled("outbound/honeypot-databases", False)
        self.assertEqual(len(pfw.lockout_warnings(pfw.build_document(s), "db-proxy")), 3)
        s.enabled = False
        self.assertIn("switched off", pfw.lockout_warnings(pfw.build_document(s), "default")[0])

    def test_honeypot_lockout_warnings(self):
        s = pfw.FirewallSettings.load(Path(tempfile.mkdtemp()) / "h.json", pfw.HONEYPOT.defaults_path)
        warn = lambda: pfw.lockout_warnings(pfw.build_document(s), "default", pfw.HONEYPOT)  # noqa: E731
        self.assertEqual(warn(), [])
        s.set_enabled("outbound/database", False)
        self.assertIn("db-host", warn()[0])
        s.set_enabled("inbound/edge-http", False)
        self.assertEqual(len(warn()), 2)
        d = pfw.FirewallSettings.load(Path(tempfile.mkdtemp()) / "d.json", pfw.HONEYPOT_DATABASE.defaults_path)
        d.set_enabled("inbound/mysql", False)
        self.assertIn("tcp/3306", pfw.lockout_warnings(pfw.build_document(d), "default", pfw.HONEYPOT_DATABASE)[0])

    def test_status_parse(self):
        doc = pfw.build_document(self.settings())
        fp = pfw.fingerprint(doc)
        status = pfw.FirewallStatus.parse(json.dumps({
            "source": "saved", "layer": "default", "hooked": True, "document": doc, "fingerprint": fp,
            "enforced_fingerprint": fp, "applied_at": "2026-10-31T10:00:00+00:00",
            "resolved": {"reverse_proxy": ["172.20.0.9"]}, "ipv6": True,
            "counters": {"in": {"edge-http": {"packets": 7, "bytes": 420}}, "out": []},
        }))
        self.assertTrue(status.enforced)
        self.assertEqual(status.hits("inbound", "edge-http"), 7)
        self.assertIsNone(status.hits("outbound", "database"))
        with self.assertRaises(pfw.FirewallError):
            pfw.FirewallStatus.parse("not json")

    def test_apply_runs_compose_exec(self):
        doc = pfw.build_document(self.settings())
        with mock.patch.object(pfw, "run_checked") as run:
            pfw.apply_document(None, doc)
        argv = run.call_args.args[0]
        i = argv.index("exec")
        self.assertEqual(argv[i:i + 5], ["exec", "-T", "production_eshop_net", "container-firewall", "apply"])
        self.assertEqual(json.loads(base64.b64decode(argv[-1])), doc)
        doc["inbound"][0]["ports"] = "0"
        with self.assertRaises(pfw.FirewallError):
            pfw.apply_document(None, doc)

    def test_honeypot_apply_and_status_target_pool_firewall(self):
        doc = pfw.load_default_ruleset(pfw.HONEYPOT.defaults_path)
        with mock.patch.object(pfw, "run_checked") as run:
            pfw.apply_document(None, doc, pfw.HONEYPOT)
        argv = run.call_args.args[0]
        i = argv.index("exec")
        self.assertEqual(argv[i:i + 5], ["exec", "-T", "honeypot_eshop_1_net", "container-firewall", "apply"])

    def test_database_profile_targets_the_layer_firewall(self):
        doc = pfw.load_default_ruleset(pfw.HONEYPOT_DATABASE.defaults_path)
        for layer, service in (("default", "honeypot_database_1_net"), ("db-proxy", "honeypot_database_net")):
            with mock.patch.object(pfw, "active_layer", return_value=layer), \
                    mock.patch.object(pfw, "run_checked") as run:
                pfw.apply_document(None, doc, pfw.HONEYPOT_DATABASE)
            self.assertIn(service, run.call_args.args[0])

    def test_missing_service_explained(self):
        with mock.patch.object(pfw, "run_checked",
                               side_effect=pfw.FirewallError("service \"honeypot_eshop_1_net\" is not running")):
            with self.assertRaises(pfw.FirewallError) as cm:
                pfw.get_status(None, pfw.HONEYPOT)
        self.assertIn("honeypot_eshop_1_net", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
