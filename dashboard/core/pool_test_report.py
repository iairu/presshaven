"""Data and verdict for the Segmentation Validation page's PDF report (no Qt, so it is unit
tested on its own; the rendering is core/pool_test_report_pdf.py).

The property under test: by default there is ONE flagged session per
honeypot pool. The pools scale with the number of user sessions: a session
that finds no free pool borrows one round-robin until pool_manager has built its
own, then moves there. Two sessions only keep sharing a pool once growth is
capped (the pools' resource budget or POOL_MAX is reached, or the host is low on
memory/CPU/disk) -- the router then reuses the ready pools round-robin.
analyze() turns the frames' session -> pool observations plus the Redis pool
registry into a verdict on exactly that.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# Patterns the report runs, chosen from a live probe of every GET preset (fresh
# session each, up to three attempts): these divert to a honeypot on the FIRST
# request. Per window (A, B, C): a primary pattern and a second, different one;
# FALLBACK are the ones that divert on the 2nd-3rd request, tried only when a
# window's chosen pattern does not divert within MAX_ATTEMPTS. Presets that never
# divert in three attempts (time-based blind SQLi, wordlist scans, IDOR walks)
# are deliberately absent. test_pool_test_report checks every CVE exists.
PATTERN_PLAN = [("CVE-2024-2387", "CVE-2024-1071"),     # A: SQL injection
                ("CVE-2025-47577", "CVE-2025-4403"),    # B: file-upload RCE
                ("GENERIC-WP-003", "GENERIC-WP-002")]   # C: user enumeration / installer
FALLBACK_PATTERNS = ["CVE-2024-27956", "CVE-2022-0739", "CVE-2024-2879", "CVE-2023-2986",
                     "CVE-2025-2266", "GENERIC-SQLI-001", "GENERIC-XSS-001", "GENERIC-XSS-002",
                     "GENERIC-WP-001"]
MAX_ATTEMPTS = 3

# How many test windows the Segmentation Validation page can run side by side.
MIN_WINDOWS, MAX_WINDOWS = 3, 10

# What each window puts in its cart before anything is attacked: (product slug,
# quantity). Simple products only, so a plain ?add-to-cart= request is enough.
CART_PLAN = [[("ceramic-pour-over-dripper", 1), ("paper-filters-size-02", 2)],
             [("hand-burr-coffee-grinder", 1), ("stainless-milk-pitcher", 1)],
             [("enamel-camp-mug", 2), ("fernhill-canvas-tote", 1)],
             [("gooseneck-electric-kettle", 1), ("logo-cap", 2)],
             [("digital-brew-scale", 1)],
             [("glass-french-press", 1), ("barista-apron", 1)],
             [("glass-bean-canister", 2)],
             [("double-wall-glass-cups", 2)],
             [("insulated-travel-tumbler", 1)],
             [("coffee-lover-gift-box", 1), ("pour-over-starter-kit", 1)]]

# What a window that is not attacking looks at meanwhile, like a shopper would:
# (path, what the report calls it). Read-only pages only -- nothing here may
# change a cart or log anyone in.
BROWSE_PAGES = [("/product/kenya-nyeri-aa/", "Kenya Nyeri AA"),
                ("/terms-of-service/", "the Terms of Service"),
                ("/product-category/brewing-gear/", "Brewing Gear"),
                ("/product/glass-french-press/", "Glass French Press"),
                ("/shipping-returns/", "Shipping & Returns"),
                ("/product/ethiopia-guji-natural/", "Ethiopia Guji Natural"),
                ("/product-category/drinkware/", "Drinkware"),
                ("/faq/", "the FAQ"),
                ("/product/stoneware-mug/", "Stoneware Mug"),
                ("/privacy-policy/", "the Privacy Policy"),
                ("/product/coffee-club-subscription/", "Coffee Club Subscription"),
                ("/product-category/coffee/", "Coffee Beans"),
                ("/about/", "Our Story"),
                ("/product/sunrise-espresso-blend/", "Sunrise Espresso")]


def browse_page(window: int, visit: int) -> tuple[str, str]:
    """The `visit`-th page window `window` browses while it has nothing else to
    do. Windows start at different points of BROWSE_PAGES, so they look at
    different things at the same time."""
    return BROWSE_PAGES[(window * 3 + visit) % len(BROWSE_PAGES)]


def browse_action(labels: list[str]) -> str:
    """Report text for the pages a window looked at during one step."""
    if not labels:
        return "Browses the shop"
    seen = list(dict.fromkeys(labels))
    return "Looks at " + ", ".join(seen)


def window_plan(windows: int) -> list[tuple[str, str]]:
    """(first, second) pattern per window. Windows A-C use PATTERN_PLAN; further
    windows open with a fallback pattern (a different one each while they last)
    and run one of A-C's second patterns afterwards -- separate sessions, so a
    repeat across windows does not matter there."""
    plan = list(PATTERN_PLAN[:windows])
    for w in range(len(plan), windows):
        k = w - len(PATTERN_PLAN)
        plan.append((FALLBACK_PATTERNS[k % len(FALLBACK_PATTERNS)],
                     PATTERN_PLAN[k % len(PATTERN_PLAN)][1]))
    return plan

EXCLUSIVE = "exclusive"
SHARED_EXPECTED = "shared_expected"
SHARED_UNEXPECTED = "shared_unexpected"
MERGED = "merged"
INCOMPLETE = "incomplete"
UNSTABLE = "unstable"
CART_LOST = "cart_lost"
TAMPER_ACCEPTED = "tamper_accepted"
REASSIGN_FAILED = "reassign_failed"


@dataclass
class FrameResult:
    label: str
    user_agent: str = ""
    language: str = ""
    url: str = ""
    session_id: str = ""          # "" -> the proxy never set a session cookie
    pool: int | None = None       # None -> session not bound to any pool
    screenshot: Any = None        # QImage of the frame, or None


@dataclass
class Decision:
    """The router's current decision for one session, read back from Redis."""
    session_id: str = ""
    route: str = "NO SESSION"     # "PRODUCTION" | "HONEYPOT" | "NO SESSION"
    score: int | None = None
    reason: str = ""
    pool: int | None = None
    waiting: bool = False         # borrowing `pool` until its own pool is built

    def text(self) -> str:
        if self.route == "NO SESSION":
            return "No session yet"
        out = f"Routed to {self.route}"
        if self.pool is not None:
            out += f" \u2022 pool {self.pool}"
            if self.waiting:
                out += " (borrowed, own pool being built)"
        if self.score is not None:
            out += f" \u2022 score {self.score}"
        if self.reason and self.route == "HONEYPOT":
            out += f" \u2022 {self.reason}"
        return out


