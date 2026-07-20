"""Unified product model, the HQ catalog snapshot, and the read-only
/api/products dashboard route."""

from __future__ import annotations

from brain.products import ProductView, VariantView, product_view_from_printful

PRINTFUL_DETAIL = {
    "sync_product": {"id": 555, "external_id": "mvd-quiet-game-tee",
                     "name": "Quiet Game Tee", "synced": True,
                     "thumbnail_url": "https://cdn/x.png"},
    "sync_variants": [
        {"id": 11, "variant_id": 4018, "retail_price": "26.00",
         "name": "Quiet Game Tee / Black / M"},
        {"id": 12, "variant_id": 4019, "retail_price": "26.00",
         "name": "Quiet Game Tee / Black / L"},
        {"id": 13, "variant_id": 4113, "retail_price": None,
         "name": "Quiet Game Tee / Navy / M"},
    ],
}


class TestProductView:
    def test_normalizes_a_printful_product(self):
        pv = product_view_from_printful(PRINTFUL_DETAIL)
        assert pv.platform == "printful"
        assert pv.title == "Quiet Game Tee"
        assert pv.external_id == "mvd-quiet-game-tee"
        assert pv.status == "synced"
        assert pv.colorways == ["Black", "Navy"]
        assert pv.sizes == ["M", "L"]
        assert len(pv.variants) == 3
        assert pv.variants[0].color == "Black" and pv.variants[0].size == "M"
        assert pv.variants[0].catalog_variant_id == 4018
        assert pv.variants[0].sync_variant_id == 11

    def test_price_range_and_margin(self):
        pv = product_view_from_printful(PRINTFUL_DETAIL)
        assert pv.price_range == "$26.00"  # one distinct set price; None ignored
        v = pv.variants[0]
        assert v.margin is None            # no base cost known
        v.base_cost = 14.18
        assert v.margin == round(26.0 - 14.18, 2)

    def test_price_range_spans_when_prices_differ(self):
        pv = ProductView(platform="printful", product_id="1", title="T", status="synced",
                         variants=[VariantView("Black", "M", retail_price="24.00"),
                                   VariantView("Black", "L", retail_price="30.00")])
        assert pv.price_range == "$24.00–$30.00"

    def test_unset_price_reads_not_set(self):
        pv = ProductView(platform="printful", product_id="1", title="T", status="unsynced",
                         variants=[VariantView("Black", "M", retail_price=None)])
        assert pv.price_range == "not set"

    def test_etsy_normalizes_into_the_same_shape(self):
        """The model is platform-agnostic — an Etsy listing round-trips through
        the same dict shape, so the dashboard/agent treat both identically."""
        etsy = ProductView(platform="etsy", product_id="900123", title="Quiet Game Tee",
                           status="active", external_id=None,
                           variants=[VariantView("Black", "M", retail_price="28.00")],
                           url="https://etsy.com/listing/900123")
        d = etsy.to_dict()
        assert d["platform"] == "etsy"
        assert d["price_range"] == "$28.00"
        assert ProductView.from_dict(d).to_dict() == d  # roundtrip stable


class TestHQCatalog:
    def test_write_then_read_roundtrips(self, hq):
        pv = product_view_from_printful(PRINTFUL_DETAIL)
        hq.write_product_catalog("2026-07-20T10:00:00", [pv.to_dict()])
        catalog = hq.read_product_catalog()
        assert catalog["generated_at"] == "2026-07-20T10:00:00"
        assert catalog["products"][0]["title"] == "Quiet Game Tee"

    def test_markdown_mirror_written_and_human_readable(self, hq):
        pv = product_view_from_printful(PRINTFUL_DETAIL)
        hq.write_product_catalog("2026-07-20T10:00:00", [pv.to_dict()])
        md = (hq.root / "products" / "catalog.md").read_text(encoding="utf-8")
        assert "Quiet Game Tee" in md
        assert "Black, Navy" in md
        assert hq.product_catalog_markdown() == md

    def test_empty_catalog_when_never_synced(self, hq):
        catalog = hq.read_product_catalog()
        assert catalog == {"generated_at": None, "products": []}


class TestProductsRoute:
    def test_api_products_reads_snapshot_no_live_call(self, config, hq):
        from fastapi.testclient import TestClient

        from brain.dashboard.app import create_app

        pv = product_view_from_printful(PRINTFUL_DETAIL)
        hq.write_product_catalog("2026-07-20T10:00:00", [pv.to_dict()])
        client = TestClient(create_app(config, hq))
        r = client.get("/api/products")
        assert r.status_code == 200
        body = r.json()
        assert body["generated_at"] == "2026-07-20T10:00:00"
        assert body["products"][0]["title"] == "Quiet Game Tee"

    def test_api_products_empty_before_first_sync(self, config, hq):
        from fastapi.testclient import TestClient

        from brain.dashboard.app import create_app

        client = TestClient(create_app(config, hq))
        assert client.get("/api/products").json() == {"generated_at": None, "products": []}
