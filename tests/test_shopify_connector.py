"""Shopify connector tests — fake transport, never hits the network.
Covers GraphQL reads, the two governed actions' execute/read_state/restore
round-trips, disconnected behavior, and the printful+shopify sync merge."""

from __future__ import annotations

import json

import pytest

from brain.actions.registry import REGISTRY
from brain.connectors.shopify import (ShopifyConnector, ShopifyError,
                                      ShopifyNotConnected, _gid)
from brain.products import product_view_from_shopify


class FakeTransport:
    """Records calls; returns canned responses in FIFO order per call."""

    def __init__(self):
        self.calls = []
        self.queue = []

    def push(self, status, body):
        self.queue.append((status, body))

    def __call__(self, method, url, headers, body_bytes):
        self.calls.append({"method": method, "url": url, "headers": headers,
                           "body": json.loads(body_bytes) if body_bytes else None})
        return self.queue.pop(0) if self.queue else (200, {"data": {}})


def make_product_node(pid="7001", title="Bodysurf Fin Tumbler",
                      description="<p>old copy</p>"):
    return {
        "id": f"gid://shopify/Product/{pid}", "legacyResourceId": pid,
        "title": title, "handle": "wine-tumbler", "status": "ACTIVE",
        "descriptionHtml": description,
        "seo": {"title": title, "description": "old meta"},
        "featuredMedia": {"preview": {"image": {"url": "https://cdn/x.jpg"}}},
        "media": {"edges": [
            {"node": {"id": "gid://shopify/MediaImage/1", "alt": "front",
                      "image": {"url": "https://cdn/1.jpg"}}},
            {"node": {"id": "gid://shopify/MediaImage/2", "alt": None,
                      "image": {"url": "https://cdn/2.jpg"}}},
        ]},
        "variants": {"edges": [
            {"node": {"id": "gid://shopify/ProductVariant/9101",
                      "legacyResourceId": "9101", "title": "Black White",
                      "price": "19.00", "sku": "SKU1",
                      "selectedOptions": [{"name": "Color", "value": "Black White"}]}},
        ]},
    }


def connected(transport):
    return ShopifyConnector(access_token="shpat_test",
                            store_domain="test.myshopify.com",
                            transport=transport)


class TestGid:
    def test_wraps_numeric_and_passes_gid_through(self):
        assert _gid("Product", 7) == "gid://shopify/Product/7"
        assert _gid("Product", "gid://shopify/Product/7") == "gid://shopify/Product/7"


class TestDisconnected:
    def test_reads_and_protocol_raise_plain_next_step(self):
        c = ShopifyConnector()
        assert not c.connected
        with pytest.raises(ShopifyNotConnected, match="SHOPIFY_ACCESS_TOKEN"):
            c.list_products()
        with pytest.raises(ShopifyNotConnected):
            c.read_state(REGISTRY["shopify.update_listing_copy"], {"product_id": "1"})


class TestReads:
    def test_list_products_paginates(self):
        t = FakeTransport()
        t.push(200, {"data": {"products": {
            "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
            "edges": [{"node": make_product_node("1")}]}}})
        t.push(200, {"data": {"products": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "edges": [{"node": make_product_node("2")}]}}})
        nodes = connected(t).list_products()
        assert [n["legacyResourceId"] for n in nodes] == ["1", "2"]
        assert t.calls[1]["body"]["variables"]["after"] == "c1"
        assert t.calls[0]["headers"]["X-Shopify-Access-Token"] == "shpat_test"

    def test_graphql_errors_raise(self):
        t = FakeTransport()
        t.push(200, {"errors": [{"message": "boom"}]})
        with pytest.raises(ShopifyError, match="boom"):
            connected(t).list_products()