def parse_decision(session_id: str, session_json: str, pool_text: str,
                   waiting_text: str = "") -> Decision:
    """Decision from the session:<id> record, honeypot_pool_session:<id> value
    and the session's score in honeypot_pool:waiting (any may be empty or
    unparseable -> that part is simply unknown)."""
    if not session_id:
        return Decision()
    try:
        rec = json.loads(session_json) if session_json.strip() else {}
    except ValueError:
        rec = {}
    pool = int(pool_text) if pool_text.strip().isdigit() else None
    if not isinstance(rec, dict):
        rec = {}
    score = rec.get("risk_score")
    bound = bool(rec.get("honeypot_bound")) or pool is not None
    return Decision(
        session_id=session_id,
        route="HONEYPOT" if bound else "PRODUCTION",
        score=int(score) if isinstance(score, (int, float)) else None,
        reason=str(rec.get("honeypot_reason") or ""),
        pool=pool, waiting=pool is not None and bool(waiting_text.strip()))


@dataclass
class CartState:
    """A window's cart as the shop reports it (WooCommerce Store API)."""
    items: list[tuple[str, int]] = field(default_factory=list)   # (product name, quantity)
    total: str = ""

    def signature(self) -> tuple:
        return tuple(sorted(self.items))

    def text(self) -> str:
        if not self.items:
            return "Cart empty"
        n = sum(q for _n, q in self.items)
        return f"Cart: {n} item{'s' if n != 1 else ''}" + (f" \u2022 {self.total}" if self.total else "")


def parse_cart(store_api_json: str) -> CartState | None:
    """CartState from a /wp-json/wc/store/v1/cart response; None if unreadable."""
    try:
        d = json.loads(store_api_json)
        minor = int(d["totals"].get("currency_minor_unit", 2))
        cents = int(d["totals"]["total_price"])
        sym = d["totals"].get("currency_prefix", "$")
        return CartState([(i["name"], int(i["quantity"])) for i in d["items"]],
                         f"{sym}{cents / 10 ** minor:,.{minor}f}")
    except (ValueError, KeyError, TypeError):
        return None


# ---- session tamper-proofing: clearing and forging session data ------------
#
# With tamper-proofing on, random windows tamper with their own session between
# steps. Some clear their data the way a regular visitor does from the
# browser's settings: the site's cookies, its localStorage/sessionStorage, or
# both. The stack should keep them on their session by its passive
# fingerprint. Others forge it:
#   * forge_cookie  -- SERVERID rewritten to an invented session id with a
#                      made-up signature,
#   * hijack_cookie -- SERVERID rewritten to ANOTHER window's real session id
#                      with a made-up signature (a session-hijack attempt),
#   * forge_storage -- a fake session written into localStorage and
#                      sessionStorage.
# A forged cookie must fail the proxy's HMAC check: the proxy logs it to Redis
# (session_cookie_rejections, by the SHA-1 of the value) and recovers the
# window's real session by fingerprint, never the claimed one. Browser storage
# is never sent to the server, so a forged one must change nothing at all.
# The report records, as observed, what the stack did with the window.

# Clearing only localStorage/sessionStorage is not scheduled: the shop keeps
# nothing there, so it removed 0 entries and tested nothing. Browser storage is
# covered by forge_storage instead (a fake session written there must change
# nothing). "storage" stays readable for reports made before.
CLEAR_VARIANTS = [("cookies", "cleared its cookies"),
                  ("all", "cleared all site data (cookies, localStorage, sessionStorage)")]
LEGACY_VARIANTS = [("storage", "cleared its localStorage and sessionStorage")]
FORGE_VARIANTS = [("forge_cookie", "forged its session cookie (invented session id, made-up signature)"),
                  ("hijack_cookie", "forged its session cookie to another window's session id "
                                    "(made-up signature)"),
                  ("forge_storage", "wrote a fake session into its localStorage and sessionStorage")]
CLEAR_TEXT = dict(CLEAR_VARIANTS + FORGE_VARIANTS + LEGACY_VARIANTS)
SHORT_TEXT = {"cookies": "cleared cookies", "all": "cleared site data", "storage": "cleared storage",
              "forge_cookie": "forged cookie", "hijack_cookie": "hijack attempt",
              "forge_storage": "forged storage"}
FORGE_KEYS = {k for k, _t in FORGE_VARIANTS}
COOKIE_FORGERIES = {"forge_cookie", "hijack_cookie"}

# Chance that an eligible step starts with one window tampering with its session.
CLEAR_CHANCE = 0.5


def clear_schedule(steps: list[int], windows: int, rng,
                   forge: bool = True) -> dict[int, list[tuple[int, str]]]:
    """{step number: [(window, variant), ...]} -- who clears or forges what
    before which step. Each step gets one event with CLEAR_CHANCE; a run with
    eligible steps always gets at least one clearing and (with ``forge``) at
    least one cookie forgery and one storage forgery, so the report has every
    kind to show. With a second window to steal from, at least one of the
    cookie forgeries is a hijack, after the first eligible step."""
    if not steps or windows <= 0:
        return {}
    clears = [k for k, _t in CLEAR_VARIANTS]
    cookie_forges = ([k for k in ("forge_cookie", "hijack_cookie") if windows > 1 or k != "hijack_cookie"]
                     if forge else [])
    storage_forges = ["forge_storage"] if forge else []
    variants = clears + cookie_forges + storage_forges
    out: dict[int, list[tuple[int, str]]] = {}
    for n in steps:
        if rng.random() < CLEAR_CHANCE:
            out[n] = [(rng.randrange(windows), rng.choice(variants))]
    for pool in (clears, cookie_forges, storage_forges):
        if pool and not any(v in pool for events in out.values() for _w, v in events):
            free = [n for n in steps if n not in out] or steps
            out.setdefault(rng.choice(free), []).append((rng.randrange(windows), rng.choice(pool)))
    # The hijack (another window's real session) is the telling forgery; with
    # a second window there is always one, after the first eligible step so
    # that some window is already diverted and its session is worth stealing.
    if "hijack_cookie" in cookie_forges and not any(
            v == "hijack_cookie" and n > steps[0] for n, events in out.items() for _w, v in events):
        later = [n for n in steps[1:] if n not in out] or steps[1:] or steps
        out.setdefault(rng.choice(later), []).append((rng.randrange(windows), "hijack_cookie"))
    return out


