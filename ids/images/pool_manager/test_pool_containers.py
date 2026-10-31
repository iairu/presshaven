"""Runtime pool containers: the hardening each one is created with.

Docker is a MagicMock, so this checks the arguments manager.py hands the SDK --
the same properties docker-compose.yml gives pools 1-3 (ids/testing/
test_stack_hardening.py checks those). No Redis or Docker needed:
  python -m unittest test_pool_containers
"""
import os
import sys
import unittest
from unittest import mock

sys.modules.setdefault("docker", mock.MagicMock())
os.environ.setdefault("REDIS_PASSWORD", "x")
os.environ.setdefault("MYSQL_PASSWORD", "x")
os.environ.setdefault("MYSQL_ROOT_PASSWORD", "x")
import manager  # noqa: E402

NET_ADMIN_FREE_CAPS = {"CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID", "NET_BIND_SERVICE", "KILL"}


class PoolContainers(unittest.TestCase):
    def setUp(self):
        with mock.patch.object(manager.Manager, "__init__", lambda s: None):
            self.mgr = manager.Manager()
        self.mgr.docker = mock.MagicMock()
        self.mgr.redis = mock.MagicMock()
        self.mgr._local = manager.threading.local()
        self.mgr._local.phases = []
        self.mgr._wait_healthy = mock.MagicMock()
        self.mgr.register_ready = mock.MagicMock()
        self.fw = mock.MagicMock(id="fw123", name="pool_7_net")
        self.wp = mock.MagicMock(id="wp456")
        self.mgr.docker.containers.create.side_effect = [self.fw, self.wp]
        self.mgr.docker.api.create_endpoint_config.side_effect = lambda **kw: {"cfg": kw}
        self.mgr._start_wordpress_container(7, "honeypot_database_7", "honeypot_eshop_7",
                                            "files_7", {"honeypot.pool": "7"}, "pw")
        (fw_call, wp_call) = self.mgr.docker.containers.create.call_args_list
        self.fw_args, self.fw_kw = fw_call.args, fw_call.kwargs
        self.wp_args, self.wp_kw = wp_call.args, wp_call.kwargs

    # -- the firewall (network namespace owner) ------------------------------
    def test_firewall_is_created_and_healthy_before_wordpress(self):
        self.assertEqual(self.fw_args[0], manager.FIREWALL_IMAGE)
        self.fw.start.assert_called_once()
        first_wait = self.mgr._wait_healthy.call_args_list[0]
        self.assertIs(first_wait.args[0], self.fw)
        self.wp.start.assert_called_once()
        self.mgr.register_ready.assert_called_once_with(7)

    def test_firewall_enforces_the_honeypot_profile_for_its_own_database(self):
        env = self.fw_kw["environment"]
        self.assertEqual(env["FIREWALL_PROFILE"], "honeypot")
        self.assertEqual(env["FIREWALL_LAYER"], "default")
        self.assertEqual(env["FIREWALL_DB_HOST"], "honeypot_database_7:3306")

    def test_firewall_shares_the_rules_volume_with_compose_pools(self):
        self.assertEqual(self.fw_kw["volumes"], {
            f"{manager.PROJECT}_container_firewall_rules":
                {"bind": "/var/lib/container-firewall", "mode": "rw"}})

    def test_firewall_is_on_honeypot_network_only_and_answers_to_the_pool_name(self):
        net = f"{manager.PROJECT}_honeypot_network"
        self.assertEqual(self.fw_kw["network"], net)
        self.assertEqual(list(self.fw_kw["networking_config"]), [net])
        self.assertEqual(self.fw_kw["networking_config"][net], {"cfg": {"aliases": ["honeypot_eshop_7"]}})
        self.assertEqual(self.fw_kw["name"], "honeypot_eshop_7_net")

    def test_firewall_is_minimal(self):
        kw = self.fw_kw
        self.assertEqual(kw["cap_drop"], ["ALL"])
        self.assertEqual(kw["cap_add"], ["NET_ADMIN"])
        self.assertIn("no-new-privileges:true", kw["security_opt"])
        self.assertTrue(kw["read_only"])
        self.assertTrue(kw["init"])
        self.assertEqual(kw["pids_limit"], 50)
        self.assertEqual(kw["mem_limit"], "64m")
        self.assertEqual(kw["healthcheck"]["test"], ["CMD", "container-firewall", "health"])
        self.assertEqual(kw["labels"], {"honeypot.pool": "7"})  # destroyed with the pool

    # -- WordPress -----------------------------------------------------------
    def test_wordpress_joins_the_firewall_namespace_and_has_no_network_of_its_own(self):
        self.assertEqual(self.wp_kw["network_mode"], "container:fw123")
        self.assertNotIn("network", self.wp_kw)
        self.assertNotIn("networking_config", self.wp_kw)
        self.assertNotIn("ports", self.wp_kw)

    def test_wordpress_cannot_touch_the_firewall(self):
        kw = self.wp_kw
        self.assertEqual(kw["cap_drop"], ["ALL"])
        self.assertEqual(set(kw["cap_add"]), NET_ADMIN_FREE_CAPS)
        self.assertNotIn("NET_ADMIN", kw["cap_add"])
        self.assertNotIn("NET_RAW", kw["cap_add"])
        self.assertIn("no-new-privileges:true", kw["security_opt"])
        self.assertNotIn("/var/lib/container-firewall",
                         [v["bind"] for v in kw["volumes"].values()])
        self.assertNotIn("privileged", kw)

    def test_wordpress_talks_to_its_own_pool_database_only(self):
        env = self.wp_kw["environment"]
        self.assertEqual(env["WORDPRESS_DB_HOST"], "honeypot_database_7:3306")
        self.assertEqual(env["WORDPRESS_DB_PASSWORD"], "pw")
        self.assertEqual(env["HONEYPOT_POOL_ID"], "7")
        self.assertFalse(any("PRODUCTION" in k or "MYSQL_ROOT" in k for k in env))

    def test_wordpress_is_resource_limited(self):
        self.assertEqual(self.wp_kw["mem_limit"], "1024m")
        self.assertEqual(self.wp_kw["pids_limit"], 300)


