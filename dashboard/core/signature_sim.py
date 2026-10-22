"""Live, end-to-end demonstration of the consent-gated gdpr_token ->
gdpr_signature flow, for the dashboard's Signature Simulation page.

It reproduces, against the RUNNING reverse proxy, exactly the path ids/GDPR.md
describes, so a student can watch one browser characteristic -- the screen
size, here driven by a resizeable window -- turn into the one-way signature the
proxy derives, including the client IP the proxy now appends SERVER-SIDE
(lua/gdpr_handler.lua) just before it hashes.

Client half (reproduced here from Python, mirroring gdpr_client.js via
core.gdpr_token.GdprConsent):
  1. characteristics = { s: "<W>x<H>" }         -- from the resizeable window
  2. payload         = characteristics + { t }  -- a fresh timestamp
  3. gdpr_token      = base64( RSA-OAEP-SHA256( payload, proxy public key ) )
     (the public key comes from GET /__gdpr/config.)

Server half (OBSERVED, never reproduced -- the signature salt and the private
key never leave the proxy, and the raw characteristics are never revealed
back): we send one real request carrying the token, and the proxy logs
  "[GDPR] Received gdpr_signature=<hex> | Session: <id>"
(nginx.conf, at info level, to stdout). We read that line back from the proxy's
own container logs. The signature is the ONLY thing that comes out of the
server half -- which is the whole privacy point of the design.

Qt-free so it is unit-testable (see extract_signature); the UI half lives in
ui/page_signature_sim.py.
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass

from core import pattern_log_parser
from core.docker_ctl import Target
from core.gdpr_token import GdprConsent

# The reverse-proxy service whose logs carry the derived-signature line (same
# service the Attack Simulation page's security feed tails).
PROXY_SERVICE = "reverse_proxy"

# How many recent proxy log lines to scan for the signature line. Bounded so a
# busy log is cheap to read, but large enough that our just-sent request's line
# is comfortably inside it right after we send.
_LOG_TAIL = 500


@dataclass
class FlowResult:
    """One run of the flow. ``ok`` is True only when a signature came back.
    Partial runs still carry whatever earlier stages produced (so the UI can
    show the client side even when the proxy half fails)."""
    ok: bool = False
    error: str = ""
    # Furthest stage reached: "config" | "encrypt" | "request" | "signature".
    stage: str = "config"
    screen: str = ""          # the "WxH" characteristic that was signed
    timestamp: int = 0        # the payload timestamp (stripped before signing)
    payload_json: str = ""    # the exact plaintext that was encrypted
    token_b64: str = ""       # the gdpr_token the browser would send
    http_status: str = ""     # the proxy's response status line to our request
    session_id: str = ""      # the SERVERID session the proxy logged it under
    signature: str = ""       # the one-way gdpr_signature the proxy derived


def extract_signature(log_text: str) -> tuple[str, str]:
    """``(signature, session)`` from the MOST RECENT
    ``[GDPR] Received gdpr_signature=<hex> | Session: <id>`` line in a proxy
    log tail, or ``("", "")`` when none is present.

    Reuses core.pattern_log_parser so the docker-prefix / ANSI / timestamp /
    trailing ``, client: ...`` stripping is shared with the Attack Simulation
    page (and stays correct if those shapes change in one place). ``session``
    is "" when the matched line carried no session.
    """
    sig, session = "", ""
    for raw in log_text.splitlines():
        ev = pattern_log_parser.parse_line(raw)
        if ev is None or ev.kind != "gdpr":
            continue
        # ev.detail is "Signature: <hex>" or "Signature: <hex> | Session: <id>".
        body = ev.detail.split("Signature:", 1)[-1].strip()
        value, sep, sess = body.partition("| Session:")
        sig, session = value.strip(), (sess.strip() if sep else "")
    return sig, session


def _payload_preview(characteristics: dict, ts: int) -> str:
    """The exact JSON the browser encrypts: the characteristics plus a
    timestamp, compact and key-order-matching core.gdpr_token.token()."""
    payload = dict(characteristics)
    payload["t"] = ts
    return json.dumps(payload, separators=(",", ":"))


def _send(base: str, cookie_name: str, token: str, timeout: int) -> tuple[str, str]:
    """Send ONE request to ``base + "/"`` carrying only the gdpr_token cookie
    (no session cookie, so the proxy mints a fresh session we can tell apart
    from earlier runs). Returns ``(status_line, error)``."""
    argv = ["curl", "-sk", "-o", "/dev/null", "-D", "-", "--max-time", str(timeout),
            "-b", f"{cookie_name}={token}", base.rstrip("/") + "/"]
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=timeout + 5)
    except (subprocess.SubprocessError, OSError) as e:
        return "", f"Request to the proxy failed: {e}"
    status = ""
    for line in out.stdout.splitlines():
        if line.startswith("HTTP/"):
            status = line.strip()   # keep the last (post-redirect) status
    return status or "(request sent)", ""


def _read_signature(target: Target) -> tuple[str, str]:
    """The most recent logged ``(signature, session)`` from the proxy's log
    tail, or ``("", "")`` on any docker/ssh failure."""
    argv, cwd = target.build("logs", f"--tail={_LOG_TAIL}", "--timestamps", PROXY_SERVICE)
    try:
        out = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=20)
    except (subprocess.SubprocessError, OSError):
        return "", ""
    return extract_signature(out.stdout)


def run_flow(base_url: str, target: Target, screen: str, *,
             timeout: int = 15, log_attempts: int = 8, log_gap_s: float = 0.5) -> FlowResult:
    """Run the whole flow once for the ``screen`` characteristic (``"WxH"``).

    Reads the proxy's public key, mints a gdpr_token, sends one request
    carrying it, then polls the proxy log until the NEW derived-signature line
    appears (identified by a session id different from the one logged before we
    sent -- a fresh request always gets a fresh session, so this stays correct
    even when the signature itself repeats, which is the re-recognition the
    page is there to show)."""
    res = FlowResult(screen=screen)
    base = base_url.rstrip("/")
    characteristics = {"s": screen}

    consent = GdprConsent.acquire(base, timeout=timeout)
    if consent is None:
        res.error = ("The proxy's GDPR subsystem is disabled or could not be reached. "
                     "Start the ids stack and ensure reverse_proxy is up with GDPR enabled.")
        return res

    try:
        res.timestamp = int(time.time())
        res.payload_json = _payload_preview(characteristics, res.timestamp)

        token = consent.token(characteristics)
        if not token:
            res.stage = "encrypt"
            res.error = "Could not encrypt the gdpr_token (is the openssl CLI available?)."
            return res
        res.token_b64 = token
        res.stage = "request"

        # What the proxy last logged BEFORE our request, so we can recognise
        # the line our own request produces (by its fresh session id).
        _before_sig, before_session = _read_signature(target)

        res.http_status, err = _send(base, consent.cookie_name, token, timeout)
        if err:
            res.error = err
            return res

        # The proxy writes the line asynchronously; poll briefly for the fresh one.
        for _ in range(log_attempts):
            time.sleep(log_gap_s)
            sig, session = _read_signature(target)
            if sig and (before_session == "" or session != before_session):
                res.signature, res.session_id = sig, session
                res.stage = "signature"
                res.ok = True
                return res

        res.error = ("The token was sent, but no new gdpr_signature line appeared in the "
                     "proxy log. The token may have been rejected (clock skew or an expired "
                     "timestamp), or GDPR is disabled on the proxy.")
        return res
    finally:
        consent.cleanup()
