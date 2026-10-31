#!/usr/bin/env python3
"""Replace placeholder / missing / weak secrets in ids/.env with strong random
values. Prints key names only, never values. Backs up .env first (0600).

  python3 scripts/generate_secrets.py [path/to/.env]

Generated: every database password (production, pools 1-3, the db-proxy
honeypot database -- each user and root password distinct), Redis, session
manager, internal test secret, session signing key, WordPress salts and a new
GDPR RSA key. External credentials (AbuseIPDB, Elasticsearch) cannot be
generated: a placeholder there is blanked, which disables that integration.
Rotating them logs everyone out and needs a full `docker compose down && up`.
"""
import base64
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

EDGE = Path(__file__).resolve().parent.parent
EXAMPLE = EDGE / ".env.example"

HEX32 = [
    "MYSQL_ROOT_PASSWORD", "MYSQL_PASSWORD",
    *[f"MYSQL_PASSWORD_POOL_{n}" for n in (1, 2, 3)],
    *[f"MYSQL_ROOT_PASSWORD_POOL_{n}" for n in (1, 2, 3)],
    "HONEYPOT_DB_PASSWORD", "HONEYPOT_MYSQL_ROOT_PASSWORD",
    "REDIS_PASSWORD", "SESSION_MANAGER_SECRET", "INTERNAL_TEST_SECRET", "SESSION_SIGNING_KEY",
    *[f"WORDPRESS_{k}" for k in ("AUTH_KEY", "SECURE_AUTH_KEY", "LOGGED_IN_KEY", "NONCE_KEY",
                                 "AUTH_SALT", "SECURE_AUTH_SALT", "LOGGED_IN_SALT", "NONCE_SALT")],
]
ADMIN = ["WP_ADMIN_PASSWORD", "HONEYPOT_WP_ADMIN_PASSWORD"]
EXTERNAL = ["ABUSEIPDB_API_KEY", "ELASTICSEARCH_PASSWORD"]
PLACEHOLDER = re.compile(r"change_this|your_|changeme|example", re.I)


def parse(text):
    return {m.group(1): m.group(2) for m in re.finditer(r"^([A-Z0-9_]+)=(.*)$", text, re.M)}


def gdpr_key():
    der = subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
                          "rsa_keygen_bits:2048", "-outform", "DER"],
                         check=True, capture_output=True).stdout
    return base64.b64encode(der).decode()


def plan(cur, example):
    """{key: new value} for every secret in `cur` (a parsed .env) that is
    missing, a placeholder, the .env.example value or too short. A blank
    value means "clear this external credential". Shared with the dashboard
    (Settings -> ids .env -> Generate weak secrets)."""
    def weak(k, min_len):
        v = cur.get(k, "")
        return (not v or len(v) < min_len or PLACEHOLDER.search(v)
                or (example.get(k) and v == example[k]))

    new = {}
    for k in HEX32:
        if weak(k, 32):
            new[k] = secrets.token_hex(32)
    for k in ADMIN:
        if weak(k, 16):
            new[k] = secrets.token_urlsafe(21).replace("-", "x").replace("_", "y")
    if weak("GDPR_PRIVATE_KEY", 1000):
        new["GDPR_PRIVATE_KEY"] = gdpr_key()
    for k in EXTERNAL:
        if cur.get(k) and (PLACEHOLDER.search(cur[k]) or cur[k] == example.get(k)):
            new[k] = ""
    # No two secrets may share a value (regenerate the newcomer on a clash).
    merged = {**cur, **new}
    seen = {}
    for k in HEX32 + ADMIN:
        v = merged.get(k)
        if v and v in seen:
            new[k] = merged[k] = secrets.token_hex(32)
        seen[merged.get(k)] = k
    return new


def backup(env):
    """Copy `env` to .env.bak.<timestamp> (0600) and return the copy's path."""
    path = env.with_name(f".env.bak.{time.strftime('%Y%m%d%H%M%S')}")
    shutil.copy2(env, path)
    path.chmod(0o600)
    return path


def main():
    env = Path(sys.argv[1]) if len(sys.argv) > 1 else EDGE / ".env"
    text = env.read_text()
    new = plan(parse(text), parse(EXAMPLE.read_text()))
    if not new:
        print(".env: nothing to change")
        return
    saved = backup(env)
    for k, v in new.items():
        if re.search(rf"^{k}=.*$", text, re.M):
            text = re.sub(rf"^{k}=.*$", lambda _m: f"{k}={v}", text, count=1, flags=re.M)
        else:
            text = text.rstrip("\n") + f"\n{k}={v}\n"
    env.write_text(text)
    env.chmod(0o600)
    print(f"backup: {saved}")
    print("generated:", ", ".join(k for k in new if new[k]))
    blanked = [k for k in new if not new[k]]
    if blanked:
        print("blanked (placeholder external credential, integration now disabled):", ", ".join(blanked))

if __name__ == "__main__":
    main()
