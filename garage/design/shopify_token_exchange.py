"""One-time Shopify OAuth token exchange — the "backend" the dev-dashboard
app flow assumes, run locally instead of hosted.

Shopify's install flow hands the browser a short-lived, single-use ?code=…
on the registered redirect URL; the permanent offline access token
(shpat_…) is only returned by a non-browser POST to
/admin/oauth/access_token carrying client_id + client_secret + code.
This script is that POST. See docs/… none — garage-only, run at most a
handful of times per app install.

Usage:
  .venv/Scripts/python.exe garage/design/shopify_token_exchange.py \
      "<full redirect URL pasted from the browser address bar>" \
      [--state <expected-state-nonce>]

Reads SHOPIFY_CLIENT_ID / SHOPIFY_CLIENT_SECRET from .env. On success,
appends/updates SHOPIFY_ACCESS_TOKEN and SHOPIFY_STORE_DOMAIN in .env.
The token itself is NEVER printed — only a masked prefix and the granted
scopes, so transcripts/logs don't collect another copy of a secret.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent.parent
ENV_PATH = REPO / ".env"


def set_env_var(name: str, value: str) -> None:
    """Idempotently set NAME=value in .env (replace existing line or append)."""
    text = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    pattern = re.compile(rf"^{re.escape(name)}=.*$", flags=re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub(f"{name}={value}", text)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += f"{name}={value}\n"
    ENV_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("redirect_url", help="full URL the browser landed on after approval")
    ap.add_argument("--state", default=None, help="expected state nonce from the authorize URL")
    args = ap.parse_args()

    env = dotenv_values(ENV_PATH)
    client_id = env.get("SHOPIFY_CLIENT_ID")
    client_secret = env.get("SHOPIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("SHOPIFY_CLIENT_ID / SHOPIFY_CLIENT_SECRET missing from .env")

    query = urllib.parse.parse_qs(urllib.parse.urlparse(args.redirect_url).query)
    code = (query.get("code") or [None])[0]
    shop = (query.get("shop") or [None])[0]
    state = (query.get("state") or [None])[0]
    if not code or not shop:
        sys.exit(f"redirect URL missing code/shop params — got keys: {sorted(query)}")
    if args.state and state != args.state:
        sys.exit(f"state mismatch: expected {args.state!r}, got {state!r} — "
                 "possible stale/foreign callback, aborting")

    body = json.dumps({"client_id": client_id, "client_secret": client_secret,
                       "code": code}).encode("utf-8")
    req = urllib.request.Request(
        f"https://{shop}/admin/oauth/access_token", data=body,
        headers={"Content-Type": "application/json", "User-Agent": "JBA-brain/1.0"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        sys.exit(f"exchange failed (HTTP {e.code}): {detail}\n"
                 "Codes are single-use and short-lived — generate a fresh "
                 "authorize URL and try again promptly.")

    token = data.get("access_token")
    if not token:
        sys.exit(f"no access_token in response: {sorted(data)}")
    set_env_var("SHOPIFY_ACCESS_TOKEN", token)
    set_env_var("SHOPIFY_STORE_DOMAIN", shop)
    print(f"SUCCESS: token {token[:9]}… ({len(token)} chars) written to .env")
    print(f"  shop:   {shop}")
    print(f"  scopes: {data.get('scope')}")


if __name__ == "__main__":
    main()
