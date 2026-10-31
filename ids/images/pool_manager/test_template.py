"""Unit tests for the database-layer pool template (fast scale-up): a pool is
built by copying a pre-seeded template MySQL data directory instead of dumping
production again. Docker and Redis are stubbed, so no services are needed.

  python -m unittest test_template
"""
import os
import sys
import unittest
from unittest import mock

# manager.py imports docker/redis at module level; stub both so this runs where
# the SDKs aren't installed (same approach as test_manager_reconcile).
sys.modules.setdefault("docker", mock.MagicMock())
sys.modules.setdefault("redis", mock.MagicMock())
os.environ.setdefault("REDIS_PASSWORD", "x")
os.environ.setdefault("MYSQL_PASSWORD", "x")

import manager  # noqa: E402


def _fake_volume(name, built, **labels):
    v = mock.MagicMock()
    v.name = name
    v.attrs = {"Labels": {"honeypot.template.built": str(built), **labels}}
    return v


class TemplateBase(unittest.TestCase):
    def setUp(self):
        manager.MODE = "database"
        manager.USE_TEMPLATE = True
        manager.TEMPLATE_TTL_S = 0
        with mock.patch.object(manager.Manager, "__init__", lambda s: None):
            self.mgr = manager.Manager()
        self.mgr.mysql_password = "prod-pw"
        self.mgr.honeypot_db_password = "hp-pw"
        self.mgr.host_paths = {
            "/migrations": "/h/migrations",
            "/migrations_override/01_clean-honeypot-data.sql": "/h/clean.sql"}
        self.mgr.image = "pool_manager:test"
        self.mgr._template_lock = manager.threading.Lock()
        self.mgr.docker = mock.MagicMock()
        self.mgr.docker.volumes.list.return_value = []   # no template yet
        self.mgr.redis = mock.MagicMock()
        self.mgr.redis.exists.return_value = False       # query log off
        # Record the helper runs ("what" label) and container builds.
        self.helpers = []
        self.mgr._run_helper = lambda *a, **k: self.helpers.append(k.get("what"))
        self.mgr._wait_healthy = lambda c, w: None
        self.created = []
        self.registered = []
        self.mgr.register_ready = lambda n, owned=False: self.registered.append(n)

        self.db_passwords = []

        def fake_create(name, vol, pw, labels):
            c = mock.MagicMock()
            c.name = name
            self.created.append((name, vol))
            self.db_passwords.append(pw)
            return c
        self.mgr._create_database_container = fake_create

    def _template_present(self, age_seconds=10.0):
        # Freshness is read from the "ready" marker volume, created last.
        marker = self.mgr._template_marker_name()
        self.mgr.docker.volumes.list.return_value = [
            _fake_volume(marker, manager.time.time() - age_seconds)]


class ProvisionWithTemplate(TemplateBase):
    def test_pool_copies_template_and_skips_the_production_clone(self):
        self._template_present()
        self.mgr.provision_database(7)
        self.assertIn("copy template", self.helpers)
        self.assertNotIn("clone + scrub", self.helpers)
        self.assertEqual(self.registered, [7])
        # The pool's own data volume is created and MySQL started on it.
        self.assertIn(("honeypot_database_7",
                       f"{manager.PROJECT}_honeypot_database_7_data"), self.created)

    def test_falls_back_to_production_clone_when_no_template(self):
        # volumes.list stays empty: ensure_template would build one, so stub it
        # out to simulate a build that did not finish (template still absent).
        self.mgr.ensure_template = lambda: None
        self.mgr.provision_database(8)
        self.assertIn("clone + scrub", self.helpers)
        self.assertNotIn("copy template", self.helpers)
        self.assertEqual(self.registered, [8])

    def test_template_off_always_clones_from_production(self):
        manager.USE_TEMPLATE = False
        self._template_present()
        called = []
        self.mgr.ensure_template = lambda: called.append(True)
        self.mgr.provision_database(9)
        self.assertEqual(called, [])                 # never consulted
        self.assertIn("clone + scrub", self.helpers)
        self.assertNotIn("copy template", self.helpers)

    def test_stale_template_is_not_used(self):
        manager.TEMPLATE_TTL_S = 60
        self._template_present(age_seconds=120)      # older than the TTL
        self.mgr.ensure_template = lambda: None       # pretend a rebuild is pending
        self.mgr.provision_database(10)
        self.assertNotIn("copy template", self.helpers)
        self.assertIn("clone + scrub", self.helpers)


