"""Unit tests for core.wp_studio (Qt-free)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import wp_studio  # noqa: E402


class _FakeTarget:
    """Records the compose args wp_studio.sync_argv forwards to Target.build."""

    def __init__(self):
        self.calls: list[tuple] = []

    def build(self, *compose_args):
        self.calls.append(compose_args)
        return (["docker", "compose", *compose_args], "/edge")


class StudioUrlTests(unittest.TestCase):
    def test_bare_host_gets_https_and_wp_admin(self):
        self.assertEqual(wp_studio.studio_url("shop.example"), "https://shop.example/wp-admin/")

    def test_trailing_slash_and_whitespace_trimmed(self):
        self.assertEqual(wp_studio.studio_url("  shop.example/  "), "https://shop.example/wp-admin/")

    def test_full_url_is_tolerated(self):
        self.assertEqual(wp_studio.studio_url("http://10.0.0.5:8080"), "http://10.0.0.5:8080/wp-admin/")


class StudioHeadersTests(unittest.TestCase):
    def test_backend_header_always_sent(self):
        h = wp_studio.studio_headers("s3cret")
        self.assertEqual(h[wp_studio.STUDIO_BACKEND_HEADER], wp_studio.STUDIO_BACKEND_VALUE)
        self.assertEqual(h[wp_studio.INTERNAL_TEST_HEADER], "s3cret")

    def test_no_secret_omits_auth_header(self):
        for secret in (None, "", "   "):
            h = wp_studio.studio_headers(secret)
            self.assertIn(wp_studio.STUDIO_BACKEND_HEADER, h)
            self.assertNotIn(wp_studio.INTERNAL_TEST_HEADER, h)

    def test_secret_is_stripped(self):
        self.assertEqual(wp_studio.studio_headers("  tok  ")[wp_studio.INTERNAL_TEST_HEADER], "tok")


class ReadyPoolsTests(unittest.TestCase):
    def setUp(self):
        from core import redis_inspect
        self._ri = redis_inspect
        self._orig = redis_inspect.pool_state

    def tearDown(self):
        self._ri.pool_state = self._orig

    def test_uses_ready_pools_sorted_and_deduped(self):
        self._ri.pool_state = lambda remote, timeout=10.0: {"ready": ["3", "1", "2", "1"]}
        self.assertEqual(wp_studio.ready_pools(None), [1, 2, 3])

    def test_falls_back_to_static_pools_when_none_ready(self):
        self._ri.pool_state = lambda remote, timeout=10.0: {"ready": []}
        self.assertEqual(wp_studio.ready_pools(None), [1, 2, 3])

    def test_falls_back_when_redis_raises(self):
        def boom(remote, timeout=10.0):
            raise RuntimeError("no redis")
        self._ri.pool_state = boom
        self.assertEqual(wp_studio.ready_pools(None), [1, 2, 3])

    def test_ignores_bogus_pool_numbers(self):
        self._ri.pool_state = lambda remote, timeout=10.0: {"ready": ["0", "-1", "5", "2"]}
        self.assertEqual(wp_studio.ready_pools(None), [2, 5])


class PropagationStepsTests(unittest.TestCase):
    def test_one_step_per_pool_in_order(self):
        steps = wp_studio.propagation_steps([2, 5])
        self.assertEqual([(s.pool, s.label) for s in steps],
                         [(2, "Honeypot pool 2"), (5, "Honeypot pool 5")])


class SyncArgvTests(unittest.TestCase):
    def test_builds_once_exec_for_the_pool(self):
        target = _FakeTarget()
        argv, cwd = wp_studio.sync_argv(target, 2)
        self.assertEqual(cwd, "/edge")
        self.assertEqual(
            target.calls[0],
            ("exec", "-T", "honeypot_content_sync", "bash",
             "/replicate_content_to_honeypot.sh", "--once", "2"),
        )
        # The pool number is stringified and the script path is the mounted one.
        self.assertIn("--once", argv)
        self.assertEqual(argv[argv.index("--once") + 1], "2")


class PolicyConstantTests(unittest.TestCase):
    def test_propagation_lists_are_non_empty(self):
        self.assertTrue(wp_studio.PROPAGATES)
        self.assertTrue(wp_studio.NEVER_PROPAGATES)

    def test_secrets_are_on_the_never_list(self):
        joined = " ".join(wp_studio.NEVER_PROPAGATES).lower()
        for term in ("password", "api key", "secret", "token"):
            self.assertIn(term, joined)


if __name__ == "__main__":
    unittest.main()