@dataclass
class ClearEvent:
    """One window clearing or forging its own session data, and what the stack did next."""
    t: float                      # seconds since the run started
    window: int
    step: int                     # index into PoolTestData.steps of the step it happened before
    variant: str                  # a key of CLEAR_TEXT
    before_session: str
    before_pool: int | None = None
    cookies: list[str] = field(default_factory=list)   # names of the cookies deleted
    storage_keys: int = 0         # localStorage + sessionStorage entries removed / written
    after_session: str = ""       # the window's session once the step settled
    after_pool: int | None = None
    after_route: str = ""
    resolved: bool = False        # the step after it was read back
    # Forgeries: the value planted, the session id it claimed, its SHA-1 (what
    # the proxy logs instead of the value) and the proxy's rejection record
    # ({"status", "scored", "score", ...}) found for it in Redis.
    planted: str = ""
    claimed_session: str = ""
    planted_sha1: str = ""
    rejection: dict | None = None
    rejections_checked: bool = False   # the Redis rejection log could be read
    # A hijack: whose session it claimed, and the pool that session was on
    # (None: on production) -- a diverted victim is preferred.
    claimed_window: int | None = None
    claimed_pool: int | None = None

    def clears_cookies(self) -> bool:
        return self.variant in ("cookies", "all")

    def is_forgery(self) -> bool:
        return self.variant in FORGE_KEYS

    def forges_cookie(self) -> bool:
        return self.variant in COOKIE_FORGERIES

    def same_session(self) -> bool:
        return bool(self.before_session) and self.after_session == self.before_session

    def accepted_forgery(self) -> bool:
        """The stack took the forged session: the window ended up in the
        session its forged cookie claimed."""
        return (self.forges_cookie() and self.resolved and bool(self.claimed_session)
                and self.after_session == self.claimed_session)

    def detection(self) -> str:
        """For a forgery: 'detected', 'ignored' (storage, as designed),
        'accepted', 'not logged', or 'not observed'."""
        if not self.is_forgery():
            return ""
        if self.accepted_forgery():
            return "accepted"
        if not self.forges_cookie():
            if not self.resolved:
                return "not observed"
            return "ignored" if self.same_session() or not self.before_session else "session changed"
        if self.rejection:
            return "detected"
        if not self.rejections_checked:
            return "not observed"
        return "not logged"

    def what(self) -> str:
        return CLEAR_TEXT.get(self.variant, self.variant)

    def short_outcome(self) -> str:
        """The outcome in a word or two, for the step tables' action cells."""
        if not self.resolved:
            return "not observed"
        if self.is_forgery():
            d = self.detection()
            return {"detected": "rejected", "accepted": "ACCEPTED"}.get(d, d)
        if self.same_session():
            return "kept its session"
        return "fresh session" if self.after_session else "no session"

    def action_note(self) -> str:
        """'◆ hijack attempt → rejected' -- the marker a step table shows in the
        window's action; the tamper table has the detail."""
        return f"\u25c6 {self.short()} \u2192 {self.short_outcome()}"

    def short(self) -> str:
        """A few words for narrow cells (the step tables, the tamper table's
        first line); what() is the full sentence."""
        return SHORT_TEXT.get(self.variant, self.variant)

    def removed(self) -> str:
        if self.forges_cookie():
            victim = ""
            if self.claimed_window is not None:
                victim = (f" of User {chr(65 + self.claimed_window)}, on "
                          + (f"pool {self.claimed_pool}" if self.claimed_pool is not None else "production"))
            return (f"SERVERID = {self.planted[:14]}\u2026 (claims session {self.claimed_session[:8]}"
                    f"{victim})")
        if self.variant == "forge_storage":
            return f"{self.storage_keys} storage entr{'y' if self.storage_keys == 1 else 'ies'} written"
        parts = []
        if self.clears_cookies():
            # The session and cart cookies by name, the rest as a count: the full
            # list (sourcebuster, WooCommerce hashes, a 50-character session
            # cookie name) made one table row span two pages.
            key = [c for c in self.cookies if c in ("SERVERID", "fh_cart")]
            rest = len(self.cookies) - len(key)
            named = ", ".join(key) + (f" + {rest} other(s)" if rest and key else
                                      f"{rest} other(s)" if rest else "")
            parts.append(f"{len(self.cookies)} cookie(s)" + (f" ({named})" if self.cookies else ""))
        # The shop keeps nothing in browser storage, so clearing it usually
        # removes nothing: only worth a mention when there was something.
        if self.variant in ("storage", "all") and (self.storage_keys or self.variant == "storage"):
            parts.append(f"{self.storage_keys} storage entr{'y' if self.storage_keys == 1 else 'ies'}")
        return ", ".join(parts)

    def outcome(self) -> str:
        """What the stack did with the window afterwards, as observed."""
        if not self.resolved:
            return "not observed: the run ended before the window loaded another page"
        where = (f"pool {self.after_pool}" if self.after_pool is not None
                 else "production" if self.after_route == "PRODUCTION" else "no route yet")
        if self.accepted_forgery():
            return f"ACCEPTED the forged session {self.claimed_session[:8]}, served by {where}"
        prefix = ""
        if self.forges_cookie():
            if self.rejection:
                scored = (f", scored +{self.rejection.get('score', 0)} as tampering"
                          if self.rejection.get("scored") else ", not scored (no stable signing key)")
                prefix = f"rejected ({self.rejection.get('status', '?')}{scored}); "
            elif self.rejections_checked:
                prefix = "no rejection logged for the planted cookie; "
        elif self.variant == "forge_storage":
            prefix = "the server never reads browser storage; "
        if not self.after_session:
            return prefix + "no session afterwards"
        if self.same_session():
            return prefix + f"kept its session, served by {where}"
        return prefix + f"given a fresh session, served by {where}"


def cart_resets(cleared: list[ClearEvent] | None) -> set[tuple[int, int]]:
    """(step index, window) where the window deleted its cookies: WooCommerce's
    own cart cookie went with them, so an emptied cart there is expected."""
    return {(e.step, e.window) for e in cleared or [] if e.clears_cookies()}


def session_resets(cleared: list[ClearEvent] | None) -> set[tuple[int, int]]:
    """(step index, window) where the window came out of a clearing with a
    different session: its pool history starts over there."""
    return {(e.step, e.window) for e in cleared or []
            if e.resolved and e.after_session and not e.same_session()}


# How a window's cart compares with its baseline in one step (see cart_marks()).
CART_UNREADABLE, CART_NONE, CART_CLEARED, CART_RESTORED, CART_SAME, CART_CHANGED = (
    "unreadable", "none", "cleared", "restored", "same", "changed")


