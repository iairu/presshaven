"""Static setup + hardening checks for the production and honeypot instances.

Renders both honeypot layers with `docker compose config` (the stack is NOT
started, nothing is contacted) and checks what each WordPress / database
container is declared with: its network namespace owner (the container
firewall sidecar), capabilities, limits, networks and firewall profile.
Runtime pools (pool_manager) are covered by images/pool_manager/
test_pool_containers.py; the running stack by test_production_instance.sh and
test_honeypot_instance.sh.

  cd ids/testing && python3 -m unittest test_stack_hardening -v
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

EDGE_DIR = Path(__file__).resolve().parent.parent
LAYERS = {"default": "docker-compose.yml", "db-proxy": "docker-compose.db-proxy.yml"}
FIREWALL_IMAGE = "presshaven/container-firewall:1"
WORDPRESS_IMAGE = "presshaven/wordpress:7.1.3-php8.4-hardened"
WORDPRESS_CAPS = {"CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID", "NET_BIND_SERVICE", "KILL"}
MYSQL_CAPS = {"CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID", "SYS_NICE"}
# Capabilities no WordPress or database container may ever hold.
FORBIDDEN_CAPS = {"NET_ADMIN", "NET_RAW", "SYS_ADMIN", "SYS_PTRACE", "SYS_MODULE", "ALL"}
# Services allowed on both production_network and honeypot_network: the edge,
# and trusted jobs that only open connections (no listener a pool could use;
# the pools' firewalls refuse them anyway).
BRIDGES = {"reverse_proxy", "honeypot_content_sync", "honeypot_db_init"}

_rendered: dict[str, dict] = {}


def render(layer: str) -> dict:
    if layer not in _rendered:
        out = subprocess.run(["docker", "compose", "-f", LAYERS[layer], "config", "--format", "json"],
                             cwd=EDGE_DIR, capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            raise unittest.SkipTest(f"docker compose config failed: {out.stderr.strip()[:300]}")
        _rendered[layer] = json.loads(out.stdout)
    return _rendered[layer]


def env(service: dict) -> dict:
    e = service.get("environment") or {}
    return e if isinstance(e, dict) else dict(x.split("=", 1) for x in e)


def networks(service: dict) -> set:
    return set(service.get("networks") or {})


def mounts(service: dict) -> dict:
    return {v["target"]: v for v in service.get("volumes") or []}


@unittest.skipUnless(shutil.which("docker"), "docker CLI not installed")
class LayerChecks:
    """Mixed into one TestCase per layer (LAYER set by the subclass)."""
    LAYER = ""

    @classmethod
    def setUpClass(cls):
        cls.cfg = render(cls.LAYER)
        cls.svc = cls.cfg["services"]

    # -- helpers ---------------------------------------------------------------
    def assertHardened(self, name, caps, mem_max_mb):
        s = self.svc[name]
        self.assertEqual(s.get("cap_drop"), ["ALL"], name)
        self.assertEqual(set(s.get("cap_add") or []), caps, name)
        self.assertFalse(set(s.get("cap_add") or []) & FORBIDDEN_CAPS, name)
        self.assertIn("no-new-privileges:true", s.get("security_opt") or [], name)
        self.assertFalse(s.get("privileged"), name)
        self.assertNotIn("pid", s, name)  # never the host's PID namespace
        self.assertNotIn("ipc", s, name)
        self.assertFalse(s.get("ports"), f"{name} publishes ports on the host")
        self.assertTrue(s.get("pids_limit"), name)
        mem = int(s.get("mem_limit") or 0)
        self.assertTrue(0 < mem <= mem_max_mb * 2**20, f"{name} mem_limit {mem}")
        self.assertNotIn("/var/run/docker.sock", mounts(s), name)

    def assertFirewallSidecar(self, fw_name, protected, profile):
        fw, wp = self.svc[fw_name], self.svc[protected]
        self.assertEqual(fw["image"], FIREWALL_IMAGE)
        self.assertEqual(env(fw)["FIREWALL_PROFILE"], profile)
        self.assertEqual(env(fw)["FIREWALL_LAYER"], self.LAYER)
        self.assertEqual(fw.get("cap_drop"), ["ALL"])
        self.assertEqual(fw.get("cap_add"), ["NET_ADMIN"])
        self.assertIn("no-new-privileges:true", fw.get("security_opt") or [])
        self.assertTrue(fw.get("read_only"))
        self.assertTrue(fw.get("init"))
        self.assertFalse(fw.get("ports"))
        self.assertEqual(fw["healthcheck"]["test"], ["CMD", "container-firewall", "health"])
        self.assertEqual(mounts(fw)["/var/lib/container-firewall"]["source"], "container_firewall_rules")
        # Every network answers to the protected container's old DNS name.
        for net, opts in (fw.get("networks") or {}).items():
            self.assertIn(protected, (opts or {}).get("aliases") or [], f"{fw_name} on {net}")
        # The protected container lives in the sidecar's namespace, nothing else.
        self.assertEqual(wp.get("network_mode"), f"service:{fw_name}")
        self.assertFalse(wp.get("networks"))
        dep = wp["depends_on"][fw_name]
        self.assertEqual(dep["condition"], "service_healthy")
        self.assertTrue(dep.get("restart"), f"{protected} must be recreated when its firewall restarts")
        self.assertNotIn("/var/lib/container-firewall", mounts(wp), f"rules must stay out of {protected}")
        self.assertEqual(networks(fw), {"honeypot_network"} if profile != "production" else networks(fw))

    # -- production ------------------------------------------------------------
    def test_production_eshop_is_hardened(self):
        self.assertEqual(self.svc["production_eshop"]["image"], WORDPRESS_IMAGE)
        self.assertHardened("production_eshop", WORDPRESS_CAPS, 1024)
        e = env(self.svc["production_eshop"])
        self.assertEqual(e["WORDPRESS_DB_HOST"].split(":")[0], "production_database")
        self.assertNotIn("MYSQL_ROOT_PASSWORD", e)

    def test_production_eshop_sits_behind_its_firewall(self):
        self.assertFirewallSidecar("production_eshop_net", "production_eshop", "production")

    def test_production_database_is_hardened_and_private(self):
        self.assertHardened("production_database", MYSQL_CAPS, 2048)
        self.assertEqual(networks(self.svc["production_database"]), {"production_network"})

    def test_backup_service_cannot_be_reached_from_honeypots(self):
        s = self.svc["backup_service"]
        self.assertEqual(networks(s), {"production_network"})
        self.assertEqual(s.get("cap_drop"), ["ALL"])
        self.assertTrue(mounts(s)["/source_wp"].get("read_only"))

    def test_only_the_edge_publishes_ports(self):
        self.assertEqual({n for n, s in self.svc.items() if s.get("ports")}, {"reverse_proxy"})

    def test_no_service_mounts_the_docker_socket_except_pool_manager(self):
        with_socket = {n for n, s in self.svc.items() if "/var/run/docker.sock" in mounts(s)}
        self.assertLessEqual(with_socket, {"pool_manager"})

    # -- honeypot --------------------------------------------------------------
    def test_honeypot_network_is_internal(self):
        self.assertTrue(self.cfg["networks"]["honeypot_network"].get("internal"),
                        "a hijacked pool must have no route to the internet")

    def test_only_bridges_join_production_and_honeypot_networks(self):
        both = {n for n, s in self.svc.items()
                if {"production_network", "honeypot_network"} <= networks(s)}
        both.discard("production_eshop_net")  # db-proxy layer: production serves the pool DBs
        self.assertLessEqual(both, BRIDGES)

    def test_no_honeypot_service_is_on_production_network(self):
        for name, s in self.svc.items():
            if name.startswith("honeypot_eshop") or re.match(r"honeypot_database(_\d+)?$", name):
                self.assertNotIn("production_network", networks(s), name)

    def test_firewall_defaults_keep_a_pool_inside(self):
        doc = json.loads((EDGE_DIR / "images/container_firewall/honeypot.json").read_text())
        self.assertTrue(doc["enabled"])
        self.assertEqual([(r["peer"], r["ports"]) for r in doc["outbound"] if r["enabled"]],
                         [("db-host", "3306")])
        self.assertEqual([(r["peer"], r["ports"]) for r in doc["inbound"] if r["enabled"]],
                         [("reverse_proxy", "80")])

    def test_database_firewall_defaults_open_nothing_out(self):
        doc = json.loads((EDGE_DIR / "images/container_firewall/honeypot_database.json").read_text())
        self.assertTrue(doc["enabled"])
        self.assertEqual(doc["outbound"], [])
        self.assertEqual([(r["peer"], r["proto"], r["ports"]) for r in doc["inbound"] if r["enabled"]],
                         [("local-subnets", "tcp", "3306")])

    def test_honeypot_profiles_are_locked_in_the_firewall_tool(self):
        src = (EDGE_DIR / "images/container_firewall/container-firewall.php").read_text()
        self.assertIn("const LOCKED_OUTBOUND = ['honeypot' => ['db-host'], 'honeypot_database' => []];", src)
        self.assertIn("'FORWARD' => 'FW_FWD'", src)

    def test_every_container_attackers_can_reach_sits_behind_a_honeypot_firewall(self):
        # A pool's WordPress, its database (WordPress holds the DB password)
        # and the seed jobs that run that WordPress's PHP via wp-cli.
        for name, s in self.svc.items():
            if re.fullmatch(r"honeypot_(eshop|database|db_seed)(_\d+)?", name):
                owner = (s.get("network_mode") or "").removeprefix("service:")
                self.assertTrue(owner.endswith("_net"), f"{name} has its own network namespace")
                self.assertEqual(env(self.svc[owner])["FIREWALL_PROFILE"],
                                 "honeypot_database" if "database" in name else "honeypot", name)

    def test_containers_on_honeypot_network_and_another_never_forward(self):
        for name, s in self.svc.items():
            nets = networks(s)
            if "honeypot_network" in nets and len(nets) > 1 and not name.endswith("_net"):
                self.assertEqual(str((s.get("sysctls") or {}).get("net.ipv4.ip_forward")), "0", name)

    def test_jobs_never_send_local_files_to_a_pool_database(self):
        text = (EDGE_DIR / LAYERS[self.LAYER]).read_text()
        for host in ("HP", "HOST"):
            self.assertNotIn(f'mysql -h\\"\\$${host}\\"', text, host)
        for script in ("scripts", "db_proxy/scripts"):
            src = (EDGE_DIR / script / "replicate_content_to_honeypot.sh").read_text()
            self.assertNotIn('mysql -h "$db_host"', src, script)
            self.assertEqual(src.count('mysql --local-infile=0 -h "$db_host"'), 2, script)

    def test_production_firewall_defaults_do_not_open_honeypots_in_this_layer(self):
        doc = json.loads((EDGE_DIR / "images/container_firewall/production.json").read_text())
        for r in doc["outbound"]:
            if r["enabled"] and r.get("layer", self.LAYER) == self.LAYER and self.LAYER == "default":
                self.assertNotIn(r["peer"], ("any", "local-subnets"), r["id"])


class DefaultLayer(LayerChecks, unittest.TestCase):
    LAYER = "default"

    def pools(self):
        return sorted(int(m.group(1)) for n in self.svc if (m := re.fullmatch(r"honeypot_eshop_(\d+)", n)))

    def test_every_pool_is_complete(self):
        pools = self.pools()
        self.assertGreaterEqual(len(pools), 1)
        for n in pools:
            for name in (f"honeypot_eshop_{n}", f"honeypot_eshop_{n}_net", f"honeypot_database_{n}",
                         f"honeypot_database_{n}_net"):
                self.assertIn(name, self.svc)

    def test_pool_eshops_are_hardened_and_behind_their_firewalls(self):
        for n in self.pools():
            self.assertEqual(self.svc[f"honeypot_eshop_{n}"]["image"], WORDPRESS_IMAGE)
            self.assertHardened(f"honeypot_eshop_{n}", WORDPRESS_CAPS, 1024)
            self.assertFirewallSidecar(f"honeypot_eshop_{n}_net", f"honeypot_eshop_{n}", "honeypot")

    def test_each_pool_is_wired_to_its_own_database(self):
        for n in self.pools():
            db = f"honeypot_database_{n}"
            self.assertEqual(env(self.svc[f"honeypot_eshop_{n}"])["WORDPRESS_DB_HOST"].split(":")[0], db)
            self.assertEqual(env(self.svc[f"honeypot_eshop_{n}_net"])["FIREWALL_DB_HOST"].split(":")[0], db)

    def test_pool_databases_are_hardened_and_behind_their_firewalls(self):
        for n in self.pools():
            self.assertHardened(f"honeypot_database_{n}", MYSQL_CAPS, 1024)
            self.assertFirewallSidecar(f"honeypot_database_{n}_net", f"honeypot_database_{n}",
                                       "honeypot_database")

    def test_seeds_run_wordpress_php_inside_the_pool_firewall(self):
        for n in self.pools():
            seed = self.svc[f"honeypot_db_seed_{n}"]
            self.assertEqual(seed.get("network_mode"), f"service:honeypot_eshop_{n}_net")
            self.assertFalse(seed.get("networks"))
            self.assertEqual(seed["depends_on"][f"honeypot_eshop_{n}_net"]["condition"], "service_healthy")

    def test_pool_database_passwords_differ_from_each_other_and_production(self):
        # Compared, never printed.
        pw = {n: env(self.svc[f"honeypot_database_{n}"])["MYSQL_PASSWORD"] for n in self.pools()}
        prod = env(self.svc["production_database"])
        self.assertEqual(len(set(pw.values())), len(pw), "two pools share a database password")
        self.assertTrue(prod["MYSQL_ROOT_PASSWORD"] not in pw.values(), "a pool user has production's root password")
        self.assertTrue(prod["MYSQL_PASSWORD"] not in pw.values(), "a pool user has production's password")
        for n in self.pools():
            self.assertTrue(env(self.svc[f"honeypot_database_{n}"])["MYSQL_ROOT_PASSWORD"]
                            != prod["MYSQL_ROOT_PASSWORD"], f"pool {n} shares production's root password")

    def test_production_firewall_is_on_production_network_only(self):
        self.assertEqual(networks(self.svc["production_eshop_net"]), {"production_network"})

    def test_pool_manager_builds_runtime_pools_with_the_same_firewall_image(self):
        src = (EDGE_DIR / "images/pool_manager/manager.py").read_text()
        default = re.search(r'FIREWALL_IMAGE = os\.environ\.get\("POOL_FIREWALL_IMAGE", "([^"]+)"\)', src)
        image = env(self.svc["pool_manager"]).get("POOL_FIREWALL_IMAGE", default.group(1))
        self.assertEqual(image, FIREWALL_IMAGE)


class DbProxyLayer(LayerChecks, unittest.TestCase):
    LAYER = "db-proxy"

    def test_no_honeypot_wordpress_containers(self):
        self.assertFalse([n for n in self.svc if n.startswith("honeypot_eshop")])

    def test_production_firewall_networks(self):
        self.assertEqual(networks(self.svc["production_eshop_net"]),
                         {"production_network", "honeypot_network", "monitoring_network"})

    def test_honeypot_database_is_hardened_and_behind_its_firewall(self):
        self.assertHardened("honeypot_database", MYSQL_CAPS, 1024)
        self.assertFirewallSidecar("honeypot_database_net", "honeypot_database", "honeypot_database")


if __name__ == "__main__":
    unittest.main()