class DatabaseLayerCredentials(TemplateBase):
    def test_every_database_layer_pool_uses_the_honeypot_password(self):
        self._template_present()
        self.mgr.provision_database(10)                 # from the template
        self.mgr.ensure_template = lambda: None
        self.mgr.docker.volumes.list.return_value = []
        self.mgr.provision_database(11)                 # direct clone
        self.assertEqual(self.db_passwords, ["hp-pw", "hp-pw"])

    def test_clone_reads_production_with_its_password_and_writes_with_the_honeypots(self):
        envs = []
        self.mgr._run_helper = lambda *a, **k: envs.append(k.get("environment"))
        self.mgr._build_template_database()
        env = next(e for e in envs if e and "HP" in e)
        self.assertEqual((env["MYSQL_PASSWORD"], env["HP_PASSWORD"]), ("prod-pw", "hp-pw"))
        script = manager.CLONE_SCRIPT
        self.assertNotIn('-h"$HP" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD"', script)
        self.assertNotIn('-h"$PROD" -u"$MYSQL_USER" -p"$HP_PASSWORD"', script)


class BuildTemplate(TemplateBase):
    def test_builds_scrubs_and_shuts_down_cleanly(self):
        stopped, removed = [], []

        def fake_create(name, vol, pw, labels):
            c = mock.MagicMock()
            c.name = name
            c.stop = lambda timeout=None: stopped.append(timeout)
            c.remove = lambda force=False, v=False: removed.append(name)
            self.created.append((name, vol))
            return c
        self.mgr._create_database_container = fake_create
        created_volumes = []
        self.mgr.docker.volumes.create = lambda name, labels=None: created_volumes.append(name)
        self.mgr._build_template_database()
        # Seeded with the same clone+scrub a pool would run...
        self.assertIn("template clone + scrub", self.helpers)
        # ...on a container whose volume is the template volume...
        self.assertIn(("honeypot_pool_template", self.mgr._template_volume_name()),
                      self.created)
        # ...then shut down cleanly (so copies need no crash recovery) and removed.
        self.assertEqual(stopped, [90])
        self.assertIn("honeypot_pool_template", removed)
        # The "ready" marker is created last and only after the data volume.
        self.assertEqual(created_volumes,
                         [self.mgr._template_volume_name(), self.mgr._template_marker_name()])

    def test_failed_build_leaves_no_ready_marker(self):
        created_volumes = []
        self.mgr.docker.volumes.create = lambda name, labels=None: created_volumes.append(name)

        def boom(*a, **k):
            raise RuntimeError("clone failed")
        self.mgr._run_helper = boom
        with self.assertRaises(RuntimeError):
            self.mgr._build_template_database()
        # Data volume was created, but the marker (freshness flag) never was.
        self.assertIn(self.mgr._template_volume_name(), created_volumes)
        self.assertNotIn(self.mgr._template_marker_name(), created_volumes)

    def test_ensure_template_builds_only_once_when_fresh(self):
        builds = []
        self.mgr._build_template_database = lambda: builds.append(True)
        self.mgr.ensure_template()                   # no volume -> builds
        self.assertEqual(len(builds), 1)
        self._template_present()                     # now a fresh one exists
        self.mgr.ensure_template()                   # -> no rebuild
        self.assertEqual(len(builds), 1)


class WordPressBase(TemplateBase):
    """WordPress layer: the template is a files + database volume pair, and a
    pool copies both and starts MySQL with its own DB password instead of
    re-running wp-cli."""

    def setUp(self):
        super().setUp()
        manager.MODE = "wordpress"
        self.mgr.host_paths.update({
            "/source_files": "/h/files", "/source_db": "/h/db", "/scripts": "/h/scripts"})

    def _template_present(self, age_seconds=10.0, admin=None):
        # The WordPress marker also records which decoy admin it was seeded with.
        marker = self.mgr._template_marker_name()
        if admin is None:
            admin = manager.Manager._decoy_admin_fingerprint()
        self.mgr.docker.volumes.list.return_value = [
            _fake_volume(marker, manager.time.time() - age_seconds,
                         **{"honeypot.template.admin": admin})]


class ProvisionWordPressWithTemplate(WordPressBase):
    def test_pool_copies_template_and_skips_wpcli(self):
        self._template_present()
        self.mgr.provision_wordpress(5)
        self.assertIn("copy template", self.helpers)
        self.assertIn("migrations", self.helpers)
        self.assertIn("content sync", self.helpers)        # catalog still freshened
        self.assertNotIn("WordPress seed", self.helpers)   # the ~50 s wp-cli install
        self.assertNotIn("seed volumes", self.helpers)
        self.assertEqual(self.registered, [5])
        # This pool's own unique DB password was stored for the router/sync.
        self.mgr.redis.set.assert_called_once()
        self.assertEqual(self.mgr.redis.set.call_args.args[0], manager.PW_PREFIX + "5")

    def test_falls_back_to_full_build_when_no_template(self):
        self.mgr.ensure_template = lambda: None            # build did not finish
        self.mgr.provision_wordpress(6)
        self.assertIn("seed volumes", self.helpers)
        self.assertIn("WordPress seed", self.helpers)
        self.assertIn("content sync", self.helpers)
        self.assertNotIn("copy template", self.helpers)
        self.assertEqual(self.registered, [6])

    def test_pool_database_gets_the_pools_own_password_never_productions(self):
        for template in (True, False):
            self.db_passwords.clear()
            if template:
                self._template_present()
            else:
                self.mgr.ensure_template = lambda: None
            self.mgr.provision_wordpress(7)
            stored = self.mgr.redis.set.call_args.args[1]
            self.assertEqual(len(self.db_passwords), 1)
            self.assertTrue(self.db_passwords[0] == stored, "pool DB not created with its own password")
            self.assertTrue(stored != "prod-pw", "pool uses production's password")

    def test_template_off_builds_from_scratch(self):
        manager.USE_TEMPLATE = False
        self._template_present()
        self.mgr.ensure_template = lambda: self.fail("template consulted with POOL_TEMPLATE=0")
        self.mgr.provision_wordpress(7)
        self.assertIn("WordPress seed", self.helpers)
        self.assertNotIn("copy template", self.helpers)


