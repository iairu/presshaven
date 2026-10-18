"""The detection knobs of the edge stack as a structured, validated model
(Qt-free): which .env keys the reverse proxy genuinely reads for scoring
and reputation, their type/range/meaning, and helpers to read, validate and
write them back into an EnvFile. Only keys wired end-to-end (.env ->
docker-compose.yml -> nginx `env` directive -> init.lua) are listed; the
honeypot threshold itself (80) is a constant in init.lua, not a setting.

decay_preview()/seconds_to_fall_below() mirror decay_policy.decay()'s
exponential half-life (peak * 0.5^(elapsed/half_life)) for the page's
"what does this setting mean" text."""
from __future__ import annotations

import math
from dataclasses import dataclass

from core.env_file import EnvFile

HONEYPOT_THRESHOLD = 80
SCORE_MAX = 100


@dataclass(frozen=True)
class Knob:
    key: str
    label: str
    kind: str            # "bool" | "int"
    default: str
    help: str
    minimum: int = 0
    maximum: int = 0
    unit: str = ""


KNOBS: list[Knob] = [
    Knob("THREAT_DECAY_ENABLED", "Score decay", "bool", "true",
         "Whether a session's / IP's risk score fades once no new suspicious signal arrives. "
         "Off: a score, once earned, persists until it is reset."),
    Knob("SCORE_DECAY_HALF_LIFE_SECONDS", "Decay half-life", "int", "300",
         "How long a score takes to fall to half its value with no new signal (larger = slower fade). "
         "Repeat offenders decay more slowly.", 10, 86400, "s"),
    Knob("IP_REPUTATION_CAP", "IP reputation cap", "int", "10",
         "The most an address's reputation (Suricata alerts, AbuseIPDB) adds to a request's score. "
         "The default can never divert anyone on its own; above 50, bad addresses are diverted again.",
         0, 100, "points"),
    Knob("SHARED_IP_SESSIONS", "Shared-address session count", "int", "2",
         "How many distinct sessions on one address make it 'shared' (NAT, offices); a shared address's "
         "reputation stops counting.", 1, 100, "sessions"),
    Knob("SHARED_IP_WINDOW", "Shared-address window", "int", "3600",
         "The time window in which those sessions are counted.", 60, 86400, "s"),
    Knob("ABUSEIPDB_CONFIDENCE_MINIMUM", "AbuseIPDB minimum confidence", "int", "90",
         "Minimum AbuseIPDB confidence (0-100) for an address to be pulled into the bulk blacklist feed.",
         0, 100, "%"),
]
KNOB_BY_KEY = {k.key: k for k in KNOBS}

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _clean(raw: str) -> str:
    return raw.strip().strip("\"'").strip()


def read_values(env) -> dict[str, str]:
    """{key: normalised value} for every knob, from anything with
    .get(key, default); missing keys give the default, unparseable ones
    too."""
    out = {}
    for k in KNOBS:
        out[k.key] = normalise(k, env.get(k.key, k.default)) or k.default
    return out


def normalise(knob: Knob, raw: str) -> str | None:
    """The canonical text for `raw` ("true"/"false" or a plain integer), or
    None when it isn't valid for the knob (wrong type or out of range)."""
    text = _clean(str(raw))
    if knob.kind == "bool":
        if text.lower() in _TRUE:
            return "true"
        if text.lower() in _FALSE:
            return "false"
        return None
    try:
        value = int(text)
    except ValueError:
        return None
    return str(value) if knob.minimum <= value <= knob.maximum else None


def validate(values: dict[str, str]) -> dict[str, str]:
    """{key: error message} for every invalid entry (empty when all fine)."""
    errors = {}
    for key, raw in values.items():
        knob = KNOB_BY_KEY.get(key)
        if knob is None:
            errors[key] = "unknown setting"
        elif normalise(knob, raw) is None:
            errors[key] = ("must be true or false" if knob.kind == "bool"
                           else f"must be a whole number from {knob.minimum} to {knob.maximum}")
    return errors


def changes(env, values: dict[str, str]) -> dict[str, str]:
    """The subset of `values` that differs from what `env` currently holds
    (compared after normalisation), normalised."""
    current = read_values(env)
    out = {}
    for key, raw in values.items():
        knob = KNOB_BY_KEY[key]
        new = normalise(knob, raw)
        if new is not None and new != current[key]:
            out[key] = new
    return out


def apply_to(env: EnvFile, values: dict[str, str]) -> dict[str, str]:
    """Writes the changed, valid values into `env` (comments and every
    other key untouched) and returns what was changed."""
    errors = validate(values)
    if errors:
        raise ValueError("; ".join(f"{k}: {m}" for k, m in errors.items()))
    diff = changes(env, values)
    for key, value in diff.items():
        env.set(key, value)
    return diff


# ---- decay explanation ----

def decayed(peak: float, elapsed: float, half_life: float) -> float:
    return peak * (0.5 ** (elapsed / half_life)) if half_life > 0 else peak


def seconds_to_fall_below(half_life: float, peak: float = SCORE_MAX,
                          threshold: float = HONEYPOT_THRESHOLD) -> float:
    """Seconds for an unrefreshed score of `peak` to fall under `threshold`
    (base half-life: first offence)."""
    if peak <= threshold or half_life <= 0:
        return 0.0
    return half_life * math.log2(peak / threshold)


def decay_summary(enabled: bool, half_life: int) -> str:
    if not enabled:
        return "Decay is off: a maxed score (100) never falls back under the honeypot threshold on its own."
    to_threshold = seconds_to_fall_below(half_life)
    to_quarter = decayed(SCORE_MAX, half_life * 2, half_life)
    return (f"With a {half_life}s half-life, a maxed score (100) drops under the honeypot threshold "
            f"({HONEYPOT_THRESHOLD}) after about {to_threshold:.0f}s, to half after {half_life}s and to "
            f"{to_quarter:.0f} after {half_life * 2}s without new signals (first offence; repeat offenders fade slower).")