class PoolDatabase(unittest.TestCase):
    def setUp(self):
        with mock.patch.object(manager.Manager, "__init__", lambda s: None):
            self.mgr = manager.Manager()
        self.mgr.docker = mock.MagicMock()
        self.mgr._local = manager.threading.local()
        self.mgr._local.phases = []
        self.mgr._wait_healthy = mock.MagicMock()
        self.fw, self.db = mock.MagicMock(id="dbfw9"), mock.MagicMock()
        self.mgr.docker.containers.create.side_effect = [self.fw, self.db]
        self.mgr.docker.api.create_endpoint_config.side_effect = lambda **kw: {"cfg": kw}

    def create(self, mode="wordpress"):
        with mock.patch.object(manager, "MODE", mode):
            got = self.mgr._create_database_container("honeypot_database_7", "db_7", "pw",
                                                      {"honeypot.pool": "7"})
        self.assertIs(got, self.db)
        fw_call, db_call = self.mgr.docker.containers.create.call_args_list
        return fw_call.kwargs, db_call.kwargs

    def test_runtime_database_is_hardened_and_inside_its_firewall(self):
        fw_kw, kw = self.create()
        self.assertEqual(kw["network_mode"], "container:dbfw9")
        self.assertNotIn("network", kw)
        self.assertNotIn("networking_config", kw)
        self.assertEqual(kw["cap_drop"], ["ALL"])
        self.assertNotIn("NET_ADMIN", kw["cap_add"])
        self.assertIn("no-new-privileges:true", kw["security_opt"])
        self.assertNotIn("ports", kw)

    def test_database_firewall_is_started_healthy_first(self):
        self.create()
        self.fw.start.assert_called_once()
        self.assertIs(self.mgr._wait_healthy.call_args_list[0].args[0], self.fw)
        self.db.start.assert_not_called()   # the caller starts MySQL

    def test_database_firewall_enforces_the_locked_profile_and_owns_the_name(self):
        fw_kw, _ = self.create()
        net = f"{manager.PROJECT}_honeypot_network"
        self.assertEqual(fw_kw["name"], "honeypot_database_7_net")
        self.assertEqual(fw_kw["environment"], {"FIREWALL_PROFILE": "honeypot_database",
                                                "FIREWALL_LAYER": "default"})
        self.assertEqual(fw_kw["network"], net)
        self.assertEqual(fw_kw["networking_config"], {net: {"cfg": {"aliases": ["honeypot_database_7"]}}})
        self.assertEqual(fw_kw["cap_add"], ["NET_ADMIN"])
        self.assertTrue(fw_kw["read_only"])
        self.assertEqual(fw_kw["labels"], {"honeypot.pool": "7"})  # destroyed with the pool

    def test_database_layer_firewall_reads_the_db_proxy_rules(self):
        fw_kw, _ = self.create("database")
        self.assertEqual(fw_kw["environment"]["FIREWALL_LAYER"], "db-proxy")

    def test_a_leftover_firewall_of_the_same_name_is_replaced(self):
        self.create()
        self.mgr.docker.containers.get.assert_called_with("honeypot_database_7_net")
        self.mgr.docker.containers.get.return_value.remove.assert_called_with(force=True)

    def test_removing_a_database_removes_its_firewall_after_it(self):
        order = []
        db = mock.MagicMock()
        db.name = "honeypot_pool_template"
        db.remove.side_effect = lambda **k: order.append("db")
        self.mgr.docker.containers.get.return_value.remove.side_effect = lambda **k: order.append("fw")
        self.mgr._remove_database(db)
        self.assertEqual(order, ["db", "fw"])
        self.mgr.docker.containers.get.assert_called_with("honeypot_pool_template_net")