class DecoyAdminAccount(WordPressBase):
    """Pools are decoys: their admin password is HONEYPOT_WP_ADMIN_PASSWORD,
    never production's, and a template seeded with an older one is rebuilt."""

    def test_template_seeded_with_another_admin_is_stale(self):
        self._template_present(admin="0000000000000000")
        self.assertFalse(self.mgr._template_is_fresh())
        self._template_present()
        self.assertTrue(self.mgr._template_is_fresh())

    def test_template_without_admin_label_is_stale(self):
        marker = self.mgr._template_marker_name()
        self.mgr.docker.volumes.list.return_value = [
            _fake_volume(marker, manager.time.time() - 10)]
        self.assertFalse(self.mgr._template_is_fresh())

    def test_fingerprint_follows_the_decoy_password(self):
        with mock.patch.dict(os.environ, {"HONEYPOT_WP_ADMIN_PASSWORD": "one"}):
            a = manager.Manager._decoy_admin_fingerprint()
        with mock.patch.dict(os.environ, {"HONEYPOT_WP_ADMIN_PASSWORD": "two"}):
            b = manager.Manager._decoy_admin_fingerprint()
        self.assertNotEqual(a, b)
        self.assertNotIn("one", a)

    def test_wpcli_seed_gets_the_decoy_password_not_productions(self):
        runs = []
        self.mgr._run_helper = lambda *a, **k: runs.append(k)
        env = {"WP_ADMIN_PASSWORD": "production-secret",
               "HONEYPOT_WP_ADMIN_PASSWORD": "decoy-secret"}
        with mock.patch.dict(os.environ, env):
            self.mgr._wordpress_cli_seed("honeypot_database_9", "files", {}, "dbpw", "WordPress seed")
        self.assertEqual(runs[0]["environment"]["WP_ADMIN_PASSWORD"], "decoy-secret")


class BuildWordPressTemplate(WordPressBase):
    def test_ensure_template_dispatches_to_wordpress_builder(self):
        called = []
        self.mgr._build_template_wordpress = lambda: called.append(True)
        self.mgr._build_template_database = lambda: self.fail("database builder in wordpress mode")
        self.mgr.ensure_template()
        self.assertEqual(called, [True])

    def test_seeds_installs_once_and_shuts_down_cleanly(self):
        stopped, removed = [], []

        def fake_create(name, vol, pw, labels):
            c = mock.MagicMock()
            c.name = name
            c.stop = lambda timeout=None: stopped.append(timeout)
            c.remove = lambda force=False, v=False: removed.append(name)
            self.created.append((name, vol))
            return c
        self.mgr._create_database_container = fake_create
        created_volumes = []
        self.mgr.docker.volumes.create = lambda name, labels=None: created_volumes.append(name)
        self.mgr._build_template_wordpress()
        # The one-time seeding a full build would run, wp-cli install included...
        self.assertIn("seed volumes", self.helpers)
        self.assertIn("template WordPress seed", self.helpers)
        # ...but no per-pool steps (no password rotation to a pool, no content sync).
        self.assertNotIn("content sync", self.helpers)
        # Clean InnoDB shutdown so the copied data dir needs no crash recovery.
        self.assertEqual(stopped, [90])
        self.assertIn("honeypot_pool_template_db", removed)
        # Both data volumes created, then the "ready" marker last.
        self.assertEqual(created_volumes, [
            self.mgr._template_files_volume_name(), self.mgr._template_db_volume_name(),
            self.mgr._template_marker_name()])

    def test_failed_build_leaves_no_ready_marker(self):
        created_volumes = []
        self.mgr.docker.volumes.create = lambda name, labels=None: created_volumes.append(name)
        calls = []

        def run(*a, **k):
            calls.append(k.get("what"))
            if k.get("what") == "template WordPress seed":
                raise RuntimeError("wp-cli failed")
        self.mgr._run_helper = run
        with self.assertRaises(RuntimeError):
            self.mgr._build_template_wordpress()
        self.assertNotIn(self.mgr._template_marker_name(), created_volumes)


if __name__ == "__main__":
    unittest.main()
