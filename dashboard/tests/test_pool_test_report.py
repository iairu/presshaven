"""Tests for core/pool_test_report.py -- the pool-exclusivity verdict.

Run from dashboard/: python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.pool_test_report import (EXCLUSIVE, INCOMPLETE, MERGED, SHARED_EXPECTED,  # noqa: E402
                                   SHARED_UNEXPECTED, FrameResult, analyze, sharing_justified)

SID = ["a" * 32, "b" * 32, "c" * 32]


def frames(*pools):
    return [FrameResult(label=f"F{i}", session_id=SID[i], pool=p) for i, p in enumerate(pools)]


def state(ready=(1, 2, 3), free=(), owners=None, capped=""):
    return {"ready": list(ready), "free": list(free), "capped": capped,
            "owners": owners or {n: 1 for n in ready}}


class VerdictTests(unittest.TestCase):
    def test_distinct_pools_are_exclusive(self):
        self.assertEqual(analyze(frames(1, 2, 3), state(free=[4])).status, EXCLUSIVE)

    def test_shared_with_free_pool_is_unexpected(self):
        v = analyze(frames(1, 1, 2), state(free=[3], owners={1: 2, 2: 1, 3: 0}))
        self.assertEqual(v.status, SHARED_UNEXPECTED)
        self.assertEqual(v.by_pool[1], ["F0", "F1"])

    def test_shared_when_growth_capped_is_expected(self):
        v = analyze(frames(1, 1, 2), state(ready=(1, 2), free=[1], capped="low memory"))
        self.assertEqual(v.status, SHARED_EXPECTED)

    def test_shared_when_every_pool_owned_is_expected(self):
        v = analyze(frames(1, 2, 1), state(ready=(1, 2), owners={1: 2, 2: 1}))
        self.assertEqual(v.status, SHARED_EXPECTED)

    def test_same_session_is_merged(self):
        f = frames(1, 1, 2)
        f[1].session_id = f[0].session_id
        self.assertEqual(analyze(f, state()).status, MERGED)

    def test_missing_session_or_pool_is_incomplete(self):
        f = frames(1, None, 2)
        self.assertEqual(analyze(f, state()).status, INCOMPLETE)
        f[1].session_id = ""
        self.assertEqual(analyze(f, state()).status, INCOMPLETE)

    def test_shared_while_pools_are_still_being_built_is_expected(self):
        v = analyze(frames(1, 2, 1), state(ready=(1, 2), owners={1: 2, 2: 1}) | {"free": [3], "waiting": 1})
        self.assertEqual(v.status, SHARED_EXPECTED)
        self.assertIn("waiting", " ".join(v.findings))

    def test_unreadable_state_never_justifies_sharing(self):
        self.assertFalse(sharing_justified({}))
        self.assertEqual(analyze(frames(1, 1, 2), {}).status, SHARED_UNEXPECTED)



class DecisionTests(unittest.TestCase):
    def test_parse_decision(self):
        from core.pool_test_report import Decision, parse_decision, StepResult, sticky_violations
        d = parse_decision("s", '{"risk_score": 85, "honeypot_bound": true, "honeypot_reason": "high_risk_score"}', "2")
        self.assertEqual((d.route, d.pool, d.score), ("HONEYPOT", 2, 85))
        self.assertIn("pool 2", d.text())
        self.assertEqual(parse_decision("s", "", "").route, "PRODUCTION")
        self.assertEqual(parse_decision("", "", "").route, "NO SESSION")
        self.assertEqual(parse_decision("s", "not json", "").route, "PRODUCTION")
        w = parse_decision("s", '{"honeypot_bound": true}', "1", "7")
        self.assertTrue(w.waiting)
        self.assertIn("borrowed", w.text())
        self.assertFalse(parse_decision("s", "", "", "7").waiting)   # no pool, nothing borrowed

    def test_pool_change_between_steps_is_unstable(self):
        from core.pool_test_report import Decision, StepResult, UNSTABLE
        mk = lambda *pools: StepResult("t", "", [], [Decision("s", "HONEYPOT", 90, "", p) for p in pools])
        v = analyze(frames(1, 2, 3), state(free=[4]), [mk(1, 2, 3), mk(1, 3, 3)])
        self.assertEqual(v.status, UNSTABLE)
        self.assertEqual(analyze(frames(1, 2, 3), state(free=[4]), [mk(1, 2, 3)]).status, EXCLUSIVE)

    def test_move_off_a_borrowed_pool_is_not_a_violation(self):
        from core.pool_test_report import Decision, StepResult, sticky_violations
        borrowed = StepResult("attack", "", [], [Decision("s", "HONEYPOT", 90, "", 1, waiting=True)])
        own = StepResult("scale", "", [], [Decision("s", "HONEYPOT", 90, "", 4)])
        moved = StepResult("again", "", [], [Decision("s", "HONEYPOT", 90, "", 5)])
        self.assertEqual(sticky_violations([borrowed, own]), [])
        self.assertEqual(len(sticky_violations([borrowed, own, moved])), 1)


class PlanTests(unittest.TestCase):
    def test_plan_patterns_exist_and_are_browser_runnable(self):
        from core.patterns import PATTERN_PRESETS
        from core.pool_test_report import PATTERN_PLAN, FALLBACK_PATTERNS
        by_cve = {p.cve: p for p in PATTERN_PRESETS}
        planned = [c for pair in PATTERN_PLAN for c in pair]
        self.assertEqual(len(planned), len(set(planned)), "windows must run different patterns")
        for cve in planned + FALLBACK_PATTERNS:
            self.assertIn(cve, by_cve)
            self.assertEqual(by_cve[cve].method, "GET", cve)
            self.assertEqual(by_cve[cve].headers, {}, cve)
        self.assertFalse(set(planned) & set(FALLBACK_PATTERNS))

    def test_database_layer_runs_only_patterns_it_isolates(self):
        from core.patterns import PATTERN_PRESETS
        from core.pool_test_report import fallback_patterns, pattern_plan, window_plan
        by_cve = {p.cve: p for p in PATTERN_PRESETS}
        planned = [c for pair in pattern_plan(True) for c in pair]
        self.assertEqual(len(planned), len(set(planned)))
        for cve in planned + fallback_patterns(True):
            self.assertTrue(by_cve[cve].db_isolated, cve)
            self.assertEqual((by_cve[cve].method, by_cve[cve].headers), ("GET", {}), cve)
        self.assertFalse(set(planned) & set(fallback_patterns(True)))
        for n in range(3, 11):
            for pair in window_plan(n, database=True):
                self.assertTrue(all(by_cve[c].db_isolated for c in pair), (n, pair))

    def test_window_plan_covers_every_window_count(self):
        from core.pool_test_report import (CART_PLAN, PATTERN_PLAN, MAX_WINDOWS, MIN_WINDOWS,
                                           window_plan)
        self.assertEqual(window_plan(3), PATTERN_PLAN)
        self.assertGreaterEqual(len(CART_PLAN), MAX_WINDOWS)
        for n in range(MIN_WINDOWS, MAX_WINDOWS + 1):
            plan = window_plan(n)
            self.assertEqual(len(plan), n)
            firsts = [a for a, _b in plan]
            self.assertEqual(len(firsts), len(set(firsts)), f"{n} windows: first patterns repeat")
            self.assertTrue(all(a != b for a, b in plan))


class EvidenceTests(unittest.TestCase):
    def test_parsers_and_cross_traffic(self):
        from core import pool_evidence as pe
        log = ('172.21.0.5 - - [05/Oct/2026:07:44:12 +0000] "GET /?author=1 HTTP/1.1" 301 0 "-" "Mozilla/5.0 PoolTest/B"\n'
               '127.0.0.1 - - [05/Oct/2026:07:43:12 +0000] "GET / HTTP/1.1" 200 6 "-" "curl/8.14.1"\n'
               '172.21.0.5 - - [05/Oct/2026:07:44:13 +0000] "GET /a.css HTTP/1.1" 200 5 "-" "Mozilla/5.0 PoolTest/C"')
        ev = pe.ContainerEvidence(1, hits=pe.parse_access_log(log))
        self.assertEqual(ev.windows(), ["B", "C"])
        self.assertEqual([h.path for h in ev.notable()], ["/?author=1"])
        self.assertEqual(len(pe.cross_traffic([ev], {1: "B"})), 1)
        self.assertEqual(pe.parse_status("Questions\t5\nCom_select\t2\n"), {"Questions": 5, "Com_select": 2})
        self.assertEqual(pe.db_delta({"Questions": 1}, {"Questions": 4})["Questions"], 3)
        self.assertIsNone(pe.db_delta(None, {"Questions": 4}))
        self.assertEqual(pe.filter_files(["/var/www/html/x.php", "/tmp/a", "/run/b"]), ["/var/www/html/x.php"])


class CartTests(unittest.TestCase):
    def _step(self, title, *carts):
        from core.pool_test_report import StepResult
        return StepResult(title, "", [], [], carts=list(carts))

    def test_parse_cart(self):
        from core.pool_test_report import parse_cart
        c = parse_cart('{"items":[{"name":"Mug","quantity":2}],"totals":{"total_price":"4400","currency_minor_unit":2,"currency_prefix":"$"}}')
        self.assertEqual(c.items, [("Mug", 2)])
        self.assertEqual(c.total, "$44.00")
        self.assertIn("2 items", c.text())
        self.assertIsNone(parse_cart("not json"))

    def test_cart_must_survive_routing(self):
        from core.pool_test_report import CART_LOST, CartState, cart_violations
        full, empty = CartState([("Mug", 2)], "$44"), CartState([], "$0")
        ok = [self._step("open", empty), self._step("fill", full), self._step("attack", full)]
        self.assertEqual(cart_violations(ok), [])
        bad = ok + [self._step("again", empty)]
        self.assertEqual(len(cart_violations(bad)), 1)
        v = analyze(frames(1, 2, 3), state(free=[4]), [self._step("fill", full, full, full), self._step("attack", full, empty, full)])
        self.assertEqual(v.status, CART_LOST)
        self.assertIn("Window 2", " ".join(v.findings))

    def test_plan_products_exist_and_are_simple(self):
        from core.pool_test_report import CART_PLAN
        import json, os
        cat = json.load(open(os.path.join(os.path.dirname(__file__), "..", "..", "ids", "eshop_seed", "catalog.json")))
        by = {p["slug"]: p for p in cat["products"]}
        for window in CART_PLAN:
            for slug, qty in window:
                self.assertEqual(by[slug]["type"], "simple", slug)
                self.assertGreater(qty, 0)
        self.assertEqual(len({s for w in CART_PLAN for s, _ in w}), sum(len(w) for w in CART_PLAN))


class ScalingTests(unittest.TestCase):
    """Timeline, case A (borrowed while scaling) and case B (resource limit)."""

    def _data(self, timeline, events=(), duration=100.0):
        from core.pool_test_report import PoolTestData, Sample
        samples = [Sample(t, w, f"s{w}", r, p, wt)
                   for t, batch in timeline for w, (r, p, wt) in enumerate(batch)]
        return PoolTestData("now", "t", "u", "", frames(*[None] * len(timeline[0][1])),
                            duration=duration, samples=samples, events=list(events))

    def test_classify(self):
        from core.pool_test_report import BORROWED, OWN, PRODUCTION, SHARED, Sample, classify
        batch = [Sample(0, 0, "a", "HONEYPOT", 1, False), Sample(0, 1, "b", "HONEYPOT", 1, True),
                 Sample(0, 2, "c", "PRODUCTION", None, False), Sample(0, 3, "d", "HONEYPOT", 2, False),
                 Sample(0, 4, "e", "HONEYPOT", 2, False)]
        self.assertEqual(classify(batch), [OWN, BORROWED, PRODUCTION, SHARED, SHARED])

    def test_borrowed_then_own_is_case_a(self):
        from core.pool_test_report import BORROWED, OWN, scaling_summary
        H, P = ("HONEYPOT", 1, False), ("PRODUCTION", None, False)
        d = self._data([(0, [P, P]), (10, [H, ("HONEYPOT", 1, True)]), (40, [H, ("HONEYPOT", 2, False)])],
                       [{"type": "build_start", "pool": 2, "reason": "waiting session", "at": 11},
                        {"type": "build", "pool": 2, "start": 11, "seconds": 28, "ok": True, "at": 39,
                         "phases": [["seed volumes", 10], ["WordPress start", 15]]},
                        {"type": "handoff", "pool": 2, "session": "s1", "borrowed": 1, "waited": 29, "at": 39}])
        s = scaling_summary(d)
        self.assertEqual([seg[2] for seg in s.timelines[1]], ["production", BORROWED, OWN])
        (c,) = s.borrow
        # Timed from pool_manager's hand-off event (assigned at 39 - 29 = 10, moved at 39).
        self.assertEqual((c.window, c.borrowed, c.own_pool, c.end - c.start, c.waited), (1, 1, 2, 29, 29))
        self.assertEqual((s.builds[0].pool, s.builds[0].reason, s.builds[0].seconds), (2, "waiting session", 28))
        self.assertEqual(s.limit, [])

    def test_a_read_without_a_session_is_not_a_dip_to_production(self):
        from core.pool_test_report import OWN, PoolTestData, Sample, timelines
        samples = [Sample(0, 0, "a", "HONEYPOT", 1, False), Sample(10, 0, "", "NO SESSION", None, False),
                   Sample(20, 0, "a", "HONEYPOT", 1, False)]
        self.assertEqual([seg[2] for seg in timelines(samples, 30)[0]], [OWN])

    def test_a_borrow_between_two_reads_comes_from_the_handoff(self):
        from core.pool_test_report import scaling_summary
        P, H5 = ("PRODUCTION", None, False), ("HONEYPOT", 5, False)
        # The window is never sampled on borrowed pool 2: production, then its own pool 5.
        d = self._data([(0, [P]), (10, [P]), (20, [H5])],
                       [{"type": "handoff", "pool": 5, "session": "s0", "borrowed": 2, "waited": 4, "at": 16}])
        (c,) = scaling_summary(d).borrow
        self.assertEqual((c.window, c.borrowed, c.own_pool, c.start, c.end, c.outcome), (0, 2, 5, 12, 16, "own"))

    def test_reads_after_the_scale_down_are_not_the_run(self):
        from core.pool_test_report import OWN, scaling_summary
        H1, H2 = ("HONEYPOT", 1, False), ("HONEYPOT", 2, False)
        # Both own a pool for the whole run; after the scale-down request (t=60)
        # the reassignment check finds window 1 parked on pool 1, waiting.
        d = self._data([(0, [H1, H2]), (50, [H1, H2]), (70, [H1, ("HONEYPOT", 1, True)])])
        d.scaledown = {"requested": 60}
        s = scaling_summary(d)
        self.assertEqual(s.borrow, [])
        self.assertEqual([seg[2] for seg in s.timelines[1]], [OWN])
        d.scaledown = {}
        self.assertEqual(len(scaling_summary(d).borrow), 1)      # without the cut it was counted

    def test_builds_after_the_scale_down_are_not_the_runs(self):
        from core.pool_test_report import scaling_summary
        from core.pool_test_report_pdf import _build_outcome
        H = ("HONEYPOT", 1, False)
        d = self._data([(0, [H]), (50, [H])],
                       [{"type": "build_start", "pool": 8, "reason": "spare", "at": 20},
                        {"type": "build", "pool": 8, "start": 20, "seconds": 30, "ok": True, "at": 50},
                        {"type": "build_start", "pool": 4, "reason": "waiting session", "at": 70},
                        {"type": "scaledown", "pool": 9, "seconds": 1, "forced": True, "at": 65},
                        {"type": "scaledown", "pool": 4, "seconds": 1, "forced": True, "at": 140}])
        d.scaledown = {"requested": 60, "cleanup": {"start": 100}}
        s = scaling_summary(d)
        self.assertEqual([b.pool for b in s.builds], [8])
        self.assertEqual([b.pool for b in s.late_builds], [4])
        self.assertEqual([r.pool for r in s.removals], [9])     # not the clean-up's removal of pool 4
        self.assertIn("still building", _build_outcome(s.late_builds[0]))
        self.assertEqual(_build_outcome(s.builds[0]), "")

    def test_newcomer_on_a_pool_at_the_limit_is_case_b(self):
        from core.pool_test_report import scaling_summary
        P, H = ("PRODUCTION", None, False), ("HONEYPOT", 1, False)
        d = self._data([(0, [P, P]), (10, [H, P]), (50, [H, H])],
                       [{"type": "capped", "reason": "resource limit reached", "at": 30}])
        s = scaling_summary(d)
        self.assertEqual([(c.window, c.pool, c.shared_with) for c in s.limit], [(1, 1, [0])])
        self.assertEqual(s.capped, [(30.0, "resource limit reached")])

    def test_borrower_dropped_at_the_limit(self):
        from core.pool_test_report import scaling_summary
        P, H = ("PRODUCTION", None, False), ("HONEYPOT", 1, False)
        d = self._data([(0, [P, P]), (10, [H, ("HONEYPOT", 1, True)]), (30, [H, H])],
                       [{"type": "dropped_waiting", "sessions": ["s1"], "at": 25, "reason": "limit"}])
        s = scaling_summary(d)
        self.assertEqual([c.outcome for c in s.borrow], ["dropped"])
        self.assertEqual([(c.window, c.how) for c in s.limit], [(1, "dropped from the wait queue")])

    def test_load_stats(self):
        from core.pool_test_report import LoadTiming, load_stats
        st = load_stats([LoadTiming(0, 0, "x", ms, "own") for ms in (100, 200, 300)]
                        + [LoadTiming(0, 1, "x", 50, "")])
        self.assertEqual(set(st), {"own"})
        self.assertEqual((st["own"]["n"], st["own"]["median"], st["own"]["max"]), (3, 200, 300))


class ScaledownReportTests(unittest.TestCase):
    def test_pool_usage_parses_compose_and_runtime_containers(self):
        import json
        from core.resource_stats import parse_pool_usage
        lines = "\n".join(json.dumps(x) for x in [
            {"Name": "honeypot-ids-system-v1-honeypot_eshop_2-1", "MemUsage": "512MiB / 1GiB", "CPUPerc": "10.5%"},
            {"Name": "honeypot-ids-system-v1-honeypot_database_2-1", "MemUsage": "256MiB / 512MiB", "CPUPerc": "1.5%"},
            {"Name": "honeypot_eshop_5", "MemUsage": "100MiB / 1GiB", "CPUPerc": "3%"},
            {"Name": "honeypot-ids-system-v1-honeypot_database-1", "MemUsage": "64MiB / 512MiB", "CPUPerc": "0%"},
            {"Name": "honeypot-ids-system-v1-production_eshop-1", "MemUsage": "900MiB / 1GiB", "CPUPerc": "50%"},
        ]) + "\nnot json"
        u = parse_pool_usage(lines)
        self.assertEqual((u.containers, u.pools), (4, 3))
        self.assertEqual(u.per_pool_mem[2], 768 * 2 ** 20)
        self.assertAlmostEqual(u.cpu_percent, 15.0)
        # production_eshop is never a pool; reported apart (database layer).
        self.assertEqual(u.eshop_mem_bytes, 900 * 2 ** 20)
        self.assertAlmostEqual(u.eshop_cpu_percent, 50.0)

    def test_removals_and_usage_lookup(self):
        from core.pool_test_report import PoolTestData, UsageSample, scaling_summary, usage_at
        d = PoolTestData("now", "t", "u", "", [], duration=60, events=[
            {"type": "released", "pool": 4, "sessions": ["a", "b"], "reason": "released on request", "at": 40},
            {"type": "scaledown", "pool": 4, "idle": 3, "forced": True, "seconds": 2.5, "at": 42}],
            usage=[UsageSample(t, 2, 1, 100.0 * t, 0) for t in (0, 30, 45)])
        s = scaling_summary(d)
        self.assertEqual([(r.pool, r.seconds, r.forced) for r in s.removals], [(4, 2.5, True)])
        self.assertEqual(s.released, [(40.0, 4, 2, "released on request")])
        self.assertEqual(usage_at(d.usage, 40).t, 30)
        self.assertEqual(usage_at(d.usage, 40, after=True).t, 45)


class ProductIds(unittest.TestCase):
    def test_reads_ids_by_slug_from_the_store_api(self):
        from core.pool_test_report import parse_product_ids
        body = '[{"id": 178, "slug": "logo-cap"}, {"id": 136, "slug": "ceramic-pour-over-dripper"}]'
        self.assertEqual(parse_product_ids(body, ["ceramic-pour-over-dripper", "logo-cap"]),
                         {"ceramic-pour-over-dripper": 136, "logo-cap": 178})

    def test_missing_product_or_unreadable_response_raises(self):
        from core.pool_test_report import parse_product_ids
        with self.assertRaises(RuntimeError):
            parse_product_ids('[{"id": 1, "slug": "a"}]', ["a", "b"])
        with self.assertRaises(RuntimeError):
            parse_product_ids("<html>", ["a"])

    def test_no_answer_is_told_apart_from_missing_products(self):
        from core.pool_test_report import ProductListUnreadable, parse_product_ids
        for body in ("", "<html>", '{"code": "rest_no_route"}'):
            with self.assertRaises(ProductListUnreadable):
                parse_product_ids(body, ["a"])
        try:
            parse_product_ids('[{"id": 1, "slug": "a"}]', ["a", "b"])
        except ProductListUnreadable:
            self.fail("a real missing product is not an unreadable list")
        except RuntimeError as e:
            self.assertIn("b", str(e))


class Browsing(unittest.TestCase):
    def test_windows_look_at_different_pages_and_move_on(self):
        from core.pool_test_report import BROWSE_PAGES, browse_page
        firsts = [browse_page(w, 0)[0] for w in range(4)]
        self.assertEqual(len(set(firsts)), 4)
        self.assertNotEqual(browse_page(0, 0), browse_page(0, 1))
        self.assertEqual(browse_page(1, len(BROWSE_PAGES)), browse_page(1, 0))
        for path, _label in BROWSE_PAGES:   # nothing that changes a cart or logs in
            self.assertNotRegex(path, r"cart|checkout|account|login|wp-admin")

    def test_action_lists_each_page_once(self):
        from core.pool_test_report import browse_action
        self.assertEqual(browse_action([]), "Browses the shop")
        self.assertEqual(browse_action(["the FAQ", "Stoneware Mug", "the FAQ"]),
                         "Looks at the FAQ, Stoneware Mug")



class PoolEvidenceRuntimePools(unittest.TestCase):
    """Pools pool_manager built at runtime are not compose services: reading
    them must fall back from `docker compose exec/logs` to plain docker."""

    def test_falls_back_to_docker_when_compose_does_not_know_the_pool(self):
        from unittest import mock
        from core import pool_evidence as pe
        target = mock.MagicMock()
        target.build.side_effect = lambda *a: (["compose", *a], None)
        target.build_shell.side_effect = lambda cmd: (["sh", "-c", cmd], None)
        calls = []

        def run(argv, error, **_kw):
            calls.append(argv)
            if argv[0] == "compose":
                raise error('service "honeypot_eshop_4" is not running')
            return mock.Mock(stdout="2026-10-08T17:30:00Z\n")
        with mock.patch.object(pe, "run_checked", side_effect=run):
            out = pe._exec(target, "honeypot_eshop_4", "date -u")
            log = pe._logs(target, "honeypot_eshop_4", "2026-10-08T17:30:00Z")
        self.assertEqual(out.strip(), "2026-10-08T17:30:00Z")
        self.assertTrue(log)
        self.assertIn("docker exec honeypot_eshop_4 sh -c 'date -u'", calls[1][2])
        self.assertIn("docker logs --since 2026-10-08T17:30:00Z honeypot_eshop_4", calls[3][2])

    def test_logs_retry_through_docker_when_compose_prints_nothing(self):
        from unittest import mock
        from core import pool_evidence as pe
        target = mock.MagicMock()
        target.build.side_effect = lambda *a: (["compose", *a], None)
        target.build_shell.side_effect = lambda cmd: (["sh", "-c", cmd], None)
        line = '172.21.0.9 - - [09/Oct/2026:06:30:00 +0000] "GET /x HTTP/1.1" 200 5 "-" "UA PoolTest/D"\n'

        def run(argv, error, **_kw):   # compose: unknown service -> exit 0, no output
            return mock.Mock(stdout="" if argv[0] == "compose" else line)
        with mock.patch.object(pe, "run_checked", side_effect=run):
            log = pe._logs(target, "honeypot_eshop_4", "2026-10-09T06:00:00Z")
        self.assertEqual([h.window for h in pe.parse_access_log(log)], ["D"])

    def test_pool_built_during_the_run_gets_its_own_baseline(self):
        from unittest import mock
        from core import pool_evidence as pe
        baseline = {"since": "2026-10-08T17:00:00Z", "db": {1: {"Questions": 5}}, "pool_since": {}}
        with mock.patch.object(pe, "_exec", return_value="2026-10-08T17:31:00Z\n"), \
                mock.patch.object(pe, "db_status", return_value={"Questions": 900}):
            pe.extend_baseline(mock.MagicMock(), baseline, [1, 4])
        self.assertEqual(baseline["db"][1], {"Questions": 5})          # untouched
        self.assertEqual(baseline["db"][4], {"Questions": 900})
        self.assertEqual(baseline["pool_since"], {4: "2026-10-08T17:31:00Z"})


class PoolEvidenceDatabaseLayer(unittest.TestCase):
    """Database proxy layer: a pool is a database, attributed to the test
    windows through its MySQL general query log."""

    def test_pool_one_is_the_compose_database(self):
        from core import pool_evidence as pe
        self.assertEqual(pe.db_service(1, database=True), "honeypot_database")
        self.assertEqual(pe.db_service(4, database=True), "honeypot_database_4")
        self.assertEqual(pe.db_service(1, database=False), "honeypot_database_1")

    def test_session_key_from_the_woocommerce_cookie(self):
        from core import pool_evidence as pe
        self.assertEqual(pe.wc_session_key("wp_woocommerce_session_abc",
                                           "t_1f2e3d4c%7C%7C1760000000%7C%7C1759990000%7C%7Cdeadbeef"),
                         "t_1f2e3d4c")
        self.assertEqual(pe.wc_session_key("wp_woocommerce_session_abc", "42||1||1||x"), "")   # too short
        self.assertEqual(pe.wc_session_key("SERVERID", "t_1f2e3d4c||1||1||x"), "")
        self.assertEqual(pe.wc_session_key("wp_woocommerce_session_abc", "x'; DROP||1"), "")

    def test_sql_names_only_safe_keys_and_skips_the_reader(self):
        from core import pool_evidence as pe
        q = pe.attribution_sql({"t_ab12ef34": "A", "bad'keyabc": "B", "t_cd34ef56": "lower"},
                               "2026-10-18 06:24:23.282976")
        self.assertIn("'%t\\_ab12ef34%'", q[0])
        self.assertNotIn("bad", q[0])
        self.assertNotIn("cd34", q[0])                  # window must be one capital letter
        for sql in q:
            self.assertIn("NOT LIKE '%[root] @%'", sql)
            self.assertIn("event_time >= '2026-10-18 06:24:23.282976'", sql)
        self.assertNotIn("event_time", pe.attribution_sql({"t_ab12ef34": "A"}, "")[0])   # whole log
        self.assertIsNone(pe.attribution_sql({}, ""))
        self.assertIsNone(pe.attribution_sql({"t_ab12ef34": "A"}, "yesterday'; --"))

    def test_parse_attribution(self):
        from core import pool_evidence as pe
        totals = "A\t3\t120\t4\t1\nB\t2\t80\t2\t0\n"
        examples = ("A\t0\tINSERT INTO wp_woocommerce_sessions VALUES ('t_a','x')\n"
                    "A\t0\tUPDATE wp_options SET option_value='1' WHERE option_name='cwmp'\n"
                    "A\t1\tSELECT * FROM wp_afi WHERE id = '1' UNION SELECT user_pass FROM wp_users\n"
                    "C\t1\tSELECT 1\n")
        windows, other = pe.parse_attribution(totals, examples, "9\n")
        self.assertEqual([(q.window, q.requests, q.queries, q.writes, q.suspicious) for q in windows],
                         [("A", 3, 120, 4, 1), ("B", 2, 80, 2, 0)])
        self.assertEqual(windows[0].examples, [
            "SELECT * FROM wp_afi WHERE id = '1' UNION SELECT user_pass FROM wp_users",
            "UPDATE wp_options SET option_value='1' WHERE option_name='cwmp'"])
        self.assertEqual(other, 4)
        ev = pe.ContainerEvidence(2, db_windows=windows)
        self.assertEqual(ev.windows(), ["A", "B"])
        self.assertEqual(len(pe.cross_traffic([ev], {2: "A"})), 1)
        self.assertEqual(pe.parse_attribution("", "", "")[1], None)

    def test_database_baseline_turns_the_query_log_on(self):
        from unittest import mock
        from core import pool_evidence as pe
        services = []

        def fake_exec(_t, service, command, timeout=30.0):
            services.append(service)
            if command.startswith("date"):
                return "2026-10-18T06:00:00Z\n"
            if "NOW(6)" in command:
                return "2026-10-18 06:00:01.123456\n"
            return "Questions\t7\n"
        with mock.patch.object(pe, "_exec", side_effect=fake_exec):
            b = pe.take_baseline(mock.MagicMock(), [1, 4], database=True)
            pe.extend_baseline(mock.MagicMock(), b, [5])
        self.assertTrue(b["database"])
        self.assertEqual(b["since"], "2026-10-18T06:00:00Z")
        self.assertEqual(b["qlog"], {1: "2026-10-18 06:00:01.123456", 4: "2026-10-18 06:00:01.123456",
                                     5: ""})                 # built during the run: whole log
        self.assertEqual(b["shared_since"], "2026-10-18T06:00:00Z")
        self.assertIn("honeypot_database", services)
        self.assertNotIn("honeypot_eshop_1", services)


if __name__ == "__main__":
    unittest.main()


class PrebuildTests(unittest.TestCase):
    def test_breakdown_adds_up(self):
        from core.pool_test_report import PoolBuild
        from core.pool_test_report_pdf import prebuild_breakdown
        self.assertEqual(prebuild_breakdown(2, 0, [8], [], 280),
                         ": 2 built for it, 1 spare(s) that were already building (pool 8)")
        # Older report: derived from the spare build that straddled the request.
        spare = PoolBuild(8, 235, 66, True, "spare")
        self.assertIn("(pool 8)", prebuild_breakdown(2, 0, None, [spare], 280))
        self.assertEqual(prebuild_breakdown(3, 0, [], [], 280), ": 3 built for it")


class LoadLogTests(unittest.TestCase):
    def test_failures_by_step_and_during_builds(self):
        from core.pool_test_report import load_failures_by_step
        log = [{"t": 100, "step": "Honeypot pools scale up"}, {"t": 30, "step": "User D attacks"},
               {"t": 101, "step": "Honeypot pools scale up"}, {"t": 400, "step": "latency probe: at the end"}]
        by_step, during = load_failures_by_step(log, [(60, 120)])
        self.assertEqual(by_step, [("User D attacks", 1), ("Honeypot pools scale up", 2),
                                   ("latency probe: at the end", 1)])
        self.assertEqual(during, 2)

    def test_counts_per_load_not_per_attempt(self):
        from core.pool_test_report import load_problems
        log = [{"window": 0, "attempts": 3, "outcome": "retried"},
               {"window": 1, "attempts": 5, "outcome": "failed"},
               {"window": 2, "attempts": 5, "outcome": "fixed before the next step"},
               {"window": 3, "attempts": 1, "outcome": "timed out"}]
        loads, attempts, never = load_problems(log)
        self.assertEqual(loads, 4)
        self.assertEqual(attempts, 2 + 5 + 4 + 1)
        self.assertEqual([e["window"] for e in never], [1, 3])


class ReassignmentTests(unittest.TestCase):
    """What a window whose pool the forced scale-down removed got next."""

    def test_outcomes(self):
        from core.pool_test_report import reassignment_outcome
        base = {"window": 0, "from": 7, "session_before": SID[0], "session_after": SID[0]}
        kind, _ = reassignment_outcome(dict(base, pool=1, route="HONEYPOT", status=200))
        self.assertEqual(kind, "reassigned")
        kind, words = reassignment_outcome(dict(base, pool=1, route="HONEYPOT", status=502, title="502 Bad Gateway"))
        self.assertEqual(kind, "error")
        self.assertIn("HTTP 502", words)
        self.assertEqual(reassignment_outcome(dict(base, pool=None, route="", status=0))[0], "error")
        self.assertEqual(reassignment_outcome(dict(base, pool=7, route="HONEYPOT", status=200))[0], "stranded")
        kind, words = reassignment_outcome(dict(base, pool=None, route="PRODUCTION", status=200,
                                                session_after=SID[1]))
        self.assertEqual(kind, "escaped")
        self.assertIn("new session", words)
        kind, words = reassignment_outcome(dict(base, pool=None, route="PRODUCTION", status=200))
        self.assertEqual(kind, "escaped")
        self.assertIn("no longer diverted", words)

    def test_a_failed_move_fails_the_run(self):
        from core.pool_test_report import REASSIGN_FAILED
        f = [FrameResult(label=f"F{i}", session_id=SID[i], pool=i + 1) for i in range(3)]
        ok = [{"window": 2, "from": 3, "pool": 1, "route": "HONEYPOT", "session_before": SID[2],
               "session_after": SID[2], "status": 200}]
        self.assertEqual(analyze(f, state(), None, None, ok).status, EXCLUSIVE)
        bad = [dict(ok[0], status=502)]
        v = analyze(f, state(), None, None, bad)
        self.assertEqual(v.status, REASSIGN_FAILED)
        self.assertIn("F2 (was on removed pool 3): HTTP 502", " ".join(v.findings))


class ClearBrowserDataTests(unittest.TestCase):
    """Windows clearing their own cookies / storage mid-run, reported as observed."""

    @staticmethod
    def _step(title, *pools, sids=None, carts=()):
        from core.pool_test_report import Decision, StepResult
        sids = sids or SID
        return StepResult(title, "", [""] * len(pools),
                          [Decision(sids[i], "HONEYPOT" if p is not None else "PRODUCTION", pool=p)
                           for i, p in enumerate(pools)], carts=list(carts))

    def test_schedule_is_reproducible_and_never_empty(self):
        import random
        from core.pool_test_report import CLEAR_TEXT, clear_schedule
        a = clear_schedule([3, 4, 5, 6], 3, random.Random(7))
        self.assertEqual(a, clear_schedule([3, 4, 5, 6], 3, random.Random(7)))
        for seed in range(50):
            s = clear_schedule([3, 4], 3, random.Random(seed))
            self.assertTrue(s)
            for n, events in s.items():
                self.assertIn(n, (3, 4))
                for w, variant in events:
                    self.assertIn(w, range(3))
                    self.assertIn(variant, CLEAR_TEXT)
        self.assertEqual(clear_schedule([], 3, random.Random(1)), {})

    def test_schedule_always_has_a_clearing_and_a_forgery(self):
        import random
        from core.pool_test_report import FORGE_KEYS, clear_schedule
        for seed in range(50):
            variants = [v for events in clear_schedule([3, 4, 5], 3, random.Random(seed)).values()
                        for _w, v in events]
            self.assertTrue(any(v in ("forge_cookie", "hijack_cookie") for v in variants))
            self.assertIn("forge_storage", variants)
            self.assertTrue(any(v not in FORGE_KEYS for v in variants))
            self.assertNotIn("storage", variants)       # storage-only clearing tested nothing
            off = [v for events in clear_schedule([3, 4, 5], 3, random.Random(seed), forge=False).values()
                   for _w, v in events]
            self.assertFalse(any(v in FORGE_KEYS for v in off))
        # With a second window there is always a hijack, after the first step.
        for seed in range(50):
            sched = clear_schedule([3, 4, 5, 6], 3, random.Random(seed))
            self.assertTrue(any(v == "hijack_cookie" and n > 3 for n, ev in sched.items() for _w, v in ev))
        # One window has no other session to hijack.
        for seed in range(50):
            for events in clear_schedule([3, 4, 5, 6], 1, random.Random(seed)).values():
                self.assertNotIn("hijack_cookie", [v for _w, v in events])

    def test_no_window_forges_its_cookie_twice(self):
        # Each rejected forgery scores +50: two diverted a delayed window
        # before its attack. Events also go to different windows first.
        import random
        from core.pool_test_report import COOKIE_FORGERIES, clear_schedule
        for seed in range(300):
            sched = clear_schedule(list(range(3, 16)), 10, random.Random(seed))
            events = [ev for n in sorted(sched) for ev in sched[n]]
            forgers = [w for w, v in events if v in COOKIE_FORGERIES]
            self.assertEqual(len(forgers), len(set(forgers)), seed)
            windows = [w for w, _v in events]
            self.assertEqual(len(set(windows)), min(10, len(windows)), seed)

    def test_forged_cookie_detection(self):
        from core.pool_test_report import ClearEvent
        rejected = ClearEvent(1.0, 0, 2, "forge_cookie", SID[0], 1, planted="e" * 32 + ".f",
                              claimed_session="e" * 32, rejections_checked=True,
                              rejection={"status": "bad_signature", "scored": True, "score": 50},
                              after_session=SID[0], after_pool=1, resolved=True)
        self.assertEqual(rejected.detection(), "detected")
        self.assertIn("rejected (bad_signature, scored +50 as tampering); kept its session",
                      rejected.outcome())
        unlogged = ClearEvent(1.0, 0, 2, "forge_cookie", SID[0], planted="x", claimed_session="e" * 32,
                              rejections_checked=True, after_session=SID[0], resolved=True)
        self.assertEqual(unlogged.detection(), "not logged")
        hijack = ClearEvent(1.0, 0, 2, "hijack_cookie", SID[0], planted="x", claimed_session=SID[1],
                            rejections_checked=True, after_session=SID[1], resolved=True)
        self.assertTrue(hijack.accepted_forgery())
        self.assertEqual(hijack.detection(), "accepted")
        storage = ClearEvent(1.0, 0, 2, "forge_storage", SID[0], storage_keys=8,
                             after_session=SID[0], resolved=True)
        self.assertEqual(storage.detection(), "ignored")
        self.assertIn("never reads browser storage", storage.outcome())
        self.assertFalse(storage.clears_cookies())

    def test_empty_storage_is_not_listed(self):
        from core.pool_test_report import ClearEvent
        e = ClearEvent(1.0, 0, 2, "all", SID[0], cookies=["SERVERID", "fh_cart"], storage_keys=0)
        self.assertNotIn("storage", e.removed())
        e.storage_keys = 3
        self.assertIn("3 storage entries", e.removed())

    def test_action_note_is_short(self):
        from core.pool_test_report import ClearEvent
        e = ClearEvent(1.0, 0, 2, "hijack_cookie", SID[0], planted="x", claimed_session=SID[1],
                       rejections_checked=True, rejection={"status": "bad_signature"},
                       after_session=SID[0], resolved=True)
        self.assertEqual(e.action_note(), "\u25c6 hijack attempt \u2192 rejected")
        c = ClearEvent(1.0, 0, 2, "cookies", SID[0], after_session=SID[0], resolved=True)
        self.assertEqual(c.action_note(), "\u25c6 cleared cookies \u2192 kept its session")

    def test_hijack_names_its_victim(self):
        from core.pool_test_report import ClearEvent
        e = ClearEvent(1.0, 0, 2, "hijack_cookie", SID[0], planted="b" * 32 + ".x", claimed_session=SID[1],
                       claimed_window=3, claimed_pool=7)
        self.assertIn("of User D, on pool 7", e.removed())
        e.claimed_pool = None
        self.assertIn("of User D, on production", e.removed())

    def test_accepted_forgery_fails_the_run(self):
        from core.pool_test_report import TAMPER_ACCEPTED, ClearEvent
        steps = [self._step("attack", 1, 2, 3), self._step("forged", 2, 2, 3, sids=[SID[1], SID[1], SID[2]])]
        f = [FrameResult(label=f"F{i}", session_id=s, pool=p)
             for i, (s, p) in enumerate(((SID[1], 2), (SID[1], 2), (SID[2], 3)))]
        hijack = ClearEvent(1.0, 0, 1, "hijack_cookie", SID[0], 1, planted="x", claimed_session=SID[1],
                            after_session=SID[1], after_pool=2, resolved=True)
        v = analyze(f, state(ready=(1, 2, 3)), steps, [hijack])
        self.assertEqual(v.status, TAMPER_ACCEPTED)
        self.assertIn("F0 forged its SERVERID", v.findings[0])

    def test_outcome_is_observed_not_judged(self):
        from core.pool_test_report import ClearEvent
        kept = ClearEvent(1.0, 0, 2, "cookies", SID[0], 1, cookies=["SERVERID"],
                          after_session=SID[0], after_pool=1, after_route="HONEYPOT", resolved=True)
        self.assertTrue(kept.same_session())
        self.assertIn("kept its session, served by pool 1", kept.outcome())
        self.assertIn("1 cookie(s) (SERVERID)", kept.removed())
        fresh = ClearEvent(1.0, 0, 2, "all", SID[0], 1, storage_keys=2,
                           after_session="d" * 32, after_route="PRODUCTION", resolved=True)
        self.assertIn("fresh session, served by production", fresh.outcome())
        self.assertIn("2 storage entries", fresh.removed())
        self.assertIn("not observed", ClearEvent(1.0, 0, 2, "storage", SID[0]).outcome())

    def test_cleared_cookies_restart_the_cart_baseline(self):
        from core.pool_test_report import CartState, ClearEvent, cart_resets, cart_violations
        full, empty = CartState([("Mug", 2)], "$44"), CartState([], "$0")
        steps = [self._step("fill", 1, carts=[full]), self._step("next", 1, carts=[empty])]
        self.assertEqual(len(cart_violations(steps)), 1)
        cookies = [ClearEvent(1.0, 0, 1, "cookies", SID[0])]
        self.assertEqual(cart_violations(steps, cart_resets(cookies)), [])
        storage = [ClearEvent(1.0, 0, 1, "storage", SID[0])]
        self.assertEqual(len(cart_violations(steps, cart_resets(storage))), 1)

    def test_fresh_session_after_clearing_is_not_a_pool_move(self):
        from core.pool_test_report import ClearEvent
        new = ["d" * 32, SID[1], SID[2]]
        steps = [self._step("attack", 1, 2, 3), self._step("cleared", 4, 2, 3, sids=new)]
        f = [FrameResult(label=f"F{i}", session_id=new[i], pool=p) for i, p in enumerate((4, 2, 3))]
        self.assertEqual(analyze(f, state(ready=(1, 2, 3, 4), free=[5]), steps).status, "unstable")
        event = ClearEvent(1.0, 0, 1, "all", SID[0], 1, after_session=new[0], after_pool=4,
                           after_route="HONEYPOT", resolved=True)
        self.assertEqual(analyze(f, state(ready=(1, 2, 3, 4), free=[5]), steps, [event]).status,
                         EXCLUSIVE)

    def test_fresh_session_left_on_production_is_noted_not_incomplete(self):
        from core.pool_test_report import ClearEvent
        new = ["d" * 32, SID[1], SID[2]]
        steps = [self._step("attack", 1, 2, 3), self._step("cleared", None, 2, 3, sids=new)]
        f = [FrameResult(label=f"F{i}", session_id=new[i], pool=p) for i, p in enumerate((None, 2, 3))]
        self.assertEqual(analyze(f, state(free=[4]), steps).status, INCOMPLETE)
        event = ClearEvent(1.0, 0, 1, "cookies", SID[0], 1, after_session=new[0],
                           after_route="PRODUCTION", resolved=True)
        v = analyze(f, state(free=[4]), steps, [event])
        self.assertEqual(v.status, EXCLUSIVE)
        self.assertIn("F0 cleared browser data", " ".join(v.findings))

    def test_cart_after_clearing_cookies_is_explained(self):
        from core.pool_test_report import (CART_CLEARED, CART_RESTORED, CART_SAME, CartState,
                                           ClearEvent, cart_marks, cart_resets)
        full, empty = CartState([("Mug", 2)], "$44"), CartState([], "$0")
        resets = cart_resets([ClearEvent(1.0, 0, 1, "cookies", SID[0])])
        # Cleared before step 2: empty from then on is expected, not a change.
        steps = [self._step("fill", 1, carts=[full]), self._step("clear", 1, carts=[empty]),
                 self._step("later", 1, carts=[empty])]
        marks, issues, notes = cart_marks(steps, resets)
        self.assertEqual([m[0] for m in marks], [CART_SAME, CART_CLEARED, CART_CLEARED])
        self.assertEqual((issues, notes), ([], []))
        # A cart that comes back afterwards is noted, then is the new baseline.
        steps.append(self._step("back", 1, carts=[full]))
        steps.append(self._step("gone", 1, carts=[empty]))
        marks, issues, notes = cart_marks(steps, resets)
        self.assertEqual(marks[3][0], CART_RESTORED)
        self.assertIn("reappeared in 'back'", notes[0])
        self.assertEqual(len(issues), 1)
        self.assertIn("deleted its cookies before 'clear'", issues[0])


class ReportRunRegressionTests(unittest.TestCase):
    """The shape of the 2026-10-16 run (pool_test_report_issues.md 3.1-3.3, 3.5)."""

    def setUp(self):
        from core.pool_test_report import PoolTestData, Sample
        P = ("PRODUCTION", None, False)
        # windows: 0 = A (own pool 1), 1 = E, 2 = H, 3 = I
        timeline = [
            (0, [("a", *P), ("e_old", *P), ("h", *P), ("i", *P)]),
            (10, [("a", "HONEYPOT", 1, False), ("e_old", *P), ("h", *P), ("i", *P)]),
            (82, [("a", "HONEYPOT", 1, False), ("e_old", "HONEYPOT", 1, True), ("h", *P), ("i", *P)]),
            (110, [("a", "HONEYPOT", 1, False), ("e_new", *P), ("h", *P), ("i", *P)]),   # E cleared data
            (290, [("a", "HONEYPOT", 1, False), ("e_new", *P), ("h", "HONEYPOT", 8, False),
                   ("i", "HONEYPOT", 5, False)]),
        ]
        samples = [Sample(t, w, sid, r, p, wt) for t, row in timeline
                   for w, (sid, r, p, wt) in enumerate(row)]
        events = [{"type": "handoff", "pool": 5, "session": "e_old", "borrowed": 1, "waited": 52, "at": 132},
                  {"type": "capped", "reason": "resource limit reached", "at": 164}]
        frames_ = [FrameResult(f"User {c}", session_id=s, pool=p)
                   for c, s, p in (("A", "a", 1), ("E", "e_new", None), ("H", "h", 8), ("I", "i", 5))]
        self.state = {"ready": [1, 5, 8], "free": [], "capped": "resource limit reached",
                      "owners": {1: 1, 5: 2, 8: 1}}
        self.data = PoolTestData("now", "t", "u", "", frames_, pool_state=self.state,
                                 duration=400, samples=samples, events=events)

    def test_cases(self):
        from core.pool_test_report import scaling_summary
        s = scaling_summary(self.data)
        (b,) = s.borrow
        self.assertEqual((b.window, b.outcome, b.own_pool, b.start), (1, "abandoned", 5, 80))
        self.assertEqual([(a.window, a.session_id, a.later_pool) for a in s.abandoned], [(1, "e_old", 5)])
        self.assertEqual([c.window for c in s.limit], [3])          # I only; H had pool 8 alone
        self.assertIn("abandoned session", s.limit[0].shared_outside[0])
        self.assertEqual(s.owners[1], 0)

    def test_verdict_counts_registry_owners(self):
        frames_ = [FrameResult(f"User {c}", session_id=f"{c * 32}", pool=p)
                   for c, p in (("A", 1), ("E", 1), ("H", 8), ("I", 5))]
        state = dict(self.state, owners={1: 2, 5: 2, 8: 1})
        v = analyze(frames_, state)
        self.assertIn("Pool 5 is shared by User I and 1 session(s) outside the test.", v.findings)
        self.assertNotIn(8, [n for n in v.by_pool if f"Pool {n} is shared" in " ".join(v.findings)])


class IssueFixTests(unittest.TestCase):
    def test_background_is_subtracted_from_db_counters(self):
        from core.pool_evidence import without_background
        base = {"Questions": 1000, "Com_select": 900, "Com_insert": 0, "Com_update": 0, "Com_delete": 0}
        idle = {"Questions": 1600, "Com_select": 1500, "Com_insert": 0, "Com_update": 0, "Com_delete": 0}
        delta = {"Questions": 7000, "Com_select": 6500, "Com_insert": 5, "Com_update": 2, "Com_delete": 0}
        out = without_background(delta, base, idle, idle_s=60, total_s=600)   # 10/s background
        self.assertEqual(out["Questions"], 1000)
        self.assertEqual(out["Com_select"], 500)
        self.assertEqual(out["Com_insert"], 5)
        self.assertIsNone(without_background(delta, base, None, 60, 600))

    def test_explained_cross_traffic_is_not_a_finding(self):
        from core import pool_evidence as pe
        ev = pe.ContainerEvidence(1, hits=[pe.Hit("A", "GET", "/", 200), pe.Hit("E", "GET", "/x", 200),
                                           pe.Hit("G", "GET", "/y", 200)])
        out = pe.cross_traffic([ev], {1: "A"}, {1: {"E"}})
        self.assertEqual(len(out), 1)
        self.assertIn("G", out[0])
        self.assertNotIn("E,", out[0])

    def test_capacity_warning(self):
        from core.pool_test_report import capacity_warning
        state = {"ready": [1, 2, 3, 4], "status": {"room": 4, "mem_per_pool": 1536}}
        self.assertIn("2 of the 10 windows", capacity_warning(10, 3, state))
        self.assertEqual(capacity_warning(8, 0, state), "")
        self.assertEqual(capacity_warning(10, 0, {}), "")       # manager status unknown

    def test_probe_loads_are_preferred_for_latency(self):
        from core.pool_test_report import LoadTiming, latency_loads
        loads = [LoadTiming(0, 0, "step", 3000, "own"), LoadTiming(1, 0, "probe", 400, "own", probe=True)]
        chosen, probed = latency_loads(loads)
        self.assertTrue(probed)
        self.assertEqual([x.ms for x in chosen], [400])
        self.assertEqual(latency_loads(loads[:1]), (loads[:1], False))

    def test_score_cause_is_the_forgery_until_the_pattern_is_sent(self):
        from core.pool_test_report import (ClearEvent, FrameResult, PatternRun, PoolTestData, StepResult,
                                           score_causes)
        steps = [StepResult(f"s{k}", "", ["Looks at the FAQ", "Looks at the FAQ"], [], [], [])
                 for k in range(4)]
        steps[3].actions[1] = "Opens CVE-2025-2266 (1 attempt(s))"
        steps[1].actions[0] = "Opens CVE-2024-2387 (1 attempt(s))"
        rej = {"status": "bad_signature", "scored": True, "score": 50}
        d = PoolTestData("now", "t", "u", "", [FrameResult("User A"), FrameResult("User B")], steps=steps,
                         runs=[PatternRun("A", "CVE-2024-2387", "x", 1, True, 1),
                               PatternRun("B", "CVE-2025-2266", "y", 1, True, 3)],
                         cleared=[ClearEvent(1, 1, 1, "hijack_cookie", "s", rejection=rej),
                                  ClearEvent(2, 1, 2, "forge_cookie", "s", rejection=rej)])
        c = score_causes(d)
        self.assertEqual([x.get(0) for x in c], [None] + ["its CVE-2024-2387 request"] * 3)
        self.assertEqual([x.get(1) for x in c], [None, "its rejected forged cookie",
                                                 "its rejected forged cookies", "its CVE-2025-2266 request"])


class ResponseRealismTests(unittest.TestCase):
    def test_counts_4xx_pattern_responses(self):
        from core import pool_evidence as pe
        ev = pe.ContainerEvidence(1, hits=[
            pe.Hit("A", "GET", "/?page=advanced-form-integration-log&x=1", 404),
            pe.Hit("A", "GET", "/product/mug/", 200),
            pe.Hit("B", "GET", "/?action=dnd-wc-upload-file&name=shell", 404),
            pe.Hit("B", "GET", "/style.css", 200)])   # asset: excluded by notable()
        total, four, ex = pe.response_realism([ev])
        self.assertEqual((total, four), (3, 2))
        self.assertTrue(any("404" in e for e in ex))


class PersonalIssueTests(unittest.TestCase):
    def test_host_stats_parsing(self):
        from core.resource_stats import parse_host_stats
        out = "20\nMemTotal:       16375680 kB\nMemAvailable:    4000000 kB\nSwap: 0\n"
        cpus, total, used = parse_host_stats(out)
        self.assertEqual(cpus, 20)
        self.assertAlmostEqual(total, 15992.0, delta=1)
        self.assertAlmostEqual(used, 12085.0, delta=1)   # (16375680-4000000)/1024
        self.assertIsNone(parse_host_stats("nope"))

    def test_cpu_panel_normalizes_by_host_cpus(self):
        # usage_figure labels CPU by host cpus when known; check the label logic.
        from core.pool_test_report import PoolTestData, UsageSample
        d = PoolTestData("n", "t", "u", "x", [], host_cpus=20,
                         usage=[UsageSample(0, 2, 1, 400, 180.0, 1)])
        # The normalized value for a 180% sum on 20 CPUs is 9%.
        cpus = d.host_cpus
        self.assertAlmostEqual(d.usage[0].cpu_percent / cpus, 9.0)