class Helpers(unittest.TestCase):
    def setUp(self):
        with mock.patch.object(manager.Manager, "__init__", lambda s: None):
            self.mgr = manager.Manager()
        self.mgr.docker = mock.MagicMock()
        self.mgr._local = manager.threading.local()
        self.mgr._local.phases = []
        self.mgr.docker.containers.create.return_value.wait.return_value = {"StatusCode": 0}

    def test_a_helper_on_two_networks_does_not_forward_between_them(self):
        self.mgr._run_helper("img", ["true"], {}, {}, "x", network="a", extra_networks=["b"])
        kw = self.mgr.docker.containers.create.call_args.kwargs
        self.assertEqual(kw["sysctls"], {"net.ipv4.ip_forward": "0"})

    def test_a_helper_on_one_network_is_left_alone(self):
        self.mgr._run_helper("img", ["true"], {}, {}, "x", network="a")
        self.assertIsNone(self.mgr.docker.containers.create.call_args.kwargs["sysctls"])


class Destroy(unittest.TestCase):
    def test_firewalls_are_removed_after_wordpress_and_mysql(self):
        with mock.patch.object(manager.Manager, "__init__", lambda s: None):
            mgr = manager.Manager()
        mgr.docker, mgr.redis = mock.MagicMock(), mock.MagicMock()
        mgr.unregister = mock.MagicMock()
        removed = []
        containers = []
        for name in ("honeypot_eshop_8_net", "honeypot_database_8_net", "honeypot_eshop_8",
                     "honeypot_database_8"):
            c = mock.MagicMock()
            c.name = name
            c.remove.side_effect = lambda *a, _n=name, **k: removed.append(_n)
            containers.append(c)
        mgr.docker.containers.list.return_value = containers
        mgr.docker.volumes.list.return_value = []
        mgr.destroy(8)
        self.assertEqual(set(removed[-2:]), {"honeypot_eshop_8_net", "honeypot_database_8_net"})
        self.assertEqual(set(removed), {c.name for c in containers})


if __name__ == "__main__":
    unittest.main()
