"""Client-side GDPR consent token for the dashboard's automated test traffic.

The Attack Simulation and Segmentation Validation report exports run automated
requests against the reverse proxy. When the operator agrees to GDPR for that
run, this module reproduces -- from Python -- exactly what the in-browser
reverse_proxy_enhanced/gdpr_client.js does: it fetches the proxy's RSA public
key (GET /__gdpr/config), then RSA-OAEP(SHA-256)-encrypts a small payload
(characteristics -- here a screen size -- plus a fresh timestamp) into a
``gdpr_token`` the automated requests carry as a cookie. The proxy decrypts it,
derives the one-way gdpr_signature and routes accordingly (see ids/GDPR.md).

The dashboard has no Python crypto dependency, so this shells out to the
``openssl`` CLI. The OAEP parameters (``rsa_oaep_md:sha256`` /
``rsa_mgf1_md:sha256``) match WebCrypto's ``RSA-OAEP`` with ``hash: "SHA-256"``,
which is what gdpr_client.js and lua/gdpr_handler.lua use. Everything degrades
gracefully: if the proxy has GDPR disabled or is unreachable, acquire() returns
None and callers simply run without a token (session cookie only).
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
from typing import Optional


class GdprConsent:
    """A live consent: holds the proxy's public key and mints fresh tokens.

    Construct via :meth:`acquire`. Call :meth:`curl_args` (for curl-based
    traffic) or :meth:`cookie_value` (for a browser cookie store) with the
    characteristics to sign; each call re-stamps the timestamp so the token is
    always inside the proxy's freshness window. Call :meth:`cleanup` when done.
    """

    def __init__(self, pub_pem_path: str, window_s: int, cookie_name: str, tmpdir: str):
        self._pub_pem = pub_pem_path
        self.window_s = window_s
        self.cookie_name = cookie_name
        self._tmpdir = tmpdir

    @classmethod
    def acquire(cls, base_url: str, *, timeout: int = 10) -> Optional["GdprConsent"]:
        """Fetch the proxy's GDPR config/public key and prepare for signing.

        Returns None (never raises) when GDPR is disabled on the proxy, the
        proxy is unreachable, or openssl is unavailable -- callers treat that as
        "run without a consent token".
        """
        base = base_url.rstrip("/")
        try:
            res = subprocess.run(
                ["curl", "-sk", "--max-time", str(timeout), base + "/__gdpr/config"],
                capture_output=True, text=True, timeout=timeout + 5)
        except (subprocess.SubprocessError, OSError):
            return None
        if res.returncode != 0 or not res.stdout.strip():
            return None
        try:
            cfg = json.loads(res.stdout)
        except (ValueError, TypeError):
            return None
        if not cfg.get("enabled") or not cfg.get("publicKey"):
            return None
        try:
            der = base64.b64decode(cfg["publicKey"])
        except (ValueError, TypeError):
            return None

        tmpdir = tempfile.mkdtemp(prefix="gdpr_consent_")
        der_path = os.path.join(tmpdir, "pub.der")
        pem_path = os.path.join(tmpdir, "pub.pem")
        try:
            with open(der_path, "wb") as fh:
                fh.write(der)
            # openssl's pkeyutl -encrypt wants a key file; convert the SPKI DER
            # the proxy served into PEM once, here, and reuse it per token.
            conv = subprocess.run(
                ["openssl", "pkey", "-pubin", "-inform", "DER",
                 "-in", der_path, "-out", pem_path],
                capture_output=True, text=True, timeout=10)
        except (subprocess.SubprocessError, OSError):
            shutil.rmtree(tmpdir, ignore_errors=True)
            return None
        if conv.returncode != 0 or not os.path.exists(pem_path):
            shutil.rmtree(tmpdir, ignore_errors=True)
            return None

        window_s = int(cfg.get("windowSeconds") or 300)
        cookie_name = cfg.get("cookieName") or "gdpr_token"
        return cls(pem_path, window_s, cookie_name, tmpdir)

    def token(self, characteristics: dict) -> Optional[str]:
        """A freshly stamped, base64 gdpr_token for ``characteristics`` (a dict
        of identifying values, e.g. ``{"s": "1920x1080"}``), or None on failure."""
        payload = dict(characteristics)
        payload["t"] = int(time.time())
        data = json.dumps(payload, separators=(",", ":")).encode()
        try:
            res = subprocess.run(
                ["openssl", "pkeyutl", "-encrypt", "-pubin", "-inkey", self._pub_pem,
                 "-pkeyopt", "rsa_padding_mode:oaep",
                 "-pkeyopt", "rsa_oaep_md:sha256",
                 "-pkeyopt", "rsa_mgf1_md:sha256"],
                input=data, capture_output=True, timeout=10)
        except (subprocess.SubprocessError, OSError):
            return None
        if res.returncode != 0 or not res.stdout:
            return None
        return base64.b64encode(res.stdout).decode()

    def cookie_value(self, characteristics: dict) -> Optional[str]:
        """Alias for :meth:`token` -- the value to put in a ``gdpr_token`` cookie."""
        return self.token(characteristics)

    def curl_args(self, characteristics: dict) -> list:
        """``["-b", "gdpr_token=<token>"]`` for a curl invocation, or ``[]`` if a
        token could not be minted (so the request still goes out, untokened)."""
        tok = self.token(characteristics)
        if not tok:
            return []
        return ["-b", f"{self.cookie_name}={tok}"]

    def cleanup(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)