def cart_marks(steps: list["StepResult"], resets: set[tuple[int, int]] | None = None
               ) -> tuple[list[list[str]], list[str], list[str]]:
    """Per step and window, how the cart compares with what the window filled
    (one of the CART_* marks); one plain sentence per cart that changed; and
    one per cart that came back after clearing (observed, not a failure).

    The baseline is each window's cart in the first step that has one. Where
    `resets` (see cart_resets()) says the window deleted its cookies, the cart
    cookie went with them: from then on an empty cart is expected (CART_CLEARED).
    A cart that shows up again after that is CART_RESTORED -- the browser no
    longer held it, so the stack brought it back -- and becomes the new baseline."""
    resets = resets or set()
    marks: list[list[str]] = []
    issues: list[str] = []
    notes: list[str] = []
    base: dict[int, tuple[CartState, str]] = {}
    cleared_at: dict[int, str] = {}          # window -> title of the step it cleared before
    for n, step in enumerate(steps):
        row = []
        for i, c in enumerate(step.carts):
            if (n, i) in resets:
                base.pop(i, None)
                cleared_at[i] = step.title
            note = (f" Window {i + 1} had deleted its cookies before '{cleared_at[i]}', "
                    "so the cart it filled was gone from the browser from that step on."
                    if i in cleared_at else "")
            if c is None:
                # Not measured, not a changed cart: the read (retried once with
                # a longer timeout) still timed out, typically while pools were
                # being built and the host was busy.
                row.append(CART_UNREADABLE)
                if i in base:
                    notes.append(f"Window {i + 1}: cart not measured in '{step.title}' "
                                 "(the read timed out twice).")
                continue
            if i not in base:
                if not c.items:
                    row.append(CART_CLEARED if i in cleared_at else CART_NONE)
                    continue
                base[i] = (c, step.title)
                if i in cleared_at:
                    row.append(CART_RESTORED)
                    notes.append(f"Window {i + 1}: a cart ({c.text()}) reappeared in '{step.title}'."
                                  + note + " The browser no longer held it, so the stack restored it.")
                else:
                    row.append(CART_SAME)
                continue
            if c.signature() == base[i][0].signature():
                row.append(CART_SAME)
                continue
            row.append(CART_CHANGED)
            now = c.text() if c.items else "empty"
            issues.append(f"Window {i + 1}: cart changed in '{step.title}' ({now}) "
                          f"from what it held in '{base[i][1]}' ({base[i][0].text()})." + note)
        marks.append(row)
    return marks, issues, notes


def cart_violations(steps: list["StepResult"], resets: set[tuple[int, int]] | None = None) -> list[str]:
    """Carts must stay exactly as filled, however the session is routed (see cart_marks())."""
    return cart_marks(steps, resets)[1]


class ProductListUnreadable(RuntimeError):
    """The Store API answer wasn't a product list at all: the request never
    reached the shop (e.g. the window was on Chromium's error page after a
    failed load) -- as opposed to products that are really missing."""


def parse_product_ids(store_api_json: str, slugs: list[str]) -> dict[str, int]:
    """{slug: product id} from a Store API products response. Raises
    ProductListUnreadable when the response isn't a product list (no answer
    from the shop), RuntimeError when the list lacks one of ``slugs``."""
    try:
        data = json.loads(store_api_json or "")
        if not isinstance(data, list):
            raise TypeError
        found = {p["slug"]: int(p["id"]) for p in data}
    except (ValueError, KeyError, TypeError):
        raise ProductListUnreadable(
            "Could not read the shop's product list: the request from the test window got no "
            "valid answer (the shop page failed to load, e.g. ERR_NETWORK_CHANGED while Docker "
            "created or removed containers, or the shop is not up yet).") from None
    missing = [s for s in slugs if s not in found]
    if missing:
        raise RuntimeError(f"Could not find product(s) {', '.join(missing)} on the shop.")
    return {s: found[s] for s in slugs}


@dataclass
class StepResult:
    """One scripted step: what each window did, and each session's decision after."""
    title: str
    detail: str
    actions: list[str]            # per frame: what that window did this step
    decisions: list[Decision]     # per frame, read after the step settled
    shots: list[Any] = field(default_factory=list)   # per frame QImage
    carts: list[CartState | None] = field(default_factory=list)   # per frame, read after the step
    # Windows whose last page load had failed when the step was read: their
    # screenshot (and cart) come from Chromium's error page, not the shop.
    failed: list[int] = field(default_factory=list)


def sticky_violations(steps: list[StepResult], resets: set[tuple[int, int]] | None = None) -> list[str]:
    """A session bound to a pool must keep that pool for the rest of the run.
    The one allowed move: off a pool it only borrowed (waiting) while its own
    was being built. Starts over where `resets` (see session_resets()) says the
    window got a fresh session after clearing its browser data."""
    out = []
    seen: dict[int, Decision] = {}
    for n, step in enumerate(steps):
        for i, d in enumerate(step.decisions):
            if resets and (n, i) in resets:
                seen.pop(i, None)
            if d.pool is None:
                continue
            prev = seen.get(i)
            if prev is not None and prev.pool != d.pool and not prev.waiting:
                out.append(f"Window {i + 1} moved from pool {prev.pool} to pool {d.pool} "
                           f"during '{step.title}'.")
            seen[i] = d
    return out


@dataclass
class PatternRun:
    """One pattern a window ran: how many attempts it took to be diverted."""
    window: str
    cve: str
    name: str
    attempts: int
    diverted: bool
    pool: int | None
    replaced: bool = False        # picked because an earlier choice never diverted


# Where a window's session is served at one moment (see classify()).
PRODUCTION, OWN, BORROWED, SHARED = "production", "own", "borrowed", "shared"
STATES = (PRODUCTION, OWN, BORROWED, SHARED)


@dataclass
class Sample:
    """One window's routing at one moment of the run (seconds since its start).
    Samples taken together (one read of every window) share the same `t`."""
    t: float
    window: int
    session_id: str
    route: str
    pool: int | None
    waiting: bool


@dataclass
class LoadTiming:
    """How long one page load took in one window, and where it was served."""
    t: float                      # seconds since the run started (load start)
    window: int
    step: str
    ms: float
    state: str = ""               # filled from the routing read right after the load
    probe: bool = False           # a latency probe load (same page, one window at a time)


@dataclass
class UsageSample:
    """All honeypot pool containers' resource use at one moment of the run."""
    t: float
    containers: int
    pools: int
    mem_mb: float
    cpu_percent: float            # sum over pool containers (100 = one core busy)
    ready: int | None = None      # pools registered ready with the router (Redis)
    host_mem_mb: float | None = None   # total RAM in use on the host at this sample


@dataclass
class PoolTestData:
    generated_at: str
    target_label: str
    base_url: str
    pattern: str
    frames: list[FrameResult]
    pool_state: dict = field(default_factory=dict)   # redis_inspect.pool_state()
    steps: list[StepResult] = field(default_factory=list)
    runs: list[PatternRun] = field(default_factory=list)
    evidence: list[Any] = field(default_factory=list)   # pool_evidence.ContainerEvidence
    since: str = ""
    # Scaling / latency (all times in seconds since the run started).
    duration: float = 0.0
    delayed: int = 0              # windows that attacked only after pools were pre-built
    samples: list[Sample] = field(default_factory=list)
    loads: list[LoadTiming] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)  # pool_manager events, `at` rebased
    marks: list[tuple[float, str]] = field(default_factory=list)   # (t, step title)
    reserve: dict = field(default_factory=dict)       # see ScalingSummary.reserve
    usage: list[UsageSample] = field(default_factory=list)
    host_cpus: int = 0            # logical processors on the host (0 = unknown)
    host_mem_total_mb: float = 0.0  # total RAM on the host
    # The forced scale-down at the end: {"requested", "done" (None = timed out),
    # "sessions", "pools_before", "pools_after", "idle_timeout"}
    scaledown: dict = field(default_factory=dict)
    # Windows clearing their browser data mid-run (clear_seed None: switched off).
    cleared: list[ClearEvent] = field(default_factory=list)
    clear_seed: int | None = None
    # Page loads that did not succeed at the first attempt (mostly
    # ERR_NETWORK_CHANGED while Docker adds or removes pool containers), one
    # entry per load: {"t", "step", "window", "url", "attempts", "outcome"}
    # with outcome "retried", "failed", "timed out" or "fixed before the next step".
    load_log: list[dict] = field(default_factory=list)
    # Seconds the clean-up after the reassignment check took, after `duration`
    # (not part of the run's figures).
    cleanup_seconds: float = 0.0


