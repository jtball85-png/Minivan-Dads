"""Live-check research tools for department agents. Read-only HTTP lookups
— checking whether a URL exists doesn't write, spend, or commit anything,
so per the action-layer spec these bypass the executor entirely and stay
inside Tier 0. Stdlib-only (urllib), no new dependency.

Honesty is the point of this module, not just correctness: search-index
"no hits found" is weak signal; these functions give a real live-web
answer where one is obtainable, and say plainly "inconclusive" where
platforms actively block unauthenticated checks (X above all) rather than
pretend a confidence the check doesn't have.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

TIMEOUT = 12  # RDAP can be slow for less common TLDs (.shop timed out at 8s in testing)
USER_AGENT = "Mozilla/5.0 (compatible; MinivanDadsResearch/1.0; +read-only availability check)"
COMMON_HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json",
                  "Accept-Language": "en-US,en;q=0.9"}

# Per-platform behavior. mode="live_check" does a real HTTP fetch and trusts
# the not_found_markers text; mode="unverifiable" skips the network call
# entirely and always reports inconclusive, because we have EVIDENCE (not
# just suspicion) that no reliable signal exists for that platform:
#
# - x: the platform actively blocks unauthenticated checks (HTTP-level).
# - instagram / tiktok: proven unreliable by direct test — a nonsense
#   handle that cannot possibly be registered (e.g.
#   "zzqxnonexistenthandle999xyz") still returned "taken_or_exists",
#   because both are JS-rendered single-page apps whose "this page isn't
#   available" message is injected client-side and never appears in the
#   raw server HTML this tool fetches. A marker that never fires isn't
#   medium confidence, it's ALWAYS "taken" regardless of truth — worse
#   than no answer, so this returns "we don't know" instead of guessing.
PLATFORM_CONFIG = {
    "instagram": {
        "url": "https://www.instagram.com/{handle}/",
        "mode": "unverifiable",
        "note": "Instagram is a JS-rendered app — its 'page not found' message "
                "never appears in the raw HTML this tool fetches, so a 'taken' "
                "result would be indistinguishable from an available one "
                "(verified with a nonsense-handle test). Cannot verify.",
    },
    "tiktok": {
        "url": "https://www.tiktok.com/@{handle}",
        "mode": "unverifiable",
        "note": "TikTok is a JS-rendered app with the same limitation as "
                "Instagram — verified with a nonsense-handle test. Cannot verify.",
    },
    "etsy": {
        "url": "https://www.etsy.com/shop/{handle}",
        "mode": "live_check",
        "confidence": "high",  # Etsy returns a real HTTP 404 for missing shops
        "not_found_markers": [],
    },
    "x": {
        "url": "https://x.com/{handle}",
        "mode": "unverifiable",
        "note": "X blocks unauthenticated availability checks outright.",
    },
}


def check_domain(domain: str) -> dict:
    """RDAP lookup (free, public, no API key) — the reliable one. 200 =
    registered; 404 = not found in any registry, i.e. available."""
    domain = domain.strip().lower()
    url = f"https://rdap.org/domain/{domain}"
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/rdap+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            if resp.status == 200:
                return {"domain": domain, "status": "registered", "confidence": "high"}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"domain": domain, "status": "available", "confidence": "high"}
        return {"domain": domain, "status": "unknown", "confidence": "low",
                "note": f"RDAP returned HTTP {e.code}"}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"domain": domain, "status": "unknown", "confidence": "low",
                "note": f"lookup failed: {e}"}
    return {"domain": domain, "status": "unknown", "confidence": "low"}


def check_handle(platform: str, handle: str) -> dict:
    """Live profile-page check. Confidence varies by platform — see
    PLATFORM_CONFIG — because most social sites are JS single-page apps
    that don't return honest HTTP status codes for missing users."""
    platform = platform.strip().lower()
    handle = handle.strip().lstrip("@")
    cfg = PLATFORM_CONFIG.get(platform)
    if cfg is None:
        return {
            "platform": platform, "handle": handle, "status": "unsupported_platform",
            "confidence": "n/a",
            "note": f"supported platforms: {', '.join(PLATFORM_CONFIG)}",
        }
    if cfg["mode"] == "unverifiable":
        return {
            "platform": platform, "handle": handle, "status": "inconclusive",
            "confidence": "unverifiable", "note": cfg["note"],
        }

    url = cfg["url"].format(handle=handle)
    req = urllib.request.Request(url, headers=COMMON_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(20_000).decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"platform": platform, "handle": handle, "status": "available",
                    "confidence": cfg["confidence"]}
        return {"platform": platform, "handle": handle, "status": "inconclusive",
                "confidence": "low", "note": f"HTTP {e.code} — platform may be rate-limiting"}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"platform": platform, "handle": handle, "status": "inconclusive",
                "confidence": "low", "note": f"lookup failed: {e}"}

    if any(marker.lower() in body.lower() for marker in cfg["not_found_markers"]):
        return {"platform": platform, "handle": handle, "status": "available",
                "confidence": cfg["confidence"]}
    return {"platform": platform, "handle": handle, "status": "taken_or_exists",
            "confidence": cfg["confidence"]}


# -- Anthropic tool-use schemas + dispatcher, for wiring into llm.py --------

TOOL_SCHEMAS = [
    {
        "name": "check_domain_availability",
        "description": (
            "Check whether a domain name is currently registered, via a live "
            "RDAP registry lookup (not a search-index guess). High confidence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"domain": {"type": "string", "description": "e.g. minivandads.com"}},
            "required": ["domain"],
        },
    },
    {
        "name": "check_handle_availability",
        "description": (
            "Check whether a username/handle is taken on a specific platform, "
            "via a live request to that platform (not a search-index guess). "
            "Only etsy gives a real answer (high confidence, real HTTP 404s); "
            "instagram, tiktok, and x always return 'inconclusive' — verified "
            "unreliable/blocked, not a guess dressed up as medium confidence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": list(PLATFORM_CONFIG)},
                "handle": {"type": "string", "description": "without the @"},
            },
            "required": ["platform", "handle"],
        },
    },
]


def execute_tool(name: str, tool_input: dict) -> dict:
    if name == "check_domain_availability":
        return check_domain(tool_input["domain"])
    if name == "check_handle_availability":
        return check_handle(tool_input["platform"], tool_input["handle"])
    return {"error": f"unknown tool {name!r}"}