class TestUpdateListingCopy:
    def test_execute_maps_params_to_product_update(self):
        t = FakeTransport()
        t.push(200, {"data": {"productUpdate": {
            "product": {"id": "gid://shopify/Product/7001", "title": "New"},
            "userErrors": []}}})
        out = connected(t).execute(
            REGISTRY["shopify.update_listing_copy"],
            {"product_id": "7001", "title": "New",
             "description": "<p>new</p>", "seo": "new meta"})
        sent = t.calls[0]["body"]["variables"]["product"]
        assert sent["id"] == "gid://shopify/Product/7001"
        assert sent["title"] == "New"
        assert sent["descriptionHtml"] == "<p>new</p>"
        assert sent["seo"] == {"title": "New", "description": "new meta"}
        assert out["product_id"] == "7001"

    def test_user_errors_raise(self):
        t = FakeTransport()
        t.push(200, {"data": {"productUpdate": {
            "product": None,
            "userErrors": [{"field": ["title"], "message": "too long"}]}}})
        with pytest.raises(ShopifyError, match="too long"):
            connected(t).execute(
                REGISTRY["shopify.update_listing_copy"],
                {"product_id": "7001", "title": "x", "description": "d", "seo": "s"})

    def test_snapshot_then_restore_round_trip(self):
        t = FakeTransport()
        t.push(200, {"data": {"product": make_product_node()}})   # read_state
        c = connected(t)
        snap = c.read_state(REGISTRY["shopify.update_listing_copy"],
                            {"product_id": "7001"})
        assert snap["title"] == "Bodysurf Fin Tumbler"
        assert snap["description"] == "<p>old copy</p>"
        assert snap["seo"]["description"] == "old meta"

        t.push(200, {"data": {"productUpdate": {
            "product": {"id": "gid://shopify/Product/7001"}, "userErrors": []}}})
        out = c.restore(REGISTRY["shopify.update_listing_copy"], snap)
        sent = t.calls[1]["body"]["variables"]["product"]
        assert sent["title"] == "Bodysurf Fin Tumbler"
        assert sent["descriptionHtml"] == "<p>old copy</p>"
        assert sent["seo"] == {"title": "Bodysurf Fin Tumbler", "description": "old meta"}
        assert out["restored"] == "copy"


class TestUpdateListingImages:
    def test_execute_updates_alts_and_reorders(self):
        t = FakeTransport()
        t.push(200, {"data": {"fileUpdate": {"files": [], "userErrors": []}}})
        t.push(200, {"data": {"productReorderMedia": {"job": {"id": "j1"},
                                                     "userErrors": []}}})
        out = connected(t).execute(
            REGISTRY["shopify.update_listing_images"],
            {"product_id": "7001", "images": [
                {"id": "gid://shopify/MediaImage/2", "alt": "hero shot"},
                {"id": "gid://shopify/MediaImage/1"},
            ]})
        alts = t.calls[0]["body"]["variables"]["files"]
        assert alts == [{"id": "gid://shopify/MediaImage/2", "alt": "hero shot"}]
        moves = t.calls[1]["body"]["variables"]["moves"]
        assert moves[0] == {"id": "gid://shopify/MediaImage/2", "newPosition": "0"}
        assert out["alt_updated"] == 1 and out["reordered"] == 2

    def test_snapshot_captures_media_order_and_alts(self):
        t = FakeTransport()
        t.push(200, {"data": {"product": make_product_node()}})
        snap = connected(t).read_state(
            REGISTRY["shopify.update_listing_images"], {"product_id": "7001"})
        assert snap["media"] == [
            {"id": "gid://shopify/MediaImage/1", "alt": "front"},
            {"id": "gid://shopify/MediaImage/2", "alt": None},
        ]


class TestProductView:
    def test_normalizes_node_to_unified_view(self):
        view = product_view_from_shopify(make_product_node(),
                                         storefront_base="https://joshballart.com")
        assert view.platform == "shopify"
        assert view.product_id == "7001"
        assert view.status == "active"
        assert view.url == "https://joshballart.com/products/wine-tumbler"
        assert view.thumbnail_url == "https://cdn/x.jpg"
        assert view.variants[0].color == "Black White"
        assert view.variants[0].retail_price == "19.00"
        assert view.price_range == "$19.00"


class TestSyncMerge:
    def test_sync_products_merges_platforms(self, tmp_path, monkeypatch):
        from brain.main import sync_products

        class FakeShopify:
            connected = True
            def list_products(self):
                return [make_product_node()]

        class FakeHQ:
            def __init__(self):
                self.written = None
            def write_product_catalog(self, generated_at, products):
                self.written = products

        hq = FakeHQ()
        sync_products(hq, {"shopify": FakeShopify()})
        assert len(hq.written) == 1
        assert hq.written[0]["platform"] == "shopify"
        assert hq.written[0]["title"] == "Bodysurf Fin Tumbler"
