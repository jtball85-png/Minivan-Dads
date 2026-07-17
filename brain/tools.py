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

# Per-platform behavior. "confidence" describes how much a clean result can
# be trusted; not_found_markers are text fragments that show up on that
# platform's own "doesn't exist" page even when it returns HTTP 200 (most
# social platforms are single-page apps that don't use real 404s).
PLATFORM_CONFIG = {
    "instagram": {
        "url": "https://www.instagram.com/{handle}/",
        "confidence": "medium",
        "not_found_markers": ["Sorry, this page"],
    },
    "tiktok": {
        "url": "https://www.tiktok.com/@{handle}",
        "confidence": "medium",
        "not_found_markers": ["Couldn't find this account", "user-post"],
    },
    "etsy": {
        "url": "https://www.etsy.com/shop/{handle}",
        "confidence": "high",  # Etsy returns a real HTTP 404 for missing shops
        "not_found_markers": [],
    },
    "x": {
        "url": "https://x.com/{handle}",
        "confidence": "blocked",  # X blocks unauthenticated checks outright
        "not_found_markers": [],
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
    if cfg["confidence"] == "blocked":
        return {
            "platform": platform, "handle": handle, "status": "inconclusive",
            "confidence": "blocked",
            "note": "X blocks unauthenticated availability checks — this tool "
                    "cannot verify X handles. Report this limitation, don't guess.",
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
            "Confidence varies by platform: etsy=high, instagram/tiktok=medium "
            "(JS apps, best-effort), x=always inconclusive (platform blocks this)."
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