def load_problems(log: list[dict]) -> tuple[int, int, list[dict]]:
    """(loads that needed a retry, failed attempts, loads that never loaded)
    from PoolTestData.load_log. A load fixed by the reload before the next
    step counts as recovered."""
    never = [e for e in log if e.get("outcome") not in ("retried", "fixed before the next step")]
    attempts = sum(int(e.get("attempts", 1)) - (0 if e in never else 1) for e in log)
    return len(log), attempts, never


def classify(batch: list[Sample]) -> list[str]:
    """State of each sample in one simultaneous read of the windows:
    production, borrowed (sharing a pool only until its own is built), shared
    (with another test window, for good) or own."""
    out = []
    for s in batch:
        if s.route != "HONEYPOT" or s.pool is None:
            out.append(PRODUCTION)
        elif s.waiting:
            out.append(BORROWED)
        elif any(o is not s and o.pool == s.pool and o.route == "HONEYPOT" and not o.waiting
                 for o in batch):
            out.append(SHARED)
        else:
            out.append(OWN)
    return out


def timelines(samples: list[Sample], end: float) -> dict[int, list[tuple[float, float, str, int | None]]]:
    """Per window: (start, end, state, pool) segments, consecutive equal
    states merged; the last one runs until `end`."""
    batches: dict[float, list[Sample]] = {}
    for smp in samples:
        batches.setdefault(smp.t, []).append(smp)
    out: dict[int, list] = {}
    for t in sorted(batches):
        batch = batches[t]
        for smp, state in zip(batch, classify(batch)):
            segs = out.setdefault(smp.window, [])
            pool = smp.pool if state != PRODUCTION else None
            if segs and segs[-1][2] == state and segs[-1][3] == pool:
                continue
            if segs:
                segs[-1] = (segs[-1][0], t, segs[-1][2], segs[-1][3])
            segs.append((t, end, state, pool))
    for segs in out.values():
        if segs:
            segs[-1] = (segs[-1][0], max(end, segs[-1][0]), segs[-1][2], segs[-1][3])
    return out


