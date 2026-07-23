"""Shopify connector — governed listing management for the live store.

Talks to the GraphQL Admin API only (POST /admin/api/{VERSION}/graphql.json,
X-Shopify-Access-Token header). Shopify deprecated the REST product
endpoints for apps created after early 2025, and the "JBA Brain" custom app
is one of those — GraphQL is the supported path.

Scope of this connector mirrors the registry exactly:
- reads: list_products()/get_product() for the unified catalog + reviews.
- shopify.update_listing_copy  — title / descriptionHtml / SEO, reversible
  (read_state snapshots the current values; restore re-applies them).
- shopify.update_listing_images — image alt text + order, reversible.
- shopify.set_price is registered but in NO agent's allowed_actions
  (brain/actions/limits.yaml), so the executor escalates it to the CEO —
  this connector deliberately does not implement it.

Auth: SHOPIFY_ACCESS_TOKEN + SHOPIFY_STORE_DOMAIN from the environment
(.env). Same injectable-transport pattern as the Printful connector, so
tests never touch the network. Same ready-not-wired discipline as the Etsy
connector: without credentials every live method raises ShopifyNotConnected
with a plain next step.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable

from brain.actions.models import ActionType

API_VERSION = "2026-07"
USER_AGENT = "JBA-brain/1.0 (governed Shopify connector)"

# transport(method, url, headers, body_bytes) -> (status_int, parsed_json_or_None)
Transport = Callable[[str, str, dict, bytes | None], tuple[int, dict | None]]


class ShopifyError(RuntimeError):
    def __init__(self, status: int, detail):
        super().__init__(f"Shopify API error {status}: {detail}")
        self.status = status
        self.detail = detail


class ShopifyNotConnected(RuntimeError):
    def __init__(self, detail: str = ""):
        super().__init__(
            "Shopify is not connected. Set SHOPIFY_ACCESS_TOKEN and "
            "SHOPIFY_STORE_DOMAIN in .env (see the JBA Brain custom app). "
            + detail
        )


def _urllib_transport(method: str, url: str, headers: dict, body: bytes | None):
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = {"raw": raw}
        return e.code, parsed


def _gid(resource: str, id_or_gid) -> str:
    """Accept a bare numeric id or a full gid; return the gid Shopify wants."""
    s = str(id_or_gid)
    return s if s.startswith("gid://") else f"gid://shopify/{resource}/{s}"


class ShopifyConnector:
    def __init__(self, access_token: str | None = None,
                 store_domain: str | None = None,
                 transport: Transport | None = None):
        self.access_token = access_token
        self.store_domain = store_domain
        self._transport = transport or _urllib_transport

    @property
    def connected(self) -> bool:
        return bool(self.access_token and self.store_domain)

    def _gql(self, query: str, variables: dict | None = None) -> dict:
        if not self.connected:
            raise ShopifyNotConnected()
        headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT,
                   "X-Shopify-Access-Token": self.access_token}
        body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
        url = f"https://{self.store_domain}/admin/api/{API_VERSION}/graphql.json"
        status, data = self._transport("POST", url, headers, body)
        if status >= 400 or data is None:
            raise ShopifyError(status, data)
        if data.get("errors"):
            raise ShopifyError(status, data["errors"])
        return data["data"]

    @staticmethod
    def _check_user_errors(payload: dict, key: str) -> dict:
        node = payload.get(key) or {}
        errs = node.get("userErrors") or []
        if errs:
            raise ShopifyError(200, errs)
        return node

    # -- reads (free, non-mutating) --------------------------------------

    _PRODUCT_FIELDS = """
        id legacyResourceId title handle status descriptionHtml
        seo { title description }
        featuredMedia { preview { image { url } } }
        media(first: 20) {
            edges { node { id alt ... on MediaImage { image { url } } } }
        }
        variants(first: 100) {
            edges { node {
                id legacyResourceId title price sku
                selectedOptions { name value }
            } }
        }
    """

    def list_products(self, page_size: int = 50) -> list[dict]:
        """Every product in the store (all statuses), paginated. Returns the
        raw normalized GraphQL nodes; product_view_from_shopify() turns one
        into the unified ProductView."""
        out, cursor = [], None
        query = ("query($n: Int!, $after: String) { products(first: $n, after: $after) "
                 "{ pageInfo { hasNextPage endCursor } edges { node { %s } } } }"
                 % self._PRODUCT_FIELDS)
        while True:
            data = self._gql(query, {"n": page_size, "after": cursor})
            page = data["products"]
            out += [e["node"] for e in page["edges"]]
            if not page["pageInfo"]["hasNextPage"]:
                return out
            cursor = page["pageInfo"]["endCursor"]

    def get_product(self, product_id) -> dict:
        query = ("query($id: ID!) { product(id: $id) { %s } }" % self._PRODUCT_FIELDS)
        data = self._gql(query, {"id": _gid("Product", product_id)})
        if not data.get("product"):
            raise ShopifyError(404, f"product {product_id!r} not found")
        return data["product"]

    # -- Connector protocol (executor-only: read_state / execute / restore)

    def read_state(self, action_type: ActionType, params: dict) -> dict:
        product = self.get_product(params["product_id"])
        if action_type.name == "shopify.update_listing_copy":
            return {"product_id": params["product_id"],
                    "title": product["title"],
                    "description": product["descriptionHtml"],
                    "seo": product.get("seo") or {}}
        if action_type.name == "shopify.update_listing_images":
            media = [{"id": e["node"]["id"], "alt": e["node"].get("alt")}
                     for e in product["media"]["edges"]]
            return {"product_id": params["product_id"], "media": media}
        raise ShopifyError(0, f"unhandled snapshot for {action_type.name!r}")

    def execute(self, action_type: ActionType, params: dict) -> dict:
        if action_type.name == "shopify.update_listing_copy":
            return self._update_copy(
                params["product_id"], title=params.get("title"),
                description=params.get("description"),
                seo_description=params.get("seo"))
        if action_type.name == "shopify.update_listing_images":
            return self._update_images(params["product_id"], params["images"])
        raise ShopifyError(0, f"unhandled action {action_type.name!r}")

    def restore(self, action_type: ActionType, snapshot: dict) -> dict:
        if action_type.name == "shopify.update_listing_copy":
            seo = snapshot.get("seo") or {}
            out = self._update_copy(
                snapshot["product_id"], title=snapshot.get("title"),
                description=snapshot.get("description"),
                seo_title=seo.get("title"), seo_description=seo.get("description"))
            out["restored"] = "copy"
            return out
        if action_type.name == "shopify.update_listing_images":
            images = [{"id": m["id"], "alt": m.get("alt")}
                      for m in snapshot.get("media", [])]
            out = self._update_images(snapshot["product_id"], images)
            out["restored"] = "images"
            return out
        raise ShopifyError(0, f"unhandled restore for {action_type.name!r}")

    # -- mutations --------------------------------------------------------

    def _update_copy(self, product_id, title=None, description=None,
                     seo_title=None, seo_description=None) -> dict:
        """productUpdate for title/descriptionHtml/SEO. The registry's single
        'seo' string param maps to seo.description (the meta description);
        seo.title follows the listing title unless given explicitly."""
        product: dict = {"id": _gid("Product", product_id)}
        if title is not None:
            product["title"] = title
        if description is not None:
            product["descriptionHtml"] = description
        seo = {}
        if seo_title is not None or title is not None:
            seo["title"] = seo_title if seo_title is not None else title
        if seo_description is not None:
            seo["description"] = seo_description
        if seo:
            product["seo"] = seo
        mutation = """
            mutation($product: ProductUpdateInput!) {
                productUpdate(product: $product) {
                    product { id title }
                    userErrors { field message }
                }
            }"""
        data = self._gql(mutation, {"product": product})
        node = self._check_user_errors(data, "productUpdate")
        return {"product_id": str(product_id),
                "updated": sorted(set(product) - {"id"})}

    def _update_images(self, product_id, images: list[dict]) -> dict:
        """Alt-text updates (fileUpdate) and/or reorder (productReorderMedia).
        `images` is the desired list, in order: [{"id": <media gid>,
        "alt": <str or None>}, ...]. Only media with an 'alt' key get alt
        updates; order is applied for the whole list."""
        gid_product = _gid("Product", product_id)
        alt_updates = [{"id": img["id"], "alt": img["alt"]}
                       for img in images if "alt" in img and img["alt"] is not None]
        if alt_updates:
            mutation = """
                mutation($files: [FileUpdateInput!]!) {
                    fileUpdate(files: $files) {
                        files { id }
                        userErrors { field message }
                    }
                }"""
            data = self._gql(mutation, {"files": alt_updates})
            self._check_user_errors(data, "fileUpdate")
        moves = [{"id": img["id"], "newPosition": str(i)}
                 for i, img in enumerate(images)]
        if moves:
            mutation = """
                mutation($id: ID!, $moves: [MoveInput!]!) {
                    productReorderMedia(id: $id, moves: $moves) {
                        job { id }
                        userErrors { field message }
                    }
                }"""
            data = self._gql(mutation, {"id": gid_product, "moves": moves})
            self._check_user_errors(data, "productReorderMedia")
        return {"product_id": str(product_id),
                "alt_updated": len(alt_updates), "reordered": len(moves)}
