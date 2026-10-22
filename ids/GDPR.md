# Consent-gated `gdpr_signature` identity

A second, **privacy-preserving** way for the reverse proxy to recognise a
returning visitor — one that survives the visitor clearing **both** their
cookies and their `localStorage` — layered *alongside* the existing signed
`SERVERID` session cookie, never replacing it. It only ever activates with the
visitor's **explicit, revocable consent**, and the server never stores anything
identifiable about them.

It exists because the signed session cookie and the passive recovery
fingerprint (see [`lua/session_identity_rules.lua`](reverse_proxy_enhanced/lua/session_identity_rules.lua))
can still be shed by a client that clears storage *and* presents a different
TLS/HTTP fingerprint. This adds an orthogonal, consent-based recovery path that
the browser itself reproduces deterministically.

## The flow

```
                         ┌─────────────────────────── browser ──────────────────────────┐
0. GET /                 │                                                               │
1. proxy injects  ──────▶│  gdpr_client.js shows a consent banner                        │
   <script> +            │  fetches /__gdpr/config → { enabled, publicKey, ... }         │
   serves /__gdpr/config │                                                               │
                         │  2. ONLY if "Agree" (and immediately):                        │
                         │     payload = { s:"<screenW>x<screenH>", t:<now> }            │
                         │     gdpr_token = base64( RSA-OAEP-SHA256( payload, pubKey ) )  │
                         │     set cookie gdpr_token; reload                              │
                         └───────────────┬───────────────────────────────────────────────┘
                                         │  gdpr_token cookie on every request
                                         ▼
3. proxy (lua/gdpr_handler.lua), per request, in memory only:
     plaintext   = RSA-OAEP-SHA256-decrypt(gdpr_token, PRIVATE key)   ← key never leaves server
     payload.ip  = $remote_addr        ← client IP the browser can't supply, appended server-side
     if timestamp within GDPR_TIMESTAMP_WINDOW:
         canonical = characteristics (incl. the appended ip) with timestamp stripped (sorted, stable)
         signature = SHA256( deployment-salt | canonical )            ← ONE-WAY, no PII kept
         if  Redis has  gdpr_honeypot_sig:<signature>  (unexpired):
                 prolong its TTL  →  route to honeypot (router Stage 1a)
         else:   fall through to the normal session-token routing
     the plaintext / characteristics are discarded immediately
4. whenever a request that carried a valid signature is routed to the honeypot
   (for ANY reason), the proxy writes  gdpr_honeypot_sig:<signature>  with a
   GDPR_BINDING_TTL TTL — so a later storage wipe + re-consent lands back here.
```

## Why it is privacy-preserving

- **Consent first, and only then.** No token is generated or sent until the
  visitor clicks *Agree*. Decline (or never decide) → the `gdpr_token` cookie is
  never set / is cleared, and the `SERVERID` session stays the only identifier.
- **The browser is the only thing that can produce a token.** The plaintext
  characteristics are recomputed live in the browser each time; only ciphertext
  is ever at rest, so nothing identifying can be read back out of storage. The
  token can't be decrypted without the private key, which never leaves the proxy.
- **The server never stores PII.** The token is decrypted only in memory, only
  long enough to verify the timestamp and compute a **one-way** `SHA256`
  signature. Only that hash is stored, and only for honeypot-bound signatures —
  as a Redis key with a TTL. There is nothing identifiable to delete.
- **Revocation is "just stop sending it."** Because the only server-side record
  is a one-way hash that expires on its own, revoking consent (an empty
  `gdpr_token`) needs no server-side erasure — the signature simply can no
  longer be computed.
- **Deterministic re-recognition.** The same browser yields the same canonical
  characteristics → the same signature, so re-consent after a storage wipe
  reproduces the identity without the server ever having kept it.

## Pieces

| File | Role |
|------|------|
| [`reverse_proxy_enhanced/gdpr_client.js`](reverse_proxy_enhanced/gdpr_client.js) | Client: consent banner, WebCrypto RSA-OAEP token, cookie refresh, revocation UI. Injected into every HTML page by nginx `sub_filter`. |
| [`reverse_proxy_enhanced/lua/gdpr_rules.lua`](reverse_proxy_enhanced/lua/gdpr_rules.lua) | **Pure** logic: timestamp-window check, canonical characteristics, validation. Plain-`lua` testable. |
| [`reverse_proxy_enhanced/lua/gdpr_handler.lua`](reverse_proxy_enhanced/lua/gdpr_handler.lua) | **Adapter**: RSA key load, OAEP decrypt, SHA-256 signature, Redis bindings. Fails open. |
| [`reverse_proxy_enhanced/lua/tests/test_gdpr_rules.lua`](reverse_proxy_enhanced/lua/tests/test_gdpr_rules.lua) | Unit tests for the pure module. |
| `reverse_proxy_enhanced/nginx.conf` | `sub_filter` injection, `/__gdpr/*` endpoints, access-phase integration. |
| `reverse_proxy_enhanced/lua/router.lua` | Stage 1a: route a matched signature to the honeypot. |

## Configuration (`.env`)

| Variable | Default | Meaning |
|----------|---------|---------|
| `GDPR_ENABLED` | `true` | `false` disables the whole subsystem (client script goes inert). |
| `GDPR_PRIVATE_KEY` | *(demo key)* | RSA private key, **base64 DER (PKCS#8), one line**. The only secret; the public key is derived from it and never drifts. Regenerate with `openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -outform DER \| base64 -w0`. |
| `GDPR_TIMESTAMP_WINDOW` | `300` | Seconds a token's timestamp may be from "now" (replay window). |
| `GDPR_BINDING_TTL` | `3600` | Lifetime of a honeypot↔signature binding in Redis; prolonged on every match. |

## Endpoints (served by the proxy, no routing pipeline)

- `GET /__gdpr/gdpr.js` — the client script.
- `GET /__gdpr/config` — `{ enabled, publicKey, cookieName, windowSeconds, refreshSeconds }`.
- `GET /__gdpr/pubkey` — base64 SPKI public key (debugging).

## Demo limitation (by design)

For this demo the browser supplies a single characteristic, the **screen
size**, to which the proxy adds the **client IP** server-side before signing.
Both are low-entropy: many unrelated visitors share a resolution, and an IP is
shared behind NAT and changes as a visitor moves between networks (so the same
browser then re-signs under a new signature). That is acceptable for
demonstrating the mechanism — the signature is salted per-deployment and the
honeypot binding is explicit and expiring — but a real deployment would combine
several higher-entropy characteristics before the signature became meaningfully
distinguishing. These two inputs are used purely to keep the demo legible.