def _quantile(values: list[float], q: float) -> float:
    v = sorted(values)
    if not v:
        return 0.0
    k = (len(v) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def latency_loads(loads: list[LoadTiming]) -> tuple[list[LoadTiming], bool]:
    """The loads to compare latency on, and whether they are probe loads.
    Probe loads (the same product page, one window at a time) compare like
    with like; the step loads mix pages and run every window at once, so
    they mostly measure the test machine. Step loads only when no probe ran."""
    probes = [x for x in loads if x.probe]
    return (probes, True) if probes else (list(loads), False)


def load_stats(loads: list[LoadTiming]) -> dict[str, dict]:
    """Page-load latency per routing state: n, median, p90, max (ms)."""
    out = {}
    for state in STATES:
        ms = [x.ms for x in loads if x.state == state]
        if ms:
            out[state] = {"n": len(ms), "median": _quantile(ms, 0.5),
                          "p90": _quantile(ms, 0.9), "max": max(ms)}
    return out


@dataclass
class PoolBuild:
    pool: int
    start: float
    seconds: float | None         # None -> still building when the run ended
    ok: bool
    reason: str = ""              # "waiting session" | "reserve" | "spare"
    phases: list[tuple[str, float]] = field(default_factory=list)
    error: str = ""


@dataclass
class BorrowCase:
    """Case A: a session that found no free pool (not scaled yet) and borrowed one."""
    window: int
    borrowed: int | None
    start: float                  # assigned (from the hand-off event when there is one)
    end: float | None             # moved to its own pool / dropped / abandoned / None = waiting
    outcome: str                  # "own" | "dropped" | "abandoned" | "waiting"
    own_pool: int | None = None
    waited: float | None = None   # pool_manager's figure when it handed the pool over
    session_id: str = ""


@dataclass
class LimitCase:
    """Case B: a window's session left on a shared pool for good."""
    window: int
    pool: int | None
    since: float
    shared_with: list[int]        # other test windows on the pool
    how: str                      # "assigned while capped" | "dropped from the wait queue" | ...
    shared_outside: list[str] = field(default_factory=list)   # other owners, described
    session_id: str = ""


@dataclass
class AbandonedSession:
    """A session a window left behind by clearing its data (1.1 / 1.3)."""
    window: int
    session_id: str
    at: float                     # when the window was first seen on another session
    pool: int | None              # the pool it held then (None: production)
    later_pool: int | None = None  # a pool handed to it after it was abandoned


@dataclass
class PoolRemoval:
    pool: int
    at: float                     # removal finished
    seconds: float                # time to remove its containers and volumes
    idle: float | None            # seconds since a request last reached it
    forced: bool                  # requested scale-down, not the idle timeout


@dataclass
class ScalingSummary:
    builds: list[PoolBuild]
    borrow: list[BorrowCase]
    limit: list[LimitCase]
    capped: list[tuple[float, str]]        # (t, reason) each time growth got capped
    reserve: dict                          # {"requested", "start", "reached", "end", "free", "reason"}
    timelines: dict[int, list]
    removals: list[PoolRemoval] = field(default_factory=list)
    released: list[tuple[float, int, int, str]] = field(default_factory=list)  # (t, pool, sessions, reason)
    abandoned: list[AbandonedSession] = field(default_factory=list)
    owners: dict[int, int] = field(default_factory=dict)       # pool -> first window to own it
    # Builds pool_manager started after the scale-down request -- for the
    # sessions the reassignment check parked on a surviving pool -- kept out
    # of the run's builds (they were still running, or were cleaned up again).
    late_builds: list[PoolBuild] = field(default_factory=list)


def session_timelines(samples: list[Sample], end: float) -> dict[tuple[int, str], list]:
    """Like timelines(), but per (window, session id): a window that cleared
    its data and got a new session gets a separate timeline for each, the
    earlier one ending when the window was first seen on the next."""
    batches: dict[float, list[Sample]] = {}
    for smp in samples:
        batches.setdefault(smp.t, []).append(smp)
    out: dict[tuple[int, str], list] = {}
    current: dict[int, str] = {}
    for t in sorted(batches):
        batch = batches[t]
        for smp, state in zip(batch, classify(batch)):
            if not smp.session_id:
                continue
            prev = current.get(smp.window)
            if prev is not None and prev != smp.session_id:
                segs = out[(smp.window, prev)]
                segs[-1] = (segs[-1][0], t, segs[-1][2], segs[-1][3])
            current[smp.window] = smp.session_id
            segs = out.setdefault((smp.window, smp.session_id), [])
            pool = smp.pool if state != PRODUCTION else None
            if segs and segs[-1][2] == state and segs[-1][3] == pool:
                continue
            if segs:
                segs[-1] = (segs[-1][0], t, segs[-1][2], segs[-1][3])
            segs.append((t, end, state, pool))
    return out


def usage_at(usage: list[UsageSample], t: float, after: bool = False) -> UsageSample | None:
    """The last sample at or before `t` (or, with after=True, the first at or after it)."""
    if after:
        return next((u for u in sorted(usage, key=lambda u: u.t) if u.t >= t), None)
    return next((u for u in sorted(usage, key=lambda u: -u.t) if u.t <= t), None)


def _arrival(segs: list, pool: int | None) -> float:
    """When a timeline first held `pool` for real -- as its own or shared,
    not merely borrowed while its own was being built (inf if never)."""
    return next((sg[0] for sg in segs if sg[3] == pool and sg[2] in (OWN, SHARED)), float("inf"))


def run_samples(data: PoolTestData) -> list[Sample]:
    """The routing samples of the run proper: up to the forced scale-down
    request. After it, the reassignment check sends the windows back to the
    shop, the router parks the still-flagged sessions on a surviving pool
    while pool_manager builds new ones -- reads that were counted as
    "borrowed although pools had been pre-built" and "still borrowing at the
    end" for windows that never borrowed during the run."""
    cut = (data.scaledown or {}).get("requested")
    return [s for s in data.samples if cut is None or s.t < cut]


def scaling_summary(data: PoolTestData) -> ScalingSummary:
    """Pool builds, case A (borrowed while scaling) and case B (shared at the
    resource limit) from the samples and pool_manager's event log."""
    starts = {}
    builds: list[PoolBuild] = []
    capped: list[tuple[float, str]] = []
    handoffs: dict[str, dict] = {}
    dropped: dict[str, float] = {}
    intervals: list[list] = []             # [capped at, uncapped at or None]
    removals: list[PoolRemoval] = []
    released: list[tuple[float, int, int, str]] = []
    for e in sorted(data.events, key=lambda e: e.get("at", 0)):
        kind = e.get("type")
        if kind == "build_start":
            starts[e.get("pool")] = e
        elif kind == "build":
            b = starts.pop(e.get("pool"), {})
            builds.append(PoolBuild(int(e.get("pool", 0)), float(e.get("start", e["at"])),
                                    float(e.get("seconds", 0)), bool(e.get("ok")),
                                    b.get("reason", ""),
                                    [(str(n), float(sec)) for n, sec in e.get("phases", [])],
                                    str(e.get("error", ""))))
        elif kind == "capped":
            capped.append((float(e["at"]), str(e.get("reason", ""))))
            intervals.append([float(e["at"]), None])
        elif kind == "uncapped" and intervals and intervals[-1][1] is None:
            intervals[-1][1] = float(e["at"])
        elif kind == "handoff":
            handoffs[str(e.get("session"))] = e
        elif kind == "scaledown":
            removals.append(PoolRemoval(int(e.get("pool", 0)), float(e["at"]),
                                        float(e.get("seconds", 0)),
                                        e.get("idle"), bool(e.get("forced"))))
        elif kind == "released":
            released.append((float(e["at"]), int(e.get("pool", 0)),
                             len(e.get("sessions", [])), str(e.get("reason", ""))))
        elif kind == "dropped_waiting":
            for sid in e.get("sessions", []):
                dropped[str(sid)] = float(e["at"])
    for pool, e in starts.items():   # started during the run, not finished
        builds.append(PoolBuild(int(pool), float(e["at"]), None, False, e.get("reason", "")))
    builds.sort(key=lambda b: b.start)
    cut = (data.scaledown or {}).get("requested")
    late_builds = [b for b in builds if cut is not None and b.start >= cut]
    builds = [b for b in builds if b not in late_builds]
    # Pools the test's own cleanup removed after the reassignment check are
    # not the forced scale-down's removals.
    cleanup_at = ((data.scaledown or {}).get("cleanup") or {}).get("start")
    if cleanup_at is not None:
        removals = [r for r in removals if r.at < cleanup_at]

    samples = run_samples(data)
    tl = timelines(samples, data.duration)
    stl = session_timelines(samples, data.duration)
    order: dict[int, list[str]] = {}            # window -> its sessions, in order
    for (w, sid), segs in sorted(stl.items(), key=lambda kv: kv[1][0][0]):
        order.setdefault(w, []).append(sid)
    last_sid = {w: sids[-1] for w, sids in order.items()}

    abandoned: list[AbandonedSession] = []
    for (w, sid), segs in stl.items():
        if last_sid.get(w) != sid:
            h = handoffs.get(sid)
            abandoned.append(AbandonedSession(w, sid, segs[-1][1], segs[-1][3],
                                              h.get("pool") if h and h["at"] >= segs[-1][1] else None))
    abandoned.sort(key=lambda a: a.at)
    gone = {a.session_id: a for a in abandoned}

    # First window to hold each pool as its own: the pool's owner.
    owners: dict[int, int] = {}
    for (w, sid), segs in sorted(stl.items(), key=lambda kv: kv[1][0][0]):
        for t0, _t1, state, pool in segs:
            if pool is not None and state in (OWN, SHARED):
                if pool not in owners or t0 < owners[pool][0]:
                    owners[pool] = (t0, w)
    owner_of = {p: w for p, (_t, w) in owners.items()}

    borrow: list[BorrowCase] = []
    for (w, sid), segs in sorted(stl.items(), key=lambda kv: (kv[0][0], kv[1][0][0])):
        for i, (t0, t1, state, pool) in enumerate(segs):
            if state != BORROWED or (i and segs[i - 1][2] == BORROWED):
                continue
            h = handoffs.get(sid)
            waited = h.get("waited") if h else None
            # pool_manager knows when the session started waiting; the window
            # only sees it at its next routing read (several seconds later).
            start = h["at"] - waited if h and waited is not None else t0
            nxt = next((sg for sg in segs[i + 1:] if sg[2] != BORROWED), None)
            if sid in gone and nxt is None:
                a_ = gone[sid]
                borrow.append(BorrowCase(w, pool, start, a_.at, "abandoned", a_.later_pool,
                                         waited, sid))
            elif nxt is not None and nxt[2] == OWN:
                borrow.append(BorrowCase(w, pool, start, h["at"] if h else nxt[0], "own",
                                         nxt[3], waited, sid))
            elif sid in dropped or nxt is not None:
                borrow.append(BorrowCase(w, pool, start, dropped.get(sid, nxt[0] if nxt else None),
                                         "dropped", None, None, sid))
            else:
                borrow.append(BorrowCase(w, pool, start, None, "waiting", None, None, sid))

    # A borrow shorter than the gap between two routing reads never shows in
    # the samples: the session's diverting request lands on the borrowed pool
    # and pool_manager hands it its own pool before the next read. Its
    # hand-off event still records it (borrowed pool, wait) -- without it the
    # report listed fewer borrows than the registry counted, and called the
    # borrowed pool's traffic from that window unexplained.
    sid_window = {smp.session_id: smp.window for smp in samples if smp.session_id}
    seen = {c.session_id for c in borrow}
    for sid, h in handoffs.items():
        w = sid_window.get(sid)
        if w is None or sid in seen or (cut is not None and float(h.get("at", 0)) >= cut):
            continue
        waited = h.get("waited")
        at = float(h["at"])
        borrowed = h.get("borrowed")
        borrow.append(BorrowCase(w, int(borrowed) if borrowed is not None else None,
                                 at - float(waited) if waited is not None else at, at, "own",
                                 int(h.get("pool")) if h.get("pool") is not None else None,
                                 waited, sid))
    borrow.sort(key=lambda c: c.start)

    # Case B: a window's CURRENT session sharing its pool for good, with
    # another window (as the later arrival) or with sessions outside the
    # test (the registry counts more owners than windows on the pool).
    registry = (data.pool_state or {}).get("owners", {}) or {}
    finals = {w: stl[(w, sid)][-1] for w, sid in last_sid.items()}
    limit: list[LimitCase] = []
    for w, sid in sorted(last_sid.items()):
        t0, _t1, state, pool = finals[w]
        if pool is None or state not in (OWN, SHARED):
            continue
        segs = stl[(w, sid)]
        arrived = _arrival(segs, pool)
        on_pool = [o for o, f in finals.items() if f[3] == pool and f[2] in (OWN, SHARED)]
        earlier = [o for o in on_pool if o != w
                   and _arrival(stl[(o, last_sid[o])], pool) < arrived]
        outside_n = max(0, int(registry.get(pool, 0) or 0) - len(on_pool))
        outside = []
        for a_ in abandoned:
            if outside_n and (a_.later_pool == pool or (a_.pool == pool and a_.later_pool is None)):
                outside.append(f"window {a_.window + 1}'s abandoned session {a_.session_id[:8]}\u2026")
                outside_n -= 1
        outside += ["a session outside the test"] * outside_n
        if not earlier and not outside:
            continue
        first = next((sg for sg in segs if sg[3] == pool), finals[w])
        capped_then = any(c - 1 <= first[0] and (u is None or first[0] <= u) for c, u in intervals)
        how = ("dropped from the wait queue" if sid in dropped else
               "assigned while capped" if capped_then else "assigned round-robin (no free pool)")
        limit.append(LimitCase(w, pool, first[0], sorted(earlier), how, outside, sid))
    return ScalingSummary(builds, borrow, limit, capped, dict(data.reserve), tl,
                          removals, released, abandoned, owner_of, late_builds)


@dataclass
class Verdict:
    status: str
    headline: str
    findings: list[str]
    by_pool: dict[int, list[str]]   # pool -> labels of the frames bound to it


def sharing_justified(state: dict) -> bool:
    """Whether the registry explains sessions sharing a pool: growth capped,
    sessions still waiting for pools being built, or no free pool and every
    ready pool already owned (round-robin reuse)."""
    if not state:
        return False
    if state.get("capped") or state.get("waiting"):
        return True
    owners = state.get("owners", {})
    ready = state.get("ready", [])
    return not state.get("free") and bool(ready) and all(owners.get(n, 0) >= 1 for n in ready)


# What became of a window whose pool the forced scale-down removed, once it was
# sent back to the shop (reassignment_outcome()).
REASSIGNED, REASSIGN_ERROR, REASSIGN_ESCAPED, REASSIGN_STRANDED, REASSIGN_UNKNOWN = (
    "reassigned", "error", "escaped", "stranded", "unknown")


def reassignment_outcome(r: dict) -> tuple[str, str]:
    """(kind, plain words) for one reassignment record from the forced scale-down:
    {"from": removed pool, "pool": pool after, "route": route after,
     "session_before", "session_after", "status": HTTP status of the page it
     loaded (0 = no response / Chromium error page), "title": page title}.

    A window that was diverted must stay diverted: moved to a surviving pool,
    with the same session, and the page must actually load. A 5xx or an error
    page means the router sent it somewhere that no longer answers (the removed
    pool's container); production or a new session means the attacker walked
    out of the honeypot."""
    status = int(r.get("status") or 0)
    pool, route = r.get("pool"), r.get("route") or ""
    before, after = r.get("session_before") or "", r.get("session_after") or ""
    fresh = bool(before and after and after != before)
    if status == 0 or status >= 500:
        what = f"HTTP {status}" if status else "no response (browser error page)"
        return REASSIGN_ERROR, f"{what} on the next request" + (f" ({r.get('title')})" if r.get("title") else "")
    if pool is not None and pool == r.get("from"):
        return REASSIGN_STRANDED, f"still routed to the removed pool {pool}"
    if pool is not None and not fresh:
        return REASSIGNED, f"moved to surviving pool {pool}, same session"
    if pool is not None:
        return REASSIGN_ESCAPED, f"pool {pool}, but under a new session (its risk history is gone)"
    if route == "PRODUCTION" or not route:
        return REASSIGN_ESCAPED, ("production with a new session" if fresh
                                  else "production with its old session (no longer diverted)")
    return REASSIGN_UNKNOWN, f"route {route.lower()}"


def analyze(frames: list[FrameResult], state: dict, steps: list[StepResult] | None = None,
            cleared: list[ClearEvent] | None = None, reassign: list[dict] | None = None) -> Verdict:
    by_pool: dict[int, list[str]] = {}
    for f in frames:
        if f.pool is not None:
            by_pool.setdefault(f.pool, []).append(f.label)

    seen: dict[str, str] = {}
    merged: list[str] = []
    for f in frames:
        if f.session_id and f.session_id in seen:
            merged.append(f"{seen[f.session_id]} and {f.label}")
        elif f.session_id:
            seen[f.session_id] = f.label
    accepted = [e for e in cleared or [] if e.accepted_forgery()]
    if accepted:
        return Verdict(TAMPER_ACCEPTED, "A forged session cookie was accepted", [
            f"{frames[e.window].label if e.window < len(frames) else e.window + 1} forged its "
            f"SERVERID to claim session {e.claimed_session[:8]} and the stack served it that session."
            for e in accepted] + ["The proxy must reject a cookie whose HMAC doesn't verify "
                                  "(session_identity_rules.verify) and never look its id up."], by_pool)
    if merged:
        return Verdict(MERGED, "Frames were merged into one session", [
            f"{pair} hold the same session id, so they are one user, not two."
            for pair in merged
        ] + ["Each frame needs its own cookie jar and browser fingerprint "
             "(User-Agent / Accept-Language); check that the frames were reset with "
             "'New sessions' before the run."], by_pool)

    # A window that cleared its data and was handed a fresh session it never
    # attacked from again is on production by design, not an unfinished run.
    renewed = {e.window for e in cleared or [] if (e.step, e.window) in session_resets(cleared)}
    fresh = [f.label for i, f in enumerate(frames)
             if i in renewed and f.session_id and f.pool is None]
    missing = [f.label for f in frames if not f.session_id]
    unbound = [f.label for f in frames if f.session_id and f.pool is None and f.label not in fresh]
    if missing or unbound:
        findings = []
        if missing:
            findings.append("No session cookie yet: " + ", ".join(missing)
                            + " (open the shop in that frame first).")
        if unbound:
            findings.append("Session not bound to a pool: " + ", ".join(unbound)
                            + " (the attack has not pushed its score over the diversion "
                              "threshold, or has not been sent).")
        return Verdict(INCOMPLETE, "Not every frame reached a honeypot pool", findings, by_pool)

    failed_moves = []
    for r in reassign or []:
        kind, words = reassignment_outcome(r)
        if kind in (REASSIGN_ERROR, REASSIGN_ESCAPED, REASSIGN_STRANDED):
            w = r.get("window", 0)
            failed_moves.append(f"{frames[w].label if w < len(frames) else w + 1} (was on removed "
                                f"pool {r.get('from')}): {words}.")
    if failed_moves:
        pools = ", ".join(f"{f.label} \u2192 pool {f.pool}" for f in frames)
        return Verdict(REASSIGN_FAILED, "After the scale-down, diverted users were not kept in a "
                       "honeypot", ["Before the scale-down: " + pools + "."] + failed_moves
                       + ["A diverted session whose pool is removed must be moved to a surviving pool "
                          "with its session (and risk) intact, and the page must load."], by_pool)

    moved = sticky_violations(steps or [], session_resets(cleared))
    unstable = bool(moved)
    if steps and any(d.route == "HONEYPOT" for d in steps[0].decisions):
        moved.append("Some windows were already diverted before attacking (step 1): the host "
                     "IP carries bad reputation from earlier tests. Use 'Unpoison host IP' on "
                     "the Attack Simulation page and run the report again.")
    if fresh:
        moved.append(", ".join(fresh) + " cleared browser data, got a fresh session and was "
                     "not diverted again before the run ended, so it is on production.")
    cart_issues = cart_violations(steps or [], cart_resets(cleared))
    unlogged = [e for e in cleared or [] if e.detection() == "not logged"]
    if unlogged:
        moved.append("No rejection was logged for the forged cookie of "
                     + ", ".join(frames[e.window].label for e in unlogged if e.window < len(frames))
                     + " (session_cookie_rejections in Redis), although the stack did not accept it.")
    # The registry counts every session on a pool; more owners than windows
    # on it means it is shared with a session outside the test (e.g. one a
    # window abandoned by clearing its data), even with one window on it.
    registry = (state or {}).get("owners", {}) or {}
    outside = {n: int(registry.get(n, 0) or 0) - len(labels) for n, labels in by_pool.items()
               if int(registry.get(n, 0) or 0) > len(labels)}
    shared = {n: labels for n, labels in by_pool.items() if len(labels) > 1 or n in outside}
    if not shared and cart_issues:
        pools = ", ".join(f"{f.label} \u2192 pool {f.pool}" for f in frames)
        return Verdict(CART_LOST, "A cart changed when its session was routed to a honeypot",
                       [pools + "."] + cart_issues + moved, by_pool)
    if not shared:
        pools = ", ".join(f"{f.label} → pool {f.pool}" for f in frames)
        if unstable:
            return Verdict(UNSTABLE, "Pools are exclusive but a user changed pool",
                           [pools + "."] + moved, by_pool)
        return Verdict(EXCLUSIVE, "Every user has a honeypot pool of their own",
                       [pools + "."] + moved, by_pool)

    findings = [f"Pool {n} is shared by {', '.join(labels)}"
                + (f" and {outside[n]} session(s) outside the test" if n in outside else "") + "."
                for n, labels in sorted(shared.items())]
    if sharing_justified(state):
        if state.get("capped"):
            reason = (f"pool growth is capped ({state.get('capped')}), so further users "
                      "were assigned to the ready pools round-robin")
        elif state.get("waiting"):
            reason = (f"{state.get('waiting')} session(s) were still waiting for the pool "
                      "pool_manager was building for them when the run ended")
        else:
            reason = ("no free pool was left, so new users were assigned to the "
                      "ready pools round-robin")
        return Verdict(SHARED_EXPECTED, "Pools are shared, as expected under resource pressure",
                       findings + [f"This is the designed fallback: {reason}."] + moved + cart_issues, by_pool)
    free = state.get("free", []) if state else []
    findings.append(
        "Sharing is only the designed fallback while pools are being built or once growth "
        "is capped, "
        + (f"but spare pool(s) {', '.join(map(str, free))} were free and growth is not capped."
           if free else "but the registry shows no reason for it (state unavailable or pools missing)."))
    return Verdict(SHARED_UNEXPECTED, "Pools are shared although free pools exist",
                   findings + moved + cart_issues, by_pool)


def capacity_warning(windows: int, delayed: int, state: dict) -> str:
    """Before a run: a warning when the resource limit can't give every window
    a pool of its own, so the round-robin fallback (and, for the delayed
    windows, a pre-build that can't finish) is what the run will show. The
    run releases this machine's sessions first, so every ready pool plus the
    room left under the limit is available to it. "" when it fits or the
    pool_manager status is unknown."""
    status = (state or {}).get("status") or {}
    if "room" not in status:
        return ""
    capacity = len(state.get("ready", [])) + int(status.get("room") or 0)
    if windows <= capacity:
        return ""
    short = windows - capacity
    text = (f"Only {capacity} pool(s) fit in the resource limit, so {short} of the {windows} windows "
            "will share a pool round-robin (case B) instead of getting one of their own.")
    if delayed:
        text += (f" The {delayed} delayed window(s) attack last, so they are the ones most likely "
                 "to find no pre-built pool.")
    per = status.get("mem_per_pool")
    if per:
        text += (f" To fit all windows, raise POOL_MAX_MEMORY_MB / POOL_MAX_CPUS / POOL_MAX, or "
                 f"lower the per-pool charge (now {per:g} MB per pool, POOL_RESERVE_MEM_MB / "
                 "POOL_RESERVE_CPUS) in ids/.env.")
    return text
